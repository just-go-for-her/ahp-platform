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
        if not project_key: st.error("비밀번호 설정이 필요합니다.")
        else:
            full_structure = {**survey_data, "secret_key": project_key}
            survey_id = uuid.uuid4().hex[:8]
            with open(os.path.join(CONFIG_DIR, f"{survey_id}.json"), "w", encoding="utf-8") as f:
                json.dump(full_structure, f, ensure_ascii=False, indent=2)
            st.code(f"{FULL_URL}?id={survey_id}")
            st.success("공유 링크가 생성되었습니다.")

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
        .board-title {{ font-weight: bold; color: #495057; font-size: 0.9em; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; }}
        .status-pill {{ padding: 4px 12px; border-radius: 20px; font-size: 0.82em; font-weight: bold; }}
        
        .board-grid {{ display: flex; gap: 10px; overflow-x: auto; padding-bottom: 10px; }}
        
        .board-item {{ 
            min-width: 140px; background: white; padding: 12px; border-radius: 12px; 
            text-align: center; border: 1px solid #dee2e6; 
            flex: 1; display: flex; flex-direction: column; gap: 5px; 
            position: relative; 
            transition: all 0.3s ease;
        }}
        
        .flipped-card {{
            border: 2px solid #fa5252 !important;
            background-color: #fff5f5 !important;
            box-shadow: 0 4px 12px rgba(250, 82, 82, 0.15);
        }}

        .item-name {{ font-weight: 800; color: #343a40; border-bottom: 1px solid #f1f3f5; padding-bottom: 6px; }}
        .rank-row {{ display: flex; justify-content: space-between; font-size: 0.85em; color: #666; }}
        .rank-val {{ font-weight: bold; color: #228be6; }}
        
        .error-text {{ color: #fa5252 !important; font-weight: 900; }}
        .match-text {{ color: #228be6; }}

        .card {{ background: #fff; padding: 30px; border-radius: 15px; text-align: center; margin-bottom: 20px; border: 1px solid #e9ecef; box-shadow: 0 4px 12px rgba(0,0,0,0.03); }}
        input[type=range] {{ -webkit-appearance: none; width: 100%; height: 12px; background: #dee2e6; border-radius: 6px; outline: none; margin: 35px 0; }}
        input[type=range]::-webkit-slider-thumb {{ -webkit-appearance: none; appearance: none; width: 28px; height: 28px; background: #228be6; border: 4px solid white; border-radius: 50%; cursor: pointer; box-shadow: 0 2px 6px rgba(0,0,0,0.2); position: relative; z-index: 5; }}

        .btn {{ width: 100%; padding: 15px; background: #228be6; color: white; border: none; border-radius: 10px; font-size: 1.1em; font-weight: bold; cursor: pointer; }}
        .btn-secondary {{ background: #adb5bd; }}
        .btn-reset {{ background: #868e96; color: white; }} 
        
        .btn-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 20px; }}

        .modal {{ display: none; position: fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7); justify-content:center; align-items:center; z-index:9999; }}
        .modal-box {{ background:white; padding:35px; border-radius:20px; width:90%; max-width:450px; text-align:center; }}
        
        .flip-list {{ text-align: left; background: #fff5f5; padding: 15px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #ffc9c9; font-size: 0.9em; color: #c92a2a; }}
        .flip-item {{ margin-bottom: 4px; font-weight: bold; }}
    </style>
    </head>
    <body>
    <div class="container">
        <h3 id="task-title" style="margin-top:0; color:#212529;"></h3>

        <div id="live-board" class="ranking-board" style="display:none;">
            <div class="board-title">
                <span>📊 실시간 순위 현황</span>
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
                    (기존 순위: <span id="hint-a"></span>위) vs (기존 순위: <span id="hint-b"></span>위)
                </div>
                <input type="range" id="slider" min="-4" max="4" value="0" step="1" oninput="updateUI(true)">
                <div id="val-display" style="font-weight:bold; color:#343a40; font-size:1.4em;">동등함</div>
            </div>
            
            <div id="btn-area" class="btn-grid"></div>
        </div>

        <div id="step-finish" class="step">
            <div style="text-align:center; padding:40px 0;">
                <h2>✅ 모든 설문 완료</h2>
                <textarea id="result-code" readonly style="width:100%; height:150px; padding:15px; border-radius:12px; border:1px solid #dee2e6; background:#f8f9fa; font-family:monospace;"></textarea>
            </div>
        </div>
    </div>

    <div id="modal-flip" class="modal">
        <div class="modal-box">
            <h3 style="color:#fa5252; margin-top:0;">⚠️ 순위 역전 감지</h3>
            <p style="font-size:0.95em; color:#495057; line-height:1.7; margin-bottom:15px;">
                설정하신 순위와 달리, 아래 항목들의 점수가 뒤집혔습니다.<br>
                (동점은 허용되지만, <b>확실히 낮아진 경우</b>입니다)
            </p>
            <div id="flip-details" class="flip-list"></div>
            <div style="display:grid; gap:12px;">
                <button class="btn" onclick="closeModal('flip', 'resurvey')" style="background:#228be6;">👈 응답 수정 (기존 순위 유지)</button>
                <button class="btn" onclick="closeModal('flip', 'updaterank')" style="background:#868e96;">✅ 변경 인정 (설정값 업데이트)</button>
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
            
            // 순위대로 정렬 (1위, 2위, 3위...)
            tempIdxMap.sort((a, b) => a.rank - b.rank);
            
            pairs = [];
            // 정렬된 순서대로 쌍 생성 (항상 상위 순위가 왼쪽(A)에 오도록 됨)
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
            
            pairIdx = 0; 
            showStep('step-compare'); 
            renderPair();
        }}

        function renderPair() {{
            const p = pairs[pairIdx];
            document.getElementById('item-a').innerText = p.a; 
            document.getElementById('item-b').innerText = p.b;
            document.getElementById('hint-a').innerText = initialRanks[p.r];
            document.getElementById('hint-b').innerText = initialRanks[p.c];
            document.getElementById('slider').value = 0;
            
            const btnArea = document.getElementById('btn-area');
            if (pairIdx === 0) {{
                btnArea.innerHTML = `
                    <button class="btn btn-reset" onclick="resetTask()">🔄 순위 변경</button>
                    <button class="btn" onclick="checkLogic()">다음 질문 ➡</button>
                `;
            }} else {{
                btnArea.innerHTML = `
                    <button class="btn btn-secondary" onclick="goBack()">⬅ 이전 질문</button>
                    <button class="btn" onclick="checkLogic()">다음 질문 ➡</button>
                `;
            }}

            document.getElementById('live-board').style.display = 'block';
            // Render board but don't check for alerts yet
            updateUI(false); 
        }}

        function updateUI(checkAlert = false) {{
            const slider = document.getElementById('slider');
            let val = parseInt(slider.value);
            const p = pairs[pairIdx];

            // [핵심] 슬라이더 이동 방향 제한 (Alert & Reset)
            // p.r(A)이 p.c(B)보다 순위가 높음(숫자가 작음) -> val은 음수(왼쪽)여야 함
            if (checkAlert) {{
                if (initialRanks[p.r] < initialRanks[p.c] && val > 0) {{
                    alert(`🚫 [논리 보호]\\n\\n이미 '${{p.a}}' 항목을 상위 순위로 설정하셨습니다.\\n따라서 점수도 '${{p.a}}' 쪽(왼쪽)으로만 줄 수 있습니다.`);
                    slider.value = 0; val = 0;
                }} 
                else if (initialRanks[p.r] > initialRanks[p.c] && val < 0) {{
                    alert(`🚫 [논리 보호]\\n\\n이미 '${{p.b}}' 항목을 상위 순위로 설정하셨습니다.\\n따라서 점수도 '${{p.b}}' 쪽(오른쪽)으로만 줄 수 있습니다.`);
                    slider.value = 0; val = 0;
                }}
            }}

            const disp = document.getElementById('val-display');
            let perc = (val + 4) * 12.5;
            
            if(val < 0) slider.style.background = `linear-gradient(to right, #dee2e6 0%, #dee2e6 ${{perc}}%, #228be6 ${{perc}}%, #228be6 50%, #dee2e6 50%, #dee2e6 100%)`;
            else if(val > 0) slider.style.background = `linear-gradient(to right, #dee2e6 0%, #dee2e6 50%, #fa5252 50%, #fa5252 ${{perc}}%, #dee2e6 ${{perc}}%, #dee2e6 100%)`;
            else slider.style.background = '#dee2e6';

            if(val == 0) disp.innerText = "동등함 (1:1)";
            else if(val < 0) disp.innerText = `${{p.a}} ${{Math.abs(val)+1}}배 중요`;
            else disp.innerText = `${{p.b}} ${{Math.abs(val)+1}}배 중요`; 
            
            updateBoard();
        }}

        function updateBoard() {{
            const grid = document.getElementById('board-grid'); 
            grid.innerHTML = "";
            const pill = document.getElementById('status-pill');
            
            let weights = calculateWeights();
            const EPSILON = 0.00001;

            // 순위 계산 (동점 처리: 기존 순위 우선 -> 절대 동순위 없음)
            let indexedWeights = weights.map((w, i) => ({{w, i}}));
            indexedWeights.sort((a,b) => {{
                if (Math.abs(b.w - a.w) > EPSILON) return b.w - a.w;
                return initialRanks[a.i] - initialRanks[b.i];
            }});

            let rankMap = {{}};
            indexedWeights.forEach((obj, idx) => rankMap[obj.i] = idx + 1);

            let flippedIndices = new Set();
            if (pairIdx > 0) {{
                for(let i=0; i<items.length; i++) {{
                    for(let j=0; j<items.length; j++) {{
                        if(i === j) continue;
                        if (initialRanks[i] < initialRanks[j] && rankMap[i] > rankMap[j]) {{
                            flippedIndices.add(i); flippedIndices.add(j);
                        }}
                    }}
                }}
            }}

            let hasFlip = (flippedIndices.size > 0);
            
            if (pairIdx === 0) {{
                pill.innerText = "✅ 순위 설정 완료"; pill.style.background = "#ebfbee"; pill.style.color = "#2f9e44";
            }} else if (hasFlip) {{
                pill.innerText = "⚠️ 순위 역전 감지"; pill.style.background = "#fff5f5"; pill.style.color = "#fa5252";
            }} else {{
                pill.innerText = "✅ 논리 일치"; pill.style.background = "#ebfbee"; pill.style.color = "#2f9e44";
            }}

            let fixedOrder = items.map((name, i) => ({{name, org: initialRanks[i], idx: i}}))
                                    .sort((a,b) => a.org - b.org);

            fixedOrder.forEach(item => {{
                let isFlipped = flippedIndices.has(item.idx);
                
                // [핵심] 첫 질문(pairIdx==0)일 땐 '현재 순위' = '기존 순위'로 고정 (울렁임 방지)
                let curRank = (pairIdx === 0) ? item.org : rankMap[item.idx];
                
                let borderStyle = isFlipped ? "2px solid #fa5252 !important" : "1px solid #dee2e6";
                let bgStyle = isFlipped ? "#fff5f5 !important" : "white";
                let textColorClass = isFlipped ? "error-text" : "match-text";
                let shadow = isFlipped ? "box-shadow: 0 4px 12px rgba(250, 82, 82, 0.15);" : "";

                // [핵심] 첫 질문에서는 '현재 순위' 행을 아예 안 보여줌 (깔끔)
                let currentRankHtml = "";
                if (pairIdx > 0) {{
                    currentRankHtml = `<div class="rank-row"><span>현재:</span><span class="rank-val ${{textColorClass}}">${{curRank}}위</span></div>`;
                }}

                grid.innerHTML += `
                <div class="board-item" style="border: ${{borderStyle}}; background-color: ${{bgStyle}}; ${{shadow}}">
                    <span class="item-name">${{item.name}}</span>
                    <div class="rank-row"><span>기존:</span><span class="rank-val">${{item.org}}위</span></div>
                    ${{currentRankHtml}}
                </div>`;
            }});
        }}

        function calculateWeights(tempVal = null) {{
            const n = items.length; 
            let tempMatrix = matrix.map(row => [...row]);
            let p = pairs[pairIdx];
            let val = tempVal !== null ? tempVal : parseInt(document.getElementById('slider').value);
            
            let w_abs = Math.abs(val) + 1;
            let w_final = (val <= 0) ? w_abs : (1 / w_abs);

            tempMatrix[p.r][p.c] = w_final; 
            tempMatrix[p.c][p.r] = 1 / w_final;
            
            for(let i=0; i<n; i++) {{ for(let j=0; j<n; j++) {{ if(tempMatrix[i][j] === 0) tempMatrix[i][j] = 1; }} }}
            let weights = tempMatrix.map(row => Math.pow(row.reduce((a, b) => a * b, 1), 1/n));
            let sum = weights.reduce((a, b) => a + b, 0);
            return weights.map(v => v / sum);
        }}

        function checkLogic() {{
            if (pairIdx === 0) {{ saveAndNext(); return; }}
            const sliderVal = parseInt(document.getElementById('slider').value);
            
            let weights = calculateWeights(sliderVal);
            const EPSILON = 0.00001;
            let indexedWeights = weights.map((w, i) => ({{w, i}})).sort((a,b) => {{
                if (Math.abs(b.w - a.w) > EPSILON) return b.w - a.w;
                return initialRanks[a.i] - initialRanks[b.i];
            }});
            let rankMap = {{}};
            indexedWeights.forEach((obj, idx) => rankMap[obj.i] = idx + 1);

            let flippedPairs = [];
            for(let i=0; i<items.length; i++) {{
                for(let j=0; j<items.length; j++) {{
                    if(i === j) continue;
                    if(initialRanks[i] < initialRanks[j] && rankMap[i] > rankMap[j]) {{
                        flippedPairs.push(`${{items[i]}} (기존 ${{initialRanks[i]}}위) ↔ ${{items[j]}} (기존 ${{initialRanks[j]}}위)`);
                    }}
                }}
            }}

            if (flippedPairs.length > 0) {{ 
                const listDiv = document.getElementById('flip-details');
                listDiv.innerHTML = "";
                [...new Set(flippedPairs)].forEach(txt => {{
                    listDiv.innerHTML += `<div class="flip-item">❌ ${{(txt)}}</div>`;
                }});
                document.getElementById('modal-flip').style.display = 'flex'; 
                return; 
            }}

            // CR 체크는 데이터 센터(Page 3)로 이관됨 -> 바로 저장
            saveAndNext();
        }}

        function closeModal(type, action) {{
            document.getElementById('modal-' + type).style.display = 'none';
            if (type === 'flip') {{
                if(action === 'updaterank') {{
                    let weights = calculateWeights();
                    let sortedIdx = weights.map((w, i) => i).sort((a, b) => weights[b] - weights[a]);
                    sortedIdx.forEach((idx, i) => {{ initialRanks[idx] = i + 1; }});
                    saveAndNext();
                }} else {{
                    document.getElementById('slider').value = 0; updateUI();
                }}
            }}
        }}

        function resetTask() {{
            // 현재 작업의 순위 설정 화면(1단계)으로 돌아감 (새로고침 아님)
            if(confirm("순위 설정 화면으로 돌아가시겠습니까?\\n(입력한 내용은 초기화됩니다)")) {{ 
                loadTask(); 
            }}
        }}

        function goBack() {{ if (pairIdx > 0) {{ pairIdx--; renderPair(); }} }}

        function saveAndNext() {{
            const val = parseInt(document.getElementById('slider').value);
            let w_abs = Math.abs(val) + 1;
            let w_final = (val <= 0) ? w_abs : (1 / w_abs);

            const p = pairs[pairIdx];
            matrix[p.r][p.c] = w_final; matrix[p.c][p.r] = 1/w_final;
            allAnswers[`[${{tasks[currentTaskIdx].name}}] ${{p.a}} vs ${{p.b}}`] = w_final.toFixed(2);
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
    with st.form("save_v_final"):
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
                    df = pd.DataFrame([save_dict])
                    try: old_df = pd.read_csv(file_path)
                    except: old_df = pd.DataFrame()
                    pd.concat([old_df, df], ignore_index=True).to_csv(file_path, index=False)
                    st.success("✅ 제출 성공!"); st.balloons()
                except: st.error("코드 오류")
