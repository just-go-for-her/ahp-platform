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
# 2. 인증 설정 (다중 키 지원)
# --------------------------------------------------------------------------
API_KEYS = []

# 1. Secrets에서 리스트로 가져오기
if "gemini_keys" in st.secrets:
    API_KEYS = st.secrets["gemini_keys"]
elif "GOOGLE_API_KEY" in st.secrets:
    API_KEYS = [st.secrets["GOOGLE_API_KEY"]]

# 2. 없으면 사이드바에서 입력받기 (여러 개 입력 가능)
if not API_KEYS:
    with st.sidebar:
        st.header("🔑 API 키 입력")
        st.info("키가 3개라면 줄바꿈으로 구분해서 넣으세요.")
        user_input = st.text_area(
            "API Key 목록 (예: Key1 엔터 Key2 엔터 Key3)", 
            type="password", 
            height=150
        )
        if user_input:
            # 콤마나 줄바꿈으로 구분된 키를 리스트로 변환
            API_KEYS = [k.strip() for k in user_input.replace(',', '\n').split('\n') if k.strip()]

# --------------------------------------------------------------------------
# 3. AI 분석 함수 (총력전: 키 3개 x 모델 5개)
# --------------------------------------------------------------------------
def analyze_ahp_logic(goal, parent, children):
    if not children:
        return {"grade": "정보없음", "summary": "하위 항목 없음", "suggestion": "", "example": "", "detail": ""}
    
    if not API_KEYS:
        return {"grade": "키 없음", "summary": "API 키가 없습니다.", "suggestion": "", "example": "", "detail": ""}
    
    # [전략] 작성자님 리스트에 있는 텍스트 모델 5종 (순서 중요)
    # Lite 모델을 앞세워 속도와 쿼터를 챙기고, 뒤로 갈수록 고성능 모델 배치
    models = [
        'gemini-2.5-flash-lite',      # 1. 최신 경량 (빠름/무료 빵빵)
        'gemini-2.0-flash-lite',      # 2. 2.0 경량 (안정적)
        'gemini-2.5-flash',           # 3. 최신 표준 (메인)
        'gemini-2.0-flash',           # 4. 2.0 표준 (서브)
        'gemini-2.0-pro-exp-02-05'    # 5. 프로 (최후의 보루)
    ]
    
    # [프롬프트] 주제에 따른 페르소나 자동 전환
    prompt = f"""
    [분석 대상]
    - 최종 목표: {goal}
    - 현재 기준: {parent}
    - 하위 항목: {children}
    
    [지침: 페르소나 설정]
    1. '{goal}'의 성격을 파악하라.
       - **전문적/비즈니스/논문** 주제 -> '냉철한 컨설턴트' 톤 (전문 용어 사용, 엄격함)
       - **일상/취미/가벼운** 주제 -> '친절한 멘토' 톤 (쉬운 용어, 격려)
    
    2. 공통 지침
       - **한국어**로 작성하라.
       - [EXAMPLE]은 설명 없이 **추천 항목 명사**만 3~4개 나열하라.
       - [DETAIL]은 문제의 원인과 해결책을 짧고 명확하게 적어라.
    
    [출력 포맷]
    [GRADE] 적합/보완필요/부적합
    [SUMMARY] (주제 성격에 맞는 1문장 요약)
    [SUGGESTION] (핵심 제안 1문장)
    [EXAMPLE]
    - 항목1
    - 항목2
    - 항목3
    [DETAIL]
    1. 구성(MECE): (진단)
    2. 위계 적절성: (진단)
    3. 용어 명확성: (진단)
    """
    
    # [핵심] 조합 생성 (Key 3개 x Model 5개 = 15개 조합)
    attempts = []
    for key in API_KEYS:
        for model in models:
            attempts.append((key, model))
    
    # 순서는 섞지 않습니다. (Lite 모델부터 소모하는 게 이득이므로)
    
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
            # 429(한도초과) 등 에러 발생 시, 0.2초만 쉬고 바로 다음 키/모델로 넘어감
            # (총 15번의 기회가 있으므로 과감하게 넘겨도 됨)
            time.sleep(0.2)
            continue

    return {"grade": "대기", "summary": "모든 API 키/모델 사용량 초과", "detail": "잠시 휴식 후 다시 시도해주세요.", "example": ""}

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
# 5. 메인 로직 (속도 최적화: 대기 시간 단축)
# --------------------------------------------------------------------------
if 'main_count' not in st.session_state: st.session_state.main_count = 1 
if 'sub_counts' not in st.session_state: st.session_state.sub_counts = {}

st.title("1️⃣ 연구 설계 및 AI 진단")

if API_KEYS:
    # 사용자에게 든든함을 주는 메시지
    models_count = 5
    total_chances = len(API_KEYS) * models_count
    st.caption(f"🔒 **슈퍼 가동 모드:** API 키 {len(API_KEYS)}개 × 모델 {models_count}종 = **총 {total_chances}중 방어 시스템** 작동 중")

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
                total_steps = 1 + len(struct)
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # 1. 메인 분석
                status_text.text("🧠 목표 분석 중... (멀티 엔진 가동)")
                res = analyze_ahp_logic(goal, goal, main)
                render_result_ui(f"1차 기준: {goal}", res)
                
                # [속도 개선] 키가 3개나 있으므로 대기 시간을 2초로 줄입니다. (충분함)
                progress_bar.progress(1/total_steps)
                time.sleep(2)
                
                # 2. 세부 항목 분석
                current_step = 2
                for p, ch in struct.items():
                    status_text.text(f"🧠 '{p}' 분석 중...")
                    msg = "⚠️ 항목 과다" if len(ch) >= 8 else ""
                    res = analyze_ahp_logic(goal, p, ch)
                    render_result_ui(f"세부항목: {p}", res, msg)
                    
                    # 대기 시간 2초
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
