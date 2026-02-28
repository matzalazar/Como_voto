#!/usr/bin/env python3
"""Simple local web server for the generated site.

Usage:
    python serve.py [port]

Defaults to port 8080. The script changes into the ``docs/`` directory and
boots a :mod:`http.server` so the site can be previewed in a browser.
"""
import http.server
import socketserver
import os
import sys

port = 8080
if len(sys.argv) > 1:
    try:
        port = int(sys.argv[1])
    except ValueError:
        print("Invalid port, using 8080")

webdir = os.path.join(os.path.dirname(__file__), "docs")
if not os.path.isdir(webdir):
    print(f"docs/ directory not found at {webdir}")
    sys.exit(1)

os.chdir(webdir)
handler = http.server.SimpleHTTPRequestHandler

with socketserver.TCPServer(("", port), handler) as httpd:
    print(f"Serving {webdir} at http://localhost:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")
