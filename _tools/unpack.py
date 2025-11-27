#!/usr/bin/env python3
import os.path
import json
from pathlib import Path
import shutil
REPO_ROOT  = Path(__file__).resolve().parent.parent

try:
    from .validate import find_all_packages, GITHUB_BASE
except ImportError:
    print("Import error: validate")
    from validate import find_all_packages, GITHUB_BASE
try:
    from .mip import install as mip_install
except ImportError:
    print("Import error: mip")
    from mip import install as mip_install


def parse_package_json(package_json_path:Path):
    """
    "urls": [
    [
        "async_oledui/uiframes.py",
        "github:BxNxM/micrOSPackages/async_oledui/package/uiframes.py"
    ], ...]
    Return version, urls and deps
    """
    print(f"[Unpack] package.json {package_json_path}")
    content = {"version": "n/a", "urls": [], "deps": []}
    with open(package_json_path, 'r') as f:
        content = json.load(f)
    return content.get("version", "0.0.0"), content.get("urls", []), content.get("deps", [])


def resolve_urls_with_local_path(files_list:list, target_dir_lib:Path) -> list:
    """
    Replace GitHub URLs with local paths
    """
    copy_struct = []
    for file in files_list:
        target = file[0]
        source = file[1]
        mod_source = source.replace(GITHUB_BASE.rstrip("/"), str(REPO_ROOT))
        mod_target = str(target_dir_lib / target)
        copy_struct.append([mod_target, mod_source])
    return copy_struct


def copy_package_resources(local_packages):

    for package_source in local_packages:
        source_path = package_source[1]
        target_path = package_source[0]
        print(f"COPY {source_path} to {target_path}")
        try:
            shutil.copy(source_path, target_path)
        except Exception as e:
            print(f"Error copying {source_path} to {target_path}: {e}")


def post_install(lib_path:Path) -> list:
    """
    micrOS on-device post install simulation
    """
    print("[Unpack] micrOS on device LM unpack (/modules)")
    files = [f for f in lib_path.glob("LM_*.py") if f.is_file()]
    overwrites = []
    for file in files:
        modules_path = Path(file).parent.parent / "modules"
        file_target_path = modules_path / file.name
        if os.path.exists(file_target_path):
            overwrites.append(f"{file_target_path.parent.name}/{file_target_path.name}")
        print(f"Move {file} to {file_target_path}")
        file.rename(file_target_path)
    return overwrites


def download_deps(deps:list, target_path:Path):
    for dep in deps:
        ref = dep[0]
        version = dep[1] if len(dep) > 1 else "latest"
        print(f"[DEP] Install: {ref} @{version} ({target_path})")
        # TODO version handling...
        mip_install(ref, target=target_path)


def unpack_package(package_path:Path, target_path:Path):
    """
    1. Create target_path folder
    2. Parse package.json from package_path/package.json
    3. Copy files from package_path/package/* to target_path based on package.json urls
    """
    print(f"[UNPACK] {package_path.name}")
    source_package_json_path = package_path / "package.json"

    # Build target dir structure
    target_dir_root = target_path
    target_dir_lib = target_dir_root / "lib"
    target_dir_lib_package = target_dir_lib / package_path.name
    target_dir_modules = target_dir_root / "modules"
    if not target_dir_root.is_dir():
        print(f"[Unpack] Create dir: {target_dir_root}")
        target_dir_root.mkdir(exist_ok=True)
    if not target_dir_lib.is_dir():
        print(f"[Unpack] Create dir: {target_dir_lib}")
        target_dir_lib.mkdir(exist_ok=True)
    if not target_dir_modules.is_dir():
        print(f"[Unpack] Create dir: {target_dir_modules}")
        target_dir_modules.mkdir(exist_ok=True)
    if not target_dir_lib_package.is_dir():
        print(f"[Unpack] Create dir: {target_dir_lib_package}")
        target_dir_lib_package.mkdir(exist_ok=True)

    version, files, deps = parse_package_json(source_package_json_path)
    local_package_source = resolve_urls_with_local_path(files, target_dir_lib)
    copy_package_resources(local_package_source)
    #download_deps(deps, target_dir_lib)
    overwrites = post_install(target_dir_lib)
    return overwrites



def unpack_all(target:Path=None):
    """
    Find and unpack all packages to target folder
    :param target: target directory
    """
    if target is None:
        target = REPO_ROOT / "unpacked"
    print(f"Unpack all packages from {REPO_ROOT}")
    all_overwrites = []
    for pkg in find_all_packages(REPO_ROOT):
        all_overwrites += unpack_package(Path(pkg), target)
    print(f"[Unpack] Overwritten from packages: {all_overwrites}")
    return all_overwrites


if __name__ == "__main__":
    unpack_all()
