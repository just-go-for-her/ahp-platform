import streamlit as st
import pandas as pd
import io
import os

st.set_page_config(page_title="결과 데이터 센터", page_icon="📊", layout="wide")

st.title("📊 결과 데이터 센터")
st.markdown("설문지에서 제출된 데이터가 이곳에 실시간으로 수집됩니다.")

DATA_FILE = "ahp_results.csv"

if os.path.exists(DATA_FILE):
    # 1. 데이터 읽기
    df = pd.read_csv(DATA_FILE)
    
    # 2. 요약 지표
    col1, col2 = st.columns(2)
    col1.metric("총 응답 수", f"{len(df)}건")
    col2.metric("최근 응답", df['Time'].iloc[-1] if not df.empty else "-")
    
    # 3. 데이터 미리보기
    st.subheader("📋 수집된 데이터 (미리보기)")
    st.dataframe(df)
    
    # 4. 엑셀 다운로드
    st.divider()
    st.subheader("📥 연구용 파일 다운로드")
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Survey_Data')
        
    st.download_button(
        label="엑셀 파일(.xlsx) 받기",
        data=output.getvalue(),
        file_name="AHP_Survey_Final.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )

    # (옵션) 데이터 초기화 버튼
    with st.expander("⚠️ 데이터 관리 (주의)"):
        if st.button("모든 데이터 삭제하기", type="primary"):
            os.remove(DATA_FILE)
            st.rerun()

else:
    st.info("📭 아직 수집된 데이터가 없습니다.")
    st.caption("2번 메뉴에서 설문을 진행하고 제출해보세요.")
