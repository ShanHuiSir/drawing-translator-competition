# 演示视频制作复盘

这组脚本记录中文神经语音、连续真实浏览器操作采集、编码和文件验证。详情见 ../../docs/视频说明.md。

脚本原始位置为比赛 workspace/.work/drawing-translator-video/production，应用位于 workspace/drawing-translator。它们是本机制作过程的归档，移植时需调整 ROOT、CLI、模型、Python/FFmpeg 与输入文件路径。运行环境包括 Tabbit、Kokoro 中文模型、misaki、PyMuPDF、Pillow 和 imageio-ffmpeg。语音模型与原始帧未提交到 Git。

先 build_audio.py，再分章 record.py，最后 assemble.py、write_docs.py、verify.py。录制过程只添加鼠标提示并隐藏浏览器辅助浮层，不修改应用结果；PDF 预览直接渲染实际导出的文件。
