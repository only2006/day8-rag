import chromadb

from embedding import embed_one

QA = [
    ("钱付不出去卡住了", "支付接口偶发超时"),
    ("登录功能改过什么", "登录模块重构"),
    ("谁在做前端", "小明"),
    ("这个杯子多久充一次电", "电池续航"),
]


def keyword_hit(texts: list[str], query: str) -> int | None:
    """最朴素的基线：按单字重合度排序。"""
    q = set(query)
    scored = [(len(q & set(t)) / max(len(q), 1), i) for i, t in enumerate(texts)]
    scored.sort(reverse=True)
    return scored[0][1] if scored else None


def main() -> None:
    client = chromadb.PersistentClient(path="./chroma_db")
    col = client.get_collection("docs")
    data = col.get(include=["documents"])
    texts = data["documents"]

    print(f"库里 {len(texts)} 条\n")
    print(f"{'提问':<22}{'关键词Top1':<28}{'向量Top1'}")

    vec_win = kw_win = 0
    for query, expected in QA:
        res = col.query(query_embeddings=[embed_one(query)], n_results=1,
                        include=["documents"])
        vec_top = res["documents"][0][0][:24]

        kw_idx = keyword_hit(texts, query)
        kw_top = texts[kw_idx][:24] if kw_idx is not None else "-"

        vec_ok = expected in res["documents"][0][0]
        kw_ok = kw_idx is not None and expected in texts[kw_idx]
        vec_win += vec_ok
        kw_win += kw_ok

        print(f"{query:<22}{kw_top:<28}{vec_top}")
        print(f"{'':22}命中={'是' if kw_ok else '否':<26}命中={'是' if vec_ok else '否'}")

    print(f"\n向量命中 {vec_win}/{len(QA)}   关键词命中 {kw_win}/{len(QA)}")


if __name__ == "__main__":
    main()