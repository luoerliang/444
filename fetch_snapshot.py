import json,re,requests
from bs4 import BeautifulSoup
from datetime import datetime,timedelta
URLS=['https://macaujc.com/open_video3/','http://macaujc.com/open_video3/']
H={'User-Agent':'Mozilla/5.0','Cache-Control':'no-cache','Pragma':'no-cache'}
def infer(issue):
 d=datetime.strptime(issue[:8],'%Y%m%d'); return (d+timedelta(minutes=(int(issue[8:])-1)*3)).strftime('%Y-%m-%d %H:%M:%S')
def parse(html):
 t=BeautifulSoup(html,'html.parser').get_text('\n',strip=True); issues=list(re.finditer(r'20\d{9}',t)); out=[]
 combo=re.compile(r'(\d{1,2})\D{0,18}(\d{1,2})\D{0,18}(\d{1,2})\D{0,18}(\d{1,2})\D{0,18}(\d{1,2})\D{0,18}(\d{1,2})\D{0,25}\+\D{0,8}(\d{1,2})')
 for i,m in enumerate(issues):
  w=t[m.end():(issues[i+1].start() if i+1<len(issues) else m.end()+2500)]; c=combo.search(w)
  if c: out.append({'issue':m.group(),'open_time':infer(m.group()),'main':[f'{int(c.group(j)):02d}' for j in range(1,7)],'special':f'{int(c.group(7)):02d}'})
 d={x['issue']:x for x in out}; return sorted(d.values(),key=lambda x:x['issue'],reverse=True)
for u in URLS:
 try:
  r=requests.get(u+'?cb=1',headers=H,timeout=20); r.raise_for_status(); ds=parse(r.text)
  if ds:
   json.dump({'updated_at':datetime.utcnow().isoformat()+'Z','draws':ds[:100]},open('data/draws.json','w'),ensure_ascii=False,indent=2); print('OK',u,ds[0]['issue']); break
 except Exception as e: print('ERR',u,e)
else: raise SystemExit('source unavailable')
