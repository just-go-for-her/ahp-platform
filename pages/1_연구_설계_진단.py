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
        st.header("🔑 API Key Authorization")
        user_input = st.text_area("Enter API Keys (One per line)", type="password", height=100)
        if user_input:
            API_KEYS = [k.strip() for k in user_input.replace(',', '\n').split('\n') if k.strip()]

# --------------------------------------------------------------------------
# 3. AI 분석 함수 (전문가/경영가용 프롬프트 적용)
# --------------------------------------------------------------------------
def analyze_ahp_logic(goal, parent, children):
    # 하위 항목 부재 시 처리
    if not children:
        return {
            "grade": "N/A", "summary": "하위 평가 요소가 정의되지 않았습니다.", 
            "suggestion": "평가 목적에 부합하는 하위 요소를 구성하십시오.", "example": "", "detail": ""
        }
    
    if not API_KEYS:
        return {
            "grade": "Unauthorized", "summary": "API 인증 키가 확인되지 않습니다.",
            "suggestion": "시스템 관리자에게 문의하거나 키를 설정하십시오.", "example": "", "detail": ""
        }
    
    # [상황 인식 로직] 1차 기준 vs 2차 세부항목
    is_main_criteria = (goal == parent)
    
    if is_main_criteria:
        context_guide = """
        - 현재 분석 대상은 최상위 목표를 달성하기 위한 '핵심 성공 요인(CSF)' 또는 '1차 평가 기준'임.
        - 전략적 중요도와 평가의 포괄성(Comprehensiveness)을 중심으로 진단할 것.
        """
    else:
        context_guide = f"""
        - 현재 분석 대상은 상위 기준 '{parent}'를 측정하기 위한 '세부 측정 지표(Sub-criteria)'임.
        - 상위 기준과의 논리적 연계성(Alignment)과 측정 가능성(Measurability)을 중심으로 진단할 것.
        """

    # [핵심] 전문가용 프롬프트 (Professional Tone)
    prompt = f"""
    [Role] Senior Methodology Consultant (AHP & Decision Science Expert)
    [Target User] Professional Researchers, Business Executives, Policy Makers
    [Context]
    - Goal: {goal}
    - Parent Criteria: {parent}
    - Sub-criteria (To be analyzed): {children}
    
    [Instruction]
    {context_guide}
    Analyze the structural validity based on AHP principles. Use professional and academic terminology.
    
    [Output Guidelines]
    1. **Conciseness**: Be direct and analytical. Avoid conversational filler.
    2. **Terminology**: Use terms like 'MECE', 'Hierarchy', 'Operational Definition', 'Strategic Alignment'.
    3. **Recommendation**: Provide industry-standard criteria suitable for high-level decision making.
    
    [Required Output Format]
    [GRADE] Optimal / Needs Improvement / Critical Issue (Choose one)
    [SUMMARY] (Executive Summary of structural integrity, max 2 sentences)
    [SUGGESTION] (Key strategic recommendation for model optimization)
    [EXAMPLE]
    - Criteria 1 (Rationale)
    - Criteria 2 (Rationale)
    - Criteria 3 (Rationale)
    [DETAIL]
    1. MECE Analysis: (Check for Mutually Exclusive & Collectively Exhaustive)
    2. Hierarchical Consistency: (Check for level appropriateness)
    3. Terminological Precision: (Check for ambiguity)
    """
    
    # 키 & 모델 로테이션 (안정성 확보)
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

    return {"grade": "Pending", "summary": "API Quota Exceeded", "detail": "Please try again later.", "example": ""}

# --------------------------------------------------------------------------
# 4. UI 렌더링 함수 (비즈니스 리포트 스타일)
# --------------------------------------------------------------------------
def render_result_ui(title, data, count_msg=""):
    grade = data.get('grade', '-').replace("[", "").replace("]", "").strip()
    
    # 등급 매핑 (전문적인 용어로 변경)
    if "Optimal" in grade or "양호" in grade: 
        icon, color, bg = "✅", "green", "#f0fff4"
        korean_grade = "적합 (Optimal)"
    elif "Improvement" in grade or "주의" in grade: 
        icon, color, bg = "⚠️", "orange", "#fffcf5"
        korean_grade = "보완 필요 (Needs Improvement)"
    elif "Critical" in grade or "위험" in grade: 
        icon, color, bg = "🚨", "red", "#fff5f5"
        korean_grade = "부적합 (Critical Issue)"
    else: 
        icon, color, bg = "❓", "gray", "#f8f9fa"
        korean_grade = "분석 불가"

    with st.container(border=True):
        # 헤더 디자인
        c1, c2 = st.columns([0.7, 0.3])
        c1.markdown(f"#### {icon} {title}")
        c2.markdown(f"<div style='color:{color}; font-weight:bold; text-align:right; font-family:sans-serif;'>{korean_grade}</div>", unsafe_allow_html=True)
        
        if count_msg: st.caption(f":red[{count_msg}]")
        st.divider()
        
        # 1. Executive Summary
        st.markdown(f"**📊 Executive Summary**")
        st.write(data.get('summary', '-'))
        
        # 2. Strategic Recommendation
        st.info(f"💡 **Strategic Recommendation:** {data.get('suggestion', '-')}")
        
        # 3. Standard Criteria (모범 답안)
        ex = data.get('example', '')
        if len(ex) > 2:
            st.markdown(f"""
            <div style="background:{bg}; padding:15px; border-radius:4px; border-left:4px solid {color}; margin-top:10px;">
                <div style="font-weight:bold; color:#444; margin-bottom:5px; font-size:0.9em;">🧬 표준화된 평가 지표 제언 (Recommended Criteria)</div>
                <div style="white-space: pre-line; color:#333; font-size:0.95em;">{ex}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # 4. Detailed Audit (상세 분석)
        with st.expander("🔍 Structural Integrity Audit (구조적 정합성 상세 분석)"):
            st.markdown(data.get('detail', '-'))

# --------------------------------------------------------------------------
# 5. 메인 로직
# --------------------------------------------------------------------------
if 'main_count' not in st.session_state: st.session_state.main_count = 1 
if 'sub_counts' not in st.session_state: st.session_state.sub_counts = {}

st.title("⚖️ 연구 설계 및 구조 진단")

if API_KEYS:
    st.caption(f"🔒 **Secure Mode Active:** {len(API_KEYS)} API Keys Ready")

goal = st.text_input("🎯 Decision Goal (최종 의사결정 목표)", placeholder="예: 차세대 주력 전차(MBT) 기종 선정, 신사옥 입지 선정 전략")

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
        if st.button("🚀 구조 정합성 진단 실행 (Analyze Structure)", type="primary"):
            if not API_KEYS:
                st.error("API Key Missing.")
            else:
                with st.spinner("🔄 Performing Structural Integrity Analysis..."):
                    # 1. 메인 분석
                    res = analyze_ahp_logic(goal, goal, main)
                    render_result_ui(f"Level 1: {goal}", res)
                    
                    # 2. 세부 항목 분석
                    for p, ch in struct.items():
                        msg = "⚠️ 항목 과다 (Cognitive Overload Risk)" if len(ch) >= 8 else ""
                        res = analyze_ahp_logic(goal, p, ch)
                        render_result_ui(f"Level 2: {p}", res, msg)

        st.divider()
        if st.button("💾 연구 모형 확정 및 설문 생성 (Confirm & Deploy)"):
            st.session_state['passed_structure'] = {
                "goal": goal,
                "main_criteria": main,
                "sub_criteria": struct
            }
            st.success("✅ Model Confirmed. Proceed to [2_설문_진행].")
