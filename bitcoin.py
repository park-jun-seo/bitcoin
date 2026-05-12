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
# 2. 사이드바 설정 (지표 변수 제거됨)
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
st.sidebar.subheader("🚨 급등 탐지 조건 (24H 기준)")
surge_price = st.sidebar.number_input("가격 상승률 기준 (%)", value=5.0, step=1.0, help="24시간 전 대비 현재가 상승률입니다.")

# -----------------------------
# 3. 데이터 로딩 및 지표 계산 (기본값 고정)
# -----------------------------
@st.cache_data(ttl=5)
def get_coin_data(ticker, interval):
    df = pyupbit.get_ohlcv(ticker=ticker, interval=interval, count=100)
    if df is not None:
        # 단기 이평선 5, 장기 이평선 20으로 고정
        df['MA_S'] = df['close'].rolling(5).mean()
        df['MA_L'] = df['close'].rolling(20).mean()
        # RSI 14로 고정
        df['RSI'] = RSIIndicator(close=df['close'], window=14).rsi()
        # 볼린저 밴드 20, 2로 고정
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
fig.add_trace(go.Scatter(x=df.index, y=df['MA_S'], line=dict(color='orange', width=1), name='MA5'))
fig.add_trace(go.Scatter(x=df.index, y=df['MA_L'], line=dict(color='blue', width=1), name='MA20'))
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
# 7. 호가창 & 급등 탐지기
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
    st.subheader("🚨 24H 급등 탐지기")
    st.markdown(f"**현재 설정:** 24시간 전 대비 가격 `{surge_price}%` 이상 상승")
    
    if st.button("🚀 전체 마켓 즉시 스캔", use_container_width=True):
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
# 9. 가상화폐 모의투자
# -----------------------------
st.markdown("---")
st.subheader("💰 가상화폐 모의투자")

# 초기값 설정
if "cash" not in st.session_state:
    st.session_state.cash = 100_000_000   # 초기 자금 1천만 원

if "holdings" not in st.session_state:
    st.session_state.holdings = {}

if "trade_history" not in st.session_state:
    st.session_state.trade_history = []

# 현재 선택 코인 보유 수량
coin_amount = st.session_state.holdings.get(ticker, 0)

# 평가금액 계산
coin_value = coin_amount * current_price
total_asset = st.session_state.cash + coin_value

# 수익/손실 계산
initial_cash = 100_000_000
profit_loss = total_asset - initial_cash
profit_rate = (profit_loss / initial_cash) * 100

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("보유 현금", f"{st.session_state.cash:,.0f} 원")

with col2:
    st.metric(f"{selected_korean_name} 보유 수량", f"{coin_amount:.6f} 개")

with col3:
    st.metric(
        "총 평가 자산",
        f"{total_asset:,.0f} 원",
        f"{profit_loss:,.0f} 원"
    )

with col4:
    st.metric(
        "수익률",
        f"{profit_rate:.2f}%",
        f"{profit_loss:,.0f} 원"
    )
st.markdown("### 🛒 매수 / 매도")

col_buy, col_sell = st.columns(2)

# 매수
with col_buy:
    st.markdown("#### 매수")
    buy_money = st.number_input(
        "매수 금액 입력",
        min_value=0,
        step=10000,
        key="buy_money"
    )

    if st.button("매수하기"):
        if buy_money <= 0:
            st.warning("매수 금액을 입력하세요.")

        elif buy_money > st.session_state.cash:
            st.error("보유 현금이 부족합니다.")

        else:
            buy_amount = buy_money / current_price

            st.session_state.cash -= buy_money
            st.session_state.holdings[ticker] = coin_amount + buy_amount

            st.session_state.trade_history.append({
                "구분": "매수",
                "코인": selected_korean_name,
                "티커": ticker,
                "가격": current_price,
                "금액": buy_money,
                "수량": buy_amount
            })

            st.success(f"{selected_korean_name} {buy_amount:.6f}개 매수 완료")

# 매도
with col_sell:
    st.markdown("#### 매도")
    sell_amount = st.number_input(
        "매도 수량 입력",
        min_value=0.0,
        step=0.0001,
        key="sell_amount"
    )

    if st.button("매도하기"):
        if sell_amount <= 0:
            st.warning("매도 수량을 입력하세요.")

        elif sell_amount > coin_amount:
            st.error("보유 수량이 부족합니다.")

        else:
            sell_money = sell_amount * current_price

            st.session_state.cash += sell_money
            st.session_state.holdings[ticker] = coin_amount - sell_amount

            st.session_state.trade_history.append({
                "구분": "매도",
                "코인": selected_korean_name,
                "티커": ticker,
                "가격": current_price,
                "금액": sell_money,
                "수량": sell_amount
            })

            st.success(f"{selected_korean_name} {sell_amount:.6f}개 매도 완료")

# 거래 내역
st.markdown("### 📄 거래 내역")

if st.session_state.trade_history:
    history_df = pd.DataFrame(st.session_state.trade_history)
    st.dataframe(history_df, use_container_width=True, hide_index=True)
else:
    st.info("아직 거래 내역이 없습니다.")

# 초기화 버튼
if st.button("모의투자 초기화"):
    st.session_state.cash = 100_000_000
    st.session_state.holdings = {}
    st.session_state.trade_history = []
    st.success("모의투자 데이터가 초기화되었습니다.")
