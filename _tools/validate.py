#!/usr/bin/env python3
import os
import json
import sys
from pathlib import Path

ROOT = os.path.abspath(os.path.dirname(__file__))
TEMPLATE_PACMAN_JSON = Path(ROOT) / "app_template" / "package" / "pacman.json"

try:
    from .create_package import GITHUB_BASE
    from .package_rules import layout_entry_target_path, layout_source_allowed, layout_target_allowed, package_dest, package_files, pacman_layout_for_urls
except ImportError:
    from create_package import GITHUB_BASE
    from package_rules import layout_entry_target_path, layout_source_allowed, layout_target_allowed, package_dest, package_files, pacman_layout_for_urls

VERBOSE = True

def verbose_print(text):
    if VERBOSE:
        print(text)


def _check_package_json(path):
    """Check if a package"""
    pkg_file = os.path.join(path, "package.json")
    if os.path.isfile(pkg_file):
        return True
    return False


def find_all_packages(source_path):
    """Find subdirectories containing a package.json."""
    packages = []

    current_dir_name = os.path.basename(ROOT)

    # List directories in the parent dir, excluding the current dir
    root_folders = [
        f for f in os.listdir(source_path)
        if f != current_dir_name and os.path.isdir(os.path.join(source_path, f))
    ]

    for entry in root_folders:
        full = os.path.join(source_path, entry)  # use parent, not root
        if _check_package_json(full):
            packages.append(full)

    return sorted(packages)


def resolve_packages(pack_name: str = None):
    """Resolve one package or all packages to absolute package directories."""
    source_path = os.path.dirname(ROOT)
    if pack_name is None:
        return find_all_packages(source_path)

    package = os.path.join(source_path, pack_name)
    if _check_package_json(package):
        return [package]
    return []
def is_http_remote(src: str) -> bool:
    if not isinstance(src, str):
        return False
    return src.startswith("http://") or src.startswith("https://")


def resolve_repo_local_github_path(src: str, pkg_name: str, pkg_path: str):
    """
    Try to resolve a github:BxNxM/micrOSPackages/... path to a local file.

    Examples:
      src = github:BxNxM/micrOSPackages/blinky_example/package/__init__.py

    We try:
      1) ROOT / (rest after GITHUB_BASE)
         -> ROOT/blinky_example/package/__init__.py
      2) If that doesn't exist and first path segment == pkg_name:
         pkg_path / (rest after '<pkg_name>/')
         -> <pkg_path>/package/__init__.py
    """
    if not isinstance(src, str) or not src.startswith(GITHUB_BASE):
        return None

    rel = src[len(GITHUB_BASE)+1:]  # blinky_example/package/__init__.py
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


def device_lib_target(dest: str) -> str:
    """Return the package install target as it appears under /lib."""
    return f"/lib/{dest.lstrip('/')}"


def relative_local_path(path: str) -> str:
    """Return a readable path relative to the packages repo root."""
    repo_root = os.path.dirname(ROOT)
    return os.path.relpath(path, repo_root)


def verbose_print_url_row(status: str, package_ref: str, local_path: str, device_target: str, note: str = ""):
    suffix = f"  ({note})" if note else ""
    verbose_print(f"  {status} {package_ref} | {local_path} | {device_target}{suffix}")


def expected_package_urls(pkg_path: Path) -> list[list[str]]:
    pkg_name = pkg_path.name
    pkg_content_path = pkg_path / "package"
    urls = []
    for file_path in package_files(pkg_content_path):
        rel = file_path.relative_to(pkg_content_path).as_posix()
        src = f"{GITHUB_BASE}/{pkg_name}/package/{rel}"
        urls.append([package_dest(pkg_name, rel), src])
    return urls


def load_template_pacman_json() -> dict:
    with open(TEMPLATE_PACMAN_JSON, "r") as f:
        return json.load(f)


def expected_pacman_layout(pkg_name: str, urls: list[list[str]]) -> dict:
    template_data = load_template_pacman_json()
    return pacman_layout_for_urls(pkg_name, urls, template_data.get("layout", {}))


def validate_package_json(pkg_path):
    """
    Validate package.json and file references
    """
    pkg_json = os.path.join(pkg_path, "package.json")
    pkg_name = os.path.basename(pkg_path)

    print(f"{'\n' if VERBOSE else ''}📦 {pkg_name}")

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

    package_lm_exists = False
    package_pacman_json_exists = False
    verbose_print("  package reference | local relative path | target on device")
    for entry in urls:
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            print(f"  ❌ Invalid urls entry (expected [dest, src]): {entry}")
            all_ok = False
            continue

        dest, src = entry
        device_target = device_lib_target(dest) if isinstance(dest, str) else "n/a"
        # Optional resource check
        if isinstance(dest, str) and dest.endswith("pacman.json"):
            package_pacman_json_exists = True
        if isinstance(dest, str) and dest.split("/")[-1].startswith("LM_"):
            package_lm_exists = True

        if not validate_dest_path(dest):
            verbose_print_url_row("❌", str(src), "n/a", device_target, "invalid dest path: contains '..'")
            all_ok = False
            continue

        # 1) Our own repo's github: paths
        repo_local_path = resolve_repo_local_github_path(src, pkg_name, pkg_path)
        if isinstance(src, str) and src.startswith(GITHUB_BASE):
            exists = os.path.exists(repo_local_path)
            status = "✅" if exists else "❌"
            if not exists:
                all_ok = False
            rel_local = relative_local_path(repo_local_path)
            verbose_print_url_row(status, src, rel_local, device_target)
            continue

        # 2) Plain local paths (relative to package folder)
        if not is_http_remote(src) and not (isinstance(src, str) and src.startswith("github:")):
            src_path = os.path.join(pkg_path, src)
            exists = os.path.exists(src_path)
            status = "✅" if exists else "❌"
            if not exists:
                all_ok = False
            rel_local = relative_local_path(src_path)
            verbose_print_url_row(status, src, rel_local, device_target)
            continue

        # 3) Other remotes: different GitHub repo or http(s)
        verbose_print_url_row("🌐", src, "remote, not checked", device_target)

    verbose_print(f"{'✅ Load Module exists' if package_lm_exists else '⚠️ Load Module missing'}")
    verbose_print(f"{'✅ Packaging metadata exists (pacman.json)' if package_pacman_json_exists else '⚠️  Packaging metadata missing (pacman.json)'}")
    return all_ok


