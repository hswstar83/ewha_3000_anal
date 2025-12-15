import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# -----------------------------------------------------------------------------
# 1. 페이지 설정
# -----------------------------------------------------------------------------
st.set_page_config(page_title="하이브리드 정밀 분석기", layout="wide")

st.markdown("""
<style>
    .metric-card { background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 10px; }
    .metric-value { font-size: 24px; font-weight: bold; color: #333; }
    .metric-label { font-size: 14px; color: #666; }
</style>
""", unsafe_allow_html=True)

st.title("🔬 작전주 하이브리드 정밀 분석기")
st.markdown("이평선, 볼린저밴드, 일목균형표 중 **누가 진짜 지지선**이었는지 수치로 검증합니다.")

# -----------------------------------------------------------------------------
# 2. 사이드바 & 설정
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 분석 파라미터")
    stock_code = st.text_input("종목코드", value="005930")
    start_date = st.date_input("시작일", datetime(2020, 1, 1))
    end_date = st.date_input("종료일", datetime.now())
    
    st.markdown("---")
    st.subheader("지지선 테스트 후보군")
    st.info("아래 지표들을 모두 경쟁시켜 1등을 찾습니다.")
    st.write("✅ 이동평균선 (3일~60일)")
    st.write("✅ 볼린저밴드 하단선")
    st.write("✅ 일목균형표 기준선/전환선")
    st.write("✅ 일목균형표 선행스팬1/2 (구름대)")
    
    run_btn = st.button("🚀 정밀 분석 실행", type="primary")

# -----------------------------------------------------------------------------
# 3. 지표 계산 함수 (수치화 강화)
# -----------------------------------------------------------------------------
def calculate_indicators(df):
    # 1. 볼린저밴드 & 밴드폭(Bandwidth)
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['StdDev'] = df['Close'].rolling(window=20).std()
    df['BB_Upper'] = df['MA20'] + (df['StdDev'] * 2)
    df['BB_Lower'] = df['MA20'] - (df['StdDev'] * 2)
    # 밴드폭 수치화: (상단-하단)/중심 (값이 작을수록 응축)
    df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['MA20']

    # 2. 일목균형표
    high_9 = df['High'].rolling(window=9).max()
    low_9 = df['Low'].rolling(window=9).min()
    df['Ichi_Tenkan'] = (high_9 + low_9) / 2 # 전환선

    high_26 = df['High'].rolling(window=26).max()
    low_26 = df['Low'].rolling(window=26).min()
    df['Ichi_Kijun'] = (high_26 + low_26) / 2 # 기준선

    df['Ichi_SpanA'] = ((df['Ichi_Tenkan'] + df['Ichi_Kijun']) / 2).shift(25)
    
    high_52 = df['High'].rolling(window=52).max()
    low_52 = df['Low'].rolling(window=52).min()
    df['Ichi_SpanB'] = ((high_52 + low_52) / 2).shift(25)

    # 3. OBV & OBV 기울기(Slope)
    # 방향: 1(상승), -1(하락), 0(보합)
    direction = np.where(df['Close'] > df['Close'].shift(1), 1, 
                np.where(df['Close'] < df['Close'].shift(1), -1, 0))
    df['OBV'] = (direction * df['Volume']).fillna(0).cumsum()
    
    # OBV 5일 기울기 (최근 5일간 OBV가 얼마나 가파르게 변했나)
    df['OBV_Slope'] = df['OBV'].diff(5) 
    
    return df

