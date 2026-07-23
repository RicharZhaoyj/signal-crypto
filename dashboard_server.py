#!/usr/bin/env python3
import http.server
import json
import os
import socket
import sys
import traceback
import urllib.parse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ga4_data import get_all_sites_data, format_duration

PORT = int(os.environ.get('DASHBOARD_PORT', 8090))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)


def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line)
    try:
        log_file = os.path.join(LOG_DIR, 'dashboard_' + datetime.now().strftime('%Y%m%d') + '.log')
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port))
            return False
        except OSError:
            return True


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_GET(self):
        try:
            parsed = urllib.parse.urlparse(self.path)

            if parsed.path == '/api/traffic':
                self._handle_traffic_api()
            elif parsed.path == '/api/health':
                self._handle_health_api()
            elif parsed.path == '/' or parsed.path == '/dashboard' or parsed.path == '/dashboard.html':
                self.path = '/sites/ai-link-cn/dashboard.html'
                super().do_GET()
            else:
                super().do_GET()
        except Exception as e:
            log(f'ERROR in do_GET: {e}\n{traceback.format_exc()}')
            try:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(f'Server Error: {e}'.encode('utf-8'))
            except Exception:
                pass

    def _handle_traffic_api(self):
        try:
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            days = int(query.get('days', ['7'])[0])
            days = max(1, min(30, days))

            data = get_all_sites_data(days=days)

            for site_id, site_data in data['sites'].items():
                site_data['summary']['avg_duration_formatted'] = format_duration(
                    site_data['summary']['avg_duration']
                )
                for day in site_data['daily']:
                    day['avg_duration_formatted'] = format_duration(day['avg_duration'])

            response = json.dumps(data, ensure_ascii=False, indent=2)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(response.encode('utf-8'))
        except Exception as e:
            log(f'ERROR in traffic API: {e}\n{traceback.format_exc()}')
            error = {'error': str(e)}
            self.send_response(500)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(error, ensure_ascii=False).encode('utf-8'))

    def _handle_health_api(self):
        response = {
            'status': 'ok',
            'time': datetime.now().isoformat(),
            'version': '1.1.0',
            'uptime': getattr(self.server, 'start_time', None) and (
                datetime.now() - self.server.start_time
            ).total_seconds(),
        }
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))

    def log_message(self, format, *args):
        if '/api/' in args[0]:
            log(args[0])

    def handle_error(self, request, client_address):
        log(f'ERROR from {client_address}: {traceback.format_exc()}')


def main():
    if is_port_in_use(PORT):
        log(f'端口 {PORT} 已被占用，请检查是否已有服务器在运行')
        log(f'尝试使用现有服务器: http://localhost:{PORT}/dashboard.html')
        sys.exit(1)

    server = http.server.HTTPServer(('0.0.0.0', PORT), DashboardHandler)
    server.start_time = datetime.now()

    log('=' * 50)
    log(f' Dashboard server started on port {PORT}')
    log(f' Dashboard: http://localhost:{PORT}/dashboard.html')
    log(f' API:       http://localhost:{PORT}/api/traffic')
    log(f' Health:    http://localhost:{PORT}/api/health')
    log(f' Logs:      {LOG_DIR}')
    log('=' * 50)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log('Server stopped by user (Ctrl+C)')
        server.server_close()
    except Exception as e:
        log(f'FATAL: {e}\n{traceback.format_exc()}')
        server.server_close()
        sys.exit(1)


if __name__ == '__main__':
    main()
