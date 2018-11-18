# -*- coding: utf-8 -
# 
# liet flask
from flask import Flask, request, make_response

def cookie_respon(rspdata, cookies=None):
    rsp = make_response(rspdata)
    if cookies is None:
        return rsp
    for k,v in cookies.items():
        rsp.set_cookie(k, value=str(v))
    return rsp

app = Flask(__name__)
ctx = app.app_context()
ctx.push()

@app.route('/')
@app.route('/index')
def index():
    index_rt = "<html><head><title>???</title></head><body><h1>Hello,World</h1></body></html>"
    wid = request.cookies.get('gworkerid')
    if not wid:
        wid = request.environ.get('wsgi.gworkerid')
        if wid:
            return cookie_respon(index_rt, {'gworkerid': wid})
    return cookie_respon(index_rt)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)