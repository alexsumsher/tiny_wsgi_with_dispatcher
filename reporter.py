# -*- coding: utf-8 -
#
#A reporter:
#work with AF_INET mode(ON UDP) SOCK_DGRAM
#
from spsocket import spsocket
import socket
import time
import select
import signal


class RP_ERROR(Exception):
    def __init__(self, code, msg=''):
        self.code = code
        self.msg = msg

    def __repr__(self):
        return "RP_ERROR: %s(code:%s)" % (self.msg, self.code)


class reporter(object):
    """
    reporter's job:
    reporter worker's status to leader/arbiter interval
    step:
    create a listener/client socket;
    client: if server is not specified, broadcast for server then record server address;
    server: listen on a port for report and broadcast;
    send reports, if error test server on line? if no -> broadcast for server until deadtimes;
    SUB CLASS: interval_reporter; living_reporter
    """
    def_svr_port = 19800
    find_server_timeout = 5
    clients = set()

    def __init__(self, svr_addr='', svr_port=0):
        self.sck_server = None
        self.c_ready = False
        self.svr_addr = svr_addr
        self.svr_port = svr_port or self.__class__.def_svr_port

    def reset(self, svr_addr='', svr_port=0):
        if self.sck_server:
            self.sck_server.destroy()
            self.sck_server = None
        if svr_addr:
            self.svr_addr = svr_addr
        if svr_port:
            self.svr_port = svr_port
        self.c_ready = False

    def ini_server(self, addr='', port=0, timeout=5):
        self.sck_server = spsocket(socket.AF_INET, socket.SOCK_DGRAM, 0)
        if addr:
            self.svr_addr = addr
        if port:
            self.svr_port = port
        try:
            self.sck_server.bind((self.svr_addr, self.svr_port))
            self.settimeout(timeout)
        except:
            raise RuntimeError("Server Not DONE!!")

    def find_server(self, timeout=5):
        if self.sck_server:
            raise RuntimeError("reporter is already work on server mode!")
        fsock = spsocket(socket.AF_INET, socket.SOCK_DGRAM, 0)
        if not self.svr_addr:
            t_addr = '255.255.255.255'
            fsock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        else:
            t_addr = self.svr_addr
        fsock.sendto((t_addr, self.svr_port))
        try:
            fsock.settimeout(timeout)
            srvdata = fsock.recv(128)
        except socket.timeout:
            print "SERVER NOT FOUND!"
            raise
        self.c_ready = True
        self._parse_serverdata(svrdata)

    def _parse_serverdata(self, data):
        sdatas = data.split(":")
        if len(datas) == 3:
            self.svr_addr = sdata[1]
            self.svr_port = int(sdata[2])

    def post_report(self, report_info):
        if self.c_ready:
            self.sendto(report_info, (self.svr_addr, self.svr_port))

    def take_report(self, whitelist=False, docache=False):
        if self.sck_server is None:
            raise RuntimeError("WE ARE NOT WORK AS SERVER!")
        reportdata, client = self.recvfrom(1024)
        if whitelist and client[0] not in self.__class__.clients:
                raise RuntimeError("CLIENT is NOT LIGGLE!")
        elif docache and len(self.__class__.clients) < 100:
            self.__class__.clients.add(client[0])


class BReporter(object):

    SMODE = 0
    CMODE = 1
    def_svr_port = 19800

    def __new__(cls, mode):
        if mode == self.SMODE:
            return Rpt_Server
        else:
            return Rpt_Clien

    def __init__(self):
        pass

    def jobs(self):
        raise NotImplementedError("Do JOBS!")

    def do_work(self):
        inputs = [self._socket,]
        outputs = []
        while 1:
            try:
                rtbls,wtbls,ess = select.select(inputs, outputs, inputs, 0.5)
            except:
                return
            for i in rtbls:
                if i = self._socket:
                    self.jobs()
                else:
                    pass
            if wtbls:
                for i in wtbls:
                    pass
            if ess:
                for i in ess:
                    pass


class Rpt_Server(BReporter):
    clients = set()

    def __init__(self, svr_port):
        self._socket = spsocket()


class Rpt_Clien(BReporter):
    find_server_timeout = 5