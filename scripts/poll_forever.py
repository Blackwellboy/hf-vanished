#!/usr/bin/env python3
"""Persistent/enriched runner for HF Vanished."""
from __future__ import annotations

import urllib.parse
import poll

MAX_WEIGHT_NAMES = 96
_original_expand = poll.expand_seeds
_original_classify = poll.classify_http
_original_diff = poll.diff_events
_original_fetch = poll.fetch_model
_original_bootstrap = poll.bootstrap_known
_original_event_status = poll.event_status


def _license_from_payload(payload: dict) -> str | None:
    card = payload.get("cardData")
    if isinstance(card, dict) and card.get("license"):
        value = card.get("license")
        return ", ".join(str(x) for x in value if x) if isinstance(value, list) else str(value)
    for tag in payload.get("tags") or []:
        if isinstance(tag, str) and tag.lower().startswith("license:"):
            return tag.split(":", 1)[1]
    return None


def _base_models_from_payload(payload: dict) -> list[str]:
    card = payload.get("cardData")
    if not isinstance(card, dict):
        return []
    value = card.get("base_model") or card.get("base_models")
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(x) for x in value if x]
    return []


def _config_from_payload(payload: dict) -> dict:
    value = payload.get("config")
    return value if isinstance(value, dict) else {}


def _architectures_from_payload(payload: dict) -> list[str]:
    config = _config_from_payload(payload)
    value = config.get("architectures")
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(x) for x in value if x]
    return []


def _parameter_count_from_payload(payload: dict) -> int | None:
    """Best-effort public parameter count without inventing one."""
    safetensors = payload.get("safetensors")
    if isinstance(safetensors, dict):
        total = safetensors.get("total")
        if isinstance(total, (int, float)) and total >= 0:
            return int(total)
        parameters = safetensors.get("parameters")
        if isinstance(parameters, dict):
            values = [v for v in parameters.values() if isinstance(v, (int, float)) and v >= 0]
            if values:
                return int(sum(values))
    config = _config_from_payload(payload)
    for key in ("num_parameters", "n_parameters", "parameter_count"):
        value = config.get(key)
        if isinstance(value, (int, float)) and value >= 0:
            return int(value)
    return None


def _formats_from_files(weight_files: list[str]) -> list[str]:
    mapping = (
        (".safetensors", "safetensors"),
        (".gguf", "gguf"),
        (".bin", "pytorch-bin"),
        (".pt", "pytorch-pt"),
        (".pth", "pytorch-pth"),
        (".ckpt", "checkpoint"),
        (".msgpack", "msgpack"),
    )
    out: list[str] = []
    seen: set[str] = set()
    for name in weight_files:
        low = str(name).lower()
        for suffix, label in mapping:
            if low.endswith(suffix) and label not in seen:
                seen.add(label)
                out.append(label)
                break
    return out


def _quantization_from_payload(payload: dict) -> list[str]:
    """Only retain quantization hints explicitly exposed by public metadata."""
    out: list[str] = []
    seen: set[str] = set()

    def add(value: object) -> None:
        if value is None:
            return
        label = str(value).strip()
        if not label:
            return
        key = label.lower()
        if key not in seen:
            seen.add(key)
            out.append(label)

    config = _config_from_payload(payload)
    quant = config.get("quantization_config") or payload.get("quantization_config")
    if isinstance(quant, dict):
        method = quant.get("quant_method") or quant.get("quantization_method") or quant.get("method")
        bits = quant.get("bits")
        if method and isinstance(bits, (int, float, str)):
            add(f"{str(method).upper()} {bits}-bit")
        elif method:
            add(str(method).upper())

    known = (
        ("awq", "AWQ"),
        ("gptq", "GPTQ"),
        ("exl2", "EXL2"),
        ("exl3", "EXL3"),
        ("bitsandbytes", "bitsandbytes"),
        ("bnb-4bit", "BNB 4-bit"),
        ("bnb-8bit", "BNB 8-bit"),
        ("nf4", "NF4"),
        ("fp8", "FP8"),
        ("fp4", "FP4"),
        ("int4", "INT4"),
        ("int8", "INT8"),
    )
    tags = [str(x).lower() for x in (payload.get("tags") or []) if isinstance(x, str)]
    for token, label in known:
        if any(token in tag for tag in tags):
            add(label)
    return out


