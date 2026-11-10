"""MPEP section detection, on heading shapes copied from the real PDFs.

Each case below is text as PyMuPDF extracts it from the USPTO's chapter
PDFs (Rev. 01.2024). Search results cite these numbers, so a missed heading
silently labels pages with the previous section.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mcp_server"))

from mpep_search import find_mpep_headings, locate_mpep_section, mpep_section_marks  # noqa: E402


def numbers(text, chapter):
    return [n for _, n, _ in find_mpep_headings(text, chapter)]


def test_title_wrapping_onto_a_line_that_starts_with_a_number():
    text = (
        "2176-2180  [Reserved]\n2181  Identifying and Interpreting a 35 U.S.C.\n"
        "112(f) or Pre-AIA 35 U.S.C. 112, Sixth\nParagraph Limitation [R-07.2022]\n"
        "This section sets forth guidelines"
    )
    [(_, number, title)] = find_mpep_headings(text, 2100)
    assert number == "2181"
    assert title.endswith("Sixth Paragraph Limitation")


def test_title_ending_in_a_year():
    text = (
        "with the appropriate strike-through.\n601.05(a)  Application Data Sheet (ADS) --\n"
        "Application Filed On or After September 16,\n2012 [R-01.2024]\n [Editor Note"
    )
    assert numbers(text, 600) == ["601.05(a)"]


def test_contents_entries_and_cross_references_are_not_headings():
    contents = "2173.02 \nDetermining Whether Claim\nLanguage is Definite\n2173.03 \nCorrespondence"
    reference = "unavailable, see MPEP §§ 409.02, 604, and 605.\nFor information"
    assert numbers(contents, 2100) == []
    assert numbers(reference, 400) == []


def test_heading_numbered_outside_the_chapter_is_dropped():
    assert numbers("2173.02  Determining Whether Claim\nLanguage is Definite [R-01.2024]", 600) == []


def test_deep_and_reserved_sections():
    text = (
        "2106.04(a)(2)  Abstract Idea Groupings [R-10.2019]\nbody\n"
        "706.02(c)(1)   [Reserved] [R-10.2019]\n [Editor Note"
    )
    assert numbers(text, 2100) == ["2106.04(a)(2)"]
    assert numbers(text, 700) == ["706.02(c)(1)"]


def test_title_line_starting_with_a_statute_number():
    text = (
        "2132.01  Overcoming a Pre-AIA 35 U.S.C.\n102(a) Rejection based on a Printed\n"
        "Publication or Patent [R-10.2019]\n [Editor Note"
    )
    [(_, number, title)] = find_mpep_headings(text, 2100)
    assert number == "2132.01"
    assert title.endswith("Printed Publication or Patent")


def test_a_one_space_line_cannot_swallow_the_next_heading():
    text = (
        "2173.01 See the next section for details.\n"
        "2173.02  Determining Whether Claim Language is Definite [R-01.2024]\n"
    )
    assert numbers(text, 2100) == ["2173.02"]


def section_at(marks, page, offset):
    opening, here = marks[page]
    return locate_mpep_section(opening, here, offset, offset + 1).get("mpep_section")


def test_heading_split_across_a_page_break():
    # mpep-1400.pdf pages 74-75: the heading starts above the footer.
    page74 = (
        "1417  Claim for Priority [R-01.2024]\nbody of 1417\n"
        "1418  Notification of Prior/Concurrent\n"
        "Proceedings and Decisions Thereon, and of\n"
        "1400-74\nRev. 01.2024, November   2024\n"
        "MANUAL OF PATENT EXAMINING PROCEDURE\n§ 1417\n"
    )
    page75 = (
        "Information Known To Be Material to\nPatentability [R-08.2017]\n"
        "37 CFR 1.178  Original patent\n"
        "Rev. 01.2024, November   2024\n1400-75\n§ 1418\nREISSUE\n"
    )
    marks = mpep_section_marks([page74, page75], 1400)
    assert section_at(marks, 0, page74.index("body of 1417")) == "1417"
    assert section_at(marks, 1, page75.index("37 CFR")) == "1418"
    opening, here = marks[1]
    title = locate_mpep_section(opening, here, 0, 1)["section_title"]
    assert title == (
        "Notification of Prior/Concurrent Proceedings and Decisions Thereon, "
        "and of Information Known To Be Material to Patentability"
    )


def test_reserved_range_ends_the_previous_section():
    # mpep-2100.pdf page 506 opens with a reserved range after §2175.
    page = (
        "2176-2180  [Reserved]\n2181  Identifying and Interpreting a 35 U.S.C.\n"
        "112(f) or Pre-AIA 35 U.S.C. 112, Sixth\nParagraph Limitation [R-07.2022]\nbody"
    )
    opening = ("2175", "Form Paragraphs")
    marks = mpep_section_marks([page], 2100)
    _, here = marks[0]
    assert locate_mpep_section(opening, here, 0, 120)["mpep_section"] == "2181"


def test_shortened_passage_cites_only_the_section_it_starts_in():
    from tools.analyzer_tools import _cite

    meta = {"section": "MPEP 600", "mpep_section": "601.05(b), 602"}
    assert _cite(meta) == "MPEP § 601.05(b), 602"
    assert _cite(meta, whole=False) == "MPEP § 601.05(b)"
    assert _cite({"section": "MPEP 600"}, whole=False) == "MPEP 600"
