"""Read-only viewer for real exported PDF pixels and recorded verification evidence."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler,HTTPServer
import json,html,re
import pymupdf
ROOT=Path(__file__).resolve().parents[3];JOBS=ROOT/'.work/drawing-translator-video/app-data/jobs'
EVIDENCE=ROOT/'图译交付材料/测试证据'
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  try:
   match=re.fullmatch(r'/pdf-preview/([a-f0-9]{16})\.png',self.path)
   if match:
    source=next((JOBS/match[1]/'exports/beside').glob('*.pdf'))
    with pymupdf.open(source) as doc:
     data=doc[0].get_pixmap(matrix=pymupdf.Matrix(2,2)).tobytes('png')
    kind='image/png'
   elif self.path=='/evidence':
    log=(EVIDENCE/'pytest-final.log').read_text()
    gold=json.loads((EVIDENCE/'参考答案验证.json').read_text())
    batch=json.loads((EVIDENCE/'批量处理报告.json').read_text())
    assert '23 passed' in log
    facts=[('功能测试','23 passed（实际 pytest 日志）'),('选定参考术语',f"{gold['correct']} / {gold['expected']} 个点，范围为三张参考原图"),('批量结果',f"{len(batch)} 份 PDF / {sum(x['pages'] for x in batch)} 页；两种标注模式"),('准确率解释','选定术语点通过率不代表全文专业准确率'),('正式验收待补','Windows 10/11 实机；≥50 份完整金标；指定 i7/16GB 完整文件性能；72 小时稳定性')]
    rows=''.join('<tr><th>'+html.escape(a)+'</th><td>'+html.escape(b)+'</td></tr>' for a,b in facts)
    body='<!doctype html><meta charset="utf-8"><title>图译 · 实测记录汇总</title><style>body{margin:64px 90px;font:22px/1.7 -apple-system,sans-serif;color:#23343c;background:#f7fafb}h1{font-size:34px}p{color:#71818b;font-size:18px}table{border-collapse:collapse;width:100%;background:white}th,td{padding:24px;border-bottom:1px solid #dfe6e7;text-align:left}th{width:210px;color:#14776e}small{font-size:16px;color:#71818b}</style><h1>图译 · 实测记录汇总</h1><p>直接读取交付中的 pytest、参考答案验证和批量处理报告；这是证据阅读页，不是产品功能界面。</p><table>'+rows+'</table><p><small>原始记录：测试证据/pytest-final.log、参考答案验证.json、批量处理报告.json。运行时图纸与识别文本只在本机处理。</small></p>'
    data=body.encode();kind='text/html; charset=utf-8'
   else:self.send_error(404);return
   self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
  except Exception as error:self.send_error(500,str(error))
HTTPServer(('127.0.0.1',8791),Handler).serve_forever()
