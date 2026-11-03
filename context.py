"""把检索结果拼成「带编号的参考资料」。

两个要点：
1. 必须编号 —— 模型没法引用没有名字的文字，但能引用 [1]
2. 去重 —— Day 9 的 overlap 会让相邻块内容重复，白占预算
"""

from dataclasses import dataclass

DEFAULT_MAX_CHARS = 3000


@dataclass
class Hit:
    idx: int          # 1-based，对应回答里的 [n]
    text: str
    doc_id: str
    page_no: int
    section: str
    sim: float        # 向量相似度（0–1），不是 RRF 分


def dedupe(hits: list[dict], probe: int = 100) -> list[dict]:
    """用「前 probe 字的互相包含」判断是不是重叠块。"""
    kept: list[dict] = []
    for h in hits:
        head = h["text"].strip()[:probe]
        dup = False
        for k in kept:
            other = k["text"].strip()[:probe]
            if head in k["text"] or other in h["text"]:
                dup = True
                break
        if not dup:
            kept.append(h)
    return kept


def build_context(
    hits: list[dict],
    max_chars: int = DEFAULT_MAX_CHARS,
    use_dedupe: bool = True,
) -> tuple[str, list[Hit]]:
    """返回（拼好的参考资料文本, 编号→来源 的映射表）。"""
    if use_dedupe:
        hits = dedupe(hits)

    used: list[Hit] = []
    blocks: list[str] = []
    total = 0

    for i, h in enumerate(hits, start=1):
        meta = h["meta"]
        page = meta.get("page_no", -1)
        section = (meta.get("section") or "").strip()

        loc = f"第{page}页" if page and page > 0 else "无页码"
        head = f"[{i}]（来源：{meta['doc_id']} {loc}"
        head += f" · {section}）" if section else "）"
        body = h["text"].strip()
        block = f"{head}\n{body}"

        if used and total + len(block) > max_chars:
            break

        blocks.append(block)
        used.append(
            Hit(
                idx=i,
                text=body,
                doc_id=meta["doc_id"],
                page_no=page,
                section=section,
                sim=float(h.get("sim", 0.0)),
            )
        )
        total += len(block) + 2

    return "\n\n".join(blocks), used


def format_sources(used: list[Hit]) -> str:
    if not used:
        return ""
    lines = []
    for h in used:
        sec = f" · {h.section}" if h.section else ""
        loc = f" · 第{h.page_no}页" if h.page_no and h.page_no > 0 else ""
        lines.append(f"[{h.idx}] {h.doc_id}{loc}{sec}  相似度 {h.sim:.2f}")
    return "\n".join(lines)
