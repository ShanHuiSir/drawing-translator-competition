"""Record actual Tabbit viewport frames, paced to measured neural narration.

Only a cursor/click indicator and hiding unrelated browser-extension overlays are
injected. Drawing content, application results, counters and status stay untouched.
"""
from pathlib import Path
import json,subprocess,shutil,sys,time
ROOT=Path(__file__).resolve().parents[3];WORK=Path(__file__).resolve().parent
CLI='/Users/niou9/.local/bin/tabbit-cli';TASK='图译演示视频'
scenes=json.loads((WORK/'narration.json').read_text())
HELPERS=r'''
const pause=ms=>new Promise(r=>setTimeout(r,ms));
const until=async seconds=>{await pause(Math.max(0,seconds*1000-(Date.now()-start)));};
const install=async()=>{await page.evaluate(()=>{
 const style=document.createElement('style');style.textContent='doubao-ai-csui,#doubao-ai-assistant,[id^="doubao-ai-translate-image-assistant"],.cici-ext-container{display:none!important}';document.head.append(style);
 if(document.getElementById('video-cursor'))return;
 const e=document.createElement('div');e.id='video-cursor';e.style.cssText='position:fixed;left:0;top:0;width:23px;height:31px;pointer-events:none;z-index:99999;filter:drop-shadow(0 1px 2px #666)';e.innerHTML='<svg width="23" height="31" viewBox="0 0 24 32"><path d="M2 2 L2 25 L8 20 L13 30 L17 28 L12 18 L22 18 Z" fill="white" stroke="#172b3b" stroke-width="1.5"/></svg>';document.body.append(e);
 document.addEventListener('mousemove',v=>{window.videoMouse={x:v.clientX,y:v.clientY};e.style.transform=`translate(${v.clientX}px,${v.clientY}px)`;});
 document.addEventListener('mousedown',v=>{const r=document.createElement('div');r.style.cssText=`position:fixed;left:${v.clientX-20}px;top:${v.clientY-20}px;width:40px;height:40px;border:2px solid #14776e;border-radius:50%;pointer-events:none;z-index:99998`;document.body.append(r);r.animate([{opacity:.8,transform:'scale(.6)'},{opacity:0,transform:'scale(1.4)'}],{duration:500}).finished.then(()=>r.remove());});
});};
const move=async loc=>{const b=await loc.boundingBox();if(!b)throw Error('目标不可见');const from=await page.evaluate(()=>window.videoMouse||{x:110,y:110});const to={x:b.x+b.width/2,y:b.y+b.height/2};for(let k=1;k<=15;k++){await page.mouse.move(from.x+(to.x-from.x)*k/15,from.y+(to.y-from.y)*k/15);await pause(22);}};
const click=async loc=>{await move(loc);await loc.click();};
const keyboardClick=async loc=>{await move(loc);await loc.focus();await page.keyboard.press('Enter');};
const scroll=async(loc,dx,dy)=>{await move(loc);for(let k=0;k<14;k++){await page.mouse.wheel(dx/14,dy/14);await pause(30);}};
await install();
const frames=[];let done=false;const downloads=[];const start=Date.now();
const capture=(async()=>{while(!done){const t=Date.now()-start;const shot=await page.screenshot({fullPage:false});frames.push([t,shot.path]);await pause(Math.max(0,120-(Date.now()-start-t)));}})();
'''
ACTIONS=[
 r'''await move(page.getByRole('heading',{level:1}));await until(C[1].start+.5);await move(page.getByRole('button',{name:'选择图纸',exact:true}));await until(C[2].start+.3);await move(page.locator('.local-badge'));''',
 r'''await click(page.getByRole('combobox',{name:'识别方式',exact:true}));await page.getByRole('combobox',{name:'识别方式',exact:true}).selectOption('fast');await click(page.getByRole('textbox',{name:'处理页码',exact:true}));await page.getByRole('textbox',{name:'处理页码',exact:true}).pressSequentially('1',{delay:180});await until(C[1].start+.25);const waiter=page.waitForEvent('filechooser');await click(page.getByRole('button',{name:'＋ 导入图纸',exact:true}));await(await waiter).setFiles('/Users/niou9/Documents/ChatGPT/百景大赛/.work/drawing-translator-video/开发样例_防跳屑结构.pdf');await expect(page.locator('#document-name')).toHaveText('开发样例_防跳屑结构.pdf');await expect(page.locator('#export-button')).toBeEnabled({timeout:60000});await expect(page.locator('#region-count')).toHaveText('74');await expect(page.locator('#translated-count')).toHaveText('65');globalThis.videoJob=(await page.locator('#original-image').getAttribute('src')).match(/jobs\/([^/]+)\//)[1];await until(C[2].start+.1);await move(page.locator('#elapsed'));''',
 r'''await move(page.locator('#region-count'));await move(page.locator('#translated-count'));await move(page.getByRole('img',{name:'原始机械图纸',exact:true}));await move(page.getByRole('img',{name:'标注中文译文的机械图纸',exact:true}));await until(C[1].start+.2);for(let k=0;k<4;k++)await click(page.getByRole('button',{name:'放大图纸',exact:true}));await scroll(page.locator('.viewer-pane').nth(1).locator('.canvas-scroll'),0,260);await until(C[2].start+.15);await click(page.getByRole('button',{name:'待复核',exact:true}));await scroll(page.locator('#regions'),0,200);await until(C[2].end-2);await move(page.locator('#review-count'));''',
 r'''await click(page.getByRole('button',{name:'全部',exact:true}));const search=page.getByRole('searchbox',{name:'搜索文本',exact:true});await click(search);await search.pressSequentially('GROOVE DEPTH',{delay:95});await click(page.getByRole('button',{name:'GROOVE DEPTH 槽深 术语匹配 98% · p1-t5',exact:true}));await until(C[1].start+.2);await move(page.locator('#edit-coordinates'));await until(C[2].start+.15);const box=page.getByRole('textbox',{name:'中文译文',exact:true});await click(box);await box.press('End');await box.pressSequentially('（复核示例）',{delay:210});await until(C[3].start+.05);await click(page.getByRole('checkbox',{name:'记入个人术语库',exact:true}));await click(page.getByRole('button',{name:'保存并标为已复核',exact:true}));await expect(page.locator('#edit-warning')).toHaveText('已保存并标为已复核');await expect(box).toHaveValue('槽深（复核示例）');await move(page.getByRole('img',{name:'标注中文译文的机械图纸',exact:true}));''',
 r'''await keyboardClick(page.getByRole('button',{name:'关闭编辑',exact:true}));await click(page.getByRole('button',{name:'不遮挡英文',exact:true}));await click(page.getByRole('button',{name:'适合窗口',exact:true}));for(let k=0;k<2;k++)await click(page.getByRole('button',{name:'放大图纸',exact:true}));await move(page.getByRole('img',{name:'标注中文译文的机械图纸',exact:true}));await until(C[1].start+.1);await click(page.getByRole('button',{name:'遮挡英文',exact:true}));await expect(page.locator('#translated-image')).toHaveAttribute('src',/mode=cover/);await until(C[2].start+.1);await scroll(page.locator('.viewer-pane').nth(1).locator('.canvas-scroll'),0,180);await until(C[2].end-2);await move(page.getByRole('img',{name:'原始机械图纸',exact:true}));''',
 r'''await click(page.getByRole('button',{name:'不遮挡英文',exact:true}));const ready=page.waitForResponse(r=>r.url().includes('/export?')&&r.request().method()==='POST');await click(page.getByRole('button',{name:'导出图纸与坐标 ↗',exact:true}));const response=await ready;const payload=await response.json();assert(payload.report.omitted_annotations===0);globalThis.videoExport=payload;globalThis.videoJob=payload.url.split('/')[3];await expect(page.locator('#status-text')).toContainText('导出完成');const saved=await page.fetch(payload.url,{as:'file',savePath:artifactPath('drawing-video-result-'+Date.now()+'.zip')});assert(saved.ok);downloads.push(saved);await until(C[1].start+1);await move(page.locator('#status-text'));await until(C[2].start);await page.goto('http://127.0.0.1:8790/'+globalThis.videoJob+'/exports/beside/',{waitUntil:'domcontentloaded'});await install();await expect(page.getByRole('link',{name:payload.files[0],exact:true})).toBeVisible();await move(page.getByRole('link',{name:payload.files[0],exact:true}));await until(C[2].start+2);await page.goto('http://127.0.0.1:8791/pdf-preview/'+globalThis.videoJob+'.png',{waitUntil:'load'});await install();await expect(page.locator('body > img').first()).toBeVisible();await until(C[2].start+4);await click(page.locator('body > img').first());await pause(250);await scroll(page.locator('body > img').first(),0,-1600);''',
 r'''await page.goto('http://127.0.0.1:8787/',{waitUntil:'domcontentloaded'});await expect(page.locator('#translated-count')).toHaveText('65');await install();await page.getByRole('searchbox',{name:'搜索文本',exact:true}).pressSequentially('复核示例',{delay:140});await move(page.locator('#regions'));await until(C[1].start);await page.goto('http://127.0.0.1:8791/evidence',{waitUntil:'domcontentloaded'});await install();await move(page.getByText('23 passed（实际 pytest 日志）',{exact:true}));await until(C[2].start);await move(page.getByText('正式验收待补',{exact:true}));await until(C[3].start);await page.goto('http://127.0.0.1:8787/',{waitUntil:'domcontentloaded'});await expect(page.locator('#translated-count')).toHaveText('65');await install();await move(page.getByRole('button',{name:'导出图纸与坐标 ↗',exact:true}));'''
]

