"""embedding 封装：两种后端可切换。

后端 1（默认）：API —— 硅基流动，无需下载模型
后端 2：本地 —— sentence-transformers，免费、离线

在 .env 里切换：
    EMBED_BACKEND=api      或   local
"""

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

BACKEND = os.getenv("EMBED_BACKEND", "api").strip().lower()

# --- API 后端 ---
API_BASE = os.getenv("EMBED_BASE_URL", "https://api.siliconflow.cn/v1")
API_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-m3")
API_KEY_ENV = "SILICONFLOW_API_KEY"

# --- 本地后端 ---
LOCAL_MODEL = os.getenv("EMBED_LOCAL_MODEL", "BAAI/bge-small-zh-v1.5")


def _embed_api(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI

    key = os.getenv(API_KEY_ENV)
    if not key:
        raise RuntimeError(
            f"没有配置 {API_KEY_ENV}，请在 .env 里填入，"
            "或把 EMBED_BACKEND 改成 local 用本地模型"
        )

    client = OpenAI(api_key=key, base_url=API_BASE)
    resp = client.embeddings.create(model=API_MODEL, input=texts)
    return [item.embedding for item in resp.data]


@lru_cache(maxsize=1)
def _get_local_model():
    from sentence_transformers import SentenceTransformer

    print(f"[embedding] 首次加载本地模型：{LOCAL_MODEL}（可能要等几十秒）")
    return SentenceTransformer(LOCAL_MODEL)


def _embed_local(texts: list[str]) -> list[list[float]]:
    model = _get_local_model()
    vectors = model.encode(
        texts,
        normalize_embeddings=True,
        batch_size=32,
        show_progress_bar=False,
    )
    return [v.tolist() for v in vectors]


def embed_texts(texts: list[str]) -> list[list[float]]:
    """把一批文本转成向量。"""
    if not texts:
        return []
    if BACKEND == "local":
        return _embed_local(texts)
    return _embed_api(texts)


def embed_one(text: str) -> list[float]:
    return embed_texts([text])[0]


def describe() -> str:
    if BACKEND == "local":
        return f"local:{LOCAL_MODEL}"
    return f"api:{API_MODEL}"
