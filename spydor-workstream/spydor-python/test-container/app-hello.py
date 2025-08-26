from http.server import HTTPServer, BaseHTTPRequestHandler

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<html><body><h1>Hello World!</h1><p>Python web app from scratch container</p></body></html>')

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 8080), Handler)
    print('Server starting on port 8080...')
    server.serve_forever()