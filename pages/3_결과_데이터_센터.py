import streamlit as st
import pandas as pd
import numpy as np
import json
import io
import os

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
# [함수] AHP 핵심 엔진
# ==============================================================================
def calculate_ahp_metrics(comparisons):
    """
    입력: {"A vs B": 3, ...}
    출력: (항목 리스트, 가중치 배열, CR 값)
    """
    items = set()
    for pair in comparisons.keys():
        if " vs " in pair:
            a, b = pair.split(" vs ")
            items.add(a); items.add(b)
    items = sorted(list(items))
    n = len(items)
    item_map = {name: i for i, name in enumerate(items)}

    matrix = np.ones((n, n))
    for pair, val in comparisons.items():
        try:
            if " vs " in pair:
                a, b = pair.split(" vs ")
                val = float(val)
                if a in item_map and b in item_map:
                    i, j = item_map[a], item_map[b]
                    matrix[i][j] = val
                    matrix[j][i] = 1 / val
        except: continue

    try:
        eigvals, eigvecs = np.linalg.eig(matrix)
        max_idx = np.argmax(eigvals)
        max_eigval = eigvals[max_idx].real
        weights = eigvecs[:, max_idx].real
        weights = weights / weights.sum()
    except:
        weights = np.ones(n)
        for i in range(n):
            weights[i] = np.prod(matrix[i]) ** (1/n)
        weights = weights / weights.sum()
        max_eigval = n

    ri_table = {1: 0, 2: 0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45}
    ci = (max_eigval - n) / (n - 1) if n > 1 else 0
    ri = ri_table.get(n, 1.49)
    cr = ci / ri if ri != 0 else 0

    return items, weights, cr

# ==============================================================================
# [UI] 사이드바 인증 및 파일 선택
# ==============================================================================
with st.sidebar:
    st.header("🔑 접속 인증")
    user_key = st.text_input("프로젝트 비밀번호(Key)", type="password")

if not user_key:
    st.info("👈 사이드바에 **프로젝트 비밀번호**를 입력하세요.")
    st.stop()

all_files = [f for f in os.listdir(DATA_FOLDER) if f.endswith(".csv")]
my_files = [f for f in all_files if f.startswith(f"{user_key}_")]

if not my_files:
    st.error("해당 비밀번호의 데이터를 찾을 수 없습니다.")
    st.stop()

st.sidebar.success(f"인증 성공! {len(my_files)}개 발견")
selected_file = st.selectbox("📂 분석할 프로젝트 선택", my_files)

