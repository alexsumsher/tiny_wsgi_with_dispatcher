# -*- coding: utf-8 -
# 
from threading import Event, local
import signal
import os
import sys
import time
import select

from iparts import env_parseall
from lite_wsgi import Twsgi

class thread_env(local):

    def update(self, D):
        if isinstance(D, dict):
            for k,v in D.iteritems():
                self.__setattr__(k, v)

    def __getitem__(self, n):
        return self.__getattribute__(n)

    def export(self, **others):
        outd = dict()
        for a in dir(self)[16:]:
            if callable(self[a]):
                continue
            outd[a] = self[a]
        if others:
            outd.update(others)
        return outd


class mproc(object):
    # work as wsgi_holder + wsgi
    socknum = 0

    def __init__(self, isock, osock, app, islocal=True, isleader=False):
        self.xid=0
        self.ear = isock
        self.mouth = osock
        self.app = app
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
        self.mouth.close()
        sys.exit(exitcode)

    def some_ini(self):
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
        #self.wsgi = run_with_cgi

    def write(self, data, headers=None):
        if self.headerdone is False:
            if not headers:
                headerstr = make_respon2(data)
            else:
                status, response_headers = headers[:]
                headerstr = 'Status: %s\r\n' % status
                headerstr += '\r\n'.join(["%s: %s" % header for header in response_headers]) + '\r\n\r\n'
            self.mouth.sendall(headerstr + data)
            self.headerdone = True
            return
        self.mouth.sendall(data)

    def do_leader(self):
        # a leader's works:
        #print "this is leader"
        pass

    def do_proc(self):
        print "worker: %s socknum: %s" % (self.xid, self.socknum)
        signal.signal(signal.SIGUSR1, self.killme)
        self.some_ini()
        self.status = 1
        time.sleep(1)
        print "waiting from server ..."
        inputs = [self.ear,]
        outputs = []
        dcount = 120
        sevent = Event()
        sevent.set()

        while True:
            if self.isleader:
                self.do_leader()
            Uname = ''
            # by testing: listener still have to accept with another socktet
            try:
                infds, outfds, errfds = select.select(inputs, outputs, inputs, 0.5)
            except Exception as e:
                print 'listening error!'
                print e
                self.goodby()
            if infds and infds[0] is self.ear:
                data = self.ear.recv(1024)
                print "data from %s by with data" % self.xid
                if len(data) >= 14 and data[:10] == '<::0000::>':
                    Uname = data[10:14]
                    data = data[14:]
                if Uname and data:
                    print Uname,data
                    # cenv use for current http action , sevent, app, sender
                    cenv = env_parseall(data, origin_dict=self.env)
                    U = Twsgi(Uname, cenv, sevent, self.app, self.mouth)
                    Uname = ''
                    U.start()
                    U.join()
                #respiter = self.wsgi(cenv, self.mouth)
                # we can add cookies here
                #result = self.app(cenv, respiter.start_response)
                #try:
                #    for data in result:
                #        if data:    # don't send headers until body appears
                #            respiter.write(data)
                #            #self.write(data, respiter.headers_set)
                #finally:
                #    if hasattr(result, 'close'):
                #        result.close()
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