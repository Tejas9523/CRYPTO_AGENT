def fetch_klines(symbol, interval, limit):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"

    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8", errors="replace")

        if not raw.strip():
            raise Exception("Empty response from Binance API.")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            print("\nBinance did not return JSON.")
            print("First 500 characters of response:")
            print(raw[:500])
            raise Exception("Binance API may be blocked by your network, region, VPN, or firewall.")

        if isinstance(data, dict) and "code" in data:
            raise Exception(f"Binance API error: {data}")

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

    except Exception as e:
        print("\nError while fetching market data:")
        print(e)
        print("\nTry:")
        print("1. Open this URL in browser:")
        print(url)
        print("2. Try mobile hotspot instead of office Wi-Fi")
        print("3. Try VPN")
        print("4. Use CoinGecko fallback version")
        raise
