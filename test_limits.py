"""Day 14 验收：限流与缓存。

用法：
    uv run test_limits.py
"""

import os
import time

import httpx

BASE = os.getenv("API_URL", "http://127.0.0.1:8000")
QUESTION = "谁负责前端"


def ask(q: str) -> tuple[int, str, float]:
    t0 = time.perf_counter()
    r = httpx.post(f"{BASE}/ask", json={"question": q, "k": 4}, timeout=120)
    return r.status_code, r.text[:80].replace("\n", " "), time.perf_counter() - t0


def main() -> None:
    print("=== 缓存测试（两次问同一句）===")
    s1, b1, t1 = ask(QUESTION)
    print(f"  第 1 次 {s1}  {t1:5.2f}s")
    s2, b2, t2 = ask(QUESTION)
    print(f"  第 2 次 {s2}  {t2:5.2f}s   ← 应该明显更快")
    if t2 < t1 * 0.5:
        print("  [PASS] 缓存生效")
    else:
        print("  [WARN] 第二次没有明显变快，检查 cache_get/cache_put")

    print("\n=== 限流测试（连发 30 次）===")
    codes: dict[int, int] = {}
    for _ in range(30):
        code, _, _ = ask("限流测试")
        codes[code] = codes.get(code, 0) + 1

    print(f"  状态码分布：{codes}")
    if 429 in codes:
        print(f"  [PASS] 触发限流 {codes[429]} 次")
    else:
        print("  [FAIL] 没触发 429，检查 RATE_LIMIT 或中间件路径判断")


if __name__ == "__main__":
    main()
