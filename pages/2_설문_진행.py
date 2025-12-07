import streamlit as st
import streamlit.components.v1 as components
import json
import base64
import urllib.parse
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="설문 진행", page_icon="📝", layout="wide")

# 1. URL 데이터 처리
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
# [MODE A] 연구자: 설문 배포 화면
# ------------------------------------------------------------------
if not is_respondent:
    st.title("📢 설문 배포 센터")
    
    if not survey_data:
        st.warning("⚠️ 확정된 구조가 없습니다. [1번 페이지]에서 구조를 먼저 확정하세요.")
        st.stop()

    st.markdown(f"**목표:** {survey_data['goal']}")
    st.success("1번 페이지에서 구조를 불러왔습니다. 배포용 링크를 생성합니다.")

    with st.expander("⚙️ 배포 링크 설정 (필수)", expanded=True):
        st.caption("현재 브라우저 주소창의 주소를 복사해서 아래에 붙여넣으세요.")
        base_url = st.text_input("내 사이트 주소", value="https://ahp-platform.streamlit.app/설문_진행")

    if st.button("🔗 공유 링크 생성하기", type="primary"):
        full_structure = {
            "goal": survey_data['goal'],
            "main_criteria": survey_data['main_criteria'],
            "sub_criteria": survey_data['sub_criteria']
        }
        json_str = json.dumps(full_structure, ensure_ascii=False)
        b64_data = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")
        url_safe = urllib.parse.quote(b64_data)
        
        final_url = f"{base_url}?data={url_safe}"
        
        st.success("링크 생성 완료!")
        st.code(final_url, language="text")
        
        st.markdown("### 📤 공유하기")
        col1, col2 = st.columns(2)
        
        with col1:
            subject = f"[설문 요청] {survey_data['goal']} 전문가 의견 조사"
            body = f"안녕하세요.\n다음 링크를 통해 AHP 설문에 참여 부탁드립니다.\n\n링크: {final_url}"
            mailto_link = f"mailto:?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
            st.link_button("📧 이메일로 보내기", mailto_link, use_container_width=True)
            
        with col2:
            st.info("💬 **카카오톡 공유:** 위 링크를 복사해서 카톡방에 붙여넣으세요.")

