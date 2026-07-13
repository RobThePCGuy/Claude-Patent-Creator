"""Package Consistency Tools

Cross-artifact checks over an assembled filing-package directory —
the deterministic half of the two-red-teams discipline in the
patent-application-creator skill.

Tools:
    - check_package: stamp freshness, claim-count agreement, status
      contradictions, filing-copy purity, date sanity
"""

from typing import Any


def register_package_tools(
    mcp,
    PackageChecker,
    log_info,
    log_error,
    validate_input,
    CheckPackageInput,
    track_performance,
    log_operation_result,
):
    """Register package-consistency tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        PackageChecker: Package checker class (None if unavailable)
        log_info: Logging function for info messages
        log_error: Logging function for error messages
        validate_input: Input validation function
        CheckPackageInput: Pydantic model for package check validation
        track_performance: Performance tracking decorator
        log_operation_result: Operation result logging function
    """

    @mcp.tool()
    @track_performance("tool_check_package")
    def check_package(directory: str) -> dict[str, Any]:
        """Check an assembled filing-package directory for cross-artifact consistency: stale content-hash verification stamps (edit-after-check), claim-count disagreements between documents, status contradictions (readiness claims beside draft markers), commentary inside filing copies, and future/malformed dates. Per-document checkers cannot see these — run this on the whole package directory before calling anything filing-ready."""
        try:
            validated = validate_input(CheckPackageInput, directory=directory)
            directory = validated.directory

            log_info("check_package_started", directory=directory)

            if PackageChecker is None:
                return {"error": "Package checker is not available."}

            checker = PackageChecker()
            report = checker.analyze(directory)

            log_operation_result(
                "check_package",
                success=True,
                files_scanned=report.get("files_scanned"),
                critical=report.get("critical_issues"),
            )
            return report
        except ValueError as e:
            log_error("check_package_failed", error=str(e))
            return {"error": str(e)}
        except Exception as e:
            log_error("check_package_failed", error=str(e))
            return {"error": f"Package check failed: {e}"}
