"""
Ark Access Control HTTP Service

This module provides an HTTP service compatible with the "ARK Join Control"
mod [https://steamcommunity.com/sharedfiles/filedetails/?id=949422684]

Author:
    IceDragon <icedragon@quickfox.org>
"""

import json
from functools import partial
from typing import Tuple, Callable
from urllib.parse import parse_qsl, urlparse

from http.server import HTTPServer, BaseHTTPRequestHandler

__all__ = [
    'ArkJoinControlRequestHandler',
    'start_http_service',
]

# TEXT_CONTENT_TYPE = 'text/plain'
# HTML_CONTENT_TYPE = 'text/html'
JSON_CONTENT_TYPE = 'application/json'


class ArkJoinControlRequestHandler(BaseHTTPRequestHandler):
    @property
    def server_version(self) -> str:
        return 'GJC/1.0'

    def __init__(self, is_allowed: Callable[[str], bool], *args, **kwargs):
        self.is_allowed = is_allowed
        super().__init__(*args, **kwargs)

    # noinspection PyPep8Naming
    def do_GET(self):
        path = urlparse(self.path)
        query = dict(parse_qsl(path.query))

        if path.path != '/':
            return self.send_error(404)

        steam_id = query.get('steam_id')
        if not steam_id:
            return self.send_error(400)

        self.send_access_response(steam_id, self.is_allowed(steam_id))

    def send_preamble(self, code: int, content_type: str = JSON_CONTENT_TYPE):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.end_headers()

    def send_access_response(self, steam_id: str, allowed: bool):
        self.send_preamble(200, JSON_CONTENT_TYPE)
        response = {
            'steam_id': steam_id,
            'allowed': str(int(allowed)),
        }

        json_bytes = bytes(json.dumps(response), 'utf-8')
        self.wfile.write(json_bytes)

    def send_error(self, code: int, message: str = None, explain: str = None):
        response = {
            'type': 'error',
            'code': code,
        }

        if message:
            response['message'] = message

        if explain:
            response['extra'] = explain

        self.send_preamble(code, JSON_CONTENT_TYPE)
        json_bytes = bytes(json.dumps(response), 'utf-8')
        self.wfile.write(json_bytes)


def start_http_service(addr: Tuple[str, int], is_allowed: Callable[[str], bool]):
    server = HTTPServer(addr, partial(ArkJoinControlRequestHandler, is_allowed))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
