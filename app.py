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
st.set_page_config(page_title="실전 수익률 기반 세력선 분석기", layout="wide")

st.markdown("""
<style>
    .metric-card { background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 10px; border-left: 5px solid #ff4b4b; }
    .metric-value { font-size: 24px; font-weight: bold; color: #333; }
    .metric-label { font-size: 14px; color: #666; }
    .highlight-table { font-size: 14px; }
</style>
""", unsafe_allow_html=True)

st.title("💰 실전 수익률 기반: 세력선 정밀 분석기")
st.markdown("""
단순히 주가를 따라다니는 선이 아니라, **'닿으면 실제로 반등하여 수익을 준 선'**을 찾습니다.
(백테스팅 기준: 지지선 터치 매수 -> **5일 보유 후 매도** 가정)
""")

# -----------------------------------------------------------------------------
# 2. 사이드바 & 설정
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 백테스팅 설정")
    stock_code = st.text_input("종목코드", value="005930")
    start_date = st.date_input("시작일", datetime(2020, 1, 1))
    end_date = st.date_input("종료일", datetime.now())
    
    st.markdown("---")
    st.subheader("테스트 조건")
    holding_period = st.slider("매수 후 보유 기간 (일)", 1, 10, 5, help="지지선 터치 후 며칠 뒤에 팔았을 때를 기준으로 할까요?")
    min_ma = st.number_input("최소 이평선", value=5)
    max_ma = st.number_input("최대 이평선", value=120)
    
    run_btn = st.button("🚀 수익률 분석 실행", type="primary")

# -----------------------------------------------------------------------------
# 3. 데이터 및 지표 계산
# -----------------------------------------------------------------------------
def get_data_with_indicators(code, start, end):
    try:
        df = fdr.DataReader(code, start, end)
        if df.empty: return None
        
        # 1. 이평선 (주요 라인만 테스트하지 않고 범위 내 전체 테스트하되, 단기는 필터링 가능)
        # (여기서는 나중에 루프 돌며 계산)

        # 2. 볼린저밴드
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['Std'] = df['Close'].rolling(window=20).std()
        df['BB_Upper'] = df['MA20'] + (df['Std'] * 2)
        df['BB_Lower'] = df['MA20'] - (df['Std'] * 2)
        
        # 3. 일목균형표 (기준선, 선행스팬1, 선행스팬2)
        high_9 = df['High'].rolling(window=9).max()
        low_9 = df['Low'].rolling(window=9).min()
        df['Ichi_Tenkan'] = (high_9 + low_9) / 2

        high_26 = df['High'].rolling(window=26).max()
        low_26 = df['Low'].rolling(window=26).min()
        df['Ichi_Kijun'] = (high_26 + low_26) / 2

        df['Ichi_SpanA'] = ((df['Ichi_Tenkan'] + df['Ichi_Kijun']) / 2).shift(25)
        
        high_52 = df['High'].rolling(window=52).max()
        low_52 = df['Low'].rolling(window=52).min()
        df['Ichi_SpanB'] = ((high_52 + low_52) / 2).shift(25)
        
        # 4. 엔벨로프 (20일, 10% 지지선 - 낙폭과대용)
        df['Env_Lower'] = df['MA20'] * 0.90 

        return df
    except Exception as e:
        return None

# -----------------------------------------------------------------------------
# 4. 백테스팅 로직 ( 핵심: Profit Score )
# -----------------------------------------------------------------------------
def backtest_line(df, line_series, holding_days):
    # 로직: 저가가 라인을 터치(하거나 살짝 깸) -> 종가는 방어했거나, 혹은 터치한 날 매수했다고 가정
    # 매수가: 라인 가격 (지정가 매수 가정)
    # 매도가: N일 후 종가
    
    trades = []
    
    for i in range(len(df) - holding_days):
        date = df.index[i]
        low = df['Low'].iloc[i]
        line_price = line_series.iloc[i]
        
        if pd.isna(line_price): continue
        
        # 매수 조건: 주가가 라인 근처까지 내려왔을 때 (-2% ~ +0.5%)
        # 너무 위에 있으면 매수 안됨, 너무 폭락해서 뚫고 내려가버린건(3%이상 하락) 지지 실패로 간주
        if (line_price * 0.97 <= low <= line_price * 1.005):
            
            buy_price = line_price # 라인 가격에 샀다고 가정
            sell_price = df['Close'].iloc[i + holding_days] # N일 후 종가
            
            profit_rate = (sell_price - buy_price) / buy_price * 100
            trades.append(profit_rate)
            
    if not trades:
        return 0, 0, 0 # 거래 없음
    
    avg_return = np.mean(trades)
    win_rate = len([x for x in trades if x > 0]) / len(trades) * 100
    trade_count = len(trades)
    
    # 종합 점수 = 평균수익률 * (승률 보정)
    score = avg_return * (win_rate / 100)
    
    return score, avg_return, win_rate, trade_count

