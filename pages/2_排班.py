import streamlit as st
import pandas as pd
import calendar
from ortools.sat.python import cp_model
import io
import json
import os

st.set_page_config(page_title="阿長排班系統", layout="wide")

st.title("🏥 智慧護理排班系統 (5.8 嚴格邏輯純淨版)")

st.markdown("""
    <style>
    [data-testid="stSidebar"] { left: unset; right: 0; border-left: 1px solid #f0f2f6; }
    [data-testid="stSidebarCollapsedControl"] { left: unset; right: 10px; }
    .stButton button { font-weight: bold; border-radius: 8px; cursor: default; }
    .magic-btn button { background-color: #ff4b4b; color: white; border: 2px solid #ff4b4b; }
    </style>
""", unsafe_allow_html=True)

DEFAULT_HEME = ['血腫-蔡O樺', '血腫-吳O茹', '血腫-張O葳', '血腫-葉O菁', '血腫-蔡O蓁', '血腫-呂O岑', '血腫-洪O蔚']
DEFAULT_PALL = ['安寧-龔O如', '安寧-葉O敏', '安寧-沈O叡', '安寧-張O嘉', '安寧-許O禎', '安寧-吳O萍', '安寧-劉O君', '安寧-鐘O淇', '安寧-洪O安', '安寧-陳O柔', '安寧-黃O柔', '安寧-李O軒']
DEFAULT_HN = '護理長-林O穎'

def load_staff_data():
    data = {"heme": DEFAULT_HEME, "pall": DEFAULT_PALL, "hn": DEFAULT_HN, "heme_seniors": ['血腫-蔡O樺', '血腫-吳O茹'], "pall_seniors": ['安寧-龔O如', '安寧-葉O敏']}
    if os.path.exists('staff_v5.json'):
        try:
            with open('staff_v5.json', 'r', encoding='utf-8') as f:
                saved = json.load(f)
                if 'heme' in saved: data['heme'] = [x.strip() for x in saved['heme'] if x.strip()]
                if 'pall' in saved: data['pall'] = [x.strip() for x in saved['pall'] if x.strip()]
                if 'hn' in saved: data['hn'] = saved['hn'].strip()
                if 'heme_seniors' in saved: data['heme_seniors'] = [x.strip() for x in saved['heme_seniors'] if x.strip()]
                if 'pall_seniors' in saved: data['pall_seniors'] = [x.strip() for x in saved['pall_seniors'] if x.strip()]
        except: pass
    return data

def save_staff_data(data):
    try:
        with open('staff_v5.json', 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=4)
    except: pass

staff_data = load_staff_data()
heme_staff = staff_data.get('heme', DEFAULT_HEME)
pall_staff = staff_data.get('pall', DEFAULT_PALL)
hn_name = staff_data.get('hn', DEFAULT_HN)
heme_seniors = staff_data.get('heme_seniors', [])
pall_seniors = staff_data.get('pall_seniors', [])

active_staff = heme_staff + pall_staff 
all_staff = active_staff + [hn_name]

# 加入 ND 相關班別
SHIFTS = ['Off', 'D', 'E', 'N', '12-8', '4-8', '8-12', '1-8', 'M', '公', 'L', 'ND-D', 'ND-E', 'ND-N']

def fmt_num(n): return int(n) if n == int(n) else n

if 'daily_shifts' not in st.session_state: st.session_state.daily_shifts = {n: {} for n in all_staff}
if 'fixed' not in st.session_state: st.session_state.fixed = {n: "無 (混合)" for n in all_staff}
if 'prev_status' not in st.session_state: st.session_state.prev_status = {n: {'shift': 'Off'} for n in all_staff}
if 'prev_streak' not in st.session_state: st.session_state.prev_streak = {n: 0 for n in all_staff}

