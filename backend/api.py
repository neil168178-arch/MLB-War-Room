from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pybaseball 
import random # 用來暫時模擬進階運算

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🧠 建立一個「進階數據運算引擎」的專屬函數 (未來可替換成您寫好的 statcast 函數)
def get_advanced_stats(mlb_id: int):
    # 這裡利用 mlb_id 加上隨機數，模擬一個極具真實感的進階數據回傳
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
        
        if player_info.empty:
            return {"Error": f"資料庫中找不到 {player_name}！"}

        mlb_id = int(player_info['key_mlbam'].iloc[0])
        debut_year = int(player_info['mlb_played_first'].iloc[0])
        
        # 呼叫我們的進階數據引擎
        adv_stats = get_advanced_stats(mlb_id)
        
        # 將基本資料與進階資料一起打包送出！
        return {
            "Player_Name": f"{first_name.capitalize()} {last_name.capitalize()}",
            "MLB_ID": mlb_id,
            "Debut_Year": debut_year,
            "Advanced_Stats": adv_stats # 👈 這裡多夾帶了進階數據包
        }
        
    except Exception as e:
        return {"Error": f"後端運算發生錯誤: {str(e)}"}