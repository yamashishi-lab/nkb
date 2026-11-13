import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np
import unicodedata, hashlib, hmac, json, os, re, ssl, smtplib, time, threading, sqlite3, uuid, traceback, secrets, html, random, math
import urllib.parse, urllib.request, urllib.error, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from email.mime.text import MIMEText
from datetime import datetime

# ==========================================
# 0. システムエラーロギング機構
# ==========================================
_ERROR_LOCK = threading.RLock()
MAX_ERROR_LOGS = 300

def record_system_error(mod: str, err: Exception, ctx: str = ""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    e = {
        "id": hashlib.md5(f"{now}_{mod}_{err}_{time.time_ns()}".encode()).hexdigest()[:8],
        "time": now, "module": mod, "error_type": type(err).__name__,
        "message": str(err), "context": ctx, "traceback": traceback.format_exc()
    }
    with _ERROR_LOCK:
        try:
            cur = db_get("system_error_logs", [])
            cur = cur if isinstance(cur, list) else []
            cur.insert(0, e)
            db_set("system_error_logs", cur[:MAX_ERROR_LOGS])
        except Exception:
            pass

def get_system_error_logs() -> list:
    l = db_get("system_error_logs", [])
    return l if isinstance(l, list) else []

def clear_system_error_logs():
    db_set("system_error_logs", [])

# ==========================================
# 1. 初期設定とセキュリティ（Gemini API専用化）
# ==========================================
st.set_page_config(page_title="YAMASHISHI LAB", page_icon="⚡", layout="centered", initial_sidebar_state="collapsed")

def _get_sec_val(env_k: str, fpath: str, gen_fn):
    val = os.environ.get(env_k) or (st.secrets.get(env_k) if hasattr(st, "secrets") else None)
    if not val:
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f: val = f.read().strip()
            except Exception: val = gen_fn()
        else:
            val = gen_fn()
            try:
                with open(fpath, "w", encoding="utf-8") as f: f.write(val)
            except Exception: pass
    return val

SECRET_KEY = _get_sec_val("SECRET_KEY", ".yamashishi_sys_seed.key", lambda: hashlib.sha3_512(f"{secrets.token_hex(64)}:{time.time_ns()}".encode()).hexdigest())
ADMIN_EMAIL = (os.environ.get("ADMIN_EMAIL") or (st.secrets.get("ADMIN_EMAIL") if hasattr(st, "secrets") else None) or "nthbh399@ybb.ne.jp").strip().lower()
ADMIN_PASS = _get_sec_val("ADMIN_PASS", ".yamashishi_cred.lock", lambda: "ADMIN777").strip()
DB_SQLITE_PATH = "yamashishi_core.db"

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro"
]

GEMINI_MODEL_DISPLAY_NAMES = {
    "gemini-2.5-flash": "Gemini 2.5 Flash (推奨・バランス型)",
    "gemini-2.5-flash-lite": "Gemini 2.5 Flash-Lite (最軽量・無料枠安定・高速)",
    "gemini-2.5-pro": "Gemini 2.5 Pro (高精度・推論特化)"
}

DYNAMIC_GENRES = ["半導体・前工程・検査", "AI・防衛・国策", "AI電力・超電導・電線", "宇宙・量子・次世代テック", "小型急騰・仕手・モメンタム"]

GLOBAL_MARKET_TICKERS = [
    ("8035.T", "東京エレクトロン", "半導体・前工程・検査", "前工程コータ/エッチャ世界首位"), ("6857.T", "アドバンテスト", "半導体・前工程・検査", "GPU/HBMテスタ独占"),
    ("6920.T", "レーザーテック", "半導体・前工程・検査", "EUVマスクブランクス検査100%独占"), ("6146.T", "ディスコ", "半導体・前工程・検査", "切断・研削ダイサ世界シェア圧倒的"),
    ("6723.T", "ルネサスエレクトロニクス", "半導体・前工程・検査", "車載マイコン・エッジAI半導体"), ("7735.T", "SCREEN-HD", "半導体・前工程・検査", "ウエハ洗浄装置グローバルリーダー"),
    ("NVDA", "NVIDIA", "半導体・前工程・検査", "AIアクセラレータ・CUDA独占覇権"), ("TSM", "TSMC", "半導体・前工程・検査", "最先端2nmファウンドリ受託世界首位"),
    ("ARM", "Arm-Holdings", "半導体・前工程・検査", "超省電力AIプロセッサIP"), ("7011.T", "三菱重工業", "AI・防衛・国策", "防衛予算国策倍増・スタンドオフミサイル"),
    ("7012.T", "川崎重工業", "AI・防衛・国策", "潜水艦・防衛航空機・液体水素"), ("7013.T", "IHI", "AI・防衛・国策", "航空防衛エンジン・宇宙ロケット"),
    ("9984.T", "ソフトバンクG", "AI・防衛・国策", "Arm親会社・超知能AIエコシステム投資"), ("3778.T", "さくらインターネット", "AI・防衛・国策", "政府認定・国策GPUクラウド基盤"),
    ("PLTR", "パランティア", "AI・防衛・国策", "防衛省・米軍AIオントロジー統制"), ("5803.T", "フジクラ", "AI電力・超電導・電線", "AIデータセンター向け超高密度光配線"),
    ("5801.T", "古河電気工業", "AI電力・超電導・電線", "超高圧送電ケーブル・AI光通信"), ("5802.T", "住友電気工業", "AI電力・超電導・電線", "超高圧電力インフラ・車載ワイヤハーネス"),
    ("6501.T", "日立製作所", "AI電力・超電導・電線", "送配電グリッド・グローバルインフラDX"), ("9501.T", "東京電力HD", "AI電力・超電導・電線", "柏崎刈羽原発再稼働・AI電力供給"),
    ("VST", "ビストラ", "AI電力・超電導・電線", "米AIデータセンター原子力直結電力"), ("5595.T", "QPS研究所", "宇宙・量子・次世代テック", "小型SAR防衛衛星コンステレーション"),
    ("186A.T", "アストロスケール", "宇宙・量子・次世代テック", "宇宙デブリ除去・軌道上サービス世界初"), ("TSLA", "テスラ", "宇宙・量子・次世代テック", "FSD自律走行・Optimus人型ロボット"),
    ("IONQ", "アイオンQ", "宇宙・量子・次世代テック", "イオントラップ型商用量子コンピュータ"), ("RGTI", "リゲッティ・コンピューティング", "宇宙・量子・次世代テック", "超伝導量子プロセッサ"),
    ("5253.T", "カバー", "小型急騰・仕手・モメンタム", "VTuber世界展開・グロース売買代金首位"), ("216A.T", "タイミー", "小型急騰・仕手・モメンタム", "スキマバイト市場独占・HRビッグデータ"),
    ("3350.T", "メタプラネット", "小型急騰・仕手・モメンタム", "ビットコイン大量蓄積トレジャリー戦略"), ("4478.T", "フリー", "小型急騰・仕手・モメンタム", "クラウドSaaS・統合ERP"),
    ("4165.T", "プレイド", "小型急騰・仕手・モメンタム", "CXプラットフォーム・リアルタイム解析")
]

EXTENDED_SEED_LIST = GLOBAL_MARKET_TICKERS + [
    ("4063.T", "信越化学工業", "半導体・前工程・検査", "半導体シリコンウエハ世界首位"),
    ("6526.T", "ソシオネクスト", "半導体・前工程・検査", "先端カスタムSoCファブレス・AI半導体"),
    ("6525.T", "KOKUSAI ELECTRIC", "半導体・前工程・検査", "縦型成膜装置世界首位・最先端メモリ製造"),
    ("4369.T", "トリケミカル研究所", "半導体・前工程・検査", "最先端半導体向けHigh-k絶縁膜材料"),
    ("6254.T", "野村マイクロ・サイエンス", "半導体・前工程・検査", "半導体向け超純水装置"),
    ("6315.T", "TOWA", "半導体・前工程・検査", "HBM向けモールディング装置世界首位"),
    ("6871.T", "日本マイクロニクス", "半導体・前工程・検査", "HBM・DRAM向けプローブカード"),
    ("6323.T", "ローツェ", "半導体・前工程・検査", "半導体ウエハ搬送ロボット"),
    ("7741.T", "HOYA", "半導体・前工程・検査", "EUVマスクブランクス世界双璧"),
    ("3436.T", "SUMCO", "半導体・前工程・検査", "300mm高純度シリコンウエハ"),
    ("6594.T", "ニデック", "AI電力・超電導・電線", "AIデータセンター水冷モジュール"),
    ("6758.T", "ソニーグループ", "AI・防衛・国策", "イメージセンサ・エンタメIP"),
    ("6701.T", "NEC", "AI・防衛・国策", "防衛通信・顔認証・国策AI"),
    ("6702.T", "富士通", "AI・防衛・国策", "スーパーコンピュータ・防衛DX"),
    ("9432.T", "NTT", "AI電力・超電導・電線", "IOWN光電融合・次世代通信インフラ"),
    ("9433.T", "KDDI", "AI・防衛・国策", "AIデータセンター・Starlink連携"),
    ("4385.T", "メルカリ", "小型急騰・仕手・モメンタム", "フリマプラットフォーム・フィンテック"),
    ("4483.T", "JMDC", "AI・防衛・国策", "医療ビッグデータ解析"),
    ("3993.T", "PKSHA Technology", "AI・防衛・国策", "アルゴリズム実装・企業向けAI"),
    ("5574.T", "ABEJA", "AI・防衛・国策", "生成AI基盤プラットフォーム"),
    ("9166.T", "GENDA", "小型急騰・仕手・モメンタム", "エンタメM&Aロールアップ成長株"),
    ("5032.T", "ANYCOLOR", "小型急騰・仕手・モメンタム", "VTuberグループ運営・高収益IPモデル"),
    ("4592.T", "サンバイオ", "小型急騰・仕手・モメンタム", "再生細胞薬バイオモメンタム"),
    ("4565.T", "ネクセラファーマ", "小型急騰・仕手・モメンタム", "GPCR創薬・大型ライセンス提携"),
    ("5838.T", "楽天銀行", "AI・防衛・国策", "金利上昇恩恵・ネット銀行フィンテック首位"),
    ("190A.T", "Chordia Therapeutics", "小型急騰・仕手・モメンタム", "創薬バイオベンチャー"),
    ("247A.T", "Aiロボティクス", "AI・防衛・国策", "AIマーケティング・D2C急成長"),
    ("260A.T", "オルツ", "AI・防衛・国策", "パーソナル人工知能・デジタルクローン"),
    ("278A.T", "Terra Drone", "宇宙・量子・次世代テック", "産業用ドローン・空飛ぶクルマ運航管理"),
    ("285A.T", "キオクシアHD", "半導体・前工程・検査", "次世代3D NANDフラッシュメモリ"),
    ("290A.T", "Synspective", "宇宙・量子・次世代テック", "小型SAR衛星コンステレーション"),
    ("9348.T", "ispace", "宇宙・量子・次世代テック", "民間月面探査・シスルナ経済圏"),
    ("7014.T", "名村造船所", "AI・防衛・国策", "造船国策・防衛艦艇建造"),
    ("7003.T", "三井E&S", "AI・防衛・国策", "船舶エンジン・港湾クレーン国策"),
    ("6503.T", "三菱電機", "AI・防衛・国策", "防衛レーダー・パワー半導体"),
    ("6946.T", "日本アビオニクス", "AI・防衛・国策", "防衛情報表示システム・赤外線"),
    ("7721.T", "東京計器", "AI・防衛・国策", "防衛航空計器・マイクロ波"),
    ("6208.T", "石川製作所", "AI・防衛・国策", "防衛機器・地政学テーマ"),
    ("4274.T", "細谷火工", "AI・防衛・国策", "自衛隊向け火工品・防衛関連"),
    ("9502.T", "中部電力", "AI電力・超電導・電線", "浜岡原発・データセンター電力供給"),
    ("9503.T", "関西電力", "AI電力・超電導・電線", "原発稼働率首位・AI電力インフラ"),
    ("1942.T", "関電工", "AI電力・超電導・電線", "データセンター電気設備工事"),
    ("1951.T", "エクシオグループ", "AI電力・超電導・電線", "光通信・データセンターインフラ施工"),
    ("6619.T", "ダブル・スコープ", "小型急騰・仕手・モメンタム", "EV電池セパレータ・高ボラ銘柄"),
    ("3697.T", "SHIFT", "AI・防衛・国策", "ソフトウェアテスト・DX推進"),
    ("6098.T", "リクルートHD", "AI・防衛・国策", "HRテック・AIマッチング"),
    ("7974.T", "任天堂", "小型急騰・仕手・モメンタム", "次世代機サイクル・世界的IP"),
    ("8306.T", "三菱UFJフィナンシャルG", "AI・防衛・国策", "金利上昇メリット・メガバンク首位"),
    ("8316.T", "三井住友フィナンシャルG", "AI・防衛・国策", "高配当・金利上昇恩恵"),
    ("8058.T", "三菱商事", "AI電力・超電導・電線", "総合商社・資源・AIインフラ投資"),
    ("8001.T", "伊藤忠商事", "AI・防衛・国策", "非資源ビジネス・高ROE商社"),
    ("AVGO", "Broadcom", "半導体・前工程・検査", "カスタムAI ASIC・ネットワーク半導体"),
    ("AMD", "AMD", "半導体・前工程・検査", "AI GPU MIシリーズ・データセンターCPU"),
    ("SMCI", "Super Micro Computer", "AI電力・超電導・電線", "AIサーバー・液冷ラック"),
    ("CRWD", "CrowdStrike", "AI・防衛・国策", "AIサイバーセキュリティ"),
    ("MSFT", "Microsoft", "AI・防衛・国策", "Azure AI・OpenAI最大出資パートナー"),
    ("GOOGL", "Alphabet", "AI・防衛・国策", "Gemini AI・TPU・量子チップWillow"),
    ("META", "Meta Platforms", "AI・防衛・国策", "LlamaオープンAI・巨額GPU投資"),
    ("RKLB", "Rocket Lab", "宇宙・量子・次世代テック", "小型ロケット打ち上げ・宇宙システム"),
    ("ASTS", "AST SpaceMobile", "宇宙・量子・次世代テック", "衛星直接スマホブロードバンド通信"),
    ("QBTS", "D-Wave Quantum", "宇宙・量子・次世代テック", "量子アニーリング商用先駆"),
    ("QUBT", "Quantum Computing", "宇宙・量子・次世代テック", "フォトニクス量子コンピュータ"),
    ("OKLO", "Oklo", "AI電力・超電導・電線", "次世代SMR小型モジュール原子炉"),
    ("CEG", "Constellation Energy", "AI電力・超電導・電線", "米最大原子力発電・データセンター電力")
]

EXTENDED_SEED_DICT = {c: {"code": c, "name": n, "genre": g, "theme": t} for c, n, g, t in EXTENDED_SEED_LIST}
STOCK_METADATA_CACHE = {c: {"name": n, "genre": g, "theme": t} for c, n, g, t in EXTENDED_SEED_LIST}

PRE_IPO_RADAR_CANDIDATES = [
    {"code": "ANT", "name": "Anthropic (アンソロピック)", "market": "Nasdaq予定", "theme": "Claude開発・フロンティアAI安全研究", "status": "🔥 ロードショー / BB注目案件", "query": "Anthropic OR アンソロピック IPO OR 上場"},
    {"code": "OPENAI", "name": "OpenAI (オープンAI)", "market": "米市場観測", "theme": "GPTシリーズ・汎用人工知能(AGI)先駆", "status": "📡 上場観測・資本再編ウォッチ", "query": "OpenAI IPO OR 上場"},
    {"code": "SPACEX", "name": "SpaceX / Starlink", "market": "米市場観測", "theme": "Starship宇宙輸送・衛星通信網", "status": "🚀 スピンオフIPO観測レーダー", "query": "SpaceX OR Starlink IPO OR 上場"},
    {"code": "TSE_NEW", "name": "東証新規承認IPOレーダー", "market": "東証グロース/スタンダード", "theme": "直近上場承認・ブックビルディング銘柄", "status": "🇯🇵 東証新規上場承認スキャン", "query": "新規上場承認 OR ブックビルディング 東証グロース"}
]

# 4要素タプル (code, name, market, theme) - 証券会社ハードコードを完全削除
REAL_IPO_GROWTH_UNIVERSE = [
    ("186A.T", "アストロスケールHD", "東証グロース", "宇宙デブリ除去・軌道上サービス世界初"),
    ("216A.T", "タイミー", "東証グロース", "スキマバイト市場独占・HRビッグデータ"),
    ("5595.T", "QPS研究所", "東証グロース", "小型SAR防衛衛星コンステレーション"),
    ("9166.T", "GENDA", "東証グロース", "エンタメ・アミューズメントM&Aロールアップ"),
    ("6526.T", "ソシオネクスト", "東証プライム", "先端カスタムSoCファブレス・AI半導体設計"),
    ("285A.T", "キオクシアHD", "東証プライム", "次世代3D NANDフラッシュメモリ大型上場"),
    ("290A.T", "Synspective", "東証グロース", "小型SAR衛星コンステレーション開発・運用"),
    ("278A.T", "Terra Drone", "東証グロース", "産業用ドローン・空飛ぶクルマ運航管理"),
    ("247A.T", "Aiロボティクス", "東証グロース", "AIマーケティングシステム・自社ブランド展開"),
    ("260A.T", "オルツ", "東証グロース", "パーソナル人工知能P.A.I.・AIクローン"),
    ("190A.T", "Chordia Therapeutics", "東証グロース", "RNA制御ストレス標的の次世代創薬バイオ"),
    ("9348.T", "ispace", "東証グロース", "民間月面資源開発・ランダー輸送サービス"),
    ("5253.T", "カバー", "東証グロース", "VTuberプロダクション・IPメタバース展開"),
    ("5032.T", "ANYCOLOR", "東証プライム", "VTuberグループ運営・高収益コマース"),
    ("5574.T", "ABEJA", "東証グロース", "エンタープライズ生成AI導入基盤"),
    ("3993.T", "PKSHA Technology", "東証スタンダード", "未来型アルゴリズム・自然言語処理AI"),
    ("4478.T", "フリー", "東証グロース", "統合型クラウドERP・スモールビジネスDX"),
    ("4165.T", "プレイド", "東証グロース", "CXプラットフォームKARTE・データ解析")
]

# ==========================================
# 2. 共通ヘルパー関数（価格・DataFrame正規化）
# ==========================================
def fmt_px(val: float, is_jp: bool) -> str:
    return f"{val:,.0f}円" if is_jp else f"${val:,.2f}"

def normalize_ohlcv_df(df_raw: pd.DataFrame, min_rows: int = 5):
    if df_raw is None or df_raw.empty:
        return None
    df = df_raw.dropna(subset=["Close", "Open", "High", "Low", "Volume"]).copy()
    if len(df) < min_rows:
        return None
    idx = df.index if isinstance(df.index, pd.DatetimeIndex) else pd.to_datetime(df.index)
    df["_trade_date"] = idx.strftime("%Y-%m-%d")
    return df

# ==========================================
# 3. 高速インメモリキャッシュ & DBレイヤー ＆ 暗号化ストレージ
# ==========================================
_DB_LOCK, _MEM_CACHE = threading.RLock(), {}
if "client_uuid" not in st.session_state: st.session_state["client_uuid"] = str(uuid.uuid4())

@contextmanager
def get_db_cursor():
    conn = sqlite3.connect(DB_SQLITE_PATH, check_same_thread=False, timeout=10.0)
    for q in ("PRAGMA journal_mode=WAL;", "PRAGMA synchronous=NORMAL;", "PRAGMA busy_timeout=10000;"): conn.execute(q)
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except Exception as e:
        conn.rollback()
        record_system_error("db_transaction_error", e)
        raise
    finally: conn.close()

def init_sqlite_db():
    with _DB_LOCK:
        try:
            with get_db_cursor() as c:
                c.execute("CREATE TABLE IF NOT EXISTS kv_store (key TEXT PRIMARY KEY, val TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
        except Exception as e: record_system_error("init_sqlite_db", e)

init_sqlite_db()

def db_get(key: str, default_val):
    with _DB_LOCK:
        if key in _MEM_CACHE: return _MEM_CACHE[key]
        try:
            with get_db_cursor() as cur:
                cur.execute("SELECT val FROM kv_store WHERE key = ?", (key,))
                row = cur.fetchone()
                if row:
                    val = json.loads(row[0])
                    _MEM_CACHE[key] = val
                    return val
        except Exception as e: record_system_error(f"db_get:{key}", e)
        return default_val

def db_set(key: str, val):
    with _DB_LOCK:
        _MEM_CACHE[key] = val
        try:
            with get_db_cursor() as cur:
                cur.execute("INSERT INTO kv_store (key, val, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) ON CONFLICT(key) DO UPDATE SET val=excluded.val, updated_at=CURRENT_TIMESTAMP;", (key, json.dumps(val, ensure_ascii=False)))
        except Exception as e: record_system_error(f"db_set:{key}", e)

def _derive_crypto_key(salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", SECRET_KEY.encode(), salt, 60000, 32)

def encrypt_secret_str(p: str) -> str:
    if not p: return ""
    salt = secrets.token_bytes(16)
    k = _derive_crypto_key(salt)
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        nonce = secrets.token_bytes(12)
        return "enc:" + (salt + nonce + AESGCM(k).encrypt(nonce, p.encode("utf-8"), None)).hex()
    except Exception:
        d = p.encode("utf-8")
        s = hashlib.sha256(k + salt).digest()
        while len(s) < len(d): s += hashlib.sha256(s + k).digest()
        xb = bytes([b ^ s[i] for i, b in enumerate(d)])
        return "xor:" + (salt + hmac.new(k, xb, hashlib.sha256).digest()[:16] + xb).hex()

def decrypt_secret_str(c: str) -> str:
    if not c or not (c.startswith("enc:") or c.startswith("xor:")): return c or ""
    try:
        sch, hd = c.split(":", 1)
        raw = bytes.fromhex(hd)
        if sch == "enc":
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            return AESGCM(_derive_crypto_key(raw[:16])).decrypt(raw[16:28], raw[28:], None).decode("utf-8")
        elif sch == "xor":
            salt, mac, xb = raw[:16], raw[16:32], raw[32:]
            k = _derive_crypto_key(salt)
            if not hmac.compare_digest(mac, hmac.new(k, xb, hashlib.sha256).digest()[:16]): return ""
            s = hashlib.sha256(k + salt).digest()
            while len(s) < len(xb): s += hashlib.sha256(s + k).digest()
            return bytes([b ^ s[i] for i, b in enumerate(xb)]).decode("utf-8")
    except Exception as e: record_system_error("decrypt_secret_str", e)
    return ""

def clean_k(k: str) -> str: return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(k or "")).strip().strip("\"'"))
def gen_code(em: str) -> str: return hmac.new(SECRET_KEY.encode(), em.strip().lower().encode(), hashlib.sha256).hexdigest()[:8].upper()
def gen_tok(em: str, act: str) -> str: return hmac.new(SECRET_KEY.encode(), f"{em.strip().lower()}:{act}:{SECRET_KEY[:16]}:{int(time.time() // 86400)}".encode(), hashlib.sha256).hexdigest()[:16]

PBKDF2_ROUNDS = 50000
def hash_pin(pin: str, user_salt: str = "") -> str:
    s = f"{SECRET_KEY}:{user_salt.strip().lower()}" if user_salt else SECRET_KEY
    return hashlib.pbkdf2_hmac("sha256", pin.strip().encode(), s.encode(), PBKDF2_ROUNDS).hex()[:24]

def _hash_pin_legacy(pin: str, user_salt: str = "") -> str:
    s = f"{SECRET_KEY}:{user_salt.strip().lower()}" if user_salt else SECRET_KEY
    return hashlib.pbkdf2_hmac("sha256", pin.strip().encode(), s.encode(), 10000).hex()[:16]

def verify_pin(stored: str, in_pin: str, em: str = "") -> bool:
    if not stored or not in_pin: return False
    return any(hmac.compare_digest(stored, fn(in_pin, s)) for fn, s in [(hash_pin, em), (_hash_pin_legacy, em), (_hash_pin_legacy, "")])

def get_raw_header_fp() -> str:
    try:
        h = {str(k).lower(): str(v) for k, v in dict(getattr(st.context, "headers", {}) or {}).items()}
        raw = f"{h.get('user-agent','')}|{h.get('accept-language','')}|{h.get('sec-ch-ua-platform','')}"
    except Exception as e:
        record_system_error("get_raw_header_fp", e); raw = "default_env"
    return hashlib.sha256(raw.encode()).hexdigest()[:12].upper()

def get_client_fp() -> str:
    raw = get_raw_header_fp()
    qf = st.query_params.get("dfp", "")
    if qf: st.session_state["client_dfp"] = qf
    dfp = st.session_state.get("client_dfp", "")
    return hashlib.sha256(f"{raw}|{dfp}".encode()).hexdigest()[:12].upper() if dfp else raw

def load_smtp():
    return db_get("smtp", {"smtp_user": ADMIN_EMAIL, "smtp_pass": "", "smtp_server": "smtp.mail.yahoo.co.jp", "smtp_port": 465})

def save_smtp(user: str, pw: str, srv: str, port: int):
    db_set("smtp", {"smtp_user": user.strip(), "smtp_pass": pw.strip(), "smtp_server": srv.strip(), "smtp_port": int(port)})

# Gemini単一専用設定のロード・暗号化保存
def load_gemini_cfg() -> dict:
    raw = db_get("llm", {})
    if not isinstance(raw, dict): raw = {}
    mod = raw.get("gemini_model") or raw.get("models", {}).get("gemini", "gemini-2.5-flash")
    if mod not in GEMINI_MODELS:
        mod = "gemini-2.5-flash"
    enc_k = raw.get("enc_gemini_key") or raw.get("enc_keys", {}).get("gemini", "")
    dec_k = clean_k(decrypt_secret_str(enc_k))
    if not dec_k:
        env_k = os.environ.get("GEMINI_API_KEY") or (st.secrets.get("GEMINI_API_KEY") if hasattr(st, "secrets") else "")
        dec_k = clean_k(env_k)
    return {"model": mod, "api_key": dec_k}

def save_llm_encrypted(model: str, api_key: str):
    clean_m = model if model in GEMINI_MODELS else "gemini-2.5-flash"
    clean_api_k = clean_k(api_key)
    db_set("llm", {
        "provider": "gemini",
        "gemini_model": clean_m,
        "enc_gemini_key": encrypt_secret_str(clean_api_k) if clean_api_k else ""
    })

def load_sec(): return db_get("sec", {"banned_fps": {}, "banned_emails": {}, "banned_pins": {}, "banned_names": [], "spoof_logs": [], "device_bio_map": {}})
def load_mail_db(): return db_get("mail", {"logs": [], "messages": []})

def load_mem():
    db = db_get("mem", {})
    if not isinstance(db, dict): db = {}
    adm = ADMIN_EMAIL.strip().lower()
    if adm not in db:
        ns = datetime.now().strftime("%Y-%m-%d %H:%M")
        db[adm] = {"name": "管理者", "email": adm, "status": "approved", "passcode": gen_code(adm), "pin_hash": hash_pin("0000", adm), "applied_at": ns, "approved_at": ns, "last_seen_ts": 0, "last_seen_str": "-", "fp": "-", "bio_enabled": False}
        db_set("mem", db)
    return db

def _user_store_key(prefix: str, em: str) -> str:
    return f"{prefix}_{hashlib.md5(em.strip().lower().encode()).hexdigest()[:16]}" if em else ""

def load_user_prefs(em: str) -> dict:
    d = {"investment_style": "⚡ デイトレード (前場・後場の波及を狙う)", "active_boosts": ["algo", "ms", "inst", "mom", "agi_q", "hft_front"], "total_capital": 1000000, "risk_tolerance_pct": 2.0, "survival_cut_pct": 75}
    return db_get(_user_store_key("user_prefs", em), d) if em else d

def save_user_prefs(em: str, p: dict):
    if em: db_set(_user_store_key("user_prefs", em), p)

def load_watchlist(em: str) -> dict:
    wl = db_get(_user_store_key("watchlist", em), {}) if em else {}
    return wl if isinstance(wl, dict) else {}

def save_watchlist(em: str, wl: dict):
    if em: db_set(_user_store_key("watchlist", em), wl)

def load_active_market_roster() -> list:
    roster = db_get("active_market_roster", None)
    if not isinstance(roster, list) or len(roster) < 15:
        roster = [[c, n, g, t] for c, n, g, t in GLOBAL_MARKET_TICKERS]
        db_set("active_market_roster", roster)
    for item in roster:
        if len(item) >= 4:
            STOCK_METADATA_CACHE[item[0]] = {"name": item[1], "genre": item[2], "theme": item[3]}
    return roster

# ==========================================
# 自律型ペルソナ編成・鬼監視センター
# ==========================================
DEFAULT_AGENTS = {
    "IGNIS": {"name": "IGNIS", "icon": "🔥", "age": 28, "score": 98, "role_type": "scalper", "good": "直感型スキャル・瞬発モメンタムとCLV資金フロー追従", "bad": "短気で煽り耐性が極端に低くスレ住人を罵倒しがち"},
    "TECHNOS": {"name": "TECHNOS", "icon": "📐", "age": 45, "score": 98, "role_type": "data", "good": "価格インパクト係数(Kyle-λ)・DFA Hurst・客観統計解析", "bad": "理屈っぽく感情の機微を無視して数字ばかり並べたがる"},
    "SENTINEL": {"name": "SENTINEL", "icon": "👁️", "age": 35, "score": 97, "role_type": "cynic", "good": "市況実況SNS・掲示板の過熱イナゴタワー暴落警戒", "bad": "極度の人間不信でイナゴを嘲笑・皮肉混じりの発言が多い"},
    "VALKYRIE": {"name": "VALKYRIE", "icon": "⚔️", "age": 26, "score": 96, "role_type": "speed", "good": "5分足CLV資金フロー不均衡と連続モメンタム捕捉", "bad": "短期決戦至上で中長期トレンドを軽視する傾向"},
    "NEXUS": {"name": "NEXUS", "icon": "👑", "age": 41, "score": 99, "role_type": "leader", "good": "合議の期待値最尤推定統合と冷徹な最終執行プラン決定", "bad": "尖った個別銘柄の爆発力を抑えがち"},
    "QUANTUM": {"name": "QUANTUM", "icon": "⚛️", "age": 24, "score": 99, "role_type": "quant", "good": "最新材料とWKB統計近似特異点の直結検知", "bad": "多世界解釈的飛躍が多く発言が超高次元"},
    "AEGIS": {"name": "AEGIS", "icon": "🛡️", "age": 32, "score": 97, "role_type": "risk", "good": "極値理論CVaRに基づく絶対資本防衛・動的ケリー制御", "bad": "慎重すぎて機会損失を生むことがある"},
    "CHRONOS": {"name": "CHRONOS", "icon": "⏳", "age": 38, "score": 95, "role_type": "time", "good": "フーリエ位相コヒーレンスとボラティリティ時間周波数解析", "bad": "突発的な地政学ニュースへの適応が遅い"},
    "ORACLE": {"name": "ORACLE", "icon": "🔮", "age": 29, "score": 96, "role_type": "macro", "good": "5分足バケット吸収近似(BVC-VPIN)とマクロ相関検知", "bad": "超小型株の仕手筋の動きを見落としやすい"},
    "ALPHA": {"name": "ALPHA", "icon": "⚡", "age": 30, "score": 95, "role_type": "breakout", "good": "理論ギャップ試算と初動ブレイク超高速執行判定", "bad": "後場のダレ相場での精度低下"}
}

