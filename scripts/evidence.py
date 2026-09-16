#!/usr/bin/env python3
"""HF Vanished forensic evidence layer.

Builds additive v2-style evidence feeds without changing the existing v1 event/status
contracts. Public sources only, bounded/fail-soft, and no causal inference: a removal
reason remains UNKNOWN unless a curated entry cites a public source.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STATE = DATA / "state.json"
EVENTS = DATA / "events.json"
REASONS = DATA / "reasons.json"
EVIDENCE = DATA / "evidence.json"
MANIFESTS = DATA / "manifests.json"
INCIDENTS = DATA / "incidents.json"

UA = "hf-vanished/0.3 (+https://github.com/Blackwellboy/hf-vanished; public forensic ledger)"
TIMEOUT = int(os.getenv("HFV_EVIDENCE_TIMEOUT", "12"))
EVENT_LIMIT = int(os.getenv("HFV_EVIDENCE_EVENT_LIMIT", "30"))
ROTATE_LIMIT = int(os.getenv("HFV_EVIDENCE_ROTATE_LIMIT", "24"))
STALE_HOURS = int(os.getenv("HFV_EVIDENCE_STALE_HOURS", "72"))
MAX_DISCUSSIONS = int(os.getenv("HFV_MAX_DISCUSSIONS", "8"))
MAX_DISCUSSION_EVENTS = int(os.getenv("HFV_MAX_DISCUSSION_EVENTS", "20"))
MAX_COMMITS = int(os.getenv("HFV_MAX_COMMITS", "12"))
MAX_TREE_FILES = int(os.getenv("HFV_MAX_TREE_FILES", "2000"))

REASON_CATEGORIES = {
    "author_action", "legal", "licensing", "moderation", "safety_policy",
    "terms_of_service", "distribution_change", "platform_action", "unknown", "other",
}
REASON_STATUSES = {"OFFICIAL", "PRIMARY_SOURCE", "CORROBORATED", "REPORTED", "UNKNOWN"}
SIGNAL_WORDS = (
    "dmca", "takedown", "legal", "lawyer", "copyright", "license", "licence",
    "moderation", "policy", "safety", "removed", "removal", "disabled", "private",
    "report", "reported", "terms of service", "tos", "appeal", "counter-notice",
)


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def age_hours(value: str | None) -> float | None:
    dt = parse_ts(value)
    if not dt:
        return None
    return (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(obj: Any) -> str:
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def http(url: str, accept: str = "application/json") -> tuple[int | None, str, dict[str, str]]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read().decode("utf-8", errors="replace"), dict(r.headers.items())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace"), dict(e.headers.items())
    except Exception as e:
        return None, repr(e), {}


def get_json(url: str) -> tuple[int | None, Any]:
    code, body, _ = http(url)
    if code != 200:
        return code, None
    try:
        return code, json.loads(body)
    except json.JSONDecodeError:
        return None, None


def q(mid: str) -> str:
    return urllib.parse.quote(mid, safe="/")


def repo_url(mid: str) -> str:
    return f"https://huggingface.co/{mid}"


def discussion_api(mid: str) -> str:
    return f"https://huggingface.co/api/models/{q(mid)}/discussions?p=0&type=all&status=all"


def discussion_detail_api(mid: str, num: int) -> str:
    return f"https://huggingface.co/api/models/{q(mid)}/discussions/{num}"


def commits_api(mid: str, rev: str = "main") -> str:
    return f"https://huggingface.co/api/models/{q(mid)}/commits/{urllib.parse.quote(rev, safe='')}"


def tree_api(mid: str, rev: str = "main") -> str:
    params = urllib.parse.urlencode({"recursive": "true", "expand": "true", "limit": MAX_TREE_FILES})
    return f"https://huggingface.co/api/models/{q(mid)}/tree/{urllib.parse.quote(rev, safe='')}?{params}"


def raw_readme_url(mid: str, rev: str = "main") -> str:
    return f"https://huggingface.co/{q(mid)}/raw/{urllib.parse.quote(rev, safe='')}/README.md"


def safe_text(value: Any, max_len: int = 800) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:max_len]


def keyword_signals(text: str, source_url: str) -> list[dict[str, Any]]:
    if not text:
        return []
    low = text.lower()
    out = []
    for word in SIGNAL_WORDS:
        start = low.find(word)
        if start < 0:
            continue
        lo, hi = max(0, start - 100), min(len(text), start + len(word) + 180)
        out.append({
            "signal": word,
            "classification": "NON_CAUSAL_SIGNAL",
            "excerpt": safe_text(text[lo:hi], 320),
            "source_url": source_url,
        })
        if len(out) >= 8:
            break
    return out


def normalize_discussion(item: dict[str, Any]) -> dict[str, Any]:
    num = item.get("num") or item.get("number")
    return {
        "num": num,
        "title": safe_text(item.get("title"), 300),
        "status": item.get("status"),
        "is_pull_request": bool(item.get("isPullRequest") or item.get("is_pull_request")),
        "author": ((item.get("author") or {}).get("name") if isinstance(item.get("author"), dict) else item.get("author")),
        "created_at": item.get("createdAt") or item.get("created_at"),
        "updated_at": item.get("updatedAt") or item.get("updated_at"),
    }


def fetch_discussions(mid: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    code, payload = get_json(discussion_api(mid))
    if code != 200 or not isinstance(payload, (list, dict)):
        return [], []
    rows = payload if isinstance(payload, list) else (payload.get("discussions") or [])
    rows = [x for x in rows if isinstance(x, dict)][:MAX_DISCUSSIONS]
    discussions, signals = [], []
    for raw in rows:
        d = normalize_discussion(raw)
        num = d.get("num")
        if isinstance(num, int):
            dc, detail = get_json(discussion_detail_api(mid, num))
            if dc == 200 and isinstance(detail, dict):
                events = detail.get("events") or []
                captured_events = []
                for ev in events[:MAX_DISCUSSION_EVENTS]:
                    if not isinstance(ev, dict):
                        continue
                    content = safe_text(ev.get("content") or ev.get("comment") or ev.get("title"), 1200)
                    actor = ev.get("author")
                    if isinstance(actor, dict): actor = actor.get("name")
                    row = {
                        "type": ev.get("type"), "author": actor,
                        "created_at": ev.get("createdAt") or ev.get("created_at"),
                        "content": content,
                    }
                    captured_events.append(row)
                    signals.extend(keyword_signals(content, f"{repo_url(mid)}/discussions/{num}"))
                d["events"] = captured_events
                d["source_sha256"] = digest(detail)
            time.sleep(.03)
        signals.extend(keyword_signals(d.get("title") or "", f"{repo_url(mid)}/discussions/{num}" if num else repo_url(mid)))
        discussions.append(d)
    return discussions, signals[:16]


def fetch_commits(mid: str, rev: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    code, payload = get_json(commits_api(mid, rev))
    if code != 200 or not isinstance(payload, list):
        return [], []
    commits, signals = [], []
    for item in payload[:MAX_COMMITS]:
        if not isinstance(item, dict):
            continue
        title = safe_text(item.get("title") or item.get("message"), 500)
        cid = item.get("id") or item.get("oid") or item.get("sha")
        commits.append({
            "id": cid, "title": title,
            "created_at": item.get("createdAt") or item.get("created_at") or item.get("date"),
            "authors": item.get("authors") or item.get("author"),
            "url": f"{repo_url(mid)}/commit/{cid}" if cid else repo_url(mid),
        })
        signals.extend(keyword_signals(title, f"{repo_url(mid)}/commit/{cid}" if cid else repo_url(mid)))
    return commits, signals[:12]


def fetch_readme_signals(mid: str, rev: str) -> tuple[str | None, list[dict[str, Any]]]:
    url = raw_readme_url(mid, rev)
    code, body, _ = http(url, "text/plain,text/markdown,*/*")
    if code != 200:
        return None, []
    return hashlib.sha256(body.encode("utf-8")).hexdigest(), keyword_signals(body, url)


def file_identity(item: dict[str, Any]) -> dict[str, Any]:
    path = item.get("path") or item.get("rfilename")
    lfs = item.get("lfs") if isinstance(item.get("lfs"), dict) else {}
    xet = item.get("xetHash") or item.get("xet_hash")
    oid = item.get("oid") or item.get("id")
    lfs_oid = lfs.get("oid")
    sha256 = None
    if isinstance(lfs_oid, str):
        sha256 = lfs_oid.split(":", 1)[1] if lfs_oid.startswith("sha256:") else (lfs_oid if re.fullmatch(r"[0-9a-fA-F]{64}", lfs_oid) else None)
    return {
        "path": path,
        "size": item.get("size") if item.get("size") is not None else lfs.get("size"),
        "git_oid": oid,
        "lfs_sha256": sha256,
        "xet_hash": xet,
    }


def fetch_manifest(mid: str, rev: str, fallback: dict[str, Any]) -> dict[str, Any]:
    code, payload = get_json(tree_api(mid, rev))
    if code == 200 and isinstance(payload, list):
        files = [file_identity(x) for x in payload if isinstance(x, dict) and (x.get("type") in (None, "file") or x.get("path"))]
        files = [x for x in files if x.get("path")][:MAX_TREE_FILES]
        core = {"repo": mid, "revision": rev, "files": files}
        return {
            "captured_at": now(), "revision": rev, "completeness": "TREE_API",
            "file_count": len(files), "truncated": len(payload) >= MAX_TREE_FILES,
            "files": files, "root_sha256": digest(core),
        }
    names = fallback.get("weight_files") or []
    files = [{"path": x, "size": None, "git_oid": None, "lfs_sha256": None, "xet_hash": None} for x in names]
    core = {"repo": mid, "revision": rev, "files": files}
    return {
        "captured_at": now(), "revision": rev, "completeness": "LAST_PUBLIC_SAMPLE",
        "file_count": fallback.get("file_count"), "weight_count": fallback.get("weight_count"),
        "truncated": bool(fallback.get("weight_files_truncated")), "files": files,
        "root_sha256": digest(core),
    }


def reason_for(mid: str, reasons: dict[str, Any]) -> dict[str, Any]:
    raw = (reasons.get("models") or {}).get(mid) or {}
    if not raw:
        return {"category": "unknown", "status": "UNKNOWN", "summary": "No public source documenting the cause has been recorded.", "sources": []}
    category = str(raw.get("category") or "unknown").lower()
    status = str(raw.get("status") or "UNKNOWN").upper()
    sources = [x for x in (raw.get("sources") or []) if isinstance(x, dict) and x.get("url")]
    if category not in REASON_CATEGORIES or status not in REASON_STATUSES or status != "UNKNOWN" and not sources:
        return {"category": "unknown", "status": "UNKNOWN", "summary": "Curated reason entry failed validation; cause remains unknown.", "sources": []}
    return {"category": category, "status": status, "summary": safe_text(raw.get("summary") or "", 700), "sources": sources}


def choose_models(state: dict[str, Any], events: list[dict[str, Any]], evidence: dict[str, Any]) -> tuple[list[str], int]:
    models = evidence.setdefault("models", {})
    cursor = int(evidence.get("cursor") or 0)
    picked, seen = [], set()
    def add(mid: str) -> None:
        if mid and mid not in seen:
            seen.add(mid); picked.append(mid)
    for ev in events[:EVENT_LIMIT]:
        mid = str(ev.get("id") or "")
        old = models.get(mid) or {}
        if mid and ((age_hours(old.get("captured_at")) or 9999) >= 6): add(mid)
    ids = sorted(str(x) for x in (state.get("models") or {}) if x)
    if ids:
        i, scanned = cursor % len(ids), 0
        while scanned < len(ids) and len(picked) < EVENT_LIMIT + ROTATE_LIMIT:
            mid = ids[i]; old = models.get(mid) or {}
            if (age_hours(old.get("captured_at")) or 9999) >= STALE_HOURS: add(mid)
            i, scanned = (i + 1) % len(ids), scanned + 1
        cursor = i
    return picked, cursor


def build_timeline(mid: str, events: list[dict[str, Any]], discussions: list[dict[str, Any]], commits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for e in events:
        if e.get("id") == mid:
            rows.append({"at": e.get("detected_at"), "type": "availability_event", "label": e.get("status"), "source": e.get("hf_url")})
    for d in discussions:
        if d.get("created_at"):
            rows.append({"at": d.get("created_at"), "type": "discussion", "label": d.get("title"), "source": f"{repo_url(mid)}/discussions/{d.get('num')}"})
    for c in commits:
        if c.get("created_at"):
            rows.append({"at": c.get("created_at"), "type": "commit", "label": c.get("title"), "source": c.get("url")})
    rows.sort(key=lambda x: str(x.get("at") or ""), reverse=True)
    return rows[:40]


def family_key(mid: str) -> str:
    name = mid.split("/", 1)[-1].lower()
    name = re.sub(r"[-_.](gguf|awq|gptq|fp8|fp16|bf16|nvfp4|q[2-8].*|int[248].*)$", "", name)
    parts = [x for x in re.split(r"[-_.]+", name) if x]
    return "-".join(parts[:3]) if parts else name


def build_incidents(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for e in events:
        dt = parse_ts(e.get("detected_at"))
        if dt and e.get("id"):
            rows.append((dt, e))
    rows.sort(key=lambda x: x[0])
    clusters, used = [], set()
    for i, (dt, ev) in enumerate(rows):
        if i in used: continue
        members = []
        for j in range(i, len(rows)):
            dt2, ev2 = rows[j]
            if (dt2 - dt).total_seconds() > 24 * 3600: break
            members.append((j, ev2))
        if len(members) < 2: continue
        for j, _ in members: used.add(j)
        ids = [str(x[1].get("id")) for x in members]
        owners: dict[str, int] = {}; families: dict[str, int] = {}
        for mid in ids:
            owner = mid.split("/", 1)[0] if "/" in mid else ""
            owners[owner] = owners.get(owner, 0) + 1
            fam = family_key(mid); families[fam] = families.get(fam, 0) + 1
        signals = [{"type": "TEMPORAL_CLUSTER", "count": len(ids), "window_hours": 24}]
        for owner, count in sorted(owners.items(), key=lambda x: -x[1]):
            if owner and count >= 2: signals.append({"type": "SAME_OWNER_CLUSTER", "owner": owner, "count": count})
        for fam, count in sorted(families.items(), key=lambda x: -x[1]):
            if fam and count >= 2: signals.append({"type": "SAME_MODEL_FAMILY", "family": fam, "count": count})
        start = members[0][1].get("detected_at"); end = members[-1][1].get("detected_at")
        cluster_id = "INC-" + hashlib.sha256(("|".join(ids) + str(start)).encode()).hexdigest()[:10].upper()
        clusters.append({
            "id": cluster_id, "start": start, "end": end, "models": ids,
            "signals": signals,
            "interpretation": "CORRELATION_ONLY",
            "note": "Signals describe timing/metadata correlation only; they do not establish coordination, motive, reporting campaigns, or government action.",
        })
    clusters.sort(key=lambda x: str(x.get("end") or ""), reverse=True)
    return clusters[:200]


def enrich_one(mid: str, state: dict[str, Any], events: list[dict[str, Any]], reasons: dict[str, Any], old: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    snap = (state.get("models") or {}).get(mid) or {}
    rev = str(snap.get("sha") or "main")
    discussions, dsignals = fetch_discussions(mid)
    commits, csignals = fetch_commits(mid, rev)
    readme_sha, rsignals = fetch_readme_signals(mid, rev)
    manifest = fetch_manifest(mid, rev, snap)
    if not discussions and old: discussions = old.get("discussions") or []
    if not commits and old: commits = old.get("commits") or []
    signals = (dsignals + csignals + rsignals)[:24]
    if not signals and old: signals = old.get("reason_signals") or []
    record = {
        "captured_at": now(), "repo": mid, "hf_url": repo_url(mid),
        "reason": reason_for(mid, reasons),
        "reason_signals": signals,
        "reason_signals_note": "Keyword/context signals are leads only and are never converted into a causal reason automatically.",
        "discussions": discussions,
        "commits": commits,
        "readme_sha256": readme_sha or ((old or {}).get("readme_sha256")),
        "manifest_root_sha256": manifest.get("root_sha256"),
        "timeline": build_timeline(mid, events, discussions, commits),
    }
    record["evidence_sha256"] = digest({k: v for k, v in record.items() if k != "evidence_sha256"})
    return record, manifest


def main() -> int:
    state = read(STATE, {"models": {}})
    envelope = read(EVENTS, {"events": []})
    events = envelope.get("events") or []
    reasons = read(REASONS, {"schema": "hf-vanished.reasons.v1", "models": {}})
    evidence = read(EVIDENCE, {"schema": "hf-vanished.evidence.v1", "generated_at": None, "cursor": 0, "models": {}})
    manifests = read(MANIFESTS, {"schema": "hf-vanished.manifest.v1", "generated_at": None, "models": {}})
    selected, cursor = choose_models(state, events, evidence)
    print(f"forensic evidence models={len(selected)}", flush=True)
    for mid in selected:
        try:
            old = (evidence.get("models") or {}).get(mid)
            record, manifest = enrich_one(mid, state, events, reasons, old)
            evidence.setdefault("models", {})[mid] = record
            manifests.setdefault("models", {})[mid] = manifest
        except Exception as exc:
            print(f"warn evidence {mid}: {exc!r}")
        time.sleep(.05)
    evidence.update({"schema": "hf-vanished.evidence.v1", "generated_at": now(), "cursor": cursor})
    manifests.update({"schema": "hf-vanished.manifest.v1", "generated_at": now()})
    incidents = {"schema": "hf-vanished.incidents.v1", "generated_at": now(), "incidents": build_incidents(events)}
    write(EVIDENCE, evidence); write(MANIFESTS, manifests); write(INCIDENTS, incidents)
    print(f"evidence_cached={len(evidence.get('models') or {})} incidents={len(incidents['incidents'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