with st.sidebar:
    st.header("⚙️ 排班系統控制台")
    year = st.number_input("年份", 2025, 2030, 2026, key="ctrl_year")
    month = st.number_input("月份", 1, 12, 6, key="ctrl_month") 
    _, num_days = calendar.monthrange(year, month)
    
    with st.expander("👥 每日人力需求調整", expanded=True):
        tab_h, tab_p = st.tabs(["🩸 血腫組", "🕊️ 安寧組"])
        with tab_h:
            c1, c2, c3, c4 = st.columns(4)
            h_wd_d = c1.number_input("平D", 0, 10, 2, key="h_wd_d")
            h_wd_e = c2.number_input("平E", 0, 10, 1, key="h_wd_e")
            h_wd_n = c3.number_input("平N", 0, 10, 1, key="h_wd_n")
            h_wd_48 = c4.number_input("平4-8", 0, 10, 1, key="h_wd_48")
            
            c1, c2, c3, c4 = st.columns(4)
            h_sa_d = c1.number_input("六D", 0, 10, 1, key="h_sa_d")
            h_sa_e = c2.number_input("六E", 0, 10, 1, key="h_sa_e")
            h_sa_n = c3.number_input("六N", 0, 10, 1, key="h_sa_n")
            h_sa_812 = c4.number_input("六8-12", 0, 10, 1, key="h_sa_812")
            
            c1, c2, c3 = st.columns(3)
            h_su_d = c1.number_input("日D", 0, 10, 1, key="h_su_d")
            h_su_e = c2.number_input("日E", 0, 10, 1, key="h_su_e")
            h_su_n = c3.number_input("日N", 0, 10, 1, key="h_su_n")
            
        with tab_p:
            c1, c2, c3, c4, c5 = st.columns(5)
            p_mth_d = c1.number_input("平D", 0, 10, 4, key="p_mth_d")
            p_mth_e = c2.number_input("平E", 0, 10, 2, key="p_mth_e")
            p_mth_n = c3.number_input("平N", 0, 10, 2, key="p_mth_n")
            p_mth_48 = c4.number_input("平4-8", 0, 10, 1, key="p_mth_48")
            p_mth_18 = c5.number_input("平1-8", 0, 10, 0, key="p_mth_18")
            
            c1, c2, c3, c4 = st.columns(4)
            p_f_d = c1.number_input("五D", 0, 10, 4, key="p_f_d")
            p_f_e = c2.number_input("五E", 0, 10, 2, key="p_f_e")
            p_f_n = c3.number_input("五N", 0, 10, 2, key="p_f_n")
            p_f_18 = c4.number_input("五1-8", 0, 10, 1, key="p_f_18")
            
            c1, c2, c3 = st.columns(3)
            p_we_d = c1.number_input("假D", 0, 10, 3, key="p_we_d")
            p_we_e = c2.number_input("假E", 0, 10, 2, key="p_we_e")
            p_we_n = c3.number_input("假N", 0, 10, 2, key="p_we_n")
            
    with st.expander("📁 Excel 智慧匯入/匯出", expanded=False): 0, 10, 2)
    
    with st.expander("📁 Excel 智慧匯入/匯出", expanded=False):
        template_data = []
        date_row = {"姓名": "日期", "屬性": "", "上月最後班": "", "月底連上天數": ""}
        for d in range(1, num_days + 1): date_row[str(d)] = f"{month}/{d}"
        template_data.append(date_row)
        week_row = {"姓名": "星期", "屬性": "", "上月最後班": "", "月底連上天數": ""}
        weekdays_map = {0: '一', 1: '二', 2: '三', 3: '四', 4: '五', 5: '六', 6: '日'}
        for d in range(1, num_days + 1): week_row[str(d)] = weekdays_map[calendar.weekday(year, month, d)]
        template_data.append(week_row)

        for n in all_staff:
            row = {"姓名": n, "屬性": st.session_state.fixed.get(n, "無 (混合)"), "上月最後班": st.session_state.prev_status.get(n, {}).get("shift", "Off"), "月底連上天數": st.session_state.prev_streak.get(n, 0)}
            for d in range(1, num_days + 1): row[str(d)] = st.session_state.daily_shifts.get(n, {}).get(d, "")
            template_data.append(row)
            
        df_template = pd.DataFrame(template_data)
        output_template = io.BytesIO()
        with pd.ExcelWriter(output_template, engine='xlsxwriter') as writer: df_template.to_excel(writer, index=False, sheet_name='預班表')
        st.download_button("📥 下載 Excel 預班表", output_template.getvalue(), f"{year}年{month}月_打碼預班表.xlsx", type="primary", use_container_width=True)
        
        uploaded_file = st.file_uploader("上傳 Excel", type=["xlsx", "csv"], label_visibility="collapsed")
        if uploaded_file is not None:
            if st.button("🚀 執行智慧匯入", use_container_width=True):
                try:
                    df_in = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                    df_in.columns = df_in.columns.astype(str).str.strip(); df_in = df_in.fillna("")
                    for index, row in df_in.iterrows():
                        name = str(row.get("姓名", "")).strip()
                        if not name or "星期" in name or "日期" in name or "計" in name or "組" in name: continue 
                        if name not in all_staff: continue 
                        
                        prop_col = "屬性" if "屬性" in df_in.columns else None
                        if prop_col:
                            fv = str(row[prop_col]).strip().upper()
                            new_fix = "新人 (純白班)" if any(x in fv for x in ['新', '純白']) else ("固定白 (D)" if any(x in fv for x in ['D', '白']) else ("固定小 (E)" if any(x in fv for x in ['E', '小']) else ("固定大 (N)" if any(x in fv for x in ['N', '大']) else "無 (混合)")))
                            st.session_state.fixed[name] = new_fix
                        
                        last_col = "上月最後班" if "上月最後班" in df_in.columns else None
                        if last_col:
                            lv = str(row[last_col]).strip().upper()
                            new_lv = 'Off' if any(x in lv for x in ['OFF', '休', '0', 'O']) else ('D' if 'D' in lv else ('L' if 'L' in lv else ('E' if 'E' in lv else ('N' if 'N' in lv else 'Off'))))
                            st.session_state.prev_status[name] = {'shift': new_lv}

                        streak_col = "月底連上天數" if "月底連上天數" in df_in.columns else None
                        if streak_col:
                            try: st.session_state.prev_streak[name] = int(float(str(row[streak_col]).strip()))
                            except: st.session_state.prev_streak[name] = 0
                        
                        st.session_state.daily_shifts[name] = {}
                        for d in range(1, num_days + 1):
                            val = str(row.get(str(d), row.get(f"{month}/{d}", ""))).strip().upper()
                            if val:
                                if val in ['OFF', '休', '0', 'O', 'OF']: val = 'Off'
                                elif val in ['48', '4-8']: val = '4-8'
                                elif val in ['18', '1-8']: val = '1-8'  
                                elif val in ['128', '12-8']: val = '12-8'
                                elif val in ['812', '8-12']: val = '8-12'
                                elif val in ['M', '行政']: val = 'M'
                                elif val in ['公', '公假']: val = '公'
                                elif val in ['L', 'LEADER']: val = 'L'
                                elif val in ['NDD', 'ND-D', '支援白']: val = 'ND-D'
                                elif val in ['NDE', 'ND-E', '支援小']: val = 'ND-E'
                                elif val in ['NDN', 'ND-N', '支援大夜']: val = 'ND-N'
                                if val in SHIFTS: st.session_state.daily_shifts[name][d] = val
                    st.success("✅ 匯入成功！"); st.rerun()
                except Exception as e: st.error(f"檔案讀取失敗: {e}")

    with st.expander("👥 人員名單設定", expanded=False):
        with st.form("staff_form"):
            new_heme = st.text_area("🩸 血腫組", value="\n".join(heme_staff), height=150)
            new_pall = st.text_area("🕊️ 安寧組", value="\n".join(pall_staff), height=200)
            new_hn = st.text_input("👩‍⚕️ 護理長", value=hn_name)
            if st.form_submit_button("💾 儲存"):
                staff_data['heme'] = [x.strip() for x in new_heme.split('\n') if x.strip()]; staff_data['pall'] = [x.strip() for x in new_pall.split('\n') if x.strip()]; staff_data['hn'] = new_hn.strip(); save_staff_data(staff_data); st.rerun()
    
    with st.expander("👑 Leader 設定", expanded=False):
        with st.form("leader_form"):
            new_h_seniors = st.multiselect("🩸 血腫資深", heme_staff, default=[x for x in heme_seniors if x in heme_staff])
            new_p_seniors = st.multiselect("🕊️ 安寧資深", pall_staff, default=[x for x in pall_seniors if x in pall_staff])
            if st.form_submit_button("💾 儲存"): staff_data['heme_seniors'] = new_h_seniors; staff_data['pall_seniors'] = new_p_seniors; save_staff_data(staff_data); st.rerun()

    allowed_off_gap = st.slider("⚖️ 允許休假天數最大落差", 0, 10, 4)
    allow_iso_work = st.checkbox("🌟 允許單日上班", value=True)
    shift_consistency_weight = st.slider("🔀 班別一致性", 0, 1000, 500)
    anti_frag_weight = st.slider("🛡️ 護肝指數", 0, 500, 200)
    soft_max_streak = st.slider("💡 期望最多連上天數", 3, 7, 4)
    hard_max_streak = st.slider("🛑 絕對極限連上天數", 3, 7, 5)
    min_bonus_days = st.number_input("💰 包班最低達標天數", 1, 31, 15)
    holiday_dates = st.multiselect("國定假日", list(range(1, num_days+1)))

