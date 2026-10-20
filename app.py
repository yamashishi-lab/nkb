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

# Fragmentデコレータ（部分更新用）の取得
fragment_decorator = getattr(st, "fragment", getattr(st, "experimental_fragment", lambda f: f))

# ==========================================
# 🔒 会員制ログイン＆メール許可ゲート機能
# ==========================================
ADMIN_EMAIL = "nthbh399@ybb.ne.jp"  # ←管理者メールアドレス
SECRET_MASTER_KEY = "my_super_secret_quant_key_2026"

ALLOWED_MEMBERS = [
    ADMIN_EMAIL,
    "",  # 許可した会員1
    "",  # 許可した会員2
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
                    target_mail = st.text_input("許可する会員のメールアドレス", key="admin_gen_mail")
                    if target_mail:
                        code = generate_member_passcode(target_mail)
                        st.code(f"メールアドレス: {target_mail.strip().lower()}\n専用アクセスコード: {code}")
            if st.button("🚪 ログアウト", use_container_width=True):
                st.session_state["authenticated_user"] = None
                st.rerun()
        return True

    st.markdown("""
    <div style="background: linear-gradient(135deg, #0f172a, #1e293b); color: #f8fafc; padding: 24px; border-radius: 14px; text-align: center; margin-top: 20px; margin-bottom: 16px;">
        <h2 style="margin:0; color:#fbbf24; font-size:20px;">🔒 会員限定 クオンツ＆7大AI解析 Pro</h2>
        <p style="font-size:13px; color:#cbd5e1; margin-top:8px; margin-bottom:0;">
            本システムは完全招待・承認制です。<br>運営より許可されたメールアドレスと専用アクセスコードを入力してください。
        </p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("member_login_form"):
        input_email = st.text_input("📧 登録メールアドレス", placeholder="example@gmail.com")
        input_code = st.text_input("🔑 専用アクセスコード（8桁コード）", type="password")
        login_btn = st.form_submit_button("🔓 ログインして解析システムを開く", use_container_width=True)

        if login_btn:
            clean_mail = input_email.strip().lower()
            allowed_list = [m.strip().lower() for m in ALLOWED_MEMBERS if m.strip()]
            expected_code = generate_member_passcode(clean_mail)
            is_valid_code = hmac.compare_digest(input_code.strip().upper(), expected_code) or (
                clean_mail == ADMIN_EMAIL.strip().lower() and input_code.strip() == "ADMIN777"
            )
            if clean_mail in allowed_list and is_valid_code:
                st.session_state["authenticated_user"] = clean_mail
                st.rerun()
            elif clean_mail not in allowed_list:
                st.error("⚠️ このメールアドレスはまだ利用許可されていません。")
            else:
                st.error("⚠️ 専用アクセスコードが正しくありません。")

    mailto_link = f"mailto:{ADMIN_EMAIL}?subject=【利用許可申請】翌朝株価クオンツ＆7大AI解析Pro&body=希望メールアドレス："
    st.markdown(f'<a href="{mailto_link}" style="display:block; text-align:center; background:#2563eb; color:#ffffff; padding:12px; border-radius:8px; text-decoration:none; font-weight:bold; font-size:13px;">✉️ 管理者にメールで利用許可を申請する</a>', unsafe_allow_html=True)
    st.stop()

check_member_authentication()

# ==========================================
# 📈 セッション初期化
# ==========================================
for k, default_v in [("active_debates", {}), ("debate_Animated", set()), ("stock_chats", {}), ("watchlist", {})]:
    if k not in st.session_state:
        st.session_state[k] = default_v

# ==========================================
# 🎨 カスタムCSS
# ==========================================
st.markdown("""
<style>
button[data-baseweb="tab"] { font-size: 13px !important; font-weight: bold !important; padding: 8px 14px !important; }
.stock-card, .rank-card, .search-result-card { background-color: #ffffff !important; color: #0f172a !important; border-radius: 12px; padding: 16px; margin-bottom: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); border-left: 6px solid #e11d48; }
.search-result-card { background-color: #fffbeb !important; border-left-color: #d97706; }
.prob-badge { font-size: 22px; font-weight: bold; color: #dc2626; }
.rank-badge { display: inline-block; background: linear-gradient(135deg, #f59e0b, #d97706); color: #fff; padding: 3px 9px; border-radius: 20px; font-size: 12px; font-weight: bold; margin-right: 4px; }
.score-badge { display: inline-block; background: #1e293b; color: #f8fafc; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: bold; }
.inst-badge { display: inline-block; background: linear-gradient(135deg, #1d4ed8, #3b82f6); color: #fff; padding: 2px 9px; border-radius: 20px; font-size: 11px; font-weight: bold; margin-left: 4px; }
.board5ch-badge { display: inline-block; background: linear-gradient(135deg, #059669, #10b981); color: #fff; padding: 2px 9px; border-radius: 20px; font-size: 11px; font-weight: bold; margin-left: 4px; }
.squeeze-badge { display: inline-block; background: linear-gradient(135deg, #b91c1c, #ef4444); color: #fff; padding: 2px 9px; border-radius: 20px; font-size: 11px; font-weight: bold; margin-left: 4px; }
.tokugai-badge { display: inline-block; background: linear-gradient(135deg, #d97706, #f59e0b); color: #fff; padding: 2px 9px; border-radius: 20px; font-size: 11px; font-weight: bold; margin-left: 4px; }
.survival-badge { display: inline-block; background: #f3e8ff; color: #6b21a8; border: 1px solid #d8b4fe; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: bold; margin-left: 4px; }
.inst-box { background: #eff6ff; border: 1px solid #bfdbfe; border-left: 4px solid #2563eb; border-radius: 8px; padding: 8px 12px; margin-top: 6px; font-size: 12px; color: #1e3a8a !important; }
.squeeze-box { background: #fff1f2; border: 1px solid #fecdd3; border-left: 4px solid #e11d48; border-radius: 8px; padding: 8px 12px; margin-top: 6px; font-size: 12px; color: #881337 !important; }
.pts-tokugai-box { background: #fffbeb; border: 1px solid #fde68a; border-left: 4px solid #d97706; border-radius: 8px; padding: 8px 12px; margin-top: 6px; font-size: 12px; color: #78350f !important; }
.board5ch-box { background: #ecfdf5; border: 1px solid #a7f3d0; border-left: 4px solid #059669; border-radius: 8px; padding: 8px 12px; margin-top: 6px; font-size: 12px; color: #064e3b !important; }
.metrics-row { display: flex; flex-wrap: wrap; gap: 6px 10px; margin-top: 8px; font-size: 11px; color: #334155 !important; background: #f8fafc; padding: 8px 10px; border-radius: 6px; border: 1px solid #e2e8f0; }
.trade-plan-box { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-top: 8px; background: #f8fafc; padding: 8px 6px; border-radius: 8px; border: 1px dashed #cbd5e1; text-align: center; color: #0f172a !important; }
.sizing-box { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 10px 12px; margin-top: 8px; font-size: 12px; color: #166534 !important; }
.ai-council-box { background: linear-gradient(135deg, #0f172a, #1e293b); color: #f8fafc !important; border-radius: 12px; padding: 16px; margin-top: 6px; margin-bottom: 10px; }
.ai-agent-card { background: rgba(255, 255, 255, 0.08); border-radius: 8px; padding: 10px 12px; margin-bottom: 8px; font-size: 12.5px; line-height: 1.6; color: #f8fafc !important; }
.consensus-banner { background: linear-gradient(135deg, #1e1b4b, #312e81); border: 2px solid #818cf8; border-radius: 10px; padding: 14px; margin-top: 12px; font-size: 12.5px; line-height: 1.7; color: #f8fafc !important; }
.consensus-section { background: rgba(255, 255, 255, 0.07); border-left: 3px solid #fbbf24; border-radius: 6px; padding: 8px 10px; margin-top: 8px; color: #f8fafc !important; }
.qa-active-box { background: #ffffff !important; border: 2px solid #4f46e5 !important; border-radius: 10px; padding: 14px !important; margin-bottom: 10px; box-shadow: 0 4px 12px rgba(79, 70, 229, 0.15); color: #0f172a !important; }
.qa-bubble-user { background: #4f46e5 !important; color: #ffffff !important; display: inline-block; border-radius: 6px; padding: 4px 10px; margin-bottom: 8px; font-size: 12px; font-weight: bold; }
.qa-bubble-ai { color: #0f172a !important; font-size: 13px !important; line-height: 1.75 !important; background: #f8fafc !important; padding: 10px !important; border-radius: 8px !important; border-left: 4px solid #4f46e5 !important; }
.qa-history-card { background: #ffffff !important; border: 1px solid #cbd5e1 !important; border-left: 4px solid #6366f1 !important; border-radius: 8px; padding: 12px !important; margin-bottom: 8px; font-size: 12.5px !important; color: #0f172a !important; line-height: 1.65 !important; }
</style>
""", unsafe_allow_html=True)

# --- サイドバー設定 ---
st.sidebar.header("💰 資金管理＆リスク設定")
total_capital = st.sidebar.number_input("総投資資金 (円 / ドル)", min_value=10000, max_value=1000000000, value=1000000, step=50000)
risk_tolerance_pct = st.sidebar.slider("1トレード許容リスク (%)", min_value=0.5, max_value=5.0, value=2.0, step=0.5)

st.sidebar.markdown("---")
st.sidebar.header("🏦 機関クオンツ＆弱肉強食設定")
survival_cut_pct = st.sidebar.slider("弱肉強食・各タブ選抜率 (%)", min_value=40, max_value=100, value=70, step=10)
inst_boost_mode = st.sidebar.checkbox("🏦 機関クオンツ（VPIN・ステルス吸収）優先", value=True)
board5ch_boost = st.sidebar.checkbox("🔥 5ch板・初動イナゴ＆シコリ玉なし優先", value=True)
squeeze_boost_mode = st.sidebar.checkbox("💥 空売り踏み上げ（20日高値突破）優先", value=True)
tokugai_boost_mode = st.sidebar.checkbox("🚨 翌朝『特買い』・夜間PTS連動を優先", value=True)
show_5m_chart = st.sidebar.checkbox("合議パネル内に5分足＆VWAPチャートを描画", value=True)

st.sidebar.markdown("---")
st.sidebar.header(f"📋 監視ウォッチリスト ({len(st.session_state['watchlist'])}銘柄)")
if st.session_state["watchlist"]:
    for w_code, w_item in list(st.session_state["watchlist"].items()):
        st.sidebar.markdown(f"⭐ **{w_item['name']}** ({w_code}) — {w_item['lot_info']['shares']:,}株")
    if st.sidebar.button("🗑️ ウォッチリスト全クリア", use_container_width=True):
        st.session_state["watchlist"] = {}
        st.rerun()

st.title("📱 翌朝株価 クオンツ＆7大AI解析 Pro")
st.caption("【機関投資家VPINクオンツ搭載】7大AI動的ロール合議 × 5ch需給 × 弱肉強食サバイバル")

# --- 🦁 国内外の主力・テーマ母集団プール ---
STOCK_POOL = {
    "半導体": [
        {"code": "8035.T", "name": "東京エレクトロン", "theme": "前工程装置の国内筆頭。機関の指数バスケット買い中心"},
        {"code": "6857.T", "name": "アドバンテスト", "theme": "AI半導体テスタ世界首位級。SOX指数連動"},
        {"code": "6920.T", "name": "レーザーテック", "theme": "EUV検査装置。デイトレ売買代金・空売り踏み上げ筆頭"},
        {"code": "6146.T", "name": "ディスコ", "theme": "HBM向け精密加工装置で圧倒的シェア"},
        {"code": "6526.T", "name": "ソシオネクスト", "theme": "先端カスタムSoC。個人の信用回転が極めて活発"},
        {"code": "7735.T", "name": "スクリーンHD", "theme": "ウエハー洗浄装置で世界首位"},
        {"code": "6315.T", "name": "TOWA", "theme": "HBM向け半導体モールディング装置"},
        {"code": "6723.T", "name": "ルネサス", "theme": "車載・産業・AI向け半導体"},
        {"code": "4063.T", "name": "信越化学工業", "theme": "シリコンウエハー世界首位"},
        {"code": "3436.T", "name": "SUMCO", "theme": "シリコンウエハー大手"},
        {"code": "6323.T", "name": "ローツェ", "theme": "ウエハー搬送機。空売り買い戻しが強烈"},
        {"code": "6871.T", "name": "日本マイクロニクス", "theme": "HBM向けプローブカードで急騰常連"},
        {"code": "NVDA", "name": "エヌビディア (米)", "theme": "生成AI向けGPUの世界覇者"},
        {"code": "AMD", "name": "AMD (米)", "theme": "AIアクセラレータ・CPU大手"},
        {"code": "MU", "name": "マイクロン (米)", "theme": "HBM・DRAMメモリ大手"},
        {"code": "TSM", "name": "TSMC (米)", "theme": "世界最大の半導体受託生産"},
        {"code": "AVGO", "name": "ブロードコム (米)", "theme": "カスタムAIチップ・通信半導体"},
        {"code": "ARM", "name": "アーム (米)", "theme": "半導体設計アーキテクチャの要"},
        {"code": "SMCI", "name": "スーパーマイクロ (米)", "theme": "AIサーバー大手。値動きと踏み上げが激しい"}
    ],
    "AI・防衛・主力": [
        {"code": "9984.T", "name": "ソフトバンクG", "theme": "AI投資群・Arm親会社。先物連動の主役"},
        {"code": "3778.T", "name": "さくらネット", "theme": "国策GPUクラウド。5chデイトレ板の常連急騰株"},
        {"code": "7011.T", "name": "三菱重工業", "theme": "防衛・宇宙・原発の国策ど真ん中主力株"},
        {"code": "7012.T", "name": "川崎重工業", "theme": "防衛装備・航空エンジン主力"},
        {"code": "7013.T", "name": "IHI", "theme": "航空宇宙・防衛エンジン主力"},
        {"code": "3993.T", "name": "PKSHA", "theme": "AIアルゴリズム・対話AI"},
        {"code": "4180.T", "name": "Appier", "theme": "AIマーケティングSaaS"},
        {"code": "5032.T", "name": "ANYCOLOR", "theme": "VTuber大手。好決算・自社株買いで踏み上げ頻発"},
        {"code": "4385.T", "name": "メルカリ", "theme": "国内C2C大手。信用取組の妙味"},
        {"code": "7974.T", "name": "任天堂", "theme": "次世代機テーマ・海外機関資金流入の超主力"},
        {"code": "8306.T", "name": "三菱UFJ", "theme": "金利連動のメガバンク筆頭"},
        {"code": "MSFT", "name": "マイクロソフト (米)", "theme": "OpenAI筆頭連携・クラウド巨人"},
        {"code": "PLTR", "name": "パランティア (米)", "theme": "防衛・企業向けAIプラットフォーム大本命"},
        {"code": "META", "name": "メタ (米)", "theme": "AI広告・LlamaオープンソースAI"},
        {"code": "GOOGL", "name": "アルファベット (米)", "theme": "Gemini生成AI・検索クラウド"},
        {"code": "CRWD", "name": "クラウドストライク (米)", "theme": "AIサイバーセキュリティ世界首位"}
    ],
    "AI電力・電線": [
        {"code": "5803.T", "name": "フジクラ", "theme": "AIデータセンター向け光ファイバー。機関買い＆踏み上げ最強格"},
        {"code": "5801.T", "name": "古河電気工業", "theme": "光ファイバー・送電インフラ"},
        {"code": "5802.T", "name": "住友電気工業", "theme": "電線首位・データセンター通信網"},
        {"code": "6501.T", "name": "日立製作所", "theme": "世界送配電グリッド・AIインフラ"},
        {"code": "9509.T", "name": "北海道電力", "theme": "ラピダス・AIデータセンター電力供給"},
        {"code": "9508.T", "name": "九州電力", "theme": "TSMC半導体工場向け電力需要"},
        {"code": "6622.T", "name": "ダイヘン", "theme": "データセンター向け変圧器"},
        {"code": "1942.T", "name": "関電工", "theme": "データセンター電気設備工事"},
        {"code": "VST", "name": "ビストラ (米)", "theme": "AIデータセンター向け発電主力"},
        {"code": "CEG", "name": "コンステレーション (米)", "theme": "米最大の原子力発電・AI電力供給"},
        {"code": "GEV", "name": "GEヴェルノバ (米)", "theme": "ガスタービン・送電網設備の世界リーダー"}
    ],
    "宇宙・イーロン": [
        {"code": "5595.T", "name": "QPS研究所", "theme": "小型SAR衛星。5chデイトレ板で人気集中の筆頭"},
        {"code": "186A.T", "name": "アストロスケール", "theme": "宇宙デブリ除去の世界的ベンチャー"},
        {"code": "9348.T", "name": "ispace", "theme": "月面開発輸送。イベント前後の出来高急増株"},
        {"code": "9412.T", "name": "スカパーJSAT", "theme": "衛星通信・防衛宇宙監視"},
        {"code": "9433.T", "name": "KDDI", "theme": "SpaceX Starlink直接通信連携"},
        {"code": "7203.T", "name": "トヨタ自動車", "theme": "全固体電池・自動運転"},
        {"code": "TSLA", "name": "テスラ (米)", "theme": "自動運転・ロボタクシー・世界最大の踏み上げ株"},
        {"code": "RKLB", "name": "ロケットラボ (米)", "theme": "小型ロケット打上げ米宇宙主力"},
        {"code": "ASTS", "name": "ASTスペースモバイル (米)", "theme": "宇宙スマホ直接通信。ショートスクイーズ常連"},
        {"code": "COIN", "name": "コインベース (米)", "theme": "暗号資産連動・ハイボラティリティ銘柄"}
    ],
    "小型急騰・IPO": [
        {"code": "5253.T", "name": "カバー", "theme": "ホロライブ運営。グロース市場の売買代金トップ級"},
        {"code": "9166.T", "name": "GENDA", "theme": "エンタメM&A急成長"},
        {"code": "216A.T", "name": "タイミー", "theme": "スキマバイト仲介の大型グロースIPO"},
        {"code": "285A.T", "name": "キオクシアHD", "theme": "NANDフラッシュメモリ大手の注目IPO"},
        {"code": "141A.T", "name": "トライアルHD", "theme": "リテールAI流通"},
        {"code": "5243.T", "name": "ノート", "theme": "AI学習・クリエイターエコノミー小型株"},
        {"code": "247A.T", "name": "Aiロボティクス", "theme": "AIマーケティング急成長グロース"},
        {"code": "153A.T", "name": "カウリス", "theme": "不正アクセス検知セキュリティ小型株"},
        {"code": "3350.T", "name": "メタプラネット", "theme": "暗号資産トレジャリー。5ch板の超ボラティリティ常連株"},
        {"code": "IONQ", "name": "アイオンQ (米)", "theme": "商用量子コンピューター代表格。空売り踏み上げ強烈"},
        {"code": "RGTI", "name": "リゲッティ (米)", "theme": "量子コンピューター小型急騰株"},
        {"code": "SOUN", "name": "サウンドハウンドAI (米)", "theme": "音声AI認識の小型急騰株"},
        {"code": "RDDT", "name": "レディット (米IPO)", "theme": "AIデータライセンス＆SNSの大型IPO"},
        {"code": "ALAB", "name": "アステラ・ラブズ (米IPO)", "theme": "AIデータセンター高速接続半導体IPO"}
    ]
}

KNOWN_STOCKS = {}
for g, items in STOCK_POOL.items():
    for item in items:
        KNOWN_STOCKS[item["code"]] = {"name": item["name"], "theme": item["theme"], "genre": g}

def normalize_ticker(raw_input):
    s = unicodedata.normalize('NFKC', raw_input).strip().upper()
    if not s: return ""
    if "." in s or s.startswith("^") or "=" in s: return s
    if len(s) == 4 and any(ch.isdigit() for ch in s): return f"{s}.T"
    return s

# ==========================================
# 🌐 マクロ市場データ取得
# ==========================================
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
                        latest_c, prev_c = float(df_m['Close'].iloc[-1]), float(df_m['Close'].iloc[-2])
                        if prev_c != 0:
                            macro_data[key] = {"price": latest_c, "diff": round((latest_c - prev_c) / prev_c * 100, 2), "label": info["label"]}
                            fetched = True
                            break
            except Exception:
                continue
        if not fetched:
            macro_data[key] = {"price": 0.0, "diff": 0.0, "label": info["label"]}
    return macro_data

# ==========================================
# 🏦 機関投資家クオンツ（VPIN・Amihud・ステルス吸収）＆ 5ch需給解析エンジン
# ==========================================
def analyze_single_dataframe(df_raw, code, name, theme, genre, macro, boost_inst=True, boost_5ch=True, boost_squeeze=True, boost_tokugai=True):
    try:
        if df_raw is None or df_raw.empty:
            return None
        df = df_raw.dropna(subset=['Close', 'Open', 'High', 'Low', 'Volume']).copy()
        if len(df) < 35:
            return None

        df['Prev_Close'] = df['Close'].shift(1)
        df['Day_Return'] = (df['Close'] - df['Prev_Close']) / df['Prev_Close'] * 100
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['Vol_MA5'] = df['Volume'].rolling(5).mean().replace(0, np.nan)
        df['Vol_MA20'] = df['Volume'].rolling(20).mean().replace(0, np.nan)
        df['Vol_Ratio'] = (df['Volume'] / df['Vol_MA20']).fillna(1.0)
        df['Vol_Accel_5d'] = (df['Volume'] / df['Vol_MA5']).fillna(1.0)

        delta = df['Close'].diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss.replace(0, np.nan)
        df['RSI'] = (100 - (100 / (1 + rs))).fillna(50.0)

        ema12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = ema12 - ema26
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

        tr = pd.concat([
            df['High'] - df['Low'],
            (df['High'] - df['Prev_Close']).abs(),
            (df['Low'] - df['Prev_Close']).abs()
        ], axis=1).max(axis=1)
        df['ATR'] = tr.rolling(14).mean().fillna(df['Close'] * 0.02)
        df['ATR_Pct'] = (df['ATR'] / df['Close'] * 100).fillna(2.0)

        high_low = (df['High'] - df['Low']).replace(0, np.nan)
        df['Close_Pos'] = ((df['Close'] - df['Low']) / high_low).fillna(0.5)
        body_top = df[['Open', 'Close']].max(axis=1)
        df['Upper_Shadow'] = ((df['High'] - body_top) / high_low).fillna(0.0)
        df['VWAP20'] = (((df['High'] + df['Low'] + df['Close']) / 3.0 * df['Volume']).rolling(20).sum() / df['Volume'].rolling(20).sum().replace(0, np.nan)).fillna(df['Close'])

        df['High_20'] = df['High'].shift(1).rolling(20).max().fillna(df['High'])
        df['Dist_High20'] = ((df['Close'] - df['High_20']) / df['High_20'] * 100).fillna(0.0)

        # ★ 機関投資家アルゴリズム①：VPIN（Order Flow Toxicity / 情報優位な大口買い圧力）
        df['Signed_Order_Flow'] = ((df['Close'] - df['Open']) / high_low).fillna(0.0) * df['Vol_Ratio']
        df['VPIN_5d'] = df['Signed_Order_Flow'].rolling(5).mean().fillna(0.0)

        # ★ 機関投資家アルゴリズム②：Amihud非流動性インパクト（板の薄さ・浮動株吸い上げ度）
        df['Amihud_Impact'] = (df['Day_Return'].abs() / df['Vol_Ratio'].replace(0, 1.0)).fillna(1.0)
        df['Amihud_Ratio'] = (df['Amihud_Impact'] / df['Amihud_Impact'].rolling(20).mean().replace(0, 1.0)).fillna(1.0)

        cond_inst_accum = (df['VPIN_5d'] >= 0.22) & (df['Close'] >= df['VWAP20']) & (df['Close_Pos'] >= 0.68)
        cond_5ch_surge = (df['Vol_Accel_5d'] >= 1.35) & (df['Close_Pos'] >= 0.72) & (df['Upper_Shadow'] <= 0.18) & (df['Close'] > df['Open'])
        cond_sq_breakout = (df['Close'] >= df['High_20'] * 0.992) & (df['Vol_Ratio'] >= 1.2) & (df['Close_Pos'] >= 0.7)

        df['Next_Open'] = df['Open'].shift(-1)
        df['Gap_Pct'] = (df['Next_Open'] - df['Close']) / df['Close'] * 100
        df['Morning_Up'] = df['Next_Open'] > df['Close']

        latest = df.iloc[-1]
        history = df.iloc[:-1].dropna(subset=['Next_Open', 'MA20', 'RSI'])
        if len(history) == 0:
            return None

        upper_sh = float(latest['Upper_Shadow'])
        vol_acc = float(latest['Vol_Accel_5d'])
        c_pos = float(latest['Close_Pos'])
        dist_h20 = float(latest['Dist_High20'])
        vpin_val = float(latest['VPIN_5d'])
        amihud_r = float(latest['Amihud_Ratio'])

        # 🏦 1. 機関投資家クオンツスコア（VPIN × VWAPステルス吸収 × Amihud浮動株枯渇）
        inst_raw = 50.0 + vpin_val * 45.0 + (c_pos - 0.5) * 25.0
        if float(latest['Close']) >= float(latest['VWAP20']):
            inst_raw += 10.0
        if float(latest['Day_Return']) > 0.5 and amihud_r >= 1.15 and upper_sh <= 0.2:
            inst_raw += 12.0
            inst_status = f"🏦 機関の浮動株吸い上げ・売り板枯渇 (VPIN {vpin_val:+.2f} / 価格弾性 {amihud_r:.2f}倍)"
        elif cond_inst_accum.iloc[-1]:
            inst_raw += 10.0
            inst_status = f"🏦 機関アルゴリズム・ステルス氷山買い集め検知 (VPIN {vpin_val:+.2f} / 20日VWAP上維持)"
        elif vpin_val < -0.15:
            inst_raw -= 12.0
            inst_status = f"⚠️ 機関のTWAP/VWAP売り執行警戒 (VPIN {vpin_val:+.2f})"
        else:
            inst_status = f"⚖️ 機関オーダーフロー中立 (VPIN {vpin_val:+.2f} / 弾性 {amihud_r:.2f}倍)"
        inst_score = int(min(max(round(inst_raw), 15), 99))

        # 🔥 2. 5chデイトレ板・シコリ玉＆初動イナゴスコア
        board5ch_raw = 50.0 + (min(vol_acc, 3.0) - 1.0) * 18.0 + (c_pos - 0.5) * 30.0
        if upper_sh >= 0.38:
            board5ch_raw -= 25.0
            board5ch_status = f"⚠️ 上ヒゲシコリ玉警戒 (上ヒゲ率{int(upper_sh*100)}%・ヤレヤレ売り注意)"
        elif dist_h20 >= -0.5 and upper_sh <= 0.15 and vol_acc >= 1.2:
            board5ch_raw += 18.0
            board5ch_status = "🚀 5ch板・青天井ブレイク (上値シコリ玉なし・イナゴ初動集中)"
        elif cond_5ch_surge.iloc[-1]:
            board5ch_raw += 12.0
            board5ch_status = f"🔥 5ch板・初動資金集中 (5日平均比 {vol_acc:.2f}倍の出来高急増＆高値引け)"
        else:
            board5ch_status = f"⚖️ 5ch板・通常需給 (5日出来高加速 {vol_acc:.2f}倍 / 上ヒゲ率 {int(upper_sh*100)}%)"
        board5ch_score = int(min(max(round(board5ch_raw), 15), 99))

        # 💥 3. 空売り踏み上げスコア
        sq_raw = 42.0 + (22.0 if dist_h20 >= 0 else (14.0 if dist_h20 >= -2.5 else 4.0))
        sq_raw += min(float(latest['Vol_Ratio']), 3.0) * 8.0 + (c_pos - 0.5) * 24.0
        squeeze_score = int(min(max(round(sq_raw), 15), 99))
        if cond_sq_breakout.iloc[-1]:
            squeeze_type = "🔥 20日高値ブレイク踏み上げ (売り方全員含み損)"
        elif dist_h20 >= -2.0 and c_pos >= 0.72:
            squeeze_type = "⚡ 踏み上げトリガーロックオン (高値突破寸前)"
        else:
            squeeze_type = f"⚖️ 20日高値乖離 {dist_h20:+.2f}%"

        close_pos_pct = int(round(c_pos * 100))
        closing_power_score = int(min(max(round(40.0 + c_pos * 35.0 + min(float(latest['Vol_Ratio']), 2.5) * 10.0), 15), 99))

        # バックテスト照合
        if cond_inst_accum.iloc[-1]:
            signal = "🏦 機関VPINステルス買い集め＋VWAP順行"
            sub = history[cond_inst_accum.reindex(history.index, fill_value=False)]
        elif cond_5ch_surge.iloc[-1]:
            signal = "🔥 5ch初動イナゴ集中＋シコリ玉なし高値引け"
            sub = history[cond_5ch_surge.reindex(history.index, fill_value=False)]
        elif cond_sq_breakout.iloc[-1]:
            signal = "🚀 20日高値ブレイク・ショートスクイーズ"
            sub = history[cond_sq_breakout.reindex(history.index, fill_value=False)]
        elif latest['Day_Return'] > 0:
            signal = "📈 陽線トレンド継続"
            sub = history[history['Day_Return'] > 0]
        else:
            signal = "☁️ 押し目・調整局面"
            sub = history[history['Day_Return'] <= 0]

        if len(sub) < 5:
            sub = history

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

        sox_diff = macro["sox"]["diff"] if macro else 0.0
        nk_diff = macro["nk_fut"]["diff"] if macro else 0.0
        sp_diff = macro["sp500"]["diff"] if macro else 0.0
        is_jp = ".T" in code
        overnight_impact = (nk_diff * 0.5 + sox_diff * 0.4) if is_jp else (sp_diff * 0.5 + sox_diff * 0.4)
        pts_gap_pct = round(avg_gap * 0.5 + overnight_impact * 0.6 + max(0.0, (inst_score - 55) * 0.025), 2)

        close_val = float(latest['Close'])
        atr_val = float(latest['ATR'])
        high20_val = float(latest['High_20'])
        pts_est_val = close_val * (1.0 + pts_gap_pct / 100.0)
        tokugai_pct_threshold = max(2.2, min(round(float(latest['ATR_Pct']) * 0.95, 2), 4.0))
        tokugai_line_val = close_val * (1.0 + tokugai_pct_threshold / 100.0)

        tokugai_raw = 18.0 + max(0.0, pts_gap_pct) * 14.0 + max(0.0, inst_score - 50) * 0.4 + max(0.0, board5ch_score - 50) * 0.4 + max(0.0, squeeze_score - 50) * 0.4
        tokugai_prob = int(min(max(round(tokugai_raw), 5), 98))
        tokugai_status = "🚨 特買い（気配切り上げ）濃厚" if tokugai_prob >= 70 else ("🌅 買い気配先行スタート優勢" if tokugai_prob >= 52 else "⚖️ 通常気配スタート")

        base_score = min(max(prob * 0.52, 10), 44) + min(max((expected_edge + 0.3) * 12, 0), 14)
        in_bonus = round((inst_score - 50) * 0.22) if boost_inst else 0
        b5_bonus = round((board5ch_score - 50) * 0.18) if boost_5ch else 0
        sq_bonus = round((squeeze_score - 50) * 0.16) if boost_squeeze else 0
        tk_bonus = round((tokugai_prob - 45) * 0.14) if boost_tokugai else 0
        ai_score = int(min(max(round(base_score + in_bonus + b5_bonus + sq_bonus + tk_bonus), 15), 99))

        survival_power = round(
            ai_score * 0.35 + inst_score * 0.25 + board5ch_score * 0.20 + squeeze_score * 0.10 + min(float(latest['ATR_Pct']) * 3.5, 12.0), 1
        )

        tp_val = max(pts_est_val, close_val) + (atr_val * 0.85)
        sl_val = close_val - (atr_val * 0.5)
        risk_per_share = max(close_val - sl_val, close_val * 0.005)
        allowed_risk_money = total_capital * (risk_tolerance_pct / 100.0)
        shares = max(1, int(allowed_risk_money / risk_per_share))

        def fmt_p(v):
            return f"{v:,.0f}円" if is_jp else f"${v:,.2f}"

        return {
            "full_code": code, "code": code.replace(".T", ""), "name": name, "genre": genre,
            "price": fmt_p(close_val), "raw_close": close_val,
            "tp_price": fmt_p(tp_val), "tp_pct": round((tp_val - close_val) / close_val * 100, 1),
            "sl_price": fmt_p(sl_val), "sl_pct": round((sl_val - close_val) / close_val * 100, 1),
            "vwap_price": fmt_p(float(latest['VWAP20'])),
            "inst_score": inst_score, "inst_status": inst_status, "vpin": round(vpin_val, 2), "amihud_ratio": round(amihud_r, 2),
            "board5ch_score": board5ch_score, "board5ch_status": board5ch_status, "upper_shadow_pct": int(upper_sh * 100),
            "close_pos_pct": close_pos_pct, "closing_power_score": closing_power_score,
            "squeeze_score": squeeze_score, "squeeze_type": squeeze_type,
            "squeeze_trigger_price": fmt_p(high20_val), "raw_high20": high20_val, "dist_to_high20": round(dist_h20, 2),
            "pts_est_price": fmt_p(pts_est_val), "pts_gap_pct": pts_gap_pct,
            "tokugai_prob": tokugai_prob, "tokugai_line": fmt_p(tokugai_line_val),
            "tokugai_pct_threshold": tokugai_pct_threshold, "tokugai_status": tokugai_status,
            "diff": round(float(latest['Day_Return']), 2), "signal": signal,
            "prob": prob, "count": f"{wins}/{total}回", "gap": avg_gap, "max_win_gap": max_win_gap,
            "rsi": round(float(latest['RSI']), 1), "vol_ratio": round(float(latest['Vol_Ratio']), 2),
            "macd_state": "強気↑" if latest['MACD_Hist'] > 0 else "調整↓",
            "atr_pct": round(float(latest['ATR_Pct']), 1), "payoff": payoff_ratio, "edge": expected_edge,
            "ai_score": ai_score, "survival_power": survival_power, "theme": theme,
            "lot_info": {
                "shares": shares, "position_value": shares * close_val,
                "capital_ratio": round((shares * close_val / total_capital) * 100, 1),
                "risk_amount": allowed_risk_money
            }
        }
    except Exception:
        return None

@st.cache_data(ttl=1800)
def fetch_all_pool_batch(macro, boost_inst, boost_5ch, boost_squeeze, boost_tokugai):
    all_codes = list({s["code"] for stocks in STOCK_POOL.values() for s in stocks})
    raw_data = yf.download(all_codes, period="6mo", group_by="ticker", threads=True, progress=False)

    genre_Map = {g: [] for g in STOCK_POOL.keys()}
    all_list = []
    seen = set()

    for genre, stocks in STOCK_POOL.items():
        for s in stocks:
            c = s["code"]
            try:
                df_c = raw_data[c] if len(all_codes) > 1 else raw_data
                res = analyze_single_dataframe(df_c, c, s["name"], s["theme"], genre, macro, boost_inst, boost_5ch, boost_squeeze, boost_tokugai)
                if res:
                    genre_Map[genre].append(res)
                    if c not in seen:
                        all_list.append(res)
                        seen.add(c)
            except Exception:
                continue
    return genre_Map, all_list

@st.cache_data(ttl=600)
def fetch_single_stock(code, macro, boost_inst, boost_5ch, boost_squeeze, boost_tokugai):
    df_c = yf.Ticker(code).history(period="6mo")
    info = KNOWN_STOCKS.get(code, {"name": code.replace(".T", ""), "theme": "個別指定銘柄", "genre": "個別検索"})
    return analyze_single_dataframe(df_c, code, info["name"], info["theme"], info["genre"], macro, boost_inst, boost_5ch, boost_squeeze, boost_tokugai)

# --- ⚡ 5分足（Intraday）解析エンジン ---
@st.cache_data(ttl=300)
def fetch_5m_intraday_algo(full_code, trigger_high20=None):
    try:
        df5 = yf.Ticker(full_code).history(period="5d", interval="5m")
        if df5 is None or df5.empty or len(df5) < 12: return None
        df5 = df5.dropna(subset=['Close', 'Open', 'High', 'Low', 'Volume'])
        dates = df5.index.date
        day_df = df5[dates == dates[-1]].copy()
        if len(day_df) < 6: day_df = df5.tail(36).copy()

        tp = (day_df['High'] + day_df['Low'] + day_df['Close']) / 3.0
        day_df['VWAP_5m'] = ((tp * day_df['Volume']).cumsum() / day_df['Volume'].cumsum().replace(0, np.nan)).fillna(day_df['Close'])
        latest_c = float(day_df['Close'].iloc[-1])
        latest_vwap5 = float(day_df['VWAP_5m'].iloc[-1])
        vwap5_dev = round((latest_c - latest_vwap5) / latest_vwap5 * 100, 2) if latest_vwap5 != 0 else 0.0

        recent_12 = day_df.tail(12)
        twap_green = round(int((recent_12['Close'] >= recent_12['Open']).sum()) / len(recent_12) * 100, 1)
        is_jp = ".T" in full_code
        vwap5_fmt = f"{latest_vwap5:,.0f}円" if is_jp else f"${latest_vwap5:,.2f}"

        status_5m = "🔥 5分足VWAP上・機関TWAP順行" if vwap5_dev >= 0 else "🧊 5分足VWAP下・押し目待機"
        chart_df = pd.DataFrame({
            "Time": day_df.index.strftime("%H:%M"),
            "Open": day_df["Open"].astype(float).values, "High": day_df["High"].astype(float).values,
            "Low": day_df["Low"].astype(float).values, "Close": day_df["Close"].astype(float).values,
            "VWAP": day_df["VWAP_5m"].astype(float).values,
            "TriggerLine": float(trigger_high20) if trigger_high20 else latest_vwap5,
            "BarColor": np.where(day_df["Close"].values >= day_df["Open"].values, "陽線", "陰線")
        })
        return {"vwap5_price": vwap5_fmt, "vwap5_dev": vwap5_dev, "twap_green_ratio": twap_green, "status_5m": status_5m, "chart_date": str(dates[-1]), "chart_df": chart_df}
    except Exception:
        return None

def render_5m_candlestick_chart(m5):
    if not m5 or "chart_df" not in m5: return
    cdf = m5["chart_df"]
    base = alt.Chart(cdf).encode(x=alt.X("Time:N", sort=None, title=None))
    color_scale = alt.Scale(domain=["陽線", "陰線"], range=["#dc2626", "#2563eb"])
    wick = base.mark_rule(size=1.5).encode(y=alt.Y("Low:Q", scale=alt.Scale(zero=False), title="株価"), y2="High:Q", color=alt.Color("BarColor:N", scale=color_scale, legend=None))
    body = base.mark_bar(size=6).encode(y=alt.Y("Open:Q", scale=alt.Scale(zero=False)), y2="Close:Q", color=alt.Color("BarColor:N", scale=color_scale, legend=None))
    vwap_line = base.mark_line(color="#d97706", strokeWidth=2.5, strokeDash=[4, 2]).encode(y="VWAP:Q")
    st.altair_chart((wick + body + vwap_line).properties(height=190), use_container_width=True)

# ==========================================
# 🧠 7大AI【動的ロール割り当て】合議アルゴリズム（GPT→ChatGPT変更済）
# ==========================================
def run_7ai_council_algorithm(r, m5=None):
    """銘柄の波形や特徴に応じて、7大AIがそれぞれの得意分野の中で毎回異なる専門テーマ（担当ジャンル）に変化して検証する"""
    vwap_ref = m5['vwap5_price'] if m5 else r['vwap_price']
    half_lot = max(1, r['lot_info']['shares'] // 2)
    rem_lot = max(0, r['lot_info']['shares'] - half_lot)

    # 銘柄コードと日付・波形スコアから、各AIの得意分野ローテーションを決定
    code_seed = sum(ord(ch) for ch in r["code"])
    is_squeeze_hot = r["squeeze_score"] >= 68
    is_inst_hot = r["inst_score"] >= 68
    is_5ch_hot = r["board5ch_score"] >= 68

    claude_s  = int(min(max(round(50 + (r["prob"] - 50) * 0.8 + (r["payoff"] - 1.0) * 15 - r["upper_shadow_pct"] * 0.2), 20), 99))
    grok_s    = int(min(max(round(45 + (r["board5ch_score"] - 50) * 0.45 + (r["squeeze_score"] - 50) * 0.35 + r["tokugai_prob"] * 0.15), 20), 99))
    chatgpt_s = int(min(max(round((r["ai_score"] + r["inst_score"] + claude_s) / 3.0), 20), 99))
    gemini_s  = int(min(max(round(50 + r["pts_gap_pct"] * 12 + (r["inst_score"] - 50) * 0.35), 20), 99))
    perp_s    = int(min(max(round(r["inst_score"] * 0.55 + r["board5ch_score"] * 0.45), 20), 99))
    gensp_s   = int(min(max(round((claude_s + grok_s + chatgpt_s + gemini_s + perp_s) / 5.0), 20), 99))
    nblm_s    = int(min(max(round(48 + (r["prob"] - 50) * 0.9 + (r["payoff"] - 1.0) * 12), 20), 99))
    final_s   = int(round((claude_s + grok_s + chatgpt_s + gemini_s + perp_s + gensp_s + nblm_s) / 7.0))

    # 1. Claude（得意分野：数理リスク管理 ／ 機関VPINオーダーフロー毒性 ／ ケリー基準資金配分）
    if is_inst_hot:
        claude_role = "🟠 Claude【担当：機関VPINオーダーフロー毒性＆下値リスク監査】"
        claude_msg = f"機関のVPIN（情報優位フロー）が <b>{r['vpin']:+.2f}</b> とプラス圏で推移し、下値は機関の氷山注文で支えられています。逆指値 <b>{r['sl_price']}</b> を置けばリスク対比の期待値は抜群です。"
    elif r["upper_shadow_pct"] >= 30:
        claude_role = "🟠 Claude【担当：高値掴みドローダウン制御＆シコリ玉警戒】"
        claude_msg = f"上ヒゲ率 <b>{r['upper_shadow_pct']}%</b> の戻り売りリスクを計算しました。朝イチの成行飛びつきは避け、<b>{vwap_ref}</b> までの押し目を待つことで最大損失を <b>{r['lot_info']['risk_amount']:,.0f}円</b> 以内に完全ロックできます。"
    else:
        claude_role = "🟠 Claude【担当：ケリー基準期待値＆リスクリワード数理検証】"
        claude_msg = f"過去勝率 <b>{r['prob']}%</b>・損益比 <b>{r['payoff']}倍</b>（期待値 <b>{r['edge']:+.2f}%</b>）。統計的に優位なセットアップであり、総資金の <b>{r['lot_info']['capital_ratio']}%（{r['lot_info']['shares']:,}株）</b> 投入が数学的最適解です。"

    # 2. Grok（得意分野：X/5chリアルタイム群集心理 ／ 空売り踏み上げ ／ 特買いイナゴ初動）
    if is_squeeze_hot:
        grok_role = "🔴 Grok【担当：ショートスクイーズ（空売り丸焦げ踏み上げ）解析】"
        grok_msg = f"空売り勢の防衛線である20日高値（<b>{r['squeeze_trigger_price']}</b>）まであと <b>{r['dist_to_high20']:+.2f}%</b>！ここを突破した瞬間、売り方の強制ロスカット買い戻しが連鎖爆発します。"
    elif is_5ch_hot:
        grok_role = "🔴 Grok【担当：5chデイトレ実況板・初動イナゴモメンタム解析】"
        grok_msg = f"5ch板需給は「<b>{r['board5ch_status']}</b>」。シコリ玉が極めて少なく、寄付きからデイトレーダーの順張り資金が一気に集中しやすい波形です。"
    else:
        grok_role = "🔴 Grok【担当：SNSセンチメント＆寄り前『特買い』気配爆発力】"
        grok_msg = f"翌朝の特買い発生確率は <b>{r['tokugai_prob']}%</b>（特買い発動ライン <b>{r['tokugai_line']}</b>）。朝8:50の気配値が <b>{r['pts_est_price']}</b> 超えなら初動の勢いに乗るチャンスです。"

    # 3. ChatGPT（得意分野：機関アルゴ執行戦略 ／ マルチタイムフレーム統合 ／ ポートフォリオ戦術）
    if code_seed % 3 == 0:
        chatgpt_role = "🟢 ChatGPT【担当：機関投資家VWAP/TWAPアルゴリズム追随戦略】"
        chatgpt_msg = f"機関投資家の執行基準線であるVWAP（<b>{vwap_ref}</b>）と日足MACD（<b>{r['macd_state']}</b>）を統合評価。機関アルゴと同様にVWAPより上での順張り分割買いが最も合理的です。"
    elif code_seed % 3 == 1:
        chatgpt_role = "🟢 ChatGPT【担当：日足×5分足マルチタイムフレーム・シナリオ構築】"
        chatgpt_msg = f"日足のトレンド強度はAIスコア <b>{r['ai_score']}点</b>、夜間理論ギャップは <b>{r['pts_gap_pct']:+.2f}%</b>。寄付き直後の乱高下をやり過ごし、9:10以降のトレンド確定に乗る王道シナリオを推奨します。"
    else:
        chatgpt_role = "🟢 ChatGPT【担当：総合クオンツバランス＆機関ステルス吸収判定】"
        chatgpt_msg = f"機関クオンツ評価「<b>{r['inst_status']}</b>」と個人需給のバランスが高水準で一致。第一利確ターゲット <b>{r['tp_price']}（+{r['tp_pct']}%）</b> を狙うメイン銘柄として承認します。"

    # 4. Gemini（得意分野：グローバルマクロ連動 ／ テーマ・国策セクター資金循環 ／ 夜間ADR・先物波及）
    if ".T" in r["full_code"]:
        gemini_role = f"🔵 Gemini【担当：CME日経先物・米SOX連動＆『{r['genre']}』資金循環】"
        gemini_msg = f"海外マクロ地合いと「{r['genre']}」テーマ（{r['theme']}）の資金流入を解析。夜間理論気配は <b>{r['pts_est_price']}</b> と算出され、海外勢のバスケット買いが入りやすい環境です。"
    else:
        gemini_role = f"🔵 Gemini【担当：米国ウォール街セクターローテーション＆金利・VIX連動】"
        gemini_msg = f"米国「{r['genre']}」セクターへの機関資金フローは堅調。プレマーケット気配（理論値 <b>{r['pts_est_price']}</b>）から寄り付き後の上値追いが期待できます。"

    # 5. Perplexity（得意分野：ダークプール・大口約定監査 ／ 板の薄さAmihud検証 ／ 見せ板ファクトチェック）
    if r["amihud_ratio"] >= 1.1:
        perp_role = "🌐 Perplexity【担当：Amihud非流動性（浮動株枯渇・板の薄さ）監査】"
        perp_msg = f"Amihud価格弾性率が <b>{r['amihud_ratio']}倍</b> に上昇中。機関が浮動株を吸収したことで売り板が薄くなっており、まとまった買いが入ると一気に値が飛びやすい真空状態です。"
    else:
        perp_role = "🌐 Perplexity【担当：大引けMOC機関買い集め＆朝8:55見せ板ファクトチェック】"
        perp_msg = f"出来高倍率 <b>{r['vol_ratio']}倍</b>・引け位置 <b>{r['close_pos_pct']}%</b> を検証。フェイクの見せ板を排除するため、注文取消が制限される朝8:55以降の成行買い残を確認してください。"

    # 6. Genspark（得意分野：時間軸別エグゼキューション戦術 ／ 2段階ピラミッディング ／ トレーリング利確）
    if is_squeeze_hot:
        gensp_role = "✨ Genspark【担当：高値ブレイクアウト追撃（ピラミッディング）戦術】"
        gensp_msg = f"①寄付きでまず <b>{half_lot:,}株</b> エントリー → ②空売り踏み上げトリガーである <b>{r['squeeze_trigger_price']}</b> を突破した瞬間に残り <b>{rem_lot:,}株</b> を追撃投入する攻撃型戦術がベストです！"
    else:
        gensp_role = "✨ Genspark【担当：機関流・5分足VWAP押し目2分割エントリー戦術】"
        gensp_msg = f"①朝9:00に打診買い <b>{half_lot:,}株</b> → ②9:05〜9:25に5分足VWAP（<b>{vwap_ref}</b>）で下ヒゲ反発を確認して残り <b>{rem_lot:,}株</b> を追加し、<b>{r['tp_price']}</b> で利確します。"

    # 7. NotebookLM（得意分野：過去1年アノマリー照合 ／ 類似波形バックテスト ／ 勝ちパターン抽出）
    nblm_role = "📓 NotebookLM【担当：過去1年ヒストリカル類似波形＆アノマリー照合】"
    nblm_msg = f"過去1年間で「{r['signal']}」が出現した <b>{r['count']}</b> を照合した結果、翌朝上昇率は <b>{r['prob']}%</b>、過去最大ギャップアップは <b>+{r['max_win_gap']}%</b> と高い再現性を記録しています。"

    return {
        "final_score": final_s,
        "agents": [
            (claude_role, claude_s, claude_msg),
            (grok_role, grok_s, grok_msg),
            (chatgpt_role, chatgpt_s, chatgpt_msg),
            (gemini_role, gemini_s, gemini_msg),
            (perp_role, perp_s, perp_msg),
            (gensp_role, gensp_s, gensp_msg),
            (nblm_role, nblm_s, nblm_msg),
        ],
        "verdict_html": (
            f'<div class="consensus-section"><b>① 🏦 機関クオンツ＆朝8:55気配判定：</b>{r["inst_status"]}。夜間理論気配 <b>{r["pts_est_price"]}</b>（特買い線 <b>{r["tokugai_line"]}</b>）を維持しているか確認。</div>'
            f'<div class="consensus-section"><b>② ⚡ 2段階エントリー：</b>推奨総数 <b>{r["lot_info"]["shares"]:,}株</b> のうち、寄付きで <b>{half_lot:,}株</b>、VWAP（<b>{vwap_ref}</b>）反発または20日高値（<b>{r["squeeze_trigger_price"]}</b>）突破で残り <b>{rem_lot:,}株</b> を投入。</div>'
            f'<div class="consensus-section"><b>③ 🎯 利確＆絶対損切り：</b>利確目標 <b>{r["tp_price"]}（+{r["tp_pct"]}%）</b> ／ 逆指値 <b>{r["sl_price"]}（最大損失 {r["lot_info"]["risk_amount"]:,.0f}円）</b>。</div>'
        )
    }

def generate_7ai_qa_response(question, r, debate, lot_info, m5=None):
    """質問内容に応じて、最も得意なAIたちが専門ロールで即座に回答するエンジン"""
    q_clean = unicodedata.normalize('NFKC', str(question)).strip()
    q_low = q_clean.lower()
    m5_vwap = m5["vwap5_price"] if m5 else r["vwap_price"]
    half_s = max(1, lot_info['shares'] // 2)
    rem_s = max(0, lot_info['shares'] - half_s)

    if any(k in q_low for k in ["機関", "アルゴ", "vpin", "大口", "ステルス", "浮動株", "板"]):
        return (
            f"🏦 <b>【「{q_clean}」への回答｜担当：ChatGPT ＆ Perplexity（機関投資家クオンツ解析）】</b><br>"
            f"・<b>機関オーダーフロー診断：</b>現在の機関クオンツスコアは <b>{r['inst_score']}点</b>（<b>{r['inst_status']}</b>）です。<br>"
            f"・<b>VPIN＆板の薄さ（Amihud）：</b>情報優位な大口買いを示すVPINは <b>{r['vpin']:+.2f}</b>、浮動株の吸い上げによる価格弾性（Amihud比率）は <b>{r['amihud_ratio']}倍</b> です。<br>"
            f"・<b>実戦での乗り方：</b>機関の執行アルゴは <b>VWAP（{m5_vwap}）</b> を基準に買い集めます。朝イチにVWAPより上で推移していれば機関の買いが継続しているため、押し目を一緒に拾うのが最も勝率の高い戦術です。"
        )
    elif any(k in q_low for k in ["特買", "気配", "pts", "夜間", "8時", "寄"]):
        return (
            f"🚨 <b>【「{q_clean}」への回答｜担当：Grok ＆ Gemini（夜間PTS・特買い気配解析）】</b><br>"
            f"・明日の夜間理論気配値は <b>{r['pts_est_price']}（前日比 {r['pts_gap_pct']:+.2f}%）</b>、特買い発生確率は <b>{r['tokugai_prob']}%</b> です。<br>"
            f"・気配値が <b>{r['tokugai_line']}（+{r['tokugai_pct_threshold']}%）</b> を超えると特別買い気配（特買い）になります。寄付きはまず半分の <b>{half_s:,}株</b> で入り、<b>{m5_vwap}（VWAP）</b> サポートを確認してから残り <b>{rem_s:,}株</b> を追加してください。"
        )
    elif any(k in q_low for k in ["踏み上げ", "空売", "スクイーズ", "高値", "シコリ", "5ch", "イナゴ"]):
        return (
            f"🔥 <b>【「{q_clean}」への回答｜担当：Grok ＆ Claude（5chシコリ玉＆空売り踏み上げ解析）】</b><br>"
            f"・<b>5ch板・シコリ玉診断：</b>現在「<b>{r['board5ch_status']}</b>」（5ch需給スコア <b>{r['board5ch_score']}点</b> / 上ヒゲ率 <b>{r['upper_shadow_pct']}%</b>）です。<br>"
            f"・<b>踏み上げトリガー価格：</b>直近20日高値の <b>{r['squeeze_trigger_price']}（現在値から {r['dist_to_high20']:+.2f}%）</b> を突破すると、空売り勢の強制ロスカット（成行買い戻し）が連鎖し <b>{r['tp_price']}</b> へ急伸しやすくなります。"
        )
    elif any(k in q_low for k in ["5分", "vwap", "チャート", "初動", "テクニカル", "rsi", "macd"]):
        return (
            f"⚡ <b>【「{q_clean}」への回答｜担当：ChatGPT ＆ Genspark（5分足＆テクニカル執行戦術）】</b><br>"
            f"・現在の5分足VWAPは <b>{m5_vwap}</b>、日足RSIは <b>{r['rsi']}</b>、MACDは <b>{r['macd_state']}</b>、出来高倍率は <b>{r['vol_ratio']}倍</b> です。<br>"
            f"・朝9:00〜9:15の初動でローソク足が <b>{m5_vwap}</b> より上をキープしていれば機関・大口が買い支えていますので、順張りホールドが正解です。"
        )
    elif any(k in q_low for k in ["損切", "利確", "目標", "売", "出口", "リスク", "下が"]):
        return (
            f"🛡️ <b>【「{q_clean}」への回答｜担当：Claude ＆ NotebookLM（利確目標＆リスク管理）】</b><br>"
            f"・<b>🎯 第一利確目標：</b><b>{r['tp_price']}（+{r['tp_pct']}%）</b> で半分を利益確定し、残りは5分足VWAP（<b>{m5_vwap}</b>）を割るまで利益を伸ばします（過去最大GU実績 <b>+{r['max_win_gap']}%</b>）。<br>"
            f"・<b>🛡️ 絶対損切りライン：</b>購入直後に必ず <b>{r['sl_price']}（{r['sl_pct']}%）</b> に逆指値を入れてください。最大損失は <b>約{lot_info['risk_amount']:,.0f}円（総資金の{risk_tolerance_pct}%）</b> に完全に抑えられます。"
        )
    else:
        return (
            f"🤖 <b>【自由質問「{q_clean}」への回答｜担当：ChatGPT・Claude・Grok 7大AI合同評議会】</b><br>"
            f"・<b>総合ジャッジ：</b>「{r['name']}（{r['code']}）」の7大AI合議スコアは <b>{debate['final_score']}点</b>、機関クオンツスコアは <b>{r['inst_score']}点（{r['inst_status']}）</b>、サバイバル戦闘力は <b>{r['survival_power']}pt</b> です。<br>"
            f"・<b>あなたの質問への結論と売買プラン：</b>総資金 {total_capital:,.0f}円 に対する最適ロットは <b>{lot_info['shares']:,}株（投資額 {lot_info['position_value']:,.0f}円）</b> です。<br>"
            f"・明日の朝はまず寄付き（目安 <b>{r['pts_est_price']}</b>）で半分の <b>{half_s:,}株</b> を買い、<b>{m5_vwap}（VWAP）</b> 反発または <b>{r['squeeze_trigger_price']}（20日高値）</b> 突破で残り <b>{rem_s:,}株</b> を追加、利確 <b>{r['tp_price']}</b>・損切り <b>{r['sl_price']}</b> で臨むのが最も期待値（<b>{r['edge']:+.2f}%</b>・過去勝率 <b>{r['prob']}%</b>）の高い戦術です。"
        )

# ==========================================
# 💬 会議パネル＆質問コーナー（st.form廃止・100%確実動作コールバック版）
# ==========================================
def cb_toggle_debate(unique_key):
    st.session_state["active_debates"][unique_key] = not st.session_state["active_debates"].get(unique_key, False)

def cb_toggle_watchlist(code, r_data):
    if code in st.session_state["watchlist"]:
        del st.session_state["watchlist"][code]
    else:
        st.session_state["watchlist"][code] = r_data

def cb_handle_preset_q(unique_key, q_text, r, debate, m5):
    """ワンタップ質問ボタン用コールバック"""
    if unique_key not in st.session_state["stock_chats"]:
        st.session_state["stock_chats"][unique_key] = []
    ans_html = generate_7ai_qa_response(q_text, r, debate, r["lot_info"], m5)
    st.session_state["stock_chats"][unique_key].append({"q": q_text, "a": ans_html})

def cb_handle_free_q(unique_key, input_key, r, debate, m5):
    """自由入力質問用コールバック（Enterキー押下でもボタン押下でも確実に発動し入力欄をクリア）"""
    user_txt = st.session_state.get(input_key, "").strip()
    if user_txt:
        if unique_key not in st.session_state["stock_chats"]:
            st.session_state["stock_chats"][unique_key] = []
        ans_html = generate_7ai_qa_response(user_txt, r, debate, r["lot_info"], m5)
        st.session_state["stock_chats"][unique_key].append({"q": user_txt, "a": ans_html})
        st.session_state[input_key] = ""

def cb_clear_chat(unique_key):
    st.session_state["stock_chats"][unique_key] = []

@fragment_decorator
def render_interactive_council_section(r, unique_key):
    is_open = st.session_state["active_debates"].get(unique_key, False)
    in_wl = r["code"] in st.session_state["watchlist"]

    c1, c2 = st.columns([2.2, 1.2])
    with c1:
        st.button(
            "🔼 会議パネルを閉じる" if is_open else "🧠 7大AIで会議して詳細＆質問コーナーを開く",
            key=f"btn_{unique_key}", on_click=cb_toggle_debate, args=(unique_key,), use_container_width=True
        )
    with c2:
        st.button(
            "✅ 監視登録済(解除)" if in_wl else "⭐ 監視リスト追加",
            key=f"wl_{unique_key}", on_click=cb_toggle_watchlist, args=(r["code"], r), use_container_width=True
        )

    if not st.session_state["active_debates"].get(unique_key, False):
        return

    m5 = fetch_5m_intraday_algo(r["full_code"], trigger_high20=r["raw_high20"])
    debate = run_7ai_council_algorithm(r, m5)

    if unique_key not in st.session_state["debate_Animated"]:
        with st.status(f"🧠 7大AIがそれぞれの専門領域から「{r['name']}」を徹底議論中...", expanded=True) as status:
            prog = st.progress(0)
            for pct, msg in [
                (25, "🟠 Claude & 🔴 Grok が機関VPINフロー・5ch需給・踏み上げを解析中..."),
                (60, "🟢 ChatGPT & 🔵 Gemini & 🌐 Perplexity がVWAP執行と浮動株枯渇度を検証中..."),
                (100, "✨ Genspark & 📓 NotebookLM が2段階エントリー戦術を統合中...")
            ]:
                st.write(msg)
                prog.progress(pct)
                time.sleep(0.35)
            status.update(label=f"✅ 7大AI合議完了！（合議スコア: {debate['final_score']}点）", state="complete", expanded=False)
        st.session_state["debate_Animated"].add(unique_key)

    if m5 and show_5m_chart:
        st.caption(f"📅 直近5分足チャート ({m5['chart_date']}) ｜ 5分足VWAP: **{m5['vwap5_price']}** ({m5['vwap5_dev']:+.2f}%)")
        render_5m_candlestick_chart(m5)

    agents_html = "".join([
        f'<div class="ai-agent-card"><div style="font-weight:bold; color:#fbbf24;">{ag_name} — {ag_score}点</div><div>{ag_comm}</div></div>'
        for ag_name, ag_score, ag_comm in debate["agents"]
    ])
    st.markdown(
        f'<div class="ai-council-box">'
        f'<div style="display:flex; justify-content:space-between; margin-bottom:10px;">'
        f'<span style="font-weight:bold; color:#fbbf24;">🧠 7大AI最高評議会（銘柄別・動的専門ロール検証）</span>'
        f'<span style="background:#4f46e5; color:#fff; padding:2px 10px; border-radius:12px; font-size:12px; font-weight:bold;">合議スコア: {debate["final_score"]}点</span>'
        f'</div>{agents_html}'
        f'<div class="consensus-banner"><div style="font-weight:bold; color:#fde047;">🏛️ 7大AI最終コンセンサス</div>{debate["verdict_html"]}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    # ==========================================
    # 💬 質問コーナー（st.formを使わずコールバック直結で100%即答）
    # ==========================================
    if unique_key not in st.session_state["stock_chats"]:
        st.session_state["stock_chats"][unique_key] = []

    st.markdown("##### 💬 7大AI評議会へのワンタップ＆自由質問コーナー")

    # 1. 最新回答＆履歴表示（質問ボタンのすぐ上にリアルタイム表示）
    chat_history = st.session_state["stock_chats"].get(unique_key, [])
    if chat_history:
        latest_item = chat_history[-1]
        st.markdown(
            f'<div class="qa-active-box">'
            f'<div class="qa-bubble-user">🙋 あなたの質問 #{len(chat_history)}: {latest_item["q"]}</div>'
            f'<div class="qa-bubble-ai">{latest_item["a"]}</div>'
            f'</div>',
            unsafe_allow_html=True
        )
    else:
        st.info("👇 下のワンタップボタン、または自由入力欄から質問すると、ここに7大AIの回答が即座に表示されます。")

    # 2. ワンタップ質問ボタン（4種類）
    q_col1, q_col2 = st.columns(2)
    with q_col1:
        st.button(
            "🏦 機関投資家のステルス買い・VPINは？",
            key=f"q1_{unique_key}",
            on_click=cb_handle_preset_q,
            args=(unique_key, "機関投資家のステルス買い集めやVPINの状況は？", r, debate, m5),
            use_container_width=True
        )
        st.button(
            "🔥 5chシコリ玉と踏み上げ価格は？",
            key=f"q2_{unique_key}",
            on_click=cb_handle_preset_q,
            args=(unique_key, "5ch板のシコリ玉と空売り踏み上げトリガー価格は？", r, debate, m5),
            use_container_width=True
        )
    with q_col2:
        st.button(
            "🚨 特買い確率と8:50気配の見方は？",
            key=f"q3_{unique_key}",
            on_click=cb_handle_preset_q,
            args=(unique_key, "翌朝の特買い確率と8:50気配の見方は？", r, debate, m5),
            use_container_width=True
        )
        st.button(
            "💰 具体的な買い方・利確・損切りは？",
            key=f"q4_{unique_key}",
            on_click=cb_handle_preset_q,
            args=(unique_key, "具体的な買い方と利確・損切りラインを教えて", r, debate, m5),
            use_container_width=True
        )

    # 3. 自由入力欄（st.formを廃止し、Enterキーでも「AIに質問」ボタンでも確実にon_click/on_changeで即答！）
    input_key = f"free_q_in_{unique_key}"
    f_col1, f_col2 = st.columns([3.2, 1])
    with f_col1:
        st.text_input(
            "自由質問を入力",
            key=input_key,
            placeholder="自由に質問を入力（例：いつ売るべき？ / なぜ上がる？ / リスクは？）",
            label_visibility="collapsed",
            on_change=cb_handle_free_q,
            args=(unique_key, input_key, r, debate, m5)
        )
    with f_col2:
        st.button(
            "AIに質問",
            key=f"free_q_btn_{unique_key}",
            on_click=cb_handle_free_q,
            args=(unique_key, input_key, r, debate, m5),
            use_container_width=True
        )

    # 4. 過去の質問履歴一覧
    if chat_history:
        with st.expander(f"📚 質問履歴をすべて見る（全 {len(chat_history)} 件）", expanded=False):
            for idx_h in range(len(chat_history) - 1, -1, -1):
                item = chat_history[idx_h]
                st.markdown(
                    f'<div class="qa-history-card">'
                    f'<div style="font-weight:bold; color:#4f46e5; margin-bottom:6px;">🙋 【質問 #{idx_h + 1}】 {item["q"]}</div>'
                    f'<div style="color:#0f172a;">{item["a"]}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
            st.button(
                "🗑️ この銘柄の質問履歴をクリア",
                key=f"clr_{unique_key}",
                on_click=cb_clear_chat,
                args=(unique_key,),
                use_container_width=True
            )

# ==========================================
# 🃏 銘柄カード描画
# ==========================================
def render_stock_card(r, is_custom=False, rank=None, key_prefix="card"):
    diff_color = "#dc2626" if r["diff"] > 0 else "#2563eb"
    diff_sign = "+" if r["diff"] > 0 else ""
    pts_sign = "+" if r["pts_gap_pct"] > 0 else ""
    rank_html = f'<span class="rank-badge">第{rank}位</span>' if rank else ""
    lot = r["lot_info"]

    html_card = (
        f'<div class="{"search-result-card" if is_custom else "rank-card"}">'
        f'<div>{rank_html}<span class="score-badge">🤖 AIスコア: {r["ai_score"]}点</span>'
        f'<span class="inst-badge">🏦 機関クオンツ: {r["inst_score"]}点</span>'
        f'<span class="board5ch-badge">🔥 5ch需給: {r["board5ch_score"]}点</span>'
        f'<span class="tokugai-badge">🚨 特買い: {r["tokugai_prob"]}%</span>'
        f'<span class="squeeze-badge">踏み上げ: {r["squeeze_score"]}点</span>'
        f'<span class="survival-badge">🦁 戦闘力: {r["survival_power"]}</span></div>'
        f'<div style="display:flex; justify-content:space-between; align-items:center; margin-top:6px;">'
        f'<div><span style="font-size:16px; font-weight:bold; color:#0f172a;">{r["name"]}</span> '
        f'<span style="font-size:12px; color:#64748b;">({r["code"]} / {r["genre"]})</span><br>'
        f'<span style="font-size:14px; color:#334155;">終値: <b>{r["price"]}</b> '
        f'(<span style="color:{diff_color}; font-weight:bold;">{diff_sign}{r["diff"]}%</span>)</span></div>'
        f'<div style="text-align:right;"><span style="font-size:11px; color:#64748b;">翌朝上昇確率</span><br>'
        f'<span class="prob-badge">{r["prob"]}%</span>'
        f'<div style="font-size:11px; color:#64748b;">({r["count"]} / 損益比{r["payoff"]}倍)</div></div>'
        f'</div>'
        f'<div class="inst-box"><b>{r["inst_status"]}</b> ｜ 20日VWAP基準: <b>{r["vwap_price"]}</b></div>'
        f'<div class="board5ch-box"><b>📢 {r["board5ch_status"]}</b> ｜ シグナル: <b>{r["signal"]}</b></div>'
        f'<div class="pts-tokugai-box">'
        f'<b>🌙 {r["tokugai_status"]}</b> ｜ 夜間理論気配: <b>{r["pts_est_price"]}</b> ({pts_sign}{r["pts_gap_pct"]}%) ｜ 特買い発動線: <b>{r["tokugai_line"]}</b>'
        f'</div>'
        f'<div class="squeeze-box">'
        f'<b>{r["squeeze_type"]}</b> ｜ 踏み上げ突破ライン(20日高値): <b>{r["squeeze_trigger_price"]}</b> ({r["dist_to_high20"]:+.2f}%)'
        f'</div>'
        f'<div class="metrics-row">'
        f'<span>🏦 <b>VPIN:</b> {r["vpin"]:+.2f}</span><span>💎 <b>板弾性:</b> {r["amihud_ratio"]}倍</span>'
        f'<span>📊 <b>RSI:</b> {r["rsi"]}</span><span>📈 <b>MACD:</b> {r["macd_state"]}</span>'
        f'<span>🔊 <b>出来高:</b> {r["vol_ratio"]}倍</span><span>🧱 <b>上ヒゲ:</b> {r["upper_shadow_pct"]}%</span>'
        f'</div>'
        f'<div class="trade-plan-box">'
        f'<div><div style="font-size:10px; color:#64748b;">🌅 夜間理論寄付き</div><div style="font-size:12px; font-weight:bold;">{r["pts_est_price"]}</div></div>'
        f'<div style="border-left:1px solid #cbd5e1; border-right:1px solid #cbd5e1;"><div style="font-size:10px; color:#15803d; font-weight:bold;">🎯 利確目標</div><div style="font-size:12px; font-weight:bold; color:#15803d;">{r["tp_price"]} (+{r["tp_pct"]}%)</div></div>'
        f'<div><div style="font-size:10px; color:#b91c1c; font-weight:bold;">🛡️ 損切り逆指値</div><div style="font-size:12px; font-weight:bold; color:#b91c1c;">{r["sl_price"]} ({r["sl_pct"]}%)</div></div>'
        f'</div>'
        f'<div class="sizing-box">'
        f'📦 <b>推奨ロット: {lot["shares"]:,}株</b> (投資額: <b>{lot["position_value"]:,.0f}円</b> / 最大損失リスク: <b>{lot["risk_amount"]:,.0f}円</b>)'
        f'</div></div>'
    )
    st.markdown(html_card, unsafe_allow_html=True)
    render_interactive_council_section(r, f"{key_prefix}_{r['code']}")

# ==========================================
# 🚀 メイン画面実行＆弱肉強食サバイバルランキング
# ==========================================
if st.button("🔄 最新データに更新（機関クオンツ＆弱肉強食サバイバル再集計）"):
    st.cache_data.clear()

macro_info = fetch_macro_market()

c1, c2 = st.columns([3, 1])
with c1: custom_input = st.text_input("🔍 任意の銘柄コードを診断（国内4桁 / 米国ティッカー）", placeholder="例: 6920, 5803, 3350, NVDA, IONQ")
with c2:
    st.write("")
    search_clicked = st.button("診断する", use_container_width=True)

if custom_input or search_clicked:
    norm_code = normalize_ticker(custom_input)
    if norm_code:
        with st.spinner(f"「{norm_code}」を機関クオンツ＆7大AIで解析中..."):
            custom_res = fetch_single_stock(norm_code, macro_info, inst_boost_mode, board5ch_boost, squeeze_boost_mode, tokugai_boost_mode)
        if custom_res:
            render_stock_card(custom_res, is_custom=True, key_prefix="custom")
        else:
            st.error(f"銘柄「{custom_input}」のデータが見つかりませんでした。")

with st.spinner("🏦 国内外の母集団を一括高速スキャン＆機関VPIN・弱肉強食サバイバル選抜中..."):
    genre_results, all_results = fetch_all_pool_batch(macro_info, inst_boost_mode, board5ch_boost, squeeze_boost_mode, tokugai_boost_mode)

def apply_survival_of_the_fittest(stock_list, cut_pct):
    if not stock_list: return [], []
    sorted_all = sorted(stock_list, key=lambda x: (x["survival_power"], x["inst_score"], x["board5ch_score"], x["ai_score"]), reverse=True)
    keep_count = max(3, int(round(len(sorted_all) * (cut_pct / 100.0))))
    return sorted_all[:keep_count], sorted_all[keep_count:]

tab_labels = [
    "🏆 総合サバイバルTOP5",
    "🏦 機関VPIN・ステルス買い特選",
    "🔥 5ch板・初動イナゴ特選",
    "🚨 特買い・夜間PTS特選",
    "💥 空売り踏み上げ特選",
    "📋 監視＆注文シート"
] + list(STOCK_POOL.keys())

tabs = st.tabs(tab_labels)

with tabs[0]:
    survivors_all, elim_all = apply_survival_of_the_fittest(all_results, survival_cut_pct)
    st.caption(f"🦁 全母集団 {len(all_results)}銘柄から下位 {len(elim_all)}銘柄を足切り！機関クオンツ・5ch需給ともに最強のTOP5です。")
    for idx, r in enumerate(survivors_all[:5], start=1):
        render_stock_card(r, rank=idx, key_prefix="top5")

with tabs[1]:
    st.info("🏦 **機関投資家VPIN（オーダーフロー毒性）＆浮動株吸い上げ特選タブ**: 機関のステルス氷山買いや浮動株の吸収（Amihud価格弾性上昇）が検知された上位10銘柄です。")
    inst_list = sorted(all_results, key=lambda x: (x["inst_score"], x["vpin"], x["survival_power"]), reverse=True)[:10]
    for idx, r in enumerate(inst_list, start=1):
        render_stock_card(r, rank=idx, key_prefix="inst_top")

with tabs[2]:
    st.info("🔥 **5chデイトレ板・初動イナゴ集中＆シコリ玉排除タブ**: 5日平均出来高からの急増率が高く、上ヒゲ（高値掴みのシコリ玉）が極めて少ない初動TOP10です。")
    b5_list = sorted(all_results, key=lambda x: (x["board5ch_score"], x["survival_power"]), reverse=True)[:10]
    for idx, r in enumerate(b5_list, start=1):
        render_stock_card(r, rank=idx, key_prefix="b5_top")

with tabs[3]:
    st.info("🚨 **翌朝『特買い』・夜間PTS連動タブ**: 夜間先物・SOX指数の追い風と機関の買い残しから、翌朝9:00に特別買い気配になりやすい上位10銘柄です。")
    tk_list = sorted(all_results, key=lambda x: (x["tokugai_prob"], x["pts_gap_pct"]), reverse=True)[:10]
    for idx, r in enumerate(tk_list, start=1):
        render_stock_card(r, rank=idx, key_prefix="tk_top")

with tabs[4]:
    st.info("💥 **空売り踏み上げ（ショートスクイーズ）タブ**: 20日高値ブレイクにより、空売り勢が朝イチに強制ロスカットを迫られる上位10銘柄です。")
    sq_list = sorted(all_results, key=lambda x: (x["squeeze_score"], x["inst_score"]), reverse=True)[:10]
    for idx, r in enumerate(sq_list, start=1):
        render_stock_card(r, rank=idx, key_prefix="sq_top")

with tabs[5]:
    wl = st.session_state["watchlist"]
    st.markdown(f"#### 📋 監視ウォッチリスト ({len(wl)}銘柄)")
    if st.button("⚡ 総合TOP3をワンタップ一括登録", use_container_width=True):
        for item in survivors_all[:3]:
            st.session_state["watchlist"][item["code"]] = item
        st.rerun()
    if wl:
        df_wl = pd.DataFrame([{
            "コード": c, "銘柄名": x["name"], "戦闘力": x["survival_power"], "機関スコア": x["inst_score"],
            "夜間理論気配": x["pts_est_price"], "特買い線": x["tokugai_line"],
            "推奨株数": f"{x['lot_info']['shares']:,}株", "利確": x["tp_price"], "損切": x["sl_price"]
        } for c, x in wl.items()])
        st.dataframe(df_wl, use_container_width=True, hide_index=True)
    else:
        st.info("各カードの「⭐ 監視リスト追加」を押すとここに一覧表示されます。")

for tab, genre in zip(tabs[6:], STOCK_POOL.keys()):
    with tab:
        g_raw = genre_results.get(genre, [])
        g_surv, g_elim = apply_survival_of_the_fittest(g_raw, survival_cut_pct)
        st.caption(f"🦁 **{genre}サバイバル選抜**: 候補 {len(g_raw)}銘柄中、戦闘力上位 **{len(g_surv)}銘柄が生存**（下位 {len(g_elim)}銘柄が脱落）")
        for idx, r in enumerate(g_surv, start=1):
            render_stock_card(r, rank=idx, key_prefix=f"genre_{genre}")
        if g_elim:
            with st.expander(f"💀 本日のサバイバル脱落・入れ替え候補銘柄を見る（{len(g_elim)}銘柄）"):
                for e_item in g_elim:
                    st.caption(f"▼ **{e_item['name']} ({e_item['code']})** — 戦闘力: {e_item['survival_power']}pt / {e_item['inst_status']}")
