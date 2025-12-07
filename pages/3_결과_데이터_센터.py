import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="결과 데이터 센터", page_icon="📊")

st.title("📊 결과 데이터 수집 및 변환")
st.markdown("설문 결과를 업로드하면, **AHP 분석 전용 Excel 파일**로 변환해 드립니다.")

st.divider()

# 1. 파일 업로드 (가정: 설문 툴에서 CSV가 나온다고 가정)
uploaded_file = st.file_uploader("설문 결과 파일 업로드 (CSV)", type=['csv'])

if uploaded_file is not None:
    try:
        # 데이터 읽기
        df = pd.read_csv(uploaded_file)
        
        st.subheader("1. 업로드된 원본 데이터 미리보기")
        st.dataframe(df.head())
        
        st.markdown("---")
        st.subheader("2. 연구용 데이터로 변환 중...")
        
        # [시나리오] 여기서는 단순 변환을 보여주지만, 
        # 실제로는 쌍대비교 값을 행렬로 바꾸거나, 
        # 기하평균을 미리 계산해주는 로직을 넣을 수 있습니다.
        
        # 예시: 엑셀 다운로드를 위한 변환
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # 시트 1: 원본 데이터
            df.to_excel(writer, index=False, sheet_name='Raw_Data')
            
            # 시트 2: 통계 요약 (예시)
            summary = df.describe()
            summary.to_excel(writer, sheet_name='Summary_Stats')
            
        processed_data = output.getvalue()

        st.success("변환이 완료되었습니다! 아래 버튼을 눌러 다운로드하세요.")
        
        # 다운로드 버튼
        st.download_button(
            label="📥 연구용 Excel 파일 다운로드",
            data=processed_data,
            file_name="AHP_Research_Data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    except Exception as e:
        st.error(f"파일 처리 중 오류가 발생했습니다: {e}")

else:
    st.info("👈 설문이 완료되면, 결과 파일(CSV)을 받아 이곳에 올려주세요.")
