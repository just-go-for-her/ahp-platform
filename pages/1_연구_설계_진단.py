import streamlit as st
import google.generativeai as genai
import re
import time
import random

# --------------------------------------------------------------------------
# 1. 페이지 설정
# --------------------------------------------------------------------------
st.set_page_config(page_title="연구 설계 및 진단", page_icon="🧠", layout="wide")

# --------------------------------------------------------------------------
# 2. 인증 설정 (하이브리드: Secrets 우선 -> 없으면 사이드바 입력)
# --------------------------------------------------------------------------
API_KEYS = []

if "gemini_keys" in st.secrets:
    API_KEYS = st.secrets["gemini_keys"]
elif "GOOGLE_API_KEY" in st.secrets:
    API_KEYS = [st.secrets["GOOGLE_API_KEY"]]

if not API_KEYS:
    with st.sidebar:
        st.header("🔑 API 키 입력")
        user_input = st.text_area("API Key 목록 (줄바꿈 구분)", type="password", height=100)
        if user_input:
            API_KEYS = [k.strip() for k in user_input.replace(',', '\n').split('\n') if k.strip()]

# --------------------------------------------------------------------------
# 3. AI 분석 함수 (핵심 위주로 짧게 출력하도록 프롬프트 수정)
# --------------------------------------------------------------------------
def analyze_ahp_logic(goal, parent, children):
    if not children:
        return {
            "grade": "정보없음", "summary": "하위 항목 없음", 
            "suggestion": "항목 추가 필요", "example": "", "detail": ""
        }
    
    if not API_KEYS:
        return {
            "grade": "키 없음", "summary": "API 키가 없습니다.",
            "suggestion": "API 키를 설정해주세요.", "example": "", "detail": ""
        }
    
    # [핵심] 프롬프트: "짧고 간결하게, 명사 위주로" 강력 지시
    prompt = f"""
    [역할] AHP 연구 설계 컨설턴트 (핵심만 직관적으로 전달)
    [분석 대상] 목표: {goal} / 상위: {parent} / 하위: {children}
    
    [지침]
    1. 모든 설명은 **간결하게(Concise)** 하라. 긴 문장은 금지한다.
    2. [EXAMPLE]은 설명 없이 **추천 항목의 명사만** 나열하라. (이유 적지 말 것)
    3. [DETAIL]은 '문제점'과 '이유'만 딱 짚어서 짧게 서술하라.
    
    [출력 포맷]
    [GRADE] 양호/주의/위험
    [SUMMARY] (상태를 1문장으로 요약)
    [SUGGESTION] (가장 시급한 수정 사항 1가지)
    [EXAMPLE]
    - 추천항목1
    - 추천항목2
    - 추천항목3
    [DETAIL]
    1. 중복/누락: (핵심만)
    2. 계층적절성: (핵심만)
    3. 용어명확성: (핵심만)
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
            
            def extract(tag, t):
                match = re.search(fr"\[\s*{tag}\s*\](.*?)(?=\[\s*[A-Z]+\s*\]|$)", t, re.DOTALL | re.IGNORECASE)
                if match:
                    return re.sub(r"^[\s\[\*\:\-]]+|[\s\]\*\:\-]+$", "", match.group(1).strip()).strip()
                return "내용 없음"

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
            return {"grade": "에러", "detail": str(e), "summary": "오류 발생", "example": ""}

    return {"grade": "대기", "summary": "사용량 초과", "detail": "잠시 후 시도하세요.", "example": ""}

# --------------------------------------------------------------------------
# 4. UI 렌더링 함수 (가독성 최적화)
# --------------------------------------------------------------------------
def render_result_ui(title, data, count_msg=""):
    grade = data.get('grade', '정보없음').replace("[", "").replace("]", "").strip()
    
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
        
        # 1. 요약 & 제안 (짧게)
        st.write(f"**📋 요약:** {data.get('summary', '-')}")
        st.info(f"💡 **제안:** {data.get('suggestion', '-')}")
        
        # 2. 모범 답안 (핵심 단어만 보여주기)
        ex = data.get('example', '')
        if len(ex) > 2:
            st.markdown(f"""
            <div style="background:{bg}; padding:15px; border-radius:5px; border-left:4px solid {color}; margin-top:10px;">
                <div style="font-weight:bold; color:#555; margin-bottom:5px;">✨ AI 추천 항목</div>
                <div style="white-space: pre-line; color:#333;">{ex}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # 3. 상세 분석 (핵심만)
        with st.expander("🔍 상세 분석 (핵심 체크)"):
            st.write(data.get('detail', '-'))

# --------------------------------------------------------------------------
# 5. 메인 로직
# --------------------------------------------------------------------------
if 'main_count' not in st.session_state: st.session_state.main_count = 1 
if 'sub_counts' not in st.session_state: st.session_state.sub_counts = {}

st.title("1️⃣ 연구 설계 및 AI 진단")

if API_KEYS:
    st.caption(f"🔒 API 키 {len(API_KEYS)}개 연동됨")

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
            if not API_KEYS:
                st.error("API 키가 없습니다!")
            else:
                with st.spinner("🧠 핵심만 빠르게 분석 중..."):
                    res = analyze_ahp_logic(goal, goal, main)
                    render_result_ui(f"1차 기준: {goal}", res)
                    
                    for p, ch in struct.items():
                        msg = "⚠️ 항목 과다" if len(ch) >= 8 else ""
                        res = analyze_ahp_logic(goal, p, ch)
                        render_result_ui(f"세부항목: {p}", res, msg)

        st.divider()
        if st.button("💾 구조 확정 및 설문 배포하러 가기"):
            st.session_state['passed_structure'] = {
                "goal": goal,
                "main_criteria": main,
                "sub_criteria": struct
            }
            st.success("✅ 구조가 저장되었습니다! [2_설문_진행] 메뉴로 이동하세요.")
