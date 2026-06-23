import csv
import json
import os
import urllib.request
from datetime import datetime

# ==========================
# SETTINGS
# ==========================

SYMBOL = "BTCUSDT"       # Change to ETHUSDT if you want
INTERVAL = "15m"         # 5m, 15m, 1h, 4h
LIMIT = 200

INITIAL_BALANCE = 10000.0
RISK_PER_TRADE_PERCENT = 1.0

STATE_FILE = "paper_state.json"
TRADES_FILE = "paper_trades.csv"


# ==========================
# DATA FETCHING
# ==========================

def fetch_klines(symbol, interval, limit):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(request, timeout=15) as response:
        raw = response.read().decode("utf-8", errors="replace")

    if not raw.strip():
        raise Exception("Empty response from Binance API.")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("Binance did not return JSON.")
        print("First 500 characters:")
        print(raw[:500])
        raise Exception("API blocked or invalid response.")

    candles = []

    for k in data:
        candles.append({
            "open_time": int(k[0]),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "close_time": int(k[6])
        })

    return candles


# ==========================
# INDICATORS
# ==========================

def ema(values, period):
    if len(values) < period:
        return None

    k = 2 / (period + 1)
    result = values[0]

    for value in values[1:]:
        result = value * k + result * (1 - k)

    return result


def calculate_rsi(values, period=14):
    if len(values) <= period:
        return None

    gains = 0.0
    losses = 0.0

    for i in range(len(values) - period, len(values)):
        diff = values[i] - values[i - 1]

        if diff > 0:
            gains += diff
        else:
            losses -= diff

    if losses == 0:
        return 100.0

    rs = gains / losses
    return 100 - (100 / (1 + rs))


def calculate_atr(candles, period=14):
    if len(candles) <= period:
        return None

    trs = []

    for i in range(len(candles) - period, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i - 1]["close"]

        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )

        trs.append(tr)

    return sum(trs) / len(trs)


# ==========================
# SIGNAL ENGINE
# ==========================

def generate_signal(candles):
    # Use only completed candles.
    completed = candles[:-1]

    closes = [c["close"] for c in completed]
    last = completed[-1]

    price = last["close"]
    ema20 = ema(closes[-80:], 20)
    ema50 = ema(closes[-120:], 50)
    rsi = calculate_rsi(closes, 14)
    atr = calculate_atr(completed, 14)

    if ema20 is None or ema50 is None or rsi is None or atr is None:
        return None

    avg_volume = sum(c["volume"] for c in completed[-21:-1]) / 20
    current_volume = completed[-1]["volume"]
    volume_boost = current_volume > avg_volume * 1.15

    recent_high = max(c["high"] for c in completed[-20:])
    recent_low = min(c["low"] for c in completed[-20:])

    long_score = 0
    short_score = 0

    # Trend
    if price > ema20 and ema20 > ema50:
        long_score += 40

    if price < ema20 and ema20 < ema50:
        short_score += 40

    # Momentum
    if 52 <= rsi <= 72:
        long_score += 25

    if 28 <= rsi <= 48:
        short_score += 25

    # Volume
    if volume_boost and price > ema20:
        long_score += 15

    if volume_boost and price < ema20:
        short_score += 15

    # Breakout / breakdown area
    if price > recent_high - atr * 0.35:
        long_score += 10

    if price < recent_low + atr * 0.35:
        short_score += 10

    # EMA50 bias
    if price > ema50:
        long_score += 10

    if price < ema50:
        short_score += 10

    decision = "NO TRADE"
    confidence = max(long_score, short_score)

    if long_score >= 70 and long_score >= short_score + 10:
        decision = "LONG"

    elif short_score >= 70 and short_score >= long_score + 10:
        decision = "SHORT"

    entry = price
    stop_loss = None
    target = None

    if decision == "LONG":
        stop_loss = entry - atr * 1.5
        target = entry + atr * 2.25

    elif decision == "SHORT":
        stop_loss = entry + atr * 1.5
        target = entry - atr * 2.25

    return {
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "decision": decision,
        "confidence": confidence,
        "entry": entry,
        "stop_loss": stop_loss,
        "target": target,
        "price": price,
        "ema20": ema20,
        "ema50": ema50,
        "rsi": rsi,
        "atr": atr,
        "long_score": long_score,
        "short_score": short_score,
        "signal_time": last["close_time"]
    }


