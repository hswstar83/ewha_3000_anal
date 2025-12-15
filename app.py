import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# -----------------------------------------------------------------------------
# 1. 페이지 설정
# -----------------------------------------------------------------------------
st.set_page_config(page_title="세력선 & 보조지표 분석기", layout="wide")

st.markdown("""
<style>
    .big-font { font-size:24px !important; font-weight: bold; }
    .highlight { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

st.title("🕵️‍♀️ 주가 심층 분석기 (세력선 + 보조지표)")
st.markdown("최적의 **이동평균선(세력선)**을 찾고, **일목균형표/볼린저밴드/OBV**를 통해 세력의 움직임을 입체적으로 분석합니다.")

# -----------------------------------------------------------------------------
# 2. 사이드바 설정
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("🔍 분석 설정")
    
    # 종목 & 기간
    stock_code = st.text_input("종목코드", value="005930")
    start_date = st.date_input("시작일", datetime(2020, 1, 1))
    end_date = st.date_input("종료일", datetime.now())
    
    st.markdown("---")
    st.header("🛠 지표 설정")
    
    # 1) 이평선 찾기 설정
    st.subheader("1. 세력선(Best 이평선) 찾기")
    min_ma = st.number_input("최소 범위", value=3)
    max_ma = st.number_input("최대 범위", value=60)
    
    # 2) 보조지표 선택
    st.subheader("2. 차트에 표시할 지표")
    show_bollinger = st.checkbox("볼린저밴드 (변동성/지지저항)", value=True)
    show_ichimoku = st.checkbox("일목균형표 (구름대/추세)", value=False)
    show_obv = st.checkbox("OBV (거래량 매집 추적)", value=True)

    st.markdown("---")
    run_btn = st.button("🚀 종합 분석 시작", type="primary")

# -----------------------------------------------------------------------------
# 3. 데이터 계산 함수들
# -----------------------------------------------------------------------------

# 볼린저밴드 계산
def calculate_bollinger(df, window=20, num_std=2):
    df['BB_Mid'] = df['Close'].rolling(window=window).mean()
    df['BB_Std'] = df['Close'].rolling(window=window).std()
    df['BB_Upper'] = df['BB_Mid'] + (df['BB_Std'] * num_std)
    df['BB_Lower'] = df['BB_Mid'] - (df['BB_Std'] * num_std)
    return df

# 일목균형표 계산
def calculate_ichimoku(df):
    # 전환선 (9일)
    high_9 = df['High'].rolling(window=9).max()
    low_9 = df['Low'].rolling(window=9).min()
    df['Ichi_Tenkan'] = (high_9 + low_9) / 2

    # 기준선 (26일)
    high_26 = df['High'].rolling(window=26).max()
    low_26 = df['Low'].rolling(window=26).min()
    df['Ichi_Kijun'] = (high_26 + low_26) / 2

    # 선행스팬 A (26일 앞)
    df['Ichi_SpanA'] = ((df['Ichi_Tenkan'] + df['Ichi_Kijun']) / 2).shift(26)

    # 선행스팬 B (52일 고저평균 -> 26일 앞)
    high_52 = df['High'].rolling(window=52).max()
    low_52 = df['Low'].rolling(window=52).min()
    df['Ichi_SpanB'] = ((high_52 + low_52) / 2).shift(26)
    
    # 후행스팬 (현재 종가를 26일 뒤로) - 차트 표시는 생략하거나 필요시 추가
    return df

# OBV 계산
def calculate_obv(df):
    # OBV = 이전 OBV + (만약 상승시 거래량) - (만약 하락시 거래량)
    # numpy where를 써서 한번에 계산
    direction = np.where(df['Close'] > df['Close'].shift(1), 1, 
                np.where(df['Close'] < df['Close'].shift(1), -1, 0))
    df['OBV'] = (direction * df['Volume']).cumsum()
    return df

# -----------------------------------------------------------------------------
# 4. 메인 로직
# -----------------------------------------------------------------------------
if run_btn:
    with st.spinner('데이터 수집 및 지표 계산 중...'):
        try:
            df = fdr.DataReader(stock_code, start_date, end_date)
        except Exception as e:
            st.error(f"에러 발생: {e}")
            df = pd.DataFrame()

        if df.empty:
            st.error("데이터가 없습니다.")
        else:
            # --- [1] 지표 계산 ---
            # (A) 볼린저밴드
            if show_bollinger:
                df = calculate_bollinger(df)
            
            # (B) 일목균형표
            if show_ichimoku:
                df = calculate_ichimoku(df)
            
            # (C) OBV
            if show_obv:
                df = calculate_obv(df)

            # (D) Best 이평선 찾기 (기존 로직)
            scores = {}
            for ma in range(min_ma, max_ma + 1):
                col = f'MA_{ma}'
                df[col] = df['Close'].rolling(window=ma).mean()
                
                # 지지력 테스트
                count = 0
                for idx, row in df.iterrows():
                    if pd.isna(row[col]): continue
                    if (row[col]*0.98 <= row['Low'] <= row[col]*1.01) and (row['Close'] >= row[col]):
                        count += 1
                scores[ma] = count
            
            sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            best_ma = sorted_scores[0][0]
            best_count = sorted_scores[0][1]


            # --- [2] 결과 시각화 (Subplots 사용) ---
            
            # OBV를 켰으면 2줄짜리 차트, 아니면 1줄짜리 차트
            if show_obv:
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                    vertical_spacing=0.05, row_heights=[0.7, 0.3],
                                    subplot_titles=(f"주가 및 지표 ({best_ma}일선)", "OBV (매집 강도)"))
            else:
                fig = make_subplots(rows=1, cols=1, subplot_titles=(f"주가 및 지표 ({best_ma}일선)",))

            # 1. 캔들 차트 (Row 1)
            fig.add_trace(go.Candlestick(x=df.index,
                            open=df['Open'], high=df['High'],
                            low=df['Low'], close=df['Close'],
                            name='주가'), row=1, col=1)

            # 2. Best 이평선 (Row 1)
            fig.add_trace(go.Scatter(x=df.index, y=df[f'MA_{best_ma}'], 
                                     line=dict(color='black', width=2), 
                                     name=f'🏆 세력선 ({best_ma}일)'), row=1, col=1)

            # 3. 볼린저밴드 (Row 1)
            if show_bollinger:
                # 상단선
                fig.add_trace(go.Scatter(x=df.index, y=df['BB_Upper'],
                                         line=dict(color='rgba(0,0,255,0.2)', width=1),
                                         name='볼린저 상단'), row=1, col=1)
                # 하단선
                fig.add_trace(go.Scatter(x=df.index, y=df['BB_Lower'],
                                         line=dict(color='rgba(0,0,255,0.2)', width=1),
                                         fill='tonexty', # 상단선과 하단선 사이 채우기
                                         fillcolor='rgba(0,0,255,0.05)',
                                         name='볼린저 하단'), row=1, col=1)

            # 4. 일목균형표 (Row 1)
            if show_ichimoku:
                # 구름대 (Span A, Span B)
                fig.add_trace(go.Scatter(x=df.index, y=df['Ichi_SpanA'],
                                         line=dict(color='rgba(0, 255, 0, 0.3)', width=0),
                                         name='선행스팬1'), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['Ichi_SpanB'],
                                         line=dict(color='rgba(255, 0, 0, 0.3)', width=0),
                                         fill='tonexty', # 구름대 채우기
                                         fillcolor='rgba(0, 128, 0, 0.1)',
                                         name='선행스팬2(구름대)'), row=1, col=1)
                # 기준선
                fig.add_trace(go.Scatter(x=df.index, y=df['Ichi_Kijun'],
                                         line=dict(color='gray', width=1.5, dash='dash'),
                                         name='일목 기준선'), row=1, col=1)

            # 5. OBV 차트 (Row 2) - 선택했을 경우에만
            if show_obv:
                fig.add_trace(go.Scatter(x=df.index, y=df['OBV'],
                                         line=dict(color='purple', width=2),
                                         name='OBV'), row=2, col=1)

            # 레이아웃 설정
            fig.update_layout(height=800, xaxis_rangeslider_visible=False)
            
            # 화면 출력
            col1, col2 = st.columns([1, 3])
            
            with col1:
                st.success(f"분석 완료!")
                st.markdown(f"""
                <div class='highlight'>
                    <h3>🏆 최적의 세력선</h3>
                    <h1 style='color: #ff4b4b; margin:0;'>{best_ma}일선</h1>
                    <p>지지 횟수: <b>{best_count}회</b></p>
                </div>
                """, unsafe_allow_html=True)
                
                st.write("---")
                st.write("**지표 해석 팁:**")
                if show_obv:
                    st.info("**OBV(보라색):** 주가는 횡보하거나 떨어지는데 OBV가 계속 올라간다면? **'매집'** 신호일 수 있습니다.")
                if show_bollinger:
                    st.info("**볼린저밴드:** 폭이 좁아지는 '개미허리' 구간 이후에 시세 분출이 자주 일어납니다.")
                if show_ichimoku:
                    st.info("**일목균형표:** 주가가 구름대(음영) 위에 있으면 '상승 추세', 아래에 있으면 '하락 추세'로 봅니다.")

            with col2:
                st.plotly_chart(fig, use_container_width=True)

