import os,re,sqlite3,threading,time,json,urllib.request
from datetime import datetime,timezone,timedelta
from flask import Flask,jsonify,render_template_string
app=Flask(__name__)
DB_PATH=os.getenv('DB_PATH','draws.db'); BOT_TOKEN=os.getenv('TELEGRAM_BOT_TOKEN','').strip(); BJ=timezone(timedelta(hours=8))
Z={1:'马',13:'马',25:'马',37:'马',49:'马',2:'蛇',14:'蛇',26:'蛇',38:'蛇',3:'龙',15:'龙',27:'龙',39:'龙',4:'兔',16:'兔',28:'兔',40:'兔',5:'虎',17:'虎',29:'虎',41:'虎',6:'牛',18:'牛',30:'牛',42:'牛',7:'鼠',19:'鼠',31:'鼠',43:'鼠',8:'猪',20:'猪',32:'猪',44:'猪',9:'狗',21:'狗',33:'狗',45:'狗',10:'鸡',22:'鸡',34:'鸡',46:'鸡',11:'猴',23:'猴',35:'猴',47:'猴',12:'羊',24:'羊',36:'羊',48:'羊'}
RED={1,2,7,8,12,13,18,19,23,24,29,30,34,35,40,45,46}; BLUE={3,4,9,10,14,15,20,25,26,31,36,37,41,42,47,48}; GREEN={5,6,11,16,17,21,22,27,28,32,33,38,39,43,44,49}
def wave(n): return '红波' if n in RED else '蓝波' if n in BLUE else '绿波'
def key(s):
 m=re.search(r'\d{9,}',s or ''); return int(m.group()) if m else 0
def init():
 c=sqlite3.connect(DB_PATH); c.execute('CREATE TABLE IF NOT EXISTS draws(issue TEXT PRIMARY KEY,numbers TEXT,special INTEGER,received_at TEXT)'); c.commit(); c.close()
def save(issue,nums):
 if len(nums)!=7 or len(set(nums))<7 or not all(1<=n<=49 for n in nums): return
 c=sqlite3.connect(DB_PATH); c.execute('INSERT OR REPLACE INTO draws VALUES(?,?,?,?)',(issue,','.join(map(str,nums[:6])),nums[6],datetime.now(BJ).isoformat())); c.commit(); c.close()
def draws():
 c=sqlite3.connect(DB_PATH); rows=c.execute('SELECT issue,numbers,special,received_at FROM draws ORDER BY issue DESC').fetchall(); c.close(); return [{'issue':i,'numbers':[int(x) for x in ns.split(',')],'special':sp,'received_at':t} for i,ns,sp,t in rows]
def parse(t):
 m=re.search(r'(?:澳门六合彩3分彩\s*[:：]\s*)?(\d{9,})\s*期?开奖结果?\s*[:：]\s*([0-9０-９,，、\s]+)',t or '')
 if not m:return
 raw=m.group(2).translate(str.maketrans('０１２３４５６７８９','0123456789')); ns=[int(x) for x in re.findall(r'\d{1,2}',raw)]
 return (m.group(1),ns[:7]) if len(ns)>=7 else None
def tg():
 if not BOT_TOKEN:return
 off=0
 while True:
  try:
   u=f'https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?timeout=25&offset={off}'
   with urllib.request.urlopen(u,timeout=35) as r:d=json.loads(r.read())
   for x in d.get('result',[]):
    off=x['update_id']+1; msg=x.get('message') or x.get('channel_post') or {}; p=parse(msg.get('text',''))
    if p: save(*p)
  except Exception: time.sleep(5)
def cycle_start_for(ds):
 # 本统计周期从当天001期开始；跨日后自动切换到新日期001期。
 if ds:
  latest=sorted(ds,key=lambda d:key(d['issue']),reverse=True)[0]['issue']
  m=re.match(r'(\d{8})\d{3,}',latest)
  if m:return m.group(1)+'001'
 return datetime.now(BJ).strftime('%Y%m%d')+'001'

def active(ds):
 start=cycle_start_for(ds); k=key(start); return [d for d in ds if key(d['issue'])>=k],start

def score_candidates(hist, limit=22):
 # 仅使用目标期之前已经出现的数据，避免把当前期结果泄漏进预测。
 if not hist:return []
 hist=sorted(hist,key=lambda d:key(d['issue']))
 freq={n:0.0 for n in range(1,50)}
 # 多窗口+时间衰减：近期数据权重更高，同时保留全周期频率。
 windows=[(15,1.00),(30,0.70),(60,0.40)]
 for w,wt in windows:
  part=hist[-w:]
  if not part:continue
  for i,d in enumerate(part):
   recency=(i+1)/len(part)
   weight=wt*(0.55+0.45*recency)
   for n in d['numbers']+[d['special']]:freq[n]+=weight
 # 当前周期总频率轻量加入，避免样本太小时波动过大。
 for d in hist:
  for n in d['numbers']+[d['special']]:freq[n]+=0.08
 ranked=sorted(range(1,50),key=lambda n:(-freq[n],n))
 return ranked[:limit]

