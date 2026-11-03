"""测阈值该设多少：把「应回答」和「应拒答」两组问题的最高相似度打出来。

用法：
    uv run probe_threshold.py
    uv run probe_threshold.py -k 1        # 只看第 1 条

看结果：阈值取「应回答的最低分」和「应拒答的最高分」之间。
两组有重叠 → 光靠阈值分不开，必须靠 prompt 兜底。
"""

import argparse

from retrieval import Searcher

# 文档里确实有答案的（用同义改写，别照抄原文）
ANSWERABLE = [
    "支付超时怎么处理",
    "登录功能改了什么",
    "谁负责前端",
    "接口响应时间优化了多少",
    "充电一次能用多久",
    "哪个型号防水最好",
    "设备没反应怎么办",
    "日志在哪里看",
]

# 文档里确实没有的（注意：最后几条模型自己知道答案，更能测出「拒答」）
UNANSWERABLE = [
    "公司的年假政策是什么",
    "怎么申请报销",
    "这个产品的保修期多久",
    "能不能分期付款",
    "Python 的 GIL 是什么",
    "2024 年诺贝尔文学奖得主是谁",
    "怎么办理护照",
    "北京明天的天气",
]


def collect(s: Searcher, questions: list[str], k: int) -> list[float]:
    sims = []
    for q in questions:
        hits = s.hybrid(q, k=k)
        sim = max(h.get("sim", 0.0) for h in hits) if hits else 0.0
        sims.append(sim)
        print(f"  {sim:.3f}  {q}")
    return sims


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-k", type=int, default=4)
    args = parser.parse_args()

    s = Searcher()
    print(f"向量库 {len(s)} 条\n")

    print("=== 应该回答 ===")
    ok = collect(s, ANSWERABLE, args.k)

    print("\n=== 应该拒答 ===")
    no = collect(s, UNANSWERABLE, args.k)

    print("\n" + "=" * 46)
    print(f"应回答：最低 {min(ok):.3f}  最高 {max(ok):.3f}  平均 {sum(ok)/len(ok):.3f}")
    print(f"应拒答：最低 {min(no):.3f}  最高 {max(no):.3f}  平均 {sum(no)/len(no):.3f}")

    low_ok, high_no = min(ok), max(no)
    print("-" * 46)
    if high_no < low_ok:
        mid = (high_no + low_ok) / 2
        print(f"两组可分。建议阈值 ≈ {mid:.2f}")
        print(f"（应回答最低 {low_ok:.3f}，应拒答最高 {high_no:.3f}）")
    else:
        print("两组重叠，单靠阈值分不开。")
        print(f"（应回答最低 {low_ok:.3f} < 应拒答最高 {high_no:.3f}）")
        print("对策：阈值设低一点（宁可多答），靠 prompt 那层兜底拒答。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
