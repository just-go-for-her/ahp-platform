import streamlit as st
import google.generativeai as genai
import re
import json
import base64
import urllib.parse

st.set_page_config(page_title="연구 설계", page_icon="🧠", layout="wide")

# ... (인증 및 AI 설정 코드는 기존과 동일, 생략) ...
# (기존의 api_key 설정 부분과 analyze_ahp_logic 함수는 그대로 두세요)

# --- 메인 로직 ---
if 'main_count' not in st.session_state: st.session_state.main_count = 1 
if 'sub_counts' not in st.session_state: st.session_state.sub_counts = {}

st.title("1️⃣ 연구 설계 및 진단")

goal = st.text_input("🎯 최종 목표", placeholder="예: 차세대 전투기 도입")

if goal:
    st.subheader("1. 기준 설정")
    main_criteria = []
    for i in range(st.session_state.main_count):
        val = st.text_input(f"기준 {i+1}", key=f"main_{i}")
        if val: main_criteria.append(val)
    
    if st.button("➕ 기준 추가"):
        st.session_state.main_count += 1
        st.rerun()

    structure_data = {}
    
    if main_criteria:
        st.divider()
        st.subheader("2. 세부 항목 구성")
        for criterion in main_criteria:
            with st.expander(f"📂 '{criterion}' 하위 요소", expanded=True):
                if criterion not in st.session_state.sub_counts: st.session_state.sub_counts[criterion] = 1
                sub_items = []
                for j in range(st.session_state.sub_counts[criterion]):
                    s_val = st.text_input(f"ㄴ {criterion}-{j+1}", key=f"sub_{criterion}_{j}")
                    if s_val: sub_items.append(s_val)
                if st.button("➕ 추가", key=f"btn_{criterion}"):
                    st.session_state.sub_counts[criterion] += 1
                    st.rerun()
                structure_data[criterion] = sub_items
        
        # -------------------------------------------------------
        # [수정됨] 설문 생성 및 URL 암호화 로직
        # -------------------------------------------------------
        st.divider()
        st.subheader("3. 설문 배포")
        
        if st.button("📢 설문지 생성 및 공유 링크 만들기", type="primary"):
            # 1. 데이터 패키징
            survey_package = {
                "goal": goal,
                "criteria": main_criteria,
                # 하위 항목은 일단 제외하고 1차 기준만으로 설문 생성 (오류 최소화)
                "sub_criteria": structure_data 
            }
            
            # 2. 세션 저장 (내부 이동용)
            st.session_state['survey_design'] = survey_package
            
            # 3. URL 암호화 (한글 깨짐 방지 완벽 처리)
            json_str = json.dumps(survey_package, ensure_ascii=False) # 한글 보존
            bytes_data = json_str.encode("utf-8")
            b64_data = base64.b64encode(bytes_data).decode("utf-8")
            url_safe_data = urllib.parse.quote(b64_data)
            
            # 4. 링크 생성
            # 배포 전에는 로컬주소, 배포 후에는 streamlit.app 주소가 됨
            base_url = "https://ahp-platform.streamlit.app/설문_진행"
            final_url = f"{base_url}?data={url_safe_data}"
            
            st.success("✅ 설문지가 생성되었습니다!")
            
            st.markdown("👇 **아래 박스 오른쪽 위의 복사 아이콘(📄)을 누르세요!**")
            st.code(final_url, language="text")
            
            st.info("💡 팁: 이 URL을 복사해서 카카오톡이나 메일로 보내면 됩니다.")
