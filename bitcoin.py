import streamlit as st
import pyupbit
import pandas as pd
import plotly.graph_objects as go
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
from streamlit_autorefresh import st_autorefresh
import requests

# -----------------------------
# 1. 페이지 설정 및 자동 새로고침
# -----------------------------
st.set_page_config(
    page_title="PRO 암호화폐 실시간 대시보드",
    layout="wide"
)

# 기본 차트 새로고침 (10초)
st_autorefresh(interval=10000, key="refresh")

# -----------------------------
# 2. 사이드바 설정
# -----------------------------
st.sidebar.title("🛠️ 설정")

@st.cache_data(ttl=3600)
def get_krw_coin_dict():
    url = "https://api.upbit.com/v1/market/all?isDetails=false"
    headers = {"accept": "application/json"}
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        return {f"{item['korean_name']} ({item['market']})": item['market'] for item in data if item['market'].startswith("KRW-")}
    except:
        return {"비트코인 (KRW-BTC)": "KRW-BTC"}

coins_dict = get_krw_coin_dict()

selected_display_name = st.sidebar.selectbox("🔍 코인 검색 및 선택", list(coins_dict.keys()))
ticker = coins_dict[selected_display_name]
selected_korean_name = selected_display_name.split(" ")[0]

interval = st.sidebar.selectbox(
    "차트 주기(분봉/일봉)",
    ["minute1", "minute5", "minute15", "minute60", "day"],
    index=1
)

st.sidebar.markdown("---")
st.sidebar.subheader("📈 지표 변수")
ma_short_val = st.sidebar.number_input("단기 이평선(MA)", value=5, min_value=1)
ma_long_val = st.sidebar.number_input("장기 이평선(MA)", value=20, min_value=1)
rsi_window = st.sidebar.number_input("RSI 기간", value=14, min_value=1)

st.sidebar.markdown("---")
st.sidebar.subheader("🚨 급등 탐지 조건 (24H 기준)")
surge_price = st.sidebar.number_input("가격 상승률 기준 (%)", value=5.0, step=1.0, help="24시간 전 대비 현재가 상승률입니다.")

# -----------------------------
# 3. 데이터 로딩 및 지표 계산
# -----------------------------
@st.cache_data(ttl=5)
def get_coin_data(ticker, interval):
    df = pyupbit.get_ohlcv(ticker=ticker, interval=interval, count=100)
    if df is not None:
        df['MA_S'] = df['close'].rolling(ma_short_val).mean()
        df['MA_L'] = df['close'].rolling(ma_long_val).mean()
        df['RSI'] = RSIIndicator(close=df['close'], window=rsi_window).rsi()
        bb = BollingerBands(close=df['close'], window=20, window_dev=2)
        df['BB_H'] = bb.bollinger_hband()
        df['BB_L'] = bb.bollinger_lband()
    return df

df = get_coin_data(ticker, interval)
current_price = pyupbit.get_current_price(ticker)

# -----------------------------
# 4. 메인 화면 헤더
# -----------------------------
st.title(f"📊 {selected_korean_name}({ticker}) 실시간 분석")

col_m1, col_m2, col_m3, col_m4 = st.columns(4)
with col_m1:
    st.metric("현재가", f"{current_price:,.0f} 원")
with col_m2:
    high_24h = df['high'].max()
    st.metric("최근 최고가", f"{high_24h:,.0f} 원")
with col_m3:
    last_rsi = df['RSI'].iloc[-1]
    st.metric("RSI (14)", f"{last_rsi:.2f}")
with col_m4:
    vol_sum = df['volume'].sum()
    st.metric("최근 누적 거래량", f"{vol_sum:,.2f}")

