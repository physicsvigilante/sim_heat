"""Render the two trusted product Markdown files as static, script-free HTML.

Deliberately bounded syntax, not a general Markdown engine or an upload service.
The committed HTML is generated output; --check detects drift without writing.
"""
from __future__ import annotations
import argparse
import hashlib
import html
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = ('CAPABILITIES', 'AUTHORING')
INLINE = re.compile(r'(`[^`\n]+`|\*\*[^*\n]+\*\*|\[[^\]\n]+\]\([^\s)]+\))')
STYLE = '''
:root{font-family:system-ui,sans-serif;color:#173c43;background:#f5f7f3;line-height:1.7;color-scheme:light}
*{box-sizing:border-box}body{margin:0}header,main,footer{max-width:1120px;margin:auto;padding:24px}
header,footer{border-bottom:1px solid #ccdcd5}nav{display:flex;gap:20px;flex-wrap:wrap}
a{color:#116973;text-underline-offset:3px}a:focus-visible,.table-scroll:focus-visible{outline:3px solid #a65124;outline-offset:4px}
.skip{position:absolute;top:-90px;left:12px;background:white;padding:12px;z-index:2}.skip:focus{top:8px}
h1{font:500 clamp(2rem,4vw,3.3rem)/1.2 Georgia,serif}h2{margin-top:2.1em;line-height:1.3}
p{max-width:90ch}code{overflow-wrap:anywhere;font-size:.91em}pre{white-space:pre-wrap;overflow-wrap:anywhere;padding:18px;background:#e8efeb;border-radius:8px}
.table-scroll{max-width:100%;overflow-x:auto;margin:20px 0;background:white;border:1px solid #cbd9d3;border-radius:8px}
table{width:100%;border-collapse:collapse;min-width:650px}caption{text-align:left;font-weight:700;padding:12px 16px}
th,td{padding:12px 16px;border-top:1px solid #d7e1dc;text-align:left;vertical-align:top}th{background:#e8efeb}td{overflow-wrap:anywhere}
.note,footer{color:#4d676d;font-size:.88rem}main{min-width:0}main:focus{outline:none}
@media(max-width:600px){header,main,footer{padding:18px}pre{padding:12px}}
'''.strip()


def href(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme and parsed.scheme != 'https') or (parsed.netloc and not parsed.scheme):
        raise ValueError(f'unsupported document link: {value}')
    if any(ord(c) < 32 for c in value) or '\\' in value:
        raise ValueError('invalid document link')
    # Only these two documents have generated counterparts. Other links retain
    # their exact original target (including source Markdown / JSON / Python).
    if not parsed.scheme and value in {name + '.md' for name in DOCUMENTS}:
        return value[:-3] + '.html'
    return value


def inline(text: str) -> str:
    result = []
    for part in INLINE.split(text):
        if part.startswith('`') and part.endswith('`'):
            result.append('<code>' + html.escape(part[1:-1]) + '</code>')
        elif part.startswith('**') and part.endswith('**'):
            result.append('<strong>' + html.escape(part[2:-2]) + '</strong>')
        elif part.startswith('[') and '](' in part and part.endswith(')'):
            label, target = part[1:-1].split('](', 1)
            result.append('<a href="' + html.escape(href(target), quote=True) + '">' + html.escape(label) + '</a>')
        else:
            result.append(html.escape(part))
    return ''.join(result)


def cells(line: str) -> list[str]:
    if not line.startswith('|') or not line.endswith('|'):
        raise ValueError('table rows require leading and trailing pipes')
    return [cell.strip() for cell in line[1:-1].split('|')]


