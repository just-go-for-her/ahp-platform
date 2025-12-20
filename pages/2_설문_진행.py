import streamlit as st
import streamlit.components.v1 as components
import json
import pandas as pd
from datetime import datetime
import os
import uuid 

# ==============================================================================
# [설정] 본인의 실제 배포 주소 입력
# ==============================================================================
FULL_URL = "https://ahp-platform-bbee45epwqjjy2zfpccz7p.streamlit.app/%EC%84%A4%EB%AC%B8_%EC%A7%84%ED%96%89"
# ==============================================================================

CONFIG_DIR = "survey_config"
os.makedirs(CONFIG_DIR, exist_ok=True)

st.set_page_config(page_title="설문 진행", page_icon="📝", layout="wide")

query_params = st.query_params
raw_id = query_params.get("id", None)
if isinstance(raw_id, list): survey_id = raw_id[0] if raw_id else None
else: survey_id = raw_id

survey_data = None

if survey_id:
    config_path = os.path.join(CONFIG_DIR, f"{survey_id}.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            survey_data = json.load(f)
        is_respondent = True
    else:
        st.error("유효하지 않은 링크입니다."); st.stop()
else:
    is_respondent = False
    survey_data = st.session_state.get("passed_structure", None)

if not is_respondent:
    st.title("📢 설문 배포 센터")
    if not survey_data:
        st.warning("⚠️ [1번 페이지]에서 구조를 먼저 확정하세요."); st.stop()
    project_key = st.text_input("프로젝트 비밀번호(Key) 설정", type="password")
    if st.button("🔗 공유 링크 생성하기", type="primary", use_container_width=True):
        if not project_key: st.error("비밀번호 설정 필요")
        else:
            full_structure = {**survey_data, "secret_key": project_key}
            survey_id = uuid.uuid4().hex[:8]
            with open(os.path.join(CONFIG_DIR, f"{survey_id}.json"), "w", encoding="utf-8") as f:
                json.dump(full_structure, f, ensure_ascii=False, indent=2)
            st.code(f"{FULL_URL}?id={survey_id}")
            st.success("링크 생성 완료!")

else:
    st.title(f"📝 {survey_data['goal']}")
    tasks = []
    if len(survey_data["main_criteria"]) > 1:
        tasks.append({"name": "📂 1. 평가 기준 중요도 비교", "items": survey_data["main_criteria"]})
    for cat, items in survey_data["sub_criteria"].items():
        if len(items) > 1:
            tasks.append({"name": f"📂 2. [{cat}] 세부 항목 평가", "items": items})

    js_tasks = json.dumps(tasks, ensure_ascii=False)

    html_code = f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: "Pretendard", sans-serif; padding: 10px; background: #f8f9fa; }}
        .container {{ max-width: 700px; margin: 0 auto; background: white; padding: 25px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }}
        .step {{ display: none; }} .active {{ display: block; }}
        
        /* 실시간 랭킹 보드 레이아웃 */
        .ranking-board {{ background: #f1f3f5; padding: 18px; border-radius: 12px; margin-bottom: 25px; border: 1px solid #dee2e6; }}
        .board-title {{ font-weight: bold; color: #495057; font-size: 0.9em; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; }}
        .status-pill {{ padding: 4px 12px; border-radius: 20px; font-size: 0.82em; font-weight: bold; }}
        
        .board-grid {{ display: flex; gap: 10px; overflow-x: auto; padding-bottom: 8px; }}
        .board-item {{ min-width: 150px; background: white; padding: 15px; border-radius: 12px; text-align: center; border: 1px solid #dee2e6; flex: 1; display: flex; flex-direction: column; gap: 6px; }}
        
        .item-name {{ font-weight: 800; color: #343a40; border-bottom: 1px solid #f1f3f5; padding-bottom: 6px; margin-bottom: 2px; }}
        .rank-row {{ display: flex; justify-content: space-between; align-items: center; font-size: 0.85em; color: #666; padding: 0 4px; }}
        .rank-val {{ font-weight: bold; color: #333; }}
        /* 순위 변동(오류) 발생 시 강조 색상 */
        .error-color {{ color: #fa5252 !important; text-decoration: underline; font-weight: 800; }}
        .match-color {{ color: #228be6; }}

        .card {{ background: #fff; padding: 30px; border-radius: 15px; text-align: center; margin-bottom: 20px; border: 1px solid #e9ecef; box-shadow: 0 4px 12px rgba(0,0,0,0.03); }}
        input[type=range] {{ -webkit-appearance: none; width: 100%; height: 12px; background: #dee2e6; border-radius: 6px; outline: none; margin: 35px 0; }}
        input[type=range]::-webkit-slider-thumb {{ -webkit-appearance: none; appearance: none; width: 28px; height: 28px; background: #228be6; border: 4px solid white; border-radius: 50%; cursor: pointer; box-shadow: 0 2px 6px rgba(0,0,0,0.2); position: relative; z-index: 5; }}

        .button-group {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }}
        .btn {{ width: 100%; padding: 15px; background: #228be6; color: white; border: none; border-radius: 10px; font-size: 1.1em; font-weight: bold; cursor: pointer; }}
        .btn-secondary {{ background: #adb5bd; }}
        .btn-hidden {{ visibility: hidden; }}

        .modal {{ display: none; position: fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7); justify-content:center; align-items:center; z-index:9999; }}
        .modal-box {{ background:white; padding:35px; border-radius:20px; width:90%; max-width:450px; text-align:center; }}
    </style>
    </head>
    <body>
    <div class="container">
        <h3 id="task-title" style="margin-top:0; color:#212529;"></h3>

        <div id="live-board" class="ranking-board" style="display:none;">
            <div class="board-title">
                <span>📊 실시간 순위 현황 (1등 → N등)</span>
                <span id="status-pill" class="status-pill">체크 중</span>
            </div>
            <div id="board-grid" class="board-grid"></div>
        </div>

        <div id="step-ranking" class="step">
            <p><b>1단계:</b> 각 항목의 중요도 순위를 먼저 정해주세요.</p>
            <div id="ranking-list" style="margin-bottom:20px;"></div>
            <button class="btn" onclick="startCompare()">설문 시작하기</button>
        </div>

        <div id="step-compare" class="step">
            <div class="card">
                <div style="display:flex; justify-content:space-between; font-weight:bold; font-size:1.4em; margin-bottom:20px;">
                    <span id="item-a" style="color:#228be6;">A</span>
                    <span style="color:#dee2e6;">VS</span>
                    <span id="item-b" style="color:#fa5252;">B</span>
                </div>
                <div style="font-size:0.95em; color:#adb5bd; margin-bottom:10px;">
                    (기존: <span id="hint-a"></span>위) vs (기존: <span id="hint-b"></span>위)
                </div>
                <input type="range" id="slider" min="-4" max="4" value="0" step="1" oninput="updateUI()">
                <div id="val-display" style="font-weight:bold; color:#343a40; font-size:1.4em;">동등함</div>
            </div>
            
            <div class="button-group">
                <button class="btn btn-secondary" onclick="goBack()" id="back-btn">이전 질문</button>
                <button class="btn" onclick="checkLogic()" id="next-btn">다음 질문</button>
            </div>
        </div>

        <div id="step-finish" class="step">
            <div style="text-align:center; padding:40px 0;">
                <h2>✅ 모든 설문 완료</h2>
                <textarea id="result-code" readonly style="width:100%; height:150px; padding:15px; border-radius:12px; border:1px solid #dee2e6; background:#f8f9fa; font-family:monospace;"></textarea>
            </div>
        </div>
    </div>

    <div id="modal" class="modal">
        <div class="modal-box">
            <h3 style="color:#fa5252; margin-top:0;">⚠️ 순위 변동 위험 감지</h3>
            <p style="font-size:0.95em; color:#495057; line-height:1.7; margin-bottom:25px;">
                현재 응답을 적용하면 <b>이전 답변들과의 관계</b> 때문에<br>처음에 설정한 순위가 뒤바뀌게 됩니다.
            </p>
            <div style="display:grid; gap:12px;">
                <button class="btn" onclick="closeModal('resurvey')" style="background:#228be6;">👈 현재 답변 수정 (기존 순위 유지)</button>
                <button class="btn" onclick="closeModal('updaterank')" style="background:#868e96;">✅ 순위 변경 인정 (변동 순위 반영)</button>
            </div>
        </div>
    </div>

    <script>
        const tasks = {js_tasks};
        let currentTaskIdx = 0, items = [], pairs = [], matrix = [], pairIdx = 0, initialRanks = [];
        let allAnswers = {{}};

        function loadTask() {{
            if (currentTaskIdx >= tasks.length) {{ finishAll(); return; }}
            const task = tasks[currentTaskIdx]; items = task.items;
            document.getElementById('task-title').innerText = task.name;
            const listDiv = document.getElementById('ranking-list'); listDiv.innerHTML = "";
            let options = '<option value="" selected disabled>선택</option>';
            for(let i=1; i<=items.length; i++) options += `<option value="${{i}}">${{i}}위</option>`;
            items.forEach((item, idx) => {{
                listDiv.innerHTML += `<div style="display:flex; justify-content:space-between; padding:14px; background:#f8f9fa; border-radius:10px; margin-bottom:10px; align-items:center; border:1px solid #eee;">
                    <span style="font-weight:bold;">${{item}}</span><select id="rank-${{idx}}">${{options}}</select></div>`;
            }});
            showStep('step-ranking'); document.getElementById('live-board').style.display = 'none';
        }}

        function startCompare() {{
            initialRanks = []; let tempIdxMap = [];
            for(let i=0; i<items.length; i++) {{
                const el = document.getElementById('rank-'+i);
                if(!el.value) {{ alert("순위를 정해주세요."); return; }}
                initialRanks[i] = parseInt(el.value);
                tempIdxMap.push({{ name: items[i], rank: initialRanks[i], originIdx: i }});
            }}
            if(new Set(initialRanks).size !== initialRanks.length) {{ alert("중복 순위가 있습니다."); return; }}
            
            tempIdxMap.sort((a, b) => a.rank - b.rank);
            pairs = [];
            for(let i=0; i<tempIdxMap.length; i++) {{
                for(let j=i+1; j<tempIdxMap.length; j++) {{
                    pairs.push({{ 
                        r: tempIdxMap[i].originIdx, c: tempIdxMap[j].originIdx, 
                        a: tempIdxMap[i].name, b: tempIdxMap[j].name 
                    }});
                }}
            }}
            const n = items.length; matrix = Array.from({{length: n}}, () => Array(n).fill(0));
            for(let i=0; i<n; i++) matrix[i][i] = 1;
            pairIdx = 0; showStep('step-compare'); renderPair();
        }}

        function renderPair() {{
            const p = pairs[pairIdx];
            document.getElementById('item-a').innerText = p.a; 
            document.getElementById('item-b').innerText = p.b;
            document.getElementById('hint-a').innerText = initialRanks[p.r];
            document.getElementById('hint-b').innerText = initialRanks[p.c];
            document.getElementById('slider').value = 0;
            document.getElementById('back-btn').className = (pairIdx === 0) ? 'btn btn-secondary btn-hidden' : 'btn btn-secondary';
            document.getElementById('live-board').style.display = 'block';
            updateUI();
        }}

        function updateUI() {{
            const slider = document.getElementById('slider');
            let val = parseInt(slider.value);
            const p = pairs[pairIdx];

            // [조작 실수 차단 로직]
            if (val > 0) {{
                alert(`⚠️ 안내: 현재 [${{p.a}}] 항목이 상위 순위로 설정되어 있습니다.\\n논리적 일관성을 위해 왼쪽 방향으로만 가중치를 선택해 주세요.`);
                slider.value = 0; val = 0;
            }}

            const disp = document.getElementById('val-display');
            let perc = (val + 4) * 12.5;
            if(val < 0) slider.style.background = `linear-gradient(to right, #dee2e6 0%, #dee2e6 ${{perc}}%, #228be6 ${{perc}}%, #228be6 50%, #dee2e6 50%, #dee2e6 100%)`;
            else slider.style.background = '#dee2e6';

            if(val == 0) disp.innerText = "동등함 (1:1)";
            else disp.innerText = `${{p.a}} ${{Math.abs(val)+1}}배 중요`;
            updateBoard();
        }}

        function updateBoard() {{
            const grid = document.getElementById('board-grid'); grid.innerHTML = "";
            const pill = document.getElementById('status-pill');
            
            if (pairIdx === 0) {{
                pill.innerText = "✅ 논리 일치"; pill.style.background = "#ebfbee"; pill.style.color = "#2f9e44";
                let sortedItems = items.map((name, i) => ({{name, rank: initialRanks[i]}})).sort((a,b) => a.rank - b.rank);
                sortedItems.forEach(item => {{
                    grid.innerHTML += `<div class="board-item">
                        <span class="item-name">${{item.name}}</span>
                        <div class="rank-row"><span>기존 순위:</span><span class="rank-val">${{item.rank}}위</span></div>
                    </div>`;
                }});
                return;
            }}

            let weights = calculateWeights();
            let sortedIdx = weights.map((w, i) => i).sort((a, b) => weights[b] - weights[a]);
            
            let mismatchFound = false;
            sortedIdx.forEach((idx, i) => {{
                const curRank = i + 1;
                const orgRank = initialRanks[idx];
                const isMatch = curRank === orgRank;
                if(!isMatch) mismatchFound = true;
                
                grid.innerHTML += `<div class="board-item" style="border-color:${{isMatch?'#dee2e6':'#fa5252'}}">
                    <span class="item-name">${{items[idx]}}</span>
                    <div class="rank-row">
                        <span>기존 순위:</span><span class="rank-val">${{orgRank}}위</span>
                    </div>
                    <div class="rank-row">
                        <span>변동 순위:</span><span class="rank-val ${{isMatch?'match-color':'error-color'}}">${{curRank}}위</span>
                    </div>
                </div>`;
            }});

            if(mismatchFound) {{
                pill.innerText = "⚠️ 순위 변동 위험"; pill.style.background = "#fff5f5"; pill.style.color = "#fa5252";
            }} else {{
                pill.innerText = "✅ 논리 일치"; pill.style.background = "#ebfbee"; pill.style.color = "#2f9e44";
            }}
        }}

        function calculateWeights() {{
            const n = items.length; let tempMatrix = matrix.map(row => [...row]);
            const val = parseInt(document.getElementById('slider').value);
            const p = pairs[pairIdx]; const w = val === 0 ? 1 : (Math.abs(val)+1);
            tempMatrix[p.r][p.c] = w; tempMatrix[p.c][p.r] = 1/w;
            for(let i=0; i<n; i++) {{ for(let j=0; j<n; j++) {{ if(tempMatrix[i][j] === 0) tempMatrix[i][j] = 1; }} }}
            let weights = tempMatrix.map(row => Math.pow(row.reduce((a, b) => a * b, 1), 1/n));
            let sum = weights.reduce((a, b) => a + b, 0);
            return weights.map(v => v / sum);
        }}

        function checkLogic() {{
            if (pairIdx === 0) {{ saveAndNext(); return; }}
            let weights = calculateWeights();
            let sortedIdx = weights.map((w, i) => i).sort((a, b) => weights[b] - weights[a]);
            let mismatch = items.some((_, i) => (sortedIdx.indexOf(i) + 1) !== initialRanks[i]);
            if (mismatch) {{ document.getElementById('modal').style.display = 'flex'; return; }}
            saveAndNext();
        }}

        function closeModal(action) {{
            document.getElementById('modal').style.display = 'none';
            if(action === 'updaterank') {{
                let weights = calculateWeights();
                let sortedIdx = weights.map((w, i) => i).sort((a, b) => weights[b] - weights[a]);
                sortedIdx.forEach((idx, i) => {{ initialRanks[idx] = i + 1; }});
                // 남은 질문 좌우 자동 정렬
                for (let k = pairIdx; k < pairs.length; k++) {{
                    let p = pairs[k];
                    if (initialRanks[p.r] > initialRanks[p.c]) {{
                        let tr = p.r; pairs[k].r = p.c; pairs[k].c = tr;
                        let ta = p.a; pairs[k].a = p.b; pairs[k].b = ta;
                    }}
                }}
                saveAndNext();
            }} else {{
                document.getElementById('slider').value = 0; updateUI();
            }}
        }}

        function goBack() {{ if (pairIdx > 0) {{ pairIdx--; renderPair(); }} }}

        function saveAndNext() {{
            const val = parseInt(document.getElementById('slider').value);
            const w = val === 0 ? 1 : (Math.abs(val)+1);
            const p = pairs[pairIdx];
            matrix[p.r][p.c] = w; matrix[p.c][p.r] = 1/w;
            allAnswers[`[${{tasks[currentTaskIdx].name}}] ${{p.a}} vs ${{p.b}}`] = w.toFixed(2);
            pairIdx++;
            if (pairIdx >= pairs.length) {{ currentTaskIdx++; loadTask(); }}
            else {{ renderPair(); }}
        }}

        function finishAll() {{
            showStep('step-finish'); document.getElementById('live-board').style.display = 'none';
            document.getElementById('result-code').value = JSON.stringify(allAnswers, null, 2);
        }}

        function showStep(id) {{ document.querySelectorAll('.step').forEach(e => e.classList.remove('active')); document.getElementById(id).classList.add('active'); }}
        loadTask();
    </script>
    </body>
    </html>
    """
    components.html(html_code, height=850, scrolling=True)

    st.divider()
    with st.form("save"):
        respondent = st.text_input("응답자 성함")
        code = st.text_area("결과 코드 붙여넣기")
        if st.form_submit_button("최종 제출"):
            if respondent and code:
                try:
                    json.loads(code)
                    goal_clean = survey_data["goal"].replace(" ", "_")
                    secret_key = survey_data.get("secret_key", "public")
                    if not os.path.exists("survey_data"): os.makedirs("survey_data")
                    file_path = f"survey_data/{secret_key}_{goal_clean}.csv"
                    save_dict = {"Time": datetime.now().strftime("%Y-%m-%d %H:%M"), "Respondent": respondent, "Raw_Data": code}
                    df = pd.DataFrame([save_dict]); try: old_df = pd.read_csv(file_path); except: old_df = pd.DataFrame()
                    pd.concat([old_df, df], ignore_index=True).to_csv(file_path, index=False)
                    st.success("✅ 제출 성공!"); st.balloons()
                except: st.error("코드 오류")
