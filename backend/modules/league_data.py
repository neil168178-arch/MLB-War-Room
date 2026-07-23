import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from streamlit_option_menu import option_menu

from backend.config import exclude_cols, STYLER_FORMATS, MLB_TEAM_IDS
from backend.utils import get_percentile, score_to_grade, style_grade, highlight_pr90, get_relative_grade, format_metric, get_team_color, hex_to_rgba
from backend.data_fetcher import fetch_recent_form_ranking, fetch_milb_stats
from backend.ui_utils import color_rank_rows
from backend.fantasy_logic import AL_TEAMS, NL_TEAMS, get_eligible_players

# 🔥 終極容錯機制：防止 API 欄位異常或空值，強制轉為浮點數
def get_val(row, keys, default):
    for k in keys:
        if k in row:
            try: 
                val_str = str(row[k]).strip()
                if val_str == '' or val_str.lower() == 'nan': continue
                return float(row[k])
            except: pass
    return default

def calculate_scout_grades(row, p_type, level_id):
    grades = {}
    is_aaa = (level_id == 11)
    if p_type == '打者':
        avg = get_val(row, ['AVG', 'avg', '打擊率 (AVG)'], 0.250)
        grades['Hit'] = 75 if avg >= 0.320 else 65 if avg >= 0.300 else 55 if avg >= 0.280 else 45 if avg >= 0.250 else 35

        ops = get_val(row, ['OPS', 'ops', '攻擊指數 (OPS)'], 0.700)
        grades['Power'] = 80 if ops >= 1.000 else 70 if ops >= 0.900 else 60 if ops >= 0.800 else 50 if ops >= 0.700 else 40

        sb = get_val(row, ['SB', 'sb', '盜壘 (SB)'], 0)
        grades['Run'] = 75 if sb >= 25 else 60 if sb >= 15 else 50 if sb >= 5 else 40

        obp = get_val(row, ['OBP', 'obp', '上壘率 (OBP)'], 0.320)
        grades['Discipline'] = 75 if obp >= 0.400 else 60 if obp >= 0.360 else 50 if obp >= 0.330 else 40
        
        fv = int((grades['Hit'] * 0.3 + grades['Power'] * 0.4 + grades['Run'] * 0.1 + grades['Discipline'] * 0.2) / 5) * 5
        grades['FV'] = int(min(80, max(20, fv + (5 if is_aaa else 0))))
    else:
        k9 = get_val(row, ['K/9', 'strikeoutsPer9Inn', '三振率 (K/9)'], 9.0)
        grades['Stuff'] = 80 if k9 >= 12.5 else 70 if k9 >= 11.0 else 60 if k9 >= 9.5 else 50 if k9 >= 8.0 else 40

        bb9 = get_val(row, ['BB/9', 'baseOnBallsPer9Inn', '保送率 (BB/9)'], 3.5)
        grades['Control'] = 75 if bb9 <= 1.8 else 65 if bb9 <= 2.5 else 50 if bb9 <= 3.5 else 40 if bb9 <= 4.5 else 30

        whip = get_val(row, ['WHIP', 'whip', '被上壘率 (WHIP)'], 1.30)
        grades['Command'] = 75 if whip <= 1.00 else 65 if whip <= 1.15 else 50 if whip <= 1.30 else 40

        fv = int((grades['Stuff'] * 0.5 + grades['Control'] * 0.3 + grades['Command'] * 0.2) / 5) * 5
        grades['FV'] = int(min(80, max(20, fv + (5 if is_aaa else 0))))
        
    return grades

def estimate_league_prospect(fv, level_id):
    is_aaa = (level_id == 11)
    if is_aaa:
        eta = "本季隨時" if fv >= 55 else "擴編期"
    else:
        eta = "明年春訓" if fv >= 60 else "季中升 3A"

    # 🔥 在聯盟數據裡，我們用「球探語言」代替 Fantasy 的「總管建議」
    if fv >= 60:
        evaluation = "🔥 頂級大物"
    elif fv >= 50:
        evaluation = "👀 值得期待"
    else:
        evaluation = "⏳ 農場培養"
        
    return eta, evaluation