def render_staff_card(name, year, month, is_hn=False):
    fix_status = st.session_state.fixed.get(name, "無")
    icon = "👑" if is_hn else ("🐣" if "新" in fix_status else ("☀️" if "白" in fix_status else ("🌙" if "小" in fix_status else ("✨" if "大" in fix_status else "🟢"))))
    with st.expander(f"{icon} {name}  |  狀態: {fix_status}", expanded=False):
        if not is_hn:
            c1, c2, c3 = st.columns([1, 1, 1.2])
            with c1: st.session_state.prev_status[name]['shift'] = st.selectbox("上月最後班", ['Off', 'D', 'E', 'N', 'L', 'ND-D', 'ND-E', 'ND-N'], index=['Off', 'D', 'E', 'N', 'L', 'ND-D', 'ND-E', 'ND-N'].index(st.session_state.prev_status.get(name, {}).get('shift', 'Off')), key=f"ps_{name}")
            with c2: st.session_state.prev_streak[name] = st.number_input("月底連上天數", 0, 15, value=st.session_state.prev_streak.get(name, 0), key=f"streak_{name}")
            with c3: st.session_state.fixed[name] = st.selectbox("屬性", ["無 (混合)", "固定白 (D)", "固定小 (E)", "固定大 (N)", "新人 (純白班)"], index=["無 (混合)", "固定白 (D)", "固定小 (E)", "固定大 (N)", "新人 (純白班)"].index(st.session_state.fixed.get(name, "無 (混合)")), key=f"fix_{name}")
        st.divider()
        cols = st.columns(7)
        for i, w in enumerate(['一', '二', '三', '四', '五', '六', '日']): cols[i].markdown(f"<div style='text-align: center; color: gray'>{w}</div>", unsafe_allow_html=True)
        for week in calendar.monthcalendar(year, month):
            cols = st.columns(7)
            for i, day in enumerate(week):
                with cols[i]:
                    if day != 0:
                        v = st.session_state.daily_shifts.get(name, {}).get(day)
                        st.button(f"{day}\n{v}" if v else ("🔴"+str(day) if day in holiday_dates else str(day)), key=f"b_{name}_{day}", type="primary" if v else "secondary", use_container_width=True)

