import os
import urlparse
import datetime
import threading
import mimetools
import socket
import errno
import sys
import select
import time
import json


import xlog
logging = xlog.Logger()


class HttpServerHandler():
    default_request_version = "HTTP/1.1"
    MessageClass = mimetools.Message
    rbufsize = -1
    wbufsize = 0

    def __init__(self, sock, client, args, logger=logging):
        self.connection = sock
        sock.settimeout(300)
        self.rfile = socket._fileobject(self.connection, "rb", self.rbufsize, close=True)
        self.wfile = socket._fileobject(self.connection, "wb", self.wbufsize, close=True)
        self.client_address = client
        self.args = args
        self.logger = logger
        self.setup()

    def setup(self):
        pass

    def __del__(self):
        try:
            socket.socket.close(self.connection)
        except:
            pass

    def handle(self):
        #self.logger.info('Connected from %r', self.client_address)
        while True:
            try:
                self.close_connection = 1
                self.handle_one_request()
            except Exception as e:
                #self.logger.warn("handle err:%r close", e)
                self.close_connection = 1

            if self.close_connection:
                break
        self.connection.close()
        #self.logger.debug("closed from %s:%d", self.client_address[0], self.client_address[1])

    def address_string(self):
        return '%s:%s' % self.client_address[:2]

    def parse_request(self):
        self.command = None  # set in case of error on the first line
        self.request_version = version = self.default_request_version

        requestline = self.raw_requestline
        requestline = requestline.rstrip('\r\n')
        self.requestline = requestline
        words = requestline.split()
        if len(words) == 3:
            command, path, version = words
            if version[:5] != 'HTTP/':
                self.send_error(400, "Bad request version (%r)" % version)
                return False
            try:
                base_version_number = version.split('/', 1)[1]
                version_number = base_version_number.split(".")
                # RFC 2145 section 3.1 says there can be only one "." and
                #   - major and minor numbers MUST be treated as
                #      separate integers;
                #   - HTTP/2.4 is a lower version than HTTP/2.13, which in
                #      turn is lower than HTTP/12.3;
                #   - Leading zeros MUST be ignored by recipients.
                if len(version_number) != 2:
                    raise ValueError
                version_number = int(version_number[0]), int(version_number[1])
            except (ValueError, IndexError):
                self.send_error(400, "Bad request version (%r)" % version)
                return False
            if version_number >= (1, 1):
                self.close_connection = 0
            if version_number >= (2, 0):
                self.send_error(505,
                          "Invalid HTTP Version (%s)" % base_version_number)
                return False
        elif len(words) == 2:
            command, path = words
            self.close_connection = 1
            if command != 'GET':
                self.send_error(400,
                                "Bad HTTP/0.9 request type (%r)" % command)
                return False
        elif not words:
            return False
        else:
            self.send_error(400, "Bad request syntax (%r)" % requestline)
            return False
        self.command, self.path, self.request_version = command, path, version

        # Examine the headers and look for a Connection directive
        self.headers = self.MessageClass(self.rfile, 0)

        conntype = self.headers.get('Connection', "")
        if conntype.lower() == 'close':
            self.close_connection = 1
        elif conntype.lower() == 'keep-alive':
            self.close_connection = 0
        return True

    def handle_one_request(self):
        try:
            try:
                self.raw_requestline = self.rfile.readline(65537)
            except Exception as e:
                #self.logger.warn("simple server handle except %r", e)
                return

            if len(self.raw_requestline) > 65536:
                #self.logger.warn("recv command line too large")
                return
            if not self.raw_requestline:
                #self.logger.warn("closed")
                return

            self.parse_request()
            self.close_connection = 0

            if self.command == "GET":
                self.do_GET()
            elif self.command == "POST":
                self.do_POST()
            elif self.command == "CONNECT":
                self.do_CONNECT()
            elif self.command == "HEAD":
                self.do_HEAD()
            elif self.command == "DELETE":
                self.do_DELETE()
            elif self.command == "OPTIONS":
                self.do_OPTIONS()
            elif self.command == "PUT":
                self.do_PUT()
            else:
                self.logger.warn("unhandler cmd:%s path:%s from:%s", self.command, self.path, self.address_string())
                return

            self.wfile.flush() #actually send the response if not already done.

        except socket.error as e:
            #self.logger.warn("socket error:%r", e)
            self.close_connection = 1
        except IOError as e:
            if e.errno == errno.EPIPE:
                self.logger.warn("PIPE error:%r", e)
                pass
            else:
                self.logger.warn("IOError:%r", e)
                pass
        #except OpenSSL.SSL.SysCallError as e:
        #    self.logger.warn("socket error:%r", e)
            self.close_connection = 1
        except Exception as e:
            self.logger.exception("handler:%r cmd:%s path:%s from:%s", e,  self.command, self.path, self.address_string())
            self.close_connection = 1

    def do_GET(self):
        self.logger.warn("unhandler cmd:%s from:%s", self.command, self.address_string())

    def do_POST(self):
        self.logger.warn("unhandler cmd:%s from:%s", self.command, self.address_string())

    def do_PUT(self):
        self.logger.warn("unhandler cmd:%s from:%s", self.command, self.address_string())

    def do_DELETE(self):
        self.logger.warn("unhandler cmd:%s from:%s", self.command, self.address_string())

    def do_OPTIONS(self):
        self.logger.warn("unhandler cmd:%s from:%s", self.command, self.address_string())

    def do_HEAD(self):
        self.logger.warn("unhandler cmd:%s from:%s", self.command, self.address_string())

    def do_CONNECT(self):
        self.logger.warn("unhandler cmd:%s from:%s", self.command, self.address_string())

    def send_not_found(self):
        self.wfile.write(b'HTTP/1.1 404\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\n404 Not Found')

    def send_error(self, code, message=None):
        self.wfile.write('HTTP/1.1 %d\r\n' % code)
        self.wfile.write('Connection: close\r\n\r\n')
        if message:
            self.wfile.write(message)

    def send_response(self, mimetype="", content="", headers="", status=200):
        data = []
        data.append('HTTP/1.1 %d\r\n' % status)
        if len(mimetype):
            data.append('Content-Type: %s\r\n' % mimetype)

        data.append('Content-Length: %s\r\n' % len(content))
        if len(headers):
            if isinstance(headers, dict):
                for key in headers:
                    data.append("%s: %s\r\n" % (key, headers[key]))
            elif isinstance(headers, basestring):
                data.append(headers)
        data.append("\r\n")

        if len(content) < 1024:
            data.append(content)
            data_str = "".join(data)
            self.wfile.write(data_str)
        else:
            data_str = "".join(data)
            self.wfile.write(data_str)
            if len(content):
                self.wfile.write(content)

    def send_response_nc(self, mimetype="", content="", headers="", status=200):
        no_cache_headers = "Cache-Control: no-cache, no-store, must-revalidate\r\nPragma: no-cache\r\nExpires: 0\r\n"
        return self.send_response(mimetype, content, no_cache_headers + headers, status)

    def send_file(self, filename, mimetype):
        try:
            if not os.path.isfile(filename):
                self.send_not_found()
                return

            file_size = os.path.getsize(filename)
            tme = (datetime.datetime.today()+datetime.timedelta(minutes=330)).strftime('%a, %d %b %Y %H:%M:%S GMT')
            head = 'HTTP/1.1 200\r\nAccess-Control-Allow-Origin: *\r\nCache-Control:public, max-age=31536000\r\n'
            head += 'Expires: %s\r\nContent-Type: %s\r\nContent-Length: %s\r\n\r\n' % (tme, mimetype, file_size)
            self.wfile.write(head.encode())

            with open(filename, 'rb') as fp:
                while True:
                    data = fp.read(65535)
                    if not data:
                        break
                    self.wfile.write(data)
        except:
            pass
            #self.logger.warn("download broken")

    def response_json(self, res_arr):
        data = json.dumps(res_arr, indent=0, sort_keys=True)
        self.send_response('application/json', data)


