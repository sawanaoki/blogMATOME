import streamlit as st
import json
from src.config import Config
from src.collectors.yahoo_realtime import fetch_yahoo_trends, fetch_yahoo_topic_posts
from src.collectors.google_news import fetch_google_news, search_google_news, GOOGLE_NEWS_CATEGORIES
from src.collectors.twitter_api import TwitterAPIClient
from src.generator.gemini_client import GeminiGenerator, format_admin_comment_html
from src.publisher.livedoor_client import LivedoorPublisher

# ページ設定
st.set_page_config(
    page_title="まとめブログ自動作成ツール",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# セッション状態の初期化
if "current_topic" not in st.session_state:
    st.session_state.current_topic = ""
if "news_summary" not in st.session_state:
    st.session_state.news_summary = ""
if "collected_posts" not in st.session_state:
    st.session_state.collected_posts = []
if "generated_article" not in st.session_state:
    st.session_state.generated_article = None

# ==========================================
# サイドバー: 設定
# ==========================================
st.sidebar.title("⚙️ 設定 & 連携")

with st.sidebar.expander("🔑 Google Gemini API 設定", expanded=True):
    gemini_key = st.text_input(
        "Gemini API Key",
        value=Config.GEMINI_API_KEY,
        type="password",
        help="Google AI Studioで取得したAPIキーを入力してください。"
    )
    model_choices = [
        "gemini-3.8-flash",
        "gemini-3.8-pro",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "✏️ 直接モデル名を入力"
    ]
    # 設定ファイルの値があれば初期インデックスを決定
    default_idx = 0
    if Config.GEMINI_MODEL in model_choices:
        default_idx = model_choices.index(Config.GEMINI_MODEL)
    
    selected_model_choice = st.selectbox(
        "モデル選択",
        model_choices,
        index=default_idx,
        help="最新世代の gemini-3.8-flash / gemini-3.8-pro を選択できます。"
    )

    if selected_model_choice == "✏️ 直接モデル名を入力":
        gemini_model = st.text_input("モデル名を入力:", value=Config.GEMINI_MODEL)
    else:
        gemini_model = selected_model_choice

with st.sidebar.expander("📝 ライブドアブログ設定", expanded=True):
    livedoor_id = st.text_input(
        "livedoor ID",
        value=Config.LIVEDOOR_ID,
        help="ライブドアブログのID（ログインIDまたはブログID）"
    )
    livedoor_api_key = st.text_input(
        "API Key",
        value=Config.LIVEDOOR_API_KEY,
        type="password",
        help="ブログ管理画面 > ブログ設定 > API Key で確認できます"
    )
    post_as_draft = st.checkbox(
        "下書きとして保存する",
        value=Config.LIVEDOOR_POST_DRAFT,
        help="チェックを入れると下書き（非公開）で投稿されます。"
    )

with st.sidebar.expander("🐦 X (Twitter) 公式 API 設定（将来用）", expanded=False):
    st.caption("※有料APIアカウントをお持ちの場合のみ入力してください。未入力の場合はYahoo!リアルタイム検索が使われます。")
    x_bearer = st.text_input("Bearer Token", value=Config.TWITTER_BEARER_TOKEN, type="password")

st.sidebar.markdown("---")
st.sidebar.caption("🚀 まとめブログ自動作成ツール v1.0")

# モバイル最適化CSS
st.markdown("""
<style>
    /* モバイル向け押しやすいボタンとカードレイアウト */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        padding: 0.5rem 1rem;
    }
    .buzz-item {
        background: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    @media (max-width: 768px) {
        .block-container {
            padding-left: 0.8rem;
            padding-right: 0.8rem;
            padding-top: 1rem;
        }
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# メイン画面
# ==========================================
st.title("⚡ バズ話題・ニュースまとめブログ自動作成")
st.caption("今バズっているXの話題や最新ニュースを選んで、Geminiでライブドア向けまとめ記事を瞬時に作成します。")

# ----------------------------------------------------
# STEP 1: 話題・ニュースを選ぶ
# ----------------------------------------------------
st.subheader("1. バズ話題・ニュース一覧から選ぶ")

tab_yahoo, tab_gnews, tab_manual = st.tabs([
    "🔥 Yahoo!リアルタイム バズ一覧",
    "📰 Googleニュース一覧",
    "🔍 自由キーワード検索"
])

# --- タブ1: Yahoo!リアルタイム急上昇トレンド ---
with tab_yahoo:
    c_ref, c_view = st.columns([1, 2])
    with c_ref:
        if st.button("🔄 トレンド再取得", key="btn_refresh_trends"):
            with st.spinner("最新トレンドを取得中..."):
                st.session_state.yahoo_trends = fetch_yahoo_trends(25)
    
    if "yahoo_trends" not in st.session_state:
        st.session_state.yahoo_trends = fetch_yahoo_trends(25)

    trends = st.session_state.yahoo_trends
    if trends:
        with c_view:
            view_mode = st.radio("表示スタイル:", ["📱 カード一覧（スマホ推奨）", "📋 プルダウン選択"], horizontal=True)

        if view_mode == "📱 カード一覧（スマホ推奨）":
            st.write("▼ 今まさにバズっている話題一覧（タップで即選択）")
            for idx, t in enumerate(trends):
                rank = t.get("rank", idx + 1)
                word = t.get("word", "")
                
                # 順位に応じたアイコン装飾
                if rank == 1:
                    badge = f"🥇 **1位**"
                elif rank == 2:
                    badge = f"🥈 **2位**"
                elif rank == 3:
                    badge = f"🥉 **3位**"
                else:
                    badge = f"**{rank}位**"

                with st.container():
                    c_text, c_act = st.columns([3, 2])
                    with c_text:
                        st.markdown(f"#### {badge} {word}")
                        if t.get("url"):
                            st.caption(f"[🔍 Yahoo!リアルタイムで見る]({t['url']})")
                    with c_act:
                        if st.button(f"👉 まとめ作成", key=f"btn_pick_trend_{idx}", type="primary"):
                            with st.spinner(f"「{word}」のポストを収集中..."):
                                st.session_state.current_topic = word
                                st.session_state.news_summary = f"Yahoo!リアルタイム急上昇トレンド: {word}"
                                posts = fetch_yahoo_topic_posts(word, max_count=15)
                                st.session_state.collected_posts = posts
                                st.session_state.generated_article = None
                                st.success(f"「{word}」のポストを {len(posts)} 件取得しました！下のステップ2へ進んでください。")
                                st.rerun()
                    st.divider()

        else:
            # 従来のプルダウン方式
            trend_words = [f"{t.get('rank', i+1)}位: {t['word']}" for i, t in enumerate(trends)]
            selected_trend_idx = st.selectbox("トレンドを選択:", range(len(trend_words)), format_func=lambda i: trend_words[i])
            chosen_word = trends[selected_trend_idx]["word"]
            if st.button("👉 このトレンドで情報を収集する", key="btn_collect_trend", type="primary"):
                with st.spinner(f"「{chosen_word}」に関するXのポストを収集しています..."):
                    st.session_state.current_topic = chosen_word
                    st.session_state.news_summary = f"Yahoo!リアルタイム急上昇トレンド: {chosen_word}"
                    posts = fetch_yahoo_topic_posts(chosen_word, max_count=15)
                    st.session_state.collected_posts = posts
                    st.session_state.generated_article = None
                    st.success(f"「{chosen_word}」に関するポストを {len(posts)} 件取得しました！")
    else:
        st.info("トレンド情報を取得できませんでした。しばらく経ってから再試行するか、自由検索をご利用ください。")

# --- タブ2: Googleニュース ---
with tab_gnews:
    c_cat, c_nref = st.columns([2, 1])
    with c_cat:
        selected_cat = st.selectbox("カテゴリ選択:", list(GOOGLE_NEWS_CATEGORIES.keys()))
    with c_nref:
        if st.button("🔄 ニュース再取得", key="btn_fetch_gnews"):
            with st.spinner("ニュース更新中..."):
                st.session_state.gnews_articles = fetch_google_news(selected_cat, max_count=15)
    
    if "gnews_articles" not in st.session_state:
        st.session_state.gnews_articles = fetch_google_news(selected_cat, max_count=15)
        
    gnews = st.session_state.gnews_articles
    if gnews:
        st.write(f"▼ 【{selected_cat}】最新ヘッドライン一覧（タップで即選択）")
        for i, n in enumerate(gnews):
            clean_title = n['title'].split(" - ")[0]
            with st.container():
                st.markdown(f"**【{n['source'] or 'ニュース'}】 {clean_title}**")
                st.caption(f"公開日時: {n['published']}")
                if st.button("👉 このニュースでまとめ作成", key=f"btn_pick_news_{i}", type="primary"):
                    with st.spinner(f"「{clean_title}」のネットの反応を検索中..."):
                        st.session_state.current_topic = clean_title
                        st.session_state.news_summary = f"ニュースタイトル: {n['title']}\n配信元: {n['source']}\nリンク: {n['link']}"
                        posts = fetch_yahoo_topic_posts(clean_title[:30], max_count=15)
                        st.session_state.collected_posts = posts
                        st.session_state.generated_article = None
                        st.success(f"「{clean_title}」と関連ポスト {len(posts)} 件を取得しました！")
                        st.rerun()
                st.divider()

# --- タブ3: 自由キーワード検索 ---
with tab_manual:
    manual_kw = st.text_input("気になるキーワードや人物名・事件名:", placeholder="例: 大谷翔平 50-50")
    if st.button("🔍 検索して情報収集", key="btn_manual_search", type="primary"):
        if manual_kw.strip():
            with st.spinner(f"「{manual_kw}」の情報を収集中..."):
                st.session_state.current_topic = manual_kw.strip()
                news_results = search_google_news(manual_kw, max_count=3)
                news_text = ""
                if news_results:
                    news_text = "\n".join([f"- {n['title']} ({n['source']})" for n in news_results])
                st.session_state.news_summary = news_text or f"検索キーワード: {manual_kw}"
                posts = fetch_yahoo_topic_posts(manual_kw, max_count=15)
                st.session_state.collected_posts = posts
                st.session_state.generated_article = None
                st.success(f"関連ポスト {len(posts)} 件を収集しました！")
        else:
            st.warning("キーワードを入力してください。")

st.markdown("---")

# ----------------------------------------------------
# STEP 2: 収集された情報とポストの確認・調整
# ----------------------------------------------------
st.subheader("2. 収集データの確認・記事構成の指定")

col_top, col_tone = st.columns([3, 2])
with col_top:
    topic_val = st.text_input("現在のメイントピック:", value=st.session_state.current_topic)
    st.session_state.current_topic = topic_val

with col_tone:
    article_tone = st.selectbox(
        "記事のトーン:",
        [
            "🔥 俺的ゲーム速報・はちま起稿風（赤太字・青太字・煽り・管理人コメント付き）",
            "王道まとめブログ風（テンポよく熱量高め・定番見出し付き）",
            "2ch・5chスレ風（『〇〇した結果ｗｗｗ』・ネット民のツッコミ重視）",
            "分かりやすい解説ニュース風（丁寧・客観的かつ読者を飽きさせない）",
            "辛口・考察風（賛否両論のポイントを鋭く分析）"
        ]
    )

with st.expander("📋 収集されたXポスト一覧の確認（不要なポストをチェックで除外）", expanded=bool(st.session_state.collected_posts)):
    if st.session_state.collected_posts:
        active_posts = []
        for idx, p in enumerate(st.session_state.collected_posts):
            c_check, c_text = st.columns([1, 15])
            with c_check:
                use_post = st.checkbox("採用", value=True, key=f"post_chk_{idx}")
            with c_text:
                st.markdown(f"**{p['author']}**: {p['text']}")
            if use_post:
                active_posts.append(p)
    else:
        active_posts = []
        st.info("上のステップ1で話題を選んで情報収集を実行してください。")

# ----------------------------------------------------
# STEP 3: Geminiでまとめ記事を自動生成
# ----------------------------------------------------
st.subheader("3. まとめ記事を生成する")

if st.button("⚡ Geminiでまとめブログ記事を自動生成する", type="primary", use_container_width=True):
    if not gemini_key:
        st.error("左側メニューの「Google Gemini API 設定」にAPIキーを入力してください。")
    elif not st.session_state.current_topic:
        st.error("先にステップ1で話題を選択・入力してください。")
    else:
        with st.spinner("Geminiがバズ情報からまとめ記事（ライブドア向けHTML）を執筆中..."):
            try:
                generator = GeminiGenerator(api_key=gemini_key, model=gemini_model)
                article_result = generator.generate_article(
                    topic=st.session_state.current_topic,
                    news_summary=st.session_state.news_summary,
                    posts=active_posts if active_posts else st.session_state.collected_posts,
                    tone=article_tone
                )
                st.session_state.generated_article = article_result
                st.success("記事が完成しました！下のプレビューで確認してください。")
            except Exception as e:
                st.error(f"生成エラー: {e}")

st.markdown("---")

# ----------------------------------------------------
# STEP 4: 記事のプレビュー・編集・ライブドア投稿
# ----------------------------------------------------
st.subheader("4. 記事の確認・編集 & ライブドアブログ投稿")

if st.session_state.generated_article:
    art = st.session_state.generated_article

    # タイトル候補の切り替え
    candidates = art.get("title_candidates", [])
    if candidates:
        st.write("💡 **他のタイトル候補:**")
        cols = st.columns(len(candidates))
        for i, cand in enumerate(candidates):
            with cols[i]:
                if st.button(f"案{i+1}: {cand[:20]}...", key=f"btn_cand_{i}", help=cand):
                    art["title"] = cand
                    st.rerun()

    edit_title = st.text_input("記事タイトル:", value=art.get("title", ""))
    tags_list = art.get("tags", [])
    edit_tags = st.text_input("タグ (カンマ区切り):", value=", ".join(tags_list))

    # 管理人のひとこと専用編集エリア
    st.markdown("##### 💬 管理人のひとこと・感想（編集可能）")
    st.caption("※ここに入力したテキストは、記事末尾の専用デザイン枠に自動反映されます。")
    current_admin_comment = art.get("admin_comment", "")
    edit_admin_comment = st.text_area(
        "管理人のひとこと本文:",
        value=current_admin_comment,
        height=100,
        help="フランクな感想やオチ、ツッコミなどを自由に編集できます。"
    )
    art["admin_comment"] = edit_admin_comment

    # 本文HTMLと管理人のひとこと枠を合成
    body_html = art.get("body_html", "")
    if not body_html:
        body_html = art.get("content_html", "")
    
    # 完全なHTML（本文＋装飾された管理人のひとこと枠）
    full_html = body_html + format_admin_comment_html(edit_admin_comment)
    art["content_html"] = full_html

    tab_preview, tab_html_code = st.tabs(["👁️ ブログ表示プレビュー", "💻 HTMLコード直接編集"])

    with tab_preview:
        st.markdown(f"### {edit_title}")
        st.components.v1.html(
            f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.7; color: #2b2b2b;">
                {full_html}
            </div>
            """,
            height=600,
            scrolling=True
        )

    with tab_html_code:
        edit_html_direct = st.text_area(
            "HTML本文（全体コード）:",
            value=full_html,
            height=400,
            help="必要に応じてHTMLを直接編集できます。"
        )
        if edit_html_direct != full_html:
            full_html = edit_html_direct
            art["content_html"] = full_html

    # アクションボタン群
    col_copy, col_save, col_post = st.columns([1, 1, 1.5])

    with col_copy:
        # クリップボードコピー用HTML
        st.caption("ライブドア等のエディタへ貼り付け:")
        st.code(full_html, language="html")

    with col_save:
        if st.button("💾 ローカルにHTML保存", use_container_width=True):
            publisher = LivedoorPublisher()
            saved_file = publisher.save_to_local(edit_title, full_html, is_draft=post_as_draft)
            st.success(f"保存完了: {saved_file.name}")

    with col_post:
        if st.button("🚀 ライブドアブログへ送信", type="primary", use_container_width=True):
            if not livedoor_id or not livedoor_api_key:
                st.warning("左側の「ライブドアブログ設定」に livedoor ID と API Key を設定してください。")
            else:
                with st.spinner("ライブドアブログへ投稿中..."):
                    publisher = LivedoorPublisher(livedoor_id=livedoor_id, api_key=livedoor_api_key)
                    tag_items = [t.strip() for t in edit_tags.split(",") if t.strip()]
                    post_res = publisher.post_article(
                        title=edit_title,
                        content_html=full_html,
                        categories=tag_items,
                        draft=post_as_draft
                    )
                    if post_res.get("success"):
                        st.balloons()
                        st.success(post_res.get("message"))
                    else:
                        st.error(post_res.get("message"))
else:
    st.info("ステップ3で「Geminiでまとめブログ記事を自動生成する」を実行すると、ここに記事が表示されます。")
