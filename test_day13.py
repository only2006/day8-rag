"""Day 13 冒烟测试：上传 → 提问 → 校验 SSE 与来源。

用法：
    1. 先起服务：uv run uvicorn rag_api:app --port 8000
    2. 另开终端：uv run test_day13.py
"""

import json
import os

import httpx

BASE = os.getenv("API_URL", "http://127.0.0.1:8000")


def test_health() -> None:
    r = httpx.get(f"{BASE}/health", timeout=10)
    print(f"[health] {r.status_code} {r.json()}")


def test_upload(path: str) -> None:
    with open(path, "rb") as f:
        files = {"file": (path.split("\\")[-1].split("/")[-1], f,
                          "application/octet-stream")}
        r = httpx.post(f"{BASE}/upload", files=files, timeout=120)
    print(f"[upload] {r.status_code} {r.json()}")
    if r.status_code == 200:
        print("         ^ 上传成功，注意 chunks 数量")


def test_ask(question: str) -> None:
    print(f"\n[ask] {question}")
    body = {"question": question, "k": 4}
    sources = []
    answer = ""

    with httpx.stream("POST", f"{BASE}/ask", json=body, timeout=120) as r:
        if r.status_code != 200:
            print(f"  HTTP {r.status_code}")
            return
        for line in r.iter_lines():
            if not line.startswith("data: "):
                continue
            evt = json.loads(line[6:])
            if evt["type"] == "sources":
                sources = evt["sources"]
            elif evt["type"] == "delta":
                answer += evt["text"]
            elif evt["type"] == "error":
                print(f"  错误：{evt['message']}")
            elif evt["type"] == "done":
                break

    print(f"  回答：{answer}")
    if sources:
        for s in sources:
            page = f"第{s['page_no']}页" if s["page_no"] and s["page_no"] > 0 else "无页码"
            print(f"  出处 [{s['id']}] {s['doc_id']} {page} {s['section']} sim={s['sim']}")
    else:
        print("  出处：（无，说明走了拒答路径）")


def main() -> None:
    import sys

    test_health()

    # 命令行给了问题就只问这些，否则跑默认的验收三问
    questions = sys.argv[1:] or [
        "谁负责前端",
        "公司的年假政策是什么",
        "中控怎么恢复出厂设置",
    ]
    for q in questions:
        test_ask(q)


if __name__ == "__main__":
    main()
