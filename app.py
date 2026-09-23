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

def parse_web_history(html):
    # 兼容官方页不同日期格式、表格/普通文本结构。
    out=[]
    rows=re.findall(r'<tr[^>]*>(.*?)</tr>',html,re.I|re.S)
    if not rows:
        rows=re.split(r'(?=<\d{11}\b)',html)
    for row in rows:
        txt=re.sub(r'<script[^>]*>.*?</script>|<style[^>]*>.*?</style>',' ',row,flags=re.I|re.S)
        txt=re.sub(r'<[^>]+>',' ',txt)
        txt=re.sub(r'&nbsp;|&#160;',' ',txt)
        txt=re.sub(r'\s+',' ',txt).strip()
        im=re.search(r'\b(20\d{9})\b',txt)
        if not im: continue
        issue=im.group(1)
        # 先找开奖时间；支持 2026-09-23 / 2026/9/23 等写法。
        tm=re.search(r'20\d{2}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2}:\d{2}',txt)
        rest=txt[tm.end():] if tm else txt[im.end():]
        # 去掉常见的期号/日期数字干扰，只在后续文本里找 01-49。
        ns=[int(x) for x in re.findall(r'(?<!\d)(0[1-9]|[1-4]\d|49)(?!\d)',rest)]
        if len(ns)>=7:
            ns=ns[:7]
            if len(set(ns))==7:
                out.append((issue,ns))
    # 去重，保留第一次出现
    seen=set(); clean=[]
    for x in out:
        if x[0] not in seen:
            seen.add(x[0]); clean.append(x)
    return clean

def web_backfill():
    while True:
        try:
            target=datetime.now(BJ).strftime('%Y%m%d'); reached=False
            for page in range(1,13):
                for url in [f'https://maoaujc.com/macaujc2//?id=3&page={page}',f'http://maoaujc.com/macaujc2//?id=3&page={page}',f'https://r.jina.ai/http://maoaujc.com/macaujc2//?id=3&page={page}']:
                    try:
                        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
                        with urllib.request.urlopen(req,timeout=20) as r: html=r.read().decode('utf-8','ignore')
                        got=parse_web_history(html)
                        for issue,ns in got:
                            if issue.startswith(target): save(issue,ns)
                            if issue==target+'001': reached=True
                        if got: break
                    except Exception: continue
                if reached: break
            for url in ['https://macaujc.com/open_video3/','https://r.jina.ai/http://macaujc.com/open_video3/']:
                try:
                    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
                    with urllib.request.urlopen(req,timeout=20) as r: html=r.read().decode('utf-8','ignore')
                    for issue,ns in parse_web_history(html):
                        if issue.startswith(target): save(issue,ns)
                    break
                except Exception: continue
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

def special_score_map(hist):
    if not hist:return {n:0.0 for n in range(1,50)}
    hist=sorted(hist,key=lambda d:key(d['issue']))
    score={n:0.0 for n in range(1,50)}
    for w,wt in [(12,1.25),(24,0.95),(48,0.65),(96,0.35)]:
        part=hist[-w:]
        if not part: continue
        L=len(part)
        for i,d in enumerate(part):
            weight=wt*(0.35+0.65*((i+1)/L))
            score[d['special']]+=weight
    for d in hist: score[d['special']]+=0.025
    seen={d['special'] for d in hist[-18:]}
    for n in range(1,50):
        if n not in seen: score[n]+=0.12
    if hist:
        score[hist[-1]['special']]*=0.82
        if len(hist)>=2 and hist[-2]['special']==hist[-1]['special']:
            score[hist[-1]['special']]*=0.72
    return score

def score_candidates(hist, limit=22):
    score=special_score_map(hist)
    return sorted(range(1,50),key=lambda n:(-score[n],n))[:limit]

def ensure_prediction_table():
 c=sqlite3.connect(DB_PATH); c.execute('CREATE TABLE IF NOT EXISTS predictions(issue TEXT PRIMARY KEY,candidates TEXT,created_at TEXT,hit_count INTEGER,hit INTEGER)'); c.commit(); c.close()

