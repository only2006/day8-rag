"""Day 11 · 检索命中率评测

用法：
    uv run evaluate.py
    uv run evaluate.py --k 5
"""

import argparse
import statistics

from eval_set import CASES
from retrieval import Searcher

METHODS = {
    "纯向量": "vector",
    "BM25": "bm25_search",
    "混合(RRF)": "hybrid",
    "混合+rerank": "hybrid_rerank",
}


def hit(ranked: list[dict], expect: str, k: int) -> bool:
    """前 k 条里，有没有一条包含 expect 这个关键词。"""
    return any(expect in item["text"] for item in ranked[:k])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--k", type=int, default=5, help="评估的 top-k 上限")
    args = parser.parse_args()

    s = Searcher()
    print(f"向量库 {len(s)} 条，评测集 {len(CASES)} 条\n")

    if len(s) < 30:
        print("[WARN] 库里不到 30 条，评测结果不可靠——语料太少，检索器差别体现不出来")
        print("       建议再放几份真实文档，或把 size 调小产生更多块\n")
    if len(CASES) < 10:
        print("[WARN] 评测集不到 10 条，结论没有说服力\n")

    results: dict[str, dict[str, float]] = {}

    for label, method in METHODS.items():
        hits = {i: 0 for i in range(1, args.k + 1)}
        ranks: list[int] = []

        for case in CASES:
            fn = getattr(s, method)
            ranked = fn(case["q"], k=args.k)

            first = next(
                (i for i, item in enumerate(ranked, start=1) if case["expect"] in item["text"]),
                None,
            )
            if first:
                ranks.append(first)

            for k in hits:
                if hit(ranked, case["expect"], k):
                    hits[k] += 1

        total = len(CASES)
        results[label] = {f"Hit@{k}": v / total * 100 for k, v in hits.items()}
        results[label]["MRR"] = (
            statistics.mean(1.0 / r for r in ranks) if ranks else 0.0
        )

    # --- 打印表格 ---
    header = f"{'方法':<12}" + "".join(f"{f'Hit@{k}':>10}" for k in range(1, args.k + 1))
    header += f"{'MRR':>10}"
    print(header)
    print("-" * len(header))

    for label in METHODS:
        row = f"{label:<12}"
        for k in range(1, args.k + 1):
            row += f"{results[label][f'Hit@{k}']:>9.0f}%"
        row += f"{results[label]['MRR']:>10.2f}"
        print(row)

    base = results["纯向量"]["Hit@3"]
    best_label = max(METHODS, key=lambda m: results[m]["Hit@3"])
    best = results[best_label]["Hit@3"]

    print(f"\n结论：Hit@3 从 {base:.0f}%（纯向量）提升到 {best:.0f}%（{best_label}）")
    print(f"      小幅提示：Hit@k 是「前 k 条里有答案」的比例，MRR 是「答案排得多靠前」")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

