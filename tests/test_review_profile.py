import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin/review-profile"
loader = importlib.machinery.SourceFileLoader("review_profile", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)


class Resolve(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="review-profile-test-")
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.root = base / "profiles"
        self.prompts = self.root / "prompts"
        self.prompts.mkdir(parents=True)
        self.skill_dirs = [base / "claude", base / "agents"]
        for directory in self.skill_dirs:
            self.add_skill(directory, "rubric")
        self.base = base
        self.env = {**os.environ, "REVIEW_PROFILE_ROOT": str(self.root),
                    "REVIEW_PROFILE_SKILL_DIRS": ":".join(map(str, self.skill_dirs)),
                    "PYTHONDONTWRITEBYTECODE": "1"}

    def add_skill(self, directory, name):
        (directory / name).mkdir(parents=True)
        (directory / name / "SKILL.md").write_text(f"# {name}\n")

    def write(self, config):
        text = config if isinstance(config, str) else json.dumps(config)
        (self.root / "profiles.json").write_text(text)

    def run_script(self, *args):
        return subprocess.run([str(SCRIPT), *args], env=self.env, text=True,
                              capture_output=True, timeout=15)

    def resolve(self, *args):
        result = self.run_script(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return result.stdout.splitlines()

    def reject(self, *args):
        result = self.run_script(*args)
        self.assertEqual(result.returncode, module.EX_POLICY, result.stdout)
        self.assertEqual(result.stdout, "")
        lines = result.stderr.splitlines()
        self.assertEqual(len(lines), 1, result.stderr)
        self.assertTrue(lines[0].startswith("review-profile: "), lines[0])
        return lines[0]

    def test_exact_match(self):
        (self.prompts / "rules.md").write_text("Check the rules.\n")
        self.write({"octo/*": {"skills": [], "files": []},
                    "octo/repo": {"skills": ["rubric"], "files": ["rules.md"]},
                    "default": {"skills": [], "files": []}})
        self.assertEqual(self.resolve("octo/repo"),
                         ["profile: octo/repo", "skill: rubric",
                          f"file: {(self.prompts / 'rules.md').resolve()}"])

    def test_first_glob_in_file_order_wins(self):
        self.write({"octo/re*": {"skills": ["rubric"], "files": []},
                    "octo/*": {"skills": [], "files": []},
                    "default": {"skills": [], "files": []}})
        self.assertEqual(self.resolve("octo/repo"), ["profile: octo/re*", "skill: rubric"])

    def test_mixed_case_input_is_lowercased(self):
        self.write({"octo/repo": {"skills": [], "files": []},
                    "default": {"skills": [], "files": []}})
        self.assertEqual(self.resolve("Octo/RePo"), ["profile: octo/repo"])

    def test_fallback_to_default(self):
        self.write({"octo/repo": {"skills": [], "files": []},
                    "default": {"skills": ["rubric"], "files": []}})
        self.assertEqual(self.resolve("other/thing"), ["profile: default", "skill: rubric"])

    def test_missing_default(self):
        self.write({"octo/repo": {"skills": [], "files": []}})
        self.assertIn("no default profile", self.reject("octo/repo"))

    def test_uppercase_glob(self):
        self.write({"Octo/*": {"skills": [], "files": []},
                    "default": {"skills": [], "files": []}})
        self.assertIn("uppercase", self.reject("octo/repo"))

    def test_uppercase_exact_key(self):
        self.write({"octo/Repo": {"skills": [], "files": []},
                    "default": {"skills": [], "files": []}})
        self.assertIn("uppercase", self.reject("other/thing"))

    def test_parent_file_rejected(self):
        (self.root / "outside.md").write_text("outside\n")
        self.write({"default": {"skills": [], "files": ["../outside.md"]}})
        self.reject("octo/repo")

    def test_symlink_escaping_prompts(self):
        (self.root / "outside.md").write_text("outside\n")
        (self.prompts / "link.md").symlink_to(self.root / "outside.md")
        self.write({"default": {"skills": [], "files": ["link.md"]}})
        self.assertIn("outside", self.reject("octo/repo"))

    def test_missing_file(self):
        self.write({"default": {"skills": [], "files": ["absent.md"]}})
        self.assertIn("missing", self.reject("octo/repo"))

    def test_skill_that_is_a_path(self):
        self.write({"default": {"skills": ["nested/rubric"], "files": []}})
        self.assertIn("plain name", self.reject("octo/repo"))

    def test_skill_missing_from_one_present_dir(self):
        self.add_skill(self.skill_dirs[0], "partial")
        self.write({"default": {"skills": ["partial"], "files": []}})
        self.assertIn(str(self.skill_dirs[1]), self.reject("octo/repo"))

    def test_absent_skill_dir_is_skipped(self):
        absent = self.base / "pi"
        self.env["REVIEW_PROFILE_SKILL_DIRS"] = ":".join(map(str, [*self.skill_dirs, absent]))
        self.write({"default": {"skills": ["rubric"], "files": []}})
        self.assertEqual(self.resolve("octo/repo"), ["profile: default", "skill: rubric"])

    def test_prompt_files_over_cap(self):
        half = module.PROMPT_CAP // 2
        (self.prompts / "one.md").write_text("a" * half)
        (self.prompts / "two.md").write_text("b" * (half + 1))
        self.write({"default": {"skills": [], "files": ["one.md", "two.md"]}})
        self.assertIn("cap", self.reject("octo/repo"))

    def test_malformed_json(self):
        self.write('{"default": {"skills": [], "files": []}')
        self.assertIn("bad JSON", self.reject("octo/repo"))

    def test_bad_usage(self):
        self.write({"default": {"skills": [], "files": []}})
        self.assertIn("usage", self.reject())
        self.assertIn("usage", self.reject("octo/repo", "extra"))
        self.assertIn("owner/repo", self.reject("not-a-repo"))


if __name__ == "__main__":
    unittest.main()
