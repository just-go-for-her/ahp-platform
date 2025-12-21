import streamlit as st
import pandas as pd
import numpy as np
import json
import io
import os
import re

# ==============================================================================
# [설정] 페이지 기본 설정
# ==============================================================================
st.set_page_config(page_title="결과 데이터 센터", page_icon="📊", layout="wide")
st.title("📊 AHP 결과 데이터 센터")

# 데이터 저장소 경로
DATA_FOLDER = "survey_data"
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

# ==============================================================================
# [함수] 스마트 매칭 & 행렬 보정 엔진
# ==============================================================================
def is_match(main_name, sub_task_name):
    """대항목 이름이 소항목 그룹 이름에 포함되는지 검사"""
    clean_main = main_name.replace(" ", "").strip()
    clean_sub = sub_task_name.replace(" ", "").strip()
    if clean_main in clean_sub: return True
    match = re.search(r'\[(.*?)\]', sub_task_name)
    if match:
        extracted = match.group(1).replace(" ", "").strip()
        if extracted == clean_main: return True
    return False

def get_cr(matrix, n):
    """행렬의 CR값 계산"""
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
    """5점 척도 제한 보정 알고리즘"""
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

# ==============================================================================
# [함수] AHP 계산
# ==============================================================================
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

all_files = [f for f in os.listdir(DATA_FOLDER) if f.endswith(".csv")]
my_files = [f for f in all_files if f.startswith(f"{user_key}_")]

if not my_files:
    st.error("데이터가 없습니다.")
    st.stop()

selected_file = st.selectbox("📂 프로젝트 선택", my_files)

