#!/usr/bin/env python3
"""
System Health Checker for Claude Patent Creator
Provides comprehensive pre-flight dependency validation
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from logging_config import get_logger

    logger = get_logger()
except ImportError:
    logger = None

# Import from server module
try:
    from server import INDEX_DIR, MPEP_DIR
except ImportError:
    # Fallback for standalone testing — same resolution as the server
    try:
        from data_paths import index_dir, mpep_dir
    except ImportError:
        from mcp_server.data_paths import index_dir, mpep_dir

    INDEX_DIR = index_dir()
    MPEP_DIR = mpep_dir()


class SystemHealthChecker:
    """Comprehensive dependency and readiness validation"""

    def __init__(self):
        self.results = {}

    def check_all_dependencies(self, verbose: bool = False) -> dict[str, Any]:
        """Run all health checks and return comprehensive status"""
        if logger:
            logger.info("health_check_started")
        elif verbose:
            print("Running system health checks...", file=sys.stderr)

        self.results = {
            "timestamp": datetime.now().isoformat(),
            "mpep_index": self._check_mpep_index(),
            "bigquery": self._check_bigquery(),
            "uspto_api": self._check_uspto_api(),
            "graphviz": self._check_graphviz(),
            "gpu_status": self._check_gpu(),
            "disk_space": self._check_disk_space(),
            "models": self._check_models(),
            "python_packages": self._check_packages(),
        }

        # Calculate overall health
        ready_components = sum(
            1
            for comp in self.results.values()
            if isinstance(comp, dict) and comp.get("ready", False)
        )
        total_components = sum(
            1 for comp in self.results.values() if isinstance(comp, dict) and "ready" in comp
        )

        self.results["overall"] = {
            "ready_components": ready_components,
            "total_components": total_components,
            "health_percentage": (
                int((ready_components / total_components) * 100) if total_components > 0 else 0
            ),
            "status": "healthy" if ready_components == total_components else "degraded",
        }

        if logger:
            logger.info(
                "health_check_completed",
                extra={
                    "overall_health": self.results["overall"]["status"],
                    "ready_components": ready_components,
                    "total_components": total_components,
                    "health_percentage": self.results["overall"]["health_percentage"],
                },
            )

        return self.results

    def _check_mpep_index(self) -> dict[str, Any]:
        """Check if MPEP index is built and ready"""
        index_file = INDEX_DIR / "mpep_index.faiss"
        metadata_file = INDEX_DIR / "mpep_metadata.json"

        if not index_file.exists() or not metadata_file.exists():
            if logger:
                logger.warning(
                    "health_check_mpep_index_missing",
                    extra={
                        "index_exists": index_file.exists(),
                        "metadata_exists": metadata_file.exists(),
                    },
                )
            return {
                "status": "missing",
                "ready": False,
                "fix": "patent-creator setup",
                "details": "MPEP index not built. Run setup to download and index USPTO rules.",
                "required_for": [
                    "search_mpep",
                    "review_patent_claims",
                    "review_specification",
                    "check_formalities",
                ],
            }

        # Check index integrity
        try:
            import json

            import faiss

            index = faiss.read_index(str(index_file))
            chunk_count = index.ntotal

            with metadata_file.open(encoding="utf-8") as f:
                metadata = json.load(f)

            result = {
                "status": "ready",
                "ready": True,
                "chunks": chunk_count,
                "metadata_entries": len(metadata.get("metadata", [])),
                "size_mb": round(index_file.stat().st_size / (1024**2), 2),
                "last_modified": datetime.fromtimestamp(index_file.stat().st_mtime).isoformat(),
            }

            if logger:
                logger.info(
                    "health_check_mpep_index_success",
                    extra={"chunks": chunk_count, "size_mb": result["size_mb"]},
                )

            return result
        except Exception as e:
            if logger:
                logger.error(
                    "health_check_mpep_index_corrupt", extra={"error": str(e)}, exc_info=True
                )
            return {
                "status": "corrupt",
                "ready": False,
                "error": str(e),
                "fix": "patent-creator setup --rebuild-index",
                "details": "Index files exist but are corrupted. Rebuild required.",
            }

    def _check_bigquery(self) -> dict[str, Any]:
        """Check if BigQuery patent search is available"""
        try:
            from bigquery_search import check_bigquery_available

            status = check_bigquery_available()

            if status.get("available"):
                if logger:
                    logger.info(
                        "health_check_bigquery_success", extra={"project": status.get("project")}
                    )
                return {
                    "status": "ready",
                    "ready": True,
                    "project": status.get("project"),
                    "coverage": "100M+ worldwide patents, 12M+ US patents",
                    "cost": "Free for typical usage (1TB/month)",
                    "details": "Google BigQuery patent search ready",
                    "provides": [
                        "search_patents_bigquery",
                        "get_patent_bigquery",
                        "search_patents_by_cpc_bigquery",
                    ],
                }
            else:
                if logger:
                    logger.warning(
                        "health_check_bigquery_not_configured", extra={"error": status.get("error")}
                    )
                return {
                    "status": "not_configured",
                    "ready": False,
                    "error": status.get("error", "Unknown error"),
                    "fix": status.get(
                        "install_command", "pip install google-cloud-bigquery db-dtypes"
                    ),
                    "details": "BigQuery not available. Install dependencies or configure credentials.",
                    "provides": [
                        "search_patents_bigquery (RECOMMENDED for prior art)",
                        "get_patent_bigquery",
                        "search_patents_by_cpc_bigquery",
                    ],
                }
        except Exception as e:
            if logger:
                logger.error("health_check_bigquery_error", extra={"error": str(e)}, exc_info=True)
            return {
                "status": "error",
                "ready": False,
                "error": str(e),
                "fix": "pip install google-cloud-bigquery db-dtypes",
                "details": "BigQuery module not available",
            }

    def _check_uspto_api(self) -> dict[str, Any]:
        """Check USPTO API key and connectivity"""
        api_key = os.getenv("USPTO_API_KEY")

        if not api_key:
            if logger:
                logger.warning("health_check_uspto_api_not_configured")
            return {
                "status": "not_configured",
                "ready": False,
                "available": False,
                "api_key_configured": False,
                "fix": "Set USPTO_API_KEY environment variable",
                "details": (
                    "Get API key at: https://data.uspto.gov/myodp\n"
                    "Setup takes 5 minutes. Requires USPTO account and ID.me verification."
                ),
                "required_for": [
                    "search_uspto_api",
                    "get_uspto_patent",
                    "get_recent_uspto_patents",
                ],
            }

        # Test API connectivity with detailed diagnostics
        try:
            from uspto_api import USPTOClient

            client = USPTOClient(api_key)

            # Use detailed status check for better diagnostics
            detailed_status = client.check_api_status_detailed()

            if detailed_status["available"]:
                if logger:
                    logger.info(
                        "health_check_uspto_api_success",
                        extra={"response_time_ms": detailed_status.get("response_time_ms")},
                    )
                return {
                    "status": "ready",
                    "ready": True,
                    "available": True,
                    "api_key_configured": True,
                    "api_key_status": "CONFIGURED",
                    "endpoint": client.BASE_URL,
                    "connectivity": "verified",
                    "response_time_ms": detailed_status.get("response_time_ms"),
                    "message": detailed_status.get("message"),
                }
            else:
                if logger:
                    logger.error(
                        "health_check_uspto_api_failed",
                        extra={
                            "error": detailed_status.get("error"),
                            "message": detailed_status.get("message"),
                        },
                    )
                return {
                    "status": (
                        "authentication_failed"
                        if detailed_status["api_key_configured"]
                        else "not_configured"
                    ),
                    "ready": False,
                    "available": False,
                    "api_key_configured": detailed_status["api_key_configured"],
                    "api_key_status": "CONFIGURED" if api_key else "NOT_CONFIGURED",
                    "error": detailed_status.get("error", "Unknown error"),
                    "message": detailed_status.get("message"),
                    "fix": "Verify API key at https://data.uspto.gov/myodp",
                }

        except ImportError:
            if logger:
                logger.error("health_check_uspto_api_import_error")
            return {
                "status": "module_missing",
                "ready": False,
                "available": False,
                "error": "USPTO API module not available",
                "fix": "pip install -e .",
            }
        except Exception as e:
            if logger:
                logger.error(
                    "health_check_uspto_api_exception", extra={"error": str(e)}, exc_info=True
                )
            return {
                "status": "error",
                "ready": False,
                "available": False,
                "api_key_configured": True,
                "error": str(e),
                "fix": "Check network connectivity and API key validity",
            }

    def _check_graphviz(self) -> dict[str, Any]:
        """Check if Graphviz is installed for diagram generation"""
        try:
            import subprocess

            # Check system Graphviz installation
            try:
                result = subprocess.run(["dot", "-V"], capture_output=True, text=True, timeout=5)
                version = result.stderr.strip() if result.stderr else result.stdout.strip()

                if logger:
                    logger.info("health_check_graphviz_success", extra={"version": version})

                return {
                    "status": "ready",
                    "ready": True,
                    "python_package": True,
                    "system_command": True,
                    "version": version,
                }
            except (subprocess.TimeoutExpired, FileNotFoundError):
                if logger:
                    logger.warning(
                        "health_check_graphviz_partial",
                        extra={"python_package": True, "system_command": False},
                    )
                return {
                    "status": "partial",
                    "ready": False,
                    "python_package": True,
                    "system_command": False,
                    "fix": "Install system Graphviz: sudo apt install graphviz (Linux) or winget install graphviz (Windows)",
                    "details": "Python package installed but system Graphviz missing",
                    "required_for": ["render_diagram", "create_flowchart", "create_block_diagram"],
                }
        except ImportError:
            if logger:
                logger.warning("health_check_graphviz_not_installed")
            return {
                "status": "not_installed",
                "ready": False,
                "python_package": False,
                "system_command": False,
                "fix": "pip install graphviz && sudo apt install graphviz",
                "required_for": ["diagram generation tools"],
            }

    def _check_gpu(self) -> dict[str, Any]:
        """Check GPU availability and status"""
        try:
            import torch

            if torch.cuda.is_available():
                gpu_count = torch.cuda.device_count()
                current_device = torch.cuda.current_device()
                gpu_name = torch.cuda.get_device_name(current_device)
                gpu_memory = torch.cuda.get_device_properties(current_device).total_memory / (
                    1024**3
                )

                return {
                    "status": "available",
                    "ready": True,
                    "device_count": gpu_count,
                    "current_device": current_device,
                    "device_name": gpu_name,
                    "vram_gb": round(gpu_memory, 1),
                    "cuda_version": torch.version.cuda,
                    "performance_impact": "5-10x faster indexing and search",
                }
            else:
                return {
                    "status": "not_available",
                    "ready": True,  # CPU is fine, just slower
                    "device": "cpu",
                    "details": "Using CPU. Install CUDA-enabled PyTorch for GPU acceleration.",
                    "fix": "See GPU_SETUP.md for installation instructions",
                    "performance_impact": "CPU mode is slower but functional",
                }
        except ImportError:
            return {
                "status": "pytorch_missing",
                "ready": False,
                "error": "PyTorch not installed",
                "fix": "pip install torch",
            }

    def _check_disk_space(self) -> dict[str, Any]:
        """Check available disk space"""
        try:
            import shutil

            project_root = Path(__file__).parent.parent
            total, used, free = shutil.disk_usage(project_root)

            free_gb = free / (1024**3)
            total_gb = total / (1024**3)
            used_percent = (used / total) * 100

            if free_gb < 5:
                status = "critical"
                ready = False
                message = "Less than 5GB free. May not be able to download sources."
            elif free_gb < 20:
                status = "warning"
                ready = True
                message = "Limited space. Cannot download patent corpus (requires 15GB)."
            else:
                status = "healthy"
                ready = True
                message = "Sufficient disk space available"

            return {
                "status": status,
                "ready": ready,
                "free_gb": round(free_gb, 2),
                "total_gb": round(total_gb, 2),
                "used_percent": round(used_percent, 1),
                "message": message,
            }
        except Exception as e:
            return {
                "status": "error",
                "ready": True,  # Not critical
                "error": str(e),
            }

    def _check_models(self) -> dict[str, Any]:
        """Check if required AI models can be loaded"""
        models_status: dict[str, Any] = {
            "embeddings": {"ready": False},
            "reranker": {"ready": False},
            "hyde": {"ready": False},
        }

        try:
            from sentence_transformers import CrossEncoder, SentenceTransformer

            # Test embeddings model
            try:
                _ = SentenceTransformer("BAAI/bge-base-en-v1.5", device="cpu")
                models_status["embeddings"] = {
                    "ready": True,
                    "model": "BAAI/bge-base-en-v1.5",
                    "dimensions": 768,
                }
            except Exception as e:
                models_status["embeddings"] = {
                    "ready": False,
                    "error": str(e),
                    "fix": "pip install sentence-transformers",
                }

            # Test reranker model
            try:
                _ = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", device="cpu")
                models_status["reranker"] = {
                    "ready": True,
                    "model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
                }
            except Exception as e:
                models_status["reranker"] = {"ready": False, "error": str(e)}

            # Test HyDE (optional) — skip when explicitly disabled via env var
            use_hyde = os.environ.get("PATENT_MPEP_USE_HYDE", "true").lower() != "false"
            if use_hyde:
                try:
                    from hyde import HyDEQueryExpander

                    _ = HyDEQueryExpander(backend="auto")
                    models_status["hyde"] = {
                        "ready": True,
                        "optional": True,
                        "note": "Query expansion enabled for better search results",
                    }
                except Exception:
                    models_status["hyde"] = {
                        "ready": False,
                        "optional": True,
                        "note": "HyDE disabled, using standard search",
                    }
            else:
                models_status["hyde"] = {
                    "ready": False,
                    "optional": True,
                    "note": "HyDE disabled by --no-hyde flag",
                }

        except ImportError as e:
            return {
                "status": "error",
                "ready": False,
                "error": str(e),
                "fix": "pip install sentence-transformers",
            }

        # Overall models status
        required_ready = models_status["embeddings"]["ready"] and models_status["reranker"]["ready"]

        return {
            "status": "ready" if required_ready else "error",
            "ready": required_ready,
            "models": models_status,
        }

    def _check_packages(self) -> dict[str, Any]:
        """Check if critical Python packages are installed"""
        packages = {
            "torch": False,
            "sentence_transformers": False,
            "faiss": False,
            "numpy": False,
            "mcp": False,
            "requests": False,
        }

        versions = {}

        for package in packages:
            try:
                if package == "faiss":
                    # FAISS can be faiss-cpu or faiss-gpu
                    try:
                        import faiss

                        packages[package] = True
                        versions[package] = (
                            faiss.__version__ if hasattr(faiss, "__version__") else "installed"
                        )
                    except ImportError:
                        packages[package] = False
                else:
                    mod = __import__(package)
                    packages[package] = True
                    versions[package] = (
                        mod.__version__ if hasattr(mod, "__version__") else "installed"
                    )
            except ImportError:
                packages[package] = False

        all_installed = all(packages.values())

        return {
            "status": "ready" if all_installed else "incomplete",
            "ready": all_installed,
            "packages": packages,
            "versions": versions,
            "fix": "pip install -e ." if not all_installed else None,
        }

    def get_warnings(self) -> list[str]:
        """Get list of warnings based on health check results"""
        warnings = []

        if not self.results.get("mpep_index", {}).get("ready"):
            warnings.append(
                f"[WARNING] MPEP Index not ready. Fix: {self.results['mpep_index'].get('fix', 'unknown')}"
            )

        if not self.results.get("uspto_api", {}).get("ready"):
            warnings.append(
                f"[WARNING] USPTO API not configured. {self.results['uspto_api'].get('details', '')}"
            )

        if not self.results.get("graphviz", {}).get("ready"):
            warnings.append("[WARNING] Graphviz not installed. Diagram generation will not work.")

        return warnings

    def print_status_report(self):
        """Print formatted status report to stderr"""
        if not self.results:
            self.check_all_dependencies(verbose=True)

        print("\n" + "=" * 65, file=sys.stderr)
        print("SYSTEM STATUS - Claude Patent Creator", file=sys.stderr)
        print("=" * 65, file=sys.stderr)

        # MPEP Index
        mpep = self.results.get("mpep_index", {})
        status_icon = "[OK]" if mpep.get("ready") else "[X]"
        print(f"\nMPEP Index............ {status_icon} ", end="", file=sys.stderr)
        if mpep.get("ready"):
            print(
                f"Ready ({mpep.get('chunks', 0):,} chunks, {mpep.get('size_mb', 0)} MB)",
                file=sys.stderr,
            )
        else:
            print(f"{mpep.get('status', 'unknown')}", file=sys.stderr)
            print(f"                         Fix: {mpep.get('fix', 'unknown')}", file=sys.stderr)

        # USPTO API
        uspto = self.results.get("uspto_api", {})
        status_icon = "[OK]" if uspto.get("ready") else "[X]"
        print(f"USPTO API............. {status_icon} ", end="", file=sys.stderr)
        if uspto.get("ready"):
            print("Connected (API Key: ****)", file=sys.stderr)
        else:
            print(f"{uspto.get('status', 'unknown')}", file=sys.stderr)
            if uspto.get("fix"):
                print(f"                         Fix: {uspto.get('fix')}", file=sys.stderr)

        # Graphviz
        graphviz = self.results.get("graphviz", {})
        status_icon = "[OK]" if graphviz.get("ready") else "[X]"
        print(f"Graphviz.............. {status_icon} ", end="", file=sys.stderr)
        if graphviz.get("ready"):
            print(f"Installed ({graphviz.get('version', 'unknown')})", file=sys.stderr)
        else:
            print(f"{graphviz.get('status', 'unknown')}", file=sys.stderr)

        # GPU
        gpu = self.results.get("gpu_status", {})
        status_icon = "[OK]" if gpu.get("status") == "available" else "[INFO]"
        print(f"GPU................... {status_icon} ", end="", file=sys.stderr)
        if gpu.get("status") == "available":
            print(f"{gpu.get('device_name')} ({gpu.get('vram_gb')}GB)", file=sys.stderr)
        else:
            print(f"CPU mode ({gpu.get('details', 'No GPU detected')})", file=sys.stderr)

        # Disk Space
        disk = self.results.get("disk_space", {})
        status_icon = "[OK]" if disk.get("status") == "healthy" else "[WARNING]"
        print(
            f"Disk Space............ {status_icon} {disk.get('free_gb', 0):.1f}GB available",
            file=sys.stderr,
        )

        # Models
        models = self.results.get("models", {})
        status_icon = "[OK]" if models.get("ready") else "[X]"
        print("\nModels:", file=sys.stderr)
        for model_type, model_info in models.get("models", {}).items():
            icon = "[OK]" if model_info.get("ready") else "[X]"
            print(f"  {model_type.capitalize():15} {icon}", file=sys.stderr)

        # Overall
        overall = self.results.get("overall", {})
        print(
            f"\nOVERALL STATUS: {overall.get('ready_components', 0)}/{overall.get('total_components', 0)} components ready ({overall.get('health_percentage', 0)}%)",
            file=sys.stderr,
        )

        # Warnings
        warnings = self.get_warnings()
        if warnings:
            print("\nRECOMMENDATIONS:", file=sys.stderr)
            for i, warning in enumerate(warnings, 1):
                print(f"  {i}. {warning}", file=sys.stderr)

        print("=" * 65 + "\n", file=sys.stderr)


def main():
    """CLI entry point for health checks"""
    checker = SystemHealthChecker()
    checker.check_all_dependencies(verbose=True)
    checker.print_status_report()


if __name__ == "__main__":
    main()
