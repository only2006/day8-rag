"""Day 12 · 带引用的文档问答 CLI

用法：
    uv run qa.py "支付超时怎么处理"
    uv run qa.py "公司的年假政策是什么"          # 应该触发拒答
    uv run qa.py "..." -k 4 --show-context
    uv run qa.py "..." --threshold 0.50

两个关键设计：
1. 阈值比较的是「向量相似度 sim」，不是 hybrid 的 RRF 分
2. prompt 里不要写「绝对不要用自己的知识」这种绝对化措辞，会导致过度拒答
"""

import argparse
import os
import re

from dotenv import load_dotenv
from openai import OpenAI

from context import build_context, format_sources
from retrieval import Searcher

load_dotenv()

MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")

# 拒答时使用的固定措辞 —— 程序要靠它判断"是不是拒答"，所以不能变
REFUSAL = "资料里没有找到相关信息"

SYSTEM_PROMPT = f"""你是文档问答助手。

规则：
1. 优先根据【参考资料】回答
2. 参考资料中只要有相关信息，就必须据此回答；信息不完整也可以回答已有的部分，
   并说明还缺什么，不要因为不完整就拒答
3. 每个结论后用 [编号] 标注出处，例如 [1] 或 [1][2]
4. 只有参考资料与问题完全无关时，才输出这一句：{REFUSAL}
5. 不要编造编号，只能用参考资料里出现过的编号
6. 回答简洁，控制在 200 字以内
"""

# few-shot：示范「信息不完整也要回答」，抑制过度拒答
FEW_SHOT_USER = """【参考资料】
[1]（来源：中控手册 第1页 · 4.3 恢复出厂）
当配置严重错乱且无法通过后台修正时，恢复出厂是最后手段。执行前请先导出备份密钥。

【问题】
中控配置彻底乱了怎么办"""

FEW_SHOT_ASSISTANT = (
    "配置严重错乱且无法后台修正时，可以使用恢复出厂设置 [1]；执行前要先导出备份密钥 [1]。"
)

CITE_RE = re.compile(r"\[(\d+)\]")


def make_client() -> OpenAI:
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        raise SystemExit("没有配置 DEEPSEEK_API_KEY（可以从 day5-api 的 .env 复制过来）")
    return OpenAI(api_key=key, base_url=BASE_URL)


def ask(client: OpenAI, question: str, context: str) -> str:
    user = f"【参考资料】\n{context}\n\n【问题】\n{question}"
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": FEW_SHOT_USER},
            {"role": "assistant", "content": FEW_SHOT_ASSISTANT},
            {"role": "user", "content": user},
        ],
        temperature=0,
        max_tokens=600,
    )
    return (resp.choices[0].message.content or "").strip()


def validate_citations(answer: str, used) -> tuple[list[int], list[int]]:
    """返回（合法编号, 越界编号）。模型偶尔会编出 [5] 这种不存在的引用。"""
    valid_range = {h.idx for h in used}
    cited = [int(n) for n in CITE_RE.findall(answer)]
    ok = sorted({n for n in cited if n in valid_range})
    bad = sorted({n for n in cited if n not in valid_range})
    return ok, bad


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("-k", type=int, default=4)
    parser.add_argument("--threshold", type=float, default=0.50,
                        help="最高「向量相似度」低于此值时直接拒答，不调模型")
    parser.add_argument("--show-context", action="store_true")
    parser.add_argument("--no-llm", action="store_true", help="只打印检索结果，不调模型")
    args = parser.parse_args()

    searcher = Searcher()
    hits = searcher.hybrid(args.question, k=args.k)

    if not hits:
        print(REFUSAL)
        return 0

    top_sim = max(h.get("sim", 0.0) for h in hits)
    context, used = build_context(hits)

    if args.show_context or args.no_llm:
        print("=" * 62)
        print(context)
        print("=" * 62)
        print("\n检索分数（sim = 向量相似度，用于阈值；score = RRF 分，仅排序）：")
        for h in hits:
            print(f"  sim={h.get('sim', 0):.3f}  rrf={h['score']:.4f}  "
                  f"{h['meta']['doc_id']}  {h['text'][:40]!r}")

    if args.no_llm:
        return 0

    # 第一层拒答：检索层就没有足够相关的内容
    if top_sim < args.threshold:
        print(f"\n【回答】\n{REFUSAL}")
        print(f"\n（最高相似度 {top_sim:.3f} < 阈值 {args.threshold}，未调用模型）")
        return 0

    answer = ask(make_client(), args.question, context)

    print("\n【回答】")
    print(answer)

    if REFUSAL in answer:
        print("\n（模型判定资料中没有答案）")
        return 0

    ok, bad = validate_citations(answer, used)
    if bad:
        print(f"\n[WARN] 模型引用了不存在的编号 {bad}，已忽略")
    if not ok:
        print("\n[WARN] 回答里没有任何引用，可信度存疑")

    cited = [h for h in used if h.idx in ok] or used
    print("\n【来源】")
    print(format_sources(cited))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
