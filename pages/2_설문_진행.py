import streamlit as st
import streamlit.components.v1 as components
import json
import base64
import urllib.parse
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="설문 진행", page_icon="📝", layout="wide")

# 1. URL 데이터 복원
query_params = st.query_params
encoded_data = query_params.get("data", None)
survey_data = None

if encoded_data:
    try:
        decoded_b64 = urllib.parse.unquote(encoded_data)
        decoded_bytes = base64.b64decode(decoded_b64)
        survey_data = json.loads(decoded_bytes.decode("utf-8"))
    except:
        st.error("잘못된 링크입니다.")
        st.stop()
else:
    # 테스트용 (1번 페이지에서 넘어온 경우)
    if 'passed_structure' in st.session_state:
        survey_data = st.session_state['passed_structure']
    else:
        st.warning("⚠️ 활성화된 설문이 없습니다.")
        st.stop()

# 2. 설문 화면
st.title(f"📝 {survey_data['goal']}")
st.caption("각 카테고리별 세부 항목들의 중요도를 비교해주세요.")

# [핵심] 세부 항목 데이터를 통째로 JS로 넘김
js_sub_criteria = json.dumps(survey_data['sub_criteria'], ensure_ascii=False)

html_code = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<style>
    body {{ font-family: "Pretendard", sans-serif; padding: 10px; }}
    .category-title {{ 
        background: #f1f3f5; padding: 10px; border-radius: 8px; 
        margin-top: 30px; margin-bottom: 10px; font-weight: bold; color: #495057;
    }}
    .card {{ 
        border: 1px solid #e0e0e0; border-radius: 12px; padding: 20px; 
        margin-bottom: 15px; background: white; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }}
    .vs-box {{ 
        display: flex; justify-content: space-between; align-items: center; 
        font-weight: bold; font-size: 1.1em; margin-bottom: 15px;
    }}
    input[type=range] {{ width: 100%; margin: 15px 0; }}
    .val-disp {{ text-align: center; font-weight: bold; color: #228be6; }}
    .btn {{ width:100%; padding:15px; background:#228be6; color:white; border:none; border-radius:8px; cursor:pointer; font-size:1.1em; }}
</style>
</head>
<body>

<div id="survey-area"></div>
<div id="result-area" style="display:none; text-align:center; margin-top:20px;">
    <h3>🎉 설문 완료!</h3>
    <p>아래 <b>[결과 코드]</b>를 복사해서 하단의 입력창에 붙여넣어주세요.</p>
    <textarea id="result-code" style="width:100%; height:100px; font-family:monospace;"></textarea>
</div>

<script>
    // Python에서 받은 데이터: {{"기준A": ["a1", "a2"], "기준B": ["b1", "b2"]}}
    const subCriteria = {js_sub_criteria};
    
    // 전체 비교 쌍 생성 (1차 기준은 건너뛰고 세부 항목만!)
    let allPairs = [];
    
    // 딕셔너리 순회
    for (const [category, items] of Object.entries(subCriteria)) {{
        if (items.length < 2) continue; // 항목이 1개면 비교 불가
        
        for(let i=0; i<items.length; i++) {{
            for(let j=i+1; j<items.length; j++) {{
                allPairs.push({{
                    category: category,
                    itemA: items[i],
                    itemB: items[j]
                }});
            }}
        }}
    }}
    
    const area = document.getElementById('survey-area');
    
    function render() {{
        let html = "";
        let currentCat = "";
        
        allPairs.forEach((p, idx) => {{
            // 카테고리가 바뀔 때 헤더 표시
            if (p.category !== currentCat) {{
                html += `<div class="category-title">📂 ${{p.category}} 부문 비교</div>`;
                currentCat = p.category;
            }}
            
            html += `
            <div class="card">
                <div class="vs-box">
                    <span style="color:#228be6;">${{p.itemA}}</span>
                    <span style="font-size:0.8em; color:#ccc;">VS</span>
                    <span style="color:#fa5252;">${{p.itemB}}</span>
                </div>
                <input type="range" id="r_${{idx}}" min="-9" max="9" value="0" step="1" oninput="upd(${{idx}})">
                <div id="d_${{idx}}" class="val-disp">동등함 (1:1)</div>
            </div>`;
        }});
        
        if (allPairs.length === 0) {{
            html = "<p>비교할 세부 항목이 부족합니다. (최소 2개 이상)</p>";
        }} else {{
            html += `<button class="btn" onclick="finish()">결과 코드 생성하기</button>`;
        }}
        
        area.innerHTML = html;
    }}
    
    function upd(idx) {{
        const val = document.getElementById('r_'+idx).value;
        const disp = document.getElementById('d_'+idx);
        const p = allPairs[idx];
        
        if(val==0) disp.innerText = "동등함";
        else if(val<0) disp.innerText = p.itemA + " 쪽으로 " + (Math.abs(val)+1) + "배 중요";
        else disp.innerText = p.itemB + " 쪽으로 " + (Number(val)+1) + "배 중요";
    }}
    
    function finish() {{
        let answers = {{}};
        allPairs.forEach((p, idx) => {{
            // 키 형식: [카테고리]항목A_vs_항목B
            const key = `[${{p.category}}]${{p.itemA}}_vs_${{p.itemB}}`;
            answers[key] = document.getElementById('r_'+idx).value;
        }});
        
        const finalJson = JSON.stringify(answers);
        document.getElementById('result-area').style.display = 'block';
        document.getElementById('result-code').value = finalJson;
        document.getElementById('survey-area').style.display = 'none';
    }}
    
    render();
</script>
</body>
</html>
"""

components.html(html_code, height=800, scrolling=True)

# 3. 데이터 저장
st.divider()
st.markdown("### 📥 데이터 제출")
with st.form("save_form"):
    respondent = st.text_input("응답자 성함")
    result_code = st.text_area("결과 코드 붙여넣기")
    
    if st.form_submit_button("제출하기", type="primary"):
        if result_code:
            try:
                json.loads(result_code) # 유효성 검사
                save_data = {
                    "Time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Goal": survey_data['goal'],
                    "Respondent": respondent,
                    "Raw_Data": result_code
                }
                df = pd.DataFrame([save_data])
                try:
                    old_df = pd.read_csv("ahp_results.csv")
                    final_df = pd.concat([old_df, df], ignore_index=True)
                except:
                    final_df = df
                final_df.to_csv("ahp_results.csv", index=False)
                st.success("데이터가 저장되었습니다!")
            except:
                st.error("코드가 올바르지 않습니다.")
