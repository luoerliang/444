import os,re,sqlite3,threading,time
from datetime import datetime,timedelta,timezone
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
import requests
from bs4 import BeautifulSoup
from flask import Flask,render_template_string,jsonify

app=Flask(__name__)
DB=os.getenv('DB_PATH','macau3.db')
TZ8=timezone(timedelta(hours=8))
TOKEN=os.getenv('TELEGRAM_BOT_TOKEN','').strip()
TG_API=f'https://api.telegram.org/bot{TOKEN}' if TOKEN else ''
TG={'ok':False,'issue':'','time':'','error':'未开始'}
SOURCES=['https://macaujc.com/open_video3/','http://macaujc.com/open_video3/','https://r.jina.ai/http://macaujc.com/open_video3/']
HEAD={'User-Agent':'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1','Cache-Control':'no-cache','Pragma':'no-cache'}
HTML='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="20"><title>澳门六合彩3分分析</title><style>body{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;background:#f5f6f8;margin:0;color:#222}.wrap{max-width:760px;margin:auto;padding:14px}.card{background:#fff;border-radius:14px;padding:16px;margin:10px 0;box-shadow:0 2px 10px #0001}h1{font-size:22px;margin:4px 0 8px}.muted{color:#777;font-size:13px}.nums{display:flex;gap:7px;flex-wrap:wrap;margin:12px 0}.ball{width:38px;height:38px;border-radius:50%;background:#eee;display:flex;align-items:center;justify-content:center;font-weight:700}.special{background:#222;color:#fff}.grid{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}.item{padding:10px;border:1px solid #eee;border-radius:10px;text-align:center}.big{font-size:19px;font-weight:700}.tag{font-size:12px;color:#777}.row{display:flex;justify-content:space-between;gap:8px}.copyrow{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.copybtn{border:0;padding:9px 12px;border-radius:9px;background:#111;color:#fff}.copynum{font-weight:700}.ok{color:#087f23}.err{color:#b00020}.btn{display:inline-block;padding:9px 12px;border-radius:9px;background:#111;color:#fff;text-decoration:none}.table{width:100%;border-collapse:collapse;font-size:13px}.table td{padding:8px 3px;border-bottom:1px solid #eee}</style></head><body><div class="wrap"><div class="card"><h1>澳门六合彩3分分析</h1><div class="muted">Telegram实时开奖 + 公开源补充 · 北京时间 UTC+8</div></div><div class="card"><div class="row"><b>最新开奖</b><span class="muted">{{lt}}</span></div><p><b>第{{li or '—'}}期</b></p><div class="nums">{% for n in lm %}<span class="ball">{{n}}</span>{% endfor %}{% if ls %}<span class="ball special">{{ls}}</span>{% endif %}</div><div class="muted">前6个为正码，黑色为特码</div></div><div class="card"><b>实时统计候选（仅统计，不保证结果）</b><p class="muted">按已收集的全部记录累计统计，最多22个号码。</p><div class="copyrow"><span class="copynum" id="ct">{{ct}}</span><button class="copybtn" onclick="navigator.clipboard.writeText(document.getElementById('ct').innerText).then(()=>alert('已复制'))">一键复制</button></div><div class="grid">{% for n,c in cs %}<div class="item"><div class="big">{{n}}</div><div class="tag">{{c}}分</div></div>{% endfor %}</div></div><div class="card"><b>Telegram实时接收状态</b><p class="{{'ok' if tgok else 'err'}}">{{tgs}}</p>{% if tgi %}<div class="muted">最后收到：第{{tgi}}期　{{tgt}}</div>{% endif %}</div><div class="card"><div class="row"><b>同步状态</b><span class="muted">{{now}}</span></div><p class="{{'err' if err else ''}}">{{status}}</p><a class="btn" href="/sync">立即同步</a></div><div class="card"><b>最近记录</b><table class="table"><tbody>{% for r in rs %}<tr><td>第{{r.issue}}期<br><span class="muted">{{r.time}}</span></td><td>{{' '.join(r.main)}} <b>+ {{r.special}}</b></td></tr>{% endfor %}</tbody></table></div></div></body></html>'''

def db():
 c=sqlite3.connect(DB,timeout=30);c.row_factory=sqlite3.Row;return c

def init():
 c=db();c.execute('CREATE TABLE IF NOT EXISTS draws(issue TEXT PRIMARY KEY,open_time TEXT,nums TEXT,special TEXT)');c.commit();c.close()

def infer(issue):
 try:
  d=datetime.strptime(issue[:8],'%Y%m%d');s=int(issue[8:]);return (d+timedelta(minutes=max(0,(s-1)*3))).strftime('%Y-%m-%d %H:%M:%S')
 except:return None

def parse_tg(text):
 p=re.compile(r'(20\d{9})\s*(?:期开奖结果)\s*:?\s*((?:\d{1,2}\s+){6}\d{1,2})')
 out=[]
 for m in p.finditer(text or ''):
  nums=[f'{int(x):02d}' for x in m.group(2).split()]
  if len(nums)==7 and all(1<=int(x)<=49 for x in nums):out.append((m.group(1),infer(m.group(1)),nums[:6],nums[6]))
 return out

