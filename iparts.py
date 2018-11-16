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
    # easy and quit respon
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

def env_parseall(req_head, origin_dict=None, check_mobile=True):
    # parse http request into dict
    # if needed, check if a request from mobile
    def fline_parser(fline):
        # firstline: GET /abc.file HTTP/1.1
        blocks = re.split(r'\s+', fline)
        try:
            qstr = blocks[1].split('?')[1]
        except IndexError:
            qstr = ''
        return dict(REQUEST_METHOD=blocks[0], PATH_INFO=blocks[1], QUERY_STRING=qstr, SERVER_PROTOCOL=blocks[2])

    hdrs = re.split(r'[:|\r\n]', req_head)
    out_dict = dict()
    if origin_dict:
        out_dict.update(origin_dict)
    fline = fline_parser(hdrs.pop(0))
    # fline: 'GET|POST|... target http_version'
    x = 0
    mlen = len(hdrs) - 1
    while x <= mlen:
        if len(hdrs[x]) > 0:
            out_dict['HTTP_' + hdrs[x].upper()] = hdrs[x+1]
            x += 2
        else:
            x += 1
    if check_mobile:
        out_dict['IS_MOBILE'] = 'no'
        UA = out_dict.get('HTTP_USER-AGENT')
        if UA and ('Android' in UA or 'Phone' in UA or 'Mobile' in UA):
            out_dict['IS_MOBILE'] = 'yes'
    out_dict.update(fline)
    return out_dict

def inmsger(msg):
    msgtypes = {'SENDER'}
    if len(msg) < 32:
        hdr = msg.split(">>>")
        if len(hdr) == 2 and hdr[0] in msgtypes:
            return hdr[1]
    else:
        return None
