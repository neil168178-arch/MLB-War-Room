import streamlit as st
import pandas as pd

STYLER_FORMATS = {
    'AB': '{:.0f}', 'G': '{:.0f}', 'PA': '{:.0f}', 'R': '{:.0f}', 'H': '{:.0f}', 
    '1B': '{:.0f}', '2B': '{:.0f}', '3B': '{:.0f}', 'HR': '{:.0f}', 'RBI': '{:.0f}', 
    'SB': '{:.0f}', 'BB': '{:.0f}', 'HBP': '{:.0f}', 'K': '{:.0f}', 'E': '{:.0f}', 
    'CYC': '{:.0f}', 'SLAM': '{:.0f}', 'W': '{:.0f}', 'L': '{:.0f}', 'SHO': '{:.0f}', 
    'SV': '{:.0f}', 'OUT': '{:.0f}', 'ER': '{:.0f}', 'WP': '{:.0f}', 'HLD': '{:.0f}', 
    'QS': '{:.0f}', 'BSV': '{:.0f}',
    'WAR': '{:.1f}', 'ERA': '{:.2f}', 'WHIP': '{:.2f}', 'IP': '{:.1f}', 'FIP': '{:.2f}', 
    'xERA': '{:.2f}', 'K/9': '{:.1f}', 'BB/9': '{:.1f}', 'AVG': '{:.3f}', 'OBP': '{:.3f}', 
    'SLG': '{:.3f}', 'OPS': '{:.3f}', 'wRC+': '{:.0f}', 
    'BB%': '{:.1f}%', 'K%': '{:.1f}%', 'Chase%': '{:.1f}%', 'Whiff%': '{:.1f}%', 
    'Barrel%': '{:.1f}%', 'HardHit%': '{:.1f}%', 'GB%': '{:.1f}%', 'LD%': '{:.1f}%', 'FB%': '{:.1f}%',
    'Sprint': '{:.1f}', 'Arm': '{:.1f}', 'Def': '{:.1f}', 
    'Fan_Pts': '{:.1f}', 'Avg_Pts': '{:.2f}'
}

# 🔥 修正 Milwaukee Brewers 的主副色順序 (海軍藍在前，黃色在後)
MLB_TEAM_COLORS = {
    "Los Angeles Dodgers": ("#005A9C", "#A5ACAF"), "New York Yankees": ("#0C2340", "#C4CED4"),
    "Boston Red Sox": ("#BD3039", "#0C2340"), "Houston Astros": ("#002D62", "#EB6E1F"),
    "Atlanta Braves": ("#CE1141", "#13274F"), "Philadelphia Phillies": ("#E81828", "#002D72"),
    "New York Mets": ("#002D72", "#FF5910"), "Toronto Blue Jays": ("#134A8E", "#1D2D5C"),
    "Baltimore Orioles": ("#DF4601", "#000000"), "Tampa Bay Rays": ("#092C5C", "#8FBCE6"),
    "Chicago White Sox": ("#27251F", "#C4CED4"), "Cleveland Guardians": ("#E31937", "#002B5C"),
    "Detroit Tigers": ("#0C2340", "#FA4616"), "Kansas City Royals": ("#004687", "#BD9B60"),
    "Minnesota Twins": ("#002B5C", "#D31145"), "Los Angeles Angels": ("#BA0021", "#003263"),
    "Oakland Athletics": ("#003831", "#EFB21E"), "Seattle Mariners": ("#0C2C56", "#005C5C"),
    "Texas Rangers": ("#003278", "#C0111F"), "Chicago Cubs": ("#0E3386", "#CC3433"),
    "Cincinnati Reds": ("#C6011F", "#000000"), "Miami Marlins": ("#00A3E0", "#EF3340"),
    "Washington Nationals": ("#AB0003", "#14225A"), "Arizona Diamondbacks": ("#A71930", "#E3D4AD"),
    "Colorado Rockies": ("#33006F", "#C4CED4"), "San Diego Padres": ("#2F241D", "#FFC425"),
    "San Francisco Giants": ("#FD5A1E", "#27251F"), "Milwaukee Brewers": ("#12284B", "#FFC52F"),
    "St. Louis Cardinals": ("#C41E3A", "#0C2340"), "Pittsburgh Pirates": ("#FDB827", "#27251F"),
    "Multiple": ("#607D8B", "#B0BEC5"), "Unknown": ("#9E9E9E", "#E0E0E0")
}

