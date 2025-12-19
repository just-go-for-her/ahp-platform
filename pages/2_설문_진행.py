import streamlit as st
import streamlit.components.v1 as components
import json
import base64 
import urllib.parse
import pandas as pd
from datetime import datetime
import os
import uuid 

# ==============================================================================
# [설정] 본인의 실제 배포 주소 입력
# ==============================================================================
FULL_URL = "https://ahp-platform-bbee45epwqjjy2zfpccz7p.streamlit.app/%EC%84%A4%EB%AC%B8_%EC%A7%84%ED%96%89"
# ==============================================================================

# 설문 구조(연구자용) 저장 디렉토리
CONFIG_DIR = "survey_config"
os.makedirs(CONFIG_DIR, exist_ok=True)

st.set_page_config(page_title="설문 진행", page_icon="📝", layout="wide")

# 1. URL 데이터 처리
query_params = st.query_params
raw_id = query_params.get("id", None)
if isinstance(raw_id, list):
    survey_id = raw_id[0] if raw_id else None
else:
    survey_id = raw_id

survey_data = None

# ------------------------------------------------------------------
# [MODE B] 응답자 모드: id 로 설문 구조 불러오기
# ------------------------------------------------------------------
if survey_id:
    config_path = os.path.join(CONFIG_DIR, f"{survey_id}.json")
    if not os.path.exists(config_path):
        st.error("유효하지 않은 설문 링크입니다. (설문 ID를 찾을 수 없습니다)")
        st.stop()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            survey_data = json.load(f)
        is_respondent = True
    except Exception as e:
        st.error(f"설문 구성을 불러오는 중 오류가 발생했습니다: {e}")
        st.stop()
else:
    is_respondent = False
    if "passed_structure" in st.session_state:
        survey_data = st.session_state["passed_structure"]
    else:
        survey_data = None

# ------------------------------------------------------------------
# [MODE A] 연구자: 비밀번호 설정 및 링크 생성
# ------------------------------------------------------------------
if not is_respondent:
    st.title("📢 설문 배포 센터 (Private Mode)")

    if not survey_data:
        st.warning("⚠️ 확정된 구조가 없습니다. [1번 페이지]에서 구조를 먼저 확정하세요.")
        st.stop()

    st.success(f"**목표:** {survey_data['goal']}")

    if "여기에" in FULL_URL:
        st.error("🚨 코드 맨 윗줄의 'FULL_URL'을 설정해주세요!")
        st.stop()

    with st.container(border=True):
        st.subheader("🔐 보안 설정 (관리자용)")
        st.caption("응답자는 이 비밀번호를 알 필요가 없습니다. 데이터 확인용으로 연구자만 기억하세요.")
        project_key = st.text_input(
            "프로젝트 비밀번호(Key) 설정",
            placeholder="예: team_a (이 키는 결과 조회 시 필요합니다)",
            type="password",
        )

    if st.button("🔗 공유 링크 생성하기", type="primary", use_container_width=True):
        if not project_key:
            st.error("데이터 관리를 위해 비밀번호를 설정해주세요.")
        else:
            full_structure = {
                "goal": survey_data["goal"],
                "main_criteria": survey_data["main_criteria"],
                "sub_criteria": survey_data["sub_criteria"],
                "secret_key": project_key,
            }
            survey_id = uuid.uuid4().hex[:8]
            config_path = os.path.join(CONFIG_DIR, f"{survey_id}.json")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(full_structure, f, ensure_ascii=False, indent=2)

            final_url = f"{FULL_URL}?id={survey_id}"

            st.markdown("### 👇 아래 버튼을 눌러 공유하세요")
            components.html(
                f"""
            <style>
                body {{ margin: 0; padding: 0; font-family: sans-serif; }}
                .kakao-btn {{
                    background-color: #FEE500; color: #000000; border: none; border-radius: 12px;
                    padding: 15px 0; width: 100%; font-size: 16px; font-weight: bold; cursor: pointer;
                    display: flex; align-items: center; justify-content: center; gap: 10px;
                }}
            </style>
            <script>
                function copyLink() {{
                    const url = '{final_url}';
                    navigator.clipboard.writeText(url).then(() => {{
                        document.getElementById('msg').innerText = "✅ 복사되었습니다! 카톡방에 붙여넣으세요.";
                        setTimeout(() => {{ document.getElementById('msg').innerText = ""; }}, 3000);
                    }}).catch(err => {{ prompt("이 링크를 복사하세요:", url); }});
                }}
            </script>
            <button class="kakao-btn" onclick="copyLink()">💬 카카오톡 링크 복사하기</button>
            <div id="msg" style="text-align:center; color:green; font-size:12px; margin-top:5px; height:20px;"></div>
            """, height=100)

