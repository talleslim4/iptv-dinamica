#!/usr/bin/env python3
import json, re, time, unicodedata, urllib.request, urllib.error
from pathlib import Path
from urllib.parse import urljoin, urlsplit, parse_qsl
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "input/canais.m3u"
SOURCES = ROOT / "sources.json"
STATE = ROOT / "state.json"
DOCS = ROOT / "docs"
TIMEOUT = 12
UA = "IPTV-Dinamica/3.0"
SECRET_KEYS = {"token", "access_token", "auth", "authorization", "signature", "sig", "jwt", "api_key", "apikey"}

def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def attr(line, key):
    match = re.search(r'\\b' + re.escape(key) + r'="([^"]*)"', line, re.I)
    return match.group(1).strip() if match else ""

def normalize(value):
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()

def safe_url(url):
    try:
        parts = urlsplit(url)
        return parts.scheme in ("http", "https") and bool(parts.netloc) and not any(
            key.casefold() in SECRET_KEYS and value
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
        )
    except Exception:
        return False

def request_bytes(url, limit=65536):
    if not safe_url(url):
        raise ValueError("URL inválida ou com parâmetro de credencial")
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "*/*", "Range": f"bytes=0-{limit-1}"
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
        return response.status, response.read(limit)

def parse_m3u(text):
    entries, meta, url = [], [], None
    for raw in text.lstrip("\\ufeff").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            if meta:
                entries.append({"meta": meta, "url": url})
            meta, url = [line], None
        elif line.startswith("#"):
            if meta:
                meta.append(line)
        elif meta:
            url = line
            entries.append({"meta": meta, "url": url})
            meta, url = [], None
    if meta:
        entries.append({"meta": meta, "url": None})
    return entries

def check(url):
    if not safe_url(url):
        return False, None, "URL inválida ou contém parâmetro de credencial"
    started = time.monotonic()
    try:
        status, data = request_bytes(url)
        if status not in (200, 206) or not data:
            return False, None, f"HTTP {status}"
        if data.lstrip().lower().startswith((b"<html", b"<!doctype")):
            return False, None, "Resposta HTML"
        if b"#EXTM3U" in data[:1024]:
            playlist = data.decode("utf-8", "replace")
            child = next((line.strip() for line in playlist.splitlines()
                          if line.strip() and not line.lstrip().startswith("#")), None)
            if child:
                child_url = urljoin(url, child)
                child_status, child_data = request_bytes(child_url, 8192)
                if child_status not in (200, 206) or not child_data:
                    return False, None, f"Recurso HLS filho HTTP {child_status}"
        return True, round((time.monotonic() - started) * 1000), "OK"
    except urllib.error.HTTPError as error:
        return False, None, f"HTTP {error.code}"
    except Exception as error:
        return False, None, str(error)[:160]

def main():
    if not INPUT.exists():
        raise SystemExit("Arquivo input/canais.m3u não encontrado.")
    selected = parse_m3u(INPUT.read_text(encoding="utf-8-sig", errors="replace"))
    selected = [item for item in selected if item["meta"] and item["meta"][0].startswith("#EXTINF")]
    if not selected:
        raise SystemExit("input/canais.m3u está vazio. Adicione os canais desejados.")

    overrides = read_json(SOURCES, {})
    previous = read_json(STATE, {})
    output = ["#EXTM3U"]
    new_state, report = {}, []

    for index, item in enumerate(selected):
        name = item["meta"][0].rsplit(",", 1)[-1].strip()
        key = f"{index}:{name}"
        candidates = []
        if item["url"]:
            candidates.append(item["url"])
        extra = overrides.get(name, [])
        if isinstance(extra, list):
            candidates.extend(value.strip() for value in extra if isinstance(value, str) and value.strip())
        old_url = previous.get(key, {}).get("last_good")
        if old_url:
            candidates.append(old_url)
        candidates = list(dict.fromkeys(url for url in candidates if safe_url(url)))

        checks = {}
        with ThreadPoolExecutor(max_workers=min(12, max(1, len(candidates)))) as pool:
            futures = {pool.submit(check, url): url for url in candidates}
            for future in as_completed(futures):
                checks[futures[future]] = future.result()

        working = [(latency, url) for url, (ok, latency, _) in checks.items() if ok]
        working.sort(key=lambda pair: pair[0])
        if working:
            _, chosen = working[0]
            status = "online"
            new_state[key] = {"last_good": chosen}
            output.extend(item["meta"] + [chosen])
        else:
            chosen = None
            status = "sem_fonte_configurada" if not candidates else "offline"
            new_state[key] = {}
            output.extend(item["meta"])

        report.append({
            "name": name,
            "tvg_id": attr(item["meta"][0], "tvg-id"),
            "status": status,
            "selected_url": chosen,
            "candidates": [
                {"url": url, "ok": result[0], "latency_ms": result[1], "detail": result[2]}
                for url, result in checks.items()
            ]
        })

    DOCS.mkdir(exist_ok=True)
    updated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (DOCS / "playlist.m3u").write_text("\\n".join(output) + "\\n", encoding="utf-8")
    (DOCS / "status.json").write_text(json.dumps({
        "updated_at": updated,
        "interval_minutes": 30,
        "source": "somente fontes cadastradas pelo usuário",
        "channels": report
    }, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
    STATE.write_text(json.dumps(new_state, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
    (DOCS / "index.html").write_text(
        '<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>IPTV dinâmica</title>'
        '<body><h1>IPTV dinâmica</h1><p><a href="playlist.m3u">Playlist M3U</a></p>'
        '<p><a href="status.json">Relatório de canais</a></p></body></html>', encoding="utf-8"
    )
    print(f"Verificados {len(report)} canais selecionados; {sum(1 for row in report if row['status'] == 'online')} online.")

if __name__ == "__main__":
    main()
