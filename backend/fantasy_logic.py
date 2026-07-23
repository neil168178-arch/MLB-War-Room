import json
import os
import streamlit as st
import requests
import base64
import pandas as pd

# 聯盟球隊清單常數
AL_TEAMS = ["New York Yankees", "Boston Red Sox", "Houston Astros", "Toronto Blue Jays", "Baltimore Orioles", "Tampa Bay Rays", "Chicago White Sox", "Cleveland Guardians", "Detroit Tigers", "Kansas City Royals", "Minnesota Twins", "Los Angeles Angels", "Oakland Athletics", "Seattle Mariners", "Texas Rangers"]
NL_TEAMS = ["Los Angeles Dodgers", "Atlanta Braves", "Philadelphia Phillies", "New York Mets", "Chicago Cubs", "Cincinnati Reds", "Miami Marlins", "Washington Nationals", "Arizona Diamondbacks", "Colorado Rockies", "San Diego Padres", "San Francisco Giants", "Milwaukee Brewers", "St. Louis Cardinals", "Pittsburgh Pirates"]

# 🔥 專屬於全網單週排行與賽季排行的硬核寫實計分系統
HARDCORE_WEIGHTS = {
    'Hitter': {'R': 3.0, 'H': 2.0, '1B': 3.0, '2B': 6.0, '3B': 10.0, 'HR': 15.0, 'RBI': 2.0, 'SB': 5.0, 'BB': 2.0, 'HBP': 3.0, 'K': -2.0, 'E': -3.0, 'CYC': 20.0, 'SLAM': 30.0},
    'Pitcher': {'W': 20.0, 'L': -10.0, 'SHO': 15.0, 'SV': 8.0, 'OUT': 1.0, 'H': -1.0, 'ER': -3.0, 'HR': -5.0, 'BB': -1.0, 'HBP': -2.0, 'K': 4.0, 'WP': -3.0, 'HLD': 3.0, 'QS': 10.0, 'BSV': -10.0}
}

# 建立新聯盟時的預設值
FANTASY_WEIGHTS = {
    'Hitter': {'1B': 1.0, '2B': 2.0, '3B': 3.0, 'HR': 4.0, 'R': 1.0, 'RBI': 1.0, 'SB': 1.0, 'BB': 1.0, 'K': -1.0},
    'Pitcher': {'IP': 3.0, 'H': -1.0, 'ER': -2.0, 'BB': -1.0, 'K': 1.0, 'W': 5.0, 'L': -5.0, 'SV': 5.0, 'HLD': 2.0}
}

ALL_HITTER_CATS = ['R', 'H', '1B', '2B', '3B', 'HR', 'RBI', 'AVG', 'OBP', 'SLG', 'OPS', 'SB', 'CS', 'NSB', 'BB', 'IBB', 'HBP', 'TB', 'XBH', 'K', 'E', 'CYC', 'SLAM']
ALL_PITCHER_CATS = ['IP', 'OUT', 'W', 'L', 'SV', 'HLD', 'K', 'ER', 'H', 'BB', 'HBP', 'HR', 'WP', 'ERA', 'WHIP', 'K/9', 'K/BB', 'BSV', 'SVOP', 'QS', 'CG', 'SHO']

DB_FILE = "fantasy_db.json"

def load_db():
    """載入本地 JSON 資料庫"""
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: return {}
    return {}

def save_db(db_data):
    """儲存資料至本地 JSON 資料庫"""
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db_data, f, indent=4, ensure_ascii=False)

def get_eligible_players(pos, df_h, df_p):
    """取得符合特定守備位置的球員名單 (包含傷兵過濾機制)"""
    il_list = st.session_state.fantasy_db.get('real_il_players', []) if 'fantasy_db' in st.session_state else []
    
    # 若為板凳或受傷名單，則回傳所有打者與投手
    if pos in ['BN', 'IL', 'NA']: 
        return sorted(list(set(df_h['Player'].tolist() + df_p['Player'].tolist())))
        
    def check_pos(p_str, pos_target):
        plist = [p.strip() for p in str(p_str).split(',')]
        if pos_target == 'UTIL': return not any(p in ['SP', 'RP', 'CL', 'P'] for p in plist)
        if pos_target == 'P': return any(p in ['SP', 'RP', 'CL'] for p in plist)
        if pos_target == 'OF': return any(p in ['OF', 'RF', 'CF', 'LF'] for p in plist)
        if pos_target == 'IF': return any(p in ['1B', '2B', '3B', 'SS', 'IF'] for p in plist)
        if pos_target == 'C': return 'C' in plist
        # 👇 請在這裡加入這行：允許 RP 槽位接受 RP 或 CL
        if pos_target == 'RP': return any(p in ['RP', 'CL'] for p in plist)
        return pos_target in plist

    if pos in ['SP', 'RP', 'P']:
        valid_df = df_p[~df_p['Player'].isin(il_list)]
        return sorted(valid_df[valid_df['Position'].apply(lambda x: check_pos(x, pos))]['Player'].unique())
    else:
        valid_df = df_h[~df_h['Player'].isin(il_list)]
        return sorted(valid_df[valid_df['Position'].apply(lambda x: check_pos(x, pos))]['Player'].unique())

