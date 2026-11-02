"""解析结果的统一数据结构。

关键设计：保留页码和标题。
后面做「引用来源」时，要能说出"这句话出自第 3 页"，否则用户没法核对。
"""

from dataclasses import dataclass, field


@dataclass
class Page:
    """一页（或一段）文本。"""

    text: str
    page_no: int | None = None       # PDF 有页码，txt 没有
    section: str | None = None       # Word 的标题层级


@dataclass
class ParsedDoc:
    """一份解析完的文档。"""

    filename: str
    source_type: str                  # pdf / docx / txt
    pages: list[Page] = field(default_factory=list)
    meta: dict = field(default_factory=dict)   # 页数、编码、警告等

    @property
    def text(self) -> str:
        """全文拼接，页与页之间用空行隔开。"""
        return "\n\n".join(p.text for p in self.pages if p.text.strip())

    @property
    def char_count(self) -> int:
        return len(self.text)

    def preview(self, n: int = 300) -> str:
        return self.text[:n]
