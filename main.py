"""Day 8 · 文档解析 CLI

用法：
    uv run main.py samples/report.pdf
    uv run main.py samples/                 # 批量
    uv run main.py samples/ --out out/      # 顺便存成 txt
"""

import sys
from pathlib import Path

from parsers import parse_any

SUPPORTED = {".pdf", ".docx", ".doc", ".txt", ".md", ".csv"}


def process(path: Path, out_dir: Path | None) -> None:
    try:
        doc = parse_any(path)
    except Exception as exc:                      # noqa: BLE001
        print(f"[FAIL] {path.name}  解析失败：{exc}")
        return

    print(f"\n{'=' * 60}")
    print(f"[FILE] {doc.filename}  ({doc.source_type})")
    print(f"       字符数：{doc.char_count}   页/段：{len(doc.pages)}")
    if doc.meta:
        print(f"       元信息：{doc.meta}")
    if doc.meta.get("warning"):
        print(f"       [WARN] {doc.meta['warning']}")
    print("-" * 60)
    print(doc.preview(300))
    print("-" * 60)

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{path.stem}.txt"
        out_file.write_text(doc.text, encoding="utf-8")
        print(f"       [SAVE] {out_file}")


def main(argv: list[str]) -> int:
    args = argv[1:]
    out_dir: Path | None = None

    if "--out" in args:
        idx = args.index("--out")
        if idx + 1 < len(args):
            out_dir = Path(args[idx + 1])
            del args[idx:idx + 2]

    if not args:
        print("用法：uv run main.py <文件或目录> [--out 输出目录]")
        return 1

    target = Path(args[0])
    if not target.exists():
        print(f"路径不存在：{target}")
        return 1

    if target.is_dir():
        files = [p for p in target.iterdir() if p.suffix.lower() in SUPPORTED]
        if not files:
            print(f"{target} 里没有支持的文档（支持：{sorted(SUPPORTED)}）")
            return 1
        for f in sorted(files):
            process(f, out_dir)
    else:
        process(target, out_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
