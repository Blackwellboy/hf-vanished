#!/usr/bin/env python3
"""Bounded Pirate Face recovery probe + FrostByte handoff feed."""
from __future__ import annotations

import html, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STATE, EVENTS = DATA / "state.json", DATA / "events.json"
CACHE, STATUS = DATA / "integrations.json", DATA / "status.json"
PF = "https://pirateface.co"
FROST = "https://blackfrostai.com/frostbyte"
FROST_REPO = "https://github.com/Blackfrost-AI/FrostByte-App"
UA = "hf-vanished/0.2 (+https://github.com/Blackwellboy/hf-vanished; recovery probe)"
EVENT_LIMIT = int(os.getenv("PIRATEFACE_EVENT_PROBE_LIMIT", "30"))
ROTATE_LIMIT = int(os.getenv("PIRATEFACE_ROTATING_PROBE_LIMIT", "20"))
BOOTSTRAP_LIMIT = int(os.getenv("PIRATEFACE_BOOTSTRAP_PROBE_LIMIT", "220"))
STALE_H = int(os.getenv("PIRATEFACE_STALE_HOURS", "72"))
TIMEOUT = int(os.getenv("PIRATEFACE_TIMEOUT", "8"))


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read(path: Path, default: Any) -> Any:
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return default


def write(path: Path, obj: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def age_hours(ts: str | None) -> float | None:
    if not ts: return None
    try: dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError: return None
    return (datetime.now(timezone.utc) - dt).total_seconds() / 3600


def pf_url(mid: str) -> str:
    return f"{PF}/{urllib.parse.quote(mid, safe='/')}"


def fetch_html(url: str) -> tuple[int | None, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return None, repr(e)


def plain(raw: str) -> str:
    raw = re.sub(r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>", " ", raw, flags=re.I | re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()


def probe(mid: str) -> dict[str, Any]:
    url, checked = pf_url(mid), now()
    code, raw = fetch_html(url)
    if code == 404: return {"url": url, "status": "not_indexed", "checked_at": checked, "http": 404}
    if code != 200: return {"url": url, "status": "unknown", "checked_at": checked, "http": code, "error": True}
    text, low = plain(raw), plain(raw).lower()
    if "availability & integrity" not in low and mid.lower() not in low:
        return {"url": url, "status": "not_indexed", "checked_at": checked, "http": 200}
    match = re.search(r"magnet:\?[^\"'<>\s]+", html.unescape(raw), re.I)
    magnet = html.unescape(match.group(0)).replace("&amp;", "&") if match else None
    torrent = bool(magnet or "hf + p2p" in low or "a pirate face magnet has been created" in low)
    waiting = "no pirate face magnet has been created yet" in low or "hf only" in low
    seed = re.search(r"\b([0-9][0-9,]*)\s+seeders?\b", text, re.I)
    out = {"url": url, "status": "torrent" if torrent else ("indexed" if waiting else "unknown"), "checked_at": checked, "http": 200}
    if magnet: out["magnet"] = magnet
    if seed: out["seeders"] = int(seed.group(1).replace(",", ""))
    return out


def eligibility(value: Any) -> str:
    if value is None or str(value).strip() == "": return "UNKNOWN"
    lic = str(value).strip().lower().replace("_", "-")
    allowed = {"mit", "mit license", "apache-2.0", "apache 2.0", "apache license 2.0", "apache-2.0 license"}
    return "ELIGIBLE" if lic in allowed else "NOT_CURRENTLY_LISTED"


def lifecycle(s: dict) -> str:
    vis = s.get("visibility")
    if s.get("disabled") or vis in ("disabled", "deleted", "private"): return "VANISHED"
    if vis == "public" and s.get("gated") not in (False, None, "", 0): return "RESTRICTED"
    if vis == "public": return "AVAILABLE"
    return "UNKNOWN"


def preservation(life: str, p: dict, elig: str) -> str:
    st = p.get("status")
    if st == "torrent": return "RESCUED" if life == "VANISHED" else "PROTECTED"
    if st in ("indexed", "not_indexed"):
        if life == "VANISHED": return "NO_KNOWN_COPY"
        return "UNMIRRORED" if elig == "NOT_CURRENTLY_LISTED" else "AT_RISK"
    return "UNKNOWN"


def choose(state: dict, events: list[dict], cache: dict, cursor: int) -> tuple[list[str], int]:
    picked, seen = [], set()
    def add(mid: str) -> None:
        if mid and mid not in seen: seen.add(mid); picked.append(mid)
    event_ids = []
    for e in events:
        mid = str(e.get("id") or "")
        c = cache.get(mid) or {}
        if mid and (not c.get("status") or (age_hours(c.get("checked_at")) or 999) >= 6): event_ids.append(mid)
    for mid in event_ids[:EVENT_LIMIT]: add(mid)
    ids = sorted(str(x) for x in state.get("models", {}) if x)
    if ids:
        # Warm a new install quickly so the public site does not spend days with
        # UNKNOWN preservation states. Once every current watched model has a
        # cached PF observation, revert to the cheap rotating maintenance pass.
        coverage_incomplete = any(mid not in cache for mid in ids)
        rotation_budget = BOOTSTRAP_LIMIT if coverage_incomplete else ROTATE_LIMIT
        total_budget = EVENT_LIMIT + rotation_budget
        i, scanned = cursor % len(ids), 0
        while scanned < len(ids) and len(picked) < total_budget:
            mid, c = ids[i], cache.get(ids[i]) or {}
            if not c.get("status") or (age_hours(c.get("checked_at")) or 999) >= STALE_H: add(mid)
            i, scanned = (i + 1) % len(ids), scanned + 1
        cursor = i
    return picked, cursor


def build(state: dict, events: list[dict], pf_cache: dict) -> dict:
    event_by_id = {}
    for e in events:
        mid = str(e.get("id") or "")
        if mid and mid not in event_by_id: event_by_id[mid] = e
    models, counts = {}, {k: 0 for k in ("watched","available","restricted","vanished","protected","rescued","at_risk","no_known_copy")}
    for mid, s in state.get("models", {}).items():
        life = lifecycle(s)
        lic = s.get("license")
        elig = eligibility(lic)
        p = pf_cache.get(mid) or {"url": pf_url(mid), "status": "unknown"}
        pres = preservation(life, p, elig)
        handoff = "magnet" if p.get("magnet") else ("huggingface" if life in ("AVAILABLE","RESTRICTED") else None)
        lp = {
            "checked_at": s.get("last_public_checked_at"), "sha": s.get("sha"), "license": lic,
            "pipeline_tag": s.get("pipeline_tag"), "library_name": s.get("library_name"),
            "file_count": s.get("file_count"), "weight_count": s.get("weight_count"),
            "weight_files_sample": (s.get("weight_files") or [])[:12],
            "weight_files_truncated": s.get("weight_files_truncated") or max(0, len(s.get("weight_files") or []) - 12),
        }
        models[mid] = {
            "hf": {"url": f"https://huggingface.co/{mid}", "lifecycle": life, "visibility": s.get("visibility"), "http": s.get("http"), "gated": s.get("gated"), "disabled": s.get("disabled"), "checked_at": s.get("checked_at")},
            "last_public": lp, "license": lic, "mirror_eligibility": elig, "preservation": pres,
            "pirateface": {"url": p.get("url") or pf_url(mid), "status": p.get("status","unknown"), "checked_at": p.get("checked_at"), "seeders": p.get("seeders"), "magnet": p.get("magnet")},
            "frostbyte": {"app_url": FROST, "repo_url": FROST_REPO, "handoff": handoff, "magnet": p.get("magnet")},
        }
        if mid in event_by_id:
            e = event_by_id[mid]
            models[mid]["event"] = {"status": e.get("status"), "detected_at": e.get("detected_at"), "wayback_url": e.get("wayback_url")}
        counts["watched"] += 1
        if life == "AVAILABLE": counts["available"] += 1
        elif life == "RESTRICTED": counts["restricted"] += 1
        elif life == "VANISHED": counts["vanished"] += 1
        if pres == "PROTECTED": counts["protected"] += 1
        elif pres == "RESCUED": counts["rescued"] += 1
        elif pres == "AT_RISK": counts["at_risk"] += 1
        elif pres == "NO_KNOWN_COPY": counts["no_known_copy"] += 1
    return {"schema":"hf-vanished.status.v1","generated_at":now(),"source":"https://github.com/Blackwellboy/hf-vanished","summary":counts,"integrations":{"pirateface":{"base_url":PF,"mode":"bounded public-page probe; no private API"},"frostbyte":{"app_url":FROST,"repo_url":FROST_REPO,"handoff":"HF or magnet metadata; no custom app URL scheme assumed"}},"models":models}


def main() -> int:
    state = read(STATE, {"models": {}}); env = read(EVENTS, {"events": []})
    cache = read(CACHE, {"schema":"hf-vanished.integrations.v1","updated_at":None,"cursor":0,"pirateface":{"models":{}}})
    pc = cache.setdefault("pirateface", {}).setdefault("models", {})
    ids, cursor = choose(state, env.get("events") or [], pc, int(cache.get("cursor") or 0))
    print(f"pirateface probes={len(ids)}", file=sys.stderr)
    for mid in ids:
        old, new = pc.get(mid) or {}, probe(mid)
        if new.get("error") and old.get("status"):
            old = dict(old); old["last_attempted_at"] = new.get("checked_at"); old["last_error_http"] = new.get("http"); pc[mid] = old
        else: pc[mid] = new
        time.sleep(.05)
    cache.update({"schema":"hf-vanished.integrations.v1","updated_at":now(),"cursor":cursor})
    status = build(state, env.get("events") or [], pc)
    write(CACHE, cache); write(STATUS, status)
    print(f"status watched={status['summary']['watched']} rescued={status['summary']['rescued']}", file=sys.stderr)
    return 0

if __name__ == "__main__": raise SystemExit(main())
