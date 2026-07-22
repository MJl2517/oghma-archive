import re

from markupsafe import Markup, escape
from ogma.safe_urls import ExternalHttpUrl, InternalPath, UnsafeUrl


RULE_TEXT_COLOR_CLASSES = {
    "red": "red",
    "\u043a\u0440\u0430\u0441\u043d\u044b\u0439": "red",
    "\u043a\u0440\u0430\u0441\u043d\u0430\u044f": "red",
    "green": "green",
    "\u0437\u0435\u043b\u0451\u043d\u044b\u0439": "green",
    "\u0437\u0435\u043b\u0435\u043d\u044b\u0439": "green",
    "\u0437\u0435\u043b\u0451\u043d\u0430\u044f": "green",
    "\u0437\u0435\u043b\u0435\u043d\u0430\u044f": "green",
    "blue": "blue",
    "\u0441\u0438\u043d\u0438\u0439": "blue",
    "\u0441\u0438\u043d\u044f\u044f": "blue",
    "gold": "gold",
    "\u0437\u043e\u043b\u043e\u0442\u043e": "gold",
    "\u0436\u0451\u043b\u0442\u044b\u0439": "gold",
    "\u0436\u0435\u043b\u0442\u044b\u0439": "gold",
    "aqua": "aqua",
    "\u0431\u0438\u0440\u044e\u0437\u043e\u0432\u044b\u0439": "aqua",
    "purple": "purple",
    "\u0444\u0438\u043e\u043b\u0435\u0442\u043e\u0432\u044b\u0439": "purple",
}


def normalize_rule_reference(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).casefold()


def render_rule_inline(text: str, rule_link_resolver=None, color_classes: dict[str, str] | None = None) -> str:
    tokens = []
    color_classes = color_classes or RULE_TEXT_COLOR_CLASSES

    def hold(html: str) -> str:
        token = f"\u0000RULE_HTML_{len(tokens)}\u0000"
        tokens.append((token, html))
        return token

    def replace_code(match):
        return hold(f"<code>{escape(match.group(1))}</code>")

    def replace_rule_link(match):
        label = match.group(1).strip()
        target = match.group(2).strip()
        link = rule_link_resolver(target) if rule_link_resolver else None
        safe_label = escape(label)
        if not link:
            return hold(f'<span class="rule-broken-link" title="\u041f\u0440\u0430\u0432\u0438\u043b\u043e \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u043e">{safe_label}</span>')
        if link["external"]:
            try:
                href = ExternalHttpUrl.parse(link["href"]).value
            except UnsafeUrl:
                return hold(f'<span class="rule-broken-link">{safe_label}</span>')
            return hold(
                f'<a class="rule-inline-link" href="{escape(href)}" target="_blank" rel="noopener noreferrer">{safe_label}</a>'
            )
        try:
            href = InternalPath.parse(link["href"]).value
        except UnsafeUrl:
            return hold(f'<span class="rule-broken-link">{safe_label}</span>')
        return hold(
            f'<a class="rule-inline-link" href="{escape(href)}" data-open-rule-modal="{escape(link["rule_id"])}">{safe_label}</a>'
        )

    def replace_wiki_link(match):
        label = match.group(1).strip()
        if not label:
            return ""
        return hold(f'<span class="note-wiki-link">{escape(label)}</span>')

    text = re.sub(r"`([^`\n]+)`", replace_code, text)
    text = re.sub(r"\[\[([^\]]+)\]\]", replace_wiki_link, text)
    text = re.sub(r"\[([^\]\n|]+?)\s*\|\s*([^\]\n]+?)\]", replace_rule_link, text)
    rendered = str(escape(text))

    def replace_standard_link(match):
        label = match.group(1).strip()
        href = match.group(2).strip()
        try:
            if href.startswith("/"):
                safe_href = InternalPath.parse(href).value
                target = ""
            else:
                safe_href = ExternalHttpUrl.parse(href).value
                target = ' target="_blank" rel="noopener noreferrer"'
        except UnsafeUrl:
            return match.group(0)
        return f'<a class="rule-inline-link" href="{escape(safe_href)}"{target}>{label}</a>'

    def replace_color(match):
        color_key = normalize_rule_reference(match.group(1))
        color = color_classes.get(color_key)
        if not color:
            return match.group(0)
        return f'<span class="rule-color rule-color-{color}">{match.group(2)}</span>'

    rendered = re.sub(r"\[([^\]\n]+?)\]\(([^)\n]+?)\)", replace_standard_link, rendered)
    rendered = re.sub(r"\{([A-Za-z\u0410-\u042f\u0430-\u044f\u0401\u0451-]+)\|([^{}\n]+)\}", replace_color, rendered)
    rendered = re.sub(r"\*\*([^*\n]+?)\*\*", r"<strong>\1</strong>", rendered)
    rendered = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<em>\1</em>", rendered)
    rendered = re.sub(r"(?<!\w)_([^_\n]+?)_(?!\w)", r"<u>\1</u>", rendered)

    for token, html in tokens:
        rendered = rendered.replace(token, html)
    return rendered


