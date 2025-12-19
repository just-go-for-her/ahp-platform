import streamlit as st
import pandas as pd
import json
import os
import re
import numpy as np
import io

# --------------------------------------------------------------------------
# 1. 페이지 설정
# --------------------------------------------------------------------------
st.set_page_config(page_title="결과 데이터 센터", page_icon="📊", layout="wide")

st.title("🔐 결과 데이터 센터 (Private)")

DATA_FOLDER = "survey_data"
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

# --------------------------------------------------------------------------
# 2. AHP 계산 엔진
# --------------------------------------------------------------------------
RI_TABLE = {1: 0, 2: 0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}

def saaty_scale(val):
    try:
        val_f = float(val)
    except (ValueError, TypeError):
        return 1
    if val_f >= 1: return val_f
    elif val_f <= -1: return 1 / abs(val_f)
    else: return 1

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
    geo_means = [np.prod(matrix[i]) ** (1/n) for i in range(n)]
    total_sum = sum(geo_means)
    weights = [gm / total_sum for gm in geo_means]
    weights_dict = {items[i]: w for i, w in enumerate(weights)}
    if n <= 2: cr = 0.0
    else:
        lambda_max = sum(np.sum(matrix[:, i]) * weights[i] for i in range(n))
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
                groups[group_name], items_in_group[group_name] = {}, set()
            groups[group_name][pair_key] = val
            if " vs " in pair_key:
                a, b = pair_key.split(" vs ")
                items_in_group[group_name].add(a.strip()); items_in_group[group_name].add(b.strip())
    calc_weights, max_cr = {}, 0.0 
    main_group = next((k for k in groups.keys() if "1." in k or "기준" in k), None)
    if main_group:
        w, cr = calculate_ahp(list(items_in_group[main_group]), groups[main_group])
        calc_weights["MAIN"], max_cr = w, cr
    else: return None, 9.9 
    final_rows = []
    for g_name, pairs in groups.items():
        if g_name == main_group: continue
        parent = next((m for m in calc_weights["MAIN"].keys() if m in g_name), None)
        if parent:
            sub_w, sub_cr = calculate_ahp(list(items_in_group[g_name]), pairs)
            if sub_cr > max_cr: max_cr = sub_cr
            p_w = calc_weights["MAIN"][parent]
            for s_item, s_w in sub_w.items():
                final_rows.append({"1차 기준": parent, "1차 가중치": p_w, "2차 항목": s_item, "2차 가중치": s_w, "종합 가중치": p_w * s_w})
    return final_rows, max_cr

# --------------------------------------------------------------------------
# 3. 메인 UI
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("🔑 접속 인증")
    user_key = st.text_input("프로젝트 비밀번호(Key)", type="password")

if not user_key:
    st.info("👈 사이드바에 **프로젝트 비밀번호**를 입력하세요.")
    st.stop()

# 파일 목록 필터링
all_files = [f for f in os.listdir(DATA_FOLDER) if f.endswith(".csv")]
my_files = [f for f in all_files if f.startswith(f"{user_key}_")]

if not my_files:
    st.error(f"비밀번호 '{user_key}' 관련 데이터를 찾을 수 없습니다.")
    st.stop()

st.success(f"인증 성공! '{user_key}' 관련 데이터를 불러왔습니다.")
selected_file = st.selectbox("📂 분석할 데이터 선택:", my_files)

if selected_file:
    file_path = os.path.join(DATA_FOLDER, selected_file)
    df = pd.read_csv(file_path)
    display_name = selected_file.replace(f"{user_key}_", "").replace(".csv", "").replace("_", " ")
    st.subheader(f"📈 분석 대시보드: {display_name}")
    
    if st.button("🧮 분석 실행", type="primary"):
        valid_rows, indiv_v, indiv_i, status_list = [], [], [], []
        for idx, row in df.iterrows():
            res, cr = process_single_response(row['Raw_Data'])
            if res is None: continue
            is_valid = cr <= 0.1
            status_list.append({"순번": idx+1, "응답자": row.get('Respondent', '익명'), "작성시간": row['Time'], "CR": round(cr, 4), "유효판정": "O" if is_valid else "X"})
            p_df = pd.DataFrame(res).sort_values(by='종합 가중치', ascending=False)
            p_df['순위'] = range(1, len(p_df)+1)
            for c, v in [('응답자', row.get('Respondent', '익명')), ('작성시간', row['Time']), ('CR', round(cr, 4))]: p_df.insert(0, c, v)
            if is_valid: valid_rows.extend(res); indiv_v.extend(p_df.to_dict('records'))
            else: indiv_i.extend(p_df.to_dict('records'))

        st.markdown("### 1️⃣ 데이터 유효성 검증 현황")
        status_df = pd.DataFrame(status_list)
        st.dataframe(status_df.style.applymap(lambda v: 'background-color: #e6fcf5' if v == 'O' else 'background-color: #fff5f5; color: red;', subset=['유효판정']), use_container_width=True)

        if valid_rows:
            f_df = pd.DataFrame(valid_rows).groupby(['1차 기준', '2차 항목']).mean(numeric_only=True).reset_index().sort_values(by='종합 가중치', ascending=False)
            f_df['순위'] = range(1, len(f_df)+1)
            
            st.divider()
            st.markdown("### 🏆 2️⃣ 최종 종합 순위 (기준층/세부항목 분리)")
            c_weights = f_df.groupby('1차 기준')['1차 가중치'].mean().sort_values(ascending=False).reset_index()
            
            table_md = ""
            for _, r_c in c_weights.iterrows():
                c_n, c_w = r_c['1차 기준'], r_c['1차 가중치']
                table_md += f"<div style='margin-top:25px; padding:10px; background:#f0f8ff; border-left: 6px solid #228be6;'>**<span style='font-size:1.1em; color:#228be6;'>{c_n}</span>** (기준 가중치: {c_w:.4f})</div>\n\n"
                disp = f_df[f_df['1차 기준'] == c_n][['2차 항목', '2차 가중치', '종합 가중치', '순위']].rename(columns={'2차 항목':'세부 항목', '2차 가중치':'항목 가중치'}).to_markdown(index=False, floatfmt=".4f")
                table_md += disp + "\n\n"
            st.markdown(table_md, unsafe_allow_html=True)

            st.divider()
            st.markdown("### 📥 상세 리포트 다운로드")
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                f_df[['순위', '1차 기준', '2차 항목', '1차 가중치', '2차 가중치', '종합 가중치']].to_excel(writer, index=False, sheet_name='종합_순위_분석')
                pd.DataFrame(indiv_v).to_excel(writer, index=False, sheet_name='개인별_상세(유효)')
                if indiv_i: pd.DataFrame(indiv_i).to_excel(writer, index=False, sheet_name='부적합_상세_결과')
                status_df.to_excel(writer, index=False, sheet_name='응답자_현황_및_CR')
                df.to_excel(writer, index=False, sheet_name='원본_RAW_데이터')
            st.download_button(label="📊 통합 엑셀 리포트 다운로드 (.xlsx)", data=output.getvalue(), file_name=f"AHP_Report_{display_name}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
        else: st.error("유효한 데이터가 없어 분석할 수 없습니다.")

    st.divider()
    with st.expander("🗑️ 데이터 초기화"):
        if st.button("현재 파일 삭제"): os.remove(file_path); st.rerun()
