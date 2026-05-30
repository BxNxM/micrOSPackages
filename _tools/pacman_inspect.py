#!/usr/bin/env python3
import json
from pathlib import Path

try:
    from . import validate
    from .package_rules import lib_content_for_urls
except ImportError:
    import validate
    from package_rules import lib_content_for_urls


def _relative_path(path: Path) -> str:
    return path.relative_to(Path(validate.ROOT).parent).as_posix()


def _print_list(title: str, items: list):
    print(f"{title}:")
    if not isinstance(items, list):
        print(f"  {items}")
        return
    if not items:
        print("  (empty)")
        return
    for item in items:
        print(f"  - {item}")


def _print_layout(layout: dict, lib_content: list[str]):
    print("layout:")
    if not isinstance(layout, dict):
        print(f"  {layout}")
        return
    device_layout = dict(layout)
    device_layout["/lib"] = lib_content
    for target, sources in device_layout.items():
        print(f"  {target}:")
        if not isinstance(sources, list):
            print(f"    {sources}")
            continue
        if not sources:
            print("    (empty)")
            continue
        for source in sources:
            print(f"    - {source}")


def _read_json(path: Path, label: str):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Cannot read {label}: {e}")
        return None


def _select_package() -> str | None:
    packages = validate.resolve_packages()
    if not packages:
        print("❌ No packages found")
        return None

    print("Available packages:")
    for index, package in enumerate(packages, start=1):
        print(f"  {index}. {Path(package).name}")

    try:
        selected = input("Select package index: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n❌ Package selection cancelled")
        return None

    try:
        index = int(selected)
    except ValueError:
        print(f"❌ Invalid package index: {selected}")
        return None

    if not 1 <= index <= len(packages):
        print(f"❌ Package index out of range: {index}")
        return None

    return Path(packages[index - 1]).name


def inspect_package(package_name: str | None = None) -> bool:
    if package_name is None:
        package_name = _select_package()
        if package_name is None:
            return False

    packages = validate.resolve_packages(package_name)
    if not packages:
        print(f"❌ Package not found: {package_name}")
        return False

    package_path = Path(packages[0])
    pacman_json = package_path / "package" / "pacman.json"
    package_json = package_path / "package.json"
    if not pacman_json.is_file():
        print(f"❌ pacman.json not found: {_relative_path(pacman_json)}")
        return False
    if not package_json.is_file():
        print(f"❌ package.json not found: {_relative_path(package_json)}")
        return False

    data = _read_json(pacman_json, _relative_path(pacman_json))
    package_data = _read_json(package_json, _relative_path(package_json))
    if data is None or package_data is None:
        return False

    if not isinstance(data, dict) or not isinstance(package_data, dict):
        print("❌ Manifest root must be a JSON object")
        return False

    versions = data.get("versions", {})
    if not isinstance(versions, dict):
        versions = {}
    print(f"📦 {package_path.name}")
    print("metadata:")
    print(f"  - pacman.json: {_relative_path(pacman_json)}")
    print(f"  - package.json: {_relative_path(package_json)}")
    print(f"url: {data.get('url', '')}")
    print("versions:")
    print(f"  package: {versions.get('package', '')}")
    print(f"  packager: {versions.get('packager', '')}")
    _print_list("deps", data.get("deps", []))
    _print_layout(data.get("layout", {}), lib_content_for_urls(package_path.name, package_data.get("urls", [])))
    return True
