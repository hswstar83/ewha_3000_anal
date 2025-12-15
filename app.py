import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# -----------------------------------------------------------------------------
# 1. 페이지 설정 및 디자인
# -----------------------------------------------------------------------------
st.set_page_config(page_title="작전주 세력선 추적기", layout="wide")

st.markdown("""
<style>
    .big-font { font-size:24px !important; font-weight: bold; }
    .highlight { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

st.title("🕵️‍♀️ 작전주 비밀 세력선(이평선) 추적기")
st.markdown("과거 급등주(작전주)들이 **어떤 이동평균선을 밟고 올라갔는지** 디테일하게 역추적합니다.")
st.markdown("---")

# -----------------------------------------------------------------------------
# 2. 사이드바 (사용자 입력)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("🔍 분석 설정")
    
    # 종목코드 입력 (기본값: 이화공영 001840)
    stock_code = st.text_input("종목코드 (예: 001840)", value="001840")
    
    # 날짜 입력 (기본값: 2007년 이화공영 대시세 구간)
    start_date = st.date_input("시작일", datetime(2007, 1, 1))
    end_date = st.date_input("종료일", datetime(2007, 12, 31))
    
    st.markdown("---")
    st.subheader("이평선 테스트 범위")
    st.write("3일선부터 60일선까지 전부 대입해서 가장 잘 맞는 선을 찾습니다.")
    min_ma = st.number_input("최소 이평선", value=3, min_value=1)
    max_ma = st.number_input("최대 이평선", value=60, min_value=10)
    
    run_btn = st.button("🚀 세력선 분석 시작", type="primary")

# -----------------------------------------------------------------------------
# 3. 분석 로직 (버튼 클릭 시 실행)
# -----------------------------------------------------------------------------
if run_btn:
    with st.spinner(f"'{stock_code}'의 과거 데이터를 샅샅이 뒤지는 중입니다..."):
        
        # (1) 데이터 수집
        try:
            df = fdr.DataReader(stock_code, start_date, end_date)
        except Exception as e:
            st.error(f"데이터를 가져오는데 실패했습니다: {e}")
            df = pd.DataFrame()

        if df.empty:
            st.error("해당 기간의 데이터가 없습니다. 날짜나 종목코드를 확인해주세요.")
        else:
            # (2) 백테스팅: 모든 이평선 계산 및 점수 매기기
            scores = {} # {이평선일수: 지지성공횟수}
            
            # 진행률 표시바
            progress_bar = st.progress(0)
            total_steps = max_ma - min_ma + 1
            step_count = 0

            for ma in range(min_ma, max_ma + 1):
                col_name = f'MA_{ma}'
                # 이평선 계산
                df[col_name] = df['Close'].rolling(window=ma).mean()
                
                # 지지력 테스트 (매우 정교한 로직)
                # 조건: 저가(Low)가 이평선을 살짝 건드리고(-2% ~ +1%), 종가(Close)는 이평선 위에 안착했는가?
                support_count = 0
                
                for idx, row in df.iterrows():
                    if pd.isna(row[col_name]): continue
                    
                    ma_val = row[col_name]
                    low_val = row['Low']
                    close_val = row['Close']
                    
                    # 지지 판단 범위 (이평선 기준 -2% ~ +1% 사이까지 내려왔다가)
                    lower_bound = ma_val * 0.98
                    upper_bound = ma_val * 1.01
                    
                    if lower_bound <= low_val <= upper_bound:
                        # 종가는 이평선보다 높거나 같게 마감 (지지에 성공)
                        if close_val >= ma_val:
                            support_count += 1
                
                scores[ma] = support_count
                
                # 진행률 업데이트
                step_count += 1
                progress_bar.progress(step_count / total_steps)

            # (3) 결과 도출: 1등 이평선 찾기
            sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
            best_ma = sorted_scores[0][0]     # 1등 이평선 (예: 13일)
            best_count = sorted_scores[0][1]  # 지지 횟수

            # -------------------------------------------------------------------------
            # 4. 결과 화면 출력
            # -------------------------------------------------------------------------
            st.success("분석 완료!")
            
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.markdown(f"""
                <div class='highlight'>
                    <h3>🏆 발견된 세력선</h3>
                    <h1 style='color: #ff4b4b; margin:0;'>{best_ma}일선</h1>
                    <p>이 기간 동안 총 <b>{best_count}번</b>의 완벽한 지지를 보여주었습니다.</p>
                    <p>세력들이 20일선 대신 <b>{best_ma}일선</b>을 보고 운전했을 가능성이 높습니다.</p>
                </div>
                """, unsafe_allow_html=True)
                
                st.write("#### 📊 이평선 순위 (Top 5)")
                rank_df = pd.DataFrame(sorted_scores, columns=['이평선(일)', '지지 성공 횟수']).head(5)
                st.dataframe(rank_df, hide_index=True)

            with col2:
                # 차트 그리기
                st.subheader(f"📈 {stock_code} 주가와 {best_ma}일선 흐름")
                
                fig = go.Figure()

                # 캔들 차트
                fig.add_trace(go.Candlestick(x=df.index,
                                open=df['Open'], high=df['High'],
                                low=df['Low'], close=df['Close'],
                                name='주가',
                                increasing_line_color='red', decreasing_line_color='blue')) # 한국식 컬러

                # 베스트 이평선
                fig.add_trace(go.Scatter(x=df.index, y=df[f'MA_{best_ma}'], 
                                        line=dict(color='black', width=2), 
                                        name=f'세력선 ({best_ma}일)'))

                fig.update_layout(height=500, xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)
                
            st.info(f"💡 팁: 차트의 특정 부분을 드래그하면 확대해서 '{best_ma}일선'을 타고 가는지 자세히 볼 수 있습니다.")

