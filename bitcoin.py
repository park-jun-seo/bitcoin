import streamlit as st
import pyupbit
import pandas as pd
import plotly.graph_objects as go
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
from streamlit_autorefresh import st_autorefresh
import time
import requests

# -----------------------------
# 1. 페이지 설정 및 자동 새로고침
# -----------------------------
st.set_page_config(
    page_title="PRO 암호화폐 실시간 대시보드",
    layout="wide"
)

# 기본 차트 및 현재가 새로고침 (10초)
# (급등 스캔은 이제 버튼 수동 클릭이므로 자동 새로고침 주기를 줄여도 안전합니다)
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

# [NEW] 급등 탐지 조건 커스텀 설정
st.sidebar.markdown("---")
st.sidebar.subheader("🚨 급등 탐지 조건 (전일 대비)")
surge_price = st.sidebar.number_input("가격 상승률 기준 (%)", value=5.0, step=1.0)
surge_vol = st.sidebar.number_input("거래량 증가율 기준 (%)", value=20.0, step=5.0)
surge_logic = st.sidebar.radio("조건 결합 방식", ["둘 중 하나라도 (OR)", "둘 다 만족해야 (AND)"])

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
# 7. 호가창 & 수동 급등 탐지 (수정됨)
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
    st.subheader("🚨 전일 대비 급등 탐지기")
    st.markdown(f"**현재 설정:** 가격 `{surge_price}%` 이상 상승 **{surge_logic.split(' ')[0]}** 거래량 `{surge_vol}%` 이상 증가")
    
    # 버튼을 누를 때만 스캔이 작동하도록 변경 (UI 정지 현상 완벽 해결)
    if st.button("🚀 전체 마켓 스캔 시작 (약 15초 소요)", use_container_width=True):
        all_tickers = list(coins_dict.values())
        surge_list = []
        
        # 진행률을 보여주는 UI
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, coin_ticker in enumerate(all_tickers):
            try:
                # interval="day" 로 전일과 금일 데이터 2개 추출
                temp_df = pyupbit.get_ohlcv(coin_ticker, interval="day", count=2)
                
                if temp_df is not None and len(temp_df) >= 2:
                    prev_day = temp_df.iloc[0] # 전일 데이터
                    curr_day = temp_df.iloc[1] # 금일 (현재) 데이터
                    
                    # 1. 가격 상승률 계산 (%)
                    price_change = ((curr_day['close'] - prev_day['close']) / prev_day['close']) * 100
                    
                    # 2. 거래량 증가율 계산 (%)
                    if prev_day['volume'] > 0:
                        vol_change = ((curr_day['volume'] - prev_day['volume']) / prev_day['volume']) * 100
                    else:
                        vol_change = 0
                    
                    # 3. 사이드바 조건 체크
                    condition_met = False
                    if "OR" in surge_logic:
                        if price_change >= surge_price or vol_change >= surge_vol:
                            condition_met = True
                    else: # AND 조건
                        if price_change >= surge_price and vol_change >= surge_vol:
                            condition_met = True
                            
                    # 조건에 맞으면 리스트에 추가
                    if condition_met:
                        k_names = [k for k, v in coins_dict.items() if v == coin_ticker]
                        k_name = k_names[0].split(" ")[0] if k_names else coin_ticker
                        
                        surge_list.append({
                            "코인": k_name,
                            "가격상승(%)": round(price_change, 2),
                            "거래량증가(%)": round(vol_change, 2),
                            "현재가(원)": curr_day['close']
                        })
            except Exception as e:
                pass
            
            # 로딩바 업데이트 및 API 차단(IP 밴) 방지 딜레이
            progress_bar.progress((i + 1) / len(all_tickers))
            status_text.text(f"스캔 진행 중... ({i+1}/{len(all_tickers)})")
            time.sleep(0.12) 
            
        # 스캔 완료 후 로딩바 지우기
        progress_bar.empty()
        status_text.empty()
        
        # 결과 출력
        surge_df = pd.DataFrame(surge_list)
        if not surge_df.empty:
            st.success(f"🚨 {len(surge_df)}개의 급등 코인 발견!")
            # 가격 상승률 기준으로 내림차순 정렬
            surge_df = surge_df.sort_values("가격상승(%)", ascending=False)
            st.dataframe(surge_df, use_container_width=True, hide_index=True)
        else:
            st.info("현재 설정한 조건에 만족하는 코인이 없습니다.")

# -----------------------------
# 8. 최근 데이터 테이블
# -----------------------------
with st.expander("📄 상세 데이터 확인 (최근 5개 봉)"):
    st.table(df.tail())
