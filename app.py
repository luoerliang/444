
import os,re,sqlite3,threading,time,json,csv
from datetime import datetime,timezone,timedelta
from flask import Flask,jsonify,render_template_string,Response
import urllib.request

app=Flask(__name__)
DB_PATH=os.getenv("DB_PATH","draws.db")
BOT_TOKEN=os.getenv("TELEGRAM_BOT_TOKEN","").strip()
BJ=timezone(timedelta(hours=8))
BASE=os.path.dirname(os.path.abspath(__file__))

Z={1:"马",13:"马",25:"马",37:"马",49:"马",2:"蛇",14:"蛇",26:"蛇",38:"蛇",3:"龙",15:"龙",27:"龙",39:"龙",4:"兔",16:"兔",28:"兔",40:"兔",5:"虎",17:"虎",29:"虎",41:"虎",6:"牛",18:"牛",30:"牛",42:"牛",7:"鼠",19:"鼠",31:"鼠",43:"鼠",8:"猪",20:"猪",32:"猪",44:"猪",9:"狗",21:"狗",33:"狗",45:"狗",10:"鸡",22:"鸡",34:"鸡",46:"鸡",11:"猴",23:"猴",35:"猴",47:"猴",12:"羊",24:"羊",36:"羊",48:"羊"}
RED={1,2,7,8,12,13,18,19,23,24,29,30,34,35,40,45,46}
BLUE={3,4,9,10,14,15,20,25,26,31,36,37,41,42,47,48}
def wave(n): return "红波" if n in RED else "蓝波" if n in BLUE else "绿波"

def init():
    c=sqlite3.connect(DB_PATH)
    c.execute("CREATE TABLE IF NOT EXISTS draws(issue TEXT PRIMARY KEY,numbers TEXT,special INTEGER,received_at TEXT,source TEXT DEFAULT 'legacy')")
    c.execute("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY,v TEXT)")
    c.commit(); c.close()

def save(issue,nums,source="telegram"):
    issue=str(issue)
    nums=[int(x) for x in nums]
    if len(nums)!=7 or len(set(nums))<7 or not all(1<=x<=49 for x in nums): return
    pri={"legacy":0,"seed":1,"web":2,"api":2,"telegram":3}
    c=sqlite3.connect(DB_PATH)
    row=c.execute("SELECT source FROM draws WHERE issue=?",(issue,)).fetchone()
    if row and pri.get(source,1)<pri.get(row[0] or "legacy",0):
        c.close(); return
    c.execute("INSERT OR REPLACE INTO draws(issue,numbers,special,received_at,source) VALUES(?,?,?,?,?)",
              (issue,",".join(map(str,nums[:6])),nums[6],datetime.now(BJ).isoformat(),source))
    c.commit(); c.close()

def draws():
    c=sqlite3.connect(DB_PATH)
    rows=c.execute("SELECT issue,numbers,special,received_at,COALESCE(source,'legacy') FROM draws ORDER BY issue ASC").fetchall()
    c.close()
    return [{"issue":i,"numbers":[int(x) for x in ns.split(",")],"special":int(sp),"received_at":t,"source":src} for i,ns,sp,t,src in rows]

def import_seeds():
    p=os.path.join(BASE,"history_seed.csv")
    if os.path.exists(p):
        try:
            with open(p,"r",encoding="utf-8-sig",newline="") as f:
                for r in csv.DictReader(f):
                    issue=str(r.get("期号","")).strip()
                    try:
                        nums=[int(r[k]) for k in ["正码1","正码2","正码3","正码4","正码5","正码6","特码"]]
                        if re.fullmatch(r"20\d{9}",issue): save(issue,nums,"seed")
                    except Exception: pass
        except Exception: pass
    p=os.path.join(BASE,"robot_seed.json")
    if os.path.exists(p):
        try:
            for issue,nums in json.load(open(p,"r",encoding="utf-8")).items():
                save("20260923"+str(int(issue)).zfill(3),nums,"seed")
        except Exception: pass

def ensure_seed_data():
    """只补缺，不删除数据库；Render重启后即使SQLite为空也会自动恢复随包历史。"""
    try:
        c=sqlite3.connect(DB_PATH)
        n=c.execute("SELECT COUNT(*) FROM draws").fetchone()[0]
        c.close()
        if n==0:
            import_seeds()
    except Exception:
        try: import_seeds()
        except Exception: pass