class HTTPServer():
    def __init__(self, address, handler, args=(), use_https=False, cert="", logger=logging):
        self.sockets = []
        self.running = True
        if isinstance(address, tuple):
            self.server_address = [address]
        else:
            # server can listen multi-port
            self.server_address = address
        self.handler = handler
        self.logger = logger
        self.args = args
        self.use_https = use_https
        self.cert = cert
        self.init_socket()
        #self.logger.info("server %s:%d started.", address[0], address[1])

    def start(self):
        self.http_thread = threading.Thread(target=self.serve_forever)
        self.http_thread.setDaemon(True)
        self.http_thread.start()

    def init_socket(self):
        for addr in self.server_address:
            self.add_listen(addr)

    def add_listen(self, addr):
        if ":" in addr[0]:
            sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        addr = tuple(addr)
        try:
            sock.bind(addr)
        except Exception as e:
            err_string = "bind to %s:%d fail:%r" % (addr[0], addr[1], e)
            self.logger.error(err_string)
            raise Exception(err_string)

        if self.use_https:
            import OpenSSL
            if hasattr(OpenSSL.SSL, "TLSv1_2_METHOD"):
                ssl_version = OpenSSL.SSL.TLSv1_2_METHOD
            elif hasattr(OpenSSL.SSL, "TLSv1_1_METHOD"):
                ssl_version = OpenSSL.SSL.TLSv1_1_METHOD
            elif hasattr(OpenSSL.SSL, "TLSv1_METHOD"):
                ssl_version = OpenSSL.SSL.TLSv1_METHOD

            ctx = OpenSSL.SSL.Context(ssl_version)
            # server.pem's location (containing the server private key and the server certificate).
            fpem = self.cert
            ctx.use_privatekey_file(fpem)
            ctx.use_certificate_file(fpem)
            sock = OpenSSL.SSL.Connection(ctx, sock)
        sock.listen(200)
        self.sockets.append(sock)
        self.logger.info("server %s:%d started.", addr[0], addr[1])

    def serve_forever(self):
        if hasattr(select, 'epoll'):

            fn_map = {}
            p = select.epoll()
            for sock in self.sockets:
                fn = sock.fileno()
                sock.setblocking(0)
                p.register(fn, select.EPOLLIN | select.EPOLLHUP | select.EPOLLPRI)
                fn_map[fn] = sock

            while self.running:
                events = p.poll(timeout=1)
                for fn, event in events:
                    if fn not in fn_map:
                        self.logger.error("p.poll get fn:%d", fn)
                        continue

                    sock = fn_map[fn]
                    try:
                        (sock, address) = sock.accept()
                    except IOError as e:
                        self.logger.warn("socket accept fail(errno: %s).", e.args[0])
                        if e.args[0] == 10022:
                            self.logger.info("restart socket server.")
                            self.init_socket()
                        break
                    self.process_connect(sock, address)

        else:
            while self.running:
                r, w, e = select.select(self.sockets, [], [], 1)
                for rsock in r:
                    try:
                        (sock, address) = rsock.accept()
                    except IOError as e:
                        self.logger.warn("socket accept fail(errno: %s).", e.args[0])
                        if e.args[0] == 10022:
                            self.logger.info("restart socket server.")
                            self.init_socket()
                        break
                    self.process_connect(sock, address)

    def process_connect(self, sock, address):
        #self.logger.debug("connect from %s:%d", address[0], address[1])
        client_obj = self.handler(sock, address, self.args)
        client_thread = threading.Thread(target=client_obj.handle)
        client_thread.start()

    def shutdown(self):
        self.running = False

    def server_close(self):
        for sock in self.sockets:
            sock.close()
        self.sockets = []


