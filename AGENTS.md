# micrOS Packages Agent Guide

## Purpose

This directory is the micrOS package registry. Each top-level folder is a
MicroPython `mip` package with extra micrOS Package Life Cycle Management
(PLCM) metadata.

The two manifests have distinct roles:

- `package.json` is the MicroPython `mip` manifest. It installs package content
  into `/lib`.
- `package/pacman.json` is micrOS PLCM metadata. It describes only the files
  that must move after the `mip` install and later be removed during uninstall.

`/lib` is the default `mip` install location. Never store `/lib` or
`/lib/<package>` entries in `pacman.json["layout"]`.

## Idea

A package normally keeps a flat source layout:

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

One level of package-owned folders is also supported and preserved:

```text
package/feature/file2.py -> /lib/my_package/feature/file2.py
```

The lifecycle is intentionally simple:

1. Generate the `mip` file map in `package.json`.
2. Generate micrOS PLCM metadata in `package/pacman.json` from that map.
3. Let `mip` install everything into `/lib`.
4. Apply PLCM moves for files that belong in `/modules`, `/data`, or `/web`.

Shared scan, mapping, and merge rules live in `_tools/package_rules.py`. Keep
generation, validation, inspection, and unpack behavior aligned through that
module.

## Packaging

Update one package or the whole registry:

```bash
python3 tools.py -u my_package
python3 tools.py -u ALL
```

Packaging scans `package/`, excluding `__pycache__`, then follows one ordered
pipeline:

1. Regenerate `package.json["urls"]` as the `mip` install map.
2. Read the updated `package.json`.
3. Regenerate `package/pacman.json` as PLCM metadata.

Both package creation and update use this same flow.

The `package.json` destination rules are:

```text
package/LM_name.py       -> LM_name.py
package/file.py          -> my_package/file.py
package/folder/file2.py  -> my_package/folder/file2.py
package/pacman.json      -> my_package/pacman.json
```

Keep `package.json["deps"]` fully `mip` compatible:

```json
[
    ["github:BxNxM/micrOSPackages/sim800", "main"]
]
```

Required `pacman.json` top-level keys come from
`_tools/app_template/package/pacman.json`. Only those top-level defaults are
mandatory. Do not copy template example children into user metadata.

Generated `pacman.json["layout"]` contains post-install moves only:

- root-level `LM_*.py` files -> `/modules`
- root-level `.html`, `.js`, `.css` files -> `/web`
- root-level `.png`, `.jpeg`, `.ico`, `.gif` files -> `/web/data`
- other root-level resources -> `/data`
- regular `.py`, `.mpy`, and `pacman.json` files -> remain under
  `/lib/<package>`

Nested folders are compact standalone units. Preserve their path beneath
`package/` without adding the package name:

- If a nested folder contains any `.py` or `.mpy` file, keep the entire folder
  under `/lib/<package>/<folder>`, including companion data files.
- Otherwise, if a nested folder contains a web resource, move its files
  together under `/web/<folder>`.
- Otherwise, keep the entire nested folder under `/lib/<package>/<folder>`.

Only top-level non-library resources move independently to `/data`.

```text
package/icon.png                   -> /web/data/icon.png
package/config.txt                 -> /data/config.txt
package/folder/helper.py           -> /lib/my_package/folder/helper.py
package/folder/settings.txt        -> /lib/my_package/folder/settings.txt
package/matrix/matrix_draw.html    -> /web/matrix/matrix_draw.html
package/matrix/background.png      -> /web/matrix/background.png
package/matrix/default_layout.txt  -> /web/matrix/default_layout.txt
```

PLCM layout roots are `/modules`, `/data`, and `/web`. Valid child targets are
also accepted when they describe the same destination. For example,
`"/web": ["data/icon.png"]` and `"/web/data": ["icon.png"]` are equivalent.
Updates preserve valid user forms and remove stale or invalid entries.

`pacman.json["deps"]` is derived from `package.json["deps"]` as package folder
names only. PLCM uses this list to apply the dependency packages' own
post-install layouts during a complex install:

```json
["sim800", "phone_manager"]
```

Inspect and validate generated metadata with:

```bash
python3 tools.py -i my_package
python3 tools.py -i
python3 tools.py -v -q
python3 tools.py -ut -q
```

Inspection shows the PLCM layout plus a display-only `/lib` section derived
from `package.json`. The `/lib` section is not stored in `pacman.json`.

## Unpackaging

Run the local install simulation with:

```bash
python3 tools.py --unpack
```