# ==========================
# STATE MANAGEMENT
# ==========================

def load_state():
    if not os.path.exists(STATE_FILE):
        return {
            "balance": INITIAL_BALANCE,
            "open_trade": None
        }

    with open(STATE_FILE, "r") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)


def init_trades_file():
    if os.path.exists(TRADES_FILE):
        return

    with open(TRADES_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "open_time",
            "close_time",
            "symbol",
            "interval",
            "side",
            "entry",
            "stop_loss",
            "target",
            "exit_price",
            "result",
            "qty",
            "pnl",
            "balance_after",
            "confidence"
        ])


def append_trade(trade):
    init_trades_file()

    with open(TRADES_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            trade["open_time"],
            trade["close_time"],
            trade["symbol"],
            trade["interval"],
            trade["side"],
            round(trade["entry"], 4),
            round(trade["stop_loss"], 4),
            round(trade["target"], 4),
            round(trade["exit_price"], 4),
            trade["result"],
            round(trade["qty"], 8),
            round(trade["pnl"], 4),
            round(trade["balance_after"], 4),
            trade["confidence"]
        ])


# ==========================
# PAPER TRADING LOGIC
# ==========================

def open_paper_trade(state, signal):
    balance = state["balance"]

    risk_amount = balance * (RISK_PER_TRADE_PERCENT / 100)
    stop_distance = abs(signal["entry"] - signal["stop_loss"])

    if stop_distance <= 0:
        print("Invalid stop distance. Trade skipped.")
        return

    qty = risk_amount / stop_distance

    trade = {
        "symbol": signal["symbol"],
        "interval": signal["interval"],
        "side": signal["decision"],
        "entry": signal["entry"],
        "stop_loss": signal["stop_loss"],
        "target": signal["target"],
        "qty": qty,
        "risk_amount": risk_amount,
        "confidence": signal["confidence"],
        "open_time": signal["signal_time"]
    }

    state["open_trade"] = trade
    save_state(state)

    print()
    print("NEW PAPER TRADE OPENED")
    print("----------------------")
    print("Side:", trade["side"])
    print("Entry:", round(trade["entry"], 2))
    print("Stop Loss:", round(trade["stop_loss"], 2))
    print("Target:", round(trade["target"], 2))
    print("Quantity:", round(trade["qty"], 8))
    print("Risk Amount:", round(trade["risk_amount"], 2))
    print("Confidence:", str(trade["confidence"]) + "/100")


