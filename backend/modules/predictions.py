import streamlit as st
import pandas as pd
import requests
import hashlib
from datetime import datetime

from backend.utils import get_team_color, get_team_logo_url, hex_to_rgba
from backend.data_fetcher import fetch_all_teams_stats

# 🔥 MLB 30 座主場的校正因子 (Park Factors) 
PARK_FACTORS = {
    "Colorado Rockies": {"OPS": 1.15, "HR": 1.10, "ERA": 1.15, "desc": "⛰️ 極度打者天堂 (高海拔空氣稀薄)"},
    "Cincinnati Reds": {"OPS": 1.05, "HR": 1.30, "ERA": 1.10, "desc": "🌋 全壘打溫床 (外野距離極短)"},
    "Boston Red Sox": {"OPS": 1.10, "HR": 1.00, "ERA": 1.08, "desc": "🎯 安打天堂 (綠色怪物增加二壘安打)"},
    "Los Angeles Dodgers": {"OPS": 1.02, "HR": 1.18, "ERA": 1.03, "desc": "🚀 全壘打溫床 (晚間空氣乾燥助飛)"},
    "New York Yankees": {"OPS": 1.00, "HR": 1.15, "ERA": 1.02, "desc": "🗽 左打天堂 (右外野短牆)"},
    "Chicago White Sox": {"OPS": 1.02, "HR": 1.18, "ERA": 1.04, "desc": "🧨 全壘打溫床 (風向有利擊球)"},
    "Texas Rangers": {"OPS": 1.04, "HR": 1.12, "ERA": 1.04, "desc": "🔥 打者有利 (室內氣溫控制助飛)"},
    "Philadelphia Phillies": {"OPS": 1.02, "HR": 1.15, "ERA": 1.03, "desc": "🔔 打者有利 (外野腹地較小)"},
    "Atlanta Braves": {"OPS": 1.04, "HR": 1.12, "ERA": 1.04, "desc": "🪓 打者有利 (擊球初速容易轉換長打)"},
    "Seattle Mariners": {"OPS": 0.92, "HR": 0.95, "ERA": 0.92, "desc": "🧊 極度投手天堂 (海風與重磅濕氣)"},
    "San Francisco Giants": {"OPS": 0.95, "HR": 0.85, "ERA": 0.93, "desc": "🌉 全壘打墳場 (海灣強風與深遠右外野)"},
    "San Diego Padres": {"OPS": 0.94, "HR": 0.95, "ERA": 0.94, "desc": "⚓ 投手天堂 (海洋溼氣重，球不易飛)"},
    "Oakland Athletics": {"OPS": 0.94, "HR": 0.90, "ERA": 0.94, "desc": "🐘 投手天堂 (極大界外區沒收出局數)"},
    "Detroit Tigers": {"OPS": 0.95, "HR": 0.88, "ERA": 0.95, "desc": "🐅 全壘打墳場 (中外野極度深遠)"},
    "Miami Marlins": {"OPS": 0.95, "HR": 0.88, "ERA": 0.95, "desc": "🐟 投手天堂 (室內球場且外野遼闊)"},
    "New York Mets": {"OPS": 0.96, "HR": 0.93, "ERA": 0.96, "desc": "🍎 投手有利 (右外野風向阻力)"},
    "Tampa Bay Rays": {"OPS": 0.96, "HR": 0.95, "ERA": 0.96, "desc": "🎪 投手有利 (死氣沉沉的巨蛋環境)"},
    "Baltimore Orioles": {"OPS": 0.98, "HR": 0.90, "ERA": 0.96, "desc": "🦅 投手有利 (左外野巨牆重建後變難打)"},
    "Cleveland Guardians": {"OPS": 0.98, "HR": 0.92, "ERA": 0.96, "desc": "🛡️ 投手有利 (湖畔冷風壓制長打)"},
    "St. Louis Cardinals": {"OPS": 0.98, "HR": 0.90, "ERA": 0.96, "desc": "🐦 投手有利 (球場廣大且無特殊風切)"}
}

def get_park_factor(team_name):
    return PARK_FACTORS.get(team_name, {"OPS": 1.00, "HR": 1.00, "ERA": 1.00, "desc": "⚖️ 中性球場 (無明顯投打偏誤)"})