def resource(rid):
 offset=0;parts=[]
 while True:
  p=subprocess.run([CLI,'resource','--task',TASK,'--resource',rid,'--offset',str(offset),'--max-bytes','32768'],capture_output=True,text=True,check=True)
  value=json.loads(p.stdout);parts.append(value['data'])
  if value['eof']:break
  offset=value['nextOffset']
 return json.loads(''.join(parts))

for i in ([int(x) for x in sys.argv[1:]] or range(len(scenes))):
 s=scenes[i];folder=WORK/f'frames-{i:02}';folder.mkdir(exist_ok=True)
 pre="await page.setViewportSize({width:1600,height:800});\n"
 if i==5:pre+="await page.goto('http://127.0.0.1:8787/',{waitUntil:'domcontentloaded'});await expect(page.locator('#translated-count')).toHaveText('65');await page.getByRole('button',{name:'遮挡英文',exact:true}).click();await page.getByRole('searchbox',{name:'搜索文本',exact:true}).fill('GROOVE DEPTH');await page.getByRole('button',{name:'放大图纸',exact:true}).click();await page.getByRole('button',{name:'放大图纸',exact:true}).click();\n"
 program=pre+f"const C={json.dumps(s['captions'],ensure_ascii=False)};const duration={s['seconds']};\n"+HELPERS+'\ntry{'+ACTIONS[i]+r'''
await until(duration);
}finally{done=true;await capture;}
const dir=frames[0][1].slice(0,frames[0][1].lastIndexOf('/'));
return {dir,frames:frames.map(([t,p])=>[t,p.split('/').at(-1)]),seconds:(Date.now()-start)/1000,downloads,job:globalThis.videoJob,export:globalThis.videoExport,url:page.url()};
'''
 (WORK/f'record-{i:02}.js').write_text(program)
 p=subprocess.run([CLI,'nodejs','--task',TASK,'--request-id',f'drawing-scene-{i:02}-{int(time.time())}','--timeout-ms','120000'],input=program,capture_output=True,text=True)
 (WORK/f'receipt-{i:02}.json').write_text(p.stdout);(WORK/f'receipt-{i:02}.stderr').write_text(p.stderr)
 result=json.loads(p.stdout)
 if result['status']!='succeeded':print(p.stdout[-5000:],flush=True);raise RuntimeError(f'录制失败，先检查持久状态再重试：{i}')
 raw=result['result'];value=raw.get('value') or resource(raw['resourceId'])
 for j,(t,name) in enumerate(value['frames']):shutil.copy(Path(value['dir'])/name,folder/f'{j:05}.png')
 value['frames']=[[t,f'{j:05}.png'] for j,(t,_) in enumerate(value['frames'])]
 for download in value['downloads']:
  if download.get('path'):shutil.copy(download['path'],WORK/Path(download['path']).name)
 (folder/'timing.json').write_text(json.dumps(value,ensure_ascii=False,indent=2))
 print('CAPTURED',i,s['title'],len(value['frames']),round(value['seconds'],2),value['url'],flush=True)
