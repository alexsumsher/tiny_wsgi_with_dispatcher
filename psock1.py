# -*- coding: utf-8 -
#
# 测试：
# 目标是dispatcher调度器，可以通过事先预读cookie中的信息，将客户request分配到不同的子进程上，即某种意义上的会话保持；因为子进程的http app会cache已登录用户的信息，应当保证下次的客户连接接到对应的已登录服务器上;如果可以将功能加到gunicorn上。
# step1：主进程生成子进程；主进程监听网络（服务器），收到信息后，通过unix socket传递给本地监听的子进程
# setp2: 主进程通过cookies的gworkerid进行判断，如果没有该数值，则随机分配（初次接入的），然后将分配的结果保存在inet_socket表中，当后端返回数据后将按照分配表中的内容进行对应的返回。此时后端的首次response应携带相应的字段（gworkerid），后续将按照该字段内容始终分配给对应的unix_socket对应的worker，由于worker和wsgi一一对应，因此该用户将始终连接到worker对应的wsgi后端.（在wsgi的environ中附带gworkerID的内容）
# step3：wsgi 初步成功，使用wsgi类
# 
import os
import sys
import time
import select
import socket
import signal
import random
from datetime import datetime as dt
# from __future__ import division

from iparts import cookey, make_respon2, env_parseall, inmsger
from lite_back import app as flask_app
from lite_wsgi import run_with_cgi
from spsocket import spsocket

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
    # the last assigned proc_number, if new proc created, proc_number +=1 as 
    # worker's id which is the key of worker in workers dict.
    main_proc.last_proc_num = 0
    main_proc.isleader = True
    main_proc.inited = False

    # workers: {af_unix_socket_fileno: workerpid}
    workers = {}
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
            os._exit()

    def proc_maintain():
        # proc_num is outer variable, in local function, which could be read but not write
        # 填坑模式
        for n in xrange(len(s_sockets)):
            if s_sockets[n] is not None:
                continue
            psock = make_unix_psock()
            worker = proc(psock[1], isleader=main_proc.isleader)
            main_proc.isleader = False
            main_proc.inited = False
            main_proc.last_proc_num = n
            wpid = os.fork()
            if wpid != 0:
                workers[psock[0].fileno()] = wpid
                s_sockets[n] = psock[0]
                psock[1].close()
                time.sleep(0.3)
            else:
                return worker
        print workers
        print s_sockets
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
            except socket.error:
                # die
                s = s_sockets[n]
                fno = s.fileno()
                debugstr += 'stick_sockt file_no: %s is die and replace with new one!' % fno
                clearup(fno)
                s_sockets[n] = None
                c += 1
        print debugstr
        return proc_maintain() if c else None

    # at the very beginning, proc_num is 0 and set to proc_num_limit - 1 after first time proc_maintain
    # main_proc return with number of workers, and sub proc return cur worker
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
    inputs.extend(s_sockets)
    outputs = []
    outq = {}
    # main loop
    while True:
        try:
            readable, writable, exceptional = select.select(inputs, outputs, inputs, 0.5)
        except:
            print 'Exception on Select'
            clearup()
            return
        # handle: server_socket; worker_socket; client_socket
        for _ in readable:
            if _ is server:
                # server always listen so accept with another socket
                conn, client_addr = server.accept()
                print("new connection from", client_addr)
                # for fast hanlding put conn to input and handle it next loop
                conn.setblocking(0)
                inputs.append(conn)
                print inputs
            else:
                data = _.recv(1024)
                if data:
                    fromer = _.getpeername()[0] if _.family == socket.AF_INET else 'sock'
                    print('received data with len %s from %s' % (len(data), fromer))
                    # when data from proc send data to client with output
                    # devide for tcp and unix socket
                    if _.family == socket.AF_INET:
                        v = wdispatcher(data)
                        #os.write(s_sockets[v], '1bcdef')
                        s = s_sockets[v]
                        s.send(data)
                        # make the inet connectin for return data
                        sname = "%s_%s" % (v, s.fileno())
                        outq[sname] = _
                        # the unix con s should wait for respon from proc, so put into inputs
                        # pattern: index-of-socket-in-s_sockets_inet-fileno "0~num_fileno" like: 0_112
                    elif _.family == socket.AF_UNIX:
                        sname = "%s_%s" % (s_sockets.index(_), _.fileno())
                        s_inet = outq.get(sname)
                        if s_inet:
                            print "put data back to client with inet socket: %s" % sname
                            s_inet.send(data)
                            outq.pop(sname)
                            # if keep alive will difference
                            s_inet.close()
                            inputs.remove(s_inet)
                        else:
                            print "not found the correct connection to inet with name: %s" % sname
                else:
                    #print "no data recv!"
                    if _.family == socket.AF_UNIX:
                        _.setblocking(0)
                    else:
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
        if counter > 30:
            # patrol for dead socket in s_socket(connect to a worker identifed by socket.workerpid)
            patroler = patrol()
            if isinstance(patroler, proc):
                break
            counter = 0
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


