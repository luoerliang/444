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
  c=sqlite3.connect(DB_PATH); c.execute("CREATE TABLE IF NOT EXISTS draws(issue TEXT PRIMARY KEY,numbers TEXT,special INTEGER,received_at TEXT,source TEXT DEFAULT 'legacy')"); c.commit()
  try: c.execute("ALTER TABLE draws ADD COLUMN source TEXT DEFAULT 'legacy'")
  except Exception: pass
  c.execute("UPDATE draws SET source='legacy' WHERE source IS NULL")
  c.commit(); c.close()

def save(issue,nums,source='telegram',force=False):
 if len(nums)!=7 or len(set(nums))<7 or not all(1<=n<=49 for n in nums): return
 c=sqlite3.connect(DB_PATH)
 try: c.execute("ALTER TABLE draws ADD COLUMN source TEXT DEFAULT 'legacy'")
 except Exception: pass
 pri={'legacy':0,'seed':1,'telegram':3}
 row=c.execute('SELECT source FROM draws WHERE issue=?',(issue,)).fetchone()
 old=row[0] if row and row[0] else 'legacy'
 if row and pri.get(source,0) < pri.get(old,0): c.close(); return
 if row and old=='telegram' and source!='telegram': c.close(); return
 c.execute('INSERT OR REPLACE INTO draws(issue,numbers,special,received_at,source) VALUES(?,?,?,?,?)',(issue,','.join(map(str,nums[:6])),nums[6],datetime.now(BJ).isoformat(),source))
 c.commit(); c.close()

def seed_csv():
 p=os.path.join(os.path.dirname(__file__),'seed_history.csv')
 if not os.path.exists(p): return 0
 try:
  import csv
  rows=[]
  with open(p,'r',encoding='utf-8-sig',newline='') as f:
   for r in csv.DictReader(f):
    issue=str(r.get('期号','')).strip(); vals=[]
    for k in ['正码1','正码2','正码3','正码4','正码5','正码6','特码']:
     try: vals.append(int(r[k]))
     except Exception: vals=[]; break
    if re.fullmatch(r'20\d{9}',issue) and len(vals)==7:
     rows.append((issue,','.join(map(str,vals[:6])),vals[6],r.get('开奖时间') or datetime.now(BJ).isoformat(),'seed'))
  c=sqlite3.connect(DB_PATH); c.executemany("INSERT OR IGNORE INTO draws(issue,numbers,special,received_at,source) VALUES(?,?,?,?,?)",rows); c.commit(); c.close(); return len(rows)
 except Exception: return 0

def seed_robot_extra():
 rows=[
 ('20260923151',[8,47,17,40,48,18,45]),('20260923152',[21,35,15,5,40,10,44]),('20260923153',[48,31,10,24,15,47,38]),('20260923154',[2,46,12,15,25,19,9]),('20260923155',[12,31,36,33,25,38,15]),('20260923156',[8,47,25,40,10,24,46]),('20260923157',[6,27,5,45,12,15,23]),('20260923158',[34,32,8,5,24,35,19]),('20260923159',[43,37,49,48,2,11,30]),('20260923160',[18,16,22,25,1,46,5]),('20260923161',[47,15,20,34,26,25,30]),('20260923162',[10,36,28,42,41,4,12]),('20260923163',[1,44,20,47,41,42,31]),('20260923164',[46,32,44,38,43,8,2]),('20260923165',[2,48,42,33,4,34,28]),('20260923166',[23,20,26,18,27,45,24]),('20260923167',[1,42,24,21,13,26,30]),('20260923168',[39,7,27,46,8,21,14]),('20260923169',[39,35,37,15,38,12,21]),('20260923170',[22,24,3,37,39,18,35]),('20260923172',[40,49,17,1,42,41,13]),('20260923179',[25,45,23,41,13,24,8]),('20260923180',[3,38,12,25,16,14,28]),('20260923181',[28,41,5,45,9,30,39]),('20260923182',[7,20,43,34,33,19,24]),('20260923183',[13,7,9,27,4,14,32]),('20260923184',[9,12,2,32,5,27,48]),('20260923185',[48,12,40,1,49,16,37]),('20260923186',[46,20,17,10,5,13,49]),('20260923187',[9,28,34,7,15,41,46]),('20260923188',[15,6,45,43,12,38,27]),('20260923189',[13,48,37,24,44,36,8]),('20260923190',[47,11,22,26,28,14,16]),('20260923191',[47,13,17,34,21,49,12]),('20260923192',[10,14,27,22,23,42,44]),('20260923193',[32,47,31,6,10,2,11]),('20260923194',[28,49,12,37,31,24,20]),('20260923195',[26,27,37,34,17,46,48]),('20260923196',[20,22,41,28,5,44,33]),('20260923198',[8,20,9,48,43,49,16]),('20260923199',[17,34,24,47,5,33,28]),('20260923200',[5,48,17,31,42,16,37]),('20260923201',[5,32,9,14,34,26,10]),('20260923202',[10,13,6,32,21,35,1]),('20260923203',[28,41,47,9,17,45,6]),('20260923204',[8,20,23,1,33,37,17]),('20260923205',[27,34,21,16,45,49,13]),('20260923206',[39,49,42,36,45,43,6]),('20260923207',[3,28,9,27,29,11,7]),('20260923208',[13,47,40,16,10,38,37]),('20260923209',[49,39,2,38,25,22,35]),('20260923210',[7,4,42,44,8,11,18]),('20260923213',[20,8,46,37,43,9,7]),('20260923215',[47,16,28,33,49,8,18]),('20260923217',[2,32,20,9,13,45,44]),('20260923220',[47,18,12,10,26,48,19]),('20260923226',[35,49,40,31,17,16,27]),('20260923234',[39,3,17,40,16,24,49])]
 for issue,nums in rows: save(issue,nums,source='telegram')
 return len(rows)

