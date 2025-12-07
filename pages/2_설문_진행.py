import streamlit as st
import streamlit.components.v1 as components
import json
import base64
import urllib.parse
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="AHP 설문 조사", page_icon="📝", layout="wide")

# --------------------------------------------------------------------------
# 1. 데이터 베이스 (임시: 실제 서비스에선 구글 시트 등을 연결해야 함)
# --------------------------------------------------------------------------
# 수집된 데이터를 저장할 파일명
DATA_FILE = "ahp_survey_results.csv"

def save_response(data):
    """응답 데이터를 로컬 CSV 파일에 저장하는 함수"""
    try:
        new_df = pd.DataFrame([data])
        try:
            old_df = pd.read_csv(DATA_FILE)
            final_df = pd.concat([old_df, new_df], ignore_index=True)
        except FileNotFoundError:
            final_df = new_df
        
        final_df.to_csv(DATA_FILE, index=False)
        return True
    except Exception as e:
        st.error(f"저장 중 오류 발생: {e}")
        return False

# --------------------------------------------------------------------------
# 2. URL 파라미터 처리 (URL -> 설문 구조 복원)
# --------------------------------------------------------------------------
# URL에서 데이터 가져오기 (쿼리 파라미터)
query_params = st.query_params
encoded_data = query_params.get("data", None)

survey_structure = None

# A. URL에 데이터가 있으면 (응답자 모드) -> 그걸 씀
if encoded_data:
    try:
        decoded_bytes = base64.b64decode(encoded_data)
        decoded_str = urllib.parse.unquote(decoded_bytes.decode('utf-8'))
        survey_structure = json.loads(decoded_str)
    except:
        st.error("잘못된 설문 링크입니다.")

# B. URL에 없고, 방금 1번 페이지에서 넘어왔으면 (연구자 모드) -> 그걸 씀
elif 'survey_design' in st.session_state:
    survey_structure = st.session_state['survey_design']

# --------------------------------------------------------------------------
# 3. 화면 UI 구성
# --------------------------------------------------------------------------
if not survey_structure:
    st.warning("⚠️ 설정된 설문이 없습니다.")
    st.info("👈 [1_연구_설계_진단] 페이지에서 먼저 구조를 확정하고 버튼을 눌러주세요.")
    st.stop()

# --- [연구자 모드] 공유 링크 생성 화면 ---
if not encoded_data: 
    st.title("📢 설문지 배포 센터")
    st.markdown(f"**목표:** {survey_structure['goal']}")
    
    # 데이터를 문자열로 변환 후 URL 인코딩
    json_str = json.dumps(survey_structure)
    b64_str = base64.b64encode(urllib.parse.quote(json_str).encode('utf-8')).decode('utf-8')
    
    # 현재 사이트 주소 (배포 시 실제 도메인으로 변경됨)
    base_url = "https://ahp-platform.streamlit.app/설문_진행" 
    share_url = f"{base_url}?data={b64_str}"

    st.success("설문 링크가 생성되었습니다! 아래 링크를 복사해서 공유하세요.")
    st.code(share_url, language="text")

    # 공유 버튼들
    c1, c2 = st.columns(2)
    with c1:
        # 이메일 공유 (Mailto)
        subject = f"[설문 요청] {survey_structure['goal']} 관련 전문가 설문"
        body = f"안녕하세요.\n다음 링크를 통해 AHP 설문에 참여 부탁드립니다.\n\n링크: {share_url}"
        mailto_link = f"mailto:?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
        st.link_button("📧 이메일로 보내기", mailto_link, type="primary", use_container_width=True)
    
    with c2:
        # 카카오톡은 API 연동이 필요하므로 '링크 복사' 안내로 대체 (현실적)
        st.info("💬 카카오톡: 위 링크를 복사해서 채팅방에 붙여넣으세요.")

    st.divider()
    st.markdown("👇 **아래는 응답자가 보게 될 화면 미리보기입니다.**")

# --- [응답자 모드] 실제 설문 화면 ---
st.header(f"📝 {survey_structure['goal']} 의사결정 설문")

# 친구의 HTML/JS 코드에 '데이터 전송 기능' 주입
# (여기에 survey_structure의 기준들을 Javascript 변수로 넣어줍니다)
criteria_js_array = json.dumps(survey_structure['criteria']) 

