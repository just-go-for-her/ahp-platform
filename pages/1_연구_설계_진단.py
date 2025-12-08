import streamlit as st
import google.generativeai as genai
import re

# --------------------------------------------------------------------------
# 1. 페이지 설정
# --------------------------------------------------------------------------
st.set_page_config(page_title="연구 설계 및 진단", page_icon="🧠", layout="wide")

# --------------------------------------------------------------------------
# 2. 인증 설정 (Secrets 우선)
# --------------------------------------------------------------------------
api_key = None
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    with st.sidebar:
        api_key = st.text_input("Google API Key", type="password")

if api_key:
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
    except:
        pass

# --------------------------------------------------------------------------
# 3. AI 분석 함수 (429 에러 방지 기능 탑재)
# --------------------------------------------------------------------------
def analyze_ahp_logic(goal, parent, children):
    if not children:
        return {
            "grade": "정보없음", "summary": "하위 항목 없음", 
            "suggestion": "항목 추가 필요", "example": "추천 없음", "detail": "데이터 없음"
        }
    
    prompt = f"""
    [역할] AHP 구조 진단 컨설턴트
    [대상] 목표: {goal} / 상위항목: {parent} / 하위항목들: {children}
    
    [지침]
    1. 논리적(독립성, MECE)으로 문제가 없다면 '양호' 등급을 주어라.
    2. [EXAMPLE]에는 현재 계층에 적합한 **핵심 키워드 3~5개**를 명사형으로 나열하라. (설명 금지)
    
    [필수 출력 태그]
    [GRADE] (양호/주의/위험)
    [SUMMARY] (3줄 요약)
    [SUGGESTION] (1줄 제안)
    [EXAMPLE] (3~5개의 모범 항목 리스트)
    [DETAIL] (상세 분석)
    """
    
    try:
        # AI에게 요청
        response = model.generate_content(prompt)
        text = response.text
        
        # 정규표현식 파싱
        def extract(tag, t):
            match = re.search(fr"\[{tag}\](.*?)(?=\[|$)", t, re.DOTALL)
            return match.group(1).strip() if match else "내용 없음"

        data = {
            "grade": extract("GRADE", text),
            "summary": extract("SUMMARY", text),
            "suggestion": extract("SUGGESTION", text),
            "example": extract("EXAMPLE", text),
            "detail": extract("DETAIL", text)
        }
        
        # 파싱 실패 시 안전장치
        if data["grade"] == "내용 없음": 
            data["grade"] = "주의"
            data["detail"] = text
        return data

    except Exception as e:
        # [핵심] 사용량 초과(429) 에러가 발생했을 때 부드럽게 대처
        error_msg = str(e)
        if "429" in error_msg or "Quota" in error_msg:
            return {
                "grade": "⏳ 대기 필요",
                "summary": "AI 사용량이 일시적으로 많습니다.",
                "suggestion": "약 1분 뒤에 다시 버튼을 눌러주세요.",
                "example": "잠시 휴식",
                "detail": f"구글 AI 무료 버전의 분당 사용 한도에 도달했습니다.\n(잠시만 기다렸다가 시도하면 정상 작동합니다.)\n\nError: {error_msg}"
            }
        
        # 그 외 다른 에러
        return {
            "grade": "에러", 
            "summary": "오류 발생",
            "suggestion": "관리자 문의",
            "example": "없음",
            "detail": str(e)
        }

# --------------------------------------------------------------------------
# 4. UI 렌더링 함수
# --------------------------------------------------------------------------
def render_result_ui(title, data, count_msg=""):
    grade = data.get('grade', '정보없음')
    
    # 등급별 색상 설정
    if "위험" in grade or "에러" in grade: icon, color, bg = "🚨", "red", "#fee"
    elif "주의" in grade: icon, color, bg = "⚠️", "orange", "#fffae5"
    elif "양호" in grade: icon, color, bg = "✅", "green", "#eff"
    elif "대기" in grade: icon, color, bg = "⏳", "blue", "#e7f5ff"
    else: icon, color, bg = "❓", "gray", "#eee"

    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        c1.markdown(f"#### {icon} {title}")
        c2.markdown(f"**등급: :{color}[{grade}]**")
        
        if count_msg: st.caption(f":red[{count_msg}]")
        st.divider()
        st.markdown(f"**📋 요약:** {data.get('summary', '')}")
        
        # 제안 메시지
        if "양호" in grade: st.success(f"💡 **제안:** {data.get('suggestion', '')}")
        else: st.warning(f"💡 **제안:** {data.get('suggestion', '')}")
        
        # [✨ 추천 예시 박스]
        example_text = data.get('example', '')
        if len(example_text) > 2 and "없음" not in example_text:
            st.markdown(f"""
            <div style="background-color: {bg}; padding: 15px; border-radius: 10px; margin: 10px 0; border: 1px solid {color};">
                <strong style="color: {color};">✨ AI 추천 모범 답안</strong>
                <div style="margin-top: 5px; font-size: 0.95em; white-space: pre-line;">
                    {example_text}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
        with st.expander("🔍 상세 분석 보기"):
            st.write(data.get('detail', ''))

# --------------------------------------------------------------------------
# 5. 메인 로직
# --------------------------------------------------------------------------
if 'main_count' not in st.session_state: st.session_state.main_count = 1 
if 'sub_counts' not in st.session_state: st.session_state.sub_counts = {}

st.title("1️⃣ 연구 설계 및 AI 진단")

goal = st.text_input("🎯 최종 목표", placeholder="예: 차세대 전투기 도입")

if goal:
    st.subheader("1. 기준 설정 (1차)")
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
        st.subheader("2. 세부 항목 구성 (2차)")
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
        # [AI 진단 버튼]
        if st.button("🚀 AI 진단 시작", type="primary"):
            with st.spinner("AI가 분석 중..."):
                res = analyze_ahp_logic(goal, goal, main_criteria)
                render_result_ui(f"1차 기준: {goal}", res)
                for p, c in structure_data.items():
                    msg = ""
                    if len(c) >= 8: msg = f"⚠️ 항목 과다 (7개 이하 권장)"
                    res = analyze_ahp_logic(goal, p, c)
                    render_result_ui(f"세부항목: {p}", res, msg)

        # [데이터 전송 버튼] (번호 삭제됨)
        st.divider()
        st.markdown("### 📤 설문 생성 단계")
        st.caption("구조가 확정되었다면 아래 버튼을 눌러 설문 도구로 이동하세요.")
        
        if st.button("💾 구조 확정 및 설문 배포하러 가기"):
            st.session_state['passed_structure'] = {
                "goal": goal,
                "main_criteria": main_criteria,
                "sub_criteria": structure_data
            }
            st.success("✅ 구조가 저장되었습니다! 왼쪽 메뉴의 [2_설문_진행]으로 이동하세요.")
