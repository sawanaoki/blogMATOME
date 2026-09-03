import os
from pathlib import Path
from dotenv import load_dotenv

# プロジェクトルートの .env を読み込み
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

def get_setting(key: str, default: str = "") -> str:
    # 1. 環境変数 (.env) をチェック
    val = os.getenv(key)
    if val:
        return val
    # 2. Streamlit Secrets (クラウド環境) をチェック
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return default

class Config:
    # Gemini API
    GEMINI_API_KEY: str = get_setting("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = get_setting("GEMINI_MODEL", "gemini-3.8-flash")

    # ライブドアブログ
    LIVEDOOR_ID: str = get_setting("LIVEDOOR_ID", "")
    LIVEDOOR_API_KEY: str = get_setting("LIVEDOOR_API_KEY", "")
    LIVEDOOR_POST_DRAFT: bool = get_setting("LIVEDOOR_POST_DRAFT", "true").lower() in ("true", "1", "yes")

    # X (Twitter) API (将来拡張用)
    TWITTER_BEARER_TOKEN: str = get_setting("TWITTER_BEARER_TOKEN", "")
    TWITTER_API_KEY: str = get_setting("TWITTER_API_KEY", "")
    TWITTER_API_SECRET: str = get_setting("TWITTER_API_SECRET", "")
    TWITTER_ACCESS_TOKEN: str = get_setting("TWITTER_ACCESS_TOKEN", "")
    TWITTER_ACCESS_TOKEN_SECRET: str = get_setting("TWITTER_ACCESS_TOKEN_SECRET", "")

    # 出力先ディレクトリ (生成記事のバックアップ用)
    OUTPUT_DIR: Path = PROJECT_ROOT / "output"

# 出力ディレクトリが存在しない場合は作成
Config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
