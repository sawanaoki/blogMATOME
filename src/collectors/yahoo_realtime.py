import re
import urllib.parse
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

def fetch_yahoo_trends(max_count: int = 25) -> List[Dict[str, Any]]:
    """
    Yahoo!リアルタイム検索から現在の急上昇トレンドキーワード一覧（順位付き）を取得します。
    """
    url = "https://search.yahoo.co.jp/realtime"
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching Yahoo trends: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    raw_trends: List[Dict[str, Any]] = []
    seen_words = set()

    rank = 1
    for a in soup.find_all("a", href=re.compile(r"/realtime/search\?p=")):
        text = a.text.strip()
        # 先頭の数字やジャンル名をクリーンアップ
        cleaned = re.sub(r"^\d+\s*", "", text)
        cleaned = re.sub(r"^(アニメ・ゲーム|スポーツ|エンタメ|ビジネス|IT・科学|国内|地域|国際|グルメ)\s*", "", cleaned)
        cleaned = cleaned.strip()
        
        if (
            cleaned
            and len(cleaned) > 1
            and cleaned not in seen_words
            and not any(ng in cleaned for ng in ["もっと見る", "ヘルプ", "利用規約", "検索", "プライバシー", "ご意見"])
        ):
            seen_words.add(cleaned)
            href = a.get("href", "")
            full_url = "https://search.yahoo.co.jp" + href if href.startswith("/") else href
            
            raw_trends.append({
                "rank": rank,
                "word": cleaned,
                "url": full_url
            })
            rank += 1
            if len(raw_trends) >= max_count:
                break

    return raw_trends

def fetch_yahoo_topic_posts(keyword: str, max_count: int = 15) -> List[Dict[str, str]]:
    """
    指定キーワードでYahoo!リアルタイム検索を行い、関連するX（Twitter）の投稿テキストと投稿者情報を取得します。
    """
    encoded = urllib.parse.quote(keyword)
    url = f"https://search.yahoo.co.jp/realtime/search?p={encoded}"
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching topic posts for '{keyword}': {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    posts: List[Dict[str, str]] = []

    tweet_containers = soup.find_all("div", class_=re.compile(r"Tweet_Tweet__"))

    for tc in tweet_containers:
        # 本文 (pタグ)
        p_elem = tc.find("p")
        if not p_elem:
            body_elem = tc.find(class_=re.compile(r"Tweet_bodyWrap|Tweet_bodyContainer"))
            text = body_elem.get_text(separator=" ", strip=True) if body_elem else ""
        else:
            text = p_elem.get_text(separator=" ", strip=True)

        if not text or len(text) < 5:
            continue

        # 投稿者名・アカウント
        author_elem = tc.find(class_=re.compile(r"Tweet_author|Tweet_info"))
        author = author_elem.get_text(separator=" ", strip=True) if author_elem else "匿名"

        # リンク
        link_elem = tc.find("a", href=re.compile(r"twitter\.com|x\.com"))
        link = link_elem.get("href", "") if link_elem else ""

        posts.append({
            "author": author,
            "text": text,
            "link": link
        })

        if len(posts) >= max_count:
            break

    return posts

if __name__ == "__main__":
    trends = fetch_yahoo_trends(5)
    print("Trends:", [t["word"] for t in trends])
    if trends:
        sample_kw = trends[0]["word"]
        print(f"\nPosts for '{sample_kw}':")
        posts = fetch_yahoo_topic_posts(sample_kw, 3)
        for i, p in enumerate(posts, 1):
            print(f"[{i}] {p['author']}: {p['text'][:60]}...")
