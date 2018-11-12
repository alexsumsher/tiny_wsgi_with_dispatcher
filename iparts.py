# -*- coding: utf-8 -

import re
from datetime import datetime as dt


# sample: GET /sample_page.html HTTP/1.1\r\nHost: www.example.org\r\nCookie: yummy_cookie=choco; tasty_cookie=strawberry
def cookey(ckstr, key):
    rec = r'%s=(\w+)' % key
    rert = re.findall(rec, ckstr)
    if rert:
        return rert[0]
    return None

def cookeies(ckstr):
    rec1 = r'.*Cookie:(.*)[$|\\r]'
    rec2 = r'[;|=]'
    rert = re.findall(rec1, ckstr)
    if rert:
        rert = re.split(rec2, rert)
        out = dict()
        for x in xrange(len(rert)/2):
            out[rert[x*2].strip()] = rert[x*2+1]
        return out

def make_respon(text, cookies=None):
    holder = """HTTP/1.1  200  OK\r\nServer: Apache-Coyote/1.1 \r\nDate: %s\r\nContent-Length: %s\r\n"""
    if isinstance(cookies, dict):
        ckstr = ';'.join(["%s=%s" % (x[0], x[1]) for x in cookies.items()])
        holder += 'Set-Cookie: ' + ckstr + '\r\n\r\n%s\r\n'
    else:
        holder += '\r\n%s\r\n'
    dtx = dt.now().isoformat()
    text = text.decode('gbk')
    lenx = len(text)
    return holder % (dtx, lenx, text)

def make_respon2(text, cookies=None):
    # return header, content
    holder = """HTTP/1.1  200  OK\r\nServer: Apache-Coyote/1.1 \r\nDate: %s\r\nContent-Length: %s\r\n"""
    if isinstance(cookies, dict):
        ckstr = ';'.join(["%s=%s" % (x[0], x[1]) for x in cookies.items()])
        holder += 'Set-Cookie: ' + ckstr + '\r\n\r\n'
    else:
        holder += '\r\n'
    dtx = dt.now().isoformat()
    text = text.decode('gbk')
    lenx = len(text)
    return holder % (dtx, lenx), text


def env_parser(req_head, origin_dict=None, check_mobile=True):
    #parse http request header to dict
    # special checker:
    # ismobile
    spliter = r'[\s+|\r\n]'
    headers = re.split(spliter, req_head)
    origin_dict = origin_dict or dict()
    origin_dict['REQUEST_METHOD'] = headers[0]
    origin_dict['PATH_INFO'] = headers[1]
    origin_dict['SCRIPT_NAME '] = ''
    origin_dict['HTTP_HOST'] = headers[5]
    if check_mobile:
        origin_dict['IS_MOBILE'] = 'no'
        ix = headers.index('User-Agent')
        if ix > 0 and ('Android' in headers[ix+1] or 'AppleWebKit' in headers[ix+1]):
            origin_dict['IS_MOBILE'] = 'yes'
    return origin_dict