def check_open_trade(state, candles):
    trade = state["open_trade"]

    if trade is None:
        return

    completed = candles[:-1]

    candles_after_entry = [
        c for c in completed
        if c["close_time"] > trade["open_time"]
    ]

    if not candles_after_entry:
        print("Open trade still active. Waiting for next completed candle.")
        return

    side = trade["side"]
    exit_price = None
    result = None
    close_time = None

    for candle in candles_after_entry:
        high = candle["high"]
        low = candle["low"]

        if side == "LONG":
            # Conservative rule: if both SL and target hit same candle, count SL first.
            if low <= trade["stop_loss"]:
                exit_price = trade["stop_loss"]
                result = "LOSS"
                close_time = candle["close_time"]
                break

            if high >= trade["target"]:
                exit_price = trade["target"]
                result = "WIN"
                close_time = candle["close_time"]
                break

        elif side == "SHORT":
            # Conservative rule: if both SL and target hit same candle, count SL first.
            if high >= trade["stop_loss"]:
                exit_price = trade["stop_loss"]
                result = "LOSS"
                close_time = candle["close_time"]
                break

            if low <= trade["target"]:
                exit_price = trade["target"]
                result = "WIN"
                close_time = candle["close_time"]
                break

    if result is None:
        print()
        print("OPEN TRADE ACTIVE")
        print("-----------------")
        print("Side:", trade["side"])
        print("Entry:", round(trade["entry"], 2))
        print("Stop Loss:", round(trade["stop_loss"], 2))
        print("Target:", round(trade["target"], 2))
        return

    if side == "LONG":
        pnl = (exit_price - trade["entry"]) * trade["qty"]
    else:
        pnl = (trade["entry"] - exit_price) * trade["qty"]

    state["balance"] += pnl

    closed_trade = {
        "open_time": trade["open_time"],
        "close_time": close_time,
        "symbol": trade["symbol"],
        "interval": trade["interval"],
        "side": side,
        "entry": trade["entry"],
        "stop_loss": trade["stop_loss"],
        "target": trade["target"],
        "exit_price": exit_price,
        "result": result,
        "qty": trade["qty"],
        "pnl": pnl,
        "balance_after": state["balance"],
        "confidence": trade["confidence"]
    }

    append_trade(closed_trade)

    state["open_trade"] = None
    save_state(state)

    print()
    print("PAPER TRADE CLOSED")
    print("------------------")
    print("Result:", result)
    print("Exit Price:", round(exit_price, 2))
    print("PnL:", round(pnl, 2))
    print("New Balance:", round(state["balance"], 2))


# ==========================
# PERFORMANCE
# ==========================

def show_performance(state):
    if not os.path.exists(TRADES_FILE):
        print()
        print("No closed trades yet.")
        print("Current Balance:", round(state["balance"], 2))
        return

    wins = 0
    losses = 0
    total_pnl = 0.0
    total_trades = 0

    with open(TRADES_FILE, "r") as f:
        reader = csv.DictReader(f)

        for row in reader:
            total_trades += 1

            if row["result"] == "WIN":
                wins += 1
            elif row["result"] == "LOSS":
                losses += 1

            total_pnl += float(row["pnl"])

    win_rate = 0.0

    if total_trades > 0:
        win_rate = (wins / total_trades) * 100

    print()
    print("PAPER TRADING PERFORMANCE")
    print("-------------------------")
    print("Total Trades:", total_trades)
    print("Wins:", wins)
    print("Losses:", losses)
    print("Win Rate:", round(win_rate, 2), "%")
    print("Total PnL:", round(total_pnl, 2))
    print("Current Balance:", round(state["balance"], 2))


# ==========================
# MAIN
# ==========================

def main():
    print()
    print("====================================")
    print("BTC / ETH PAPER TRADING AGENT")
    print("====================================")
    print("Time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("Symbol:", SYMBOL)
    print("Timeframe:", INTERVAL)

    state = load_state()

    candles = fetch_klines(SYMBOL, INTERVAL, LIMIT)

    # First check if existing trade has hit SL or target.
    check_open_trade(state, candles)

    # Reload state after possible trade close.
    state = load_state()

    # If no trade is open, generate new signal.
    if state["open_trade"] is None:
        signal = generate_signal(candles)

        if signal is None:
            print("Not enough candle data to generate signal.")
            return

        print()
        print("CURRENT SIGNAL")
        print("--------------")
        print("Price:", round(signal["price"], 2))
        print("EMA20:", round(signal["ema20"], 2))
        print("EMA50:", round(signal["ema50"], 2))
        print("RSI:", round(signal["rsi"], 2))
        print("ATR:", round(signal["atr"], 2))
        print("Long Score:", signal["long_score"])
        print("Short Score:", signal["short_score"])
        print("Decision:", signal["decision"])
        print("Confidence:", str(signal["confidence"]) + "/100")

        if signal["decision"] in ["LONG", "SHORT"]:
            open_paper_trade(state, signal)
        else:
            print()
            print("NO TRADE")
            print("Market setup is not strong enough now.")

    show_performance(load_state())

    print()
    print("Files created:")
    print("-", STATE_FILE)
    print("-", TRADES_FILE)
    print()
    print("Educational paper trading only. No guaranteed profit.")
    print("====================================")


if __name__ == "__main__":
    main()