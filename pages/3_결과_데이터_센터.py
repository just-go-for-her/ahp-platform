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
# 2. AHP 계산 엔진 (수학 로직)
# --------------------------------------------------------------------------
# Saaty의 무작위 지수 (RI)
RI_TABLE = {1: 0, 2: 0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}

def saaty_scale(val):
    """슬라이더 값(-8~8)을 Saaty 척도(1/9~9)로 변환"""
    val = int(val)
    if val == 0: return 1
    elif val < 0: return 1 / (abs(val) + 1)
    else: return val + 1

def calculate_ahp(items, pairs_data):
    """가중치와 CR(일관성 비율)을 동시에 계산"""
    n = len(items)
    if n == 0: return {}, 0
    
    # 1. 쌍대비교 행렬 생성
    matrix = np.ones((n, n))
    item_map = {name: i for i, name in enumerate(items)}

    for key, val in pairs_data.items():
        # 데이터 파싱 ("A vs B")
        if " vs " in key:
            parts = key.split(" vs ")
            item_a, item_b = parts[0].strip(), parts[1].strip()
            
            if item_a in item_map and item_b in item_map:
                idx_a, idx_b = item_map[item_a], item_map[item_b]
                scale_val = saaty_scale(val)
                matrix[idx_a][idx_b] = scale_val
                matrix[idx_b][idx_a] = 1 / scale_val

    # 2. 가중치 계산 (기하평균법)
    geo_means = []
    for i in range(n):
        row_prod = np.prod(matrix[i])
        geo_means.append(row_prod ** (1/n))
    
    total_sum = sum(geo_means)
    weights = [gm / total_sum for gm in geo_means]
    weights_dict = {items[i]: w for i, w in enumerate(weights)}

    # 3. CR(일관성 비율) 계산
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
    """한 명의 응답 데이터를 분석하여 가중치와 CR 반환"""
    try:
        data = json.loads(raw_json)
    except:
        return None, 9.9 # 파싱 에러

    groups, items_in_group = {}, {}

    # 데이터 분류
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
    
    # 1차 기준 계산 (보통 '1.' 이나 '기준'이 들어감)
    main_group_name = next((k for k in groups.keys() if "1." in k or "기준" in k), None)
    
    if main_group_name:
        items = list(items_in_group[main_group_name])
        w, cr = calculate_ahp(items, groups[main_group_name])
        calculated_weights["MAIN"] = w
        if cr > max_cr: max_cr = cr
    else:
        return None, 9.9 

    # 2차 세부항목 계산 및 종합
    final_rows = []
    
    for group_name, pairs in groups.items():
        if group_name == main_group_name: continue
        
        # 부모 찾기
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

# --------------------------------------------------------------------------
# 3. 메인 UI (분석 및 시각화)
# --------------------------------------------------------------------------
# 사이드바: 비밀번호 인증
with st.sidebar:
    st.header("🔑 접속 인증")
    user_key = st.text_input("프로젝트 비밀번호(Key)", type="password")

if not user_key:
    st.info("👈 왼쪽 사이드바에 **프로젝트 비밀번호**를 입력해주세요.")
    st.stop()

# 파일 필터링
all_files = [f for f in os.listdir(DATA_FOLDER) if f.endswith(".csv")]
my_files = [f for f in all_files if f.startswith(f"{user_key}_")]

if not my_files:
    st.error(f"비밀번호 '{user_key}'에 해당하는 프로젝트가 없습니다.")
    st.stop()

st.success(f"인증 성공! '{user_key}' 프로젝트 데이터를 불러왔습니다.")
selected_file = st.selectbox("📂 분석할 데이터 파일 선택:", my_files)