def recalculate_custom_score(df, p_type, scoring):
    """根據輸入的權重，重新精算 Fantasy 積分 (具備防呆轉型)"""
    df_out = df.copy()
    if p_type == '打者':
        h_weights = scoring.get('Hitter', {})
        for c in ['H', '2B', '3B', 'HR', 'R', 'RBI', 'SB', 'CS', 'BB', 'IBB', 'HBP', 'K', 'E', 'CYC', 'SLAM', 'AVG', 'OBP', 'SLG', 'OPS', 'XBH']:
            if c not in df_out.columns: df_out[c] = 0.0
            else: df_out[c] = pd.to_numeric(df_out[c], errors='coerce').fillna(0.0)
        
        df_out['1B'] = (df_out['H'] - df_out['2B'] - df_out['3B'] - df_out['HR']).clip(lower=0)
        if 'TB' in h_weights and 'TB' not in df_out.columns: df_out['TB'] = df_out['1B'] + 2*df_out['2B'] + 3*df_out['3B'] + 4*df_out['HR']
        if 'XBH' in h_weights and 'XBH' not in df_out.columns: df_out['XBH'] = df_out['2B'] + df_out['3B'] + df_out['HR']
        if 'NSB' in h_weights and 'NSB' not in df_out.columns: df_out['NSB'] = df_out['SB'] - df_out['CS']

        df_out['Fan_Pts'] = sum(df_out[cat] * weight for cat, weight in h_weights.items() if cat in df_out.columns)
    else:
        p_weights = scoring.get('Pitcher', {})
        for c in ['IP', 'IP_calc', 'W', 'L', 'SV', 'K', 'ER', 'R', 'H', 'BB', 'HLD', 'QS', 'CG', 'SHO', 'BSV', 'SVOP', 'ERA', 'WHIP', 'HR', 'HBP', 'WP']:
            if c not in df_out.columns: df_out[c] = 0.0
            else: df_out[c] = pd.to_numeric(df_out[c], errors='coerce').fillna(0.0)
        
        if 'OUT' not in df_out.columns or df_out['OUT'].sum() == 0:
            ip_source = df_out['IP_calc'] if 'IP_calc' in df_out.columns else df_out['IP']
            df_out['OUT'] = (ip_source * 3).round().astype(int)

        if 'K/9' in p_weights and 'K/9' not in df_out.columns: df_out['K/9'] = (df_out['K'] * 9) / df_out.get('IP_calc', df_out['IP']).clip(lower=1)
        if 'K/BB' in p_weights and 'K/BB' not in df_out.columns: df_out['K/BB'] = df_out['K'] / df_out['BB'].replace(0, 1)

        df_out['Fan_Pts'] = sum(df_out[cat] * weight for cat, weight in p_weights.items() if cat in df_out.columns)
                
    return df_out['Fan_Pts'].round(2)
# ==========================================
# 💾 專家系統：雙棲存檔引擎 (支援本機與 GitHub 雲端)
# ==========================================
def save_db(db_data, filename="fantasy_db.json"):
    """【V2.0】將 Fantasy 陣容即時同步至 Firebase 雲端資料庫 (光速版)"""
    
    # 偵測是否在雲端環境 (Secrets 是否有 Firebase 金鑰)
    if "FIREBASE_URL" in st.secrets:
        try:
            # 1. 取得資料庫網址並確保格式正確
            base_url = st.secrets["FIREBASE_URL"]
            if not base_url.endswith('/'):
                base_url += '/'
            
            # 2. 組合 API 網址 (Firebase 規定結尾必須是 .json)
            url = f"{base_url}{filename}"
            
            # 3. 發射給 Firebase 覆寫 (不需要轉 Base64，直接傳送 JSON 字典！)
            put_res = requests.put(url, json=db_data)
            
            if put_res.status_code in [200, 201]:
                return True
            else:
                st.error(f"⚠️ 雲端資料庫同步失敗，錯誤碼: {put_res.status_code}")
                return False
                
        except Exception as e:
            st.error(f"⚠️ 雲端存檔發生例外錯誤: {e}")
            return False

    # 如果沒有金鑰 (例如在本機端沒設定 secrets)，則自動退回一般本機存檔
    else:
        try:
            json_str = json.dumps(db_data, indent=4, ensure_ascii=False)
            with open(filename, "w", encoding="utf-8") as f:
                f.write(json_str)
            return True
        except Exception as e:
            st.error(f"本機存檔失敗: {e}")
            return False