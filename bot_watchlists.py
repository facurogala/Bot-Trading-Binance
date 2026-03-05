from typing import List

HAACK_UNIVERSE: List[str] = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT",
    "LTCUSDT", "TRXUSDT", "BCHUSDT", "UNIUSDT", "NEARUSDT",
    "FILUSDT", "ETCUSDT", "OPUSDT", "ARBUSDT", "ATOMUSDT",
    "HBARUSDT", "VETUSDT", "SUIUSDT", "APTUSDT", "GRTUSDT",
    "AAVEUSDT", "GALAUSDT", "MINAUSDT", "THETAUSDT", "FLOWUSDT",
    "EGLDUSDT", "AXSUSDT", "IMXUSDT", "SANDUSDT", "MANAUSDT",
    "ENJUSDT", "APEUSDT", "QNTUSDT", "DASHUSDT", "COMPUSDT",
    "ONEUSDT", "CHZUSDT", "INJUSDT", "DYDXUSDT", "STXUSDT",
    "CRVUSDT", "KAVAUSDT", "TWTUSDT", "CAKEUSDT", "FXSUSDT",
    "GMXUSDT", "WOOUSDT", "ROSEUSDT", "KDAUSDT", "ZILUSDT",
    "RVNUSDT", "SSVUSDT", "ALGOUSDT", "CELOUSDT", "YFIUSDT",
    "BAKEUSDT", "GTCUSDT", "HIGHUSDT", "IOSTUSDT", "KNCUSDT",
    "LRCUSDT", "MTLUSDT", "OGNUSDT", "ONTUSDT", "STORJUSDT",
]

SCALPING_WATCHLIST: List[str] = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT",
    "LTCUSDT", "TRXUSDT", "BCHUSDT", "UNIUSDT", "NEARUSDT",
    "FILUSDT", "ETCUSDT", "OPUSDT", "ARBUSDT", "ATOMUSDT",
    "SUIUSDT", "APTUSDT", "INJUSDT",
]

SWING_CANDIDATES: List[str] = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT",
    "LTCUSDT", "TRXUSDT", "BCHUSDT", "UNIUSDT", "NEARUSDT",
    "FILUSDT", "ETCUSDT", "OPUSDT", "ARBUSDT", "ATOMUSDT",
    "HBARUSDT", "SUIUSDT", "APTUSDT", "GRTUSDT", "AAVEUSDT",
    "INJUSDT", "DYDXUSDT", "STXUSDT", "CRVUSDT", "CAKEUSDT",
    "ALGOUSDT", "QNTUSDT", "IMXUSDT", "MANAUSDT", "SANDUSDT",
    "THETAUSDT", "FLOWUSDT", "GALAUSDT", "EGLDUSDT", "WOOUSDT",
]

_scalping_set = set(SCALPING_WATCHLIST)
SWING_WATCHLIST: List[str] = [symbol for symbol in SWING_CANDIDATES if symbol not in _scalping_set]
_swing_set = set(SWING_WATCHLIST)
HAACK_WATCHLIST: List[str] = [
    symbol for symbol in HAACK_UNIVERSE if symbol not in _scalping_set and symbol not in _swing_set
]

def _assert_disjoint() -> None:
    scalping = set(SCALPING_WATCHLIST)
    swing = set(SWING_WATCHLIST)
    haack = set(HAACK_WATCHLIST)

    if scalping & swing:
        raise ValueError(f"Watchlists solapadas entre Scalping y Swing: {sorted(scalping & swing)}")
    if scalping & haack:
        raise ValueError(f"Watchlists solapadas entre Scalping y Haack: {sorted(scalping & haack)}")
    if swing & haack:
        raise ValueError(f"Watchlists solapadas entre Swing y Haack: {sorted(swing & haack)}")

_assert_disjoint()
