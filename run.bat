@echo off
chcp 65001 > nul
echo ========================================================
echo   まとめブログ自動作成ツール (Streamlit Webアプリ)
echo ========================================================
echo アプリケーションを起動しています...
python -m streamlit run app.py
pause
