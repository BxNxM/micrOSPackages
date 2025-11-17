#!/usr/bin/env python3
import http.server
import socketserver
import os
import socket
try:
    from .validate import find_all_packages
except ImportError as e:
    print(f"Import error: {e}")
    from validate import find_all_packages

ROOT = os.path.abspath(os.path.dirname(__file__))
DEFAULT_PORT = 8000


def get_local_ip():
    """Best-effort LAN IP detection for nice URLs."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't actually send data, just used to pick an interface
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def print_instructions(ip, port):
    packages = find_all_packages(ROOT)

    print("📦 Available mip packages in repo root:\n")
    if not packages:
        print("  ⚠️ No subfolders with package.json found.")
        return

    for name in packages:
        url = f"http://{ip}:{port}/{name}"
        print(f"  • {name}")
        print(f"    👉 On device:  import mip; mip.install('{url}')")
    print("")


def main():
    os.chdir(ROOT)
    port = DEFAULT_PORT
    ip = get_local_ip()

    handler = http.server.SimpleHTTPRequestHandler

    print(f"🚀 Serving repo root: {ROOT}")
    print(f"🌐 HTTP server: http://0.0.0.0:{port}/")
    print(f"📡 Detected local IP: http://{ip}:{port}/\n")

    print_instructions(ip, port)

    print("🛠️ Press Ctrl+C to stop.\n")

    with socketserver.TCPServer(("", port), handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 Stopping server.")
            httpd.server_close()


if __name__ == "__main__":
    main()

