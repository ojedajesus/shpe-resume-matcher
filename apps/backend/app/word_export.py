"""Editable Word resume exports from saved data; no AI or browser required."""
from html.parser import HTMLParser
from io import BytesIO
import re

from docx import Document
from docx.shared import Inches, Mm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT

from app.schemas.models import ResumeData, SectionMeta

DEFAULT_SECTIONS = [
    ("personalInfo", "Personal Info", "personalInfo"),
    ("summary", "Summary", "text"),
    ("workExperience", "Experience", "itemList"),
    ("education", "Education", "itemList"),
    ("personalProjects", "Projects", "itemList"),
    ("additional", "Skills & Awards", "stringList"),
]


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.suppressed = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.suppressed += 1
        elif not self.suppressed and tag in {"br", "p", "li", "div"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.suppressed = max(0, self.suppressed - 1)
        elif not self.suppressed and tag in {"p", "li", "div"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.suppressed:
            self.parts.append(data)


def plain_text(value: str | None) -> str:
    """Strip editor markup and XML-invalid controls without executing content."""
    value = value or ""
    if re.search(r"</?(?:p|div|br|strong|em|b|i|u|a|ul|ol|li|span|script|style)\b", value, re.I):
        parser = _Text()
        parser.feed(value)
        value = "".join(parser.parts)
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]", "", value)
    return "\n".join(line.strip() for line in value.splitlines() if line.strip())


def render_resume_docx(
    data: ResumeData, *, page_size: str = "A4",
    margins: tuple[int, int, int, int] = (10, 10, 10, 10),
    section_spacing: int = 3, item_spacing: int = 2, line_height: int = 3,
    font_size: int = 3, header_scale: int = 3,
    header_font: str = "serif", body_font: str = "sans-serif", compact: bool = False,
) -> bytes:
    """Editable single-column layout using the preview's typography and spacing."""
    doc = Document()
    section = doc.sections[0]
    section.page_width = Inches(8.5) if page_size == "LETTER" else Mm(210)
    section.page_height = Inches(11) if page_size == "LETTER" else Mm(297)
    section.top_margin, section.bottom_margin, section.left_margin, section.right_margin = map(Mm, margins)
    width = section.page_width - section.left_margin - section.right_margin
    # CSS pixels are 3/4 of a Word point. Families match the Windows browser's
    # serif, system sans, and monospace choices; Word can substitute if absent.
    base = (11, 12, 14, 15, 16)[font_size - 1] * .75
    multiplier = .6 if compact else 1
    item_gap = (2, 4, 8, 12, 16)[item_spacing - 1] * .75 * multiplier
    section_gap = (6, 10, 16, 20, 24)[section_spacing - 1] * .75 * multiplier
    line = (1.15, 1.25, 1.35, 1.45, 1.55)[line_height - 1] * (.92 if compact else 1)
    families = {"serif": "Georgia", "sans-serif": "Segoe UI", "mono": "Consolas"}

    def font(style, family, size, bold=False, color="1F2937"):
        style.font.name = family
        style.font.size = Pt(size)
        style.font.bold = bold
        style.font.color.rgb = RGBColor.from_string(color)
        # Remove theme overrides inherited from python-docx's template.
        fonts = style.element.get_or_add_rPr().find(qn("w:rFonts"))
        for attr in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
            fonts.attrib.pop(qn("w:" + attr), None)
        style.paragraph_format.space_before = Pt(0)
        style.paragraph_format.space_after = Pt(0)
        style.paragraph_format.line_spacing = Pt(size * line)
        for border in style.element.xpath("./w:pPr/w:pBdr"):
            border.getparent().remove(border)

    font(doc.styles["Normal"], families[body_font], base)
    font(doc.styles["List Bullet"], families[body_font], base * .92)
    font(doc.styles["Title"], families[header_font], base * (1.5, 1.75, 2, 2.25, 2.5)[header_scale - 1], True, "000000")
    font(doc.styles["Heading 1"], families[header_font], base * (1, 1.1, 1.2, 1.3, 1.4)[header_scale - 1], True, "000000")
    doc.styles["Heading 1"].paragraph_format.space_before = Pt(section_gap)
    doc.styles["Heading 1"].paragraph_format.space_after = Pt(item_gap)
    doc.styles["Heading 1"].paragraph_format.keep_with_next = True
    doc.core_properties.author = ""
    doc.core_properties.last_modified_by = ""
    doc.core_properties.title = ""

    def rule(p, size="6"):
        borders = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        for key, value in {"val": "single", "sz": size, "space": "2", "color": "9CA3AF"}.items():
            bottom.set(qn("w:" + key), value)
        borders.append(bottom)
        p._p.get_or_add_pPr().append(borders)

    def paragraph(text, *, bold=None, style=None):
        cleaned = plain_text(text)
        if not cleaned:
            return
        if style == "Heading 1":
            cleaned = cleaned.upper()
        p = doc.add_paragraph(style=style)
        p.add_run(cleaned).bold = bold
        if style == "Heading 1":
            rule(p)
        return p

    def small(p, *, mono=False, factor=.92):
        if p is not None:
            for run in p.runs:
                run.font.name = "Consolas" if mono else families[body_font]
                run.font.size = Pt(base * factor)
            p.paragraph_format.line_spacing = Pt(base * factor * line)

    def row(left, right, *, bold=False, subtitle=False):
        p = paragraph(left, bold=bold)
        if p is None:
            p = doc.add_paragraph()
        p.paragraph_format.tab_stops.add_tab_stop(width, WD_TAB_ALIGNMENT.RIGHT)
        if right:
            run = p.add_run("\t" + plain_text(right))
            run.bold = False
            run.font.name = families[body_font] if subtitle else "Consolas"
            run.font.size = Pt(base * (.95 if subtitle else .75))
            run.font.color.rgb = RGBColor.from_string("374151" if subtitle else "4B5563")
        p.paragraph_format.space_after = Pt(item_gap if subtitle else item_gap * .6)
        if subtitle:
            small(p, factor=.95)
        p.paragraph_format.keep_with_next = True
        return p

    def items(entries):
        for index, item in enumerate(entries):
            if getattr(item, "institution", None) is not None:
                title, subtitle = item.institution, item.degree
            else:
                title = getattr(item, "title", None) or getattr(item, "name", "")
                subtitle = getattr(item, "company", None) or getattr(item, "role", None) or getattr(item, "subtitle", None)
            first = len(doc.paragraphs)
            p = row(title, item.years, bold=True)
            p.paragraph_format.space_before = Pt(item_gap if index else 0)
            if subtitle or getattr(item, "location", None):
                row(subtitle, getattr(item, "location", None), subtitle=True)
            for key in ("github", "website"):
                p = paragraph(getattr(item, key, None))
                small(p, mono=True, factor=.75)
            description = item.description
            if isinstance(description, str):
                small(paragraph(description))
            else:
                styles = getattr(item, "descriptionStyles", [])
                for index, text in enumerate(description or []):
                    plain = index < len(styles) and styles[index] == "plain"
                    p = paragraph(text, style=None if plain else "List Bullet")
                    if p is not None:
                        small(p)
                        p.paragraph_format.space_after = Pt(item_gap * .75)
                        if not plain:
                            p.paragraph_format.left_indent = Pt(18)
                            p.paragraph_format.first_line_indent = Pt(-9)
            # Keep an entry's title with its content, while allowing long
            # description lists to flow naturally across pages.
            if len(doc.paragraphs) > first:
                doc.paragraphs[-1].paragraph_format.keep_with_next = False

    metadata = data.sectionMeta or [SectionMeta(id=key, key=key, displayName=label, sectionType=kind, order=index) for index, (key, label, kind) in enumerate(DEFAULT_SECTIONS)]
    visible = sorted((s for s in metadata if s.isVisible), key=lambda s: s.order)
    if any(s.key == "personalInfo" for s in visible):
        info = data.personalInfo
        p = paragraph(info.name.upper(), style="Title")
        if p is not None:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_after = Pt(3)
            p.paragraph_format.keep_with_next = True
        p = paragraph(info.title.upper())
        if p is not None:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            small(p, mono=True, factor=.82)
            p.paragraph_format.space_after = Pt(9)
            p.paragraph_format.keep_with_next = True
        contacts = [(info.email, "mailto:"), (info.phone, "tel:"), (info.location, ""),
                    (info.website, "https://"), (info.linkedin, "https://"), (info.github, "https://")]
        if any(value for value, _ in contacts):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            used = 0
            max_chars = (width / 12700) / (base * .82 * .6)
            for value, prefix in contacts:
                if not value:
                    continue
                value = plain_text(value)
                if used:
                    if used + len(value) + 2 > max_chars:
                        p.add_run("\n")
                        used = 0
                    else:
                        p.add_run(", ")
                        used += 2
                if prefix:
                    target = value if value.startswith(("https://", "http://")) else prefix + value
                    link = OxmlElement("w:hyperlink")
                    link.set(qn("r:id"), p.part.relate_to(target, RT.HYPERLINK, is_external=True))
                    run = OxmlElement("w:r")
                    props = OxmlElement("w:rPr")
                    fonts = OxmlElement("w:rFonts")
                    fonts.set(qn("w:ascii"), "Consolas")
                    fonts.set(qn("w:hAnsi"), "Consolas")
                    props.append(fonts)
                    for tag, val in (("sz", str(round(base * .82 * 2))), ("color", "4B5563"), ("u", "single")):
                        element = OxmlElement("w:" + tag)
                        element.set(qn("w:val"), val)
                        props.append(element)
                    run.append(props)
                    text = OxmlElement("w:t")
                    text.text = value
                    run.append(text)
                    link.append(run)
                    p._p.append(link)
                else:
                    p.add_run(value)
                used += len(value)
            small(p, mono=True, factor=.82)
            # A different border width prevents Word merging this paragraph's
            # rule with the next section heading's border.
            rule(p, size="5")
            p.paragraph_format.space_after = Pt(item_gap * 1.25)
            p.paragraph_format.keep_with_next = True
    for meta in visible:
        if meta.key == "personalInfo":
            continue
        if meta.isDefault:
            value = getattr(data, meta.key, None)
            if meta.key == "additional":
                if not any(data.additional.model_dump().values()):
                    continue
                paragraph(meta.displayName, style="Heading 1")
                labels = {"technicalSkills": "Technical Skills", "languages": "Languages", "certificationsTraining": "Certifications and Training", "awards": "Awards"}
                for key, label in labels.items():
                    values = getattr(data.additional, key)
                    if values:
                        p = doc.add_paragraph()
                        p.add_run(label + ": ").bold = True
                        p.add_run(", ".join(plain_text(v) for v in values))
                        small(p)
                        p.paragraph_format.space_after = Pt(item_gap * .6)
            elif value:
                paragraph(meta.displayName, style="Heading 1")
                if isinstance(value, str):
                    p = paragraph(value)
                    if p is not None:
                        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                elif isinstance(value, list):
                    items(value)
        else:
            custom = data.customSections.get(meta.key)
            if custom is None or not (custom.text or custom.items or custom.strings):
                continue
            paragraph(meta.displayName, style="Heading 1")
            if custom.text:
                paragraph(custom.text)
            if custom.items:
                items(custom.items)
            for text in custom.strings or []:
                paragraph(text, style="List Bullet")
    output = BytesIO()
    doc.save(output)
    return output.getvalue()
