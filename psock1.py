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

from iparts import cookey,make_respon2
from lite_back import app as flask_app
from lite_wsgi import run_with_cgi

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
    psock = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM, 0)
    return psock

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


def main_proc(num=0, host='0.0.0.0', port=8080):
    # if port is used then exit
    # work as server/arbiter/dispatcher
    try:
        assert is_port_clear(host, port) is True
    except AssertionError:
        print "PORT is USED!"
        raise

    workers = {}
    s_sockets = []
    num = num or 3
    server = None
    inited = False

    def clearup(pid=0):
        #single clear
        if pid > 0:
            os.kill(pid, signal.SIGUSR1)
            workers.pop(pid)
            return
        # all clear: before exit
        if server:
            make_inet_socket(host, port, presock=server)
        for pid in workers.keys():
            os.kill(pid, signal.SIGUSR1)

    def makecc(path):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM, 0)
        s.connect(path)
        return s

    def wdispatcher(headstr):
        gwid = cookey(headstr, cookey_mark)
        if gwid and gwid.isdigit():
            gwid = int(gwid)
            if gwid < len(s_sockets):
                print "get gwid from cookies: %s" % gwid
                return gwid
        print "no gwid from cookie!"
        return random.randint(1,100) % num

    def when_int_signal(sig, frame):
        print "INT SIGNAL CATCHED!"
        if workers:
            clearup()

    def patrol():
        # patrol for closed/overtime socket in input list
        # works with spsocket
        # patrol for dead sub-process and spawn new ones
        pass

    for _ in xrange(num):
        psock = make_unix_psock()
        worker = proc(psock[1])
        pid = os.fork()
        if pid != 0:
            workers[pid] = worker
            s_sockets.append(psock[0])
            psock[1].close()
            time.sleep(0.3)
            if _ >=num:
                print workers.keys()
                print s_sockets
                main_proc.__dict__['when_int_signal'] = when_int_signal
                signal.signal(signal.SIGINT, when_int_signal)
                inited = True
            continue
        break
        # sub
        #print len(workers)
    if inited is False:
        try:
            worker.socknum = _
            worker.xid = os.getpid()
            worker.do_proc()
            sys.exit(0)
        except Exception as e:
            print e
            raise
    #main proc
    counter = 0
    server = make_inet_socket(host, port)
    print "listening on %s:%s" % (host,port)
    if server is None:
        clearup()
    server.listen(1)
    inputs = [server]
    inputs.extend(s_sockets)
    outputs = []
    outq={}
    # main loop
    while True:
        counter += 1
        if counter > 120:
            clearup()
            return
        try:
            readable, writable, exceptional = select.select(inputs, outputs, inputs, 0.5)
        except:
            print 'Exception on Select'
            clearup()
            return
        for _ in readable:
            if _ is server:
                # server always listen so accept with another socket
                conn, client_addr = _.accept()
                print("new connection from", client_addr)
                # for fast hanlding put conn to input and handle it next loop
                conn.setblocking(0)
                inputs.append(conn)
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
    print 'all done'


class proc(object):
    # work as wsgi_holder + wsgi
    socknum = 0

    def __init__(self, isock):
        self.xid=0
        self.ear = isock
        self.app = None
        self.env = None
        self.headerdone=False

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
        #environ = dict(os.environ.items())
        environ=dict()
        environ['SERVER_NAME'] = '127.0.0.1'
        environ['SERVER_PORT'] = '8080'
        environ['REQUEST_METHOD'] = 'GET'
        environ['SCRIPT_NAME '] = ''
        environ['PATH_INFO'] = '/'
        environ['HTTP_HOST'] = '127.0.0.1'
        environ['wsgi.input'] = self.ear
        environ['wsgi.errors'] = self.ear
        environ['wsgi.version'] = (1, 0)
        environ['wsgi.multithread']  = False
        environ['wsgi.multiprocess'] = True
        environ['wsgi.run_once'] = True
        environ['wsgi.url_scheme'] = 'http'
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

    def do_proc(self):
        print "worker: %s socknum: %s" % (self.xid, self.socknum)
        signal.signal(signal.SIGUSR1, self.killme)
        self.some_ini()
        time.sleep(1)
        print "waiting from ..."
        inputs = [self.ear,]
        outputs = []
        while True:
            # by testing: listener still have to accept with another socktet
            try:
                infds, outfds, errfds = select.select(inputs,outputs,inputs,0.5)
            except:
                self.goodby()
            if infds and infds[0] is self.ear:
                data = self.ear.recv(1024)
                print "data from %s by data with len: %s" % (self.xid, len(data))
                self.headerdone = False
                respiter = self.wsgi(self.env, self.ear)
                time.sleep(0.2)
                # we can add cookies here
                result = self.app(self.env, respiter.start_response)
                #['200 OK', [('Content-Type', 'text/html; charset=utf-8'), ('Content-Length', '77'), ('Set-Cookie', 'gworkerid=1; Path=/')]]
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