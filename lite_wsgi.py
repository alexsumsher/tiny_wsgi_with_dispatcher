# -*- coding: utf-8 -

import os, sys
from threading import Thread

class run_with_cgi(object):

    def_env = {
        'wsgi.version': (1, 0),
        'wsgi.multithread': False,
        'wsgi.multiprocess': True,
        'wsgi.run_once': True,
        'wsgi.url_scheme': 'http',
        }

    def __init__(self, environ, sender):
        self.environ = environ
        self.environ.update(self.__class__.def_env)
        self.sender = sender

        if self.environ.get('HTTPS', 'off') in ('on', '1'):
            self.environ['wsgi.url_scheme'] = 'https'
        else:
            self.environ['wsgi.url_scheme'] = 'http'

        self.headers_set = []
        self.headers_sent = []

    def write(self, data):
        headerstr = ''
        if not self.headers_set:
            raise AssertionError("write() before start_response()")
        elif not self.headers_sent:
            # Before the first output, send the stored headers
            status, response_headers = self.headers_sent[:] = self.headers_set
            headerstr = 'HTTP/1.1 %s\r\n' % status
            for header in response_headers:
                headerstr += '%s: %s\r\n' % header
            headerstr += '\r\n'
            self.sender.sendall(headerstr)
        self.sender.sendall(data)

    def start_response(self, status, response_headers, exc_info=None):
        if exc_info:
            try:
                if self.headers_sent:
                    # Re-raise original exception if headers sent
                    raise exc_info[0], exc_info[1], exc_info[2]
            finally:
                exc_info = None     # avoid dangling circular ref
        elif self.headers_set:
            raise AssertionError("Headers already set!")

        self.headers_set[:] = [status, response_headers]
        return self.write


class Twsgi(Thread):
    globalwait = 5
    def_env = {
        'wsgi.version': (1, 0),
        'wsgi.multithread': False,
        'wsgi.multiprocess': True,
        'wsgi.run_once': True,
        'wsgi.url_scheme': 'http',
        }

    def __init__(self, name, environ, ev, app, sender):
        super(Twsgi, self).__init__()
        self.name = name
        self.env = environ
        self.env.update(self.__class__.def_env)
        self.ev = ev
        self.app = app
        self.sender = sender

        if self.env.get('HTTPS', 'off') in ('on', '1'):
            self.env['wsgi.url_scheme'] = 'https'
        else:
            self.env['wsgi.url_scheme'] = 'http'

        self.headers_set = []
        self.headers_sent = []

    def write(self, data):
        headerstr = ''
        if not self.headers_set:
            raise AssertionError("write() before start_response()")
        elif not self.headers_sent:
            # Before the first output, send the stored headers
            status, response_headers = self.headers_sent[:] = self.headers_set
            headerstr = 'HTTP/1.1 %s\r\n' % status
            for header in response_headers:
                headerstr += '%s: %s\r\n' % header
            headerstr += '\r\n'
            self.sender.send(headerstr)
        self.sender.send(data)

    def start_response(self, status, response_headers, exc_info=None):
        if exc_info:
            try:
                if self.headers_sent:
                    # Re-raise original exception if headers sent
                    raise exc_info[0], exc_info[1], exc_info[2]
            finally:
                exc_info = None     # avoid dangling circular ref
        elif self.headers_set:
            raise AssertionError("Headers already set!")

        self.headers_set[:] = [status, response_headers]
        return self.write

    def run(self):
        print 'thread waiting...'
        print 'thread: %s working...' % self.name
        #respiter = self.wsgi(self.env, self.sender)
        result = self.app(self.env, self.start_response)
        try:
            self.ev.wait(self.globalwait)
            self.ev.clear()
            self.sender.sendall('<::1111::>%s' % self.name)
            for data in result:
                if data:    # don't send headers until body appears
                    self.write(data)
                    #self.write(data, respiter.headers_set)
        finally:
            if hasattr(result, 'close'):
                result.close()
            self.ev.set()
