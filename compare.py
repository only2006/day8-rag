import sys
from pathlib import Path

from chunker import chunk_doc
from parsers import parse_any

CONFIGS = [
    {"name": "A 小碎块", "size": 200, "overlap": 0, "strategy": "recursive"},
    {"name": "B 中等+重叠", "size": 500, "overlap": 100, "strategy": "recursive"},
    {"name": "C 结构优先", "size": 500, "overlap": 100, "strategy": "structure"},
]

SENTENCE_END = "。！？；.!?;\n"


def stats(chunks) -> dict:
    if not chunks:
        return {"数量": 0}

    lengths = [c.length for c in chunks]
    # 句子完整率：以句末标点或换行结尾的块占比
    complete = sum(1 for c in chunks if c.text.strip()[-1] in SENTENCE_END)
    # 截断率：块长度正好等于 size 的，大概率是被硬切的
    return {
        "块数": len(chunks),
        "平均长度": round(sum(lengths) / len(lengths), 1),
        "最短": min(lengths),
        "最长": max(lengths),
        "句子完整率": f"{complete / len(chunks) * 100:.0f}%",
        "总字符": sum(lengths),
    }


def main() -> int:
    if len(sys.argv) < 2:
        print("用法：uv run compare.py samples/某文件.pdf")
        return 1

    path = Path(sys.argv[1])
    doc = parse_any(path)
    print(f"文档：{doc.filename}  字符数 {doc.char_count}\n")

    for cfg in CONFIGS:
        chunks = chunk_doc(doc, cfg["size"], cfg["overlap"], cfg["strategy"])
        s = stats(chunks)
        print(f"=== {cfg['name']}  (size={cfg['size']}, overlap={cfg['overlap']}, "
              f"{cfg['strategy']}) ===")
        for k, v in s.items():
            print(f"  {k:8} {v}")
        print("  前 2 块预览：")
        for c in chunks[:2]:
            print(f"    [{c.chunk_index}] len={c.length}  {c.preview(70)!r}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())