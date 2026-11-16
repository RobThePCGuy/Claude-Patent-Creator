"""CI: the package version must rise whenever the installed code changes,
and must never fall.

Apps that install these tools decide whether an installed copy is current by
comparing versions, so a change that ships without a higher version leaves
every existing install looking current.

Usage: python scripts/check_package_version.py BASE_REF
"""

import subprocess
import sys
from pathlib import Path

import tomllib
from packaging.version import InvalidVersion, Version

INSTALLED = ("mcp_server/", "setup.py", "MANIFEST.in")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def packaging_inputs(doc: dict) -> dict:
    """Everything in pyproject.toml that decides what gets installed: the
    [project] table except the version itself, [build-system], and the
    build backend's own [tool.setuptools] settings (package finding,
    package data). Lint, test and type-checker settings are left out."""
    project = {k: v for k, v in doc.get("project", {}).items() if k != "version"}
    tools = {k: v for k, v in doc.get("tool", {}).items() if k.startswith("setuptools")}
    return {"project": project, "build-system": doc.get("build-system"), "tool": tools}


def main(base: str) -> int:
    old_doc = tomllib.loads(git("show", f"{base}:pyproject.toml"))
    with Path("pyproject.toml").open("rb") as f:
        new_doc = tomllib.load(f)
    old_project, new_project = old_doc.get("project", {}), new_doc.get("project", {})
    try:
        old, new = Version(old_project["version"]), Version(new_project["version"])
    except (KeyError, InvalidVersion) as e:
        print(f"::error::pyproject.toml [project].version is missing or not a valid version: {e}")
        return 1

    changed = [p for p in git("diff", "--name-only", f"{base}...HEAD").splitlines() if p.startswith(INSTALLED)]
    deps_changed = packaging_inputs(old_doc) != packaging_inputs(new_doc)

    if new < old:
        print(f"::error::pyproject.toml version went down ({old} -> {new}). Versions only rise.")
        return 1
    if not changed and not deps_changed:
        print(f"Installed code unchanged ({old} -> {new}); guard passes.")
        return 0
    if new > old:
        print(f"Installed code changed and version raised {old} -> {new}; guard passes.")
        return 0
    what = ", ".join(changed[:5]) or "the packaging settings in pyproject.toml"
    print(f"::error::Installed code changed ({what}) but the version is still {old}.")
    print("Raise [project].version in pyproject.toml and add a CHANGELOG section,"
          " so installed copies can tell they are out of date.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
