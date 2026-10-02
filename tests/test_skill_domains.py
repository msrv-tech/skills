import json
import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "skill-domains.json"
EXPECTED_SKILLS = {
    "access-and-navigation",
    "codex-test-bridge",
    "configuration",
    "database",
    "extension",
    "external-artifacts",
    "forms",
    "layouts",
    "metadata",
    "reports",
    "test-databases",
    "ui-testing",
    "web-publication",
}
REQUIRED_INFRASTRUCTURE_DIRS = {".git", ".github", "common", "docs", "tests"}
OPTIONAL_INFRASTRUCTURE_DIRS = {"temp", "codex-ui-test-fixtures"}


class SkillDomainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.skills = cls.manifest["skills"]

    def test_manifest_declares_only_thirteen_domain_skills(self):
        discovered = {path.parent.name for path in ROOT.glob("*/SKILL.md")}
        self.assertEqual(2, self.manifest["schemaVersion"])
        self.assertEqual(EXPECTED_SKILLS, set(self.skills))
        self.assertEqual(EXPECTED_SKILLS, discovered)

    def test_each_skill_has_valid_agent_metadata(self):
        for skill_name in sorted(self.skills):
            agent_file = ROOT / skill_name / "agents" / "openai.yaml"
            self.assertTrue(agent_file.is_file(), str(agent_file))
            agent = yaml.safe_load(agent_file.read_text(encoding="utf-8"))
            prompt = agent["interface"]["default_prompt"]
            self.assertIn(f"${skill_name}", prompt)

    def test_every_mode_route_and_script_resolves_inside_its_domain(self):
        for skill_name, skill in self.skills.items():
            skill_dir = ROOT / skill_name
            skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            for mode, route in skill["modes"].items():
                reference = skill_dir / route["reference"]
                self.assertTrue(reference.is_file(), str(reference))
                self.assertIn(route["reference"], skill_text)
                self.assertRegex(skill_text, rf"(?m)^\| `{re.escape(mode)}` \|")
                for relative_script in route["scripts"]:
                    script = skill_dir / relative_script
                    self.assertTrue(script.is_file(), str(script))
                    self.assertIn(relative_script, skill_text)
                    self.assertEqual(skill_dir, script.parents[1])

    def test_merged_evals_use_domain_name_and_declared_modes(self):
        for skill_name, skill in self.skills.items():
            eval_file = ROOT / skill_name / "evals" / "evals.json"
            if not eval_file.exists():
                continue
            payload = json.loads(eval_file.read_text(encoding="utf-8"))
            self.assertEqual(skill_name, payload["skill_name"])
            evals = payload["evals"]
            self.assertEqual(list(range(1, len(evals) + 1)), [item["id"] for item in evals])
            for item in evals:
                self.assertIn(item["mode"], skill["modes"])

    def test_no_legacy_operation_or_compatibility_entrypoints_remain(self):
        self.assertEqual([], list(ROOT.glob("*/OPERATION.md")))
        self.assertFalse((ROOT / "scripts" / "sync-skill-domains.py").exists())
        top_level_dirs = {path.name for path in ROOT.iterdir() if path.is_dir()}
        required = EXPECTED_SKILLS | REQUIRED_INFRASTRUCTURE_DIRS
        self.assertTrue(required <= top_level_dirs)
        self.assertTrue(top_level_dirs <= required | OPTIONAL_INFRASTRUCTURE_DIRS)
        for skill_name in self.skills:
            text = (ROOT / skill_name / "SKILL.md").read_text(encoding="utf-8")
            self.assertNotIn("OPERATION.md", text)
            self.assertNotRegex(text, r"\.\./[^/]+/(?:scripts|SKILL\.md)")

    def test_python_entrypoints_do_not_shadow_standard_library_modules(self):
        self.assertEqual([], list(ROOT.glob("*/scripts/inspect.py")))

    def test_relative_markdown_links_resolve(self):
        roots = [ROOT / name for name in EXPECTED_SKILLS] + [ROOT / "docs"]
        for base in roots:
            for markdown in base.rglob("*.md"):
                if "node_modules" in markdown.parts:
                    continue
                text = markdown.read_text(encoding="utf-8")
                for match in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", text):
                    target = match.group(1).strip().split("#", 1)[0]
                    if not target or "://" in target or target.startswith(("mailto:", "<")):
                        continue
                    self.assertTrue((markdown.parent / target).exists(), f"{markdown}: {target}")

    def test_documented_script_paths_resolve(self):
        for skill_name in EXPECTED_SKILLS:
            for document in (ROOT / skill_name).rglob("*"):
                if not document.is_file() or "node_modules" in document.parts:
                    continue
                try:
                    text = document.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                self.assertNotIn("OPERATION.md", text, str(document))
                for match in re.finditer(r"<skills-root>/([^/\s]+)/scripts/([^\s\"'`;]+)", text):
                    domain, script_name = match.groups()
                    self.assertIn(domain, EXPECTED_SKILLS, f"{document}: {match.group(0)}")
                    self.assertTrue((ROOT / domain / "scripts" / script_name).is_file(), f"{document}: {match.group(0)}")
                for match in re.finditer(r"(?:<skills-root>|skills)\\([^\\\s]+)\\scripts\\([^\s\"'`;]+)", text):
                    domain, script_name = match.groups()
                    self.assertIn(domain, EXPECTED_SKILLS, f"{document}: {match.group(0)}")
                    self.assertTrue((ROOT / domain / "scripts" / script_name).is_file(), f"{document}: {match.group(0)}")


if __name__ == "__main__":
    unittest.main()
