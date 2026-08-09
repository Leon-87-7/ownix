"""Netscape bookmark export parsing — shared by the bookmark import processor.

Structure: an <H3> names the folder that follows; the next <DL> opens that
folder's scope, closed by the matching </DL>. <A HREF> entries anywhere in
that scope belong to the innermost open folder. Extraction only — coerce_url
(the single "is this a URL" implementation, #490) decides what's usable.
"""

from __future__ import annotations

from html.parser import HTMLParser


class _BookmarkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.entries: list[dict] = []
        self._folder_stack: list[str | None] = []
        self._pending_folder_name: str | None = None
        self._in_h3 = False
        self._h3_text: list[str] = []
        self._in_a = False
        self._a_attrs: dict[str, str | None] = {}
        self._a_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "h3":
            self._in_h3 = True
            self._h3_text = []
        elif tag == "dl":
            # The folder named by the most recent </H3> (if any) opens here.
            self._folder_stack.append(self._pending_folder_name)
            self._pending_folder_name = None
        elif tag == "a":
            self._in_a = True
            self._a_attrs = dict(attrs)
            self._a_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "h3":
            self._in_h3 = False
            self._pending_folder_name = "".join(self._h3_text)
        elif tag == "dl":
            if self._folder_stack:
                self._folder_stack.pop()
        elif tag == "a":
            self._in_a = False
            folder = next((f for f in reversed(self._folder_stack) if f), None)
            self.entries.append(
                {
                    "href": self._a_attrs.get("href") or "",
                    "title": "".join(self._a_text).strip(),
                    "add_date": self._a_attrs.get("add_date"),
                    "folder": folder,
                }
            )

    def handle_data(self, data: str) -> None:
        if self._in_h3:
            self._h3_text.append(data)
        elif self._in_a:
            self._a_text.append(data)


def parse_bookmarks_html(html: str) -> list[dict]:
    """Extract every <A HREF> entry as {href, title, add_date, folder}.

    `folder` is the innermost open <H3> name at the entry's position (not
    stripped — the caller decides whitespace handling), or None at the root.
    Non-http(s) hrefs (chrome://, file://, javascript:) are returned as-is;
    filtering is the caller's job via coerce_url.
    """
    parser = _BookmarkParser()
    parser.feed(html)
    return parser.entries
