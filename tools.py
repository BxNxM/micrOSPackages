#!/usr/bin/env python3

import argparse
from _tools import validate, serve_packages, create_package

def build_parser():
    parser = argparse.ArgumentParser(
        description="CLI tool supporting validate, serve, and create options."
    )

    # VALIDATE: optional package name
    parser.add_argument(
        "-v", "--validate",
        nargs="?",
        const="__ALL__",   # Special marker meaning user passed -v without a value
        help="✅ Validate a package by name. If no name is provided, validate all packages."
    )

    # SERVE: simple flag
    parser.add_argument(
        "-s", "--serve",
        action="store_true",
        help="🌐 Start the mip server (TODO)"
    )

    # CREATE: enabling creation mode
    parser.add_argument(
        "-c", "--create",
        action="store_true",
        help="📦 Create micrOS application package"
    )

    # UPDATE: package.json urls
    parser.add_argument(
        "-u", "--update",
        help="✅ Update application package.json by its package name"
    )

    # Additional params for CREATE
    parser.add_argument("--package", help="[Package] Name of the package/application")
    parser.add_argument("--module", help="[LM] Public command name")

    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()

    # --- VALIDATE LOGIC ---
    if args.validate is not None:
        if args.validate == "__ALL__":
            print("Validating ALL packages...")
            validate.main()
        else:
            print(f"Validating package: {args.validate}")
            validate.main(pack_name=args.validate)

    # --- SERVE LOGIC ---
    if args.serve:
        print("Starting server...")
        serve_packages.main()

    # --- UPDATE LOGIC ---
    if args.update is not None:
        package_name = args.update
        package_path = create_package.REPO_ROOT / package_name / "package"
        print(f"Updating package.json for {package_name}")
        create_package.update_package_json(package_path, package_name)

    # --- CREATE LOGIC ---
    if args.create:
        print("Creating micrOS Application Package...")
        if args.package is None:
            args.package = input("Package name: ")
        if args.module is None:
            args.module = input("Command (load module) name: ")
        print(f"  package name: {args.package}")
        print(f"  command: {args.module}")
        create_package.create_package(package=args.package, module=args.module)
        print(f"Shell example, download: pacman download ...")
        print(f"Shell example, execution:\n\t{args.module} load\n\t{args.module} do")
