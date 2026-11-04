"""Minimal Markdown -> DOCX converter used for the final documents.

Supports: '#'..'####' headings, paragraphs with **bold** and *italic*, '- ' bullets, '1. ' numbered
items, pipe tables (first row = header), fenced code blocks, images '![caption](path)' (auto-numbered
"Figure n."), table captions written as a paragraph starting with 'Table n.' immediately before a table,
and '---' page breaks.
"""
import re

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.shared import Inches, Pt, RGBColor


def _runs(par, text, size=None):
    for tok in re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)", text):
        if not tok:
            continue
        if tok.startswith("**"):
            r = par.add_run(tok[2:-2]); r.bold = True
        elif tok.startswith("`"):
            r = par.add_run(tok[1:-1]); r.font.name = "Consolas"
        elif tok.startswith("*") and len(tok) > 2:
            r = par.add_run(tok[1:-1]); r.italic = True
        else:
            r = par.add_run(tok)
        if size:
            r.font.size = Pt(size)


def convert(md, out_path, title=None, base_font=10.5):
    d = Document()
    st = d.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(base_font)
    for s in ("Heading 1", "Heading 2", "Heading 3"):
        d.styles[s].font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
    if title:
        d.add_heading(title, 0)
    lines = md.split("\n")
    i, fig = 0, 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            j = i + 1
            buf = []
            while j < len(lines) and not lines[j].startswith("```"):
                buf.append(lines[j]); j += 1
            p = d.add_paragraph(); r = p.add_run("\n".join(buf)); r.font.name = "Consolas"; r.font.size = Pt(8.5)
            i = j + 1; continue
        if ln.strip() == "---":
            d.add_paragraph().add_run().add_break(WD_BREAK.PAGE); i += 1; continue
        m = re.match(r"^(#{1,4}) (.*)", ln)
        if m:
            d.add_heading(m.group(2), level=len(m.group(1))); i += 1; continue
        m = re.match(r"^!\[(.*)\]\((.*)\)", ln)
        if m:
            fig += 1
            d.add_picture(m.group(2), width=Inches(6.5))
            d.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            cap = d.add_paragraph(); _runs(cap, f"**Figure {fig}.** {m.group(1)}", size=9)
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            i += 1; continue
        if ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            ncol = max(len(r) for r in rows)
            t = d.add_table(rows=0, cols=ncol); t.style = "Light Grid Accent 1"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
            fs = 8 if ncol > 6 else 8.5
            for k, r in enumerate(rows):
                cells = t.add_row().cells
                for c in range(ncol):
                    txt = r[c] if c < len(r) else ""
                    cells[c].text = ""
                    _runs(cells[c].paragraphs[0], f"**{txt}**" if k == 0 and txt else txt, size=fs)
            d.add_paragraph(); continue
        m = re.match(r"^(\s*)- (.*)", ln)
        if m:
            p = d.add_paragraph(style="List Bullet 2" if len(m.group(1)) >= 2 else "List Bullet")
            _runs(p, m.group(2)); i += 1; continue
        m = re.match(r"^(\d+)\. (.*)", ln)
        if m:
            p = d.add_paragraph(style="List Number"); _runs(p, m.group(2)); i += 1; continue
        if ln.strip() == "":
            i += 1; continue
        # paragraph: join consecutive plain lines
        buf = [ln]
        while i + 1 < len(lines) and lines[i + 1].strip() and not re.match(r"^(#|!\[|\||- |\s+- |\d+\. |```|---)", lines[i + 1]):
            i += 1; buf.append(lines[i])
        p = d.add_paragraph()
        text = " ".join(x.strip() for x in buf)
        if re.match(r"^Table \d+\.", text):
            _runs(p, f"**{text}**", size=9.5)
        else:
            _runs(p, text)
        i += 1
    d.save(out_path)
