"""三种检索器：纯向量 / BM25 / 混合（RRF 融合）。

用法：
    from retrieval import Searcher
    s = Searcher()
    s.vector("登录模块改了什么", k=3)
    s.bm25_search("登录模块改了什么", k=3)
    s.hybrid("登录模块改了什么", k=3)
"""

import json
import os
import urllib.request

import chromadb
import jieba
from rank_bm25 import BM25Okapi

from embedding import embed_one

DB_PATH = "./chroma_db"
COLLECTION = "docs"

# 硅基流动 rerank API（与 embedding 同源同鉴权，不下载模型）
RERANK_URL = "https://api.siliconflow.cn/v1/rerank"
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"


def tokenize(text: str) -> list[str]:
    """中文分词，BM25 需要词列表而不是整段字符串。"""
    return [t for t in jieba.lcut(text) if t.strip()]


def rerank(query: str, candidates: list[dict], top_k: int = 5) -> list[dict]:
    """用硅基流动 rerank API 对候选集重新打分，返回 top_k。candidates 一般 20-40 条。

    不下载模型，复用 SILICONFLOW_API_KEY（与 embedding 同一套鉴权）。
    """
    if not candidates:
        return []
    key = os.getenv("SILICONFLOW_API_KEY")
    if not key:
        raise RuntimeError("未配置 SILICONFLOW_API_KEY，无法调用 rerank API")

    texts = [c["text"] for c in candidates]
    payload = json.dumps(
        {
            "model": RERANK_MODEL,
            "query": query,
            "documents": texts,
            "return_documents": False,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        RERANK_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    scores = {r["index"]: float(r["relevance_score"]) for r in data["results"]}
    for i, c in enumerate(candidates):
        c["rerank_score"] = scores.get(i, 0.0)
    return sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)[:top_k]


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
            {"id": cid, "text": txt, "meta": meta, "score": 1 - dist}
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

        fused: dict[str, float] = {}
        for ranking in (vec, kw):
            for rank, item in enumerate(ranking, start=1):
                fused[item["id"]] = fused.get(item["id"], 0.0) + 1.0 / (rrf_k + rank)

        ranked = sorted(fused.items(), key=lambda x: x[1], reverse=True)[:k]
        out: list[dict] = []
        for cid, score in ranked:
            i = self.pos[cid]
            out.append(
                {"id": cid, "text": self.texts[i], "meta": self.metas[i], "score": score}
            )
        return out

    def hybrid_rerank(self, query: str, k: int = 5, recall: int = 20) -> list[dict]:
        """混合检索 + rerank：先 RRF 召回 recall 条，再用 rerank API 精排到 k 条。"""
        cands = self.hybrid(query, recall)
        try:
            return rerank(query, cands, k)
        except Exception as e:  # noqa: BLE001 —— 评测不应因单次 API 抖动而中断
            print(f"[WARN] rerank 调用失败，回退到混合原始顺序：{e}")
            return cands[:k]

