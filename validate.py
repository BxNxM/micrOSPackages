#!/usr/bin/env python3
import os
import json
import sys

ROOT = os.path.abspath(os.path.dirname(__file__))


def find_all_packages(root):
    """Find subdirectories containing a package.json."""
    packages = []
    for entry in os.listdir(root):
        full = os.path.join(root, entry)
        pkg_file = os.path.join(full, "package.json")
        if os.path.isdir(full) and os.path.isfile(pkg_file):
            packages.append(full)
    return sorted(packages)


def validate_package(pkg_path):
    pkg_json = os.path.join(pkg_path, "package.json")
    pkg_name = os.path.basename(pkg_path)

    # Header
    print(f"\n📦 **{pkg_name}**")

    # Load package.json
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

    for dest, src in urls:
        src_path = os.path.join(pkg_path, src)
        exists = os.path.exists(src_path)

        if exists:
            status = "✅"
        else:
            status = "❌"
            all_ok = False

        # Compact colorful line: STATUS source → target
        print(f"  {status} {src}  ➜  {dest}")

    # Summary line
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

