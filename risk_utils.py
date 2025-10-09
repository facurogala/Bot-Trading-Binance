"""Utility helpers for risk-based sizing and target calculations."""
from __future__ import annotations

import os
from typing import Iterable, List


def env_float(default: float, *keys: str, context: str | None = None) -> float:
    """Return the first valid float found in the provided environment keys.

    Falls back to ``default`` when no key is defined or parsable. The optional
    ``context`` string is used only for warning messages.
    """
    for key in keys:
        if not key:
            continue
        raw = os.getenv(key)
        if raw is None or str(raw).strip() == "":
            continue
        try:
            return float(raw)
        except ValueError:
            label = f" ({context})" if context else ""
            print(f"⚠️ Valor inválido en {key}='{raw}'{label}. Usando {default}.")
    return float(default)


def parse_float_list(raw: str | None, default: Iterable[float]) -> List[float]:
    """Parse a comma-separated list of floats with graceful fallbacks."""
    if raw is None or str(raw).strip() == "":
        return [float(x) for x in default]

    values: List[float] = []
    for chunk in raw.split(','):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            values.append(float(chunk))
        except ValueError:
            continue

    return values if values else [float(x) for x in default]


def risk_tp_prices(entry: float, sl: float, side: str, multipliers: Iterable[float]) -> List[float]:
    """Build TP prices as multiples of the risk distance (1R, 2R, ...)."""
    distance = abs(entry - sl)
    if distance <= 0:
        # Fallback to a small distance relative to price to avoid degenerate targets
        distance = max(abs(entry) * 0.001, 1e-6)

    side_upper = (side or "").upper()
    prices: List[float] = []
    for mult in multipliers:
        try:
            m = float(mult)
        except (TypeError, ValueError):
            continue
        if m <= 0:
            continue
        if side_upper == "SHORT":
            prices.append(entry - distance * m)
        else:
            prices.append(entry + distance * m)

    if side_upper == "SHORT":
        prices = sorted(prices, reverse=True)
    else:
        prices = sorted(prices)

    # Remove duplicates while preserving order
    unique: List[float] = []
    seen = set()
    for price in prices:
        if price not in seen:
            unique.append(price)
            seen.add(price)
    return unique
