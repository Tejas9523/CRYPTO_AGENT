import json
import urllib.request
from datetime import datetime

SYMBOL = "BTCUSDT"   # Change to ETHUSDT if needed
INTERVAL = "15m"
LIMIT = 150

def fetch_klines(symbol, interval, limit):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    with urllib.request.urlopen(url, timeout=10) as response:
        data = json.loads(response.read().decode("utf-8"))

    candles = []
    for k in data:
        candles.append({
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5])
        })
    return candles

def ema(values, period):
    k = 2 / (period + 1)
    result = values[0]
    for value in values[1:]:
        result = value * k + result * (1 - k)
    return result

def calculate_rsi(values, period=14):
    gains = 0
    losses = 0

    for i in range(len(values) - period, len(values)):
        diff = values[i] - values[i - 1]
        if diff > 0:
            gains += diff
        else:
            losses -= diff

    if losses == 0:
        return 100

    rs = gains / losses
    return 100 - (100 / (1 + rs))

def calculate_atr(candles, period=14):
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

def generate_signal(candles):
    closes = [c["close"] for c in candles]

    price = closes[-1]
    ema20 = ema(closes[-80:], 20)
    ema50 = ema(closes[-120:], 50)
    rsi = calculate_rsi(closes)
    atr = calculate_atr(candles)

    avg_volume = sum(c["volume"] for c in candles[-21:-1]) / 20
    current_volume = candles[-1]["volume"]
    volume_boost = current_volume > avg_volume * 1.15

    long_score = 0
    short_score = 0

    if price > ema20 and ema20 > ema50:
        long_score += 40

    if price < ema20 and ema20 < ema50:
        short_score += 40

    if 52 <= rsi <= 72:
        long_score += 30

    if 28 <= rsi <= 48:
        short_score += 30

    if volume_boost and price > ema20:
        long_score += 20

    if volume_boost and price < ema20:
        short_score += 20

    if price > ema50:
        long_score += 10

    if price < ema50:
        short_score += 10

    decision = "NO TRADE"

    if long_score >= 70 and long_score >= short_score + 10:
        decision = "BUY / LONG NOW"
    elif short_score >= 70 and short_score >= long_score + 10:
        decision = "SHORT NOW"

    stop_loss = None
    target_1 = None
    target_2 = None

    if decision == "BUY / LONG NOW":
        stop_loss = price - atr * 1.5
        target_1 = price + atr * 2.25
        target_2 = price + atr * 3.75

    elif decision == "SHORT NOW":
        stop_loss = price + atr * 1.5
        target_1 = price - atr * 2.25
        target_2 = price - atr * 3.75

    return {
        "price": price,
        "ema20": ema20,
        "ema50": ema50,
        "rsi": rsi,
        "atr": atr,
        "long_score": long_score,
        "short_score": short_score,
        "decision": decision,
        "stop_loss": stop_loss,
        "target_1": target_1,
        "target_2": target_2
    }

def main():
    candles = fetch_klines(SYMBOL, INTERVAL, LIMIT)
    signal = generate_signal(candles)

    print()
    print("====================================")
    print("BTC / ETH AUTO SIGNAL AGENT")
    print("====================================")
    print("Time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("Symbol:", SYMBOL)
    print("Timeframe:", INTERVAL)
    print("Price:", round(signal["price"], 2))
    print("EMA20:", round(signal["ema20"], 2))
    print("EMA50:", round(signal["ema50"], 2))
    print("RSI:", round(signal["rsi"], 2))
    print("ATR:", round(signal["atr"], 2))
    print("Long Score:", signal["long_score"])
    print("Short Score:", signal["short_score"])
    print("------------------------------------")
    print("SIGNAL:", signal["decision"])

    if signal["decision"] != "NO TRADE":
        print("Entry:", round(signal["price"], 2))
        print("Stop Loss:", round(signal["stop_loss"], 2))
        print("Target 1:", round(signal["target_1"], 2))
        print("Target 2:", round(signal["target_2"], 2))
    else:
        print("No strong setup right now.")

    print("====================================")
    print("Educational scanner only. No guaranteed profit.")
    print("====================================")
    print()

if __name__ == "__main__":
    main()