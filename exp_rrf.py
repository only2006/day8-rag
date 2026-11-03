"""实验：加权 RRF。

标准 RRF 两路等权。但在这里向量明显更强（95% vs 65%），
等权等于把弱的那路拉平到和强的一样重要 —— 所以试试给向量更高权重。
"""

from eval_set import CASES
from retrieval import Searcher

s = Searcher()


def rrf_weighted(query: str, k: int, pool: int, w_vec: float, w_bm25: float) -> list[dict]:
    vec = s.vector(query, pool)
    kw = s.bm25_search(query, pool)

    fused: dict[str, float] = {}
    for ranking, w in ((vec, w_vec), (kw, w_bm25)):
        for rank, item in enumerate(ranking, start=1):
            fused[item["id"]] = fused.get(item["id"], 0.0) + w / (60 + rank)

    ranked = sorted(fused.items(), key=lambda x: x[1], reverse=True)[:k]
    out = []
    for cid, sc in ranked:
        i = s.pos[cid]
        out.append({"id": cid, "text": s.texts[i], "meta": s.metas[i], "score": sc})
    return out


def hit3(ranked: list[dict], expect: str) -> bool:
    return any(expect in r["text"] for r in ranked[:3])


def score(fn) -> float:
    return sum(1 for c in CASES if hit3(fn(c["q"], 5), c["expect"])) / len(CASES) * 100


def main() -> None:
    print(f"库 {len(s)} 条，评测集 {len(CASES)} 条\n")
    print(f"{'配置':<34}{'Hit@3':>8}")
    print("-" * 44)
    print(f"{'纯向量':<34}{score(lambda q, k: s.vector(q, k)):>7.0f}%")
    print(f"{'BM25':<34}{score(lambda q, k: s.bm25_search(q, k)):>7.0f}%")

    for pool in (3, 5, 10):
        for wv, wb in ((1, 1), (2, 1), (3, 1), (5, 1)):
            tag = f"加权 pool={pool}  w_vec={wv} w_bm25={wb}"
            print(f"{tag:<34}{score(lambda q, k, p=pool, a=wv, b=wb: rrf_weighted(q, k, p, a, b)):>7.0f}%")


if __name__ == "__main__":
    main()
