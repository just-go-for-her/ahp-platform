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
# 3. AI 분석 함수 (채점 기준 완화 및 현실화)
# --------------------------------------------------------------------------
def analyze_ahp_logic(goal, parent, children):
    if not children:
        return {"grade": "정보없음", "summary": "하위 항목 없음", "suggestion": "", "example": "", "detail": ""}
    
    if not API_KEYS:
        return {"grade": "키 없음", "summary": "API 키가 없습니다.", "suggestion": "", "example": "", "detail": ""}
    
    # [상황 인식] 1차 vs 2차
    is_main_criteria = (goal == parent)
    
    if is_main_criteria:
        scope_guide = "현재 '1차 평가 기준'을 심사 중입니다. 전체적인 균형을 보세요."
    else:
        scope_guide = f"현재 상위 기준 '{parent}'의 '하위 세부 항목'만 심사 중입니다. 딴소리(다른 상위 기준 언급) 하지 마세요."

    # 모델 리스트
    models = [
        'gemini-2.5-flash-lite', 'gemini-2.0-flash-lite', 
        'gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-2.0-pro-exp-02-05'
    ]
    
    # [핵심] 채점 기준(Grading Policy)을 명확히 지시
    prompt = f"""
    [역할] 상황에 맞춰 유연하게 사고하는 연구 멘토
    [분석 대상]
    - 최종 목표: {goal}
    - 현재 기준: {parent}
    - 하위 항목: {children}
    
    [지침 1: 주제 파악 및 태도]
    - '{goal}'이 일상적/가벼운 주제(예: 점심, 여행)라면?
      -> **관대하게 평가하라.** 엄격한 MECE 잣대 대신 '상식적인 수준'에서 통하면 '적합'을 주어라.
      -> 말투: 친절하고 격려하는 톤.
    - '{goal}'이 전문적/학술적 주제라면?
      -> **논리적으로 평가하되, 억지로 흠을 잡지 마라.** 핵심 요소가 갖춰졌다면 '적합'을 주어라.
      -> 말투: 객관적이고 명확한 톤.

    [지침 2: 평가 가이드라인]
    - {scope_guide}
    - **중요:** 하위 항목이 2개 이상이고, 상위 기준을 설명하기에 무리가 없다면 과감하게 **'적합'** 판정을 내려라.
    - 완벽하지 않더라도 치명적인 오류(완전히 엉뚱한 항목 등)가 없다면 '보완필요'를 남발하지 마라.
    - [EXAMPLE] 추천 시, 구체적 사물(예: 햄버거) 말고 **'평가 기준 명사'(예: 메뉴 다양성)**를 추천하라.
    
    [출력 포맷]
    [GRADE] 적합/보완필요/부적합
    [SUMMARY] (주제 성격에 맞는 1줄 총평)
    [SUGGESTION] (칭찬할 건 칭찬하고, 정말 필요한 경우만 수정 제안 1줄)
    [EXAMPLE]
    - (추천 기준 명사 1)
    - (추천 기준 명사 2)
    - (추천 기준 명사 3)
    [DETAIL]
    1. 구성(MECE): (핵심 진단)
    2. 위계 적절성: (핵심 진단)
    3. 용어 명확성: (핵심 진단)
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
        
        # 칭찬일 때와 지적일 때 아이콘/색상 구분
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
