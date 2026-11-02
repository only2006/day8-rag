"""Day 8 测试样本生成器（零外部依赖：仅标准库 + python-docx）。

生成 4 个文件到 samples/：
  report.pdf   —— 有表格的 PDF（真实文字层，测表格提取）
  scan.pdf     —— 扫描版 PDF（纯矢量图形、无文字层，测扫描件检测）
  weekly.docx  —— 带标题层级 + 表格的 Word
  notes.txt    —— GBK/ANSI 编码的 txt（测编码自动识别）

注意：PDF 用纯字节手写，故意只用英文（标准 Helvetica 字体不支持中文），
      中文测试由 docx / txt 两个样本覆盖。
"""
from pathlib import Path

SAMPLES = Path(__file__).parent / "samples"
SAMPLES.mkdir(parents=True, exist_ok=True)


# ---------- 极简 PDF 构造器（纯标准库）----------
def _pdf_text(x: int, y: int, text: str, size: int = 12) -> str:
    t = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    return f"BT /F1 {size} Tf {x} {y} Td ({t}) Tj ET\n"


def _pdf_table(col_xs, y_header, rows, row_h=20):
    ops = []
    for cx, val in zip(col_xs, rows[0]):          # 表头
        ops.append(_pdf_text(cx, y_header, val, 11))
    bottom = y_header - row_h * len(rows)
    ops.append(f"0.5 w {col_xs[0]-5} {y_header+6} m {col_xs[-1]+40} {y_header+6} l S")  # 上边线
    ops.append(f"0.5 w {col_xs[0]-5} {bottom} m {col_xs[-1]+40} {bottom} l S")        # 下边线
    for i, row in enumerate(rows[1:], start=1):
        yy = y_header - row_h * i
        for cx, val in zip(col_xs, row):
            ops.append(_pdf_text(cx, yy, val, 10))
        ops.append(f"0.5 w {col_xs[0]-5} {yy-4} m {col_xs[-1]+40} {yy-4} l S")  # 行间线
    ops.append(f"0.5 w {col_xs[0]-5} {y_header+6} m {col_xs[0]-5} {bottom} l S")   # 左边线
    ops.append(f"0.5 w {col_xs[-1]+40} {y_header+6} m {col_xs[-1]+40} {bottom} l S")  # 右边线
    return "\n".join(ops)


def build_pdf(path: Path, page_ops: list[str]):
    """page_ops: 每页一段 content stream 文本。"""
    n = len(page_ops)
    page_nums = [3 + 2 * i for i in range(n)]
    content_nums = [4 + 2 * i for i in range(n)]
    font_num = 3 + 2 * n

    objs = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: ("<< /Type /Pages /Kids [%s] /Count %d >>"
            % (" ".join(f"{p} 0 R" for p in page_nums), n)).encode(),
    }
    for i in range(n):
        objs[page_nums[i]] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 {font_num} 0 R >> >> "
            f"/Contents {content_nums[i]} 0 R >>"
        ).encode()
        stream = page_ops[i].encode("latin-1")
        objs[content_nums[i]] = (
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
            + stream + b"\nendstream"
        )
    objs[font_num] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for num in sorted(objs):
        offsets[num] = len(out)
        out += f"{num} 0 obj\n".encode() + objs[num] + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for num in sorted(objs):
        out += f"{offsets[num]:010d} 00000 n \n".encode()
    out += b"trailer\n"
    out += f"<< /Size {len(objs) + 1} /Root 1 0 R >>\n".encode()
    out += b"startxref\n" + str(xref_pos).encode() + b"\n%%EOF"
    path.write_bytes(out)


# ---------- 1) 有表格的 PDF（真实文字层）----------
def make_pdf_with_table(path: Path):
    ops = [
        _pdf_text(50, 780, "Smart Cup Pro - Product Manual", 16),
        _pdf_text(50, 745, "A smart water bottle with Bluetooth and temp sensing.", 11),
        _pdf_text(50, 725, "Below is the model comparison table.", 11),
        _pdf_table([55, 165, 285, 405], 600, [
            ["Model", "Capacity", "Battery", "Waterproof"],
            ["CW-100", "400ml", "7 days", "IPX7"],
            ["CW-200", "500ml", "14 days", "IPX7"],
            ["CW-300", "600ml", "30 days", "IPX8"],
        ]),
        _pdf_text(50, 520, "Note: charge fully before first use.", 10),
    ]
    build_pdf(path, ["\n".join(ops)])  # 单页：所有内容合并成一段 stream


