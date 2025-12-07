import streamlit as st
import streamlit.components.v1 as components
import json
import base64
import urllib.parse
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="설문 생성 및 진행", page_icon="📝", layout="wide")

# ------------------------------------------------------------------
# 1. URL 데이터 확인 (응답자인지 연구자인지 구분)
# ------------------------------------------------------------------
query_params = st.query_params
encoded_data = query_params.get("data", None)
survey_data = None

# 응답자 모드 (URL에 데이터가 있음)
if encoded_data:
    try:
        decoded_b64 = urllib.parse.unquote(encoded_data)
        decoded_bytes = base64.b64decode(decoded_b64)
        survey_data = json.loads(decoded_bytes.decode("utf-8"))
        is_respondent = True
    except:
        st.error("잘못된 링크입니다.")
        st.stop()

# 연구자 모드 (URL 데이터 없음)
else:
    is_respondent = False
    # 1번 페이지에서 넘겨준 데이터가 있는지 확인
    if 'passed_structure' in st.session_state:
        initial_data = st.session_state['passed_structure']
    else:
        initial_data = {"goal": "", "criteria": []}

# ------------------------------------------------------------------
# 2. [연구자 모드] 구조 수정 및 링크 생성
# ------------------------------------------------------------------
if not is_respondent:
    st.title("🛠️ 설문지 구조 확정 및 배포")
    st.info("1번 페이지에서 가져온 구조를 여기서 최종 수정하고 링크를 만드세요.")

    # 1. 구조 수정 칸 마련 (요청사항)
    with st.container(border=True):
        st.subheader("1. 구조 최종 점검")
        final_goal = st.text_input("설문 제목 (목표)", value=initial_data.get("goal", ""))
        
        # 기준 수정 (콤마로 구분해서 입력받기)
        current_criteria = ", ".join(initial_data.get("criteria", []))
        final_criteria_str = st.text_area("비교할 항목들 (쉼표로 구분)", value=current_criteria, help="예: 맛, 가격, 서비스")
        
        final_criteria = [x.strip() for x in final_criteria_str.split(",") if x.strip()]

    # 2. 링크 생성 버튼
    if st.button("🔗 설문 링크 생성하기", type="primary"):
        if len(final_criteria) < 2:
            st.error("최소 2개 이상의 항목이 필요합니다.")
        else:
            # 패키징 & 암호화
            pkg = {"goal": final_goal, "criteria": final_criteria}
            json_str = json.dumps(pkg, ensure_ascii=False)
            b64_data = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")
            url_safe = urllib.parse.quote(b64_data)
            
            # 링크 표시
            base_url = "https://ahp-platform.streamlit.app/설문_진행"
            final_url = f"{base_url}?data={url_safe}"
            
            st.success("설문지가 완성되었습니다!")
            st.code(final_url, language="text")
            st.caption("위 링크를 복사해서 친구나 전문가에게 보내세요.")

# ------------------------------------------------------------------
# 3. [응답자 모드] 친구의 Tool 실행 & 데이터 수집
# ------------------------------------------------------------------
else:
    st.title(f"📝 {survey_data['goal']} - 전문가 설문")
    
    # 친구의 HTML Tool에 데이터를 넣어줍니다.
    js_criteria = json.dumps(survey_data['criteria'], ensure_ascii=False)
    
    # [친구의 Tool 코드 삽입] 
    # 핵심: 결과값을 복사할 수 있게 JS 수정됨
    html_code = f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: "Pretendard", sans-serif; padding: 10px; }}
        .card {{ border: 1px solid #ddd; padding: 20px; margin-bottom: 15px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }}
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
        const criteria = {js_criteria};
        let pairs = [], answers = {{}};
        
        // 쌍 생성
        for(let i=0; i<criteria.length; i++) {{
            for(let j=i+1; j<criteria.length; j++) {{ pairs.push([criteria[i], criteria[j]]); }}
        }}
        
        const area = document.getElementById('survey-area');
        
        function render() {{
            let html = "";
            pairs.forEach((p, idx) => {{
                html += `
                <div class="card">
                    <div style="display:flex; justify-content:space-between; font-weight:bold;">
                        <span>${{p[0]}}</span> <span>VS</span> <span>${{p[1]}}</span>
                    </div>
                    <input type="range" id="r_${{idx}}" min="-9" max="9" value="0" step="1" oninput="upd(${{idx}})">
                    <div id="d_${{idx}}" class="val-disp">동등함 (1:1)</div>
                </div>`;
            }});
            html += `<button class="btn" onclick="finish()">결과 코드 생성하기</button>`;
            area.innerHTML = html;
        }}
        
        function upd(idx) {{
            const val = document.getElementById('r_'+idx).value;
            const disp = document.getElementById('d_'+idx);
            if(val==0) disp.innerText = "동등함";
            else if(val<0) disp.innerText = "왼쪽이 " + (Math.abs(val)+1) + "배 중요";
            else disp.innerText = "오른쪽이 " + (Number(val)+1) + "배 중요";
        }}
        
        function finish() {{
            pairs.forEach((p, idx) => {{
                answers[`${{p[0]}}_vs_${{p[1]}}`] = document.getElementById('r_'+idx).value;
            }});
            // 결과 JSON 생성
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
    
    components.html(html_code, height=600, scrolling=True)
    
    st.divider()
    st.markdown("### 📥 데이터 제출 (마지막 단계)")
    st.info("위 화면에서 '결과 코드 생성하기'를 누른 뒤, 나온 코드를 아래에 붙여넣고 제출하세요.")
    
    with st.form("save_form"):
        respondent = st.text_input("응답자 성함")
        result_code = st.text_area("결과 코드 붙여넣기")
        
        if st.form_submit_button("✅ 최종 제출하기"):
            if not result_code:
                st.error("결과 코드를 입력해주세요.")
            else:
                # 데이터 저장 로직
                try:
                    # 유효한 JSON인지 확인
                    json.loads(result_code)
                    
                    save_data = {
                        "Time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "Goal": survey_data['goal'],
                        "Respondent": respondent,
                        "Raw_Data": result_code # 분석용 원본 데이터
                    }
                    
                    df = pd.DataFrame([save_data])
                    try:
                        old_df = pd.read_csv("ahp_results.csv")
                        final_df = pd.concat([old_df, df], ignore_index=True)
                    except:
                        final_df = df
                    
                    final_df.to_csv("ahp_results.csv", index=False)
                    st.success("수고하셨습니다! 데이터가 '결과 데이터 센터'로 전송되었습니다.")
                    st.balloons()
                except:
                    st.error("코드가 올바르지 않습니다. 복사한 코드를 정확히 붙여넣어 주세요.")
