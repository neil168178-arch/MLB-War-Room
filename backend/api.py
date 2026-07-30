from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz
import pybaseball
from pybaseball import statcast_batter_expected_stats, statcast_pitcher_expected_stats
from pybaseball import statcast_batter_exitvelo_barrels, statcast_pitcher_exitvelo_barrels
from functools import lru_cache
import random  
from pydantic import BaseModel
from typing import List, Optional
class TradeRequest(BaseModel):
    give_players: List[str]
    receive_players: List[str]
# 💡 貼在這裡：接收前端修改球員資料 (包含實際分數) 的請求格式
class UpdatePlayerRequest(BaseModel):
    name: str
    slot: Optional[str] = None
    pos: Optional[str] = None
    real_pts: Optional[float] = None
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ==========================================
# ⚾ 棒球專屬：MLB 局數 (IP) 統一解析引擎
# ==========================================
def parse_innings(ip_val):
    """
    將 MLB 的特殊局數格式 (如 '5.1', '5.2') 轉換為精確數值。
    回傳: (ip_math, outs) -> (用於計算的精確小數, 實際總出局數)
    範例: '5.2' -> (5.666666666666667, 17)
    """
    if ip_val is None or ip_val == '-' or ip_val == '':
        return 0.0, 0
    
    ip_str = str(ip_val).strip()
    try:
        if '.' in ip_str:
            parts = ip_str.split('.')
            whole = int(parts[0]) if parts[0] else 0
            frac = int(parts[1])
            
            # .1 代表 1/3 局 (1個出局數), .2 代表 2/3 局 (2個出局數)
            if frac == 1:
                return (whole + 1/3.0), (whole * 3 + 1)
            elif frac == 2:
                return (whole + 2/3.0), (whole * 3 + 2)
            else:
                # 容錯處理 (例如 '5.0' 或異常資料)
                return float(ip_str), (whole * 3)
        else:
            whole = int(ip_str)
            return float(whole), (whole * 3)
    except ValueError:
        return 0.0, 0
# --- ⚾ Roster 引擎核心：球隊 ID 對照表 ---
MLB_TEAM_IDS = {
    # 3 字母縮寫 (將 ATH 放前面，確保畫面優先顯示新版縮寫)
    "LAD": 119, "NYY": 147, "BOS": 111, "HOU": 117, "ATL": 144, "PHI": 143,
    "NYM": 121, "TOR": 141, "BAL": 110, "TEX": 140, "SEA": 136, "SD": 135,
    "CHC": 112, "CIN": 113, "MIN": 142, "CLE": 114, "TB": 139, "MIL": 158,
    "SF": 137, "ARI": 109, "MIA": 146, "DET": 116, "STL": 138, "PIT": 134,
    "KC": 118, "CWS": 145, "COL": 115, "WSH": 120, "ATH": 133, "OAK": 133, "LAA": 108,
    
    # 官方全稱 (新增去城市化的 Athletics)
    "Los Angeles Dodgers": 119, "New York Yankees": 147, "Boston Red Sox": 111,
    "Houston Astros": 117, "Atlanta Braves": 144, "Philadelphia Phillies": 143,
    "New York Mets": 121, "Toronto Blue Jays": 141, "Baltimore Orioles": 110,
    "Texas Rangers": 140, "Seattle Mariners": 136, "San Diego Padres": 135,
    "Chicago Cubs": 112, "Cincinnati Reds": 113, "Minnesota Twins": 142,
    "Detroit Tigers": 116, "Cleveland Guardians": 114, "Chicago White Sox": 145,
    "Kansas City Royals": 118, "Los Angeles Angels": 108, 
    "Athletics": 133, "Oakland Athletics": 133,
    "Tampa Bay Rays": 139, "Miami Marlins": 146, "Washington Nationals": 120,
    "Milwaukee Brewers": 158, "St. Louis Cardinals": 138, "Pittsburgh Pirates": 134,
    "Arizona Diamondbacks": 109, "Colorado Rockies": 115, "San Francisco Giants": 137
}
# ⚾ 完整 30 支球隊真實 Park Factors (球場環境因子)
PARK_FACTORS = {
    "COL": {"OPS": 1.15, "HR": 1.12, "ERA": 0.85, "desc": "高海拔極端打者天堂"},
    "CIN": {"OPS": 1.08, "HR": 1.20, "ERA": 0.92, "desc": "小巧球場，極易擊出全壘打"},
    "BOS": {"OPS": 1.06, "HR": 0.98, "ERA": 0.94, "desc": "綠色怪物極度有利二壘安打"},
    "CWS": {"OPS": 1.05, "HR": 1.10, "ERA": 0.95, "desc": "保證率球場易產全壘打"},
    "PHI": {"OPS": 1.05, "HR": 1.12, "ERA": 0.95, "desc": "打者友善的市民銀行球場"},
    "NYY": {"OPS": 1.04, "HR": 1.15, "ERA": 0.96, "desc": "右外野短牆拉打天堂"},
    "ATL": {"OPS": 1.04, "HR": 1.08, "ERA": 0.96, "desc": "偏向打者的 Truist Park"},
    "TEX": {"OPS": 1.03, "HR": 1.05, "ERA": 0.97, "desc": "全球人壽球場略偏打者"},
    "LAD": {"OPS": 1.02, "HR": 1.05, "ERA": 0.98, "desc": "道奇體育場略偏打者"},
    "TOR": {"OPS": 1.02, "HR": 1.04, "ERA": 0.98, "desc": "羅傑斯中心略有利打者"},
    "LAA": {"OPS": 1.02, "HR": 1.08, "ERA": 0.98, "desc": "天使球場全壘打率偏高"},
    "HOU": {"OPS": 1.01, "HR": 1.02, "ERA": 0.99, "desc": "美粒果球場中性偏打"},
    "MIN": {"OPS": 1.01, "HR": 1.01, "ERA": 0.99, "desc": "標靶球場標準中性"},
    "MIL": {"OPS": 1.01, "HR": 1.04, "ERA": 0.99, "desc": "釀酒人主場中性偏打"},
    "ARI": {"OPS": 1.00, "HR": 0.98, "ERA": 1.00, "desc": "大通體育場標準中性"},
    "WSH": {"OPS": 1.00, "HR": 1.00, "ERA": 1.00, "desc": "國民球場標準中性"},
    "CHC": {"OPS": 1.00, "HR": 1.02, "ERA": 1.00, "desc": "瑞格利球場受風向影響大"},
    "BAL": {"OPS": 0.97, "HR": 0.88, "ERA": 1.03, "desc": "左外野後移變為偏投手球場"},
    "KC":  {"OPS": 0.98, "HR": 0.85, "ERA": 1.02, "desc": "考夫曼球場廣闊不利全壘打"},
    "CLE": {"OPS": 0.98, "HR": 0.95, "ERA": 1.02, "desc": "進步球場略偏投手"},
    "STL": {"OPS": 0.97, "HR": 0.92, "ERA": 1.03, "desc": "布希體育場略偏投手"},
    "PIT": {"OPS": 0.97, "HR": 0.90, "ERA": 1.03, "desc": "PNC球場偏向投手"},
    "TB":  {"OPS": 0.96, "HR": 0.94, "ERA": 1.04, "desc": "純品康納室內球場偏投手"},
    "MIA": {"OPS": 0.96, "HR": 0.92, "ERA": 1.04, "desc": "馬林魚主場偏向投手"},
    "NYM": {"OPS": 0.96, "HR": 0.95, "ERA": 1.04, "desc": "花旗球場偏向投手"},
    "DET": {"OPS": 0.95, "HR": 0.88, "ERA": 1.05, "desc": "克邁利卡廣闊外野有利投手"},
    "SF":  {"OPS": 0.94, "HR": 0.85, "ERA": 1.06, "desc": "甲骨文球場極度偏投手"},
    "OAK": {"OPS": 0.94, "HR": 0.88, "ERA": 1.06, "desc": "極端偏投手"},
    "ATH": {"OPS": 0.94, "HR": 0.88, "ERA": 1.06, "desc": "極端偏投手"},
    "SD":  {"OPS": 0.94, "HR": 0.90, "ERA": 1.06, "desc": "教士沛可球場重投手"},
    "SEA": {"OPS": 0.92, "HR": 0.88, "ERA": 1.08, "desc": "海風阻擋極端投手天堂"},
}
TEAM_MAP = {
    "Arizona Diamondbacks": "ARI", "Atlanta Braves": "ATL", "Baltimore Orioles": "BAL", "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC", "Chicago White Sox": "CWS", "Cincinnati Reds": "CIN", "Cleveland Guardians": "CLE", 
    "Colorado Rockies": "COL", "Detroit Tigers": "DET", "Houston Astros": "HOU", "Kansas City Royals": "KC",
    "Los Angeles Angels": "LAA", "Los Angeles Dodgers": "LAD", "Miami Marlins": "MIA", "Milwaukee Brewers": "MIL", 
    "Minnesota Twins": "MIN", "New York Mets": "NYM", "New York Yankees": "NYY", "Oakland Athletics": "OAK", 
    "Philadelphia Phillies": "PHI", "Pittsburgh Pirates": "PIT", "San Diego Padres": "SD", "San Francisco Giants": "SF", 
    "Seattle Mariners": "SEA", "St. Louis Cardinals": "STL", "Tampa Bay Rays": "TB", "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR", "Washington Nationals": "WSH"
}

def get_today_matchups():
    """獲取真實今日大聯盟賽程"""
    try:
        # 確保抓取美國東岸時間的「今日」真實賽程
        now = datetime.now(pytz.timezone('US/Eastern'))
        today_str = now.strftime('%Y-%m-%d')
        
        url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today_str}"
        res = requests.get(url, timeout=5).json()
        matchups = {}
        if res.get('dates'):
            for game in res['dates'][0].get('games', []):
                away_id = game['teams']['away']['team']['id']
                home_id = game['teams']['home']['team']['id']
                matchups[away_id] = {"opp_id": home_id, "is_home": False}
                matchups[home_id] = {"opp_id": away_id, "is_home": True}
        return matchups
    except:
        return {}
def get_team_id(team_str):
    """🔍 智慧查詢球隊 ID (利用已有的 TEAM_MAP 自動把全名轉縮寫)"""
    if not team_str: return None
    # 1. 如果本身就是縮寫 (例如 LAD)
    if team_str in MLB_TEAM_IDS:
        return MLB_TEAM_IDS[team_str]
    # 2. 如果是全名 (例如 Los Angeles Dodgers)，透過 TEAM_MAP 轉縮寫
    abbr = TEAM_MAP.get(team_str)
    if abbr and abbr in MLB_TEAM_IDS:
        return MLB_TEAM_IDS[abbr]
    return None
def get_team_abbr(team_id):
    """反向將 ID 轉回 3 字母縮寫"""
    for abbr, tid in MLB_TEAM_IDS.items():
        if tid == team_id and len(abbr) <= 3:  # 確保畫面上只回傳俐落的 3 字母縮寫
            return abbr
    return "MLB"
# --- ⚾ 聯盟主數據庫 API ---
def fetch_mlb_official_stats(year: int, group: str):
    # 🛡️ 加入 hydrate=person 強制大聯盟提供球員守備位置
    url = f"https://statsapi.mlb.com/api/v1/stats?stats=season&group={group}&season={year}&gameType=R&limit=1500&hydrate=person"
    res = requests.get(url, timeout=15).json()
    rows = []
    for s in res.get('stats', [{}])[0].get('splits', []):
        st = s.get('stat', {})
        p = s.get('player', {})
        team_name = s.get('team', {}).get('name', '-')
        team_abbr = TEAM_MAP.get(team_name, team_name)
        
        pos = p.get('primaryPosition', {}).get('abbreviation') or s.get('position', {}).get('abbreviation') or '-'
        
        rows.append({
            "mlb_id": p.get('id'), "Name": p.get('fullName'), "Team": team_abbr, "Pos": pos,
            "PA": st.get('plateAppearances', 0), "AB": st.get('atBats', 0), "H": st.get('hits', 0), "2B": st.get('doubles', 0), "3B": st.get('triples', 0), "HR": st.get('homeRuns', 0), "BB": st.get('baseOnBalls', 0), "IBB": st.get('intentionalWalks', 0), "HBP": st.get('hitByPitch', 0), "SF": st.get('sacFlies', 0), "SO": st.get('strikeOuts', 0), 
            "AVG": float(st.get('avg', 0) or 0), "OPS": float(st.get('ops', 0) or 0), "IP": parse_innings(st.get('inningsPitched', '0'))[0], "ERA": float(st.get('era', 0) or 0), "WHIP": float(st.get('whip', 0) or 0), "BF": st.get('battersFaced', 0),
            "R": st.get('runs', 0), "RBI": st.get('runsBattedIn', 0), "SB": st.get('stolenBases', 0),
            "W": st.get('wins', 0), "L": st.get('losses', 0), "SV": st.get('saves', 0), "HLD": st.get('holds', 0)
        })
    return pd.DataFrame(rows)

@lru_cache(maxsize=10)
def fetch_savant_combined(year: int, is_batter: bool):
    try:
        if is_batter:
            df_exp = statcast_batter_expected_stats(year, 1)
            df_ev = statcast_batter_exitvelo_barrels(year, 1)
        else:
            df_exp = statcast_pitcher_expected_stats(year, 1)
            df_ev = statcast_pitcher_exitvelo_barrels(year, 1)
            
        if not df_exp.empty: df_exp = df_exp.rename(columns={'player_id': 'mlb_id'})
        if not df_ev.empty: df_ev = df_ev.rename(columns={'player_id': 'mlb_id'})
        
        if not df_exp.empty and not df_ev.empty: return pd.merge(df_exp, df_ev, on='mlb_id', how='outer')
        return df_exp if not df_exp.empty else df_ev
    except: return pd.DataFrame()

@app.get("/league-stats")
def get_league_stats(year: Optional[int] = None, min_pa: int = 400, sort_by: str = "綜合分數", p_type: str = "打者", pos: str = "ALL"):
    if year is None: year = datetime.now().year
    try:
        is_batter = (p_type == "打者")
        df_mlb = fetch_mlb_official_stats(year, "hitting" if is_batter else "pitching")
        df_savant = fetch_savant_combined(year, is_batter)
        
        if df_mlb.empty: return {"status": "success", "data": [], "p_type": p_type}
        if not df_savant.empty and 'mlb_id' in df_savant.columns: df = pd.merge(df_mlb, df_savant, on='mlb_id', how='left')
        else: df = df_mlb
            
        for col in df.columns:
            if col not in ['Name', 'Team', 'Pos', 'last_name, first_name']: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        df = df[df['PA'] >= min_pa] if is_batter else df[df['IP'] >= (min_pa / 4.0)]
        if df.empty: return {"status": "success", "data": [], "p_type": p_type}

        if pos != "ALL":
            if pos == "OF": df = df[df['Pos'].isin(['OF', 'LF', 'CF', 'RF'])]
            else: df = df[df['Pos'] == pos]
            
        if df.empty: return {"status": "success", "data": [], "p_type": p_type}

        if is_batter:
            uBB = df['BB'] - df['IBB']
            H1B = df['H'] - df['2B'] - df['3B'] - df['HR']
            denom = (df['AB'] + df['BB'] + df['SF'] + df['HBP']).replace(0, 1)
            df['wOBA'] = (0.69*uBB + 0.72*df['HBP'] + 0.89*H1B + 1.27*df['2B'] + 1.62*df['3B'] + 2.10*df['HR']) / denom
            df['wRC+'] = (df['wOBA'] / 0.318) * 100
            df['WAR'] = ((df['wRC+'] - 100) * df['PA'] / 1500)
            df['MVP_Index'] = df['WAR']*20 + df['OPS']*50 + df['wRC+']*0.5
            df['K%'] = (df['SO'] / df['PA'].replace(0, 1)) * 100
            df['BB%'] = (df['BB'] / df['PA'].replace(0, 1)) * 100
        else:
            IP = df['IP'].replace(0, 0.1)
            BF = df['BF'].replace(0, 1)
            df['FIP'] = ((13*df['HR'] + 3*(df['BB']+df['HBP']) - 2*df['SO']) / IP) + 3.20
            df['K%'] = (df['SO'] / BF) * 100
            df['BB%'] = (df['BB'] / BF) * 100
            df['WAR'] = (4.00 - df['ERA']) * IP / 20
            df['Cy_Index'] = df['WAR']*15 + df['K%']*1.2 - df['ERA']*8 - df['WHIP']*10

        df['xwOBA'] = df.get('est_woba', 0)
        df['xBA'] = df.get('est_ba', 0)
        df['EV'] = df.get('avg_hit_speed', df.get('exit_velocity_avg', 0))
        df['HardHit%'] = df.get('ev95percent', df.get('hard_hit_percent', 0))
        df['Barrel%'] = df.get('brl_percent', df.get('barrel_batted_rate', 0))

        core_metrics = ['OPS', 'wOBA', 'wRC+', 'xwOBA', 'HardHit%', 'Barrel%'] if is_batter else ['ERA', 'WHIP', 'FIP', 'K%', 'xwOBA']
        lower_is_better = ['ERA', 'WHIP', 'FIP', 'xwOBA'] if not is_batter else []

        scores = []
        for m in core_metrics:
            if m in df.columns:
                if m in lower_is_better: scores.append(df[m].rank(pct=True, ascending=False) * 100)
                else: scores.append(df[m].rank(pct=True, ascending=True) * 100)
        df['綜合分數'] = pd.concat(scores, axis=1).mean(axis=1) if scores else 50.0

        def score_to_grade(score):
            if score >= 90: return 'S'
            elif score >= 75: return 'A'
            elif score >= 50: return 'B'
            elif score >= 25: return 'C'
            else: return 'D'
            
        df['Grade'] = df['綜合分數'].apply(score_to_grade)

        asc = False
        if sort_by in ['ERA', 'WHIP', 'FIP'] or (not is_batter and sort_by == 'xwOBA'): asc = True
        if sort_by not in df.columns: sort_by = '綜合分數'
        
        top_players = df.sort_values(by=[sort_by], ascending=asc).head(800)
        
        result = []
        for _, row in top_players.iterrows():
            d = row.to_dict()
            d['Pos'] = str(d.get('Pos', '-'))
            result.append(d)
            
        return {"status": "success", "data": result, "p_type": p_type}
    except Exception as e: return {"status": "error", "message": f"魔球計算引擎錯誤: {str(e)}"}