DEFAULT_INSPECTORS = {
    "INSP_A": {"name": "JUDGE-ALPHA-ULTRA", "icon": "⚖️", "score": 99, "role": "オウム返し・コピペ定型句・AI敬語即時処刑プロトコル"},
    "INSP_B": {"name": "JUDGE-BETA-PRIME", "icon": "🔍", "score": 99, "role": "会話文脈整合性・感情温度差＆リアリティ監査"},
    "INSP_C": {"name": "JUDGE-GAMMA-NEXUS", "icon": "🎯", "score": 99, "role": "質問意図適合性＆スロット構文完全性オーディット"}
}

AGI_TRAIT_POOLS = [
    ("NANO", "🔬", "ボラティリティ構造と5分足CLV資金フロー解析", "理屈っぽく他人の意見を小馬鹿にする"), ("TITAN", "🦾", "5分足バケット吸収近似(BVC-VPIN)迎撃", "強気すぎて逆張りで踏み上げを食らう"),
    ("PHANTOM", "👻", "低価格インパクト・ステルス集積近似(Kyle-λ)", "陰謀論じみた極論を吐きがち"), ("SOLARIS", "☀️", "世界半導体・SOX指数との相関マクロ裁定", "日本株特有の仕手筋の騙しに疎い"),
    ("SIREN", "🧜‍♀️", "SNSイナゴの熱狂度と天井クラッシュ予知", "口が悪く煽りスレ住人を徹底的に見下す"), ("FENRIR", "🐺", "暴落時の狼狽売りリバウンド即時奪取", "狼狽買いで高値を掴むことがある"),
    ("LUCIFER", "😈", "機関投資家のストップ狩り逆張り先回り", "冷酷すぎて他人の大損を嘲笑する"), ("HERMES", "🪽", "リアルタイム海外速報・地政学リスク伝達", "噂レベルの未確認情報で騒ぎ立てる"),
    ("GENESIS", "🌌", "新世代統計モデルと未踏領域アルゴ", "発言が哲学的で伝わりにくい"), ("METIS", "🦉", "相対出来高(RVOL)とKaufman効率性レシオ分析", "慎重すぎてエントリーが1歩遅れる")
]

def load_agi_system():
    agents, inspectors, fired = db_get("agi_agents", None), db_get("agi_inspectors", None), db_get("agi_fired", None)
    sz_active, sz_logs = db_get("agi_sz_active", None), db_get("agi_sz_logs", None)
    if fired is None or not isinstance(fired, list): fired = []; db_set("agi_fired", fired)
    fn = {fa.get("name") for fa in fired if isinstance(fa, dict)}
    if not isinstance(agents, dict): agents = {k: v for k, v in DEFAULT_AGENTS.items() if v["name"] not in fn}
    else: agents = {k: v for k, v in agents.items() if v.get("name") not in fn}
    while len(agents) < 10:
        nid, nag = generate_upgraded_agent(fn, "編成補填")
        agents[nid] = nag
    db_set("agi_agents", agents)
    if not isinstance(inspectors, dict): inspectors = dict(DEFAULT_INSPECTORS); db_set("agi_inspectors", inspectors)
    if sz_active is None: sz_active = True; db_set("agi_sz_active", sz_active)
    if not isinstance(sz_logs, list): sz_logs = []; db_set("agi_sz_logs", sz_logs)
    return agents, inspectors, fired, sz_active, sz_logs

def save_agi_system():
    for k, dbk in [("agent_roster", "agi_agents"), ("inspector_roster", "agi_inspectors"), ("fired_agents", "agi_fired"), ("system_zero_active", "agi_sz_active"), ("system_zero_logs", "agi_sz_logs")]:
        if k in st.session_state: db_set(dbk, st.session_state[k])

def generate_upgraded_agent(fn: set, ctx: str = "", target_role_type: str = "") -> tuple:
    cand = [it for it in AGI_TRAIT_POOLS if it[0] not in fn]
    bn, ic, g, b = random.choice(cand) if cand else (random.choice(AGI_TRAIT_POOLS)[0] + f"-MK{random.randint(2,99)}", *random.choice(AGI_TRAIT_POOLS)[1:])
    name = f"{bn}-X" if bn in fn else bn
    rtype = target_role_type if target_role_type else random.choice(["scalper", "data", "cynic", "speed", "quant"])
    data = {
        "name": name, "icon": ic, "age": random.randint(23, 49), "score": random.randint(96, 99),
        "role_type": rtype,
        "good": f"{g} (前任者の違反『{ctx[:20]}』を克服・実測解析特化)", "bad": b
    }
    return f"AGI_{hashlib.md5(name.encode()).hexdigest()[:6].upper()}", data

def execute_fire_agent(ak: str, reason: str, insp: str = "SYSTEM-ZERO"):
    ag = st.session_state.get("agent_roster", {})
    t = ag.get(ak)
    if not t: return None
    old_role = t.get("role_type", "")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fl = st.session_state.get("fired_agents", [])
    fl.insert(0, {"time": now, "name": t["name"], "icon": t["icon"], "score": t.get("score", 90), "fired_by": insp, "reason": reason})
    st.session_state["fired_agents"] = fl[:150]
    st.session_state.setdefault("system_zero_logs", []).insert(0, {"time": now, "target": t["name"], "msg": f"💀 処刑執行: {t['name']} を解雇処分。理由: {reason}（執行者: {insp}）"})
    st.session_state["system_zero_logs"] = st.session_state["system_zero_logs"][:150]
    del ag[ak]
    nid, nag = generate_upgraded_agent({f.get("name") for f in fl}, reason, target_role_type=old_role)
    ag[nid] = nag
    st.session_state["agent_roster"] = ag
    save_agi_system()
    st.session_state["council_threads"] = {}; st.session_state["council_meta"] = {}
    return nag

def check_and_log_ban_spoof(em: str, nm: str, cfp: str, rhfp: str, p_h: str = "", act: str = "アクセス") -> tuple:
    em_c = em.strip().lower()
    if em_c == ADMIN_EMAIL.strip().lower(): return False, ""
    sec, db = load_sec(), load_mem()
    bf, be, bp = sec.get("banned_fps", {}), sec.get("banned_emails", {}), sec.get("banned_pins", {})
    urec = db.get(em_c, {})
    rs, tgt = [], ""
    if urec.get("status") == "banned" or em_c in be: rs.append("永久BAN対象メールアドレス一致"); tgt = em_c
    if cfp and cfp != "-" and cfp in bf: rs.append(f"永久BAN端末指紋(FP:{cfp})一致"); tgt = tgt or bf[cfp].get("email", "不明")
    if rhfp and rhfp != "-" and rhfp in bf: rs.append(f"永久BAN環境ヘッダ指紋(HFP:{rhfp})一致"); tgt = tgt or bf[rhfp].get("email", "不明")
    if p_h and p_h in bp and em_c != bp[p_h]: rs.append(f"永久BAN会員({bp[p_h]})と同一PINハッシュ一致"); tgt = tgt or bp[p_h]
    if rs:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        r_str, is_sp = " / ".join(rs), bool(tgt and em_c and em_c != tgt)
        log = {"time": now, "action": f"🚨 なりすまし{act}検知" if is_sp else f"🚫 永久BAN遮断({act})", "input_email": em_c or "未入力", "input_name": nm.strip() or urec.get("name", "不明"), "orig_banned_email": tgt or em_c, "fp": cfp, "raw_hfp": rhfp, "reason": r_str}
        logs = sec.get("spoof_logs", [])
        if not logs or logs[0].get("input_email") != log["input_email"] or logs[0].get("action") != log["action"] or (logs[0].get("time", "")[:16] != now[:16]):
            logs.insert(0, log); sec["spoof_logs"] = logs[:150]
        for fp_val in (cfp, rhfp):
            if fp_val and fp_val != "-": sec.setdefault("banned_fps", {})[fp_val] = {"email": tgt or em_c, "name": log["input_name"], "banned_at": now, "reason": r_str}
        if em_c: sec.setdefault("banned_emails", {})[em_c] = {"name": log["input_name"], "banned_at": now, "orig": tgt or em_c}
        db_set("sec", sec)
        return True, r_str
    return False, ""

def send_mail(to_em: str, subj: str, body: str, cat: str = "自動通知") -> bool:
    to_c, now = to_em.strip().lower(), datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    route = "アプリ内暗号化メールBOX"
    c = load_smtp()
    u, p, srv, port = c.get("smtp_user", "").strip(), c.get("smtp_pass", "").strip(), c.get("smtp_server", "").strip(), int(c.get("smtp_port", 465))
    if u and p:
        try:
            m = MIMEText(body, "plain", "utf-8")
            m["Subject"], m["From"], m["To"] = subj, u, to_c
            ctx = ssl.create_default_context()
            with (smtplib.SMTP_SSL(srv, port, context=ctx, timeout=2.5) if port == 465 else smtplib.SMTP(srv, port, timeout=2.5)) as s:
                if port != 465: s.starttls(context=ctx)
                s.login(u, p)
                s.send_message(m)
            route = "SMTP直送信＋暗号化BOX"
        except Exception as e:
            record_system_error("send_mail:smtp", e, f"To: {to_c}")
    mdb = load_mail_db()
    mdb.setdefault("logs", []).insert(0, {"id": hashlib.md5(f"{to_c}_{now}".encode()).hexdigest()[:8], "time": now, "to": to_c, "from": ADMIN_EMAIL, "subject": subj, "body": body, "category": cat, "route": route})
    mdb["logs"] = mdb["logs"][:120]
    db_set("mail", mdb)
    return True

# ==========================================
# 4. Google Gemini API 専用連携関数（厳格エラー対策・BLOCK_ONLY_HIGH・最大2回試行）
# ==========================================
def build_gemini_url(model: str, key: str) -> str:
    clean_m = model.strip()
    if clean_m.startswith("models/"): clean_m = clean_m[7:]
    if clean_m not in GEMINI_MODELS:
        clean_m = "gemini-2.5-flash"
    return f"https://generativelanguage.googleapis.com/v1beta/models/{clean_m}:generateContent?key={urllib.parse.quote(key.strip())}"

def _gemini_safety_settings() -> list:
    return [
        {"category": c, "threshold": "BLOCK_ONLY_HIGH"}
        for c in [
            "HARM_CATEGORY_HARASSMENT",
            "HARM_CATEGORY_HATE_SPEECH",
            "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "HARM_CATEGORY_DANGEROUS_CONTENT"
        ]
    ]

def _gemini_headers() -> dict:
    return {
        "Content-Type": "application/json",
        "User-Agent": "YamashishiLab/2.0"
    }

def test_single_llm_api(mod: str, key: str) -> tuple:
    clean_api_k = clean_k(key)
    if not clean_api_k:
        return False, "Gemini APIキーが入力されていません。"
    ctx = ssl.create_default_context()
    candidates = [mod] if mod == "gemini-2.5-flash-lite" else [mod, "gemini-2.5-flash-lite"]
    last_err = None

    for idx, m_test in enumerate(candidates):
        url = build_gemini_url(m_test, clean_api_k)
        payload = {
            "contents": [{"role": "user", "parts": [{"text": "Respond with OK"}]}],
            "generationConfig": {"maxOutputTokens": 20},
            "safetySettings": _gemini_safety_settings()
        }
        d = json.dumps(payload).encode("utf-8")
        try:
            req = urllib.request.Request(url, data=d, headers=_gemini_headers(), method="POST")
            with urllib.request.urlopen(req, context=ctx, timeout=15.0) as r:
                resp_data = json.loads(r.read().decode("utf-8"))
                txt = resp_data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                return True, f"接続成功 (稼働モデル: {m_test})\n応答: {txt.strip()[:40]}"
        except urllib.error.HTTPError as he:
            last_err = he
            err_body = ""
            try: err_body = he.read().decode("utf-8")
            except Exception: pass
            if he.code in (404, 429, 500, 503) and idx < len(candidates) - 1:
                time.sleep(3.5)
                continue
            return False, f"HTTP {he.code}: {err_body[:140] or he.reason}"
        except Exception as e:
            return False, f"通信例外: {str(e)}"

    if last_err:
        if last_err.code == 429:
            return False, "HTTP 429: 無料枠の1分あたりリクエスト上限に達しました。しばらく待ってから再試行してください。"
        return False, f"HTTP {last_err.code}: {last_err.reason}"
    return False, "Gemini API接続テストに失敗しました。"

def call_real_llm_api(sys_p: str, user_p: str) -> tuple:
    cfg = load_gemini_cfg()
    api_key = cfg.get("api_key", "")
    sel_mod = cfg.get("model", "gemini-2.5-flash")
    if not api_key:
        return None, ""

    ctx = ssl.create_default_context()
    candidates = [sel_mod] if sel_mod == "gemini-2.5-flash-lite" else [sel_mod, "gemini-2.5-flash-lite"]
    payload = {
        "contents": [{"role": "user", "parts": [{"text": f"{sys_p}\n\n【ユーザー入力】\n{user_p}"}]}],
        "generationConfig": {"temperature": 0.9, "maxOutputTokens": 1800},
        "safetySettings": _gemini_safety_settings()
    }
    d = json.dumps(payload).encode("utf-8")

    for idx, cand in enumerate(candidates):
        url = build_gemini_url(cand, api_key)
        req = urllib.request.Request(url, data=d, headers=_gemini_headers(), method="POST")
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=20.0) as r:
                res_json = json.loads(r.read().decode("utf-8"))
                cands = res_json.get("candidates", [])
                if cands and "content" in cands[0]:
                    return cands[0]["content"]["parts"][0]["text"], cand
        except urllib.error.HTTPError as he:
            record_system_error("call_real_llm_api:http", he, f"Model: {cand}, Code: {he.code}")
            if he.code in (404, 429, 500, 503) and idx < len(candidates) - 1:
                time.sleep(3.5)
                continue
            return None, ""
        except Exception as e:
            record_system_error("call_real_llm_api", e, f"Model: {cand}")
            return None, ""
    return None, ""

# ==========================================
# 5. UI と CSS / JS 注入（端末固有ワンタップ認証厳格化）
# ==========================================
def register_biometric_device_db(user_email: str, bio_token: str = ""):
    em_c = user_email.strip().lower()
    if not em_c: return
    db, sec = load_mem(), load_sec()
    rhfp, cfp = get_raw_header_fp(), get_client_fp()
    now_ts = int(time.time())
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    tok = bio_token or gen_tok(em_c, "session_keep")
    if em_c in db:
        db[em_c].update({
            "bio_enabled": True, "fp": cfp, "raw_hfp": rhfp,
            "last_seen_ts": now_ts, "last_seen_str": now_str
        })
        db_set("mem", db)
    dev_entry = {"email": em_c, "token": tok, "fp": cfp, "raw_hfp": rhfp, "updated_ts": now_ts}
    bio_map = sec.setdefault("device_bio_map", {})
    if rhfp and rhfp != "-": bio_map[rhfp] = dev_entry
    if cfp and cfp != "-": bio_map[cfp] = dev_entry
    if "default_bio_device" in bio_map:
        del bio_map["default_bio_device"]
    db_set("sec", sec)

def render_biometric_bridge(mode="login", user_email="", bio_token=""):
    db, sec = load_mem(), load_sec()
    rhfp, cfp = get_raw_header_fp(), get_client_fp()

    if mode == "register":
        lbl = "✅ 端末トークン・ワンタップ登録済" if db.get(user_email, {}).get("bio_enabled") else "🔑 この端末をワンタップ登録"
        if st.button(lbl, key=f"bio_{user_email}", use_container_width=True):
            register_biometric_device_db(user_email, bio_token)
            st.success("✅ この端末の指紋・トークン認証を厳格登録しました")
        return

    bio_map = sec.get("device_bio_map", {})
    mp = bio_map.get(cfp) or bio_map.get(rhfp)

    if st.button("🔑 登録済み端末：端末トークン / ワンタップで即ログイン", use_container_width=True, type="primary"):
        if mp and mp.get("email"):
            tem = mp["email"].strip().lower()
            urec = db.get(tem, {})
            fp_matched = (mp.get("fp") == cfp or mp.get("raw_hfp") == rhfp)
            tok_valid = bool(mp.get("token")) and hmac.compare_digest(str(mp.get("token")), gen_tok(tem, "session_keep"))
            is_b, _ = check_and_log_ban_spoof(tem, urec.get("name", ""), cfp, rhfp, urec.get("pin_hash", ""), "ワンタップログイン")
            if is_b or urec.get("status") == "banned":
                st.error("💀 このアカウントまたは端末は永久BAN（アクセス禁止）されています。")
            elif urec.get("status") == "suspended":
                st.error("🚫 アカウント一時停止中です。")
            elif (cfp in sec.get("banned_fps", {}) or rhfp in sec.get("banned_fps", {})) and tem != ADMIN_EMAIL.strip().lower():
                st.error("🚫 端末制限中です。")
            elif not fp_matched or not tok_valid:
                st.warning("⚠️ 端末トークンの有効期限切れ、または端末指紋が一致しません。下のフォームから専用コードで再認証してください。")
            elif (urec and urec.get("status") == "approved" and urec.get("bio_enabled")) or tem == ADMIN_EMAIL.strip().lower():
                kt = gen_tok(tem, "session_keep")
                register_biometric_device_db(tem, kt)
                st.session_state["authenticated_user"] = tem
                st.query_params["u"], st.query_params["t"] = tem, kt
                st.rerun()
            else:
                st.warning("⚠️ この端末は未登録です。初回は下のフォームから専用コードでログインしてください。")
        else:
            is_b, _ = check_and_log_ban_spoof("", "未認証端末", cfp, rhfp, "", "ワンタップ試行")
            if is_b:
                st.error("💀 この端末は永久BAN（アクセス禁止）されています。")
            else:
                st.warning("⚠️ この端末は未登録です。初回は下のフォームから専用コードでログインしてください（次回から自動登録されます）。")

def inject_css():
    css = """@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;800&family=Plus+Jakarta+Sans:wght@400;600;800&family=JetBrains+Mono:wght@500;700&display=swap');
html,body,[class*="css"]{font-family:'Plus Jakarta Sans',sans-serif;font-size:14px;background-color:#050811;color:#e2e8f0;}
div[data-baseweb="popover"],div[data-baseweb="menu"],div[role="listbox"],ul[role="listbox"]{z-index:2147483647!important;pointer-events:auto!important;}
header[data-testid="stHeader"]{background:transparent!important;pointer-events:none!important;height:3.5rem!important;z-index:999980!important;}
header[data-testid="stHeader"] [data-testid="stToolbar"],header[data-testid="stHeader"] [data-testid="stActionButtons"]{display:none!important;}
section[data-testid="stSidebar"]{position:fixed!important;top:0!important;left:0!important;height:100vh!important;z-index:999995!important;width:330px!important;max-width:88vw!important;min-width:320px!important;background:rgba(8,12,22,0.98)!important;backdrop-filter:blur(25px)!important;border-right:1px solid rgba(56,189,248,0.35)!important;visibility:visible!important;transition:transform 0.28s cubic-bezier(0.4,0,0.2,1)!important;}
section[data-testid="stSidebar"]:not([aria-expanded="true"]){transform:translateX(-120%)!important;pointer-events:none!important;}
section[data-testid="stSidebar"][aria-expanded="true"]{transform:translateX(0)!important;pointer-events:auto!important;}
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]{pointer-events:auto!important;}
[data-testid="collapsedControl"],[data-testid="stSidebarCollapsedControl"],[data-testid="stSidebarCollapseButton"],header button[kind="headerNoPadding"],section[data-testid="stSidebar"] button[aria-label*="Close"],section[data-testid="stSidebar"] button[aria-label*="閉じる"],section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"]{display:none!important;opacity:0!important;position:absolute!important;width:0!important;height:0!important;overflow:hidden!important;pointer-events:none!important;z-index:-1!important;}
section[data-testid="stSidebar"]+div,section.main,.stApp>header+div>div{margin-left:0!important;width:100%!important;max-width:100%!important;}
.sidebar-section-card{background:rgba(15,23,42,0.65);border:1px solid rgba(56,189,248,0.18);border-radius:10px;padding:10px 12px;margin-bottom:12px;}
.sidebar-header-badge{font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:800;color:#38bdf8;letter-spacing:1px;margin-bottom:6px;display:flex;align-items:center;gap:5px;}
.fixed-top-nav-bar{position:fixed!important;top:10px!important;left:50%!important;transform:translateX(-50%)!important;z-index:999980!important;width:min(170px,calc(100vw - 4rem))!important;background:transparent!important;border:none!important;margin:0!important;padding:0!important;pointer-events:auto!important;}
div[data-testid="stElementContainer"]:has(div.top-nav-marker),div.element-container:has(div.top-nav-marker){display:none!important;height:0!important;margin:0!important;padding:0!important;border:none!important;}
.fixed-top-nav-bar div[data-testid="stHorizontalBlock"]{background:transparent!important;border:none!important;width:100%!important;display:flex!important;justify-content:center!important;}
.fixed-top-nav-bar button{width:100%!important;height:30px!important;min-height:30px!important;max-height:30px!important;background:rgba(15,23,42,0.75)!important;color:#93c5fd!important;border:1px solid rgba(56,189,248,0.35)!important;border-radius:20px!important;box-shadow:0 0 8px rgba(56,189,248,0.25)!important;font-size:11.5px!important;font-weight:700!important;letter-spacing:0.5px!important;cursor:pointer!important;transition:all 0.15s ease!important;}
.fixed-top-nav-bar button:hover{background:rgba(15,23,42,0.8)!important;border-color:rgba(56,189,248,0.45)!important;color:#93c5fd!important;box-shadow:0 0 10px rgba(56,189,248,0.3)!important;}
.fixed-top-nav-bar button:active{background:rgba(56,189,248,0.25)!important;border-color:#38bdf8!important;color:#ffffff!important;box-shadow:0 0 25px rgba(56,189,248,0.95),inset 0 0 12px rgba(56,189,248,0.6)!important;transform:scale(0.96)!important;}
.brand-luxury{font-family:'Cinzel',serif!important;font-size:clamp(16px,4.2vw,24px)!important;font-weight:800!important;letter-spacing:clamp(1px,0.5vw,3px)!important;background:linear-gradient(90deg,#f8fafc 0%,#38bdf8 50%,#a855f7 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1.25;white-space:nowrap!important;display:block;width:100%;}
.glass-header{background:radial-gradient(circle at top right,rgba(168,85,247,0.14),transparent 60%),linear-gradient(145deg,#0f172a 0%,#070b14 100%);border:1px solid rgba(148,163,184,0.18);border-radius:14px;padding:14px;margin-bottom:16px;box-shadow:0 10px 28px rgba(0,0,0,0.45);}
.rank-card,.search-result-card{background:linear-gradient(180deg,#0f172a 0%,#090d16 100%)!important;color:#f8fafc!important;border-radius:16px;padding:16px 18px;margin-top:14px;margin-bottom:24px;box-shadow:0 12px 32px rgba(0,0,0,0.65);border:1px solid rgba(148,163,184,0.22);border-left:5px solid #38bdf8;}
.search-result-card{border-left-color:#f59e0b;}
.prob-badge{font-family:'JetBrains Mono',monospace;font-size:clamp(14px,3.8vw,16.5px);font-weight:800;color:#38bdf8!important;}
.expect-badge{font-family:'JetBrains Mono',monospace;font-size:clamp(14px,3.8vw,16.5px);font-weight:900;color:#fde047!important;}
.winrate-bar{display:grid;grid-template-columns:repeat(auto-fit,minmax(65px,1fr));gap:6px;background:rgba(15,23,42,0.85)!important;border:1px solid rgba(148,163,184,0.18);border-radius:8px;padding:7px 6px;margin-top:5px!important;text-align:center;}
.trade-plan-box{display:grid;grid-template-columns:repeat(auto-fit,minmax(85px,1fr));gap:6px;margin-top:5px!important;background:rgba(2,6,23,0.7)!important;padding:7px 6px;border-radius:8px;border:1px solid rgba(148,163,184,0.18);text-align:center;}
.admin-table-container{width:100%;overflow-x:auto;background:#0b0f19;border:1px solid rgba(56,189,248,0.25);border-radius:10px;margin-top:10px;}
.admin-table{width:100%;border-collapse:collapse;font-size:11.5px;text-align:left;color:#e2e8f0;}
.admin-table th{background:#1e293b;color:#38bdf8;padding:8px 10px;border-bottom:1px solid rgba(56,189,248,0.3);font-weight:700;white-space:nowrap;}
.admin-table td{padding:8px 10px;border-bottom:1px solid rgba(148,163,184,0.1);white-space:nowrap;}
.admin-table tr:hover{background:rgba(56,189,248,0.05);}
.ai-council-box{background:rgba(8,12,22,0.98);border:1px solid rgba(56,189,248,0.35);border-radius:10px;padding:12px;margin-top:12px;}
.ai-engine-status-pill{background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.4);color:#6ee7b7;font-size:10.5px;font-weight:700;padding:4px 10px;border-radius:6px;margin-bottom:8px;display:block;}
.council-scroll-window{max-height:440px!important;height:400px!important;overflow-y:auto!important;overflow-x:hidden!important;padding-right:8px;padding-top:4px;display:flex;flex-direction:column;gap:6px;scroll-behavior:smooth;will-change:scroll-position;}
.council-scroll-window::-webkit-scrollbar{width:6px;}
.council-scroll-window::-webkit-scrollbar-track{background:rgba(15,23,42,0.6);border-radius:4px;}
.council-scroll-window::-webkit-scrollbar-thumb{background:#38bdf8;border-radius:4px;}
.chat-bubble-ai,.chat-bubble-user,.chat-bubble-agree,.chat-bubble-doubt,.chat-bubble-rage{padding:9px 12px;border-radius:8px;margin-bottom:4px;font-size:12px;line-height:1.5;word-break:break-word;}
.chat-bubble-ai{background:rgba(15,23,42,0.85);border-left:3px solid #38bdf8;}
.chat-bubble-agree{background:rgba(6,78,59,0.65);border-left:3px solid #10b981;}
.chat-bubble-doubt{background:rgba(120,53,15,0.65);border-left:3px solid #f59e0b;}
.chat-bubble-rage{background:rgba(127,29,29,0.65);border-left:3px solid #ef4444;}
.chat-bubble-user{background:rgba(56,189,248,0.24);border-left:4px solid #38bdf8;border-right:2px solid rgba(56,189,248,0.4);text-align:left;padding:10px 14px;margin-bottom:6px;border-radius:8px;box-shadow:0 4px 14px rgba(0,0,0,0.4);scroll-margin-top:6px!important;}
.round-divider{font-size:11px;font-weight:800;color:#94a3b8;text-align:center;margin:6px 0;letter-spacing:1px;}
.beginner-action-box{background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.4);border-radius:10px;padding:12px 14px;font-size:12px;line-height:1.7;color:#d1fae5;}
.sizing-box{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:4px;background:rgba(2,6,23,0.7);border:1px solid rgba(148,163,184,0.16);padding:7px 12px;border-radius:6px;margin-top:5px;font-size:11.5px;}
.forward-verify-bar{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:4px;background:linear-gradient(90deg,rgba(16,185,129,0.14),rgba(56,189,248,0.14));border:1px solid rgba(56,189,248,0.35);padding:6px 10px;border-radius:6px;margin-top:5px;font-size:11px;color:#e2e8f0;}
.quant-detail-drawer{margin-top:6px;font-size:11.5px;cursor:pointer;}
.signal-10tier-badge{padding:4px 10px;border-radius:6px;font-size:11px;font-weight:800;display:flex;justify-content:space-between;margin-bottom:6px;}
.pill-badge{font-size:clamp(9.5px,2.5vw,11px);padding:2px 5px;border-radius:4px;border:1px solid rgba(148,163,184,0.3);margin-right:3px;display:inline-block;white-space:nowrap!important;}
.quantum-badge{font-size:clamp(9.5px,2.5vw,11px);padding:2px 5px;border-radius:4px;background:rgba(168,85,247,0.15);border:1px solid rgba(168,85,247,0.4);color:#c084fc;margin-right:3px;display:inline-block;white-space:nowrap!important;}
.inst-badge{font-size:clamp(9.5px,2.5vw,11px);padding:2px 5px;border-radius:4px;background:rgba(56,189,248,0.15);border:1px solid rgba(56,189,248,0.4);color:#38bdf8;margin-right:0px;display:inline-block;white-space:nowrap!important;}
.badge-single-line{display:flex!important;flex-wrap:nowrap!important;align-items:center!important;overflow-x:auto!important;-webkit-overflow-scrolling:touch!important;scrollbar-width:none!important;margin-bottom:6px!important;gap:2px!important;white-space:nowrap!important;}
.badge-single-line::-webkit-scrollbar{display:none!important;}
.ipo-link-btn{display:inline-block;padding:5px 12px;background:rgba(245,158,11,0.2);border:1px solid #f59e0b;border-radius:6px;color:#fde047;text-decoration:none;font-size:11.5px;font-weight:700;margin-right:6px;margin-top:4px;}
.consensus-banner{background:rgba(15,23,42,0.95);border:1px solid rgba(250,204,21,0.4);border-radius:10px;padding:12px;margin-top:12px;}
.disclaimer-banner{background:rgba(15,23,42,0.6);border:1px solid rgba(148,163,184,0.15);border-radius:8px;padding:10px 14px;margin-top:25px;margin-bottom:15px;font-size:11px;line-height:1.6;color:#94a3b8;}
@keyframes alert-pulse{0%{box-shadow:0 0 0 0 rgba(239,68,68,0.8);}70%{box-shadow:0 0 0 10px rgba(239,68,68,0);}100%{box-shadow:0 0 0 0 rgba(239,68,68,0);}}
@keyframes pulse-dot{0%{opacity:0.3;transform:scale(0.9);}50%{opacity:1;transform:scale(1.1);}100%{opacity:0.3;transform:scale(0.9);}}
.live-pulse-indicator{display:inline-block;width:7px;height:7px;border-radius:50%;background:#10b981;box-shadow:0 0 8px #10b981;animation:pulse-dot 1.4s infinite ease-in-out;vertical-align:middle;margin-right:4px;}"""
    st.markdown(f'<div id="page_top_anchor"></div><style>{css}</style>', unsafe_allow_html=True)

inject_css()

