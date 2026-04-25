#!/usr/bin/env python3
"""Small ingress endpoint that redirects the add-on sidebar entry to the dashboard."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


OPTIONS_PATH = Path("/data/options.json")
DEFAULT_DASHBOARD_PATH = "/lovelace/vacuum-automation"


def dashboard_target() -> str:
    try:
        options = json.loads(OPTIONS_PATH.read_text())
    except Exception:
        return DEFAULT_DASHBOARD_PATH

    target = str(options.get("dashboard_path") or DEFAULT_DASHBOARD_PATH).strip()
    if not target:
        return DEFAULT_DASHBOARD_PATH
    return target


class RedirectHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        target = dashboard_target()
        self.send_response(302)
        self.send_header("Location", target)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(
            (
                "<html><head>"
                f'<meta http-equiv="refresh" content="0; url={target}">'
                "</head><body>"
                f'<a href="{target}">Open dashboard</a>'
                "</body></html>"
            ).encode("utf-8")
        )

    def log_message(self, format, *args):
        return


def main():
    port = int(os.environ.get("SIDEBAR_REDIRECT_PORT", "8099"))
    server = HTTPServer(("0.0.0.0", port), RedirectHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
