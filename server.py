import http.server
import socketserver

PORT = 5000
HOST = "0.0.0.0"

Handler = http.server.SimpleHTTPRequestHandler

with socketserver.TCPServer((HOST, PORT), Handler) as httpd:
    print(f"Serving at http://{HOST}:{PORT}")
    httpd.serve_forever()
