# config.py

# 大聯盟 30 支球隊 API ID (用於爬蟲抓取戰況與傷兵)
MLB_TEAM_IDS = {
    "Arizona Diamondbacks": 109, "Atlanta Braves": 144, "Baltimore Orioles": 110,
    "Boston Red Sox": 111, "Chicago Cubs": 112, "Chicago White Sox": 145,
    "Cincinnati Reds": 113, "Cleveland Guardians": 114, "Colorado Rockies": 115,
    "Detroit Tigers": 116, "Houston Astros": 117, "Kansas City Royals": 118,
    "Los Angeles Angels": 108, "Los Angeles Dodgers": 119, "Miami Marlins": 146,
    "Milwaukee Brewers": 158, "Minnesota Twins": 142, "New York Mets": 121,
    "New York Yankees": 147, "Oakland Athletics": 133, "Philadelphia Phillies": 143,
    "Pittsburgh Pirates": 134, "San Diego Padres": 135, "San Francisco Giants": 137,
    "Seattle Mariners": 136, "St. Louis Cardinals": 138, "Tampa Bay Rays": 139,
    "Texas Rangers": 140, "Toronto Blue Jays": 141, "Washington Nationals": 120
}

# 球隊專屬主副色碼 (用於 UI 渲染與圖表)
MLB_TEAM_COLORS = {
    "Los Angeles Dodgers": ("#005A9C", "#A5ACAF"), "New York Yankees": ("#0C2340", "#C4CED4"),
    "Boston Red Sox": ("#BD3039", "#0C2340"), "Houston Astros": ("#EB6E1F", "#002D62"), 
    "Atlanta Braves": ("#13274F", "#CE1141"), "Philadelphia Phillies": ("#E81828", "#6FACD5"), 
    "New York Mets": ("#FF5910", "#002D72"), "Toronto Blue Jays": ("#134A8E", "#1D2D5C"),
    "Baltimore Orioles": ("#DF4601", "#000000"), "Tampa Bay Rays": ("#092C5C", "#8FBCE6"), 
    "Chicago White Sox": ("#27251F", "#C4CED4"), "Cleveland Guardians": ("#E31937", "#0C2340"), 
    "Detroit Tigers": ("#0C2340", "#FA4616"), "Kansas City Royals": ("#004687", "#BD9B60"),
    "Minnesota Twins": ("#D31145", "#002B5C"), "Los Angeles Angels": ("#BA0021", "#003263"),
    "Oakland Athletics": ("#003831", "#EFB21E"), "Seattle Mariners": ("#005C5C", "#0C2C56"), 
    "Texas Rangers": ("#003278", "#C0111F"), "Chicago Cubs": ("#0E3386", "#CC3433"),
    "Cincinnati Reds": ("#C6011F", "#000000"), "Milwaukee Brewers": ("#12284B", "#FFC52F"), 
    "Pittsburgh Pirates": ("#000000", "#FDB827"), "St. Louis Cardinals": ("#C41E3A", "#0C2340"),
    "Arizona Diamondbacks": ("#A71930", "#E3D4AD"), "Colorado Rockies": ("#33006F", "#C4CED4"),
    "San Diego Padres": ("#2F241D", "#FFC425"), "San Francisco Giants": ("#FD5A1E", "#27251F"),
    "Miami Marlins": ("#00A3E0", "#EF3340"), "Washington Nationals": ("#AB0003", "#14225A")
}

# 評級顏色設定
grade_keys = ['S', 'A', 'B', 'C', 'D']
grade_defaults = ['#FFD700', '#00E676', '#2196F3', '#FF9800', '#F44336']

# 🔥 核心修復：把 'Player' 加入數值計算排除名單，讓系統知道「名字不是可以拿來計算高低優劣的數據」
exclude_cols = ['Player', 'Player_ID', 'Team', 'Position']

# Pandas 表格數字格式化規則
STYLER_FORMATS = {
    'WAR': '{:.1f}', 'ERA': '{:.2f}', 'WHIP': '{:.2f}', 'AVG': '{:.3f}', 
    'OPS': '{:.3f}', 'OBP': '{:.3f}', 'SLG': '{:.3f}', 'wRC+': '{:.0f}',
    'K%': '{:.1f}', 'BB%': '{:.1f}', 'HardHit%': '{:.1f}', 'Barrel%': '{:.1f}',
    'Whiff%': '{:.1f}', 'Chase%': '{:.1f}', 'GB%': '{:.1f}', 'FIP': '{:.2f}',
    'Fan_Pts': '{:.2f}', 'Avg_Pts': '{:.2f}', 'Total_Pts (區間總分)': '{:.2f}',
    '預期主項': '{:.2f}', '基礎預期分': '{:.2f}', '🔥 進階預期分': '{:.2f}',
    'MVP_Index': '{:.2f}', 'Cy_Index': '{:.2f}', 'IP': '{:.1f}', 'IP_calc': '{:.1f}',
    'R': '{:.0f}', 'H': '{:.0f}', 'HR': '{:.0f}', 'RBI': '{:.0f}', 'SB': '{:.0f}',
    'W': '{:.0f}', 'L': '{:.0f}', 'SV': '{:.0f}', 'HLD': '{:.0f}', 'K': '{:.0f}', 'BB': '{:.0f}'
}

# 數據指標的中英對照字典 (用於 UI 顯示)
METRIC_TW = {
    'WAR': '勝利貢獻值', 'OPS': '攻擊指數', 'AVG': '打擊率', 'HR': '全壘打',
    'ERA': '防禦率', 'WHIP': '每局被上壘率', 'K%': '三振率', 'BB%': '保送率',
    'wRC+': '標準化創造進攻', 'HardHit%': '強擊球率', 'Barrel%': '出色擊球率',
    'Whiff%': '揮空率', 'Chase%': '追打壞球率', 'FIP': '投手獨立防禦率', 'SB': '盜壘'
}