def _public_snapshot(snap: dict) -> dict:
    """Fields frozen on the most recent confirmed public observation."""
    keys = (
        "checked_at", "downloads", "likes", "sha", "last_modified", "license",
        "pipeline_tag", "library_name", "model_type", "architectures", "base_models",
        "author", "namespace", "parameter_count", "used_storage", "formats",
        "quantization", "file_count", "weight_count", "weight_files",
        "weight_files_truncated",
    )
    return {key: snap.get(key) for key in keys}


def enriched_classify(code: int | None, payload: dict | None) -> dict:
    snap = _original_classify(code, payload)
    if code == 200 and isinstance(payload, dict):
        siblings = payload.get("siblings") or []
        weight_files = [
            str(item.get("rfilename")) for item in siblings
            if isinstance(item, dict) and item.get("rfilename")
            and any(str(item.get("rfilename", "")).lower().endswith(ext) for ext in poll.WEIGHT_EXTS)
        ]
        config = _config_from_payload(payload)
        snap.update({
            "license": _license_from_payload(payload),
            "pipeline_tag": payload.get("pipeline_tag"),
            "library_name": payload.get("library_name"),
            "model_type": config.get("model_type"),
            "architectures": _architectures_from_payload(payload),
            "base_models": _base_models_from_payload(payload),
            "author": payload.get("author"),
            "parameter_count": _parameter_count_from_payload(payload),
            "used_storage": payload.get("usedStorage"),
            "formats": _formats_from_files(weight_files),
            "quantization": _quantization_from_payload(payload),
            "weight_files": weight_files[:MAX_WEIGHT_NAMES],
            "weight_files_truncated": max(0, len(weight_files) - MAX_WEIGHT_NAMES),
        })
    snap["auth_required"] = code in (401, 403)
    return snap


def enriched_fetch(model_id: str) -> dict:
    snap = _original_fetch(model_id)
    snap["namespace"] = model_id.split("/", 1)[0] if "/" in model_id else None
    if snap.get("visibility") == "public" and not snap.get("disabled"):
        snap["last_public_checked_at"] = snap.get("checked_at")
        # This nested object is deliberately absent from non-public responses.
        # poll.py merges snapshots into the previous state instead of deleting
        # unknown keys, so the final confirmed public profile survives a later
        # 401/403/404/disabled observation unchanged.
        snap["last_public"] = _public_snapshot(snap)
    return snap


def cumulative_expand(seeds: dict) -> list[str]:
    ids = list(_original_expand(seeds)); seen = set(ids)
    state = poll.load_json(poll.STATE_PATH, {"models": {}})
    for model_id in state.get("models", {}):
        if model_id and model_id not in seen:
            seen.add(model_id); ids.append(model_id)
    return ids


def bootstrap_missing(seeds: dict, state: dict, events: list[dict]) -> None:
    """Curated seeds are bootstrap data, not work to repeat every six hours."""
    existing = {(e.get("id"), str(e.get("status") or "").upper()) for e in events}
    missing = []
    for item in seeds.get("known_events", []):
        if not isinstance(item, dict) or not item.get("id") or not item.get("status"):
            missing.append(item); continue
        mid = item.get("id")
        want = str(item.get("status")).upper()
        key = (mid, want)
        # AUTH_REQUIRED is the conservative normalized form of older curated
        # PRIVATE/DELETED labels when the only current proof is HTTP 401/403.
        auth_equivalent = want in ("PRIVATE", "DELETED") and (mid, "AUTH_REQUIRED") in existing
        if (key not in existing and not auth_equivalent) or mid not in state.get("models", {}):
            missing.append(item)
    if not missing:
        return
    subset = dict(seeds); subset["known_events"] = missing
    _original_bootstrap(subset, state, events)


