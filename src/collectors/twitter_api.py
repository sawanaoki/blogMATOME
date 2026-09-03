"""
X (Twitter) 公式 API v2 連携モジュール (拡張用スロット)

将来的にX Developer Portalで有料プラン（Basic / Pro等）を契約した際、
API認証情報を .env に設定することで、Xの公式API経由で話題のツイートやトレンドを
直接取得できるようにするための拡張用モジュールです。
"""

from typing import List, Dict, Any, Optional
import requests
from src.config import Config

class TwitterAPIClient:
    def __init__(
        self,
        bearer_token: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        access_token_secret: Optional[str] = None
    ):
        self.bearer_token = bearer_token or Config.TWITTER_BEARER_TOKEN
        self.api_key = api_key or Config.TWITTER_API_KEY
        self.api_secret = api_secret or Config.TWITTER_API_SECRET
        self.access_token = access_token or Config.TWITTER_ACCESS_TOKEN
        self.access_token_secret = access_token_secret or Config.TWITTER_ACCESS_TOKEN_SECRET

    def is_configured(self) -> bool:
        """APIキーやBearer Tokenが設定されているか確認"""
        return bool(self.bearer_token or (self.api_key and self.api_secret))

    def search_recent_tweets(self, query: str, max_results: int = 15) -> List[Dict[str, Any]]:
        """
        X API v2: 最近のツイート検索 (/2/tweets/search/recent)
        """
        if not self.is_configured():
            print("[TwitterAPIClient] X APIの認証情報が設定されていません。Yahoo!リアルタイム検索をご利用ください。")
            return []

        url = "https://api.twitter.com/2/tweets/search/recent"
        headers = {
            "Authorization": f"Bearer {self.bearer_token}"
        }
        params = {
            "query": f"{query} lang:ja -is:retweet",
            "max_results": min(max(max_results, 10), 100),
            "tweet.fields": "created_at,public_metrics,author_id",
            "expansions": "author_id",
            "user.fields": "username,name"
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code != 200:
                print(f"[TwitterAPIClient] エラー: {response.status_code} - {response.text}")
                return []

            data = response.json()
            tweets = data.get("data", [])
            users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}

            results = []
            for tw in tweets:
                author_id = tw.get("author_id")
                user = users.get(author_id, {})
                results.append({
                    "author": f"{user.get('name', 'ユーザー')} (@{user.get('username', '')})",
                    "text": tw.get("text", ""),
                    "link": f"https://x.com/{user.get('username', '_')}/status/{tw.get('id')}",
                    "likes": tw.get("public_metrics", {}).get("like_count", 0),
                    "retweets": tw.get("public_metrics", {}).get("retweet_count", 0)
                })
            return results
        except Exception as e:
            print(f"[TwitterAPIClient] リクエスト例外: {e}")
            return []

if __name__ == "__main__":
    client = TwitterAPIClient()
    print("Configured:", client.is_configured())
