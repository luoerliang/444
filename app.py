import os, re, sqlite3, threading, time
from datetime import datetime, timedelta, timezone
from collections import Counter

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)
DB = os.getenv('DB_PATH', 'macau3.db')
TZ8 = timezone(timedelta(hours=8))
SOURCE_READER_URL = os.getenv('SOURCE_READER_URL', 'https://r.jina.ai/http://macaujc.com/open_video3/')
DIRECT_URLS = [
    'https://macaujc.com/open_video3/',
    'http://macaujc.com/open_video3/',
    'https://maoaujc.com/open_video3/',
    'http://maoaujc.com/open_video3/',
]
HEADERS = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1'}

HTML = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="60"><title>澳门六合彩3分分析</title><style>
body{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;background:#f5f6f8;margin:0;color:#222}.wrap{max-width:760px;margin:auto;padding:14px}.card{background:#fff;border-radius:14px;padding:16px;margin:10px 0;box-shadow:0 2px 10px #00000010}h1{font-size:22px;margin:4px 0 8px}.muted{color:#777;font-size:13px}.nums{display:flex;gap:7px;flex-wrap:wrap;margin:12px 0}.ball{width:38px;height:38px;border-radius:50%;background:#eee;display:flex;align-items:center;justify-content:center;font-weight:700}.special{background:#222;color:#fff}.grid{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}.item{padding:10px;border:1px solid #eee;border-radius:10px;text-align:center}.tag{font-size:12px;color:#777}.big{font-size:19px;font-weight:700}.row{display:flex;justify-content:space-between;gap:8px}.table{width:100%;border-collapse:collapse;font-size:13px}.table td{padding:8px 3px;border-bottom:1px solid #eee}.btn{display:inline-block;padding:9px 12px;border-radius:9px;background:#111;color:#fff;text-decoration:none}.err{color:#b00020}
</style></head><body><div class="wrap"><div class="card"><h1>澳门六合彩3分分析</h1><div class="muted">数据源：澳门六合彩3分公开开奖页面 · 北京时间 UTC+8</div></div>
<div class="card"><div class="row"><b>最新开奖</b><span class="muted">{{ latest_time }}</span></div><p><b>第{{ latest_issue or '—' }}期</b></p><div class="nums">{% for n in latest_main %}<span class="ball">{{n}}</span>{% endfor %}{% if latest_special %}<span class="ball special">{{latest_special}}</span>{% endif %}</div><div class="muted">前6个为正码，黑色为特码</div></div>
<div class="card"><b>统计候选（仅统计，不保证结果）</b><p class="muted">根据当天已收集记录的号码频次，并对近期记录加权。</p><div class="grid">{% for n,c in candidates %}<div class="item"><div class="big">{{n}}</div><div class="tag">{{c}}分</div></div>{% endfor %}</div></div>
<div class="card"><div class="row"><b>同步状态</b><span class="muted">{{ now }}</span></div><p class="{{'err' if error else ''}}">{{ status }}</p><a class="btn" href="/sync">立即同步</a></div>
<div class="card"><b>最近记录</b><table class="table"><tbody>{% for r in rows %}<tr><td>第{{r.issue}}期<br><span class="muted">{{r.time}}</span></td><td>{{' '.join(r.main)}} <b>+ {{r.special}}</b></td></tr>{% endfor %}</tbody></table></div>
</div></body></html>'''


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = db()
    c.execute('CREATE TABLE IF NOT EXISTS draws(issue TEXT PRIMARY KEY, open_time TEXT, nums TEXT, special TEXT)')
    c.commit(); c.close()


def infer_time_from_issue(issue):
    try:
        day = datetime.strptime(issue[:8], '%Y%m%d')
        seq = int(issue[8:])
        return (day + timedelta(minutes=max(0, (seq - 1) * 3))).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return None


def parse_source(html):
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text('\n', strip=True).replace('\xa0', ' ')
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    joined = '\n'.join(lines)
    issues = list(re.finditer(r'20\d{9}', joined))
    out = []
    combo = re.compile(r'(\d{1,2})\D{0,18}(\d{1,2})\D{0,18}(\d{1,2})\D{0,18}(\d{1,2})\D{0,18}(\d{1,2})\D{0,18}(\d{1,2})\D{0,25}\+\D{0,8}(\d{1,2})')
    time_re = re.compile(r'(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})[日\sT]+(\d{1,2}):(\d{2})(?::(\d{2}))?')
    for idx, im in enumerate(issues):
        issue = im.group(0); start = im.end(); end = issues[idx+1].start() if idx+1 < len(issues) else min(len(joined), start+2500)
        window = joined[start:end]
        cm = combo.search(window)
        if not cm: continue
        nums = [f'{int(cm.group(i)):02d}' for i in range(1,7)]
        special = f'{int(cm.group(7)):02d}'
        tm = time_re.search(window)
        if tm:
            open_time = f'{tm.group(1)}-{int(tm.group(2)):02d}-{int(tm.group(3)):02d} {tm.group(4)}:{tm.group(5)}:{tm.group(6) or "00"}'
        else:
            open_time = infer_time_from_issue(issue)
        if open_time: out.append((issue, open_time, nums, special))
    if not out:
        for i, line in enumerate(lines):
            m = re.search(r'(20\d{9})', line)
            if not m: continue
            cm = combo.search(' '.join(lines[i:i+12]))
            if cm:
                out.append((m.group(1), infer_time_from_issue(m.group(1)), [f'{int(cm.group(j)):02d}' for j in range(1,7)], f'{int(cm.group(7)):02d}'))
    seen=set(); unique=[]
    for row in out:
        if row[0] not in seen and row[1]: seen.add(row[0]); unique.append(row)
    return unique


def fetch_page():
    errors=[]
    try:
        r=requests.get(SOURCE_READER_URL, headers=HEADERS, timeout=15); r.raise_for_status()
        draws=parse_source(r.text)
        if draws: return draws, '3分开奖页（读取中转）'
        errors.append('中转页面已打开，但未解析到开奖数据')
    except Exception as e: errors.append('中转：'+str(e))
    for url in DIRECT_URLS:
        try:
            r=requests.get(url, headers=HEADERS, timeout=8); r.raise_for_status()
            draws=parse_source(r.text)
            if draws: return draws, '3分开奖页（直连）'
            errors.append('直连页面无法解析')
        except Exception as e: errors.append('直连：'+str(e))
    raise RuntimeError('；'.join(errors))


def save_draws(draws):
    today=datetime.now(TZ8).date(); c=db(); added=0
    for issue, open_time, nums, special in draws:
        try: d=datetime.strptime(open_time,'%Y-%m-%d %H:%M:%S').date()
        except Exception: continue
        if d != today or len(nums)!=6 or not special: continue
        c.execute('INSERT OR REPLACE INTO draws(issue,open_time,nums,special) VALUES(?,?,?,?)',(issue,open_time,','.join(nums),special)); added+=1
    c.commit(); c.close(); return added


def sync():
    draws, source=fetch_page(); return len(draws), save_draws(draws), source


def rows(limit=80):
    c=db(); rs=c.execute('SELECT * FROM draws ORDER BY open_time DESC, issue DESC LIMIT ?', (limit,)).fetchall(); c.close()
    return [{'issue':r['issue'],'time':r['open_time'],'main':r['nums'].split(','),'special':r['special']} for r in rs]


def candidates():
    rs=rows(80); score=Counter()
    for idx,r in enumerate(rs):
        weight=max(1,80-idx)
        for n in r['main']+[r['special']]: score[n]+=weight
    return sorted(score.items(), key=lambda x:(-x[1],x[0]))[:10]

init_db(); state={'status':'正在首次同步…','error':False}

def bg():
    while True:
        try:
            n,a,source=sync(); state.update(status=f'自动同步正常：{source}，读取 {n} 条，写入/更新 {a} 条', error=False)
        except Exception as e: state.update(status='同步失败：'+str(e), error=True)
        time.sleep(60)

threading.Thread(target=bg, daemon=True).start()

@app.route('/')
def home():
    rs=rows(30); latest=rs[0] if rs else None; now=datetime.now(TZ8).strftime('%Y-%m-%d %H:%M:%S')
    return render_template_string(HTML, latest_issue=latest['issue'] if latest else None, latest_time=latest['time'] if latest else '—', latest_main=latest['main'] if latest else [], latest_special=latest['special'] if latest else None, candidates=candidates(), rows=rs, now=now, status=state['status'], error=state['error'])

@app.route('/sync')
def manual_sync():
    try:
        n,a,source=sync(); state.update(status=f'同步完成：{source}，读取 {n} 条，写入/更新 {a} 条', error=False)
    except Exception as e: state.update(status='同步失败：'+str(e), error=True)
    return home()

@app.route('/api/draws')
def api_draws(): return jsonify(rows(100))

if __name__=='__main__': app.run(host='0.0.0.0', port=int(os.getenv('PORT','10000')))
