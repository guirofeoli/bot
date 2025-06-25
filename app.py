from flask import Flask, render_template, request
import requests
import pandas as pd
import time
import sqlite3
import ta

app = Flask(__name__)

# Pares e intervalos disponíveis
PAIRS = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT']
INTERVALS = ['1min', '5min', '15min', '1hour', '4hour']

# Função para buscar candles da API da KuCoin
def fetch_kucoin_candles(symbol, interval, limit=1000):
    url = f"https://api.kucoin.com/api/v1/market/candles?type={interval}&symbol={symbol}"
    all_candles = []
    end_time = int(time.time()) * 1000
    while len(all_candles) < limit:
        res = requests.get(url + f"&endAt={end_time}")
        data = res.json()
        candles = data['data']
        if not candles:
            break
        all_candles = candles + all_candles
        end_time = int(candles[0][0]) - 1
        if len(all_candles) >= limit:
            break
        time.sleep(0.2)
    df = pd.DataFrame(all_candles, columns=[
        'timestamp', 'open', 'close', 'high', 'low', 'volume', 'turnover'
    ])
    df = df.astype({
        'timestamp': 'int64', 'open': 'float', 'close': 'float',
        'high': 'float', 'low': 'float', 'volume': 'float', 'turnover': 'float'
    })
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.sort_values('timestamp')
    return df.tail(limit)

# Aplicar indicadores técnicos com a biblioteca ta
def apply_indicators(df):
    df['rsi'] = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()
    macd = ta.trend.MACD(df['close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    bb = ta.volatility.BollingerBands(df['close'])
    df['bb_upper'] = bb.bollinger_hband()
    df['bb_lower'] = bb.bollinger_lband()
    df['ema9'] = ta.trend.EMAIndicator(df['close'], window=9).ema_indicator()
    df['ema21'] = ta.trend.EMAIndicator(df['close'], window=21).ema_indicator()
    return df

# Salvar no SQLite
def save_to_sqlite(df, symbol, interval):
    conn = sqlite3.connect('crypto_data.db')
    table_name = f"candles_{symbol.replace('-', '_')}_{interval}"
    df.to_sql(table_name, conn, if_exists='replace', index=False)
    conn.close()

@app.route('/', methods=['GET', 'POST'])
def index():
    data = None
    selected_pair = PAIRS[0]
    selected_interval = INTERVALS[0]
    if request.method == 'POST':
        selected_pair = request.form['pair']
        selected_interval = request.form['interval']
        df = fetch_kucoin_candles(selected_pair, selected_interval, limit=1200)
        df = apply_indicators(df)
        df = df.dropna().tail(1000)
        save_to_sqlite(df, selected_pair, selected_interval)
        data = df.to_dict(orient='records')
    return render_template('index.html', pairs=PAIRS, intervals=INTERVALS, data=data, selected_pair=selected_pair, selected_interval=selected_interval)

if __name__ == '__main__':
    app.run(debug=True)
