"""rerank 封装：调用硅基流动的 rerank API。

为什么不用本地 CrossEncoder：
    bge-reranker-base 下载约 1GB，首次加载慢。
    API 版本一次调用几十毫秒，且和 embedding 用同一个 Key。

失败时降级为原顺序，不阻断主流程。
"""

import os

import httpx

RERANK_URL = "https://api.siliconflow.cn/v1/rerank"
RERANK_MODEL = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")


def rerank(query: str, documents: list[str], top_n: int = 5) -> list[tuple[int, float]]:
    """返回 [(原索引, 相关度分数)]，按分数降序。"""
    if not documents:
        return []

    key = os.getenv("SILICONFLOW_API_KEY")
    if not key:
        print("[rerank] 没配 SILICONFLOW_API_KEY，降级为原顺序")
        return [(i, 0.0) for i in range(min(top_n, len(documents)))]

    try:
        resp = httpx.post(
            RERANK_URL,
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": RERANK_MODEL,
                "query": query,
                "documents": documents,
                "top_n": min(top_n, len(documents)),
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return [(item["index"], float(item["relevance_score"])) for item in data["results"]]
    except Exception as exc:                      # noqa: BLE001
        print(f"[rerank] 调用失败，降级为原顺序：{exc}")
        return [(i, 0.0) for i in range(min(top_n, len(documents)))]
