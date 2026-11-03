"""冒烟测试：rerank 能不能跑通。"""

from retrieval import Searcher

s = Searcher()
for q in ("充电一次能用多久", "IPX8 是哪一款"):
    print(f"\n=== {q} ===")
    for item in s.hybrid_rerank(q, k=3, pool=8):
        score = item.get("rerank", 0.0)
        print(f"  {score:.3f}  {item['text'][:48]!r}")
