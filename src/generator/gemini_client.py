import json
import re
from typing import Dict, Any, List, Optional
from google import genai
from google.genai import types
from src.config import Config
from src.generator.prompts import SUMMARY_BLOG_SYSTEM_PROMPT, SUMMARY_BLOG_USER_PROMPT_TEMPLATE

def format_admin_comment_html(comment: str) -> str:
    """
    管理人のひとことテキストを「俺的・はちま風」の装飾HTML枠に変換します。
    """
    if not comment or not comment.strip():
        return ""
    # 改行を <br> に変換
    formatted_comment = "<br>".join([c.strip() for c in comment.strip().split("\n") if c.strip()])
    return f"""
<!-- 管理人のひとこと枠 -->
<div style="background: #fff9db; border: 2px solid #fcc419; border-radius: 8px; padding: 18px; margin-top: 35px;">
  <p style="font-size: 1.1em; font-weight: bold; margin-top: 0; margin-bottom: 8px; color: #d9480f;">
    💬 管理人のひとこと・感想
  </p>
  <p style="margin: 0; line-height: 1.8; color: #212529;">
    {formatted_comment}
  </p>
</div>
"""

class GeminiGenerator:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or Config.GEMINI_API_KEY
        self.model_name = model or Config.GEMINI_MODEL
        self.client = None
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)

    def is_configured(self) -> bool:
        return bool(self.api_key and self.client)

    def generate_article(
        self,
        topic: str,
        news_summary: str = "",
        posts: Optional[List[Dict[str, str]]] = None,
        tone: str = "標準的なまとめブログ風（テンポよく読みやすい）"
    ) -> Dict[str, Any]:
        """
        トピック、ニュース、Xポスト群を元にまとめブログ記事を生成します。
        """
        if not self.is_configured():
            raise ValueError(
                "Gemini APIキーが設定されていません。.env ファイルまたは画面上で GEMINI_API_KEY を設定してください。"
            )

        posts = posts or []
        posts_text_list = []
        for idx, p in enumerate(posts, 1):
            author = p.get("author", "匿名")
            text = p.get("text", "")
            likes = p.get("likes", 0)
            rts = p.get("rts", 0)
            metric_str = f" [❤️ {likes:,}いいね / 🔁 {rts:,}RT]" if (likes or rts) else ""
            posts_text_list.append(f"[{idx}] {author}{metric_str}: {text}")
        posts_text = "\n".join(posts_text_list) if posts_text_list else "特になし（トピック情報をもとに構成してください）"

        user_content = SUMMARY_BLOG_USER_PROMPT_TEMPLATE.format(
            topic=topic,
            news_summary=news_summary if news_summary else "（ニュース本文なし・トピックキーワード中心）",
            posts_text=posts_text,
            tone=tone
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_content,
                config=types.GenerateContentConfig(
                    system_instruction=SUMMARY_BLOG_SYSTEM_PROMPT,
                    temperature=0.7,
                    response_mime_type="application/json"
                )
            )

            response_text = response.text.strip()
            cleaned_text = response_text
            if cleaned_text.startswith("```"):
                cleaned_text = re.sub(r"^```(?:json)?\s*", "", cleaned_text)
                cleaned_text = re.sub(r"\s*```$", "", cleaned_text)

            article_data = json.loads(cleaned_text)

            # 後方互換性と管理人の一言分離処理
            admin_comment = article_data.get("admin_comment", "")
            body_html = article_data.get("body_html", "")
            if not body_html and "content_html" in article_data:
                body_html = article_data["content_html"]

            article_data["body_html"] = body_html
            article_data["admin_comment"] = admin_comment
            article_data["content_html"] = body_html + format_admin_comment_html(admin_comment)

            return article_data

        except Exception as e:
            raise RuntimeError(f"Gemini APIによる記事生成中にエラーが発生しました: {e}")

if __name__ == "__main__":
    generator = GeminiGenerator()
    print("Gemini Configured:", generator.is_configured())
