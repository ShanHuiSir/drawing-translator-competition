"""Encode measured browser frames with synchronized narration and Chinese subtitles."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import json,subprocess,math,bisect,sys
ROOT=Path(__file__).resolve().parents[3];WORK=Path(__file__).resolve().parent
FF=ROOT/'.work/runtime/lib/python3.12/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1'
FONT='/System/Library/Fonts/Hiragino Sans GB.ttc'
SCENES=json.loads((WORK/'narration.json').read_text());FPS=24
fonts={n:ImageFont.truetype(FONT,n) for n in [18,20,30]}

def wrap(draw,text,font,width):
 lines=[];line=''
 for char in text:
  if draw.textlength(line+char,font=font)>width:lines.append(line);line=char
  else:line+=char
 if line:lines.append(line)
 return lines

def render(i,base,seconds):
 scene=SCENES[i];im=base.copy();draw=ImageDraw.Draw(im)
 draw.rectangle((0,0,1920,32),fill='#eef3f4')
 draw.text((20,2),'图译 · 真实操作 / 比赛开发样例',font=fonts[20],fill='#314b5a')
 title=f"{i+1:02} / 07   {scene['title']}"
 draw.text((1900-draw.textlength(title,font=fonts[20]),2),title,font=fonts[20],fill='#14776e')
 draw.rectangle((0,992,1920,1080),fill='#18313e')
 caption=next((c['text'] for c in scene['captions'] if c['start']<=seconds<=c['end']),None)
 if caption:
  lines=wrap(draw,caption,fonts[30],1770);assert len(lines)<=2
  for j,line in enumerate(lines):draw.text(((1920-draw.textlength(line,font=fonts[30]))/2,998+j*37+(18 if len(lines)==1 else 0)),line,font=fonts[30],fill='white')
 else:draw.text((20,1023),'本机实测 · 原图不覆盖 · 正式验收范围见随附说明',font=fonts[18],fill='#d1dde2')
 return im

for i in ([int(x) for x in sys.argv[1:]] or range(len(SCENES))):
 scene=SCENES[i];folder=WORK/f'frames-{i:02}';timing=json.loads((folder/'timing.json').read_text());stamps=[x[0]/1000 for x in timing['frames']]
 target=WORK/f'clip-{i:02}.mp4'
 cmd=[str(FF),'-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-r',str(FPS),'-i','pipe:0','-i',str(WORK/f'audio-{i:02}.wav'),'-t',str(scene['seconds']),'-af','highpass=f=65,loudnorm=I=-16:TP=-1.5:LRA=11','-ar','48000','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k',str(target)]
 process=subprocess.Popen(cmd,stdin=subprocess.PIPE)
 last=-1;base=None
 try:
  for frame in range(math.ceil(scene['seconds']*FPS)):
   t=frame/FPS;index=max(0,bisect.bisect_right(stamps,t)-1)
   if index!=last:
    shot=Image.open(folder/timing['frames'][index][1]).convert('RGB').resize((1920,960),Image.Resampling.LANCZOS)
    base=Image.new('RGB',(1920,1080),'#eef3f4');base.paste(shot,(0,32));last=index
   im=render(i,base,t)
   if frame in [24,round(scene['seconds']*FPS/2),math.ceil(scene['seconds']*FPS)-24]:im.save(WORK/f'qa-{i:02}-{frame:04}.png')
   process.stdin.write(im.tobytes())
 finally:process.stdin.close()
 if process.wait()!=0:raise RuntimeError('视频编码失败')
 print('ENCODED',i,scene['title'],round(scene['seconds'],2),flush=True)
if all((WORK/f'clip-{i:02}.mp4').exists() for i in range(len(SCENES))):
 listing=WORK/'concat.txt';listing.write_text(''.join(f"file '{WORK/f'clip-{i:02}.mp4'}'\n" for i in range(len(SCENES))))
 final=WORK/'图译_演示视频.mp4'
 subprocess.run([str(FF),'-y','-v','error','-f','concat','-safe','0','-i',str(listing),'-c','copy','-movflags','+faststart',str(final)],check=True)
 print('FINAL',str(final),sum(s['seconds'] for s in SCENES),final.stat().st_size,flush=True)