def body(markdown: str) -> tuple[str, str]:
    lines = markdown.splitlines()
    output, headings = [], set()
    title, section, i = '', 'Document table', 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith('```'):
            language = line[3:]
            if not re.fullmatch(r'[A-Za-z0-9_-]*', language):
                raise ValueError('unsupported fence language')
            i += 1
            code = []
            while i < len(lines) and lines[i] != '```':
                code.append(lines[i]); i += 1
            if i == len(lines):
                raise ValueError('unclosed code fence')
            output.append('<pre><code class="language-' + language + '">' + html.escape('\n'.join(code)) + '</code></pre>')
            i += 1
            continue
        match = re.fullmatch(r'(#{1,3}) (.+)', line)
        if match:
            level, text = len(match[1]), match[2]
            if level == 1:
                if title:
                    raise ValueError('multiple document titles')
                title = text
            section = text
            anchor = re.sub('[^a-z0-9]+', '-', text.lower()).strip('-')
            if not anchor or anchor in headings:
                raise ValueError('empty/duplicate heading anchor')
            headings.add(anchor)
            output.append(f'<h{level} id="{anchor}">{inline(text)}</h{level}>')
            i += 1
            continue
        if line.startswith('|'):
            header = cells(line)
            i += 1
            if i >= len(lines) or len(cells(lines[i])) != len(header) or not all(re.fullmatch(':?-{3,}:?', c) for c in cells(lines[i])):
                raise ValueError('invalid table separator')
            i += 1
            label = html.escape(section, quote=True)
            table = [f'<div class="table-scroll" tabindex="0" role="region" aria-label="{label}">',
                     '<table><caption>' + label + '</caption><thead><tr>',
                     ''.join('<th scope="col">' + inline(c) + '</th>' for c in header), '</tr></thead><tbody>']
            while i < len(lines) and lines[i].startswith('|'):
                row = cells(lines[i])
                if len(row) != len(header):
                    raise ValueError('inconsistent table width')
                table.append('<tr>' + ''.join('<td>' + inline(c) + '</td>' for c in row) + '</tr>')
                i += 1
            table.append('</tbody></table></div>')
            output.append(''.join(table))
            continue
        paragraph = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].startswith(('#', '|', '```')):
            paragraph.append(lines[i]); i += 1
        output.append('<p>' + inline(' '.join(paragraph)) + '</p>')
    if not title:
        raise ValueError('document title required')
    return title, '\n'.join(output)


def render(raw: bytes, name: str) -> bytes:
    if name not in DOCUMENTS:
        raise ValueError('unknown product document')
    title, content = body(raw.decode('utf-8'))
    digest = hashlib.sha256(raw).hexdigest()
    page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="source-sha256" content="{digest}"><title>{html.escape(title)}</title><style>{STYLE}</style></head>
<body><a class="skip" id="skip-link" href="#main">Skip to main content</a>
<header><nav aria-label="Product documentation"><a href="../index.html">Start</a><a href="../viewer/network/index.html">Thermal explorer</a><a href="CAPABILITIES.html">Capabilities</a><a href="AUTHORING.html">Authoring guide</a></nav></header>
<main id="main" tabindex="-1"><p class="note">Static rendering of <a id="markdown-source" href="{name}.md">the Markdown source</a>. Tables can be scrolled horizontally. Source-code and historical-document links open their original files.</p>
<article id="document">{content}</article>
</main><footer>Generated from {name}.md. Edit the Markdown, then run <code>python -B tools/render_product_docs.py</code>. No scripts, solver or native execution.</footer></body></html>
'''
    return page.encode('utf-8')


def build(root: Path, check: bool = False) -> None:
    for name in DOCUMENTS:
        target = root / 'docs' / (name + '.html')
        expected = render((root / 'docs' / (name + '.md')).read_bytes(), name)
        if check:
            if not target.is_file() or target.read_bytes() != expected:
                raise ValueError(f'{target.name} is missing or stale; rerun tools/render_product_docs.py')
        else:
            target.write_bytes(expected)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        build(ROOT, args.check)
    except (OSError, UnicodeError, ValueError) as exc:
        parser.exit(1, f'Document rendering failed: {exc}\n')
    print('PASS: product documentation HTML matches Markdown.' if args.check else 'Rendered product documentation.')
