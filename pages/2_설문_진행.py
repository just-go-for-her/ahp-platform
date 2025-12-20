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
    with st.container(border=True):
        st.subheader("🔐 보안 설정 (관리자용)")
        project_key = st.text_input("프로젝트 비밀번호(Key) 설정", type="password")
    if st.button("🔗 공유 링크 생성하기", type="primary", use_container_width=True):
        if not project_key: st.error("비밀번호를 설정해주세요.")
        else:
            full_structure = {**survey_data, "secret_key": project_key}
            survey_id = uuid.uuid4().hex[:8]
            with open(os.path.join(CONFIG_DIR, f"{survey_id}.json"), "w", encoding="utf-8") as f:
                json.dump(full_structure, f, ensure_ascii=False, indent=2)
            st.code(f"{FULL_URL}?id={survey_id}")
            st.success("링크가 생성되었습니다. 복사하여 사용하세요.")

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
        
        .ranking-board {{ background: #f1f3f5; padding: 18px; border-radius: 12px; margin-bottom: 25px; border: 1px solid #dee2e6; }}
        .board-title {{ font-weight: bold; color: #495057; font-size: 0.9em; margin-bottom: 15px; display: flex; justify-content: space-between; }}
        .board-grid {{ display: flex; gap: 10px; overflow-x: auto; padding-bottom: 5px; }}
        .board-item {{ min-width: 135px; background: white; padding: 12px; border-radius: 10px; text-align: center; border: 1px solid #dee2e6; flex: 1; }}
        
        .rank-label {{ font-size: 0.75em; color: #868e96; }}
        .rank-value {{ font-weight: bold; font-size: 0.9em; display: block; margin-top: 2px; }}
        .mismatch {{ color: #fa5252 !important; font-weight: 800; }}

        .card {{ background: #fff; padding: 30px; border-radius: 15px; text-align: center; margin-bottom: 20px; border: 1px solid #e9ecef; }}
        
        input[type=range] {{
            -webkit-appearance: none; width: 100%; height: 12px; background: #dee2e6;
            border-radius: 6px; outline: none; margin: 35px 0;
        }}
        input[type=range]::-webkit-slider-thumb {{
            -webkit-appearance: none; appearance: none; width: 26px; height: 26px;
            background: #228be6; border: 4px solid white; border-radius: 50%;
            cursor: pointer; box-shadow: 0 2px 6px rgba(0,0,0,0.2); position: relative; z-index: 5;
        }}

        .button-group {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }}
        .btn {{ width: 100%; padding: 14px; background: #228be6; color: white; border: none; border-radius: 10px; font-size: 1em; font-weight: bold; cursor: pointer; }}
        .btn-secondary {{ background: #adb5bd; }}

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
                <span id="logic-status">상태 체크 중</span>
            </div>
            <div id="board-grid" class="board-grid"></div>
        </div>

        <div id="step-ranking" class="step">
            <p><b>1단계:</b> 각 항목의 <b>기대 순위</b>를 정해주세요.</p>
            <div id="ranking-list" style="margin-bottom:20px;"></div>
            <button class="btn" style="width:100%;" onclick="startCompare()">설문 시작하기</button>
        </div>

        <div id="step-compare" class="step">
            <div class="card">
                <div style="display:flex; justify-content:space-between; font-weight:bold; font-size:1.3em; margin-bottom:20px;">
                    <span id="item-a" style="color:#228be6;">A</span>
                    <span style="color:#dee2e6;">VS</span>
                    <span id="item-b" style="color:#fa5252;">B</span>
                </div>
                <div style="font-size:0.85em; color:#adb5bd; margin-bottom:10px;">
                    (기대 <span id="hint-a"></span>위) vs (기대 <span id="hint-b"></span>위)
                </div>
                <input type="range" id="slider" min="-4" max="4" value="0" step="1" oninput="updateUI()">
                <div id="val-display" style="font-weight:bold; color:#495057; font-size:1.3em;">동등함</div>
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
            <h3 style="color:#fa5252; margin-top:0;">⚠️ 순위가 뒤바뀌었습니다</h3>
            <p style="font-size:0.95em; color:#495057; line-height:1.6; margin-bottom:25px;">
                현재 응답을 적용하면 처음에 정한 순위와 달라집니다.<br><b>바뀐 생각을 반영</b>하시겠습니까, 아니면 <b>응답을 수정</b>하시겠습니까?
            </p>
            <div style="display:grid; gap:12px;">
                <button class="btn" onclick="closeModal('resurvey')" style="background:#228be6;">👈 현재 응답 수정 (원래 생각대로)</button>
                <button class="btn" onclick="closeModal('updaterank')" style="background:#868e96;">✅ 순위 변경 인정 (바뀐 생각 반영)</button>
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
                if(!el.value) {{ alert("순위를 모두 정해주세요."); return; }}
                initialRanks[i] = parseInt(el.value);
                tempIdxMap.push({{ name: items[i], rank: initialRanks[i], originIdx: i }});
            }}
            if(new Set(initialRanks).size !== initialRanks.length) {{ alert("중복 순위가 있습니다."); return; }}
            
            generatePairs(tempIdxMap);
            const n = items.length; matrix = Array.from({{length: n}}, () => Array(n).fill(0));
            for(let i=0; i<n; i++) matrix[i][i] = 1;
            pairIdx = 0; showStep('step-compare'); renderPair();
        }}

        function generatePairs(tempIdxMap) {{
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
        }}

        function renderPair() {{
            const p = pairs[pairIdx];
            document.getElementById('item-a').innerText = p.a; 
            document.getElementById('item-b').innerText = p.b;
            document.getElementById('hint-a').innerText = initialRanks[p.r];
            document.getElementById('hint-b').innerText = initialRanks[p.c];
            document.getElementById('slider').value = 0;
            document.getElementById('back-btn').style.visibility = (pairIdx === 0) ? 'hidden' : 'visible';
            document.getElementById('live-board').style.display = 'block';
            updateUI();
        }}

        function updateUI() {{
            const slider = document.getElementById('slider');
            const val = parseInt(slider.value);
            const p = pairs[pairIdx]; const disp = document.getElementById('val-display');
            
            let perc = (val + 4) * 12.5;
            if(val < 0) slider.style.background = `linear-gradient(to right, #dee2e6 0%, #dee2e6 ${{perc}}%, #228be6 ${{perc}}%, #228be6 50%, #dee2e6 50%, #dee2e6 100%)`;
            else if(val > 0) slider.style.background = `linear-gradient(to right, #dee2e6 0%, #dee2e6 50%, #228be6 50%, #228be6 ${{perc}}%, #dee2e6 ${{perc}}%, #dee2e6 100%)`;
            else slider.style.background = '#dee2e6';

            if(val == 0) disp.innerText = "동등함 (1:1)";
            else if(val < 0) disp.innerText = `${{p.a}} ${{Math.abs(val)+1}}배 중요`;
            else disp.innerText = `${{p.b}} ${{val+1}}배 중요`;
            updateBoard();
        }}

        function updateBoard() {{
            const grid = document.getElementById('board-grid'); grid.innerHTML = "";
            const status = document.getElementById('logic-status');
            
            if (pairIdx === 0) {{
                status.innerText = "✅ 기준 설정 중"; status.style.color = "#2f9e44";
                let sortedInitial = items.map((name, i) => ({{name, rank: initialRanks[i]}})).sort((a,b) => a.rank - b.rank);
                sortedInitial.forEach(item => {{
                    grid.innerHTML += `<div class="board-item"><b>${{item.name}}</b><br><span class="rank-label">기대: ${{item.rank}}위</span></div>`;
                }});
                return;
            }}

            let weights = calculateWeights();
            let sortedIdx = weights.map((w, i) => i).sort((a, b) => weights[b] - weights[a]);
            
            sortedIdx.forEach((idx, i) => {{
                const match = (i+1) === initialRanks[idx];
                grid.innerHTML += `<div class="board-item" style="border-color:${{match?'#dee2e6':'#fa5252'}}">
                    <b>${{items[idx]}}</b><span class="rank-label">기대: ${{initialRanks[idx]}}위</span>
                    <span class="rank-value ${{match?'':'mismatch'}}">현재: ${{i+1}}위</span></div>`;
            }});
            
            let isAnyMismatch = items.some((_, idx) => (sortedIdx.indexOf(idx) + 1) !== initialRanks[idx]);
            status.innerText = isAnyMismatch ? "⚠️ 순위 변동 위험" : "✅ 논리 일치";
            status.style.color = isAnyMismatch ? "#fa5252" : "#2f9e44";
        }}

        function calculateWeights() {{
            const n = items.length; let tempMatrix = matrix.map(row => [...row]);
            const val = parseInt(document.getElementById('slider').value);
            const p = pairs[pairIdx]; 
            const w = val === 0 ? 1 : (val < 0 ? Math.abs(val)+1 : 1/(val+1));
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
                // 1. 현재 가중치 기준으로 신규 순위 데이터(initialRanks) 업데이트
                let weights = calculateWeights();
                let sortedIdx = weights.map((w, i) => i).sort((a, b) => weights[b] - weights[a]);
                sortedIdx.forEach((idx, i) => {{ initialRanks[idx] = i + 1; }});
                
                // 2. [핵심] 남은 모든 설문 질문의 좌우 위치를 새로운 순위에 맞춰 재정렬
                // 항상 "높은 순위(작은 숫자)가 왼쪽(a)"에 오도록 pairs 배열 수정
                for (let k = pairIdx; k < pairs.length; k++) {{
                    let p = pairs[k];
                    if (initialRanks[p.r] > initialRanks[p.c]) {{
                        // 순위가 뒤바뀌어 있으면 r-c와 a-b를 서로 맞바꿈
                        let tempR = p.r; pairs[k].r = p.c; pairs[k].c = tempR;
                        let tempA = p.a; pairs[k].a = p.b; pairs[k].b = tempA;
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
            const w = val === 0 ? 1 : (val < 0 ? Math.abs(val)+1 : 1/(val+1));
            const p = pairs[pairIdx];
            matrix[p.r][p.c] = w; matrix[p.c][p.r] = 1/w;
            let logVal = w >= 1 ? w : -1*(1/w);
            allAnswers[`[${{tasks[currentTaskIdx].name}}] ${{p.a}} vs ${{p.b}}`] = logVal.toFixed(2);
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
        st.write("📋 **최종 데이터 제출**")
        respondent = st.text_input("응답자 성함")
        code = st.text_area("결과 코드를 붙여넣으세요")
        if st.form_submit_button("최종 제출하기", type="primary", use_container_width=True):
            if respondent and code:
                try:
                    json.loads(code)
                    goal_clean = survey_data["goal"].replace(" ", "_")
                    secret_key = survey_data.get("secret_key", "public")
                    if not os.path.exists("survey_data"): os.makedirs("survey_data")
                    file_path = f"survey_data/{{secret_key}}_{{goal_clean}}.csv"
                    save_data = {{ "Time": datetime.now().strftime("%Y-%m-%d %H:%M"), "Respondent": respondent, "Raw_Data": code }}
                    df = pd.DataFrame([save_data]); try: old_df = pd.read_csv(file_path); except: old_df = pd.DataFrame()
                    pd.concat([old_df, df], ignore_index=True).to_csv(file_path, index=False)
                    st.success("✅ 제출되었습니다!"); st.balloons()
                except: st.error("코드가 올바르지 않습니다.")