def parse_web(html):
 soup=BeautifulSoup(html,'html.parser');text=soup.get_text('\n',strip=True).replace('\xa0',' ');joined='\n'.join(x.strip() for x in text.splitlines() if x.strip());issues=list(re.finditer(r'20\d{9}',joined));out=[]
 combo=re.compile(r'(\d{1,2})\D{0,18}(\d{1,2})\D{0,18}(\d{1,2})\D{0,18}(\d{1,2})\D{0,18}(\d{1,2})\D{0,18}(\d{1,2})\D{0,25}\+\D{0,8}(\d{1,2})')
 tr=re.compile(r'(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})[日\sT]+(\d{1,2}):(\d{2})(?::(\d{2}))?')
 for i,m in enumerate(issues):
  issue=m.group(0);w=joined[m.end():(issues[i+1].start() if i+1<len(issues) else min(len(joined),m.end()+2500))];cm=combo.search(w)
  if not cm:continue
  nums=[f'{int(cm.group(j)):02d}' for j in range(1,7)];sp=f'{int(cm.group(7)):02d}';tm=tr.search(w);ot=(f'{tm.group(1)}-{int(tm.group(2)):02d}-{int(tm.group(3)):02d} {tm.group(4)}:{tm.group(5)}:{tm.group(6) or "00"}' if tm else infer(issue));
  if ot:out.append((issue,ot,nums,sp))
 seen=set();u=[]
 for x in out:
  if x[0] not in seen:seen.add(x[0]);u.append(x)
 return u

def save(ds):
 c=db();n=0
 for issue,ot,nums,sp in ds:
  if len(nums)==6 and sp:
   c.execute('INSERT OR REPLACE INTO draws VALUES(?,?,?,?)',(issue,ot,','.join(nums),sp));n+=1
 c.commit();c.close();return n

def rows(limit=None):
 c=db();q='SELECT * FROM draws ORDER BY open_time DESC,issue DESC';rs=c.execute(q if limit is None else q+' LIMIT ?',() if limit is None else (limit,)).fetchall();c.close();return [{'issue':r['issue'],'time':r['open_time'],'main':r['nums'].split(','),'special':r['special']} for r in rs]

def cand():
 rs=rows(None);sc=Counter()
 for i,r in enumerate(rs):
  w=max(1,120-i)
  for n in r['main']+[r['special']]:sc[n]+=w
 return sorted(sc.items(),key=lambda x:(-x[1],x[0]))[:22]

def tg_loop():
 global TG
 if not TOKEN:TG['error']='TELEGRAM_BOT_TOKEN 未设置';return
 off=None
 while True:
  try:
   res=requests.post(TG_API+'/getUpdates',json={'offset':off,'timeout':20,'allowed_updates':['message']},timeout=25).json()
   if not res.get('ok'):raise RuntimeError(str(res))
   TG['ok']=True;TG['error']=''
   for u in res.get('result',[]):
    off=u['update_id']+1;msg=u.get('message') or {};ds=parse_tg(msg.get('text',''))
    if ds:
     save(ds);issue=max(ds,key=lambda x:x[0])[0];TG['issue']=issue;TG['time']=datetime.now(TZ8).strftime('%Y-%m-%d %H:%M:%S');print('TELEGRAM_DRAW',issue,flush=True)
  except Exception as e:
   TG['ok']=False;TG['error']=str(e)[:200];print('TELEGRAM_ERROR',TG['error'],flush=True);time.sleep(5)

def public_sync():
 with ThreadPoolExecutor(max_workers=3) as ex:
  fs=[ex.submit(lambda u: (lambda r:(parse_web(r.text),u))(requests.get(u,headers=HEAD,timeout=12)),u) for u in SOURCES]
  for f in as_completed(fs):
   try:
    ds,u=f.result()
    if ds:return save(ds),f'公开源 {u}'
   except:pass
 return 0,'公开源暂未读取到新数据'

init();state={'s':'正在首次同步…','e':False}
def bg():
 while True:
  try:n,s=public_sync();state.update(s=f'{s}，更新 {n} 条',e=False)
  except Exception as e:state.update(s='公开源同步失败：'+str(e),e=True)
  time.sleep(30)
threading.Thread(target=bg,daemon=True).start();threading.Thread(target=tg_loop,daemon=True).start()

@app.route('/')
def home():
 rs=rows(100);last=rs[0] if rs else None;cs=cand();tgs='🟢 Telegram实时接收正常' if TG['ok'] else ('🔴 Telegram接收异常：'+TG['error'] if TG['error'] else '🟡 Telegram正在等待实时消息…')
 return render_template_string(HTML,li=last['issue'] if last else None,lt=last['time'] if last else '—',lm=last['main'] if last else [],ls=last['special'] if last else None,cs=cs,ct=' '.join(x[0] for x in cs),tgok=TG['ok'],tgs=tgs,tgi=TG['issue'],tgt=TG['time'],now=datetime.now(TZ8).strftime('%Y-%m-%d %H:%M:%S'),status=state['s'],err=state['e'],rs=rs)

@app.route('/sync')
def sync():
 try:n,s=public_sync();state.update(s=f'{s}，更新 {n} 条',e=False)
 except Exception as e:state.update(s='同步失败：'+str(e),e=True)
 return home()
@app.route('/api/draws')
def api():return jsonify(rows(100))
if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.getenv('PORT','10000')))
