# まとめブログ自動作成ツール 実装計画書

バズったXの投稿や最新ニュース（Yahoo!リアルタイム検索トレンド、Google News RSS）を収集し、Google Gemini APIを活用してまとめブログ風の記事（HTML形式）を自動生成し、ライブドアブログへの投稿（またはHTML出力）を簡単に行えるStreamlit Webアプリケーションを開発します。

---

## 1. 全体アーキテクチャ

```mermaid
graph TD
    subgraph DataCollection [情報収集層]
        Y[Yahoo!リアルタイム検索<br/>トレンド & ポスト収集]
        G[Google News RSS<br/>最新トピック & 記事収集]
    end

    subgraph Core [生成 & 変換層]
        P[プロンプトエンジニアリング<br/>まとめブログ風テンプレ]
        LLM[Google Gemini API<br/>記事タイトル/概要/反応まとめ/考察生成]
        HTML[リッチHTMLフォーマッタ<br/>見出し・引用・吹き出し装飾]
    end

    subgraph UI [ユーザーインターフェース]
        ST[Streamlit Web画面<br/>・話題選択<br/>・生成プレビュー<br/>・直接編集]
    end

    subgraph Publishing [出力 & 投稿]
        LD[ライブドアブログ<br/>AtomPub API投稿 (下書き/公開)]
        CP[ワンクリックHTMLコピー /<br/>ローカル保存]
    end

    DataCollection --> ST
    ST --> Core
    Core --> ST
    ST --> Publishing
```

---

## 2. ディレクトリ構成

```text
blogMATOME/
├── .env.example              # APIキー・設定テンプレート
├── requirements.txt          # 必要パッケージ一覧
├── app.py                    # Streamlit Webアプリ本体
├── src/
│   ├── __init__.py
│   ├── config.py             # 設定・環境変数管理
│   ├── collectors/           # 情報収集
│   │   ├── __init__.py
│   │   ├── yahoo_realtime.py # Yahoo!リアルタイム検索（トレンド＆話題ポスト）
│   │   └── google_news.py    # Google News RSSフィード取得
│   ├── generator/            # 記事生成 (Gemini)
│   │   ├── __init__.py
│   │   ├── gemini_client.py  # Gemini API クライアント
│   │   └── prompts.py        # まとめブログ用プロンプト定義
│   └── publisher/            # ブログ投稿
│       ├── __init__.py
│       └── livedoor_client.py# ライブドアブログ AtomPub API 連携
└── docs/
    └── summary_blog_generator/
        ├── task.md
        ├── implementation_plan.md
        └── walkthrough.md
```

---

## 3. 主要モジュールの詳細設計

### 3.1 データ収集 (Collectors)
- **`yahoo_realtime.py`**:
  - `get_trends()`: Yahoo!リアルタイム検索（`https://search.yahoo.co.jp/realtime`）のトレンド急上昇ワード一覧を抽出。
  - `get_topic_posts(keyword, count=15)`: 指定したトレンドワードや検索キーワードについて、Yahoo!リアルタイム検索結果からツイート本文、投稿日時等をスクレイピングで抽出。
- **`google_news.py`**:
  - `get_top_news(category="all")`: Google News RSS（`https://news.google.com/rss?hl=ja&gl=JP&ceid=JP:ja`）から最新の注目記事タイトルとリンクを取得。
  - `search_news(keyword)`: 特定のキーワードに関するニュース一覧を取得。

### 3.2 記事生成 (Generator)
- **`gemini_client.py`**:
  - Google Gemini API (`gemini-2.5-flash` または `gemini-1.5-flash` / `gemini-1.5-pro` を選択可能) を利用。
  - 収集したニュース記事の要約や、複数のXポストをインプットにして、自然で読み応えのあるまとめ記事を生成。
- **`prompts.py`**:
  - まとめブログ特有の構成（キャッチーなタイトル候補、事件や話題の概要・背景、ネットの反応（肯定・否定・ユーモア・考察の分類）、管理人の総括）を指示。
  - 出力はそのままライブドアブログに貼り付けられるよう、見出しタグ（`<h3>`）、強調（`<strong>`）、引用枠（`<blockquote>`）、レス番風・吹き出し風の装飾HTMLを生成。

### 3.3 ライブドアブログ投稿 (Publisher)
- **`livedoor_client.py`**:
  - ライブドアブログの AtomPub API (`https://livedoor.blogcms.jp/atom/blog/{livedoor_id}/article`) に対応。
  - WSSE認証またはBasic認証 (livedoor ID + API Key) による認証処理。
  - 下書き（Draft）または公開（Publish）モードを選択して投稿。
  - APIキー未設定時でも、ワンクリックでHTMLをクリップボードにコピーできる代替フローを提供。

### 3.4 Streamlit Web画面 (`app.py`)
- **ステップ1: 話題選び**
  - タブ1: Yahoo!リアルタイム検索（急上昇トレンドから選ぶ）
  - タブ2: Googleニュース（最新主要ニュースから選ぶ）
  - タブ3: 自由入力（気になるキーワードを入力して検索）
- **ステップ2: 収集データの確認・調整**
  - 収集されたニュース概要やXのポスト一覧を確認。不要なポストの除外や追加が可能。
  - 記事のトーン設定（「2ちゃんねるまとめ風」「一般的なニュースまとめ風」「ライトな解説風」など）。
- **ステップ3: 記事自動生成 & プレビュー**
  - Gemini APIで記事を生成。
  - リッチなHTMLプレビュー表示と、直接編集可能なテキストエリアを提供。
- **ステップ4: 投稿 / 出力**
  - 「ライブドアブログに下書き投稿」ボタン
  - 「HTMLをコピー」ボタン
  - ローカルへのHTML/Markdown保存

---

## 4. 検証計画 (Verification Plan)

### 自動/スクリプト検証
1. **データ収集テスト**:
   - `python -m src.collectors.yahoo_realtime` でトレンドおよびツイートテキストが取得できるかテスト。
   - `python -m src.collectors.google_news` でGoogle News RSSが正常にパースできるかテスト。
2. **Gemini API連携テスト**:
   - テスト用スクリプトでダミー収集データを渡し、Geminiが意図したHTMLフォーマットで返却するか検証。
3. **ライブドアAtomPubテスト**:
   - APIクライアントのXML生成およびリクエスト組み立ての単体テスト。

### 手動検証
1. Streamlitを起動し（`streamlit run app.py`）、ブラウザで画面操作を行い：
   - トレンド取得 → キーワード選択 → Xポスト・ニュース収集 → 記事生成 → プレビュー表示 の一連の流れを確認。
   - 生成されたHTMLの見栄えとコピー機能、下書き投稿機能の動作を確認。
