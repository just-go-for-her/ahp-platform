import streamlit as st
import pandas as pd
import numpy as np
import json
import io

# ==============================================================================
# [설정] 페이지 기본 설정
# ==============================================================================
st.set_page_config(page_title="결과 데이터 센터", page_icon="📊", layout="wide")
st.title("📊 AHP 결과 데이터 센터")

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
        a, b = pair.split(" vs ")
        items.add(a); items.add(b)
    items = sorted(list(items))
    n = len(items)
    item_map = {name: i for i, name in enumerate(items)}

    # 2. 행렬 생성
    matrix = np.ones((n, n))
    for pair, val in comparisons.items():
        try:
            a, b = pair.split(" vs ")
            val = float(val)
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
# [메인] 데이터 처리 및 리포트 생성
# ==============================================================================

# 1. 파일 업로드
uploaded_file = st.file_uploader("📂 수집된 CSV 파일을 업로드하세요", type=["csv"])

if uploaded_file:
    raw_df = pd.read_csv(uploaded_file)
    
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
            st.error(f"데이터 처리 중 오류 발생 (Row {idx}): {e}")
            
        progress_bar.progress((idx + 1) / len(raw_df))
    
    progress_bar.empty()
    
    # --------------------------------------------------------------------------
    # 2. 데이터 분류 (유효 vs 무효)
    # --------------------------------------------------------------------------
    full_df = pd.DataFrame(processed_data)
    valid_df = pd.DataFrame(valid_weights) # 가중치만 모은 DF (평균 계산용)
    invalid_rows = full_df[full_df['Is_Valid'] == False]
    
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
    # 항목별 산술 평균 (Group Decision Making의 표준: AIP)
    avg_weights = valid_df.mean()
    
    # 구조 파싱 (Main vs Sub)
    # 태스크 이름 정렬 -> 보통 [1. 메인], [2. 서브] 순서임
    tasks_unique = set([k.split("|")[0] for k in avg_weights.index])
    sorted_tasks = sorted(list(tasks_unique))
    
    main_task = sorted_tasks[0] # 첫 번째 태스크를 대항목으로 가정
    sub_tasks = sorted_tasks[1:] # 나머지를 소항목으로 가정
    
    final_report = []
    
    # 메인 항목 찾기 및 정렬
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
            "소항목 가중치": 0, # 시각적으로 비움
            "최종 가중치": m_weight,
            "순위": 0 # 대항목 순위는 별도
        })
        
        # 2. 이 대항목에 속하는 소항목 찾기
        matching_sub_task = None
        for st_name in sub_tasks:
            # 태스크 이름에 대항목 이름이 포함되어 있는지 확인 (예: "2. [가격] 세부")
            if m_name in st_name:
                matching_sub_task = st_name
                break
        
        if matching_sub_task:
            sub_items = [k for k in avg_weights.index if k.startswith(matching_sub_task)]
            
            # 소항목들만 임시 저장해서 정렬
            temp_subs = []
            for s_key in sub_items:
                s_name = s_key.split("|")[1]
                s_weight = avg_weights[s_key] # 소항목 내 로컬 가중치
                global_w = m_weight * s_weight # 글로벌 가중치 계산
                temp_subs.append({
                    "구분": "소항목",
                    "대항목명": m_name,
                    "소항목명": s_name,
                    "대항목 가중치": m_weight,
                    "소항목 가중치": s_weight,
                    "최종 가중치": global_w
                })
            
            # 최종 가중치 기준 내림차순 정렬하여 추가
            temp_subs.sort(key=lambda x: x["최종 가중치"], reverse=True)
            final_report.extend(temp_subs)

    report_df = pd.DataFrame(final_report)
    
    # --------------------------------------------------------------------------
    # 4. 순위 매기기 및 포맷팅
    # --------------------------------------------------------------------------
    # 소항목 전체 순위 (Global Rank)
    sub_mask = report_df['구분'] == '소항목'
    if sub_mask.any():
        report_df.loc[sub_mask, '순위'] = report_df.loc[sub_mask, '최종 가중치'].rank(ascending=False).astype(int)
    
    # 대항목 순위
    main_mask = report_df['구분'] == '대항목'
    if main_mask.any():
        report_df.loc[main_mask, '순위'] = report_df.loc[main_mask, '최종 가중치'].rank(ascending=False).astype(int)

    # --------------------------------------------------------------------------
    # 5. 화면 출력
    # --------------------------------------------------------------------------
    st.subheader("🏆 최종 가중치 및 순위 리포트")
    st.caption("산술 평균(Arithmetic Mean) 방식으로 집계된 결과입니다.")
    
    # 출력용 데이터프레임 (깔끔하게)
    display_df = report_df.copy()
    
    # 숫자 포맷팅
    cols_to_format = ["대항목 가중치", "소항목 가중치", "최종 가중치"]
    for c in cols_to_format:
        display_df[c] = display_df[c].apply(lambda x: f"{x:.4f}" if x > 0 else "")
        
    display_df['순위'] = display_df['순위'].apply(lambda x: f"{int(x)}위")
    
    # 대항목 행인 경우 소항목 관련 컬럼 비우기
    display_df.loc[display_df['구분'] == '대항목', '소항목 가중치'] = ""
    display_df.loc[display_df['구분'] == '대항목', '소항목명'] = ""
    
    # 컬럼 순서 정리
    final_cols = ["구분", "대항목명", "소항목명", "대항목 가중치", "소항목 가중치", "최종 가중치", "순위"]
    st.dataframe(display_df[final_cols], use_container_width=True, hide_index=True)
    
    # --------------------------------------------------------------------------
    # 6. Excel 다운로드 (3개 시트)
    # --------------------------------------------------------------------------
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Sheet 1: 최종 결과 (보고서용)
        display_df[final_cols].to_excel(writer, sheet_name='1_최종_분석_결과', index=False)
        
        # Sheet 2: 원본 데이터 (전체)
        raw_df.to_excel(writer, sheet_name='2_전체_원본_데이터', index=False)
        
        # Sheet 3: 유효하지 않은 데이터 (검증용)
        if not invalid_rows.empty:
            invalid_export = invalid_rows[["Respondent", "Time", "CR_Details"]]
            invalid_export.to_excel(writer, sheet_name='3_제외된_데이터_오류목록', index=False)
    
    output.seek(0)
    
    st.download_button(
        label="📥 전체 결과 엑셀 다운로드",
        data=output,
        file_name=f"AHP_Result_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )

    # --------------------------------------------------------------------------
    # 7. 제외된 데이터 화면 표시
    # --------------------------------------------------------------------------
    if not invalid_rows.empty:
        with st.expander("⚠️ 제외된 데이터(CR > 0.1) 상세 보기"):
            st.error("아래 응답자들은 논리적 일관성 부족으로 최종 계산에서 제외되었습니다.")
            
            inv_show = invalid_rows[["Respondent", "CR_Details"]].copy()
            inv_show['CR값 상세'] = inv_show['CR_Details'].apply(lambda x: x.replace("{", "").replace("}", "").replace("'", ""))
            st.table(inv_show[["Respondent", "CR값 상세"]])

else:
    st.info("좌측 메뉴의 [설문 진행] 페이지에서 데이터를 생성한 후, CSV 파일을 다운로드 받아 업로드해주세요.")
    st.markdown("""
    #### 💡 분석 원리 안내
    1. **수정 가중치 (Corrected Weight):** - 각 응답자의 데이터를 **고유벡터법(Eigenvector Method)**으로 분석하여, 가장 논리적인 가중치를 추출합니다.
    2. **데이터 필터링:** - **CR(일관성 비율)이 0.1을 초과**하는 데이터는 신뢰도가 낮으므로 평균 계산에서 **자동 제외**됩니다.
    3. **최종 산출 (AIP 방식):**
       - 유효한 응답자들의 가중치를 **산술 평균(Arithmetic Mean)**하여 최종 값을 도출합니다.
    """)
