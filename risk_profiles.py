import os
from typing import Dict


_PROFILE_DEFAULTS = {
    "TESTNET_SAFE": {
        "RISK_GUARD_ENABLED": "True",
        "MAX_DAILY_LOSS_USDT": "500",
        "MAX_CONSECUTIVE_LOSSES": "8",
        "MAX_DRAWDOWN_PCT": "0",
        "RISK_GUARD_PAUSE_MINUTES": "30",
    },
    "PROD_SAFE": {
        "RISK_GUARD_ENABLED": "True",
        "MAX_DAILY_LOSS_USDT": "50",
        "MAX_CONSECUTIVE_LOSSES": "3",
        "MAX_DRAWDOWN_PCT": "12",
        "RISK_GUARD_PAUSE_MINUTES": "180",
    },
    "CONSERVATIVE": {
        "RISK_GUARD_ENABLED": "True",
        "MAX_DAILY_LOSS_USDT": "30",
        "MAX_CONSECUTIVE_LOSSES": "2",
        "MAX_DRAWDOWN_PCT": "8",
        "RISK_GUARD_PAUSE_MINUTES": "240",
    },
    "AGGRESSIVE": {
        "RISK_GUARD_ENABLED": "True",
        "MAX_DAILY_LOSS_USDT": "100",
        "MAX_CONSECUTIVE_LOSSES": "5",
        "MAX_DRAWDOWN_PCT": "20",
        "RISK_GUARD_PAUSE_MINUTES": "60",
    },
}


def _is_testnet_enabled() -> bool:
    testnet = os.getenv("TESTNET")
    use_testnet = os.getenv("USE_TESTNET")
    return (str(testnet).lower() == "true") or (str(use_testnet).lower() == "true")


def apply_risk_profile_defaults() -> Dict[str, str]:
    """Aplica defaults de riesgo solo si no existen en el entorno.

    Variables soportadas:
    - RISK_PROFILE=AUTO|CONSERVATIVE|AGGRESSIVE
    - RISK_GUARD_ENABLED
    - MAX_DAILY_LOSS_USDT
    - MAX_CONSECUTIVE_LOSSES
    - MAX_DRAWDOWN_PCT
    - RISK_GUARD_PAUSE_MINUTES
    """
    profile = os.getenv("RISK_PROFILE", "AUTO").upper().strip()

    if profile == "AUTO":
        selected = "TESTNET_SAFE" if _is_testnet_enabled() else "PROD_SAFE"
    elif profile in _PROFILE_DEFAULTS:
        selected = profile
    else:
        selected = "PROD_SAFE"

    defaults = _PROFILE_DEFAULTS[selected]
    for key, value in defaults.items():
        if os.getenv(key) is None:
            os.environ[key] = value

    snapshot = {k: os.getenv(k, v) for k, v in defaults.items()}
    snapshot["RISK_PROFILE_SELECTED"] = selected
    snapshot["RISK_PROFILE_REQUESTED"] = profile
    snapshot["RISK_ENV_MODE"] = "TESTNET" if _is_testnet_enabled() else "PROD"
    return snapshot
