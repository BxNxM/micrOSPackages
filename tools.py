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
        help="🌐 Start the mip server"
    )

    # CREATE: enabling creation mode
    parser.add_argument(
        "-c", "--create",
        action="store_true",
        help="📦 Create micrOS application package (requires additional create parameters)."
    )

    # Additional params for CREATE
    parser.add_argument("--name", help="[Package] Name of the application")
    parser.add_argument("--command", help="[LM] Command to run the application")

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

    # --- CREATE LOGIC ---
    if args.create:
        print("Creating micrOS Application Package...")
        if args.name is None:
            args.name = input("Project name? ")
        if args.command is None:
            args.command = input("Command name? ")
        print(f"  name:    {args.name}")
        print(f"  command: {args.command}")
        create_package.create_package(name=args.name, command=args.command)
        print(f"Shell example, download: pacman download ...")
        print(f"Shell example, execution:\n\t{args.command} load\n\t{args.command} do")