def conservative_diff(prev: dict | None, cur: dict) -> list[tuple[str, str, str]]:
    out = []
    for kind, severity, summary in _original_diff(prev, cur):
        if kind == "private" and cur.get("http") in (401, 403):
            summary = "Unauthenticated access now returns HTTP 401/403 after a prior public observation."
        out.append((kind, severity, summary))

    # Reinstatement is an observable state change too. Record it without
    # inferring whether it followed an appeal, author action, platform action,
    # legal process, or a transient incident.
    if prev and cur.get("visibility") == "public" and not cur.get("disabled"):
        prev_vis = prev.get("visibility")
        prev_gated = prev.get("gated") not in (False, None, "", 0)
        cur_gated = cur.get("gated") not in (False, None, "", 0)
        was_unavailable = bool(prev.get("disabled")) or prev_vis in ("deleted", "private", "disabled", "auth_required")
        weights_returned = (
            isinstance(prev.get("weight_count"), int) and isinstance(cur.get("weight_count"), int)
            and prev.get("weight_count") == 0 and cur.get("weight_count") > 0
        )
        ungated = prev_gated and not cur_gated
        if was_unavailable:
            out.append(("restored", "soft", "Repo resolves publicly again after a prior unavailable/auth-required observation."))
        elif weights_returned:
            out.append(("restored", "soft", f"Model files are present again ({prev.get('weight_count')} → {cur.get('weight_count')})."))
        elif ungated:
            out.append(("restored", "soft", "Previously gated repository is publicly accessible without the prior gate."))
    return out


def extended_event_status(kind: str) -> str:
    if kind == "restored":
        return "RESTORED"
    return _original_event_status(kind)


def enrich_outputs() -> None:
    state = poll.load_json(poll.STATE_PATH, {"models": {}})
    envelope = poll.load_json(poll.EVENTS_PATH, {"events": []})
    for event in envelope.get("events") or []:
        model_id = event.get("id")
        if not model_id: continue
        event["pirateface_url"] = f"https://pirateface.co/{urllib.parse.quote(str(model_id), safe='/')}"
        snap = state.get("models", {}).get(model_id) or {}

        # A bare unauthenticated 401/403 does not prove deletion vs privacy.
        # Normalize both old curated labels and new PRIVATE transitions to the
        # observable fact, while retaining the original label for provenance.
        if snap.get("http") in (401, 403) and str(event.get("status") or "").upper() in ("PRIVATE", "DELETED"):
            event.setdefault("reported_status", event.get("status"))
            event["status"] = "AUTH_REQUIRED"
            event["kind"] = "auth_required"
            event["summary"] = "Unauthenticated Hub access returns HTTP 401/403 after prior public evidence; exact private/deleted state is not inferred."
            event.setdefault("curr", {})["visibility"] = "auth_required"
            event["curr"]["http"] = snap.get("http")
            event["curr"]["auth_required"] = True
        elif (event.get("curr") or {}).get("http") in (401, 403):
            event.setdefault("curr", {})["auth_required"] = True

        # Use only the nested profile captured during a confirmed public
        # observation. Never relabel metadata from a disabled/private response
        # as historical public evidence.
        frozen = snap.get("last_public")
        if isinstance(frozen, dict) and frozen:
            event["last_public"] = frozen
    envelope["cadence"] = "17 */6 * * *"
    poll.save_json(poll.EVENTS_PATH, envelope)


def main() -> int:
    poll.classify_http = enriched_classify
    poll.fetch_model = enriched_fetch
    poll.expand_seeds = cumulative_expand
    poll.bootstrap_known = bootstrap_missing
    poll.diff_events = conservative_diff
    poll.event_status = extended_event_status
    rc = poll.main()
    if rc == 0: enrich_outputs()
    return rc

if __name__ == "__main__": raise SystemExit(main())
