import streamlit as st
import pyupbit
import pandas as pd
import plotly.graph_objects as go
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
from streamlit_autorefresh import st_autorefresh
import time
import requests # 한글 코인명 가져오기 위해 추가

# -----------------------------
# 1. 페이지 설정 및 자동 새로고침
# -----------------------------
st.set_page_config(
    page_title="PRO 암호화폐 실시간 대시보드",
    layout="wide"
)

# 자동 새로고침 (모든 코인 스캔 시간을 고려해 30초로 조정)
st_autorefresh(interval=30000, key="refresh")

# -----------------------------
# 2. 사이드바 설정 (한글 코인명 검색 기능)
# -----------------------------
st.sidebar.title("🛠️ 설정")

# 업비트 전체 마켓 정보를 가져와 "한글명 (티커)" 형태로 딕셔너리 생성
@st.cache_data(ttl=3600)
def get_krw_coin_dict():
    url = "https://api.upbit.com/v1/market/all?isDetails=false"
    headers = {"accept": "application/json"}
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        # KRW 마켓만 필터링하여 딕셔너리 생성
        coin_dict = {f"{item['korean_name']} ({item['market']})": item['market'] for item in data if item['market'].startswith("KRW-")}
        return coin_dict
    except:
        # API 오류 시 기본값 반환
        return {"비트코인 (KRW-BTC)": "KRW-BTC", "이더리움 (KRW-ETH)": "KRW-ETH"}

coins_dict = get_krw_coin_dict()

# Streamlit의 selectbox는 기본적으로 텍스트 입력 검색을 지원합니다.
# 박스를 클릭하고 '비트코인' 또는 'BTC'를 타이핑하면 자동 검색됩니다.
selected_display_name = st.sidebar.selectbox("🔍 코인 검색 및 선택", list(coins_dict.keys()))

ticker = coins_dict[selected_display_name]
selected_korean_name = selected_display_name.split(" ")[0] # "비트코인" 부분만 추출

interval = st.sidebar.selectbox(
    "차트 주기(분봉/일봉)",
    ["minute1", "minute5", "minute15", "minute60", "day"],
    index=1  # 기본값 5분봉
)

st.sidebar.markdown("---")
st.sidebar.subheader("📈 지표 변수")
ma_short_val = st.sidebar.number_input("단기 이평선(MA)", value=5, min_value=1)
ma_long_val = st.sidebar.number_input("장기 이평선(MA)", value=20, min_value=1)
rsi_window = st.sidebar.number_input("RSI 기간", value=14, min_value=1)

# -----------------------------
# 3. 데이터 로딩 및 지표 계산
# -----------------------------
@st.cache_data(ttl=5)
def get_coin_data(ticker, interval):
    df = pyupbit.get_ohlcv(ticker=ticker, interval=interval, count=100)
    if df is not None:
        # 이평선
        df['MA_S'] = df['close'].rolling(ma_short_val).mean()
        df['MA_L'] = df['close'].rolling(ma_long_val).mean()
        # RSI
        df['RSI'] = RSIIndicator(close=df['close'], window=rsi_window).rsi()
        # 볼린저 밴드
        bb = BollingerBands(close=df['close'], window=20, window_dev=2)
        df['BB_H'] = bb.bollinger_hband()
        df['BB_L'] = bb.bollinger_lband()
    return df

df = get_coin_data(ticker, interval)
current_price = pyupbit.get_current_price(ticker)

# -----------------------------
# 4. 메인 화면 헤더 (상단 메트릭)
# -----------------------------
st.title(f"📊 {selected_korean_name}({ticker}) 실시간 분석")

col_m1, col_m2, col_m3, col_m4 = st.columns(4)
with col_m1:
    st.metric("현재가", f"{current_price:,.0f} 원")
with col_m2:
    high_24h = df['high'].max()
    st.metric("24H 최고가", f"{high_24h:,.0f} 원")
with col_m3:
    last_rsi = df['RSI'].iloc[-1]
    st.metric("RSI (14)", f"{last_rsi:.2f}")
with col_m4:
    vol_sum = df['volume'].sum()
    st.metric("최근 누적 거래량", f"{vol_sum:,.2f}")

# -----------------------------
# 5. 메인 차트 (캔들 + 볼린저밴드 + 이평선)
# -----------------------------
st.subheader("🕯️ 메인 기술적 분석 차트")

fig = go.Figure()

# 캔들차트
fig.add_trace(go.Candlestick(
    x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'],
    name='Candle'
))

# 볼린저 밴드 상/하단
fig.add_trace(go.Scatter(x=df.index, y=df['BB_H'], line=dict(color='rgba(173, 216, 230, 0.5)'), name='BB_Upper'))
fig.add_trace(go.Scatter(x=df.index, y=df['BB_L'], line=dict(color='rgba(173, 216, 230, 0.5)'), fill='tonexty', name='BB_Lower'))

# 이평선
fig.add_trace(go.Scatter(x=df.index, y=df['MA_S'], line=dict(color='orange', width=1), name=f'MA{ma_short_val}'))
fig.add_trace(go.Scatter(x=df.index, y=df['MA_L'], line=dict(color='blue', width=1), name=f'MA{ma_long_val}'))

fig.update_layout(height=500, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# 6. 하단 차트 레이아웃 (거래량 & RSI 가로 배치)
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
# 7. 호가창 & 전체 코인 급등 탐지
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
    st.subheader("🚨 실시간 급등 탐지 (전체 KRW 마켓)")
    
    @st.cache_data(ttl=30)
    def detect_surge_coins():
        # 이제 제한 없이 모든 원화 코인을 스캔합니다.
        all_tickers = list(coins_dict.values())
        surge_list = []
        
        for coin_ticker in all_tickers:
            try:
                temp_df = pyupbit.get_ohlcv(coin_ticker, interval="minute1", count=6)
                if temp_df is None or len(temp_df) < 6: continue
                
                change_rate = ((temp_df['close'].iloc[-1] - temp_df['close'].iloc[0]) / temp_df['close'].iloc[0]) * 100
                vol_rate = temp_df['volume'].iloc[-1] / temp_df['volume'].iloc[:-1].mean() if temp_df['volume'].iloc[:-1].mean() > 0 else 0
                
                if change_rate >= 2.0 and vol_rate >= 2.0:
                    # 딕셔너리 키(한글명 포함)를 찾아 매핑
                    korean_name = [k for k, v in coins_dict.items() if v == coin_ticker][0]
                    surge_list.append({
                        "코인": korean_name.split(" ")[0],
                        "상승률(%)": round(change_rate, 2),
                        "거래폭증": round(vol_rate, 1),
                        "현재가": temp_df['close'].iloc[-1]
                    })
                # 모든 코인을 스캔하므로 0.08초 대기로 IP 차단 방지 (총 10초 내외 소요)
                time.sleep(0.08) 
            except: continue
        return pd.DataFrame(surge_list)

    with st.spinner("전체 마켓 스캔 중..."):
        surge_df = detect_surge_coins()
        
    if not surge_df.empty:
        st.warning(f"🚨 {len(surge_df)}개의 급등 의심 코인이 발견되었습니다!")
        st.dataframe(surge_df.sort_values("상승률(%)", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("현재 급등 탐지된 코인이 없습니다.")

# -----------------------------
# 8. 최근 데이터 테이블
# -----------------------------
with st.expander("📄 상세 데이터 확인 (최근 5개 봉)"):
    st.table(df.tail())


