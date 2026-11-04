# day8-rag · 带引用与上传的 RAG 文档问答

> 把 Day 8–12 的检索增强生成（RAG）链路包成了一个能点开的网页：
> 上传文档 → 自动入库 → 提问得到**带 `[n]` 出处**的回答；文档里没有的问题会**拒答**。

## 是什么

- **上传即入库**：PDF / DOCX / TXT / MD → 解析 → 切分 → 向量化 → 写入 Chroma
- **带出处问答**：提问 → 混合检索（向量 + BM25 + RRF）→ 拼 context → 流式生成，每个结论标注 `[n]` 来源
- **双层拒答**：检索层相似度阈值（第一层，100% 可靠）+ prompt 指令（第二层，兜底），文档外问题直接说"资料里没有找到相关信息"
- **引用校验**：过滤模型编出的越界编号 `[n]`

## 运行

```bash
# 依赖（只需一次）
uv add fastapi "uvicorn[standard]" python-multipart

# 启动后端 + 前端
uv run uvicorn rag_api:app --reload --port 8000
# 浏览器打开 http://127.0.0.1:8000

# 冒烟测试（不开浏览器也能验 health / 提问 / 拒答）
uv run test_day13.py
```

## 接口

| 接口 | 方法 | 说明 |
|---|---|---|
| `/health` | GET | 返回库容量 `chunks` 数（部署平台靠它判断存活） |
| `/upload` | POST (multipart) | 存文件并入库；后缀白名单 `.pdf/.docx/.txt/.md` + 大小限制 20MB |
| `/ask` | POST (JSON) | 检索 + 流式生成；SSE 协议先发 `sources`，再逐字发 `delta` |
| `/` | GET | 返回 `static/index.html` |

**SSE 事件类型**：`sources`（检索命中，先发）→ `delta`（逐字文本）→ `done`（前端按 `keepCited` 只显示被引用的出处）→ `error`。

## 已知限制

> 这些是当前实现的有意取舍，记录下来比假装没问题更能体现工程素养。

1. **`ingest.py --rebuild` 会丢掉上传的文档**：重建只扫 `samples/`，不扫 `data/uploads/`，重建后上传的内容消失。→ 改成扫两个目录，或上传也写进 `samples/`。
2. **不支持多轮追问**：`/ask` 每次独立检索，不带上文，问"那它的价格呢"接不上。→ 加 `history` 参数。
3. **单进程内存缓存**：`Searcher` 缓存在进程里，多 worker 时可能不一致。→ 生产环境用独立检索服务。
4. **上传同名文件会覆盖**：id 是 `doc_id#index`，旧版本内容被替换。→ 加版本号或哈希后缀。
