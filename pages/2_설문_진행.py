import streamlit as st
import streamlit.components.v1 as components
import json
import base64
import urllib.parse
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="설문 진행", page_icon="📝", layout="wide")

# --------------------------------------------------------------------------
# 1. 데이터 복원 (URL -> Python)
# --------------------------------------------------------------------------
survey_data = None

# (1) URL에 데이터가 있는지 확인 (공유받은 사람)
query_params = st.query_params
encoded_data = query_params.get("data", None)

if encoded_data:
    try:
        # 암호 해독 (URL Decode -> Base64 Decode -> JSON Load)
        decoded_b64 = urllib.parse.unquote(encoded_data)
        decoded_bytes = base64.b64decode(decoded_b64)
        survey_data = json.loads(decoded_bytes.decode("utf-8"))
    except Exception as e:
        st.error(f"❌ 설문 링크가 손상되었습니다. (Error: {e})")
        st.stop()

# (2) URL에 없으면 세션 확인 (연구자 본인)
elif 'survey_design' in st.session_state:
    survey_data = st.session_state['survey_design']

# (3) 둘 다 없으면 에러 표시
else:
    st.warning("⚠️ 활성화된 설문이 없습니다.")
    st.info("👈 [1_연구_설계_진단] 메뉴에서 먼저 설문을 만들어주세요.")
    st.stop()

# --------------------------------------------------------------------------
# 2. 설문 화면 표시
# --------------------------------------------------------------------------
st.title(f"📝 {survey_data['goal']}")
st.caption("다음 항목들의 중요도를 비교해주세요.")

# [중요] Python 리스트를 자바스크립트용 문자열로 변환 (오류 해결 핵심!)
# ensure_ascii=False를 해야 한글이 깨지지 않고 JS로 넘어갑니다.
js_criteria = json.dumps(survey_data['criteria'], ensure_ascii=False)

# 친구의 HTML 코드 (데이터 주입 부분 수정됨)
html_code = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<style>
    body {{ font-family: "Pretendard", sans-serif; padding: 10px; }}
    .card {{ 
        border: 1px solid #e0e0e0; border-radius: 12px; padding: 20px; 
        margin-bottom: 15px; background: white; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }}
    .vs-box {{ 
        display: flex; justify-content: space-between; align-items: center; 
        font-weight: bold; font-size: 1.1em; margin-bottom: 15px;
    }}
    .slider-wrapper {{ position: relative; height: 40px; }}
    input[type=range] {{ 
        width: 100%; cursor: pointer;
    }}
    .labels {{ 
        display: flex; justify-content: space-between; font-size: 0.85em; color: #666; margin-top: 5px;
    }}
    .val-display {{ text-align: center; color: #228be6; font-weight: bold; margin-bottom: 10px; }}
</style>
</head>
<body>

<div id="survey-container"></div>
<div style="text-align: center; margin-top: 20px; color: #888;">
    <small>모든 응답을 완료하면 아래 '제출' 버튼을 눌러주세요.</small>
</div>

<script>
    // Python에서 받은 데이터 (여기서 에러가 많이 납니다. json.dumps 필수!)
    const criteria = {js_criteria};
    
    // 쌍대비교 조합 생성
    let pairs = [];
    for(let i=0; i<criteria.length; i++) {{
        for(let j=i+1; j<criteria.length; j++) {{
            pairs.push([criteria[i], criteria[j]]);
        }}
    }}

    const container = document.getElementById('survey-container');
    
    pairs.forEach((pair, idx) => {{
        const itemA = pair[0];
        const itemB = pair[1];
        
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `
            <div class="vs-box">
                <span style="color:#228be6;">${{itemA}}</span>
                <span style="font-size:0.8em; color:#ccc;">VS</span>
                <span style="color:#fa5252;">${{itemB}}</span>
            </div>
            <div class="val-display" id="disp_${{idx}}">동등함 (1:1)</div>
            <div class="slider-wrapper">
                <input type="range" id="rng_${{idx}}" min="-9" max="9" value="0" step="1" 
                       oninput="updateLabel(${{idx}}, '${{itemA}}', '${{itemB}}')">
            </div>
            <div class="labels">
                <span>◀ ${{itemA}} 중요</span>
                <span>${{itemB}} 중요 ▶</span>
            </div>
        `;
        container.appendChild(card);
    }});

    function updateLabel(idx, nameA, nameB) {{
        const val = parseInt(document.getElementById('rng_' + idx).value);
        const disp = document.getElementById('disp_' + idx);
        
        if (val === 0) disp.innerText = "동등함 (1:1)";
        else if (val < 0) disp.innerText = `${{nameA}} 쪽으로 ${{Math.abs(val)+1}}배`;
        else disp.innerText = `${{nameB}} 쪽으로 ${{val+1}}배`;
    }}
</script>

</body>
</html>
"""

# HTML 렌더링
components.html(html_code, height=600, scrolling=True)

# --------------------------------------------------------------------------
# 3. 제출 및 저장 (파이썬 로직)
# --------------------------------------------------------------------------
st.divider()
with st.form("survey_form"):
    st.write("📋 **설문 제출하기**")
    respondent = st.text_input("응답자 성함 (선택사항)")
    
    # [참고] 원래는 HTML에서 값을 받아와야 하지만, 
    # Streamlit 기본 기능으로는 통신이 어렵습니다. 
    # 일단은 '제출 버튼'이 동작하고 데이터가 쌓이는 흐름을 확인하세요.
    
    submit = st.form_submit_button("설문 결과 전송", type="primary")
    
    if submit:
        # 데이터 저장 (CSV)
        save_data = {
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Goal": survey_data['goal'],
            "Respondent": respondent,
            "Status": "Completed"
        }
        
        df = pd.DataFrame([save_data])
        
        # 파일이 없으면 헤더 포함 저장, 있으면 이어쓰기
        try:
            old_df = pd.read_csv("ahp_survey_results.csv")
            new_df = pd.concat([old_df, df], ignore_index=True)
        except:
            new_df = df
            
        new_df.to_csv("ahp_survey_results.csv", index=False)
        
        st.success("✅ 제출되었습니다! [3_결과_데이터_센터]에서 확인할 수 있습니다.")
