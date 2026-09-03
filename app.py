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
    initial_sidebar_state="collapsed"  # スマホで見やすいよう初期は折りたたみ
)

# セッション状態の初期化
if "current_step" not in st.session_state:
    st.session_state.current_step = 1  # 1: 話題選び, 2: 記事生成, 3: プレビュー・投稿
if "current_topic" not in st.session_state:
    st.session_state.current_topic = ""
if "news_summary" not in st.session_state:
    st.session_state.news_summary = ""
if "collected_posts" not in st.session_state:
    st.session_state.collected_posts = []
if "generated_article" not in st.session_state:
    st.session_state.generated_article = None

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
    @media (max-width: 768px) {
        .block-container {
            padding-left: 0.6rem;
            padding-right: 0.6rem;
            padding-top: 0.8rem;
        }
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# サイドバー: 設定
# ==========================================
st.sidebar.title("⚙️ 設定 & 連携")

with st.sidebar.expander("🔑 Google Gemini API 設定", expanded=True):
    # クエリパラメータまたはデフォルト値から復元（リロード対策）
    default_gemini_key = st.query_params.get("gk", Config.GEMINI_API_KEY)
    gemini_key = st.text_input(
        "Gemini API Key",
        value=default_gemini_key,
        type="password",
        help="Google AI Studioで取得したAPIキーを入力してください。"
    )
    if gemini_key:
        st.query_params["gk"] = gemini_key

    model_choices = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.5-pro",
        "gemini-3.8-flash",
        "gemini-3.8-pro",
        "✏️ 直接モデル名を入力"
    ]
    saved_model = st.query_params.get("gm", Config.GEMINI_MODEL)
    default_idx = 0
    if saved_model in model_choices:
        default_idx = model_choices.index(saved_model)
    
    selected_model_choice = st.selectbox(
        "モデル選択",
        model_choices,
        index=default_idx,
        help="最も安定・高速な gemini-2.5-flash を推奨します。混雑（503エラー）が発生した場合は自動的に安定モデルへフォールバックします。"
    )

    if selected_model_choice == "✏️ 直接モデル名を入力":
        gemini_model = st.text_input("モデル名を入力:", value=saved_model)
    else:
        gemini_model = selected_model_choice
    
    if gemini_model:
        st.query_params["gm"] = gemini_model

with st.sidebar.expander("📝 ライブドアブログ設定", expanded=True):
    default_livedoor_id = st.query_params.get("lid", Config.LIVEDOOR_ID)
    livedoor_id = st.text_input(
        "livedoor ID",
        value=default_livedoor_id,
        help="ライブドアブログのID（ログインIDまたはブログID）"
    )
    if livedoor_id:
        st.query_params["lid"] = livedoor_id

    default_livedoor_key = st.query_params.get("lkey", Config.LIVEDOOR_API_KEY)
    livedoor_api_key = st.text_input(
        "API Key",
        value=default_livedoor_key,
        type="password",
        help="ブログ管理画面 > ブログ設定 > API Key で確認できます"
    )
    if livedoor_api_key:
        st.query_params["lkey"] = livedoor_api_key

    post_as_draft = st.checkbox(
        "下書きとして保存する",
        value=Config.LIVEDOOR_POST_DRAFT,
        help="チェックを入れると下書き（非公開）で投稿されます。"
    )

with st.sidebar.expander("🐦 X (Twitter) 公式 API 設定（将来用）", expanded=False):
    st.caption("※有料APIアカウントをお持ちの場合のみ入力してください。未入力の場合はYahoo!リアルタイム検索が使われます。")
    x_bearer = st.text_input("Bearer Token", value=Config.TWITTER_BEARER_TOKEN, type="password")

st.sidebar.markdown("---")
st.sidebar.caption("🚀 まとめブログ自動作成ツール v1.1")

# ==========================================
# メイン画面: タイトルとステップナビゲーション
# ==========================================
st.title("⚡ バズ話題・まとめブログ自動作成")