@app.get("/fantasy/recent")
def get_recent_form(p_type: str = "打者", pos_filter: str = "ALL", min_filter: float = 10.0, sort_metric: str = "OPS"):
    """🔥 取得近 14 天近況戰報 (解鎖 wOBA, wRC+, FIP 等進階數據)"""
    try:
        tw_now = datetime.now()
        if tw_now.month < 4 or tw_now.month > 10:
            end_dt = datetime(tw_now.year if tw_now.month > 10 else tw_now.year - 1, 9, 30)
        else:
            end_dt = tw_now
        start_dt = end_dt - timedelta(days=14)
        
        group = 'hitting' if p_type == '打者' else 'pitching'
        url = f"https://statsapi.mlb.com/api/v1/stats?stats=byDateRange&group={group}&startDate={start_dt.strftime('%Y-%m-%d')}&endDate={end_dt.strftime('%Y-%m-%d')}&sportId=1&gameType=R&playerPool=ALL&limit=1000&hydrate=person"
        
        res = requests.get(url, timeout=15).json()
        splits = res.get('stats', [{}])[0].get('splits', [])
        
        data = []
        for s in splits:
            stat = s.get('stat', {})
            p_name = s.get('player', {}).get('fullName', 'Unknown')
            t_name = s.get('team', {}).get('name', 'Unknown')
            pos = s.get('player', {}).get('primaryPosition', {}).get('abbreviation', 'Unknown')
            
            if pos_filter != "ALL":
                if pos_filter == "OF" and pos not in ["OF", "LF", "CF", "RF"]: continue
                elif pos_filter == "RP" and pos not in ["RP", "CL"]: continue
                elif pos_filter not in ["OF", "RP"] and pos != pos_filter: continue
                
            if p_type == '打者':
                pa = int(stat.get('plateAppearances', 0))
                if pa < min_filter: continue
                
                ab = int(stat.get('atBats', 0))
                r = int(stat.get('runs', 0))
                h = int(stat.get('hits', 0))
                b2 = int(stat.get('doubles', 0))
                b3 = int(stat.get('triples', 0))
                hr = int(stat.get('homeRuns', 0))
                b1 = max(0, h - b2 - b3 - hr)
                rbi = int(stat.get('rbi', 0))
                sb = int(stat.get('stolenBases', 0))
                bb = int(stat.get('baseOnBalls', 0))
                hbp = int(stat.get('hitByPitch', 0))
                k = int(stat.get('strikeOuts', 0)) # 打者這裡原本就是 stat 沒錯
                
                avg = float(stat.get('avg', '.000'))
                obp = float(stat.get('obp', '.000'))
                slg = float(stat.get('slg', '.000'))
                ops = float(stat.get('ops', '.000'))
                
                # 計算近況進階數據
                k_pct_val = (k / pa) * 100 if pa > 0 else 0
                bb_pct_val = (bb / pa) * 100 if pa > 0 else 0
                woba_val = (0.69*bb + 0.72*hbp + 0.89*b1 + 1.27*b2 + 1.62*b3 + 2.10*hr) / pa if pa > 0 else 0.0
                wrc_plus = int((woba_val / 0.315) * 100) if pa > 0 else 0
                
                data.append({
                    'name': p_name, 'team': t_name, 'pos': pos, 'pa': pa, 'ab': ab,
                    'r': r, 'h': h, 'b1': b1, 'b2': b2, 'b3': b3, 'hr': hr, 'rbi': rbi,
                    'sb': sb, 'bb': bb, 'k': k, 'avg': avg, 'obp': obp, 'slg': slg, 'ops': ops,
                    'woba': f"{woba_val:.3f}", 'wrc_plus': wrc_plus,
                    'k_pct': f"{round(k_pct_val, 1)}%", 'bb_pct': f"{round(bb_pct_val, 1)}%"
                })
            else:
                ip, outs = parse_innings(stat.get('inningsPitched', '0'))
                if ip < min_filter: continue
                
                w = int(stat.get('wins', 0))
                l = int(stat.get('losses', 0))
                sv = int(stat.get('saves', 0))
                hld = int(stat.get('holds', 0))
                h_hits = int(stat.get('hits', 0))
                er = int(stat.get('earnedRuns', 0))
                hr = int(stat.get('homeRuns', 0))
                bb = int(stat.get('baseOnBalls', 0))
                hbp = int(stat.get('hitBatsmen', 0))
                
                # 🔥 這裡已經修復：將 st 改成 stat
                k = int(stat.get('strikeOuts', 0)) 
                
                bf = int(stat.get('battersFaced', 0))
                
                era = float(stat.get('era', '0.00'))
                whip = float(stat.get('whip', '0.00'))
                
                # 計算近況進階數據
                fip = round(((13*hr + 3*(bb+hbp) - 2*k) / ip) + 3.10, 2) if ip > 0 else 0.00
                k_pct_val = (k / bf) * 100 if bf > 0 else 0
                bb_pct_val = (bb / bf) * 100 if bf > 0 else 0
                
                if stat.get('gamesStarted', 0) > stat.get('gamesPlayed', 0) / 2: pos = 'SP'
                elif sv >= 1 or stat.get('gamesFinished', 0) > 0: pos = 'CL/RP'
                else: pos = 'RP'
                
                data.append({
                    'name': p_name, 'team': t_name, 'pos': pos, 'ip': round(ip, 1),
                    'w': w, 'l': l, 'sv': sv, 'hld': hld, 'h': h_hits, 'er': er, 'hr': hr, 'bb': bb, 'k': k,
                    'era': era, 'whip': whip, 'fip': fip,
                    'k_pct': f"{round(k_pct_val, 1)}%", 'bb_pct': f"{round(bb_pct_val, 1)}%"
                })
                
        if p_type == '打者':
            data.sort(key=lambda x: x.get(sort_metric.lower(), 0), reverse=True)
        else:
            rev = False if sort_metric.lower() in ['era', 'whip', 'bb'] else True
            data.sort(key=lambda x: x.get(sort_metric.lower(), 0), reverse=rev)
            
        return {"status": "success", "data": data[:50]}
    except Exception as e:
        return {"status": "error", "message": f"獲取近況失敗: {str(e)}"}

# --- 🌱 MiLB 小聯盟農場 API ---
@app.get("/milb-stats")
def get_milb_stats(year: int = 2023, sport_id: int = 11, p_type: str = "打者"):
    try:
        group = "hitting" if p_type == "打者" else "pitching"
        # 🛡️ 強制吃數字 sport_id，並加上 gameType=R 與 playerPool=ALL
        url = f"https://statsapi.mlb.com/api/v1/stats?stats=season&group={group}&season={year}&sportId={sport_id}&gameType=R&playerPool=ALL&limit=1000&hydrate=person"
        res = requests.get(url, timeout=15).json()
        
        rows = []
        for s in res.get('stats', [{}])[0].get('splits', []):
            st = s.get('stat', {})
            p = s.get('player', {})
            
            pos = p.get('primaryPosition', {}).get('abbreviation') or s.get('position', {}).get('abbreviation') or '-'
            
            row = {
                "Name": p.get('fullName', '-'),
                "Team": s.get('team', {}).get('name', '-'),
                "Pos": pos
            }
            
            if p_type == "打者":
                pa = st.get('plateAppearances', 0)
                if pa < 50: continue
                ops = float(st.get('ops', 0) or 0)
                avg = float(st.get('avg', 0) or 0)
                row.update({
                    "PA": pa, "HR": st.get('homeRuns', 0), "SB": st.get('stolenBases', 0),
                    "AVG": avg, "OPS": ops
                })
                if ops >= 0.950: fv = 70
                elif ops >= 0.880: fv = 60
                elif ops >= 0.800: fv = 50
                elif ops >= 0.700: fv = 40
                else: fv = 30
                row["FV"] = fv
            else:
                ip, outs = parse_innings(st.get('inningsPitched', '0'))
                if ip < 15: continue
                era = float(st.get('era', 0) or 0)
                whip = float(st.get('whip', 0) or 0)
                row.update({
                    "IP": ip, "ERA": era, "WHIP": whip,
                    "SO": st.get('strikeOuts', 0)
                })
                if era <= 2.50: fv = 70
                elif era <= 3.20: fv = 60
                elif era <= 4.00: fv = 50
                elif era <= 4.80: fv = 40
                else: fv = 30
                row["FV"] = fv
                
            rows.append(row)
            
        df = pd.DataFrame(rows)
        if df.empty: return {"status": "success", "data": []}
        
        if p_type == "打者":
            df = df.sort_values(by=['FV', 'OPS'], ascending=[False, False]).head(50)
        else:
            df = df.sort_values(by=['FV', 'ERA'], ascending=[False, True]).head(50)
            
        return {"status": "success", "data": df.to_dict(orient='records'), "p_type": p_type}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/suggest-player/{query}")
def suggest_player(query: str):
    """🧠 智慧搜尋聯想引擎：呼叫 MLB 官方 Lookup API 進行即時比對"""
    try:
        # 使用 MLB 官方輕量級的查詢 API，只找現役球員 ('Y')
        url = f"https://lookup-service-prod.mlb.com/json/named.search_player_all.bam?entity_type='Y'&search_player_all='{query}'"
        res = requests.get(url, timeout=5).json()
        results = res.get("search_player_all", {}).get("queryResults", {})
        
        row = results.get("row")
        if not row: 
            return {"status": "success", "suggestions": []}
        
        # 如果只有一個結果，MLB API 會回傳 dict，我們把它包成 list 以便統一處理
        if isinstance(row, dict): 
            row = [row]
        
        # 提取全名並回傳前 10 筆
        suggestions = [p.get("name_display_first_last") for p in row if p.get("name_display_first_last")]
        return {"status": "success", "suggestions": suggestions[:10]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/deep-search/{player_name}")
def get_deep_search_data(player_name: str, year: Optional[int] = None):
    if year is None: year = datetime.now().year
    try:
        # 🔥 升級核心：捨棄容易出錯的 pybaseball.playerid_lookup
        target_name = player_name.split('(')[0].strip()
        
        search_url = f"https://statsapi.mlb.com/api/v1/people/search?names={target_name}&sportIds=11,12,13,14,15,1,16,17"
        search_res = requests.get(search_url, timeout=10).json()
        
        if not search_res.get('people'):
            return {"status": "error", "message": f"資料庫中找不到 {player_name}！請確認拼字是否正確。"}
            
        person_basic = search_res['people'][0]
        mlb_id = person_basic['id']
        real_name = person_basic['fullName']
        
        # 👇 下面完全保留您原本寫好的超強 hydrate 數據爬蟲邏輯 👇
        # 🛡️ 升級 1：在 hydrate 中加入 fielding (守備數據)
        url = f"https://statsapi.mlb.com/api/v1/people/{mlb_id}?hydrate=stats(group=[hitting,pitching,fielding],type=[season,platoon,statSplits],sitCodes=[vl,vr],season={year})"
        res = requests.get(url, timeout=10).json()
        person = res.get('people', [{}])[0]
        
        basic_info = {
            "Name": real_name, "Age": person.get('currentAge', '-'),
            "Height": person.get('height', '-'), "Weight": person.get('weight', '-'),
            "Throws": person.get('pitchHand', {}).get('code', '-'), "Bats": person.get('batSide', {}).get('code', '-'),
            "TeamID": person.get('currentTeam', {}).get('id', 0),
            "TeamName": person.get('currentTeam', {}).get('name', 'Free Agent')
        }

        hitting_stats, pitching_stats = {}, {}
        platoon_stats = {'hitting': {'vl': {}, 'vr': {}}, 'pitching': {'vl': {}, 'vr': {}}}
        fielding_pos_count = {} # 用來計算各守位出賽數
        
        for s in person.get('stats', []):
            group_name = s.get('group', {}).get('displayName', '').lower()
            type_name = s.get('type', {}).get('displayName', '')
            splits = s.get('splits', [])
            if not splits: continue
            
            if type_name == 'season':
                if group_name == 'hitting': hitting_stats = splits[0].get('stat', {})
                elif group_name == 'pitching': pitching_stats = splits[0].get('stat', {})
                elif group_name == 'fielding':
                    # 🛡️ 升級 2：累加該賽季各個守備位置的出賽場次
                    for sp in splits:
                        pos_abbr = sp.get('position', {}).get('abbreviation', '')
                        g_played = sp.get('stat', {}).get('gamesPlayed', 0)
                        if pos_abbr and pos_abbr != 'P': # 投手獨立計算
                            fielding_pos_count[pos_abbr] = fielding_pos_count.get(pos_abbr, 0) + g_played

            elif type_name in ['platoon', 'statSplits']:
                for sp in splits:
                    code = sp.get('split', {}).get('code', '').lower()
                    if code in ['vl', 'vr'] and group_name in ['hitting', 'pitching']:
                        platoon_stats[group_name][code] = sp.get('stat', {})

        has_hitting = bool(hitting_stats and (hitting_stats.get('plateAppearances', 0) > 0 or hitting_stats.get('atBats', 0) > 0))
        has_pitching = bool(pitching_stats and (pitching_stats.get('inningsPitched', '0') != '0' or pitching_stats.get('gamesPitched', 0) > 0))

        # ==========================================
        # 🛡️ 升級 3：野手守位過濾 (>= 10 場) 與 OF 整合
        # ==========================================
        qualified_positions = set()
        has_of = False
        for pos, games in fielding_pos_count.items():
            if games >= 10:
                if pos in ['LF', 'CF', 'RF']: has_of = True
                else: qualified_positions.add(pos)
        
        if has_of: qualified_positions.add('OF')

        primary_pos = person.get('primaryPosition', {}).get('abbreviation', '')
        if has_hitting and not qualified_positions and primary_pos == 'DH':
            qualified_positions.add('DH')
        elif has_hitting and primary_pos == 'DH' and hitting_stats.get('gamesPlayed', 0) >= 10:
            qualified_positions.add('DH')

        final_positions = list(qualified_positions)

        # ==========================================
        # 🛡️ 升級 4：投手 SP / RP / CP 智慧判定
        # ==========================================
        if has_pitching:
            p_g = pitching_stats.get('gamesPlayed', 0)
            p_gs = pitching_stats.get('gamesStarted', 0)
            p_sv = pitching_stats.get('saves', 0)

            if p_sv >= 5: final_positions.append('CP')
            elif p_gs > (p_g / 2) and p_gs > 0: final_positions.append('SP')
            elif p_gs >= 5 and (p_g - p_gs) >= 10: final_positions.extend(['SP', 'RP'])
            else: final_positions.append('RP')

        if not final_positions: final_positions.append(primary_pos or '-')
        
        basic_info['PrimaryPos'] = final_positions 

        # --- 抓取主客場與生涯數據 ---
        ha_url = f"https://statsapi.mlb.com/api/v1/people/{mlb_id}/stats?stats=homeAndAway&group=hitting,pitching&season={year}"
        ha_res = requests.get(ha_url, timeout=10).json()
        ha_stats = {'hitting': {'home': {}, 'away': {}}, 'pitching': {'home': {}, 'away': {}}}
        for s in ha_res.get('stats', []):
            group_name = s.get('group', {}).get('displayName', '').lower()
            for sp in s.get('splits', []):
                is_home = sp.get('isHome')
                if is_home is True and group_name in ha_stats: ha_stats[group_name]['home'] = sp.get('stat', {})
                elif is_home is False and group_name in ha_stats: ha_stats[group_name]['away'] = sp.get('stat', {})

        yby_url = f"https://statsapi.mlb.com/api/v1/people/{mlb_id}/stats?stats=yearByYear&group=hitting,pitching"
        yby_res = requests.get(yby_url, timeout=10).json()
        career_stats = {'hitting': [], 'pitching': []}
        for s in yby_res.get('stats', []):
            group_name = s.get('group', {}).get('displayName', '').lower()
            for sp in s.get('splits', []):
                st = sp.get('stat', {})
                st['season'] = sp.get('season')
                st['team'] = sp.get('team', {}).get('name', 'Multiple')
                if group_name in career_stats: career_stats[group_name].append(st)
        
        career_stats['hitting'] = sorted(career_stats['hitting'], key=lambda x: str(x.get('season', '')), reverse=True)[:7]
        career_stats['pitching'] = sorted(career_stats['pitching'], key=lambda x: str(x.get('season', '')), reverse=True)[:7]

        # --- Savant PR 計算 ---
        hitting_adv, pitching_adv, h_prs, p_prs = {}, {}, {}, {}
        if has_hitting:
            savant_h = fetch_savant_combined(year, True)
            if not savant_h.empty and mlb_id in savant_h['mlb_id'].values:
                p_savant = savant_h[savant_h['mlb_id'] == mlb_id].iloc[0]
                hitting_adv['xwOBA'] = p_savant.get('est_woba', 0)
                hitting_adv['EV'] = p_savant.get('avg_hit_speed', p_savant.get('exit_velocity_avg', 0))
            h_prs['OPS'] = get_pseudo_pr(hitting_stats.get('ops'), 0.600, 0.900)
            h_prs['HR'] = get_pseudo_pr(hitting_stats.get('homeRuns'), 0, 40)
            if 'xwOBA' in hitting_adv: h_prs['xwOBA'] = get_pseudo_pr(hitting_adv['xwOBA'], 0.280, 0.380)
            if 'EV' in hitting_adv: h_prs['EV'] = get_pseudo_pr(hitting_adv['EV'], 86.0, 93.0)

        if has_pitching:
            savant_p = fetch_savant_combined(year, False)
            if not savant_p.empty and mlb_id in savant_p['mlb_id'].values:
                p_savant_p = savant_p[savant_p['mlb_id'] == mlb_id].iloc[0]
                pitching_adv['xwOBA'] = p_savant_p.get('est_woba', 0)
                pitching_adv['FIP'] = p_savant_p.get('est_era', 0) # 暫代防呆
            
            try:
                ip_val, outs = parse_innings(pitching_stats.get('inningsPitched', '0'))
                if ip_val == 0: ip_val = 0.1
                so_val = float(pitching_stats.get('strikeOuts', 0) or 0)
                bb_val = float(pitching_stats.get('baseOnBalls', 0) or 0)
                hr_val = float(pitching_stats.get('homeRuns', 0) or 0)
                hbp_val = float(pitching_stats.get('hitByPitch', 0) or 0)
                bf_val = float(pitching_stats.get('battersFaced', 1) or 1)
                
                fip = ((13 * hr_val + 3 * (bb_val + hbp_val) - 2 * so_val) / ip_val) + 3.20
                pitching_adv['FIP'] = round(fip, 2)
                pitching_adv['K%'] = round((so_val / bf_val) * 100, 1)
                pitching_adv['BB%'] = round((bb_val / bf_val) * 100, 1)
            except: pass

            p_prs['ERA'] = get_pseudo_pr(pitching_stats.get('era'), 2.50, 5.50, reverse=True)
            p_prs['WHIP'] = get_pseudo_pr(pitching_stats.get('whip'), 1.00, 1.50, reverse=True)
            p_prs['SO'] = get_pseudo_pr(pitching_stats.get('strikeOuts'), 50, 220)
            if 'FIP' in pitching_adv: p_prs['FIP'] = get_pseudo_pr(pitching_adv['FIP'], 2.80, 5.20, reverse=True)
            if 'K%' in pitching_adv: p_prs['K%'] = get_pseudo_pr(pitching_adv['K%'], 15.0, 35.0)
            if 'BB%' in pitching_adv: p_prs['BB%'] = get_pseudo_pr(pitching_adv['BB%'], 4.0, 12.0, reverse=True)
            if 'xwOBA' in pitching_adv: p_prs['xwOBA'] = get_pseudo_pr(pitching_adv['xwOBA'], 0.250, 0.350, reverse=True)

        return {
            "status": "success", "year": year, "player_info": basic_info,
            "has_hitting": has_hitting, "has_pitching": has_pitching, "is_two_way": (has_hitting and has_pitching),
            "hitting_stats": hitting_stats, "pitching_stats": pitching_stats,
            "hitting_adv": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in hitting_adv.items()},
            "pitching_adv": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in pitching_adv.items()},
            "hitting_prs": h_prs, "pitching_prs": p_prs,
            "platoon_stats": platoon_stats, "ha_stats": ha_stats, "career_stats": career_stats,
            
            # ==========================================
            # 🔥 關鍵修改：把 hitting_stats 與 pitching_stats 餵給 AI 球探，讓它自動計算樣本數 (PA/IP)
            # ==========================================
            "scout_report": generate_scout_conclusion(
                h_prs, p_prs, has_hitting, has_pitching, 
                h_stats=hitting_stats, p_stats=pitching_stats
            )
        }
    except Exception as e: 
        return {"status": "error", "message": f"深度搜尋失敗: {str(e)}"}

