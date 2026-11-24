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
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

_ERROR_LOCK, _IN_ERROR_LOGGING, _FALLBACK_ERROR_LOGS, MAX_ERROR_LOGS = threading.RLock(), threading.local(), [], 300

def record_system_error(mod: str, err: Exception, ctx: str = ""):
    if getattr(_IN_ERROR_LOGGING, "active", False): return
    _IN_ERROR_LOGGING.active = True
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        e = {"id": hashlib.md5(f"{now}_{mod}_{err}_{time.time_ns()}".encode()).hexdigest()[:8], "time": now, "module": mod, "error_type": type(err).__name__, "message": str(err), "context": ctx, "traceback": traceback.format_exc()}
        with _ERROR_LOCK:
            _FALLBACK_ERROR_LOGS.insert(0, e); del _FALLBACK_ERROR_LOGS[MAX_ERROR_LOGS:]
            try:
                cur = db_get("system_error_logs", []); cur = cur if isinstance(cur, list) else []
                cur.insert(0, e); db_set("system_error_logs", cur[:MAX_ERROR_LOGS])
            except Exception: pass
    finally: _IN_ERROR_LOGGING.active = False

def get_system_error_logs() -> list:
    try:
        l = db_get("system_error_logs", None)
        if isinstance(l, list): return l
    except Exception: pass
    with _ERROR_LOCK: return list(_FALLBACK_ERROR_LOGS)

def clear_system_error_logs():
    with _ERROR_LOCK: _FALLBACK_ERROR_LOGS.clear()
    try: db_set("system_error_logs", [])
    except Exception: pass

st.set_page_config(page_title="YAMASHISHI LAB", page_icon="⚡", layout="centered", initial_sidebar_state="collapsed")

def _get_sec_val(env_k: str, fpath: str, gen_fn):
    val = os.environ.get(env_k)
    if not val:
        try:
            if hasattr(st, "secrets") and env_k in st.secrets: val = st.secrets[env_k]
        except Exception: val = None
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

def _safe_get_env_or_secret(k: str) -> str:
    val = os.environ.get(k)
    if val: return str(val).strip()
    try:
        if hasattr(st, "secrets") and k in st.secrets: return str(st.secrets[k]).strip()
    except Exception: pass
    return ""

SECRET_KEY = _get_sec_val("SECRET_KEY", ".yamashishi_sys_seed.key", lambda: hashlib.sha3_512(f"{secrets.token_hex(64)}:{time.time_ns()}".encode()).hexdigest())
ADMIN_EMAIL = (_safe_get_env_or_secret("ADMIN_EMAIL") or "nthbh399@ybb.ne.jp").strip().lower()
ADMIN_PASS = _get_sec_val("ADMIN_PASS", ".yamashishi_cred.lock", lambda: "ADMIN777").strip()
DB_SQLITE_PATH = "yamashishi_core.db"

def _get_supabase_config() -> tuple:
    sb_url = _safe_get_env_or_secret("SUPABASE_URL").rstrip("/")
    sb_key = _safe_get_env_or_secret("SUPABASE_KEY") or _safe_get_env_or_secret("SUPABASE_ANON_KEY") or _safe_get_env_or_secret("SUPABASE_SERVICE_ROLE_KEY")
    if sb_url and sb_key:
        return sb_url, sb_key
    return "", ""

def _supabase_rest_get(key: str):
    sb_url, sb_key = _get_supabase_config()
    if not sb_url or not sb_key:
        return False, None
    try:
        q_url = f"{sb_url}/rest/v1/kv_store?key=eq.{urllib.parse.quote(str(key), safe='')}&select=val&limit=1"
        req = urllib.request.Request(
            q_url,
            headers={
                "apikey": sb_key,
                "Authorization": f"Bearer {sb_key}",
                "Accept": "application/json",
                "User-Agent": "YamashishiLab/3.0"
            },
            method="GET"
        )
        with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=4.0) as resp:
            rows = json.loads(resp.read().decode("utf-8"))
            if isinstance(rows, list) and len(rows) > 0:
                raw_val = rows[0].get("val")
                parsed = json.loads(raw_val) if isinstance(raw_val, str) else raw_val
                return True, parsed
    except Exception:
        pass
    return False, None

def _supabase_rest_upsert(key: str, val) -> bool:
    sb_url, sb_key = _get_supabase_config()
    if not sb_url or not sb_key:
        return False
    try:
        u_url = f"{sb_url}/rest/v1/kv_store?on_conflict=key"
        payload = json.dumps({
            "key": str(key),
            "val": json.dumps(val, ensure_ascii=False),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            u_url,
            data=payload,
            headers={
                "apikey": sb_key,
                "Authorization": f"Bearer {sb_key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=minimal",
                "User-Agent": "YamashishiLab/3.0"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=4.0) as resp:
            return 200 <= int(getattr(resp, "status", 200)) < 300
    except Exception:
        return False

GEMINI_MODELS = ["gemini-3-flash-preview", "gemini-3.1-pro-preview", "gemini-3.1-flash-lite-preview", "gemini-2.5-flash", "gemini-2.5-pro"]
GEMINI_MODEL_DISPLAY_NAMES = {"gemini-3-flash-preview": "Gemini 3 Flash Preview (推奨・最新高速マルチモーダル)", "gemini-3.1-pro-preview": "Gemini 3.1 Pro Preview (最新フラッグシップ高推論モデル)", "gemini-3.1-flash-lite-preview": "Gemini 3.1 Flash-Lite Preview (超軽量・高速モデル)", "gemini-2.5-flash": "Gemini 2.5 Flash (従来標準モデル)", "gemini-2.5-pro": "Gemini 2.5 Pro (従来高推論モデル)"}
DYNAMIC_GENRES = ["半導体・前工程・検査", "AI・防衛・国策", "AI電力・超電導・電線", "宇宙・量子・次世代テック", "小型急騰・仕手・モメンタム"]

STYLE_SPEC = {
    "スキャルピング": {"pfx": "スキャルピング", "tf": "5m", "max_hold_days": 1, "allow_short": True, "atr_sl_mult": 0.45, "sl_min_pct": 0.004, "sl_max_pct": 0.015, "rr_mult": 1.8, "tp_min_pct": 0.007, "tp_max_pct": 0.027, "lot_mul": 1.5, "w": (1.3, 1.2, 2.5, 0.6, 0.25), "dur": "9:05〜11:00 前場集中・次バー始値約定 → 当日大引け完結", "beg_title": "スキャルピング実戦講座"},
    "デイトレード": {"pfx": "デイトレード", "tf": "5m", "max_hold_days": 1, "allow_short": True, "atr_sl_mult": 0.65, "sl_min_pct": 0.006, "sl_max_pct": 0.022, "rr_mult": 2.0, "tp_min_pct": 0.012, "tp_max_pct": 0.044, "lot_mul": 1.65, "w": (1.45, 1.55, 1.25, 1.1, 0.6), "dur": "9:05〜13:30 確定後次バー始値約定 → 14:30手仕舞い", "beg_title": "デイトレード実戦講座"},
    "スイングトレード": {"pfx": "スイングトレード", "tf": "1d", "max_hold_days": 10, "allow_short": False, "atr_sl_mult": 1.5, "sl_min_pct": 0.030, "sl_max_pct": 0.060, "atr_tp_mult": 3.2, "tp_min_pct": 0.060, "tp_max_pct": 0.140, "lot_mul": 1.2, "w": (1.8, 2.0, 0.9, 2.2, 1.2), "dur": "日足押し目確定翌営業日始値約定 → 最大10営業日保有", "beg_title": "スイングトレード実戦講座"},
    "バイ＆ホールド": {"pfx": "バイ＆ホールド", "tf": "1d", "max_hold_days": 20, "allow_short": False, "atr_sl_mult": 2.5, "sl_min_pct": 0.060, "sl_max_pct": 0.120, "atr_tp_mult": 5.0, "tp_min_pct": 0.120, "tp_max_pct": 0.250, "lot_mul": 0.9, "w": (0.8, 1.2, 0.4, 1.6, 2.8), "dur": "日足・週足支持帯反発翌営業日始値約定 → 最大20営業日保有", "beg_title": "バイ＆ホールド実戦講座"}
}

def get_style_spec(style: str) -> dict:
    pfx = style.split(" ")[1] if " " in str(style) else str(style)
    return STYLE_SPEC.get(pfx, STYLE_SPEC["デイトレード"])

GLOBAL_MARKET_TICKERS = [
    ("8035.T", "東京エレクトロン", "半導体・前工程・検査", "前工程コータ/エッチャ世界首位"), ("6857.T", "アドバンテスト", "半導体・前工程・検査", "GPU/HBMテスタ独占"), ("6920.T", "レーザーテック", "半導体・前工程・検査", "EUVマスクブランクス検査100%独占"),
    ("6146.T", "ディスコ", "半導体・前工程・検査", "切断・研削ダイサ世界シェア圧倒的"), ("6723.T", "ルネサスエレクトロニクス", "半導体・前工程・検査", "車載マイコン・エッジAI半導体"), ("7735.T", "SCREEN-HD", "半導体・前工程・検査", "ウエハ洗浄装置グローバルリーダー"),
    ("NVDA", "NVIDIA", "半導体・前工程・検査", "AIアクセラレータ・CUDA独占覇権"), ("TSM", "TSMC", "半導体・前工程・検査", "最先端2nmファウンドリ受託世界首位"), ("ARM", "Arm-Holdings", "半導体・前工程・検査", "超省電力AIプロセッサIP"),
    ("7011.T", "三菱重工業", "AI・防衛・国策", "防衛予算国策倍増・スタンドオフミサイル"), ("7012.T", "川崎重工業", "AI・防衛・国策", "潜水艦・防衛航空機・液体水素"), ("7013.T", "IHI", "AI・防衛・国策", "航空防衛エンジン・宇宙ロケット"),
    ("9984.T", "ソフトバンクG", "AI・防衛・国策", "Arm親会社・超知能AIエコシステム投資"), ("3778.T", "さくらインターネット", "AI・防衛・国策", "政府認定・国策GPUクラウド基盤"), ("PLTR", "パランティア", "AI・防衛・国策", "防衛省・米軍AIオントロジー統制"),
    ("5803.T", "フジクラ", "AI電力・超電導・電線", "AIデータセンター向け超高密度光配線"), ("5801.T", "古河電気工業", "AI電力・超電導・電線", "超高圧送電ケーブル・AI光通信"), ("5802.T", "住友電気工業", "AI電力・超電導・電線", "超高圧電力インフラ・車載ワイヤハーネス"),
    ("6501.T", "日立製作所", "AI電力・超電導・電線", "送配電グリッド・グローバルインフラDX"), ("9501.T", "東京電力HD", "AI電力・超電導・電線", "柏崎刈羽原発再稼働・AI電力供給"), ("VST", "ビストラ", "AI電力・超電導・電線", "米AIデータセンター原子力直結電力"),
    ("5595.T", "QPS研究所", "宇宙・量子・次世代テック", "小型SAR防衛衛星コンステレーション"), ("186A.T", "アストロスケール", "宇宙・量子・次世代テック", "宇宙デブリ除去・軌道上サービス世界初"), ("TSLA", "テスラ", "宇宙・量子・次世代テック", "FSD自律走行・Optimus人型ロボット"),
    ("IONQ", "アイオンQ", "宇宙・量子・次世代テック", "イオントラップ型商用量子コンピュータ"), ("RGTI", "リゲッティ・コンピューティング", "宇宙・量子・次世代テック", "超伝導量子プロセッサ"), ("5253.T", "カバー", "小型急騰・仕手・モメンタム", "VTuber世界展開・グロース売買代金首位"),
    ("216A.T", "タイミー", "小型急騰・仕手・モメンタム", "スキマバイト市場独占・HRビッグデータ"), ("3350.T", "メタプラネット", "小型急騰・仕手・モメンタム", "ビットコイン大量蓄積トレジャリー戦略"), ("4478.T", "フリー", "小型急騰・仕手・モメンタム", "クラウドSaaS・統合ERP"),
    ("4165.T", "プレイド", "小型急騰・仕手・モメンタム", "CXプラットフォーム・リアルタイム解析")
]

DELISTED_OR_INVALID_CODES = {"4483.T", "260A.T", "6594.T", "3436.T"}

EXTENDED_SEED_LIST = GLOBAL_MARKET_TICKERS + [
    ("4063.T", "信越化学工業", "半導体・前工程・検査", "半導体シリコンウエハ世界首位"), ("6526.T", "ソシオネクスト", "半導体・前工程・検査", "先端カスタムSoCファブレス・AI半導体"), ("6525.T", "KOKUSAI ELECTRIC", "半導体・前工程・検査", "縦型成膜装置世界首位・最先端メモリ製造"),
    ("4369.T", "トリケミカル研究所", "半導体・前工程・検査", "最先端半導体向けHigh-k絶縁膜材料"), ("6254.T", "野村マイクロ・サイエンス", "半導体・前工程・検査", "半導体向け超純水装置"), ("6315.T", "TOWA", "半導体・前工程・検査", "HBM向けモールディング装置世界首位"),
    ("6871.T", "日本マイクロニクス", "半導体・前工程・検査", "HBM・DRAM向けプローブカード"), ("6323.T", "ローツェ", "半導体・前工程・検査", "半導体ウエハ搬送ロボット"), ("7741.T", "HOYA", "半導体・前工程・検査", "EUVマスクブランクス世界双璧"),
    ("6981.T", "村田製作所", "半導体・前工程・検査", "積層セラミックコンデンサ(MLCC)世界首位"), ("6367.T", "ダイキン工業", "AI電力・超電導・電線", "AIデータセンター向け高効率空調・冷却システム"), ("6758.T", "ソニーグループ", "AI・防衛・国策", "イメージセンサ・エンタメIP"),
    ("6701.T", "NEC", "AI・防衛・国策", "防衛通信・顔認証・国策AI"), ("6702.T", "富士通", "AI・防衛・国策", "スーパーコンピュータ・防衛DX"), ("9432.T", "NTT", "AI電力・超電導・電線", "IOWN光電融合・次世代通信インフラ"),
    ("9433.T", "KDDI", "AI・防衛・国策", "AIデータセンター・Starlink連携"), ("4385.T", "メルカリ", "小型急騰・仕手・モメンタム", "フリマプラットフォーム・フィンテック"), ("6532.T", "ベイカレント", "AI・防衛・国策", "総合DX戦略コンサルティング・高収益成長"),
    ("3993.T", "PKSHA Technology", "AI・防衛・国策", "アルゴリズム実装・企業向けAI"), ("5574.T", "ABEJA", "AI・防衛・国策", "生成AI基盤プラットフォーム"), ("9166.T", "GENDA", "小型急騰・仕手・モメンタム", "エンタメM&Aロールアップ成長株"),
    ("5032.T", "ANYCOLOR", "小型急騰・仕手・モメンタム", "VTuberグループ運営・高収益IPモデル"), ("4592.T", "サンバイオ", "小型急騰・仕手・モメンタム", "再生細胞薬バイオモメンタム"), ("4565.T", "ネクセラファーマ", "小型急騰・仕手・モメンタム", "GPCR創薬・大型ライセンス提携"),
    ("5838.T", "楽天銀行", "AI・防衛・国策", "金利上昇恩恵・ネット銀行フィンテック首位"), ("190A.T", "Chordia Therapeutics", "小型急騰・仕手・モメンタム", "創薬バイオベンチャー"), ("247A.T", "Aiロボティクス", "AI・防衛・国策", "AIマーケティング・D2C急成長"),
    ("4194.T", "ビジョナル", "AI・防衛・国策", "ハイクラスHRテック・クラウド人材基盤"), ("278A.T", "Terra Drone", "宇宙・量子・次世代テック", "産業用ドローン・空飛ぶクルマ運航管理"), ("285A.T", "キオクシアHD", "半導体・前工程・検査", "次世代3D NANDフラッシュメモリ"),
    ("290A.T", "Synspective", "宇宙・量子・次世代テック", "小型SAR衛星コンステレーション"), ("9348.T", "ispace", "宇宙・量子・次世代テック", "民間月面探査・シスルナ経済圏"), ("7014.T", "名村造船所", "AI・防衛・国策", "造船国策・防衛艦艇建造"),
    ("7003.T", "三井E&S", "AI・防衛・国策", "船舶エンジン・港湾クレーン国策"), ("6503.T", "三菱電機", "AI・防衛・国策", "防衛レーダー・パワー半導体"), ("6946.T", "日本アビオニクス", "AI・防衛・国策", "防衛情報表示システム・赤外線"),
    ("7721.T", "東京計器", "AI・防衛・国策", "防衛航空計器・マイクロ波"), ("6208.T", "石川製作所", "AI・防衛・国策", "防衛機器・地政学テーマ"), ("4274.T", "細谷火工", "AI・防衛・国策", "自衛隊向け火工品・防衛関連"),
    ("9502.T", "中部電力", "AI電力・超電導・電線", "浜岡原発・データセンター電力供給"), ("9503.T", "関西電力", "AI電力・超電導・電線", "原発稼働率首位・AI電力インフラ"), ("1942.T", "関電工", "AI電力・超電導・電線", "データセンター電気設備工事"),
    ("1951.T", "エクシオグループ", "AI電力・超電導・電線", "光通信・データセンターインフラ施工"), ("6619.T", "ダブル・スコープ", "小型急騰・仕手・モメンタム", "EV電池セパレータ・高ボラ銘柄"), ("3697.T", "SHIFT", "AI・防衛・国策", "ソフトウェアテスト・DX推進"),
    ("6098.T", "リクルートHD", "AI・防衛・国策", "HRテック・AIマッチング"), ("7974.T", "任天堂", "小型急騰・仕手・モメンタム", "次世代機サイクル・世界的IP"), ("8306.T", "三菱UFJフィナンシャルG", "AI・防衛・国策", "金利上昇メリット・メガバンク首位"),
    ("8316.T", "三井住友フィナンシャルG", "AI・防衛・国策", "高配当・金利上昇恩恵"), ("8058.T", "三菱商事", "AI電力・超電導・電線", "総合商社・資源・AIインフラ投資"), ("8001.T", "伊藤忠商事", "AI・防衛・国策", "非資源ビジネス・高ROE商社"),
    ("AVGO", "Broadcom", "半導体・前工程・検査", "カスタムAI ASIC・ネットワーク半導体"), ("AMD", "AMD", "半導体・前工程・検査", "AI GPU MIシリーズ・データセンターCPU"), ("SMCI", "Super Micro Computer", "AI電力・超電導・電線", "AIサーバー・液冷ラック"),
    ("CRWD", "CrowdStrike", "AI・防衛・国策", "AIサイバーセキュリティ"), ("MSFT", "Microsoft", "AI・防衛・国策", "Azure AI・OpenAI最大出資パートナー"), ("GOOGL", "Alphabet", "AI・防衛・国策", "Gemini AI・TPU・量子チップWillow"),
    ("META", "Meta Platforms", "AI・防衛・国策", "LlamaオープンAI・巨額GPU投資"), ("RKLB", "Rocket Lab", "宇宙・量子・次世代テック", "小型ロケット打ち上げ・宇宙システム"), ("ASTS", "AST SpaceMobile", "宇宙・量子・次世代テック", "衛星直接スマホブロードバンド通信"),
    ("QBTS", "D-Wave Quantum", "宇宙・量子・次世代テック", "量子アニーリング商用先駆"), ("QUBT", "Quantum Computing", "宇宙・量子・次世代テック", "フォトニクス量子コンピュータ"), ("OKLO", "Oklo", "AI電力・超電導・電線", "次世代SMR小型モジュール原子炉"),
    ("CEG", "Constellation Energy", "AI電力・超電導・電線", "米最大原子力発電・データセンター電力")
]

EXTENDED_SEED_DICT = {c: {"code": c, "name": n, "genre": g, "theme": t} for c, n, g, t in EXTENDED_SEED_LIST if c not in DELISTED_OR_INVALID_CODES}
STOCK_METADATA_CACHE = {c: {"name": n, "genre": g, "theme": t} for c, n, g, t in EXTENDED_SEED_LIST if c not in DELISTED_OR_INVALID_CODES}

UPCOMING_IPO_WATCHLIST = [
    {
        "code": "未定",
        "stage_label": "🟠 上場準備・承認観測（大型フィンテック）",
        "name": "PayPay（ペイペイ）",
        "market": "東証プライム / 米国NASDAQ（デュアル上場観測）",
        "listing_date_disp": "2026年〜2027年 上場準備・観測中",
        "offer_info": "想定時価総額 1兆〜1.5兆円規模（仮条件未公表）",
        "bb_info": "承認後スケジュール公表予定",
        "lead_underwriter": "野村證券 / 三菱UFJモルガン・スタンレー / ゴールドマン・サックス（観測）",
        "absorption_scale": "超大型（1,000億円超・機関投資家主導型）",
        "theme": "国内QRコード決済シェア圧倒的首位・金融スーパーアプリ基盤",
        "business_desc": "登録ユーザー6,500万人超を抱える国内最大のキャッシュレス決済プラットフォーム。PayPay銀行・PayPay証券・PayPayカードとの金融エコシステム統合により黒字化と高収益化を実現。ソフトバンクグループ・LYグループの中核フィンテック資産として国内外の機関投資家から最注目されています。",
        "supply_outlook": "超大型案件のため初値急騰（2倍超）よりも、公開価格近辺での落ち着いた初値形成後に海外パッシブ資金・指数組み入れ需要でじわじわ上昇する『セカンダリー順張り型』の需給構造が想定されます。",
        "query": '"PayPay" ("上場" OR "IPO")'
    },
    {
        "code": "未定",
        "stage_label": "🟣 米国メガIPO観測（宇宙・衛星通信）",
        "name": "SpaceX / Starlink（スペースX・スターリンク）",
        "market": "米国NASDAQ / NYSE（スピンオフIPO観測）",
        "listing_date_disp": "2026年後半〜2027年 上場観測中",
        "offer_info": "未公表（非公開評価額 3,500億ドル超規模）",
        "bb_info": "SEC S-1登録届出書提出待ち",
        "lead_underwriter": "モルガン・スタンレー / ゴールドマン・サックス（観測）",
        "absorption_scale": "世界最大級メガIPO（グローバル機関投資家集中）",
        "theme": "低軌道衛星ブロードバンド網Starlink・再使用型ロケットStarship世界独占",
        "business_desc": "世界の軌道上打ち上げ重量の8割以上を独占する宇宙輸送インフラ企業であり、衛星通信事業『Starlink』は世界100ヶ国以上で契約数を急拡大中。日本の宇宙関連株（QPS研究所・アストロスケール・ispace）や通信株への連想買いを直接引き起こす最重要グローバルIPO候補です。",
        "supply_outlook": "上場承認報道が出た瞬間から国内の宇宙・衛星関連セクターへ強力なテーマ資金が波及します。本体上場時は米国市場での流動性爆発と初動ボラティリティ拡大に要注目です。",
        "query": '("SpaceX" OR "Starlink") ("IPO" OR "上場")'
    },
    {
        "code": "未定",
        "stage_label": "🟠 上場準備・承認観測（AI・クラウド）",
        "name": "Sakana AI（サカナAI）",
        "market": "東証プライム / グロース（ユニコーン大型上場候補）",
        "listing_date_disp": "上場準備・観測段階（承認待ち）",
        "offer_info": "想定時価総額 2,000億円超クラス（未公表）",
        "bb_info": "承認後スケジュール公表予定",
        "lead_underwriter": "野村證券 / SMBC日興証券 / モルガン・スタンレー（観測）",
        "absorption_scale": "大型グロース〜プライム（機関・海外勢参入型）",
        "theme": "進化的モデルマージ技術・日本発の次世代生成AIユニコーン",
        "business_desc": "元Google Brainのトップ研究者らが東京で創業した日本発のAIユニコーン企業。少量の計算資源で複数のAIモデルを自動融合させる独自技術を持ち、NVIDIAや国内メガバンク・大手通信各社が出資参画。日本の国策AI・ソブリンAI開発の中核を担う存在です。",
        "supply_outlook": "AI・半導体テーマとの親和性が極めて高く、上場承認が発表されれば国内AI関連株（さくらインターネット・PKSHA等）の連れ高トリガーになりやすい注目案件です。",
        "query": '"Sakana AI" ("上場" OR "IPO" OR "資金調達")'
    },
    {
        "code": "未定",
        "stage_label": "🟠 上場準備・承認観測（半導体・メモリ）",
        "name": "JSR（次世代半導体フォトレジスト再上場観測）",
        "market": "東証プライム（再上場・大型案件観測）",
        "listing_date_disp": "産業革新投資機構(JIC)傘下での再編後・再上場観測",
        "offer_info": "未公表（大型プライム案件）",
        "bb_info": "再上場承認スケジュール待ち",
        "lead_underwriter": "野村證券 / 大和証券 / みずほ証券（観測）",
        "absorption_scale": "超大型プライム（半導体セクター中核）",
        "theme": "EUVフォトレジスト世界首位級・最先端半導体材料インフラ",
        "business_desc": "最先端半導体製造に不可欠なEUV（極端紫外線）露光用フォトレジストで世界トップシェアを誇る化学材料メーカー。JICによる非公開化を経て業界再編と研究開発投資を加速させており、半導体前工程セクターのバリュエーション基準となる大型再上場候補です。",
        "supply_outlook": "東京エレクトロン・SCREEN・トリケミカル研究所など半導体材料・装置株と強い相関を持ち、再上場観測報道が出るたびに材料セクター全体の再評価買いを誘発します。",
        "query": '"JSR" ("再上場" OR "IPO" OR "半導体")'
    },
    {
        "code": "285A",
        "stage_label": "🟢 既上場大型IPO（セカンダリー監視中）",
        "name": "キオクシアホールディングス",
        "market": "東証プライム（2024年12月18日上場）",
        "listing_date_disp": "2024-12-18 上場済（プライム大型）",
        "offer_info": "公開価格 1,455円 ／ 初値 1,440円（公募比 -1.0%）",
        "bb_info": "BB完了・東証プライム売買代金上位常連",
        "lead_underwriter": "三菱UFJモルガン・スタンレー / 野村 / SMBC日興",
        "absorption_scale": "約1,200億円（超大型プライム・高流動性）",
        "theme": "AIデータセンター向け大容量エンタープライズSSD・3D NANDフラッシュ世界大手",
        "business_desc": "旧東芝メモリを源流とする世界屈指のフラッシュメモリ専業メーカー。AIサーバーの学習・推論データ爆発に伴うエンタープライズ向け大容量SSD需要の急拡大を背景に、業績回復と設備投資サイクルの恩恵を直接受ける東証プライムの大型IPO銘柄です。",
        "supply_outlook": "超大型上場のため初値は公募価格近辺で落ち着いたものの、上場後の業績モメンタムとAIメモリ需要を背景に機関投資家の組み入れが進み、セカンダリー相場で強いトレンドを形成しやすい典型例です。",
        "query": '"キオクシア" 株価'
    },
    {
        "code": "290A",
        "stage_label": "🟢 既上場グロースIPO（宇宙・衛星監視中）",
        "name": "Synspective（シンスペクティブ）",
        "market": "東証グロース（2024年12月19日上場）",
        "listing_date_disp": "2024-12-19 上場済（宇宙グロース）",
        "offer_info": "公開価格 480円 ／ 初値 603円（公募比 +25.6%）",
        "bb_info": "BB完了・防衛省/官公庁向けSAR衛星案件",
        "lead_underwriter": "野村證券",
        "absorption_scale": "約138億円（中型グロース・テーマ性特化）",
        "theme": "小型SAR（合成開口レーダー）衛星コンステレーション開発・安全保障ソリューション",
        "business_desc": "天候や昼夜を問わず地表を高精細観測できる小型SAR衛星を自社開発・打ち上げ・解析まで一気通貫で提供する宇宙ベンチャー。防衛省や防災インフラ向けの長期契約が拡大しており、QPS研究所と並ぶ日本の宇宙国策グロースの双璧です。",
        "supply_outlook": "公開価格480円から初値603円（+25.6%）と健全な初値形成後、宇宙・防衛予算関連の材料が出るたびに短期資金が集中しやすい高ボラティリティ銘柄です。ロックアップ解除期日とVWAP支持帯を意識した押し目狙いが有効です。",
        "query": '"Synspective" 株価'
    }
]

REAL_IPO_GROWTH_UNIVERSE = [
    ("186A.T", "アストロスケールHD", "東証グロース", "宇宙デブリ除去・軌道上サービス世界初"), ("216A.T", "タイミー", "東証グロース", "スキマバイト市場独占・HRビッグデータ"), ("5595.T", "QPS研究所", "東証グロース", "小型SAR防衛衛星コンステレーション"),
    ("9166.T", "GENDA", "東証グロース", "エンタメ・アミューズメントM&Aロールアップ"), ("6526.T", "ソシオネクスト", "東証プライム", "先端カスタムSoCファブレス・AI半導体設計"), ("285A.T", "キオクシアHD", "東証プライム", "次世代3D NANDフラッシュメモリ大型上場"),
    ("290A.T", "Synspective", "東証グロース", "小型SAR衛星コンステレーション開発・運用"), ("278A.T", "Terra Drone", "東証グロース", "産業用ドローン・空飛ぶクルマ運航管理"), ("247A.T", "Aiロボティクス", "東証グロース", "AIマーケティングシステム・自社ブランド展開"),
    ("4194.T", "ビジョナル", "東証プライム", "ハイクラスHRテック・クラウド人材基盤"), ("190A.T", "Chordia Therapeutics", "東証グロース", "RNA制御ストレス標的の次世代創薬バイオ"), ("9348.T", "ispace", "東証グロース", "民間月面資源開発・ランダー輸送サービス"),
    ("5253.T", "カバー", "東証グロース", "VTuberプロダクション・IPメタバース展開"), ("5032.T", "ANYCOLOR", "東証プライム", "VTuberグループ運営・高収益コマース"), ("5574.T", "ABEJA", "東証グロース", "エンタープライズ生成AI導入基盤"),
    ("3993.T", "PKSHA Technology", "東証スタンダード", "未来型アルゴリズム・自然言語処理AI"), ("4478.T", "フリー", "東証グロース", "統合型クラウドERP・スモールビジネスDX"), ("4165.T", "プレイド", "東証グロース", "CXプラットフォームKARTE・データ解析")
]

IPO_HISTORICAL_META = {
    "186A.T": {"listing_date": "2024-06-05", "offer_price": 850, "initial_price": 1281, "lead_underwriter": "三菱UFJモルガン・スタンレー証券", "absorption_scale": "約246億円（大型グロース）", "note": ""},
    "216A.T": {"listing_date": "2024-07-26", "offer_price": 1450, "initial_price": 1850, "lead_underwriter": "大和証券 / 三菱UFJモルガン・スタンレー", "absorption_scale": "約493億円（大型グロース）", "note": ""},
    "285A.T": {"listing_date": "2024-12-18", "offer_price": 1455, "initial_price": 1440, "lead_underwriter": "三菱UFJモルガン・スタンレー / 野村 / SMBC日興", "absorption_scale": "約1,200億円（超大型プライム）", "note": ""},
    "290A.T": {"listing_date": "2024-12-19", "offer_price": 480, "initial_price": 603, "lead_underwriter": "野村證券", "absorption_scale": "約138億円（中型グロース）", "note": ""},
    "278A.T": {"listing_date": "2024-11-29", "offer_price": 2350, "initial_price": 2162, "lead_underwriter": "SMBC日興証券 / 大和証券", "absorption_scale": "約62億円（中型グロース）", "note": ""},
    "247A.T": {"listing_date": "2024-09-27", "offer_price": 1760, "initial_price": 2453, "lead_underwriter": "SBI証券", "absorption_scale": "約29億円（小型グロース）", "note": ""},
    "190A.T": {"listing_date": "2024-06-14", "offer_price": 153, "initial_price": 252, "lead_underwriter": "SMBC日興証券", "absorption_scale": "約38億円（バイオ小型）", "note": ""},
    "5595.T": {"listing_date": "2023-12-06", "offer_price": 390, "initial_price": 860, "lead_underwriter": "SMBC日興証券", "absorption_scale": "約71億円（宇宙グロース）", "note": ""},
    "9166.T": {"listing_date": "2023-07-28", "offer_price": 1770, "initial_price": 1560, "lead_underwriter": "SBI証券 / SMBC日興証券", "absorption_scale": "約148億円（中型グロース）", "note": ""},
    "9348.T": {"listing_date": "2023-04-12", "offer_price": 254, "initial_price": 1000, "lead_underwriter": "SMBC日興証券", "absorption_scale": "約76億円（宇宙グロース）", "note": ""},
    "5253.T": {"listing_date": "2023-03-27", "offer_price": 750, "initial_price": 1422, "lead_underwriter": "三菱UFJモルガン・スタンレー / みずほ証券", "absorption_scale": "約105億円（中型グロース）", "note": ""},
    "5032.T": {"listing_date": "2022-06-08", "offer_price": 1530, "initial_price": 4810, "lead_underwriter": "三菱UFJモルガン・スタンレー / 大和証券", "absorption_scale": "約34億円（小型グロース）", "note": ""},
    "5574.T": {"listing_date": "2023-06-13", "offer_price": 1550, "initial_price": 4680, "lead_underwriter": "野村證券", "absorption_scale": "約24億円（AI小型グロース）", "note": ""},
    "6526.T": {"listing_date": "2022-10-12", "offer_price": 3650, "initial_price": 3835, "lead_underwriter": "野村證券 / SMBC日興証券", "absorption_scale": "約667億円（大型プライム）", "note": ""},
    "4194.T": {"listing_date": "2021-04-22", "offer_price": 5000, "initial_price": 7250, "lead_underwriter": "野村證券 / モルガン・スタンレーMUFG", "absorption_scale": "約694億円（大型マザーズ）", "note": ""},
    "3993.T": {"listing_date": "2017-09-22", "offer_price": 2400, "initial_price": 5480, "lead_underwriter": "SMBC日興証券", "absorption_scale": "約132億円（AIマザーズ）", "note": ""},
    "4478.T": {"listing_date": "2019-12-17", "offer_price": 2000, "initial_price": 2500, "lead_underwriter": "三菱UFJモルガン・スタンレー / 大和証券", "absorption_scale": "約384億円（大型SaaS）", "note": ""},
    "4165.T": {"listing_date": "2020-12-17", "offer_price": 1600, "initial_price": 3190, "lead_underwriter": "みずほ証券 / 野村證券", "absorption_scale": "約258億円（中型SaaS）", "note": ""}
}

_UNIQUE_IPO_GROWTH_UNIVERSE, _SEEN_IPO_UNIVERSE = [], set()
for _ic, _inm, _imkt, _ith in REAL_IPO_GROWTH_UNIVERSE:
    if _ic not in _SEEN_IPO_UNIVERSE and _ic not in DELISTED_OR_INVALID_CODES:
        _SEEN_IPO_UNIVERSE.add(_ic); _UNIQUE_IPO_GROWTH_UNIVERSE.append((_ic, _inm, _imkt, _ith))
        if _ic not in STOCK_METADATA_CACHE: STOCK_METADATA_CACHE[_ic] = {"name": _inm, "genre": "小型急騰・仕手・モメンタム", "theme": _ith}
REAL_IPO_GROWTH_UNIVERSE = _UNIQUE_IPO_GROWTH_UNIVERSE

TOPIX100_CORE_CODES = {"8035.T", "6857.T", "6920.T", "6146.T", "6723.T", "7011.T", "9984.T", "6501.T", "4063.T", "6758.T", "6701.T", "6702.T", "9432.T", "9433.T", "6098.T", "7974.T", "8306.T", "8316.T", "8058.T", "8001.T", "6367.T", "6981.T", "7741.T"}
HIGH_BETA_VOLATILE_CODES = {"6920.T", "6146.T", "6857.T", "5803.T", "6315.T", "6871.T", "6254.T", "6526.T", "6525.T", "285A.T", "NVDA", "SMCI", "ARM", "TSLA"}
SMALL_MOMENTUM_SPEC_CODES = {"5595.T", "186A.T", "3350.T", "5253.T", "216A.T", "4478.T", "4165.T", "4592.T", "4565.T", "190A.T", "247A.T", "278A.T", "290A.T", "9348.T", "6208.T", "4274.T", "6619.T", "5574.T", "3993.T", "7014.T", "7003.T", "9166.T", "5032.T", "IONQ", "RGTI", "QBTS", "QUBT", "ASTS", "RKLB", "OKLO"}
DEFENSIVE_LARGE_CODES = {"9432.T", "9433.T", "9501.T", "9502.T", "9503.T", "8306.T", "8316.T", "8058.T", "8001.T", "1942.T", "1951.T", "MSFT", "GOOGL"}
BEARISH_NEWS_KEYWORDS = ["下方修正", "減益", "赤字", "希薄化", "売り出し", "公募増資", "ストップ安", "業績悪化", "不祥事", "訴訟", "立会外分売", "新株予約権", "第三者割当", "ロックアップ", "投資判断引き下げ", "延期"]

TSE_PRICE_LIMIT_TABLE = [
    (100.0, 30.0), (200.0, 50.0), (500.0, 80.0), (700.0, 100.0), (1000.0, 150.0),
    (1500.0, 300.0), (2000.0, 400.0), (3000.0, 500.0), (5000.0, 700.0), (7000.0, 1000.0),
    (10000.0, 1500.0), (15000.0, 3000.0), (20000.0, 4000.0), (30000.0, 5000.0),
    (50000.0, 7000.0), (70000.0, 10000.0), (100000.0, 15000.0), (150000.0, 30000.0),
    (200000.0, 40000.0), (300000.0, 50000.0), (500000.0, 70000.0), (700000.0, 100000.0),
    (1000000.0, 150000.0), (1500000.0, 300000.0), (2000000.0, 400000.0), (3000000.0, 500000.0),
    (5000000.0, 700000.0), (7000000.0, 1000000.0), (10000000.0, 1500000.0)
]

def get_tse_price_limit(prev_close: float) -> float:
    pc = float(prev_close or 0.0)
    if pc <= 0: return 0.0
    for thresh, lim in TSE_PRICE_LIMIT_TABLE:
        if pc < thresh: return lim
    return 1500000.0

def get_tse_tick_step(val: float, full_code: str) -> float:
    if ".T" not in str(full_code): return 0.01
    if str(full_code) in TOPIX100_CORE_CODES: return 0.5 if val <= 3000 else (1.0 if val <= 10000 else (5.0 if val <= 30000 else 10.0))
    return 1.0 if val <= 3000 else (5.0 if val <= 5000 else (10.0 if val <= 30000 else (50.0 if val <= 50000 else 100.0)))

def round_to_tse_tick(val: float, full_code: str, mode: str = "nearest") -> float:
    if val <= 0: return 0.0
    if ".T" not in str(full_code): return round(float(val), 2)
    tick = get_tse_tick_step(val, full_code)
    q = float(val) / tick
    res = math.ceil(q - 1e-9) * tick if mode == "ceil" else (math.floor(q + 1e-9) * tick if mode == "floor" else round(q) * tick)
    return round(res, 1) if tick < 1.0 else float(int(round(res)))

def apply_unfavorable_tick_slip(val: float, full_code: str, is_long_entry_or_short_exit: bool) -> float:
    if val <= 0: return 0.0
    tick = get_tse_tick_step(val, full_code)
    if is_long_entry_or_short_exit:
        base = round_to_tse_tick(val, full_code, "ceil")
        return round(base + tick, 2) if tick < 1.0 else float(int(round(base + tick)))
    base = round_to_tse_tick(val, full_code, "floor")
    res = max(base - tick, tick)
    return round(res, 2) if tick < 1.0 else float(int(round(res)))

def fmt_px(val: float, is_jp: bool, full_code: str = "") -> str:
    if not is_jp: return f"${val:,.2f}"
    r_val = round_to_tse_tick(val, full_code or ".T", "nearest")
    return f"{r_val:,.1f}円" if r_val % 1 != 0 else f"{int(r_val):,}円"

def get_tse_session_regime() -> dict:
    now_dt = datetime.now()
    if now_dt.weekday() >= 5: return {"label": "休場（週末）：翌営業日シナリオ準備期", "advice": "休場中のため、先物・SOX動向と前日VWAP・日足MA25・週足10年POCを確認し、翌朝9:05以降の確定足待ち指値シナリオを準備してください。"}
    mins = now_dt.hour * 60 + now_dt.minute
    if 9 * 60 <= mins < 9 * 60 + 30: return {"label": "初動ORB期 (9:00-9:30)", "advice": "寄付き直後の乱高下に飛びつかず、9:05以降の初動レンジ(OR15)と平均約定価格(VWAP)への押し目引きつけを確認してから執行してください。"}
    elif 9 * 60 + 30 <= mins < 11 * 60 + 30: return {"label": "前場トレンド期 (9:30-11:30)", "advice": "大口資金の流動性が最も高い時間帯です。OR15安値維持・押し目反発・高値ブレイク確定後の次バー執行を優先してください。"}
    elif 11 * 60 + 30 <= mins < 12 * 60 + 30: return {"label": "前引け昼休み：後場需給再点検期", "advice": "前場引け値と平均約定価格の位置関係を再点検し、後場寄付き（12:30）に備えて逆指値ラインを厳格設定してください。"}
    elif 12 * 60 + 30 <= mins < 13 * 60 + 30: return {"label": "後場需給転換期 (12:30-13:30)", "advice": "後場寄付き後の反転が発生しやすい時間帯です。新規エントリーの最終受付リミット（13:30）を意識してください。"}
    elif 13 * 60 + 30 <= mins <= 15 * 60 + 30: return {"label": "利益保護・手仕舞い期 (13:30-15:30)", "advice": "新規飛びつきは原則控え、既存建玉の+1.0R到達時50%分割利確・建値以上への逆指値ロックと大引け手仕舞いを優先してください。"}
    return {"label": "場外：翌営業日シナリオ準備期", "advice": "東証立会時間外のため、米市場・ドル円と当日終値・移動平均線から翌営業日の執行計画を事前セットしてください。"}

def get_ticker_combat_profile(full_code: str, genre: str = "", rvol: float = 1.0, yz_vol: float = 0.3) -> dict:
    fc = str(full_code).upper()
    if fc in SMALL_MOMENTUM_SPEC_CODES or "小型" in genre or "宇宙" in genre or "グロース" in genre: return {"tier_class": "Tier3: 小型高ボラ・モメンタム特化", "cost_rate": 0.0020, "tp_mult": 1.15, "sl_mult": 1.12, "lot_cap_mult": 0.60, "min_rvol_req": 1.15, "max_gu_limit": 2.5}
    elif fc in HIGH_BETA_VOLATILE_CODES or "半導体" in genre: return {"tier_class": "Tier2: 値嵩ハイベータ主力", "cost_rate": 0.0010, "tp_mult": 1.08, "sl_mult": 1.05, "lot_cap_mult": 0.85, "min_rvol_req": 0.90, "max_gu_limit": 2.8}
    elif fc in DEFENSIVE_LARGE_CODES or "電力" in genre: return {"tier_class": "Tier4: 大型インフラ・バリュー主力", "cost_rate": 0.0007, "tp_mult": 0.85, "sl_mult": 0.90, "lot_cap_mult": 1.00, "min_rvol_req": 0.80, "max_gu_limit": 2.2}
    return {"tier_class": "Tier1: 超大型・機関コア主力", "cost_rate": 0.0008, "tp_mult": 1.00, "sl_mult": 1.00, "lot_cap_mult": 1.00, "min_rvol_req": 0.85, "max_gu_limit": 3.0}

def is_jp_tier3_short_restricted(full_code: str, genre: str = "", combat_prof: dict = None) -> bool:
    fc = str(full_code).upper()
    if ".T" not in fc: return False
    prof = combat_prof or get_ticker_combat_profile(fc, genre)
    return ("Tier3" in str(prof.get("tier_class", ""))) or (fc in SMALL_MOMENTUM_SPEC_CODES)

def compute_ticker_macro_bias(full_code: str, genre: str, macro: dict) -> float:
    fc = str(full_code).upper()
    sox_d, nk_d, fx_d, sp_d, vix_d = [float(macro.get(k, {}).get("diff", 0.0)) for k in ("sox", "nk_fut", "usdjpy", "sp500", "vix")]
    bias = 0.0
    if "半導体" in genre or fc in {"8035.T", "6857.T", "6920.T", "6146.T", "NVDA", "TSM", "ARM", "AVGO", "AMD", "SMCI"}: bias += sox_d * 1.30 + fx_d * 0.45
    elif fc in {"8306.T", "8316.T", "5838.T"}: bias += nk_d * 0.75 + fx_d * 0.60
    elif "防衛" in genre or fc in {"7011.T", "7012.T", "7013.T", "7014.T"}: bias += nk_d * 0.65 + fx_d * 0.55
    elif ".T" in fc: bias += nk_d * 0.85 + fx_d * 0.30
    else: bias += sp_d * 1.10 + sox_d * 0.50
    if vix_d >= 5.0 and (fc in SMALL_MOMENTUM_SPEC_CODES or "小型" in genre or "宇宙" in genre): bias -= (vix_d - 4.0) * 0.35
    return float(np.clip(bias, -4.0, 4.0))

def normalize_ohlcv_df(df_raw: pd.DataFrame, min_rows: int = 5):
    if df_raw is None or df_raw.empty: return None
    df = df_raw.dropna(subset=["Close", "Open", "High", "Low", "Volume"]).copy()
    if len(df) < min_rows: return None
    idx = df.index if isinstance(df.index, pd.DatetimeIndex) else pd.to_datetime(df.index)
    df["_trade_date"] = idx.strftime("%Y-%m-%d"); df["_bar_hm"] = idx.strftime("%H:%M")
    return df

_DB_LOCK, _MEM_CACHE = threading.RLock(), {}
if "client_uuid" not in st.session_state: st.session_state["client_uuid"] = str(uuid.uuid4())

@contextmanager
def get_db_cursor():
    conn = sqlite3.connect(DB_SQLITE_PATH, check_same_thread=False, timeout=10.0)
    for q in ("PRAGMA journal_mode=WAL;", "PRAGMA synchronous=NORMAL;", "PRAGMA busy_timeout=10000;"): conn.execute(q)
    cur = conn.cursor()
    try: yield cur; conn.commit()
    except Exception as e: conn.rollback(); record_system_error("db_transaction_error", e); raise
    finally: conn.close()

def init_sqlite_db():
    with _DB_LOCK:
        try:
            with get_db_cursor() as c: c.execute("CREATE TABLE IF NOT EXISTS kv_store (key TEXT PRIMARY KEY, val TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
        except Exception as e: record_system_error("init_sqlite_db", e)

init_sqlite_db()

def db_get(key: str, default_val):
    with _DB_LOCK:
        if key in _MEM_CACHE: return _MEM_CACHE[key]
        sb_ok, sb_val = _supabase_rest_get(key)
        if sb_ok:
            _MEM_CACHE[key] = sb_val
            try:
                with get_db_cursor() as cur:
                    cur.execute("INSERT INTO kv_store (key, val, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) ON CONFLICT(key) DO UPDATE SET val=excluded.val, updated_at=CURRENT_TIMESTAMP;", (key, json.dumps(sb_val, ensure_ascii=False)))
            except Exception: pass
            return sb_val
        try:
            with get_db_cursor() as cur:
                cur.execute("SELECT val FROM kv_store WHERE key = ?", (key,))
                row = cur.fetchone()
                if row:
                    val = json.loads(row[0]); _MEM_CACHE[key] = val
                    if _get_supabase_config()[0]:
                        threading.Thread(target=_supabase_rest_upsert, args=(key, val), daemon=True).start()
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
        try:
            if _get_supabase_config()[0]:
                threading.Thread(target=_supabase_rest_upsert, args=(key, val), daemon=True).start()
        except Exception: pass

def _derive_crypto_key(salt: bytes) -> bytes: return hashlib.pbkdf2_hmac("sha256", SECRET_KEY.encode(), salt, 60000, 32)

def encrypt_secret_str(p: str) -> str:
    if not p: return ""
    salt = secrets.token_bytes(16); k = _derive_crypto_key(salt)
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        nonce = secrets.token_bytes(12)
        return "enc:" + (salt + nonce + AESGCM(k).encrypt(nonce, p.encode("utf-8"), None)).hex()
    except Exception:
        d = p.encode("utf-8"); s = hashlib.sha256(k + salt).digest()
        while len(s) < len(d): s += hashlib.sha256(s + k).digest()
        xb = bytes([b ^ s[i] for i, b in enumerate(d)])
        return "xor:" + (salt + hmac.new(k, xb, hashlib.sha256).digest()[:16] + xb).hex()

def _is_valid_gemini_key(k: str) -> bool: return bool(k) and ((k.startswith("AQ.") and len(k) >= 40) or (k.startswith("AIza") and len(k) >= 35))

def decrypt_secret_str(c: str) -> str:
    if not c or not (c.startswith("enc:") or c.startswith("xor:")):
        raw_plain = str(c or "").strip(); return raw_plain if _is_valid_gemini_key(raw_plain) else ""
    try:
        sch, hd = c.split(":", 1); raw = bytes.fromhex(hd); res_str = ""
        if sch == "enc":
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            res_str = AESGCM(_derive_crypto_key(raw[:16])).decrypt(raw[16:28], raw[28:], None).decode("utf-8")
        elif sch == "xor":
            salt, mac, xb = raw[:16], raw[16:32], raw[32:]; k = _derive_crypto_key(salt)
            if not hmac.compare_digest(mac, hmac.new(k, xb, hashlib.sha256).digest()[:16]): return ""
            s = hashlib.sha256(k + salt).digest()
            while len(s) < len(xb): s += hashlib.sha256(s + k).digest()
            res_str = bytes([b ^ s[i] for i, b in enumerate(xb)]).decode("utf-8")
        clean_res = res_str.strip(); return clean_res if _is_valid_gemini_key(clean_res) else ""
    except Exception as e: record_system_error("decrypt_secret_str", e)
    return ""

def clean_k(k: str) -> str: return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(k or "")).strip().strip("\"'"))

def sanitize_api_key(k: str) -> str:
    if not k: return ""
    norm = unicodedata.normalize("NFKC", str(k)).strip()
    m_aq = re.search(r"(AQ\.[0-9A-Za-z_\-\.]{40,70})", norm)
    if m_aq: return m_aq.group(1)
    m_aiza = re.search(r"(AIza[0-9A-Za-z_\-]{30,45})", norm)
    if m_aiza: return m_aiza.group(1)
    return re.sub(r"[^A-Za-z0-9_\-\.]", "", clean_k(norm))

def gen_code(em: str) -> str: return hmac.new(SECRET_KEY.encode(), em.strip().lower().encode(), hashlib.sha256).hexdigest()[:8].upper()
def gen_tok(em: str, act: str) -> str: return hmac.new(SECRET_KEY.encode(), f"{em.strip().lower()}:{act}:{SECRET_KEY[:16]}:{int(time.time() // 86400)}".encode(), hashlib.sha256).hexdigest()[:16]

PBKDF2_ROUNDS = 50000
def hash_pin(pin: str, user_salt: str = "") -> str: return hashlib.pbkdf2_hmac("sha256", pin.strip().encode(), (f"{SECRET_KEY}:{user_salt.strip().lower()}" if user_salt else SECRET_KEY).encode(), PBKDF2_ROUNDS).hex()[:24]
def _hash_pin_legacy(pin: str, user_salt: str = "") -> str: return hashlib.pbkdf2_hmac("sha256", pin.strip().encode(), (f"{SECRET_KEY}:{user_salt.strip().lower()}" if user_salt else SECRET_KEY).encode(), 10000).hex()[:16]
def verify_pin(stored: str, in_pin: str, em: str = "") -> bool: return bool(stored and in_pin) and any(hmac.compare_digest(stored, fn(in_pin, s)) for fn, s in [(hash_pin, em), (_hash_pin_legacy, em), (_hash_pin_legacy, "")])

def get_raw_header_fp() -> str:
    try:
        h = {str(k).lower(): str(v) for k, v in dict(getattr(st.context, "headers", {}) or {}).items()}
        raw = f"{h.get('user-agent','')}|{h.get('accept-language','')}|{h.get('sec-ch-ua-platform','')}"
    except Exception as e: record_system_error("get_raw_header_fp", e); raw = "default_env"
    return hashlib.sha256(raw.encode()).hexdigest()[:12].upper()

def get_client_fp() -> str:
    raw = get_raw_header_fp(); qf = st.query_params.get("dfp", "")
    if qf: st.session_state["client_dfp"] = qf
    dfp = st.session_state.get("client_dfp", "")
    return hashlib.sha256(f"{raw}|{dfp}".encode()).hexdigest()[:12].upper() if dfp else raw

def load_smtp(): return db_get("smtp", {"smtp_user": ADMIN_EMAIL, "smtp_pass": "", "smtp_server": "smtp.mail.yahoo.co.jp", "smtp_port": 465})
def save_smtp(user: str, pw: str, srv: str, port: int): db_set("smtp", {"smtp_user": user.strip(), "smtp_pass": pw.strip(), "smtp_server": srv.strip(), "smtp_port": int(port)})

def load_gemini_cfg() -> dict:
    raw = db_get("llm", {})
    if not isinstance(raw, dict): raw = {}
    mod = str(raw.get("gemini_model") or raw.get("models", {}).get("gemini", "gemini-3-flash-preview")).strip() or "gemini-3-flash-preview"
    dec_k = sanitize_api_key(decrypt_secret_str(raw.get("enc_gemini_key") or raw.get("enc_keys", {}).get("gemini", "")))
    if not _is_valid_gemini_key(dec_k):
        env_k = sanitize_api_key(_safe_get_env_or_secret("GEMINI_API_KEY"))
        dec_k = env_k if _is_valid_gemini_key(env_k) else ""
    return {"model": mod, "api_key": dec_k}

def save_llm_encrypted(model: str, api_key: str):
    clean_m = re.sub(r"[^A-Za-z0-9_\-\.]", "", str(model or "").strip()) or "gemini-3-flash-preview"
    clean_api_k = sanitize_api_key(api_key)
    db_set("llm", {"provider": "gemini", "gemini_model": clean_m, "enc_gemini_key": encrypt_secret_str(clean_api_k) if clean_api_k else ""})
    st.session_state["last_working_gemini_model"] = ""

def load_sec(): return db_get("sec", {"banned_fps": {}, "banned_emails": {}, "banned_pins": {}, "banned_names": [], "spoof_logs": [], "device_bio_map": {}})
def load_mail_db(): return db_get("mail", {"logs": [], "messages": []})

def load_mem():
    db = db_get("mem", {})
    if not isinstance(db, dict): db = {}
    adm = ADMIN_EMAIL.strip().lower()
    if adm not in db:
        ns = datetime.now().strftime("%Y-%m-%d %H:%M")
        db[adm] = {"name": "管理者", "email": adm, "status": "approved", "passcode": gen_code(adm), "pin_hash": hash_pin("0000", adm), "applied_at": ns, "approved_at": ns, "last_seen_ts": 0, "last_seen_str": "-", "fp": "-", "bio_enabled": False, "deep_dive_status": "approved", "deep_dive_allowed": True}
        db_set("mem", db)
    return db

def _normalize_boost_keys(raw_boosts) -> list:
    valid_cores = {"core_vol", "core_inst", "core_mom"}
    if not isinstance(raw_boosts, (list, set, tuple)): return ["core_vol", "core_inst", "core_mom"]
    legacy_map = {"algo": "core_vol", "agi_q": "core_vol", "core_vol": "core_vol", "ms": "core_inst", "inst": "core_inst", "core_inst": "core_inst", "mom": "core_mom", "hft_front": "core_mom", "core_mom": "core_mom"}
    res = list(dict.fromkeys([legacy_map[k] for k in raw_boosts if k in legacy_map and legacy_map[k] in valid_cores]))
    return res if res else ["core_vol", "core_inst", "core_mom"]

def _user_store_key(prefix: str, em: str) -> str: return f"{prefix}_{hashlib.md5(em.strip().lower().encode()).hexdigest()[:16]}" if em else ""
def load_user_prefs(em: str) -> dict:
    if not em: return {}
    p = db_get(_user_store_key("user_prefs", em), {"investment_style": "⚡ デイトレード (前場・後場の波及を狙う)", "active_boosts": ["core_vol", "core_inst", "core_mom"], "total_capital": 1000000, "risk_tolerance_pct": 2.0, "survival_cut_pct": 75})
    if isinstance(p, dict): p["active_boosts"] = _normalize_boost_keys(p.get("active_boosts", ["core_vol", "core_inst", "core_mom"]))
    return p
def save_user_prefs(em: str, p: dict):
    if em: db_set(_user_store_key("user_prefs", em), p)
def load_watchlist(em: str) -> dict:
    wl = db_get(_user_store_key("watchlist", em), {}) if em else {}
    return wl if isinstance(wl, dict) else {}
def save_watchlist(em: str, wl: dict):
    if em: db_set(_user_store_key("watchlist", em), wl)

def load_trade_journal(em: str) -> list:
    if not em: return []
    j = db_get(_user_store_key("trade_journal", em), [])
    return j if isinstance(j, list) else []

def save_trade_journal(em: str, entries: list):
    if em: db_set(_user_store_key("trade_journal", em), entries[:200])

def load_shared_ticker_intel() -> dict:
    cur = st.session_state.get("shared_ticker_intel")
    if isinstance(cur, dict) and cur:
        return cur
    saved = db_get("shared_ticker_intel", {})
    if not isinstance(saved, dict):
        saved = {}
    st.session_state["shared_ticker_intel"] = saved
    return saved

def sync_lab_intel_to_shared(r: dict, council_turns: list = None, rel_news_list: list = None, persist: bool = False):
    if not isinstance(r, dict) or not r.get("full_code"):
        return {}
    fc = str(r["full_code"]).strip().upper()
    intel_map = load_shared_ticker_intel()
    prev = intel_map.get(fc) if isinstance(intel_map.get(fc), dict) else {}
    now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existing_dd_res = prev.get("dd_result") if isinstance(prev.get("dd_result"), dict) else None
    existing_dd_ts = str(prev.get("dd_updated_at") or "")
    entry = {
        "lab_full": r,
        "lab_council": list(council_turns) if isinstance(council_turns, list) else list(prev.get("lab_council") or []),
        "lab_related_news": list(rel_news_list) if isinstance(rel_news_list, list) else list(prev.get("lab_related_news") or []),
        "lab_updated_at": now_s,
        "dd_result": existing_dd_res,
        "dd_updated_at": existing_dd_ts,
    }
    intel_map[fc] = entry
    st.session_state["shared_ticker_intel"] = intel_map
    if persist:
        db_set("shared_ticker_intel", intel_map)
    return entry

def sync_dd_intel_from_session(fc: str):
    if not fc:
        return
    fc_u = str(fc).strip().upper()
    intel_map = load_shared_ticker_intel()
    prev = intel_map.get(fc_u) if isinstance(intel_map.get(fc_u), dict) else {}
    dd_latest = st.session_state.get("dd_latest_result")
    dd_in_hub = prev.get("dd_result")
    updated_dd = None
    if isinstance(dd_latest, dict) and dd_latest:
        d_code = str(dd_latest.get("full_code") or dd_latest.get("code") or fc_u).strip().upper()
        if d_code in (fc_u, fc_u.replace(".T", "")):
            updated_dd = dd_latest
    elif isinstance(dd_in_hub, dict) and dd_in_hub:
        updated_dd = dd_in_hub
    if updated_dd is not None:
        prev["dd_result"] = updated_dd
        prev["dd_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        intel_map[fc_u] = prev
        st.session_state["shared_ticker_intel"] = intel_map
        db_set("shared_ticker_intel", intel_map)

def load_active_market_roster() -> list:
    roster = db_get("active_market_roster", None)
    if not isinstance(roster, list) or len(roster) < 15:
        roster = [[c, n, g, t] for c, n, g, t in GLOBAL_MARKET_TICKERS if c not in DELISTED_OR_INVALID_CODES]; db_set("active_market_roster", roster)
    else:
        filtered, seen_r = [], set()
        for it in roster:
            if len(it) >= 4 and it[0] not in DELISTED_OR_INVALID_CODES and it[0] not in seen_r: seen_r.add(it[0]); filtered.append(it)
        if len(filtered) != len(roster): roster = filtered; db_set("active_market_roster", roster)
    for item in roster:
        if len(item) >= 4: STOCK_METADATA_CACHE[item[0]] = {"name": item[1], "genre": item[2], "theme": item[3]}
    return roster

DEFAULT_AGENTS = {
    "IGNIS": {"name": "IGNIS", "icon": "🔥", "role_type": "scalper", "role_title": "短期モメンタム・OR15分初動ブレイク執行", "good": "OR15分初動レンジ維持判定・5分足CLV資金フローと押し目高値更新ブレイク執行", "bad": "VWAP乖離+1.5%超や+2σ超の高値飛びつきは厳格に抑止"},
    "TECHNOS": {"name": "TECHNOS", "icon": "📐", "role_type": "data", "role_title": "3階層MTF・価格帯別出来高(LVN/HVN)・OB構造解析", "good": "週足10Y×日足2Y×5分足60Dの3階層MTF統合、価格帯別出来高(LVN/HVN)、PDH/PDL・機関オーダーブロック(OB)構造解析", "bad": "定量的根拠のない主観的推測は一切排除"},
    "SENTINEL": {"name": "SENTINEL", "icon": "👁️", "role_type": "cynic", "role_title": "悪材料・直上しこり壁(HVN)・VWAP+2σ過熱リスク監査", "good": "直上HVNしこり抵抗帯・VWAP+2σ過熱・ストップ高上限余地・上ヒゲ拒絶ベクトル・悪材料ヘッドラインの徹底警戒", "bad": "期待値過大評価への厳格なブレーキ監査"},
    "AEGIS": {"name": "AEGIS", "icon": "🛡️", "role_type": "risk", "role_title": "リークフリー検証・SQN・最大DD・ケリー資金管理", "good": "完全リークフリー検証(勝率/PF/SQN/最大DD)・動的ケリー基準・東証呼値丸め逆指値と+1.0R半分利確管理", "bad": "検証未達(Grade-C)銘柄への無謀なエントリーを遮断"},
    "NEXUS": {"name": "NEXUS", "icon": "👑", "role_type": "leader", "role_title": "最終執行プラン・実戦適格ゲート裁定統括", "good": "5条件実戦適格ゲート・30分イントラデイRS先行度・投資スタイル別執行ルールの最終裁定統括", "bad": "一貫性のある冷徹な執行基準の維持"}
}

def load_quant_auditors() -> dict:
    return dict(DEFAULT_AGENTS)

def check_and_log_ban_spoof(em: str, nm: str, cfp: str, rhfp: str, p_h: str = "", act: str = "アクセス") -> tuple:
    em_c = em.strip().lower()
    if em_c == ADMIN_EMAIL.strip().lower(): return False, ""
    sec, db = load_sec(), load_mem()
    bf, be, bp, urec = sec.get("banned_fps", {}), sec.get("banned_emails", {}), sec.get("banned_pins", {}), db.get(em_c, {})
    rs, tgt = [], ""
    if urec.get("status") == "banned" or em_c in be: rs.append("永久BAN対象メールアドレス一致"); tgt = em_c
    if cfp and cfp != "-" and cfp in bf: rs.append(f"永久BAN環境ハッシュ(FP:{cfp})一致"); tgt = tgt or bf[cfp].get("email", "不明")
    if rhfp and rhfp != "-" and rhfp in bf: rs.append(f"永久BAN環境ヘッダハッシュ(HFP:{rhfp})一致"); tgt = tgt or bf[rhfp].get("email", "不明")
    if p_h and p_h in bp and em_c != bp[p_h]: rs.append(f"永久BAN会員({bp[p_h]})と同一PINハッシュ一致"); tgt = tgt or bp[p_h]
    if rs:
        now, r_str, is_sp = datetime.now().strftime("%Y-%m-%d %H:%M:%S"), " / ".join(rs), bool(tgt and em_c and em_c != tgt)
        log = {"time": now, "action": f"🚨 なりすまし{act}検知（※HTTPヘッダー環境ハッシュ＆日次HMACトークン照合）" if is_sp else f"🚫 永久BAN遮断({act})", "input_email": em_c or "未入力", "input_name": nm.strip() or urec.get("name", "不明"), "orig_banned_email": tgt or em_c, "fp": cfp, "raw_hfp": rhfp, "reason": r_str}
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
    to_c, now, route, c = to_em.strip().lower(), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "アプリ内暗号化メールBOX", load_smtp()
    u, p, srv, port = c.get("smtp_user", "").strip(), c.get("smtp_pass", "").strip(), c.get("smtp_server", "").strip(), int(c.get("smtp_port", 465))
    if u and p:
        try:
            m = MIMEText(body, "plain", "utf-8"); m["Subject"], m["From"], m["To"] = subj, u, to_c; ctx = ssl.create_default_context()
            with (smtplib.SMTP_SSL(srv, port, context=ctx, timeout=2.5) if port == 465 else smtplib.SMTP(srv, port, timeout=2.5)) as s:
                if port != 465: s.starttls(context=ctx)
                s.login(u, p); s.send_message(m)
            route = "SMTP直送信＋暗号化BOX"
        except Exception as e: record_system_error("send_mail:smtp", e, f"To: {to_c}")
    mdb = load_mail_db()
    mdb.setdefault("logs", []).insert(0, {"id": hashlib.md5(f"{to_c}_{now}".encode()).hexdigest()[:8], "time": now, "to": to_c, "from": ADMIN_EMAIL, "subject": subj, "body": body, "category": cat, "route": route})
    mdb["logs"] = mdb["logs"][:120]; db_set("mail", mdb)
    return True

def build_gemini_url(model: str, key: str = "") -> str:
    clean_m = str(model or "").strip()
    if clean_m.startswith("models/"): clean_m = clean_m[7:]
    clean_m = re.sub(r"[^A-Za-z0-9_\-\.]", "", clean_m) or "gemini-3-flash-preview"
    return f"https://generativelanguage.googleapis.com/v1beta/models/{clean_m}:generateContent"

def _gemini_safety_settings() -> list: return [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]

def _gemini_headers(api_key: str = "", use_bearer: bool = False) -> dict:
    h, clean_k_val = {"Content-Type": "application/json", "User-Agent": "YamashishiLab/3.0"}, sanitize_api_key(api_key)
    if clean_k_val:
        if use_bearer: h["Authorization"] = f"Bearer {clean_k_val}"
        else: h["x-goog-api-key"] = clean_k_val
    return h

@st.cache_data(ttl=3600)
def fetch_available_gemini_models(api_key: str) -> list:
    clean_k_val = sanitize_api_key(api_key)
    if not clean_k_val: return []
    url, ctx = "https://generativelanguage.googleapis.com/v1beta/models", ssl.create_default_context()
    for use_bearer in ([False, True] if clean_k_val.startswith("AQ.") else [False]):
        try:
            req = urllib.request.Request(url, headers=_gemini_headers(clean_k_val, use_bearer=use_bearer), method="GET")
            with urllib.request.urlopen(req, context=ctx, timeout=8.0) as r:
                data = json.loads(r.read().decode("utf-8"))
                avail = [m.get("name", "").replace("models/", "") for m in data.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", []) and not any(old in m.get("name", "") for old in ["gemini-1.", "gemini-2.0"]) and any(k in m.get("name", "") for k in ["flash", "pro"]) and not any(x in m.get("name", "") for x in ["image", "tts", "audio", "embedding", "vision", "deep-research"])]
                if avail:
                    avail.sort(key=lambda n: (0 if ("gemini-3" in n and "flash" in n and "lite" not in n) else (1 if ("gemini-3" in n and "pro" in n) else (2 if "gemini-3" in n else (3 if n == "gemini-2.5-flash" else (4 if n == "gemini-2.5-pro" else 5)))), n))
                    return avail
        except Exception: continue
    return []

def _build_fallback_chain(primary_model: str, api_key: str = "") -> list:
    chain = []
    for cand in [str(st.session_state.get("last_working_gemini_model", "") or "").strip()] + (fetch_available_gemini_models(api_key) if api_key else []) + [str(primary_model or "").strip()] + GEMINI_MODELS:
        if cand and cand not in chain: chain.append(cand)
    return chain[:6]

def _extract_gemini_response_text(resp_data: dict) -> str:
    cands = resp_data.get("candidates", [])
    if not cands or "content" not in cands[0]: return ""
    parts = cands[0]["content"].get("parts", [])
    non_thought = [p.get("text", "") for p in parts if "text" in p and not p.get("thought")]
    return "".join(non_thought) if non_thought else "".join([p.get("text", "") for p in parts if "text" in p])

def test_single_llm_api(mod: str, key: str) -> tuple:
    clean_api_k = sanitize_api_key(key)
    if not clean_api_k: return False, "Gemini APIキーが空です。キーを入力してからEnterを押してください。"
    if not _is_valid_gemini_key(clean_api_k): return False, f"APIキーの形式が正しくありません（入力値: {clean_api_k[:4]}...({len(clean_api_k)}文字)）。Google AI Studioのキー（AQ.〜 または AIza〜）を入力してください。"
    st.session_state["last_working_gemini_model"] = ""
    ctx, candidates, model_errors = ssl.create_default_context(), _build_fallback_chain(mod, clean_api_k), []
    key_preview = f"{clean_api_k[:6]}...{clean_api_k[-4:]} ({len(clean_api_k)}文字)"
    auth_attempts = [("x-goog-api-key", False, False), ("Authorization: Bearer", True, False), ("URL ?key=", False, True)] if clean_api_k.startswith("AQ.") else [("x-goog-api-key", False, False), ("URL ?key=", False, True)]
    for idx, m_test in enumerate(candidates):
        base_url = build_gemini_url(m_test, clean_api_k)
        d = json.dumps({"contents": [{"role": "user", "parts": [{"text": "Respond with OK"}]}], "generationConfig": {"maxOutputTokens": 256}, "safetySettings": _gemini_safety_settings()}).encode("utf-8")
        for auth_label, use_bearer, use_query_key in auth_attempts:
            try:
                req = urllib.request.Request(f"{base_url}?key={urllib.parse.quote(clean_api_k)}", data=d, headers=_gemini_headers(""), method="POST") if use_query_key else urllib.request.Request(base_url, data=d, headers=_gemini_headers(clean_api_k, use_bearer=use_bearer), method="POST")
                with urllib.request.urlopen(req, context=ctx, timeout=12.0) as r:
                    txt = _extract_gemini_response_text(json.loads(r.read().decode("utf-8")))
                    st.session_state["last_working_gemini_model"] = m_test
                    return True, f"接続成功 [認識キー: {key_preview}] (稼働モデル: {m_test}{' (※' + mod + 'から自動フォールバック)' if m_test != mod else ''}{' / 認証方式: ' + auth_label if (use_bearer or use_query_key) else ''})\n応答: {txt.strip()[:40]}"
            except urllib.error.HTTPError as he:
                err_body = ""
                try: err_body = he.read().decode("utf-8")
                except Exception: pass
                model_errors.append(f"・{m_test} [{auth_label}]: HTTP {he.code} ({re.sub(r'\\s+', ' ', err_body)[:120] or he.reason})")
                if he.code == 404: break
                if he.code in (400, 401, 403): time.sleep(0.05); continue
                break
            except Exception as e:
                model_errors.append(f"・{m_test} [{auth_label}]: 通信例外 ({str(e)})")
                if not use_query_key: time.sleep(0.05); continue
                break
        if idx < len(candidates) - 1: time.sleep(0.05)
    return False, f"全候補モデルの接続テストに失敗しました [送信キー: {key_preview}]:\n" + ("\n".join(model_errors) if model_errors else "詳細エラー情報なし")

def call_real_llm_api(sys_p: str, user_p: str, expect_json: bool = False) -> tuple:
    cfg = load_gemini_cfg(); api_key, sel_mod = sanitize_api_key(cfg.get("api_key", "")), cfg.get("model", "gemini-3-flash-preview")
    if not api_key: return None, ""
    ctx, candidates, gen_cfg = ssl.create_default_context(), _build_fallback_chain(sel_mod, api_key), {"temperature": 0.9, "maxOutputTokens": 4096}
    if expect_json: gen_cfg["responseMimeType"] = "application/json"
    d = json.dumps({"systemInstruction": {"parts": [{"text": sys_p}]}, "contents": [{"role": "user", "parts": [{"text": user_p}]}], "generationConfig": gen_cfg, "safetySettings": _gemini_safety_settings()}).encode("utf-8")
    auth_attempts = [("x-goog-api-key", False, False), ("Authorization: Bearer", True, False), ("URL ?key=", False, True)] if api_key.startswith("AQ.") else [("x-goog-api-key", False, False), ("URL ?key=", False, True)]
    for idx, cand in enumerate(candidates):
        base_url = build_gemini_url(cand, api_key)
        for auth_label, use_bearer, use_query_key in auth_attempts:
            req = urllib.request.Request(f"{base_url}?key={urllib.parse.quote(api_key)}", data=d, headers=_gemini_headers(""), method="POST") if use_query_key else urllib.request.Request(base_url, data=d, headers=_gemini_headers(api_key, use_bearer=use_bearer), method="POST")
            try:
                with urllib.request.urlopen(req, context=ctx, timeout=12.0) as r:
                    out_txt = _extract_gemini_response_text(json.loads(r.read().decode("utf-8")))
                    if out_txt: st.session_state["last_working_gemini_model"] = cand; return out_txt, cand
            except urllib.error.HTTPError as he:
                record_system_error("call_real_llm_api:http", he, f"Model: {cand}, Auth: {auth_label}, Code: {he.code}")
                if he.code == 404: break
                if he.code in (400, 401, 403): time.sleep(0.05); continue
                if he.code in (429, 500, 503): break
                return None, ""
            except Exception as e:
                record_system_error("call_real_llm_api", e, f"Model: {cand}, Auth: {auth_label}")
                if not use_query_key: time.sleep(0.05); continue
                break
        if idx < len(candidates) - 1: time.sleep(0.05)
    return None, ""

def register_biometric_device_db(user_email: str, bio_token: str = ""):
    em_c = user_email.strip().lower()
    if not em_c: return
    db, sec, rhfp, cfp, now_ts, now_str = load_mem(), load_sec(), get_raw_header_fp(), get_client_fp(), int(time.time()), datetime.now().strftime("%Y-%m-%d %H:%M")
    tok = bio_token or gen_tok(em_c, "session_keep")
    if em_c in db: db[em_c].update({"bio_enabled": True, "fp": cfp, "raw_hfp": rhfp, "last_seen_ts": now_ts, "last_seen_str": now_str}); db_set("mem", db)
    dev_entry = {"email": em_c, "token": tok, "fp": cfp, "raw_hfp": rhfp, "updated_ts": now_ts}
    bio_map = sec.setdefault("device_bio_map", {})
    if rhfp and rhfp != "-": bio_map[rhfp] = dev_entry
    if cfp and cfp != "-": bio_map[cfp] = dev_entry
    bio_map.pop("default_bio_device", None); db_set("sec", sec)

def render_biometric_bridge(mode="login", user_email="", bio_token=""):
    db, sec, rhfp, cfp = load_mem(), load_sec(), get_raw_header_fp(), get_client_fp()
    if mode == "register":
        lbl = "✅ 端末環境トークン・ワンタップ登録済" if db.get(user_email, {}).get("bio_enabled") else "🔑 この端末環境をワンタップ登録"
        if st.button(lbl, key=f"bio_{user_email}", use_container_width=True): register_biometric_device_db(user_email, bio_token); st.success("✅ この端末のHTTPヘッダー環境ハッシュ＆日次HMACトークン認証を登録しました")
        return
    bio_map = sec.get("device_bio_map", {}); mp = bio_map.get(cfp) or bio_map.get(rhfp)
    if st.button("🔑 登録済み端末：環境ハッシュ / ワンタップで即ログイン", use_container_width=True, type="primary"):
        if mp and mp.get("email"):
            tem = mp["email"].strip().lower(); urec = db.get(tem, {})
            fp_matched = (mp.get("fp") == cfp or mp.get("raw_hfp") == rhfp)
            tok_valid = bool(mp.get("token")) and hmac.compare_digest(str(mp.get("token")), gen_tok(tem, "session_keep"))
            is_b, _ = check_and_log_ban_spoof(tem, urec.get("name", ""), cfp, rhfp, urec.get("pin_hash", ""), "ワンタップログイン")
            if is_b or urec.get("status") == "banned": st.error("💀 このアカウントまたは端末は永久BAN（アクセス禁止）されています。")
            elif urec.get("status") == "suspended": st.error("🚫 アカウント一時停止中です。")
            elif (cfp in sec.get("banned_fps", {}) or rhfp in sec.get("banned_fps", {})) and tem != ADMIN_EMAIL.strip().lower(): st.error("🚫 端末制限中です。")
            elif not fp_matched or not tok_valid: st.warning("⚠️ 端末トークンの有効期限切れ、またはHTTPヘッダー環境ハッシュが一致しません。下のフォームから専用コードで再認証してください。")
            elif (urec and urec.get("status") == "approved" and urec.get("bio_enabled")) or tem == ADMIN_EMAIL.strip().lower():
                kt = gen_tok(tem, "session_keep"); register_biometric_device_db(tem, kt)
                st.session_state["authenticated_user"] = tem; st.query_params["u"], st.query_params["t"] = tem, kt; st.rerun()
            else: st.warning("⚠️ この端末は未登録です。初回は下のフォームから専用コードでログインしてください。")
        else:
            is_b, _ = check_and_log_ban_spoof("", "未認証端末", cfp, rhfp, "", "ワンタップ試行")
            if is_b: st.error("💀 この端末は永久BAN（アクセス禁止）されています。")
            else: st.warning("⚠️ この端末は未登録です。初回は下のフォームから専用コードでログインしてください（次回から自動登録されます）。")

def inject_css():
    css = """@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;800&family=Plus+Jakarta+Sans:wght@400;600;800&family=JetBrains+Mono:wght@500;700;800&display=swap');
html,body,[class*="css"]{font-family:'Plus Jakarta Sans',sans-serif;font-size:14px;background-color:#070b14;color:#e2e8f0;}
.block-container{padding-top:2.9rem!important;}
div[data-baseweb="popover"],div[data-baseweb="menu"],div[role="listbox"],ul[role="listbox"]{z-index:2147483647!important;pointer-events:auto!important;}
header[data-testid="stHeader"]{background:transparent!important;pointer-events:none!important;height:3.5rem!important;z-index:999980!important;}
header[data-testid="stHeader"] [data-testid="stToolbar"],header[data-testid="stHeader"] [data-testid="stActionButtons"]{display:none!important;}
section[data-testid="stSidebar"]{position:fixed!important;top:0!important;left:0!important;height:100vh!important;z-index:999995!important;width:330px!important;max-width:88vw!important;min-width:320px!important;background:rgba(7,11,20,0.98)!important;backdrop-filter:blur(25px)!important;border-right:1px solid rgba(56,189,248,0.35)!important;visibility:visible!important;transition:transform 0.28s cubic-bezier(0.4,0,0.2,1)!important;}
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
.fixed-top-nav-bar button:hover{background:rgba(15,23,42,0.85)!important;border-color:rgba(56,189,248,0.55)!important;color:#ffffff!important;}
.fixed-top-nav-bar button:active{background:rgba(56,189,248,0.25)!important;border-color:#38bdf8!important;color:#ffffff!important;transform:scale(0.96)!important;}
.brand-luxury{font-family:'Cinzel',serif!important;font-size:clamp(16px,4.2vw,23px)!important;font-weight:800!important;letter-spacing:clamp(1px,0.5vw,3px)!important;background:linear-gradient(90deg,#f8fafc 0%,#38bdf8 50%,#a855f7 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1.25;white-space:nowrap!important;display:block;width:100%;}
.glass-header{background:radial-gradient(circle at top right,rgba(168,85,247,0.12),transparent 60%),linear-gradient(145deg,rgba(15,23,42,0.88) 0%,rgba(7,11,20,0.96) 100%);backdrop-filter:blur(12px);border:1px solid rgba(148,163,184,0.16);border-radius:12px;padding:10px 13px;margin-bottom:8px;box-shadow:0 8px 24px rgba(0,0,0,0.45);}
.lab-thin-ribbon{display:flex!important;flex-wrap:nowrap!important;align-items:center!important;overflow-x:auto!important;-webkit-overflow-scrolling:touch!important;scrollbar-width:none!important;gap:6px!important;padding:3px 2px!important;margin-bottom:6px!important;white-space:nowrap!important;}
.lab-thin-ribbon::-webkit-scrollbar{display:none!important;}
.lab-ribbon-chip{display:inline-flex;align-items:center;gap:4px;background:rgba(15,23,42,0.78);border:1px solid rgba(148,163,184,0.18);border-radius:6px;padding:3px 8px;font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;font-size:10.5px;flex-shrink:0;}
.rank-card,.search-result-card{background:linear-gradient(180deg,rgba(15,23,42,0.92) 0%,rgba(7,11,20,0.98) 100%)!important;backdrop-filter:blur(10px);color:#f8fafc!important;border-radius:14px;padding:13px 15px;margin-top:8px;margin-bottom:10px;box-shadow:0 10px 28px rgba(0,0,0,0.55);border:1px solid rgba(148,163,184,0.18);border-left:4px solid #38bdf8;font-variant-numeric:tabular-nums;}
.search-result-card{border-left-color:#f59e0b;}
.card-top-meta{display:flex;align-items:center;justify-content:space-between;gap:6px;flex-wrap:wrap;margin-bottom:6px;}
.card-hero-row{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;}
.card-kpi-right{text-align:right;flex-shrink:0;font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;}
.prob-badge{font-family:'JetBrains Mono',monospace;font-size:clamp(13.5px,3.6vw,15.5px);font-weight:800;color:#38bdf8!important;}
.expect-badge{font-family:'JetBrains Mono',monospace;font-size:clamp(15px,4vw,18px);font-weight:900;color:#fde047!important;}
.card-action-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;background:rgba(2,6,23,0.72);border:1px solid rgba(148,163,184,0.16);border-radius:9px;padding:7px 6px;margin-top:8px;text-align:center;font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;}
@media (max-width:640px){.card-action-grid{grid-template-columns:repeat(2,1fr);}}
.card-action-cell{padding:2px 4px;}
.card-action-lbl{font-size:9.3px;color:#94a3b8;font-family:'Plus Jakarta Sans',sans-serif;font-weight:700;}
.card-action-val{font-size:12px;font-weight:800;margin-top:1px;}
.card-perf-strip{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:6px;background:rgba(15,23,42,0.72);border:1px solid rgba(56,189,248,0.22);border-radius:7px;padding:5px 9px;margin-top:6px;font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;font-size:10.5px;color:#cbd5e1;}
.winrate-bar{display:grid;grid-template-columns:repeat(auto-fit,minmax(65px,1fr));gap:6px;background:rgba(15,23,42,0.85)!important;border:1px solid rgba(148,163,184,0.18);border-radius:8px;padding:7px 6px;margin-top:6px!important;text-align:center;font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;}
.trade-plan-box{display:grid;grid-template-columns:repeat(auto-fit,minmax(85px,1fr));gap:6px;margin-top:6px!important;background:rgba(2,6,23,0.7)!important;padding:7px 6px;border-radius:8px;border:1px solid rgba(148,163,184,0.18);text-align:center;font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;}
.order-ticket-box{background:linear-gradient(135deg,rgba(15,23,42,0.96) 0%,rgba(8,47,73,0.92) 100%);border:1.5px solid #38bdf8;border-radius:10px;padding:10px 12px;margin-bottom:10px;box-shadow:0 4px 16px rgba(56,189,248,0.18);font-variant-numeric:tabular-nums;}
.order-ticket-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:6px;margin-top:6px;}
.order-ticket-cell{background:rgba(2,6,23,0.78);border:1px solid rgba(148,163,184,0.22);border-radius:6px;padding:6px 8px;font-family:'JetBrains Mono',monospace;}
.admin-table-container{width:100%;overflow-x:auto;background:#0b0f19;border:1px solid rgba(56,189,248,0.25);border-radius:10px;margin-top:10px;}
.admin-table{width:100%;border-collapse:collapse;font-size:11.5px;text-align:left;color:#e2e8f0;}
.admin-table th{background:#1e293b;color:#38bdf8;padding:8px 10px;border-bottom:1px solid rgba(56,189,248,0.3);font-weight:700;white-space:nowrap;}
.admin-table td{padding:8px 10px;border-bottom:1px solid rgba(148,163,184,0.1);white-space:nowrap;}
.admin-table tr:hover{background:rgba(56,189,248,0.05);}
.ai-council-box{background:rgba(8,12,22,0.98);border:1px solid rgba(56,189,248,0.35);border-radius:10px;padding:12px;margin-top:10px;}
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
.combat-guide-box{background:rgba(56,189,248,0.08);border:1px solid rgba(56,189,248,0.26);padding:7px 10px;border-radius:6px;margin-top:6px;font-size:10.8px;color:#bae6fd;line-height:1.55;}
.macro10y-box{background:rgba(168,85,247,0.10);border:1px solid rgba(168,85,247,0.32);padding:7px 10px;border-radius:6px;margin-top:6px;font-size:10.8px;color:#e9d5ff;line-height:1.55;}
.daily2y-box{background:rgba(14,165,233,0.10);border:1px solid rgba(14,165,233,0.34);padding:7px 10px;border-radius:6px;margin-top:6px;font-size:10.8px;color:#bae6fd;line-height:1.55;}
.forward-verify-bar{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:4px;background:linear-gradient(90deg,rgba(16,185,129,0.14),rgba(56,189,248,0.14));border:1px solid rgba(56,189,248,0.35);padding:6px 10px;border-radius:6px;margin-top:6px;font-size:11px;color:#e2e8f0;font-variant-numeric:tabular-nums;}
.quant-detail-drawer{margin-top:8px;background:rgba(2,6,23,0.62);border:1px solid rgba(148,163,184,0.18);border-radius:8px;padding:7px 10px;font-size:11.5px;cursor:pointer;}
.quant-detail-drawer summary{font-weight:800;color:#7dd3fc;outline:none;}
.pill-badge{font-size:clamp(9.5px,2.4vw,10.5px);padding:2px 6px;border-radius:5px;border:1px solid rgba(148,163,184,0.28);margin-right:3px;display:inline-block;white-space:nowrap!important;font-family:'JetBrains Mono',monospace;}
.quantum-badge{font-size:clamp(9.5px,2.4vw,10.5px);padding:2px 6px;border-radius:5px;background:rgba(168,85,247,0.15);border:1px solid rgba(168,85,247,0.4);color:#c084fc;margin-right:3px;display:inline-block;white-space:nowrap!important;font-family:'JetBrains Mono',monospace;}
.inst-badge{font-size:clamp(9.5px,2.4vw,10.5px);padding:2px 6px;border-radius:5px;background:rgba(56,189,248,0.15);border:1px solid rgba(56,189,248,0.4);color:#38bdf8;margin-right:3px;display:inline-block;white-space:nowrap!important;font-family:'JetBrains Mono',monospace;}
.compact-bar-label{font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:800;color:#38bdf8;letter-spacing:0.6px;margin:4px 0 4px 2px;}
.ipo-link-btn{display:inline-block;padding:5px 12px;background:rgba(245,158,11,0.2);border:1px solid #f59e0b;border-radius:6px;color:#fde047;text-decoration:none;font-size:11.5px;font-weight:700;margin-right:6px;margin-top:4px;}
.consensus-banner{background:rgba(15,23,42,0.95);border:1px solid rgba(250,204,21,0.4);border-radius:10px;padding:12px;margin-top:10px;}
.disclaimer-banner{background:rgba(15,23,42,0.6);border:1px solid rgba(148,163,184,0.15);border-radius:8px;padding:10px 14px;margin-top:25px;margin-bottom:15px;font-size:11px;line-height:1.6;color:#94a3b8;}
.svg-chart-wrap{background:rgba(2,6,23,0.88);border:1px solid rgba(56,189,248,0.32);border-radius:10px;padding:8px 10px;margin-top:8px;margin-bottom:8px;overflow-x:auto;}
.manual-card{background:rgba(15,23,42,0.92);border:1px solid rgba(56,189,248,0.28);border-left:4px solid #38bdf8;border-radius:10px;padding:12px 14px;margin-bottom:10px;}
@keyframes alert-pulse{0%{box-shadow:0 0 0 0 rgba(239,68,68,0.8);}70%{box-shadow:0 0 0 10px rgba(239,68,68,0);}100%{box-shadow:0 0 0 0 rgba(239,68,68,0);}}"""
    st.markdown(f'<div id="page_top_anchor"></div><style>{css}</style>', unsafe_allow_html=True)

inject_css()

def check_auth():
    qu, qt = st.query_params.get("u", "").strip().lower(), st.query_params.get("t", "").strip()
    if "authenticated_user" not in st.session_state: st.session_state["authenticated_user"] = None
    db, cfp, rhfp = load_mem(), get_client_fp(), get_raw_header_fp()
    if not st.session_state["authenticated_user"] and qu and qt:
        if hmac.compare_digest(qt, gen_tok(qu, "session_keep")) and ((db.get(qu) and db[qu].get("status") == "approved") or qu == ADMIN_EMAIL.strip().lower()): st.session_state["authenticated_user"] = qu
    if st.session_state["authenticated_user"]:
        cu = st.session_state["authenticated_user"]; urec = db.get(cu, {})
        if cu != ADMIN_EMAIL.strip().lower():
            is_b, _ = check_and_log_ban_spoof(cu, urec.get("name", ""), cfp, rhfp, urec.get("pin_hash", ""), "セッション維持")
            if is_b or urec.get("status") == "banned": st.session_state["authenticated_user"] = None; st.query_params.clear(); st.error("💀 このアカウントまたは端末は永久BANされています。"); st.stop()
            if not urec or urec.get("status") != "approved": st.session_state["authenticated_user"] = None; st.query_params.clear(); st.error("🚫 アカウント一時停止中、または削除されています。"); st.stop()
        kt = gen_tok(cu, "session_keep")
        if st.query_params.get("u") != cu or st.query_params.get("t") != kt: st.query_params["u"], st.query_params["t"] = cu, kt
        return True
    st.markdown('<style>section[data-testid="stSidebar"]{display:none!important;transform:translateX(-150%)!important;}#yamashishi-floating-sidebar-btn{display:none!important;}</style>', unsafe_allow_html=True)
    st.markdown('<div class="glass-header" style="text-align:center;padding:18px 12px;"><div class="brand-luxury">YAMASHISHI LAB</div><div class="brand-sub" style="margin-top:4px;">5-MIN 60D × DAILY 2Y × WEEKLY 10Y 3-TIER MTF QUANTITATIVE TERMINAL</div><div style="display:flex;justify-content:center;gap:8px;margin-top:10px;flex-wrap:wrap;"><span class="quantum-badge">⚛️ 3階層MTF融合 (週足10Y×日足2Y×5分足60D)</span><span class="inst-badge">🏛️ 5分足需給×日足トレンド×10年大局</span><span class="pill-badge" style="color:#10b981;border-color:rgba(16,185,129,0.3);">🔑 環境ハッシュ＆HMACトークン認証</span></div></div>', unsafe_allow_html=True)
    render_biometric_bridge(mode="login")
    tab_login, tab_apply, tab_vault = st.tabs(["🔑 コードログイン", "📩 新規会員登録申請", "🔐 承認確認・暗号化コード照会"])
    with tab_login:
        with st.form("login"):
            ie, ic = st.text_input("📧 登録メールアドレス", placeholder="your@email.com"), st.text_input("🔑 専用アクセスコード", type="password", placeholder="8桁の専用コード")
            if st.form_submit_button("🔓 認証してターミナルを起動", use_container_width=True):
                cm, adm_c = ie.strip().lower(), ADMIN_EMAIL.strip().lower(); rec = db.get(cm)
                if (rec and rec.get("status") == "approved" or cm == adm_c) and ((cm == adm_c and hmac.compare_digest(ic.strip(), ADMIN_PASS)) or (rec and rec.get("status") == "approved" and hmac.compare_digest(ic.strip().upper(), gen_code(cm)))):
                    kt = gen_tok(cm, "session_keep"); register_biometric_device_db(cm, kt); st.session_state["authenticated_user"] = cm; st.query_params["u"], st.query_params["t"] = cm, kt; st.rerun()
                else: st.warning("⚠️ 未承認または専用アクセスコードが異なります。")
    with tab_apply:
        with st.form("apply"):
            st.caption("🔐 セキュリティ保護のため、申請時に「あなただけの4桁の暗証番号(PIN)」を設定してください。")
            an, am, apin = st.text_input("👤 お名前（ニックネーム可）"), st.text_input("📧 メールアドレス"), st.text_input("🔢 秘密の4桁暗証番号 (PIN・数字4桁)", type="password", max_chars=4, placeholder="例: 7788")
            if st.form_submit_button("📨 セキュア会員登録を申請する", use_container_width=True):
                if "@" not in am or len(apin.strip()) < 4 or not apin.strip().isdigit(): st.warning("⚠️ 正しいメールアドレスと数字4桁の暗証番号(PIN)を入力してください。")
                else:
                    cm, ns = am.strip().lower(), datetime.now().strftime("%Y-%m-%d %H:%M"); nm, ph = an.strip() or "未入力", hash_pin(apin, cm)
                    is_b, _ = check_and_log_ban_spoof(cm, nm, cfp, rhfp, ph, "新規登録申請")
                    if is_b or (db.get(cm) and db[cm].get("status") == "banned"): st.error("💀 セキュリティ監視システムにより、申請は永久ブロックされました。")
                    else:
                        db[cm] = {"name": nm, "email": cm, "status": "pending", "passcode": gen_code(cm), "pin_hash": ph, "applied_at": ns, "approved_at": "-", "last_seen_ts": 0, "last_seen_str": "-", "fp": cfp, "raw_hfp": rhfp, "bio_enabled": False, "deep_dive_status": "none", "deep_dive_allowed": False}; db_set("mem", db)
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
                elif u_info.get("pin_hash") and not verify_pin(u_info.get("pin_hash", ""), chk_pin, chk_em): st.error("🚫 暗証番号(PIN)が一致しません。")
                elif u_info.get("status") == "approved":
                    if len(u_info.get("pin_hash", "")) < 24: u_info["pin_hash"] = hash_pin(chk_pin, chk_em); db[chk_em] = u_info; db_set("mem", db)
                    st.success(f"🎉 本人確認完了・承認済みです！専用アクセスコード: **`{u_info.get('passcode', gen_code(chk_em))}`**")
                elif u_info.get("status") == "pending": st.info("⏳ 本人確認完了：現在、管理者の承認審査待ちです。")
                else: st.error("🚫 現在このアカウントは一時停止中または利用できません。")
    st.stop()

check_auth()

saved_agents = load_quant_auditors()
cu_active = st.session_state.get("authenticated_user", "")
user_saved_prefs, user_saved_watchlist = load_user_prefs(cu_active), load_watchlist(cu_active)

if "user_prefs_loaded" not in st.session_state or st.session_state.get("last_loaded_user") != cu_active:
    st.session_state["investment_style_choice"] = user_saved_prefs.get("investment_style", "⚡ デイトレード (前場・後場の波及を狙う)")
    st.session_state["total_capital_val"] = int(user_saved_prefs.get("total_capital", 1000000))
    st.session_state["risk_tolerance_val"] = float(user_saved_prefs.get("risk_tolerance_pct", 2.0))
    st.session_state["survival_cut_val"] = int(user_saved_prefs.get("survival_cut_pct", 75))
    saved_boosts = set(_normalize_boost_keys(user_saved_prefs.get("active_boosts", ["core_vol", "core_inst", "core_mom"])))
    for bk in ["core_vol", "core_inst", "core_mom"]: st.session_state[f"chk_{bk}"] = (bk in saved_boosts)
    st.session_state["watchlist"] = user_saved_watchlist; st.session_state["user_prefs_loaded"] = True; st.session_state["last_loaded_user"] = cu_active
    st.session_state["_last_saved_prefs_hash"] = hashlib.md5(json.dumps({"user": cu_active, "prefs": user_saved_prefs}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

defaults = {"active_debates": {}, "council_threads": {}, "council_meta": {}, "debate_round_seed": {}, "watchlist": user_saved_watchlist, "navigation_page": "TOP", "selected_news_item": None, "custom_search_code": "", "active_category": "🏆 総合TOP5", "last_cat": "🏆 総合TOP5", "nav_history": [], "scroll_top_trig": 0, "scroll_target_id": "", "focused_stock_item": None, "agent_roster": saved_agents, "stock_dialogue_signatures": {}, "news_ai_deep_cache": {}, "last_audit_similarity_penalty": 0, "last_working_gemini_model": "", "force_close_sidebar_trig": 0, "last_synced_style": "", "journal_audit_results": {}, "dd_lab_ctx": None, "shared_ticker_intel": db_get("shared_ticker_intel", {})}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v
if not isinstance(st.session_state.get("shared_ticker_intel"), dict):
    st.session_state["shared_ticker_intel"] = {}
st.session_state["agent_roster"] = dict(DEFAULT_AGENTS)

with st.container():
    st.markdown('<div class="top-nav-marker"></div>', unsafe_allow_html=True)
    if st.button("トップに戻る", key="top_nav_top", use_container_width=True):
        st.session_state["navigation_page"] = "TOP"; st.session_state["focused_stock_item"] = None; st.session_state["custom_search_code"] = ""; st.session_state["selected_news_item"] = None; st.session_state["active_category"] = "🏆 総合TOP5"; st.session_state["last_cat"] = "🏆 総合TOP5"
        if "search_code_input" in st.session_state: st.session_state["search_code_input"] = ""
        st.session_state["scroll_top_trig"] = int(time.time() * 1000); st.session_state["force_close_sidebar_trig"] = int(time.time() * 1000); st.rerun()

scroll_target_js = f"setTimeout(function(){{try{{const el=window.parent.document.getElementById('{st.session_state.get('scroll_target_id')}');if(el){{const win=el.closest('.council-scroll-window');if(win){{win.scrollTo({{top:Math.max(0,el.offsetTop-4),behavior:'smooth'}});}}(el.closest('.ai-council-box')||el).scrollIntoView({{behavior:'smooth',block:'center'}});}}}}catch(e){{}}}},120);" if st.session_state.get("scroll_target_id") else ""
st.session_state["scroll_target_id"] = ""

is_overlay_page_active = (st.session_state.get("navigation_page") in ("ADMIN", "MANUAL", "DEEP_DIVE"))
force_close_trig = int(st.session_state.get("force_close_sidebar_trig", 0))
force_close_js = "window.parent.sessionStorage.setItem('yamashishi_sb_state','closed');closeCustomSidebar();" if is_overlay_page_active else (f"if(window.parent._lastForceCloseTrig!=={force_close_trig}){{window.parent._lastForceCloseTrig={force_close_trig};window.parent.sessionStorage.setItem('yamashishi_sb_state','closed');closeCustomSidebar();}}" if force_close_trig > 0 else "")

components.html(f"""<script>(function(){{const doc=window.parent.document;function closeCustomSidebar(){{try{{const sb=doc.querySelector('section[data-testid="stSidebar"]'),o=doc.getElementById('yamashishi-sidebar-backdrop');if(sb){{sb.setAttribute('aria-expanded','false');sb.style.setProperty('transform','translateX(-120%)','important');sb.style.setProperty('pointer-events','none','important');}}if(o){{o.style.setProperty('display','none','important');o.style.setProperty('pointer-events','none','important');}}window.parent.sessionStorage.setItem('yamashishi_sb_state','closed');}}catch(e){{}}}}function openCustomSidebar(){{try{{const sb=doc.querySelector('section[data-testid="stSidebar"]'),o=doc.getElementById('yamashishi-sidebar-backdrop');if(sb){{sb.setAttribute('aria-expanded','true');sb.style.setProperty('transform','translateX(0)','important');sb.style.setProperty('pointer-events','auto','important');}}if(o){{o.style.setProperty('display','block','important');o.style.setProperty('pointer-events','auto','important');}}window.parent.sessionStorage.setItem('yamashishi_sb_state','open');}}catch(e){{}}}}window.parent._yamashishiCloseSidebar=closeCustomSidebar;window.parent._yamashishiOpenSidebar=openCustomSidebar;function setupCustomSidebar(){{try{{if(!doc.getElementById('yamashishi-custom-sidebar-styles')){{const s=doc.createElement('style');s.id='yamashishi-custom-sidebar-styles';s.textContent=`#yamashishi-floating-sidebar-btn{{position:fixed!important;top:8px!important;left:10px!important;z-index:2147483647!important;display:flex!important;align-items:center!important;justify-content:center!important;gap:4px!important;height:28px!important;padding:0 10px 0 8px!important;background:rgba(11,15,25,0.95)!important;backdrop-filter:blur(16px)!important;border:1.5px solid rgba(56,189,248,0.7)!important;border-radius:8px!important;cursor:pointer!important;box-shadow:0 4px 18px rgba(0,0,0,0.75),0 0 12px rgba(56,189,248,0.3)!important;user-select:none!important;transition:transform 0.1s ease!important;color:#38bdf8!important;pointer-events:auto!important;outline:none!important;-webkit-tap-highlight-color:transparent!important;}}#yamashishi-floating-sidebar-btn:active{{border-color:#fde047!important;color:#fde047!important;transform:scale(0.95)!important;}}#yamashishi-floating-sidebar-btn svg{{width:15px!important;height:15px!important;}}#yamashishi-floating-sidebar-btn span{{font-family:'JetBrains Mono',monospace!important;font-size:11px!important;font-weight:800!important;}}#yamashishi-sidebar-backdrop{{position:fixed!important;top:0!important;left:0!important;width:100vw!important;height:100vh!important;background:rgba(0,0,0,0.45)!important;backdrop-filter:blur(2px)!important;z-index:999990!important;display:none;pointer-events:auto!important;cursor:pointer!important;}}`;doc.head.appendChild(s);}}let o=doc.getElementById('yamashishi-sidebar-backdrop');if(!o){{o=doc.createElement('div');o.id='yamashishi-sidebar-backdrop';doc.body.appendChild(o);}}o.onclick=function(e){{e.preventDefault();e.stopPropagation();window.parent._yamashishiCloseSidebar();}};let b=doc.getElementById('yamashishi-floating-sidebar-btn');if(!b){{b=doc.createElement('div');b.id='yamashishi-floating-sidebar-btn';b.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg><span>MENU</span>';doc.body.appendChild(b);}}b.onclick=function(e){{e.preventDefault();e.stopPropagation();const sb=doc.querySelector('section[data-testid="stSidebar"]');const isOpen=sb&&(sb.getAttribute('aria-expanded')==='true'||window.parent.sessionStorage.getItem('yamashishi_sb_state')==='open');if(isOpen){{window.parent._yamashishiCloseSidebar();}}else{{window.parent._yamashishiOpenSidebar();}}}};if(doc._yamashishiOutsideHandler){{doc.removeEventListener('pointerdown',doc._yamashishiOutsideHandler,true);doc.removeEventListener('click',doc._yamashishiOutsideHandler,true);}}doc._yamashishiOutsideHandler=function(e){{const sb=doc.querySelector('section[data-testid="stSidebar"]'),btn=doc.getElementById('yamashishi-floating-sidebar-btn');const isOpen=sb&&(sb.getAttribute('aria-expanded')==='true'||window.parent.sessionStorage.getItem('yamashishi_sb_state')==='open');if(!isOpen)return;const t=e.target;if((sb&&sb.contains(t))||(btn&&btn.contains(t))||(t&&t.closest&&t.closest('[data-baseweb="popover"],[data-baseweb="menu"],[role="listbox"],ul[role="listbox"]')))return;window.parent._yamashishiCloseSidebar();}};doc.addEventListener('pointerdown',doc._yamashishiOutsideHandler,true);doc.addEventListener('click',doc._yamashishiOutsideHandler,true);{force_close_js}if(window.parent.sessionStorage.getItem('yamashishi_sb_state')==='open'){{openCustomSidebar();}}else{{closeCustomSidebar();}}}}catch(e){{}}}}function fixTopNav(){{try{{const m=doc.querySelector('.top-nav-marker');if(!m)return;let bx=m.closest('[data-testid="stVerticalBlockBorderWrapper"]')||m.closest('[data-testid="stVerticalBlock"]');if(bx&&bx.querySelector('button'))bx.classList.add('fixed-top-nav-bar');}}catch(e){{}}}}setupCustomSidebar();fixTopNav();function scrollToTopAbsolute(){{try{{window.parent.scrollTo(0,0);}}catch(e){{}}[doc.documentElement,doc.body,doc.querySelector('section.main'),doc.querySelector('[data-testid="stAppViewContainer"]')].forEach(el=>{{if(el){{try{{el.scrollTop=0;}}catch(e){{}}}}}});const ta=doc.getElementById('page_top_anchor');if(ta&&typeof ta.scrollIntoView==='function')try{{ta.scrollIntoView({{behavior:'instant',block:'start'}});}}catch(e){{}}}}if({st.session_state['scroll_top_trig']}>0&&window.parent._lastScrollTrig!=={st.session_state['scroll_top_trig']}){{window.parent._lastScrollTrig={st.session_state['scroll_top_trig']};scrollToTopAbsolute();}}{scroll_target_js}}})();</script>""", height=0)

def _compute_real_audit_metrics() -> dict:
    err_cnt = len(get_system_error_logs())
    sim_pen = int(st.session_state.get("last_audit_similarity_penalty", 0))
    gem_ok = bool(load_gemini_cfg().get("api_key"))
    ledger = db_get("daily_forward_ledger", {})
    ledger_entries = len(ledger) if isinstance(ledger, dict) else 0
    return {"health_score": int(np.clip(100 - min(25, err_cnt * 2) - sim_pen, 55, 100)), "err_cnt": err_cnt, "sim_pen": sim_pen, "gem_ok": gem_ok, "ledger_entries": ledger_entries}

def render_user_manual_page():
    st.markdown('<div class="glass-header" style="border-left:4px solid #38bdf8;"><div style="font-size:18px;font-weight:800;color:#f8fafc;">📖 YAMASHISHI LAB 公式説明書・用語＆アルゴリズム辞典</div><div style="font-size:11.5px;color:#94a3b8;margin-top:4px;">銘柄カードに表示される独自指標・執行グレード・3階層MTF・チャート記号・リークフリー検証の意味と実戦での使い方をわかりやすく解説します。</div></div>', unsafe_allow_html=True)
    if st.button("⬅️ メイン画面に戻る", key="manual_back_top", use_container_width=True, type="primary"):
        st.session_state["navigation_page"] = "TOP"
        st.session_state["force_close_sidebar_trig"] = int(time.time() * 1000)
        st.session_state["scroll_top_trig"] = int(time.time() * 1000)
        st.rerun()

    q_kw = st.text_input("🔍 分からない用語・記号を検索 (例: Grade, VWAP, SQN, HVN, RVOL, OB, Fusion)", placeholder="キーワードを入力すると該当解説だけをリアルタイム絞り込み表示します...", key="manual_search_input").strip().lower()

    manual_sections = [
        {
            "cat_id": "grade",
            "tab": "🚦 1. 執行品質グレード＆5条件ゲート・DD統合",
            "items": [
                ("🔥 LAB × DEEP DIVE 双方向統合（Fusion期待度＆同期判定）", "上位足・日足・5分足60日を評価する『YAMASHISHI LAB』と、当日5分足軌道・CVD・30分3分岐を解析する『DEEP DIVE』を双方向連動させた統合判定です。両者の方向性が一致すれば『🟢 LAB×DD完全同期』、乖離している場合は『⚠️ LAB×DD乖離警戒（押し目/戻り待ち推奨）』を表示します。", "【実戦の目安】DEEP DIVEで解析した銘柄はLABのチャート・OCOチケット・5名監査官へ自動反映されます。"),
                ("🟢 Grade-A: 即時執行適格（全5条件クリア）", "5つの定量条件すべてに合格した最上位シグナルです。上位足（週足10年・日足2年）と当日5分足の方向が一致し、かつ値動きの効率性・出来高・ヒゲ形状も良好なため、ルール通りのエントリーが最も機能しやすい状態です。", "【実戦の目安】5/5条件クリア。計画されたエントリー価格・逆指値（SL）・+1.0R半分利確に従って執行します。"),
                ("🔵 Grade-B: 標準執行（4/5条件クリア・基準厳守）", "主要4条件をクリアした標準的な執行適格銘柄です。1項目だけ軽微な注意（例：ややRVOL控えめ等）があるため、飛びつき買いを避け、必ずVWAPや押し目支持線まで引きつけてから指値・逆指値で執行します。", "【実戦の目安】4/5条件クリア。高値追いせず引きつけてエントリー。"),
                ("🟡 Grade-C: 様子見・押し目/戻り待機（3条件以下）", "上位足と短期足の方向が噛み合っていない、上ヒゲ（売り圧力）が強すぎる、出来高不足、または過去検証成績（PF/勝率）が基準未満の状態です。リークフリー検証でもGrade-Cの日は『見送り（NO TRADE）』として無駄打ちを遮断しています。", "【実戦の目安】新規エントリーは見送り、条件が揃ってGrade-B以上に昇格するまで待機します。"),
                ("⚠️ 決算跨ぎ警戒 / VWAP+2σ過熱 / ストップ高張り付き減点", "①決算発表まで3営業日以内の銘柄は決算ギャンブル回避のため自動でグレード減点＋推奨ロット半減。②現在値がVWAP+2σを超えている場合は高値掴みリスクで減点。③ストップ高まで残り1.5%未満の場合は上値余地が乏しいため減点されます。", "【実戦の目安】これらの警告バッジが点灯している時は無理な追撃を控えてください。")
            ]
        },
        {
            "cat_id": "mtf",
            "tab": "⚛️ 2. 3階層MTF（週足10Y×日足2Y×5分足60D）",
            "items": [
                ("第1層：過去10年週足大局（10年POC・10年CAGR・200週MA）", "過去10年間の週足データから『長年の大口資金が最も売買した岩盤価格帯（10年POC）』と『年率成長率（CAGR）』を算出します。株価が10年POCより上にあれば岩盤サポート、下にあれば長期の戻り売り圧力として機能します。", "【良い例】10年大局スコア70点以上・現在値が10年POCより上・10年CAGRプラス。"),
                ("第2層：日足2年中期トレンド（パーフェクトオーダー・MA25/75/200）", "日足チャートで『現在値 > 5日線 > 25日線 > 75日線』かつ25日線が上向きの状態を『強気パーフェクトオーダー(PO)』と判定します。中期のトレンドが明確な銘柄ほど5分足の押し目買いが成功しやすくなります。", "【良い例】強気パーフェクトオーダー点灯、または25日移動平均線の上でMACDヒストグラムがプラス圏。"),
                ("第3層：5分足60日ミクロ需給＆執行タイミング", "上位足（週足・日足）で選んだ銘柄に対し、実際のエントリー・利確・損切りを5分足レベルで精密制御します。朝イチの乱高下を避け、9:05〜13:30の確定足ベースで執行タイミングを測ります。", "【悪い例】日足が25日線・75日線割れの下落トレンドなのに、5分足の小さな反発だけで飛びつくこと。")
            ]
        },
        {
            "cat_id": "chart",
            "tab": "📊 3. チャート＆出来高の重要用語",
            "items": [
                ("VWAP（出来高加重平均価格）＆ VWAP ±1σ / ±2σバンド", "当日市場で取引された『1株あたりの平均約定価格』です。機関投資家も基準にする最重要ラインで、現在値がVWAPより上なら当日の買い方が含み益（強気）、下なら含み損（弱気）を示します。±1σ・±2σは統計的な標準偏差バンドで、+2σ超えは買われすぎ（高値掴み警戒圏）を意味します。", "【実戦の見方】買いは『VWAP〜+1σへの押し目反発』が理想。+2σ超えへの成行飛びつきは厳禁。"),
                ("OR15（オープニングレンジ15分高値・安値）", "寄り付きから最初の15分間（5分足3本分）で形成された高値（OR15 High）と安値（OR15 Low）のレンジです。朝一番の迷いが凝縮された価格帯であり、OR15安値を維持したまま高値をブレイクすると強いトレンドが発生しやすくなります。", "【実戦の見方】OR15安値を明確に割り込んだ銘柄は、その日の買いシナリオを撤回します。"),
                ("PDH（前日高値）・PDL（前日安値）＆ ストップ高上限", "PDHは前営業日の最高値、PDLは前営業日の最安値です。PDHを上抜けると前日の売り方の損切りを巻き込んで上昇が加速しやすく、逆にPDH付近で跳ね返されるとダブルトップになりやすい節目です。日本株は前日終値に基づく東証公式の値幅制限（ストップ高）も自動計算して目標上限をキャップします。", "【実戦の見方】PDHブレイク後のサポレジ転換（PDHが支持線に変わる動き）は絶好の順張りポイントです。"),
                ("LVN（上値真空地帯）と HVN（直上しこり壁）", "過去1年間の価格帯別出来高（Volume Profile）を20段階に分解し、現在値の少し上（+1%〜+6%）に過去の売買が極端に少ない『真空地帯（LVN）』があれば抵抗なく急伸しやすく、逆に過去の出来高が極端に溜まった『しこり壁（HVN）』があれば戻り売りで上値を抑えられやすくなります。", "【実戦の見方】HVNしこり壁が直上にある場合、システムは自動的に利確目標(TP)を壁の少し手前に安全調整します。"),
                ("機関オーダーブロック（OB支持帯）", "当日5分足の中で『平均出来高の2.2倍以上の大商い』かつ『陽線実体比率60%以上』を伴って急伸した起点バーの安値ゾーンです。大口機関投資家の買い注文が集中した痕跡であり、その後価格が押してきた際に強力な下値支持帯として機能します。", "【実戦の見方】チャート上の緑色のOB支持帯付近での下げ止まりは押し目買いの好機です。")
            ]
        },
        {
            "cat_id": "quant",
            "tab": "🏛️ 4. 独自クオンツ指標・英字略語辞典",
            "items": [
                ("WKB統計近似突破率（ボラティリティ突破指数）", "量子力学のトンネル効果（WKB近似）を金融時系列に応用した独自指標です。直近のボラティリティ（σ）と出来高エネルギー（E）が、直上レジスタンス障壁（V0）を突破する確率を0〜99.5%で算出します。", "【数値の目安】80%以上＝上値障壁突破フェーズ / 50〜79%＝エネルギー干渉中 / 50%未満＝抵抗帯下で蓄積中。"),
                ("Kyle-λ（カイル・ラムダ）ステルス吸収率", "マーケットマイクロストラクチャー理論の指標で『出来高が急増しているのに価格が暴落せず吸収されている度合い』を測ります。高いほど大口機関投資家が板を崩さずに静かに玉を集めている（ステルス集積）可能性を示します。", "【数値の目安】68%以上＝大口のステルス吸収傾向あり。"),
                ("BVC-VPIN ＆ CLV資金フローZスコア", "VPINは売買注文の偏り（毒性フロー）を近似計測し、CLV資金フローZスコアはローソク足の終値位置（高値引けか安値引けか）×出来高から『実弾の買い圧力と売り圧力のどちらが優勢か』を-3.0〜+3.0で数値化します。", "【数値の目安】CLVフローZが +0.5以上なら買い優勢、-0.5以下なら売り流出優勢。"),
                ("DFA Hurst指数（ハースト指数）＆ 効率性ER", "Hurst指数は値動きの『トレンド持続性』を測る指標で、0.50を超えるとトレンドが継続しやすく、0.50未満は往復ビンタ（レンジ平均回帰）になりやすい特性を示します。効率性ER（Efficiency Ratio）はノイズに対する直線的な値動きの純度（0〜100%）です。", "【数値の目安】Hurst 0.55以上・効率性ER 30%以上が順張りに適した素直な波形です。"),
                ("WRV（上ヒゲ拒絶圧力 / 下ヒゲ支持力）", "直近12本のローソク足における上ヒゲと下ヒゲの長さを出来高で加重平均した指標です。上ヒゲ圧力が高い（45以上）銘柄は高値圏で強い利益確定売り（寄り天・天井打ち）が出ている危険サインです。", "【数値の目安】買い狙い時は『上ヒゲ圧力 45未満』が合格条件です。"),
                ("時間帯補正RVOL・日次RSα・30分イントラデイRS", "時間帯補正RVOLは『今日の朝〜現在までの累積出来高』を『過去数日の同じ時刻までの平均出来高』と比較した真の出来高倍率です。日次RSαと30分RSは、日経平均やS&P500（または市場中央値）に対してどれだけ強くアウトパフォーム（逆行高）しているかを示します。", "【数値の目安】RVOL 1.2倍以上・30分RS +0.8%以上は資金が集中している主役銘柄の証です。"),
                ("CVaR(99%)・YZ年率Vol・ケリー基準（Kelly %）", "CVaR(99%)は最悪1%の急落ケースにおける平均損失率、YZ年率Volは窓開け（ギャップ）も考慮したヤン・チャン方式の年率ボラティリティです。これらと勝率・ペイオフレシオから数学的に最適な資金配分比率（ケリー基準）と推奨株数を自動算出します。", "【実戦の目安】1トレードの許容リスク（初期設定2%）以内に収まるよう推奨ロットが自動調整されます。")
            ]
        },
        {
            "cat_id": "verify",
            "tab": "📈 5. リークフリー検証テーブルの見方",
            "items": [
                ("完全リークフリー検証とは？", "『前日までのデータだけで売買シグナルを判定し、翌営業日の確定後次バー始値＋不利な1ティックスリッページ＋往復取引コストを差し引いて損益を検証する』厳格なバックテスト方式です。未来のカンニング（ルックアヘッドバイアス）を完全に排除しています。", "【見送り(NO TRADE)】条件を満たさない日は無理にエントリーせず見送りとして記録されます。"),
                ("実質勝率・PF（プロフィットファクター）・SQNスコア", "①実質勝率は建値撤退を除いた勝ちトレード比率。②PF（総利益÷総損失）は1.0以上でプラス収益、1.5以上で優秀、2.0以上で極めて優秀です。③SQN（System Quality Number）はトレードの安定性を示す指標で、1.6以上なら良好、2.5以上なら非常に安定したエッジがあることを示します。", "【注意】直近検証で勝率45%未満またはPF 0.95未満の銘柄は自動でGrade-Cに降格し注意喚起されます。"),
                ("+1.0R 50%分割利確 ＆ 建値ロックルール", "エントリーから損切り幅と同じだけの含み益（+1.0R）に到達した瞬間、保有株数の50%を利確して利益を確保し、残り50%の逆指値（損切りライン）を買値（建値＋コスト）まで引き上げるプロのリスク管理手法です。これにより残りの玉は『負けない状態』で最終目標(TP)を狙えます。", "【SCRATCH（建値撤退）】半分利確後に建値ロックで決済された場合などの微益・微損撤退を指します。")
            ]
        },
        {
            "cat_id": "guide",
            "tab": "🏛️ 6. 5名の監査官＆各機能ガイド",
            "items": [
                ("5名のプロフェッショナル・クオンツ監査官の役割", "🔥 IGNIS（短期モメンタム・OR15初動執行） / 📐 TECHNOS（3階層MTF・LVN/HVN・OB構造解析） / 👁️ SENTINEL（しこり壁・VWAP+2σ過熱・悪材料監査） / 🛡️ AEGIS（リークフリー検証・SQN・ケリー資金管理） / 👑 NEXUS（5条件ゲート最終裁定統括）の5名が多角的に銘柄を監査します。", "【質問投下機能】各銘柄の合議ボックス下部の入力欄から、気になる点や売買相談を直接質問できます。"),
                ("🎟️ 直近IPO・グロース実測分析タブの使い方", "上場前の注目新規承認・メガIPO観測企業（企業名・上場予定日・想定価格・主幹事・初値需給見立て）と、既上場IPO・グロース銘柄の公開価格比・初値比・ロックアップ期間（90日/180日）節目アラートを2階建てで一覧監視できます。", "【実戦のコツ】上場後75〜105日・165〜195日はVC等のロックアップ解除売りに注意が必要です。"),
                ("📋 監視シート（相関リスク診断）＆ 📓 トレード日誌AI監査", "監視シートに2銘柄以上登録すると、直近60日の値動き相関係数とセクター集中度を自動計算し、同一テーマ偏重による同時被弾リスクを警告します。また、各銘柄カードの『🎯 日誌記録』を押すとトレード日誌に保存され、決済後にAEGIS＆SENTINELが100点満点で規律採点を行います。", "【活用法】毎日の振り返りに使うことで、高値掴みや損切り遅れの癖を客観的に改善できます。")
            ]
        }
    ]

    total_hits = 0
    for sec in manual_sections:
        matched_items = []
        for title_s, desc_s, tip_s in sec["items"]:
            if not q_kw or (q_kw in title_s.lower() or q_kw in desc_s.lower() or q_kw in tip_s.lower()):
                matched_items.append((title_s, desc_s, tip_s))
        if not matched_items: continue
        total_hits += len(matched_items)
        with st.expander(f"{sec['tab']} （{len(matched_items)}項目）", expanded=True):
            for title_s, desc_s, tip_s in matched_items:
                st.markdown(
                    f'<div class="manual-card">'
                    f'<div style="font-size:13.5px;font-weight:800;color:#38bdf8;margin-bottom:4px;">{html.escape(title_s)}</div>'
                    f'<div style="font-size:12px;color:#e2e8f0;line-height:1.68;">{html.escape(desc_s)}</div>'
                    f'<div style="font-size:11.5px;color:#6ee7b7;background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.32);border-radius:6px;padding:5px 9px;margin-top:6px;font-weight:700;">{html.escape(tip_s)}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
    if total_hits == 0:
        st.warning(f"「{html.escape(q_kw)}」に一致する用語が見つかりませんでした。別のキーワードでお試しください。")

    if st.button("⬅️ メイン画面に戻る", key="manual_back_bottom", use_container_width=True, type="primary"):
        st.session_state["navigation_page"] = "TOP"
        st.session_state["force_close_sidebar_trig"] = int(time.time() * 1000)
        st.session_state["scroll_top_trig"] = int(time.time() * 1000)
        st.rerun()

with st.sidebar:
    cu = st.session_state.get("authenticated_user", "")
    is_admin_user = (cu == ADMIN_EMAIL.strip().lower())
    if cu:
        role_badge = "👑 MASTER ADMIN" if is_admin_user else "⚛️ MEMBER SESSION ACTIVE"
        st.markdown(f'<div class="sidebar-section-card"><div class="sidebar-header-badge">{role_badge}</div><div style="color:#f8fafc;font-size:12px;font-weight:700;">会員: {html.escape(cu)}</div></div>', unsafe_allow_html=True)
        render_biometric_bridge(mode="register", user_email=cu, bio_token=st.query_params.get("t", ""))
    if st.button("📖 説明書・用語＆アルゴリズム辞典を開く", key="sidebar_open_manual_btn", use_container_width=True, type="primary"):
        st.session_state["navigation_page"] = "MANUAL"
        st.session_state["force_close_sidebar_trig"] = int(time.time() * 1000)
        st.session_state["scroll_top_trig"] = int(time.time() * 1000)
        st.rerun()
    if is_admin_user:
        if st.button("🖥️ 統合管理コントロールセンター起動", use_container_width=True):
            st.session_state["navigation_page"] = "ADMIN"; st.session_state["force_close_sidebar_trig"] = int(time.time() * 1000); st.session_state["scroll_top_trig"] = int(time.time() * 1000); st.rerun()

    with st.expander("🎯 投資スタイル ＆ 3大コア・エンジン選択", expanded=True):
        style_list = ["⚡ デイトレード (前場・後場の波及を狙う)", "🚀 スキャルピング (秒〜分単位のモメンタム)", "📈 スイングトレード (数日〜数週間のトレンド)", "💎 バイ＆ホールド (中長期・IPO分散投資)"]
        cur_style_saved = st.session_state.get("investment_style_choice", style_list[0])
        idx = style_list.index(cur_style_saved) if cur_style_saved in style_list else 0
        investment_style = st.selectbox("トレードスタイル", style_list, index=idx, key="investment_style_choice")
        if investment_style != cur_style_saved: st.session_state["council_threads"] = {}; st.session_state["council_meta"] = {}
        st.caption(f"選択中: **{investment_style.split(' ')[1]}**")
        st.markdown("<hr style='margin:8px 0; border-color:rgba(56,189,248,0.2);'><b>3大コア・エンジン（週足10Y×日足2Y×5分足60D連動）</b>", unsafe_allow_html=True)
        BOOST_MAP = {"⚛️ 量子ボラティリティ＆BBスクイーズ突破 (WKB・位相・Exp-Ratio)": "core_vol", "🏛️ 機関ミクロ需給＆ステルス吸収 (Kyle-λ・Hurst・BVC-VPIN・CLV)": "core_inst", "🔥 初動モメンタム＆ヒゲ拒絶スパイク (時間帯RVOL・Vol-Spike・WRV・報道熱量)": "core_mom"}
        ac_b = {k for l, k in BOOST_MAP.items() if st.checkbox(l, value=st.session_state.get(f"chk_{k}", True), key=f"chk_{k}")}
        if not ac_b: ac_b = {"core_vol", "core_inst", "core_mom"}

    with st.expander("💰 資金管理＆選抜フィルタ", expanded=False):
        total_capital = st.number_input("総投資資金 (円)", min_value=10000, max_value=1000000000, value=int(st.session_state.get("total_capital_val", 1000000)), step=50000, key="total_capital_input")
        risk_tolerance_pct = st.slider("1トレード許容リスク (%)", 0.5, 5.0, float(st.session_state.get("risk_tolerance_val", 2.0)), 0.5, key="risk_tolerance_input")
        survival_cut_pct = st.slider("選抜合格率 (%)", 40, 100, int(st.session_state.get("survival_cut_val", 75)), 5, key="survival_cut_input")

    if cu:
        prefs_payload = {"investment_style": investment_style, "active_boosts": sorted(list(ac_b)), "total_capital": int(total_capital), "risk_tolerance_pct": float(risk_tolerance_pct), "survival_cut_pct": int(survival_cut_pct)}
        prefs_hash = hashlib.md5(json.dumps({"user": cu, "prefs": prefs_payload}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if st.session_state.get("_last_saved_prefs_hash") != prefs_hash:
            save_user_prefs(cu, prefs_payload)
            st.session_state["_last_saved_prefs_hash"] = prefs_hash

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚪 ログアウト", use_container_width=True):
        cu_l, db_l = st.session_state.get("authenticated_user"), load_mem()
        if cu_l in db_l: db_l[cu_l]["last_seen_ts"] = 0; db_set("mem", db_l)
        st.session_state["authenticated_user"] = None; st.query_params.clear(); st.rerun()

if st.session_state.get("navigation_page") == "MANUAL":
    render_user_manual_page()
    st.stop()

if st.session_state.get("navigation_page") == "DEEP_DIVE":
    cu_dd = st.session_state.get("authenticated_user", "").strip().lower()
    db_dd = load_mem()
    u_dd = db_dd.get(cu_dd, {})
    dd_st = u_dd.get("deep_dive_status", "approved" if u_dd.get("deep_dive_allowed") else "none")
    is_dd_ok = (cu_dd == ADMIN_EMAIL.strip().lower()) or (dd_st == "approved")

    if not is_dd_ok:
        st.markdown(
            '<div class="glass-header" style="border-left:4px solid #f59e0b;">'
            '<div class="brand-luxury">YAMASHISHI DEEP DIVE</div>'
            '<div style="color:#fde047;font-weight:800;font-size:14px;margin-top:8px;">🔒 アクセス権限が必要です</div>'
            '<div style="color:#cbd5e1;font-size:12.5px;margin-top:6px;line-height:1.7;">'
            'ディープサーチ（単一銘柄・極限解析ターミナル）を利用するには、管理者からの閲覧権限が必要です。<br>'
            '下のボタンから利用権限を申請してください。</div></div>',
            unsafe_allow_html=True
        )
        if dd_st == "pending":
            st.info("⏳ 現在、管理者の承認審査待ちです。承認されるまでしばらくお待ちください。")
        else:
            if st.button("📩 管理者へディープサーチ利用権限を申請する", use_container_width=True, type="primary"):
                if cu_dd in db_dd:
                    db_dd[cu_dd]["deep_dive_status"] = "pending"
                    db_dd[cu_dd]["deep_dive_applied_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    db_set("mem", db_dd)
                    st.success("✅ 利用権限を申請しました！管理者の承認をお待ちください。")
                    st.rerun()
        if st.button("⬅️ トップ画面に戻る", use_container_width=True):
            st.session_state["navigation_page"] = "TOP"
            st.session_state["scroll_top_trig"] = int(time.time() * 1000)
            st.rerun()
        st.stop()

    import deep_dive
    dd_tgt_fc = str(st.session_state.get("dd_target_code", "NVDA")).strip().upper()
    deep_dive.render_deep_dive_page(
        init_code=dd_tgt_fc,
        init_style=st.session_state.get("dd_target_style", "デイトレード"),
        gemini_api_key=load_gemini_cfg().get("api_key", ""),
        lab_ctx=st.session_state.get("dd_lab_ctx")
    )
    sync_dd_intel_from_session(dd_tgt_fc)
    st.stop()

if st.session_state.get("navigation_page") == "ADMIN" and cu == ADMIN_EMAIL.strip().lower():
    st.markdown("### 👑 統合管理コントロールセンター (MASTER TERMINAL)")
    if st.button("⬅️ メイン画面に戻る", use_container_width=True, type="primary"):
        st.session_state["navigation_page"] = "TOP"; st.session_state["force_close_sidebar_trig"] = int(time.time() * 1000); st.session_state["scroll_top_trig"] = int(time.time() * 1000); st.rerun()
    db_dd_chk = load_mem()
    dd_wait_cnt = sum(1 for u in db_dd_chk.values() if u.get("deep_dive_status") == "pending")
    tab_gemini_sys, tab_users, tab_employment, tab_apply_wait, tab_dd_wait, tab_error_logs = st.tabs([
        "🔑 Gemini API・システム設定",
        "👥 会員情報管理",
        "🧠 クオンツエンジン稼働状態＆データ整合性監査",
        "📩 会員申し込み審査",
        f"🔥 ディープサーチ申請待ち ({dd_wait_cnt})",
        "⚠️ システムエラーログ"
    ])
    with tab_gemini_sys:
        has_sec_secret = bool(_safe_get_env_or_secret("SECRET_KEY"))
        has_sb_secret = bool(_get_supabase_config()[0])
        st.caption(f"🛡️ 永続化ステータス: SECRET_KEY={'🟢 st.secrets固定済' if has_sec_secret else '🟡 ローカル自動生成'} ｜ 外部永続DB(Supabase)={'🟢 永続化ON (kv_store同期中)' if has_sb_secret else '🟡 ローカルSQLite一時保存モード'}")
        st.markdown("#### 🔵 Google Gemini API 暗号化設定")
        gem_cur = load_gemini_cfg(); cur_m, cur_k = gem_cur.get("model", "gemini-3-flash-preview"), gem_cur.get("api_key", "")
        show_plain_key = st.checkbox("👁️ APIキーを平文表示して確認する", value=False, key="chk_show_gem_key")
        in_gem_key = sanitize_api_key(st.text_input("🔑 Google Gemini API Key (AQ.〜 または AIza〜)", value=cur_k, type="default" if show_plain_key else "password", key="admin_gem_key_input"))
        in_gem_mod = st.selectbox("🧠 デフォルト Gemini モデル選択", GEMINI_MODELS, index=GEMINI_MODELS.index(cur_m) if cur_m in GEMINI_MODELS else 0, format_func=lambda m: GEMINI_MODEL_DISPLAY_NAMES.get(m, m), key="admin_gem_mod_select")
        col_g1, col_g2 = st.columns([1, 1])
        if col_g1.button("💾 Gemini API設定を暗号化保存", type="primary", use_container_width=True):
            save_llm_encrypted(in_gem_mod, in_gem_key); st.session_state["council_threads"] = {}; st.session_state["council_meta"] = {}; st.session_state["news_ai_deep_cache"] = {}; st.success("✅ Gemini API設定を暗号化保存しました。")
        if col_g2.button("⚡ Gemini API 接続テスト実行", use_container_width=True):
            with st.spinner("接続テスト実行中..."):
                ok, t_msg = test_single_llm_api(in_gem_mod, in_gem_key)
                if ok: save_llm_encrypted(in_gem_mod, in_gem_key); st.session_state["council_threads"] = {}; st.session_state["council_meta"] = {}; st.session_state["news_ai_deep_cache"] = {}; st.success(f"✅ {t_msg}")
                else: st.error(f"❌ 接続テスト失敗:\n{t_msg}")
        st.markdown("<hr style='margin:14px 0; border-color:rgba(56,189,248,0.25);'><h4>📧 SMTPメール通知サーバー設定</h4>", unsafe_allow_html=True)
        smtp_cur = load_smtp()
        with st.form("admin_smtp_form"):
            sc1, sc2 = st.columns(2)
            s_user, s_pass = sc1.text_input("SMTP ユーザー", value=smtp_cur.get("smtp_user", ADMIN_EMAIL)), sc2.text_input("SMTP パスワード", value=smtp_cur.get("smtp_pass", ""), type="password")
            sc3, sc4 = st.columns([3, 1])
            s_srv, s_port = sc3.text_input("SMTP サーバーホスト", value=smtp_cur.get("smtp_server", "smtp.mail.yahoo.co.jp")), sc4.number_input("ポート番号", min_value=1, max_value=65535, value=int(smtp_cur.get("smtp_port", 465)))
            if st.form_submit_button("💾 SMTPメール設定を保存", use_container_width=True): save_smtp(s_user, s_pass, s_srv, int(s_port)); st.success("✅ SMTP設定を保存しました。")
        st.markdown("<hr style='margin:14px 0; border-color:rgba(56,189,248,0.25);'><h4>⚔️ 市場サバイバル入れ替え戦ログ</h4>", unsafe_allow_html=True)
        surv_logs = db_get("market_survival_logs", [])
        if surv_logs:
            for sl in surv_logs[:20]: st.markdown(f'<div style="background:rgba(15,23,42,0.85);border-left:3px solid #f59e0b;padding:6px 10px;margin-bottom:6px;border-radius:4px;font-size:11.5px;"><span style="color:#94a3b8;font-size:10px;">{html.escape(sl.get("time",""))}</span><br><span style="color:#f8fafc;">{html.escape(sl.get("msg",""))}</span></div>', unsafe_allow_html=True)
        else: st.info("現在記録されている入れ替え戦ログはありません。")
    with tab_users:
        st.markdown("#### 📋 登録済み会員一覧")
        st.caption("🛡️ 端末識別・なりすまし検知の技術仕様:（※HTTPヘッダー環境ハッシュ＆日次HMACトークン照合）によりアクセス整合性を管理しています（ハードウェア生体認証ではありません）。")
        db_m, sec_m = load_mem(), load_sec()
        rows = ""
        for em, u in list(db_m.items())[:200]:
            dd_ok_u = (em == ADMIN_EMAIL.strip().lower()) or (u.get("deep_dive_status") == "approved") or bool(u.get("deep_dive_allowed", False))
            dd_lbl = "<span style='color:#10b981;font-weight:800;'>🔥 許可済</span>" if dd_ok_u else ("<span style='color:#fde047;font-weight:800;'>⏳ 申請中</span>" if u.get("deep_dive_status") == "pending" else "<span style='color:#64748b;'>🔒 未許可</span>")
            rows += f"<tr><td><b>{html.escape(u.get('name',''))}</b></td><td>{html.escape(em)}</td><td style='color:#38bdf8;font-family:monospace;'>{html.escape(u.get('passcode','-'))}</td><td>{dd_lbl}</td><td style='color:#fde047;font-family:monospace;'>{html.escape(u.get('fp','-'))}</td><td>{html.escape(u.get('applied_at','-'))}</td><td><span style='color:{'#10b981' if u.get('status')=='approved' else ('#ef4444' if u.get('status')=='banned' else '#f59e0b')}'><b>{html.escape(u.get('status',''))}</b></span></td></tr>"
        st.markdown(f'<div class="admin-table-container"><table class="admin-table"><thead><tr><th>お名前</th><th>メールアドレス</th><th>専用パスコード</th><th>DD権限</th><th>環境ハッシュ(FP)</th><th>登録日</th><th>状態</th></tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)
        spoof_logs = sec_m.get("spoof_logs", [])
        if spoof_logs:
            st.markdown("##### 🚨 なりすまし検知・BAN遮断ログ（※HTTPヘッダー環境ハッシュ＆日次HMACトークン照合）")
            s_rows = "".join([f"<tr><td>{html.escape(sl.get('time','-'))}</td><td>{html.escape(sl.get('action','-'))}</td><td>{html.escape(sl.get('input_email','-'))}</td><td style='font-family:monospace;color:#fde047;'>{html.escape(sl.get('fp','-'))}</td><td>{html.escape(sl.get('reason','-'))}</td></tr>" for sl in spoof_logs[:30]])
            st.markdown(f'<div class="admin-table-container"><table class="admin-table"><thead><tr><th>日時</th><th>検知種別（※HTTPヘッダー環境ハッシュ＆日次HMACトークン照合）</th><th>入力メール</th><th>環境ハッシュ(FP)</th><th>詳細理由</th></tr></thead><tbody>{s_rows}</tbody></table></div>', unsafe_allow_html=True)
        target_em = st.selectbox("操作対象会員を選択", list(db_m.keys()))
        if target_em and target_em != ADMIN_EMAIL.strip().lower():
            u_status = db_m[target_em].get("status", ""); b1, b2, b3, b4 = st.columns(4)
            if u_status == "approved":
                if b1.button("⏸️ 一時停止", use_container_width=True): db_m[target_em]["status"] = "suspended"; db_set("mem", db_m); st.rerun()
            elif b1.button("▶️ 利用再開", use_container_width=True): db_m[target_em]["status"] = "approved"; db_set("mem", db_m); st.rerun()
            if b2.button("🚫 永久BAN", use_container_width=True):
                db_m[target_em]["status"] = "banned"; now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                for f_k in ("fp", "raw_hfp"):
                    val = db_m[target_em].get(f_k)
                    if val and val != "-": sec_m.setdefault("banned_fps", {})[val] = {"email": target_em, "banned_at": now_s, "reason": "管理者強制永久BAN（※HTTPヘッダー環境ハッシュ＆日次HMACトークン照合）"}
                sec_m.setdefault("banned_emails", {})[target_em] = {"banned_at": now_s, "orig": target_em}; db_set("mem", db_m); db_set("sec", sec_m); st.rerun()
            if b3.button("🗑️ 完全削除", use_container_width=True): del db_m[target_em]; db_set("mem", db_m); st.rerun()
            dd_is_ok = (db_m[target_em].get("deep_dive_status") == "approved") or bool(db_m[target_em].get("deep_dive_allowed", False))
            if b4.button("🔥 DD取消" if dd_is_ok else "🔓 DD許可", use_container_width=True):
                db_m[target_em]["deep_dive_status"] = "none" if dd_is_ok else "approved"
                db_m[target_em]["deep_dive_allowed"] = not dd_is_ok
                db_set("mem", db_m); st.rerun()
    with tab_employment:
        st.markdown("#### 🧠 クオンツエンジン稼働状態＆データ整合性監査")
        audit_m = _compute_real_audit_metrics(); h_col = "#10b981" if audit_m["health_score"] >= 90 else ("#fde047" if audit_m["health_score"] >= 75 else "#ef4444")
        gem_stat_txt = "🟢 Gemini API 接続済 (AIマルチペルソナ合議稼働中)" if audit_m["gem_ok"] else "🟡 Gemini API 未接続 (統計ルールベース精密推論モード稼働中)"
        st.markdown(f'<div style="background:rgba(16,185,129,0.12);border:1px solid #38bdf8;padding:10px 14px;border-radius:8px;font-size:12px;margin-bottom:12px;line-height:1.7;">📊 <b>システム整合性スコア:</b> <b style="color:{h_col};">{audit_m["health_score"]}点</b> ｜ <b>LLM推論状態:</b> {gem_stat_txt}<br>📁 <b>リークフリー検証台帳レコード数:</b> <b>{audit_m["ledger_entries"]}銘柄・スタイル</b> ｜ <b>例外ログ件数:</b> <b>{audit_m["err_cnt"]}件</b> ｜ <b>対話品質重複ペナルティ:</b> <b>{audit_m["sim_pen"]}pt</b></div>', unsafe_allow_html=True)
        st.markdown("##### 🏛️ 5名固定プロフェッショナル・クオンツ監査官プロファイル")
        for ak, av in DEFAULT_AGENTS.items():
            st.markdown(f'<div style="background:rgba(15,23,42,0.88);border:1px solid rgba(56,189,248,0.3);border-left:4px solid #38bdf8;border-radius:6px;padding:8px 12px;margin-bottom:7px;font-size:12px;"><div style="display:flex;justify-content:space-between;align-items:center;"><span style="font-weight:800;color:#f8fafc;font-size:13px;">{html.escape(av["icon"])} {html.escape(av["name"])} <span style="color:#38bdf8;font-size:11px;">[{html.escape(av["role_title"])}]</span></span><span style="background:rgba(16,185,129,0.2);border:1px solid #10b981;color:#6ee7b7;padding:2px 8px;border-radius:4px;font-size:10.5px;font-weight:800;">🟢 常時稼働中</span></div><div style="color:#cbd5e1;margin-top:4px;font-size:11.5px;"><b>専門監査領域:</b> {html.escape(av["good"])}</div><div style="color:#94a3b8;margin-top:2px;font-size:11px;"><b>監査基準・制約:</b> {html.escape(av["bad"])}</div></div>', unsafe_allow_html=True)
    with tab_apply_wait:
        st.markdown("#### 📩 新規会員登録 審査待ちリスト")
        db_all = load_mem(); pending = {em: u for em, u in db_all.items() if u.get("status") == "pending"}
        if pending:
            for pem, pu in list(pending.items()):
                st.markdown(f'<div style="background:rgba(15,23,42,0.85);border:1px solid rgba(56,189,248,0.3);border-radius:8px;padding:10px 14px;margin-bottom:8px;"><b>{html.escape(pu.get("name","未入力"))}</b> ({html.escape(pem)})</div>', unsafe_allow_html=True)
                cb1, cb2 = st.columns([1, 1])
                if cb1.button(f"✅ 承認 ({pu.get('name','')})", key=f"appr_{pem}", use_container_width=True):
                    db_all[pem]["status"], db_all[pem]["approved_at"] = "approved", datetime.now().strftime("%Y-%m-%d %H:%M"); db_set("mem", db_all)
                    send_mail(pem, "【YAMASHISHI LAB】会員登録承認", f"{pu.get('name','')} 様\n専用アクセスコードは【 {db_all[pem]['passcode']} 】です。"); st.rerun()
                if cb2.button(f"🚫 却下 ({pu.get('name','')})", key=f"rej_{pem}", use_container_width=True): del db_all[pem]; db_set("mem", db_all); st.rerun()
        else: st.info("承認待ちの新規申請はありません。")
    with tab_dd_wait:
        st.markdown("#### 🔥 ディープサーチ（DEEP DIVE）利用権限 申請待ちリスト")
        db_all = load_mem()
        dd_pending = {em: u for em, u in db_all.items() if u.get("deep_dive_status") == "pending"}
        if dd_pending:
            for pem, pu in list(dd_pending.items()):
                st.markdown(
                    f'<div style="background:rgba(15,23,42,0.85);border:1px solid rgba(245,158,11,0.4);border-left:4px solid #f59e0b;border-radius:8px;padding:10px 14px;margin-bottom:8px;">'
                    f'<b>{html.escape(pu.get("name","未入力"))}</b> ({html.escape(pem)}) '
                    f'<span style="color:#94a3b8;font-size:11px;margin-left:8px;">申請日時: {html.escape(pu.get("deep_dive_applied_at","-"))}</span></div>',
                    unsafe_allow_html=True
                )
                dc1, dc2 = st.columns([1, 1])
                if dc1.button(f"✅ 許可する ({pu.get('name','')})", key=f"dd_ok_{pem}", use_container_width=True, type="primary"):
                    db_all[pem]["deep_dive_status"] = "approved"
                    db_all[pem]["deep_dive_allowed"] = True
                    db_set("mem", db_all); st.rerun()
                if dc2.button(f"🚫 却下する ({pu.get('name','')})", key=f"dd_ng_{pem}", use_container_width=True):
                    db_all[pem]["deep_dive_status"] = "none"
                    db_all[pem]["deep_dive_allowed"] = False
                    db_set("mem", db_all); st.rerun()
        else:
            st.info("現在、ディープサーチ利用権限の申請待ちはありません。")
    with tab_error_logs:
        st.markdown("#### ⚠️ システムエラーログ管理")
        err_list = get_system_error_logs()
        if err_list:
            col_down, col_clear = st.columns([2, 2])
            col_down.download_button("📥 JSONエクスポート", data=json.dumps(err_list[:100], ensure_ascii=False), file_name="yamashishi_error_logs.json", mime="application/json", use_container_width=True)
            if col_clear.button("🗑️ 全消去", use_container_width=True): clear_system_error_logs(); st.rerun()
            rows_err = "".join([f"<tr><td>{html.escape(e.get('time','-'))}</td><td>{html.escape(e.get('module','-'))}</td><td>{html.escape(e.get('error_type','-'))}</td><td>{html.escape(str(e.get('message','-'))[:60])}</td></tr>" for e in err_list[:20]])
            st.markdown(f'<div class="admin-table-container"><table class="admin-table"><thead><tr><th>日時</th><th>モジュール</th><th>例外</th><th>メッセージ</th></tr></thead><tbody>{rows_err}</tbody></table></div>', unsafe_allow_html=True)
        else: st.success("🎉 エラーはありません。")
    st.stop()
def _parse_news_age_hours(pub_str: str) -> float:
    if not pub_str: return 12.0
    try:
        dt = parsedate_to_datetime(pub_str.strip())
        if dt is not None:
            if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
            return max(0.0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 3600.0)
    except Exception: pass
    return 12.0

@st.cache_data(ttl=300)
def search_single_query(q: str, max_r: int, trusted_only: bool = False, max_age_hours: float = 36.0) -> list:
    res = []
    effective_q = f"{q} (site:kabutan.jp OR site:jp.reuters.com OR site:bloomberg.co.jp OR site:minkabu.jp OR site:prtimes.jp)" if trusted_only else q
    try:
        req = urllib.request.Request(f"https://news.google.com/rss/search?q={urllib.parse.quote(effective_q)}&hl=ja&gl=JP&ceid=JP:ja", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=2.5, context=ssl.create_default_context()) as r:
            for it in ET.fromstring(r.read()).findall("./channel/item")[:max_r * 3]:
                t = re.sub(r"\s*-\s*[^-]+$", "", re.sub(r"<[^>]+>", "", it.findtext("title") or "").strip())
                d = re.sub(r"<[^>]+>", "", it.findtext("description") or "").strip()
                pub = (it.findtext("pubDate") or "").strip()
                if _parse_news_age_hours(pub) > float(max_age_hours): continue
                if t:
                    res.append(f"{t} ({d[:80]}...) [{pub[:16]}]")
                    if len(res) >= max_r: break
    except Exception as e: record_system_error("search_single_query", e, f"Query: {effective_q}")
    return res

def _infer_genre_from_text(txt: str) -> str:
    tu = (txt or "").upper()
    if any(k in tu for k in ["半導体", "ウエハ", "EUV", "HBM", "GPU", "チップ", "ファウンドリ", "検査装置", "NVIDIA", "NVDA", "TSMC", "AVGO", "AMD"]): return "半導体・前工程・検査"
    if any(k in tu for k in ["防衛", "自衛隊", "重工", "国策", "AI", "人工知能", "クラウド", "サイバー", "銀行", "商社"]): return "AI・防衛・国策"
    if any(k in tu for k in ["電力", "原発", "送電", "電線", "光ファイバー", "データセンター", "液冷", "原子炉"]): return "AI電力・超電導・電線"
    if any(k in tu for k in ["宇宙", "衛星", "ロケット", "月面", "量子", "ドローン", "ロボット"]): return "宇宙・量子・次世代テック"
    return "小型急騰・仕手・モメンタム"

def _clean_corp_name(raw_name: str) -> str:
    s = html.unescape(str(raw_name or "")).strip()
    s = re.sub(r"^(?:株式会社|\(株\)|（株）)|(?:株式会社|\(株\)|（株）)$", "", s).strip()
    return re.sub(r"\s+", " ", s)

@st.cache_data(ttl=86400)
def _fetch_remote_ticker_name(full_code: str) -> tuple:
    fc = str(full_code or "").strip().upper()
    is_jp = fc.endswith(".T"); code4 = fc.replace(".T", "")
    resolved_name, sector_hint = "", ""
    ctx = ssl.create_default_context()
    if is_jp:
        urls = [(f"https://finance.yahoo.co.jp/quote/{code4}.T", [r"^([^(\（\【\-｜|]+?)(?:\s*[\(\（\【]|株価)"]), (f"https://kabutan.jp/stock/?code={code4}", [r"【([^】]+)】", r"^([^(\（\【\-｜|]+?)(?:\s*[\(\（\【]|基本情報)"])]
        for u, pats in urls:
            try:
                req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                with urllib.request.urlopen(req, timeout=2.5, context=ctx) as resp:
                    page_txt = resp.read(32768).decode("utf-8", errors="ignore")
                    m_title = re.search(r"<title[^>]*>(.*?)</title>", page_txt, re.IGNORECASE | re.DOTALL)
                    if m_title:
                        t_clean = re.sub(r"\s+", " ", html.unescape(m_title.group(1))).strip()
                        for pat in pats:
                            m_nm = re.search(pat, t_clean)
                            if m_nm:
                                cand = _clean_corp_name(m_nm.group(1))
                                if cand and cand != code4 and not cand.isdigit() and len(cand) >= 2:
                                    resolved_name = cand; sector_hint = t_clean; break
                    if resolved_name: break
            except Exception: continue
        if not resolved_name:
            for h in search_single_query(f"{code4} 株価", 3, False):
                m_h = re.search(rf"([^\s「」『』【】\(\)（）]{{2,18}})\s*[\(（<＜\[]?\s*{re.escape(code4)}", h)
                if m_h:
                    cand = _clean_corp_name(m_h.group(1))
                    if cand and cand != code4 and not cand.isdigit():
                        resolved_name = cand; sector_hint = h; break
    if not resolved_name:
        try:
            inf = yf.Ticker(fc).info or {}
            cand = _clean_corp_name(inf.get("longName") or inf.get("shortName") or "")
            if cand and cand.upper() != code4: resolved_name = cand
            sector_hint = f"{sector_hint} {inf.get('sector', '')} {inf.get('industry', '')}"
        except Exception: pass
    return resolved_name, sector_hint

def resolve_ticker_metadata(full_code: str) -> dict:
    fc = str(full_code or "").strip().upper()
    if re.match(r"^[0-9]{3}[0-9A-Z]$", fc): fc = f"{fc}.T"
    code4 = fc.replace(".T", "")
    cached = STOCK_METADATA_CACHE.get(fc)
    if cached and cached.get("name") and cached["name"] not in (code4, fc, f"東証{code4}"): return cached
    resolved_name, sector_hint = _fetch_remote_ticker_name(fc)
    final_name = resolved_name if resolved_name else (f"東証{code4}" if fc.endswith(".T") else code4)
    inferred_genre = _infer_genre_from_text(f"{final_name} {sector_hint}")
    meta = {"name": final_name, "genre": inferred_genre, "theme": (cached.get("theme") if cached and cached.get("theme") else f"{inferred_genre}・個別銘柄定量スキャン")}
    STOCK_METADATA_CACHE[fc] = meta
    return meta

def _extract_tickers_from_text(txt: str) -> list:
    found, seen_local = [], set()
    for rc in re.findall(r"(?<![0-9A-Za-z])([1-9][0-9]{2}[0-9A-Z])(?![0-9A-Za-z])", txt or ""):
        if re.match(r"^202[0-9]$", rc): continue
        fc = f"{rc}.T"
        if fc in seen_local or fc in DELISTED_OR_INVALID_CODES: continue
        seen_local.add(fc)
        if fc in EXTENDED_SEED_DICT:
            inf = EXTENDED_SEED_DICT[fc]; found.append((fc, inf["name"], inf["genre"], inf["theme"]))
        else:
            m_name = re.search(rf"([^\s「」『』【】\(\)（）]{{2,14}})\s*[\(（<＜]?\s*{re.escape(rc)}", txt or "")
            est_name = _clean_corp_name(m_name.group(1)) if m_name else ""
            if not est_name or est_name == rc or est_name.isdigit():
                meta = resolve_ticker_metadata(fc)
                est_name, est_genre, est_theme = meta["name"], meta["genre"], meta["theme"]
            else:
                est_genre, est_theme = _infer_genre_from_text(txt), "市況急動意・ニュース自動発掘銘柄"
                STOCK_METADATA_CACHE[fc] = {"name": est_name, "genre": est_genre, "theme": est_theme}
            found.append((fc, est_name, est_genre, est_theme))
    for fc, inf in EXTENDED_SEED_DICT.items():
        if fc in seen_local or fc in DELISTED_OR_INVALID_CODES: continue
        short_nm = inf["name"].replace("HD", "").replace("グループ", "").replace("フィナンシャルG", "")
        if len(short_nm) >= 2 and short_nm.upper() in (txt or "").upper():
            seen_local.add(fc); found.append((fc, inf["name"], inf["genre"], inf["theme"]))
    return found

@st.cache_data(ttl=240)
def discover_challenger_tickers(existing_codes_tuple: tuple) -> list:
    challengers, seen, rss_snippets = [], set(existing_codes_tuple) | DELISTED_OR_INVALID_CODES, []
    queries = [('("ストップ高" OR "上方修正" OR "急騰" OR "最高益" OR "自社株買い" OR "新規上場") 株', True), ('("ストップ高" OR "上方修正" OR "急騰" OR "最高益" OR "自社株買い" OR "新規上場") 株', False), ('("急伸" OR "連騰" OR "買い気配" OR "好決算" OR "テーマ株") 東証', False)]
    with ThreadPoolExecutor(max_workers=3) as ex:
        for f in as_completed([ex.submit(search_single_query, q, 8, t_flag) for q, t_flag in queries]):
            try: rss_snippets.extend(f.result())
            except Exception as e: record_system_error("discover_challenger_tickers:rss", e)
    for snip in rss_snippets:
        for item in _extract_tickers_from_text(snip):
            if item[0] not in seen:
                seen.add(item[0]); meta = resolve_ticker_metadata(item[0])
                challengers.append((item[0], meta["name"], meta["genre"], meta["theme"]))
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
                        df_c = (raw_5d[c] if (len(cand_codes) > 1 and c in raw_5d) else raw_5d).dropna(subset=["Close", "Volume"])
                        if len(df_c) >= 2:
                            cl, vo = df_c["Close"].values.astype(float), df_c["Volume"].values.astype(float)
                            rvol = float(vo[-1]) / max(float(np.mean(vo[:-1])) if len(vo) > 1 else float(vo[-1]), 1.0)
                            abs_chg = abs((float(cl[-1]) - float(cl[-2])) / max(float(cl[-2]), 1e-4)) * 100.0
                            scored_cands.append((rvol * 10.0 + abs_chg * 3.0, (c, n, g, t)))
                    except Exception: continue
                scored_cands.sort(key=lambda x: x[0], reverse=True)
                for _, item in scored_cands[:needed]: seen.add(item[0]); challengers.append(item)
            except Exception as e: record_system_error("discover_challenger_tickers:yf_5d", e)
    for c, n, g, t in challengers: STOCK_METADATA_CACHE[c] = {"name": n, "genre": g, "theme": t}
    return challengers[:14]

def analyze_news_impact_and_links(title: str, cat: str, summary_text: str = "") -> dict:
    tu = (title + " " + summary_text).upper()
    clean_sum = re.sub(r"&nbsp;|&#\d+;", " ", re.sub(r"<[^>]+>", "", summary_text or "")).strip()
    dynamic_codes = list(dict.fromkeys([it[0] for it in _extract_tickers_from_text(f"{title} {clean_sum}")]))
    if any(w in tu for w in ["半導体", "エヌビディア", "NVDA", "TSMC", "AVGO", "AMD", "AI", "アドバンテスト", "東エレク", "レーザー", "光配線", "データセンター", "CHIP", "SEMICONDUCTOR"]):
        base_codes, sf = ["6857.T", "8035.T", "6146.T", "6920.T", "5803.T", "NVDA"], "AI半導体・先端パッケージング・光電融合インフラ"
        bg_body = f"【報道ヘッドラインの要点】\n{clean_sum if len(clean_sum) > 25 else title}\n\n【やさしいテーマ解説】\n世界のAI開発競争に伴い、データセンター向けの最新チップや製造・検査装置の需要が注目されています。"
        mech = "【資金が動く仕組み】\n①【海外市場との連動】米国半導体株の動きに日本の関連株が反応しやすい傾向があります。\n②【主役から周辺への波及】まず大型の主役株が買われ、その後に電線や部材など周辺銘柄へ買いが広がりやすい流れです。"
        timeline = "・朝イチ(9:00〜9:15): ニュースを見た短期の買いが集中し乱高下しやすい時間帯（飛びつき注意・OR15レンジ形成）。\n・前場〜後場(9:15〜13:30): 一度価格が落ち着き、平均約定価格(VWAP)や移動平均線で下げ止まったのを確認してから狙います。\n・大引け前(13:30〜): 利益が出ている半分を確定し、残りは損をしない位置に保険をかけて持ち越すか手仕舞いします。"
        risk_note = "ニュースを見て朝一番の高値に飛びつくと「高値掴み」になりやすいため厳禁です。OR15分安値や平均価格を割り込んで下落が続く場合は無理に買わず見送ります。"
        action_guide = "① 【どこで買う？】朝イチの急騰には飛びつかず、9:15〜13:30の間に価格が落ち着いてOR15分安値維持・平均約定価格(VWAP)や移動平均線付近で下げ止まり、再び上昇し始めたタイミングで買います（高値掴み防止）。\n② 【どこで利確・損切り？】買ったらすぐに損切りライン（逆指値）を予約し、利益が損切り幅と同じだけ伸びたらまず半分を利確して心の余裕を作りましょう。"
    elif any(w in tu for w in ["防衛", "三菱重", "川崎重", "IHI", "宇宙", "衛星", "地政学", "ミサイル", "ドローン", "安保"]):
        base_codes, sf = ["7011.T", "7012.T", "7013.T", "5595.T", "186A.T", "PLTR"], "防衛国策・宇宙衛星コンステレーション・重工インフラ"
        bg_body = f"【報道ヘッドラインの要点】\n{clean_sum if len(clean_sum) > 25 else title}\n\n【やさしいテーマ解説】\n国の防衛予算拡大や宇宙・衛星開発など、複数年にわたる国策プロジェクトの恩恵を受けるテーマです。"
        mech = "【資金が動く仕組み】\n①【独自材料の強さ】日経平均全体が弱い日でも、防衛・宇宙関連の報道が出ると独自の買いが集まりやすい特徴があります。\n②【大手から中小型への波及】まず重工大手が買われ、その後小型の宇宙・ドローン関連株へ資金が向かいやすくなります。"
        timeline = "・朝イチ(9:05〜9:45): 重工大手株に大口の買いが入りトレンドが生まれます。\n・中盤(9:45〜13:30): 押し目を作ったタイミングで中小型関連株へ買いが波及します。\n・終盤(13:30〜14:30): 半分利確と逆指値引き上げで利益を守ります。"
        risk_note = "地政学リスクの緩和や計画延期のニュースが出た場合は、一気に利益確定売りが出やすいため損切りラインを厳守してください。"
        action_guide = "① 【どこで買う？】寄付き直後の成行買いは避け、9:15〜13:30にOR15分安値を維持しつつ平均約定価格(VWAP)付近まで引きつけて反発を確認してから注文を出します。\n② 【どこで利確・損切り？】エントリーと同時に逆指値（損切り予約）を入れ、目標の半分に到達したら半分利確＋残りは買値に逆指値を移して安全に伸ばします。"
    else:
        base_codes, sf = ["9984.T", "6857.T", "5803.T", "7011.T", "5253.T", "3350.T"], "上方修正サプライズ・国策AI・短期モメンタム集中銘柄"
        bg_body = f"【報道ヘッドラインの要点】\n{clean_sum if len(clean_sum) > 25 else title}\n\n【やさしいテーマ解説】\n業績の上方修正や増配、自社株買い、大型提携などの好材料が出ると、売り方の買い戻しと新規の買いが重なり上昇トレンドが生まれやすくなります。"
        mech = "【資金が動く仕組み】\n①【買い戻しの連鎖】株価が上がると空売りしていた投資家が慌てて買い戻すため、さらに株価が押し上げられます。\n②【押し目買いの攻防】一度上がった後に少し下がったところ（押し目）で買い支えが入るかを確認するのがポイントです。"
        timeline = "・前場〜後場(9:15〜13:30): 押し目で下げ止まり、直前の高値を抜けたタイミングでエントリーします。\n・利益確定フェーズ: 損切り幅と同じ利益が出たら半分を利確します。\n・大引け前(13:30〜): 残りの半分も利益を守る位置に逆指値を置いて安全に管理します。"
        risk_note = "材料が出尽くして高値から急落する「寄り天」に注意し、決めた損切り価格を下回ったら迷わず撤退して塩漬けを防ぎます。"
        action_guide = "① 【どこで買う？】高値掴みを防ぐため、朝一番の飛びつき買いは控え、価格が一度落ち着いてOR15分安値維持・平均価格付近で反発したのを確認してから買います。\n② 【どこで利確・損切り？】買った瞬間に逆指値（損切り保険）をセットし、利益が伸びたら最初に半分だけ利確して心の余裕を確保します。"
    sector_ref_codes = [c for c in base_codes if c not in dynamic_codes]
    return {"sector_focus": sf, "news_body": bg_body, "mechanism": mech, "timeline": timeline, "risk_note": risk_note, "extracted_codes": dynamic_codes, "sector_ref_codes": sector_ref_codes, "related_codes": list(dict.fromkeys(dynamic_codes + base_codes))[:8], "action_guide": action_guide}

def generate_ai_news_deep_report(news_item: dict, style_name: str) -> str:
    ck = f"{news_item.get('id', '')}_{style_name}"; cache = st.session_state.setdefault("news_ai_deep_cache", {})
    if ck in cache: return cache[ck]
    if not load_gemini_cfg().get("api_key"): return ""
    sys_p = "あなたは初心者にもわかりやすく丁寧に教える投資ストラテジストです。速報ニュースについて『ニュースの背景』『注目銘柄への影響』『失敗しない買い方・利確・損切りの注意点』を400〜600文字の優しい日本語で出力してください（難解な専門略語は使わないこと）。"
    res, _ = call_real_llm_api(sys_p, f"見出し: {news_item.get('title','')}\n概要: {re.sub(r'<[^>]+>', '', news_item.get('summary','')).strip()}\nスタイル: {style_name}", expect_json=False)
    if res and len(res.strip()) > 30: cache[ck] = re.sub(r'```[a-zA-Z]*|```', '', res).strip(); return cache[ck]
    return ""

NEWS_IMPACT_KEYWORDS = ["ストップ高", "上方修正", "最高益", "増配", "自社株買い", "TOB", "提携", "急騰", "防衛", "半導体", "NVIDIA", "AI", "SURGE", "BEAT"]
TRUSTED_PRIMARY_MEDIA = ["REUTERS", "ロイター", "BLOOMBERG", "ブルームバーグ", "株探", "KABUTAN", "PR TIMES", "日経", "NIKKEI", "みんかぶ", "MINKABU", "YAHOO FINANCE"]

def _compute_news_impact_score(title: str, desc: str, source: str = "", age_hours: float = 12.0, stream_tag: str = "") -> int:
    kw_hits = sum(1 for kw in NEWS_IMPACT_KEYWORDS if kw.upper() in f"{title} {desc}".upper())
    src_up = (source or "").upper()
    trust_bonus = 13 if any(tm in src_up for tm in TRUSTED_PRIMARY_MEDIA) else (8 if stream_tag == "trusted" else 0)
    fresh_adj = 6 if age_hours <= 6.0 else (2 if age_hours <= 18.0 else (-5 if age_hours <= 36.0 else -20))
    return int(np.clip(66 + kw_hits * 4 + trust_bonus + fresh_adj, 45, 99))

def fetch_single_news_rss(cat: str, q: str, stream_tag: str = "broad") -> list:
    out = []
    try:
        url = "https://feeds.finance.yahoo.com/rss/2.0/headline?s=NVDA,TSM,AVGO,AMD&region=US&lang=en-US" if stream_tag == "us_semi" else f"https://news.google.com/rss/search?q={urllib.parse.quote(f'{q} (site:kabutan.jp OR site:jp.reuters.com OR site:bloomberg.co.jp OR site:minkabu.jp OR site:prtimes.jp)' if stream_tag == 'trusted' else q)}&hl=ja&gl=JP&ceid=JP:ja"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=2.0, context=ssl.create_default_context()) as res:
            for it in ET.fromstring(res.read()).findall("./channel/item")[:6]:
                raw_title = (it.findtext("title") or "").strip()
                t = re.sub(r"\s*-\s*[^-]+$", "", raw_title) if stream_tag != "us_semi" else raw_title
                desc = re.sub(r"<[^>]+>", "", (it.findtext("description") or "").strip())
                pub_raw = (it.findtext("pubDate") or "").strip(); age_h = _parse_news_age_hours(pub_raw)
                if age_h > 36.0: continue
                src_txt = (it.findtext("source") or ("Yahoo Finance US" if stream_tag == "us_semi" else "Market Wire")).strip()
                if t:
                    extracted = [x[0] for x in _extract_tickers_from_text(f"{t} {desc}")]
                    out.append({"id": hashlib.md5(f"{stream_tag}_{t}".encode()).hexdigest()[:8], "cat": cat, "title": t, "summary": desc, "link": it.findtext("link") or "https://jp.reuters.com/", "source": src_txt, "stream_tag": stream_tag, "age_hours": round(age_h, 1), "pub_date": (pub_raw or datetime.now().strftime("%Y-%m-%d %H:%M"))[:25], "extracted_codes": extracted, "impact_score": _compute_news_impact_score(t, desc, src_txt, age_h, stream_tag)})
    except Exception as e: record_system_error(f"fetch_single_news_rss:{stream_tag}", e, f"Query: {q}")
    return out

@st.cache_data(ttl=240)
def fetch_global_impact_news() -> list:
    out_all, seen = [], set()
    tasks = [("高信頼一次報道・半導体AI", "半導体 OR エヌビディア OR TSMC OR アドバンテスト 株価", "trusted"), ("高信頼一次報道・急騰国策", "ストップ高 OR 上方修正 OR 三菱重工 OR 防衛 株", "trusted"), ("広域マーケット速報・AI半導体", "半導体 OR エヌビディア OR TSMC OR アドバンテスト 株価", "broad"), ("広域マーケット速報・防衛国策", "ストップ高 OR 上方修正 OR 三菱重工 OR 防衛 株", "broad"), ("米国半導体・マクロ速報(US)", "NVDA TSM AVGO AMD", "us_semi")]
    with ThreadPoolExecutor(max_workers=5) as ex:
        for f in as_completed([ex.submit(fetch_single_news_rss, cat, q, stg) for cat, q, stg in tasks]):
            try:
                for item in f.result():
                    norm_title = re.sub(r"\s+", "", item["title"])
                    if norm_title not in seen: out_all.append(item); seen.add(norm_title)
            except Exception as e: record_system_error("fetch_global_impact_news:futures", e)
    ticker_source_streams = {}
    for it in out_all:
        for tc in it.get("extracted_codes", []): ticker_source_streams.setdefault(tc, set()).add(it.get("stream_tag", "broad"))
    for it in out_all:
        cross_streams = set()
        for tc in it.get("extracted_codes", []): cross_streams |= ticker_source_streams.get(tc, set())
        if len(cross_streams) >= 2: it["impact_score"] = int(np.clip(it.get("impact_score", 70) + (len(cross_streams) - 1) * 7, 50, 99)); it["cross_verified"] = True
        else: it["cross_verified"] = False
        it["detail"] = analyze_news_impact_and_links(it["title"], it["cat"], it.get("summary", ""))
    out_all.sort(key=lambda x: x.get("impact_score", 70), reverse=True)
    return out_all[:6]

all_impact_news = fetch_global_impact_news()

def _extract_ipo_schedule_details(text_blob: str, is_unlisted_rumor: bool = False) -> dict:
    txt = str(text_blob or "")
    listing_date_disp = "上場準備・承認観測中（JPX公式参照）" if is_unlisted_rumor else "直近承認・スケジュール確認中（JPX公式参照）"
    m_date = re.search(r"(?:上場日|上場予定|新規上場)[\s:：]*([0-9]{4}[/\-年][0-9]{1,2}[/\-月][0-9]{1,2}日?|[0-9]{1,2}月[0-9]{1,2}日)", txt)
    if m_date:
        raw_d = m_date.group(1)
        m_ymd = re.match(r"([0-9]{4})[/\-年]([0-9]{1,2})[/\-月]([0-9]{1,2})", raw_d)
        listing_date_disp = f"{int(m_ymd.group(1)):04d}-{int(m_ymd.group(2)):02d}-{int(m_ymd.group(3)):02d}" if m_ymd else raw_d
    elif not is_unlisted_rumor:
        m_md_any = re.search(r"([0-9]{1,2}月[0-9]{1,2}日)(?:に)?(?:東証|新規上場|上場)", txt)
        if m_md_any: listing_date_disp = m_md_any.group(1)
    m_price = re.search(r"(?:公開価格|公募価格|想定価格|仮条件)[\s:：]*([0-9,]+(?:\s*[〜~\-]\s*[0-9,]+)?\s*円)", txt)
    m_bb = re.search(r"(?:ブックビルディング|BB期間|需要申告)[\s:：]*([0-9]{1,2}月[0-9]{1,2}日\s*[〜~\-]\s*[0-9]{1,2}月[0-9]{1,2}日|[0-9]{1,2}/[0-9]{1,2}\s*[〜~\-]\s*[0-9]{1,2}/[0-9]{1,2})", txt)
    m_uw = re.search(r"(?:主幹事)[\s:：]*([^\s、。,\(\)（）]{2,20}(?:証券|モルガン|サックス))", txt)
    m_mkt = re.search(r"(東証プライム|東証スタンダード|東証グロース|NASDAQ|NYSE)", txt)
    return {
        "listing_date_disp": listing_date_disp,
        "offer_info": m_price.group(1).strip() if m_price else "未公表 / 観測中",
        "bb_info": m_bb.group(1).strip() if m_bb else "スケジュール確認中",
        "lead_underwriter": m_uw.group(1).strip() if m_uw else "JPX目論見書参照",
        "market": m_mkt.group(1).strip() if m_mkt else "東証グロース/スタンダード"
    }

@st.cache_data(ttl=600)
def fetch_upcoming_jpx_ipo_schedule() -> list:
    schedule_items, seen_names = [], set()
    queries = [
        '("新規上場" OR "上場承認") ("東証グロース" OR "東証プライム" OR "東証スタンダード" OR "公開価格")',
        'site:finance.yahoo.co.jp/stocks/ipo OR site:kabutan.jp "新規上場承認"'
    ]
    for q in queries:
        for h in search_single_query(q, 10, trusted_only=False, max_age_hours=720.0):
            clean_h = re.sub(r"\[.*?\]", "", h).strip()
            if not clean_h: continue
            det = _extract_ipo_schedule_details(clean_h, is_unlisted_rumor=False)
            codes_found = [dc for dc in dict.fromkeys(re.findall(r"(?<![0-9A-Za-z])([1-9][0-9]{2}[0-9A-Z])(?![0-9A-Za-z])", clean_h)) if not re.match(r"^202[0-9]$", dc)]
            corp_name = ""
            if codes_found:
                c4 = codes_found[0]
                m_nm = re.search(rf"([^\s「」『』【】\(\)（）]{{2,18}})\s*[\(（<＜\[]?\s*{re.escape(c4)}", clean_h)
                if m_nm: corp_name = _clean_corp_name(m_nm.group(1))
                if not corp_name or corp_name == c4:
                    corp_name = resolve_ticker_metadata(f"{c4}.T").get("name", f"東証{c4}")
            else:
                m_c2 = re.search(r"([^\s「」『』【】\(\)（）]{2,18})(?:が|、)(?:東証|新規上場|上場承認)", clean_h)
                if m_c2: corp_name = _clean_corp_name(m_c2.group(1))
            if corp_name and corp_name not in seen_names and not any(ng in corp_name for ng in ["東証", "新規上場", "承認", "一覧", "スケジュール", "IPO"]):
                seen_names.add(corp_name)
                code_disp = codes_found[0] if codes_found else "未定"
                schedule_items.append({
                    "code": code_disp,
                    "stage_label": "🔴 東証新規上場承認・直近スケジュール抽出",
                    "name": corp_name,
                    "market": det["market"],
                    "listing_date_disp": det["listing_date_disp"],
                    "offer_info": det["offer_info"],
                    "bb_info": det["bb_info"],
                    "lead_underwriter": det["lead_underwriter"],
                    "absorption_scale": "目論見書・JPX公表値参照",
                    "theme": "東証新規上場承認・IPOセカンダリー注目企業",
                    "business_desc": f"直近の市場報道・新規上場承認情報において確認された注目IPO企業です。{clean_h[:110]}",
                    "supply_outlook": "上場初日は公開価格と初値の乖離率（公募比）および寄り付き後のVWAP維持が最重要ポイントです。初値高騰後の飛びつき買いは避け、OR15分レンジ形成後の押し目反発を確認してからエントリーしてください。",
                    "latest_headline": clean_h,
                    "query": f'"{corp_name}" IPO'
                })
            if len(schedule_items) >= 4: break
        if len(schedule_items) >= 4: break
    return schedule_items

@st.cache_data(ttl=86400)
def _resolve_dynamic_ipo_listing_info(full_code: str) -> dict:
    if full_code in IPO_HISTORICAL_META:
        return dict(IPO_HISTORICAL_META[full_code])
    df_max = None
    try:
        df_max = yf.Ticker(full_code).history(period="max", interval="1d", auto_adjust=True)
        if df_max is not None and not df_max.empty:
            df_max = df_max.dropna(subset=["Open", "Close"]).sort_index()
    except Exception as e:
        record_system_error(f"_resolve_dynamic_ipo_listing_info:hist:{full_code}", e)
    yf_first_open = float(df_max["Open"].iloc[0]) if (df_max is not None and not df_max.empty and float(df_max["Open"].iloc[0]) > 0) else None
    yf_first_dt = df_max.index[0].strftime("%Y-%m-%d") if (df_max is not None and not df_max.empty and hasattr(df_max.index[0], "strftime")) else ""
    if yf_first_open is not None:
        return {"listing_date": yf_first_dt or datetime.now().strftime("%Y-%m-%d"), "offer_price": None, "initial_price": round(yf_first_open, 1), "lead_underwriter": "東証新規上場（実測履歴特定）", "absorption_scale": "市場データ自動検出", "note": "※公開価格は非公表/未登録のため初日始値を初値（実測）として表示"}
    return {"listing_date": datetime.now().strftime("%Y-%m-%d"), "offer_price": None, "initial_price": None, "lead_underwriter": "東証グロース/新規発掘", "absorption_scale": "市場データ自動検出", "note": ""}

def _extract_ticker_df(raw_df, code: str, total_codes: int):
    if raw_df is None or raw_df.empty: return None
    if isinstance(raw_df.columns, pd.MultiIndex):
        if code in raw_df.columns.get_level_values(0): return raw_df[code]
        if code in raw_df.columns.get_level_values(1): return raw_df.xs(code, axis=1, level=1)
        return None
    return raw_df if total_codes == 1 else (raw_df[code] if code in raw_df else None)

@st.cache_data(ttl=300)
def fetch_real_ipo_growth_analysis() -> dict:
    extracted_ipo_firms = fetch_upcoming_jpx_ipo_schedule()
    combined_upcoming, seen_up_names = [], set()
    for it in extracted_ipo_firms:
        nm_k = re.sub(r"\s+", "", it["name"])
        if nm_k not in seen_up_names:
            seen_up_names.add(nm_k); combined_upcoming.append(dict(it))
    for w_it in UPCOMING_IPO_WATCHLIST:
        nm_k = re.sub(r"\s+", "", w_it["name"].split("（")[0])
        if nm_k not in seen_up_names and len(combined_upcoming) < 6:
            seen_up_names.add(nm_k); combined_upcoming.append(dict(w_it))

    today_tag = datetime.now().strftime("%d %b %Y")
    def _enrich_upcoming_card(card_obj: dict) -> dict:
        hits = search_single_query(card_obj.get("query", f'"{card_obj["name"]}" IPO'), 6, trusted_only=False, max_age_hours=720.0)
        headline = re.sub(r"\(.*?\)|\[.*?\]", "", hits[0]).strip() if hits else card_obj.get("latest_headline", "上場準備・需給動向を継続モニタリング中")
        buzz_cnt = len(hits)
        recent_cnt = sum(1 for h in hits if today_tag in h or "時間前" in h or "分前" in h)
        card_obj["heat_score"] = int(np.clip(55 + buzz_cnt * 4 + recent_cnt * 5, 50, 99))
        card_obj["latest_headline"] = headline
        c_raw = str(card_obj.get("code", "未定")).strip()
        if re.match(r"^[1-9][0-9]{2}[0-9A-Z]$", c_raw):
            card_obj["kabutan_url"] = f"https://kabutan.jp/stock/?code={c_raw}"
            card_obj["yahoo_url"] = f"https://finance.yahoo.co.jp/quote/{c_raw}.T"
        else:
            q_enc = urllib.parse.quote(card_obj["name"].split("（")[0])
            card_obj["kabutan_url"] = f"https://kabutan.jp/news/?q={q_enc}"
            card_obj["yahoo_url"] = f"https://finance.yahoo.co.jp/search/?query={q_enc}"
        card_obj["jpx_ipo_url"] = "https://www.jpx.co.jp/listing/stocks/new/index.html"
        return card_obj

    upcoming_cards = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        for f in as_completed([ex.submit(_enrich_upcoming_card, c) for c in combined_upcoming]):
            try: upcoming_cards.append(f.result())
            except Exception as e: record_system_error("fetch_real_ipo_growth_analysis:upcoming", e)
    upcoming_cards.sort(key=lambda x: (0 if "🔴" in x.get("stage_label", "") else (1 if "🟠" in x.get("stage_label", "") else (2 if "🟣" in x.get("stage_label", "") else 3)), -x.get("heat_score", 60)))

    dynamic_ipo_pool, seen_ipo_codes = list(REAL_IPO_GROWTH_UNIVERSE), {it[0] for it in REAL_IPO_GROWTH_UNIVERSE} | DELISTED_OR_INVALID_CODES
    try:
        for snip in search_single_query('("IPO" OR "新規上場" OR "東証グロース") 株価 急騰', 8, trusted_only=False, max_age_hours=720.0):
            for fc, nm, _, th in _extract_tickers_from_text(snip):
                if fc.endswith(".T") and fc not in seen_ipo_codes:
                    seen_ipo_codes.add(fc); dynamic_ipo_pool.append((fc, nm, "東証グロース/新規発掘", th))
                    if len(dynamic_ipo_pool) >= 22: break
    except Exception as e_disc:
        record_system_error("fetch_real_ipo_growth_analysis:discover", e_disc)
    codes = [c for c, _, _, _ in dynamic_ipo_pool]
    raw = None
    try: raw = yf.download(codes, period="1mo", interval="1d", group_by="ticker", threads=True, progress=False, timeout=10.0)
    except Exception as e: record_system_error("fetch_real_ipo_growth_analysis:download", e); raw = None
    all_evaluated, today_dt = [], datetime.now()

    def _analyze_ipo_item(item):
        c, name, mkt, theme = item
        try:
            df_raw_c = _extract_ticker_df(raw, c, len(codes))
            if df_raw_c is None or df_raw_c.dropna(subset=["Close"]).empty:
                try: df_raw_c = yf.Ticker(c).history(period="1mo", interval="1d", auto_adjust=True)
                except Exception: df_raw_c = None
            df = normalize_ohlcv_df(df_raw_c, min_rows=3)
            code4 = c.replace(".T", "")
            hist_meta = _resolve_dynamic_ipo_listing_info(c)
            listing_date_str = str(hist_meta.get("listing_date") or "")
            days_since_listing, lockup_alert, lockup_note = 0, False, ""
            if listing_date_str:
                try:
                    days_since_listing = max(0, (today_dt - datetime.strptime(listing_date_str[:10], "%Y-%m-%d")).days)
                    if (75 <= days_since_listing <= 105) or (165 <= days_since_listing <= 195):
                        lockup_alert = True
                        lockup_note = f"⚠️ ロックアップ期間（{90 if days_since_listing <= 120 else 180}日）節目チェック推奨（上場後 {days_since_listing}日経過）"
                except Exception: pass
            offer_px, init_px = hist_meta.get("offer_price"), hist_meta.get("initial_price")

            if df is None:
                fallback_px = float(init_px) if (init_px is not None and float(init_px) > 0) else (float(offer_px) if (offer_px is not None and float(offer_px) > 0) else 0.0)
                offer_str = f"{float(offer_px):,.0f}円" if (offer_px is not None and float(offer_px) > 0) else "非公表 / 市場実測"
                init_str = f"{float(init_px):,.0f}円 ({round(((float(init_px) - float(offer_px)) / float(offer_px)) * 100.0, 1):+.1f}%)" if (offer_px and init_px and float(offer_px) > 0 and float(init_px) > 0) else (f"{float(init_px):,.0f}円" if init_px else "実測中")
                return {"code": code4, "full_code": c, "name": name, "market": mkt, "theme": theme, "listing_date": listing_date_str, "days_since_listing": days_since_listing, "lockup_alert": lockup_alert, "lockup_note": lockup_note, "offer_price_str": offer_str, "initial_price_str": init_str, "curr_vs_init_str": "0.0%", "lead_underwriter": hist_meta.get("lead_underwriter", "-"), "absorption_scale": hist_meta.get("absorption_scale", "-"), "ipo_meta_note": hist_meta.get("note", "※相場データ取得待機中・基本メタデータ表示"), "price": f"{fallback_px:,.0f}円" if fallback_px > 0 else "データ取得中", "chg_pct": 0.0, "period_range": "-", "from_high_pct": 0.0, "curr_vol": 0, "rvol": 1.0, "ann_vol": 0.0, "turnover_m_yen": 0.0, "score": 55, "tier": "🛡️ B級残留：基準メタデータ監視モード", "latest_headline": "直近の特段の悪材料なし・需給推移中", "kabutan_url": f"https://kabutan.jp/stock/?code={code4}", "yahoo_url": f"https://finance.yahoo.co.jp/quote/{code4}.T", "jpx_ipo_url": "https://www.jpx.co.jp/listing/stocks/new/index.html"}

            cl, hi, lo, vo = [df[col].values.astype(float) for col in ["Close", "High", "Low", "Volume"]]
            curr_px, prev_px = float(cl[-1]), float(cl[-2]) if len(cl) >= 2 else float(cl[-1])
            chg_pct = round(((curr_px - prev_px) / max(prev_px, 1e-4)) * 100.0, 2)
            period_high, period_low = float(np.max(hi)), float(np.min(lo))
            from_high_pct = round(((curr_px - period_high) / max(period_high, 1e-4)) * 100.0, 2)
            rvol = round(float(vo[-1]) / max(float(np.mean(vo[-6:-1])) if len(vo) >= 6 else float(np.mean(vo)), 1.0), 2)
            rets = np.diff(cl) / np.maximum(cl[:-1], 1e-4)
            ann_vol = round(float(np.std(rets) * np.sqrt(252) * 100.0), 1) if len(rets) >= 3 else 0.0
            news_items = search_single_query(f"{name} 株価", 4, trusted_only=False, max_age_hours=168.0)
            score = int(np.clip(50 + chg_pct * 3.5 + (rvol - 1.0) * 18.0 + (20.0 + from_high_pct) * 0.6 + len(news_items) * 2.0, 15, 99))
            tier = "🔥 S級サバイバー：出来高急増・高値圏ブレイク態勢" if score >= 80 else ("⚡ A級サバイバー：順張り・押し目需給良好" if score >= 65 else ("🛡️ B級残留：底値固め・出来高待ちフェーズ" if score >= 52 else "💀 C級脱落圏：モメンタム低下・圏外淘汰候補"))
            if offer_px is not None and float(offer_px) > 0:
                offer_str = f"{float(offer_px):,.0f}円"
                init_str = f"{float(init_px):,.0f}円 ({round(((float(init_px) - float(offer_px)) / float(offer_px)) * 100.0, 1):+.1f}%)" if (init_px is not None and float(init_px) > 0) else "算出中"
            else:
                offer_str = "非公表 / 市場実測"
                init_str = f"{float(init_px):,.0f}円 (初日始値実測)" if (init_px is not None and float(init_px) > 0) else "実測中"
            curr_vs_init_str = f"{round(((curr_px - float(init_px)) / float(init_px)) * 100.0, 1):+.1f}%" if (init_px is not None and float(init_px) > 0) else "-"
            return {"code": code4, "full_code": c, "name": name, "market": mkt, "theme": theme, "listing_date": listing_date_str, "days_since_listing": days_since_listing, "lockup_alert": lockup_alert, "lockup_note": lockup_note, "offer_price_str": offer_str, "initial_price_str": init_str, "curr_vs_init_str": curr_vs_init_str, "lead_underwriter": hist_meta.get("lead_underwriter", "-"), "absorption_scale": hist_meta.get("absorption_scale", "-"), "ipo_meta_note": hist_meta.get("note", ""), "price": f"{curr_px:,.0f}円", "chg_pct": chg_pct, "period_range": f"{period_low:,.0f}円 〜 {period_high:,.0f}円", "from_high_pct": from_high_pct, "curr_vol": int(vo[-1]), "rvol": rvol, "ann_vol": ann_vol, "turnover_m_yen": round((curr_px * float(vo[-1])) / 1_000_000.0, 1), "score": score, "tier": tier, "latest_headline": re.sub(r"\[.*?\]", "", news_items[0]).strip() if news_items else "直近の特段の悪材料なし・需給推移中", "kabutan_url": f"https://kabutan.jp/stock/?code={code4}", "yahoo_url": f"https://finance.yahoo.co.jp/quote/{code4}.T", "jpx_ipo_url": "https://www.jpx.co.jp/listing/stocks/new/index.html"}
        except Exception as e_item: record_system_error(f"fetch_real_ipo_growth_analysis:{c}", e_item); return None
    with ThreadPoolExecutor(max_workers=6) as ex:
        for f in as_completed([ex.submit(_analyze_ipo_item, it) for it in dynamic_ipo_pool]):
            res_it = f.result()
            if res_it: all_evaluated.append(res_it)
    all_evaluated.sort(key=lambda x: x["score"], reverse=True)
    survivors, eliminated = all_evaluated[:6], all_evaluated[6:]
    for idx, r in enumerate(survivors, 1): r["rank"] = idx
    return {"upcoming_ipos": upcoming_cards, "survivors": survivors, "eliminated": eliminated, "total_scanned": len(all_evaluated)}

def search_web_knowledge_parallel(q1: str, q2: str) -> list:
    res = []
    with ThreadPoolExecutor(max_workers=2) as ex:
        f1 = ex.submit(search_single_query, q1, 3, True); f2 = ex.submit(search_single_query, q2, 3, False) if q2 else None
        try:
            res.extend(f1.result())
            if f2: res.extend(f2.result())
        except Exception as e: record_system_error("search_web_knowledge_parallel", e)
    return list(dict.fromkeys(res))

def calculate_text_similarity(s1: str, s2: str) -> float:
    w1, w2 = set(re.findall(r"[\u4e00-\u9fa5\u3040-\u309f\u30a0-\u30ffa-zA-Z0-9]{2,}", s1)), set(re.findall(r"[\u4e00-\u9fa5\u3040-\u309f\u30a0-\u30ffa-zA-Z0-9]{2,}", s2))
    return float(len(w1 & w2)) / float(max(len(w1 | w2), 1)) if w1 and w2 else 0.0

def sanitize_and_verify_dialogue(turns: list, r: dict, uq: str = "") -> list:
    uq_clean = (uq or "").strip()
    cliches = ["おい！『", "神話級クオンツ分析完了", "おいおい！【", "って書いた奴！", "スレ民調子に乗るなよｗ 『", "ご質問ありがとうございます", "承知いたしました", "AIとしてお答えします", "投資は自己責任です"]
    m10 = r.get("macro_10y", {}); d2y = r.get("daily_2y", {}); ft = r.get("forward_test", {})
    vp_lbl = str(d2y.get("vp_struct_label", "標準出来高分布"))
    sqn_v = float(ft.get("sqn", 0.0)); max_dd_v = float(ft.get("max_dd_pct", 0.0)); avg_r_v = float(ft.get("avg_r", 0.0))
    rs_30m = float(r.get("intraday_rs_30m", 0.0))
    role_fallbacks = {
        "IGNIS": f"【定量監査置換】{r.get('name','')}（{r.get('code','')}）は当日VWAP（{r.get('vwap_price','-')}）とOR15分初動レンジを基準に、30分RS先行度（{rs_30m:+.2f}%）を確認した上で次バー始値で執行します。",
        "TECHNOS": f"【定量監査置換】週足10年POC（{m10.get('poc_10y_str','-')}）×日足MA25（{d2y.get('ma25_str','-')}）×価格帯別出来高構造（{vp_lbl}）の3階層MTF構造に基づき目標{r.get('tp_price','-')}を設定しています。",
        "SENTINEL": f"【定量監査置換】上ヒゲ圧力（{r.get('upper_wick_pressure',0):.1f}）および価格帯別出来高（{vp_lbl}）の抵抗帯を監視し、高値掴みを回避するため逆指値{r.get('sl_price','-')}を厳格設定します。",
        "AEGIS": f"【定量監査置換】リークフリー検証実績（実質勝率{ft.get('actual_win_rate',0):.1f}% / PF={ft.get('profit_factor',0):.2f} / SQN={sqn_v:.2f} / 平均{avg_r_v:+.2f}R / 最大DD={max_dd_v:.1f}%）と許容リスクに基づき推奨{r.get('lot_info',{}).get('shares',0):,}株・+1.0R半分利確を適用します。",
        "NEXUS": f"【定量監査置換】実戦適格ゲート（{r.get('exec_grade','')}）および総合期待度{r.get('expect_pct',0)}%に基づき、{r.get('strat',{}).get('entry_mode','')}で執行します。"
    }
    sanitized = []
    for t in turns:
        if not isinstance(t, dict) or "round" in t or t.get("is_user"):
            sanitized.append(t); continue
        txt = str(t.get("text", "")).strip()
        spk = str(t.get("speaker", ""))
        matched_key = next((ak for ak in ("IGNIS", "TECHNOS", "SENTINEL", "AEGIS", "NEXUS") if ak in spk.upper()), "NEXUS")
        has_bad = (not txt) or any(cw in txt for cw in cliches) or (len(uq_clean) >= 6 and (f"『{uq_clean}』" in txt or f"「{uq_clean}」" in txt or uq_clean in txt))
        if has_bad:
            t_copy = dict(t); t_copy["text"] = role_fallbacks[matched_key]
            sanitized.append(t_copy)
        else:
            sanitized.append(t)
    txt_all = " ".join([t.get("text", "") for t in sanitized if isinstance(t, dict) and "text" in t and not t.get("is_user")])
    sigs = st.session_state.setdefault("stock_dialogue_signatures", {})
    sc = str(r.get("code", ""))
    max_sim = max([calculate_text_similarity(txt_all, ot) for oc, ot in sigs.items() if oc != sc] or [0.0])
    if sc: sigs[sc] = txt_all
    st.session_state["last_audit_similarity_penalty"] = int(max(0, round((max_sim - 0.25) * 30)))
    return sanitized

# =========================================================================
# DEEP DIVE 予測情報の双方向自動統合ヘルパー（Fusion Engine）
# =========================================================================
def _merge_dd_intel_into_lab_item(r: dict) -> dict:
    if not isinstance(r, dict):
        return r
    out = dict(r)
    fc = str(out.get("full_code", "")).strip().upper()
    intel_entry = load_shared_ticker_intel().get(fc, {}) if fc else {}
    dd_res = intel_entry.get("dd_result") if isinstance(intel_entry, dict) else None
    dd_updated = str(intel_entry.get("dd_updated_at") or "") if isinstance(intel_entry, dict) else ""

    lab_exp = float(out.get("expect_pct", 50.0) or 50.0)
    if not isinstance(dd_res, dict) or not dd_res:
        out["has_dd_intel"] = False
        out["fusion_expect_pct"] = round(lab_exp, 1)
        out["dd_sync_label"] = ""
        out["dd_sync_ok"] = None
        out["dd_intel"] = {}
        return out

    is_jp = ".T" in fc
    side = str((out.get("strat") or {}).get("side", "LONG")).upper()
    is_long = (side != "SHORT")

    dd_fusion = dd_res.get("fusion_score")
    dd_sc = float(dd_fusion if dd_fusion is not None else (dd_res.get("dd_score") or dd_res.get("comp_score") or lab_exp))
    dd_close_chg = float(dd_res.get("est_close_chg", 0.0) or 0.0)
    dd_close_px = float(dd_res.get("est_close_px", 0.0) or 0.0)
    dd_open_px = float(dd_res.get("est_open_px", 0.0) or 0.0)
    dip_time = str(dd_res.get("dip_time") or "-")
    dip_px = float(dd_res.get("dip_px", 0.0) or 0.0)
    peak_time = str(dd_res.get("peak_time") or "-")
    peak_px = float(dd_res.get("peak_px", 0.0) or 0.0)

    s3w = dd_res.get("short_horizon_3way") if isinstance(dd_res.get("short_horizon_3way"), dict) else {}
    p_up = int(s3w.get("p_up", 33))
    p_fl = int(s3w.get("p_flat", 34))
    p_dn = int(s3w.get("p_down", 33))

    exp_reg = dd_res.get("expansion_regime") if isinstance(dd_res.get("expansion_regime"), dict) else {}
    cvd_div = dd_res.get("cvd_div") if isinstance(dd_res.get("cvd_div"), dict) else {}
    scen_p = dd_res.get("scenario_probs") if isinstance(dd_res.get("scenario_probs"), dict) else {}

    dir_match = (dd_close_chg >= -0.15) if is_long else (dd_close_chg <= 0.15)
    if exp_reg.get("active"):
        if (is_long and exp_reg.get("dir") == "DOWN") or ((not is_long) and exp_reg.get("dir") == "UP"):
            dir_match = False

    fusion_expect = round(float(np.clip(lab_exp * 0.50 + dd_sc * 0.50, 5.0, 99.0)), 1)
    if dir_match:
        sync_lbl = "🟢 LAB×DD完全同期"
    else:
        sync_lbl = "⚠️ LAB×DD乖離警戒（押し目/戻り待ち推奨）"

    out["has_dd_intel"] = True
    out["dd_updated_at"] = dd_updated
    out["fusion_expect_pct"] = fusion_expect
    out["dd_sync_label"] = sync_lbl
    out["dd_sync_ok"] = dir_match
    out["dd_intel"] = {
        "fusion_score": dd_sc,
        "est_open_px": dd_open_px,
        "est_close_px": dd_close_px,
        "est_close_chg": dd_close_chg,
        "dip_time": dip_time,
        "dip_px": dip_px,
        "peak_time": peak_time,
        "peak_px": peak_px,
        "fusion_entry_px": float(dd_res.get("fusion_entry_px", 0.0) or 0.0),
        "fusion_half_r_px": float(dd_res.get("fusion_half_r_px", 0.0) or 0.0),
        "fusion_tp_px": float(dd_res.get("fusion_tp_px", 0.0) or 0.0),
        "fusion_sl_px": float(dd_res.get("fusion_sl_px", 0.0) or 0.0),
        "short_3way": {"active": bool(s3w.get("active")), "p_up": p_up, "p_flat": p_fl, "p_down": p_dn},
        "expansion_active": bool(exp_reg.get("active")),
        "expansion_label": str(exp_reg.get("label") or "通常レジーム"),
        "expansion_dir": str(exp_reg.get("dir") or "NONE"),
        "cvd_label": str(cvd_div.get("label") or "計測中"),
        "cvd_state": str(cvd_div.get("state") or "WAIT"),
        "scenario_probs": scen_p,
        "verdict": str(dd_res.get("verdict") or ""),
        "summary": str(dd_res.get("summary") or ""),
    }
    return out

def _format_dd_shared_summary(dd_res: dict) -> str:
    if not isinstance(dd_res, dict) or not dd_res:
        return ""
    parts = []
    f_sc = dd_res.get("fusion_score") or dd_res.get("dd_score")
    if f_sc is not None:
        parts.append(f"統合スコア:{float(f_sc):.1f}%")
    if dd_res.get("est_close_chg") is not None:
        parts.append(f"DD大引け予測:{float(dd_res['est_close_chg']):+.2f}%")
    if dd_res.get("dip_time"):
        parts.append(f"押目:{dd_res['dip_time']} / 高値:{dd_res.get('peak_time','-')}")
    s3w = dd_res.get("short_horizon_3way")
    if isinstance(s3w, dict) and s3w.get("active"):
        parts.append(f"30分3分岐(▲{s3w.get('p_up',33)}%/▶{s3w.get('p_flat',34)}%/▼{s3w.get('p_down',33)}%)")
    cvd = dd_res.get("cvd_div")
    if isinstance(cvd, dict) and cvd.get("label"):
        parts.append(f"CVD:{cvd['label']}")
    exp_r = dd_res.get("expansion_regime")
    if isinstance(exp_r, dict) and exp_r.get("active"):
        parts.append(f"🚨{exp_r.get('label','ブレイク中')}")
    if not parts and dd_res.get("verdict"):
        parts.append(str(dd_res["verdict"])[:140])
    return " ｜ ".join(parts)

def _build_natural_fallback_dialogue(uq: str, r: dict, st_style: str, web_hits: list, ig: dict, tc: dict, sn: dict, nx: dict, ae: dict, dd_summary: str = "") -> list:
    r_m = _merge_dd_intel_into_lab_item(r)
    dd_i = r_m.get("dd_intel", {})
    has_dd = bool(r_m.get("has_dd_intel"))
    stock_kws = ["株", "買", "売", "配当", "決算", "チャート", "板", "気配", "PER", "PBR", "PTS", "利確", "損切", "ロット", "銘柄", "指数", "先物", "寄", "信用", "空売り"]
    game_kws = ["ゲーム", "ガチャ", "PS5", "Switch", "steam", "モンハン", "原神", "ポケモン", "RPG", "fps", "課金", "攻略", "ボス", "任天堂", "カプコン"]
    is_stock = any(kw in uq for kw in stock_kws) or (r['name'] in uq) or (r['code'] in uq) if uq else True
    is_game = any(gkw in uq for gkw in game_kws)
    is_short = (r.get("strat", {}).get("side") == "SHORT")
    spec = get_style_spec(st_style)
    exec_g = r.get("exec_grade", "🔵 Grade-B: 標準執行（基準厳守）")
    m10 = r.get("macro_10y", {}); m10_lbl = m10.get("regime_10y_label", "10年大局中立"); m10_poc = m10.get("poc_10y_str", "-")
    d2y = r.get("daily_2y", {}); d2y_lbl = d2y.get("regime_1d_label", "日足中立"); d2y_ma = d2y.get("ma_align_label", "MA均衡"); d2y_sc = d2y.get("daily_trend_score", 50)
    vp_lbl = d2y.get("vp_struct_label", "⚖️ 標準出来高分布")
    ft = r.get("forward_test", {})
    ft_win, ft_profit, ft_pf = float(ft.get("actual_win_rate", 50.0)), float(ft.get("total_profit_yen", 0.0)), float(ft.get("profit_factor", 0.0))
    ft_sqn, ft_dd, ft_avgr = float(ft.get("sqn", 0.0)), float(ft.get("max_dd_pct", 0.0)), float(ft.get("avg_r", 0.0))
    rs_30m = float(r.get("intraday_rs_30m", 0.0))

    dd_time_note = f"DD5分足軌道では押し目候補 {dd_i.get('dip_time','-')} / ピーク想定 {dd_i.get('peak_time','-')}（大引け予測 {dd_i.get('est_close_chg',0.0):+.2f}% / 30分3分岐 ▲{dd_i.get('short_3way',{}).get('p_up',33)}%/▼{dd_i.get('short_3way',{}).get('p_down',33)}%）を示唆。" if has_dd else ""
    dd_cvd_note = f"DD側CVD状態は『{dd_i.get('cvd_label','-')}』、レジームは『{dd_i.get('expansion_label','通常レジーム')}』を検知。" if has_dd else ""
    dd_fusion_note = f"【LAB×DD統合判定: {r_m.get('dd_sync_label','')} / 統合期待度 {r_m.get('fusion_expect_pct', r['expect_pct'])}%】" if has_dd else ""

    if not uq:
        diff_v, rvol_v = float(r.get("diff", 0.0)), float(r.get("rvol", 1.0))
        u_wick, l_wick = float(r.get("upper_wick_pressure", 0.0)), float(r.get("lower_wick_support", 0.0))
        b_edge, s_edge, rs_al = float(r.get("bull_edge", 0.0)), float(r.get("bear_edge", 0.0)), float(r.get("rs_alpha", 0.0))
        genre_s, theme_s = r.get("genre", ""), r.get("theme", "")
        clean_news = re.sub(r"\(.*?\)|\[.*?\]", "", web_hits[0]).strip() if web_hits else f"{theme_s}関連の需給思惑"

        if is_short:
            ig_msg = f"【統計ルール推論】{r['name']}（{r['code']}・{exec_g}）は日足『{d2y_lbl}』×10年大局『{m10_lbl}』に対しSHORT優勢度{s_edge:+.1f}（上ヒゲ圧力{u_wick:.1f} / 30分RS={rs_30m:+.2f}%）で売りシグナル点灯。{dd_time_note} VWAP（{r['vwap_price']}）割れの陰線確定後、次バー始値で空売り（SHORT）を執行します。"
            ig_tone = "rage"
            sn_msg = f"【統計ルール推論】価格帯別出来高（{vp_lbl}）、日足MA25（{d2y.get('ma25_str','-')}）、10年POC（{m10_poc}）と上ヒゲ圧力{u_wick:.1f}を厳格監視。{dd_cvd_note} 踏み上げ逆指値（{r['sl_price']}）を必ず設定します。"
            ae_msg = f"【統計ルール推論】リークフリー検証（実質勝率{ft_win:.1f}% / PF={ft_pf:.2f} / SQN={ft_sqn:.2f} / 平均{avg_r_v:+.2f}R / 最大DD={ft_dd:.1f}%）に基づき推奨{r['lot_info']['shares']:,}株を算出。+1.0R到達で50%買い戻し利確＋建値ロックを適用します。"
            nx_msg = f"【統計ルール推論・統括】{dd_fusion_note}『{r['name']}（{exec_g}）』は週足10年×日足2年×5分足SHORT優勢度({s_edge:+.1f})の合致により空売り（SHORT）を採択。推奨{r['lot_info']['shares']:,}株を目標{r['tp_price']}・逆指値{r['sl_price']}で執行します。"
        else:
            mode_note = f"（※{spec['pfx']}モードのため買い専念）" if not spec["allow_short"] else f"（LONG優勢度{b_edge:+.1f} / 日次RSα={rs_al:+.2f}% / 30分RS={rs_30m:+.2f}%）"
            if spec["tf"] == "1d":
                ref_ma = d2y.get("ma25_str", "-") if spec["pfx"] == "スイングトレード" else f"10年POC({m10_poc}) / MA75({d2y.get('ma75_str','-')})"
                ig_msg = f"【統計ルール推論】{r['name']}（{exec_g}）は{spec['pfx']}基準で{ref_ma}の支持帯と出来高構造（{vp_lbl}）を確認中。{dd_time_note} 押し目陽線確定の翌営業日始値で執行します。{mode_note}"
                ig_tone = "agree"
                sn_msg = f"【統計ルール推論】セクター（{genre_s}）の変動幅と価格帯別出来高（{vp_lbl}）の抵抗帯を警戒。{dd_cvd_note} 逆指値（{r['sl_price']}）を厳守します。"
                ae_msg = f"【統計ルール推論】リークフリー検証（実質勝率{ft_win:.1f}% / PF={ft_pf:.2f} / SQN={ft_sqn:.2f} / 平均{avg_r_v:+.2f}R / 最大DD={ft_dd:.1f}%）に基づき、推奨{r['lot_info']['shares']:,}株・+1.0R半分利確＋建値ロックで資本を防衛します。"
                nx_msg = f"【統計ルール推論・統括】{dd_fusion_note}『{r['name']}（{exec_g}）』は週足10年『{m10_lbl}』×日足2年『{d2y_lbl}({d2y_sc}点)』が合致し【{r['strat']['tactic_type']}】を採択。推奨{r['lot_info']['shares']:,}株を目標{r['tp_price']}・逆指値{r['sl_price']}（最大{spec['max_hold_days']}営業日）で執行します。"
            else:
                if diff_v >= 2.5 and rvol_v >= 1.3:
                    ig_msg, ig_tone = f"【統計ルール推論】{r['name']}（{exec_g}）が前日比+{diff_v}%・RVOL {rvol_v}倍・30分RS {rs_30m:+.2f}%で先行。{dd_time_note} OR15分安値を維持しつつVWAP（{r['vwap_price']}）押し目確認＋高値更新陽線確定の次バー始値で執行します。{mode_note}", "agree"
                elif diff_v <= -1.5:
                    ig_msg, ig_tone = f"【統計ルール推論】{r['name']}（{exec_g}）が{diff_v}%まで調整中。日足MA25（{d2y.get('ma25_str','-')}）・10年POC（{m10_poc}）と下ヒゲ支持力{l_wick:.1f}を背景に{dd_time_note} VWAP（{r['vwap_price']}）奪還・陽線確定を確認すれば反発の好機です。{mode_note}", "doubt"
                else:
                    ig_msg, ig_tone = f"【統計ルール推論】{r['name']}（{r['code']}・{exec_g}）は現在値{r['price']}（日足:{d2y_lbl} / 30分RS:{rs_30m:+.2f}%）で推移。『{clean_news[:22]}』と{dd_time_note} VWAP押し目確認＋高値ブレイク陽線確定を待機します。{mode_note}", "agree"
                sn_msg = f"【統計ルール推論】セクター（{genre_s}）の往復ビンタと上値出来高（{vp_lbl}）の抵抗帯を警戒。{dd_cvd_note} VWAP+2σ超の飛びつきとOR15分安値割れでの逆張り買いは厳禁とし、逆指値（{r['sl_price']}）を厳守します。"
                ae_msg = f"【統計ルール推論】日足ATR14と検証成績（実質勝率{ft_win:.1f}% / PF={ft_pf:.2f} / SQN={ft_sqn:.2f} / 最大DD={ft_dd:.1f}%）に基づき推奨{r['lot_info']['shares']:,}株を算出。+1.0R到達時50%分割利確＋建値ロックを徹底します。"
                nx_msg = f"【統計ルール推論・統括】{dd_fusion_note}『{r['name']}（{exec_g}）』は週足10年『{m10_lbl}』×日足2年『{d2y_lbl}({d2y_sc}点)』×5分足OR15/VWAP波形が合致し【{r['strat']['tactic_type']}】を採択。推奨{r['lot_info']['shares']:,}株を目標{r['tp_price']}・逆指値{r['sl_price']}で執行します。"

        tc_msg = f"【{r['code']} 3階層MTF＆DD統合診断】週足10年={m10_lbl}（POC={m10_poc}）｜日足2年={d2y_lbl}（{d2y_ma} / {vp_lbl}）｜LONG={b_edge:+.1f} vs SHORT={s_edge:+.1f}｜30分RS={rs_30m:+.2f}%。{dd_time_note} リークフリー実質勝率{ft_win:.1f}%・PF={ft_pf:.2f}・SQN={ft_sqn:.2f}。"
        return [
            {"speaker": f"{ig['icon']} {ig['name']}", "role_label": f"{ig.get('role_title','短期モメンタム執行')} [統計推論]", "tone": ig_tone, "text": ig_msg},
            {"speaker": f"{tc['icon']} {tc['name']}", "role_label": f"{tc.get('role_title','3階層MTF・出来高構造解析')} [統計推論]", "tone": "normal", "text": tc_msg},
            {"speaker": f"{sn['icon']} {sn['name']}", "role_label": f"{sn.get('role_title','リスク・しこり壁監査')} [統計推論]", "tone": "doubt", "text": sn_msg},
            {"speaker": f"{ae['icon']} {ae['name']}", "role_label": f"{ae.get('role_title','検証・ケリー資金管理')} [統計推論]", "tone": "agree", "text": ae_msg},
            {"speaker": f"{nx['icon']} {nx['name']}", "role_label": f"{nx.get('role_title','最終執行裁定統括')} [統計推論]", "tone": "normal", "text": nx_msg}
        ]

    if is_game: return [{"speaker": f"{ig['icon']} {ig['name']}", "role_label": "短期モメンタム執行 [統計推論]", "tone": "agree", "text": "【統計ルール推論】ゲームの話題ですね。期待値管理と試行回数の最適化が重要です。"}, {"speaker": f"{tc['icon']} {tc['name']}", "role_label": "定量解析 [統計推論]", "tone": "normal", "text": "【統計ルール推論】期待値マイナスの試行を続けるのは統計的に非合理です。"}]
    if not is_stock:
        f_sum = ("・" + "\n・".join([re.sub(r'\(.*?\)|\[.*?\]', '', h).strip() for h in web_hits][:2])) if web_hits else ""
        return [{"speaker": f"{tc['icon']} {tc['name']}", "role_label": "定量解析 [統計推論]", "tone": "normal", "text": f"【統計ルール推論】WEBの最新動向を照合しました。\n{f_sum}\n構造を因数分解して判断するのが合理的です。" if f_sum else "【統計ルール推論】利害関係とインセンティブの構造を整理して考えるのが最も合理的です。"}, {"speaker": f"{ig['icon']} {ig['name']}", "role_label": "短期モメンタム執行 [統計推論]", "tone": "agree", "text": "【統計ルール推論】結論から整理して合理的に判断しましょう。"}]
    side_act = "VWAP割れの陰線確定後の次バー始値で空売り（SHORT）一括エントリー" if is_short else f"{r['strat']['entry_mode']}に従いOR15分安値維持・順張り買い（LONG）エントリー"
    return [{"speaker": f"{ig['icon']} {ig['name']}", "role_label": "短期モメンタム執行 [統計推論]", "tone": "agree", "text": f"【統計ルール推論】{dd_fusion_note} {r['name']}（現在{r['price']}・日足:{d2y_lbl}）は、{side_act}が有効です。{dd_time_note}"}, {"speaker": f"{ae['icon']} {ae['name']}", "role_label": "検証・ケリー資金管理 [統計推論]", "tone": "normal", "text": f"【統計ルール推論】東証呼値丸め済みの逆指値（{r['sl_price']}）と+1.0R到達時50%分割利確＋建値ロック（SQN={ft_sqn:.2f} / 最大DD={ft_dd:.1f}%）で執行するのが合理的です。"}]

def _parse_llm_json_turns(raw_res: str) -> list:
    if not raw_res: return []
    try:
        raw_clean = re.sub(r'```json|```', '', raw_res).strip()
        m_arr = re.search(r'\[.*\]', raw_clean, re.DOTALL)
        p = json.loads(m_arr.group(0) if m_arr else raw_clean)
        if isinstance(p, dict):
            for v in p.values():
                if isinstance(v, list): p = v; break
        if isinstance(p, list) and len(p) > 0: return [x for x in p if isinstance(x, dict) and "text" in x]
    except Exception as e: record_system_error("_parse_llm_json_turns", e)
    return []

@st.cache_data(ttl=1800)
def fetch_earnings_days_left(full_code: str):
    try:
        cal = yf.Ticker(str(full_code).strip().upper()).calendar
        if cal is None: return None
        dates_found = []
        if isinstance(cal, dict):
            ev = cal.get("Earnings Date")
            if isinstance(ev, (list, tuple)): dates_found.extend(ev)
            elif ev is not None: dates_found.append(ev)
        elif hasattr(cal, "loc") and "Earnings Date" in cal.index:
            row = cal.loc["Earnings Date"]
            dates_found.extend(row.tolist() if hasattr(row, "tolist") else [row])
        today_d = datetime.now().date()
        future_days = []
        for d_item in dates_found:
            if d_item is None: continue
            dt_obj = d_item.date() if hasattr(d_item, "date") else pd.to_datetime(str(d_item), errors="coerce").date()
            if dt_obj is not None:
                diff_d = (dt_obj - today_d).days
                if 0 <= diff_d <= 7:
                    bdays = int(np.busday_count(today_d.isoformat(), dt_obj.isoformat()))
                    future_days.append(bdays)
        return min(future_days) if future_days else None
    except Exception:
        return None

def build_tomorrow_forecast_svg(r: dict) -> str:
    try:
        r_m = _merge_dd_intel_into_lab_item(r)
        is_jp = ".T" in str(r_m.get("full_code", ""))
        fc = str(r_m.get("full_code", ""))
        cv = float(r_m.get("raw_close", 0.0))
        tp = float(r_m.get("raw_tp", cv * 1.03))
        sl = float(r_m.get("raw_sl", cv * 0.985))
        vwap = float(r_m.get("raw_vwap", cv))
        is_short = (r_m.get("strat", {}).get("side") == "SHORT")
        if cv <= 0: return ""

        has_dd = bool(r_m.get("has_dd_intel"))
        dd_i = r_m.get("dd_intel", {})

        if has_dd and float(dd_i.get("est_close_px", 0.0)) > 0:
            dd_open = float(dd_i.get("est_open_px", cv)) or cv
            dd_dip_px = float(dd_i.get("dip_px", 0.0)) or min(cv, vwap)
            dd_dip_tm = str(dd_i.get("dip_time") or "押目")
            dd_peak_px = float(dd_i.get("peak_px", 0.0)) or max(cv, tp)
            dd_peak_tm = str(dd_i.get("peak_time") or "高値")
            dd_close = float(dd_i.get("est_close_px", cv))
            s3 = dd_i.get("short_3way", {})
            header_sub = (
                f"⚡ DD連動: 30分3分岐 ▲{s3.get('p_up',33)}% / ▶{s3.get('p_flat',34)}% / ▼{s3.get('p_down',33)}% ｜ "
                f"CVD: {html.escape(dd_i.get('cvd_label','-'))}"
            )
            if is_short:
                entry_pt = round_to_tse_tick(float(dd_i.get("fusion_entry_px") or dd_peak_px), fc, "nearest")
                half_pt = round_to_tse_tick(float(dd_i.get("fusion_half_r_px") or (entry_pt - abs(sl - entry_pt))), fc, "floor")
                all_p = [cv, dd_open, dd_peak_px, dd_dip_px, dd_close, entry_pt, half_pt, tp, sl]
                p_min, p_max = min(all_p) * 0.996, max(all_p) * 1.004
                span = max(p_max - p_min, 1e-4)
                def to_y(val): return round(155.0 - ((val - p_min) / span) * 125.0, 1)
                y_cur, y_op, y_pk, y_dp, y_cl = to_y(cv), to_y(dd_open), to_y(dd_peak_px), to_y(dd_dip_px), to_y(dd_close)
                y_tp, y_sl, y_half = to_y(tp), to_y(sl), to_y(half_pt)
                path_d = f"M 40 {y_cur} L 95 {y_op} Q 130 {y_pk}, 165 {y_pk} Q 215 {round((y_pk+y_dp)/2,1)}, 250 {y_dp} L 315 {y_cl}"
                entry_lbl = f"📉 戻り売り {dd_peak_tm} ({fmt_px(dd_peak_px, is_jp, fc)})"
                path_col = "#fb7185"
                mid_cx, mid_cy = 165, y_pk
            else:
                entry_pt = round_to_tse_tick(float(dd_i.get("fusion_entry_px") or dd_dip_px), fc, "nearest")
                half_pt = round_to_tse_tick(float(dd_i.get("fusion_half_r_px") or (entry_pt + abs(entry_pt - sl))), fc, "ceil")
                all_p = [cv, dd_open, dd_dip_px, dd_peak_px, dd_close, entry_pt, half_pt, tp, sl]
                p_min, p_max = min(all_p) * 0.996, max(all_p) * 1.004
                span = max(p_max - p_min, 1e-4)
                def to_y(val): return round(155.0 - ((val - p_min) / span) * 125.0, 1)
                y_cur, y_op, y_dp, y_pk, y_cl = to_y(cv), to_y(dd_open), to_y(dd_dip_px), to_y(dd_peak_px), to_y(dd_close)
                y_tp, y_sl, y_half = to_y(tp), to_y(sl), to_y(half_pt)
                path_d = f"M 40 {y_cur} L 95 {y_op} Q 130 {y_dp}, 165 {y_dp} Q 215 {round((y_dp+y_pk)/2,1)}, 250 {y_pk} L 315 {y_cl}"
                entry_lbl = f"🛒 押目買い {dd_dip_tm} ({fmt_px(dd_dip_px, is_jp, fc)})"
                path_col = "#34d399"
                mid_cx, mid_cy = 165, y_dp

            return (
                f'<div class="svg-chart-wrap" style="border-color:rgba(249,115,22,0.5);margin-top:8px;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:4px;font-size:10.5px;font-weight:800;color:#fdba74;margin-bottom:4px;">'
                f'<span>🗺️ LAB × DEEP DIVE 統合軌道ナビ（実測5分足予測座標）</span>'
                f'<span style="font-family:JetBrains Mono,monospace;font-size:9.8px;color:#7dd3fc;">{header_sub}</span></div>'
                f'<svg viewBox="0 0 360 182" width="100%" style="max-height:188px;display:block;">'
                f'<line x1="35" y1="{y_tp}" x2="345" y2="{y_tp}" stroke="#10b981" stroke-width="1.2" stroke-dasharray="4,3"/>'
                f'<text x="342" y="{max(12.0, y_tp-3)}" fill="#6ee7b7" font-size="9" font-weight="bold" text-anchor="end">🎯 TP ({fmt_px(tp, is_jp, fc)})</text>'
                f'<line x1="35" y1="{y_half}" x2="345" y2="{y_half}" stroke="#facc15" stroke-width="1" stroke-dasharray="3,3"/>'
                f'<text x="342" y="{max(22.0, y_half-3)}" fill="#fde047" font-size="8.8" font-weight="bold" text-anchor="end">💰 +1.0R ({fmt_px(half_pt, is_jp, fc)})</text>'
                f'<line x1="35" y1="{y_sl}" x2="345" y2="{y_sl}" stroke="#ef4444" stroke-width="1.4" stroke-dasharray="4,2"/>'
                f'<text x="342" y="{min(176.0, y_sl+11)}" fill="#fca5a5" font-size="9" font-weight="bold" text-anchor="end">🛡️ SL ({fmt_px(sl, is_jp, fc)})</text>'
                f'<path d="{path_d}" fill="none" stroke="{path_col}" stroke-width="2.6" stroke-dasharray="5,3"/>'
                f'<circle cx="40" cy="{y_cur}" r="4" fill="#94a3b8"/><text x="40" y="{max(12.0, y_cur-6)}" fill="#cbd5e1" font-size="8.5" text-anchor="middle">現在</text>'
                f'<circle cx="95" cy="{y_op}" r="3.8" fill="#c084fc"/><text x="95" y="{max(12.0, y_op-6)}" fill="#e9d5ff" font-size="8.5" text-anchor="middle">始値想定</text>'
                f'<circle cx="{mid_cx}" cy="{mid_cy}" r="5.5" fill="#38bdf8" stroke="#fff" stroke-width="1.2"/>'
                f'<rect x="92" y="{min(158.0, max(18.0, mid_cy+7))}" width="146" height="15" rx="4" fill="rgba(7,11,20,0.92)" stroke="#38bdf8" stroke-width="1"/>'
                f'<text x="165" y="{min(168.5, max(28.5, mid_cy+17.5))}" fill="#7dd3fc" font-size="8.8" font-weight="bold" text-anchor="middle">{html.escape(entry_lbl)}</text>'
                f'<circle cx="250" cy="{y_dp if is_short else y_pk}" r="4.2" fill="#facc15"/><text x="250" y="{max(12.0, (y_dp if is_short else y_pk)-6)}" fill="#fde047" font-size="8.5" text-anchor="middle">{html.escape(dd_dip_tm if is_short else dd_peak_tm)}</text>'
                f'<circle cx="315" cy="{y_cl}" r="5.2" fill="#f97316" stroke="#fff" stroke-width="1.2"/><text x="315" y="{min(176.0, y_cl+12)}" fill="#fdba74" font-size="8.8" font-weight="bold" text-anchor="middle">大引け {fmt_px(dd_close, is_jp, fc)}</text>'
                f'</svg></div>'
            )

        if is_short:
            entry_pt = round_to_tse_tick(max(cv, vwap), fc, "nearest")
            half_pt = round_to_tse_tick(entry_pt - abs(sl - entry_pt), fc, "floor")
            all_p = [cv, entry_pt, half_pt, tp, sl]
            p_min, p_max = min(all_p) * 0.996, max(all_p) * 1.004
            span = max(p_max - p_min, 1e-4)
            def to_y(val): return round(155.0 - ((val - p_min) / span) * 125.0, 1)
            y_cur, y_ent, y_half, y_tp, y_sl = to_y(cv), to_y(entry_pt), to_y(half_pt), to_y(tp), to_y(sl)
            path_d = f"M 45 {y_cur} Q 95 {round((y_cur+y_ent)/2 - 6,1)}, 135 {y_ent} Q 185 {round((y_ent+y_half)/2,1)}, 225 {y_half} T 305 {y_tp}"
            entry_lbl = f"📉 ここで空売り ({fmt_px(entry_pt, is_jp, fc)})"
            path_col = "#fb7185"
        else:
            entry_pt = round_to_tse_tick(min(cv, vwap) if vwap > 0 else cv * 0.995, fc, "nearest")
            if entry_pt <= sl: entry_pt = round_to_tse_tick(cv * 0.997, fc, "nearest")
            half_pt = round_to_tse_tick(entry_pt + abs(entry_pt - sl), fc, "ceil")
            all_p = [cv, entry_pt, half_pt, tp, sl]
            p_min, p_max = min(all_p) * 0.996, max(all_p) * 1.004
            span = max(p_max - p_min, 1e-4)
            def to_y(val): return round(155.0 - ((val - p_min) / span) * 125.0, 1)
            y_cur, y_ent, y_half, y_tp, y_sl = to_y(cv), to_y(entry_pt), to_y(half_pt), to_y(tp), to_y(sl)
            path_d = f"M 45 {y_cur} Q 95 {round(max(y_cur, y_ent)+8,1)}, 135 {y_ent} Q 185 {round((y_ent+y_half)/2,1)}, 225 {y_half} T 305 {y_tp}"
            entry_lbl = f"🛒 ここで買う ({fmt_px(entry_pt, is_jp, fc)})"
            path_col = "#34d399"

        return (
            f'<div class="svg-chart-wrap" style="border-color:rgba(16,185,129,0.45);margin-top:8px;">'
            f'<div style="font-size:11px;font-weight:800;color:#6ee7b7;margin-bottom:4px;">🗺️ 初心者向け・明日の想定値動きナビゲーション図（売買ポイント可視化）</div>'
            f'<svg viewBox="0 0 360 180" width="100%" style="max-height:185px;display:block;">'
            f'<line x1="35" y1="{y_tp}" x2="345" y2="{y_tp}" stroke="#10b981" stroke-width="1.2" stroke-dasharray="4,3"/>'
            f'<text x="342" y="{max(12.0, y_tp-3)}" fill="#6ee7b7" font-size="9.5" font-weight="bold" text-anchor="end">🎯 最終利確 ({fmt_px(tp, is_jp, fc)})</text>'
            f'<line x1="35" y1="{y_half}" x2="345" y2="{y_half}" stroke="#facc15" stroke-width="1" stroke-dasharray="3,3"/>'
            f'<text x="342" y="{max(22.0, y_half-3)}" fill="#fde047" font-size="9" font-weight="bold" text-anchor="end">💰 半分利確 +1.0R ({fmt_px(half_pt, is_jp, fc)})</text>'
            f'<line x1="35" y1="{y_sl}" x2="345" y2="{y_sl}" stroke="#ef4444" stroke-width="1.4" stroke-dasharray="4,2"/>'
            f'<text x="342" y="{min(174.0, y_sl+11)}" fill="#fca5a5" font-size="9.5" font-weight="bold" text-anchor="end">🛡️ 損切りライン ({fmt_px(sl, is_jp, fc)})</text>'
            f'<path d="{path_d}" fill="none" stroke="{path_col}" stroke-width="2.6" stroke-dasharray="5,3"/>'
            f'<circle cx="45" cy="{y_cur}" r="4" fill="#94a3b8"/><text x="45" y="{max(12.0, y_cur-7)}" fill="#cbd5e1" font-size="9" text-anchor="middle">現在値</text>'
            f'<circle cx="135" cy="{y_ent}" r="5.5" fill="#38bdf8" stroke="#fff" stroke-width="1.2"/>'
            f'<rect x="70" y="{min(156.0, max(18.0, y_ent+7))}" width="132" height="16" rx="4" fill="rgba(15,23,42,0.92)" stroke="#38bdf8" stroke-width="1"/>'
            f'<text x="136" y="{min(167.0, max(29.0, y_ent+18))}" fill="#7dd3fc" font-size="9" font-weight="bold" text-anchor="middle">{html.escape(entry_lbl)}</text>'
            f'<circle cx="225" cy="{y_half}" r="4.5" fill="#facc15"/>'
            f'<circle cx="305" cy="{y_tp}" r="5.5" fill="#10b981" stroke="#fff" stroke-width="1.2"/>'
            f'</svg></div>'
        )
    except Exception:
        return ""

def build_intraday_svg_chart(df: pd.DataFrame, r: dict) -> str:
    try:
        if df is None or df.empty: return ""
        is_jp = ".T" in str(r.get("full_code", ""))
        fc = str(r.get("full_code", ""))
        latest_d = df["_trade_date"].iloc[-1]
        sub = df[df["_trade_date"] == latest_d].copy()
        if len(sub) < 3: sub = df.tail(40).copy()
        o, h, l, c, v = [sub[col].values.astype(float) for col in ["Open", "High", "Low", "Close", "Volume"]]
        n = len(c)
        typ_arr = (h + l + c) / 3.0
        cum_pv = np.cumsum(typ_arr * np.maximum(v, 1.0))
        cum_v = np.cumsum(np.maximum(v, 1.0))
        vwap_arr = cum_pv / cum_v
        cum_pv2 = np.cumsum((typ_arr ** 2) * np.maximum(v, 1.0))
        vwap_var_arr = np.maximum((cum_pv2 / cum_v) - (vwap_arr ** 2), 0.0)
        vwap_std_arr = np.sqrt(vwap_var_arr)
        vwap_p1_arr = vwap_arr + vwap_std_arr
        vwap_p2_arr = vwap_arr + 2.0 * vwap_std_arr

        or15_hi = float(r.get("or15_high", np.max(h[:min(3, n)])))
        or15_lo = float(r.get("or15_low", np.min(l[:min(3, n)])))
        cv = float(r.get("raw_close", c[-1]))
        tp = float(r.get("raw_tp", cv * 1.02))
        sl = float(r.get("raw_sl", cv * 0.99))
        hvn_wall = float(r.get("daily_2y", {}).get("hvn_wall_price", 0.0))
        pdh_val = float(r.get("pdh", 0.0))
        ob_sup = float(r.get("ob_support_px", 0.0))
        ob_hi = float(r.get("ob_high_px", 0.0))

        price_refs = [float(np.min(l)), float(np.max(h)), or15_hi, or15_lo, cv, tp, sl, float(np.max(vwap_p1_arr))]
        if hvn_wall > 0: price_refs.append(hvn_wall)
        if pdh_val > 0 and abs(pdh_val - cv) / max(cv, 1e-4) <= 0.08: price_refs.append(pdh_val)
        if ob_sup > 0: price_refs.append(ob_sup)
        p_min, p_max = min(price_refs) * 0.9985, max(price_refs) * 1.0015
        span = max(p_max - p_min, 1e-4)

        W, H, chart_r, vp_w = 420.0, 225.0, 325.0, 62.0
        def to_y(val): return round(200.0 - ((val - p_min) / span) * 175.0, 1)
        def to_x(idx): return round(18.0 + (idx / max(n - 1, 1)) * (chart_r - 24.0), 1)

        y_or_hi, y_or_lo = to_y(or15_hi), to_y(or15_lo)
        or_rect_y = min(y_or_hi, y_or_lo)
        or_rect_h = max(abs(y_or_lo - y_or_hi), 2.0)

        ob_band_svg = ""
        if ob_sup > 0 and p_min <= ob_sup <= p_max:
            y_ob_lo = to_y(ob_sup)
            y_ob_hi = to_y(ob_hi if (ob_hi > ob_sup and ob_hi <= p_max) else ob_sup * 1.004)
            ob_h = max(abs(y_ob_lo - y_ob_hi), 4.0)
            ob_band_svg = (
                f'<rect x="15" y="{min(y_ob_hi, y_ob_lo)}" width="{chart_r - 15}" height="{ob_h}" fill="rgba(16,185,129,0.16)" stroke="rgba(16,185,129,0.55)" stroke-width="0.8"/>'
                f'<text x="18" y="{min(212.0, max(12.0, y_ob_lo - 2))}" fill="#6ee7b7" font-size="8" font-weight="bold">🏛️ 機関OB支持帯 ({fmt_px(ob_sup, is_jp, fc)})</text>'
            )

        vp_bins = np.linspace(p_min, p_max, 13)
        vp_hist = np.bincount(np.clip(np.digitize(typ_arr, vp_bins) - 1, 0, 11), weights=np.maximum(v, 1.0), minlength=12)
        vp_max = max(float(np.max(vp_hist)), 1.0)
        vp_bars_svg = ""
        for bi in range(12):
            bw = round((float(vp_hist[bi]) / vp_max) * vp_w, 1)
            by1, by2 = to_y(vp_bins[bi + 1]), to_y(vp_bins[bi])
            bh = max(abs(by2 - by1) - 1.0, 2.0)
            vp_bars_svg += f'<rect x="{round(W - 10.0 - bw, 1)}" y="{min(by1, by2)}" width="{bw}" height="{bh}" fill="rgba(56,189,248,0.35)" stroke="rgba(56,189,248,0.6)" stroke-width="0.5"/>'

        bar_w = max(2.2, min(7.0, (chart_r - 24.0) / max(n * 1.45, 1.0)))
        candles_svg, vwap_pts, p1_pts, p2_pts = "", [], [], []
        for i in range(n):
            cx = to_x(i)
            yo, yh, yl, yc = to_y(o[i]), to_y(h[i]), to_y(l[i]), to_y(c[i])
            col = "#10b981" if c[i] >= o[i] else "#ef4444"
            candles_svg += f'<line x1="{cx}" y1="{yh}" x2="{cx}" y2="{yl}" stroke="{col}" stroke-width="1"/><rect x="{round(cx - bar_w/2, 1)}" y="{min(yo, yc)}" width="{round(bar_w, 1)}" height="{max(abs(yc - yo), 1.4)}" fill="{col}"/>'
            vwap_pts.append(f"{cx},{to_y(vwap_arr[i])}")
            p1_pts.append(f"{cx},{to_y(np.clip(vwap_p1_arr[i], p_min, p_max))}")
            p2_pts.append(f"{cx},{to_y(np.clip(vwap_p2_arr[i], p_min, p_max))}")

        y_tp, y_sl, y_cv = to_y(tp), to_y(sl), to_y(cv)
        hvn_svg = ""
        if hvn_wall > 0 and p_min <= hvn_wall <= p_max:
            yhvn = to_y(hvn_wall)
            hvn_svg = f'<line x1="15" y1="{yhvn}" x2="{chart_r}" y2="{yhvn}" stroke="#f59e0b" stroke-width="1.3" stroke-dasharray="4,2"/><text x="18" y="{max(12.0, yhvn-3)}" fill="#fde047" font-size="8.5" font-weight="bold">🧱 HVNしこり壁 ({fmt_px(hvn_wall, is_jp, fc)})</text>'

        pdh_svg = ""
        if pdh_val > 0 and p_min <= pdh_val <= p_max:
            ypdh = to_y(pdh_val)
            pdh_svg = f'<line x1="15" y1="{ypdh}" x2="{chart_r}" y2="{ypdh}" stroke="#facc15" stroke-width="1.2" stroke-dasharray="5,3"/><text x="{chart_r - 2}" y="{max(12.0, ypdh-3)}" fill="#fef08a" font-size="8" font-weight="bold" text-anchor="end">📍 PDH前日高値 ({fmt_px(pdh_val, is_jp, fc)})</text>'

        return (
            f'<div class="svg-chart-wrap">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;font-size:11px;font-weight:800;color:#38bdf8;margin-bottom:4px;">'
            f'<span>📊 当日5分足 × VWAP±1σ/2σ × OR15 × PDH × 機関OB支持帯</span>'
            f'<span style="font-size:9.5px;color:#94a3b8;">右端棒: 価格帯出来高</span></div>'
            f'<svg viewBox="0 0 {int(W)} {int(H)}" width="100%" style="max-height:230px;display:block;">'
            f'<rect x="15" y="{or_rect_y}" width="{chart_r - 15}" height="{or_rect_h}" fill="rgba(168,85,247,0.14)" stroke="rgba(168,85,247,0.4)" stroke-width="0.8" stroke-dasharray="2,2"/>'
            f'<text x="18" y="{max(11.0, or_rect_y + 9)}" fill="#d8b4fe" font-size="8">OR15帯 ({fmt_px(or15_lo, is_jp, fc)}〜{fmt_px(or15_hi, is_jp, fc)})</text>'
            f'{ob_band_svg}{vp_bars_svg}{candles_svg}'
            f'<polyline fill="none" stroke="rgba(56,189,248,0.55)" stroke-width="1.1" stroke-dasharray="3,2" points="{" ".join(p1_pts)}"/>'
            f'<polyline fill="none" stroke="rgba(244,114,182,0.55)" stroke-width="1.1" stroke-dasharray="2,2" points="{" ".join(p2_pts)}"/>'
            f'<polyline fill="none" stroke="#38bdf8" stroke-width="1.8" points="{" ".join(vwap_pts)}"/>'
            f'{hvn_svg}{pdh_svg}'
            f'<line x1="15" y1="{y_tp}" x2="{chart_r}" y2="{y_tp}" stroke="#10b981" stroke-width="1.2" stroke-dasharray="4,2"/>'
            f'<text x="{chart_r - 2}" y="{max(11.0, y_tp - 2)}" fill="#6ee7b7" font-size="8.5" font-weight="bold" text-anchor="end">TP {fmt_px(tp, is_jp, fc)}</text>'
            f'<line x1="15" y1="{y_sl}" x2="{chart_r}" y2="{y_sl}" stroke="#ef4444" stroke-width="1.2" stroke-dasharray="4,2"/>'
            f'<text x="{chart_r - 2}" y="{min(218.0, y_sl + 9)}" fill="#fca5a5" font-size="8.5" font-weight="bold" text-anchor="end">SL {fmt_px(sl, is_jp, fc)}</text>'
            f'<line x1="15" y1="{y_cv}" x2="{chart_r}" y2="{y_cv}" stroke="#f8fafc" stroke-width="0.9" stroke-dasharray="2,2"/>'
            f'</svg></div>'
        )
    except Exception:
        return ""

def _build_equity_and_session_html(hist_rows: list, is_jp: bool) -> str:
    traded = [x for x in reversed(hist_rows) if x.get("result_category") != "NOTRADE"]
    if not traded:
        return ""
    cum_vals = [0.0]
    acc = 0.0
    for tr in traded:
        acc += float(tr.get("return_pct", 0.0))
        cum_vals.append(round(acc, 2))
    c_min, c_max = min(cum_vals), max(cum_vals)
    span = max(c_max - c_min, 0.5)
    W, H = 340.0, 68.0
    pts = []
    for idx, val in enumerate(cum_vals):
        px = round(10.0 + (idx / max(len(cum_vals) - 1, 1)) * (W - 20.0), 1)
        py = round(56.0 - ((val - c_min) / span) * 44.0, 1)
        pts.append(f"{px},{py}")
    y_zero = round(56.0 - ((0.0 - c_min) / span) * 44.0, 1)
    line_col = "#10b981" if cum_vals[-1] >= 0 else "#ef4444"
    eq_svg = (
        f'<svg viewBox="0 0 {int(W)} {int(H)}" width="100%" style="max-height:72px;display:block;">'
        f'<line x1="10" y1="{y_zero}" x2="{int(W-10)}" y2="{y_zero}" stroke="rgba(148,163,184,0.35)" stroke-width="1" stroke-dasharray="3,2"/>'
        f'<polyline fill="none" stroke="{line_col}" stroke-width="2.2" points="{" ".join(pts)}"/>'
        f'<text x="12" y="12" fill="#94a3b8" font-size="8.5">累積リターン推移 ({len(traded)}戦)</text>'
        f'<text x="{int(W-12)}" y="12" fill="{line_col}" font-size="9.5" font-weight="bold" text-anchor="end">{cum_vals[-1]:+.2f}%</text>'
        f'</svg>'
    )

    buckets = {"前場初動 9:05-9:30": [0, 0], "前場トレンド 9:30-11:30": [0, 0], "後場 12:30-14:30": [0, 0]}
    for tr in traded:
        hm = str(tr.get("entry_hm", ""))
        rcat = tr.get("result_category", "")
        if rcat not in ("WIN", "LOSE"): continue
        b_key = "前場トレンド 9:30-11:30"
        if ":" in hm:
            try:
                hh, mm = [int(p) for p in hm.split(":")[:2]]
                mins = hh * 60 + mm
                if mins < 9 * 60 + 30: b_key = "前場初動 9:05-9:30"
                elif mins < 12 * 60: b_key = "前場トレンド 9:30-11:30"
                else: b_key = "後場 12:30-14:30"
            except Exception: pass
        buckets[b_key][1] += 1
        if rcat == "WIN": buckets[b_key][0] += 1

    sess_pills = ""
    for lbl, (w_n, tot_n) in buckets.items():
        wr_s = f"{(w_n / tot_n * 100.0):.0f}%" if tot_n > 0 else "-"
        col_s = "#6ee7b7" if (tot_n > 0 and (w_n / tot_n) >= 0.5) else "#cbd5e1"
        sess_pills += f'<div style="background:rgba(15,23,42,0.85);border:1px solid rgba(56,189,248,0.22);border-radius:6px;padding:4px 6px;text-align:center;"><div style="font-size:9px;color:#94a3b8;">{lbl}</div><div style="font-size:11px;font-weight:800;color:{col_s};">{tot_n}戦 / 勝率 {wr_s}</div></div>'

    return (
        f'<div style="background:rgba(15,23,42,0.65);border:1px solid rgba(56,189,248,0.25);border-radius:8px;padding:7px 9px;margin-bottom:7px;">'
        f'{eq_svg}'
        f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin-top:5px;">{sess_pills}</div>'
        f'</div>'
    )

def build_instant_verdict_html(r: dict) -> str:
    r_m = _merge_dd_intel_into_lab_item(r)
    has_dd = bool(r_m.get("has_dd_intel"))
    dd_i = r_m.get("dd_intel", {})
    ft = r_m.get("forward_test", {}); hist_rows = ft.get("history_rows", []); is_jp = ".T" in r_m.get("full_code", ""); is_short = (r_m.get("strat", {}).get("side") == "SHORT")
    fc = str(r_m.get("full_code", ""))
    m10 = r_m.get("macro_10y", {}); d2y = r_m.get("daily_2y", {})
    verified_span_days = int(ft.get("verified_span_days", len(hist_rows)))
    cv = float(r_m.get("raw_close", 0.0))
    tp_v = float(r_m.get("raw_tp", cv))
    sl_v = float(r_m.get("raw_sl", cv))
    vwap_v = float(r_m.get("raw_vwap", cv))
    sh_cnt = int(r_m.get("lot_info", {}).get("shares", 100))
    half_sh = max(1, int(round(sh_cnt * 0.5)))

    if is_short:
        side_order_lbl = f"{'信用新規売り' if is_jp else 'SHORT売り'} {sh_cnt:,}株"
        base_ent = float(dd_i.get("fusion_entry_px") or dd_i.get("peak_px") or (max(cv, vwap_v) if vwap_v > 0 else cv)) if has_dd else (max(cv, vwap_v) if vwap_v > 0 else cv)
        entry_ref_px = round_to_tse_tick(base_ent, fc, "nearest")
        half_r_px = round_to_tse_tick(float(dd_i.get("fusion_half_r_px") or (entry_ref_px - abs(sl_v - entry_ref_px))) if has_dd else (entry_ref_px - abs(sl_v - entry_ref_px)), fc, "floor")
    else:
        side_order_lbl = f"{'現物/信用買い' if is_jp else 'LONG買い'} {sh_cnt:,}株"
        base_ent = float(dd_i.get("fusion_entry_px") or dd_i.get("dip_px") or (min(cv, vwap_v) if vwap_v > 0 else cv)) if has_dd else (min(cv, vwap_v) if vwap_v > 0 else cv)
        entry_ref_px = round_to_tse_tick(base_ent, fc, "nearest")
        if entry_ref_px <= sl_v and cv > sl_v:
            entry_ref_px = round_to_tse_tick(cv, fc, "nearest")
        half_r_px = round_to_tse_tick(float(dd_i.get("fusion_half_r_px") or (entry_ref_px + abs(entry_ref_px - sl_v))) if has_dd else (entry_ref_px + abs(entry_ref_px - sl_v)), fc, "ceil")

    dd_oco_cells = ""
    if has_dd:
        s3 = dd_i.get("short_3way", {})
        target_tm = dd_i.get("peak_time", "-") if is_short else dd_i.get("dip_time", "-")
        target_px_s = fmt_px(float(dd_i.get("peak_px") if is_short else dd_i.get("dip_px")), is_jp, fc)
        exp_warn_txt = f"🚨 {dd_i.get('expansion_label','通常')}" if dd_i.get("expansion_active") else f"CVD: {dd_i.get('cvd_label','-')}"
        dd_oco_cells = (
            f'<div class="order-ticket-cell" style="border-color:rgba(249,115,22,0.45);"><div style="font-size:9.5px;color:#fdba74;">🕒 DD{"戻り" if is_short else "押し目"}候補時刻</div><div style="font-size:11.5px;font-weight:800;color:#fed7aa;">{html.escape(target_tm)} ({target_px_s})</div></div>'
            f'<div class="order-ticket-cell" style="border-color:rgba(249,115,22,0.45);"><div style="font-size:9.5px;color:#fdba74;">⚡ DD想定大引け＆3分岐</div><div style="font-size:11px;font-weight:800;color:#7dd3fc;">{fmt_px(float(dd_i.get("est_close_px",cv)), is_jp, fc)} ({float(dd_i.get("est_close_chg",0)):+.2f}%) ▲{s3.get("p_up",33)}%/▼{s3.get("p_down",33)}%</div></div>'
            f'<div class="order-ticket-cell" style="border-color:rgba(249,115,22,0.45);"><div style="font-size:9.5px;color:#fdba74;">🛡️ DDブレイク・CVD警戒</div><div style="font-size:11px;font-weight:800;color:#fde047;">{html.escape(exp_warn_txt)}</div></div>'
        )

    order_ticket_html = (
        f'<div class="order-ticket-box">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:4px;">'
        f'<span style="font-size:12.5px;font-weight:900;color:#38bdf8;">📱 スマホ証券アプリ即発注用・OCOオーダーチケットBOX</span>'
        f'<span style="font-size:10px;color:#fde047;font-weight:700;">{"🔥 LAB×DD統合連動済" if has_dd else "東証呼値丸め済・逆指値同時セット推奨"}</span>'
        f'</div>'
        f'<div class="order-ticket-grid">'
        f'<div class="order-ticket-cell"><div style="font-size:9.5px;color:#94a3b8;">① 売買方向 ＆ 推奨株数</div><div style="font-size:12px;font-weight:900;color:{"#fb7185" if is_short else "#6ee7b7"};">{html.escape(side_order_lbl)}</div></div>'
        f'<div class="order-ticket-cell"><div style="font-size:9.5px;color:#94a3b8;">② 推奨エントリー目安</div><div style="font-size:12px;font-weight:800;color:#f8fafc;">{fmt_px(entry_ref_px, is_jp, fc)} 付近</div></div>'
        f'<div class="order-ticket-cell"><div style="font-size:9.5px;color:#fde047;">③ +1.0R 半分利確ライン</div><div style="font-size:12px;font-weight:800;color:#fde047;">{fmt_px(half_r_px, is_jp, fc)} ({half_sh:,}株利確)</div></div>'
        f'<div class="order-ticket-cell"><div style="font-size:9.5px;color:#10b981;">④ 最終利確目標 (TP指値)</div><div style="font-size:12px;font-weight:900;color:#10b981;">{r_m.get("tp_price", "-")}</div></div>'
        f'<div class="order-ticket-cell"><div style="font-size:9.5px;color:#ef4444;">⑤ 必須・損切り逆指値 (SL)</div><div style="font-size:12px;font-weight:900;color:#ef4444;">{r_m.get("sl_price", "-")}</div></div>'
        f'{dd_oco_cells}'
        f'</div></div>'
    )

    table_rows_html = ""
    for hr in hist_rows:
        res_cat = hr.get("result_category") or ("WIN" if hr.get("is_win") is True else ("LOSE" if hr.get("is_win") is False else "NOTRADE"))
        res_color = "#10b981" if res_cat == "WIN" else ("#ef4444" if res_cat == "LOSE" else ("#fde047" if res_cat == "SCRATCH" else "#94a3b8"))
        ret_v, prof_v = float(hr.get("return_pct", 0.0)), float(hr.get("profit_val", 0.0))
        ret_s = "-" if res_cat == "NOTRADE" else f"{'+' if ret_v >= 0 else ''}{ret_v:.2f}%"
        prof_s = "未約定" if res_cat == "NOTRADE" else (f"{'+' if prof_v >= 0 else ''}{prof_v:,.0f}円" if is_jp else f"{'+' if prof_v >= 0 else ''}${prof_v:,.2f}")
        hold_days = int(hr.get("hold_days", 1))
        ehm = str(hr.get("entry_hm", ""))
        hm_tag = f" {ehm}" if (res_cat != "NOTRADE" and ehm and ehm != "-") else ""
        date_disp = f"{hr.get('date', '-')}{hm_tag} ({hold_days}日保有)" if (res_cat != "NOTRADE" and hold_days > 1) else f"{hr.get('date', '-')}{hm_tag}"
        table_rows_html += f"<tr><td>{html.escape(date_disp)}</td><td style='color:#38bdf8;'>{html.escape(str(hr.get('plan_short', '-')))}</td><td style='font-family:monospace;'>{html.escape(str(hr.get('entry_str', '-')))} → {html.escape(str(hr.get('exit_str', '-')))}</td><td style='color:{res_color};font-weight:800;'>{html.escape(str(hr.get('outcome', '-')))}</td><td style='color:{res_color};font-family:monospace;font-weight:800;'>{ret_s} ({prof_s})</td></tr>"
    if not table_rows_html: table_rows_html = "<tr><td colspan='5' style='text-align:center;color:#94a3b8;'>確定決済済みの市場データ蓄積後に自動検証ログが追記されます。</td></tr>"

    tot_p = float(ft.get("total_profit_yen", 0.0))
    tot_p_str = f"{'+' if tot_p >= 0 else ''}{tot_p:,.0f}円" if is_jp else f"{'+' if tot_p >= 0 else ''}${tot_p:,.2f}"
    tot_p_col = "#10b981" if tot_p >= 0 else "#ef4444"
    traded_days = int(ft.get("total_days", 0)); win_cnt = int(ft.get("win_count", 0)); lose_cnt = int(ft.get("lose_count", max(0, traded_days - win_cnt))); scratch_cnt = int(ft.get("scratch_count", 0)); notrade_cnt = int(ft.get("notrade_count", max(0, len(hist_rows) - traded_days)))
    pf_val = float(ft.get("profit_factor", 0.0)); pf_str = f"{pf_val:.2f}" if pf_val < 99.0 else "∞"
    sqn_val = float(ft.get("sqn", 0.0)); max_dd_val = float(ft.get("max_dd_pct", 0.0)); avg_r_val = float(ft.get("avg_r", 0.0))
    vp_struct_lbl = str(d2y.get("vp_struct_label", "⚖️ 標準出来高分布"))
    rs_30m_val = float(r_m.get("intraday_rs_30m", 0.0))
    tp_lbl = "🎯 空売り利確目標(買い戻し)" if is_short else "🎯 最終目標利確価格"
    sl_lbl = "🛡️ 構造的踏み上げ逆指値" if is_short else "🛡️ 構造的初期逆指値(損切)"
    tf_note = "日足マルチデイ検証" if r_m.get("strat", {}).get("tf") == "1d" else "5分足デイトレ検証"
    eq_sess_html = _build_equity_and_session_html(hist_rows, is_jp)
    forecast_svg_html = build_tomorrow_forecast_svg(r_m)

    daily2y_verdict_html = (
        f'<div style="background:rgba(14,165,233,0.14); border:1px solid rgba(14,165,233,0.42); border-radius:8px; padding:8px 11px; margin-bottom:8px; font-size:11.5px; line-height:1.65; color:#e0f2fe;">'
        f'<b>📈 日足2年中期トレンド＆価格帯別出来高(Volume Profile)診断（3階層MTF・第2層上位足基準）:</b><br>'
        f'・<b>日足レジーム:</b> <span style="color:#fde047;font-weight:800;">{html.escape(str(d2y.get("regime_1d_label", "日足中立")))}</span>（日足トレンドスコア: <b>{d2y.get("daily_trend_score", 50)}点</b> / MA並び: <b>{html.escape(str(d2y.get("ma_align_label", "MA均衡")))}</b>）<br>'
        f'・<b>上値出来高構造(1Y Volume Profile):</b> <b style="color:#6ee7b7;">{html.escape(vp_struct_lbl)}</b> ｜ <b>30分イントラデイRS先行度:</b> <b style="color:{"#34d399" if rs_30m_val>=0 else "#fb7185"};">{rs_30m_val:+.2f}%</b><br>'
        f'・<b>移動平均線・乖離:</b> MA25=<b>{html.escape(str(d2y.get("ma25_str", "-")))}</b> ({d2y.get("ma25_dev_pct", 0.0):+.1f}%) ｜ MA75=<b>{html.escape(str(d2y.get("ma75_str", "-")))}</b> ({d2y.get("ma75_dev_pct", 0.0):+.1f}%) ｜ MA200=<b>{html.escape(str(d2y.get("ma200_str", "-")))}</b><br>'
        f'・<b>モメンタム＆ボラ基準:</b> 日足MACDヒスト=<b>{d2y.get("macd_hist", 0.0):+.2f}</b> ｜ 日足RSI(14)=<b>{d2y.get("daily_rsi14", 50.0):.1f}%</b> ｜ 52週高安位置=<b>{d2y.get("pos_52w_pct", 50.0):.1f}%</b> ｜ 日足ATR14=<b>{html.escape(str(d2y.get("daily_atr14_str", "-")))}</b>'
        f'</div>'
    )
    macro10y_verdict_html = (
        f'<div style="background:rgba(168,85,247,0.14); border:1px solid rgba(168,85,247,0.42); border-radius:8px; padding:8px 11px; margin-bottom:10px; font-size:11.5px; line-height:1.65; color:#f3e8ff;">'
        f'<b>📅 過去10年週足大局アルゴリズム診断（3階層MTF・第1層大局基準）:</b><br>'
        f'・<b>10年レジーム:</b> <span style="color:#fde047;font-weight:800;">{html.escape(str(m10.get("regime_10y_label", "10年大局中立")))}</span>（10年大局スコア: <b>{m10.get("long_10y_score", 50)}点</b>）<br>'
        f'・<b>10年CAGR(年率成長率):</b> <b>{m10.get("cagr_10y", 0.0):+.1f}%</b> ｜ <b>10年レンジ高安位置:</b> <b>{m10.get("pos_10y_pct", 50.0):.1f}%</b> ｜ <b>200週移動平均乖離:</b> <b>{m10.get("ma200w_dev_pct", 0.0):+.1f}%</b><br>'
        f'・<b>10年最大出来高POC（岩盤支持/しこり帯）:</b> <b style="color:#6ee7b7;">{html.escape(str(m10.get("poc_10y_str", "-")))}</b>（{html.escape(str(m10.get("poc_relation_note", "")))}）'
        f'</div>'
    )
    forward_table_html = (
        f'<div style="background:rgba(2,6,23,0.85); border:1px solid rgba(56,189,248,0.35); border-radius:8px; padding:10px 12px; margin-top:10px;">'
        f'<div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:4px;">'
        f'<span style="font-size:12.5px; font-weight:800; color:#38bdf8;">📊 直近{verified_span_days}営業日 完全リークフリー検証（{tf_note}・次バー始値+不利1ティックスリップ・コスト {r_m.get("combat_cost_pct",0.1)}%反映）</span>'
        f'<span style="font-size:11px; color:#fde047; font-weight:700;">約定 {traded_days}戦 / 見送り {notrade_cnt}日 ｜ 実質勝率: {ft.get("actual_win_rate", 0.0):.1f}% ({win_cnt}勝{lose_cnt}敗 / 建値{scratch_cnt}件) ｜ PF: <b style="color:#38bdf8;">{pf_str}</b> ｜ SQN: <b style="color:#c084fc;">{sqn_val:.2f}</b> ｜ 平均R: <b style="color:#6ee7b7;">{avg_r_val:+.2f}R</b> ｜ 最大DD: <b style="color:#f87171;">{max_dd_val:.1f}%</b> ｜ 累計純損益: <span style="color:{tot_p_col};">{tot_p_str}</span></span>'
        f'</div>'
        f'{eq_sess_html}'
        f'<div style="font-size:10.5px; color:#94a3b8; margin-bottom:6px;">※5分足・日足・週足四本値（OHLCV）から算出した統計モデル検証ログ（未来データ参照ゼロ・+1.0R半分利確加重反映）</div>'
        f'<div class="admin-table-container" style="margin-top:4px;"><table class="admin-table">'
        f'<thead><tr><th>検証日・約定時刻</th><th>前日決定プラン</th><th>約定→50%分割決済</th><th>実測勝敗結果(±0.15R基準)</th><th>ネット損益率・純損益額</th></tr></thead>'
        f'<tbody>{table_rows_html}</tbody></table></div></div>'
    )
    return (
        f'{order_ticket_html}'
        f'<div style="background:rgba(0,0,0,0.35); border:1px solid rgba(255,255,255,0.12); border-radius:8px; padding:12px; margin-top:5px;">'
        f'{macro10y_verdict_html}{daily2y_verdict_html}'
        f'<div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:6px; text-align:center; margin-bottom:10px;">'
        f'<div style="background:rgba(16,185,129,0.15); padding:6px; border-radius:6px; border:1px solid rgba(16,185,129,0.4);"><div style="font-size:10px; color:#a7f3d0;">{tp_lbl}</div><div style="font-size:14px; font-weight:800; color:#10b981;">{r_m["tp_price"]}</div></div>'
        f'<div style="background:rgba(239,68,68,0.15); padding:6px; border-radius:6px; border:1px solid rgba(239,68,68,0.4);"><div style="font-size:10px; color:#fca5a5;">{sl_lbl}</div><div style="font-size:14px; font-weight:800; color:#ef4444;">{r_m["sl_price"]}</div></div>'
        f'<div style="background:rgba(56,189,248,0.15); padding:6px; border-radius:6px; border:1px solid rgba(56,189,248,0.4);"><div style="font-size:10px; color:#bae6fd;">⏱️ 想定保有期間</div><div style="font-size:12.5px; font-weight:800; color:#38bdf8;">{r_m["strat"]["trade_duration"]}</div></div>'
        f'</div><div style="font-size:12px; line-height:1.7; color:#e2e8f0;"><b>⚡ プロ執行アクション詳細プラン ({r_m["strat"]["style_name"]}専科 / {r_m["strat"].get("side","LONG")} / {html.escape(r_m.get("exec_grade",""))}):</b><br>{r_m["strat"]["step_plan"]}</div>'
        f'</div><div class="beginner-action-box" style="margin-top:10px;">{r_m["strat"]["beginner_html"]}{forecast_svg_html}</div>{forward_table_html}'
    )

def generate_humanlike_2ch_debate(r: dict, uq: str = "", hist: list = None) -> tuple:
    r_m = _merge_dd_intel_into_lab_item(r)
    uq = (uq or "").strip(); st_style = r_m.get("strat", {}).get("style_name", "デイトレード")
    rl = DEFAULT_AGENTS
    ig, tc, sn, ae, nx = rl["IGNIS"], rl["TECHNOS"], rl["SENTINEL"], rl["AEGIS"], rl["NEXUS"]
    h_lines = [f"ユーザー: {ht.get('text', '')}" if ht.get('is_user') else f"{re.sub(r'^[^\w]+', '', ht.get('speaker', '')).strip()}: {ht.get('text', '')}" for ht in (hist or [])[-6:] if "round" not in ht]
    h_str = "\n".join(h_lines) if h_lines else "（新規スレッド）"
    is_stk = any(kw in uq for kw in ["株", "決算", "買い", "売り", "チャート", "PTS", "利確", "損切", "寄り", "板", "気配", "PER", "目標", "相場", "信用", "空売り", "ロット", "配当"]) or (r_m['name'] in uq) if uq else True
    web_hits = (search_single_query(uq, 3, False) if not is_stk and len(uq) >= 2 else search_web_knowledge_parallel(f"{r_m['name']} {uq}", f"{r_m['code']} 株価")) if uq else search_web_knowledge_parallel(f"{r_m['name']} 株価 最新 ニュース", f"{r_m['name']} {r_m.get('genre', '')}")
    web_str = "\n".join([f"・{h}" for h in web_hits]) if web_hits else f"・{r_m['name']}は直近{r_m.get('genre', '')}分野で需給思惑が継続中。"
    m10 = r_m.get("macro_10y", {}); d2y = r_m.get("daily_2y", {})

    fc_u = str(r_m.get("full_code", "")).strip().upper()
    intel_entry = load_shared_ticker_intel().get(fc_u, {}) if fc_u else {}
    dd_res_shared = intel_entry.get("dd_result") if isinstance(intel_entry, dict) else None
    dd_summary_txt = _format_dd_shared_summary(dd_res_shared)
    dd_prompt_block = ""
    if r_m.get("has_dd_intel"):
        dd_i = r_m.get("dd_intel", {})
        s3 = dd_i.get("short_3way", {})
        dd_prompt_block = (
            f"\n【DEEP DIVE 5分足極限解析からの統合データ】\n"
            f"・同期判定: {r_m.get('dd_sync_label','')} / 統合期待度: {r_m.get('fusion_expect_pct')}% (DD単体スコア={dd_i.get('fusion_score')}%)\n"
            f"・5分足軌道: 想定始値={dd_i.get('est_open_px')} / 押し目候補={dd_i.get('dip_time')}({dd_i.get('dip_px')}) / ピーク想定={dd_i.get('peak_time')}({dd_i.get('peak_px')}) / 大引け予測={dd_i.get('est_close_px')}({dd_i.get('est_close_chg'):+.2f}%)\n"
            f"・短期30分3分岐: ▲上昇{s3.get('p_up',33)}% / ▶横ばい{s3.get('p_flat',34)}% / ▼下落{s3.get('p_down',33)}% ｜ CVD={dd_i.get('cvd_label','-')} ｜ レジーム={dd_i.get('expansion_label','通常レジーム')}"
        )

    has_api_key = bool(load_gemini_cfg().get("api_key"))
    if not has_api_key: engine_status = "⚙️ 統計ルールベース自動推論（API未接続時・週足10Y×日足2Y×5分足60D＋DD統合出力）"; llm_turns = []
    else:
        ft = r_m.get("forward_test", {}); v_days = int(ft.get("verified_span_days", len(ft.get("history_rows", []))))
        sys_p = f"""あなたはプロフェッショナル・クオンツ監査委員会の5名の専門監査官（IGNIS / TECHNOS / SENTINEL / AEGIS / NEXUS）です。対象銘柄固有の「事業テーマ」「最新ニュース」「過去10年週足大局({m10.get('regime_10y_label','')} / 10年CAGR={m10.get('cagr_10y',0):+.1f}% / 10年POC={m10.get('poc_10y_str','-')})」「日足2年中期トレンド({d2y.get('regime_1d_label','')} / {d2y.get('ma_align_label','')} / 上値出来高構造={d2y.get('vp_struct_label','')} / MA25={d2y.get('ma25_str','-')} / 日足ATR14={d2y.get('daily_atr14_str','-')})」「投資スタイル({st_style})」「売買方向({r_m['strat'].get('side','LONG')})」「実戦適格ゲート({r_m.get('exec_grade','')})」「直近{v_days}営業日リークフリー検証成績（勝率/PF/SQN/平均R/最大DD）」および「DEEP DIVE 5分足軌道・CVD・30分3分岐データ」に基づき論理的かつ簡潔に統合監査合議を行ってください。オウム返しや定型文は厳禁です。
【これまでの会話ログ】\n{h_str}\n【最新WEBニュース】\n{web_str}{dd_prompt_block}
【銘柄プロファイル】
・銘柄: {r_m['code']} {r_m['name']} ({r_m.get('combat_tier','')} / {r_m.get('exec_grade','')}) / テーマ: {r_m.get('theme','')}
・現在値: {r_m['price']} ({r_m.get('diff',0):+.2f}% / 日次RSα: {r_m.get('rs_alpha',0):+.2f}% / 30分RS: {r_m.get('intraday_rs_30m',0):+.2f}%) / 当日VWAP: {r_m['vwap_price']} / 目標: {r_m['tp_price']} / 逆指値: {r_m['sl_price']} / 戦術: {r_m['strat']['algo_name']} ({r_m['strat'].get('side','LONG')})
・第1層(週足10Y): {m10.get('regime_10y_label','')} (スコア{m10.get('long_10y_score',50)}点 / CAGR {m10.get('cagr_10y',0):+.1f}% / POC {m10.get('poc_10y_str','-')})
・第2層(日足2Y): {d2y.get('regime_1d_label','')} (スコア{d2y.get('daily_trend_score',50)}点 / {d2y.get('ma_align_label','')} / 出来高構造={d2y.get('vp_struct_label','')})
・第3層(5分足60D): RSI={r_m.get('rsi',50)}% / 時間帯補正RVOL={r_m.get('rvol',1.0)}倍 / 確定実質勝率: {ft.get('actual_win_rate',0):.1f}% ({ft.get('win_count',0)}勝{ft.get('lose_count',0)}敗 / PF={ft.get('profit_factor',0):.2f} / SQN={ft.get('sqn',0):.2f} / 平均R={ft.get('avg_r',0):+.2f}R / 最大DD={ft.get('max_dd_pct',0):.1f}%) 累計純損益: {ft.get('total_profit_yen',0):+,.0f}円
以下のJSON配列のみを出力（5名）：[{{"speaker": "アイコン 名前", "role_label": "専門スタンス", "tone": "agree|doubt|rage|normal", "text": "内容"}}]"""
        r_name = r_m["name"]
        user_msg = f"【今回の入力】\n『{uq if uq else f'（{r_name}のLAB上位足分析とDEEP DIVE 5分足軌道・CVD・3分岐データを統合した最終売買監査合議）'}』"
        raw_txt, used_mod = call_real_llm_api(sys_p, user_msg, expect_json=True)
        llm_turns = _parse_llm_json_turns(raw_txt)
        engine_status = f"🔵 Gemini AI生成クオンツ監査合議（稼働モデル: {GEMINI_MODEL_DISPLAY_NAMES.get(used_mod, used_mod)}）" if llm_turns else "⚙️ 統計ルールベース自動推論（API未接続/応答フォールバック時）"

    turns = []
    if not hist:
        header_tag = "🔥 Gemini AI クオンツ監査合議" if llm_turns else "⚙️ 統計ルールベース自動推論（API未接続時）"
        turns.append({"round": f"{header_tag} 【{r_m['code']}】{r_m['name']} ｜ {st_style} 3階層MTF＋DD統合監査"})
    turns.extend(llm_turns if llm_turns else _build_natural_fallback_dialogue(uq, r_m, st_style, web_hits, ig, tc, sn, nx, ae, dd_summary=dd_summary_txt))
    turns = sanitize_and_verify_dialogue(turns, r_m, uq=uq)
    rel_news_for_sync = [n for n in all_impact_news if r_m.get("full_code") in n.get("detail", {}).get("related_codes", [])]
    sync_lab_intel_to_shared(r_m, council_turns=turns, rel_news_list=rel_news_for_sync, persist=True)
    return turns, engine_status

def run_gemini_council(r: dict, m5=None, seed: int = 0, uq: str = "", hist: list = None) -> dict:
    turns, engine_status = generate_humanlike_2ch_debate(r, uq, hist)
    return {"final_score": r["ai_score"], "dialogue": turns, "verdict_html": build_instant_verdict_html(r), "engine_status": engine_status}

def _fmt_turn(t: dict, idx: int = 0) -> str:
    if "round" in t: return f'<div class="round-divider">{html.escape(t["round"])}</div>'
    if t.get("is_user"):
        d_id = f' id="{html.escape(t.get("dom_id", ""))}"' if t.get("dom_id") else ""
        return f'<div class="chat-bubble-user"{d_id}><div style="font-weight:800;color:#38bdf8;font-size:11.5px;margin-bottom:3px;">🗣️ あなたの質問・投下レス:</div><div style="color:#ffffff;font-size:12.5px;font-weight:600;">{html.escape(t["text"])}</div></div>'
    b_cls = {"doubt": "chat-bubble-doubt", "rage": "chat-bubble-rage", "agree": "chat-bubble-agree"}.get(t.get("tone", "normal"), "chat-bubble-ai")
    role_lbl = t.get("role_label") or {"agree": "強気・追随スタンス", "doubt": "慎重・リスク警戒", "rage": "過熱・空売り警鐘スタンス"}.get(t.get("tone", "normal"), "多角分析スタンス")
    return f'<div class="{b_cls}"><div style="font-weight:700;color:#38bdf8;font-size:11px;margin-bottom:2px;">{html.escape(t["speaker"])} <span style="color:#94a3b8;font-size:10px;">[{html.escape(role_lbl)}]</span></div><div>{html.escape(t["text"])}</div></div>'

def _app_rerun():
    try:
        st.rerun(scope="app")
    except TypeError:
        st.rerun()

def _render_council_sec_impl(r, uk, auto_open=False):
    is_open = auto_open or st.session_state["active_debates"].get(uk, False)
    if not is_open: return

    side_title = "空売り(SHORT)" if r.get("strat", {}).get("side") == "SHORT" else "順張り買い(LONG)"
    st.markdown(f'<div class="consensus-banner"><div style="font-weight:800;color:#fde047;font-size:13px;margin-bottom:6px;">🏛️ 最終結論 ＆ プロ推奨{side_title}アクションプラン（{r["strat"]["style_name"]}専科）</div>{build_instant_verdict_html(r)}</div>', unsafe_allow_html=True)
    ck = f"{uk}_{r.get('strat', {}).get('style_name', 'default')}"
    if ck not in st.session_state["council_threads"]:
        with st.spinner("🔵 5名のクオンツ監査官がリアルタイム合議を生成中..."):
            deb = run_gemini_council(r, None, 0, "", hist=[])
            st.session_state["council_threads"][ck], st.session_state["council_meta"][ck] = deb["dialogue"], deb

    meta, turns = st.session_state["council_meta"][ck], st.session_state["council_threads"][ck]
    eng_st = meta.get("engine_status", "⚙️ 統計ルールベース自動推論（API未接続時）")
    pill_style = "" if "Gemini AI生成" in eng_st else ' style="background:rgba(245,158,11,0.14);border-color:rgba(245,158,11,0.45);color:#fde047;"'
    st.markdown(f'<div class="ai-council-box" id="box_{uk}"><div class="ai-engine-status-pill"{pill_style}>{html.escape(eng_st)}</div><div class="council-scroll-window" id="scroll_window_{uk}">{"".join(_fmt_turn(t, i) for i, t in enumerate(turns))}</div></div>', unsafe_allow_html=True)

    with st.form(f"form_q_{uk}", clear_on_submit=True):
        jc1, jc2 = st.columns([3.2, 1])
        uop = jc1.text_input("質問・発言", placeholder=f"『{r['name']}』への質問・相談・追加の視点リクエスト", label_visibility="collapsed")
        if jc2.form_submit_button("💬 質問投下", use_container_width=True) and uop.strip():
            ut, nid = uop.strip(), f"user_q_anchor_{uk}_{int(time.time()*1000)}"
            cur_t = list(st.session_state["council_threads"][ck])
            st.session_state["council_threads"][ck].append({"is_user": True, "text": ut, "dom_id": nid})
            with st.spinner("🔵 5名のクオンツ監査官が追加合議を生成中..."):
                deb_u = run_gemini_council(r, None, 0, uq=ut, hist=cur_t)
            for nt in deb_u["dialogue"]: st.session_state["council_threads"][ck].append(nt)
            st.session_state["council_meta"][ck] = deb_u; st.session_state["scroll_target_id"] = nid; st.rerun()

    if auto_open and not st.session_state.get("custom_search_code"):
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("⬅️ 一覧に戻る (他の銘柄を見る)", key=f"btn_back_bottom_{uk}", use_container_width=True, type="primary"):
            st.session_state["focused_stock_item"] = None; st.session_state["scroll_top_trig"] = int(time.time() * 1000); _app_rerun()

if hasattr(st, "fragment"):
    render_council_sec = st.fragment(_render_council_sec_impl)
else:
    render_council_sec = _render_council_sec_impl

# =========================================================================
# スッキリ3層構造 銘柄カード（情報量100%保持・プロ端末レイアウト）
# =========================================================================
def render_card(r, is_custom=False, rank=None, kp="card", is_focused=False, extra_origin_badge: str = "", intraday_df: pd.DataFrame = None):
    r_m = _merge_dd_intel_into_lab_item(r)
    has_dd = bool(r_m.get("has_dd_intel"))
    dd_i = r_m.get("dd_intel", {})
    rel_news_list = [n for n in all_impact_news if r_m["full_code"] in n["detail"]["related_codes"]]
    rel_news = rel_news_list[0] if rel_news_list else None
    fc_card = str(r_m.get("full_code", "")).strip().upper()
    is_jp = ".T" in fc_card

    dc, ds = ("#10b981" if r_m["diff"] >= 0 else "#ef4444"), ("+" if r_m["diff"] > 0 else "")
    lot, st_info = r_m["lot_info"], r_m["strat"]
    is_short_card = (st_info.get("side") == "SHORT")
    spec = get_style_spec(st_info.get("style_name", "デイトレード"))
    is_long_only_guard = (not spec["allow_short"]) or is_jp_tier3_short_restricted(fc_card, r_m.get("genre", ""))

    # 上段コアバッジ（最大4〜5個の重要バッジのみ表示）
    rk_h = f'<span class="pill-badge" style="background:#f59e0b;color:#0f172a;border:none;font-weight:900;">#{rank}</span>' if rank else ""
    side_badge = '<span class="pill-badge" style="background:rgba(225,29,72,0.25);border-color:#fb7185;color:#fecdd3;font-weight:900;">SHORT</span>' if is_short_card else '<span class="pill-badge" style="background:rgba(16,185,129,0.2);border-color:#34d399;color:#a7f3d0;font-weight:900;">LONG</span>'
    exec_grade = str(r_m.get("exec_grade", "🔵 Grade-B: 標準執行（基準厳守）"))
    exec_score = int(r_m.get("exec_score", 3))
    exec_badge_style = "background:rgba(16,185,129,0.22);border-color:#10b981;color:#6ee7b7;font-weight:900;" if exec_score >= 4 else ("background:rgba(56,189,248,0.20);border-color:#38bdf8;color:#7dd3fc;font-weight:800;" if exec_score == 3 else "background:rgba(245,158,11,0.22);border-color:#f59e0b;color:#fde047;font-weight:800;")
    exec_badge_html = f'<span class="pill-badge" style="{exec_badge_style}">{html.escape(exec_grade.split("（")[0].split(": ")[0])}</span>'
    dd_badge_html = '<span class="pill-badge" style="background:rgba(249,115,22,0.25);border-color:#f97316;color:#fdba74;font-weight:900;">🔥 DD統合済</span>' if has_dd else ""
    new_badge = '<span class="pill-badge" style="background:rgba(16,185,129,0.2);border-color:#10b981;color:#6ee7b7;font-weight:800;">🆕 NEW</span>' if r_m.get("is_new_challenger") else ""

    # 警告系バッジ（発火時のみ簡潔表示）
    warn_badges = ""
    earnings_days = r_m.get("earnings_days_left")
    if earnings_days is not None and 0 <= int(earnings_days) <= 3:
        warn_badges += f'<span class="pill-badge" style="background:rgba(239,68,68,0.25);border-color:#ef4444;color:#fca5a5;font-weight:900;">⚠️決算{int(earnings_days)}日</span>'
    if bool(r_m.get("vwap_over_2sigma", False)) and not is_short_card:
        warn_badges += '<span class="pill-badge" style="background:rgba(244,63,94,0.25);border-color:#fb7185;color:#fecdd3;font-weight:900;">⚠️+2σ過熱</span>'
    if bool(r_m.get("limit_up_tight", False)) and not is_short_card:
        warn_badges += '<span class="pill-badge" style="background:rgba(245,158,11,0.28);border-color:#f59e0b;color:#fde047;font-weight:900;">⚠️S高接近</span>'

    # 期待度表示（DD統合時は Fusion XX%、未統合時は LAB XX%）
    disp_expect = r_m["fusion_expect_pct"] if has_dd else r_m["expect_pct"]
    expect_lbl_top = "FUSION EXPECT" if has_dd else "LAB EXPECT"
    sync_sub_html = f'<div style="font-size:9.5px;font-weight:800;color:{"#6ee7b7" if r_m.get("dd_sync_ok") else "#fde047"};margin-top:2px;">{html.escape(r_m.get("dd_sync_label",""))}</div>' if has_dd else ""

    # エントリー目安（DD押し目/戻り時刻があれば併記）
    cv = float(r_m.get("raw_close", 0.0))
    vwap_v = float(r_m.get("raw_vwap", cv))
    if has_dd:
        ent_px_val = float(dd_i.get("fusion_entry_px") or (dd_i.get("peak_px") if is_short_card else dd_i.get("dip_px")) or cv)
        ent_tm_hint = f" ({dd_i.get('peak_time','-')})" if is_short_card else f" ({dd_i.get('dip_time','-')})"
        ent_disp = f"{fmt_px(ent_px_val, is_jp, fc_card)}{ent_tm_hint}"
    else:
        ent_px_val = round_to_tse_tick(max(cv, vwap_v) if is_short_card else (min(cv, vwap_v) if vwap_v > 0 else cv), fc_card, "nearest")
        ent_disp = f"{fmt_px(ent_px_val, is_jp, fc_card)} 付近"

    tp_sign_c = "+" if r_m["tp_pct"] > 0 else ""; sl_sign_c = "+" if r_m["sl_pct"] > 0 else ""
    odd_lot_tag = " (S株)" if lot.get("is_odd_lot") else ""

    # リークフリー検証1行バー
    ft = r_m.get("forward_test", {})
    w_cnt, l_cnt, t_days = int(ft.get("win_count", 0)), int(ft.get("lose_count", 0)), int(ft.get("total_days", 0))
    pf_val = float(ft.get("profit_factor", 0.0)); pf_str = f"{pf_val:.2f}" if pf_val < 99.0 else "∞"
    sqn_val = float(ft.get("sqn", 0.0))
    tot_p = float(ft.get("total_profit_yen", 0.0))
    tot_p_str = f"{'+' if tot_p >= 0 else ''}{tot_p:,.0f}円" if is_jp else f"{'+' if tot_p >= 0 else ''}${tot_p:,.2f}"
    tot_p_col = "#10b981" if tot_p >= 0 else "#ef4444"

    # 詳細ドロワー内用データ
    m10 = r_m.get("macro_10y", {}); d2y = r_m.get("daily_2y", {})
    vp_struct_lbl = str(d2y.get("vp_struct_label", "⚖️ 標準出来高分布"))
    rs_30m_v = float(r_m.get("intraday_rs_30m", 0.0))
    pdh_s = fmt_px(float(r_m.get("pdh", 0.0)), is_jp, fc_card) if float(r_m.get("pdh", 0.0)) > 0 else "-"
    pdl_s = fmt_px(float(r_m.get("pdl", 0.0)), is_jp, fc_card) if float(r_m.get("pdl", 0.0)) > 0 else "-"
    vp2_s = fmt_px(float(r_m.get("vwap_p2", 0.0)), is_jp, fc_card) if float(r_m.get("vwap_p2", 0.0)) > 0 else "-"
    ob_s = fmt_px(float(r_m.get("ob_support_px", 0.0)), is_jp, fc_card) if float(r_m.get("ob_support_px", 0.0)) > 0 else "未検出"
    lim_up_s = fmt_px(float(r_m.get("limit_up_px", 0.0)), is_jp, fc_card) if (is_jp and float(r_m.get("limit_up_px", 0.0)) > 0) else "制限なし"
    session_reg = get_tse_session_regime()
    dd_drawer_html = ""
    if has_dd:
        s3 = dd_i.get("short_3way", {})
        dd_drawer_html = (
            f'<div style="background:rgba(249,115,22,0.12);border:1px solid rgba(249,115,22,0.4);border-radius:6px;padding:6px 8px;margin-bottom:6px;color:#fed7aa;">'
            f'🔥 <b>DEEP DIVE 5分足連動サマリー ({html.escape(r_m.get("dd_updated_at",""))}):</b> '
            f'想定始値={fmt_px(float(dd_i.get("est_open_px",cv)), is_jp, fc_card)} ｜ 押目={html.escape(dd_i.get("dip_time","-"))}({fmt_px(float(dd_i.get("dip_px",cv)), is_jp, fc_card)}) ｜ 高値={html.escape(dd_i.get("peak_time","-"))}({fmt_px(float(dd_i.get("peak_px",cv)), is_jp, fc_card)}) ｜ 大引け予測={fmt_px(float(dd_i.get("est_close_px",cv)), is_jp, fc_card)} ({float(dd_i.get("est_close_chg",0)):+.2f}%) ｜ 30分3分岐=▲{s3.get("p_up",33)}%/▶{s3.get("p_flat",34)}%/▼{s3.get("p_down",33)}% ｜ CVD={html.escape(dd_i.get("cvd_label","-"))}'
            f'</div>'
        )

    n_banner = f'<div style="margin-top:6px;"><span style="display:inline-block;width:100%;text-align:center;background:linear-gradient(90deg,#b91c1c 0%,#ef4444 50%,#b91c1c 100%);color:#ffffff;font-weight:800;font-size:11px;padding:4px 8px;border-radius:6px;border:1px solid #fca5a5;">🚨【速報】{html.escape(rel_news["title"][:34] + "..." if len(rel_news["title"]) > 34 else rel_news["title"])}</span></div>' if rel_news else ""
    intraday_svg_block = build_intraday_svg_chart(intraday_df, r_m) if (is_focused or is_custom) and intraday_df is not None else ""

    disp_name = html.escape(str(r_m.get("name", r_m["code"])))
    disp_code = html.escape(str(r_m["code"]))

    st.markdown(
        f'<div class="{"search-result-card" if is_custom else "rank-card"}">'
        f'<div class="card-top-meta">'
        f'<div>{rk_h}{side_badge}{exec_badge_html}{dd_badge_html}{extra_origin_badge}{new_badge}{warn_badges}</div>'
        f'<span style="font-size:10px;color:#94a3b8;font-family:\'JetBrains Mono\',monospace;">{html.escape(r_m["genre"])} ｜ {html.escape(st_info["tactic_type"])}</span>'
        f'</div>'
        f'<div class="card-hero-row">'
        f'<div style="min-width:0;flex:1;">'
        f'<div style="font-size:16.5px;font-weight:800;color:#f8fafc;line-height:1.25;">{disp_name} <span style="font-size:11.5px;color:#38bdf8;font-family:\'JetBrains Mono\',monospace;">[{disp_code}]</span></div>'
        f'<div style="font-size:11px;color:#94a3b8;margin-top:2px;">{html.escape(r_m["theme"])}</div>'
        f'<div style="font-size:11.5px;color:#e2e8f0;margin-top:4px;font-family:\'JetBrains Mono\',monospace;">現在値: <b>{r_m["price"]}</b> (<span style="color:{dc};font-weight:800;">{ds}{r_m["diff"]}%</span>) ｜ VWAP: <b>{r_m["vwap_price"]}</b></div>'
        f'{sync_sub_html}'
        f'</div>'
        f'<div class="card-kpi-right">'
        f'<div style="font-size:9px;color:#fde047;font-weight:800;letter-spacing:0.5px;">{expect_lbl_top}</div>'
        f'<div><span class="expect-badge">{disp_expect}%</span></div>'
        f'<div style="font-size:10px;color:#94a3b8;">テク強度 <span class="prob-badge" style="font-size:11.5px;">{r_m["total_win_rate"]}pt</span></div>'
        f'</div></div>'
        f'{n_banner}{intraday_svg_block}'
        f'<div class="card-action-grid">'
        f'<div class="card-action-cell"><div class="card-action-lbl">① エントリー目安</div><div class="card-action-val" style="color:#38bdf8;">{html.escape(ent_disp)}</div></div>'
        f'<div class="card-action-cell"><div class="card-action-lbl">② 最終利確 TP</div><div class="card-action-val" style="color:#10b981;">{r_m["tp_price"]} ({tp_sign_c}{r_m["tp_pct"]}%)</div></div>'
        f'<div class="card-action-cell"><div class="card-action-lbl">③ 厳格逆指値 SL</div><div class="card-action-val" style="color:#ef4444;">{r_m["sl_price"]} ({sl_sign_c}{r_m["sl_pct"]}%)</div></div>'
        f'<div class="card-action-cell"><div class="card-action-lbl">④ 推奨ロット</div><div class="card-action-val" style="color:#f8fafc;">{lot["shares"]:,}株{odd_lot_tag}</div></div>'
        f'</div>'
        f'<div class="card-perf-strip">'
        f'<span>📊 検証22D: 勝率 <b style="color:#fde047;">{ft.get("actual_win_rate",0.0):.1f}%</b> ({w_cnt}勝{l_cnt}敗)</span>'
        f'<span>PF <b style="color:#38bdf8;">{pf_str}</b> ｜ SQN <b style="color:#c084fc;">{sqn_val:.2f}</b> ｜ 累計 <b style="color:{tot_p_col};">{tot_p_str}</b></span>'
        f'</div>'
        f'<details class="quant-detail-drawer"><summary>📂 3階層MTF・東証プロファイル・全クオンツ指標を展開</summary>'
        f'<div style="font-size:11px;color:#cbd5e1;margin-top:6px;line-height:1.6;">'
        f'{dd_drawer_html}'
        f'<b>■ 10年週足大局:</b> {html.escape(str(m10.get("regime_10y_label", "")))} (スコア{int(m10.get("long_10y_score", 50))}点 / CAGR={m10.get("cagr_10y", 0.0):+.1f}% / 10年POC={html.escape(str(m10.get("poc_10y_str", "-")))})<br>'
        f'<b>■ 日足2年中期:</b> {html.escape(str(d2y.get("regime_1d_label", "")))} ({html.escape(str(d2y.get("ma_align_label", "")))} / {html.escape(vp_struct_lbl)} / MA25乖離={d2y.get("ma25_dev_pct", 0.0):+.1f}% / ATR14={html.escape(str(d2y.get("daily_atr14_str", "-")))})<br>'
        f'<b>■ 執行プロファイル:</b> {html.escape(exec_grade)} ｜ {html.escape(str(r_m.get("combat_tier","")))} (コスト{r_m.get("combat_cost_pct",0.08):.2f}%) ｜ {html.escape(session_reg["label"])}<br>'
        f'<b>■ 重要節目ガード:</b> PDH=<b>{pdh_s}</b> / PDL=<b>{pdl_s}</b> / VWAP+2σ=<b>{vp2_s}</b> / 機関OB=<b>{ob_s}</b> / S高上限=<b>{lim_up_s}</b><br>'
        f'<b>■ 全クオンツ指標:</b> WKB突破率=<b>{r_m["q_tunnel"]}%</b> / Kyle吸収率=<b>{r_m["kyle_stealth"]}%</b> / VPIN=<b>{r_m["vpin"]}</b> / CLVフローZ=<b>{r_m["ofi_z"]}</b> / Hurst=<b>{r_m["hurst"]}</b> / RSI=<b>{r_m["rsi"]}%</b> / 時間帯RVOL=<b>{r_m["rvol"]}x</b> / 30分RS=<b>{rs_30m_v:+.2f}%</b> / Kelly=<b>{r_m["kelly_pct"]}%</b>'
        f'</div></details></div>',
        unsafe_allow_html=True
    )

    # 横並びコンパクト・アクションバー（2×2グリッド配置で縦幅を圧縮）
    uk_card = f"foc_{r_m['code']}" if (is_focused or is_custom) else f"{kp}_{r_m['code']}"
    is_open_now = bool(is_focused or is_custom or st.session_state["active_debates"].get(uk_card, False))
    b_col1, b_col2 = st.columns(2)
    with b_col1:
        if not (is_focused or is_custom):
            g_lbl = "🔼 ガイドを閉じる" if is_open_now else ("🔴 空売りガイド・合議" if is_short_card else "🔵 売買ガイド・合議")
            if st.button(g_lbl, key=f"btn_open_{uk_card}", use_container_width=True, type="primary"):
                st.session_state["focused_stock_item"] = r_m
                st.session_state["scroll_top_trig"] = int(time.time() * 1000)
                _app_rerun()
        else:
            if rel_news and st.button("🚨 速報ニュース解説", key=f"nb_{kp}_{r_m['code']}", use_container_width=True):
                st.session_state["selected_news_item"] = rel_news
                st.session_state["navigation_page"] = "NEWS_DETAIL"
                st.session_state["scroll_top_trig"] = int(time.time() * 1000)
                st.rerun()
        w_lbl = "✅ 監視解除" if r_m["code"] in st.session_state["watchlist"] else "⭐ 監視追加"
        if st.button(w_lbl, key=f"btn_watch_{uk_card}", use_container_width=True):
            if r_m["code"] in st.session_state["watchlist"]:
                del st.session_state["watchlist"][r_m["code"]]
            else:
                st.session_state["watchlist"][r_m["code"]] = r_m
            cu = st.session_state.get("authenticated_user", "")
            if cu: save_watchlist(cu, st.session_state["watchlist"])
            st.rerun()

    with b_col2:
        if st.button(f"🔥 DEEP DIVE ({r_m['code']})", key=f"btn_dd_{kp}_{r_m['code']}", use_container_width=True):
            st.session_state["dd_target_code"] = r_m["full_code"]
            st.session_state["dd_target_style"] = st_info.get("style_name", "デイトレード")
            st.session_state["dd_code_in"] = r_m["full_code"]
            st.session_state["dd_style_in"] = st_info.get("style_name", "デイトレード")
            st_name_cur = st_info.get("style_name", "default")
            matched_council = []
            for c_key_cand, c_val_cand in st.session_state.get("council_threads", {}).items():
                if r_m["code"] in str(c_key_cand) and st_name_cur in str(c_key_cand) and isinstance(c_val_cand, list):
                    matched_council = c_val_cand
                    break
            synced_entry = sync_lab_intel_to_shared(r_m, council_turns=matched_council if matched_council else None, rel_news_list=rel_news_list, persist=True)
            st.session_state["dd_lab_ctx"] = {
                "full_code": r_m["full_code"],
                "side": st_info.get("side", "LONG"),
                "expect_pct": float(r_m.get("expect_pct", 50.0)),
                "exec_grade": str(r_m.get("exec_grade", "")),
                "tp": float(r_m.get("raw_tp", 0.0)),
                "sl": float(r_m.get("raw_sl", 0.0)),
                "vwap": float(r_m.get("raw_vwap", 0.0)),
                "lab_full": r_m,
                "lab_council": synced_entry.get("lab_council", []),
                "lab_related_news": synced_entry.get("lab_related_news", rel_news_list),
                "lab_updated_at": synced_entry.get("lab_updated_at", ""),
                "dd_result": synced_entry.get("dd_result"),
                "dd_updated_at": synced_entry.get("dd_updated_at", ""),
            }
            st.session_state["navigation_page"] = "DEEP_DIVE"
            st.session_state["scroll_top_trig"] = int(time.time() * 1000)
            st.rerun()

        if st.button(f"🎯 日誌記録 ({r_m['code']})", key=f"btn_journal_add_{kp}_{r_m['code']}", use_container_width=True):
            cu_j = st.session_state.get("authenticated_user", "")
            if cu_j:
                j_list = load_trade_journal(cu_j)
                j_entry = {
                    "id": hashlib.md5(f"{r_m['full_code']}_{time.time_ns()}".encode()).hexdigest()[:10],
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "full_code": r_m["full_code"],
                    "code": r_m["code"],
                    "name": r_m["name"],
                    "genre": r_m["genre"],
                    "style": st_info.get("style_name", "デイトレード"),
                    "side": st_info.get("side", "LONG"),
                    "tactic_type": st_info.get("tactic_type", "Type-E"),
                    "exec_grade": exec_grade,
                    "entry_price": float(r_m.get("raw_close", 0.0)),
                    "tp_price": float(r_m.get("raw_tp", 0.0)),
                    "sl_price": float(r_m.get("raw_sl", 0.0)),
                    "vwap_price": float(r_m.get("raw_vwap", 0.0)),
                    "shares": int(lot.get("shares", 100)),
                    "status": "OPEN",
                    "exit_price": None,
                    "closed_at": None,
                    "pnl_yen": 0.0,
                    "pnl_pct": 0.0,
                    "ai_feedback": ""
                }
                j_list.insert(0, j_entry)
                save_trade_journal(cu_j, j_list)
                st.success(f"✅ 『{r_m['name']} ({r_m['code']})』をトレード日誌に記録しました！")

    render_council_sec(r_m, uk_card, auto_open=bool(is_focused or is_custom))
def _compute_single_10y_metrics(df_w: pd.DataFrame, full_code: str) -> dict:
    is_jp = ".T" in str(full_code)
    default_res = {"cagr_10y": 0.0, "pos_10y_pct": 50.0, "poc_10y_price": 0.0, "poc_10y_str": "-", "low_10y_str": "-", "high_10y_str": "-", "ma200w_dev_pct": 0.0, "ma200w_slope_up": True, "long_10y_score": 50, "regime_10y_label": "📊 10年大局データ標準評価", "poc_relation_note": "データ蓄積中", "years_span": "10Y", "df_weekly_clean": None, "has_data": False}
    if df_w is None or df_w.empty: return default_res
    df = df_w.dropna(subset=["Close", "High", "Low", "Volume"]).copy()
    if len(df) < 8: return default_res
    idx = df.index if isinstance(df.index, pd.DatetimeIndex) else pd.to_datetime(df.index)
    df["_w_str"] = idx.strftime("%Y-%m-%d")
    df = df[~df["_w_str"].duplicated(keep="last")].sort_index()
    if "Open" not in df.columns: df["Open"] = df["Close"]
    df_weekly_clean = df[["Open", "High", "Low", "Close", "Volume", "_w_str"]].copy()
    c, h, l, v = [np.asarray(df_weekly_clean[col].values, dtype=float).reshape(-1) for col in ["Close", "High", "Low", "Volume"]]
    curr_px, oldest_px = float(c[-1]), max(float(c[0]), 1e-4)
    years = max(len(c) / 52.0, 0.25); years_lbl = f"{years:.1f}Y" if years < 9.5 else "10Y"
    cagr_10y = round(float(np.clip(((curr_px / oldest_px) ** (1.0 / years) - 1.0) * 100.0, -60.0, 180.0)), 1)
    hi_10y, lo_10y = float(np.max(h)), float(np.min(l)); span_10y = max(hi_10y - lo_10y, 1e-4)
    pos_10y_pct = round(float(np.clip(((curr_px - lo_10y) / span_10y) * 100.0, 0.0, 100.0)), 1)
    bins = np.linspace(lo_10y, hi_10y + 1e-4, 16); typ_px = (h + l + c) / 3.0
    vol_profile = np.bincount(np.clip(np.digitize(typ_px, bins) - 1, 0, 14), weights=np.maximum(v, 1.0), minlength=15)
    poc_bin = int(np.argmax(vol_profile)); poc_10y_price = round_to_tse_tick(float((bins[poc_bin] + bins[poc_bin + 1]) * 0.5), full_code, "nearest")
    ma_len = min(200, len(c)); ma200w = float(np.mean(c[-ma_len:]))
    ma200w_prev = float(np.mean(c[-ma_len - min(12, len(c) - ma_len):-min(12, len(c) - ma_len)])) if len(c) > ma_len + 4 else float(c[0])
    ma200w_dev_pct = round(float(((curr_px - ma200w) / max(ma200w, 1e-4)) * 100.0), 1); ma200w_slope_up = bool(ma200w >= ma200w_prev)
    cagr_pts = float(np.clip(cagr_10y * 1.15, -20.0, 28.0))
    pos_pts = 14.0 if pos_10y_pct >= 88.0 else (8.0 if pos_10y_pct >= 65.0 else (10.0 if (pos_10y_pct <= 28.0 and curr_px >= poc_10y_price * 0.96) else 0.0))
    poc_pts = 10.0 if curr_px >= poc_10y_price else -6.0
    ma_pts = (8.0 if ma200w_dev_pct >= 0 else -6.0) + (5.0 if ma200w_slope_up else -4.0)
    long_10y_score = int(np.clip(round(48.0 + cagr_pts + pos_pts + poc_pts + ma_pts), 10, 99))
    if pos_10y_pct >= 90.0 and curr_px >= poc_10y_price: regime_10y_label = f"🚀 10年青天井ブレイク態勢 (CAGR {cagr_10y:+.1f}%)"
    elif pos_10y_pct <= 25.0 and ma200w_slope_up: regime_10y_label = f"💎 10年長期底値圏・大局バリュー反発域 (CAGR {cagr_10y:+.1f}%)"
    elif curr_px >= poc_10y_price and ma200w_dev_pct >= 0: regime_10y_label = f"🏛️ 10年長期上昇・岩盤POC支持トレンド (CAGR {cagr_10y:+.1f}%)"
    elif curr_px < poc_10y_price and ma200w_dev_pct < -5.0: regime_10y_label = f"⚠️ 10年長期戻り売り警戒・POC下抜け圏 (CAGR {cagr_10y:+.1f}%)"
    else: regime_10y_label = f"⚖️ 10年大局レンジ中立・需給均衡帯 (CAGR {cagr_10y:+.1f}%)"
    poc_diff_pct = ((curr_px - poc_10y_price) / max(poc_10y_price, 1e-4)) * 100.0
    poc_relation_note = f"現在値は10年最大出来高POCより+{poc_diff_pct:.1f}%上方（岩盤下値支持として機能）" if poc_diff_pct >= 0 else f"現在値は10年最大出来高POCより{poc_diff_pct:.1f}%下方（上値しこり抵抗帯として意識）"
    return {"cagr_10y": cagr_10y, "pos_10y_pct": pos_10y_pct, "poc_10y_price": poc_10y_price, "poc_10y_str": fmt_px(poc_10y_price, is_jp, full_code), "low_10y_str": fmt_px(lo_10y, is_jp, full_code), "high_10y_str": fmt_px(hi_10y, is_jp, full_code), "ma200w_dev_pct": ma200w_dev_pct, "ma200w_slope_up": ma200w_slope_up, "long_10y_score": long_10y_score, "regime_10y_label": regime_10y_label, "poc_relation_note": poc_relation_note, "years_span": years_lbl, "df_weekly_clean": df_weekly_clean, "has_data": True}

@st.cache_data(ttl=43200)
def fetch_10y_macro_metrics(codes_tuple: tuple) -> dict:
    codes = [c for c in dict.fromkeys(codes_tuple) if c and c not in DELISTED_OR_INVALID_CODES]
    out = {}
    if not codes: return out
    chunks = [codes[i:i + 20] for i in range(0, len(codes), 20)]
    def _proc_chunk(ch):
        ch_out = {}
        raw_ch = None
        try: raw_ch = yf.download(ch, period="10y", interval="1wk", auto_adjust=True, group_by="ticker", threads=True, progress=False, timeout=15.0)
        except Exception as e: record_system_error("fetch_10y_macro_metrics:chunk", e, f"Chunk size: {len(ch)}")
        for c in ch:
            try:
                df_c = _extract_ticker_df(raw_ch, c, len(ch))
                if df_c is None or df_c.dropna(subset=["Close"]).empty: df_c = yf.Ticker(c).history(period="10y", interval="1wk", auto_adjust=True)
                ch_out[c] = _compute_single_10y_metrics(df_c, c)
            except Exception as e_single: record_system_error(f"fetch_10y_macro_metrics:{c}", e_single); ch_out[c] = _compute_single_10y_metrics(None, c)
        return ch_out
    with ThreadPoolExecutor(max_workers=3) as ex_ch:
        for f_ch in as_completed([ex_ch.submit(_proc_chunk, ch) for ch in chunks]):
            try: out.update(f_ch.result())
            except Exception as e_f: record_system_error("fetch_10y_macro_metrics:future", e_f)
    return out

def _compute_single_daily_metrics(df_d: pd.DataFrame, bench_ret_series: pd.Series, full_code: str) -> dict:
    is_jp = ".T" in str(full_code)
    default_res = {"ma5": 0.0, "ma25": 0.0, "ma75": 0.0, "ma200": 0.0, "ma5_str": "-", "ma25_str": "-", "ma75_str": "-", "ma200_str": "-", "ma5_dev_pct": 0.0, "ma25_dev_pct": 0.0, "ma75_dev_pct": 0.0, "ma200_dev_pct": 0.0, "ma25_slope_up": True, "ma75_slope_up": True, "bull_po": False, "bear_po": False, "ma_align_label": "MA均衡", "macd_line": 0.0, "macd_signal": 0.0, "macd_hist": 0.0, "daily_rsi14": 50.0, "pos_52w_pct": 50.0, "is_52w_break": False, "daily_atr14": 0.0, "daily_atr14_str": "-", "daily_yz_vol": 0.30, "daily_rs_alpha_map": {}, "latest_rs_alpha": 0.0, "daily_trend_score": 50, "regime_1d_label": "⚖️ 日足中期レンジ均衡", "is_lvn_breakout": False, "hvn_wall_price": 0.0, "vp_struct_label": "⚖️ 標準出来高分布", "recent_close_60": [], "pdh": 0.0, "pdl": 0.0, "prev_close_1d": 0.0, "df_daily_clean": None, "has_data": False}
    if df_d is None or df_d.empty: return default_res
    df = df_d.dropna(subset=["Open", "High", "Low", "Close", "Volume"]).copy()
    if len(df) < 15: return default_res
    idx = df.index if isinstance(df.index, pd.DatetimeIndex) else pd.to_datetime(df.index)
    df["_d_str"] = idx.strftime("%Y-%m-%d")
    df = df[~df["_d_str"].duplicated(keep="last")].sort_index()
    o, h, l, c, v = [np.asarray(df[col].values, dtype=float).reshape(-1) for col in ["Open", "High", "Low", "Close", "Volume"]]
    curr_px = float(c[-1])
    pdh_val = float(h[-2]) if len(h) >= 2 else float(h[-1])
    pdl_val = float(l[-2]) if len(l) >= 2 else float(l[-1])
    prev_close_1d = float(c[-2]) if len(c) >= 2 else float(o[-1])
    ma5, ma25, ma75, ma200 = [float(np.mean(c[-min(k, len(c)):])) for k in (5, 25, 75, 200)]
    ma25_slope_up = bool(ma25 >= (float(np.mean(c[-min(30, len(c)):-5])) if len(c) >= 10 else ma25))
    ma75_slope_up = bool(ma75 >= (float(np.mean(c[-min(80, len(c)):-5])) if len(c) >= 15 else ma75))
    ma5_dev_pct, ma25_dev_pct, ma75_dev_pct, ma200_dev_pct = [round(((curr_px - m) / max(m, 1e-4)) * 100.0, 2) for m in (ma5, ma25, ma75, ma200)]
    bull_po = bool((curr_px > ma5 > ma25 > ma75) and ma25_slope_up)
    bear_po = bool((curr_px < ma5 < ma25 < ma75) and (not ma25_slope_up))
    ma_align_label = "🔥 強気パーフェクトオーダー(C>5>25>75)" if bull_po else ("❄️ 弱気パーフェクトオーダー(C<5<25<75)" if bear_po else ("📈 上昇配列(C>MA25>MA75)" if (curr_px >= ma25 and ma25 >= ma75) else ("📉 下降配列(MA25・75割れ)" if (curr_px < ma25 and curr_px < ma75) else "⚖️ MA交錯・転換監視帯")))
    c_series = pd.Series(c); macd_s = c_series.ewm(span=12, adjust=False).mean() - c_series.ewm(span=26, adjust=False).mean(); sig_s = macd_s.ewm(span=9, adjust=False).mean()
    macd_line, macd_signal, macd_hist = round(float(macd_s.iloc[-1]), 3), round(float(sig_s.iloc[-1]), 3), round(float((macd_s - sig_s).iloc[-1]), 3)
    diffs = np.diff(c); g, ls = np.maximum(diffs, 0.0), np.maximum(-diffs, 0.0)
    if len(diffs) >= 14:
        ag, al = float(np.mean(g[-14:])), float(np.mean(ls[-14:]))
        for i in range(len(diffs) - 14, len(diffs)): ag = (ag * 13.0 + float(g[i])) / 14.0; al = (al * 13.0 + float(ls[i])) / 14.0
        daily_rsi14 = round(float(np.clip(100.0 - (100.0 / (1.0 + ag / max(al, 1e-8))), 5.0, 95.0)), 1)
    else: daily_rsi14 = 50.0
    n_52w = min(252, len(c)); hi_52w, lo_52w = float(np.max(h[-n_52w:])), float(np.min(l[-n_52w:]))
    pos_52w_pct = round(float(np.clip(((curr_px - lo_52w) / max(hi_52w - lo_52w, 1e-4)) * 100.0, 0.0, 100.0)), 1); is_52w_break = bool(curr_px >= hi_52w * 0.992)

    h_vp, l_vp, c_vp, v_vp = h[-n_52w:], l[-n_52w:], c[-n_52w:], np.maximum(v[-n_52w:], 1.0)
    vp_bins = np.linspace(lo_52w, hi_52w + 1e-4, 21)
    vp_typ = (h_vp + l_vp + c_vp) / 3.0
    vp_hist = np.bincount(np.clip(np.digitize(vp_typ, vp_bins) - 1, 0, 19), weights=v_vp, minlength=20)
    vp_mean_vol = max(float(np.mean(vp_hist)), 1e-8)
    zone_lo, zone_hi = curr_px * 1.01, curr_px * 1.06
    above_bin_indices = [bi for bi in range(20) if vp_bins[bi + 1] >= zone_lo and vp_bins[bi] <= zone_hi]
    is_lvn_breakout, hvn_wall_price, vp_struct_label = False, 0.0, "⚖️ 標準出来高分布"
    if not above_bin_indices:
        if curr_px >= hi_52w * 0.985:
            is_lvn_breakout = True; vp_struct_label = "🚀 上値真空地帯(LVN・青天井)"
    else:
        above_vols = [float(vp_hist[bi]) for bi in above_bin_indices]
        above_avg_density = float(np.mean(above_vols))
        hvn_candidates = [bi for bi in above_bin_indices if float(vp_hist[bi]) >= vp_mean_vol * 1.8]
        if hvn_candidates:
            first_hvn_bin = min(hvn_candidates)
            raw_wall = max(float(vp_bins[first_hvn_bin]), curr_px * 1.005)
            hvn_wall_price = round_to_tse_tick(raw_wall, full_code, "nearest")
            vp_struct_label = f"🧱 直上しこり壁(HVN: {fmt_px(hvn_wall_price, is_jp, full_code)})"
        elif above_avg_density <= vp_mean_vol * 0.45 or curr_px >= hi_52w * 0.985:
            is_lvn_breakout = True; vp_struct_label = "🚀 上値真空地帯(LVN・青天井)"

    prev_c = np.roll(c, 1); prev_c[0] = c[0]; tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    daily_atr14 = max(float(np.mean(tr[-min(14, len(tr)):])), curr_px * 0.0115)
    n_yz = min(20, len(c) - 1)
    if n_yz >= 3:
        o_sub, h_sub, l_sub, c_sub, c_prev = o[-n_yz:], h[-n_yz:], l[-n_yz:], c[-n_yz:], c[-n_yz - 1:-1]
        log_oc, log_co = np.log(np.maximum(o_sub / np.maximum(c_prev, 1e-4), 1e-4)), np.log(np.maximum(c_sub / np.maximum(o_sub, 1e-4), 1e-4))
        log_ho, log_lo = np.log(np.maximum(h_sub / np.maximum(o_sub, 1e-4), 1e-4)), np.log(np.maximum(l_sub / np.maximum(o_sub, 1e-4), 1e-4))
        log_hc, log_lc = np.log(np.maximum(h_sub / np.maximum(c_sub, 1e-4), 1e-4)), np.log(np.maximum(l_sub / np.maximum(c_sub, 1e-4), 1e-4))
        k_yz = 0.34 / (1.34 + (n_yz + 1.0) / max(n_yz - 1.0, 1.0))
        yz_var = max(float(np.var(log_oc, ddof=1)) + k_yz * float(np.var(log_co, ddof=1)) + (1.0 - k_yz) * float(np.mean(log_ho * log_hc + log_lo * log_lc)), 1e-6)
        daily_yz_vol = round(float(np.clip(np.sqrt(yz_var * 252.0), 0.08, 2.50)), 2)
    else: daily_yz_vol = 0.30
    stk_ret_pct = pd.Series(c, index=df["_d_str"]).pct_change().fillna(0.0) * 100.0
    daily_rs_alpha_map = {str(d_k): round(float(s_r) - (float(bench_ret_series.get(d_k, 0.0)) if (bench_ret_series is not None and d_k in bench_ret_series.index) else 0.0), 3) for d_k, s_r in stk_ret_pct.items()}
    latest_rs_alpha = float(daily_rs_alpha_map.get(str(df["_d_str"].iloc[-1]), 0.0))
    po_pts = 16.0 if bull_po else (-16.0 if bear_po else (8.0 if (curr_px >= ma25 and ma25_slope_up) else (-7.0 if curr_px < ma25 else 0.0)))
    macd_pts = 8.0 if (macd_hist > 0 and macd_line > 0) else (4.0 if macd_hist > 0 else (-7.0 if (macd_hist < 0 and macd_line < 0) else -3.0))
    w52_pts = 10.0 if pos_52w_pct >= 88.0 else (5.0 if pos_52w_pct >= 65.0 else (-6.0 if pos_52w_pct <= 22.0 else 0.0))
    lvn_pts = 5.0 if is_lvn_breakout else 0.0
    daily_trend_score = int(np.clip(round(50.0 + po_pts + macd_pts + w52_pts + lvn_pts + (6.0 if ma200_dev_pct >= 0 else -5.0) + float(np.clip(latest_rs_alpha * 1.5, -6.0, 6.0))), 10, 99))
    regime_1d_label = "🚀 日足強気PO＋52週高値ブレイク" if (bull_po and is_52w_break) else ("🔥 日足強気パーフェクトオーダー上昇" if bull_po else ("❄️ 日足弱気パーフェクトオーダー下落" if bear_po else ("📈 日足MA25上・MACD好転トレンド" if (curr_px >= ma25 and macd_hist > 0) else ("📉 日足MA25・MA75割れ調整局面" if (curr_px < ma25 and curr_px < ma75) else "⚖️ 日足中期レンジ・方向感模索"))))
    recent_close_60 = [round(float(x), 4) for x in c[-61:]]
    return {"ma5": ma5, "ma25": ma25, "ma75": ma75, "ma200": ma200, "ma5_str": fmt_px(ma5, is_jp, full_code), "ma25_str": fmt_px(ma25, is_jp, full_code), "ma75_str": fmt_px(ma75, is_jp, full_code), "ma200_str": fmt_px(ma200, is_jp, full_code), "ma5_dev_pct": ma5_dev_pct, "ma25_dev_pct": ma25_dev_pct, "ma75_dev_pct": ma75_dev_pct, "ma200_dev_pct": ma200_dev_pct, "ma25_slope_up": ma25_slope_up, "ma75_slope_up": ma75_slope_up, "bull_po": bull_po, "bear_po": bear_po, "ma_align_label": ma_align_label, "macd_line": macd_line, "macd_signal": macd_signal, "macd_hist": macd_hist, "daily_rsi14": daily_rsi14, "pos_52w_pct": pos_52w_pct, "is_52w_break": is_52w_break, "daily_atr14": daily_atr14, "daily_atr14_str": fmt_px(daily_atr14, is_jp, full_code), "daily_yz_vol": daily_yz_vol, "daily_rs_alpha_map": daily_rs_alpha_map, "latest_rs_alpha": latest_rs_alpha, "daily_trend_score": daily_trend_score, "regime_1d_label": regime_1d_label, "is_lvn_breakout": is_lvn_breakout, "hvn_wall_price": hvn_wall_price, "vp_struct_label": vp_struct_label, "recent_close_60": recent_close_60, "pdh": pdh_val, "pdl": pdl_val, "prev_close_1d": prev_close_1d, "df_daily_clean": df[["Open", "High", "Low", "Close", "Volume", "_d_str"]].copy(), "has_data": True}

@st.cache_data(ttl=1800)
def fetch_2y_daily_metrics(codes_tuple: tuple) -> dict:
    codes = [c for c in dict.fromkeys(codes_tuple) if c and c not in DELISTED_OR_INVALID_CODES]
    out = {}
    if not codes: return out
    all_req = list(dict.fromkeys(codes + ["^N225", "^GSPC"]))
    raw_all = None
    try: raw_all = yf.download(all_req, period="2y", interval="1d", auto_adjust=True, group_by="ticker", threads=True, progress=False, timeout=12.0)
    except Exception as e: record_system_error("fetch_2y_daily_metrics:batch", e)
    def _build_bench_ret(b_code: str) -> pd.Series:
        try:
            bdf = _extract_ticker_df(raw_all, b_code, len(all_req))
            if bdf is None or bdf.dropna(subset=["Close"]).empty: bdf = yf.Ticker(b_code).history(period="2y", interval="1d", auto_adjust=True)
            if bdf is not None and not bdf.empty:
                bdf = bdf.dropna(subset=["Close"]).copy(); b_idx = bdf.index if isinstance(bdf.index, pd.DatetimeIndex) else pd.to_datetime(bdf.index)
                bdf["_d_str"] = b_idx.strftime("%Y-%m-%d"); bdf = bdf[~bdf["_d_str"].duplicated(keep="last")].sort_index()
                return pd.Series(bdf["Close"].values.astype(float), index=bdf["_d_str"]).pct_change().fillna(0.0) * 100.0
        except Exception as eb: record_system_error(f"fetch_2y_daily_metrics:bench:{b_code}", eb)
        return pd.Series(dtype=float)
    n225_ret, gspc_ret = _build_bench_ret("^N225"), _build_bench_ret("^GSPC")
    for c in codes:
        try:
            df_c = _extract_ticker_df(raw_all, c, len(all_req))
            if df_c is None or df_c.dropna(subset=["Close"]).empty: df_c = yf.Ticker(c).history(period="2y", interval="1d", auto_adjust=True)
            out[c] = _compute_single_daily_metrics(df_c, n225_ret if ".T" in str(c).upper() else gspc_ret, c)
        except Exception as e_c: record_system_error(f"fetch_2y_daily_metrics:{c}", e_c); out[c] = _compute_single_daily_metrics(None, pd.Series(dtype=float), c)
    return out

@st.cache_data(ttl=300)
def fetch_real_market_buzz(tickers_tuple: tuple) -> dict:
    buzz_map = {}
    def _query_buzz(item):
        c, n, _, _ = item; time.sleep(0.05)
        hits = search_single_query(f"{n} 株", 5, trusted_only=False)
        return c, {"news_hits": len(hits), "headlines": hits[:2]}
    with ThreadPoolExecutor(max_workers=4) as ex:
        for f in as_completed([ex.submit(_query_buzz, it) for it in tickers_tuple]):
            try: c, info = f.result(); buzz_map[c] = info
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
            except Exception as e_tick: record_system_error(f"fetch_macro:{k}", e_tick); res[k] = {"price": 0.0, "diff": 0.0, "label": lbl}
    except Exception as e:
        record_system_error("fetch_macro", e)
        for k, (_, lbl) in tks.items(): res[k] = {"price": 0.0, "diff": 0.0, "label": lbl}
    return res

def compute_smoothed_clv_z(c: np.ndarray, h: np.ndarray, l: np.ndarray, v: np.ndarray, day_bars_count: int = 0) -> float:
    if len(c) < 10: return 0.0
    clv = (2.0 * c - h - l) / np.maximum(h - l, 1e-4); sf = clv * v
    std_ref = max(float(np.std(sf[-30:])) if len(sf) >= 30 else float(np.std(sf)), 1.0)
    mean_ref = float(np.mean(sf[-30:])) if len(sf) >= 30 else float(np.mean(sf))
    z_recent10 = (float(np.mean(sf[-10:])) - mean_ref) / std_ref
    n_day = day_bars_count if day_bars_count >= 3 else min(len(c), 45)
    c_d, h_d, l_d, v_d = c[-n_day:], h[-n_day:], l[-n_day:], v[-n_day:]
    clv_d = (2.0 * c_d - h_d - l_d) / np.maximum(h_d - l_d, 1e-4)
    z_day_vw = float(np.sum(clv_d * v_d) / max(float(np.sum(v_d)), 1e-8)) * 2.2
    return float(np.clip(z_day_vw * 0.60 + z_recent10 * 0.40, -3.0, 3.0))

def compute_quantum_wave_metrics(c: np.ndarray, h: np.ndarray, l: np.ndarray, v: np.ndarray, o: np.ndarray = None, rsi_val: float = None, upper_wick_val: float = None) -> dict:
    n_win = min(20, len(c) - 1); c_sub, v_sub = c[-n_win:], v[-n_win:]
    vwma = float(np.sum(c_sub * v_sub) / max(np.sum(v_sub), 1e-8)) if np.sum(v_sub) > 0 else float(np.mean(c_sub))
    sigma = max(float(np.std(c_sub - vwma)), max(float(c[-1]) * 0.002, 1e-6))
    hh = h[-20:-1] if len(h) >= 20 else h[:-1]
    r_max, bars_since_high = (float(np.max(hh)), len(hh) - int(np.argmax(hh))) if len(hh) > 0 else (float(c[-1]), 1)
    v0 = max((r_max - float(c[-1])) / (sigma + 1e-8), 0.0)
    look_k = min(6, len(c)); mom_move = abs(float(c[-1] - c[-look_k]))
    base_v = float(np.mean(v[-20:-5])) if len(v) >= 20 else float(np.mean(v[:-1]))
    rvol = float(np.mean(v[-5:])) / max(base_v, 1.0)
    energy_e = (mom_move / (5.0 * sigma + 1e-8)) * max(rvol, 0.1)
    delta_x = float(np.clip(bars_since_high / 20.0, 0.2, 2.0))
    qt = float(np.clip(80.0 + (energy_e - v0) * 10.0, 80.0, 99.5)) if energy_e >= v0 else float(np.clip(80.0 * np.exp(-2.0 * np.sqrt(max(v0 - energy_e, 0.0)) * delta_x), 5.0, 99.5))
    if rsi_val is None:
        diffs_w = np.diff(c); gw, lw = np.maximum(diffs_w, 0.0), np.maximum(-diffs_w, 0.0)
        rsi_val = float(np.clip(100.0 - (100.0 / (1.0 + float(np.mean(gw[-14:])) / max(float(np.mean(lw[-14:])), 1e-8))), 5.0, 95.0)) if len(diffs_w) >= 14 else 50.0
    if upper_wick_val is None:
        nw = min(12, len(c)); o_arr = o[-nw:] if o is not None else np.roll(c, 1)[-nw:]
        hw, lw_arr, cw, vw = h[-nw:], l[-nw:], c[-nw:], np.maximum(v[-nw:], 1.0)
        upper_wick_val = float(np.clip((np.sum(((hw - np.maximum(o_arr, cw)) / np.maximum(hw - lw_arr, 1e-4)) * vw) / max(float(np.sum(vw)), 1e-8)) * 100.0, 0.0, 100.0))
    overheat_penalty = min(42.0, (float(rsi_val) - 75.0) * 1.4 + (float(upper_wick_val) - 45.0) * 0.65) if (float(rsi_val) > 75.0 and float(upper_wick_val) > 45.0) else 0.0
    if overheat_penalty > 0: qt = float(np.clip(qt - overheat_penalty, 5.0, 72.0))
    rets = np.diff(c) / np.maximum(c[:-1], 1e-4); rets_16 = rets[-16:] if len(rets) >= 16 else rets
    if len(rets_16) >= 5:
        hist_counts, _ = np.histogram(rets_16, bins=5); probs = hist_counts / max(float(np.sum(hist_counts)), 1.0); probs_nz = probs[probs > 0]
        h_norm = float(np.clip(float(-np.sum(probs_nz * np.log(probs_nz))) / np.log(5.0), 0.0, 1.0))
        order_pct = (1.0 - h_norm) * 100.0; phase_coh = float(np.abs(np.mean(np.exp(1j * np.angle(np.fft.rfft(rets_16))))) * 100.0)
    else: h_norm, order_pct, phase_coh = 0.5, 50.0, 50.0
    coh = float(np.clip(phase_coh * 0.55 + order_pct * 0.45 - overheat_penalty * 0.4, 5.0, 99.0))
    q_score = int(np.clip(round(qt * 0.65 + coh * 0.35), 5, 99))
    q_state = f"⚠️ 天井過熱・上ヒゲ拒絶減衰中 (RSI={rsi_val:.0f}/上ヒゲ={upper_wick_val:.0f})" if overheat_penalty > 0 else ("⚛️ WKB統計近似・上値障壁突破フェーズ" if qt >= 80.0 else ("🌊 ボラティリティ位相コヒーレンス干渉" if qt >= 50.0 else "🧱 抵抗帯下・エネルギー蓄積中"))
    return {"q_score": q_score, "q_tunnel": round(qt, 1), "q_coherence": round(coh, 1), "q_entropy": round(h_norm, 2), "q_state": q_state}

def compute_inst_microstructure(c: np.ndarray, h: np.ndarray, l: np.ndarray, v: np.ndarray) -> dict:
    rets = np.diff(c) / np.maximum(c[:-1], 1e-4); n = min(len(rets), 50)
    if n >= 20:
        cd = np.cumsum(rets[-n:] - np.mean(rets[-n:])); scales, fls = [4, 8, 16], []
        for s in scales:
            n_seg = n // s; segs = cd[:n_seg * s].reshape(n_seg, s); x_idx = np.arange(s); x_mean = np.mean(x_idx); x_var = np.sum((x_idx - x_mean) ** 2)
            slopes = np.sum((segs - np.mean(segs, axis=1, keepdims=True)) * (x_idx - x_mean), axis=1) / max(x_var, 1e-8)
            trends = slopes[:, None] * x_idx[None, :] + (np.mean(segs, axis=1) - slopes * x_mean)[:, None]
            fls.append(np.sqrt(max(float(np.mean((segs - trends) ** 2)), 1e-12)))
        hurst = float(np.clip(np.polyfit(np.log(scales), np.log(fls), 1)[0], 0.15, 0.95))
    else: hurst = 0.50
    dp = np.diff(c[-21:]) if len(c) >= 21 else np.diff(c); v_20 = v[-len(dp):]; sv = np.where(dp == 0, 1.0, np.sign(dp)) * v_20
    kyle_lambda = float(np.mean((dp - np.mean(dp)) * (sv - np.mean(sv)))) / (float(np.var(sv)) + 1e-8) if (len(dp) >= 5 and np.var(sv) > 1e-8) else 0.0
    base_v = float(np.mean(v[-20:-5])) if len(v) >= 20 else float(np.mean(v[:-1])); rvol = float(np.mean(v[-5:])) / max(base_v, 1.0)
    clv_recent = float(np.mean((2.0 * c[-5:] - h[-5:] - l[-5:]) / np.maximum(h[-5:] - l[-5:], 1e-4)))
    stealth_absorption = float(np.clip(1.0 / (1.0 + (abs(kyle_lambda) * max(float(np.mean(v_20)), 1.0) / max(float(c[-1]), 1.0)) * 150.0), 0.0, 1.0))
    ks = float(np.clip(40.0 + (hurst - 0.50) * 70.0 + min(max(rvol - 0.8, 0.0), 3.0) * 10.0 + stealth_absorption * 22.0 + clv_recent * 15.0, 10.0, 99.0))
    ms_score = int(np.clip(round(ks), 10, 99))
    ms_regime = "📐 低価格インパクト・5分足ステルス集積近似" if (hurst >= 0.58 and ks >= 68.0) else ("🏛️ トレンド持続型・5分足フロー追従" if hurst >= 0.52 else "⚖️ 平均回帰・レンジ流動性中立")
    return {"ms_score": ms_score, "hurst": round(hurst, 2), "kyle_lambda": kyle_lambda, "kyle_stealth": round(ks, 1), "ms_regime": ms_regime}

def compute_intraday_cumulative_rvol(df: pd.DataFrame, daily_df: pd.DataFrame = None) -> float:
    if df is not None and "_trade_date" in df.columns and len(df) >= 5:
        u_dates = sorted(df["_trade_date"].unique().tolist())
        if len(u_dates) >= 2:
            latest_d = u_dates[-1]; today_sub = df[df["_trade_date"] == latest_d]; k_bars = len(today_sub); today_cum_vol = float(today_sub["Volume"].sum())
            if k_bars >= 1 and today_cum_vol > 0:
                past_cum_vols = [float(df[df["_trade_date"] == pd_str]["Volume"].iloc[:min(k_bars, len(df[df["_trade_date"] == pd_str]))].sum()) for pd_str in u_dates[-7:-1] if len(df[df["_trade_date"] == pd_str]) >= 1]
                past_cum_vols = [pv for pv in past_cum_vols if pv > 0]
                if past_cum_vols: return round(float(np.clip(today_cum_vol / max(float(np.mean(past_cum_vols)), 1.0), 0.1, 15.0)), 2)
    if daily_df is not None and len(daily_df) >= 3:
        dv = daily_df["Volume"].values.astype(float)
        return round(float(dv[-1]) / max(float(np.mean(dv[-6:-1])) if len(dv) >= 6 else float(np.mean(dv[:-1])), 1.0), 2)
    return 1.0

def compute_advanced_quant_indicators(c: np.ndarray, o: np.ndarray, h: np.ndarray, l: np.ndarray, v: np.ndarray, daily_df: pd.DataFrame = None, news_hits: int = 0, df: pd.DataFrame = None, real_daily_yz_vol: float = None) -> dict:
    diffs, rets = np.diff(c), np.diff(c) / np.maximum(c[:-1], 1e-4); g, ls = np.maximum(diffs, 0.0), np.maximum(-diffs, 0.0)
    if len(diffs) >= 14:
        ag, al = float(np.mean(g[-14:])), float(np.mean(ls[-14:]))
        for i in range(len(diffs) - 14, len(diffs)): ag = (ag * 13.0 + float(g[i])) / 14.0; al = (al * 13.0 + float(ls[i])) / 14.0
        rsi = float(np.clip(100.0 - (100.0 / (1.0 + ag / max(al, 1e-8))), 5.0, 95.0))
    else: rsi = 50.0
    n_wick = min(12, len(c))
    if n_wick >= 1:
        h_w, l_w, o_w, c_w, v_w = h[-n_wick:], l[-n_wick:], o[-n_wick:], c[-n_wick:], np.maximum(v[-n_wick:], 1.0); rng_w = np.maximum(h_w - l_w, 1e-4); tot_vw = float(np.sum(v_w))
        upper_wick_pressure = round(float(np.clip((np.sum(((h_w - np.maximum(o_w, c_w)) / rng_w) * v_w) / max(tot_vw, 1e-8)) * 100.0, 0.0, 100.0)), 1)
        lower_wick_support = round(float(np.clip((np.sum(((np.minimum(o_w, c_w) - l_w) / rng_w) * v_w) / max(tot_vw, 1e-8)) * 100.0, 0.0, 100.0)), 1)
    else: upper_wick_pressure, lower_wick_support = 0.0, 0.0
    n_vpin = min(20, len(diffs))
    if n_vpin >= 5:
        dc_sub, v_sub = diffs[-n_vpin:], v[-n_vpin:]; z_t = dc_sub / max(float(np.std(dc_sub)), max(float(c[-1]) * 0.001, 1e-6))
        phi_z = np.vectorize(lambda z: 0.5 * (1.0 + math.erf(float(z) / math.sqrt(2.0))))(z_t); tot_v_sub = float(np.sum(v_sub))
        vpin = float(np.clip(np.sum(np.abs(v_sub * phi_z - v_sub * (1.0 - phi_z))) / max(tot_v_sub, 1e-8), 0.05, 0.98)) if tot_v_sub > 0 else 0.50
    else: vpin = 0.50
    if len(rets) >= 20:
        v99 = np.percentile(rets, 1); tl = rets[rets <= v99]
        cvar = float(np.clip(abs(np.mean(tl)) * 100.0 if len(tl) > 0 else abs(v99) * 100.0, 0.5, 18.0))
    else: cvar = 3.8
    er_n = min(20, len(c) - 1)
    eff_pct = int(np.clip(round((abs(float(c[-1] - c[-1 - er_n])) / max(float(np.sum(np.abs(np.diff(c[-1 - er_n:])))), 1e-8)) * 100.0), 1, 99)) if er_n >= 5 else 50
    pos_diffs, neg_diffs = diffs[diffs > 0], np.abs(diffs[diffs < 0])
    payoff = round(float(np.clip((float(np.mean(pos_diffs)) if len(pos_diffs) > 0 else float(c[-1] * 0.005)) / max(float(np.mean(neg_diffs)) if len(neg_diffs) > 0 else float(c[-1] * 0.005), 1e-8), 0.3, 6.0)), 2)
    bb_exp_ratio = round(float(np.clip((float(np.std(c[-5:])) / max(float(np.mean(c[-5:])), 1e-4)) / max(float(np.std(c[-25:-5])) / max(float(np.mean(c[-25:-5])), 1e-4), 1e-5), 0.2, 4.0)), 2) if len(c) >= 25 else 1.0
    if len(c) >= 20:
        v_win, c_win, o_win, h_win, l_win = v[-20:], c[-20:], o[-20:], h[-20:], l[-20:]
        vol_spike_bull_pct = round(float(np.mean((v_win >= (float(np.mean(v_win)) + 1.5 * float(np.std(v_win)))) & (((c_win - o_win) / np.maximum(h_win - l_win, 1e-4)) >= 0.55))) * 100.0, 1)
    else: vol_spike_bull_pct = 0.0
    rvol = compute_intraday_cumulative_rvol(df, daily_df=daily_df)
    yz_vol = float(real_daily_yz_vol) if (real_daily_yz_vol is not None and real_daily_yz_vol > 0) else 0.30
    surge_score = int(np.clip(30.0 + min(rvol, 4.0) * 15.0 + min(news_hits, 5) * 4.5 + abs(rets[-1]) * 180.0, 10, 99))
    return {"rsi": round(rsi, 1), "vpin": round(vpin, 2), "cvar95": round(cvar, 2), "yz_vol": yz_vol, "eff_pct": eff_pct, "payoff": payoff, "rvol": rvol, "news_hits": news_hits, "surge_attention_score": surge_score, "bb_exp_ratio": bb_exp_ratio, "vol_spike_bull_pct": vol_spike_bull_pct, "upper_wick_pressure": upper_wick_pressure, "lower_wick_support": lower_wick_support}

def compute_style_tp_sl_deltas(ref_px: float, atrv: float, is_short: bool, style: str, combat_prof: dict, full_code: str, recent_lows: np.ndarray = None, recent_highs: np.ndarray = None) -> tuple:
    spec = get_style_spec(style)
    sl_mult, tp_mult = float(combat_prof.get("sl_mult", 1.0)), float(combat_prof.get("tp_mult", 1.0))
    tick = get_tse_tick_step(ref_px, full_code)
    if spec["tf"] == "1d":
        atr_sl = atrv * float(spec["atr_sl_mult"]) * sl_mult
        if recent_lows is not None and len(recent_lows) > 0:
            struct_sl = max(0.0, (ref_px - float(np.min(recent_lows))) + tick)
            raw_sl = max(atr_sl, struct_sl)
        else: raw_sl = atr_sl
        sl_d = float(np.clip(raw_sl, ref_px * spec["sl_min_pct"], ref_px * spec["sl_max_pct"]))
        raw_tp = atrv * float(spec["atr_tp_mult"]) * tp_mult
        tp_d = float(np.clip(raw_tp, max(ref_px * spec["tp_min_pct"], sl_d * 1.6), ref_px * spec["tp_max_pct"]))
        return sl_d, tp_d
    atr_sl = max(atrv * float(spec["atr_sl_mult"]) * sl_mult, ref_px * spec["sl_min_pct"])
    if is_short:
        struct_dist = max(0.0, (float(np.max(recent_highs)) - ref_px) + tick) if (recent_highs is not None and len(recent_highs) > 0) else atr_sl
    else:
        struct_dist = max(0.0, (ref_px - float(np.min(recent_lows))) + tick) if (recent_lows is not None and len(recent_lows) > 0) else atr_sl
    sl_d = float(np.clip(max(atr_sl, min(struct_dist, ref_px * spec["sl_max_pct"])), ref_px * spec["sl_min_pct"], ref_px * spec["sl_max_pct"]))
    tp_d = float(np.clip(sl_d * float(spec["rr_mult"]) * tp_mult, sl_d * 1.5, ref_px * spec["tp_max_pct"]))
    return sl_d, tp_d

def compute_japanese_lot_sizing(cv: float, slv: float, total_capital: float, risk_tolerance_pct: float, is_jp: bool, style_mul: float = 1.0, lot_cap_mult: float = 1.0, earnings_days_left=None) -> dict:
    earnings_mult = 0.5 if (earnings_days_left is not None and 0 <= int(earnings_days_left) <= 3) else 1.0
    eff_cap_mult = float(lot_cap_mult) * earnings_mult
    rm = float(total_capital) * (float(risk_tolerance_pct) / 100.0) * earnings_mult
    risk_per_share = max(abs(cv - slv), cv * 0.005)
    raw_shares = int((rm / risk_per_share) * style_mul)
    max_affordable = int((float(total_capital) * eff_cap_mult) // max(cv, 1e-4))
    if max_affordable < 1: max_affordable = int((float(total_capital) * earnings_mult) // max(cv, 1e-4))
    if max_affordable < 1: max_affordable = int(float(total_capital) // max(cv, 1e-4))
    capped_shares = max(1, min(raw_shares, max_affordable)); is_odd_lot = False
    if is_jp:
        if max_affordable >= 100:
            final_shares = max(100, (capped_shares // 100) * 100) if (capped_shares // 100) * 100 > 0 else 100
            if final_shares * cv > float(total_capital): final_shares, is_odd_lot = max(1, capped_shares), True
        else: final_shares, is_odd_lot = max(1, capped_shares), True
    else: final_shares = max(1, capped_shares)
    return {"shares": final_shares, "position_value": final_shares * cv, "risk_amount": rm, "is_odd_lot": is_odd_lot}

def compute_directional_edges(ofi_z: float, rsi: float, prev_trend_weak: bool, hurst: float, upper_wick_pressure: float, lower_wick_support: float, rel_news_title: str = "", rs_alpha: float = 0.0, below_vwap: bool = False, daily_ctx: dict = None, macro_10y: dict = None, cv: float = 0.0) -> tuple:
    bull_edge = ofi_z * 18.0 + (lower_wick_support - upper_wick_pressure) * 0.4 + (hurst - 0.5) * 40.0 * (1.0 if not prev_trend_weak else -0.5)
    bear_edge = (-ofi_z) * 18.0 + (upper_wick_pressure - lower_wick_support) * 0.45 + (12.0 if prev_trend_weak else 0.0) + max(0.0, rsi - 62.0) * 1.1
    if rs_alpha > 0.5: bull_edge += min((rs_alpha - 0.5) * 4.5 + 4.0, 18.0)
    elif rs_alpha < -0.5: bear_edge += min((abs(rs_alpha) - 0.5) * 4.5 + 4.0, 18.0)
    d_ctx, m10 = daily_ctx or {}, macro_10y or {}
    poc_10y = float(m10.get("poc_10y_price", 0.0))
    above_10y_poc = bool(poc_10y <= 0.0 or cv <= 0.0 or cv >= poc_10y * 0.995)
    below_10y_poc = bool(poc_10y > 0.0 and cv > 0.0 and cv < poc_10y * 0.990)
    if d_ctx.get("bull_po"):
        bull_edge += 11.0
        if above_10y_poc: bull_edge += 7.0; bear_edge -= 14.0
    elif d_ctx.get("bear_po"):
        bear_edge += 13.0
        if below_10y_poc: bear_edge += 7.0; bull_edge -= 10.0
    else:
        ma25_v, ma75_v, macd_h, pos_52w = float(d_ctx.get("ma25", 0.0)), float(d_ctx.get("ma75", 0.0)), float(d_ctx.get("macd_hist", 0.0)), float(d_ctx.get("pos_52w_pct", 50.0))
        if ma25_v > 0 and cv > 0:
            if cv >= ma25_v and d_ctx.get("ma25_slope_up", True): bull_edge += 6.5
            elif cv < ma25_v and (ma75_v <= 0 or cv < ma75_v): bear_edge += 8.5
        if macd_h > 0: bull_edge += 4.5
        elif macd_h < 0: bear_edge += 5.0
        if pos_52w >= 88.0: bull_edge += 5.0
        elif pos_52w <= 22.0 and below_10y_poc: bear_edge += 4.5
    if m10.get("has_data"):
        if above_10y_poc and m10.get("ma200w_dev_pct", 0.0) >= 0.0: bull_edge += 5.0
        elif below_10y_poc and m10.get("ma200w_dev_pct", 0.0) < -3.0: bear_edge += 6.0
    if rel_news_title:
        if any(bw in rel_news_title for bw in BEARISH_NEWS_KEYWORDS): bear_edge += 18.0
        elif below_vwap and upper_wick_pressure >= 35.0: bear_edge += 15.0
        else: bull_edge += 15.0; bear_edge -= 20.0
    return round(float(bull_edge), 2), round(float(bear_edge), 2)

def evaluate_execution_quality_gate(is_short: bool, prev_trend_weak: bool, cv: float, vwap_today: float, eff_pct: int, bull_edge: float, bear_edge: float, rvol: float, min_rvol_req: float, upper_wick_pressure: float, lower_wick_support: float, daily_ctx: dict = None, macro_10y: dict = None, macro: dict = None, rs_alpha: float = 0.0, earnings_days_left=None, vwap_over_2sigma: bool = False, limit_up_tight: bool = False) -> tuple:
    d_ctx, m10 = daily_ctx or {}, macro_10y or {}
    ma25_v, poc_10y = float(d_ctx.get("ma25", 0.0)), float(m10.get("poc_10y_price", 0.0))
    daily_bull_ok = (cv >= ma25_v * 0.992) if ma25_v > 0 else (not prev_trend_weak)
    daily_bear_ok = (cv <= ma25_v * 1.005) if ma25_v > 0 else prev_trend_weak
    weekly_bull_ok = (cv >= poc_10y * 0.985) if poc_10y > 0 else True
    weekly_bear_ok = (cv <= poc_10y * 1.02) if poc_10y > 0 else True
    cond1_mtf = ((cv <= vwap_today * 1.001) and (daily_bear_ok or prev_trend_weak) and (weekly_bear_ok or d_ctx.get("bear_po", False))) if is_short else ((cv >= vwap_today * 0.998) and daily_bull_ok and (weekly_bull_ok or d_ctx.get("bull_po", False)))
    cond2_er, cond3_spread, cond4_rvol = (int(eff_pct) >= 28), (abs(bull_edge - bear_edge) >= 8.0), (float(rvol) >= float(min_rvol_req))
    cond5_wick = (float(lower_wick_support) < 45.0) if is_short else (float(upper_wick_pressure) < 45.0)
    raw_exec_score = int(cond1_mtf) + int(cond2_er) + int(cond3_spread) + int(cond4_rvol) + int(cond5_wick)
    macro_risk_off, macro_note = False, ""
    if isinstance(macro, dict):
        nk_d, sp_d = float(macro.get("nk_fut", {}).get("diff", 0.0)), float(macro.get("sp500", {}).get("diff", 0.0))
        if (nk_d <= -1.2 or sp_d <= -1.2) and float(rs_alpha) < 1.5:
            macro_risk_off = True; macro_note = f" / ⚠️指数リスクオフ減点(-1: 先物{nk_d:+.1f}%/SP{sp_d:+.1f}%, RSα={rs_alpha:+.1f}%<1.5%)"
    earnings_penalty, earnings_note = 0, ""
    if earnings_days_left is not None and 0 <= int(earnings_days_left) <= 3:
        earnings_penalty = 1
        earnings_note = f" / ⚠️決算跨ぎ減点(-1: 残り{int(earnings_days_left)}日・建玉半減)"
    vwap_2s_penalty, vwap_2s_note = 0, ""
    if (not is_short) and vwap_over_2sigma:
        vwap_2s_penalty = 1
        vwap_2s_note = " / ⚠️VWAP+2σ過熱減点(-1: 高値掴み警戒)"
    lim_penalty, lim_note = 0, ""
    if (not is_short) and limit_up_tight:
        lim_penalty = 1
        lim_note = " / ⚠️ストップ高張り付き減点(-1: 上値余地1.5%未満)"
    exec_score = max(0, raw_exec_score - (1 if macro_risk_off else 0) - earnings_penalty - vwap_2s_penalty - lim_penalty)
    exec_grade = "🟢 Grade-A: 即時執行適格（3階層MTF全5条件クリア）" if exec_score >= 5 else ("🔵 Grade-B: 標準執行（基準厳守）" if exec_score == 4 else "🟡 Grade-C: 様子見・押し目/戻り待機（厳選フィルタ/MTF注意）")
    wick_tag = f"下ヒゲ支持({lower_wick_support:.0f}<45)={'OK' if cond5_wick else 'NG(底堅い)'}" if is_short else f"上ヒゲ拒絶({upper_wick_pressure:.0f}<45)={'OK' if cond5_wick else 'NG(寄り天警戒)'}"
    return exec_score, exec_grade, f"3階層MTF(10Y/1D/5m)={'OK' if cond1_mtf else 'NG'} / 効率性ER({eff_pct}%)={'OK' if cond2_er else 'NG'} / 優位差({abs(bull_edge-bear_edge):.1f}pt)={'OK' if cond3_spread else 'NG'} / 時間帯RVOL({rvol}x)={'OK' if cond4_rvol else 'NG'} / {wick_tag}{macro_note}{earnings_note}{vwap_2s_note}{lim_note}"

def determine_tactic_classification(full_code: str, genre: str, ofi_z: float, vpin: float, rsi: float, pgap: float, expect_pct: float, prev_trend_weak: bool, qm: dict, ms: dict, rel_news_title: str = "", style: str = "", upper_wick_pressure: float = 0.0, lower_wick_support: float = 0.0, cv: float = 0.0, vwap_today: float = 0.0, rs_alpha: float = 0.0, daily_ctx: dict = None, macro_10y: dict = None) -> str:
    spec = get_style_spec(style)
    is_jp_t3 = is_jp_tier3_short_restricted(full_code, genre)
    hurst = float(ms.get("hurst", 0.50)); has_vwap = (cv > 0.0 and vwap_today > 0.0); below_vwap = bool(has_vwap and (cv < vwap_today))
    d_ctx, m10 = daily_ctx or {}, macro_10y or {}
    poc_10y, ma25_v, ma25_slope_up = float(m10.get("poc_10y_price", 0.0)), float(d_ctx.get("ma25", 0.0)), bool(d_ctx.get("ma25_slope_up", True))
    daily_clear_downtrend = bool(ma25_v > 0 and cv > 0 and (cv < ma25_v) and (not ma25_slope_up))
    strong_daily_weekly_bull = bool(d_ctx.get("bull_po", False) and (poc_10y <= 0.0 or cv <= 0.0 or cv >= poc_10y))

    if spec["allow_short"] and (not is_jp_t3):
        bull_edge, bear_edge = compute_directional_edges(ofi_z, rsi, prev_trend_weak, hurst, upper_wick_pressure, lower_wick_support, rel_news_title=rel_news_title, rs_alpha=rs_alpha, below_vwap=below_vwap, daily_ctx=d_ctx, macro_10y=m10, cv=cv)
        if ((not has_vwap) or (cv < vwap_today)) and ofi_z <= -0.35 and (bear_edge >= bull_edge + 6.0) and bear_edge >= 14.0: return "Type-S1"
        if not strong_daily_weekly_bull:
            strong_bandwalk = bool(hurst >= 0.56 and ((not has_vwap) or (cv > vwap_today * 1.002)) and (lower_wick_support > upper_wick_pressure))
            if not strong_bandwalk and rsi >= 66.0 and upper_wick_pressure >= 38.0 and ((ofi_z <= 0.10) or (has_vwap and cv <= vwap_today * 1.003)) and (bear_edge >= bull_edge + 3.0) and bear_edge >= 11.0:
                return "Type-S2"

    if daily_clear_downtrend: return "Type-E"
    is_good_news = bool(rel_news_title) and not any(bw in rel_news_title for bw in BEARISH_NEWS_KEYWORDS) and not (below_vwap and upper_wick_pressure >= 35.0)
    if is_good_news or ofi_z >= 0.55 or strong_daily_weekly_bull: return "Type-A"
    if pgap >= 0.8 or rsi >= 60.0 or d_ctx.get("is_52w_break", False): return "Type-B"
    if ms.get("kyle_stealth", 0) >= 56.0 or hurst >= 0.53: return "Type-C"
    if qm.get("q_tunnel", 0) >= 60.0: return "Type-D"
    return "Type-E"

def _build_beginner_guide_html(disp_name: str, style_title: str, q1: str, q2: str, q3: str, q4: str) -> str:
    return (
        f"<b>🔰 {html.escape(disp_name)} {html.escape(style_title)}</b><br>"
        f"<b>💡 1. なぜ今この銘柄に注目なのか？（やさしい現状解説）</b><br>{q1}<br>"
        f"<b>🛒 2. どうやって買えばいい？（失敗しない注文の出し方と理由）</b><br>{q2}<br>"
        f"<b>💰 3. どこで利益確定する？（欲張りすぎないコツ）</b><br>{q3}<br>"
        f"<b>🛡️ 4. もし予想と逆に下がったら？（資産を守る保険のかけ方）</b><br>{q4}"
    )

def select_dynamic_strategy(code: str, style: str, ofi_z: float, vpin: float, cvar95: float, rsi: float, lot_info: dict, pest_str: str, vwap_str: str, tp_str: str, sl_str: str, qm: dict, ms: dict, name: str = "", theme: str = "", rel_news_title: str = "", pgap: float = 0.0, expect_pct: float = 50.0, prev_trend_weak: bool = False, full_code: str = "", genre: str = "", upper_wick_pressure: float = 0.0, lower_wick_support: float = 0.0, cv: float = 0.0, vwap_today: float = 0.0, rs_alpha: float = 0.0, macro_10y: dict = None, daily_2y: dict = None) -> dict:
    spec = get_style_spec(style); pfx = spec["pfx"]
    sh = int(lot_info["shares"]); odd_note = "（※単元未満株・S株換算）" if lot_info.get("is_odd_lot") else ""
    disp_name = name or code; part_sh = max(1, int(round(sh * 0.50))); rem_sh = max(0, sh - part_sh)
    m10, d2y = macro_10y or {}, daily_2y or {}
    m10_lbl, m10_poc_s, m10_cagr = str(m10.get("regime_10y_label", "10年大局中立")), str(m10.get("poc_10y_str", "-")), float(m10.get("cagr_10y", 0.0))
    d2y_lbl, d2y_ma, d2y_ma5_s, d2y_ma25_s, d2y_ma75_s, d2y_ma200_s = str(d2y.get("regime_1d_label", "日足中立")), str(d2y.get("ma_align_label", "MA均衡")), str(d2y.get("ma5_str", "-")), str(d2y.get("ma25_str", "-")), str(d2y.get("ma75_str", "-")), str(d2y.get("ma200_str", "-"))
    fc_eval = full_code or (f"{code}.T" if re.match(r"^[0-9]{3}[0-9A-Z]$", str(code)) else str(code))
    tactic_type = determine_tactic_classification(fc_eval, genre, ofi_z, vpin, rsi, pgap, expect_pct, prev_trend_weak, qm, ms, rel_news_title=rel_news_title, style=style, upper_wick_pressure=upper_wick_pressure, lower_wick_support=lower_wick_support, cv=cv, vwap_today=vwap_today, rs_alpha=rs_alpha, daily_ctx=d2y, macro_10y=m10)

    if tactic_type in ("Type-S1", "Type-S2") and spec["allow_short"]:
        is_s2 = (tactic_type == "Type-S2")
        s_tag = "過熱・上ヒゲ拒絶VWAP割れ" if is_s2 else "資金流出VWAP割れ順張り"
        return {
            "style_name": pfx, "tf": spec["tf"], "side": "SHORT", "tactic_type": tactic_type,
            "entry_mode": f"【空売り】{s_tag}次バー始値＋50%利確",
            "algo_name": f"{'🟣' if is_s2 else '🔴'} [{pfx} / {tactic_type} 空売り] {s_tag}次バー始値空売り ＋ +1.0R 50%買い戻し型",
            "risk_posture": f"📉 空売り一括 <b>{sh:,}株</b> → +1.0Rで50%(<b>{part_sh:,}株</b>)利確＋次バー以降建値ロック{odd_note}",
            "core_logic": f"週足10年『{html.escape(m10_lbl)}』×日足2年『{html.escape(d2y_lbl)}』の抵抗帯を背に、5分足VWAP（{vwap_str}）割れの陰線確定後、次バー始値で空売り（SHORT）を実行し反落幅を収益化します。",
            "adj_shares": sh, "trade_duration": spec["dur"],
            "step_plan": f"① 【5分足VWAP割れ次バー始値空売り】9:05〜13:30に当日VWAP（<b>{vwap_str}</b>）または5本EMAを割り込む陰線確定後、次バー始値で<b>{sh:,}株</b>{odd_note}を一括信用新規売り（逆指値<b>{sl_str}</b>）。<br>② 【+1.0R 50%買い戻し＋建値ロック】損切り幅と同じ利益(+1.0R)到達で<b>{part_sh:,}株</b>を買い戻し利確、次バー以降に残り<b>{rem_sh:,}株</b>の逆指値を建値以下へロックして目標<b>{tp_str}</b>へ。",
            "beginner_html": _build_beginner_guide_html(
                disp_name, f"{spec['beg_title']}（空売り・下落狙い）",
                f"過去1ヶ月平均（MA25: <b>{html.escape(d2y_ma25_s)}</b>）や過去10年売買集中帯（<b>{html.escape(m10_poc_s)}</b>）の節目で買いの勢いが一服し、上値が重くなっている波です。",
                f"焦って成行売りせず、9:05〜13:30の間に今日の平均約定価格（<b>{vwap_str}</b>）を下に抜けて陰線が確定した次の足で<b>{sh:,}株</b>{odd_note}を信用新規売りします（高値掴みならぬ安値売り防止）。",
                f"利益が損切り幅と同額（+1.0R）になったら、まず半分（<b>{part_sh:,}株</b>）を買い戻して利益を確定し、心の余裕を作ってから残り<b>{rem_sh:,}株</b>で目標<b>{tp_str}</b>を狙います。",
                f"予想と逆に上がってしまった場合に備え、注文と同時に<b>{sl_str}</b>に買い戻しの逆指値（損切り予約）を入れ、損失拡大を確実に防ぎます。"
            )
        }

    if pfx == "スキャルピング":
        entry_mode = "【買い】前場OR15維持・5分足VWAP/5EMA押し目ブレイク"
        algo_name = f"🚀 [スキャルピング / {tactic_type} 買い] 前場9:05〜11:00集中・OR15安値維持＆5分足VWAP/5EMA押し目＋高値更新次バー始値型"
        risk_posture = f"⚡ 素早い回転売買 <b>{sh:,}株</b> → +1.0Rで50%(<b>{part_sh:,}株</b>)即利確＋建値ロック{odd_note}"
        core_logic = f"流動性と板の勢いが最も集中する前場（9:05〜11:00）に特化。OR15分安値を維持しつつ5分足VWAP（{vwap_str}）および5本EMAへの浅い押し目確認後、前バー高値を上抜く陽線確定の次バー始値で素早く約定します。"
        step_plan = f"① 【前場OR15維持・5分足押し目ブレイク】9:05〜11:00の前場トレンド時間帯に、OR15分安値を維持したまま5分足VWAP（<b>{vwap_str}</b>）または5本EMA付近で下げ止まり、前バー高値を上抜く陽線確定の次バー始値で<b>{sh:,}株</b>{odd_note}を素早く買い約定（逆指値<b>{sl_str}</b>）。<br>② 【+1.0R即半分利確＆当日大引け完結】ATR×0.45基準のタイトな損切り幅に対し+1.0R到達で即座に<b>{part_sh:,}株</b>を利確、残りは建値ロックして目標<b>{tp_str}</b>を狙い、当日大引けまでに必ず手仕舞い。"
        q1 = f"直近の出来高と値動きの勢いが非常に活発で、過去1ヶ月平均（MA25: <b>{html.escape(d2y_ma25_s)}</b>）のトレンドに乗りながら短期資金が集中している強い波です。"
        q2 = f"最も動きが素直な前場（9:05〜11:00）に絞り、急騰への飛びつき（高値掴み）を避けてOR15分安値維持＆今日の平均価格（<b>{vwap_str}</b>）付近で反発した瞬間に<b>{sh:,}株</b>{odd_note}を指値・逆指値で素早く買います。"
        q3 = f"スキャルピングは欲張らないのが鉄則です。損切り幅と同じ利益（+1.0R）が出たら即座に半分（<b>{part_sh:,}株</b>）を利確して心の余裕を作り、残りは建値に保険をかけて目標<b>{tp_str}</b>まで伸ばします。"
        q4 = f"勢いが止まって逆行したら一瞬で逃げるため、約定と同時に<b>{sl_str}</b>へ逆指値（自動損切り予約）を必ず設定し、その日のうちに必ず決済して翌日へ持ち越しません。"
    elif pfx == "デイトレード":
        entry_mode = "【買い】9:05〜13:30 OR15維持・VWAP押し目＋50%利確"
        algo_name = f"⚡ [デイトレード / {tactic_type} 買い] OR15分安値維持＆5分足VWAP押し目反発次バー始値 ＋ +1.0R半分利確・14:30手仕舞い型"
        risk_posture = f"🚀 デイトレ一括 <b>{sh:,}株</b> → +1.0Rで50%(<b>{part_sh:,}株</b>)利確＋14:30手仕舞い{odd_note}"
        core_logic = f"週足10年『{html.escape(m10_lbl)}』×日足2年『{html.escape(d2y_lbl)}』の追い風を受け、9:05〜13:30の間にOR15分安値を維持しつつ5分足VWAP（{vwap_str}）への押し目反発＋前バー高値更新陽線確定の次バー始値で買い約定します。"
        step_plan = f"① 【9:05〜13:30 OR15維持＆5分足VWAP押し目待ち】朝イチの乱高下を見送り、9:05〜13:30にOR15分安値を維持したまま5分足VWAP（<b>{vwap_str}</b>）付近への押し目確認＋前バー高値更新陽線確定の次バー始値で<b>{sh:,}株</b>{odd_note}を買い約定（逆指値<b>{sl_str}</b>）。<br>② 【+1.0R半分利確＆14:30手仕舞い】+1.0R到達で<b>{part_sh:,}株</b>を利確して建値ロック、目標<b>{tp_str}</b>を追いつつ14:30までに全決済してオーバーナイトリスクをゼロにします。"
        q1 = f"過去1ヶ月平均（MA25: <b>{html.escape(d2y_ma25_s)}</b>）および過去10年平均帯（<b>{html.escape(m10_poc_s)}</b>）を上回る上昇の波にあり、1日の中で素直な押し目買いが機能しやすい状態です。"
        q2 = f"高値掴みを防ぐため朝一番の飛びつき買いは我慢し、9:05〜13:30の間にOR15分安値を割っていないことと今日の平均約定価格（<b>{vwap_str}</b>）付近で反発したのを確認してから<b>{sh:,}株</b>{odd_note}を注文します。"
        q3 = f"目標は<b>{tp_str}</b>ですが、途中で損切り幅と同額（+1.0R）の利益が出たらまず半分（<b>{part_sh:,}株</b>）を利確して利益を確保し、心の余裕を持って14:30の手仕舞い時間まで伸ばします。"
        q4 = f"予想に反して平均価格を割り込み<b>{sl_str}</b>まで下がった場合は、逆指値（自動損切り保険）で一度撤退し、損失を限定して次のチャンスに資金を残します。"
    elif pfx == "スイングトレード":
        entry_mode = "【買い】日足MA25・MA5押し目確定翌営業日始値（数日〜2週間保有）"
        algo_name = f"📈 [スイングトレード / {tactic_type} 買い] 日足25日・5日移動平均線押し目反発＋最大10営業日トレンド追従型"
        risk_posture = f"📈 スイング保有 <b>{sh:,}株</b> → +1.0Rで50%(<b>{part_sh:,}株</b>)利確＋逆指値トレール{odd_note}"
        core_logic = f"日足25日移動平均線（{html.escape(d2y_ma25_s)}）の上向きトレンドおよび75日線（{html.escape(d2y_ma75_s)}）支持を軸に、日足終値がMA5（{html.escape(d2y_ma5_s)}）またはMA25付近へ押し目形成後の陽線確定翌営業日始値で買い約定し、数日〜2週間（最大10営業日）の波を捉えます。"
        step_plan = f"① 【日足MA25・MA5押し目確定＆翌朝寄付き/14:50エントリー】日足チャートで25日線（<b>{html.escape(d2y_ma25_s)}</b>）または5日線（<b>{html.escape(d2y_ma5_s)}</b>）付近での下値支持と陽線確定を確認後、翌営業日の寄付き（または大引け前14:50の引け成行/指値）で<b>{sh:,}株</b>{odd_note}を買い約定（逆指値<b>{sl_str}</b>）。<br>② 【数日〜2週間保有＆逆指値管理】最大10営業日を上限に保有し、+1.0R到達で<b>{part_sh:,}株</b>を分割利確・翌営業日以降に残り<b>{rem_sh:,}株</b>の逆指値を買値以上へ引き上げて目標<b>{tp_str}</b>を狙います。"
        q1 = f"過去1ヶ月平均（25日移動平均線: <b>{html.escape(d2y_ma25_s)}</b>）が上向きで、過去10年売買集中帯（<b>{html.escape(m10_poc_s)}</b>）も下支えしており、数日〜2週間かけてじわじわ上昇する中期トレンドの波に乗っています。"
        q2 = f"日中ずっと画面を見る必要はありません。日足で5日線（<b>{html.escape(d2y_ma5_s)}</b>）や25日線（<b>{html.escape(d2y_ma25_s)}</b>）付近まで押して陽線が出た翌朝の寄付き、または大引け直前（14:50）に<b>{sh:,}株</b>{odd_note}を落ち着いて買います（急騰日の高値飛びつき厳禁）。"
        q3 = f"数日〜2週間かけて目標<b>{tp_str}</b>を目指します。途中で損切り幅と同じ利益（+1.0R）が出たら半分（<b>{part_sh:,}株</b>）を先に利確しておくと、残りは「負けない状態」でゆったり大きな値幅を狙えます。"
        q4 = f"寝ている間のニュース等で急落しても資産を守れるよう、買ったら必ず<b>{sl_str}</b>（25日線や直近5日安値割れ水準）に逆指値（損切り予約）を入れておき、塩漬けを絶対に防ぎます。"
    else:
        tranche1_sh = max(1, (part_sh // 100) * 100) if (".T" in fc_eval and sh >= 200) else part_sh
        tranche2_sh = max(0, sh - tranche1_sh)
        entry_mode = "【買い】週足10年POC・日足75/200日線基準 2回分割時間分散買い"
        algo_name = f"💎 [バイ＆ホールド / {tactic_type} 買い] 週足10年POC×日足75/200日線サポート・2回分割時間分散中長期保有型"
        risk_posture = f"💎 2回分割買い 計<b>{sh:,}株</b>（1回目<b>{tranche1_sh:,}株</b>＋2回目<b>{tranche2_sh:,}株</b>）＋広め損切り{odd_note}"
        core_logic = f"過去10年週足の最大出来高価格帯POC（{html.escape(m10_poc_s)}・10年CAGR {m10_cagr:+.1f}%）と日足75日線（{html.escape(d2y_ma75_s)}）・200日線（{html.escape(d2y_ma200_s)}）の岩盤サポート帯を基準に、資金を2回に分けて時間分散エントリーし最大20営業日〜中長期で資産成長を狙います。"
        step_plan = f"① 【2回に分ける分割買い（時間分散）】週足10年POC（<b>{html.escape(m10_poc_s)}</b>）や日足75日線（<b>{html.escape(d2y_ma75_s)}</b>）・200日線（<b>{html.escape(d2y_ma200_s)}</b>）の支持帯反発を確認後、まず1回目として<b>{tranche1_sh:,}株</b>{odd_note}を翌営業日始値で買い、数日〜1週間後の押し目確認時に残り<b>{tranche2_sh:,}株</b>を追加して平均取得単価を平準化します。<br>② 【広い損切り設定と中長期保有】一時的なノイズで振り落とされないようATR×2.5基準の広い逆指値（<b>{sl_str}</b>）を設定し、+1.0R到達で半分利確＋建値ロックを行いながら目標<b>{tp_str}</b>（最大20営業日・中長期トレンド継続）を保有します。"
        q1 = f"過去10年間の年率成長率（CAGR <b>{m10_cagr:+.1f}%</b>）と10年分の売買が最も集中した岩盤ライン（<b>{html.escape(m10_poc_s)}</b>）、さらに過去3ヶ月〜1年平均（75日線 <b>{html.escape(d2y_ma75_s)}</b> / 200日線 <b>{html.escape(d2y_ma200_s)}</b>）に支えられた王道の中長期上昇トレンドです。"
        q2 = f"一度に全額を買うと高値掴みのリスクがあるため、予算を2回に分ける「時間分散買い」を行います。まず1回目に<b>{tranche1_sh:,}株</b>{odd_note}を買い、数日〜1週間後に相場が落ち着いたタイミングで残り<b>{tranche2_sh:,}株</b>を買い増します。"
        q3 = f"中長期の大きな波で目標<b>{tp_str}</b>を狙います。株価が大きく伸びて損切り幅と同額（+1.0R）の含み益になったら半分（<b>{part_sh:,}株</b>）を利確し、残りは買値に逆指値を移して安心して長期保有を続けます。"
        q4 = f"日々の小さな上下動で慌てて売らないよう、通常より広めの<b>{sl_str}</b>（直近20日安値や200日線割れ水準）に逆指値（資産防衛の保険）を設定し、大局トレンドが崩れた場合のみ一度撤退します。"

    return {
        "style_name": pfx, "tf": spec["tf"], "side": "LONG", "tactic_type": tactic_type,
        "entry_mode": entry_mode, "algo_name": algo_name, "risk_posture": risk_posture,
        "core_logic": core_logic, "adj_shares": sh, "trade_duration": spec["dur"], "step_plan": step_plan,
        "beginner_html": _build_beginner_guide_html(disp_name, spec["beg_title"], q1, q2, q3, q4)
    }

def _is_market_open_now(is_jp: bool) -> bool:
    now_dt = datetime.now()
    if is_jp:
        if now_dt.weekday() >= 5: return False
        mins = now_dt.hour * 60 + now_dt.minute
        return (9 * 60) <= mins <= (15 * 60 + 30)
    now_utc = datetime.now(timezone.utc)
    if now_utc.weekday() >= 5: return False
    utc_mins = now_utc.hour * 60 + now_utc.minute
    return (13 * 60 + 30) <= utc_mins <= (21 * 60)

def _build_historical_daily_slice_ctx(df_daily_clean: pd.DataFrame, prev_d: str, fallback_close: float, full_code: str = "", df_weekly_clean: pd.DataFrame = None) -> dict:
    default_ctx = {"ma5": fallback_close, "ma25": fallback_close, "ma75": fallback_close, "ma200": fallback_close, "ma25_slope_up": True, "bull_po": False, "bear_po": False, "macd_hist": 0.0, "pos_52w_pct": 50.0, "daily_atr14": fallback_close * 0.015, "prev_trend_weak": False, "poc_10y_price": 0.0, "pos_10y_pct": 50.0, "ma200w_dev_pct": 0.0, "has_data": False}
    if df_daily_clean is None or df_daily_clean.empty: return default_ctx
    sub = df_daily_clean[df_daily_clean["_d_str"] <= prev_d]
    if sub.empty: return default_ctx
    h, l, c = [np.asarray(sub[col].values, dtype=float).reshape(-1) for col in ["High", "Low", "Close"]]
    v = np.asarray(sub["Volume"].values, dtype=float).reshape(-1) if "Volume" in sub.columns else np.ones_like(c)
    px = float(c[-1])
    ma5, ma25, ma75, ma200 = [float(np.mean(c[-min(k, len(c)):])) for k in (5, 25, 75, 200)]
    ma25_slope_up = bool(ma25 >= (float(np.mean(c[-min(30, len(c)):-5])) if len(c) >= 10 else ma25))
    bull_po = bool((px > ma5 > ma25 > ma75) and ma25_slope_up)
    bear_po = bool((px < ma5 < ma25 < ma75) and (not ma25_slope_up))
    c_s = pd.Series(c); macd_s = c_s.ewm(span=12, adjust=False).mean() - c_s.ewm(span=26, adjust=False).mean()
    macd_hist = float((macd_s - macd_s.ewm(span=9, adjust=False).mean()).iloc[-1])
    n_52w = min(252, len(c)); hi_52w, lo_52w = float(np.max(h[-n_52w:])), float(np.min(l[-n_52w:]))
    pos_52w_pct = float(np.clip(((px - lo_52w) / max(hi_52w - lo_52w, 1e-4)) * 100.0, 0.0, 100.0))
    prev_c = np.roll(c, 1); prev_c[0] = c[0]; tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    daily_atr14 = max(float(np.mean(tr[-min(14, len(tr)):])), px * 0.0115)
    prev_trend_weak = bool(px < ma25 * 0.992) if len(c) >= 5 else False

    w_sub = df_weekly_clean[df_weekly_clean["_w_str"] <= prev_d] if (df_weekly_clean is not None and not df_weekly_clean.empty and "_w_str" in df_weekly_clean.columns) else None
    if w_sub is not None and len(w_sub) >= 4:
        wh, wl, wc = [np.asarray(w_sub[col].values, dtype=float).reshape(-1) for col in ["High", "Low", "Close"]]
        wv = np.asarray(w_sub["Volume"].values, dtype=float).reshape(-1) if "Volume" in w_sub.columns else np.ones_like(wc)
        hi_10y, lo_10y = float(np.max(wh)), float(np.min(wl)); pos_10y_pct = float(np.clip(((px - lo_10y) / max(hi_10y - lo_10y, 1e-4)) * 100.0, 0.0, 100.0))
        bins = np.linspace(lo_10y, hi_10y + 1e-4, 16); vol_profile = np.bincount(np.clip(np.digitize((wh + wl + wc) / 3.0, bins) - 1, 0, 14), weights=np.maximum(wv, 1.0), minlength=15)
        poc_bin = int(np.argmax(vol_profile)); poc_raw = float((bins[poc_bin] + bins[poc_bin + 1]) * 0.5)
        poc_10y_price = round_to_tse_tick(poc_raw, full_code, "nearest") if full_code else poc_raw
        ma200w = float(np.mean(wc[-min(200, len(wc)):])); ma200w_dev_pct = float(((px - ma200w) / max(ma200w, 1e-4)) * 100.0)
    else:
        hi_hist, lo_hist = float(np.max(h)), float(np.min(l)); pos_10y_pct = float(np.clip(((px - lo_hist) / max(hi_hist - lo_hist, 1e-4)) * 100.0, 0.0, 100.0))
        bins = np.linspace(lo_hist, hi_hist + 1e-4, 16); vol_profile = np.bincount(np.clip(np.digitize((h + l + c) / 3.0, bins) - 1, 0, 14), weights=np.maximum(v, 1.0), minlength=15)
        poc_bin = int(np.argmax(vol_profile)); poc_raw = float((bins[poc_bin] + bins[poc_bin + 1]) * 0.5)
        poc_10y_price = round_to_tse_tick(poc_raw, full_code, "nearest") if full_code else poc_raw
        ma200w_dev_pct = float(((px - ma200) / max(ma200, 1e-4)) * 100.0)
    return {"ma5": ma5, "ma25": ma25, "ma75": ma75, "ma200": ma200, "ma25_slope_up": ma25_slope_up, "bull_po": bull_po, "bear_po": bear_po, "macd_hist": macd_hist, "pos_52w_pct": pos_52w_pct, "daily_atr14": daily_atr14, "prev_trend_weak": prev_trend_weak, "poc_10y_price": poc_10y_price, "pos_10y_pct": pos_10y_pct, "ma200w_dev_pct": ma200w_dev_pct, "has_data": True}

def record_and_verify_daily_Forward_test(df: pd.DataFrame, full_code: str, strat: dict, pest: float, vwap20: float, tpv: float, slv: float, shares: int, style: str, total_capital: float = 1000000.0, risk_tolerance_pct: float = 2.0, shared_ledger: dict = None, save_db: bool = True, genre: str = "", daily_2y: dict = None, macro_10y: dict = None, active_boosts: tuple = ("core_inst", "core_mom", "core_vol")) -> dict:
    is_jp = ".T" in full_code; now_dt = datetime.now(); today_str = now_dt.strftime("%Y-%m-%d"); today_utc_str = datetime.now(timezone.utc).strftime("%Y-%m-%d"); is_market_open = _is_market_open_now(is_jp)
    combat_prof = get_ticker_combat_profile(full_code, genre)
    BASE_COST_RATE, max_gu_limit = float(combat_prof["cost_rate"]), float(combat_prof["max_gu_limit"])
    is_tier3_small = is_jp_tier3_short_restricted(full_code, genre, combat_prof)
    spec = get_style_spec(style); st_p, max_hold_days = spec["pfx"], int(spec["max_hold_days"])
    tactic_type = strat.get("tactic_type", "Type-E"); entry_mode = strat.get("entry_mode", "確定後次バー始値一括約定")
    plan_entry_price = round_to_tse_tick(float(vwap20 if tactic_type != "Type-D" else pest), full_code, "nearest")

    d2y, m10 = daily_2y or {}, macro_10y or {}
    df_daily_clean, df_weekly_clean, daily_rs_alpha_map = d2y.get("df_daily_clean"), m10.get("df_weekly_clean"), d2y.get("daily_rs_alpha_map", {})
    boosts_key = "_".join(sorted([str(b) for b in (active_boosts or ())]))
    ledger_key = f"{full_code}__{st_p}__{boosts_key}"
    ledger = shared_ledger if shared_ledger is not None else db_get("daily_forward_ledger", {})
    if not isinstance(ledger, dict): ledger = {}
    with _DB_LOCK:
        existing_sl = ledger.get(ledger_key)
        stock_ledger = {"signals": dict(existing_sl.get("signals", {})), "verified": dict(existing_sl.get("verified", {})), "algo_ver": existing_sl.get("algo_ver", "")} if isinstance(existing_sl, dict) else {"signals": {}, "verified": {}, "algo_ver": ""}

    ALGO_VERSION_TAG = "QWM27_VWAP2S_LIMITUP_OB"
    if stock_ledger.get("algo_ver") != ALGO_VERSION_TAG:
        stock_ledger["verified"], stock_ledger["algo_ver"] = {}, ALGO_VERSION_TAG

    PARTIAL_RATIO, REMAINING_RATIO, BASE_LOT = 0.50, 0.50, (100 if is_jp else 1)

    if spec["tf"] == "1d" and df_daily_clean is not None and len(df_daily_clean) >= 35:
        d_dates = sorted(df_daily_clean["_d_str"].unique().tolist())
        latest_d_date = d_dates[-1] if d_dates else today_str
        unconf_dates = {today_str, today_utc_str, latest_d_date} if is_market_open else set()
        if unconf_dates:
            for k_v, v_rec in list(stock_ledger["verified"].items()):
                if k_v in unconf_dates or v_rec.get("exit_date", k_v) in unconf_dates: del stock_ledger["verified"][k_v]
        stock_ledger["signals"][today_str] = {"date": today_str, "entry_type": entry_mode, "tactic_type": tactic_type, "plan_entry_price": round(plan_entry_price, 4), "tp_val": round(float(tpv), 4), "sl_val": round(float(slv), 4), "style": style}
        try:
            start_i = max(25, len(d_dates) - 35)
            for idx_prev in range(start_i, len(d_dates) - 1):
                prev_d, entry_d = d_dates[idx_prev], d_dates[idx_prev + 1]
                if entry_d in stock_ledger["verified"] or entry_d in unconf_dates: continue
                sub_prev = df_daily_clean[df_daily_clean["_d_str"] <= prev_d]
                if len(sub_prev) < 25: continue
                p_close, p_open, p_low = float(sub_prev["Close"].iloc[-1]), float(sub_prev["Open"].iloc[-1]), float(sub_prev["Low"].iloc[-1])
                hist_ctx = _build_historical_daily_slice_ctx(df_daily_clean, prev_d, p_close, full_code=full_code, df_weekly_clean=df_weekly_clean)
                ma5_p, ma25_p, ma75_p, ma200_p = hist_ctx["ma5"], hist_ctx["ma25"], hist_ctx["ma75"], hist_ctx["ma200"]
                poc_10y_p, p_atr = hist_ctx["poc_10y_price"], hist_ctx["daily_atr14"]

                if st_p == "スイングトレード":
                    trend_ok = bool((hist_ctx["ma25_slope_up"] and p_close >= ma25_p * 0.985) or (p_close >= ma75_p))
                    pullback_ok = bool((p_low <= ma5_p * 1.012) or (p_low <= ma25_p * 1.015))
                    bull_candle_ok = bool((p_close > p_open) and (p_close >= ma5_p * 0.992))
                    sig_ok = trend_ok and pullback_ok and bull_candle_ok
                    plan_lbl = "スイング(MA5/25押し目陽線)"
                else:
                    support_ok = bool((poc_10y_p > 0 and p_close >= poc_10y_p * 0.985) or (p_close >= ma75_p * 0.985) or (p_close >= ma200_p * 0.985))
                    rebound_ok = bool((p_low <= max(ma75_p, ma200_p, poc_10y_p) * 1.025) and (p_close > p_open))
                    sig_ok = support_ok and rebound_ok
                    plan_lbl = "バイ&ホールド(支持帯反発)"

                hold_dates = d_dates[idx_prev + 1 : idx_prev + 1 + max_hold_days]
                span_d = df_daily_clean[df_daily_clean["_d_str"].isin(hold_dates)]
                if span_d.empty: continue
                if not sig_ok:
                    stock_ledger["verified"][entry_d] = {"date": entry_d, "entry_date": entry_d, "entry_hm": "09:00", "exit_date": entry_d, "hold_days": 1, "signal_date": prev_d, "plan_short": plan_lbl, "entry_price": round(p_close, 4), "exit_price": round(p_close, 4), "entry_str": f"待機 {fmt_px(p_close, is_jp, full_code)}", "exit_str": "未約定", "outcome": "⚪ 日足押し目/支持条件未到達・見送り (NO TRADE)", "result_category": "NOTRADE", "is_win": None, "return_pct": 0.0, "r_mult": 0.0, "base_100_profit": 0.0}
                    continue

                look_lb = 5 if st_p == "スイングトレード" else 20
                rec_lows = sub_prev["Low"].values[-look_lb:].astype(float)
                entry_px = apply_unfavorable_tick_slip(float(span_d["Open"].iloc[0]), full_code, is_long_entry_or_short_exit=True)
                sl_d, tp_d = compute_style_tp_sl_deltas(entry_px, p_atr, False, style, combat_prof, full_code, recent_lows=rec_lows)
                eff_tp = round_to_tse_tick(entry_px + tp_d, full_code, "ceil")
                if is_jp and p_close > 0:
                    lim_up_1d = p_close + get_tse_price_limit(p_close)
                    tick_1d = get_tse_tick_step(lim_up_1d, full_code)
                    if eff_tp >= lim_up_1d:
                        eff_tp = round_to_tse_tick(max(lim_up_1d - tick_1d, entry_px + sl_d * 1.1), full_code, "floor")
                eff_sl = round_to_tse_tick(max(entry_px - sl_d, entry_px * 0.5), full_code, "floor")
                half_trig_px = round_to_tse_tick(entry_px + sl_d, full_code, "ceil")
                half_done, half_px, half_day_idx = False, 0.0, -1
                pending_be, outcome, result_cat, exit_px, exit_date_act, hold_days_act, realized_ret, r_mult = None, "", "NOTRADE", 0.0, entry_d, 1, 0.0, 0.0

                for d_i in range(len(span_d)):
                    row_d = span_d.iloc[d_i]
                    cur_d_str = str(row_d["_d_str"])
                    do, dh, dl, dc = float(row_d["Open"]), float(row_d["High"]), float(row_d["Low"]), float(row_d["Close"])
                    if pending_be is not None and d_i > half_day_idx:
                        eff_sl = max(eff_sl, pending_be); pending_be = None
                    if d_i > 0 and do <= eff_sl:
                        sl_fill = apply_unfavorable_tick_slip(min(do, eff_sl), full_code, False)
                        exit_px = (PARTIAL_RATIO * half_px + REMAINING_RATIO * sl_fill) if half_done else sl_fill
                        realized_ret = ((PARTIAL_RATIO * ((half_px - entry_px) / entry_px) + REMAINING_RATIO * ((sl_fill - entry_px) / entry_px)) - BASE_COST_RATE) if half_done else (((sl_fill - entry_px) / entry_px) - BASE_COST_RATE)
                        exit_date_act, hold_days_act = cur_d_str, d_i + 1
                        r_mult = realized_ret / max(sl_d / entry_px, 0.005)
                        outcome, result_cat = (f"⭕ [買い]50%利確後建値ロック完遂 (+{r_mult:.2f}R) [{hold_days_act}日保有] (WIN)", "WIN") if r_mult >= 0.15 else (f"⚖️ [買い]建値撤退 ({r_mult:+.2f}R) [{hold_days_act}日保有] (SCRATCH)", "SCRATCH") if r_mult > -0.15 else (f"🛡️ [買い]逆指値損切 ({r_mult:.2f}R) [{hold_days_act}日保有] (LOSE)", "LOSE")
                        break
                    if dl <= eff_sl:
                        sl_fill = apply_unfavorable_tick_slip(eff_sl, full_code, False)
                        exit_px = (PARTIAL_RATIO * half_px + REMAINING_RATIO * sl_fill) if half_done else sl_fill
                        realized_ret = ((PARTIAL_RATIO * ((half_px - entry_px) / entry_px) + REMAINING_RATIO * ((sl_fill - entry_px) / entry_px)) - BASE_COST_RATE) if half_done else (((sl_fill - entry_px) / entry_px) - BASE_COST_RATE)
                        exit_date_act, hold_days_act = cur_d_str, d_i + 1
                        r_mult = realized_ret / max(sl_d / entry_px, 0.005)
                        outcome, result_cat = (f"⭕ [買い]50%利確後建値ロック完遂 (+{r_mult:.2f}R) [{hold_days_act}日保有] (WIN)", "WIN") if r_mult >= 0.15 else (f"⚖️ [買い]建値撤退 ({r_mult:+.2f}R) [{hold_days_act}日保有] (SCRATCH)", "SCRATCH") if r_mult > -0.15 else (f"🛡️ [買い]逆指値損切 ({r_mult:.2f}R) [{hold_days_act}日保有] (LOSE)", "LOSE")
                        break
                    if dh >= eff_tp:
                        tp_fill = max(do, eff_tp) if (d_i > 0 and do >= eff_tp) else eff_tp
                        if not half_done:
                            half_done = True
                            half_px = max(do, half_trig_px) if (d_i > 0 and do >= half_trig_px) else half_trig_px
                        exit_px = PARTIAL_RATIO * half_px + REMAINING_RATIO * tp_fill
                        realized_ret = (PARTIAL_RATIO * ((half_px - entry_px) / entry_px) + REMAINING_RATIO * ((tp_fill - entry_px) / entry_px)) - BASE_COST_RATE
                        exit_date_act, hold_days_act = cur_d_str, d_i + 1
                        r_mult = realized_ret / max(sl_d / entry_px, 0.005)
                        outcome, result_cat = f"⭕ [買い]50%分割＋目標到達完遂 (+{r_mult:.2f}R) [{hold_days_act}日保有] (WIN)", "WIN"
                        break
                    if (not half_done) and dh >= half_trig_px:
                        half_done = True; half_px = max(do, half_trig_px) if (d_i > 0 and do >= half_trig_px) else half_trig_px; half_day_idx = d_i
                        pending_be = round_to_tse_tick(entry_px * (1.0 + BASE_COST_RATE + 0.001), full_code, "ceil")

                if outcome == "":
                    if len(span_d) < max_hold_days or str(span_d["_d_str"].iloc[-1]) in unconf_dates: continue
                    close_fill = apply_unfavorable_tick_slip(float(span_d["Close"].iloc[-1]), full_code, False)
                    exit_px = (PARTIAL_RATIO * half_px + REMAINING_RATIO * close_fill) if half_done else close_fill
                    realized_ret = ((PARTIAL_RATIO * ((half_px - entry_px) / entry_px) + REMAINING_RATIO * ((close_fill - entry_px) / entry_px)) - BASE_COST_RATE) if half_done else (((close_fill - entry_px) / entry_px) - BASE_COST_RATE)
                    exit_date_act, hold_days_act = str(span_d["_d_str"].iloc[-1]), len(span_d)
                    r_mult = realized_ret / max(sl_d / entry_px, 0.005)
                    outcome, result_cat = (f"⭕ [買い]満期大引け利確 (+{r_mult:.2f}R) [{hold_days_act}日保有] (WIN)", "WIN") if r_mult >= 0.15 else (f"🛡️ [買い]満期大引け損切 ({r_mult:.2f}R) [{hold_days_act}日保有] (LOSE)", "LOSE") if r_mult <= -0.15 else (f"⚖️ [買い]建値撤退 ({r_mult:+.2f}R) [{hold_days_act}日保有] (SCRATCH)", "SCRATCH")

                ret_pct = realized_ret * 100.0; base_100_profit = (entry_px * BASE_LOT) * realized_ret
                is_win_bool = True if result_cat == "WIN" else (False if result_cat == "LOSE" else None)
                stock_ledger["verified"][entry_d] = {"date": exit_date_act, "entry_date": entry_d, "entry_hm": "09:00", "exit_date": exit_date_act, "hold_days": hold_days_act, "signal_date": prev_d, "plan_short": plan_lbl, "entry_price": round(entry_px, 4), "exit_price": round(exit_px, 4), "entry_str": fmt_px(entry_px, is_jp, full_code), "exit_str": fmt_px(exit_px, is_jp, full_code), "outcome": outcome, "result_category": result_cat, "is_win": is_win_bool, "return_pct": round(ret_pct, 2), "r_mult": round(float(r_mult), 2), "base_100_profit": round(base_100_profit, 2)}
        except Exception as e_1d: record_system_error("record_and_verify_daily_Forward_test:1d", e_1d, f"Code: {full_code}")
    else:
        bars_by_date = {d_k: g_df for d_k, g_df in df.groupby("_trade_date", sort=False)} if (df is not None and not df.empty and "_trade_date" in df.columns) else {}
        unique_dates = sorted(bars_by_date.keys())
        latest_trade_date = unique_dates[-1] if unique_dates else today_str
        unconf_dates = {today_str, today_utc_str, latest_trade_date} if is_market_open else set()
        if unconf_dates:
            for k_v, v_rec in list(stock_ledger["verified"].items()):
                if k_v in unconf_dates or v_rec.get("exit_date", k_v) in unconf_dates: del stock_ledger["verified"][k_v]
        stock_ledger["signals"][today_str] = {"date": today_str, "entry_type": entry_mode, "tactic_type": tactic_type, "plan_entry_price": round(plan_entry_price, 4), "tp_val": round(float(tpv), 4), "sl_val": round(float(slv), 4), "style": style}
        TACTIC_MODE_LABELS = {"Type-S2": "【空売り】過熱・WRV拒絶VWAP割れ", "Type-S1": "【空売り】資金流出VWAP割れ", "Type-A": "【買い】OR15維持+押し目高値更新始値", "Type-B": "【買い】OR15維持+押し目反発始値", "Type-C": "【買い】OR15維持+VWAP支持始値", "Type-D": "【買い】OR15高値ブレイク", "Type-E": "【買い】OR15維持+安値切上始値"}
        try:
            if len(unique_dates) >= 2:
                all_c, all_o, all_h, all_l, all_v = [np.asarray(df[col].values, dtype=float).reshape(-1) for col in ["Close", "Open", "High", "Low", "Volume"]]
                all_daily_5m = df.groupby("_trade_date").agg(Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"), Close=("Close", "last"), Volume=("Volume", "sum")).sort_index()
                date_end_pos = {}
                t_dates_arr = df["_trade_date"].values
                for pos_idx, td_val in enumerate(t_dates_arr):
                    date_end_pos[str(td_val)] = pos_idx + 1

                start_idx = max(0, len(unique_dates) - 35)
                for idx_prev in range(start_idx, len(unique_dates) - 1):
                    try:
                        prev_d, entry_d = unique_dates[idx_prev], unique_dates[idx_prev + 1]
                        if entry_d in stock_ledger["verified"] or entry_d in unconf_dates: continue
                        prev_bars, entry_day_bars = bars_by_date.get(prev_d), bars_by_date.get(entry_d)
                        if prev_bars is None or prev_bars.empty or entry_day_bars is None or entry_day_bars.empty: continue
                        end_p = date_end_pos.get(prev_d, 0)
                        if end_p <= 0: continue
                        p_close = float(prev_bars["Close"].iloc[-1]); p_vol = prev_bars["Volume"].values.astype(float)
                        p_typ = (prev_bars["High"].values + prev_bars["Low"].values + prev_bars["Close"].values) / 3.0
                        p_vwap = float(np.sum(p_typ * p_vol) / np.sum(p_vol)) if np.sum(p_vol) > 0 else p_close
                        hist_daily_5m = all_daily_5m.loc[:prev_d]
                        hist_daily_ctx = _build_historical_daily_slice_ctx(df_daily_clean, prev_d, p_close, full_code=full_code, df_weekly_clean=df_weekly_clean)
                        hist_macro_slice = {"poc_10y_price": hist_daily_ctx["poc_10y_price"], "pos_10y_pct": hist_daily_ctx["pos_10y_pct"], "ma200w_dev_pct": hist_daily_ctx["ma200w_dev_pct"], "has_data": hist_daily_ctx["has_data"]}
                        poc_hist_p, pos_hist_p, p_atr = float(hist_daily_ctx["poc_10y_price"]), float(hist_daily_ctx["pos_10y_pct"]), float(hist_daily_ctx["daily_atr14"])
                        rs_alpha_p, is_prev_trend_weak = float(daily_rs_alpha_map.get(prev_d, 0.0)), bool(hist_daily_ctx["prev_trend_weak"])

                        hc, ho, hh, hl, hv = all_c[:end_p], all_o[:end_p], all_h[:end_p], all_l[:end_p], all_v[:end_p]
                        hist_df_slice = df.iloc[:end_p]
                        ofi_p = compute_smoothed_clv_z(hc, hh, hl, hv, day_bars_count=len(prev_bars))
                        qa_p = compute_advanced_quant_indicators(hc, ho, hh, hl, hv, daily_df=hist_daily_5m, df=hist_df_slice) if len(hc) >= 20 else {"rsi": 50.0, "vpin": 0.50, "eff_pct": 50, "surge_attention_score": 50, "rvol": 1.0, "upper_wick_pressure": 0.0, "lower_wick_support": 0.0}
                        qm_p = compute_quantum_wave_metrics(hc, hh, hl, hv, o=ho, rsi_val=qa_p.get("rsi", 50.0), upper_wick_val=qa_p.get("upper_wick_pressure", 0.0)) if len(hc) >= 20 else {"q_tunnel": 50.0, "q_score": 50}
                        ms_p = compute_inst_microstructure(hc, hh, hl, hv) if len(hc) >= 20 else {"kyle_stealth": 50.0, "hurst": 0.50, "ms_score": 50}
                        r20_p = int(np.sum(np.diff(hc[-21:]) > 0)) if len(hc) >= 21 else 10
                        base_tech_p = float(np.clip((r20_p / 20.0) * 100.0 * 0.65 + (qa_p.get("eff_pct", 50) * 0.35), 10.0, 95.0))
                        inst_flow_p = float(np.clip(50.0 + ofi_p * 14.0 + (0.5 - qa_p.get("vpin", 0.50)) * 35.0, 10.0, 98.0))
                        tot_win_p = float(np.clip((base_tech_p + qm_p.get("q_score", 50) * 0.85 + ms_p.get("ms_score", 50) * 0.80 + inst_flow_p * 0.75 + qa_p.get("surge_attention_score", 50) * 0.65) / 4.05, 5.0, 97.8))
                        expect_pct_p = float(np.clip(tot_win_p * 0.85 + ofi_p * 3.8 + 6.0, 5.0, 99.5))
                        pgap_p = round(float(np.clip(ofi_p * 0.65, -2.5, 3.8)), 2); pest_p = round_to_tse_tick(p_close * (1.0 + pgap_p / 100.0), full_code, "nearest")
                        rsi_p, vpin_p, u_wick_p, l_wick_p = float(qa_p.get("rsi", 50.0)), float(qa_p.get("vpin", 0.50)), float(qa_p.get("upper_wick_pressure", 0.0)), float(qa_p.get("lower_wick_support", 0.0))

                        sig_tactic = determine_tactic_classification(full_code, genre, ofi_p, vpin_p, rsi_p, pgap_p, expect_pct_p, is_prev_trend_weak, qm_p, ms_p, rel_news_title="", style=style, upper_wick_pressure=u_wick_p, lower_wick_support=l_wick_p, cv=p_close, vwap_today=p_vwap, rs_alpha=rs_alpha_p, daily_ctx=hist_daily_ctx, macro_10y=hist_macro_slice)
                        sig_mode = TACTIC_MODE_LABELS.get(sig_tactic, "【買い】OR15維持+安値切上始値")
                        sig_plan_px = pest_p if sig_tactic == "Type-D" else round_to_tse_tick(p_vwap, full_code, "nearest")
                        is_short_sig = sig_tactic in ("Type-S1", "Type-S2")
                        bull_ep, bear_ep = compute_directional_edges(ofi_p, rsi_p, is_prev_trend_weak, float(ms_p.get("hurst", 0.50)), u_wick_p, l_wick_p, rel_news_title="", rs_alpha=rs_alpha_p, below_vwap=(p_close < p_vwap), daily_ctx=hist_daily_ctx, macro_10y=hist_macro_slice, cv=p_close)
                        exec_score_p, _, _ = evaluate_execution_quality_gate(is_short_sig, is_prev_trend_weak, p_close, p_vwap, int(qa_p.get("eff_pct", 50)), bull_ep, bear_ep, float(qa_p.get("rvol", 1.0)), float(combat_prof["min_rvol_req"]), u_wick_p, l_wick_p, daily_ctx=hist_daily_ctx, macro_10y=hist_macro_slice, rs_alpha=rs_alpha_p)

                        def _calc_structural_tp_sl(entry_px: float, is_short: bool, rec_lows: np.ndarray, rec_highs: np.ndarray) -> tuple:
                            sl_d, tp_d = compute_style_tp_sl_deltas(entry_px, p_atr, is_short, style, combat_prof, full_code, recent_lows=rec_lows, recent_highs=rec_highs)
                            if not is_short:
                                if pos_hist_p >= 90.0 and (poc_hist_p <= 0 or entry_px >= poc_hist_p): tp_d *= 1.10
                                elif poc_hist_p > entry_px and (poc_hist_p - entry_px) < tp_d: tp_d = max((poc_hist_p - entry_px) * 0.94, sl_d * 1.35)
                            if is_short:
                                tp_px = round_to_tse_tick(max(entry_px - tp_d, entry_px * 0.5), full_code, "floor")
                                sl_px = round_to_tse_tick(entry_px + sl_d, full_code, "ceil")
                                return (tp_px, sl_px, max(entry_px - tp_px, entry_px * 0.004), max(sl_px - entry_px, entry_px * 0.004))
                            tp_px = round_to_tse_tick(entry_px + tp_d, full_code, "ceil")
                            sl_px = round_to_tse_tick(max(entry_px - sl_d, entry_px * 0.5), full_code, "floor")
                            if is_jp and p_close > 0:
                                lim_up_5m = p_close + get_tse_price_limit(p_close)
                                tk_5m = get_tse_tick_step(lim_up_5m, full_code)
                                if tp_px >= lim_up_5m:
                                    tp_px = round_to_tse_tick(max(lim_up_5m - tk_5m, entry_px + sl_d * 1.1), full_code, "floor")
                            return (tp_px, sl_px, max(tp_px - entry_px, entry_px * 0.004), max(entry_px - sl_px, entry_px * 0.004))

                        span_bars = entry_day_bars
                        n_bo, n_bh, n_bl, n_bc, n_bv = [span_bars[col].values.astype(float) for col in ["Open", "High", "Low", "Close", "Volume"]]
                        n_hms = span_bars["_bar_hm"].values.tolist() if "_bar_hm" in span_bars.columns else ["-"] * len(n_bo)
                        total_span_bars = len(n_bo)
                        or15_bars = min(3, total_span_bars)
                        or15_high = round_to_tse_tick(float(np.max(n_bh[:or15_bars])) if or15_bars > 0 else p_close, full_code, "ceil")
                        or15_low = round_to_tse_tick(float(np.min(n_bl[:or15_bars])) if or15_bars > 0 else p_close, full_code, "floor")
                        open_gap_pct = ((float(n_bo[0]) - p_close) / max(p_close, 1e-4)) * 100.0 if total_span_bars > 0 else 0.0

                        entered, avg_entry_px, first_entry_bar, entry_hm_act = False, 0.0, -1, "-"
                        pending_entry_side, pending_entry_lows, pending_entry_highs, pending_exit_reason = "", np.array([]), np.array([]), ""
                        half_tp_done, half_tp_px, half_tp_bar_idx, pending_be_sl = False, 0.0, -1, None
                        eff_tp, eff_sl, tp_delta, sl_delta, pullback_touched = 0.0, 0.0, 0.0, 0.0, False
                        outcome, exit_px, result_category, realized_ret_rate, r_multiple_final = "", 0.0, "NOTRADE", 0.0, 0.0
                        cum_pv, cum_pv2, cum_v, ema5, alpha_ema5 = 0.0, 0.0, 0.0, (float(n_bc[0]) if total_span_bars > 0 else p_close), 2.0 / 6.0

                        for b_i in range(total_span_bars):
                            bo, bh, bl, bc, bv = float(n_bo[b_i]), float(n_bh[b_i]), float(n_bl[b_i]), float(n_bc[b_i]), float(n_bv[b_i])
                            prev_vwap_for_entry = (cum_pv / cum_v) if cum_v > 0 else p_vwap
                            typ_b = (bh + bl + bc) / 3.0
                            vol_b = max(bv, 1.0)
                            cum_pv += typ_b * vol_b; cum_pv2 += (typ_b ** 2) * vol_b; cum_v += vol_b
                            curr_vwap = cum_pv / cum_v
                            curr_vwap_std = math.sqrt(max((cum_pv2 / cum_v) - (curr_vwap ** 2), 0.0))
                            curr_vwap_p2 = curr_vwap + 2.0 * curr_vwap_std
                            ema5 = bc if b_i == 0 else (bc * alpha_ema5 + ema5 * (1.0 - alpha_ema5))
                            is_afternoon_protect = (b_i >= int(total_span_bars * 0.65)); is_late_session = (b_i >= int(total_span_bars * 0.80))

                            def _finalize_split_exit(rem_exit_px: float) -> tuple:
                                rem_clean = round_to_tse_tick(rem_exit_px, full_code, "nearest")
                                trip_cost = BASE_COST_RATE + (((0.0006 if is_tier3_small else 0.0) + 0.0002) if is_short_sig else 0.0)
                                if is_short_sig:
                                    return ((PARTIAL_RATIO * (((avg_entry_px - half_tp_px) / max(avg_entry_px, 1e-4)) - trip_cost) + REMAINING_RATIO * (((avg_entry_px - rem_clean) / max(avg_entry_px, 1e-4)) - trip_cost)), (PARTIAL_RATIO * half_tp_px + REMAINING_RATIO * rem_clean)) if half_tp_done else ((((avg_entry_px - rem_clean) / max(avg_entry_px, 1e-4)) - trip_cost), rem_clean)
                                return ((PARTIAL_RATIO * (((half_tp_px - avg_entry_px) / max(avg_entry_px, 1e-4)) - trip_cost) + REMAINING_RATIO * (((rem_clean - avg_entry_px) / max(avg_entry_px, 1e-4)) - trip_cost)), (PARTIAL_RATIO * half_tp_px + REMAINING_RATIO * rem_clean)) if half_tp_done else ((((rem_clean - avg_entry_px) / max(avg_entry_px, 1e-4)) - trip_cost), rem_clean)

                            def _classify_r_outcome(net_ret_rate: float, entry_p: float, risk_d: float, side_lbl: str, win_desc: str, lose_desc: str) -> tuple:
                                r_mult_val = net_ret_rate / max(risk_d / max(entry_p, 1e-4), 0.003)
                                return (f"⭕ {side_lbl}{win_desc} (+{r_mult_val:.2f}R) (WIN)", "WIN", r_mult_val) if r_mult_val >= 0.15 else ((f"🛡️ {side_lbl}{lose_desc} ({r_mult_val:.2f}R) (LOSE)", "LOSE", r_mult_val) if r_mult_val <= -0.15 else (f"⚖️ {side_lbl}建値撤退 ({r_mult_val:+.2f}R) (SCRATCH)", "SCRATCH", r_mult_val))

                            if (not entered) and pending_entry_side:
                                is_long_dir = (pending_entry_side == "LONG")
                                avg_entry_px = apply_unfavorable_tick_slip(bo, full_code, is_long_entry_or_short_exit=is_long_dir)
                                entered, first_entry_bar, entry_hm_act = True, b_i, str(n_hms[b_i])
                                eff_tp, eff_sl, tp_delta, sl_delta = _calc_structural_tp_sl(avg_entry_px, not is_long_dir, pending_entry_lows, pending_entry_highs)
                                pending_entry_side = ""

                            if entered and (pending_be_sl is not None) and (b_i > half_tp_bar_idx):
                                eff_sl = min(eff_sl, pending_be_sl) if is_short_sig else max(eff_sl, pending_be_sl); pending_be_sl = None

                            if entered:
                                side_tag = "[空売り]" if is_short_sig else "[買い]"
                                trip_cost_cur = BASE_COST_RATE + (((0.0006 if is_tier3_small else 0.0) + 0.0002) if is_short_sig else 0.0)
                                if pending_exit_reason and b_i > first_entry_bar:
                                    exec_out_px = apply_unfavorable_tick_slip(bo, full_code, is_long_entry_or_short_exit=is_short_sig)
                                    realized_ret_rate, exit_px = _finalize_split_exit(exec_out_px)
                                    outcome, result_category, r_multiple_final = _classify_r_outcome(realized_ret_rate, avg_entry_px, sl_delta, side_tag, "失速早期利確撤退" if pending_exit_reason == "STALL" else "時間軸プラス手仕舞い", "モメンタム失速早期撤退" if pending_exit_reason == "STALL" else "時間軸手仕舞い")
                                    break
                                bars_held = b_i - first_entry_bar
                                if is_short_sig:
                                    half_trigger_px = round_to_tse_tick(avg_entry_px - sl_delta, full_code, "floor")
                                    if (b_i > first_entry_bar and bo >= eff_sl) or bh >= eff_sl:
                                        sl_fill = apply_unfavorable_tick_slip(max(bo, eff_sl) if (b_i > first_entry_bar and bo >= eff_sl) else eff_sl, full_code, True)
                                        realized_ret_rate, exit_px = _finalize_split_exit(sl_fill)
                                        outcome, result_category, r_multiple_final = _classify_r_outcome(realized_ret_rate, avg_entry_px, sl_delta, side_tag, "50%利確後建値ロック完遂", "構造的逆指値損切"); break
                                    elif bl <= eff_tp:
                                        tp_fill = min(bo, eff_tp) if (b_i > first_entry_bar and bo <= eff_tp) else eff_tp
                                        if not half_tp_done:
                                            half_tp_done = True
                                            half_tp_px = min(bo, half_trigger_px) if (b_i > first_entry_bar and bo <= half_trigger_px) else half_trigger_px
                                        realized_ret_rate, exit_px = _finalize_split_exit(tp_fill)
                                        outcome, result_category, r_multiple_final = _classify_r_outcome(realized_ret_rate, avg_entry_px, sl_delta, side_tag, "50%分割＋下落目標到達", "目標決済"); break
                                    if (not half_tp_done) and (bl <= half_trigger_px):
                                        half_tp_done, half_tp_bar_idx = True, b_i
                                        half_tp_px = min(bo, half_trigger_px) if (b_i > first_entry_bar and bo <= half_trigger_px) else half_trigger_px
                                        pending_be_sl = round_to_tse_tick(avg_entry_px * (1.0 - trip_cost_cur - 0.0005), full_code, "floor")
                                    if (not half_tp_done) and (bars_held >= 6) and (bc > avg_entry_px * 0.9985) and (bc > curr_vwap) and (bc > ema5): pending_exit_reason = "STALL"
                                    elif is_late_session and bc <= avg_entry_px * (1.0 - trip_cost_cur - 0.0020): pending_exit_reason = "TIME"
                                    elif is_afternoon_protect and bc <= avg_entry_px * (1.0 - trip_cost_cur - 0.0015): pending_be_sl = min(pending_be_sl if pending_be_sl is not None else eff_sl, round_to_tse_tick(avg_entry_px * (1.0 - trip_cost_cur - 0.0005), full_code, "floor"))
                                else:
                                    half_trigger_px = round_to_tse_tick(avg_entry_px + sl_delta, full_code, "ceil")
                                    if (b_i > first_entry_bar and bo <= eff_sl) or bl <= eff_sl:
                                        sl_fill = apply_unfavorable_tick_slip(min(bo, eff_sl) if (b_i > first_entry_bar and bo <= eff_sl) else eff_sl, full_code, False)
                                        realized_ret_rate, exit_px = _finalize_split_exit(sl_fill)
                                        outcome, result_category, r_multiple_final = _classify_r_outcome(realized_ret_rate, avg_entry_px, sl_delta, side_tag, "50%利確後建値ロック完遂", "構造的逆指値損切"); break
                                    elif bh >= eff_tp:
                                        tp_fill = max(bo, eff_tp) if (b_i > first_entry_bar and bo >= eff_tp) else eff_tp
                                        if not half_tp_done:
                                            half_tp_done = True
                                            half_tp_px = max(bo, half_trigger_px) if (b_i > first_entry_bar and bo >= half_trigger_px) else half_trigger_px
                                        realized_ret_rate, exit_px = _finalize_split_exit(tp_fill)
                                        outcome, result_category, r_multiple_final = _classify_r_outcome(realized_ret_rate, avg_entry_px, sl_delta, side_tag, "50%分割＋最終目標到達", "目標決済"); break
                                    if (not half_tp_done) and (bh >= half_trigger_px):
                                        half_tp_done, half_tp_bar_idx = True, b_i
                                        half_tp_px = max(bo, half_trigger_px) if (b_i > first_entry_bar and bo >= half_trigger_px) else half_trigger_px
                                        pending_be_sl = round_to_tse_tick(avg_entry_px * (1.0 + trip_cost_cur + 0.0005), full_code, "ceil")
                                    if (not half_tp_done) and (bars_held >= 6) and (bc < avg_entry_px * 1.0015) and (bc < curr_vwap) and (bc < ema5): pending_exit_reason = "STALL"
                                    elif is_late_session and bc >= avg_entry_px * (1.0 + trip_cost_cur + 0.0020): pending_exit_reason = "TIME"
                                    elif is_afternoon_protect and bc >= avg_entry_px * (1.0 + trip_cost_cur + 0.0015): pending_be_sl = max(pending_be_sl if pending_be_sl is not None else eff_sl, round_to_tse_tick(avg_entry_px * (1.0 + trip_cost_cur + 0.0005), full_code, "ceil"))

                            max_entry_bar = max(7, int(total_span_bars * (0.45 if st_p == "スキャルピング" else 0.72)))
                            if (not entered) and (not pending_entry_side) and (exec_score_p >= 4) and (1 <= b_i <= max_entry_bar) and (b_i + 1 < total_span_bars):
                                prev_close_bar, prev_high_bar = float(n_bc[b_i - 1]), float(n_bh[b_i - 1])
                                rec_lows, rec_highs = n_bl[max(0, b_i - 4):b_i + 1], n_bh[max(0, b_i - 4):b_i + 1]
                                if is_short_sig:
                                    if ((bc <= curr_vwap * 1.001 or bc <= ema5) and bc <= bo) or (b_i >= 2 and bl <= or15_low and bc < prev_close_bar):
                                        pending_entry_side, pending_entry_lows, pending_entry_highs = "SHORT", rec_lows, rec_highs
                                elif b_i >= 2:
                                    or15_low_held = bool(bc >= or15_low)
                                    vwap_held = bool(bc >= curr_vwap * 0.998)
                                    bull_break_prev_high = bool((bc > bo) and (bc > prev_high_bar))
                                    not_overheated_vwap = bool(((bc - curr_vwap) / max(curr_vwap, 1e-4) <= 0.015) and ((bc - curr_vwap) <= 0.45 * p_atr) and (curr_vwap_std <= 0 or bc <= curr_vwap_p2))
                                    high_gap_ok = True if open_gap_pct <= 1.8 else bool((bl >= float(n_bl[b_i - 1]) * 0.999) and ((bh - bc) <= (bc - bo) * 0.6))
                                    if or15_low_held and vwap_held and bull_break_prev_high and not_overheated_vwap and high_gap_ok:
                                        near_vwap_or_ema = bool((bl <= curr_vwap * 1.006) or (bl <= ema5 * 1.006) or (bc <= curr_vwap * 1.006) or (bc <= ema5 * 1.006))
                                        higher_lows_3 = bool(n_bl[b_i] >= n_bl[b_i - 1] >= n_bl[b_i - 2])
                                        if near_vwap_or_ema or higher_lows_3: pullback_touched = True
                                        if sig_tactic == "Type-D":
                                            if ((prev_close_bar >= prev_vwap_for_entry * 0.997) and (bc >= or15_high) and open_gap_pct <= max_gu_limit) or pullback_touched:
                                                pending_entry_side, pending_entry_lows, pending_entry_highs = "LONG", rec_lows, rec_highs
                                        elif sig_tactic == "Type-E":
                                            if higher_lows_3 or pullback_touched:
                                                pending_entry_side, pending_entry_lows, pending_entry_highs = "LONG", rec_lows, rec_highs
                                        else:
                                            if pullback_touched or (bc >= or15_high):
                                                pending_entry_side, pending_entry_lows, pending_entry_highs = "LONG", rec_lows, rec_highs

                        if not entered:
                            no_trade_reason = "⚪ 執行ゲートGrade-C・見送り (NO TRADE)" if exec_score_p < 4 else "⚪ OR15/押し目ブレイク条件未到達・見送り (NO TRADE)"
                            outcome, avg_entry_px, exit_px, result_category, ret_pct, r_multiple_final, base_100_profit, entry_hm_act = no_trade_reason, sig_plan_px, sig_plan_px, "NOTRADE", 0.0, 0.0, 0.0, "-"
                        else:
                            if outcome == "":
                                if entry_d in unconf_dates: continue
                                side_tag = "[空売り]" if is_short_sig else "[買い]"
                                close_fill = apply_unfavorable_tick_slip(float(n_bc[-1]), full_code, is_long_entry_or_short_exit=is_short_sig)
                                realized_ret_rate, exit_px = _finalize_split_exit(close_fill)
                                outcome, result_category, r_multiple_final = _classify_r_outcome(realized_ret_rate, avg_entry_px, sl_delta, side_tag, "最終大引け利確決済", "最終大引け損切決済")
                            ret_pct, base_100_profit = realized_ret_rate * 100.0, (avg_entry_px * BASE_LOT) * realized_ret_rate

                        is_win_bool = True if result_category == "WIN" else (False if result_category == "LOSE" else None)
                        stock_ledger["verified"][entry_d] = {"date": entry_d, "entry_date": entry_d, "entry_hm": entry_hm_act, "exit_date": entry_d, "hold_days": 1, "signal_date": prev_d, "plan_short": f"{sig_tactic}({sig_mode[:10]})", "entry_price": round(avg_entry_px, 4), "exit_price": round(exit_px, 4), "entry_str": fmt_px(avg_entry_px, is_jp, full_code) if result_category != "NOTRADE" else f"待機 {fmt_px(sig_plan_px, is_jp, full_code)}", "exit_str": fmt_px(exit_px, is_jp, full_code) if result_category != "NOTRADE" else "未約定", "outcome": outcome, "result_category": result_category, "is_win": is_win_bool, "return_pct": round(ret_pct, 2), "r_mult": round(float(r_multiple_final), 2), "base_100_profit": round(base_100_profit, 2)}
                    except Exception as e_day: record_system_error("forward_test_day_loop", e_day, f"Code: {full_code}, Date: {prev_d}"); continue
        except Exception as e: record_system_error("record_and_verify_daily_Forward_test", e, f"Code: {full_code}")

    confirmed_items = [v for k, v in stock_ledger["verified"].items() if k not in unconf_dates and v.get("exit_date", k) not in unconf_dates]
    raw_verified_22 = sorted(confirmed_items, key=lambda x: x.get("entry_date", x.get("date", "")), reverse=True)[:22]
    for k_name in ("verified", "signals"):
        if len(stock_ledger[k_name]) > 80:
            keep = sorted(stock_ledger[k_name].keys(), reverse=True)[:80]; stock_ledger[k_name] = {k: stock_ledger[k_name][k] for k in keep}
    with _DB_LOCK:
        ledger[ledger_key] = stock_ledger
        if save_db: db_set("daily_forward_ledger", ledger)

    user_shares, all_verified = max(1, int(shares)), []
    for item in raw_verified_22:
        row_copy = dict(item)
        rcat = row_copy.get("result_category") or ("WIN" if row_copy.get("is_win") is True else ("LOSE" if row_copy.get("is_win") is False else "NOTRADE"))
        row_copy["result_category"] = rcat
        row_copy["profit_val"] = 0.0 if rcat == "NOTRADE" else round(float(row_copy["entry_price"]) * user_shares * (float(row_copy["return_pct"]) / 100.0), 2)
        all_verified.append(row_copy)

    traded_rows = [x for x in all_verified if x.get("result_category") != "NOTRADE"]
    total_days, notrade_count = len(traded_rows), len(all_verified) - len(traded_rows)
    win_count = sum(1 for x in traded_rows if x.get("result_category") == "WIN")
    lose_count = sum(1 for x in traded_rows if x.get("result_category") == "LOSE")
    scratch_count = sum(1 for x in traded_rows if x.get("result_category") == "SCRATCH")
    decisive_trades = win_count + lose_count
    actual_win_rate = round((win_count / decisive_trades) * 100.0, 1) if decisive_trades > 0 else 0.0
    gross_profit = sum(float(x.get("profit_val", 0.0)) for x in traded_rows if float(x.get("profit_val", 0.0)) > 0.0)
    gross_loss = abs(sum(float(x.get("profit_val", 0.0)) for x in traded_rows if float(x.get("profit_val", 0.0)) < 0.0))
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0.0 else (99.9 if gross_profit > 0.0 else 0.0)
    total_profit_yen = round(sum(float(x.get("profit_val", 0.0)) for x in traded_rows), 2)

    if traded_rows:
        r_list = [float(x.get("r_mult", float(x.get("return_pct", 0.0)) / 1.0)) for x in traded_rows]
        avg_r = round(float(np.mean(r_list)), 2)
        sqn = round(float(np.sqrt(len(r_list)) * (np.mean(r_list) / max(np.std(r_list), 1e-4))), 2) if len(r_list) >= 3 else 0.0
        chrono_trades = sorted(traded_rows, key=lambda x: x.get("entry_date", x.get("date", "")))
        cum_ret, peak_ret, max_dd = 0.0, 0.0, 0.0
        for tr_it in chrono_trades:
            cum_ret += float(tr_it.get("return_pct", 0.0))
            if cum_ret > peak_ret: peak_ret = cum_ret
            dd = peak_ret - cum_ret
            if dd > max_dd: max_dd = dd
        max_dd_pct = round(float(max_dd), 2)
    else:
        avg_r, sqn, max_dd_pct = 0.0, 0.0, 0.0

    latest_result = traded_rows[0] if traded_rows else (all_verified[0] if all_verified else {"date": today_str, "entry_hm": "-", "plan_short": f"{tactic_type}({entry_mode[:10]})", "entry_str": fmt_px(plan_entry_price, is_jp, full_code), "exit_str": "-", "outcome": "⏳ 保有中・確定決済待機", "result_category": "NOTRADE", "is_win": None, "return_pct": 0.0, "r_mult": 0.0, "profit_val": 0.0, "hold_days": 1})
    return {"win_count": win_count, "lose_count": lose_count, "scratch_count": scratch_count, "total_days": total_days, "notrade_count": notrade_count, "verified_span_days": len(all_verified), "actual_win_rate": actual_win_rate, "profit_factor": profit_factor, "sqn": sqn, "avg_r": avg_r, "max_dd_pct": max_dd_pct, "total_profit_yen": total_profit_yen, "latest_result": latest_result, "history_rows": all_verified}

def analyze_df(df_raw, code, name, theme, genre, macro, buzz_map, style, core_vol=True, core_inst=True, core_mom=True, total_capital=1000000, risk_tolerance_pct=2.0, shared_ledger=None, save_db=True, macro_10y_map=None, daily_2y_map=None, bench_30m_ret=None, earnings_days_left=None):
    try:
        df = normalize_ohlcv_df(df_raw, min_rows=25)
        if df is None: return None
        spec = get_style_spec(style); st_p = spec["pfx"]
        daily_df_5m = df.groupby("_trade_date").agg(Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"), Close=("Close", "last"), Volume=("Volume", "sum")).sort_index()
        c, o, h, l, v = [np.asarray(df[col].values, dtype=float).reshape(-1) for col in ["Close", "Open", "High", "Low", "Volume"]]
        cv = float(c[-1]); prev_day_close = float(daily_df_5m["Close"].iloc[-2]) if len(daily_df_5m) >= 2 else float(o[0])
        day_ret = float((cv - prev_day_close) / max(prev_day_close, 1e-4) * 100.0)

        stock_30m_ret = float(((c[-1] - c[-7]) / max(c[-7], 1e-4)) * 100.0) if len(c) >= 7 else 0.0
        if bench_30m_ret is not None:
            ref_30m = float(bench_30m_ret)
        else:
            m_key = "nk_fut" if ".T" in str(code) else "sp500"
            ref_30m = float(macro.get(m_key, {}).get("diff", 0.0)) * 0.3
        intraday_rs_30m = round(stock_30m_ret - ref_30m, 2)

        macro_10y = (macro_10y_map or {}).get(code) or _compute_single_10y_metrics(None, code)
        daily_2y = (daily_2y_map or {}).get(code) or _compute_single_daily_metrics(None, pd.Series(dtype=float), code)

        pdh_val = float(daily_2y.get("pdh", 0.0)) if daily_2y.get("has_data") and float(daily_2y.get("pdh", 0.0)) > 0 else (float(daily_df_5m["High"].iloc[-2]) if len(daily_df_5m) >= 2 else float(np.max(h)))
        pdl_val = float(daily_2y.get("pdl", 0.0)) if daily_2y.get("has_data") and float(daily_2y.get("pdl", 0.0)) > 0 else (float(daily_df_5m["Low"].iloc[-2]) if len(daily_df_5m) >= 2 else float(np.min(l)))
        ref_prev_close_lim = float(daily_2y.get("prev_close_1d", 0.0)) if (daily_2y.get("has_data") and float(daily_2y.get("prev_close_1d", 0.0)) > 0) else prev_day_close

        if daily_2y.get("has_data") and float(daily_2y.get("daily_atr14", 0.0)) > 0: atrv = max(float(daily_2y["daily_atr14"]), cv * 0.0115)
        elif len(daily_df_5m) >= 3:
            dh, dl, dc = [daily_df_5m[col].values.astype(float) for col in ["High", "Low", "Close"]]
            d_prev_c = np.roll(dc, 1); d_prev_c[0] = dc[0]
            atrv = max(float(np.mean(np.maximum(dh - dl, np.maximum(np.abs(dh - d_prev_c), np.abs(dl - d_prev_c)))[-14:])), cv * 0.0115)
        else:
            prev_c = np.roll(c, 1); prev_c[0] = c[0]
            atrv = max(float(np.mean(np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))[-14:])) * 1.8, cv * 0.0115)

        today_bars = df[df["_trade_date"] == df["_trade_date"].iloc[-1]]
        to, th, tl, tc, tv = [today_bars[col].values.astype(float) for col in ["Open", "High", "Low", "Close", "Volume"]]
        tot_tv = float(np.sum(tv))
        if tot_tv > 0:
            typ_t = (th + tl + tc) / 3.0
            vwap_today = float(np.sum(typ_t * tv) / tot_tv)
            vwap_var = max(float(np.sum(((typ_t - vwap_today) ** 2) * tv) / tot_tv), 0.0)
            vwap_std = math.sqrt(vwap_var)
        else:
            vwap_today, vwap_std = cv, 0.0
        vwap_p1 = round_to_tse_tick(vwap_today + vwap_std, code, "nearest")
        vwap_p2 = round_to_tse_tick(vwap_today + 2.0 * vwap_std, code, "nearest")
        vwap_m1 = round_to_tse_tick(max(vwap_today - vwap_std, cv * 0.5), code, "nearest")
        vwap_m2 = round_to_tse_tick(max(vwap_today - 2.0 * vwap_std, cv * 0.5), code, "nearest")
        vwap_over_2sigma = bool(vwap_std > 0 and cv > (vwap_today + 2.0 * vwap_std))
        vwap_pullback_zone = bool(vwap_std > 0 and (vwap_today <= cv <= (vwap_today + vwap_std)))

        ob_support_px, ob_high_px = 0.0, 0.0
        if len(today_bars) >= 3:
            mean_tv = max(float(np.mean(tv)), 1.0)
            for bi_ob in range(len(today_bars) - 1, -1, -1):
                rng_b = max(float(th[bi_ob] - tl[bi_ob]), 1e-4)
                body_b = float(tc[bi_ob] - to[bi_ob])
                if float(tv[bi_ob]) >= mean_tv * 2.2 and (body_b / rng_b) >= 0.60:
                    ob_support_px = round_to_tse_tick(float(tl[bi_ob]), code, "floor")
                    ob_high_px = round_to_tse_tick(float(th[bi_ob]), code, "ceil")
                    break

        or15_n = min(3, len(today_bars))
        or15_low_today = float(np.min(tl[:or15_n])) if or15_n > 0 else cv
        or15_high_today = float(np.max(th[:or15_n])) if or15_n > 0 else cv

        is_jp = ".T" in code
        limit_up_px, limit_down_px, limit_up_tight = 0.0, 0.0, False
        if is_jp and ref_prev_close_lim > 0:
            lim_w = get_tse_price_limit(ref_prev_close_lim)
            limit_up_px = round_to_tse_tick(ref_prev_close_lim + lim_w, code, "floor")
            limit_down_px = round_to_tse_tick(max(ref_prev_close_lim - lim_w, 1.0), code, "ceil")
            rem_up_pct = ((limit_up_px - cv) / max(cv, 1e-4)) * 100.0
            limit_up_tight = bool(rem_up_pct < 1.5)

        news_hits = int((buzz_map or {}).get(code, {}).get("news_hits", 0))
        q_adv = compute_advanced_quant_indicators(c, o, h, l, v, daily_df=daily_df_5m, news_hits=news_hits, df=df, real_daily_yz_vol=(float(daily_2y["daily_yz_vol"]) if daily_2y.get("has_data") else None))
        qm = compute_quantum_wave_metrics(c, h, l, v, o=o, rsi_val=q_adv["rsi"], upper_wick_val=q_adv["upper_wick_pressure"])
        ms = compute_inst_microstructure(c, h, l, v)

        long_10y_score, cagr_10y, pos_10y_pct, poc_10y_price, ma200w_dev_pct = float(macro_10y.get("long_10y_score", 50)), float(macro_10y.get("cagr_10y", 0.0)), float(macro_10y.get("pos_10y_pct", 50.0)), float(macro_10y.get("poc_10y_price", 0.0)), float(macro_10y.get("ma200w_dev_pct", 0.0))
        daily_trend_score = float(daily_2y.get("daily_trend_score", 50))
        combat_prof = get_ticker_combat_profile(code, genre, rvol=q_adv["rvol"], yz_vol=q_adv["yz_vol"])
        tier_str = str(combat_prof.get("tier_class", ""))
        ofi_z = compute_smoothed_clv_z(c, h, l, v, day_bars_count=len(today_bars))

        r20 = int(np.sum(np.diff(c[-21:]) > 0)) if len(c) >= 21 else 10
        base_tech_score = float(np.clip((r20 / 20.0) * 100.0 * 0.65 + (q_adv["eff_pct"] * 0.35), 10.0, 95.0))
        inst_flow_score = float(np.clip(50.0 + ofi_z * 14.0 + (0.5 - q_adv["vpin"]) * 35.0, 10.0, 98.0))
        bb_exp_score = float(np.clip(35.0 + (q_adv["bb_exp_ratio"] - 0.8) * 32.0, 10.0, 98.0))
        vol_spike_score = float(np.clip(30.0 + q_adv["vol_spike_bull_pct"] * 2.5, 10.0, 98.0))

        is_30m_rs_leader = bool(intraday_rs_30m >= 0.8 and cv >= vwap_today)
        core_vol_score = float(qm["q_score"]) * 0.60 + bb_exp_score * 0.40
        core_inst_score = float(np.clip(float(ms["ms_score"]) * 0.52 + inst_flow_score * 0.48 + (6.0 if is_30m_rs_leader else 0.0) + (3.5 if ob_support_px > 0 else 0.0), 10.0, 99.0))
        core_mom_score = float(q_adv["surge_attention_score"]) * 0.55 + vol_spike_score * 0.45

        m_bias = compute_ticker_macro_bias(code, genre, macro)
        rs_alpha = round(float(daily_2y["latest_rs_alpha"]), 2) if daily_2y.get("has_data") else round(day_ret - m_bias, 2)
        w_vol, w_inst, w_mom, w_1d, w_10y = spec["w"]

        if st_p == "スキャルピング":
            fit_bonus = (4.5 if q_adv["yz_vol"] >= 0.35 else 0.0) + (4.0 if q_adv["rvol"] >= 1.2 else 0.0) + (3.5 if abs(ofi_z) >= 0.6 else 0.0) + (2.0 if ("Tier2" in tier_str or "Tier3" in tier_str) else (-8.0 if "Tier4" in tier_str else 0.0))
            style_fit_bonus = float(np.clip(fit_bonus, -10.0, 12.0))
        elif st_p == "スイングトレード":
            fit_bonus = (4.5 if ms["hurst"] >= 0.55 else 0.0) + (4.0 if ms["kyle_stealth"] >= 62.0 else 0.0) + (4.0 if (daily_2y.get("bull_po") or daily_2y.get("bear_po")) else 0.0) + (3.5 if abs(rs_alpha) >= 1.0 else 0.0) + (-7.0 if ("Tier3" in tier_str and q_adv["eff_pct"] < 35) else 0.0)
            style_fit_bonus = float(np.clip(fit_bonus, -10.0, 14.0))
        elif st_p == "バイ＆ホールド":
            fit_bonus = (min((cagr_10y - 10.0) * 0.35 + 4.0, 8.0) if cagr_10y >= 12.0 else 0.0) + (4.0 if (ma200w_dev_pct >= 0.0 and macro_10y.get("ma200w_slope_up", True)) else 0.0) + (3.0 if daily_2y.get("ma200_dev_pct", 0.0) >= 0.0 else 0.0) + (4.5 if ("Tier1" in tier_str or "Tier4" in tier_str) else 0.0) + (-10.0 if (("Tier3" in tier_str and cagr_10y < 5.0) or ma200w_dev_pct < -10.0) else 0.0)
            style_fit_bonus = float(np.clip(fit_bonus, -12.0, 16.0))
        else:
            fit_bonus = (4.5 if q_adv["eff_pct"] >= 45 else 0.0) + (3.5 if abs(cv - vwap_today) / max(vwap_today, 1e-4) <= 0.015 else 0.0) + (2.5 if daily_2y.get("bull_po") else 0.0)
            style_fit_bonus = float(np.clip(fit_bonus, -6.0, 10.0))

        vwap_band_adj = 2.5 if vwap_pullback_zone else (-4.5 if vwap_over_2sigma else 0.0)

        weighted_sum = base_tech_score * 1.0 + daily_trend_score * w_1d + long_10y_score * w_10y
        total_weight = 1.0 + w_1d + w_10y
        if core_vol: weighted_sum += core_vol_score * w_vol; total_weight += w_vol
        if core_inst: weighted_sum += core_inst_score * w_inst; total_weight += w_inst
        if core_mom: weighted_sum += core_mom_score * w_mom; total_weight += w_mom

        tot_win = float(np.clip((weighted_sum / total_weight) + style_fit_bonus * 0.65, 5.0, 97.8))
        kelly_pct = round(float(np.clip(max(0.0, (tot_win / 100.0) - ((1.0 - (tot_win / 100.0)) / max(q_adv["payoff"], 0.1))) * 100.0, 0.0, 35.0)), 1)
        rvol_penalty = -4.5 if q_adv["rvol"] < combat_prof["min_rvol_req"] else 0.0
        raw_expect_pct = float(np.clip(tot_win * 0.85 + ofi_z * 3.8 + m_bias * 1.8 + style_fit_bonus * 0.45 + vwap_band_adj + rvol_penalty + 6.0, 5.0, 99.5))

        if core_vol and q_adv["bb_exp_ratio"] >= 1.35 and not (q_adv["rsi"] > 75.0 and q_adv["upper_wick_pressure"] > 45.0): qm["q_state"] = f"🧠 BBスクイーズ拡大初動 ({q_adv['bb_exp_ratio']}x)"
        if is_30m_rs_leader: ms["ms_regime"] = f"🏛️ 機関資金・30分RS逆行高リーダー ({intraday_rs_30m:+.2f}%)"
        elif core_mom and q_adv["vol_spike_bull_pct"] >= 10.0: ms["ms_regime"] = f"⚠️ 出来高スパイク実体陽線頻度 {q_adv['vol_spike_bull_pct']}%"

        is_mkt_open = _is_market_open_now(is_jp)
        if is_mkt_open and len(today_bars) > 0:
            today_open_px = float(today_bars["Open"].iloc[0])
            pgap = round(float(((today_open_px - prev_day_close) / max(prev_day_close, 1e-4)) * 100.0), 2)
            pest = round_to_tse_tick(today_open_px, code, "nearest")
            pts_label_title = "📊 当日確定始値(Open) ＆ 実測寄付きギャップ率（※場中実測値）"
        else:
            pgap = round(float(np.clip(m_bias * 0.75 + ofi_z * 0.25, -3.5, 4.5)), 2)
            pest = round_to_tse_tick(prev_day_close * (1.0 + pgap / 100.0), code, "nearest")
            pts_label_title = "📊 理論寄付き試算値（前日終値×マクロ・資金フロー推計）"
        vwap_rounded = round_to_tse_tick(vwap_today, code, "nearest")

        hist_gu_rate = float(np.mean(daily_df_5m["Open"].values[1:].astype(float) > daily_df_5m["Close"].values[:-1].astype(float))) * 100.0 if len(daily_df_5m) >= 3 else 50.0
        gu_prob_pct = round(float(np.clip(hist_gu_rate * 0.65 + (50.0 + pgap * 10.0) * 0.35, 5.0, 95.0)), 1)
        n_bar_chk = min(20, len(c)); c_sub20, o_sub20, h_sub20, l_sub20 = c[-n_bar_chk:], o[-n_bar_chk:], h[-n_bar_chk:], l[-n_bar_chk:]
        intraday_bull_pct = round(float(np.clip((float(np.mean(c_sub20 > o_sub20)) * 100.0) * 0.65 + (float(np.mean(np.clip((c_sub20 - o_sub20) / np.maximum(h_sub20 - l_sub20, 1e-4), -1.0, 1.0))) * 50.0 + 50.0) * 0.35, 5.0, 95.0)), 1)

        ma25_now, ma75_now = float(daily_2y.get("ma25", 0.0)), float(daily_2y.get("ma75", 0.0))
        prev_trend_weak = (cv < ma25_now * 0.992) if ma25_now > 0 else ((cv < float(np.mean(daily_df_5m["Close"].values[-5:].astype(float))) * 0.992) if len(daily_df_5m) >= 5 else False)
        rel_news_obj = next((n for n in all_impact_news if code in n.get("detail", {}).get("related_codes", [])), None)
        rel_news_title = rel_news_obj["title"] if rel_news_obj else ""

        u_wick_now, l_wick_now = float(q_adv.get("upper_wick_pressure", 0.0)), float(q_adv.get("lower_wick_support", 0.0))
        bull_edge, bear_edge = compute_directional_edges(ofi_z, q_adv["rsi"], prev_trend_weak, float(ms.get("hurst", 0.50)), u_wick_now, l_wick_now, rel_news_title=rel_news_title, rs_alpha=rs_alpha, below_vwap=(cv < vwap_today), daily_ctx=daily_2y, macro_10y=macro_10y, cv=cv)
        if is_30m_rs_leader:
            bull_edge = round(bull_edge + 5.0, 2)
        if vwap_pullback_zone:
            bull_edge = round(bull_edge + 3.0, 2)
        tactic_now = determine_tactic_classification(code, genre, ofi_z, q_adv["vpin"], q_adv["rsi"], pgap, round(raw_expect_pct, 1), prev_trend_weak, qm, ms, rel_news_title=rel_news_title, style=style, upper_wick_pressure=u_wick_now, lower_wick_support=l_wick_now, cv=cv, vwap_today=vwap_today, rs_alpha=rs_alpha, daily_ctx=daily_2y, macro_10y=macro_10y)
        is_short_now = (tactic_now in ("Type-S1", "Type-S2")) and spec["allow_short"]

        df_d_clean = daily_2y.get("df_daily_clean")
        if spec["tf"] == "1d" and df_d_clean is not None and len(df_d_clean) >= 5:
            lb_n = 5 if st_p == "スイングトレード" else 20
            rec_lows = df_d_clean["Low"].values[-lb_n:].astype(float)
            rec_highs = df_d_clean["High"].values[-lb_n:].astype(float)
        else:
            rec_lows, rec_highs = l[-5:], h[-5:]

        sl_delta_cur, tp_delta_cur = compute_style_tp_sl_deltas(cv, atrv, is_short_now, style, combat_prof, code, recent_lows=rec_lows, recent_highs=rec_highs)
        if spec["tf"] == "5m":
            if not is_short_now:
                if pos_10y_pct >= 90.0 and (poc_10y_price <= 0 or cv >= poc_10y_price): tp_delta_cur *= 1.10
                elif poc_10y_price > cv and (poc_10y_price - cv) < tp_delta_cur: tp_delta_cur = max((poc_10y_price - cv) * 0.94, sl_delta_cur * 1.35)
                for res_ma in (ma25_now, ma75_now):
                    if res_ma > cv and (res_ma - cv) < tp_delta_cur * 0.85: tp_delta_cur = max((res_ma - cv) * 0.95, sl_delta_cur * 1.35)
            else:
                for sup_lv in (ma25_now, ma75_now, poc_10y_price):
                    if 0 < sup_lv < cv and (cv - sup_lv) < tp_delta_cur * 0.85: tp_delta_cur = max((cv - sup_lv) * 0.95, sl_delta_cur * 1.35)

        exec_score, exec_grade, exec_detail = evaluate_execution_quality_gate(is_short_now, prev_trend_weak, cv, vwap_today, int(q_adv["eff_pct"]), bull_edge, bear_edge, float(q_adv["rvol"]), float(combat_prof["min_rvol_req"]), u_wick_now, l_wick_now, daily_ctx=daily_2y, macro_10y=macro_10y, macro=macro, rs_alpha=rs_alpha, earnings_days_left=earnings_days_left, vwap_over_2sigma=vwap_over_2sigma, limit_up_tight=limit_up_tight)
        if is_short_now:
            tpv, slv = round_to_tse_tick(max(cv - tp_delta_cur, cv * 0.5), code, "floor"), round_to_tse_tick(cv + sl_delta_cur, code, "ceil")
            if is_jp and limit_down_px > 0 and tpv <= limit_down_px:
                tk_d = get_tse_tick_step(limit_down_px, code)
                tpv = round_to_tse_tick(min(limit_down_px + tk_d, cv - sl_delta_cur * 1.1), code, "ceil")
        else:
            tpv, slv = round_to_tse_tick(cv + tp_delta_cur, code, "ceil"), round_to_tse_tick(max(cv - sl_delta_cur, cv * 0.5), code, "floor")
            hvn_wall_px = float(daily_2y.get("hvn_wall_price", 0.0))
            if hvn_wall_px > cv and tpv > hvn_wall_px:
                tpv = round_to_tse_tick(max(hvn_wall_px * 0.995, cv + sl_delta_cur * 1.35), code, "floor")
            if is_jp and limit_up_px > 0 and tpv >= limit_up_px:
                tk_u = get_tse_tick_step(limit_up_px, code)
                tpv = round_to_tse_tick(max(limit_up_px - tk_u, cv + sl_delta_cur * 1.1), code, "floor")

        lot_info = compute_japanese_lot_sizing(cv, slv, total_capital, risk_tolerance_pct, is_jp, spec["lot_mul"], lot_cap_mult=combat_prof["lot_cap_mult"], earnings_days_left=earnings_days_left)
        tp_pct_disp, sl_pct_disp = round((tpv - cv) / max(cv, 1e-4) * 100, 1), round((slv - cv) / max(cv, 1e-4) * 100, 1)
        tp_sign, sl_sign = ("+" if tp_pct_disp > 0 else ""), ("+" if sl_pct_disp > 0 else "")

        active_boosts_tuple = tuple(sorted([k for k, f in [("core_vol", core_vol), ("core_inst", core_inst), ("core_mom", core_mom)] if f]))
        strat = select_dynamic_strategy(code.replace(".T", ""), style, ofi_z, q_adv["vpin"], q_adv["cvar95"], q_adv["rsi"], lot_info, fmt_px(pest, is_jp, code), fmt_px(vwap_rounded, is_jp, code), f"{fmt_px(tpv, is_jp, code)}({tp_sign}{tp_pct_disp}%)", f"{fmt_px(slv, is_jp, code)}({sl_sign}{sl_pct_disp}%)", qm, ms, name=name, theme=theme, rel_news_title=rel_news_title, pgap=pgap, expect_pct=round(raw_expect_pct, 1), prev_trend_weak=prev_trend_weak, full_code=code, genre=genre, upper_wick_pressure=u_wick_now, lower_wick_support=l_wick_now, cv=cv, vwap_today=vwap_today, rs_alpha=rs_alpha, macro_10y=macro_10y, daily_2y=daily_2y)
        forward_test = record_and_verify_daily_Forward_test(df, code, strat, pest, vwap_rounded, tpv, slv, lot_info["shares"], style, total_capital=total_capital, risk_tolerance_pct=risk_tolerance_pct, shared_ledger=shared_ledger, save_db=save_db, genre=genre, daily_2y=daily_2y, macro_10y=macro_10y, active_boosts=active_boosts_tuple)

        ft_days = int(forward_test.get("total_days", 0))
        ft_wr = float(forward_test.get("actual_win_rate", 50.0))
        ft_pf = float(forward_test.get("profit_factor", 0.0))
        ft_sqn = float(forward_test.get("sqn", 0.0))
        ft_prof = float(forward_test.get("total_profit_yen", 0.0))

        ft_bonus = float(np.clip((ft_wr - 52.0) * 0.14 + (1.8 if ft_prof > 0 else -1.5), -5.0, 6.0)) if ft_days >= 3 else 0.0
        if ft_days >= 4:
            if ft_wr < 45.0 or ft_pf < 0.95 or ft_prof < 0:
                ft_bonus = -12.0
                exec_score = min(exec_score, 3)
                exec_grade = "🟡 Grade-C: アルゴ相性注意・見送り推奨（過去検証PF/勝率未達）"
                exec_detail += f" / ⚠️過去検証未達(勝率{ft_wr:.1f}%/PF={ft_pf:.2f})"
            elif ft_wr >= 60.0 and ft_pf >= 1.5 and ft_sqn >= 1.2:
                ft_bonus += 5.5
                exec_detail += f" / 🏆実証ボーナス(勝率{ft_wr:.1f}%/PF={ft_pf:.2f}/SQN={ft_sqn:.2f})"

        if is_short_now:
            short_base_tech = float(np.clip(((20 - r20) / 20.0) * 100.0 * 0.65 + (q_adv["eff_pct"] * 0.35), 10.0, 95.0))
            short_inst_flow = float(np.clip(50.0 + (-ofi_z) * 14.0 + (q_adv["vpin"] - 0.5) * 35.0, 10.0, 98.0))
            short_tot_win = float(np.clip((short_base_tech + qm["q_score"] * 0.80 + ms["ms_score"] * 0.80 + short_inst_flow * 0.80 + q_adv["surge_attention_score"] * 0.65) / 4.05, 10.0, 97.8))
            expect_pct = float(np.clip(short_tot_win * 0.82 + bear_edge * 0.42 + u_wick_now * 0.12 + (-m_bias) * 1.8 + style_fit_bonus * 0.40 + rvol_penalty + 4.0 + ft_bonus, 5.0, 98.5))
        else:
            expect_pct = float(np.clip(raw_expect_pct + ft_bonus, 5.0, 98.5))

        edge = round((expect_pct - 50.0) / 10.0 + abs(ofi_z) * 0.5, 2)
        if strat.get("side") == "SHORT":
            t_num, t_lbl, t_col, t_bg = (10, "【📉S級空売り：過熱天井・下落急襲モード】", "#fff", "linear-gradient(90deg,#9f1239,#be123c)") if expect_pct >= 88.0 else ((9, "【📉A級空売り：VWAP割れ順張りショート】", "#fff", "linear-gradient(90deg,#be123c,#6d28d9)") if expect_pct >= 78.0 else (8, "【📉空売り優位：反落収益化モード】", "#fff", "linear-gradient(90deg,#881337,#4c1d95)"))
        else:
            t_num, t_lbl, t_col, t_bg = (10, "【Lv.10：🔥S級・全力買い突破】", "#fff", "linear-gradient(90deg,#7e22ce,#dc2626)") if expect_pct >= 90.0 else ((9, "【Lv.9：⚡超強気順張り買い】", "#fff", "linear-gradient(90deg,#0369a1,#1d4ed8)") if expect_pct >= 80.0 else ((7, "【Lv.7：⭕押し目買い優位】", "#e2e8f0", "linear-gradient(90deg,#065f46,#0f766e)") if expect_pct >= 65.0 else (5, "【Lv.5：⚖️中立・押し目待機】", "#e2e8f0", "linear-gradient(90deg,#334155,#1e293b)")))

        macro_10y_serializable = {k: v for k, v in macro_10y.items() if k != "df_weekly_clean"}
        daily_2y_serializable = {k: v for k, v in daily_2y.items() if k not in ("df_daily_clean", "daily_rs_alpha_map")}
        return {"full_code": code, "code": code.replace(".T", ""), "name": name, "genre": genre, "theme": theme, "combat_tier": combat_prof["tier_class"], "combat_cost_pct": round(combat_prof["cost_rate"] * 100, 2), "exec_grade": exec_grade, "exec_score": exec_score, "exec_detail": exec_detail, "earnings_days_left": earnings_days_left, "rs_alpha": rs_alpha, "intraday_rs_30m": intraday_rs_30m, "or15_low": or15_low_today, "or15_high": or15_high_today, "pdh": pdh_val, "pdl": pdl_val, "ob_support_px": ob_support_px, "ob_high_px": ob_high_px, "limit_up_px": limit_up_px, "limit_down_px": limit_down_px, "limit_up_tight": limit_up_tight, "vwap_p1": vwap_p1, "vwap_p2": vwap_p2, "vwap_m1": vwap_m1, "vwap_m2": vwap_m2, "vwap_over_2sigma": vwap_over_2sigma, "style_fit_bonus": round(style_fit_bonus, 1), "macro_10y": macro_10y_serializable, "daily_2y": daily_2y_serializable, "price": fmt_px(cv, is_jp, code), "raw_close": cv, "raw_tp": tpv, "raw_sl": slv, "raw_vwap": vwap_rounded, "tp_price": fmt_px(tpv, is_jp, code), "tp_pct": tp_pct_disp, "sl_price": fmt_px(slv, is_jp, code), "sl_pct": sl_pct_disp, "vwap_price": fmt_px(vwap_rounded, is_jp, code), "inst_score": int(np.clip(round((ms["ms_score"] + inst_flow_score) * 0.5), 10, 99)), "vpin": q_adv["vpin"], "ofi_z": round(ofi_z, 2), "yz_vol": q_adv["yz_vol"], "cvar95": q_adv["cvar95"], "eff_pct": q_adv["eff_pct"], "kelly_pct": kelly_pct, "bb_exp_ratio": q_adv["bb_exp_ratio"], "vol_spike_bull_pct": q_adv["vol_spike_bull_pct"], "upper_wick_pressure": u_wick_now, "lower_wick_support": l_wick_now, "bull_edge": bull_edge, "bear_edge": bear_edge, "q_score": qm["q_score"], "q_tunnel": qm["q_tunnel"], "q_coherence": qm["q_coherence"], "q_entropy": qm["q_entropy"], "q_state": qm["q_state"], "ms_score": ms["ms_score"], "hurst": ms["hurst"], "kyle_lambda": ms["kyle_lambda"], "kyle_stealth": ms["kyle_stealth"], "ms_regime": ms["ms_regime"], "expect_pct": round(expect_pct, 1), "surge_attention_score": q_adv["surge_attention_score"], "rvol": q_adv["rvol"], "news_hits": news_hits, "pts_est_price": fmt_px(pest, is_jp, code), "pts_gap_pct": pgap, "pts_label_title": pts_label_title, "diff": round(day_ret, 2), "prob": gu_prob_pct, "intraday_win_rate": intraday_bull_pct, "total_win_rate": round(tot_win, 1), "rsi": q_adv["rsi"], "payoff": q_adv["payoff"], "edge": edge, "ai_score": int(np.clip(round(expect_pct * 0.92 + 4), 10, 99)), "tier_num": t_num, "tier_label": t_lbl, "tier_color": t_col, "tier_bg": t_bg, "lot_info": lot_info, "strat": strat, "forward_test": forward_test}
    except Exception as e: record_system_error("analyze_df", e, f"Code: {code}"); return None
def _download_5m_pool(codes: list):
    for p_str in ("60d", "1mo", "15d"):
        try:
            raw = yf.download(codes, period=p_str, interval="5m", group_by="ticker", threads=True, progress=False, timeout=10.0)
            if raw is not None and not raw.empty:
                return raw
        except Exception as e:
            record_system_error(f"_download_5m_pool:{p_str}", e)
    return {}

def _fetch_all_earnings_parallel(codes: list) -> dict:
    earnings_map = {}
    with ThreadPoolExecutor(max_workers=8) as ex_e:
        fut_e = {ex_e.submit(fetch_earnings_days_left, c): c for c in codes}
        for f_e in as_completed(fut_e):
            c_e = fut_e[f_e]
            try: earnings_map[c_e] = f_e.result()
            except Exception: earnings_map[c_e] = None
    return earnings_map

def _collect_raw_market_snapshot(universe_tuple: tuple) -> dict:
    codes_tuple = tuple(c for c, _, _, _ in universe_tuple)
    codes = list(codes_tuple)
    buzz_map, macro_10y_map, daily_2y_map, earnings_map, raw = {}, {}, {}, {}, {}
    with ThreadPoolExecutor(max_workers=5) as ex_io:
        f_buzz = ex_io.submit(fetch_real_market_buzz, universe_tuple)
        f_10y = ex_io.submit(fetch_10y_macro_metrics, codes_tuple)
        f_2y = ex_io.submit(fetch_2y_daily_metrics, codes_tuple)
        f_earn = ex_io.submit(_fetch_all_earnings_parallel, codes)
        f_5m = ex_io.submit(_download_5m_pool, codes)
        try: buzz_map = f_buzz.result()
        except Exception as e: record_system_error("_collect_raw_market_snapshot:buzz", e)
        try: macro_10y_map = f_10y.result()
        except Exception as e: record_system_error("_collect_raw_market_snapshot:10y", e)
        try: daily_2y_map = f_2y.result()
        except Exception as e: record_system_error("_collect_raw_market_snapshot:2y", e)
        try: earnings_map = f_earn.result()
        except Exception as e: record_system_error("_collect_raw_market_snapshot:earn", e)
        try: raw = f_5m.result()
        except Exception as e: record_system_error("_collect_raw_market_snapshot:5m", e)
    return {
        "buzz_map": buzz_map,
        "macro_10y_map": macro_10y_map,
        "daily_2y_map": daily_2y_map,
        "earnings_map": earnings_map,
        "raw_5m": raw,
        "total_codes": len(codes),
        "fetched_ts": time.time(),
    }

@st.cache_data(ttl=90)
def _fetch_raw_market_bundle(universe_tuple: tuple) -> dict:
    return _collect_raw_market_snapshot(universe_tuple)

@st.cache_resource
def _get_bg_market_refresher():
    state = {"lock": threading.RLock(), "snapshot": None, "universe": None, "started": False}
    def _daemon_loop():
        while True:
            time.sleep(100.0)
            with state["lock"]:
                u_tup = state.get("universe")
            if not u_tup:
                continue
            try:
                snap = _collect_raw_market_snapshot(u_tup)
                with state["lock"]:
                    state["snapshot"] = snap
            except Exception as e:
                record_system_error("_bg_market_refresher:loop", e)
    with state["lock"]:
        if not state["started"]:
            t = threading.Thread(target=_daemon_loop, name="YamashishiBgRefresher", daemon=True)
            t.start()
            state["started"] = True
    return state

@st.cache_data(ttl=90)
def _fetch_pool_batch_core(macro_sig: tuple, style: str, core_vol: bool, core_inst: bool, core_mom: bool):
    macro = {k: {"price": p, "diff": d, "label": l} for k, p, d, l in macro_sig}
    base_roster = load_active_market_roster(); existing_codes = tuple(sorted([it[0] for it in base_roster]))
    challengers = discover_challenger_tickers(existing_codes); challenger_codes_set = {it[0] for it in challengers}
    combined_universe, seen_c = [], set()
    for it in base_roster + challengers:
        if it[0] not in seen_c and it[0] not in DELISTED_OR_INVALID_CODES:
            seen_c.add(it[0]); meta = resolve_ticker_metadata(it[0])
            combined_universe.append((it[0], meta["name"] if it[1].startswith("東証") else it[1], it[2], it[3]))
    combined_universe = combined_universe[:45]
    universe_tuple = tuple(combined_universe)
    codes_tuple = tuple(c for c, _, _, _ in combined_universe)
    codes = list(codes_tuple)

    bg_state = _get_bg_market_refresher()
    bundle = None
    with bg_state["lock"]:
        bg_state["universe"] = universe_tuple
        snap = bg_state.get("snapshot")
        if isinstance(snap, dict) and (time.time() - float(snap.get("fetched_ts", 0.0))) <= 150.0:
            bundle = snap
    if bundle is None:
        bundle = _fetch_raw_market_bundle(universe_tuple)
        with bg_state["lock"]:
            bg_state["snapshot"] = bundle

    buzz_map = bundle.get("buzz_map", {})
    macro_10y_map = bundle.get("macro_10y_map", {})
    daily_2y_map = bundle.get("daily_2y_map", {})
    earnings_map = bundle.get("earnings_map", {})
    raw = bundle.get("raw_5m", {})

    ret_30m_list = []
    for c in codes:
        df_tmp = _extract_ticker_df(raw, c, len(codes))
        if df_tmp is not None and not df_tmp.empty:
            c_arr = df_tmp["Close"].dropna().values.astype(float)
            if len(c_arr) >= 7 and c_arr[-7] > 0:
                ret_30m_list.append(float(((c_arr[-1] - c_arr[-7]) / c_arr[-7]) * 100.0))
    market_median_30m_ret = round(float(np.median(ret_30m_list)), 3) if ret_30m_list else 0.0

    shared_ledger = db_get("daily_forward_ledger", {})
    if not isinstance(shared_ledger, dict): shared_ledger = {}
    evaluated_all = []
    def _w(c, n, g, t):
        df = _extract_ticker_df(raw, c, len(codes))
        r = analyze_df(df, c, n, t, g, macro, buzz_map, style, core_vol=core_vol, core_inst=core_inst, core_mom=core_mom, total_capital=1000000, risk_tolerance_pct=2.0, shared_ledger=shared_ledger, save_db=False, macro_10y_map=macro_10y_map, daily_2y_map=daily_2y_map, bench_30m_ret=market_median_30m_ret, earnings_days_left=earnings_map.get(c))
        if r: r["is_new_challenger"] = (c in challenger_codes_set)
        return r

    with ThreadPoolExecutor(max_workers=min(len(combined_universe), 8)) as ex:
        for f in as_completed([ex.submit(_w, c, n, g, t) for c, n, g, t in combined_universe]):
            try:
                r = f.result()
                if r: evaluated_all.append(r)
            except Exception as e: record_system_error("_fetch_pool_batch_core:future", e)
    db_set("daily_forward_ledger", shared_ledger)

    for ev_r in evaluated_all:
        rel_n_ev = [n for n in all_impact_news if ev_r.get("full_code") in n.get("detail", {}).get("related_codes", [])]
        sync_lab_intel_to_shared(ev_r, rel_news_list=rel_n_ev, persist=False)
    db_set("shared_ticker_intel", load_shared_ticker_intel())

    def _is_combat_eligible(item: dict) -> int:
        ft_d = item.get("forward_test", {})
        t_days = int(ft_d.get("total_days", 0))
        pf_v = float(ft_d.get("profit_factor", 0.0))
        return 1 if (int(item.get("exec_score", 0)) >= 4 and (t_days < 3 or pf_v >= 1.0)) else 0

    st_p = get_style_spec(style)["pfx"]
    if st_p == "スキャルピング":
        evaluated_all.sort(key=lambda x: (_is_combat_eligible(x), x["expect_pct"] * 0.72 + x["surge_attention_score"] * 0.28), reverse=True)
    elif st_p == "スイングトレード":
        evaluated_all.sort(key=lambda x: (_is_combat_eligible(x), x["expect_pct"] * 0.68 + x.get("daily_2y", {}).get("daily_trend_score", 50) * 0.20 + x.get("macro_10y", {}).get("long_10y_score", 50) * 0.12), reverse=True)
    elif st_p == "バイ＆ホールド":
        evaluated_all.sort(key=lambda x: (_is_combat_eligible(x), x["expect_pct"] * 0.55 + x.get("daily_2y", {}).get("daily_trend_score", 50) * 0.15 + x.get("macro_10y", {}).get("long_10y_score", 50) * 0.30), reverse=True)
    else:
        evaluated_all.sort(key=lambda x: (_is_combat_eligible(x), x["expect_pct"] * 0.74 + x["surge_attention_score"] * 0.18 + x.get("daily_2y", {}).get("daily_trend_score", 50) * 0.08), reverse=True)

    survivors, survivor_codes = [], set()
    for g in DYNAMIC_GENRES:
        for item in [x for x in evaluated_all if x["genre"] == g and float(x.get("expect_pct", 0.0)) >= 60.0][:2]:
            if item["full_code"] not in survivor_codes: survivors.append(item); survivor_codes.add(item["full_code"])
    for item in evaluated_all:
        if len(survivors) >= 32: break
        if item["full_code"] not in survivor_codes: survivors.append(item); survivor_codes.add(item["full_code"])

    if len(survivors) >= 15:
        prev_codes_set = {it[0] for it in base_roster}
        promoted, purged = [x for x in survivors if x["full_code"] not in prev_codes_set], [it for it in base_roster if it[0] not in survivor_codes]
        db_set("active_market_roster", [[x["full_code"], x["name"], x["genre"], x["theme"]] for x in survivors])
        if promoted or purged:
            now_s = datetime.now().strftime("%Y-%m-%d %H:%M"); s_logs = db_get("market_survival_logs", [])
            if not isinstance(s_logs, list): s_logs = []
            for p_it in promoted[:5]:
                msg_p = f"🟢 [新規昇格] {p_it['name']}({p_it['code']}) が期待度 {p_it['expect_pct']}% / RVOL {p_it['rvol']}倍 でロスター奪取！"
                if not s_logs or s_logs[0].get("msg") != msg_p: s_logs.insert(0, {"time": now_s, "msg": msg_p})
            for d_it in purged[:5]:
                msg_d = f"💀 [圏外追放] {d_it[1]}({d_it[0].replace('.T','')}) が期待度低下によりサバイバル脱落。"
                if not s_logs or s_logs[0].get("msg") != msg_d: s_logs.insert(0, {"time": now_s, "msg": msg_d})
            db_set("market_survival_logs", s_logs[:100])

    gmap = {g: [] for g in DYNAMIC_GENRES}
    for r in survivors: gmap.setdefault(r["genre"], []).append(r)
    for g in gmap: gmap[g] = sorted(gmap[g], key=lambda x: (_is_combat_eligible(x), x["expect_pct"]), reverse=True)
    return gmap, sorted(survivors, key=lambda x: (_is_combat_eligible(x), x["expect_pct"]), reverse=True)

def _scale_stock_item_for_user(item: dict, style: str, total_cap: float, risk_pct: float) -> dict:
    r = dict(item)
    code = str(r.get("full_code", ""))
    is_jp = ".T" in code
    cv = float(r.get("raw_close", 0.0))
    slv = float(r.get("raw_sl", cv * 0.99))
    spec = get_style_spec(style)
    combat_prof = get_ticker_combat_profile(code, r.get("genre", ""), rvol=float(r.get("rvol", 1.0)), yz_vol=float(r.get("yz_vol", 0.3)))
    new_lot = compute_japanese_lot_sizing(cv, slv, total_cap, risk_pct, is_jp, spec["lot_mul"], lot_cap_mult=combat_prof["lot_cap_mult"], earnings_days_left=r.get("earnings_days_left"))
    r["lot_info"] = new_lot

    old_strat = r.get("strat")
    if isinstance(old_strat, dict):
        old_sh = int(old_strat.get("adj_shares", 100))
        new_sh = int(new_lot.get("shares", 100))
        if old_sh != new_sh or float(total_cap) != 1000000.0 or float(risk_pct) != 2.0:
            tp_sign = "+" if float(r.get("tp_pct", 0.0)) > 0 else ""
            sl_sign = "+" if float(r.get("sl_pct", 0.0)) > 0 else ""
            r["strat"] = select_dynamic_strategy(
                r.get("code", code.replace(".T", "")), style, float(r.get("ofi_z", 0.0)), float(r.get("vpin", 0.5)),
                float(r.get("cvar95", 2.5)), float(r.get("rsi", 50.0)), new_lot,
                str(r.get("pts_est_price", "-")), str(r.get("vwap_price", "-")),
                f"{r.get('tp_price', '-')}({tp_sign}{r.get('tp_pct', 0.0)}%)",
                f"{r.get('sl_price', '-')}({sl_sign}{r.get('sl_pct', 0.0)}%)",
                {"q_score": r.get("q_score", 50), "q_tunnel": r.get("q_tunnel", 50.0)},
                {"ms_score": r.get("ms_score", 50), "hurst": r.get("hurst", 0.5), "kyle_stealth": r.get("kyle_stealth", 50.0)},
                name=r.get("name", ""), theme=r.get("theme", ""), pgap=float(r.get("pts_gap_pct", 0.0)),
                expect_pct=float(r.get("expect_pct", 50.0)), full_code=code, genre=r.get("genre", ""),
                upper_wick_pressure=float(r.get("upper_wick_pressure", 0.0)), lower_wick_support=float(r.get("lower_wick_support", 0.0)),
                cv=cv, vwap_today=float(r.get("raw_vwap", cv)), rs_alpha=float(r.get("rs_alpha", 0.0)),
                macro_10y=r.get("macro_10y", {}), daily_2y=r.get("daily_2y", {})
            )
        else:
            r["strat"] = dict(old_strat)

    ft = r.get("forward_test")
    if isinstance(ft, dict):
        ft_copy = dict(ft)
        user_shares = max(1, int(new_lot.get("shares", 100)))
        new_rows = []
        for hr in ft.get("history_rows", []):
            h_copy = dict(hr)
            rcat = h_copy.get("result_category", "NOTRADE")
            h_copy["profit_val"] = 0.0 if rcat == "NOTRADE" else round(float(h_copy.get("entry_price", 0.0)) * user_shares * (float(h_copy.get("return_pct", 0.0)) / 100.0), 2)
            new_rows.append(h_copy)
        ft_copy["history_rows"] = new_rows
        traded_rows = [x for x in new_rows if x.get("result_category") != "NOTRADE"]
        ft_copy["total_profit_yen"] = round(sum(float(x.get("profit_val", 0.0)) for x in traded_rows), 2)
        if isinstance(ft.get("latest_result"), dict):
            lat_copy = dict(ft["latest_result"])
            l_cat = lat_copy.get("result_category", "NOTRADE")
            lat_copy["profit_val"] = 0.0 if l_cat == "NOTRADE" else round(float(lat_copy.get("entry_price", 0.0)) * user_shares * (float(lat_copy.get("return_pct", 0.0)) / 100.0), 2)
            ft_copy["latest_result"] = lat_copy
        r["forward_test"] = ft_copy
    return r

def fetch_pool_batch(macro, style, core_vol=True, core_inst=True, core_mom=True, total_cap=1000000, risk_pct=2.0):
    macro_sig = tuple(sorted((k, round(float(v.get("price", 0.0)), 4), round(float(v.get("diff", 0.0)), 2), str(v.get("label", ""))) for k, v in (macro or {}).items()))
    core_gmap, core_all = _fetch_pool_batch_core(macro_sig, style, bool(core_vol), bool(core_inst), bool(core_mom))
    scaled_map = {}
    scaled_all = []
    for item in core_all:
        sc_item = _merge_dd_intel_into_lab_item(_scale_stock_item_for_user(item, style, float(total_cap), float(risk_pct)))
        scaled_map[sc_item["full_code"]] = sc_item
        scaled_all.append(sc_item)
    scaled_gmap = {g: [scaled_map[x["full_code"]] for x in items if x["full_code"] in scaled_map] for g, items in core_gmap.items()}
    return scaled_gmap, scaled_all

@st.cache_data(ttl=120)
def fetch_one_with_df(code, macro, style, core_vol=True, core_inst=True, core_mom=True, total_cap=1000000, risk_pct=2.0):
    try:
        code = code.strip().upper()
        if re.match(r"^[0-9]{3}[0-9A-Z]$", code): code = f"{code}.T"
        if code in DELISTED_OR_INVALID_CODES: return None, None
        inf = resolve_ticker_metadata(code)
        local_buzz = {code: {"news_hits": len(search_single_query(f"{inf['name']} 株", 5, trusted_only=False))}}
        macro_10y_map, daily_2y_map = fetch_10y_macro_metrics((code,)), fetch_2y_daily_metrics((code,))
        e_days = fetch_earnings_days_left(code)
        tkr = yf.Ticker(code); hist_df = None
        for p_str in ("60d", "1mo", "15d"):
            hist_df = tkr.history(period=p_str, interval="5m")
            if hist_df is not None and not hist_df.empty: break
        norm_df = normalize_ohlcv_df(hist_df, min_rows=25)
        res = analyze_df(hist_df, code, inf["name"], inf["theme"], inf["genre"], macro, local_buzz, style, core_vol=core_vol, core_inst=core_inst, core_mom=core_mom, total_capital=total_cap, risk_tolerance_pct=risk_pct, macro_10y_map=macro_10y_map, daily_2y_map=daily_2y_map, bench_30m_ret=None, earnings_days_left=e_days)
        if res:
            res = _merge_dd_intel_into_lab_item(res)
        return res, norm_df
    except Exception as e:
        record_system_error("fetch_one_with_df", e, f"Code: {code}")
        return None, None

def fetch_one(code, macro, style, core_vol=True, core_inst=True, core_mom=True, total_cap=1000000, risk_pct=2.0):
    res, _ = fetch_one_with_df(code, macro, style, core_vol=core_vol, core_inst=core_inst, core_mom=core_mom, total_cap=total_cap, risk_pct=risk_pct)
    return res

def compute_sector_rotation_stats(all_stocks: list) -> list:
    out = []
    for g in DYNAMIC_GENRES:
        items = [x for x in all_stocks if x.get("genre") == g]
        if not items:
            out.append({"genre": g, "count": 0, "avg_rs30": 0.0, "avg_rvol": 1.0, "avg_ofi": 0.0, "flow_score": 0.0})
            continue
        avg_rs30 = round(float(np.mean([float(x.get("intraday_rs_30m", 0.0)) for x in items])), 2)
        avg_rvol = round(float(np.mean([float(x.get("rvol", 1.0)) for x in items])), 2)
        avg_ofi = round(float(np.mean([float(x.get("ofi_z", 0.0)) for x in items])), 2)
        flow_score = round(avg_rs30 * 12.0 + avg_ofi * 15.0 + (avg_rvol - 1.0) * 10.0, 1)
        out.append({"genre": g, "count": len(items), "avg_rs30": avg_rs30, "avg_rvol": avg_rvol, "avg_ofi": avg_ofi, "flow_score": flow_score})
    out.sort(key=lambda x: x["flow_score"], reverse=True)
    return out

def analyze_watchlist_portfolio_risk(wl_dict: dict) -> dict:
    items = list(wl_dict.values())
    n = len(items)
    if n < 2: return {"has_alert": False}
    genre_counts = {}
    for it in items:
        g = str(it.get("genre", "その他"))
        genre_counts[g] = genre_counts.get(g, 0) + 1
    top_genre, top_cnt = max(genre_counts.items(), key=lambda x: x[1])
    max_sector_pct = round((top_cnt / n) * 100.0, 1)

    ret_series_list = []
    for it in items:
        closes = it.get("daily_2y", {}).get("recent_close_60") or []
        if len(closes) >= 15:
            arr = np.asarray(closes, dtype=float)
            rets = np.diff(arr) / np.maximum(arr[:-1], 1e-4)
            ret_series_list.append(rets)
    avg_corr = 0.0
    if len(ret_series_list) >= 2:
        min_len = min(len(r) for r in ret_series_list)
        if min_len >= 10:
            mat = np.vstack([r[-min_len:] for r in ret_series_list])
            corr_m = np.corrcoef(mat)
            upper_vals = [float(corr_m[i, j]) for i in range(len(ret_series_list)) for j in range(i + 1, len(ret_series_list)) if not np.isnan(corr_m[i, j])]
            if upper_vals: avg_corr = round(float(np.mean(upper_vals)), 2)

    is_high_risk = (avg_corr >= 0.70) or (max_sector_pct >= 60.0)
    return {"has_alert": True, "count": n, "avg_corr": avg_corr, "top_genre": top_genre, "max_sector_pct": max_sector_pct, "is_high_risk": is_high_risk}

def evaluate_journal_trade_audit(entry: dict, all_stocks: list) -> str:
    code = entry.get("code", "")
    name = entry.get("name", "")
    side = entry.get("side", "LONG")
    ep = float(entry.get("entry_price", 0.0))
    xp = float(entry.get("exit_price") or ep)
    tp = float(entry.get("tp_price", ep))
    sl = float(entry.get("sl_price", ep))
    pnl_pct = float(entry.get("pnl_pct", 0.0))
    pnl_yen = float(entry.get("pnl_yen", 0.0))
    exec_g = str(entry.get("exec_grade", ""))

    if load_gemini_cfg().get("api_key"):
        sys_p = "あなたはプロクオンツ監査委員会のリスク管理官AEGISとリスク監査官SENTINELです。ユーザーのトレード記録を採点（100点満点）し、エントリー根拠・損切り規律・利確執行の良かった点と改善点を300〜450文字で具体的に講評してください。"
        u_p = f"銘柄: {name}({code}) / 方向: {side} / 執行グレード: {exec_g} / 約定値: {ep} / 決済値: {xp} / 計画TP: {tp} / 計画SL: {sl} / 損益: {pnl_pct:+.2f}% ({pnl_yen:+,.0f}円)"
        res, _ = call_real_llm_api(sys_p, u_p, expect_json=False)
        if res and len(res.strip()) > 25:
            return re.sub(r'```[a-zA-Z]*|```', '', res).strip()

    sl_breached = (xp < sl * 0.995) if side == "LONG" else (xp > sl * 1.005)
    score = 75
    if pnl_pct > 0: score += 15
    if sl_breached: score -= 28
    if "Grade-C" in exec_g: score -= 12
    score = int(np.clip(score, 20, 98))
    sl_comment = "⚠️ 計画逆指値（SL）を超えて損失が拡大しています。次回はエントリーと同時に自動逆指値注文を必ず設定してください。" if sl_breached else "✅ 計画逆指値（SL）の規律範囲内でリスクコントロールが機能しています。"
    tp_comment = "🎯 計画通りの利確執行で期待値通りのトレードです。+1.0Rでの半分利確習慣を継続しましょう。" if pnl_pct >= 1.0 else ("⚖️ 微損・微益での撤退です。方向感が崩れた際の早期撤退は資金防衛として有効です。" if pnl_pct > -1.0 else "🛡️ 損切り後のドテンやリベンジ売買を控え、次のGrade-A銘柄を待ちましょう。")
    return f"【AEGIS＆SENTINEL 規律監査スコア: {score}点】\n・損益結果: {pnl_pct:+.2f}%（{pnl_yen:+,.0f}円）｜執行グレード: {exec_g}\n・リスク監査(SENTINEL): {sl_comment}\n・資金管理講評(AEGIS): {tp_comment}"

# =========================================================================
# メイン画面レイアウト（スリム1行リボン・視認性優先・全機能100%保持）
# =========================================================================
macro_info = fetch_macro()
ribbon_chips = "".join([
    f'<div class="lab-ribbon-chip">'
    f'<span style="color:#94a3b8;">{html.escape(str(m["label"]))}</span>'
    f'<span style="color:{"#10b981" if m["diff"]>=0 else "#ef4444"};font-weight:800;">{m["diff"]:+.2f}%</span>'
    f'</div>'
    for m in macro_info.values()
])
st.markdown(
    f'<div class="glass-header">'
    f'<div style="display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:6px;">'
    f'<div class="brand-luxury">YAMASHISHI LAB v28.0</div>'
    f'<div style="font-size:10px;color:#94a3b8;font-family:\'JetBrains Mono\',monospace;">3-TIER MTF × DEEP DIVE FUSION × 5-AUDITOR COUNCIL</div>'
    f'</div>'
    f'<div class="lab-thin-ribbon" style="margin-top:6px;margin-bottom:0;">{ribbon_chips}</div>'
    f'</div>',
    unsafe_allow_html=True
)

_cache_pool_key = f"pool_v28_full_{investment_style}_{sorted(list(ac_b))}_{total_capital}_{risk_tolerance_pct}"
if _cache_pool_key not in st.session_state:
    with st.spinner(f"⚛️ 【{investment_style.split(' ')[1]}】週足10年×日足2年×5分足60日 3階層MTFスコアリングを実行中..."):
        g_res, all_res = fetch_pool_batch(macro_info, investment_style, core_vol=("core_vol" in ac_b), core_inst=("core_inst" in ac_b), core_mom=("core_mom" in ac_b), total_cap=total_capital, risk_pct=risk_tolerance_pct)
        st.session_state[_cache_pool_key] = (g_res, all_res)
else:
    raw_g_res, raw_all_res = st.session_state[_cache_pool_key]
    all_res = [_merge_dd_intel_into_lab_item(x) for x in raw_all_res]
    g_res = {gk: [_merge_dd_intel_into_lab_item(x) for x in gl] for gk, gl in raw_g_res.items()}

if st.session_state.get("last_synced_style") != investment_style:
    st.session_state["last_synced_style"] = investment_style
    res_by_fc = {it["full_code"]: it for it in all_res}
    foc_cur = st.session_state.get("focused_stock_item")
    if isinstance(foc_cur, dict) and foc_cur.get("full_code"):
        fc_f = foc_cur["full_code"]
        refreshed_f = res_by_fc.get(fc_f) or fetch_one(fc_f, macro_info, investment_style, core_vol=("core_vol" in ac_b), core_inst=("core_inst" in ac_b), core_mom=("core_mom" in ac_b), total_cap=total_capital, risk_pct=risk_tolerance_pct)
        if refreshed_f: st.session_state["focused_stock_item"] = _merge_dd_intel_into_lab_item(refreshed_f)
    wl_cur = st.session_state.get("watchlist", {})
    if isinstance(wl_cur, dict) and wl_cur:
        updated_wl, changed_wl = {}, False
        for w_k, w_v in wl_cur.items():
            fc_w = w_v.get("full_code") or (f"{w_k}.T" if re.match(r"^[0-9]{3}[0-9A-Z]$", str(w_k)) else str(w_k))
            refreshed_w = res_by_fc.get(fc_w) or fetch_one(fc_w, macro_info, investment_style, core_vol=("core_vol" in ac_b), core_inst=("core_inst" in ac_b), core_mom=("core_mom" in ac_b), total_cap=total_capital, risk_pct=risk_tolerance_pct)
            if refreshed_w: updated_wl[w_k] = _merge_dd_intel_into_lab_item(refreshed_w); changed_wl = True
            else: updated_wl[w_k] = _merge_dd_intel_into_lab_item(w_v)
        if changed_wl:
            st.session_state["watchlist"] = updated_wl
            if cu: save_watchlist(cu, updated_wl)

focused_item = st.session_state.get("focused_stock_item")
if focused_item:
    focused_item = _merge_dd_intel_into_lab_item(focused_item)
    st.markdown("### 🔵 銘柄詳細・売買合議フォーカスモード")
    foc_fc = str(focused_item.get("full_code", "")).strip().upper()
    foc_df = None
    bg_state_f = _get_bg_market_refresher()
    with bg_state_f["lock"]:
        snap_f = bg_state_f.get("snapshot")
    if isinstance(snap_f, dict) and isinstance(snap_f.get("raw_5m"), (pd.DataFrame, dict)):
        raw_5m_snap = snap_f["raw_5m"]
        tot_codes_snap = int(snap_f.get("total_codes") or (len(snap_f.get("universe") or ()) or 45))
        df_cand_f = _extract_ticker_df(raw_5m_snap, foc_fc, tot_codes_snap)
        foc_df = normalize_ohlcv_df(df_cand_f, min_rows=25)
    if foc_df is None:
        _, foc_df = fetch_one_with_df(foc_fc, macro_info, investment_style, core_vol=("core_vol" in ac_b), core_inst=("core_inst" in ac_b), core_mom=("core_mom" in ac_b), total_cap=total_capital, risk_pct=risk_tolerance_pct)
    render_card(focused_item, is_custom=False, kp=f"foc_{focused_item['code']}", is_focused=True, intraday_df=foc_df); st.stop()

if st.session_state.get("navigation_page") == "NEWS_DETAIL":
    if not all_impact_news:
        st.info("現在、新規の重大ヘッドラインは検出されていません。")
        if st.button("⬅️ 戻る", use_container_width=True, type="primary"): st.session_state["navigation_page"] = "TOP"; st.session_state["scroll_top_trig"] = int(time.time()*1000); st.rerun()
        st.stop()
    tn = st.session_state.get("selected_news_item") or all_impact_news[0]
    det = tn.get("detail") or analyze_news_impact_and_links(tn.get("title", ""), tn.get("cat", ""), tn.get("summary", ""))
    st_short = investment_style.split(" ")[1] if " " in investment_style else "デイトレード"
    ai_deep_txt = generate_ai_news_deep_report(tn, st_short)
    body_html, mech_html, time_html, risk_html, act_html = [html.escape(det.get(k, "")).replace("\n", "<br>") for k in ("news_body", "mechanism", "timeline", "risk_note", "action_guide")]
    src_link = tn.get("link", "")
    link_btn = f'<div style="margin-top:10px;"><a href="{html.escape(src_link)}" target="_blank" rel="noopener noreferrer" class="ipo-link-btn">📰 報道元オリジナル記事を開く ({html.escape(tn.get("source", "News"))})</a></div>' if src_link else ""
    cross_badge = '<span class="pill-badge" style="background:rgba(16,185,129,0.25);border-color:#10b981;color:#6ee7b7;font-weight:800;">✅ 複数メディア・クロス検証済</span>' if tn.get("cross_verified") else ""
    ai_deep_block = f'<div class="rank-card" style="border-left-color:#10b981;background:linear-gradient(180deg,#06281e 0%,#090d16 100%)!important;"><div style="font-size:14px;font-weight:800;color:#10b981;margin-bottom:6px;">🧠 Gemini AI生成・個別記事深掘り解析</div><div style="font-size:12.5px;line-height:1.75;color:#ecfdf5;">{html.escape(ai_deep_txt).replace(chr(10), "<br>")}</div></div>' if ai_deep_txt else '<div class="rank-card" style="border-left-color:#f59e0b;background:linear-gradient(180deg,#1e180b 0%,#090d16 100%)!important;"><div style="font-size:13px;font-weight:800;color:#fde047;margin-bottom:4px;">⚙️ やさしいセクター＆立ち回り解説モード（Gemini API未接続時）</div><div style="font-size:12px;line-height:1.65;color:#fef3c7;">現在Gemini APIキーが未接続のため、報道要点と初心者にもわかりやすい立ち回りガイドを表示しています。</div></div>'

    st.markdown(f'<div class="glass-header" style="border-left:4px solid #ef4444;"><div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;"><div><span class="pill-badge" style="background:#ef4444;color:#fff;font-weight:800;">🚨 重大ニュース解説レポート ｜ {html.escape(tn.get("cat", "速報"))} (重要度: {tn.get("impact_score", 70)}点)</span>{cross_badge}</div><span style="font-size:11px;color:#94a3b8;">配信元: {html.escape(tn.get("source", "Market Wire"))} ｜ {html.escape(tn.get("pub_date", ""))} (経過: {tn.get("age_hours", 0)}h)</span></div><div style="font-size:17.5px;font-weight:800;color:#f8fafc;margin-top:8px;line-height:1.4;">{html.escape(tn["title"])}</div><div style="font-size:11.5px;color:#fde047;margin-top:6px;font-weight:700;">🎯 直撃テーマ領域: {html.escape(det.get("sector_focus", ""))}</div>{link_btn}</div>{ai_deep_block}<div class="rank-card" style="border-left-color:#38bdf8;"><div style="font-size:14px;font-weight:800;color:#38bdf8;margin-bottom:6px;">📰 1. ニュース要点 ＆ やさしいテーマ背景</div><div style="font-size:12.5px;line-height:1.75;color:#e2e8f0;">{body_html}</div></div><div class="rank-card" style="border-left-color:#a855f7;"><div style="font-size:14px;font-weight:800;color:#e9d5ff;margin-bottom:6px;">🧠 2. 資金が動く仕組み（セクター波及の流れ）</div><div style="font-size:12.5px;line-height:1.75;color:#e2e8f0;">{mech_html}</div><hr style="border-color:rgba(168,85,247,0.25);margin:12px 0;"><div style="font-size:13.5px;font-weight:800;color:#fde047;margin-bottom:6px;">⏱️ 3. 時間帯別の値動きイメージ</div><div style="font-size:12px;line-height:1.75;color:#cbd5e1;">{time_html}</div><hr style="border-color:rgba(239,68,68,0.25);margin:12px 0;"><div style="font-size:13px;font-weight:800;color:#f87171;margin-bottom:4px;">⚠️ 4. 高値掴み・ダマシ警戒リスク ＆ 撤退基準</div><div style="font-size:12px;line-height:1.7;color:#fca5a5;">{risk_html}</div><div class="beginner-action-box" style="margin-top:12px;"><b>⚡ 5. 【{st_short}】初心者向け・失敗しない注文と利確・損切りガイド</b><br>{act_html}</div></div>', unsafe_allow_html=True)

    extracted_codes_list = list(det.get("extracted_codes") or [])
    sector_ref_codes_list = list(det.get("sector_ref_codes") or [c for c in det.get("related_codes", []) if c not in extracted_codes_list])
    extracted_codes_set = set(extracted_codes_list)
    st.markdown("### 🔗 記事内直接言及銘柄 ＆ 同セクター代表・波及監視銘柄")
    st.caption(f"🎯 記事本文・見出しから直接抽出: {len(extracted_codes_list)}銘柄 ／ 📂 抽出銘柄が3件未満のため同セクター代表銘柄で補完表示")

    def _resolve_stock_items(code_list: list, limit: int) -> list:
        out_items, seen_fc = [], set()
        for rc in code_list:
            if len(out_items) >= limit: break
            if rc in seen_fc: continue
            found = next((r_it for r_it in all_res if r_it["full_code"] == rc or r_it["code"] == rc.replace(".T", "")), None) or fetch_one(rc, macro_info, investment_style, core_vol=("core_vol" in ac_b), core_inst=("core_inst" in ac_b), core_mom=("core_mom" in ac_b), total_cap=total_capital, risk_pct=risk_tolerance_pct)
            if found and found["full_code"] not in seen_fc: out_items.append(_merge_dd_intel_into_lab_item(found)); seen_fc.add(found["full_code"])
        return out_items

    extracted_items = sorted(_resolve_stock_items(extracted_codes_list, 3), key=lambda x: x["fusion_expect_pct"], reverse=True)
    needed_ref = max(0, 3 - len(extracted_items))
    ref_items = sorted(_resolve_stock_items([c for c in sector_ref_codes_list if c not in {it["full_code"] for it in extracted_items}], needed_ref), key=lambda x: x["fusion_expect_pct"], reverse=True) if needed_ref > 0 else []
    combined_news_stocks = (extracted_items + ref_items) or sorted(all_res, key=lambda x: x["fusion_expect_pct"], reverse=True)[:3]

    for idx, r_item in enumerate(combined_news_stocks, 1):
        is_direct_mention = (r_item["full_code"] in extracted_codes_set) or (r_item["code"] in {c.replace(".T", "") for c in extracted_codes_set})
        origin_badge = '<span class="pill-badge" style="background:rgba(16,185,129,0.28);border-color:#10b981;color:#6ee7b7;font-weight:900;">🎯 記事内直接言及</span>' if is_direct_mention else '<span class="pill-badge" style="background:rgba(148,163,184,0.22);border-color:#94a3b8;color:#e2e8f0;font-weight:800;">📂 セクター代表</span>'
        render_card(r_item, rank=idx, kp=f"nr_{tn['id']}", extra_origin_badge=origin_badge)

    if st.button("⬅️ 戻る", use_container_width=True, type="primary"): st.session_state["navigation_page"] = "TOP"; st.session_state["scroll_top_trig"] = int(time.time()*1000); st.rerun()
    st.stop()

c1, c2 = st.columns([3.4, 1])
cin = c1.text_input("🔍 銘柄検索", placeholder="コード入力 (例: 6920 / 7203 / AAPL)", label_visibility="collapsed", key="search_code_input")
if c2.button("🔍 診断", use_container_width=True) and cin:
    st.session_state["custom_search_code"] = clean_k(cin); st.session_state["focused_stock_item"] = None; st.session_state["navigation_page"] = "TOP"; st.session_state["scroll_top_trig"] = int(time.time() * 1000); st.rerun()

if st.session_state.get("custom_search_code"):
    st.markdown("### 🎯 個別銘柄・精密3階層MTFクオンツ診断モード")
    with st.spinner("📡 銘柄正式名称・週足10年・日足2年・5分足60日波形を解析中..."):
        cr, cr_df = fetch_one_with_df(st.session_state["custom_search_code"], macro_info, investment_style, core_vol=("core_vol" in ac_b), core_inst=("core_inst" in ac_b), core_mom=("core_mom" in ac_b), total_cap=total_capital, risk_pct=risk_tolerance_pct)
    if cr: render_card(cr, is_custom=True, kp="custom", intraday_df=cr_df)
    else: st.warning("⚠️ 指定された銘柄コードのデータが取得できないか、上場廃止・無効な銘柄です。")
    if st.button("⬅️ トップ画面（ランキング一覧）に戻る", key="btn_back_from_custom_diag", use_container_width=True, type="primary"):
        st.session_state["custom_search_code"] = ""
        if "search_code_input" in st.session_state: st.session_state["search_code_input"] = ""
        st.session_state["scroll_top_trig"] = int(time.time() * 1000); st.rerun()
    st.stop()

# サバイバル戦況バー（1行横スクロール極薄リボン ＋ 詳細折りたたみ）
surv_logs_top = db_get("market_survival_logs", [])
if isinstance(surv_logs_top, list) and surv_logs_top:
    prom_items = [x for x in surv_logs_top if "[新規昇格]" in x.get("msg", "")][:5]
    purg_items = [x for x in surv_logs_top if "[圏外追放]" in x.get("msg", "")][:5]
    bar_pills = "".join([
        f'<span class="lab-ribbon-chip" style="background:{"rgba(16,185,129,0.16)" if "[新規昇格]" in it.get("msg","") else "rgba(239,68,68,0.16)"};border-color:{"rgba(16,185,129,0.42)" if "[新規昇格]" in it.get("msg","") else "rgba(239,68,68,0.42)"};color:{"#6ee7b7" if "[新規昇格]" in it.get("msg","") else "#fca5a5"};">'
        f'{html.escape(it.get("msg","").split(" が")[0])}</span>'
        for it in surv_logs_top[:6]
    ])
    st.markdown(
        f'<div class="lab-thin-ribbon">'
        f'<span class="lab-ribbon-chip" style="border-color:rgba(250,204,21,0.4);color:#fde047;font-weight:800;">⚔️ 入替戦 昇格{len(prom_items)}/追放{len(purg_items)}</span>'
        f'{bar_pills}</div>',
        unsafe_allow_html=True
    )
    with st.expander("⚔️ サバイバル入れ替え戦・詳細ログ", expanded=False):
        for sl in surv_logs_top[:12]:
            st.markdown(f'<div style="font-size:11px;color:#cbd5e1;padding:3px 0;border-bottom:1px solid rgba(148,163,184,0.12);"><span style="color:#94a3b8;font-family:JetBrains Mono,monospace;">{html.escape(sl.get("time",""))}</span> {html.escape(sl.get("msg",""))}</div>', unsafe_allow_html=True)

# 5大セクター資金ローテーションバー（1行横スクロール極薄リボン ＋ 詳細折りたたみ）
sec_rot_stats = compute_sector_rotation_stats(all_res)
if sec_rot_stats:
    sec_ribbon = "".join([
        f'<div class="lab-ribbon-chip" style="background:{"rgba(16,185,129,0.16)" if float(sr["flow_score"])>=0 else "rgba(239,68,68,0.16)"};border-color:{"rgba(16,185,129,0.42)" if float(sr["flow_score"])>=0 else "rgba(239,68,68,0.42)"};">'
        f'<span style="color:#f8fafc;font-weight:800;">{html.escape(sr["genre"].split("・")[0])}</span>'
        f'<span style="color:{"#6ee7b7" if float(sr["flow_score"])>=0 else "#fca5a5"};font-weight:800;">{sr["avg_rs30"]:+.2f}%</span>'
        f'<span style="color:#94a3b8;">({sr["avg_rvol"]}x)</span></div>'
        for sr in sec_rot_stats
    ])
    st.markdown(
        f'<div class="lab-thin-ribbon">'
        f'<span class="lab-ribbon-chip" style="border-color:rgba(168,85,247,0.45);color:#e9d5ff;font-weight:800;">🧭 セクター資金流</span>'
        f'{sec_ribbon}</div>',
        unsafe_allow_html=True
    )
    with st.expander("🧭 5大セクター資金ローテーション・詳細指標", expanded=False):
        for sr in sec_rot_stats:
            st.markdown(f'<div style="font-size:11px;color:#cbd5e1;padding:3px 0;border-bottom:1px solid rgba(148,163,184,0.12);"><b>{html.escape(sr["genre"])}</b>（{sr["count"]}銘柄）: 30mRS <b>{sr["avg_rs30"]:+.2f}%</b> ｜ RVOL <b>{sr["avg_rvol"]}x</b> ｜ CLV <b>{sr["avg_ofi"]:+.2f}</b> ｜ FlowScore <b>{sr["flow_score"]:+.1f}</b></div>', unsafe_allow_html=True)

def cut_stocks(slist, pct): return slist[:max(3, int(round(len(slist) * (pct / 100.0))))] if slist else []

def _top5_eligibility_key(item: dict) -> tuple:
    ft_d = item.get("forward_test", {})
    t_days = int(ft_d.get("total_days", 0))
    pf_v = float(ft_d.get("profit_factor", 0.0))
    eligible = 1 if (int(item.get("exec_score", 0)) >= 4 and (t_days < 3 or pf_v >= 1.0)) else 0
    exp_val = float(item.get("fusion_expect_pct", item.get("expect_pct", 0.0)))
    return (eligible, exp_val)

cats = ["🏆 総合TOP5", "⚛️ ボラティリティ突破TOP10", "🏛️ 5分足需給ミクロTOP10", "🚨 重大ニュース＆連動株", "🎟️ 直近IPO・グロース実測分析", "🏦 BVC-VPIN・CLV資金フロー", "🔥 出来高サージ＆市場注目度", "📋 監視シート", "📓 トレード日誌＆AI監査"] + [f"📂 {g}" for g in DYNAMIC_GENRES]
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

sel_cat, surv = st.session_state.get("active_category"), cut_stocks(sorted(all_res, key=_top5_eligibility_key, reverse=True), survival_cut_pct)

if sel_cat == "🏆 総合TOP5":
    top5_sorted = sorted(surv, key=_top5_eligibility_key, reverse=True)[:5]
    for i, r in enumerate(top5_sorted, 1): render_card(r, rank=i, kp="top5")
elif sel_cat == "⚛️ ボラティリティ突破TOP10":
    for i, r in enumerate(sorted(surv, key=lambda x: x["q_score"], reverse=True)[:10], 1): render_card(r, rank=i, kp="qtop")
elif sel_cat == "🏛️ 5分足需給ミクロTOP10":
    for i, r in enumerate(sorted(surv, key=lambda x: x["ms_score"], reverse=True)[:10], 1): render_card(r, rank=i, kp="mstop")
elif sel_cat == "🚨 重大ニュース＆連動株":
    if not all_impact_news: st.info("現在、新規の重大ヘッドラインは検出されていません。")
    else:
        for n in all_impact_news:
            cross_tag = '<span class="pill-badge" style="background:rgba(16,185,129,0.2);border-color:#10b981;color:#6ee7b7;font-weight:800;">✅ クロス検証済</span>' if n.get("cross_verified") else ""
            st.markdown(f'<div class="rank-card" style="border-left-color:#ef4444;"><div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:4px;"><div><span style="font-size:11px;color:#f87171;font-weight:800;">🚨 {html.escape(n["cat"])}</span> {cross_tag}</div><div><span style="font-size:10.5px;color:#94a3b8;margin-right:6px;">{html.escape(n.get("source",""))} ({n.get("age_hours",0)}h前)</span><span class="pill-badge" style="color:#fde047;border-color:#fde047;">実測重要度: {n.get("impact_score", 70)}点</span></div></div><div style="font-size:14.5px;font-weight:800;color:#f8fafc;margin-top:4px;margin-bottom:4px;">{html.escape(n["title"])}</div></div>', unsafe_allow_html=True)
            if st.button("🔥 詳細レポートを見る", key=f"tab_n_{n['id']}", use_container_width=True): st.session_state["selected_news_item"] = n; st.session_state["navigation_page"] = "NEWS_DETAIL"; st.session_state["scroll_top_trig"] = int(time.time()*1000); st.rerun()
elif sel_cat == "🎟️ 直近IPO・グロース実測分析":
    st.markdown('<div class="glass-header"><div style="font-size:16px;font-weight:800;color:#f8fafc;">🎟️ 2階建てIPO・グロース市場 実測サバイバルターミナル</div><div style="font-size:11px;color:#94a3b8;margin-top:3px;">① 上場予定・新規承認IPO注目企業（企業名・上場予定日・想定価格・主幹事・初値需給見立て） ＋ ② 既上場IPO・グロース実測サバイバルTOP6</div><div style="margin-top:8px;"><a href="https://www.jpx.co.jp/listing/stocks/new/index.html" target="_blank" rel="noopener noreferrer" class="ipo-link-btn" style="border-color:#38bdf8;color:#7dd3fc;">🏛️ 日本取引所グループ(JPX) 新規上場会社情報公式ページを開く</a></div></div>', unsafe_allow_html=True)
    with st.spinner("📡 上場予定・新規承認IPO企業＆既上場グロース広域プールを実測スキャン中..."): ipo_bundle = fetch_real_ipo_growth_analysis()

    st.markdown("### ① 上場予定・新規承認IPO 注目企業一覧")
    upcoming_ipos = ipo_bundle.get("upcoming_ipos", []) if isinstance(ipo_bundle, dict) else []
    for idx_u, u_ipo in enumerate(upcoming_ipos, 1):
        c_raw_u = str(u_ipo.get("code", "未定")).strip()
        code_badge_u = f"証券コード: {c_raw_u}" if c_raw_u != "未定" else "コード未定（上場準備・承認待ち）"
        ld_disp = str(u_ipo.get("listing_date_disp", "上場準備・観測中"))
        st.markdown(
            f'<div class="rank-card" style="border-left-color:#a855f7;background:linear-gradient(180deg,#160d2b 0%,#090d16 100%)!important;">'
            f'<div style="display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin-bottom:6px;">'
            f'<span class="pill-badge" style="background:rgba(16,185,129,0.24);border-color:#10b981;color:#6ee7b7;font-weight:900;font-size:11.5px;">📅 上場予定日/時期: {html.escape(ld_disp)}</span>'
            f'<span class="pill-badge" style="background:#a855f7;color:#fff;font-weight:800;">{html.escape(str(u_ipo.get("stage_label", "上場注目企業")))}</span>'
            f'<span class="quantum-badge">報道熱量 {int(u_ipo.get("heat_score", 60))}点</span>'
            f'</div>'
            f'<div style="font-size:17.5px;font-weight:800;color:#f8fafc;">🏷️ {html.escape(str(u_ipo.get("name", "")))} <span style="font-size:12px;color:#38bdf8;font-family:\'JetBrains Mono\',monospace;">[{html.escape(code_badge_u)}]</span></div>'
            f'<div style="font-size:11.5px;color:#cbd5e1;margin-top:4px;">🏛️ <b>上場市場:</b> {html.escape(str(u_ipo.get("market", "-")))} ｜ 🏦 <b>主幹事証券:</b> {html.escape(str(u_ipo.get("lead_underwriter", "-")))}</div>'
            f'<div class="winrate-bar" style="margin-top:8px;text-align:left;padding:8px 10px;">'
            f'<div><div style="font-size:9.5px;color:#fde047;">💰 想定価格 / 公開価格（仮条件）</div><div style="font-size:11.5px;font-weight:800;color:#f8fafc;">{html.escape(str(u_ipo.get("offer_info", "未公表 / 観測中")))}</div></div>'
            f'<div><div style="font-size:9.5px;color:#38bdf8;">🗓️ ブックビルディング(BB)期間</div><div style="font-size:11.5px;font-weight:800;color:#e0f2fe;">{html.escape(str(u_ipo.get("bb_info", "スケジュール確認中")))}</div></div>'
            f'<div><div style="font-size:9.5px;color:#c084fc;">📦 吸収金額規模・需給タイプ</div><div style="font-size:11.5px;font-weight:800;color:#f3e8ff;">{html.escape(str(u_ipo.get("absorption_scale", "-")))}</div></div>'
            f'</div>'
            f'<div style="background:rgba(15,23,42,0.88);border:1px solid rgba(56,189,248,0.28);border-radius:7px;padding:8px 10px;margin-top:7px;font-size:11.5px;line-height:1.65;color:#e2e8f0;">'
            f'<b>🎯 事業内容・強み・注目ポイント（{html.escape(str(u_ipo.get("theme", "")))}）:</b><br>{html.escape(str(u_ipo.get("business_desc", "")))}'
            f'</div>'
            f'<div style="background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.38);border-radius:7px;padding:8px 10px;margin-top:6px;font-size:11.5px;line-height:1.65;color:#d1fae5;">'
            f'<b>📊 初値・セカンダリー需給の見立て（クオンツ視点）:</b><br>{html.escape(str(u_ipo.get("supply_outlook", "")))}'
            f'</div>'
            f'<div style="background:rgba(2,6,23,0.75);border:1px solid rgba(168,85,247,0.3);border-radius:6px;padding:6px 10px;margin-top:6px;font-size:11.5px;color:#e9d5ff;">📰 <b>最新関連ニュース見出し:</b> {html.escape(str(u_ipo.get("latest_headline", "")))}</div>'
            f'<div style="margin-top:8px;">'
            f'<a href="{html.escape(str(u_ipo.get("jpx_ipo_url", "https://www.jpx.co.jp/listing/stocks/new/index.html")))}" target="_blank" rel="noopener noreferrer" class="ipo-link-btn" style="border-color:#10b981;color:#6ee7b7;">🏛️ JPX新規上場公式</a>'
            f'<a href="{html.escape(str(u_ipo.get("yahoo_url", "https://finance.yahoo.co.jp/stocks/ipo")))}" target="_blank" rel="noopener noreferrer" class="ipo-link-btn" style="border-color:#38bdf8;color:#7dd3fc;">💹 Yahoo!ファイナンスIPO</a>'
            f'<a href="{html.escape(str(u_ipo.get("kabutan_url", "https://kabutan.jp/")))}" target="_blank" rel="noopener noreferrer" class="ipo-link-btn">📊 株探リンク</a>'
            f'</div></div>',
            unsafe_allow_html=True
        )
        if re.match(r"^[1-9][0-9]{2}[0-9A-Z]$", c_raw_u):
            if st.button(f"🔵 {u_ipo['name']} ({c_raw_u}) の3階層MTF＆売買戦略を診断する", key=f"up_ipo_diag_{idx_u}_{c_raw_u}", use_container_width=True):
                st.session_state["custom_search_code"] = f"{c_raw_u}.T"; st.session_state["scroll_top_trig"] = int(time.time() * 1000); st.rerun()

    st.markdown("### ② 既上場IPO・グロース実測サバイバルTOP6")
    survivors_ipo = ipo_bundle.get("survivors", []) if isinstance(ipo_bundle, dict) else []
    if not survivors_ipo:
        st.info("📡 現在既上場IPO銘柄の相場データを再取得中です。数秒後に再度お試しください。")
    for ipo in survivors_ipo:
        chg_col = "#10b981" if ipo["chg_pct"] >= 0 else "#ef4444"
        lockup_badge = f'<span class="pill-badge" style="background:rgba(245,158,11,0.25);border-color:#f59e0b;color:#fde047;font-weight:900;">{html.escape(ipo.get("lockup_note", ""))}</span>' if ipo.get("lockup_alert") else ""
        meta_note_html = f'<div style="font-size:10px;color:#6ee7b7;margin-top:3px;">{html.escape(ipo.get("ipo_meta_note", ""))}</div>' if ipo.get("ipo_meta_note") else ""
        st.markdown(f'<div class="rank-card" style="border-left-color:#f59e0b;"><div style="display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin-bottom:6px;"><span class="pill-badge" style="background:rgba(16,185,129,0.24);border-color:#10b981;color:#6ee7b7;font-weight:900;font-size:11.5px;">📅 上場日: {html.escape(str(ipo.get("listing_date") or "実測特定済"))}（上場後 {int(ipo.get("days_since_listing", 0)):,}日経過）</span>{lockup_badge}</div><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;flex-wrap:wrap;gap:4px;"><div><span class="pill-badge" style="background:#f59e0b;color:#0f172a;font-weight:900;">🏆 生存 第{ipo["rank"]}位</span><span class="pill-badge" style="background:rgba(250,204,21,0.2);color:#fde047;border-color:#facc15;">スコア {ipo["score"]}点</span></div><div style="font-size:11px;color:#38bdf8;font-weight:700;">{html.escape(ipo["tier"])}</div></div><div><span style="font-size:18px;font-weight:800;color:#f8fafc;">{html.escape(ipo["name"])}</span> <span style="font-size:12px;color:#94a3b8;">({ipo["code"]} / {html.escape(ipo["market"])})</span></div><div style="font-size:11px;color:#cbd5e1;margin-top:3px;">🎯 {html.escape(ipo["theme"])} ｜ 🏦 主幹事: {html.escape(str(ipo.get("lead_underwriter", "-")))} ｜ 📦 吸収規模: {html.escape(str(ipo.get("absorption_scale", "-")))}</div><div class="winrate-bar" style="margin-top:8px;"><div><div style="font-size:9.5px;color:#94a3b8;">🏷️ 公開価格</div><div style="font-size:12px;font-weight:800;color:#e2e8f0;">{html.escape(str(ipo.get("offer_price_str", "-")))}</div></div><div><div style="font-size:9.5px;color:#fde047;">🚀 初値 (公募比)</div><div style="font-size:12px;font-weight:800;color:#fde047;">{html.escape(str(ipo.get("initial_price_str", "-")))}</div></div><div><div style="font-size:9.5px;color:#38bdf8;">💰 現在値 (前日比 / 初値比)</div><div style="font-size:12px;font-weight:800;">{ipo["price"]} (<span style="color:{chg_col};">{ipo["chg_pct"]:+.2f}%</span> / 初値比 <b style="color:#6ee7b7;">{html.escape(str(ipo.get("curr_vs_init_str", "-")))}</b>)</div></div></div><div class="trade-plan-box" style="margin-top:6px;"><div><div style="font-size:9.5px;color:#94a3b8;">📊 当日RVOL</div><div style="font-size:12px;font-weight:800;color:#fde047;">{ipo["rvol"]}倍</div></div><div><div style="font-size:9.5px;color:#94a3b8;">📏 1ヶ月高安レンジ (高値乖離)</div><div style="font-size:11.5px;font-weight:700;">{html.escape(ipo["period_range"])} ({ipo["from_high_pct"]}%)</div></div><div><div style="font-size:9.5px;color:#94a3b8;">💴 直近売買代金 / 年率Vol</div><div style="font-size:11.5px;font-weight:700;">{ipo["turnover_m_yen"]:,.1f}百万円 / {ipo["ann_vol"]}%</div></div></div>{meta_note_html}<div style="background:rgba(2,6,23,0.75);border:1px solid rgba(245,158,11,0.28);border-radius:6px;padding:6px 10px;margin-top:6px;font-size:11.5px;color:#fef3c7;">📰 <b>最新ヘッドライン:</b> {html.escape(ipo["latest_headline"])}</div><div style="margin-top:8px;"><a href="{ipo["kabutan_url"]}" target="_blank" rel="noopener noreferrer" class="ipo-link-btn">📊 株探詳細</a><a href="{ipo["yahoo_url"]}" target="_blank" rel="noopener noreferrer" class="ipo-link-btn" style="border-color:#38bdf8;color:#7dd3fc;">💹 Yahoo!ファイナンス</a><a href="{ipo["jpx_ipo_url"]}" target="_blank" rel="noopener noreferrer" class="ipo-link-btn" style="border-color:#10b981;color:#6ee7b7;">🏛️ JPX新規上場情報</a></div></div>', unsafe_allow_html=True)
        if st.button(f"🔵 {ipo['name']} ({ipo['code']}) の実戦検証と売買戦略詳細を見る", key=f"ipo_diag_{ipo['code']}", use_container_width=True): st.session_state["custom_search_code"] = ipo["full_code"]; st.session_state["scroll_top_trig"] = int(time.time() * 1000); st.rerun()
elif sel_cat == "🏦 BVC-VPIN・CLV資金フロー":
    for i, r in enumerate(sorted(surv, key=lambda x: x["inst_score"], reverse=True)[:10], 1): render_card(r, rank=i, kp="inst")
elif sel_cat == "🔥 出来高サージ＆市場注目度":
    for i, r in enumerate(sorted(surv, key=lambda x: x["surge_attention_score"], reverse=True)[:10], 1): render_card(r, rank=i, kp="mom")
elif sel_cat == "📋 監視シート":
    wl = st.session_state["watchlist"]
    if len(wl) >= 2:
        pf_diag = analyze_watchlist_portfolio_risk(wl)
        if pf_diag.get("has_alert"):
            if pf_diag.get("is_high_risk"):
                st.markdown(
                    f'<div class="rank-card" style="border-left-color:#ef4444;background:linear-gradient(180deg,#2a0d16 0%,#090d16 100%)!important;padding:12px 14px;">'
                    f'<div style="font-size:13px;font-weight:900;color:#fca5a5;">🛡️ AEGIS リスク監査官：セクター集中・相関過多リスク警告（監視 {pf_diag["count"]}銘柄）</div>'
                    f'<div style="font-size:11.5px;color:#fecdd3;margin-top:4px;line-height:1.6;">'
                    f'・<b>直近60日平均相関係数:</b> <b style="color:#fde047;">{pf_diag["avg_corr"]:.2f}</b>（閾値 0.70） ｜ '
                    f'<b>最大集中セクター:</b> <b style="color:#fde047;">{html.escape(pf_diag["top_genre"])} ({pf_diag["max_sector_pct"]:.1f}%)</b>（閾値 60%）<br>'
                    f'💡 <b>分散推奨メッセージ:</b> 監視銘柄の値動きが強く連動しており、セクター急落時に同時被弾するリスクが高い状態です。ディフェンシブ大型（電力・銀行・商社）や別テーマ銘柄を組み入れて相関分散を図ってください。'
                    f'</div></div>',
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f'<div class="rank-card" style="border-left-color:#10b981;padding:10px 14px;">'
                    f'<div style="font-size:12px;font-weight:800;color:#6ee7b7;">🛡️ AEGIS ポートフォリオ分散診断：良好（監視 {pf_diag["count"]}銘柄）</div>'
                    f'<div style="font-size:11px;color:#d1fae5;margin-top:2px;">直近60日平均相関係数: <b>{pf_diag["avg_corr"]:.2f}</b> ｜ 最大セクター比率: <b>{html.escape(pf_diag["top_genre"])} ({pf_diag["max_sector_pct"]:.1f}%)</b> — 適切なリスク分散が維持されています。</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
    if st.button("⚡ 総合TOP3を一括登録", use_container_width=True):
        for it in surv[:3]: wl[it["code"]] = _merge_dd_intel_into_lab_item(it)
        cu = st.session_state.get("authenticated_user", "")
        if cu: save_watchlist(cu, wl)
        st.rerun()
    for wc, wi in list(wl.items()): render_card(wi, kp=f"wl_{wc}")
elif sel_cat == "📓 トレード日誌＆AI監査":
    st.markdown('<div class="glass-header"><div style="font-size:16px;font-weight:800;color:#f8fafc;">📓 実戦トレード日誌 ＆ クオンツ監査官（AEGIS・SENTINEL）振り返り採点</div><div style="font-size:11px;color:#94a3b8;margin-top:3px;">銘柄カードから記録したエントリープランの決済確定・損益集計・AI規律監査を実行します</div></div>', unsafe_allow_html=True)
    cu_j = st.session_state.get("authenticated_user", "")
    j_entries = load_trade_journal(cu_j)
    if not j_entries:
        st.info("まだトレード日誌に記録がありません。各銘柄カードの『🎯 日誌記録』ボタンから登録してください。")
    else:
        closed_j = [x for x in j_entries if x.get("status") == "CLOSED"]
        tot_j_pnl = sum(float(x.get("pnl_yen", 0.0)) for x in closed_j)
        win_j = sum(1 for x in closed_j if float(x.get("pnl_yen", 0.0)) > 0)
        wr_j = round((win_j / len(closed_j)) * 100.0, 1) if closed_j else 0.0
        st.markdown(f'<div class="forward-verify-bar" style="margin-bottom:10px;"><span>📊 <b>日誌通算成績:</b> 全{len(j_entries)}件（決済済 {len(closed_j)}件 / 保有中 {len(j_entries)-len(closed_j)}件）</span><span>勝率: <b style="color:#fde047;">{wr_j:.1f}%</b> ｜ 確定純損益: <b style="color:{"#10b981" if tot_j_pnl>=0 else "#ef4444"};">{tot_j_pnl:+,.0f}円</b></span></div>', unsafe_allow_html=True)

        for idx_j, je in enumerate(j_entries):
            jid = je.get("id", str(idx_j))
            fc_j = je.get("full_code", "")
            is_jp_j = ".T" in fc_j
            ep_j = float(je.get("entry_price", 0.0))
            tp_j = float(je.get("tp_price", 0.0))
            sl_j = float(je.get("sl_price", 0.0))
            sh_j = int(je.get("shares", 100))
            side_j = je.get("side", "LONG")
            st_j = je.get("status", "OPEN")
            border_c = "#38bdf8" if st_j == "OPEN" else ("#10b981" if float(je.get("pnl_yen", 0.0)) >= 0 else "#ef4444")
            status_badge = '<span class="pill-badge" style="background:rgba(56,189,248,0.22);border-color:#38bdf8;color:#7dd3fc;font-weight:800;">⏳ 保有中 (OPEN)</span>' if st_j == "OPEN" else f'<span class="pill-badge" style="background:{"rgba(16,185,129,0.22)" if float(je.get("pnl_yen",0))>=0 else "rgba(239,68,68,0.22)"};border-color:{border_c};color:#f8fafc;font-weight:800;">✅ 決済済 ({float(je.get("pnl_pct",0)):+.2f}% / {float(je.get("pnl_yen",0)):+,.0f}円)</span>'

            st.markdown(
                f'<div class="rank-card" style="border-left-color:{border_c};margin-bottom:10px;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:4px;">'
                f'<div><b>{html.escape(je.get("name",""))} [{html.escape(je.get("code",""))}]</b> <span style="font-size:11px;color:#94a3b8;">({html.escape(je.get("style",""))} / {side_j} / {sh_j:,}株)</span></div>'
                f'<div>{status_badge}</div></div>'
                f'<div style="font-size:11px;color:#cbd5e1;margin-top:4px;">記録日時: {html.escape(str(je.get("created_at","")))} ｜ 約定値: <b>{fmt_px(ep_j, is_jp_j, fc_j)}</b> ｜ 計画TP: <b style="color:#10b981;">{fmt_px(tp_j, is_jp_j, fc_j)}</b> ｜ 計画SL: <b style="color:#f87171;">{fmt_px(sl_j, is_jp_j, fc_j)}</b></div>'
                f'</div>',
                unsafe_allow_html=True
            )
            if st_j == "OPEN":
                jc_a, jc_b, jc_c = st.columns([2.2, 1.3, 1.0])
                exit_in = jc_a.number_input("決済価格", min_value=0.01, value=max(0.01, ep_j), step=1.0 if is_jp_j else 0.1, key=f"j_exit_px_{jid}", label_visibility="collapsed")
                if jc_b.button("💰 決済確定＆AI監査", key=f"j_close_{jid}", use_container_width=True, type="primary"):
                    pnl_rate = ((exit_in - ep_j) / max(ep_j, 1e-4)) if side_j == "LONG" else ((ep_j - exit_in) / max(ep_j, 1e-4))
                    je["exit_price"] = float(exit_in)
                    je["closed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    je["status"] = "CLOSED"
                    je["pnl_pct"] = round(pnl_rate * 100.0, 2)
                    je["pnl_yen"] = round(ep_j * sh_j * pnl_rate, 2)
                    with st.spinner("🛡️ AEGIS＆SENTINELがトレード規律を監査中..."):
                        je["ai_feedback"] = evaluate_journal_trade_audit(je, all_res)
                    j_entries[idx_j] = je
                    save_trade_journal(cu_j, j_entries)
                    st.rerun()
                if jc_c.button("🗑️ 削除", key=f"j_del_{jid}", use_container_width=True):
                    del j_entries[idx_j]
                    save_trade_journal(cu_j, j_entries)
                    st.rerun()
            else:
                fb_txt = str(je.get("ai_feedback", ""))
                if fb_txt:
                    st.markdown(f'<div class="beginner-action-box" style="margin-top:-4px;margin-bottom:12px;">{html.escape(fb_txt).replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
                jb1, jb2 = st.columns([3, 1])
                if jb1.button("🔄 AI監査を再実行", key=f"j_reaudit_{jid}", use_container_width=True):
                    with st.spinner("🛡️ クオンツ監査官が再採点中..."):
                        je["ai_feedback"] = evaluate_journal_trade_audit(je, all_res)
                    j_entries[idx_j] = je
                    save_trade_journal(cu_j, j_entries)
                    st.rerun()
                if jb2.button("🗑️ 削除", key=f"j_del_c_{jid}", use_container_width=True):
                    del j_entries[idx_j]
                    save_trade_journal(cu_j, j_entries)
                    st.rerun()
elif sel_cat.startswith("📂 "):
    for i, r in enumerate(cut_stocks(g_res.get(sel_cat.replace("📂 ", ""), []), survival_cut_pct), 1): render_card(r, rank=i, kp=f"g_{sel_cat}")

st.markdown('<div class="disclaimer-banner"><b>⚖️ 重要免責事項・法的表示</b><br>本システム「YAMASHISHI LAB」が提供するすべての指標（ボラティリティ突破指数・WKB統計近似モデル、5分足60日OHLCV需給ミクロ構造近似、日足2年中期トレンド・MAパーフェクトオーダー・MACD・52週位置・日足ATR14・価格帯別出来高Volume Profile(LVN上値真空/HVNしこり壁)・対ベンチマークRSα・30分イントラデイRS先行度、過去10年週足大局アルゴリズム・10年POC価格帯別出来高解析、BVC-VPIN・Kyle-λ統計近似、WRVヒゲ拒絶ベクトル、OR15分初動レンジ判定・時間帯補正RVOL・3階層MTF5条件執行品質ゲート、VWAP±1σ/2σ動的バンド過熱判定・PDH/PDL前日高値安値・機関オーダーブロック(OB)支持帯検出・東証値幅制限(ストップ高/ストップ安)自動キャップ、決算跨ぎリスク遮断ゲート、監視ポートフォリオ相関＆セクター集中リスク診断、5大セクター資金ローテーション・ヒートマップ、当日実測寄付きギャップ／理論寄付き試算値、期待度パーセンテージ、LAB×DEEP DIVE双方向統合予測・同期判定、リークフリー検証統計(勝率/PF/SQN/平均R/最大DD/エクイティカーブ/時間帯別勝率)、スマホ即発注用OCOオーダーチケットBOX、Geminiクオンツ監査合議ログ、トレード日誌AI監査、および買い・空売り双方の売買プラン）は、過去の5分足・日足・週足四本値および出来高(OHLCV)データと数理アルゴリズムに基づく研究シミュレーション・情報提供を目的としたものであり、実際の板情報（Tick）やPTS実勢値に基づくものではなく、特定の有価証券の売買推奨や投資助言（投資助言・代理業等）を行うものではありません。株式投資（特に信用取引・空売り）には元本割れや元本超過損・市場変動のリスクが伴います。最終的な投資判断および資金配分は、必ず利用者ご自身の自己責任にて行っていただけますようお願い申し上げます。</div>', unsafe_allow_html=True)
