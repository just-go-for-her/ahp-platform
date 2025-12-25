import streamlit as st
import pandas as pd
import numpy as np
import json
import io
import os
import re
import requests # [추가] 구글 시트 데이터를 가져오기 위해 필요

# ==============================================================================
# [설정] 페이지 기본 설정
# ==============================================================================
st.set_page_config(page_title="결과 데이터 센터", page_icon="📊", layout="wide")
st.title("📊 AHP 결과 데이터 센터")

# 데이터 저장소 경로
DATA_FOLDER = "survey_data"
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

# [추가] 구글 시트 데이터 로드 함수
def load_from_google_cloud(user_key):
    """
    구글 시트에 저장된 전체 데이터 중 현재 사용자의 비밀번호(user_key)와 일치하는 것만 가져옵니다.
    """
    WEBAPP_URL = "https://script.google.com/macros/s/AKfycbw-c1Cf71eSMFaouFhN_YziqOl05KBqZzt4-qOXFwkbFBUQrS4ADMozoIswYdAsQiIIOQ/exec"
    try:
        response = requests.get(WEBAPP_URL, params={"user_key": user_key}, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data:
                return pd.DataFrame(data)
    except:
        pass
    return pd.DataFrame()

# ==============================================================================
# [함수] 스마트 매칭 & 행렬 보정 엔진 (기존 코드 유지)
# ==============================================================================
def is_match(main_name, sub_task_name):
    clean_main = main_name.replace(" ", "").strip()
    clean_sub = sub_task_name.replace(" ", "").strip()
    if clean_main in clean_sub: return True
    match = re.search(r'\[(.*?)\]', sub_task_name)
    if match:
        extracted = match.group(1).replace(" ", "").strip()
        if extracted == clean_main: return True
    return False

def get_cr(matrix, n):
    try:
        eigvals, _ = np.linalg.eig(matrix)
        max_eigval = np.max(eigvals.real)
        ci = (max_eigval - n) / (n - 1) if n > 1 else 0
        ri_table = {1: 0, 2: 0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45}
        ri = ri_table.get(n, 1.49)
        return ci / ri if ri != 0 else 0
    except:
        return 1.0

def calibrate_matrix(matrix, target_cr=0.1, max_iter=50, max_scale=5.0):
    n = matrix.shape[0]
    curr_matrix = matrix.copy()
    for _ in range(max_iter):
        cr = get_cr(curr_matrix, n)
        if cr <= target_cr: break
        eigvals, eigvecs = np.linalg.eig(curr_matrix)
        max_idx = np.argmax(eigvals)
        w = eigvecs[:, max_idx].real
        w = w / w.sum()
        perfect_matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                if w[j] != 0:
                    val = w[i] / w[j]
                    if val > max_scale: val = max_scale
                    if val < 1/max_scale: val = 1/max_scale
                    perfect_matrix[i][j] = val
                else:
                    perfect_matrix[i][j] = 1.0
        alpha = 0.8 
        curr_matrix = alpha * curr_matrix + (1 - alpha) * perfect_matrix
        for i in range(n):
            for j in range(n):
                if curr_matrix[i][j] > max_scale: curr_matrix[i][j] = max_scale
                if curr_matrix[i][j] < 1/max_scale: curr_matrix[i][j] = 1/max_scale
        for i in range(n):
            curr_matrix[i][i] = 1.0
            for j in range(i+1, n):
                curr_matrix[j][i] = 1.0 / curr_matrix[i][j]
    return curr_matrix

def calculate_ahp_metrics(comparisons, do_calibration=False, cr_limit=0.1, max_scale=5.0):
    norm_comps = {}
    items = set()
    for pair, val in comparisons.items():
        if " vs " in pair:
            a, b = pair.split(" vs ")
            a, b = a.strip(), b.strip()
            items.add(a); items.add(b)
            norm_comps[f"{a} vs {b}"] = float(val)
    items = sorted(list(items))
    n = len(items)
    item_map = {name: i for i, name in enumerate(items)}
    matrix = np.ones((n, n))
    for pair, val in norm_comps.items():
        try:
            a, b = pair.split(" vs ")
            if a in item_map and b in item_map:
                i, j = item_map[a], item_map[b]
                matrix[i][j] = val
                matrix[j][i] = 1 / val
        except: continue
    original_cr = get_cr(matrix, n)
    final_cr = original_cr
    was_calibrated = False
    if original_cr > cr_limit and do_calibration:
        matrix = calibrate_matrix(matrix, target_cr=cr_limit, max_scale=max_scale)
        final_cr = get_cr(matrix, n)
        was_calibrated = True
    try:
        eigvals, eigvecs = np.linalg.eig(matrix)
        max_idx = np.argmax(eigvals)
        weights = eigvecs[:, max_idx].real
        weights = weights / weights.sum()
    except:
        weights = np.ones(n) / n
    return items, weights, final_cr, was_calibrated

# ==============================================================================
# [UI] 사이드바
# ==============================================================================
with st.sidebar:
    st.header("🔑 관리자 메뉴")
    user_key = st.text_input("프로젝트 비밀번호", type="password")
    st.divider()
    st.subheader("🎛️ 분석 옵션")
    auto_calibrate = st.checkbox("✨ 데이터 자동 보정", value=True)
    cr_threshold = st.slider("CR 허용 기준", 0.05, 0.5, 0.1, 0.05)
    max_scale_val = st.number_input("최대 배수 제한", value=5.0, min_value=3.0, max_value=9.0)

if not user_key:
    st.info("👈 사이드바에 비밀번호를 입력하세요.")
    st.stop()

# 파일 목록 및 구글 복구 버튼
all_files = [f for f in os.listdir(DATA_FOLDER) if f.endswith(".csv")]
my_files = [f for f in all_files if f.startswith(f"{user_key}_")]

st.sidebar.divider()
if st.sidebar.button("☁️ 구글 클라우드에서 복구"):
    cloud_df = load_from_google_cloud(user_key)
    if not cloud_df.empty:
        st.session_state['cloud_data'] = cloud_df
        st.success("✅ 클라우드 데이터를 불러왔습니다.")
    else:
        st.error("클라우드에 데이터가 없습니다.")

# ==============================================================================
# [메인] 데이터 로드 (인코딩 에러 및 들여쓰기 교정 완료)
# ==============================================================================
raw_df = pd.DataFrame()

if my_files:
    selected_file = st.selectbox("📂 로컬 프로젝트 선택", my_files)
    if selected_file:
        file_path = os.path.join(DATA_FOLDER, selected_file)
        try:
            # 1순위: UTF-8 시도
            raw_df = pd.read_csv(file_path, encoding='utf-8-sig')
        except UnicodeDecodeError:
            # 2순위: CP949 시도 (엑셀 저장 파일용)
            raw_df = pd.read_csv(file_path, encoding='cp949')
        st.markdown(f"### 📄 프로젝트: **{selected_file.replace(user_key+'_', '').replace('.csv', '')}**")
elif 'cloud_data' in st.session_state:
    raw_df = st.session_state['cloud_data']
    st.markdown(f"### 📄 클라우드 복구 데이터 (총 {len(raw_df)}건)")
else:
    st.error("데이터가 없습니다. [☁️ 구글 클라우드에서 복구]를 눌러보세요.")
    st.stop()

# ==============================================================================
# [메인] 데이터 처리 및 출력 (기존 로직 유지)
# ==============================================================================
if not raw_df.empty:
    processed_data = []
    valid_weights = []
    task_crs = {}
    calibrated_count = 0
    progress_bar = st.progress(0)
    
    for idx, row in raw_df.iterrows():
        try:
            survey_dict = json.loads(row['Raw_Data'])
            tasks = {}
            for k, v in survey_dict.items():
                if "]" in k:
                    split_idx = k.rfind("]")
                    task_name = k[1:split_idx]
                    pair = k[split_idx+1:].strip()
                    if task_name not in tasks: tasks[task_name] = {}
                    tasks[task_name][pair] = v
            
            is_valid = True
            resp_weights = {}
            resp_crs = {}
            is_resp_calibrated = False
            
            for t_name, comps in tasks.items():
                items, w, cr, calib = calculate_ahp_metrics(
                    comps, do_calibration=auto_calibrate, 
                    cr_limit=cr_threshold, max_scale=max_scale_val
                )
                if cr > cr_threshold: is_valid = False
                if calib: is_resp_calibrated = True
                resp_crs[t_name] = cr
                for i, item in enumerate(items):
                    resp_weights[f"{t_name}|{item}"] = w[i]
                if is_valid:
                    if t_name not in task_crs: task_crs[t_name] = []
                    task_crs[t_name].append(cr)
            
            status = "Valid"
            if not is_valid: status = "Invalid"
            elif is_resp_calibrated: status = "Calibrated"
            if is_resp_calibrated and is_valid: calibrated_count += 1
            
            processed_data.append({
                "Respondent": row['Respondent'], "Time": row['Time'],
                "Status": status, "Is_Valid": is_valid,
                "CR_Details": str(resp_crs), **resp_weights
            })
            if is_valid: valid_weights.append(resp_weights)
        except: continue
        progress_bar.progress((idx + 1) / len(raw_df))
    progress_bar.empty()

    if not valid_weights:
        st.error("유효한 데이터가 없습니다."); st.stop()

    valid_df = pd.DataFrame(valid_weights); full_log_df = pd.DataFrame(processed_data)
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 응답", f"{len(processed_data)}명")
    c2.metric("✅ 유효 데이터", f"{len(valid_weights)}명")
    c3.metric("✨ 5점척도 보정", f"{calibrated_count}명")
    c4.metric("❌ 제외됨", f"{len(processed_data) - len(valid_weights)}명")

    avg_weights = valid_df.mean()
    tasks_unique = sorted(list(set([k.split("|")[0] for k in avg_weights.index])))
    if tasks_unique:
        main_task = tasks_unique[0]; sub_tasks = tasks_unique[1:]; final_rows = []
        def get_avg_cr(task_name): return np.mean(task_crs[task_name]) if task_name in task_crs else 0.0
        
        main_cr = get_avg_cr(main_task)
        main_items = [{"name": k.split("|")[1], "w": avg_weights[k]} for k in avg_weights.index if k.startswith(main_task)]
        main_items.sort(key=lambda x: x['w'], reverse=True)

        for m in main_items:
            match_sub = next((s for s in sub_tasks if is_match(m['name'], s)), None)
            if match_sub:
                sub_cr = get_avg_cr(match_sub)
                s_keys = [k for k in avg_weights.index if k.startswith(match_sub)]
                subs = [{"n": k.split("|")[1], "w": avg_weights[k]} for k in s_keys]
                subs.sort(key=lambda x: (m['w'] * x['w']), reverse=True)
                for i, s in enumerate(subs):
                    final_rows.append({
                        "대항목명": m['name'] if i == 0 else "", "대항목 가중치": m['w'] if i == 0 else None,
                        "소항목명": s['n'], "소항목 가중치": s['w'], "종합 가중치": m['w'] * s['w'],
                        "그룹 CR": sub_cr, "순위": 0
                    })
            else:
                final_rows.append({
                    "대항목명": m['name'], "대항목 가중치": m['w'], "소항목명": "-", 
                    "소항목 가중치": None, "종합 가중치": m['w'], "그룹 CR": main_cr, "순위": 0
                })

        report_df = pd.DataFrame(final_rows)
        report_df['순위'] = report_df['종합 가중치'].rank(ascending=False, method='min').astype(int)
        
        st.subheader("🏆 최종 가중치 및 순위 리포트")
        st.info(f"📌 **1단계(대항목) 평균 CR:** {main_cr:.4f}")
        
        display_df = report_df.copy()
        for c in ["대항목 가중치", "소항목 가중치", "종합 가중치", "그룹 CR"]:
            display_df[c] = display_df[c].apply(lambda x: f"{x:.4f}" if pd.notnull(x) else "")
        display_df["순위"] = display_df["순위"].apply(lambda x: f"{x}위")
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            display_df.to_excel(writer, sheet_name='1_최종_분석_결과', index=False)
            raw_df.to_excel(writer, sheet_name='2_전체_원본_데이터', index=False)
        st.download_button("📥 엑셀 리포트 다운로드", output.getvalue(), "Report_AHP.xlsx", "primary")

    st.divider()
    with st.expander("🗑️ 데이터 삭제"):
        if st.button("현재 데이터 영구 삭제"):
            if 'selected_file' in locals() and os.path.exists(file_path):
                os.remove(file_path); st.rerun()