# ---------- 2) 扫描版 PDF（纯图形、无文字层）----------
def make_scanned_pdf(path: Path):
    # 只画灰色矩形当“文字行”，没有任何文字操作符 → pypdf 抽不出文字 → 触发扫描件警告
    ops = [
        "0.7 0.7 0.7 rg 60 780 320 22 re f",     # 标题块
        "0.85 0.85 0.85 rg 60 740 470 10 re f",  # 正文行
        "0.85 0.85 0.85 rg 60 720 470 10 re f",
        "0.85 0.85 0.85 rg 60 700 470 10 re f",
        "0.85 0.85 0.85 rg 60 680 380 10 re f",
        "0.85 0.85 0.85 rg 60 640 470 10 re f",
        "0.85 0.85 0.85 rg 60 620 300 10 re f",
        "0.7 0.7 0.7 rg 60 560 250 22 re f",     # 第二段标题
        "0.85 0.85 0.85 rg 60 520 470 10 re f",
        "0.85 0.85 0.85 rg 60 500 470 10 re f",
    ]
    build_pdf(path, ["\n".join(ops)])  # 单页：纯图形、无文字层


# ---------- 3) 带标题层级 + 表格的 Word ----------
def make_docx(path: Path):
    from docx import Document

    doc = Document()
    doc.add_heading("项目周报", level=0)
    doc.add_heading("一、本周进展", level=1)
    doc.add_paragraph("完成了登录模块重构，接口平均响应时间从 320ms 降到 110ms。")
    doc.add_heading("二、风险与问题", level=1)
    doc.add_paragraph("第三方支付接口偶发超时，已联系厂商排查。")
    doc.add_heading("三、人员排期", level=1)
    table = doc.add_table(rows=1, cols=3)
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    hdr[0].text, hdr[1].text, hdr[2].text = "成员", "任务", "状态"
    for r in [("小明", "前端", "进行中"), ("小红", "后端", "已完成"), ("小刚", "测试", "未开始")]:
        cells = table.add_row().cells
        cells[0].text, cells[1].text, cells[2].text = r
    doc.save(str(path))


# ---------- 4) GBK/ANSI 编码的 txt ----------
def make_gbk_txt(path: Path):
    content = (
        "这是一份用 GBK 编码保存的测试文本。\n"
        "中文内容包含全角标点：，。；：“”（）\n"
        "目的是测试解析器的编码自动识别能力。\n"
        "如果解析器正确识别，meta.encoding 应当显示为 gbk。\n"
        "Windows 记事本默认保存为 ANSI/GBK，直接按 UTF-8 读会乱码。\n"
    )
    path.write_text(content, encoding="gbk")


if __name__ == "__main__":
    make_pdf_with_table(SAMPLES / "report.pdf")
    make_scanned_pdf(SAMPLES / "scan.pdf")
    make_docx(SAMPLES / "weekly.docx")
    make_gbk_txt(SAMPLES / "notes.txt")

    # 自检：用项目里已有的库读回来，确认样本有效
    from pypdf import PdfReader
    from docx import Document

    r = PdfReader(str(SAMPLES / "report.pdf"))
    rtext = (r.pages[0].extract_text() or "")
    s = PdfReader(str(SAMPLES / "scan.pdf"))
    stext = (s.pages[0].extract_text() or "")
    d = Document(str(SAMPLES / "weekly.docx"))

    print("生成完成 + 自检：")
    for p in sorted(SAMPLES.iterdir()):
        print(f"  {p.name:14s} ({p.stat().st_size:6d} 字节)")
    print(f"\nreport.pdf : {len(r.pages)} 页, 抽出文字 {len(rtext)} 字 (应有表格文本)")
    print(f"scan.pdf   : {len(s.pages)} 页, 抽出文字 {len(stext)} 字 (应为 0 → 触发扫描件警告)")
    print(f"weekly.docx: {len(d.paragraphs)} 段落, {len(d.tables)} 个表格")
    print("notes.txt  : GBK 编码已写入")
