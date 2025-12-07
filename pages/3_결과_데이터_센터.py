import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="결과 데이터 센터", page_icon="📊", layout="wide")

st.title("📊 설문 결과 데이터 센터")
st.markdown("공유된 설문지를 통해 수집된 데이터를 실시간으로 확인하고 엑셀로 다운로드합니다.")

DATA_FILE = "ahp_survey_results.csv"

# 1. 데이터 현황 확인
if os.path.exists(DATA_FILE):
    df = pd.read_csv(DATA_FILE)
    st.metric("총 응답 수", f"{len(df)}명")
    
    st.subheader("📋 수집된 데이터 미리보기")
    st.dataframe(df)
    
    # 2. 엑셀 변환 및 다운로드
    st.subheader("📥 데이터 다운로드")
    
    # CSV를 엑셀로 변환
    import io
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Raw_Data')
        # 필요하다면 여기에 통계 시트 추가 가능
    
    st.download_button(
        label="엑셀 파일(XLSX)로 다운로드",
        data=output.getvalue(),
        file_name="AHP_Final_Result.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )

else:
    st.info("📭 아직 수집된 설문 데이터가 없습니다.")
    st.caption("2번 메뉴에서 설문 링크를 만들어 공유해보세요!")
