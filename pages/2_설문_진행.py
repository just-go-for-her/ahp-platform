import streamlit as st
import streamlit.components.v1 as components
import json
import base64
import urllib.parse
import pandas as pd
import os
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
    
    with st.expander("⚙️ 배포 링크 설정", expanded=True):
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
        
        col1, col2 = st.columns(2)
        with col1:
            subject = f"[설문 요청] {survey_data['goal']}"
            body = f"링크: {final_url}"
            mailto = f"mailto:?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
            st.link_button("📧 이메일 보내기", mailto, use_container_width=True)
        with col2:
            st.info("💬 카카오톡은 링크를 복사해서 공유하세요.")

# ------------------------------------------------------------------
# [MODE B] 응답자: 동료의 로직 (순위 선정 + CR 체크) 적용
# ------------------------------------------------------------------
else:
    st.title(f"📝 {survey_data['goal']}")
    
    # 데이터를 JS로 넘기기 위해 구조화
    # Task List 생성: [ {name: "1차 기준", items: [...]}, {name: "비용 하위", items: [...]}, ... ]
    tasks = []
    
    # 1. 메인 기준
    if len(survey_data['main_criteria']) > 1:
        tasks.append({"name": "1차 기준 (Main Criteria)", "items": survey_data['main_criteria']})
    
    # 2. 세부 항목
    for cat, items in survey_data['sub_criteria'].items():
        if len(items) > 1:
            tasks.append({"name": f"[{cat}] 세부 항목", "items": items})
            
    js_tasks = json.dumps(tasks, ensure_ascii=False)

    html_code = f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: "Pretendard", sans-serif; padding: 20px; }}
        .step {{ display: none; animation: fadeIn 0.3s; }}
        .active {{ display: block; }}
        @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
        
        .container {{ max-width: 700px; margin: 0 auto; background: white; padding: 30px; border-radius: 15px; box-shadow: 0 5px 20px rgba(0,0,0,0.08); }}
        h2 {{ color: #333; border-bottom: 2px solid #228be6; padding-bottom: 10px; }}
        
        .ranking-item {{ display: flex; justify-content: space-between; margin-bottom: 10px; padding: 10px; background: #f8f9fa; border-radius: 8px; align-items: center; }}
        .rank-select {{ padding: 5px; border-radius: 5px; }}
        
        .card {{ background: #f1f3f5; padding: 20px; border-radius: 12px; text-align: center; margin-bottom: 20px; }}
        .vs-row {{ display: flex; justify-content: space-between; font-size: 1.2em; font-weight: bold; margin-bottom: 15px; }}
        input[type=range] {{ width: 100%; margin: 20px 0; }}
        
        .btn {{ width: 100%; padding: 15px; background: #228be6; color: white; border: none; border-radius: 8px; font-size: 1.1em; cursor: pointer; }}
        .btn:disabled {{ background: #adb5bd; }}
        
        /* 모달 (CR 체크) */
        .modal {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); justify-content: center; align-items: center; }}
        .modal-box {{ background: white; padding: 30px; border-radius: 15px; width: 90%; max-width: 400px; text-align: center; }}
        .logic-text {{ color: #228be6; font-weight: bold; }}
        .user-text {{ color: #fa5252; font-weight: bold; }}
    </style>
    </head>
    <body>

    <div class="container">
        <h3 id="task-title"></h3>
        
        <div id="step-ranking" class="step">
            <p>1. 각 항목의 중요도 순위를 미리 예상해 주세요.</p>
            <div id="ranking-list"></div>
            <button class="btn" onclick="startCompare()">비교 시작</button>
        </div>

        <div id="step-compare" class="step">
            <p>2. 두 항목 중 더 중요한 쪽을 선택하세요. (<span id="progress"></span>)</p>
            <div class="card">
                <div class="vs-row">
                    <span style="color:#228be6;" id="item-a">A</span>
                    <span style="font-size:0.8em; color:#999;">VS</span>
                    <span style="color:#fa5252;" id="item-b">B</span>
                </div>
                <div style="font-size:0.9em; color:#666; margin-bottom:10px;">
                    <span id="rank-hint-a"></span> vs <span id="rank-hint-b"></span>
                </div>
                <input type="range" id="slider" min="-8" max="8" value="0" step="1" oninput="updateLabel()">
                <div id="val-display" style="font-weight:bold; color:#555;">동등함</div>
            </div>
            <button class="btn" onclick="checkConsistency()">다음 질문</button>
        </div>

        <div id="step-finish" class="step">
            <h2>🎉 모든 설문 완료!</h2>
            <p>아래 코드를 복사해서 제출해주세요.</p>
            <textarea id="result-code" style="width:100%; height:150px;"></textarea>
        </div>
    </div>

    <div id="modal" class="modal">
        <div class="modal-box">
            <h3>⚠️ 논리적 일관성 확인</h3>
            <p>이전 답변들과 모순될 수 있습니다.</p>
            <div style="background:#f8f9fa; padding:15px; border-radius:8px; margin:15px 0; text-align:left;">
                <div>🧠 추천: <span id="rec-val" class="logic-text"></span></div>
                <div>🖐 선택: <span id="my-val" class="user-text"></span></div>
            </div>
            <div style="display:flex; gap:10px;">
                <button class="btn" style="background:#aaa;" onclick="closeModal(false)">수정</button>
                <button class="btn" onclick="closeModal(true)">유지</button>
            </div>
        </div>
    </div>

    <script>
        const tasks = {js_tasks};
        let currentTaskIdx = 0;
        
        // 현재 태스크 변수들
        let items = [];
        let pairs = [];
        let matrix = [];
        let pairIdx = 0;
        let initialRanks = [];
        let pendingVal = 0;
        
        let allAnswers = {{}}; // 최종 결과 저장소

        function loadTask() {{
            if (currentTaskIdx >= tasks.length) {{
                finishAll();
                return;
            }}
            
            const task = tasks[currentTaskIdx];
            items = task.items;
            document.getElementById('task-title').innerText = task.name;
            
            // 순위 UI 생성
            const listDiv = document.getElementById('ranking-list');
            listDiv.innerHTML = "";
            let options = '<option value="" selected disabled>선택</option>';
            for(let i=1; i<=items.length; i++) options += `<option value="${{i}}">${{i}}위</option>`;
            
            items.forEach((item, idx) => {{
                listDiv.innerHTML += `
                    <div class="ranking-item">
                        <span>${{item}}</span>
                        <select id="rank-${{idx}}" class="rank-select">${{options}}</select>
                    </div>`;
            }});
            
            showStep('step-ranking');
        }}

        function startCompare() {{
            // 순위 저장 및 검증
            initialRanks = [];
            let checks = [];
            for(let i=0; i<items.length; i++) {{
                const val = document.getElementById('rank-'+i).value;
                if(!val) {{ alert("순위를 모두 선택해주세요."); return; }}
                initialRanks.push(val);
                checks.push(val);
            }}
            
            // 행렬 및 쌍 초기화
            const n = items.length;
            matrix = Array.from({{length: n}}, () => Array(n).fill(0));
            for(let i=0; i<n; i++) matrix[i][i] = 1;
            
            pairs = [];
            for(let i=0; i<n; i++) {{
                for(let j=i+1; j<n; j++) {{
                    pairs.push({{ r: i, c: j, a: items[i], b: items[j] }});
                }}
            }}
            
            pairIdx = 0;
            showStep('step-compare');
            renderPair();
        }}

        function renderPair() {{
            if (pairIdx >= pairs.length) {{
                // 현재 태스크 완료 -> 다음 태스크로
                currentTaskIdx++;
                loadTask();
                return;
            }}
            
            const p = pairs[pairIdx];
            document.getElementById('progress').innerText = `${{pairIdx+1}} / ${{pairs.length}}`;
            document.getElementById('item-a').innerText = p.a;
            document.getElementById('item-b').innerText = p.b;
            document.getElementById('rank-hint-a').innerText = `예상 ${{-initialRanks[p.r]}}위`; // 마이너스는 텍스트용 임시
            document.getElementById('rank-hint-a').innerText = `(예상 ${{initialRanks[p.r]}}위)`;
            document.getElementById('rank-hint-b').innerText = `(예상 ${{initialRanks[p.c]}}위)`;
            
            document.getElementById('slider').value = 0;
            updateLabel();
        }}

        function updateLabel() {{
            const val = parseInt(document.getElementById('slider').value);
            const disp = document.getElementById('val-display');
            const p = pairs[pairIdx];
            
            if(val == 0) {{ disp.innerText = "동등함 (1:1)"; disp.style.color = "#555"; }}
            else if(val < 0) {{ 
                disp.innerText = p.a + " " + (Math.abs(val)+1) + "배 중요"; 
                disp.style.color = "#228be6";
            }} else {{ 
                disp.innerText = p.b + " " + (val+1) + "배 중요"; 
                disp.style.color = "#fa5252";
            }}
        }}

        // [동료의 CR 로직]
        function checkConsistency() {{
            const sliderVal = parseInt(document.getElementById('slider').value);
            let weight = sliderVal === 0 ? 1 : (sliderVal < 0 ? Math.abs(sliderVal) + 1 : 1 / (sliderVal + 1));
            
            const p = pairs[pairIdx];
            const n = items.length;
            let conflict = false;
            let logicalW = 0;

            for(let k=0; k<n; k++) {{
                if(k === p.r || k === p.c) continue;
                if(matrix[p.r][k] !== 0 && matrix[k][p.c] !== 0) {{
                    const predicted = matrix[p.r][k] * matrix[k][p.c];
                    const ratio = predicted > weight ? predicted / weight : weight / predicted;
                    if(ratio > 3.0) {{ conflict = true; logicalW = predicted; break; }}
                }}
            }}

            if(conflict) {{
                showModal(logicalW, weight);
                pendingVal = weight;
            }} else {{
                saveAnswer(weight);
            }}
        }}

        function showModal(logW, usrW) {{
            const fmt = (w) => w >= 1 ? "왼쪽 " + w.toFixed(1) + "배" : "오른쪽 " + (1/w).toFixed(1) + "배";
            document.getElementById('rec-val').innerText = fmt(logW);
            document.getElementById('my-val').innerText = fmt(usrW);
            document.getElementById('modal').style.display = 'flex';
        }}

        function closeModal(confirm) {{
            document.getElementById('modal').style.display = 'none';
            if(confirm) saveAnswer(pendingVal);
        }}

        function saveAnswer(w) {{
            const p = pairs[pairIdx];
            matrix[p.r][p.c] = w;
            matrix[p.c][p.r] = 1 / w;
            
            const taskName = tasks[currentTaskIdx].name;
            const sliderV = document.getElementById('slider').value;
            allAnswers[`[${{taskName}}] ${{p.a}} vs ${{p.b}}`] = sliderV;
            
            pairIdx++;
            renderPair();
        }}

        function finishAll() {{
            showStep('step-finish');
            document.getElementById('result-code').value = JSON.stringify(allAnswers);
        }}

        function showStep(id) {{
            document.querySelectorAll('.step').forEach(e => e.classList.remove('active'));
            document.getElementById(id).classList.add('active');
        }}

        loadTask(); // 시작
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
                # 데이터 저장 로직: Goal을 기준으로 파일명 생성
                goal_filename = survey_data['goal'].replace(" ", "_")
                
                # 폴더가 없으면 생성
                if not os.path.exists("survey_data"):
                    os.makedirs("survey_data")
                
                file_path = f"survey_data/{goal_filename}.csv"
                
                save_data = {
                    "Time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Respondent": respondent,
                    "Raw_Data": code
                }
                df = pd.DataFrame([save_data])
                
                try: old_df = pd.read_csv(file_path)
                except: old_df = pd.DataFrame()
                
                pd.concat([old_df, df], ignore_index=True).to_csv(file_path, index=False)
                st.success(f"✅ '{survey_data['goal']}' 프로젝트 데이터 센터에 저장되었습니다!")
            except Exception as e:
                st.error(f"오류 발생: {e}")
