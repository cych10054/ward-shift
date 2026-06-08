import streamlit as st

st.set_page_config(page_title="護理站系統入口", layout="centered")

st.title("🏥 護理站智慧整合系統")
st.markdown("---")
st.subheader("請選擇您的入口：")

if st.button("📝 前往：護理師劃假系統", use_container_width=True):
    st.switch_page("pages/1_預假.py")

if st.button("🏥 前往：阿長排班系統", use_container_width=True):
    st.switch_page("pages/2_排班.py")
