"""Package-level consistency checker for assembled filing packages.

Per-artifact checkers (review_patent_claims, review_specification,
check_formalities) each validate one document in isolation. Nothing
validated the PACKAGE — so a README could claim "verified" beside a stale
draft header, a claim could be added after its recorded compliance check,
and strategy commentary could ride along inside documents marked for
filing. This module checks the assembly:

- verification-stamp freshness: a stamp is a backticked lowercase-hex
  prefix of the SHA-256 of the target file's raw bytes, written near the
  word "hash". Stamps are recomputed; a mismatch means edit-after-check.
  A stamp whose target file cannot be resolved is unverifiable, which is
  treated as unverified.
- claim-count agreement between the claims file and every "N claims"
  assertion elsewhere in the package
- status contradictions: readiness assertions ("filing-ready") anywhere
  while draft/DO-NOT-FILE/SUPERSEDED markers exist anywhere
- filing-copy purity: documents marked for filing must carry no bracketed
  commentary, TODO notes, checker scores, or "Next steps" sections
- date sanity: future or malformed ISO dates
"""

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Optional

try:
    from analyzer_base import BaseAnalyzer, BaseIssue
except ImportError:
    from mcp_server.analyzer_base import BaseAnalyzer, BaseIssue

TEXT_SUFFIXES = {".md", ".txt", ".markdown"}
MAX_FILE_BYTES = 2 * 1024 * 1024

STAMP_RE = re.compile(r"hash[^`\n]{0,40}`([0-9a-f]{8,64})`", re.IGNORECASE)
FILE_REF_RE = re.compile(r"`([^`\n]+?\.(?:md|txt|markdown|svg|pdf))`", re.IGNORECASE)
CLAIM_LINE_RE = re.compile(r"^\s{0,3}(\d{1,3})\.\s+(?:A|An|The)\b")
CLAIM_COUNT_ASSERTION_RE = re.compile(r"\b(\d{1,3})\s+claims\b", re.IGNORECASE)
READY_RE = re.compile(r"filing[- ]ready|ready\s+(?:to|for)\s+fil\w*", re.IGNORECASE)
NEGATION_RE = re.compile(r"\b(?:not|never|isn't|aren't|no)\b[\s:*]*$", re.IGNORECASE)
# 'is filing-ready' asserts; 'the gate for calling anything filing-ready'
# merely mentions. Only assertive contexts count.
ASSERTION_CUE_RE = re.compile(
    r"(?:\b(?:is|are|now|deemed|considered|declared)\b|\bstatus\b[^\n]{0,10})[\s:*'\"]*$",
    re.IGNORECASE,
)
DRAFT_MARKER_RE = re.compile(
    r"\bDRAFT\b|DO NOT FILE|\bSUPERSEDED\b|not yet\b", re.IGNORECASE
)
FILING_COPY_MARKER_RE = re.compile(r"FILING[- _]COP", re.IGNORECASE)
IMPURITY_RES = [
    (re.compile(r"\[(?:NOTE|TODO|STRATEGY|INTERNAL|FIXME)\b", re.IGNORECASE), "bracketed commentary"),
    (re.compile(r"^#{1,6}\s*next steps\b", re.IGNORECASE | re.MULTILINE), "'Next steps' section"),
    (re.compile(r"\b\d+\s+critical\b|\bcompliance score\b|\bchecker\b", re.IGNORECASE), "checker/score language"),
    (re.compile(r"<!--"), "HTML comment"),
]
ISO_DATE_RE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")


@dataclass
class PackageIssue(BaseIssue):
    """A package-level consistency issue.

    Attributes:
        check: Which package check produced the issue (stamp_freshness,
            claim_count, status_contradiction, filing_copy_purity,
            date_sanity)
        file: Package-relative path of the primary file involved
    """

    check: str = ""
    file: str = ""


