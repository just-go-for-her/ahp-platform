import streamlit as st
import pandas as pd
import json
import os
import re
import numpy as np

st.set_page_config(page_title="결과 데이터 센터", page_icon="📊", layout="wide")

st.title("🔐 결과 데이터 센터 (Private)")

DATA_FOLDER = "survey_data"
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

# ==============================================================================
# 1. 비밀번호(ID) 인증 단계
# ==============================================================================
with st.sidebar:
    st.header("🔑 접속 인증")
    user_key = st.text_input("프로젝트 비밀번호(Key) 입력", type="password")

if not user_key:
    st.info("👈 왼쪽 사이드바에 **프로젝트 비밀번호**를 입력해야 결과를 볼 수 있습니다.")
    st.stop()

# ==============================================================================
# 2. 해당 비밀번호의 파일만 필터링
# ==============================================================================
all_files = [f for f in os.listdir(DATA_FOLDER) if f.endswith(".csv")]
# 파일명 규칙: {Key}_{Goal}.csv -> Key가 일치하는지 확인
my_files = [f for f in all_files if f.startswith(f"{user_key}_")]

if not my_files:
    st.error(f"비밀번호 '{user_key}'에 해당하는 프로젝트가 없습니다.")
    st.stop()

# ==============================================================================
# 3. 데이터 분석 (이후는 기존 로직과 동일)
# ==============================================================================
st.success(f"반갑습니다! '{user_key}' 프로젝트의 데이터를 불러왔습니다.")
selected_file = st.selectbox("📂 분석할 프로젝트 선택:", my_files)

# ... (아래는 기존의 AHP 계산 및 분석 코드 그대로 사용) ...
# (너무 길어서 핵심만 넣겠습니다. 기존 AHP 함수들은 그대로 유지해주세요!)

# [여기부터 아래는 아까 드린 AHP 계산 로직 복붙해서 쓰시면 됩니다. 
# 단, process_single_response 함수 등은 그대로 두세요.]

# 편의를 위해 '기존 AHP 계산 코드' 전체를 다시 합쳐드릴게요.
RI_TABLE = {1: 0, 2: 0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45}

def saaty_scale(val):
    val = int(val)
    if val == 0: return 1
    elif val < 0: return 1 / (abs(val) + 1)
    else: return val + 1

def calculate_ahp(items, pairs_data):
    n = len(items)
    if n == 0: return {}, 0
    matrix = np.ones((n, n))
    item_map = {name: i for i, name in enumerate(items)}
    for key, val in pairs_data.items():
        if " vs " in key:
            parts = key.split(" vs ")
            item_a, item_b = parts[0].strip(), parts[1].strip()
            if item_a in item_map and item_b in item_map:
                idx_a, idx_b = item_map[item_a], item_map[item_b]
                scale_val = saaty_scale(val)
                matrix[idx_a][idx_b] = scale_val
                matrix[idx_b][idx_a] = 1 / scale_val
    geo_means = []
    for i in range(n):
        row_prod = np.prod(matrix[i])
        geo_means.append(row_prod ** (1/n))
    total_sum = sum(geo_means)
    weights = [gm / total_sum for gm in geo_means]
    weights_dict = {items[i]: w for i, w in enumerate(weights)}
    if n <= 2: cr = 0.0
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
    try: data = json.loads(raw_json)
    except: return None, 9.9
    groups, items_in_group = {}, {}
    for full_key, val in data.items():
        match = re.match(r"\[(.*?)\](.*)", full_key)
        if match:
            group_name, pair_key = match.group(1), match.group(2).strip()
            if group_name not in groups: 
                groups[group_name] = {}
                items_in_group[group_name] = set()
            groups[group_name][pair_key] = val
            if " vs " in pair_key:
                a, b = pair_key.split(" vs ")
                items_in_group[group_name].add(a.strip())
                items_in_group[group_name].add(b.strip())
    calculated_weights = {}
    max_cr = 0.0 
    main_group_name = next((k for k in groups.keys() if "1." in k or "1차" in k), None)
    if main_group_name:
        items = list(items_in_group[main_group_name])
        w, cr = calculate_ahp(items, groups[main_group_name])
        calculated_weights["MAIN"] = w
        if cr > max_cr: max_cr = cr
    else: return None, 9.9 
    final_rows = []
    for group_name, pairs in groups.items():
        if group_name == main_group_name: continue
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

# UI 렌더링
if selected_file:
    file_path = os.path.join(DATA_FOLDER, selected_file)
    df = pd.read_csv(file_path)
    
    st.divider()
    # 파일명에서 Key 제거하고 보여주기: {Key}_{Goal}.csv -> {Goal}
    display_name = selected_file.replace(f"{user_key}_", "").replace(".csv", "").replace("_", " ")
    st.subheader(f"📈 프로젝트 분석: {display_name}")
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
                    "응답자": row['Respondent'],
                    "작성시간": row['Time'],
                    "최대 CR": round(person_max_cr, 4),
                    "활용 여부": valid_mark
                }
                respondent_status.append(status)
                if is_valid: valid_respondents_data.extend(res_rows)
            except: continue 

        st.markdown("### 1️⃣ 데이터 유효성 검사")
        status_df = pd.DataFrame(respondent_status)
        if not status_df.empty:
            def color_validity(val): return 'background-color: #e6fcf5' if val == 'O' else 'background-color: #fff5f5'
            st.dataframe(status_df.style.applymap(color_validity, subset=['활용 여부']), use_container_width=True)
        
        if valid_respondents_data:
            result_df = pd.DataFrame(valid_respondents_data)
            final_df = result_df.groupby(['1차 기준', '2차 항목']).mean(numeric_only=True).reset_index()
            final_df = final_df.sort_values(by='종합 가중치', ascending=False)
            final_df['순위'] = range(1, len(final_df) + 1)
            display_df = final_df[['순위', '1차 기준', '2차 항목', '종합 가중치', '1차 가중치', '2차 가중치']]
            
            st.divider()
            st.markdown("### 🏆 2️⃣ 최종 종합 순위")
            # Matplotlib 없이 심플하게 출력 (에러 방지)
            st.dataframe(display_df, use_container_width=True)
            
            import io
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                display_df.to_excel(writer, index=False, sheet_name='종합순위')
                status_df.to_excel(writer, index=False, sheet_name='유효성검사')
                df.to_excel(writer, index=False, sheet_name='원본')
            st.download_button("📥 엑셀 다운로드", data=output.getvalue(), file_name=f"Result_{display_name}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.error("유효한 데이터(O)가 없습니다.")

    # 삭제 기능 (비밀번호 아는 사람만 가능)
    st.divider()
    with st.expander("⚠️ 데이터 삭제 (관리자)"):
        if st.button("🗑️ 이 프로젝트 영구 삭제"):
            os.remove(file_path)
            st.success("삭제되었습니다.")
            st.rerun()
