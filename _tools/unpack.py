#!/usr/bin/env python3
import os.path
import json
from pathlib import Path
import shutil
REPO_ROOT  = Path(__file__).resolve().parent.parent
CACHE_DIR_PATH  = Path(__file__).resolve().parent / "cache"
DEFAULT_UNPACKED_DIR = REPO_ROOT / "unpacked"
WEB_DATA_DIR = "data"


def path_within(path:Path, root:Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def is_resource_target(target: str) -> bool:
    return (
        target == "/web"
        or target.startswith("/web/")
        or target == "/data"
        or target.startswith("/data/")
    )

try:
    from .validate import find_all_packages, GITHUB_BASE, load_template_pacman_json
except ImportError:
    print("Import error: validate")
    from validate import find_all_packages, GITHUB_BASE, load_template_pacman_json
try:
    from .package_rules import layout_source_allowed, layout_target_allowed, package_name_allowed, relative_path_allowed
except ImportError:
    print("Import error: package_rules")
    from package_rules import layout_source_allowed, layout_target_allowed, package_name_allowed, relative_path_allowed
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
        if not isinstance(file, (list, tuple)) or len(file) != 2:
            raise ValueError(f"Invalid package URL mapping: {file}")
        target, source = file
        if not relative_path_allowed(target):
            raise ValueError(f"Invalid package install target: {target}")
        if not isinstance(source, str) or not source.startswith(f"{GITHUB_BASE}/"):
            raise ValueError(f"Invalid local package source: {source}")
        source_rel = source[len(GITHUB_BASE) + 1:]
        if not relative_path_allowed(source_rel):
            raise ValueError(f"Invalid local package source path: {source}")
        mod_source_path = REPO_ROOT / source_rel
        mod_target_path = target_dir_lib / target
        if not path_within(mod_source_path, REPO_ROOT):
            raise ValueError(f"Local package source escapes repository: {source}")
        if not path_within(mod_target_path, target_dir_lib):
            raise ValueError(f"Package install target escapes /lib: {target}")
        mod_source = str(mod_source_path)
        mod_target = str(mod_target_path)
        copy_struct.append([mod_target, mod_source])
    return copy_struct


def copy_package_resources(local_packages):

    for package_source in local_packages:
        source_path = Path(package_source[1])
        target_path = Path(package_source[0])
        print(f"COPY {source_path} to {target_path}")
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(source_path, target_path)
        except Exception as e:
            print(f"Error copying {source_path} to {target_path}: {e}")
            raise


def resolve_layout_source(lib_path:Path, package_name:str, target:str, source:str) -> Path:
    if is_resource_target(target):
        direct_source = lib_path / package_name / source
        package_prefixed_source = lib_path / source
        if Path(source).parts and Path(source).parts[0] == package_name:
            if direct_source.exists():
                return direct_source
            if package_prefixed_source.exists():
                return package_prefixed_source
            return direct_source
        target_parts = Path(target.lstrip("/")).parts
        target_rel = Path(*target_parts[1:]) if len(target_parts) > 1 else None
        child_target_source = lib_path / package_name / target_rel / source if target_rel else None
        source_parts = Path(source).parts
        prefer_child_target = (
            child_target_source is not None
            and not (target_parts[0] == "web" and target_rel.parts[0] == WEB_DATA_DIR)
        )
        if prefer_child_target and child_target_source.exists():
            return child_target_source
        if (
            not direct_source.exists()
            and len(source_parts) > 1
            and source_parts[0] == WEB_DATA_DIR
        ):
            return lib_path / package_name / Path(*source_parts[1:])
        if not direct_source.exists() and child_target_source is not None:
            return child_target_source
        return direct_source
    return lib_path / source


def resolve_layout_target(lib_path:Path, package_name:str, target:str, source:str) -> Path:
    if is_resource_target(target):
        source_parts = Path(source).parts
        direct_source = lib_path / package_name / source
        package_prefixed_source = lib_path / source
        if (
            source_parts
            and source_parts[0] == package_name
            and package_prefixed_source.exists()
            and not direct_source.exists()
        ):
            source_rel = Path(*source_parts[1:])
        else:
            source_rel = Path(source)
    else:
        source_rel = Path(source).name
    return lib_path.parent / target.lstrip("/") / source_rel


def load_installed_pacman(lib_path:Path, package_name:str) -> dict | None:
    if not package_name_allowed(package_name):
        print(f"[Unpack] Skip invalid PLCM dependency: {package_name}")
        return None
    package_path = lib_path / package_name
    pacman_json_path = package_path / "pacman.json"
    if not package_path.is_dir():
        print(f"[Unpack] Skip PLCM dependency {package_name}: package folder missing")
        return None
    if not pacman_json_path.is_file():
        print(f"[Unpack] Skip PLCM dependency {package_name}: pacman.json missing")
        return None
    try:
        with open(pacman_json_path, 'r') as f:
            package_data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[Unpack] Skip PLCM dependency {package_name}: cannot read pacman.json ({e})")
        return None
    if not isinstance(package_data, dict):
        print(f"[Unpack] Skip PLCM dependency {package_name}: invalid pacman.json")
        return None
    return package_data


def post_install(lib_path:Path, package_name:str, processed:set[str]=None, active:set[str]=None, template_layout:dict=None) -> tuple[list, list]:
    """
    MICROS ON-DEVICE SIDE - recursive PLCM post install simulation + load module name collection
    returns: overwritten_files, load_modules_list
    """
    processed = set() if processed is None else processed
    active = set() if active is None else active
    if template_layout is None:
        template_layout = load_template_pacman_json().get("layout", {})
    overwrites = []
    ext_load_modules = []
    if package_name in processed:
        return overwrites, ext_load_modules
    if package_name in active:
        print(f"[Unpack] Skip cyclic PLCM dependency: {package_name}")
        return overwrites, ext_load_modules

    package_data = load_installed_pacman(lib_path, package_name)
    if package_data is None:
        return overwrites, ext_load_modules

    active.add(package_name)
    dependencies = package_data.get("deps", [])
    if not isinstance(dependencies, list):
        print(f"[Unpack] Skip invalid PLCM deps in {package_name}: {dependencies}")
        dependencies = []
    for dependency in dependencies:
        if not isinstance(dependency, str):
            print(f"[Unpack] Skip invalid PLCM dependency in {package_name}: {dependency}")
            continue
        dep_overwrites, dep_load_modules = post_install(lib_path, dependency, processed, active, template_layout)
        overwrites.extend(dep_overwrites)
        ext_load_modules.extend(dep_load_modules)
    active.discard(package_name)

    print(f"[Unpack] Apply PLCM layout: {package_name}")
    package_layout = package_data.get("layout", {})
    if not isinstance(package_layout, dict):
        print(f"[Unpack] Skip invalid PLCM layout in {package_name}: {package_layout}")
        package_layout = {}
    for target, sources in package_layout.items():
        if not layout_target_allowed(target, template_layout) or not isinstance(sources, list):
            print(f"[Unpack] Skip invalid PLCM layout sources in {package_name}: {target}")
            continue
        for s in sources:
            if not layout_source_allowed(s):
                print(f"[Unpack] Skip invalid PLCM layout source in {package_name}: {s}")
                continue
            source_abs_path = resolve_layout_source(lib_path, package_name, target, s)
            target_abs_path = resolve_layout_target(lib_path, package_name, target, s)
            print(f"[Unpack] Move {source_abs_path} -> {target_abs_path}")
            if not path_within(source_abs_path, lib_path) or not path_within(target_abs_path, lib_path.parent):
                print(f"[Unpack] Skip PLCM path outside install roots: {target}: {s}")
                continue
            if source_abs_path == target_abs_path:
                continue
            if not source_abs_path.is_file():
                print(f"[Unpack] Skip missing or non-file source: {source_abs_path}")
                continue
            if target_abs_path.exists() and not target_abs_path.is_file():
                print(f"[Unpack] Skip non-file target: {target_abs_path}")
                continue
            if not target_abs_path.parent.is_dir():
                print(f"[Unpack] Create subdir: {str(target_abs_path.parent)}")
                target_abs_path.parent.mkdir(parents=True)
            if target_abs_path.is_file():
                overwrites.append(str(target_abs_path).replace(str(lib_path.parent), ""))
            shutil.move(source_abs_path, target_abs_path)
            if s.startswith("LM_"):
                ext_load_modules.append(s)
    processed.add(package_name)
    return overwrites, ext_load_modules


# --- the caching decorator (one main folder per package@version) ---
def cache_dep(func):

    def _copy_delta(delta_paths: set[Path], src_root: Path, cache_pkg: Path) -> None:
        """
        Copy new/changed items listed in delta_paths into cache_pkg, preserving
        paths relative to src_root. Creates missing dirs as needed.

        delta_paths: absolute Paths (files/dirs) under src_root
        src_root: the root to compute relative paths from (e.g. .../unpacked/lib)
        cache_pkg: destination root
        """
        src_root = Path(src_root).resolve()
        cache_pkg = Path(cache_pkg).resolve()

        # Work only with items that still exist and are under src_root
        items = []
        for p in delta_paths:
            p = Path(p)
            if not p.exists():
                continue
            try:
                p.relative_to(src_root)
            except ValueError:
                continue
            items.append(p)

        # Ensure directories are created before files (important)
        items.sort(key=lambda p: (p.is_file(), str(p)))

        for src in items:
            rel = src.relative_to(src_root)
            dst = cache_pkg / rel

            if src.is_dir():
                dst.mkdir(parents=True, exist_ok=True)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

    def wrapper(package:str, version:str, target_path:Path):
        target_str = str(target_path)
        cache_root = CACHE_DIR_PATH / "deps"
        cache_pkg = cache_root / f"{package}@{version}"
        if not path_within(cache_pkg, cache_root):
            raise ValueError(f"Invalid dependency cache path: {package}@{version}")

        print(f"🗄️ [CACHE] Deps path: {str(cache_pkg)}")
        if cache_pkg.is_dir():
            print("[CACHE] RESTORE ... skip mip install")
            try:
                _copy_delta({p.resolve() for p in cache_pkg.rglob("*")}, cache_pkg, target_path)
                return None
            except Exception as e:
                print(f"\t❌ Restore failed: {e}")

        # Install and cache 3PP from the internet
        print(f"\tCreate cache dir: {'/'.join(str(cache_pkg).split('/')[-2:])}")
        os.makedirs(cache_pkg, exist_ok=True)
        before_snapshot = {p.resolve() for p in target_path.rglob("*")}
        # Run decorated function
        result = func(package, version, target_str)
        after_snapshot = {p.resolve() for p in target_path.rglob("*")}
        new_contents = after_snapshot - before_snapshot
        print("[CACHE] BACKUP ... cache mip install content")
        try:
            _copy_delta(new_contents, target_path, cache_pkg)
        except Exception as e:
            print(f"\t❌ Backup failed: {e}")
        return result

    return wrapper

def clean_cache():
    if DEFAULT_UNPACKED_DIR.exists():
        print(f"🗑️  Clean default unpacked dir: {str(DEFAULT_UNPACKED_DIR)}")
        shutil.rmtree(DEFAULT_UNPACKED_DIR)
    if CACHE_DIR_PATH.exists():
        print(f"🗑️  Clean cache dir: {str(CACHE_DIR_PATH)}")
        shutil.rmtree(CACHE_DIR_PATH)
        return
    print(f"Cache dir not exists: {str(CACHE_DIR_PATH)}")

# --- the decorated single-dependency installer ---
@cache_dep
def _install_dep(package:str, version:str, target_path:Path):
    if isinstance(target_path, Path):
        # Make sure target_path is mip compatible (str)
        target_path = str(target_path)
    print(f"[DEP] Install: {package} @{version} ({target_path})")
    if version in (None, "", "latest"):
        mip_install(package=package, target=target_path)
        return
    mip_install(package=package, target=target_path, version=version)


def download_deps(deps:list, target_path:Path):
    """
    micrOS.Simulator -> mip.py copy usage - download 3pps (with 3PP caching)
    """
    print(f"INSTALL 3PPs FROM DEPS: {deps}\n\tTARGET: {str(target_path)}")
    for dep in deps:
        if not isinstance(dep, list):
            raise Exception(f"Invalid deps structure: {dep} must be list, structure must be [[],[],...]")
        package = dep[0]
        version = dep[1] if len(dep) > 1 else "latest"

        # Only this part is now "decorated logic":
        _install_dep(package, version, target_path)


def unpack_package(package_path:Path, target_path:Path) -> tuple[list, list]:
    """
    1. Create target_path folder
    2. Parse package.json from package_path/package.json
    3. Copy files from package_path/package/* to target_path based on package.json urls
    """
    print(f"📦 [UNPACK] {package_path.name}")
    source_package_json_path = package_path / "package.json"

    # Build target dir structure - ensure prerequisites
    target_dir_root = target_path
    target_dir_lib = target_dir_root / "lib"
    target_dir_lib_package = target_dir_lib / package_path.name
    target_dir_web = target_dir_root / "web"
    target_dir_data = target_dir_root / "data"
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
    if not target_dir_web.is_dir():
        print(f"[Unpack] Create dir: {target_dir_web}")
        target_dir_web.mkdir(exist_ok=True)
    if not target_dir_data.is_dir():
        print(f"[Unpack] Create dir: {target_dir_data}")
        target_dir_data.mkdir(exist_ok=True)
    if not target_dir_lib_package.is_dir():
        print(f"[Unpack] Create dir: {target_dir_lib_package}")
        target_dir_lib_package.mkdir(exist_ok=True)

    # PACKAGE.JSON
    version, files, deps = parse_package_json(source_package_json_path)
    local_package_source = resolve_urls_with_local_path(files, target_dir_lib)
    copy_package_resources(local_package_source)
    # Download deps - 3pps
    try:
        download_deps(deps, target_dir_lib)
    except Exception as e:
        print(f"❌ 3PP DEP install failed: {e}")
        raise
    # PACMAN.JSON
    overwrites, load_modules = post_install(target_dir_lib, package_path.name)
    return overwrites, load_modules


def unpack_all(target:Path=None):
    """
    Find and unpack all packages to target folder
    :param target: target directory
    """
    if target is None:
        target = DEFAULT_UNPACKED_DIR
    print(f"UNPACK ALL PACKAGES FROM {REPO_ROOT}")
    all_overwrites = []
    all_lm_names = []
    for pkg in find_all_packages(REPO_ROOT):
        overwrites, load_modules = unpack_package(Path(pkg), target)
        all_overwrites += overwrites
        all_lm_names += load_modules
    print(f"[UNPACK] Overwritten from packages: {all_overwrites}")
    print(f"[UNPACK] Available Load Modules: {all_lm_names}")
    return all_overwrites, all_lm_names


if __name__ == "__main__":
    unpack_all()
