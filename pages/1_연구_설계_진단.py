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
# 2. 인증 설정 (Secrets 사용 - 기존 방식 유지)
# --------------------------------------------------------------------------
API_KEYS = []

# secrets.toml에서 가져오기
if "gemini_keys" in st.secrets:
    API_KEYS = st.secrets["gemini_keys"]
elif "GOOGLE_API_KEY" in st.secrets:
    API_KEYS = [st.secrets["GOOGLE_API_KEY"]]

if not API_KEYS:
    st.error("🚨 Secrets에 API 키가 없습니다. 설정 후 다시 실행해주세요.")
    st.stop()

# --------------------------------------------------------------------------
# 3. AI 분석 함수 (핵심 수정: 오류 방지 및 상세분석 포맷 고정)
# --------------------------------------------------------------------------
def analyze_ahp_logic(goal, parent, children):
    # 하위 항목이 없으면 바로 리턴
    if not children:
        return {
            "grade": "정보없음", "summary": "하위 항목이 없습니다.", 
            "suggestion": "항목을 추가해주세요.", "example": "", "detail": ""
        }
    
    # [프롬프트] 상세 분석을 3가지 관점으로 명확히 요구
    prompt = f"""
    [역할] AHP 연구 설계 전문가
    [분석 대상] 목표: {goal} / 상위: {parent} / 하위: {children}
    
    [지침]
    1. 등급은 양호/주의/위험 중 하나만 선택하라.
    2. [DETAIL]에서는 반드시 아래 3가지 소제목으로 나누어 분석하라.
       - 1. MECE(중복/누락)
       - 2. 계층 위계 적절성
       - 3. 용어 명확성
    3. 괄호나 특수문자 장식을 최소화하라.
    
    [출력 포맷]
    [GRADE] 양호
    [SUMMARY] (핵심 요약 1~2문장)
    [SUGGESTION] (가장 중요한 제안 1가지)
    [EXAMPLE] (모범 항목 3~5개 나열)
    [DETAIL] (위 3가지 관점의 상세 분석)
    """
    
    # 모델 & 키 로테이션 로직 (기존 유지)
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
            
            # [핵심 수정] 파싱 로직 강화 (None 반환 방지)
            def extract(tag, t):
                match = re.search(fr"\[\s*{tag}\s*\](.*?)(?=\[\s*[A-Z]+\s*\]|$)", t, re.DOTALL | re.IGNORECASE)
                if match:
                    content = match.group(1).strip()
                    # 앞뒤 특수문자 제거
                    return re.sub(r"^[\s\[\*\:\-]]+|[\s\]\*\:\-]+$", "", content).strip()
                return "내용 없음" # None 대신 기본 문자열 반환

            return {
                "grade": extract("GRADE", text),
                "summary": extract("SUMMARY", text),
                "suggestion": extract("SUGGESTION", text),
                "example": extract("EXAMPLE", text),
                "detail": extract("DETAIL", text)
            }

        except Exception as e:
            # 429 등 일시적 에러는 넘어가고, 다음 키 시도
            if any(err in str(e) for err in ["429", "Quota", "503"]):
                time.sleep(0.5)
                continue
            return {"grade": "에러", "summary": "API 호출 오류", "suggestion": "잠시 후 다시 시도하세요.", "detail": str(e), "example": ""}

    return {
        "grade": "대기", "summary": "모든 API 키 한도 초과", 
        "suggestion": "잠시 후 다시 시도해주세요.", "detail": "사용량 초과", "example": ""
    }

# --------------------------------------------------------------------------
# 4. UI 렌더링 함수 (기존 디자인 유지 + 안전장치 추가)
# --------------------------------------------------------------------------
def render_result_ui(title, data, count_msg=""):
    # 데이터가 없거나 에러일 경우를 대비한 안전장치
    if not data: data = {}
    grade = data.get('grade', '정보없음').replace("[", "").replace("]", "").strip()
    
    # 색상 설정
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
        
        # 요약 & 제안
        st.markdown(f"**📋 진단 요약**")
        st.write(data.get('summary', '내용 없음'))
        
        st.markdown(f"**💡 AI의 핵심 제안**")
        if "양호" in grade: st.success(data.get('suggestion', '내용 없음'))
        else: st.warning(data.get('suggestion', '내용 없음'))
        
        # 모범 답안
        ex = data.get('example', '')
        if len(ex) > 5:
            st.markdown(f"<div style='background:{bg}; padding:15px; border-left:4px solid {color}; margin:10px 0;'><b>✨ AI 모범 답안</b><br>{ex.replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)
        
        # 상세 분석 (개념별 정리 확인)
        with st.expander("🔍 상세 분석 결과 보기 (MECE / 위계 / 용어)"):
            st.markdown(data.get('detail', '상세 내용 없음'))

# --------------------------------------------------------------------------
# 5. 메인 로직 (기존 플로우 유지)
# --------------------------------------------------------------------------
if 'main_count' not in st.session_state: st.session_state.main_count = 1 
if 'sub_counts' not in st.session_state: st.session_state.sub_counts = {}

st.title("1️⃣ 연구 설계 및 AI 진단")

# API 키 상태 표시 (보안 모드)
if API_KEYS:
    st.caption(f"🔒 보안 모드: {len(API_KEYS)}개의 키가 준비되었습니다.")

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
            with st.spinner("🧠 AI 전문가가 분석 중입니다..."):
                # 1. 1차 기준 분석
                res = analyze_ahp_logic(goal, goal, main)
                render_result_ui(f"1차 기준: {goal}", res)
                
                # 2. 세부 항목 분석
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
            st.success("✅ 구조가 저장되었습니다! 왼쪽 메뉴의 [2_설문_진행]으로 이동하세요.")
