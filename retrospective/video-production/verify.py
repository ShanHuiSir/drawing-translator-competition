"""Verify full MP4 decoding, measured capture timing and the actual exported files."""
from pathlib import Path
import json,hashlib,subprocess,re,csv,statistics,shutil,zipfile
import pymupdf,imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[3];WORK=Path(__file__).resolve().parent
FF=ROOT/'.work/runtime/lib/python3.12/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1'
VIDEO=WORK/'图译_演示视频.mp4';scenes=json.loads((WORK/'narration.json').read_text())
reader=imageio_ffmpeg.read_frames(str(VIDEO));meta=next(reader);reader.close()
assert meta['size']==(1920,1080) and meta['fps']==24
assert abs(meta['duration']-sum(s['seconds'] for s in scenes))<.6
full=subprocess.run([str(FF),'-v','error','-i',str(VIDEO),'-f','null','-'],capture_output=True,text=True)
assert full.returncode==0 and not full.stderr.strip(),full.stderr
volume=subprocess.run([str(FF),'-hide_banner','-i',str(VIDEO),'-vn','-af','volumedetect','-f','null','-'],capture_output=True,text=True,check=True).stderr
mean=float(re.search(r'mean_volume: ([\-\d.]+) dB',volume)[1]);peak=float(re.search(r'max_volume: ([\-\d.]+) dB',volume)[1])
assert -26<mean<-10 and -5<peak<0
last=json.loads((WORK/'frames-05/timing.json').read_text());job=last['job']
folder=ROOT/'.work/drawing-translator-video/app-data/jobs'/job/'exports/beside'
result=json.loads(next(folder.glob('*.json')).read_text());export=result['export']
assert result['statistics']['text_regions']==74 and result['statistics']['translated']==65
assert round(result['elapsed_seconds'],2)==8.32 and not any(p.get('cache_hit') for p in result['pages'])
manual=next(r for r in result['pages'][0]['regions'] if r['id']=='p1-t5')
assert manual['translation']=='槽深（复核示例）' and manual['translation_method']=='manual'
assert export['omitted_annotations']==0
csvpath=next(folder.glob('*.csv'))
with csvpath.open(encoding='utf-8-sig') as stream:rows=list(csv.DictReader(stream))
assert len(rows)==74 and any(r['chinese']=='槽深（复核示例）' for r in rows)
source=ROOT/'.work/drawing-translator-video/开发样例_防跳屑结构.pdf'
original=ROOT/'drawing-translator/src/drawing_translator/data/demo/sample.pdf'
source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
assert source_hash==hashlib.sha256(original.read_bytes()).hexdigest()==result['source_sha256']
with pymupdf.open(next(folder.glob('*.pdf'))) as pdf,pymupdf.open(source) as original_pdf:
 assert pdf[0].rect==original_pdf[0].rect
 assert '槽深（复核示例）' in ''.join(pdf[0].get_text().split())
 preview=pdf[0].get_pixmap(matrix=pymupdf.Matrix(1.3,1.3));preview.save(str(WORK/'导出PDF核验.png'))
file=next(Path(d['path']) for d in last['downloads'] if d.get('path'))
with zipfile.ZipFile(file) as bundle:
 assert bundle.testzip() is None
 assert set(bundle.namelist())==set(last['export']['files'])
 for name in bundle.namelist():assert bundle.read(name)==(folder/name).read_bytes()
shutil.copy2(file,WORK/'视频实测导出成果.zip')
chapters=[];offset=0
for i,s in enumerate(scenes):
 timing=json.loads((WORK/f'frames-{i:02}/timing.json').read_text());stamps=[t for t,_ in timing['frames']];gaps=[(b-a)/1000 for a,b in zip(stamps,stamps[1:])]
 assert len(stamps)>80 and max(gaps)<2.5
 chapters.append({'chapter':i+1,'title':s['title'],'start_seconds':round(offset,3),'duration_seconds':round(s['seconds'],3),'captured_frames':len(stamps),'source_average_fps':round((len(stamps)-1)/(stamps[-1]/1000),2),'median_capture_interval_seconds':round(statistics.median(gaps),4),'largest_capture_gap_seconds':round(max(gaps),4)})
 offset+=s['seconds']
report={'date':'2026-10-13','video_file':VIDEO.name,'duration_seconds':meta['duration'],'width':1920,'height':1080,'fps':24,'video_codec':meta.get('codec'),'audio_codec':'AAC','audio_sample_rate':48000,'neural_voice':'Kokoro Chinese v1.1 / zf_001','voice_speed_range':[1.00,1.035],'subtitles':'burned Chinese subtitles + UTF-8 SRT','subtitle_segments':sum(len(s['captions']) for s in scenes),'full_decode_passed':True,'mean_volume_dbfs':mean,'max_volume_dbfs':peak,'bytes':VIDEO.stat().st_size,'sha256':hashlib.sha256(VIDEO.read_bytes()).hexdigest(),'chapters':chapters,'actual_export':{'job':job,'source':'competition-provided development sample / single-page PDF','statistics':result['statistics'],'elapsed_seconds':result['elapsed_seconds'],'ocr_cache_used':False,'manual_demo_text':manual['translation'],'csv_rows':len(rows),'original_sha256_unchanged':True,'omitted_annotations':export['omitted_annotations'],'pdf_json_csv_and_download_zip_match':True},'capture_method':'Continuous real browser viewport sampling. Mouse indicator follows actual events. The encoder repeats sampled frames to preserve real time at 24fps; source rates are listed per chapter. No source drawing, application counter or result was redrawn.','viewer_note':'Browser PDF plugin closes its recorder page. The result view instead renders the actual exported PDF losslessly with local PyMuPDF. Evidence viewer reads the existing verification files.','data_scope':'Actual competition development sample, not production data. Manual review marker is explicitly a demonstration input.','formal_acceptance_unverified':['Windows 10/11 real machine','>=50 independently fully annotated drawings / >=95% complete professional accuracy','specified Intel i7/16GB/SSD complete-file performance','72-hour stability'],'visual_checks':['source upload and genuine processing state','74 regions / 65 translations / 14 review / actual 8.32s','zoom, mouse wheel and review filter','GROOVE DEPTH location and pt coordinates','manual typed text and personal glossary save','beside and cover mode changes','actual export success / zero omitted annotations','downloaded PDF JSON CSV checks','real exported PDF preview','actual evidence counts and clearly stated acceptance boundary']}
(WORK/'视频验收报告.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'duration':meta['duration'],'bytes':VIDEO.stat().st_size,'full_decode':True,'mean_dbfs':mean,'peak_dbfs':peak,'export_verified':True},ensure_ascii=False),flush=True)