class PackageChecker(BaseAnalyzer):
    """Cross-artifact consistency checker for an assembled package directory."""

    def analyze(self, directory: str) -> dict[str, Any]:
        root = Path(directory).expanduser()
        if not root.is_dir():
            raise ValueError(f"Package directory not found: {directory}")

        files = self._load_files(root)
        if not files:
            raise ValueError(
                f"No text documents (.md/.txt) found under: {directory}"
            )

        self.issues = []
        stamps = self._check_stamps(root, files)
        self._check_claim_counts(files)
        self._check_status_contradictions(files)
        self._check_filing_copy_purity(files)
        self._check_date_sanity(files)

        self._sort_issues(secondary_key=lambda i: (i.check, i.file))
        counts = self._count_by_severity()
        score = max(
            0.0,
            100.0
            - 25.0 * counts["critical"]
            - 10.0 * counts["important"]
            - 2.0 * counts["minor"],
        )
        if counts["total"] == 0:
            summary = (
                f"[OK] Package is internally consistent: {len(files)} documents "
                "scanned, no issues found."
            )
        else:
            summary = (
                f"[!] {counts['critical']} critical, {counts['important']} important, "
                f"{counts['minor']} minor package-consistency issues across "
                f"{len(files)} documents."
            )
        return self._generate_base_report(
            "package_integrity_score",
            score,
            summary,
            additional_data={
                "files_scanned": len(files),
                "stamps": stamps,
            },
        )

    def _issue_to_dict(self, issue: BaseIssue) -> dict[str, Any]:
        return {
            "severity": issue.severity,
            "check": issue.check,
            "file": issue.file,
            "problem": issue.problem,
            "fix": issue.fix,
            "legal_ref": issue.legal_ref,
            "confidence": issue.confidence,
        }

    def _add(self, severity, check, file, problem, fix, confidence="HIGH"):
        self.issues.append(
            PackageIssue(
                severity=severity,
                problem=problem,
                fix=fix,
                legal_ref="package integrity",
                confidence=confidence,
                check=check,
                file=file,
            )
        )

    # ------------------------------------------------------------ loading

    def _load_files(self, root: Path) -> dict[str, str]:
        """Read every small text document, keyed by package-relative path."""
        files: dict[str, str] = {}
        for path in sorted(root.rglob("*")):
            if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
                continue
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            files[path.relative_to(root).as_posix()] = text
        return files

    # ------------------------------------------------------------- stamps

    def _check_stamps(self, root: Path, files: dict[str, str]) -> list[dict[str, Any]]:
        stamps: list[dict[str, Any]] = []
        basenames = {Path(rel).name: rel for rel in files}
        found: list[tuple[str, str, Optional[str]]] = []
        for rel, text in files.items():
            for block in self._blocks(text):
                for match in STAMP_RE.finditer(block):
                    found.append(
                        (rel, match.group(1), self._resolve_target(block, rel, basenames))
                    )
        anchored_values = {stamp for _, stamp, target in found if target}
        for rel, stamp, target in found:
            record = {"file": rel, "stamp": stamp, "target": target}
            if target is None:
                if stamp in anchored_values:
                    # A bare repeat of a hash anchored elsewhere ('re-vet
                    # the flags at hash `x`') is a reference, not a stamp.
                    record["status"] = "reference"
                else:
                    record["status"] = "unanchored"
                    self._add(
                        "IMPORTANT",
                        "stamp_freshness",
                        rel,
                        f"Verification stamp `{stamp}` in {rel} names no "
                        "file in the package — it cannot be recomputed, so "
                        "it verifies nothing.",
                        "Name the stamped file (backticked) in the same "
                        "line or paragraph as the stamp.",
                    )
            else:
                actual = hashlib.sha256(
                    (root / basenames[target]).read_bytes()
                ).hexdigest()
                if actual.startswith(stamp):
                    record["status"] = "fresh"
                else:
                    record["status"] = "stale"
                    self._add(
                        "CRITICAL",
                        "stamp_freshness",
                        rel,
                        f"Stale verification stamp: {rel} records "
                        f"{target} at content hash `{stamp}`, but the "
                        f"file now hashes to `{actual[:12]}`. The file "
                        "was edited after the recorded check.",
                        f"Re-run the recorded check against the current "
                        f"{target} and update the stamp, or revert the "
                        "unreviewed edit.",
                    )
            stamps.append(record)
        return stamps

    @staticmethod
    def _blocks(text: str) -> list[str]:
        """Stamp scope: a table row is its own block; prose splits on blank lines."""
        blocks: list[str] = []
        prose: list[str] = []
        for line in text.splitlines():
            if line.lstrip().startswith("|"):
                if prose:
                    blocks.append("\n".join(prose))
                    prose = []
                blocks.append(line)
            elif line.strip():
                prose.append(line)
            else:
                if prose:
                    blocks.append("\n".join(prose))
                    prose = []
        if prose:
            blocks.append("\n".join(prose))
        return blocks

    @staticmethod
    def _resolve_target(
        block: str, containing: str, basenames: dict[str, str]
    ) -> Optional[str]:
        """The stamped file is a backticked filename in the same block."""
        for ref in FILE_REF_RE.findall(block):
            name = Path(ref).name
            if name in basenames and basenames[name] != containing:
                return name
        return None

    # -------------------------------------------------------- claim count

    def _check_claim_counts(self, files: dict[str, str]) -> None:
        claims_files = {
            rel: text
            for rel, text in files.items()
            if "claim" in Path(rel).name.lower()
        }
        if not claims_files:
            return
        for claims_rel, claims_text in claims_files.items():
            numbers = {
                int(m.group(1))
                for line in claims_text.splitlines()
                if (m := CLAIM_LINE_RE.match(line))
            }
            if not numbers:
                continue
            actual = len(numbers)
            for rel, text in files.items():
                for match in CLAIM_COUNT_ASSERTION_RE.finditer(text):
                    asserted = int(match.group(1))
                    if asserted != actual:
                        self._add(
                            "CRITICAL",
                            "claim_count",
                            rel,
                            f"{rel} asserts {asserted} claims, but "
                            f"{claims_rel} contains {actual} claims. A claim "
                            "was added or removed after that assertion was "
                            "written.",
                            f"Recount and update {rel}, then re-run any "
                            "compliance check recorded against the claim set.",
                        )

    # ----------------------------------------------- status contradictions

    def _check_status_contradictions(self, files: dict[str, str]) -> None:
        ready_hits: list[tuple[str, str]] = []
        draft_hits: list[tuple[str, str]] = []
        for rel, text in files.items():
            for match in READY_RE.finditer(text):
                preceding = text[max(0, match.start() - 40) : match.start()]
                if NEGATION_RE.search(preceding):
                    continue
                if not ASSERTION_CUE_RE.search(preceding):
                    continue
                ready_hits.append((rel, match.group(0)))
            for match in DRAFT_MARKER_RE.finditer(text):
                draft_hits.append((rel, match.group(0)))
        if ready_hits and draft_hits:
            ready_rel, ready_text = ready_hits[0]
            draft_rel, draft_text = draft_hits[0]
            self._add(
                "CRITICAL",
                "status_contradiction",
                ready_rel,
                f"{ready_rel} asserts readiness ('{ready_text}') while "
                f"{draft_rel} carries a draft marker ('{draft_text}'). The "
                "package contradicts itself about its own status.",
                "Either the readiness claim or the draft marker is wrong — "
                "fix the wrong one, then re-check the package.",
            )

    # ------------------------------------------------- filing-copy purity

    def _check_filing_copy_purity(self, files: dict[str, str]) -> None:
        for rel, text in files.items():
            header = "\n".join(
                [ln for ln in text.splitlines() if ln.strip()][:5]
            )
            is_filing_copy = bool(
                FILING_COPY_MARKER_RE.search(rel)
                or FILING_COPY_MARKER_RE.search(header)
            )
            if not is_filing_copy:
                continue
            body = self._strip_filing_copy_marker(text)
            for pattern, label in IMPURITY_RES:
                match = pattern.search(body)
                if match:
                    self._add(
                        "CRITICAL",
                        "filing_copy_purity",
                        rel,
                        f"{rel} is marked as a filing copy but contains "
                        f"{label}: '{match.group(0)[:60]}'. Internal "
                        "commentary must never reach a filing.",
                        "Regenerate the filing copy mechanically from the "
                        "working document, stripping all commentary, and "
                        "diff-check the result.",
                    )

    @staticmethod
    def _strip_filing_copy_marker(text: str) -> str:
        """The marker itself may be an HTML comment — don't flag it as one."""
        return re.sub(
            r"<!--[^>]{0,80}FILING[- _]COP[^>]{0,80}-->", "", text, flags=re.IGNORECASE
        )

    # --------------------------------------------------------- date sanity

    def _check_date_sanity(self, files: dict[str, str]) -> None:
        today = date.today()
        for rel, text in files.items():
            for match in ISO_DATE_RE.finditer(text):
                year, month, day = (int(g) for g in match.groups())
                try:
                    found = date(year, month, day)
                except ValueError:
                    self._add(
                        "MINOR",
                        "date_sanity",
                        rel,
                        f"Malformed date '{match.group(0)}' in {rel}.",
                        "Correct the date.",
                        confidence="MEDIUM",
                    )
                    continue
                if found > today:
                    self._add(
                        "IMPORTANT",
                        "date_sanity",
                        rel,
                        f"Future date '{match.group(0)}' in {rel} — records "
                        "of work cannot postdate today.",
                        "Correct the date (check timezone drift between "
                        "local time and UTC file timestamps).",
                    )
