"""Day 10 · 检索 CLI：输入一句话，返回最相关的 k 段原文

用法：
    uv run search.py "支付接口超时怎么处理"
    uv run search.py "支付接口超时怎么处理" -k 5
"""

import argparse
from pathlib import Path

import chromadb

from embedding import embed_one

DB_PATH = "./chroma_db"
COLLECTION = "docs"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="要检索的问题")
    parser.add_argument("-k", type=int, default=3, help="返回几条")
    parser.add_argument("--full", action="store_true", help="打印完整文本")
    args = parser.parse_args()

    if not Path(DB_PATH).exists():
        print(f"向量库不存在：{DB_PATH}，先跑 uv run ingest.py")
        return 1

    client = chromadb.PersistentClient(path=DB_PATH)
    collection = client.get_collection(COLLECTION)

    vector = embed_one(args.query)

    result = collection.query(
        query_embeddings=[vector],
        n_results=args.k,
        include=["documents", "metadatas", "distances"],
    )

    docs = result["documents"][0]
    metas = result["metadatas"][0]
    dists = result["distances"][0]

    print(f"\n查询：{args.query}")
    print(f"库里共 {collection.count()} 条，返回 {len(docs)} 条\n")

    for rank, (text, meta, dist) in enumerate(zip(docs, metas, dists), start=1):
        # cosine 距离 → 相似度：sim = 1 - distance
        sim = 1 - dist
        page = meta.get("page_no", -1)
        section = meta.get("section") or ""
        print("=" * 62)
        print(f"[{rank}] 相似度 {sim:.3f}   "
              f"来源：{meta['doc_id']} 第 {page} 页  {section}")
        body = text if args.full else text[:200].replace("\n", " ")
        print(f"    {body}{'' if args.full or len(text) <= 200 else '…'}")
    print("=" * 62)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
