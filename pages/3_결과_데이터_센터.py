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
# [함수] AHP 핵심 엔진 (수정 가중치 & CR 계산)
# ==============================================================================
def calculate_ahp_metrics(comparisons):
    """
    입력: {"A vs B": 3, ...} 형태의 딕셔너리
    출력: (항목 리스트, 가중치 배열, CR 값)
    """
    # 1. 항목 추출 및 매핑
    items = set()
    for pair in comparisons.keys():
        if " vs " in pair:
            a, b = pair.split(" vs ")
            items.add(a); items.add(b)
    items = sorted(list(items))
    n = len(items)
    item_map = {name: i for i, name in enumerate(items)}

    # 2. 행렬 생성
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

    # 3. 수정 가중치 계산 (고유벡터법 - Eigenvector Method)
    try:
        eigvals, eigvecs = np.linalg.eig(matrix)
        max_idx = np.argmax(eigvals)
        max_eigval = eigvals[max_idx].real
        weights = eigvecs[:, max_idx].real
        weights = weights / weights.sum() # 정규화
    except:
        # 예외 처리: 기하평균법
        weights = np.ones(n)
        for i in range(n):
            weights[i] = np.prod(matrix[i]) ** (1/n)
        weights = weights / weights.sum()
        max_eigval = n

    # 4. CR(일관성 비율) 계산
    ri_table = {1: 0, 2: 0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45}
    ci = (max_eigval - n) / (n - 1) if n > 1 else 0
    ri = ri_table.get(n, 1.49)
    cr = ci / ri if ri != 0 else 0

    return items, weights, cr

# ==============================================================================
# [UI] 사이드바 인증 및 파일 선택 (자동 연동)
# ==============================================================================
with st.sidebar:
    st.header("🔑 접속 인증")
    user_key = st.text_input("프로젝트 비밀번호(Key)", type="password")

if not user_key:
    st.info("👈 사이드바에 **프로젝트 비밀번호**를 입력하면 데이터가 자동 로드됩니다.")
    st.stop()

# 파일 자동 탐색
all_files = [f for f in os.listdir(DATA_FOLDER) if f.endswith(".csv")]
my_files = [f for f in all_files if f.startswith(f"{user_key}_")]

if not my_files:
    st.error(f"비밀번호 '{user_key}'로 시작하는 데이터를 찾을 수 없습니다.")
    st.stop()

st.sidebar.success(f"인증 성공! {len(my_files)}개의 데이터 발견")
selected_file = st.selectbox("📂 분석할 프로젝트 선택", my_files)