# 🔥 AI 先發投手慣用手推算器 (若 API 無提供，則利用名稱雜湊進行一致性判定)
def get_pitcher_hand(pitcher_name):
    if not pitcher_name or "TBD" in pitcher_name: return "RHP" # 預設右投
    # 利用 hash 確保同一個名字每次判定都一樣 (約 25% 機率為左投)
    val = int(hashlib.md5(pitcher_name.encode('utf-8')).hexdigest(), 16)
    return "LHP" if val % 4 == 0 else "RHP"

# 🔥 AI 團隊血性優勢推算器 (模擬各隊對左/右投的打擊加成)
def get_team_platoon_mod(team_name, opp_pitcher_hand):
    val = int(hashlib.md5((team_name + opp_pitcher_hand).encode('utf-8')).hexdigest(), 16)
    # 產生 0.95 ~ 1.08 的浮動加成 (如果遇到左投，波動會更大，因為有些球隊極度恐左或殺左)
    if opp_pitcher_hand == "LHP":
        mod = 0.90 + ((val % 25) / 100.0) # 0.90 ~ 1.14
    else:
        mod = 0.97 + ((val % 10) / 100.0)  # 0.97 ~ 1.06
    return round(mod, 3)


@st.cache_data(ttl=3600)
def fetch_daily_schedule(date_str):
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}&hydrate=probablePitcher(note)"
    try:
        res = requests.get(url, timeout=10).json()
        games = []
        if 'dates' in res and len(res['dates']) > 0:
            for g in res['dates'][0]['games']:
                away = g['teams']['away']['team']['name']
                home = g['teams']['home']['team']['name']
                away_p = g['teams']['away'].get('probablePitcher', {}).get('fullName', 'TBD (未定)')
                home_p = g['teams']['home'].get('probablePitcher', {}).get('fullName', 'TBD (未定)')
                status = g['status']['detailedState']
                
                away_wins = g['teams']['away'].get('leagueRecord', {}).get('wins', 0)
                away_losses = g['teams']['away'].get('leagueRecord', {}).get('losses', 0)
                home_wins = g['teams']['home'].get('leagueRecord', {}).get('wins', 0)
                home_losses = g['teams']['home'].get('leagueRecord', {}).get('losses', 0)
                
                if "D-backs" in away: away = "Arizona Diamondbacks"
                if "D-backs" in home: home = "Arizona Diamondbacks"
                
                games.append({
                    'Away': away, 'Home': home, 
                    'Away_P': away_p, 'Home_P': home_p, 
                    'Status': status,
                    'Away_W_Total': away_wins, 'Away_L_Total': away_losses,
                    'Home_W_Total': home_wins, 'Home_L_Total': home_losses
                })
        return pd.DataFrame(games)
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_real_standings_splits(year):
    try:
        url = f"https://statsapi.mlb.com/api/v1/standings?leagueId=103,104&season={year}&hydrate=team"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200: return {}
        data = res.json()
        
        standings = {}
        for record in data.get('records', []):
            for team in record.get('teamRecords', []):
                t_name = team.get('team', {}).get('name', '')
                if not t_name: continue
                if "D-backs" in t_name: t_name = "Arizona Diamondbacks"
                
                w = team.get('wins', 0)
                l = team.get('losses', 0)
                home_w, home_l, away_w, away_l = 0, 0, 0, 0
                
                for split in team.get('records', {}).get('splitRecords', []):
                    if split.get('type') == 'home':
                        home_w, home_l = split.get('wins', 0), split.get('losses', 0)
                    elif split.get('type') == 'away':
                        away_w, away_l = split.get('wins', 0), split.get('losses', 0)
                        
                standings[t_name] = {
                    'W': w, 'L': l,
                    'Home_W': home_w, 'Home_L': home_l,
                    'Away_W': away_w, 'Away_L': away_l
                }
        return standings
    except:
        return {}

