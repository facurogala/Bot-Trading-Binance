import ast
import json
from pathlib import Path

path = Path(r"c:\Users\Facu\Desktop\Bot 5.12\Automatizacion\auto_trading_scanner_scalping_tpfast.py")
module = ast.parse(path.read_text(encoding="utf-8"))
watch = None
for node in module.body:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if getattr(target, "id", None) == "WATCHLIST":
                watch = ast.literal_eval(node.value)
                break
    if watch is not None:
        break
if watch is None:
    raise SystemExit("WATCHLIST not found")
watch = list(watch)

highcaps = {
    "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","ADAUSDT","DOGEUSDT","TRXUSDT",
    "LTCUSDT","DOTUSDT","AVAXUSDT","LINKUSDT","ATOMUSDT","APTUSDT","ARBUSDT","OPUSDT","NEARUSDT",
    "AAVEUSDT","FILUSDT","ETCUSDT","SANDUSDT","AXSUSDT","MANAUSDT","SUIUSDT","SEIUSDT","INJUSDT","RUNEUSDT",
    "GALAUSDT","RENDERUSDT","QNTUSDT","THETAUSDT","FETUSDT","IMXUSDT","GMXUSDT","LDOUSDT","SNXUSDT",
    "FLOWUSDT","STXUSDT","ENSUSDT","COMPUSDT","UNIUSDT","CAKEUSDT","KAVAUSDT","CHZUSDT","HBARUSDT","DYDXUSDT",
    "TIAUSDT","TONUSDT","PYTHUSDT","MINAUSDT","ALGOUSDT","1INCHUSDT","KNCUSDT","KSMUSDT","YFIUSDT","ZECUSDT",
    "ZILUSDT","BCHUSDT","GRTUSDT","SUSHIUSDT","CRVUSDT"
}

high_order = [t for t in watch if t in highcaps]
other_tokens = [t for t in watch if t not in highcaps]

bots = ["tpfast", "lax", "scalping", "grid_lax"]
targets = {"tpfast": 62, "lax": 61, "scalping": 61, "grid_lax": 61}
res = {b: [] for b in bots}
high_counts = {b: 0 for b in bots}

for token in high_order:
    candidates = [b for b in bots if len(res[b]) < targets[b]]
    if not candidates:
        break
    candidates.sort(key=lambda b: (high_counts[b], len(res[b]), bots.index(b)))
    best = candidates[0]
    res[best].append(token)
    high_counts[best] += 1

for token in other_tokens:
    candidates = [b for b in bots if len(res[b]) < targets[b]]
    if not candidates:
        break
    candidates.sort(key=lambda b: (len(res[b]), high_counts[b], bots.index(b)))
    best = candidates[0]
    res[best].append(token)

info = {
    b: {
        "count": len(res[b]),
        "highcaps": sum(1 for t in res[b] if t in highcaps)
    }
    for b in bots
}

print(json.dumps(info, indent=2))
for b in bots:
    print(f"== {b} ({len(res[b])} symbols, {sum(1 for t in res[b] if t in highcaps)} high caps)")
    for token in res[b]:
        print(token)

files = {
    "tpfast": Path(r"c:\\Users\\Facu\\Desktop\\Bot 5.12\\Automatizacion\\auto_trading_scanner_scalping_tpfast.py"),
    "lax": Path(r"c:\\Users\\Facu\\Desktop\\Bot 5.12\\Automatizacion\\auto_trading_scanner_scalping_lax.py"),
    "scalping": Path(r"c:\\Users\\Facu\\Desktop\\Bot 5.12\\Automatizacion\\auto_trading_scanner_scalping.py"),
    "grid_lax": Path(r"c:\\Users\\Facu\\Desktop\\Bot 5.12\\Automatizacion\\auto_trading_grid_lax.py"),
}


def format_watchlist(tokens):
    chunk_size = 6
    lines = []
    for i in range(0, len(tokens), chunk_size):
        chunk = tokens[i:i + chunk_size]
        quoted = ", ".join(f'"{token}"' for token in chunk)
        lines.append(f"    {quoted},")
    if lines:
        lines[-1] = lines[-1].rstrip(',') + ','
    block = "WATCHLIST = [\n" + "\n".join(lines) + "\n]\n\n"
    return block


def update_file(path: Path, tokens):
    text = path.read_text(encoding="utf-8")
    marker = "WATCHLIST = ["
    start = text.find(marker)
    if start == -1:
        raise ValueError(f"WATCHLIST block not found in {path}")
    close_idx = text.find("\n]", start)
    if close_idx == -1:
        close_idx = text.find("]", start)
        if close_idx == -1:
            raise ValueError(f"WATCHLIST closing bracket not found in {path}")
    # include the closing bracket line
    end = close_idx + 2
    new_block = format_watchlist(tokens)
    text = text[:start] + new_block + text[end:]
    path.write_text(text, encoding="utf-8")


for bot, tokens in res.items():
    update_file(files[bot], tokens)
