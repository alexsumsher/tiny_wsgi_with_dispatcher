# -*- coding: utf-8 -

import os, sys


class run_with_cgi(object):

    def __init__(self, environ, sender):
        self.environ = environ
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