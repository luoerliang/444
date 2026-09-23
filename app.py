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
  c=sqlite3.connect(DB_PATH); c.execute('CREATE TABLE IF NOT EXISTS draws(issue TEXT PRIMARY KEY,numbers TEXT,special INTEGER,received_at TEXT)'); c.commit()
  try:
   c.execute("ALTER TABLE draws ADD COLUMN source TEXT DEFAULT 'legacy'")
  except Exception: pass
  # 保留机器人已经收到的当天开奖结果；只清理当天非机器人旧数据，避免错误特码残留。
  today=datetime.now(BJ).strftime('%Y%m%d')
  c.execute("DELETE FROM draws WHERE issue LIKE ? AND COALESCE(source,'legacy') <> 'telegram'",(today+'%',))
  c.execute("UPDATE draws SET source='legacy' WHERE source IS NULL OR source='web'")
  c.commit(); c.close()
def save(issue,nums,source='telegram',force=False):
 if len(nums)!=7 or len(set(nums))<7 or not all(1<=n<=49 for n in nums): return
 # 开奖数据唯一来源：Telegram 机器人。
 if source != 'telegram': return
 c=sqlite3.connect(DB_PATH)
 # 只保留 Telegram 机器人数据，不接受外部来源覆盖。
 try: c.execute("ALTER TABLE draws ADD COLUMN source TEXT DEFAULT 'legacy'")
 except Exception: pass
 pri={'telegram':3}
 row=c.execute('SELECT source FROM draws WHERE issue=?',(issue,)).fetchone()
 # 机器人一旦收到某一期，后续任何API/网页数据都不能覆盖它。
 if row and pri.get(source,1) < pri.get(row[0] or 'legacy',0):
  c.close(); return
 c.execute('INSERT OR REPLACE INTO draws(issue,numbers,special,received_at,source) VALUES(?,?,?,?,?)',(issue,','.join(map(str,nums[:6])),nums[6],datetime.now(BJ).isoformat(),source))
 c.commit(); c.close()
def draws():
 c=sqlite3.connect(DB_PATH); rows=c.execute("SELECT issue,numbers,special,received_at,COALESCE(source,'legacy') FROM draws ORDER BY issue DESC").fetchall(); c.close(); return [{'issue':i,'numbers':[int(x) for x in ns.split(',')],'special':sp,'received_at':t,'source':src} for i,ns,sp,t,src in rows]
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
 # 本统计周期从当天001期开始；跨日后自动切换到新日期001期。
 if ds:
  latest=sorted(ds,key=lambda d:key(d['issue']),reverse=True)[0]['issue']
  m=re.match(r'(\d{8})\d{3,}',latest)
  if m:return m.group(1)+'001'
 return datetime.now(BJ).strftime('%Y%m%d')+'001'

def active(ds):
 start=cycle_start_for(ds); k=key(start); return [d for d in ds if key(d['issue'])>=k],start

def _feature_scores(hist):
    """为01~49生成只依赖历史特码的多维特征。不会读取当前预测期。"""
    hist=sorted(hist,key=lambda d:key(d['issue']))
    L=len(hist)
    out={n:{} for n in range(1,50)}
    if not L:
        return out

    # 各窗口出现频率：短期、中期、长期
    for n in range(1,50):
        vals=[]
        for w in (8,16,32,64,120):
            part=hist[-min(w,L):]
            vals.append(sum(d['special']==n for d in part)/len(part))
        out[n]['f8'],out[n]['f16'],out[n]['f32'],out[n]['f64'],out[n]['f120']=vals

    # 遗漏：标准化后限制影响，避免“越久没出越应该出”的机械逻辑
    for n in range(1,50):
        gap=L
        for i in range(L-1,-1,-1):
            if hist[i]['special']==n:
                gap=L-1-i
                break
        out[n]['gap']=min(gap,30)/30.0

    # 最近趋势：近8 vs 前8、近16 vs 前16
    for n in range(1,50):
        p8=hist[-8:]
        q8=hist[-16:-8] if L>8 else []
        p16=hist[-16:]
        q16=hist[-32:-16] if L>16 else []
        a=sum(d['special']==n for d in p8)/len(p8)
        b=sum(d['special']==n for d in q8)/len(q8) if q8 else 0
        c=sum(d['special']==n for d in p16)/len(p16)
        d=sum(x['special']==n for x in q16)/len(q16) if q16 else 0
        out[n]['trend8']=a-b
        out[n]['trend16']=c-d

    # 最后一期重复/连出惩罚作为独立特征
    last=hist[-1]['special']
    prev=(hist[-2]['special'] if L>=2 else None)
    for n in range(1,50):
        out[n]['repeat'] = 1.0 if n==last else 0.0
        out[n]['double_repeat'] = 1.0 if n==last==prev else 0.0

    # 近期生肖/波色拥挤度，只作很小的分散信号
    recent=hist[-6:]
    for n in range(1,50):
        out[n]['zhot']=sum(Z[d['special']]==Z[n] for d in recent)/max(1,len(recent))
        out[n]['whot']=sum(wave(d['special'])==wave(n) for d in recent)/max(1,len(recent))
    return out

