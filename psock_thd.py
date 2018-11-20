# -*- coding: utf-8 -
#
# 测试：
# 目标是dispatcher调度器，可以通过事先预读cookie中的信息，将客户request分配到不同的子进程上，即某种意义上的会话保持；因为子进程的http app会cache已登录用户的信息，应当保证下次的客户连接接到对应的已登录服务器上;如果可以将功能加到gunicorn上。
# step1：主进程生成子进程；主进程监听网络（服务器），收到信息后，通过unix socket传递给本地监听的子进程
# setp2: 主进程通过cookies的gworkerid进行判断，如果没有该数值，则随机分配（初次接入的），然后将分配的结果保存在inet_socket表中，当后端返回数据后将按照分配表中的内容进行对应的返回。此时后端的首次response应携带相应的字段（gworkerid），后续将按照该字段内容始终分配给对应的unix_socket对应的worker，由于worker和wsgi一一对应，因此该用户将始终连接到worker对应的wsgi后端.（在wsgi的environ中附带gworkerID的内容）
# step3：wsgi 初步成功，使用wsgi类
# step4: 多线程，双路arbiter<=>worker [A-(send)-W and A-(recv)-W] 2 pair work
# 
import os
import sys
import time
import select
import socket
import signal
import random
from datetime import datetime as dt
from threading import Lock, local
# from __future__ import division

from iparts import cookey, make_respon2, env_parseall, inmsger
from lite_wsgi import run_with_cgi
from spsocket import spsocket
from mthreads import mproc
from lite_back import app

# update:
# work with spsocket

cookey_mark = 'gworkerid'

def make_unix_socket(path, psock=None):
    if psock:
        for s in psock:
            s.close()
        return
    usock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM, 0)
    if os.path.exists(path):
        os.unlink(path)
    usock.bind(path)
    return usock

def make_unix_psock():
    # pair socket is good to use
    psock_a,psock_b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM, 0)
    psock_a.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    psock_b.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    return psock_a,psock_b

def make_inet_socket(ipaddr, port, presock=None):
    if presock:
        presock.close()
        return
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(0)
    try:
        sock.bind((ipaddr,port))
    except socket.error:
        print 'bind wrong!'
        sock.close()
        return None
    return sock

