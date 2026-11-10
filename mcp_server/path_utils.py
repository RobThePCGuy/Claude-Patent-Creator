#!/usr/bin/env python3
"""
Cross-Platform Path Formatting Utilities
Handles Windows, Linux, macOS path formatting for different shells
"""

import os
import platform
import shlex
from pathlib import Path
from typing import Union


def interpreter_path(path: Union[str, Path, None] = None) -> str:
    """Absolute path to a Python interpreter, keeping venv symlinks intact.

    ``Path.resolve()`` follows a virtual environment's ``bin/python`` symlink
    back to the base interpreter, which has none of the venv's packages.
    Anything that records "the Python to run this tool with" must use this.
    """
    import sys

    # .absolute(), never .resolve(): resolve() follows the venv symlink.
    return str(Path(path if path is not None else sys.executable).absolute())


class PathFormatter:
    """Cross-platform path formatting and quoting for various shells"""

    @staticmethod
    def for_bash(path: Union[str, Path]) -> str:
        """
        Format path for Bash (Git Bash, WSL, Linux, macOS)

        Examples:
            C:\\Users\\<YOUR_USER>\\file.txt -> /c/Users/<YOUR_USER>/file.txt
            /home/user/file.txt -> /home/user/file.txt
            "path with spaces" -> 'path with spaces'
        """
        path_str = str(Path(path).resolve())

        # Convert Windows paths to POSIX for Git Bash
        if platform.system() == "Windows":
            # C:\\Users\\<YOUR_USER> -> /c/Users/<YOUR_USER>
            if len(path_str) >= 3 and path_str[1] == ":":
                drive = path_str[0].lower()
                rest = path_str[3:].replace("\\", "/")
                path_str = f"/{drive}/{rest}"
            else:
                path_str = path_str.replace("\\", "/")

        # Quote if contains spaces or special characters
        if " " in path_str or any(c in path_str for c in ["&", "|", ";", "(", ")", "<", ">"]):
            return shlex.quote(path_str)
        return path_str

    @staticmethod
    def for_powershell(path: Union[str, Path]) -> str:
        """
        Format path for PowerShell

        Examples:
            C:\\Users\\<YOUR_USER>\\file.txt -> "C:\\Users\\<YOUR_USER>\\file.txt" (if spaces)
            C:\\Users\\file.txt -> C:\\Users\\file.txt (no spaces)
        """
        path_str = str(Path(path).resolve())

        # PowerShell uses double quotes for paths with spaces
        if " " in path_str:
            # Escape inner double quotes if any
            path_str = path_str.replace('"', '`"')
            return f'"{path_str}"'
        return path_str

    @staticmethod
    def for_cmd(path: Union[str, Path]) -> str:
        """
        Format path for Windows CMD

        Examples:
            C:\\Users\\<YOUR_USER>\\file.txt -> "C:\\Users\\<YOUR_USER>\\file.txt" (if spaces)
            C:\\Users\\file.txt -> C:\\Users\\file.txt (no spaces)
        """
        path_str = str(Path(path).resolve())

        # CMD uses double quotes for paths with spaces
        if " " in path_str:
            return f'"{path_str}"'
        return path_str

    @staticmethod
    def auto_format(path: Union[str, Path]) -> str:
        """
        Automatically format path for current shell environment

        Detects:
        - Git Bash (MSYSTEM env var)
        - WSL (WSL_DISTRO_NAME env var)
        - PowerShell (PSMODULEPATH env var)
        - CMD (default on Windows)
        - Bash/sh (Linux/macOS)
        """
        # Check for Git Bash or WSL
        if os.getenv("MSYSTEM") or os.getenv("WSL_DISTRO_NAME"):
            return PathFormatter.for_bash(path)

        # Check for PowerShell
        if os.getenv("PSMODULEPATH") or os.getenv("PSModulePath"):
            return PathFormatter.for_powershell(path)

        # Check platform
        system = platform.system()
        if system == "Windows":
            # Likely CMD if we got here
            return PathFormatter.for_cmd(path)
        else:
            # Linux or macOS - use bash formatting
            return PathFormatter.for_bash(path)

    @staticmethod
    def normalize(path: Union[str, Path]) -> Path:
        """
        Normalize path across platforms (resolve, absolute, clean)

        Returns Path object that works consistently across platforms
        """
        return Path(path).resolve()

    @staticmethod
    def ensure_posix_str(path: Union[str, Path]) -> str:
        """
        Convert path to POSIX string format (forward slashes)

        Useful for URLs, JSON, and cross-platform storage
        """
        return str(Path(path).resolve()).replace("\\", "/")

    @staticmethod
    def get_shell_type() -> str:
        """
        Detect current shell type

        Returns: "bash", "powershell", "cmd", "git-bash", "wsl", "zsh", "sh", "unknown"
        """
        # Check environment variables
        if os.getenv("MSYSTEM"):
            return "git-bash"
        if os.getenv("WSL_DISTRO_NAME"):
            return "wsl"
        if os.getenv("PSMODULEPATH") or os.getenv("PSModulePath"):
            return "powershell"

        # Check SHELL environment variable (Linux/macOS)
        shell = os.getenv("SHELL", "").lower()
        if "bash" in shell:
            return "bash"
        if "zsh" in shell:
            return "zsh"
        if "sh" in shell and "bash" not in shell:
            return "sh"

        # Default based on platform
        if platform.system() == "Windows":
            return "cmd"
        else:
            return "bash"  # Assume bash on *nix systems

    @staticmethod
    def format_for_claude_mcp(
        python_path: Union[str, Path], script_path: Union[str, Path]
    ) -> tuple:
        """
        Format paths specifically for Claude MCP registration

        Returns: (python_str, script_str) formatted appropriately
        """
        # MCP registration uses POSIX-style paths even on Windows.
        # The interpreter path must NOT be resolved: a venv's python is a
        # symlink to the base interpreter, and following it registers a
        # Python that cannot import this package's dependencies.
        python_str = interpreter_path(python_path).replace("\\", "/")
        script_str = PathFormatter.ensure_posix_str(script_path)

        return python_str, script_str


