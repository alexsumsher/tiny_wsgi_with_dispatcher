# -*- coding: utf-8 -
#
#A reporter:
#work with AF_INET mode(ON UDP) SOCK_DGRAM
#
from spsocket import spsocket,bsocket
import socket
import time


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


class RPserver(bsocket):
    """base on spsocket"""
    def_svr_addr = '0.0.0.0'
    def_svr_port = 19800
    clients = set()

    def __init__(self, svr_addr='', svr_port=0):
        super(RPserver, self).__init__(family=socket.AF_INET, dtype=socket.SOCK_DGRAM, flag=0)
        self.svr_addr = svr_addr or self.__class__.def_svr_addr
        self.svr_port = svr_port or self.__class__.def_svr_port
        self.bind((self.svr_addr, self.svr_port))

    def _rpcheck(self, rdata, client):
        rdatas = rdata.split('>>>>')
        if rdatas[0] == 'ACTION':
            if rdatas[1] == 'CHECK_SERVER':
                self.sendto('%s:%s' % (self.svr_addr, self.svr_port), client)
            elif rdatas[1] == 'REPORT':
                return rdatas[2]

    def take_report(self, whitelist=False, docache=False):
        try:
            reportdata, client = self.recvfrom(1024)
        except:
            raise
        if whitelist and client[0] not in self.__class__.clients:
                raise RuntimeError("CLIENT is NOT LIGGLE!")
        elif docache and len(self.__class__.clients) < 100:
            self.__class__.clients.add(client[0])
        self._rpcheck(reportdata, client)


class RPclient(bsocket):
    """base on spsocket"""

    def __init__(self, svr_addr='', svr_port=0, reporter=None):
        super(RPserver, self).__init__(family=socket.AF_INET, dtype=socket.SOCK_DGRAM, flag=0)
        self.svr_addr = svr_addr or self.__class__.def_svr_addr
        self.svr_port = svr_port or self.__class__.def_svr_port
        self.reporter = reporter
        self.c_ready = False

    def _parse_serverdata(self, data):
        sdatas = data.split(":")
        if len(datas) == 3:
            self.svr_addr = sdata[1]
            self.svr_port = int(sdata[2])
    
    def find_server(self, timeout=5, retries=3):
        if not self.svr_addr:
            t_addr = '255.255.255.255'
            self.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        else:
            t_addr = self.svr_addr
        hello_str = ">>>>ACTION>>>>CHECK_SERVER"
        self.sendto(hello_str, (t_addr, self.svr_port))
        for x in xrange(retries):
            try:
                self.settimeout(timeout)
                # self.recvfrom will not block for success
                srvdata = self.recv(128)
            except socket.timeout:
                print "SERVER NOT FOUND!"
                continue
            if srvdata:
                break
        self.c_ready = True
        self._parse_serverdata(svrdata)

    def post_report(self, reporter=None):
        reporter = reporter or self.reporter
        report_info = reporter() if callable(reporter) else str(reporter)
        if self.c_ready is False:
            self.find_server()
        if report_info:
            report_info = '>>>>ACTION>>>>REPORT>>>>' + report_info
            self.sendto(report_info, (self.svr_addr, self.svr_port))
        else:
            raise RuntimeError("no report data to send!")