tab_heme, tab_pall, tab_run = st.tabs(["🩸 血腫組", "🕊️ 安寧組", "🚀 產生班表"])
with tab_heme: 
    for name in heme_staff: render_staff_card(name, year, month)
with tab_pall:
    for name in pall_staff: render_staff_card(name, year, month)
    st.divider(); render_staff_card(hn_name, year, month, True)

with tab_run:
    if st.button("🚀 啟動排班", type="primary", use_container_width=True):
        with st.spinner("神經網路運算中..."):
            model = cp_model.CpModel(); work = {}; first_wd, num_days = calendar.monthrange(year, month)
            for n in active_staff:
                for d in range(1, num_days+1):
                    for s in range(len(SHIFTS)): work[(n,d,s)] = model.NewBoolVar(f'w_{n}_{d}_{s}')
                    model.Add(sum(work[(n,d,s)] for s in range(len(SHIFTS))) == 1)

            fragmentation_penalties = []; shift_changes = []; streak_penalties = []
            for n in active_staff:
                user_shifts = st.session_state.daily_shifts.get(n, {}); f_type = st.session_state.fixed.get(n, "")
                for d, s_val in user_shifts.items():
                    if s_val in SHIFTS: model.Add(work[(n, d, SHIFTS.index(s_val))] == 1)
                for d in range(1, num_days+1):
                    if user_shifts.get(d) != 'M': model.Add(work[(n, d, SHIFTS.index('M'))] == 0)
                    if user_shifts.get(d) != '公': model.Add(work[(n, d, SHIFTS.index('公'))] == 0)
                    if user_shifts.get(d) not in ['ND-D', 'ND-E', 'ND-N']: 
                        for nd_idx in [11, 12, 13]: model.Add(work[(n, d, nd_idx)] == 0)

                if "白" in f_type and "新" not in f_type:
                    for d in range(1, num_days+1): 
                        if d not in user_shifts:
                            for s_idx in [2, 3, 4, 5, 6, 7]: model.Add(work[(n,d,s_idx)]==0) 
                
                # --- 核心：固定E班保護網 ---
                elif "小" in f_type:
                    for d in range(1, num_days+1): 
                        if d not in user_shifts:
                            # 絕對禁止 1(D), 3(N), 4(12-8), 5(4-8), 6(8-12), 7(1-8), 8(M), 10(L)
                            for s_idx in [1, 3, 4, 5, 6, 7, 8, 10]: model.Add(work[(n,d,s_idx)]==0) 
                    model.Add(sum(work[(n, d, 2)] for d in range(1, num_days+1)) >= 15)
                # -------------------------

                elif "大" in f_type:
                    for d in range(1, num_days+1): 
                        if d not in user_shifts:
                            for s_idx in [1, 2, 4, 5, 6, 7, 8, 9, 10]: model.Add(work[(n,d,s_idx)]==0) 
                elif "新" in f_type:
                    for d in range(1, num_days+1):
                        if d not in user_shifts:
                            for s_idx in [2, 3, 4, 5, 6, 7, 8, 9, 10]: model.Add(work[(n,d,s_idx)]==0)

                for d in range(1, num_days):
                    if d in user_shifts and (d+1) in user_shifts: continue 
                    for day_shift in [1, 6, 8, 9, 10, 11]: model.Add(work[(n, d, 2)] + work[(n, d+1, day_shift)] <= 1)
                    for prev_shift in [1, 2, 4, 5, 6, 7, 8, 9, 10]: model.Add(work[(n, d, prev_shift)] + work[(n, d+1, 3)] <= 1)

                for d in range(1, num_days):
                    for s1 in range(1, len(SHIFTS)):
                        for s2 in range(1, len(SHIFTS)):
                            if s1 != s2 and not (s1 in [1, 10] and s2 in [1, 10]):
                                cv = model.NewBoolVar(f'sc_{n}_{d}_{s1}_{s2}')
                                model.Add(cv >= work[(n, d, s1)] + work[(n, d+1, s2)] - 1)
                                shift_changes.append(cv)

                window_size = hard_max_streak + 1
                for d in range(1, num_days - window_size + 2):
                    if all((d+k) not in user_shifts or user_shifts[d+k] != 'Off' for k in range(window_size)): model.Add(sum(work[(n, d+k, 0)] for k in range(window_size)) >= 1)

                W = [0 if st.session_state.prev_status.get(n, {}).get('shift', 'Off') == 'Off' else 1]
                for d in range(1, num_days+1):
                    w_d = model.NewBoolVar(f'W_{n}_{d}')
                    model.Add(w_d == sum(work[(n, d, s)] for s in range(1, len(SHIFTS))))
                    W.append(w_d)
                W.append(model.NewBoolVar(f'W_{n}_last')); model.Add(W[-1] == W[-2])
                
                for d in range(1, num_days+1):
                    iso_off = model.NewBoolVar(f'iso_off_{n}_{d}')
                    model.Add(iso_off >= W[d-1] - W[d] + W[d+1] - 1)
                    fragmentation_penalties.append(iso_off)

            shortfall_vars = []; surplus_vars = [] 
            def add_exact_demand(staff_list, day, shift_indices, target_count):
                sf = model.NewIntVar(0, target_count, f'sf_{day}_{shift_indices}_{id(staff_list)}')
                surp = model.NewIntVar(0, len(staff_list), f'surp_{day}_{shift_indices}_{id(staff_list)}')
                model.Add(sum(work[(n, day, s)] for n in staff_list for s in shift_indices) + sf - surp == target_count)
                shortfall_vars.append(sf); surplus_vars.append(surp)

            leader_shortfalls = []; valid_seniors = list(set([n for n in heme_seniors if n in heme_staff] + [n for n in pall_seniors if n in pall_staff]))

            for d in range(1, num_days+1):
                wd = (first_wd + d - 1) % 7; is_h = (d in holiday_dates); is_w = (wd < 5) 
                if wd < 5 and not is_h:
                    if h_wd_d > 0: add_exact_demand(heme_staff, d, [1], h_wd_d)
                    if h_wd_e > 0: add_exact_demand(heme_staff, d, [2], h_wd_e)
                    if h_wd_n > 0: add_exact_demand(heme_staff, d, [3], h_wd_n)
                    if h_wd_48 > 0: add_exact_demand(heme_staff, d, [5], h_wd_48)
                elif wd == 5 and not is_h:
                    if h_sa_d > 0: add_exact_demand(heme_staff, d, [1], h_sa_d)
                    if h_sa_e > 0: add_exact_demand(heme_staff, d, [2], h_sa_e)
                    if h_sa_n > 0: add_exact_demand(heme_staff, d, [3], h_sa_n)
                    if h_sa_812 > 0: add_exact_demand(heme_staff, d, [6], h_sa_812)
                else:
                    if h_su_d > 0: add_exact_demand(heme_staff, d, [1], h_su_d)
                    if h_su_e > 0: add_exact_demand(heme_staff, d, [2], h_su_e)
                    if h_su_n > 0: add_exact_demand(heme_staff, d, [3], h_su_n)

                if wd < 4 and not is_h:
                    if p_mth_d > 0: add_exact_demand(pall_staff, d, [1], p_mth_d)
                    if p_mth_e > 0: add_exact_demand(pall_staff, d, [2], p_mth_e)
                    if p_mth_n > 0: add_exact_demand(pall_staff, d, [3], p_mth_n)
                    if p_mth_48 > 0: add_exact_demand(pall_staff, d, [5], p_mth_48)
                    if p_mth_18 > 0: add_exact_demand(pall_staff, d, [7], p_mth_18)
                elif wd == 4 and not is_h:
                    if p_f_d > 0: add_exact_demand(pall_staff, d, [1], p_f_d)
                    if p_f_e > 0: add_exact_demand(pall_staff, d, [2], p_f_e)
                    if p_f_n > 0: add_exact_demand(pall_staff, d, [3], p_f_n)
                    if p_f_18 > 0: add_exact_demand(pall_staff, d, [7], p_f_18)
                else:
                    if p_we_d > 0: add_exact_demand(pall_staff, d, [1], p_we_d)
                    if p_we_e > 0: add_exact_demand(pall_staff, d, [2], p_we_e)
                    if p_we_n > 0: add_exact_demand(pall_staff, d, [3], p_we_n)

                if is_w:
                    for n in active_staff:
                        if n not in valid_seniors and st.session_state.daily_shifts.get(n, {}).get(d) != 'L': model.Add(work[(n, d, 10)] == 0)
                    sf_l = model.NewIntVar(0, 1, f'sf_l_{d}')
                    model.Add(sum(work[(n, d, 10)] for n in valid_seniors) + sf_l >= 1)
                    leader_shortfalls.append((d, sf_l))
                else:
                    for n in active_staff:
                        if st.session_state.daily_shifts.get(n, {}).get(d) != 'L': model.Add(work[(n, d, 10)] == 0)

            max_off_var = model.NewIntVar(0, 31, 'max_off'); min_off_var = model.NewIntVar(0, 31, 'min_off')
            for n in active_staff:
                offs = sum(work[(n,d,0)] for d in range(1, num_days+1))
                model.Add(max_off_var >= offs); model.Add(min_off_var <= offs)
            fairness_gap = max_off_var - min_off_var
            excess_gap = model.NewIntVar(0, 31, 'excess_gap'); model.Add(excess_gap >= fairness_gap - allowed_off_gap)

            model.Maximize(
                sum(work[(n,d,0)] for n in active_staff for d in range(1, num_days+1)) * 10 
                - sum(shortfall_vars) * 1000000 
                - sum(surplus_vars) * 8000 
                - sum(sf for d, sf in leader_shortfalls) * 500000
                - sum(shift_changes) * shift_consistency_weight 
                - sum(fragmentation_penalties) * anti_frag_weight 
                - excess_gap * 1000 - fairness_gap * 5   
            )

            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = 30
            status = solver.Solve(model)

            if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                excel_data = []; display_data = {} 
                excel_data.append(['姓名', '屬性', '上月', '天數'] + [f"{month}/{d}" for d in range(1, num_days+1)] + ['OFF', 'N', 'E', '包班'])
                excel_data.append(['星期', '', '', ''] + [{'0':'一', '1':'二', '2':'三', '3':'四', '4':'五', '5':'六', '6':'日'}[str(calendar.weekday(year, month, d))] for d in range(1, num_days+1)] + ['', '', '', ''])
                
                global_n, global_d, global_e = [0.0]*num_days, [0.0]*num_days, [0.0]*num_days
                for group_name, staff_list, short_name in [('🩸 【血腫組】', heme_staff, '血腫'), ('🕊️ 【安寧組】', pall_staff, '安寧'), ('👩‍⚕️ 【護理長】', [hn_name], '護理長')]:
                    excel_data.append([group_name] + [''] * (len(excel_data[0]) - 1))
                    grp_n, grp_d, grp_e = [0.0]*num_days, [0.0]*num_days, [0.0]*num_days
                    
                    for n in staff_list:
                        row_shifts = []
                        for d in range(1, num_days+1):
                            assigned = 'Off'
                            if n == hn_name: assigned = st.session_state.daily_shifts.get(n, {}).get(d, 'Off')
                            else:
                                for s in range(len(SHIFTS)):
                                    if solver.Value(work[(n,d,s)]) == 1: assigned = SHIFTS[s]; break
                            row_shifts.append(assigned)
                            if n != hn_name:
                                if assigned in ['N', 'ND-N']: grp_n[d-1] += 1; global_n[d-1] += 1
                                elif assigned in ['D', 'L']: grp_d[d-1] += 1; global_d[d-1] += 1
                                elif assigned == '8-12': grp_d[d-1] += 0.5; global_d[d-1] += 0.5
                                elif assigned in ['E', '12-8', 'ND-E']: grp_e[d-1] += 1; global_e[d-1] += 1
                                elif assigned in ['4-8', '1-8']: grp_e[d-1] += 0.5; global_e[d-1] += 0.5
                        
                        # 加入 ND 統計
                        n_count = row_shifts.count('N') + row_shifts.count('ND-N')
                        e_count = fmt_num(row_shifts.count('E') + row_shifts.count('12-8') + row_shifts.count('ND-E') + 0.5*(row_shifts.count('4-8') + row_shifts.count('1-8')))
                        excel_data.append([n, st.session_state.fixed.get(n, "無 (混合)"), st.session_state.prev_status.get(n, {}).get('shift', 'Off'), st.session_state.prev_streak.get(n, 0)] + row_shifts + [row_shifts.count('Off'), n_count, e_count, '-'])
                    
                    if short_name != '護理長':
                        excel_data.append([f'{short_name}-N小計', '', '', ''] + [fmt_num(x) for x in grp_n] + ['', '', '', ''])
                        excel_data.append([f'{short_name}-D小計', '', '', ''] + [fmt_num(x) for x in grp_d] + ['', '', '', ''])
                        excel_data.append([f'{short_name}-E小計', '', '', ''] + [fmt_num(x) for x in grp_e] + ['', '', '', ''])

                excel_data.append([''] * len(excel_data[0]))
                excel_data.append(['全站總計 N', '', '', ''] + [fmt_num(x) for x in global_n] + ['', '', '', ''])
                excel_data.append(['全站總計 D', '', '', ''] + [fmt_num(x) for x in global_d] + ['', '', '', ''])
                excel_data.append(['全站總計 E', '', '', ''] + [fmt_num(x) for x in global_e] + ['', '', '', ''])
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer: pd.DataFrame(excel_data).to_excel(writer, sheet_name='總表', header=False, index=False)
                st.success("✅ 排班完成！支援班與固定E班已完美整合。"); st.download_button("📥 下載總表", output.getvalue(), f"{year}年{month}月_排班表.xlsx")
            else: st.error("❌ 無解！(條件衝突，請調整人力需求或預排假)")
