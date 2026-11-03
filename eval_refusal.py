"""Day 12 验收：拒答能力评测。

注意：这里**不套用阈值**（不走 qa.py 的第一层拒答），
直接调模型，专门检验 prompt 层的拒答能力。
"""

from context import build_context
from qa import REFUSAL, ask, make_client
from retrieval import Searcher

ANSWERABLE = [
    "登录功能改了什么",
    "谁负责前端",
    "接口响应时间优化了多少",
    "充电一次能用多久",
    "哪个型号防水级别最高",
]

UNANSWERABLE = [
    "公司的年假政策是什么",
    "怎么申请报销",
    "Python 的 GIL 是什么",
    "2024 年诺贝尔文学奖得主是谁",
    "这个产品的保修期多久",
]


def top_sim(hits: list[dict]) -> float:
    return max((h.get("sim", 0.0) for h in hits), default=0.0)


def main() -> None:
    searcher = Searcher()
    client = make_client()

    print("=== 应该回答的问题（检验过度拒答）===")
    correct = 0
    for q in ANSWERABLE:
        hits = searcher.hybrid(q, k=4)
        ctx, _ = build_context(hits)
        ans = ask(client, q, ctx)
        refused = REFUSAL in ans
        correct += 0 if refused else 1
        flag = "拒答(错)" if refused else "回答(对)"
        print(f"  [{flag}] {q:<22} sim={top_sim(hits):.3f}")

    print(f"\n回答率 {correct}/{len(ANSWERABLE)}")

    print("\n=== 应该拒答的问题（检验会不会硬答）===")
    refused_ok = 0
    for q in UNANSWERABLE:
        hits = searcher.hybrid(q, k=4)
        ctx, _ = build_context(hits)
        ans = ask(client, q, ctx)
        refused = REFUSAL in ans
        refused_ok += 1 if refused else 0
        flag = "拒答(对)" if refused else "硬答(错)"
        print(f"  [{flag}] {q:<22} sim={top_sim(hits):.3f}")

    print(f"\n拒答率 {refused_ok}/{len(UNANSWERABLE)}")

    total = len(ANSWERABLE) + len(UNANSWERABLE)
    print(f"\n综合正确率 {(correct + refused_ok)}/{total}")


if __name__ == "__main__":
    main()
