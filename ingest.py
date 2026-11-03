"""Day 10 · 入库：解析 → 切分 → 向量化 → 写入 Chroma

用法：
    uv run ingest.py                   # 增量入库（同 id 覆盖）
    uv run ingest.py --rebuild         # 清空后重建
    uv run ingest.py --size 400 --overlap 80 --strategy structure
"""

import argparse
import time
from pathlib import Path

import chromadb

from chunk_schema import Chunk
from chunker import chunk_doc
from embedding import describe, embed_texts
from parsers import parse_any

SUPPORTED = {".pdf", ".docx", ".doc", ".txt", ".md", ".csv"}
DB_PATH = "./chroma_db"
COLLECTION = "docs"
BATCH = 32


def to_metadata(chunk: Chunk) -> dict:
    """Chroma 的 metadata 只接受 str / int / float / bool，None 会报错。"""
    return {
        "doc_id": chunk.doc_id,
        "chunk_index": chunk.chunk_index,
        "page_no": chunk.page_no if chunk.page_no is not None else -1,
        "section": chunk.section or "",
        "char_start": chunk.char_start,
        "char_end": chunk.char_end,
    }


def build_chunks(samples: Path, size: int, overlap: int, strategy: str) -> list[Chunk]:
    files = sorted(p for p in samples.iterdir() if p.suffix.lower() in SUPPORTED)
    if not files:
        raise SystemExit(f"{samples} 里没有可处理的文档")

    all_chunks: list[Chunk] = []
    for f in files:
        try:
            doc = parse_any(f)
        except Exception as exc:                  # noqa: BLE001
            print(f"[FAIL] {f.name} 解析失败：{exc}")
            continue

        chunks = chunk_doc(doc, size, overlap, strategy)
        print(f"[PARSE] {f.name:28} 原文 {doc.char_count:6d} 字 → {len(chunks):4d} 块")
        all_chunks.extend(chunks)

    return all_chunks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", default="samples")
    parser.add_argument("--size", type=int, default=500)
    parser.add_argument("--overlap", type=int, default=100)
    parser.add_argument("--strategy", default="structure",
                        choices=["fixed", "recursive", "structure"])
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()

    samples = Path(args.samples)
    if not samples.exists():
        print(f"samples 目录不存在：{samples}")
        return 1

    chunks = build_chunks(samples, args.size, args.overlap, args.strategy)
    if not chunks:
        print("没有产出任何块，检查文档是否为空或全是扫描件")
        return 1

    print(f"\n共 {len(chunks)} 块，准备向量化（后端：{describe()}）")

    client = chromadb.PersistentClient(path=DB_PATH)

    if args.rebuild:
        try:
            client.delete_collection(COLLECTION)
            print(f"已删除旧 collection：{COLLECTION}")
        except Exception:                         # noqa: BLE001
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine"},        # 用余弦距离，不是欧氏距离
    )

    start = time.time()
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i:i + BATCH]
        texts = [c.text for c in batch]
        vectors = embed_texts(texts)

        collection.upsert(
            ids=[f"{c.doc_id}#{c.chunk_index}" for c in batch],
            documents=texts,
            embeddings=vectors,
            metadatas=[to_metadata(c) for c in batch],
        )
        done = min(i + BATCH, len(chunks))
        print(f"  已入库 {done}/{len(chunks)}", end="\r")

    print(f"\n完成，用时 {time.time() - start:.1f} 秒")
    print(f"collection 现有 {collection.count()} 条记录，路径：{DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