if selected_file:
    file_path = os.path.join(DATA_FOLDER, selected_file)
    df = pd.read_csv(file_path)
    
    st.divider()
    display_name = selected_file.replace(f"{user_key}_", "").replace(".csv", "").replace("_", " ")
    st.subheader(f"📈 분석 대시보드: {display_name}")
    st.caption(f"총 응답 데이터: {len(df)}건")
    
    # [핵심] 분석 실행 버튼
    if st.button("🧮 AHP 분석 실행 (순위/일관성/엑셀)", type="primary"):
        
        valid_data = [] # 유효한 데이터 모음
        status_list = [] # O/X 현황판
        
        # 1. 데이터 한 줄씩 꺼내서 분석
        for idx, row in df.iterrows():
            try:
                res_rows, person_cr = process_single_response(row['Raw_Data'])
                
                if res_rows is None: 
                    continue # 데이터 깨짐 방지

                # 유효성 판정 (CR <= 0.1)
                is_valid = person_cr <= 0.1
                valid_mark = "O" if is_valid else "X"
                
                status = {
                    "응답자": row.get('Respondent', f'참여자 {idx+1}'),
                    "작성시간": row['Time'],
                    "최대 CR": round(person_cr, 4),
                    "판정": valid_mark
                }
                status_list.append(status)
                
                if is_valid:
                    valid_data.extend(res_rows)
                    
            except Exception as e:
                continue 

        # -------------------------------------------------------
        # [기능 1] 일관성 검증 표 (CR Check)
        # -------------------------------------------------------
        st.markdown("### 1️⃣ 데이터 일관성 검증 (CR Check)")
        st.caption("CR(일관성 비율)이 0.1 이하인 데이터만 **'O'**로 판정하여 분석에 포함합니다.")
        
        status_df = pd.DataFrame(status_list)
        if not status_df.empty:
            # 색상 적용 함수
            def color_validity(val):
                color = '#e6fcf5' if val == 'O' else '#fff5f5'
                return f'background-color: {color}'
            
            st.dataframe(status_df.style.applymap(color_validity, subset=['판정']), use_container_width=True)
            
            valid_count = len(status_df[status_df['판정'] == 'O'])
            st.info(f"전체 {len(status_df)}명 중 **{valid_count}명(O)**의 유효 데이터를 활용합니다.")
        else:
            st.warning("분석할 데이터가 없습니다.")

        # -------------------------------------------------------
        # [기능 2] 최종 순위 산출 (Ranking)
        # -------------------------------------------------------
        if valid_data:
            res_df = pd.DataFrame(valid_data)
            
            # 평균 계산
            final_df = res_df.groupby(['1차 기준', '2차 항목']).mean(numeric_only=True).reset_index()
            final_df = final_df.sort_values(by='종합 가중치', ascending=False)
            final_df['순위'] = range(1, len(final_df) + 1)
            
            # 보여줄 컬럼 정리
            disp_df = final_df[['순위', '1차 기준', '2차 항목', '종합 가중치', '1차 가중치', '2차 가중치']]
            
            st.divider()
            st.markdown("### 🏆 2️⃣ 최종 종합 순위 (Global Rank)")
            
            # 순위표 출력 (색칠 기능 포함, 에러 시 기본표 출력)
            try:
                st.dataframe(
                    disp_df.style.format({
                        '종합 가중치': '{:.4f}', '1차 가중치': '{:.4f}', '2차 가중치': '{:.4f}'
                    }).background_gradient(subset=['종합 가중치'], cmap='Blues'),
                    use_container_width=True
                )
            except:
                st.dataframe(disp_df, use_container_width=True)

            # -------------------------------------------------------
            # [기능 3] 엑셀 다운로드 (Excel Export)
            # -------------------------------------------------------
            st.divider()
            st.markdown("### 📥 결과 리포트 다운로드")
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                disp_df.to_excel(writer, index=False, sheet_name='종합순위_결과')
                status_df.to_excel(writer, index=False, sheet_name='유효성_검사')
                df.to_excel(writer, index=False, sheet_name='원본_데이터')
            
            st.download_button(
                label="📄 엑셀 파일 다운로드 (.xlsx)",
                data=output.getvalue(),
                file_name=f"AHP_Analysis_{display_name}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
            
        else:
            st.error("🚨 분석에 활용할 수 있는 유효한 데이터(O)가 하나도 없습니다.")

    # [관리자 기능] 데이터 초기화
    st.divider()
    with st.expander("🗑️ 데이터 초기화 (관리자용)"):
        st.warning("⚠️ 주의: 이 버튼을 누르면 현재 선택된 파일이 영구 삭제됩니다.")
        if st.button("현재 파일 삭제하기"):
            try:
                os.remove(file_path)
                st.success("파일이 삭제되었습니다. 페이지를 새로고침합니다.")
                st.rerun()
            except:
                st.error("삭제 실패")