# -----------------------------------------------------------------------------
# 5. 메인 실행
# -----------------------------------------------------------------------------
if run_btn:
    with st.spinner('세력들이 수익을 낸 진짜 라인을 검증 중입니다...'):
        df = get_data_with_indicators(stock_code, start_date, end_date)
        
        if df is None:
            st.error("데이터 오류. 종목코드를 확인하세요.")
        else:
            # -------------------------------------------------------
            # [A] 지지선 후보 등록 및 대결
            # -------------------------------------------------------
            results = []
            
            # 1. 이동평균선 전수 조사
            for ma in range(min_ma, max_ma + 1):
                col_name = f'MA_{ma}'
                df[col_name] = df['Close'].rolling(window=ma).mean()
                score, ret, win, count = backtest_line(df, df[col_name], holding_period)
                
                if count >= 3: # 최소 3번 이상 매매 기회가 있었던 것만 인정
                    results.append({
                        '구분': '이동평균선',
                        '지표명': f'{ma}일선',
                        '종합점수': score,
                        '평균수익률(%)': round(ret, 2),
                        '승률(%)': round(win, 1),
                        '매매횟수': count,
                        'line_data': df[col_name]
                    })
            
            # 2. 보조지표 후보군
            indicators = [
                ('볼린저밴드 하단', df['BB_Lower']),
                ('일목균형표 기준선', df['Ichi_Kijun']),
                ('일목 구름대 상단(SpanA)', df['Ichi_SpanA']),
                ('일목 구름대 하단(SpanB)', df['Ichi_SpanB']),
                ('엔벨로프 하단(20, -10%)', df['Env_Lower'])
            ]
            
            for name, series in indicators:
                score, ret, win, count = backtest_line(df, series, holding_period)
                if count >= 3:
                    results.append({
                        '구분': '보조지표',
                        '지표명': name,
                        '종합점수': score,
                        '평균수익률(%)': round(ret, 2),
                        '승률(%)': round(win, 1),
                        '매매횟수': count,
                        'line_data': series
                    })

            # -------------------------------------------------------
            # [B] 결과 분석 및 선정
            # -------------------------------------------------------
            if not results:
                st.warning("설정된 조건에 맞는 지지 반등이 없었습니다. 이평선 범위를 늘려보세요.")
            else:
                res_df = pd.DataFrame(results).sort_values(by='평균수익률(%)', ascending=False)
                winner = res_df.iloc[0]
                
                st.success("분석 완료! 수익률 기반 최적의 지표를 찾았습니다.")

                # 요약 카드
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown(f"""
                    <div class='metric-card'>
                        <div class='metric-label'>🥇 수익률 1위 지지선</div>
                        <div class='metric-value' style='color:#e02a2a;'>{winner['지표명']}</div>
                        <div class='metric-label'>평균 수익률: <b>{winner['평균수익률(%)']}%</b></div>
                    </div>""", unsafe_allow_html=True)
                with c2:
                    st.markdown(f"""
                    <div class='metric-card'>
                        <div class='metric-label'>🎯 적중 확률 (승률)</div>
                        <div class='metric-value'>{winner['승률(%)']}%</div>
                        <div class='metric-label'>총 {winner['매매횟수']}번 기회 중 수익</div>
                    </div>""", unsafe_allow_html=True)
                with c3:
                    st.markdown(f"""
                    <div class='metric-card'>
                        <div class='metric-label'>🗓 검증 전략</div>
                        <div class='metric-value'>{holding_period}일 보유</div>
                        <div class='metric-label'>터치 후 {holding_period}일 뒤 매도 시</div>
                    </div>""", unsafe_allow_html=True)

                # -------------------------------------------------------
                # [C] 상세 분석 리포트 (Text Logic)
                # -------------------------------------------------------
                st.write("### 📝 AI 분석 리포트")
                
                analysis_text = f"""
                이 종목(**{stock_code}**)의 지난 흐름을 정밀 분석한 결과, 가장 돈이 되는 지지선은 **'{winner['지표명']}'** 입니다.
                
                1. **왜 이 선인가요?** - 단순히 닿은 횟수가 많은 선이 아니라, 닿았을 때 **평균적으로 {winner['평균수익률(%)']}% 상승**했기 때문입니다.
                   - 짧은 이평선(3, 5일선)이 잡히지 않았다는 것은, 이 종목이 잔파동보다는 **{winner['지표명']}** 부근까지 눌림목을 준 뒤에야 진짜 반등이 나온다는 뜻입니다.
                
                2. **실전 활용 가이드:**
                   - 향후 주가가 조정받을 때 **{winner['지표명']}** 가격대({int(winner['line_data'].iloc[-1]):,}원 부근)에 도달하면 분할 매수를 고려해볼 수 있습니다.
                   - 승률이 {winner['승률(%)']}% 이므로, 만약 이 선을 강하게 하향 이탈한다면 손절 계획도 필요합니다.
                """
                st.info(analysis_text)

                # -------------------------------------------------------
                # [D] 시각화 (Winner 시점 표시)
                # -------------------------------------------------------
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
                
                # 캔들
                fig.add_trace(go.Candlestick(x=df.index,
                                open=df['Open'], high=df['High'],
                                low=df['Low'], close=df['Close'],
                                name='주가'), row=1, col=1)
                
                # Winner Line
                fig.add_trace(go.Scatter(x=df.index, y=winner['line_data'], 
                                        line=dict(color='blue', width=2), 
                                        name=f"★ {winner['지표명']} (매수타점)"), row=1, col=1)

                # 거래량 (보조)
                fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='거래량', marker_color='lightgray'), row=2, col=1)

                fig.update_layout(height=600, xaxis_rangeslider_visible=False, title=f"'{winner['지표명']}' 지지 시뮬레이션")
                st.plotly_chart(fig, use_container_width=True)
                
                # -------------------------------------------------------
                # [E] 전체 순위표
                # -------------------------------------------------------
                st.write("### 📊 지표별 수익률 순위 (Top 10)")
                # 필요한 컬럼만 깔끔하게
                display_df = res_df[['구분', '지표명', '평균수익률(%)', '승률(%)', '매매횟수']].head(10)
                st.dataframe(display_df, hide_index=True)

