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
    st.title("📢 설문 배포 센터 (Private Mode)")
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
            final_url = f"{FULL_URL}?id={survey_id}"
            st.code(final_url)
            st.success("링크가 생성되었습니다. 위 주소를 복사하여 공유하세요.")

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
        .ranking-board {{ background: #e7f5ff; padding: 15px; border-radius: 10px; margin-bottom: 20px; border: 1px solid #a5d8ff; }}
        .board-title {{ font-weight: bold; color: #1971c2; font-size: 0.9em; margin-bottom: 8px; display: flex; justify-content: space-between; }}
        .board-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 10px; }}
        .board-item {{ background: white; padding: 8px; border-radius: 6px; text-align: center; font-size: 0.85em; border: 1px solid #dbeafe; }}
        .card {{ background: #f8f9fa; padding: 20px; border-radius: 12px; text-align: center; margin-bottom: 20px; border: 1px solid #eee; }}
        input[type=range] {{ width: 100%; margin: 20px 0; cursor: pointer; }}
        .btn {{ width: 100%; padding: 14px; background: #228be6; color: white; border: none; border-radius: 8px; font-size: 1em; cursor: pointer; margin-top:10px; }}
        .modal {{ display: none; position: fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7); justify-content:center; align-items:center; z-index:9999; }}
        .modal-box {{ background:white; padding:30px; border-radius:15px; width:85%; max-width:450px; text-align:center; box-shadow: 0 10px 25px rgba(0,0,0,0.2); }}
        .highlight {{ color: #228be6; font-weight: bold; }}
    </style>
    </head>
    <body>
    <div class="container">
        <h3 id="task-title" style="margin-top:0;"></h3>

        <div id="live-board" class="ranking-board" style="display:none;">
            <div class="board-title">
                <span>📊 나의 논리 일관성 체크</span>
                <span id="logic-status">✅ 순위 일치</span>
            </div>
            <div id="board-grid" class="board-grid"></div>
        </div>

        <div id="step-ranking" class="step">
            <p><b>1단계:</b> 비교를 시작하기 전, 항목들의 <b>예상 순위</b>를 정해주세요.</p>
            <div id="ranking-list" style="margin-bottom:20px;"></div>
            <button class="btn" style="width:100%;" onclick="startCompare()">비교 시작하기</button>
        </div>

        <div id="step-compare" class="step">
            <div class="card">
                <div style="display:flex; justify-content:space-between; font-weight:bold; font-size:1.1em; margin-bottom:15px;">
                    <span id="item-a" style="color:#228be6;">A</span>
                    <span style="color:#adb5bd;">VS</span>
                    <span id="item-b" style="color:#fa5252;">B</span>
                </div>
                <div style="font-size:0.85em; color:#868e96; margin-bottom:10px;">
                    <span id="rank-hint-a"></span> vs <span id="rank-hint-b"></span>
                </div>
                <input type="range" id="slider" min="-4" max="4" value="0" step="1" oninput="updateLabel()">
                <div id="val-display" style="font-weight:bold; color:#495057; font-size:1.1em;">동등함</div>
            </div>
            <button class="btn" style="width:100%;" onclick="checkLogic()">다음 질문으로</button>
        </div>

        <div id="step-finish" class="step">
            <h2>🎉 모든 설문이 완료되었습니다!</h2>
            <p>아래 생성된 코드를 복사하여 페이지 하단의 제출란에 붙여넣어주세요.</p>
            <textarea id="result-code" readonly style="width:100%; height:120px; padding:10px; border-radius:8px; border:1px solid #ddd; background:#f1f3f5; font-family:monospace;"></textarea>
        </div>
    </div>

    <div id="modal" class="modal">
        <div class="modal-box">
            <h3 style="color:#e03131; margin-top:0;">⚠️ 순위 논리 불일치 감지</h3>
            <p style="font-size:0.95em; color:#495057; line-height:1.6; text-align:left;">
                현재 선택하신 가중치를 적용하면 처음에 정하신 순위와 실제 결과가 달라집니다. (역전 발생)
            </p>
            <div style="background:#f1f3f5; padding:15px; border-radius:8px; margin:15px 0; font-size:0.9em; text-align:left;">
                <div style="margin-bottom:5px;">✅ <b>순위 유지 권장값:</b> <span id="rec-val" class="highlight"></span></div>
                <div style="color:#868e96; font-size:0.85em;">* 이 값을 참고하여 다시 선택하면 순위가 유지됩니다.</div>
            </div>
            <div style="display:flex; flex-direction:column; gap:10px;">
                <button class="btn" onclick="closeModal('resurvey')" style="background:#228be6;">📍 다시 설문하기 (권장)</button>
                <button class="btn" onclick="closeModal('updaterank')" style="background:#868e96;">🔄 순위 변경하기 (현재 응답 인정)</button>
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
                listDiv.innerHTML += `<div style="display:flex; justify-content:space-between; padding:12px; background:#f1f3f5; border-radius:8px; margin-bottom:8px; align-items:center;">
                    <span style="font-weight:bold;">${{item}}</span><select id="rank-${{idx}}" style="padding:6px; border-radius:4px; border:1px solid #ccc;">${{options}}</select></div>`;
            }});
            showStep('step-ranking'); document.getElementById('live-board').style.display = 'none';
        }}

        function startCompare() {{
            initialRanks = [];
            for(let i=0; i<items.length; i++) {{
                const v = document.getElementById('rank-'+i).value;
                if(!v) {{ alert("모든 항목의 예상 순위를 선택해주세요."); return; }}
                initialRanks.push(parseInt(v));
            }}
            if(new Set(initialRanks).size !== initialRanks.length) {{ alert("중복된 순위가 있습니다. 서로 다르게 지정해주세요."); return; }}
            const n = items.length; matrix = Array.from({{length: n}}, () => Array(n).fill(0));
            for(let i=0; i<n; i++) matrix[i][i] = 1;
            pairs = [];
            for(let i=0; i<n; i++) {{ for(let j=i+1; j<n; j++) {{ pairs.push({{ r: i, c: j, a: items[i], b: items[j] }}); }} }}
            pairIdx = 0; showStep('step-compare'); renderPair();
        }}

        function renderPair() {{
            if (pairIdx >= pairs.length) {{ currentTaskIdx++; loadTask(); return; }}
            const p = pairs[pairIdx];
            document.getElementById('item-a').innerText = p.a; document.getElementById('item-b').innerText = p.b;
            document.getElementById('rank-hint-a').innerText = `기대: ${{initialRanks[p.r]}}위`;
            document.getElementById('rank-hint-b').innerText = `기대: ${{initialRanks[p.c]}}위`;
            document.getElementById('slider').value = 0; updateLabel(); updateBoard();
            document.getElementById('live-board').style.display = 'block';
        }}

        function updateLabel() {{
            const val = parseInt(document.getElementById('slider').value);
            const p = pairs[pairIdx]; const disp = document.getElementById('val-display');
            if(val == 0) disp.innerText = "동등함 (1:1)";
            else if(val < 0) disp.innerText = `${{p.a}} ${{Math.abs(val)+1}}배 더 중요`;
            else disp.innerText = `${{p.b}} ${{val+1}}배 더 중요`;
            updateBoard();
        }}

        // 실시간 순위 보드 업데이트 (정교화된 로직)
        function updateBoard() {{
            const grid = document.getElementById('board-grid'); grid.innerHTML = "";
            let weights = calculateCurrentWeights();
            
            // 가중치에 따른 현재 순위 산정
            let sortedIdx = weights.map((w, i) => i).sort((a, b) => weights[b] - weights[a]);
            let currentRanks = new Array(items.length);
            sortedIdx.forEach((idx, i) => currentRanks[idx] = i + 1);

            let isMismatched = false;
            items.forEach((item, i) => {{
                const match = currentRanks[i] === initialRanks[i];
                if(!match) isMismatched = true;
                grid.innerHTML += `<div class="board-item" style="border: 1px solid ${{match?'#d3f9d8':'#ffc9c9'}}; background: ${{match?'white':'#fff5f5'}}">
                    <div style="font-weight:bold; color:#1971c2;">${{item}}</div>
                    <div style="font-size:0.75em; color:#868e96;">기대: ${{initialRanks[i]}}위</div>
                    <div style="font-size:0.85em; font-weight:bold; color:${{match?'#2f9e44':'#e03131'}};">현재: ${{currentRanks[i]}}위</div>
                </div>`;
            }});
            const status = document.getElementById('logic-status');
            status.innerText = isMismatched ? "⚠️ 순위 불일치 상태" : "✅ 순위 일치 상태";
            status.style.color = isMismatched ? "#e03131" : "#2f9e44";
        }}

        function calculateCurrentWeights() {{
            const n = items.length;
            let tempMatrix = matrix.map(row => [...row]);
            const val = parseInt(document.getElementById('slider').value);
            const p = pairs[pairIdx];
            const w = val === 0 ? 1 : (val < 0 ? Math.abs(val)+1 : 1/(val+1));
            tempMatrix[p.r][p.c] = w; tempMatrix[p.c][p.r] = 1/w;
            
            // 아직 비교하지 않은 칸은 '동등(1)'이 아니라 '기대 순위'를 반영한 근사값으로 채움 (오판단 방지)
            for(let i=0; i<n; i++) {{
                for(let j=0; j<n; j++) {{
                    if(tempMatrix[i][j] === 0) {{
                        // 기대 순위가 높을수록 가중치를 조금 더 줌 (임시)
                        tempMatrix[i][j] = initialRanks[i] < initialRanks[j] ? 1.1 : (initialRanks[i] > initialRanks[j] ? 0.9 : 1);
                    }}
                }}
            }}
            
            let weights = tempMatrix.map(row => Math.pow(row.reduce((a, b) => a * b, 1), 1/n));
            let sum = weights.reduce((a, b) => a + b, 0);
            return weights.map(v => v / sum);
        }}

        function checkLogic() {{
            const sliderVal = parseInt(document.getElementById('slider').value);
            const p = pairs[pairIdx];
            const rankA = initialRanks[p.r]; const rankB = initialRanks[p.c];
            
            // 단순 방향성 체크 (A가 1등인데 B를 선택한 경우 등)
            if ((rankA < rankB && sliderVal > 0) || (rankA > rankB && sliderVal < 0)) {{
                showModal(); return;
            }}
            saveAndNext();
        }}

        function showModal() {{
            const p = pairs[pairIdx];
            document.getElementById('rec-val').innerText = initialRanks[p.r] < initialRanks[p.c] ? `"${{p.a}}" 우세 (왼쪽)` : `"${{p.b}}" 우세 (오른쪽)`;
            document.getElementById('modal').style.display = 'flex';
        }}

        function closeModal(action) {{
            document.getElementById('modal').style.display = 'none';
            if(action === 'updaterank') {{
                // 응답자의 현재 판단을 존중하여 초기 순위 배열을 즉시 재배치
                let weights = calculateCurrentWeights();
                let sortedIdx = weights.map((w, i) => i).sort((a, b) => weights[b] - weights[a]);
                sortedIdx.forEach((idx, i) => initialRanks[idx] = i + 1);
                saveAndNext();
            }} else {{
                // 다시 설문하기: 슬라이더 0으로 리셋
                document.getElementById('slider').value = 0; updateLabel();
            }}
        }}

        function saveAndNext() {{
            const val = parseInt(document.getElementById('slider').value);
            const w = val === 0 ? 1 : (val < 0 ? Math.abs(val)+1 : 1/(val+1));
            const p = pairs[pairIdx];
            matrix[p.r][p.c] = w; matrix[p.c][p.r] = 1/w;
            allAnswers[`[${{tasks[currentTaskIdx].name}}] ${{p.a}} vs ${{p.b}}`] = (w >= 1 ? w : -1*(1/w)).toFixed(2);
            pairIdx++; renderPair();
        }}

        function finishAll() {{
            showStep('step-finish'); document.getElementById('live-board').style.display = 'none';
            document.getElementById('result-code').value = JSON.stringify(allAnswers);
        }}

        function showStep(id) {{
            document.querySelectorAll('.step').forEach(e => e.classList.remove('active'));
            document.getElementById(id).classList.add('active');
        }}
        loadTask();
    </script>
    </body>
    </html>
    """
    components.html(html_code, height=850, scrolling=True)

    st.divider()
    with st.form("save"):
        st.write("📋 **설문 제출란**")
        respondent = st.text_input("응답자 성함 (실명 입력)")
        code = st.text_area("결과 코드 붙여넣기 (위에서 복사한 내용)")
        if st.form_submit_button("최종 데이터 제출하기", type="primary", use_container_width=True):
            if not respondent or not code:
                st.warning("이름과 코드를 모두 입력해주세요.")
            else:
                try:
                    json.loads(code)
                    goal_clean = survey_data["goal"].replace(" ", "_")
                    secret_key = survey_data.get("secret_key", "public")
                    if not os.path.exists("survey_data"): os.makedirs("survey_data")
                    file_path = f"survey_data/{{secret_key}}_{{goal_clean}}.csv"
                    save_data = { "Time": datetime.now().strftime("%Y-%m-%d %H:%M"), "Respondent": respondent, "Raw_Data": code }
                    df = pd.DataFrame([save_data])
                    try: old_df = pd.read_csv(file_path)
                    except: old_df = pd.DataFrame()
                    pd.concat([old_df, df], ignore_index=True).to_csv(file_path, index=False)
                    st.success(f"✅ {{respondent}}님, 데이터가 성공적으로 저장되었습니다!")
                    st.balloons()
                except Exception as e: st.error(f"오류: 코드가 올바르지 않습니다.")
