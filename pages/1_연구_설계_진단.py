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
# 3. AI 분석 함수 (정밀도 & 간결성 최적화)
# --------------------------------------------------------------------------
def analyze_ahp_logic(goal, parent, children):
    if not children:
        return {"grade": "정보없음", "summary": "하위 항목 없음", "suggestion": "", "example": "", "detail": ""}
    
    if not API_KEYS:
        return {"grade": "키 없음", "summary": "API 키가 없습니다.", "suggestion": "", "example": "", "detail": ""}
    
    # [상황 인식] 1차 기준 vs 2차 세부항목
    is_main_criteria = (goal == parent)
    
    if is_main_criteria:
        # 1차 기준일 때: 넓게 보라고 지시
        focus_instruction = """
        - 현재 '1차 평가 기준'을 심사 중임.
        - 목표 달성을 위한 핵심 성공 요인(CSF)들이 빠짐없이(MECE) 구성되었는지 확인할 것.
        - 예: 점심 선정 -> 맛, 가격, 거리 (적절) / 맛, 매운맛, 짠맛 (부적절 - 맛에 편중됨)
        """
    else:
        # 2차 세부항목일 때: 깊게 보라고 지시 (딴소리 금지)
        focus_instruction = f"""
        - 현재 상위 기준 '{parent}'의 '하위 세부 지표'만 심사 중임.
        - **[중요] 절대 다른 상위 기준(예: 가격 분석 중인데 맛, 거리 언급 금지)을 제안하지 말 것.**
        - 오직 '{parent}'를 더 구체적으로 쪼갠 항목인지만 판단할 것.
        - 예: 가격 -> 1인당 비용, 할인율 (O) / 가격 -> 맛, 영양 (X - 이건 가격이 아님)
        """

    # 모델 리스트
    models = [
        'gemini-2.5-flash-lite', 'gemini-2.0-flash-lite', 
        'gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-2.0-pro-exp-02-05'
    ]
    
    # [프롬프트] 간결하고 명확하게 수정
    prompt = f"""
    [역할] 논리적 사고와 구조화를 돕는 연구 멘토
    [분석 대상]
    - 최종 목표: {goal}
    - 현재 기준: {parent}
    - 하위 항목: {children}
    
    [지침]
    1. **{focus_instruction}**
    2. **예시 추천:** 구체적인 사물(예: 떡볶이, 김밥)이 아니라 **'평가 기준 명사'(예: 메뉴 다양성, 접근성)**를 추천할 것.
    3. **답변 스타일:** 서술형 문장을 피하고, 핵심만 **간결하게(Bullet points)** 요약할 것.
    
    [출력 포맷]
    [GRADE] 적합/보완필요/부적합
    [SUMMARY] (논리 구조에 대한 1줄 핵심 진단)
    [SUGGESTION] (가장 시급한 수정 사항 1줄)
    [EXAMPLE]
    - (추천 기준 명사 1)
    - (추천 기준 명사 2)
    - (추천 기준 명사 3)
    [DETAIL]
    1. MECE(중복/누락): (핵심 진단)
    2. 위계 적절성: (상/하위 관계 진단)
    3. 용어 명확성: (직관성 진단)
    """
    
    attempts = []
    for key in API_KEYS:
        for model in models:
            attempts.append((key, model))
    
    # 순차 실행 (Lite 우선)
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
                <div style="font-weight:bold; color:#555; margin-bottom:5px;">✨ AI 추천 항목 (기준)</div>
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
    st.caption(f"🔒 API 키 {len(API_KEYS)}개 연동됨 (정밀 분석 모드)")

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
