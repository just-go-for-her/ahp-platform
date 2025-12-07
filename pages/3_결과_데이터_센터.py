import streamlit as st
import pandas as pd
import json
import os
import re
import numpy as np

st.set_page_config(page_title="결과 데이터 센터", page_icon="📊", layout="wide")

st.title("📊 결과 데이터 센터")
st.markdown("수집된 데이터를 분석하여 **데이터 유효성(CR)**을 검증하고 **최종 순위**를 산출합니다.")

DATA_FOLDER = "survey_data"

# ==============================================================================
# [AHP 계산 엔진]
# ==============================================================================
RI_TABLE = {1: 0, 2: 0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45}

def saaty_scale(val):
    val = int(val)
    if val == 0: return 1
    elif val < 0: return 1 / (abs(val) + 1)
    else: return val + 1

def calculate_ahp(items, pairs_data):
    """가중치와 CR(일관성 비율)을 동시에 계산"""
    n = len(items)
    if n == 0: return {}, 0
    
    matrix = np.ones((n, n))
    item_map = {name: i for i, name in enumerate(items)}

    for key, val in pairs_data.items():
        # [수정됨] 구분자를 " vs "로 변경하고, 양쪽 공백 제거
        if " vs " in key:
            parts = key.split(" vs ")
            item_a, item_b = parts[0].strip(), parts[1].strip()
            
            if item_a in item_map and item_b in item_map:
                idx_a, idx_b = item_map[item_a], item_map[item_b]
                scale_val = saaty_scale(val)
                matrix[idx_a][idx_b] = scale_val
                matrix[idx_b][idx_a] = 1 / scale_val

    # 1. 가중치 계산 (기하평균법)
    geo_means = []
    for i in range(n):
        row_prod = np.prod(matrix[i])
        geo_means.append(row_prod ** (1/n))
    
    total_sum = sum(geo_means)
    weights = [gm / total_sum for gm in geo_means]
    weights_dict = {items[i]: w for i, w in enumerate(weights)}

    # 2. CR 계산
    if n <= 2:
        cr = 0.0
    else:
        lambda_max = 0
        for i in range(n):
            col_sum = np.sum(matrix[:, i])
            lambda_max += col_sum * weights[i]
            
        ci = (lambda_max - n) / (n - 1)
        ri = RI_TABLE.get(n, 1.49)
        cr = ci / ri if ri != 0 else 0

    return weights_dict, cr

def process_single_response(raw_json):
    """한 명의 응답 데이터를 분석"""
    try:
        data = json.loads(raw_json)
    except:
        return None, 9.9

    groups, items_in_group = {}, {}

    # 데이터 파싱
    for full_key, val in data.items():
        # 정규표현식: [그룹명] 항목A vs 항목B
        match = re.match(r"\[(.*?)\](.*)", full_key)
        if match:
            group_name, pair_key = match.group(1), match.group(2).strip()
            
            if group_name not in groups: 
                groups[group_name] = {}
                items_in_group[group_name] = set()
            
            groups[group_name][pair_key] = val
            
            # [수정됨] 구분자 " vs " 처리
            if " vs " in pair_key:
                a, b = pair_key.split(" vs ")
                items_in_group[group_name].add(a.strip())
                items_in_group[group_name].add(b.strip())

    # 계산 수행
    calculated_weights = {}
    max_cr = 0.0 
    
    # (1) 1차 기준 계산 ('1.' 또는 '1차'가 포함된 그룹)
    main_group_name = next((k for k in groups.keys() if "1." in k or "1차" in k), None)
    
    if main_group_name:
        items = list(items_in_group[main_group_name])
        w, cr = calculate_ahp(items, groups[main_group_name])
        calculated_weights["MAIN"] = w
        if cr > max_cr: max_cr = cr
    else:
        return None, 9.9 

    # (2) 2차 세부 항목 계산
    final_rows = []
    
    for group_name, pairs in groups.items():
        if group_name == main_group_name: continue
        
        # 부모 찾기
        parent_name = None
        for m_item in calculated_weights["MAIN"].keys():
            # 그룹명에 메인 기준 이름이 포함되어 있는지 확인 (예: [비용] 세부...)
            if m_item in group_name:
                parent_name = m_item
                break
        
        if parent_name:
            items = list(items_in_group[group_name])
            sub_w, sub_cr = calculate_ahp(items, pairs)
            
            if sub_cr > max_cr: max_cr = sub_cr
            
            p_weight = calculated_weights["MAIN"][parent_name]
            for s_item, s_weight in sub_w.items():
                final_rows.append({
                    "1차 기준": parent_name,
                    "1차 가중치": p_weight,
                    "2차 항목": s_item,
                    "2차 가중치": s_weight,
                    "종합 가중치": p_weight * s_weight
                })

    return final_rows, max_cr

