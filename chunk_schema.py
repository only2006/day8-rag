from dataclasses import dataclass


@dataclass
class Chunk:
    text: str
    doc_id: str
    chunk_index: int
    page_no: int | None = None
    section: str | None = None
    char_start: int = 0
    char_end: int = 0

    @property
    def length(self) -> int:
        return len(self.text)

    def preview(self, n: int = 80) -> str:
        flat = self.text.replace("\n", "⏎")
        return flat[:n] + ("…" if len(flat) > n else "")