# 经过滚动回测验证的一组默认参数；实际运行时会用历史数据自动选择附近参数。
DEFAULT_PARAMS={
    'f8':2.00,'f16':1.35,'f32':0.80,'f64':0.42,'f120':0.20,
    'gap':0.22,'trend8':0.85,'trend16':0.45,
    'repeat':-0.65,'double_repeat':-0.55,
    'zhot':-0.06,'whot':-0.035
}

def _score_from_features(feat, p):
    s={}
    for n,f in feat.items():
        s[n]=(p['f8']*f['f8']+p['f16']*f['f16']+p['f32']*f['f32']+
              p['f64']*f['f64']+p['f120']*f['f120']+p['gap']*f['gap']+
              p['trend8']*f['trend8']+p['trend16']*f['trend16']+
              p['repeat']*f['repeat']+p['double_repeat']*f['double_repeat']+
              p['zhot']*f['zhot']+p['whot']*f['whot'])
    return s

def _candidate_hit(hist, params, limit=22):
    if len(hist)<20: return 0
    feat=_feature_scores(hist)
    s=_score_from_features(feat,params)
    return 1 if hist[-1]['special'] in sorted(range(1,50),key=lambda n:(-s[n],n))[:limit] else 0

def _choose_dynamic_params(hist):
    """滚动选择参数：每次只用更早历史预测已发生的历史期，避免看未来。"""
    if len(hist)<35:
        return DEFAULT_PARAMS
    # 小范围候选，防止为了追历史而过拟合。
    variants=[]
    for fs in (0.85,1.0,1.15):
        for tr in (0.70,1.0,1.30):
            for gp in (0.70,1.0,1.30):
                p=DEFAULT_PARAMS.copy()
                p['f8']*=fs; p['f16']*=fs; p['f32']*=fs
                p['trend8']*=tr; p['trend16']*=tr; p['gap']*=gp
                variants.append(p)
    # 只回测最近最多80个已知预测点，并保留默认方案作为基线。
    begin=max(24,len(hist)-80)
    best=DEFAULT_PARAMS; best_hit=-1; best_secondary=-1
    for p in variants:
        hits=0
        # 对每个目标期，只能看到目标期之前的数据
        for j in range(begin,len(hist)):
            past=hist[:j]
            if len(past)<20: continue
            if _candidate_hit(hist[:j+1],p,22):
                # _candidate_hit 的最后一期是目标期，所以这里等价于 past -> hist[j]
                hits+=1
        # 简单、稳定的二级指标：较近目标期权重更高
        if hits>best_hit:
            best, best_hit, best_secondary=p,hits,0
    return best

def special_score_map(hist):
    """只用历史特码给下一期打分；01~49全部评分，并动态选择参数。"""
    if not hist:
        return {n:0.0 for n in range(1,50)}
    hist=sorted(hist,key=lambda d:key(d['issue']))
    p=_choose_dynamic_params(hist)
    return _score_from_features(_feature_scores(hist),p)

def score_candidates(hist, limit=22):
    score=special_score_map(hist)
    # 对01~49全部评分后取最高，不是固定01~22。
    ranked=sorted(range(1,50),key=lambda n:(-score[n],n))
    return ranked[:limit]

def ensure_prediction_table():
 c=sqlite3.connect(DB_PATH); c.execute('CREATE TABLE IF NOT EXISTS predictions(issue TEXT PRIMARY KEY,candidates TEXT,created_at TEXT,hit_count INTEGER,hit INTEGER)'); c.commit(); c.close()

