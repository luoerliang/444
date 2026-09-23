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
def save(issue,nums,received_at=None):
 if len(nums)!=7 or len(set(nums))<7 or not all(1<=n<=49 for n in nums): return
 c=sqlite3.connect(DB_PATH); c.execute('INSERT OR REPLACE INTO draws VALUES(?,?,?,?)',(issue,','.join(map(str,nums[:6])),nums[6],received_at or datetime.now(BJ).isoformat())); c.commit(); c.close()
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

def parse_web_history(html):
    # 支持普通HTML表格和Jina文本代理；提取期号、时间、6正码+特码。
    out=[]
    rows=re.findall(r'<tr[^>]*>(.*?)</tr>',html,re.I|re.S)
    for row in rows:
        txt=re.sub(r'<[^>]+>',' ',row)
        txt=re.sub(r'&nbsp;|&#160;',' ',txt)
        txt=re.sub(r'\s+',' ',txt).strip()
        m=re.search(r'(\d{11}).*?(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})(.*)',txt)
        if not m: continue
        issue,tm,rest=m.groups()
        ns=[int(x) for x in re.findall(r'(?<!\d)(0[1-9]|[1-4]\d|49)(?!\d)',rest)]
        if len(ns)>=7 and len(set(ns[:7]))==7: out.append((issue,ns[:7],tm))
    # Jina/纯文本页面常把每期拆成连续文本；按“期号 + 时间”切块再取后7个号码。
    if not out:
        txt=re.sub(r'<[^>]+>',' ',html)
        txt=re.sub(r'&nbsp;|&#160;',' ',txt)
        txt=re.sub(r'\s+',' ',txt)
        pat=re.compile(r'(20\d{9}).{0,500}?(202\d-\d\d-\d\d\s+\d\d:\d\d:\d\d)',re.S)
        ms=list(pat.finditer(txt))
        for i,m in enumerate(ms):
            issue,tm=m.group(1),m.group(2)
            block=txt[m.end(): ms[i+1].start() if i+1<len(ms) else m.end()+700]
            nums=[int(x) for x in re.findall(r'(?<!\d)(0[1-9]|[1-4]\d|49)(?!\d)',block)]
            if len(nums)>=7:
                ns=nums[:7]
                if len(set(ns))==7: out.append((issue,ns,tm))
    return out

def web_backfill_once():
    # Telegram负责实时；历史补齐使用多个公开入口/代理，优先抓当天001期以来的全部3分彩。
    today=datetime.now(BJ).strftime('%Y%m%d')
    urls=[]
    for page in range(1,9):
        urls += [
          f'https://r.jina.ai/https://maoaujc.com/macaujc2//?id=3&page={page}',
          f'https://r.jina.ai/http://maoaujc.com/macaujc2//?id=3&page={page}',
          f'https://r.jina.ai/https://www.maoaujc.com/macaujc2//?id=3&page={page}'
        ]
    urls += [
      'https://r.jina.ai/https://macaujc.com/open_video3/',
      'https://r.jina.ai/http://macaujc.com/open_video3/'
    ]
    saved=0
    for url in urls:
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'text/html,text/plain,*/*'})
            with urllib.request.urlopen(req,timeout=18) as r: html=r.read().decode('utf-8','ignore')
            for issue,ns,tm in parse_web_history(html):
                if issue.startswith(today):
                    before=len(draws())
                    save(issue,ns,tm)
                    after=len(draws())
                    if after>before: saved += 1
        except Exception:
            continue
    return saved

def web_backfill():
    while True:
        try: web_backfill_once()
        except Exception: pass
        time.sleep(30)

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
    # 只统计特码，用于预测下一期的特码。
    if not hist:return []
    hist=sorted(hist,key=lambda d:key(d['issue']))
    freq={n:0.0 for n in range(1,50)}
    for w,wt in [(15,1.00),(30,0.70),(60,0.40)]:
        part=hist[-w:]
        for i,d in enumerate(part):
            weight=wt*(0.55+0.45*(i+1)/len(part))
            freq[d['special']]+=weight
    for d in hist: freq[d['special']]+=0.08
    return sorted(range(1,50),key=lambda n:(-freq[n],n))[:limit]

def ensure_prediction_table():
 c=sqlite3.connect(DB_PATH); c.execute('CREATE TABLE IF NOT EXISTS predictions(issue TEXT PRIMARY KEY,candidates TEXT,created_at TEXT,hit_count INTEGER,hit INTEGER)'); c.commit(); c.close()

