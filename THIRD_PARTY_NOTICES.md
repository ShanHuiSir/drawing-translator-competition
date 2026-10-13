# 第三方组件与模型说明

原创应用源代码以 AGPL-3.0-or-later 分发，完整许可见 LICENSE。本交付同时提供可编辑源码和启动器 C 源码。

| 组件 | 许可 / 说明 | 官方来源 |
|---|---|---|
| PyMuPDF / MuPDF | AGPLv3 或 Artifex 商业授权；当前使用开源版本 | https://github.com/pymupdf/PyMuPDF |
| CPython 3.12.10 Windows embeddable | Python Software Foundation License；许可位于 python/LICENSE.txt | https://www.python.org/downloads/release/python-31210/ |
| RapidOCR | Apache-2.0 | https://github.com/RapidAI/RapidOCR |
| PaddleOCR 英文模型 | Apache-2.0；模型下载由 RapidAI 提供，版本与 SHA-256 见 models/ocr/source.json | https://huggingface.co/SWHL/RapidOCR |
| ONNX Runtime | MIT；ThirdPartyNotices 随包保留 | https://github.com/microsoft/onnxruntime |
| OpenCV | Apache-2.0；固定 4.11.0.86，避开已复现的 OpenCV 5 原生缩放崩溃 | https://opencv.org/license/ |
| CTranslate2 | MIT；依赖 DLL 的原始许可证保留在包元数据中 | https://github.com/OpenNMT/CTranslate2 |
| SentencePiece | Apache-2.0 | https://github.com/google/sentencepiece |
| OPUS-MT en→zh / Argos 1.9 | 模型 CC-BY-4.0，署名见下文 | https://argos-net.com/v1/translate-en_zh-1_9.argosmodel |
| 内嵌中文字体 | MuPDF 提供的 Droid Sans Fallback / Apache-2.0 字体；用于 PDF 与图片一致绘制 | https://github.com/ArtifexSoftware/mupdf |
| FastAPI / Uvicorn / Pillow / NumPy 等 | 以各自发行包 LICENSE / dist-info 为准，原始元数据随 Windows 包保留 | 对应官方发行项目 |

OPUS-MT 模型署名：Jörg Tiedemann and Santhosh Thottingal, “OPUS-MT — Building open translation services for the World”, Proceedings of the 22nd Annual Conference of the European Association for Machine Translation (EAMT), Lisbon, 2020。模型由 Argos Open Technologies 打包；许可：https://creativecommons.org/licenses/by/4.0/ 。本应用直接以 CTranslate2 读取模型，不调用在线翻译服务，也不修改模型权重。

Windows 包中的所有下载轮子和 CPython 存档具有 SHA-256 构建清单。模型下载记录亦已保留。未将用户提供的 DeepSeek API 密钥写入源码、模型、运行包或说明文档。
