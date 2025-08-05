"""
Streamlit app for real-time stock monitoring with alert notifications.

Features:
- Fetches stock price data from Azure SQL DB.
- Displays interactive trend charts.
- Sends email alerts when a selected stock crosses a threshold.
"""

import streamlit as st
import pandas as pd
import pyodbc
import altair as alt
import smtplib
from email.mime.text import MIMEText
from streamlit_autorefresh import st_autorefresh
from config import (
    DB_SERVER,
    DB_NAME,
    DB_USER,
    DB_PASSWORD,
    EMAIL_SENDER,
    EMAIL_PASSWORD,
)


def send_email(stock: str, price: float, threshold: float, receiver_email: str):
    """
    Sends an email alert when the stock price exceeds the threshold value.
    """
    subject = f"🚨 Stock Alert: {stock} exceeded threshold"
    body = (
        f"The price of {stock} is now ₹{price}, "
        f"which is above your threshold of ₹{threshold}."
    )
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = receiver_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        st.error(f"❌ Failed to send email: {e}")


@st.cache_data(ttl=5)
def fetch_data() -> pd.DataFrame:
    """
    Fetches the stock data from the Azure SQL Database.
    """
    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_NAME};"
        f"UID={DB_USER};"
        f"PWD={DB_PASSWORD};"
    )

    try:
        conn = pyodbc.connect(conn_str)
        df = pd.read_sql("SELECT * FROM StockPrices ORDER BY Timestamp DESC", conn)
        conn.close()
        df["Timestamp"] = pd.to_datetime(df["Timestamp"])
        return df
    except Exception as e:
        st.error(f"❌ Error fetching data: {e}")
        return pd.DataFrame()


def init_session_state():
    """
    Initializes the session state variables.
    """
    default_stock = stock_list[0] if stock_list else ""
    st.session_state.setdefault("threshold", 1000.0)
    st.session_state.setdefault("email", "receiver_email@gmail.com")
    st.session_state.setdefault("alert_stock", default_stock)
    st.session_state.setdefault("alert_sent", {})
    st.session_state.setdefault("prev_config", {})


# --- Streamlit Page Configuration ---
st.set_page_config(page_title="📊 Real-Time Stock Analysis", layout="wide")
st.title("📈 Real-Time Stock Analysis")

# --- Auto-refresh every 5 seconds ---
st_autorefresh(interval=5000, key="autorefresh")

# --- Load Data ---
df = fetch_data()
if df.empty:
    st.warning("No stock data available.")
    st.stop()

df = df.sort_values(by="Timestamp")
stock_list = [col for col in df.columns if col not in ["Timestamp", "id"]]

init_session_state()

# --- Sidebar for Threshold Alert ---
st.sidebar.header("🔔 Set Threshold Alert")

selected_stock = st.sidebar.selectbox(
    "Select stock for alert:", stock_list, index=stock_list.index(st.session_state.alert_stock)
)
threshold = st.sidebar.number_input("Price threshold:", value=st.session_state.threshold)
email_receiver = st.sidebar.text_input("Alert email to:", value=st.session_state.email)

# --- Reset alert if config changed ---
prev_config = st.session_state.prev_config.get(selected_stock, {})
if prev_config.get("threshold") != threshold or prev_config.get("email") != email_receiver:
    st.session_state.alert_sent[selected_stock] = False
    st.session_state.prev_config[selected_stock] = {
        "threshold": threshold,
        "email": email_receiver
    }

# --- Update Session State ---
st.session_state.alert_stock = selected_stock
st.session_state.threshold = threshold
st.session_state.email = email_receiver

# --- Alert Logic ---
latest_price = df.iloc[-1][selected_stock]

if latest_price > threshold:
    if not st.session_state.alert_sent.get(selected_stock, False):
        send_email(selected_stock, latest_price, threshold, email_receiver)
        st.session_state.alert_sent[selected_stock] = True
        st.sidebar.error(f"🚨 Alert sent: {selected_stock} = ₹{latest_price} > ₹{threshold}")
    else:
        st.sidebar.warning("📨 Alert already sent.")
