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
        
        /* 이전 버전의 고퀄리티 랭킹 보드 스타일 */
        .ranking-board {{ background: #f1f3f5; padding: 18px; border-radius: 12px; margin-bottom: 25px; border: 1px solid #dee2e6; }}
        .board-title {{ font-weight: bold; color: #495057; font-size: 0.95em; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; }}
        .board-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 12px; }}
        .board-item {{ background: white; padding: 12px; border-radius: 10px; text-align: center; font-size: 0.85em; border: 1px solid #dee2e6; transition: all 0.3s; }}
        .rank-badge {{ display: inline-block; padding: 2px 10px; border-radius: 20px; font-weight: bold; margin-bottom: 6px; font-size: 0.8em; }}
        
        .card {{ background: #fff; padding: 30px; border-radius: 15px; text-align: center; margin-bottom: 20px; border: 1px solid #e9ecef; box-shadow: 0 4px 12px rgba(0,0,0,0.03); }}
        input[type=range] {{ width: 100%; margin: 30px 0; cursor: pointer; }}
        
        /* 버튼 시스템: 동일 크기 및 우측 배치 */
        .button-group {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }}
        .btn {{ width: 100%; padding: 14px; background: #228be6; color: white; border: none; border-radius: 10px; font-size: 1em; font-weight: bold; cursor: pointer; transition: background 0.2s; }}
        .btn:hover {{ background: #1c7ed6; }}
        .btn-secondary {{ background: #adb5bd; }}
        .btn-secondary:hover {{ background: #868e96; }}
        .btn-hidden {{ visibility: hidden; }}

        .modal {{ display: none; position: fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7); justify-content:center; align-items:center; z-index:9999; }}
        .modal-box {{ background:white; padding:30px; border-radius:20px; width:90%; max-width:450px; text-align:center; }}
        .highlight {{ color: #228be6; font-weight: bold; }}
    </style>
    </head>
    <body>
    <div class="container">
        <h3 id="task-title" style="margin-top:0; color:#212529; border-left: 5px solid #228be6; padding-left: 15px;"></h3>

        <div id="live-board" class="ranking-board" style="display:none;">
            <div class="board-title">
                <span>📊 실시간 순위 변동</span>
                <span id="logic-status" style="font-size:0.85em; padding:4px 10px; border-radius:5px;">분석 중...</span>
            </div>
            <div id="board-grid" class="board-grid"></div>
        </div>

        <div id="step-ranking" class="step">
            <p style="color:#495057;"><b>1단계:</b> 각 항목의 <b>기대 순위</b>를 정해주세요.</p>
            <div id="ranking-list" style="margin-bottom:20px;"></div>
            <button class="btn" onclick="startCompare()">설문 시작하기</button>
        </div>

        <div id="step-compare" class="step">
            <div class="card">
                <div style="display:flex; justify-content:space-between; font-weight:bold; font-size:1.3em; margin-bottom:25px;">
                    <span id="item-a" style="color:#228be6;">A</span>
                    <span style="color:#dee2e6; font-weight:300;">VS</span>
                    <span id="item-b" style="color:#fa5252;">B</span>
                </div>
                <div style="font-size:0.9em; color:#adb5bd; margin-bottom:10px;">
                    <span id="rank-hint-a"></span> vs <span id="rank-hint-b"></span>
                </div>
                <input type="range" id="slider" min="-4" max="4" value="0" step="1" oninput="updateUI()">
                <div id="val-display" style="font-weight:bold; color:#343a40; font-size:1.3em; background:#f8f9fa; display:inline-block; padding:8px 20px; border-radius:30px;">동등함</div>
            </div>
            
            <div class="button-group">
                <button class="btn btn-secondary" onclick="goBack()" id="back-btn">이전 질문</button>
                <button class="btn" onclick="checkLogic()" id="next-btn">다음 질문</button>
            </div>
        </div>

        <div id="step-finish" class="step">
            <div style="text-align:center; padding:40px 0;">
                <h2 style="color:#228be6;">✅ 설문 완료</h2>
                <p style="color:#868e96;">모든 비교가 끝났습니다. 아래 코드를 제출해주세요.</p>
                <textarea id="result-code" readonly style="width:100%; height:150px; padding:15px; border-radius:12px; border:1px solid #dee2e6; background:#f8f9fa; font-family:monospace; font-size:0.9em;"></textarea>
            </div>
        </div>
    </div>

    <div id="modal" class="modal">
        <div class="modal-box">
            <h3 style="color:#fa5252; margin-top:0;">⚠️ 논리 불일치 알림</h3>
            <p style="font-size:0.95em; color:#495057; line-height:1.6;">
                현재 응답은 초기에 설정한 <b>기대 순위와 모순</b>되거나,<br>이전 답변들과 비교했을 때 일관성이 낮습니다.
            </p>
            <div style="background:#f8f9fa; padding:15px; border-radius:12px; margin:20px 0; border:1px solid #eee;">
                <div style="font-size:0.9em; color:#868e96; margin-bottom:5px;">💡 시스템 추천 가중치</div>
                <div id="rec-val" class="highlight" style="font-size:1.1em;"></div>
            </div>
            <div style="display:grid; gap:12px;">
                <button class="btn" onclick="closeModal('resurvey')">현재 질문 수정 (슬라이더 조정)</button>
                <button class="btn" onclick="closeModal('updaterank')" style="background:#868e96;">기대 순위 변경 (현재 응답 인정)</button>
                <button class="btn" onclick="closeModal('back')" style="background:#adb5bd;">이전 질문으로 돌아가기</button>
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
                    <span style="font-weight:bold; color:#495057;">${{item}}</span><select id="rank-${{idx}}" style="padding:8px; border-radius:6px; border:1px solid #ced4da;">${{options}}</select></div>`;
            }});
            showStep('step-ranking'); document.getElementById('live-board').style.display = 'none';
        }}

        function startCompare() {{
            initialRanks = [];
            for(let i=0; i<items.length; i++) {{
                const v = document.getElementById('rank-'+i).value;
                if(!v) {{ alert("모든 항목의 순위를 정해주세요."); return; }}
                initialRanks.push(parseInt(v));
            }}
            if(new Set(initialRanks).size !== initialRanks.length) {{ alert("중복된 순위가 있습니다."); return; }}
            
            const n = items.length; matrix = Array.from({{length: n}}, () => Array(n).fill(0));
            for(let i=0; i<n; i++) matrix[i][i] = 1;
            
            pairs = [];
            for(let i=0; i<n; i++) {{
                for(let j=i+1; j<n; j++) {{ pairs.push({{ r: i, c: j, a: items[i], b: items[j] }}); }}
            }}
            pairIdx = 0; showStep('step-compare'); renderPair();
        }}

        function renderPair() {{
            const p = pairs[pairIdx];
            document.getElementById('item-a').innerText = p.a; 
            document.getElementById('item-b').innerText = p.b;
            document.getElementById('rank-hint-a').innerText = `기대 ${{initialRanks[p.r]}}위`;
            document.getElementById('rank-hint-b').innerText = `기대 ${{initialRanks[p.c]}}위`;
            document.getElementById('slider').value = 0;
            
            // 버튼 제어 (첫 질문이면 '이전 질문' 숨김)
            const backBtn = document.getElementById('back-btn');
            if(pairIdx === 0) backBtn.classList.add('btn-hidden');
            else backBtn.classList.remove('btn-hidden');
            
            document.getElementById('live-board').style.display = 'block';
            updateUI();
        }}

        function updateUI() {{
            const val = parseInt(document.getElementById('slider').value);
            const p = pairs[pairIdx]; const disp = document.getElementById('val-display');
            if(val == 0) disp.innerText = "동등함 (1:1)";
            else if(val < 0) disp.innerText = `${{p.a}} ${{Math.abs(val)+1}}배 중요`;
            else disp.innerText = `${{p.b}} ${{val+1}}배 중요`;
            updateBoard();
        }}

        function updateBoard() {{
            const grid = document.getElementById('board-grid'); grid.innerHTML = "";
            const status = document.getElementById('logic-status');
            
            let weights = calculateWeights();
            let sortedIdx = weights.map((w, i) => i).sort((a, b) => weights[b] - weights[a]);
            let currentRanks = new Array(items.length);
            sortedIdx.forEach((idx, i) => currentRanks[idx] = i + 1);

            let mismatchCount = 0;
            items.forEach((item, i) => {{
                const match = currentRanks[i] === initialRanks[i];
                if(!match) mismatchCount++;
                
                const badgeColor = match ? '#e7f5ff' : '#fff5f5';
                const textColor = match ? '#228be6' : '#fa5252';
                const borderColor = match ? '#a5d8ff' : '#ffc9c9';

                grid.innerHTML += `<div class="board-item" style="border-color: ${{borderColor}}; background: ${{match?'white':'#fffafb'}}">
                    <span class="rank-badge" style="background:${{badgeColor}}; color:${{textColor}};">현재 ${{currentRanks[i]}}위</span>
                    <div style="font-weight:bold; color:#495057;">${{item}}</div>
                    <div style="font-size:0.8em; color:#adb5bd; margin-top:4px;">기대: ${{initialRanks[i]}}위</div>
                </div>`;
            }});

            if(mismatchCount > 0) {{
                status.innerText = "⚠️ 순위 변동 발생";
                status.style.background = "#fff5f5"; status.style.color = "#fa5252";
            }} else {{
                status.innerText = "✅ 순위 유지 중";
                status.style.background = "#ebfbee"; status.style.color = "#2f9e44";
            }}
        }}

        function calculateWeights() {{
            const n = items.length; let tempMatrix = matrix.map(row => [...row]);
            const val = parseInt(document.getElementById('slider').value);
            const p = pairs[pairIdx]; 
            const w = val === 0 ? 1 : (val < 0 ? Math.abs(val)+1 : 1/(val+1));
            tempMatrix[p.r][p.c] = w; tempMatrix[p.c][p.r] = 1/w;
            
            for(let i=0; i<n; i++) {{ 
                for(let j=0; j<n; j++) {{ 
                    if(tempMatrix[i][j] === 0) {{
                        // 미응답 구간은 논리적 추론값 혹은 1로 채움
                        tempMatrix[i][j] = 1;
                    }}
                }} 
            }}
            let weights = tempMatrix.map(row => Math.pow(row.reduce((a, b) => a * b, 1), 1/n));
            let sum = weights.reduce((a, b) => a + b, 0);
            return weights.map(v => v / sum);
        }}

        function checkLogic() {{
            if (pairIdx === 0) {{ saveAndNext(); return; }}
            const sliderVal = parseInt(document.getElementById('slider').value);
            const p = pairs[pairIdx];
            
            // 1. 순위 역전 체크
            const rankA = initialRanks[p.r]; const rankB = initialRanks[p.c];
            const isReverse = (rankA < rankB && sliderVal > 0) || (rankA > rankB && sliderVal < 0);
            
            // 2. 기하평균 논리 체크
            let estimates = [];
            for(let k=0; k<items.length; k++) {{
                if(k === p.r || k === p.c) continue;
                if(matrix[p.r][k] !== 0 && matrix[k][p.c] !== 0) estimates.push(matrix[p.r][k] * matrix[k][p.c]);
            }}

            if (estimates.length > 0) {{
                let geoMean = Math.exp(estimates.reduce((acc, v) => acc + Math.log(v), 0) / estimates.length);
                const currentWeight = sliderVal === 0 ? 1 : (sliderVal < 0 ? Math.abs(sliderVal)+1 : 1/(sliderVal+1));
                const ratio = currentWeight > geoMean ? currentWeight/geoMean : geoMean/currentWeight;
                
                if (isReverse || ratio >= 2.0) {{
                    const fmt = (w) => (w >= 1.1) ? `"${{p.a}}"(이)가 약 ${{Math.round(w)}}배 중요` : (w <= 0.9) ? `"${{p.b}}"(이)가 약 ${{Math.round(1/w)}}배 중요` : "두 항목이 동등함";
                    document.getElementById('rec-val').innerText = fmt(geoMean);
                    document.getElementById('modal').style.display = 'flex';
                    return;
                }}
            }} else if (isReverse) {{
                document.getElementById('rec-val').innerText = rankA < rankB ? `"${{p.a}}" 우세 권장` : `"${{p.b}}" 우세 권장`;
                document.getElementById('modal').style.display = 'flex';
                return;
            }}
            
            saveAndNext();
        }}

        function closeModal(action) {{
            document.getElementById('modal').style.display = 'none';
            if(action === 'updaterank') {{
                let weights = calculateWeights();
                let sortedIdx = weights.map((w, i) => i).sort((a, b) => weights[b] - weights[a]);
                sortedIdx.forEach((idx, i) => initialRanks[idx] = i + 1);
                saveAndNext();
            }} else if(action === 'back') {{
                goBack();
            }}
        }}

        function goBack() {{
            if (pairIdx > 0) {{
                pairIdx--;
                renderPair();
            }}
        }}

        function saveAndNext() {{
            const val = parseInt(document.getElementById('slider').value);
            const w = val === 0 ? 1 : (val < 0 ? Math.abs(val)+1 : 1/(val+1));
            const p = pairs[pairIdx];
            matrix[p.r][p.c] = w; matrix[p.c][p.r] = 1/w;
            allAnswers[`[${{tasks[currentTaskIdx].name}}] ${{p.a}} vs ${{p.b}}`] = (w >= 1 ? w : -1*(1/w)).toFixed(2);
            
            pairIdx++;
            if (pairIdx >= pairs.length) {{
                currentTaskIdx++;
                loadTask();
            }} else {{
                renderPair();
            }}
        }}

        function finishAll() {{
            showStep('step-finish');
            document.getElementById('live-board').style.display = 'none';
            document.getElementById('result-code').value = JSON.stringify(allAnswers, null, 2);
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
        st.write("📋 **최종 데이터 제출**")
        respondent = st.text_input("응답자 성함")
        code = st.text_area("위에서 생성된 결과 코드를 복사해서 붙여넣으세요")
        if st.form_submit_button("설문 제출하기", type="primary", use_container_width=True):
            if respondent and code:
                try:
                    json.loads(code)
                    goal_clean = survey_data["goal"].replace(" ", "_")
                    secret_key = survey_data.get("secret_key", "public")
                    if not os.path.exists("survey_data"): os.makedirs("survey_data")
                    file_path = f"survey_data/{secret_key}_{goal_clean}.csv"
                    save_data = {"Time": datetime.now().strftime("%Y-%m-%d %H:%M"), "Respondent": respondent, "Raw_Data": code}
                    df = pd.DataFrame([save_data])
                    try: old_df = pd.read_csv(file_path)
                    except: old_df = pd.DataFrame()
                    pd.concat([old_df, df], ignore_index=True).to_csv(file_path, index=False)
                    st.success("✅ 소중한 응답이 성공적으로 기록되었습니다. 감사합니다!"); st.balloons()
                except: st.error("코드가 올바르지 않습니다. 위 박스의 내용을 그대로 복사했는지 확인해주세요.")
