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


def test_unanchored_stamp_is_flagged(tmp_path, checker):
    (tmp_path / "README.md").write_text(
        "Compliance checked at content hash `deadbeef1234`.\n",
        encoding="utf-8",
    )

    report = checker.analyze(str(tmp_path))

    issues = _issues_for(report, "stamp_freshness")
    assert len(issues) == 1


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
    assert issues


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
    assert issues
    assert issues[0]["severity"] == "CRITICAL"


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


def test_filing_copy_marker_in_header_is_recognized(tmp_path, checker):
    (tmp_path / "claims-final.md").write_text(
        "<!-- FILING COPY -->\n1. A method.\n[TODO tighten]\n",
        encoding="utf-8",
    )

    report = checker.analyze(str(tmp_path))

    assert _issues_for(report, "filing_copy_purity")


# ------------------------------------------------------------- date sanity


# ---------------------------------------------------------------- reporting


def test_missing_directory_raises(checker):
    with pytest.raises(ValueError):
        checker.analyze(r"C:\does\not\exist-anywhere-42")


def test_empty_directory_raises(tmp_path, checker):
    with pytest.raises(ValueError):
        checker.analyze(str(tmp_path))
