import streamlit as st
import pandas as pd
import requests
import random
import hashlib
import plotly.graph_objects as go
from datetime import datetime, timedelta
from streamlit_option_menu import option_menu

from backend.config import STYLER_FORMATS
from backend.utils import f_size, get_team_color, highlight_pr90, hex_to_rgba
from backend.data_fetcher import fetch_weekly_fantasy_ranking, fetch_recent_form_ranking, fetch_milb_stats
from backend.ui_utils import color_rank_rows
from backend.fantasy_logic import ALL_HITTER_CATS, ALL_PITCHER_CATS, FANTASY_WEIGHTS, HARDCORE_WEIGHTS, save_db, get_eligible_players, recalculate_custom_score, AL_TEAMS, NL_TEAMS

def extract_game_col(df):
    for col in ['G', 'GP', 'Games', 'gamesPlayed', 'game']:
        if col in df.columns: return pd.to_numeric(df[col], errors='coerce').fillna(1).astype(int)
    return pd.Series(1, index=df.index).astype(int)

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

def calculate_scout_grades(row, p_type, level):
    grades = {}
    is_aaa = (level == 'AAA')
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

def estimate_fantasy_stash(fv, level):
    if level == 'AAA':
        eta = "本季隨時" if fv >= 55 else "擴編期"
    else:
        eta = "明年春訓" if fv >= 60 else "季中升 3A"

    if fv >= 60:
        stash = "🔥 放進名單"
    elif fv >= 50:
        stash = "👀 密切關注"
    else:
        stash = "⏳ 暫不需理會"
        
    return eta, stash
# ==========================================
# 🧠 專家系統：模組 1 & 2 核心引擎
# ==========================================
def analyze_batter_luck(row):
    # 強制轉浮點數，並給予預設值防呆
    ba = pd.to_numeric(row.get('BA', row.get('AVG', 0.250)), errors='coerce')
    xba = pd.to_numeric(row.get('xBA', ba), errors='coerce')
    babip = pd.to_numeric(row.get('BABIP', 0.300), errors='coerce')
    chase = pd.to_numeric(row.get('Chase%', 28.0), errors='coerce')
    
    luck_score = 0
    messages = []
    
    # 核心邏輯 1：預期打擊率 vs 實際打擊率
    if pd.notna(xba) and pd.notna(ba):
        if ba - xba > 0.040:
            luck_score -= 2
            messages.append("🚨 <b style='color:#D32F2F;'>假性高潮</b>：實際打擊率遠高於 xBA，近期的安打有極高比例是運氣(Lucky Hits)。")
        elif xba - ba > 0.030:
            luck_score += 2
            messages.append("🔥 <b style='color:#388E3C;'>擊球極佳</b>：預期打擊率(xBA)遠高於實際，強勁擊球常被沒收，強烈建議逢低買進！")
            
    # 核心邏輯 2：BABIP (場內安打率)
    if pd.notna(babip) and babip > 0.350:
        luck_score -= 1
        messages.append("⚠️ <b style='color:#F57C00;'>BABIP過高</b>：場內安打率不尋常偏高，必然面臨校正下修。")
        
    # 核心邏輯 3：揮擊決策 (Chase%)
    if pd.notna(chase):
        if chase < 25.0:
            luck_score += 1
            messages.append("🟢 <b style='color:#388E3C;'>選球眼極佳</b>：追打壞球率極低，打擊本質非常健康。")
        elif chase > 35.0:
            luck_score -= 1
            messages.append("🔴 <b style='color:#D32F2F;'>盲劍客危機</b>：揮擊決策差(Chase%過高)，一旦手感冷卻將陷入大低潮。")
            
    # 綜合診斷判定
    if luck_score >= 2: return "🚀 逢低買進 (Buy Low)", "<br>".join(messages)
    elif luck_score <= -2: return "📉 逢高賣出 (Sell High)", "<br>".join(messages)
    else: return "⚖️ 實力相符 (Hold)", "目前數據反應真實實力，無明顯運氣成分干擾。<br>" + ("<br>".join(messages) if messages else "")

def analyze_pitcher_risk(row):
    era = pd.to_numeric(row.get('ERA', 4.00), errors='coerce')
    xera = pd.to_numeric(row.get('xERA', row.get('FIP', era)), errors='coerce')
    k_pct = pd.to_numeric(row.get('K%', 22.0), errors='coerce')
    ip = pd.to_numeric(row.get('IP', 0), errors='coerce')
    g = pd.to_numeric(row.get('G', 1), errors='coerce')
    
    risk_score = 0
    messages = []
    
    # 核心邏輯 1：預期防禦率 vs 實際防禦率
    if pd.notna(xera) and pd.notna(era):
        if xera - era > 1.0:
            risk_score += 2
            messages.append("🚨 <b style='color:#D32F2F;'>運氣過佳</b>：預期防禦率(xERA)遠高於實際ERA，隨時可能校正回歸(爆炸)。")
        elif era - xera > 0.5:
            risk_score -= 1
            messages.append("🟢 <b style='color:#388E3C;'>運氣不佳</b>：被安打多為不營養擊球，未來防禦率有望反彈下降。")
            
    # 核心邏輯 2：三振壓制力
    if pd.notna(k_pct) and k_pct < 20.0:
        risk_score += 1
        messages.append("⚠️ <b style='color:#F57C00;'>三振能力下滑</b>：K% 低於聯盟平均，極度依賴守備，壓制力堪憂。")
        
    # 核心邏輯 3：過勞警示 (以均局數與出賽頻率粗估)
    if g > 0 and (ip / g) > 6.2 and ip > 50:
        risk_score += 1
        messages.append("⚠️ <b style='color:#D32F2F;'>手臂疲勞警告</b>：近期吃下大量局數，須留意球速(Velocity)下滑與受傷風險。")
        
    # 綜合診斷判定
    if risk_score >= 2: return "🔴 高度風險 (Sell/Bench)", "<br>".join(messages)
    elif risk_score == 1: return "🟡 觀察警示 (Hold)", "<br>".join(messages)
    else: return "🟢 狀態穩定 (Safe/Buy)", "進階指標健康，未見明顯衰退風險。<br>" + ("<br>".join(messages) if messages else "")
# ==========================================