@st.cache_data(ttl=3600*6)
def fetch_team_standings(year):
    import requests
    try:
        url = f"https://statsapi.mlb.com/api/v1/standings?leagueId=103,104&season={year}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json()
        standings = {}
        for record in data.get('records', []):
            for team in record.get('teamRecords', []):
                t_name = team['team']['name']
                if "D-backs" in t_name: t_name = "Arizona Diamondbacks"
                
                w = team['wins']
                l = team['losses']
                home_w, home_l, away_w, away_l = 0, 0, 0, 0
                for split in team.get('records', {}).get('splitRecords', []):
                    if split['type'] == 'home': home_w, home_l = split['wins'], split['losses']
                    elif split['type'] == 'away': away_w, away_l = split['wins'], split['losses']
                standings[t_name] = {'W': w, 'L': l, 'Home_W': home_w, 'Home_L': home_l, 'Away_W': away_w, 'Away_L': away_l}
        return standings
    except Exception as e: return {}

def clean_name(name_str):
    if not isinstance(name_str, str): return name_str
    import unicodedata
    return unicodedata.normalize('NFD', name_str).encode('ascii', 'ignore').decode('utf-8').split(' - ')[0].replace('Jr.', '').replace('Sr.', '').strip()

def safe_float(val):
    try: return float(val)
    except: return 0.0

def f_size(base_size, factor):
    return f"{int(base_size * factor)}px"

def hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip('#')
    return f"rgba({int(hex_color[0:2], 16)}, {int(hex_color[2:4], 16)}, {int(hex_color[4:6], 16)}, {alpha})"

def darken_color(hex_color, factor=0.8):
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"#{int(r * factor):02x}{int(g * factor):02x}{int(b * factor):02x}"

def get_team_color(team_name):
    team_name = str(team_name).strip()
    if team_name in MLB_TEAM_COLORS: return MLB_TEAM_COLORS[team_name]
    for full_name, colors in MLB_TEAM_COLORS.items():
        if team_name in full_name: return colors
    return ("#005A9C", "#A5ACAF")

def get_team_logo_url(team_name):
    team_name = str(team_name).strip()
    espn_abbr = {
        "Diamondbacks": "ari", "Braves": "atl", "Orioles": "bal", "Red Sox": "bos",
        "Cubs": "chc", "White Sox": "chw", "Reds": "cin", "Guardians": "cle",
        "Rockies": "col", "Tigers": "det", "Astros": "hou", "Royals": "kc",
        "Angels": "laa", "Dodgers": "lad", "Marlins": "mia", "Brewers": "mil",
        "Twins": "min", "Mets": "nym", "Yankees": "nyy", "Athletics": "oak",
        "Phillies": "phi", "Pirates": "pit", "Padres": "sd", "Giants": "sf",
        "Mariners": "sea", "Cardinals": "stl", "Rays": "tb", "Rangers": "tex",
        "Blue Jays": "tor", "Nationals": "wsh"
    }
    for key, abbr in espn_abbr.items():
        if key in team_name: return f"https://a.espncdn.com/i/teamlogos/mlb/500/{abbr}.png"
    return "https://www.mlbstatic.com/team-logos/league-on-dark/1.svg"

def score_to_grade(score):
    if score >= 90: return 'S'
    if score >= 80: return 'A'
    if score >= 70: return 'B'
    if score >= 50: return 'C'
    if score >= 30: return 'D'
    return 'F'

def style_grade(val):
    color_map = {'S': '#FFD700', 'A': '#00E676', 'B': '#2196F3', 'C': '#FF9800', 'D': '#FF5722', 'F': '#F44336'}
    bg_color = color_map.get(str(val), '#9E9E9E')
    return f'background-color: {bg_color} !important; color: black !important; font-weight: 900 !important; text-align: center;'

