import os, re, sqlite3, threading, time, json
from datetime import datetime, timedelta, timezone
from collections import Counter
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)
DB = os.getenv('DB_PATH', 'macau3.db')
TZ8 = timezone(timedelta(hours=8))
GITHUB_RAW = os.getenv('GITHUB_RAW_URL', 'https://raw.githubusercontent.com/luoerliang/macau3-predictor-final/main/data/draws.json')
DIRECT_URLS = [
    'https://macaujc.com/open_video3/',
    'http://macaujc.com/open_video3/',
]
HEADERS = {'User-Agent':'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1','Cache-Control':'no-cache','Pragma':'no-cache'}

HTML='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="30"><title>澳门六合彩3分分析</title><style>body{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;background:#f5f6f8;margin:0;color:#222}.wrap{max-width:760px;margin:auto;padding:14px}.card{background:#fff;border-radius:14px;padding:16px;margin:10px 0;box-shadow:0 2px 10px #00000010}h1{font-size:22px;margin:4px 0 8px}.muted{color:#777;font-size:13px}.nums{display:flex;gap:7px;flex-wrap:wrap;margin:12px 0}.ball{width:38px;height:38px;border-radius:50%;background:#eee;display:flex;align-items:center;justify-content:center;font-weight:700}.special{background:#222;color:#fff}.grid{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}.copyrow{display:flex;gap:8px;align-items:center;margin:10px 0}.copybtn{border:0;padding:9px 12px;border-radius:9px;background:#111;color:#fff;font-size:14px}.copynum{font-weight:700;letter-spacing:.3px}.item{padding:10px;border:1px solid #eee;border-radius:10px;text-align:center}.tag{font-size:12px;color:#777}.big{font-size:19px;font-weight:700}.row{display:flex;justify-content:space-between;gap:8px}.table{width:100%;border-collapse:collapse;font-size:13px}.table td{padding:8px 3px;border-bottom:1px solid #eee}.btn{display:inline-block;padding:9px 12px;border-radius:9px;background:#111;color:#fff;text-decoration:none}.err{color:#b00020}</style></head><body><div class="wrap"><div class="card"><h1>澳门六合彩3分分析</h1><div class="muted">数据源：澳门六合彩3分公开开奖页面 · 北京时间 UTC+8</div></div><div class="card"><div class="row"><b>最新开奖</b><span class="muted">{{latest_time}}</span></div><p><b>第{{latest_issue or '—'}}期</b></p><div class="nums">{% for n in latest_main %}<span class="ball">{{n}}</span>{% endfor %}{% if latest_special %}<span class="ball special">{{latest_special}}</span>{% endif %}</div><div class="muted">前6个为正码，黑色为特码</div></div><div class="card"><b>实时统计候选（仅统计，不保证结果）</b><p class="muted">根据已收集记录的号码频次，并对近期记录加权，最多显示22个号码。</p><div class="copyrow"><span class="copynum" id="candidateText">{{candidate_text}}</span><button class="copybtn" onclick="copyCandidates()">一键复制</button></div><div class="grid">{% for n,c in candidates %}<div class="item"><div class="big">{{n}}</div><div class="tag">{{c}}分</div></div>{% endfor %}</div></div><div class="card"><div class="row"><b>同步状态</b><span class="muted">{{now}}</span></div><p class="{{'err' if error else ''}}">{{status}}</p><a class="btn" href="/sync">立即同步</a></div><div class="card"><b>最近记录</b><table class="table"><tbody>{% for r in rows %}<tr><td>第{{r.issue}}期<br><span class="muted">{{r.time}}</span></td><td>{{' '.join(r.main)}} <b>+ {{r.special}}</b></td></tr>{% endfor %}</tbody></table></div></div><script>function copyCandidates(){const t=document.getElementById('candidateText').innerText;navigator.clipboard.writeText(t).then(()=>alert('已复制统计候选号码')).catch(()=>{const x=document.createElement('textarea');x.value=t;document.body.appendChild(x);x.select();document.execCommand('copy');x.remove();alert('已复制统计候选号码')})}</script></body></html>'''

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init_db():
    c=db(); c.execute('CREATE TABLE IF NOT EXISTS draws(issue TEXT PRIMARY KEY, open_time TEXT, nums TEXT, special TEXT)'); c.commit(); c.close()

def infer_time(issue):
    try:
        day=datetime.strptime(issue[:8],'%Y%m%d'); seq=int(issue[8:]); return (day+timedelta(minutes=max(0,(seq-1)*3))).strftime('%Y-%m-%d %H:%M:%S')
    except: return None

