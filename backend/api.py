from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pybaseball 
import random
from functools import lru_cache # 👈 引入快取魔法

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- (保持原樣) Scout 進階數據引擎 ---
def get_advanced_stats(mlb_id: int):
    random.seed(mlb_id) 
    return {
        "xwOBA": round(random.uniform(0.310, 0.420), 3),
        "xBA": round(random.uniform(0.240, 0.310), 3),
        "Exit_Velocity": round(random.uniform(88.0, 96.0), 1),
        "HardHit_Percent": round(random.uniform(35.0, 55.0), 1)
    }

@app.get("/scout-report/{player_name}")
def get_player_data(player_name: str):
    try:
        name_parts = player_name.strip().split(" ")
        first_name = name_parts[0] if len(name_parts) >= 2 else ""
        last_name = name_parts[-1]
        player_info = pybaseball.playerid_lookup(last_name, first_name)
        if player_info.empty: return {"Error": f"資料庫中找不到 {player_name}！"}
        mlb_id = int(player_info['key_mlbam'].iloc[0])
        return {
            "Player_Name": f"{first_name.capitalize()} {last_name.capitalize()}",
            "MLB_ID": mlb_id,
            "Debut_Year": int(player_info['mlb_played_first'].iloc[0]),
            "Advanced_Stats": get_advanced_stats(mlb_id) 
        }
    except Exception as e: return {"Error": str(e)}

# --- (保持原樣) Roster 我的陣容 ---
@app.get("/roster")
def get_my_roster():
    return {
        "team_name": "Dodgers Data Center",
        "manager": "總教練",
        "starters": [
            {"position": "DH", "name": "Shohei Ohtani", "status": "Active"},
            {"position": "RF", "name": "Mookie Betts", "status": "Active"},
            {"position": "1B", "name": "Freddie Freeman", "status": "Active"},
            {"position": "SP", "name": "Tyler Glasnow", "status": "Active"}
        ],
        "bench": [{"position": "OF", "name": "Teoscar Hernández", "status": "Bench"}, {"position": "SP", "name": "Yoshinobu Yamamoto", "status": "IL-15"}]
    }

# ==========================================
# 📊 新增：全聯盟進階數據 API (純血 Savant + 動態篩選)
# ==========================================
from pybaseball import statcast_batter_expected_stats
from functools import lru_cache

# 🚀 快取大升級：我們只根據「年份」去抓資料，並把門檻降到最低 (1個打席)，把所有人抓下來。
# 這樣使用者只要不換年份，調整打席數時就會「瞬間」跑出結果！
@lru_cache(maxsize=10)
def fetch_savant_stats_cached(year: int):
    return statcast_batter_expected_stats(year, 1)

@app.get("/league-stats")
def get_league_stats(year: int = 2023, min_pa: int = 400, sort_by: str = "est_woba"):
    try:
        df = fetch_savant_stats_cached(year)
        
        # 🛡️ 核心修正：在這裡用 Pandas 強制過濾打席，讓前端傳來的 min_pa 絕對生效！
        df_qualified = df[df['pa'] >= min_pa]
        
        if sort_by not in df_qualified.columns:
            sort_by = "est_woba"
            
        # 動態排序
        top_players = df_qualified.sort_values(by=[sort_by], ascending=False).head(50)
        
        result = []
        for _, row in top_players.iterrows():
            name_raw = str(row.get('last_name, first_name', 'Unknown'))
            if ", " in name_raw:
                last, first = name_raw.split(", ")
                clean_name = f"{first} {last}"
            else:
                clean_name = name_raw

            result.append({
                "Name": clean_name,
                "PA": int(row.get('pa', 0)),
                "xwOBA": round(float(row.get('est_woba', 0)), 3),
                "xBA": round(float(row.get('est_ba', 0)), 3),
                "xSLG": round(float(row.get('est_slg', 0)), 3)
            })
            
        return {"status": "success", "data": result}
        
    except Exception as e:
        return {"status": "error", "message": f"Savant 官方 API 連線異常: {str(e)}"}