# ステップナビゲーションバー（スマホで迷わずスクロール不要）
nav1, nav2, nav3 = st.columns(3)
with nav1:
    type_s1 = "primary" if st.session_state.current_step == 1 else "secondary"
    if st.button("① 話題を選ぶ", key="btn_nav_1", type=type_s1):
        st.session_state.current_step = 1
        st.rerun()

with nav2:
    type_s2 = "primary" if st.session_state.current_step == 2 else "secondary"
    can_s2 = bool(st.session_state.current_topic)
    if st.button("② 記事生成", key="btn_nav_2", type=type_s2, disabled=not can_s2):
        st.session_state.current_step = 2
        st.rerun()

with nav3:
    type_s3 = "primary" if st.session_state.current_step == 3 else "secondary"
    can_s3 = bool(st.session_state.generated_article)
    if st.button("③ プレビュー・投稿", key="btn_nav_3", type=type_s3, disabled=not can_s3):
        st.session_state.current_step = 3
        st.rerun()

st.markdown("---")

# ==========================================
# 画面1: 話題・ニュースを選ぶ
# ==========================================
if st.session_state.current_step == 1:
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
                st.write("▼ 今バズっている話題（タップすると自動で生成画面へ進みます）")
                for idx, t in enumerate(trends):
                    rank = t.get("rank", idx + 1)
                    word = t.get("word", "")
                    badge = f"🥇 1位" if rank == 1 else (f"🥈 2位" if rank == 2 else (f"🥉 3位" if rank == 3 else f"{rank}位"))

                    with st.container():
                        c_text, c_act = st.columns([3, 2])
                        with c_text:
                            st.markdown(f"#### {badge} {word}")
                            if t.get("url"):
                                st.caption(f"[🔍 Yahoo!で見る]({t['url']})")
                        with c_act:
                            if st.button(f"👉 まとめ作成", key=f"btn_pick_trend_{idx}", type="primary"):
                                with st.spinner(f"「{word}」のポストを収集中..."):
                                    st.session_state.current_topic = word
                                    st.session_state.news_summary = f"Yahoo!リアルタイム急上昇トレンド: {word}"
                                    posts = fetch_yahoo_topic_posts(word, max_count=15)
                                    st.session_state.collected_posts = posts
                                    st.session_state.generated_article = None
                                    # スクロール不要！即座にステップ2（生成画面）へ自動遷移
                                    st.session_state.current_step = 2
                                    st.rerun()
                        st.divider()

            else:
                trend_words = [f"{t.get('rank', i+1)}位: {t['word']}" for i, t in enumerate(trends)]
                selected_trend_idx = st.selectbox("トレンドを選択:", range(len(trend_words)), format_func=lambda i: trend_words[i])
                chosen_word = trends[selected_trend_idx]["word"]
                if st.button("👉 このトレンドでまとめ作成へ", key="btn_collect_trend", type="primary"):
                    with st.spinner(f"「{chosen_word}」に関するXのポストを収集しています..."):
                        st.session_state.current_topic = chosen_word
                        st.session_state.news_summary = f"Yahoo!リアルタイム急上昇トレンド: {chosen_word}"
                        posts = fetch_yahoo_topic_posts(chosen_word, max_count=15)
                        st.session_state.collected_posts = posts
                        st.session_state.generated_article = None
                        st.session_state.current_step = 2
                        st.rerun()
        else:
            st.info("トレンド情報を取得できませんでした。しばらく経ってから再試行するか、自由検索をご利用ください。")

    # --- タブ2: Googleニュース ---
    with tab_gnews:
        c_cat, c_nref = st.columns([2, 1])
        with c_cat:
            selected_cat = st.selectbox("カテゴリ選択:", list(GOOGLE_NEWS_CATEGORIES.keys()))
        with c_nref:
            if st.button("🔄 ニュース更新", key="btn_fetch_gnews"):
                with st.spinner("ニュース更新中..."):
                    st.session_state.gnews_articles = fetch_google_news(selected_cat, max_count=15)
        
        if "gnews_articles" not in st.session_state:
            st.session_state.gnews_articles = fetch_google_news(selected_cat, max_count=15)
            
        gnews = st.session_state.gnews_articles
        if gnews:
            st.write(f"▼ 【{selected_cat}】最新ヘッドライン一覧")
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
                            st.session_state.current_step = 2
                            st.rerun()
                    st.divider()

    # --- タブ3: 自由キーワード検索 ---
    with tab_manual:
        manual_kw = st.text_input("気になるキーワードや人物名・事件名:", placeholder="例: 大谷翔平 50-50")
        if st.button("🔍 検索してまとめ作成へ", key="btn_manual_search", type="primary"):
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
                    st.session_state.current_step = 2
                    st.rerun()
            else:
                st.warning("キーワードを入力してください。")

