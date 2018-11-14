## -*- coding: utf-8 -
#
# HTTP OBJECTS:
# http req handler;
# 

class http_req(object):

    def __new__(cls, req_dict):
        # return get/post/some
        pass

    # __init__ is not need


class http_req_get(http_req):
    
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