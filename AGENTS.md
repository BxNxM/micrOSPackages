# micrOS Packages Agent Guide

## Purpose

This directory is the micrOS package registry. Each top-level package is a MicroPython `mip` package with extra micrOS metadata for post-install file placement.

A package has this shape:

```text
my_package/
├── package.json
├── package/
│   ├── LM_my_feature.py
│   ├── __init__.py
│   ├── helper.py
│   ├── widget.html
│   └── pacman.json
└── tests/
```

Prefer a flat `package/` folder. One level of package-owned folders is also supported and preserved:

```text
package/feature/file2.py -> /lib/my_package/feature/file2.py
```

The two manifests have different roles:

- `package.json` is the MicroPython `mip` manifest. It installs package files into `/lib`.
- `package/pacman.json` is micrOS metadata. It describes post-install moves only.

`/lib` is the default install path for package management. Do not represent `/lib` or `/lib/<package>` in `pacman.json["layout"]`.

## Packaging

Run package updates with:

```bash
python3 tools.py -u my_package
python3 tools.py -u ALL
```

Packaging scans `package/`, excluding `__pycache__`, then regenerates `package.json["urls"]` and `package/pacman.json`.

`package.json` must stay `mip` compatible. Destination rules:

```text
package/LM_name.py       -> LM_name.py
package/file.py          -> my_package/file.py
package/folder/file2.py  -> my_package/folder/file2.py
package/pacman.json      -> my_package/pacman.json
```

`package.json["deps"]` keeps full `mip` dependency references:

```json
[
    ["github:BxNxM/micrOSPackages/sim800", "main"]
]
```

`pacman.json` required top-level keys come from `_tools/app_template/package/pacman.json`:

- `versions`
- `url`
- `layout`
- `deps`

Template layout roots are:

```text
/modules
/data
/web
```

Generated `pacman.json["layout"]` contains only files that need post-install moves:

- `LM_*.py` -> `/modules`
- `.html`, `.js`, `.css` -> `/web`
- `.png`, `.jpeg`, `.ico`, `.gif` -> `/web` as `data/...`
- other non-`.py`, non-`pacman.json` files -> `/data`

Regular Python library files are not listed in `pacman.json["layout"]`; they stay where `mip` installs them under `/lib/<package>`.

Web paths preserve the path defined under `package/` and do not add the package name:

```text
package/matrix/matrix_draw.html -> /web/matrix/matrix_draw.html
package/matrix_draw.html        -> /web/matrix_draw.html
package/icon.png                -> /web/data/icon.png
```

Because `/web` is an accessible root, user-defined child targets such as `/web/data` are valid when they map to the same generated target path. For example, `/web: ["data/icon.png"]` and `/web/data: ["icon.png"]` both mean `/web/data/icon.png`. Updates may preserve the user form, but stale entries such as `/web/test/matrix_draw.html` must be removed.

`pacman.json["deps"]` is generated from `package.json["deps"]` as package folder names only:

```json
["sim800", "phone_manager"]
```

Shared path and merge rules live in `_tools/package_rules.py`. Keep generator, validator, and unpack behavior aligned through that module.

Validate with:

```bash
python3 tools.py -v -q
python3 tools.py -ut -q
```

Validation checks package URLs, required pacman keys, accessible layout roots, stale layout target paths, duplicate layout entries, unsafe paths, and flat pacman deps.

Inspect generated pacman metadata with:

```bash
python3 tools.py -i my_package
python3 tools.py --inspect my_package
```

## Unpackaging

Run local unpack simulation with:

```bash
python3 tools.py --unpack
```

Default output:

```text
unpacked/
├── lib/
├── modules/
├── web/
└── data/
```

Unpack steps:

1. Read `package.json`.
2. Copy every `package.json["urls"]` entry into `unpacked/lib`.
3. Install/cache `package.json["deps"]` into `unpacked/lib`.
4. Read `unpacked/lib/<package>/pacman.json`.
5. Apply `pacman.json["layout"]` as post-install moves.

Examples:

```text
package/LM_my_feature.py -> unpacked/lib/LM_my_feature.py -> unpacked/modules/LM_my_feature.py
package/helper.py        -> unpacked/lib/my_package/helper.py
package/folder/file2.py  -> unpacked/lib/my_package/folder/file2.py
package/pacman.json      -> unpacked/lib/my_package/pacman.json
package/matrix/file.html -> unpacked/lib/my_package/matrix/file.html -> unpacked/web/matrix/file.html
```

`pacman.json` remains in `unpacked/lib/<package>/pacman.json`. Regular library files are not moved by pacman; they remain under `/lib/<package>` from the initial `mip` copy.

Keep `_tools/unpack.py` lightweight. It should copy files, install deps, and apply layout. Mapping policy belongs in `_tools/package_rules.py`.

## Uninstall

Uninstall should read installed metadata from:

```text
/lib/<package>/pacman.json
```

Uninstall is the reverse of unpack post-install moves, plus removal of the package install tree.

Expected layout cleanup:

```text
"/modules": ["LM_my_feature.py"]   -> remove /modules/LM_my_feature.py
"/web": ["matrix/file.html"]       -> remove /web/matrix/file.html
"/web": ["data/icons/app.png"]     -> remove /web/data/icons/app.png
"/web/data": ["icons/app.png"]     -> remove /web/data/icons/app.png
"/data": ["my_package/config.py"]  -> remove /data/config.py
```

After layout cleanup, remove `/lib/<package>`, including `/lib/<package>/pacman.json` and regular library files installed by `mip`.

Do not automatically remove packages listed in `pacman.json["deps"]`; dependencies may be shared. Dependency cleanup must be explicit.

Uninstall must be conservative:

- Skip missing files without failing the whole uninstall.
- Never delete outside known micrOS roots: `/lib`, `/modules`, `/web`, and `/data`.
- Remove empty directories bottom-up, stopping at those known roots.
- Do not discover extra files by broad directory scans; use `pacman.json["layout"]` and the package tree under `/lib/<package>`.