def split_table_row(line: str) -> list[str]:
    """Split a markdown table row, ignoring pipes inside inline Oghma markup."""
    cells = []
    current = []
    square_depth = 0
    brace_depth = 0
    in_code = False
    value = line.strip()
    if value.startswith("|"):
        value = value[1:]
    if value.endswith("|"):
        value = value[:-1]

    for index, char in enumerate(value):
        previous = value[index - 1] if index else ""
        if char == "`" and previous != "\\":
            in_code = not in_code
            current.append(char)
            continue
        if not in_code:
            if char == "[" and previous != "\\":
                square_depth += 1
            elif char == "]" and square_depth:
                square_depth -= 1
            elif char == "{" and previous != "\\":
                brace_depth += 1
            elif char == "}" and brace_depth:
                brace_depth -= 1
            elif char == "|" and not square_depth and not brace_depth:
                cells.append("".join(current).strip())
                current = []
                continue
        current.append(char)

    cells.append("".join(current).strip())
    return cells


def render_rule_content(content: str, rule_link_resolver=None, color_classes: dict[str, str] | None = None) -> Markup:
    lines = (content or "").splitlines()
    html = []
    paragraph = []

    def render_inline(value: str) -> str:
        return render_rule_inline(value, rule_link_resolver, color_classes)

    def flush_paragraph() -> None:
        if paragraph:
            html.append(f"<p>{'<br>'.join(render_inline(line) for line in paragraph)}</p>")
            paragraph.clear()

    def is_table_separator(line: str) -> bool:
        cells = split_table_row(line)
        return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells)

    index = 0
    while index < len(lines):
        line = lines[index].rstrip()
        image_match = re.fullmatch(r"!\[(.*?)\]\((.*?)\)", line.strip())

        if not line.strip():
            flush_paragraph()
            index += 1
            continue

        if image_match:
            flush_paragraph()
            alt, src = image_match.groups()
            try:
                safe_src = InternalPath.parse(src).value
            except UnsafeUrl:
                html.append(f"<p>{escape(alt)}</p>")
                index += 1
                continue
            html.append(f'<figure class="rule-content-image"><img src="{escape(safe_src)}" alt="{escape(alt)}"><figcaption>{escape(alt)}</figcaption></figure>')
            index += 1
            continue

        heading_match = re.fullmatch(r"(#{1,4})\s+(.+)", line.strip())
        if heading_match:
            flush_paragraph()
            level = min(len(heading_match.group(1)) + 1, 5)
            html.append(f"<h{level}>{render_inline(heading_match.group(2))}</h{level}>")
            index += 1
            continue

        if re.fullmatch(r"[-*]\s+.+", line.strip()):
            flush_paragraph()
            items = []
            while index < len(lines) and re.fullmatch(r"[-*]\s+.+", lines[index].strip()):
                items.append(re.sub(r"^[-*]\s+", "", lines[index].strip(), count=1))
                index += 1
            html.append("<ul>" + "".join(f"<li>{render_inline(item)}</li>" for item in items) + "</ul>")
            continue

        if re.fullmatch(r"\d+[.)]\s+.+", line.strip()):
            flush_paragraph()
            items = []
            while index < len(lines) and re.fullmatch(r"\d+[.)]\s+.+", lines[index].strip()):
                items.append(re.sub(r"^\d+[.)]\s+", "", lines[index].strip(), count=1))
                index += 1
            html.append("<ol>" + "".join(f"<li>{render_inline(item)}</li>" for item in items) + "</ol>")
            continue

        if line.strip().startswith("> "):
            flush_paragraph()
            quote_lines = []
            while index < len(lines) and lines[index].strip().startswith("> "):
                quote_lines.append(lines[index].strip()[2:].strip())
                index += 1
            html.append(f"<blockquote>{'<br>'.join(render_inline(item) for item in quote_lines)}</blockquote>")
            continue

        if "|" in line and index + 1 < len(lines) and is_table_separator(lines[index + 1]):
            flush_paragraph()
            headers = split_table_row(line)
            index += 2
            rows = []
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                rows.append(split_table_row(lines[index]))
                index += 1

            head = "".join(f"<th>{render_inline(cell)}</th>" for cell in headers)
            body_rows = []
            for row in rows:
                body_rows.append("<tr>" + "".join(f"<td>{render_inline(cell)}</td>" for cell in row) + "</tr>")
            html.append(f"<div class=\"rule-table-wrap\"><table><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table></div>")
            continue

        paragraph.append(line)
        index += 1

    flush_paragraph()
    return Markup("\n".join(html))


def render_text_content(content: str, rule_link_resolver=None, color_classes: dict[str, str] | None = None) -> Markup:
    rendered = str(render_rule_content(content, rule_link_resolver, color_classes))
    if not rendered.strip():
        rendered = "<p>\u0422\u0435\u043a\u0441\u0442\u0430 \u043f\u043e\u043a\u0430 \u043d\u0435\u0442.</p>"
    return Markup(f'<div class="rich-text">{rendered}</div>')


def render_note_content(content: str, rule_link_resolver=None, color_classes: dict[str, str] | None = None) -> Markup:
    return render_text_content(content, rule_link_resolver, color_classes)
