"""The exact ``patent-creator`` command for this install.

The README installs into a virtual environment that is never activated, so a
bare ``patent-creator ...`` in an instruction fails with "command not found".
Anything that tells a person which command to run renders it through here.
The console script sits next to the interpreter that is running.
"""

import re
import shutil
import sys
from pathlib import Path

_BARE = re.compile(r"(?<![\w/\\.-])patent-creator(?= )")


def installed_cli() -> str:
    folder = Path(sys.executable).absolute().parent
    for name in ("patent-creator", "patent-creator.exe"):
        candidate = folder / name
        if candidate.exists():
            text = str(candidate)
            if shutil.which("patent-creator") == text:
                return "patent-creator"
            return f'"{text}"' if " " in text else text
    return "patent-creator"


def render(message: str) -> str:
    """Replace each bare ``patent-creator <subcommand>`` with the real command."""
    cmd = installed_cli()
    if cmd == "patent-creator":
        return message
    return _BARE.sub(lambda _m: cmd, message)
