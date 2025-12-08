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
# 2. 인증 설정 (Secrets 우선 -> 사이드바 입력)
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
# 3. AI 분석 함수 (동적 페르소나 적용)
# --------------------------------------------------------------------------
def analyze_ahp_logic(goal, parent, children):
    if not children:
        return {"grade": "정보없음", "summary": "하위 항목 없음", "suggestion": "", "example": "", "detail": ""}
    
    if not API_KEYS:
        return {"grade": "키 없음", "summary": "API 키가 없습니다.", "suggestion": "", "example": "", "detail": ""}
    
    # [핵심] 목표에 따라 AI의 말투와 기준을 바꾸는 프롬프트
    prompt = f"""
    [분석 대상]
    - 최종 목표: {goal}
    - 현재 기준: {parent}
    - 하위 항목: {children}
    
    [지침: 페르소나 설정]
    1. 먼저 '{goal}'의 성격을 분석하라.
       - **전문적/학술적/비즈니스 주제**라면: '냉철한 전문 컨설턴트' 톤으로 분석하라. 전문 용어(MECE, 위계성 등)를 적절히 사용하고 엄격하게 평가하라.
       - **일상/취미/가벼운 주제**라면: '친절한 멘토' 톤으로 분석하라. 쉬운 용어를 사용하고 격려하는 어조로 평가하라.
    
    2. 공통 지침
       - 답변은 **한국어**로 간결하게 작성하라.
       - [EXAMPLE]은 설명 없이 **추천 항목 명사**만 3~4개 나열하라.
       - 불필요한 서론/결론을 빼고 핵심만 출력하라.
    
    [출력 포맷]
    [GRADE] 적합/보완필요/부적합 (중 택 1)
    [SUMMARY] (주제 성격에 맞는 톤으로 1문장 요약)
    [SUGGESTION] (가장 필요한 수정 사항 1문장)
    [EXAMPLE]
    - 항목1
    - 항목2
    - 항목3
    [DETAIL]
    1. 구성(MECE): (핵심 진단)
    2. 위계 적절성: (핵심 진단)
    3. 용어 명확성: (핵심 진단)
    """
    
    # [수정] 작성자님 리스트에 있는 모델 중 'Lite'와 'Flash' 위주로 구성
    # Lite가 가장 가벼워서 무료 티어 방어에 유리합니다.
    models = [
        'gemini-2.0-flash-lite',       # 1순위: 리스트에 있는 경량 모델
        'gemini-2.0-flash',            # 2순위: 표준 모델
        'gemini-2.5-flash'             # 3순위: 최신 모델
    ]
    
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
                return "-"

            return {
                "grade": extract("GRADE", text),
                "summary": extract("SUMMARY", text),
                "suggestion": extract("SUGGESTION", text),
                "example": extract("EXAMPLE", text),
                "detail": extract("DETAIL", text)
            }

        except Exception as e:
            # 에러 시 짧게 대기 후 재시도
            if any(err in str(e) for err in ["429", "Quota", "503"]):
                time.sleep(0.5)
                continue
            return {"grade": "에러", "detail": str(e), "summary": "오류 발생", "example": ""}

    return {"grade": "대기", "summary": "사용량 초과 (잠시 후 시도)", "detail": "모든 API 키가 바쁩니다.", "example": ""}

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
        
        # 요약 & 제안
        st.write(f"**📋 진단 요약:** {data.get('summary', '-')}")
        st.info(f"💡 **제안:** {data.get('suggestion', '-')}")
        
        # 모범 답안
        ex = data.get('example', '')
        if len(ex) > 2:
            st.markdown(f"""
            <div style="background:{bg}; padding:15px; border-radius:5px; border-left:4px solid {color}; margin-top:10px;">
                <div style="font-weight:bold; color:#555; margin-bottom:5px;">✨ AI 추천 항목</div>
                <div style="white-space: pre-line; color:#333;">{ex}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # 상세 분석
        with st.expander("🔍 상세 분석 보기"):
            st.write(data.get('detail', '-'))

# --------------------------------------------------------------------------
# 5. 메인 로직
# --------------------------------------------------------------------------
if 'main_count' not in st.session_state: st.session_state.main_count = 1 
if 'sub_counts' not in st.session_state: st.session_state.sub_counts = {}

st.title("1️⃣ 연구 설계 및 AI 진단")

if API_KEYS:
    st.caption(f"🔒 API 키 {len(API_KEYS)}개 연동됨")

goal = st.text_input("🎯 최종 목표", placeholder="예: 차세대 전투기 도입 (전문적) / 점심 메뉴 선정 (가벼움)")

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
                # 안전한 실행을 위한 진행바 및 딜레이
                total_steps = 1 + len(struct)
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # 1. 메인 분석
                status_text.text("🧠 목표 분석 중...")
                res = analyze_ahp_logic(goal, goal, main)
                render_result_ui(f"1차 기준: {goal}", res)
                
                # 강제 휴식 (2초)
                progress_bar.progress(1/total_steps)
                time.sleep(2)
                
                # 2. 세부 항목 분석
                current_step = 2
                for p, ch in struct.items():
                    status_text.text(f"🧠 '{p}' 분석 중...")
                    msg = "⚠️ 항목 과다" if len(ch) >= 8 else ""
                    res = analyze_ahp_logic(goal, p, ch)
                    render_result_ui(f"세부항목: {p}", res, msg)
                    
                    # 강제 휴식 (2초)
                    progress_bar.progress(current_step/total_steps)
                    time.sleep(2)
                    current_step += 1
                
                status_text.text("✅ 분석 완료!")
                progress_bar.progress(1.0)

        st.divider()
        if st.button("💾 구조 확정 및 설문 배포하러 가기"):
            st.session_state['passed_structure'] = {
                "goal": goal,
                "main_criteria": main,
                "sub_criteria": struct
            }
            st.success("✅ 구조가 저장되었습니다! [2_설문_진행] 메뉴로 이동하세요.")