# -----------------------------
# 5. 메인 차트
# -----------------------------
st.subheader("🕯️ 메인 기술적 분석 차트")
fig = go.Figure()
fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='Candle'))
fig.add_trace(go.Scatter(x=df.index, y=df['BB_H'], line=dict(color='rgba(173, 216, 230, 0.5)'), name='BB_Upper'))
fig.add_trace(go.Scatter(x=df.index, y=df['BB_L'], line=dict(color='rgba(173, 216, 230, 0.5)'), fill='tonexty', name='BB_Lower'))
fig.add_trace(go.Scatter(x=df.index, y=df['MA_S'], line=dict(color='orange', width=1), name=f'MA{ma_short_val}'))
fig.add_trace(go.Scatter(x=df.index, y=df['MA_L'], line=dict(color='blue', width=1), name=f'MA{ma_long_val}'))
fig.update_layout(height=500, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# 6. 하단 차트
# -----------------------------
col_c1, col_c2 = st.columns(2)
with col_c1:
    st.markdown("**📦 실시간 거래량**")
    vol_fig = go.Figure(go.Bar(x=df.index, y=df['volume'], marker_color='gray', name='Volume'))
    vol_fig.update_layout(height=250, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(vol_fig, use_container_width=True)
with col_c2:
    st.markdown("**📉 RSI 지표**")
    rsi_fig = go.Figure()
    rsi_fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple'), name='RSI'))
    rsi_fig.add_hline(y=70, line_dash="dash", line_color="red")
    rsi_fig.add_hline(y=30, line_dash="dash", line_color="blue")
    rsi_fig.update_layout(height=250, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(rsi_fig, use_container_width=True)

# -----------------------------
# 7. 호가창 & 초고속 급등 탐지기 (NEW)
# -----------------------------
st.markdown("---")
col_f1, col_f2 = st.columns([1, 2])

with col_f1:
    st.subheader("📑 실시간 호가")
    orderbook = pyupbit.get_orderbook(ticker)
    if orderbook:
        units = orderbook['orderbook_units']
        ob_df = pd.DataFrame(units)
        ob_df = ob_df[['ask_price', 'ask_size', 'bid_price', 'bid_size']].head(10)
        ob_df.columns = ['매도호가', '매도잔량', '매수호가', '매수잔량']
        st.dataframe(ob_df, use_container_width=True, hide_index=True)

with col_f2:
    st.subheader("🚨 24H 급등 탐지기 (초고속)")
    st.markdown(f"**현재 설정:** 24시간 전 대비 가격 `{surge_price}%` 이상 상승")
    
    if st.button("🚀 전체 마켓 즉시 스캔 (1초 컷!)", use_container_width=True):
        all_tickers = list(coins_dict.values())
        
        # 110개 코인 티커를 쉼표(,)로 연결하여 한 번의 API 호출로 모두 가져옵니다.
        markets_str = ",".join(all_tickers)
        url = f"https://api.upbit.com/v1/ticker?markets={markets_str}"
        headers = {"accept": "application/json"}
        
        with st.spinner("데이터 불러오는 중..."):
            try:
                response = requests.get(url, headers=headers)
                data = response.json()
                
                surge_list = []
                for item in data:
                    # signed_change_rate는 소수점으로 나옴 (예: 0.05 = 5%)
                    change_pct = item['signed_change_rate'] * 100
                    
                    if change_pct >= surge_price:
                        # 딕셔너리에서 한글 이름 역추적
                        coin_ticker = item['market']
                        k_names = [k for k, v in coins_dict.items() if v == coin_ticker]
                        k_name = k_names[0].split(" ")[0] if k_names else coin_ticker
                        
                        surge_list.append({
                            "코인": k_name,
                            "상승률(%)": round(change_pct, 2),
                            "현재가(원)": item['trade_price'],
                            "24H거래대금(백만)": int(item['acc_trade_price_24h'] / 1000000)
                        })
                        
                surge_df = pd.DataFrame(surge_list)
                
                if not surge_df.empty:
                    st.success(f"🚨 {len(surge_df)}개의 급등 코인 발견!")
                    surge_df = surge_df.sort_values("상승률(%)", ascending=False)
                    # 거래대금 포맷팅 등 깔끔하게 출력
                    st.dataframe(surge_df.style.format({"상승률(%)": "{:.2f}%", "현재가(원)": "{:,.0f}", "24H거래대금(백만)": "{:,.0f}"}), use_container_width=True, hide_index=True)
                else:
                    st.info(f"현재 가격이 {surge_price}% 이상 상승한 코인이 없습니다.")
                    
            except Exception as e:
                st.error("업비트 서버에서 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.")

# -----------------------------
# 8. 최근 데이터 테이블
# -----------------------------
with st.expander("📄 상세 데이터 확인 (최근 5개 봉)"):
    st.table(df.tail())

# -----------------------------
# 9. 현재 시장 상태 분석
# -----------------------------
st.markdown("---")
st.subheader("🧠 현재 시장 상태 분석")

# 최신 데이터 가져오기
latest_rsi = df['RSI'].iloc[-1]

ma_short = df['MA_S'].iloc[-1]
ma_long = df['MA_L'].iloc[-1]

latest_volume = df['volume'].iloc[-1]
avg_volume = df['volume'].mean()

latest_close = df['close'].iloc[-1]

bb_upper = df['BB_H'].iloc[-1]
bb_lower = df['BB_L'].iloc[-1]

# -----------------------------
# RSI 분석
# -----------------------------
if latest_rsi >= 70:
    rsi_status = "과매수 상태"
elif latest_rsi <= 30:
    rsi_status = "과매도 상태"
else:
    rsi_status = "중립 상태"

# -----------------------------
# 이동평균선 분석
# -----------------------------
if ma_short > ma_long:
    trend_status = "단기 상승 추세"
else:
    trend_status = "단기 하락 추세"

# -----------------------------
# 거래량 분석
# -----------------------------
if latest_volume > avg_volume * 1.5:
    volume_status = "거래량 증가"
else:
    volume_status = "평균 거래량 수준"

# -----------------------------
# 볼린저 밴드 분석
# -----------------------------
if latest_close >= bb_upper:
    bb_status = "볼린저밴드 상단 돌파 (과열 가능성)"
elif latest_close <= bb_lower:
    bb_status = "볼린저밴드 하단 이탈 (반등 가능성)"
else:
    bb_status = "볼린저밴드 내부 움직임"

# -----------------------------
# 종합 분석
# -----------------------------
if latest_rsi >= 70 and ma_short > ma_long:
    final_status = "현재 상승 흐름이 강한 상태입니다."

elif latest_rsi <= 30:
    final_status = "과매도 구간으로 반등 가능성을 확인할 수 있습니다."

elif ma_short > ma_long:
    final_status = "현재 단기 상승 흐름이 유지되고 있습니다."

else:
    final_status = "현재 시장은 비교적 안정적인 흐름입니다."

# -----------------------------
# 출력
# -----------------------------
st.info(f"""
📌 RSI 분석
→ {rsi_status}

📌 이동평균선 분석
→ {trend_status}

📌 거래량 분석
→ {volume_status}

📌 볼린저밴드 분석
→ {bb_status}

📌 종합 분석
→ {final_status}
""")
