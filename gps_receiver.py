"""独立、仅监听本机的设备上报服务；公网 HTTPS 由反向隧道提供。"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from gps_store import accept_position


class ReceiverHandler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, *args):
        pass  # 不记录凭证、坐标或手机号

    def _send(self, code, body, content_type="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Permissions-Policy", "geolocation=(self)")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in ("/", "/mobile"):
            self._send(200, Path(__file__).with_name("mobile_gps.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/health":
            self._send(200, {"status": "ok"})
        else:
            self._send(404, {"error": "接口不存在"})

    def do_POST(self):
        if urlsplit(self.path).path != "/api/location":
            self._send(404, {"error": "接口不存在"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4096:
                self._send(413, {"error": "请求体过大或为空"})
                return
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                raise PermissionError("缺少设备凭证")
            payload = json.loads(self.rfile.read(length))
            updated = accept_position(auth[7:], payload)
            self._send(200, {"ok": True, "updated": updated})
        except PermissionError as exc:
            self._send(401, {"error": str(exc)})
        except (ValueError, UnicodeError) as exc:
            self._send(400, {"error": str(exc)})
        except Exception:
            self._send(503, {"error": "位置存储暂不可用，请稍后重试"})


class LocationReceiver:
    def __init__(self, port=0):
        self.server = ThreadingHTTPServer(("127.0.0.1", port), ReceiverHandler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_port}"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


if __name__ == "__main__":
    import argparse
    from database.init_db import init_database
    parser = argparse.ArgumentParser(description="真实 GPS 接收服务")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    init_database()
    receiver = LocationReceiver(args.port)
    print(f"接收端：{receiver.url}；异地接入须通过 HTTPS 反向代理或隧道。")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        receiver.stop()