# ==========================================
# 画面2: 収集データ確認 & 記事生成
# ==========================================
elif st.session_state.current_step == 2:
    st.subheader("2. 記事構成の指定 & 自動生成")

    c_back, _ = st.columns([1, 2])
    with c_back:
        if st.button("← ① 話題一覧に戻る", key="btn_back_to_1"):
            st.session_state.current_step = 1
            st.rerun()

    st.info(f"📌 **選択中のトピック**: {st.session_state.current_topic}")

    topic_val = st.text_input("トピック名（微調整可能）:", value=st.session_state.current_topic)
    st.session_state.current_topic = topic_val

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

    with st.expander(f"📋 収集されたXポスト一覧 ({len(st.session_state.collected_posts)}件・いいね数順)", expanded=True):
        active_posts = []
        if st.session_state.collected_posts:
            # 一括操作ボタン
            c_btn_none, c_btn_all = st.columns(2)
            with c_btn_none:
                if st.button("❌ 採用チェックをすべて外す", key="btn_uncheck_all", use_container_width=True):
                    for i in range(len(st.session_state.collected_posts)):
                        st.session_state[f"post_chk_{i}"] = False
                    st.rerun()
            with c_btn_all:
                if st.button("✅ すべて選択する", key="btn_check_all", use_container_width=True):
                    for i in range(len(st.session_state.collected_posts)):
                        st.session_state[f"post_chk_{i}"] = True
                    st.rerun()

            st.caption("※不要なポストのチェックを外すか、「すべて外す」を押してから使いたいポストだけチェックを入れてください。")
            for idx, p in enumerate(st.session_state.collected_posts):
                c_chk, c_txt = st.columns([1, 10])
                chk_key = f"post_chk_{idx}"
                # セッションステートに初期値がなければTrue
                if chk_key not in st.session_state:
                    st.session_state[chk_key] = True

                with c_chk:
                    use_post = st.checkbox("採用", key=chk_key)
                with c_txt:
                    likes = p.get("likes", 0)
                    rts = p.get("rts", 0)
                    metrics_badge = f"　<span style='background:#ffe3e3;color:#c92a2a;padding:2px 8px;border-radius:12px;font-size:0.85em;font-weight:bold;'>❤️ {likes:,} いいね</span> <span style='background:#e7f5ff;color:#1864ab;padding:2px 8px;border-radius:12px;font-size:0.85em;font-weight:bold;'>🔁 {rts:,} RT</span>" if (likes or rts) else ""
                    st.markdown(f"**{p['author']}**{metrics_badge}", unsafe_allow_html=True)
                    st.markdown(f"<div style='background:#f8f9fa;padding:8px 12px;border-radius:6px;margin:4px 0 10px;font-size:0.95em;'>{p['text']}</div>", unsafe_allow_html=True)
                if use_post:
                    active_posts.append(p)
        else:
            active_posts = []
            st.caption("関連ポストなし（トピック名からGeminiが構成します）")

    st.markdown("---")
    
    # メインの生成ボタン
    if st.button("⚡ Geminiでまとめブログ記事を生成する", type="primary", use_container_width=True):
        if not gemini_key:
            st.error("左側メニュー（またはSecrets）にGemini APIキーを設定してください。")
        else:
            with st.spinner("Geminiがまとめ記事を執筆中...（完了すると自動でプレビュー画面へ移動します）"):
                try:
                    generator = GeminiGenerator(api_key=gemini_key, model=gemini_model)
                    article_result = generator.generate_article(
                        topic=st.session_state.current_topic,
                        news_summary=st.session_state.news_summary,
                        posts=active_posts if active_posts else st.session_state.collected_posts,
                        tone=article_tone
                    )
                    st.session_state.generated_article = article_result
                    # スクロール不要！即座にステップ3（プレビュー画面）へ自動遷移
                    st.session_state.current_step = 3
                    st.rerun()
                except Exception as e:
                    st.error(f"生成エラー: {e}")

