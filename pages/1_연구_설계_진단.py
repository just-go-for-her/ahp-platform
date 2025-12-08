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
        user_input = st.text_area("API Key 목록 (줄바꿈 구분)", type="password", height=150)
        if user_input:
            API_KEYS = [k.strip() for k in user_input.replace(',', '\n').split('\n') if k.strip()]

# --------------------------------------------------------------------------
# 3. AI 분석 함수 (생존 전략: 살아있는 모델 우선 사용)
# --------------------------------------------------------------------------
def analyze_ahp_logic(goal, parent, children):
    # 에러 기본값
    empty_res = {"grade": "오류", "summary": "분석 실패", "suggestion": "잠시 후 시도", "example": "", "detail": ""}

    if not children:
        return {**empty_res, "grade": "정보없음", "summary": "하위 항목 없음"}
    
    if not API_KEYS:
        return {**empty_res, "grade": "키 없음", "summary": "API 키 없음"}
    
    # [상황 인식]
    is_main = (goal == parent)
    scope_guide = "1차 평가 기준의 균형성(MECE)을 중심으로 진단." if is_main else f"상위 기준 '{parent}'의 하위 세부 항목 적절성만 진단(다른 기준 언급 금지)."

    # [핵심 전략] 
    # 1. 에러가 났던 '2.0-flash'는 맨 뒤로 뺍니다.
    # 2. 사용량이 0인 '2.5-flash-lite'를 1순위로 올립니다.
    models = [
        'gemini-2.5-flash-lite',                # 1순위: 가장 쌩쌩함 (강추)
        'gemini-2.0-flash-lite-preview-02-05', # 2순위: 그 다음으로 가벼움
        'gemini-2.5-flash',                     # 3순위: 성능 좋음
        'gemini-2.0-pro-exp-02-05',             # 4순위: 고성능
        'gemini-2.0-flash'                      # 5순위: (현재 한도 초과 의심됨 -> 맨 뒤로)
    ]
    
    prompt = f"""
    [분석 대상]
    - 목표: {goal}
    - 기준: {parent}
    - 하위: {children}
    
    [지침 1: 태도]
    - 주제가 전문적이면 '냉철한 컨설턴트', 일상적이면 '친절한 멘토' 톤.
    - {scope_guide}
    
    [지침 2: 형식]
    - **한국어** 작성.
    - **특수문자(**, *) 사용 금지.**
    - [EXAMPLE]은 설명 없이 **추천 항목 명사**만 나열.
    
    [출력 포맷]
    [GRADE] 적합/보완필요/부적합
    [SUMMARY] (1줄 요약)
    [SUGGESTION] (1줄 제안)
    [EXAMPLE]
    - 항목1
    - 항목2
    - 항목3
    [DETAIL]
    1. 구성: (내용)
    2. 위계: (내용)
    3. 용어: (내용)
    """
    
    attempts = []
    # (키 개수 x 모델 5개) 조합 생성
    for key in API_KEYS:
        for model in models:
            attempts.append((key, model))
    
    # [전략 수정] 랜덤 셔플을 뺍니다.
    # 이유: 지금은 '2.5-flash-lite'가 확실히 살아있으므로, 얘부터 무조건 먼저 시키는 게 유리합니다.
    # random.shuffle(attempts) 
    
    last_error = ""
    
    for i, (key, model_name) in enumerate(attempts):
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            text = response.text
            
            def extract(tag, t):
                match = re.search(fr"\[{tag}\](.*?)(?=\[|$)", t, re.DOTALL | re.IGNORECASE)
                if match:
                    c = match.group(1).strip()
                    c = c.replace("**", "").replace("*", "") # 별표 제거
                    return re.sub(r"^[\s\:\-]]+|[\s\]\:\-]+$", "", c).strip()
                return "-"

            # 성공하면 바로 리턴 (루프 종료)
            return {
                "grade": extract("GRADE", text),
                "summary": extract("SUMMARY", text),
                "suggestion": extract("SUGGESTION", text),
                "example": extract("EXAMPLE", text),
                "detail": extract("DETAIL", text)
            }

        except Exception as e:
            # 에러 발생 시 로그만 찍고, '즉시' 다음 모델로 넘어감 (Sleep 최소화)
            error_msg = str(e)
            last_error = error_msg
            
            # 429(한도초과)면 가차 없이 다음 타자 등판
            if "429" in error_msg or "Quota" in error_msg:
                # print(f"Pass: {model_name} (Quota Exceeded)") # 디버깅용
                continue 
            
            # 다른 에러면 잠깐 숨 고르고 이동
            time.sleep(0.5)
            continue

    return {**empty_res, "detail": f"모든 모델이 한도 초과입니다. 새 API 키가 필요합니다.\n(Last: {last_error})"}

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
            st.success(f"💡 **제안:** {data.get('suggestion', '현재 구성이 훌륭합니다.')}")
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
        
        with st.expander("🔍 상세 분석 보기"):
            st.write(data.get('detail', '-'))

# --------------------------------------------------------------------------
# 5. 메인 로직
# --------------------------------------------------------------------------
if 'main_count' not in st.session_state: st.session_state.main_count = 1 
if 'sub_counts' not in st.session_state: st.session_state.sub_counts = {}

st.title("1️⃣ 연구 설계 및 AI 진단")

if API_KEYS:
    st.caption(f"🔒 API 키 {len(API_KEYS)}개 연동됨 (생존 모델 우선 사용)")

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
                total_steps = 1 + len(struct)
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # 1. 메인 분석
                status_text.text("🧠 1차 기준 분석 중... (Lite 모델 가동)")
                res = analyze_ahp_logic(goal, goal, main)
                render_result_ui(f"1차 기준: {goal}", res)
                
                # 안전 대기 (Lite 모델은 분당 10-15회 가능하므로 5초면 충분)
                for i in range(5):
                    time.sleep(1)
                    progress_bar.progress((1/total_steps) * (i/5))
                
                # 2. 세부 항목 분석
                current_step = 2
                for p, ch in struct.items():
                    status_text.text(f"🧠 '{p}' 분석 중...")
                    msg = "⚠️ 항목 과다" if len(ch) >= 8 else ""
                    res = analyze_ahp_logic(goal, p, ch)
                    render_result_ui(f"세부항목: {p}", res, msg)
                    
                    # 안전 대기 5초
                    for i in range(5):
                        time.sleep(1)
                    
                    current_step += 1
                
                status_text.success("✅ 모든 분석이 완료되었습니다!")
                progress_bar.progress(1.0)

        st.divider()
        if st.button("💾 구조 확정 및 설문 배포하러 가기"):
            st.session_state['passed_structure'] = {
                "goal": goal,
                "main_criteria": main,
                "sub_criteria": struct
            }
            st.success("✅ 구조가 저장되었습니다! [2_설문_진행] 메뉴로 이동하세요.")
