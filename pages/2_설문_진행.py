import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
import streamlit.components.v1 as components
import requests  # [추가] 구글 시트 전송을 위한 라이브러리

# ==============================================================================
# [설정] 페이지 기본 설정
# ==============================================================================
st.set_page_config(page_title="설문 진행", page_icon="📝", layout="wide")

# [추가] 구글 시트 전송 함수
def send_to_google_cloud(user_key, respondent, raw_data):
    """
    구글 Apps Script 웹 앱으로 데이터를 전송하여 시트에 기록합니다.
    """
    # 사용자가 생성한 구글 Apps Script URL을 여기에 입력하세요.
    WEBAPP_URL = "https://script.google.com/macros/s/AKfycbxw_fT-O6gXHpK_08gKygB_HjwtdUnjYml-2DqnxqN0Ek9NsHCbuaDPnQ5Diz31qmjpdg/exec" 
    
    payload = {
        "user_key": user_key,
        "respondent": respondent,
        "raw_data": raw_data
    }
    try:
        # 타임아웃을 설정하여 구글 서버 응답이 늦어져도 사용자 화면이 멈추지 않게 함
        requests.post(WEBAPP_URL, json=payload, timeout=5)
    except:
        pass # 전송 실패 시에도 기존 로컬 저장 로직은 계속 실행됨

# 데이터 저장 폴더 설정
DATA_FOLDER = "survey_data"
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

# 세션 상태 초기화
if 'passed_structure' not in st.session_state:
    st.warning("⚠️ [1_연구_설계_진단] 페이지에서 구조를 먼저 확정해주세요.")
    st.stop()

# 설계 데이터 불러오기
config = st.session_state['passed_structure']
goal = config['goal']
main_criteria = config['main_criteria']
sub_criteria = config['sub_criteria']

# ==============================================================================
# [UI] 상단 안내 및 사용자 정보 입력
# ==============================================================================
st.title("📝 AHP 설문 참여")
st.info(f"🎯 **설문 목표:** {goal}")

with st.sidebar:
    st.header("👤 참여자 정보")
    user_key = st.text_input("프로젝트 비밀번호", placeholder="설계 시 설정한 비번", type="password")
    user_name = st.text_input("성함/닉네임", placeholder="결과 확인용")
    project_name = st.text_input("프로젝트명", value="My_AHP_Project")

if not user_key or not user_name:
    st.warning("👈 왼쪽 사이드바에서 비밀번호와 성함을 입력해주세요.")
    st.stop()

# ==============================================================================
# [로직] 쌍대비교 항목 생성
# ==============================================================================
def make_pairs(items):
    pairs = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            pairs.append((items[i], items[j]))
    return pairs

all_sections = []
# 1. 대항목 비교 세션
all_sections.append({
    "title": "📂 1. 평가 기준 중요도 비교",
    "pairs": make_pairs(main_criteria)
})

# 2. 소항목 비교 세션들
for main_item in main_criteria:
    if main_item in sub_criteria and len(sub_criteria[main_item]) > 1:
        all_sections.append({
            "title": f"📂 2. [{main_item}] 세부 항목 평가",
            "pairs": make_pairs(sub_criteria[main_item])
        })

# ==============================================================================
# [UI] 설문 본문 (쌍대비교)
# ==============================================================================
st.write("---")
st.markdown("#### 💡 설문 방법")
st.caption("더 중요하다고 생각하는 항목 쪽으로 슬라이더를 옮겨주세요. 중앙(1)은 두 항목이 대등함을 의미합니다.")

survey_results = {}

for section in all_sections:
    with st.expander(section['title'], expanded=True):
        for left, right in section['pairs']:
            pair_label = f"[{section['title']}] {left} vs {right}"
            
            col1, col2, col3 = st.columns([2, 5, 2])
            with col1:
                st.write(f"**{left}**")
            with col2:
                # -8 ~ 8 슬라이더 (실제 내부값은 1~9 비율로 변환됨)
                val = st.slider(
                    f"선택: {left} vs {right}",
                    min_value=-8, max_value=8, value=0, step=1,
                    key=pair_label,
                    label_visibility="collapsed"
                )
            with col3:
                st.write(f"<div style='text-align:right;'><b>{right}</b></div>", unsafe_allow_html=True)
            
            # AHP 1~9 척도 변환 로직
            if val < 0: # 왼쪽이 중요
                final_val = float(abs(val) + 1)
            elif val > 0: # 오른쪽이 중요
                final_val = 1.0 / float(val + 1)
            else: # 동일
                final_val = 1.0
                
            survey_results[pair_label] = f"{final_val:.2f}"
    st.write("")

# ==============================================================================
# [제출] 데이터 저장 (로컬 CSV + 구글 시트)
# ==============================================================================
st.write("---")
if st.button("🚀 설문 제출", type="primary"):
    # 1. 로컬 CSV 저장 로직 (기존 유지)
    file_name = f"{user_key}_{project_name}.csv"
    file_path = os.path.join(DATA_FOLDER, file_name)
    
    raw_json = json.dumps(survey_results, ensure_ascii=False)
    new_data = pd.DataFrame({
        "Time": [datetime.now().strftime('%Y-%m-%d %H:%M')],
        "Respondent": [user_name],
        "Raw_Data": [raw_json]
    })
    
    if os.path.exists(file_path):
        existing_df = pd.read_csv(file_path)
        updated_df = pd.concat([existing_df, new_data], ignore_index=True)
        updated_df.to_csv(file_path, index=False, encoding='utf-8-sig')
    else:
        new_data.to_csv(file_path, index=False, encoding='utf-8-sig')
    
    # 2. 구글 시트 이중 백업 전송 (추가됨)
    send_to_google_cloud(user_key, user_name, raw_json)
    
    st.balloons()
    st.success(f"✅ 설문이 성공적으로 제출되었습니다! (응답자: {user_name}님)")
    st.info("이제 '결과 데이터 센터' 메뉴에서 분석 결과를 확인하실 수 있습니다.")
    
    # 데이터 확인용 (개발 시)
    # st.json(survey_results)

# ==============================================================================
# [UI] 하단 여백
# ==============================================================================
st.write("\n\n")
st.divider()
st.caption("AHP Analysis System v2.5 | 구글 클라우드 백업 활성화됨")