def ensure_prediction_table():
 c=sqlite3.connect(DB_PATH); c.execute('CREATE TABLE IF NOT EXISTS predictions(issue TEXT PRIMARY KEY,candidates TEXT,created_at TEXT,hit_count INTEGER,hit INTEGER)'); c.commit(); c.close()

def evaluate_cycle(ds,start):
 # 对已经开奖的每一期，用“该期之前”的历史生成22码，并记录命中/错误。
 act=sorted([d for d in ds if key(d['issue'])>=key(start)],key=lambda d:key(d['issue']))
 ensure_prediction_table()
 c=sqlite3.connect(DB_PATH)
 for idx,d in enumerate(act):
  if idx==0: continue
  hist=act[:idx]
  cand=score_candidates(hist,22)
  actual=set(d['numbers']+[d['special']])
  hits=len(actual & set(cand))
  c.execute('INSERT OR REPLACE INTO predictions(issue,candidates,created_at,hit_count,hit) VALUES(?,?,?,?,?)',(d['issue'],','.join(map(str,cand)),datetime.now(BJ).isoformat(),hits,1 if hits>0 else 0))
 c.commit()
 rows=c.execute('SELECT COUNT(*),COALESCE(SUM(hit),0),COALESCE(SUM(hit_count),0) FROM predictions WHERE issue>=?',(start,)).fetchone(); c.close()
 return {'cycle_draw_count':len(act),'evaluated_count':int(rows[0]),'hit_periods':int(rows[1]),'miss_periods':int(rows[0]-rows[1]),'hit_rate':round((rows[1]/rows[0]*100),1) if rows[0] else 0.0,'total_hits':int(rows[2])}

def pack(n):return {'number':f'{n:02d}','zodiac':Z[n],'wave':wave(n)}
@app.get('/')
def home(): return render_template_string(HTML)
@app.get('/api/data')
def data():
 ds=draws(); act,start=active(ds); latest=ds[0] if ds else None
 # 当前页面候选只使用最新一期之前的数据，避免把最新开奖结果反哺进候选。
 hist=sorted([d for d in act if not latest or key(d['issue'])<key(latest['issue'])],key=lambda d:key(d['issue']))
 cand=score_candidates(hist,22) if hist else []
 freq={n:0 for n in range(1,50)}
 for d in hist:
  for n in d['numbers']+[d['special']]:freq[n]+=1
 zf={z:0 for z in set(Z.values())}
 for n in cand:zf[Z[n]]+=freq[n]
 top=sorted(zf.items(),key=lambda x:(-x[1],x[0]))[:5]
 stats=evaluate_cycle(act,start)
 return jsonify({'latest':({'issue':latest['issue'],'time':latest['received_at'],'numbers':[pack(n) for n in sorted(latest['numbers'])],'special':pack(latest['special'])} if latest else None),'candidates':[pack(n) for n in sorted(cand)],'copy':','.join(f'{n:02d}' for n in sorted(cand)),'candidate_zodiacs':[{'zodiac':z,'count':c,'numbers':[f'{n:02d}' for n in range(1,50) if Z[n]==z]} for z,c in top],'active_count':len(act),'cycle_start':start,'stats':stats})