def draws():
 c=sqlite3.connect(DB_PATH); rows=c.execute("SELECT issue,numbers,special,received_at,COALESCE(source,'legacy') FROM draws ORDER BY issue DESC").fetchall(); c.close(); return [{'issue':i,'numbers':[int(x) for x in ns.split(',')],'special':int(sp),'received_at':t,'source':src} for i,ns,sp,t,src in rows]
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
   u=f'https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?timeout=25&offset={off}&allowed_updates=%5B%22message%22,%22channel_post%22,%22edited_message%22,%22edited_channel_post%22%5D'
   with urllib.request.urlopen(u,timeout=35) as r:d=json.loads(r.read())
   for x in d.get('result',[]):
    off=x['update_id']+1
    msg=x.get('message') or x.get('channel_post') or x.get('edited_message') or x.get('edited_channel_post') or {}
    text=msg.get('text') or msg.get('caption') or ''
    p=parse(text)
    if p: save(*p,source='telegram')
  except Exception: time.sleep(5)

def parse_embedded_history(raw):
    """从页面原始HTML/内联JS中的 JSON/对象数据提取3分彩历史。"""
    if not raw:
        return []
    out=[]
    # 常见JSON键名：expect/issue + openCode/open_code/opencode
    patterns = [
        r'["\']expect["\']\s*:\s*["\'](20\d{9})["\'][\s\S]{0,500}?["\']openCode["\']\s*:\s*["\']([^"\']+)["\']',
        r'["\']issue["\']\s*:\s*["\'](20\d{9})["\'][\s\S]{0,500}?["\'](?:openCode|open_code|opencode)["\']\s*:\s*["\']([^"\']+)["\']',
        r'expect\s*:\s*["\'](20\d{9})["\'][\s\S]{0,500}?(?:openCode|open_code|opencode)\s*:\s*["\']([^"\']+)["\']',
    ]
    for pat in patterns:
        for m in re.finditer(pat, raw, re.I):
            issue=m.group(1); code=m.group(2)
            nums=[]
            for q in re.findall(r'\d{1,2}',code):
                n=int(q)
                if 1<=n<=49 and n not in nums: nums.append(n)
            if len(nums)>=7 and len(set(nums[:7]))==7:
                out.append((issue,nums[:7]))
    # 有些页面把期号和7个号码作为连续文本写进JS
    for m in re.finditer(r'(20\d{9})[\s\S]{0,220}?(?<!\d)(0?[1-9]|[1-4]\d|49)(?:\D+)(0?[1-9]|[1-4]\d|49)(?:\D+)(0?[1-9]|[1-4]\d|49)(?:\D+)(0?[1-9]|[1-4]\d|49)(?:\D+)(0?[1-9]|[1-4]\d|49)(?:\D+)(0?[1-9]|[1-4]\d|49)(?:\D+)(0?[1-9]|[1-4]\d|49)', raw):
        issue=m.group(1); ns=[int(x) for x in m.groups()[1:]]
        if len(set(ns))==7: out.append((issue,ns))
    seen=set(); clean=[]
    for x in out:
        if x[0] not in seen:
            seen.add(x[0]); clean.append(x)
    return clean