def get_percentile(df, metric, value, p_type):
    if metric not in df.columns or pd.isna(value): return 50.0
    lower_is_better = ['Chase%', 'Whiff%', 'GB%', 'K%'] if p_type == '打者' else ['ERA', 'xERA', 'WHIP', 'FIP', 'BA', 'xBA', 'BB%', 'HardHit%', 'Barrel%', 'Diff']
    s = df[metric].dropna()
    if s.empty: return 50.0
    pr = (s < value).mean() * 100
    if metric in lower_is_better: pr = 100 - pr
    return round(pr, 1)

def get_relative_grade(df, metric, value, p_type):
    pr = get_percentile(df, metric, value, p_type)
    return score_to_grade(pr), pr

def format_metric(val, metric):
    if pd.isna(val) or val == "": return "-"
    if isinstance(val, str):
        try: val = float(val.replace(',', ''))
        except ValueError: return val
    fmt = STYLER_FORMATS.get(metric, "{:.2f}")
    try:
        res = fmt.format(val)
        return res.replace("0.", ".") if res.startswith("0.") and metric in ['AVG', 'OBP', 'SLG', 'OPS', 'BA'] else res
    except: return str(val)

def highlight_elite_stats(val, col, p_type):
    if pd.isna(val) or type(val) == str: return ''
    lower_is_better = ['Chase%', 'Whiff%', 'GB%', 'K%'] if p_type == '打者' else ['ERA', 'xERA', 'WHIP', 'FIP', 'BA', 'xBA', 'BB%', 'HardHit%', 'Barrel%', 'Diff']
    elite_thresholds_h = {'wRC+': 130, 'OPS': 0.850, 'WAR': 4.0, 'HR': 30, 'Sprint': 29.0, 'HardHit%': 45.0, 'Barrel%': 12.0}
    elite_thresholds_p = {'ERA': 3.00, 'WHIP': 1.10, 'K/9': 10.0, 'WAR': 3.5, 'K%': 28.0, 'xERA': 3.20}
    
    thresholds = elite_thresholds_h if p_type == '打者' else elite_thresholds_p
    is_elite = False
    
    if col in thresholds:
        if col in lower_is_better:
            is_elite = val <= thresholds[col]
        else:
            is_elite = val >= thresholds[col]
            
    if is_elite: return 'color: #D32F2F !important; font-weight: 900 !important; background-color: #ffebee !important;'
    return ''

def highlight_pr90(s):
    """
    全域熱圖高光函式：自動將所有模組(含球員個人面版) 的頂級/優良/偏弱數據上色
    使用淡色背景 + 飽和粗體字。
    """
    styles = [''] * len(s)
    
    # 判斷這欄是否為數值型態，若非數值則不上色
    if not pd.api.types.is_numeric_dtype(s):
        return styles
        
    for i, val in enumerate(s):
        if pd.isna(val):
            continue
            
        # 如果是 PR 值 (通常界於 0~100 之間)
        if s.name and 'PR' in str(s.name).upper():
            if val >= 90:
                styles[i] = 'color: #C62828 !important; background-color: #FFEBEE !important; font-weight: 900 !important;'
            elif val >= 75:
                styles[i] = 'color: #E65100 !important; background-color: #FFF3E0 !important; font-weight: 900 !important;'
            elif val <= 25:
                styles[i] = 'color: #1565C0 !important; background-color: #E3F2FD !important; font-weight: 900 !important;'
        
        # 針對傳統進階數據的攔截高光 (給球員個人面板使用)
        elif s.name in ['OPS', 'wOBA', 'xwOBA']:
            if val >= 0.900 or (s.name != 'OPS' and val >= 0.380):
                styles[i] = 'color: #C62828 !important; background-color: #FFEBEE !important; font-weight: 900 !important;'
            elif val >= 0.800 or (s.name != 'OPS' and val >= 0.340):
                styles[i] = 'color: #E65100 !important; background-color: #FFF3E0 !important; font-weight: 900 !important;'
        
        elif s.name in ['ERA', 'xERA', 'FIP']:
            if val > 0 and val <= 2.50:
                styles[i] = 'color: #C62828 !important; background-color: #FFEBEE !important; font-weight: 900 !important;'
            elif val > 0 and val <= 3.50:
                styles[i] = 'color: #E65100 !important; background-color: #FFF3E0 !important; font-weight: 900 !important;'
            elif val >= 5.00:
                styles[i] = 'color: #1565C0 !important; background-color: #E3F2FD !important; font-weight: 900 !important;'
                
    return styles


