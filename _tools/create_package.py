#!/usr/bin/env python3
import sys
from pathlib import Path
import shutil
from pprint import pprint
import json
from copy import deepcopy

try:
    from .package_rules import package_dest, package_files, merge_pacman_layout, pacman_layout_for_urls
except ImportError:
    from package_rules import package_dest, package_files, merge_pacman_layout, pacman_layout_for_urls

PACKAGER_VERSION = "0.2.0"
REPO_ROOT  = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = Path(__file__).resolve().parent / "app_template"
GITHUB_BASE = "github:BxNxM/micrOSPackages"

def github_package_url(package):
    """
    Get GITHUB package URL by package name
    :param: pacakge: name of the package
    """
    return f"{GITHUB_BASE}/{package.lstrip('/')}"

def _copy_one_depth(src, dst):
    src = Path(src)
    dst = Path(dst)

    for item in src.iterdir():
        if item.is_file():
            # copy file
            shutil.copy2(item, dst / item.name)

        elif item.is_dir():
            # copy folder itself
            target_dir = dst / item.name
            target_dir.mkdir(exist_ok=True)

            # copy ONLY files inside this folder (no recursion)
            for subfile in item.iterdir():
                if subfile.is_file():
                    shutil.copy2(subfile, target_dir / subfile.name)


def render_readme(package, module):
    """
    Replace placeholders in README template with actual values.
    """
    package_readme_path = REPO_ROOT / package / "README.md"

    # Read the existing content
    with open(package_readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Perform the replacements
    content = (
        content.replace("<package-app-name>", package)
               .replace("<app_name>", module)
               .replace("<package-url>", github_package_url(package))
    )

    # Write back updated content
    with open(package_readme_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✅Updated: {package_readme_path}")


def create_package(package, module):
    """
    :param package: package/application name (folder)
    :param module: module name public load module (LM_*)
    """
    # 0. Input validation and normalization
    if module.startswith("LM_"):
        module = module.replace("LM_", "")
    if "-" in package:
        package = package.replace("-", "_")
    # 1. Create new-package directory in repo root
    print(f"⭐️[1/7] Create new-package directory: {package}")
    target = REPO_ROOT / package
    target_package_dir = target / "package"
    try:
        target.mkdir(exist_ok=False)
    except FileExistsError:
        print(f"❌Package already exists with the same name: {package}")
        sys.exit(1)
    # 2. Copy template files to new-package directory
    print(f"⭐️[2/7] Copy template files from {TEMPLATE_DIR} -> {target}")
    _copy_one_depth(TEMPLATE_DIR, target)
    print(f"⭐️[3/7] Replace package import in LM_app.py from package to {package}")
    temp_app = target_package_dir / "LM_app.py"
    text = temp_app.read_text()
    temp_app.write_text(text.replace("package", package))
    # 3. Rename LM_app.py to LM_<module>.py
    print(f"⭐️[4/7] Rename LM_app.py -> LM_{module}.py")
    Path(target_package_dir / "LM_app.py").rename(target_package_dir / f"LM_{module}.py")
    # 4. Update package.json with new module information
    print(f"⭐️[5/7] Update package.json with new module information")
    update_package_json(target_package_dir, package)
    print(f"⭐️[6/7] Update pacman.json with package management information (layout, url, etc.)")
    update_pacman_json(target_package_dir, package)
    print(f"⭐️[7/7] Render application README")
    render_readme(package, module)


def update_package_json(target_path:Path, package:str):
    """Checking package"""
    package_json_file = target_path.parent / "package.json"
    package_dir_name = target_path.name
    resources = [
        p.relative_to(target_path).as_posix()
        for p in package_files(target_path)
    ]
    print(f"\t Discovered resources: {resources}")
    destination_source_lists = []
    for r in resources:
        _source = f"{github_package_url(package)}/{package_dir_name}/{r}"
        destination_source_lists.append([package_dest(package, r), _source])
    print("Build destination - source mapping for mip")
    #pprint(destination_source_lists, indent=2)
    with open(package_json_file, "r+") as f:
        data = json.load(f)  # read the JSON
        data["urls"] = destination_source_lists  # modify it

        f.seek(0)  # move cursor to start
        json.dump(data, f, indent=4)
        f.truncate()  # remove leftover old content
        print("⭐️Updated urls in package.json")
        pprint(data, indent=2)
    print(f"✅Updated: {package_json_file}")


def _load_template_pacman_json():
    template_pacman_json_path = TEMPLATE_DIR / "package" / "pacman.json"
    with open(template_pacman_json_path, "r") as f:
        return json.load(f)


def _merge_pacman_template_defaults(data:dict, template_data:dict):
    """Backfill new top-level pacman.json template sections into existing packages."""
    for key, value in template_data.items():
        if key not in data:
            data[key] = deepcopy(value)


def _pacman_dep_name(dep_name:str):
    return dep_name.rstrip("/").split("/")[-1]


def _pacman_deps(package_deps:list):
    pacman_deps = []
    for dep in package_deps:
        if isinstance(dep, list) and dep:
            pacman_deps.append(_pacman_dep_name(dep[0]))
        elif isinstance(dep, str):
            pacman_deps.append(_pacman_dep_name(dep))
        else:
            pacman_deps.append(dep)
    return pacman_deps


def update_pacman_json(target_path:Path, package:str):
    """Update pacman.json based on package.json"""
    package_json_file = target_path.parent / "package.json"
    pacman_json_file = target_path.parent / "package" / "pacman.json"
    template_pacman_json_path = TEMPLATE_DIR / "package" / "pacman.json"

    with open(package_json_file, 'r') as f:
        _package_json_dict = json.load(f)
        package_urls = _package_json_dict.get("urls", [])
        package_version = _package_json_dict.get("version", "0.0.0")
        package_deps = _package_json_dict.get("deps", [])
    if not pacman_json_file.exists():
        # Copy pacman.json from template
        if template_pacman_json_path.is_file():
            shutil.copy2(template_pacman_json_path, pacman_json_file)
        else:
            print(f"❌Cannot update, not exists: {pacman_json_file}")
            return
    # Update pacman.json
    with open(pacman_json_file, "r+") as f:
        data = json.load(f)  # read the JSON
        template_data = _load_template_pacman_json()
        _merge_pacman_template_defaults(data, template_data)
        data["versions"]["packager"] = PACKAGER_VERSION
        data["versions"]["package"] = package_version
        data["url"] = github_package_url(package)
        data["deps"] = _pacman_deps(package_deps)
        generated_layout = pacman_layout_for_urls(package, package_urls, template_data.get("layout", {}))
        data["layout"] = merge_pacman_layout(data.get("layout", {}), generated_layout, template_data.get("layout", {}))

        f.seek(0)  # move cursor to start
        json.dump(data, f, indent=4)
        f.truncate()  # remove leftover old content
        print(f"✅Updated: {pacman_json_file}")
        pprint(data)
