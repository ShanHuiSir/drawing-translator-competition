"""Rebuild the complete video submission from immutable public release assets.

Downloads happen only when this setup command is explicitly run. Every file is
checked against the delivery manifest before it is included in the final ZIP.
--asset-dir enables fully offline restoration from already downloaded assets.
"""
import argparse,hashlib,json,shutil,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE='https://github.com/ShanHuiSir/drawing-translator-competition/releases/download/'
ASSETS={
 '图译_Windows免安装版.zip':('v1.0.0','windows-portable.zip'),
 '图译_源码及模型.zip':('v1.0.0','source-models.zip'),
 '图译_139页样例结果.zip':('v1.0.0','sample-results-139-pages.zip'),
 '图译_演示视频.mp4':('v1.0.1','drawing-translator-demo.mp4'),
 '演示解说词.md':('v1.0.1','demo-narration.md'),
 '图译_演示字幕.srt':('v1.0.1','demo-subtitles.srt'),
 '视频说明.md':('v1.0.1','demo-readme.md'),
 '视频验收报告.json':('v1.0.1','demo-verification.json'),
 '视频实测导出成果.zip':('v1.0.1','demo-actual-exports.zip'),
 '视频制作脚本.zip':('v1.0.1','video-production-scripts.zip'),
}

def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as stream:
  for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
 return h.hexdigest()

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--output',type=Path,default=ROOT/'delivery')
 parser.add_argument('--asset-dir',type=Path,help='缓存的Release附件目录；可使用英文发行名或原始中文文件名')
 args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
 manifest_path=ROOT/'evidence/视频提交清单.json'
 manifest=json.loads(manifest_path.read_text('utf-8'))
 for item in manifest['items']:
  relative=Path(item['file'])
  if relative.is_absolute() or '..' in relative.parts:raise ValueError('非法清单路径')
  target=out/relative
  if target.exists() and digest(target)==item['sha256']:continue
  target.parent.mkdir(parents=True,exist_ok=True)
  asset=ASSETS.get(item['file']);source=None
  if args.asset_dir:
   candidates=[args.asset_dir/relative]
   if asset:candidates.append(args.asset_dir/asset[1])
   source=next((p for p in candidates if p.is_file()),None)
  if source is None and asset:
   if args.asset_dir:raise FileNotFoundError(f'离线资源缺失：{asset[1]}')
   temporary=target.with_name(target.name+'.download')
   try:
    request=urllib.request.Request(BASE+asset[0]+'/'+asset[1],headers={'User-Agent':'drawing-translator-delivery/1.0.1'})
    print('下载',asset[1],flush=True)
    with urllib.request.urlopen(request,timeout=120) as response,temporary.open('wb') as stream:shutil.copyfileobj(response,stream)
    if digest(temporary)!=item['sha256']:raise ValueError(f'下载校验失败：{asset[1]}')
    temporary.replace(target)
   finally:temporary.unlink(missing_ok=True)
  elif source is None:
   if relative.parts[0]=='测试证据':source=ROOT/'evidence'/Path(*relative.parts[1:])
   elif item['file']=='先读我.txt':source=ROOT/'docs/提交包先读我.txt'
   else:source=ROOT/'docs'/relative
  if source is not None:shutil.copy2(source,target)
  if target.stat().st_size!=item['bytes'] or digest(target)!=item['sha256']:raise ValueError(f'交付文件校验失败：{relative}')
 shutil.copy2(manifest_path,out/'交付清单.json')
 temporary=out/'.submission.tmp.zip';final=out/'图译_比赛交付总包.zip'
 with zipfile.ZipFile(temporary,'w',zipfile.ZIP_STORED) as archive:
  for relative in [i['file'] for i in manifest['items']]+['交付清单.json']:
   archive.write(out/relative,'图译交付材料/'+relative)
 with zipfile.ZipFile(temporary) as archive:
  if archive.testzip() is not None:raise ValueError('整包CRC校验失败')
 temporary.replace(final)
 print('完整整包内容已恢复：',final,flush=True)

if __name__=='__main__':main()