def translate_injury(desc):
    if not desc or pd.isna(desc): return "無詳細報告"
    return str(desc)

def generate_fun_nickname(row, p_type):
    if p_type == '打者':
        hr, sb, avg, ops, wrc, bb_pct, k_pct, hard, barrel, sprint, def_stat, rbi = row.get('HR',0), row.get('SB',0), row.get('AVG',0), row.get('OPS',0), row.get('wRC+',0), row.get('BB%',0), row.get('K%',0), row.get('HardHit%',0), row.get('Barrel%',0), row.get('Sprint',0), row.get('Def',0), row.get('RBI',0)
        
        if hr >= 50: return "👑 世代全壘打王"
        if hr >= 40 and sb >= 40: return "🐉 神話級雙棲巨獸"
        if hr >= 30 and sb >= 30: return "🦄 閃電怪力神獸"
        if hr >= 40: return "🌋 破壞神巨砲"
        if ops >= 1.000: return "🌟 史詩級神獸"
        if wrc >= 160: return "🚀 頂級進攻引擎"
        if sb >= 50: return "🌪️ 幻影神偷"
        if sb >= 40: return "⚡ 盜壘音速小子"
        if avg >= 0.330: return "🎯 絕對領域打擊王"
        if avg >= 0.310: return "🎯 無死角安打機器"
        if bb_pct >= 18.0: return "👁️ 究極選球眼"
        if bb_pct >= 15.0 and k_pct <= 15.0: return "🧠 絕對冷靜大師"
        if bb_pct >= 15.0: return "🦅 鷹眼選球大師"
        if barrel >= 18.0: return "💥 爆擊毀滅者"
        if hard >= 55.0: return "☄️ 爆擊外星人"
        if sprint >= 29.5: return "🐆 草上飛奔豹"
        if def_stat >= 20.0: return "🧱 絕對領域鐵壁"
        if def_stat >= 15.0: return "🛡️ 金手套魔術師"
        if ops >= 0.900: return "🔥 全能核彈頭"
        if hr >= 20 and sb >= 20: return "⚔️ 雙刀流遊俠"
        if rbi >= 100: return "🎰 終極打點狂人"
        if hr >= 25: return "🏏 重砲威脅"
        if avg >= 0.280 and ops >= 0.800: return "📈 高效能打擊機"
        if sb >= 25: return "🏃 壘包破壞者"
        if rbi >= 80: return "⚾ 穩定輸出核心"
        
        if k_pct >= 32.0: return "🪭 人體電風扇"
        if k_pct >= 28.0: return "💨 揮空製造機"
        if wrc > 0 and wrc <= 70: return "🧊 絕對冰河期"
        if ops > 0 and ops <= 0.600: return "🪫 貧打絕緣體"
        if row.get('GB%', 0) >= 55.0: return "🐜 地堂腿專家"
        if bb_pct > 0 and bb_pct <= 4.0: return "🪓 盲劍客"
        if sprint > 0 and sprint <= 25.0: return "🐢 重裝坦克"
        if def_stat > 0 and ops <= 0.650: return "🧤 純守備工具人"
        if avg > 0 and avg <= 0.200: return "📉 掙扎期打者"
        
        if ops > 0.750: return "⚖️ 中規中矩"
        if ops > 0.700: return "⚙️ 待開發戰力"
        return "🧩 替補陣容"
    else:
        k9, era, whip, gb, fip, sv, ip, xera, bb9, hld, qs, whiff = row.get('K/9',0), row.get('ERA',4.0), row.get('WHIP',1.5), row.get('GB%',0), row.get('FIP',4.0), row.get('SV',0), row.get('IP',0), row.get('xERA',4.0), row.get('BB/9',4.0), row.get('HLD',0), row.get('QS',0), row.get('Whiff%',0)
        hr, hr9 = row.get('HR', 0), row.get('HR/9', 0)
        if ip > 0 and hr9 == 0: hr9 = (hr / ip) * 9
        
        if era <= 1.50 and ip >= 100: return "👽 異次元壓制者"
        if k9 >= 13.0: return "⚡ 殘酷三振王"
        if k9 >= 11.5: return "🌪️ 終極 K 博士"
        if whip <= 0.90 and ip >= 50: return "👻 絕對虛無空間"
        if whip <= 1.00 and ip >= 80: return "🧊 絕對冰封大師"
        if era <= 2.20 and ip >= 100: return "🧱 銅牆鐵壁王牌"
        if era <= 2.80 and ip >= 120: return "🛡️ 菁英防禦陣"
        if xera <= 2.50: return "🔮 預判大師"
        if gb >= 60.0: return "🪨 重力滾地製造機"
        if gb >= 55.0: return "🎳 滾地球引誘機"
        if fip <= 2.50 and ip >= 80: return "⚖️ 真實壓制鬼才"
        if bb9 <= 1.5 and ip >= 100: return "🎯 究極控球儀"
        if sv >= 40: return "🚪 嘆息之牆"
        if sv >= 30: return "🔒 絕望關門死神"
        if ip >= 200: return "🤖 無情投球機器"
        if ip >= 180: return "🐎 鐵人耐戰馬"
        if whiff >= 35.0: return "🎭 變化球魔術師"
        
        if k9 >= 10.0 and era <= 3.50: return "⚔️ 剛猛火球男"
        if hld >= 25: return "🦾 鐵腕佈局橋樑"
        if qs >= 18: return "🌟 優質先發達人"
        if sv >= 15: return "🚒 危機撲火員"
        
        if era >= 6.00 and ip >= 30: return "🔥 頻繁發球機"
        if era >= 5.00 and ip >= 30: return "🧨 爆炸風險"
        if hr9 >= 1.8 and ip >= 30: return "🚀 煙火發射器"
        if bb9 >= 4.5 and ip >= 30: return "🧭 迷航發球機"
        if whip >= 1.50 and ip >= 30: return "🚶 壘包堆積機"
        if k9 > 0 and k9 <= 5.5 and ip >= 30: return "🥎 餵球達人"
        if fip >= 5.00 and ip >= 30: return "💣 危機製造者"
        if era >= 4.50 and ip >= 50: return "🎢 骰子型投手"
        
        if era <= 4.00: return "🎯 穩定輪值"
        if era <= 4.50: return "⚙️ 堪用戰力"
        return "🧩 替補陣容"

