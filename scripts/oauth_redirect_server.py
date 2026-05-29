#!/usr/bin/env python3
"""Tiny redirect server: Spotify OAuth callback on port 8888 → FastAPI on 8000."""

import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

FASTAPI_CALLBACK = "http://localhost:8000/api/spotify/auth/callback"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = "?" + urllib.parse.urlparse(self.path).query if "?" in self.path else ""
        self.send_response(302)
        self.send_header("Location", FASTAPI_CALLBACK + qs)
        self.end_headers()

    def log_message(self, format, *args):
        print(f"[oauth-redirect] {args[0]}")


if __name__ == "__main__":
    srv = HTTPServer(("localhost", 8888), Handler)
    print("[oauth-redirect] Listening on http://localhost:8888 →", FASTAPI_CALLBACK)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
