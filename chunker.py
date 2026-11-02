import re
from pathlib import Path

from chunk_schema import Chunk
from schemas import ParsedDoc

# 分隔符优先级：段落 → 换行 → 句号 → 问号/感叹号 → 分号 → 逗号 → 空格
DEFAULT_SEPARATORS = ["\n\n", "\n", "。", "！", "？", ";", "；", "，", " "]

# 中文/中文章节标题：一、 / 第一章 / 1.2 / ## 标题
HEADING_RE = re.compile(
    r"^\s*(?:"
    r"第[一二三四五六七八九十百零]+[章节部分篇]"
    r"|[一二三四五六七八九十]+、"
    r"|\d+(?:\.\d+){0,3}[、.\s]"
    r"|#{1,6}\s+\S"
    r")"
)


def _hard_split(text: str, size: int) -> list[str]:
    return [text[i:i + size] for i in range(0, len(text), size)]


def _split_recursive(text: str, size: int, seps: list[str]) -> list[str]:
    """把 text 切成尽量不超过 size 的片段，优先在分隔符处断开。"""
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []
    if not seps:
        return _hard_split(text, size)

    sep, rest = seps[0], seps[1:]
    raw_parts = text.split(sep)

    # 把分隔符拼回去（换行类不拼，避免块首出现空行）
    parts: list[str] = []
    for i, part in enumerate(raw_parts):
        if part:
            suffix = sep if (i < len(raw_parts) - 1 and sep not in ("\n\n", "\n")) else ""
            parts.append(part + suffix)

    chunks: list[str] = []
    buf = ""
    for part in parts:
        if len(part) > size:
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.extend(_split_recursive(part, size, rest))
        elif len(buf) + len(part) <= size:
            buf += part
        else:
            if buf:
                chunks.append(buf)
            buf = part
    if buf:
        chunks.append(buf)

    return [c for c in chunks if c.strip()]


def _apply_overlap(chunks: list[str], overlap: int) -> list[str]:
    """给相邻块加重叠：把上一块的末尾拼到下一块开头。"""
    if overlap <= 0 or len(chunks) < 2:
        return chunks

    out = [chunks[0]]
    for i in range(1, len(chunks)):
        tail = chunks[i - 1][-overlap:]
        out.append(tail + chunks[i])
    return out


def split_sections(text: str) -> list[tuple[str | None, str]]:
    """按标题把全文切成 (标题, 正文)。没有标题时返回 [(None, 全文)]。"""
    lines = text.split("\n")
    sections: list[tuple[str | None, list[str]]] = []
    current_title: str | None = None
    current_lines: list[str] = []

    for line in lines:
        if HEADING_RE.match(line) and line.strip():
            if current_lines and any(l.strip() for l in current_lines):
                sections.append((current_title, current_lines))
            current_title = line.strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines and any(l.strip() for l in current_lines):
        sections.append((current_title, current_lines))

    if not sections:
        return [(None, text)]

    return [(title, "\n".join(body).strip()) for title, body in sections]


def chunk_text(
    text: str,
    size: int = 500,
    overlap: int = 100,
    strategy: str = "recursive",
) -> list[str]:
    """切分纯文本，返回字符串列表。"""
    text = text.strip()
    if not text:
        return []

    if strategy == "fixed":
        return _apply_overlap(_hard_split(text, size), overlap)

    if strategy == "recursive":
        return _apply_overlap(_split_recursive(text, size, DEFAULT_SEPARATORS), overlap)

    if strategy == "structure":
        result: list[str] = []
        for title, body in split_sections(text):
            if not body:
                continue
            # 每块都带上标题，避免检索出来不知道属于哪一节
            prefix = f"【{title}】\n" if title else ""
            budget = max(size - len(prefix), 100)
            pieces = _split_recursive(body, budget, DEFAULT_SEPARATORS)
            for piece in pieces:
                result.append(prefix + piece)
        return _apply_overlap(result, overlap)

    raise ValueError(f"未知策略：{strategy}")


def chunk_doc(
    doc: ParsedDoc,
    size: int = 500,
    overlap: int = 100,
    strategy: str = "recursive",
) -> list[Chunk]:
    """切分一份 ParsedDoc，保留页码等元数据。"""
    chunks: list[Chunk] = []
    offset = 0

    for page in doc.pages:
        if not page.text.strip():
            continue
        pieces = chunk_text(page.text, size, overlap, strategy)
        for piece in pieces:
            chunks.append(
                Chunk(
                    text=piece,
                    doc_id=doc.filename,
                    chunk_index=len(chunks),
                    page_no=page.page_no,
                    section=page.section,
                    char_start=offset,
                    char_end=offset + len(piece),
                )
            )
            offset += len(piece)

    return chunks