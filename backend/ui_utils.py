import streamlit as st
from backend.utils import get_team_color, hex_to_rgba

def color_rank_rows(row):
    """為表格套用球隊專屬主色的 CSS 渲染器"""
    team_color = get_team_color(row['Team'])[0]
    id_cols = ['Player', 'Team', 'Position', 'Nickname', 'Slot (指派位置)']
    return [f'color: {team_color} !important; font-weight: 900 !important;' if col in id_cols else '' for col in row.index]
def hex_to_rgba(hex_str, alpha):
    hex_str = hex_str.lstrip('#')
    rgb = tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    return f"rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {alpha})"

def inject_custom_css(primary_col, secondary_col):
    """注入全域的 CSS，強制全域置中、滿版延伸、並實作「頂部滑動條」黑科技"""
    st.markdown(f"""
        <style>
        /* ========================================================================= */
        /* 🛡️ 0. 全站極致純白背景與快取破壞 */
        /* ========================================================================= */
        .stApp, [data-testid="stAppViewContainer"], [data-testid="stMainBlockContainer"] {{
            background-color: #FFFFFF !important;
        }}
        
        /* ========================================================================= */
        /* 1. 隱藏原生頂部裝飾與側邊欄 */
        /* ========================================================================= */
        header[data-testid="stHeader"], .stAppHeader {{ display: none !important; }}
        [data-testid="collapsedControl"] {{ display: none !important; }}
        section[data-testid="stSidebar"] {{ display: none !important; width: 0px !important; margin: 0 !important; padding: 0 !important; }}

        /* ========================================================================= */
        /* 2. 主視窗完美對稱：保留 95% 寬度與呼吸留白，絕對置中 */
        /* ========================================================================= */
        .block-container {{ 
            max-width: 95% !important; 
            padding-top: 2rem !important; 
            padding-bottom: 2rem !important; 
            margin: 0 auto !important; 
        }}
/* ========================================================================= */
        /* 3. Tabs 分頁：極致對稱、均分寬度 (無差別穿透版) */
        /* ========================================================================= */
        .stTabs {{
            width: 100% !important;
        }}
        .stTabs > div {{
            display: flex !important;
            justify-content: center !important;
            width: 100% !important;
        }}
        .stTabs button {{
            flex-grow: 1 !important; /* 強制所有按鈕自動均分畫面 */
            text-align: center !important;
        }}

        /* ========================================================================= */
        /* 4. Radio 按鈕：物理置中 (無差別穿透版) */
        /* ========================================================================= */
        .stRadio {{
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            width: 100% !important;
            text-align: center !important;
        }}
        .stRadio > div {{
            display: flex !important;
            justify-content: center !important;
            margin: 0 auto !important;
        }}
        /* ========================================================================= */
        /* 5. 大標題與內文：無死角絕對置中 */
        /* ========================================================================= */
        [data-testid="stMarkdownContainer"] h1, 
        [data-testid="stMarkdownContainer"] h2, 
        [data-testid="stMarkdownContainer"] h3, 
        [data-testid="stMarkdownContainer"] h4 {{ 
            width: 100% !important;
            text-align: center !important; 
            margin-left: auto !important;
            margin-right: auto !important;
        }}
        [data-testid="stMarkdownContainer"] p {{
            font-size: 20px !important; 
            font-weight: 700 !important;
            text-align: center !important;
        }}
        
        [data-testid="stMarkdownContainer"] h1 {{ font-size: 42px !important; font-weight: 900 !important; margin-bottom: 20px !important; }}
        [data-testid="stMarkdownContainer"] h2 {{ font-size: 28px !important; font-weight: 900 !important; margin-top: 5px !important; margin-bottom: 15px !important; }}
        [data-testid="stMarkdownContainer"] h3 {{ font-size: 32px !important; font-weight: 900 !important; }}
        [data-testid="stMarkdownContainer"] h4 {{ font-size: 26px !important; font-weight: 800 !important; }}
        
        /* ========================================================================= */
        /* 6. 頂部滑動條黑科技：將外殼 180度翻轉，內部元素再翻轉回來 */
        /* ========================================================================= */
        .table-scroll-container {{ 
            width: 100% !important; 
            overflow-x: auto !important; 
            overflow-y: visible !important; 
            border: 1px solid #e0e0e0; 
            border-radius: 8px; 
            background-color: white; 
            margin: 0 auto 20px auto !important;
            display: block !important;
            transform: rotateX(180deg); 
        }}
        .table-scroll-container table {{ 
            width: 100% !important; 
            min-width: 100% !important; 
            display: table !important; 
            margin: 0 auto !important; 
            transform: rotateX(180deg); 
        }}
        .table-scroll-container th {{ 
            background-color: {primary_col} !important; 
            color: white !important; 
            font-size: 18px !important; 
            position: sticky; 
            top: 0; 
            z-index: 10; 
            text-align: center !important; 
        }}
        .table-scroll-container td {{ 
            font-size: 17px !important; 
            text-align: center !important; 
            vertical-align: middle !important;
        }}
        </style>
    """, unsafe_allow_html=True)