def parse_web_history(html):
    """解析3分彩历史：明确按“6个正码 + 特码”结构读取，避免把页面其它数字当特码。"""
    out=[]
    rows=re.findall(r'<tr[^>]*>(.*?)</tr>', html or '', re.I|re.S)
    if not rows:
        rows=re.split(r'(?=20\d{9}\b)', html or '')
    for row in rows:
        txt=re.sub(r'<script[^>]*>.*?</script>|<style[^>]*>.*?</style>',' ',row,flags=re.I|re.S)
        txt=re.sub(r'<[^>]+>',' ',txt)
        txt=re.sub(r'&nbsp;|&#160;',' ',txt)
        txt=re.sub(r'\s+',' ',txt).strip()
        im=re.search(r'\b(20\d{9})\b',txt)
        if not im: continue
        issue=im.group(1)
        tail=txt[im.end():]
        # 日期、时间等都在期号后面，先删掉，避免时间数字进入号码。
        tail=re.sub(r'20\d{2}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?',' ',tail)
        # 3分彩历史文本通常明确用“+ / 澳 / 特码”分隔特码。
        # 优先取分隔符前的6个唯一号码，再取分隔符后的第一个号码。
        plus=re.search(r'\+\s*(?:澳|特(?:码)?|特码)?\s*',tail)
        nums=[]
        if plus:
            left,right=tail[:plus.start()],tail[plus.end():]
            leftvals=[int(v) for v in re.findall(r'(?<!\d)(0?[1-9]|[1-4]\d|49)(?!\d)',left)]
            for n in leftvals[-6:]:
                if n not in nums: nums.append(n)
            sp=None
            for v in re.findall(r'(?<!\d)(0?[1-9]|[1-4]\d|49)(?!\d)',right):
                n=int(v)
                if n not in nums:
                    sp=n; break
            if len(nums)==6 and sp is not None:
                out.append((issue,nums+[sp]))
                continue
        # 备用：按单元格读取，但同样只接受明确的“6正码+特码”。
        cells=re.findall(r'<(?:td|th)[^>]*>(.*?)</(?:td|th)>', row, re.I|re.S)
        vals=[]
        for cell in cells:
            ct=re.sub(r'<[^>]+>',' ',cell); ct=re.sub(r'&nbsp;|&#160;',' ',ct); ct=re.sub(r'\s+',' ',ct).strip()
            if re.search(r'20\d{2}[-/]\d{1,2}[-/]\d{1,2}',ct) or re.fullmatch(r'\d{1,2}:\d{2}(?::\d{2})?',ct): continue
            vals += [int(v) for v in re.findall(r'(?<!\d)(0?[1-9]|[1-4]\d|49)(?!\d)',ct)]
        if len(vals)>=7:
            # 去重并只接受7个号码，最后一个作为特码。
            uniq=[]
            for n in vals:
                if n not in uniq: uniq.append(n)
            if len(uniq)>=7 and len(set(uniq[:7]))==7: out.append((issue,uniq[:7]))
    seen=set(); clean=[]
    for x in out:
        if x[0] not in seen:
            seen.add(x[0]); clean.append(x)
    return clean

def fetch_history_page(page):
    """3分彩历史页多种分页参数兜底。"""
    urls=[
        f'https://macaujc.com/macaujc3/?id=3&page={page}',
        f'https://macaujc.com/macaujc3/?page={page}',
        f'https://macaujc.com/macaujc3/?id=3&p={page}',
        f'https://macaujc.com/macaujc3/?id=3&pageNum={page}',
        f'https://macaujc.com/macaujc3/?id=3&currentPage={page}',
        f'https://r.jina.ai/http://macaujc.com/macaujc3/?id=3&page={page}',
        f'https://r.jina.ai/https://macaujc.com/macaujc3/?id=3&page={page}',
    ]
    for url in urls:
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Safari/605.1','Accept':'text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8','Accept-Language':'zh-CN,zh;q=0.9'})
            with urllib.request.urlopen(req,timeout=18) as r: html=r.read().decode('utf-8','ignore')
            got=parse_embedded_history(html) or parse_web_history(html) or parse_text_history(html)
            if got: return got
        except Exception: continue
    return []

