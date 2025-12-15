#!/usr/bin/env python3
import http.server
import socketserver
import os
import socket
import sys
import json
from typing import List

try:
    from .validate import find_all_packages
except ImportError as e:
    print(f"Import error in serve_packages.py: {e}")
    from validate import find_all_packages  # type: ignore

TOOLS_DIR = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT = os.path.dirname(TOOLS_DIR)
DEFAULT_PORT = 8000


def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def map_github_to_local(source: str, base_url: str, package_name: str) -> str:
    """
    github:BxNxM/micrOSPackages/blinky_example/package/LM_blinky.py
    -> http://<ip>:<port>/blinky_example/package/LM_blinky.py
    """
    # Drop "github:"
    path = source[len("github:"):]  # "BxNxM/micrOSPackages/blinky_example/package/LM_blinky.py"
    parts = path.split("/")

    try:
        idx = parts.index(package_name)
        # Everything AFTER the package_name: ["package", "LM_blinky.py"]
        suffix_parts = parts[idx + 1 :]
    except ValueError:
        # Fallback: last 2 components if package_name not found
        suffix_parts = parts[-2:]

    suffix = "/".join(suffix_parts)  # "package/LM_blinky.py"
    return f"{base_url}/{package_name}/{suffix}"


def patch_package_json(raw_bytes: bytes, base_url: str, package_name: str) -> bytes:
    """
    Patch urls from:
        ["LM_blinky.py", "github:BxNxM/micrOSPackages/blinky_example/package/LM_blinky.py"]
    to:
        ["LM_blinky.py", "http://ip:port/blinky_example/package/LM_blinky.py"]
    """
    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except Exception as e:
        print(f"[WARN] JSON decode failed for {package_name}: {e}")
        return raw_bytes

    urls = data.get("urls")
    if isinstance(urls, list):
        patched = []
        for entry in urls:
            if not (isinstance(entry, list) and len(entry) == 2):
                patched.append(entry)
                continue

            target, source = entry

            if isinstance(source, str) and source.startswith("github:"):
                new_source = map_github_to_local(source, base_url, package_name)
            else:
                new_source = source

            patched.append([target, new_source])

        data["urls"] = patched

    try:
        return json.dumps(data).encode("utf-8")
    except Exception as e:
        print(f"[WARN] JSON encode failed for {package_name}: {e}")
        return raw_bytes


class PackageRequestHandler(http.server.SimpleHTTPRequestHandler):
    base_url: str = ""

    def do_GET(self):
        # Intercept /<pkg>/package.json
        if self.path.endswith("package.json"):
            parts = self.path.strip("/").split("/")
            package_name = parts[-2] if len(parts) >= 2 else ""
            fs_path = self.translate_path(self.path)

            if os.path.isfile(fs_path):
                try:
                    with open(fs_path, "rb") as f:
                        raw = f.read()

                    patched = patch_package_json(raw, self.base_url, package_name)

                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(patched)))
                    self.end_headers()
                    self.wfile.write(patched)
                    return
                except Exception as e:
                    print(f"[ERROR] Failed to serve patched package.json for {self.path}: {e}")
                    # fall through to default handler

        # Everything else → normal static file handling
        super().do_GET()


def print_instructions(ip: str, port: int, packages: List[str]) -> None:
    print("📦 Available mip packages in repo root:\n")
    if not packages:
        print("  ⚠️ No subfolders with package.json found.")
        return

    for package_path in packages:
        name = os.path.basename(package_path)
        url = f"http://{ip}:{port}/{name}/"
        print(f"  • {name}")
        print(f"    🧪 Test with curl:     curl {url}package.json | jq .")
        print(f"    👉 On device (repl):   import mip; mip.install('{url}')")
        print(f"    👉 On device (shell):  pacman install '{url}'")
    print("")


def main(port: int = DEFAULT_PORT) -> None:
    os.chdir(REPO_ROOT)

    ip = get_local_ip()
    base_url = f"http://{ip}:{port}"
    packages = find_all_packages(REPO_ROOT)

    handler_class = PackageRequestHandler
    handler_class.base_url = base_url

    print(f"🚀 Serving repo root: {REPO_ROOT}")
    print(f"🌐 HTTP server: http://0.0.0.0:{port}/")
    print(f"📡 Detected local IP: {base_url}/\n")
    print_instructions(ip, port, packages)
    print("🛠️ Press Ctrl+C to stop.\n")

    with socketserver.TCPServer(("", port), handler_class) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 Stopping server.")
            httpd.server_close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            main(int(sys.argv[1]))
        except ValueError:
            main()
    else:
        main()
