#!/usr/bin/env python3
import sys
from pathlib import Path
import shutil
from pprint import pprint
import json

PACKAGER_VERSION = "0.1.0"
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
    if module.statswith("LM_"):
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
    resources = [p.name for p in target_path.iterdir() if p.is_file()]
    print(f"\t Discovered resources: {resources}")
    destination_source_lists = []
    for r in resources:
        _source = f"{github_package_url(package)}/{package_dir_name}/{r}"
        if r.startswith("LM_"):
            destination_source_lists.append([f"{r}", _source])
        else:
            destination_source_lists.append([f"{package}/{r}", _source])
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


def _reset_pacman_json_layout(layout:dict):
    for l in layout:
        layout[l] = []
    print("pacman.json layout reset done")


def update_pacman_json(target_path:Path, package:str):
    """Update pacman.json based on package.json"""
    package_json_file = target_path.parent / "package.json"
    pacman_json_file = target_path.parent / "package" / "pacman.json"

    with open(package_json_file, 'r') as f:
        _package_json_dict = json.load(f)
        package_urls = _package_json_dict.get("urls", [])
        package_version = _package_json_dict.get("version", "0.0.0")
    package_file_targets = [p[0] for p in package_urls if p]
    if not pacman_json_file.exists():
        # Copy pacman.json from template
        template_pacman_json_path = TEMPLATE_DIR / "package" / "pacman.json"
        if template_pacman_json_path.is_file():
            shutil.copy2(template_pacman_json_path, pacman_json_file)
        else:
            print(f"❌Cannot update, not exists: {pacman_json_file}")
            return
    # Update pacman.json
    with open(pacman_json_file, "r+") as f:
        data = json.load(f)  # read the JSON
        data["versions"]["packager"] = PACKAGER_VERSION
        data["versions"]["package"] = package_version
        data["url"] = github_package_url(package)
        _reset_pacman_json_layout(data["layout"])
        for res in package_file_targets:
            # Unpackaging destination generation
            if res.endswith("py"):
                if "LM_" in res:
                    # MOVE: LM_* -> /modules
                    data["layout"]["/modules"].append(res)
                else:
                    # SKIP: basic .py/.mpy in the package
                    continue
            elif res.split(".")[-1] in ["js", "html", "css"]:
                # MOVE: web resources under /web
                data["layout"]["/web"].append(res)
            elif res.split(".")[-1] in ["png", "jpeg", "ico", "gif"]:
                # MOVE: web data under /web
                data["layout"]["/web/data"].append(res)
            else:
                if res.endswith("pacman.json"):
                    continue
                # MOVE: move everything else under /data
                data["layout"]["/data"].append(res)

        f.seek(0)  # move cursor to start
        json.dump(data, f, indent=4)
        f.truncate()  # remove leftover old content
        print(f"✅Updated: {pacman_json_file}")
        pprint(data)