# -----------------------------------------------------------------------------
# 4. 분석 엔진 (Hybrid Scoring)
# -----------------------------------------------------------------------------
if run_btn:
    with st.spinner('모든 지표를 대조하여 최적의 지지선을 찾는 중...'):
        # 데이터 수집
        try:
            df = fdr.DataReader(stock_code, start_date, end_date)
            if df.empty: raise Exception("Empty Data")
            df = calculate_indicators(df)
        except Exception as e:
            st.error(f"데이터 오류: {e}")
            st.stop()

        # -------------------------------------------------------
        # [A] 지지선 올림픽 (Support Championship)
        # -------------------------------------------------------
        candidates = {}
        
        # 1. 이평선 후보 등록 (3~60일)
        for ma in range(3, 61):
            col_name = f'MA_{ma}'
            df[col_name] = df['Close'].rolling(window=ma).mean()
            candidates[f'{ma}일 이평선'] = df[col_name]
            
        # 2. 보조지표 후보 등록
        candidates['볼린저밴드 하단'] = df['BB_Lower']
        candidates['일목 기준선'] = df['Ichi_Kijun']
        candidates['일목 구름대 상단(SpanA)'] = df['Ichi_SpanA']
        candidates['일목 구름대 하단(SpanB)'] = df['Ichi_SpanB']
        
        # 3. 지지력 테스트 실행
        scores = []
        
        for name, series in candidates.items():
            success_count = 0
            valid_days = 0
            
            for idx, row in df.iterrows():
                line_val = row[name] if name in row else series[idx] # Series 접근 처리
                
                if pd.isna(line_val): continue
                valid_days += 1
                
                # 지지 조건: 저가가 라인 근처(-2% ~ +1%)까지 내려왔으나
                # 종가는 라인 위에서 마감했는가?
                if (line_val * 0.98 <= row['Low'] <= line_val * 1.01) and (row['Close'] >= line_val):
                    success_count += 1
            
            # 점수 기록
            scores.append({
                '지표명': name,
                '지지횟수': success_count,
                '적중률': round((success_count / valid_days * 100), 2) if valid_days > 0 else 0
            })
            
        # 순위 산정
        rank_df = pd.DataFrame(scores).sort_values(by='지지횟수', ascending=False)
        winner = rank_df.iloc[0] # 1등 지표
        winner_name = winner['지표명']

        # -------------------------------------------------------
        # [B] 수치 정밀 분석 리포트
        # -------------------------------------------------------
        st.success("분석 완료! 정밀 리포트를 생성했습니다.")
        
        # 최신 데이터 기준 수치
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-label'>🏆 최적의 지지선(Winner)</div>
                <div class='metric-value' style='color:#e02a2a;'>{winner_name}</div>
                <div class='metric-label'>지지성공: {winner['지지횟수']}회</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col2:
            # 밴드폭 평가
            width_status = "보통"
            if last_row['BB_Width'] < 0.10: width_status = "🔥 초극도로 좁음 (폭발임박)"
            elif last_row['BB_Width'] < 0.20: width_status = "⚠️ 매우 좁음 (주시)"
            
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-label'>📊 볼린저 밴드폭 (Squeeze)</div>
                <div class='metric-value'>{last_row['BB_Width']:.4f}</div>
                <div class='metric-label'>{width_status}</div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            # OBV 기울기 평가
            obv_diff = last_row['OBV'] - prev_row['OBV']
            obv_sign = "🔺 증가" if obv_diff > 0 else "🔻 감소"
            
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-label'>🌊 OBV 거래량 추세</div>
                <div class='metric-value'>{int(last_row['OBV']):,}</div>
                <div class='metric-label'>전일대비 {obv_sign} ({int(obv_diff):,})</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col4:
            # 일목균형표 위치
            ichi_pos = "구름대 안 (혼조)"
            if last_row['Close'] > max(last_row['Ichi_SpanA'], last_row['Ichi_SpanB']):
                ichi_pos = "🌤 구름대 위 (상승추세)"
            elif last_row['Close'] < min(last_row['Ichi_SpanA'], last_row['Ichi_SpanB']):
                ichi_pos = "🌧 구름대 아래 (하락추세)"
                
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-label'>☁️ 일목균형표 위치값</div>
                <div class='metric-value'>{ichi_pos}</div>
                <div class='metric-label'>기준선: {int(last_row['Ichi_Kijun']):,}원</div>
            </div>
            """, unsafe_allow_html=True)

        # -------------------------------------------------------
        # [C] 시각화 (Winner 위주로 그리기)
        # -------------------------------------------------------
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.05, row_heights=[0.7, 0.3],
                            subplot_titles=(f"주가와 1등 지지선 ({winner_name})", "OBV 거래량 지표"))

        # 1. 캔들
        fig.add_trace(go.Candlestick(x=df.index,
                        open=df['Open'], high=df['High'],
                        low=df['Low'], close=df['Close'],
                        name='주가'), row=1, col=1)

        # 2. 1등 지표 그리기
        # candidates 딕셔너리에 있는 시리즈를 그대로 가져와서 그림
        if winner_name in candidates:
            fig.add_trace(go.Scatter(x=df.index, y=candidates[winner_name], 
                                     line=dict(color='blue', width=2), 
                                     name=f'★ {winner_name} (Winner)'), row=1, col=1)

        # 3. 보조: 볼린저밴드가 1등이 아니더라도 참고용으로 연하게 표시
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_Upper'],
                                 line=dict(color='gray', width=1, dash='dot'),
                                 name='볼린저 상단'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_Lower'],
                                 line=dict(color='gray', width=1, dash='dot'),
                                 name='볼린저 하단'), row=1, col=1)

        # 4. OBV
        fig.add_trace(go.Scatter(x=df.index, y=df['OBV'],
                                 line=dict(color='purple', width=2),
                                 name='OBV'), row=2, col=1)

        fig.update_layout(height=800, xaxis_rangeslider_visible=False)
        
        st.write("### 📈 종합 분석 차트")
        st.plotly_chart(fig, use_container_width=True)
        
        st.write("### 📋 지지선 적중률 전체 순위")
        st.dataframe(rank_df.head(10), hide_index=True)
