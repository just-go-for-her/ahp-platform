import streamlit as st
import google.generativeai as genai
import re

# --------------------------------------------------------------------------
# 1. 페이지 설정
# --------------------------------------------------------------------------
st.set_page_config(page_title="AHP 논리 정밀 진단기", page_icon="⚖️", layout="wide")

# --------------------------------------------------------------------------
# 2. 인증 설정 (Secrets 우선)
# --------------------------------------------------------------------------
api_key = None
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    with st.sidebar:
        st.header("🔐 인증 설정")
        api_key = st.text_input("Google API Key", type="password")

if api_key:
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
    except Exception as e:
        st.error(f"키 설정 오류: {e}")
        st.stop()
else:
    st.warning("⚠️ API 키가 필요합니다. (Streamlit Secrets 또는 사이드바 입력)")
    st.stop()

# --------------------------------------------------------------------------
# 3. AI 분석 함수 (프롬프트 튜닝: 절제된 추천 및 유연한 평가)
# --------------------------------------------------------------------------
def analyze_ahp_logic(goal, parent, children):
    if not children:
        return {
            "grade": "정보없음", "summary": "하위 항목 없음", 
            "suggestion": "항목 추가 필요", "example": "추천 없음", "detail": "데이터 없음"
        }
    
    # [핵심] 과도한 비판 금지 & 추천 예시는 간결하게 제한
    prompt = f"""
    [역할] AHP 구조 진단 컨설턴트 (친절하고 건설적인 태도)
    [대상] 목표: {goal} / 현재 상위항목: {parent} / 현재 하위항목들: {children}
    
    [지침]
    1. **평가 태도:** 너무 비판적으로 보지 마라. 논리적으로 큰 결함이 없다면 '양호' 등급을 부여하라.
    2. **[EXAMPLE] 작성 규칙 (매우 중요):**
       - **절대 설명이나 수식어를 붙이지 마라.** (예: '비용 효율성' O, '경제성을 고려한 비용 효율성' X)
       - 하위의 하위 항목(Depth 3)까지 나열하지 마라. **현재 계층의 바로 아래 단계만** 적어라.
       - 개수는 **핵심적인 3개~5개**로 딱 잘라라.
       - 예시:
         - 항목 A
         - 항목 B
         - 항목 C
    3. **상세 분석:** 구체적인 이유나 추가적인 세부 제안은 모두 [DETAIL] 섹션에 적어라.
    
    [필수 출력 태그]
    [GRADE] (양호/주의/위험)
    [SUMMARY] (3줄 이내 요약)
    [SUGGESTION] (1줄 제안)
    [EXAMPLE] (3~5개의 깔끔한 명사형 키워드 리스트)
    [DETAIL] (상세 분석 및 추가 설명)
    """
    
    try:
        response = model.generate_content(prompt)
        text = response.text
        
        # 정규표현식 파싱
        def extract_content(tag, text):
            pattern = fr"\[{tag}\](.*?)(?=\[|$)"
            match = re.search(pattern, text, re.DOTALL)
            return match.group(1).strip() if match else "내용 없음"

        data = {
            "grade": extract_content("GRADE", text),
            "summary": extract_content("SUMMARY", text),
            "suggestion": extract_content("SUGGESTION", text),
            "example": extract_content("EXAMPLE", text),
            "detail": extract_content("DETAIL", text)
        }
        
        # 파싱 실패 시 기본값 처리
        if data["grade"] == "내용 없음":
            data["grade"] = "주의"
            data["detail"] = text 

        return data

    except Exception as e:
        return {"grade": "에러", "summary": "오류", "suggestion": "", "example": "", "detail": str(e)}

# --------------------------------------------------------------------------
# 4. UI 렌더링
# --------------------------------------------------------------------------
def render_result_ui(title, data, count_msg=""):
    grade = data['grade']
    
    # 등급별 색상
    if "위험" in grade:
        icon, color, bg = "🚨", "red", "#fee"
    elif "주의" in grade:
        icon, color, bg = "⚠️", "orange", "#fffae5"
    elif "양호" in grade:
        icon, color, bg = "✅", "green", "#eff"
    else:
        icon, color, bg = "❓", "gray", "#eee"

    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        with c1: st.markdown(f"#### {icon} {title}")
        with c2: st.markdown(f"**등급: :{color}[{grade}]**")
        
        if count_msg: st.caption(f":red[{count_msg}]")
        st.divider()
        
        st.markdown("**📋 핵심 요약**")
        st.markdown(data['summary'])
        
        # 제안
        if "양호" in grade:
            st.success(f"💡 **제안:** {data['suggestion']}")
        elif "위험" in grade:
            st.error(f"💡 **제안:** {data['suggestion']}")
        else:
            st.warning(f"💡 **제안:** {data['suggestion']}")
        
        # 추천 예시 (내용이 있을 때만 표시)
        if len(data['example']) > 2 and "없음" not in data['example']:
            st.markdown(f"""
            <div style="background-color: {bg}; padding: 15px; border-radius: 10px; margin: 10px 0; border: 1px solid {color};">
                <strong style="color: {color};">✨ AI 추천 모범 답안</strong>
                <div style="margin-top: 5px; font-size: 0.95em; white-space: pre-line; line-height: 1.6;">
                    {data['example']}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with st.expander("🔍 상세 분석 사유 보기"):
            st.write(data['detail'])

# --------------------------------------------------------------------------
# 5. 메인 로직
# --------------------------------------------------------------------------
if 'main_count' not in st.session_state: st.session_state.main_count = 1 
if 'sub_counts' not in st.session_state: st.session_state.sub_counts = {}

with st.sidebar:
    st.info("💡 **리포트 구조**\n1. 요약 (3줄)\n2. 제안 (1줄)\n3. **추천 (핵심 3~5개)**\n4. 상세")

st.title("⚖️ AHP 논리 진단 리포트 (Pro)")
st.caption("AI가 오류를 진단하고, **핵심적인 모범 항목**을 추천합니다.")
st.divider()

col_goal, _ = st.columns([2, 1])
with col_goal:
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

        st.divider()
        if st.button("🚀 AI 진단 및 추천 받기", type="primary", use_container_width=True):
            with st.spinner("AI가 분석 리포트를 작성 중입니다..."):
                res_main = analyze_ahp_logic(goal, goal, main_criteria)
                render_result_ui(f"1차 기준: {goal}", res_main)
                for p, c in structure_data.items():
                    msg = ""
                    if len(c) >= 8: msg = f"⚠️ 항목 {len(c)}개 (7±2 초과)"
                    elif len(c) == 1: msg = "⚠️ 항목 1개 (비교 불가)"
                    res = analyze_ahp_logic(goal, p, c)
                    render_result_ui(f"세부항목: {p}", res, msg)

# ... (기존 AI 진단 로직 끝부분) ...

st.divider()
st.subheader("5. 설문지 배포 (Survey Generation)")

# 데이터 패키징 (목표 + 1차 기준 + 2차 기준)
survey_package = {
    "goal": goal,
    "criteria": main_criteria,
    "sub_criteria": structure_data
}

# 설문 생성 버튼
if st.button("📢 이 구조로 설문지 생성 및 링크 만들기", type="primary"):
    # 1. 데이터를 세션에 저장 (Page 2로 넘기기 위해)
    st.session_state['survey_design'] = survey_package
    
    st.success("설문 구조가 확정되었습니다! 왼쪽 메뉴의 [2_설문_진행] 페이지로 이동하세요.")
    st.balloons()