def evaluate_cycle(ds,start):
    # 第N期预测只使用001~N-1期特码；验证第N期实际特码。
    act=sorted([d for d in ds if key(d['issue'])>=key(start)],key=lambda d:key(d['issue']))
    ensure_prediction_table(); c=sqlite3.connect(DB_PATH)
    for idx,d in enumerate(act):
        if idx==0: continue
        cand=score_candidates(act[:idx],22); hit=1 if d['special'] in cand else 0
        c.execute('INSERT OR REPLACE INTO predictions(issue,candidates,created_at,hit_count,hit) VALUES(?,?,?,?,?)',(d['issue'],','.join(map(str,cand)),datetime.now(BJ).isoformat(),hit,hit))
    c.commit(); rows=c.execute('SELECT COUNT(*),COALESCE(SUM(hit),0) FROM predictions WHERE issue>=?',(start,)).fetchone(); c.close()
    return {'cycle_draw_count':len(act),'evaluated_count':int(rows[0]),'hit_periods':int(rows[1]),'miss_periods':int(rows[0]-rows[1]),'hit_rate':round(rows[1]/rows[0]*100,1) if rows[0] else 0.0,'total_hits':int(rows[1])}

def pack(n):return {'number':f'{n:02d}','zodiac':Z[n],'wave':wave(n)}
@app.get('/')
def home(): return render_template_string(HTML)
@app.get('/api/data')
def data():
    ds=draws(); act,start=active(ds); latest=ds[0] if ds else None
    hist=sorted([d for d in act if not latest or key(d['issue'])<key(latest['issue'])],key=lambda d:key(d['issue']))
    cand=score_candidates(hist,22)
    freq={n:0 for n in range(1,50)}
    for d in hist: freq[d['special']]+=1
    zf={z:0 for z in set(Z.values())}
    for n in cand: zf[Z[n]]+=freq[n]
    top=sorted(zf.items(),key=lambda x:(-x[1],x[0]))[:5]
    znums={z:[] for z in zf}
    for n in cand: znums[Z[n]].append(n)
    stats=evaluate_cycle(act,start); history=sorted(act,key=lambda d:key(d['issue']),reverse=True)
    return jsonify({'latest':({'issue':latest['issue'],'time':latest['received_at'],'numbers':[pack(n) for n in sorted(latest['numbers'])],'special':pack(latest['special'])} if latest else None),'predict_issue':(f"{int(latest['issue'])+1:011d}" if latest else ''),'candidates':[pack(n) for n in sorted(cand)],'copy':','.join(f'{n:02d}' for n in sorted(cand)),'candidate_zodiacs':[{'zodiac':z,'count':c,'numbers':[f'{n:02d}' for n in sorted(znums[z])]} for z,c in top],'active_count':len(act),'cycle_start':start,'stats':stats,'history':[{'issue':d['issue'],'numbers':[pack(n) for n in sorted(d['numbers'])],'special':pack(d['special']),'time':d['received_at']} for d in history]})