# ==============================================================================
# [UI 메인]
# ==============================================================================

if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

files = [f for f in os.listdir(DATA_FOLDER) if f.endswith(".csv")]

if files:
    selected_file = st.selectbox("📂 분석할 프로젝트 선택:", files)
    
    if selected_file:
        file_path = os.path.join(DATA_FOLDER, selected_file)
        df = pd.read_csv(file_path)
        
        st.divider()
        st.subheader(f"📈 프로젝트 분석: {selected_file.replace('.csv', '').replace('_', ' ')}")
        st.caption(f"총 응답자: {len(df)}명")
        
        if st.button("🧮 유효성 검사 및 분석 실행", type="primary"):
            
            valid_respondents_data = [] 
            respondent_status = []      
            
            for idx, row in df.iterrows():
                try:
                    res_rows, person_max_cr = process_single_response(row['Raw_Data'])
                    
                    if res_rows is None: continue

                    is_valid = person_max_cr <= 0.1
                    valid_mark = "O" if is_valid else "X"
                    
                    status = {
                        "응답자": row['Respondent'] if pd.notna(row['Respondent']) else f"참여자 {idx+1}",
                        "작성시간": row['Time'],
                        "최대 CR": round(person_max_cr, 4),
                        "활용 여부": valid_mark
                    }
                    respondent_status.append(status)
                    
                    if is_valid:
                        valid_respondents_data.extend(res_rows)
                        
                except Exception as e:
                    continue 

            # 1. 유효성 검사 표
            st.markdown("### 1️⃣ 데이터 유효성 검사 (Consistency Check)")
            status_df = pd.DataFrame(respondent_status)
            
            if not status_df.empty:
                def color_validity(val):
                    return 'background-color: #e6fcf5' if val == 'O' else 'background-color: #fff5f5'
                st.dataframe(status_df.style.applymap(color_validity, subset=['활용 여부']), use_container_width=True)
            else:
                st.warning("분석할 수 있는 데이터가 없습니다.")

            # 2. 최종 순위 표
            if valid_respondents_data:
                result_df = pd.DataFrame(valid_respondents_data)
                
                final_df = result_df.groupby(['1차 기준', '2차 항목']).mean(numeric_only=True).reset_index()
                final_df = final_df.sort_values(by='종합 가중치', ascending=False)
                final_df['순위'] = range(1, len(final_df) + 1)
                
                display_df = final_df[['순위', '1차 기준', '2차 항목', '종합 가중치', '1차 가중치', '2차 가중치']]
                
                st.divider()
                st.markdown("### 🏆 2️⃣ 최종 종합 순위 (Global Rank)")
                st.dataframe(
                    display_df.style.format({
                        '종합 가중치': '{:.4f}', '1차 가중치': '{:.4f}', '2차 가중치': '{:.4f}'
                    }).background_gradient(subset=['종합 가중치'], cmap='Blues'),
                    use_container_width=True
                )
                
                # 엑셀 다운로드
                import io
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    display_df.to_excel(writer, index=False, sheet_name='종합순위_결과')
                    status_df.to_excel(writer, index=False, sheet_name='데이터_유효성_검사')
                    df.to_excel(writer, index=False, sheet_name='원본_데이터')
                
                st.download_button(
                    label="📥 전체 분석 결과 엑셀 다운로드",
                    data=output.getvalue(),
                    file_name=f"Final_{selected_file.replace('.csv', '.xlsx')}",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
            else:
                st.error("유효한 데이터(O)가 없어서 순위를 산출할 수 없습니다.")
        
        with st.expander("📋 원본 데이터 확인"):
            st.dataframe(df)

else:
    st.info("📭 저장된 데이터가 없습니다.")