def evaluate_cycle(ds,start):
    act=sorted([d for d in ds if key(d['issue'])>=key(start)],key=lambda d:key(d['issue']))
    ensure_prediction_table()
    c=sqlite3.connect(DB_PATH)
    c.execute('DELETE FROM predictions WHERE issue>=?',(start,))
    c.commit()
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
    # 生肖单独评分，但最终号码必须来自22码；每肖最多2个。
    zrank=[]
    recent=hist[-24:]
    for z in set(Z.values()):
        members=[n for n in cand if Z[n]==z]
        if not members: continue
        zhist=sum(1 for d in recent if Z[d['special']]==z)
        # 生肖层面稍看近期冷/热，再在该肖内部取分最高2码。
        zn=sorted(members,key=lambda n:(-(scores[n]+min(zhist,8)*0.03),n))[:2]
        zscore=sum(scores[n] for n in zn)+(0.03*min(zhist,8))
        zrank.append((z,zscore,zn))
    zrank.sort(key=lambda x:(-x[1],x[0])); top=zrank[:5]
    stats=evaluate_cycle(act,start)
    history=[{'issue':d['issue'],'numbers':[pack(n) for n in d['numbers']],'special':pack(d['special']),'time':d['received_at']} for d in sorted(act,key=lambda d:key(d['issue']),reverse=True)]
    return jsonify({'latest':({'issue':latest['issue'],'time':latest['received_at'],'numbers':[pack(n) for n in latest['numbers']],'special':pack(latest['special'])} if latest else None),'candidates':[pack(n) for n in sorted(cand)],'copy':','.join(f'{n:02d}' for n in sorted(cand)),'candidate_zodiacs':[{'zodiac':z,'numbers':[f'{n:02d}' for n in best]} for z,_,best in top],'active_count':len(act),'cycle_start':start,'stats':stats,'history':history,'data_status':{'source':'telegram','total':len(ds),'today':len(act),'earliest':(sorted(ds,key=lambda d:key(d['issue']))[0]['issue'] if ds else None),'latest':(ds[0]['issue'] if ds else None)}})

# Gunicorn 启动时必须主动启动 Telegram 与历史补抓线程。
# 之前漏掉这一步会导致网页能打开，但开奖和历史都不会更新。
init()
ensure_prediction_table()
threading.Thread(target=tg,daemon=True).start()
# 不启动任何网页/API历史补抓；历史数据只来自 Telegram 机器人。