# ------------------------------------------------------------------
# [MODE B] 응답자: 설문 진행 (오류 수정됨)
# ------------------------------------------------------------------
else:
    st.title(f"📝 {survey_data['goal']}")
    st.caption("각 부문별 세부 항목의 중요도를 비교해주세요.")

    # Python 데이터를 JS로 넘기기
    js_sub_criteria = json.dumps(survey_data['sub_criteria'], ensure_ascii=False)

    # HTML/JS 코드 (f-string 사용 시 중괄호 {{ }} 주의)
    html_code = f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: "Pretendard", sans-serif; padding: 20px; }}
        .category-header {{ 
            background: #e7f5ff; color: #1c7ed6; padding: 15px; border-radius: 8px; 
            margin-bottom: 20px; font-weight: bold; text-align: center; font-size: 1.2em;
        }}
        .card {{ 
            border: 1px solid #dee2e6; padding: 30px; border-radius: 12px; 
            text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.05); background: white;
        }}
        .vs-row {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; font-size: 1.3em; font-weight: bold; }}
        input[type=range] {{ width: 100%; margin: 20px 0; cursor: pointer; }}
        .btn {{ width: 100%; padding: 15px; background: #228be6; color: white; border: none; border-radius: 8px; font-size: 1.1em; cursor: pointer; margin-top: 20px; }}
        
        /* 모달 스타일 */
        .modal {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); justify-content: center; align-items: center; }}
        .modal-content {{ background: white; padding: 30px; border-radius: 15px; width: 90%; max-width: 400px; text-align: center; }}
        .logic-val {{ color: #1c7ed6; font-weight: bold; }}
        .user-val {{ color: #fa5252; font-weight: bold; }}
    </style>
    </head>
    <body>

    <div id="survey-container" style="max-width: 600px; margin: 0 auto;">
        <div id="header-area"></div>
        <div id="card-area" class="card"></div>
    </div>

    <div id="result-area" style="display:none; text-align:center; margin-top:50px;">
        <h3>🎉 설문 완료!</h3>
        <p>아래 결과 코드를 복사해서 제출해주세요.</p>
        <textarea id="result-code" style="width:100%; height:100px; font-family:monospace;"></textarea>
    </div>

    <div id="conflict-modal" class="modal">
        <div class="modal-content">
            <h3>⚠️ 논리적 일관성 확인</h3>
            <p>앞선 답변들과 논리적으로 상충됩니다.</p>
            <div style="margin: 20px 0; text-align: left; background: #f8f9fa; padding: 15px; border-radius: 8px;">
                <div>🧠 논리적 추천: <span id="rec-val" class="logic-val"></span></div>
                <div style="margin-top:10px;">🖐 당신의 선택: <span id="my-val" class="user-val"></span></div>
            </div>
            <div style="display:flex; gap:10px;">
                <button class="btn" style="background:#868e96;" onclick="closeModal(false)">다시 선택</button>
                <button class="btn" onclick="closeModal(true)">선택 유지</button>
            </div>
        </div>
    </div>

    <script>
        const subCriteria = {js_sub_criteria};
        
        // 1. 전체 비교 쌍 생성
        let surveyGroups = [];
        
        for (const [cat, items] of Object.entries(subCriteria)) {{
            if (items.length < 2) continue;
            
            let pairs = [];
            let n = items.length;
            let matrix = Array.from({{length: n}}, () => Array(n).fill(0));
            for(let i=0; i<n; i++) matrix[i][i] = 1;
            
            for(let i=0; i<n; i++) {{
                for(let j=i+1; j<n; j++) {{
                    pairs.push({{ r: i, c: j, nameA: items[i], nameB: items[j] }});
                }}
            }}
            surveyGroups.push({{ cat: cat, items: items, pairs: pairs, matrix: matrix }});
        }}

        // 상태 변수
        let groupIdx = 0;
        let pairIdx = 0;
        let pendingVal = 0;
        let answers = {{}};

        function render() {{
            if (groupIdx >= surveyGroups.length) {{
                finishSurvey();
                return;
            }}

            const group = surveyGroups[groupIdx];
            document.getElementById('header-area').innerHTML = `<div class="category-header">📂 ${{group.cat}} 부문 (${{pairIdx + 1}} / ${{group.pairs.length}})</div>`;
            
            const p = group.pairs[pairIdx];
            document.getElementById('card-area').innerHTML = `
                <div class="vs-row">
                    <span style="color:#228be6;">${{p.nameA}}</span>
                    <span style="font-size:0.8em; color:#adb5bd;">VS</span>
                    <span style="color:#fa5252;">${{p.nameB}}</span>
                </div>
                <input type="range" id="slider" min="-9" max="9" value="0" step="1" oninput="updateDisp()">
                <div id="disp-val" style="margin-top:10px; font-weight:bold; color:#868e96;">동등함 (1:1)</div>
                <div style="display:flex; justify-content:space-between; font-size:0.8em; color:#888; margin-top:5px;">
                    <span>◀ 왼쪽 중요</span>
                    <span>오른쪽 중요 ▶</span>
                </div>
                <button class="btn" onclick="checkConsistency()">다음 질문</button>
            `;
            updateDisp();
        }}

        function updateDisp() {{
            const val = parseInt(document.getElementById('slider').value);
            const disp = document.getElementById('disp-val');
            const p = surveyGroups[groupIdx].pairs[pairIdx];
            
            if(val == 0) {{
                disp.innerText = "동등함 (1:1)";
                disp.style.color = "#868e96";
            }} else if (val < 0) {{
                disp.innerText = p.nameA + " 쪽으로 " + (Math.abs(val)+1) + "배";
                disp.style.color = "#228be6";
            }} else {{
                disp.innerText = p.nameB + " 쪽으로 " + (val+1) + "배";
                disp.style.color = "#fa5252";
            }}
        }}

        function checkConsistency() {{
            const sliderVal = parseInt(document.getElementById('slider').value);
            let weight = sliderVal === 0 ? 1 : (sliderVal < 0 ? Math.abs(sliderVal) + 1 : 1 / (sliderVal + 1));
            
            const group = surveyGroups[groupIdx];
            const p = group.pairs[pairIdx];
            const n = group.items.length;
            const matrix = group.matrix;

            let conflict = false;
            let logicalW = 0;

            for (let k = 0; k < n; k++) {{
                if (k === p.r || k === p.c) continue;
                if (matrix[p.r][k] !== 0 && matrix[k][p.c] !== 0) {{
                    const predicted = matrix[p.r][k] * matrix[k][p.c];
                    const ratio = predicted > weight ? predicted / weight : weight / predicted;
                    if (ratio > 3.0) {{ 
                        conflict = true; 
                        logicalW = predicted; 
                        break; 
                    }}
                }}
            }}

            if (conflict) {{
                showModal(logicalW, weight);
                pendingVal = weight;
            }} else {{
                saveAndNext(weight);
            }}
        }}

        function showModal(logicalW, userW) {{
            const format = (w) => w >= 1 ? "왼쪽으로 " + w.toFixed(1) + "배" : "오른쪽으로 " + (1/w).toFixed(1) + "배";
            document.getElementById('rec-val').innerText = format(logicalW);
            document.getElementById('my-val').innerText = format(userW);
            document.getElementById('conflict-modal').style.display = 'flex';
        }}

        function closeModal(confirm) {{
            document.getElementById('conflict-modal').style.display = 'none';
            if (confirm) saveAndNext(pendingVal);
        }}

        function saveAndNext(weight) {{
            const group = surveyGroups[groupIdx];
            const p = group.pairs[pairIdx];
            
            group.matrix[p.r][p.c] = weight;
            group.matrix[p.c][p.r] = 1 / weight;
            
            const key = `[${{group.cat}}]${{p.nameA}}_vs_${{p.nameB}}`;
            let sliderVal = document.getElementById('slider').value; 
            answers[key] = sliderVal;

            pairIdx++;
            if (pairIdx >= group.pairs.length) {{
                groupIdx++;
                pairIdx = 0;
            }}
            render();
        }}

        function finishSurvey() {{
            document.getElementById('survey-container').style.display = 'none';
            document.getElementById('result-area').style.display = 'block';
            document.getElementById('result-code').value = JSON.stringify(answers);
        }}

        render();
    </script>
    </body>
    </html>
    """
    
    components.html(html_code, height=600, scrolling=True)

    st.divider()
    with st.form("save"):
        st.write("📋 **데이터 제출**")
        respondent = st.text_input("응답자 성함")
        code = st.text_area("결과 코드 붙여넣기")
        if st.form_submit_button("제출"):
            try:
                json.loads(code)
                save_data = {"Time": datetime.now().strftime("%Y-%m-%d %H:%M"), "Goal": survey_data['goal'], "Respondent": respondent, "Data": code}
                df = pd.DataFrame([save_data])
                try: old_df = pd.read_csv("ahp_results.csv")
                except: old_df = pd.DataFrame()
                pd.concat([old_df, df], ignore_index=True).to_csv("ahp_results.csv", index=False)
                st.success("제출 완료! [3_결과_데이터_센터]에서 확인하세요.")
            except:
                st.error("코드가 올바르지 않습니다.")
