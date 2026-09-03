import urllib.parse
from typing import List, Dict, Any, Optional
import feedparser

GOOGLE_NEWS_CATEGORIES = {
    "トップニュース": "https://news.google.com/rss?hl=ja&gl=JP&ceid=JP:ja",
    "国内": "https://news.google.com/rss/headlines/section/topic/NATION.ja_jp?hl=ja&gl=JP&ceid=JP:ja",
    "エンタメ": "https://news.google.com/rss/headlines/section/topic/ENTERTAINMENT.ja_jp?hl=ja&gl=JP&ceid=JP:ja",
    "テクノロジー": "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY.ja_jp?hl=ja&gl=JP&ceid=JP:ja",
    "ビジネス": "https://news.google.com/rss/headlines/section/topic/BUSINESS.ja_jp?hl=ja&gl=JP&ceid=JP:ja",
    "スポーツ": "https://news.google.com/rss/headlines/section/topic/SPORTS.ja_jp?hl=ja&gl=JP&ceid=JP:ja",
}

def fetch_google_news(category: str = "トップニュース", max_count: int = 15) -> List[Dict[str, Any]]:
    """
    指定カテゴリのGoogle News RSSから記事一覧を取得します。
    """
    url = GOOGLE_NEWS_CATEGORIES.get(category, GOOGLE_NEWS_CATEGORIES["トップニュース"])
    feed = feedparser.parse(url)
    
    articles = []
    for entry in feed.entries[:max_count]:
        articles.append({
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "published": entry.get("published", ""),
            "summary": entry.get("summary", ""),
            "source": entry.get("source", {}).get("title", "") if "source" in entry else ""
        })
    return articles

def search_google_news(query: str, max_count: int = 15) -> List[Dict[str, Any]]:
    """
    キーワードでGoogle Newsを検索し、記事一覧を取得します。
    """
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
    feed = feedparser.parse(url)
    
    articles = []
    for entry in feed.entries[:max_count]:
        articles.append({
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "published": entry.get("published", ""),
            "summary": entry.get("summary", ""),
            "source": entry.get("source", {}).get("title", "") if "source" in entry else ""
        })
    return articles

if __name__ == "__main__":
    print("Fetching top news...")
    news = fetch_google_news("トップニュース", max_count=3)
    for n in news:
        print(f"- {n['title']} ({n['published']})")
