#!/usr/bin/env python3
"""Run repository checks without an agent CLI, model downloads, or GPU access."""

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".git", ".venv", ".lux", ".tools", "vendor", "models", "outputs", "node_modules", "__pycache__"}
# Character class keeps the retired name out of maintained source text.
RETIRED_BRAND = re.compile(r"s[u]no", re.IGNORECASE)


def project_files(root: Path) -> list[Path]:
    """Include tracked and new nonignored files, or use a source archive's tree."""
    git = shutil.which("git")
    result = subprocess.run(
        [git, "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        capture_output=True,
    ) if git and (root / ".git").exists() else None
    if result and result.returncode == 0:
        paths = {root / name.decode() for name in result.stdout.split(b"\0") if name}
    else:
        # Prune generated directories before traversing them in a source archive.
        import os
        paths = set()
        for folder, directories, files in os.walk(root):
            directories[:] = [d for d in directories if d not in EXCLUDED]
            paths.update(Path(folder) / name for name in files)
    return sorted(p for p in paths if p.is_file() and not EXCLUDED.intersection(p.relative_to(root).parts))


def check_branding(root: Path, files: list[Path]) -> None:
    hits = []
    for path in files:
        relative = path.relative_to(root)
        if RETIRED_BRAND.search(str(relative)):
            hits.append(str(relative))
        payload = path.read_bytes()
        if b"\0" not in payload:
            for line, text in enumerate(payload.decode("utf-8", errors="replace").splitlines(), 1):
                if RETIRED_BRAND.search(text):
                    hits.append(f"{relative}:{line}")
    if hits:
        raise ValueError("Retired branding remains in: " + ", ".join(hits))


def check_metadata(root: Path) -> None:
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    lock = tomllib.loads((root / "uv.lock").read_text())
    editable = [p for p in lock["package"] if p.get("source") == {"editable": "."}]
    if project["name"] != "lux-in-music" or len(editable) != 1:
        raise ValueError("Expected one editable lux-in-music package")
    if (editable[0]["name"], editable[0]["version"]) != (project["name"], project["version"]):
        raise ValueError("Project and editable lock package identities differ")
    if lock["requires-python"] != project["requires-python"]:
        raise ValueError("Project and lock Python requirements differ")
    if project["scripts"].get("studio-gen") != "studio.cli:main":
        raise ValueError("The generation CLI entry point is missing")


def check_bridges(root: Path) -> None:
    for name in ("CLAUDE.md", "GEMINI.md", ".github/copilot-instructions.md"):
        text = (root / name).read_text()
        if "AGENTS.md" not in text or len(text.splitlines()) > 4:
            raise ValueError(f"{name} must be a small bridge to AGENTS.md")
    for name in ("AGENTS.md", "CONTRIBUTING.md", "docs/architecture.md", "docs/harness.md", "docs/progress.md"):
        if not (root / name).read_text().strip():
            raise ValueError(f"Missing contributor context: {name}")


def read_requirements(root: Path) -> list[dict]:
    ledger = json.loads((root / "harness/requirements.json").read_text())
    if ledger.get("schema_version") != 1 or not ledger.get("requirements"):
        raise ValueError("Unsupported or empty requirement ledger")
    ids = set()
    for item in ledger["requirements"]:
        required = {"id", "issue", "description", "status", "tests", "acceptance"}
        if required - item.keys() or item["id"] in ids:
            raise ValueError("Missing fields or duplicate requirement ID")
        ids.add(item["id"])
        if item["status"] not in {"planned", "implemented"}:
            raise ValueError(f"Invalid requirement status: {item['id']}")
        if not item["issue"].startswith("https://github.com/lvxworld/lux-in-music/issues/"):
            raise ValueError(f"Missing project issue link: {item['id']}")
        if not isinstance(item["acceptance"], list) or not item["acceptance"] or not all(
            isinstance(step, str) and step.strip() for step in item["acceptance"]
        ):
            raise ValueError(f"Missing acceptance scenarios: {item['id']}")
        if not isinstance(item["tests"], list) or not all(
            isinstance(test, str) and test.startswith("tests.") for test in item["tests"]
        ):
            raise ValueError(f"Invalid test selectors: {item['id']}")
        if item["status"] == "implemented" and not item["tests"]:
            raise ValueError(f"Implemented requirement has no verification: {item['id']}")
    return ledger["requirements"]


def check_syntax(files: list[Path]) -> None:
    for path in files:
        if path.suffix == ".py":
            ast.parse(path.read_text(), filename=str(path))
    for suffixes, command in (({".js"}, ["node", "--check"]), ({".sh", ".command"}, ["bash", "-n"])):
        if not shutil.which(command[0]):
            raise ValueError(f"Install {command[0]} to run syntax checks")
        for path in files:
            if path.suffix in suffixes:
                result = subprocess.run([*command, str(path)], capture_output=True, text=True)
                if result.returncode:
                    raise ValueError(result.stderr.strip() or f"Invalid syntax: {path}")


def run_tests(names: list[str]) -> None:
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromNames(names)
    if not suite.countTestCases() or loader.errors:
        raise ValueError("Missing or empty verification tests: " + "; ".join(loader.errors))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful() or result.skipped:
        raise ValueError("Verification failed or skipped required tests")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="also run offline application checks")
    parser.add_argument("--require-complete", action="store_true", help="fail if any product requirement is planned; implies --full")
    parser.add_argument("--report", type=Path, help="write a JSON verification report")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    report = {"checks": [], "requirements": [], "application_checks": args.full or args.require_complete}
    failed = False
    files = project_files(ROOT)
    checks = [
        ("Project branding", lambda: check_branding(ROOT, files)),
        ("Package and lock metadata", lambda: check_metadata(ROOT)),
        ("Shared instructions and bridges", lambda: check_bridges(ROOT)),
        ("Python, JavaScript, and shell syntax", lambda: check_syntax(files)),
        ("Harness regression tests", lambda: run_tests(["tests.test_harness", "tests.test_release_ci"])),
    ]
    for name, check in checks:
        try:
            check()
            report["checks"].append({"name": name, "passed": True})
            print(f"PASS {name}", flush=True)
        except Exception as error:
            failed = True
            report["checks"].append({"name": name, "passed": False, "error": str(error)})
            print(f"FAIL {name}: {error}", flush=True)
    try:
        report["requirements"] = read_requirements(ROOT)
        print("PASS Requirement ledger", flush=True)
        if report["application_checks"]:
            # Run available checks for planned work too, without promoting its
            # status. Audio/listening acceptance still lives in the ledger.
            loader = unittest.TestLoader()
            selectors = []
            for item in report["requirements"]:
                if item["tests"]:
                    suite = loader.loadTestsFromNames(item["tests"])
                    if loader.errors or not suite.countTestCases():
                        raise ValueError(f"Cannot verify requirement {item['id']}: {loader.errors}")
                    selectors.extend(item["tests"])
            run_tests(list(dict.fromkeys([*selectors, "tests.test_app.RequestBoundaryTests", "tests.test_vibe",
                                          "tests.test_edit"])))
            for item in report["requirements"]:
                if item["status"] == "implemented":
                    report["checks"].append({"name": item["id"], "passed": True})
            report["checks"].append({"name": "Offline request boundary tests", "passed": True})
            print("PASS Offline application checks", flush=True)
        for item in report["requirements"]:
            if item["status"] == "planned":
                print(f"PLANNED {item['id']} ({item['issue']})", flush=True)
        if args.require_complete and any(i["status"] == "planned" for i in report["requirements"]):
            raise ValueError("Product readiness failed: planned requirements remain")
    except Exception as error:
        failed = True
        report["checks"].append({"name": "Requirements/application verification", "passed": False, "error": str(error)})
        print(f"FAIL Requirements/application verification: {error}", flush=True)
    report["passed"] = not failed
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print("Checks failed." if failed else "Checks passed. Planned requirements are not verified product behavior.")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
