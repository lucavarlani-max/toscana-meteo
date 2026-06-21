# -*- coding: utf-8 -*-
import json, statistics, urllib.request, urllib.parse, time as _time, ssl, re
from pathlib import Path
from collections import defaultdict

out = Path(__file__).parent
gc_path = out / "geocache.json"

# -- SCARICA DATI -----------------------------------------------------------
print("Scarico dati CFR Toscana...")
_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE

_req = urllib.request.Request(
    "https://www.cfr.toscana.it/monitoraggio/stazioni.php?type=termo",
    headers={"User-Agent": "Mozilla/5.0"}
)
with urllib.request.urlopen(_req, context=_ctx, timeout=20) as _r:
    _html = _r.read().decode("utf-8", errors="replace")

_ts = re.search(r'\d{2}/\d{2}/\d{4}[\s]+\d{2}[.:]\d{2}', _html)
timestamp = _ts.group(0).replace(".", ":") if _ts else ""

_arr_match = re.search(r'(\w+)\[0\] = new Array\("TOS\w+","[^"]+\((RADIO|GPRS|GSM)\)', _html)
if not _arr_match:
    raise RuntimeError("Array dati non trovato nell'HTML del CFR")
_arr_name = _arr_match.group(1)

_rows = re.findall(
    rf'{_arr_name}\[\d+\] = new Array\(("TOS.+?"(?:,"[^"]*")*)\)',
    _html
)

def _unquote(s):
    return s.strip().strip('"')

stations = []
for row in _rows:
    c = [_unquote(x) for x in row.split('","')]
    if len(c) < 10 or not c[0].startswith("TOS"):
        continue
    name = c[1]
    if "firenzuola" in name.lower():
        continue
    stations.append({
        "id": c[0], "name": name, "province": c[2], "area": c[3], "altitude": c[5],
        "temp_current": c[6],       "temp_current_time": c[7],
        "temp_min_today": c[8],     "temp_min_today_time": c[9],
        "temp_max_today": c[10],    "temp_max_today_time": c[11],
        "temp_min_yesterday": c[12] if len(c) > 12 else "",
        "temp_min_yesterday_time": c[13] if len(c) > 13 else "",
        "temp_max_yesterday": c[14] if len(c) > 14 else "",
        "temp_max_yesterday_time": c[15] if len(c) > 15 else "",
    })

print(f"Stazioni termo: {len(stations)} | Timestamp: {timestamp}")

def to_float(v):
    try:
        return float(re.sub(r'<[^>]+>', '', str(v)).replace(",", "."))
    except:
        return None

# -- SCARICA DATI PLUVIO ----------------------------------------------------
print("Scarico dati pluviometrici...")
_req2 = urllib.request.Request(
    "https://www.cfr.toscana.it/monitoraggio/stazioni.php?type=pluvio",
    headers={"User-Agent": "Mozilla/5.0"}
)
with urllib.request.urlopen(_req2, context=_ctx, timeout=20) as _r2:
    _html2 = _r2.read().decode("utf-8", errors="replace")

_arr2 = re.search(r'(\w+)\[0\] = new Array\("TOS\w+","[^"]+\((RADIO|GPRS|GSM)\)', _html2)
if not _arr2:
    raise RuntimeError("Array pluvio non trovato")
_arr2_name = _arr2.group(1)
_rows2 = re.findall(
    rf'{_arr2_name}\[\d+\] = new Array\(("TOS.+?"(?:,"[^"]*")*)\)',
    _html2
)

def _strip_html(s):
    return re.sub(r'<[^>]+>', '', s).strip()

pluvio_stations = []
for row in _rows2:
    c = [_unquote(x) for x in row.split('","')]
    if len(c) < 12 or not c[0].startswith("TOS"):
        continue
    pluvio_stations.append({
        "id": c[0], "name": c[1], "province": c[2], "area": c[3],
        "p15m":  _strip_html(c[4]),
        "ph1":   _strip_html(c[5]),
        "ph3":   _strip_html(c[6]),
        "ph6":   _strip_html(c[7]),
        "ph12":  _strip_html(c[8]),
        "ph24":  _strip_html(c[9]),
        "ph36":  _strip_html(c[10]),
        "last_update": c[11],
        "altitude": c[17] if len(c) > 17 else "",
    })

print(f"Stazioni pluvio: {len(pluvio_stations)}")

# -- STATISTICHE PLUVIO -----------------------------------------------------
def pf(s, key):
    return to_float(s.get(key))