HTML='''<!doctype html><html lang="zh-CN"><meta name="viewport" content="width=device-width,initial-scale=1"><title>澳门六合彩·3分</title><style>body{margin:0;background:#f4f7fb;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;color:#15233d}.head{background:#123f82;color:#fff;padding:18px}.wrap{max-width:900px;margin:auto;padding:14px}.card{background:#fff;border-radius:14px;padding:12px;margin-bottom:10px;box-shadow:0 4px 18px #17345a12}.row{display:flex;justify-content:space-between;align-items:center;gap:10px}.title{font-size:18px;font-weight:800}.muted{color:#78879c}.status{background:#eaffef;color:#087d31;border-radius:20px;padding:8px 12px}.latest{display:flex;gap:5px;flex-wrap:wrap;margin-top:6px}.ball{width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:900;border:2px solid}.red{color:#d71919;border-color:#ef4141;background:#fff1f1}.blue{color:#125de2;border-color:#2174ee;background:#eef5ff}.green{color:#129344;border-color:#20a453;background:#effbf3}.meta{text-align:center;font-size:7px;font-weight:800;margin-top:3px;line-height:1.15}.copy{background:#1667e8;color:#fff;border:0;border-radius:10px;padding:9px 12px;font-size:14px;font-weight:800}.nums{color:#084fe0;font-size:14px;font-weight:900;line-height:1.5;margin:8px 0;white-space:normal;overflow-wrap:anywhere}.grid{display:grid;grid-template-columns:repeat(6,1fr);gap:6px}.tile{text-align:center;border:1px solid #dfe6f0;border-radius:10px;padding:6px 2px}.n{font-size:16px;font-weight:900}.zgrid{display:grid;grid-template-columns:repeat(5,1fr);gap:6px}.z{text-align:center;border:1px solid #ddd;border-radius:9px;padding:6px 2px}.zname{font-size:14px;font-weight:900}.znums{font-size:12px;color:#64748b;margin-top:5px}.note{background:#eff6ff;border-radius:12px;padding:10px;color:#637795;font-size:12px;margin-top:10px}@media(max-width:650px){.grid{grid-template-columns:repeat(4,1fr)}.zgrid{grid-template-columns:repeat(2,1fr)}.latest{gap:4px}.card{padding:10px}.title{font-size:17px}.head{padding:12px}.head b{font-size:20px!important}.status{font-size:12px;padding:6px 8px}} </style><body><div class="head"><div class="row"><div><b style="font-size:24px">澳门六合彩 · 3分</b><div>实时开奖 · 历史统计 · 智能分析</div></div><div class="status">🟢 Telegram 接收正常</div></div></div><div class="wrap"><div class="card"><div class="row"><div class="title">最新开奖</div><div id="time" class="muted"></div></div><div id="issue" class="muted"></div><div id="latest" class="latest"></div><div class="muted">前6个为正码，最后一个为特码</div></div><div class="card"><div class="row"><div><div class="title">下一期预测特码（历史统计，不保证结果）</div><div class="muted">只用上一期以前的历史特码预测下一期；每一期开奖后自动验证命中或错误。</div></div><button class="copy" onclick="cp()">一键复制</button></div><div id="nums" class="nums"></div><div id="grid" class="grid"></div><div id="stats" class="note"></div></div><div class="card"><div class="title">⭐ 统计候选生肖（5个）</div><div id="zgrid" class="zgrid"></div><div class="card"><div class="title">📜 本周期全部历史开奖</div><div class="muted">从001期开始，最新在上面。</div><div style="overflow:auto;margin-top:8px"><table style="width:100%;border-collapse:collapse;font-size:12px"><thead><tr><th>期号</th><th>正码</th><th>特码</th><th>北京时间</th></tr></thead><tbody id="history"></tbody></table></div></div><div class="note">以上为历史开奖统计，仅供参考，不代表开奖结果。命中率为历史回测指标，不代表未来结果；统计从本周期001期开始累计。</div></div></div><script>let cpv='';function wc(w){return w[0]=='红'?'red':w[0]=='蓝'?'blue':'green'}function render(d){document.querySelector('#time').textContent=d.latest?new Date(d.latest.time).toLocaleString('zh-CN',{hour12:false}):'';document.querySelector('#issue').textContent=d.latest?'第'+d.latest.issue+'期':'等待Telegram开奖';let h='';if(d.latest){for(const x of d.latest.numbers)h+=`<div><div class="ball ${wc(x.wave)}">${x.number}</div><div class="meta ${wc(x.wave)}">${x.zodiac} · ${x.wave}</div></div>`;const x=d.latest.special;h+=`<div><div class="ball ${wc(x.wave)}">${x.number}</div><div class="meta ${wc(x.wave)}">${x.zodiac} · ${x.wave}<br>特码</div></div>`}document.querySelector('#latest').innerHTML=h;cpv=d.copy;document.querySelector('#nums').textContent=d.copy;document.querySelector('#stats').innerHTML=`预测第${d.predict_issue||''}期｜本周期：${d.cycle_start}　已开奖：${d.stats.cycle_draw_count}期　已回测：${d.stats.evaluated_count}期　命中：${d.stats.hit_periods}期　错误：${d.stats.miss_periods}期　历史命中率：${d.stats.hit_rate}%　累计命中：${d.stats.total_hits}`;document.querySelector('#history').innerHTML=d.history.map(x=>`<tr><td>${x.issue}</td><td>${x.numbers.map(y=>y.number).join(' ')}</td><td>${x.special.number}<br>${x.special.zodiac}·${x.special.wave}</td><td>${new Date(x.time).toLocaleTimeString('zh-CN',{hour12:false})}</td></tr>`).join('');document.querySelector('#grid').innerHTML=d.candidates.map(x=>`<div class="tile"><div class="n ${wc(x.wave)}">${x.number}</div><div class="meta ${wc(x.wave)}">${x.zodiac} · ${x.wave}</div></div>`).join('');document.querySelector('#zgrid').innerHTML=d.candidate_zodiacs.map(x=>`<div class="z"><div class="zname">${x.zodiac}</div><b>(${x.count}次)</b><div class="znums">${x.numbers.join(', ')}</div></div>`).join('')}async function load(){try{render(await (await fetch('/api/data?x='+Date.now())).json())}catch(e){}}async function cp(){try{await navigator.clipboard.writeText(cpv);alert('已复制：'+cpv)}catch(e){prompt('复制下面号码：',cpv)}}load();setInterval(load,15000)</script></body></html>'''
init()
threading.Thread(target=web_backfill,daemon=True).start()
if BOT_TOKEN: threading.Thread(target=tg,daemon=True).start()
threading.Thread(target=web_backfill,daemon=True).start()
if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.getenv('PORT','10000')))
