import streamlit as st
import pandas as pd
import calendar
from ortools.sat.python import cp_model
import io
import json
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- 1. 頁面設定 ---
st.set_page_config(page_title="護理站智慧整合系統", layout="wide")

# --- 2. 員工資料庫 (原編對應) ---
EMP_DB = {
    "05768": "血腫-蔡O樺", "10054": "血腫-吳O茹", "13218": "血腫-張O葳", 
    "13598": "血腫-葉O菁", "13717": "血腫-蔡O蓁", "16148": "血腫-呂O岑", 
    "16623": "血腫-洪O蔚",
    "03125": "安寧-龔O如", "04009": "安寧-葉O敏", "13217": "安寧-沈O叡", 
    "12820": "安寧-張O嘉", "13736": "安寧-許O禎", "13533": "安寧-吳O萍", 
    "15783": "安寧-劉O君", "16147": "安寧-鐘O淇", "16391": "安寧-洪O安", 
    "16449": "安寧-陳O柔", "16625": "安寧-黃O柔", "16663": "安寧-李O軒",
    "03059": "護理長-林O穎"
}

if 'logged_in_user' not in st.session_state:
    st.session_state.logged_in_user = None

# --- 3. 側邊欄入口選擇器 ---
page = st.sidebar.radio("請選擇系統模式", ["🏥 阿長排班系統", "📝 護理師劃假入口"])

