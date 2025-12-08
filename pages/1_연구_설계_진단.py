import streamlit as st
import google.generativeai as genai
import re
import time
import random

# --------------------------------------------------------------------------
# 1. 페이지 설정
# --------------------------------------------------------------------------
st.set_page_config(page_title="AHP 연구 설계 진단", page_icon="⚖️", layout="wide")

# --------------------------------------------------------------------------
# 2. 인증 설정 (Secrets 우선 -> 사이드바 입력)
# --------------------------------------------------------------------------
API_KEYS = []

if "gemini_keys" in st.secrets:
    API_KEYS = st.secrets["gemini_keys"]
elif "GOOGLE_API_KEY" in st.secrets:
    API_KEYS = [st.secrets["GOOGLE_API_KEY"]]

if not API_KEYS:
    with st.sidebar:
        st.header("🔑 API Key 입력")
        user_input = st.text_area("API Key 목록 (한 줄에 하나씩)", type="password", height=100)
        if user_input:
            API_KEYS = [k.strip() for k in user_input.replace(',', '\n').split('\n') if k.strip()]

# --------------------------------------------------------------------------
# 3. AI 분석 함수 (한국형 전문가 보고서 스타일)
# --------------------------------------------------------------------------
def analyze_ahp_logic(goal, parent, children):
    if not children:
        return {
            "grade": "N/A", "summary": "하위 평가 요소 미정의", 
            "suggestion": "평가 목적에 부합하는 하위 요소를 구성하십시오.", "example": "", "detail": ""
        }
    
    if not API_KEYS:
        return {
            "grade": "인증실패", "summary": "API 키가 확인되지 않습니다.",
            "suggestion": "설정에서 API 키를 입력하십시오.", "example": "", "detail": ""
        }
    
    # [상황 인식] 1차 기준 vs 2차 세부항목
    is_main_criteria = (goal == parent)
    
    if is_main_criteria:
        context_guide = """
        - 현재 분석 대상: 최상위 목표 달성을 위한 '핵심 성공 요인(CSF)' 또는 '1차 평가 기준'.
        - 진단 초점: 전략적 중요도와 평가 영역의 포괄성(Comprehensiveness).
        """
    else:
        context_guide = f"""
        - 현재 분석 대상: 상위 기준 '{parent}'를 측정하기 위한 '세부 측정 지표'.
        - 진단 초점: 상위 기준과의 논리적 연계성(Alignment) 및 측정 가능성.
        """

    # [핵심] 한국어 전문가 프롬프트
    prompt = f"""
    [역할] AHP 연구 방법론 전문 컨설턴트
    [분석 대상] 
    - 목표: {goal}
    - 상위 기준: {parent}
    - 하위 항목: {children}
    
    [지침]
    1. **언어:** 반드시 **한국어(Korean)**로 작성하라.
    2. **톤앤매너:** 객관적이고 냉철한 '분석 보고서' 스타일 (예: ~함, ~가 식별됨).
    3. **핵심 위주:** 장황한 설명 대신, 문제의 **'원인'과 '개선 방향'**을 명사형으로 간결하게 제시하라.
    
    {context_guide}
    
    [출력 포맷]
    [GRADE] 적합/보완필요/부적합 (중 택 1)
    [SUMMARY] (구조적 정합성에 대한 1줄 요약)
    [SUGGESTION] (최적화를 위한 전략적 제언 1문장)
    [EXAMPLE]
    - 표준 지표 1 (선정 근거)
    - 표준 지표 2 (선정 근거)
    [DETAIL]
    1. 구성의 완결성(MECE): (중복/누락 여부 핵심 진단)
    2. 위계의 적합성: (항목 레벨 및 분류 적절성 진단)
    3. 개념의 명확성: (용어의 조작적 정의 및 직관성 진단)
    """
    
    # 키 & 모델 로테이션
    models = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-2.0-flash-lite']
    attempts = []
    for key in API_KEYS:
        for model in models:
            attempts.append((key, model))
    random.shuffle(attempts)

    for i, (key, model_name) in enumerate(attempts):
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            text = response.text
            
            # 파싱 로직
            def extract(tag, t):
                match = re.search(fr"\[\s*{tag}\s*\](.*?)(?=\[\s*[A-Z]+\s*\]|$)", t, re.DOTALL | re.IGNORECASE)
                if match:
                    return re.sub(r"^[\s\[\*\:\-]]+|[\s\]\*\:\-]+$", "", match.group(1).strip()).strip()
                return "-"

            return {
                "grade": extract("GRADE", text),
                "summary": extract("SUMMARY", text),
                "suggestion": extract("SUGGESTION", text),
                "example": extract("EXAMPLE", text),
                "detail": extract("DETAIL", text)
            }

        except Exception as e:
            if any(err in str(e) for err in ["429", "Quota", "503"]):
                time.sleep(0.3)
                continue
            return {"grade": "Error", "detail": f"System Error: {str(e)}", "summary": "Analysis Failed", "example": ""}

    return {"grade": "대기", "summary": "API Quota Exceeded", "detail": "Please try again later.", "example": ""}