def get_pseudo_pr(val, min_val, max_val, reverse=False):
    if pd.isna(val) or val == '-' or val is None: return 50
    try:
        val = float(val)
        pr = ((val - min_val) / (max_val - min_val)) * 100
        if reverse: pr = 100 - pr
        return int(max(1, min(99, pr)))
    except: return 50

def generate_scout_conclusion(h_prs, p_prs, has_h, has_p, h_stats=None, p_stats=None, pa=None, ip=None):
    """
    🤖 AI 球探總結產生器 (支援 PR 值實力 + 樣本數 PA/IP 自動解析 + 終極防呆)
    """
    # 💡 1. 自動解析打席 PA (若無傳入則自動從 h_stats 提取)
    if pa is None:
        if isinstance(h_stats, dict):
            pa = h_stats.get('PA') or h_stats.get('plateAppearances') or h_stats.get('pa') or 0
        else:
            pa = 300 # 防呆：若完全沒傳入數據包，預設給予足夠樣本，避免將主力誤判為菜鳥

    try:
        pa_num = int(float(pa))
    except:
        pa_num = 300

    # 💡 2. 自動解析局數 IP (若無傳入則自動從 p_stats 提取)
    if ip is None:
        if isinstance(p_stats, dict):
            ip = p_stats.get('IP') or p_stats.get('inningsPitched') or p_stats.get('ip') or 0
        else:
            ip = 100.0

    try:
        ip_num = float(ip)
    except:
        ip_num = 100.0

    # 🦄 二刀流判斷
    if has_h and has_p:
        return random.choice([
            "🦄 神話級二刀流奇才！同時具備頂尖的打擊破壞力與主宰賽場的投球宰制力。",
            "⚔️ 現代棒球的奇蹟，能在投打兩端同時為球隊帶來巨大影響力的二刀流怪物。"
        ])
    
    # ⚾ 純打者判斷
    elif has_h:
        ops_pr = h_prs.get('OPS', 50) if isinstance(h_prs, dict) else 50
        hr_pr = h_prs.get('HR', 50) if isinstance(h_prs, dict) else 50
        avg_pr = h_prs.get('AVG', 50) if isinstance(h_prs, dict) else 50
        
        # ⚠️ 1. 小樣本 (PA < 50)
        if pa_num < 50:
            if ops_pr >= 80:
                return random.choice([
                    "🚨 樣本數尚小，但初登板展現了令人驚豔的破壞力 (OPS 高標)，值得放入觀察名單持續追蹤。",
                    "👀 驚號之姿！雖然打席數極少，但目前的爆發力絕對值得在深層聯盟買個夢想。"
                ])
            elif ops_pr >= 50:
                return random.choice([
                    "🔍 目前上場機會有限，表現中規中矩，需更多打席才能展露真實天賦。",
                    "📋 尚在適應大聯盟節奏，處於農場與板凳間的過渡期，建議持續觀望。"
                ])
            else:
                return random.choice([
                    "❄️ 樣本數極少且尚未找到手感，可能很快就會被下放或減少上場時間。",
                    "⚠️ 初登板狀態冰冷，在打席數與打擊機制校正前暫無 Fantasy 投資價值。"
                ])
                
        # ⚖️ 2. 中樣本 (50 <= PA < 250)
        elif pa_num < 250:
            if ops_pr >= 85:
                return random.choice([
                    "📈 半季樣本展現極高效率！如果能獲得穩定先發，將是超級大黑馬。",
                    "⚡ 出賽數不多但刀刀見骨！這名球員正用高效的打擊強勢爭取固定先發位置。"
                ])
            elif ops_pr >= 70:
                return random.choice([
                    "🛠️ 稱職的輪替要角，能提供穩定的火力支援，適合視對手作先發調度。",
                    "⚖️ 表現符合聯盟水準之上，是球隊不可或缺的拼圖，適合填補陣容空缺。"
                ])
            else:
                return random.choice([
                    "📉 累積了破百打席但成效不彰，可能面臨被壓縮上場時間的危機。",
                    "🧊 火力支援有限，目前數據來看僅能作為極深聯盟的板凳替補。"
                ])
                
        # 💎 3. 大樣本 (PA >= 250)
        else:
            if ops_pr >= 90:
                return random.choice([
                    "🎖️ MVP 級距建隊基石！經過長期賽季檢驗，他擁有統治聯盟的打擊影響力。",
                    "👑 毫無疑問的頂尖神獸。經過大量打席驗證，高輸出讓他成為陣容的絕對核心。"
                ])
            elif hr_pr >= 85:
                return random.choice([
                    "🌋 聯盟頂尖重砲手，擁有改變戰局的破壞力，是 Fantasy 長打數據的保證。",
                    "💣 絕對的巨砲威脅，只要球被他咬中，通常都會是一發改變戰局的全壘打。"
                ])
            elif avg_pr >= 85:
                return random.choice([
                    "🎯 頂尖安打機器，極佳的球棒控制能力，能大幅提升球隊的團隊打擊率。",
                    "🏏 擁有聯盟頂尖的擊球技巧與選球眼，是穩定輸出安打數的絕佳前段棒次。"
                ])
            elif ops_pr >= 70:
                return random.choice([
                    "⚔️ 優秀的先發主力打者，能穩定輸出火力，撐起球隊的攻擊中樞。",
                    "🌟 具備長期穩定先發實力，各項數據都在聯盟水準之上，是建隊的優質綠葉。"
                ])
            else:
                return random.choice([
                    "🛡️ 獲得大量打席的堪用打擊輪替戰力，適合用來填補特定的守備或計分空缺。",
                    "⚠️ 雖然擁有固定先發，但整季下來打擊效率偏低，在 Fantasy 陣容中屬於容易被取代的邊緣戰力。"
                ])

    # 🥎 純投手判斷
    else:
        era_pr = p_prs.get('ERA', 50) if isinstance(p_prs, dict) else 50
        so_pr = p_prs.get('SO', 50) if isinstance(p_prs, dict) else 50
        
        # ⚠️ 1. 小樣本 (IP < 20)
        if ip_num < 20:
            if era_pr >= 80:
                return random.choice([
                    "🚨 投球局數雖少，但展現了驚人壓制力！可能是潛力股或好用的短局數奇兵。",
                    "👀 少量樣本中防禦率極佳，球威值得關注，建議放入追蹤名單觀察後續發展。"
                ])
            else:
                return random.choice([
                    "📋 局數樣本過少且內容不佳，尚不具備 Fantasy 討論價值。",
                    "❄️ 剛上場就遭到震撼教育，目前局數極少且容易砸鍋，建議遠離。"
                ])
                
        # ⚖️ 2. 中樣本 (20 <= IP < 80)
        elif ip_num < 80:
            if era_pr >= 85:
                return random.choice([
                    "🔥 極佳的投球效率！無論是長中繼還是王牌後援，他都能大幅安定你的投手群。",
                    "💎 中等局數卻繳出鬼神成績，這類高效率投手是拉低團隊 ERA/WHIP 的神級維他命。"
                ])
            elif era_pr >= 65:
                return random.choice([
                    "🛠️ 稱職的牛棚或輪值後段戰力。能吃下局數且不至於崩盤，實用的工人型投手。",
                    "⚖️ 局數累積具一定規模且表現符合預期，適合在賽程緊湊時拉上來應急填補空缺。"
                ])
            else:
                return random.choice([
                    "⚠️ 在一定的局數內被頻繁狙擊，投球內容不穩，隨時可能變成球隊的核彈。",
                    "📉 壓制力嚴重不足，累積的局數反而會傷害你的比例數據，建議尋找其他替代方案。"
                ])
                
        # 💎 3. 大樣本 (IP >= 80)
        else:
            if era_pr >= 90 or so_pr >= 95:
                return random.choice([
                    "👑 賽揚等級神獸，能徹底主宰比賽。擁有他等於每週自動鎖定各項投手數據勝局。",
                    "🎖️ 統治級的先發巨投！經過大量局數檢驗依然屹立不搖，是能宰制 Fantasy 的真王牌。"
                ])
            elif so_pr >= 85:
                return random.choice([
                    "🔥 頂級三振機器，擁有極具引誘性的極品變化球，是三振數據 (K) 的大補丸。",
                    "🌪️ 具備極強的奪三振能力，能憑藉球威強勢解決打者，但需注意用球數的控制。"
                ])
            elif era_pr >= 70:
                return random.choice([
                    "🎯 穩定的前段輪值或佈局投手，值得信賴，能為球隊吃下大量優質局數。",
                    "🌟 優質的主力投手！能穩定壓低失分且確保一定品質，是球隊不可多得的中流砥柱。"
                ])
            else:
                return random.choice([
                    "🧩 大量吃局數的稱職投手戰力。雖然偶有失常，但能穩定貢獻 IP，屬於勞工型投手。",
                    "⚠️ 大量局數伴隨的是偏高的防禦率，上場宛如俄羅斯輪盤，容易造成單週 ERA 爆炸，慎用！"
                ])

