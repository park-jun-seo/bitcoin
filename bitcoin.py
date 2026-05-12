import streamlit as st
import pyupbit
import pandas as pd
import plotly.graph_objects as go
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
import requests
import html
import json
import os
import streamlit.components.v1 as components

# -----------------------------
# 가격 포맷팅 헬퍼 함수
# -----------------------------
def format_price(price):
    if price >= 100:
        return f"{price:,.0f}"
    elif price >= 1:
        return f"{price:,.2f}"
    else:
        return f"{price:,.4f}"

# -----------------------------
# 1. 페이지 설정
# -----------------------------
st.set_page_config(
    page_title="PRO 암호화폐 실시간 대시보드",
    layout="wide"
)

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

# --- 관심종목 설정 ---
st.sidebar.subheader("⭐ 관심종목 설정")
all_options = list(coins_dict.keys())
safe_defaults = [coin for coin in ["비트코인 (KRW-BTC)", "리플 (KRW-XRP)"] if coin in all_options]

watchlist_names = st.sidebar.multiselect(
    "자주 보는 코인을 등록해두세요.", 
    options=all_options,
    default=safe_defaults
)

# 관심종목 클릭 이동
if watchlist_names:
    for name in watchlist_names:
        coin_ticker = coins_dict[name]
        coin_name = name.split(" ")[0]

        if st.sidebar.button(
            f"🔴 {coin_name}",
            key=f"watch_{coin_ticker}",
            use_container_width=True
        ):
            st.session_state.selected_coin_name = name
            st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("🔍 코인 검색")

# 검색 모드 라디오 버튼
search_mode = st.sidebar.radio("검색 모드", ["전체 코인에서 찾기", "관심종목에서 찾기"])

if search_mode == "관심종목에서 찾기":
    if not watchlist_names:
        st.sidebar.warning("등록된 관심종목이 없어 전체 목록을 표시합니다.")
        display_list = all_options
    else:
        display_list = watchlist_names
else:
    display_list = all_options

default_coin = st.session_state.get(
    "selected_coin_name",
    display_list[0]
)

if default_coin not in display_list:
    default_coin = display_list[0]

selected_display_name = st.sidebar.selectbox(
    "분석할 코인을 선택하세요",
    display_list,
    index=display_list.index(default_coin)
)
ticker = coins_dict[selected_display_name]
selected_korean_name = selected_display_name.split(" ")[0]
coin_symbol = ticker.split('-')[1]

interval = st.sidebar.selectbox(
    "차트 주기(분봉/일봉)",
    ["minute1", "minute5", "minute15", "minute60", "day"],
    index=1
)

st.sidebar.markdown("---")
st.sidebar.subheader("🚨 급등 탐지 조건 (24H 기준)")
surge_price = st.sidebar.number_input("가격 상승률 기준 (%)", value=5.0, step=1.0)

CLIENT_ID = "WkWFhEYqUpNeMPxD2L8W"
CLIENT_SECRET = "I8DdAQGce_"

# -----------------------------
# 3. 데이터 로딩 및 지표 계산
# -----------------------------
@st.cache_data(ttl=5)
def get_coin_data(ticker, interval):
    df = pyupbit.get_ohlcv(ticker=ticker, interval=interval, count=100)
    if df is not None:
        df['MA_S'] = df['close'].rolling(5).mean()
        df['MA_L'] = df['close'].rolling(20).mean()
        df['RSI'] = RSIIndicator(close=df['close'], window=14).rsi()
        bb = BollingerBands(close=df['close'], window=20, window_dev=2)
        df['BB_H'] = bb.bollinger_hband()
        df['BB_L'] = bb.bollinger_lband()
    return df

@st.cache_data(ttl=300)
def get_news(query):
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {"X-Naver-Client-Id": CLIENT_ID, "X-Naver-Client-Secret": CLIENT_SECRET}
    params = {"query": query, "display": 5, "sort": "date"}
    try:
        response = requests.get(url, headers=headers, params=params)
        return response.json()['items']
    except:
        return []

