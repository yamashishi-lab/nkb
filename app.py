import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import altair as alt
import unicodedata
import hashlib
import hmac
import time

# スマホ画面向けにページ設定
st.set_page_config(page_title="翌朝株価 クオンツ＆7大AI解析 Pro (会員限定版)", page_icon="📈", layout="centered")

# ==========================================
# 🔒 会員制ログイン＆メール許可ゲート機能
# ==========================================
ADMIN_EMAIL = "nthbh399@ybb.ne.jp"  # ←あなたのメールアドレスに変更してください
SECRET_MASTER_KEY = "my_super_secret_quant_key_2026"  # ←好きな英数字に変更してください

ALLOWED_MEMBERS = [
    ADMIN_EMAIL,                # 管理者（あなた自身）
    "yamashita007722@gmail.com",# 許可した会員1
    "",                         # 許可した会員2
]

def generate_member_passcode(email: str) -> str:
    clean_email = email.strip().lower()
    h = hmac.new(SECRET_MASTER_KEY.encode(), clean_email.encode(), hashlib.sha256).hexdigest()
    return h[:8].upper()

def check_member_authentication():
    if "authenticated_user" not in st.session_state:
        st.session_state["authenticated_user"] = None

    if st.session_state["authenticated_user"]:
        with st.sidebar:
            st.success(f"👤 会員ログイン中:\n{st.session_state['authenticated_user']}")
            if st.session_state["authenticated_user"] == ADMIN_EMAIL.strip().lower():
                with st.expander("🔑 【管理者専用】会員パスコード発行機"):
                    st.caption("申請が来た会員のメアドを入力すると、専用8桁コードが表示されます。")
                    target_mail = st.text_input("許可する会員のメールアドレス", key="admin_gen_mail")
                    if target_mail:
                        code = generate_member_passcode(target_mail)
                        st.code(f"メールアドレス: {target_mail.strip().lower()}\n専用アクセスコード: {code}")
                        st.caption("↑このコードをメールで返信し、ALLOWED_MEMBERS にメアドを追加してください。")
            if st.button("🚪 ログアウト", use_container_width=True):
                st.session_state["authenticated_user"] = None
                st.rerun()
        return True

    st.markdown("""
    <div style="background: linear-gradient(135deg, #0f172a, #1e293b); color: #f8fafc; padding: 24px; border-radius: 14px; text-align: center; margin-top: 20px; margin-bottom: 16px; box-shadow: 0 4px 16px rgba(0,0,0,0.2);">
        <h2 style="margin:0; color:#fbbf24; font-size:20px;">🔒 会員限定 クオンツ＆7大AI解析 Pro</h2>
        <p style="font-size:13px; color:#cbd5e1; margin-top:8px; margin-bottom:0;">
            本システムは完全招待・承認制です。<br>運営より許可されたメールアドレスと専用アクセスコードを入力してください。
        </p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("member_login_form"):
        input_email = st.text_input("📧 登録メールアドレス", placeholder="example@gmail.com")
        input_code = st.text_input("🔑 専用アクセスコード（メールで届いた8桁コード）", type="password")
        login_btn = st.form_submit_button("🔓 ログインして解析システムを開く", use_container_width=True)

        if login_btn:
            clean_mail = input_email.strip().lower()
            allowed_list = [m.strip().lower() for m in ALLOWED_MEMBERS]
            expected_code = generate_member_passcode(clean_mail)

            is_valid_code = hmac.compare_digest(input_code.strip().upper(), expected_code) or (
                clean_mail == ADMIN_EMAIL.strip().lower() and input_code.strip() == "ADMIN777"
            )

            if clean_mail in allowed_list and is_valid_code:
                st.session_state["authenticated_user"] = clean_mail
                st.rerun()
            elif clean_mail not in allowed_list:
                st.error("⚠️ このメールアドレスはまだ利用許可されていません。下のボタンから管理者に利用申請を行ってください。")
            else:
                st.error("⚠️ 専用アクセスコードが正しくありません。")

    st.markdown("---")
    st.markdown("##### 📩 まだ利用許可をお持ちでない方へ")
    mailto_link = (
        f"mailto:{ADMIN_EMAIL}"
        f"?subject=【利用許可申請】翌朝株価クオンツ＆7大AI解析Pro"
        f"&body=以下のメールアドレスでの利用許可を申請します。%0D%0A%0D%0A"
        f"・お名前：%0D%0A"
        f"・希望メールアドレス：%0D%0A"
    )
    st.markdown(
        f'<a href="{mailto_link}" style="display:block; text-align:center; background:#2563eb; color:#ffffff; padding:12px; border-radius:8px; text-decoration:none; font-weight:bold; font-size:13px;">✉️ 管理者にメールで利用許可を申請する</a>',
        unsafe_allow_html=True
    )
    st.stop()

check_member_authentication()

# ==========================================
# 📈 メイン処理（認証通過後・セッション管理）
# ==========================================
if "active_debates" not in st.session_state:
    st.session_state["active_debates"] = {}
if "debate_Animated" not in st.session_state:
    st.session_state["debate_Animated"] = set()
if "stock_chats" not in st.session_state:
    st.session_state["stock_chats"] = {}
if "watchlist" not in st.session_state:
    st.session_state["watchlist"] = {}
if "order_checks" not in st.session_state:
    st.session_state["order_checks"] = {}
if "selected_category" not in st.session_state:
    st.session_state["selected_category"] = "🏆 総合TOP5"

# カスタムCSS
st.markdown("""
<style>
.market-banner { background: linear-gradient(135deg, #0f172a, #1e293b); color: #f8fafc; border-radius: 12px; padding: 12px 10px; margin-bottom: 16px; box-shadow: 0 2px 10px rgba(0,0,0,0.18); width: 100%; }
.market-title { font-size: 11px; font-weight: bold; color: #94a3b8; margin-bottom: 8px; text-align: center; }
.market-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 6px; width: 100%; }
.market-item { background: rgba(255, 255, 255, 0.08); border-radius: 8px; padding: 7px 4px; text-align: center; border: 1px solid rgba(255, 255, 255, 0.07); }
.span-2 { grid-column: span 2; }
.span-3 { grid-column: span 3; }
@media (max-width: 340px) { .span-2, .span-3 { grid-column: span 6; } }
.stock-card { background-color: #ffffff; border-radius: 12px; padding: 16px; margin-bottom: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); border-left: 6px solid #dc2626; }
.rank-card { background-color: #ffffff; border-radius: 12px; padding: 16px; margin-bottom: 6px; box-shadow: 0 4px 12px rgba(220, 38, 38, 0.12); border-left: 6px solid #e11d48; }
.search-result-card { background-color: #fffbeb; border-radius: 12px; padding: 16px; margin-bottom: 6px; box-shadow: 0 4px 12px rgba(217, 119, 6, 0.15); border-left: 6px solid #d97706; }
.watchlist-summary-banner { background: linear-gradient(135deg, #064e3b, #047857); color: #f8fafc; border-radius: 12px; padding: 14px; margin-bottom: 14px; border: 1px solid #10b981; }
.order-sheet-card { background: #ffffff; border-radius: 12px; padding: 14px; margin-bottom: 10px; border: 1px solid #cbd5e1; border-left: 6px solid #059669; }
.prob-badge { font-size: 22px; font-weight: bold; color: #dc2626; }
.rank-badge { display: inline-block; background: linear-gradient(135deg, #f59e0b, #d97706); color: #ffffff; padding: 3px 9px; border-radius: 20px; font-size: 12px; font-weight: bold; margin-right: 4px; margin-bottom: 6px; }
.score-badge { display: inline-block; background: linear-gradient(135deg, #1e293b, #334155); color: #f8fafc; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: bold; margin-bottom: 6px; }
.macro-badge { display: inline-block; background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; padding: 2px 8px; border-radius: 20px; font-size: 11px; font-weight: bold; margin-left: 4px; }
.edge-badge { display: inline-block; background: #f0fdf4; color: #15803d; border: 1px solid #bbf7d0; padding: 2px 8px; border-radius: 20px; font-size: 11px; font-weight: bold; margin-left: 4px; }
.moc-badge { display: inline-block; background: linear-gradient(135deg, #7e22ce, #a855f7); color: #ffffff; padding: 2px 9px; border-radius: 20px; font-size: 11px; font-weight: bold; margin-left: 4px; }
.squeeze-badge { display: inline-block; background: linear-gradient(135deg, #b91c1c, #ef4444); color: #ffffff; padding: 2px 9px; border-radius: 20px; font-size: 11px; font-weight: bold; margin-left: 4px; }
.tokugai-badge { display: inline-block; background: linear-gradient(135deg, #d97706, #f59e0b); color: #ffffff; padding: 2px 9px; border-radius: 20px; font-size: 11px; font-weight: bold; margin-left: 4px; }
.genre-badge { display: inline-block; background: #f3e8ff; color: #6b21a8; border: 1px solid #e9d5ff; padding: 2px 8px; border-radius: 6px; font-size: 10px; font-weight: bold; margin-left: 6px; }
.signal-tag { display: inline-block; background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: bold; margin-top: 8px; }
.squeeze-box { background: linear-gradient(135deg, #fff1f2, #ffe4e6); border: 1px solid #fecdd3; border-left: 4px solid #e11d48; border-radius: 8px; padding: 8px 12px; margin-top: 6px; font-size: 12px; color: #881337; }
.pts-tokugai-box { background: linear-gradient(135deg, #fffbeb, #fef3c7); border: 1px solid #fde68a; border-left: 4px solid #d97706; border-radius: 8px; padding: 8px 12px; margin-top: 6px; font-size: 12px; color: #78350f; }
.premarket-board-box { background: linear-gradient(135deg, #451a03, #78350f); border: 1px solid #f59e0b; border-left: 4px solid #fbbf24; border-radius: 8px; padding: 10px 12px; margin-bottom: 8px; font-size: 12px; color: #fef3c7; }
.intraday-5m-box { background: linear-gradient(135deg, #0f172a, #1e1b4b); border: 1px solid #38bdf8; border-left: 4px solid #06b6d4; border-radius: 8px; padding: 10px 12px; margin-bottom: 8px; font-size: 12px; color: #f8fafc; }
.closing-moc-box { background: linear-gradient(135deg, #2e1065, #4c1d95); border: 1px solid #c084fc; border-left: 4px solid #a855f7; border-radius: 8px; padding: 10px 12px; margin-bottom: 8px; font-size: 12px; color: #f8fafc; }
.chart-legend-box { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 6px 10px; margin-bottom: 6px; font-size: 11px; color: #334155; text-align: center; }
.metrics-row { display: flex; flex-wrap: wrap; gap: 6px 10px; margin-top: 8px; font-size: 11px; color: #475569; background: #f8fafc; padding: 8px 10px; border-radius: 6px; border: 1px solid #e2e8f0; }
.trade-plan-box { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-top: 8px; background: #f8fafc; padding: 8px 6px; border-radius: 8px; border: 1px dashed #cbd5e1; text-align: center; }
.factor-box { background: #f1f5f9; border-radius: 8px; padding: 10px 12px; margin-top: 10px; font-size: 12px; color: #1e293b; line-height: 1.5; }
.sizing-box { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 10px 12px; margin-top: 8px; font-size: 12px; color: #166534; }
.ai-council-box { background: linear-gradient(135deg, #0f172a, #1e293b); color: #f8fafc; border-radius: 12px; padding: 16px; margin-top: 4px; margin-bottom: 10px; box-shadow: 0 4px 14px rgba(15, 23, 42, 0.25); border: 1px solid #334155; }
.ai-agent-card { background: rgba(255, 255, 255, 0.07); border-radius: 8px; padding: 12px 14px; margin-bottom: 10px; font-size: 12.5px; line-height: 1.65; }
.claude-card     { border-left: 4px solid #f59e0b; }
.grok-card       { border-left: 4px solid #ef4444; }
.gpt-card        { border-left: 4px solid #10b981; }
.gemini-card     { border-left: 4px solid #3b82f6; }
.perplexity-card { border-left: 4px solid #06b6d4; }
.genspark-card   { border-left: 4px solid #a855f7; }
.notebooklm-card { border-left: 4px solid #ec4899; }
.consensus-banner { background: linear-gradient(135deg, #1e1b4b, #312e81); border: 2px solid #818cf8; border-radius: 10px; padding: 16px; margin-top: 14px; font-size: 13px; line-height: 1.75; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
.consensus-section { background: rgba(255, 255, 255, 0.06); border-left: 3px solid #fbbf24; border-radius: 6px; padding: 10px 12px; margin-top: 8px; font-size: 12.5px; color: #f8fafc; }
.easy-guide-box { background: rgba(16, 185, 129, 0.14); border: 1px solid #34d399; border-radius: 8px; padding: 14px; margin-top: 12px; color: #ecfdf5; font-size: 12.5px; line-height: 1.75; }
.qa-bubble-user { background: #eff6ff; color: #1e3a8a; border: 1px solid #bfdbfe; border-radius: 10px 10px 2px 10px; padding: 8px 12px; margin-top: 8px; font-size: 12px; font-weight: bold; }
.qa-bubble-ai { background: #f8fafc; color: #0f172a; border: 1px solid #cbd5e1; border-left: 4px solid #4f46e5; border-radius: 2px 10px 10px 10px; padding: 10px 12px; margin-top: 4px; margin-bottom: 10px; font-size: 12.5px; line-height: 1.65; }
</style>
""", unsafe_allow_html=True)

# --- サイドバー設定 ---
st.sidebar.header("💰 資金管理＆リスク設定")
total_capital = st.sidebar.number_input("総投資資金 (円 / ドル)", min_value=10000, max_value=1000000000, value=1000000, step=50000)
risk_tolerance_pct = st.sidebar.slider("1トレードあたりの許容リスク (%)", min_value=0.5, max_value=5.0, value=2.0, step=0.5)

st.sidebar.markdown("---")
st.sidebar.header("🔥 優先アルゴリズム設定")
moc_boost_mode = st.sidebar.checkbox("🌆 大引けMOC（引けピン）銘柄を優先", value=True)
squeeze_boost_mode = st.sidebar.checkbox("🔥 空売り踏み上げ（ショートスクイーズ）優先", value=True)
tokugai_boost_mode = st.sidebar.checkbox("🚨 翌朝『特買い』・夜間PTS連動を優先", value=True)
show_5m_chart = st.sidebar.checkbox("合議パネル内に5分足＆VWAPチャートを描画", value=True)

st.sidebar.markdown("---")
st.sidebar.header(f"📋 監視ウォッチリスト ({len(st.session_state['watchlist'])}銘柄)")
if st.session_state["watchlist"]:
    total_wl_pos = sum(item["lot_info"]["position_value"] for item in st.session_state["watchlist"].values())
    total_wl_risk = sum(item["lot_info"]["risk_amount"] for item in st.session_state["watchlist"].values())
    st.sidebar.caption(f"・合計投資予定額: **{total_wl_pos:,.0f}円** (資金比 {total_wl_pos/total_capital*100:.1f}%)")
    st.sidebar.caption(f"・合計最大リスク: **{total_wl_risk:,.0f}円**")
    for w_code, w_item in list(st.session_state["watchlist"].items()):
        st.sidebar.markdown(f"⭐ **{w_item['name']}** ({w_code}) — {w_item['lot_info']['shares']:,}株")
    if st.sidebar.button("🗑️ ウォッチリストを全クリア", use_container_width=True):
        st.session_state["watchlist"] = {}
        st.session_state["order_checks"] = {}
        st.rerun()
else:
    st.sidebar.caption("各銘柄カードの「⭐ 監視リスト追加」ボタンを押すと、ここに登録されます。")

st.title("📱 翌朝株価 クオンツ＆7大AI解析 Pro")
st.caption("【会員限定】7大AIリアルタイム10秒議論 × 監視＆注文シート × 特買い気配 × 空売り踏み上げ")

# --- 各ジャンルの候補プール ---
STOCK_POOL = {
    "半導体": [
        {"code": "8035.T", "name": "東京エレクトロン", "theme": "前工程装置の国内筆頭。海外勢の指数買いが入りやすい"},
        {"code": "6857.T", "name": "アドバンテスト", "theme": "AI半導体向けテスタで高シェア。米SOX指数と連動性大"},
        {"code": "6920.T", "name": "レーザーテック", "theme": "EUVマスク欠陥検査装置。空売り残が多く踏み上げが起きやすい筆頭"},
        {"code": "6146.T", "name": "ディスコ", "theme": "HBM向け切断・研削装置で高収益"},
        {"code": "6723.T", "name": "ルネサス", "theme": "車載・産業・データセンター向けパワー半導体を展開"},
        {"code": "7735.T", "name": "スクリーンHD", "theme": "半導体洗浄装置で世界トップクラス"},
        {"code": "4063.T", "name": "信越化学工業", "theme": "半導体シリコンウエハー世界首位"},
        {"code": "6526.T", "name": "ソシオネクスト", "theme": "先端SoC開発。個人の信用取組・空売り回転が活発"},
        {"code": "3436.T", "name": "SUMCO", "theme": "シリコンウエハー大手。需給動向に敏感に反応"},
        {"code": "6976.T", "name": "太陽誘電", "theme": "積層セラミックコンデンサ（MLCC）"},
        {"code": "6758.T", "name": "ソニーグループ", "theme": "イメージセンサー世界首位"},
        {"code": "6981.T", "name": "村田製作所", "theme": "通信・スマホ向け電子部品の世界的リーダー"},
        {"code": "6315.T", "name": "TOWA", "theme": "半導体樹脂封止装置で世界トップシェア。HBM関連"},
        {"code": "NVDA", "name": "エヌビディア (米国)", "theme": "生成AI向けGPUの圧倒的覇者"},
        {"code": "AMD", "name": "AMD (米国)", "theme": "AIアクセラレータおよびCPUでエヌビディアを追撃"},
        {"code": "MU", "name": "マイクロン (米国)", "theme": "HBM・DRAM大手。メモリー市況のバロメーター"},
        {"code": "TSM", "name": "台湾セミコンダクター (米国)", "theme": "世界最大の半導体ファウンドリ"},
        {"code": "AVGO", "name": "ブロードコム (米国)", "theme": "AIネットワーク・カスタムシリコンの巨塔"}
    ],
    "AI": [
        {"code": "9984.T", "name": "ソフトバンクG", "theme": "傘下ArmやAI投資群の評価益期待。先物主導で踏み上げが起きやすい"},
        {"code": "3778.T", "name": "さくらネット", "theme": "政府クラウド・生成AI向けGPUクラウドの国策銘柄"},
        {"code": "3993.T", "name": "PKSHA", "theme": "自然言語処理・AIアルゴリズム開発"},
        {"code": "4180.T", "name": "Appier", "theme": "AIマーケティングSaaS。グロース市場の資金流入先"},
        {"code": "4307.T", "name": "野村総合研究所", "theme": "企業のAI導入・DXシステム刷新"},
        {"code": "4478.T", "name": "フリー", "theme": "クラウド会計ソフト。SaaSセクターのモメンタム連動"},
        {"code": "4483.T", "name": "JMDC", "theme": "医療ビッグデータ・ヘルスケアAIプラットフォーム"},
        {"code": "5032.T", "name": "ANYCOLOR", "theme": "VTuberエンタメテック。空売り買戻しで急反発しやすい"},
        {"code": "4443.T", "name": "Sansan", "theme": "名刺管理・営業DXプラットフォーム"},
        {"code": "4385.T", "name": "メルカリ", "theme": "国内最大のC2Cマーケットプレイス"},
        {"code": "4689.T", "name": "LINEヤフー", "theme": "国内最大級のポータル・AI検索基盤"},
        {"code": "MSFT", "name": "マイクロソフト (米国)", "theme": "OpenAI最大株主。AzureとCopilotの収益化"},
        {"code": "GOOGL", "name": "アルファベット (米国)", "theme": "独自生成AI「Gemini」および検索・クラウド"},
        {"code": "META", "name": "メタ (米国)", "theme": "オープンソースAI「Llama」および広告最適化AI"},
        {"code": "PLTR", "name": "パランティア (米国)", "theme": "政府・防衛・企業向けAIプラットフォームの大本命"}
    ],
    "宇宙": [
        {"code": "5595.T", "name": "QPS研究所", "theme": "小型SAR衛星コンステレーション。空売り勢の踏み上げ頻発"},
        {"code": "9348.T", "name": "ispace", "theme": "月面開発・輸送プログラム。イベントドリブンで出来高急増"},
        {"code": "186A.T", "name": "アストロスケール", "theme": "スペースデブリ（宇宙ごみ）除去の世界的リーダー"},
        {"code": "9412.T", "name": "スカパーJSAT", "theme": "アジア最大の衛星通信。防衛省向け宇宙監視"},
        {"code": "7011.T", "name": "三菱重工業", "theme": "H3ロケット打ち上げ及び防衛予算拡大の国策中核銘柄"},
        {"code": "7012.T", "name": "川崎重工業", "theme": "防衛装備品・航空機エンジン・無人機システム"},
        {"code": "7013.T", "name": "IHI", "theme": "航空機用ジェットエンジン・宇宙ロケット"},
        {"code": "RKLB", "name": "ロケット・ラボ (米国)", "theme": "小型ロケット「エレクトロン」打上げの米宇宙ベンチャー筆頭"},
        {"code": "ASTS", "name": "ASTスペースモバイル (米国)", "theme": "宇宙からの直接スマホ通信網構築企業。ショートスクイーズ常連銘柄"},
        {"code": "LMT", "name": "ロッキード・マーティン (米国)", "theme": "世界最大の防衛・宇宙航空コントラクター"}
    ],
    "AI電力・インフラ": [
        {"code": "9509.T", "name": "北海道電力", "theme": "ラピダスおよび大規模AIデータセンター誘致による電力需要急増期待"},
        {"code": "9508.T", "name": "九州電力", "theme": "TSMC熊本工場や半導体工場群の増設に伴う大口電力拡大"},
        {"code": "5803.T", "name": "フジクラ", "theme": "生成AIデータセンター向け超多芯光ファイバー需要逼迫。踏み上げ代表格"},
        {"code": "6501.T", "name": "日立製作所", "theme": "世界の送配電網（グリッド）設備更新と変電システム"},
        {"code": "6622.T", "name": "ダイヘン", "theme": "AIデータセンター接続に不可欠な変圧器・受変電設備"},
        {"code": "5801.T", "name": "古河電気工業", "theme": "超高圧送電線・AIデータセンター向け高速通信ケーブル"},
        {"code": "5802.T", "name": "住友電気工業", "theme": "電線業界の最大手。電力網インフラと次世代半導体基板"},
        {"code": "1942.T", "name": "関電工", "theme": "電気設備工事の主力。データセンター・大型ビルの配線工事"},
        {"code": "VST", "name": "ビストラ (米国)", "theme": "AIデータセンター向け原子力・電力供給の筆頭"},
        {"code": "CEG", "name": "コンステレーション・エナジー (米国)", "theme": "米最大の原子力発電企業。AIテック巨人と電力供給契約"},
        {"code": "GEV", "name": "GEヴェルノバ (米国)", "theme": "発電用ガスタービン・送電グリッド設備の世界的リーダー"}
    ],
    "イーロン": [
        {"code": "TSLA", "name": "テスラ (米国)", "theme": "自動運転(FSD)・ロボタクシー・Optimus展開。世界最大のショートスクイーズ銘柄"},
        {"code": "6752.T", "name": "パナソニックHD", "theme": "北米EV向け車載電池およびデータセンター向け蓄電システム"},
        {"code": "5713.T", "name": "住友金属鉱山", "theme": "EV電池向け正極材（ニッケル）および銅などの資源価格連動"},
        {"code": "9433.T", "name": "KDDI (Starlink)", "theme": "SpaceXのStarlinkを活用した衛星・スマホ直接通信サービス"},
        {"code": "7203.T", "name": "トヨタ自動車", "theme": "世界最大の自動車メーカー。北米EV・全固体電池の動向"},
        {"code": "6902.T", "name": "デンソー", "theme": "自動運転・EV用サーマルマネジメント・車載部品"},
        {"code": "6594.T", "name": "ニデック", "theme": "EV用トラクションモーター（e-Axle）の世界展開"},
        {"code": "COIN", "name": "コインベース (米国)", "theme": "暗号資産・ブロックチェーン連動。空売り踏み上げが極めて強い"}
    ],
    "小型株": [
        {"code": "5595.T", "name": "QPS研究所", "theme": "小型SAR衛星コンステレーションによる時価総額拡大の小型宇宙株"},
        {"code": "186A.T", "name": "アストロスケール", "theme": "宇宙ゴミ除去というニッチトップの小型グロース株"},
        {"code": "9348.T", "name": "ispace", "theme": "民間で月面輸送を手掛ける小型宇宙ベンチャー。テーマ性抜群"},
        {"code": "5243.T", "name": "ノート", "theme": "クリエイターエコノミーを牽引する小型メディアプラットフォーム"},
        {"code": "6182.T", "name": "メタリアル", "theme": "AI自動翻訳・生成AI領域での高成長小型株"},
        {"code": "4475.T", "name": "HENNGE", "theme": "クラウドセキュリティ認証基盤の小型ストック型SaaS"},
        {"code": "5031.T", "name": "モイ", "theme": "ライブ配信「ツイキャス」運営・AI音声認識の小型株"},
        {"code": "153A.T", "name": "カウリス", "theme": "金融機関向け不正アクセス検知サービスの小型セキュリティ株"},
        {"code": "247A.T", "name": "Aiロボティクス", "theme": "AIマーケティングを活用したD2C展開の小型グロース株"},
        {"code": "ACHR", "name": "アーチャー・アビエーション (米国)", "theme": "空飛ぶクルマ（eVTOL）実用化の米小型株。ショートカバー急騰が多い"},
        {"code": "JOBY", "name": "ジョビー・アビエーション (米国)", "theme": "トヨタが出資する空飛ぶクルマの有力ベンチャー"},
        {"code": "IONQ", "name": "アイオンQ (米国)", "theme": "商用量子コンピューター開発。空売り比率が高く踏み上げが激しい小型株"},
        {"code": "SOUN", "name": "サウンドハウンドAI (米国)", "theme": "音声AI認識技術で急成長を遂げる小型AI関連の注目株"},
        {"code": "BBAI", "name": "ビッグベア.ai (米国)", "theme": "防衛・政府向けのAI予測アナリティクス小型株"}
    ],
    "IPO": [
        {"code": "9023.T", "name": "東京地下鉄 (東京メトロ)", "theme": "大型IPOの筆頭。高い配当利回りと安定収益で資金流入"},
        {"code": "285A.T", "name": "キオクシアHD", "theme": "半導体メモリー大手の大型IPO。NAND需要回復と連動"},
        {"code": "216A.T", "name": "タイミー", "theme": "スキマバイト仲介のグロースIPO。短期資金が集中"},
        {"code": "186A.T", "name": "アストロスケールHD", "theme": "宇宙デブリ除去ベンチャーの注目IPO"},
        {"code": "141A.T", "name": "トライアルHD", "theme": "リテールAI活用で急成長する流通IPO"},
        {"code": "5253.T", "name": "カバー", "theme": "VTuber事務所「ホロライブ」運営。圧倒的な売買代金"},
        {"code": "9166.T", "name": "GENDA", "theme": "アミューズメント施設M&Aで急成長を続ける注目株"},
        {"code": "RDDT", "name": "レディット (米国IPO)", "theme": "米国大型SNSの注目IPO。ショートスクイーズが多発"},
        {"code": "ARM", "name": "アーム・ホールディングス (米国IPO)", "theme": "ソフトバンクG傘下の半導体設計の要"},
        {"code": "ALAB", "name": "アステラ・ラブズ (米国IPO)", "theme": "AIデータセンター向け高速接続半導体の大型IPO"}
    ],
    "未公開株": [
        {"code": "8595.T", "name": "ジャフコ グループ", "theme": "国内最大手の老舗VC。未公開スタートアップ投資の筆頭"},
        {"code": "8473.T", "name": "SBIホールディングス", "theme": "国内外の未公開フィンテック・半導体企業へ積極投資するVC群を保有"},
        {"code": "9984.T", "name": "ソフトバンクG (SVF)", "theme": "OpenAIなど世界の未公開ユニコーン企業へ投資する実質的ファンド"},
        {"code": "4751.T", "name": "サイバーエージェント", "theme": "藤田ファンドを通じ、有望な未公開ITベンチャーを多数保有"},
        {"code": "8591.T", "name": "オリックス", "theme": "プライベートエクイティ（未公開株買収）の国内トッププレイヤー"},
        {"code": "DXYZ", "name": "Destiny Tech100 (米国・未公開株ファンド)", "theme": "SpaceXやOpenAI等の未公開100社ファンド。猛烈な踏み上げが起きる銘柄"},
        {"code": "KKR", "name": "KKR (米国)", "theme": "世界の未公開株買収・投資を手掛けるオルタナティブ投資の巨人"},
        {"code": "BX", "name": "ブラックストーン (米国)", "theme": "世界最大の未公開株・プライベートアセット運用会社"}
    ]
}

KNOWN_STOCKS = {}
for g, items in STOCK_POOL.items():
    for item in items:
        KNOWN_STOCKS[item["code"]] = {"name": item["name"], "theme": item["theme"], "genre": g}

def normalize_ticker(raw_input):
    s = unicodedata.normalize('NFKC', raw_input).strip().upper()
    if not s:
        return ""
    if "." in s or s.startswith("^") or "=" in s:
        return s
    if len(s) == 4 and any(ch.isdigit() for ch in s):
        return f"{s}.T"
    return s

# --- ⚡ 5分足（Intraday）＋ 🌆 大引け30分MOC 解析エンジン ---
@st.cache_data(ttl=300)
def fetch_5m_intraday_algo(full_code, trigger_high20=None):
    try:
        df5 = yf.Ticker(full_code).history(period="5d", interval="5m")
        if df5 is None or df5.empty or len(df5) < 12:
            return None
        df5 = df5.dropna(subset=['Close', 'Open', 'High', 'Low', 'Volume'])
        if df5.empty:
            return None

        dates = df5.index.date
        latest_date = dates[-1]
        day_df = df5[dates == latest_date].copy()
        if len(day_df) < 6:
            day_df = df5.tail(36).copy()

        tp = (day_df['High'] + day_df['Low'] + day_df['Close']) / 3.0
        vol_sum = day_df['Volume'].cumsum().replace(0, np.nan)
        day_df['VWAP_5m'] = ((tp * day_df['Volume']).cumsum() / vol_sum).fillna(day_df['Close'])

        latest_close = float(day_df['Close'].iloc[-1])
        latest_vwap5 = float(day_df['VWAP_5m'].iloc[-1])
        vwap5_dev = round((latest_close - latest_vwap5) / latest_vwap5 * 100, 2) if latest_vwap5 != 0 else 0.0

        first_3 = day_df.head(3)
        open_p = float(first_3['Open'].iloc[0])
        close_15m = float(first_3['Close'].iloc[-1])
        open_drive_pct = round((close_15m - open_p) / open_p * 100, 2) if open_p != 0 else 0.0

        recent_12 = day_df.tail(12)
        green_bars = int((recent_12['Close'] >= recent_12['Open']).sum())
        twap_green_ratio = round(green_bars / len(recent_12) * 100, 1)

        mean_vol5 = float(day_df['Volume'].mean())
        max_recent_vol = float(day_df.tail(6)['Volume'].max())
        vol_spike_5m = round(max_recent_vol / mean_vol5, 2) if mean_vol5 > 0 else 1.0
        above_vwap_ratio = round(float((day_df['Close'] >= day_df['VWAP_5m']).mean() * 100), 1)

        last_6 = day_df.tail(6)
        close_30m_open = float(last_6['Open'].iloc[0])
        close_30m_end = float(last_6['Close'].iloc[-1])
        close_drive_pct = round((close_30m_end - close_30m_open) / close_30m_open * 100, 2) if close_30m_open != 0 else 0.0

        close_30m_vol_mean = float(last_6['Volume'].mean())
        close_vol_ratio = round(close_30m_vol_mean / mean_vol5, 2) if mean_vol5 > 0 else 1.0
        close_green_bars = int((last_6['Close'] >= last_6['Open']).sum())

        moc_score = 50
        if close_drive_pct >= 0.35 and close_vol_ratio >= 1.25:
            moc_score += 25
        elif close_drive_pct > 0 and close_vol_ratio >= 1.1:
            moc_score += 14
        elif close_drive_pct <= -0.35 and close_vol_ratio >= 1.25:
            moc_score -= 18
        if close_green_bars >= 4:
            moc_score += 10
        if vwap5_dev > 0 and close_30m_end >= float(day_df['High'].max()) * 0.995:
            moc_score += 10
        moc_score = int(min(max(moc_score, 15), 99))

        if close_drive_pct >= 0.3 and close_vol_ratio >= 1.25 and vwap5_dev >= 0:
            moc_status = "🌆 大引けMOC（引け成り）強烈買い集め"
            moc_comment = f"ラスト30分間で出来高が日中平均の<b>{close_vol_ratio}倍</b>に急増し、株価も<b>{close_drive_pct:+.2f}%</b>上昇して高値引け（陽線{close_green_bars}/6本）！空売り勢の買い戻しが翌朝へ持ち越されています。"
        elif close_drive_pct >= 0.1 and close_green_bars >= 4:
            moc_status = "📈 大引けにかけて堅調吸収"
            moc_comment = f"ラスト30分間（陽線{close_green_bars}/6本・変動<b>{close_drive_pct:+.2f}%</b>）で売り物を着実に吸収して引けており、翌朝の寄り付きにプラスの勢いを残しています。"
        elif close_drive_pct <= -0.3 and close_vol_ratio >= 1.2:
            moc_status = "⚠️ 大引け手仕舞い売り優勢"
            moc_comment = f"ラスト30分で出来高を伴い（<b>{close_vol_ratio}倍</b>）<b>{close_drive_pct:+.2f}%</b>下落。手仕舞い売りに押されて引けています。"
        else:
            moc_status = "⚖️ 大引け通常執行（需給均衡）"
            moc_comment = f"ラスト30分間の値動きは<b>{close_drive_pct:+.2f}%</b>（出来高倍率<b>{close_vol_ratio}倍</b>）と均衡しています。"

        score_5m = 50
        score_5m += 10 if vwap5_dev > 0 else -8
        score_5m += 8 if open_drive_pct >= 0.4 else (-5 if open_drive_pct <= -0.5 else 0)
        score_5m += 10 if twap_green_ratio >= 65 else (-5 if twap_green_ratio <= 35 else 0)
        score_5m += 7 if (vol_spike_5m >= 1.8 and vwap5_dev >= 0) else 0
        score_5m += 7 if above_vwap_ratio >= 70 else 0
        score_5m += int((moc_score - 50) * 0.25)
        score_5m = int(min(max(score_5m, 15), 99))

        if vwap5_dev > 0 and twap_green_ratio >= 65:
            status_5m = "🔥 5分足連続買い＆ショートカバー順行"
            comment_5m = f"直近1時間の陽線出現率が<b>{twap_green_ratio}%</b>に達し、5分足VWAP（乖離<b>{vwap5_dev:+.2f}%</b>）の上で買い戻しが継続しています。"
        elif open_drive_pct >= 0.6 and above_vwap_ratio >= 65:
            status_5m = "🚀 寄付き15分オープニングドライブ"
            comment_5m = f"寄付き後15分で<b>{open_drive_pct:+.2f}%</b>の上昇ドライブが発生。日中を通して5分足VWAP上（滞在率<b>{above_vwap_ratio}%</b>）を維持する強い波形です。"
        elif vwap5_dev < -0.3 and above_vwap_ratio < 40:
            status_5m = "🧊 5分足VWAP下抜け（上値重い）"
            comment_5m = f"現在値が5分足VWAPを<b>{vwap5_dev:+.2f}%</b>下回っています。5分足VWAP奪還まで待機推奨。"
        else:
            status_5m = "⚖️ 5分足VWAP攻防・レンジ推移"
            comment_5m = f"5分足VWAP（乖離<b>{vwap5_dev:+.2f}%</b>）を挟んだ攻防です。陽線率は<b>{twap_green_ratio}%</b>です。"

        is_jp = ".T" in full_code
        vwap5_fmt = f"{latest_vwap5:,.0f}円" if is_jp else f"${latest_vwap5:,.2f}"

        n_bars = len(day_df)
        is_closing_30m = np.zeros(n_bars, dtype=bool)
        if n_bars >= 6:
            is_closing_30m[-6:] = True

        vol_vals = day_df["Volume"].astype(float).values
        vol_colors = []
        for idx_b in range(n_bars):
            if is_closing_30m[idx_b] and vol_vals[idx_b] >= mean_vol5 * 1.15:
                vol_colors.append("大引け30分MOC執行")
            elif vol_vals[idx_b] >= mean_vol5 * 1.8:
                vol_colors.append("出来高スパイク")
            else:
                vol_colors.append("通常出来高")

        chart_df = pd.DataFrame({
            "Time": day_df.index.strftime("%H:%M"),
            "Open": day_df["Open"].astype(float).values,
            "High": day_df["High"].astype(float).values,
            "Low": day_df["Low"].astype(float).values,
            "Close": day_df["Close"].astype(float).values,
            "VWAP": day_df["VWAP_5m"].astype(float).values,
            "TriggerLine": float(trigger_high20) if trigger_high20 else latest_vwap5,
            "Volume": vol_vals,
            "BarColor": np.where(day_df["Close"].values >= day_df["Open"].values, "陽線(買い優勢)", "陰線(売り優勢)"),
            "VolColor": vol_colors
        })

        return {
            "vwap5_price": vwap5_fmt, "vwap5_dev": vwap5_dev,
            "open_drive_pct": open_drive_pct, "twap_green_ratio": twap_green_ratio,
            "vol_spike_5m": vol_spike_5m, "above_vwap_ratio": above_vwap_ratio,
            "score_5m": score_5m, "status_5m": status_5m, "comment_5m": comment_5m,
            "close_drive_pct": close_drive_pct, "close_vol_ratio": close_vol_ratio,
            "close_green_bars": close_green_bars, "moc_score": moc_score,
            "moc_status": moc_status, "moc_comment": moc_comment,
            "chart_date": str(latest_date), "chart_df": chart_df
        }
    except Exception:
        return None

def render_5m_candlestick_chart(m5, show_trigger=True):
    if not m5 or "chart_df" not in m5 or m5["chart_df"] is None or m5["chart_df"].empty:
        return
    cdf = m5["chart_df"]

    st.markdown(
        f'<div class="chart-legend-box">'
        f'📅 <b>直近5分足 ({m5["chart_date"]})</b> ｜ '
        f'<span style="color:#dc2626; font-weight:bold;">■ 陽線</span> ／ '
        f'<span style="color:#2563eb; font-weight:bold;">■ 陰線</span> ／ '
        f'<span style="color:#d97706; font-weight:bold;">--- 日中VWAP</span> ／ '
        f'<span style="color:#e11d48; font-weight:bold;">┈┈ 20日高値(踏み上げ線)</span>'
        f'</div>',
        unsafe_allow_html=True
    )

    base = alt.Chart(cdf).encode(
        x=alt.X("Time:N", sort=None, title=None, axis=alt.Axis(labelAngle=-45, labelOverlap=True, labelFontSize=10))
    )
    color_scale = alt.Scale(domain=["陽線(買い優勢)", "陰線(売り優勢)"], range=["#dc2626", "#2563eb"])

    wick = base.mark_rule(size=1.5).encode(
        y=alt.Y("Low:Q", scale=alt.Scale(zero=False), title="株価"), y2="High:Q",
        color=alt.Color("BarColor:N", scale=color_scale, legend=None)
    )
    body = base.mark_bar(size=6).encode(
        y=alt.Y("Open:Q", scale=alt.Scale(zero=False)), y2="Close:Q",
        color=alt.Color("BarColor:N", scale=color_scale, legend=None),
        tooltip=[
            alt.Tooltip("Time:N", title="時刻"), alt.Tooltip("Open:Q", title="始値", format=",.1f"),
            alt.Tooltip("High:Q", title="高値", format=",.1f"), alt.Tooltip("Low:Q", title="安値", format=",.1f"),
            alt.Tooltip("Close:Q", title="終値", format=",.1f"), alt.Tooltip("VWAP:Q", title="5分足VWAP", format=",.1f")
        ]
    )
    vwap_line = base.mark_line(color="#d97706", strokeWidth=2.5, strokeDash=[4, 2]).encode(
        y=alt.Y("VWAP:Q", scale=alt.Scale(zero=False))
    )

    min_p, max_p = float(cdf["Low"].min()), float(cdf["High"].max())
    trig_val = float(cdf["TriggerLine"].iloc[0])
    if show_trigger and (min_p * 0.96 <= trig_val <= max_p * 1.04):
        trig_line = base.mark_line(color="#e11d48", strokeWidth=1.8, strokeDash=[2, 2]).encode(
            y=alt.Y("TriggerLine:Q", scale=alt.Scale(zero=False))
        )
        price_chart = (wick + body + vwap_line + trig_line).properties(height=200)
    else:
        price_chart = (wick + body + vwap_line).properties(height=200)

    vol_color_scale = alt.Scale(domain=["大引け30分MOC執行", "出来高スパイク", "通常出来高"], range=["#9333ea", "#f59e0b", "#94a3b8"])
    vol_chart = base.mark_bar(size=6).encode(
        y=alt.Y("Volume:Q", title="出来高", axis=alt.Axis(format="~s", labelFontSize=9)),
        color=alt.Color("VolColor:N", scale=vol_color_scale, legend=None)
    ).properties(height=70)

    st.altair_chart(alt.vconcat(price_chart, vol_chart, spacing=4).resolve_scale(x="shared"), use_container_width=True)

# --- 🧠 7大AI合議エンジン（会議のまとめ・最終コンセンサスを超詳細化！） ---
def run_7ai_council_algorithm(r, m5=None):
    prob = r["prob"]
    payoff = r["payoff"]
    edge = r["edge"]
    rsi = r["rsi"]
    vol_ratio = r["vol_ratio"]
    atr_pct = r["atr_pct"]
    macro_score = r["macro_score"]
    sq_score = r["squeeze_score"]
    sq_type = r["squeeze_type"]
    tokugai_prob = r["tokugai_prob"]
    pts_gap = r["pts_gap_pct"]
    macd_up = "強気" in r["macd_state"]

    s5 = m5["score_5m"] if m5 else 55
    vwap5_dev = m5["vwap5_dev"] if m5 else 0.0
    moc_score = m5["moc_score"] if m5 else r["closing_power_score"]
    close_vol_r = m5["close_vol_ratio"] if m5 else 1.0
    vwap_ref = m5['vwap5_price'] if m5 else r['vwap_price']

    half_lot = max(1, r['lot_info']['shares'] // 2)
    rem_lot = max(0, r['lot_info']['shares'] - half_lot)

    # 1. Claude (リスク管理・資金配分担当)
    claude_raw = 50 + (prob - 50) * 0.85 + (payoff - 1.0) * 16 - max(0, atr_pct - 3.5) * 4 + (moc_score - 50) * 0.15 + (sq_score - 50) * 0.12
    if rsi > 78 and sq_score < 70: claude_raw -= 12
    elif rsi < 35: claude_raw += 8
    claude_score = int(min(max(round(claude_raw), 15), 99))

    if claude_score >= 70:
        claude_stance = "🟢 リスクに対して利益期待が抜群（積極参戦OK）"
        claude_comment = (
            f"<b>【結論：勝ちやすく負けにくい優位な局面です】</b><br>"
            f"・過去同じチャートの形が出たとき、翌朝に上がった確率は <b>{prob}%（{r['count']}）</b>、勝ちトレードの平均利益は負けの <b>{payoff}倍</b> あります。<br>"
            f"・<b>注意点：</b>もし明日の朝、特買いライン（<b>{r['tokugai_line']}</b>）を超えて大きく高く始まった場合は、飛びつき買いによる高値掴みを防ぐため、最初は予定株数の半分（<b>{half_lot:,}株</b>）だけ買い、逆指値（<b>{r['sl_price']}</b>）を必ずセットしてください。"
        )
    elif claude_score >= 52:
        claude_stance = "🟡 条件付き承認（朝の押し目を待って買う）"
        claude_comment = (
            f"<b>【結論：朝イチの成行買いは避け、少し下がった所を狙いましょう】</b><br>"
            f"・期待値はプラス（<b>{edge:+.2f}%</b>）ですが、1日の値動き幅（ATR: {atr_pct}%）がやや大きめです。<br>"
            f"・9時00分にすぐ買うのではなく、日中の平均買値である <b>5分足VWAP（{vwap_ref}）</b> 付近まで株価が落ち着いてから指値で買うと、損切りリスクを最小限に抑えられます。"
        )
    else:
        claude_stance = "🔴 リスク警戒（今回は見送り推奨）"
        claude_comment = (
            f"<b>【結論：無理に手を出さず、資金を守る場面です】</b><br>"
            f"・株価の乱高下幅（{atr_pct}%）に対して、見込める利益の期待値（{edge:+.2f}%）が小さく、割に合いません。より条件の良い上位銘柄に資金を回すことを強く推奨します。"
        )

    # 2. Grok (特買い気配＆空売り踏み上げ担当)
    grok_raw = 45 + (vol_ratio - 1.0) * 16 + (10 if macd_up else -6) + ((moc_score - 50) * 0.18) + ((s5 - 50) * 0.18) + ((sq_score - 50) * 0.25) + (tokugai_prob * 0.15)
    grok_score = int(min(max(round(grok_raw), 15), 99))

    if grok_score >= 70:
        grok_stance = "🔥 特買い＆空売り勢のパニック買い戻し発生へ！"
        grok_comment = (
            f"<b>【結論：空売りしている投資家が損失に耐えきれず、朝イチに買い戻す可能性が極めて高いです】</b><br>"
            f"・明日の朝9時に買い注文が殺到してすぐ値段がつかない『特買い』になる確率は <b>{tokugai_prob}%</b> です。<br>"
            f"・現在「<b>{sq_type}</b>」の状態にあり、直近20日高値（<b>{r['squeeze_trigger_price']}</b>）を超えると、空売り勢の強制ロスカット（成行の買い戻し）が連鎖して一気に急騰しやすい波形です。"
        )
    elif grok_score >= 52:
        grok_stance = "⚡ 朝8:50の気配値次第で踏み上げ急騰"
        grok_comment = (
            f"<b>【結論：朝8時50分の板気配を見て、強ければ乗るチャンスです】</b><br>"
            f"・夜間の先物や米国株の動きから計算した明日の予想スタート価格は <b>{r['pts_est_price']}（前日比 {pts_gap:+.2f}%）</b> です。<br>"
            f"・朝8:50〜8:58の気配値が、空売り勢の防衛ライン（<b>{r['squeeze_trigger_price']}</b>）に近い、または上回っていれば一気に火がつきます。"
        )
    else:
        grok_stance = "🧊 爆発力・踏み上げエネルギー不足"
        grok_comment = (
            f"<b>【結論：明日の朝に急騰を巻き起こすほどの買いエネルギーがまだ溜まっていません】</b><br>"
            f"・出来高倍率（{vol_ratio}倍）や夜間連動（{pts_gap:+.2f}%）が穏やかなため、特買いやショートスクイーズ（踏み上げ）を狙うには力不足です。"
        )

    # 3. GPT (ファンダ・テクニカル・夜間連動の総合バランサー)
    gpt_raw = (r["ai_score"] * 0.38) + (claude_score * 0.2) + (grok_score * 0.2) + (s5 * 0.12) + (sq_score * 0.1) + (macro_score * 1.2)
    gpt_score = int(min(max(round(gpt_raw), 15), 99))

    if gpt_score >= 70:
        gpt_stance = "💎 すべての好条件が揃ったS級セットアップ"
        gpt_comment = (
            f"<b>【結論：チャート・出来高・大引けの買い・夜間の追い風がすべて揃っています】</b><br>"
            f"・前日の大引け間際の買い集め（<b>{moc_score}点</b>）、空売り踏み上げ度（<b>{sq_score}点</b>）、夜間の予想ギャップ（<b>{pts_gap:+.2f}%</b>）のどれを取っても高水準です。<br>"
            f"・素直にトレンドに従って順張りでついていくのが最も勝率の高い王道パターンです。"
        )
    elif gpt_score >= 52:
        gpt_stance = "⚖️ 全体的に堅調（焦らず押し目買い）"
        gpt_comment = (
            f"<b>【結論：方向感は上向きですが、買うタイミングだけ工夫しましょう】</b><br>"
            f"・日足のトレンドは良好です。寄り付き直後の乱高下が落ち着く9時10分〜15分頃に、株価が5分足VWAP（<b>{vwap_ref}</b>）の上でしっかり支えられているのを確認してから買うのがベストです。"
        )
    else:
        gpt_stance = "🛡️ 様子見・トレンド発生待ち"
        gpt_comment = (
            f"<b>【結論：今はまだ買いシグナルが揃っていません】</b><br>"
            f"・複数の指標を総合すると、上がるか下がるかが五分五分の状態です。明確な出来高増加が出るまで待ちましょう。"
        )

    # 4. Gemini (米国株・為替・セクター資金の流れ担当)
    gemini_raw = 48 + (prob - 50) * 0.5 + (edge * 16) + (macro_score * 2.0) + ((moc_score - 50) * 0.2) + ((sq_score - 50) * 0.2)
    if vol_ratio >= 1.15 and macd_up: gemini_raw += 8
    gemini_score = int(min(max(round(gemini_raw), 15), 99))

    if gemini_score >= 70:
        gemini_stance = "🌐 海外投資家の資金流入＆セクター追い風"
        gemini_comment = (
            f"<b>【結論：『{r['genre']}』関連株に海外の大きな資金が入ってきています】</b><br>"
            f"・テーマ背景（{r['theme']}）に加え、米国市場や日経先物の動きを反映した夜間理論価格は <b>{r['pts_est_price']}</b> と好調です。<br>"
            f"・明日は朝からセクター全体が買われやすく、第一目標の <b>{r['tp_price']}（+{r['tp_pct']}%）</b> を十分に狙える環境です。"
        )
    elif gemini_score >= 52:
        gemini_stance = "🧭 テーマ性は良好・朝の地合い確認"
        gemini_comment = (
            f"<b>【結論：銘柄自体のテーマは強いので、全体の地合いだけ確認してください】</b><br>"
            f"・明日の朝、日経先物や米国株が大きく崩れていなければ、予想価格（<b>{r['pts_est_price']}</b>）付近から堅調に推移する見込みです。"
        )
    else:
        gemini_stance = "🔭 セクターへの資金流入が一服"
        gemini_comment = (
            f"<b>【結論：他の注目テーマへ資金が移動している可能性があります】</b><br>"
            f"・『{r['genre']}』セクター全体への追い風がやや弱まっているため、本日は深追い禁物です。"
        )

    # 5. Perplexity (出来高の裏付け・騙し上げチェック担当)
    perp_raw = 50 + (macro_score * 2.5) + ((moc_score - 50) * 0.25) + ((s5 - 50) * 0.2) + ((sq_score - 50) * 0.2)
    if vol_ratio >= 1.3: perp_raw += 10
    elif vol_ratio < 0.85 and r["diff"] > 1.5: perp_raw -= 12
    perplexity_score = int(min(max(round(perp_raw), 15), 99))

    if perplexity_score >= 70:
        perplexity_stance = "🔍 本物の大口買いを確認（騙し上げの可能性極小）"
        perplexity_comment = (
            f"<b>【結論：見せかけの上昇ではなく、実際の資金がしっかり入っています】</b><br>"
            f"・普段の <b>{vol_ratio}倍</b> の出来高があり、さらに前日終了前の30分間にも普段の <b>{close_vol_r}倍</b> の買いが入って高値引け（引けピン度 <b>{r['close_pos_pct']}%</b>）しています。<br>"
            f"・<b>朝のチェック法：</b>朝8時55分を過ぎても板の「成行買い」の株数が減らなければ、本物の大口買いなので安心してついていけます。"
        )
    elif perplexity_score >= 52:
        perplexity_stance = "📡 出来高は合格圏（8:55の「見せ板」だけ注意）"
        perplexity_comment = (
            f"<b>【結論：需給データは良好ですが、朝8時台の『見せ板』にだけ注意してください】</b><br>"
            f"・朝8:00〜8:45頃は、買わせるためのダミー注文（見せ板）が出ることがあります。必ず注文取り消しが制限される <b>朝8時55分〜8時58分の気配値</b> を見てから最終判断してください。"
        )
    else:
        perplexity_stance = "⚠️ 出来高不足による「寄り天（朝だけ高くて後で下がる）」警戒"
        perplexity_comment = (
            f"<b>【結論：朝だけ高く始まって、すぐ売られる『寄り天』に注意が必要です】</b><br>"
            f"・出来高の裏付け（{vol_ratio}倍）がやや薄いため、高く始まったところに飛びつくと危険です。"
        )

    # 6. Genspark (具体的な買い方・戦術まとめ担当)
    genspark_raw = (claude_score + grok_score + gpt_score + gemini_score + perplexity_score) / 5.0 + (6 if (sq_score >= 68 and moc_score >= 65) else 0)
    genspark_score = int(min(max(round(genspark_raw), 15), 99))

    if genspark_score >= 70:
        genspark_stance = "✨ 推奨戦術：『2回に分けて買う』分割エントリー戦術"
        genspark_comment = (
            f"<b>【結論：一度に全部買わず、2回に分けて買うと最も安全で利益が伸びます】</b><br>"
            f"・<b>1回目（9:00 寄付き）：</b>まず推奨株数の半分（<b>{half_lot:,}株</b>）を購入します。<br>"
            f"・<b>2回目（9:05〜9:30）：</b>寄り付いた後、5分足VWAP（<b>{vwap_ref}</b>）で下げ止まって反発した時、または踏み上げライン（<b>{r['squeeze_trigger_price']}</b>）を突破した瞬間に残りの <b>{rem_lot:,}株</b> を追加購入してください。"
        )
    elif genspark_score >= 52:
        genspark_stance = "🎯 推奨戦術：『朝9:15まで待って買う』初動見極め戦術"
        genspark_comment = (
            f"<b>【結論：9時00分の寄り付きは見送り、最初の15分間の動きを見てから買いましょう】</b><br>"
            f"・9:00〜9:15（5分足3本分）を見て、ローソク足が5分足VWAP（<b>{vwap_ref}</b>）より上にキープできていれば、そこから指値で <b>{half_lot:,}〜{r['lot_info']['shares']:,}株</b> エントリーするのが最も確実です。"
        )
    else:
        genspark_stance = "🛑 推奨戦術：本日はエントリー見送り（資金温存）"
        genspark_comment = (
            f"<b>【結論：今日は買わずにウォッチリストで観察するだけにしましょう】</b><br>"
            f"・勝率とリスクリワードのバランスが基準に達していません。キャッシュ（現金）を残して次のチャンスを待つのがプロの判断です。"
        )

    # 7. NotebookLM (過去1年間のデータ照合・実績担当)
    nblm_raw = 48 + (prob - 50) * 0.9 + (payoff - 1.0) * 14 + (10 if (sq_score >= 65 and moc_score >= 60) else -4)
    notebooklm_score = int(min(max(round(nblm_raw), 15), 99))

    if notebooklm_score >= 70:
        notebooklm_stance = "📓 過去1年の勝ちパターンと高一致！"
        notebooklm_comment = (
            f"<b>【結論：過去1年間のデータの中で、翌朝もっとも大きく上がりやすかった形と一致しています】</b><br>"
            f"・過去1年で同じシグナルが出た日は <b>{r['count']}</b> あり、そのうち <b>{prob}%</b> の確率で翌朝プラス発進しています（過去最大で <b>+{r['max_win_gap']}%</b> の大幅ギャップアップ実績あり）。データの裏付けはバッチリです。"
        )
    elif notebooklm_score >= 52:
        notebooklm_stance = "📚 過去1年のデータでは平均以上の勝率"
        notebooklm_comment = (
            f"<b>【結論：過去データ上はまずまずの好成績（勝率 {prob}%）です】</b><br>"
            f"・過去同条件（{r['count']}）では平均 <b>{r['gap']:+.2f}%</b>（最大 <b>+{r['max_win_gap']}%</b>）で始まっています。日中の5分足VWAPより上で推移する日はさらに勝率が上がります。"
        )
    else:
        notebooklm_stance = "🗂️ 過去データでは勝ったり負けたり（再現性低め）"
        notebooklm_comment = (
            f"<b>【結論：過去1年の記録では、上がるか下がるかクセが読みづらい形です】</b><br>"
            f"・過去の勝率は <b>{prob}%（{r['count']}）</b> に留まっており、統計的な優位性はあまり高くありません。"
        )

    scores_list = [claude_score, grok_score, gpt_score, gemini_score, perplexity_score, genspark_score, notebooklm_score]
    final_score = int(round(sum(scores_list) / 7.0))
    bullish_count = sum(1 for s in scores_list if s >= 65)
    cautious_count = sum(1 for s in scores_list if 50 <= s < 65)
    bearish_count = sum(1 for s in scores_list if s < 50)

    # ★「7大AI最終コンセンサス（会議のまとめ）」を超・詳細化！
    if final_score >= 74:
        rank_title = f"👑 【7大AI満場一致：Sランク大本命（合議スコア {final_score}点 / 強気賛成 {bullish_count}名）】"
        summary_intro = (
            f"7大AIのうち<b>{bullish_count}名が強気（積極買い）</b>と判定しました。過去1年の統計勝率（<b>{prob}%・{r['count']}</b>）、"
            f"前日大引けMOCの強い買い集め（<b>{moc_score}点・引けピン度{r['close_pos_pct']}%</b>）、"
            f"そして空売り勢の踏み上げ圧力（<b>{sq_score}点</b>）と翌朝特買い確率（<b>{tokugai_prob}%</b>）がすべて高次元で一致した<b>本日の最優先ターゲット</b>です。"
        )
    elif final_score >= 61:
        rank_title = f"✅ 【7大AI合議結論：Aランク有力候補（合議スコア {final_score}点 / 強気 {bullish_count}名・慎重 {cautious_count}名）】"
        summary_intro = (
            f"夜間市場の追い風（理論気配 <b>{r['pts_est_price']}・{pts_gap:+.2f}%</b>）と前日の買い残し（大引けMOC <b>{moc_score}点</b>）により、"
            f"翌朝は買い先行でスタートする優位性が確認されました。高値掴みだけを避けて分割エントリーすることで、高いリスクリワード（損益比 <b>{payoff}倍</b>）が見込めます。"
        )
    elif final_score >= 50:
        rank_title = f"⚠️ 【7大AI合議結論：Bランク条件付き（合議スコア {final_score}点 / 強気 {bullish_count}名・慎重 {cautious_count}名・警戒 {bearish_count}名）】"
        summary_intro = (
            f"上昇ポテンシャルはありますが、AI間で「モメンタム期待（Grok/Gemini）」と「ボラティリティ警戒（Claude/Perplexity）」の意見が分かれています。"
            f"9時00分の成行飛びつき買いは厳禁とし、<b>9時15分までの初動で5分足VWAP（{vwap_ref}）の上を維持できるか</b>を確認してからの押し目買いに徹してください。"
        )
    else:
        rank_title = f"🛑 【7大AI合議結論：Cランク見送り推奨（合議スコア {final_score}点 / 警戒 {bearish_count}名）】"
        summary_intro = (
            f"7大AIの過半数が「今はリスクに対してリターンが見合わない（期待値 <b>{edge:+.2f}%</b>）」と結論付けました。"
            f"出来高の裏付けや踏み上げエネルギーが不足しているため、本日は無理にエントリーせず、資金をSランク・Aランク銘柄に集中させることを強く推奨します。"
        )

    verdict_html = (
        f'<div style="font-size:14.5px; font-weight:bold; color:#fde047; margin-bottom:8px;">{rank_title}</div>'
        f'<div style="font-size:12.5px; color:#f8fafc; margin-bottom:10px;">{summary_intro}</div>'
        f'<div class="consensus-section">'
        f'<b>① 🌅 翌朝8:50〜9:00 寄り前気配の最終判定基準</b><br>'
        f'・夜間理論スタート価格は <b>{r["pts_est_price"]}（前日比 {pts_gap:+.2f}%）</b> です。朝8:55以降に注文取消が制限された段階で、気配値が <b>{r["price"]}〜{r["pts_est_price"]}</b> 以上を維持し、板の「成行買い株数 ＞ 成行売り株数」であれば機関・大口の本物の買いです。<br>'
        f'・もし気配値が <b>{r["tokugai_line"]}（+{r["tokugai_pct_threshold"]}%）</b> を超えている場合は<b>「特別買い気配（特買い）」</b>となり、寄付き直後から強い上値追いが期待できます。'
        f'</div>'
        f'<div class="consensus-section">'
        f'<b>② ⚡ 9:00〜9:30 具体的な買い方と空売り踏み上げの急所</b><br>'
        f'・推奨購入数は総資金（{total_capital:,.0f}円）に対し <b>合計 {r["lot_info"]["shares"]:,}株（投資額 {r["lot_info"]["position_value"]:,.0f}円）</b> です。<br>'
        f'・<b>第1弾（打診買い）：</b>朝9:00の寄付き（または特買い成立時）に、まず半分の <b>{half_lot:,}株</b> だけエントリーします。<br>'
        f'・<b>第2弾（追撃買い）：</b>寄付き後の押し目で <b>5分足VWAP（{vwap_ref}）</b> 付近で下げ止まり陽線が出た瞬間、または空売り勢の最大ロスカットラインである <b>20日高値（{r["squeeze_trigger_price"]}）</b> を出来高を伴って上抜けた瞬間に、残りの <b>{rem_lot:,}株</b> を追撃投入します。'
        f'</div>'
        f'<div class="consensus-section">'
        f'<b>③ 🎯 出口戦略（利確ターゲット）と 🛡️ 絶対撤退ライン（損切り）</b><br>'
        f'・<b>第一利確目標：</b><b>{r["tp_price"]}（+{r["tp_pct"]}%）</b> に到達した時点で半分を利益確定し、残りは5分足VWAPを割るまで利益を伸ばします（過去同条件での最大ギャップアップ実績は <b>+{r["max_win_gap"]}%</b>）。<br>'
        f'・<b>損切り逆指値：</b>購入直後に必ず <b>{r["sl_price"]}（{r["sl_pct"]}%）</b> に逆指値（ストップロス）を入れてください。万が一シナリオが崩れても、損失額は許容リスク内の <b>約{r["lot_info"]["risk_amount"]:,.0f}円（総資金の{risk_tolerance_pct}%）</b> に完全に限定されます。'
        f'</div>'
        f'<div class="consensus-section" style="border-left-color:#f87171;">'
        f'<b>④ ⚠️ 見送り・撤退すべき危険サイン（リスクシナリオ）</b><br>'
        f'・もし朝9:00に大きくギャップアップして始まった直後、最初の5分足〜15分足で<b>大陰線をつけて5分足VWAP（{vwap_ref}）を明確に下抜けた場合</b>は「寄り天（大口の利食いぶつけ）」のサインですので、第2弾の追加買いは中止し、速やかに撤退してください。'
        f'</div>'
    )

    easy_guide = (
        f"<b>🔰 【スマホを見ながらそのまま使える！明日の朝の行動チェックリスト】</b><br>"
        f"<b>STEP 1（朝8:55）：</b>証券アプリの板を見て、気配値が <b>{r['pts_est_price']}</b> 付近で買い優勢か確認する（<b>{r['tokugai_line']}</b> 超えなら特買い祭り！）<br>"
        f"<b>STEP 2（朝9:00）：</b>まずは推奨株数の半分 <b>{half_lot:,}株</b> を買う。すぐ逆指値（損切り予約）を <b>{r['sl_price']}</b> にセットする。<br>"
        f"<b>STEP 3（朝9:05〜9:30）：</b>株価が <b>{vwap_ref}（VWAP）</b> の上で反発するか、<b>{r['squeeze_trigger_price']}（踏み上げ線）</b> を超えたら残りの <b>{rem_lot:,}株</b> を追加し、<b>{r['tp_price']}</b> で利益確定を狙う！"
    )

    return {
        "claude_score": claude_score, "claude_stance": claude_stance, "claude_comment": claude_comment,
        "grok_score": grok_score, "grok_stance": grok_stance, "grok_comment": grok_comment,
        "gpt_score": gpt_score, "gpt_stance": gpt_stance, "gpt_comment": gpt_comment,
        "gemini_score": gemini_score, "gemini_stance": gemini_stance, "gemini_comment": gemini_comment,
        "perplexity_score": perplexity_score, "perplexity_stance": perplexity_stance, "perplexity_comment": perplexity_comment,
        "genspark_score": genspark_score, "genspark_stance": genspark_stance, "genspark_comment": genspark_comment,
        "notebooklm_score": notebooklm_score, "notebooklm_stance": notebooklm_stance, "notebooklm_comment": notebooklm_comment,
        "final_score": final_score, "verdict_html": verdict_html, "easy_guide": easy_guide
    }

# --- 7大AIに対する個別質問への自動回答エンジン（さらに詳しく回答） ---
def generate_7ai_qa_response(question, r, debate, lot_info, m5=None):
    q_lower = question.lower()
    m5_vwap = m5["vwap5_price"] if m5 else r["vwap_price"]
    m5_status = m5["status_5m"] if m5 else "5分足データ集計中"
    moc_st = m5["moc_status"] if m5 else r["closing_status"]
    half_s = max(1, lot_info['shares'] // 2)
    rem_s = max(0, lot_info['shares'] - half_s)

    if any(k in q_lower for k in ["特買", "気配", "pts", "夜間", "adr", "先物", "8時", "板", "寄り付", "寄付き"]):
        return (
            f"<b>🚨 【「{question}」への7大AI詳細回答：特買い＆朝8:50気配値の見極め方】</b><br>"
            f"・<b>夜間理論スタート価格：</b>米国株・SOX指数・CME日経先物の変動と前日大引けの買い残しから算出した明日の理論気配値は <b>{r['pts_est_price']}（前日比 {r['pts_gap_pct']:+.2f}%）</b>、特買い発生確率は <b>{r['tokugai_prob']}%</b> です。<br>"
            f"・<b>特買い発動ライン：</b>気配値が <b>{r['tokugai_line']}（+{r['tokugai_pct_threshold']}%超）</b> を上回ると、9:00にすぐ値がつかず3分ごとに気配値を切り上げる「特別買い気配（特買い）」となります。<br>"
            f"・<b>特買いで寄り付いた直後の動き方：</b>特買いで高く寄り付いた直後は、最初の5分間（1本目の5分足）で利食い売りが出ることがあります。そのため、寄付きでは半分の <b>{half_s:,}株</b> だけ買い、寄付き後に下ヒゲをつけて <b>5分足VWAP（{m5_vwap}）</b> の上で踏ん張ったのを確認してから残り <b>{rem_s:,}株</b> を入れると高値掴みを完全に防げます。"
        )
    elif any(k in q_lower for k in ["踏み上げ", "スクイーズ", "空売", "ショート", "買戻", "買い戻", "ロスカット", "トリガー"]):
        return (
            f"<b>🔥 【「{question}」への7大AI詳細回答：空売り踏み上げ（ショートスクイーズ）攻略】</b><br>"
            f"・<b>現在の踏み上げ診断：</b>踏み上げスコアは <b>{r['squeeze_score']}点（{r['squeeze_type']}）</b> です。<br>"
            f"・<b>最大の急所（トリガー価格）：</b>過去20日間で空売りした投資家の損切り逆指値が最も溜まっている防衛ラインは <b>{r['squeeze_trigger_price']}（現在値から {r['dist_to_high20']:+.2f}%）</b> です。<br>"
            f"・<b>どう乗るべきか：</b>株価が <b>{r['squeeze_trigger_price']}</b> を1ティックでも上抜けると、売り方の強制買い戻し（成行買い）が一斉に発動し、板が薄くなって一気に <b>{r['tp_price']}</b> 方向へ跳ねやすくなります。突破した瞬間の順張り追撃が非常に有効です。"
        )
    elif any(k in q_lower for k in ["5分", "五分", "初動", "日中", "vwap", "チャート", "大引", "moc"]):
        return (
            f"<b>⚡ 【「{question}」への7大AI詳細回答：5分足チャート＆大引けMOCの活用法】</b><br>"
            f"・<b>前日大引け〜5分足の状況：</b>前日ラスト30分間の動きは「<b>{moc_st}</b>」、5分足トレンドは「<b>{m5_status}</b>」です。<br>"
            f"・<b>5分足VWAP（{m5_vwap}）の使い方：</b>チャート上のオレンジ色の点線（5分足VWAP）は「その日に買った投資家全員の平均買値」です。ローソク足がこの線より<b>上</b>にあれば全員が含み益で売りが出にくく、<b>下</b>に割ると含み損の投げ売りが出やすくなります。<br>"
            f"・したがって、朝9:00〜9:15の初動でローソク足が <b>{m5_vwap}</b> の上をキープしている限りは強気ホールド＆押し目買いが大正解です。"
        )
    else:
        return (
            f"<b>🤖 【「{question}」に対する7大AIからの具体的アドバイス】</b><br>"
            f"・<b>総合評価：</b>7大AI合議スコアは <b>{debate['final_score']}点 / 100点</b>（過去勝率 <b>{r['prob']}%</b>・期待値 <b>{r['edge']:+.2f}%</b>）です。<br>"
            f"・<b>資金配分と株数：</b>あなたの設定資金（{total_capital:,.0f}円・許容リスク{risk_tolerance_pct}%）における最適株数は <b>合計 {lot_info['shares']:,}株</b> です。<br>"
            f"・<b>具体的な注文手順：</b><br>"
            f"　① まず寄付き（目安 <b>{r['price']} 〜 {r['pts_est_price']}</b>）で半分の <b>{half_s:,}株</b> を購入。<br>"
            f"　② 5分足VWAP（<b>{m5_vwap}</b>）での反発、または踏み上げライン（<b>{r['squeeze_trigger_price']}</b>）突破で残り <b>{rem_s:,}株</b> を追加。<br>"
            f"　③ 利確指値を <b>{r['tp_price']}（+{r['tp_pct']}%）</b>、逆指値（損切り）を <b>{r['sl_price']}（{r['sl_pct']}%）</b> に置いてトレードしてください。"
        )

# --- コールバック関数（タブや会議画面が絶対に閉じないように制御） ---
def cb_toggle_debate(unique_key):
    is_open = st.session_state["active_debates"].get(unique_key, False)
    st.session_state["active_debates"][unique_key] = not is_open
    if is_open and unique_key in st.session_state["debate_Animated"]:
        st.session_state["debate_Animated"].remove(unique_key)

def cb_toggle_watchlist(code, r_data):
    if code in st.session_state["watchlist"]:
        del st.session_state["watchlist"][code]
    else:
        st.session_state["watchlist"][code] = r_data

def cb_ask_preset_question(unique_key, q_text, r_data, debate_data, m5_data):
    st.session_state["active_debates"][unique_key] = True
    st.session_state["debate_Animated"].add(unique_key)
    if unique_key not in st.session_state["stock_chats"]:
        st.session_state["stock_chats"][unique_key] = []
    ans = generate_7ai_qa_response(q_text, r_data, debate_data, r_data["lot_info"], m5_data)
    st.session_state["stock_chats"][unique_key].append({"q": q_text, "a": ans})

def cb_ask_custom_question(unique_key, input_key, r_data, debate_data, m5_data):
    user_q = st.session_state.get(input_key, "").strip()
    if user_q:
        st.session_state["active_debates"][unique_key] = True
        st.session_state["debate_Animated"].add(unique_key)
        if unique_key not in st.session_state["stock_chats"]:
            st.session_state["stock_chats"][unique_key] = []
        ans = generate_7ai_qa_response(user_q, r_data, debate_data, r_data["lot_info"], m5_data)
        st.session_state["stock_chats"][unique_key].append({"q": user_q, "a": ans})
        st.session_state[input_key] = ""

def cb_clear_chat(unique_key):
    st.session_state["stock_chats"][unique_key] = []

# --- マクロ市場データ取得 ---
@st.cache_data(ttl=900)
def fetch_macro_market():
    macro_tickers = {
        "sp500":  {"codes": ["^GSPC"],         "label": "🇺🇸 米S&P500"},
        "sox":    {"codes": ["^SOX"],          "label": "💽 米SOX半導体"},
        "usdjpy": {"codes": ["JPY=X"],         "label": "💴 ドル円為替"},
        "nk_fut": {"codes": ["NIY=F", "^N225"], "label": "🇯🇵 CME日経先物"},
        "vix":    {"codes": ["^VIX"],          "label": "⚡ VIX恐怖指数"}
    }
    macro_data = {}
    for key, info in macro_tickers.items():
        fetched = False
        for c in info["codes"]:
            try:
                df_m = yf.Ticker(c).history(period="5d")
                if df_m is not None and not df_m.empty:
                    df_m = df_m.dropna(subset=['Close'])
                    if len(df_m) >= 2:
                        latest_c = float(df_m['Close'].iloc[-1])
                        prev_c = float(df_m['Close'].iloc[-2])
                        if not np.isnan(latest_c) and not np.isnan(prev_c) and prev_c != 0:
                            diff_pct = round((latest_c - prev_c) / prev_c * 100, 2)
                            lbl = "🇯🇵 日経平均(現物)" if (key == "nk_fut" and c == "^N225") else info["label"]
                            macro_data[key] = {"price": latest_c, "diff": diff_pct, "label": lbl}
                            fetched = True
                            break
            except Exception:
                continue
        if not fetched:
            macro_data[key] = {"price": 0.0, "diff": 0.0, "label": info["label"]}
    return macro_data

# --- メイン解析関数 ---
@st.cache_data(ttl=1800)
def fetch_and_analyze(code, name=None, theme=None, genre="個別検索", macro=None, boost_moc=True, boost_squeeze=True, boost_tokugai=True):
    try:
        ticker_obj = yf.Ticker(code)
        df = ticker_obj.history(period="1y")
        if df is None or df.empty or len(df) < 40:
            return None

        df = df.dropna(subset=['Close', 'Open', 'High', 'Low', 'Volume'])
        if len(df) < 40:
            return None

        if code in KNOWN_STOCKS:
            name = name or KNOWN_STOCKS[code]["name"]
            theme = theme or KNOWN_STOCKS[code]["theme"]
            genre = genre if genre != "個別検索" else KNOWN_STOCKS[code]["genre"]
        else:
            name = name or code.replace(".T", "")
            theme = theme or "カスタム指定銘柄（過去1年の日足・需給データに基づく統計解析）"

        df['Prev_Close'] = df['Close'].shift(1)
        df['Day_Return'] = (df['Close'] - df['Prev_Close']) / df['Prev_Close'] * 100
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['Vol_MA20'] = df['Volume'].rolling(20).mean().replace(0, np.nan)
        df['Vol_Ratio'] = (df['Volume'] / df['Vol_MA20']).fillna(1.0)

        delta = df['Close'].diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss.replace(0, np.nan)
        df['RSI'] = (100 - (100 / (1 + rs))).fillna(50.0)

        df['BB_Std'] = df['Close'].rolling(20).std().replace(0, np.nan)
        df['BB_Sigma'] = ((df['Close'] - df['MA20']) / df['BB_Std']).fillna(0.0)
        df['BB_Width'] = (df['BB_Std'] * 4.0 / df['MA20'] * 100).fillna(10.0)
        df['BB_Width_Min20'] = df['BB_Width'].rolling(20).min().fillna(5.0)

        ema12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = ema12 - ema26
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
        df['MACD_Hist_Diff'] = df['MACD_Hist'].diff()

        tr1 = df['High'] - df['Low']
        tr2 = (df['High'] - df['Prev_Close']).abs()
        tr3 = (df['Low'] - df['Prev_Close']).abs()
        df['TR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['ATR'] = df['TR'].rolling(14).mean().fillna(df['Close'] * 0.02)
        df['ATR_Pct'] = (df['ATR'] / df['Close'] * 100).fillna(2.0)

        high_low = (df['High'] - df['Low']).replace(0, np.nan)
        df['Close_Pos'] = ((df['Close'] - df['Low']) / high_low).fillna(0.5)
        body_bottom = df[['Open', 'Close']].min(axis=1)
        df['Lower_Shadow'] = ((body_bottom - df['Low']) / high_low).fillna(0.0)
        body_top = df[['Open', 'Close']].max(axis=1)
        df['Upper_Shadow'] = ((df['High'] - body_top) / high_low).fillna(0.0)

        df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3.0
        df['TP_Vol'] = df['Typical_Price'] * df['Volume']
        df['VWAP20'] = (df['TP_Vol'].rolling(20).sum() / df['Volume'].rolling(20).sum().replace(0, np.nan)).fillna(df['Close'])

        df['High_20'] = df['High'].shift(1).rolling(20).max().fillna(df['High'])
        df['Dist_High20'] = ((df['Close'] - df['High_20']) / df['High_20'] * 100).fillna(0.0)
        df['Prior_5d_Ret'] = ((df['Prev_Close'] - df['Close'].shift(6)) / df['Close'].shift(6) * 100).fillna(0.0)

        cond_sq_breakout = (df['Close'] >= df['High_20'] * 0.992) & (df['Vol_Ratio'] >= 1.25) & (df['Close_Pos'] >= 0.72) & (df['Day_Return'] > 1.0)
        cond_sq_bb_expand = (df['BB_Width'].shift(1) <= df['BB_Width_Min20'].shift(1) * 1.35) & (df['BB_Sigma'] >= 1.45) & (df['Vol_Ratio'] >= 1.2) & (df['Close'] > df['Open'])
        cond_sq_beartrap = (df['Prior_5d_Ret'] <= -3.0) & (df['Day_Return'] >= 1.8) & (df['Close_Pos'] >= 0.75) & (df['Vol_Ratio'] >= 1.15)
        cond_closing_moc = (df['Close_Pos'] >= 0.82) & (df['Upper_Shadow'] <= 0.12) & (df['Vol_Ratio'] >= 1.15) & (df['Close'] > df['Open'])

        df['Next_Open'] = df['Open'].shift(-1)
        df['Gap_Pct'] = (df['Next_Open'] - df['Close']) / df['Close'] * 100
        df['Morning_Up'] = df['Next_Open'] > df['Close']

        cond_squeeze_break = (df['Close'] > df['MA20']) & (df['MACD_Hist'] > 0) & (df['MACD_Hist_Diff'] > 0) & (df['Vol_Ratio'] >= 1.2)
        cond_pinbar_rev = (df['Lower_Shadow'] >= 0.45) & (df['Close_Pos'] >= 0.6) & (df['RSI'] < 50)
        cond_strong_close = (df['Close'] > df['MA5']) & (df['Close_Pos'] >= 0.75) & (df['Day_Return'] > 0)
        cond_oversold = (df['RSI'] < 38) & (df['BB_Sigma'] <= -1.3)
        cond_uptrend = (df['Close'] > df['MA5']) & (df['MACD'] > df['MACD_Signal'])
        cond_up = df['Day_Return'] > 0
        cond_down = df['Day_Return'] <= 0

        latest = df.iloc[-1]
        history = df.iloc[:-1].dropna(subset=['Next_Open', 'MA20', 'RSI', 'MACD_Hist'])
        if len(history) == 0:
            return None

        sq_raw = 42.0
        dist_h20 = float(latest['Dist_High20'])
        if dist_h20 >= 0: sq_raw += 22.0
        elif dist_h20 >= -2.5: sq_raw += 15.0
        elif dist_h20 >= -5.0: sq_raw += 6.0

        sq_raw += min(float(latest['Vol_Ratio']), 3.0) * 8.0
        sq_raw += (float(latest['Close_Pos']) - 0.5) * 24.0
        if float(latest['BB_Sigma']) >= 1.5: sq_raw += 8.0

        if cond_sq_breakout.iloc[-1]:
            sq_raw += 12.0
            squeeze_type = "🔥 20日高値ブレイク踏み上げ (売り方全員含み損)"
            squeeze_detail = f"空売り勢の防衛ライン（20日高値）を出来高倍率{latest['Vol_Ratio']:.2f}倍で突破！強制ロスカット買い戻しが連鎖しやすい状態です。"
        elif cond_sq_beartrap.iloc[-1]:
            sq_raw += 12.0
            squeeze_type = "🪤 ベアトラップ踏み上げ (突っ込み売り丸焦げ反発)"
            squeeze_detail = f"直近の下落で空売りを誘い込んだ後、高値引け大陽線（{latest['Day_Return']:+.1f}%）で売り方を底値に閉じ込めています。"
        elif cond_sq_bb_expand.iloc[-1]:
            sq_raw += 10.0
            squeeze_type = "💥 バンド収縮エクスパンション踏み上げ"
            squeeze_detail = f"ボリンジャーバンド収縮から+{latest['BB_Sigma']:.1f}σへ急拡大。溜まっていた空売りエネルギーが上方向に爆発しています。"
        elif dist_h20 >= -2.0 and latest['Close_Pos'] >= 0.75:
            sq_raw += 8.0
            squeeze_type = "⚡ 踏み上げトリガーロックオン (高値突破寸前)"
            squeeze_detail = f"空売り勢のロスカット集中ラインまであと{abs(dist_h20):.2f}%に迫り、高値引けで翌朝のブレイクを狙っています。"
        else:
            squeeze_type = "⚖️ 踏み上げ圧力・標準"
            squeeze_detail = f"20日高値（空売り防衛線）との乖離は{dist_h20:+.2f}%です。"

        squeeze_score = int(min(max(round(sq_raw), 15), 99))

        close_pos_pct = int(round(float(latest['Close_Pos']) * 100))
        closing_power_raw = 40.0 + (float(latest['Close_Pos']) * 35.0) + (min(float(latest['Vol_Ratio']), 2.5) * 10.0)
        if latest['Close'] > latest['Open']: closing_power_raw += 8.0
        if latest['Upper_Shadow'] <= 0.15: closing_power_raw += 6.0
        closing_power_score = int(min(max(round(closing_power_raw), 15), 99))

        if cond_closing_moc.iloc[-1]:
            closing_status = f"🌆 大引けMOC引けピン買い集め (高値引け度{close_pos_pct}%)"
        elif close_pos_pct >= 75 and latest['Day_Return'] > 0:
            closing_status = f"📈 大引け堅調・高値圏引け (高値引け度{close_pos_pct}%)"
        elif close_pos_pct <= 25:
            closing_status = f"⚠️ 大引け手仕舞い売り・安値引け (高値引け度{close_pos_pct}%)"
        else:
            closing_status = f"⚖️ 大引け通常引け (高値引け度{close_pos_pct}%)"

        if cond_sq_breakout.iloc[-1]:
            signal = "🔥 20日高値ブレイク・ショートスクイーズ(踏み上げ)"
            sub = history[cond_sq_breakout.reindex(history.index, fill_value=False)]
        elif cond_sq_beartrap.iloc[-1]:
            signal = "🪤 ベアトラップ踏み上げ・空売り丸焦げ反発"
            sub = history[cond_sq_beartrap.reindex(history.index, fill_value=False)]
        elif cond_closing_moc.iloc[-1]:
            signal = "🌆 大引けMOCバスケット買い・引けピン"
            sub = history[cond_closing_moc.reindex(history.index, fill_value=False)]
        elif cond_squeeze_break.iloc[-1]:
            signal = "🔥 MACD加速＋出来高ブレイク"
            sub = history[cond_squeeze_break.reindex(history.index, fill_value=False)]
        elif cond_pinbar_rev.iloc[-1]:
            signal = "🔨 下ヒゲ吸収（大口の買い支え）"
            sub = history[cond_pinbar_rev.reindex(history.index, fill_value=False)]
        elif cond_strong_close.iloc[-1]:
            signal = "💪 高値引け・強気モメンタム"
            sub = history[cond_strong_close.reindex(history.index, fill_value=False)]
        elif cond_oversold.iloc[-1]:
            signal = "⚡ BBマイナス圏・売られすぎ反発"
            sub = history[cond_oversold.reindex(history.index, fill_value=False)]
        elif cond_uptrend.iloc[-1]:
            signal = "📈 5日線＆MACDゴールデンクロス圏"
            sub = history[cond_uptrend.reindex(history.index, fill_value=False)]
        elif cond_up.iloc[-1]:
            signal = "☀️ 陽線・プラス引け推移"
            sub = history[cond_up.reindex(history.index, fill_value=False)]
        else:
            signal = "☁️ 押し目・調整局面"
            sub = history[cond_down.reindex(history.index, fill_value=False)]

        if len(sub) < 5:
            sub = history
            signal += " (全体統計)"

        total = len(sub)
        wins = int(sub['Morning_Up'].sum())
        prob = round((wins / total) * 100, 1)
        avg_gap = round(float(sub['Gap_Pct'].mean()), 2)

        win_gaps = sub[sub['Morning_Up']]['Gap_Pct']
        loss_gaps = sub[~sub['Morning_Up']]['Gap_Pct']
        avg_win = float(win_gaps.mean()) if len(win_gaps) > 0 else 0.5
        max_win_gap = round(float(win_gaps.max()), 2) if len(win_gaps) > 0 else 1.5
        avg_loss = abs(float(loss_gaps.mean())) if len(loss_gaps) > 0 else 0.5
        payoff_ratio = round(avg_win / max(avg_loss, 0.1), 2)
        expected_edge = round((prob / 100 * avg_win) - ((100 - prob) / 100 * avg_loss), 2)

        macro_score = 0
        macro_reasons = []
        sox_diff = macro["sox"]["diff"] if macro else 0.0
        nk_diff = macro["nk_fut"]["diff"] if macro else 0.0
        sp_diff = macro["sp500"]["diff"] if macro else 0.0
        fx_diff = macro["usdjpy"]["diff"] if macro else 0.0

        if macro:
            if genre in ["半導体", "AI", "AI電力・インフラ", "小型株", "IPO", "未公開株"]:
                if sox_diff >= 1.0:
                    macro_score += 5
                    macro_reasons.append(f"米SOX指数が<b>+{sox_diff}%</b>と強く上昇しており追い風です。")
                elif sox_diff <= -1.5:
                    macro_score -= 5
                    macro_reasons.append(f"米SOX指数が<b>{sox_diff}%</b>と下落しており売り先行に警戒が必要です。")

            if ".T" in code:
                if nk_diff >= 0.6:
                    macro_score += 4
                    macro_reasons.append(f"CME先物が<b>+{nk_diff}%</b>と上昇しています。")
                elif nk_diff <= -0.6:
                    macro_score -= 4
                    macro_reasons.append(f"CME先物が<b>{nk_diff}%</b>と軟調です。")

        is_jp = ".T" in code
        if is_jp:
            if genre == "半導体":
                overnight_macro_impact = (nk_diff * 0.55) + (sox_diff * 0.48) + (fx_diff * 0.25)
            elif genre in ["AI", "小型株", "IPO", "宇宙"]:
                overnight_macro_impact = (nk_diff * 0.50) + (sox_diff * 0.30) + (sp_diff * 0.30)
            else:
                overnight_macro_impact = (nk_diff * 0.65) + (sp_diff * 0.25) + (fx_diff * 0.20)
        else:
            overnight_macro_impact = (sp_diff * 0.55) + (sox_diff * 0.45)

        moc_carry_over = max(0.0, (closing_power_score - 55) * 0.025)
        squeeze_carry_over = max(0.0, (squeeze_score - 60) * 0.03) if float(latest['Close_Pos']) >= 0.7 else 0.0
        pts_gap_pct = round(avg_gap * 0.55 + overnight_macro_impact * 0.65 + moc_carry_over + squeeze_carry_over, 2)

        close_val = float(latest['Close'])
        atr_val = float(latest['ATR'])
        vwap_val = float(latest['VWAP20'])
        high20_val = float(latest['High_20'])

        pts_est_val = close_val * (1.0 + (pts_gap_pct / 100.0))
        tokugai_pct_threshold = max(2.2, min(round(float(latest['ATR_Pct']) * 0.95, 2), 4.0))
        tokugai_line_val = close_val * (1.0 + (tokugai_pct_threshold / 100.0))

        tokugai_raw = 18.0
        tokugai_raw += max(0.0, pts_gap_pct) * 14.0
        tokugai_raw += max(0.0, closing_power_score - 50) * 0.55
        tokugai_raw += max(0.0, squeeze_score - 50) * 0.55
        tokugai_raw += max(0.0, float(latest['Vol_Ratio']) - 1.0) * 12.0
        if overnight_macro_impact >= 0.8: tokugai_raw += 12.0
        elif overnight_macro_impact <= -0.8: tokugai_raw -= 15.0
        tokugai_prob = int(min(max(round(tokugai_raw), 5), 98))

        if tokugai_prob >= 72:
            tokugai_status = "🚨 特買い（特別買い気配・気配切り上げ）濃厚"
            premarket_advice = f"翌朝8:50時点で成行買いが殺到し、9:00にすぐ寄らず<b>特買い（基準+{tokugai_pct_threshold}%超）</b>で気配を切り上げる公算が大です。"
        elif tokugai_prob >= 52:
            tokugai_status = "🌅 買い気配先行・ギャップアップスタート優勢"
            premarket_advice = f"夜間連動と大引けMOCの買い残しにより、翌朝は前日終値より上の<b>{pts_gap_pct:+.2f}%付近</b>で買い気配スタートが見込まれます。"
        elif pts_gap_pct < -0.3:
            tokugai_status = "🌧️ 売り気配・押し目スタート警戒"
            premarket_advice = f"夜間地合いの逆風により安く始まる可能性があります。5分足VWAPを奪還するまで待機してください。"
        else:
            tokugai_status = "⚖️ 通常気配スタート（板需給拮抗）"
            premarket_advice = f"翌朝は前日終値付近でのスタート予想です。9:00〜9:15の初動出来高を見極めてからエントリーしてください。"

        reasons = []
        if macro_reasons: reasons.extend(macro_reasons)
        reasons.append(f"需給＆踏み上げ解析: <b>{closing_status}</b> / <b>{squeeze_type}</b>。")
        reasons.append(f"過去同条件では{total}回中<b>{wins}回</b>ギャップアップ（最大<b>{max_win_gap:+.2f}%</b>）。")

        base_score = min(max(prob * 0.58, 10), 46)
        edge_score = min(max((expected_edge + 0.3) * 14, 0), 15)
        tech_score = 0
        if latest['Vol_Ratio'] >= 1.2: tech_score += 4
        if latest['Close_Pos'] >= 0.7: tech_score += 4
        if latest['MACD_Hist_Diff'] > 0: tech_score += 4

        moc_bonus = round((closing_power_score - 50) * 0.18) if boost_moc else 0
        sq_bonus = round((squeeze_score - 50) * 0.18) if boost_squeeze else 0
        tokugai_bonus = round((tokugai_prob - 45) * 0.14) if boost_tokugai else 0
        ai_score = int(min(max(round(base_score + edge_score + tech_score + macro_score + moc_bonus + sq_bonus + tokugai_bonus), 15), 99))

        est_open_val = close_val * (1.0 + (avg_gap / 100.0))
        tp_val = max(est_open_val, pts_est_val, close_val) + (atr_val * 0.8)
        sl_val = min(est_open_val, close_val) - (atr_val * 0.5)

        tp_pct = round((tp_val - close_val) / close_val * 100, 1)
        sl_pct = round((sl_val - close_val) / close_val * 100, 1)

        risk_per_share = max(close_val - sl_val, close_val * 0.005)
        allowed_total_risk_money = total_capital * (risk_tolerance_pct / 100.0)
        calculated_shares = max(1, int(allowed_total_risk_money / risk_per_share))
        position_value = calculated_shares * close_val
        capital_ratio = round((position_value / total_capital) * 100, 1)

        def fmt_p(v):
            if pd.isna(v) or np.isnan(v): return "ー"
            return f"{v:,.0f}円" if is_jp else f"${v:,.2f}"

        return {
            "full_code": code,
            "code": code.replace(".T", ""), "name": name, "genre": genre,
            "price": fmt_p(close_val), "raw_close": close_val,
            "est_open": fmt_p(est_open_val),
            "tp_price": fmt_p(tp_val), "tp_pct": tp_pct,
            "sl_price": fmt_p(sl_val), "sl_pct": sl_pct,
            "vwap_price": fmt_p(vwap_val),
            "close_pos_pct": close_pos_pct, "closing_power_score": closing_power_score, "closing_status": closing_status,
            "squeeze_score": squeeze_score, "squeeze_type": squeeze_type, "squeeze_detail": squeeze_detail,
            "squeeze_trigger_price": fmt_p(high20_val), "raw_high20": high20_val, "dist_to_high20": round(dist_h20, 2),
            "pts_est_price": fmt_p(pts_est_val), "pts_gap_pct": pts_gap_pct,
            "tokugai_prob": tokugai_prob, "tokugai_line": fmt_p(tokugai_line_val),
            "tokugai_pct_threshold": tokugai_pct_threshold, "tokugai_status": tokugai_status,
            "premarket_advice": premarket_advice,
            "diff": round(float(latest['Day_Return']), 2), "signal": signal,
            "prob": prob, "count": f"{wins}/{total}回", "gap": avg_gap, "max_win_gap": max_win_gap,
            "rsi": round(float(latest['RSI']), 1),
            "vol_ratio": round(float(latest['Vol_Ratio']), 2),
            "bb_sigma": round(float(latest['BB_Sigma']), 2),
            "macd_state": "強気↑" if latest['MACD_Hist'] > 0 else "調整↓",
            "atr_pct": round(float(latest['ATR_Pct']), 1),
            "payoff": payoff_ratio, "edge": expected_edge,
            "ai_score": ai_score, "macro_score": macro_score,
            "theme": theme, "reasons": " / ".join(reasons),
            "lot_info": {
                "shares": calculated_shares,
                "position_value": position_value,
                "capital_ratio": capital_ratio,
                "risk_amount": allowed_total_risk_money
            }
        }
    except Exception:
        return None

def render_stock_card(r, is_custom=False, rank=None, key_prefix="card"):
    diff_color = "#dc2626" if r["diff"] > 0 else "#2563eb"
    diff_sign = "+" if r["diff"] > 0 else ""
    gap_sign = "+" if r["gap"] > 0 else ""
    pts_sign = "+" if r["pts_gap_pct"] > 0 else ""
    sigma_sign = "+" if r["bb_sigma"] > 0 else ""
    edge_sign = "+" if r["edge"] > 0 else ""
    h20_sign = "+" if r["dist_to_high20"] > 0 else ""

    card_class = "search-result-card" if is_custom else ("rank-card" if rank is not None else "stock-card")
    rank_html = f'<span class="rank-badge">第{rank}位</span>' if rank is not None else ""
    genre_html = f'<span class="genre-badge">{r["genre"]}</span>' if rank is not None else ""

    m_score = r["macro_score"]
    macro_badge_html = f'<span class="macro-badge">🌐 地合い {m_score:+d}点</span>'
    edge_badge_html = f'<span class="edge-badge">📐 損益比 {r["payoff"]}倍 (期待値{edge_sign}{r["edge"]}%)</span>'
    moc_badge_html = f'<span class="moc-badge">🌆 大引けMOC: {r["closing_power_score"]}点</span>'
    sq_badge_html = f'<span class="squeeze-badge">🔥 踏み上げ: {r["squeeze_score"]}点</span>'
    tokugai_badge_html = f'<span class="tokugai-badge">🚨 特買い確率: {r["tokugai_prob"]}%</span>'

    lot = r["lot_info"]

    html_card = (
        f'<div class="{card_class}">'
        f'<div>{rank_html}<span class="score-badge">🤖 AIスコア: {r["ai_score"]} / 100</span>{tokugai_badge_html}{sq_badge_html}{moc_badge_html}{macro_badge_html}{edge_badge_html}</div>'
        f'<div style="display:flex; justify-content:space-between; align-items:center; margin-top:4px;">'
        f'<div><span style="font-size:16px; font-weight:bold; color:#1e293b;">{r["name"]}</span> '
        f'<span style="font-size:12px; color:#64748b;">({r["code"]})</span>{genre_html}<br>'
        f'<span style="font-size:14px; color:#334155;">終値: <b>{r["price"]}</b> '
        f'(<span style="color:{diff_color}; font-weight:bold;">{diff_sign}{r["diff"]}%</span>)</span></div>'
        f'<div style="text-align:right;"><span style="font-size:11px; color:#64748b;">翌朝上昇確率</span><br>'
        f'<span class="prob-badge">{r["prob"]}%</span>'
        f'<div style="font-size:11px; color:#64748b;">({r["count"]} / 平均{gap_sign}{r["gap"]}%)</div></div>'
        f'</div>'
        f'<div class="signal-tag">{r["signal"]}</div>'
        f'<div class="pts-tokugai-box">'
        f'<b>🌙 {r["tokugai_status"]}</b> ｜ 夜間PTS/先物理論気配: <b>{r["pts_est_price"]}</b> ({pts_sign}{r["pts_gap_pct"]}%)<br>'
        f'🚨 <b>特買い（気配切り上げ）発動目安ライン: {r["tokugai_line"]}</b> (+{r["tokugai_pct_threshold"]}%超) ｜ 過去最大GU: <b>+{r["max_win_gap"]}%</b>'
        f'</div>'
        f'<div class="squeeze-box">'
        f'<b>{r["squeeze_type"]}</b> ｜ 踏み上げトリガー(20日高値): <b>{r["squeeze_trigger_price"]}</b> ({h20_sign}{r["dist_to_high20"]}%)<br>'
        f'<b>{r["closing_status"]}</b><br>'
        f'<span style="font-size:11px; color:#9f1239;">└ {r["squeeze_detail"]}</span>'
        f'</div>'
        f'<div class="metrics-row">'
        f"<span>📊 <b>RSI:</b> {r['rsi']}</span>"
        f"<span>📈 <b>MACD:</b> {r['macd_state']}</span>"
        f"<span>🔊 <b>出来高:</b> {r['vol_ratio']}倍</span>"
        f"<span>📏 <b>BB:</b> {sigma_sign}{r['bb_sigma']}σ</span>"
        f"<span>⚡ <b>ATR:</b> {r['atr_pct']}%</span>"
        f'</div>'
        f'<div class="trade-plan-box">'
        f'<div class="trade-plan-item">'
        f'<div style="font-size:10px; color:#64748b;">🌅 夜間理論寄付き</div>'
        f'<div style="font-size:12px; font-weight:bold; color:#0f172a; margin-top:2px;">{r["pts_est_price"]}</div>'
        f'</div>'
        f'<div class="trade-plan-item" style="border-left:1px solid #e2e8f0; border-right:1px solid #e2e8f0;">'
        f'<div style="font-size:10px; color:#15803d; font-weight:bold;">🎯 利確目標</div>'
        f'<div style="font-size:12px; font-weight:bold; color:#15803d; margin-top:2px;">{r["tp_price"]}</div>'
        f'</div>'
        f'<div class="trade-plan-item">'
        f'<div style="font-size:10px; color:#b91c1c; font-weight:bold;">🛡️ 損切り目安</div>'
        f'<div style="font-size:12px; font-weight:bold; color:#b91c1c; margin-top:2px;">{r["sl_price"]}</div>'
        f'</div>'
        f'</div>'
        f'<div class="sizing-box">'
        f'📦 <b>【7大AI最適ロットサイジング】</b> 推奨購入数: <b>{lot["shares"]:,} 株</b> '
        f'(投資額: <b>{lot["position_value"]:,.0f}円</b> / 資金比率: <b>{lot["capital_ratio"]}%</b>)<br>'
        f'<span style="font-size:11px; color:#15803d;">※損切り到達時の最大損失額を総資金の {risk_tolerance_pct}%（{lot["risk_amount"]:,.0f}円）に自動抑制します。</span>'
        f'</div>'
        f'<div class="factor-box">'
        f'<div style="margin-bottom:4px;"><b>【テーマ】</b> {r["theme"]}</div>'
        f'<div><b>【需給判定】</b> {r["reasons"]}</div>'
        f'</div></div>'
    )
    st.markdown(html_card, unsafe_allow_html=True)

    unique_key = f"{key_prefix}_{r['code']}"
    is_open = st.session_state["active_debates"].get(unique_key, False)
    in_wl = r["code"] in st.session_state["watchlist"]

    btn_col1, btn_col2 = st.columns([2.2, 1.2])
    with btn_col1:
        btn_label = "🔼 会議パネルを閉じる" if is_open else "🧠 7大AIで10秒会議して詳細を見る"
        st.button(
            btn_label,
            key=f"btn_{unique_key}",
            on_click=cb_toggle_debate,
            args=(unique_key,),
            use_container_width=True
        )
    with btn_col2:
        wl_label = "✅ 監視登録済(解除)" if in_wl else "⭐ 監視リスト追加"
        st.button(
            wl_label,
            key=f"wl_{unique_key}",
            on_click=cb_toggle_watchlist,
            args=(r["code"], r),
            use_container_width=True
        )

    # --- 🧠 10秒間のリアルタイム会議演出 ＆ 詳細レポート表示 ---
    if st.session_state["active_debates"].get(unique_key, False):
        m5 = fetch_5m_intraday_algo(r["full_code"], trigger_high20=r["raw_high20"])
        debate = run_7ai_council_algorithm(r, m5)

        # 初回オープン時のみ10秒間の会議中アニメーションを実行（質問時はスキップして即表示）
        if unique_key not in st.session_state["debate_Animated"]:
            with st.status(f"🧠 【会議中】7大AIが「{r['name']}」を徹底議論しています...（約10秒）", expanded=True) as status:
                prog_bar = st.progress(0, text="会議を開始しています...")
                discussion_steps = [
                    (14, "🟠 **Claude** が過去1年の勝率と損切りリスク幅を計算中..."),
                    (28, "🔴 **Grok** が空売り勢の踏み上げラインと翌朝の特買い確率を解析中..."),
                    (42, "🟢 **GPT** が日足トレンドと5分足VWAPのバランスを検証中..."),
                    (57, "🔵 **Gemini** が米国株・SOX指数・夜間先物の波及効果を分析中..."),
                    (71, "🌐 **Perplexity** が大引け30分間の出来高と本物の買いかを監査中..."),
                    (85, "✨ **Genspark** が明日の朝一番安全な『分割買い戦術』を策定中..."),
                    (100, "📓 **NotebookLM** が過去ログと照合し、最終結論をまとめています...")
                ]
                for pct, msg in discussion_steps:
                    st.write(msg)
                    prog_bar.progress(pct, text=f"🧠 会議中... ({pct}%)")
                    time.sleep(1.4)
                status.update(label=f"✅ 7大AIの10秒会議が完了しました！（合議スコア: {debate['final_score']}点）", state="complete", expanded=False)
            st.session_state["debate_Animated"].add(unique_key)

        premarket_html = (
            f'<div class="premarket-board-box">'
            f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">'
            f'<span style="font-weight:bold; color:#fde68a;">⏰ 翌朝8:50〜9:00 寄り前板気配・特買いシミュレーター</span>'
            f'<span style="background:#d97706; color:#fff; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:bold;">特買い確率: {r["tokugai_prob"]}%</span>'
            f'</div>'
            f'<div style="font-size:11px; color:#fef3c7; margin-bottom:4px;">'
            f'・夜間理論気配値: <b>{r["pts_est_price"]} ({r["pts_gap_pct"]:+.2f}%)</b> ｜ '
            f'特買い発動ライン: <b>{r["tokugai_line"]}</b> ｜ '
            f'踏み上げ突破ライン: <b>{r["squeeze_trigger_price"]}</b>'
            f'</div>'
            f'<div style="font-size:11px; color:#fde68a;">└ {r["premarket_advice"]}</div>'
            f'</div>'
        )
        st.markdown(premarket_html, unsafe_allow_html=True)

        if m5:
            moc_html = (
                f'<div class="closing-moc-box">'
                f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">'
                f'<span style="font-weight:bold; color:#e9d5ff;">{m5["moc_status"]}</span>'
                f'<span style="background:#9333ea; color:#fff; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:bold;">大引けMOCスコア: {m5["moc_score"]}点</span>'
                f'</div>'
                f'<div style="font-size:11px; color:#f3e8ff; margin-bottom:4px;">'
                f'・ラスト30分株価ドライブ: <b>{m5["close_drive_pct"]:+.2f}%</b> ｜ '
                f'大引け出来高集中度: <b>日中平均の{m5["close_vol_ratio"]}倍</b> ｜ '
                f'ラスト30分陽線数: <b>{m5["close_green_bars"]}/6本</b>'
                f'</div>'
                f'<div style="font-size:11px; color:#e9d5ff;">└ {m5["moc_comment"]}</div>'
                f'</div>'
            )
            st.markdown(moc_html, unsafe_allow_html=True)

            m5_html = (
                f'<div class="intraday-5m-box">'
                f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">'
                f'<span style="font-weight:bold; color:#38bdf8;">⚡ 5分足リアルタイム解析: {m5["status_5m"]}</span>'
                f'<span style="background:#0284c7; color:#fff; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:bold;">5分足スコア: {m5["score_5m"]}点</span>'
                f'</div>'
                f'<div style="font-size:11px; color:#e2e8f0; margin-bottom:4px;">'
                f'・日中5分足VWAP: <b>{m5["vwap5_price"]}</b> ({m5["vwap5_dev"]:+.2f}%) ｜ '
                f'寄付き15分初動: <b>{m5["open_drive_pct"]:+.2f}%</b> ｜ '
                f'陽線率: <b>{m5["twap_green_ratio"]}%</b>'
                f'</div>'
                f'<div style="font-size:11px; color:#bae6fd;">└ {m5["comment_5m"]}</div>'
                f'</div>'
            )
            st.markdown(m5_html, unsafe_allow_html=True)

            if show_5m_chart:
                render_5m_candlestick_chart(m5)

        council_html = (
            f'<div class="ai-council-box">'
            f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">'
            f'<span style="font-size:14px; font-weight:bold; color:#fbbf24;">🧠 7大AI最高評議会 徹底議論レポート（分かりやすい詳細解説）</span>'
            f'<span style="background:#4f46e5; color:#fff; padding:4px 12px; border-radius:20px; font-size:12px; font-weight:bold;">'
            f'7大AI合議スコア: {debate["final_score"]} / 100点</span>'
            f'</div>'
            f'<div class="ai-agent-card claude-card"><div style="font-weight:bold; color:#fbbf24; margin-bottom:4px;">🟠 Claude（リスク管理・負けにくさ担当）— {debate["claude_score"]}点 【{debate["claude_stance"]}】</div><div style="color:#f1f5f9;">{debate["claude_comment"]}</div></div>'
            f'<div class="ai-agent-card grok-card"><div style="font-weight:bold; color:#f87171; margin-bottom:4px;">🔴 Grok（特買い気配・空売り踏み上げ担当）— {debate["grok_score"]}点 【{debate["grok_stance"]}】</div><div style="color:#f1f5f9;">{debate["grok_comment"]}</div></div>'
            f'<div class="ai-agent-card gpt-card"><div style="font-weight:bold; color:#34d399; margin-bottom:4px;">🟢 GPT（総合バランス・トレンド判定担当）— {debate["gpt_score"]}点 【{debate["gpt_stance"]}】</div><div style="color:#f1f5f9;">{debate["gpt_comment"]}</div></div>'
            f'<div class="ai-agent-card gemini-card"><div style="font-weight:bold; color:#60a5fa; margin-bottom:4px;">🔵 Gemini（夜間先物・米国株・テーマ資金担当）— {debate["gemini_score"]}点 【{debate["gemini_stance"]}】</div><div style="color:#f1f5f9;">{debate["gemini_comment"]}</div></div>'
            f'<div class="ai-agent-card perplexity-card"><div style="font-weight:bold; color:#22d3ee; margin-bottom:4px;">🌐 Perplexity（本物の買いか・見せ板チェック担当）— {debate["perplexity_score"]}点 【{debate["perplexity_stance"]}】</div><div style="color:#f1f5f9;">{debate["perplexity_comment"]}</div></div>'
            f'<div class="ai-agent-card genspark-card"><div style="font-weight:bold; color:#c084fc; margin-bottom:4px;">✨ Genspark（具体的な買い方・分割エントリー担当）— {debate["genspark_score"]}点 【{debate["genspark_stance"]}】</div><div style="color:#f1f5f9;">{debate["genspark_comment"]}</div></div>'
            f'<div class="ai-agent-card notebooklm-card"><div style="font-weight:bold; color:#f472b6; margin-bottom:4px;">📓 NotebookLM（過去1年間の統計データ照合担当）— {debate["notebooklm_score"]}点 【{debate["notebooklm_stance"]}】</div><div style="color:#f1f5f9;">{debate["notebooklm_comment"]}</div></div>'
            f'<div class="consensus-banner">'
            f'<div style="font-size:14px; font-weight:bold; color:#a5b4fc; margin-bottom:6px; border-bottom:1px solid rgba(255,255,255,0.15); padding-bottom:4px;">🏛️ 7大AI最終コンセンサス（会議の総括まとめ・実戦トレード計画）</div>'
            f'{debate["verdict_html"]}'
            f'</div>'
            f'<div class="easy-guide-box">{debate["easy_guide"]}</div>'
            f'</div>'
        )
        st.markdown(council_html, unsafe_allow_html=True)

        if unique_key not in st.session_state["stock_chats"]:
            st.session_state["stock_chats"][unique_key] = []

        # --- 💬 質問コーナー（コールバック化により、押しても絶対にタブや会議画面が閉じない！） ---
        st.markdown("**💬 7大AI評議会にさらに質問する（ボタンを押すとすぐ下に回答が表示されます）**")
        q_col1, q_col2 = st.columns(2)
        with q_col1:
            st.button(
                "🚨 翌朝の特買い確率と8:50気配の見方は？",
                key=f"q1_{unique_key}",
                on_click=cb_ask_preset_question,
                args=(unique_key, "翌朝の特買い確率と8:50気配の見方は？", r, debate, m5),
                use_container_width=True
            )
            st.button(
                "🔥 空売り踏み上げの確率とトリガー価格は？",
                key=f"q2_{unique_key}",
                on_click=cb_ask_preset_question,
                args=(unique_key, "空売り踏み上げの確率とトリガー価格は？", r, debate, m5),
                use_container_width=True
            )
        with q_col2:
            st.button(
                "⚡ 5分足チャートの初動と乗り方は？",
                key=f"q3_{unique_key}",
                on_click=cb_ask_preset_question,
                args=(unique_key, "5分足チャートの初動と乗り方は？", r, debate, m5),
                use_container_width=True
            )
            st.button(
                "💰 具体的な買い方と株数をもう一度教えて",
                key=f"q4_{unique_key}",
                on_click=cb_ask_preset_question,
                args=(unique_key, "具体的な買い方と株数をもう一度教えて", r, debate, m5),
                use_container_width=True
            )

        input_key = f"custom_q_input_{unique_key}"
        f1, f2 = st.columns([3, 1])
        with f1:
            st.text_input(
                "質問",
                key=input_key,
                placeholder="自由に質問（例：特買いで寄り付いた直後はどう動くべき？）",
                label_visibility="collapsed"
            )
        with f2:
            st.button(
                "送信",
                key=f"send_q_{unique_key}",
                on_click=cb_ask_custom_question,
                args=(unique_key, input_key, r, debate, m5),
                use_container_width=True
            )

        # 質問と回答の表示エリア
        chat_history = st.session_state["stock_chats"].get(unique_key, [])
        if chat_history:
            for item in chat_history:
                st.markdown(f'<div class="qa-bubble-user">🙋 あなた: {item["q"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="qa-bubble-ai">{item["a"]}</div>', unsafe_allow_html=True)
            st.button(
                "🗑️ 質問履歴をクリア",
                key=f"clear_{unique_key}",
                on_click=cb_clear_chat,
                args=(unique_key,)
            )
        st.markdown("---")

# --- 📋 監視ウォッチリスト ＆ 翌朝8:50実戦発注チェックシート ---
def render_watchlist_order_sheet(all_results):
    wl = st.session_state["watchlist"]

    st.markdown(f"#### 📋 本日の監視ウォッチリスト ({len(wl)}銘柄) ＆ 翌朝8:50発注チェックシート")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("⚡ 本日の総合TOP3をワンタップ一括登録", use_container_width=True):
            if all_results:
                top3 = sorted(all_results, key=lambda x: (x["ai_score"], x["tokugai_prob"], x["squeeze_score"]), reverse=True)[:3]
                for item in top3:
                    st.session_state["watchlist"][item["code"]] = item
                st.rerun()
    with col_b:
        if st.button("🗑️ ウォッチリストをすべて空にする", use_container_width=True):
            st.session_state["watchlist"] = {}
            st.session_state["order_checks"] = {}
            st.rerun()

    if not wl:
        st.info("💡 現在ウォッチリストは空です。「⚡ 本日の総合TOP3をワンタップ一括登録」を押すか、各銘柄カードの **「⭐ 監視リスト追加」** ボタンを押して登録してください。")
        return

    total_pos = sum(item["lot_info"]["position_value"] for item in wl.values())
    total_risk = sum(item["lot_info"]["risk_amount"] for item in wl.values())
    cap_usage_pct = round(total_pos / total_capital * 100, 1)
    risk_usage_pct = round(total_risk / total_capital * 100, 1)

    summary_html = (
        f'<div class="watchlist-summary-banner">'
        f'<div style="font-size:14px; font-weight:bold; color:#a7f3d0; margin-bottom:6px;">🛡️ ポートフォリオ合算資金・リスク管理シミュレーター（登録: {len(wl)}銘柄）</div>'
        f'<div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:8px; text-align:center; background:rgba(0,0,0,0.2); padding:8px; border-radius:8px;">'
        f'<div><div style="font-size:10px; color:#cbd5e1;">合計投資予定額</div><div style="font-size:14px; font-weight:bold; color:#fff;">{total_pos:,.0f}円</div><div style="font-size:10px; color:#6ee7b7;">(稼働率 {cap_usage_pct}%)</div></div>'
        f'<div><div style="font-size:10px; color:#cbd5e1;">第1弾(寄付き半分)合計</div><div style="font-size:14px; font-weight:bold; color:#fde68a;">{total_pos/2:,.0f}円</div><div style="font-size:10px; color:#fde68a;">(稼働率 {cap_usage_pct/2:.1f}%)</div></div>'
        f'<div><div style="font-size:10px; color:#cbd5e1;">最大合計リスク(損切時)</div><div style="font-size:14px; font-weight:bold; color:#fca5a5;">-{total_risk:,.0f}円</div><div style="font-size:10px; color:#fca5a5;">(総資金の -{risk_usage_pct}%)</div></div>'
        f'</div></div>'
    )
    st.markdown(summary_html, unsafe_allow_html=True)

    table_rows = []
    for code, item in wl.items():
        lot_s = item["lot_info"]["shares"]
        half_s = max(1, lot_s // 2)
        table_rows.append({
            "コード": code, "銘柄名": item["name"], "セクター": item["genre"],
            "AIスコア": item["ai_score"], "特買い確率": f"{item['tokugai_prob']}%",
            "踏み上げ度": f"{item['squeeze_score']}点", "前日終値": item["price"],
            "夜間理論気配": f"{item['pts_est_price']} ({item['pts_gap_pct']:+.2f}%)",
            "特買い発動線": item["tokugai_line"], "踏み上げ線(20日高)": item["squeeze_trigger_price"],
            "推奨総ロット": f"{lot_s:,}株", "①寄付き半分ロット": f"{half_s:,}株",
            "🎯利確目標": item["tp_price"], "🛡️逆指値(損切)": item["sl_price"],
        })
    df_order = pd.DataFrame(table_rows)
    st.dataframe(df_order, use_container_width=True, hide_index=True)

    csv_bytes = df_order.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 本日の注文計画シートをCSVダウンロード", data=csv_bytes, file_name="morning_quant_order_sheet.csv", mime="text/csv", use_container_width=True)

    st.markdown("##### ⏰ 翌朝8:50〜9:15 実戦発注チェックカード")
    for code, r in list(wl.items()):
        lot_s = r["lot_info"]["shares"]
        half_s = max(1, lot_s // 2)
        rem_s = max(0, lot_s - half_s)

        card_html = (
            f'<div class="order-sheet-card">'
            f'<div><span style="font-size:16px; font-weight:bold; color:#0f172a;">⭐ {r["name"]} ({code})</span> '
            f'<span class="score-badge">AI {r["ai_score"]}点</span>'
            f'<span class="tokugai-badge">🚨 特買い {r["tokugai_prob"]}%</span>'
            f'<span class="squeeze-badge">🔥 踏み上げ {r["squeeze_score"]}点</span></div>'
            f'<div style="margin-top:6px; font-size:12px; color:#334155; background:#f8fafc; padding:8px; border-radius:6px; border:1px solid #e2e8f0;">'
            f'・<b>買い指値ゾーン:</b> <b>{r["price"]} 〜 {r["pts_est_price"]}</b> ｜ <b>特買いライン:</b> <b style="color:#d97706;">{r["tokugai_line"]}</b> ｜ <b>踏み上げ突破線:</b> <b style="color:#e11d48;">{r["squeeze_trigger_price"]}</b><br>'
            f'・<b>推奨ロット配分:</b> 総数 <b>{lot_s:,}株</b> （第1弾 寄付き: <b>{half_s:,}株</b> ＋ 第2弾 VWAPサポ/高値突破: <b>{rem_s:,}株</b>）<br>'
            f'・<b>エグジット計画:</b> 🎯 第一利確 <b>{r["tp_price"]} (+{r["tp_pct"]}%)</b> ／ 🛡️ 逆指値(損切) <b style="color:#b91c1c;">{r["sl_price"]} ({r["sl_pct"]}%)</b>'
            f'</div></div>'
        )
        st.markdown(card_html, unsafe_allow_html=True)

        chk_c1, chk_c2, chk_c3, chk_c4, chk_del = st.columns([1.2, 1.2, 1.2, 1.2, 0.7])
        with chk_c1: st.checkbox("① 8:50気配OK", key=f"chk1_{code}")
        with chk_c2: st.checkbox(f"② 初動{half_s:,}株発注", key=f"chk2_{code}")
        with chk_c3: st.checkbox(f"③ 逆指値({r['sl_price']})済", key=f"chk3_{code}")
        with chk_c4: st.checkbox("④ 5分足VWAP追撃済", key=f"chk4_{code}")
        with chk_del:
            st.button(
                "解除",
                key=f"rm_wl_{code}",
                on_click=cb_toggle_watchlist,
                args=(code, r),
                use_container_width=True
            )

if st.button("🔄 最新データに更新"):
    st.cache_data.clear()

macro_info = fetch_macro_market()

def fmt_macro(item, span_class="span-2", mode="index"):
    d = item["diff"]
    sign = "+" if d > 0 else ""
    color = "#4ade80" if d > 0 else ("#f87171" if d < 0 else "#cbd5e1")
    if item["price"] == 0 or np.isnan(item["price"]):
        val_str, diff_str = "取得中/休場", "-"
    else:
        val_str = f"{item['price']:,.2f}円" if mode == "fx" else (f"{item['price']:,.2f} pt" if mode == "vix" else f"{item['price']:,.0f}")
        diff_str = f"{sign}{d}%"
    return f'<div class="market-item {span_class}"><div style="font-size:10px; color:#cbd5e1;">{item["label"]}</div><div style="font-size:13px; font-weight:bold; color:#f8fafc;">{val_str}</div><div style="font-size:11px; color:{color};">{diff_str}</div></div>'

sp_item  = macro_info.get("sp500",  {"price": 0, "diff": 0, "label": "🇺🇸 米S&P500"})
sox_item = macro_info.get("sox",    {"price": 0, "diff": 0, "label": "💽 米SOX半導体"})
fx_item  = macro_info.get("usdjpy", {"price": 0, "diff": 0, "label": "💴 ドル円為替"})
nk_item  = macro_info.get("nk_fut", {"price": 0, "diff": 0, "label": "🇯🇵 CME日経先物"})
vix_item = macro_info.get("vix",    {"price": 0, "diff": 0, "label": "⚡ VIX恐怖指数"})

banner_html = (
    '<div class="market-banner"><div class="market-title">🌐 米国市場・為替・CME先物・VIXフィルター</div><div class="market-grid">'
    f'{fmt_macro(sp_item, "span-2", "index")}{fmt_macro(sox_item, "span-2", "index")}{fmt_macro(fx_item, "span-2", "fx")}'
    f'{fmt_macro(nk_item, "span-3", "nk")}{fmt_macro(vix_item, "span-3", "vix")}'
    '</div></div>'
)
st.markdown(banner_html, unsafe_allow_html=True)

with st.container():
    c1, c2 = st.columns([3, 1])
    with c1: custom_input = st.text_input("🔍 任意の銘柄コードを診断", placeholder="例: 6920, 5803, NVDA, DXYZ")
    with c2:
        st.write("")
        search_clicked = st.button("診断する", use_container_width=True)

if custom_input or search_clicked:
    norm_code = normalize_ticker(custom_input)
    if norm_code:
        with st.spinner(f"「{norm_code}」の特買い気配＆踏み上げ・大引けMOC解析中..."):
            custom_res = fetch_and_analyze(norm_code, macro=macro_info, boost_moc=moc_boost_mode, boost_squeeze=squeeze_boost_mode, boost_tokugai=tokugai_boost_mode)
        if custom_res:
            st.markdown("##### 🎯 個別銘柄のリアルタイム診断結果")
            render_stock_card(custom_res, is_custom=True, key_prefix="custom")
        else:
            st.error(f"証券コード「{custom_input}」のデータが見つかりませんでした。")

genre_results = {g: [] for g in STOCK_POOL.keys()}
all_results = []
seen_in_all = set()

with st.spinner("全候補銘柄の特買い確率・踏み上げ・大引けMOC波形をスキャン中..."):
    for genre, stocks in STOCK_POOL.items():
        for s in stocks:
            res = fetch_and_analyze(s["code"], s["name"], s["theme"], genre, macro_info, boost_moc=moc_boost_mode, boost_squeeze=squeeze_boost_mode, boost_tokugai=tokugai_boost_mode)
            if res:
                genre_results[genre].append(res)
                if s["code"] not in seen_in_all:
                    all_results.append(res)
                    seen_in_all.add(s["code"])
                clean_c = s["code"].replace(".T", "")
                if clean_c in st.session_state["watchlist"]:
                    st.session_state["watchlist"][clean_c] = res

# --- 🧭 タブの代わりにセッション固定型のカテゴリー選択バーを採用（ボタンを押しても絶対にタブが飛ばない！） ---
category_options = [
    "🏆 総合TOP5",
    "📋 監視＆注文シート",
    "🚨 特買い・夜間連動特選",
    "🔥 踏み上げ特選",
    "🌆 大引けMOC特選"
] + list(STOCK_POOL.keys())

st.markdown("##### 📂 解析カテゴリー選択")
selected_cat = st.radio(
    "カテゴリーを選択",
    options=category_options,
    key="selected_category",
    horizontal=True,
    label_visibility="collapsed"
)
st.markdown("---")

if selected_cat == "🏆 総合TOP5":
    st.caption("全プールから、本日のAIスコア・特買い確率・踏み上げ・大引けMOCが最も高い上位5銘柄を表示しています。")
    if all_results:
        top5_list = sorted(all_results, key=lambda x: (x["ai_score"], x["tokugai_prob"], x["squeeze_score"], x["closing_power_score"]), reverse=True)[:5]
        for idx, r in enumerate(top5_list, start=1):
            render_stock_card(r, rank=idx, key_prefix="top5")

elif selected_cat == "📋 監視＆注文シート":
    render_watchlist_order_sheet(all_results)

elif selected_cat == "🚨 特買い・夜間連動特選":
    st.info("🚨 **特買い（特別買い気配）・夜間PTS/ADR連動特選**: 夜間先物・米SOXの追い風と、前日大引けの買い残し・空売り踏み上げが重なり、翌朝9:00に『特買い（気配切り上げ）』になりやすい上位10銘柄です。")
    if all_results:
        tokugai_top_list = sorted(all_results, key=lambda x: (x["tokugai_prob"], x["pts_gap_pct"], x["ai_score"]), reverse=True)[:10]
        for idx, r in enumerate(tokugai_top_list, start=1):
            render_stock_card(r, rank=idx, key_prefix="tokugai_top")

elif selected_cat == "🔥 踏み上げ特選":
    st.info("🔥 **空売り踏み上げ（ショートスクイーズ）特選**: 20日高値ブレイク・ベアトラップ反発・バンド膨張など、空売り勢が損失に耐えきれず翌朝に強制買い戻し（ロスカット）を迫られやすい上位10銘柄です。")
    if all_results:
        sq_top_list = sorted(all_results, key=lambda x: (x["squeeze_score"], x["closing_power_score"], x["ai_score"]), reverse=True)[:10]
        for idx, r in enumerate(sq_top_list, start=1):
            render_stock_card(r, rank=idx, key_prefix="sq_top")

elif selected_cat == "🌆 大引けMOC特選":
    st.info("🌆 **大引けMOC（引けピン買い集め）特選**: 大引けにかけてバスケット買い・高値引け（引けピン）の勢いが最も強い上位10銘柄です。翌朝のギャップアップ期待が最も高いグループです。")
    if all_results:
        moc_top_list = sorted(all_results, key=lambda x: (x["closing_power_score"], x["squeeze_score"], x["ai_score"]), reverse=True)[:10]
        for idx, r in enumerate(moc_top_list, start=1):
            render_stock_card(r, rank=idx, key_prefix="moc_top")

elif selected_cat in STOCK_POOL:
    genre = selected_cat
    if genre == "小型株": st.info("💡 **小型株セクション**: 値動きが軽く急騰しやすい純粋な小型グロース株のみを厳選。")
    elif genre == "IPO": st.info("💡 **IPOセクション**: 直近新規上場銘柄の特買い確率・踏み上げと最適ロットを算出。")
    elif genre == "未公開株": st.info("💡 **未公開株・VC関連セクション**: プライベートマーケット連動銘柄の資金管理。")
    results = genre_results.get(genre, [])
    if results:
        results.sort(key=lambda x: (x["ai_score"], x["tokugai_prob"], x["squeeze_score"], x["closing_power_score"]), reverse=True)
        for idx, r in enumerate(results[:20], start=1):
            render_stock_card(r, rank=idx, key_prefix=f"genre_{genre}")