@app.get("/team-info/{team_id}")
def get_team_info(team_id: int, year: int = 2026):
    """⚾ 獲取球隊全方位戰情：戰績、團隊數據、名單、賽程"""
    try:
        if not team_id or team_id == 0:
            return {"status": "error", "message": "無效的球隊 ID"}

        # 1. 抓取球隊戰績
        standings_url = f"https://statsapi.mlb.com/api/v1/standings?leagueId=103,104&season={year}&standingsTypes=regularSeason"
        standings_res = requests.get(standings_url, timeout=10).json()
        team_standing = {}
        for record in standings_res.get('records', []):
            for team_record in record.get('teamRecords', []):
                if team_record.get('team', {}).get('id') == team_id:
                    rs = team_record.get('runsScored', 0)
                    ra = team_record.get('runsAllowed', 0)
                    diff = team_record.get('runDifferential', rs - ra)
                    diff_str = f"+{diff}" if diff > 0 else str(diff)

                    team_standing = {
                        "divisionRank": team_record.get('divisionRank', '-'),
                        "leagueRank": team_record.get('leagueRank', '-'),
                        "wins": team_record.get('wins', 0),
                        "losses": team_record.get('losses', 0),
                        "pct": team_record.get('winningPercentage', '.000'),
                        "gb": team_record.get('gamesBack', '-'),
                        "streak": team_record.get('streak', {}).get('streakCode', '-'),
                        "home_record": "-", "away_record": "-",
                        "runs_scored": rs, "runs_allowed": ra, "run_diff": diff_str
                    }
                    for r in team_record.get('records', {}).get('splitRecords', []):
                        r_type = r.get('type')
                        if r_type == 'lastTen': team_standing['l10'] = f"{r.get('wins')}-{r.get('losses')}"
                        elif r_type == 'home': team_standing['home_record'] = f"{r.get('wins')}-{r.get('losses')}"
                        elif r_type == 'away': team_standing['away_record'] = f"{r.get('wins')}-{r.get('losses')}"
                    break

        # 2. 抓取團隊投打數據
        team_stats_url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/stats?stats=season&group=hitting,pitching&season={year}"
        team_stats_res = requests.get(team_stats_url, timeout=10).json()
        team_hitting, team_pitching = {}, {}
        for s in team_stats_res.get('stats', []):
            grp = s.get('group', {}).get('displayName', '').lower()
            splits = s.get('splits', [])
            if splits:
                st = splits[0].get('stat', {})
                if grp == 'hitting':
                    team_hitting = {"avg": st.get('avg', '.000'), "ops": st.get('ops', '.000'), "hr": st.get('homeRuns', 0), "sb": st.get('stolenBases', 0)}
                elif grp == 'pitching':
                    team_pitching = {"era": st.get('era', '0.00'), "whip": st.get('whip', '0.00'), "so": st.get('strikeOuts', 0), "sv": st.get('saves', 0)}

        # 🚀 升級核心：抓取全隊各投手數據，用來智慧判定 SP / RP / CP
        team_p_stats_url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/stats?stats=season&group=pitching&playerPool=all&season={year}"
        team_p_res = requests.get(team_p_stats_url, timeout=10).json()
        pitcher_roles = {}
        for s in team_p_res.get('stats', []):
            for split in s.get('splits', []):
                # 🛡️ 關鍵修復：強制把 ID 轉成字串，避免型別比對失敗
                pid = str(split.get('player', {}).get('id', ''))
                st = split.get('stat', {})
                p_g = st.get('gamesPlayed', 0)
                p_gs = st.get('gamesStarted', 0)
                p_sv = st.get('saves', 0)
                
                # 判斷邏輯
                if p_sv >= 5: role = 'CP'
                elif p_gs > (p_g / 2) and p_gs > 0: role = 'SP'
                elif p_gs >= 3 and (p_g - p_gs) >= 5: role = 'SP/RP'
                else: role = 'RP'
                
                pitcher_roles[pid] = role

       # 3. 抓取名單並利用 hydrate 直接掛載個人賽季數據 (致敬原版 data_fetcher 做法)
        roster_url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster?rosterType=40Man&hydrate=person(stats(type=season,season={year}))"
        roster_res = requests.get(roster_url, timeout=15).json()
        roster_list, injury_list = [], []
        
        for item in roster_res.get('roster', []):
            person = item.get('person', {})
            primary_pos = item.get('position', {}).get('abbreviation', '-')
            
            pos_list = []
            
            # 1. 投手 / 二刀流 Pitching 角色判定
            if primary_pos in ['P', 'TWP']:
                p_stat = None
                for s in person.get('stats', []):
                    if s.get('group', {}).get('displayName', '').lower() == 'pitching' and s.get('type', {}).get('displayName', '').lower() == 'season':
                        if s.get('splits'):
                            p_stat = s['splits'][0].get('stat', {})
                            break
                if p_stat:
                    p_gs = p_stat.get('gamesStarted', 0)
                    p_gp = p_stat.get('gamesPlayed', 0)
                    p_sv = p_stat.get('saves', 0)
                    
                    if p_sv >= 5: pos_list.append('CP')
                    elif p_gs > (p_gp / 2) and p_gs > 0: pos_list.append('SP')
                    elif p_gs >= 3 and (p_gp - p_gs) >= 5: pos_list.append('SP/RP')
                    else: pos_list.append('RP')
                else:
                    pos_list.append('SP' if primary_pos == 'TWP' else 'RP')

            # 2. 二刀流 / 打者 / 野手 守位判定 (致敬 data_fetcher.py 邏輯)
            if primary_pos in ['TWP', 'DH'] and 'DH' not in pos_list:
                pos_list.append('DH')
            elif primary_pos in ['LF', 'CF', 'RF'] and 'OF' not in pos_list:
                pos_list.append('OF')
            elif primary_pos not in ['P', 'TWP'] and primary_pos not in pos_list:
                pos_list.append(primary_pos)

            pos_str = ", ".join(dict.fromkeys(pos_list))
            
            status_code = item.get('status', {}).get('code', 'A')
            status_desc = item.get('status', {}).get('description', 'Active')
            
            p_data = {
                "name": person.get('fullName', '-'),
                "number": item.get('jerseyNumber', '-'),
                "pos": pos_str, # 回傳像 "SP, DH" 或 "OF"
                "bats_throws": f"{person.get('batSide', {}).get('code', '-')}/{person.get('pitchHand', {}).get('code', '-')}",
                "status": status_desc
            }
            
            if 'IL' in status_desc or 'Injured' in status_desc or status_code in ['D10', 'D15', 'D60', 'IL']:
                injury_list.append(p_data)
            else:
                roster_list.append(p_data)
        # 4. 賽程表
        today = datetime.now()
        start_date = (today - timedelta(days=15)).strftime("%Y-%m-%d")
        end_date = (today + timedelta(days=15)).strftime("%Y-%m-%d")
        schedule_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId={team_id}&startDate={start_date}&endDate={end_date}&hydrate=team,linescore,probablePitcher(noteam)"
        schedule_res = requests.get(schedule_url, timeout=10).json()

        past_games, future_games = [], []
        for date_data in schedule_res.get('dates', []):
            date_str = date_data.get('date', '')
            for game in date_data.get('games', []):
                status = game.get('status', {}).get('abstractGameState', '')
                teams = game.get('teams', {})
                is_home = teams.get('home', {}).get('team', {}).get('id') == team_id
                game_info = {
                    "date": date_str,
                    "opponent": teams.get('away' if is_home else 'home', {}).get('team', {}).get('name', ''),
                    "venue": "🏠 主場" if is_home else "✈️ 客場",
                    "status": status
                }
                if status == 'Final':
                    ts = teams['home'].get('score', 0) if is_home else teams['away'].get('score', 0)
                    os = teams['away'].get('score', 0) if is_home else teams['home'].get('score', 0)
                    game_info["result"] = "W" if ts > os else ("L" if ts < os else "T")
                    game_info["score"] = f"{ts} - {os}"
                    past_games.append(game_info)
                elif status in ['Preview', 'Scheduled', 'Pre-Game']:
                    game_info["opp_pitcher"] = teams.get('home' if not is_home else 'away', {}).get('probablePitcher', {}).get('fullName', 'TBD')
                    future_games.append(game_info)

        past_games = sorted(past_games, key=lambda x: x['date'], reverse=True)[:5]
        future_games = sorted(future_games, key=lambda x: x['date'])[:5]

        return {
            "status": "success", "team_id": team_id,
            "standings": team_standing, "team_stats": {"hitting": team_hitting, "pitching": team_pitching},
            "roster": roster_list, "injuries": injury_list,
            "past_games": past_games, "future_games": future_games,
            "recent_form": {
                "runs_scored": sum(int(g['score'].split(' - ')[0]) for g in past_games if 'score' in g),
                "runs_allowed": sum(int(g['score'].split(' - ')[1]) for g in past_games if 'score' in g)
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
@app.get("/daily-schedule")
def get_daily_schedule(date_str: str):
    """📅 抓取指定日期的 MLB 全聯盟賽程、預計先發投手與球隊 ID"""
    try:
        url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}&hydrate=probablePitcher,team,linescore"
        res = requests.get(url, timeout=10).json()
        
        dates = res.get('dates', [])
        if not dates:
            return {"status": "success", "date": date_str, "games": []}
            
        games_list = []
        for g in dates[0].get('games', []):
            teams = g.get('teams', {})
            away = teams.get('away', {})
            home = teams.get('home', {})
            
            away_team_id = away.get('team', {}).get('id', 0)
            home_team_id = home.get('team', {}).get('id', 0)
            
            away_team_name = away.get('team', {}).get('name', 'Unknown')
            home_team_name = home.get('team', {}).get('name', 'Unknown')
            
            away_pitcher = away.get('probablePitcher', {}).get('fullName', 'TBD')
            home_pitcher = home.get('probablePitcher', {}).get('fullName', 'TBD')
            
            status = g.get('status', {}).get('abstractGameState', 'Scheduled')
            detailed_status = g.get('status', {}).get('detailedState', '')
            
            away_score = away.get('score', 0)
            home_score = home.get('score', 0)
            
            games_list.append({
                "game_pk": g.get('gamePk'),
                "venue_name": home_team_name,
                "away_team_id": away_team_id,
                "home_team_id": home_team_id,
                "away_team": away_team_name,
                "home_team": home_team_name,
                "away_pitcher": away_pitcher,
                "home_pitcher": home_pitcher,
                "status": status,
                "detailed_status": detailed_status,
                "score": f"{away_score} - {home_score}" if status in ['Live', 'Final'] else "vs"
            })
            
        return {"status": "success", "date": date_str, "games": games_list}
    except Exception as e:
        return {"status": "error", "message": f"無法獲取賽程: {str(e)}"}
@app.get("/predict-matchup")
def predict_matchup(home_team: str, away_team: str, year: Optional[int] = None):
    if year is None: year = datetime.now().year
    """🔮 實時賽事預測引擎：動態抓取指定賽季 (2026) 實時主客場 Split 數據與戰績，拒絕假數據"""
    try:
        home_team_id = get_team_id(home_team)
        away_team_id = get_team_id(away_team)
        
        home_abbr = get_team_abbr(home_team_id)
        away_abbr = get_team_abbr(away_team_id)

        # 安全轉換浮點數，不寫死任何假數據預設值
        def safe_float(val):
            try:
                if val is None or str(val).strip() in ["-.--", ".---", ""]:
                    return None
                return float(val)
            except:
                return None

        # 1. 實時抓取當前指定賽季 (year) 的主客場獨立數據
        def fetch_real_team_stats(t_id, is_home_split):
            if not t_id:
                return {"ops": None, "era": None, "hr": None}
            try:
                # 📡 請求當季 (如 2026) Home/Away split 實時數據
                url = f"https://statsapi.mlb.com/api/v1/teams/{t_id}/stats?stats=homeAndAway&group=hitting,pitching&season={year}"
                res = requests.get(url, timeout=8).json()
                
                ops, era, hr = None, None, None
                for s in res.get('stats', []):
                    grp = s.get('group', {}).get('displayName', '').lower()
                    for split in s.get('splits', []):
                        if split.get('isHome') == is_home_split:
                            st = split.get('stat', {})
                            if grp == 'hitting':
                                ops = safe_float(st.get('ops'))
                                hr = int(st.get('homeRuns')) if st.get('homeRuns') is not None else None
                            elif grp == 'pitching':
                                era = safe_float(st.get('era'))
                
                # 💡 若 Split 資料欄位不齊全，則抓取當季 (year) 團隊整體數據補全，絕不拿過期年份或預設假數字
                if ops is None or era is None:
                    url_gen = f"https://statsapi.mlb.com/api/v1/teams/{t_id}/stats?stats=season&group=hitting,pitching&season={year}"
                    res_gen = requests.get(url_gen, timeout=8).json()
                    for s in res_gen.get('stats', []):
                        grp = s.get('group', {}).get('displayName', '').lower()
                        splits = s.get('splits', [])
                        if splits:
                            st = splits[0].get('stat', {})
                            if grp == 'hitting' and ops is None:
                                ops = safe_float(st.get('ops'))
                                hr = int(st.get('homeRuns')) if st.get('homeRuns') is not None else hr
                            elif grp == 'pitching' and era is None:
                                era = safe_float(st.get('era'))
                                
                return {"ops": ops, "era": era, "hr": hr}
            except Exception as e:
                return {"ops": None, "era": None, "hr": None}

        home_stats = fetch_real_team_stats(home_team_id, True)
        away_stats = fetch_real_team_stats(away_team_id, False)

        # 2. 實時抓取當季 (year) 聯賽戰績榜
        home_record, away_record = "0-0", "0-0"
        home_overall, away_overall = "0-0", "0-0"
        home_win_ratio, away_win_ratio = 0.5, 0.5

        try:
            standings_url = f"https://statsapi.mlb.com/api/v1/standings?leagueId=103,104&season={year}&standingsTypes=regularSeason"
            standings_res = requests.get(standings_url, timeout=5).json()

            for record in standings_res.get('records', []):
                for tr in record.get('teamRecords', []):
                    tid = tr.get('team', {}).get('id')
                    w, l = tr.get('wins', 0), tr.get('losses', 0)
                    
                    if tid == home_team_id:
                        home_overall = f"{w}-{l}"
                        for sr in tr.get('records', {}).get('splitRecords', []):
                            if sr.get('type') == 'home': 
                                home_record = f"{sr.get('wins')}-{sr.get('losses')}"
                                hw, hl = sr.get('wins', 0), sr.get('losses', 0)
                                if hw + hl > 0: home_win_ratio = hw / (hw + hl)
                    elif tid == away_team_id:
                        away_overall = f"{w}-{l}"
                        for sr in tr.get('records', {}).get('splitRecords', []):
                            if sr.get('type') == 'away': 
                                away_record = f"{sr.get('wins')}-{sr.get('losses')}"
                                aw, al = sr.get('wins', 0), sr.get('losses', 0)
                                if aw + al > 0: away_win_ratio = aw / (aw + al)
        except: pass

        # 3. 球場環境因子 (Park Factors)
        safe_abbr = str(home_abbr).strip().upper()
        
        # 使用淨化後的 safe_abbr 去查字典
        pf = PARK_FACTORS.get(safe_abbr, {"OPS": 1.00, "HR": 1.00, "ERA": 1.00, "desc": "⚖️ 標準中性球場"})
        # 取出實時數值 (若 API 尚未採集到，使用目前聯盟基準 0.720 / 4.10 作極致防呆)
        h_ops = home_stats.get('ops') if home_stats and home_stats.get('ops') is not None else 0.720
        h_era = home_stats.get('era') if home_stats and home_stats.get('era') is not None else 4.10
        a_ops = away_stats.get('ops') if away_stats and away_stats.get('ops') is not None else 0.720
        a_era = away_stats.get('era') if away_stats and away_stats.get('era') is not None else 4.10

        # 魔球計算模型
        LEAGUE_AVG_OPS = 0.720
        away_off_power = 4.5 + ((a_ops - LEAGUE_AVG_OPS) / 0.01) * 0.18
        home_off_power = 4.5 + ((h_ops - LEAGUE_AVG_OPS) / 0.01) * 0.18
        
        exp_away_runs = max(1.0, round(((away_off_power + h_era) / 2) * pf['OPS'], 1))
        exp_home_runs = max(1.0, round(((home_off_power + a_era) / 2) * pf['OPS'] + 0.4, 1))
        
        run_diff = exp_home_runs - exp_away_runs
        record_adj = (home_win_ratio - away_win_ratio) * 10
        home_win_pct = max(20, min(80, int(50 + (run_diff * 14) + record_adj)))
        away_win_pct = 100 - home_win_pct
        
        # 🧠 生成 AI 球探報告
        scout_summary = []
        adv_text = f"顯示出 **{home_team}** 擁有極佳的主場優勢與火力，客隊將面臨嚴峻挑戰。" if home_win_ratio > away_win_ratio else f"顯示出 **{away_team}** 具備優異的客場抗壓能力，有望在客場踢館成功。"
        scout_summary.append(f"📊 **主客場戰鬥力解析**：**{home_team}** 當前賽季主場戰績為 **{home_record}** (總戰績 {home_overall})，主場實時 OPS 為 {h_ops:.3f}；而 **{away_team}** 客場戰績為 **{away_record}** (總戰績 {away_overall})，客場實時 OPS 為 {a_ops:.3f}。{adv_text}")

        env_adv = "優勢" if pf['ERA'] < 1 else "考驗"
        better_pitcher = home_team if h_era < a_era else away_team
        scout_summary.append(f"🛡️ **投手壓制力與環境庇護**：主場屬於對投手的 **{env_adv}環境** ({pf['desc']})。**{better_pitcher}** 帶著優異的防禦率表現 ({min(h_era, a_era):.2f}) 進入本場比賽，預期能利用環境庇護有效降低對手的長打威脅。")

        better_hitter = home_team if h_ops > a_ops else away_team
        scout_summary.append(f"🔥 **打線火力與勝率效應**：**{better_hitter}** 展現出強大的打擊火網 (OPS 達 {max(h_ops, a_ops):.3f})。在勝率模型中，這種高串聯度的打線能製造極高的得分期望值。")
        
        home_edge = (h_ops - a_ops) + ((a_era - h_era) * 0.05)
        blood_team = home_team if home_edge > 0 else away_team
        blood_victim = away_team if home_edge > 0 else home_team
        scout_summary.append(f"⚔️ **血性優勢與陣容相剋**：經當前賽季主客場實時數據交叉比對，**{blood_team}** 在對戰適應性與牛棚消耗戰中，對 **{blood_victim}** 具有顯著的壓制優勢。")

        return {
            "status": "success",
            "home_team": home_team,
            "away_team": away_team,
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
            "park_factor": pf,
            "matchup_stats": {
                "home_record": home_record, "home_overall": home_overall, "home_ops": h_ops, "home_era": h_era,
                "away_record": away_record, "away_overall": away_overall, "away_ops": a_ops, "away_era": a_era
            },
            "prediction": {
                "home_win_pct": home_win_pct, "away_win_pct": away_win_pct,
                "exp_score": f"{exp_away_runs} - {exp_home_runs}", "exp_away_runs": exp_away_runs, "exp_home_runs": exp_home_runs
            },
            "scout_summary": scout_summary
        }
    except Exception as e:
        return {"status": "error", "message": f"預測失敗: {str(e)}"}
@app.get("/fantasy/projections")
def get_future_projections(p_type: str = "打者", year: Optional[int] = None):
    """🔮 未來預期 (三合一引擎)：ROS 剩餘推算 + 賽程紅利 + 買低賣高雷達"""
    if year is None: year = datetime.now().year
    try:
        db = load_fantasy_db()
        my_players = [p["name"].lower() for p in db.get("custom_roster", [])]
        
        real_stats = get_real_season_stats()
        hit_sc_data, pit_sc_data = get_statcast_data(year)
        
        # 🗓️ 1. 批次抓取全聯盟未來 7 天賽程，建立紅利快取 (極速演算法)
        today = datetime.now()
        start_date = today.strftime("%Y-%m-%d")
        end_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")
        sch_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&startDate={start_date}&endDate={end_date}"
        sch_res = requests.get(sch_url, timeout=5).json()
        
        team_schedule_cache = {}
        for date_data in sch_res.get('dates', []):
            for game in date_data.get('games', []):
                away_id = game['teams']['away']['team']['id']
                home_id = game['teams']['home']['team']['id']
                
                # 客隊記錄
                if away_id not in team_schedule_cache: team_schedule_cache[away_id] = {"games": 0, "diff_score": 0, "opponents": []}
                team_schedule_cache[away_id]["games"] += 1
                pf_away = PARK_FACTORS.get(get_team_abbr(home_id), {}).get("OPS", 1.0)
                team_schedule_cache[away_id]["diff_score"] += (pf_away - 1.0) # 客場看對手主場係數
                team_schedule_cache[away_id]["opponents"].append(f"@{get_team_abbr(home_id)}")
                
                # 主隊記錄
                if home_id not in team_schedule_cache: team_schedule_cache[home_id] = {"games": 0, "diff_score": 0, "opponents": []}
                team_schedule_cache[home_id]["games"] += 1
                pf_home = PARK_FACTORS.get(get_team_abbr(home_id), {}).get("OPS", 1.0)
                team_schedule_cache[home_id]["diff_score"] += (pf_home - 1.0) # 享受自己主場係數
                team_schedule_cache[home_id]["opponents"].append(f"vs {get_team_abbr(away_id)}")

        # 🔮 2. 開始生成全聯盟球員預期
        projections_data = []
        target_type = "hitter" if p_type == "打者" else "pitcher"
        
        for name, data in real_stats.items():
            if data["type"] != target_type: continue
            
            st = data["stat"]
            player_id = None # 若需精準查 statcast，需有 player_id，這裡我們用迴圈反查或以名字對應，為求快我們用迴圈匹配
            # 這裡簡化：實務上 statcast 快取是用 MLB_ID，我們從 real_stats 裡拿不到 ID，直接用全域對應或簡單防呆
            # (在您原本的程式裡 real_stats 似乎沒存 ID，我們先用傳統進階公式做回歸，或略過鷹眼數據)
            
            team_abbr = data["team"]
            team_id = get_team_id(team_abbr)
            
            # --- 🗓️ 賽程紅利模組 ---
            sch = team_schedule_cache.get(team_id, {"games": 0, "diff_score": 0, "opponents": []})
            games_next_7 = sch["games"]
            diff = sch["diff_score"]
            opp_str = ", ".join(sch["opponents"][:3]) + ("..." if games_next_7 > 3 else "")
            
            if p_type == "打者":
                sch_grade = "🔥 極佳" if diff > 0.05 and games_next_7 >= 6 else ("❄️ 艱困" if diff < -0.05 or games_next_7 <= 5 else "⚖️ 中性")
            else:
                sch_grade = "🔥 極佳" if diff < -0.05 else ("❄️ 艱困" if diff > 0.05 else "⚖️ 中性")

            if p_type == "打者":
                g = int(st.get('gamesPlayed', 1)) or 1
                pa = int(st.get('plateAppearances', 0))
                if pa < 40: continue
                
                hr = int(st.get('homeRuns', 0))
                sb = int(st.get('stolenBases', 0))
                avg = float(st.get('avg', '.000'))
                babip = float(st.get('babip', '.000'))
                
                # --- 🔮 ROS 剩餘賽季推算模組 ---
                rem_games = max(0, 162 - g)
                ros_hr = int((hr / g) * rem_games) if g > 0 else 0
                ros_sb = int((sb / g) * rem_games) if g > 0 else 0
                
                # --- 📈 買低賣高回歸模組 ---
                luck_score = 0
                xba = avg + (0.300 - babip) * 0.4 # 簡易預期打擊率
                
                if babip > 0.340 and avg > 0.280: luck_score -= 2
                elif babip < 0.260 and avg < 0.250: luck_score += 2
                
                ai_judgement = "🚀 逢低買進" if luck_score > 0 else ("📉 逢高賣出" if luck_score < 0 else "⚖️ 實力相符")
                reason = f"BABIP 異常 ({babip:.3f})" if luck_score != 0 else "數據健康"
                
                projections_data.append({
                    "name": name.title(), "team": team_abbr, "pos": data["pos"],
                    "in_my_team": name in my_players,
                    "ros_hr": ros_hr, "ros_sb": ros_sb, "proj_end": f"{hr + ros_hr} 轟 / {sb + ros_sb} 盜",
                    "sch_games": games_next_7, "sch_opp": opp_str, "sch_grade": sch_grade,
                    "ba": avg, "xba": round(xba, 3), "ai_judgment": ai_judgement, "report": reason,
                    "sort_score": abs(luck_score) * 10 + (1 if name in my_players else 0)
                })
                
            else: # 投手
                g = int(st.get('gamesPlayed', 1)) or 1
                # 直接呼叫引擎，同時取得計算用局數 (ip_math) 與出局數 (outs)
                ip_math, outs = parse_innings(st.get('inningsPitched', '0'))
                if ip_math < 15: continue
                
                so = int(st.get('strikeOuts', 0))
                sv = int(st.get('saves', 0))
                era = float(st.get('era', '4.00'))
                hr, bb = int(st.get('homeRuns', 0)), int(st.get('baseOnBalls', 0))
                
                # --- 🔮 ROS 剩餘賽季推算模組 ---
                # 簡單推算剩餘三振數與救援 (假設牛棚出賽約 65 場，先發約 32 場)
                is_sp = data["pos"] in ["SP", "SP/RP"]
                proj_total_g = 32 if is_sp else 65
                rem_games = max(0, proj_total_g - g)
                ros_so = int((so / g) * rem_games) if g > 0 else 0
                ros_sv = int((sv / g) * rem_games) if g > 0 and sv > 0 else 0
                proj_end = f"{so + ros_so} K" + (f" / {sv + ros_sv} SV" if sv > 0 else "")
                
                # --- 📈 買低賣高回歸模組 ---
                fip = round(((13*hr + 3*bb - 2*so) / ip_math) + 3.15, 2)
                luck_score = 0
                if era - fip > 0.8: luck_score += 2
                elif fip - era > 0.8: luck_score -= 2
                
                ai_judgement = "🚀 逢低買進" if luck_score > 0 else ("📉 逢高賣出" if luck_score < 0 else "⚖️ 實力相符")
                reason = f"FIP 落差 ({fip:.2f})" if luck_score != 0 else "防禦率真實"
                
                projections_data.append({
                    "name": name.title(), "team": team_abbr, "pos": data["pos"],
                    "in_my_team": name in my_players,
                    "proj_end": proj_end,
                    "sch_games": games_next_7, "sch_opp": opp_str, "sch_grade": sch_grade,
                    "era": era, "xera": fip, "ai_judgment": ai_judgement, "report": reason,
                    "sort_score": abs(luck_score) * 10 + (1 if name in my_players else 0)
                })

        # 排序：有異常預警的排前面，自己隊上的也稍微優先
        projections_data.sort(key=lambda x: x['sort_score'], reverse=True)
        return {"status": "success", "data": projections_data[:60]}
        
    except Exception as e:
        return {"status": "error", "message": f"預測引擎錯誤: {str(e)}"}
    
@app.get("/fantasy/prospects")
def get_prospects(level: str = "AAA", p_type: str = "打者", year: Optional[int] = None):
    if year is None: year = datetime.now().year
    """🌟 Fantasy 農場大物雷達 (小聯盟潛力新秀球探評分)"""
    try:
        # 小聯盟層級 ID：AAA = 11, AA = 12
        sport_id = 11 if level == "AAA" else 12
        group = 'hitting' if p_type == '打者' else 'pitching'
        url = f"https://statsapi.mlb.com/api/v1/stats?stats=season&group={group}&sportId={sport_id}&season={year}&limit=100"
        res = requests.get(url, timeout=10).json()
        
        prospects = []
        for item in res.get('stats', [])[0].get('splits', []):
            player_name = item.get('player', {}).get('fullName', 'Unknown')
            team_name = item.get('team', {}).get('name', 'Unknown')
            pos = item.get('position', {}).get('abbreviation', 'UNK')
            st = item.get('stat', {})
            
            grades = {}
            is_aaa = (level == 'AAA')
            
            if p_type == "打者":
                if st.get('plateAppearances', 0) < 50: continue
                avg = float(st.get('avg', '.000'))
                ops = float(st.get('ops', '.000'))
                sb = int(st.get('stolenBases', 0))
                obp = float(st.get('obp', '.000'))
                hr = int(st.get('homeRuns', 0))
                
                grades['Hit'] = 75 if avg >= 0.320 else 65 if avg >= 0.300 else 55 if avg >= 0.280 else 45 if avg >= 0.250 else 35
                grades['Power'] = 80 if ops >= 1.000 else 70 if ops >= 0.900 else 60 if ops >= 0.800 else 50 if ops >= 0.700 else 40
                grades['Run'] = 75 if sb >= 25 else 60 if sb >= 15 else 50 if sb >= 5 else 40
                grades['Discipline'] = 75 if obp >= 0.400 else 60 if obp >= 0.360 else 50 if obp >= 0.330 else 40
                
                fv = int((grades['Hit'] * 0.3 + grades['Power'] * 0.4 + grades['Run'] * 0.1 + grades['Discipline'] * 0.2) / 5) * 5
                grades['FV'] = int(min(80, max(20, fv + (5 if is_aaa else 0))))
                
                eta = "本季隨時" if grades['FV'] >= 55 and is_aaa else ("擴編期" if is_aaa else ("明年春訓" if grades['FV'] >= 60 else "季中升 3A"))
                stash = "🔥 放進名單" if grades['FV'] >= 60 else ("👀 密切關注" if grades['FV'] >= 50 else "⏳ 暫不需理會")
                
                prospects.append({
                    "name": player_name, "team": team_name, "pos": pos,
                    "fv": grades['FV'], "eta": eta, "stash": stash,
                    "hit": grades['Hit'], "power": grades['Power'], "run": grades['Run'], "discipline": grades['Discipline'],
                    "ops": ops, "hr": hr
                })
                
            else: # 投手
                ip_math, outs = parse_innings(st.get('inningsPitched', '0'))
                if ip_math < 20: continue
                
                k9 = (float(st.get('strikeOuts', 0)) / ip_math) * 9 if ip_math > 0 else 9.0
                bb9 = (float(st.get('baseOnBalls', 0)) / ip_math) * 9 if ip_math > 0 else 3.5
                whip = float(st.get('whip', '1.30'))
                era = float(st.get('era', '4.00'))
                
                grades['Stuff'] = 80 if k9 >= 12.5 else 70 if k9 >= 11.0 else 60 if k9 >= 9.5 else 50 if k9 >= 8.0 else 40
                grades['Control'] = 75 if bb9 <= 1.8 else 65 if bb9 <= 2.5 else 50 if bb9 <= 3.5 else 40 if bb9 <= 4.5 else 30
                grades['Command'] = 75 if whip <= 1.00 else 65 if whip <= 1.15 else 50 if whip <= 1.30 else 40
                
                fv = int((grades['Stuff'] * 0.5 + grades['Control'] * 0.3 + grades['Command'] * 0.2) / 5) * 5
                grades['FV'] = int(min(80, max(20, fv + (5 if is_aaa else 0))))
                
                eta = "本季隨時" if grades['FV'] >= 55 and is_aaa else ("擴編期" if is_aaa else ("明年春訓" if grades['FV'] >= 60 else "季中升 3A"))
                stash = "🔥 放進名單" if grades['FV'] >= 60 else ("👀 密切關注" if grades['FV'] >= 50 else "⏳ 暫不需理會")
                
                prospects.append({
                    "name": player_name, "team": team_name, "pos": pos,
                    "fv": grades['FV'], "eta": eta, "stash": stash,
                    "stuff": grades['Stuff'], "control": grades['Control'], "command": grades['Command'],
                    "era": era, "whip": whip
                })
        
        # 依球探評分排序
        prospects.sort(key=lambda x: x['fv'], reverse=True)
        return {"status": "success", "data": prospects[:30]}
    except Exception as e:
        return {"status": "error", "message": f"獲取農場資料失敗: {str(e)}"}

import json
import os

FANTASY_DB_FILE = "fantasy_db.json"
AL_TEAMS = ["New York Yankees", "Boston Red Sox", "Houston Astros", "Toronto Blue Jays", "Baltimore Orioles", "Tampa Bay Rays", "Chicago White Sox", "Cleveland Guardians", "Detroit Tigers", "Kansas City Royals", "Minnesota Twins", "Los Angeles Angels", "Athletics", "Oakland Athletics", "Seattle Mariners", "Texas Rangers"]
NL_TEAMS = ["Los Angeles Dodgers", "Atlanta Braves", "Philadelphia Phillies", "New York Mets", "Chicago Cubs", "Cincinnati Reds", "Miami Marlins", "Washington Nationals", "Arizona Diamondbacks", "Colorado Rockies", "San Diego Padres", "San Francisco Giants", "Milwaukee Brewers", "St. Louis Cardinals", "Pittsburgh Pirates"]

# 快取全聯盟球員名單 (給前端下拉選單自動完成使用)
_cached_mlb_players = []

@app.get("/fantasy/players-list")
def get_all_players_list():
    """📋 獲取全聯盟球員清單 (供自動完成下拉選單使用)"""
    global _cached_mlb_players
    if _cached_mlb_players:
        return {"status": "success", "data": _cached_mlb_players}
    try:
        url = "https://statsapi.mlb.com/api/v1/stats?stats=season&group=hitting,pitching&playerPool=ALL&season=2026&limit=1500"
        res = requests.get(url, timeout=10).json()
        plist = []
        seen = set()
        
        for item in res.get('stats', []):
            group = item.get('group', {}).get('displayName', '').lower()
            for split in item.get('splits', []):
                name = split.get('player', {}).get('fullName')
                if not name: continue
                
                # 🔥 搜尋清單大谷條款
                if name == "Shohei Ohtani":
                    if group == "hitting": 
                        name = "Shohei Ohtani (Batter)"
                    else: 
                        name = "Shohei Ohtani (Pitcher)"
                
                if name not in seen:
                    seen.add(name)
                    plist.append({
                        "name": name,
                        "team": split.get('team', {}).get('name', 'FA'),
                        "pos": split.get('position', {}).get('abbreviation', 'UTIL')
                    })
                    
        _cached_mlb_players = plist
        return {"status": "success", "data": plist}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# 🔥 完整 14 項打者 & 13 項投手自訂計分權重 (對照 Streamlit 原版)
DEFAULT_WEIGHTS = {
    "hitter": {
        "R": 3.0, "H": 2.0, "1B": 3.0, "2B": 6.0, "3B": 10.0, "HR": 15.0, 
        "RBI": 2.0, "SB": 5.0, "BB": 2.0, "HBP": 3.0, "K": -2.0, "E": -3.0, 
        "CYC": 20.0, "SLAM": 30.0
    },
    "pitcher": {
        "W": 20.0, "L": -10.0, "SHO": 15.0, "SV": 8.0, "OUT": 1.0, 
        "H": -1.0, "ER": -3.0, "HR": -5.0, "BB": -1.0, "HBP": -2.0, 
        "K": 4.0, "WP": -3.0, "HLD": 3.0, "QS": 10.0, "BSV": -10.0
    }
}
# ☁️ 1. 自動讀取 .streamlit/secrets.toml 裡面的 FIREBASE_URL
FIREBASE_URL = "https://real-fantasy-web-default-rtdb.firebaseio.com/"

def get_firebase_url():
    global FIREBASE_URL
    if FIREBASE_URL: return FIREBASE_URL
    secrets_paths = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), ".streamlit", "secrets.toml"),
        os.path.join(".streamlit", "secrets.toml"), "secrets.toml"
    ]
    for path in secrets_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f.read().splitlines():
                        if "FIREBASE_URL" in line and "=" in line:
                            url = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if not url.endswith('/'): url += '/'
                            FIREBASE_URL = url
                            return FIREBASE_URL
            except: pass
    return FIREBASE_URL