# ==========================================
# 4. 실시간 대시보드 (Fragment 구역)
# ==========================================
@st.fragment(run_every="10s")
def render_realtime_dashboard():
    df = get_coin_data(ticker, interval)
    current_price = pyupbit.get_current_price(ticker)

    st.title(f"📊 {selected_korean_name}({ticker}) 실시간 분석")
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric("현재가", f"{format_price(current_price)} 원")
    with col_m2:
        st.metric("최근 최고가", f"{format_price(df['high'].max())} 원")
    with col_m3:
        st.metric("RSI (14)", f"{df['RSI'].iloc[-1]:.2f}")
    with col_m4:
        st.metric("최근 누적 거래량", f"{df['volume'].sum():,.2f}")

    st.subheader("🕯️ 메인 기술적 분석 차트")
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='Candle'))
    fig.add_trace(go.Scatter(x=df.index, y=df['BB_H'], line=dict(color='rgba(173, 216, 230, 0.5)'), name='BB_Upper'))
    fig.add_trace(go.Scatter(x=df.index, y=df['BB_L'], line=dict(color='rgba(173, 216, 230, 0.5)'), fill='tonexty', name='BB_Lower'))
    fig.add_trace(go.Scatter(x=df.index, y=df['MA_S'], line=dict(color='orange', width=1), name='MA5'))
    fig.add_trace(go.Scatter(x=df.index, y=df['MA_L'], line=dict(color='blue', width=1), name='MA20'))
    fig.update_layout(height=500, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        # [수정] 제목 짤림 현상을 막기 위해 차트 내부 title 속성 대신 st.markdown 사용
        st.markdown("**📦 실시간 거래량**")
        vol_fig = go.Figure(go.Bar(x=df.index, y=df['volume'], marker_color='gray', name='Volume'))
        vol_fig.update_layout(height=250, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(vol_fig, use_container_width=True)
    with col_c2:
        # [수정] 제목 짤림 현상을 막기 위해 차트 내부 title 속성 대신 st.markdown 사용
        st.markdown("**📉 RSI 지표**")
        rsi_fig = go.Figure(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple'), name='RSI'))
        rsi_fig.add_hline(y=70, line_dash="dash", line_color="red")
        rsi_fig.add_hline(y=30, line_dash="dash", line_color="blue")
        rsi_fig.update_layout(height=250, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(rsi_fig, use_container_width=True)

    # -----------------------------
    # 업비트 스타일 호가창
    # -----------------------------
    st.markdown("---")
    st.subheader("📑 실시간 호가 (업비트 스타일)")
    
    orderbook = pyupbit.get_orderbook(ticker)
    
    try:
        ticker_info = requests.get(f"https://api.upbit.com/v1/ticker?markets={ticker}").json()[0]
        recent_trades = requests.get(f"https://api.upbit.com/v1/trades/ticks?market={ticker}&count=14").json()
        
        if orderbook:
            prev_close = ticker_info['prev_closing_price']
            units = orderbook['orderbook_units']
            asks = units[::-1]
            bids = units
            
            max_size = max([u['ask_size'] for u in asks] + [u['bid_size'] for u in bids])
            row_h = 32

            # [수정] max-width 추가 (화면 꽉 차지 않고 왼쪽 정렬), 스크롤바 디자인 추가
            html_str = f'''
            <!DOCTYPE html>
            <html>
            <head>
            <style>
                /* 커스텀 스크롤바 디자인 */
                ::-webkit-scrollbar {{ width: 8px; }}
                ::-webkit-scrollbar-track {{ background: #f1f1f4; }}
                ::-webkit-scrollbar-thumb {{ background: #d1d5db; border-radius: 4px; }}
                ::-webkit-scrollbar-thumb:hover {{ background: #9ca3af; }}
                
                body {{ margin: 0; font-family: 'Malgun Gothic', dotum, sans-serif; font-size: 12px; color: #333; }}
                /* max-width: 850px 추가로 왼쪽 치우침 유지 */
                .ob-wrap {{ display: flex; width: 100%; max-width: 850px; border-top: 2px solid #115dcb; border-bottom: 1px solid #d3d6dc; background: white; }}
                .col {{ flex: 1; display: flex; flex-direction: column; }}
                .col-center {{ flex: 1; border-left: 1px solid #f1f1f4; border-right: 1px solid #f1f1f4; }}
                .row {{ height: {row_h}px; display: flex; align-items: center; position: relative; }}
                .ask-bg {{ background-color: #eef2fb; }}
                .bid-bg {{ background-color: #fdf0f0; }}
                .ask-bar {{ position: absolute; right: 0; top: 2px; bottom: 2px; background-color: #cddbf6; z-index: 1; }}
                .bid-bar {{ position: absolute; left: 0; top: 2px; bottom: 2px; background-color: #f6d8d8; z-index: 1; }}
                .val {{ z-index: 2; padding: 0 10px; width: 100%; display: flex; align-items: center; }}
                .up {{ color: #c84a31; }}
                .down {{ color: #1261c4; }}
                .info-box {{ height: {row_h * 15}px; padding: 15px; font-size: 11px; display: flex; flex-direction: column; justify-content: center; border-bottom: 1px solid #f1f1f4; }}
                .info-row {{ display: flex; justify-content: space-between; margin-bottom: 8px; }}
                .trade-header {{ height: {row_h}px; display: flex; align-items: center; justify-content: space-between; padding: 0 10px; background-color: #f8f8f8; border-top: 1px solid #e1e1e1; border-bottom: 1px solid #e1e1e1; font-weight: bold; color: #666; }}
            </style>
            </head>
            <body>
            <div class="ob-wrap">
                <div class="col">
            '''
            for ask in asks:
                w = min((ask['ask_size']/max_size)*100, 100) if max_size > 0 else 0
                html_str += f'<div class="row"><div class="ask-bar" style="width:{w}%;"></div><div class="val" style="justify-content: flex-end;">{ask["ask_size"]:,.3f}</div></div>'
            
            html_str += '<div class="trade-header"><span>체결가</span><span>체결량</span></div>'
            for trade in recent_trades:
                color = "up" if trade['ask_bid'] == 'BID' else "down"
                html_str += f'<div class="row" style="padding: 0 10px; justify-content: space-between; border-bottom: 1px solid #f9f9f9;"><span class="{color}">{format_price(trade["trade_price"])}</span><span class="{color}">{trade["trade_volume"]:,.3f}</span></div>'
                
            html_str += '</div>'
            
            html_str += '<div class="col col-center">'
            for ask in asks:
                p = ask['ask_price']
                pct = (p - prev_close)/prev_close * 100
                c_class = "up" if p > prev_close else "down" if p < prev_close else ""
                html_str += f'<div class="row ask-bg"><div class="val {c_class}" style="justify-content: center; font-weight: bold;">{format_price(p)} <span style="font-weight: normal; font-size: 11px; margin-left: 8px;">{pct:+.2f}%</span></div></div>'
            
            for bid in bids:
                p = bid['bid_price']
                pct = (p - prev_close)/prev_close * 100
                c_class = "up" if p > prev_close else "down" if p < prev_close else ""
                html_str += f'<div class="row bid-bg"><div class="val {c_class}" style="justify-content: center; font-weight: bold;">{format_price(p)} <span style="font-weight: normal; font-size: 11px; margin-left: 8px;">{pct:+.2f}%</span></div></div>'
            html_str += '</div>'
            
            html_str += '<div class="col">'
            html_str += f'''
                <div class="info-box">
                    <div class="info-row"><span style="color:#666;">거래량</span><span>{ticker_info['acc_trade_volume_24h']:,.0f} <span style="font-size:9px; color:#999;">{coin_symbol}</span></span></div>
                    <div class="info-row"><span style="color:#666;">거래대금</span><span>{ticker_info['acc_trade_price_24h']/1000000:,.0f} <span style="font-size:9px; color:#999;">백만</span></span></div>
                    <div style="border-top:1px solid #f1f1f4; margin:10px 0;"></div>
                    <div class="info-row"><span style="color:#666;">52주 최고</span><span class="up">{format_price(ticker_info['highest_52_week_price'])}</span></div>
                    <div class="info-row"><span style="color:#666;">52주 최저</span><span class="down">{format_price(ticker_info['lowest_52_week_price'])}</span></div>
                    <div style="border-top:1px solid #f1f1f4; margin:10px 0;"></div>
                    <div class="info-row"><span style="color:#666;">전일종가</span><span>{format_price(prev_close)}</span></div>
                    <div class="info-row"><span style="color:#666;">당일고가</span><span class="up">{format_price(ticker_info['high_price'])}</span></div>
                    <div class="info-row"><span style="color:#666;">당일저가</span><span class="down">{format_price(ticker_info['low_price'])}</span></div>
                </div>
            '''
            for bid in bids:
                w = min((bid['bid_size']/max_size)*100, 100) if max_size > 0 else 0
                html_str += f'<div class="row"><div class="bid-bar" style="width:{w}%;"></div><div class="val" style="justify-content: flex-start;">{bid["bid_size"]:,.3f}</div></div>'
                
            html_str += '''
                </div>
            </div>
            </body>
            </html>
            '''
            
            # [수정] 높이를 600px로 줄이고 scrolling=True로 변경하여 컴팩트하게 스크롤 처리
            components.html(html_str, height=600, scrolling=True)
            
    except Exception as e:
        st.error("호가창 데이터를 불러오는 중 오류가 발생했습니다.")

render_realtime_dashboard()

# -----------------------------
# 5. 급등 탐지기 (정적 영역)
# -----------------------------
st.markdown("---")
st.subheader("🚨 24H 급등 탐지기")

if st.button("🚀 전체 마켓 즉시 스캔", use_container_width=True):
    all_tickers = list(coins_dict.values())
    markets_str = ",".join(all_tickers)
    url = f"https://api.upbit.com/v1/ticker?markets={markets_str}"
    
    with st.spinner("데이터 스캔 중..."):
        try:
            response = requests.get(url, headers={"accept": "application/json"}).json()
            surge_list = []
            for item in response:
                change_pct = item['signed_change_rate'] * 100
                if change_pct >= surge_price:
                    k_names = [k for k, v in coins_dict.items() if v == item['market']]
                    k_name = k_names[0].split(" ")[0] if k_names else item['market']
                    surge_list.append({
                        "코인": k_name,
                        "상승률(%)": round(change_pct, 2),
                        "현재가(원)": item['trade_price'],
                        "24H거래대금(백만)": int(item['acc_trade_price_24h'] / 1000000)
                    })
            
            surge_df = pd.DataFrame(surge_list)
            if not surge_df.empty:
                st.success(f"🚨 {len(surge_df)}개의 급등 코인 발견! (기준: {surge_price}%)")
                st.dataframe(surge_df.sort_values("상승률(%)", ascending=False).style.format({"상승률(%)": "{:.2f}%", "현재가(원)": "{:,.0f}", "24H거래대금(백만)": "{:,.0f}"}), use_container_width=True, hide_index=True)
            else:
                st.info(f"현재 가격이 {surge_price}% 이상 상승한 코인이 없습니다.")
        except:
            st.error("데이터를 불러오지 못했습니다.")

# -----------------------------
# 6. 가상화폐 모의투자
# -----------------------------
st.markdown("---")
st.subheader("💰 가상화폐 모의투자")

SAVE_FILE = "mock_trading_data.json"
INITIAL_CASH = 100_000_000

def load_mock_data():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {"cash": INITIAL_CASH, "holdings": {}, "trade_history": []}

def save_mock_data():
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump({"cash": st.session_state.cash, "holdings": st.session_state.holdings, "trade_history": st.session_state.trade_history}, f, ensure_ascii=False, indent=4)

if "cash" not in st.session_state:
    data = load_mock_data()
    st.session_state.cash = data["cash"]
    st.session_state.holdings = data["holdings"]
    st.session_state.trade_history = data["trade_history"]

coin_amount = st.session_state.holdings.get(ticker, 0)
total_coin_value = sum(amt * pyupbit.get_current_price(t) for t, amt in st.session_state.holdings.items() if pyupbit.get_current_price(t))
total_asset = st.session_state.cash + total_coin_value
profit_loss = total_asset - INITIAL_CASH
profit_rate = (profit_loss / INITIAL_CASH) * 100

col1, col2, col3, col4 = st.columns(4)
col1.metric("보유 현금", f"{st.session_state.cash:,.0f} 원")
col2.metric(f"{selected_korean_name} 보유 수량", f"{coin_amount:.6f} 개")
col3.metric("총 평가 자산", f"{total_asset:,.0f} 원", f"{profit_loss:,.0f} 원")
col4.metric("수익률", f"{profit_rate:.2f}%", f"{profit_loss:,.0f} 원")

st.markdown("### 🛒 매수 / 매도")
col_buy, col_sell = st.columns(2)

with col_buy:
    buy_money = st.number_input("매수 금액 입력", min_value=0, step=10000, key="buy_money")
    if st.button("🚀 매수하기", use_container_width=True):
        real_time_price = pyupbit.get_current_price(ticker)
        if buy_money <= 0: st.warning("매수 금액을 입력하세요.")
        elif buy_money > st.session_state.cash: st.error("보유 현금이 부족합니다.")
        else:
            buy_amount = buy_money / real_time_price
            st.session_state.cash -= buy_money
            st.session_state.holdings[ticker] = coin_amount + buy_amount
            st.session_state.trade_history.append({"구분": "매수", "코인": selected_korean_name, "티커": ticker, "가격": real_time_price, "금액": buy_money, "수량": buy_amount})
            save_mock_data()
            st.success(f"{selected_korean_name} {buy_amount:.6f}개 매수 완료")
            st.rerun()

with col_sell:
    sell_amount = st.number_input("매도 수량 입력", min_value=0.0, step=0.0001, key="sell_amount")
    if st.button("📉 매도하기", use_container_width=True):
        real_time_price = pyupbit.get_current_price(ticker)
        if sell_amount <= 0: st.warning("매도 수량을 입력하세요.")
        elif sell_amount > coin_amount: st.error("보유 수량이 부족합니다.")
        else:
            sell_money = sell_amount * real_time_price
            st.session_state.cash += sell_money
            st.session_state.holdings[ticker] = coin_amount - sell_amount
            st.session_state.trade_history.append({"구분": "매도", "코인": selected_korean_name, "티커": ticker, "가격": real_time_price, "금액": sell_money, "수량": sell_amount})
            save_mock_data()
            st.success(f"{selected_korean_name} {sell_amount:.6f}개 매도 완료")
            st.rerun()

with st.expander("📄 상세 거래 내역 보기"):
    if st.session_state.trade_history:
        st.dataframe(pd.DataFrame(st.session_state.trade_history), use_container_width=True, hide_index=True)
    else:
        st.info("아직 거래 내역이 없습니다.")
    
    if st.button("모의투자 데이터 전체 초기화 (1억원 리셋)"):
        st.session_state.cash = INITIAL_CASH
        st.session_state.holdings = {}
        st.session_state.trade_history = []
        save_mock_data()
        st.rerun()

# -----------------------------
# 7. 실시간 뉴스
# -----------------------------
st.markdown("---")
st.subheader("📰 실시간 암호화폐 뉴스")
news_list = get_news(selected_korean_name + " 코인")
if news_list:
    for news in news_list[:5]:
        title = html.unescape(news['title']).replace("<b>", "").replace("</b>", "")
        desc = html.unescape(news['description']).replace("<b>", "").replace("</b>", "")
        st.markdown(f"""
        **{title}**  
        {desc}  
        <a href="{news['originallink']}" target="_blank" style="font-size: 13px; color: #1E90FF; text-decoration: none;">🔗 기사 보러가기</a>
        <hr style="margin-top: 10px; margin-bottom: 15px;">
        """, unsafe_allow_html=True)
else:
    st.info("뉴스를 불러오지 못했습니다.")