# ==========================================
# 模式一：護理師劃假入口 (2.0 登入版 + 月曆)
# ==========================================
if page == "📝 護理師劃假入口":
    st.title("📝 護理師專屬劃假網頁")
    
    if "google_sheets_key" in st.secrets:
        # 連接 Google Sheets
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["google_sheets_key"], 
                ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
        client = gspread.authorize(creds)
        sheet = client.open_by_key("1C5iM_4aqANm4z9mXZzrMZ3vbQLcj4O_wL2_AJK5BjsU").sheet1
        
        # --- 登入畫面 ---
        if st.session_state.logged_in_user is None:
            st.markdown("### 🔒 系統登入")
            emp_id = st.text_input("請輸入您的員工編號", type="password")
            if st.button("登入", type="primary"):
                if emp_id in EMP_DB:
                    st.session_state.logged_in_user = EMP_DB[emp_id]
                    st.rerun()
                else:
                    st.error("❌ 找不到此員工編號，請重新確認。")
        
        # --- 登入後的月曆劃假畫面 ---
        else:
            name = st.session_state.logged_in_user
            
            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(f"### 👩‍⚕️ 歡迎，**{name}**")
            with c2:
                if st.button("登出系統"):
                    st.session_state.logged_in_user = None
                    st.rerun()
            
            st.divider()
            st.markdown("#### 📅 選擇預假日期 (彈出式月曆)")
            
            selected_date = st.date_input("點擊下方選擇日期：", value=datetime.today())
            shift = st.selectbox("您要劃什麼班？", ["Off", "D", "E", "N", "4-8", "1-8"])
            
            # 格式化日期，方便之後阿長匯入 Excel 看得懂
            date_str = f"{selected_date.month}/{selected_date.day}"
            
            if st.button("送出劃假申請", type="primary"):
                sheet.append_row([pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"), name, date_str, shift])
                st.success(f"✅ 成功！已將 **{name}** 在 **{date_str}** 的班別記錄為 **{shift}**。")
                st.balloons()
    else:
        st.error("⚠️ 系統尚未設定 Google Sheets 金鑰。")

# ==========================================
# 模式二：阿長排班系統 (5.8 嚴格邏輯版)
# ==========================================
else:
    st.title("🏥 智慧護理排班系統 (5.8 嚴格邏輯純淨版)")

    # --- CSS 設計 ---
    st.markdown("""
        <style>
        [data-testid="stSidebar"] { left: unset; right: 0; border-left: 1px solid #f0f2f6; }
        [data-testid="stSidebarCollapsedControl"] { left: unset; right: 10px; }
        .stButton button { font-weight: bold; border-radius: 8px; cursor: default; }
        .magic-btn button { background-color: #ff4b4b; color: white; border: 2px solid #ff4b4b; }
        </style>
    """, unsafe_allow_html=True)

    # --- 預設名單 ---
    DEFAULT_HEME = ['血腫-蔡O樺', '血腫-吳O茹', '血腫-張O葳', '血腫-葉O菁', '血腫-蔡O蓁', '血腫-呂O岑', '血腫-洪O蔚']
    DEFAULT_PALL = ['安寧-龔O如', '安寧-葉O敏', '安寧-沈O叡', '安寧-張O嘉', '安寧-許O禎', '安寧-吳O萍', '安寧-劉O君', '安寧-鐘O淇', '安寧-洪O安', '安寧-陳O柔', '安寧-黃O柔', '安寧-李O軒']
    DEFAULT_HN = '護理長-林O穎'

    def load_staff_data():
        data = {
            "heme": DEFAULT_HEME, "pall": DEFAULT_PALL, "hn": DEFAULT_HN,
            "heme_seniors": ['血腫-蔡O樺', '血腫-吳O茹'], 
            "pall_seniors": ['安寧-龔O如', '安寧-葉O敏']
        }
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
            with open('staff_v5.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except: pass

    staff_data = load_staff_data()
    heme_staff = staff_data.get('heme', DEFAULT_HEME)
    pall_staff = staff_data.get('pall', DEFAULT_PALL)
    hn_name = staff_data.get('hn', DEFAULT_HN)
    heme_seniors = staff_data.get('heme_seniors', [])
    pall_seniors = staff_data.get('pall_seniors', [])

    active_staff = heme_staff + pall_staff 
    all_staff = active_staff + [hn_name]

    SHIFTS = ['Off', 'D', 'E', 'N', '12-8', '4-8', '8-12', '1-8', 'M', '公', 'L']

    def fmt_num(n):
        return int(n) if n == int(n) else n

    # --- 狀態初始化 ---
    if 'daily_shifts' not in st.session_state: st.session_state.daily_shifts = {n: {} for n in all_staff}
    if 'fixed' not in st.session_state: st.session_state.fixed = {n: "無 (混合)" for n in all_staff}
    if 'prev_status' not in st.session_state: st.session_state.prev_status = {n: {'shift': 'Off'} for n in all_staff}
    if 'prev_streak' not in st.session_state: st.session_state.prev_streak = {n: 0 for n in all_staff}

    # --- 側邊欄 ---
    with st.sidebar:
        st.header("⚙️ 排班系統控制台")
        
        year = st.number_input("年份", 2025, 2030, 2026)
        month = st.number_input("月份", 1, 12, 6) 
        _, num_days = calendar.monthrange(year, month)
        
        with st.expander("👥 每日人力需求調整", expanded=True):
            tab_h, tab_p = st.tabs(["🩸 血腫組", "🕊️ 安寧組"])
            
            with tab_h:
                st.write("【平日 (週一 ~ 週五)】")
                c1, c2, c3, c4 = st.columns(4)
                h_wd_d = c1.number_input("D", 0, 10, 2, key="h_wd_d")
                h_wd_e = c2.number_input("E", 0, 10, 1, key="h_wd_e")
                h_wd_n = c3.number_input("N", 0, 10, 1, key="h_wd_n")
                h_wd_48 = c4.number_input("4-8", 0, 10, 1, key="h_wd_48")
                
                st.write("【週六】")
                c1, c2, c3, c4 = st.columns(4)
                h_sa_d = c1.number_input("D", 0, 10, 1, key="h_sa_d")
                h_sa_e = c2.number_input("E", 0, 10, 1, key="h_sa_e")
                h_sa_n = c3.number_input("N", 0, 10, 1, key="h_sa_n")
                h_sa_812 = c4.number_input("8-12", 0, 10, 1, key="h_sa_812")
                
                st.write("【週日 / 國定假日】")
                c1, c2, c3 = st.columns(3)
                h_su_d = c1.number_input("D ", 0, 10, 1, key="h_su_d")
                h_su_e = c2.number_input("E ", 0, 10, 1, key="h_su_e")
                h_su_n = c3.number_input("N ", 0, 10, 1, key="h_su_n")

            with tab_p:
                st.write("【平日 (週一 ~ 週四)】")
                c1, c2, c3 = st.columns(3)
                p_mth_d = c1.number_input("D", 0, 10, 4, key="p_mth_d")
                p_mth_e = c2.number_input("E", 0, 10, 2, key="p_mth_e")
                p_mth_n = c3.number_input("N", 0, 10, 2, key="p_mth_n")
                c4, c5, c6 = st.columns(3)
                p_mth_48 = c4.number_input("4-8", 0, 10, 1, key="p_mth_48")
                p_mth_18 = c5.number_input("1-8", 0, 10, 0, key="p_mth_18")
                
                st.write("【週五】")
                c1, c2, c3, c4 = st.columns(4)
                p_f_d = c1.number_input("D", 0, 10, 4, key="p_f_d")
                p_f_e = c2.number_input("E", 0, 10, 2, key="p_f_e")
                p_f_n = c3.number_input("N", 0, 10, 2, key="p_f_n")
                p_f_18 = c4.number_input("1-8", 0, 10, 1, key="p_f_18")
                
                st.write("【週末 / 國定假日】")
                c1, c2, c3 = st.columns(3)
                p_we_d = c1.number_input("D ", 0, 10, 3, key="p_we_d")
                p_we_e = c2.number_input("E ", 0, 10, 2, key="p_we_e")
                p_we_n = c3.number_input("N ", 0, 10, 2, key="p_we_n")
    
        with st.expander("📁 Excel 智慧匯入/匯出", expanded=False):
            st.write("**第一步：下載公版 (含目前設定)**")
            template_data = []
            
            date_row = {"姓名": "日期", "屬性": "", "上月最後班": "", "月底連上天數": ""}
            for d in range(1, num_days + 1): date_row[str(d)] = f"{month}/{d}"
            template_data.append(date_row)
            
            week_row = {"姓名": "星期", "屬性": "", "上月最後班": "", "月底連上天數": ""}
            weekdays_map = {0: '一', 1: '二', 2: '三', 3: '四', 4: '五', 5: '六', 6: '日'}
            for d in range(1, num_days + 1): week_row[str(d)] = weekdays_map[calendar.weekday(year, month, d)]
            template_data.append(week_row)

            for n in all_staff:
                row = {
                    "姓名": n,
                    "屬性": st.session_state.fixed.get(n, "無 (混合)"),
                    "上月最後班": st.session_state.prev_status.get(n, {}).get("shift", "Off"),
                    "月底連上天數": st.session_state.prev_streak.get(n, 0)
                }
                for d in range(1, num_days + 1):
                    row[str(d)] = st.session_state.daily_shifts.get(n, {}).get(d, "")
                template_data.append(row)
                
            df_template = pd.DataFrame(template_data)
            output_template = io.BytesIO()
            
            with pd.ExcelWriter(output_template, engine='xlsxwriter') as writer:
                df_template.to_excel(writer, index=False, sheet_name='預班表')
                workbook = writer.book
                worksheet = writer.sheets['預班表']
                
                weekend_format = workbook.add_format({'bg_color': '#FFF2CC', 'align': 'center'}) 
                weekday_format = workbook.add_format({'align': 'center'})
                
                worksheet.set_column('A:A', 14)
                worksheet.set_column('B:B', 12)
                worksheet.set_column('C:D', 10) 
                
                for d in range(1, num_days + 1):
                    wd = calendar.weekday(year, month, d)
                    col_idx = 3 + d 
                    if wd >= 5: worksheet.set_column(col_idx, col_idx, 6, weekend_format)
                    else: worksheet.set_column(col_idx, col_idx, 6, weekday_format)
                worksheet.freeze_panes(2, 4)
                
            st.download_button("📥 下載 Excel 預班表", output_template.getvalue(), f"{year}年{month}月_打碼預班表.xlsx", type="primary", use_container_width=True)
            
            st.write("---")
            st.write("**第二步：上傳排好的 Excel**")
            uploaded_file = st.file_uploader("上傳 Excel 或 CSV", type=["xlsx", "csv"], label_visibility="collapsed")
            if uploaded_file is not None:
                if st.button("🚀 執行智慧匯入", use_container_width=True):
                    try:
                        if uploaded_file.name.endswith('.csv'): df_in = pd.read_csv(uploaded_file)
                        else: df_in = pd.read_excel(uploaded_file)
                        
                        df_in.columns = df_in.columns.astype(str).str.strip()
                        df_in = df_in.fillna("")
                        not_found_names = [] 
                        
                        for index, row in df_in.iterrows():
                            name = str(row.get("姓名", "")).strip()
                            if not name or "星期" in name or "日期" in name or "總計" in name or "小計" in name or "血腫" in name and "組" in name or "安寧" in name and "組" in name or "護理長" in name and "】" in name: 
                                continue 
                            if name not in all_staff:
                                not_found_names.append(name)
                                continue 
                                
                            prop_col = "屬性" if "屬性" in df_in.columns else ("班別" if "班別" in df_in.columns else ("固定班" if "固定班" in df_in.columns else None))
                            if prop_col:
                                fv = str(row[prop_col]).strip().upper()
                                if any(x in fv for x in ['新', '純白']): new_fix = "新人 (純白班)"
                                elif any(x in fv for x in ['D', '白']): new_fix = "固定白 (D)"
                                elif any(x in fv for x in ['E', '小']): new_fix = "固定小 (E)"
                                elif any(x in fv for x in ['N', '大']): new_fix = "固定大 (N)"
                                else: new_fix = "無 (混合)"
                                st.session_state.fixed[name] = new_fix
                                st.session_state[f"fix_{name}"] = new_fix 
                            
                            last_col = "上月" if "上月" in df_in.columns else ("上月最後班" if "上月最後班" in df_in.columns else None)
                            if last_col:
                                lv = str(row[last_col]).strip().upper()
                                if any(x in lv for x in ['OFF', '休', '0', 'O']): new_lv = 'Off'
                                elif 'D' in lv: new_lv = 'D'
                                elif 'L' in lv: new_lv = 'L'
                                elif 'E' in lv: new_lv = 'E'
                                elif 'N' in lv: new_lv = 'N'
                                else: new_lv = 'Off'
                                st.session_state.prev_status[name] = {'shift': new_lv}
                                st.session_state[f"ps_{name}"] = new_lv 

                            streak_col = "天數" if "天數" in df_in.columns else ("月底連上天數" if "月底連上天數" in df_in.columns else None)
                            if streak_col:
                                streak_val = str(row[streak_col]).strip()
                                try:
                                    sv = int(float(streak_val))
                                    st.session_state.prev_streak[name] = sv
                                    st.session_state[f"streak_{name}"] = sv
                                except:
                                    st.session_state.prev_streak[name] = 0
                                    st.session_state[f"streak_{name}"] = 0
                            
                            st.session_state.daily_shifts[name] = {}
                            for d in range(1, num_days + 1):
                                col_str = str(d)
                                date_col_str = f"{month}/{d}"
                                
                                val = ""
                                if col_str in df_in.columns: val = str(row[col_str]).strip().upper()
                                elif date_col_str in df_in.columns: val = str(row[date_col_str]).strip().upper()
                                
                                if val:
                                    if val in ['OFF', '休', '0', 'O', 'OF']: val = 'Off'
                                    elif val in ['48', '4-8']: val = '4-8'
                                    elif val in ['18', '1-8']: val = '1-8'  
                                    elif val in ['128', '12-8']: val = '12-8'
                                    elif val in ['812', '8-12']: val = '8-12'
                                    elif val in ['M', '行政']: val = 'M'
                                    elif val in ['公', '公假']: val = '公'
                                    elif val in ['L', 'LEADER']: val = 'L'
                                    if val in SHIFTS:
                                        st.session_state.daily_shifts[name][d] = val
                        
                        if not_found_names: st.error(f"🚨 警告！Excel 裡這些名字對不上：{', '.join(not_found_names)}")
                        else: st.success("✅ 匯入成功！")
                    except Exception as e:
                        st.error(f"檔案讀取失敗: {e}")
                    st.rerun()

        with st.expander("👥 人員名單設定", expanded=False):
            st.write("在此新增或刪除人員：")
            with st.form("staff_form"):
                new_heme = st.text_area("🩸 血腫組", value="\n".join(heme_staff), height=150)
                new_pall = st.text_area("🕊️ 安寧組", value="\n".join(pall_staff), height=200)
                new_hn = st.text_input("👩‍⚕️ 護理長", value=hn_name)
                if st.form_submit_button("💾 儲存人員名單"):
                    staff_data['heme'] = [x.strip() for x in new_heme.split('\n') if x.strip()]
                    staff_data['pall'] = [x.strip() for x in new_pall.split('\n') if x.strip()]
                    staff_data['hn'] = new_hn.strip()
                    save_staff_data(staff_data)
                    st.success("名單已儲存！請重整網頁套用新名單。")
                    st.rerun()

        with st.expander("👑 白班 Leader (資深人員) 設定", expanded=False):
            st.write("勾選可擔任白班 Leader 的資深護理師：")
            with st.form("leader_form"):
                new_h_seniors = st.multiselect("🩸 血腫資深", heme_staff, default=[x for x in heme_seniors if x in heme_staff])
                new_p_seniors = st.multiselect("🕊️ 安寧資深", pall_staff, default=[x for x in pall_seniors if x in pall_staff])
                if st.form_submit_button("💾 儲存 Leader 名單"):
                    staff_data['heme_seniors'] = new_h_seniors
                    staff_data['pall_seniors'] = new_p_seniors
                    save_staff_data(staff_data)
                    st.success("Leader 名單已儲存！")
                    st.rerun()

        st.write("⚖️ **核心排班規則設定**")
        allowed_off_gap = st.slider("⚖️ 允許休假天數最大落差 (增加彈性)", 0, 10, 4)
        allow_iso_work = st.checkbox("🌟 允許單日上班 (增加排班彈性)", value=True)
        shift_consistency_weight = st.slider("🔀 班別一致性 (同段班不換班)", 0, 1000, 500)
        anti_frag_weight = st.slider("🛡️ 護肝指數 (盡量避免單日休假)", 0, 500, 200)
        
        soft_max_streak = st.slider("💡 期望最多連上天數", 3, 7, 4)
        hard_max_streak = st.slider("🛑 絕對極限連上天數", 3, 7, 5)
        
        min_bonus_days = st.number_input("💰 包班最低達標天數 (鐵血保證)", 1, 31, 15)
        holiday_dates = st.multiselect("勾選國定假日", list(range(1, num_days+1)))

    # --- 5. 人員卡片 ---
    def render_staff_card(name, year, month, is_hn=False):
        fix_status = st.session_state.fixed.get(name, "無")
        is_leader = name in heme_seniors or name in pall_seniors
        base_icon = "🌟" if is_leader else "🟢"
        icon = "👑" if is_hn else ("🐣" if "新" in fix_status else ("☀️" if "白" in fix_status else ("🌙" if "小" in fix_status else ("✨" if "大" in fix_status else base_icon))))
        
        with st.expander(f"{icon} {name}  |  狀態: {fix_status}", expanded=False):
            if not is_hn:
                c1, c2, c3 = st.columns([1, 1, 1.2])
                with c1:
                    if f"ps_{name}" not in st.session_state:
                        st.session_state[f"ps_{name}"] = st.session_state.prev_status.get(name, {}).get('shift', 'Off')
                    new_s = st.selectbox("上月最後一天", ['Off', 'D', 'E', 'N', 'L'], key=f"ps_{name}")
                    st.session_state.prev_status[name] = {'shift': new_s}
                with c2:
                    if f"streak_{name}" not in st.session_state:
                        st.session_state[f"streak_{name}"] = st.session_state.prev_streak.get(name, 0)
                    st.session_state.prev_streak[name] = st.number_input("月底連上天數", 0, 15, key=f"streak_{name}")
                with c3:
                    opts = ["無 (混合)", "固定白 (D)", "固定小 (E)", "固定大 (N)", "新人 (純白班)"]
                    if f"fix_{name}" not in st.session_state:
                        cur = st.session_state.fixed.get(name, "無 (混合)")
                        st.session_state[f"fix_{name}"] = cur if cur in opts else "無 (混合)"
                    st.session_state.fixed[name] = st.selectbox("本月固定班", opts, key=f"fix_{name}")

            st.divider()
            cols = st.columns(7)
            for i, w in enumerate(['一', '二', '三', '四', '五', '六', '日']):
                cols[i].markdown(f"<div style='text-align: center; color: gray; font-size: 0.8em'>{w}</div>", unsafe_allow_html=True)
            
            for week in calendar.monthcalendar(year, month):
                cols = st.columns(7)
                for i, day in enumerate(week):
                    with cols[i]:
                        if day != 0:
                            current_val = st.session_state.daily_shifts.get(name, {}).get(day)
                            label = f"{day}\n{current_val}" if current_val else str(day)
                            btn_type = "primary" if current_val and current_val != 'L' else ("secondary" if not current_val else "primary")
                            if day in holiday_dates: label = "🔴" + label
                            st.button(label, key=f"b_{name}_{day}", type=btn_type, use_container_width=True)

    # --- 6. 主畫面 Tabs ---
    tab_heme, tab_pall, tab_run = st.tabs(["🩸 血腫組", "🕊️ 安寧組", "🚀 產生班表"])

    with tab_heme:
        for name in heme_staff: render_staff_card(name, year, month)

    with tab_pall:
        for name in pall_staff: render_staff_card(name, year, month)
        st.divider()
        st.subheader("👩‍⚕️ 護理長 (完全獨立手動排班)")
        render_staff_card(hn_name, year, month, is_hn=True)

    with tab_run:
        if st.button("🚀 啟動排班", type="primary", use_container_width=True):
            with st.spinner("神經網路運算中... (100% 嚴格邏輯)"):
                model = cp_model.CpModel()
                work = {}
                first_wd, num_days = calendar.monthrange(year, month)
                
                for n in active_staff:
                    for d in range(1, num_days+1):
                        for s in range(len(SHIFTS)):
                            work[(n,d,s)] = model.NewBoolVar(f'w_{n}_{d}_{s}')
                        model.Add(sum(work[(n,d,s)] for s in range(len(SHIFTS))) == 1)

                fragmentation_penalties = []
                shift_changes = [] 
                streak_penalties = []

                for n in active_staff:
                    user_shifts = st.session_state.daily_shifts.get(n, {})
                    f_type = st.session_state.fixed.get(n, "")
                    
                    # 🛑 5.8 嚴格遵守手動排班
                    for d, s_val in user_shifts.items():
                        if s_val in SHIFTS:
                            model.Add(work[(n, d, SHIFTS.index(s_val))] == 1)
                    
                    for d in range(1, num_days+1):
                        manual_shift = user_shifts.get(d)
                        if manual_shift != 'M': model.Add(work[(n, d, SHIFTS.index('M'))] == 0)
                        if manual_shift != '公': model.Add(work[(n, d, SHIFTS.index('公'))] == 0)

                    # 🛑 5.8 嚴格跨月規則
                    last_shift = st.session_state.prev_status.get(n, {}).get('shift', 'Off')
                    if 1 not in user_shifts:
                        if last_shift == 'E':
                            for s in [1, 6, 8, 9, 10]: model.Add(work[(n, 1, s)] == 0)
                        elif last_shift in ['D', 'L']:
                            model.Add(work[(n, 1, 3)] == 0) 

                    if "白" in f_type and "新" not in f_type:
                        for d in range(1, num_days+1): 
                            if d not in user_shifts:
                                for s_idx in [2, 3, 4, 5, 6, 7]: model.Add(work[(n,d,s_idx)]==0) 
                    elif "小" in f_type:
                        for d in range(1, num_days+1): 
                            if d not in user_shifts:
                                for s_idx in [1, 3, 6, 8, 9, 10]: model.Add(work[(n,d,s_idx)]==0) 
                    elif "大" in f_type:
                        for d in range(1, num_days+1): 
                            if d not in user_shifts:
                                for s_idx in [1, 2, 4, 5, 6, 7, 8, 9, 10]: model.Add(work[(n,d,s_idx)]==0) 
                    elif "新" in f_type:
                        for d in range(1, num_days+1):
                            if d not in user_shifts:
                                for s_idx in [2, 3, 4, 5, 6, 7, 8, 9, 10]: model.Add(work[(n,d,s_idx)]==0)

                    # 🛑 5.8 嚴格班別順序
                    for d in range(1, num_days):
                        if d in user_shifts and (d+1) in user_shifts: continue 
                        for day_shift in [1, 6, 8, 9, 10]:
                            model.Add(work[(n, d, 2)] + work[(n, d+1, day_shift)] <= 1)
                        for prev_shift in [1, 2, 4, 5, 6, 7, 8, 9, 10]:
                            model.Add(work[(n, d, prev_shift)] + work[(n, d+1, 3)] <= 1)

                    for d in range(1, num_days):
                        for s1 in range(1, len(SHIFTS)):
                            for s2 in range(1, len(SHIFTS)):
                                if s1 != s2 and not (s1 in [1, 10] and s2 in [1, 10]):
                                    change_var = model.NewBoolVar(f'sc_{n}_{d}_{s1}_{s2}')
                                    model.Add(change_var >= work[(n, d, s1)] + work[(n, d+1, s2)] - 1)
                                    shift_changes.append(change_var)

                    # 🛑 5.8 嚴格極限連上天數
                    window_size = hard_max_streak + 1
                    for d in range(1, num_days - window_size + 2):
                        manual_violation = True
                        for k in range(window_size):
                            if (d+k) not in user_shifts or user_shifts[d+k] == 'Off':
                                manual_violation = False
                                break
                        if not manual_violation:
                            model.Add(sum(work[(n, d+k, 0)] for k in range(window_size)) >= 1)

                    prev_streak = st.session_state.prev_streak.get(n, 0)
                    if prev_streak > 0:
                        limit = hard_max_streak - prev_streak
                        window_end = max(1, limit + 1) 
                        window_end = min(window_end, num_days)
                        
                        manual_violation = True
                        for k in range(1, window_end + 1):
                            if user_shifts.get(k) == 'Off' or k not in user_shifts:
                                manual_violation = False
                                break
                        if not manual_violation:
                            model.Add(sum(work[(n, k, 0)] for k in range(1, window_end + 1)) >= 1)

                    if soft_max_streak < hard_max_streak:
                        soft_window = soft_max_streak + 1
                        for d in range(1, num_days - soft_window + 2):
                            pen = model.NewBoolVar(f'streak_pen_{n}_{d}')
                            model.AddBoolOr([work[(n, d+k, 0)] for k in range(soft_window)] + [pen])
                            streak_penalties.append(pen)
                            
                        if prev_streak > 0:
                            k_days = soft_max_streak - prev_streak + 1
                            if 1 <= k_days <= num_days:
                                pen = model.NewBoolVar(f'prev_streak_pen_{n}')
                                model.AddBoolOr([work[(n, k, 0)] for k in range(1, k_days + 1)] + [pen])
                                streak_penalties.append(pen)
                            elif k_days <= 0:
                                pen = model.NewBoolVar(f'prev_streak_pen_{n}')
                                model.AddBoolOr([work[(n, 1, 0)], pen])
                                streak_penalties.append(pen)

                    allowed_bonus = []
                    if "白" in f_type and "新" not in f_type: allowed_bonus = [1, 10]
                    elif "小" in f_type: allowed_bonus = [2, 4, 5, 7] 
                    elif "大" in f_type: allowed_bonus = [3]
                    elif "新" in f_type: allowed_bonus = [1, 10] 
                    
                    if allowed_bonus:
                        max_possible = sum(1 for d in range(1, num_days+1) if user_shifts.get(d) is None or SHIFTS.index(user_shifts.get(d)) in allowed_bonus)
                        target = min(min_bonus_days, max_possible)
                        if target > 0:
                            model.Add(sum(work[(n,d,s)] for d in range(1, num_days+1) for s in allowed_bonus) >= target)

                    W = []
                    W.append(0 if last_shift == 'Off' else 1) 
                    for d in range(1, num_days+1):
                        w_d = model.NewBoolVar(f'W_{n}_{d}')
                        model.Add(w_d == sum(work[(n, d, s)] for s in range(1, len(SHIFTS))))
                        W.append(w_d)
                    
                    w_last = model.NewBoolVar(f'W_{n}_last')
                    model.Add(w_last == W[-1])
                    W.append(w_last)
                    
                    for d in range(1, num_days+1):
                        iso_off = model.NewBoolVar(f'iso_off_{n}_{d}')
                        model.Add(iso_off >= W[d-1] - W[d] + W[d+1] - 1)
                        fragmentation_penalties.append(iso_off)
                        
                        if not allow_iso_work:
                            iso_work = model.NewBoolVar(f'iso_work_{n}_{d}')
                            model.Add(iso_work >= -W[d-1] + W[d] - W[d+1])
                            fragmentation_penalties.append(iso_work)

                shortfall_vars = []
                surplus_vars = [] 
                def add_exact_demand(staff_list, day, shift_indices, target_count):
                    sf = model.NewIntVar(0, target_count, f'sf_{day}_{shift_indices}_{id(staff_list)}')
                    surp = model.NewIntVar(0, len(staff_list), f'surp_{day}_{shift_indices}_{id(staff_list)}')
                    model.Add(sum(work[(n, day, s)] for n in staff_list for s in shift_indices) + sf - surp == target_count)
                    shortfall_vars.append(sf)
                    surplus_vars.append(surp)

                leader_shortfalls = []
                valid_seniors = list(set([n for n in heme_seniors if n in heme_staff] + [n for n in pall_seniors if n in pall_staff]))

                for d in range(1, num_days+1):
                    wd = (first_wd + d - 1) % 7 
                    is_holiday = (d in holiday_dates)
                    is_weekday = (wd < 5) 
                    
                    if wd < 5 and not is_holiday:
                        if h_wd_d > 0: add_exact_demand(heme_staff, d, [1], h_wd_d)
                        if h_wd_e > 0: add_exact_demand(heme_staff, d, [2], h_wd_e)
                        if h_wd_n > 0: add_exact_demand(heme_staff, d, [3], h_wd_n)
                        if h_wd_48 > 0: add_exact_demand(heme_staff, d, [5], h_wd_48)
                    elif wd == 5 and not is_holiday:
                        if h_sa_d > 0: add_exact_demand(heme_staff, d, [1], h_sa_d)
                        if h_sa_e > 0: add_exact_demand(heme_staff, d, [2], h_sa_e)
                        if h_sa_n > 0: add_exact_demand(heme_staff, d, [3], h_sa_n)
                        if h_sa_812 > 0: add_exact_demand(heme_staff, d, [6], h_sa_812)
                    else:
                        if h_su_d > 0: add_exact_demand(heme_staff, d, [1], h_su_d)
                        if h_su_e > 0: add_exact_demand(heme_staff, d, [2], h_su_e)
                        if h_su_n > 0: add_exact_demand(heme_staff, d, [3], h_su_n)

                    if wd < 4 and not is_holiday:
                        if p_mth_d > 0: add_exact_demand(pall_staff, d, [1], p_mth_d)
                        if p_mth_e > 0: add_exact_demand(pall_staff, d, [2], p_mth_e)
                        if p_mth_n > 0: add_exact_demand(pall_staff, d, [3], p_mth_n)
                        if p_mth_48 > 0: add_exact_demand(pall_staff, d, [5], p_mth_48)
                        if p_mth_18 > 0: add_exact_demand(pall_staff, d, [7], p_mth_18)
                    elif wd == 4 and not is_holiday:
                        if p_f_d > 0: add_exact_demand(pall_staff, d, [1], p_f_d)
                        if p_f_e > 0: add_exact_demand(pall_staff, d, [2], p_f_e)
                        if p_f_n > 0: add_exact_demand(pall_staff, d, [3], p_f_n)
                        if p_f_18 > 0: add_exact_demand(pall_staff, d, [7], p_f_18)
                    else:
                        if p_we_d > 0: add_exact_demand(pall_staff, d, [1], p_we_d)
                        if p_we_e > 0: add_exact_demand(pall_staff, d, [2], p_we_e)
                        if p_we_n > 0: add_exact_demand(pall_staff, d, [3], p_we_n)

                    if is_weekday:
                        for n in active_staff:
                            if n not in valid_seniors and st.session_state.daily_shifts.get(n, {}).get(d) != 'L':
                                model.Add(work[(n, d, 10)] == 0)
                        
                        manual_L = sum(1 for n in active_staff if st.session_state.daily_shifts.get(n, {}).get(d) == 'L')
                        model.Add(sum(work[(n, d, 10)] for n in active_staff) <= max(1, manual_L))
                        
                        sf_l = model.NewIntVar(0, 1, f'sf_l_{d}')
                        model.Add(sum(work[(n, d, 10)] for n in valid_seniors) + sf_l >= 1)
                        leader_shortfalls.append((d, sf_l))
                    else:
                        for n in active_staff:
                            if st.session_state.daily_shifts.get(n, {}).get(d) != 'L':
                                model.Add(work[(n, d, 10)] == 0)

                max_off_var = model.NewIntVar(0, 31, 'max_off')
                min_off_var = model.NewIntVar(0, 31, 'min_off')
                for n in active_staff:
                    offs = sum(work[(n,d,0)] for d in range(1, num_days+1))
                    model.Add(max_off_var >= offs)
                    model.Add(min_off_var <= offs)
                
                fairness_gap = max_off_var - min_off_var
                excess_gap = model.NewIntVar(0, 31, 'excess_gap')
                model.Add(excess_gap >= fairness_gap - allowed_off_gap)

                total_offs = sum(work[(n,d,0)] for n in active_staff for d in range(1, num_days+1))
                total_shortfall_penalty = sum(shortfall_vars)
                total_surplus_penalty = sum(surplus_vars) 
                total_leader_penalty = sum(sf for d, sf in leader_shortfalls)
                total_frag_penalty = sum(fragmentation_penalties) 
                total_shift_change_penalty = sum(shift_changes) 
                total_streak_penalty = sum(streak_penalties)
                
                # 🛑 5.8 嚴格版：1000000 缺班重罰
                model.Maximize(
                    total_offs * 10 
                    - total_shortfall_penalty * 1000000 
                    - total_surplus_penalty * 8000 
                    - total_leader_penalty * 500000
                    - total_shift_change_penalty * shift_consistency_weight 
                    - total_frag_penalty * anti_frag_weight 
                    - total_streak_penalty * 800  
                    - excess_gap * 1000  
                    - fairness_gap * 5   
                )

                solver = cp_model.CpSolver()
                solver.parameters.max_time_in_seconds = 30
                status = solver.Solve(model)

                if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                    shortfall_amount = int(solver.Value(sum(shortfall_vars)))
                    surplus_amount = int(solver.Value(sum(surplus_vars)))
                    
                    unrescued_l = []
                    rescued_l = []
                    missing_staff_l = [d for d, sf in leader_shortfalls if solver.Value(sf) > 0]
                    
                    for d_day in missing_staff_l:
                        hn_shift = st.session_state.daily_shifts.get(hn_name, {}).get(d_day, 'Off')
                        if hn_shift in ['D', 'L']: rescued_l.append(str(d_day))
                        else: unrescued_l.append(str(d_day))
                    
                    if unrescued_l: st.error(f"🚨 **警告！缺 L 日期：**{', '.join(unrescued_l)} 號")
                    if rescued_l: st.warning(f"⚠️ **提示**：{', '.join(rescued_l)} 號由護理長親自上陣救援 L 班！")
                    
                    if shortfall_amount > 0: 
                        st.error(f"🚨 嚴重警告！已達系統極限，仍有 {shortfall_amount} 個班次缺人。請至左側【每日人力需求調整】降載人力，或修改預排！")
                    elif surplus_amount > 0: 
                        st.info(f"💡 班表出爐！本月有 {surplus_amount} 個班次多出人力。")
                    elif not unrescued_l: 
                        st.success(f"✅ 完美報表產出！請下載 Excel 供主管審核！")
                    
                    excel_data = []
                    display_data = {} 
                    
                    date_row = ['姓名', '屬性', '上月', '天數'] + [f"{month}/{d}" for d in range(1, num_days+1)] + ['OFF', 'N', 'E', '包班']
                    excel_data.append(date_row)
                    
                    weekdays_map = {0: '一', 1: '二', 2: '三', 3: '四', 4: '五', 5: '六', 6: '日'}
                    week_row = ['星期', '', '', ''] + [weekdays_map[calendar.weekday(year, month, d)] for d in range(1, num_days+1)] + ['', '', '', '']
                    excel_data.append(week_row)
                    display_data['📅 星期'] = week_row[4:-4] 
                    
                    groups = [
                        ('🩸 【血腫組】', heme_staff, '血腫'),
                        ('🕊️ 【安寧組】', pall_staff, '安寧'),
                        ('👩‍⚕️ 【護理長】', [hn_name], '護理長')
                    ]
                    
                    global_n, global_d, global_e = [0.0]*num_days, [0.0]*num_days, [0.0]*num_days
                    stats = {} 
                    
                    for group_name, staff_list, short_name in groups:
                        excel_data.append([group_name] + [''] * (len(date_row) - 1))
                        display_data[group_name] = [''] * num_days
                        
                        grp_n, grp_d, grp_e = [0.0]*num_days, [0.0]*num_days, [0.0]*num_days
                        
                        for n in staff_list:
                            user_pre_shifts = st.session_state.daily_shifts.get(n, {})
                            row_shifts, display_row = [], []
                            
                            for d_idx in range(num_days):
                                d = d_idx + 1
                                if n == hn_name: assigned = st.session_state.daily_shifts.get(n, {}).get(d, 'Off')
                                else:
                                    assigned = 'Off'
                                    for s in range(len(SHIFTS)):
                                        if solver.Value(work[(n,d,s)]) == 1:
                                            assigned = SHIFTS[s]
                                            break
                                row_shifts.append(assigned)
                                
                                if d in user_pre_shifts or (n == hn_name and assigned != 'Off'): display_row.append(f"<span style='color:red; font-weight:bold;'>{assigned}</span>")
                                else: display_row.append(assigned)
                                    
                                if n != hn_name:
                                    if assigned == 'N': 
                                        grp_n[d_idx] += 1; global_n[d_idx] += 1
                                    elif assigned in ['D', 'L']: 
                                        grp_d[d_idx] += 1; global_d[d_idx] += 1
                                    elif assigned == '8-12':
                                        grp_d[d_idx] += 0.5; global_d[d_idx] += 0.5
                                    elif assigned in ['E', '12-8']: 
                                        grp_e[d_idx] += 1; global_e[d_idx] += 1
                                    elif assigned in ['4-8', '1-8']:
                                        grp_e[d_idx] += 0.5; global_e[d_idx] += 0.5
                            
                            f_type = st.session_state.fixed.get(n, "無 (混合)")
                            ps = st.session_state.prev_status.get(n, {}).get('shift', 'Off')
                            streak = st.session_state.prev_streak.get(n, 0)
                            
                            off_count = row_shifts.count('Off')
                            n_count = row_shifts.count('N')
                            e_count = fmt_num(row_shifts.count('E') + row_shifts.count('12-8') + 0.5*(row_shifts.count('4-8') + row_shifts.count('1-8')))
                            
                            b_count = 0
                            if "白" in f_type and "新" not in f_type: b_count = row_shifts.count('D') + row_shifts.count('L') + 0.5 * row_shifts.count('8-12')
                            elif "小" in f_type: b_count = row_shifts.count('E') + row_shifts.count('12-8') + 0.5 * (row_shifts.count('4-8') + row_shifts.count('1-8'))
                            elif "大" in f_type: b_count = row_shifts.count('N')
                            elif "新" in f_type: b_count = row_shifts.count('D') + row_shifts.count('L') + 0.5 * row_shifts.count('8-12')
                            
                            b_str = fmt_num(b_count) if (b_count > 0 or f_type != "無 (混合)") else '-'
                            
                            excel_data.append([n, f_type, ps, streak] + row_shifts + [off_count, n_count, e_count, b_str])
                            display_data[n] = display_row
                            
                            stats[n] = {
                                '休假(Off)': off_count, '📍包班/新白': b_str, '白(D)': row_shifts.count('D'),
                                '👑 Leader(L)': row_shifts.count('L'), '小(E)': row_shifts.count('E'), '大(N)': n_count,
                                '4-8 (0.5)': row_shifts.count('4-8'), '1-8 (0.5)': row_shifts.count('1-8'), '12-8': row_shifts.count('12-8'),
                                '8-12 (0.5)': row_shifts.count('8-12'), '行政(M)': row_shifts.count('M'), '公假': row_shifts.count('公')
                            }
                        
                        if short_name != '護理長':
                            grp_n_fmt, grp_d_fmt, grp_e_fmt = [fmt_num(x) for x in grp_n], [fmt_num(x) for x in grp_d], [fmt_num(x) for x in grp_e]
                            excel_data.append([f'{short_name}-N小計', '', '', ''] + grp_n_fmt + ['', '', '', ''])
                            excel_data.append([f'{short_name}-D小計', '', '', ''] + grp_d_fmt + ['', '', '', ''])
                            excel_data.append([f'{short_name}-E小計', '', '', ''] + grp_e_fmt + ['', '', '', ''])
                            display_data[f'📊 {short_name}-N小計'] = grp_n_fmt; display_data[f'📊 {short_name}-D小計'] = grp_d_fmt; display_data[f'📊 {short_name}-E小計'] = grp_e_fmt

                    excel_data.append([''] * len(date_row))
                    global_n_fmt, global_d_fmt, global_e_fmt = [fmt_num(x) for x in global_n], [fmt_num(x) for x in global_d], [fmt_num(x) for x in global_e]
                    excel_data.append(['全站總計 N', '', '', ''] + global_n_fmt + ['', '', '', ''])
                    excel_data.append(['全站總計 D', '', '', ''] + global_d_fmt + ['', '', '', ''])
                    excel_data.append(['全站總計 E', '', '', ''] + global_e_fmt + ['', '', '', ''])
                    
                    headers = [str(d) for d in range(1, num_days+1)]
                    st.markdown(pd.DataFrame(display_data, index=headers).T.to_html(escape=False), unsafe_allow_html=True)
                    st.write("📊 本月班別統計"); st.dataframe(pd.DataFrame(stats).T)
                    
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer: 
                        pd.DataFrame(excel_data).to_excel(writer, sheet_name='總表', header=False, index=False)
                        ws_main, workbook = writer.sheets['總表'], writer.book
                        
                        b_fmt = workbook.add_format({'align': 'center', 'valign': 'vcenter'})
                        w_fmt = workbook.add_format({'bg_color': '#FFF2CC', 'align': 'center', 'valign': 'vcenter'})
                        r_fmt = workbook.add_format({'font_color': 'red', 'bold': True, 'align': 'center', 'valign': 'vcenter'})
                        rw_fmt = workbook.add_format({'bg_color': '#FFF2CC', 'font_color': 'red', 'bold': True, 'align': 'center', 'valign': 'vcenter'})
                        h_fmt = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'align': 'center', 'valign': 'vcenter'})
                        s_fmt = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#E2EFDA'})
                        sec_fmt = workbook.add_format({'bg_color': '#DDEBF7', 'bold': True, 'align': 'left', 'valign': 'vcenter', 'font_color': '#2F75B5'})
                        sh_fmt = workbook.add_format({'bg_color': '#EAEAEA', 'bold': True, 'align': 'left', 'valign': 'vcenter', 'font_color': '#333333'})
                        sn_fmt = workbook.add_format({'bg_color': '#EAEAEA', 'bold': True, 'align': 'center', 'valign': 'vcenter'})
                        sw_fmt = workbook.add_format({'bg_color': '#DFD6A3', 'bold': True, 'align': 'center', 'valign': 'vcenter'})
                        
                        ws_main.set_column(0, 0, 16); ws_main.set_column(1, 1, 12); ws_main.set_column(2, 3, 6); ws_main.set_column(4, 3+num_days, 6) 
                        
                        for r_idx, row_data in enumerate(excel_data):
                            if r_idx < 2:
                                for c_idx, val in enumerate(row_data): ws_main.write(r_idx, c_idx, val, h_fmt)
                                continue
                            name = row_data[0]
                            if name in ['🩸 【血腫組】', '🕊️ 【安寧組】', '👩‍⚕️ 【護理長】']:
                                ws_main.merge_range(r_idx, 0, r_idx, len(row_data)-1, name, sec_fmt)
                                continue
                            if '全站總計' in name:
                                for c_idx, val in enumerate(row_data): ws_main.write(r_idx, c_idx, val, h_fmt)
                                continue
                            if '小計' in name:
                                for c_idx, val in enumerate(row_data):
                                    if c_idx == 0: ws_main.write(r_idx, c_idx, val, sh_fmt)
                                    elif 4 <= c_idx < 4 + num_days:
                                        wd = calendar.weekday(year, month, c_idx - 3)
                                        ws_main.write(r_idx, c_idx, val, sw_fmt if wd >= 5 else sn_fmt)
                                    else: ws_main.write(r_idx, c_idx, val, sn_fmt)
                                continue
                            if name == '': continue
                            for c_idx, val in enumerate(row_data):
                                if 4 <= c_idx < 4 + num_days:
                                    d = c_idx - 3; wd = calendar.weekday(year, month, d)
                                    is_pre = (name == hn_name and st.session_state.daily_shifts.get(name, {}).get(d)) or (name != hn_name and d in st.session_state.daily_shifts.get(name, {}))
                                    fmt = (rw_fmt if is_pre else w_fmt) if wd >= 5 else (r_fmt if is_pre else b_fmt)
                                    ws_main.write(r_idx, c_idx, val, fmt)
                                elif c_idx >= 4 + num_days: ws_main.write(r_idx, c_idx, val, s_fmt) 
                                else: ws_main.write(r_idx, c_idx, val, b_fmt)
                        ws_main.freeze_panes(2, 4)

                    st.download_button("📥 下載嚴格邏輯版 Excel (純淨總表)", output.getvalue(), f"{year}年{month}月_排班表.xlsx", type="primary")
                else: st.error("❌ 無解！(跨月防護或預排假導致嚴重衝突，請稍微放寬條件)")