class PathValidator:
    """Validate paths and provide helpful error messages"""

    @staticmethod
    def validate_executable(path: Union[str, Path]) -> tuple[bool, str]:
        """
        Validate that path points to an executable file

        Returns: (is_valid, error_message)
        """
        path_obj = Path(path)

        if not path_obj.exists():
            return False, f"File not found: {path}"

        if not path_obj.is_file():
            return False, f"Not a file: {path}"

        if not os.access(path_obj, os.X_OK) and platform.system() != "Windows":
            return False, f"Not executable: {path}"

        return True, ""

    @staticmethod
    def validate_directory(path: Union[str, Path], must_exist: bool = True) -> tuple[bool, str]:
        """
        Validate that path points to a directory

        Returns: (is_valid, error_message)
        """
        path_obj = Path(path)

        if must_exist and not path_obj.exists():
            return False, f"Directory not found: {path}"

        if path_obj.exists() and not path_obj.is_dir():
            return False, f"Not a directory: {path}"

        return True, ""

    @staticmethod
    def suggest_fix(path: Union[str, Path], issue: str) -> str:
        """
        Suggest how to fix common path issues

        Args:
            path: The problematic path
            issue: Description of the issue

        Returns: Suggested fix command or instruction
        """
        if "not found" in issue.lower():
            parent = Path(path).parent
            if parent.exists():
                return f"Create with: mkdir '{path}'"
            else:
                return f"Create parent directories with: mkdir -p '{path}'"

        if "spaces" in issue.lower():
            shell = PathFormatter.get_shell_type()
            if shell in ["bash", "sh", "zsh"]:
                return f"Quote the path: '{path}'"
            elif shell in ["powershell", "cmd"]:
                return f'Quote the path: "{path}"'

        if "not executable" in issue.lower():
            return f"Make executable: chmod +x '{path}'"

        return "No suggestion available"


# Convenience functions for common use cases
def format_for_bash(path: Union[str, Path]) -> str:
    """Shorthand for PathFormatter.for_bash()"""
    return PathFormatter.for_bash(path)


def format_for_powershell(path: Union[str, Path]) -> str:
    """Shorthand for PathFormatter.for_powershell()"""
    return PathFormatter.for_powershell(path)


def auto_format_path(path: Union[str, Path]) -> str:
    """Shorthand for PathFormatter.auto_format()"""
    return PathFormatter.auto_format(path)


# Example usage and testing
if __name__ == "__main__":
    print("=" * 60)
    print("Cross-Platform Path Formatter Test")
    print("=" * 60)

    test_paths = [
        r"C:\Users\Test User\Documents\file.txt",
        r"/home/user/documents/file.txt",
        r"C:\Program Files\MyApp\bin\app.exe",
    ]

    for test_path in test_paths:
        print(f"\nOriginal: {test_path}")
        print(f"  Bash:       {PathFormatter.for_bash(test_path)}")
        print(f"  PowerShell: {PathFormatter.for_powershell(test_path)}")
        print(f"  CMD:        {PathFormatter.for_cmd(test_path)}")
        print(f"  Auto:       {PathFormatter.auto_format(test_path)}")
        print(f"  POSIX:      {PathFormatter.ensure_posix_str(test_path)}")

    print(f"\nDetected shell: {PathFormatter.get_shell_type()}")
    print("=" * 60)
