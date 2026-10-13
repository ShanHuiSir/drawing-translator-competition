"""Build the Chinese delivery PDF from actual verification evidence, never invented scores."""

import io
import json
from pathlib import Path
from xml.sax.saxutils import escape

import pymupdf
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / "图译交付材料"
ACCENT, INK, MUTED = colors.HexColor("#14776e"), colors.HexColor("#23343c"), colors.HexColor("#71818b")


def main():
    OUT.mkdir(exist_ok=True)
    gold = json.loads((ROOT / "outputs/参考答案验证.json").read_text())
    times = json.loads((ROOT / "outputs/单页独立计时.json").read_text())
    batch = json.loads((ROOT / "outputs/最终样例结果/批量处理报告.json").read_text())
    comments = json.loads((ROOT / "outputs/源码注释统计.json").read_text())
    pytest_log = (ROOT / "outputs/pytest-final.log").read_text()
    assert "23 passed" in pytest_log, "The report requires actual passing test evidence"
    assert len(batch) == 6 and sum(x["pages"] for x in batch) == 139
    pdfmetrics.registerFont(TTFont("Chinese", io.BytesIO(pymupdf.Font("china-s").buffer)))
    styles = {
        "title": ParagraphStyle("title", fontName="Chinese", fontSize=28, leading=38, textColor=INK, spaceAfter=16),
        "sub": ParagraphStyle("sub", fontName="Chinese", fontSize=12, leading=20, textColor=MUTED, spaceAfter=12),
        "h": ParagraphStyle("h", fontName="Chinese", fontSize=17, leading=25, textColor=INK, spaceAfter=12),
        "body": ParagraphStyle("body", fontName="Chinese", fontSize=10, leading=17, textColor=INK, spaceAfter=9, wordWrap="CJK"),
        "small": ParagraphStyle("small", fontName="Chinese", fontSize=8, leading=13, textColor=MUTED, spaceAfter=7, wordWrap="CJK"),
        "cell": ParagraphStyle("cell", fontName="Chinese", fontSize=8.5, leading=14, textColor=INK, wordWrap="CJK"),
        "tablehead": ParagraphStyle("tablehead", fontName="Chinese", fontSize=9, leading=14, textColor=colors.white, wordWrap="CJK"),
    }
    story = []
    def p(text, style="body"):
        return Paragraph(escape(text).replace("\n", "<br/>"), styles[style])
    def add(text, style="body"):
        story.append(p(text, style))
    def table(headers, rows, widths):
        data = [[p(x, "tablehead") for x in headers]] + [[p(str(x), "cell") for x in row] for row in rows]
        result = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        result.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), ACCENT), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                                   ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                                   ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f0f6f5"), colors.white]),
                                   ("LINEBELOW", (0, -1), (-1, -1), .5, colors.HexColor("#dfe6e7"))]))
        story.append(result); story.append(Spacer(1, 12))
    def picture(path, width, max_height):
        image = Image(str(path));ratio=min(width/image.imageWidth,max_height/image.imageHeight)
        image.drawWidth=image.imageWidth*ratio;image.drawHeight=image.imageHeight*ratio;image.hAlign="LEFT";story.append(image)
    def page(title):
        story.append(PageBreak());add(title,"h")

    add("图译", "title")
    add("英文零件图纸术语自动翻译\n交付说明与实测报告", "title")
    add("2026 年 10 月 13 日  /  Python 本地应用", "sub")
    add("识别英文，记录坐标，生成红色中文。图纸与识别文本始终在本机处理，运行时不调用外部 API。")
    picture(ROOT / "docs/images/工作台.png", 170*mm, 92*mm)
    story.append(Spacer(1, 16))
    table(["已交付", "内容"], [
        ["Windows 免安装包", "原生图译.exe、Python 运行时、OCR 与离线翻译模型"],
        ["完整可编辑源码", "Python、界面资源、词库、启动器 C 源码和构建脚本"],
        ["真实样例结果", "6 份 PDF / 139 页，两种模式共 12 份译文 PDF，附坐标 JSON / CSV"],
        ["复测与文档", "功能测试、参考答案验证、计时证据、使用手册、技术方案、演示稿"],
    ], [42*mm,128*mm])
    add("验收边界：本次在 macOS 上完成实现和实测。Windows 真机、甲方至少 50 份完整图纸的专业准确率和 72 小时稳定性，仍需在指定环境独立验收。", "small")

    page("01  启动与操作")
    for text in ["1. 完整解压 Windows 免安装包到可写目录，双击图译.exe。无需安装 Python 或申请 API。", "2. 点击导入图纸，可多文件排队。留空处理全部页，1-3,5 仅处理指定页。", "3. 选择快速或四方向增强模式。右侧筛选待复核文本，点击条目定位原文。", "4. 修改英文 OCR 和中文译文；保存后可将确认的术语加入个人词库。", "5. 选择遮挡或不遮挡，下载图纸 + JSON + CSV。退出点击左下退出工作台。"]:
        add(text)
    picture(ROOT / "docs/images/不遮挡效果.png",170*mm,103*mm)
    add("不遮挡：红字放在空白区，原英文与工程线保持可见。远移标注的实际位置会保存在导出 JSON。", "small")
    add("遮挡：原文上方叠加白色遮罩。中文框过小时保留可读字号，遮挡原文并移至空白区。原图文件不会被覆盖。")
    add("工作目录 workspace 保留上传副本、修订结果、术语库、缓存和日志；重启后可继续查看已完成任务。日志不自动删除。")

    page("02  算法与数据契约")
    table(["阶段", "实现与作用"], [
        ["解析与识别", "PDF 原生文本优先；扫描和混合页执行本地英文 OCR。增强模式使用白纸对比度、四方向和重叠切片。"],
        ["坐标恢复", "撤销切片偏移与旋转，再映射回显示页。保留多边形、左上角 bbox 和左下角 MinX/MinY/MaxX/MaxY。"],
        ["专业翻译", "术语库和数字模板优先；未匹配文本由 OPUS 英中模型在本地 CPU int8 推理，通用译文保留待复核。"],
        ["保真标注", "PDF 只追加字体与红字，保留原对象；图片保持像素尺寸并以无损方式导出。记录实际标注位置与警告。"],
    ], [36*mm,134*mm])
    add("PDF 坐标单位为 pt，1 pt = 1/72 英寸；图片坐标为 px。显示页左上角 bbox 的 y 向下，任务书左下角坐标的 y 向上：MinY = H - y1，MaxY = H - y0。")
    add("每条记录包含 source、translation、bbox、polygon、confidence、angle、extraction、translation_method、needs_review、enabled 和 warnings。源文件 SHA-256 使输出可追溯。")
    add("JPEG 导出 PNG，避免二次有损压缩；CMYK 位图导出无损 TIFF。灰度图需要转成 RGB 才能显示红字，原灰度像素保持等值 RGB，并明确记录该转换。")
    add("本地接口只绑定 127.0.0.1，并校验 Host、Origin 和操作令牌。所有界面资源随包提供，不依赖 CDN。", "small")

    page("03  实测证据")
    table(["测试", "结果与范围"], [
        ["功能与回归", "23 项通过。覆盖 PDF / PNG / JPG / BMP、旋转、混合页、坐标、红字、保真、修订恢复、异常文件及本地接口保护。"],
        ["参考答案重点验证", f"{gold['correct']} / {gold['expected']} 个验证点通过；OCR 召回 {gold['ocr_recall']:.0%}，已识别术语译文正确率 {gold['translation_accuracy_given_detection']:.0%}。仅为 3 张参考原图中的重点术语，不是全文准确率。"],
        ["批量样例", "6 份 / 139 页全部完成，输出两种模式。所有坐标与译文 JSON 可复核。"],
        ["源码说明比例", f"{comments['ratio']:.1%}，统计非空 Python 行中的 # 注释与模块、类、函数 docstring。"],
    ], [42*mm,128*mm])
    add("六份 PDF 各首页，快速模式、无 OCR 缓存、顺序执行：", "body")
    table(["文件", "提取 + 翻译", "识别区域"], [[c["file"],f"{c['elapsed_seconds']:.3f} 秒",c["regions"]] for c in times["cases"]], [92*mm,43*mm,35*mm])
    add("计时平台为 macOS arm64，非指定 Intel i7 / 16 GB。上述首页均低于 5 秒，但不能推广为所有页面或完整多页文件达标。增强验证约 10–12 秒 / 图，实际耗时见机器可读报告。", "small")
    add("Windows 包完成 x86-64 PE 启动器、官方 Python 和 wheel 组装及静态核对；尚未在 Windows 10/11 真机执行。72 小时测试脚本已提供，未声称本次已连续运行 72 小时。", "small")

    page("04  需求对照与正式验收")
    table(["任务书要求", "当前实现", "验收状态"], [
        ["Python 应用及 UI", "本地 Python 服务 + 双栏图纸工作台", "功能已验证"],
        ["PDF / JPG / PNG / BMP", "原生解析与扫描 OCR，多页批量", "功能已验证"],
        ["英文识别和坐标", "旋转恢复、框、多边形、两种轴原点", "功能已验证；完整召回需金标"],
        ["中文红字与两种遮挡", "空白排版、原文遮罩、实际位置记录", "功能已验证"],
        ["≥95% 专业术语准确率", "词库优先 + 离线神经模型 + 人工复核", "甲方 ≥50 份完整金标待测"],
        ["单图纸 ≤5 秒", "首页无缓存实测 1.64–2.93 秒", "目标硬件与完整文件待测"],
        ["Windows 10/11", "已组装免安装 x86-64 包和自检脚本", "真机待测"],
        ["72 小时无泄漏 / 崩溃", "有界缓存、逐页资源释放、soak 脚本", "72 小时完整运行待测"],
        ["本地安全 / 180 天日志", "无外部推理；每日日志不自动清理", "本地流程与访问保护已测"],
        ["原图分辨率 / 色彩", "PDF 原对象、位图尺寸、无损导出", "灰度红字需 RGB，已明确记录"],
    ], [43*mm,84*mm,43*mm])
    add("建议正式验收：先运行 Windows自检脚本，再用独立完整图纸金标跑 evaluate；在规定硬件禁用缓存计时；最终连续运行 soak_test.py 72 小时并审查 RSS 与错误日志。", "small")
    add("任务书时效加分截止为 2026 年 5 月 31 日；本次交付日期为 2026 年 10 月 13 日，不声明满足该已过期加分条件。", "small")

    page("05  交付文件与复测")
    table(["材料", "用途"], [
        ["图译_Windows免安装版.zip", "完整解压，双击图译.exe；含模型、运行时及源码。"],
        ["图译_源码及模型.zip", "可编辑源代码、词库、模型、测试、输入样例、构建和文档。"],
        ["图译_139页样例结果.zip", "12 份译文 PDF，逐条坐标 JSON、CSV 及批量处理报告。"],
        ["测试证据", "pytest、重点术语 gold、无缓存计时、注释统计与构建 SHA-256。"],
        ["技术文档与演示稿", "详细操作、关键算法、需求对照及约 4 分钟演示步骤。"],
    ], [62*mm,108*mm])
    add("Windows 运行验证：python\\python.exe scripts\\windows_smoke.py。脚本验证实际格式解析、OCR、中文翻译、两种导出、原件 SHA-256，并生成 Windows自检结果.json。")
    add("源码环境功能测试：python -m pytest -q。重点验证：python scripts/evaluate.py。完整 72 小时：python scripts/soak_test.py 输入图纸.pdf --hours 72。性能比较请始终关闭缓存。")
    add("修复记录：保留 CAD 原对象，避免 275,042 个 xref 对象的去重卡顿；嵌入一致字体，解决中英文混排越界；固定 OpenCV 4.11，回归覆盖真实小图放大切片的原生缩放崩溃。")
    add("授权：源码以 AGPL-3.0-or-later 分发，PyMuPDF 采用开源授权；OPUS 模型为 CC-BY-4.0，PaddleOCR / RapidOCR 模型为 Apache-2.0。许可证与模型署名随包提供。", "small")

    def footer(canvas, doc):
        canvas.setStrokeColor(colors.HexColor("#dfe6e7"));canvas.line(20*mm,18*mm,190*mm,18*mm)
        canvas.setFont("Chinese",8);canvas.setFillColor(MUTED)
        canvas.drawString(20*mm,12*mm,"图译  ·  交付与实测  ·  2026-10-13")
        canvas.drawRightString(190*mm,12*mm,str(doc.page))
    document = SimpleDocTemplate(str(OUT / "图译_交付说明与实测报告.pdf"), pagesize=(210*mm,297*mm),
                                rightMargin=20*mm,leftMargin=20*mm,topMargin=20*mm,bottomMargin=25*mm,
                                title="图译：交付说明与实测报告", author="图译项目")
    document.build(story,onFirstPage=footer,onLaterPages=footer)
    print(OUT / "图译_交付说明与实测报告.pdf")


if __name__ == "__main__":
    main()
