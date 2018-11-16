## -*- coding: utf-8 -
#
# HTTP OBJECTS:
# http req handler;
# 


def make_httpo(req_dict):
    m = req_dict['REQUEST_METHOD']
    if m == 'GET':
        return http_req_get('abc')
    elif m == 'POST':
        return http_req_get('cdf')


class http_req(object):
    pass

    # __init__ is not need


class http_req_get(http_req):

    def __new__(cls, accept2socket):
        pass
    
    def __init__(self, accept2socket):
        self.method = 'GET'
        self.socket = accept2socket
        self.respon = None
        # arbiter side socket, connecting to one of workers
        self.upsocket = None


class http_req_post(http_req):
    
    def __init__(self, accept2socket):
        self.method = 'POST'
        self.socket = accept2socket
        self.respon = None
        self.upsocket = None

    def post_file(self):
        pass