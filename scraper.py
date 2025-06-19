import time
import pytz
import pyodbc
import requests
from datetime import datetime
from bs4 import BeautifulSoup

# Connection string with your DB details (replace with your connection information)
conn_str = (
    "DRIVER=/opt/microsoft/msodbcsql17/lib64/libmsodbcsql-17.10.so.6.1;"
    "SERVER=your_server.database.windows.net;"
    "DATABASE=your_db_name;"
    "UID=your_username;"
    "PWD=your_password;"
)

tickers = [ 'INFY', 'ADANIGREEN', 'RELIANCE', 'TCS', 'HDFCBANK',
            'SBIN', 'ITC', 'HINDUNILVR', 'BAJAJ-AUTO', 'MARUTI' ]

def get_ist_time():
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist)

def get_stock_price(ticker):
    url = f'https://www.google.com/finance/quote/{ticker}:NSE'
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    price_tag = soup.find(class_='YMlKec fxKbKc')
    if price_tag:
        price = price_tag.text.replace('₹', '').replace(',', '').strip()
        try:
            return float(price)
        except:
            return None
    return None

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

cursor.execute("""
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='StockPrices' and xtype='U')
CREATE TABLE StockPrices (
    Timestamp DATETIME,
    INFY FLOAT,
    ADANIGREEN FLOAT,
    RELIANCE FLOAT,
    TCS FLOAT,
    HDFCBANK FLOAT,
    SBIN FLOAT,
    ITC FLOAT,
    HINDUNILVR FLOAT,
    BAJAJ_AUTO FLOAT,
    MARUTI FLOAT
)
""")
conn.commit()

start_time = time.time()
duration = 60 * 60  # 1 hour

print("Starting stock data collection...")

while time.time() - start_time < duration:
    now = get_ist_time()
    stock_data = [now]

    for t in tickers:
        p = get_stock_price(t)
        stock_data.append(p)
        print(f"{t}: {p}")

    cursor.execute("""
        INSERT INTO StockPrices (
            Timestamp, INFY, ADANIGREEN, RELIANCE, TCS, HDFCBANK,
            SBIN, ITC, HINDUNILVR, BAJAJ_AUTO, MARUTI
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, *stock_data)

    conn.commit()
    print(f"Inserted at {now.strftime('%H:%M:%S')}")
    time.sleep(2)

print("Data collection complete.")
conn.close()
