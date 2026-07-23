import streamlit as st
import json
import os
import requests
from datetime import datetime, timezone, timedelta

# 🌟 必須是第一個 Streamlit 指令
st.set_page_config(layout="wide", page_title="MLB 球探數據系統")

# 🔥 引入外援套件：高質感置中導覽列
from streamlit_option_menu import option_menu 

from backend.config import MLB_TEAM_IDS
from backend.utils import get_team_color, generate_fun_nickname
from backend.ui_utils import inject_custom_css
from backend.data_fetcher import process_combined_data

# ==========================================
# 📌 V2.0 雲端資料庫初始化 (Firebase 讀取核心)
# ==========================================
if 'fantasy_db' not in st.session_state:
    try:
        # 從 Secrets 保險箱中讀取網址並加上 .json
        url = st.secrets["FIREBASE_URL"] + "fantasy_db.json"
        response = requests.get(url)
        
        if response.status_code == 200 and response.json() is not None:
            raw_cloud_data = response.json()
            
            # 智能攔截：自動拆解 Firebase 匯入時可能多包的一層
            if "fantasy_db" in raw_cloud_data and len(raw_cloud_data) == 1:
                st.session_state.fantasy_db = raw_cloud_data["fantasy_db"]
            else:
                st.session_state.fantasy_db = raw_cloud_data
        else:
            st.session_state.fantasy_db = {}
            
    except Exception as e:
        # 如果雲端連線失敗的備用防呆
        st.session_state.fantasy_db = {}

# ==========================================
# 📌 台灣時間與賽季日期設定 (完美相容標準庫)
# ==========================================
tw_tz = timezone(timedelta(hours=8))
year = datetime.now(tw_tz).year 
today_dt = datetime.now(tw_tz)
today_str = today_dt.strftime("%Y-%m-%d")
tomorrow_str = (today_dt + timedelta(days=1)).strftime("%Y-%m-%d")

# ==========================================
# 📌 隱形變數初始化區
# ==========================================
if 'font_size' not in st.session_state: st.session_state.font_size = 24
if 'table_font_size' not in st.session_state: st.session_state.table_font_size = 20

grade_keys = ['S', 'A', 'B', 'C', 'D', 'F']
grade_defaults = ['#FFD700', '#00E676', '#2196F3', '#FF9800', '#FF5722', '#F44336']
for k, c in zip(grade_keys, grade_defaults):
    if f'color_{k}' not in st.session_state: st.session_state[f'color_{k}'] = c


# 注入全站 UI CSS (全新置中滿版)
primary_col, secondary_col = get_team_color("Los Angeles Dodgers")
inject_custom_css(primary_col, secondary_col)

# ==========================================
# 📌 ⚾ 全局主標題
# ==========================================
st.markdown(f"""
    <div style="text-align: center; margin-top: 15px; margin-bottom: 20px;">
        <h1 style="color: {primary_col}; text-shadow: 1px 1px 3px rgba(0,0,0,0.15); font-weight: 900; margin-top: -50px; padding-left: 60px; font-size: 42px;"> MLB 球探數據系統 </h1>
        <div style="width: 120px; height: 5px; background-color: {secondary_col}; margin-top: -20px; margin-bottom: 20px; margin-left: 600px; border-radius: 3px; box-shadow: 0px 1px 2px rgba(0,0,0,0.2);"></div>
    </div>
""", unsafe_allow_html=True)

# 撈取數據 (底層門檻 0，解鎖全聯盟球員)
with st.spinner("載入大聯盟資料中..."):
    raw_data_h = process_combined_data("打者", year, 0)
    raw_data_p = process_combined_data("投手", year, 0.0)

if not raw_data_h.empty: raw_data_h['Nickname'] = raw_data_h.apply(lambda row: generate_fun_nickname(row, "打者"), axis=1)
if not raw_data_p.empty: raw_data_p['Nickname'] = raw_data_p.apply(lambda row: generate_fun_nickname(row, "投手"), axis=1)

all_players = sorted(raw_data_h['Player'].unique().tolist() + raw_data_p['Player'].unique().tolist())
all_nicknames = sorted(list(set(raw_data_h['Nickname'].unique().tolist() + raw_data_p['Nickname'].unique().tolist())))

# ==========================================
# 📌 系統路由：高質感置中主選單
# ==========================================
selected_tab = option_menu(
    menu_title=None, 
    options=["📊 全聯盟一般數據", "🦄 Fantasy 夢幻棒球", "🔍 深度搜尋面板", "🔮 賽程中心與預測"],
    default_index=0,
    orientation="horizontal",
    styles={
        "container": {"padding": "0!important", "max-width": "1000px", "margin": "0 auto 25px auto", "background-color": "#FFFFFF", "border": "2px solid #F0F2F6", "border-radius": "25px"},
        "nav-link": {"font-size": "18px", "text-align": "center", "margin": "0px", "font-weight": "bold", "color": "#555", "border-radius": "25px"},
        "nav-link-selected": {"background-color": "#005A9C", "color": "white", "font-weight": "900"}, # 主選單使用道奇藍，凸顯大氣
    }
)

# ==========================================
# 📌 頁面切換邏輯 (使用 if/elif 取代 with)
# ==========================================
if selected_tab == "📊 全聯盟一般數據":
    from backend.modules.league_data import render_league_data
    render_league_data(raw_data_h, raw_data_p, year)

elif selected_tab == "🦄 Fantasy 夢幻棒球":
    from backend.modules.fantasy_team import render_fantasy_team
    # 🟢 校正回歸：傳遞真正的 today_str，讓夢幻球隊系統擁有正確的出發點
    render_fantasy_team(raw_data_h, raw_data_p, all_players, today_str)

elif selected_tab == "🔍 深度搜尋面板":
    from backend.modules.deep_search import render_deep_search
    render_deep_search(raw_data_h, raw_data_p, all_players, today_str, all_nicknames, year)

elif selected_tab == "🔮 賽程中心與預測":
    from backend.modules.predictions import render_predictions
    render_predictions(raw_data_h, raw_data_p, all_players, year)