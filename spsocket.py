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


class bsocket(socket.socket):

    @classmethod
    def wrapsocket(cls, fromsocket):
        if isinstance(fromsocket, socket.socket):
            return cls(fromsocket)
        else:
            raise TypeError("not a socket instance pass in!")

    def __init__(self, family=2, dtype=1, flag=0, fromsocket=None):
        if fromsocket:
            self._socket = fromsocket
            self._sock = self._socket._sock
        else:
            self._socket = None
            super(bsocket, self).__init__(family, dtype, flag)

    def __getattr__(self, pn):
        # when the socket comes from socket.socket(by cls.wrapsocket) redirect the attributies
        return getattr(self, pn) if hasattr(self, pn) else getattr(self._socket, pn)

#A local socket
class spsocket(socket.socket):
    #AF_UNIX=1;AF_INET=2
    #SOCK_STREAM=1;SOCK_DGRAM=2;SOCK_RAW=3
    S_CLOSED = -1
    S_WORK = 1
    S_WAIT = 0
    overtime = 120

    @classmethod
    def wrapsocket(cls, fromsocket):
        if isinstance(fromsocket, socket.socket):
            return cls(fromsocket)
        else:
            raise TypeError("not a socket instance pass in!")

    def __init__(self, family=2, dtype=1, flag=0, rsmode=0, ltime=0, fromsocket=None):
        if fromsocket:
            self._socket = fromsocket
            self._sock = self._socket._sock
        else:
            self._socket = None
            super(spsocket, self).__init__(family, dtype, flag)
        self.status = self.S_WAIT
        self.stime = time.time()
        # keep_alive time , 0 means use and close
        self.keep_alive = ltime
        if ltime > 0:
            self.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, True)
        # receive and send mode: one time receive and one time send then close
        # if set to 1 then go, when receive rsmode +1, when send rsmode +2, rsmode=4 close
        self.rsmode = rsmode
        self.isserver = False

    def __getattr__(self, pn):
        # when the socket comes from socket.socket(by cls.wrapsocket) redirect the attributies
        return getattr(self, pn) if hasattr(self, pn) else getattr(self._socket, pn)

    def __repr__(self):
        if self.isserver:
            return 'Server:'
        return str(self._sock)
    
    def accept(self, set_blocking=0):
        if self._socket:
            newcon, addr = self._socket.accept()
        else:
            newcon, addr = super(spsocket, self).accept()
        newcon = self.__class__.wrapsocket(newcon)
        return newcon, addr

    def close(self):
        self.status = self.S_CLOSED
        if self._socket:
            self._socket.close()
        else:
            super(spsocket, self).close()

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
            raise RuntimeError("SOCKET is alreay Server!")
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

    def destroy(self, chktime=0):
        chktime = chktime or time.time()
        if chktime - self.stime > self.overtime or chktime - self.stime > self.keep_alive:
            self.close()
            return True
        else:
            return False