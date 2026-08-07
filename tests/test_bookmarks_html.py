from src.utils.bookmarks_html import parse_bookmarks_html

_SAMPLE = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
<!-- This is an automatically generated file. -->
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<TITLE>Bookmarks</TITLE>
<H1>Bookmarks</H1>
<DL><p>
    <DT><H3 ADD_DATE="1600000000">Bookmarks bar</H3>
    <DL><p>
        <DT><A HREF="https://github.com/Leon-87-7" ADD_DATE="1752572196">GitHub profile</A>
        <DT><H3 ADD_DATE="1600000001">Investing</H3>
        <DL><p>
            <DT><H3 ADD_DATE="1600000002">screeners</H3>
            <DL><p>
                <DT><A HREF="https://finviz.com" ADD_DATE="1600000003">Finviz</A>
            </DL><p>
        </DL><p>
        <DT><A HREF="https://mail.google.com/mail/u/0/?tab=rm&amp;ogbl#inbox" ADD_DATE="1609949322">Gmail</A>
        <DT><A HREF="chrome://bookmarks/">Chrome bookmarks</A>
        <DT><A HREF="javascript:(function(){alert(1)})()">Bookmarklet</A>
    </DL><p>
</DL><p>
"""


def test_parses_top_level_and_nested_entries():
    entries = parse_bookmarks_html(_SAMPLE)
    hrefs = [e["href"] for e in entries]
    assert "https://github.com/Leon-87-7" in hrefs
    assert "https://finviz.com" in hrefs
    assert "https://mail.google.com/mail/u/0/?tab=rm&ogbl#inbox" in hrefs


def test_captures_title_and_add_date():
    entries = parse_bookmarks_html(_SAMPLE)
    github = next(e for e in entries if e["href"] == "https://github.com/Leon-87-7")
    assert github["title"] == "GitHub profile"
    assert github["add_date"] == "1752572196"


def test_leaf_folder_is_the_innermost_h3():
    entries = parse_bookmarks_html(_SAMPLE)
    github = next(e for e in entries if e["href"] == "https://github.com/Leon-87-7")
    assert github["folder"] == "Bookmarks bar"

    finviz = next(e for e in entries if e["href"] == "https://finviz.com")
    assert finviz["folder"] == "screeners"


def test_top_level_entry_after_nested_folder_closes_uses_root_folder():
    """Gmail sits back at the Bookmarks bar level, after the Investing/screeners
    subtree's </DL> tags have closed — the folder stack must have unwound."""
    entries = parse_bookmarks_html(_SAMPLE)
    gmail = next(e for e in entries if "mail.google.com" in e["href"])
    assert gmail["folder"] == "Bookmarks bar"


def test_html_entities_in_href_are_decoded():
    entries = parse_bookmarks_html(_SAMPLE)
    gmail = next(e for e in entries if "mail.google.com" in e["href"])
    assert "&ogbl" in gmail["href"]
    assert "&amp;" not in gmail["href"]


def test_non_http_hrefs_are_still_returned_unfiltered():
    """Filtering (coerce_url) is the caller's job, not the parser's — the
    parser only extracts structure."""
    entries = parse_bookmarks_html(_SAMPLE)
    hrefs = [e["href"] for e in entries]
    assert "chrome://bookmarks/" in hrefs
    assert any(h.startswith("javascript:") for h in hrefs)


def test_missing_add_date_yields_none_not_a_crash():
    html = (
        "<!DOCTYPE NETSCAPE-Bookmark-file-1>\n"
        "<DL><p><DT><A HREF=\"https://example.com\">No date</A></DL><p>"
    )
    entries = parse_bookmarks_html(html)
    assert entries[0]["add_date"] is None


def test_empty_document_yields_no_entries():
    assert parse_bookmarks_html("<!DOCTYPE NETSCAPE-Bookmark-file-1>\n") == []


def test_folder_name_with_trailing_whitespace_preserved_for_caller_to_strip():
    html = (
        "<!DOCTYPE NETSCAPE-Bookmark-file-1>\n"
        "<DL><p><DT><H3>Trading </H3>\n"
        "<DL><p><DT><A HREF=\"https://example.com\">x</A></DL><p></DL><p>"
    )
    entries = parse_bookmarks_html(html)
    assert entries[0]["folder"] == "Trading "
