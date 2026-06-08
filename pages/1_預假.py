import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# ==========================================
# 模式一：護理師劃假入口 (2.1 升級版)
# ==========================================
if page == "📝 護理師劃假入口":
    st.title("📝 護理師專屬劃假網頁")
    
    if "google_sheets_key" in st.secrets:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["google_sheets_key"], 
                ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
        client = gspread.authorize(creds)
        sheet = client.open_by_key("1C5iM_4aqANm4z9mXZzrMZ3vbQLcj4O_wL2_AJK5BjsU").sheet1
        
        # 1. 全站看板 (顯示所有人預約情況)
        with st.expander("📊 點擊查看全站預約概況 (大家劃了哪些天)", expanded=False):
            all_records = sheet.get_all_records()
            if all_records:
                df_all = pd.DataFrame(all_records)
                st.dataframe(df_all[['姓名', '日期', '您要劃什麼班？']].sort_values(by='日期'), use_container_width=True)
            else:
                st.info("目前尚無人預約。")
        
        st.divider()

        # 2. 登入機制
        if st.session_state.logged_in_user is None:
            st.markdown("### 🔒 系統登入")
            emp_id = st.text_input("請輸入您的員工編號", type="password")
            if st.button("登入"):
                if emp_id in EMP_DB:
                    st.session_state.logged_in_user = EMP_DB[emp_id]
                    st.rerun()
                else:
                    st.error("❌ 找不到此員工編號。")
        else:
            name = st.session_state.logged_in_user
            st.success(f"👩‍⚕️ 您好，{name}")
            
            # 顯示個人預約歷史
            personal_records = [r for r in all_records if r['姓名'] == name]
            if personal_records:
                st.write("**您的預約紀錄：**")
                st.table(pd.DataFrame(personal_records)[['日期', '您要劃什麼班？']])
            
            # 3. 月曆式預約 (簡單互動)
            st.markdown("---")
            st.subheader("📅 點選日期劃假")
            
            col_a, col_b = st.columns([2, 1])
            with col_a:
                selected_date = st.date_input("選擇日期")
                date_label = f"{selected_date.month}/{selected_date.day}"
            with col_b:
                shift = st.selectbox("選擇班別", ["Off", "D", "E", "N"])
            
            if st.button("送出預約"):
                sheet.append_row([pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"), name, date_label, shift])
                st.success("✅ 預約已送出！請點擊左側欄位重新載入以更新看板。")
                st.balloons()
            
            if st.button("登出"):
                st.session_state.logged_in_user = None
                st.rerun()
    else:
        st.error("⚠️ 系統尚未設定 Google Sheets 金鑰。")
