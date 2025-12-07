import streamlit as st
import google.generativeai as genai
import re

st.set_page_config(page_title="연구 설계 및 AI 진단", page_icon="🧠", layout="wide")

# 1. 인증 설정 (Secrets 우선)
api_key = None
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    with st.sidebar:
        api_key = st.text_input("Google API Key", type="password")

if api_key:
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
    except:
        pass

# 2. AI 분석 함수 (복구됨!)
def analyze_ahp_logic(goal, parent, children):
    if not children:
        return {"grade": "정보없음", "summary": "하위 항목 없음", "suggestion": "추가 필요", "detail": "데이터 없음"}
    
    prompt = f"""
    [역할] AHP 구조 진단 전문가
    [대상] 목표: {goal} / 상위: {parent} / 하위: {children}
    [지침] 논리적 결함이 없다면 '양호'를 주고, 비판보다는 건설적인 제안을 하라.
    [출력 태그] [GRADE], [SUMMARY], [SUGGESTION], [DETAIL]
    """
    try:
        response = model.generate_content(prompt)
        text = response.text
        def extract(tag, t):
            match = re.search(fr"\[{tag}\](.*?)(?=\[|$)", t, re.DOTALL)
            return match.group(1).strip() if match else "내용 없음"
        return {
            "grade": extract("GRADE", text), "summary": extract("SUMMARY", text),
            "suggestion": extract("SUGGESTION", text), "detail": extract("DETAIL", text)
        }
    except Exception as e:
        return {"grade": "에러", "detail": str(e)}

# 3. UI 렌더링 함수
def render_result_ui(title, data):
    grade = data.get('grade', '정보없음')
    color = "green" if "양호" in grade else ("red" if "위험" in grade else "orange")
    icon = "✅" if "양호" in grade else ("🚨" if "위험" in grade else "⚠️")
    
    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        c1.markdown(f"#### {icon} {title}")
        c2.markdown(f"**등급: :{color}[{grade}]**")
        st.divider()
        st.markdown(f"**📋 요약:** {data.get('summary', '')}")
        st.info(f"💡 **제안:** {data.get('suggestion', '')}")
        with st.expander("🔍 상세 분석 보기"):
            st.write(data.get('detail', ''))

# 4. 메인 로직
if 'main_count' not in st.session_state: st.session_state.main_count = 1 
if 'sub_counts' not in st.session_state: st.session_state.sub_counts = {}

st.title("1️⃣ 연구 설계 및 AI 진단")
st.info("AI와 함께 구조를 잡고, [설문 생성] 버튼을 눌러 2번 페이지로 넘기세요.")

goal = st.text_input("🎯 최종 목표", placeholder="예: 차세대 전투기 도입")

if goal:
    st.subheader("1. 기준 설정")
    main_criteria = []
    for i in range(st.session_state.main_count):
        val = st.text_input(f"기준 {i+1}", key=f"main_{i}")
        if val: main_criteria.append(val)
    if st.button("➕ 기준 추가"):
        st.session_state.main_count += 1
        st.rerun()

    structure_data = {}
    if main_criteria:
        st.divider()
        st.subheader("2. 세부 항목 구성")
        for criterion in main_criteria:
            with st.expander(f"📂 '{criterion}' 하위 요소", expanded=True):
                if criterion not in st.session_state.sub_counts: st.session_state.sub_counts[criterion] = 1
                sub_items = []
                for j in range(st.session_state.sub_counts[criterion]):
                    s_val = st.text_input(f"ㄴ {criterion}-{j+1}", key=f"sub_{criterion}_{j}")
                    if s_val: sub_items.append(s_val)
                if st.button("➕ 추가", key=f"btn_{criterion}"):
                    st.session_state.sub_counts[criterion] += 1
                    st.rerun()
                structure_data[criterion] = sub_items

        # [AI 진단 버튼]
        st.divider()
        if st.button("🚀 AI 진단 시작", type="primary"):
            with st.spinner("AI가 분석 중..."):
                res = analyze_ahp_logic(goal, goal, main_criteria)
                render_result_ui(f"1차 기준: {goal}", res)
                for p, c in structure_data.items():
                    res = analyze_ahp_logic(goal, p, c)
                    render_result_ui(f"세부항목: {p}", res)

        # [설문 데이터 전송 버튼]
        st.divider()
        st.subheader("3. 다음 단계로 이동")
        if st.button("📢 이 구조로 설문 만들러 가기 (Click)", type="secondary"):
            # 데이터 패키징하여 세션에 저장
            st.session_state['passed_structure'] = {
                "goal": goal,
                "criteria": main_criteria,
                "sub_criteria": structure_data
            }
            st.success("✅ 구조가 저장되었습니다! 왼쪽 메뉴의 [2_설문_진행]을 클릭하세요.")