def parse_text_history(text):
    """解析纯文本历史，严格按“6正码 + 特码”取值。"""
    if not text: return []
    out=[]
    pat=re.compile(r'(20\d{9})\s*期?([\s\S]{0,320}?)(?=20\d{9}\s*期|$)')
    for m in pat.finditer(text):
        issue=m.group(1); block=m.group(2)
        block=re.sub(r'20\d{2}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?',' ',block)
        plus=re.search(r'\+\s*(?:澳|特(?:码)?|特码)?\s*',block)
        if not plus: continue
        left,right=block[:plus.start()],block[plus.end():]
        nums=[]
        leftvals=[int(x) for x in re.findall(r'(?<!\d)(0?[1-9]|[1-4]\d|49)(?!\d)',left)]
        for n in leftvals[-6:]:
            if n not in nums: nums.append(n)
        sp=None
        for x in re.findall(r'(?<!\d)(0?[1-9]|[1-4]\d|49)(?!\d)',right):
            n=int(x)
            if n not in nums: sp=n; break
        if len(nums)==6 and sp is not None: out.append((issue,nums+[sp]))
    seen=set(); clean=[]
    for x in out:
        if x[0] not in seen: seen.add(x[0]); clean.append(x)
    return clean


def parse_api_history(data):
    out=[]
    items=[]
    if isinstance(data,dict):
        items=data.get('data') or []
    elif isinstance(data,list):
        items=data
    for x in items:
        if not isinstance(x,dict):
            continue
        issue=str(x.get('expect') or x.get('issue') or '').strip()
        code=str(x.get('openCode') or x.get('open_code') or x.get('opencode') or '').strip()
        # 3分彩期号必须是 YYYYMMDD + 三位日内期号，例如 20260923001。
        if not re.fullmatch(r'20\d{9}',issue):
            continue
        if not issue[4:8].isdigit() or not (1 <= int(issue[4:6]) <= 12 and 1 <= int(issue[6:8]) <= 31):
            continue
        ns=[]
        for q in re.findall(r'\d{1,2}',code):
            n=int(q)
            if 1<=n<=49: ns.append(n)
        if len(ns)>=7 and len(set(ns[:7]))==7:
            out.append((issue,ns[:7]))
    return out


def fetch_api_history(year):
    """官方站公开的3分彩历史接口。3分彩期号格式必须为 YYYYMMDDNNN。"""
    urls=[
        f'https://history.macaumarksix.com/history/macaujc3/y/{year}',
        f'https://history.macaumarksix.com/history/macaujc3/year/{year}',
    ]
    for url in urls:
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json,text/plain,*/*'})
            with urllib.request.urlopen(req,timeout=12) as r:
                raw=r.read().decode('utf-8','ignore')
            data=json.loads(raw)
            got=parse_api_history(data)
            if got:
                return got
        except Exception:
            continue
    return []

def fetch_issue_api(issue):
    """逐期查询3分彩；同时尝试官方历史路径、当前接口查询参数和公共代理。"""
    urls=[
        f'https://history.macaumarksix.com/history/macaujc3/expect/{issue}',
        f'https://history.macaumarksix.com/history/macaujc3/{issue}',
        f'https://macaumarksix.com/api/macaujc3.com?expect={issue}',
        f'https://macaumarksix.com/api/macaujc3.com?number={issue}',
        f'https://macaumarksix.com/api/macaujc3.com?issue={issue}',
    ]
    for url in urls:
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json,text/plain,*/*'})
            with urllib.request.urlopen(req,timeout=7) as r:
                raw=r.read().decode('utf-8','ignore')
            try:
                data=json.loads(raw); got=parse_api_history(data)
            except Exception:
                got=parse_embedded_history(raw) or parse_text_history(raw)
            for item in got:
                if item[0]==issue: return item
        except Exception:
            continue
    return None