def render_league_data(raw_data_h, raw_data_p, year):
    
    def get_fmt_dict(df):
        fmt = {}
        num_cols = df.select_dtypes(include=['number']).columns
        for c in df.columns:
            if c in STYLER_FORMATS:
                fmt[c] = STYLER_FORMATS[c]
            elif c in num_cols:
                fmt[c] = lambda x: f"{int(x)}" if pd.notna(x) and float(x).is_integer() else (f"{round(float(x), 3)}" if pd.notna(x) else "-")
        return fmt

    col_sort1, col_pos, col_sort2, col_sort3, col_sort4 = st.columns([1, 1, 1, 1, 1])
    
    with col_sort1:
        p_type = option_menu(
            None, ["打者", "投手"], icons=["person-arms-up", "bullseye"],
            default_index=0 if st.session_state.get('main_p_type', '打者') == '打者' else 1,
            orientation="vertical",
            key="league_p_type_menu",  # 👈 加入這行專屬身分證
            styles={
                "container": {"padding": "0!important", "margin": "0", "background-color": "#F0F2F6", "border-radius": "15px"},
                "nav-link": {"font-size": "14px", "padding": "5px"},
                "nav-link-selected": {"background-color": "#0C2340", "color": "white"}
            }
        )
    st.session_state.main_p_type = p_type
    
    raw_data = raw_data_h if p_type == "打者" else raw_data_p
    data = raw_data.copy()
        # 🔥 全域動態熱圖函式：為所有數據欄位自動產生高光
    def style_league_heatmap(s):
        styles = [''] * len(s)
        # 排除不需要算熱圖的文字或特定欄位
        if s.name in ['Player', 'Team', 'Position', 'Rank', 'Grade', 'Player_ID', 'Nickname']:
            return styles
        
        try:
            # 轉換為數字，排除非數值
            s_num = pd.to_numeric(s, errors='coerce').dropna()
            if s_num.empty: return styles
            
            # 定義反向指標 (越低越好)
            lower_is_better = ['ERA', 'xERA', 'WHIP', 'FIP', 'BA', 'xBA', 'BB%', 'HardHit%', 'Barrel%', 'Diff', 'L', 'BSV', 'E', 'WP', 'Chase%', 'Whiff%', 'GB%', 'K%']
            
            if s.name in lower_is_better:
                q_good = s_num.quantile(0.2)
                q_ok = s_num.quantile(0.5)
                q_bad = s_num.quantile(0.8)
                for i, val in enumerate(s):
                    try:
                        v = float(val)
                        if pd.isna(v) or (v == 0 and s.name in ['ERA', 'WHIP']): continue
                        if v <= q_good: styles[i] = 'color: #C62828 !important; background-color: #FFEBEE !important; font-weight: 900 !important;'
                        elif v <= q_ok: styles[i] = 'color: #E65100 !important; background-color: #FFF3E0 !important; font-weight: 900 !important;'
                        elif v >= q_bad: styles[i] = 'color: #1565C0 !important; background-color: #E3F2FD !important; font-weight: 900 !important;'
                    except: pass
            else:
                # 正常指標 (越高越好)
                q_good = s_num.quantile(0.8)
                q_ok = s_num.quantile(0.5)
                q_bad = s_num.quantile(0.2)
                for i, val in enumerate(s):
                    try:
                        v = float(val)
                        if pd.isna(v): continue
                        if v >= q_good: styles[i] = 'color: #C62828 !important; background-color: #FFEBEE !important; font-weight: 900 !important;'
                        elif v >= q_ok: styles[i] = 'color: #E65100 !important; background-color: #FFF3E0 !important; font-weight: 900 !important;'
                        elif v <= q_bad: styles[i] = 'color: #1565C0 !important; background-color: #E3F2FD !important; font-weight: 900 !important;'
                    except: pass
        except: pass
        return styles

    
    pos_options = ["全部 (ALL)", "DH", "C", "1B", "2B", "3B", "SS", "OF", "UTIL"] if p_type == '打者' else ["全部 (ALL)", "SP", "RP", "CL"]
    sel_pos = col_pos.selectbox("🛡️ 守備位置", pos_options, index=0, key="league_global_pos")
    if sel_pos != "全部 (ALL)":
        data = data[data['Player'].isin(get_eligible_players(sel_pos, raw_data_h, raw_data_p))]
    
    global_metrics = [c for c in raw_data.columns if c not in exclude_cols and c != 'Nickname']
    
    # ==========================================
    # 🔥 核心修正：Grade 綜合評分系統優化
    # 排除會互相傷害的計數型數據 (如 SV, QS)，只取純粹的「效率與進階實力指標」
    # ==========================================
    if p_type == '打者':
        core_metrics = ['OPS', 'wOBA', 'wRC+', 'xwOBA', 'xBA', 'HardHit%', 'Barrel%', 'WAR']
    else:
        # 投手只看防禦率、獨立防禦率、三振保送率、預期數據與 WAR，無視先發或後援身分
        core_metrics = ['ERA', 'WHIP', 'FIP', 'xERA', 'K%', 'BB%', 'BA', 'xBA', 'WAR']
        
    scout_metrics_l = [m for m in core_metrics if m in raw_data.columns]
    
    # 防呆機制：如果找不到上述指標，才退回原本的全抓邏輯
    if not scout_metrics_l:
        scout_metrics_l = [m for m in global_metrics if m not in ['CYC', 'SLAM', 'E', 'Fantasy_Score', 'Fan_Pts', 'Avg_Pts']]
    
    if not data.empty:
        data['綜合分數'] = [round(sum(get_relative_grade(data, m, row[m], p_type)[1] for m in scout_metrics_l)/max(1, len(scout_metrics_l)), 3) for _, row in data.iterrows()]
        data = data.sort_values(by='綜合分數', ascending=False).reset_index(drop=True)
        data.insert(0, 'Rank', data.index + 1)
        data.insert(1, 'Grade', data['綜合分數'].apply(score_to_grade))
        data = data.drop(columns=['綜合分數'])
        
    sortable_cols = [c for c in data.columns if c not in ['Player', 'Player_ID', 'Team', 'Position', 'Nickname', 'Rank', 'Grade', 'CYC', 'SLAM', 'Fantasy_Score', 'Fan_Pts', 'Avg_Pts']]
    sort_metric = col_sort2.selectbox("🔍 重新排序指標", sortable_cols, index=sortable_cols.index('WAR') if 'WAR' in sortable_cols else 0, key="league_sort_metric")
    lower_is_better = ['Chase%', 'Whiff%', 'GB%', 'K%'] if p_type == '打者' else ['ERA', 'xERA', 'WHIP', 'FIP', 'BA', 'xBA', 'BB%', 'HardHit%', 'Barrel%', 'Diff']
    
    sort_order = col_sort3.selectbox("排序方式", ["由高到低", "由低到高"], index=1 if sort_metric in lower_is_better else 0, key="league_sort_order")
    
    if p_type == '打者':
        min_filter = col_sort4.number_input("設定本季 PA (打席) 下限", min_value=0, value=30, step=10, key="league_min_pa")
        if 'PA' in data.columns: data = data[data['PA'] >= min_filter].copy()
    else:
        min_filter = col_sort4.number_input("設定本季 IP (局數) 下限", min_value=0.0, value=10.0, step=5.0, key="league_min_ip")
        if 'IP' in data.columns: data = data[data['IP'] >= min_filter].copy()

    # 📌 動態設定標籤列表 (打者沒有賽揚獎)
    league_options = ["📊 排名", "🔥 近況", "📈 雷達", "🌌 散佈", "⚖️ 對決", "👑 MVP", "🌱 MiLB 大物"] if p_type == "打者" else ["📊 排名", "🔥 近況", "📈 雷達", "🌌 散佈", "⚖️ 對決", "👑 MVP", "🏆 賽揚", "🌱 MiLB 大物"]
    
    selected_league = option_menu(
        menu_title=None, 
        options=league_options, # 👈 就是剛剛報錯找不到的變數，現在我們確定把它放在最前面了！
        default_index=0,
        orientation="horizontal",
        key="league_sub_menu",
        styles={
            "container": {"padding": "0!important", "max-width": "100%", "margin": "0 auto 20px auto", "background-color": "#F0F2F6", "border-radius": "15px", "display": "flex", "flex-wrap": "wrap"},
            "nav-link": {"font-size": "14px", "font-weight": "bold", "color": "#555", "margin": "2px"},
            "nav-link-selected": {"background-color": "#CE1141", "color": "white"}
        }
    )
    
    
   
    if selected_league == "📊 排名":       
        if not data.empty:
            sorted_data = data.sort_values(by=sort_metric, ascending=(sort_order == "由低到高")).reset_index(drop=True)
            sorted_data['Rank'] = sorted_data.index + 1
            
            drop_cols = ['Player_ID', 'Nickname', 'CYC', 'SLAM', 'Fantasy_Score', 'Fan_Pts', 'Avg_Pts']
            display_df = sorted_data.drop(columns=drop_cols, errors='ignore').copy()
            
            if 'E' in display_df.columns: display_df['E'] = pd.to_numeric(display_df['E'], errors='coerce').fillna(0).astype(int)
                
            styled_df = display_df.style\
                .map(style_grade, subset=['Grade'])\
                .apply(style_league_heatmap, axis=0)\
                .apply(color_rank_rows, axis=1)\
                .format(get_fmt_dict(display_df), na_rep="-")\
                .hide(axis='index')
            st.markdown(f"<div class='table-scroll-container rank-table-container'>{styled_df.to_html()}</div>", unsafe_allow_html=True)
        else: st.warning("目前無數據可顯示。")
        
    if selected_league == "🔥 近況":
        c_rf1, c_rf2 = st.columns(2)
        recent_min_filter = c_rf1.slider("設定近況最少打席/局數門檻", min_value=1.0, max_value=50.0, value=10.0 if p_type == '打者' else 3.0, step=1.0, key="league_recent_min")
        sel_recent_m = c_rf2.selectbox("📊 選擇近況排序指標", ['OPS', 'AVG', 'OBP', 'SLG', 'HR', 'RBI', 'PA'] if p_type == '打者' else ['ERA', 'WHIP', 'K', 'BB', 'SV', 'IP'], key="league_recent_metric")
        
        with st.spinner("全網大範圍撈取最新戰報中..."):
            recent_df = fetch_recent_form_ranking(p_type)
            if not recent_df.empty:
                if p_type == '打者': recent_df = recent_df[recent_df['PA'] >= recent_min_filter].copy()
                else: recent_df = recent_df[recent_df['IP_calc'] >= recent_min_filter].copy().drop(columns=['IP_calc'])
                recent_df['Position'] = recent_df['Player'].map(raw_data.set_index('Player')['Position'].to_dict()).fillna(recent_df['Position'])
                
                if sel_pos != "全部 (ALL)": 
                    recent_df = recent_df[recent_df['Player'].isin(get_eligible_players(sel_pos, raw_data_h, raw_data_p))]
                    
                if not recent_df.empty:
                    recent_df = recent_df.sort_values(by=sel_recent_m, ascending=False if p_type == '打者' else (True if sel_recent_m in ['ERA', 'WHIP', 'BB'] else False)).reset_index(drop=True)
                    recent_df.insert(0, 'Rank', recent_df.index + 1)
                    cols_r = list(recent_df.columns); cols_r.remove('Position'); cols_r.insert(2, 'Position'); recent_df = recent_df[cols_r]
                    
                    styled_recent = recent_df.style.apply(style_league_heatmap, axis=0).apply(color_rank_rows, axis=1).format(get_fmt_dict(recent_df), na_rep="-").hide(axis='index')
                    st.markdown(f"<div class='table-scroll-container rank-table-container'>{styled_recent.to_html()}</div>", unsafe_allow_html=True)
                else: st.warning("符合條件之近況數據不足。")
            else: st.warning("目前抓取不到符合條件的近況數據。")

    if selected_league == "📈 雷達":
        if not data.empty:
            col_t1, col_t2 = st.columns(2)
            target1_rad = col_t1.selectbox("雷達主要目標", data['Player'].unique(), index=0, key="league_rad_p1")
            target2_rad = col_t2.selectbox("雷達比較對象", data['Player'].unique(), index=1 if len(data['Player'].unique()) > 1 else 0, key="league_rad_p2")
            p1_rad, p2_rad = data[data['Player'] == target1_rad].iloc[0], data[data['Player'] == target2_rad].iloc[0]
            default_rad_metrics = global_metrics[:5]
            if 'WAR' in global_metrics and 'WAR' not in default_rad_metrics: default_rad_metrics[-1] = 'WAR'
            selected_metrics = st.multiselect("📊 選擇雷達圖與對比指標 (可多選)", global_metrics, default=default_rad_metrics, key="league_rad_metrics")
            
            if selected_metrics:
                plot_metrics = selected_metrics + [selected_metrics[0]]
                res1 = [get_percentile(data, m, p1_rad[m], p_type) for m in plot_metrics]
                res2 = [get_percentile(data, m, p2_rad[m], p_type) for m in plot_metrics]
                
                p1_color = get_team_color(p1_rad['Team'])[0]
                p2_color = get_team_color(p2_rad['Team'])[0]
                if p1_color == p2_color: p2_color = get_team_color(p2_rad['Team'])[1]
                
                fig = go.Figure()
                fig.add_trace(go.Scatterpolar(
                    r=res1, theta=plot_metrics, fill=None, mode='lines+markers', 
                    marker=dict(size=12, symbol='circle'), line_color=p1_color, name=target1_rad
                ))
                if target1_rad != target2_rad: 
                    fig.add_trace(go.Scatterpolar(
                        r=res2, theta=plot_metrics, fill=None, mode='lines+markers', 
                        marker=dict(size=12, symbol='circle'), line_color=p2_color, name=target2_rad
                    ))
                fig.update_layout(polar=dict(radialaxis=dict(range=[0, 100])), showlegend=True, height=600, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.markdown("<div style='display:flex; justify-content:center;'>", unsafe_allow_html=True)
                st.plotly_chart(fig, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
                
                comp_data = {
                    "指標 (Metrics)": selected_metrics,
                    f"{target1_rad} 數值": [format_metric(p1_rad[m], m) for m in selected_metrics],
                    f"{target1_rad} PR值": [f"PR {get_percentile(data, m, p1_rad[m], p_type):.0f}" for m in selected_metrics]
                }
                if target1_rad != target2_rad:
                    comp_data[f"{target2_rad} 數值"] = [format_metric(p2_rad[m], m) for m in selected_metrics]
                    comp_data[f"{target2_rad} PR值"] = [f"PR {get_percentile(data, m, p2_rad[m], p_type):.0f}" for m in selected_metrics]
                    
                    winners = []
                    for m in selected_metrics:
                        v1, v2 = p1_rad[m], p2_rad[m]
                        is_lower_better = m in (['Chase%', 'Whiff%', 'GB%', 'K%'] if p_type == '打者' else ['ERA', 'xERA', 'WHIP', 'FIP', 'BA', 'xBA', 'BB%', 'HardHit%', 'Barrel%', 'Diff'])
                        try:
                            if pd.isna(v1) or pd.isna(v2): winners.append("-")
                            else:
                                f1, f2 = float(v1), float(v2)
                                if f1 == f2: winners.append("平手")
                                elif is_lower_better: winners.append(f"🏆 {target1_rad}" if f1 < f2 else f"🏆 {target2_rad}")
                                else: winners.append(f"🏆 {target1_rad}" if f1 > f2 else f"🏆 {target2_rad}")
                        except:
                            winners.append("-")
                    comp_data["優勢 (Advantage)"] = winners
                    
                comp_df = pd.DataFrame(comp_data)
                
                def color_radar_rows(row):
                    styles = [''] * len(row)
                    styles[1] = f'color: {p1_color} !important; font-weight: 900 !important;'
                    styles[2] = f'color: {p1_color} !important; font-weight: 900 !important;'
                    if target1_rad != target2_rad:
                        styles[3] = f'color: {p2_color} !important; font-weight: 900 !important;'
                        styles[4] = f'color: {p2_color} !important; font-weight: 900 !important;'
                        
                        adv = str(row.iloc[5])
                        if target1_rad in adv:
                            styles[5] = f'color: white !important; background-color: {p1_color} !important; font-weight: 900 !important; border-radius: 4px;'
                        elif target2_rad in adv:
                            styles[5] = f'color: white !important; background-color: {p2_color} !important; font-weight: 900 !important; border-radius: 4px;'
                    return styles
                    
                st.markdown(f"#### 📊 {target1_rad} vs {target2_rad} 實際數據與勝負判定")
                html_str = comp_df.style.apply(color_radar_rows, axis=1).hide(axis='index').to_html()
                st.markdown(f"<div class='table-scroll-container'>{html_str}</div>", unsafe_allow_html=True)

    if selected_league == "🌌 散佈":
        if not data.empty:
            col_sx, col_sy = st.columns(2)
            plot_metrics = [c for c in data.columns if c not in ['Rank', 'Grade', 'Player', 'Player_ID', 'Team', 'Position', 'Nickname']]
            x_col = col_sx.selectbox("X 軸", plot_metrics, index=0, key="league_sct_x")
            y_col = col_sy.selectbox("Y 軸", plot_metrics, index=1 if len(plot_metrics)>1 else 0, key="league_sct_y")
            
            c_p1, c_p2 = st.columns(2)
            comp_p1 = c_p1.selectbox("🎯 標記比較球員 A (選填)", ["無"] + sorted(data['Player'].unique().tolist()), index=0, key="league_sct_p1")
            comp_p2 = c_p2.selectbox("🎯 標記比較球員 B (選填)", ["無"] + sorted(data['Player'].unique().tolist()), index=0, key="league_sct_p2")
            
            fig = px.scatter(data, x=x_col, y=y_col, color="Team", hover_name="Player", color_discrete_map={t: get_team_color(t)[0] for t in data['Team'].unique()})
            fig.update_traces(marker=dict(symbol='circle', size=9, opacity=0.65, line=dict(width=0)))
            
            if comp_p1 != "無" and not data[data['Player'] == comp_p1].empty:
                p1_dat = data[data['Player'] == comp_p1].iloc[0]
                tc1 = get_team_color(p1_dat['Team'])[0]
                fig.add_trace(go.Scatter(x=[p1_dat[x_col]], y=[p1_dat[y_col]], mode='markers+text',
                    marker=dict(symbol='star', size=26, color=tc1, line=dict(width=2, color='white')),
                    text=[f"⭐ {comp_p1}"], textposition="top center",
                    textfont=dict(size=18, color=tc1, weight="bold"), name=comp_p1))
                    
            if comp_p2 != "無" and not data[data['Player'] == comp_p2].empty:
                p2_dat = data[data['Player'] == comp_p2].iloc[0]
                tc2 = get_team_color(p2_dat['Team'])[0]
                fig.add_trace(go.Scatter(x=[p2_dat[x_col]], y=[p2_dat[y_col]], mode='markers+text',
                    marker=dict(symbol='star', size=26, color=tc2, line=dict(width=2, color='white')),
                    text=[f"⭐ {comp_p2}"], textposition="top center",
                    textfont=dict(size=18, color=tc2, weight="bold"), name=comp_p2))
                
            fig.update_layout(showlegend=False, height=650, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

    if selected_league == "⚖️ 對決":
        if not data.empty:
            col_h1, col_h2 = st.columns(2)
            h2h_t1 = col_h1.selectbox("對決目標 A", data['Player'].unique(), index=0, key="league_h2h_1")
            h2h_t2 = col_h2.selectbox("對決目標 B", data['Player'].unique(), index=1 if len(data['Player'].unique())>1 else 0, key="league_h2h_2")
            p1_h2h, p2_h2h = data[data['Player'] == h2h_t1].iloc[0], data[data['Player'] == h2h_t2].iloc[0]
            for m in global_metrics:
                col_m1, col_m2 = st.columns(2)
                v1, v2 = p1_h2h[m], p2_h2h[m]
                is_lower_better = m in (['Chase%', 'Whiff%', 'GB%', 'K%'] if p_type == '打者' else ['ERA', 'xERA', 'WHIP', 'FIP', 'BA', 'xBA', 'BB%', 'HardHit%', 'Barrel%', 'Diff'])
                c1, c2 = ("#00E676", "#A9A9A9") if (v1 < v2 if is_lower_better else v1 > v2) else ("#A9A9A9", "#00E676")
                
                col_m1.markdown(f"<div><b style='font-size: clamp(20px, 1.6vw, 28px);'>{h2h_t1} - {m}</b><br><span style='font-size: clamp(38px, 3.2vw, 54px); color:{c1}; font-weight:900;'>{format_metric(v1, m)}</span></div>", unsafe_allow_html=True)
                col_m2.markdown(f"<div><b style='font-size: clamp(20px, 1.vw, 28px);'>{h2h_t2} - {m}</b><br><span style='font-size: clamp(38px, 3.2vw, 54px); color:{c2}; font-weight:900;'>{format_metric(v2, m)}</span></div>", unsafe_allow_html=True)
                st.divider()

    if selected_league == "👑 MVP":
        sel_lg_mvp = st.radio("聯盟", ["美國聯盟 (AL)", "國家聯盟 (NL)"], horizontal=True, key="league_mvp_lg")
        mvp_df = data[data['Team'].isin(AL_TEAMS if sel_lg_mvp=="美國聯盟 (AL)" else NL_TEAMS)].copy()
        if not mvp_df.empty:
            if p_type == '打者': mvp_df['MVP_Index'] = (mvp_df['WAR']*20 + mvp_df.get('OPS', 0)*50 + mvp_df.get('wRC+', 0)*0.5).round(2)
            else: mvp_df['MVP_Index'] = (mvp_df['WAR']*25 + mvp_df.get('K%', 0)*1.5 - mvp_df.get('ERA', 0)*10).round(2)
            mvp_df = mvp_df.sort_values('MVP_Index', ascending=False).head(15).reset_index(drop=True); mvp_df.index += 1
            
            keep_cols = ['Player', 'Team', 'Position', 'WAR', 'OPS', 'wRC+', 'HR', 'MVP_Index'] if p_type == '打者' else ['Player', 'Team', 'Position', 'WAR', 'ERA', 'WHIP', 'K%', 'MVP_Index']
            keep_cols = [c for c in keep_cols if c in mvp_df.columns]
            # 🔥 將 highlight_pr90 替換為 style_league_heatmap，讓 MVP_Index 亮起來！
            styled_mvp = mvp_df[keep_cols].style.apply(style_league_heatmap, axis=0).apply(color_rank_rows, axis=1).format(get_fmt_dict(mvp_df), na_rep="-").hide(axis='index')
            st.markdown(f"<div class='table-scroll-container'>{styled_mvp.to_html()}</div>", unsafe_allow_html=True)
        else: st.info("無MVP榜單數據")

    elif selected_league == "🏆 賽揚":
            sel_lg_cy = st.radio("聯盟", ["美國聯盟 (AL)", "國家聯盟 (NL)"], horizontal=True, key="league_cy_lg")
            cy_df = data[data['Team'].isin(AL_TEAMS if sel_lg_cy=="美國聯盟 (AL)" else NL_TEAMS)].copy()
            if not cy_df.empty:
                cy_df['Cy_Index'] = (cy_df['WAR']*15 + cy_df.get('K%', 0)*1.2 - cy_df.get('ERA', 0)*8 - cy_df.get('WHIP', 0)*10).round(2)
                cy_df = cy_df.sort_values('Cy_Index', ascending=False).head(15).reset_index(drop=True); cy_df.index += 1
                
                keep_cols_cy = ['Player', 'Team', 'Position', 'WAR', 'ERA', 'WHIP', 'K%', 'IP', 'Cy_Index']
                keep_cols_cy = [c for c in keep_cols_cy if c in cy_df.columns]
                                # 🔥 賽揚獎指數 (Cy_Index) 也換上熱圖高光
                # 🔥 賽揚獎指數 (Cy_Index) 也換上熱圖高光
                styled_cy = cy_df[keep_cols_cy].style.apply(style_league_heatmap, axis=0).apply(color_rank_rows, axis=1).format(get_fmt_dict(cy_df), na_rep="-").hide(axis='index')
                st.markdown(f"<div class='table-scroll-container'>{styled_cy.to_html()}</div>", unsafe_allow_html=True)
            else: st.info("無賽揚榜單數據")

    # 🔥 全聯盟一般數據：🌱 MiLB 大物球探報告 (與 Fantasy 雷達共用高級渲染架構)
    elif selected_league == "🌱 MiLB 大物":
        st.markdown("### 🌟 聯盟天賦庫：MiLB 大物球探報告 ")
        st.caption("AI 球探系統自動掃描 3A 與 2A 數據，將表現轉換為 **20-80 球探評分制**，讓您輕鬆掌握全聯盟未來的基石！")
        
        c1, c2 = st.columns([1, 2])
        milb_level = c1.selectbox("選擇小聯盟層級", ["AAA", "AA"], key="league_milb_level")
        p_type_prospect = c2.radio("球員類型", ["打者", "投手"], horizontal=True, key="league_milb_ptype")

        lvl_map = {"AAA": 11, "AA": 12}
        level_id = lvl_map[milb_level]

        with st.spinner(f"正在連線全聯盟 {milb_level} 數據庫並執行 AI 球探分析..."):
            year = datetime.now().year
            milb_df = fetch_milb_stats(year, level_id, p_type_prospect)
            
            if milb_df is not None and not milb_df.empty:
                scout_data = []
                for _, row in milb_df.iterrows():
                    grades = calculate_scout_grades(row, p_type_prospect, milb_level)
                    eta, eval_text = estimate_league_prospect(grades['FV'], level_id)
                    
                    if grades['FV'] >= 50:
                        player_name = str(row.get('Player', row.get('球員 (Player)', row.get('球員', 'Unknown')))).strip()
                        team_name = str(row.get('Team', row.get('大聯盟母隊 (MLB Team)', row.get('球隊', 'Unknown')))).strip()
                        pos = str(row.get('Position', row.get('守位 (Pos)', row.get('位置', 'UNK')))).strip()
                        
                        if not pos or pos.lower() == 'nan': pos = 'UNK'
                        if not player_name or player_name.lower() == 'nan': player_name = 'Unknown'
                        if not team_name or team_name.lower() == 'nan': team_name = 'Unknown'

                        scout_info = {
                            "球員": player_name,
                            "所屬母隊": team_name,
                            "位置": pos, 
                            "球探評分 (FV)": grades['FV'],
                            "預計升上": eta,
                            "球探評價": eval_text
                        }
                        
                        if p_type_prospect == '打者':
                            scout_info.update({
                                "打擊(Hit)": int(grades['Hit']), "力量(Pow)": int(grades['Power']), 
                                "速度(Run)": int(grades['Run']), "選球(Eye)": int(grades['Discipline']), 
                                "OPS": get_val(row, ['OPS', '攻擊指數 (OPS)'], 0.0), 
                                "HR": int(get_val(row, ['HR', '全壘打 (HR)'], 0))
                            })
                        else:
                            scout_info.update({
                                "三振(Stuff)": int(grades['Stuff']), "控球(Ctrl)": int(grades['Control']), 
                                "壓制(Cmd)": int(grades['Command']), 
                                "ERA": get_val(row, ['ERA', '防禦率 (ERA)'], 0.0)
                            })
                            
                        scout_data.append(scout_info)
                
                if not scout_data:
                    st.warning("⚠️ 查無符合條件的高天賦潛力大物。")
                else:
                    prospect_df = pd.DataFrame(scout_data).sort_values(by="球探評分 (FV)", ascending=False).reset_index(drop=True)
                    prospect_df.index += 1
                    
                    st.markdown("##### 🔍 大物精準篩選")
                    f_col1, f_col2 = st.columns(2)
                    
                    eta_list = ["全部"] + list(prospect_df["預計升上"].unique())
                    eval_list = ["全部"] + list(prospect_df["球探評價"].unique())
                    
                    sel_eta = f_col1.selectbox("📅 過濾預計升上時間", eta_list, key="league_filter_eta")
                    sel_eval = f_col2.selectbox("🤖 過濾球探評價", eval_list, key="league_filter_eval")
                    
                    if sel_eta != "全部":
                        prospect_df = prospect_df[prospect_df["預計升上"] == sel_eta]
                    if sel_eval != "全部":
                        prospect_df = prospect_df[prospect_df["球探評價"] == sel_eval]
                        
                    if prospect_df.empty:
                        st.info("⚠️ 篩選後無符合條件的球員。")
                    else:
                        # 🔥 全聯盟專屬字體高光系統
                        def style_league_prospects(row):
                            try: tc = get_team_color(row['所屬母隊'])[0]
                            except: tc = "#555" 
                            
                            # 預設整列都是母隊主色
                            styles = [f'color: {tc} !important; font-weight: 900 !important;'] * len(row)
                            
                            for i, col in enumerate(row.index):
                                val = row[col]
                                
                                # FV / 球探評價 色塊標籤
                                if col == '球探評分 (FV)':
                                    if val >= 65: styles[i] = 'color: white !important; background-color: #D32F2F !important; font-weight: bold;'
                                    elif val >= 55: styles[i] = 'color: white !important; background-color: #FF9800 !important; font-weight: bold;'
                                    else: styles[i] = 'color: white !important; background-color: #2196F3 !important; font-weight: bold;'
                                elif col == '球探評價':
                                    if '🔥' in str(val): styles[i] = 'color: white !important; background-color: #D32F2F !important; font-weight: bold;'
                                    elif '👀' in str(val): styles[i] = 'color: white !important; background-color: #FF9800 !important; font-weight: bold;'
                                    elif '⏳' in str(val): styles[i] = 'color: white !important; background-color: #9E9E9E !important; font-weight: bold;'
                                
                                # 🔥 進階數據區：淡底色 + 飽和粗體字 (熱圖高光)
                                elif col in ['打擊(Hit)', '力量(Pow)', '速度(Run)', '選球(Eye)', '三振(Stuff)', '控球(Ctrl)', '壓制(Cmd)']:
                                    if val >= 60: styles[i] = 'color: #C62828 !important; background-color: #FFEBEE !important; font-weight: 900 !important;'
                                    elif val >= 50: styles[i] = 'color: #E65100 !important; background-color: #FFF3E0 !important; font-weight: 900 !important;'
                                    elif val <= 35: styles[i] = 'color: #1565C0 !important; background-color: #E3F2FD !important; font-weight: 900 !important;'
                                
                                elif col == 'OPS':
                                    if pd.notna(val):
                                        if val >= 0.900: styles[i] = 'color: #C62828 !important; background-color: #FFEBEE !important; font-weight: 900 !important;'
                                        elif val >= 0.800: styles[i] = 'color: #E65100 !important; background-color: #FFF3E0 !important; font-weight: 900 !important;'
                                        elif val <= 0.650: styles[i] = 'color: #1565C0 !important; background-color: #E3F2FD !important; font-weight: 900 !important;'
                                elif col == 'HR':
                                    if pd.notna(val):
                                        if val >= 20: styles[i] = 'color: #C62828 !important; background-color: #FFEBEE !important; font-weight: 900 !important;'
                                        elif val >= 10: styles[i] = 'color: #E65100 !important; background-color: #FFF3E0 !important; font-weight: 900 !important;'
                                elif col == 'ERA':
                                    if pd.notna(val) and val > 0: 
                                        if val <= 2.50: styles[i] = 'color: #C62828 !important; background-color: #FFEBEE !important; font-weight: 900 !important;'
                                        elif val <= 3.50: styles[i] = 'color: #E65100 !important; background-color: #FFF3E0 !important; font-weight: 900 !important;'
                                        elif val >= 5.00: styles[i] = 'color: #1565C0 !important; background-color: #E3F2FD !important; font-weight: 900 !important;'
                                        
                            return styles


                        st.markdown(f"#### 📋 聯盟 {milb_level} 頂級農場百大新秀名單")
                        
                        format_dict = {'OPS': '{:.3f}', 'HR': '{:.0f}'} if p_type_prospect == '打者' else {'ERA': '{:.2f}'}
                        
                        # 隱藏位置
                        display_df = prospect_df.drop(columns=['位置'])
                        
                        # 拆解 f-string 渲染
                        styled_prospect_df = display_df.style.apply(style_league_prospects, axis=1).format(format_dict).hide(axis='index')
                        html_str = styled_prospect_df.to_html(classes="league-prospect-table")
                        
                        # 🔥 內嵌 CSS 精準控制欄位寬度與滾動條
                        custom_css = """
                        <style>
                        .league-prospect-table { width: 100%; border-collapse: collapse; table-layout: auto; }
                        .league-prospect-table th, .league-prospect-table td { text-align: center; vertical-align: middle; padding: 6px; }
                        /* 球員欄縮小 */
                        .league-prospect-table td:nth-child(1), .league-prospect-table th:nth-child(1) { width: 100px !important; min-width: 100px !important; text-align: left; white-space: normal; word-wrap: break-word; }
                        /* 球探評價欄放大 */
                        .league-prospect-table td:nth-last-child(1), .league-prospect-table th:nth-last-child(1) { min-width: 160px !important; font-size: 1.1em; }
                        /* 固定表頭 */
                        .league-prospect-table thead th { position: sticky; top: 0; background-color: #f8f9fa; z-index: 10; box-shadow: 0 2px 2px -1px rgba(0, 0, 0, 0.4); }
                        </style>
                        """
                        # 📦 加上帶有滾動條的 div 容器
                        st.markdown(f"<div style='max-height: 450px; overflow-y: auto; border: 1px solid #e0e0e0; border-radius: 8px;'>{custom_css}{html_str}</div>", unsafe_allow_html=True)
                        
                        st.divider()
                        
                        st.markdown("### 🕷️ 大物專屬戰力體檢 (Scouting Radar)")
                        # 🔥 這裡加入了專屬的 KEY 解決報錯！
                        selected_prospect = st.selectbox("選擇球員查看雷達圖", prospect_df['球員'].tolist(), key="league_prospect_radar_select")
                        
                        if selected_prospect:
                            p_data = prospect_df[prospect_df['球員'] == selected_prospect].iloc[0]
                            
                            if p_type_prospect == '打者':
                                categories = ['打擊(Hit)', '力量(Pow)', '速度(Run)', '選球(Eye)']
                                vals = [p_data['打擊(Hit)'], p_data['力量(Pow)'], p_data['速度(Run)'], p_data['選球(Eye)'] ]
                            else:
                                categories = ['三振(Stuff)', '控球(Ctrl)', '壓制(Cmd)']
                                vals = [p_data['三振(Stuff)'], p_data['控球(Ctrl)'], p_data['壓制(Cmd)'] ]
                                
                            try: radar_color = get_team_color(p_data['所屬母隊'])[0]
                            except: radar_color = "#2196F3"
                            
                            c_radar, c_info = st.columns([1, 1])
                            
                            fig = go.Figure(go.Scatterpolar(
                                r=vals + [vals[0]],
                                theta=categories + [categories[0]],
                                fill='toself', line_color=radar_color, fillcolor=hex_to_rgba(radar_color, 0.4)
                            ))
                            fig.update_layout(polar=dict(radialaxis=dict(range=[20, 80], tickfont=dict(size=12))), height=350, margin=dict(l=40, r=40, t=30, b=30))
                            c_radar.plotly_chart(fig, use_container_width=True)
                            
                            with c_info:
                                st.markdown(f"<h3 style='color: {radar_color}; margin-bottom: 0;'>{selected_prospect}</h3>", unsafe_allow_html=True)
                                
                                # 隱藏未知的守位
                                pos_display = p_data['位置']
                                pos_text = f" | **位置：** {pos_display}" if pos_display not in ['UNK', 'Unknown', '-', 'nan', ''] else ""
                                st.markdown(f"**所屬球隊：** {p_data['所屬母隊']} ({milb_level}){pos_text}")
                                
                                st.markdown(f"**球探評分 (FV)：** <span style='font-size: 24px; font-weight: 900; color: {radar_color};'>{p_data['球探評分 (FV)']}</span>", unsafe_allow_html=True)
                                
                                st.markdown(f"""
                                <div style="background-color: #f8f9fa; padding: 15px; border-left: 5px solid {radar_color}; border-radius: 5px; margin-top: 15px;">
                                    <b>🚀 預計升上：</b> {p_data['預計升上']}<br><br>
                                    <b>🤖 球探評價：</b> {p_data['球探評價']}<br>
                                    <i>該球員目前在小聯盟展現出 {p_data['球探評分 (FV)']} 分等級的未來價值 (Future Value)，是值得各隊關注的農場潛力股！</i>
                                </div>
                                """, unsafe_allow_html=True)
            else:
                st.warning(f"⚠️ 無法取得 {year} 賽季 {milb_level} 的資料，請稍後再試。")
