# ⚾ MLB 終極球探系統 (Fantasy Scout System)

這是一個專為硬核大聯盟球迷與 Fantasy Baseball 玩家打造的**個人化數據分析與球探預測平台**。
透過整合 MLB Stats API 與 Baseball Savant 進階數據，將傳統數據表昇華為具備「主動決策能力」的 AI 總管大腦。

## ✨ 核心戰力與特色 (Key Features)

* **🔥 Savant 等級全域動態熱圖**：自動將 PR 值極端的數據（如 xBA、Chase%、xERA）以上色與粗體高光標示，一眼看穿球員本質。
* **🧠 AI 專家預警系統 (Expert System)**：
  * **打者運氣濾網**：交叉比對實際打擊率與預期數據，精準抓出「假性高潮」與「運氣極佳」的球員。
  * **投手衰退雷達**：監控球速、轉速與用球負荷，在投手爆炸或受傷前提前發出紅燈警示。
* **🏟️ 動態球場校正引擎 (Park Factor)**：內建全大聯盟 30 座主場的環境參數，自動依據今日對戰球場（如 Coors Field 或是 T-Mobile Park）加權或下修預期表現。
* **⚔️ 血性優勢與對戰預測**：自動分析左右投相剋優勢，並提供每日賽程的雙方勝率與火力評估。
* **🏥 智能傷兵與名單濾網**：一鍵排除 15/60 天 IL 與整季報銷名單，並支援獨家「大谷條款（打者/投手拆分）」與「跨聯盟互斥認領」機制。
* **🔍 深度搜尋與外號系統**：可利用「盲劍客」、「二壘安打機器」等 AI 標籤快速篩選特定型態的球員。

## 🛠️ 技術架構 (Tech Stack)

* **Frontend & UI**: [Streamlit](https://streamlit.io/)
* **Data Processing**: Pandas, NumPy
* **Data Visualization**: Plotly
* **Data Sources**: [pybaseball](https://github.com/jldbc/pybaseball) (Statcast), MLB Stats API

## 🚀 部署與執行 (Getting Started)

本系統已針對 **Streamlit Community Cloud** 進行優化，具備完整的 `requirements.txt`。

若需於本機端執行，請在終端機輸入：
```bash
pip install -r requirements.txt
streamlit run app.py