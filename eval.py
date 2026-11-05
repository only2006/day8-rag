"""Day 18 · 端到端评测：检索 → 拼 context → 生成 → 判分。

用法：
    uv run eval.py                 # 跑全部 30 条
    uv run eval.py --only 事实型    # 只跑某个类别

判定用「关键词同义词组」，不额外调 LLM 复核：便宜、可复现。
阈值 / TOP_K 必须与 rag_api.py 一致，否则评的不是线上那个系统。
"""

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from context import build_context
from evalset import CASES
from qa import REFUSAL, ask, make_client
from retrieval import Searcher

load_dotenv()

THRESHOLD = 0.50
TOP_K = 4
CITE_RE = re.compile(r"\[(\d+)\]")
REPORT_DIR = Path("docs")


# ---------------------------------------------------------------- 判分
def keywords_ok(answer: str, groups: list[list[str]]) -> tuple[bool, list[list[str]]]:
    """每组至少命中一个词。返回（是否通过, 未命中的组）。"""
    missing = [g for g in groups if not any(w in answer for w in g)]
    return (not missing), missing


def citations_ok(answer: str, n_sources: int) -> tuple[bool, list[int]]:
    ids = [int(x) for x in CITE_RE.findall(answer)]
    return all(1 <= i <= n_sources for i in ids), ids


# ---------------------------------------------------------------- 单条
def run_case(searcher: Searcher, client, case: dict) -> dict:
    q = case["q"]
    hits = searcher.hybrid(q, k=TOP_K)
    top_sim = max((h.get("sim", 0.0) for h in hits), default=0.0)

    # 和 rag_api 一致：过不了阈值的直接拒答，不调模型
    blocked = not hits or top_sim < THRESHOLD
    if blocked:
        answer, used = REFUSAL, []
    else:
        ctx, used = build_context(hits)
        answer = ask(client, q, ctx)

    refused = REFUSAL in answer
    cite_ok, cite_ids = citations_ok(answer, len(used))

    if case.get("expect_refusal"):
        passed = refused
        reason = "正确拒答" if passed else "该拒未拒"
    elif refused:
        # 关键：这两种都表现为「拒答」，但根因和修法完全不同。
        #   阈值拦截  = 根本没调模型，sim 没过 0.50 → 调阈值 / 查询改写 / 检索
        #   模型主动拒答 = 过了阈值，但模型看着 context 说没有 → 查检索内容 / context
        # 教程原版把它们都记成「误拒答」，按归因修时容易选错方向。
        if blocked or not used:
            passed, reason = False, "误拒答·阈值拦截"
        else:
            passed, reason = False, "误拒答·模型拒答"
    else:
        ok, missing = keywords_ok(answer, case.get("must_include", []))
        if not ok:
            # blocked 的情况上面已经处理完，这里一定是「调了模型但答漏/用词不同」
            passed, reason = False, "答案不完整"
        elif not cite_ok:
            passed, reason = False, "引用越界"
        elif case.get("must_not") and any(w in answer for w in case["must_not"]):
            passed, reason = False, "答串了（出现不该有的内容）"
        else:
            passed, reason = True, "通过"

    return {
        "id": case.get("id"),
        "q": q,
        "category": case.get("category", "未分类"),
        "expect_refusal": bool(case.get("expect_refusal")),
        "answer": answer,
        "refused": refused,
        "top_sim": round(top_sim, 3),
        "threshold_blocked": blocked,
        "sources": len(used),
        "cited": cite_ids,
        "cite_ok": cite_ok,
        "passed": passed,
        "reason": reason,
    }


# ---------------------------------------------------------------- 报表
def print_table(rows: list[dict]) -> None:
    header = f"{'ID':<5}{'类别':<10}{'结果':<6}{'sim':>6}  {'归因':<18}问题"
    print(header)
    print("-" * 80)
    for r in rows:
        flag = "PASS" if r["passed"] else "FAIL"
        print(f"{r['id']:<5}{r['category']:<10}{flag:<6}{r['top_sim']:>6.2f}  "
              f"{r['reason']:<18}{r['q'][:26]}")


def group_stats(rows: list[dict]) -> dict[str, dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        grouped[r["category"]].append(r)
    return {
        cat: {
            "total": len(items),
            "passed": sum(1 for i in items if i["passed"]),
            "rate": sum(1 for i in items if i["passed"]) / len(items) * 100,
        }
        for cat, items in grouped.items()
    }


def write_markdown(rows: list[dict], stats: dict[str, dict]) -> Path:
    REPORT_DIR.mkdir(exist_ok=True)
    path = REPORT_DIR / "eval-report.md"

    total = len(rows)
    passed = sum(1 for r in rows if r["passed"])
    rate = passed / total * 100 if total else 0

    lines = [
        "# 端到端评测报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"测试集：{total} 条　通过 {passed} 条　**准确率 {rate:.0f}%**",
        f"阈值 {THRESHOLD}（与 rag_api.py 一致）　TOP_K {TOP_K}",
        "",
        "| 类别 | 条数 | 通过 | 通过率 |",
        "|---|---|---|---|",
    ]
    for cat, s in sorted(stats.items(), key=lambda kv: -kv[1]["rate"]):
        lines.append(f"| {cat} | {s['total']} | {s['passed']} | {s['rate']:.0f}% |")

    lines += ["", "## 失败归因", "", "| 归因 | 条数 |", "|---|---|"]
    reasons: dict[str, int] = defaultdict(int)
    for r in rows:
        if not r["passed"]:
            reasons[r["reason"]] += 1
    for reason, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {reason} | {n} |")

    fails = [r for r in rows if not r["passed"]]
    if fails:
        lines += ["", "## 失败样例", ""]
        for r in fails[:8]:
            lines.append(f"**{r['id']} · {r['q']}**（sim={r['top_sim']}，{r['reason']}）")
            lines.append("")
            lines.append(f"> {r['answer'][:200]}")
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ---------------------------------------------------------------- 主流程
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default=None, help="只跑某个类别")
    args = parser.parse_args()

    cases = CASES if not args.only else [c for c in CASES if c["category"] == args.only]
    if not cases:
        print("没有匹配的测试用例")
        return 1

    print(f"评测集 {len(cases)} 条，阈值 {THRESHOLD}\n")

    searcher = Searcher()
    client = make_client()
    rows = [run_case(searcher, client, c) for c in cases]

    print_table(rows)

    stats = group_stats(rows)
    total = len(rows)
    passed = sum(1 for r in rows if r["passed"])

    print(f"\n{'=' * 60}")
    print(f"总计 {passed}/{total} 通过，准确率 {passed / total * 100:.0f}%")
    print(f"{'类别':<12}{'通过':>8}")
    for cat, s in sorted(stats.items(), key=lambda kv: -kv[1]["rate"]):
        print(f"{cat:<12}{s['passed']}/{s['total']:>4}  {s['rate']:.0f}%")

    reasons: dict[str, int] = defaultdict(int)
    for r in rows:
        if not r["passed"]:
            reasons[r["reason"]] += 1
    if reasons:
        print("\n失败归因：")
        for reason, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
            print(f"  {reason:<20}{n} 条")

    out = REPORT_DIR / "eval-result.json"
    REPORT_DIR.mkdir(exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    md = write_markdown(rows, stats)
    print(f"\n明细：{out}")
    print(f"报告：{md}（可直接贴进 README）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
