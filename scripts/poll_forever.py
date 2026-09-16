#!/usr/bin/env python3
"""Persistent wrapper for hf-vanished.

The discovery layer in poll.py is intentionally small and cheap: explicit seeds,
keyword families and a popular-model slice. This wrapper makes discovery
cumulative. Once a model has ever entered data/state.json it remains in the
watch set on every future run, even if it later drops out of the current search
or popularity results.
"""

from __future__ import annotations

import poll

_original_expand = poll.expand_seeds


def cumulative_expand(seeds: dict) -> list[str]:
    ids = list(_original_expand(seeds))
    seen = set(ids)
    state = poll.load_json(poll.STATE_PATH, {"models": {}})

    for model_id in state.get("models", {}):
        if model_id and model_id not in seen:
            seen.add(model_id)
            ids.append(model_id)

    return ids


poll.expand_seeds = cumulative_expand

if __name__ == "__main__":
    raise SystemExit(poll.main())