def fetch_current_api():
    """3分彩专用当前接口；只接受 YYYYMMDDNNN 期号。"""
    for url in ['https://macaumarksix.com/api/macaujc3.com','https://macaumarksix.com/api/macaujc3']:
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json,text/plain,*/*'})
            with urllib.request.urlopen(req,timeout=8) as r:
                data=json.loads(r.read().decode('utf-8','ignore'))
            got=parse_api_history(data)
            if got:
                return got[0]
        except Exception:
            continue
    return None

def web_backfill():
    """严格按本周期001→当前期补齐；只有完整连续历史才用于预测。"""
    while True:
        try:
            target=datetime.now(BJ).strftime('%Y%m%d')
            # 当前期优先相信机器人：机器人已收到的最新期号就是主进度。
            # 只有机器人尚无当天数据时，才退回3分彩专用API确定当前期。
            ds0=draws()
            bot_nums=[int(d['issue'][-3:]) for d in ds0 if d['issue'].startswith(target) and d['issue'][-3:].isdigit() and d.get('source')=='telegram']
            curitem=fetch_current_api()
            api_num=int(curitem[0][-3:]) if curitem and curitem[0].startswith(target) else 0
            current_num=max(bot_nums) if bot_nums else api_num
            if curitem and curitem[0].startswith(target): save(curitem[0],curitem[1],source='api',force=True)

            # 历史接口只作为辅助源；机器人已经收到的期号和号码绝不覆盖。
            got=fetch_api_history(datetime.now(BJ).year)
            for issue,ns in got:
                if issue.startswith(target) and issue[-3:].isdigit() and int(issue[-3:]) <= current_num:
                    save(issue,ns,source='api',force=True)
            for page in range(1,61):
                got=fetch_history_page(page)
                for issue,ns in got:
                    if issue.startswith(target) and issue[-3:].isdigit() and int(issue[-3:]) <= current_num:
                        save(issue,ns,source='web',force=True)

            # 再检查数据库，确定应该补到哪里。
            ds=draws()
            nums=sorted({int(d['issue'][-3:]) for d in ds if d['issue'].startswith(target) and d['issue'][-3:].isdigit()})
            # 机器人是当前期主源；无机器人数据时才使用3分彩专用API。
            if current_num<=0:
                time.sleep(15)
                continue
            # 删除任何超过真源当前期号的当天记录，防止旧错误数据再次进入预测。
            c=sqlite3.connect(DB_PATH)
            c.execute("DELETE FROM draws WHERE issue LIKE ? AND CAST(substr(issue,9,3) AS INTEGER)>?",(target+'%',current_num))
            c.commit(); c.close()
            expected=set(range(1,current_num+1))
            have=set(nums)
            missing=sorted(expected-have)

            # 只补缺号；避免每分钟重复请求全部历史。
            if missing:
               from concurrent.futures import ThreadPoolExecutor, as_completed
               with ThreadPoolExecutor(max_workers=20) as ex:
                   futs={ex.submit(fetch_issue_api,f'{target}{i:03d}'):i for i in missing}
                   for f in as_completed(futs):
                       try:
                           item=f.result()
                           if item and item[0].startswith(target): save(item[0],item[1],source='api',force=True)
                       except Exception:
                           pass

            # 最后再扫一次页面；仍然严格限制在当前接口确认的期号以内。
            for page in range(1,61):
                got=fetch_history_page(page)
                for issue,ns in got:
                    if issue.startswith(target) and issue[-3:].isdigit() and int(issue[-3:]) <= current_num:
                         save(issue,ns,source='web',force=True)

            # 连续性状态由页面读取；如果001~当前全齐，就进入60秒检查，否则15秒重试。
            ds=draws()
            have2={int(d['issue'][-3:]) for d in ds if d['issue'].startswith(target) and d['issue'][-3:].isdigit()}
            complete=current_num>0 and all(i in have2 for i in range(1,current_num+1))
            time.sleep(60 if complete else 15)
        except Exception:
            time.sleep(15)


def cycle_start_for(ds):
 return sorted(ds,key=lambda d:key(d['issue']))[0]['issue'] if ds else datetime.now(BJ).strftime('%Y%m%d')+'001'

def active(ds): return sorted(ds,key=lambda d:key(d['issue'])),cycle_start_for(ds)

def _transition_stats(hist, attr):
 vals=[attr(d['special']) for d in hist]; counts={}; trans={}
 for v in vals: counts[v]=counts.get(v,0)+1
 for a,b in zip(vals,vals[1:]): trans[(a,b)]=trans.get((a,b),0)+1
 return counts,trans

def adaptive_components(hist):
 hist=sorted(hist,key=lambda d:key(d['issue'])); nums={n:0.0 for n in range(1,50)}
 if not hist:return nums,{}, {}, '无历史'
 for w,wt in [(12,2.0),(24,1.45),(48,0.9),(96,0.5),(180,0.25),(360,0.12),(720,0.06)]:
  part=hist[-w:]; plen=len(part)
  for i,d in enumerate(part): nums[d['special']]+=wt*(0.45+0.55*(i+1)/plen)
 for d in hist: nums[d['special']]+=0.035
 last_seen={n:-1 for n in range(1,50)}
 for i,d in enumerate(hist): last_seen[d['special']]=i
 L=len(hist)
 for n in range(1,50): nums[n]+=min(L-1-last_seen[n] if last_seen[n]>=0 else L,60)*0.012
 zc,zt=_transition_stats(hist,lambda n:Z[n]); wc,wt=_transition_stats(hist,wave)
 zscore={z:0.0 for z in set(Z.values())}; wscore={w:0.0 for w in ('红波','蓝波','绿波')}
 for z,c in zc.items(): zscore[z]+=c/max(L,1)*1.2
 for w,c in wc.items(): wscore[w]+=c/max(L,1)*1.2
 for w in (12,24,48,96):
  part=hist[-w:]
  for i,d in enumerate(part):
   zscore[Z[d['special']]]+=(0.35+0.65*(i+1)/max(1,len(part)))
   wscore[wave(d['special'])]+=(0.35+0.65*(i+1)/max(1,len(part)))
 lastz=Z[hist[-1]['special']]; lastw=wave(hist[-1]['special'])
 if lastz in zc:
  for z in zscore: zscore[z]+=0.8*zt.get((lastz,z),0)/max(1,zc[lastz])
 if lastw in wc:
  for w in wscore: wscore[w]+=0.8*wt.get((lastw,w),0)/max(1,wc[lastw])
 last=hist[-1]['special']; eligible=len(hist)-1; repeats=sum(1 for a,b in zip(hist,hist[1:]) if a['special']==b['special']); repeat_rate=repeats/max(1,eligible)
 if repeat_rate<0.035: nums[last]*=0.52
 elif repeat_rate<0.065: nums[last]*=0.68
 elif repeat_rate>0.085: nums[last]*=0.88
 else: nums[last]*=0.75
 if len(hist)>=2 and hist[-2]['special']==last: nums[last]*=0.65
 recent=hist[-8:]
 for n in range(1,50):
  nums[n]-=sum(1 for d in recent if Z[d['special']]==Z[n])*0.025
  nums[n]-=sum(1 for d in recent if wave(d['special'])==wave(n))*0.012
 for n in range(1,50): nums[n]+=0.22*zscore[Z[n]]+0.16*wscore[wave(n)]
 return nums,zscore,wscore,f'特码重复率 {repeat_rate*100:.1f}%；上一期特码仅在模型支持时保留'

def special_score_map(hist): return adaptive_components(hist)[0]
def score_candidates(hist,limit=22):
 score,_,_,_=adaptive_components(hist); return sorted(range(1,50),key=lambda n:(-score[n],n))[:limit]

def predict_zodiac_wave(hist,cand,scores):
 score,zscore,wscore,rep=adaptive_components(hist)
 zr=sorted(zscore,key=lambda z:(-zscore[z],z)); bestz=zr[0] if zr else None
 if len(zr)>1 and hist and [Z[d['special']] for d in hist[-5:]].count(bestz)>=2: bestz=zr[1]
 members=[n for n in range(1,50) if Z[n]==bestz]; bestn=max(members,key=lambda n:(scores[n],-n)) if members else None
 wr=sorted(wscore,key=lambda w:(-wscore[w],w)); return bestz,bestn,(wr[0] if wr else None),rep

def ensure_prediction_table():
 c=sqlite3.connect(DB_PATH); c.execute('CREATE TABLE IF NOT EXISTS predictions(issue TEXT PRIMARY KEY,candidates TEXT,created_at TEXT,hit INTEGER,zodiac TEXT,wave TEXT)'); c.commit(); c.close()

BACKTEST_CACHE={'latest':None,'stats':None}

def evaluate_cycle(ds,start):
 act=sorted(ds,key=lambda d:key(d['issue'])); latest=act[-1]['issue'] if act else None
 if BACKTEST_CACHE['latest']==latest and BACKTEST_CACHE['stats'] is not None: return BACKTEST_CACHE['stats']
 sample=act[-1000:] if len(act)>1000 else act
 hits=0; total=0
 for idx,d in enumerate(sample):
  if idx<60: continue
  hist=sample[:idx]
  cand=score_candidates(hist,22); hits += int(d['special'] in cand); total += 1
 stats={'all_history':len(act),'evaluated_count':total,'hit_periods':hits,'miss_periods':total-hits,'hit_rate':round(hits/total*100,1) if total else 0.0}
 BACKTEST_CACHE['latest']=latest; BACKTEST_CACHE['stats']=stats
 return stats

def pack(n): return {'number':f'{n:02d}','zodiac':Z[n],'wave':wave(n)}
@app.get('/')
def home(): return render_template_string(HTML)
@app.get('/api/data')
def data():
 ds=draws(); hist,start=active(ds); latest=hist[-1] if hist else None; cand=score_candidates(hist,22) if hist else []; scores=special_score_map(hist) if hist else {}
 pz,pn,pw,rep=predict_zodiac_wave(hist,cand,scores) if hist else (None,None,None,'无历史'); stats=evaluate_cycle(hist,start)
 history=[{'issue':d['issue'],'numbers':[pack(n) for n in d['numbers']],'special':pack(d['special']),'time':d['received_at']} for d in reversed(hist[-1000:])]
 return jsonify({'latest':({'issue':latest['issue'],'time':latest['received_at'],'numbers':[pack(n) for n in latest['numbers']],'special':pack(latest['special'])} if latest else None),'candidates':[pack(n) for n in cand],'copy':','.join(f'{n:02d}' for n in cand),'candidate_zodiac':({'zodiac':pz,'number':f'{pn:02d}' if pn else None} if pz else None),'predicted_wave':pw,'repeat_note':rep,'active_count':len(hist),'cycle_start':start,'stats':stats,'history':history,'data_status':{'source':'seed+telegram','total':len(ds),'displayed_history':len(history),'earliest':(hist[0]['issue'] if hist else None),'latest':(hist[-1]['issue'] if hist else None)}})

init(); seed_csv(); seed_robot_extra(); ensure_prediction_table(); threading.Thread(target=tg,daemon=True,name='telegram-receiver').start()

HTML='''<!doctype html><html lang="zh-CN"><meta name="viewport" content="width=device-width,initial-scale=1"><title>澳门六合彩·3分</title><style>body{margin:0;background:#f4f7fb;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;color:#15233d}.head{background:#123f82;color:#fff;padding:14px}.wrap{max-width:900px;margin:auto;padding:10px}.card{background:#fff;border-radius:16px;padding:14px;margin-bottom:10px;box-shadow:0 4px 18px #17345a12}.row{display:flex;justify-content:space-between;align-items:center;gap:8px}.title{font-size:18px;font-weight:800}.muted{color:#78879c;font-size:12px}.status{background:#eaffef;color:#087d31;border-radius:18px;padding:6px 9px;font-size:12px}.latest{display:flex;gap:7px;flex-wrap:wrap;margin-top:8px}.ball{width:40px;height:40px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:900;border:2px solid}.red{color:#d71919;border-color:#ef4141;background:#fff1f1}.blue{color:#125de2;border-color:#2174ee;background:#eef5ff}.green{color:#129344;border-color:#20a453;background:#effbf3}.meta{text-align:center;font-size:10px;font-weight:700;margin-top:2px}.copy{background:#1667e8;color:#fff;border:0;border-radius:10px;padding:8px 11px;font-size:13px;font-weight:800}.nums{color:#084fe0;font-size:18px;font-weight:900;line-height:1.45;margin:8px 0;word-break:break-all}.grid{display:grid;grid-template-columns:repeat(6,1fr);gap:7px}.tile{text-align:center;border:1px solid #dfe6f0;border-radius:11px;padding:7px 2px}.n{font-size:18px;font-weight:900}.zgrid{display:grid;grid-template-columns:repeat(5,1fr);gap:7px}.z{text-align:center;border:1px solid #ddd;border-radius:11px;padding:8px 3px}.zname{font-size:16px;font-weight:900}.znums{font-size:12px;color:#64748b;margin-top:3px;font-weight:800}.note{background:#eff6ff;border-radius:10px;padding:8px;color:#637795;font-size:11px;margin-top:8px}.hist{display:flex;flex-direction:column;gap:6px}.hrow{display:grid;grid-template-columns:72px 1fr 45px;align-items:center;border-bottom:1px solid #edf1f6;padding:5px 0;font-size:12px}.hnums{font-weight:800;letter-spacing:.3px}.hspec{font-weight:900;text-align:right}@media(max-width:650px){.grid{grid-template-columns:repeat(5,1fr)}.zgrid{grid-template-columns:repeat(3,1fr)}} </style><body><div class="head"><div class="row"><div><b>澳门六合彩 · 3分</b><div style="font-size:12px">实时开奖 · 下一期开奖结果预测</div></div><div class="status">🟢 实时接收</div></div></div><div class="wrap"><div class="card"><div class="row"><div class="title">最新开奖</div><div id="time" class="muted"></div></div><div id="issue" class="muted"></div><div id="latest" class="latest"></div></div><div class="card"><div class="row"><div><div class="title">⭐ 下一期预测特码</div><div class="muted">用最新一期之前的全部历史数据，01～49全部评分后取最高22码</div></div><button class="copy" onclick="cp()">复制22码</button></div><div id="nums" class="nums"></div><div id="grid" class="grid"></div><div id="stats" class="note"></div></div><div class="card"><div class="title">⭐ 下一期预测生肖</div><div id="zgrid" class="zgrid" style="margin-top:8px"></div><div id="wave" class="note"></div></div><div class="card"><div class="title">📜 本周期全部历史开奖</div><div class="muted" id="hcount">数据库保留全部历史；页面显示最近1000期</div><div id="hist" class="hist" style="margin-top:6px"></div></div></div><script>let cpv='';function wc(w){return w[0]=='红'?'red':w[0]=='蓝'?'blue':'green'}function render(d){document.querySelector('#time').textContent=d.latest?new Date(d.latest.time).toLocaleString('zh-CN',{hour12:false}):'';document.querySelector('#issue').textContent=d.latest?'第'+d.latest.issue+'期':('等待历史数据抓取…（当前0期）');let h='';if(d.latest){for(const x of d.latest.numbers)h+=`<div><div class="ball ${wc(x.wave)}">${x.number}</div><div class="meta ${wc(x.wave)}">${x.zodiac}·${x.wave}</div></div>`;const x=d.latest.special;h+=`<div><div class="ball ${wc(x.wave)}">${x.number}</div><div class="meta ${wc(x.wave)}">${x.zodiac}·${x.wave}<br>特码</div></div>`}document.querySelector('#latest').innerHTML=h;cpv=d.copy;document.querySelector('#nums').textContent=d.copy;document.querySelector('#stats').innerHTML=`历史库存：${d.stats.all_history}期　　已回测：${d.stats.evaluated_count}期　命中：${d.stats.hit_periods}期　错误：${d.stats.miss_periods}期　历史命中率：${d.stats.hit_rate}%　累计命中：${d.stats.total_hits}次`;document.querySelector('#grid').innerHTML=d.candidates.map(x=>`<div class="tile"><div class="n ${wc(x.wave)}">${x.number}</div><div class="meta ${wc(x.wave)}">${x.zodiac}·${x.wave}</div></div>`).join('');document.querySelector('#zgrid').innerHTML=d.candidate_zodiac?`<div class="z"><div class="zname">${d.candidate_zodiac.zodiac}</div><div class="znums">一肖一码：${d.candidate_zodiac.number}</div></div>`:'';document.querySelector('#wave').textContent=d.predicted_wave?`预测波色：${d.predicted_wave}　${d.repeat_note||''}`:'';document.querySelector('#hcount').textContent='数据库共'+d.data_status.total+'期；页面显示最近'+d.history.length+'期（历史数据不删除）';document.querySelector('#hist').innerHTML=d.history.map(r=>{let ns=r.numbers.map(x=>`<span class="smallball ${wc(x.wave)}">${x.number}</span>`).join(' ');return `<div class="hrow"><div>${r.issue.slice(-3)}期</div><div class="hnums">${ns}</div><div class="hspec ${wc(r.special.wave)}">+${r.special.number}</div></div>`}).join('')}async function load(){try{const r=await fetch('/api/data?x='+Date.now());if(!r.ok)throw new Error('API '+r.status);render(await r.json())}catch(e){document.querySelector('#issue').textContent='数据读取中…';}}async function cp(){try{await navigator.clipboard.writeText(cpv);alert('已复制：'+cpv)}catch(e){prompt('复制下面号码：',cpv)}}load();setInterval(load,15000)</script></body></html>'''
