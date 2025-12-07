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
# [AHP 계산 엔진] CR(일관성 비율) 계산 추가
# ==============================================================================
# Saaty의 무작위 지수 (Random Index)
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
        if "_vs_" in key:
            parts = key.split("_vs_")
            item_a, item_b = parts[0], parts[1]
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

    # 2. CR 계산 (Lambda Max)
    if n <= 2:
        cr = 0.0
    else:
        # 근사값 계산: 행렬의 열 합계 * 가중치 합
        lambda_max = 0
        for i in range(n):
            col_sum = np.sum(matrix[:, i])
            lambda_max += col_sum * weights[i]
            
        ci = (lambda_max - n) / (n - 1)
        ri = RI_TABLE.get(n, 1.49)
        cr = ci / ri if ri != 0 else 0

    return weights_dict, cr

def process_single_response(raw_json):
    """한 명의 응답 데이터를 분석하여 가중치와 최대 CR 반환"""
    data = json.loads(raw_json)
    groups, items_in_group = {}, {}

    # 데이터 파싱
    for full_key, val in data.items():
        match = re.match(r"\[(.*?)\](.*)", full_key)
        if match:
            group_name, pair_key = match.group(1), match.group(2)
            if group_name not in groups: 
                groups[group_name] = {}
                items_in_group[group_name] = set()
            groups[group_name][pair_key] = val
            if "_vs_" in pair_key:
                a, b = pair_key.split("_vs_")
                items_in_group[group_name].add(a)
                items_in_group[group_name].add(b)

    # 계산 수행
    calculated_weights = {}
    max_cr = 0.0 # 이 응답자의 CR 중 가장 나쁜(높은) 값
    
    # (1) 1차 기준 계산
    main_keys = [k for k in groups.keys() if "1" in k or "Main" in k or "기준" in k or "평가" in k]
    # '평가' 등의 단어가 포함된 그룹을 1차 기준으로 추정 (설문 생성 시 이름 규칙 중요)
    # 여기서는 가장 먼저 나오는 그룹을 1차로 가정하거나 이름으로 매칭
    
    # 2번 페이지 로직에 따라 "📂 1. 평가 기준..." 이름이 붙음
    main_group_name = next((k for k in groups.keys() if "1." in k), None)
    
    if main_group_name:
        items = list(items_in_group[main_group_name])
        w, cr = calculate_ahp(items, groups[main_group_name])
        calculated_weights["MAIN"] = w
        if cr > max_cr: max_cr = cr
    else:
        return None, 9.9 # 1차 기준 없으면 에러 처리

    # (2) 2차 세부 항목 계산 및 종합
    final_rows = []
    
    for group_name, pairs in groups.items():
        if group_name == main_group_name: continue
        
        # 부모 찾기 (이름 매칭)
        parent_name = None
        for m_item in calculated_weights["MAIN"].keys():
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
# [UI 및 메인 로직]
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
            
            valid_respondents_data = [] # O인 사람들의 데이터만 모음
            respondent_status = []      # 사람별 O/X 현황판
            
            # 1. 사람별로 CR 체크 및 O/X 판정
            for idx, row in df.iterrows():
                try:
                    res_rows, person_max_cr = process_single_response(row['Raw_Data'])
                    
                    # 판정 로직 (CR <= 0.1 이면 통과)
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
                    continue # 데이터 오류 시 스킵

            # 2. 유효성 검사 결과표 출력
            st.markdown("### 1️⃣ 데이터 유효성 검사 (Consistency Check)")
            st.caption("CR(일관성 비율)이 0.1 이하인 데이터만 'O'로 판정하여 분석에 활용합니다.")
            
            status_df = pd.DataFrame(respondent_status)
            
            # 색상 입히기 (O는 파랑, X는 빨강)
            def color_validity(val):
                color = '#e6fcf5' if val == 'O' else '#fff5f5' # 배경색
                return f'background-color: {color}'

            st.dataframe(status_df.style.applymap(color_validity, subset=['활용 여부']), use_container_width=True)
            
            # 유효 데이터 통계
            valid_count = len(status_df[status_df['활용 여부'] == 'O'])
            st.info(f"총 {len(status_df)}명 중 **{valid_count}명(O)**의 데이터만 사용하여 최종 순위를 계산합니다.")

            # 3. 최종 순위 산출 (유효 데이터만 사용)
            if valid_respondents_data:
                result_df = pd.DataFrame(valid_respondents_data)
                
                # 평균 계산
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
                
                # 엑셀 다운로드 (3개 시트: 종합순위, 유효성검사, 원본)
                import io
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    display_df.to_excel(writer, index=False, sheet_name='종합순위_결과')
                    status_df.to_excel(writer, index=False, sheet_name='데이터_유효성_검사')
                    df.to_excel(writer, index=False, sheet_name='원본_데이터')
                
                st.download_button(
                    label="📥 전체 분석 결과 엑셀 다운로드",
                    data=output.getvalue(),
                    file_name=f"Final_Report_{selected_file.replace('.csv', '.xlsx')}",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
            else:
                st.error("분석에 활용할 수 있는 유효한 데이터(O)가 하나도 없습니다. 설문을 다시 진행해주세요.")
        
        with st.expander("📋 원본 데이터 확인"):
            st.dataframe(df)

else:
    st.info("📭 저장된 데이터가 없습니다. 설문을 먼저 진행해주세요.")
