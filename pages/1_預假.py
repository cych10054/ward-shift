import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

st.set_page_config(page_title="護理師預假系統", layout="wide")

# 1. 定義員工資料庫 (一定要加在每個檔案裡，或放在一個共用檔案)
EMP_DB = {
    "05768": "血腫-蔡O樺", "10054": "血腫-吳O茹", "13218": "血腫-張O葳", 
    "13598": "血腫-葉O菁", "13717": "血腫-蔡O蓁", "16148": "血腫-呂O岑", 
    "16623": "血腫-洪O蔚", "03125": "安寧-龔O如", "04009": "安寧-葉O敏", 
    "13217": "安寧-沈O叡", "12820": "安寧-張O嘉", "13736": "安寧-許O禎", 
    "13533": "安寧-吳O萍", "15783": "安寧-劉O君", "16147": "安寧-鐘O淇", 
    "16391": "安寧-洪O安", "16449": "安寧-陳O柔", "16625": "安寧-黃O柔", 
    "16663": "安寧-李O軒", "03059": "護理長-林O穎"
}

# 確保登入狀態存在
if 'logged_in_user' not in st.session_state:
    st.session_state.logged_in_user = None

st.title("📝 護理師專屬劃假網頁")

if "google_sheets_key" in st.secrets:
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["google_sheets_key"], 
            ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
    client = gspread.authorize(creds)
    sheet = client.open_by_key("1C5iM_4aqANm4z9mXZzrMZ3vbQLcj4O_wL2_AJK5BjsU").sheet1
    
    # 讀取資料
    all_records = sheet.get_all_records()
    
    # 全站看板
    with st.expander("📊 點擊查看全站預約概況 (大家劃了哪些天)", expanded=False):
        if all_records:
            df_all = pd.DataFrame(all_records)
            st.dataframe(df_all, use_container_width=True)
        else:
            st.info("目前尚無人預約。")
    
    st.divider()

    # 登入機制
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
            st.table(pd.DataFrame(personal_records))
        
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
            st.success("✅ 預約已送出！請重新整理頁面查看看板。")
            st.balloons()
        
        if st.button("登出"):
            st.session_state.logged_in_user = None
            st.rerun()
else:
    st.error("⚠️ 系統尚未設定 Google Sheets 金鑰。")
