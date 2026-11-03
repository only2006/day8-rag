"""三种检索器：纯向量 / BM25 / 混合（RRF 融合）。

注意两个分数的区别（Day 12 踩过这个坑）：
    score  = 该检索器自己的分数（向量是相似度，BM25 是 BM25 分，hybrid 是 RRF 分）
    sim    = 向量相似度（0–1），只有它适合拿来跟阈值比较

阈值判断一律用 sim，不要用 score。
"""

import chromadb
import jieba
from rank_bm25 import BM25Okapi

from embedding import embed_one

DB_PATH = "./chroma_db"
COLLECTION = "docs"


def tokenize(text: str) -> list[str]:
    """中文分词，BM25 需要词列表而不是整段字符串。"""
    return [t for t in jieba.lcut(text) if t.strip()]


class Searcher:
    """一次性把库读进内存，适合几百到几万条的小库。"""

    def __init__(self, db_path: str = DB_PATH, collection: str = COLLECTION) -> None:
        client = chromadb.PersistentClient(path=db_path)
        self.col = client.get_collection(collection)

        data = self.col.get(include=["documents", "metadatas"])
        self.ids: list[str] = data["ids"]
        self.texts: list[str] = data["documents"]
        self.metas: list[dict] = data["metadatas"]

        if not self.ids:
            raise SystemExit("向量库是空的，先跑 uv run ingest.py --rebuild")

        self.pos = {cid: i for i, cid in enumerate(self.ids)}
        self.bm25 = BM25Okapi([tokenize(t) for t in self.texts])

    def __len__(self) -> int:
        return len(self.ids)

    def vector(self, query: str, k: int = 5) -> list[dict]:
        res = self.col.query(
            query_embeddings=[embed_one(query)],
            n_results=min(k, len(self.ids)),
            include=["documents", "metadatas", "distances"],
        )
        return [
            {
                "id": cid,
                "text": txt,
                "meta": meta,
                "score": 1 - dist,     # 向量：score 就是相似度
                "sim": 1 - dist,
            }
            for cid, txt, meta, dist in zip(
                res["ids"][0], res["documents"][0],
                res["metadatas"][0], res["distances"][0],
            )
        ]

    def bm25_search(self, query: str, k: int = 5) -> list[dict]:
        scores = self.bm25.get_scores(tokenize(query))
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [
            {
                "id": self.ids[i],
                "text": self.texts[i],
                "meta": self.metas[i],
                "score": float(scores[i]),
                "sim": 0.0,            # BM25 没有相似度，置 0
            }
            for i in order[:k]
        ]

    def hybrid(
        self,
        query: str,
        k: int = 5,
        rrf_k: int = 60,
        pool: int = 20,
    ) -> list[dict]:
        """RRF 融合：只看排名，不看两边的原始分数（量纲不同，不能直接相加）。"""
        vec = self.vector(query, pool)
        kw = self.bm25_search(query, pool)

        sim_map = {item["id"]: item["sim"] for item in vec}

        fused: dict[str, float] = {}
        for ranking in (vec, kw):
            for rank, item in enumerate(ranking, start=1):
                fused[item["id"]] = fused.get(item["id"], 0.0) + 1.0 / (rrf_k + rank)

        ranked = sorted(fused.items(), key=lambda x: x[1], reverse=True)[:k]
        out: list[dict] = []
        for cid, rrf_score in ranked:
            i = self.pos[cid]
            out.append(
                {
                    "id": cid,
                    "text": self.texts[i],
                    "meta": self.metas[i],
                    "score": rrf_score,               # RRF 分（0.01–0.05 量级）
                    "sim": sim_map.get(cid, 0.0),     # 真实相似度（0–1），阈值用它
                }
            )
        return out