def is_port_clear(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        rlt = sock.connect_ex((host, port))
        sock.close()
    except:
        # if host not found some... false
        print "connect error!"
        return False
    # if we can connect to port rlt==0 means port is used!
    return False if rlt == 0 else True


# single server mode
# if distribute mode? works with inet
def main_proc(proc_num_limit=0, host='0.0.0.0', port=8080):
    # if port is used then exit
    # work as server/arbiter/dispatcher
    try:
        assert is_port_clear(host, port) is True
    except AssertionError:
        print "PORT is USED!"
        raise
    
    # i don't wanna use class, so....
    main_proc.proc_num_limit = proc_num_limit or 3
    # the last assigned proc_number, if new mproc created, proc_number +=1 as 
    # worker's id which is the key of worker in workers dict.
    main_proc.last_proc_num = 0
    main_proc.isleader = True
    main_proc.inited = False

    # workers: {af_unix_socket_fileno: workerpid}
    # r_sockets: receiv from worker
    # s_sockets: send to worker
    # r_sockets[n] <=Worker=>s_sockets[n]
    workers = {}
    r_sockets = [None] * main_proc.proc_num_limit
    s_sockets = [None] * main_proc.proc_num_limit
    server = None
    # server info set to environment
    os.environ['current_host'] = host
    os.environ['current_port'] = str(port)

    def clearup(fno=0):
        #single clear
        if fno > 0:
            wpid = workers[fno]
            os.kill(wpid, signal.SIGUSR1)
            workers.pop(fno)
            return fno
        # all clear: before exit
        if server:
            server.destroy(force=True)
            os.environ.pop('current_host')
            os.environ.pop('current_port')
        for fo in workers.keys():
            wpid = workers.pop(fo)
            os.kill(wpid, signal.SIGUSR1)

    def makecc(path):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM, 0)
        s.connect(path)
        return s

    def wdispatcher(headstr):
        # if we use leader, who's job is more than normal worker
        # dispatcher like:
        # py3: from __future__ import division; round(random.randint(1,100)%7/2+0.1)
        # py2: round(float(random.randint(1,100))%7/2+0.1)
        # py2: seler = [0]; [seler.extend([_]*2) for _ in xrange(num-1)];random.choice(seler)
        gwid = cookey(headstr, cookey_mark)
        if gwid and gwid.isdigit():
            gwid = int(gwid)
            if gwid < len(s_sockets):
                print "get gwid from cookies: %s" % gwid
                return gwid
        print "no gwid from cookie!"
        return random.randint(1,100) % main_proc.proc_num_limit

    def when_int_signal(sig, frame):
        print "INT SIGNAL CATCHED!"
        if workers:
            clearup()
            os._exit(0)

    def proc_maintain():
        # proc_num is outer variable, in local function, which could be read but not write
        # 填坑模式
        for n in xrange(len(s_sockets)):
            if s_sockets[n] is not None:
                continue
            psock_a2w = make_unix_psock()
            psock_w2a = make_unix_psock()
            worker = mproc(psock_a2w[1], psock_w2a[1], app, isleader=main_proc.isleader)
            main_proc.isleader = False
            main_proc.inited = False
            main_proc.last_proc_num = n
            wpid = os.fork()
            if wpid != 0:
                workers[psock_a2w[0].fileno()] = wpid
                s_sockets[n] = psock_a2w[0]
                r_sockets[n] = psock_w2a[0]
                psock_a2w[1].close()
                psock_w2a[1].close()
                time.sleep(0.3)
            else:
                return worker
        #print workers
        #print s_sockets, r_sockets
        main_proc.when_int_signal = when_int_signal
        signal.signal(signal.SIGINT, when_int_signal)
        main_proc.inited = True
        return main_proc.last_proc_num

    def patrol():
        # patrol for closed/overtime socket in input list
        # works with spsocket
        # patrol for dead sub-process and spawn new ones
        print '------patroling--------'
        debugstr = ''
        chktime = time.time()
        c = 0
        for n in xrange(len(s_sockets)):
            try:
                s_sockets[n].getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                r_sockets[n].getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            except socket.error:
                # die
                debugstr += 'stick_sockt index: %s is die and replace with new one!' % n
                clearup(s.fileno())
                s_sockets[n] = None
                r_sockets[n] = None
                c += 1
        print debugstr
        return proc_maintain() if c else None

    # at the very beginning, proc_num is 0 and set to proc_num_limit - 1 after first time proc_maintain
    # main_proc return with number of workers, and sub mproc return cur worker
    worker = proc_maintain()
    # sub process!
    # print len(workers)
    if main_proc.inited is False:
        try:
            worker.socknum = main_proc.last_proc_num
            worker.xid = os.getpid()
            worker.do_proc()
            sys.exit(0)
        except Exception as e:
            print e
            raise
    # main process!
    counter = 0
    server = spsocket()
    if server.do_netserver(host, port, 1):
        print "listening on %s:%s" % (host,port)
    else:
        clearup()
        return
    inputs = [server]
    inputs.extend(r_sockets)
    outputs = []
    # on multithread, outq = {work1: {threadid1: con1, threadid2: con2, ...}, work2: ...}
    # wating_cons = {work1: con1, work2: con2, ...} one con per work, when r_socket get "<::0000::>????"
    # next_cons = {work1: con1, work2: con2, ...} one con per work, when r_socket get "<::1111::>????"
    # rdata[:10] == '<::0000::>'?threadid=rdata[10:]
    outq = {}
    next_cons = {}
    smark = '<::0000::>??'
    # main loop
    while True:
        try:
            readable, writable, exceptional = select.select(inputs, outputs, inputs, 0.1)
        except Exception as e:
            print 'Exception on Select %s' % e
            clearup()
            return
        # handle: server_socket; worker_socket; client_socket
        print 'lenth of coming sock: %s' % len(readable)
        # 如果select是线性扫描，则如有client connnect必然在首位
        # https://blog.csdn.net/q8250356/article/details/81058396
        if readable and readable[0] is server:
            svr = readable.pop(0)
            # server always listen so accept with another socket
            conn, client_addr = server.accept()
            print("new connection from", client_addr)
            # for fast hanlding put conn to input and handle it next loop
            conn.setblocking(0)
            # 直接处理？通常client发起connect的同时会立刻发送数据
            # 可能策略2：select只循环[server,]并将accept生成的conn列表，一直到到没有接入要求时再开始处理conn列表的recv操作？
            readable.append(conn)
            #inputs.append(conn)
        for _ in readable:
            data = _.recv(1024)
            if not data:
                continue
            fromer = _.getpeername()[0] if _.family == socket.AF_INET else 'sock'
            print('received data with len %s from %s' % (len(data), fromer))
            # when data from mproc send data to client with output
            # devide for tcp and unix socket
            if _.family == socket.AF_INET:
                v = wdispatcher(data)
                #os.write(s_sockets[v], '1bcdef')
                fno = _.fileno()
                s = s_sockets[v]
                # presending message=> which conn has hold the connection with clients
                s.sendall('<::0000::>{:0>4d}'.format(fno))
                s.send(data)
                # make the inet connectin for return data
                outq[fno] = _
                # the unix con s should wait for respon from mproc, so put into inputs
                # pattern: cause we are under the syn mode, only one conn on a r_socket, so use index of unix socket for name of conn
            elif _.family == socket.AF_UNIX:
                # data from unix means comes from worker from r_sockets
                # chcek the target con:
                rname = r_sockets.index(_)
                s_inet = None
                if len(data) >= 14 and data[:10] == '<::1111::>':
                    target_con = int(data[10:14])
                    # if one time mode: system_control_head + realdata
                    data = data[14:]
                    next_cons.pop(rname).close() if rname in next_cons else None
                    next_cons[rname] = outq.pop(target_con)
                #print rname, target_con, data
                if data:
                    s_inet = next_cons.get(rname)
                if s_inet:
                    print "put data back to client with inet socket: %s" % target_con
                    s_inet.send(data)
                    # if keep alive will difference
                    try:
                        inputs.remove(s_inet)
                    except:
                        print 'error on remove s_inet!'
                        continue
                else:
                    print "not found the correct connection to inet with name: %s" % target_con
                    continue
            else:
                print "bad recv!"
                inputs.remove(_)
                _.close()
        if exceptional:
            print "error FDS!"
            print exceptional
            for _ in exceptional:
                try:
                    _.close()
                    inputs.remove(_)
                except:
                    pass
        # count for patrol
        counter += 1
        if counter > 120:
            counter = 0
            # patrol for dead socket in s_socket(connect to a worker identifed by socket.workerpid)
            patroler = patrol()
            if isinstance(patroler, mproc):
                break
    # when patrol action break the loop; a new name "patroler" shuld be create as a worker(proc class)
    print "break from the main loop cause forked as sub-process"
    try:
        patroler.socknum = main_proc.last_proc_num
        patroler.xid = os.getpid()
        patroler.do_proc()
        sys.exit(0)
    except Exception as e:
        print e
        raise


if __name__ == '__main__':
    main_proc()