"""Day 13 · RAG 的 Web 服务

启动：
    uv run uvicorn rag_api:app --reload --port 8000

接口：
    GET  /           前端页面
    POST /upload     上传文档 → 解析 → 切分 → 向量化 → 入库
    POST /ask        提问，SSE 流式返回
    GET  /health     健康检查 + 库容量

SSE 事件协议（前端按 type 分发）：
    {"type": "sources", "sources": [{id, doc_id, page_no, section, sim}]}
    {"type": "delta",   "text": "字"}
    {"type": "error",   "message": "..."}
    {"type": "done"}
"""

import json
import os
from dataclasses import asdict
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from chunker import chunk_doc
from context import build_context
from embedding import embed_texts
from parsers import parse_any
from qa import FEW_SHOT_ASSISTANT, FEW_SHOT_USER, REFUSAL, SYSTEM_PROMPT
from retrieval import Searcher

load_dotenv()

MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")

DB_PATH = "./chroma_db"
COLLECTION = "docs"

UPLOAD_DIR = Path("data/uploads")
MAX_MB = 20
ALLOWED = {".pdf", ".docx", ".txt", ".md"}

SIZE, OVERLAP, STRATEGY = 500, 0, "structure"
THRESHOLD = 0.50
BATCH = 32

app = FastAPI(title="RAG 文档问答", version="1.0.0")

# ---------------------------------------------------------------- 模型客户端
_client: AsyncOpenAI | None = None


def get_llm() -> AsyncOpenAI:
    global _client
    if _client is None:
        key = os.getenv("DEEPSEEK_API_KEY")
        if not key:
            raise HTTPException(503, "服务端没有配置 DEEPSEEK_API_KEY")
        _client = AsyncOpenAI(api_key=key, base_url=BASE_URL)
    return _client


# ---------------------------------------------------------------- 检索器缓存
_searcher: Searcher | None = None


def get_searcher() -> Searcher:
    """Searcher 会把全库读进内存并建 BM25 索引，所以缓存起来。"""
    global _searcher
    if _searcher is None:
        _searcher = Searcher()
    return _searcher


def reload_searcher() -> None:
    """上传新文档后必须调用，否则 BM25 索引和内存缓存都是旧的。"""
    global _searcher
    _searcher = None


# ---------------------------------------------------------------- 入库
def ingest_file(path: Path) -> tuple[int, int]:
    try:
        doc = parse_any(path)
    except Exception as exc:                      # noqa: BLE001
        raise HTTPException(400, f"解析失败：{exc}") from exc

    if doc.char_count == 0:
        raise HTTPException(400, "解析后没有文字，可能是扫描件（需要 OCR）")

    chunks = chunk_doc(doc, SIZE, OVERLAP, STRATEGY)
    if not chunks:
        raise HTTPException(400, "切分后没有内容")

    client = chromadb.PersistentClient(path=DB_PATH)
    col = client.get_or_create_collection(
        name=COLLECTION, metadata={"hnsw:space": "cosine"}
    )

    for i in range(0, len(chunks), BATCH):
        batch = chunks[i:i + BATCH]
        texts = [c.text for c in batch]
        vectors = embed_texts(texts)
        col.upsert(
            ids=[f"{c.doc_id}#{c.chunk_index}" for c in batch],
            documents=texts,
            embeddings=vectors,
            metadatas=[
                {
                    "doc_id": c.doc_id,
                    "chunk_index": c.chunk_index,
                    "page_no": c.page_no if c.page_no is not None else -1,
                    "section": c.section or "",
                    "char_start": c.char_start,
                    "char_end": c.char_end,
                }
                for c in batch
            ],
        )

    return doc.char_count, len(chunks)


# ---------------------------------------------------------------- 接口
class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    k: int = Field(default=4, ge=1, le=10)


def sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.get("/health")
async def health() -> dict:
    client = chromadb.PersistentClient(path=DB_PATH)
    try:
        count = client.get_collection(COLLECTION).count()
    except Exception:                             # noqa: BLE001
        count = 0
    return {"status": "ok", "model": MODEL, "chunks": count, "threshold": THRESHOLD}


@app.post("/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    filename = Path(file.filename or "").name
    suffix = Path(filename).suffix.lower()

    if suffix not in ALLOWED:
        raise HTTPException(400, f"不支持 {suffix}，只接受 {sorted(ALLOWED)}")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / filename

    size = 0
    with dest.open("wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_MB * 1024 * 1024:
                f.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, f"文件超过 {MAX_MB}MB")
            f.write(chunk)

    chars, n_chunks = ingest_file(dest)
    reload_searcher()          # 关键：让下一次检索看到新内容

    return {"doc_id": filename, "chars": chars, "chunks": n_chunks}


@app.post("/ask")
async def ask(req: AskRequest) -> StreamingResponse:
    async def gen():
        try:
            searcher = get_searcher()
            hits = searcher.hybrid(req.question, k=req.k)
        except SystemExit:
            yield sse({"type": "error", "message": "知识库是空的，请先上传文档"})
            yield sse({"type": "done"})
            return

        if not hits:
            yield sse({"type": "sources", "sources": []})
            yield sse({"type": "delta", "text": REFUSAL})
            yield sse({"type": "done"})
            return

        # 拒答判定用「向量检索 top-1 的余弦相似度」，不与 hybrid/RRF 的融合排序耦合：
        # 跨语言或弱关键词的相关块（如中文问题命中英文 PDF）会被 BM25 排到后面，
        # 若只看 hybrid 结果的 max(sim) 会误拒。向量相似度本身才是可靠的语义信号。
        vec_top = searcher.vector(req.question, 1)
        top_sim = vec_top[0]["sim"] if vec_top else 0.0

        # 第一层拒答：检索层就没相关的内容，不调模型
        if top_sim < THRESHOLD:
            yield sse({"type": "sources", "sources": []})
            yield sse({"type": "delta", "text": REFUSAL})
            yield sse({"type": "done"})
            return

        # 上下文以 hybrid 为主，并补入向量 top-k（按 id 去重），
        # 保证语义最相关的块（跨语言命中的 PDF）一定进上下文。
        seen = {h["id"] for h in hits}
        for h in searcher.vector(req.question, req.k):
            if h["id"] not in seen:
                seen.add(h["id"])
                hits.append(h)
        hits.sort(key=lambda x: x.get("sim", 0.0), reverse=True)

        ctx, used = build_context(hits)

        # 先发来源，前端可以先渲染卡片，再逐字出答案
        yield sse(
            {
                "type": "sources",
                "sources": [
                    {
                        "id": h.idx,
                        "doc_id": h.doc_id,
                        "page_no": h.page_no,
                        "section": h.section,
                        "sim": round(h.sim, 3),
                    }
                    for h in used
                ],
            }
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": FEW_SHOT_USER},
            {"role": "assistant", "content": FEW_SHOT_ASSISTANT},
            {
                "role": "user",
                "content": f"【参考资料】\n{ctx}\n\n【问题】\n{req.question}",
            },
        ]

        try:
            stream = await get_llm().chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0,
                max_tokens=600,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices:
                    piece = chunk.choices[0].delta.content
                    if piece:
                        yield sse({"type": "delta", "text": piece})
        except Exception as exc:                  # noqa: BLE001
            yield sse({"type": "error", "message": f"生成失败：{exc}"})

        yield sse({"type": "done"})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse("static/index.html")
