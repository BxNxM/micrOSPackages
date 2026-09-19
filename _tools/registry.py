"""Generate the package catalogue while preserving editable descriptions."""

import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

from .create_package import GITHUB_BASE
from .package_rules import package_name_allowed
from .validate import find_all_packages


def _git_output(repo_root, *args):
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _github_base(remote_url):
    if remote_url.startswith("git@github.com:"):
        remote_url = "ssh://git@github.com/" + remote_url.split(":", 1)[1]
    try:
        url = urlsplit(remote_url)
        if url.scheme not in ("https", "http", "ssh", "git") or url.hostname != "github.com":
            return None
        if url.query or url.fragment:
            return None
        path = url.path.strip("/")
        if path.endswith(".git"):
            path = path[:-4]
        if re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+", path):
            return f"github:{path}"
    except ValueError:
        pass
    return None


def detect_github_base(repo_root):
    """Use the branch's upstream remote, then origin, then the default base."""
    # Do not accidentally use the parent checkout for an unversioned package tree.
    top = _git_output(repo_root, "rev-parse", "--show-toplevel")
    if not top or Path(top).resolve() != Path(repo_root).resolve():
        return GITHUB_BASE
    branch = _git_output(repo_root, "symbolic-ref", "--quiet", "--short", "HEAD")
    upstream = _git_output(repo_root, "config", "--get", f"branch.{branch}.remote") if branch else ""
    remotes = [upstream] if upstream and upstream != "." else []
    if "origin" not in remotes:
        remotes.append("origin")
    for remote in remotes:
        base = _github_base(_git_output(repo_root, "remote", "get-url", "--", remote))
        if base:
            return base
    return GITHUB_BASE


def update_registry(repo_root):
    """Refresh registry.json from all available package manifests."""
    registry_path = Path(repo_root) / "registry.json"
    descriptions = {}
    if registry_path.exists():
        existing = json.loads(registry_path.read_text(encoding="utf-8"))
        if not isinstance(existing, list):
            raise ValueError(f"Expected a package list in {registry_path}")
        for entry in existing:
            if (not isinstance(entry, dict)
                    or not isinstance(entry.get("description", ""), str)):
                raise ValueError(f"Invalid registry entry in {registry_path}")
            # Accept the old name field when migrating existing registries.
            name = entry.get("name")
            if name is None:
                ref = entry.get("ref")
                name = ref.rsplit("/", 1)[-1] if isinstance(ref, str) and "/" in ref else None
            if not isinstance(name, str) or not package_name_allowed(name):
                raise ValueError(f"Invalid registry entry in {registry_path}")
            descriptions[name] = entry.get("description", "")

    github_base = detect_github_base(repo_root)
    registry = []
    for package in find_all_packages(repo_root):
        package_path = Path(package)
        manifest = json.loads((package_path / "package.json").read_text(encoding="utf-8"))
        registry.append({
            "version": manifest.get("version", "0.0.0"),
            "ref": f"{github_base}/{package_path.name}",
            "description": descriptions.get(package_path.name, ""),
        })

    registry_path.write_text(json.dumps(registry, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"✅Updated: {registry_path} ({len(registry)} packages)")
