import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import re
import requests
import unicodedata
from datetime import datetime, timedelta
from streamlit_option_menu import option_menu

from backend.config import MLB_TEAM_IDS, exclude_cols, STYLER_FORMATS
from backend.utils import (
    get_team_color, get_team_logo_url, hex_to_rgba, generate_fun_nickname,
    fetch_team_standings, generate_scout_conclusion, get_percentile, score_to_grade, style_grade, 
    highlight_elite_stats, format_metric, darken_color, highlight_pr90
)
from backend.data_fetcher import (
    fetch_player_handedness, fetch_player_gamelog, fetch_recent_form_ranking,
    fetch_savant_platoon_splits, fetch_player_home_away_splits, fetch_player_career,
    fetch_all_teams_stats, fetch_team_recent_matchups, fetch_team_roster,
    fetch_team_injury_list
)
from backend.ui_utils import color_rank_rows

def render_deep_search(raw_data_h, raw_data_p, all_players, today_str, all_nicknames, year):
    
    def get_fmt_dict(df):
        fmt = {}
        num_cols = df.select_dtypes(include=['number']).columns
        for c in df.columns:
            if c in STYLER_FORMATS:
                fmt[c] = STYLER_FORMATS[c]
            elif c in num_cols:
                fmt[c] = lambda x: f"{int(x)}" if pd.notna(x) and float(x).is_integer() else (f"{round(float(x), 3)}" if pd.notna(x) else "-")
        return fmt

    def norm_name(n):
        if not isinstance(n, str): return str(n)
        return unicodedata.normalize('NFD', n).encode('ascii', 'ignore').decode('utf-8').replace('Jr.', '').replace('Sr.', '').strip().lower()

    col_type, _ = st.columns([1, 3])
    with col_type:
        p_type = option_menu(
            None, ["打者", "投手"], icons=["person-arms-up", "bullseye"],
            default_index=0 if st.session_state.get('main_p_type', '打者') == '打者' else 1,
            orientation="horizontal",
            styles={
                "container": {"padding": "0!important", "margin": "0", "background-color": "#F0F2F6", "border-radius": "15px"},
                "nav-link": {"font-size": "14px", "padding": "5px"},
                "nav-link-selected": {"background-color": "#0C2340", "color": "white"}
            }
        )
    
    st.session_state.main_p_type = p_type
    raw_data = raw_data_h if p_type == '打者' else raw_data_p
    
    # 🔥 全域資料融合：用來抓取跨投打的「所有守位」與「傷病紀錄」
    all_raw_combined = pd.concat([raw_data_h, raw_data_p], ignore_index=True)
    
    current_players = sorted(raw_data['Player'].unique().tolist())
    current_nicknames = sorted([n for n in raw_data['Nickname'].unique() if isinstance(n, str) and n])
    all_teams = sorted(list(MLB_TEAM_IDS.keys()))

    selected_search = option_menu(
        None, 
        options=["🧑 球員個人面版", "🏟️ 球隊戰情室", "🎭 外號同好會"],
        default_index=0,
        orientation="horizontal",
        key="search_type_menu",
        styles={
            "container": {"padding": "0!important", "max-width": "800px", "margin": "0 auto 20px auto", "background-color": "#F0F2F6", "border-radius": "25px"},
            "nav-link": {"font-size": "16px", "font-weight": "bold", "color": "#555"},
            "nav-link-selected": {"background-color": "#134A8E", "color": "white"} # 藍鳥藍
        }
    )
    
    if selected_search == "🧑 球員個人面版":
        target_profile = st.selectbox(f"🔍 搜尋{p_type} (進入專屬面版)", options=current_players, index=None, placeholder="點選或輸入名字")
        if target_profile and not raw_data.empty:
            p_data = raw_data[raw_data['Player'] == target_profile]
            if not p_data.empty:
                p_prof = p_data.iloc[0]
                t_colors = get_team_color(p_prof['Team'])
                logo_url = get_team_logo_url(p_prof['Team'])
                hand_info = fetch_player_handedness(p_prof['Player_ID'])
                logo_html = f"<img src='{logo_url}' width='45' style='vertical-align: middle; margin-right: 12px;'>" if logo_url else ""
                
                # 🔥 目標 2: 抓取該球員「所有能守的位置」
                p_all_data = all_raw_combined[all_raw_combined['Player'] == target_profile]
                all_positions = []
                for pos in p_all_data['Position'].dropna():
                    for p in str(pos).split(','):
                        p_clean = p.strip()
                        if p_clean and p_clean not in all_positions:
                            all_positions.append(p_clean)
                player_position = ", ".join(all_positions)
                pos_display = f" | 🛡️ {player_position}" if player_position else ""
                
                st.markdown(f"<h2 style='color:{t_colors[0]}; border-bottom: 3px solid {t_colors[0]}; padding-bottom: 10px;'>{logo_html} {target_profile}{pos_display} ({hand_info}) | {p_prof['Team']}</h2>", unsafe_allow_html=True)
                
                # 🔥 目標 1 & 2: 個人面板深度醫療報告攔截
                player_inj_detail = ""
                t_id = MLB_TEAM_IDS.get(p_prof['Team'])
                if t_id:
                    try:
                        end_date = datetime.now().strftime("%Y-%m-%d")
                        start_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
                        tx_url = f"https://statsapi.mlb.com/api/v1/transactions?teamId={t_id}&startDate={start_date}&endDate={end_date}"
                        tx_res = requests.get(tx_url, timeout=3).json()
                        p_norm = norm_name(target_profile)
                        for tx in tx_res.get('transactions', []):
                            desc = tx.get('description', '')
                            tx_nm = norm_name(tx.get('person', {}).get('fullName', ''))
                            if tx_nm == p_norm and ('injured' in desc.lower() or 'il' in desc.lower() or 'placed' in desc.lower() or 'strain' in desc.lower() or 'surgery' in desc.lower()):
                                if len(desc) > len(player_inj_detail):
                                    player_inj_detail = desc
                    except: pass

                if not player_inj_detail:
                    i_val = str(p_prof.get('Injury', '')).strip()
                    if i_val and i_val not in ['nan', 'None']:
                        player_inj_detail = i_val

                if player_inj_detail:
                    st.markdown(f"<div style='background-color: #ffebee; color: #D32F2F; padding: 12px 20px; border-radius: 6px; font-weight: bold; margin-bottom: 20px; border-left: 6px solid #D32F2F; font-size: 1.15em; line-height: 1.4;'>🏥 傷病報告：{player_inj_detail}</div>", unsafe_allow_html=True)

                custom_table_styles = [
                    {'selector': 'th', 'props': [('background-color', f'{t_colors[0]} !important'), ('color', 'white !important')]}
                ]

                global_metrics = [c for c in raw_data.columns if c not in exclude_cols and c != 'Nickname']
                eval_metrics = ['WAR', 'wRC+', 'OPS', 'HR', 'Sprint', 'Def', 'HardHit%', 'Barrel%'] if p_type == '打者' else ['WAR', 'ERA', 'WHIP', 'K/9', 'BB/9', 'FIP', 'xERA', 'Whiff%']
                eval_metrics = [m for m in eval_metrics if m in raw_data.columns]

                prs = {}
                for m in eval_metrics:
                    try: prs[m] = get_percentile(raw_data, m, p_prof[m], p_type)
                    except: pass

                scout_conclusion = generate_scout_conclusion(prs, p_prof, p_type)
                st.markdown(f'''
                    <div style="background-color: {t_colors[0]}; padding: 15px 20px; border-radius: 5px; margin-bottom: 20px; box-shadow: 0 4px 8px rgba(0,0,0,0.15);">
                        <h4 style="margin-top: 0; color: {t_colors[1]}; text-shadow: 1px 1px 2px rgba(0,0,0,0.5);">📋 球探總結報告</h4>
                        <p style="font-size: 18px; font-weight: bold; color: {t_colors[1]}; margin: 0; line-height: 1.5; text-shadow: 1px 1px 2px rgba(0,0,0,0.5);">{scout_conclusion}</p>
                    </div>
                ''', unsafe_allow_html=True)

                col_pr_chart, col_pr_bar = st.columns([1, 1])
                if prs:
                    fig_pr = go.Figure(go.Scatterpolar(
                        r=list(prs.values()) + [list(prs.values())[0]],
                        theta=list(prs.keys()) + [list(prs.keys())[0]],
                        fill='toself', line_color=t_colors[0], fillcolor=hex_to_rgba(t_colors[0], 0.4)
                    ))
                    fig_pr.update_layout(polar=dict(radialaxis=dict(range=[0, 100], tickfont=dict(size=10))), height=350, margin=dict(l=20, r=20, t=20, b=20))
                    col_pr_chart.plotly_chart(fig_pr, use_container_width=True)

                    with col_pr_bar:
                        st.markdown(f"<h4 style='color: {t_colors[0]};'>⚡ 核心能力 PR 值 (百分位)</h4>", unsafe_allow_html=True)
                        for m, pr in prs.items():
                            val_str = format_metric(p_prof[m], m)
                            pr_color = "#D32F2F" if pr >= 80 else ("#1976D2" if pr >= 50 else "#757575")
                            st.markdown(f"""
                                <div style="margin-bottom: 8px;">
                                    <div style="display: flex; justify-content: space-between; font-size: 14px; font-weight: bold; margin-bottom: 2px;">
                                        <span>{m} ({val_str})</span><span style="color: {pr_color}">PR {pr:.0f}</span>
                                    </div>
                                    <div style="width: 100%; background-color: #E0E0E0; border-radius: 4px; height: 10px;">
                                        <div style="width: {pr}%; background-color: {t_colors[0]}; height: 100%; border-radius: 4px;"></div>
                                    </div>
                                </div>
                            """, unsafe_allow_html=True)

                st.divider()

                def style_gamelog(row):
                    styles = [''] * len(row)
                    for i, col in enumerate(row.index):
                        if 'Opponent' in col or '對手' in col:
                            opp_val = str(row[col])
                            opp_clean = re.sub(r'[^a-zA-Z\s]', '', opp_val).strip()
                            opp_color = get_team_color(opp_clean)[0]
                            styles[i] = f'color: {opp_color} !important; font-weight: 900 !important; font-size: 1.15em !important;'
                    return styles

                st.markdown(f"<h4 style='color: {t_colors[0]};'>📅 近期出賽紀錄 (Game Log)</h4>", unsafe_allow_html=True)
                gamelog_df = fetch_player_gamelog(int(p_prof['Player_ID']), p_type, year)
                if gamelog_df is not None and not gamelog_df.empty:
                    recent_5 = gamelog_df.head(10).copy()
                    show_cols = ['Date', 'Opponent', '主/客', 'AB', 'R', 'H', 'RBI', 'HR', 'SB', 'BB', 'K'] if p_type == '打者' else ['Date', 'Opponent', '主/客', 'IP', 'H', 'R', 'ER', 'BB', 'K', 'PC']
                    
                    styled_html_gamelog = recent_5[[c for c in show_cols if c in recent_5.columns]].style\
                        .apply(style_gamelog, axis=1)\
                        .set_table_styles(custom_table_styles)\
                        .format(get_fmt_dict(recent_5), na_rep="-").hide(axis='index').to_html()
                        
                    st.markdown(f"<div class='table-scroll-container'>{styled_html_gamelog}</div>", unsafe_allow_html=True)
                else: st.info("無近期賽事紀錄。")
                
                def style_advanced_data_cells(col_s):
                    styles = []
                    col_name = col_s.name
                    lower_better = ['Chase%', 'Whiff%', 'GB%', 'K%'] if p_type == '打者' else ['ERA', 'xERA', 'WHIP', 'FIP', 'BA', 'xBA', 'BB%', 'HardHit%', 'Barrel%', 'Diff']
                    elite_thresholds_h = {'wRC+': 130, 'OPS': 0.850, 'WAR': 4.0, 'HR': 30, 'Sprint': 29.0, 'HardHit%': 45.0, 'Barrel%': 12.0}
                    elite_thresholds_p = {'ERA': 3.00, 'WHIP': 1.10, 'K/9': 10.0, 'WAR': 3.5, 'K%': 28.0, 'xERA': 3.20}
                    thresholds = elite_thresholds_h if p_type == '打者' else elite_thresholds_p
                    
                    for val in col_s:
                        if pd.isna(val) or isinstance(val, str):
                            styles.append(f'color: {t_colors[0]} !important; font-weight: 900 !important; font-size: 1.1em !important;')
                            continue
                            
                        is_elite = False
                        if col_name in thresholds:
                            if col_name in lower_better: is_elite = val <= thresholds[col_name]
                            else: is_elite = val >= thresholds[col_name]
                            
                        if is_elite:
                            styles.append(f'color: white !important; font-weight: 900 !important; font-size: 1.1em !important; background-color: {t_colors[0]} !important; border-radius: 4px;')
                        else:
                            styles.append(f'color: {t_colors[0]} !important; font-weight: 900 !important; font-size: 1.1em !important;')
                    return styles

                st.markdown(f"<h4 style='color: {t_colors[0]};'>🔬 本季進階數據總覽</h4>", unsafe_allow_html=True)
                single_df = raw_data[raw_data['Player'] == target_profile].drop(columns=['Player_ID', 'Nickname', 'CYC', 'SLAM', 'Fantasy_Score', 'Fan_Pts', 'Avg_Pts'], errors='ignore')
                if 'E' in single_df.columns: single_df['E'] = pd.to_numeric(single_df['E'], errors='coerce').fillna(0).astype(int)

                styled_html_single = single_df.style\
                    .apply(style_advanced_data_cells, axis=0)\
                    .set_table_styles(custom_table_styles)\
                    .format(get_fmt_dict(single_df), na_rep="-").hide(axis='index').to_html()
                    
                st.markdown(f"<div class='table-scroll-container'>{styled_html_single}</div>", unsafe_allow_html=True)

                st.divider()
                
                def highlight_better(col_s):
                    styles = [''] * len(col_s)
                    if len(col_s) != 2: return styles
                    col_name = col_s.name
                    
                    if col_name in ['對戰手', '主客場', 'Split', 'Player', 'Team', 'Position']: return styles
                    
                    numeric_s = pd.to_numeric(col_s, errors='coerce')
                    if numeric_s.isna().any(): return styles
                    
                    v1, v2 = numeric_s.iloc[0], numeric_s.iloc[1]
                    if v1 == v2: return styles
                    
                    lower_better = ['Chase%', 'Whiff%', 'GB%', 'K%'] if p_type == '打者' else ['ERA', 'xERA', 'WHIP', 'FIP', 'AVG', 'OBP', 'SLG', 'OPS', 'BA', 'xBA', 'BB%', 'HardHit%', 'Barrel%', 'HR', 'R', 'ER']
                    is_lower = col_name in lower_better
                    idx = 0 if (v1 < v2 if is_lower else v1 > v2) else 1
                    
                    styles[idx] = f'color: white !important; background-color: {t_colors[0]} !important; font-weight: 900 !important; border-radius: 4px;'
                    return styles

                st.markdown(f"<h4 style='color: {t_colors[0]};'>⚔️ 左右對戰分歧 (Splits)</h4>", unsafe_allow_html=True)
                with st.spinner("獲取分歧數據..."):
                    split_df = fetch_savant_platoon_splits(int(p_prof['Player_ID']), p_type, year)
                    if split_df is not None and not split_df.empty:
                        if '對戰慣用手 (Split)' in split_df.columns:
                            split_df = split_df.rename(columns={'對戰慣用手 (Split)': '對戰手'})
                        elif 'Split' in split_df.columns:
                            split_df = split_df.rename(columns={'Split': '對戰手'})
                            
                        if '對戰手' in split_df.columns:
                            split_df['對戰手'] = split_df['對戰手'].replace({
                                'vs LHP': '左投', 'vs RHP': '右投',
                                'vs LHB': '左打', 'vs RHB': '右打',
                                'vs L': '左投/左打', 'vs R': '右投/右打'
                            })
                            
                        styled_html_split = split_df.style\
                            .apply(highlight_better, axis=0)\
                            .set_table_styles(custom_table_styles)\
                            .format(get_fmt_dict(split_df), na_rep='-').hide(axis='index').to_html()
                            
                        st.markdown(f"<div class='table-scroll-container'>{styled_html_split}</div>", unsafe_allow_html=True)
                    else: st.info("無對戰分歧資料。")

                st.divider()

                st.markdown(f"<h4 style='color: {t_colors[0]};'>🏟️ 主客場分歧 (Home/Away)</h4>", unsafe_allow_html=True)
                with st.spinner("獲取主客場數據..."):
                    ha_df = fetch_player_home_away_splits(int(p_prof['Player_ID']), p_type, year)
                    if ha_df is not None and not ha_df.empty:
                        if '主/客 (Home/Away)' in ha_df.columns:
                            ha_df = ha_df.rename(columns={'主/客 (Home/Away)': '主客場'})
                        elif 'Split' in ha_df.columns:
                            ha_df = ha_df.rename(columns={'Split': '主客場'})
                            
                        if '主客場' in ha_df.columns:
                            ha_df['主客場'] = ha_df['主客場'].replace({
                                'Home': '🏠 主場 (Home)', 'Away': '✈️ 客場 (Away)'
                            })
                            
                        styled_html_ha = ha_df.style\
                            .apply(highlight_better, axis=0)\
                            .set_table_styles(custom_table_styles)\
                            .format(get_fmt_dict(ha_df), na_rep='-').hide(axis='index').to_html()
                            
                        st.markdown(f"<div class='table-scroll-container'>{styled_html_ha}</div>", unsafe_allow_html=True)
                    else: st.info("無主客場資料。")

    if selected_search == "🏟️ 球隊戰情室":
        target_team = st.selectbox("🏟️ 選擇球隊", options=all_teams, index=None, placeholder="選擇球隊")
        if target_team:
            t_colors = get_team_color(target_team)
            
            # 🔥 共用名單強化引擎：用來抓取真實詳細的 Fantasy 位置與大聯盟醫療筆記
            def enrich_df_details(df, t_id, is_il=False):
                if df.empty: return df
                p_col = next((c for c in df.columns if '球員' in c and 'ID' not in c) or (c for c in df.columns if 'Player' in c), None)
                pos_col = next((c for c in df.columns if '位置' in c or 'Position' in c), None)
                inj_col = next((c for c in df.columns if '傷勢' in c or 'Injury' in c), None)
                
                if not p_col: return df

                pos_map = {}
                inj_map = {}
                for _, r in all_raw_combined.iterrows():
                    pn = r.get('Player')
                    if pd.isna(pn): continue
                    cn = norm_name(pn)
                    
                    p_val = str(r.get('Position', '')).strip()
                    if p_val and p_val != 'nan':
                        if cn in pos_map:
                            ex = [x.strip() for x in pos_map[cn].split(',')]
                            nw = [x.strip() for x in p_val.split(',')]
                            pos_map[cn] = ', '.join(list(dict.fromkeys(ex + nw)))
                        else: pos_map[cn] = p_val
                            
                    i_val = str(r.get('Injury', '')).strip()
                    if i_val and i_val not in ['nan', 'None']: inj_map[cn] = i_val

                api_inj_map = {}
                if is_il and t_id:
                    try:
                        end_date = datetime.now().strftime("%Y-%m-%d")
                        start_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
                        tx_url = f"https://statsapi.mlb.com/api/v1/transactions?teamId={t_id}&startDate={start_date}&endDate={end_date}"
                        tx_res = requests.get(tx_url, timeout=5).json()
                        for tx in tx_res.get('transactions', []):
                            desc = tx.get('description', '')
                            nm = norm_name(tx.get('person', {}).get('fullName', ''))
                            if nm and ('injured' in desc.lower() or 'il' in desc.lower() or 'placed' in desc.lower() or 'transferred' in desc.lower() or 'strain' in desc.lower() or 'sprain' in desc.lower() or 'surgery' in desc.lower()):
                                if nm not in api_inj_map or len(desc) > len(api_inj_map.get(nm, '')):
                                    api_inj_map[nm] = desc
                    except: pass

                for i, row in df.iterrows():
                    cn = norm_name(row[p_col])
                    if pos_col and cn in pos_map: df.at[i, pos_col] = pos_map[cn]
                    if inj_col:
                        best_inj = api_inj_map.get(cn, "")
                        if not best_inj: best_inj = inj_map.get(cn, "")
                        if best_inj: df.at[i, inj_col] = best_inj

                return df

            with st.spinner("抓取球隊戰報..."):
                matchup_df = fetch_team_recent_matchups(MLB_TEAM_IDS[target_team], today_str)
            
            res_col = next((c for c in matchup_df.columns if '勝負' in c or 'Result' in c), None)
            
            streak_html = ""
            if res_col and not matchup_df.empty:
                recent_5 = matchup_df[res_col].dropna().head(5).tolist()
                for res in recent_5:
                    res_char = str(res).strip().upper()[0] if str(res).strip() else ""
                    bg_color = "#00E676" if res_char == 'W' else ("#FF5252" if res_char == 'L' else "#9E9E9E")
                    streak_html += f"<span style='color: white; background-color: {bg_color}; padding: 4px 10px; border-radius: 6px; margin: 0 4px; font-size: 22px; font-weight: 900; box-shadow: 1px 1px 3px rgba(0,0,0,0.3);'>{res_char}</span>"
            
            recent_streak_display = f"<span style='margin-left: 30px; vertical-align: middle;'>{streak_html}</span>" if streak_html else ""
            
            team_logo_url = get_team_logo_url(target_team)
            t_logo_html = f"<img src='{team_logo_url}' width='90' style='vertical-align: middle; margin-right: 20px; filter: drop-shadow(2px 4px 6px rgba(0,0,0,0.2));'>" if team_logo_url else ""
            
            st.markdown(f"<div style='border-bottom: 5px solid {t_colors[0]}; padding-bottom: 20px; text-align: center; margin-bottom: 30px;'><span style='font-size: 55px; font-weight: 900; color: {t_colors[0]}; vertical-align: middle; text-shadow: 1px 2px 4px rgba(0,0,0,0.15);'>{t_logo_html}{target_team}</span>{recent_streak_display}</div>", unsafe_allow_html=True)
            
            standings_data = fetch_team_standings(year)
            team_record = standings_data.get(target_team, {})
            if team_record:
                win_pct_str = f"🏆 本季戰績：{team_record['W']}勝 {team_record['L']}敗 &nbsp;|&nbsp; 🏠 主場：{team_record['Home_W']}勝 {team_record['Home_L']}敗 &nbsp;|&nbsp; ✈️ 客場：{team_record['Away_W']}勝 {team_record['Away_L']}敗"
                st.markdown(f"<div style='text-align: center; margin-top: 10px; margin-bottom: 30px;'><span style='font-size: 22px; font-weight: 900; color: {t_colors[0]}; background-color: {hex_to_rgba(t_colors[0], 0.1)}; padding: 12px 30px; border-radius: 12px; border: 2px solid {t_colors[0]}'>{win_pct_str}</span></div>", unsafe_allow_html=True)
            
            team_table_styles = [{'selector': 'th', 'props': [('background-color', f'{t_colors[0]} !important'), ('color', 'white !important')]}]
            
            with st.spinner("調閱團隊攻防大數據..."):
                ts_df = fetch_all_teams_stats(year)
                if not ts_df.empty and target_team in ts_df['Team'].values:
                    if not raw_data_p.empty and 'HR' in raw_data_p.columns:
                        team_hr_allowed = raw_data_p.groupby('Team')['HR'].sum().reset_index()
                        team_hr_allowed.rename(columns={'HR': 'P_HR_Real'}, inplace=True)
                        ts_df = ts_df.merge(team_hr_allowed, on='Team', how='left')
                        ts_df['P_HR'] = ts_df['P_HR_Real'].fillna(0)
                        
                    for col, asc in [('H_OPS', False), ('H_HR', False), ('H_R', False), ('H_AVG', False), ('P_ERA', True), ('P_WHIP', True), ('P_K', False), ('P_HR', True)]:
                        if col in ts_df.columns: ts_df[f'{col}_Rank'] = ts_df[col].rank(ascending=asc, method='min')

                    ts = ts_df[ts_df['Team'] == target_team].iloc[0]
                    def team_metric_card(label, val_str, rank):
                        try:
                            rank_int = int(float(rank))
                            rank_str, rank_color = f"聯盟第 {rank_int} 名", "#00E676" if rank_int <= 15 else "#A9A9A9"
                        except:
                            rank_str, rank_color = "聯盟排名 --", "#A9A9A9"
                        return f'<div style="background-color: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 15px; border: 1px solid #e0e0e0; text-align: center;"><div style="font-size: 16px; color: #555; margin-bottom: 5px; font-weight: bold;">{label}</div><div style="font-size: 28px; font-weight: 900; color: {t_colors[0]};">{val_str}</div><div style="font-size: 14px; color: {rank_color}; font-weight: bold; margin-top: 5px;">{rank_str}</div></div>'
                    
                    c1, c2, c3, c4 = st.columns(4)
                    c1.markdown(team_metric_card("攻擊指數 (OPS)", f"{ts.get('H_OPS', 0):.3f}", ts.get('H_OPS_Rank', '--')), unsafe_allow_html=True)
                    c2.markdown(team_metric_card("團隊全壘打 (HR)", f"{int(ts.get('H_HR', 0))}", ts.get('H_HR_Rank', '--')), unsafe_allow_html=True)
                    c3.markdown(team_metric_card("總得分 (R)", f"{int(ts.get('H_R', 0))}", ts.get('H_R_Rank', '--')), unsafe_allow_html=True)
                    c4.markdown(team_metric_card("團隊打擊率 (AVG)", f"{ts.get('H_AVG', 0):.3f}", ts.get('H_AVG_Rank', '--')), unsafe_allow_html=True)

                    c5, c6, c7, c8 = st.columns(4)
                    c5.markdown(team_metric_card("團隊防禦率 (ERA)", f"{ts.get('P_ERA', 0):.2f}", ts.get('P_ERA_Rank', '--')), unsafe_allow_html=True)
                    c6.markdown(team_metric_card("被上壘率 (WHIP)", f"{ts.get('P_WHIP', 0):.2f}", ts.get('P_WHIP_Rank', '--')), unsafe_allow_html=True)
                    c7.markdown(team_metric_card("團隊三振數 (K)", f"{int(ts.get('P_K', 0))}", ts.get('P_K_Rank', '--')), unsafe_allow_html=True)
                    c8.markdown(team_metric_card("被全壘打數 (HR Allowed)", f"{int(ts.get('P_HR', 0))}", ts.get('P_HR_Rank', '--')), unsafe_allow_html=True)

            st.divider()
            
            st.markdown(f"<h4 style='color:{t_colors[0]}'>⚔️ 近期賽程與比分</h4>", unsafe_allow_html=True)
            if not matchup_df.empty:
                def style_team_matchups(row):
                    styles = [f'color: {t_colors[0]} !important; font-weight: 900 !important; font-size: 1.1em;'] * len(row)
                    for i, col in enumerate(row.index):
                        if 'Opponent' in col or '對手' in col:
                            opp_val = str(row[col])
                            opp_clean = re.sub(r'[^a-zA-Z\s]', '', opp_val).strip()
                            opp_color = get_team_color(opp_clean)[0]
                            styles[i] = f'color: {opp_color} !important; font-weight: 900 !important; font-size: 1.15em !important;'
                        
                        elif '勝負' in col or 'Result' in col:
                            val = str(row[col]).strip().upper()
                            if val.startswith('W'):
                                styles[i] = 'color: white !important; background-color: #00E676 !important; font-weight: 900 !important; border-radius: 4px; font-size: 1.1em;'
                            elif val.startswith('L'):
                                styles[i] = 'color: white !important; background-color: #FF5252 !important; font-weight: 900 !important; border-radius: 4px; font-size: 1.1em;'
                    return styles
                
                with pd.option_context("display.max_colwidth", None):
                    styled_html_matchups = matchup_df.style\
                        .apply(style_team_matchups, axis=1)\
                        .set_table_styles(team_table_styles)\
                        .hide(axis='index').to_html()
                    st.markdown(f"<div class='table-scroll-container'>{styled_html_matchups}</div>", unsafe_allow_html=True)
            else:
                st.info("無近期賽事紀錄。")

            st.divider()

            st.markdown(f"<h4 style='color:{t_colors[0]}'>📝 26 人服役名單 (Active Roster)</h4>", unsafe_allow_html=True)
            with st.spinner("抓取球隊名單..."):
                roster_df = fetch_team_roster(MLB_TEAM_IDS[target_team], year)
                if not roster_df.empty:
                    roster_df = roster_df.drop(columns=['球員ID'], errors='ignore')
                    
                    # 🔥 攔截器解鎖所有守位
                    roster_df = enrich_df_details(roster_df, MLB_TEAM_IDS[target_team], is_il=False)
                    
                    def style_roster(col):
                        return [f'color: {t_colors[0]} !important; font-weight: 900 !important; font-size: 1.05em; text-align: center;'] * len(col)
                    
                    with pd.option_context("display.max_colwidth", None):
                        styled_html_roster = roster_df.style\
                            .apply(style_roster, axis=0)\
                            .set_table_styles(team_table_styles)\
                            .hide(axis='index').to_html()
                        st.markdown(f"<div class='table-scroll-container'>{styled_html_roster}</div>", unsafe_allow_html=True)
            
            st.divider()
            
            # 🔥 目標 1: 解鎖無限制字數，強制文字換行顯示傷兵筆記
            st.markdown(f"<h4 style='color:#D32F2F'>🏥 傷兵名單 (IL)</h4>", unsafe_allow_html=True)
            with st.spinner("抓取傷兵報告..."):
                inj_df = fetch_team_injury_list(MLB_TEAM_IDS[target_team])
                if not inj_df.empty:
                    inj_df = inj_df.drop(columns=['球員ID'], errors='ignore')
                    
                    # 🔥 攔截器挖出真實醫療紀錄與所有守位
                    inj_df = enrich_df_details(inj_df, MLB_TEAM_IDS[target_team], is_il=True)
                    
                    def style_inj(col):
                        if any(k in str(col.name) for k in ['傷', 'Inj', 'Status', 'Note', '原因']):
                            return [f'color: {t_colors[0]} !important; font-weight: 900 !important; font-size: 1.05em; text-align: left !important; white-space: normal !important; min-width: 300px; line-height: 1.4; word-wrap: break-word;'] * len(col)
                        return [f'color: {t_colors[0]} !important; font-weight: 900 !important; font-size: 1.05em; text-align: center !important;'] * len(col)
                    
                    with pd.option_context("display.max_colwidth", None):
                        props_dict = {'white-space': 'normal', 'text-align': 'left', 'word-wrap': 'break-word'}
                        styled_html_inj = inj_df.style\
                            .apply(style_inj, axis=0)\
                            .set_properties(**props_dict)\
                            .set_table_styles(team_table_styles)\
                            .hide(axis='index').to_html()
                        st.markdown(f"<div class='table-scroll-container'>{styled_html_inj}</div>", unsafe_allow_html=True)
                else: st.info("目前無人傷停！")

    if selected_search == "🎭 外號同好會":
        target_nickname = st.selectbox(f"🎭 依 AI 判定外號篩選{p_type}", options=current_nicknames, index=None, placeholder="選擇外號類型", key="deep_search_nickname")
        if target_nickname:
            nk_data = raw_data_h[raw_data_h['Nickname'] == target_nickname].copy() if p_type == '打者' else raw_data_p[raw_data_p['Nickname'] == target_nickname].copy()
            if not nk_data.empty:
                nk_data.insert(0, 'Rank', range(1, len(nk_data) + 1))
                
                drop_targets = ['Player_ID', 'Nickname', 'CYC', 'SLAM', 'Fantasy_Score', 'Fan_Pts', 'Avg_Pts']
                nk_data = nk_data.drop(columns=[c for c in drop_targets if c in nk_data.columns], errors='ignore')
                
                if 'E' in nk_data.columns:
                    nk_data['E'] = pd.to_numeric(nk_data['E'], errors='coerce').fillna(0).astype(int)

                styled_html_nk = nk_data.style\
                    .apply(highlight_pr90, axis=0)\
                    .apply(color_rank_rows, axis=1)\
                    .format(get_fmt_dict(nk_data), na_rep="-").hide(axis='index').to_html()
                st.markdown(f"<div class='table-scroll-container'>{styled_html_nk}</div>", unsafe_allow_html=True)