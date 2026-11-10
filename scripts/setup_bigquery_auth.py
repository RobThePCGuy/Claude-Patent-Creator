#!/usr/bin/env python3
"""Sign in to Google for the optional BigQuery patent search.

This hands off to Google's own `gcloud auth application-default login`,
which opens a browser and saves Application Default Credentials. (An earlier
version ran its own OAuth flow with placeholder client credentials, which
could never sign anyone in.)

Usage:
    python scripts/setup_bigquery_auth.py [your-project-id]
"""

import shutil
import subprocess
import sys
from pathlib import Path

INSTALL_URL = "https://cloud.google.com/sdk/docs/install"


def _cli() -> str:
    folder = Path(sys.executable).absolute().parent
    for name in ("patent-creator", "patent-creator.exe"):
        if (folder / name).exists():
            return str(folder / name)
    return "patent-creator"


def main() -> int:
    gcloud = shutil.which("gcloud")
    if not gcloud:
        print("BigQuery sign-in needs Google's gcloud tool, which isn't installed.")
        print(f"Install it from {INSTALL_URL}, open a new terminal, and run this again.")
        return 1

    project = sys.argv[1] if len(sys.argv) > 1 else ""
    cmd = [gcloud, "auth", "application-default", "login"]
    if project:
        cmd += ["--project", project]
    print("Opening your browser to sign in to Google...")
    if subprocess.call(cmd) != 0:
        print("Sign-in did not finish. Run this again when you're ready.")
        return 1

    cli = _cli()
    if project:
        subprocess.call([cli, "config", "set", "GOOGLE_CLOUD_PROJECT", project])
    else:
        print(f'\nNow save your project ID: {cli} config set GOOGLE_CLOUD_PROJECT your-project-id')
    print(f"Then test it: {cli} check-bigquery")
    return 0


if __name__ == "__main__":
    sys.exit(main())
