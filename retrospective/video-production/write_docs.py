"""Write the measured voice script, SRT and truthful video production notes."""
from pathlib import Path
import json
WORK=Path(__file__).resolve().parent
scenes=json.loads((WORK/'narration.json').read_text())
def stamp(seconds):
 ms=round(seconds*1000);hours,ms=divmod(ms,3600000);minutes,ms=divmod(ms,60000);secs,ms=divmod(ms,1000)
 return f'{hours:02}:{minutes:02}:{secs:02},{ms:03}'
md=['# 图译演示视频解说词','','成片约 2 分 59 秒。开发样例真实操作，中文神经语音与字幕；复核示例标记为人工演示输入，不是原图内容。','']
srt=[];offset=0;number=1
for i,scene in enumerate(scenes):
 md.extend([f"## {i+1:02} {scene['title']} · {stamp(offset).replace(',', '.')} — {stamp(offset+scene['seconds']).replace(',', '.')}",''])
 for caption in scene['captions']:
  md.extend([f"**{stamp(offset+caption['start']).replace(',', '.')}** {caption['spoken']}",''])
  if caption['text']!=caption['spoken']:md.extend(['字幕：'+caption['text'],''])
  srt.extend([str(number),f"{stamp(offset+caption['start'])} --> {stamp(offset+caption['end'])}",caption['text'],'']);number+=1
 offset+=scene['seconds']
md.extend(['## 用词与真实性','','“槽深”对应界面中的 GROOVE DEPTH；“点”对应 PDF 的 pt 单位；图片坐标 px 的功能在既有格式测试中验证，本视频操作的是一页 PDF。','', '视频中的“槽深（复核示例）”由录制时真实输入并保存，仅演示修订流程。它进入本次导出文件与隔离个人术语库，不是专业译文改进结论。','', '本次处理界面实际显示 1 页、74 个文本区域、65 条译文、14 条待复核，耗时 8.32 秒。运行期间同时录制视口，未启用已有 OCR 缓存。这不是指定 i7/16GB 环境的性能验收。',''])
(WORK/'演示解说词.md').write_text('\n'.join(md),encoding='utf-8')
(WORK/'图译_演示字幕.srt').write_text('\n'.join(srt),encoding='utf-8')
notes='''# 图译演示视频与复现说明

- **图译_演示视频.mp4**：约 2 分 59 秒，1920×1080，24fps 编码，H.264 / AAC。中文神经语音与烧录字幕，另附 UTF-8 SRT。
- **演示解说词.md**：口语化逐章解说与实际时间码。
- **图译_演示字幕.srt**：按实际神经语音合成片段起止时间生成，可独立导入剪辑软件。
- **视频验收报告.json**：文件校验、完整解码、音量、视口采样、章节、实际导出和验证范围。
- **视频实测导出成果.zip**：视频中按钮实际生成的 PDF、JSON 与 CSV，含人工复核示例标记。

## 内容顺序

业务问题 → 输入开发样例 → 本机识别 → 查看双栏结果 → 搜索定位与坐标 → 实际输入修订和保存 → 两种标注模式 → 点击导出 → 查看实际 PDF 的渲染预览 → 阅读实际测试证据及待验收范围。

## 声音和画面

声音使用本机 Kokoro 中文 v1.1 神经模型、zf_001 音色。句间停顿约 0.28–0.44 秒，轻微语速变化约 1.00–1.035 倍。没有调用在线语音或翻译服务，没有额外配背景音乐。

画面为 Tabbit 浏览器视口连续采集，保留真实鼠标移动、点击、逐字输入、滚动、等待和状态变化。按真实采集时间编码成 24fps；重复帧只是维持时间，不代表源视口达到 24fps。实际采样率在验收报告中记录。章节之间裁掉制作调度空档，本次本机处理等待保留；字幕放在独立底栏，不遮挡应用文字。

鼠标提示跟随实际 mousemove/mousedown，未改写应用结果。仅隐藏与图译无关的浏览器辅助浮层。浏览器原生 PDF 插件会关闭录制页，因此结果阅读使用本机 PyMuPDF 对本次实际导出 PDF 的即时无损渲染，图纸内容没有重新绘制。最后的证据阅读页直接读取既有 pytest、参考答案和批量处理记录，明确标注为证据汇总，不是产品新增功能。

## 真实性和验收范围

本视频输入为比赛开发样例单页 PDF，不是生产业务数据，没有新增模拟工程数值。真实识别为 74 个区域、65 条译文、14 条待复核。操作时耗时 8.32 秒，保留实际界面数值；不能用该录制环境证明指定硬件 5 秒要求。

“槽深（复核示例）”是为演示人工修改流程输入的标记，不是图纸原文或已核准的专业译文。个人词库使用独立录制目录，不改动交付原始词库。导出后逐条核对 JSON/CSV 和 PDF，原件哈希不变。

已验证：23 项功能测试、三张参考原图的 20 个选定术语点、六份 PDF / 139 页两种导出。20/20 不能推断完整图纸 ≥95% 专业准确率。Windows 真机、≥50 份完整金标、指定 i7/16GB 完整文件性能及 72 小时稳定性仍需正式验收。

## 同步交付

视频、解说词、字幕、验收报告和本次导出成果已经纳入更新后的比赛提交整包。原 Windows 程序、源码及模型包、139 页结果与报告保留，不用视频代替功能或验收证据。
'''
(WORK/'视频说明.md').write_text(notes,encoding='utf-8')
print('文稿及字幕完成',number-1,'个字幕段',offset,'秒')