else:
    st.sidebar.success(f"✅ {selected_stock} is ₹{latest_price} (below threshold)")
    st.session_state.alert_sent[selected_stock] = False

# --- Section: Trend Monitor ---
st.subheader("🔍 Stock Price Monitor")
stock = st.selectbox("Choose a stock to view trend:", stock_list)

df_selected = df[["Timestamp", stock]].dropna().copy()
df_selected.reset_index(drop=True, inplace=True)
df_selected["Reading"] = df_selected.index + 1
df_selected["Formatted_Time"] = df_selected["Timestamp"].dt.strftime("%d-%m-%Y %H:%M")

latest_price = df_selected[stock].iloc[-1]
latest_time = df_selected["Formatted_Time"].iloc[-1]
st.metric(label=f"📌 Latest {stock} Price", value=latest_price)
st.caption(f"Last updated: {latest_time}")

min_price = df_selected[stock].min()
max_price = df_selected[stock].max()
padding = (max_price - min_price) * 0.02 if max_price > min_price else 1
y_scale = alt.Scale(domain=[min_price - padding, max_price + padding])

trend_chart = alt.Chart(df_selected).mark_line(point=True).encode(
    x=alt.X("Reading:O", title="Reading #"),
    y=alt.Y(f"{stock}:Q", title="Price", scale=y_scale),
    tooltip=[
        alt.Tooltip("Formatted_Time:N", title="Date & Time"),
        alt.Tooltip(f"{stock}:Q", title="Price")
    ]
).properties(width=800, height=400).interactive()

st.altair_chart(trend_chart, use_container_width=True)

# --- Section: Gainers & Losers ---
st.subheader("📈 Top Gainers & 📉 Losers")
recent_df = df.tail(5).copy()
price_change = {}
for s in stock_list:
    if recent_df[s].notnull().sum() >= 2:
        first, last = recent_df[s].iloc[0], recent_df[s].iloc[-1]
        change = ((last - first) / first) * 100 if first != 0 else 0
        price_change[s] = round(change, 2)

change_df = pd.DataFrame(price_change.items(), columns=["Stock", "Change(%)"])
gainers = change_df.sort_values(by="Change(%)", ascending=False).head(5)
losers = change_df.sort_values(by="Change(%)").head(5)

col1, col2 = st.columns(2)
with col1:
    st.success("📈 Top 5 Gainers")
    st.dataframe(gainers, use_container_width=True)
with col2:
    st.error("📉 Top 5 Losers")
    st.dataframe(losers, use_container_width=True)

# --- Section: Price Snapshot ---
st.subheader("💰 Stock Price Snapshot")
latest_row = df.iloc[-1][stock_list]
top_prices = latest_row.sort_values(ascending=False).head(5)
bottom_prices = latest_row.sort_values().head(5)

col3, col4 = st.columns(2)
with col3:
    st.success("Most Expensive Stocks Now")
    st.dataframe(top_prices.reset_index().rename(columns={"index": "Stock", latest_row.name: "Price"}))
with col4:
    st.warning("Least Expensive Stocks Now")
    st.dataframe(bottom_prices.reset_index().rename(columns={"index": "Stock", latest_row.name: "Price"}))

# --- Section: Compare Multiple Stocks ---
st.subheader("📊 Compare Multiple Stocks")
selected_stocks = st.multiselect("Select stocks to compare:", stock_list, default=stock_list[:3])
if selected_stocks:
    compare_df = df[["Timestamp"] + selected_stocks].dropna().tail(20)
    compare_df = pd.melt(compare_df, id_vars=["Timestamp"], var_name="Stock", value_name="Price")
    chart = alt.Chart(compare_df).mark_line().encode(
        x="Timestamp:T",
        y="Price:Q",
        color="Stock:N",
        tooltip=["Stock:N", "Price:Q", alt.Tooltip("Timestamp:T", title="Date & Time")]
    ).properties(width=900, height=400).interactive()
    st.altair_chart(chart, use_container_width=True)