# ------------------------------------------------------------------
# [MODE B] 응답자: 설문 진행
# ------------------------------------------------------------------
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
        body {{ font-family: "Pretendard", sans-serif; padding: 20px; }}
        .step {{ display: none; animation: fadeIn 0.3s; }}
        .active {{ display: block; }}
        @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
        .container {{ max-width: 700px; margin: 0 auto; background: white; padding: 30px; border-radius: 15px; box-shadow: 0 5px 20px rgba(0,0,0,0.08); border: 1px solid #eee; }}
        h2 {{ color: #333; border-bottom: 2px solid #228be6; padding-bottom: 10px; }}
        .ranking-item {{ display: flex; justify-content: space-between; margin-bottom: 10px; padding: 10px; background: #f8f9fa; border-radius: 8px; align-items: center; }}
        .card {{ background: #f8f9fa; padding: 20px; border-radius: 12px; text-align: center; margin-bottom: 20px; }}
        .vs-row {{ display: flex; justify-content: space-between; font-size: 1.2em; font-weight: bold; margin-bottom: 15px; }}
        input[type=range] {{ width: 100%; margin: 20px 0; cursor: pointer; }}
        .btn {{ width: 100%; padding: 15px; background: #228be6; color: white; border: none; border-radius: 8px; font-size: 1.1em; cursor: pointer; }}
        .modal {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); justify-content: center; align-items: center; }}
        .modal-box {{ background: white; padding: 30px; border-radius: 15px; width: 90%; max-width: 450px; text-align: center; }}
        .logic-text {{ color: #228be6; font-weight: bold; font-size: 1.1em; }}
        .user-text {{ color: #fa5252; font-weight: bold; font-size: 1.1em; }}
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
                <input type="range" id="slider" min="-4" max="4" value="0" step="1" oninput="updateLabel()">
                <div id="val-display" style="font-weight:bold; color:#555; font-size:1.1em; margin-top:10px;">동등함</div>
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
            <p style="font-size:0.9em; color:#666;">이전 응답을 분석한 결과, 순위 논리를 유지하면서 추천되는 값입니다.</p>
            <div style="background:#f1f3f5; padding:20px; border-radius:10px; margin:20px 0; text-align:left;">
                <div style="margin-bottom:10px;">🧠 AI 추천: <span id="rec-val" class="logic-text"></span></div>
                <div>🖐 나의 선택: <span id="my-val" class="user-text"></span></div>
            </div>
            <div style="display:flex; gap:10px;">
                <button class="btn" style="background:#adb5bd;" onclick="closeModal(false)">내 선택 유지</button>
                <button class="btn" onclick="closeModal(true)">다시 설문하기</button>
            </div>
        </div>
    </div>

    <script>
        const tasks = {js_tasks};
        let currentTaskIdx = 0;
        let items = [], pairs = [], matrix = [], pairIdx = 0, initialRanks = [];
        let allAnswers = {{}};

        function getWeightFromSlider(val) {{
            if (val === 0) return 1;
            return val < 0 ? (Math.abs(val) + 1) : (1 / (val + 1));
        }}

        function loadTask() {{
            if (currentTaskIdx >= tasks.length) {{ finishAll(); return; }}
            const task = tasks[currentTaskIdx];
            items = task.items;
            document.getElementById('task-title').innerText = task.name;
            const listDiv = document.getElementById('ranking-list');
            listDiv.innerHTML = "";
            let options = '<option value="" selected disabled>선택</option>';
            for(let i=1; i<=items.length; i++) options += `<option value="${{i}}">${{i}}위</option>`;
            items.forEach((item, idx) => {{
                listDiv.innerHTML += `<div class="ranking-item"><span>${{item}}</span><select id="rank-${{idx}}" class="rank-select" style="padding:5px; border-radius:5px;">${{options}}</select></div>`;
            }});
            showStep('step-ranking');
        }}

        function startCompare() {{
            initialRanks = [];
            for(let i=0; i<items.length; i++) {{
                const val = document.getElementById('rank-'+i).value;
                if(!val) {{ alert("순위를 모두 선택해주세요."); return; }}
                initialRanks.push(val);
            }}
            if(new Set(initialRanks).size !== initialRanks.length) {{ alert("⚠️ 중복된 순위가 있습니다!"); return; }}
            const n = items.length;
            matrix = Array.from({{length: n}}, () => Array(n).fill(0));
            for(let i=0; i<n; i++) matrix[i][i] = 1;
            pairs = [];
            for(let i=0; i<n; i++) {{ for(let j=i+1; j<n; j++) {{ pairs.push({{ r: i, c: j, a: items[i], b: items[j] }}); }} }}
            pairIdx = 0;
            showStep('step-compare');
            renderPair();
        }}

        function renderPair() {{
            if (pairIdx >= pairs.length) {{ currentTaskIdx++; loadTask(); return; }}
            const p = pairs[pairIdx];
            document.getElementById('item-a').innerText = p.a;
            document.getElementById('item-b').innerText = p.b;
            document.getElementById('rank-hint-a').innerText = `(${{initialRanks[p.r]}}위)`;
            document.getElementById('rank-hint-b').innerText = `(${{initialRanks[p.c]}}위)`;
            document.getElementById('slider').value = 0;
            updateLabel();
            document.getElementById('progress').innerText = (pairIdx + 1) + " / " + pairs.length;
        }}

        function updateLabel() {{
            const val = parseInt(document.getElementById('slider').value);
            const disp = document.getElementById('val-display');
            const p = pairs[pairIdx];
            if(val == 0) {{ disp.innerText = "동등함 (1:1)"; disp.style.color = "#555"; }}
            else if(val < 0) {{ disp.innerText = p.a + " " + (Math.abs(val)+1) + "배 중요"; disp.style.color = "#228be6"; }}
            else {{ disp.innerText = p.b + " " + (val+1) + "배 중요"; disp.style.color = "#fa5252"; }}
        }}

        function checkConsistency() {{
            const sliderVal = parseInt(document.getElementById('slider').value);
            const p = pairs[pairIdx];
            const rankA = parseInt(initialRanks[p.r]);
            const rankB = parseInt(initialRanks[p.c]);

            if (rankA < rankB && sliderVal > 0) {{ alert(`⚠️ 순위 모순! '${{p.a}}'(${{rankA}}위)가 더 높으므로 오른쪽으로 갈 수 없습니다.`); return; }}
            if (rankA > rankB && sliderVal < 0) {{ alert(`⚠️ 순위 모순! '${{p.b}}'(${{rankB}}위)가 더 높으므로 왼쪽으로 갈 수 없습니다.`); return; }}

            let currentWeight = getWeightFromSlider(sliderVal);
            const n = items.length;
            let indirectEstimates = [];
            for(let k=0; k<n; k++) {{
                if(k === p.r || k === p.c) continue;
                if(matrix[p.r][k] !== 0 && matrix[k][p.c] !== 0) indirectEstimates.push(matrix[p.r][k] * matrix[k][p.c]);
            }}

            if(indirectEstimates.length > 0) {{
                let geoMean = Math.exp(indirectEstimates.reduce((acc, val) => acc + Math.log(val), 0) / indirectEstimates.length);
                if (rankA < rankB && geoMean < 1) geoMean = 1;
                if (rankA > rankB && geoMean > 1) geoMean = 1;

                const ratio = currentWeight > geoMean ? currentWeight / geoMean : geoMean / currentWeight;
                if(ratio >= 2.0) {{ showModal(geoMean, currentWeight); return; }}
            }}
            saveAnswer(currentWeight);
        }}

        function showModal(recW, usrW) {{
            const fmt = (w) => {{
                if (w >= 1.1) return "왼쪽(A) " + Math.min(5, Math.round(w)) + "배";
                if (w <= 0.9) return "오른쪽(B) " + Math.min(5, Math.round(1/w)) + "배";
                return "동등함(1:1)";
            }};
            document.getElementById('rec-val').innerText = fmt(recW);
            document.getElementById('my-val').innerText = fmt(usrW);
            document.getElementById('modal').style.display = 'flex';
        }}

        function closeModal(reSurvey) {{
            document.getElementById('modal').style.display = 'none';
            if(reSurvey) {{
                document.getElementById('slider').value = 0; updateLabel();
                alert("💡 추천값을 참고하여 슬라이더를 다시 조정해 주세요.");
            }} else {{
                saveAnswer(getWeightFromSlider(parseInt(document.getElementById('slider').value)));
            }}
        }}

        function saveAnswer(w) {{
            const p = pairs[pairIdx];
            matrix[p.r][p.c] = w; matrix[p.c][p.r] = 1 / w;
            let logVal = w >= 1 ? w : -1 * (1/w);
            allAnswers[`[${{tasks[currentTaskIdx].name}}] ${{p.a}} vs ${{p.b}}`] = logVal.toFixed(2);
            pairIdx++; renderPair();
        }}

        function finishAll() {{ showStep('step-finish'); document.getElementById('result-code').value = JSON.stringify(allAnswers); }}
        function showStep(id) {{ document.querySelectorAll('.step').forEach(e => e.classList.remove('active')); document.getElementById(id).classList.add('active'); }}
        loadTask();
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
                goal_clean = survey_data["goal"].replace(" ", "_")
                secret_key = survey_data.get("secret_key", "public")
                if not os.path.exists("survey_data"): os.makedirs("survey_data")
                
                # [오타 수정 완료] 중괄호를 하나만 사용
                file_path = f"survey_data/{secret_key}_{goal_clean}.csv"
                
                save_data = { "Time": datetime.now().strftime("%Y-%m-%d %H:%M"), "Respondent": respondent, "Raw_Data": code }
                df = pd.DataFrame([save_data])
                try: old_df = pd.read_csv(file_path)
                except: old_df = pd.DataFrame()
                pd.concat([old_df, df], ignore_index=True).to_csv(file_path, index=False)
                st.success(f"✅ '{respondent}'님, 안전하게 제출되었습니다! 감사합니다.")
                st.balloons()
            except Exception as e:
                st.error(f"오류 발생: {e}")
