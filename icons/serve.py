#!/usr/bin/env python3
"""Serve report.html locally and save icon picks to prefer-new.txt.

A page opened from file:// cannot write to disk, so this tiny server
accepts the page's POST and writes the file build.py reads.

Usage:
    python3 serve.py   then open the printed URL
"""

import functools
import http.server
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PORT = 8765
NAME = re.compile(r'[\w.+@-]+')


class Handler(http.server.SimpleHTTPRequestHandler):
    """Static files from the project root, plus one writable file."""

    def do_POST(self) -> None:  # noqa: N802 - name fixed by http.server
        """Replace prefer-new.txt with the posted list of icon names."""
        if self.path != '/prefer-new.txt':
            self.send_error(404)
            return
        body = self.rfile.read(int(self.headers.get('Content-Length', 0))).decode()
        names = body.split()
        # only plain icon names, so the page cannot write anything else
        if not all(NAME.fullmatch(n) for n in names):
            self.send_error(400)
            return
        (HERE / 'prefer-new.txt').write_text(''.join(f'{n}\n' for n in sorted(set(names))))
        self.send_response(204)
        self.end_headers()


def main() -> None:
    handler = functools.partial(Handler, directory=str(HERE))
    try:
        server = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), handler)
    except OSError as e:
        # usually an older serve.py still running in another terminal
        raise SystemExit(f'port {PORT} is busy ({e}); find it with: lsof -i :{PORT}')
    print(f'http://127.0.0.1:{PORT}/report.html')
    server.serve_forever()


if __name__ == '__main__':
    main()
