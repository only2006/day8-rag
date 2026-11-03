from qa import REFUSAL, ask, make_client
from context import build_context
from retrieval import Searcher

ANSWERABLE = [
    "登录功能改了什么",
    "谁负责前端",
    "接口响应时间优化了多少",
    "充电一次能用多久",
    "哪个型号防水最好",
]

UNANSWERABLE = [
    "公司的年假政策是什么",
    "怎么申请报销",
    "Python 的 GIL 是什么",
    "2024 年诺贝尔文学奖得主是谁",
    "这个产品的保修期多久",     # 文档可能真没有
]


def main() -> None:
    searcher = Searcher()
    client = make_client()

    print("=== 应该回答的问题 ===")
    correct = 0
    for q in ANSWERABLE:
        hits = searcher.hybrid(q, k=4)
        ctx, used = build_context(hits)
        ans = ask(client, q, ctx)
        refused = REFUSAL in ans
        correct += 0 if refused else 1
        flag = "拒答(错)" if refused else "回答(对)"
        print(f"  [{flag}] {q}   最高分 {hits[0]['score']:.3f}")

    print(f"\n回答率 {correct}/{len(ANSWERABLE)}")

    print("\n=== 应该拒答的问题 ===")
    refused_ok = 0
    for q in UNANSWERABLE:
        hits = searcher.hybrid(q, k=4)
        ctx, used = build_context(hits)
        ans = ask(client, q, ctx)
        refused = REFUSAL in ans
        refused_ok += 1 if refused else 0
        flag = "拒答(对)" if refused else "硬答(错)"
        print(f"  [{flag}] {q}   最高分 {hits[0]['score']:.3f}")

    print(f"\n拒答率 {refused_ok}/{len(UNANSWERABLE)}")


if __name__ == "__main__":
    main()