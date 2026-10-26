"""Delays between batch downloads so a long run does not trip rate limits or account bans."""

from __future__ import annotations

import random

# Minimum base delay (seconds) per platform. Instagram is stricter than YouTube.
MIN_DELAY_SEC = {"instagram": 8.0, "youtube": 4.0}

# Group order: Instagram runs completely before YouTube starts.
PLATFORM_ORDER = ("instagram", "youtube")


def next_delay(platform: str, base: float = 0.0, rng: random.Random | None = None) -> float:
    """Random wait before the next link. Never below the platform minimum, never a fixed beat."""
    floor = MIN_DELAY_SEC.get(platform, 4.0)
    base = max(float(base or 0.0), floor)
    rand = rng or random
    return round(rand.uniform(base * 0.75, base * 1.5), 1)


def check_delay(platform: str, rng: random.Random | None = None) -> float:
    """Short jittered wait between metadata checks (Instagram needs it, YouTube barely)."""
    rand = rng or random
    if platform == "instagram":
        return round(rand.uniform(1.0, 2.5), 1)
    return 0.2