# top 10 per pioggia ultime 24h (escludi zero)
pluvio_sorted_24h = sorted(
    [s for s in pluvio_stations if (pf(s,"ph24") or 0) > 0],
    key=lambda s: pf(s,"ph24") or 0, reverse=True
)
top10_pluvio = pluvio_sorted_24h[:10]

max_ph24 = pf(top10_pluvio[0], "ph24") if top10_pluvio else 0
max_ph24_name = top10_pluvio[0]["name"] if top10_pluvio else "N/D"
max_ph1  = max((pf(s,"ph1") or 0 for s in pluvio_stations), default=0)
max_ph1_name = next((s["name"] for s in pluvio_stations if (pf(s,"ph1") or 0) == max_ph1), "N/D")
n_pioggia = len([s for s in pluvio_stations if (pf(s,"ph1") or 0) > 0])

# ranking html pioggia
def build_pluvio_ranking(items):
    if not items:
        return "<p style='color:#888'>Nessuna precipitazione registrata</p>"
    vals = [pf(s,"ph24") or 0 for s in items]
    v_max = max(vals) if vals else 1
    rows = ""
    for rank, s in enumerate(items, 1):
        val = pf(s,"ph24") or 0
        pct = max(round(val / v_max * 100), 4)
        intensity = val / v_max
        r2 = int(30 + 60 * intensity)
        g2 = int(100 + 80 * intensity)
        b2 = int(200)
        bar_color = f"rgb({r2},{g2},{b2})"
        medals = {1:"&#x1F947;", 2:"&#x1F948;", 3:"&#x1F949;"}
        prefix = medals.get(rank, f"{rank}.")
        short = re.sub(r'\s*\((RADIO|GPRS|GSM)\)', '', s["name"])
        prov_badge = f'<span style="background:#eee;color:#555;border-radius:4px;padding:1px 6px;font-size:0.78em;margin-left:6px">{s["province"]}</span>'
        rows += f"""
        <div class="rank-row">
          <span class="rank-num">{prefix}</span>
          <div class="rank-bar-wrap">
            <div class="rank-label">{short}{prov_badge}</div>
            <div class="rank-bar-track">
              <div class="rank-bar" style="width:{pct}%;background:{bar_color}">
                <span class="rank-val">{val} mm</span>
              </div>
            </div>
          </div>
        </div>"""
    return rows

pluvio_ranking_html = build_pluvio_ranking(top10_pluvio)

# tabella pluvio
prov_pluvio = sorted(set(s["province"] for s in pluvio_stations))
prov_pluvio_options = "\n".join(f'<option value="{p}">{p}</option>' for p in prov_pluvio)
pluvio_sorted_table = sorted(pluvio_stations, key=lambda s: pf(s,"ph24") or 0, reverse=True)

pluvio_table_rows = ""
for s in pluvio_sorted_table:
    v24 = pf(s, "ph24") or 0
    v1  = pf(s, "ph1")  or 0
    bg = ""
    if v24 >= 50:   bg = "background:#ffdddd"
    elif v24 >= 20: bg = "background:#fff3cc"
    elif v24 >= 5:  bg = "background:#e8f4fd"
    pluvio_table_rows += f"""
    <tr data-pprov="{s['province']}"
        data-p15m="{s['p15m']}" data-ph1="{s['ph1']}" data-ph3="{s['ph3']}"
        data-ph6="{s['ph6']}" data-ph12="{s['ph12']}" data-ph24="{s['ph24']}"
        data-ph36="{s['ph36']}" data-pname="{s['name']}" data-pprov2="{s['province']}"
        style="{bg}">
      <td>{s['name'].replace(' (RADIO)','').replace(' (GPRS)','').replace(' (GSM)','')}</td>
      <td>{s['province']}</td>
      <td>{s['area']}</td>
      <td>{s['altitude']} m</td>
      <td style="text-align:center"><b>{s['p15m']}</b></td>
      <td style="text-align:center">{s['ph1']}</td>
      <td style="text-align:center">{s['ph3']}</td>
      <td style="text-align:center">{s['ph6']}</td>
      <td style="text-align:center">{s['ph12']}</td>
      <td style="text-align:center"><b>{s['ph24']}</b></td>
      <td style="text-align:center">{s['ph36']}</td>
      <td style="text-align:center;font-size:0.82em">{s['last_update']}</td>
    </tr>"""

# -- STATISTICHE ------------------------------------------------------------
temps_curr = [to_float(s["temp_current"]) for s in stations if to_float(s["temp_current"]) is not None]
temps_max  = [to_float(s["temp_max_today"]) for s in stations if to_float(s["temp_max_today"]) is not None]
temps_min  = [to_float(s["temp_min_today"]) for s in stations if to_float(s["temp_min_today"]) is not None]

