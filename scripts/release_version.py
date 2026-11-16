"""For the release workflow.

python scripts/release_version.py          -> [project].version from pyproject.toml
python scripts/release_version.py notes V  -> the CHANGELOG.md section for version V
"""

import re
import sys
from pathlib import Path

import tomllib


def version() -> str:
    with Path("pyproject.toml").open("rb") as f:
        return tomllib.load(f)["project"]["version"]


def notes(v: str) -> str:
    text = Path("CHANGELOG.md").read_text(encoding="utf-8")
    m = re.search(rf"^## \[{re.escape(v)}\][^\n]*\n(.*?)(?=^## \[|\Z)", text, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m and m.group(1).strip() else "See CHANGELOG.md."


if __name__ == "__main__":
    print(notes(sys.argv[2]) if sys.argv[1:2] == ["notes"] else version())