The unpack flow mirrors device installation:

1. Read `package.json`.
2. Copy every `package.json["urls"]` entry into `unpacked/lib`.
3. Install or cache `package.json["deps"]` into `unpacked/lib`.
4. Read `unpacked/lib/<package>/pacman.json`.
5. Recursively apply installed PLCM dependency layouts first.
6. Apply the requested package's PLCM layout as post-install moves.

Expected results:

```text
package/LM_my_feature.py -> unpacked/modules/LM_my_feature.py
package/helper.py        -> unpacked/lib/my_package/helper.py
package/folder/file2.py  -> unpacked/lib/my_package/folder/file2.py
package/pacman.json      -> unpacked/lib/my_package/pacman.json
package/matrix/file.html -> unpacked/web/matrix/file.html
package/folder/file.txt  -> unpacked/lib/my_package/folder/file.txt
```

`pacman.json` stays at `/lib/<package>/pacman.json`. Regular library files stay
where `mip` installed them. When traversing PLCM dependencies, skip packages
that do not have an installed `/lib/<dependency>` folder and `pacman.json`.
This allows ordinary third-party `mip` dependencies without PLCM metadata.
Protect recursive traversal from cycles and repeated packages.

### Suggested on-device PLCM flow

After `mip` installs a package, device-side `pacman` should use the installed
metadata at:

```text
/lib/<package>/pacman.json
```

Treat `pacman.json` as an installed PLCM receipt. It must remain under
`/lib/<package>` after unpackaging so later inspect, update, and uninstall
operations can use it.

Suggested device-side procedure:

1. Run the normal `mip` install. This places the requested package and its
   `package.json["deps"]` under `/lib`. If `mip` fails, stop before PLCM moves.
2. Open `/lib/<package>/pacman.json`. If the package folder or metadata file is
   missing, leave the installed files unchanged and skip PLCM unpackaging.
3. Walk `pacman.json["deps"]` recursively. Each entry is a package folder name,
   so resolve it as `/lib/<dependency>/pacman.json`.
4. Apply dependency layouts before the parent package layout.
5. For each `layout` entry, move the installed source from `/lib` into the
   declared `/modules`, `/data`, or `/web` target.
6. Keep `/lib/<package>/pacman.json` and regular Python library files in place.

The device implementation should:

- Track active and completed package names to prevent dependency cycles and
  repeated work.
- Accept dependency package folder names only. Reject empty names, separators,
  `.` values, and `..` values.
- Skip missing dependency folders and missing metadata. Third-party `mip`
  packages do not need to provide `pacman.json`.
- Move regular files only. Skip missing or already-moved source files so
  repeated post-install runs are safe.
- Accept only `/modules`, `/data`, and `/web` layout roots, including valid
  child paths such as `/web/data`.
- Reject absolute source paths and `..` path traversal.

Conceptual pseudocode:

```python
def plcm_unpack(package, active, completed):
    if package in completed or package in active:
        return
    metadata = read_optional("/lib/{}/pacman.json".format(package))
    if metadata is None:
        return
    active.add(package)
    for dependency in metadata.get("deps", []):
        plcm_unpack(dependency, active, completed)
    active.remove(package)
    for target, sources in metadata.get("layout", {}).items():
        for source in sources:
            move_installed_resource(package, source, target)
    completed.add(package)
```

Keep `_tools/unpack.py` lightweight: copying, dependency installation, and move
application belong there; mapping policy belongs in `_tools/package_rules.py`.

## Uninstall

Uninstall is the reverse of the PLCM post-install phase plus removal of the
package tree installed by `mip`.

1. Read `/lib/<package>/pacman.json`.
2. Remove each file listed by `pacman.json["layout"]` from `/modules`, `/data`,
   or `/web`.
3. Remove empty directories bottom-up, stopping at the known root folders.
4. Remove `/lib/<package>`, including its metadata and regular library files.

Uninstall must be conservative:

- Ignore missing files without failing the entire uninstall.
- Never delete outside `/lib`, `/modules`, `/data`, and `/web`.
- Use metadata entries and the package tree only. Do not scan broadly for
  additional files.
- Do not automatically uninstall dependencies. PLCM dependencies may be shared
  and require explicit removal.

Examples:

```text
"/modules": ["LM_my_feature.py"] -> remove /modules/LM_my_feature.py
"/web": ["matrix/file.html"]     -> remove /web/matrix/file.html
"/web/data": ["icons/app.png"]   -> remove /web/data/icons/app.png
```
