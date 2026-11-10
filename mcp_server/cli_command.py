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


_BARE_PIP = re.compile(r"(?<![\w/\\.-])(?<!-m )pip(?= install)")


def python_command() -> str:
    exe = str(Path(sys.executable).absolute())
    return f'"{exe}"' if " " in exe else exe


def render(message: str) -> str:
    """Make every command in an instruction one that runs from this install.

    Bare ``patent-creator <subcommand>`` becomes the installed executable, and
    bare ``pip install`` becomes ``<this python> -m pip install`` (a bare pip
    in an unactivated venv installs into a different Python).
    """
    pip = f"{python_command()} -m pip"
    message = _BARE_PIP.sub(lambda _m: pip, message)
    cmd = installed_cli()
    if cmd == "patent-creator":
        return message
    return _BARE.sub(lambda _m: cmd, message)
