"""实验：精确匹配型问题（型号 / 数字 / 编号）。

假设：这类问题 BM25 应该强于向量，混合应该能赢。
如果假设成立，那 Day 11 的结论就该是：
    「整体持平，但在精确匹配类问题上混合更优」——而不是「混合没有用」。
"""

from retrieval import Searcher

s = Searcher()

# 全部指向文档里的精确 token：型号、数值、章节号
EXACT_CASES = [
    {"q": "CW-300 电池能用多久",        "expect": "30 days"},
    {"q": "IPX8 是哪一款",              "expect": "CW-300"},
    {"q": "400ml 的是哪个型号",         "expect": "CW-100"},
    {"q": "320ms 优化到了多少",         "expect": "110ms"},
    {"q": "4.3 节讲的是什么",           "expect": "恢复出厂"},
    {"q": "哪款续航 14 days",           "expect": "CW-200"},
]


def hit(ranked: list[dict], expect: str, k: int = 3) -> bool:
    return any(expect in r["text"] for r in ranked[:k])


def score(fn) -> float:
    return sum(1 for c in EXACT_CASES if hit(fn(c["q"], 5), c["expect"])) / len(EXACT_CASES) * 100


def main() -> None:
    print(f"精确匹配型用例 {len(EXACT_CASES)} 条\n")
    print(f"{'方法':<26}{'Hit@3':>8}")
    print("-" * 36)
    print(f"{'纯向量':<26}{score(lambda q, k: s.vector(q, k)):>7.0f}%")
    print(f"{'BM25':<26}{score(lambda q, k: s.bm25_search(q, k)):>7.0f}%")
    print(f"{'混合 pool=3':<26}{score(lambda q, k: s.hybrid(q, k, pool=3)):>7.0f}%")
    print(f"{'混合 pool=5':<26}{score(lambda q, k: s.hybrid(q, k, pool=5)):>7.0f}%")

    print("\n=== 逐条看谁命中 ===")
    for c in EXACT_CASES:
        v = hit(s.vector(c["q"], 5), c["expect"])
        b = hit(s.bm25_search(c["q"], 5), c["expect"])
        h = hit(s.hybrid(c["q"], 5, pool=5), c["expect"])
        mark = lambda ok: "✓" if ok else "✗"  # noqa: E731
        print(f"  {c['q']:<24} 向量{mark(v)}  BM25{mark(b)}  混合{mark(h)}")


if __name__ == "__main__":
    main()
