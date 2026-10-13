"""Add verified video assets and refresh the outer submission ZIP atomically."""
from pathlib import Path
import json,hashlib,shutil,zipfile,os
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT.parent/'图译交付材料'
WORK=ROOT.parent/'.work/drawing-translator-video/production'
EXCLUDED={'.DS_Store','交付清单.json','图译_比赛交付总包.zip','.图译_比赛交付总包.tmp.zip','英文零件图纸术语自动翻译.zip','.英文零件图纸术语自动翻译.tmp.zip'}
FILES=['图译_演示视频.mp4','演示解说词.md','图译_演示字幕.srt','视频说明.md','视频验收报告.json','视频实测导出成果.zip']
def sha(path):
 digest=hashlib.sha256()
 with path.open('rb') as stream:
  for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
 return digest.hexdigest()
def main():
 report=json.loads((WORK/'视频验收报告.json').read_text())
 assert report['full_decode_passed'] and report['actual_export']['pdf_json_csv_and_download_zip_match']
 assert sha(WORK/'图译_演示视频.mp4')==report['sha256']
 OUT.mkdir(exist_ok=True)
 for name in FILES:shutil.copy2(WORK/name,OUT/name)
 for name in ['演示解说词.md','视频说明.md','视频验收报告.json']:shutil.copy2(WORK/name,ROOT/'docs'/name)
 shutil.copy2(WORK/'演示解说词.md',ROOT/'docs/参赛演示稿.md');shutil.copy2(ROOT/'docs/参赛演示稿.md',OUT/'参赛演示稿.md')
 manual=ROOT/'docs/使用手册.md';marker='\n## 演示视频（2026-10-13 补充）\n'
 text=manual.read_text().split(marker)[0]+marker+'\n提交整包内的 `图译_演示视频.mp4` 为约 2 分 59 秒的真实操作，带中文神经配音和烧录字幕。另附 `演示解说词.md`、`图译_演示字幕.srt`、`视频说明.md`、`视频验收报告.json` 与本次实际导出成果。详情见视频说明。\n\n输入是比赛开发样例；人工复核标记仅演示操作。本次录制实际显示 8.32 秒，不声明满足指定硬件 5 秒要求。正式准确率、Windows 真机和 72 小时测试仍待验收。\n'
 manual.write_text(text,encoding='utf-8');shutil.copy2(manual,OUT/'使用手册.md')
 readme=OUT/'先读我.txt';text=readme.read_text()
 if '5. 演示视频' not in text:text=text.replace('4. 功能、计时与验收边界见 图译_交付说明与实测报告.pdf。','4. 功能、计时与验收边界见 图译_交付说明与实测报告.pdf。\n5. 演示视频见 图译_演示视频.mp4；另附解说词、字幕、视频说明、验收报告和实测导出成果。\n6. 原源码及模型压缩包保留交付基线；最新视频与相关说明独立附在本提交整包中。')
 readme.write_text(text,encoding='utf-8')
 with zipfile.ZipFile(OUT/'视频制作脚本.zip','w',zipfile.ZIP_DEFLATED) as bundle:
  for name in ['build_audio.py','record.py','artifact_server.py','assemble.py','verify.py','write_docs.py','narration.json']:bundle.write(WORK/name,'视频制作脚本/'+name)
  bundle.writestr('视频制作脚本/README.md','# 制作过程归档\n\n脚本记录本次神经配音、真实视口采集、剪辑编码和验证过程，播放视频不需要这些工具。\n\n原始工作目录为比赛 workspace 的 .work/drawing-translator-video/production，应用位于 drawing-translator。使用 Tabbit CLI、本机 Kokoro 中文模型、PyMuPDF、Pillow 和 imageio-ffmpeg。移植时需配置 ROOT、CLI、Python/FFmpeg、模型及输入文件路径。语音模型和原始录制帧未打包。\n\n配音模型来源：https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1；使用 kokoro-v1.1-zh.fp16.onnx、voices-v1.1-zh.bin 和 zf_001 音色。先运行 build_audio.py，再依章节运行 record.py；最后 assemble.py、write_docs.py、verify.py。\n\n导出查看页读取本次真实 PDF；证据阅读页从实际交付记录汇总，没有替换界面业务数据。\n')
 manifest=[]
 for path in sorted(OUT.rglob('*')):
  if path.is_file() and path.name not in EXCLUDED:
   manifest.append({'file':str(path.relative_to(OUT)),'bytes':path.stat().st_size,'sha256':sha(path)})
 (OUT/'交付清单.json').write_text(json.dumps({'date':'2026-10-13','revision':'video-supplement-v1.0.1','items':manifest},ensure_ascii=False,indent=2),encoding='utf-8')
 temporary=OUT/'.图译_比赛交付总包.tmp.zip';combined=OUT/'图译_比赛交付总包.zip'
 with zipfile.ZipFile(temporary,'w',zipfile.ZIP_STORED) as bundle:
  for path in sorted(OUT.rglob('*')):
   if path.is_file() and (path.name not in EXCLUDED or path.name=='交付清单.json'):bundle.write(path,'图译交付材料/'+str(path.relative_to(OUT)))
 with zipfile.ZipFile(temporary) as bundle:assert bundle.testzip() is None
 temporary.replace(combined)
 alias=OUT/'英文零件图纸术语自动翻译.zip';backup=WORK.parent/'原始交付总包留档.zip'
 if alias.exists() and not backup.exists():shutil.copy2(alias,backup)
 alias_temporary=OUT/'.英文零件图纸术语自动翻译.tmp.zip';alias_temporary.unlink(missing_ok=True)
 os.link(combined,alias_temporary);alias_temporary.replace(alias)
 print(json.dumps({'bundle':str(combined),'bytes':combined.stat().st_size,'sha256':sha(combined),'video':report['video_file'],'seconds':report['duration_seconds'],'separate_files':len(manifest)},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