# ==============================================================================
# [메인] 데이터 처리 및 리포트 생성
# ==============================================================================
if selected_file:
    file_path = os.path.join(DATA_FOLDER, selected_file)
    raw_df = pd.read_csv(file_path)
    
    st.markdown(f"### 📄 프로젝트: **{selected_file.replace(user_key+'_', '').replace('.csv', '')}**")
    
    processed_data = []
    valid_weights = []
    
    progress_bar = st.progress(0)
    
    for idx, row in raw_df.iterrows():
        try:
            survey_dict = json.loads(row['Raw_Data'])
            
            tasks = {}
            for k, v in survey_dict.items():
                if "]" in k:
                    task_name = k.split("]")[0].replace("[", "")
                    pair = k.split("]")[1].strip()
                    if task_name not in tasks: tasks[task_name] = {}
                    tasks[task_name][pair] = v
            
            is_valid = True
            resp_weights = {}
            resp_crs = {}
            
            for t_name, comps in tasks.items():
                items, w, cr = calculate_ahp_metrics(comps)
                if cr > 0.1: is_valid = False
                resp_crs[t_name] = cr
                for i, item in enumerate(items):
                    resp_weights[f"{t_name}|{item}"] = w[i]
            
            processed_data.append({
                "Respondent": row['Respondent'],
                "Time": row['Time'],
                "Is_Valid": is_valid,
                "CR_Details": str(resp_crs),
                **resp_weights
            })
            
            if is_valid: valid_weights.append(resp_weights)
                
        except Exception: continue
        progress_bar.progress((idx + 1) / len(raw_df))
    
    progress_bar.empty()
    
    # --------------------------------------------------------------------------
    # 2. 결과 집계 (AIP)
    # --------------------------------------------------------------------------
    valid_df = pd.DataFrame(valid_weights)
    invalid_rows = pd.DataFrame(processed_data)
    if not invalid_rows.empty:
        invalid_rows = invalid_rows[invalid_rows['Is_Valid'] == False]

    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("총 응답자", f"{len(processed_data)}명")
    c2.metric("✅ 유효 데이터", f"{len(valid_weights)}명")
    c3.metric("❌ 제외된 데이터 (CR>0.1)", f"{len(invalid_rows)}명")

    if len(valid_weights) == 0:
        st.error("유효한 데이터가 없어 분석할 수 없습니다.")
        st.stop()

    avg_weights = valid_df.mean()
    
    # 구조 파싱
    tasks_unique = sorted(list(set([k.split("|")[0] for k in avg_weights.index])))
    main_task = tasks_unique[0] # [1. 메인...] 가정
    sub_tasks = tasks_unique[1:]
    
    # [핵심] 리포트용 리스트 생성
    final_rows = []
    
    # 메인 항목
    main_items_keys = [k for k in avg_weights.index if k.startswith(main_task)]
    
    # 대항목을 가중치 순으로 정렬 (보기 좋게)
    main_items_data = []
    for k in main_items_keys:
        main_items_data.append({"key": k, "name": k.split("|")[1], "weight": avg_weights[k]})
    main_items_data.sort(key=lambda x: x['weight'], reverse=True)

    # 전체 소항목 데이터를 미리 수집하여 순위 산정
    all_sub_items = []
    
    for m_item in main_items_data:
        m_name = m_item['name']
        m_weight = m_item['weight']
        
        # 소항목 찾기 (매칭 로직 강화)
        matching_sub_task = None
        for st_name in sub_tasks:
            if m_name in st_name: # 이름이 포함되어 있으면 매칭
                matching_sub_task = st_name
                break
        
        if matching_sub_task:
            sub_keys = [k for k in avg_weights.index if k.startswith(matching_sub_task)]
            
            # 소항목 임시 저장 (정렬용)
            temp_subs = []
            for s_key in sub_keys:
                s_name = s_key.split("|")[1]
                s_weight = avg_weights[s_key]
                global_w = m_weight * s_weight
                temp_subs.append({
                    "s_name": s_name, 
                    "s_weight": s_weight, 
                    "global_w": global_w
                })
            
            # 소항목 가중치 순 정렬
            temp_subs.sort(key=lambda x: x['global_w'], reverse=True)
            
            # 행 추가
            for i, sub in enumerate(temp_subs):
                all_sub_items.append(sub['global_w']) # 순위 산정을 위해 수집
                
                final_rows.append({
                    "대항목명": m_name if i == 0 else "",      # 첫 줄만 표시
                    "대항목 가중치": m_weight if i == 0 else None, # 첫 줄만 표시
                    "소항목명": sub['s_name'],
                    "소항목 가중치": sub['s_weight'],
                    "종합 가중치": sub['global_w'],
                    "SortKey": sub['global_w'] # 정렬 키
                })
        else:
            # 소항목이 없는 경우 (대항목만 존재)
            final_rows.append({
                "대항목명": m_name,
                "대항목 가중치": m_weight,
                "소항목명": "-",
                "소항목 가중치": None,
                "종합 가중치": m_weight,
                "SortKey": m_weight
            })

    # 전체 리스트 DF 변환
    report_df = pd.DataFrame(final_rows)
    
    # [순위 산정] 종합 가중치를 기준으로 전체 순위 매기기
    # 소항목이 있는 행만 대상으로 순위 매김
    report_df['순위'] = report_df['종합 가중치'].rank(ascending=False).astype(int)
    
    # --------------------------------------------------------------------------
    # 3. 화면 출력 (요청하신 레이아웃)
    # --------------------------------------------------------------------------
    st.subheader("🏆 최종 가중치 및 순위 리포트")
    
    display_cols = ["대항목명", "대항목 가중치", "소항목명", "소항목 가중치", "종합 가중치", "순위"]
    display_df = report_df[display_cols].copy()
    
    # 포맷팅 함수
    def fmt(x): return f"{x:.4f}" if pd.notnull(x) and x != "" else ""
    
    display_df["대항목 가중치"] = display_df["대항목 가중치"].apply(fmt)
    display_df["소항목 가중치"] = display_df["소항목 가중치"].apply(fmt)
    display_df["종합 가중치"] = display_df["종합 가중치"].apply(fmt)
    display_df["순위"] = display_df["순위"].apply(lambda x: f"{x}위")
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # --------------------------------------------------------------------------
    # 4. Excel 다운로드
    # --------------------------------------------------------------------------
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        display_df.to_excel(writer, sheet_name='1_최종_분석_결과', index=False)
        raw_df.to_excel(writer, sheet_name='2_전체_원본_데이터', index=False)
        if not invalid_rows.empty:
            invalid_rows[["Respondent", "Time", "CR_Details"]].to_excel(writer, sheet_name='3_제외된_데이터_오류목록', index=False)
            
    st.download_button(
        label="📥 엑셀 리포트 다운로드",
        data=output.getvalue(),
        file_name=f"AHP_Report_{selected_file.replace('.csv','')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )

    # --------------------------------------------------------------------------
    # 5. 삭제 기능
    # --------------------------------------------------------------------------
    st.divider()
    with st.expander("🗑️ 데이터 삭제"):
        if st.button("현재 데이터 영구 삭제"):
            os.remove(file_path)
            st.success("삭제되었습니다.")
            st.rerun()