def evaluate_cycle(ds,start):
    act=sorted([d for d in ds if key(d['issue'])>=key(start)],key=lambda d:key(d['issue']))
    ensure_prediction_table(); c=sqlite3.connect(DB_PATH)
    for idx,d in enumerate(act):
        if idx==0: continue
        cand=score_candidates(act[:idx],22)
        hit=1 if d['special'] in cand else 0
        c.execute('INSERT OR REPLACE INTO predictions(issue,candidates,created_at,hit_count,hit) VALUES(?,?,?,?,?)',(d['issue'],','.join(map(str,cand)),datetime.now(BJ).isoformat(),hit,hit))
    c.commit(); rows=c.execute('SELECT COUNT(*),COALESCE(SUM(hit),0),COALESCE(SUM(hit_count),0) FROM predictions WHERE issue>=?',(start,)).fetchone(); c.close()
    return {'cycle_draw_count':len(act),'evaluated_count':int(rows[0]),'hit_periods':int(rows[1]),'miss_periods':int(rows[0]-rows[1]),'hit_rate':round(rows[1]/rows[0]*100,1) if rows[0] else 0.0,'total_hits':int(rows[2])}

def pack(n):return {'number':f'{n:02d}','zodiac':Z[n],'wave':wave(n)}
@app.get('/')
def home(): return render_template_string(HTML)
@app.get('/api/data')
def data():
    ds=draws(); act,start=active(ds); latest=ds[0] if ds else None
    hist=sorted(act,key=lambda d:key(d['issue']))
    cand=score_candidates(hist,22) if hist else []
    scores=special_score_map(hist)
    zrank=[]
    for z in set(Z.values()):
        zn=sorted([n for n in cand if Z[n]==z],key=lambda n:(-scores[n],n))[:2]
        if zn: zrank.append((z,sum(scores[n] for n in zn),zn))
    zrank.sort(key=lambda x:(-x[1],x[0])); top=zrank[:5]
    stats=evaluate_cycle(act,start)
    history=[{'issue':d['issue'],'numbers':[pack(n) for n in d['numbers']],'special':pack(d['special']),'time':d['received_at']} for d in sorted(act,key=lambda d:key(d['issue']),reverse=True)]
    return jsonify({'latest':({'issue':latest['issue'],'time':latest['received_at'],'numbers':[pack(n) for n in sorted(latest['numbers'])],'special':pack(latest['special'])} if latest else None),'candidates':[pack(n) for n in sorted(cand)],'copy':','.join(f'{n:02d}' for n in sorted(cand)),'candidate_zodiacs':[{'zodiac':z,'numbers':[f'{n:02d}' for n in best]} for z,_,best in top],'active_count':len(act),'cycle_start':start,'stats':stats,'history':history})

# Gunicorn 启动时必须主动启动 Telegram 与历史补抓线程。
# 之前漏掉这一步会导致网页能打开，但开奖和历史都不会更新。
init()
ensure_prediction_table()
threading.Thread(target=tg,daemon=True).start()
threading.Thread(target=web_backfill,daemon=True).start()

