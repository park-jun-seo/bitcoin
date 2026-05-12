import streamlit as st
import pyupbit
import pandas as pd
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

st.set_page_config(
    page_title="CoinFirst",
    page_icon="🪙",
    layout="wide"
)

st_autorefresh(interval=5000, key="refresh")

st.title("🪙 CoinFirst - 업비트 실시간 코인 대시보드")
st.caption("업비트 Open API 기반 실시간 시세 분석")

# -----------------------------
# 사이드바
# -----------------------------
st.sidebar.header("설정")

tickers = pyupbit.get_tickers(fiat="KRW")
coin = st.sidebar.selectbox("코인 선택", tickers, index=tickers.index("KRW-BTC"))

interval = st.sidebar.selectbox(
    "캔들 간격",
    ["minute1", "minute5", "minute15", "minute60", "day"],
    index=1
)

count = st.sidebar.slider("캔들 개수", 30, 200, 100)

# -----------------------------
# 데이터 불러오기
# -----------------------------
@st.cache_data(ttl=5)
def load_data(ticker, interval, count):
    df = pyupbit.get_ohlcv(ticker, interval=interval, count=count)
    return df

df = load_data(coin, interval, count)

if df is None or df.empty:
    st.error("데이터를 불러오지 못했습니다.")
    st.stop()

current_price = pyupbit.get_current_price(coin)

prev_close = df["close"].iloc[-2]
change_rate = ((current_price - prev_close) / prev_close) * 100

high_price = df["high"].iloc[-1]
low_price = df["low"].iloc[-1]
volume = df["volume"].iloc[-1]

# -----------------------------
# 상단 지표
# -----------------------------
col1, col2, col3, col4 = st.columns(4)

col1.metric("현재가", f"{current_price:,.0f} 원", f"{change_rate:.2f}%")
col2.metric("고가", f"{high_price:,.0f} 원")
col3.metric("저가", f"{low_price:,.0f} 원")
col4.metric("거래량", f"{volume:,.2f}")

# -----------------------------
# 캔들 차트
# -----------------------------
st.subheader(f"{coin} 캔들 차트")

fig = go.Figure()

fig.add_trace(go.Candlestick(
    x=df.index,
    open=df["open"],
    high=df["high"],
    low=df["low"],
    close=df["close"],
    name="Candlestick"
))

fig.update_layout(
    height=550,
    xaxis_rangeslider_visible=False,
    template="plotly_dark"
)

st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# 이동평균선 분석
# -----------------------------
df["MA5"] = df["close"].rolling(window=5).mean()
df["MA20"] = df["close"].rolling(window=20).mean()

st.subheader("이동평균선 분석")

fig2 = go.Figure()

fig2.add_trace(go.Scatter(
    x=df.index,
    y=df["close"],
    mode="lines",
    name="종가"
))

fig2.add_trace(go.Scatter(
    x=df.index,
    y=df["MA5"],
    mode="lines",
    name="MA5"
))

fig2.add_trace(go.Scatter(
    x=df.index,
    y=df["MA20"],
    mode="lines",
    name="MA20"
))

fig2.update_layout(
    height=400,
    template="plotly_dark"
)

st.plotly_chart(fig2, use_container_width=True)

# -----------------------------
# RSI 계산
# -----------------------------
def calculate_rsi(data, period=14):
    delta = data["close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi

df["RSI"] = calculate_rsi(df)

latest_rsi = df["RSI"].iloc[-1]

st.subheader("RSI 분석")

if latest_rsi >= 70:
    signal = "과매수 구간"
elif latest_rsi <= 30:
    signal = "과매도 구간"
else:
    signal = "중립 구간"

st.metric("현재 RSI", f"{latest_rsi:.2f}", signal)

fig3 = go.Figure()

fig3.add_trace(go.Scatter(
    x=df.index,
    y=df["RSI"],
    mode="lines",
    name="RSI"
))

fig3.add_hline(y=70, line_dash="dash")
fig3.add_hline(y=30, line_dash="dash")

fig3.update_layout(
    height=300,
    template="plotly_dark"
)

st.plotly_chart(fig3, use_container_width=True)

# -----------------------------
# 거래대금 TOP 10
# -----------------------------
st.subheader("KRW 마켓 거래대금 TOP 10")

@st.cache_data(ttl=10)
def get_market_top10():
    data = []

    for ticker in tickers[:80]:
        try:
            temp = pyupbit.get_ohlcv(ticker, interval="minute1", count=1)
            price = pyupbit.get_current_price(ticker)

            if temp is not None and price is not None:
                trade_value = temp["volume"].iloc[-1] * price
                data.append([ticker, price, trade_value])
        except:
            pass

    result = pd.DataFrame(data, columns=["코인", "현재가", "거래대금"])
    result = result.sort_values("거래대금", ascending=False).head(10)
    return result

top10 = get_market_top10()

st.dataframe(
    top10,
    use_container_width=True,
    hide_index=True
)

# -----------------------------
# 급등/급락 판단
# -----------------------------
st.subheader("간단 매매 신호")

if change_rate > 2 and latest_rsi < 70:
    st.success("상승 흐름이 강합니다. 단, 추격 매수는 주의하세요.")
elif change_rate < -2:
    st.warning("단기 하락폭이 큽니다. 변동성에 주의하세요.")
elif latest_rsi >= 70:
    st.error("RSI 과매수 구간입니다. 단기 조정 가능성을 확인하세요.")
elif latest_rsi <= 30:
    st.info("RSI 과매도 구간입니다. 반등 가능성을 관찰할 수 있습니다.")
else:
    st.write("현재는 뚜렷한 과열 또는 침체 신호가 크지 않습니다.")