def validate_package(pkg_path):
    """
    Validate /package folder content against package.json and pacman.json.
    """
    if not isinstance(pkg_path, Path):
        pkg_path = Path(pkg_path)

    pkg_json = pkg_path / "package.json"
    pacman_json = pkg_path / "package" / "pacman.json"
    pkg_name = pkg_path.name

    try:
        with open(pkg_json, 'r') as f:
            package_data = json.load(f)
    except Exception as e:
        print(f"❌ Cannot load {str(pkg_json)}: {e}")
        return False

    expected_urls = expected_package_urls(pkg_path)
    actual_urls = package_data.get("urls", [])
    all_ok = True
    if actual_urls != expected_urls:
        print(f"❌ package.json urls mismatch in {pkg_name}")
        verbose_print(f"  expected: {expected_urls}")
        verbose_print(f"  actual:   {actual_urls}")
        all_ok = False

    try:
        with open(pacman_json, 'r') as f:
            pacman_data = json.load(f)
    except Exception as e:
        print(f"❌ Cannot load {str(pacman_json)}: {e}")
        return False

    layout = pacman_data.get("layout")
    if not isinstance(layout, dict):
        print(f"❌ pacman.json layout missing or invalid in {pkg_name}")
        return False

    template_data = load_template_pacman_json()
    missing_keys = sorted(set(template_data) - set(pacman_data))
    if missing_keys:
        print(f"❌ pacman.json missing top-level key(s) in {pkg_name}: {missing_keys}")
        all_ok = False

    expected_layout = expected_pacman_layout(pkg_name, expected_urls)
    unexpected_targets = sorted(
        target for target in layout
        if not layout_target_allowed(target, template_data.get("layout", {}))
    )
    if unexpected_targets:
        print(f"❌ pacman.json layout has inaccessible target(s) in {pkg_name}: {unexpected_targets}")
        all_ok = False

    invalid_sources = [
        f"{target}: {source}"
        for target, sources in layout.items()
        for source in sources
        if not layout_source_allowed(source)
    ]
    if invalid_sources:
        print(f"❌ pacman.json layout has invalid source path(s) in {pkg_name}: {invalid_sources}")
        all_ok = False

    actual_target_paths = {
        layout_entry_target_path(target, source)
        for target, sources in layout.items()
        for source in sources
        if layout_source_allowed(source)
    }
    expected_target_paths = {
        layout_entry_target_path(target, source)
        for target, sources in expected_layout.items()
        for source in sources
    }
    extra_target_paths = sorted(actual_target_paths - expected_target_paths)
    if extra_target_paths:
        print(f"❌ pacman.json layout has stale target path(s) in {pkg_name}: {extra_target_paths}")
        all_ok = False

    for target, expected_sources in expected_layout.items():
        actual_sources = layout.get(target, [])
        missing_sources = [
            source for source in expected_sources
            if layout_entry_target_path(target, source) not in actual_target_paths
        ]
        if missing_sources:
            print(f"❌ pacman.json layout mismatch in {pkg_name}: {target}")
            verbose_print(f"  missing expected target(s): {missing_sources}")
            verbose_print(f"  actual:   {actual_sources}")
            all_ok = False

    for target, actual_sources in layout.items():
        if len(actual_sources) != len(set(actual_sources)):
            print(f"❌ pacman.json layout has duplicate source(s) in {pkg_name}: {target}")
            all_ok = False

    pacman_deps = pacman_data.get("deps", [])
    if not isinstance(pacman_deps, list) or any(isinstance(dep, list) for dep in pacman_deps):
        print(f"❌ pacman.json deps must be a flat list of package folder names in {pkg_name}")
        all_ok = False

    return all_ok


def main(pack_name:str=None, verbose:bool=True):
    global VERBOSE
    VERBOSE = verbose

    packages = resolve_packages(pack_name)

    if not packages:
        print("⚠️ No packages found (no subfolders containing package.json).")
        return False

    verbose_print(f"🔍 Found {len(packages)} package(s).")

    validation_ok = True
    for pkg in packages:
        package_ok = True
        if not validate_package_json(pkg):
            package_ok = False
        if not validate_package(pkg):
            package_ok = False
        validation_ok &= package_ok
        if package_ok:
            verbose_print("  ✔️ VALID\n")
        else:
            print("  ✖️ INVALID\n")

    if validation_ok:
        print("🎉 All packages are valid!")
    else:
        print("❗ Some packages failed validation.\n\tFix: ./tools.py --update <package-name>")
        if not VERBOSE:
            print("\tFor more details, run: ./tools.py --validate")
    return validation_ok


if __name__ == "__main__":
    sys.exit(main())
