"""Create conversational Chinese neural narration with measured subtitle boundaries."""
from pathlib import Path
import json, wave
import numpy as np
from kokoro_onnx import Kokoro
from misaki.zh import ZHG2P
ROOT=Path(__file__).resolve().parents[3]
WORK=Path(__file__).resolve().parent
SCENES=[
 {'title':'业务问题','parts':[
 '看英文零件图纸，麻烦的往往不只是翻译，还得反复找到原文在哪儿。',
 '我用图译走一遍：导入图纸，识别英文，核对中文，最后把标注和坐标一起导出。',
 '这里用的是比赛提供的开发样例，不是生产业务图纸。'], 'hold':1.2},
 {'title':'输入文件','parts':[
 '先选快速识别，再填第一页。多页文件也可以只处理指定页码。',
 '现在导入这份防跳屑结构样例。文件进来以后，就开始在本机识别和翻译。',
 '这一段是真实运行，界面的等待和结果变化都保留了。'], 'hold':1.5},
 {'title':'查看识别结果','parts':[
 '结果出来了。左边是英文原图，右边是红色中文，文本和译文数量都来自这次处理。',
 '我把图放大一点，再滚动看一下，红字和原图可以对照着读。',
 '机械术语先查本地词库，没匹配上的再用离线翻译模型。需要人工确认的，会标成待复核。'], 'hold':2.0},
 {'title':'定位与人工复核','parts':[
 {'say':'我先找一下槽深。点开这条，左边就定位到原文，下面能看到它的坐标。','text':'我先找一下 GROOVE DEPTH（槽深）。点开这条，左边定位原文，下方显示坐标。'},
 '这份是文档，坐标单位是点，采用左下角原点。图片文件则记录像素坐标。',
 '接着，我加一个复核示例标记，演示修改和保存。这个标记不是原图内容。',
 '勾上个人术语库，再保存。刚才输入的译文会更新到预览里，也会进入导出结果。'], 'hold':2.0},
 {'title':'切换标注方式','parts':[
 '现在看两种标注方式。先是不遮挡，英文还在，中文放到旁边的空白位置。',
 '切换到遮挡模式，原文上方会加白色遮罩，再显示红字。',
 '如果原来的框太小，系统会移动标注，实际放置的位置也会记录。导出不会覆盖原文件。'], 'hold':2.0},
 {'title':'导出成果','parts':[
 '最后切回不遮挡，点击导出图纸与坐标。',
 '生成的是一个压缩包，里面有中文标注图纸、逐条坐标数据，以及可以用表格软件打开的清单。',
 '我打开刚才实际导出的文件看一下。这里的复核标记也保留下来了，不是另外做的效果图。'], 'hold':2.5},
 {'title':'验证范围与交付','parts':[
 '这一轮展示的是开发样例的真实处理、定位、修订和导出。没有使用在线翻译接口。',
 '已有二十三项功能测试和二十个选定参考术语点通过，六份图纸、一百三十九页完成了两种模式导出。',
 '这些结果不等于全文准确率达标。微软桌面端、完整标准集准确率、指定硬件性能和七十二小时稳定性，还需要正式验收。',
 '程序、源码、文档和这段演示都一起交付，后面可以按刚才的步骤复现。'], 'hold':1.8}
]
model=ROOT/'.work/tablebridge/neural-model'
k=Kokoro(str(model/'kokoro-v1.1-zh.fp16.onnx'),str(model/'voices-v1.1-zh.bin'))
g=ZHG2P(version='1.1')
voice='zf_001'
for i,s in enumerate(SCENES):
 samples=[np.zeros(9600,dtype=np.float32)];captions=[];elapsed=.4
 for j,part in enumerate(s['parts']):
  spoken=part if isinstance(part,str) else part['say'];text=part if isinstance(part,str) else part['text']
  phonemes,_=g(spoken);speed=[1.02,1.00,1.035,1.015][(i+j)%4]
  audio,sr=k.create(phonemes,voice=voice,speed=speed,is_phonemes=True,sentence_pause=.34,clause_pause=.14)
  assert sr==24000 and np.isfinite(audio).all() and len(audio)>sr*.6
  captions.append({'start':round(elapsed,4),'end':round(elapsed+len(audio)/sr,4),'text':text,'spoken':spoken,'speed':speed})
  pause=[.32,.44,.28,.38][j%4];samples.extend([audio,np.zeros(round(sr*pause),dtype=np.float32)]);elapsed+=len(audio)/sr+pause
 samples.append(np.zeros(round(sr*s['hold']),dtype=np.float32));combined=np.concatenate(samples)
 with wave.open(str(WORK/f'audio-{i:02}.wav'),'wb') as w:
  w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr);w.writeframes((np.clip(combined,-1,1)*32767).astype('<i2').tobytes())
 s.update(captions=captions,seconds=len(combined)/sr,voice=voice)
 print(i,s['title'],round(s['seconds'],2),flush=True)
(WORK/'narration.json').write_text(json.dumps(SCENES,ensure_ascii=False,indent=2),encoding='utf-8')
print('TOTAL',sum(s['seconds'] for s in SCENES),flush=True)