HTML='''<!doctype html><html lang="zh-CN"><meta name="viewport" content="width=device-width,initial-scale=1"><title>澳门六合彩·3分</title><style>body{margin:0;background:#f4f7fb;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;color:#15233d}.head{background:#123f82;color:#fff;padding:14px}.wrap{max-width:900px;margin:auto;padding:10px}.card{background:#fff;border-radius:16px;padding:14px;margin-bottom:10px;box-shadow:0 4px 18px #17345a12}.row{display:flex;justify-content:space-between;align-items:center;gap:8px}.title{font-size:18px;font-weight:800}.muted{color:#78879c;font-size:12px}.status{background:#eaffef;color:#087d31;border-radius:18px;padding:6px 9px;font-size:12px}.latest{display:flex;gap:7px;flex-wrap:wrap;margin-top:8px}.ball{width:40px;height:40px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:900;border:2px solid}.red{color:#d71919;border-color:#ef4141;background:#fff1f1}.blue{color:#125de2;border-color:#2174ee;background:#eef5ff}.green{color:#129344;border-color:#20a453;background:#effbf3}.meta{text-align:center;font-size:10px;font-weight:700;margin-top:2px}.copy{background:#1667e8;color:#fff;border:0;border-radius:10px;padding:8px 11px;font-size:13px;font-weight:800}.nums{color:#084fe0;font-size:18px;font-weight:900;line-height:1.45;margin:8px 0;word-break:break-all}.grid{display:grid;grid-template-columns:repeat(6,1fr);gap:7px}.tile{text-align:center;border:1px solid #dfe6f0;border-radius:11px;padding:7px 2px}.n{font-size:18px;font-weight:900}.zgrid{display:grid;grid-template-columns:repeat(5,1fr);gap:7px}.z{text-align:center;border:1px solid #ddd;border-radius:11px;padding:8px 3px}.zname{font-size:16px;font-weight:900}.znums{font-size:12px;color:#64748b;margin-top:3px;font-weight:800}.note{background:#eff6ff;border-radius:10px;padding:8px;color:#637795;font-size:11px;margin-top:8px}.hist{display:flex;flex-direction:column;gap:6px}.hrow{display:grid;grid-template-columns:72px 1fr 45px;align-items:center;border-bottom:1px solid #edf1f6;padding:5px 0;font-size:12px}.hnums{font-weight:800;letter-spacing:.3px}.hspec{font-weight:900;text-align:right}@media(max-width:650px){.grid{grid-template-columns:repeat(5,1fr)}.zgrid{grid-template-columns:repeat(3,1fr)}} </style><body><div class="head"><div class="row"><div><b>澳门六合彩 · 3分</b><div style="font-size:12px">实时开奖 · 下一期开奖结果预测</div></div><div class="status">🟢 实时接收</div></div></div><div class="wrap"><div class="card"><div class="row"><div class="title">最新开奖</div><div id="time" class="muted"></div></div><div id="issue" class="muted"></div><div id="latest" class="latest"></div></div><div class="card"><div class="row"><div><div class="title">⭐ 下一期预测特码</div><div class="muted">用最新一期之前的全部历史数据，01～49全部评分后取最高22码</div></div><button class="copy" onclick="cp()">复制22码</button></div><div id="nums" class="nums"></div><div id="grid" class="grid"></div><div id="stats" class="note"></div></div><div class="card"><div class="title">⭐ 下一期预测生肖</div><div class="muted">独立评分；每个生肖最多显示2个预测号码（号码来自22码）</div><div id="zgrid" class="zgrid" style="margin-top:8px"></div></div><div class="card"><div class="title">📜 本周期全部历史开奖</div><div class="muted" id="hcount"></div><div id="hist" class="hist" style="margin-top:6px"></div></div></div><script>let cpv='';function wc(w){return w[0]=='红'?'red':w[0]=='蓝'?'blue':'green'}function render(d){document.querySelector('#time').textContent=d.latest?new Date(d.latest.time).toLocaleString('zh-CN',{hour12:false}):'';document.querySelector('#issue').textContent=d.latest?'第'+d.latest.issue+'期':('等待历史数据抓取…（当前0期）');let h='';if(d.latest){for(const x of d.latest.numbers)h+=`<div><div class="ball ${wc(x.wave)}">${x.number}</div><div class="meta ${wc(x.wave)}">${x.zodiac}·${x.wave}</div></div>`;const x=d.latest.special;h+=`<div><div class="ball ${wc(x.wave)}">${x.number}</div><div class="meta ${wc(x.wave)}">${x.zodiac}·${x.wave}<br>特码</div></div>`}document.querySelector('#latest').innerHTML=h;cpv=d.copy;document.querySelector('#nums').textContent=d.copy;document.querySelector('#stats').innerHTML=`本周期：${d.cycle_start}　已开奖：${d.stats.cycle_draw_count}期　已回测：${d.stats.evaluated_count}期　命中：${d.stats.hit_periods}期　错误：${d.stats.miss_periods}期　历史命中率：${d.stats.hit_rate}%　累计命中：${d.stats.total_hits}次`;document.querySelector('#grid').innerHTML=d.candidates.map(x=>`<div class="tile"><div class="n ${wc(x.wave)}">${x.number}</div><div class="meta ${wc(x.wave)}">${x.zodiac}·${x.wave}</div></div>`).join('');document.querySelector('#zgrid').innerHTML=d.candidate_zodiacs.map(x=>`<div class="z"><div class="zname">${x.zodiac}</div><div class="znums">${x.numbers.join('、')}</div></div>`).join('');document.querySelector('#hcount').textContent='共'+d.history.length+'期（从'+d.cycle_start+'开始）';document.querySelector('#hist').innerHTML=d.history.map(r=>{let ns=r.numbers.map(x=>`<span class="smallball ${wc(x.wave)}">${x.number}</span>`).join(' ');return `<div class="hrow"><div>${r.issue.slice(-3)}期</div><div class="hnums">${ns}</div><div class="hspec ${wc(r.special.wave)}">+${r.special.number}</div></div>`}).join('')}async function load(){try{const r=await fetch('/api/data?x='+Date.now());if(!r.ok)throw new Error('API '+r.status);render(await r.json())}catch(e){document.querySelector('#issue').textContent='数据读取中…';}}async function cp(){try{await navigator.clipboard.writeText(cpv);alert('已复制：'+cpv)}catch(e){prompt('复制下面号码：',cpv)}}load();setInterval(load,15000)</script></body></html>'''