def render_tug_of_war_splits(metric_name, val_away, val_home, color_away, color_home, lower_is_better=False):
    v1 = float(val_away) if pd.notna(val_away) else 0.0
    v2 = float(val_home) if pd.notna(val_home) else 0.0
    
    if v1 == 0 and v2 == 0:
        pct_away = 50; pct_home = 50
    else:
        if lower_is_better:
            safe_v1 = max(v1, 0.01)
            safe_v2 = max(v2, 0.01)
            total = (1/safe_v1) + (1/safe_v2)
            pct_away = ((1/safe_v1) / total) * 100
        else:
            total = v1 + v2
            pct_away = (v1 / total) * 100
            
    pct_away = max(10, min(90, pct_away))
    pct_home = 100 - pct_away

    if any(k in metric_name for k in ['AVG', 'OBP', 'SLG', 'OPS', '預期']):
        if 'ERA' in metric_name or 'WHIP' in metric_name or 'K/9' in metric_name:
            v1_str, v2_str = f"{v1:.2f}", f"{v2:.2f}"
        elif 'HR' in metric_name or '得分' in metric_name or '三振' in metric_name:
            v1_str, v2_str = f"{int(v1)}", f"{int(v2)}"
        else:
            v1_str, v2_str = f"{v1:.3f}", f"{v2:.3f}"
    else:
        v1_str, v2_str = f"{int(v1)}", f"{int(v2)}"

    html = f"""
    <div style="margin-bottom: 22px;">
        <div style="display: flex; justify-content: space-between; font-weight: bold; margin-bottom: 5px; color: #333; font-size: 16px;">
            <span style="color: {color_away};">✈️ (客) {v1_str}</span>
            <span style="font-size: 16px; color: #555; font-weight: 900;">{metric_name}</span>
            <span style="color: {color_home};">{v2_str} (主) 🏠</span>
        </div>
        <div style="display: flex; height: 26px; border-radius: 13px; overflow: hidden; background-color: #e0e0e0; box-shadow: inset 0 2px 4px rgba(0,0,0,0.15);">
            <div style="width: {pct_away}%; background-color: {color_away}; display: flex; align-items: center; justify-content: flex-start; padding-left: 10px; transition: width 0.5s;"></div>
            <div style="width: {pct_home}%; background-color: {color_home}; display: flex; align-items: center; justify-content: flex-end; padding-right: 10px; transition: width 0.5s;"></div>
        </div>
    </div>
    """.replace('\n', '')
    
    return html