avg_curr  = round(statistics.mean(temps_curr), 1)
max_curr  = max(temps_curr); min_curr = min(temps_curr)
max_today = max(temps_max);  min_today = min(temps_min)

s_max  = next(s for s in stations if to_float(s["temp_max_today"]) == max_today)
s_min  = next(s for s in stations if to_float(s["temp_min_today"]) == min_today)
s_hot  = next(s for s in stations if to_float(s["temp_current"]) == max_curr)
s_cold = next(s for s in stations if to_float(s["temp_current"]) == min_curr)

# -- GRAFICI ----------------------------------------------------------------
fasce = {"< 10C": 0, "10-15C": 0, "15-20C": 0, "20-25C": 0, "25-30C": 0, "30-35C": 0, "> 35C": 0}
for s in stations:
    tc = to_float(s["temp_current"])
    if tc is None: continue
    if tc < 10:   fasce["< 10C"] += 1
    elif tc < 15: fasce["10-15C"] += 1
    elif tc < 20: fasce["15-20C"] += 1
    elif tc < 25: fasce["20-25C"] += 1
    elif tc < 30: fasce["25-30C"] += 1
    elif tc < 35: fasce["30-35C"] += 1
    else:         fasce["> 35C"] += 1

top15_max = sorted([(s["name"], to_float(s["temp_max_today"])) for s in stations if to_float(s["temp_max_today"]) is not None],
                   key=lambda x: x[1], reverse=True)[:15]
top30_max = sorted([(s["name"], to_float(s["temp_max_today"])) for s in stations if to_float(s["temp_max_today"]) is not None],
                   key=lambda x: x[1], reverse=True)[:30]
top15_min = sorted([(s["name"], to_float(s["temp_min_today"])) for s in stations if to_float(s["temp_min_today"]) is not None],
                   key=lambda x: x[1])[:15]

prov_temps = defaultdict(list)
for s in stations:
    tc = to_float(s["temp_current"])
    if tc is not None:
        prov_temps[s["province"]].append(tc)
prov_avg = {p: round(sum(v)/len(v), 1) for p, v in sorted(prov_temps.items())}

# -- GEOCODING --------------------------------------------------------------
_coord_cache = json.loads(gc_path.read_text(encoding="utf-8")) if gc_path.exists() else {}

def geocode(name):
    if name in _coord_cache:
        return _coord_cache[name]
    clean = re.sub(r'\s*\((RADIO|GPRS|GSM|XBOW)\)', '', name)
    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(clean+', Toscana, Italy')}&format=json&limit=1&countrycodes=it"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ToscanaMeteo/1.0"})
        with urllib.request.urlopen(req, context=_ctx, timeout=8) as r:
            data = json.loads(r.read())
        if data:
            coords = [float(data[0]["lat"]), float(data[0]["lon"])]
            _coord_cache[name] = coords
            gc_path.write_text(json.dumps(_coord_cache, indent=2, ensure_ascii=False), encoding="utf-8")
            return coords
    except Exception as e:
        print(f"  Geocoding errore {name}: {e}")
    return None

map_stations = []
print(f"Geocoding top 30 stazioni...")
for rank, (name, _) in enumerate(top30_max, 1):
    s = next((x for x in stations if x["name"] == name), None)
    if not s: continue
    coords = geocode(name)
    if coords:
        map_stations.append({
            "name": name, "province": s["province"],
            "temp_max": s["temp_max_today"], "temp_min": s["temp_min_today"],
            "temp_current": s["temp_current"], "rank": rank,
            "lat": coords[0], "lon": coords[1]
        })
    _time.sleep(0.35)

print(f"  -> {len(map_stations)}/30 geocodificate")
map_stations_json = json.dumps(map_stations)

# -- RANKING HTML -----------------------------------------------------------
def build_ranking_html(items, is_hot):
    vals = [v for _, v in items]
    v_min, v_max = min(vals), max(vals)
    span = v_max - v_min if v_max != v_min else 1
    rows = ""
    for rank, (name, val) in enumerate(items, 1):
        pct = round((val - v_min) / span * 100)
        if is_hot:
            bar_color = f"rgb({int(180+75*pct/100)},{int(120-100*pct/100)},30)"
        else:
            bar_color = f"rgb(30,{int(80+80*(1-pct/100))},{int(180+75*(1-pct/100))})"
        medals = {1: "&#x1F947;", 2: "&#x1F948;", 3: "&#x1F949;"}
        prefix = medals.get(rank, f"{rank}.")
        short = re.sub(r'\s*\((RADIO|GPRS|GSM)\)', '', name)
        prov = next((s["province"] for s in stations if s["name"] == name), "")
        prov_badge = f'<span style="background:#eee;color:#555;border-radius:4px;padding:1px 6px;font-size:0.78em;margin-left:6px">{prov}</span>'
        rows += f"""
        <div class="rank-row" title="{name}: {val}°C">
          <span class="rank-num">{prefix}</span>
          <div class="rank-bar-wrap">
            <div class="rank-label">{short}{prov_badge}</div>
            <div class="rank-bar-track">
              <div class="rank-bar" style="width:{max(pct,4)}%;background:{bar_color}">
                <span class="rank-val">{val}&deg;C</span>
              </div>
            </div>
          </div>
        </div>"""
    return rows

