#!/usr/bin/env python3
"""Build same-origin live-data.json for the Grand Lake community site."""
import json, re, time
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.request import Request, urlopen

UA = "GrandLakeCommunityInfo/1.0 (public community information page)"
def get(url):
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/json,text/html,*/*"})
    with urlopen(req, timeout=20) as response:
        return response.read()

class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]
    def handle_data(self, data):
        if data.strip(): self.parts.append(data.strip())

out = {"generated_at": datetime.now(timezone.utc).isoformat(), "power": {}, "aircraft": {}, "network": {}}

# NB Power publishes regional counts and a refresh timestamp on its outage page.
try:
    raw = get("https://www.nbpower.com/Open/Outages.aspx?lang=en").decode("utf-8", "replace")
    parser = TextOnly(); parser.feed(raw)
    text = re.sub(r"\s+", " ", " ".join(parser.parts))
    region = re.search(r"Kings\s*/\s*Queens\s+(\d+)\s+(\d+)", text, re.I)
    total = re.search(r"Summary\s+(\d+)\s+(\d+)", text, re.I)
    stamp = re.search(r"Outage Data Last Updated at:\s*(.{5,45}?)(?:Emergency Contact|$)", text, re.I)
    if not region or not total:
        raise ValueError("NB Power page layout did not contain the expected regional table")
    out["power"] = {
        "ok": True, "region": "Kings/Queens", "outages": int(region.group(1)),
        "customers": int(region.group(2)), "total_outages": int(total.group(1)),
        "total_customers": int(total.group(2)),
        "source_updated": stamp.group(1).strip() if stamp else "Not supplied"
    }
except Exception as e:
    out["power"] = {"ok": False, "error": str(e)[:180]}

# Airplanes.live feed is fetched server-side to avoid browser CORS restrictions.
try:
    try:
        data = json.loads(get("https://api.airplanes.live/v2/point/46.0/-65.9/50"))
    except Exception:
        data = json.loads(get("https://api.adsb.lol/v2/point/46.0/-65.9/50"))
    aircraft = [a for a in data.get("ac", []) if a.get("lat") is not None and a.get("lon") is not None and float(a.get("seen_pos", 999) or 999) < 90]
    samples = []
    for a in aircraft[:8]:
        callsign = str(a.get("flight") or a.get("hex") or "Aircraft").strip()
        alt = a.get("alt_baro")
        altitude = (str(round(float(alt)/100)*100) + " ft") if isinstance(alt, (int,float)) else ("on ground" if alt == "ground" else "")
        samples.append((callsign + (" · " + altitude if altitude else "")).strip())
    out["aircraft"] = {"ok": True, "count": len(aircraft), "samples": samples, "radius_nm": 50}
except Exception as e:
    out["aircraft"] = {"ok": False, "error": str(e)[:180]}

# Cloudflare's public Statuspage JSON API (not the old v3 RSS URL).
try:
    data = json.loads(get("https://www.cloudflarestatus.com/api/v2/incidents.json"))
    active = [i for i in data.get("incidents", []) if i.get("status") not in ("resolved", "completed")]
    out["network"] = {
        "ok": True,
        "incidents": [{"name": i.get("name","Incident"), "status": i.get("status","unknown")} for i in active[:6]],
        "active_count": len(active)
    }
except Exception as e:
    out["network"] = {"ok": False, "error": str(e)[:180]}

with open("live-data.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
print(json.dumps(out, ensure_ascii=False))
