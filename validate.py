#!/usr/bin/env python3
import os
import json
import sys

ROOT = os.path.abspath(os.path.dirname(__file__))

# Adjust if you rename GitHub user or repo
GITHUB_BASE = "github:BxNxM/micrOSPackages/"


def find_all_packages(root):
    """Find subdirectories containing a package.json."""
    packages = []
    for entry in os.listdir(root):
        full = os.path.join(root, entry)
        pkg_file = os.path.join(full, "package.json")
        if os.path.isdir(full) and os.path.isfile(pkg_file):
            packages.append(full)
    return sorted(packages)


def is_http_remote(src: str) -> bool:
    if not isinstance(src, str):
        return False
    return src.startswith("http://") or src.startswith("https://")


def resolve_repo_local_github_path(src: str, pkg_name: str, pkg_path: str):
    """
    Try to resolve a github:BxNxM/micrOSPackages/... path to a local file.

    Examples:
      src = github:BxNxM/micrOSPackages/micros-app-template/template_app/__init__.py

    We try:
      1) ROOT / (rest after GITHUB_BASE)
         -> ROOT/micros-app-template/template_app/__init__.py
      2) If that doesn't exist and first path segment == pkg_name:
         pkg_path / (rest after '<pkg_name>/')
         -> <pkg_path>/template_app/__init__.py
    """
    if not isinstance(src, str) or not src.startswith(GITHUB_BASE):
        return None

    rel = src[len(GITHUB_BASE):]  # micros-app-template/template_app/__init__.py
    # First attempt: relative to repo root
    candidate_root = os.path.join(ROOT, rel)
    if os.path.exists(candidate_root):
        return candidate_root

    # Second attempt: strip leading "<pkg_name>/" and resolve inside pkg_path
    parts = rel.split("/", 1)
    if len(parts) == 2 and parts[0] == pkg_name:
        candidate_pkg = os.path.join(pkg_path, parts[1])
        if os.path.exists(candidate_pkg):
            return candidate_pkg

    # If neither exists, still return the ROOT-based candidate for debug
    return candidate_root


def validate_dest_path(dest: str) -> bool:
    """Basic sanity check for destination path (no '..')."""
    if not isinstance(dest, str):
        return False
    if ".." in dest.split("/"):
        return False
    return True


def validate_package(pkg_path):
    pkg_json = os.path.join(pkg_path, "package.json")
    pkg_name = os.path.basename(pkg_path)

    print(f"\n📦 {pkg_name}")

    try:
        with open(pkg_json, "r") as f:
            data = json.load(f)
    except Exception as e:
        print(f"  ❌ Error reading package.json: {e}")
        return False

    urls = data.get("urls")
    if not isinstance(urls, list):
        print("  ❌ 'urls' missing or invalid")
        return False

    all_ok = True

    for entry in urls:
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            print(f"  ❌ Invalid urls entry (expected [dest, src]): {entry}")
            all_ok = False
            continue

        dest, src = entry

        if not validate_dest_path(dest):
            print(f"  ❌ {src}  ➜  {dest}   (invalid dest path: contains '..')")
            all_ok = False
            continue

        # 1) Our own repo's github: paths
        repo_local_path = resolve_repo_local_github_path(src, pkg_name, pkg_path)
        if isinstance(src, str) and src.startswith(GITHUB_BASE):
            exists = os.path.exists(repo_local_path)
            status = "✅" if exists else "❌"
            if not exists:
                all_ok = False
            rel_local = os.path.relpath(repo_local_path, ROOT)
            print(f"  {status} {src}  ➜  {dest}   (local: {rel_local})")
            continue

        # 2) Plain local paths (relative to package folder)
        if not is_http_remote(src) and not (isinstance(src, str) and src.startswith("github:")):
            src_path = os.path.join(pkg_path, src)
            exists = os.path.exists(src_path)
            status = "✅" if exists else "❌"
            if not exists:
                all_ok = False
            print(f"  {status} {src}  ➜  {dest}")
            continue

        # 3) Other remotes: different GitHub repo or http(s)
        print(f"  🌐 {src}  ➜  {dest}   (remote, not checked)")

    if all_ok:
        print("  ✔️ VALID\n")
    else:
        print("  ✖️ INVALID\n")

    return all_ok


def main():
    packages = find_all_packages(ROOT)

    if not packages:
        print("⚠️ No packages found (no subfolders containing package.json).")
        return 1

    print(f"🔍 Found {len(packages)} package(s).")

    all_ok = True
    for pkg in packages:
        if not validate_package(pkg):
            all_ok = False

    if all_ok:
        print("🎉 All packages valid!")
        return 0
    else:
        print("❗ Some packages failed validation.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
