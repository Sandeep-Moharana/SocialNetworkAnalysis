"""Phase 2 "who is where" registry. Runs on the MASTER laptop, port 8099.

Phone hotspots give every laptop a new IP each time (Android even picks a new
subnet). Instead of typing IPs into .env on every laptop:
  - scripts/worker_up.ps1 on a friend's PC scans the hotspot for this service,
    says "I am alice at 10.67.29.112" (/register), and reads back everyone's IP;
  - scripts/cluster_up.ps1 on the master reads the same table (/hosts).

Only the Python standard library. Registrations live in memory: a new session
(or a new master IP) starts empty and every PC registers again.

  GET /hosts                         -> {"service", "master", "expected", "nodes"}
  GET /register?name=alice&ip=1.2.3.4 -> same, after recording alice
"""
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT = 8099
MASTER_IP = os.environ.get("MASTER_IP", "")                   # set by cluster_up.ps1
EXPECTED = [n for n in os.environ.get("EXPECTED", "").split(",") if n]   # friends' names from .env
NODES = {}                                                     # name -> IP, filled by /register

VALID_NAME = re.compile(r"^[a-z0-9-]{1,30}$")                  # same rule as NODE_NAME in .env
VALID_IP = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if url.path == "/register":
            name = query.get("name", [""])[0]
            ip = query.get("ip", [""])[0]
            if not (VALID_NAME.match(name) and VALID_IP.match(ip)):
                return self.reply(400, {"error": "use /register?name=<lowercase name>&ip=<a.b.c.d>"})
            if NODES.get(name) != ip:
                print(f"[registry] {name} is at {ip}", flush=True)
            NODES[name] = ip
        elif url.path != "/hosts":
            return self.reply(404, {"error": "use /hosts or /register"})
        self.reply(200, {"service": "sna-registry", "master": MASTER_IP,
                         "expected": EXPECTED, "nodes": NODES})

    def reply(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):   # keep the container log to registrations only
        pass


if __name__ == "__main__":
    print(f"[registry] master {MASTER_IP}, expecting {EXPECTED}, listening on :{PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
