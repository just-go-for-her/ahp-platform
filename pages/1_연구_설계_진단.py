import streamlit as st
import google.generativeai as genai
import re
import time

# --------------------------------------------------------------------------
# 1. 페이지 설정
# --------------------------------------------------------------------------
st.set_page_config(page_title="연구 설계 및 진단", page_icon="🧠", layout="wide")

# --------------------------------------------------------------------------
# 2. 인증 설정
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
    except:
        pass

# --------------------------------------------------------------------------
# 3. AI 분석 함수 (프롬프트 대폭 개선)
# --------------------------------------------------------------------------
def analyze_ahp_logic(goal, parent, children):
    if not children:
        return {
            "grade": "정보없음", "summary": "하위 항목 없음", 
            "suggestion": "항목 추가 필요", "example": "추천 없음", "detail": "데이터 없음"
        }
    
    # [핵심] AI에게 "개념적으로 정리해서" 답하라고 지시하는 프롬프트
    prompt = f"""
    [역할] AHP 연구 방법론 전문가
    [분석 대상] 
    - 최종 목표: {goal} 
    - 현재 상위 항목: {parent} 
    - 현재 하위 항목들: {children}
    
    [지침]
    아래 태그에 맞춰 분석 결과를 출력하라. 괄호나 특수문자 장식은 최소화하라.

    [GRADE]
    (양호 / 주의 / 위험) 중 하나만 선택

    [SUMMARY]
    전체적인 구조의 상태를 2문장 이내로 핵심만 요약

    [SUGGESTION]
    연구자가 즉시 적용할 수 있는 가장 중요한 수정 제안 1가지

    [EXAMPLE]
    (현재 계층에 가장 적합한 모범 항목을 3~5개만 선정하고, 괄호 안에 선정 이유를 짧게 적어라)
    - 항목명 (이유)
    - 항목명 (이유)

    [DETAIL]
    (다음 3가지 소주제로 나누어 분석하라. 각 소주제는 줄바꿈으로 구분하라)
    1. MECE(중복/누락) 진단: ...
    2. 계층 위계 적절성: ...
    3. 용어의 명확성: ...
    """
    
    # 모델 리스트 (이어달리기)
    models_to_try = [
        'gemini-2.5-flash',
        'gemini-2.0-flash',
        'gemini-2.0-flash-lite'
    ]
    
    last_error = ""

    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            text = response.text
            
            # 파싱 로직
            def extract(tag, t):
                pattern = fr"\[\s*{tag}\s*\](.*?)(?=\[\s*[A-Z]+\s*\]|$)"
                match = re.search(pattern, t, re.DOTALL | re.IGNORECASE)
                if match:
                    content = match.group(1).strip()
                    content = re.sub(r"^[\s\[\*\:\-]]+|[\s\]\*\:\-]+$", "", content).strip()
                    return content
                return "내용 없음"

            data = {
                "grade": extract("GRADE", text),
                "summary": extract("SUMMARY", text),
                "suggestion": extract("SUGGESTION", text),
                "example": extract("EXAMPLE", text),
                "detail": extract("DETAIL", text)
            }
            
            if data["grade"] == "내용 없음": 
                data["grade"] = "주의"
                data["detail"] = text
            
            return data

        except Exception as e:
            error_msg = str(e)
            last_error = error_msg
            if "429" in error_msg or "Quota" in error_msg or "503" in error_msg:
                time.sleep(1)
                continue
            else:
                return {"grade": "에러", "detail": f"시스템 오류: {error_msg}"}

    return {
        "grade": "⏳ 대기",
        "summary": "AI 사용량 초과",
        "suggestion": "잠시 후 다시 시도해주세요.",
        "example": "",
        "detail": f"Last Error: {last_error}"
    }

# --------------------------------------------------------------------------
# 4. UI 렌더링 함수 (깔끔한 디자인 적용)
# --------------------------------------------------------------------------
def render_result_ui(title, data, count_msg=""):
    grade = data.get('grade', '정보없음')
    grade_clean = grade.replace("[", "").replace("]", "").strip()
    
    # 색상 테마 설정
    if "위험" in grade_clean or "에러" in grade_clean: 
        icon, color = "🚨", "red"
        bg_color = "#fff5f5"
        alert_func = st.error
    elif "주의" in grade_clean: 
        icon, color = "⚠️", "orange"
        bg_color = "#fffcf5"
        alert_func = st.warning
    elif "양호" in grade_clean: 
        icon, color = "✅", "green"
        bg_color = "#f0fff4"
        alert_func = st.success
    else: 
        icon, color = "⏳", "blue"
        bg_color = "#e7f5ff"
        alert_func = st.info

    # 카드 UI 시작
    with st.container(border=True):
        # 1. 헤더
        c1, c2 = st.columns([0.75, 0.25])
        with c1:
            st.markdown(f"#### {icon} {title}")
            if count_msg: st.caption(f":red[{count_msg}]")
        with c2:
            st.markdown(f"<div style='text-align:right; color:{color}; font-weight:bold; font-size:1.1em; padding-top:10px;'>{grade_clean}</div>", unsafe_allow_html=True)
        
        st.divider()
        
        # 2. 진단 요약
        st.markdown("**📋 진단 요약**")
        st.write(data.get('summary', '-'))
        
        # 3. AI 제안 (강조 박스)
        st.markdown("**💡 AI의 핵심 제안**")
        alert_func(data.get('suggestion', '-'))
        
        # 4. 모범 답안 (카드 스타일)
        example_text = data.get('example', '')
        if len(example_text) > 5 and "없음" not in example_text:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(f"""
            <div style="background-color: #f8f9fa; border-left: 4px solid {color}; padding: 15px; border-radius: 4px;">
                <div style="font-weight:bold; color: #555; margin-bottom: 8px;">✨ AI 추천 모범 답안 (Best Practice)</div>
                <div style="font-size: 0.95em; line-height: 1.6; color: #333; white-space: pre-line;">
                    {example_text}
                </div>
            </div>
            """, unsafe_allow_html=True)

        # 5. 상세 분석 (구조화된 텍스트)
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("🔍 상세 분석 결과 보기 (MECE / 위계 / 용어)"):
            detail_text = data.get('detail', '')
            # 소주제별로 볼드체 처리 등 마크다운 강화 가능
            st.markdown(detail_text)

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
        if st.button("🚀 AI 진단 시작", type="primary"):
            with st.spinner("🧠 AI 전문가 군단이 구조를 정밀 분석 중입니다..."):
                res = analyze_ahp_logic(goal, goal, main_criteria)
                render_result_ui(f"1차 기준: {goal}", res)
                
                time.sleep(1) 
                
                for p, c in structure_data.items():
                    msg = ""
                    if len(c) >= 8: msg = f"⚠️ 항목 과다 (7개 이하 권장)"
                    res = analyze_ahp_logic(goal, p, c)
                    render_result_ui(f"세부항목: {p}", res, msg)
                    time.sleep(1)

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