def render_fantasy_team(raw_data_h, raw_data_p, all_players, today_str):
    # ==========================================
    # 🔥 總管全域時空防呆：為所有分頁預先定義 target_date_str
    # ==========================================
    from datetime import datetime, timedelta
    tw_now = datetime.utcnow() + timedelta(hours=8)
    try:
        # 如果超過 18:00 預設給明天，否則給今天
        if tw_now.hour >= 18:
            target_date_str = (datetime.strptime(today_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            target_date_str = today_str
    except:
        target_date_str = today_str
    # ==========================================
    raw_data_h = raw_data_h.copy()
    raw_data_p = raw_data_p.copy()
    all_players = list(all_players)
    
    ohtani_names = ['Shohei Ohtani', '大谷翔平']
    for name in ohtani_names:
        # 拆分打者
        if name in raw_data_h['Player'].values:
            raw_data_h.loc[raw_data_h['Player'] == name, 'Player'] = f"{name} (Batter)"
            if name in all_players: all_players.remove(name)
            if f"{name} (Batter)" not in all_players: all_players.append(f"{name} (Batter)")
                
        # 拆分投手
        if name in raw_data_p['Player'].values:
            raw_data_p.loc[raw_data_p['Player'] == name, 'Player'] = f"{name} (Pitcher)"
            if f"{name} (Pitcher)" not in all_players: all_players.append(f"{name} (Pitcher)")
                
        # 自動修復資料庫中舊版大谷的名字 (防呆機制)
        if 'fantasy_db' in st.session_state:
            for lg, lg_data in st.session_state.fantasy_db.items():
        
        # 🔥 資料型態防護罩：如果抓出來的不是字典 (代表它是傷兵清單或設定檔)，就直接跳過不處理！
                if not isinstance(lg_data, dict):
                    continue
            
                for tm, tm_data in lg_data.items():
                        for date, roster in tm_data.get('roster', {}).items():
                            for slot, p_name in roster.items():
                                if p_name == name:
                                    roster[slot] = f"{name} (Pitcher)" if any(ps in slot for ps in ['SP', 'RP', 'P']) else f"{name} (Batter)"
            
            if name in st.session_state.fantasy_db.get('external_taken', []):
                st.session_state.fantasy_db['external_taken'].remove(name)
                st.session_state.fantasy_db['external_taken'].extend([f"{name} (Batter)", f"{name} (Pitcher)"])
            if name in st.session_state.fantasy_db.get('real_il_players', []):
                st.session_state.fantasy_db['real_il_players'].remove(name)
                st.session_state.fantasy_db['real_il_players'].extend([f"{name} (Batter)", f"{name} (Pitcher)"])
    
                
   # ==========================================
    # 🔥 終極升級：MLB 官方醫療直升機 (直接呼叫 MLB Stats API 抓取真實 IL 名單)
    # ==========================================
    @st.cache_data(ttl=3600)  # 快取 1 小時，避免頻繁呼叫被封鎖
    def fetch_mlb_official_il():
        il_players = set()
        try:
            # 呼叫 MLB 官方的 transactions API 抓取近 10 天放入 IL 的名單，或者直接查 injury status
            # 為了穩定，我們抓取當前賽季所有有 injury status 的球員 (sportId=1 是 MLB)
            url = "https://statsapi.mlb.com/api/v1/sports/1/players?season=2024" # 請確保賽季年份正確
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                for player in data.get('people', []):
                    # 檢查球員狀態是否為傷兵相關 (通常 IL10, IL15, IL60 或是 status="Injured")
                    status_code = player.get('primaryPosition', {}).get('abbreviation', '') # 有時放這裡
                    active_status = player.get('active', True)
                    # 官方 API 的傷兵狀態通常藏在 player_status，這裡我們用一個廣泛的攔截
                    if not active_status or player.get('injuryStatus', '') or 'IL' in str(player):
                        # 如果需要更精準，必須呼叫 team roster API 檢查 status，這裡提供簡單防呆
                        # 為了確保抓到，最穩定的方式是去撈 MLB 的傷病報告網頁或專用 API
                        pass
        except Exception as e:
            st.warning(f"⚠️ MLB 官方醫療雷達連線異常: {e}")
            
        return il_players

    # 🚨 注意：由於 Streamlit Cloud 有時會擋外部 HTTP，我們改用一個更聰明且輕量的做法
    # 從 CBS Sports 或是 ESPN 的公開 RSS/JSON 抓，但最穩定的其實是用 `pybaseball.standings` 或相關套件
    # 這裡我們實作一個最穩定的「動態網路爬蟲」機制，透過 pandas read_html 抓取公開傷兵網頁！
    @st.cache_data(ttl=3600)
    def scrape_real_il_from_web():
        il_set = set()
        try:
            # 直接讀取 CBS Sports 的大聯盟傷兵名單表格
            url = "https://www.cbssports.com/mlb/injuries/"
            tables = pd.read_html(url)
            for tb in tables:
                if 'Player' in tb.columns:
                    # 1. 拔除守位與球隊縮寫
                    names = tb['Player'].astype(str).str.replace(r'\s+([A-Z]{2,4}|[1-3]B|SS|OF|DH|C|SP|RP|CL)$', '', regex=True)
                
                    # 🔥 2. 終極解黏 V3：嚴格鎖定「大寫字母+點+空白」開頭，狙擊並消除重複的姓氏殘影！
                    names = names.str.replace(r'^(?:[A-Z]\.)+\s+(.+?)(?=[A-Z].*\1$)', '', regex=True)
                    # 把抓到的名字轉換成 set 方便比對
                    il_set.update(names.tolist())
        except Exception as e:
            # 如果爬蟲失敗，安靜地回傳空集合，不干擾畫面
            pass
        return il_set

    # 啟動爬蟲雷達
    auto_il_players = scrape_real_il_from_web()
    
   # 🔥 總管最高裁決：將「系統自動抓取」扣除「總管指定的誤判名單」後，再與「手動補充」合併！
    false_il_players = set(st.session_state.get('fantasy_db', {}).get('false_il_players', []))
    combined_il_players = (auto_il_players - false_il_players).union(set(st.session_state.get('fantasy_db', {}).get('real_il_players', [])))
    # ==========================================
    def get_fmt_dict(df):
        fmt = {}
        num_cols = df.select_dtypes(include=['number']).columns
        for c in df.columns:
            if c in STYLER_FORMATS:
                fmt[c] = STYLER_FORMATS[c]
            elif c in num_cols:
                fmt[c] = lambda x: f"{int(x)}" if pd.notna(x) and float(x).is_integer() else (f"{round(float(x), 3)}" if pd.notna(x) else "-")
        return fmt

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
    raw_data = raw_data_h if p_type == '打者' else raw_data_p

    # 🔥 全域動態熱圖函式：為所有數據欄位自動產生高光
    def style_fantasy_pts(s):
        styles = [''] * len(s)
        # 排除不需要算熱圖的文字或特定欄位
        if s.name in ['Player', 'Team', 'Position', 'Rank', 'Slot (指派位置)', 'Game', '預計出賽(G)', '對手難易度', '血性優勢']:
            return styles
        
        try:
            s_num = pd.to_numeric(s, errors='coerce').dropna()
            if s_num.empty: return styles
            
            # 🎯 針對 Score 欄位獨立設定：高飽和度搶眼背景色 + 純黑粗體字
            if s.name == 'Score':
                q_good = s_num.quantile(0.8)
                q_ok = s_num.quantile(0.5)
                q_bad = s_num.quantile(0.2)
                for i, val in enumerate(s):
                    try:
                        v = float(val)
                        if pd.isna(v): continue
                        # 搶眼火紅 / 亮眼金黃 / 醒目天藍 (字體統一用純黑確保最高對比度)
                        if v >= q_good: styles[i] = 'color: #000000 !important; background-color: #FF8A80 !important; font-weight: 900 !important;'
                        elif v >= q_ok: styles[i] = 'color: #000000 !important; background-color: #FFD54F !important; font-weight: 900 !important;'
                        elif v <= q_bad: styles[i] = 'color: #000000 !important; background-color: #81D4FA !important; font-weight: 900 !important;'
                    except: pass
                return styles


            # 📊 其他數據維持原本的「飽和字體色 + 背景色」
            lower_is_better = ['ERA', 'WHIP', 'L', 'BSV', 'E', 'WP']
            
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
        
    

    def calc_z_scores_for_roster(player_names):
        df_h = raw_data_h[raw_data_h['Player'].isin(player_names)]
        df_p = raw_data_p[raw_data_p['Player'].isin(player_names)]
        
        z = {}
        eps = 1e-6 # 防止分母為 0 的安全係數
        
        # ==========================================
        # 🏏 打者部門：以全聯盟歷史/本季總資料庫為母體基準
        # ==========================================
        if not df_h.empty:
            # 轉換為浮點數並防呆
            for col in ['HR', 'SB', 'OPS', 'R', 'RBI']:
                raw_data_h[col] = pd.to_numeric(raw_data_h[col], errors='coerce').fillna(0)
                df_h[col] = pd.to_numeric(df_h[col], errors='coerce').fillna(0)
            
            # 1. 全壘打 (HR)
            z_hr = (df_h['HR'].mean() - raw_data_h['HR'].mean()) / (raw_data_h['HR'].std() + eps)
            z['HR (全壘打)'] = 60 + (z_hr * 15)
            
            # 2. 盜壘 (SB)
            z_sb = (df_h['SB'].mean() - raw_data_h['SB'].mean()) / (raw_data_h['SB'].std() + eps)
            z['SB (盜壘)'] = 60 + (z_sb * 15)
            
            # 3. 整體攻擊指數 (OPS)
            z_ops = (df_h['OPS'].mean() - raw_data_h['OPS'].mean()) / (raw_data_h['OPS'].std() + eps)
            z['OPS (攻擊)'] = 60 + (z_ops * 15)
            
            # 4. 產出能力 (R + RBI 聯合評估)
            league_r_rbi = raw_data_h['R'] + raw_data_h['RBI']
            team_r_rbi = df_h['R'] + df_h['RBI']
            z_r_rbi = (team_r_rbi.mean() - league_r_rbi.mean()) / (league_r_rbi.std() + eps)
            z['R+RBI (產出)'] = 60 + (z_r_rbi * 15)
        else:
            z['HR (全壘打)'] = z['SB (盜壘)'] = z['OPS (攻擊)'] = z['R+RBI (產出)'] = 50

        # ==========================================
        # 🎯 投手部門：以全聯盟歷史/本季總資料庫為母體基準
        # ==========================================
        if not df_p.empty:
            for col in ['K', 'SV', 'HLD', 'ERA', 'WHIP']:
                raw_data_p[col] = pd.to_numeric(raw_data_p[col], errors='coerce').fillna(0 if col not in ['ERA', 'WHIP'] else 4.0)
                df_p[col] = pd.to_numeric(df_p[col], errors='coerce').fillna(0 if col not in ['ERA', 'WHIP'] else 4.0)
            
            # 1. 三振壓制 (K)
            z_k = (df_p['K'].mean() - raw_data_p['K'].mean()) / (raw_data_p['K'].std() + eps)
            z['K (三振)'] = 60 + (z_k * 15)
            
            # 2. 牛棚戰力 (SV + HLD 聯合評估)
            league_sv_hld = raw_data_p['SV'] + raw_data_p['HLD']
            team_sv_hld = df_p['SV'] + df_p['HLD']
            z_sv_hld = (team_sv_hld.mean() - league_sv_hld.mean()) / (league_sv_hld.std() + eps)
            z['SV+HLD (牛棚)'] = 60 + (z_sv_hld * 15)
            
            # 3. 壓制率 (ERA + WHIP 聯合評估，注意：低於聯盟平均才是優勢，因此取負號)
            z_era = (df_p['ERA'].mean() - raw_data_p['ERA'].mean()) / (raw_data_p['ERA'].std() + eps)
            z_whip = (df_p['WHIP'].mean() - raw_data_p['WHIP'].mean()) / (raw_data_p['WHIP'].std() + eps)
            z_pitch_control = -((z_era + z_whip) / 2.0) # 負負得正
            z['ERA+WHIP (壓制)'] = 60 + (z_pitch_control * 15)
        else:
            z['K (三振)'] = z['SV+HLD (牛棚)'] = z['ERA+WHIP (壓制)'] = 50
            
        # 🔥 總管指定：終極 Capping 天花板防線 (鎖死在 15 ~ 95 分之間，絕對不爆表)
        return {k: max(15, min(95, round(v, 1))) for k, v in z.items()}
    selected_fantasy = option_menu(
        None, 
        options=["🔥 近七日狀態", "📊 本季數據", "📝 夢幻球隊", "🛒 自由市場", "⚖️ 雙星對決", "🤝 交易模擬器", "🌟 大物雷達", "🧠 專家預警"],
        default_index=0,
        orientation="horizontal",
        key="fantasy_type_menu",
        styles={
            "container": {"padding": "0!important", "max-width": "100%", "margin": "0 auto 20px auto", "background-color": "#F0F2F6", "border-radius": "15px", "display": "flex", "flex-wrap": "wrap"},
            "nav-link": {"font-size": "14px", "font-weight": "bold", "color": "#555", "margin": "2px"},
            "nav-link-selected": {"background-color": "#E81828", "color": "white"} # 費城人紅
        }
    )

    if selected_fantasy == "🔥 近七日狀態":
        st.caption("透過官方 API 直接抓取近七日累積數據，精算近期火力與狀態！")
        with st.spinner("精算 Fantasy 積分中..."):
            weekly_df = fetch_weekly_fantasy_ranking(p_type)
            if not weekly_df.empty:
                for name in ['Shohei Ohtani', '大谷翔平']:
                    mask = weekly_df['Player'] == name
                    if mask.any(): weekly_df.loc[mask, 'Player'] = f"{name} ({'Batter' if p_type == '打者' else 'Pitcher'})"
                weekly_df['Position'] = weekly_df['Player'].map(raw_data.set_index('Player')['Position'].to_dict()).fillna(weekly_df['Position'])
                col_w1, col_w2, col_w3 = st.columns([1, 1, 1])
                
                sel_week_pos = col_w1.selectbox("🛡️ 篩選本週守備位置", ["全部 (ALL)", "DH", "C", "1B", "2B", "3B", "SS", "LF", "CF", "RF"] if p_type == '打者' else ["全部 (ALL)", "SP", "RP", "CL"], index=0, key="fan_week_pos")
                sort_options = ["Fan_Pts", "Avg_Pts"] if "Avg_Pts" in weekly_df.columns else ["Fan_Pts"]
                sort_week_metric = col_w2.selectbox("📊 選擇排序指標", sort_options, index=0, key="fan_week_metric")
                sort_week_order = col_w3.selectbox("排序方式", ["由高到低", "由低到高"], index=0, key="fan_week_order")
                
                if sel_week_pos != "全部 (ALL)": 
                    weekly_df = weekly_df[weekly_df['Position'].astype(str).apply(lambda x: sel_week_pos in [p.strip() for p in x.split(',')])]
                weekly_df = weekly_df.sort_values(by=sort_week_metric, ascending=(sort_week_order == "由低到高")).reset_index(drop=True)
                weekly_df.insert(0, 'Rank', weekly_df.index + 1)
                
                cols_w = list(weekly_df.columns)
                if 'Position' in cols_w and 'Position' != cols_w[3]:
                    cols_w.remove('Position')
                    cols_w.insert(3, 'Position')
                    weekly_df = weekly_df[cols_w]
                
                drop_keywords = ['nickname', 'slam', 'cyc']
                cols_to_drop = [c for c in weekly_df.columns if any(k in c.lower() for k in drop_keywords)]
                display_df = weekly_df.drop(columns=cols_to_drop)
                
                styled_weekly = display_df.style.apply(style_fantasy_pts, axis=0)\
                                                .apply(color_rank_rows, axis=1)\
                                                .format(get_fmt_dict(display_df), na_rep="-").hide(axis='index')
                st.markdown(f"<div class='table-scroll-container rank-table-container'>{styled_weekly.to_html()}</div>", unsafe_allow_html=True)
            else: st.warning("⚠️ 查無近七日比賽資料。")
            
    if selected_fantasy == "📊 本季數據":
        st.caption("完整提取夢幻棒球常用的累積計分項目！")
        
        col_f1, col_f2, col_f3, col_f4 = st.columns([1, 1, 1, 1])
        
        sel_fantasy_pos = col_f1.selectbox("🛡️ 篩選守備位置 (Season)", ["全部 (ALL)", "DH", "C", "1B", "2B", "3B", "SS", "LF", "CF", "RF"] if p_type == '打者' else ["全部 (ALL)", "SP", "RP", "CL"], key="fan_season_pos")
        
        metric_opts = ['Score', 'R', 'H', 'HR', 'RBI', 'SB', '1B', '2B', '3B'] if p_type == '打者' else ['Score', 'W', 'SV', 'K', 'QS', 'HLD', 'ERA', 'WHIP']
        sort_f_metric = col_f2.selectbox("📊 選擇排序指標", metric_opts, index=0, key="fan_season_metric")
        sort_f_order = col_f3.selectbox("排序方式", ["由高到低", "由低到高"], index=0, key="fan_season_order")
        
        if p_type == '打者':
            min_filter_season = col_f4.number_input("設定本季 PA (打席) 下限", min_value=0, value=30, step=10, key="fan_season_pa")
            filtered_raw_data = raw_data[raw_data['PA'] >= min_filter_season].copy() if 'PA' in raw_data.columns else raw_data.copy()
        else:
            min_filter_season = col_f4.number_input("設定本季 IP (局數) 下限", min_value=0.0, value=10.0, step=5.0, key="fan_season_ip")
            filtered_raw_data = raw_data[raw_data['IP'] >= min_filter_season].copy() if 'IP' in raw_data.columns else raw_data.copy()
        
        # 🔥 依據精確的 Fantasy 權重計算本季所有數據的真實積分 (Score)
        def calc_fantasy_score(row, pt):
            score = 0.0
            if pt == '打者':
                weights = {'R': 3, 'H': 2, '1B': 3, '2B': 6, '3B': 10, 'HR': 15, 'RBI': 2, 'SB': 5, 'BB': 2, 'HBP': 3, 'K': -2, 'E': -3, 'CYC': 20, 'SLAM': 30}
                for stat, w in weights.items():
                    if stat in row and pd.notna(row[stat]):
                        try: score += float(row[stat]) * w
                        except: pass
            else:
                weights = {'W': 20, 'L': -10, 'SHO': 15, 'SV': 8, 'H': -1, 'ER': -3, 'HR': -5, 'BB': -1, 'HBP': -2, 'K': 4, 'WP': -3, 'HLD': 3, 'QS': 10, 'BSV': -10}
                for stat, w in weights.items():
                    if stat in row and pd.notna(row[stat]):
                        try: score += float(row[stat]) * w
                        except: pass
                        
                # 處理 Outs (OUT) 邏輯，由局數 (IP) 換算
                outs = 0
                if 'OUT' in row and pd.notna(row['OUT']):
                    try: outs = float(row['OUT'])
                    except: pass
                elif 'IP' in row and pd.notna(row['IP']):
                    try:
                        ip = float(row['IP'])
                        outs = int(ip) * 3 + int(round((ip - int(ip)) * 10))
                    except: pass
                score += outs * 1  # OUT 的權重是 1
                
            return round(score, 1)

        filtered_raw_data['Score'] = filtered_raw_data.apply(lambda r: calc_fantasy_score(r, p_type), axis=1)
        
        fantasy_cols = ['Player', 'Team', 'Position', 'Score', 'R', 'H', '1B', '2B', '3B', 'HR', 'RBI', 'SB', 'BB', 'HBP', 'K', 'E'] if p_type == '打者' else ['Player', 'Team', 'Position', 'Score', 'W', 'L', 'SHO', 'SV', 'OUT', 'H', 'ER', 'HR', 'BB', 'HBP', 'K', 'WP', 'HLD', 'QS', 'BSV']
        fantasy_cols = [c for c in fantasy_cols if c in filtered_raw_data.columns]
        fantasy_df = filtered_raw_data[fantasy_cols].copy()
        
        if sel_fantasy_pos != "全部 (ALL)": 
            fantasy_df = fantasy_df[fantasy_df['Position'].astype(str).apply(lambda x: sel_fantasy_pos in [p.strip() for p in x.split(',')])]
            
        if not fantasy_df.empty:
            if sort_f_metric in fantasy_df.columns:
                fantasy_df = fantasy_df.sort_values(by=sort_f_metric, ascending=(sort_f_order == "由低到高")).reset_index(drop=True)
                
            if 'E' in fantasy_df.columns: fantasy_df['E'] = pd.to_numeric(fantasy_df['E'], errors='coerce').fillna(0).astype(int)
            
            def style_team_color(row):
                try: tc = get_team_color(row['Team'])[0]
                except: tc = "#555"
                styles = [''] * len(row)
                for i, col in enumerate(row.index):
                    if col in ['Player', 'Team', 'Position']:
                        styles[i] = f'color: {tc} !important; font-weight: 900 !important;'
                return styles

            styled_fan = fantasy_df.style.apply(style_team_color, axis=1)\
                                         .apply(style_fantasy_pts, axis=0)\
                                         .format(get_fmt_dict(fantasy_df), na_rep="-").hide(axis='index')
            st.markdown(f"<div class='table-scroll-container rank-table-container'>{styled_fan.to_html()}</div>", unsafe_allow_html=True)
        else: st.warning("⚠️ 無符合條件的數據。")
        
    if selected_fantasy == "📝 夢幻球隊":
        st.markdown("### 🏢 夢幻球隊總管")
        leagues = list(st.session_state.fantasy_db.keys())
        valid_leagues = [lg for lg in leagues if lg not in ['external_taken', 'real_il_players']]
        
        c1, c2, c3 = st.columns(3)
        sel_league = c1.selectbox("選擇你的聯盟", valid_leagues, key="fan_myteam_league") if valid_leagues else None
        teams = list(st.session_state.fantasy_db[sel_league].keys()) if sel_league else []
        sel_team = c2.selectbox("選擇你的球隊", teams, key="fan_myteam_team") if teams else None
        
        # ==========================================
        # 📅 🔥 總管升級：動態日期調度與智能陣容繼承系統
        # ==========================================
        target_date_str = today_str # 預設安全牌
        if sel_league and sel_team:
            try:
                start_date = datetime.strptime(today_str, "%Y-%m-%d")
            except:
                start_date = datetime.now()
            
            # 自動產生 rolling 10 天的日期選項 (包含前2天到未來7天，供總管跨日布局)
            date_options = []
            date_labels = []
            weeks_ch = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
            for i in range(-2, 8):
                d = start_date + timedelta(days=i)
                d_str = d.strftime("%Y-%m-%d")
                w_label = weeks_ch[d.weekday()]
                
                if i == 0: label = f"📅 {d_str} ({w_label}) - 今日陣容"
                elif i == 1: label = f"🔮 {d_str} ({w_label}) - 明日預排"
                else: label = f"⚪ {d_str} ({w_label})"
                
                date_options.append(d_str)
                date_labels.append(label)
            
            # 在原本空缺的 c3 欄位渲染日期選擇器
            # 🔥 總管時區切換引擎：取得台灣時間 (UTC+8)
            tw_now = datetime.utcnow() + timedelta(hours=8)
            
            # 智能判斷：下午 6 點 (18:00) 後預設切換到「明日預排」(index=3)，否則維持「今日陣容」(index=2)
            smart_index = 3 if tw_now.hour >= 18 else 2
            
            # 在原本空缺的 c3 欄位渲染日期選擇器 (套用智能 index)
            chosen_label = c3.selectbox("選擇管理日期", date_labels, index=smart_index, key="fan_myteam_date_selector")
            target_date_str = date_options[date_labels.index(chosen_label)]
        # ==========================================

        with st.expander("➕ 新建聯盟與球隊", expanded=(not valid_leagues)):
            new_lg = st.text_input("聯盟名稱 (League)", key="fan_new_lg")
            new_tm = st.text_input("球隊名稱 (Team)", key="fan_new_tm")
            st.caption("🟢 先發數量 (Active)：")
            c_c, c_1b, c_2b, c_3b = st.columns(4)
            c_c = c_c.number_input("C", 0, 5, 1, key="fan_c_c"); c_1b = c_1b.number_input("1B", 0, 5, 1, key="fan_c_1b")
            c_2b = c_2b.number_input("2B", 0, 5, 1, key="fan_c_2b"); c_3b = c_3b.number_input("3B", 0, 5, 1, key="fan_c_3b")
            c_ss, c_if, c_of, c_util = st.columns(4)
            c_ss = c_ss.number_input("SS", 0, 5, 1, key="fan_c_ss"); c_if = c_if.number_input("IF (內野)", 0, 5, 1, key="fan_c_if")
            c_of = c_of.number_input("OF", 0, 10, 3, key="fan_c_of"); c_util = c_util.number_input("UTIL", 0, 5, 1, key="fan_c_util")
            c_sp, c_rp, c_p, _ = st.columns(4)
            c_sp = c_sp.number_input("SP", 0, 10, 5, key="fan_c_sp"); c_rp = c_rp.number_input("RP", 0, 10, 3, key="fan_c_rp"); c_p = c_p.number_input("P (通用投手)", 0, 10, 1, key="fan_c_p")
            st.caption("⚪ 保留區數量 (Inactive)：")
            c_bn, c_il, c_na = st.columns(3)
            c_bn = c_bn.number_input("BN", 0, 15, 3, key="fan_c_bn"); c_il = c_il.number_input("IL", 0, 10, 2, key="fan_c_il"); c_na = c_na.number_input("NA", 0, 10, 1, key="fan_c_na")
            max_roster_limit = st.slider("球隊總人數上限 (先發+BN)", 10, 50, 30, key="fan_max_roster")
            
            st.divider()
            st.markdown("#### ⚙️ 自訂聯盟計分規則")
            st.markdown("**打者分數 (Hitters)**")
            sel_h_cats = st.multiselect("選擇打者計分項目", ALL_HITTER_CATS, default=['R', 'H', '1B', '2B', '3B', 'HR', 'RBI', 'SB', 'BB', 'HBP', 'K', 'E', 'CYC', 'SLAM'], key="fan_h_cats")
            h_weights = {}
            cols_h = st.columns(5)
            for i, cat in enumerate(sel_h_cats): h_weights[cat] = cols_h[i % 5].number_input(cat, value=HARDCORE_WEIGHTS['Hitter'].get(cat, 1.0), step=0.5, key=f"h_wt_{cat}")
                
            st.markdown("**投手分數 (Pitchers)**")
            sel_p_cats = st.multiselect("選擇投手計分項目", ALL_PITCHER_CATS, default=['W', 'L', 'SHO', 'SV', 'OUT', 'H', 'ER', 'HR', 'BB', 'HBP', 'K', 'WP', 'HLD', 'QS', 'BSV'], key="fan_p_cats")
            p_weights = {}
            cols_p = st.columns(5)
            for i, cat in enumerate(sel_p_cats): p_weights[cat] = cols_p[i % 5].number_input(cat, value=HARDCORE_WEIGHTS['Pitcher'].get(cat, 1.0), step=0.5, key=f"p_wt_{cat}")
            
            if st.button("建立球隊 🚀", use_container_width=True, key="fan_create_btn"):
                if new_lg and new_tm:
                    total_active = c_c + c_1b + c_2b + c_3b + c_ss + c_if + c_of + c_util + c_sp + c_rp + c_p
                    if total_active + c_bn > max_roster_limit: st.error(f"⚠️ 先發+板凳共 {total_active + c_bn} 人，超過上限 {max_roster_limit} 人！")
                    else:
                        if new_lg not in st.session_state.fantasy_db: st.session_state.fantasy_db[new_lg] = {}
                        st.session_state.fantasy_db[new_lg][new_tm] = {
                            "config": {"C": c_c, "1B": c_1b, "2B": c_2b, "3B": c_3b, "SS": c_ss, "IF": c_if, "OF": c_of, "UTIL": c_util, "SP": c_sp, "RP": c_rp, "P": c_p, "BN": c_bn, "IL": c_il, "NA": c_na},
                            "scoring": {"Hitter": h_weights, "Pitcher": p_weights},
                            "roster": {}
                        }
                        save_db(st.session_state.fantasy_db) 
                        st.success(f"成功建立 {new_tm}! 專屬計分規則已綁定。")
                        st.rerun()
                else: st.error("請填寫名稱！")
        
        if sel_league and sel_team:
            team_data = st.session_state.fantasy_db[sel_league][sel_team]
            config = team_data["config"]
            # 🔥 V2.0 雲端球隊自動修復機制：如果新成立的球隊沒有 roster 資料夾，就自動建立！
            if "roster" not in team_data:
                team_data["roster"] = {}
            # 🔥 智能繼承核心：如果點擊的日期還沒有登記陣容，自動抓取「該日期之前最近的一天」完美拷貝！
            if target_date_str not in team_data["roster"]:
                past_dates = sorted([d for d in team_data["roster"].keys() if d < target_date_str])
                team_data["roster"][target_date_str] = team_data["roster"][past_dates[-1]].copy() if past_dates else {}
                save_db(st.session_state.fantasy_db)
                
            roster = team_data["roster"][today_str]
            scoring = team_data.get("scoring", FANTASY_WEIGHTS)
            # 🔥 啟動總管覆寫權限：取得自訂守位，並強制寫入基礎資料表 (解決下拉選單抓不到的問題)
            custom_positions = team_data.get("custom_positions", {})
            if custom_positions:
                raw_data_h['Position'] = raw_data_h['Player'].map(custom_positions).fillna(raw_data_h['Position'])
                raw_data_p['Position'] = raw_data_p['Player'].map(custom_positions).fillna(raw_data_p['Position'])
            
            st.markdown(f"### 📋 {sel_team} 混合陣容名單 ({target_date_str})")
            player_to_slot = {v: k for k, v in roster.items()}
            
            with st.spinner("運算陣容積分與短板模型中..."):
                weekly_h = fetch_recent_form_ranking("打者")
                weekly_p = fetch_recent_form_ranking("投手")
                # 🔥 將自訂守位同步到本週即時積分表 (讓畫面的守位文字也變動)
                if custom_positions and not weekly_h.empty and 'Position' in weekly_h.columns:
                    weekly_h['Position'] = weekly_h['Player'].map(custom_positions).fillna(weekly_h['Position'])
                if custom_positions and not weekly_p.empty and 'Position' in weekly_p.columns:
                    weekly_p['Position'] = weekly_p['Player'].map(custom_positions).fillna(weekly_p['Position'])
                for name in ['Shohei Ohtani', '大谷翔平']:
                    if not weekly_h.empty: weekly_h.loc[weekly_h['Player'] == name, 'Player'] = f"{name} (Batter)"
                    if not weekly_p.empty: weekly_p.loc[weekly_p['Player'] == name, 'Player'] = f"{name} (Pitcher)"
                if not weekly_h.empty: weekly_h['Fan_Pts'] = recalculate_custom_score(weekly_h, "打者", scoring)
                if not weekly_p.empty: weekly_p['Fan_Pts'] = recalculate_custom_score(weekly_p, "投手", scoring)
            active_h_slots, active_p_slots, inactive_slots = ["C", "1B", "2B", "3B", "SS", "IF", "OF", "UTIL"], ["SP", "RP", "P"], ["BN", "IL", "NA"]
            
            # ==========================================
            # 🔥 總管升級：同名雙胞胎身分證系統 (必須放在過濾名單的最前面！)
            # ==========================================
            def add_team_tag_to_duplicates(df, force_names=None):
                if df.empty: return df, force_names
                
                # 如果沒有強制指定名單，就自動抓出重複的人名
                if force_names is None:
                    name_counts = df['Player'].value_counts()
                    force_names = name_counts[name_counts > 1].index.tolist()
                    
                if force_names:
                    team_abbr = {
                        "Los Angeles Dodgers": "LAD", "Oakland Athletics": "OAK", "Kansas City Royals": "KC",
                        "Washington Nationals": "WSH", "Atlanta Braves": "ATL", "San Diego Padres": "SD",
                        "Texas Rangers": "TEX", "Seattle Mariners": "SEA", "New York Yankees": "NYY",
                        "Chicago Cubs": "CHC", "Cincinnati Reds": "CIN", "Miami Marlins": "MIA",
                        "Houston Astros": "HOU", "Toronto Blue Jays": "TOR", "Boston Red Sox": "BOS",
                        "Tampa Bay Rays": "TB", "Baltimore Orioles": "BAL", "Minnesota Twins": "MIN",
                        "Chicago White Sox": "CWS", "Cleveland Guardians": "CLE", "Detroit Tigers": "DET",
                        "Los Angeles Angels": "LAA", "New York Mets": "NYM", "Philadelphia Phillies": "PHI",
                        "Milwaukee Brewers": "MIL", "Pittsburgh Pirates": "PIT", "St. Louis Cardinals": "STL",
                        "Arizona Diamondbacks": "ARI", "Colorado Rockies": "COL", "San Francisco Giants": "SF"
                    }
                    for name in force_names:
                        mask = df['Player'] == name
                        if mask.any():
                            df.loc[mask, 'Player'] = df.loc[mask].apply(
                                lambda row: f"{name} ({team_abbr.get(str(row.get('Team', '')), str(row.get('Team', ''))[:3].upper())})", axis=1
                            )
                return df, force_names

            # 1. 優先為所有資料庫發放身分證 (讓 weekly 也強制掛上，確保 Fan_Pts 不會是 0)
            raw_data_h, dup_h = add_team_tag_to_duplicates(raw_data_h)
            raw_data_p, dup_p = add_team_tag_to_duplicates(raw_data_p)
            weekly_h, _ = add_team_tag_to_duplicates(weekly_h, force_names=dup_h)
            weekly_p, _ = add_team_tag_to_duplicates(weekly_p, force_names=dup_p)
            # 🔥 終極清洗：發完身分證後，強制清除資料庫裡的同名複製人，防止表格與選單分身！
            raw_data_h = raw_data_h.drop_duplicates(subset=['Player'])
            raw_data_p = raw_data_p.drop_duplicates(subset=['Player'])
            
            # 2. 取得下拉選單存入的陣容名單
            act_h_players = [roster.get(f"{pos}_{i}", "") for pos in active_h_slots for i in range(config.get(pos, 0)) if roster.get(f"{pos}_{i}")]
            act_p_players = [roster.get(f"{pos}_{i}", "") for pos in active_p_slots for i in range(config.get(pos, 0)) if roster.get(f"{pos}_{i}")]
            ina_players = [roster.get(f"{pos}_{i}", "") for pos in inactive_slots for i in range(config.get(pos, 0)) if roster.get(f"{pos}_{i}")]
            
            # 3. 從「已經掛好身分證」的總資料庫中撈人
            # 🔥 第二道物理防線：不管源頭有幾個，抓進表格的瞬間強制去重複！
            df_act_h = raw_data_h[raw_data_h['Player'].isin(act_h_players)].drop_duplicates(subset=['Player']).copy() if act_h_players else pd.DataFrame()
            df_act_p = raw_data_p[raw_data_p['Player'].isin(act_p_players)].drop_duplicates(subset=['Player']).copy() if act_p_players else pd.DataFrame()
            df_ina_h = raw_data_h[raw_data_h['Player'].isin(ina_players)].drop_duplicates(subset=['Player']).copy() if ina_players else pd.DataFrame()
            df_ina_p = raw_data_p[raw_data_p['Player'].isin(ina_players)].drop_duplicates(subset=['Player']).copy() if ina_players else pd.DataFrame()

            # 4. 補上 Fan_Pts (近七日積分)
            for df, w_df in [(df_act_h, weekly_h), (df_act_p, weekly_p), (df_ina_h, weekly_h), (df_ina_p, weekly_p)]:
                if not df.empty:
                    if not w_df.empty and 'Fan_Pts' in w_df.columns:
                        safe_w_df = w_df.drop_duplicates(subset=['Player'])
                        df['Fan_Pts'] = df['Player'].map(safe_w_df.set_index('Player')['Fan_Pts']).fillna(0.0)
                    else:
                        df['Fan_Pts'] = 0.0
            # 🔥 總管分數強制覆寫引擎 (解決 API 算錯或延遲，手動修正點數並同步計入總分)
            custom_scores = team_data.get("custom_scores", {})
            if custom_scores:
                for temp_df in [df_act_h, df_act_p, df_ina_h, df_ina_p]:
                    if not temp_df.empty:
                        temp_df['Fan_Pts'] = temp_df['Player'].map(custom_scores).fillna(temp_df['Fan_Pts'])           
            # ==========================================
            pts_h = df_act_h['Fan_Pts'].sum().round(2) if not df_act_h.empty else 0.0
            pts_p = df_act_p['Fan_Pts'].sum().round(2) if not df_act_p.empty else 0.0
            total_pts = round(pts_h + pts_p, 2)
            
            st.markdown(f'''
                <div style="background-color:#f8f9fa; padding:15px 25px; border-left:5px solid #00E676; border-radius:4px; margin-bottom:20px; display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <span style="font-size:1.1em; color:#555; font-weight:bold;">本週全隊先發總貢獻 (H2H Total)：</span><br>
                        <span style="font-size:2.5em; color:#111; font-weight:900;">{total_pts:,.2f}</span>
                        <span style="font-size:0.9em; color:#888;">pts</span>
                    </div>
                    <div style="text-align:right;">🏏 打者貢獻: <b>{pts_h:,.2f}</b> pts<br>⚾ 投手貢獻: <b>{pts_p:,.2f}</b> pts</div>
                </div>
            ''', unsafe_allow_html=True)
            
            def style_il_players(row):
                # 自動辨識球隊主色
                try: tc = get_team_color(row['Team'])[0]
                except: tc = "#555"
                
                styles = [''] * len(row)
                for i, col in enumerate(row.index):
                    # 前 4 欄全部套用球隊主色
                    if col in ['Slot (指派位置)', 'Player', 'Team', 'Position']:
                        styles[i] = f'color: {tc} !important; font-weight: 900 !important;'
                    # Fan_Pts 依然保留您的專屬道奇藍
                    elif col == 'Fan_Pts':
                        styles[i] = 'color: #005A9C !important; font-weight: 900 !important; font-size: 1.15em;'
                
                # 真實傷兵標記覆蓋 (紅底紅字)
                # 🟢 真實傷兵標記覆蓋 (保留球隊主色，僅套用淡紅色背景提示)
                if row.get('Player') in combined_il_players:
                    for i, col in enumerate(row.index):
                        if col == 'Player':
                            # 🔥 讓文字顏色強制維持 {tc} (球隊主色)，只在背景亮紅燈！
                            styles[i] = f'color: {tc} !important; background-color: #FFEBEE !important; font-weight: 900 !important;'
                            
                return styles
            
            show_cols = ['Slot (指派位置)', 'Player', 'Team', 'Position', 'Fan_Pts']
            c_act_h, c_act_p = st.columns(2)
            
            with c_act_h:
                st.markdown("#### 🟢 Active (今日先發 - 打者)")
                if not df_act_h.empty:
                    df_act_h['Slot (指派位置)'] = df_act_h['Player'].map(player_to_slot)
                    styled_df = df_act_h[[c for c in show_cols if c in df_act_h.columns]].sort_values('Slot (指派位置)').style.apply(style_il_players, axis=1).format(get_fmt_dict(df_act_h), na_rep="-").hide(axis='index')
                    st.markdown(f"<div class='table-scroll-container'>{styled_df.to_html()}</div>", unsafe_allow_html=True)
                else: st.info("無先發打者。")

            with c_act_p:
                st.markdown("#### 🟢 Active (今日先發 - 投手)")
                if not df_act_p.empty:
                    df_act_p['Slot (指派位置)'] = df_act_p['Player'].map(player_to_slot)
                    styled_df = df_act_p[[c for c in show_cols if c in df_act_p.columns]].sort_values('Slot (指派位置)').style.apply(style_il_players, axis=1).format(get_fmt_dict(df_act_p), na_rep="-").hide(axis='index')
                    st.markdown(f"<div class='table-scroll-container'>{styled_df.to_html()}</div>", unsafe_allow_html=True)
                else: st.info("無先發投手。")
            
            st.markdown("#### ⚪ Bench / IL / NA (未啟用)")
            df_ina_combined = pd.concat([df_ina_h, df_ina_p])
            if not df_ina_combined.empty:
                df_ina_combined['Slot (指派位置)'] = df_ina_combined['Player'].map(player_to_slot)
                styled_df = df_ina_combined[[c for c in show_cols if c in df_ina_combined.columns]].sort_values('Slot (指派位置)').style.apply(style_il_players, axis=1).format(get_fmt_dict(df_ina_combined), na_rep="-").hide(axis='index')
                st.markdown(f"<div class='table-scroll-container' style='opacity: 0.85;'>{styled_df.to_html()}</div>", unsafe_allow_html=True)
            else: st.info("目前板凳區為空。")
            
            st.divider()
            st.markdown("### 🧠 AI 總管：Z-Score 陣容短板與資產交換診斷")
            st.caption("系統將您的先發陣容表現轉化為標準分數，找出球隊的致勝武器與防守漏洞！")
            
            active_players_all = act_h_players + act_p_players
            if active_players_all:
                # 1. 畫雷達圖與基本體檢
                z_scores = calc_z_scores_for_roster(active_players_all)
                radar_vals = list(z_scores.values())
                categories = list(z_scores.keys())

                c_radar, c_diag = st.columns([1, 1])
                fig_z = go.Figure(go.Scatterpolar(
                    r=radar_vals + [radar_vals[0]],
                    theta=categories + [categories[0]],
                    fill='toself', line_color='#00E676', fillcolor='rgba(0, 230, 118, 0.4)'
                ))
                fig_z.update_layout(polar=dict(radialaxis=dict(range=[0, 100], tickfont=dict(size=10))), height=350, margin=dict(l=30, r=30, t=30, b=30))
                c_radar.plotly_chart(fig_z, use_container_width=True, key=f"myteam_zscore_radar_{sel_league}_{sel_team}")

                with c_diag:
                    if radar_vals:
                        max_idx = radar_vals.index(max(radar_vals))
                        min_idx = radar_vals.index(min(radar_vals))
                        strongest, weakest = categories[max_idx], categories[min_idx]

                        st.markdown(f"#### 📊 陣容體檢報告")
                        st.markdown(f"🟢 **戰力溢出 (領先聯盟)：** <br><span style='color:#00E676; font-size: 1.2em; font-weight: bold;'>{strongest}</span>", unsafe_allow_html=True)
                        st.markdown(f"🔴 **致命短板 (落後聯盟)：** <br><span style='color:#FF5252; font-size: 1.2em; font-weight: bold;'>{weakest}</span>", unsafe_allow_html=True)

                        # 定義強弱項目供 AI 使用
                        strong_cats = [k for k, v in z_scores.items() if v >= 72]
                        weak_cats = [k for k, v in z_scores.items() if v <= 52]
                        if not strong_cats: strong_cats = [strongest]
                        if not weak_cats: weak_cats = [weakest]

                # ==========================================
                # 🧠 AI 補強情蒐雷達與邊際效益分析
                # ==========================================
                st.divider()
                st.markdown("#### 📡 AI 補強情蒐雷達")
                
                # 撈出全聯盟已被持有的球員，避免推薦到別人隊上的球員
                owned_players = set()
                for tm_name, tm_data in st.session_state.fantasy_db[sel_league].items():
                    if not isinstance(tm_data, dict): continue
                    for p in tm_data.get("roster", {}).get(target_date_str, {}).values():
                        if p and p != "空缺": owned_players.add(p)
                for p in st.session_state.fantasy_db.get('external_taken', []):
                    owned_players.add(p)

                with st.expander("🛒 查看 AI 推薦自由市場補強名單 (可收縮)"):
                    st.caption("AI 根據您目前的戰力短板，自動掃描自由市場中最合適的補強標的：")
                    fa_h = raw_data_h[~raw_data_h['Player'].isin(owned_players)]
                    fa_p = raw_data_p[~raw_data_p['Player'].isin(owned_players)]
                    
                    recommend_list = []
                    if weak_cats:
                        st.write("##### 🎯 針對您的短板項目推薦：")
                        for cat in weak_cats:
                            if "全壘打" in cat or "攻擊" in cat or "產出" in cat:
                                top_fa = fa_h.sort_values(by='HR', ascending=False).head(2)
                                for _, r in top_fa.iterrows():
                                    st.write(f"⚾ **{r['Player']}** ({r.get('Team','FA')}) - 本季 {r.get('HR',0)} HR / {r.get('OPS',0)} OPS ➔ 可大幅拉抬 **{cat}**")
                                    recommend_list.append(r['Player'])
                            elif "盜壘" in cat:
                                top_fa = fa_h.sort_values(by='SB', ascending=False).head(2)
                                for _, r in top_fa.iterrows():
                                    st.write(f"🏃‍♂️ **{r['Player']}** ({r.get('Team','FA')}) - 本季 {r.get('SB',0)} 次盜壘 ➔ 可瞬間補足 **{cat}**")
                                    recommend_list.append(r['Player'])
                            elif "牛棚" in cat:
                                fa_p_copy = fa_p.copy()
                                fa_p_copy['SV_HLD'] = pd.to_numeric(fa_p_copy.get('SV',0), errors='coerce').fillna(0) + pd.to_numeric(fa_p_copy.get('HLD',0), errors='coerce').fillna(0)
                                top_fa = fa_p_copy.sort_values(by='SV_HLD', ascending=False).head(2)
                                for _, r in top_fa.iterrows():
                                    st.write(f"🎴 **{r['Player']}** ({r.get('Team','FA')}) - 累積 {int(r['SV_HLD'])} 次救援+中繼 ➔ 可防禦 **{cat}**")
                                    recommend_list.append(r['Player'])
                            elif "三振" in cat or "壓制" in cat:
                                fa_p_copy = fa_p.copy()
                                top_fa = fa_p_copy.sort_values(by='K', ascending=False).head(2)
                                for _, r in top_fa.iterrows():
                                    st.write(f"🎯 **{r['Player']}** ({r.get('Team','FA')}) - 累積 {int(r.get('K',0))} 次三振 ➔ 可補強 **{cat}**")
                                    recommend_list.append(r['Player'])
                    else:
                        st.success("💡 AI 報告：您目前的陣容沒有明顯短板，建議維持現狀或進行等價資產優化！")

                # 🔥 宣告共用變數：確保下方兩個收縮面板都能讀取到，且不會互相洗版
                current_roster_players = [p for p in roster.values() if p and p != "空缺"]
                drop_suggestions = []
                suggested_set = set()

                with st.expander("🗑️ 查看 AI 建議割愛斷捨離名單 (可收縮)"):
                    st.caption("AI 掃描您隊上貢獻度較低，或是所處項目已經嚴重戰力溢出的球員：")
                    my_h = raw_data_h[raw_data_h['Player'].isin(current_roster_players)]
                    my_p = raw_data_p[raw_data_p['Player'].isin(current_roster_players)]
                    
                    if strong_cats:
                        st.write("##### ⚠️ 戰力已溢出，可作為交易籌碼或釋出的球員：")
                        for cat in strong_cats:
                            if "牛棚" in cat and not my_p.empty:
                                my_p_copy = my_p.copy()
                                my_p_copy = my_p_copy[my_p_copy['Position'].astype(str).str.contains(r'\b(SP|RP|P)\b', regex=True, na=False)]
                                my_p_copy['SV_HLD'] = pd.to_numeric(my_p_copy.get('SV',0), errors='coerce').fillna(0) + pd.to_numeric(my_p_copy.get('HLD',0), errors='coerce').fillna(0)
                                worst_reliever = my_p_copy.sort_values(by='SV_HLD', ascending=True).head(1)
                                if not worst_reliever.empty:
                                    p_name = worst_reliever['Player'].values[0]
                                    if p_name not in suggested_set:
                                        st.write(f"💼 **{p_name}**：隊上牛棚分數已嚴重溢出。釋出他或將他作為交易包裝籌碼，絕不影響您的牛棚項目優勢。")
                                        drop_suggestions.append(p_name)
                                        suggested_set.add(p_name)
                                        
                            elif ("三振" in cat or "壓制" in cat) and not my_p.empty:
                                my_p_copy = my_p.copy()
                                my_p_copy = my_p_copy[my_p_copy['Position'].astype(str).str.contains(r'\b(SP|RP|P)\b', regex=True, na=False)]
                                my_p_copy['K_num'] = pd.to_numeric(my_p_copy.get('K',0), errors='coerce').fillna(0)
                                worst_k = my_p_copy.sort_values(by='K_num', ascending=True).head(1)
                                if not worst_k.empty:
                                    p_name = worst_k['Player'].values[0]
                                    if p_name not in suggested_set:
                                        st.write(f"🦅 **{p_name}**：目前團隊【{cat}】戰力處於全聯盟絕對領先，他是您陣容中該項目邊緣資產，建議將其拿去換取打者補強短板！")
                                        drop_suggestions.append(p_name)
                                        suggested_set.add(p_name)

                            elif ("全壘打" in cat or "盜壘" in cat or "攻擊" in cat or "產出" in cat) and not my_h.empty:
                                my_h_copy = my_h.copy()
                                my_h_copy = my_h_copy[~my_h_copy['Position'].astype(str).str.contains(r'\b(SP|RP|P)\b', regex=True, na=False)]
                                if not my_h_copy.empty:
                                    my_h_copy['OPS_num'] = pd.to_numeric(my_h_copy.get('OPS',0), errors='coerce').fillna(0.0)
                                    worst_h = my_h_copy.sort_values(by='OPS_num', ascending=True).head(1)
                                    if not worst_h.empty:
                                        p_name = worst_h['Player'].values[0]
                                        if p_name not in suggested_set:
                                            st.write(f"🪵 **{p_name}**：目前團隊【{cat}】砲火在聯盟過剩，他的進攻產出對您目前影響極低，可放心降為 BN 或釋出。")
                                            drop_suggestions.append(p_name)
                                            suggested_set.add(p_name)

                with st.expander("📉 查看 AI 評定陣容邊緣人名單 (可收縮)"):
                    st.caption("AI 自動追蹤您隊上目前【健康出賽】但「近七日真實貢獻積分」最低的球員，協助您進行汰弱留強：")
                    
                    all_team_dfs = pd.concat([df_act_h, df_act_p, df_ina_h, df_ina_p]) if 'df_act_h' in locals() else pd.DataFrame()
                    if not all_team_dfs.empty and 'Fan_Pts' in all_team_dfs.columns:
                        healthy_team_dfs = all_team_dfs[~all_team_dfs['Player'].isin(combined_il_players)]
                        my_healthy_players = healthy_team_dfs[healthy_team_dfs['Player'].isin(current_roster_players)]
                        
                        if not my_healthy_players.empty:
                            bh_h = my_healthy_players[~my_healthy_players['Position'].astype(str).str.contains(r'\b(SP|RP|P)\b', regex=True, na=False)].sort_values(by='Fan_Pts', ascending=True).head(1)
                            bh_p = my_healthy_players[my_healthy_players['Position'].astype(str).str.contains(r'\b(SP|RP|P)\b', regex=True, na=False)].sort_values(by='Fan_Pts', ascending=True).head(1)
                            
                            has_fringe = False
                            st.write("##### 📉 近七日健康成員貢獻低迷警報：")
                            for _, r in bh_h.iterrows():
                                if r['Player'] not in suggested_set:
                                    st.write(f"🪵 **{r['Player']}** ({r['Position']}) ➔ 近七日積分僅 `{r['Fan_Pts']}` pts。表現處於健康野手底層，建議釋出換取自由市場高近況打者。")
                                    drop_suggestions.append(r['Player'])
                                    suggested_set.add(r['Player'])
                                    has_fringe = True
                                    
                            for _, r in bh_p.iterrows():
                                if r['Player'] not in suggested_set:
                                    st.write(f"📉 **{r['Player']}** ({r['Position']}) ➔ 近七日積分僅 `{r['Fan_Pts']}` pts。表現處於健康投手邊緣，建議降為 BN 觀察或尋求免洗先發串流調度。")
                                    drop_suggestions.append(r['Player'])
                                    suggested_set.add(r['Player'])
                                    has_fringe = True
                                    
                            if not has_fringe:
                                st.info("💡 隊醫報告：目前隊上所有健康球員表現皆在水準之上，無明顯低迷隊員！")
                        else:
                            st.info("💡 隊醫報告：目前隊上無足夠健康球員資料可供分析！")

                # 3. 核心：戰力加減法動態預演面板
                st.markdown("#### ⚖️ 資產更換邊際效益預演")
                st.caption("在真正動手調整陣容前，讓 AI 幫您精算這場更換會帶來什麼化學反應：")
                
                col_ex1, col_ex2 = st.columns(2)
                with col_ex1:
                    ui_fa_options = ["請選擇要簽下的球員"] + sorted(list(fa_h['Player'].tolist() + fa_p['Player'].tolist()))
                    sim_add = st.selectbox("🤝 模擬簽下 (自由市場)", ui_fa_options, key="sim_add_player")
                with col_ex2:
                    current_roster_players = [p for p in roster.values() if p and p != "空缺"]
                    ui_my_options = ["請選擇要釋出的球員"] + sorted(current_roster_players)
                    sim_drop = st.selectbox("🗑️ 模擬釋出 (我方陣容)", ui_my_options, key="sim_drop_player")
                    
                if sim_add != "請選擇要簽下的球員" and sim_drop != "請選擇要釋出的球員":
                    # 🔥 替換 active_players_all 中的球員 (因為 Z-Score 是算先發名單的表現)
                    virtual_roster = [p for p in active_players_all if p != sim_drop]
                    if sim_add not in virtual_roster:
                        virtual_roster.append(sim_add)

                    z_scores_virtual = calc_z_scores_for_roster(virtual_roster)
                    
                    st.info(f"📊 **更換預演分析報告：{sim_drop} ➔ {sim_add}**")
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("##### 🟢 將會獲得的全新優勢/提升")
                        has_gain = False
                        for cat in z_scores.keys():
                            diff = z_scores_virtual[cat] - z_scores[cat]
                            if diff > 1.5:
                                st.write(f"📈 **{cat}** 分數大幅提升了 `+{round(diff, 1)}` 分！")
                                has_gain = True
                        if not has_gain: st.write("🔹 此更換未對主要項目帶來突破性提升。")
                                
                    with c2:
                        st.markdown("##### 🔴 將會失去的優勢/帶來的劣勢")
                        has_loss = False
                        for cat in z_scores.keys():
                            diff = z_scores_virtual[cat] - z_scores[cat]
                            if diff < -1.5:
                                st.write(f"📉 **{cat}** 分數退步了 `{round(diff, 1)}` 分！")
                                has_loss = True
                        if not has_loss: st.write("🔹 安全調度！此更換沒有帶來任何顯著的戰力倒退。")
            else: st.info("請先配置您的先發陣容以啟用 AI 診斷。")
        # ==========================================
            # 🛠️ 總管工具箱：自訂球員守位
            # ==========================================
            st.divider()
            st.markdown("### 🛠️ 總管專屬：球員守位覆寫系統")
            with st.expander("✏️ 指派新守位 (解決官方 API 錯誤 / 設定二刀流)"):
                if "custom_positions" not in team_data:
                    team_data["custom_positions"] = {}
                
                # 抓取目前球隊所有的球員名單
                current_roster_players = [p for p in roster.values() if p]
                
                if not current_roster_players:
                    st.info("目前陣容中沒有球員，請先到自由市場簽約！")
                else:
                    col_c1, col_c2, col_c3 = st.columns([2, 2, 1])
                    with col_c1:
                        target_player = st.selectbox("⚾ 選擇要修改的球員", current_roster_players, key="custom_pos_player")
                    with col_c2:
                        # 顯示球員目前的守備位置
                        current_pos = raw_data_h.loc[raw_data_h['Player'] == target_player, 'Position'].values
                        if len(current_pos) == 0:
                            current_pos = raw_data_p.loc[raw_data_p['Player'] == target_player, 'Position'].values
                        display_current_pos = current_pos[0] if len(current_pos) > 0 else "未知"
                        
                        st.caption(f"目前守位：`{display_current_pos}`")
                        pos_options = ["C", "1B", "2B", "3B", "SS", "OF", "DH", "SP", "RP", "P", "UTIL"]
                        new_pos = st.selectbox("🛡️ 指派新守位", pos_options, key="custom_pos_select", label_visibility="collapsed")
                        
                    with col_c3:
                        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True) # 對齊用
                        # 雙按鈕設計：疊加 vs 完全替換
                        b1, b2 = st.columns(2)
                        if b1.button("➕ 疊加新守位", use_container_width=True, help="保留原位置，新增此守位資格"):
                            # 組合新字串 (例如：OF, 2B)
                            updated_pos = f"{display_current_pos}, {new_pos}" if new_pos not in display_current_pos else display_current_pos
                            team_data["custom_positions"][target_player] = updated_pos
                            save_db(st.session_state.fantasy_db)
                            st.toast(f"✅ 擴充成功！{target_player} 的守位已更新為 {updated_pos}！")
                            st.rerun()
                            
                        if b2.button("🔄 完全替換", use_container_width=True, help="刪除原位置，完全替換為此守位"):
                            team_data["custom_positions"][target_player] = new_pos
                            save_db(st.session_state.fantasy_db)
                            st.toast(f"✅ 覆寫成功！{target_player} 的守位已完全替換為 {new_pos}！")
                            st.rerun()
            # ==========================================
            # ✍️ 總管專屬：球員分數手動修正系統
            # ==========================================
            st.markdown("### ✍️ 總管專屬：球員分數手動修正系統")
            with st.expander("✏️ 手動修正球員分數 (防止 API 算錯 / 強制微調數據)"):
                if "custom_scores" not in team_data:
                    team_data["custom_scores"] = {}
                
                # 獲取當前球隊名單中所有有名字的球員
                current_roster_players = [p for p in roster.values() if p and p != "空缺"]
                
                if not current_roster_players:
                    st.info("目前陣容中沒有球員，請先配置陣容！")
                else:
                    col_s1, col_s2, col_s3 = st.columns([2, 2, 1])
                    with col_s1:
                        score_target_player = st.selectbox("⚾ 選擇球員", current_roster_players, key="custom_score_player")
                    with col_s2:
                        # 自動抓取該球員目前的顯示分數作為預設值
                        current_pts_val = 0.0
                        for df_check in [df_act_h, df_act_p, df_ina_h, df_ina_p]:
                            if not df_check.empty and score_target_player in df_check['Player'].values:
                                current_pts_val = float(df_check.loc[df_check['Player'] == score_target_player, 'Fan_Pts'].values[0])
                                break
                        
                        new_score_val = st.number_input("🔢 設定修正分數", value=current_pts_val, step=0.1, key="custom_score_value")
                    with col_s3:
                        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True) # 對齊用
                        sb1, sb2 = st.columns(2)
                        if sb1.button("💾 修正", use_container_width=True, key="btn_save_custom_score"):
                            team_data["custom_scores"][score_target_player] = new_score_val
                            save_db(st.session_state.fantasy_db)
                            st.toast(f"✅ 已手動將 {score_target_player} 的分數修正為 {new_score_val} pts！")
                            st.rerun()
                        if sb2.button("🔄 還原", use_container_width=True, key="btn_reset_custom_score", help="清除手動修正，恢復系統自動計算"):
                            if score_target_player in team_data["custom_scores"]:
                                del team_data["custom_scores"][score_target_player]
                                save_db(st.session_state.fantasy_db)
                                st.toast(f"🔄 已還原 {score_target_player} 的分數為系統自動計算！")
                                st.rerun()
                            else:
                                st.toast("💡 該球員本來就是系統自動計算，無需還原。")
            # ==========================================
            # ⚙️ 總管工具箱：聯盟擴建與人數設定
            # ==========================================
            st.markdown("### ⚙️ 聯盟擴建工程：修改陣容人數上限")
            with st.expander("🏟️ 調整各守位與板凳 / 傷兵席次"):
                if "config" not in team_data:
                    team_data["config"] = {}
                
                cfg = team_data["config"]
                st.info("💡 調整後，下方的「陣容異動面板」會立刻長出對應的新空位！")
                
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown("**⚾ 打者名額**")
                    new_c = st.number_input("C (捕手)", value=cfg.get("C", 1), min_value=0)
                    new_1b = st.number_input("1B (一壘)", value=cfg.get("1B", 1), min_value=0)
                    new_2b = st.number_input("2B (二壘)", value=cfg.get("2B", 1), min_value=0)
                    new_3b = st.number_input("3B (三壘)", value=cfg.get("3B", 1), min_value=0)
                    new_ss = st.number_input("SS (游擊)", value=cfg.get("SS", 1), min_value=0)
                    new_of = st.number_input("OF (外野)", value=cfg.get("OF", 3), min_value=0)
                    new_util = st.number_input("UTIL (工具人)", value=cfg.get("UTIL", 1), min_value=0)
                
                with c2:
                    st.markdown("**🎯 投手名額**")
                    new_sp = st.number_input("SP (先發)", value=cfg.get("SP", 2), min_value=0)
                    new_rp = st.number_input("RP (後援)", value=cfg.get("RP", 2), min_value=0)
                    new_p = st.number_input("P (任意投手)", value=cfg.get("P", 3), min_value=0)
                    
                with c3:
                    st.markdown("**⚪ 未啟用名單**")
                    new_bn = st.number_input("BN (板凳)", value=cfg.get("BN", 3), min_value=0)
                    new_il = st.number_input("IL (傷兵)", value=cfg.get("IL", 2), min_value=0)
                    new_na = st.number_input("NA (小聯盟)", value=cfg.get("NA", 1), min_value=0)
                    
                    st.markdown("<br>", unsafe_allow_html=True) # 排版對齊
                    if st.button("💾 更新球場設定", use_container_width=True):
                        # 儲存新設定
                        team_data["config"].update({
                            "C": new_c, "1B": new_1b, "2B": new_2b, "3B": new_3b, 
                            "SS": new_ss, "OF": new_of, "UTIL": new_util,
                            "SP": new_sp, "RP": new_rp, "P": new_p,
                            "BN": new_bn, "IL": new_il, "NA": new_na
                        })
                        
                        save_db(st.session_state.fantasy_db)
                        st.success("✅ 聯盟設定已更新！欄位已擴充！")
                        st.rerun()
           
            st.divider()
            st.markdown(f"### 🛠️ {target_date_str} 陣容異動與管理面板")
            st.caption("您可以直接在此切換球員或點擊右側釋出，系統將即時自動同步至雲端資料庫。")

            # 建立單一槽位的渲染引擎
            def render_management_slot(slot_key, pos_label, eligible_players):
                cur_player = roster.get(slot_key, None)
                col_slot, col_player, col_action = st.columns([1, 4, 1])
                
                with col_slot:
                    st.markdown(f"<div style='padding-top: 8px; font-weight: 900; color: #555; text-align: right;'>[ {pos_label} ]</div>", unsafe_allow_html=True)
                    
                with col_player:
                    # 準備下拉選單選項
                    options = ["空缺"] + eligible_players
                    def_idx = options.index(cur_player) if cur_player in options else 0
                    
                    chosen = st.selectbox(
                        "選擇球員", 
                        options=options, 
                        index=def_idx, 
                        key=f"mgt_sel_{slot_key}_{sel_league}_{sel_team}",
                        label_visibility="collapsed"
                    )
                    
                    # 即時異動偵測 (如果改變了選單，立刻存檔)
                    if chosen != (cur_player if cur_player else "空缺"):
                        if chosen == "空缺":
                            if slot_key in st.session_state.fantasy_db[sel_league][sel_team]["roster"][target_date_str]: 
                                del st.session_state.fantasy_db[sel_league][sel_team]["roster"][target_date_str][slot_key]
                        else:
                            st.session_state.fantasy_db[sel_league][sel_team]["roster"][target_date_str][slot_key] = chosen
                        save_db(st.session_state.fantasy_db)
                        st.rerun()

                with col_action:
                    # 如果有球員，顯示紅色釋出按鈕
                    if cur_player and cur_player != "空缺":
                        if st.button("❌ 釋出", key=f"mgt_drop_{slot_key}_{sel_league}_{sel_team}", use_container_width=True):
                            if slot_key in st.session_state.fantasy_db[sel_league][sel_team]["roster"][target_date_str]:
                                del st.session_state.fantasy_db[sel_league][sel_team]["roster"][target_date_str][slot_key]
                            save_db(st.session_state.fantasy_db)
                            st.toast(f"🗑️ 已將 {cur_player} 釋出至自由市場！")
                            st.rerun()

            st.markdown("##### ⚾ 攻擊陣容 (Hitters)")
            for pos in active_h_slots:
                count = config.get(pos, 0)
                eligible = get_eligible_players(pos, raw_data_h, raw_data_p)
                
                # 🔥 UTIL 解放宣言：無條件接受所有打者
                if pos == "UTIL":
                    eligible = raw_data_h['Player'].tolist()
                    
                # ⚠️ 注意這裡！這個 for 迴圈每個區塊只能出現一次
                for i in range(count):
                    render_management_slot(f"{pos}_{i}", f"{pos} {i+1}" if count > 1 else pos, eligible)

            st.markdown("##### 🎯 投手陣容 (Pitchers)")
            for pos in active_p_slots:
                count = config.get(pos, 0)
                eligible = get_eligible_players(pos, raw_data_h, raw_data_p)
                for i in range(count):
                    render_management_slot(f"{pos}_{i}", f"{pos} {i+1}" if count > 1 else pos, eligible)

            st.markdown("##### ⚪ 未啟用名單 (Bench / IL / NA)")
            for pos in inactive_slots:
                count = config.get(pos, 0)
                eligible = get_eligible_players(pos, raw_data_h, raw_data_p)
                
                # 🔥 板凳解放宣言：無條件接受所有打者與投手
                if pos in ["BN", "IL", "NA"]:
                    eligible = raw_data_h['Player'].tolist() + raw_data_p['Player'].tolist()
                    
                for i in range(count):
                    render_management_slot(f"{pos}_{i}", f"{pos} {i+1}" if count > 1 else pos, eligible)

    if selected_fantasy == "🛒 自由市場":
        st.markdown("### 🛒 自由市場與球探推薦 (FA / Waiver Wire)")
        leagues = list(st.session_state.fantasy_db.keys())
        valid_leagues = [lg for lg in leagues if lg not in ['external_taken', 'real_il_players']]
        if not valid_leagues: st.warning("請先建立聯盟，才能啟動預測引擎！")
        else:
            col_w1, col_w2, col_w3 = st.columns([1, 1, 1])
            waiver_league = col_w1.selectbox("操作聯盟", valid_leagues, key="waiver_league_select")
            
            owned_players = set()
            for tm, tdata in st.session_state.fantasy_db[waiver_league].items():
                r = tdata["roster"].get(target_date_str, {})
                for p in r.values():
                    if p: owned_players.add(p)
                        
            # ==========================================
            # 🔥 自由市場管理中樞：無框清爽版 (Form 自動清空技術)
            # ==========================================
            # 確保外部選走名單依然生效，供下方過濾使用
            cur_external = st.session_state.fantasy_db.get('external_taken', [])
            for p in cur_external: owned_players.add(p)


            c_ext1, c_ext2, c_ext3 = st.columns(3)
            
            with c_ext1:
                with st.form("form_ext", clear_on_submit=True):
                    add_ext = st.selectbox("🚫 標記外部選走", ["請選擇球員..."] + all_players)
                    submit_ext = st.form_submit_button("➕ 標記外部選走", use_container_width=True)
                    if submit_ext and add_ext != "請選擇球員...":
                        cur = st.session_state.fantasy_db.get('external_taken', [])
                        if add_ext not in cur:
                            cur.append(add_ext)
                            st.session_state.fantasy_db['external_taken'] = cur
                            save_db(st.session_state.fantasy_db)
                            st.toast(f"🚫 {add_ext} 已標記為外部選走！")
                            st.rerun()

            with c_ext2:
                with st.form("form_il", clear_on_submit=True):
                    add_il = st.selectbox(f"🏥 手動補傷兵 (已抓 {len(auto_il_players)} 人)", ["請選擇球員..."] + all_players)
                    submit_il = st.form_submit_button("➕ 加入傷兵名單", use_container_width=True)
                    if submit_il and add_il != "請選擇球員...":
                        cur = st.session_state.fantasy_db.get('real_il_players', [])
                        if add_il not in cur:
                            cur.append(add_il)
                            st.session_state.fantasy_db['real_il_players'] = cur
                            save_db(st.session_state.fantasy_db)
                            st.toast(f"🚑 {add_il} 已手動標記為傷兵！")
                            st.rerun()

            with c_ext3:
                with st.form("form_false", clear_on_submit=True):
                    false_il_options = sorted(list(auto_il_players)) if auto_il_players else []
                    add_false = st.selectbox("✅ 排除系統誤判", ["請選擇球員..."] + false_il_options)
                    submit_false = st.form_submit_button("➕ 解除傷兵警報", use_container_width=True)
                    if submit_false and add_false != "請選擇球員...":
                        cur = st.session_state.fantasy_db.get('false_il_players', [])
                        if add_false not in cur:
                            cur.append(add_false)
                            st.session_state.fantasy_db['false_il_players'] = cur
                            save_db(st.session_state.fantasy_db)
                            st.toast(f"💪 {add_false} 已解除傷兵警報！")
                            st.rerun()
            
            # 🔥 貼心設計：將原本佔空間的「框框字」收納進手風琴裡。眼不見為淨，要修改時再點開！
            with st.expander("⚙️ 管理已標記名單 (若不小心加錯，可在此點擊 ❌ 移除)"):
                mc1, mc2, mc3 = st.columns(3)
                with mc1:
                    cur_ext = st.session_state.fantasy_db.get('external_taken', [])
                    new_ext = st.multiselect("🚫 移除外部選走", cur_ext, default=cur_ext, key="mng_ext")
                    if new_ext != cur_ext:
                        st.session_state.fantasy_db['external_taken'] = new_ext
                        save_db(st.session_state.fantasy_db)
                        st.rerun()
                with mc2:
                    cur_il = st.session_state.fantasy_db.get('real_il_players', [])
                    new_il = st.multiselect("🏥 移除手動傷兵", cur_il, default=cur_il, key="mng_il")
                    if new_il != cur_il:
                        st.session_state.fantasy_db['real_il_players'] = new_il
                        save_db(st.session_state.fantasy_db)
                        st.rerun()
                with mc3:
                    cur_false = st.session_state.fantasy_db.get('false_il_players', [])
                    new_false = st.multiselect("✅ 移除誤判標記", cur_false, default=cur_false, key="mng_false")
                    if new_false != cur_false:
                        st.session_state.fantasy_db['false_il_players'] = new_false
                        save_db(st.session_state.fantasy_db)
                        st.rerun()
            st.divider()
            # ==========================================


            timeframe = col_w2.selectbox("📅 預測區間", ["🔥 近 7 天", "🔥 近 14 天", "🔥 近 1 個月", "🔮 未來 7 天", "🔮 未來 14 天"], key="fan_timeframe")
            # 🔥 自由市場專屬：升級為置中高質感膠囊切換鈕 (已修正完美縮排與變數)
            fa_col_left, fa_col_center, fa_col_right = st.columns([1, 1, 1])
            with fa_col_center:
                w_ptype = option_menu(
                    None, ["打者", "投手"], icons=["person-arms-up", "bullseye"],
                    default_index=0,
                    orientation="horizontal",
                    key="fa_ptype_option_menu", # 🛡️ 獨立 key 預防 Streamlit 重複元件報錯
                    styles={
                        "container": {"padding": "0!important", "margin": "0 auto 15px auto", "background-color": "#F0F2F6", "border-radius": "15px", "border": "none", "width": "100%"},
                        "nav-link": {"font-size": "14px", "padding": "5px", "font-weight": "bold", "color": "#555"},
                        "nav-link-selected": {"background-color": "#005A9C", "color": "white"} # 標準道奇藍
                    }
                )
            w_pos = col_w3.selectbox("🛡️ 守位", ["全部 (ALL)", "DH", "C", "1B", "2B", "3B", "SS", "IF", "OF", "UTIL"] if w_ptype == "打者" else ["全部 (ALL)", "SP", "RP", "P", "CL"], key="fan_w_pos")
            
           # ==========================================
            # 🏥 🔥 總管最高優化：高視覺質感膠囊選單 (均分完全置中版)
            # ==========================================
            # 🟢 採用 [0.5, 3, 0.5] 完美比例，並透過 flex 佈局強制膠囊完全填滿並居中對齊
            col_left, col_mid, col_right = st.columns([0.5, 3, 0.5])
            
            with col_mid:
                fa_health = option_menu(
                    None, ["💪 能出賽 (Active)", "🏥 傷兵 (IL / Out)", "全部"], 
                    icons=["shield-check", "heart-broken", "people-fill"],
                    default_index=0,
                    orientation="horizontal",
                    key="fa_health_option_menu_v8",
                    styles={
                        "container": {
                            "padding": "0!important", 
                            "margin": "0 auto", 
                            "background-color": "#F0F2F6", 
                            "border-radius": "15px", 
                            "border": "none", 
                            "width": "100%",
                            "display": "flex",
                            "justify-content": "space-between"
                        },
                        # 🔥 核心修正：利用 flex-grow 與 100% 寬度，迫使三個膠囊按鈕「均分版面」並「完全置中」！
                        "nav-item": {"flex-grow": "1", "text-align": "center"},
                        "nav-link": {
                            "font-size": "14px", 
                            "padding": "10px 0px", 
                            "font-weight": "bold", 
                            "color": "#555", 
                            "text-align": "center", 
                            "justify-content": "center",
                            "width": "100%",
                            "display": "block"
                        },
                        "nav-link-selected": {"background-color": "#8E24AA", "color": "white"} 
                    }
                )
            
            vulture_mode = False
            # 🟢 如果是投手，將禿鷹按鈕优雅地擺在膠囊正下方的右側，保持主選單的純粹置中
            if w_ptype == "投手" and fa_health != "🏥 傷兵 (IL / Out)":
                c_v1, c_v2 = st.columns([3, 1])
                with c_v2:
                    vulture_mode = st.toggle("🦅 啟動禿鷹模式", value=False, key="fa_vulture_toggle_v5")

            st.info(f"🟢 已排除 {len(owned_players)} 位被認領球員。")
            fa_data = (raw_data_h if w_ptype == "打者" else raw_data_p).copy()
            fa_data = fa_data[~fa_data['Player'].isin(owned_players)]
            
            if w_pos != "全部 (ALL)": 
                fa_data = fa_data[fa_data['Player'].isin(get_eligible_players(w_pos, raw_data_h, raw_data_p))]
                
            # 🟢 智能醫療防線：根據新膠囊按鈕狀態過濾 DataFrame
            if not fa_data.empty:
                if fa_health == "💪 能出賽 (Active)":
                    fa_data = fa_data[~fa_data['Player'].isin(combined_il_players)]
                elif fa_health == "🏥 傷兵 (IL / Out)":
                    fa_data = fa_data[fa_data['Player'].isin(combined_il_players)]

            if vulture_mode:
                st.success("🦅 **禿鷹雷達啟動！** 系統已為您剔除 ERA > 3.5 的不穩定因子，專注推薦具備「極高三振率」的佈局投手。當主力終結者輪休時，他們將接管第九局！")
                fa_data = fa_data[fa_data['Position'].astype(str).str.contains('RP', na=False)]
                fa_data = fa_data[(pd.to_numeric(fa_data.get('SV', 0), errors='coerce').fillna(0) < 10) & 
                                  (pd.to_numeric(fa_data.get('K/9', 0), errors='coerce').fillna(0) > 9.5) & 
                                  (pd.to_numeric(fa_data.get('ERA', 4.0), errors='coerce').fillna(4.0) < 3.5)]

            if not fa_data.empty:
                # 🔥 關鍵連動修正：每次上層 Form 提交後會 rerun，這裡重新動態封鎖最新狀態的傷兵名單
                # 確保點擊按鈕的瞬間，下方的表格會立刻將該球員抽離或放回！
                auto_il_players = scrape_real_il_from_web()
                false_il_players = set(st.session_state.get('fantasy_db', {}).get('false_il_players', []))
                combined_il_players = (auto_il_players - false_il_players).union(set(st.session_state.get('fantasy_db', {}).get('real_il_players', [])))

                # 🟢 智能動態過濾防線
                if fa_health == "💪 能出賽 (Active)":
                    fa_data = fa_data[~fa_data['Player'].isin(combined_il_players)]
                elif fa_health == "🏥 傷兵 (IL / Out)":
                    fa_data = fa_data[fa_data['Player'].isin(combined_il_players)]

                # 🔥 定義全域表格置中樣式 (表頭與內容強制置中)
                center_style = [
                    {'selector': 'th', 'props': [('text-align', 'center !important')]},
                    {'selector': 'td', 'props': [('text-align', 'center !important')]}
                ]
                
                # 🎨 專屬染色引擎：確保球員、球隊、守位都會閃耀大聯盟球隊專屬主色！
                def apply_team_colors(row):
                    styles = ['' for _ in row.index]
                    try: tc = get_team_color(row["Team"])[0]
                    except: tc = "#555"
                    for i, col in enumerate(row.index):
                        if col in ['Player', 'Team', 'Position']:
                            styles[i] = f'color: {tc} !important; font-weight: 900 !important;'
                    return styles
                
                # 🚨 總管指定防線：如果是看傷兵，直接乾淨顯示名單
               # 🚨 總管指定防線：如果是看傷兵，直接乾淨顯示名單，並實裝「守位獨立分流雷達」防止打者投手混淆！
                if fa_health == "🏥 傷兵 (IL / Out)":
                    st.warning("🤕 該批球員目前處於傷兵席，系統已自動屏蔽近期出賽數據、球場係數與進階積分預測。")
                    
                    # 🔍 守位正名引擎：同時掃描打者與投手大庫，精準抓出傷兵的真實身分與原始守位！
                    il_hitters = raw_data_h[raw_data_h['Player'].isin(combined_il_players)][['Player', 'Team', 'Position']]
                    il_pitchers = raw_data_p[raw_data_p['Player'].isin(combined_il_players)][['Player', 'Team', 'Position']]
                    
                    # 將兩者合併，形成 100% 守位正確的完全體總傷兵池
                    df_il_combined = pd.concat([il_hitters, il_pitchers]).drop_duplicates(subset=['Player']).reset_index(drop=True)
                    
                    # 🟢 再度根據總管目前切換的 w_ptype (打者/投手 選單) 進行正確的分流顯示
                    if w_ptype == "打者":
                        # 排除掉守備位置包含 SP, RP, P 的球員，確保打者傷兵頁面「純野手」
                        df_il_clean = df_il_combined[~df_il_combined['Position'].astype(str).str.contains(r'\b(SP|RP|P)\b', regex=True, na=False)].reset_index(drop=True)
                    else:
                        # 僅保留守備位置包含 SP, RP, P 的球員，確保投手傷兵頁面「純投手」
                        df_il_clean = df_il_combined[df_il_combined['Position'].astype(str).str.contains(r'\b(SP|RP|P)\b', regex=True, na=False)].reset_index(drop=True)

                    if not df_il_clean.empty:
                        df_il_clean.index += 1
                        
                        styled_il = df_il_clean.style \
                            .apply(apply_team_colors, axis=1) \
                            .set_properties(**{'text-align': 'center'}) \
                            .set_table_styles(center_style) \
                            .hide(axis='index')
                            
                        st.markdown(f"<div class='table-scroll-container'>{styled_il.to_html()}</div>", unsafe_allow_html=True)
                    else:
                        st.info(f"💡 目前【{w_ptype}】傷兵名單清空，無符合條件的成員。")
                else:
                    weights = st.session_state.fantasy_db[waiver_league][list(st.session_state.fantasy_db[waiver_league].keys())[0]].get("scoring", FANTASY_WEIGHTS)
                    
                    if "歷史" in timeframe:
                        factor = (7 if "7" in timeframe else (14 if "14" in timeframe else 30)) / 180.0
                        fa_data['Game'] = (extract_game_col(fa_data) * factor).clip(lower=1).astype(int)
                        fa_data['Custom_Score_Base'] = recalculate_custom_score(fa_data, w_ptype, weights)
                        fa_data['Total_Pts (區間總分)'] = (fa_data['Custom_Score_Base'] * factor).round(2)
                        fa_data['Avg_Pts (場均分)'] = (fa_data['Total_Pts (區間總分)'] / fa_data['Game']).round(2)
                        
                        display_df = fa_data.sort_values(by='Total_Pts (區間總分)', ascending=False).head(50).reset_index(drop=True)
                        display_df.index += 1
                        st.session_state.fa_display_df = display_df 
                        
                        show_cols = ['Player', 'Team', 'Position', 'Game', 'Total_Pts (區間總分)', 'Avg_Pts (場均分)']
                        
                        # 🎨 修正點 1：修改 apply_team_colors 的定義或使其具備最高優先權
                        # 為了讓海盜隊球員整排都變海盜黃，我們在 apply_team_colors 中已經鎖定了 Player/Team/Position
                        # 我們直接在這裡讓球隊染色強制覆蓋整行數據，消滅多餘的橘色！
                        def apply_team_colors_full(row):
                            styles = ['' for _ in row.index]
                            try: tc = get_team_color(row["Team"])[0]
                            except: tc = "#555"
                            # 🟢 將 if 欄位過濾拿掉，改為【無差別整排強制染色】，徹底切齊視覺！
                            for i in range(len(row.index)):
                                styles[i] = f'color: {tc} !important; font-weight: 900 !important;'
                            return styles

                        styled_fa = display_df[show_cols].style \
                            .apply(style_fantasy_pts, axis=0) \
                            .apply(color_rank_rows, axis=1) \
                            .apply(apply_team_colors_full, axis=1) \
                            .format(get_fmt_dict(display_df), na_rep="-") \
                            .set_properties(**{'text-align': 'center'}) \
                            .set_table_styles(center_style) \
                            .hide(axis='index')
                        
                        st.markdown(f"#### 📈 歷史戰力檢視 (Top 50 FA)")
                        st.markdown(f"<div class='table-scroll-container'>{styled_fa.to_html(escape=False)}</div>", unsafe_allow_html=True)
                    
                    else:
                        days = 7 if "7" in timeframe else 14
                        fa_data['Custom_Score_Base'] = recalculate_custom_score(fa_data, w_ptype, weights)
                        
                        def get_adv_proj(row):
                            random.seed(int(hashlib.md5(f"{row['Player']}_{datetime.now().isocalendar()[1]}_{days}".encode()).hexdigest(), 16))
                            opps = random.sample(AL_TEAMS + NL_TEAMS, 2 if days==7 else 4)
                            mod = 1.0
                            
                            platoon_tag = "⚖️ 數據平穩"
                            is_lefty = random.choice([True, False, False]) 
                            is_opp_rhp = random.choice([True, True, False]) 
                            
                            if w_ptype == '打者' and is_lefty and is_opp_rhp:
                                mod *= 1.18 
                                platoon_tag = "🔥 左打剋右投 (+18%)"
                            elif w_ptype == '打者' and not is_lefty and not is_opp_rhp:
                                mod *= 1.12
                                platoon_tag = "🔥 右打剋左投 (+12%)"
                            elif w_ptype == '投手' and float(row.get('K/9', 0)) > 10.5:
                                mod *= 1.15
                                platoon_tag = "⚔️ 頂級三振壓制 (+15%)"
                            
                            PARK_FACTORS = {
                                "Colorado Rockies": 1.12, "Cincinnati Reds": 1.08, "Boston Red Sox": 1.07,
                                "Texas Rangers": 1.05, "Atlanta Braves": 1.04, "Chicago White Sox": 1.03, 
                                "Los Angeles Angels": 1.02, "Houston Astros": 1.01, "Los Angeles Dodgers": 1.01, 
                                "New York Yankees": 1.00, "Philadelphia Phillies": 1.00, "Baltimore Orioles": 0.99, 
                                "Toronto Blue Jays": 0.99, "Chicago Cubs": 0.99, "Minnesota Twins": 0.98, 
                                "San Francisco Giants": 0.97, "Tampa Bay Rays": 0.97, "San Diego Padres": 0.96,
                                "New York Mets": 0.96, "Miami Marlins": 0.95, "Detroit Tigers": 0.95, 
                                "Oakland Athletics": 0.94, "Seattle Mariners": 0.92
                            }
                            
                            pf_messages = []
                            colored_opps = []
                            for o in opps:
                                pf = PARK_FACTORS.get(o, 1.00)
                                if w_ptype == '打者':
                                    mod *= pf
                                    if pf >= 1.04: pf_messages.append(f"<span style='color:#D32F2F; font-weight: bold;'>⛰️ {o} (+{int((pf-1)*100)}%)</span>")
                                    elif pf <= 0.96: pf_messages.append(f"<span style='color:#1976D2; font-weight: bold;'>🌊 {o} ({int((pf-1)*100)}%)</span>")
                                else:
                                    pit_pf = 2.0 - pf
                                    mod *= pit_pf
                                    if pf >= 1.04: pf_messages.append(f"<span style='color:#D32F2F; font-weight: bold;'>⛰️ {o} ({int((pit_pf-1)*100)}%)</span>")
                                    elif pf <= 0.96: pf_messages.append(f"<span style='color:#388E3C; font-weight: bold;'>🌊 {o} (+{int((pit_pf-1)*100)}%)</span>")

                                try: tc = get_team_color(o)[0]
                                except: tc = "#555"
                                colored_opps.append(f"<span style='color: {tc}; font-weight: bold;'>{o}</span>")
                                
                            pf_str = "<br>".join(set(pf_messages))
                            if pf_str:
                                platoon_tag += f"<br>{pf_str}"
                                
                            egp = max(1, (float(row.get('AB', 0))/4.2) if w_ptype=='打者' else (float(row.get('IP', 0))/5.0))
                            g = random.choice([5,6,7]) if w_ptype=='打者' else (random.choices([1,2],[0.8,0.2])[0] if 'SP' in str(row['Position']) else random.choice([2,3,4]))
                            base = (row['Custom_Score_Base'] / egp * g)
                            
                            return g, "<br>".join(colored_opps), platoon_tag, round(base, 2), round(base*mod, 2)
                        
                        with st.spinner("啟動進階對戰預測引擎..."):
                            res = fa_data.apply(get_adv_proj, axis=1)
                            fa_data['預計出賽(G)'], fa_data['對手難易度'], fa_data['血性優勢 '], fa_data['基礎'], fa_data['🔥 進階'] = zip(*res)
                            if w_ptype == '投手': 
                                fa_data['預計出賽(G)'] = fa_data.apply(lambda r: f"⭐️ 雙先發 ({r['預計出賽(G)']})" if 'SP' in str(r['Position']) and r['預計出賽(G)']>=2 and days==7 else r['預計出賽(G)'], axis=1)
                                
                            display_df = fa_data.sort_values(by='🔥 進階', ascending=False).head(50).reset_index(drop=True)
                            display_df.index += 1
                            st.session_state.fa_display_df = display_df 
                            
                            show_cols = ['Player', 'Team', 'Position', '預計出賽(G)', '對手難易度', '血性優勢 ', '基礎', '🔥 進階']
                            
                           # 🎨 修正點 2：修改 lambda 渲染，讓球隊顏色直接統治整排欄位，不再區分欄位！
                            styled_proj = display_df[show_cols].style \
                                .apply(lambda r: [
                                    # 🟢 不再只限定 Player/Team/Position，讓整排數據通通完美染上該球員的球隊色！
                                    f'color: {get_team_color(r["Team"])[0]} !important; font-weight: 900 !important;'
                                    for _ in r.index
                                ], axis=1) \
                                .format(get_fmt_dict(display_df), na_rep="-").set_properties(**{'text-align': 'center'}).set_table_styles(center_style).hide(axis='index')
                                
                            st.markdown(f"#### 🔮 雙引擎賽程對戰預測 (未來 {days} 天 Top 50 FA)")
                            st.markdown(f"<div class='table-scroll-container'>{styled_proj.to_html(escape=False)}</div>", unsafe_allow_html=True)
            else:
                st.info("無符合條件的 FA 球員。")


    if selected_fantasy == "⚖️ 雙星對決":
        st.markdown("### ⚖️ 雙星對決")
        if 'fa_display_df' in st.session_state and not st.session_state.fa_display_df.empty:
            display_df = st.session_state.fa_display_df
            if len(display_df) > 1:
                c1, c2 = st.columns(2)
                fa1 = c1.selectbox("目標 A", display_df['Player'], index=0, key="fa_cmp_1")
                fa2 = c2.selectbox("目標 B", display_df['Player'], index=1, key="fa_cmp_2")
                
                d1, d2 = display_df[display_df['Player'] == fa1].iloc[0], display_df[display_df['Player'] == fa2].iloc[0]
                tc1, tc2 = get_team_color(d1['Team'])[0], get_team_color(d2['Team'])[0]
                st.markdown(f"#### 📊 <span style='color:{tc1};'>{fa1}</span> vs <span style='color:{tc2};'>{fa2}</span>", unsafe_allow_html=True)
                
                metrics = ['🔥 進階', '基礎', '預計出賽(G)'] if '🔥 進階' in display_df.columns else ['Total_Pts (區間總分)', 'Avg_Pts (場均分)', 'Game']
                for m in metrics:
                    cm1, cm2 = st.columns(2)
                    v1, v2 = d1[m], d2[m]
                    try:
                        n1, n2 = float(str(v1).replace('⭐️ 雙先發 (','').replace(')','')), float(str(v2).replace('⭐️ 雙先發 (','').replace(')',''))
                        c_a, c_b = ("#00E676", "#A9A9A9") if n1 > n2 else (("#A9A9A9", "#00E676") if n2 > n1 else ("#555", "#555"))
                    except: c_a = c_b = "#555"
                        
                    cm1.markdown(f"<div><b style='font-size: clamp(20px, 1.6vw, 28px);'>{m}</b><br><span style='font-size: clamp(38px, 3.2vw, 54px); color:{c_a}; font-weight:900;'>{v1}</span></div>", unsafe_allow_html=True)
                    if fa1 != fa2: cm2.markdown(f"<div><b style='font-size: clamp(20px, 1.6vw, 28px);'>{m}</b><br><span style='font-size: clamp(38px, 3.2vw, 54px); color:{c_b}; font-weight:900;'>{v2}</span></div>", unsafe_allow_html=True)
                    st.divider()
        else: st.warning("請先在自由市場生成名單！")

    if selected_fantasy == "🤝 交易模擬器":
        st.markdown("### 🤝 夢幻交易評估模擬器 (Trade Analyzer)")
        st.caption("利用 AI 總管的 Z-Score 陣容診斷模型，預測這筆交易對您球隊的戰力衝擊！")
        
        valid_leagues = [lg for lg in st.session_state.fantasy_db.keys() if lg not in ['external_taken', 'real_il_players']]
        if not valid_leagues:
            st.warning("請先到「📝 夢幻球隊」建立您的聯盟與陣容，才能啟動交易模擬器！")
        else:
            t_col1, t_col2 = st.columns([1, 2])
            trade_league = t_col1.selectbox("操作聯盟", valid_leagues, key="trade_league_select")
            teams_in_league = list(st.session_state.fantasy_db[trade_league].keys())
            
            my_team = t_col2.selectbox("👑 您的球隊 (Team A)", teams_in_league, key="trade_my_team")
            
            other_teams = [t for t in teams_in_league if t != my_team]
            trade_partners = ["🛒 自由市場 (FA)"] + other_teams
            partner_team = t_col2.selectbox("🔄 交易對象 (Team B / FA)", trade_partners, key="trade_partner_team")
            
            my_roster_dict = st.session_state.fantasy_db[trade_league][my_team]["roster"].get(today_str, {})
            my_players = [p for p in my_roster_dict.values() if p]
            
            if partner_team == "🛒 自由市場 (FA)":
                owned_players = set()
                for tm, tdata in st.session_state.fantasy_db[trade_league].items():
                    for p in tdata["roster"].get(today_str, {}).values():
                        if p: owned_players.add(p)
                for p in st.session_state.fantasy_db.get('external_taken', []):
                    owned_players.add(p)
                partner_players = [p for p in all_players if p not in owned_players]
            else:
                partner_roster_dict = st.session_state.fantasy_db[trade_league][partner_team]["roster"].get(today_str, {})
                partner_players = [p for p in partner_roster_dict.values() if p]

            st.divider()
            
            col_give, col_receive = st.columns(2)
            give_players = col_give.multiselect("📤 您要送出的球員 (Give)", my_players, key="trade_give")
            receive_players = col_receive.multiselect("📥 您將獲得的球員 (Receive)", partner_players, key="trade_receive")
            
            if st.button("⚖️ 執行交易評估 (Analyze Trade)", use_container_width=True):
                if not give_players and not receive_players:
                    st.error("請至少選擇一位送出或獲得的球員！")
                elif not my_players:
                    st.error("您的球隊目前沒有陣容名單，無法進行評估！")
                else:
                    simulated_roster = [p for p in my_players if p not in give_players] + receive_players
                    
                    z_before = calc_z_scores_for_roster(my_players)
                    z_after = calc_z_scores_for_roster(simulated_roster)
                    
                    categories = list(z_before.keys())
                    vals_before = list(z_before.values())
                    vals_after = list(z_after.values())
                    
                    delta_total = sum(vals_after) - sum(vals_before)
                    
                    fig_trade = go.Figure()
                    fig_trade.add_trace(go.Scatterpolar(
                        r=vals_before + [vals_before[0]], theta=categories + [categories[0]],
                        fill='toself', name='交易前 (Current)', line_color='#A9A9A9', fillcolor='rgba(169, 169, 169, 0.4)'
                    ))
                    fig_trade.add_trace(go.Scatterpolar(
                        r=vals_after + [vals_after[0]], theta=categories + [categories[0]],
                        fill='toself', name='交易後 (Projected)', line_color='#00E676' if delta_total >= 0 else '#FF5252', 
                        fillcolor='rgba(0, 230, 118, 0.4)' if delta_total >= 0 else 'rgba(255, 82, 82, 0.4)'
                    ))
                    fig_trade.update_layout(polar=dict(radialaxis=dict(range=[0, 100], tickfont=dict(size=10))), height=400, margin=dict(l=30, r=30, t=30, b=30))
                    
                    st.markdown("### 📈 交易戰力衝擊雷達圖")
                    st.plotly_chart(fig_trade, use_container_width=True, key="trade_analyzer_radar_chart")
                    
                    if delta_total > 40: grade, color, verdict = "A+", "#00E676", "搶劫級交易！對手虧大了！"
                    elif delta_total > 15: grade, color, verdict = "A", "#00C853", "極佳的補強，陣容明顯升級。"
                    elif delta_total > 5: grade, color, verdict = "B+", "#2196F3", "合理的交易，戰力微幅上升。"
                    elif delta_total > -5: grade, color, verdict = "C", "#FF9800", "戰力平盤，端看您的戰術需求。"
                    elif delta_total > -25: grade, color, verdict = "D", "#FF5252", "戰力受損，這筆交易您吃虧了。"
                    else: grade, color, verdict = "F", "#D32F2F", "災難級交易！強烈建議取消！"
                    
                    deltas = {cat: z_after[cat] - z_before[cat] for cat in categories}
                    max_gain_cat = max(deltas, key=deltas.get)
                    max_loss_cat = min(deltas, key=deltas.get)
                    
                    st.markdown(f"""
                    <div style="display: flex; background-color: #f9f9f9; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 8px rgba(0,0,0,0.1); margin-top: 10px;">
                        <div style="background-color: {color}; width: 120px; display: flex; align-items: center; justify-content: center; flex-direction: column; padding: 20px;">
                            <span style="color: white; font-size: 14px; font-weight: bold;">AI 交易評級</span>
                            <span style="color: white; font-size: 48px; font-weight: 900;">{grade}</span>
                        </div>
                        <div style="padding: 20px; flex: 1;">
                            <h4 style="margin-top: 0; color: #333;">{verdict}</h4>
                            <p style="margin: 5px 0; font-size: 16px;">🟢 <b>最大得益：</b> 您的 <span style="color:#00E676; font-weight:bold;">{max_gain_cat}</span> 獲得了最大幅度的提升 (+{deltas[max_gain_cat]:.1f})。</p>
                            <p style="margin: 5px 0; font-size: 16px;">🔴 <b>最大犧牲：</b> 您將會失去部分的 <span style="color:#FF5252; font-weight:bold;">{max_loss_cat}</span> 能力 ({deltas[max_loss_cat]:.1f})。</p>
                            <p style="margin-top: 10px; color: #666; font-size: 14px;"><i>*AI 總管建議：如果這項犧牲正好是您原本「戰力溢出」的項目，那這筆交易將會非常值得！</i></p>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

    if selected_fantasy == "🌟 大物雷達":
        st.markdown("### 🌟 Fantasy 農場大物雷達 (NA Stash Tracker)")
        st.caption("AI 總管為您從 3A/2A 農場中抓出即將升上大聯盟的「高天賦新秀」，幫助您提前放進 NA 名單囤積！")
        
        c1, c2 = st.columns(2)
        milb_level = c1.selectbox("選擇小聯盟層級", ["AAA", "AA"], key="fan_milb_level")
        # 🔥 大物雷達專屬：升級為置中高質感膠囊切換鈕
        with c2:
            p_type_prospect = option_menu(
                None, ["打者", "投手"], icons=["person-arms-up", "bullseye"],
                default_index=0,
                orientation="horizontal",
                key="prospect_ptype_menu", # 🛡️ 獨立 key 預防 Streamlit 重複元件報錯
                styles={
                    "container": {"padding": "0!important", "margin": "0", "background-color": "#F0F2F6", "border-radius": "15px", "border": "none"},
                    "nav-link": {"font-size": "14px", "padding": "5px", "font-weight": "bold", "color": "#555"},
                    "nav-link-selected": {"background-color": "#0C2340", "color": "white"}
                }
            )

        lvl_map = {"AAA": 11, "AA": 12}
        level_id = lvl_map[milb_level]

        with st.spinner(f"正在連線 {milb_level} 數據庫並執行 AI 球探分析..."):
            year = datetime.now().year
            milb_df = fetch_milb_stats(year, level_id, p_type_prospect)
            
            if milb_df is not None and not milb_df.empty:
                scout_data = []
                for _, row in milb_df.iterrows():
                    grades = calculate_scout_grades(row, p_type_prospect, milb_level)
                    eta, stash = estimate_fantasy_stash(grades['FV'], milb_level)
                    
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
                            "總管建議": stash
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
                    stash_list = ["全部"] + list(prospect_df["總管建議"].unique())
                    
                    sel_eta = f_col1.selectbox("📅 過濾預計升上時間", eta_list, key="fan_filter_eta")
                    sel_stash = f_col2.selectbox("🤖 過濾總管建議", stash_list, key="fan_filter_stash")
                    
                    if sel_eta != "全部":
                        prospect_df = prospect_df[prospect_df["預計升上"] == sel_eta]
                    if sel_stash != "全部":
                        prospect_df = prospect_df[prospect_df["總管建議"] == sel_stash]
                        
                    if prospect_df.empty:
                        st.info("⚠️ 篩選後無符合條件的球員。")
                    else:
                        def style_fantasy_prospects(row):
                            try: tc = get_team_color(row['所屬母隊'])[0]
                            except: tc = "#555" 
                            
                            # 預設整列都是母隊主色
                            styles = [f'color: {tc} !important; font-weight: 900 !important;'] * len(row)
                            
                            for i, col in enumerate(row.index):
                                val = row[col]
                                
                                if col == '球探評分 (FV)':
                                    if val >= 65: styles[i] = 'color: white !important; background-color: #D32F2F !important; font-weight: bold;'
                                    elif val >= 55: styles[i] = 'color: white !important; background-color: #FF9800 !important; font-weight: bold;'
                                    else: styles[i] = 'color: white !important; background-color: #2196F3 !important; font-weight: bold;'
                                elif col == '總管建議':
                                    if '🔥' in str(val): styles[i] = 'color: white !important; background-color: #D32F2F !important; font-weight: bold;'
                                    elif '👀' in str(val): styles[i] = 'color: white !important; background-color: #FF9800 !important; font-weight: bold;'
                                    elif '⏳' in str(val): styles[i] = 'color: white !important; background-color: #9E9E9E !important; font-weight: bold;'
                                
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

                        st.markdown(f"#### 📋 值得放入 NA (Not Active) 囤積的農場名單")
                        
                        format_dict = {'OPS': '{:.3f}', 'HR': '{:.0f}'} if p_type_prospect == '打者' else {'ERA': '{:.2f}'}
                        
                        display_df = prospect_df.drop(columns=['位置'])
                        
                        styled_prospect_df = display_df.style.apply(style_fantasy_prospects, axis=1).format(format_dict).hide(axis='index')
                        html_str = styled_prospect_df.to_html(classes="prospect-table")
                        
                        custom_css = """
                        <style>
                        .prospect-table { width: 100%; border-collapse: collapse; table-layout: auto; }
                        .prospect-table th, .prospect-table td { text-align: center; vertical-align: middle; padding: 6px; }
                        .prospect-table td:nth-child(1), .prospect-table th:nth-child(1) { width: 100px !important; min-width: 100px !important; text-align: left; white-space: normal; word-wrap: break-word; }
                        .prospect-table td:nth-last-child(1), .prospect-table th:nth-last-child(1) { min-width: 160px !important; font-size: 1.1em; }
                        .prospect-table thead th { position: sticky; top: 0; background-color: #f8f9fa; z-index: 10; box-shadow: 0 2px 2px -1px rgba(0, 0, 0, 0.4); }
                        </style>
                        """
                        st.markdown(f"<div style='max-height: 450px; overflow-y: auto; border: 1px solid #e0e0e0; border-radius: 8px;'>{custom_css}{html_str}</div>", unsafe_allow_html=True)
                        
                        st.divider()
                        
                        st.markdown("### 🕷️ 大物專屬戰力體檢 (Scouting Radar)")
                        selected_prospect = st.selectbox("選擇球員查看雷達圖", prospect_df['球員'].tolist(), key="fantasy_prospect_radar_select")
                        
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
                            
                            c_radar.plotly_chart(fig, use_container_width=True, key="fantasy_prospect_radar_chart")
                            
                            with c_info:
                                st.markdown(f"<h3 style='color: {radar_color}; margin-bottom: 0;'>{selected_prospect}</h3>", unsafe_allow_html=True)
                                
                                pos_display = p_data['位置']
                                pos_text = f" | **位置：** {pos_display}" if pos_display not in ['UNK', 'Unknown', '-', 'nan', ''] else ""
                                st.markdown(f"**所屬球隊：** {p_data['所屬母隊']} ({milb_level}){pos_text}")
                                
                                st.markdown(f"**球探評分 (FV)：** <span style='font-size: 24px; font-weight: 900; color: {radar_color};'>{p_data['球探評分 (FV)']}</span>", unsafe_allow_html=True)
                                
                                st.markdown(f"""
                                <div style="background-color: #f5f5f5; padding: 15px; border-left: 5px solid {radar_color}; border-radius: 5px; margin-top: 15px;">
                                    <b>🚀 預計升上：</b> {p_data['預計升上']}<br><br>
                                    <b>🤖 總管建議：</b> {p_data['總管建議']}<br>
                                    <i>該球員目前在小聯盟展現出 {p_data['球探評分 (FV)']} 分等級的宰制力，請根據您的聯盟深度，決定是否要提前放進 NA 名單！</i>
                                </div>
                                """, unsafe_allow_html=True)
            else:
                st.warning(f"⚠️ 無法取得 {year} 賽季 {milb_level} 的資料，請稍後再試。")
    
    if selected_fantasy == "🧠 專家預警":
        st.markdown("### 🧠 AI 總管深度分析 (Expert Warning System)")
        st.caption("透過進階數據(xBA, xERA, Chase%)剝開運氣的糖衣，精準找出隱藏的炸彈與鑽石！")
        
        c_mode1, c_mode2 = st.columns([1, 1]) # 改為 1:1 對稱排版
        
        with c_mode1:
            expert_mode = option_menu(
                None, ["打者運氣診斷", "投手衰退風險"], 
                icons=["person-arms-up", "bullseye"],
                default_index=0,
                orientation="horizontal",
                key="exp_mode_menu", # 🛡️ 必備的獨立身分證
                styles={
                    "container": {"padding": "0!important", "margin": "0", "background-color": "#F0F2F6", "border-radius": "15px", "border": "none"},
                    "nav-link": {"font-size": "15px", "padding": "5px", "font-weight": "bold", "color": "#555"},
                    "nav-link-selected": {"background-color": "#8E24AA", "color": "white"} # AI 專家紫色
                }
            )
            
        with c_mode2:
            expert_target = option_menu(
                None, ["自由市場 (FA)", "我的陣容名單"], 
                icons=["cart", "clipboard-data"],
                default_index=0,
                orientation="horizontal",
                key="exp_target_menu", # 🛡️ 必備的獨立身分證
                styles={
                    "container": {"padding": "0!important", "margin": "0", "background-color": "#F0F2F6", "border-radius": "15px", "border": "none"},
                    "nav-link": {"font-size": "15px", "padding": "5px", "font-weight": "bold", "color": "#555"},
                    "nav-link-selected": {"background-color": "#0C2340", "color": "white"} # 沉穩深藍色
                }
            )

        # 準備資料與名單
        leagues = [lg for lg in st.session_state.fantasy_db.keys() if lg not in ['external_taken', 'real_il_players']]
        
        owned_players = set()
        my_players = []
        if leagues:
            for tm, tdata in st.session_state.fantasy_db[leagues[0]].items():
                for p in tdata.get("roster", {}).get(today_str, {}).values():
                    if p: owned_players.add(p)
            my_team_name = list(st.session_state.fantasy_db[leagues[0]].keys())[0]
            my_players = [p for p in st.session_state.fantasy_db[leagues[0]][my_team_name].get("roster", {}).get(today_str, {}).values() if p]

        # 🔥 新增：專家系統專屬熱圖函式 (自動判斷 xERA, Chase% 越低越好)
        def style_expert_heatmap(s):
            styles = [''] * len(s)
            if s.name not in ['BA', 'xBA', 'BABIP', 'Chase%', 'ERA', 'xERA', 'K%', 'IP']: return styles
            try:
                s_num = pd.to_numeric(s, errors='coerce').dropna()
                if s_num.empty: return styles
                
                lower_is_better = ['ERA', 'xERA', 'Chase%']
                if s.name in lower_is_better:
                    q_good, q_ok, q_bad = s_num.quantile(0.2), s_num.quantile(0.5), s_num.quantile(0.8)
                    for i, val in enumerate(s):
                        try:
                            v = float(val)
                            if pd.isna(v): continue
                            if v <= q_good: styles[i] = 'color: #C62828 !important; background-color: #FFEBEE !important; font-weight: 900 !important;'
                            elif v <= q_ok: styles[i] = 'color: #E65100 !important; background-color: #FFF3E0 !important; font-weight: 900 !important;'
                            elif v >= q_bad: styles[i] = 'color: #1565C0 !important; background-color: #E3F2FD !important; font-weight: 900 !important;'
                        except: pass
                else:
                    q_good, q_ok, q_bad = s_num.quantile(0.8), s_num.quantile(0.5), s_num.quantile(0.2)
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

        if "打者" in expert_mode:
            st.markdown("#### ⚾ 打者揮擊決策與真實運氣模型 (Luck Regressor)")
            df_h = raw_data_h.copy()
            if "FA" in expert_target: df_h = df_h[~df_h['Player'].isin(owned_players)]
            else: df_h = df_h[df_h['Player'].isin(my_players)]
            
            if not df_h.empty:
                with st.spinner("AI 運算打者本質中..."):
                    res = df_h.apply(analyze_batter_luck, axis=1)
                    df_h['AI 判定'], df_h['總管診斷報告'] = zip(*res)
                    
                    show_c = ['Player', 'Team'] + [c for c in ['BA', 'xBA', 'BABIP', 'Chase%'] if c in df_h.columns] + ['AI 判定', '總管診斷報告']
                    df_show = df_h[show_c].copy()
                    
                    df_show['Sort_Key'] = df_show['AI 判定'].apply(lambda x: 1 if '買進' in x else (2 if '賣出' in x else 3))
                    df_show = df_show.sort_values('Sort_Key').drop(columns=['Sort_Key']).reset_index(drop=True)
                    df_show.index += 1

                    # 🔥 新增：打者專屬篩選器
                    f_col1, f_col2 = st.columns(2)
                    sel_ai = f_col1.selectbox("🤖 篩選 AI 判定", ["全部"] + list(df_show['AI 判定'].unique()), key="exp_h_ai")
                    sel_report = f_col2.selectbox("📄 篩選診斷報告", ["全部", "擊球極佳", "假性高潮", "選球眼極佳", "盲劍客危機", "BABIP過高"], key="exp_h_rep")

                    if sel_ai != "全部": df_show = df_show[df_show['AI 判定'] == sel_ai]
                    if sel_report != "全部": df_show = df_show[df_show['總管診斷報告'].str.contains(sel_report, na=False)]
                    
                    if not df_show.empty:
                        def style_expert_bat(row):
                            styles = ['' for _ in row.index]
                            for i, col in enumerate(row.index):
                                val = str(row[col])
                                
                                # 🔥 修正核心：將 Player 與 Team 的球隊染色移到第一順位，徹底杜絕高光越位！
                                if col in ['Player', 'Team']: 
                                    try: tc = get_team_color(row['Team'])[0]
                                    except: tc = "#555"
                                    styles[i] = f'color: {tc} !important; font-weight: 900 !important;'
                                    
                                # 其餘診斷高光順移至後方，只服務數據欄位與報告欄位
                                elif '🚀' in val: styles[i] = 'color: #1565C0 !important; background-color: #E3F2FD !important; font-weight: 900;'
                                elif '📉' in val or '🚨' in val: styles[i] = 'color: #C62828 !important; background-color: #FFEBEE !important; font-weight: 900;'
                                elif col == '總管診斷報告': styles[i] = 'text-align: left !important; font-size: 0.9em; line-height: 1.4;'
                            return styles
                            
                        # 🔥 加上數據高光引擎 (apply style_expert_heatmap)
                        styled_df = df_show.style.apply(style_expert_heatmap, axis=0).apply(style_expert_bat, axis=1).format(get_fmt_dict(df_show)).hide(axis='index')
                        st.markdown(f"<div class='table-scroll-container'>{styled_df.to_html(escape=False)}</div>", unsafe_allow_html=True)
                    else: st.info("無符合篩選條件的球員。")
            else: st.info("無名單可供分析。")
            
        else:
            st.markdown("#### 🛡️ 投手疲勞與衰退風險模型 (Injury/Fatigue Risk)")
            df_p = raw_data_p.copy()
            if "FA" in expert_target: df_p = df_p[~df_p['Player'].isin(owned_players)]
            else: df_p = df_p[df_p['Player'].isin(my_players)]
            
            if not df_p.empty:
                with st.spinner("AI 偵測投手手臂狀態中..."):
                    res = df_p.apply(analyze_pitcher_risk, axis=1)
                    df_p['AI 判定'], df_p['總管診斷報告'] = zip(*res)
                    
                    show_c = ['Player', 'Team'] + [c for c in ['ERA', 'xERA', 'K%', 'IP'] if c in df_p.columns] + ['AI 判定', '總管診斷報告']
                    df_show = df_p[show_c].copy()
                    
                    df_show['Sort_Key'] = df_show['AI 判定'].apply(lambda x: 1 if '風險' in x else (2 if '警示' in x else 3))
                    df_show = df_show.sort_values('Sort_Key').drop(columns=['Sort_Key']).reset_index(drop=True)
                    df_show.index += 1

                    # 🔥 新增：投手專屬篩選器
                    f_col1, f_col2 = st.columns(2)
                    sel_ai = f_col1.selectbox("🤖 篩選 AI 判定", ["全部"] + list(df_show['AI 判定'].unique()), key="exp_p_ai")
                    sel_report = f_col2.selectbox("📄 篩選診斷報告", ["全部", "運氣過佳", "運氣不佳", "三振能力下滑", "手臂疲勞警告"], key="exp_p_rep")

                    if sel_ai != "全部": df_show = df_show[df_show['AI 判定'] == sel_ai]
                    if sel_report != "全部": df_show = df_show[df_show['總管診斷報告'].str.contains(sel_report, na=False)]
                    
                    if not df_show.empty:
                        # 🟢 總管最高優先權防線：強制定點染色，不受任何狀態標籤干擾！
                        def style_expert_pit(row):
                            styles = ['' for _ in row.index]
                            for i, col in enumerate(row.index):
                                val = str(row[col])
                                
                                # 🔥 修正核心：將 Player 與 Team 的球隊染色移到第一順位，徹底杜絕橘色越位！
                                if col in ['Player', 'Team']: 
                                    try: tc = get_team_color(row['Team'])[0]
                                    except: tc = "#555"
                                    styles[i] = f'color: {tc} !important; font-weight: 900 !important;'
                                    
                                # 其餘診斷高光順移至後方，只服務數據欄位與報告欄位
                                elif '🔴' in val: styles[i] = 'color: #C62828 !important; background-color: #FFEBEE !important; font-weight: 900;'
                                elif '🟡' in val: styles[i] = 'color: #E65100 !important; background-color: #FFF3E0 !important; font-weight: 900;'
                                elif col == '總管診斷報告': styles[i] = 'text-align: left !important; font-size: 0.9em; line-height: 1.4;'
                            return styles
                            
                        # 🔥 加上數據高光引擎 (apply style_expert_heatmap)
                        styled_df = df_show.style.apply(style_expert_heatmap, axis=0).apply(style_expert_pit, axis=1).format(get_fmt_dict(df_show)).hide(axis='index')
                        st.markdown(f"<div class='table-scroll-container'>{styled_df.to_html(escape=False)}</div>", unsafe_allow_html=True)
                    else: st.info("無符合篩選條件的球員。")
            else: st.info("無名單可供分析。")
