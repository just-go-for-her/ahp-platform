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
# 2. 인증 설정
# --------------------------------------------------------------------------
API_KEYS = []

if "gemini_keys" in st.secrets:
    API_KEYS = st.secrets["gemini_keys"]
elif "GOOGLE_API_KEY" in st.secrets:
    API_KEYS = [st.secrets["GOOGLE_API_KEY"]]

if not API_KEYS:
    with st.sidebar:
        st.header("🔑 API 키 입력")
        st.info("키가 3개라면 줄바꿈으로 구분해서 넣으세요.")
        user_input = st.text_area("API Key 목록", type="password", height=150)
        if user_input:
            API_KEYS = [k.strip() for k in user_input.replace(',', '\n').split('\n') if k.strip()]

# --------------------------------------------------------------------------
# 3. AI 분석 함수 (텍스트 청소 기능 강화)
# --------------------------------------------------------------------------
def analyze_ahp_logic(goal, parent, children):
    if not children:
        return {"grade": "정보없음", "summary": "하위 항목 없음", "suggestion": "", "example": "", "detail": ""}
    
    if not API_KEYS:
        return {"grade": "키 없음", "summary": "API 키가 없습니다.", "suggestion": "", "example": "", "detail": ""}
    
    is_main_criteria = (goal == parent)
    
    if is_main_criteria:
        scope_guide = "현재 '1차 평가 기준'을 심사 중입니다. 전체적인 균형을 보세요."
    else:
        scope_guide = f"현재 상위 기준 '{parent}'의 '하위 세부 항목'만 심사 중입니다."

    models = [
        'gemini-2.5-flash-lite', 'gemini-2.0-flash-lite', 
        'gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-2.0-pro-exp-02-05'
    ]
    
    # [프롬프트 수정] 특수문자 사용 금지 명령 추가
    prompt = f"""
    [역할] 상황에 맞춰 유연하게 사고하는 연구 멘토
    [분석 대상]
    - 최종 목표: {goal}
    - 현재 기준: {parent}
    - 하위 항목: {children}
    
    [지침 1: 평가 기준]
    - 일상 주제: 관대하게 평가 (상식적이면 '적합')
    - 전문 주제: 논리적으로 평가 (치명적 오류 없으면 '적합')
    - {scope_guide}

    [지침 2: 출력 스타일 (중요)]
    - **절대 굵은 글씨(**)나 특수기호를 사용하지 마라.** (깔끔한 텍스트만 출력)
    - 문장은 간결하게 끊어서 작성하라.
    
    [출력 포맷]
    [GRADE] 적합/보완필요/부적합
    [SUMMARY] (1줄 총평)
    [SUGGESTION] (1줄 제안)
    [EXAMPLE]
    - 항목1
    - 항목2
    - 항목3
    [DETAIL]
    1. 구성(MECE): (내용)
    2. 위계 적절성: (내용)
    3. 용어 명확성: (내용)
    """
    
    attempts = []
    for key in API_KEYS:
        for model in models:
            attempts.append((key, model))
    
    for i, (key, model_name) in enumerate(attempts):
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            text = response.text
            
            # [핵심] 텍스트 청소기 (Cleaner)
            def extract(tag, t):
                match = re.search(fr"\[{tag}\](.*?)(?=\[|$)", t, re.DOTALL | re.IGNORECASE)
                if match:
                    content = match.group(1).strip()
                    # 1. ** 기호 제거 (Bold Marker 삭제)
                    content = content.replace("**", "")
                    # 2. 앞뒤 불필요한 공백/기호 제거
                    return re.sub(r"^[\s\:\-]]+|[\s\]\:\-]+$", "", content).strip()
                return "-"

            return {
                "grade": extract("GRADE", text),
                "summary": extract("SUMMARY", text),
                "suggestion": extract("SUGGESTION", text),
                "example": extract("EXAMPLE", text),
                "detail": extract("DETAIL", text)
            }

        except Exception as e:
            time.sleep(0.2)
            continue

    return {"grade": "대기", "summary": "모든 API 사용량 초과", "detail": "잠시 후 다시 시도해주세요.", "example": ""}