class proc(object):
    # work as wsgi_holder + wsgi
    socknum = 0

    def __init__(self, isock, islocal=True, isleader=False):
        self.xid=0
        self.ear = isock
        self.app = None
        self.env = None
        self.status = 0
        self.headerdone=False
        self.islocal = islocal
        self.isleader = isleader

    def killme(self, sig, frame):
        print "killme signal"
        self.goodby(1)

    def goodby(self, exitcode=0):
        print "time to say goodby!"
        self.ear.close()
        sys.exit(exitcode)

    def some_ini(self):
        if callable(flask_app):
            self.app = flask_app
        if self.islocal:
            environ=dict()
        else:
            print "local is False and get os environ!"
            environ = dict(os.environ.items())
        environ['SERVER_NAME'] = os.environ.get('current_host', '127.0.0.1')
        environ['SERVER_PORT'] = os.environ.get('current_port', '8080')
        # here for a lite mode, not set the input/errors
        environ['wsgi.input'] = self.ear
        environ['wsgi.errors'] = self.ear
        # spcial vars
        environ['wsgi.gworkerid'] = self.socknum
        self.env = environ
        self.wsgi = run_with_cgi

    def write(self, data, headers=None):
        if self.headerdone is False:
            if not headers:
                headerstr = make_respon2(data)
            else:
                status, response_headers = headers[:]
                headerstr = 'Status: %s\r\n' % status
                headerstr += '\r\n'.join(["%s: %s" % header for header in response_headers]) + '\r\n\r\n'
            self.ear.sendall(headerstr + data)
            self.headerdone = True
            return
        self.ear.sendall(data)

    def do_leader(self):
        # a leader's works:
        print "this is leader"
        pass

    def do_proc(self):
        print "worker: %s socknum: %s" % (self.xid, self.socknum)
        signal.signal(signal.SIGUSR1, self.killme)
        self.some_ini()
        self.status = 1
        time.sleep(1)
        print "waiting from ..."
        inputs = [self.ear,]
        outputs = []
        dcount = 120
        while True:
            if self.isleader:
                self.do_leader()
            # by testing: listener still have to accept with another socktet
            try:
                infds, outfds, errfds = select.select(inputs,outputs,inputs,0.5)
            except:
                self.goodby()
            if infds and infds[0] is self.ear:
                data = self.ear.recv(1024)
                print "data from %s by data with len: %s" % (self.xid, len(data))
                self.headerdone = False
                # cenv use for current http action
                cenv = env_parseall(data, origin_dict=self.env)
                respiter = self.wsgi(cenv, self.ear)
                # we can add cookies here
                result = self.app(cenv, respiter.start_response)
                try:
                    for data in result:
                        if data:    # don't send headers until body appears
                            respiter.write(data)
                            #self.write(data, respiter.headers_set)
                finally:
                    if hasattr(result, 'close'):
                        result.close()
                #self.ear.sendall(make_respon('<h1>hello,world</h1>', {cookey_mark: self.socknum}))
            if errfds:
                print "error FDS!"
                print errfds
                try:
                    self.ear.close()
                except:
                    pass
                self.goodby(101)
        #os._exit(101)
        #sys.exit(0)

if __name__ == '__main__':
    main_proc()