html_code = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<style>
    /* ... (친구의 스타일 코드 그대로) ... */
    body {{ font-family: sans-serif; padding: 20px; }}
    .container {{ max-width: 700px; margin: 0 auto; border:1px solid #ddd; padding:20px; border-radius:10px; }}
    .btn {{ width: 100%; padding: 10px; background: #228be6; color: white; border: none; border-radius: 5px; cursor: pointer; }}
    input[type=range] {{ width: 100%; }}
</style>
</head>
<body>

<div class="container" id="survey-box">
    <h3 style="text-align:center;">쌍대비교 설문</h3>
    <div id="comparison-area"></div>
    <div style="text-align:center; margin-top:20px;">
        <button class="btn" id="submit-btn" style="display:none;" onclick="sendDataToPython()">제출하기</button>
    </div>
</div>

<script>
    // Python에서 넘겨준 항목들
    const criteria = {criteria_js_array};
    let pairs = [];
    let answers = {{}}; // 결과 저장

    // 비교 쌍 생성
    for(let i=0; i<criteria.length; i++) {{
        for(let j=i+1; j<criteria.length; j++) {{
            pairs.push([criteria[i], criteria[j]]);
        }}
    }}

    let currentIdx = 0;

    function renderComparison() {{
        if(currentIdx >= pairs.length) {{
            document.getElementById('comparison-area').innerHTML = "<h3>설문이 완료되었습니다!</h3><p>제출 버튼을 눌러주세요.</p>";
            document.getElementById('submit-btn').style.display = 'block';
            return;
        }}

        const p = pairs[currentIdx];
        document.getElementById('comparison-area').innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
                <strong style="font-size:1.2em;">${{p[0]}}</strong>
                <span style="color:#888;">VS</span>
                <strong style="font-size:1.2em;">${{p[1]}}</strong>
            </div>
            <input type="range" id="slider" min="-9" max="9" value="0" step="1">
            <div style="display:flex; justify-content:space-between; color:#666; font-size:0.8em;">
                <span>⬅ 왼쪽 중요</span>
                <span>동등</span>
                <span>오른쪽 중요 ➡</span>
            </div>
            <button class="btn" style="margin-top:20px; background:#868e96;" onclick="nextStep()">다음</button>
        `;
    }}

    function nextStep() {{
        const val = document.getElementById('slider').value;
        const p = pairs[currentIdx];
        // 결과 저장 (A, B, 값)
        answers[`${{p[0]}}_vs_${{p[1]}}`] = val;
        
        currentIdx++;
        renderComparison();
    }}

    // [핵심] Python으로 데이터 전송
    function sendDataToPython() {{
        // 이 부분은 Streamlit Component 기능이 필요하지만, 
        // iframe 방식에선 부모창 통신이 복잡하므로 
        // 여기서는 간단히 '복사'하게 하거나 로직을 보여주는 용도입니다.
        // 실제로는 Streamlit Custom Component를 써야 완벽합니다.
        
        const resultJson = JSON.stringify(answers);
        
        // (임시) 화면에 출력해서 보여줌
        document.getElementById('survey-box').innerHTML = `
            <h3>제출되었습니다.</h3>
            <p>아래 코드를 복사해주세요 (임시):</p>
            <textarea style="width:100%; height:100px;">${{resultJson}}</textarea>
        `;
    }}

    renderComparison(); // 시작
</script>
</body>
</html>
"""

# Streamlit은 iframe에서 직접 데이터를 받아오는 게 까다롭습니다.
# 그래서 '제출' 버튼을 Python 쪽에 따로 만듭니다. (하이브리드 방식)

components.html(html_code, height=400, scrolling=True)

st.divider()

# 실제 데이터 수집 폼 (Streamlit Native)
with st.form("submission_form"):
    st.write("**📝 설문 제출 (마지막 단계)**")
    respondent_name = st.text_input("응답자 성함/소속 (선택)")
    
    # 실제로는 위의 HTML에서 데이터를 받아와야 하지만, 
    # 구현 난이도상 여기서는 간단한 '소감'이나 '의견'을 받는 걸로 대체하거나
    # 위 HTML이 'Custom Component'여야 자동 수집이 됩니다.
    # 일단 흐름을 보여드리기 위해 '완료 확인' 버튼으로 만듭니다.
    
    submitted = st.form_submit_button("설문 결과 서버로 전송하기")
    
    if submitted:
        # 데이터 저장 로직
        response_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "respondent": respondent_name,
            "survey_id": survey_structure['goal'],
            "status": "Completed"
            # 실제 가중치 데이터는 여기서 연결 필요
        }
        
        if save_response(response_data):
            st.success("✅ 소중한 의견이 '결과 데이터 센터'에 저장되었습니다!")
        else:
            st.error("저장 실패")
