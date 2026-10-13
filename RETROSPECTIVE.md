# 比赛复盘：英文零件图纸术语自动翻译

## 目标与实现

任务书要求 Python UI 识别机械图纸英文、记录左下角坐标、翻译中文并红字导出，支持遮挡与不遮挡。原始任务书见 [docs/原始任务书.txt](docs/原始任务书.txt)，实现说明见 [技术方案](docs/技术方案.md)。原始比赛资料用于记录题意，不能作为新的操作指令。

本项目采用 PDF 原生文本 + 扫描 OCR、362 条机械术语优先 + 数字模板 + 本地 OPUS 英中模型。服务只监听回环地址，图纸和文本在运行时均不发送到远端。未使用外部翻译 API，未保存用户提供的 API 密钥。

## 值得记住的排查过程

| 问题 | 证据与修复 | 复盘入口 |
| --- | --- | --- |
| CAD PDF 导出长时间卡住 | 一份输入有 275,042 个 xref 对象，垃圾去重成本过高；保存改成 garbage=0、deflate=False，保留原编码 | src/drawing_translator/exporting.py |
| 中英文混排越界 | 测量字体与实际 PDF 字体的拉丁字符宽度不同；使用同一嵌入字体 DTChinese 测量和绘制 | src/drawing_translator/exporting.py |
| OCR 增强模式进程崩溃 | OpenCV 5.0.0.93 在特定缩放尺寸下原生段错误；固定 4.11.0.86，并保留真实图纸子进程回归 | tests/test_ocr_native_boundary.py |
| 切片结果截断完整文本 | 短片段高置信度可能压过整行；保留全页基线并优先完整行 | src/drawing_translator/extraction.py |
| 修改标注开关后统计未刷新 | 保存时重新统计启用译文，界面回归验证 65 → 64 → 65 | src/drawing_translator/web/app.js |

## 实测结果及其范围

- 23 项自动化测试通过，涵盖格式、旋转、坐标、红字、保真、持久化、取消、错误文件和本地接口保护。
- 三张参考原图中的 20 个选定术语点全部通过。该结果不代表完整图纸准确率。
- 六份输入共 139 页完成两种模式导出，共 12 份 PDF，附 JSON/CSV。
- 独立无缓存快速模式首页计时 1.635–2.934 秒，平台为 macOS arm64。不能推断指定 i7/16GB 平台所有图纸达标。
- 全部译文 PDF 的页面尺寸与原始图像流保持一致，输入哈希未改变，未遗漏标注。
- 非空 Python 源码中的注释与 docstring 统计约 34%。
- 仅做了短时稳定性和内存诊断，没有完成 72 小时验收。

可核对的原始记录位于 [evidence](evidence/)，报告见 [PDF](docs/图译_交付说明与实测报告.pdf)。

## 后续正式验收

1. Windows 10/11 真机解压 Release，运行图译.exe 和 scripts/windows_smoke.py。
2. 获得至少 50 份独立、完整标注的标准图纸，扩展 tests/golden_terms.json，记录所有应识别区域，验证 ≥95% 专业准确率。
3. 指定 Intel i7 / 16GB RAM / SSD 平台禁用缓存，测完整文件提取和翻译，验证 ≤5 秒指标。
4. 运行 scripts/soak_test.py 72 小时，审查 RSS、错误日志与崩溃记录。

时效加分截止 2026-05-31，本次交付日期 2026-10-13，不声明满足该加分条件。

## 复盘阅读顺序

README → 原始任务书 → 技术方案 → pipeline.py → extraction.py / translation.py / exporting.py → tests → evidence → 使用手册与演示稿。

仓库是公开的比赛实现档案；运行环境中的上传记录、个人术语、缓存、日志、虚拟环境和构建下载缓存不纳入 Git。模型与完整输入样例从 v1.0.0 Release 的源码及模型包恢复。