# 🔄 2. Streamlit ↔ FastAPI 資料庫無痛升級與雙向對齊 (V3 支援多聯盟/多球隊)
def normalize_streamlit_db(data):
    if not isinstance(data, dict): data = {}
    
    if "leagues" not in data:
        l_name = data.pop("league_name", "👑 我的自創聯盟") or "👑 我的自創聯盟"
        t_name = data.pop("team_name", "總教練無敵夢幻隊") or "總教練無敵夢幻隊"
        raw_weights = data.pop("weights", {})
        h_w = {**DEFAULT_WEIGHTS["hitter"], **(raw_weights.get("hitter") or raw_weights.get("Hitter") or {})}
        p_w = {**DEFAULT_WEIGHTS["pitcher"], **(raw_weights.get("pitcher") or raw_weights.get("Pitcher") or {})}
        roster = data.pop("custom_roster", data.pop("my_roster", []))
        
        data["active_league"] = l_name
        data["active_team"] = t_name
        data["leagues"] = {
            l_name: { "weights": {"hitter": h_w, "pitcher": p_w}, "teams": { t_name: roster }, "ignored_players": [] }
        }
        
    if not data.get("active_league"): data["active_league"] = "👑 我的自創聯盟"
    if not data.get("active_team"): data["active_team"] = "總教練無敵夢幻隊"
    
    al, at = data["active_league"], data["active_team"]
    
    if al not in data["leagues"]: 
        data["leagues"][al] = {"weights": {"hitter": DEFAULT_WEIGHTS["hitter"], "pitcher": DEFAULT_WEIGHTS["pitcher"]}, "teams": {}, "ignored_players": []}
    if at not in data["leagues"][al]["teams"]: 
        data["leagues"][al]["teams"][at] = []
    
    # 💡 確保每個聯盟都有一個專屬的隱藏黑名單
    if "ignored_players" not in data["leagues"][al]:
        data["leagues"][al]["ignored_players"] = []
        
    data["league_name"], data["team_name"] = al, at
    data["weights"] = {
        "hitter": data["leagues"][al]["weights"]["hitter"], "pitcher": data["leagues"][al]["weights"]["pitcher"],
        "Hitter": data["leagues"][al]["weights"]["hitter"], "Pitcher": data["leagues"][al]["weights"]["pitcher"]
    }
    data["custom_roster"] = data["my_roster"] = data["leagues"][al]["teams"][at]
    return data

def get_active_context(db):
    al = db["active_league"]
    at = db["active_team"]
    return al, at, db["leagues"][al]["weights"], db["leagues"][al]["teams"][at]

# 💾 3. 讀取 / 寫入雙棲資料庫
def load_fantasy_db():
    fb_url, data = get_firebase_url(), None
    if fb_url:
        try:
            res = requests.get(f"{fb_url}{FANTASY_DB_FILE}", timeout=8)
            if res.status_code == 200 and res.json(): data = res.json()
        except: pass
    if not data and os.path.exists(FANTASY_DB_FILE):
        try:
            with open(FANTASY_DB_FILE, "r", encoding="utf-8") as f: data = json.load(f)
        except: pass
    if data: return normalize_streamlit_db(data)
    return normalize_streamlit_db({})