# --------------------------------------------------------------------------
# 4. UI 렌더링 함수 (전문가 보고서 디자인)
# --------------------------------------------------------------------------
def render_result_ui(title, data, count_msg=""):
    grade = data.get('grade', '-').replace("[", "").replace("]", "").strip()
    
    # 등급 매핑
    if "적합" in grade or "Optimal" in grade: 
        icon, color, bg = "✅", "green", "#f0fff4"
        display_grade = "적합 (Optimal)"
    elif "보완" in grade or "Improvement" in grade: 
        icon, color, bg = "⚠️", "orange", "#fffcf5"
        display_grade = "보완 필요 (Needs Improvement)"
    elif "부적합" in grade or "Critical" in grade: 
        icon, color, bg = "🚨", "red", "#fff5f5"
        display_grade = "부적합 (Critical Issue)"
    else: 
        icon, color, bg = "❓", "gray", "#f8f9fa"
        display_grade = "분석 불가"

    with st.container(border=True):
        # 헤더
        c1, c2 = st.columns([0.7, 0.3])
        c1.markdown(f"#### {icon} {title}")
        c2.markdown(f"<div style='color:{color}; font-weight:bold; text-align:right; font-family:sans-serif;'>{display_grade}</div>", unsafe_allow_html=True)
        
        if count_msg: st.caption(f":red[{count_msg}]")
        st.divider()
        
        # 1. 진단 요약
        st.markdown(f"**📊 구조적 정합성 진단 요약**")
        st.write(data.get('summary', '-'))
        
        # 2. 전략적 제언
        st.info(f"💡 **전문가의 전략적 제언:** {data.get('suggestion', '-')}")
        
        # 3. 표준 지표 제언
        ex = data.get('example', '')
        if len(ex) > 2:
            st.markdown(f"""
            <div style="background:{bg}; padding:15px; border-radius:4px; border-left:4px solid {color}; margin-top:10px;">
                <div style="font-weight:bold; color:#444; margin-bottom:5px; font-size:0.9em;">🧬 표준화된 평가 지표 제언 (Standard Criteria)</div>
                <div style="white-space: pre-line; color:#333; font-size:0.95em;">{ex}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # 4. 상세 분석 (핵심 관점 3가지)
        with st.expander("🔍 상세 진단 결과 (MECE / 위계 / 정의)"):
            st.markdown(data.get('detail', '-'))

# --------------------------------------------------------------------------
# 5. 메인 로직
# --------------------------------------------------------------------------
if 'main_count' not in st.session_state: st.session_state.main_count = 1 
if 'sub_counts' not in st.session_state: st.session_state.sub_counts = {}

st.title("⚖️ 연구 설계 및 구조 진단")

if API_KEYS:
    st.caption(f"🔒 **Secure Analysis Mode:** {len(API_KEYS)} API Keys Active")

goal = st.text_input("🎯 Decision Goal (최종 의사결정 목표)", placeholder="예: 차세대 주력 전차(MBT) 기종 선정")

if goal:
    st.subheader("1. 1차 평가 기준 설정 (Main Criteria)")
    main = []
    for i in range(st.session_state.main_count):
        val = st.text_input(f"Criterion {i+1}", key=f"main_{i}")
        if val: main.append(val)
    if st.button("➕ 기준 추가"): 
        st.session_state.main_count += 1
        st.rerun()

    struct = {}
    if main:
        st.divider()
        st.subheader("2. 세부 측정 지표 구성 (Sub-criteria)")
        for c in main:
            with st.expander(f"📂 '{c}' 세부 지표 설정", expanded=True):
                if c not in st.session_state.sub_counts: st.session_state.sub_counts[c]=1
                subs = []
                for j in range(st.session_state.sub_counts[c]):
                    v = st.text_input(f"ㄴ Sub-factor {j+1}", key=f"sub_{c}_{j}")
                    if v: subs.append(v)
                if st.button("➕ 지표 추가", key=f"btn_{c}"):
                    st.session_state.sub_counts[c]+=1
                    st.rerun()
                struct[c] = subs

        st.divider()
        if st.button("🚀 구조 정합성 진단 실행", type="primary"):
            if not API_KEYS:
                st.error("API 키가 없습니다.")
            else:
                with st.spinner("🔄 전문 컨설팅 알고리즘이 분석 중입니다..."):
                    # 1. 메인 분석
                    res = analyze_ahp_logic(goal, goal, main)
                    render_result_ui(f"Level 1: {goal}", res)
                    
                    # 2. 세부 항목 분석
                    for p, ch in struct.items():
                        msg = "⚠️ 지표 과다 (인지 부하 위험)" if len(ch) >= 8 else ""
                        res = analyze_ahp_logic(goal, p, ch)
                        render_result_ui(f"Level 2: {p}", res, msg)

        st.divider()
        if st.button("💾 연구 모형 확정 및 설문 생성"):
            st.session_state['passed_structure'] = {
                "goal": goal,
                "main_criteria": main,
                "sub_criteria": struct
            }
            st.success("✅ 연구 모형이 확정되었습니다. [2_설문_진행] 메뉴로 이동하십시오.")
