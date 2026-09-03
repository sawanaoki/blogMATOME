import os
import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import requests
from requests.auth import HTTPBasicAuth
from src.config import Config

class LivedoorPublisher:
    def __init__(
        self,
        livedoor_id: Optional[str] = None,
        api_key: Optional[str] = None,
        output_dir: Optional[Path] = None
    ):
        self.livedoor_id = livedoor_id or Config.LIVEDOOR_ID
        self.api_key = api_key or Config.LIVEDOOR_API_KEY
        self.output_dir = output_dir or Config.OUTPUT_DIR

    def is_configured(self) -> bool:
        """ライブドアブログのAPI連携に必要なIDとAPIキーが揃っているか"""
        return bool(self.livedoor_id and self.api_key)

    def post_article(
        self,
        title: str,
        content_html: str,
        categories: Optional[List[str]] = None,
        draft: bool = True
    ) -> Dict[str, Any]:
        """
        ライブドアブログのAtomPub API経由で記事を投稿（下書き または 公開）します。
        """
        if not self.is_configured():
            return {
                "success": False,
                "message": "ライブドアブログの ID または API Key が未設定です。設定画面または.envファイルを確認してください。"
            }

        endpoint = f"https://livedoor.blogcms.jp/atompub/{self.livedoor_id}/article"

        # カテゴリXML生成
        categories = categories or ["まとめ"]
        category_elements = "".join([f'<category term="{c}" />' for c in categories])
        draft_str = "yes" if draft else "no"

        # Atom XML リクエストボディ
        atom_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom"
       xmlns:app="http://www.w3.org/2007/app">
  <title>{title}</title>
  <content type="text/html"><![CDATA[{content_html}]]></content>
  {category_elements}
  <app:control>
    <app:draft>{draft_str}</app:draft>
  </app:control>
</entry>"""

        headers = {
            "Content-Type": "application/atom+xml; type=entry; charset=utf-8",
            "User-Agent": "LivedoorBlogAutoPublisher/1.0"
        }

        try:
            response = requests.post(
                endpoint,
                data=atom_xml.encode("utf-8"),
                headers=headers,
                auth=HTTPBasicAuth(self.livedoor_id, self.api_key),
                timeout=15
            )

            if response.status_code in [200, 201]:
                # 投稿成功時にローカルにも保存
                self.save_to_local(title, content_html, is_draft=draft)
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "message": f"ライブドアブログに正常に{'下書き保存' if draft else '公開投稿'}されました！",
                    "location": response.headers.get("Location", "")
                }
            else:
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "message": f"投稿エラー ({response.status_code}): {response.text}"
                }

        except Exception as e:
            return {
                "success": False,
                "message": f"通信エラーが発生しました: {e}"
            }

    def save_to_local(self, title: str, content_html: str, is_draft: bool = True) -> Path:
        """
        生成した記事をローカルの output/ ディレクトリにHTML形式で保存します。
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_"))[:30].strip()
        filename = f"{timestamp}_{safe_title}.html"
        file_path = self.output_dir / filename

        html_template = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.6; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #333; }}
  h1 {{ font-size: 24px; border-bottom: 2px solid #333; padding-bottom: 8px; }}
  .meta {{ color: #777; font-size: 14px; margin-bottom: 24px; }}
</style>
</head>
<body>
<h1>{title}</h1>
<div class="meta">保存日時: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 状態: {'下書き' if is_draft else '公開'}</div>
<hr/>
<div class="article-content">
{content_html}
</div>
</body>
</html>
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_template)

        return file_path
