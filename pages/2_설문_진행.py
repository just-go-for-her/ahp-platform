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
        .ranking-board {{ background: #f1f3f5; padding: 15px; border-radius: 10px; margin-bottom: 20px; border: 1px solid #dee2e6; }}
        .board-title {{ font-weight: bold; color: #495057; font-size: 0.9em; margin-bottom: 8px; display: flex; justify-content: space-between; }}
        .board-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 10px; }}
        .board-item {{ background: white; padding: 10px; border-radius: 8px; text-align: center; font-size: 0.85em; border: 1px solid #dee2e6; }}
        .card {{ background: #fff; padding: 25px; border-radius: 12px; text-align: center; margin-bottom: 20px; border: 1px solid #e9ecef; box-shadow: 0 2px 8px rgba(0,0,0,0.02); }}
        input[type=range] {{ width: 100%; margin: 25px 0; cursor: pointer; }}
        .btn {{ width: 100%; padding: 15px; background: #228be6; color: white; border: none; border-radius: 8px; font-size: 1.05em; font-weight: bold; cursor: pointer; margin-top:10px; }}
        .modal {{ display: none; position: fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7); justify-content:center; align-items:center; z-index:9999; }}
        .modal-box {{ background:white; padding:30px; border-radius:15px; width:85%; max-width:450px; text-align:center; }}
        .highlight {{ color: #228be6; font-weight: bold; }}
    </style>
    </head>
    <body>
    <div class="container">
        <h3 id="task-title" style="margin-top:0; color:#343a40;"></h3>

        <div id="live-board" class="ranking-board" style="display:none;">
            <div class="board-title">
                <span>📊 실시간 논리 현황</span>
                <span id="logic-status" style="font-weight:bold;">진행 중...</span>
            </div>
            <div id="board-grid" class="board-grid"></div>
        </div>

        <div id="step-ranking" class="step">
            <p style="color:#495057;"><b>1단계:</b> 각 항목의 <b>기대 순위</b>를 먼저 선택해주세요.</p>
            <div id="ranking-list" style="margin-bottom:20px;"></div>
            <button class="btn" onclick="startCompare()">비교 시작하기</button>
        </div>

        <div id="step-compare" class="step">
            <div class="card">
                <div style="display:flex; justify-content:space-between; font-weight:bold; font-size:1.2em; margin-bottom:20px;">
                    <span id="item-a" style="color:#228be6;">A</span>
                    <span style="color:#dee2e6;">VS</span>
                    <span id="item-b" style="color:#fa5252;">B</span>
                </div>
                <div style="font-size:0.9em; color:#868e96; margin-bottom:10px;">
                    <span id="rank-hint-a"></span> vs <span id="rank-hint-b"></span>
                </div>
                <input type="range" id="slider" min="-4" max="4" value="0" step="1" oninput="updateLabel()">
                <div id="val-display" style="font-weight:bold; color:#495057; font-size:1.15em;">동등함</div>
            </div>
            <button class="btn" onclick="checkLogic()">다음 질문</button>
        </div>

        <div id="step-finish" class="step">
            <h2 style="color:#2f9e44;">🎉 설문 완료!</h2>
            <p style="color:#495057;">생성된 코드를 복사하여 아래 제출란에 붙여넣어주세요.</p>
            <textarea id="result-code" readonly style="width:100%; height:120px; padding:12px; border-radius:8px; border:1px solid #ced4da; background:#f8f9fa; font-family:monospace;"></textarea>
        </div>
    </div>

    <div id="modal" class="modal">
        <div class="modal-box">
            <h3 style="color:#e03131; margin-top:0;">⚠️ 논리 불일치 알림</h3>
            <p style="font-size:0.95em; color:#495057; line-height:1.6; text-align:left;">
                현재 응답을 저장하면 처음에 설정한 순위와 상충하는 결과가 나옵니다.
            </p>
            <div style="background:#f1f3f5; padding:15px; border-radius:8px; margin:15px 0; font-size:0.9em; text-align:left;">
                <div>💡 <b>권장 방향:</b> <span id="rec-val" class="highlight"></span></div>
                <div style="margin-top:5px; color:#868e96; font-size:0.85em;">* 순위를 유지하려면 슬라이더를 위 방향으로 조정하세요.</div>
            </div>
            <div style="display:grid; gap:10px;">
                <button class="btn" onclick="closeModal('resurvey')" style="background:#228be6;">다시 선택하기</button>
                <button class="btn" onclick="closeModal('updaterank')" style="background:#868e96;">현재 응답대로 순위 변경</button>
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
                listDiv.innerHTML += `<div style="display:flex; justify-content:space-between; padding:12px; background:#f8f9fa; border-radius:8px; margin-bottom:8px; align-items:center; border:1px solid #eee;">
                    <span style="font-weight:bold; color:#495057;">${{item}}</span><select id="rank-${{idx}}" style="padding:6px; border-radius:4px;">${{options}}</select></div>`;
            }});
            showStep('step-ranking'); document.getElementById('live-board').style.display = 'none';
        }}

        function startCompare() {{
            initialRanks = [];
            for(let i=0; i<items.length; i++) {{
                const v = document.getElementById('rank-'+i).value;
                if(!v) {{ alert("모든 항목의 기대 순위를 정해주세요."); return; }}
                initialRanks.push(parseInt(v));
            }}
            if(new Set(initialRanks).size !== initialRanks.length) {{ alert("중복된 순위가 있습니다."); return; }}
            const n = items.length; matrix = Array.from({{length: n}}, () => Array(n).fill(0));
            for(let i=0; i<n; i++) matrix[i][i] = 1;
            pairs = [];
            for(let i=0; i<n; i++) {{ for(let j=i+1; j<n; j++) {{ pairs.push({{ r: i, c: j, a: items[i], b: items[j] }}); }} }}
            pairIdx = 0; showStep('step-compare'); renderPair();
        }}

        function renderPair() {{
            const p = pairs[pairIdx];
            document.getElementById('item-a').innerText = p.a; document.getElementById('item-b').innerText = p.b;
            document.getElementById('rank-hint-a').innerText = `기대: ${{initialRanks[p.r]}}위`;
            document.getElementById('rank-hint-b').innerText = `기대: ${{initialRanks[p.c]}}위`;
            document.getElementById('slider').value = 0; updateLabel(); 
            document.getElementById('live-board').style.display = 'block';
            updateBoard(false); // 질문 중엔 아직 보드 업데이트 안 함 (혼란 방지)
        }}

        function updateLabel() {{
            const val = parseInt(document.getElementById('slider').value);
            const p = pairs[pairIdx]; const disp = document.getElementById('val-display');
            if(val == 0) disp.innerText = "동등함 (1:1)";
            else if(val < 0) disp.innerText = `${{p.a}} ${{Math.abs(val)+1}}배 더 중요`;
            else disp.innerText = `${{p.b}} ${{val+1}}배 더 중요`;
        }}

        function updateBoard(finalCheck) {{
            const grid = document.getElementById('board-grid'); grid.innerHTML = "";
            const n = items.length;
            
            // 아직 확정되지 않은 매트릭스 복사
            let tempMatrix = matrix.map(row => [...row]);
            
            items.forEach((item, i) => {{
                // 확정된 데이터가 있는 항목만 표시
                const hasData = tempMatrix[i].some((v, idx) => v !== 0 && i !== idx);
                grid.innerHTML += `<div class="board-item" style="opacity: ${{hasData ? 1 : 0.5}};">
                    <div style="font-weight:bold; color:#1971c2;">${{item}}</div>
                    <div style="font-size:0.75em; color:#868e96;">기대: ${{initialRanks[i]}}위</div>
                    <div id="curr-rank-${{i}}" style="font-size:0.85em; font-weight:bold; color:#495057;">-</div>
                </div>`;
            }});
        }}

        function checkLogic() {{
            const sliderVal = parseInt(document.getElementById('slider').value);
            const p = pairs[pairIdx];
            const rankA = initialRanks[p.r]; const rankB = initialRanks[p.c];
            
            // [개선] 첫 번째 질문에서는 순위 모순을 체크하지 않음 (기준 데이터가 없음)
            if (pairIdx > 0) {{
                if ((rankA < rankB && sliderVal > 0) || (rankA > rankB && sliderVal < 0)) {{
                    showModal(); return;
                }}
            }}
            saveAndNext();
        }}

        function showModal() {{
            const p = pairs[pairIdx];
            const rankA = initialRanks[p.r];
            document.getElementById('rec-val').innerText = rankA < initialRanks[p.c] ? `"${{p.a}}" 쪽 우세` : `"${{p.b}}" 쪽 우세`;
            document.getElementById('modal').style.display = 'flex';
        }}

        function closeModal(action) {{
            document.getElementById('modal').style.display = 'none';
            if(action === 'updaterank') {{
                saveAndNext();
            }} else {{
                document.getElementById('slider').value = 0; updateLabel();
            }}
        }}

        function saveAndNext() {{
            const val = parseInt(document.getElementById('slider').value);
            const w = val === 0 ? 1 : (val < 0 ? Math.abs(val)+1 : 1/(val+1));
            const p = pairs[pairIdx];
            matrix[p.r][p.c] = w; matrix[p.c][p.r] = 1/w;
            allAnswers[`[${{tasks[currentTaskIdx].name}}] ${{p.a}} vs ${{p.b}}`] = (w >= 1 ? w : -1*(1/w)).toFixed(2);
            pairIdx++;
            if (pairIdx >= pairs.length) {{ currentTaskIdx++; loadTask(); }}
            else {{ renderPair(); }}
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
        st.write("📋 **데이터 제출**")
        respondent = st.text_input("응답자 성함")
        code = st.text_area("결과 코드 붙여넣기")
        if st.form_submit_button("최종 제출하기", type="primary", use_container_width=True):
            if not respondent or not code:
                st.warning("성함과 코드를 모두 입력해주세요.")
            else:
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
                    st.success("✅ 제출되었습니다! 감사합니다.")
                    st.balloons()
                except Exception as e: st.error(f"오류: {e}")