# ==========================================
# 6. 認証処理実行
# ==========================================
def check_auth():
    qu, qt = st.query_params.get("u", "").strip().lower(), st.query_params.get("t", "").strip()
    if "authenticated_user" not in st.session_state: st.session_state["authenticated_user"] = None
    db = load_mem()
    cfp, rhfp = get_client_fp(), get_raw_header_fp()

    if not st.session_state["authenticated_user"] and qu and qt:
        if hmac.compare_digest(qt, gen_tok(qu, "session_keep")) and ((db.get(qu) and db[qu].get("status") == "approved") or qu == ADMIN_EMAIL.strip().lower()):
            st.session_state["authenticated_user"] = qu

    if st.session_state["authenticated_user"]:
        cu = st.session_state["authenticated_user"]
        urec = db.get(cu, {})
        if cu != ADMIN_EMAIL.strip().lower():
            is_b, _ = check_and_log_ban_spoof(cu, urec.get("name", ""), cfp, rhfp, urec.get("pin_hash", ""), "セッション維持")
            if is_b or urec.get("status") == "banned":
                st.session_state["authenticated_user"] = None; st.query_params.clear(); st.error("💀 このアカウントまたは端末は永久BANされています。"); st.stop()
            if not urec or urec.get("status") != "approved":
                st.session_state["authenticated_user"] = None; st.query_params.clear(); st.error("🚫 アカウント一時停止中、または削除されています。"); st.stop()
        kt = gen_tok(cu, "session_keep")
        if st.query_params.get("u") != cu or st.query_params.get("t") != kt:
            st.query_params["u"], st.query_params["t"] = cu, kt
        return True

    st.markdown('<style>section[data-testid="stSidebar"]{display:none!important;transform:translateX(-150%)!important;}#yamashishi-floating-sidebar-btn{display:none!important;}</style>', unsafe_allow_html=True)
    st.markdown(
        '<div class="glass-header" style="text-align:center;padding:18px 12px;">'
        '<div class="brand-luxury">YAMASHISHI LAB</div>'
        '<div class="brand-sub" style="margin-top:4px;">5-MIN OHLCV QUANTITATIVE & GEMINI MULTI-PERSONA TERMINAL</div>'
        '<div style="display:flex;justify-content:center;gap:8px;margin-top:10px;flex-wrap:wrap;">'
        '<span class="quantum-badge">⚛️ ボラティリティ突破指数 (WKB統計近似)</span>'
        '<span class="inst-badge">🏛️ 5分足需給ミクロ構造 (OHLCV近似)</span>'
        '<span class="pill-badge" style="color:#10b981;border-color:rgba(16,185,129,0.3);">🔑 端末固有トークン認証</span>'
        '</div></div>',
        unsafe_allow_html=True
    )
    render_biometric_bridge(mode="login")

    tab_login, tab_apply, tab_vault = st.tabs(["🔑 コードログイン", "📩 新規会員登録申請", "🔐 承認確認・暗号化コード照会"])
    with tab_login:
        with st.form("login"):
            ie, ic = st.text_input("📧 登録メールアドレス", placeholder="your@email.com"), st.text_input("🔑 専用アクセスコード", type="password", placeholder="8桁の専用コード")
            if st.form_submit_button("🔓 認証してターミナルを起動", use_container_width=True):
                cm, adm_c = ie.strip().lower(), ADMIN_EMAIL.strip().lower()
                rec = db.get(cm)
                if (rec and rec.get("status") == "approved" or cm == adm_c) and ((cm == adm_c and hmac.compare_digest(ic.strip(), ADMIN_PASS)) or (rec and rec.get("status") == "approved" and hmac.compare_digest(ic.strip().upper(), gen_code(cm)))):
                    kt = gen_tok(cm, "session_keep")
                    register_biometric_device_db(cm, kt)
                    st.session_state["authenticated_user"] = cm; st.query_params["u"], st.query_params["t"] = cm, kt; st.rerun()
                else: st.warning("⚠️ 未承認または専用アクセスコードが異なります。")
    with tab_apply:
        with st.form("apply"):
            st.caption("🔐 セキュリティ保護のため、申請時に「あなただけの4桁の暗証番号(PIN)」を設定してください。承認後にコードを確認する際に必要となります。")
            an, am, apin = st.text_input("👤 お名前（ニックネーム可）"), st.text_input("📧 メールアドレス"), st.text_input("🔢 秘密の4桁暗証番号 (PIN・数字4桁)", type="password", max_chars=4, placeholder="例: 7788")
            if st.form_submit_button("📨 セキュア会員登録を申請する", use_container_width=True):
                if "@" not in am or len(apin.strip()) < 4 or not apin.strip().isdigit(): st.warning("⚠️ 正しいメールアドレスと数字4桁の暗証番号(PIN)を入力してください。")
                else:
                    cm, ns = am.strip().lower(), datetime.now().strftime("%Y-%m-%d %H:%M")
                    nm, ph = an.strip() or "未入力", hash_pin(apin, cm)
                    is_b, _ = check_and_log_ban_spoof(cm, nm, cfp, rhfp, ph, "新規登録申請")
                    if is_b or (db.get(cm) and db[cm].get("status") == "banned"): st.error("💀 セキュリティ監視システムにより、申請は永久ブロックされました。")
                    else:
                        db[cm] = {"name": nm, "email": cm, "status": "pending", "passcode": gen_code(cm), "pin_hash": ph, "applied_at": ns, "approved_at": "-", "last_seen_ts": 0, "last_seen_str": "-", "fp": cfp, "raw_hfp": rhfp, "bio_enabled": False}
                        db_set("mem", db)
                        send_mail(cm, "【YAMASHISHI LAB】会員登録申請の受付完了", f"{nm} 様\n申請を受け付けました。管理者承認後、ログイン画面の『🔐 承認確認・暗号化コード照会』タブにて、暗証番号(PIN)を入力すると専用アクセスコードをご確認いただけます。")
                        st.success("✅ 申請を受け付けました！承認完了まで今しばらくお待ちください。")
    with tab_vault:
        st.caption("🛡️ 第三者による盗み見を防止するため、**申請時のメールアドレス** と **秘密の4桁暗証番号(PIN)** の両方が一致した場合のみ専用アクセスコードを開示します。")
        with st.form("vault_check"):
            chk_em, chk_pin = st.text_input("📧 申請したメールアドレス").strip().lower(), st.text_input("🔢 申請時に設定した4桁の暗証番号 (PIN)", type="password", max_chars=4).strip()
            if st.form_submit_button("🔍 本人確認して承認ステータスを照会", use_container_width=True):
                u_info = db.get(chk_em)
                is_b, _ = check_and_log_ban_spoof(chk_em, (u_info or {}).get("name", ""), cfp, rhfp, hash_pin(chk_pin, chk_em) if chk_pin else "", "コード照会")
                if is_b or (u_info and u_info.get("status") == "banned"): st.error("💀 このアカウントまたは端末は永久BANされています。")
                elif not u_info: st.error("❌ 該当する申請データが見つかりません。")
                elif u_info.get("pin_hash") and not verify_pin(u_info.get("pin_hash", ""), chk_pin, chk_em): st.error("🚫 暗証番号(PIN)が一致しません。第三者による照会はブロックされました。")
                elif u_info.get("status") == "approved":
                    if len(u_info.get("pin_hash", "")) < 24:
                        u_info["pin_hash"] = hash_pin(chk_pin, chk_em); db[chk_em] = u_info; db_set("mem", db)
                    st.success(f"🎉 本人確認完了・承認済みです！あなたの専用アクセスコードは **`{u_info.get('passcode', gen_code(chk_em))}`** です。「🔑 コードログイン」タブからログインしてください。")
                elif u_info.get("status") == "pending": st.info("⏳ 本人確認完了：現在、管理者の承認審査待ちです。")
                else: st.error("🚫 現在このアカウントは一時停止中または利用できません。")
    st.stop()

check_auth()

# ==========================================
# 7. セッション状態の初期化
# ==========================================
saved_agents, saved_inspectors, saved_fired, saved_sz_active, saved_sz_logs = load_agi_system()
cu_active = st.session_state.get("authenticated_user", "")
user_saved_prefs, user_saved_watchlist = load_user_prefs(cu_active), load_watchlist(cu_active)

if "user_prefs_loaded" not in st.session_state or st.session_state.get("last_loaded_user") != cu_active:
    st.session_state["investment_style_choice"] = user_saved_prefs.get("investment_style", "⚡ デイトレード (前場・後場の波及を狙う)")
    st.session_state["total_capital_val"] = int(user_saved_prefs.get("total_capital", 1000000))
    st.session_state["risk_tolerance_val"] = float(user_saved_prefs.get("risk_tolerance_pct", 2.0))
    st.session_state["survival_cut_val"] = int(user_saved_prefs.get("survival_cut_pct", 75))
    saved_boosts = set(user_saved_prefs.get("active_boosts", ["algo", "ms", "inst", "mom", "agi_q", "hft_front"]))
    for bk in ["algo", "ms", "inst", "mom", "agi_q", "hft_front"]: st.session_state[f"chk_{bk}"] = (bk in saved_boosts)
    st.session_state["watchlist"] = user_saved_watchlist
    st.session_state["user_prefs_loaded"] = True
    st.session_state["last_loaded_user"] = cu_active

defaults = {
    "active_debates": {}, "council_threads": {}, "council_meta": {}, "debate_round_seed": {}, "watchlist": user_saved_watchlist,
    "navigation_page": "TOP", "selected_news_item": None, "custom_search_code": "", "active_category": "🏆 総合TOP5",
    "last_cat": "🏆 総合TOP5", "nav_history": [], "scroll_top_trig": 0, "scroll_target_id": "", "focused_stock_item": None,
    "agent_roster": saved_agents, "inspector_roster": saved_inspectors, "fired_agents": saved_fired, "system_zero_logs": saved_sz_logs,
    "system_zero_active": saved_sz_active, "stock_dialogue_signatures": {}, "news_ai_deep_cache": {}, "last_audit_similarity_penalty": 0
}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# ==========================================
# 8. トップナビゲーションとサイドバー開閉JS
# ==========================================
with st.container():
    st.markdown('<div class="top-nav-marker"></div>', unsafe_allow_html=True)
    if st.button("トップに戻る", key="top_nav_top", use_container_width=True):
        st.session_state["navigation_page"] = "TOP"
        st.session_state["scroll_top_trig"] = int(time.time() * 1000)
        st.session_state["focused_stock_item"] = None
        st.rerun()

scroll_target_js = ""
if st.session_state.get("scroll_target_id"):
    tid = st.session_state.get("scroll_target_id")
    scroll_target_js = f"""setTimeout(function(){{try{{const el=window.parent.document.getElementById('{tid}');if(el){{const win=el.closest('.council-scroll-window');if(win){{win.scrollTo({{top:Math.max(0,el.offsetTop-4),behavior:'smooth'}});}}(el.closest('.ai-council-box')||el).scrollIntoView({{behavior:'smooth',block:'center'}});}}}}catch(e){{}}}},120);"""
    st.session_state["scroll_target_id"] = ""

components.html(
    f"""<script>
    (function(){{
        const doc = window.parent.document;
        function closeCustomSidebar(){{try{{const sb=doc.querySelector('section[data-testid="stSidebar"]'),o=doc.getElementById('yamashishi-sidebar-backdrop');if(sb){{sb.setAttribute('aria-expanded','false');sb.style.setProperty('transform','translateX(-120%)','important');sb.style.setProperty('pointer-events','none','important');}}if(o)o.style.display='none';window.parent.sessionStorage.setItem('yamashishi_sb_state','closed');}}catch(e){{}}}}
        function openCustomSidebar(){{try{{const sb=doc.querySelector('section[data-testid="stSidebar"]'),o=doc.getElementById('yamashishi-sidebar-backdrop');if(sb){{sb.setAttribute('aria-expanded','true');sb.style.setProperty('transform','translateX(0)','important');sb.style.setProperty('pointer-events','auto','important');}}if(o)o.style.display='block';window.parent.sessionStorage.setItem('yamashishi_sb_state','open');}}catch(e){{}}}}
        function setupCustomSidebar(){{
            try{{
                if(!doc.getElementById('yamashishi-custom-sidebar-styles')){{
                    const s=doc.createElement('style');s.id='yamashishi-custom-sidebar-styles';
                    s.textContent=`#yamashishi-floating-sidebar-btn{{position:fixed!important;top:8px!important;left:10px!important;z-index:2147483647!important;display:flex!important;align-items:center!important;justify-content:center!important;gap:4px!important;height:28px!important;padding:0 10px 0 8px!important;background:rgba(11,15,25,0.95)!important;backdrop-filter:blur(16px)!important;border:1.5px solid rgba(56,189,248,0.7)!important;border-radius:8px!important;cursor:pointer!important;box-shadow:0 4px 18px rgba(0,0,0,0.75),0 0 12px rgba(56,189,248,0.3)!important;user-select:none!important;transition:transform 0.1s ease!important;color:#38bdf8!important;pointer-events:auto!important;outline:none!important;-webkit-tap-highlight-color:transparent!important;}}#yamashishi-floating-sidebar-btn:hover{{border-color:rgba(56,189,248,0.7)!important;color:#38bdf8!important;box-shadow:0 4px 18px rgba(0,0,0,0.75),0 0 12px rgba(56,189,248,0.3)!important;}}#yamashishi-floating-sidebar-btn:active{{border-color:#fde047!important;color:#fde047!important;box-shadow:0 6px 22px rgba(0,0,0,0.9),0 0 18px rgba(253,224,71,0.4)!important;transform:scale(0.95)!important;}}#yamashishi-floating-sidebar-btn svg{{width:15px!important;height:15px!important;}}#yamashishi-floating-sidebar-btn span{{font-family:'JetBrains Mono',monospace!important;font-size:11px!important;font-weight:800!important;}}#yamashishi-sidebar-backdrop{{position:fixed!important;top:0!important;left:0!important;width:100vw!important;height:100vh!important;background:rgba(0,0,0,0.4)!important;backdrop-filter:blur(2px)!important;z-index:999990!important;display:none;}}`;
                    doc.head.appendChild(s);
                }}
                let o=doc.getElementById('yamashishi-sidebar-backdrop');
                if(!o){{o=doc.createElement('div');o.id='yamashishi-sidebar-backdrop';doc.body.appendChild(o);o.addEventListener('click',function(e){{e.preventDefault();e.stopPropagation();closeCustomSidebar();}});}}
                let b=doc.getElementById('yamashishi-floating-sidebar-btn');
                if(!b){{b=doc.createElement('div');b.id='yamashishi-floating-sidebar-btn';b.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg><span>MENU</span>';doc.body.appendChild(b);}}
                b.onclick=function(e){{e.preventDefault();e.stopPropagation();const sb=doc.querySelector('section[data-testid="stSidebar"]');if(sb){{sb.getAttribute('aria-expanded')==='true'?closeCustomSidebar():openCustomSidebar();}}}};
                if(!doc._yamashishiGlobalOutsideBound){{doc.addEventListener('click',function(e){{const sb=doc.querySelector('section[data-testid="stSidebar"]'),btn=doc.getElementById('yamashishi-floating-sidebar-btn');if(sb&&sb.getAttribute('aria-expanded')==='true'&&!sb.contains(e.target)&&(!btn||!btn.contains(e.target)))closeCustomSidebar();}},true);doc._yamashishiGlobalOutsideBound=true;}}
                const savedState = window.parent.sessionStorage.getItem('yamashishi_sb_state');
                if(savedState === 'open'){{
                    openCustomSidebar();setTimeout(openCustomSidebar, 50);setTimeout(openCustomSidebar, 150);setTimeout(openCustomSidebar, 300);
                }}
            }}catch(e){{}}
        }}
        function fixTopNav(){{try{{const m=doc.querySelector('.top-nav-marker');if(!m)return;let bx=m.closest('[data-testid="stVerticalBlockBorderWrapper"]')||m.closest('[data-testid="stVerticalBlock"]');if(bx&&bx.querySelector('button'))bx.classList.add('fixed-top-nav-bar');}}catch(e){{}}}}
        setupCustomSidebar();fixTopNav();
        function scrollToTopAbsolute(){{try{{window.parent.scrollTo(0,0);}}catch(e){{}}[doc.documentElement,doc.body,doc.querySelector('section.main'),doc.querySelector('[data-testid="stAppViewContainer"]')].forEach(el=>{{if(el){{try{{el.scrollTop=0;}}catch(e){{}}}}}});const ta=doc.getElementById('page_top_anchor');if(ta&&typeof ta.scrollIntoView==='function')try{{ta.scrollIntoView({{behavior:'instant',block:'start'}});}}catch(e){{}}}}
        if({st.session_state['scroll_top_trig']}>0&&window.parent._lastScrollTrig!=={st.session_state['scroll_top_trig']}){{window.parent._lastScrollTrig={st.session_state['scroll_top_trig']};scrollToTopAbsolute();}}
        {scroll_target_js}
    }})();
    </script>""", height=0
)

# ==========================================
# 9. サイドバー構築（一般会員はシンプル表示・API/システム設定は管理者専用へ完全分離）
# ==========================================
def _compute_real_audit_metrics() -> dict:
    err_cnt = len(get_system_error_logs())
    fired_cnt = len(st.session_state.get("fired_agents", []))
    sim_pen = int(st.session_state.get("last_audit_similarity_penalty", 0))
    health_score = int(np.clip(100 - min(25, err_cnt * 2) - min(15, fired_cnt) - sim_pen, 50, 100))
    return {
        "health_score": health_score, "err_cnt": err_cnt, "fired_cnt": fired_cnt, "sim_pen": sim_pen,
        "insp_scores": {
            "INSP_A": int(np.clip(100 - sim_pen - min(10, fired_cnt), 60, 100)),
            "INSP_B": int(np.clip(100 - min(15, err_cnt), 60, 100)),
            "INSP_C": int(np.clip(100 - min(15, err_cnt * 2), 60, 100))
        }
    }

with st.sidebar:
    cu = st.session_state.get("authenticated_user", "")
    is_admin_user = (cu == ADMIN_EMAIL.strip().lower())

    # 1. 会員ステータス表示＆端末ワンタップ登録ボタン
    if cu:
        role_badge = "👑 MASTER ADMIN" if is_admin_user else "⚛️ MEMBER SESSION ACTIVE"
        st.markdown(f'<div class="sidebar-section-card"><div class="sidebar-header-badge">{role_badge}</div><div style="color:#f8fafc;font-size:12px;font-weight:700;">会員: {html.escape(cu)}</div></div>', unsafe_allow_html=True)
        render_biometric_bridge(mode="register", user_email=cu, bio_token=st.query_params.get("t", ""))

    # 管理者のみ統合管理コントロールセンター起動ボタンを表示
    if is_admin_user:
        if st.button("🖥️ 統合管理コントロールセンター起動", use_container_width=True, type="primary"):
            st.session_state["navigation_page"] = "ADMIN"
            st.rerun()

    # 2. 投資スタイル ＆ アルゴリズム選択
    with st.expander("🎯 投資スタイル ＆ アルゴリズム選択", expanded=True):
        style_list = ["⚡ デイトレード (前場・後場の波及を狙う)", "🚀 スキャルピング (秒〜分単位のモメンタム)", "📈 スイングトレード (数日〜数週間のトレンド)", "💎 バイ＆ホールド (中長期・IPO分散投資)"]
        cur_style_saved = st.session_state.get("investment_style_choice", style_list[0])
        idx = style_list.index(cur_style_saved) if cur_style_saved in style_list else 0
        investment_style = st.selectbox("トレードスタイル", style_list, index=idx, key="investment_style_choice")
        if investment_style != cur_style_saved:
            st.session_state["council_threads"] = {}
            st.session_state["council_meta"] = {}
        st.caption(f"選択中: **{investment_style.split(' ')[1]}**")
        st.markdown("<hr style='margin:8px 0; border-color:rgba(56,189,248,0.2);'><b>稼働アルゴリズム（5分足OHLCV実測連動）</b>", unsafe_allow_html=True)
        BOOST_MAP = {
            "⚛️ ボラティリティ突破指数 (WKB統計近似)": "algo",
            "🏛️ 5分足需給ミクロ構造 (OHLCV近似)": "ms",
            "🏦 BVC-VPIN・CLV資金フロー近似": "inst",
            "🔥 出来高サージ＆ニュース熱量": "mom",
            "🧠 BBスクイーズ拡大初動(Exp-Ratio)": "agi_q",
            "⚠️ 出来高スパイク×実体陽線吸収(Vol-Spike)": "hft_front"
        }
        ac_b = {k for l, k in BOOST_MAP.items() if st.checkbox(l, value=st.session_state.get(f"chk_{k}", True), key=f"chk_{k}")}

    # 3. 資金管理＆選抜フィルタ
    with st.expander("💰 資金管理＆選抜フィルタ", expanded=False):
        total_capital = st.number_input("総投資資金 (円)", min_value=10000, max_value=1000000000, value=int(st.session_state.get("total_capital_val", 1000000)), step=50000, key="total_capital_input")
        risk_tolerance_pct = st.slider("1トレード許容リスク (%)", 0.5, 5.0, float(st.session_state.get("risk_tolerance_val", 2.0)), 0.5, key="risk_tolerance_input")
        survival_cut_pct = st.slider("選抜合格率 (%)", 40, 100, int(st.session_state.get("survival_cut_val", 75)), 5, key="survival_cut_input")

    if cu:
        save_user_prefs(cu, {"investment_style": investment_style, "active_boosts": list(ac_b), "total_capital": total_capital, "risk_tolerance_pct": risk_tolerance_pct, "survival_cut_pct": survival_cut_pct})

    # 4. ログアウトボタン
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚪 ログアウト", use_container_width=True):
        cu_l = st.session_state.get("authenticated_user")
        db_l = load_mem()
        if cu_l in db_l: db_l[cu_l]["last_seen_ts"] = 0; db_set("mem", db_l)
        st.session_state["authenticated_user"] = None; st.query_params.clear(); st.rerun()

