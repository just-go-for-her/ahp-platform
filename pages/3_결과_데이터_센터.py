import streamlit as st
import pandas as pd
import io
import os

st.set_page_config(page_title="결과 데이터 센터", page_icon="📊", layout="wide")

st.title("📊 설문 결과 데이터 센터")
st.markdown("프로젝트(최종 목표)별로 수집된 데이터를 확인하고 관리합니다.")

DATA_FOLDER = "survey_data"

# 1. 데이터 폴더 확인 및 파일 리스트업
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

files = [f for f in os.listdir(DATA_FOLDER) if f.endswith(".csv")]

if files:
    # 2. 프로젝트 선택 (Selectbox)
    selected_file = st.selectbox("📂 확인하려는 연구 프로젝트를 선택하세요:", files)
    
    if selected_file:
        file_path = os.path.join(DATA_FOLDER, selected_file)
        df = pd.read_csv(file_path)
        
        st.divider()
        st.subheader(f"📈 프로젝트: {selected_file.replace('.csv', '').replace('_', ' ')}")
        
        # 요약 정보
        c1, c2 = st.columns(2)
        c1.metric("총 응답자 수", f"{len(df)}명")
        c2.metric("최근 업데이트", df['Time'].iloc[-1])
        
        # 데이터 표시
        with st.expander("📋 원본 데이터 보기 (Click)", expanded=True):
            st.dataframe(df)
        
        # 엑셀 다운로드
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Raw_Data')
            
        st.download_button(
            label="📥 엑셀 파일로 다운로드",
            data=output.getvalue(),
            file_name=f"Result_{selected_file.replace('.csv', '.xlsx')}",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
        
        # 데이터 삭제 기능
        st.divider()
        if st.button("🗑️ 이 프로젝트 데이터 전체 삭제", type="secondary"):
            os.remove(file_path)
            st.rerun()

else:
    st.info("📭 현재 저장된 연구 데이터가 없습니다.")
    st.caption("설문이 진행되면 자동으로 프로젝트 폴더가 생성됩니다.")
