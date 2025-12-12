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
    try:
        data = json.loads(raw_json)
    except:
        return None, 9.9 

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
    
    main_group_name = next((k for k in groups.keys() if "1." in k or "기준" in k), None)
    
    if main_group_name:
        items = list(items_in_group[main_group_name])
        w, cr = calculate_ahp(items, groups[main_group_name])
        calculated_weights["MAIN"] = w
        if cr > max_cr: max_cr = cr
    else:
        return None, 9.9 

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
                final_weight = p_weight * s_weight
                final_rows.append({
                    "1차 기준": parent_name,
                    "1차 가중치": p_weight,
                    "2차 항목": s_item,
                    "2차 가중치": s_weight,
                    "종합 가중치": final_weight
                })

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

all_files = [f for f in os.listdir(DATA_FOLDER) if f.endswith(".csv")]
my_files = [f for f in all_files if f.startswith(f"{user_key}_")]

if not my_files:
    st.error(f"비밀번호 '{user_key}'에 해당하는 데이터가 없습니다.")
    st.stop()

st.success(f"인증 성공! 프로젝트 데이터를 불러왔습니다.")
selected_file = st.selectbox("📂 분석할 데이터 선택:", my_files)

if selected_file:
    file_path = os.path.join(DATA_FOLDER, selected_file)
    df = pd.read_csv(file_path)
    
    st.divider()
    display_name = selected_file.replace(f"{user_key}_", "").replace(".csv", "").replace("_", " ")
    st.subheader(f"📈 분석 대시보드: {display_name}")
    st.caption(f"총 응답 수: {len(df)}명")
    
    if st.button("🧮 분석 실행 (리포트 생성)", type="primary"):
        
        valid_data_rows = []        # 집단 분석용 (유효 데이터만 취합)
        individual_detail_rows = [] # 유효한 개인별 상세 (순위 포함)
        invalid_detail_rows = []    # [추가됨] 부적합 개인별 상세 (순위 포함)
        status_list = []            # 현황판
        
        for idx, row in df.iterrows():
            try:
                res_rows, person_cr = process_single_response(row['Raw_Data'])
                if res_rows is None: continue

                is_valid = person_cr <= 0.1
                
                # 1. 현황판용 데이터 (화면 표시용)
                status = {
                    "순번": idx + 1,
                    "응답자": row.get('Respondent', '익명'),
                    "작성시간": row['Time'],
                    "일관성지수(CR)": round(person_cr, 4),
                    "유효판정": "O" if is_valid else "X"
                }
                status_list.append(status)
                
                # 2. 개인별 상세 데이터 가공 (공통)
                person_df = pd.DataFrame(res_rows)
                person_df = person_df.sort_values(by='종합 가중치', ascending=False)
                person_df['순위'] = range(1, len(person_df) + 1)
                
                # 인적사항 및 CR 정보 추가
                person_df.insert(0, '응답자', row.get('Respondent', '익명'))
                person_df.insert(1, '작성시간', row['Time'])
                person_df.insert(2, 'CR', round(person_cr, 4))
                
                # 3. 유효성 여부에 따른 분리 저장
                if is_valid:
                    # 유효함 -> 종합 분석 및 유효 상세 리스트에 추가
                    valid_data_rows.extend(res_rows)
                    individual_detail_rows.extend(person_df.to_dict('records'))
                else:
                    # 부적합 -> 부적합 상세 리스트에만 추가 (종합 분석 제외)
                    invalid_detail_rows.extend(person_df.to_dict('records'))
                    
            except Exception as e:
                continue 

        # -------------------------------------------------------
        # 화면 출력
        # -------------------------------------------------------
        
        # 1. 유효성 검사 현황판
        st.markdown("### 1️⃣ 데이터 유효성 검증 현황")
        status_df = pd.DataFrame(status_list)
        
        if not status_df.empty:
            def color_val(val):
                return 'background-color: #e6fcf5' if val == 'O' else 'background-color: #fff5f5; color: red;'
            st.dataframe(status_df.style.applymap(color_val, subset=['유효판정']), use_container_width=True)
            
            valid_count = len(status_df[status_df['유효판정'] == 'O'])
            st.info(f"총 {len(status_df)}명 중 **{valid_count}명(O)**의 데이터만 종합 분석에 반영됩니다.")
        
        # 2. 종합 순위 (집단 평균) - 유효한 데이터만 사용
        if valid_data_rows:
            res_df = pd.DataFrame(valid_data_rows)
            final_df = res_df.groupby(['1차 기준', '2차 항목']).mean(numeric_only=True).reset_index()
            final_df = final_df.sort_values(by='종합 가중치', ascending=False)
            final_df['순위'] = range(1, len(final_df) + 1)
            
            disp_df = final_df[['순위', '1차 기준', '2차 항목', '종합 가중치']]
            
            st.divider()
            st.markdown("### 🏆 2️⃣ 최종 종합 순위 (유효 데이터 기준)")
            st.dataframe(disp_df.style.background_gradient(subset=['종합 가중치'], cmap='Blues'), use_container_width=True)

            # -------------------------------------------------------
            # [엑셀 다운로드]
            # -------------------------------------------------------
            st.divider()
            st.markdown("### 📥 상세 리포트 다운로드")
            
            # DataFrame 변환
            personal_valid_df = pd.DataFrame(individual_detail_rows) # 유효
            personal_invalid_df = pd.DataFrame(invalid_detail_rows)  # 부적합 [추가됨]
            
            # 컬럼 순서 정리 (보기 좋게)
            cols = ['응답자', '작성시간', 'CR', '순위', '1차 기준', '1차 가중치', '2차 항목', '2차 가중치', '종합 가중치']
            
            if not personal_valid_df.empty:
                personal_valid_df = personal_valid_df[[c for c in cols if c in personal_valid_df.columns]]
            
            if not personal_invalid_df.empty:
                personal_invalid_df = personal_invalid_df[[c for c in cols if c in personal_invalid_df.columns]]

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # 시트 1: 종합 순위 (유효값 기준)
                disp_df.to_excel(writer, index=False, sheet_name='종합_순위_분석')
                
                # 시트 2: 유효한 개인별 상세
                personal_valid_df.to_excel(writer, index=False, sheet_name='개인별_상세(유효)')
                
                # 시트 3: [NEW] 부적합한 개인별 상세 (별도 시트)
                if not personal_invalid_df.empty:
                    personal_invalid_df.to_excel(writer, index=False, sheet_name='부적합_상세_결과')
                
                # 시트 4: 전체 응답자 현황 (O/X 확인용)
                status_df.to_excel(writer, index=False, sheet_name='응답자_현황_및_CR')
                
                # 시트 5: 원본 RAW 데이터
                df.to_excel(writer, index=False, sheet_name='원본_RAW_데이터')
            
            st.download_button(
                label="📊 엑셀 리포트 다운로드 (.xlsx)",
                data=output.getvalue(),
                file_name=f"AHP_Report_{display_name}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
            
            if not personal_invalid_df.empty:
                with st.expander("⚠️ 부적합 데이터(CR > 0.1) 미리보기"):
                    st.warning("아래 데이터는 일관성이 부족하여 종합 분석에서 제외되었습니다. 엑셀의 '부적합_상세_결과' 시트에서 확인 가능합니다.")
                    st.dataframe(personal_invalid_df)
            
        else:
            st.error("유효한 데이터(CR <= 0.1)가 하나도 없어 종합 분석을 수행할 수 없습니다.")
            
            # 유효한 데이터가 없더라도 부적합 데이터만이라도 엑셀로 받고 싶을 수 있으므로 다운로드 버튼 제공
            if invalid_detail_rows:
                st.warning("하지만 부적합 데이터에 대한 상세 내역은 다운로드할 수 있습니다.")
                personal_invalid_df = pd.DataFrame(invalid_detail_rows)
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    personal_invalid_df.to_excel(writer, index=False, sheet_name='부적합_상세_결과')
                    status_df.to_excel(writer, index=False, sheet_name='응답자_현황_및_CR')
                    df.to_excel(writer, index=False, sheet_name='원본_RAW_데이터')
                
                st.download_button(
                    label="📊 부적합 데이터만 다운로드 (.xlsx)",
                    data=output.getvalue(),
                    file_name=f"AHP_Invalid_Only_{display_name}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    # 초기화
    st.divider()
    with st.expander("🗑️ 데이터 초기화"):
        if st.button("현재 파일 삭제"):
            os.remove(file_path)
            st.rerun()