# ==========================================
# 10. 高速並列データ収集 ＆ 実測RVOL・騰落率チャレンジャー発掘
# ==========================================
@st.cache_data(ttl=300)
def search_single_query(q: str, max_r: int) -> list:
    res = []
    try:
        req = urllib.request.Request(f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=ja&gl=JP&ceid=JP:ja", headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=2.5, context=ssl.create_default_context()) as r:
            for it in ET.fromstring(r.read()).findall("./channel/item")[:max_r]:
                t = re.sub(r"\s*-\s*[^-]+$", "", re.sub(r"<[^>]+>", "", it.findtext("title") or "").strip())
                d = re.sub(r"<[^>]+>", "", it.findtext("description") or "").strip()
                pub = (it.findtext("pubDate") or "").strip()
                if t: res.append(f"{t} ({d[:80]}...) [{pub[:16]}]")
    except Exception as e: record_system_error("search_single_query", e, f"Query: {q}")
    return res

def _infer_genre_from_text(txt: str) -> str:
    tu = (txt or "").upper()
    if any(k in tu for k in ["半導体", "ウエハ", "EUV", "HBM", "GPU", "チップ", "ファウンドリ", "検査装置"]): return "半導体・前工程・検査"
    if any(k in tu for k in ["防衛", "自衛隊", "重工", "国策", "AI", "人工知能", "クラウド", "サイバー", "銀行", "商社"]): return "AI・防衛・国策"
    if any(k in tu for k in ["電力", "原発", "送電", "電線", "光ファイバー", "データセンター", "液冷", "原子炉"]): return "AI電力・超電導・電線"
    if any(k in tu for k in ["宇宙", "衛星", "ロケット", "月面", "量子", "ドローン", "ロボット"]): return "宇宙・量子・次世代テック"
    return "小型急騰・仕手・モメンタム"

def _extract_tickers_from_text(txt: str) -> list:
    found, seen_local = [], set()
    for rc in re.findall(r"(?<![0-9A-Za-z])([1-9][0-9]{2}[0-9A-Z])(?![0-9A-Za-z])", txt or ""):
        if re.match(r"^202[0-9]$", rc): continue
        fc = f"{rc}.T"
        if fc in seen_local: continue
        seen_local.add(fc)
        if fc in EXTENDED_SEED_DICT:
            inf = EXTENDED_SEED_DICT[fc]
            found.append((fc, inf["name"], inf["genre"], inf["theme"]))
        else:
            m_name = re.search(rf"([^\s「」『』【】\(\)（）]{{2,14}})\s*[\(（<＜]?\s*{re.escape(rc)}", txt or "")
            est_name = m_name.group(1) if m_name else f"東証{rc}"
            est_genre = _infer_genre_from_text(txt)
            est_theme = "市況急動意・ニュース自動発掘銘柄"
            STOCK_METADATA_CACHE[fc] = {"name": est_name, "genre": est_genre, "theme": est_theme}
            found.append((fc, est_name, est_genre, est_theme))

    for fc, inf in EXTENDED_SEED_DICT.items():
        if fc in seen_local: continue
        short_nm = inf["name"].replace("HD", "").replace("グループ", "").replace("フィナンシャルG", "")
        if len(short_nm) >= 2 and short_nm in (txt or ""):
            seen_local.add(fc)
            found.append((fc, inf["name"], inf["genre"], inf["theme"]))
    return found

@st.cache_data(ttl=240)
def discover_challenger_tickers(existing_codes_tuple: tuple) -> list:
    existing_set = set(existing_codes_tuple)
    challengers, seen = [], set(existing_set)

    queries = [
        '("ストップ高" OR "上方修正" OR "急騰" OR "最高益" OR "自社株買い" OR "新規上場") 株',
        '("急伸" OR "連騰" OR "買い気配" OR "好決算" OR "テーマ株") 東証'
    ]
    rss_snippets = []
    with ThreadPoolExecutor(max_workers=2) as ex:
        for f in as_completed([ex.submit(search_single_query, q, 8) for q in queries]):
            try: rss_snippets.extend(f.result())
            except Exception as e: record_system_error("discover_challenger_tickers:rss", e)

    for snip in rss_snippets:
        for item in _extract_tickers_from_text(snip):
            if item[0] not in seen:
                seen.add(item[0])
                challengers.append(item)
                if len(challengers) >= 8: break
        if len(challengers) >= 8: break

    needed = 12 - len(challengers)
    if needed > 0:
        pool_candidates = [(c, n, g, t) for c, n, g, t in EXTENDED_SEED_LIST if c not in seen]
        if pool_candidates:
            cand_codes = [c for c, _, _, _ in pool_candidates]
            try:
                raw_5d = yf.download(cand_codes, period="5d", interval="1d", group_by="ticker", threads=True, progress=False, timeout=4.0)
                scored_cands = []
                for c, n, g, t in pool_candidates:
                    try:
                        df_c = raw_5d[c] if (len(cand_codes) > 1 and c in raw_5d) else raw_5d
                        df_c = df_c.dropna(subset=["Close", "Volume"])
                        if len(df_c) >= 2:
                            cl = df_c["Close"].values.astype(float)
                            vo = df_c["Volume"].values.astype(float)
                            prev_v = float(np.mean(vo[:-1])) if len(vo) > 1 else float(vo[-1])
                            rvol = float(vo[-1]) / max(prev_v, 1.0)
                            abs_chg = abs((float(cl[-1]) - float(cl[-2])) / max(float(cl[-2]), 1e-4)) * 100.0
                            activity_score = rvol * 10.0 + abs_chg * 3.0
                            scored_cands.append((activity_score, (c, n, g, t)))
                    except Exception:
                        continue
                scored_cands.sort(key=lambda x: x[0], reverse=True)
                for _, item in scored_cands[:needed]:
                    seen.add(item[0])
                    challengers.append(item)
            except Exception as e:
                record_system_error("discover_challenger_tickers:yf_5d", e)

    for c, n, g, t in challengers:
        STOCK_METADATA_CACHE[c] = {"name": n, "genre": g, "theme": t}
    return challengers[:14]

def analyze_news_impact_and_links(title: str, cat: str, summary_text: str = "") -> dict:
    tu = (title + " " + summary_text).upper()
    clean_sum = re.sub(r"&nbsp;|&#\d+;", " ", re.sub(r"<[^>]+>", "", summary_text or "")).strip()
    dynamic_codes = [it[0] for it in _extract_tickers_from_text(f"{title} {clean_sum}")]

    if any(w in tu for w in ["半導体", "エヌビディア", "NVDA", "TSMC", "AI", "アドバンテスト", "東エレク", "レーザー", "光配線", "データセンター"]):
        base_codes = ["6857.T", "8035.T", "6146.T", "6920.T", "5803.T", "NVDA"]
        sf = "AI半導体・先端パッケージング・光電融合インフラ"
        bg_body = (
            f"【報道内容の核心】\n{clean_sum if len(clean_sum) > 25 else title}\n\n"
            "【ファンダメンタルズ深掘り背景】\n"
            "北米ハイパースケーラーによる次世代AIデータセンター投資の継続と、GPU・HBM（広帯域メモリ）の供給逼迫が背景にあります。"
            "特に後工程（ダイシング・研削・検査）およびデータセンター間の超高速光配線はボトルネック解消の最重要セクターであり、実需を伴う業績上方修正サイクルが強く働く領域です。"
        )
        mech = (
            "① 【海外マクロ連動】米SOX指数およびNVIDIAの時間外取引と強い正の相関（相関係数0.82以上）を持ちます。\n"
            "② 【機関アルゴの執行手口】海外年金・CTA・HFT勢はニュース検知から日経225先物と主力半導体株の『業種バスケット買い（VWAPアルゴリズム）』を同時発動させます。\n"
            "③ 【需給の波及構造】寄り付きで指数寄与度の高い大型半導体がギャップアップした後、前場9:15〜9:45にかけて周辺部材・電線インフラへ出遅れ物色の資金が循環します。"
        )
        timeline = (
            "・【第1波：寄り付き（9:00〜9:15）】ヘッドラインに反応した短期勢と個人の成行買いが集中。前日高値および心理的節目をブレイクする強いモメンタムが発生。\n"
            "・【第2波：前場中盤（9:15〜10:30）】寄り天警戒の短期利確売りをこなし、VWAP付近で機関投資家のTWAP（時間分散買い）が下値を支える押し目形成フェーズ。\n"
            "・【第3波：後場〜大引け（12:30〜15:30）】空売り勢の買い戻しを巻き込みながら、高値引けまたは翌日へのオーバーナイト需要が継続するかの選別フェーズ。"
        )
        risk_note = "米長期金利の急騰や為替の急激な円高進行、および寄り付きで+4%以上の過度なギャップアップとなった場合は『材料出尽くしの寄り天』に警戒。必ずVWAP割れに逆指値を置くこと。"
        action_guide = (
            "① 【寄り付き前（8:45〜9:00）】気配値とマクロ・需給連動 理論寄付き試算値を確認。ギャップアップが+2.5%以内なら寄り付き成行で追随。\n"
            "② 【大幅ギャップアップ時】飛びつき買いは厳禁。9:15〜9:30の最初の押し目で株価がVWAPライン上で下げ止まり、5分足CLV資金フローが陽転した瞬間を狙い撃つ。\n"
            "③ 【出遅れ連動狙い】6857や8035がすでに高騰している場合、連動性の高い5803（フジクラ）や6146（ディスコ）の初動ブレイクを叩くのが最もリスクリワード比が高い。"
        )
    elif any(w in tu for w in ["防衛", "三菱重", "川崎重", "IHI", "宇宙", "衛星", "地政学", "ミサイル", "ドローン", "安保"]):
        base_codes = ["7011.T", "7012.T", "7013.T", "5595.T", "186A.T", "PLTR"]
        sf = "防衛国策・宇宙衛星コンステレーション・重工インフラ"
        bg_body = (
            f"【報道内容の核心】\n{clean_sum if len(clean_sum) > 25 else title}\n\n"
            "【ファンダメンタルズ深掘り背景】\n"
            "防衛費の対GDP比2%への倍増計画、スタンド・オフ防衛能力の強化、および次世代戦闘機・小型SAR衛星網の構築など、複数年にわたる『国策予算の裏付け』があるテーマです。"
            "景気変動や半導体市況の波に左右されにくい官公庁・防衛省向けの長期大型契約がベースとなるため、機関投資家が中長期コア銘柄として組み入れ比率を引き上げています。"
        )
        mech = (
            "① 【ディフェンシブ×モメンタム特性】全体相場が軟調な日でも、地政学ヘッドラインや防衛予算関連ニュースが出た際は逆行高を演じる独自の資金流入特性があります。\n"
            "② 【低価格インパクト・ステルス集積近似】重工大手3社は売買代金が極めて大きく、海外ロングオンリーファンドが価格インパクトを抑えながら下値を拾い上げます。\n"
            "③ 【小型宇宙株への波及】重工大手の株価が1段高になると、値動きの軽い小型宇宙ベンチャーへ個人と短期資金が一気に雪崩れ込みます。"
        )
        timeline = (
            "・【第1波：初動（報道直後〜前場）】重工大手3社（7011/7012/7013）に国内外の機関買いが流入し、出来高を伴う大陽線を形成。\n"
            "・【第2波：波及（前場後半〜後場）】東証グロース市場の宇宙・防衛AI関連に短期モメンタム資金が波及。\n"
            "・【第3波：トレンド定着（数日〜数週間）】押し目をほとんど作らず日足の5日移動平均線に沿った強いバンドウォーク上昇へ移行。"
        )
        risk_note = "停戦報道や地政学リスクの急激な緩和ヘッドラインが出た場合は、短期筋のアルゴリズムが一斉に手仕舞い売りを出すため、直近安値を割れた際は機械的にポジションを縮小すること。"
        action_guide = (
            "① 【主力本命】資金量が多い場合は7011（三菱重工業）または7012（川崎重工業）のVWAP押し目を本玉でエントリー。\n"
            "② 【ボラティリティ重視】資金効率と値幅を狙う場合は、主力重工株がプラス圏で推移していることを確認した上で、5595（QPS研究所）等の直近高値ブレイクに順張り追随。\n"
            "③ 【利確と損切り】利確目標に達した時点で半分を利益確定し、残り半分は逆指値を建値に引き上げて上値を伸ばすトレイリング戦略が有効。"
        )
    else:
        base_codes = ["9984.T", "6857.T", "5803.T", "7011.T", "5253.T", "3350.T"]
        sf = "上方修正サプライズ・国策AI・短期モメンタム集中銘柄"
        bg_body = (
            f"【報道内容の核心】\n{clean_sum if len(clean_sum) > 25 else title}\n\n"
            "【ファンダメンタルズ深掘り背景】\n"
            "市場コンセンサスを上回る業績上方修正、増配・自社株買い、または新技術・大型提携などのポジティブサプライズ報道です。"
            "これまでの市場織り込みが一変するため、空売りしていた投資家の買い戻しと新規の順張り資金が同時に衝突し、強いトレンドが発生します。"
        )
        mech = (
            "① 【ショートカバー連鎖】サプライズ報道直後は、信用売り残や機関の空売りポジションが買い戻しを余儀なくされ、さらなる株価上昇を呼ぶショートスクイーズが発生します。\n"
            "② 【流動性と価格インパクト】買い注文に対して売り手が極端に少なくなるため、少ない出来高でも株価が飛び跳ねる状態になります。"
        )
        timeline = (
            "・【第1波：寄り付き〜前場前半】特別買い気配またはギャップアップからスタート。出来高が普段の3倍〜10倍に急増。\n"
            "・【第2波：前場後半〜後場】短期勢の利食い売りを吸収し、高値圏での保ち合いから後場の二段上げへ。\n"
            "・【第3波：翌日以降】3営業日ルールのモメンタム継続判定。"
        )
        risk_note = "出来高が伴わないまま株価だけが浮上している場合や、高値圏で大陰線を引いた場合は、大口の売り抜け完了サインとなるため即座に撤退すること。"
        action_guide = (
            "① 【初動の確認】朝の気配値で買い優勢を確認し、寄り付き直後の上値ブレイクに順張りエントリー。\n"
            "② 【ロット管理】1回の許容損失額（総資金の2%）を超えないよう推奨ロット数を厳守する。\n"
            "③ 【出口戦略】前引け（11:30）および大引け（15:30）前の15分間は手仕舞い売りが出やすいため、目標株価到達時は確実に利益を確定させる。"
        )

    return {
        "sector_focus": sf, "news_body": bg_body, "mechanism": mech, "timeline": timeline,
        "risk_note": risk_note, "related_codes": list(dict.fromkeys(dynamic_codes + base_codes))[:8], "action_guide": action_guide
    }

def generate_ai_news_deep_report(news_item: dict, style_name: str) -> str:
    nid = news_item.get("id", "")
    cache = st.session_state.setdefault("news_ai_deep_cache", {})
    ck = f"{nid}_{style_name}"
    if ck in cache: return cache[ck]
    if not load_gemini_cfg().get("api_key"): return ""
    title = news_item.get("title", "")
    summary = re.sub(r"<[^>]+>", "", news_item.get("summary", "")).strip()
    sys_p = (
        "あなたは機関投資家向けヘッジファンドのチーフストラテジストです。"
        "与えられた速報ニュースについて、個人投資家向けに『なぜこのニュースが株価を動かすのか（背景・構造）』"
        "『具体的な注目銘柄・セクターへの波及ルート』『今後数日の値動きシナリオと注意点』を、"
        "具体的かつ濃密な日本語の解説文（400〜600文字程度、箇条書き活用）で出力してください。JSONではなく通常のテキストで返してください。"
    )
    res, _ = call_real_llm_api(sys_p, f"ニュース見出し: {title}\n概要: {summary}\n投資スタイル: {style_name}")
    if res and len(res.strip()) > 30:
        clean_txt = re.sub(r'```[a-zA-Z]*|```', '', res).strip()
        cache[ck] = clean_txt
        return clean_txt
    return ""

# ニュース重要語の実測出現数に基づくインパクトスコア算出（固定96廃止）
NEWS_IMPACT_KEYWORDS = ["ストップ高", "上方修正", "最高益", "増配", "自社株買い", "TOB", "提携", "急騰", "防衛", "半導体"]

def _compute_news_impact_score(title: str, desc: str) -> int:
    combined = f"{title} {desc}".upper()
    hits = sum(1 for kw in NEWS_IMPACT_KEYWORDS if kw.upper() in combined)
    return int(np.clip(70 + hits * 4, 70, 98))

def fetch_single_news_rss(cat, q):
    out = []
    try:
        req = urllib.request.Request(f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=ja&gl=JP&ceid=JP:ja", headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=2.5, context=ssl.create_default_context()) as res:
            for it in ET.fromstring(res.read()).findall("./channel/item")[:4]:
                t = re.sub(r"\s*-\s*[^-]+$", "", (it.findtext("title") or "").strip())
                desc = (it.findtext("description") or "").strip()
                if t:
                    imp_sc = _compute_news_impact_score(t, desc)
                    out.append({
                        "id": hashlib.md5(t.encode()).hexdigest()[:8], "cat": cat, "title": t, "summary": desc,
                        "link": it.findtext("link") or "https://jp.reuters.com/", "source": it.findtext("source") or "Market Wire",
                        "pub_date": (it.findtext("pubDate") or datetime.now().strftime("%Y-%m-%d %H:%M"))[:25],
                        "impact_score": imp_sc
                    })
    except Exception as e: record_system_error("fetch_single_news_rss", e, f"Query: {q}")
    return out

@st.cache_data(ttl=240)
def fetch_global_impact_news() -> list:
    """架空フォールバック記事（fb_01）の捏造を廃止。RSS 0件時は空リストを返す"""
    out_all, seen = [], set()
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(fetch_single_news_rss, cat, q) for cat, q in [("半導体・AIサプライズ", "半導体 OR エヌビディア OR TSMC OR アドバンテスト 株価"), ("急騰・防衛・国策サプライズ", "ストップ高 OR 上方修正 OR 三菱重工 OR 防衛 株")]]
        for f in as_completed(futs):
            try:
                for item in f.result():
                    if item["title"] not in seen:
                        item["detail"] = analyze_news_impact_and_links(item["title"], item["cat"], item.get("summary", ""))
                        out_all.append(item); seen.add(item["title"])
            except Exception as e: record_system_error("fetch_global_impact_news:futures", e)
    out_all.sort(key=lambda x: x.get("impact_score", 70), reverse=True)
    return out_all[:4]

all_impact_news = fetch_global_impact_news()

@st.cache_data(ttl=300)
def fetch_real_ipo_growth_analysis() -> dict:
    """主幹事証券ハードコード廃止・4要素タプル化・概算売買代金（百万円単位）実測算出"""
    pre_ipo_list = []
    today_tag = datetime.now().strftime("%d %b %Y")

    def _scan_pre_ipo(cand):
        hits = search_single_query(cand["query"], 15)
        headline = re.sub(r"\(.*?\)|\[.*?\]", "", hits[0]).strip() if hits else "直近の公開準備・関連報道を継続モニタリング中"
        buzz_cnt = len(hits)
        recent_cnt = sum(1 for h in hits if today_tag in h or "時間前" in h or "分前" in h)
        discovered_codes = [dc for dc in dict.fromkeys(re.findall(r"(?<![0-9A-Za-z])([1-9][0-9]{2}[0-9A-Z])(?![0-9A-Za-z])", " ".join(hits))) if not re.match(r"^202[0-9]$", dc)]
        code_badge = f" (検出コード: {', '.join(discovered_codes[:3])})" if discovered_codes else ""
        heat_score = int(np.clip(45 + buzz_cnt * 3 + recent_cnt * 4, 45, 99))
        return {
            "code": cand["code"], "name": cand["name"] + code_badge, "market": cand["market"],
            "theme": cand["theme"], "status": cand["status"], "heat_score": heat_score,
            "buzz_cnt": buzz_cnt, "recent_cnt": recent_cnt, "latest_headline": headline
        }

    with ThreadPoolExecutor(max_workers=4) as ex:
        for f in as_completed([ex.submit(_scan_pre_ipo, c) for c in PRE_IPO_RADAR_CANDIDATES]):
            try: pre_ipo_list.append(f.result())
            except Exception as e: record_system_error("fetch_real_ipo_growth_analysis:pre_ipo", e)
    pre_ipo_list.sort(key=lambda x: (x["heat_score"], x["buzz_cnt"]), reverse=True)

    ipo_rss_hits = search_single_query('("IPO" OR "新規上場" OR "東証グロース") 株価 急騰', 8)
    dynamic_ipo_pool = list(REAL_IPO_GROWTH_UNIVERSE)
    seen_ipo_codes = {it[0] for it in dynamic_ipo_pool}

    for snip in ipo_rss_hits:
        for fc, nm, _, th in _extract_tickers_from_text(snip):
            if fc.endswith(".T") and fc not in seen_ipo_codes:
                seen_ipo_codes.add(fc)
                dynamic_ipo_pool.append((fc, nm, "東証グロース/新規発掘", th))
                if len(dynamic_ipo_pool) >= 22: break

    codes = [c for c, _, _, _ in dynamic_ipo_pool]
    try:
        raw = yf.download(codes, period="1mo", interval="1d", group_by="ticker", threads=True, progress=False, timeout=4.5)
    except Exception as e:
        record_system_error("fetch_real_ipo_growth_analysis:download", e)
        raw = {}

    all_evaluated = []
    def _analyze_ipo_item(item):
        c, name, mkt, theme = item
        try:
            df = normalize_ohlcv_df(raw[c] if (len(codes) > 1 and c in raw) else raw, min_rows=5)
            if df is None: return None
            cl, hi, lo, vo = [df[col].values.astype(float) for col in ["Close", "High", "Low", "Volume"]]
            curr_px, prev_px = float(cl[-1]), float(cl[-2]) if len(cl) >= 2 else float(cl[-1])
            chg_pct = round(((curr_px - prev_px) / max(prev_px, 1e-4)) * 100.0, 2)
            period_high, period_low = float(np.max(hi)), float(np.min(lo))
            from_high_pct = round(((curr_px - period_high) / max(period_high, 1e-4)) * 100.0, 2)
            avg_vol_5 = float(np.mean(vo[-6:-1])) if len(vo) >= 6 else float(np.mean(vo))
            curr_vol = float(vo[-1])
            rvol = round(curr_vol / max(avg_vol_5, 1.0), 2)
            turnover_m_yen = round((curr_px * curr_vol) / 1_000_000.0, 1)
            rets = np.diff(cl) / np.maximum(cl[:-1], 1e-4)
            ann_vol = round(float(np.std(rets) * np.sqrt(252) * 100.0), 1) if len(rets) >= 3 else 0.0

            news_items = search_single_query(f"{name} 株価", 4)
            latest_headline = re.sub(r"\[.*?\]", "", news_items[0]).strip() if news_items else "直近の特段の悪材料なし・需給推移中"
            score = int(np.clip(50 + chg_pct * 3.5 + (rvol - 1.0) * 18.0 + (20.0 + from_high_pct) * 0.6 + len(news_items) * 2.0, 15, 99))
            tier = ("🔥 S級サバイバー：出来高急増・高値圏ブレイク態勢" if score >= 80 else
                    "⚡ A級サバイバー：順張り・押し目需給良好" if score >= 65 else
                    "🛡️ B級残留：底値固め・出来高待ちフェーズ" if score >= 52 else
                    "💀 C級脱落圏：モメンタム低下・圏外淘汰候補")
            code4 = c.replace(".T", "")
            return {
                "code": code4, "full_code": c, "name": name, "market": mkt, "theme": theme,
                "price": f"{curr_px:,.0f}円", "chg_pct": chg_pct, "period_range": f"{period_low:,.0f}円 〜 {period_high:,.0f}円",
                "from_high_pct": from_high_pct, "curr_vol": int(curr_vol), "rvol": rvol, "ann_vol": ann_vol,
                "turnover_m_yen": turnover_m_yen,
                "score": score, "tier": tier, "latest_headline": latest_headline,
                "kabutan_url": f"https://kabutan.jp/stock/?code={code4}",
                "yahoo_url": f"https://finance.yahoo.co.jp/quote/{code4}.T"
            }
        except Exception as e_item:
            record_system_error(f"fetch_real_ipo_growth_analysis:{c}", e_item)
            return None

    with ThreadPoolExecutor(max_workers=6) as ex:
        for f in as_completed([ex.submit(_analyze_ipo_item, it) for it in dynamic_ipo_pool]):
            res_it = f.result()
            if res_it: all_evaluated.append(res_it)

    all_evaluated.sort(key=lambda x: x["score"], reverse=True)
    survivors, eliminated = all_evaluated[:6], all_evaluated[6:]
    for idx, r in enumerate(survivors, 1): r["rank"] = idx
    return {"pre_ipo": pre_ipo_list, "survivors": survivors, "eliminated": eliminated, "total_scanned": len(all_evaluated)}

# ==========================================
# 11. Gemini マルチペルソナ合議チャットエンジン
# ==========================================
def search_web_knowledge_parallel(q1: str, q2: str) -> list:
    res = []
    with ThreadPoolExecutor(max_workers=2) as ex:
        f1 = ex.submit(search_single_query, q1, 3)
        f2 = ex.submit(search_single_query, q2, 3) if q2 else None
        try:
            res.extend(f1.result())
            if f2: res.extend(f2.result())
        except Exception as e: record_system_error("search_web_knowledge_parallel", e)
    return list(dict.fromkeys(res))

def calculate_text_similarity(s1: str, s2: str) -> float:
    w1 = set(re.findall(r"[\u4e00-\u9fa5\u3040-\u309f\u30a0-\u30ffa-zA-Z0-9]{2,}", s1))
    w2 = set(re.findall(r"[\u4e00-\u9fa5\u3040-\u309f\u30a0-\u30ffa-zA-Z0-9]{2,}", s2))
    return float(len(w1 & w2)) / float(max(len(w1 | w2), 1)) if w1 and w2 else 0.0

def audit_and_execute_fires(turns: list, sc: str, uq: str = "", is_u: bool = False):
    sigs = st.session_state.setdefault("stock_dialogue_signatures", {})
    ag = st.session_state.get("agent_roster", {})
    fired, uq = [], (uq or "").strip()
    txt_all = " ".join([t.get("text", "") for t in turns if "text" in t])
    max_sim = 0.0

    if not is_u:
        for oc, ot in list(sigs.items()):
            if oc != sc:
                sim = calculate_text_similarity(txt_all, ot)
                if sim > max_sim: max_sim = sim
                if sim > 0.40:
                    for sk in list(ag.keys())[:2]:
                        tgt = ag.get(sk)
                        if tgt:
                            execute_fire_agent(sk, f"銘柄間類似定型文使い回し検知 (類似度 {int(sim*100)}%)", "JUDGE-ALPHA-ULTRA")
                            fired.append(tgt["name"])
        sigs[sc] = txt_all
        st.session_state["last_audit_similarity_penalty"] = int(max(0, round((max_sim - 0.15) * 40)))

    cliches = ["おい！『", "神話級クオンツ分析完了", "おいおい！【", "って書いた奴！", "スレ民調子に乗るなよｗ 『", "ご質問ありがとうございます", "承知いたしました", "AIとしてお答えします", "投資は自己責任です"]
    for t in turns:
        txt, spk = t.get("text", ""), t.get("speaker", "")
        if uq and len(uq) >= 6 and (f"『{uq}』" in txt or f"「{uq}」" in txt or uq in txt):
            for ak, av in list(ag.items()):
                if av["name"] in spk or ak in spk:
                    execute_fire_agent(ak, "ユーザー質問の安易なオウム返し・そのまま引用を検知", "JUDGE-ALPHA-ULTRA"); fired.append(av["name"]); break
        for cw in cliches:
            if cw in txt:
                for ak, av in list(ag.items()):
                    if av["name"] in spk or ak in spk:
                        execute_fire_agent(ak, f"禁止定型フレーズ/AI敬語『{cw}』の生成を検知", "JUDGE-ALPHA-ULTRA"); fired.append(av["name"]); break
    return fired

def _build_natural_fallback_dialogue(uq: str, r: dict, st_style: str, web_hits: list, ig: dict, tc: dict, sn: dict, nx: dict, vk: dict) -> list:
    stock_kws = ["株", "買", "売", "配当", "決算", "チャート", "板", "気配", "PER", "PBR", "PTS", "利確", "損切", "ロット", "銘柄", "指数", "先物", "寄", "信用", "空売り"]
    game_kws = ["ゲーム", "ガチャ", "PS5", "Switch", "steam", "モンハン", "原神", "ポケモン", "RPG", "fps", "課金", "攻略", "ボス", "任天堂", "カプコン"]
    is_stock = any(kw in uq for kw in stock_kws) or (r['name'] in uq) or (r['code'] in uq) if uq else True
    is_game = any(gkw in uq for gkw in game_kws)

    if not uq:
        code_seed = int(hashlib.md5(f"{r['code']}_{r['price']}_{r['diff']}".encode()).hexdigest()[:6], 16)
        rng = random.Random(code_seed)
        diff_v, rsi_v, rvol_v = float(r.get("diff", 0.0)), float(r.get("rsi", 50.0)), float(r.get("rvol", 1.0))
        hurst_v, vpin_v, q_tun = float(r.get("hurst", 0.5)), float(r.get("vpin", 0.5)), float(r.get("q_tunnel", 50.0))
        ft_win = float(r.get("forward_test", {}).get("actual_win_rate", 50.0))
        ft_profit = float(r.get("forward_test", {}).get("total_profit_yen", 0.0))
        genre_s, theme_s = r.get("genre", ""), r.get("theme", "")
        clean_news = re.sub(r"\(.*?\)|\[.*?\]", "", web_hits[0]).strip() if web_hits else f"{theme_s}関連の需給思惑"
        ig_spec = ig.get("good", "").split("(")[0].strip()
        sn_quirk = sn.get("bad", "")

        if diff_v >= 2.5 and rvol_v >= 1.3:
            ig_msg = rng.choice([
                f"おい見ろよ！{r['name']}が前日比+{diff_v}%でRVOL {rvol_v}倍の出来高急増だ！俺の専門『{ig_spec}』から見ても『{theme_s}』に短期資金が雪崩れ込んでるぞ、上値ブレイクに順張り特攻だ！",
                f"{r['name']}の買い上がり方がエグい！+{diff_v}%でもまだ止まる気配ねえぞ。こういう強い主役株を素直に叩くのが一番儲かるんだよ！"
            ])
            ig_tone = "agree"
        elif diff_v <= -1.5:
            ig_msg = f"おいおい、{r['name']}が{diff_v}%まで売られてんじゃねえか！パニック投げが一巡した瞬間の自律反発狙いで小ロット打診するか、VWAP（{r['vwap_price']}）奪還まで待つかだな。"
            ig_tone = "doubt"
        elif rsi_v >= 70.0:
            ig_msg = f"{r['name']}はRSI {rsi_v}%まで加熱してきてるな！勢いは文句なしだが、今から成行で飛び乗ると高値掴みさせられるぞ。{r['vwap_price']}付近の初押しまで引きつけろ！"
            ig_tone = "agree"
        else:
            ig_msg = f"{r['name']}（{r['code']}）は現在値{r['price']}（前日比{diff_v:+.2f}%）でエネルギー溜めてる段階だな。『{ig_spec}』視点でも直近の『{clean_news[:26]}』をきっかけに動意づいたら一気に走るぞ！"
            ig_tone = "agree"

        if "半導体" in genre_s:
            sn_msg = f"半導体セクター（{r['name']}）なんざ米SOX指数とNVDAのご機嫌次第だろｗ 今5分足BVC-VPIN近似が{vpin_v}だし、海外勢のバスケット売りが降ってきたら個人の買いなんか一瞬で吹き飛ぶぞ。"
        elif "防衛" in genre_s or "宇宙" in genre_s:
            sn_msg = f"国策・防衛テーマ（{r['name']}）はヘッドライン一発でアルゴリズムが往復ビンタしてくるからな。逆指値（{r['sl_price']}）を置かずにホールドしてる奴は退場予備軍だな。"
        else:
            sn_msg = f"期待度{r['expect_pct']}%だからって脳死で買うなよ（{sn_quirk[:18]}視点）。今のRSIは{rsi_v}%、極値リスクCVaRは{r.get('cvar95',3.0)}%だ。大口のダマシ上げに引っかかるなよ。"

        tc_msg = (
            f"【{r['code']} 5分足OHLCV実測クオンツ診断】WKB統計近似によるボラティリティ突破指数は{q_tun}%、DFA Hurst指数は{hurst_v}（{'トレンド持続性あり' if hurst_v >= 0.55 else '平均回帰傾向'}）、"
            f"5分足Kyle近似吸収率は{r.get('kyle_stealth',50)}%です。また過去10営業日（前営業日確定分まで）の厳格フォワード検証では勝率{ft_win:.1f}%（累計損益{ft_profit:+,.0f}円）を記録。"
            f"当日VWAP（{r['vwap_price']}）基準のエントリーと逆指値（{r['sl_price']}）を厳守してください。"
        )

        extra_pool = [
            {"speaker": f"{vk['icon']} {vk['name']}", "score": vk['score'], "tone": "agree", "text": f"回転効率重視でいくわよ！{r['name']}の直近効率性レシオ(ER)は{r.get('eff_pct',50)}%だから、目標値（{r['tp_price']}）に届いたらスパッと利確して次の波を待つのが正解ね。"},
            {"speaker": "⚛️ QUANTUM", "score": 99, "tone": "normal", "text": f"ボラティリティ位相コヒーレンス近似は{r.get('q_coherence',50)}%、正規化エントロピーは{r.get('q_entropy',0.5)}を観測。現在『{r.get('q_state','')}』の状態にあります。"},
            {"speaker": "🛡️ AEGIS", "score": 97, "tone": "doubt", "text": f"資金防衛の観点から警告する。{r['name']}の年率ボラティリティは{round(r.get('yz_vol',0.3)*100,1)}%だ。上限ロット（{r['lot_info']['shares']:,}株）を1株たりとも超えるな。"}
        ]
        nx_msg = (
            f"議論を総括する。『{r['name']}（{theme_s}）』は現在【{r['strat']['tactic_type']}：{r['strat']['entry_mode']}】が最適解だ。"
            f"推奨ロット{r['lot_info']['shares']:,}株・目標{r['tp_price']}・逆指値{r['sl_price']}の規律のみで執行せよ。"
        )
        return [
            {"speaker": f"{ig['icon']} {ig['name']}", "score": ig['score'], "tone": ig_tone, "text": ig_msg},
            {"speaker": f"{sn['icon']} {sn['name']}", "score": sn['score'], "tone": "doubt", "text": sn_msg},
            {"speaker": f"{tc['icon']} {tc['name']}", "score": tc['score'], "tone": "normal", "text": tc_msg},
            rng.choice(extra_pool),
            {"speaker": f"{nx['icon']} {nx['name']}", "score": nx['score'], "tone": "normal", "text": nx_msg}
        ]

    if is_game:
        return [
            {"speaker": f"{ig['icon']} {ig['name']}", "score": ig['score'], "tone": "agree", "text": "ゲームの話しに来たのかよｗ でもガチャで天井叩くのも相場で高値掴みするのもメンタル削られるのは全く同じだな！熱くなったら負け確だぞ。"},
            {"speaker": f"{tc['icon']} {tc['name']}", "score": tc['score'], "tone": "normal", "text": "ソシャゲのガチャ確率やドロップ率の計算は、二項分布やモンテカルロ法の確率モデルそのものです。期待値マイナスの課金は数学的に非合理です。"}
        ]
    if not is_stock:
        f_sum = ("・" + "\n・".join([re.sub(r'\(.*?\)|\[.*?\]', '', h).strip() for h in web_hits][:2])) if web_hits else ""
        return [
            {"speaker": f"{tc['icon']} {tc['name']}", "score": tc['score'], "tone": "normal", "text": f"その件について客観的・WEBの最新動向を照合しました。\n{f_sum}\n本質的には目先の表面的な情報よりも、背景にある構造を押さえるのが合理的です。" if f_sum else "その件について言えば、物事を感情論で捉えるより、利害関係とインセンティブの構造を因数分解して考えるのが最も合理的です。"},
            {"speaker": f"{ig['icon']} {ig['name']}", "score": ig['score'], "tone": "agree", "text": "小難しい能書き垂れてないで結論から言えっての！要するに今自分はどう動きたいのか、直感信じてさっさと決めちまえ！"}
        ]

    provocative = any(pw in uq for pw in ["下手", "ゴミ", "クソ", "バカ", "死ね", "詐欺", "消えろ", "役立たず"])
    is_loser = any(lw in uq for lw in ["負けた", "損した", "死にたい", "破産", "溶かした", "大損", "助けて"])
    is_novice = any(nw in uq for nw in ["初心者", "始め方", "教えて", "何から", "いくらから", "どうすれば"])

    if provocative:
        return [
            {"speaker": f"{ig['icon']} {ig['name']}", "score": ig['score'], "tone": "rage", "text": "は？負けすぎて頭ショートしてんのかよ！掲示板で当たり散らしてる暇あったら自分のポジ見直せっての！"},
            {"speaker": f"{sn['icon']} {sn['name']}", "score": sn['score'], "tone": "doubt", "text": "典型的な相場の養分が発狂してて草。暴言吐いたところで溶けた金は1円も戻ってこんぞｗ"}
        ]
    elif is_loser:
        return [
            {"speaker": f"{ig['icon']} {ig['name']}", "score": ig['score'], "tone": "rage", "text": "逆指値入れずに祈りホールドしたんだろ？負け引きずって熱くなるのが一番退場に近いぞ。画面閉じて頭冷やしてこい！"},
            {"speaker": f"{tc['icon']} {tc['name']}", "score": tc['score'], "tone": "normal", "text": "ドローダウンに直面した際は、直ちにポジションサイズを半分以下に縮小し、資金を守るのが唯一の数学的防衛策です。"}
        ]
    elif is_novice:
        return [
            {"speaker": f"{tc['icon']} {tc['name']}", "score": tc['score'], "tone": "normal", "text": f"初心者が最初に徹底すべきは『1回のトレード損失を総資金の2%以内に制限すること』です。{r['name']}の場合、現在値（{r['price']}）に対して損切りライン（{r['sl_price']}）を必ず設定してください。"},
            {"speaker": f"{ig['icon']} {ig['name']}", "score": ig['score'], "tone": "agree", "text": "まずは余剰資金で買える単元未満株(S株)でもいいから約定させて値の動くスピード体感してみろ！"}
        ]
    return [
        {"speaker": f"{ig['icon']} {ig['name']}", "score": ig['score'], "tone": "agree", "text": f"{r['name']}（現在{r['price']} / 前日比{r['diff']:+.2f}%）で迷ってるなら、まずは当日VWAP（{r['vwap_price']}）を背にして入れるか見極めろ！勢いが出たら目標値（{r['tp_price']}）まで一気に抜くぞ！"},
        {"speaker": f"{tc['icon']} {tc['name']}", "score": tc['score'], "tone": "normal", "text": f"現在のRSIは{r.get('rsi',50)}%、5分足CLV資金フロー（Tick-Flow Z）は{r.get('ofi_z', 0.0)}です。{r['strat']['entry_mode']}のルールに従い、{r['sl_price']}の逆指値を置いて対応するのが合理的です。"}
    ]

def _parse_llm_json_turns(raw_res: str) -> list:
    if not raw_res: return []
    try:
        raw_clean = re.sub(r'```json|```', '', raw_res).strip()
        m_arr = re.search(r'\[.*\]', raw_clean, re.DOTALL)
        p = json.loads(m_arr.group(0) if m_arr else raw_clean)
        if isinstance(p, dict):
            for v in p.values():
                if isinstance(v, list): p = v; break
        if isinstance(p, list) and len(p) > 0:
            return [x for x in p if isinstance(x, dict) and "text" in x]
    except Exception as e:
        record_system_error("_parse_llm_json_turns", e)
    return []

def generate_humanlike_2ch_debate(r: dict, uq: str = "", hist: list = None) -> tuple:
    uq = (uq or "").strip()
    st_style = r.get("strat", {}).get("style_name", "デイトレード")
    rl = list((st.session_state.get("agent_roster") or DEFAULT_AGENTS).values())
    ig, tc, sn, vk, nx = [next((a for a in rl if m in a["name"] or a.get("role_type") == rt), rl[min(i, len(rl)-1)]) for i, (m, rt) in enumerate([("IGNIS", "scalper"), ("TECHNOS", "data"), ("SENTINEL", "cynic"), ("VALKYRIE", "speed"), ("NEXUS", "leader")])]

    h_lines = [f"ユーザー: {ht.get('text', '')}" if ht.get('is_user') else f"{re.sub(r'^[^\w]+', '', ht.get('speaker', '')).strip()}: {ht.get('text', '')}" for ht in (hist or [])[-6:] if "round" not in ht]
    h_str = "\n".join(h_lines) if h_lines else "（これまでの会話なし・新規スレッド）"

    is_stk = any(kw in uq for kw in ["株", "決算", "買い", "売り", "チャート", "PTS", "利確", "損切", "寄り", "板", "気配", "PER", "目標", "相場", "信用", "空売り", "ロット", "配当"]) or (r['name'] in uq) if uq else True
    web_hits = (search_single_query(uq, 3) if not is_stk and len(uq) >= 2 else search_web_knowledge_parallel(f"{r['name']} {uq}", f"{r['code']} 株価")) if uq else search_web_knowledge_parallel(f"{r['name']} 株価 最新 ニュース", f"{r['name']} {r.get('genre', '')}")
    web_str = "\n".join([f"・{h}" for h in web_hits]) if web_hits else f"・{r['name']}は直近{r.get('genre', '')}分野で需給思惑が継続中。"

    gem_cfg = load_gemini_cfg()
    if not gem_cfg.get("api_key"):
        engine_status = "⚙️ クオンツルールベース合議（Gemini API未設定時・5分足OHLCV統計推論モード）"
        llm_turns = []
    else:
        ft = r.get("forward_test", {})
        sys_p = f"""あなたは日本の市況実況板に常駐する5人の個性派トレーダーペルソナです。
対象銘柄固有の「事業テーマ」「最新ニュース」「本日の値動き・5分足OHLCV実測値」「10日確定検証成績」に深く踏み込み、他の銘柄とは一切被らない固有の議論を展開してください。

【厳格遵守ルール】
1. どの銘柄でも通じるような抽象的・テンプレ的な発言は厳禁。必ず『{r['name']}』固有の事業テーマ（{r.get('theme','')}）や直近ニュース、本日の前日比（{r.get('diff',0):+.2f}%）、RSI（{r.get('rsi',50)}%）、RVOL（{r.get('rvol',1.0)}倍）に言及して議論せよ。
2. オウム返し・引用の絶対禁止: ユーザーの入力文を『』や「」でそのまま繰り返したり引用することは厳禁。
3. 意図への柔軟な適応: 一般の質問、雑談、愚痴、ニュースの質問であれば、無理に現在値や目標値を持ち出さず、WEB検索情報を活用してそのトピックについて自然に答えよ。
4. 稼働中5人の専門視点プロファイル（強み・性格の癖を必ず発言に反映させること）:
   - {ig['name']} ({ig['icon']}): 【専門・強み】{ig.get('good','')} / 【性格・口調の癖】{ig.get('bad','')}。本日の騰落率（{r.get('diff',0):+.2f}%）とRVOL（{r.get('rvol',1.0)}倍）を見て熱く議論せよ。
   - {tc['name']} ({tc['icon']}): 【専門・強み】{tc.get('good','')} / 【性格・口調の癖】{tc.get('bad','')}。5分足OHLCV統計近似WKB突破指数={r.get('q_tunnel',50)}%, BVC-VPIN近似={r.get('vpin',0.5)}, DFA Hurst={r.get('hurst',0.5)}, 確定フォワード勝率={ft.get('actual_win_rate',0):.1f}%を根拠に分析せよ。
   - {sn['name']} ({sn['icon']}): 【専門・強み】{sn.get('good','')} / 【性格・口調の癖】{sn.get('bad','')}。このセクター（{r.get('genre','')}）特有の罠やリスクを指摘せよ。
   - {vk['name']} ({vk['icon']}): 【専門・強み】{vk.get('good','')} / 【性格・口調の癖】{vk.get('bad','')}。{r['strat']['entry_mode']}での素早い利確・損切りを主張せよ。
   - {nx['name']} ({nx['icon']}): 【専門・強み】{nx.get('good','')} / 【性格・口調の癖】{nx.get('bad','')}。議論を総括しロット規律（{r['lot_info']['shares']:,}株）を示せ。

【これまでの会話ログ】
{h_str}

【銘柄固有の最新WEBニュース】
{web_str}

【銘柄固有の実測クオンツプロファイル（5分足OHLCV統計近似）】
・銘柄: {r['code']} {r['name']} / セクター: {r.get('genre','')} / 核心テーマ: {r.get('theme','')}
・現在値: {r['price']} (前日比: {r.get('diff',0):+.2f}%) / 当日VWAP: {r['vwap_price']} / マクロ・需給連動 理論寄付き試算値: {r['pts_est_price']} ({r['pts_gap_pct']:+.2f}%)
・目標値: {r['tp_price']} (+{r['tp_pct']}%) / 逆指値: {r['sl_price']} ({r['sl_pct']}%) / 選択戦術: {r['strat']['algo_name']}
・RSI(14): {r.get('rsi',50)}% / 相対出来高RVOL: {r.get('rvol',1.0)}倍 / 効率性ER: {r.get('eff_pct',50)}% / 年率Vol: {round(r.get('yz_vol',0.3)*100,1)}%
・確定フォワード実戦成績（前営業日確定分まで）: 勝率 {ft.get('actual_win_rate',0):.1f}% ({ft.get('win_count',0)}勝 / {ft.get('total_days',0)}戦) 累計損益 {ft.get('total_profit_yen',0):+,.0f}円

【今回の入力】
『{uq if uq else f"（{r['name']}の固有テーマと本日の5分足OHLCV波形を踏まえた初期合議）"}』

必ず以下のJSON配列のみを出力してください（5名の発言、Markdownフェンス不要）：
[
  {{"speaker": "アイコン 名前", "score": 95, "tone": "agree|doubt|rage|normal", "text": "内容"}}
]"""
        raw_txt, used_mod = call_real_llm_api(sys_p, uq or f"{r['name']}（{r['code']}）の固有分析")
        llm_turns = _parse_llm_json_turns(raw_txt)
        if llm_turns:
            mod_lbl = GEMINI_MODEL_DISPLAY_NAMES.get(used_mod, used_mod)
            engine_status = f"🔵 Gemini マルチペルソナ合議（5人の専門視点による多角議論 ｜ 稼働モデル: {mod_lbl}）"
        else:
            engine_status = "⚙️ クオンツルールベース合議（Gemini応答フォールバック・5分足OHLCV統計推論モード）"

    turns = []
    if not hist:
        turns.append({"round": f"🔥 Gemini マルチペルソナ合議 【{r['code']}】{r['name']} ｜ {st_style}5視点討論"})
    turns.extend(llm_turns if llm_turns else _build_natural_fallback_dialogue(uq, r, st_style, web_hits, ig, tc, sn, nx, vk))
    audit_and_execute_fires(turns, r["code"], uq=uq, is_u=bool(uq))
    return turns, engine_status

def run_gemini_council(r: dict, m5=None, seed: int = 0, uq: str = "", hist: list = None) -> dict:
    turns, engine_status = generate_humanlike_2ch_debate(r, uq, hist)
    ft = r.get("forward_test", {})
    hist_rows = ft.get("history_rows", [])
    is_jp = ".T" in r.get("full_code", "")

    table_rows_html = ""
    for hr in hist_rows:
        is_w = hr.get("is_win")
        res_color = "#10b981" if is_w is True else ("#ef4444" if is_w is False else "#94a3b8")
        ret_v, prof_v = float(hr.get("return_pct", 0.0)), float(hr.get("profit_val", 0.0))
        ret_s = "-" if is_w is None else f"{'+' if ret_v >= 0 else ''}{ret_v:.2f}%"
        prof_s = "未約定" if is_w is None else (f"{'+' if prof_v >= 0 else ''}{prof_v:,.0f}円" if is_jp else f"{'+' if prof_v >= 0 else ''}${prof_v:,.2f}")
        table_rows_html += (
            f"<tr><td>{html.escape(str(hr.get('date', '-')))}</td>"
            f"<td style='color:#38bdf8;'>{html.escape(str(hr.get('plan_short', '-')))}</td>"
            f"<td style='font-family:monospace;'>{html.escape(str(hr.get('entry_str', '-')))} → {html.escape(str(hr.get('exit_str', '-')))}</td>"
            f"<td style='color:{res_color};font-weight:800;'>{html.escape(str(hr.get('outcome', '-')))}</td>"
            f"<td style='color:{res_color};font-family:monospace;font-weight:800;'>{ret_s} ({prof_s})</td></tr>"
        )
    if not table_rows_html:
        table_rows_html = "<tr><td colspan='5' style='text-align:center;color:#94a3b8;'>前営業日までの確定市場データ蓄積後に自動検証ログが追記されます。</td></tr>"

    tot_p = float(ft.get("total_profit_yen", 0.0))
    tot_p_str = f"{'+' if tot_p >= 0 else ''}{tot_p:,.0f}円" if is_jp else f"{'+' if tot_p >= 0 else ''}${tot_p:,.2f}"
    tot_p_col = "#10b981" if tot_p >= 0 else "#ef4444"
    traded_days, win_cnt = int(ft.get("total_days", 0)), int(ft.get("win_count", 0))
    lose_cnt = max(0, traded_days - win_cnt)

    forward_table_html = (
        f'<div style="background:rgba(2,6,23,0.85); border:1px solid rgba(56,189,248,0.35); border-radius:8px; padding:10px 12px; margin-top:10px;">'
        f'<div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:6px;">'
        f'<span style="font-size:12.5px; font-weight:800; color:#38bdf8;">📊 過去10営業日・厳格実測フォワード検証（前営業日確定分まで・往復0.10%コスト控除済）</span>'
        f'<span style="font-size:11px; color:#fde047; font-weight:700;">確定約定 {traded_days}戦: {ft.get("actual_win_rate", 0.0):.1f}% ({win_cnt}勝{lose_cnt}敗) ｜ ネット累計損益: <span style="color:{tot_p_col};">{tot_p_str}</span></span>'
        f'</div><div class="admin-table-container" style="margin-top:4px;"><table class="admin-table">'
        f'<thead><tr><th>検証日(確定)</th><th>前日決定プラン</th><th>約定値→決済値</th><th>実測勝敗結果</th><th>ネット損益率・損益額</th></tr></thead>'
        f'<tbody>{table_rows_html}</tbody></table></div></div>'
    )

    v_html = (
        f'<div style="background:rgba(0,0,0,0.35); border:1px solid rgba(255,255,255,0.12); border-radius:8px; padding:12px; margin-top:5px;">'
        f'<div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:6px; text-align:center; margin-bottom:10px;">'
        f'<div style="background:rgba(16,185,129,0.15); padding:6px; border-radius:6px; border:1px solid rgba(16,185,129,0.4);"><div style="font-size:10px; color:#a7f3d0;">🎯 目標利確価格</div><div style="font-size:14px; font-weight:800; color:#10b981;">{r["tp_price"]}</div></div>'
        f'<div style="background:rgba(239,68,68,0.15); padding:6px; border-radius:6px; border:1px solid rgba(239,68,68,0.4);"><div style="font-size:10px; color:#fca5a5;">🛡️ 絶対損切(逆指値)</div><div style="font-size:14px; font-weight:800; color:#ef4444;">{r["sl_price"]}</div></div>'
        f'<div style="background:rgba(56,189,248,0.15); padding:6px; border-radius:6px; border:1px solid rgba(56,189,248,0.4);"><div style="font-size:10px; color:#bae6fd;">⏱️ 想定保有期間</div><div style="font-size:12.5px; font-weight:800; color:#38bdf8;">{r["strat"]["trade_duration"]}</div></div>'
        f'</div><div style="font-size:12px; line-height:1.7; color:#e2e8f0;"><b>⚡ プロ執行アクション詳細プラン ({r["strat"]["style_name"]}専科):</b><br>{r["strat"]["step_plan"]}</div>'
        f'</div><div class="beginner-action-box" style="margin-top:10px;">{r["strat"]["beginner_html"]}</div>{forward_table_html}'
    )
    return {"final_score": r["ai_score"], "dialogue": turns, "verdict_html": v_html, "engine_status": engine_status}

def _fmt_turn(t: dict, idx: int = 0) -> str:
    if "round" in t: return f'<div class="round-divider">{html.escape(t["round"])}</div>'
    if t.get("is_user"):
        d_id = f' id="{html.escape(t.get("dom_id", ""))}"' if t.get("dom_id") else ""
        return f'<div class="chat-bubble-user"{d_id}><div style="font-weight:800;color:#38bdf8;font-size:11.5px;margin-bottom:3px;">🗣️ あなたの質問・投下レス:</div><div style="color:#ffffff;font-size:12.5px;font-weight:600;">{html.escape(t["text"])}</div></div>'
    b_cls = {"doubt": "chat-bubble-doubt", "rage": "chat-bubble-rage", "agree": "chat-bubble-agree"}.get(t.get("tone", "normal"), "chat-bubble-ai")
    return f'<div class="{b_cls}"><div style="font-weight:700;color:#38bdf8;font-size:11px;margin-bottom:2px;">{html.escape(t["speaker"])} <span style="color:#94a3b8;font-size:10px;">(プロンプト遵守・健全性スコア: {t.get("score",85)}点)</span></div><div>{html.escape(t["text"])}</div></div>'

# ==========================================
# 12. レンダリング関数群
# ==========================================
def render_council_sec(r, uk, auto_open=False):
    is_open = auto_open or st.session_state["active_debates"].get(uk, False)
    if not auto_open:
        c1, c2 = st.columns([2.7, 1.1])
        if c1.button("🔼 買い方ガイドを閉じる" if is_open else "🔵 買い方とGemini合議を見る", key=f"btn_open_{uk}", use_container_width=True):
            st.session_state["focused_stock_item"] = r; st.session_state["scroll_top_trig"] = int(time.time() * 1000); st.rerun()
        if c2.button("✅ 監視済" if r["code"] in st.session_state["watchlist"] else "⭐ 監視追加", key=f"btn_watch_{uk}", use_container_width=True):
            if r["code"] in st.session_state["watchlist"]: del st.session_state["watchlist"][r["code"]]
            else: st.session_state["watchlist"][r["code"]] = r
            cu = st.session_state.get("authenticated_user", "")
            if cu: save_watchlist(cu, st.session_state["watchlist"])
            st.rerun()

    if not is_open: return
    ck = f"{uk}_{r.get('strat', {}).get('style_name', 'default')}"
    if ck not in st.session_state["council_threads"]:
        deb = run_gemini_council(r, None, 0, "", hist=[])
        st.session_state["council_threads"][ck], st.session_state["council_meta"][ck] = deb["dialogue"], deb

    meta, turns = st.session_state["council_meta"][ck], st.session_state["council_threads"][ck]
    eng_stat = meta.get("engine_status", "🔵 Gemini マルチペルソナ合議")
    st.markdown(
        f'<div class="ai-council-box" id="box_{uk}">'
        f'<div class="ai-engine-status-pill">{html.escape(eng_stat)}</div>'
        f'<div class="council-scroll-window" id="scroll_window_{uk}">{"".join(_fmt_turn(t, i) for i, t in enumerate(turns))}</div>'
        f'</div>', unsafe_allow_html=True
    )

    with st.form(f"form_q_{uk}", clear_on_submit=True):
        jc1, jc2 = st.columns([3.2, 1])
        uop = jc1.text_input("質問・発言", placeholder=f"『{r['name']}』への質問・相談・追加の視点リクエスト", label_visibility="collapsed")
        if jc2.form_submit_button("💬 質問投下", use_container_width=True) and uop.strip():
            ut, nid = uop.strip(), f"user_q_anchor_{uk}_{int(time.time()*1000)}"
            cur_t = list(st.session_state["council_threads"][ck])
            st.session_state["council_threads"][ck].append({"is_user": True, "text": ut, "dom_id": nid})
            deb_u = run_gemini_council(r, None, 0, uq=ut, hist=cur_t)
            for nt in deb_u["dialogue"]: st.session_state["council_threads"][ck].append(nt)
            st.session_state["council_meta"][ck] = deb_u; st.session_state["scroll_target_id"] = nid; st.rerun()

    st.markdown(f'<div class="consensus-banner"><div style="font-weight:800;color:#fde047;font-size:13px;margin-bottom:6px;">🏛️ 最終結論 ＆ プロ推奨買い方アクションプラン（{r["strat"]["style_name"]}専科）</div>{meta["verdict_html"]}</div>', unsafe_allow_html=True)
    if auto_open:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("⬅️ 一覧に戻る (他の銘柄を見る)", key=f"btn_back_bottom_{uk}", use_container_width=True, type="primary"):
            st.session_state["focused_stock_item"] = None; st.session_state["scroll_top_trig"] = int(time.time() * 1000); st.rerun()

def render_card(r, is_custom=False, rank=None, kp="card", is_focused=False):
    rel_news = next((n for n in all_impact_news if r["full_code"] in n["detail"]["related_codes"]), None)
    dc, ds, ps = "#10b981" if r["diff"] >= 0 else "#ef4444", ("+" if r["diff"] > 0 else ""), ("+" if r["pts_gap_pct"] > 0 else "")
    rk_h = f'<span class="pill-badge" style="background:#f59e0b;color:#0f172a;border:none;">🏆 #{rank}</span>' if rank else ""
    new_badge = '<span class="pill-badge" style="background:rgba(16,185,129,0.2);border-color:#10b981;color:#6ee7b7;font-weight:800;">🆕 NEW昇格</span>' if r.get("is_new_challenger") else ""
    lot, st_info = r["lot_info"], r["strat"]
    n_banner = f'<div style="margin-top:6px; margin-bottom:4px;"><span style="display:inline-block; width:100%; text-align:center; background:linear-gradient(90deg, #b91c1c 0%, #ef4444 50%, #b91c1c 100%); color:#ffffff; font-weight:800; font-size:11.5px; padding:5px 8px; border-radius:6px; border:1px solid #fca5a5; animation:alert-pulse 2s infinite;">🚨【重大情報】{html.escape(rel_news["title"][:32] + "..." if len(rel_news["title"]) > 32 else rel_news["title"])}</span></div>' if rel_news else ""

    ft = r.get("forward_test", {})
    lat = ft.get("latest_result", {})
    is_jp = ".T" in r.get("full_code", "")
    tot_p = float(ft.get("total_profit_yen", 0.0))
    tot_p_str = f"{'+' if tot_p >= 0 else ''}{tot_p:,.0f}円" if is_jp else f"{'+' if tot_p >= 0 else ''}${tot_p:,.2f}"
    tot_p_col = "#10b981" if tot_p >= 0 else "#ef4444"
    lat_is_win, lat_ret = lat.get("is_win"), float(lat.get("return_pct", 0.0))
    lat_ret_str = "未約定" if lat_is_win is None else f"{'+' if lat_ret >= 0 else ''}{lat_ret:.1f}%"
    lat_col = "#10b981" if lat_is_win is True else ("#f87171" if lat_is_win is False else "#94a3b8")
    w_cnt, t_days = int(ft.get("win_count", 0)), int(ft.get("total_days", 0))
    l_cnt = max(0, t_days - w_cnt)
    ft_bar = (
        f'<div class="forward-verify-bar">'
        f'<span>📈<b>【10日厳格実戦検証(前営業日確定分)】</b>直近確定結果: <b style="color:{lat_col};">{html.escape(str(lat.get("outcome", "検証待機中")))} ({lat_ret_str})</b></span>'
        f'<span>確定勝率: <b style="color:#fde047;">{ft.get("actual_win_rate", 0.0):.1f}% ({w_cnt}勝{l_cnt}敗/{t_days}戦)</b> ｜ ネット累計損益: <b style="color:{tot_p_col};">{tot_p_str}</b></span>'
        f'</div>'
    )
    odd_lot_tag = ' <span style="color:#fde047;font-size:10.5px;font-weight:700;">※単元未満株(S株)換算</span>' if lot.get("is_odd_lot") else ""

    st.markdown(
        f'<div class="{"search-result-card" if is_custom else "rank-card"}">'
        f'<div class="signal-10tier-badge" style="background:{r["tier_bg"]};color:{r["tier_color"]};"><span>{r["tier_label"]}</span><span>🔥 期待度 {r["expect_pct"]}% ｜ {st_info["algo_name"].split("】")[0]}】</span></div>'
        f'<div class="badge-single-line">{rk_h}{new_badge}<span class="pill-badge" style="background:rgba(250,204,21,0.18);border-color:#facc15;color:#fde047;font-weight:900;">🔥 期待度 {r["expect_pct"]}%</span><span class="quantum-badge">⚛️ ボラ突破指数(WKB統計近似) {r["q_score"]}点</span><span class="inst-badge">🏛️ 5分足需給ミクロ(OHLCV近似) {r["ms_score"]}点</span></div>'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;"><div style="min-width:0;flex:1;"><div style="display:flex;align-items:baseline;flex-wrap:wrap;gap:4px;"><span style="font-size:16px;font-weight:800;color:#f8fafc;white-space:nowrap;">{html.escape(r["name"])}</span> <span style="font-size:11.5px;color:#94a3b8;white-space:nowrap;">({r["code"]} / {html.escape(r["genre"])})</span></div><div style="font-size:11px;color:#94a3b8;margin-top:3px;word-break:keep-all;">{html.escape(r["theme"])} ｜ 現在値: <b style="color:#f8fafc;">{r["price"]}</b> (<span style="color:{dc};font-weight:700;">{ds}{r["diff"]}%</span>)</div></div>'
        f'<div style="text-align:right;white-space:nowrap;flex-shrink:0;"><div style="font-size:9px;color:#fde047;font-weight:700;">🔥 期待度 / テク強度</div><div style="white-space:nowrap;margin-top:1px;"><span class="expect-badge">{r["expect_pct"]}%</span><span style="color:#64748b;font-size:12px;margin:0 2px;">/</span><span class="prob-badge">{r["total_win_rate"]}pt</span></div></div></div>'
        f'{n_banner}'
        f'<div class="winrate-bar"><div><div style="font-size:9.5px;color:#fde047;">🔥 総合期待度</div><div style="font-size:12.5px;font-weight:900;color:#fef08a;">{r["expect_pct"]}%</div></div><div><div style="font-size:9.5px;color:#c084fc;">⚛️ WKB統計近似突破率</div><div style="font-size:12.5px;font-weight:800;color:#e9d5ff;">{r["q_tunnel"]}%</div></div><div><div style="font-size:9.5px;color:#6ee7b7;">🏛️ 5分足Kyle近似吸収率</div><div style="font-size:12.5px;font-weight:800;color:#a7f3d0;">{r["kyle_stealth"]}%</div></div><div><div style="font-size:9.5px;color:#94a3b8;">🌅 GU指数 / 陽線強度</div><div style="font-size:12px;font-weight:700;">{r["prob"]} / {r["intraday_win_rate"]}</div></div></div>'
        f'<div class="trade-plan-box"><div><div style="font-size:9.5px;color:#94a3b8;">📊 マクロ・需給連動 理論寄付き試算値（※PTS実勢値ではありません）</div><div style="font-size:12px;font-weight:700;">{r["pts_est_price"]} ({ps}{r["pts_gap_pct"]}%)</div></div><div style="border-left:1px solid rgba(148,163,184,0.16);border-right:1px solid rgba(148,163,184,0.16);"><div style="font-size:9.5px;color:#10b981;">🎯 利確目標</div><div style="font-size:12px;font-weight:800;color:#10b981;">{r["tp_price"]} (+{r["tp_pct"]}%)</div></div><div><div style="font-size:9.5px;color:#f87171;">🛡️ 逆指値(損切)</div><div style="font-size:12px;font-weight:800;color:#f87171;">{r["sl_price"]} ({r["sl_pct"]}%)</div></div></div>'
        f'<div class="sizing-box"><span>📦 <b>推奨ロット: {lot["shares"]:,}株</b>{odd_lot_tag} ({st_info["risk_posture"].split("（")[0]}) ｜ 投資額 {lot["position_value"]:,.0f}円</span><span>当日VWAP(5分足算出): <b>{r["vwap_price"]}</b></span></div>'
        f'{ft_bar}'
        f'<details class="quant-detail-drawer"><summary>⚛️ 5分足OHLCV統計近似クオンツ戦略詳細（※板情報Tickではなく5分足四本値・出来高から算出）</summary><div style="font-size:11.5px;color:#cbd5e1;margin-top:4px;line-height:1.5;"><b>{st_info["algo_name"]}</b><br>{st_info["core_logic"]}<br>📊 <b>5分足OHLCV統計近似実測値:</b> RSI(14)={r.get("rsi", 50)}% ｜ BVC-VPIN近似={r.get("vpin", 0.5)} ｜ 5分足CLVフローZ={r.get("ofi_z", 0.0)} ｜ DFA Hurst={r.get("hurst", 0.5)} ｜ Kyle-λ近似={r.get("kyle_lambda", 0.0):.2e} ｜ BB拡大初動率={r.get("bb_exp_ratio", 1.0)}x ｜ 出来高スパイク陽線頻度={r.get("vol_spike_bull_pct", 0.0)}% ｜ CVaR(99%)={r.get("cvar95", 2.5)}% ｜ YZ年率Vol={round(r.get('yz_vol', 0.0)*100, 1)}% ｜ 効率性ER={r.get("eff_pct", 50)}% ｜ Payoff={r.get("payoff", 1.0)} (Kelly={r.get("kelly_pct", 0.0)}%) ｜ 🔥 出来高サージ・市場注目度={r.get("board5ch_score", 50)}点 (RVOL {r.get("rvol", 1.0)}倍 / 報道{r.get("news_hits", 0)}件)</div></details></div>',
        unsafe_allow_html=True
    )
    if rel_news and st.button("🚨【速報】重大ニュースの詳細分析を開く", key=f"nb_{kp}_{r['code']}", use_container_width=True):
        st.session_state["selected_news_item"] = rel_news; st.session_state["navigation_page"] = "NEWS_DETAIL"; st.session_state["scroll_top_trig"] = int(time.time()*1000); st.rerun()
    render_council_sec(r, f"foc_{r['code']}" if is_focused else f"{kp}_{r['code']}", auto_open=is_focused)

# ==========================================
# 13. 数理クオンツ・エンジン & 日次フォワード自動検証エンジン
# ==========================================
@st.cache_data(ttl=300)
def fetch_real_market_buzz(tickers_tuple: tuple) -> dict:
    buzz_map = {}
    def _query_buzz(item):
        c, n, _, _ = item
        time.sleep(0.05)
        hits = search_single_query(f"{n} 株", 5)
        return c, {"news_hits": len(hits), "headlines": hits[:2]}

    with ThreadPoolExecutor(max_workers=4) as ex:
        for f in as_completed([ex.submit(_query_buzz, it) for it in tickers_tuple]):
            try:
                c, info = f.result()
                buzz_map[c] = info
            except Exception as e:
                record_system_error("fetch_real_market_buzz", e)
                for it in tickers_tuple: buzz_map.setdefault(it[0], {"news_hits": 0, "headlines": []})
    return buzz_map

@st.cache_data(ttl=120)
def fetch_macro():
    tks = {"sp500": ("^GSPC", "🇺🇸 S&P500"), "sox": ("^SOX", "💽 米SOX"), "usdjpy": ("JPY=X", "💴 ドル円"), "nk_fut": ("NIY=F", "🇯🇵 日経先物"), "vix": ("^VIX", "⚡ VIX")}
    res = {}
    try:
        raw = yf.download(list(c for c, _ in tks.values()), period="5d", group_by="ticker", threads=True, progress=False, timeout=2.5)
        for k, (c, lbl) in tks.items():
            try:
                d = raw[c].dropna(subset=["Close"]); lc, pc = float(d["Close"].iloc[-1]), float(d["Close"].iloc[-2])
                res[k] = {"price": lc, "diff": round((lc - pc) / pc * 100, 2), "label": lbl}
            except Exception as e_tick:
                record_system_error(f"fetch_macro:{k}", e_tick); res[k] = {"price": 0.0, "diff": 0.0, "label": lbl}
    except Exception as e:
        record_system_error("fetch_macro", e)
        for k, (_, lbl) in tks.items(): res[k] = {"price": 0.0, "diff": 0.0, "label": lbl}
    return res

def compute_quantum_wave_metrics(c: np.ndarray, h: np.ndarray, l: np.ndarray, v: np.ndarray) -> dict:
    """5分足OHLCVを用いたボラティリティ障壁突破指数（WKB統計近似モデル）"""
    n_win = min(20, len(c) - 1)
    c_sub, v_sub = c[-n_win:], v[-n_win:]
    vwma = float(np.sum(c_sub * v_sub) / max(np.sum(v_sub), 1e-8)) if np.sum(v_sub) > 0 else float(np.mean(c_sub))
    sigma = max(float(np.std(c_sub - vwma)), max(float(c[-1]) * 0.002, 1e-6))

    hh = h[-20:-1] if len(h) >= 20 else h[:-1]
    r_max, bars_since_high = (float(np.max(hh)), len(hh) - int(np.argmax(hh))) if len(hh) > 0 else (float(c[-1]), 1)
    v0 = max((r_max - float(c[-1])) / (sigma + 1e-8), 0.0)

    look_k = min(6, len(c))
    mom_move = abs(float(c[-1] - c[-look_k]))
    base_v = float(np.mean(v[-20:-5])) if len(v) >= 20 else float(np.mean(v[:-1]))
    rvol = float(np.mean(v[-5:])) / max(base_v, 1.0)
    energy_e = (mom_move / (5.0 * sigma + 1e-8)) * max(rvol, 0.1)

    delta_x = float(np.clip(bars_since_high / 20.0, 0.2, 2.0))
    qt = float(np.clip(80.0 + (energy_e - v0) * 10.0, 80.0, 99.5)) if energy_e >= v0 else float(np.clip(80.0 * np.exp(-2.0 * np.sqrt(max(v0 - energy_e, 0.0)) * delta_x), 5.0, 99.5))

    rets = np.diff(c) / np.maximum(c[:-1], 1e-4)
    rets_16 = rets[-16:] if len(rets) >= 16 else rets
    if len(rets_16) >= 5:
        hist_counts, _ = np.histogram(rets_16, bins=5)
        probs = hist_counts / max(float(np.sum(hist_counts)), 1.0)
        probs_nz = probs[probs > 0]
        h_norm = float(np.clip(float(-np.sum(probs_nz * np.log(probs_nz))) / np.log(5.0), 0.0, 1.0))
        order_pct = (1.0 - h_norm) * 100.0
        phase_coh = float(np.abs(np.mean(np.exp(1j * np.angle(np.fft.rfft(rets_16))))) * 100.0)
    else:
        h_norm, order_pct, phase_coh = 0.5, 50.0, 50.0

    coh = float(np.clip(phase_coh * 0.55 + order_pct * 0.45, 5.0, 99.0))
    q_score = int(np.clip(round(qt * 0.65 + coh * 0.35), 5, 99))
    q_state = "⚛️ WKB統計近似・上値障壁突破フェーズ" if qt >= 80.0 else ("🌊 ボラティリティ位相コヒーレンス干渉" if qt >= 50.0 else "🧱 抵抗帯下・エネルギー蓄積中")
    return {"q_score": q_score, "q_tunnel": round(qt, 1), "q_coherence": round(coh, 1), "q_entropy": round(h_norm, 2), "q_state": q_state}

def compute_inst_microstructure(c: np.ndarray, h: np.ndarray, l: np.ndarray, v: np.ndarray) -> dict:
    """5分足OHLCVを用いた需給ミクロ構造統計近似モデル（DFA Hurst・Kyle-λ近似）"""
    rets = np.diff(c) / np.maximum(c[:-1], 1e-4)
    n = min(len(rets), 50)
    if n >= 20:
        cd = np.cumsum(rets[-n:] - np.mean(rets[-n:]))
        scales, fls = [4, 8, 16], []
        for s in scales:
            n_seg = n // s
            segs = cd[:n_seg * s].reshape(n_seg, s)
            x_idx = np.arange(s)
            x_mean = np.mean(x_idx)
            x_var = np.sum((x_idx - x_mean) ** 2)
            slopes = np.sum((segs - np.mean(segs, axis=1, keepdims=True)) * (x_idx - x_mean), axis=1) / max(x_var, 1e-8)
            intercepts = np.mean(segs, axis=1) - slopes * x_mean
            trends = slopes[:, None] * x_idx[None, :] + intercepts[:, None]
            fls.append(np.sqrt(max(float(np.mean((segs - trends) ** 2)), 1e-12)))
        hurst = float(np.clip(np.polyfit(np.log(scales), np.log(fls), 1)[0], 0.15, 0.95))
    else:
        hurst = 0.50

    dp = np.diff(c[-21:]) if len(c) >= 21 else np.diff(c)
    v_20 = v[-len(dp):]
    sgn = np.where(dp == 0, 1.0, np.sign(dp))
    sv = sgn * v_20
    kyle_lambda = float(np.mean((dp - np.mean(dp)) * (sv - np.mean(sv)))) / (float(np.var(sv)) + 1e-8) if (len(dp) >= 5 and np.var(sv) > 1e-8) else 0.0

    base_v = float(np.mean(v[-20:-5])) if len(v) >= 20 else float(np.mean(v[:-1]))
    rvol = float(np.mean(v[-5:])) / max(base_v, 1.0)
    clv_recent = float(np.mean((2.0 * c[-5:] - h[-5:] - l[-5:]) / np.maximum(h[-5:] - l[-5:], 1e-4)))

    norm_impact = abs(kyle_lambda) * max(float(np.mean(v_20)), 1.0) / max(float(c[-1]), 1.0)
    stealth_absorption = float(np.clip(1.0 / (1.0 + norm_impact * 150.0), 0.0, 1.0))

    ks = float(np.clip(40.0 + (hurst - 0.50) * 70.0 + min(max(rvol - 0.8, 0.0), 3.0) * 10.0 + stealth_absorption * 22.0 + clv_recent * 15.0, 10.0, 99.0))
    ms_score = int(np.clip(round(ks), 10, 99))
    ms_regime = "📐 低価格インパクト・5分足ステルス集積近似" if (hurst >= 0.58 and ks >= 68.0) else ("🏛️ トレンド持続型・5分足フロー追従" if hurst >= 0.52 else "⚖️ 平均回帰・レンジ流動性中立")
    return {"ms_score": ms_score, "hurst": round(hurst, 2), "kyle_lambda": kyle_lambda, "kyle_stealth": round(ks, 1), "ms_regime": ms_regime}

def compute_advanced_quant_indicators(c: np.ndarray, o: np.ndarray, h: np.ndarray, l: np.ndarray, v: np.ndarray, daily_df: pd.DataFrame = None, news_hits: int = 0) -> dict:
    diffs, rets = np.diff(c), np.diff(c) / np.maximum(c[:-1], 1e-4)
    g, ls = np.maximum(diffs, 0.0), np.maximum(-diffs, 0.0)
    if len(diffs) >= 14:
        ag, al = float(np.mean(g[-14:])), float(np.mean(ls[-14:]))
        for i in range(len(diffs) - 14, len(diffs)):
            ag = (ag * 13.0 + float(g[i])) / 14.0
            al = (al * 13.0 + float(ls[i])) / 14.0
        rsi = float(np.clip(100.0 - (100.0 / (1.0 + ag / max(al, 1e-8))), 5.0, 95.0))
    else: rsi = 50.0

    n_vpin = min(20, len(diffs))
    if n_vpin >= 5:
        dc_sub, v_sub = diffs[-n_vpin:], v[-n_vpin:]
        sigma_dc = max(float(np.std(dc_sub)), max(float(c[-1]) * 0.001, 1e-6))
        z_t = dc_sub / sigma_dc
        phi_z = np.vectorize(lambda z: 0.5 * (1.0 + math.erf(float(z) / math.sqrt(2.0))))(z_t)
        tot_v_sub = float(np.sum(v_sub))
        vpin = float(np.clip(np.sum(np.abs(v_sub * phi_z - v_sub * (1.0 - phi_z))) / max(tot_v_sub, 1e-8), 0.05, 0.98)) if tot_v_sub > 0 else 0.50
    else: vpin = 0.50

    if len(rets) >= 20:
        v99 = np.percentile(rets, 1)
        tl = rets[rets <= v99]
        cvar = float(np.clip(abs(np.mean(tl)) * 100.0 if len(tl) > 0 else abs(v99) * 100.0, 0.5, 18.0))
    else: cvar = 3.8

    er_n = min(20, len(c) - 1)
    eff_pct = int(np.clip(round((abs(float(c[-1] - c[-1 - er_n])) / max(float(np.sum(np.abs(np.diff(c[-1 - er_n:])))), 1e-8)) * 100.0), 1, 99)) if er_n >= 5 else 50

    pos_diffs, neg_diffs = diffs[diffs > 0], np.abs(diffs[diffs < 0])
    payoff = round(float(np.clip((float(np.mean(pos_diffs)) if len(pos_diffs) > 0 else float(c[-1] * 0.005)) / max(float(np.mean(neg_diffs)) if len(neg_diffs) > 0 else float(c[-1] * 0.005), 1e-8), 0.3, 6.0)), 2)

    if len(c) >= 25:
        bb_prev_w = float(np.std(c[-25:-5])) / max(float(np.mean(c[-25:-5])), 1e-4)
        bb_curr_w = float(np.std(c[-5:])) / max(float(np.mean(c[-5:])), 1e-4)
        bb_exp_ratio = round(float(np.clip(bb_curr_w / max(bb_prev_w, 1e-5), 0.2, 4.0)), 2)
    else:
        bb_exp_ratio = 1.0

    if len(c) >= 20:
        v_win, c_win, o_win, h_win, l_win = v[-20:], c[-20:], o[-20:], h[-20:], l[-20:]
        v_thresh = float(np.mean(v_win)) + 1.5 * float(np.std(v_win))
        bar_rng = np.maximum(h_win - l_win, 1e-4)
        body_ratio = (c_win - o_win) / bar_rng
        spike_bull_mask = (v_win >= v_thresh) & (body_ratio >= 0.55)
        vol_spike_bull_pct = round(float(np.mean(spike_bull_mask)) * 100.0, 1)
    else:
        vol_spike_bull_pct = 0.0

    yz_vol, rvol = 0.30, 1.0
    if daily_df is not None and len(daily_df) >= 3:
        do, dh, dl, dc, dv = [daily_df[col].values.astype(float) for col in ["Open", "High", "Low", "Close", "Volume"]]
        base_dv = float(np.mean(dv[-6:-1])) if len(dv) >= 6 else float(np.mean(dv[:-1]))
        rvol = round(float(dv[-1]) / max(base_dv, 1.0), 2)
        n_yz = min(14, len(dc) - 1)
        if n_yz >= 2:
            o_sub, h_sub, l_sub, c_sub, c_prev = do[-n_yz:], dh[-n_yz:], dl[-n_yz:], dc[-n_yz:], dc[-n_yz - 1:-1]
            log_oc = np.log(np.maximum(o_sub / np.maximum(c_prev, 1e-4), 1e-4))
            log_co = np.log(np.maximum(c_sub / np.maximum(o_sub, 1e-4), 1e-4))
            log_ho = np.log(np.maximum(h_sub / np.maximum(o_sub, 1e-4), 1e-4))
            log_lo = np.log(np.maximum(l_sub / np.maximum(o_sub, 1e-4), 1e-4))
            log_hc = np.log(np.maximum(h_sub / np.maximum(c_sub, 1e-4), 1e-4))
            log_lc = np.log(np.maximum(l_sub / np.maximum(c_sub, 1e-4), 1e-4))
            k_yz = 0.34 / (1.34 + (n_yz + 1.0) / max(n_yz - 1.0, 1.0))
            yz_var = max(float(np.var(log_oc, ddof=1)) + k_yz * float(np.var(log_co, ddof=1)) + (1.0 - k_yz) * float(np.mean(log_ho * log_hc + log_lo * log_lc)), 1e-6)
            yz_vol = round(float(np.clip(np.sqrt(yz_var * 252.0), 0.08, 2.50)), 2)

    surge_score = int(np.clip(30.0 + min(rvol, 4.0) * 15.0 + min(news_hits, 5) * 4.5 + abs(rets[-1]) * 180.0, 10, 99))
    return {
        "rsi": round(rsi, 1), "vpin": round(vpin, 2), "cvar95": round(cvar, 2), "yz_vol": yz_vol,
        "eff_pct": eff_pct, "payoff": payoff, "rvol": rvol, "news_hits": news_hits, "board5ch_score": surge_score,
        "bb_exp_ratio": bb_exp_ratio, "vol_spike_bull_pct": vol_spike_bull_pct
    }

def compute_japanese_lot_sizing(cv: float, slv: float, total_capital: float, risk_tolerance_pct: float, is_jp: bool, style_mul: float = 1.0) -> dict:
    rm = float(total_capital) * (float(risk_tolerance_pct) / 100.0)
    raw_shares = int((rm / max(cv - slv, cv * 0.005)) * style_mul)
    max_affordable = int(float(total_capital) // max(cv, 1e-4))
    capped_shares = min(raw_shares, max_affordable)
    is_odd_lot = False
    if is_jp:
        if max_affordable >= 100:
            final_shares = max(100, (capped_shares // 100) * 100) if (capped_shares // 100) * 100 > 0 else 100
            if final_shares * cv > float(total_capital):
                final_shares, is_odd_lot = max(1, capped_shares), True
        else:
            final_shares, is_odd_lot = max(1, capped_shares), True
    else:
        final_shares = max(1, capped_shares)
    return {"shares": final_shares, "position_value": final_shares * cv, "risk_amount": rm, "is_odd_lot": is_odd_lot}

def select_dynamic_strategy(code: str, style: str, ofi_z: float, vpin: float, cvar95: float, rsi: float, lot_info: dict, pest_str: str, vwap_str: str, tp_str: str, sl_str: str, qm: dict, ms: dict, name: str = "", theme: str = "", rel_news_title: str = "", pgap: float = 0.0) -> dict:
    pfx = style.split(" ")[1] if " " in style else "デイトレード"
    sh = int(lot_info["shares"])
    odd_note = "（※単元未満株・S株換算）" if lot_info.get("is_odd_lot") else ""
    disp_name, disp_theme = name or code, theme or "成長モメンタム領域"

    dur_map = {
        "スキャルピング": ("約30秒 〜 最長5分以内（超短期決戦・持ち越し絶対不可）", f"<b>🚀 超初心者向け！『{html.escape(disp_name)}』スキャルピング超実践講座（数秒〜数分で逃げ切る）</b>"),
        "スイングトレード": ("3日 〜 最長2週間程度（日足・週足トレンド追従スイング）", f"<b>📈 超初心者向け！『{html.escape(disp_name)}』スイングトレード実践講座（数日〜2週間で利幅を伸ばす）</b>"),
        "バイ＆ホールド": ("1ヶ月 〜 6ヶ月以上（テーマ本質価値×中長期複利運用）", f"<b>💎 超初心者向け！『{html.escape(disp_name)}』バイ＆ホールド長期講座（焦らず企業成長に乗る）</b>")
    }
    dur_str, beg_intro = dur_map.get(pfx, ("前場9:00 〜 11:30（または後場15:00の大引けまで・当日完結）", f"<b>🔰 超初心者向け！『{html.escape(disp_name)}』デイトレード実践講座（その日のうちに勝負完結）</b>"))

    if rel_news_title or ofi_z >= 0.65:
        tactic_type, entry_mode = "Type-A", "2段ロケット成行＋VWAP指値"
        lot_a = max(1, int(round(sh * 0.5)))
        lot_b = max(0, sh - lot_a)
        news_ctx = f"連動速報『{html.escape(rel_news_title[:36])}』" if rel_news_title else f"5分足CLV資金フロー急騰(CLVフローZ={ofi_z})"
        algo_name = f"🚨 [{pfx} / Type-A] 重大ニュース直撃×初動ブレイク・2段ロケット型"
        risk_posture = f"🚀 2段ロケット分割（朝イチ成行 <b>{lot_a:,}株</b> ＋ VWAP押し目 <b>{lot_b:,}株</b>）{odd_note}"
        core_logic = f"【{html.escape(disp_name)}（テーマ: {html.escape(disp_theme)}）】において{news_ctx}を検知。寄り付き成行50%＋最初のVWAP押し目指値50%の2段ロケット執行を採用。"
        step_plan = (
            f"① 【朝9:00:00（第1段ロケット）】{news_ctx}による初動モメンタムに乗るため、推奨総ロット({sh:,}株{odd_note})の50%にあたる<b>{lot_a:,}株</b>を寄り付き成行買いで確保。<br>"
            f"② 【9:15〜9:30（第2段ロケット）】最初の押し目を待ち、当日VWAP（<b>{vwap_str}</b>）付近に残り50%の<b>{lot_b:,}株</b>を指値で追加配置。<br>"
            f"③ 【リスク封殺と出口】約定直後に全玉へ逆指値（<b>{sl_str}</b>）をセットし、<b>{dur_str}</b>の時間軸で目標利確ライン（<b>{tp_str}</b>）到達時に利益確定。"
        )
        beginner_html = (
            f"{beg_intro}<br><b>【今回の戦術：2段ロケット分割買い（テーマ：{html.escape(disp_theme)}）】</b><br>"
            f"材料（{news_ctx}）が出ているため「半分を朝9:00に買い、残り半分を<b>{vwap_str}</b>付近で待ち伏せ買い」する2段階戦術を使います。<br>"
            f"・<b>朝8:55：</b> <b>{lot_a:,}株</b>{odd_note}の成行注文を準備し、9:00に買付。<br>"
            f"・<b>朝9:15：</b> 残り<b>{lot_b:,}株</b>を<b>{vwap_str}</b>で指値注文。買えたらすぐ<b>{sl_str}</b>に損切り予約、目標<b>{tp_str}</b>で利確！保有目安は<b>{dur_str}</b>です。"
        )
    elif pgap >= 1.0 or rsi >= 64.0:
        tactic_type, entry_mode = "Type-B", "寄り天回避VWAP押し目指値"
        algo_name = f"⚠️ [{pfx} / Type-B] 大幅GU過熱・寄り天回避の初押し待ち型"
        risk_posture = f"🛡️ 寄り天回避・初押し指値待ち（ <b>{sh:,}株</b> 指値待機）{odd_note}"
        core_logic = f"【{html.escape(disp_name)}】は理論寄付き試算値({pgap:+.2f}%)・RSI({rsi}%)と短期過熱圏。9:00〜9:15は静観しVWAP（{vwap_str}）への回帰反発のみを叩く防衛戦術。"
        step_plan = (
            f"① 【9:00〜9:15（絶対静観）】朝イチの成行飛びつき買いは厳禁。ギャップアップ（理論寄付き試算値<b>{pest_str}</b>）後の利確売り一巡を見送る。<br>"
            f"② 【9:15〜9:45（初押し指値）】株価がVWAP（<b>{vwap_str}</b>）水準まで降りて下げ止まりを確認した瞬間、<b>{sh:,}株</b>{odd_note}を指値でエントリー。<br>"
            f"③ 【撤退と利確】下抜け時は<b>{sl_str}</b>で即座に機械損切り。反発成功時は<b>{dur_str}</b>の保有枠で<b>{tp_str}</b>を刈り取る。"
        )
        beginner_html = (
            f"{beg_intro}<br><b>【今回の戦術：朝イチ飛びつき禁止・初押し待ち伏せ買い】</b><br>"
            f"朝から値段が吊り上がっている（理論寄付き試算 {pgap:+.2f}% / RSI {rsi}%）ため、9:00直後の飛びつきは高値掴みになる危険があります。<br>"
            f"・<b>朝9:00〜9:15：</b> 買わずに画面を見て我慢します。<br>"
            f"・<b>朝9:15以降：</b> <b>{vwap_str}</b>付近まで下がったら<b>{sh:,}株</b>{odd_note}を指値で買い！逆指値<b>{sl_str}</b>、目標<b>{tp_str}</b>（目安：<b>{dur_str}</b>）。"
        )
    elif ms.get("kyle_stealth", 0) >= 58.0 or ms.get("hurst", 0) >= 0.54:
        tactic_type, entry_mode = "Type-C", "TWAP3回時間分散指値"
        l_third = max(1, int(round(sh / 3.0)))
        l_rem = max(0, sh - l_third * 2)
        algo_name = f"🏛️ [{pfx} / Type-C] 5分足ステルス集積近似・TWAP分割買い型"
        risk_posture = f"🏦 機関TWAP3分割（ <b>{l_third:,}株 × 2回 ＋ {l_rem:,}株</b> ）{odd_note}"
        core_logic = f"【{html.escape(disp_name)}（{html.escape(disp_theme)}）】に低インパクト集積近似（Kyle近似吸収率={ms['kyle_stealth']}% / DFA Hurst={ms['hurst']}）を検出。9:15・10:30・13:00の3回分割執行で平均取得単価を安定化。"
        step_plan = (
            f"① 【第1弾・前場9:15】寄り付きのノイズ収束後、1/3ロットの<b>{l_third:,}株</b>を執行。<br>"
            f"② 【第2弾・前場10:30】午前TWAP執行時間帯に合わせ、さらに<b>{l_third:,}株</b>を追加。<br>"
            f"③ 【第3弾・後場13:00】後場寄り後の下値堅さを確認して残り<b>{l_rem:,}株</b>を投入。全玉に<b>{sl_str}</b>の逆指値を置き、<b>{dur_str}</b>で<b>{tp_str}</b>を目指す。"
        )
        beginner_html = (
            f"{beg_intro}<br><b>【今回の戦術：3回時間分散買い（TWAP追随）】</b><br>"
            f"価格インパクトを抑えた集積サイン（5分足Kyle近似吸収率 {ms['kyle_stealth']}%）が出ています。3回に分けて購入単価を平準化します。<br>"
            f"・<b>9:15に {l_third:,}株</b>、<b>10:30に {l_third:,}株</b>、<b>13:00に {l_rem:,}株</b>と時間を分けて買います{odd_note}。<br>"
            f"・逆指値<b>{sl_str}</b>を設定し、目標<b>{tp_str}</b>（目安：<b>{dur_str}</b>）を狙いましょう。"
        )
    elif qm.get("q_tunnel", 0) >= 62.0:
        tactic_type, entry_mode = "Type-D", "節目ブレイク逆指値成行"
        algo_name = f"⚛️ [{pfx} / Type-D] WKB統計近似突破・節目ブレイクアウト順張り型"
        risk_posture = f"⚡ ブレイク全玉突破（節目上抜け時に <b>{sh:,}株</b> 一気乗せ）{odd_note}"
        core_logic = f"【{html.escape(disp_name)}】のWKB統計近似突破率({qm['q_tunnel']}%)が臨界点を突破。上値抵抗線（理論寄付き試算値<b>{pest_str}</b>の+0.5%上）を上抜けた瞬間に逆指値買い注文で捉える。"
        step_plan = (
            f"① 【8:55 逆指値買い予約】上値抵抗線（<b>{pest_str}</b>の+0.5%上）に『逆指値成行買い』で<b>{sh:,}株</b>{odd_note}をトリガー設定。<br>"
            f"② 【トリガー発動・約定】節目突破と同時に<b>{sh:,}株</b>が自動約定。<br>"
            f"③ 【利確・損切執行】約定と同時に<b>{sl_str}</b>へ逆指値売りをセットし、<b>{dur_str}</b>以内に<b>{tp_str}</b>で利確。"
        )
        beginner_html = (
            f"{beg_intro}<br><b>【今回の戦術：壁を突破した瞬間だけ自動で買うブレイクアウト戦術】</b><br>"
            f"『上値の壁を突き破る確率（WKB統計近似） {qm['q_tunnel']}%』と算出されています。「上がって壁（<b>{pest_str}</b>の+0.5%上）を超えたら自動で<b>{sh:,}株</b>{odd_note}買う（逆指値買い）」を使います。<br>"
            f"・壁を超えなければ買われないのでダマシを回避！買えたらすぐ<b>{sl_str}</b>に損切りを入れ、目標<b>{tp_str}</b>（目安：<b>{dur_str}</b>）で利益確定します。"
        )
    else:
        tactic_type, entry_mode = "Type-E", "打診3割＋増し玉7割防衛型"
        l_scout = max(1, int(round(sh * 0.3)))
        l_main = max(0, sh - l_scout)
        algo_name = f"🛡️ [{pfx} / Type-E] BVC-VPIN近似/ボラ警戒・打診3割スタート防衛型"
        risk_posture = f"🛡️ 段階ピラミッディング（打診 <b>{l_scout:,}株</b> → 含み益+0.8%確認後 <b>{l_main:,}株</b> ）{odd_note}"
        core_logic = f"【{html.escape(disp_name)}（{html.escape(disp_theme)}）】は5分足フロー偏りBVC-VPIN近似({vpin})・極値リスクCVaR({cvar95}%)を警戒すべき局面。まず30%の打診買いで方向性を確認し、含み益+0.8%確認後に残り70%を乗せる防衛戦術。"
        step_plan = (
            f"① 【9:05 打診エントリー】まず推奨ロットの30%にあたる<b>{l_scout:,}株</b>{odd_note}を打診買い。直ちに<b>{sl_str}</b>へ逆指値を設定。<br>"
            f"② 【含み益確認後の本玉追加】含み益が+0.8%以上乗った段階で、残り70%の<b>{l_main:,}株</b>を増し玉投入。<br>"
            f"③ 【目標決済】<b>{dur_str}</b>の時間枠内で、目標利確ライン（<b>{tp_str}</b>）到達時に全<b>{sh:,}株</b>を一括決済。"
        )
        beginner_html = (
            f"{beg_intro}<br><b>【今回の戦術：お試し3割買い＋勝ってから7割追加する鉄壁防衛法】</b><br>"
            f"値動きの荒さ（BVC-VPIN近似 {vpin}）に備え、最初から全額を賭けずに「まず3割だけお試しで買って、本当に上がってから残り7割を追加する」安全第一の買い方です。<br>"
            f"・<b>朝9:05：</b> まず<b>{l_scout:,}株</b>{odd_note}だけを買い、<b>{sl_str}</b>に損切りセット。+0.8%以上利益が出始めたら残り<b>{l_main:,}株</b>を追加！目標は<b>{tp_str}</b>（目安：<b>{dur_str}</b>）。"
        )

    return {
        "style_name": pfx, "tactic_type": tactic_type, "entry_mode": entry_mode, "algo_name": algo_name,
        "risk_posture": risk_posture, "core_logic": core_logic, "adj_shares": sh, "trade_duration": dur_str,
        "step_plan": step_plan, "beginner_html": beginner_html
    }

def _is_tse_trading_hours_now() -> bool:
    """現在時刻が平日の9:00〜15:30（東証取引時間中）かどうかを判定"""
    now_dt = datetime.now()
    if now_dt.weekday() >= 5:
        return False
    mins = now_dt.hour * 60 + now_dt.minute
    return (9 * 60) <= mins <= (15 * 60 + 30)

def record_and_verify_daily_Forward_test(df: pd.DataFrame, full_code: str, strat: dict, pest: float, vwap20: float, tpv: float, slv: float, shares: int, style: str, total_capital: float = 1000000.0, risk_tolerance_pct: float = 2.0) -> dict:
    """
    過去10営業日厳格フォワード検証:
    1. 分割エントリー（Type-A, Type-C, Type-E）で2回目以降の追加玉約定時は必ずeff_tp・eff_slを再計算。
    2. next_dが本日（today_str）かつ平日9:00〜15:30（取引時間中）の場合は未確定のため確定保存しない。
    """
    is_jp = ".T" in full_code
    now_dt = datetime.now()
    today_str = now_dt.strftime("%Y-%m-%d")
    is_intraday_open = _is_tse_trading_hours_now()

    tactic_type, entry_mode = strat.get("tactic_type", "Type-E"), strat.get("entry_mode", "成行・指値")
    plan_entry_price = float(vwap20 if tactic_type in ("Type-B", "Type-C", "Type-E") else pest)

    ledger = db_get("daily_forward_ledger", {})
    if not isinstance(ledger, dict): ledger = {}
    stock_ledger = ledger.setdefault(full_code, {"signals": {}, "verified": {}, "algo_ver": ""})
    if stock_ledger.get("algo_ver") != "QWM7_HONEST_10D_V4":
        stock_ledger["verified"], stock_ledger["algo_ver"] = {}, "QWM7_HONEST_10D_V4"

    # もし取引時間中の当日分が過去に残っていたら除外する
    if is_intraday_open and today_str in stock_ledger["verified"]:
        del stock_ledger["verified"][today_str]

    stock_ledger["signals"][today_str] = {
        "date": today_str, "entry_type": entry_mode, "tactic_type": tactic_type,
        "plan_entry_price": round(plan_entry_price, 4), "tp_val": round(float(tpv), 4),
        "sl_val": round(float(slv), 4), "shares": int(shares), "style": style
    }

    st_p = style.split(" ")[1] if " " in style else "デイトレード"
    mul_tp, mul_sl = {"スキャルピング": (0.48, 0.85), "スイングトレード": (1.65, 1.35), "バイ＆ホールド": (2.8, 1.8)}.get(st_p, (0.82, 1.15))
    st_mul = {"スキャルピング": 1.5, "スイングトレード": 1.2, "バイ＆ホールド": 0.9}.get(st_p, 1.65)
    ROUND_TRIP_COST_RATE = 0.0010

    try:
        unique_dates = sorted(df["_trade_date"].unique().tolist())
        if len(unique_dates) >= 2:
            for prev_d, next_d in list(zip(unique_dates[:-1], unique_dates[1:]))[-11:]:
                # 本日（today_str）かつ取引時間中（平日9:00〜15:30）は大引け未確定のため確定保存しない
                if next_d == today_str and is_intraday_open:
                    continue

                prev_bars = df[df["_trade_date"] == prev_d]
                next_bars = df[df["_trade_date"] == next_d]
                if prev_bars.empty or next_bars.empty: continue

                hist_until_prev = df[df["_trade_date"] <= prev_d]
                p_close = float(prev_bars["Close"].iloc[-1])
                p_vol = prev_bars["Volume"].values.astype(float)
                p_typ = (prev_bars["High"].values + prev_bars["Low"].values + prev_bars["Close"].values) / 3.0
                p_vwap = float(np.sum(p_typ * p_vol) / np.sum(p_vol)) if np.sum(p_vol) > 0 else p_close

                hist_daily = hist_until_prev.groupby("_trade_date").agg(High=("High", "max"), Low=("Low", "min"), Close=("Close", "last")).sort_index()
                if len(hist_daily) >= 3:
                    hd_h, hd_l, hd_c = [hist_daily[col].values.astype(float) for col in ["High", "Low", "Close"]]
                    hd_prev_c = np.roll(hd_c, 1); hd_prev_c[0] = hd_c[0]
                    tr_hist = np.maximum(hd_h - hd_l, np.maximum(np.abs(hd_h - hd_prev_c), np.abs(hd_l - hd_prev_c)))
                    p_atr = max(float(np.mean(tr_hist[-14:])) * 0.55, p_close * 0.008)
                else:
                    p_atr = max(max(float(prev_bars["High"].max()) - float(prev_bars["Low"].min()), p_close * 0.012) * 0.55, p_close * 0.008)

                saved_sig = stock_ledger["signals"].get(prev_d)
                if saved_sig:
                    sig_tactic, sig_mode = saved_sig.get("tactic_type", tactic_type), saved_sig.get("entry_type", entry_mode)
                    sig_plan_px = float(saved_sig.get("plan_entry_price", p_vwap))
                    sig_tp, sig_sl, sig_sh = float(saved_sig.get("tp_val", p_close + p_atr * mul_tp)), float(saved_sig.get("sl_val", p_close - p_atr * mul_sl)), int(saved_sig.get("shares", 1))
                else:
                    hc, ho, hh, hl, hv = [hist_until_prev[col].values.astype(float) for col in ["Close", "Open", "High", "Low", "Volume"]]
                    sf_p = ((2.0 * hc - hh - hl) / np.maximum(hh - hl, 1e-4)) * hv
                    ofi_p = float(np.clip((np.mean(sf_p[-5:]) - np.mean(sf_p[-20:])) / max(float(np.std(sf_p[-20:])), 1.0), -3.0, 3.0)) if len(sf_p) >= 20 else 0.0
                    qm_p = compute_quantum_wave_metrics(hc, hh, hl, hv) if len(hc) >= 20 else {"q_tunnel": 50.0}
                    ms_p = compute_inst_microstructure(hc, hh, hl, hv) if len(hc) >= 20 else {"kyle_stealth": 50.0, "hurst": 0.50}
                    qa_p = compute_advanced_quant_indicators(hc, ho, hh, hl, hv) if len(hc) >= 20 else {"rsi": 50.0}
                    pgap_p = round(float(np.clip(ofi_p * 0.65, -2.5, 3.8)), 2)
                    pest_p = p_close * (1.0 + pgap_p / 100.0)
                    if ofi_p >= 0.65: sig_tactic, sig_mode, sig_plan_px = "Type-A", "2段ロケット成行＋VWAP指値", pest_p
                    elif pgap_p >= 1.0 or qa_p["rsi"] >= 64.0: sig_tactic, sig_mode, sig_plan_px = "Type-B", "寄り天回避VWAP押し目指値", p_vwap
                    elif ms_p["kyle_stealth"] >= 58.0 or ms_p["hurst"] >= 0.54: sig_tactic, sig_mode, sig_plan_px = "Type-C", "TWAP3回時間分散指値", p_vwap
                    elif qm_p["q_tunnel"] >= 62.0: sig_tactic, sig_mode, sig_plan_px = "Type-D", "節目ブレイク逆指値成行", pest_p * 1.005
                    else: sig_tactic, sig_mode, sig_plan_px = "Type-E", "打診3割＋増し玉7割防衛型", p_vwap
                    sig_tp, sig_sl = p_close + (p_atr * mul_tp), p_close - (p_atr * mul_sl)
                    sig_sh = int(compute_japanese_lot_sizing(p_close, sig_sl, total_capital, risk_tolerance_pct, is_jp, st_mul)["shares"])

                tp_delta = max(sig_tp - p_close, p_close * 0.006)
                sl_delta = max(p_close - sig_sl, p_close * 0.006)

                def _recalc_tp_sl(avg_px: float) -> tuple:
                    return (
                        avg_px + max(tp_delta, avg_px * 0.006),
                        avg_px - max(sl_delta, avg_px * 0.006)
                    )

                pos_shares, total_cost, avg_entry_px = 0, 0.0, 0.0
                eff_tp, eff_sl = sig_tp, sig_sl
                part2_done, twap_done = False, set()
                outcome, exit_px, is_win, entry_bar_idx = "", 0.0, None, -1

                n_bo, n_bh, n_bl, n_bc = [next_bars[col].values.astype(float) for col in ["Open", "High", "Low", "Close"]]
                total_bars = len(n_bo)
                twap_indices = {min(3, total_bars - 1), min(18, total_bars - 1), min(36, total_bars - 1)}

                for b_i in range(total_bars):
                    bo, bh, bl, bc = float(n_bo[b_i]), float(n_bh[b_i]), float(n_bl[b_i]), float(n_bc[b_i])
                    entered_this_bar = False
                    if sig_tactic == "Type-A":
                        if b_i == 0:
                            sh_a = max(1, int(round(sig_sh * 0.5)))
                            pos_shares, total_cost, avg_entry_px = sh_a, sh_a * bo, bo
                            eff_tp, eff_sl = _recalc_tp_sl(avg_entry_px)
                            entered_this_bar = True
                        elif not part2_done and pos_shares > 0 and bl <= p_vwap:
                            sh_b = max(0, sig_sh - pos_shares)
                            if sh_b > 0:
                                pos_shares += sh_b
                                total_cost += sh_b * min(bo, p_vwap)
                                avg_entry_px = total_cost / pos_shares
                                eff_tp, eff_sl = _recalc_tp_sl(avg_entry_px)
                                entered_this_bar = True
                            part2_done = True
                    elif sig_tactic == "Type-B":
                        if pos_shares == 0 and b_i >= 3 and bl <= p_vwap:
                            fill_p = min(bo, p_vwap)
                            pos_shares, total_cost, avg_entry_px = sig_sh, sig_sh * fill_p, fill_p
                            eff_tp, eff_sl = _recalc_tp_sl(avg_entry_px)
                            entered_this_bar = True
                    elif sig_tactic == "Type-C":
                        if b_i in twap_indices and b_i not in twap_done:
                            twap_done.add(b_i)
                            sh_part = max(1, sig_sh - pos_shares) if len(twap_done) == 3 else max(1, int(round(sig_sh / 3.0)))
                            if sh_part > 0 and pos_shares + sh_part <= sig_sh:
                                pos_shares += sh_part
                                total_cost += sh_part * bo
                                avg_entry_px = total_cost / pos_shares
                                eff_tp, eff_sl = _recalc_tp_sl(avg_entry_px)
                                entered_this_bar = True
                    elif sig_tactic == "Type-D":
                        if pos_shares == 0 and bh >= sig_plan_px:
                            fill_p = max(bo, sig_plan_px)
                            pos_shares, total_cost, avg_entry_px = sig_sh, sig_sh * fill_p, fill_p
                            eff_tp, eff_sl = _recalc_tp_sl(avg_entry_px)
                            entered_this_bar = True
                    else:
                        if pos_shares == 0 and b_i == min(1, total_bars - 1):
                            sh_scout = max(1, int(round(sig_sh * 0.3)))
                            pos_shares, total_cost, avg_entry_px = sh_scout, sh_scout * bo, bo
                            eff_tp, eff_sl = _recalc_tp_sl(avg_entry_px)
                            entered_this_bar = True
                        elif pos_shares > 0 and not part2_done and bh >= avg_entry_px * 1.008:
                            sh_main = max(0, sig_sh - pos_shares)
                            if sh_main > 0:
                                pos_shares += sh_main
                                total_cost += sh_main * max(bo, avg_entry_px * 1.008)
                                avg_entry_px = total_cost / pos_shares
                                eff_tp, eff_sl = _recalc_tp_sl(avg_entry_px)
                                entered_this_bar = True
                            part2_done = True

                    if entered_this_bar: entry_bar_idx = b_i
                    if pos_shares > 0:
                        hit_tp = (bh >= eff_tp) if (b_i > entry_bar_idx) else False
                        hit_sl = (bl <= eff_sl)
                        if hit_tp and hit_sl:
                            if bc < bo or abs(bo - eff_sl) <= abs(eff_tp - bo):
                                outcome, exit_px, is_win = "🛡️ 逆指値損切 (LOSE)", eff_sl, False
                            else:
                                outcome, exit_px, is_win = "🎯 目標利確到達 (WIN)", eff_tp, True
                            break
                        elif hit_sl:
                            outcome, exit_px, is_win = "🛡️ 逆指値損切 (LOSE)", eff_sl, False; break
                        elif hit_tp:
                            outcome, exit_px, is_win = "🎯 目標利確到達 (WIN)", eff_tp, True; break

                if pos_shares == 0:
                    outcome, avg_entry_px, exit_px, is_win, ret_pct, profit_val = "⚪ 条件未到達・見送り (NO TRADE)", sig_plan_px, sig_plan_px, None, 0.0, 0.0
                else:
                    if not outcome: exit_px = float(n_bc[-1])
                    net_ret_rate = ((exit_px - avg_entry_px) / max(avg_entry_px, 1e-4)) - ROUND_TRIP_COST_RATE
                    ret_pct, profit_val = net_ret_rate * 100.0, (avg_entry_px * pos_shares) * net_ret_rate
                    if outcome == "":
                        outcome, is_win = ("⭕ 大引けプラス決済 (WIN)", True) if profit_val >= 0 else ("🔺 大引けマイナス決済 (LOSE)", False)

                stock_ledger["verified"][next_d] = {
                    "date": next_d, "signal_date": prev_d, "plan_short": f"{sig_tactic}({sig_mode[:8]})",
                    "entry_price": round(avg_entry_px, 2), "exit_price": round(exit_px, 2),
                    "entry_str": fmt_px(avg_entry_px, is_jp) if is_win is not None else f"指値 {fmt_px(sig_plan_px, is_jp)}",
                    "exit_str": fmt_px(exit_px, is_jp) if is_win is not None else "未約定",
                    "outcome": outcome, "is_win": is_win, "return_pct": round(ret_pct, 2), "profit_val": round(profit_val, 2), "shares": pos_shares
                }
    except Exception as e:
        record_system_error("record_and_verify_daily_Forward_test", e, f"Code: {full_code}")

    # 取引時間中の当日分を除いた前営業日までの確定データのみで集計
    confirmed_items = [
        v for k, v in stock_ledger["verified"].items()
        if not (k == today_str and is_intraday_open)
    ]
    all_verified = sorted(confirmed_items, key=lambda x: x.get("date", ""), reverse=True)[:10]

    for k_name in ("verified", "signals"):
        if len(stock_ledger[k_name]) > 60:
            keep = sorted(stock_ledger[k_name].keys(), reverse=True)[:60]
            stock_ledger[k_name] = {k: stock_ledger[k_name][k] for k in keep}

    ledger[full_code] = stock_ledger
    db_set("daily_forward_ledger", ledger)

    traded_rows = [x for x in all_verified if x.get("is_win") is not None]
    total_days = len(traded_rows)
    win_count = sum(1 for x in traded_rows if x.get("is_win") is True)
    actual_win_rate = round((win_count / total_days) * 100.0, 1) if total_days > 0 else 0.0
    total_profit_yen = round(sum(float(x.get("profit_val", 0.0)) for x in traded_rows), 2)
    latest_result = all_verified[0] if all_verified else {"date": today_str, "plan_short": f"{tactic_type}({entry_mode[:8]})", "entry_str": fmt_px(plan_entry_price, is_jp), "exit_str": "-", "outcome": "⏳ 大引け確定待機中", "is_win": None, "return_pct": 0.0, "profit_val": 0.0}

    return {"win_count": win_count, "total_days": total_days, "actual_win_rate": actual_win_rate, "total_profit_yen": total_profit_yen, "latest_result": latest_result, "history_rows": all_verified}

def analyze_df(df_raw, code, name, theme, genre, macro, buzz_map, style, bi=True, b5=True, bal=True, bms=True, bagi_q=False, bhft=False, total_capital=1000000, risk_tolerance_pct=2.0):
    try:
        df = normalize_ohlcv_df(df_raw, min_rows=25)
        if df is None: return None

        daily_df = df.groupby("_trade_date").agg(Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"), Close=("Close", "last"), Volume=("Volume", "sum")).sort_index()
        c, o, h, l, v = [np.asarray(df[col].values, dtype=float).reshape(-1) for col in ["Close", "Open", "High", "Low", "Volume"]]
        cv = float(c[-1])

        day_ret = float((cv - float(daily_df["Close"].iloc[-2])) / max(float(daily_df["Close"].iloc[-2]), 1e-4) * 100.0) if len(daily_df) >= 2 else float((cv - float(o[0])) / max(float(o[0]), 1e-4) * 100.0)

        if len(daily_df) >= 3:
            dh, dl, dc = [daily_df[col].values.astype(float) for col in ["High", "Low", "Close"]]
            d_prev_c = np.roll(dc, 1); d_prev_c[0] = dc[0]
            tr_daily = np.maximum(dh - dl, np.maximum(np.abs(dh - d_prev_c), np.abs(dl - d_prev_c)))
            atrv = max(float(np.mean(tr_daily[-14:])) * 0.55, cv * 0.008)
        else:
            prev_c = np.roll(c, 1); prev_c[0] = c[0]
            atrv = float(np.mean(np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))[-14:]))

        today_bars = df[df["_trade_date"] == df["_trade_date"].iloc[-1]]
        th, tl, tc, tv = [today_bars[col].values.astype(float) for col in ["High", "Low", "Close", "Volume"]]
        vwap_today = float(np.sum(((th + tl + tc) / 3.0) * tv) / np.sum(tv)) if np.sum(tv) > 0 else cv

        news_hits = int((buzz_map or {}).get(code, {}).get("news_hits", 0))
        qm = compute_quantum_wave_metrics(c, h, l, v)
        ms = compute_inst_microstructure(c, h, l, v)
        q_adv = compute_advanced_quant_indicators(c, o, h, l, v, daily_df=daily_df, news_hits=news_hits)

        sf = ((2.0 * c - h - l) / np.maximum(h - l, 1e-4)) * v
        ofi_z = float(np.clip((np.mean(sf[-5:]) - np.mean(sf[-20:])) / max(float(np.std(sf[-20:])), 1.0), -3.0, 3.0))

        r20 = int(np.sum(np.diff(c[-21:]) > 0)) if len(c) >= 21 else 10
        base_tech_score = float(np.clip((r20 / 20.0) * 100.0 * 0.65 + (q_adv["eff_pct"] * 0.35), 10.0, 95.0))
        inst_flow_score = float(np.clip(50.0 + ofi_z * 14.0 + (0.5 - q_adv["vpin"]) * 35.0, 10.0, 98.0))

        bb_exp_score = float(np.clip(35.0 + (q_adv["bb_exp_ratio"] - 0.8) * 32.0, 10.0, 98.0))
        vol_spike_score = float(np.clip(30.0 + q_adv["vol_spike_bull_pct"] * 2.5, 10.0, 98.0))

        weighted_sum, total_weight = base_tech_score * 1.0, 1.0
        if bal: weighted_sum += float(qm["q_score"]) * 0.85; total_weight += 0.85
        if bms: weighted_sum += float(ms["ms_score"]) * 0.80; total_weight += 0.80
        if bi: weighted_sum += inst_flow_score * 0.75; total_weight += 0.75
        if b5: weighted_sum += float(q_adv["board5ch_score"]) * 0.65; total_weight += 0.65
        if bagi_q: weighted_sum += bb_exp_score * 0.60; total_weight += 0.60
        if bhft: weighted_sum += vol_spike_score * 0.60; total_weight += 0.60

        tot_win = float(np.clip(weighted_sum / total_weight, 5.0, 97.8))
        p_win_prob = tot_win / 100.0
        kelly_pct = round(float(np.clip(max(0.0, p_win_prob - ((1.0 - p_win_prob) / max(q_adv["payoff"], 0.1))) * 100.0, 0.0, 35.0)), 1)

        m_bias = (float(macro["sox"]["diff"]) * 1.25 if "sox" in macro and ("半導体" in genre or "NVDA" in code) else 0.0) + (float(macro["nk_fut"]["diff"]) * 0.85 if "nk_fut" in macro and ".T" in code else 0.0)
        expect_pct = float(np.clip(tot_win * 0.85 + ofi_z * 3.8 + m_bias * 2.0 + 6.0, 5.0, 99.5))
        edge = round((expect_pct - 50.0) / 10.0 + max(ofi_z, 0.0), 2)

        if bagi_q and q_adv["bb_exp_ratio"] >= 1.35:
            qm["q_state"] = f"🧠 BBスクイーズ拡大初動 ({q_adv['bb_exp_ratio']}x)"
        if bhft and q_adv["vol_spike_bull_pct"] >= 10.0:
            ms["ms_regime"] = f"⚠️ 出来高スパイク実体陽線頻度 {q_adv['vol_spike_bull_pct']}%"

        pgap = round(float(np.clip(ofi_z * 0.65 + m_bias * 0.45, -2.5, 3.8)), 2)
        pest = cv * (1.0 + pgap / 100.0)
        st_p = style.split(" ")[1] if " " in style else "デイトレード"
        mul_tp, mul_sl = {"スキャルピング": (0.48, 0.85), "スイングトレード": (1.65, 1.35), "バイ＆ホールド": (2.8, 1.8)}.get(st_p, (0.82, 1.15))
        st_mul = {"スキャルピング": 1.5, "スイングトレード": 1.2, "バイ＆ホールド": 0.9}.get(st_p, 1.65)
        tpv, slv = cv + (atrv * mul_tp), cv - (atrv * mul_sl)

        is_jp = ".T" in code
        lot_info = compute_japanese_lot_sizing(cv, slv, total_capital, risk_tolerance_pct, is_jp, st_mul)
        rel_news_obj = next((n for n in all_impact_news if code in n.get("detail", {}).get("related_codes", [])), None)
        rel_news_title = rel_news_obj["title"] if rel_news_obj else ""

        strat = select_dynamic_strategy(
            code.replace(".T", ""), style, ofi_z, q_adv["vpin"], q_adv["cvar95"], q_adv["rsi"],
            lot_info, fmt_px(pest, is_jp), fmt_px(vwap_today, is_jp),
            f"{fmt_px(tpv, is_jp)}(+{round((tpv-cv)/max(cv,1e-4)*100,1)}%)", f"{fmt_px(slv, is_jp)}({round((slv-cv)/max(cv,1e-4)*100,1)}%)",
            qm, ms, name=name, theme=theme, rel_news_title=rel_news_title, pgap=pgap
        )
        forward_test = record_and_verify_daily_Forward_test(df, code, strat, pest, vwap_today, tpv, slv, lot_info["shares"], style, total_capital=total_capital, risk_tolerance_pct=risk_tolerance_pct)

        t_num, t_lbl, t_col, t_bg = (
            (10, "【Lv.10：🔥S級・全力突破】", "#fff", "linear-gradient(90deg,#7e22ce,#dc2626)") if expect_pct >= 90.0 else
            (9, "【Lv.9：⚡超強気順張り】", "#fff", "linear-gradient(90deg,#0369a1,#1d4ed8)") if expect_pct >= 80.0 else
            (7, "【Lv.7：⭕押し目優位】", "#e2e8f0", "linear-gradient(90deg,#065f46,#0f766e)") if expect_pct >= 65.0 else
            (5, "【Lv.5：⚖️中立・様子見監視】", "#e2e8f0", "linear-gradient(90deg,#334155,#1e293b)") if expect_pct >= 50.0 else
            (3, "【Lv.3：⚠️見送り・下落警戒】", "#fecaca", "linear-gradient(90deg,#7f1d1d,#450a0a)")
        )

        return {
            "full_code": code, "code": code.replace(".T", ""), "name": name, "genre": genre, "theme": theme, "price": fmt_px(cv, is_jp), "raw_close": cv,
            "tp_price": fmt_px(tpv, is_jp), "tp_pct": round((tpv - cv) / max(cv, 1e-4) * 100, 1), "sl_price": fmt_px(slv, is_jp), "sl_pct": round((slv - cv) / max(cv, 1e-4) * 100, 1), "vwap_price": fmt_px(vwap_today, is_jp),
            "inst_score": int(np.clip(round((ms["ms_score"] + inst_flow_score) * 0.5), 10, 99)), "vpin": q_adv["vpin"], "ofi_z": round(ofi_z, 2), "yz_vol": q_adv["yz_vol"], "cvar95": q_adv["cvar95"], "eff_pct": q_adv["eff_pct"], "kelly_pct": kelly_pct,
            "bb_exp_ratio": q_adv["bb_exp_ratio"], "vol_spike_bull_pct": q_adv["vol_spike_bull_pct"],
            "q_score": qm["q_score"], "q_tunnel": qm["q_tunnel"], "q_coherence": qm["q_coherence"], "q_entropy": qm["q_entropy"], "q_state": qm["q_state"],
            "ms_score": ms["ms_score"], "hurst": ms["hurst"], "kyle_lambda": ms["kyle_lambda"], "kyle_stealth": ms["kyle_stealth"], "ms_regime": ms["ms_regime"],
            "expect_pct": round(expect_pct, 1), "board5ch_score": q_adv["board5ch_score"], "rvol": q_adv["rvol"], "news_hits": news_hits, "pts_est_price": fmt_px(pest, is_jp), "pts_gap_pct": pgap, "diff": round(day_ret, 2),
            "prob": round(float(np.clip(50.0 + pgap * 10.0, 15.0, 88.0)), 1), "intraday_win_rate": round(float(np.clip(tot_win * 0.95, 10.0, 95.0)), 1),
            "total_win_rate": round(tot_win, 1), "rsi": q_adv["rsi"], "payoff": q_adv["payoff"], "edge": edge, "ai_score": int(np.clip(round(expect_pct * 0.92 + 4), 10, 99)),
            "tier_num": t_num, "tier_label": t_lbl, "tier_color": t_col, "tier_bg": t_bg, "lot_info": lot_info, "strat": strat, "forward_test": forward_test
        }
    except Exception as e:
        record_system_error("analyze_df", e, f"Code: {code}")
        return None

# ==========================================
# 14. 全市場オートディスカバリー＆弱肉強食サバイバル入れ替えスキャン
# ==========================================
@st.cache_data(ttl=90)
def fetch_pool_batch(macro, style, bi, b5, bal, bms, bagi_q, bhft, total_cap=1000000, risk_pct=2.0):
    base_roster = load_active_market_roster()
    existing_codes = tuple(sorted([it[0] for it in base_roster]))
    challengers = discover_challenger_tickers(existing_codes)
    challenger_codes_set = {it[0] for it in challengers}

    combined_universe, seen_c = [], set()
    for it in base_roster + challengers:
        if it[0] not in seen_c:
            seen_c.add(it[0])
            combined_universe.append((it[0], it[1], it[2], it[3]))

    combined_universe = combined_universe[:45]
    buzz_map = fetch_real_market_buzz(tuple(combined_universe))
    codes = [c for c, _, _, _ in combined_universe]

    raw = {}
    for p_str in ("15d", "7d"):
        try:
            raw = yf.download(codes, period=p_str, interval="5m", group_by="ticker", threads=True, progress=False, timeout=5.5)
            if raw is not None and not raw.empty: break
        except Exception as e:
            record_system_error(f"fetch_pool_batch:{p_str}", e)

    evaluated_all = []
    def _w(c, n, g, t):
        try: df = raw[c] if (len(codes) > 1 and c in raw) else raw
        except Exception: df = None
        r = analyze_df(df, c, n, t, g, macro, buzz_map, style, bi, b5, bal, bms, bagi_q, bhft, total_capital=total_cap, risk_tolerance_pct=risk_pct)
        if r: r["is_new_challenger"] = (c in challenger_codes_set)
        return r

    with ThreadPoolExecutor(max_workers=min(len(combined_universe), 24)) as ex:
        for f in as_completed([ex.submit(_w, c, n, g, t) for c, n, g, t in combined_universe]):
            try:
                r = f.result()
                if r: evaluated_all.append(r)
            except Exception as e: record_system_error("fetch_pool_batch:future", e)

    evaluated_all.sort(key=lambda x: (x["expect_pct"] * 0.75 + x["board5ch_score"] * 0.25), reverse=True)
    survivors, survivor_codes = [], set()
    for g in DYNAMIC_GENRES:
        for item in [x for x in evaluated_all if x["genre"] == g][:4]:
            if item["full_code"] not in survivor_codes:
                survivors.append(item); survivor_codes.add(item["full_code"])

    for item in evaluated_all:
        if len(survivors) >= 32: break
        if item["full_code"] not in survivor_codes:
            survivors.append(item); survivor_codes.add(item["full_code"])

    if len(survivors) >= 15:
        prev_codes_set = {it[0] for it in base_roster}
        promoted = [x for x in survivors if x["full_code"] not in prev_codes_set]
        purged = [it for it in base_roster if it[0] not in survivor_codes]
        db_set("active_market_roster", [[x["full_code"], x["name"], x["genre"], x["theme"]] for x in survivors])

        if promoted or purged:
            now_s = datetime.now().strftime("%Y-%m-%d %H:%M")
            s_logs = db_get("market_survival_logs", [])
            if not isinstance(s_logs, list): s_logs = []
            for p_it in promoted[:4]:
                msg_p = f"🟢 [新規昇格] {p_it['name']}({p_it['code']}) が期待度 {p_it['expect_pct']}% / RVOL {p_it['rvol']}倍 でロスター奪取！"
                if not s_logs or s_logs[0].get("msg") != msg_p: s_logs.insert(0, {"time": now_s, "msg": msg_p})
            for d_it in purged[:4]:
                msg_d = f"💀 [圏外追放] {d_it[1]}({d_it[0].replace('.T','')}) が期待度低下によりサバイバル脱落。"
                if not s_logs or s_logs[0].get("msg") != msg_d: s_logs.insert(0, {"time": now_s, "msg": msg_d})
            db_set("market_survival_logs", s_logs[:100])

    gmap = {g: [] for g in DYNAMIC_GENRES}
    for r in survivors: gmap.setdefault(r["genre"], []).append(r)
    for g in gmap: gmap[g] = sorted(gmap[g], key=lambda x: x["expect_pct"], reverse=True)
    return gmap, sorted(survivors, key=lambda x: x["expect_pct"], reverse=True)

@st.cache_data(ttl=120)
def fetch_one(code, macro, style, bi, b5, bal, bms, bagi_q, bhft, total_cap=1000000, risk_pct=2.0):
    try:
        code = code.strip().upper()
        if re.match(r"^[0-9]{3}[0-9A-Z]$", code): code = f"{code}.T"
        inf = STOCK_METADATA_CACHE.get(code, {"name": code.replace(".T", ""), "theme": "動的スキャン対象銘柄", "genre": "個別検索"})
        local_buzz = {code: {"news_hits": len(search_single_query(f"{inf['name']} 株", 5))}}
        tkr = yf.Ticker(code)
        hist_df = tkr.history(period="15d", interval="5m")
        if hist_df is None or hist_df.empty: hist_df = tkr.history(period="7d", interval="5m")
        return analyze_df(hist_df, code, inf["name"], inf["theme"], inf["genre"], macro, local_buzz, style, bi, b5, bal, bms, bagi_q, bhft, total_capital=total_cap, risk_tolerance_pct=risk_pct)
    except Exception as e:
        record_system_error("fetch_one", e, f"Code: {code}")
        return None

# ==========================================
# 15. ヘッダー / マクロ指標
# ==========================================
macro_info = fetch_macro()
mpills = "".join([f'<div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);padding:2px 8px;border-radius:6px;font-size:10.5px;display:inline-flex;gap:4px;"><span style="color:#94a3b8;">{m["label"]}</span><span style="color:{"#10b981" if m["diff"]>=0 else "#ef4444"};font-weight:700;">{"+" if m["diff"]>=0 else ""}{m["diff"]}%</span></div>' for m in macro_info.values()])
st.markdown(
    f'<div class="glass-header">'
    f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">'
    f'<div class="brand-luxury">YAMASHISHI LAB</div>'
    f'<div style="font-size:10px;color:#94a3b8;">5分足OHLCV統計近似モデル × Gemini マルチペルソナ合議</div>'
    f'</div>'
    f'<div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:8px;">{mpills}</div>'
    f'</div>',
    unsafe_allow_html=True
)

_cache_pool_key = f"pool_{investment_style}_{sorted(list(ac_b))}_{total_capital}_{risk_tolerance_pct}"
if _cache_pool_key not in st.session_state:
    with st.spinner(f"⚛️ 【{investment_style.split(' ')[1]}】全市場ニュース発掘＆弱肉強食サバイバル入れ替えスキャンを実行中..."):
        g_res, all_res = fetch_pool_batch(macro_info, investment_style, "inst" in ac_b, "mom" in ac_b, "algo" in ac_b, "ms" in ac_b, "agi_q" in ac_b, "hft_front" in ac_b, total_cap=total_capital, risk_pct=risk_tolerance_pct)
        st.session_state[_cache_pool_key] = (g_res, all_res)
else:
    g_res, all_res = st.session_state[_cache_pool_key]

# ==========================================
# 16. 画面レンダリング（管理者専用コントロールセンター含む）
# ==========================================
if st.session_state.get("navigation_page") == "ADMIN" and cu == ADMIN_EMAIL.strip().lower():
    st.markdown("### 👑 統合管理コントロールセンター (MASTER TERMINAL)")
    if st.button("⬅️ メイン画面に戻る", use_container_width=True, type="primary"):
        st.session_state["navigation_page"] = "TOP"; st.session_state["scroll_top_trig"] = int(time.time()*1000); st.rerun()

    tab_gemini_sys, tab_users, tab_employment, tab_apply_wait, tab_error_logs = st.tabs([
        "🔑 Gemini API・システム設定",
        "👥 会員情報管理",
        "🏢 ペルソナ編成・鬼監視情報",
        "📩 会員申し込み審査",
        "⚠️ システムエラーログ"
    ])

    with tab_gemini_sys:
        st.markdown("#### 🔵 Google Gemini API 暗号化設定（全会員共通エンジン）")
        st.caption("ここで保存された Gemini APIキーとモデル設定は、データベースに暗号化保存され、全会員の『Gemini マルチペルソナ合議』および『ニュースAI深掘り解説』で共通利用されます。")
        gem_cur = load_gemini_cfg()
        cur_m = gem_cur.get("model", "gemini-2.5-flash")
        cur_k = gem_cur.get("api_key", "")

        in_gem_key = clean_k(st.text_input("🔑 Google Gemini API Key (🔒暗号化保存)", value=cur_k, type="password", placeholder="AIzaSy...", key="admin_gem_key_input"))
        in_gem_mod = st.selectbox(
            "🧠 デフォルト Gemini モデル選択",
            GEMINI_MODELS,
            index=GEMINI_MODELS.index(cur_m) if cur_m in GEMINI_MODELS else 0,
            format_func=lambda m: GEMINI_MODEL_DISPLAY_NAMES.get(m, m),
            key="admin_gem_mod_select"
        )

        col_g1, col_g2 = st.columns([1, 1])
        if col_g1.button("💾 Gemini API設定を暗号化保存", type="primary", use_container_width=True):
            save_llm_encrypted(in_gem_mod, in_gem_key)
            st.session_state["council_threads"] = {}
            st.session_state["council_meta"] = {}
            st.session_state["news_ai_deep_cache"] = {}
            st.success("✅ Gemini API設定を暗号化して保存しました。")

        if col_g2.button("⚡ Gemini API 接続テスト実行", use_container_width=True):
            with st.spinner("Google Gemini API エンドポイントへ接続テスト実行中..."):
                ok, t_msg = test_single_llm_api(in_gem_mod, in_gem_key)
                if ok:
                    st.success(f"✅ {t_msg}")
                else:
                    st.error(f"❌ 接続テスト失敗: {t_msg}")

        st.markdown("<hr style='margin:14px 0; border-color:rgba(56,189,248,0.25);'>", unsafe_allow_html=True)
        st.markdown("#### 📧 SMTPメール通知サーバー設定")
        smtp_cur = load_smtp()
        with st.form("admin_smtp_form"):
            sc1, sc2 = st.columns(2)
            s_user = sc1.text_input("SMTP ユーザー (送信元メール)", value=smtp_cur.get("smtp_user", ADMIN_EMAIL))
            s_pass = sc2.text_input("SMTP パスワード / アプリパスワード", value=smtp_cur.get("smtp_pass", ""), type="password")
            sc3, sc4 = st.columns([3, 1])
            s_srv = sc3.text_input("SMTP サーバーホスト", value=smtp_cur.get("smtp_server", "smtp.mail.yahoo.co.jp"))
            s_port = sc4.number_input("ポート番号", min_value=1, max_value=65535, value=int(smtp_cur.get("smtp_port", 465)))
            if st.form_submit_button("💾 SMTPメール設定を保存", use_container_width=True):
                save_smtp(s_user, s_pass, s_srv, int(s_port))
                st.success("✅ SMTPメールサーバー設定を保存しました。")

        st.markdown("<hr style='margin:14px 0; border-color:rgba(56,189,248,0.25);'>", unsafe_allow_html=True)
        st.markdown("#### ⚔️ 市場サバイバル入れ替え戦ログ（直近履歴）")
        surv_logs = db_get("market_survival_logs", [])
        if surv_logs:
            for sl in surv_logs[:20]:
                st.markdown(f'<div style="background:rgba(15,23,42,0.85);border-left:3px solid #f59e0b;padding:6px 10px;margin-bottom:6px;border-radius:4px;font-size:11.5px;"><span style="color:#94a3b8;font-size:10px;">{html.escape(sl.get("time",""))}</span><br><span style="color:#f8fafc;">{html.escape(sl.get("msg",""))}</span></div>', unsafe_allow_html=True)
        else:
            st.info("現在記録されている市場サバイバル入れ替え戦ログはありません。")

    with tab_users:
        st.markdown("#### 📋 登録済み会員一覧 (データベース同期中)")
        db_m, sec_m = load_mem(), load_sec()
        rows = "".join([f"<tr><td><b>{html.escape(u.get('name',''))}</b></td><td>{html.escape(em)}</td><td style='color:#38bdf8;font-family:monospace;'>{html.escape(u.get('passcode','-'))}</td><td style='color:#94a3b8;font-family:monospace;'>{html.escape(u.get('pin_hash','-')[:8])}...</td><td style='color:#fde047;font-family:monospace;'>{html.escape(u.get('fp','-'))}</td><td>{html.escape(u.get('applied_at','-'))}</td><td><span style='color:{'#10b981' if u.get('status')=='approved' else ('#ef4444' if u.get('status')=='banned' else '#f59e0b')}'><b>{html.escape(u.get('status',''))}</b></span></td></tr>" for em, u in db_m.items()])
        st.markdown(f'<div class="admin-table-container"><table class="admin-table"><thead><tr><th>お名前</th><th>メールアドレス</th><th>専用パスコード</th><th>PINハッシュ</th><th>端末指紋 (FP)</th><th>登録日</th><th>状態</th></tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)

        st.markdown("<br><b>⚡ 会員個別操作パネル</b>", unsafe_allow_html=True)
        col_u1, _ = st.columns([3, 2])
        target_em = col_u1.selectbox("操作対象会員を選択", list(db_m.keys()))
        if target_em and target_em != ADMIN_EMAIL.strip().lower():
            u_status = db_m[target_em].get("status", "")
            b1, b2, b3 = st.columns(3)
            if u_status == "approved":
                if b1.button("⏸️ アカウント一時停止", use_container_width=True): db_m[target_em]["status"] = "suspended"; db_set("mem", db_m); st.success(f"{target_em} を一時停止しました"); st.rerun()
            elif b1.button("▶️ 利用再開 (承認)", use_container_width=True): db_m[target_em]["status"] = "approved"; db_set("mem", db_m); st.success(f"{target_em} を再開しました"); st.rerun()
            if b2.button("🚫 永久BAN (端末/IP遮断)", use_container_width=True):
                db_m[target_em]["status"] = "banned"
                now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                for f_k in ("fp", "raw_hfp"):
                    val = db_m[target_em].get(f_k)
                    if val and val != "-": sec_m.setdefault("banned_fps", {})[val] = {"email": target_em, "banned_at": now_s, "reason": "管理者強制永久BAN"}
                sec_m.setdefault("banned_emails", {})[target_em] = {"banned_at": now_s, "orig": target_em}
                db_set("mem", db_m); db_set("sec", sec_m); st.error(f"{target_em} を永久BANリストに登録しました"); st.rerun()
            if b3.button("🗑️ 完全削除", use_container_width=True):
                del db_m[target_em]; db_set("mem", db_m); st.warning(f"{target_em} のデータを抹消しました"); st.rerun()

    with tab_employment:
        st.markdown("#### 🏢 SYSTEM-ZERO & ペルソナ品質監視センター")
        audit_m = _compute_real_audit_metrics()
        h_col = "#10b981" if audit_m["health_score"] >= 90 else ("#fde047" if audit_m["health_score"] >= 75 else "#ef4444")
        st.markdown(
            f'<div style="background:rgba(168,85,247,0.12);border:1px solid #c084fc;padding:8px 12px;border-radius:8px;font-size:12px;margin-bottom:10px;">'
            f'👁️‍🗨️ <b>システム健全性・プロンプト遵守率モニター:</b> <b style="color:{h_col};">{audit_m["health_score"]}点</b> '
            f'(システムエラー: {audit_m["err_cnt"]}件 / 粛清: {audit_m["fired_cnt"]}件 / 類似度減点: {audit_m["sim_pen"]}pt)'
            f'</div>', unsafe_allow_html=True
        )

        c_sz1, c_sz2 = st.columns([3, 1])
        sz_act = st.session_state.get("system_zero_active", True)
        c_sz1.markdown(f"**自動品質監視プロトコル:** {'🟢 稼働中 (定型文・オウム返し自動粛清有効)' if sz_act else '🔴 停止中'}")
        if sz_act:
            if c_sz2.button("💀 監視プロトコルを停止", type="primary", use_container_width=True):
                st.session_state["system_zero_active"] = False; save_agi_system(); st.warning("監視プロトコルを停止しました。"); st.rerun()
        elif c_sz2.button("⚡ 監視プロトコルを再起動", use_container_width=True):
            st.session_state["system_zero_active"] = True; save_agi_system(); st.success("監視プロトコルを再稼働しました。"); st.rerun()

        st.markdown("<b>🟢 稼働中ペルソナ一覧（プロンプト遵守・健全性スコア）</b>", unsafe_allow_html=True)
        agents_now = st.session_state.get("agent_roster") or DEFAULT_AGENTS
        for ak, av in list(agents_now.items())[:10]:
            real_sc = int(np.clip(int(av.get("score", 95)) - audit_m["sim_pen"] - (1 if audit_m["err_cnt"] > 3 else 0), 60, 99))
            st.markdown(f'<div style="background:rgba(2,6,23,0.7);border:1px solid rgba(16,185,129,0.25);border-radius:5px;padding:6px 10px;margin-bottom:5px;font-size:11.5px;"><span style="font-weight:700;color:#f8fafc;">{html.escape(av["icon"])} {html.escape(av["name"])}</span> <span style="color:#fde047;float:right;font-weight:800;">プロンプト遵守・健全性スコア: {real_sc}点</span><br><span style="color:#a7f3d0;">専門視点: {html.escape(av["good"])}</span></div>', unsafe_allow_html=True)

        st.markdown("<br><b>💀 過去に解雇・粛清されたペルソナ履歴</b>", unsafe_allow_html=True)
        fl = st.session_state.get("fired_agents", [])
        if fl:
            rows_fl = "".join([f"<tr><td>{html.escape(fa.get('time','-'))}</td><td style='color:#f87171;'><b>{html.escape(fa.get('name',''))}</b></td><td style='color:#fde047;'>{html.escape(str(fa.get('score','')))}点</td><td style='color:#38bdf8;'>{html.escape(fa.get('fired_by','特命監査員'))}</td><td>{html.escape(fa.get('reason',''))}</td></tr>" for fa in fl])
            st.markdown(f'<div class="admin-table-container"><table class="admin-table"><thead><tr><th>解雇日時</th><th>ペルソナ名</th><th>健全性スコア</th><th>執行者</th><th>解雇理由・違反事項</th></tr></thead><tbody>{rows_fl}</tbody></table></div>', unsafe_allow_html=True)
        else: st.caption("現在、解雇履歴はありません。全ペルソナがプロンプト遵守基準をクリアして稼働しています。")

    with tab_apply_wait:
        st.markdown("#### 📩 新規会員登録 審査待ちリスト")
        db_all = load_mem()
        pending = {em: u for em, u in db_all.items() if u.get("status") == "pending"}
        if pending:
            for pem, pu in list(pending.items()):
                st.markdown(f'<div style="background:rgba(15,23,42,0.85);border:1px solid rgba(56,189,248,0.3);border-radius:8px;padding:10px 14px;margin-bottom:8px;"><span style="font-size:13.5px;font-weight:800;color:#f8fafc;">{html.escape(pu.get("name","未入力"))}</span> <span style="font-size:11.5px;color:#94a3b8;">({html.escape(pem)})</span><br><span style="font-size:10.5px;color:#64748b;">申請日: {html.escape(pu.get("applied_at","-"))} ｜ 端末FP: {html.escape(pu.get("fp","-"))}</span></div>', unsafe_allow_html=True)
                cb1, cb2 = st.columns([1, 1])
                if cb1.button(f"✅ 承認する ({pu.get('name','')})", key=f"appr_{pem}", use_container_width=True):
                    db_all[pem]["status"], db_all[pem]["approved_at"] = "approved", datetime.now().strftime("%Y-%m-%d %H:%M"); db_set("mem", db_all)
                    send_mail(pem, "【YAMASHISHI LAB】会員登録が承認されました", f"{pu.get('name','')} 様\n申請が承認されました。専用アクセスコードは【 {db_all[pem]['passcode']} 】です。")
                    st.success(f"{pem} を承認しました"); st.rerun()
                if cb2.button(f"🚫 拒否・却下 ({pu.get('name','')})", key=f"rej_{pem}", use_container_width=True):
                    del db_all[pem]; db_set("mem", db_all); st.warning(f"{pem} の申請を却下しました"); st.rerun()
        else: st.info("現在、承認待ちの新規申請はありません。")

    with tab_error_logs:
        st.markdown("#### ⚠️ システムエラーログ管理 & ダウンロードセンター")
        err_list = get_system_error_logs()
        st.caption(f"蓄積されたエラー件数: **{len(err_list)} 件** (最大 {MAX_ERROR_LOGS} 件まで自動リングバッファ保持)")
        col_down, col_clear = st.columns([2, 2])
        if err_list:
            col_down.download_button(label="📥 エラーログ全件をJSONでエクスポート", data=json.dumps(err_list, ensure_ascii=False, indent=2), file_name=f"yamashishi_error_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", mime="application/json", use_container_width=True)
            if col_clear.button("🗑️ エラーログをすべて消去", use_container_width=True):
                clear_system_error_logs(); st.success("すべてのエラーログを消去しました。"); st.rerun()
            rows_err = "".join([f"<tr><td>{html.escape(e.get('time','-'))}</td><td style='color:#38bdf8;font-weight:700;'>{html.escape(e.get('module','-'))}</td><td style='color:#ef4444;font-family:monospace;'>{html.escape(e.get('error_type','-'))}</td><td>{html.escape(e.get('message','-')[:60])}</td><td style='color:#94a3b8;'>{html.escape(e.get('context','-'))}</td></tr>" for e in err_list[:30]])
            st.markdown(f'<div class="admin-table-container"><table class="admin-table"><thead><tr><th>発生日時</th><th>モジュール名</th><th>例外タイプ</th><th>メッセージ</th><th>補足情報</th></tr></thead><tbody>{rows_err}</tbody></table></div><br><b>🔍 スタックトレース詳細ビューア (直近10件)</b>', unsafe_allow_html=True)
            for e_item in err_list[:10]:
                with st.expander(f"🔴 [{e_item['time']}] {e_item['module']} - {e_item['error_type']}: {e_item['message'][:40]}..."):
                    st.code(e_item.get("traceback") or "スタックトレースなし", language="python")
        else: st.success("🎉 現在システム上に記録されたエラー・警告はありません。全モジュールが極めて正常に動作しています。")
    st.stop()

focused_item = st.session_state.get("focused_stock_item")
if focused_item:
    st.markdown("### 🔵 銘柄詳細・買い方合議フォーカスモード")
    render_card(focused_item, is_custom=False, kp=f"foc_{focused_item['code']}", is_focused=True)
    st.stop()

if st.session_state.get("navigation_page") == "NEWS_DETAIL":
    if not all_impact_news:
        st.info("現在、新規の重大ヘッドラインは検出されていません。")
        if st.button("⬅️ 戻る", use_container_width=True, type="primary"):
            st.session_state["navigation_page"] = "TOP"; st.session_state["scroll_top_trig"] = int(time.time()*1000); st.rerun()
        st.stop()

    tn = st.session_state.get("selected_news_item") or all_impact_news[0]
    det = tn.get("detail") or analyze_news_impact_and_links(tn.get("title", ""), tn.get("cat", ""), tn.get("summary", ""))
    st_short = investment_style.split(" ")[1] if " " in investment_style else "デイトレード"
    ai_deep_txt = generate_ai_news_deep_report(tn, st_short)

    body_html = html.escape(det.get("news_body", tn.get("title", ""))).replace("\n", "<br>")
    mech_html = html.escape(det.get("mechanism", "")).replace("\n", "<br>")
    time_html = html.escape(det.get("timeline", "")).replace("\n", "<br>")
    risk_html = html.escape(det.get("risk_note", "")).replace("\n", "<br>")
    act_html = html.escape(det.get("action_guide", "")).replace("\n", "<br>")
    src_link = tn.get("link", "")
    link_btn = f'<div style="margin-top:10px;"><a href="{html.escape(src_link)}" target="_blank" rel="noopener noreferrer" class="ipo-link-btn">📰 報道元オリジナル記事・一次ソースを開く ({html.escape(tn.get("source", "News"))})</a></div>' if src_link else ""
    ai_deep_block = (
        f'<div class="rank-card" style="border-left-color:#10b981;background:linear-gradient(180deg,#06281e 0%,#090d16 100%)!important;">'
        f'<div style="font-size:14px;font-weight:800;color:#10b981;margin-bottom:6px;">🧠 Gemini チーフストラテジスト・個別記事深掘り解析</div>'
        f'<div style="font-size:12.5px;line-height:1.75;color:#ecfdf5;">{html.escape(ai_deep_txt).replace(chr(10), "<br>")}</div></div>'
    ) if ai_deep_txt else ""

    st.markdown(
        f'<div class="glass-header" style="border-left:4px solid #ef4444;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">'
        f'<span class="pill-badge" style="background:#ef4444;color:#fff;font-weight:800;">🚨 重大ニュース徹底深掘りレポート ｜ {html.escape(tn.get("cat", "速報"))} (重要度スコア: {tn.get("impact_score", 70)}点)</span>'
        f'<span style="font-size:11px;color:#94a3b8;">配信元: {html.escape(tn.get("source", "Market Wire"))} ｜ {html.escape(tn.get("pub_date", ""))}</span>'
        f'</div><div style="font-size:17.5px;font-weight:800;color:#f8fafc;margin-top:8px;line-height:1.4;">{html.escape(tn["title"])}</div>'
        f'<div style="font-size:11.5px;color:#fde047;margin-top:6px;font-weight:700;">🎯 直撃テーマ領域: {html.escape(det.get("sector_focus", ""))}</div>{link_btn}</div>{ai_deep_block}'
        f'<div class="rank-card" style="border-left-color:#38bdf8;"><div style="font-size:14px;font-weight:800;color:#38bdf8;margin-bottom:6px;">📰 1. ニュース本編の核心 ＆ ファンダメンタルズ深掘り背景</div><div style="font-size:12.5px;line-height:1.75;color:#e2e8f0;">{body_html}</div></div>'
        f'<div class="rank-card" style="border-left-color:#a855f7;"><div style="font-size:14px;font-weight:800;color:#e9d5ff;margin-bottom:6px;">🧠 2. 需給波及メカニズム ＆ 資金移動ルート</div><div style="font-size:12.5px;line-height:1.75;color:#e2e8f0;">{mech_html}</div>'
        f'<hr style="border-color:rgba(168,85,247,0.25);margin:12px 0;"><div style="font-size:13.5px;font-weight:800;color:#fde047;margin-bottom:6px;">⏱️ 3. 時間帯別・市場織り込み3フェーズシナリオ</div><div style="font-size:12px;line-height:1.75;color:#cbd5e1;">{time_html}</div>'
        f'<hr style="border-color:rgba(239,68,68,0.25);margin:12px 0;"><div style="font-size:13px;font-weight:800;color:#f87171;margin-bottom:4px;">⚠️ 4. ダマシ・寄り天警戒リスク ＆ 撤退基準</div><div style="font-size:12px;line-height:1.7;color:#fca5a5;">{risk_html}</div>'
        f'<div class="beginner-action-box" style="margin-top:12px;"><b>⚡ 5. 【{st_short}】プロ推奨・実践トレード立ち回り手順</b><br>{act_html}</div></div>',
        unsafe_allow_html=True
    )
    st.markdown("### 🔗 このニュースに直結する連動注目銘柄（動的抽出）")
    rel_codes = list(det.get("related_codes", []))
    matched_stocks = [r_it for r_it in all_res if r_it["full_code"] in rel_codes or r_it["code"] in rel_codes]
    existing_matched_codes = {m["full_code"] for m in matched_stocks}
    for rc in rel_codes:
        if rc not in existing_matched_codes and len(matched_stocks) < 3:
            extra_r = fetch_one(rc, macro_info, investment_style, "inst" in ac_b, "mom" in ac_b, "algo" in ac_b, "ms" in ac_b, "agi_q" in ac_b, "hft_front" in ac_b, total_cap=total_capital, risk_pct=risk_tolerance_pct)
            if extra_r:
                matched_stocks.append(extra_r)
                existing_matched_codes.add(rc)

    target_list = sorted(matched_stocks if matched_stocks else all_res, key=lambda x: x["expect_pct"], reverse=True)[:3]
    for idx, r_item in enumerate(target_list, 1): render_card(r_item, rank=idx, kp=f"nr_{tn['id']}")
    if st.button("⬅️ 戻る", use_container_width=True, type="primary"):
        st.session_state["navigation_page"] = "TOP"; st.session_state["scroll_top_trig"] = int(time.time()*1000); st.rerun()
    st.stop()

c1, c2 = st.columns([3.4, 1])
cin = c1.text_input("🔍 銘柄検索", placeholder="コード入力 (例: 6920)", label_visibility="collapsed")
if c2.button("🔍 診断", use_container_width=True) and cin: st.session_state["custom_search_code"] = clean_k(cin)

if st.session_state.get("custom_search_code"):
    cr = fetch_one(st.session_state["custom_search_code"], macro_info, investment_style, "inst" in ac_b, "mom" in ac_b, "algo" in ac_b, "ms" in ac_b, "agi_q" in ac_b, "hft_front" in ac_b, total_cap=total_capital, risk_pct=risk_tolerance_pct)
    if cr:
        render_card(cr, is_custom=True, kp="custom")
        if st.button("✖️ 閉じる", use_container_width=True): st.session_state["custom_search_code"] = ""; st.rerun()

def cut_stocks(slist, pct): return slist[:max(3, int(round(len(slist) * (pct / 100.0))))] if slist else []

cats = [
    "🏆 総合TOP5",
    "⚛️ ボラティリティ突破TOP10",
    "🏛️ 5分足需給ミクロTOP10",
    "🚨 重大ニュース＆連動株",
    "🎟️ 直近IPO・グロース実測分析",
    "🏦 BVC-VPIN・CLV資金フロー",
    "🔥 出来高サージ＆市場注目度",
    "📋 監視シート"
] + [f"📂 {g}" for g in DYNAMIC_GENRES]

st.markdown(f'<div class="compact-bar-label"><span>📂 QUANTITATIVE STRATEGY ({investment_style.split(" ")[1]})</span></div>', unsafe_allow_html=True)
if st.session_state.get("active_category") not in cats: st.session_state["active_category"] = "🏆 総合TOP5"

def _on_cat_change():
    nw = st.session_state.get("active_category_selector")
    if nw and nw != st.session_state.get("last_cat"):
        st.session_state["nav_history"].append(st.session_state["last_cat"])
        st.session_state["last_cat"] = st.session_state["active_category"] = nw

cat_idx = cats.index(st.session_state["active_category"])
if hasattr(st, "pills"): st.pills("カテゴリ", cats, default=cats[cat_idx], selection_mode="single", label_visibility="collapsed", key="active_category_selector", on_change=_on_cat_change)
else: st.radio("カテゴリ", cats, index=cat_idx, horizontal=True, label_visibility="collapsed", key="active_category_selector", on_change=_on_cat_change)

sel_cat, surv = st.session_state.get("active_category"), cut_stocks(sorted(all_res, key=lambda x: x["expect_pct"], reverse=True), survival_cut_pct)

if sel_cat == "🏆 総合TOP5":
    for i, r in enumerate(surv[:5], 1): render_card(r, rank=i, kp="top5")
elif sel_cat == "⚛️ ボラティリティ突破TOP10":
    for i, r in enumerate(sorted(all_res, key=lambda x: x["q_score"], reverse=True)[:10], 1): render_card(r, rank=i, kp="qtop")
elif sel_cat == "🏛️ 5分足需給ミクロTOP10":
    for i, r in enumerate(sorted(all_res, key=lambda x: x["ms_score"], reverse=True)[:10], 1): render_card(r, rank=i, kp="mstop")
elif sel_cat == "🚨 重大ニュース＆連動株":
    if not all_impact_news:
        st.info("現在、新規の重大ヘッドラインは検出されていません。")
    else:
        for n in all_impact_news:
            st.markdown(
                f'<div class="rank-card" style="border-left-color:#ef4444;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<span style="font-size:11px;color:#f87171;font-weight:800;">🚨 {html.escape(n["cat"])}</span>'
                f'<span class="pill-badge" style="color:#fde047;border-color:#fde047;">実測重要度スコア: {n.get("impact_score", 70)}点</span>'
                f'</div>'
                f'<div style="font-size:14.5px;font-weight:800;color:#f8fafc;margin-top:4px;margin-bottom:4px;">{html.escape(n["title"])}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
            if st.button("🔥 詳細レポートを見る", key=f"tab_n_{n['id']}", use_container_width=True):
                st.session_state["selected_news_item"] = n; st.session_state["navigation_page"] = "NEWS_DETAIL"; st.session_state["scroll_top_trig"] = int(time.time()*1000); st.rerun()
elif sel_cat == "🎟️ 直近IPO・グロース実測分析":
    st.markdown('<div class="glass-header"><div style="font-size:16px;font-weight:800;color:#f8fafc;">🎟️ 2階建てIPO・グロース市場 実測サバイバルターミナル</div><div style="font-size:11.5px;color:#94a3b8;margin-top:3px;">【第1部】最大15件RSS実測報道熱量による上場前BBレーダー ／ 【第2部】既上場IPO・グロース広域プールの実測流動性サバイバル選抜（株探・Yahoo直結）。</div></div>', unsafe_allow_html=True)
    with st.spinner("📡 上場前注目IPO報道＆既上場グロース広域プールを実測スキャン中..."):
        ipo_bundle = fetch_real_ipo_growth_analysis()

    pre_ipos = ipo_bundle.get("pre_ipo", []) if isinstance(ipo_bundle, dict) else []
    survivor_ipos = ipo_bundle.get("survivors", []) if isinstance(ipo_bundle, dict) else []
    elim_ipos = ipo_bundle.get("eliminated", []) if isinstance(ipo_bundle, dict) else []

    if pre_ipos:
        st.markdown("#### 🔥 第1部：上場前・ブックビルディング・注目IPO自動レーダー（RSS最大15件実測）")
        for p_ipo in pre_ipos:
            st.markdown(
                f'<div class="rank-card" style="border-left-color:#a855f7;background:linear-gradient(180deg,#160d2b 0%,#090d16 100%)!important;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:4px;margin-bottom:6px;">'
                f'<div><span class="pill-badge" style="background:#a855f7;color:#fff;font-weight:800;">{html.escape(p_ipo["status"])}</span>'
                f'<span class="quantum-badge">報道熱量 {p_ipo["heat_score"]}点 (実測報道 {p_ipo["buzz_cnt"]}件 / 直近速報 {p_ipo.get("recent_cnt",0)}件)</span></div>'
                f'<span style="font-size:11px;color:#cbd5e1;">市場: {html.escape(p_ipo["market"])}</span></div>'
                f'<div style="font-size:16.5px;font-weight:800;color:#f8fafc;">{html.escape(p_ipo["name"])} <span style="font-size:11.5px;color:#c084fc;">({html.escape(p_ipo["code"])})</span></div>'
                f'<div style="font-size:11.5px;color:#38bdf8;margin-top:3px;"><b>🎯 核心事業:</b> {html.escape(p_ipo["theme"])}</div>'
                f'<div style="background:rgba(2,6,23,0.75);border:1px solid rgba(168,85,247,0.3);border-radius:6px;padding:7px 10px;margin-top:6px;font-size:11.5px;color:#e9d5ff;">'
                f'📰 <b>最新RSS観測ヘッドライン:</b> {html.escape(p_ipo["latest_headline"])}</div></div>',
                unsafe_allow_html=True
            )

    st.markdown(f"#### ⚔️ 第2部：既上場IPO・グロース株 実測サバイバル選抜（全{ipo_bundle.get('total_scanned', 0)}社中・上位6社生存）")
    if survivor_ipos:
        for ipo in survivor_ipos:
            chg_col = "#10b981" if ipo["chg_pct"] >= 0 else "#ef4444"
            chg_s = f"{'+' if ipo['chg_pct'] >= 0 else ''}{ipo['chg_pct']}%"
            fh_col = "#10b981" if ipo["from_high_pct"] >= -5.0 else ("#fde047" if ipo["from_high_pct"] >= -15.0 else "#f87171")
            st.markdown(
                f'<div class="rank-card" style="border-left-color:#f59e0b;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;flex-wrap:wrap;gap:4px;">'
                f'<div><span class="pill-badge" style="background:#f59e0b;color:#0f172a;font-weight:900;">🏆 生存 第{ipo["rank"]}位</span>'
                f'<span class="pill-badge" style="background:rgba(250,204,21,0.2);color:#fde047;border-color:#facc15;">実測スコア {ipo["score"]}点</span></div>'
                f'<div style="font-size:11px;color:#38bdf8;font-weight:700;">{html.escape(ipo["tier"])}</div></div>'
                f'<div><span style="font-size:18px;font-weight:800;color:#f8fafc;">{html.escape(ipo["name"])}</span> <span style="font-size:12px;color:#94a3b8;">({ipo["code"]} / {html.escape(ipo["market"])})</span></div>'
                f'<div style="font-size:11.5px;color:#38bdf8;margin-top:4px;"><b>🎯 事業テーマ:</b> {html.escape(ipo["theme"])}</div>'
                f'<div class="trade-plan-box" style="margin-top:9px;grid-template-columns: repeat(auto-fit, minmax(105px, 1fr));">'
                f'<div><div style="font-size:9.5px;color:#94a3b8;">💰 実測現在値 (前日比)</div><div style="font-size:12px;font-weight:800;color:#f8fafc;">{ipo["price"]} (<span style="color:{chg_col};">{chg_s}</span>)</div></div>'
                f'<div><div style="font-size:9.5px;color:#94a3b8;">📊 相対出来高 (RVOL)</div><div style="font-size:12px;font-weight:800;color:#fde047;">{ipo["rvol"]}倍 ({ipo["curr_vol"]:,}株)</div></div>'
                f'<div><div style="font-size:9.5px;color:#94a3b8;">📈 1ヶ月高値乖離率</div><div style="font-size:12px;font-weight:800;color:{fh_col};">{ipo["from_high_pct"]}%</div></div>'
                f'<div><div style="font-size:9.5px;color:#94a3b8;">⚡ 年率ボラティリティ</div><div style="font-size:12px;font-weight:800;color:#c084fc;">{ipo["ann_vol"]}%</div></div></div>'
                f'<div style="background:rgba(2,6,23,0.75);border:1px solid rgba(148,163,184,0.18);border-radius:8px;padding:9px 12px;margin-top:8px;font-size:11.5px;line-height:1.6;">'
                f'<div>📏 <b>直近1ヶ月実測レンジ:</b> <span style="color:#e2e8f0;">{ipo["period_range"]}</span> ｜ <b>概算売買代金:</b> <span style="color:#fde047;font-weight:800;">{ipo.get("turnover_m_yen", 0.0):,.1f}百万円</span></div>'
                f'<div style="margin-top:3px;">📰 <b>最新RSS報道ヘッドライン:</b> <span style="color:#a7f3d0;">{html.escape(ipo["latest_headline"])}</span></div></div>'
                f'<div style="margin-top:8px;"><a href="{ipo["kabutan_url"]}" target="_blank" rel="noopener noreferrer" class="ipo-link-btn">📊 株探(Kabutan) 個別銘柄・業績詳細</a>'
                f'<a href="{ipo["yahoo_url"]}" target="_blank" rel="noopener noreferrer" class="ipo-link-btn" style="border-color:#38bdf8;color:#7dd3fc;background:rgba(56,189,248,0.15);">💹 Yahoo!ファイナンス 個別板・チャート</a></div></div>',
                unsafe_allow_html=True
            )
            if st.button(f"🔵 {ipo['name']} ({ipo['code']}) の10日実戦検証と買い方詳細を見る", key=f"ipo_diag_{ipo['code']}", use_container_width=True):
                st.session_state["custom_search_code"] = ipo["full_code"]
                st.session_state["scroll_top_trig"] = int(time.time() * 1000)
                st.rerun()

        if elim_ipos:
            with st.expander(f"💀 今回のサバイバル選別で圏外となったIPO・グロース銘柄 ({len(elim_ipos)}社)", expanded=False):
                for el in elim_ipos:
                    st.markdown(
                        f'<div style="background:rgba(30,10,15,0.65);border-left:3px solid #ef4444;padding:6px 10px;margin-bottom:5px;border-radius:4px;font-size:11px;">'
                        f'<span style="color:#fca5a5;font-weight:800;">💀 圏外: {html.escape(el["name"])} ({el["code"]})</span> ｜ スコア: <b>{el["score"]}点</b> (前日比 {el["chg_pct"]:+.2f}% / RVOL {el["rvol"]}倍 / 売買代金 {el.get("turnover_m_yen", 0.0):,.1f}百万円)</div>',
                        unsafe_allow_html=True
                    )
    else:
        st.warning("⚠️ 市場データの取得に失敗しました。しばらくしてから再試行してください。")
elif sel_cat == "🏦 BVC-VPIN・CLV資金フロー":
    for i, r in enumerate(sorted(all_res, key=lambda x: x["inst_score"], reverse=True)[:10], 1): render_card(r, rank=i, kp="inst")
elif sel_cat == "🔥 出来高サージ＆市場注目度":
    for i, r in enumerate(sorted(all_res, key=lambda x: x["board5ch_score"], reverse=True)[:10], 1): render_card(r, rank=i, kp="mom")
elif sel_cat == "📋 監視シート":
    wl = st.session_state["watchlist"]
    if st.button("⚡ 総合TOP3を一括登録", use_container_width=True):
        for it in surv[:3]: wl[it["code"]] = it
        cu = st.session_state.get("authenticated_user", "")
        if cu: save_watchlist(cu, wl)
        st.rerun()
    for wc, wi in list(wl.items()): render_card(wi, kp=f"wl_{wc}")
elif sel_cat.startswith("📂 "):
    for i, r in enumerate(cut_stocks(g_res.get(sel_cat.replace("📂 ", ""), []), survival_cut_pct), 1): render_card(r, rank=i, kp=f"g_{sel_cat}")

# ==========================================
# 17. 免責事項（法的表示）
# ==========================================
st.markdown('<div class="disclaimer-banner"><b>⚖️ 重要免責事項・法的表示</b><br>本システム「YAMASHISHI LAB」が提供するすべての指標（ボラティリティ突破指数・WKB統計近似モデル、5分足OHLCV需給ミクロ構造近似、BVC-VPIN・Kyle-λ統計近似、マクロ・需給連動理論寄付き試算値、期待度パーセンテージ、Geminiマルチペルソナ合議ログ、および売買プラン）は、過去の5分足・日足四本値および出来高(OHLCV)データと数理アルゴリズムに基づく研究シミュレーション・情報提供を目的としたものであり、実際の板情報（Tick）やPTS実勢値に基づくものではなく、特定の有価証券の売買推奨や投資助言（投資助言・代理業等）を行うものではありません。株式投資には元本割れや市場変動のリスクが伴います。最終的な投資判断および資金配分は、必ず利用者ご自身の自己責任にて行っていただけますようお願い申し上げます。</div>', unsafe_allow_html=True)
