#!/usr/bin/env python3
"""
Cross-platform Graphviz installer and helper
Automatically detects and helps install Graphviz on Windows, macOS, and Linux
"""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


class GraphvizInstaller:
    """Detect, install, and configure Graphviz across platforms"""

    def __init__(self):
        self.system = platform.system()
        self.status = self.check_installation()

    def check_installation(self) -> dict[str, Any]:
        """
        Check if Graphviz is properly installed

        Returns:
            Dict with installation status details
        """
        status = {
            "python_package": False,
            "system_binary": False,
            "dot_executable": None,
            "version": None,
            "ready": False,
            "platform": self.system,
        }

        # Check Python package
        try:
            import importlib.util

            if importlib.util.find_spec("graphviz") is not None:
                status["python_package"] = True
        except (ImportError, ValueError):
            pass

        # Check system binary
        dot_path = shutil.which("dot")
        if dot_path:
            status["system_binary"] = True
            status["dot_executable"] = dot_path

            # Get version
            try:
                result = subprocess.run(["dot", "-V"], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    # Version is in stderr like "dot - graphviz version 2.43.0"
                    import re

                    version_match = re.search(r"version (\d+\.\d+\.\d+)", result.stderr)
                    if version_match:
                        status["version"] = version_match.group(1)
            except Exception:
                pass

        status["ready"] = status["python_package"] and status["system_binary"]
        return status

    def get_installation_instructions(self) -> str:
        """
        Get platform-specific installation instructions

        Returns:
            Formatted installation instructions
        """
        if self.status["ready"]:
            return "[OK] Graphviz is already installed and ready!"

        instructions = []

        if not self.status["python_package"]:
            instructions.append("1. Install Python graphviz package:")
            instructions.append("   pip install graphviz")
            instructions.append("")

        if not self.status["system_binary"]:
            instructions.append("2. Install system Graphviz:")
            instructions.append("")

            if self.system == "Windows":
                instructions.append("   WINDOWS - Choose one method:")
                instructions.append("")
                instructions.append("   Option A - Winget (recommended for Windows 10+):")
                instructions.append("   winget install graphviz")
                instructions.append("")
                instructions.append("   Option B - Chocolatey:")
                instructions.append("   choco install graphviz")
                instructions.append("")
                instructions.append("   Option C - Manual download:")
                instructions.append("   1. Download from: https://graphviz.org/download/")
                instructions.append("   2. Install to default location")
                instructions.append("   3. Add to PATH: C:\\Program Files\\Graphviz\\bin")
                instructions.append("")
                instructions.append("   After installation, restart your terminal/IDE")

            elif self.system == "Darwin":  # macOS
                instructions.append("   macOS - Choose one method:")
                instructions.append("")
                instructions.append("   Option A - Homebrew (recommended):")
                instructions.append("   brew install graphviz")
                instructions.append("")
                instructions.append("   Option B - MacPorts:")
                instructions.append("   sudo port install graphviz")

            elif self.system == "Linux":
                instructions.append("   LINUX - Use your package manager:")
                instructions.append("")
                instructions.append("   Ubuntu/Debian:")
                instructions.append("   sudo apt-get install graphviz")
                instructions.append("")
                instructions.append("   Fedora/RHEL:")
                instructions.append("   sudo dnf install graphviz")
                instructions.append("")
                instructions.append("   Arch Linux:")
                instructions.append("   sudo pacman -S graphviz")

            else:
                instructions.append(f"   For {self.system}:")
                instructions.append("   Visit: https://graphviz.org/download/")

        return "\n".join(instructions)

    def _update_path_after_install(self):
        """Add common Graphviz binary locations to PATH for current process."""
        candidates = []
        if self.system == "Windows":
            candidates = [
                r"C:\Program Files\Graphviz\bin",
                r"C:\Program Files (x86)\Graphviz\bin",
            ]
        elif self.system == "Darwin":
            candidates = ["/opt/homebrew/bin", "/usr/local/bin"]
        elif self.system == "Linux":
            candidates = ["/usr/local/bin"]

        current_path = os.environ.get("PATH", "")
        for candidate in candidates:
            if Path(candidate).is_dir() and candidate not in current_path:
                os.environ["PATH"] = candidate + os.pathsep + current_path
                current_path = os.environ["PATH"]

    def try_auto_install(self) -> tuple[bool, str]:
        """
        Attempt automatic installation (requires elevated privileges)

        Returns:
            (success: bool, message: str)
        """
        if self.status["ready"]:
            return (True, "Graphviz already installed")

        # Install Python package first
        if not self.status["python_package"]:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "graphviz"])
            except subprocess.CalledProcessError as e:
                return (False, f"Failed to install Python package: {e}")

        # Try to install system binary
        if not self.status["system_binary"]:
            if self.system == "Windows":
                # STEP 1: Try winget first (no elevation needed)
                if shutil.which("winget"):
                    try:
                        result = subprocess.run(
                            ["winget", "install", "graphviz"],
                            capture_output=True,
                            text=True,
                        )
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)

                        if result.returncode == 0:
                            self._update_path_after_install()
                            return (
                                True,
                                "Installed via winget.",
                            )
                    except Exception as e:
                        print(f"Winget failed: {e}")

                # STEP 2: If winget failed, try chocolatey with UAC elevation
                if shutil.which("choco"):
                    print("\nWinget installation failed or not available.")
                    print("Chocolatey installation requires administrator privileges.")

                    try:
                        # Try to run chocolatey with elevation using PowerShell
                        # This will trigger UAC prompt on Windows
                        ps_cmd = 'Start-Process choco -ArgumentList "install","graphviz","-y" -Verb RunAs -Wait'
                        result = subprocess.run(
                            ["powershell", "-Command", ps_cmd],
                            capture_output=True,
                            text=True,
                        )

                        if result.stdout:
                            print(result.stdout)
                        if result.stderr:
                            print(result.stderr)

                        if result.returncode == 0:
                            self._update_path_after_install()
                            return (
                                True,
                                "Installed via Chocolatey.",
                            )
                        else:
                            print("Chocolatey installation failed or was cancelled.")
                    except Exception as e:
                        print(f"Chocolatey installation error: {e}")

                # STEP 3: If both failed, show manual installation instructions
                return (
                    False,
                    "Could not auto-install. Please install manually:\n"
                    + self.get_installation_instructions(),
                )

            elif self.system == "Darwin":
                if shutil.which("brew"):
                    try:
                        subprocess.check_call(["brew", "install", "graphviz"])
                        self._update_path_after_install()
                        return (True, "Installed via Homebrew")
                    except subprocess.CalledProcessError:
                        return (False, "Homebrew installation failed")
                return (False, "Homebrew not found. Install manually.")

            elif self.system == "Linux":
                # Try apt (Debian/Ubuntu)
                if shutil.which("apt-get"):
                    try:
                        subprocess.check_call(["sudo", "apt-get", "install", "-y", "graphviz"])
                        self._update_path_after_install()
                        return (True, "Installed via apt")
                    except subprocess.CalledProcessError:
                        return (False, "apt installation failed (may need sudo)")

                # Try dnf (Fedora/RHEL)
                if shutil.which("dnf"):
                    try:
                        subprocess.check_call(["sudo", "dnf", "install", "-y", "graphviz"])
                        self._update_path_after_install()
                        return (True, "Installed via dnf")
                    except subprocess.CalledProcessError:
                        return (False, "dnf installation failed (may need sudo)")

                return (False, "Could not detect package manager")

        return (False, "Unknown error occurred")

    def get_diagnostic_info(self) -> str:
        """Get detailed diagnostic information"""
        lines = [
            "=== Graphviz Installation Diagnostic ===",
            f"Platform: {self.system}",
            f"Python Package Installed: {self.status['python_package']}",
            f"System Binary Found: {self.status['system_binary']}",
            f"Dot Executable: {self.status['dot_executable'] or 'Not found'}",
            f"Graphviz Version: {self.status['version'] or 'Unknown'}",
            f"Ready to Use: {self.status['ready']}",
            "",
        ]

        if not self.status["ready"]:
            lines.append("=== Installation Instructions ===")
            lines.append(self.get_installation_instructions())

        return "\n".join(lines)


def ensure_graphviz() -> tuple[bool, str]:
    """
    Ensure Graphviz is installed and ready

    Returns:
        (ready: bool, message: str)
    """
    installer = GraphvizInstaller()

    if installer.status["ready"]:
        return (True, f"Graphviz {installer.status['version']} ready")

    # Try auto-install
    success, message = installer.try_auto_install()

    if not success:
        # Return installation instructions
        return (False, installer.get_diagnostic_info())

    # Update PATH and re-check after installation
    installer._update_path_after_install()
    installer.status = installer.check_installation()
    if installer.status["ready"]:
        return (True, message)
    else:
        return (False, message + "\n\nPlease restart your terminal and try again.")


if __name__ == "__main__":
    installer = GraphvizInstaller()
    print(installer.get_diagnostic_info())

    if not installer.status["ready"]:
        print("\n=== Attempting Auto-Install ===")
        success, message = installer.try_auto_install()
        print(message)
