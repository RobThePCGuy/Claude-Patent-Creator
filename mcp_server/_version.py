"""The package version, with pyproject.toml as the one place it is set.

Apps that install these tools (Patent Creator Studio among them) compare this
number to decide whether an installed copy is current, so it must describe
the code that is actually running:

- From a source checkout (an editable install, or running the repo's files
  directly) it reads the checkout's own pyproject.toml, because an editable
  install's recorded metadata keeps the version it had when installed.
- From an ordinary install it reads the installed package's metadata.

Callers load this file by its path next to them (see load_version), never by
module name, so a different copy elsewhere on sys.path cannot answer.
"""

import re
from pathlib import Path

PACKAGE_NAME = "claude-patent-creator"


def _project_version(text: str):
    """[project].version from pyproject.toml text, when [project].name is ours."""
    try:
        import tomllib  # Python 3.11+

        project = tomllib.loads(text).get("project", {})
        if project.get("name") == PACKAGE_NAME and isinstance(project.get("version"), str):
            return project["version"]
        return None
    except ImportError:
        pass
    except Exception:
        return None
    # Python 3.10: read only the [project] table, by hand.
    section = re.search(r"^\[project\]\s*(?:#[^\n]*)?$(.*?)(?=^\s*\[|\Z)", text, re.MULTILINE | re.DOTALL)
    if not section:
        return None
    body = section.group(1)

    def key(name):
        m = re.search(rf"""^\s*{name}\s*=\s*(["'])([^"']*)\1""", body, re.MULTILINE)
        return m.group(2) if m else None

    return key("version") if key("name") == PACKAGE_NAME else None


def version_for(package_dir: Path) -> str:
    """The version of the copy of the package in package_dir."""
    pyproject = Path(package_dir).resolve().parent / "pyproject.toml"
    try:
        found = _project_version(pyproject.read_text(encoding="utf-8"))
        if found:
            return found
    except OSError:
        pass
    try:
        from importlib.metadata import distribution

        dist = distribution(PACKAGE_NAME)
        # Only trust metadata that records this very copy of the package. A
        # checkout run beside an older install must not report the install's
        # version, so metadata that records its files somewhere else, or no
        # files at all, does not count.
        init = next(
            (f for f in (dist.files or []) if str(f).replace("\\", "/") == "mcp_server/__init__.py"), None
        )
        if init is not None and Path(dist.locate_file(init)).resolve().parent == Path(package_dir).resolve():
            return dist.version
    except Exception:
        pass
    return "0+unknown"


def load_version(caller_file: str) -> str:
    """Version of the package copy that caller_file belongs to."""
    return version_for(Path(caller_file).resolve().parent)


__version__ = load_version(__file__)
