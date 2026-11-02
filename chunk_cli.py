import argparse
import json
from dataclasses import asdict
from pathlib import Path
from chunker import chunk_doc, split_sections
from parsers import parse_any
SUPPORTED = {".pdf", ".docx", ".doc", ".txt", ".md", ".csv"}
SENTENCE_END = "。！？；.!?;\n"
def collect_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    if target.is_dir():
        return sorted(p for p in target.iterdir() if p.suffix.lower() in SUPPORTED)
    return []
def sentence_complete_rate(chunks) -> float:
    if not chunks:
        return 0.0
    ok = sum(1 for c in chunks if c.text.strip()[-1] in SENTENCE_END)
    return ok / len(chunks) * 100
def report(path: Path, args) -> list[dict]:
    try:
        doc = parse_any(path)
    except Exception as exc:                      # noqa: BLE001
        print(f"[FAIL] {path.name}  解析失败：{exc}")
        return []
    if args.sections:
        print(f"\n[FILE] {path.name}")
        secs = split_sections(doc.text)
        print(f"  识别到 {len(secs)} 个章节：")
        for i, (title, body) in enumerate(secs):
            t = title if title else "(无标题)"
            print(f"    [{i}] {t}  ——  正文 {len(body)} 字")
        return []
    chunks = chunk_doc(doc, args.size, args.overlap, args.strategy)
    if not chunks:
        print(f"\n[FILE] {path.name}  没有产出任何块（文档可能是空的，或者是扫描件）")
        return []
    lengths = [c.length for c in chunks]
    avg = sum(lengths) / len(lengths)
    print(f"\n{'=' * 62}")
    print(f"[FILE] {doc.filename}   原文 {doc.char_count} 字  "
          f"→  {len(chunks)} 块")
    print(f"       参数：size={args.size} overlap={args.overlap} "
          f"strategy={args.strategy}")
    print(f"       平均 {avg:.0f} 字 | 最短 {min(lengths)} | 最长 {max(lengths)}")
    print(f"       句子完整率 {sentence_complete_rate(chunks):.0f}%")
    # 常见异常提醒
    if len(chunks) == 1:
        print("       [WARN] 只有 1 块：文档太短，或 size 设得太大，调参看不出效果")
    if avg < args.size * 0.5:
        print("       [WARN] 平均长度不到 size 的一半：分隔符太密，切分已退化")
    if avg > args.size * 1.3:
        print("       [WARN] 平均长度明显超过 size：overlap 太大，或前缀占用过多")
    print("-" * 62)
    for c in chunks[: args.show]:
        print(f"[{c.chunk_index:03d}] len={c.length:4d} "
              f"page={c.page_no} section={c.section or '-'}")
        print(f"      {c.preview(120)!r}")
    if len(chunks) > args.show:
        print(f"  …… 还有 {len(chunks) - args.show} 块未显示，用 --show 调整")
    return [asdict(c) for c in chunks]
def main() -> int:
    parser = argparse.ArgumentParser(description="切分调试工具")
    parser.add_argument("target", help="文件或目录")
    parser.add_argument("--size", type=int, default=500)
    parser.add_argument("--overlap", type=int, default=100)
    parser.add_argument("--strategy", default="recursive",
                        choices=["fixed", "recursive", "structure"])
    parser.add_argument("--show", type=int, default=3, help="每个文件预览几块")
    parser.add_argument("--sections", action="store_true", help="只打印章节切分结果")
    parser.add_argument("--out", default=None, help="导出 JSON 到该路径")
    args = parser.parse_args()
    target = Path(args.target)
    if not target.exists():
        print(f"路径不存在：{target}")
        return 1
    files = collect_files(target)
    if not files:
        print(f"{target} 里没有支持的文档（支持：{sorted(SUPPORTED)}）")
        return 1
    all_chunks: list[dict] = []
    for f in files:
        all_chunks.extend(report(f, args))
    if args.sections:
        return 0
    print(f"\n合计 {len(all_chunks)} 块")
    if args.out and all_chunks:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(all_chunks, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"已导出：{out}")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())