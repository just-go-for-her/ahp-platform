import streamlit as st
import streamlit.components.v1 as components
import json
import base64
import urllib.parse
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="설문 진행", page_icon="📝", layout="wide")

# 1. URL 데이터 확인 (응답자인지 연구자인지 구분)
query_params = st.query_params
encoded_data = query_params.get("data", None)
survey_data = None

if encoded_data:
    try:
        decoded_b64 = urllib.parse.unquote(encoded_data)
        decoded_bytes = base64.b64decode(decoded_b64)
        survey_data = json.loads(decoded_bytes.decode("utf-8"))
        is_respondent = True
    except:
        st.error("잘못된 링크입니다.")
        st.stop()
else:
    is_respondent = False
    if 'passed_structure' in st.session_state:
        survey_data = st.session_state['passed_structure']
    else:
        survey_data = None

# ------------------------------------------------------------------
# [MODE A] 연구자 모드: 링크 생성 (배포 기능이 여기로 옴)
# ------------------------------------------------------------------
if not is_respondent:
    st.title("📢 설문 배포 센터")
    
    if not survey_data:
        st.warning("⚠️ 확정된 구조가 없습니다.")
        st.info("👈 [1_연구_설계_진단] 페이지에서 먼저 구조를 확정하고 버튼을 눌러주세요.")
        st.stop()

    st.markdown(f"**목표:** {survey_data['goal']}")
    st.success("1번 페이지에서 구조를 불러왔습니다. 배포용 링크를 생성합니다.")

    # [핵심 해결책] 사이트 주소 자동/수동 설정
    # Access Denied 에러를 막기 위해 진짜 주소를 넣어야 함
    with st.expander("⚙️ 배포 설정 (중요)", expanded=True):
        st.caption("배포된 링크가 작동하지 않는다면, 아래 주소를 실제 사이트 주소로 바꿔주세요.")
        # 기본값은 현재 브라우저의 URL을 복사해서 넣으라고 안내
        base_url = st.text_input("내 사이트 주소 (Base URL)", value="https://ahp-platform.streamlit.app/설문_진행")

    if st.button("🔗 공유 링크 생성하기", type="primary"):
        # 데이터 패키징
        full_structure = {
            "goal": survey_data['goal'],
            "main_criteria": survey_data['main_criteria'],
            "sub_criteria": survey_data['sub_criteria']
        }
        
        # 암호화
        json_str = json.dumps(full_structure, ensure_ascii=False)
        b64_data = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")
        url_safe = urllib.parse.quote(b64_data)
        
        # 최종 URL
        # 입력받은 base_url 뒤에 파라미터 붙이기
        # 만약 base_url이 'pages/'를 포함하지 않는 메인 주소라면 경로 수정 필요할 수 있음
        # 안전하게 사용자가 입력한 값 그대로 사용
        final_url = f"{base_url}?data={url_safe}"
        
        st.success("설문 링크가 생성되었습니다!")
        st.code(final_url, language="text")
        st.info("💡 위 링크를 복사해서 **새 인터넷 창(시크릿 모드)**에 붙여넣어 테스트해보세요.")

# ------------------------------------------------------------------
# [MODE B] 응답자 모드: 설문 응답 (세부 항목만 비교)
# ------------------------------------------------------------------
else:
    st.title(f"📝 {survey_data['goal']}")
    st.caption("각 부문별 세부 항목의 중요도를 비교해주세요.")

    js_sub_criteria = json.dumps(survey_data['sub_criteria'], ensure_ascii=False)

    html_code = f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: "Pretendard", sans-serif; padding: 10px; }}
        .category-title {{ background: #f8f9fa; padding: 10px; border-left: 5px solid #228be6; margin-top: 30px; font-weight: bold; color: #333; }}
        .card {{ border: 1px solid #eee; padding: 20px; margin-bottom: 15px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }}
        input[type=range] {{ width: 100%; margin: 15px 0; }}
        .val-disp {{ text-align: center; font-weight: bold; color: #228be6; }}
        .btn {{ width:100%; padding:15px; background:#228be6; color:white; border:none; border-radius:8px; cursor:pointer; font-size:1.1em; margin-top:20px; }}
    </style>
    </head>
    <body>
    <div id="survey-area"></div>
    <div id="result-area" style="display:none; text-align:center; margin-top:20px;">
        <h3>🎉 설문 완료!</h3>
        <p>아래 코드를 복사해서 하단 입력창에 붙여넣으세요.</p>
        <textarea id="result-code" style="width:100%; height:80px;"></textarea>
    </div>
    <script>
        const subCriteria = {js_sub_criteria};
        let allPairs = [];
        
        // 1차 기준 건너뛰고 세부 항목만 쌍 생성
        for (const [category, items] of Object.entries(subCriteria)) {{
            if (items.length < 2) continue;
            for(let i=0; i<items.length; i++) {{
                for(let j=i+1; j<items.length; j++) {{
                    allPairs.push({{ cat: category, a: items[i], b: items[j] }});
                }}
            }}
        }}
        
        const area = document.getElementById('survey-area');
        
        function render() {{
            if (allPairs.length === 0) {{
                area.innerHTML = "<p>비교할 세부 항목이 없습니다. (각 기준당 2개 이상 필요)</p>";
                return;
            }}
            
            let html = "";
            let currentCat = "";
            
            allPairs.forEach((p, idx) => {{
                if (p.cat !== currentCat) {{
                    html += `<div class="category-title">📂 ${{p.cat}} 부문</div>`;
                    currentCat = p.cat;
                }}
                html += `
                <div class="card">
                    <div style="display:flex; justify-content:space-between; font-weight:bold;">
                        <span>${{p.a}}</span> <span>VS</span> <span>${{p.b}}</span>
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
            const p = allPairs[idx];
            if(val==0) disp.innerText = "동등함";
            else if(val<0) disp.innerText = p.a + " 쪽으로 " + (Math.abs(val)+1) + "배";
            else disp.innerText = p.b + " 쪽으로 " + (Number(val)+1) + "배";
        }}
        
        function finish() {{
            let ans = {{}};
            allPairs.forEach((p, idx) => {{
                ans[`[${{p.cat}}]${{p.a}}_vs_${{p.b}}`] = document.getElementById('r_'+idx).value;
            }});
            document.getElementById('result-area').style.display = 'block';
            document.getElementById('result-code').value = JSON.stringify(ans);
            document.getElementById('survey-area').style.display = 'none';
        }}
        render();
    </script>
    </body>
    </html>
    """
    components.html(html_code, height=800, scrolling=True)

    st.divider()
    with st.form("save"):
        st.write("📋 **데이터 제출**")
        respondent = st.text_input("응답자 성함")
        code = st.text_area("결과 코드 붙여넣기")
        if st.form_submit_button("제출"):
            try:
                json.loads(code)
                # 저장 로직 (CSV)
                save_data = {"Time": datetime.now().strftime("%Y-%m-%d %H:%M"), "Goal": survey_data['goal'], "Respondent": respondent, "Data": code}
                df = pd.DataFrame([save_data])
                try: old_df = pd.read_csv("ahp_results.csv")
                except: old_df = pd.DataFrame()
                pd.concat([old_df, df], ignore_index=True).to_csv("ahp_results.csv", index=False)
                st.success("제출 완료! [3_결과_데이터_센터]에서 확인하세요.")
            except:
                st.error("코드가 올바르지 않습니다.")