def generate_scout_conclusion(prs, p_prof, p_type):
    top_pr = max(prs.values()) if prs else 0
    bot_pr = min(prs.values()) if prs else 100
    
    if p_type == '打者':
        if prs.get('WAR', 0) >= 90: return "🎖️ MVP 級距建隊基石，擁有統治聯盟的影響力。"
        if prs.get('HR', 0) >= 85 and prs.get('HardHit%', 0) >= 85: return "🌋 聯盟頂尖重砲手，擁有改變戰局的破壞力。"
        if prs.get('Sprint', 0) >= 85 and prs.get('SB', 0) >= 80: return "⚡ 頂尖腿哥，在壘包上能給予對手極大壓迫感。"
        if prs.get('Def', 0) >= 85: return "🛡️ 金手套等級防守中樞，守備價值極高。"
        if top_pr < 60: return "⚠️ 表現低迷或出賽樣本不足，屬於替補或邊緣戰力。"
        if bot_pr > 40: return "⚖️ 攻守均衡的實用型球員，沒有明顯弱點。"
        return "⚔️ 具備特定專長的任務型球員。"
    else:
        if prs.get('WAR', 0) >= 90: return "🏆 賽揚獎等級王牌投手，輪值絕對核心。"
        if prs.get('K%', 0) >= 85 and prs.get('Whiff%', 0) >= 85: return "🌪️ 極致的三振機器，擁有頂級的揮空誘導能力。"
        if prs.get('GB%', 0) >= 85: return "🎳 滾地球大師，能有效製造雙殺化解危機。"
        if p_prof.get('Position') in ['RP', 'CL'] and prs.get('ERA', 0) >= 80: return "🔒 值得信賴的後防大將，勝利方程式核心。"
        if top_pr < 60: return "⚠️ 壓制力不足或樣本數小，屬於敗戰處理或邊緣戰力。"
        if bot_pr > 40: return "⚖️ 穩定的吃局數工作馬，輪值中後段要角。"
        return "🎯 具備特定球路優勢的功能性投手。"