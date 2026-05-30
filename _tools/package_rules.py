from pathlib import Path

WEB_EXTENSIONS = {"js", "html", "css"}
WEB_DATA_EXTENSIONS = {"png", "jpeg", "ico", "gif"}
LIB_EXTENSIONS = {"py", "mpy"}
WEB_DATA_DIR = "data"


def package_files(package_dir: Path) -> list[Path]:
    return [
        p for p in sorted(package_dir.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts
    ]


def package_dest(package: str, rel_path: str) -> str:
    if rel_path.startswith("LM_"):
        return rel_path
    return f"{package}/{rel_path}"


def strip_package_prefix(path: str, package: str) -> str:
    prefix = f"{package}/"
    if path.startswith(prefix):
        return path[len(prefix):]
    return path


def package_layout_resource(path: str, package: str) -> str:
    rel = Path(strip_package_prefix(path, package))
    return rel.as_posix()


def resource_extension(path: str) -> str:
    return path.rsplit(".", 1)[-1] if "." in path else ""


def package_name_allowed(package: str) -> bool:
    return (
        isinstance(package, str)
        and bool(package)
        and package not in {".", ".."}
        and "/" not in package
        and "\\" not in package
    )


def relative_path_allowed(path: str) -> bool:
    if not isinstance(path, str) or not path or "\\" in path:
        return False
    parts = Path(path).parts
    return (
        bool(parts)
        and not Path(path).is_absolute()
        and ".." not in parts
    )


def is_pacman_metadata(path: str) -> bool:
    parts = Path(path).parts
    return len(parts) == 2 and parts[-1] == "pacman.json"


def is_load_module(path: str) -> bool:
    return resource_extension(path) == "py" and path.startswith("LM_")


def _nested_folder(path: str, package: str) -> str | None:
    rel = Path(strip_package_prefix(path, package))
    return rel.parts[0] if len(rel.parts) > 1 else None


def _lib_bundle_folders(package: str, urls: list[list[str]]) -> set[str]:
    folders = set()
    for dest, _src in urls:
        folder = _nested_folder(dest, package)
        if folder is not None and resource_extension(dest) in LIB_EXTENSIONS:
            folders.add(folder)
    return folders


def _web_bundle_folders(package: str, urls: list[list[str]], lib_bundle_folders: set[str]) -> set[str]:
    folders = set()
    for dest, _src in urls:
        folder = _nested_folder(dest, package)
        if (
            folder is not None
            and folder not in lib_bundle_folders
            and resource_extension(dest) in WEB_EXTENSIONS | WEB_DATA_EXTENSIONS
        ):
            folders.add(folder)
    return folders


def stays_in_lib(path: str, package: str, lib_bundle_folders: set[str], web_bundle_folders: set[str]) -> bool:
    if is_pacman_metadata(path):
        return True
    if resource_extension(path) in LIB_EXTENSIONS:
        return not is_load_module(path)
    folder = _nested_folder(path, package)
    if folder is None:
        return False
    return folder in lib_bundle_folders or folder not in web_bundle_folders


def lib_content_for_urls(package: str, urls: list[list[str]]) -> list[str]:
    valid_urls = [
        entry for entry in urls
        if isinstance(entry, (list, tuple)) and len(entry) == 2 and isinstance(entry[0], str)
    ]
    lib_bundle_folders = _lib_bundle_folders(package, valid_urls)
    web_bundle_folders = _web_bundle_folders(package, valid_urls, lib_bundle_folders)
    return [
        dest.lstrip("/")
        for dest, _src in valid_urls
        if stays_in_lib(dest, package, lib_bundle_folders, web_bundle_folders)
    ]


def _target_root(layout_roots: list[str], root: str) -> str:
    if root in layout_roots:
        return root
    for layout_root in layout_roots:
        if layout_root.startswith(f"{root}/"):
            return layout_root
    return root


def _layout_from_template(template_layout: dict) -> dict:
    layout = {}
    for target in template_layout:
        layout[target] = []
    return layout


def _web_data_resource(path: str, package: str, web_data_target: str, web_target: str) -> str:
    rel = package_layout_resource(path, package)
    if web_data_target == web_target:
        return f"{WEB_DATA_DIR}/{rel}"
    return rel


def layout_target_allowed(target: str, template_layout: dict) -> bool:
    if not isinstance(target, str) or not target.startswith("/") or ".." in Path(target).parts:
        return False
    for root in template_layout:
        root = root.rstrip("/")
        if target == root or target.startswith(f"{root}/"):
            return True
    return False


def layout_source_allowed(source: str) -> bool:
    return relative_path_allowed(source)


def layout_entry_target_path(target: str, source: str) -> str:
    return f"{target.rstrip('/')}/{source.lstrip('/')}"


def merge_pacman_layout(existing_layout: dict, generated_layout: dict, template_layout: dict) -> dict:
    if not isinstance(existing_layout, dict):
        existing_layout = {}
    merged = {
        target: list(sources)
        for target, sources in generated_layout.items()
    }
    generated_target_paths = {
        layout_entry_target_path(target, source)
        for target, sources in merged.items()
        for source in sources
    }

    for target, sources in existing_layout.items():
        if not layout_target_allowed(target, template_layout) or not isinstance(sources, list):
            continue
        merged_sources = []
        for source in sources:
            if not layout_source_allowed(source):
                continue
            target_path = layout_entry_target_path(target, source)
            if target_path not in generated_target_paths:
                continue
            for generated_target, generated_sources in merged.items():
                generated_sources[:] = [
                    generated_source for generated_source in generated_sources
                    if layout_entry_target_path(generated_target, generated_source) != target_path
                ]
            if target not in merged:
                merged[target] = []
            if source not in merged[target] and source not in merged_sources:
                merged_sources.append(source)
        if merged_sources:
            merged[target].extend(merged_sources)

    template_roots = set(template_layout)
    return {
        target: sources
        for target, sources in merged.items()
        if sources or target in template_roots
    }


def pacman_layout_for_urls(package: str, urls: list[list[str]], template_layout: dict) -> dict:
    layout_roots = list(template_layout)
    modules_target = _target_root(layout_roots, "/modules")
    web_target = _target_root(layout_roots, "/web")
    web_data_target = "/web/data" if "/web/data" in layout_roots else web_target
    data_target = _target_root(layout_roots, "/data")
    layout = _layout_from_template(template_layout)
    lib_bundle_folders = _lib_bundle_folders(package, urls)
    web_bundle_folders = _web_bundle_folders(package, urls, lib_bundle_folders)

    for dest, _src in urls:
        if is_pacman_metadata(dest):
            continue
        ext = resource_extension(dest)
        rel = package_layout_resource(dest, package)
        rel_parts = Path(rel).parts
        if ext in LIB_EXTENSIONS:
            if is_load_module(dest):
                layout[modules_target].append(dest)
        elif len(rel_parts) > 1 and rel_parts[0] in lib_bundle_folders:
            continue
        elif len(rel_parts) > 1 and rel_parts[0] in web_bundle_folders:
            layout[web_target].append(rel)
        elif len(rel_parts) > 1:
            continue
        elif ext in WEB_EXTENSIONS:
            layout[web_target].append(rel)
        elif ext in WEB_DATA_EXTENSIONS:
            layout[web_data_target].append(_web_data_resource(dest, package, web_data_target, web_target))
        else:
            layout[data_target].append(rel)
    return layout
