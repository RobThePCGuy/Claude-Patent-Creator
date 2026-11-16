"""
MPEP RAG MCP Server
Provides intelligent retrieval from patent law sources for examiner-level review
"""

from pathlib import Path

from ._version import load_version

__version__ = load_version(__file__)
__author__ = "Maintainers"

# Package root directory
PACKAGE_ROOT = Path(__file__).parent
PROJECT_ROOT = PACKAGE_ROOT.parent