class TestHttpServer(HttpServerHandler):
    def __init__(self, sock, client, args):
        self.data_path = args
        HttpServerHandler.__init__(self, sock, client, args)

    def generate_random_lowercase(self, n):
        min_lc = ord(b'a')
        len_lc = 26
        ba = bytearray(os.urandom(n))
        for i, b in enumerate(ba):
            ba[i] = min_lc + b % len_lc # convert 0..255 to 97..122
        #sys.stdout.buffer.write(ba)
        return ba

    def do_GET(self):
        url_path = urlparse.urlparse(self.path).path
        req = urlparse.urlparse(self.path).query
        reqs = urlparse.parse_qs(req, keep_blank_values=True)

        logging.debug("GET %s from %s:%d", self.path, self.client_address[0], self.client_address[1])

        if url_path == "/test":
            tme = (datetime.datetime.today() + datetime.timedelta(minutes=330)).strftime('%a, %d %b %Y %H:%M:%S GMT')
            head = 'HTTP/1.1 200\r\nAccess-Control-Allow-Origin: *\r\nCache-Control:public, max-age=31536000\r\n'
            head += 'Expires: %s\r\nContent-Type: text/plain\r\nContent-Length: 4\r\n\r\nOK\r\n' % (tme)
            self.wfile.write(head.encode())

        elif url_path == '/':
            data = "OK\r\n"
            self.wfile.write('HTTP/1.1 200\r\nAccess-Control-Allow-Origin: *\r\nContent-Length: %d\r\n\r\n%s' %(len(data), data) )
        elif url_path == '/null':
            mimetype = "application/x-binary"
            if "size" in reqs:
                file_size = int(reqs['size'][0])
            else:
                file_size = 1024 * 1024 * 1024

            self.wfile.write('HTTP/1.1 200\r\nContent-Type: %s\r\nContent-Length: %s\r\n\r\n' % (mimetype, file_size))
            start = 0
            data = self.generate_random_lowercase(65535)
            while start < file_size:
                left = file_size - start
                send_batch = min(left, 65535)
                self.wfile.write(data[:send_batch])
                start += send_batch
        else:
            target = os.path.abspath(os.path.join(self.data_path, url_path[1:]))
            if os.path.isfile(target):
                self.send_file(target, "application/x-binary")
            else:
                self.wfile.write('HTTP/1.1 404\r\nContent-Length: 0\r\n\r\n' )


def main(data_path="."):
    logging.info("listen http on 8880")
    httpd = HTTPServer(('', 8880), TestHttpServer, data_path)
    httpd.start()

    while True:
        time.sleep(10)
