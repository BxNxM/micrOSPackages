import contextlib
import io
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from _tools.registry import _github_base, detect_github_base, update_registry


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.registry = self.root / "registry.json"

    def package(self, name, version="1.0.0"):
        folder = self.root / name
        (folder / "package").mkdir(parents=True, exist_ok=True)
        (folder / "package.json").write_text(json.dumps({"version": version}))

    def generate(self):
        with contextlib.redirect_stdout(io.StringIO()):
            update_registry(self.root)
        return json.loads(self.registry.read_text())

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args],
                              check=True, capture_output=True, text=True).stdout.strip()

    def test_github_remote_url_formats(self):
        for url in ("https://github.com/owner/packages.git",
                    "git@github.com:owner/packages.git",
                    "ssh://git@github.com/owner/packages.git",
                    "https://github.com/owner/packages/"):
            with self.subTest(url=url):
                self.assertEqual(_github_base(url), "github:owner/packages")
        for url in ("", "/local/repo", "https://gitlab.com/owner/packages.git",
                    "https://github.com/owner", "https://github.com/owner/repo/tree/main",
                    "https://github.com.evil/owner/repo.git"):
            with self.subTest(url=url):
                self.assertIsNone(_github_base(url))

    def test_upstream_then_origin_then_default_and_preserved_description(self):
        self.git("init")
        self.git("remote", "add", "origin", "https://github.com/fork/packages.git")
        self.git("remote", "add", "source", "git@github.com:upstream/packages.git")
        branch = self.git("symbolic-ref", "--short", "HEAD")
        self.git("config", f"branch.{branch}.remote", "source")
        self.git("config", f"branch.{branch}.merge", "refs/heads/main")
        self.package("alpha")
        self.registry.write_text(json.dumps([
            {"description": "Keep this description.", "ref": "github:old/repo/alpha"}
        ]))
        entry = self.generate()[0]
        self.assertEqual(entry["ref"], "github:upstream/packages/alpha")
        self.assertEqual(entry["description"], "Keep this description.")
        self.git("config", "--unset", f"branch.{branch}.remote")
        self.assertEqual(detect_github_base(self.root), "github:fork/packages")
        self.git("remote", "set-url", "origin", "https://gitlab.com/fork/packages.git")
        self.assertEqual(detect_github_base(self.root), "github:BxNxM/micrOSPackages")

    def test_detached_head_uses_origin_and_nested_tree_ignores_parent(self):
        self.git("init")
        self.git("remote", "add", "origin", "https://github.com/fork/packages.git")
        self.git("-c", "user.name=Registry Test", "-c", "user.email=test@example.com",
                 "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-m", "Test fixture")
        self.git("checkout", "--detach")
        self.assertEqual(detect_github_base(self.root), "github:fork/packages")
        nested = self.root / "nested"
        nested.mkdir()
        self.assertEqual(detect_github_base(nested), "github:BxNxM/micrOSPackages")

    def test_missing_git_uses_default(self):
        with patch("_tools.registry.subprocess.run", side_effect=FileNotFoundError):
            self.assertEqual(detect_github_base(self.root), "github:BxNxM/micrOSPackages")

    def test_discovers_all_packages_in_name_order(self):
        self.package("zebra", "2.0.0")
        self.package("alpha")
        (self.root / "not_a_package").mkdir()
        self.assertEqual(self.generate(), [
            {"version": "1.0.0", "ref": "github:BxNxM/micrOSPackages/alpha", "description": ""},
            {"version": "2.0.0", "ref": "github:BxNxM/micrOSPackages/zebra", "description": ""},
        ])

    def test_preserves_edits_while_refreshing_versions_and_membership(self):
        self.package("alpha")
        self.package("removed")
        entries = self.generate()
        entries[0]["description"] = "Editable café description\nwith another line"
        self.registry.write_text(json.dumps(entries))
        self.package("alpha", "1.1.0")
        self.package("new")
        shutil.rmtree(self.root / "removed")
        self.assertEqual(self.generate(), [
            {"version": "1.1.0", "ref": "github:BxNxM/micrOSPackages/alpha", "description": entries[0]["description"]},
            {"version": "1.0.0", "ref": "github:BxNxM/micrOSPackages/new", "description": ""},
        ])
        previous = self.registry.read_bytes()
        self.generate()
        self.assertEqual(self.registry.read_bytes(), previous)

    def test_migrates_named_entries_without_losing_descriptions(self):
        self.package("alpha")
        for ref in (None, "github:old/repo/alpha"):
            with self.subTest(ref=ref):
                old = {"name": "alpha", "description": "Keep this description."}
                if ref is not None:
                    old["ref"] = ref
                self.registry.write_text(json.dumps([old]))
                entry = self.generate()[0]
                self.assertNotIn("name", entry)
                self.assertEqual(entry["description"], old["description"])
                self.assertEqual(entry["ref"], "github:BxNxM/micrOSPackages/alpha")

    def test_invalid_inputs_do_not_overwrite_registry(self):
        self.package("alpha")
        for content in ("broken json", "{}", '[{"name": "alpha", "description": null}]',
                        '[{"description": "Missing ref"}]', '[{"ref": null}]',
                        '[{"ref": "github:owner/repo/"}]'):
            with self.subTest(content=content):
                self.registry.write_text(content)
                with self.assertRaises(ValueError):
                    self.generate()
                self.assertEqual(self.registry.read_text(), content)
        self.registry.write_text('[]')
        (self.root / "alpha" / "package.json").write_text("broken json")
        with self.assertRaises(ValueError):
            self.generate()
        self.assertEqual(self.registry.read_text(), '[]')

    def test_single_and_all_update_actions_refresh_full_registry(self):
        tools_path = Path(__file__).resolve().parents[2] / "tools.py"
        self.package("alpha")
        self.package("beta")
        for target in ("alpha", "ALL"):
            with self.subTest(target=target):
                if self.registry.exists():
                    self.registry.unlink()
                with patch("_tools.create_package.REPO_ROOT", self.root), \
                        patch("sys.argv", [str(tools_path), "--update", target]), \
                        contextlib.redirect_stdout(io.StringIO()):
                    runpy.run_path(str(tools_path), run_name="__main__")
                entries = json.loads(self.registry.read_text())
                self.assertTrue(all("name" not in entry for entry in entries))
                self.assertEqual([entry["ref"] for entry in entries],
                                 ["github:BxNxM/micrOSPackages/alpha", "github:BxNxM/micrOSPackages/beta"])


if __name__ == "__main__":
    unittest.main()
