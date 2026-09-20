from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import json
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / 'json_extractor' / 'index.html'


def escape_json_path_key(key):
    if isinstance(key, int):
        return f'[{key}]'
    if isinstance(key, str) and key.isidentifier():
        return f'.{key}'
    escaped = str(key).replace('\\', '\\\\').replace("'", "\\'")
    return f"['{escaped}']"


def build_json_tree(value, path='$', label='root'):
    node_type = type(value).__name__
    if isinstance(value, dict):
        children = [
            build_json_tree(child_value, f"{path}{escape_json_path_key(child_key)}", str(child_key))
            for child_key, child_value in value.items()
        ]
        return {
            'label': label,
            'path': path,
            'type': 'object',
            'value': value,
            'children': children,
            'preview': f'Object({len(value)})'
        }
    if isinstance(value, list):
        children = [
            build_json_tree(child_value, f'{path}[{index}]', f'[{index}]')
            for index, child_value in enumerate(value)
        ]
        return {
            'label': label,
            'path': path,
            'type': 'array',
            'value': value,
            'children': children,
            'preview': f'Array({len(value)})'
        }
    return {
        'label': label,
        'path': path,
        'type': node_type,
        'value': value,
        'children': [],
        'preview': repr(value)
    }


class JsonExtractorHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self):
        body = INDEX_FILE.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ('/', '/index.html'):
            self._send_html()
            return
        self.send_error(404, 'Not Found')

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != '/api/extract':
            self._send_json({'error': '接口不存在'}, status=404)
            return

        content_length = int(self.headers.get('Content-Length', '0'))
        raw_body = self.rfile.read(content_length)
        try:
            request_json = json.loads(raw_body.decode('utf-8'))
        except json.JSONDecodeError as exc:
            self._send_json({'error': f'请求体不是合法 JSON: {exc}'}, status=400)
            return

        response_text = request_json.get('response', '')
        if not isinstance(response_text, str) or not response_text.strip():
            self._send_json({'error': 'response 字段不能为空'}, status=400)
            return

        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as exc:
            self._send_json({'error': f'接口响应不是合法 JSON: {exc}'}, status=400)
            return

        tree = build_json_tree(data)
        self._send_json({'tree': tree})


def run():
    server = ThreadingHTTPServer(('127.0.0.1', 8899), JsonExtractorHandler)
    print('JSON 提取器已启动: http://127.0.0.1:8899')
    server.serve_forever()


if __name__ == '__main__':
    run()
