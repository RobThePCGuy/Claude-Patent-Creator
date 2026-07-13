"""Package-level consistency checks (check_package).

An external zero-context review caught an assembled filing package whose
per-artifact checks all passed while the PACKAGE lied about itself: a README
claiming "verified" beside a stale draft header, a claim added after its
recorded compliance check, and strategy commentary inside documents marked
for filing. These tests pin the deterministic tooling half of that fix
(the skill half shipped in PR #59).

Stamp convention: a verification stamp is a backticked lowercase-hex prefix
of the SHA-256 of the target file's raw bytes, written near the word "hash"
(e.g. "checked at content hash `ef5315850dfb`"). A stamp that cannot be
recomputed to a match is stale by definition — unverifiable equals
unverified.
"""

import hashlib

import pytest

from mcp_server.package_checker import PackageChecker


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _issues_for(report, check):
    return [i for i in report["issues"] if i["check"] == check]


@pytest.fixture
def checker():
    return PackageChecker()


# ---------------------------------------------------------------- stamps


def test_fresh_stamp_passes(tmp_path, checker):
    spec = tmp_path / "spec.md"
    spec.write_text("The invention.\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        f"`spec.md` checked: 0 critical issues at content hash `{_sha(spec)[:12]}`.\n",
        encoding="utf-8",
    )

    report = checker.analyze(str(tmp_path))

    assert _issues_for(report, "stamp_freshness") == []
    stamps = report["stamps"]
    assert len(stamps) == 1
    assert stamps[0]["status"] == "fresh"
    assert stamps[0]["target"] == "spec.md"


def test_stale_stamp_is_critical(tmp_path, checker):
    spec = tmp_path / "spec.md"
    spec.write_text("The invention.\n", encoding="utf-8")
    stamp = _sha(spec)[:12]
    (tmp_path / "README.md").write_text(
        f"`spec.md` checked: 0 critical issues at content hash `{stamp}`.\n",
        encoding="utf-8",
    )
    # Edit AFTER the recorded check — the exact edit-after-check failure.
    spec.write_text("The invention, edited later.\n", encoding="utf-8")

    report = checker.analyze(str(tmp_path))

    issues = _issues_for(report, "stamp_freshness")
    assert len(issues) == 1
    assert issues[0]["severity"] == "CRITICAL"
    assert "spec.md" in issues[0]["problem"]
    assert stamp in issues[0]["problem"]


def test_unanchored_stamp_is_flagged(tmp_path, checker):
    (tmp_path / "README.md").write_text(
        "Compliance checked at content hash `deadbeef1234`.\n",
        encoding="utf-8",
    )

    report = checker.analyze(str(tmp_path))

    issues = _issues_for(report, "stamp_freshness")
    assert len(issues) == 1
    assert issues[0]["severity"] == "IMPORTANT"
    assert "deadbeef1234" in issues[0]["problem"]


def test_stamp_target_resolves_within_table_row(tmp_path, checker):
    """The KRW README records stamps in a table — one file per row."""
    spec = tmp_path / "spec.md"
    claims = tmp_path / "claims.md"
    spec.write_text("Spec body.\n", encoding="utf-8")
    claims.write_text("1. A method.\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "| File | State |\n| --- | --- |\n"
        f"| `spec.md` | 0 critical at content hash `{_sha(spec)[:12]}` |\n"
        f"| `claims.md` | checked at content hash `{'0' * 12}` |\n",
        encoding="utf-8",
    )

    report = checker.analyze(str(tmp_path))

    by_target = {s["target"]: s["status"] for s in report["stamps"]}
    assert by_target["spec.md"] == "fresh"
    assert by_target["claims.md"] == "stale"


# ------------------------------------------------------------ claim count


def test_claim_count_mismatch_is_critical(tmp_path, checker):
    (tmp_path / "KRW-Claims.md").write_text(
        "1. A method comprising steps.\n"
        "2. The method of claim 1, wherein.\n"
        "3. The method of claim 2, wherein.\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        "Working claims file (17 claims, 3 independent).\n", encoding="utf-8"
    )

    report = checker.analyze(str(tmp_path))

    issues = _issues_for(report, "claim_count")
    assert len(issues) == 1
    assert issues[0]["severity"] == "CRITICAL"
    assert "17" in issues[0]["problem"] and "3" in issues[0]["problem"]