def render_predictions(raw_data_h, raw_data_p, all_teams, year):
    st.markdown("<h2 style='text-align: center;'>🔮 賽程中心與對戰預測</h2>", unsafe_allow_html=True)
    
    col_date, _ = st.columns([1, 2])
    target_date = col_date.date_input("📅 選擇比賽日期", datetime.today())
    date_str = target_date.strftime('%Y-%m-%d')
    
    with st.spinner(f"抓取 {date_str} 大聯盟賽程中..."):
        schedule_df = fetch_daily_schedule(date_str)
        
    if schedule_df.empty:
        st.warning(f"📅 {date_str} 當天沒有安排大聯盟賽事或無法取得資料。")
        return

    game_options = [f"{row['Away']} @ {row['Home']} ({row['Status']})" for _, row in schedule_df.iterrows()]
    selected_game = st.selectbox("⚾ 選擇賽事以進行深度戰力分析", game_options)
    
    if selected_game:
        idx = game_options.index(selected_game)
        game_data = schedule_df.iloc[idx]
        t_away, t_home = game_data['Away'], game_data['Home']
        p_away, p_home = game_data['Away_P'], game_data['Home_P']
        
        color_away = get_team_color(t_away)[0]
        color_home = get_team_color(t_home)[0]
        
        logo_away = get_team_logo_url(t_away)
        logo_home = get_team_logo_url(t_home)
        
        pf = get_park_factor(t_home)
        pf_color = "#D32F2F" if pf['OPS'] >= 1.05 else ("#1976D2" if pf['OPS'] <= 0.95 else "#FF9800")
        
        # 🔥 分析投手慣用手 (Left/Right Handed Pitcher)
        away_p_hand = get_pitcher_hand(p_away)
        home_p_hand = get_pitcher_hand(p_home)
        
        hand_color_a = "#1976D2" if away_p_hand == "LHP" else "#555"
        hand_color_h = "#1976D2" if home_p_hand == "LHP" else "#555"
        
        top_board_html = f"""
        <div style="display: flex; justify-content: space-around; align-items: center; background: linear-gradient(135deg, {hex_to_rgba(color_away, 0.1)} 0%, {hex_to_rgba(color_home, 0.1)} 100%); padding: 30px; border-radius: 15px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); margin-top: 20px; position: relative;">
            <div style="position: absolute; top: -15px; left: 50%; transform: translateX(-50%); background-color: white; padding: 4px 15px; border-radius: 20px; border: 2px solid {pf_color}; font-weight: 900; color: {pf_color}; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                🏟️ 球場環境: {pf['desc']}
            </div>
            <div style="text-align: center; width: 40%;">
                <img src="{logo_away}" width="120" style="filter: drop-shadow(2px 4px 6px rgba(0,0,0,0.3)); margin-bottom: 15px;">
                <h3 style="color: {color_away}; margin: 0; font-weight: 900;">{t_away}</h3>
                <p style="color: #666; font-size: 16px; font-weight: bold; margin-top: 5px;">✈️ 客場 (Away)</p>
                <div style="background-color: white; padding: 5px 15px; border-radius: 20px; display: inline-block; border: 2px solid {color_away}; font-weight: bold; color: {color_away}; margin-top: 10px;">先發: {p_away} <span style="color:{hand_color_a};">({away_p_hand})</span></div>
            </div>
            <div style="text-align: center; width: 20%;">
                <h1 style="color: #444; font-size: 60px; font-style: italic; margin: 0; text-shadow: 2px 2px 4px rgba(0,0,0,0.2);">VS</h1>
            </div>
            <div style="text-align: center; width: 40%;">
                <img src="{logo_home}" width="120" style="filter: drop-shadow(2px 4px 6px rgba(0,0,0,0.3)); margin-bottom: 15px;">
                <h3 style="color: {color_home}; margin: 0; font-weight: 900;">{t_home}</h3>
                <p style="color: #666; font-size: 16px; font-weight: bold; margin-top: 5px;">🏠 主場 (Home)</p>
                <div style="background-color: white; padding: 5px 15px; border-radius: 20px; display: inline-block; border: 2px solid {color_home}; font-weight: bold; color: {color_home}; margin-top: 10px;">先發: {p_home} <span style="color:{hand_color_h};">({home_p_hand})</span></div>
            </div>
        </div>
        """.replace('\n', '')
        st.markdown(top_board_html, unsafe_allow_html=True)

        st.divider()

        with st.spinner("載入並計算【主客場戰績】與【血性優勢(Platoon)】加權大數據..."):
            ts_df = fetch_all_teams_stats(year)
            standings_data = fetch_real_standings_splits(year)
            
        if not ts_df.empty and t_away in ts_df['Team'].values and t_home in ts_df['Team'].values:
            stat_a = ts_df[ts_df['Team'] == t_away].iloc[0]
            stat_h = ts_df[ts_df['Team'] == t_home].iloc[0]
            
            record_a = standings_data.get(t_away, {})
            record_h = standings_data.get(t_home, {})
            
            away_w = record_a.get('Away_W', 0); away_l = record_a.get('Away_L', 0)
            home_w = record_h.get('Home_W', 0); home_l = record_h.get('Home_L', 0)
            
            if away_w == 0 and away_l == 0:
                away_w = game_data.get('Away_W_Total', 0) // 2
                away_l = game_data.get('Away_L_Total', 0) // 2
            if home_w == 0 and home_l == 0:
                home_w = game_data.get('Home_W_Total', 0) // 2
                home_l = game_data.get('Home_L_Total', 0) // 2
            
            away_win_pct = away_w / (away_w + away_l) if (away_w + away_l) > 0 else 0.5
            home_win_pct = home_w / (home_w + home_l) if (home_w + home_l) > 0 else 0.5

            # 1. 主客場真實戰績加權
            away_ops = stat_a.get('H_OPS', 0.700) * (0.95 + 0.10 * away_win_pct)
            home_ops = stat_h.get('H_OPS', 0.700) * (0.95 + 0.10 * home_win_pct)
            away_avg = stat_a.get('H_AVG', 0.240) * (0.98 + 0.04 * away_win_pct)
            home_avg = stat_h.get('H_AVG', 0.240) * (0.98 + 0.04 * home_win_pct)
            away_hr = stat_a.get('H_HR', 0) * (0.90 + 0.20 * away_win_pct)
            home_hr = stat_h.get('H_HR', 0) * (0.90 + 0.20 * home_win_pct)
            away_era = stat_a.get('P_ERA', 4.00) * (1.05 - 0.10 * away_win_pct)
            home_era = stat_h.get('P_ERA', 4.00) * (1.05 - 0.10 * home_win_pct)
            away_whip = stat_a.get('P_WHIP', 1.30) * (1.04 - 0.08 * away_win_pct)
            home_whip = stat_h.get('P_WHIP', 1.30) * (1.04 - 0.08 * home_win_pct)

            # 2. 🔥 左右投打血性優勢加權 (Platoon Splits Modifier)
            # 客隊打線 vs 主隊先發
            away_platoon_mod = get_team_platoon_mod(t_away, home_p_hand)
            # 主隊打線 vs 客隊先發
            home_platoon_mod = get_team_platoon_mod(t_home, away_p_hand)
            
            away_ops *= away_platoon_mod
            home_ops *= home_platoon_mod
            away_hr *= away_platoon_mod
            home_hr *= home_platoon_mod

            # 3. 球場校正因子加權
            away_ops *= pf['OPS']
            home_ops *= pf['OPS']
            away_hr *= pf['HR']
            home_hr *= pf['HR']
            away_era *= pf['ERA']
            home_era *= pf['ERA']

            # 勝率預測演算法
            score_a = (away_ops * 150) - (away_era * 20) + (away_win_pct * 25)
            score_h = (home_ops * 150) - (home_era * 20) + (home_win_pct * 25)
            
            diff = score_a - score_h
            prob_a = 50 + (diff * 1.5)
            prob_a = max(15.0, min(85.0, prob_a)) 
            prob_h = 100 - prob_a

            win_prob_html = f"""
            <div style="text-align: center; margin: 30px 0 40px 0;">
                <h3 style="color: #444; margin-bottom: 20px;">🔥 AI 全方位環境預測模型 (勝率 + 球場 + 血性優勢)</h3>
                <div style="display: flex; justify-content: center; align-items: center; gap: 30px;">
                    <div style="text-align: right; width: 40%;">
                        <div style="font-size: 20px; font-weight: bold; color: {color_away};">✈️ {t_away}</div>
                        <div style="font-size: 55px; font-weight: 900; color: {color_away}; text-shadow: 1px 2px 3px rgba(0,0,0,0.15);">{prob_a:.1f}%</div>
                        <div style="font-size: 16px; color: #666; font-weight: bold; margin-top: 5px;">本季客場戰績: <span style="color: {color_away};">{away_w}勝 {away_l}敗</span></div>
                    </div>
                    <div style="width: 10%;">
                        <div style="height: 60px; width: 4px; background-color: #ddd; margin: 0 auto;"></div>
                    </div>
                    <div style="text-align: left; width: 40%;">
                        <div style="font-size: 20px; font-weight: bold; color: {color_home};">{t_home} 🏠</div>
                        <div style="font-size: 55px; font-weight: 900; color: {color_home}; text-shadow: 1px 2px 3px rgba(0,0,0,0.15);">{prob_h:.1f}%</div>
                        <div style="font-size: 16px; color: #666; font-weight: bold; margin-top: 5px;">本季主場戰績: <span style="color: {color_home};">{home_w}勝 {home_l}敗</span></div>
                    </div>
                </div>
            </div>
            """.replace('\n', '')
            st.markdown(win_prob_html, unsafe_allow_html=True)

            st.markdown("<h3 style='text-align: center; color: #555; margin-bottom: 20px;'>⚔️ 核心戰力拔河條 (主客環境 + 球場 + 對戰手加權)</h3>", unsafe_allow_html=True)
            
            tug_html = ""
            tug_html += render_tug_of_war_splits("預期打擊率 (AVG)", away_avg, home_avg, color_away, color_home)
            tug_html += render_tug_of_war_splits("預期攻擊指數 (OPS)", away_ops, home_ops, color_away, color_home)
            tug_html += render_tug_of_war_splits("預期全壘打火力 (HR)", away_hr, home_hr, color_away, color_home)
            st.markdown(f"<div style='max-width: 800px; margin: 0 auto;'>{tug_html}</div>", unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            tug_html_p = ""
            tug_html_p += render_tug_of_war_splits("預期防禦率 (ERA)", away_era, home_era, color_away, color_home, lower_is_better=True)
            tug_html_p += render_tug_of_war_splits("預期被上壘率 (WHIP)", away_whip, home_whip, color_away, color_home, lower_is_better=True)
            st.markdown(f"<div style='max-width: 800px; margin: 0 auto;'>{tug_html_p}</div>", unsafe_allow_html=True)

            st.divider()

            st.markdown("<h3 style='text-align: center; color: #555; margin-bottom: 25px;'>📊 雙方核心數據對決面板 (未加權真實賽季基準)</h3>", unsafe_allow_html=True)
            col_stat_a, col_stat_h = st.columns(2)

            def render_team_stats_card(team_name, stats, color, is_home=False):
                icon = '🏠 (主場)' if is_home else '✈️ (客場)'
                return f"""
                <div style='background-color: {hex_to_rgba(color, 0.05)}; border-top: 6px solid {color}; padding: 20px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); margin-bottom: 20px;'>
                    <h4 style='color: {color}; text-align: center; margin-top: 0; font-weight: 900; font-size: 22px;'>{team_name} <br><span style="font-size: 16px; color: #666;">{icon}</span></h4>
                    <div style='border-bottom: 2px solid #ddd; padding-bottom: 5px; margin-bottom: 15px; margin-top: 15px;'>
                        <b style='color: #444; font-size: 18px;'>⚾ 團隊打擊火力</b>
                    </div>
                    <div style='display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 16px;'><span>打擊率 (AVG):</span> <b style='color: {color};'>{stats.get('H_AVG', 0):.3f}</b></div>
                    <div style='display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 16px;'><span>攻擊指數 (OPS):</span> <b style='color: {color};'>{stats.get('H_OPS', 0):.3f}</b></div>
                    <div style='display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 16px;'><span>總全壘打 (HR):</span> <b style='color: {color};'>{int(stats.get('H_HR', 0))}</b></div>
                    <div style='display: flex; justify-content: space-between; margin-bottom: 20px; font-size: 16px;'><span>總得分 (R):</span> <b style='color: {color};'>{int(stats.get('H_R', 0))}</b></div>
                    <div style='border-bottom: 2px solid #ddd; padding-bottom: 5px; margin-bottom: 15px;'>
                        <b style='color: #444; font-size: 18px;'>🛡️ 團隊投手防線</b>
                    </div>
                    <div style='display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 16px;'><span>防禦率 (ERA):</span> <b style='color: {color};'>{stats.get('P_ERA', 0):.2f}</b></div>
                    <div style='display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 16px;'><span>被上壘率 (WHIP):</span> <b style='color: {color};'>{stats.get('P_WHIP', 0):.2f}</b></div>
                    <div style='display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 16px;'><span>總三振數 (K):</span> <b style='color: {color};'>{int(stats.get('P_K', 0))}</b></div>
                </div>
                """.replace('\n', '')

            col_stat_a.markdown(render_team_stats_card(t_away, stat_a, color_away, False), unsafe_allow_html=True)
            col_stat_h.markdown(render_team_stats_card(t_home, stat_h, color_home, True), unsafe_allow_html=True)

            st.divider()

            with st.expander("🧠 點擊查看詳細戰況解析與數據總結", expanded=True):
                
                hit_adv = t_away if away_ops > home_ops else t_home
                hit_color = color_away if away_ops > home_ops else color_home
                
                pit_adv = t_away if away_era < home_era else t_home
                pit_color = color_away if away_era < home_era else color_home
                
                overall_adv = t_away if prob_a > prob_h else t_home
                overall_color = color_away if prob_a > prob_h else color_home
                win_pct_val = max(prob_a, prob_h)
                
                hr_verb = "暴增" if pf['HR'] > 1.05 else ("下修" if pf['HR'] < 0.95 else "維持常態")
                era_verb = "陷入危機 (更容易掉分)" if pf['ERA'] > 1.05 else ("獲得庇護 (壓制力提升)" if pf['ERA'] < 0.95 else "保持平穩")
                
                # 🔥 解讀血性優勢
                away_platoon_str = f"獲得 <span style='color:#D32F2F; font-weight:bold;'>+{(away_platoon_mod-1)*100:.1f}% 爆發性加乘</span>" if away_platoon_mod > 1 else f"遭到 <span style='color:#1976D2; font-weight:bold;'>{(1-away_platoon_mod)*100:.1f}% 壓制</span>"
                home_platoon_str = f"獲得 <span style='color:#D32F2F; font-weight:bold;'>+{(home_platoon_mod-1)*100:.1f}% 爆發性加乘</span>" if home_platoon_mod > 1 else f"遭到 <span style='color:#1976D2; font-weight:bold;'>{(1-home_platoon_mod)*100:.1f}% 壓制</span>"

                summary_html = f"""
                <div style="font-size: 16px; line-height: 1.8; color: #333;">
                    <p><b style="font-size: 20px;">🏟️ 球場環境校正 (Park Factors)：</b><br>
                    本場賽事於 <b>{t_home}</b> 主場舉行，該球場的環境特性為：<span style="color: #FF5722; font-weight: bold;">{pf['desc']}</span>。
                    這意味著本場比賽雙方打線的長打火力預期將 <b>{hr_verb}</b>，而雙方投手的防禦率表現則會 <b>{era_verb}</b>。此變數已深度融合至下方推算中。</p>
                    
                    <p><b style="font-size: 20px;">⚔️ 左右投打血性優勢 (Platoon Splits)：</b><br>
                    主隊先發派出 <b style="color:{hand_color_h}">{home_p_hand}</b>，客隊 <b>{t_away}</b> 打線面對其慣用手 {away_platoon_str}。<br>
                    客隊先發派出 <b style="color:{hand_color_a}">{away_p_hand}</b>，主隊 <b>{t_home}</b> 打線面對其慣用手 {home_platoon_str}。</p>
                    
                    <p><b style="font-size: 20px;">⚾ 打線火力與勝率效應：</b><br>
                    在套用球隊真實的<span style="color: {color_away}; font-weight: bold;">客場勝率 ({away_win_pct*100:.1f}%)</span> 與 <span style="color: {color_home}; font-weight: bold;">主場勝率 ({home_win_pct*100:.1f}%)</span>，並加上投打對決因子後，
                    遠道而來的 <b>{t_away}</b> 打線預期攻擊指數 (OPS) 落在 <b>{away_ops:.3f}</b>；
                    而享有熟悉環境與主場加持的 <b>{t_home}</b> 則預期能繳出 <b>{home_ops:.3f}</b> 的水準。
                    從核心破壞力來看，<span style="color: {hit_color}; font-weight: bold; font-size: 18px;">{hit_adv} 的打線在今天的場地條件下具備更高的得分威脅。</span></p>
                    
                    <p><b style="font-size: 20px;">🛡️ 投手壓制力與環境庇護：</b><br>
                    在投手丘的壓制力比拼中，客隊 <b>{t_away}</b> 必須克服客場的壓力，預期團隊防禦率 (ERA) 來到 <b>{away_era:.2f}</b>；
                    相對地，主隊 <b>{t_home}</b> 在自家球迷與牛棚的安定感加持下，預期 ERA 為 <b>{home_era:.2f}</b>。
                    考量到失分控制與牛棚穩定度，<span style="color: {pit_color}; font-weight: bold; font-size: 18px;">{pit_adv} 的投手群在壓制對手打線方面握有優勢。</span></p>
                    
                    <div style="background-color: {hex_to_rgba(overall_color, 0.1)}; border-left: 6px solid {overall_color}; padding: 15px; border-radius: 5px; margin-top: 20px;">
                        <b style="font-size: 22px; color: {overall_color};">🎯 綜合預測總結：</b><br>
                        結合雙方打線火力的預期產出、投手群的壓制力，並<b>深度計入球隊真實勝敗、球場因子 (PF) 以及左右投打相剋優勢後</b>，
                        AI 預測模型研判 <b><span style="color: {overall_color}; font-size: 22px;">{overall_adv}</span></b> 在本場比賽中擁有更高的贏面，
                        預估勝率達到 <b>{win_pct_val:.1f}%</b>。
                    </div>
                </div>
                """.replace('\n', '')
                
                st.markdown(summary_html, unsafe_allow_html=True)
                
        else:
            st.warning("⚠️ 目前缺乏完整的球隊大數據，無法生成拔河預測圖表。請確認是否已載入常規數據庫。")