# ==========================================
# 画面3: 記事プレビュー・編集・ライブドア投稿
# ==========================================
elif st.session_state.current_step == 3:
    st.subheader("3. 記事の確認・編集 & ライブドア投稿")

    c_s3_back, _ = st.columns([1, 2])
    with c_s3_back:
        if st.button("← ② 生成設定に戻る", key="btn_back_to_2"):
            st.session_state.current_step = 2
            st.rerun()

    if st.session_state.generated_article:
        art = st.session_state.generated_article

        # タイトル候補の切り替え
        candidates = art.get("title_candidates", [])
        if candidates:
            st.write("💡 **他のタイトル案にワンタップ変更:**")
            for i, cand in enumerate(candidates):
                if st.button(f"案{i+1}: {cand}", key=f"btn_cand_{i}"):
                    art["title"] = cand
                    st.rerun()

        edit_title = st.text_input("記事タイトル:", value=art.get("title", ""))
        tags_list = art.get("tags", [])
        edit_tags = st.text_input("タグ (カンマ区切り):", value=", ".join(tags_list))

        # 管理人のひとこと専用編集エリア
        st.markdown("##### 💬 管理人のひとこと・感想（2行程度で編集可能）")
        st.caption("※2行程度のサクッとしたオチ・感想がまとめブログに最適です。記事末尾の専用デザイン枠に自動反映されます。")
        current_admin_comment = art.get("admin_comment", "")
        edit_admin_comment = st.text_area(
            "管理人のひとこと本文:",
            value=current_admin_comment,
            height=70,
            help="フランクな感想やオチ、ツッコミなどを自由に編集できます。"
        )
        art["admin_comment"] = edit_admin_comment

        # 本文HTMLと管理人のひとこと枠を合成
        body_html = art.get("body_html", "")
        if not body_html:
            body_html = art.get("content_html", "")
        
        full_html = body_html + format_admin_comment_html(edit_admin_comment)
        art["content_html"] = full_html

        # アクションボタン群（最上部近くにも配置してスマホですぐ押せるように）
        st.write("🚀 **アクション**")
        col_post_top, col_save_top = st.columns([2, 1])
        with col_post_top:
            if st.button("🚀 ライブドアブログへ送信", type="primary", key="btn_post_top", use_container_width=True):
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
        with col_save_top:
            if st.button("💾 ローカル保存", key="btn_save_top", use_container_width=True):
                publisher = LivedoorPublisher()
                saved_file = publisher.save_to_local(edit_title, full_html, is_draft=post_as_draft)
                st.success(f"保存完了: {saved_file.name}")

        # プレビュー表示
        tab_preview, tab_html_code = st.tabs(["👁️ ブログ表示プレビュー", "💻 HTMLコード直接編集 / コピー"])

        with tab_preview:
            st.markdown(f"### {edit_title}")
            st.components.v1.html(
                f"""
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.7; color: #2b2b2b;">
                    {full_html}
                </div>
                <script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script>
                """,
                height=650,
                scrolling=True
            )

        with tab_html_code:
            st.caption("クリップボード用コード（手動コピー用）:")
            st.code(full_html, language="html")
            edit_html_direct = st.text_area(
                "HTML直接編集:",
                value=full_html,
                height=300,
                help="必要に応じてHTMLを直接編集できます。"
            )
            if edit_html_direct != full_html:
                art["content_html"] = edit_html_direct

        st.markdown("---")
        if st.button("🔄 別の話題で新しいまとめを作成する", use_container_width=True):
            st.session_state.current_step = 1
            st.session_state.current_topic = ""
            st.session_state.collected_posts = []
            st.session_state.generated_article = None
            st.rerun()
    else:
        st.info("記事がまだ生成されていません。上の「① 話題を選ぶ」から話題を選択してください。")
