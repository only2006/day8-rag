"""实验：pool 大小对混合检索的影响。

背景：改完 chunker 后纯向量 Hit@3 已经 90%，混合反而 80%。
怀疑 pool=20 在 41 条的库里取了近一半，BM25 的噪声把向量的好结果挤下去了。
"""

from eval_set import CASES
from retrieval import Searcher

s = Searcher()


def hit3(ranked: list[dict], expect: str) -> bool:
    return any(expect in r["text"] for r in ranked[:3])


def score(fn) -> float:
    return sum(1 for c in CASES if hit3(fn(c["q"], 5), c["expect"])) / len(CASES) * 100


def main() -> None:
    print(f"库 {len(s)} 条，评测集 {len(CASES)} 条\n")

    print(f"{'方法':<22}{'Hit@3':>8}")
    print("-" * 30)
    print(f"{'纯向量':<22}{score(lambda q, k: s.vector(q, k)):>7.0f}%")
    print(f"{'BM25':<22}{score(lambda q, k: s.bm25_search(q, k)):>7.0f}%")

    for pool in (3, 5, 8, 10, 20, 40):
        p = pool
        print(f"{'混合 RRF pool=' + str(pool):<22}{score(lambda q, k, p=p: s.hybrid(q, k, pool=p)):>7.0f}%")

    # 逐条对比：纯向量 vs 最佳混合
    print("\n=== 逐条对比（纯向量 vs pool=5）===")
    for c in CASES:
        v = s.vector(c["q"], 5)
        h = s.hybrid(c["q"], 5, pool=5)
        vo = hit3(v, c["expect"])
        ho = hit3(h, c["expect"])
        if vo != ho:
            flag = "混合胜" if ho else "向量胜"
            print(f"  [{flag}] {c['q']}  (expect={c['expect']})")


if __name__ == "__main__":
    main()