# --------------------------------------------------------------------------
# 4. UI 렌더링 함수
# --------------------------------------------------------------------------
def render_result_ui(title, data, count_msg=""):
    grade = data.get('grade', '정보없음').replace("[", "").replace("]", "").strip()
    
    if "적합" in grade: icon, color, bg = "✅", "green", "#f0fff4"
    elif "보완" in grade: icon, color, bg = "⚠️", "orange", "#fffcf5"
    elif "부적합" in grade: icon, color, bg = "🚨", "red", "#fff5f5"
    else: icon, color, bg = "❓", "gray", "#f8f9fa"

    with st.container(border=True):
        c1, c2 = st.columns([0.8, 0.2])
        c1.markdown(f"#### {icon} {title}")
        c2.markdown(f"<div style='color:{color}; font-weight:bold; text-align:right;'>{grade}</div>", unsafe_allow_html=True)
        
        if count_msg: st.caption(f":red[{count_msg}]")
        st.divider()
        
        st.write(f"**📋 진단 요약:** {data.get('summary', '-')}")
        
        if "적합" in grade:
            st.success(f"💡 **제안:** {data.get('suggestion', '현재 구성이 아주 훌륭합니다!')}")
        else:
            st.info(f"💡 **제안:** {data.get('suggestion', '-')}")
        
        ex = data.get('example', '')
        if len(ex) > 2:
            st.markdown(f"""
            <div style="background:{bg}; padding:15px; border-radius:5px; border-left:4px solid {color}; margin-top:10px;">
                <div style="font-weight:bold; color:#555; margin-bottom:5px;">✨ AI 추천 항목</div>
                <div style="white-space: pre-line; color:#333;">{ex}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # 상세 분석 부분 깔끔하게 출력
        with st.expander("🔍 상세 분석 보기"):
            # 여기서 한번 더 ** 제거 (이중 안전장치)
            detail_text = data.get('detail', '-').replace("**", "")
            st.markdown(detail_text)

# --------------------------------------------------------------------------
# 5. 메인 로직
# --------------------------------------------------------------------------
if 'main_count' not in st.session_state: st.session_state.main_count = 1 
if 'sub_counts' not in st.session_state: st.session_state.sub_counts = {}

st.title("1️⃣ 연구 설계 및 AI 진단")

if API_KEYS:
    st.caption(f"🔒 API 키 {len(API_KEYS)}개 연동됨")

goal = st.text_input("🎯 최종 목표", placeholder="예: 차세대 전투기 도입 / 점심 메뉴 선정")

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
                total_steps = 1 + len(struct)
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # 1. 메인 분석
                status_text.text("🧠 목표 분석 중...")
                res = analyze_ahp_logic(goal, goal, main)
                render_result_ui(f"1차 기준: {goal}", res)
                
                progress_bar.progress(1/total_steps)
                time.sleep(2)
                
                # 2. 세부 항목 분석
                current_step = 2
                for p, ch in struct.items():
                    status_text.text(f"🧠 '{p}' 분석 중...")
                    msg = "⚠️ 항목 과다" if len(ch) >= 8 else ""
                    res = analyze_ahp_logic(goal, p, ch)
                    render_result_ui(f"세부항목: {p}", res, msg)
                    
                    progress_bar.progress(current_step/total_steps)
                    time.sleep(2)
                    current_step += 1
                
                status_text.success("✅ 분석 완료!")
                progress_bar.progress(1.0)

        st.divider()
        if st.button("💾 구조 확정 및 설문 배포하러 가기"):
            st.session_state['passed_structure'] = {
                "goal": goal,
                "main_criteria": main,
                "sub_criteria": struct
            }
            st.success("✅ 구조가 저장되었습니다! [2_설문_진행] 메뉴로 이동하세요.")