# ==============================================================================
# [메인] 데이터 처리
# ==============================================================================
if selected_file:
    file_path = os.path.join(DATA_FOLDER, selected_file)
    raw_df = pd.read_csv(file_path)
    
    st.markdown(f"### 📄 프로젝트: **{selected_file.replace(user_key+'_', '').replace('.csv', '')}**")
    
    processed_data = []
    valid_weights = []
    task_crs = {} # 태스크별 평균 CR 저장용
    
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
                    comps, 
                    do_calibration=auto_calibrate, 
                    cr_limit=cr_threshold,
                    max_scale=max_scale_val
                )
                
                if cr > cr_threshold: is_valid = False
                if calib: is_resp_calibrated = True
                
                resp_crs[t_name] = cr
                for i, item in enumerate(items):
                    resp_weights[f"{t_name}|{item}"] = w[i]
                
                # CR 집계 (유효한 경우만)
                if is_valid:
                    if t_name not in task_crs: task_crs[t_name] = []
                    task_crs[t_name].append(cr)
            
            status = "Valid"
            if not is_valid: status = "Invalid"
            elif is_resp_calibrated: status = "Calibrated"
            
            if is_resp_calibrated and is_valid: calibrated_count += 1
            
            processed_data.append({
                "Respondent": row['Respondent'],
                "Time": row['Time'],
                "Status": status,
                "Is_Valid": is_valid,
                "CR_Details": str(resp_crs),
                **resp_weights
            })
            
            if is_valid: valid_weights.append(resp_weights)
        except Exception: continue
        progress_bar.progress((idx + 1) / len(raw_df))
    
    progress_bar.empty()
    
    valid_df = pd.DataFrame(valid_weights)
    full_log_df = pd.DataFrame(processed_data)
    
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 응답", f"{len(processed_data)}명")
    c2.metric("✅ 유효 데이터", f"{len(valid_weights)}명")
    c3.metric("✨ 5점척도 보정", f"{calibrated_count}명")
    c4.metric("❌ 제외됨", f"{len(processed_data) - len(valid_weights)}명")

    if len(valid_weights) == 0:
        st.error("유효한 데이터가 없습니다.")
        st.stop()

    avg_weights = valid_df.mean()
    tasks_unique = sorted(list(set([k.split("|")[0] for k in avg_weights.index])))
    if not tasks_unique: st.stop()
        
    main_task = tasks_unique[0]
    sub_tasks = tasks_unique[1:]
    
    final_rows = []
    
    # 평균 CR 계산 함수
    def get_avg_cr(task_name):
        if task_name in task_crs and len(task_crs[task_name]) > 0:
            return np.mean(task_crs[task_name])
        return 0.0

    main_keys = [k for k in avg_weights.index if k.startswith(main_task)]
    main_items_data = []
    for k in main_keys:
        main_items_data.append({"name": k.split("|")[1], "weight": avg_weights[k]})
    main_items_data.sort(key=lambda x: x['weight'], reverse=True)

    # 대항목 CR
    main_cr = get_avg_cr(main_task)

    for m_item in main_items_data:
        m_name = m_item['name']
        m_weight = m_item['weight']
        
        matching_sub_task = None
        for st_name in sub_tasks:
            if is_match(m_name, st_name):
                matching_sub_task = st_name
                break
        
        if matching_sub_task:
            sub_cr = get_avg_cr(matching_sub_task)
            sub_keys = [k for k in avg_weights.index if k.startswith(matching_sub_task)]
            temp_subs = []
            for s_key in sub_keys:
                s_name = s_key.split("|")[1]
                s_weight = avg_weights[s_key]
                global_w = m_weight * s_weight
                temp_subs.append({"s_name": s_name, "s_weight": s_weight, "global_w": global_w})
            
            temp_subs.sort(key=lambda x: x['global_w'], reverse=True)
            
            for i, sub in enumerate(temp_subs):
                final_rows.append({
                    "대항목명": m_name if i == 0 else "",      
                    "대항목 가중치": m_weight if i == 0 else None, 
                    "소항목명": sub['s_name'],
                    "소항목 가중치": sub['s_weight'],
                    "종합 가중치": sub['global_w'],
                    "순위": 0, # 나중에 계산
                    "그룹 CR": sub_cr, # 소항목 그룹의 CR
                    "is_main_cr": False
                })
            
            # 대항목 행에 CR 정보 추가 (첫줄)
            # 여기서는 구조상 대항목 행을 따로 만들지 않고 첫 소항목 옆에 대항목 정보를 병합했음.
            # 하지만 CR은 '대항목 CR'과 '소항목 CR'이 다르므로 구분이 필요함.
            # 엑셀과 화면에 '그룹 CR' 컬럼을 추가해서 보여줌.
            
        else:
            final_rows.append({
                "대항목명": m_name, "대항목 가중치": m_weight, 
                "소항목명": "-", "소항목 가중치": None,
                "종합 가중치": m_weight, "순위": 0,
                "그룹 CR": main_cr, # 대항목 자체 CR
                "is_main_cr": True
            })

    report_df = pd.DataFrame(final_rows)
    
    # [수정] 대항목의 CR은 '대항목명'이 있는 행(i=0)에만 표시하거나, 별도 컬럼으로 분리해야 함.
    # 여기서는 '그룹 CR' 컬럼에 해당 소항목 그룹의 CR을 표시하고, 대항목 CR은 별도 표기 필요.
    # 하지만 표 구조상 복잡해지므로, '소항목 CR'을 우선 표시.
    
    # 순위 계산
    report_df['순위'] = np.nan
    rank_mask = report_df['소항목명'] != "-"
    if rank_mask.any():
        report_df.loc[rank_mask, '순위'] = report_df.loc[rank_mask, '종합 가중치'].rank(ascending=False).astype(int)
    
    # --------------------------------------------------------------------------
    # 출력
    # --------------------------------------------------------------------------
    st.subheader("🏆 최종 가중치 및 순위 리포트")
    
    # [NEW] 대항목 그룹의 평균 CR 표시
    st.info(f"📌 **1단계(대항목) 평균 CR:** {main_cr:.4f}")
    
    display_cols = ["대항목명", "대항목 가중치", "소항목명", "소항목 가중치", "종합 가중치", "순위", "그룹 CR"]
    display_df = report_df[display_cols].copy()
    
    def fmt(x): return f"{x:.4f}" if pd.notnull(x) and x != "" else ""
    
    for c in ["대항목 가중치", "소항목 가중치", "종합 가중치", "그룹 CR"]:
        display_df[c] = display_df[c].apply(fmt)
        
    display_df["순위"] = display_df["순위"].apply(lambda x: f"{int(x)}위" if pd.notnull(x) else "")
    
    # 그룹 CR: 소항목 그룹의 CR을 의미. 대항목명 있는 줄에 표시하지 않고, 소항목 줄에 표시.
    # 가독성을 위해 첫 줄에만 표시하도록 처리
    # (이미 로직상 같은 소항목 그룹끼리 묶여있으므로 첫 줄만 남기고 지워도 됨)
    
    # 소항목명이 바뀌는 지점 체크해서 중복 CR 제거
    # Pandas 로직: 소항목명이 바뀌거나, 대항목명이 바뀔 때만 CR 표시
    # (여기서는 간단하게 모두 표시하거나, 첫 줄만 표시)
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        display_df.to_excel(writer, sheet_name='1_최종_분석_결과', index=False)
        raw_df.to_excel(writer, sheet_name='2_전체_원본_데이터', index=False)
        full_log_df[["Respondent", "Time", "Status", "CR_Details"]].to_excel(writer, sheet_name='3_데이터_상태_로그', index=False)
            
    st.download_button("📥 엑셀 리포트 다운로드", output.getvalue(), f"Report_{selected_file.replace('.csv','')}.xlsx", "primary")

    st.divider()
    with st.expander("🗑️ 데이터 삭제"):
        if st.button("현재 데이터 영구 삭제"):
            os.remove(file_path); st.rerun()