HTML='''<!doctype html><html lang="zh-CN"><meta name="viewport" content="width=device-width,initial-scale=1"><title>澳门六合彩·3分</title><style>body{margin:0;background:#f4f7fb;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;color:#15233d}.head{background:#123f82;color:#fff;padding:18px}.wrap{max-width:900px;margin:auto;padding:14px}.card{background:#fff;border-radius:18px;padding:18px;margin-bottom:14px;box-shadow:0 4px 18px #17345a12}.row{display:flex;justify-content:space-between;align-items:center;gap:10px}.title{font-size:22px;font-weight:800}.muted{color:#78879c}.status{background:#eaffef;color:#087d31;border-radius:20px;padding:8px 12px}.latest{display:flex;gap:12px;flex-wrap:wrap;margin-top:14px}.ball{width:54px;height:54px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:21px;font-weight:900;border:3px solid}.red{color:#d71919;border-color:#ef4141;background:#fff1f1}.blue{color:#125de2;border-color:#2174ee;background:#eef5ff}.green{color:#129344;border-color:#20a453;background:#effbf3}.meta{text-align:center;font-size:13px;font-weight:800;margin-top:4px}.copy{background:#1667e8;color:#fff;border:0;border-radius:12px;padding:12px 17px;font-size:16px;font-weight:800}.nums{color:#084fe0;font-size:24px;font-weight:900;line-height:1.55;margin:12px 0}.grid{display:grid;grid-template-columns:repeat(6,1fr);gap:9px}.tile{text-align:center;border:1px solid #dfe6f0;border-radius:13px;padding:9px 3px}.n{font-size:22px;font-weight:900}.zgrid{display:grid;grid-template-columns:repeat(5,1fr);gap:9px}.z{text-align:center;border:1px solid #ddd;border-radius:14px;padding:12px 4px}.zname{font-size:20px;font-weight:900}.znums{font-size:12px;color:#64748b;margin-top:5px}.note{background:#eff6ff;border-radius:12px;padding:10px;color:#637795;font-size:12px;margin-top:10px}@media(max-width:650px){.grid{grid-template-columns:repeat(4,1fr)}.zgrid{grid-template-columns:repeat(2,1fr)}} </style><body><div class="head"><div class="row"><div><b style="font-size:24px">澳门六合彩 · 3分</b><div>实时开奖 · 历史统计 · 智能分析</div></div><div class="status">🟢 Telegram 接收正常</div></div></div><div class="wrap"><div class="card"><div class="row"><div class="title">最新开奖</div><div id="time" class="muted"></div></div><div id="issue" class="muted"></div><div id="latest" class="latest"></div><div class="muted">前6个为正码，最后一个为特码</div></div><div class="card"><div class="row"><div><div class="title">实时统计候选（仅统计，不保证结果）</div><div class="muted">从本周期001期开始累计；每一期都回测上一期候选，显示统计期数、命中期数和错误期数。</div></div><button class="copy" onclick="cp()">一键复制</button></div><div id="nums" class="nums"></div><div id="grid" class="grid"></div><div id="stats" class="note"></div></div><div class="card"><div class="title">⭐ 统计候选生肖（5个）</div><div id="zgrid" class="zgrid"></div><div class="note">以上为历史开奖统计，仅供参考，不代表开奖结果。命中率为历史回测指标，不代表未来结果；统计从本周期001期开始累计。</div></div></div><script>let cpv='';function wc(w){return w[0]=='红'?'red':w[0]=='蓝'?'blue':'green'}function render(d){document.querySelector('#time').textContent=d.latest?new Date(d.latest.time).toLocaleString('zh-CN',{hour12:false}):'';document.querySelector('#issue').textContent=d.latest?'第'+d.latest.issue+'期':'等待Telegram开奖';let h='';if(d.latest){for(const x of d.latest.numbers)h+=`<div><div class="ball ${wc(x.wave)}">${x.number}</div><div class="meta ${wc(x.wave)}">${x.zodiac} · ${x.wave}</div></div>`;const x=d.latest.special;h+=`<div><div class="ball ${wc(x.wave)}">${x.number}</div><div class="meta ${wc(x.wave)}">${x.zodiac} · ${x.wave}<br>特码</div></div>`}document.querySelector('#latest').innerHTML=h;cpv=d.copy;document.querySelector('#nums').textContent=d.copy;document.querySelector('#stats').innerHTML=`本周期：${d.cycle_start}　已开奖：${d.stats.cycle_draw_count}期　已回测：${d.stats.evaluated_count}期　命中：${d.stats.hit_periods}期　错误：${d.stats.miss_periods}期　历史命中率：${d.stats.hit_rate}%　累计命中号码：${d.stats.total_hits}`;document.querySelector('#grid').innerHTML=d.candidates.map(x=>`<div class="tile"><div class="n ${wc(x.wave)}">${x.number}</div><div class="meta ${wc(x.wave)}">${x.zodiac} · ${x.wave}</div></div>`).join('');document.querySelector('#zgrid').innerHTML=d.candidate_zodiacs.map(x=>`<div class="z"><div class="zname">${x.zodiac}</div><b>(${x.count}次)</b><div class="znums">${x.numbers.join(', ')}</div></div>`).join('')}async function load(){try{render(await (await fetch('/api/data?x='+Date.now())).json())}catch(e){}}async function cp(){try{await navigator.clipboard.writeText(cpv);alert('已复制：'+cpv)}catch(e){prompt('复制下面号码：',cpv)}}load();setInterval(load,15000)</script></body></html>'''
init()
if BOT_TOKEN: threading.Thread(target=tg,daemon=True).start()
if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.getenv('PORT','10000')))