HTML='''<!doctype html><html lang="zh-CN"><meta name="viewport" content="width=device-width,initial-scale=1"><title>澳门六合彩·3分</title><style>body{margin:0;background:#f4f7fb;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;color:#15233d}.head{background:#123f82;color:#fff;padding:14px}.wrap{max-width:900px;margin:auto;padding:10px}.card{background:#fff;border-radius:16px;padding:14px;margin-bottom:10px;box-shadow:0 4px 18px #17345a12}.row{display:flex;justify-content:space-between;align-items:center;gap:8px}.title{font-size:18px;font-weight:800}.muted{color:#78879c;font-size:12px}.status{background:#eaffef;color:#087d31;border-radius:18px;padding:6px 9px;font-size:12px}.latest{display:flex;gap:7px;flex-wrap:wrap;margin-top:8px}.ball{width:40px;height:40px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:900;border:2px solid}.red{color:#d71919;border-color:#ef4141;background:#fff1f1}.blue{color:#125de2;border-color:#2174ee;background:#eef5ff}.green{color:#129344;border-color:#20a453;background:#effbf3}.meta{text-align:center;font-size:10px;font-weight:700;margin-top:2px}.copy{background:#1667e8;color:#fff;border:0;border-radius:10px;padding:8px 11px;font-size:13px;font-weight:800}.nums{color:#084fe0;font-size:18px;font-weight:900;line-height:1.45;margin:8px 0;word-break:break-all}.grid{display:grid;grid-template-columns:repeat(6,1fr);gap:7px}.tile{text-align:center;border:1px solid #dfe6f0;border-radius:11px;padding:7px 2px}.n{font-size:18px;font-weight:900}.zgrid{display:grid;grid-template-columns:repeat(5,1fr);gap:7px}.z{text-align:center;border:1px solid #ddd;border-radius:11px;padding:8px 3px}.zname{font-size:16px;font-weight:900}.znums{font-size:12px;color:#64748b;margin-top:3px;font-weight:800}.note{background:#eff6ff;border-radius:10px;padding:8px;color:#637795;font-size:11px;margin-top:8px}.hist{display:flex;flex-direction:column;gap:6px}.hrow{display:grid;grid-template-columns:72px 1fr 45px;align-items:center;border-bottom:1px solid #edf1f6;padding:5px 0;font-size:12px}.hnums{font-weight:800;letter-spacing:.3px}.hspec{font-weight:900;text-align:right}@media(max-width:650px){.grid{grid-template-columns:repeat(5,1fr)}.zgrid{grid-template-columns:repeat(3,1fr)}} </style><body><div class="head"><div class="row"><div><b>澳门六合彩 · 3分</b><div style="font-size:12px">实时开奖 · 下一期开奖结果预测</div></div><div class="status">🟢 实时接收</div></div></div><div class="wrap"><div class="card"><div class="row"><div class="title">最新开奖</div><div id="time" class="muted"></div></div><div id="issue" class="muted"></div><div id="latest" class="latest"></div></div><div class="card"><div class="row"><div><div class="title">⭐ 下一期预测特码</div><div class="muted">用最新一期之前的全部历史数据，最多22码</div></div><button class="copy" onclick="cp()">复制22码</button></div><div id="nums" class="nums"></div><div id="grid" class="grid"></div><div id="stats" class="note"></div></div><div class="card"><div class="title">⭐ 下一期预测生肖</div><div class="muted">独立评分；每个生肖只显示2个预测号码</div><div id="zgrid" class="zgrid" style="margin-top:8px"></div></div><div class="card"><div class="title">📜 本周期全部历史开奖</div><div class="muted" id="hcount"></div><div id="hist" class="hist" style="margin-top:6px"></div></div></div><script>let cpv='';function wc(w){return w[0]=='红'?'red':w[0]=='蓝'?'blue':'green'}function render(d){document.querySelector('#time').textContent=d.latest?new Date(d.latest.time).toLocaleString('zh-CN',{hour12:false}):'';document.querySelector('#issue').textContent=d.latest?'第'+d.latest.issue+'期':'等待开奖';let h='';if(d.latest){for(const x of d.latest.numbers)h+=`<div><div class="ball ${wc(x.wave)}">${x.number}</div><div class="meta ${wc(x.wave)}">${x.zodiac}·${x.wave}</div></div>`;const x=d.latest.special;h+=`<div><div class="ball ${wc(x.wave)}">${x.number}</div><div class="meta ${wc(x.wave)}">${x.zodiac}·${x.wave}<br>特码</div></div>`}document.querySelector('#latest').innerHTML=h;cpv=d.copy;document.querySelector('#nums').textContent=d.copy;document.querySelector('#stats').innerHTML=`本周期：${d.cycle_start}　已开奖：${d.stats.cycle_draw_count}期　已回测：${d.stats.evaluated_count}期　命中：${d.stats.hit_periods}期　错误：${d.stats.miss_periods}期　历史命中率：${d.stats.hit_rate}%　累计命中：${d.stats.total_hits}次`;document.querySelector('#grid').innerHTML=d.candidates.map(x=>`<div class="tile"><div class="n ${wc(x.wave)}">${x.number}</div><div class="meta ${wc(x.wave)}">${x.zodiac}·${x.wave}</div></div>`).join('');document.querySelector('#zgrid').innerHTML=d.candidate_zodiacs.map(x=>`<div class="z"><div class="zname">${x.zodiac}</div><div class="znums">${x.numbers.join('、')}</div></div>`).join('');document.querySelector('#hcount').textContent='共'+d.history.length+'期（从'+d.cycle_start+'开始）';document.querySelector('#hist').innerHTML=d.history.map(r=>{let ns=r.numbers.map(x=>`<span class="smallball ${wc(x.wave)}">${x.number}</span>`).join(' ');return `<div class="hrow"><div>${r.issue.slice(-3)}期</div><div class="hnums">${ns}</div><div class="hspec ${wc(r.special.wave)}">+${r.special.number}</div></div>`}).join('')}async function load(){try{const r=await fetch('/api/data?x='+Date.now());if(!r.ok)throw new Error('API '+r.status);render(await r.json())}catch(e){document.querySelector('#issue').textContent='数据读取中…';}}async function cp(){try{await navigator.clipboard.writeText(cpv);alert('已复制：'+cpv)}catch(e){prompt('复制下面号码：',cpv)}}load();setInterval(load,15000)</script></body></html>'''
