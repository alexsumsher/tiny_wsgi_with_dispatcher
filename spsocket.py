# -*- coding: utf-8 -
#
# split from main file.
# special socket from socket
# 
import socket
import time


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


#A local socket
class spsocket(socket.socket):
    #AF_UNIX=1;AF_INET=2
    #SOCK_STREAM=1;SOCK_DGRAM=2;SOCK_RAW=3
    S_CLOSED = -1
    S_WORK = 1
    S_WAIT = 0
    overtime = 120

    def __init__(self, family=2, dtype=1, proto=0, rsmode=0, ltime=0):
        # _socket = True => socket made by socketpair
        super(spsocket, self).__init__(family, dtype, proto)
        self.status = self.S_WAIT
        self.stime = time.time()
        # keep_alive time , 0 means use and close
        self.keep_alive = ltime
        if ltime > 0:
            self.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        # receive and send mode: one time receive and one time send then close
        # if set to 1 then go, when receive rsmode +1, when send rsmode +2, rsmode=4 close
        self.rsmode = rsmode
        self.isserver = False

    def __getattr__(self, pn):
        # when the socket comes from socket.socket(by cls.wrapsocket) redirect the attributies
        return getattr(self, pn) if hasattr(self, pn) else getattr(super(spsocket, self), pn)

    def __repr__(self):
        if self.isserver:
            return 'Server:'
        return str(self._sock)

    """
    def spaccept(self, set_blocking=0):
        # return my socket
        xsocket = self._socket or self
        newcon, addr = xsocket.accept()
        if newcon:
            newcon.setblocking(set_blocking)
            newcon = self.__class__.wrapsocket(newcon)
        return newcon, addr
    """

    def do_netserver(self, addr, port, backlog=5):
        if self.isserver:
            print "SOCKET is alreay Server!"
            return False
        assert is_port_clear(addr, port)
        self.bind((addr, port))
        self.setblocking(0)
        self.listen(backlog)
        self.isserver = True
        return True

    #sp-actions will do someting more
    def spsendall(self, data):
        self.stime = time.time()
        self.sendall(data)
        if self.rsmode >0:
            self.rsmode += 2
            if self.rsmode == 4:
                self.close()
                self.status = self.S_CLOSED

    def sprecv(self, length=1024, autoclose=False):
        self.stime = time.time()
        rv = self.recv(length)
        if autoclose:
            self.close()
            self.status = self.S_CLOSED
        if self.rsmode > 0:
            self.rsmode += 1
            if self.rsmode == 4:
                self.close()
                self.status = self.S_CLOSED
        return rv

    def sp_recvall(self, length=1024):
        maxcount = 1024
        collector = b''
        for x in xrange(maxcount, 0, -1):
            seg = self.recv(length)
            if len(seg) == 0:
                break
            collector += seg
        self.stime = time.time()
        return collector

    def destroy(self, chktime=0, force=False):
        chktime = chktime or time.time()
        if force or chktime - self.stime > self.overtime or chktime - self.stime > self.keep_alive:
            self.close()
            return True
        else:
            return False


class sock_assist(object):

    #https://docs.python.org/2.7/library/select.html#module-select:
    #Among the acceptable object types in the sequences are Python file objects (e.g. sys.stdin, or objects returned by open() or os.popen()), socket objects returned by socket.socket(). You may also define a wrapper class yourself, as long as it has an appropriate fileno() method (that really returns a file descriptor, not just a random integer).
    def __init__(self, fromsocket=None, family=2, dtype=1, proto=0):
        if fromsocket is None:
            self.socket = socket.socket(family, dtype, proto)
        elif isinstance(fromsocket, socket.socket):
            self.socket = fromsocket
            self._sock = self.socket._sock
        # elif (type of pairsocket) ....
        else:
            raise NotImplementedError
        self.keep_alive = False
        self.stime = time.time()

    def socket_attr(self, attname):
        return getattr(self.socket, attname)

    def fileno(self):
        return self['fileno']()

    def __getitem__(self, iname):
        # spcial:
        # self.recv() and self['recv']()
        return getattr(self.socket, iname)

    def destroy(self):
        if self.keep_alive:
            return False
        self.socket.close()
        return True