def parse_source(html):
    soup=BeautifulSoup(html,'html.parser'); text=soup.get_text('\n',strip=True).replace('\xa0',' '); lines=[x.strip() for x in text.splitlines() if x.strip()]; joined='\n'.join(lines)
    issues=list(re.finditer(r'20\d{9}',joined)); out=[]
    combo=re.compile(r'(\d{1,2})\D{0,18}(\d{1,2})\D{0,18}(\d{1,2})\D{0,18}(\d{1,2})\D{0,18}(\d{1,2})\D{0,18}(\d{1,2})\D{0,25}\+\D{0,8}(\d{1,2})')
    time_re=re.compile(r'(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})[日\sT]+(\d{1,2}):(\d{2})(?::(\d{2}))?')
    for i,im in enumerate(issues):
        issue=im.group(0); start=im.end(); end=issues[i+1].start() if i+1<len(issues) else min(len(joined),start+2500); w=joined[start:end]; cm=combo.search(w)
        if not cm: continue
        nums=[f'{int(cm.group(j)):02d}' for j in range(1,7)]; special=f'{int(cm.group(7)):02d}'; tm=time_re.search(w)
        ot=(f'{tm.group(1)}-{int(tm.group(2)):02d}-{int(tm.group(3)):02d} {tm.group(4)}:{tm.group(5)}:{tm.group(6) or "00"}' if tm else infer_time(issue))
        if ot: out.append((issue,ot,nums,special))
    seen=set(); unique=[]
    for row in out:
        if row[0] not in seen: seen.add(row[0]); unique.append(row)
    return unique

def save(draws):
    today=datetime.now(TZ8).date(); c=db(); added=0
    for issue,ot,nums,special in draws:
        try: d=datetime.strptime(ot,'%Y-%m-%d %H:%M:%S').date()
        except: continue
        if d!=today or len(nums)!=6 or not special: continue
        c.execute('INSERT OR REPLACE INTO draws VALUES(?,?,?,?)',(issue,ot,','.join(nums),special)); added+=1
    c.commit(); c.close(); return added

def fetch():
    # 第一优先：GitHub Actions 每5分钟从原站抓取并写入的最新快照。
    try:
        u=GITHUB_RAW + ('&' if '?' in GITHUB_RAW else '?') + '_cb=' + str(int(time.time()))
        r=requests.get(u,headers=HEADERS,timeout=12); r.raise_for_status(); data=r.json(); draws=[]
        for x in data.get('draws',[]):
            draws.append((str(x['issue']),x['open_time'],x['main'],str(x['special'])))
        if draws: return draws,'GitHub实时快照（绕过澳门站对Render的直连限制）'
    except Exception as e: github_err=str(e)
    # 第二优先：Render直接访问原站（如果网络策略允许）。
    for url in DIRECT_URLS:
        try:
            r=requests.get(url+'?_cb='+str(int(time.time())),headers=HEADERS,timeout=8); r.raise_for_status(); draws=parse_source(r.text)
            if draws: return draws,'澳门3分开奖页（Render直连）'
        except: pass
    raise RuntimeError('最新源读取失败；GitHub快照可能尚未更新，请稍后再试')

def sync():
    d,s=fetch(); return len(d),save(d),s

def rows(limit=80):
    c=db(); rs=c.execute('SELECT * FROM draws ORDER BY open_time DESC,issue DESC LIMIT ?',(limit,)).fetchall(); c.close(); return [{'issue':r['issue'],'time':r['open_time'],'main':r['nums'].split(','),'special':r['special']} for r in rs]

def candidates():
    rs=rows(80); score=Counter()
    for i,r in enumerate(rs):
        w=max(1,80-i)
        for n in r['main']+[r['special']]: score[n]+=w
    return sorted(score.items(),key=lambda x:(-x[1],x[0]))[:22]

init_db(); state={'status':'正在首次同步…','error':False}
def bg():
    while True:
        try:
            n,a,s=sync(); state.update(status=f'自动同步正常：{s}，读取 {n} 条，写入/更新 {a} 条',error=False)
        except Exception as e: state.update(status='同步失败：'+str(e),error=True)
        time.sleep(30)
threading.Thread(target=bg,daemon=True).start()

@app.route('/')
def home():
    rs=rows(30); latest=rs[0] if rs else None
    cand=candidates(); cand_text=' '.join(n for n,_ in cand); return render_template_string(HTML,latest_issue=latest['issue'] if latest else None,latest_time=latest['time'] if latest else '—',latest_main=latest['main'] if latest else [],latest_special=latest['special'] if latest else None,candidates=cand,candidate_text=cand_text,rows=rs,now=datetime.now(TZ8).strftime('%Y-%m-%d %H:%M:%S'),status=state['status'],error=state['error'])

@app.route('/sync')
def manual_sync():
    try:
        n,a,s=sync(); state.update(status=f'同步完成：{s}，读取 {n} 条，写入/更新 {a} 条',error=False)
    except Exception as e: state.update(status='同步失败：'+str(e),error=True)
    return home()

@app.route('/api/draws')
def api_draws(): return jsonify(rows(100))

if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.getenv('PORT','10000')))
