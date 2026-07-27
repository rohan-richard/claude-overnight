"""A small markdown-to-HTML renderer for embedding reports in the batch page.

Reports are model output, so everything is escaped before any markup is
emitted. This covers the subset `claude -p` actually produces; it is not a
general-purpose markdown implementation.
"""

import html
import re

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_HR = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
_UL_ITEM = re.compile(r"^\s*[-*+]\s+(.*)$")
_OL_ITEM = re.compile(r"^\s*\d+[.)]\s+(.*)$")
_QUOTE = re.compile(r"^\s*>\s?(.*)$")
_FENCE = re.compile(r"^\s*```(\w*)\s*$")
_TABLE_DIVIDER = re.compile(r"^\s*\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)*\|?\s*$")

_CODE_SPAN = re.compile(r"`([^`]+)`")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BOLD = re.compile(r"\*\*(\S(?:.*?\S)?)\*\*")
_ITALIC = re.compile(r"(?<![*\w])\*(\S(?:.*?\S)?)\*(?!\*)")
_BARE_URL = re.compile(r"(?<![\"'>=])\bhttps?://[^\s<>()]+")


def render(text: str) -> str:
    """Render markdown to an HTML fragment."""
    out: list[str] = []
    lines = text.replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]

        fence = _FENCE.match(line)
        if fence:
            i, block = _read_fence(lines, i, fence.group(1))
            out.append(block)
            continue

        if not line.strip():
            i += 1
            continue

        if _HR.match(line):
            out.append("<hr>")
            i += 1
            continue

        heading = _HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            i += 1
            continue

        if "|" in line and i + 1 < len(lines) and _TABLE_DIVIDER.match(lines[i + 1]):
            i, block = _read_table(lines, i)
            out.append(block)
            continue

        if _UL_ITEM.match(line) or _OL_ITEM.match(line):
            i, block = _read_list(lines, i)
            out.append(block)
            continue

        if _QUOTE.match(line):
            i, block = _read_quote(lines, i)
            out.append(block)
            continue

        i, block = _read_paragraph(lines, i)
        out.append(block)

    return "\n".join(out)


def _read_fence(lines: list[str], i: int, lang: str) -> tuple[int, str]:
    body: list[str] = []
    i += 1
    while i < len(lines) and not _FENCE.match(lines[i]):
        body.append(lines[i])
        i += 1
    i += 1  # closing fence, or end of input
    attr = f' class="lang-{html.escape(lang)}"' if lang else ""
    return i, f"<pre><code{attr}>{html.escape(chr(10).join(body))}</code></pre>"


def _split_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


def _read_table(lines: list[str], i: int) -> tuple[int, str]:
    header = _split_row(lines[i])
    i += 2  # header and the divider beneath it
    body: list[list[str]] = []
    while i < len(lines) and "|" in lines[i] and lines[i].strip():
        body.append(_split_row(lines[i]))
        i += 1
    width = len(header)
    head = "".join(f"<th>{_inline(cell)}</th>" for cell in header)
    rows = []
    for row in body:
        # Pad or trim so a ragged row cannot break the table layout.
        cells = (row + [""] * width)[:width]
        rows.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells) + "</tr>")
    table = f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    # Wrapped so a wide table scrolls itself instead of the page.
    return i, f'<div class="table-wrap">{table}</div>'


def _read_list(lines: list[str], i: int) -> tuple[int, str]:
    ordered = bool(_OL_ITEM.match(lines[i]))
    pattern = _OL_ITEM if ordered else _UL_ITEM
    items: list[str] = []
    while i < len(lines):
        match = pattern.match(lines[i])
        if not match:
            # A plain indented line continues the previous item.
            if items and lines[i].startswith((" ", "\t")) and lines[i].strip():
                items[-1] += " " + _inline(lines[i].strip())
                i += 1
                continue
            break
        items.append(_inline(match.group(1)))
        i += 1
    tag = "ol" if ordered else "ul"
    body = "".join(f"<li>{item}</li>" for item in items)
    return i, f"<{tag}>{body}</{tag}>"


def _read_quote(lines: list[str], i: int) -> tuple[int, str]:
    body: list[str] = []
    while i < len(lines):
        match = _QUOTE.match(lines[i])
        if not match:
            break
        body.append(match.group(1))
        i += 1
    return i, f"<blockquote>{_inline(' '.join(body).strip())}</blockquote>"


def _read_paragraph(lines: list[str], i: int) -> tuple[int, str]:
    body: list[str] = []
    while i < len(lines) and lines[i].strip():
        if (_HEADING.match(lines[i]) or _HR.match(lines[i]) or _FENCE.match(lines[i])
                or _UL_ITEM.match(lines[i]) or _OL_ITEM.match(lines[i])
                or _QUOTE.match(lines[i])):
            break
        if ("|" in lines[i] and i + 1 < len(lines)
                and _TABLE_DIVIDER.match(lines[i + 1])):
            break
        body.append(lines[i].strip())
        i += 1
    return i, f"<p>{_inline(' '.join(body))}</p>"


def _inline(text: str) -> str:
    """Escape, then apply inline markup. Code spans are held aside first so
    their contents are never treated as markup."""
    spans: list[str] = []

    def stash(match: re.Match) -> str:
        spans.append(html.escape(match.group(1)))
        return f"\x00{len(spans) - 1}\x00"

    text = _CODE_SPAN.sub(stash, text)
    text = html.escape(text)
    text = _LINK.sub(_link, text)
    text = _BARE_URL.sub(lambda m: f'<a href="{m.group(0)}">{m.group(0)}</a>', text)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _ITALIC.sub(r"<em>\1</em>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{spans[int(m.group(1))]}</code>", text)


def _link(match: re.Match) -> str:
    label, href = match.group(1), match.group(2)
    if not re.match(r"(https?:|mailto:|file:|#|/|\.)", href, re.I):
        return match.group(0)  # refuse javascript: and friends
    return f'<a href="{href}">{label}</a>'