def parse_tg(text):
    m=re.search(r"(20\d{9})",text or "")
    if not m:return None
    nums=[]
    for x in re.findall(r"(?<!\d)(0?[1-9]|[1-4]\d|49)(?!\d)",text[m.end():]):
        n=int(x)
        if n not in nums: nums.append(n)
        if len(nums)==7: break
    return (m.group(1),nums) if len(nums)==7 else None

def tg():
    if not BOT_TOKEN:return
    off=0
    while True:
        try:
            if off==0:
                try:
                    urllib.request.urlopen(
                        urllib.request.Request(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=false"),
                        timeout=10).read()
                except Exception: pass
            url=f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?timeout=25&offset={off}&allowed_updates=%5B%22message%22,%22channel_post%22,%22edited_message%22,%22edited_channel_post%22%5D"
            with urllib.request.urlopen(url,timeout=35) as r: data=json.loads(r.read().decode("utf-8","ignore"))
            for u in data.get("result",[]):
                off=u["update_id"]+1
                m=u.get("message") or u.get("channel_post") or u.get("edited_message") or u.get("edited_channel_post") or {}
                p=parse_tg(m.get("text") or m.get("caption") or "")
                if p: save(p[0],p[1],"telegram")
        except Exception:
            time.sleep(5)

def score(hist):
    """第16版基础上的动态特码评分，只使用历史特码。"""
    s={n:0.0 for n in range(1,50)}
    L=len(hist)
    if not hist:return s
    diversity=len(set(hist[-24:]))/max(1,min(24,L))
    rf=max(0.70,min(1.35,1.0+(0.72-diversity)*1.8))
    for w,wt in [(6,1.00*rf),(12,.82*rf),(24,.62*rf),(48,.48),(96,.34),(192,.22),(384,.12)]:
        part=hist[-w:]
        if not part: continue
        plen=len(part)
        for i,d in enumerate(part): s[d]+=wt*(.35+.65*(i+1)/plen)
    freq={n:0 for n in range(1,50)}
    for d in hist: freq[d]+=1
    for n in range(1,50): s[n]+=.018*freq[n]
    lastpos={}
    for i,d in enumerate(hist): lastpos[d]=i
    for n in range(1,50):
        gap=L-1-lastpos.get(n,-1) if n in lastpos else L
        if 4<=gap<=24:s[n]+=.11+.010*min(gap,24)
        elif 25<=gap<=45:s[n]+=.07
        elif gap>45:s[n]+=.025
    last=hist[-1]; s[last]*=.60
    if L>=2 and hist[-2]==last:s[last]*=.48
    if L>=3 and hist[-3]==last:s[last]*=.42
    for n in range(1,50):
        s[n]-=.018*sum(Z[d]==Z[n] for d in hist[-8:])+.0
        s[n]-=.010*sum(wave(d)==wave(n) for d in hist[-8:])
    trans={}
    for a,b in zip(hist[:-1],hist[1:]):trans[(wave(a),wave(b))]=trans.get((wave(a),wave(b)),0)+1
    row={w:trans.get((wave(last),w),0) for w in ("红波","蓝波","绿波")}; den=sum(row.values())
    if den:
        for n in range(1,50):s[n]+=.16*row[wave(n)]/den
    transz={}
    for a,b in zip(hist[:-1],hist[1:]):transz[(Z[a],Z[b])]=transz.get((Z[a],Z[b]),0)+1
    rowz={z:transz.get((Z[last],z),0) for z in set(Z.values())}; den=sum(rowz.values())
    if den:
        for n in range(1,50):s[n]+=.12*rowz[Z[n]]/den
    r=hist[-18:]
    if r:
        odd=sum(x%2 for x in r); big=sum(x>=25 for x in r); rl=len(r)
        for n in range(1,50):
            s[n]+=.035*((odd if n%2 else rl-odd)/rl)+.035*((big if n>=25 else rl-big)/rl)
    return s

def choose_count(hist,s):
    """第16版基础的动态码数：最多22码；分差明显时收窄，接近时放宽。
    号码本身始终按评分从01~49重新排名，绝不固定01~22。
    """
    if not hist:return 22
    ranked=sorted(range(1,50),key=lambda n:(-s[n],n)); vals=[s[n] for n in ranked]
    mu=sum(vals)/49
    sd=max((sum((x-mu)**2 for x in vals)/49)**0.5,.0001)
    gap=(vals[19]-vals[21])/sd
    diversity=len(set(hist[-24:]))/max(1,min(24,len(hist)))
    if gap < 0.28:
        k=22
    elif gap < 0.60:
        k=21
    else:
        k=20 if diversity<0.72 else 21
    return max(20,min(22,k))

def zodiac_prediction(hist,s):
    """独立生肖模型：近期、遗漏、转移、热度分开评分；每个生肖显示2个号码。"""
    if not hist:return []
    zs={z:0.0 for z in set(Z.values())}; L=len(hist)
    for w,wt in [(6,2.2),(12,1.7),(24,1.15),(48,.72),(96,.34),(192,.16)]:
        part=hist[-w:]
        if not part:continue
        c={z:0 for z in zs}
        for d in part:c[Z[d]]+=1
        for z in zs:zs[z]+=wt*c[z]/len(part)*10
    allc={z:0 for z in zs}
    for d in hist:allc[Z[d]]+=1
    for z in zs:zs[z]+=.008*allc[z]
    lastz={}
    for i,d in enumerate(hist):lastz[Z[d]]=i
    for z in zs:
        gap=L-1-lastz.get(z,-1)
        if 3<=gap<=20:zs[z]+=.13+.008*gap
        elif 21<=gap<=40:zs[z]+=.08
        elif gap>40:zs[z]+=.035
    trans={}
    for a,b in zip(hist[:-1],hist[1:]):trans[(Z[a],Z[b])]=trans.get((Z[a],Z[b]),0)+1
    lastzname=Z[hist[-1]]; row={z:trans.get((lastzname,z),0) for z in zs}; den=sum(row.values())
    if den:
        for z in zs:zs[z]+=.55*row[z]/den
    for z in zs:zs[z]-=.09*max(0,sum(Z[d]==z for d in hist[-8:])-2)
    topz=sorted(zs,key=lambda z:(-zs[z],z))[:5]
    out=[]
    for z in topz:
        local=[]
        for n in range(1,50):
            if Z[n]!=z:continue
            lp=-1
            for i,d in enumerate(hist):
                if d==n:lp=i
            gap=L-1-lp if lp>=0 else L
            hits=sum(1 for d in hist[-18:] if d==n)
            ns=s.get(n,0)+.08*min(gap,24)+.12*hits
            if hist[-1]==n:ns*=.55
            local.append((ns,n))
        nums=[n for _,n in sorted(local,key=lambda x:(-x[0],x[1]))[:2]]
        out.append({"zodiac":z,"numbers":[f"{n:02d}" for n in nums]})
    return out

def pack(n):return {"number":f"{n:02d}","zodiac":Z[n],"wave":wave(n)}

def cache():
    try:return json.load(open(os.path.join(BASE,"backtest_cache.json"),encoding="utf-8"))
    except Exception:return {"history_count":0,"evaluated_count":0,"hit_rates":{},"adaptive_hit_rate":0}

HTML=r'''<!doctype html><html lang="zh-CN"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>澳门六合彩·3分</title>
<style>
body{margin:0;background:#f4f7fb;color:#15233d;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}
.head{background:#123f82;color:#fff;padding:14px}.wrap{max-width:920px;margin:auto;padding:10px}
.card{background:#fff;border-radius:16px;padding:14px;margin-bottom:10px;box-shadow:0 4px 18px #17345a12}
.row{display:flex;justify-content:space-between;align-items:center;gap:8px}.title{font-size:18px;font-weight:900}.muted{color:#77869a;font-size:12px}
.status{border-radius:16px;padding:6px 9px;font-size:12px;background:#eefbf2;color:#087b31}.latest{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
.ball{width:42px;height:42px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:900;border:2px solid}
.red{color:#d71919;border-color:#e94747;background:#fff0f0}.blue{color:#135de2;border-color:#3479ef;background:#eef5ff}.green{color:#129344;border-color:#31a45b;background:#effbf3}
.meta{text-align:center;font-size:10px;font-weight:800;margin-top:2px}.copy{background:#1667e8;color:#fff;border:0;border-radius:10px;padding:8px 11px;font-weight:900}
.nums{font-size:20px;font-weight:900;color:#0757dc;line-height:1.5;margin:8px 0}.grid{display:grid;grid-template-columns:repeat(6,1fr);gap:7px}
.tile{text-align:center;border:1px solid #dfe6f0;border-radius:11px;padding:7px 2px}.n{font-size:18px;font-weight:900}
.zgrid{display:grid;grid-template-columns:repeat(5,1fr);gap:7px}.z{border:1px solid #dfe6f0;border-radius:11px;padding:8px;text-align:center}
.zname{font-size:16px;font-weight:900}.znums{font-size:12px;color:#64748b;font-weight:800;margin-top:3px}.note{background:#eff6ff;border-radius:10px;padding:9px;font-size:11px;color:#60748f;margin-top:8px}
.hrow{display:grid;grid-template-columns:76px 1fr 52px;gap:4px;align-items:center;border-bottom:1px solid #edf1f6;padding:6px 0;font-size:12px}
.hnums{font-weight:800;letter-spacing:.2px}.hspec{text-align:right;font-weight:900}.more{margin-top:8px;width:100%;padding:9px;border:1px solid #d7e0ec;background:#fff;border-radius:10px;font-weight:800}
@media(max-width:650px){.grid{grid-template-columns:repeat(5,1fr)}.zgrid{grid-template-columns:repeat(3,1fr)}}
</style><body><div class="head"><div class="row"><div><b>澳门六合彩 · 3分</b><div style="font-size:12px">全历史回测 · 下一期动态预测</div></div><div id="status" class="status">读取中</div></div></div>
<div class="wrap">
<div class="card"><div class="row"><div><div class="title">最新开奖</div><div id="issue" class="muted"></div></div><div id="time" class="muted"></div></div><div id="latest" class="latest"></div></div>
<div class="card"><div class="row"><div><div class="title">⭐ 下一期预测特码</div><div class="muted">全部历史特码参与评分；动态20～22码（每期自动变码）</div></div><button class="copy" onclick="cp()">复制预测码</button></div><div id="nums" class="nums"></div><div id="grid" class="grid"></div><div id="stats" class="note"></div></div>
<div class="card"><div class="title">⭐ 下一期预测生肖</div><div class="muted">独立评分；前5个生肖，每个2个号码</div><div id="zgrid" class="zgrid" style="margin-top:8px"></div></div>
<div class="card"><div class="row"><div><div class="title">📜 全部历史开奖</div><div class="muted" id="hcount"></div></div><button class="copy" onclick="location.href='/api/history.csv'">导出全部</button></div><div id="hist" style="margin-top:6px"></div><button id="more" class="more" onclick="more()">加载更多历史</button></div>
</div>
<script>
let D=null,CP="",shown=0;
function wc(w){return w[0]=="红"?"red":w[0]=="蓝"?"blue":"green"}
function render(d){
 D=d;CP=d.copy;
 document.querySelector("#status").textContent=d.data_status.telegram_configured?"🟢 Telegram已配置":"🟡 历史正常·Telegram未配置";
 document.querySelector("#issue").textContent=d.latest?"第"+d.latest.issue+"期 · "+d.latest.source:"暂无数据";
 document.querySelector("#time").textContent=d.latest?new Date(d.latest.time).toLocaleString("zh-CN",{hour12:false}):"";
 let h="";
 if(d.latest){
  for(const x of d.latest.numbers)h+=`<div><div class="ball ${wc(x.wave)}">${x.number}</div><div class="meta ${wc(x.wave)}">${x.zodiac}·${x.wave}</div></div>`;
  const x=d.latest.special;h+=`<div><div class="ball ${wc(x.wave)}">${x.number}</div><div class="meta ${wc(x.wave)}">${x.zodiac}·${x.wave}<br>特码</div></div>`;
 }
 document.querySelector("#latest").innerHTML=h;
 document.querySelector("#nums").textContent=d.copy;
 document.querySelector("#grid").innerHTML=d.candidates.map(x=>`<div class="tile"><div class="n ${wc(x.wave)}">${x.number}</div><div class="meta ${wc(x.wave)}">${x.zodiac}·${x.wave}</div></div>`).join("");
 document.querySelector("#zgrid").innerHTML=d.candidate_zodiacs.map(x=>`<div class="z"><div class="zname">${x.zodiac}</div><div class="znums">${x.numbers.join("、")}</div></div>`).join("");
 const r=d.stats;
 document.querySelector("#stats").innerHTML=`全历史${r.history_count||d.data_status.total}期；已回测${r.evaluated_count||0}期。19码 ${r.hit_rates?.["19"]??"-"}%　20码 ${r.hit_rates?.["20"]??"-"}%　21码 ${r.hit_rates?.["21"]??"-"}%　22码 ${r.hit_rates?.["22"]??"-"}%。<br>本期动态预测：${d.candidate_count}码；号码每期按最新历史重新评分并变动。仅作历史统计参考，不代表下一期结果。`;
 document.querySelector("#hcount").textContent="数据库共"+d.history.length+"期；历史开奖原顺序保留";
 shown=0;document.querySelector("#hist").innerHTML="";more();
}
function more(){
 if(!D)return;let a=D.history.slice(shown,shown+300);
 document.querySelector("#hist").insertAdjacentHTML("beforeend",a.map(r=>{let ns=r.numbers.map(x=>`<span class="${wc(x.wave)}">${x.number}</span>`).join(" ");return `<div class="hrow"><div>${r.issue.slice(-3)}期</div><div class="hnums">${ns}</div><div class="hspec ${wc(r.special.wave)}">+${r.special.number}</div></div>`}).join(""));
 shown+=a.length;document.querySelector("#more").style.display=shown<D.history.length?"block":"none";document.querySelector("#more").textContent=`加载更多（已显示${shown}/${D.history.length}）`;
}
async function load(){try{let r=await fetch("/api/data?x="+Date.now());if(!r.ok)throw Error(r.status);render(await r.json())}catch(e){document.querySelector("#status").textContent="🔴 数据读取失败"}}
async function cp(){try{await navigator.clipboard.writeText(CP);alert("已复制："+CP)}catch(e){prompt("复制下面号码：",CP)}}
load();setInterval(load,15000);
</script></body></html>'''

@app.get("/")
def home(): return render_template_string(HTML)

@app.get("/health")
def health():
    ensure_seed_data()
    d=draws()
    return jsonify({"ok":True,"total":len(d),"latest":d[-1]["issue"] if d else None,"telegram_configured":bool(BOT_TOKEN)})

@app.get("/api/history.csv")
def history_csv():
    out=["期号,正码1,正码2,正码3,正码4,正码5,正码6,特码,特码生肖,特码波色,来源"]
    for d in draws():
        out.append(",".join([d["issue"]]+[f"{n:02d}" for n in d["numbers"]]+[f"{d['special']:02d}",Z[d["special"]],wave(d["special"]),d["source"]]))
    return Response("\n".join(out),mimetype="text/csv; charset=utf-8")

@app.get("/api/data")
def data():
    ensure_seed_data()
    ds=draws()
    specials=[d["special"] for d in ds]
    s=score(specials) if specials else {}
    order=sorted(range(1,50),key=lambda n:(-s[n],n)) if specials else []
    # 每次开奖后都用当前全部历史重新评分；码数动态20~22，最多22码。
    stats=cache()
    k=choose_count(specials,s) if specials else 22
    cand=sorted(order[:k])
    zpred=zodiac_prediction(specials,s) if specials else []
    latest=ds[-1] if ds else None
    history=[]
    for d in reversed(ds):
        history.append({"issue":d["issue"],"numbers":[pack(n) for n in d["numbers"]],"special":pack(d["special"]),"time":d["received_at"],"source":d["source"]})
    return jsonify({
        "latest":({"issue":latest["issue"],"time":latest["received_at"],"numbers":[pack(n) for n in latest["numbers"]],"special":pack(latest["special"]),"source":latest["source"]} if latest else None),
        "candidates":[pack(n) for n in cand],"candidate_count":k,
        "copy":",".join(f"{n:02d}" for n in cand),"candidate_zodiacs":zpred,
        "stats":stats,"history":history,
        "data_status":{"total":len(ds),"earliest":ds[0]["issue"] if ds else None,"latest":ds[-1]["issue"] if ds else None,"telegram_configured":bool(BOT_TOKEN)}
    })

init()
import_seeds()
ensure_seed_data()
threading.Thread(target=tg,daemon=True).start()
