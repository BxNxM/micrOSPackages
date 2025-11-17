#!/usr/bin/env python3
import sys
from pathlib import Path
import shutil
from pprint import pprint
import json

REPO_ROOT  = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = Path(__file__).resolve().parent / "app_template"
GITHUB_BASE = "github:BxNxM/micrOSPackages"

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


def create_package(package, module):
    """
    :param package: package/application name (folder)
    :param module: module name public load module (LM_*)
    """
    # 1. Create new-package directory in repo root
    print(f"⭐️[1/5] Create new-package directory: {package}")
    target = REPO_ROOT / package
    target_package_dir = target / "package"
    try:
        target.mkdir(exist_ok=False)
    except FileExistsError:
        print(f"❌Package already exists with the same name: {package}")
        sys.exit(1)
    # 2. Copy template files to new-package directory
    print(f"⭐️[2/5] Copy template files from {TEMPLATE_DIR} -> {target}")
    _copy_one_depth(TEMPLATE_DIR, target)
    print(f"⭐️[3/5] Replace package import in LM_app.py from package to {package}")
    temp_app = target_package_dir / "LM_app.py"
    text = temp_app.read_text()
    temp_app.write_text(text.replace("package", package))
    # 3. Rename LM_app.py to LM_<module>.py
    print(f"⭐️[4/5] Rename LM_app.py -> LM_{module}.py")
    Path(target_package_dir / "LM_app.py").rename(target_package_dir / f"LM_{module}.py")
    # 4. Update package.json with new module information
    print(f"⭐️[5/5] Update package.json with new module information")
    update_package_json(target_package_dir, package)


def update_package_json(target_path, package):
    """Checking package"""
    package_json_file = target_path.parent / "package.json"
    package_dir_name = target_path.name
    resources = [p.name for p in target_path.iterdir() if p.is_file()]
    print(f"\t Discovered resources: {resources}")
    destination_source_lists = []
    for r in resources:
        _source = f"{GITHUB_BASE}/{package}/{package_dir_name}/{r}"
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
