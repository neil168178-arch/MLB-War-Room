import os
import sys
import subprocess

def run_streamlit():
    # 這裡確保只會執行一次 streamlit
    app_path = "app.py"
    # 使用 subprocess 執行，並傳遞環境變數標記
    env = os.environ.copy()
    env["STREAMLIT_RUNTIME"] = "True"
    
    # 啟動 streamlit，並指定不自動開啟瀏覽器(選用)，讓它在背景執行
    subprocess.run([sys.executable, "-m", "streamlit", "run", app_path], env=env)

if __name__ == "__main__":
    run_streamlit()