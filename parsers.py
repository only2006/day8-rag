"""文档解析：PDF / docx / txt  →  ParsedDoc

三个解析器 + 一套通用清洗。
"""

import re
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader

from schemas import Page, ParsedDoc

# 纯页码行："12" / "- 12 -" / "第 12 页" / "Page 12"
PAGE_NO_RE = re.compile(
    r"^\s*(?:[-—–]\s*)?(?:\d{1,4}|第\s*\d+\s*页|Page\s*\d+)\s*(?:[-—–])?\s*$",
    re.IGNORECASE,
)
# 连续 3 个以上换行 → 2 个
MULTI_NL_RE = re.compile(r"\n{3,}")
# 行内多余空格（含全角空格）
MULTI_SPACE_RE = re.compile(r"[ \t\u3000]{2,}")


def clean_text(text: str) -> str:
    """清洗抽取出来的原始文本：去页码、压缩空白。"""
    if not text:
        return ""

    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip().replace("\u3000", " ")
        if not stripped:
            lines.append("")
            continue
        if PAGE_NO_RE.match(stripped):
            continue
        lines.append(MULTI_SPACE_RE.sub(" ", stripped))

    result = "\n".join(lines)
    result = MULTI_NL_RE.sub("\n\n", result)
    return result.strip()


def parse_pdf(path: Path) -> ParsedDoc:
    reader = PdfReader(str(path))
    pages: list[Page] = []

    for i, page in enumerate(reader.pages, start=1):
        try:
            raw = page.extract_text() or ""
        except Exception:                     # noqa: BLE001
            raw = ""
        pages.append(Page(text=clean_text(raw), page_no=i))

    meta: dict = {"page_count": len(pages), "encrypted": bool(reader.is_encrypted)}

    # 扫描件检测：平均每页字符数太少，说明没有文字层
    avg_chars = sum(len(p.text) for p in pages) / max(len(pages), 1)
    if avg_chars < 20:
        meta["warning"] = "疑似扫描件（无文字层），需要 OCR，本流程无法处理"

    return ParsedDoc(filename=path.name, source_type="pdf", pages=pages, meta=meta)


def parse_docx(path: Path) -> ParsedDoc:
    doc = DocxDocument(str(path))
    blocks: list[str] = []
    sections: list[str] = []
    current_section: str | None = None

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        style = (para.style.name or "").lower()
        if style.startswith("heading") or style.startswith("标题"):
            current_section = text
            sections.append(text)

        blocks.append(text)

    # 表格单独处理：doc.paragraphs 不包含表格内容
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                blocks.append(" | ".join(cells))

    text = clean_text("\n".join(blocks))

    meta = {
        "paragraphs": len(doc.paragraphs),
        "tables": len(doc.tables),
        "sections": sections[:20],
    }
    return ParsedDoc(
        filename=path.name,
        source_type="docx",
        pages=[Page(text=text, section=current_section)],
        meta=meta,
    )


ENCODINGS = ("utf-8", "utf-8-sig", "gbk", "gb18030", "big5")


def parse_txt(path: Path) -> ParsedDoc:
    raw_bytes = path.read_bytes()
    text = ""
    used_enc = None

    for enc in ENCODINGS:
        try:
            text = raw_bytes.decode(enc)
            used_enc = enc
            break
        except UnicodeDecodeError:
            continue

    if used_enc is None:
        text = raw_bytes.decode("utf-8", errors="ignore")
        used_enc = "utf-8(ignore)"

    return ParsedDoc(
        filename=path.name,
        source_type=path.suffix.lstrip(".").lower() or "txt",
        pages=[Page(text=clean_text(text))],
        meta={"encoding": used_enc, "bytes": len(raw_bytes)},
    )


def parse_any(path: Path) -> ParsedDoc:
    """按后缀分发到对应解析器。"""
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return parse_pdf(path)
    if suffix in (".docx", ".doc"):
        return parse_docx(path)
    if suffix in (".txt", ".md", ".csv"):
        return parse_txt(path)

    raise ValueError(f"不支持的文件类型：{suffix}")
