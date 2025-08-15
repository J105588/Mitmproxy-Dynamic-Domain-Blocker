import asyncio
from mitmproxy import http, options
from mitmproxy.tools.dump import DumpMaster
from threading import Thread
import webbrowser
import socket

# --- 設定項目 ---
TARGET_DOMAINS = ["youtube.com", "tiktok.com", "x.com", "twitter.com", "instagram.com", "google,com"]
WEB_UI_PORT = 8082
BLOCK_PAGE_FILE = "block_page.html"
# ----------------

block_status = {domain: True for domain in TARGET_DOMAINS}
try:
    with open(BLOCK_PAGE_FILE, "r", encoding="utf-8") as f:
        BLOCK_PAGE_HTML = f.read()
except FileNotFoundError:
    print(f"エラー: {BLOCK_PAGE_FILE} が見つかりません。")
    BLOCK_PAGE_HTML = "<h1>アクセスはブロックされました</h1>"

class Blocker:
    def http_connect(self, flow: http.HTTPFlow) -> None:
        if any(domain in flow.request.host for domain, blocked in block_status.items() if blocked):
            flow.response = http.Response.make(200, BLOCK_PAGE_HTML.encode('utf-8'), {"Content-Type": "text/html; charset=utf-8"})
    def request(self, flow: http.HTTPFlow) -> None:
        if not flow.request.is_ssl and any(domain in flow.request.host for domain, blocked in block_status.items() if blocked):
            flow.response = http.Response.make(200, BLOCK_PAGE_HTML.encode('utf-8'), {"Content-Type": "text/html; charset=utf-8"})

async def handle_request(reader, writer):
    try:
        request_line = await reader.readline()
        if not request_line: return
        path = request_line.decode('utf-8').split(' ')[1]
        if path.startswith("/toggle"):
            domain_to_toggle = path.split("=")[1]
            if domain_to_toggle in block_status:
                block_status[domain_to_toggle] = not block_status[domain_to_toggle]
            response = f"HTTP/1.1 302 Found\r\nLocation: /\r\n\r\n"
        else:
            body = f'<html><head><title>Filter Control</title><meta name="viewport" content="width=device-width, initial-scale=1"><style>body{{font-family:sans-serif;padding:20px;}} button{{padding:5px 10px;}}</style></head><body><h1>フィルタリング制御</h1>'
            for domain, is_blocked in block_status.items():
                status_text, button_text = ("ブロック中", "許可する") if is_blocked else ("許可", "ブロックする")
                body += f'<p>{domain}: {status_text} <a href="/toggle?domain={domain}"><button>{button_text}</button></a></p>'
            body += '</body></html>'
            response = f"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n\r\n{body}"
        writer.write(response.encode('utf-8'))
        await writer.drain()
    finally:
        writer.close()

async def run_web_server():
    server = await asyncio.start_server(handle_request, '0.0.0.0', WEB_UI_PORT)
    addr = server.sockets[0].getsockname()
    ip = get_my_ip()
    print(f"[*] 管理画面: http://{ip}:{WEB_UI_PORT}")
    webbrowser.open(f"http://127.0.0.1:{WEB_UI_PORT}")
    async with server: await server.serve_forever()

def start_web_server_in_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_web_server())

def get_my_ip():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try: s.connect(('8.8.8.8', 80)); return s.getsockname()[0]
        except Exception: return '127.0.0.1'

async def main():
    opts = options.Options(listen_host='0.0.0.0', listen_port=8080)
    master = DumpMaster(opts, with_termlog=False, with_dumper=False)
    master.addons.add(Blocker())
    print(f"[*] プロキシサーバーを起動中: {get_my_ip()}:8080")
    Thread(target=start_web_server_in_thread, daemon=True).start()
    await master.run()

if __name__ == '__main__':
    try: asyncio.run(main())
    except KeyboardInterrupt: print("\n[-] サーバーを停止します。")