def test_matching_claim_count_passes(tmp_path, checker):
    (tmp_path / "claims-v2.md").write_text(
        "1. A method comprising steps.\n"
        "2. The method of claim 1, wherein.\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("Contains 2 claims.\n", encoding="utf-8")

    report = checker.analyze(str(tmp_path))

    assert _issues_for(report, "claim_count") == []


# ---------------------------------------------------- status contradiction


def test_ready_assertion_beside_draft_marker_is_critical(tmp_path, checker):
    (tmp_path / "README.md").write_text(
        "This package is filing-ready.\n", encoding="utf-8"
    )
    (tmp_path / "claims.md").write_text(
        "DRAFT — not yet compliance-checked.\n1. A method.\n", encoding="utf-8"
    )

    report = checker.analyze(str(tmp_path))

    issues = _issues_for(report, "status_contradiction")
    assert len(issues) == 1
    assert issues[0]["severity"] == "CRITICAL"
    assert "README.md" in issues[0]["problem"]
    assert "claims.md" in issues[0]["problem"]


def test_negated_readiness_is_not_a_contradiction(tmp_path, checker):
    """'Status: NOT filing-ready' is the honest form — never flag it."""
    (tmp_path / "README.md").write_text(
        "**Status: NOT filing-ready.** Open work remains.\n", encoding="utf-8"
    )
    (tmp_path / "claims.md").write_text(
        "DRAFT working claims.\n1. A method.\n", encoding="utf-8"
    )

    report = checker.analyze(str(tmp_path))

    assert _issues_for(report, "status_contradiction") == []


def test_meta_mention_of_readiness_is_not_an_assertion(tmp_path, checker):
    """'the gate for calling anything filing-ready' describes a process —
    only assertive contexts ('is filing-ready', 'Status: filing-ready') count."""
    (tmp_path / "README.md").write_text(
        "A fresh zero-context review is the gate for calling anything "
        "filing-ready.\n",
        encoding="utf-8",
    )
    (tmp_path / "claims.md").write_text(
        "DRAFT working claims.\n1. A method.\n", encoding="utf-8"
    )

    report = checker.analyze(str(tmp_path))

    assert _issues_for(report, "status_contradiction") == []


def test_repeat_mention_of_anchored_stamp_is_not_unanchored(tmp_path, checker):
    """A hash anchored to a file in one paragraph may be referenced bare in
    another ('re-vet the flags at hash `x`') without being a new stamp."""
    spec = tmp_path / "spec.md"
    spec.write_text("Spec body.\n", encoding="utf-8")
    stamp = _sha(spec)[:12]
    (tmp_path / "README.md").write_text(
        f"`spec.md` checked at content hash `{stamp}`.\n\n"
        f"Re-vet the open flags recorded at hash `{stamp}`.\n",
        encoding="utf-8",
    )

    report = checker.analyze(str(tmp_path))

    assert _issues_for(report, "stamp_freshness") == []
    assert [s["status"] for s in report["stamps"] if s["target"]] == ["fresh"]


# ------------------------------------------------------ filing-copy purity


def test_commentary_in_filing_copy_is_critical(tmp_path, checker):
    copies = tmp_path / "filing-copies"
    copies.mkdir()
    (copies / "claims.md").write_text(
        "1. A method comprising steps.\n"
        "[NOTE: broaden this after examiner feedback]\n"
        "## Next steps\n",
        encoding="utf-8",
    )

    report = checker.analyze(str(tmp_path))

    issues = _issues_for(report, "filing_copy_purity")
    assert issues, "commentary inside a filing copy must be flagged"
    assert all(i["severity"] == "CRITICAL" for i in issues)


def test_working_documents_may_contain_commentary(tmp_path, checker):
    (tmp_path / "claims-working.md").write_text(
        "1. A method.\n[NOTE: internal strategy commentary is fine here]\n",
        encoding="utf-8",
    )

    report = checker.analyze(str(tmp_path))

    assert _issues_for(report, "filing_copy_purity") == []


def test_filing_copy_marker_in_header_is_recognized(tmp_path, checker):
    (tmp_path / "claims-final.md").write_text(
        "<!-- FILING COPY -->\n1. A method.\n[TODO tighten]\n",
        encoding="utf-8",
    )

    report = checker.analyze(str(tmp_path))

    assert _issues_for(report, "filing_copy_purity")


# ------------------------------------------------------------- date sanity


def test_future_date_is_flagged(tmp_path, checker):
    (tmp_path / "README.md").write_text(
        "Assembled 2099-01-01 from verified sources.\n", encoding="utf-8"
    )

    report = checker.analyze(str(tmp_path))

    issues = _issues_for(report, "date_sanity")
    assert len(issues) == 1
    assert issues[0]["severity"] == "IMPORTANT"
    assert "2099-01-01" in issues[0]["problem"]


def test_past_dates_pass(tmp_path, checker):
    (tmp_path / "README.md").write_text(
        "Assembled 2026-07-10; reviewed 2026-07-11.\n", encoding="utf-8"
    )

    report = checker.analyze(str(tmp_path))

    assert _issues_for(report, "date_sanity") == []


# ---------------------------------------------------------------- reporting


def test_clean_package_reports_compliant(tmp_path, checker):
    spec = tmp_path / "spec.md"
    spec.write_text("The invention, fully described.\n", encoding="utf-8")
    (tmp_path / "claims.md").write_text("1. A method comprising steps.\n", encoding="utf-8")
    readme = (
        f"Working package, 1 claims. `spec.md` at content hash `{_sha(spec)[:12]}`.\n"
    )
    (tmp_path / "README.md").write_text(readme, encoding="utf-8")

    report = checker.analyze(str(tmp_path))

    assert report["critical_issues"] == 0
    assert report["package_integrity_score"] == 100.0
    assert report["files_scanned"] == 3
    assert "compliant" in report["summary"].lower() or "no issues" in report["summary"].lower()


def test_missing_directory_raises(checker):
    with pytest.raises(ValueError):
        checker.analyze(r"C:\does\not\exist-anywhere-42")


def test_empty_directory_raises(tmp_path, checker):
    with pytest.raises(ValueError):
        checker.analyze(str(tmp_path))


def test_server_registers_check_package_tool():
    """server.py must wire the tool (server.py itself is not importable here)."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    server_src = (root / "mcp_server" / "server.py").read_text(encoding="utf-8")
    assert "register_package_tools" in server_src
    assert "CheckPackageInput" in server_src
