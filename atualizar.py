#!/usr/bin/env python3
import json, re, time, urllib.request, urllib.error
from pathlib import Path
from urllib.parse import urljoin, urlsplit, parse_qsl
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parent
INP=ROOT/"input/canais.m3u"; SOURCES=ROOT/"sources.json"
STATE=ROOT/"state.json"; DOCS=ROOT/"docs"
TIMEOUT=10; UA="IPTV-Dinamica-HealthCheck/1.0"
SECRET={"token","access_token","auth","authorization","signature","sig","jwt","api_key","apikey","key"}

def readj(p,d):
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return d

def safe(u):
    try: return not any(k.lower() in SECRET and v for k,v in parse_qsl(urlsplit(u).query,keep_blank_values=True))
    except Exception: return False

def get(u,limit=65536):
    req=urllib.request.Request(u,headers={"User-Agent":UA,"Accept":"*/*","Range":f"bytes=0-{limit-1}"})
    with urllib.request.urlopen(req,timeout=TIMEOUT) as r: return r.status,r.read(limit)

def check(u):
    if not u.startswith(("http://","https://")) or not safe(u): return False,None,"URL inválida ou contém credencial"
    t=time.monotonic()
    try:
        status,data=get(u)
        if status not in (200,206) or not data: return False,None,f"HTTP {status}"
        if data.lstrip().lower().startswith((b"<html",b"<!doctype")): return False,None,"Resposta HTML"
        if b"#EXTM3U" in data[:1024]:
            text=data.decode("utf-8","replace")
            child=next((x.strip() for x in text.splitlines() if x.strip() and not x.startswith("#")),None)
            if child:
                s,d=get(urljoin(u,child),8192)
                if s not in (200,206) or not d: return False,None,f"Recurso HLS filho HTTP {s}"
        return True,round((time.monotonic()-t)*1000),"OK"
    except urllib.error.HTTPError as e: return False,None,f"HTTP {e.code}"
    except Exception as e: return False,None,str(e)[:160]

def main():
    if not INP.exists(): raise SystemExit("Crie input/canais.m3u")
    lines=INP.read_text(encoding="utf-8-sig",errors="replace").splitlines()
    overrides=readj(SOURCES,{}); old=readj(STATE,{}); new={}; out=["#EXTM3U"]; report=[]
    jobs=[]; meta=[]; pending=None
    for line in lines:
        line=line.strip()
        if line.startswith("#EXTINF"): pending=[line]
        elif line.startswith("#") and pending is not None: pending.append(line)
        elif line and not line.startswith("#") and pending is not None:
            name=pending[0].rsplit(",",1)[-1].strip()
            urls=list(dict.fromkeys([line]+[x for x in overrides.get(name,[]) if isinstance(x,str) and x.strip()]))
            jobs.append((name,pending,urls)); pending=None
    for i,(name,m,urls) in enumerate(jobs):
        results=[]
        with ThreadPoolExecutor(max_workers=min(12,max(1,len(urls)))) as pool:
            results=list(pool.map(check,urls))
        good=sorted([(lat,u,detail) for u,(ok,lat,detail) in zip(urls,results) if ok],key=lambda x:x[0])
        key=f"{i}:{name}"; prior=old.get(key,{})
        if good:
            lat,chosen,detail=good[0]; status="online"; new[key]={"last_good":chosen}
        else:
            chosen=prior.get("last_good") or (urls[0] if urls else None); status="offline" if urls else "sem_fonte"; new[key]=prior
        if chosen: out.extend(m+[chosen])
        report.append({"name":name,"status":status,"selected_url":chosen,"candidates":[{"url":u,"ok":r[0],"latency_ms":r[1],"detail":r[2]} for u,r in zip(urls,results)]})
    DOCS.mkdir(exist_ok=True); now=datetime.now(timezone.utc).isoformat(timespec="seconds")
    (DOCS/"playlist.m3u").write_text("\n".join(out)+"\n",encoding="utf-8")
    (DOCS/"status.json").write_text(json.dumps({"updated_at":now,"interval_minutes":30,"channels":report},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    STATE.write_text(json.dumps(new,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (DOCS/"index.html").write_text('<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>IPTV dinâmica</title><body><h1>IPTV dinâmica</h1><p><a href="playlist.m3u">Playlist M3U</a></p><p><a href="status.json">Relatório</a></p></body></html>',encoding="utf-8")
    print(f"Verificados {len(report)} canais.")
if __name__=="__main__": main()