top15_max_html = build_ranking_html(top15_max, is_hot=True)
top15_min_html = build_ranking_html(top15_min, is_hot=False)

# -- TABELLA ----------------------------------------------------------------
def row_color(t):
    if t is None: return ""
    if t >= 35: return "#ff4444"
    if t >= 30: return "#ff8800"
    if t >= 25: return "#ffcc00"
    if t >= 15: return "#88cc44"
    if t >= 5:  return "#44aaff"
    return "#0044cc"

provinces_sorted = sorted(set(s["province"] for s in stations))
prov_options = "\n".join(f'<option value="{p}">{p}</option>' for p in provinces_sorted)
stations_sorted = sorted(stations, key=lambda s: to_float(s.get("temp_max_today")) or -999, reverse=True)
table_rows = ""
for s in stations_sorted:
    tc = to_float(s["temp_current"])
    color = row_color(tc)
    badge = f'<span style="background:{color};color:#fff;padding:2px 7px;border-radius:12px;font-weight:bold">{tc}&deg;C</span>' if tc is not None else "N/D"
    tmin_y = to_float(s['temp_min_yesterday'])
    tmax_y = to_float(s['temp_max_yesterday'])
    tmin_t = to_float(s['temp_min_today'])
    tmax_t = to_float(s['temp_max_today'])
    table_rows += f"""
    <tr data-prov="{s['province']}"
        data-curr="{tc if tc is not None else ''}"
        data-tmin="{tmin_t if tmin_t is not None else ''}"
        data-tmax="{tmax_t if tmax_t is not None else ''}"
        data-tmin-y="{tmin_y if tmin_y is not None else ''}"
        data-tmax-y="{tmax_y if tmax_y is not None else ''}"
        data-name="{s['name']}" data-prov2="{s['province']}"
        data-alt="{s['altitude']}">
      <td>{s['name'].replace(' (RADIO)','').replace(' (GPRS)','').replace(' (GSM)','')}</td>
      <td>{s['province']}</td>
      <td>{s['area']}</td>
      <td>{s['altitude']}</td>
      <td style="text-align:center">{badge}</td>
      <td>{s['temp_min_today']}&deg;C<br><small>{s['temp_min_today_time']}</small></td>
      <td>{s['temp_max_today']}&deg;C<br><small>{s['temp_max_today_time']}</small></td>
      <td>{s['temp_min_yesterday'] if s['temp_min_yesterday'] else 'N/D'}&deg;C<br><small>{s['temp_min_yesterday_time']}</small></td>
      <td>{s['temp_max_yesterday'] if s['temp_max_yesterday'] else 'N/D'}&deg;C<br><small>{s['temp_max_yesterday_time']}</small></td>
    </tr>"""

chart_fasce_labels = json.dumps(list(fasce.keys()))
chart_fasce_data   = json.dumps(list(fasce.values()))
chart_prov_labels  = json.dumps(list(prov_avg.keys()))
chart_prov_data    = json.dumps(list(prov_avg.values()))
prov_vals = list(prov_avg.values())
prov_min  = round(min(prov_vals) - 1)
prov_max  = round(max(prov_vals) + 1)

from datetime import datetime, timezone
generated_at = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

