"""_extract_text_from_html moved from regex tag-stripping to a real HTML
parser (bs4/lxml): regex filters miss malformed closers like ``</script >``
and leave script bodies in the extracted "text" (CodeQL py/bad-tag-filter).
These pin the security-relevant behavior and the structure markers.
"""

from mcp_server import epo_downloaders as ed


def test_script_and_style_bodies_dropped_even_with_malformed_closers():
    html = (
        "<html><head><style>p { color: red }</style></head><body>"
        "<script>var direct = 1;</script>"
        '<script type="text/javascript">var sneaky = 2;</script  >'
        "<p>Real content</p></body></html>"
    )

    text = ed._extract_text_from_html(html)

    assert "direct" not in text
    assert "sneaky" not in text, "malformed closer must not leak script body"
    assert "color" not in text
    assert "Real content" in text


def test_structure_markers_and_entities_survive():
    html = (
        "<h1>Part A</h1><h2>Chapter 1</h2><h3>Section</h3>"
        "<p>Fees &amp; forms<br>second line</p>"
        "<ul><li>one</li><li>two</li></ul>"
    )

    text = ed._extract_text_from_html(html)

    assert "## Part A" in text
    assert "### Chapter 1" in text
    assert "#### Section" in text
    assert "Fees & forms" in text
    assert "second line" in text
    assert "- one" in text
    assert "- two" in text
