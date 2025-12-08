import streamlit as st
import google.generativeai as genai
import re
import time
import random

# --------------------------------------------------------------------------
# 1. 페이지 설정
# --------------------------------------------------------------------------
st.set_page_config(page_title="연구 설계 및 진단", page_icon="🧠", layout="wide")

# ==========================================================================
# [보안 설정] Secrets에서 API 키 리스트 가져오기
# ==========================================================================
API_KEYS = []

if "gemini_keys" in st.secrets:
    API_KEYS = st.secrets["gemini_keys"]
elif "GOOGLE_API_KEY" in st.secrets:
    API_KEYS = [st.secrets["GOOGLE_API_KEY"]]

if not API_KEYS:
    st.error("🚨 설정된 API 키가 없습니다! Streamlit Secrets에 'gemini_keys'를 설정해주세요.")
    st.stop()

# --------------------------------------------------------------------------
# 2. 스마트 AI 호출 함수 (키 로테이션)
# --------------------------------------------------------------------------
def call_ai_with_rotation(prompt):
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
            return response.text
        except Exception as e:
            error_msg = str(e)
            if any(err in error_msg for err in ["429", "Quota", "503", "403"]):
                time.sleep(0.2)
                continue
            else:
                return f"[ERROR] {error_msg}"
    return None

# --------------------------------------------------------------------------
# 3. 분석 로직
# --------------------------------------------------------------------------
def analyze_ahp_logic(goal, parent, children):
    if not children:
        return {"grade": "정보없음", "summary": "내용 없음", "suggestion": "항목 추가 필요", "example": "", "detail": ""}
    
    prompt = f"""
    [역할] AHP 연구 설계 멘토 (학부생 및 실무자 눈높이)
    [분석 대상] 목표: {goal} / 상위: {parent} / 하위: {children}
    
    [지침]
    1. 논리적 오류(MECE)는 지적하되, 지나치게 복잡하거나 학술적인 항목 추가는 지양하라.
    2. 항목 수는 그룹당 3~5개 이내가 적당하다고 조언하라.
    3. [EXAMPLE]에는 현실적으로 다룰 수 있는 핵심 항목 3~4개를 추천하라. (단어만 나열)
    4. 출력 시 불필요한 기호(괄호 등)를 쓰지 말고 내용만 명확히 적어라.
    
    [필수 출력 태그]
    [GRADE] 양호/주의/위험
    [SUMMARY] 요약
    [SUGGESTION] 제안
    [EXAMPLE] 모범 답안
    [DETAIL] 상세 분석
    """
    
    result_text = call_ai_with_rotation(prompt)
    
    if result_text is None:
        return {"grade": "⏳ 대기", "summary": "API 키 한도 초과", "suggestion": "잠시 후 시도하세요.", "example": "", "detail": ""}
    
    if "[ERROR]" in result_text:
         return {"grade": "에러", "detail": result_text}

    def extract(tag, t):
        match = re.search(fr"\[\s*{tag}\s*\](.*?)(?=\[\s*[A-Z]+\s*\]|$)", t, re.DOTALL | re.IGNORECASE)
        if match:
            return re.sub(r"^[\s\[\*\:\-]]+|[\s\]\*\:\-]+$", "", match.group(1).strip()).strip()
        return "내용 없음"

    return {
        "grade": extract("GRADE", result_text),
        "summary": extract("SUMMARY", result_text),
        "suggestion": extract("SUGGESTION", result_text),
        "example": extract("EXAMPLE", result_text),
        "detail": extract("DETAIL", result_text)
    }

# --------------------------------------------------------------------------
# 4. UI 렌더링 함수
# --------------------------------------------------------------------------
def render_result_ui(title, data, count_msg=""):
    grade = data.get('grade', '').replace("[", "").replace("]", "").strip()
    if "양호" in grade: icon, color, bg = "✅", "green", "#f0fff4"
    elif "주의" in grade: icon, color, bg = "⚠️", "orange", "#fffcf5"
    elif "위험" in grade: icon, color, bg = "🚨", "red", "#fff5f5"
    else: icon, color, bg = "❓", "gray", "#f8f9fa"

    with st.container(border=True):
        c1, c2 = st.columns([0.8, 0.2])
        c1.markdown(f"#### {icon} {title}")
        c2.markdown(f"<div style='color:{color}; font-weight:bold; text-align:right;'>{grade}</div>", unsafe_allow_html=True)
        if count_msg: st.caption(f":red[{count_msg}]")
        st.divider()
        st.markdown(f"**📋 요약:** {data.get('summary')}")
        st.info(f"💡 **제안:** {data.get('suggestion')}")
        
        ex = data.get('example', '')
        if len(ex) > 5:
            st.markdown(f"<div style='background:{bg}; padding:15px; border-left:4px solid {color}; margin:10px 0;'><b>✨ AI 모범 답안</b><br>{ex.replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)
        
        with st.expander("🔍 상세 분석"): st.write(data.get('detail'))

# --------------------------------------------------------------------------
# 5. 메인 로직
# --------------------------------------------------------------------------
if 'main_count' not in st.session_state: st.session_state.main_count = 1 
if 'sub_counts' not in st.session_state: st.session_state.sub_counts = {}

st.title("1️⃣ 연구 설계 및 AI 진단")

if API_KEYS:
    st.caption(f"🔒 **보안 모드:** {len(API_KEYS)}개의 API 키 로테이션 중")

goal = st.text_input("🎯 최종 목표", placeholder="예: 차세대 전투기 도입")

if goal:
    st.subheader("1. 기준 설정")
    main = []
    for i in range(st.session_state.main_count):
        val = st.text_input(f"기준 {i+1}", key=f"main_{i}")
        if val: main.append(val)
    if st.button("➕ 기준 추가"): 
        st.session_state.main_count += 1
        st.rerun()

    struct = {}
    if main:
        st.divider()
        st.subheader("2. 세부 항목")
        for c in main:
            with st.expander(f"📂 '{c}' 하위 요소", expanded=True):
                if c not in st.session_state.sub_counts: st.session_state.sub_counts[c]=1
                subs = []
                for j in range(st.session_state.sub_counts[c]):
                    v = st.text_input(f"ㄴ {c}-{j+1}", key=f"sub_{c}_{j}")
                    if v: subs.append(v)
                if st.button("➕ 추가", key=f"btn_{c}"):
                    st.session_state.sub_counts[c]+=1
                    st.rerun()
                struct[c] = subs

        st.divider()
        if st.button("🚀 AI 진단 시작", type="primary"):
            with st.spinner("🧠 분석 중..."):
                res = analyze_ahp_logic(goal, goal, main)
                render_result_ui(f"1차 기준: {goal}", res)
                
                for p, ch in struct.items():
                    msg = "⚠️ 항목 과다" if len(ch) >= 8 else ""
                    res = analyze_ahp_logic(goal, p, ch)
                    render_result_ui(f"세부항목: {p}", res, msg)

        # [여기가 핵심 수정 사항입니다!]
        st.divider()
        if st.button("💾 구조 확정 및 설문 배포하러 가기"):
            # 2번 페이지가 알아들을 수 있는 이름(main_criteria 등)으로 맞춰서 저장
            st.session_state['passed_structure'] = {
                "goal": goal,
                "main_criteria": main,    # 2번 페이지 호환용 이름
                "sub_criteria": struct    # 2번 페이지 호환용 이름
            }
            st.success("✅ 구조가 저장되었습니다! 왼쪽 메뉴의 [2_설문_진행]으로 이동하세요.")