# -- HTML -------------------------------------------------------------------
html = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Temperature Toscana - {timestamp}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9/dist/leaflet.js"></script>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: Arial, sans-serif; background: #f4f6f9; color: #222; margin: 0; padding: 16px; }}
  h1 {{ color: #1F4E79; font-size: clamp(1.3em, 4vw, 2em); margin-bottom: 4px; }}
  h2 {{ color: #2E75B6; border-bottom: 2px solid #2E75B6; padding-bottom: 4px; margin-top: 32px; font-size: clamp(1em, 3vw, 1.4em); }}
  /* stat cards */
  .stats {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 16px 0; }}
  .stat-card {{ background: #fff; border-radius: 10px; padding: 14px 18px; box-shadow: 0 2px 8px #0002; flex: 1 1 140px; }}
  .stat-card .val {{ font-size: clamp(1.4em, 4vw, 2em); font-weight: bold; color: #1F4E79; }}
  .stat-card .lbl {{ font-size: 0.82em; color: #666; }}
  /* grafici */
  .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0; }}
  .chart-box {{ background: #fff; border-radius: 10px; padding: 16px; box-shadow: 0 2px 8px #0002; }}
  /* mappa */
  #map {{ height: 420px; border-radius: 12px; box-shadow: 0 2px 10px #0003; margin: 16px 0; }}
  .map-legend {{ background: #fff; padding: 8px 12px; border-radius: 8px; box-shadow: 0 1px 6px #0002; font-size: 0.82em; line-height: 2; }}
  /* ranking */
  .ranking-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0; }}
  .ranking-box {{ background: #fff; border-radius: 12px; padding: 18px 20px; box-shadow: 0 2px 10px #0002; }}
  .ranking-box h3 {{ margin: 0 0 14px; font-size: 0.98em; color: #333; }}
  .rank-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 9px; }}
  .rank-row:hover .rank-bar {{ filter: brightness(1.12); }}
  .rank-num {{ min-width: 30px; text-align: center; font-size: 0.95em; }}
  .rank-bar-wrap {{ flex: 1; min-width: 0; }}
  .rank-label {{ font-size: 0.78em; color: #444; margin-bottom: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .rank-bar-track {{ background: #f0f0f0; border-radius: 6px; height: 22px; }}
  .rank-bar {{ height: 100%; border-radius: 6px; display: flex; align-items: center; justify-content: flex-end; padding-right: 7px; transition: width 0.3s; min-width: 44px; }}
  .rank-val {{ color: #fff; font-weight: bold; font-size: 0.82em; text-shadow: 0 1px 2px #0005; }}
  /* tabella */
  .table-wrap {{ width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; }}
  table {{ border-collapse: collapse; width: 100%; min-width: 600px; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px #0002; margin-bottom: 30px; }}
  th {{ background: #1F4E79; color: #fff; padding: 10px; text-align: left; white-space: nowrap; }}
  th.sortable, th.psortable {{ cursor: pointer; user-select: none; }}
  th.sortable:hover, th.psortable:hover {{ background: #2563a8; }}
  th.sort-asc .sort-icon::after, th.psort-asc .sort-icon::after {{ content: ' ▲'; }}
  th.sort-desc .sort-icon::after, th.psort-desc .sort-icon::after {{ content: ' ▼'; }}
  th.sort-asc .sort-icon, th.sort-desc .sort-icon,
  th.psort-asc .sort-icon, th.psort-desc .sort-icon {{ opacity: 0; }}
  .sort-icon {{ opacity: 0.4; font-size: 0.8em; }}
  td {{ padding: 7px 9px; border-bottom: 1px solid #eee; vertical-align: middle; font-size: 0.9em; }}
  tr:hover td {{ background: #f0f7ff; }}
  .footer {{ font-size: 0.8em; color: #888; margin-top: 30px; }}
  input#search {{ padding: 8px 12px; border: 1px solid #ccc; border-radius: 6px; font-size: 1em; width: 100%; max-width: 260px; }}
  select#provFilter {{ padding: 8px 12px; border: 1px solid #ccc; border-radius: 6px; font-size: 1em; }}
  .filter-bar {{ display: flex; gap: 10px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }}
  /* responsive */
  @media (max-width: 650px) {{
    .charts {{ grid-template-columns: 1fr; }}
    .ranking-grid {{ grid-template-columns: 1fr; }}
    #map {{ height: 320px; }}
    .stat-card {{ flex: 1 1 120px; }}
    body {{ padding: 10px; }}
  }}
</style>
</head>
<body>
<h1>&#x1F321; Temperature Stazioni Toscana</h1>
<p><strong>Dati CFR:</strong> {timestamp} &nbsp;|&nbsp; <strong>Stazioni:</strong> {len(stations)} &nbsp;|&nbsp; <em>Aggiornato automaticamente ogni 30 min</em></p>

<h2>&#x1F4CA; Statistiche</h2>
<div class="stats">
  <div class="stat-card"><div class="val">{avg_curr}&deg;C</div><div class="lbl">Media temp. attuale</div></div>
  <div class="stat-card"><div class="val" style="color:#ff4444">{max_curr}&deg;C</div><div class="lbl">Temp. max attuale<br><small>{s_hot['name']} ({s_hot['province']})</small></div></div>
  <div class="stat-card"><div class="val" style="color:#0066cc">{min_curr}&deg;C</div><div class="lbl">Temp. min attuale<br><small>{s_cold['name']} ({s_cold['province']})</small></div></div>
  <div class="stat-card"><div class="val" style="color:#ff6600">{max_today}&deg;C</div><div class="lbl">Tmax giornaliera<br><small>{s_max['name']} ({s_max['province']})</small></div></div>
  <div class="stat-card"><div class="val" style="color:#0088ff">{min_today}&deg;C</div><div class="lbl">Tmin giornaliera<br><small>{s_min['name']} ({s_min['province']})</small></div></div>
</div>

<h2>&#x1F4C8; Grafici</h2>
<div class="charts">
  <div class="chart-box">
    <h3 style="margin-top:0">Distribuzione temperature attuali</h3>
    <canvas id="chartFasce"></canvas>
  </div>
  <div class="chart-box">
    <h3 style="margin-top:0">Temperatura media per provincia</h3>
    <canvas id="chartProv"></canvas>
  </div>
</div>

<h2>&#x1F5FA; Mappa 30 stazioni piu calde oggi</h2>
<div id="map"></div>

<div class="ranking-grid">
  <div class="ranking-box">
    <h3>&#x1F525; Top 15 &mdash; Tmax piu alta oggi</h3>
    {top15_max_html}
  </div>
  <div class="ranking-box">
    <h3>&#x2744; Top 15 &mdash; Tmin piu bassa oggi</h3>
    {top15_min_html}
  </div>
</div>

<h2>&#x1F4CB; Tutte le stazioni</h2>
<div class="filter-bar">
  <input id="search" type="text" placeholder="Cerca stazione..." oninput="applyFilters()">
  <select id="provFilter" onchange="applyFilters()">
    <option value="">Tutte le province</option>
    {prov_options}
  </select>
  <span id="countLabel" style="color:#666;font-size:0.9em"></span>
</div>
<div class="table-wrap">
<table id="stTable">
  <thead><tr>
    <th class="sortable" data-col="name">Stazione <span class="sort-icon">⇅</span></th>
    <th class="sortable" data-col="prov2">Prov. <span class="sort-icon">⇅</span></th>
    <th>Area</th>
    <th class="sortable" data-col="alt">Quota <span class="sort-icon">⇅</span></th>
    <th class="sortable" data-col="curr">Temp Att. <span class="sort-icon">⇅</span></th>
    <th class="sortable" data-col="tmin">Tmin Oggi <span class="sort-icon">⇅</span></th>
    <th class="sortable" data-col="tmax">Tmax Oggi <span class="sort-icon">⇅</span></th>
    <th class="sortable" data-col="tmin-y">Tmin Ieri <span class="sort-icon">⇅</span></th>
    <th class="sortable" data-col="tmax-y">Tmax Ieri <span class="sort-icon">⇅</span></th>
  </tr></thead>
  <tbody>{table_rows}</tbody>
</table>
</div>

<h2>&#x1F327; Precipitazioni</h2>
<div class="stats">
  <div class="stat-card"><div class="val" style="color:#1a6abf">{max_ph24} mm</div><div class="lbl">Max pioggia 24h<br><small>{max_ph24_name.replace(' (RADIO)','').replace(' (GPRS)','')}</small></div></div>
  <div class="stat-card"><div class="val" style="color:#1a6abf">{max_ph1} mm</div><div class="lbl">Max pioggia ultima ora<br><small>{max_ph1_name.replace(' (RADIO)','').replace(' (GPRS)','')}</small></div></div>
  <div class="stat-card"><div class="val">{n_pioggia}</div><div class="lbl">Stazioni con pioggia<br><small>nell'ultima ora</small></div></div>
  <div class="stat-card"><div class="val">{len(pluvio_stations)}</div><div class="lbl">Stazioni pluviometriche<br><small>totali Toscana</small></div></div>
</div>

<div class="ranking-box" style="margin:20px 0">
  <h3>&#x1F4A7; Top 10 stazioni &mdash; Pioggia cumulata 24h</h3>
  {pluvio_ranking_html}
</div>

<h3 style="color:#2E75B6;margin-top:28px">&#x1F4CB; Tabella stazioni pluviometriche</h3>
<p style="font-size:0.85em;color:#666">Valori in mm &mdash; <span style="background:#e8f4fd;padding:2px 6px;border-radius:4px">&ge;5mm</span> <span style="background:#fff3cc;padding:2px 6px;border-radius:4px">&ge;20mm</span> <span style="background:#ffdddd;padding:2px 6px;border-radius:4px">&ge;50mm</span></p>
<div class="filter-bar">
  <input id="searchPluvio" type="text" placeholder="Cerca stazione..." oninput="applyPluvioFilters()">
  <select id="provPluvioFilter" onchange="applyPluvioFilters()">
    <option value="">Tutte le province</option>
    {prov_pluvio_options}
  </select>
  <span id="countPluvioLabel" style="color:#666;font-size:0.9em"></span>
</div>
<div class="table-wrap">
<table id="pluvioTable">
  <thead><tr>
    <th class="psortable" data-col="pname">Stazione <span class="sort-icon">⇅</span></th>
    <th class="psortable" data-col="pprov2">Prov. <span class="sort-icon">⇅</span></th>
    <th>Area</th>
    <th>Quota</th>
    <th class="psortable" data-col="p15m">&#916;15' <span class="sort-icon">⇅</span></th>
    <th class="psortable" data-col="ph1">&#916;1h <span class="sort-icon">⇅</span></th>
    <th class="psortable" data-col="ph3">&#916;3h <span class="sort-icon">⇅</span></th>
    <th class="psortable" data-col="ph6">&#916;6h <span class="sort-icon">⇅</span></th>
    <th class="psortable" data-col="ph12">&#916;12h <span class="sort-icon">⇅</span></th>
    <th class="psortable" data-col="ph24">&#916;24h <span class="sort-icon">⇅</span></th>
    <th class="psortable" data-col="ph36">&#916;36h <span class="sort-icon">⇅</span></th>
    <th>Ultimo dato</th>
  </tr></thead>
  <tbody>{pluvio_table_rows}</tbody>
</table>
</div>

<div class="footer">
  Fonte: <a href="https://www.cfr.toscana.it/monitoraggio/stazioni.php?type=termo">Centro Funzionale Regione Toscana</a>
  &mdash; Generato il {generated_at}
</div>

<script>
function applyFilters() {{
  const q = document.getElementById('search').value.toLowerCase();
  const prov = document.getElementById('provFilter').value;
  let visible = 0;
  document.querySelectorAll('#stTable tbody tr').forEach(r => {{
    const ok = (!q || r.innerText.toLowerCase().includes(q)) && (!prov || r.dataset.prov === prov);
    r.style.display = ok ? '' : 'none';
    if (ok) visible++;
  }});
  document.getElementById('countLabel').textContent = visible + ' stazioni';
}}
applyFilters();

// Ordinamento tabella
let sortCol = 'tmax', sortDir = -1;
function sortTable(col) {{
  if (sortCol === col) {{ sortDir *= -1; }} else {{ sortCol = col; sortDir = -1; }}
  document.querySelectorAll('#stTable th.sortable').forEach(th => {{
    th.classList.remove('sort-asc','sort-desc');
    if (th.dataset.col === col) th.classList.add(sortDir === 1 ? 'sort-asc' : 'sort-desc');
  }});
  const tbody = document.querySelector('#stTable tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  // converti col (es. "tmin-y") in chiave dataset camelCase ("tminY")
  const key = col.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
  rows.sort((a, b) => {{
    const av = a.dataset[key] ?? '';
    const bv = b.dataset[key] ?? '';
    const an = parseFloat(av), bn = parseFloat(bv);
    if (!isNaN(an) && !isNaN(bn)) return (an - bn) * sortDir;
    return av.localeCompare(bv, 'it') * sortDir;
  }});
  rows.forEach(r => tbody.appendChild(r));
}}
document.querySelectorAll('#stTable th.sortable').forEach(th => {{
  th.addEventListener('click', () => sortTable(th.dataset.col));
}});
sortTable('tmax');

// -- FILTRI E SORT PLUVIO --------------------------------------------------
function applyPluvioFilters() {{
  const q = document.getElementById('searchPluvio').value.toLowerCase();
  const prov = document.getElementById('provPluvioFilter').value;
  let visible = 0;
  document.querySelectorAll('#pluvioTable tbody tr').forEach(r => {{
    const ok = (!q || r.innerText.toLowerCase().includes(q)) && (!prov || r.dataset.pprov === prov);
    r.style.display = ok ? '' : 'none';
    if (ok) visible++;
  }});
  document.getElementById('countPluvioLabel').textContent = visible + ' stazioni';
}}
applyPluvioFilters();

let psortCol = 'ph24', psortDir = -1;
function sortPluvio(col) {{
  if (psortCol === col) {{ psortDir *= -1; }} else {{ psortCol = col; psortDir = -1; }}
  document.querySelectorAll('#pluvioTable th.psortable').forEach(th => {{
    th.classList.remove('psort-asc','psort-desc');
    if (th.dataset.col === col) th.classList.add(psortDir === 1 ? 'psort-asc' : 'psort-desc');
  }});
  const tbody = document.querySelector('#pluvioTable tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  const key = col.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
  rows.sort((a, b) => {{
    const av = a.dataset[key] ?? '';
    const bv = b.dataset[key] ?? '';
    const an = parseFloat(av), bn = parseFloat(bv);
    if (!isNaN(an) && !isNaN(bn)) return (an - bn) * psortDir;
    return av.localeCompare(bv, 'it') * psortDir;
  }});
  rows.forEach(r => tbody.appendChild(r));
}}
document.querySelectorAll('#pluvioTable th.psortable').forEach(th => {{
  th.addEventListener('click', () => sortPluvio(th.dataset.col));
}});
sortPluvio('ph24');

const mapStations = {map_stations_json};
const map = L.map('map').setView([43.5, 11.1], 7);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  attribution: '&copy; OpenStreetMap contributors', maxZoom: 17
}}).addTo(map);

function hotColor(rank) {{
  const t = (rank - 1) / 29;
  return `rgb(220,${{Math.round(40 + 130 * t)}},0)`;
}}
mapStations.forEach(s => {{
  const medals = {{1:'&#x1F947;',2:'&#x1F948;',3:'&#x1F949;'}};
  const prefix = medals[s.rank] || `#${{s.rank}}`;
  const color = hotColor(s.rank);
  const icon = L.divIcon({{
    className: '',
    html: `<div style="background:${{color}};color:#fff;border:2.5px solid rgba(0,0,0,0.25);border-radius:50%;width:42px;height:42px;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:11px;box-shadow:0 2px 8px #0006;cursor:pointer;line-height:1.1;text-align:center">${{s.temp_max}}&deg;<br><span style="font-size:9px;opacity:0.9">#${{s.rank}}</span></div>`,
    iconSize: [42, 42], iconAnchor: [21, 21], popupAnchor: [0, -23]
  }});
  L.marker([s.lat, s.lon], {{icon}}).addTo(map)
   .bindPopup(`<b>${{prefix}} ${{s.name}}</b> (${{s.province}})<br>&#x1F321; Attuale: <b>${{s.temp_current}}&deg;C</b><br>&#x1F53A; Tmax: <b style="color:#d63000">${{s.temp_max}}&deg;C</b><br>&#x1F53B; Tmin: <b>${{s.temp_min}}&deg;C</b><br><br><a href="https://www.cfr.toscana.it/monitoraggio/stazioni.php?type=termo" target="_blank">&#x1F517; CFR Toscana</a>`, {{maxWidth:240}});
}});

const legend = L.control({{position:'bottomright'}});
legend.onAdd = () => {{
  const d = L.DomUtil.create('div','map-legend');
  d.innerHTML = '<b>Top 30 stazioni piu calde</b><br>'
    + '<span style="background:rgb(220,40,0);display:inline-block;width:14px;height:14px;border-radius:50%;margin-right:6px;vertical-align:middle"></span>#1<br>'
    + '<span style="background:rgb(220,170,0);display:inline-block;width:14px;height:14px;border-radius:50%;margin-right:6px;vertical-align:middle"></span>#30';
  return d;
}};
legend.addTo(map);

new Chart(document.getElementById('chartFasce'), {{
  type: 'doughnut',
  data: {{
    labels: {chart_fasce_labels},
    datasets: [{{ data: {chart_fasce_data},
      backgroundColor: ['#0044cc','#44aaff','#88cc44','#ffcc00','#ff8800','#ff4444','#aa0000'],
      borderWidth: 2 }}]
  }},
  options: {{ plugins: {{ legend: {{ position: 'right' }} }} }}
}});

new Chart(document.getElementById('chartProv'), {{
  type: 'bar',
  data: {{
    labels: {chart_prov_labels},
    datasets: [{{ label: 'Temp media (grC)', data: {chart_prov_data},
      backgroundColor: 'rgba(30,100,200,0.7)', borderColor: '#1F4E79', borderWidth: 1 }}]
  }},
  options: {{
    scales: {{ y: {{ suggestedMin: {prov_min}, suggestedMax: {prov_max}, ticks: {{ stepSize: 0.5 }} }} }},
    plugins: {{ legend: {{ display: false }} }}
  }}
}});
</script>
</body>
</html>"""

(out / "index.html").write_text(html, encoding="utf-8")
print(f"index.html salvato | {len(stations)} stazioni | Tmax: {max_today}C ({s_max['name']})")
