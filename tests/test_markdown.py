from overnight import markdown


def test_headings():
    assert markdown.render("# Title") == "<h1>Title</h1>"
    assert markdown.render("### Deep") == "<h3>Deep</h3>"


def test_paragraph_joins_wrapped_lines():
    assert markdown.render("one\ntwo") == "<p>one two</p>"


def test_blank_line_splits_paragraphs():
    assert markdown.render("one\n\ntwo") == "<p>one</p>\n<p>two</p>"


def test_bold_and_italic():
    assert markdown.render("**bold**") == "<p><strong>bold</strong></p>"
    assert markdown.render("*soft*") == "<p><em>soft</em></p>"


def test_inline_code_is_not_treated_as_markup():
    out = markdown.render("use `a * b * c` here")
    assert "<code>a * b * c</code>" in out
    assert "<em>" not in out


def test_fenced_code_block_keeps_content_verbatim():
    out = markdown.render("```python\nx = 1 < 2\n```")
    assert out == '<pre><code class="lang-python">x = 1 &lt; 2</code></pre>'


def test_unordered_list():
    assert markdown.render("- a\n- b") == "<ul><li>a</li><li>b</li></ul>"


def test_ordered_list():
    assert markdown.render("1. a\n2. b") == "<ol><li>a</li><li>b</li></ol>"


def test_list_continuation_line_joins_previous_item():
    assert markdown.render("- a\n  more") == "<ul><li>a more</li></ul>"


def test_blockquote():
    assert markdown.render("> quoted") == "<blockquote>quoted</blockquote>"


def test_horizontal_rule():
    assert markdown.render("---") == "<hr>"


def test_link():
    out = markdown.render("[docs](https://example.com)")
    assert '<a href="https://example.com">docs</a>' in out


def test_bare_url_is_linked():
    out = markdown.render("see https://example.com for more")
    assert '<a href="https://example.com">https://example.com</a>' in out


def test_javascript_links_are_refused():
    out = markdown.render("[click](javascript:alert(1))")
    assert "javascript:" not in out or "<a" not in out


def test_report_text_cannot_inject_markup():
    out = markdown.render("<script>alert('x')</script>")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_heading_content_is_escaped():
    assert markdown.render("# <b>hi</b>") == "<h1>&lt;b&gt;hi&lt;/b&gt;</h1>"


def test_empty_input():
    assert markdown.render("") == ""


def test_table():
    out = markdown.render("| a | b |\n|---|---|\n| 1 | 2 |")
    assert "<th>a</th><th>b</th>" in out
    assert "<td>1</td><td>2</td>" in out


def test_table_scrolls_in_its_own_container():
    out = markdown.render("| a | b |\n|---|---|\n| 1 | 2 |")
    assert out.startswith('<div class="table-wrap">')


def test_table_with_alignment_markers():
    out = markdown.render("| a | b |\n|:--|--:|\n| 1 | 2 |")
    assert "<th>a</th>" in out


def test_ragged_table_row_is_padded():
    out = markdown.render("| a | b | c |\n|---|---|---|\n| 1 |")
    assert out.count("<td>") == 3


def test_table_cells_render_inline_markup():
    out = markdown.render("| a |\n|---|\n| **bold** |")
    assert "<td><strong>bold</strong></td>" in out


def test_table_cells_are_escaped():
    out = markdown.render("| a |\n|---|\n| <b>x</b> |")
    assert "<b>x</b>" not in out


def test_paragraph_before_table_is_not_absorbed():
    out = markdown.render("intro text\n\n| a |\n|---|\n| 1 |")
    assert out.startswith("<p>intro text</p>")


def test_pipes_without_a_divider_stay_a_paragraph():
    assert markdown.render("a | b") == "<p>a | b</p>"