def save_fantasy_db(db_data):
    norm_data = normalize_streamlit_db(db_data)
    local_ok, fb_ok, fb_msg = False, False, "未找到 Firebase URL 設定"
    fb_url = get_firebase_url()

    try:
        with open(FANTASY_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(norm_data, f, ensure_ascii=False, indent=4)
        local_ok = True
    except: pass

    if fb_url:
        try:
            res = requests.put(f"{fb_url}{FANTASY_DB_FILE}", json=norm_data, timeout=8)
            if res.status_code in [200, 201]: fb_ok, fb_msg = True, "☁️ Firebase 雲端同步成功！"
            else: fb_msg = f"Firebase 拒絕 (代碼: {res.status_code})"
        except Exception as e: fb_msg = f"Firebase 連線失敗: {str(e)}"

    return local_ok, fb_ok, fb_msg


# --- 🔗 全新切換聯盟/球隊 API ---
class SwitchContextRequest(BaseModel):
    league: str
    team: str

@app.post("/fantasy/switch-context")
def switch_context(req: SwitchContextRequest):
    db = load_fantasy_db()
    db["active_league"] = req.league
    if req.team: 
        db["active_team"] = req.team
    else:
        # 如果只切換聯盟，自動選擇該聯盟的第一支球隊，若無則創建
        teams = db.get("leagues", {}).get(req.league, {}).get("teams", {})
        db["active_team"] = list(teams.keys())[0] if teams else "預設新球隊"
    save_fantasy_db(db)
    return {"status": "success"}

# --- 1. 我的球隊 API (支援層級回傳) ---
@app.get("/fantasy/yahoo-team")
def get_yahoo_fantasy_team():
    """🏆 獲取當前球隊陣容、賽程、預期週積分、Z-Score 體檢與 AI 智慧補強推薦"""
    daily_map, weekly_map = get_pts_maps()
    try:
        db = load_fantasy_db()
        al, at, weights, roster = get_active_context(db)
        
        real_stats = get_real_season_stats()
        matchups = get_today_matchups()
        active_roster, inactive_roster = [], []
        team_hr, team_sb, team_k, team_sv = 0, 0, 0, 0

        my_player_names = [p["name"].lower() for p in roster]

        for p in roster:
            # 動態校正球隊名稱
            p_data = real_stats.get(p["name"].lower())
            if p_data:
                p["team"] = p_data["team"]

            team_id = MLB_TEAM_IDS.get(p["team"])
            opp_info = matchups.get(team_id) if matchups else None
            
            if opp_info:
                opp_abbr = get_team_abbr(opp_info['opp_id'])
                p["today_game"] = f"vs {opp_abbr}" if opp_info["is_home"] else f"@ {opp_abbr}"
                p["has_game"] = True
            else:
                p["today_game"] = "Off"
                p["has_game"] = False

            if p_data:
                avg_pts = calc_real_fan_pts(p_data["type"], p_data["stat"], weights["hitter"], weights["pitcher"])
                # 💡 自動解析：如果名字是 "Shohei Ohtani (Batter)"，既找全名，也找乾淨的 "Shohei Ohtani"
                raw_n = p["name"].lower()
                clean_n = raw_n.split('(')[0].strip()
                p["actual_pts"] = daily_map.get(raw_n, daily_map.get(clean_n, 0.0))
                p["weekly_pts"] = weekly_map.get(raw_n, weekly_map.get(clean_n, 0.0))
                p["fan_pts"] = round(avg_pts * (6 if p_data["type"] == "hitter" else (1 if p.get("slot")=="SP" else 3)), 1)
                if p.get("status", "Active") == "Active":
                    team_hr += int(p_data["stat"].get("homeRuns", 0))
                    team_sb += int(p_data["stat"].get("stolenBases", 0))
                    team_k += int(p_data["stat"].get("strikeOuts", 0)) if p_data["type"] == "pitcher" else 0
                    team_sv += int(p_data["stat"].get("saves", 0))
            else:
                p["fan_pts"] = 0.0

            display_team = get_team_abbr(team_id) if team_id else p.get("team", "FA")
            p["team"] = display_team

            if "IL" in p.get("status", "") or p.get("slot") in ["BN", "IL", "NA"]:
                inactive_roster.append(p)
            else:
                active_roster.append(p)

        z_scores = {
            "HR (長打砲火)": min(99, int((team_hr / max(1, len(active_roster))) * 15 + 40)) if active_roster else 50,
            "SB (速度壘力)": min(99, int((team_sb / max(1, len(active_roster))) * 25 + 40)) if active_roster else 50,
            "K (三振壓制)": min(99, int((team_k / max(1, len(active_roster))) * 8 + 50)) if active_roster else 50,
            "SV+HLD (牛棚)": min(99, int((team_sv / max(1, len(active_roster))) * 30 + 40)) if active_roster else 50
        }

        leagues_info = { l: list(d["teams"].keys()) for l, d in db["leagues"].items() }
        strongest_cat = max(z_scores, key=z_scores.get) if z_scores else "-"
        weakest_cat = min(z_scores, key=z_scores.get) if z_scores else "-"

        # 🤖 AI 智慧推薦：根據弱點類別 (Weakest Category) 精準尋找未在陣容中的 2~3 位頂級補強標的
        recommendations = []
        if "HR" in weakest_cat:
            candidates = []
            for name, data in real_stats.items():
                if data["type"] == "hitter" and name not in my_player_names:
                    val = int(data["stat"].get("homeRuns", 0))
                    if val > 0: candidates.append((name, data, val))
            candidates.sort(key=lambda x: x[2], reverse=True)
            for name, data, val in candidates[:3]:
                recommendations.append({
                    "name": name.title(), "team": get_team_abbr(MLB_TEAM_IDS.get(data["team"])),
                    "pos": data["pos"], "reason": f"💣 本季高達 {val} 支 HR，可瞬間填補長打缺口"
                })

        elif "SB" in weakest_cat:
            candidates = []
            for name, data in real_stats.items():
                if data["type"] == "hitter" and name not in my_player_names:
                    val = int(data["stat"].get("stolenBases", 0))
                    if val > 0: candidates.append((name, data, val))
            candidates.sort(key=lambda x: x[2], reverse=True)
            for name, data, val in candidates[:3]:
                recommendations.append({
                    "name": name.title(), "team": get_team_abbr(MLB_TEAM_IDS.get(data["team"])),
                    "pos": data["pos"], "reason": f"⚡ 本季發動 {val} 次成功盜壘，極速補充速度戰力"
                })

        elif "K" in weakest_cat:
            candidates = []
            for name, data in real_stats.items():
                if data["type"] == "pitcher" and name not in my_player_names:
                    val = int(data["stat"].get("strikeOuts", 0))
                    if val > 0: candidates.append((name, data, val))
            candidates.sort(key=lambda x: x[2], reverse=True)
            for name, data, val in candidates[:3]:
                recommendations.append({
                    "name": name.title(), "team": get_team_abbr(MLB_TEAM_IDS.get(data["team"])),
                    "pos": data["pos"], "reason": f"🔥 本季狂飆 {val} 次 K，為頂級 K/9 威壓來源"
                })

        else: # SV+HLD
            candidates = []
            for name, data in real_stats.items():
                if data["type"] == "pitcher" and name not in my_player_names:
                    sv = int(data["stat"].get("saves", 0))
                    hld = int(data["stat"].get("holds", 0))
                    total = sv + hld
                    if total > 0: candidates.append((name, data, total, sv, hld))
            candidates.sort(key=lambda x: x[2], reverse=True)
            for name, data, total, sv, hld in candidates[:3]:
                recommendations.append({
                    "name": name.title(), "team": get_team_abbr(MLB_TEAM_IDS.get(data["team"])),
                    "pos": data["pos"], "reason": f"🛡️ 本季累積 {sv} SV + {hld} HLD，能穩定進補牛棚分數"
                })

        return {
            "status": "success",
            "league_name": al, "team_name": at, "all_leagues": leagues_info,
            "total_weekly_pts": round(sum(p["fan_pts"] for p in active_roster), 1),
            "active_roster": active_roster, "inactive_roster": inactive_roster,
            "z_scores": z_scores,
            "ai_diagnosis": {
                "strongest": strongest_cat, "weakest": weakest_cat,
                "advice": f"💡 AI 總管分析：您的團隊在『{strongest_cat}』表現優異，但『{weakest_cat}』是目前最大短板！建議直接從下方推薦標的中進行補強：",
                "recommendations": recommendations
            }
        }
    except Exception as e: return {"status": "error", "message": str(e)}

# --- 2. 簽下 (+) / 釋出 (-) / 編輯 (✏️) 球員 API ---
class IgnorePlayerRequest(BaseModel):
    name: str
class PlayerActionRequest(BaseModel):
    name: str; team: Optional[str] = "FA"; pos: Optional[str] = "UTIL"; slot: Optional[str] = "UTIL"
class PlayerUpdateRequest(BaseModel):
    name: str; slot: Optional[str] = None; pos: Optional[str] = None

@app.post("/fantasy/add-player")
def add_player_to_roster(req: PlayerActionRequest):
    db = load_fantasy_db()
    al, at, _, roster = get_active_context(db)
    if any(p["name"].lower() == req.name.lower() for p in roster): return {"status": "error", "message": f"{req.name} 已經在陣容中！"}
    roster.append({"slot": req.slot if req.slot else ("SP" if req.pos in ["SP","RP","P"] else "UTIL"), "name": req.name, "team": req.team if req.team else "FA", "pos": req.pos if req.pos else "UTIL", "status": "Active"})
    save_fantasy_db(db)
    return {"status": "success", "message": f"🎉 成功簽下 {req.name}！"}

@app.post("/fantasy/drop-player")
def drop_player_from_roster(req: PlayerActionRequest):
    db = load_fantasy_db()
    al, at, _, roster = get_active_context(db)
    db["leagues"][al]["teams"][at] = [p for p in roster if p["name"].lower() != req.name.lower()]
    save_fantasy_db(db)
    return {"status": "success", "message": f"👋 已釋出 {req.name}。"}


# --- 3, 4, 5, 6: 自由市場, 專家預警, 交易評估, 數據排行榜 API (套用 V3 讀取邏輯) ---
@app.post("/fantasy/ignore-player")
def ignore_player_in_market(req: IgnorePlayerRequest):
    """🚫 將球員加入聯盟黑名單 (從自由市場隱藏)"""
    db = load_fantasy_db()
    al = db["active_league"]
    if "ignored_players" not in db["leagues"][al]:
        db["leagues"][al]["ignored_players"] = []
        
    # 防止重複加入
    if req.name.lower() not in [p.lower() for p in db["leagues"][al]["ignored_players"]]:
        db["leagues"][al]["ignored_players"].append(req.name)
        save_fantasy_db(db)
        
    return {"status": "success", "message": f"已將 {req.name} 從市場移除"}

@app.get("/fantasy/free-agents")
def get_free_agents(p_type: str = "打者", pos_filter: str = "ALL", search_query: str = ""):
    daily_map, weekly_map = get_pts_maps()
    """🛒 自由市場：動態掃描聯盟球隊歸屬、隱藏黑名單與姓名快搜"""
    try:
        db = load_fantasy_db()
        al, at, weights, roster = get_active_context(db)
        
        # 1. 取得聯盟內「所有球隊」的球員歸屬字典
        league_rostered = {}
        for t_name, t_roster in db["leagues"][al]["teams"].items():
            for p in t_roster:
                league_rostered[p["name"].lower()] = t_name
                
        # 2. 取得手動去除的黑名單
        ignored_players = [p.lower() for p in db["leagues"][al].get("ignored_players", [])]
        
        real_stats = get_real_season_stats()
        matchups = get_today_matchups()
        fa_list = []
        target_type = "hitter" if p_type == "打者" else "pitcher"
        
        # 💡 將前端傳來的搜尋字串轉為小寫，方便做關鍵字比對
        sq = search_query.strip().lower()
        
        for name, data in real_stats.items():
            if data["type"] == target_type:
                
                # ==========================================
                # 🔍 搜尋過濾：有輸入字串時，名字不符的直接跳過
                # ==========================================
                if sq and sq not in name:
                    continue

                # 先取得球員原本的守備位置 (防止打者找不到 pos)
                pos = data.get("pos", "UTIL")

                # 如果是投手，進行先發/後援/終結者的智慧角色判定
                if target_type == "pitcher":
                    st = data.get("stat", {})
                    p_g = int(st.get("gamesPlayed", 0))
                    p_gs = int(st.get("gamesStarted", 0))
                    p_sv = int(st.get("saves", 0))
                            
                    if p_sv >= 4: 
                        pos = "CP"
                    elif p_gs > (p_g / 2) and p_gs > 0: 
                        pos = "SP"
                    elif p_gs >= 3 and (p_g - p_gs) >= 5: 
                        pos = "SP/RP"
                    else: 
                        pos = "RP"
                            
                    data["pos"] = pos # 更新回資料，讓前端畫面顯示正確守位

                # 守位過濾判斷
                if pos_filter != "ALL":
                    if pos_filter == "OF" and pos not in ["OF", "LF", "CF", "RF"]: 
                        continue
                    elif pos_filter == "RP" and pos not in ["RP", "CP", "CL", "SP/RP"]: 
                        continue
                    elif pos_filter == "SP" and pos not in ["SP", "SP/RP"]:
                        continue
                    elif pos_filter not in ["OF", "RP", "SP"] and pos != pos_filter: 
                        continue

                # 🔴 需求 2：排除使用者手動去除的球員
                if name.lower() in ignored_players:
                    continue
                    
                pa_or_ip = int(data["stat"].get("plateAppearances", 0)) if target_type == "hitter" else float(data["stat"].get("inningsPitched", 0))
                
                # 💡 若總教練「沒有搜尋」，才過濾掉上場次數太少 (<10) 的球員
                # 也就是說，如果有搜尋，就算是剛升上大聯盟的小將也找得到！
                if not sq and pa_or_ip < 10: 
                    continue 
                
                # 🔴 需求 1：偵測聯盟狀態
                rostered_team = league_rostered.get(name.lower())
                if rostered_team == at:
                    continue # 自己隊上的球員直接隱藏不顯示
                    
                is_fa = not bool(rostered_team)
                league_status = f"🛑 已被 {rostered_team} 選走" if rostered_team else "✅ 自由 (FA)"
                
                # 計算球場環境 (防呆取用)
                team_id = get_team_id(data["team"])
                opp_info = matchups.get(team_id) if matchups else None
                if opp_info:
                    opp_abbr = get_team_abbr(opp_info['opp_id'])
                    opp_str = f"vs {opp_abbr}" if opp_info["is_home"] else f"@ {opp_abbr}"
                    home_team_id = team_id if opp_info["is_home"] else opp_info['opp_id']
                    pf = PARK_FACTORS.get(get_team_abbr(home_team_id), {"OPS": 1.00, "HR": 1.00, "ERA": 1.00})
                    
                    if target_type == "hitter":
                        boost = round((pf.get("OPS", 1.00) - 1.0) * 100)
                        env_str = f"⛰️ 打者天堂 ({'+' if boost > 0 else ''}{boost}%)" if boost > 0 else (f"🛡️ 投手球場 ({boost}%)" if boost < 0 else "⚖️ 中性")
                    else:
                        boost = round((1.0 - pf.get("ERA", 1.00)) * 100)
                        env_str = f"🛡️ 投手加成 ({'+' if boost > 0 else ''}{boost}%)" if boost > 0 else (f"🌋 容易挨打 ({boost}%)" if boost < 0 else "⚖️ 中性")
                else:
                    opp_str = "OFF"
                    env_str = "-"

                avg_pts = calc_real_fan_pts(target_type, data["stat"], weights["hitter"], weights["pitcher"])
                exp_g = 6 if target_type == "hitter" else (1 if data["pos"] == "SP" else 3)
                proj_pts = round(avg_pts * exp_g, 1)
                raw_n = name.lower()
                clean_n = raw_n.split('(')[0].strip()
                actual_pts = weekly_map.get(raw_n, weekly_map.get(clean_n, 0.0))
                # 💡 若總教練有指定搜尋 (sq) 或者 預期分數 > 2.0，就顯示出來
                if sq or proj_pts > 2.0:
                    fa_list.append({
                        "name": name.title(), "team": data["team"], "pos": data["pos"],
                        "expected_games": exp_g, "opponents": opp_str, "platoon_advantage": env_str,
                        "projected_pts": proj_pts,"actual_pts": actual_pts,
                        "league_status": league_status, "is_fa": is_fa
                    })
                    
        fa_list.sort(key=lambda x: x['projected_pts'], reverse=True)
        return {"status": "success", "data": fa_list[:50]}
    except Exception as e: 
        return {"status": "error", "message": str(e)}
    
@app.get("/fantasy/expert-warning")
def get_expert_warning(p_type: str = "打者"):
    try:
        db = load_fantasy_db()
        _, _, _, roster = get_active_context(db)
        my_players = [p["name"].lower() for p in roster]
        real_stats, expert_data = get_real_season_stats(), []
        
        for name, data in real_stats.items():
            st = data["stat"]
            if p_type == "打者" and data["type"] == "hitter" and int(st.get('plateAppearances', 0)) >= 50:
                avg, babip = float(st.get('avg', '.000')), float(st.get('babip', '.000'))
                luck = -2 if (babip > 0.340 and avg > 0.280) else (2 if (babip < 0.260 and avg < 0.250) else 0)
                if luck != 0: expert_data.append({"player": name.title(), "team": data["team"], "pos": data["pos"], "ba": avg, "xba": round(avg + (0.300 - babip)*0.5, 3), "in_my_team": name in my_players, "ai_judgment": "🚀 逢低買進" if luck>0 else "📉 逢高賣出", "report": f"BABIP 異常 ({babip:.3f})"})
            elif p_type == "投手" and data["type"] == "pitcher" and float(str(st.get('inningsPitched', '0')).split('.')[0]) >= 20:
                era, hr, bb, so, ip = float(st.get('era', '4.00')), int(st.get('homeRuns',0)), int(st.get('baseOnBalls',0)), int(st.get('strikeOuts',0)), float(str(st.get('inningsPitched')).split('.')[0])
                fip = round(((13*hr + 3*bb - 2*so) / ip) + 3.15, 2)
                luck = 2 if era - fip > 1.0 else (-2 if fip - era > 1.0 else 0)
                if luck != 0: expert_data.append({"player": name.title(), "team": data["team"], "pos": data["pos"], "era": era, "xera": fip, "in_my_team": name in my_players, "ai_judgment": "🚀 逢低買進" if luck>0 else "📉 逢高賣出", "report": f"FIP 差距大 ({fip:.2f})"})
        return {"status": "success", "data": expert_data[:40]}
    except Exception as e: return {"status": "error", "message": str(e)}

@app.post("/fantasy/trade-analyzer")
def analyze_trade(trade: TradeRequest):
    try:
        real_stats, db = get_real_season_stats(), load_fantasy_db()
        _, _, weights, _ = get_active_context(db)
        give_pts, rec_pts = 0.0, 0.0
        
        # 💡 新增：用來統計雙方各項傳統數據的總和
        give_totals = {"HR": 0, "SB": 0, "RBI": 0, "R": 0, "K(投)": 0, "W": 0, "SV": 0}
        rec_totals  = {"HR": 0, "SB": 0, "RBI": 0, "R": 0, "K(投)": 0, "W": 0, "SV": 0}

        def add_to_totals(totals, data):
            st = data["stat"]
            if data["type"] == "hitter":
                totals["HR"] += int(st.get("homeRuns", 0))
                totals["SB"] += int(st.get("stolenBases", 0))
                totals["RBI"] += int(st.get("rbi", 0))
                totals["R"] += int(st.get("runs", 0))
            else:
                totals["K(投)"] += int(st.get("strikeOuts", 0))
                totals["W"] += int(st.get("wins", 0))
                totals["SV"] += int(st.get("saves", 0))

        # 計算送出球員
        for p in trade.give_players:
            data = real_stats.get(p.strip().lower())
            if data: 
                give_pts += calc_real_fan_pts(data["type"], data["stat"], weights["hitter"], weights["pitcher"]) * (6 if data["type"]=="hitter" else 2)
                add_to_totals(give_totals, data)
                
        # 計算獲得球員
        for p in trade.receive_players:
            data = real_stats.get(p.strip().lower())
            if data: 
                rec_pts += calc_real_fan_pts(data["type"], data["stat"], weights["hitter"], weights["pitcher"]) * (6 if data["type"]=="hitter" else 2)
                add_to_totals(rec_totals, data)
                
        delta = rec_pts - give_pts
        
        # 💡 新增：計算各項數據的「變化差值」 (獲得 - 送出)
        diff = {k: rec_totals[k] - give_totals[k] for k in give_totals}
        
        gains = {k: v for k, v in diff.items() if v > 0}
        losses = {k: v for k, v in diff.items() if v < 0}
        
        # 抓出賺最多與虧最多的前兩項數據
        sorted_gains = sorted(gains.items(), key=lambda x: x[1], reverse=True)
        sorted_losses = sorted(losses.items(), key=lambda x: x[1]) # 負最多的排前面
        
        gain_str = ", ".join([f"{k} (+{v})" for k, v in sorted_gains[:2]]) if sorted_gains else "無顯著得益"
        loss_str = ", ".join([f"{k} ({v})" for k, v in sorted_losses[:2]]) if sorted_losses else "無顯著犧牲"

        if delta > 15: grade, verdict = "A+", "🏆 搶劫級交易！利用真實數據精算，獲得壓倒性升級！"
        elif delta > 5: grade, verdict = "A", "🟢 極佳補強。"
        elif delta > -5: grade, verdict = "B", "⚖️ 雙贏交易。"
        elif delta > -15: grade, verdict = "C", "⚠️ 稍微吃虧。"
        else: grade, verdict = "F", "🚨 災難級交易！千萬不要按同意！"
        
        return {
            "status": "success", 
            "grade": grade, 
            "verdict": verdict, 
            "delta_score": round(delta, 1), 
            "gain_category": gain_str, 
            "loss_category": loss_str, 
            "ai_advice": "已根據雙方本季累計真實數據，交叉比對您聯盟的特殊計分權重。"
        }
    except Exception as e: return {"status": "error", "message": str(e)}

@app.get("/fantasy/settings")
def get_fantasy_settings():
    db = load_fantasy_db()
    al, at, weights, _ = get_active_context(db)
    return {"status": "success", "data": {"league_name": al, "team_name": at, "weights": weights}}

class FantasySettingsRequest(BaseModel):
    league_name: str; team_name: str; weights: dict

@app.post("/fantasy/settings")
def update_fantasy_settings(req: FantasySettingsRequest):
    db = load_fantasy_db()
    al, at = db["active_league"], db["active_team"]
    
    # 支援重新命名當前聯盟或球隊
    nl, nt = req.league_name.strip(), req.team_name.strip()
    if al != nl:
        db["leagues"][nl] = db["leagues"].pop(al)
        db["active_league"], al = nl, nl
    if at != nt:
        db["leagues"][al]["teams"][nt] = db["leagues"][al]["teams"].pop(at)
        db["active_team"], at = nt, nt
        
    db["leagues"][al]["weights"] = req.weights
    local_ok, fb_ok, fb_msg = save_fantasy_db(db)
    if local_ok and fb_ok: return {"status": "success", "message": f"✅ 本機與 {fb_msg}"}
    elif local_ok and not fb_ok: return {"status": "warning", "message": f"⚠️ 本機存檔成功，雲端失敗: {fb_msg}"}
    else: return {"status": "error", "message": "❌ 嚴重錯誤：本機與雲端皆存檔失敗！"}

# 🚀 全域真實數據快取引擎 (加入 4 小時自動更新 TTL 機制)
_cached_season_stats = {"timestamp": None, "data": None}

def get_real_season_stats(year=None):
    global _cached_season_stats
    now = datetime.now()
    
    # 💡 檢查快取是否存在，且是否未超過 4 小時 (14400 秒)
    cached_ts = _cached_season_stats["timestamp"]
    cached_data = _cached_season_stats["data"]
    
    if cached_ts and cached_data and (now - cached_ts).total_seconds() < 14400:
        return cached_data
    
    # 💡 動態抓取真實世界當前的年份 (解決寫死年份抓不到資料的問題)
    if not year:
        year = now.year
        
    try:
        url_h = f"https://statsapi.mlb.com/api/v1/stats?stats=season&group=hitting&playerPool=ALL&season={year}&limit=1000"
        url_p = f"https://statsapi.mlb.com/api/v1/stats?stats=season&group=pitching&playerPool=ALL&season={year}&limit=1000"
        res_h = requests.get(url_h, timeout=10).json()
        res_p = requests.get(url_p, timeout=10).json()
        stats = {}
        
        # 處理打者數據
        if 'stats' in res_h:
            for item in res_h['stats'][0].get('splits', []):
                name = item['player']['fullName'].lower()
                
                # 🔥 打者大谷條款
                if name == "shohei ohtani":
                    name = "shohei ohtani (batter)"
                    
                stats[name] = {"type": "hitter", "stat": item['stat'], "team": item.get('team',{}).get('name','FA'), "pos": item.get('position',{}).get('abbreviation','UTIL')}
                
        # 處理投手數據
        if 'stats' in res_p:
            for item in res_p['stats'][0].get('splits', []):
                name = item['player']['fullName'].lower()
                
                # 🔥 投手大谷條款
                if name == "shohei ohtani":
                    name = "shohei ohtani (pitcher)"
                    
                stats[name] = {"type": "pitcher", "stat": item['stat'], "team": item.get('team',{}).get('name','FA'), "pos": item.get('position',{}).get('abbreviation','P')}
                
        # 💡 寫入最新快取，並蓋上現在的時間戳記
        _cached_season_stats["timestamp"] = now
        _cached_season_stats["data"] = stats
        return stats
    except Exception as e: 
        print(f"真實數據載入警告: {e}")
        # 🛡️ 終極防呆：如果 MLB API 剛好掛掉，退而求其次回傳舊快取，不要讓畫面空白
        return cached_data if cached_data else {}
def calc_real_fan_pts(p_type, stat, w_hit, w_pit, special_events=None):
    """
    計算真實 Fantasy 積分 (支援硬核計分：QS, BSV, WP, HLD, 等)
    """
    if special_events is None:
        special_events = {"cyc": 0, "slam": 0}

    if p_type == "hitter":
        g = int(stat.get('gamesPlayed', 1)) or 1
        h = int(stat.get('hits', 0))
        b2 = int(stat.get('doubles', 0))
        b3 = int(stat.get('triples', 0))
        hr = int(stat.get('homeRuns', 0))
        b1 = max(0, h - b2 - b3 - hr)
        
        pts = (
            b1 * w_hit.get("1B", 3.0) +
            b2 * w_hit.get("2B", 6.0) +
            b3 * w_hit.get("3B", 10.0) +
            hr * w_hit.get("HR", 15.0) +
            h * w_hit.get("H", 2.0) +  # 只要打安打，除了壘打數，還能額外拿到 H 的 2 分！
            int(stat.get('rbi', 0)) * w_hit.get("RBI", 2.0) +
            int(stat.get('runs', 0)) * w_hit.get("R", 3.0) +
            int(stat.get('stolenBases', 0)) * w_hit.get("SB", 5.0) +
            int(stat.get('baseOnBalls', 0)) * w_hit.get("BB", 2.0) +
            int(stat.get('hitByPitch', 0)) * w_hit.get("HBP", 3.0) +
            int(stat.get('strikeOuts', 0)) * w_hit.get("K", -2.0) +
            int(stat.get('errors', 0)) * w_hit.get("E", -3.0) +
            special_events.get("cyc", 0) * w_hit.get("CYC", 20.0) +
            special_events.get("slam", 0) * w_hit.get("SLAM", 30.0)
        )
        return pts / g
    else:
        g = int(stat.get('gamesPlayed', 1)) or 1
        # 解決局數的小數點問題 (全面採用統一解析引擎)
        ip, outs = parse_innings(stat.get('inningsPitched', '0'))
        
        pts = (
            int(stat.get('wins', 0)) * w_pit.get("W", 20.0) +
            int(stat.get('losses', 0)) * w_pit.get("L", -10.0) +
            int(stat.get('shutouts', 0)) * w_pit.get("SHO", 15.0) +
            int(stat.get('saves', 0)) * w_pit.get("SV", 8.0) +
            outs * w_pit.get("OUT", 1.0) +
            int(stat.get('hits', 0)) * w_pit.get("H", -1.0) +
            int(stat.get('earnedRuns', 0)) * w_pit.get("ER", -3.0) +
            int(stat.get('homeRuns', 0)) * w_pit.get("HR", -5.0) +
            int(stat.get('baseOnBalls', 0)) * w_pit.get("BB", -1.0) +
            int(stat.get('hitBatsmen', 0)) * w_pit.get("HBP", -2.0) +
            int(stat.get('strikeOuts', 0)) * w_pit.get("K", 4.0) +
            int(stat.get('wildPitches', 0)) * w_pit.get("WP", -3.0) +
            int(stat.get('holds', 0)) * w_pit.get("HLD", 3.0) +
            int(stat.get('qualityStarts', 0)) * w_pit.get("QS", 10.0) +
            int(stat.get('blownSaves', 0)) * w_pit.get("BSV", -10.0)
        )
        return pts / g

_STATCAST_CACHE = {}

# --- 5. 數據排行榜 API (支援全套 14項打者/13項投手自訂計分) ---
# ⚠️ 已經移除 @lru_cache(maxsize=2)，改用智能計時快取
def get_statcast_data(year: int):
    now = datetime.now()
    
    # 💡 檢查記憶體是否有快取，且快取時間是否未超過 6 小時 (21600 秒)
    if year in _STATCAST_CACHE:
        cache_time, cached_data = _STATCAST_CACHE[year]
        if (now - cache_time).total_seconds() < 21600:
            return cached_data  # 直接回傳快取的 (hit_data, pit_data)

    hit_data, pit_data = {}, {}
    try:
        # 1. 抓取全聯盟打者鷹眼預期數據與擊球品質
        df_exp_h = statcast_batter_expected_stats(year, 10)
        df_ev_h = statcast_batter_exitvelo_barrels(year, 10)
        
        if not df_exp_h.empty:
            for _, r in df_exp_h.iterrows():
                hit_data[int(r['player_id'])] = {
                    "xba": f"{r.get('est_ba', 0):.3f}", 
                    "xwoba": f"{r.get('est_woba', 0):.3f}"
                }
        if not df_ev_h.empty:
            for _, r in df_ev_h.iterrows():
                pid = int(r['player_id'])
                if pid not in hit_data: hit_data[pid] = {}
                hit_data[pid].update({
                    "hard_hit": f"{r.get('ev95percent', 0):.1f}%", 
                    "barrel": f"{r.get('brl_percent', 0):.1f}%"
                })
                
        # 2. 抓取全聯盟投手鷹眼預期數據與擊球品質
        df_exp_p = statcast_pitcher_expected_stats(year, 10)
        df_ev_p = statcast_pitcher_exitvelo_barrels(year, 10)
        
        if not df_exp_p.empty:
            for _, r in df_exp_p.iterrows():
                pit_data[int(r['player_id'])] = {
                    "xba": f"{r.get('est_ba', 0):.3f}", 
                    "xwoba": f"{r.get('est_woba', 0):.3f}"
                }
        if not df_ev_p.empty:
            for _, r in df_ev_p.iterrows():
                pid = int(r['player_id'])
                if pid not in pit_data: pit_data[pid] = {}
                pit_data[pid].update({
                    "hard_hit": f"{r.get('ev95percent', 0):.1f}%", 
                    "barrel": f"{r.get('brl_percent', 0):.1f}%"
                })
    except Exception as e:
        print(f"Statcast 資料載入警告: {e}")
        
    # 💡 抓取完成！將最新數據寫入快取，並蓋上現在的時間戳記
    _STATCAST_CACHE[year] = (now, (hit_data, pit_data))
    
    return hit_data, pit_data

@app.get("/fantasy/rankings")
def get_fantasy_rankings(timeframe: str = "本季", p_type: str = "打者", year: int = 2026, league: str = "MLB", pos_filter: str = "ALL"):
    """📊 全聯盟排行榜：包含原版進階數據公式推算 (加入極致防呆與解除人數封印)"""
    try:
        db = load_fantasy_db()
        _, _, weights, _ = get_active_context(db)
        w_hitter = weights.get("hitter", DEFAULT_WEIGHTS["hitter"])
        w_pitcher = weights.get("pitcher", DEFAULT_WEIGHTS["pitcher"])

        if year == 2026: year = datetime.now().year
        
        hit_sc_data, pit_sc_data = get_statcast_data(year)
        group = 'hitting' if p_type == '打者' else 'pitching'
        
        # ==========================================
        # 🔥 1. 解除人數與打席限制，讓前端拿到全量名單
        # ==========================================
        stats_param = "season"
        min_pa = 0   # 🚨 降為 0，抓取全聯盟所有人
        min_ip = 0.0 # 🚨 降為 0.0，抓取全聯盟所有人
        
        if timeframe and "季" not in timeframe and "season" not in timeframe.lower():
            today = datetime.now()
            end_date_str = today.strftime("%m/%d/%Y")
            if "7" in timeframe: start_date_str = (today - timedelta(days=7)).strftime("%m/%d/%Y")
            elif "15" in timeframe: start_date_str = (today - timedelta(days=15)).strftime("%m/%d/%Y")
            elif "30" in timeframe or "月" in timeframe: start_date_str = (today - timedelta(days=30)).strftime("%m/%d/%Y")
            else: start_date_str = None
                
            if start_date_str:
                stats_param = f"byDateRange&startDate={start_date_str}&endDate={end_date_str}"

        # 把 limit 拉高到 1500，確保沒人漏掉
        url = f"https://statsapi.mlb.com/api/v1/stats?stats={stats_param}&season={year}&group={group}&sportId=1&playerPool=ALL&limit=1500"
        res = requests.get(url, timeout=10).json()
        splits = res.get('stats', [])[0].get('splits', []) if res.get('stats') else []
        
        # ==========================================
        # 🛡️ 2. 建立防呆轉型護盾，防止 MLB API 爛資料搞垮伺服器
        # ==========================================
        def safe_int(v):
            try: return int(float(v)) if v is not None and str(v).strip() != '' else 0
            except: return 0
            
        def safe_float(v):
            try: return float(v) if v is not None and str(v).strip() not in ['-.--', '.---', ''] else 0.0
            except: return 0.0

        fielding_errors = {}
        if p_type == '打者':
            try:
                f_url = f"https://statsapi.mlb.com/api/v1/stats?stats={stats_param}&season={year}&group=fielding&sportId=1&limit=2000"
                f_res = requests.get(f_url, timeout=5).json()
                for fs in f_res.get('stats', [{}])[0].get('splits', []):
                    pid = fs.get('player', {}).get('id')
                    fielding_errors[pid] = fielding_errors.get(pid, 0) + safe_int(fs.get('stat', {}).get('errors', 0))
            except: pass

        rank_list = []

        for item in splits:
            player_id = item.get('player', {}).get('id')
            player_name = item.get('player', {}).get('fullName', 'Unknown')
            team_name = item.get('team', {}).get('name', 'FA')
            pos = item.get('position', {}).get('abbreviation', 'UTIL' if p_type == '打者' else 'P')
            st = item.get('stat', {})
            
           # ==========================================
            # 💡 終極升級 1：精準辨識 SP, RP, CL (加入局數防呆機制)
            # ==========================================
            if p_type == "投手":
                gs = safe_int(st.get('gamesStarted', 0))
                g = safe_int(st.get('gamesPlayed', st.get('games', 1)))
                sv = safe_int(st.get('saves', 0))
                
                # 預先抓取局數，用來換算每場負擔的局數
                # 直接呼叫引擎，同時取得計算用局數 (ip_math) 與出局數 (outs)
                ip_math, outs = parse_innings(st.get('inningsPitched', '0'))
                
                if gs > 0 and gs >= (g / 2.0):
                    pos = "SP"
                elif sv >= 1:
                    pos = "CL"
                elif g > 0 and (ip_math / g) >= 3.0:
                    pos = "SP"  # 🚨 神級防呆：就算 API 偷懶不給先發次數，只要平均每場吃 3 局以上，絕對是先發！
                else:
                    pos = "RP"
            
            if league == "AL" and team_name not in AL_TEAMS: continue
            if league == "NL" and team_name not in NL_TEAMS: continue
            
           # ==========================================
            # 💡 終極升級 2：無敵過濾器 (中英雙語通吃)
            # ==========================================
            if pos_filter and str(pos_filter).strip() != "" and str(pos_filter).upper().strip() != "ALL":
                pf_raw = str(pos_filter).upper().strip()
                
                # 🚨 神級關鍵字擷取：不管前端傳 "先發投手"、"SP" 還是 "SP (先發)"，通通精準命中！
                if "SP" in pf_raw or "先發" in pf_raw: pf = "SP"
                elif "RP" in pf_raw or "後援" in pf_raw or "中繼" in pf_raw: pf = "RP"
                elif "CL" in pf_raw or "終結" in pf_raw or "救援" in pf_raw: pf = "CL"
                elif "OF" in pf_raw or "外野" in pf_raw: pf = "OF"
                elif "P" in pf_raw or "投手" in pf_raw: pf = "P"
                else: pf = pf_raw

                if pf == "P":
                    if pos not in ["SP", "RP", "CL", "P"]: continue
                elif pf == "OF":
                    if pos not in ["OF", "LF", "CF", "RF"]: continue
                elif pf == "RP":
                    if pos not in ["RP", "CL"]: continue # 找後援時，終結者也一起列入檢閱
                else:
                    if pos != pf: continue  # 嚴格一對一比對

            if p_type == "打者":
                pa = safe_int(st.get('plateAppearances', 0))
                if pa < min_pa: continue
                
                ab = safe_int(st.get('atBats', 0))
                r = safe_int(st.get('runs', 0))
                h = safe_int(st.get('hits', 0))
                b2 = safe_int(st.get('doubles', 0))
                b3 = safe_int(st.get('triples', 0))
                hr = safe_int(st.get('homeRuns', 0))
                b1 = max(0, h - b2 - b3 - hr)
                rbi = safe_int(st.get('rbi', 0))
                sb = safe_int(st.get('stolenBases', 0))
                bb = safe_int(st.get('baseOnBalls', 0))
                hbp = safe_int(st.get('hitByPitch', 0))
                k = safe_int(st.get('strikeOuts', 0))
                e = fielding_errors.get(player_id, 0)
                
                avg = safe_float(st.get('avg', 0))
                ops = safe_float(st.get('ops', 0))
                obp = safe_float(st.get('obp', 0))

                k_pct_val = (k / pa) * 100 if pa > 0 else 0
                k_pct = f"{round(k_pct_val, 1)}%"
                bb_pct = f"{round((bb / pa) * 100, 1)}%" if pa > 0 else "0%"
                
                woba_val = (0.69*bb + 0.72*hbp + 0.89*b1 + 1.27*b2 + 1.62*b3 + 2.10*hr) / pa if pa > 0 else 0.0
                woba = f"{woba_val:.3f}"
                wrc_plus = int((woba_val / 0.315) * 100) if pa > 0 else 0

                sc = hit_sc_data.get(player_id, {})
                xwoba_str = sc.get('xwoba', '-')
                xwoba_num = safe_float(xwoba_str) if xwoba_str != '-' else 0.315

                whiff = f"{round(k_pct_val * 1.15, 1)}%"
                chase = f"{round(28.5 - (xwoba_num * 10), 1)}%"
                
                ground_outs = safe_int(st.get('groundOuts', 0))
                air_outs = safe_int(st.get('airOuts', 0))
                total_b_outs = ground_outs + air_outs
                gb_pct = f"{round((ground_outs / total_b_outs) * 100, 1)}%" if total_b_outs > 0 else "0%"
                
                war_val = (((wrc_plus - 100) * pa / 8000) + (sb * 0.04) + (pa * 0.002))
                war = f"{round(war_val, 1)}"

                fan_pts = (b1*w_hitter.get("1B",3.0) + b2*w_hitter.get("2B",6.0) + b3*w_hitter.get("3B",10.0) + hr*w_hitter.get("HR",15.0) + h*w_hitter.get("H",2.0) + rbi*w_hitter.get("RBI",2.0) + r*w_hitter.get("R",3.0) + sb*w_hitter.get("SB",5.0) + bb*w_hitter.get("BB",2.0) + hbp*w_hitter.get("HBP",3.0) + k*w_hitter.get("K",-2.0) + e*w_hitter.get("E",-3.0))

                rank_list.append({
                    "name": player_name, "team": team_name, "pos": pos,
                    "pa": pa, "ab": ab, "r": r, "h": h, "b1": b1, "b2": b2, "b3": b3, "hr": hr,
                    "rbi": rbi, "sb": sb, "bb": bb, "hbp": hbp, "k": k, "e": e,
                    "avg": avg, "ops": ops, "obp": obp,
                    "woba": woba, "wrc_plus": wrc_plus, "xwoba": xwoba_str, "xba": sc.get('xba', '-'),
                    "hard_hit": sc.get('hard_hit', '-'), "barrel": sc.get('barrel', '-'), 
                    "chase": chase, "whiff": whiff, "gb": gb_pct, "war": war, "k_pct": k_pct, "bb_pct": bb_pct,
                    "fan_pts": fan_pts
                })

            else:
                ip_math, outs = parse_innings(st.get('inningsPitched', '0'))

                if ip_math < min_ip: continue

                w = safe_int(st.get('wins', 0))
                l = safe_int(st.get('losses', 0))
                sho = safe_int(st.get('shutouts', 0))
                sv = safe_int(st.get('saves', 0))
                h_hits = safe_int(st.get('hits', 0))
                r = safe_int(st.get('runs', 0))
                er = safe_int(st.get('earnedRuns', 0))
                hr = safe_int(st.get('homeRuns', 0))
                bb = safe_int(st.get('baseOnBalls', 0))
                hbp = safe_int(st.get('hitBatsmen', 0))
                k = safe_int(st.get('strikeOuts', 0))
                
                wp = safe_int(st.get('wildPitches', 0))
                hld = safe_int(st.get('holds', 0))
                qs = safe_int(st.get('qualityStarts', 0))
                bsv = safe_int(st.get('blownSaves', 0))
                
                pc = safe_int(st.get('numberOfPitches', st.get('pitchesThrown', 0)))
                bf = safe_int(st.get('battersFaced', 0))

                era = safe_float(st.get('era', 0))
                whip = safe_float(st.get('whip', 0))
                ba = safe_float(st.get('avg', 0))
                
                fip = round(((13*hr + 3*(bb+hbp) - 2*k) / ip_math) + 3.10, 2) if ip_math > 0 else 0.00
                diff = f"{(era - fip):+.2f}"
                k_pct_val = (k / bf) * 100 if bf > 0 else 0
                k_pct = f"{round(k_pct_val, 1)}%"
                bb_pct = f"{round((bb / bf) * 100, 1)}%" if bf > 0 else "0%"

                whiff = f"{round(k_pct_val * 1.15, 1)}%"
                
                ground_outs = safe_int(st.get('groundOuts', 0))
                air_outs = safe_int(st.get('airOuts', 0))
                total_p_outs = ground_outs + air_outs
                gb_pct = f"{round((ground_outs / total_p_outs) * 100, 1)}%" if total_p_outs > 0 else "0%"
                
                war_val = ((((4.20 - fip) * ip_math / 9) / 10) + (ip_math * 0.008))
                war = f"{round(war_val, 1)}"

                sc = pit_sc_data.get(player_id, {})

                # 💡 終極修復：把 xERA 的數據導正！
                raw_xwoba = sc.get('xwoba', '-')
                try:
                    # 若原始資料庫有 xera 就用 xera，若沒有，我們就用 xwOBA 動態換算！
                    # (公式：將球員的 xwOBA 除以聯盟平均 0.315，再乘上聯盟平均防禦率 3.50)
                    calc_xera = round((float(raw_xwoba) / 0.316) * 3.50, 2) if raw_xwoba != '-' else '-'
                except:
                    calc_xera = '-'
                
                final_xera = sc.get('xera', calc_xera)

                fan_pts = (w*w_pitcher.get("W",20.0) + l*w_pitcher.get("L",-10.0) + sho*w_pitcher.get("SHO",15.0) + sv*w_pitcher.get("SV",8.0) + outs*w_pitcher.get("OUT",1.0) + h_hits*w_pitcher.get("H",-1.0) + er*w_pitcher.get("ER",-3.0) + hr*w_pitcher.get("HR",-5.0) + bb*w_pitcher.get("BB",-1.0) + hbp*w_pitcher.get("HBP",-2.0) + k*w_pitcher.get("K",4.0) + wp*w_pitcher.get("WP",-3.0) + hld*w_pitcher.get("HLD",3.0) + qs*w_pitcher.get("QS",10.0) + bsv*w_pitcher.get("BSV",-10.0))

                rank_list.append({
                    "name": player_name, "team": team_name, "pos": pos,
                    "w": w, "l": l, "sho": sho, "sv": sv, "outs": outs, "ip": round(ip_math, 1),
                    "h": h_hits, "r": r, "er": er, "hr": hr, "bb": bb, "hbp": hbp, "k": k,
                    "wp": wp, "hld": hld, "qs": qs, "bsv": bsv, "pc": pc,
                    "era": era, 
                    "xera": final_xera, # 🚨 這裡終於放對了！
                    "whip": whip, "k_pct": k_pct, "bb_pct": bb_pct,
                    "fip": fip, "ba": ba, "xba": sc.get('xba', '-'), "diff": diff,
                    "hard_hit": sc.get('hard_hit', '-'), "barrel": sc.get('barrel', '-'), 
                    "whiff": whiff, "gb": gb_pct, "war": war,
                    "fan_pts": fan_pts
                })

        rank_list.sort(key=lambda x: x['fan_pts'], reverse=True)
        # 🔥 3. 永遠不刪減！把全聯盟 800 多人完整送給網頁！
        return {"status": "success", "data": rank_list}

    except Exception as e:
        return {"status": "error", "message": f"獲取排行榜失敗: {str(e)}"}
@lru_cache(maxsize=200)
def fetch_player_special_events(player_id, year=2024):
    """
    🔍 透過 Gamelog API 掃描單一球員當季是否達成 CYC (完全打擊) 與 SLAM (滿貫砲)
    """
    special = {"cyc": 0, "slam": 0}
    try:
        # 1. 抓取 Gamelog 判定 CYC
        url_gamelog = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=gamelog&group=hitting&season={year}"
        res_gl = requests.get(url_gamelog, timeout=4).json()
        
        if res_gl.get('stats'):
            for game in res_gl['stats'][0].get('splits', []):
                st = game.get('stat', {})
                h = int(st.get('hits', 0))
                b2 = int(st.get('doubles', 0))
                b3 = int(st.get('triples', 0))
                hr = int(st.get('homeRuns', 0))
                b1 = h - b2 - b3 - hr
                
                # 單場同時具備 1B, 2B, 3B, HR 判定為完全打擊！
                if b1 >= 1 and b2 >= 1 and b3 >= 1 and hr >= 1:
                    special["cyc"] += 1

        # 2. 抓取滿壘情境數據 (Men On - Bases Loaded) 判定 SLAM
        url_splits = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=statSplits&sitCodes=menOn&group=hitting&season={year}"
        res_sp = requests.get(url_splits, timeout=4).json()
        
        if res_sp.get('stats'):
            for split in res_sp['stats'][0].get('splits', []):
                if split.get('split', {}).get('code') == 'mB': # mB 代表 Bases Loaded (滿壘)
                    special["slam"] += int(split.get('stat', {}).get('homeRuns', 0))

    except Exception as e:
        print(f"特別成就抓取異常 ({player_id}): {e}")
        
    return special
@app.get("/mvp-cyyoung")
def get_mvp_cyyoung(year: int = 2026):
    """👑 獲取全聯盟 MVP 與 🏆 賽揚獎 (AL/NL) 大數據預測排行榜"""
    try:
        if year == 2026:
            year = datetime.now().year
            
        url_h = f"https://statsapi.mlb.com/api/v1/stats?stats=season&group=hitting&playerPool=ALL&season={year}&limit=500"
        url_p = f"https://statsapi.mlb.com/api/v1/stats?stats=season&group=pitching&playerPool=ALL&season={year}&limit=500"
        
        res_h = requests.get(url_h, timeout=10).json()
        res_p = requests.get(url_p, timeout=10).json()
        
        al_mvp, nl_mvp = [], []
        al_cy, nl_cy = [], []
        
        # 1. 處理打者 MVP 評分 (綜合 OPS, HR, RBI, SB, AVG)
        if res_h.get('stats'):
            for item in res_h['stats'][0].get('splits', []):
                p_name = item.get('player', {}).get('fullName', 'Unknown')
                t_name = item.get('team', {}).get('name', 'FA')
                pos = item.get('position', {}).get('abbreviation', 'UTIL')
                st = item.get('stat', {})
                
                pa = int(st.get('plateAppearances', 0))
                if pa < 30: continue
                
                hr = int(st.get('homeRuns', 0))
                rbi = int(st.get('rbi', 0))
                r = int(st.get('runs', 0))
                sb = int(st.get('stolenBases', 0))
                avg = float(st.get('avg', '.000'))
                ops = float(st.get('ops', '.000'))
                
                # 🔥 MVP 指數計算公式
                mvp_score = round(ops * 100 + hr * 2.5 + rbi * 1.2 + r * 1.0 + sb * 1.5 + avg * 50, 1)
                
                player_data = {
                    "name": p_name, "team": t_name, "pos": pos, "pa": pa,
                    "hr": hr, "rbi": rbi, "r": r, "sb": sb, "avg": avg, "ops": ops,
                    "mvp_score": mvp_score
                }
                
                if t_name in AL_TEAMS:
                    al_mvp.append(player_data)
                elif t_name in NL_TEAMS:
                    nl_mvp.append(player_data)

        # 2. 處理投手 Cy Young 賽揚指數評分 (綜合 ERA, WHIP, SO, 勝投, IP)
        if res_p.get('stats'):
            for item in res_p['stats'][0].get('splits', []):
                p_name = item.get('player', {}).get('fullName', 'Unknown')
                t_name = item.get('team', {}).get('name', 'FA')
                pos = item.get('position', {}).get('abbreviation', 'P')
                st = item.get('stat', {})
                
                ip_math, outs = parse_innings(st.get('inningsPitched', '0'))
                if ip_math < 15.0: continue
                
                w = int(st.get('wins', 0))
                l = int(st.get('losses', 0))
                so = int(st.get('strikeOuts', 0))
                sv = int(st.get('saves', 0))
                era = float(st.get('era', '4.00'))
                whip = float(st.get('whip', '1.30'))
                
                # 🔥 賽揚指數 (Cy Young Index) 計算公式
                cy_score = round((w * 12) + (so * 0.4) + (ip_math * 1.2) + (sv * 3) - (era * 15) - (whip * 25) + 80, 1)
                
                player_data = {
                    "name": p_name, "team": t_name, "pos": pos, "ip": round(ip_math, 1),
                    "w": w, "l": l, "so": so, "sv": sv, "era": era, "whip": whip,
                    "cy_score": cy_score
                }
                
                if t_name in AL_TEAMS:
                    al_cy.append(player_data)
                elif t_name in NL_TEAMS:
                    nl_cy.append(player_data)

        al_mvp.sort(key=lambda x: x['mvp_score'], reverse=True)
        nl_mvp.sort(key=lambda x: x['mvp_score'], reverse=True)
        al_cy.sort(key=lambda x: x['cy_score'], reverse=True)
        nl_cy.sort(key=lambda x: x['cy_score'], reverse=True)

        return {
            "status": "success",
            "year": year,
            "al_mvp": al_mvp[:10],
            "nl_mvp": nl_mvp[:10],
            "al_cy": al_cy[:10],
            "nl_cy": nl_cy[:10]
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
# ==========================================
# 🎯 取得「本日」與「本週」真實 Fantasy 積分雙引擎 (二刀流累加修復版)
# ==========================================
def get_pts_maps():
    try:
        import pytz
        # 採用美東時間，早上 10 點前算昨天的比賽 (對應台灣時間晚上 10 點)
        us_tz = pytz.timezone('US/Eastern')
        logical_today = datetime.now(us_tz) - timedelta(hours=10)
        daily_str = logical_today.strftime('%Y-%m-%d')
        weekly_start_str = (logical_today - timedelta(days=6)).strftime('%Y-%m-%d')
        
        db = load_fantasy_db()
        al = db.get("active_league")
        
        w_hit, w_pit = {}, {}
        if al and "leagues" in db and al in db["leagues"]:
            weights = db["leagues"][al].get("scoring_weights", {})
            w_hit = weights.get("hitter", {})
            w_pit = weights.get("pitcher", {})
            
        daily_map, weekly_map = {}, {}
        
        def fetch_and_map(group, start, end, target_map):
            url = f"https://statsapi.mlb.com/api/v1/stats?stats=byDateRange&group={group}&startDate={start}&endDate={end}&sportId=1&gameType=R&playerPool=ALL&limit=1500"
            res = requests.get(url, timeout=10).json()
            if res.get('stats'):
                for s in res['stats'][0].get('splits', []):
                    name = s.get('player', {}).get('fullName', '').lower()
                    if name:
                        p_type = "hitter" if group == "hitting" else "pitcher"
                        pts = calc_real_fan_pts(p_type, s.get('stat', {}), w_hit, w_pit)
                        g = int(s.get('stat', {}).get('gamesPlayed', 1)) or 1
                        total_pts = round(pts * g, 1)
                        
                        # 💡 核心修復 1：使用 "+=" 累加分數，避免投球 0 分蓋掉打擊 15 分
                        if name not in target_map:
                            target_map[name] = 0.0
                        target_map[name] += total_pts
                        
                        # 💡 核心修復 2：為大谷 (Ohtani) 建立打者與投手的分身 ID，讓前端精準抓取
                        if group == "hitting":
                            target_map[f"{name} (batter)"] = total_pts
                            target_map[f"{name} (hitter)"] = total_pts
                        else:
                            target_map[f"{name} (pitcher)"] = total_pts

        # 雙引擎同時抓取本日與本週
        fetch_and_map("hitting", daily_str, daily_str, daily_map)
        fetch_and_map("pitching", daily_str, daily_str, daily_map)
        fetch_and_map("hitting", weekly_start_str, daily_str, weekly_map)
        fetch_and_map("pitching", weekly_start_str, daily_str, weekly_map)

        return daily_map, weekly_map
    except Exception as e:
        print(f"🚨 雙引擎錯誤: {e}")
        return {}, {}

# ==========================================
# 🎯 接收前端儲存實際分數 (安全獨立版)
# ==========================================
@app.post("/fantasy/update-player")
def update_player_in_roster(req: UpdatePlayerRequest):
    try:
        db = load_fantasy_db()
        al = db.get("active_league")
        at = db.get("active_team")
        
        if not al or not at:
            return {"status": "error", "message": "尚未建立聯盟或球隊"}
            
        roster = db["leagues"][al]["teams"].get(at, [])
        for p in roster:
            if p["name"].lower() == req.name.lower():
                if req.slot is not None:
                    p["slot"] = req.slot
                    # 同步更新球員狀態 (先發/板凳/傷兵)
                    p["status"] = "Bench" if req.slot == "BN" else ("IL" if req.slot == "IL" else "Active")
                if req.pos is not None: p["pos"] = req.pos
                if req.real_pts is not None: p["real_pts"] = req.real_pts # 💡 存入真實分數
                
                save_fantasy_db(db)
                return {"status": "success"}
                
        return {"status": "error", "message": f"找不到球員: {req.name}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}