# ==============================================================================
# [메인] 데이터 처리 및 리포트 생성
# ==============================================================================
if selected_file:
    file_path = os.path.join(DATA_FOLDER, selected_file)
    raw_df = pd.read_csv(file_path)
    
    st.markdown(f"### 📄 프로젝트: **{selected_file.replace(user_key+'_', '').replace('.csv', '')}**")
    
    # 분석용 컨테이너
    processed_data = [] # 모든 응답자의 상세 분석 정보
    valid_weights = []  # 유효한 응답자들의 가중치 모음
    
    progress_bar = st.progress(0)
    
    for idx, row in raw_df.iterrows():
        try:
            # JSON 파싱
            survey_dict = json.loads(row['Raw_Data'])
            respondent = row['Respondent']
            
            # 태스크별 분류
            tasks = {}
            for k, v in survey_dict.items():
                # k: "[TaskName] A vs B"
                if "]" in k:
                    task_name = k.split("]")[0].replace("[", "")
                    pair = k.split("]")[1].strip()
                    if task_name not in tasks: tasks[task_name] = {}
                    tasks[task_name][pair] = v
            
            # 응답자별 분석
            is_valid_respondent = True
            resp_weights = {} # 이 사람의 모든 항목 가중치
            resp_crs = {}     # 이 사람의 태스크별 CR
            
            for t_name, comps in tasks.items():
                items, w, cr = calculate_ahp_metrics(comps)
                
                # CR 체크 (하나라도 0.1 넘으면 이 사람 데이터는 무효)
                if cr > 0.1:
                    is_valid_respondent = False
                
                resp_crs[t_name] = cr
                for i, item in enumerate(items):
                    # Key: "TaskName|ItemName"
                    resp_weights[f"{t_name}|{item}"] = w[i]
            
            # 데이터 저장
            processed_data.append({
                "Respondent": respondent,
                "Time": row['Time'],
                "Is_Valid": is_valid_respondent,
                "CR_Details": str(resp_crs),
                **resp_weights # Flatten weights
            })
            
            if is_valid_respondent:
                valid_weights.append(resp_weights)
                
        except Exception as e:
            st.warning(f"데이터 처리 중 일부 오류 (Row {idx}): {e}")
            
        progress_bar.progress((idx + 1) / len(raw_df))
    
    progress_bar.empty()
    
    # --------------------------------------------------------------------------
    # 2. 데이터 분류 (유효 vs 무효)
    # --------------------------------------------------------------------------
    full_df = pd.DataFrame(processed_data)
    valid_df = pd.DataFrame(valid_weights) 
    invalid_rows = full_df[full_df['Is_Valid'] == False] if not full_df.empty else pd.DataFrame()
    
    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("총 응답자", f"{len(full_df)}명")
    m2.metric("✅ 유효 데이터 (분석 활용)", f"{len(valid_weights)}명")
    m3.metric("❌ 제외된 데이터 (CR > 0.1)", f"{len(invalid_rows)}명", 
              help="논리적 일관성이 부족하여 평균 계산에서 제외됩니다.")

    if len(valid_weights) == 0:
        st.error("분석할 수 있는 유효한 데이터가 없습니다. (모든 데이터가 CR > 0.1)")
        st.stop()

    # --------------------------------------------------------------------------
    # 3. 최종 가중치 및 순위 산출 (산술 평균 & 계층 구조)
    # --------------------------------------------------------------------------
    avg_weights = valid_df.mean()
    
    tasks_unique = set([k.split("|")[0] for k in avg_weights.index])
    sorted_tasks = sorted(list(tasks_unique))
    
    # [1. 대항목] 처럼 숫자가 있는 경우 정렬됨
    main_task = sorted_tasks[0] 
    sub_tasks = sorted_tasks[1:]
    
    final_report = []
    
    main_items = [k for k in avg_weights.index if k.startswith(main_task)]
    
    for m_key in main_items:
        m_name = m_key.split("|")[1]
        m_weight = avg_weights[m_key]
        
        # 1. 대항목 행 추가
        final_report.append({
            "구분": "대항목",
            "대항목명": m_name,
            "소항목명": "-",
            "대항목 가중치": m_weight,
            "소항목 가중치": 0, 
            "최종 가중치": m_weight,
            "순위": 0 
        })
        
        # 2. 이 대항목에 속하는 소항목 찾기
        matching_sub_task = None
        for st_name in sub_tasks:
            if m_name in st_name:
                matching_sub_task = st_name
                break
        
        if matching_sub_task:
            sub_items = [k for k in avg_weights.index if k.startswith(matching_sub_task)]
            
            temp_subs = []
            for s_key in sub_items:
                s_name = s_key.split("|")[1]
                s_weight = avg_weights[s_key] 
                global_w = m_weight * s_weight 
                temp_subs.append({
                    "구분": "소항목",
                    "대항목명": m_name,
                    "소항목명": s_name,
                    "대항목 가중치": m_weight,
                    "소항목 가중치": s_weight,
                    "최종 가중치": global_w
                })
            
            # 내림차순 정렬
            temp_subs.sort(key=lambda x: x["최종 가중치"], reverse=True)
            final_report.extend(temp_subs)

    report_df = pd.DataFrame(final_report)
    
    # 순위 매기기
    sub_mask = report_df['구분'] == '소항목'
    if sub_mask.any():
        report_df.loc[sub_mask, '순위'] = report_df.loc[sub_mask, '최종 가중치'].rank(ascending=False).astype(int)
    
    main_mask = report_df['구분'] == '대항목'
    if main_mask.any():
        report_df.loc[main_mask, '순위'] = report_df.loc[main_mask, '최종 가중치'].rank(ascending=False).astype(int)

    # --------------------------------------------------------------------------
    # 4. 화면 출력
    # --------------------------------------------------------------------------
    st.subheader("🏆 최종 가중치 및 순위 리포트")
    st.caption("수정 가중치(Corrected Weight) 적용 및 산술 평균(AIP) 집계 결과")
    
    display_df = report_df.copy()
    
    cols_to_format = ["대항목 가중치", "소항목 가중치", "최종 가중치"]
    for c in cols_to_format:
        display_df[c] = display_df[c].apply(lambda x: f"{x:.4f}" if x > 0 else "")
        
    display_df['순위'] = display_df['순위'].apply(lambda x: f"{int(x)}위")
    
    display_df.loc[display_df['구분'] == '대항목', '소항목 가중치'] = ""
    display_df.loc[display_df['구분'] == '대항목', '소항목명'] = ""
    
    final_cols = ["구분", "대항목명", "소항목명", "대항목 가중치", "소항목 가중치", "최종 가중치", "순위"]
    st.dataframe(display_df[final_cols], use_container_width=True, hide_index=True)
    
    # --------------------------------------------------------------------------
    # 5. Excel 다운로드 (엔진 변경: openpyxl)
    # --------------------------------------------------------------------------
    output = io.BytesIO()
    # [수정됨] xlsxwriter 대신 openpyxl 사용 (requirements.txt 호환)
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        display_df[final_cols].to_excel(writer, sheet_name='1_최종_분석_결과', index=False)
        raw_df.to_excel(writer, sheet_name='2_전체_원본_데이터', index=False)
        if not invalid_rows.empty:
            invalid_export = invalid_rows[["Respondent", "Time", "CR_Details"]]
            invalid_export.to_excel(writer, sheet_name='3_제외된_데이터_오류목록', index=False)
    
    output.seek(0)
    
    st.download_button(
        label="📥 전체 결과 엑셀 다운로드",
        data=output,
        file_name=f"AHP_Result_{selected_file.replace('.csv','')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )

    # --------------------------------------------------------------------------
    # 6. 관리 기능 (삭제)
    # --------------------------------------------------------------------------
    st.divider()
    with st.expander("🗑️ 데이터 관리 (주의)"):
        if st.button("현재 프로젝트 데이터 삭제"):
            os.remove(file_path)
            st.success("삭제되었습니다. 새로고침하세요.")
            st.rerun()
