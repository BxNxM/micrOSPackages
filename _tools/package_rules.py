from pathlib import Path

WEB_EXTENSIONS = {"js", "html", "css"}
WEB_DATA_EXTENSIONS = {"png", "jpeg", "ico", "gif"}
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


def web_layout_resource(path: str, package: str) -> str:
    rel = Path(strip_package_prefix(path, package))
    return rel.as_posix()


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
    rel = web_layout_resource(path, package)
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
    if not isinstance(source, str) or source.startswith("/"):
        return False
    return ".." not in Path(source).parts


def layout_entry_target_path(target: str, source: str) -> str:
    return f"{target.rstrip('/')}/{source.lstrip('/')}"


def merge_pacman_layout(existing_layout: dict, generated_layout: dict, template_layout: dict) -> dict:
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
        if not layout_target_allowed(target, template_layout):
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

    for dest, _src in urls:
        if dest.endswith("pacman.json"):
            continue
        ext = dest.rsplit(".", 1)[-1] if "." in dest else ""
        if dest.endswith("py"):
            if "LM_" in dest:
                layout[modules_target].append(dest)
        elif ext in WEB_EXTENSIONS:
            layout[web_target].append(web_layout_resource(dest, package))
        elif ext in WEB_DATA_EXTENSIONS:
            layout[web_data_target].append(_web_data_resource(dest, package, web_data_target, web_target))
        else:
            layout[data_target].append(dest)
    return layout
