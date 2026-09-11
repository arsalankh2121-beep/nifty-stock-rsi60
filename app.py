import yfinance as yf
import requests, os, time
from flask import Flask
from datetime import datetime
import pytz
import threading

app = Flask(__name__)
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "avais-stock-rsi60")

ALL_INDICES = {"^NSEI":"NIFTY50","^NSEBANK":"BANK","^CNXAUTO":"AUTO","^CNXIT":"IT","^CNXPHARMA":"PHARMA","^CNXFMCG":"FMCG","^CNXMETAL":"METAL","^CNXREALTY":"REALTY"}
STOCKS_MAP = {"^NSEI":["RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","ICICIBANK.NS"],"^NSEBANK":["HDFCBANK.NS","ICICIBANK.NS","SBIN.NS","KOTAKBANK.NS","AXISBANK.NS"],"^CNXAUTO":["MARUTI.NS","TATAMOTORS.NS","M&M.NS","BAJAJ-AUTO.NS","EICHERMOT.NS"],"^CNXIT":["TCS.NS","INFY.NS","WIPRO.NS","HCLTECH.NS","TECHM.NS"],"^CNXPHARMA":["SUNPHARMA.NS","DRREDDY.NS","CIPLA.NS"],"^CNXFMCG":["ITC.NS","HINDUNILVR.NS","NESTLEIND.NS"],"^CNXMETAL":["TATASTEEL.NS","JSWSTEEL.NS","HINDALCO.NS"],"^CNXREALTY":["DLF.NS","GODREJPROP.NS","OBEROIRLTY.NS"]}

def is_market_open():
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    if now.weekday() >= 5:
        return False
    start = now.replace(hour=9, minute=15, second=0, microsecond=0)
    end = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return start <= now <= end

def get_rsi(ticker, period, interval):
    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
        if len(df) < 20:
            return 0
        close = df['Close']
        delta = close.diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/14, min_periods=14).mean()
        loss = -delta.where(delta < 0, 0).ewm(alpha=1/14, min_periods=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1])
    except:
        return 0

def ntfy(msg):
    try:
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=msg.encode('utf-8'))
    except:
        pass

@app.route('/')
def home():
    ist = pytz.timezone('Asia/Kolkata')
    now_str = datetime.now(ist).strftime('%d-%m-%Y %I:%M %p IST')
    status = "MARKET OPEN - SCANNING" if is_market_open() else "MARKET CLOSED - SLEEPING"
    return f"Scanner {status} | {now_str}"

def scanner_loop():
    while True:
        if not is_market_open():
            print("Market closed, sleeping 5 min...")
            time.sleep(300)
            continue
        for idx_ticker, idx_name in ALL_INDICES.items():
            if not is_market_open():
                break
            rsi_m = get_rsi(idx_ticker, "5y", "1mo")
            rsi_w = get_rsi(idx_ticker, "2y", "1wk")
            if rsi_m > 60 and rsi_w > 60:
                for stock in STOCKS_MAP.get(idx_ticker, []):
                    sm = get_rsi(stock, "5y", "1mo")
                    sw = get_rsi(stock, "2y", "1wk")
                    if sm > 60 and sw > 60:
                        sh = get_rsi(stock, "3mo", "60m")
                        s15 = get_rsi(stock, "60d", "15m")
                        if sh > 60 and s15 > 60:
                            ntfy(f"BUY {stock} | {idx_name} M:{sm:.0f} W:{sw:.0f} H:{sh:.0f} 15M:{s15:.0f}")
            time.sleep(1)
        time.sleep(60)

threading.Thread(target=scanner_loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
