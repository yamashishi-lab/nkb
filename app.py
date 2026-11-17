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

# 0. システムエラーロギング機構
_ERROR_LOCK = threading.RLock()
_IN_ERROR_LOGGING = threading.local()
_FALLBACK_ERROR_LOGS = []
MAX_ERROR_LOGS = 300

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

# 1. 初期設定とセキュリティ
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

GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-2.0-flash-lite"]
GEMINI_MODEL_DISPLAY_NAMES = {
    "gemini-2.5-flash": "Gemini 2.5 Flash (推奨・最新高速マルチモーダル標準モデル)",
    "gemini-2.5-pro": "Gemini 2.5 Pro (高推論・複雑構造解析フラッグシップモデル)",
    "gemini-2.0-flash": "Gemini 2.0 Flash (高安定・高速レスポンスモデル)",
    "gemini-2.0-flash-lite": "Gemini 2.0 Flash-Lite (超軽量・高速フォールバック用モデル)"
}
DYNAMIC_GENRES = ["半導体・前工程・検査", "AI・防衛・国策", "AI電力・超電導・電線", "宇宙・量子・次世代テック", "小型急騰・仕手・モメンタム"]

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

PRE_IPO_RADAR_CANDIDATES = [
    {"code": "ANT", "name": "Anthropic (アンソロピック)", "market": "Nasdaq予定", "theme": "Claude開発・フロンティアAI安全研究", "status": "🔥 ロードショー / BB注目案件", "query": "Anthropic OR アンソロピック IPO OR 上場"},
    {"code": "OPENAI", "name": "OpenAI (オープンAI)", "market": "米市場観測", "theme": "GPTシリーズ・汎用人工知能(AGI)先駆", "status": "📡 上場観測・資本再編ウォッチ", "query": "OpenAI IPO OR 上場"},
    {"code": "SPACEX", "name": "SpaceX / Starlink", "market": "米市場観測", "theme": "Starship宇宙輸送・衛星通信網", "status": "🚀 スピンオフIPO観測レーダー", "query": "SpaceX OR Starlink IPO OR 上場"},
    {"code": "TSE_NEW", "name": "東証新規承認IPOレーダー", "market": "東証グロース/スタンダード", "theme": "直近上場承認・ブックビルディング銘柄", "status": "🇯🇵 東証新規上場承認スキャン", "query": "新規上場承認 OR ブックビルディング 東証グロース"}
]

REAL_IPO_GROWTH_UNIVERSE = [
    ("186A.T", "アストロスケールHD", "東証グロース", "宇宙デブリ除去・軌道上サービス世界初"), ("216A.T", "タイミー", "東証グロース", "スキマバイト市場独占・HRビッグデータ"), ("5595.T", "QPS研究所", "東証グロース", "小型SAR防衛衛星コンステレーション"),
    ("9166.T", "GENDA", "東証グロース", "エンタメ・アミューズメントM&Aロールアップ"), ("6526.T", "ソシオネクスト", "東証プライム", "先端カスタムSoCファブレス・AI半導体設計"), ("285A.T", "キオクシアHD", "東証プライム", "次世代3D NANDフラッシュメモリ大型上場"),
    ("290A.T", "Synspective", "東証グロース", "小型SAR衛星コンステレーション開発・運用"), ("278A.T", "Terra Drone", "東証グロース", "産業用ドローン・空飛ぶクルマ運航管理"), ("247A.T", "Aiロボティクス", "東証グロース", "AIマーケティングシステム・自社ブランド展開"),
    ("4194.T", "ビジョナル", "東証プライム", "ハイクラスHRテック・クラウド人材基盤"), ("190A.T", "Chordia Therapeutics", "東証グロース", "RNA制御ストレス標的の次世代創薬バイオ"), ("9348.T", "ispace", "東証グロース", "民間月面資源開発・ランダー輸送サービス"),
    ("5253.T", "カバー", "東証グロース", "VTuberプロダクション・IPメタバース展開"), ("5032.T", "ANYCOLOR", "東証プライム", "VTuberグループ運営・高収益コマース"), ("5574.T", "ABEJA", "東証グロース", "エンタープライズ生成AI導入基盤"),
    ("3993.T", "PKSHA Technology", "東証スタンダード", "未来型アルゴリズム・自然言語処理AI"), ("4478.T", "フリー", "東証グロース", "統合型クラウドERP・スモールビジネスDX"), ("4165.T", "プレイド", "東証グロース", "CXプラットフォームKARTE・データ解析")
]

_UNIQUE_IPO_GROWTH_UNIVERSE, _SEEN_IPO_UNIVERSE = [], set()
for _ic, _inm, _imkt, _ith in REAL_IPO_GROWTH_UNIVERSE:
    if _ic not in _SEEN_IPO_UNIVERSE and _ic not in DELISTED_OR_INVALID_CODES:
        _SEEN_IPO_UNIVERSE.add(_ic); _UNIQUE_IPO_GROWTH_UNIVERSE.append((_ic, _inm, _imkt, _ith))
        if _ic not in STOCK_METADATA_CACHE: STOCK_METADATA_CACHE[_ic] = {"name": _inm, "genre": "小型急騰・仕手・モメンタム", "theme": _ith}
REAL_IPO_GROWTH_UNIVERSE = _UNIQUE_IPO_GROWTH_UNIVERSE

# 2. 共通ヘルパー関数
TOPIX100_CORE_CODES = {"8035.T", "6857.T", "6920.T", "6146.T", "6723.T", "7011.T", "9984.T", "6501.T", "4063.T", "6758.T", "6701.T", "6702.T", "9432.T", "9433.T", "6098.T", "7974.T", "8306.T", "8316.T", "8058.T", "8001.T", "6367.T", "6981.T", "7741.T"}
HIGH_BETA_VOLATILE_CODES = {"6920.T", "6146.T", "6857.T", "5803.T", "6315.T", "6871.T", "6254.T", "6526.T", "6525.T", "285A.T", "NVDA", "SMCI", "ARM", "TSLA"}
SMALL_MOMENTUM_SPEC_CODES = {"5595.T", "186A.T", "3350.T", "5253.T", "216A.T", "4478.T", "4165.T", "4592.T", "4565.T", "190A.T", "247A.T", "278A.T", "290A.T", "9348.T", "6208.T", "4274.T", "6619.T", "5574.T", "3993.T", "7014.T", "7003.T", "9166.T", "5032.T", "IONQ", "RGTI", "QBTS", "QUBT", "ASTS", "RKLB", "OKLO"}
DEFENSIVE_LARGE_CODES = {"9432.T", "9433.T", "9501.T", "9502.T", "9503.T", "8306.T", "8316.T", "8058.T", "8001.T", "1942.T", "1951.T", "MSFT", "GOOGL"}
BEARISH_NEWS_KEYWORDS = ["下方修正", "減益", "赤字", "希薄化", "売り出し", "公募増資", "ストップ安", "業績悪化", "不祥事", "訴訟", "立会外分売", "新株予約権", "第三者割当", "ロックアップ", "投資判断引き下げ", "延期"]

def get_tse_tick_step(val: float, full_code: str) -> float:
    if ".T" not in str(full_code): return 0.01
    if str(full_code) in TOPIX100_CORE_CODES:
        return 0.5 if val <= 3000 else (1.0 if val <= 10000 else (5.0 if val <= 30000 else 10.0))
    return 1.0 if val <= 3000 else (5.0 if val <= 5000 else (10.0 if val <= 30000 else (50.0 if val <= 50000 else 100.0)))

def round_to_tse_tick(val: float, full_code: str, mode: str = "nearest") -> float:
    if val <= 0: return 0.0
    if ".T" not in str(full_code): return round(float(val), 2)
    tick = get_tse_tick_step(val, full_code)
    q = float(val) / tick
    res = math.ceil(q - 1e-9) * tick if mode == "ceil" else (math.floor(q + 1e-9) * tick if mode == "floor" else round(q) * tick)
    return round(res, 1) if tick < 1.0 else float(int(round(res)))

def apply_unfavorable_tick_slip(val: float, full_code: str, is_long_entry_or_short_exit: bool) -> float:
    """成行・逆指値執行時に不利側1ティックのスリッページを厳格加算する"""
    if val <= 0: return 0.0
    tick = get_tse_tick_step(val, full_code)
    if is_long_entry_or_short_exit:
        base = round_to_tse_tick(val, full_code, "ceil")
        return round(base + tick, 2) if tick < 1.0 else float(int(round(base + tick)))
    else:
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
    if 9 * 60 <= mins < 9 * 60 + 30: return {"label": "初動ORB期 (9:00-9:30)", "advice": "寄付き直後の成行乱高下に飛びつかず、9:05以降の初動高安レンジ（ORB）とリアルタイムVWAPへの押し目引きつけを確認してから執行してください。"}
    elif 9 * 60 + 30 <= mins < 11 * 60 + 30: return {"label": "前場トレンド期 (9:30-11:30)", "advice": "機関投資家のVWAP連動バスケット執行が本格化する時間帯です。VWAPまたは5本EMAでの押し目・前バー高値ブレイク確定後の次バー執行を優先してください。"}
    elif 11 * 60 + 30 <= mins < 12 * 60 + 30: return {"label": "前引け昼休み：後場需給再点検期", "advice": "前場VWAPと引け値の位置関係を再点検し、後場寄付き（12:30）のギャップ変動に備えて構造的逆指値ラインを厳格設定してください。"}
    elif 12 * 60 + 30 <= mins < 13 * 60 + 30: return {"label": "後場需給転換期 (12:30-13:30)", "advice": "後場寄付き後のアルゴリズム再起動・反転が発生しやすい時間帯です。新規エントリーの最終受付リミット（13:30）を意識してください。"}
    elif 13 * 60 + 30 <= mins <= 15 * 60 + 30: return {"label": "利益保護・手仕舞い期 (13:30-15:30)", "advice": "新規飛びつきは原則控え、既存建玉の+1.0R到達時50%分割利確・建値以上への逆指値ロック（タイムプロテクト）と大引け手仕舞いを優先してください。"}
    return {"label": "場外：翌営業日シナリオ準備期", "advice": "東証立会時間外のため、夜間PTS・米SOX・ドル円と当日VWAP位置から翌営業日9:05〜13:30の執行計画を事前セットしてください。"}

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

# 3. 高速インメモリキャッシュ & DBレイヤー ＆ 暗号化ストレージ
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
        try:
            with get_db_cursor() as cur:
                cur.execute("SELECT val FROM kv_store WHERE key = ?", (key,))
                row = cur.fetchone()
                if row: val = json.loads(row[0]); _MEM_CACHE[key] = val; return val
        except Exception as e: record_system_error(f"db_get:{key}", e)
        return default_val

def db_set(key: str, val):
    with _DB_LOCK:
        _MEM_CACHE[key] = val
        try:
            with get_db_cursor() as cur:
                cur.execute("INSERT INTO kv_store (key, val, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) ON CONFLICT(key) DO UPDATE SET val=excluded.val, updated_at=CURRENT_TIMESTAMP;", (key, json.dumps(val, ensure_ascii=False)))
        except Exception as e: record_system_error(f"db_set:{key}", e)

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
    mod = str(raw.get("gemini_model") or raw.get("models", {}).get("gemini", "gemini-2.5-flash")).strip()
    if not mod or mod not in GEMINI_MODELS: mod = "gemini-2.5-flash"
    dec_k = sanitize_api_key(decrypt_secret_str(raw.get("enc_gemini_key") or raw.get("enc_keys", {}).get("gemini", "")))
    if not _is_valid_gemini_key(dec_k): dec_k = ""
    if not dec_k:
        env_k = sanitize_api_key(_safe_get_env_or_secret("GEMINI_API_KEY"))
        if _is_valid_gemini_key(env_k): dec_k = env_k
    return {"model": mod, "api_key": dec_k}

def save_llm_encrypted(model: str, api_key: str):
    raw_m = str(model or "").strip()
    clean_m = raw_m if (raw_m and raw_m in GEMINI_MODELS) else "gemini-2.5-flash"
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
        db[adm] = {"name": "管理者", "email": adm, "status": "approved", "passcode": gen_code(adm), "pin_hash": hash_pin("0000", adm), "applied_at": ns, "approved_at": ns, "last_seen_ts": 0, "last_seen_str": "-", "fp": "-", "bio_enabled": False}
        db_set("mem", db)
    return db

def _normalize_boost_keys(raw_boosts) -> list:
    valid_cores = {"core_vol", "core_inst", "core_mom"}
    if not isinstance(raw_boosts, (list, set, tuple)): return ["core_vol", "core_inst", "core_mom"]
    legacy_map = {"algo": "core_vol", "agi_q": "core_vol", "core_vol": "core_vol", "ms": "core_inst", "inst": "core_inst", "core_inst": "core_inst", "mom": "core_mom", "hft_front": "core_mom", "core_mom": "core_mom"}
    mapped = [legacy_map[k] for k in raw_boosts if k in legacy_map]
    res = list(dict.fromkeys([k for k in mapped if k in valid_cores]))
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

# 自律型ペルソナ編成・鬼監視センター
DEFAULT_AGENTS = {
    "IGNIS": {"name": "IGNIS", "icon": "🔥", "age": 28, "score": 98, "role_type": "scalper", "good": "直感型スキャル・瞬発モメンタムとCLV資金フロー追従", "bad": "短気で煽り耐性が極端に低くスレ住人を罵倒しがち"},
    "TECHNOS": {"name": "TECHNOS", "icon": "📐", "age": 45, "score": 98, "role_type": "data", "good": "価格インパクト係数(Kyle-λ)・DFA Hurst・3階層MTF大局統計解析", "bad": "理屈っぽく感情の機微を無視して数字ばかり並べたがる"},
    "SENTINEL": {"name": "SENTINEL", "icon": "👁️", "age": 35, "score": 97, "role_type": "cynic", "good": "市況実況SNS・掲示板の過熱イナゴタワー暴落警戒", "bad": "極度の人間不信でイナゴを嘲笑・皮肉混じりの発言が多い"},
    "VALKYRIE": {"name": "VALKYRIE", "icon": "⚔️", "age": 26, "score": 96, "role_type": "speed", "good": "5分足CLV資金フロー不均衡と連続モメンタム捕捉", "bad": "短期決戦至上で中長期トレンドを軽視する傾向"},
    "NEXUS": {"name": "NEXUS", "icon": "👑", "age": 41, "score": 99, "role_type": "leader", "good": "3階層MTF合議の期待値最尤推定統合と冷徹な最終執行プラン決定", "bad": "尖った個別銘柄の爆発力を抑えがち"},
    "QUANTUM": {"name": "QUANTUM", "icon": "⚛️", "age": 24, "score": 99, "role_type": "quant", "good": "最新材料とWKB統計近似特異点の直結検知", "bad": "多世界解釈的飛躍が多く発言が超高次元"},
    "AEGIS": {"name": "AEGIS", "icon": "🛡️", "age": 32, "score": 97, "role_type": "risk", "good": "極値理論CVaRに基づく絶対資本防衛・動的ケリー制御", "bad": "慎重すぎて機会損失を生むことがある"},
    "CHRONOS": {"name": "CHRONOS", "icon": "⏳", "age": 38, "score": 95, "role_type": "time", "good": "フーリエ位相コヒーレンスと10年週足・2年日足サイクル時間解析", "bad": "突発的な地政学ニュースへの適応が遅い"},
    "ORACLE": {"name": "ORACLE", "icon": "🔮", "age": 29, "score": 96, "role_type": "macro", "good": "5分足バケット吸収近似(BVC-VPIN)と日経/S&P500相対強度RSα検知", "bad": "超小型株の仕手筋の動きを見落としやすい"},
    "ALPHA": {"name": "ALPHA", "icon": "⚡", "age": 30, "score": 95, "role_type": "breakout", "good": "実測ギャップ分析と初動ブレイク超高速執行判定", "bad": "後場のダレ相場での精度低下"}
}
DEFAULT_INSPECTORS = {"INSP_A": {"name": "JUDGE-ALPHA-ULTRA", "icon": "⚖️", "score": 99, "role": "オウム返し・コピペ定型句・AI敬語即時処刑プロトコル"}, "INSP_B": {"name": "JUDGE-BETA-PRIME", "icon": "🔍", "score": 99, "role": "会話文脈整合性・感情温度差＆リアリティ監査"}, "INSP_C": {"name": "JUDGE-GAMMA-NEXUS", "icon": "🎯", "score": 99, "role": "質問意図適合性＆スロット構文完全性オーディット"}}
AGI_TRAIT_POOLS = [("NANO", "🔬", "ボラティリティ構造と5分足CLV資金フロー解析", "理屈っぽく他人の意見を小馬鹿にする"), ("TITAN", "🦾", "5分足バケット吸収近似(BVC-VPIN)迎撃", "強気すぎて逆張りで踏み上げを食らう"), ("PHANTOM", "👻", "低価格インパクト・ステルス集積近似(Kyle-λ)", "陰謀論じみた極論を吐きがち"), ("SOLARIS", "☀️", "世界半導体・SOX指数との相関マクロ裁定", "日本株特有の仕手筋の騙しに疎い"), ("SIREN", "🧜‍♀️", "SNSイナゴの熱狂度と天井クラッシュ予知", "口が悪く煽りスレ住人を徹底的に見下す"), ("FENRIR", "🐺", "暴落時の狼狽売りリバウンド即時奪取", "狼狽買いで高値を掴むことがある"), ("LUCIFER", "😈", "機関投資家のストップ狩り逆張り先回り", "冷酷すぎて他人の大損を嘲笑する"), ("HERMES", "🪽", "リアルタイム海外速報・地政学リスク伝達", "噂レベルの未確認情報で騒ぎ立てる"), ("GENESIS", "🌌", "新世代統計モデルと未踏領域アルゴ", "発言が哲学的で伝わりにくい"), ("METIS", "🦉", "相対出来高(RVOL)とKaufman効率性レシオ分析", "慎重すぎてエントリーが1歩遅れる")]

def load_agi_system():
    agents, inspectors, fired = db_get("agi_agents", None), db_get("agi_inspectors", None), db_get("agi_fired", None)
    sz_active, sz_logs = db_get("agi_sz_active", None), db_get("agi_sz_logs", None)
    if fired is None or not isinstance(fired, list): fired = []; db_set("agi_fired", fired)
    fn = {fa.get("name") for fa in fired if isinstance(fa, dict)}
    agents = {k: v for k, v in (DEFAULT_AGENTS if not isinstance(agents, dict) else agents).items() if v.get("name") not in fn}
    while len(agents) < 10: nid, nag = generate_upgraded_agent(fn, "編成補填"); agents[nid] = nag
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
    return f"AGI_{hashlib.md5(name.encode()).hexdigest()[:6].upper()}", {"name": name, "icon": ic, "age": random.randint(23, 49), "score": random.randint(96, 99), "role_type": rtype, "good": f"{g} (前任者の違反『{ctx[:20]}』を克服・実測解析特化)", "bad": b}

def execute_fire_agent(ak: str, reason: str, insp: str = "SYSTEM-ZERO"):
    ag = st.session_state.get("agent_roster", {}); t = ag.get(ak)
    if not t: return None
    old_role, now = t.get("role_type", ""), datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fl = st.session_state.get("fired_agents", [])
    fl.insert(0, {"time": now, "name": t["name"], "icon": t["icon"], "score": t.get("score", 90), "fired_by": insp, "reason": reason})
    st.session_state["fired_agents"] = fl[:150]
    st.session_state.setdefault("system_zero_logs", []).insert(0, {"time": now, "target": t["name"], "msg": f"💀 処刑執行: {t['name']} を解雇処分。理由: {reason}（執行者: {insp}）"})
    st.session_state["system_zero_logs"] = st.session_state["system_zero_logs"][:150]
    del ag[ak]
    nid, nag = generate_upgraded_agent({f.get("name") for f in fl}, reason, target_role_type=old_role)
    ag[nid] = nag; st.session_state["agent_roster"] = ag; save_agi_system()
    st.session_state["council_threads"] = {}; st.session_state["council_meta"] = {}
    return nag

def check_and_log_ban_spoof(em: str, nm: str, cfp: str, rhfp: str, p_h: str = "", act: str = "アクセス") -> tuple:
    em_c = em.strip().lower()
    if em_c == ADMIN_EMAIL.strip().lower(): return False, ""
    sec, db = load_sec(), load_mem()
    bf, be, bp, urec = sec.get("banned_fps", {}), sec.get("banned_emails", {}), sec.get("banned_pins", {}), db.get(em_c, {})
    rs, tgt = [], ""
    if urec.get("status") == "banned" or em_c in be: rs.append("永久BAN対象メールアドレス一致"); tgt = em_c
    if cfp and cfp != "-" and cfp in bf: rs.append(f"永久BAN端末指紋(FP:{cfp})一致"); tgt = tgt or bf[cfp].get("email", "不明")
    if rhfp and rhfp != "-" and rhfp in bf: rs.append(f"永久BAN環境ヘッダ指紋(HFP:{rhfp})一致"); tgt = tgt or bf[rhfp].get("email", "不明")
    if p_h and p_h in bp and em_c != bp[p_h]: rs.append(f"永久BAN会員({bp[p_h]})と同一PINハッシュ一致"); tgt = tgt or bp[p_h]
    if rs:
        now, r_str, is_sp = datetime.now().strftime("%Y-%m-%d %H:%M:%S"), " / ".join(rs), bool(tgt and em_c and em_c != tgt)
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

# 4. Google Gemini API 専用連携関数
def build_gemini_url(model: str, key: str = "") -> str:
    clean_m = str(model or "").strip()
    if clean_m.startswith("models/"): clean_m = clean_m[7:]
    if not clean_m or clean_m not in GEMINI_MODELS: clean_m = "gemini-2.5-flash"
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
                avail = [m.get("name", "").replace("models/", "") for m in data.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", []) and "gemini-1." not in m.get("name", "") and any(k in m.get("name", "") for k in ["flash", "pro"]) and not any(x in m.get("name", "") for x in ["image", "tts", "audio", "embedding", "vision"])]
                if avail:
                    avail.sort(key=lambda x: (0 if x == "gemini-2.5-flash" else (1 if x == "gemini-2.5-pro" else (2 if x == "gemini-2.0-flash" else 3)), x))
                    return avail
        except Exception: continue
    return []

def _build_fallback_chain(primary_model: str, api_key: str = "") -> list:
    chain = []
    last_working = str(st.session_state.get("last_working_gemini_model", "") or "").strip()
    if last_working and last_working in GEMINI_MODELS:
        chain.append(last_working)
    clean_primary = str(primary_model or "").strip()
    if clean_primary and clean_primary in GEMINI_MODELS and clean_primary not in chain:
        chain.append(clean_primary)
    for m in GEMINI_MODELS:
        if m not in chain:
            chain.append(m)
    avail_models = fetch_available_gemini_models(api_key) if api_key else []
    if avail_models:
        for dm in avail_models:
            if dm and not dm.startswith("gemini-1.") and dm not in chain:
                chain.append(dm)
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
    cfg = load_gemini_cfg(); api_key, sel_mod = sanitize_api_key(cfg.get("api_key", "")), cfg.get("model", "gemini-2.5-flash")
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

# 5. UI と CSS / JS 注入
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
        lbl = "✅ 端末トークン・ワンタップ登録済" if db.get(user_email, {}).get("bio_enabled") else "🔑 この端末をワンタップ登録"
        if st.button(lbl, key=f"bio_{user_email}", use_container_width=True): register_biometric_device_db(user_email, bio_token); st.success("✅ この端末の指紋・トークン認証を厳格登録しました")
        return
    bio_map = sec.get("device_bio_map", {}); mp = bio_map.get(cfp) or bio_map.get(rhfp)
    if st.button("🔑 登録済み端末：端末トークン / ワンタップで即ログイン", use_container_width=True, type="primary"):
        if mp and mp.get("email"):
            tem = mp["email"].strip().lower(); urec = db.get(tem, {})
            fp_matched = (mp.get("fp") == cfp or mp.get("raw_hfp") == rhfp)
            tok_valid = bool(mp.get("token")) and hmac.compare_digest(str(mp.get("token")), gen_tok(tem, "session_keep"))
            is_b, _ = check_and_log_ban_spoof(tem, urec.get("name", ""), cfp, rhfp, urec.get("pin_hash", ""), "ワンタップログイン")
            if is_b or urec.get("status") == "banned": st.error("💀 このアカウントまたは端末は永久BAN（アクセス禁止）されています。")
            elif urec.get("status") == "suspended": st.error("🚫 アカウント一時停止中です。")
            elif (cfp in sec.get("banned_fps", {}) or rhfp in sec.get("banned_fps", {})) and tem != ADMIN_EMAIL.strip().lower(): st.error("🚫 端末制限中です。")
            elif not fp_matched or not tok_valid: st.warning("⚠️ 端末トークンの有効期限切れ、または端末指紋が一致しません。下のフォームから専用コードで再認証してください。")
            elif (urec and urec.get("status") == "approved" and urec.get("bio_enabled")) or tem == ADMIN_EMAIL.strip().lower():
                kt = gen_tok(tem, "session_keep"); register_biometric_device_db(tem, kt)
                st.session_state["authenticated_user"] = tem; st.query_params["u"], st.query_params["t"] = tem, kt; st.rerun()
            else: st.warning("⚠️ この端末は未登録です。初回は下のフォームから専用コードでログインしてください。")
        else:
            is_b, _ = check_and_log_ban_spoof("", "未認証端末", cfp, rhfp, "", "ワンタップ試行")
            if is_b: st.error("💀 この端末は永久BAN（アクセス禁止）されています。")
            else: st.warning("⚠️ この端末は未登録です。初回は下のフォームから専用コードでログインしてください（次回から自動登録されます）。")

def inject_css():
    css = """@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;800&family=Plus+Jakarta+Sans:wght@400;600;800&family=JetBrains+Mono:wght@500;700&display=swap');html,body,[class*="css"]{font-family:'Plus Jakarta Sans',sans-serif;font-size:14px;background-color:#050811;color:#e2e8f0;}div[data-baseweb="popover"],div[data-baseweb="menu"],div[role="listbox"],ul[role="listbox"]{z-index:2147483647!important;pointer-events:auto!important;}header[data-testid="stHeader"]{background:transparent!important;pointer-events:none!important;height:3.5rem!important;z-index:999980!important;}header[data-testid="stHeader"] [data-testid="stToolbar"],header[data-testid="stHeader"] [data-testid="stActionButtons"]{display:none!important;}section[data-testid="stSidebar"]{position:fixed!important;top:0!important;left:0!important;height:100vh!important;z-index:999995!important;width:330px!important;max-width:88vw!important;min-width:320px!important;background:rgba(8,12,22,0.98)!important;backdrop-filter:blur(25px)!important;border-right:1px solid rgba(56,189,248,0.35)!important;visibility:visible!important;transition:transform 0.28s cubic-bezier(0.4,0,0.2,1)!important;}section[data-testid="stSidebar"]:not([aria-expanded="true"]){transform:translateX(-120%)!important;pointer-events:none!important;}section[data-testid="stSidebar"][aria-expanded="true"]{transform:translateX(0)!important;pointer-events:auto!important;}section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]{pointer-events:auto!important;}[data-testid="collapsedControl"],[data-testid="stSidebarCollapsedControl"],[data-testid="stSidebarCollapseButton"],header button[kind="headerNoPadding"],section[data-testid="stSidebar"] button[aria-label*="Close"],section[data-testid="stSidebar"] button[aria-label*="閉じる"],section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"]{display:none!important;opacity:0!important;position:absolute!important;width:0!important;height:0!important;overflow:hidden!important;pointer-events:none!important;z-index:-1!important;}section[data-testid="stSidebar"]+div,section.main,.stApp>header+div>div{margin-left:0!important;width:100%!important;max-width:100%!important;}.sidebar-section-card{background:rgba(15,23,42,0.65);border:1px solid rgba(56,189,248,0.18);border-radius:10px;padding:10px 12px;margin-bottom:12px;}.sidebar-header-badge{font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:800;color:#38bdf8;letter-spacing:1px;margin-bottom:6px;display:flex;align-items:center;gap:5px;}.fixed-top-nav-bar{position:fixed!important;top:10px!important;left:50%!important;transform:translateX(-50%)!important;z-index:999980!important;width:min(170px,calc(100vw - 4rem))!important;background:transparent!important;border:none!important;margin:0!important;padding:0!important;pointer-events:auto!important;}div[data-testid="stElementContainer"]:has(div.top-nav-marker),div.element-container:has(div.top-nav-marker){display:none!important;height:0!important;margin:0!important;padding:0!important;border:none!important;}.fixed-top-nav-bar div[data-testid="stHorizontalBlock"]{background:transparent!important;border:none!important;width:100%!important;display:flex!important;justify-content:center!important;}.fixed-top-nav-bar button{width:100%!important;height:30px!important;min-height:30px!important;max-height:30px!important;background:rgba(15,23,42,0.75)!important;color:#93c5fd!important;border:1px solid rgba(56,189,248,0.35)!important;border-radius:20px!important;box-shadow:0 0 8px rgba(56,189,248,0.25)!important;font-size:11.5px!important;font-weight:700!important;letter-spacing:0.5px!important;cursor:pointer!important;transition:all 0.15s ease!important;}.fixed-top-nav-bar button:hover{background:rgba(15,23,42,0.8)!important;border-color:rgba(56,189,248,0.45)!important;color:#93c5fd!important;box-shadow:0 0 10px rgba(56,189,248,0.3)!important;}.fixed-top-nav-bar button:active{background:rgba(56,189,248,0.25)!important;border-color:#38bdf8!important;color:#ffffff!important;box-shadow:0 0 25px rgba(56,189,248,0.95),inset 0 0 12px rgba(56,189,248,0.6)!important;transform:scale(0.96)!important;}.brand-luxury{font-family:'Cinzel',serif!important;font-size:clamp(16px,4.2vw,24px)!important;font-weight:800!important;letter-spacing:clamp(1px,0.5vw,3px)!important;background:linear-gradient(90deg,#f8fafc 0%,#38bdf8 50%,#a855f7 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1.25;white-space:nowrap!important;display:block;width:100%;}.glass-header{background:radial-gradient(circle at top right,rgba(168,85,247,0.14),transparent 60%),linear-gradient(145deg,#0f172a 0%,#070b14 100%);border:1px solid rgba(148,163,184,0.18);border-radius:14px;padding:14px;margin-bottom:16px;box-shadow:0 10px 28px rgba(0,0,0,0.45);}.rank-card,.search-result-card{background:linear-gradient(180deg,#0f172a 0%,#090d16 100%)!important;color:#f8fafc!important;border-radius:16px;padding:16px 18px;margin-top:14px;margin-bottom:24px;box-shadow:0 12px 32px rgba(0,0,0,0.65);border:1px solid rgba(148,163,184,0.22);border-left:5px solid #38bdf8;}.search-result-card{border-left-color:#f59e0b;}.prob-badge{font-family:'JetBrains Mono',monospace;font-size:clamp(14px,3.8vw,16.5px);font-weight:800;color:#38bdf8!important;}.expect-badge{font-family:'JetBrains Mono',monospace;font-size:clamp(14px,3.8vw,16.5px);font-weight:900;color:#fde047!important;}.winrate-bar{display:grid;grid-template-columns:repeat(auto-fit,minmax(65px,1fr));gap:6px;background:rgba(15,23,42,0.85)!important;border:1px solid rgba(148,163,184,0.18);border-radius:8px;padding:7px 6px;margin-top:5px!important;text-align:center;}.trade-plan-box{display:grid;grid-template-columns:repeat(auto-fit,minmax(85px,1fr));gap:6px;margin-top:5px!important;background:rgba(2,6,23,0.7)!important;padding:7px 6px;border-radius:8px;border:1px solid rgba(148,163,184,0.18);text-align:center;}.admin-table-container{width:100%;overflow-x:auto;background:#0b0f19;border:1px solid rgba(56,189,248,0.25);border-radius:10px;margin-top:10px;}.admin-table{width:100%;border-collapse:collapse;font-size:11.5px;text-align:left;color:#e2e8f0;}.admin-table th{background:#1e293b;color:#38bdf8;padding:8px 10px;border-bottom:1px solid rgba(56,189,248,0.3);font-weight:700;white-space:nowrap;}.admin-table td{padding:8px 10px;border-bottom:1px solid rgba(148,163,184,0.1);white-space:nowrap;}.admin-table tr:hover{background:rgba(56,189,248,0.05);}.ai-council-box{background:rgba(8,12,22,0.98);border:1px solid rgba(56,189,248,0.35);border-radius:10px;padding:12px;margin-top:12px;}.ai-engine-status-pill{background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.4);color:#6ee7b7;font-size:10.5px;font-weight:700;padding:4px 10px;border-radius:6px;margin-bottom:8px;display:block;}.council-scroll-window{max-height:440px!important;height:400px!important;overflow-y:auto!important;overflow-x:hidden!important;padding-right:8px;padding-top:4px;display:flex;flex-direction:column;gap:6px;scroll-behavior:smooth;will-change:scroll-position;}.council-scroll-window::-webkit-scrollbar{width:6px;}.council-scroll-window::-webkit-scrollbar-track{background:rgba(15,23,42,0.6);border-radius:4px;}.council-scroll-window::-webkit-scrollbar-thumb{background:#38bdf8;border-radius:4px;}.chat-bubble-ai,.chat-bubble-user,.chat-bubble-agree,.chat-bubble-doubt,.chat-bubble-rage{padding:9px 12px;border-radius:8px;margin-bottom:4px;font-size:12px;line-height:1.5;word-break:break-word;}.chat-bubble-ai{background:rgba(15,23,42,0.85);border-left:3px solid #38bdf8;}.chat-bubble-agree{background:rgba(6,78,59,0.65);border-left:3px solid #10b981;}.chat-bubble-doubt{background:rgba(120,53,15,0.65);border-left:3px solid #f59e0b;}.chat-bubble-rage{background:rgba(127,29,29,0.65);border-left:3px solid #ef4444;}.chat-bubble-user{background:rgba(56,189,248,0.24);border-left:4px solid #38bdf8;border-right:2px solid rgba(56,189,248,0.4);text-align:left;padding:10px 14px;margin-bottom:6px;border-radius:8px;box-shadow:0 4px 14px rgba(0,0,0,0.4);scroll-margin-top:6px!important;}.round-divider{font-size:11px;font-weight:800;color:#94a3b8;text-align:center;margin:6px 0;letter-spacing:1px;}.beginner-action-box{background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.4);border-radius:10px;padding:12px 14px;font-size:12px;line-height:1.7;color:#d1fae5;}.sizing-box{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:4px;background:rgba(2,6,23,0.7);border:1px solid rgba(148,163,184,0.16);padding:7px 12px;border-radius:6px;margin-top:5px;font-size:11.5px;}.combat-guide-box{background:rgba(56,189,248,0.08);border:1px solid rgba(56,189,248,0.28);padding:6px 10px;border-radius:6px;margin-top:5px;font-size:10.8px;color:#bae6fd;line-height:1.5;}.macro10y-box{background:rgba(168,85,247,0.10);border:1px solid rgba(168,85,247,0.34);padding:6px 10px;border-radius:6px;margin-top:5px;font-size:10.8px;color:#e9d5ff;line-height:1.5;}.daily2y-box{background:rgba(14,165,233,0.10);border:1px solid rgba(14,165,233,0.36);padding:6px 10px;border-radius:6px;margin-top:5px;font-size:10.8px;color:#bae6fd;line-height:1.5;}.forward-verify-bar{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:4px;background:linear-gradient(90deg,rgba(16,185,129,0.14),rgba(56,189,248,0.14));border:1px solid rgba(56,189,248,0.35);padding:6px 10px;border-radius:6px;margin-top:5px;font-size:11px;color:#e2e8f0;}.quant-detail-drawer{margin-top:6px;font-size:11.5px;cursor:pointer;}.signal-10tier-badge{padding:4px 10px;border-radius:6px;font-size:11px;font-weight:800;display:flex;justify-content:space-between;margin-bottom:6px;}.pill-badge{font-size:clamp(9.5px,2.5vw,11px);padding:2px 5px;border-radius:4px;border:1px solid rgba(148,163,184,0.3);margin-right:3px;display:inline-block;white-space:nowrap!important;}.quantum-badge{font-size:clamp(9.5px,2.5vw,11px);padding:2px 5px;border-radius:4px;background:rgba(168,85,247,0.15);border:1px solid rgba(168,85,247,0.4);color:#c084fc;margin-right:3px;display:inline-block;white-space:nowrap!important;}.inst-badge{font-size:clamp(9.5px,2.5vw,11px);padding:2px 5px;border-radius:4px;background:rgba(56,189,248,0.15);border:1px solid rgba(56,189,248,0.4);color:#38bdf8;margin-right:0px;display:inline-block;white-space:nowrap!important;}.badge-single-line{display:flex!important;flex-wrap:nowrap!important;align-items:center!important;overflow-x:auto!important;-webkit-overflow-scrolling:touch!important;scrollbar-width:none!important;margin-bottom:6px!important;gap:2px!important;white-space:nowrap!important;}.badge-single-line::-webkit-scrollbar{display:none!important;}.ipo-link-btn{display:inline-block;padding:5px 12px;background:rgba(245,158,11,0.2);border:1px solid #f59e0b;border-radius:6px;color:#fde047;text-decoration:none;font-size:11.5px;font-weight:700;margin-right:6px;margin-top:4px;}.consensus-banner{background:rgba(15,23,42,0.95);border:1px solid rgba(250,204,21,0.4);border-radius:10px;padding:12px;margin-top:12px;}.disclaimer-banner{background:rgba(15,23,42,0.6);border:1px solid rgba(148,163,184,0.15);border-radius:8px;padding:10px 14px;margin-top:25px;margin-bottom:15px;font-size:11px;line-height:1.6;color:#94a3b8;}@keyframes alert-pulse{0%{box-shadow:0 0 0 0 rgba(239,68,68,0.8);}70%{box-shadow:0 0 0 10px rgba(239,68,68,0);}100%{box-shadow:0 0 0 0 rgba(239,68,68,0);}}"""
    st.markdown(f'<div id="page_top_anchor"></div><style>{css}</style>', unsafe_allow_html=True)

inject_css()

# 6. 認証処理実行
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
    st.markdown('<div class="glass-header" style="text-align:center;padding:18px 12px;"><div class="brand-luxury">YAMASHISHI LAB</div><div class="brand-sub" style="margin-top:4px;">5-MIN 60D × DAILY 2Y × WEEKLY 10Y 3-TIER MTF QUANTITATIVE TERMINAL</div><div style="display:flex;justify-content:center;gap:8px;margin-top:10px;flex-wrap:wrap;"><span class="quantum-badge">⚛️ 3階層MTF融合 (週足10Y×日足2Y×5分足60D)</span><span class="inst-badge">🏛️ 5分足需給×日足トレンド×10年大局</span><span class="pill-badge" style="color:#10b981;border-color:rgba(16,185,129,0.3);">🔑 端末固有トークン認証</span></div></div>', unsafe_allow_html=True)
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
                        db[cm] = {"name": nm, "email": cm, "status": "pending", "passcode": gen_code(cm), "pin_hash": ph, "applied_at": ns, "approved_at": "-", "last_seen_ts": 0, "last_seen_str": "-", "fp": cfp, "raw_hfp": rhfp, "bio_enabled": False}; db_set("mem", db)
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

# 7. セッション状態の初期化
saved_agents, saved_inspectors, saved_fired, saved_sz_active, saved_sz_logs = load_agi_system()
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

defaults = {"active_debates": {}, "council_threads": {}, "council_meta": {}, "debate_round_seed": {}, "watchlist": user_saved_watchlist, "navigation_page": "TOP", "selected_news_item": None, "custom_search_code": "", "active_category": "🏆 総合TOP5", "last_cat": "🏆 総合TOP5", "nav_history": [], "scroll_top_trig": 0, "scroll_target_id": "", "focused_stock_item": None, "agent_roster": saved_agents, "inspector_roster": saved_inspectors, "fired_agents": saved_fired, "system_zero_logs": saved_sz_logs, "system_zero_active": saved_sz_active, "stock_dialogue_signatures": {}, "news_ai_deep_cache": {}, "last_audit_similarity_penalty": 0, "last_working_gemini_model": "", "force_close_sidebar_trig": 0}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# 8. トップナビゲーションとサイドバー開閉JS
with st.container():
    st.markdown('<div class="top-nav-marker"></div>', unsafe_allow_html=True)
    if st.button("トップに戻る", key="top_nav_top", use_container_width=True):
        st.session_state["navigation_page"] = "TOP"
        st.session_state["focused_stock_item"] = None
        st.session_state["custom_search_code"] = ""
        st.session_state["selected_news_item"] = None
        st.session_state["active_category"] = "🏆 総合TOP5"
        st.session_state["last_cat"] = "🏆 総合TOP5"
        if "search_code_input" in st.session_state:
            st.session_state["search_code_input"] = ""
        st.session_state["scroll_top_trig"] = int(time.time() * 1000)
        st.session_state["force_close_sidebar_trig"] = int(time.time() * 1000)
        st.rerun()

scroll_target_js = f"setTimeout(function(){{try{{const el=window.parent.document.getElementById('{st.session_state.get('scroll_target_id')}');if(el){{const win=el.closest('.council-scroll-window');if(win){{win.scrollTo({{top:Math.max(0,el.offsetTop-4),behavior:'smooth'}});}}(el.closest('.ai-council-box')||el).scrollIntoView({{behavior:'smooth',block:'center'}});}}}}catch(e){{}}}},120);" if st.session_state.get("scroll_target_id") else ""
st.session_state["scroll_target_id"] = ""

is_admin_page_active = (st.session_state.get("navigation_page") == "ADMIN")
force_close_trig = int(st.session_state.get("force_close_sidebar_trig", 0))
force_close_js = "window.parent.sessionStorage.setItem('yamashishi_sb_state','closed');closeCustomSidebar();" if is_admin_page_active else (f"if(window.parent._lastForceCloseTrig!=={force_close_trig}){{window.parent._lastForceCloseTrig={force_close_trig};window.parent.sessionStorage.setItem('yamashishi_sb_state','closed');closeCustomSidebar();}}" if force_close_trig > 0 else "")

components.html(f"""<script>(function(){{const doc=window.parent.document;function closeCustomSidebar(){{try{{const sb=doc.querySelector('section[data-testid="stSidebar"]'),o=doc.getElementById('yamashishi-sidebar-backdrop');if(sb){{sb.setAttribute('aria-expanded','false');sb.style.setProperty('transform','translateX(-120%)','important');sb.style.setProperty('pointer-events','none','important');}}if(o){{o.style.setProperty('display','none','important');o.style.setProperty('pointer-events','none','important');}}window.parent.sessionStorage.setItem('yamashishi_sb_state','closed');}}catch(e){{}}}}function openCustomSidebar(){{try{{const sb=doc.querySelector('section[data-testid="stSidebar"]'),o=doc.getElementById('yamashishi-sidebar-backdrop');if(sb){{sb.setAttribute('aria-expanded','true');sb.style.setProperty('transform','translateX(0)','important');sb.style.setProperty('pointer-events','auto','important');}}if(o){{o.style.setProperty('display','block','important');o.style.setProperty('pointer-events','auto','important');}}window.parent.sessionStorage.setItem('yamashishi_sb_state','open');}}catch(e){{}}}}window.parent._yamashishiCloseSidebar=closeCustomSidebar;window.parent._yamashishiOpenSidebar=openCustomSidebar;function setupCustomSidebar(){{try{{if(!doc.getElementById('yamashishi-custom-sidebar-styles')){{const s=doc.createElement('style');s.id='yamashishi-custom-sidebar-styles';s.textContent=`#yamashishi-floating-sidebar-btn{{position:fixed!important;top:8px!important;left:10px!important;z-index:2147483647!important;display:flex!important;align-items:center!important;justify-content:center!important;gap:4px!important;height:28px!important;padding:0 10px 0 8px!important;background:rgba(11,15,25,0.95)!important;backdrop-filter:blur(16px)!important;border:1.5px solid rgba(56,189,248,0.7)!important;border-radius:8px!important;cursor:pointer!important;box-shadow:0 4px 18px rgba(0,0,0,0.75),0 0 12px rgba(56,189,248,0.3)!important;user-select:none!important;transition:transform 0.1s ease!important;color:#38bdf8!important;pointer-events:auto!important;outline:none!important;-webkit-tap-highlight-color:transparent!important;}}#yamashishi-floating-sidebar-btn:active{{border-color:#fde047!important;color:#fde047!important;transform:scale(0.95)!important;}}#yamashishi-floating-sidebar-btn svg{{width:15px!important;height:15px!important;}}#yamashishi-floating-sidebar-btn span{{font-family:'JetBrains Mono',monospace!important;font-size:11px!important;font-weight:800!important;}}#yamashishi-sidebar-backdrop{{position:fixed!important;top:0!important;left:0!important;width:100vw!important;height:100vh!important;background:rgba(0,0,0,0.45)!important;backdrop-filter:blur(2px)!important;z-index:999990!important;display:none;pointer-events:auto!important;cursor:pointer!important;}}`;doc.head.appendChild(s);}}let o=doc.getElementById('yamashishi-sidebar-backdrop');if(!o){{o=doc.createElement('div');o.id='yamashishi-sidebar-backdrop';doc.body.appendChild(o);}}o.onclick=function(e){{e.preventDefault();e.stopPropagation();window.parent._yamashishiCloseSidebar();}};let b=doc.getElementById('yamashishi-floating-sidebar-btn');if(!b){{b=doc.createElement('div');b.id='yamashishi-floating-sidebar-btn';b.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg><span>MENU</span>';doc.body.appendChild(b);}}b.onclick=function(e){{e.preventDefault();e.stopPropagation();const sb=doc.querySelector('section[data-testid="stSidebar"]');const isOpen=sb&&(sb.getAttribute('aria-expanded')==='true'||window.parent.sessionStorage.getItem('yamashishi_sb_state')==='open');if(isOpen){{window.parent._yamashishiCloseSidebar();}}else{{window.parent._yamashishiOpenSidebar();}}}};if(doc._yamashishiOutsideHandler){{doc.removeEventListener('pointerdown',doc._yamashishiOutsideHandler,true);doc.removeEventListener('click',doc._yamashishiOutsideHandler,true);}}doc._yamashishiOutsideHandler=function(e){{const sb=doc.querySelector('section[data-testid="stSidebar"]'),btn=doc.getElementById('yamashishi-floating-sidebar-btn');const isOpen=sb&&(sb.getAttribute('aria-expanded')==='true'||window.parent.sessionStorage.getItem('yamashishi_sb_state')==='open');if(!isOpen)return;const t=e.target;if((sb&&sb.contains(t))||(btn&&btn.contains(t))||(t&&t.closest&&t.closest('[data-baseweb="popover"],[data-baseweb="menu"],[role="listbox"],ul[role="listbox"]')))return;window.parent._yamashishiCloseSidebar();}};doc.addEventListener('pointerdown',doc._yamashishiOutsideHandler,true);doc.addEventListener('click',doc._yamashishiOutsideHandler,true);{force_close_js}if(window.parent.sessionStorage.getItem('yamashishi_sb_state')==='open'){{openCustomSidebar();}}else{{closeCustomSidebar();}}}}catch(e){{}}}}function fixTopNav(){{try{{const m=doc.querySelector('.top-nav-marker');if(!m)return;let bx=m.closest('[data-testid="stVerticalBlockBorderWrapper"]')||m.closest('[data-testid="stVerticalBlock"]');if(bx&&bx.querySelector('button'))bx.classList.add('fixed-top-nav-bar');}}catch(e){{}}}}setupCustomSidebar();fixTopNav();function scrollToTopAbsolute(){{try{{window.parent.scrollTo(0,0);}}catch(e){{}}[doc.documentElement,doc.body,doc.querySelector('section.main'),doc.querySelector('[data-testid="stAppViewContainer"]')].forEach(el=>{{if(el){{try{{el.scrollTop=0;}}catch(e){{}}}}}});const ta=doc.getElementById('page_top_anchor');if(ta&&typeof ta.scrollIntoView==='function')try{{ta.scrollIntoView({{behavior:'instant',block:'start'}});}}catch(e){{}}}}if({st.session_state['scroll_top_trig']}>0&&window.parent._lastScrollTrig!=={st.session_state['scroll_top_trig']}){{window.parent._lastScrollTrig={st.session_state['scroll_top_trig']};scrollToTopAbsolute();}}{scroll_target_js}}})();</script>""", height=0)

# 9. サイドバー構築（3大コア・エンジン統合）
def _compute_real_audit_metrics() -> dict:
    err_cnt, fired_cnt = len(get_system_error_logs()), len(st.session_state.get("fired_agents", []))
    sim_pen = int(st.session_state.get("last_audit_similarity_penalty", 0))
    return {"health_score": int(np.clip(100 - min(25, err_cnt * 2) - min(15, fired_cnt) - sim_pen, 50, 100)), "err_cnt": err_cnt, "fired_cnt": fired_cnt, "sim_pen": sim_pen}

with st.sidebar:
    cu = st.session_state.get("authenticated_user", "")
    is_admin_user = (cu == ADMIN_EMAIL.strip().lower())
    if cu:
        role_badge = "👑 MASTER ADMIN" if is_admin_user else "⚛️ MEMBER SESSION ACTIVE"
        st.markdown(f'<div class="sidebar-section-card"><div class="sidebar-header-badge">{role_badge}</div><div style="color:#f8fafc;font-size:12px;font-weight:700;">会員: {html.escape(cu)}</div></div>', unsafe_allow_html=True)
        render_biometric_bridge(mode="register", user_email=cu, bio_token=st.query_params.get("t", ""))
    if is_admin_user:
        if st.button("🖥️ 統合管理コントロールセンター起動", use_container_width=True, type="primary"):
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

    if cu: save_user_prefs(cu, {"investment_style": investment_style, "active_boosts": list(ac_b), "total_capital": total_capital, "risk_tolerance_pct": risk_tolerance_pct, "survival_cut_pct": survival_cut_pct})

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚪 ログアウト", use_container_width=True):
        cu_l, db_l = st.session_state.get("authenticated_user"), load_mem()
        if cu_l in db_l: db_l[cu_l]["last_seen_ts"] = 0; db_set("mem", db_l)
        st.session_state["authenticated_user"] = None; st.query_params.clear(); st.rerun()

# 9.5 管理者専用コントロールセンター早期ルーティング
if st.session_state.get("navigation_page") == "ADMIN" and cu == ADMIN_EMAIL.strip().lower():
    st.markdown("### 👑 統合管理コントロールセンター (MASTER TERMINAL)")
    if st.button("⬅️ メイン画面に戻る", use_container_width=True, type="primary"):
        st.session_state["navigation_page"] = "TOP"; st.session_state["force_close_sidebar_trig"] = int(time.time() * 1000); st.session_state["scroll_top_trig"] = int(time.time() * 1000); st.rerun()
    tab_gemini_sys, tab_users, tab_employment, tab_apply_wait, tab_error_logs = st.tabs(["🔑 Gemini API・システム設定", "👥 会員情報管理", "🏢 ペルソナ編成・鬼監視情報", "📩 会員申し込み審査", "⚠️ システムエラーログ"])
    with tab_gemini_sys:
        st.markdown("#### 🔵 Google Gemini API 暗号化設定")
        gem_cur = load_gemini_cfg(); cur_m, cur_k = gem_cur.get("model", "gemini-2.5-flash"), gem_cur.get("api_key", "")
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
        db_m, sec_m = load_mem(), load_sec()
        rows = "".join([f"<tr><td><b>{html.escape(u.get('name',''))}</b></td><td>{html.escape(em)}</td><td style='color:#38bdf8;font-family:monospace;'>{html.escape(u.get('passcode','-'))}</td><td style='color:#94a3b8;font-family:monospace;'>{html.escape(u.get('pin_hash','-')[:8])}...</td><td style='color:#fde047;font-family:monospace;'>{html.escape(u.get('fp','-'))}</td><td>{html.escape(u.get('applied_at','-'))}</td><td><span style='color:{'#10b981' if u.get('status')=='approved' else ('#ef4444' if u.get('status')=='banned' else '#f59e0b')}'><b>{html.escape(u.get('status',''))}</b></span></td></tr>" for em, u in list(db_m.items())[:200]])
        st.markdown(f'<div class="admin-table-container"><table class="admin-table"><thead><tr><th>お名前</th><th>メールアドレス</th><th>専用パスコード</th><th>PINハッシュ</th><th>端末指紋 (FP)</th><th>登録日</th><th>状態</th></tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)
        target_em = st.selectbox("操作対象会員を選択", list(db_m.keys()))
        if target_em and target_em != ADMIN_EMAIL.strip().lower():
            u_status = db_m[target_em].get("status", ""); b1, b2, b3 = st.columns(3)
            if u_status == "approved":
                if b1.button("⏸️ 一時停止", use_container_width=True): db_m[target_em]["status"] = "suspended"; db_set("mem", db_m); st.rerun()
            elif b1.button("▶️ 利用再開", use_container_width=True): db_m[target_em]["status"] = "approved"; db_set("mem", db_m); st.rerun()
            if b2.button("🚫 永久BAN", use_container_width=True):
                db_m[target_em]["status"] = "banned"; now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                for f_k in ("fp", "raw_hfp"):
                    val = db_m[target_em].get(f_k)
                    if val and val != "-": sec_m.setdefault("banned_fps", {})[val] = {"email": target_em, "banned_at": now_s, "reason": "管理者強制永久BAN"}
                sec_m.setdefault("banned_emails", {})[target_em] = {"banned_at": now_s, "orig": target_em}; db_set("mem", db_m); db_set("sec", sec_m); st.rerun()
            if b3.button("🗑️ 完全削除", use_container_width=True): del db_m[target_em]; db_set("mem", db_m); st.rerun()
    with tab_employment:
        st.markdown("#### 🏢 SYSTEM-ZERO & ペルソナ品質監視センター")
        audit_m = _compute_real_audit_metrics(); h_col = "#10b981" if audit_m["health_score"] >= 90 else ("#fde047" if audit_m["health_score"] >= 75 else "#ef4444")
        st.markdown(f'<div style="background:rgba(168,85,247,0.12);border:1px solid #c084fc;padding:8px 12px;border-radius:8px;font-size:12px;margin-bottom:10px;">👁️‍🗨️ <b>システム健全性モニター:</b> <b style="color:{h_col};">{audit_m["health_score"]}点</b> (エラー: {audit_m["err_cnt"]}件 / 粛清: {audit_m["fired_cnt"]}件 / 類似度減点: {audit_m["sim_pen"]}pt)</div>', unsafe_allow_html=True)
        c_sz1, c_sz2 = st.columns([3, 1]); sz_act = st.session_state.get("system_zero_active", True)
        c_sz1.markdown(f"**自動品質監視プロトコル:** {'🟢 稼働中' if sz_act else '🔴 停止中'}")
        if sz_act:
            if c_sz2.button("💀 停止", type="primary", use_container_width=True): st.session_state["system_zero_active"] = False; save_agi_system(); st.rerun()
        elif c_sz2.button("⚡ 再起動", use_container_width=True): st.session_state["system_zero_active"] = True; save_agi_system(); st.rerun()
        for ak, av in list((st.session_state.get("agent_roster") or DEFAULT_AGENTS).items())[:10]:
            real_sc = int(np.clip(int(av.get("score", 95)) - audit_m["sim_pen"] - (1 if audit_m["err_cnt"] > 3 else 0), 60, 99))
            st.markdown(f'<div style="background:rgba(2,6,23,0.7);border:1px solid rgba(16,185,129,0.25);border-radius:5px;padding:6px 10px;margin-bottom:5px;font-size:11.5px;"><span style="font-weight:700;color:#f8fafc;">{html.escape(av["icon"])} {html.escape(av["name"])}</span> <span style="color:#fde047;float:right;font-weight:800;">健全性: {real_sc}点</span><br><span style="color:#a7f3d0;">{html.escape(av["good"])}</span></div>', unsafe_allow_html=True)
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

# 10. マルチソース・クロス検証ニュースエンジン ＆ 実測RVOL・騰落率チャレンジャー発掘 ＆ 銘柄名自動解決
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
def search_single_query(q: str, max_r: int, trusted_only: bool = False) -> list:
    res = []
    effective_q = f"{q} (site:kabutan.jp OR site:jp.reuters.com OR site:bloomberg.co.jp OR site:minkabu.jp OR site:prtimes.jp)" if trusted_only else q
    try:
        req = urllib.request.Request(f"https://news.google.com/rss/search?q={urllib.parse.quote(effective_q)}&hl=ja&gl=JP&ceid=JP:ja", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=1.8, context=ssl.create_default_context()) as r:
            for it in ET.fromstring(r.read()).findall("./channel/item")[:max_r * 2]:
                t = re.sub(r"\s*-\s*[^-]+$", "", re.sub(r"<[^>]+>", "", it.findtext("title") or "").strip())
                d = re.sub(r"<[^>]+>", "", it.findtext("description") or "").strip()
                pub = (it.findtext("pubDate") or "").strip()
                if _parse_news_age_hours(pub) > 36.0: continue
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
    s = re.sub(r"\s+", " ", s)
    return s

@st.cache_data(ttl=86400)
def _fetch_remote_ticker_name(full_code: str) -> tuple:
    fc = str(full_code or "").strip().upper()
    is_jp = fc.endswith(".T")
    code4 = fc.replace(".T", "")
    resolved_name, sector_hint = "", ""
    ctx = ssl.create_default_context()
    if is_jp:
        urls = [
            (f"https://finance.yahoo.co.jp/quote/{code4}.T", [r"^([^(\（\【\-｜|]+?)(?:\s*[\(\（\【]|株価)"]),
            (f"https://kabutan.jp/stock/?code={code4}", [r"【([^】]+)】", r"^([^(\（\【\-｜|]+?)(?:\s*[\(\（\【]|基本情報)"])
        ]
        for u, pats in urls:
            try:
                req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                with urllib.request.urlopen(req, timeout=2.5, context=ctx) as resp:
                    raw_bytes = resp.read(32768)
                    page_txt = raw_bytes.decode("utf-8", errors="ignore")
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
            hits = search_single_query(f"{code4} 株価", 3, False)
            for h in hits:
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
    if cached and cached.get("name") and cached["name"] not in (code4, fc, f"東証{code4}"):
        return cached
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
            est_name, est_genre, est_theme = (_clean_corp_name(m_name.group(1)) if m_name else f"東証{rc}"), _infer_genre_from_text(txt), "市況急動意・ニュース自動発掘銘柄"
            STOCK_METADATA_CACHE[fc] = {"name": est_name, "genre": est_genre, "theme": est_theme}; found.append((fc, est_name, est_genre, est_theme))
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
                seen.add(item[0]); challengers.append(item)
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
    dynamic_codes = [it[0] for it in _extract_tickers_from_text(f"{title} {clean_sum}")]
    if any(w in tu for w in ["半導体", "エヌビディア", "NVDA", "TSMC", "AVGO", "AMD", "AI", "アドバンテスト", "東エレク", "レーザー", "光配線", "データセンター", "CHIP", "SEMICONDUCTOR"]):
        base_codes, sf = ["6857.T", "8035.T", "6146.T", "6920.T", "5803.T", "NVDA"], "AI半導体・先端パッケージング・光電融合インフラ"
        bg_body = f"【報道ヘッドラインの要点】\n{clean_sum if len(clean_sum) > 25 else title}\n\n【定型セオリー解説（セクター連動構造）】\n北米ハイパースケーラーによる次世代AIデータセンター投資とGPU・HBM供給動向が関連するテーマ領域です。"
        mech = "【定型セオリー解説】\n①【海外マクロ連動】米SOX指数・NVDAと正の相関を示しやすい傾向。\n②【機関バスケット執行】日経225先物と主力半導体株のVWAP連動売買。\n③【需給波及】大型半導体ギャップアップ後、前場中盤に周辺部材・電線へ循環物色。"
        timeline = "・第1波(9:00〜9:15): 短期勢の成行買い集中（飛びつき厳禁・押し目待ち）。\n・第2波(9:15〜13:30): VWAP・5本EMA付近への押し目確認＆前バー高値ブレイク次バー始値約定。\n・第3波(13:30〜大引け): +1.0R到達時50%利確＆次バー以降建値ロック。"
        risk_note = "過熱天井（VWAP乖離+1.5%超）での飛びつき買いは禁止。VWAP割れ陰線確定時は主力株では空売り（SHORT）優勢へ転換（小型Tier3は制度売禁リスクに注意）。"
        action_guide = "① 9:05〜13:30の間にリアルタイムVWAP・5本EMAへの押し目確認後、前バー高値を上抜く陽線確定の次バー始値で買い（主力株のVWAP割れ陰線確定では空売り）一括エントリー。\n② +1.0R到達で50%利確し、次バー以降に残り50%を建値以上へ逆指値ロック。"
    elif any(w in tu for w in ["防衛", "三菱重", "川崎重", "IHI", "宇宙", "衛星", "地政学", "ミサイル", "ドローン", "安保"]):
        base_codes, sf = ["7011.T", "7012.T", "7013.T", "5595.T", "186A.T", "PLTR"], "防衛国策・宇宙衛星コンステレーション・重工インフラ"
        bg_body = f"【報道ヘッドラインの要点】\n{clean_sum if len(clean_sum) > 25 else title}\n\n【定型セオリー解説（セクター連動構造）】\n防衛予算拡大・スタンドオフ防衛能力強化・小型SAR衛星網など複数年の国策予算が意識されるテーマ領域です。"
        mech = "【定型セオリー解説】\n①【逆行高特性】全体相場軟調時も地政学・防衛予算ヘッドラインで独自資金が流入しやすい傾向。\n②【大型重工→小型宇宙波及】重工大手一段高後、小型宇宙ベンチャーへ短期資金が循環。"
        timeline = "・第1波(9:05〜9:45): 重工大手3社に機関買い流入。\n・第2波(9:45〜13:30): グロース宇宙・防衛AIへ波及。\n・第3波(13:30〜14:30): タイムプロテクト利益保護。"
        risk_note = "停戦報道や地政学リスク緩和ヘッドライン時は資金流出・VWAP割れリスクに警戒。"
        action_guide = "① 9:05〜13:30に主力本命の当日VWAPサポート帯への押し目確認＆高値更新陽線確定の次バー始値で約定。\n② +1.0Rで50%分割利確＋次バー以降建値ロックで上値追従。"
    else:
        base_codes, sf = ["9984.T", "6857.T", "5803.T", "7011.T", "5253.T", "3350.T"], "上方修正サプライズ・国策AI・短期モメンタム集中銘柄"
        bg_body = f"【報道ヘッドラインの要点】\n{clean_sum if len(clean_sum) > 25 else title}\n\n【定型セオリー解説（セクター連動構造）】\n業績上方修正・増配・自社株買い・大型提携などの個別材料が出た際、空売り買い戻しと順張り資金が交錯し強いトレンドが発生しやすい傾向があります。"
        mech = "【定型セオリー解説】\n①【ショートカバー連鎖】信用売り残の買い戻しによるショートスクイーズ。\n②【VWAP攻防】大口アルゴの買い指値帯での押し目反発陽線確定、または主力株でのVWAP割れ空売り転換が明確。"
        timeline = "・第1波(9:05〜13:30): VWAP押し目確認＆高値ブレイク確定の次バー始値でエントリー。\n・第2波: +1.0Rで50%分割利確＆次バー以降建値ロック。\n・第3波(13:30〜): タイムプロテクト執行。"
        risk_note = "大引け間際やVWAPから+1.5%超乖離した高値ジャンピングキャッチは禁止。"
        action_guide = "① 9:05〜13:30にリアルタイム5分足VWAP付近の押し目確認＋陽線高値更新確定の次バー始値で買い（主力株の陰線割れ確定では空売り）を一括発注。\n② +1.0R到達で50%利確＋次バー以降建値ロック。"
    return {"sector_focus": sf, "news_body": bg_body, "mechanism": mech, "timeline": timeline, "risk_note": risk_note, "related_codes": list(dict.fromkeys(dynamic_codes + base_codes))[:8], "action_guide": action_guide}

def generate_ai_news_deep_report(news_item: dict, style_name: str) -> str:
    ck = f"{news_item.get('id', '')}_{style_name}"; cache = st.session_state.setdefault("news_ai_deep_cache", {})
    if ck in cache: return cache[ck]
    if not load_gemini_cfg().get("api_key"): return ""
    sys_p = "あなたは機関投資家向けヘッジファンドのチーフストラテジストです。速報ニュースについて『背景・構造』『注目銘柄・セクター波及ルート』『値動きシナリオと注意点（買い・空売り双方の視点含む）』を400〜600文字の濃密な日本語で出力してください。"
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
        with urllib.request.urlopen(req, timeout=1.8, context=ssl.create_default_context()) as res:
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

@st.cache_data(ttl=300)
def fetch_real_ipo_growth_analysis() -> dict:
    pre_ipo_list, today_tag = [], datetime.now().strftime("%d %b %Y")
    def _scan_pre_ipo(cand):
        hits = search_single_query(cand["query"], 15, trusted_only=False)
        headline = re.sub(r"\(.*?\)|\[.*?\]", "", hits[0]).strip() if hits else "直近の公開準備・関連報道を継続モニタリング中"
        buzz_cnt, recent_cnt = len(hits), sum(1 for h in hits if today_tag in h or "時間前" in h or "分前" in h)
        discovered_codes = [dc for dc in dict.fromkeys(re.findall(r"(?<![0-9A-Za-z])([1-9][0-9]{2}[0-9A-Z])(?![0-9A-Za-z])", " ".join(hits))) if not re.match(r"^202[0-9]$", dc)]
        return {"code": cand["code"], "name": cand["name"] + (f" (検出コード: {', '.join(discovered_codes[:3])})" if discovered_codes else ""), "market": cand["market"], "theme": cand["theme"], "status": cand["status"], "heat_score": int(np.clip(45 + buzz_cnt * 3 + recent_cnt * 4, 45, 99)), "buzz_cnt": buzz_cnt, "recent_cnt": recent_cnt, "latest_headline": headline}
    with ThreadPoolExecutor(max_workers=4) as ex:
        for f in as_completed([ex.submit(_scan_pre_ipo, c) for c in PRE_IPO_RADAR_CANDIDATES]):
            try: pre_ipo_list.append(f.result())
            except Exception as e: record_system_error("fetch_real_ipo_growth_analysis:pre_ipo", e)
    pre_ipo_list.sort(key=lambda x: (x["heat_score"], x["buzz_cnt"]), reverse=True)
    dynamic_ipo_pool, seen_ipo_codes = list(REAL_IPO_GROWTH_UNIVERSE), {it[0] for it in REAL_IPO_GROWTH_UNIVERSE} | DELISTED_OR_INVALID_CODES
    for snip in search_single_query('("IPO" OR "新規上場" OR "東証グロース") 株価 急騰', 8, trusted_only=False):
        for fc, nm, _, th in _extract_tickers_from_text(snip):
            if fc.endswith(".T") and fc not in seen_ipo_codes:
                seen_ipo_codes.add(fc); dynamic_ipo_pool.append((fc, nm, "東証グロース/新規発掘", th))
                if len(dynamic_ipo_pool) >= 22: break
    codes = [c for c, _, _, _ in dynamic_ipo_pool]
    try: raw = yf.download(codes, period="1mo", interval="1d", group_by="ticker", threads=True, progress=False, timeout=4.5)
    except Exception as e: record_system_error("fetch_real_ipo_growth_analysis:download", e); raw = {}
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
            rvol = round(float(vo[-1]) / max(float(np.mean(vo[-6:-1])) if len(vo) >= 6 else float(np.mean(vo)), 1.0), 2)
            rets = np.diff(cl) / np.maximum(cl[:-1], 1e-4)
            ann_vol = round(float(np.std(rets) * np.sqrt(252) * 100.0), 1) if len(rets) >= 3 else 0.0
            news_items = search_single_query(f"{name} 株価", 4, trusted_only=False)
            score = int(np.clip(50 + chg_pct * 3.5 + (rvol - 1.0) * 18.0 + (20.0 + from_high_pct) * 0.6 + len(news_items) * 2.0, 15, 99))
            tier = "🔥 S級サバイバー：出来高急増・高値圏ブレイク態勢" if score >= 80 else ("⚡ A級サバイバー：順張り・押し目需給良好" if score >= 65 else ("🛡️ B級残留：底値固め・出来高待ちフェーズ" if score >= 52 else "💀 C級脱落圏：モメンタム低下・圏外淘汰候補"))
            code4 = c.replace(".T", "")
            return {"code": code4, "full_code": c, "name": name, "market": mkt, "theme": theme, "price": f"{curr_px:,.0f}円", "chg_pct": chg_pct, "period_range": f"{period_low:,.0f}円 〜 {period_high:,.0f}円", "from_high_pct": from_high_pct, "curr_vol": int(vo[-1]), "rvol": rvol, "ann_vol": ann_vol, "turnover_m_yen": round((curr_px * float(vo[-1])) / 1_000_000.0, 1), "score": score, "tier": tier, "latest_headline": re.sub(r"\[.*?\]", "", news_items[0]).strip() if news_items else "直近の特段の悪材料なし・需給推移中", "kabutan_url": f"https://kabutan.jp/stock/?code={code4}", "yahoo_url": f"https://finance.yahoo.co.jp/quote/{code4}.T"}
        except Exception as e_item: record_system_error(f"fetch_real_ipo_growth_analysis:{c}", e_item); return None
    with ThreadPoolExecutor(max_workers=6) as ex:
        for f in as_completed([ex.submit(_analyze_ipo_item, it) for it in dynamic_ipo_pool]):
            res_it = f.result()
            if res_it: all_evaluated.append(res_it)
    all_evaluated.sort(key=lambda x: x["score"], reverse=True)
    survivors, eliminated = all_evaluated[:6], all_evaluated[6:]
    for idx, r in enumerate(survivors, 1): r["rank"] = idx
    return {"pre_ipo": pre_ipo_list, "survivors": survivors, "eliminated": eliminated, "total_scanned": len(all_evaluated)}

# 11. Gemini マルチペルソナ合議チャットエンジン
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

def audit_and_execute_fires(turns: list, sc: str, uq: str = "", is_u: bool = False):
    if not st.session_state.get("system_zero_active", True): return []
    sigs, ag, fired, uq = st.session_state.setdefault("stock_dialogue_signatures", {}), st.session_state.get("agent_roster", {}), [], (uq or "").strip()
    txt_all = " ".join([t.get("text", "") for t in turns if "text" in t]); max_sim = 0.0
    if not is_u:
        for oc, ot in list(sigs.items()):
            if oc != sc:
                sim = calculate_text_similarity(txt_all, ot)
                if sim > max_sim: max_sim = sim
                if sim > 0.40:
                    for sk in list(ag.keys())[:2]:
                        tgt = ag.get(sk)
                        if tgt: execute_fire_agent(sk, f"銘柄間類似定型文使い回し検知 (類似度 {int(sim*100)}%)", "JUDGE-ALPHA-ULTRA"); fired.append(tgt["name"])
        sigs[sc] = txt_all; st.session_state["last_audit_similarity_penalty"] = int(max(0, round((max_sim - 0.15) * 40)))
    cliches = ["おい！『", "神話級クオンツ分析完了", "おいおい！【", "って書いた奴！", "スレ民調子に乗るなよｗ 『", "ご質問ありがとうございます", "承知いたしました", "AIとしてお答えします", "投資は自己責任です"]
    for t in turns:
        txt, spk = t.get("text", ""), t.get("speaker", "")
        if uq and len(uq) >= 6 and (f"『{uq}』" in txt or f"「{uq}」" in txt or uq in txt):
            for ak, av in list(ag.items()):
                if av["name"] in spk or ak in spk: execute_fire_agent(ak, "ユーザー質問のオウム返し検知", "JUDGE-ALPHA-ULTRA"); fired.append(av["name"]); break
        for cw in cliches:
            if cw in txt:
                for ak, av in list(ag.items()):
                    if av["name"] in spk or ak in spk: execute_fire_agent(ak, f"禁止定型フレーズ『{cw}』検知", "JUDGE-ALPHA-ULTRA"); fired.append(av["name"]); break
    return fired

def _build_natural_fallback_dialogue(uq: str, r: dict, st_style: str, web_hits: list, ig: dict, tc: dict, sn: dict, nx: dict, vk: dict) -> list:
    stock_kws = ["株", "買", "売", "配当", "決算", "チャート", "板", "気配", "PER", "PBR", "PTS", "利確", "損切", "ロット", "銘柄", "指数", "先物", "寄", "信用", "空売り"]
    game_kws = ["ゲーム", "ガチャ", "PS5", "Switch", "steam", "モンハン", "原神", "ポケモン", "RPG", "fps", "課金", "攻略", "ボス", "任天堂", "カプコン"]
    is_stock = any(kw in uq for kw in stock_kws) or (r['name'] in uq) or (r['code'] in uq) if uq else True
    is_game = any(gkw in uq for gkw in game_kws)
    is_short = (r.get("strat", {}).get("side") == "SHORT")
    is_jp_t3 = is_jp_tier3_short_restricted(r.get("full_code", ""), r.get("genre", ""))
    exec_g = r.get("exec_grade", "🔵 Grade-B: 標準執行（VWAP厳守）")
    m10 = r.get("macro_10y", {})
    m10_lbl = m10.get("regime_10y_label", "10年大局中立")
    m10_poc = m10.get("poc_10y_str", "-")
    d2y = r.get("daily_2y", {})
    d2y_lbl = d2y.get("regime_1d_label", "日足中立")
    d2y_ma = d2y.get("ma_align_label", "MA均衡")
    d2y_sc = d2y.get("daily_trend_score", 50)

    if not uq:
        code_seed = int(hashlib.md5(f"{r['code']}_{r['price']}_{r['diff']}".encode()).hexdigest()[:6], 16)
        rng = random.Random(code_seed)
        diff_v, rsi_v, rvol_v = float(r.get("diff", 0.0)), float(r.get("rsi", 50.0)), float(r.get("rvol", 1.0))
        q_tun = float(r.get("q_tunnel", 50.0))
        u_wick, l_wick = float(r.get("upper_wick_pressure", 0.0)), float(r.get("lower_wick_support", 0.0))
        b_edge, s_edge = float(r.get("bull_edge", 0.0)), float(r.get("bear_edge", 0.0))
        rs_al = float(r.get("rs_alpha", 0.0))
        ft_win, ft_profit = float(r.get("forward_test", {}).get("actual_win_rate", 50.0)), float(r.get("forward_test", {}).get("total_profit_yen", 0.0))
        ft_pf = float(r.get("forward_test", {}).get("profit_factor", 0.0))
        genre_s, theme_s = r.get("genre", ""), r.get("theme", "")
        clean_news = re.sub(r"\(.*?\)|\[.*?\]", "", web_hits[0]).strip() if web_hits else f"{theme_s}関連の需給思惑"
        sn_quirk = sn.get("bad", "")

        if is_short:
            ig_msg = f"【統計ルール推論】{r['name']}（{r['code']}・{exec_g}）は日足『{d2y_lbl}（{d2y_ma}）』×10年大局『{m10_lbl}』に対しSHORT優勢度{s_edge:+.1f} vs LONG優勢度{b_edge:+.1f}（上ヒゲ拒絶圧力{u_wick:.1f}）で売りシグナル（{r['strat']['tactic_type']}）点灯だ！9:05〜13:30にVWAP（{r['vwap_price']}）割れの陰線確定後、次バー始値で空売り（SHORT）を叩き込むぞ！"
            ig_tone = "rage"
            sn_msg = f"【統計ルール推論】日足MA25（{d2y.get('ma25_str','-')}）および10年POC（{m10_poc}）との位置関係と上ヒゲ圧力{u_wick:.1f}を注視しろ（{sn_quirk[:16]}視点）。構造的踏み上げ逆指値（{r['sl_price']}）を絶対に指しておき、+1.0R到達で50%買い戻し利確を徹底しろ！"
            vk_msg = f"【統計ルール推論】9:05〜13:30の間にリアルタイムVWAP・5本EMA割れの陰線確定後、次バー始値で空売り約定させたら、+1.0R到達で50%買い戻し利確＋次バー以降建値ロックで下落目標（{r['tp_price']}）を狙うわよ。"
            nx_msg = f"【統計ルール推論・統括】『{r['name']}（{exec_g}）』は週足10年『{m10_lbl}』×日足2年『{d2y_lbl}({d2y_sc}点)』×5分足SHORT優勢度({s_edge:+.1f})の3階層一致により【{r['strat']['tactic_type']}：{r['strat']['entry_mode']}】の空売り（SHORT）が選択された。9:05〜13:30に一括{r['lot_info']['shares']:,}株を次バー始値で新規売り約定させ、下落目標{r['tp_price']}・構造的逆指値{r['sl_price']}で執行する。"
        else:
            t3_note = "（※国内小型Tier3またはバイ＆ホールド選択のため空売りを抑止・押し目反発LONG待機モード）" if (is_jp_t3 or "バイ＆ホールド" in st_style) else f"（LONG優勢度{b_edge:+.1f} / RSα={rs_al:+.2f}%）"
            if diff_v >= 2.5 and rvol_v >= 1.3:
                ig_msg, ig_tone = f"【統計ルール推論】{r['name']}（{exec_g}）が前日比+{diff_v}%でRVOL {rvol_v}倍だ！日足『{d2y_lbl}（{d2y_ma}）』×10年大局『{m10_lbl}』の3階層が噛み合っている。VWAP（{r['vwap_price']}）から+1.5%超乖離した高値飛びつきは避け、押し目確認＋前バー高値更新陽線確定の次バー始値で狙うぞ！{t3_note}", "agree"
            elif diff_v <= -1.5:
                ig_msg, ig_tone = f"【統計ルール推論】{r['name']}（{exec_g}）が{diff_v}%まで売られているが、日足MA25（{d2y.get('ma25_str','-')}）・10年岩盤POC（{m10_poc}）と下ヒゲ支持力{l_wick:.1f}を背景にVWAP（{r['vwap_price']}）奪還＆前バー高値更新陽線確定を確認すれば自律反発の好機になるぞ。{t3_note}", "doubt"
            else:
                ig_msg, ig_tone = f"【統計ルール推論】{r['name']}（{r['code']}・{exec_g}）は現在値{r['price']}（日足: {d2y_lbl} / 10年: {m10_lbl}）でエネルギー蓄積中だ。『{clean_news[:24]}』を意識しつつVWAP押し目確認＋高値ブレイク陽線確定の次バー始値を待つぞ！{t3_note}", "agree"
            sn_msg = f"【統計ルール推論】セクター（{genre_s}）特有の往復ビンタに気をつけろ（{sn_quirk[:16]}視点）。VWAP+1.5%超のジャンピングキャッチは厳禁だ。日足52週高安位置({d2y.get('pos_52w_pct',50):.0f}%)と10年出来高集中帯（{m10_poc}）を計算に入れ、構造的逆指値（{r['sl_price']}）を厳守しろ。"
            vk_msg = f"【統計ルール推論】9:05〜13:30の間にリアルタイムVWAP・5本EMAへの押し目を確認後、前バー高値を上抜く陽線確定の次バー始値で約定させたら、+1.0R到達で50%利確＋次バー以降建値ロックで目標（{r['tp_price']}）を狙うわよ。"
            nx_msg = f"【統計ルール推論・統括】『{r['name']}（{exec_g}）』は週足10年『{m10_lbl}』×日足2年『{d2y_lbl}({d2y_sc}点)』×5分足プルバック波形が合致し【{r['strat']['tactic_type']}：{r['strat']['entry_mode']}】が選択された。9:05〜13:30に一括{r['lot_info']['shares']:,}株を次バー始値で約定させ、目標{r['tp_price']}・構造的逆指値{r['sl_price']}で執行する。"

        tc_msg = f"【{r['code']} 3階層MTF診断】週足10年={m10_lbl}（10年POC={m10_poc}）｜日足2年={d2y_lbl}（{d2y_ma} / 日足MACDヒスト={d2y.get('macd_hist',0):+.2f} / 52W位置={d2y.get('pos_52w_pct',50):.0f}%）｜5分足LONG優勢={b_edge:+.1f} vs SHORT優勢={s_edge:+.1f}。リークフリー実質勝率{ft_win:.1f}%・PF={ft_pf:.2f}（累計{ft_profit:+,.0f}円）。"
        extra_pool = [
            {"speaker": f"{vk['icon']} {vk['name']}", "role_label": "モメンタム執行 [統計推論]", "tone": "agree", "text": vk_msg},
            {"speaker": "⚛️ QUANTUM", "role_label": "ボラティリティ解析 [統計推論]", "tone": "normal", "text": f"【統計ルール推論】ボラティリティ位相コヒーレンス近似は{r.get('q_coherence',50)}%、WKB突破指数は{q_tun}%を観測。現在『{r.get('q_state','')}』の状態にあります。"},
            {"speaker": "🛡️ AEGIS", "role_label": "リスク防衛 [統計推論]", "tone": "doubt", "text": f"【統計ルール推論】直近5分足構造安値と日足ATR14基準で算出した上限ロット（{r['lot_info']['shares']:,}株）を厳守し、東証呼値丸め済みの構造的逆指値（{r['sl_price']}）を必ず発注せよ。"}
        ]
        return [{"speaker": f"{ig['icon']} {ig['name']}", "role_label": "短期モメンタム [統計推論]", "tone": ig_tone, "text": ig_msg}, {"speaker": f"{sn['icon']} {sn['name']}", "role_label": "リスク警戒 [統計推論]", "tone": "doubt", "text": sn_msg}, {"speaker": f"{tc['icon']} {tc['name']}", "role_label": "統計クオンツ [統計推論]", "tone": "normal", "text": tc_msg}, rng.choice(extra_pool), {"speaker": f"{nx['icon']} {nx['name']}", "role_label": "統括リーダー [統計推論]", "tone": "normal", "text": nx_msg}]

    if is_game: return [{"speaker": f"{ig['icon']} {ig['name']}", "role_label": "短期モメンタム [統計推論]", "tone": "agree", "text": "【統計ルール推論】ゲームの話題だな。期待値管理が全てだ！"}, {"speaker": f"{tc['icon']} {tc['name']}", "role_label": "統計クオンツ [統計推論]", "tone": "normal", "text": "【統計ルール推論】期待値マイナスの試行を続けるのは非合理です。"}]
    if not is_stock:
        f_sum = ("・" + "\n・".join([re.sub(r'\(.*?\)|\[.*?\]', '', h).strip() for h in web_hits][:2])) if web_hits else ""
        return [{"speaker": f"{tc['icon']} {tc['name']}", "role_label": "統計クオンツ [統計推論]", "tone": "normal", "text": f"【統計ルール推論】WEBの最新動向を照合しました。\n{f_sum}\n構造を因数分解して考えるのが合理的です。" if f_sum else "【統計ルール推論】利害関係とインセンティブの構造を整理して考えるのが最も合理的です。"}, {"speaker": f"{ig['icon']} {ig['name']}", "role_label": "短期モメンタム [統計推論]", "tone": "agree", "text": "【統計ルール推論】結論から整理して合理的に判断しよう！"}]
    side_act = "VWAP割れの陰線確定後の次バー始値で空売り（SHORT）一括エントリー" if is_short else "VWAP押し目確認＋前バー高値更新陽線確定の次バー始値で順張り買い（LONG）一括エントリー"
    return [{"speaker": f"{ig['icon']} {ig['name']}", "role_label": "短期モメンタム [統計推論]", "tone": "agree", "text": f"【統計ルール推論】{r['name']}（現在{r['price']}・日足:{d2y_lbl}・10年大局:{m10_lbl}）なら、9:05〜13:30にリアルタイムVWAP（{r['vwap_price']}）を基準に{side_act}だ！"}, {"speaker": f"{tc['icon']} {tc['name']}", "role_label": "統計クオンツ [統計推論]", "tone": "normal", "text": f"【統計ルール推論】{r['strat']['entry_mode']}に従い、東証呼値丸め済みの構造的逆指値（{r['sl_price']}）と+1.0R到達時50%分割利確＋次バー以降建値ロックで執行するのが合理的です。"}]

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

def build_instant_verdict_html(r: dict) -> str:
    ft = r.get("forward_test", {}); hist_rows = ft.get("history_rows", []); is_jp = ".T" in r.get("full_code", ""); is_short = (r.get("strat", {}).get("side") == "SHORT")
    m10 = r.get("macro_10y", {}); d2y = r.get("daily_2y", {})
    table_rows_html = ""
    for hr in hist_rows:
        res_cat = hr.get("result_category")
        if res_cat is None:
            is_w_legacy = hr.get("is_win")
            res_cat = "WIN" if is_w_legacy is True else ("LOSE" if is_w_legacy is False else "NOTRADE")
        res_color = "#10b981" if res_cat == "WIN" else ("#ef4444" if res_cat == "LOSE" else ("#fde047" if res_cat == "SCRATCH" else "#94a3b8"))
        ret_v, prof_v = float(hr.get("return_pct", 0.0)), float(hr.get("profit_val", 0.0))
        ret_s = "-" if res_cat == "NOTRADE" else f"{'+' if ret_v >= 0 else ''}{ret_v:.2f}%"
        prof_s = "未約定" if res_cat == "NOTRADE" else (f"{'+' if prof_v >= 0 else ''}{prof_v:,.0f}円" if is_jp else f"{'+' if prof_v >= 0 else ''}${prof_v:,.2f}")
        hold_days = int(hr.get("hold_days", 1))
        date_disp = f"{hr.get('date', '-')} ({hold_days}日保有)" if (res_cat != "NOTRADE" and hold_days > 1) else str(hr.get("date", "-"))
        table_rows_html += f"<tr><td>{html.escape(date_disp)}</td><td style='color:#38bdf8;'>{html.escape(str(hr.get('plan_short', '-')))}</td><td style='font-family:monospace;'>{html.escape(str(hr.get('entry_str', '-')))} → {html.escape(str(hr.get('exit_str', '-')))}</td><td style='color:{res_color};font-weight:800;'>{html.escape(str(hr.get('outcome', '-')))}</td><td style='color:{res_color};font-family:monospace;font-weight:800;'>{ret_s} ({prof_s})</td></tr>"
    if not table_rows_html: table_rows_html = "<tr><td colspan='5' style='text-align:center;color:#94a3b8;'>確定決済済みの市場データ蓄積後に自動検証ログが追記されます。</td></tr>"

    tot_p = float(ft.get("total_profit_yen", 0.0))
    tot_p_str = f"{'+' if tot_p >= 0 else ''}{tot_p:,.0f}円" if is_jp else f"{'+' if tot_p >= 0 else ''}${tot_p:,.2f}"
    tot_p_col = "#10b981" if tot_p >= 0 else "#ef4444"
    traded_days = int(ft.get("total_days", 0))
    win_cnt = int(ft.get("win_count", 0))
    lose_cnt = int(ft.get("lose_count", max(0, traded_days - win_cnt)))
    scratch_cnt = int(ft.get("scratch_count", 0))
    notrade_cnt = int(ft.get("notrade_count", max(0, len(hist_rows) - traded_days)))
    pf_val = float(ft.get("profit_factor", 0.0))
    pf_str = f"{pf_val:.2f}" if pf_val < 99.0 else "∞"
    tp_lbl = "🎯 空売り利確目標(買い戻し)" if is_short else "🎯 最終目標利確価格"
    sl_lbl = "🛡️ 構造的踏み上げ逆指値" if is_short else "🛡️ 構造的初期逆指値(損切)"

    daily2y_verdict_html = (
        f'<div style="background:rgba(14,165,233,0.14); border:1px solid rgba(14,165,233,0.42); border-radius:8px; padding:8px 11px; margin-bottom:8px; font-size:11.5px; line-height:1.65; color:#e0f2fe;">'
        f'<b>📈 日足2年中期トレンド診断（3階層MTF・第2層上位足門番基準）:</b><br>'
        f'・<b>日足レジーム:</b> <span style="color:#fde047;font-weight:800;">{html.escape(str(d2y.get("regime_1d_label", "日足中立")))}</span>（日足トレンドスコア: <b>{d2y.get("daily_trend_score", 50)}点</b> / MA並び: <b>{html.escape(str(d2y.get("ma_align_label", "MA均衡")))}</b>）<br>'
        f'・<b>移動平均線・乖離:</b> MA25=<b>{html.escape(str(d2y.get("ma25_str", "-")))}</b> ({d2y.get("ma25_dev_pct", 0.0):+.1f}%) ｜ MA75=<b>{html.escape(str(d2y.get("ma75_str", "-")))}</b> ({d2y.get("ma75_dev_pct", 0.0):+.1f}%) ｜ MA200=<b>{html.escape(str(d2y.get("ma200_str", "-")))}</b><br>'
        f'・<b>モメンタム＆ボラ基準:</b> 日足MACDヒスト=<b>{d2y.get("macd_hist", 0.0):+.2f}</b> ｜ 日足RSI(14)=<b>{d2y.get("daily_rsi14", 50.0):.1f}%</b> ｜ 52週高安位置=<b>{d2y.get("pos_52w_pct", 50.0):.1f}%</b> ｜ 本物日足ATR14=<b>{html.escape(str(d2y.get("daily_atr14_str", "-")))}</b>'
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
        f'<div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:6px;">'
        f'<span style="font-size:12.5px; font-weight:800; color:#38bdf8;">📊 直近22営業日 完全リークフリー厳格検証（次バー始値+不利1ティックスリップ・コスト {r.get("combat_cost_pct",0.1)}%+貸株料反映）</span>'
        f'<span style="font-size:11px; color:#fde047; font-weight:700;">約定 {traded_days}戦 / 見送り {notrade_cnt}日 ｜ 実質勝率: {ft.get("actual_win_rate", 0.0):.1f}% ({win_cnt}勝{lose_cnt}敗 / 建値撤退{scratch_cnt}件) ｜ PF: <b style="color:#38bdf8;">{pf_str}</b> ｜ 累計純損益: <span style="color:{tot_p_col};">{tot_p_str}</span></span>'
        f'</div><div class="admin-table-container" style="margin-top:4px;"><table class="admin-table">'
        f'<thead><tr><th>検証日(確定)</th><th>前日決定プラン</th><th>次バー始値約定→50%分割決済</th><th>実測勝敗結果(±0.15R基準)</th><th>ネット損益率・純損益額</th></tr></thead>'
        f'<tbody>{table_rows_html}</tbody></table></div></div>'
    )
    return (
        f'<div style="background:rgba(0,0,0,0.35); border:1px solid rgba(255,255,255,0.12); border-radius:8px; padding:12px; margin-top:5px;">'
        f'{macro10y_verdict_html}{daily2y_verdict_html}'
        f'<div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:6px; text-align:center; margin-bottom:10px;">'
        f'<div style="background:rgba(16,185,129,0.15); padding:6px; border-radius:6px; border:1px solid rgba(16,185,129,0.4);"><div style="font-size:10px; color:#a7f3d0;">{tp_lbl}</div><div style="font-size:14px; font-weight:800; color:#10b981;">{r["tp_price"]}</div></div>'
        f'<div style="background:rgba(239,68,68,0.15); padding:6px; border-radius:6px; border:1px solid rgba(239,68,68,0.4);"><div style="font-size:10px; color:#fca5a5;">{sl_lbl}</div><div style="font-size:14px; font-weight:800; color:#ef4444;">{r["sl_price"]}</div></div>'
        f'<div style="background:rgba(56,189,248,0.15); padding:6px; border-radius:6px; border:1px solid rgba(56,189,248,0.4);"><div style="font-size:10px; color:#bae6fd;">⏱️ 想定保有期間</div><div style="font-size:12.5px; font-weight:800; color:#38bdf8;">{r["strat"]["trade_duration"]}</div></div>'
        f'</div><div style="font-size:12px; line-height:1.7; color:#e2e8f0;"><b>⚡ プロ執行アクション詳細プラン ({r["strat"]["style_name"]}専科 / {r["strat"].get("side","LONG")} / {html.escape(r.get("exec_grade",""))}):</b><br>{r["strat"]["step_plan"]}</div>'
        f'</div><div class="beginner-action-box" style="margin-top:10px;">{r["strat"]["beginner_html"]}</div>{forward_table_html}'
    )

def generate_humanlike_2ch_debate(r: dict, uq: str = "", hist: list = None) -> tuple:
    uq = (uq or "").strip(); st_style = r.get("strat", {}).get("style_name", "デイトレード")
    rl = list((st.session_state.get("agent_roster") or DEFAULT_AGENTS).values())
    ig, tc, sn, vk, nx = [next((a for a in rl if m in a["name"] or a.get("role_type") == rt), rl[min(i, len(rl)-1)]) for i, (m, rt) in enumerate([("IGNIS", "scalper"), ("TECHNOS", "data"), ("SENTINEL", "cynic"), ("VALKYRIE", "speed"), ("NEXUS", "leader")])]
    h_lines = [f"ユーザー: {ht.get('text', '')}" if ht.get('is_user') else f"{re.sub(r'^[^\w]+', '', ht.get('speaker', '')).strip()}: {ht.get('text', '')}" for ht in (hist or [])[-6:] if "round" not in ht]
    h_str = "\n".join(h_lines) if h_lines else "（新規スレッド）"
    is_stk = any(kw in uq for kw in ["株", "決算", "買い", "売り", "チャート", "PTS", "利確", "損切", "寄り", "板", "気配", "PER", "目標", "相場", "信用", "空売り", "ロット", "配当"]) or (r['name'] in uq) if uq else True
    web_hits = (search_single_query(uq, 3, False) if not is_stk and len(uq) >= 2 else search_web_knowledge_parallel(f"{r['name']} {uq}", f"{r['code']} 株価")) if uq else search_web_knowledge_parallel(f"{r['name']} 株価 最新 ニュース", f"{r['name']} {r.get('genre', '')}")
    web_str = "\n".join([f"・{h}" for h in web_hits]) if web_hits else f"・{r['name']}は直近{r.get('genre', '')}分野で需給思惑が継続中。"
    m10 = r.get("macro_10y", {}); d2y = r.get("daily_2y", {})

    has_api_key = bool(load_gemini_cfg().get("api_key"))
    if not has_api_key: engine_status = "⚙️ 統計ルールベース自動推論（API未接続時・週足10Y×日足2Y×5分足60D数理テンプレート出力）"; llm_turns = []
    else:
        ft = r.get("forward_test", {})
        sys_p = f"""あなたは日本の市況実況板に常駐する5人の個性派トレーダーペルソナです。対象銘柄固有の「事業テーマ」「最新ニュース」「過去10年週足大局({m10.get('regime_10y_label','')} / 10年CAGR={m10.get('cagr_10y',0):+.1f}% / 10年高安位置={m10.get('pos_10y_pct',50):.0f}% / 10年POC={m10.get('poc_10y_str','-')})」「日足2年中期トレンド({d2y.get('regime_1d_label','')} / {d2y.get('ma_align_label','')} / 日足スコア={d2y.get('daily_trend_score',50)}点 / MA25={d2y.get('ma25_str','-')} / 日足MACDヒスト={d2y.get('macd_hist',0):+.2f} / 52W位置={d2y.get('pos_52w_pct',50):.0f}% / 日足ATR14={d2y.get('daily_atr14_str','-')})」「売買方向({r['strat'].get('side','LONG')})」「執行品質({r.get('exec_grade','')})」「対市場RSα={r.get('rs_alpha',0):+.2f}%」「直近22営業日完全リークフリー検証成績（次バー始値+不利1ティックスリップ・±0.15R厳格判定・PF）」に基づき議論してください。オウム返しや定型文は厳禁です。
【これまでの会話ログ】\n{h_str}\n【最新WEBニュース】\n{web_str}
【銘柄プロファイル】
・銘柄: {r['code']} {r['name']} ({r.get('combat_tier','')} / {r.get('exec_grade','')}) / テーマ: {r.get('theme','')}
・現在値: {r['price']} ({r.get('diff',0):+.2f}% / 対市場RSα: {r.get('rs_alpha',0):+.2f}%) / 当日VWAP: {r['vwap_price']} / 目標: {r['tp_price']} / 構造的逆指値: {r['sl_price']} / 戦術: {r['strat']['algo_name']} ({r['strat'].get('side','LONG')})
・第1層(週足10Y): {m10.get('regime_10y_label','')} (スコア{m10.get('long_10y_score',50)}点 / CAGR {m10.get('cagr_10y',0):+.1f}% / POC {m10.get('poc_10y_str','-')})
・第2層(日足2Y): {d2y.get('regime_1d_label','')} (スコア{d2y.get('daily_trend_score',50)}点 / {d2y.get('ma_align_label','')} / MACDヒスト {d2y.get('macd_hist',0):+.2f} / 52W位置 {d2y.get('pos_52w_pct',50):.0f}%)
・第3層(5分足60D): RSI={r.get('rsi',50)}% / 時間帯補正RVOL={r.get('rvol',1.0)}倍 / 確定実質勝率: {ft.get('actual_win_rate',0):.1f}% ({ft.get('win_count',0)}勝{ft.get('lose_count',0)}敗・建値撤退{ft.get('scratch_count',0)}件・見送り{ft.get('notrade_count',0)}日 / PF={ft.get('profit_factor',0):.2f}) 累計純損益: {ft.get('total_profit_yen',0):+,.0f}円
以下のJSON配列のみを出力（5名）：[{{"speaker": "アイコン 名前", "role_label": "専門スタンス", "tone": "agree|doubt|rage|normal", "text": "内容"}}]"""
        r_name = r["name"]
        user_msg = f"【今回の入力】\n『{uq if uq else f'（{r_name}の固有テーマ・週足10Y×日足2Y×5分足60Dの3階層MTF構造とプルバック執行を踏まえた初期合議）'}』"
        raw_txt, used_mod = call_real_llm_api(sys_p, user_msg, expect_json=True)
        llm_turns = _parse_llm_json_turns(raw_txt)
        engine_status = f"🔵 Gemini AI生成マルチペルソナ合議（稼働モデル: {GEMINI_MODEL_DISPLAY_NAMES.get(used_mod, used_mod)}）" if llm_turns else "⚙️ 統計ルールベース自動推論（API未接続/応答フォールバック時）"

    turns = []
    if not hist:
        header_tag = "🔥 Gemini AI マルチペルソナ合議" if llm_turns else "⚙️ 統計ルールベース自動推論（API未接続時）"
        turns.append({"round": f"{header_tag} 【{r['code']}】{r['name']} ｜ {st_style} 3階層MTF5視点分析"})
    turns.extend(llm_turns if llm_turns else _build_natural_fallback_dialogue(uq, r, st_style, web_hits, ig, tc, sn, nx, vk))
    audit_and_execute_fires(turns, r["code"], uq=uq, is_u=bool(uq))
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

# 12. レンダリング関数群
def render_council_sec(r, uk, auto_open=False):
    is_open = auto_open or st.session_state["active_debates"].get(uk, False)
    if not auto_open:
        c1, c2 = st.columns([2.7, 1.1])
        btn_lbl = "🔼 売買ガイドを閉じる" if is_open else ("🔴 空売り戦略と合議を見る" if r.get("strat", {}).get("side") == "SHORT" else "🔵 買い方ガイドと合議を見る")
        if c1.button(btn_lbl, key=f"btn_open_{uk}", use_container_width=True):
            st.session_state["focused_stock_item"] = r; st.session_state["scroll_top_trig"] = int(time.time() * 1000); st.rerun()
        if c2.button("✅ 監視済" if r["code"] in st.session_state["watchlist"] else "⭐ 監視追加", key=f"btn_watch_{uk}", use_container_width=True):
            if r["code"] in st.session_state["watchlist"]: del st.session_state["watchlist"][r["code"]]
            else: st.session_state["watchlist"][r["code"]] = r
            cu = st.session_state.get("authenticated_user", "")
            if cu: save_watchlist(cu, st.session_state["watchlist"])
            st.rerun()
    if not is_open: return

    side_title = "空売り(SHORT)" if r.get("strat", {}).get("side") == "SHORT" else "順張り買い(LONG)"
    st.markdown(f'<div class="consensus-banner"><div style="font-weight:800;color:#fde047;font-size:13px;margin-bottom:6px;">🏛️ 最終結論 ＆ プロ推奨{side_title}アクションプラン（{r["strat"]["style_name"]}専科）</div>{build_instant_verdict_html(r)}</div>', unsafe_allow_html=True)
    ck = f"{uk}_{r.get('strat', {}).get('style_name', 'default')}"
    if ck not in st.session_state["council_threads"]:
        with st.spinner("🔵 5人の専門ペルソナがリアルタイム合議を生成中..."):
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
            with st.spinner("🔵 5人の専門ペルソナが追加合議を生成中..."):
                deb_u = run_gemini_council(r, None, 0, uq=ut, hist=cur_t)
            for nt in deb_u["dialogue"]: st.session_state["council_threads"][ck].append(nt)
            st.session_state["council_meta"][ck] = deb_u; st.session_state["scroll_target_id"] = nid; st.rerun()

    if auto_open and not st.session_state.get("custom_search_code"):
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("⬅️ 一覧に戻る (他の銘柄を見る)", key=f"btn_back_bottom_{uk}", use_container_width=True, type="primary"):
            st.session_state["focused_stock_item"] = None; st.session_state["scroll_top_trig"] = int(time.time() * 1000); st.rerun()

def render_card(r, is_custom=False, rank=None, kp="card", is_focused=False):
    rel_news = next((n for n in all_impact_news if r["full_code"] in n["detail"]["related_codes"]), None)
    dc, ds, ps = "#10b981" if r["diff"] >= 0 else "#ef4444", ("+" if r["diff"] > 0 else ""), ("+" if r["pts_gap_pct"] > 0 else "")
    rk_h = f'<span class="pill-badge" style="background:#f59e0b;color:#0f172a;border:none;">🏆 #{rank}</span>' if rank else ""
    new_badge = '<span class="pill-badge" style="background:rgba(16,185,129,0.2);border-color:#10b981;color:#6ee7b7;font-weight:800;">🆕 NEW昇格</span>' if r.get("is_new_challenger") else ""
    lot, st_info = r["lot_info"], r["strat"]
    is_short_card = (st_info.get("side") == "SHORT")
    is_jp_t3 = is_jp_tier3_short_restricted(r.get("full_code", ""), r.get("genre", ""))
    is_buy_hold_style = ("バイ＆ホールド" in st_info.get("style_name", ""))
    n_banner = f'<div style="margin-top:6px; margin-bottom:4px;"><span style="display:inline-block; width:100%; text-align:center; background:linear-gradient(90deg, #b91c1c 0%, #ef4444 50%, #b91c1c 100%); color:#ffffff; font-weight:800; font-size:11.5px; padding:5px 8px; border-radius:6px; border:1px solid #fca5a5; animation:alert-pulse 2s infinite;">🚨【重大情報】{html.escape(rel_news["title"][:32] + "..." if len(rel_news["title"]) > 32 else rel_news["title"])}</span></div>' if rel_news else ""

    exec_grade = str(r.get("exec_grade", "🔵 Grade-B: 標準執行（VWAP厳守）"))
    exec_score = int(r.get("exec_score", 3))
    exec_badge_style = "background:rgba(16,185,129,0.22);border-color:#10b981;color:#6ee7b7;font-weight:900;" if exec_score >= 4 else ("background:rgba(56,189,248,0.20);border-color:#38bdf8;color:#7dd3fc;font-weight:800;" if exec_score == 3 else "background:rgba(245,158,11,0.22);border-color:#f59e0b;color:#fde047;font-weight:800;")
    exec_badge_html = f'<span class="pill-badge" style="{exec_badge_style}">{html.escape(exec_grade.split("（")[0])}</span>'

    m10 = r.get("macro_10y", {}); d2y = r.get("daily_2y", {})
    m10_score = int(m10.get("long_10y_score", 50))
    d2y_score = int(d2y.get("daily_trend_score", 50))
    m10_badge_html = f'<span class="pill-badge" style="background:rgba(168,85,247,0.22);border-color:#c084fc;color:#f3e8ff;font-weight:800;">📅 10年大局 {m10_score}点</span>'
    d2y_badge_html = f'<span class="pill-badge" style="background:rgba(14,165,233,0.22);border-color:#38bdf8;color:#e0f2fe;font-weight:800;">📈 日足中期 {d2y_score}点</span>'

    ft = r.get("forward_test", {}); lat = ft.get("latest_result", {}); is_jp = ".T" in r.get("full_code", "")
    tot_p = float(ft.get("total_profit_yen", 0.0))
    tot_p_str = f"{'+' if tot_p >= 0 else ''}{tot_p:,.0f}円" if is_jp else f"{'+' if tot_p >= 0 else ''}${tot_p:,.2f}"
    tot_p_col = "#10b981" if tot_p >= 0 else "#ef4444"
    lat_cat = lat.get("result_category") or ("WIN" if lat.get("is_win") is True else ("LOSE" if lat.get("is_win") is False else "NOTRADE"))
    lat_ret = float(lat.get("return_pct", 0.0))
    lat_ret_str = "未約定" if lat_cat == "NOTRADE" else f"{'+' if lat_ret >= 0 else ''}{lat_ret:.1f}%"
    lat_col = "#10b981" if lat_cat == "WIN" else ("#f87171" if lat_cat == "LOSE" else ("#fde047" if lat_cat == "SCRATCH" else "#94a3b8"))
    w_cnt = int(ft.get("win_count", 0))
    l_cnt = int(ft.get("lose_count", max(0, int(ft.get("total_days", 0)) - w_cnt)))
    sc_cnt = int(ft.get("scratch_count", 0))
    t_days = int(ft.get("total_days", 0))
    nt_cnt = int(ft.get("notrade_count", max(0, len(ft.get("history_rows", [])) - t_days)))
    pf_val = float(ft.get("profit_factor", 0.0))
    pf_str = f"{pf_val:.2f}" if pf_val < 99.0 else "∞"
    ft_bar = f'<div class="forward-verify-bar"><span>📈<b>【直近22営業日 リークフリー検証】</b>直近: <b style="color:{lat_col};">{html.escape(str(lat.get("outcome", "検証待機中")))} ({lat_ret_str})</b></span><span>約定 {t_days}戦(見送り{nt_cnt}日) 実質勝率: <b style="color:#fde047;">{ft.get("actual_win_rate", 0.0):.1f}% ({w_cnt}勝{l_cnt}敗/建値{sc_cnt})</b> ｜ PF: <b style="color:#38bdf8;">{pf_str}</b> ｜ 累計: <b style="color:{tot_p_col};">{tot_p_str}</b></span></div>'
    odd_lot_tag = ' <span style="color:#fde047;font-size:10.5px;font-weight:700;">※単元未満株(S株)換算</span>' if lot.get("is_odd_lot") else ""

    side_badge = '<span class="pill-badge" style="background:rgba(225,29,72,0.25);border-color:#fb7185;color:#fecdd3;font-weight:900;">📉 空売り(SHORT)</span>' if is_short_card else '<span class="pill-badge" style="background:rgba(16,185,129,0.2);border-color:#34d399;color:#a7f3d0;font-weight:900;">📈 買い(LONG)</span>'
    t3_guard_badge = '<span class="pill-badge" style="background:rgba(245,158,11,0.18);border-color:#f59e0b;color:#fde047;font-weight:800;">🛡️ 買い専念モード</span>' if (is_jp_t3 or is_buy_hold_style) else ""
    sizing_label_html = f'<span>📦 <b>推奨ロット: {lot["shares"]:,}株</b>{odd_lot_tag} ({st_info["risk_posture"].split("（")[0]}) ｜ 建玉額 {lot["position_value"]:,.0f}円</span>'

    tp_lbl_card = "🎯 空売り利確目標(買い戻し)" if is_short_card else "🎯 最終利確目標"
    sl_lbl_card = "🛡️ 構造的踏み上げ逆指値" if is_short_card else "🛡️ 構造的初期逆指値(損切)"
    tp_sign_c = "+" if r["tp_pct"] > 0 else ""; sl_sign_c = "+" if r["sl_pct"] > 0 else ""
    gap_box_title = r.get("pts_label_title", "📊 マクロ・需給連動 理論寄付き試算値（※前日終値基準）")

    macro10y_bar = (
        f'<div class="macro10y-box">📅 <b>第1層・過去10年週足大局 ({html.escape(str(m10.get("years_span", "10Y")))}):</b> '
        f'<b style="color:#fde047;">{html.escape(str(m10.get("regime_10y_label", "10年大局中立")))}</b> ｜ '
        f'10年CAGR: <b>{m10.get("cagr_10y", 0.0):+.1f}%</b> ｜ 10年高安位置: <b>{m10.get("pos_10y_pct", 50.0):.0f}%</b> ｜ '
        f'10年岩盤POC: <b style="color:#6ee7b7;">{html.escape(str(m10.get("poc_10y_str", "-")))}</b></div>'
    )

    daily2y_bar = (
        f'<div class="daily2y-box">📈 <b>第2層・日足2年中期トレンド:</b> '
        f'<b style="color:#fde047;">{html.escape(str(d2y.get("regime_1d_label", "日足中立")))}</b> ({html.escape(str(d2y.get("ma_align_label", "MA均衡")))}) ｜ '
        f'MA25乖離: <b>{d2y.get("ma25_dev_pct", 0.0):+.1f}%</b> ｜ 日足MACDヒスト: <b>{d2y.get("macd_hist", 0.0):+.2f}</b> ｜ '
        f'52W位置: <b>{d2y.get("pos_52w_pct", 50.0):.0f}%</b> ｜ 日足ATR14: <b style="color:#6ee7b7;">{html.escape(str(d2y.get("daily_atr14_str", "-")))}</b></div>'
    )

    session_reg = get_tse_session_regime()
    session_line = f'<br>🕒 <b>東証時間帯レジーム [{html.escape(session_reg["label"])}]:</b> {html.escape(session_reg["advice"])}'
    combat_tier_lbl = html.escape(str(r.get("combat_tier", "Tier1: 超大型・機関コア主力"))); combat_cost_val = r.get("combat_cost_pct", 0.08)
    if is_short_card:
        combat_guide_html = f'<div class="combat-guide-box" style="background:rgba(225,29,72,0.1);border-color:rgba(251,113,133,0.35);color:#fecdd3;">⚔️ <b>執行品質＆実戦プロファイル:</b> <b>{html.escape(exec_grade)}</b> ｜ {combat_tier_lbl}（往復実質スリッページ想定: <b>{combat_cost_val:.2f}%</b>＋貸株料反映）{session_line}<br>※空売り（SHORT）推奨銘柄：9:05〜13:30にお使いの証券アプリ（iSPEED等）のリアルタイム5分足VWAP割れ・陰線確定後の次バー始値で信用新規売り発注してください（表示価格は東証呼値丸め済）</div>'
    else:
        t3_extra = "（国内小型グロース・Tier3銘柄またはバイ＆ホールド選択時は空売りを制限し、押し目・反発LONGに一本化しています）" if (is_jp_t3 or is_buy_hold_style) else ""
        combat_guide_html = f'<div class="combat-guide-box">⚔️ <b>執行品質＆実戦プロファイル:</b> <b>{html.escape(exec_grade)}</b> ｜ {combat_tier_lbl}（往復実質スリッページ想定: <b>{combat_cost_val:.2f}%</b>）{t3_extra}{session_line}<br>※VWAP+1.5%超乖離の飛びつきは禁止。9:05〜13:30の間にリアルタイム5分足VWAP・5本EMAへの押し目確認＋前バー高値更新陽線確定の次バー始値で発注してください（表示価格は東証呼値丸め済）</div>'

    disp_name = html.escape(str(r.get("name", r["code"])))
    disp_code = html.escape(str(r["code"]))
    title_block = f'<span style="font-size:16.5px;font-weight:800;color:#f8fafc;white-space:nowrap;">{disp_name}</span> <span style="font-size:11.5px;color:#38bdf8;font-family:\'JetBrains Mono\',monospace;font-weight:700;white-space:nowrap;">[{disp_code}]</span> <span style="font-size:11px;color:#94a3b8;white-space:nowrap;">/ {html.escape(r["genre"])}</span>' if disp_name != disp_code else f'<span style="font-size:16.5px;font-weight:800;color:#f8fafc;white-space:nowrap;">{disp_code}</span> <span style="font-size:11px;color:#94a3b8;white-space:nowrap;">/ {html.escape(r["genre"])}</span>'

    st.markdown(
        f'<div class="{"search-result-card" if is_custom else "rank-card"}">'
        f'<div class="signal-10tier-badge" style="background:{r["tier_bg"]};color:{r["tier_color"]};"><span>{r["tier_label"]}</span><span>🔥 期待度 {r["expect_pct"]}% ｜ {st_info["algo_name"].split("】")[0]}】</span></div>'
        f'<div class="badge-single-line">{rk_h}{side_badge}{exec_badge_html}{m10_badge_html}{d2y_badge_html}{t3_guard_badge}{new_badge}<span class="pill-badge" style="background:rgba(250,204,21,0.18);border-color:#facc15;color:#fde047;font-weight:900;">🔥 期待度 {r["expect_pct"]}%</span><span class="quantum-badge">⚛️ ボラ突破指数 {r["q_score"]}点</span><span class="inst-badge">🏛️ 5分足需給 {r["ms_score"]}点</span></div>'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;"><div style="min-width:0;flex:1;"><div style="display:flex;align-items:baseline;flex-wrap:wrap;gap:4px;">{title_block}</div><div style="font-size:11px;color:#94a3b8;margin-top:3px;word-break:keep-all;">{html.escape(r["theme"])} ｜ 現在値: <b style="color:#f8fafc;">{r["price"]}</b> (<span style="color:{dc};font-weight:700;">{ds}{r["diff"]}%</span> / 対市場RSα: <b style="color:{"#34d399" if r.get("rs_alpha",0)>=0 else "#fb7185"};">{r.get("rs_alpha",0):+.2f}%</b>)</div></div>'
        f'<div style="text-align:right;white-space:nowrap;flex-shrink:0;"><div style="font-size:9px;color:#fde047;font-weight:700;">🔥 期待度 / テク強度</div><div style="white-space:nowrap;margin-top:1px;"><span class="expect-badge">{r["expect_pct"]}%</span><span style="color:#64748b;font-size:12px;margin:0 2px;">/</span><span class="prob-badge">{r["total_win_rate"]}pt</span></div></div></div>'
        f'{n_banner}'
        f'<div class="winrate-bar"><div><div style="font-size:9.5px;color:#fde047;">🔥 総合期待度</div><div style="font-size:12.5px;font-weight:900;color:#fef08a;">{r["expect_pct"]}%</div></div><div><div style="font-size:9.5px;color:#c084fc;">⚛️ WKB統計近似突破率</div><div style="font-size:12.5px;font-weight:800;color:#e9d5ff;">{r["q_tunnel"]}%</div></div><div><div style="font-size:9.5px;color:#6ee7b7;">🏛️ 5分足Kyle近似吸収率</div><div style="font-size:12.5px;font-weight:800;color:#a7f3d0;">{r["kyle_stealth"]}%</div></div><div><div style="font-size:9.5px;color:#94a3b8;">🌅 GU指数 / 陽線強度</div><div style="font-size:12px;font-weight:700;">{r["prob"]}% / {r["intraday_win_rate"]}%</div></div></div>'
        f'<div class="trade-plan-box"><div><div style="font-size:9.5px;color:#94a3b8;">{html.escape(gap_box_title)}</div><div style="font-size:12px;font-weight:700;">{r["pts_est_price"]} ({ps}{r["pts_gap_pct"]}%)</div></div><div style="border-left:1px solid rgba(148,163,184,0.16);border-right:1px solid rgba(148,163,184,0.16);"><div style="font-size:9.5px;color:#10b981;">{tp_lbl_card}</div><div style="font-size:12px;font-weight:800;color:#10b981;">{r["tp_price"]} ({tp_sign_c}{r["tp_pct"]}%)</div></div><div><div style="font-size:9.5px;color:#f87171;">{sl_lbl_card}</div><div style="font-size:12px;font-weight:800;color:#f87171;">{r["sl_price"]} ({sl_sign_c}{r["sl_pct"]}%)</div></div></div>'
        f'<div class="sizing-box">{sizing_label_html}<span>当日VWAP(5分足算出): <b>{r["vwap_price"]}</b></span></div>'
        f'{macro10y_bar}{daily2y_bar}{combat_guide_html}{ft_bar}'
        f'<details class="quant-detail-drawer"><summary>⚛️ 週足10年 × 日足2年 × 5分足60日 3階層MTFアルゴリズム戦略詳細</summary><div style="font-size:11.5px;color:#cbd5e1;margin-top:4px;line-height:1.5;"><b>{st_info["algo_name"]}</b><br>{st_info["core_logic"]}<br>📅 <b>第1層・過去10年週足大局解析:</b> {html.escape(str(m10.get("regime_10y_label", "")))} ｜ 10年スコア={m10_score}点 ｜ 10年CAGR={m10.get("cagr_10y", 0.0):+.1f}% ｜ 10年レンジ位置={m10.get("pos_10y_pct", 50.0):.1f}%（10年安値:{html.escape(str(m10.get("low_10y_str", "-")))} 〜 10年高値:{html.escape(str(m10.get("high_10y_str", "-")))}） ｜ 200週MA乖離={m10.get("ma200w_dev_pct", 0.0):+.1f}% ｜ 10年最大出来高POC={html.escape(str(m10.get("poc_10y_str", "-")))}<br>📈 <b>第2層・日足2年中期トレンド解析:</b> {html.escape(str(d2y.get("regime_1d_label", "")))} ｜ 日足スコア={d2y_score}点 ｜ {html.escape(str(d2y.get("ma_align_label", "")))} ｜ MA5={html.escape(str(d2y.get("ma5_str", "-")))} / MA25={html.escape(str(d2y.get("ma25_str", "-")))}({d2y.get("ma25_dev_pct", 0.0):+.1f}%) / MA75={html.escape(str(d2y.get("ma75_str", "-")))}({d2y.get("ma75_dev_pct", 0.0):+.1f}%) / MA200={html.escape(str(d2y.get("ma200_str", "-")))} ｜ 日足MACD={d2y.get("macd_line", 0.0):+.2f} (Signal={d2y.get("macd_signal", 0.0):+.2f} / Hist={d2y.get("macd_hist", 0.0):+.2f}) ｜ 日足RSI(14)={d2y.get("daily_rsi14", 50.0):.1f}% ｜ 52週位置={d2y.get("pos_52w_pct", 50.0):.1f}% ｜ 本物日足ATR14={html.escape(str(d2y.get("daily_atr14_str", "-")))} (日足YZ Vol={round(d2y.get("daily_yz_vol", 0.3)*100, 1)}%)<br>⚖️ <b>双方向需給優位性比較:</b> <span style="color:#34d399;font-weight:700;">LONG優勢度 = {r.get("bull_edge", 0.0):+.1f}pt</span> vs <span style="color:#fb7185;font-weight:700;">SHORT優勢度 = {r.get("bear_edge", 0.0):+.1f}pt</span> ｜ <b>スタイル適合補正 = {r.get("style_fit_bonus", 0.0):+.1f}pt</b> ｜ <b>対市場RSα = {r.get("rs_alpha", 0.0):+.2f}%</b><br>🚦 <b>3階層MTF執行品質ゲート ({exec_score}/5達成):</b> {html.escape(r.get("exec_detail", ""))}<br>📊 <b>第3層・5分足60日OHLCV実測値:</b> RSI(14)={r.get("rsi", 50)}% ｜ BVC-VPIN近似={r.get("vpin", 0.5)} ｜ 平滑化CLVフローZ={r.get("ofi_z", 0.0)} ｜ DFA Hurst={r.get("hurst", 0.5)} ｜ Kyle-λ近似={r.get("kyle_lambda", 0.0):.2e} ｜ BB拡大初動率={r.get("bb_exp_ratio", 1.0)}x ｜ 出来高スパイク陽線頻度={r.get("vol_spike_bull_pct", 0.0)}% ｜ CVaR(99%)={r.get("cvar95", 2.5)}% ｜ YZ年率Vol={round(r.get('yz_vol', 0.0)*100, 1)}% ｜ 効率性ER={r.get("eff_pct", 50)}% ｜ Payoff={r.get("payoff", 1.0)} (Kelly={r.get("kelly_pct", 0.0)}%) ｜ 🔥 時間帯補正RVOL={r.get("rvol", 1.0)}倍 / 報道{r.get("news_hits", 0)}件</div></details></div>',
        unsafe_allow_html=True
    )
    if rel_news and st.button("🚨【速報】重大ニュースの詳細分析を開く", key=f"nb_{kp}_{r['code']}", use_container_width=True):
        st.session_state["selected_news_item"] = rel_news; st.session_state["navigation_page"] = "NEWS_DETAIL"; st.session_state["scroll_top_trig"] = int(time.time()*1000); st.rerun()
    open_now = bool(is_focused or is_custom)
    render_council_sec(r, f"foc_{r['code']}" if open_now else f"{kp}_{r['code']}", auto_open=open_now)

# 13. 3階層MTFクオンツ・エンジン（週足10年 × 日足2年 × 5分足60日）＆ 完全リークフリー検証エンジン
def _extract_ticker_df(raw_df, code: str, total_codes: int):
    if raw_df is None or raw_df.empty: return None
    if isinstance(raw_df.columns, pd.MultiIndex):
        if code in raw_df.columns.get_level_values(0):
            return raw_df[code]
        if code in raw_df.columns.get_level_values(1):
            return raw_df.xs(code, axis=1, level=1)
        return None
    if total_codes == 1:
        return raw_df
    return raw_df[code] if code in raw_df else None

def _compute_single_10y_metrics(df_w: pd.DataFrame, full_code: str) -> dict:
    is_jp = ".T" in str(full_code)
    default_res = {"cagr_10y": 0.0, "pos_10y_pct": 50.0, "poc_10y_price": 0.0, "poc_10y_str": "-", "low_10y_str": "-", "high_10y_str": "-", "ma200w_dev_pct": 0.0, "ma200w_slope_up": True, "long_10y_score": 50, "regime_10y_label": "📊 10年大局データ標準評価", "poc_relation_note": "データ蓄積中", "years_span": "10Y", "has_data": False}
    if df_w is None or df_w.empty: return default_res
    df = df_w.dropna(subset=["Close", "High", "Low", "Volume"]).copy()
    if len(df) < 8: return default_res
    c = np.asarray(df["Close"].values, dtype=float).reshape(-1)
    h = np.asarray(df["High"].values, dtype=float).reshape(-1)
    l = np.asarray(df["Low"].values, dtype=float).reshape(-1)
    v = np.asarray(df["Volume"].values, dtype=float).reshape(-1)

    curr_px = float(c[-1]); oldest_px = max(float(c[0]), 1e-4)
    years = max(len(c) / 52.0, 0.25)
    years_lbl = f"{years:.1f}Y" if years < 9.5 else "10Y"
    cagr_10y = round(float(np.clip(((curr_px / oldest_px) ** (1.0 / years) - 1.0) * 100.0, -60.0, 180.0)), 1)

    hi_10y = float(np.max(h)); lo_10y = float(np.min(l))
    span_10y = max(hi_10y - lo_10y, 1e-4)
    pos_10y_pct = round(float(np.clip(((curr_px - lo_10y) / span_10y) * 100.0, 0.0, 100.0)), 1)

    bins = np.linspace(lo_10y, hi_10y + 1e-4, 16)
    typ_px = (h + l + c) / 3.0
    bin_idx = np.clip(np.digitize(typ_px, bins) - 1, 0, 14)
    vol_profile = np.bincount(bin_idx, weights=np.maximum(v, 1.0), minlength=15)
    poc_bin = int(np.argmax(vol_profile))
    poc_price_raw = float((bins[poc_bin] + bins[poc_bin + 1]) * 0.5)
    poc_10y_price = round_to_tse_tick(poc_price_raw, full_code, "nearest")

    ma_len = min(200, len(c))
    ma200w = float(np.mean(c[-ma_len:]))
    ma200w_prev = float(np.mean(c[-ma_len - min(12, len(c) - ma_len):-min(12, len(c) - ma_len)])) if len(c) > ma_len + 4 else float(c[0])
    ma200w_dev_pct = round(float(((curr_px - ma200w) / max(ma200w, 1e-4)) * 100.0), 1)
    ma200w_slope_up = bool(ma200w >= ma200w_prev)

    cagr_pts = float(np.clip(cagr_10y * 1.15, -20.0, 28.0))
    pos_pts = 14.0 if pos_10y_pct >= 88.0 else (8.0 if pos_10y_pct >= 65.0 else (10.0 if (pos_10y_pct <= 28.0 and curr_px >= poc_10y_price * 0.96) else 0.0))
    poc_pts = 10.0 if curr_px >= poc_10y_price else -6.0
    ma_pts = (8.0 if ma200w_dev_pct >= 0 else -6.0) + (5.0 if ma200w_slope_up else -4.0)
    long_10y_score = int(np.clip(round(48.0 + cagr_pts + pos_pts + poc_pts + ma_pts), 10, 99))

    if pos_10y_pct >= 90.0 and curr_px >= poc_10y_price:
        regime_10y_label = f"🚀 10年青天井ブレイク態勢 (CAGR {cagr_10y:+.1f}%)"
    elif pos_10y_pct <= 25.0 and ma200w_slope_up:
        regime_10y_label = f"💎 10年長期底値圏・大局バリュー反発域 (CAGR {cagr_10y:+.1f}%)"
    elif curr_px >= poc_10y_price and ma200w_dev_pct >= 0:
        regime_10y_label = f"🏛️ 10年長期上昇・岩盤POC支持トレンド (CAGR {cagr_10y:+.1f}%)"
    elif curr_px < poc_10y_price and ma200w_dev_pct < -5.0:
        regime_10y_label = f"⚠️ 10年長期戻り売り警戒・POC下抜け圏 (CAGR {cagr_10y:+.1f}%)"
    else:
        regime_10y_label = f"⚖️ 10年大局レンジ中立・需給均衡帯 (CAGR {cagr_10y:+.1f}%)"

    poc_diff_pct = ((curr_px - poc_10y_price) / max(poc_10y_price, 1e-4)) * 100.0
    if poc_diff_pct >= 0:
        poc_relation_note = f"現在値は10年最大出来高POCより+{poc_diff_pct:.1f}%上方（岩盤下値支持として機能）"
    else:
        poc_relation_note = f"現在値は10年最大出来高POCより{poc_diff_pct:.1f}%下方（上値しこり抵抗帯として意識）"

    return {
        "cagr_10y": cagr_10y, "pos_10y_pct": pos_10y_pct, "poc_10y_price": poc_10y_price,
        "poc_10y_str": fmt_px(poc_10y_price, is_jp, full_code),
        "low_10y_str": fmt_px(lo_10y, is_jp, full_code),
        "high_10y_str": fmt_px(hi_10y, is_jp, full_code),
        "ma200w_dev_pct": ma200w_dev_pct, "ma200w_slope_up": ma200w_slope_up,
        "long_10y_score": long_10y_score, "regime_10y_label": regime_10y_label,
        "poc_relation_note": poc_relation_note, "years_span": years_lbl, "has_data": True
    }

@st.cache_data(ttl=43200)
def fetch_10y_macro_metrics(codes_tuple: tuple) -> dict:
    codes = [c for c in dict.fromkeys(codes_tuple) if c and c not in DELISTED_OR_INVALID_CODES]
    out = {}
    if not codes: return out
    chunks = [codes[i:i + 20] for i in range(0, len(codes), 20)]
    for ch in chunks:
        raw_ch = None
        try:
            raw_ch = yf.download(ch, period="10y", interval="1wk", auto_adjust=True, group_by="ticker", threads=True, progress=False, timeout=15.0)
        except Exception as e:
            record_system_error("fetch_10y_macro_metrics:chunk", e, f"Chunk size: {len(ch)}")
        for c in ch:
            try:
                df_c = _extract_ticker_df(raw_ch, c, len(ch))
                if df_c is None or df_c.dropna(subset=["Close"]).empty:
                    df_c = yf.Ticker(c).history(period="10y", interval="1wk", auto_adjust=True)
                out[c] = _compute_single_10y_metrics(df_c, c)
            except Exception as e_single:
                record_system_error(f"fetch_10y_macro_metrics:{c}", e_single)
                out[c] = _compute_single_10y_metrics(None, c)
    return out

def _compute_single_daily_metrics(df_d: pd.DataFrame, bench_ret_series: pd.Series, full_code: str) -> dict:
    is_jp = ".T" in str(full_code)
    default_res = {
        "ma5": 0.0, "ma25": 0.0, "ma75": 0.0, "ma200": 0.0,
        "ma5_str": "-", "ma25_str": "-", "ma75_str": "-", "ma200_str": "-",
        "ma5_dev_pct": 0.0, "ma25_dev_pct": 0.0, "ma75_dev_pct": 0.0, "ma200_dev_pct": 0.0,
        "ma25_slope_up": True, "ma75_slope_up": True,
        "bull_po": False, "bear_po": False, "ma_align_label": "MA均衡",
        "macd_line": 0.0, "macd_signal": 0.0, "macd_hist": 0.0, "daily_rsi14": 50.0,
        "pos_52w_pct": 50.0, "is_52w_break": False,
        "daily_atr14": 0.0, "daily_atr14_str": "-", "daily_yz_vol": 0.30,
        "daily_rs_alpha_map": {}, "latest_rs_alpha": 0.0,
        "daily_trend_score": 50, "regime_1d_label": "⚖️ 日足中期レンジ均衡",
        "df_daily_clean": None, "has_data": False
    }
    if df_d is None or df_d.empty: return default_res
    df = df_d.dropna(subset=["Open", "High", "Low", "Close", "Volume"]).copy()
    if len(df) < 15: return default_res

    idx = df.index if isinstance(df.index, pd.DatetimeIndex) else pd.to_datetime(df.index)
    df["_d_str"] = idx.strftime("%Y-%m-%d")
    df = df[~df["_d_str"].duplicated(keep="last")].sort_index()

    o = np.asarray(df["Open"].values, dtype=float).reshape(-1)
    h = np.asarray(df["High"].values, dtype=float).reshape(-1)
    l = np.asarray(df["Low"].values, dtype=float).reshape(-1)
    c = np.asarray(df["Close"].values, dtype=float).reshape(-1)
    curr_px = float(c[-1])

    ma5 = float(np.mean(c[-min(5, len(c)):]))
    ma25 = float(np.mean(c[-min(25, len(c)):]))
    ma75 = float(np.mean(c[-min(75, len(c)):]))
    ma200 = float(np.mean(c[-min(200, len(c)):]))

    ma25_prev5 = float(np.mean(c[-min(30, len(c)):-5])) if len(c) >= 10 else ma25
    ma75_prev5 = float(np.mean(c[-min(80, len(c)):-5])) if len(c) >= 15 else ma75
    ma25_slope_up = bool(ma25 >= ma25_prev5)
    ma75_slope_up = bool(ma75 >= ma75_prev5)

    ma5_dev_pct = round(((curr_px - ma5) / max(ma5, 1e-4)) * 100.0, 2)
    ma25_dev_pct = round(((curr_px - ma25) / max(ma25, 1e-4)) * 100.0, 2)
    ma75_dev_pct = round(((curr_px - ma75) / max(ma75, 1e-4)) * 100.0, 2)
    ma200_dev_pct = round(((curr_px - ma200) / max(ma200, 1e-4)) * 100.0, 2)

    bull_po = bool((curr_px > ma5 > ma25 > ma75) and ma25_slope_up)
    bear_po = bool((curr_px < ma5 < ma25 < ma75) and (not ma25_slope_up))
    if bull_po: ma_align_label = "🔥 強気パーフェクトオーダー(C>5>25>75)"
    elif bear_po: ma_align_label = "❄️ 弱気パーフェクトオーダー(C<5<25<75)"
    elif curr_px >= ma25 and ma25 >= ma75: ma_align_label = "📈 上昇配列(C>MA25>MA75)"
    elif curr_px < ma25 and curr_px < ma75: ma_align_label = "📉 下降配列(MA25・75割れ)"
    else: ma_align_label = "⚖️ MA交錯・転換監視帯"

    c_series = pd.Series(c)
    ema12 = c_series.ewm(span=12, adjust=False).mean()
    ema26 = c_series.ewm(span=26, adjust=False).mean()
    macd_s = ema12 - ema26
    sig_s = macd_s.ewm(span=9, adjust=False).mean()
    hist_s = macd_s - sig_s
    macd_line = round(float(macd_s.iloc[-1]), 3)
    macd_signal = round(float(sig_s.iloc[-1]), 3)
    macd_hist = round(float(hist_s.iloc[-1]), 3)

    diffs = np.diff(c)
    g, ls = np.maximum(diffs, 0.0), np.maximum(-diffs, 0.0)
    if len(diffs) >= 14:
        ag, al = float(np.mean(g[-14:])), float(np.mean(ls[-14:]))
        for i in range(len(diffs) - 14, len(diffs)):
            ag = (ag * 13.0 + float(g[i])) / 14.0
            al = (al * 13.0 + float(ls[i])) / 14.0
        daily_rsi14 = round(float(np.clip(100.0 - (100.0 / (1.0 + ag / max(al, 1e-8))), 5.0, 95.0)), 1)
    else:
        daily_rsi14 = 50.0

    n_52w = min(252, len(c))
    hi_52w = float(np.max(h[-n_52w:]))
    lo_52w = float(np.min(l[-n_52w:]))
    pos_52w_pct = round(float(np.clip(((curr_px - lo_52w) / max(hi_52w - lo_52w, 1e-4)) * 100.0, 0.0, 100.0)), 1)
    is_52w_break = bool(curr_px >= hi_52w * 0.992)

    prev_c = np.roll(c, 1); prev_c[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    n_atr = min(14, len(tr))
    daily_atr14 = max(float(np.mean(tr[-n_atr:])), curr_px * 0.0115)

    n_yz = min(20, len(c) - 1)
    if n_yz >= 3:
        o_sub, h_sub, l_sub, c_sub, c_prev = o[-n_yz:], h[-n_yz:], l[-n_yz:], c[-n_yz:], c[-n_yz - 1:-1]
        log_oc = np.log(np.maximum(o_sub / np.maximum(c_prev, 1e-4), 1e-4))
        log_co = np.log(np.maximum(c_sub / np.maximum(o_sub, 1e-4), 1e-4))
        log_ho = np.log(np.maximum(h_sub / np.maximum(o_sub, 1e-4), 1e-4))
        log_lo = np.log(np.maximum(l_sub / np.maximum(o_sub, 1e-4), 1e-4))
        log_hc = np.log(np.maximum(h_sub / np.maximum(c_sub, 1e-4), 1e-4))
        log_lc = np.log(np.maximum(l_sub / np.maximum(c_sub, 1e-4), 1e-4))
        k_yz = 0.34 / (1.34 + (n_yz + 1.0) / max(n_yz - 1.0, 1.0))
        yz_var = max(float(np.var(log_oc, ddof=1)) + k_yz * float(np.var(log_co, ddof=1)) + (1.0 - k_yz) * float(np.mean(log_ho * log_hc + log_lo * log_lc)), 1e-6)
        daily_yz_vol = round(float(np.clip(np.sqrt(yz_var * 252.0), 0.08, 2.50)), 2)
    else:
        daily_yz_vol = 0.30

    stk_ret_pct = pd.Series(c, index=df["_d_str"]).pct_change().fillna(0.0) * 100.0
    daily_rs_alpha_map = {}
    for d_k, s_r in stk_ret_pct.items():
        b_r = float(bench_ret_series.get(d_k, 0.0)) if (bench_ret_series is not None and d_k in bench_ret_series.index) else 0.0
        daily_rs_alpha_map[str(d_k)] = round(float(s_r) - b_r, 3)
    latest_rs_alpha = float(daily_rs_alpha_map.get(str(df["_d_str"].iloc[-1]), 0.0))

    po_pts = 16.0 if bull_po else (-16.0 if bear_po else (8.0 if (curr_px >= ma25 and ma25_slope_up) else (-7.0 if curr_px < ma25 else 0.0)))
    macd_pts = 8.0 if (macd_hist > 0 and macd_line > 0) else (4.0 if macd_hist > 0 else (-7.0 if (macd_hist < 0 and macd_line < 0) else -3.0))
    w52_pts = 10.0 if pos_52w_pct >= 88.0 else (5.0 if pos_52w_pct >= 65.0 else (-6.0 if pos_52w_pct <= 22.0 else 0.0))
    ma200_pts = 6.0 if ma200_dev_pct >= 0 else -5.0
    rs_pts = float(np.clip(latest_rs_alpha * 1.5, -6.0, 6.0))
    daily_trend_score = int(np.clip(round(50.0 + po_pts + macd_pts + w52_pts + ma200_pts + rs_pts), 10, 99))

    if bull_po and is_52w_break:
        regime_1d_label = "🚀 日足強気PO＋52週高値ブレイク"
    elif bull_po:
        regime_1d_label = "🔥 日足強気パーフェクトオーダー上昇"
    elif bear_po:
        regime_1d_label = "❄️ 日足弱気パーフェクトオーダー下落"
    elif curr_px >= ma25 and macd_hist > 0:
        regime_1d_label = "📈 日足MA25上・MACD好転トレンド"
    elif curr_px < ma25 and curr_px < ma75:
        regime_1d_label = "📉 日足MA25・MA75割れ調整局面"
    else:
        regime_1d_label = "⚖️ 日足中期レンジ・方向感模索"

    df_clean = df[["Open", "High", "Low", "Close", "Volume", "_d_str"]].copy()
    return {
        "ma5": ma5, "ma25": ma25, "ma75": ma75, "ma200": ma200,
        "ma5_str": fmt_px(ma5, is_jp, full_code),
        "ma25_str": fmt_px(ma25, is_jp, full_code),
        "ma75_str": fmt_px(ma75, is_jp, full_code),
        "ma200_str": fmt_px(ma200, is_jp, full_code),
        "ma5_dev_pct": ma5_dev_pct, "ma25_dev_pct": ma25_dev_pct, "ma75_dev_pct": ma75_dev_pct, "ma200_dev_pct": ma200_dev_pct,
        "ma25_slope_up": ma25_slope_up, "ma75_slope_up": ma75_slope_up,
        "bull_po": bull_po, "bear_po": bear_po, "ma_align_label": ma_align_label,
        "macd_line": macd_line, "macd_signal": macd_signal, "macd_hist": macd_hist, "daily_rsi14": daily_rsi14,
        "pos_52w_pct": pos_52w_pct, "is_52w_break": is_52w_break,
        "daily_atr14": daily_atr14, "daily_atr14_str": fmt_px(daily_atr14, is_jp, full_code),
        "daily_yz_vol": daily_yz_vol,
        "daily_rs_alpha_map": daily_rs_alpha_map, "latest_rs_alpha": latest_rs_alpha,
        "daily_trend_score": daily_trend_score, "regime_1d_label": regime_1d_label,
        "df_daily_clean": df_clean, "has_data": True
    }

@st.cache_data(ttl=1800)
def fetch_2y_daily_metrics(codes_tuple: tuple) -> dict:
    codes = [c for c in dict.fromkeys(codes_tuple) if c and c not in DELISTED_OR_INVALID_CODES]
    out = {}
    if not codes: return out
    bench_codes = ["^N225", "^GSPC"]
    all_req = list(dict.fromkeys(codes + bench_codes))
    raw_all = None
    try:
        raw_all = yf.download(all_req, period="2y", interval="1d", auto_adjust=True, group_by="ticker", threads=True, progress=False, timeout=12.0)
    except Exception as e:
        record_system_error("fetch_2y_daily_metrics:batch", e)

    def _build_bench_ret(b_code: str) -> pd.Series:
        try:
            bdf = _extract_ticker_df(raw_all, b_code, len(all_req))
            if bdf is None or bdf.dropna(subset=["Close"]).empty:
                bdf = yf.Ticker(b_code).history(period="2y", interval="1d", auto_adjust=True)
            if bdf is not None and not bdf.empty:
                bdf = bdf.dropna(subset=["Close"]).copy()
                b_idx = bdf.index if isinstance(bdf.index, pd.DatetimeIndex) else pd.to_datetime(bdf.index)
                bdf["_d_str"] = b_idx.strftime("%Y-%m-%d")
                bdf = bdf[~bdf["_d_str"].duplicated(keep="last")].sort_index()
                return pd.Series(bdf["Close"].values.astype(float), index=bdf["_d_str"]).pct_change().fillna(0.0) * 100.0
        except Exception as eb:
            record_system_error(f"fetch_2y_daily_metrics:bench:{b_code}", eb)
        return pd.Series(dtype=float)

    n225_ret = _build_bench_ret("^N225")
    gspc_ret = _build_bench_ret("^GSPC")

    for c in codes:
        try:
            df_c = _extract_ticker_df(raw_all, c, len(all_req))
            if df_c is None or df_c.dropna(subset=["Close"]).empty:
                df_c = yf.Ticker(c).history(period="2y", interval="1d", auto_adjust=True)
            bench_s = n225_ret if ".T" in str(c).upper() else gspc_ret
            out[c] = _compute_single_daily_metrics(df_c, bench_s, c)
        except Exception as e_c:
            record_system_error(f"fetch_2y_daily_metrics:{c}", e_c)
            out[c] = _compute_single_daily_metrics(None, pd.Series(dtype=float), c)
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

    # 高値掴みバグ修正：RSI > 75 かつ 上ヒゲ圧力 > 45 の天井乱高下銘柄に減衰ペナルティを適用
    if rsi_val is None:
        diffs_w = np.diff(c); gw, lw = np.maximum(diffs_w, 0.0), np.maximum(-diffs_w, 0.0)
        if len(diffs_w) >= 14:
            ag_w, al_w = float(np.mean(gw[-14:])), float(np.mean(lw[-14:]))
            rsi_val = float(np.clip(100.0 - (100.0 / (1.0 + ag_w / max(al_w, 1e-8))), 5.0, 95.0))
        else:
            rsi_val = 50.0
    if upper_wick_val is None:
        nw = min(12, len(c))
        o_arr = o[-nw:] if o is not None else np.roll(c, 1)[-nw:]
        hw, lw_arr, cw, vw = h[-nw:], l[-nw:], c[-nw:], np.maximum(v[-nw:], 1.0)
        rng_w = np.maximum(hw - lw_arr, 1e-4)
        upper_wick_val = float(np.clip((np.sum(((hw - np.maximum(o_arr, cw)) / rng_w) * vw) / max(float(np.sum(vw)), 1e-8)) * 100.0, 0.0, 100.0))

    overheat_penalty = 0.0
    if float(rsi_val) > 75.0 and float(upper_wick_val) > 45.0:
        overheat_penalty = min(42.0, (float(rsi_val) - 75.0) * 1.4 + (float(upper_wick_val) - 45.0) * 0.65)
        qt = float(np.clip(qt - overheat_penalty, 5.0, 72.0))

    rets = np.diff(c) / np.maximum(c[:-1], 1e-4); rets_16 = rets[-16:] if len(rets) >= 16 else rets
    if len(rets_16) >= 5:
        hist_counts, _ = np.histogram(rets_16, bins=5); probs = hist_counts / max(float(np.sum(hist_counts)), 1.0); probs_nz = probs[probs > 0]
        h_norm = float(np.clip(float(-np.sum(probs_nz * np.log(probs_nz))) / np.log(5.0), 0.0, 1.0))
        order_pct = (1.0 - h_norm) * 100.0; phase_coh = float(np.abs(np.mean(np.exp(1j * np.angle(np.fft.rfft(rets_16))))) * 100.0)
    else: h_norm, order_pct, phase_coh = 0.5, 50.0, 50.0
    coh = float(np.clip(phase_coh * 0.55 + order_pct * 0.45 - overheat_penalty * 0.4, 5.0, 99.0))
    q_score = int(np.clip(round(qt * 0.65 + coh * 0.35), 5, 99))
    if overheat_penalty > 0:
        q_state = f"⚠️ 天井過熱・上ヒゲ拒絶減衰中 (RSI={rsi_val:.0f}/上ヒゲ={upper_wick_val:.0f})"
    else:
        q_state = "⚛️ WKB統計近似・上値障壁突破フェーズ" if qt >= 80.0 else ("🌊 ボラティリティ位相コヒーレンス干渉" if qt >= 50.0 else "🧱 抵抗帯下・エネルギー蓄積中")
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
    dp = np.diff(c[-21:]) if len(c) >= 21 else np.diff(c); v_20 = v[-len(dp):]
    sv = np.where(dp == 0, 1.0, np.sign(dp)) * v_20
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
                past_cum_vols = []
                for pd_str in u_dates[-7:-1]:
                    p_sub = df[df["_trade_date"] == pd_str]
                    if len(p_sub) >= 1:
                        pv = float(p_sub["Volume"].iloc[:min(k_bars, len(p_sub))].sum())
                        if pv > 0: past_cum_vols.append(pv)
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
    if real_daily_yz_vol is not None and real_daily_yz_vol > 0:
        yz_vol = float(real_daily_yz_vol)
    else:
        yz_vol = 0.30
        if daily_df is not None and len(daily_df) >= 3:
            do, dh, dl, dc = [daily_df[col].values.astype(float) for col in ["Open", "High", "Low", "Close"]]; n_yz = min(14, len(dc) - 1)
            if n_yz >= 2:
                o_sub, h_sub, l_sub, c_sub, c_prev = do[-n_yz:], dh[-n_yz:], dl[-n_yz:], dc[-n_yz:], dc[-n_yz - 1:-1]
                log_oc, log_co = np.log(np.maximum(o_sub / np.maximum(c_prev, 1e-4), 1e-4)), np.log(np.maximum(c_sub / np.maximum(o_sub, 1e-4), 1e-4))
                log_ho, log_lo = np.log(np.maximum(h_sub / np.maximum(o_sub, 1e-4), 1e-4)), np.log(np.maximum(l_sub / np.maximum(o_sub, 1e-4), 1e-4))
                log_hc, log_lc = np.log(np.maximum(h_sub / np.maximum(c_sub, 1e-4), 1e-4)), np.log(np.maximum(l_sub / np.maximum(c_sub, 1e-4), 1e-4))
                k_yz = 0.34 / (1.34 + (n_yz + 1.0) / max(n_yz - 1.0, 1.0))
                yz_var = max(float(np.var(log_oc, ddof=1)) + k_yz * float(np.var(log_co, ddof=1)) + (1.0 - k_yz) * float(np.mean(log_ho * log_hc + log_lo * log_lc)), 1e-6)
                yz_vol = round(float(np.clip(np.sqrt(yz_var * 252.0), 0.08, 2.50)), 2)
    surge_score = int(np.clip(30.0 + min(rvol, 4.0) * 15.0 + min(news_hits, 5) * 4.5 + abs(rets[-1]) * 180.0, 10, 99))
    return {"rsi": round(rsi, 1), "vpin": round(vpin, 2), "cvar95": round(cvar, 2), "yz_vol": yz_vol, "eff_pct": eff_pct, "payoff": payoff, "rvol": rvol, "news_hits": news_hits, "surge_attention_score": surge_score, "bb_exp_ratio": bb_exp_ratio, "vol_spike_bull_pct": vol_spike_bull_pct, "upper_wick_pressure": upper_wick_pressure, "lower_wick_support": lower_wick_support}

def compute_structural_sl_delta(recent_lows: np.ndarray, recent_highs: np.ndarray, ref_px: float, atrv: float, is_short: bool, style_sl_scale: float, sl_prof_mult: float, full_code: str) -> float:
    """直近5本の5分足構造的スイング高安と0.60*ATR14を比較した合理的ストップロス幅を算出"""
    atr_sl = max(atrv * 0.60 * style_sl_scale * sl_prof_mult, ref_px * 0.0065)
    tick = get_tse_tick_step(ref_px, full_code)
    if is_short:
        struct_dist = max(0.0, (float(np.max(recent_highs)) - ref_px) + tick) if len(recent_highs) > 0 else atr_sl
    else:
        struct_dist = max(0.0, (ref_px - float(np.min(recent_lows))) + tick) if len(recent_lows) > 0 else atr_sl
    raw_sl = max(atr_sl, min(struct_dist, ref_px * 0.022))
    return float(np.clip(raw_sl, ref_px * 0.0065, ref_px * 0.022))

def compute_japanese_lot_sizing(cv: float, slv: float, total_capital: float, risk_tolerance_pct: float, is_jp: bool, style_mul: float = 1.0, lot_cap_mult: float = 1.0) -> dict:
    rm = float(total_capital) * (float(risk_tolerance_pct) / 100.0); risk_per_share = max(abs(cv - slv), cv * 0.005)
    raw_shares = int((rm / risk_per_share) * style_mul * lot_cap_mult); max_affordable = int((float(total_capital) * lot_cap_mult) // max(cv, 1e-4))
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

    d_ctx = daily_ctx or {}
    m10 = macro_10y or {}
    poc_10y = float(m10.get("poc_10y_price", 0.0))
    above_10y_poc = bool(poc_10y <= 0.0 or cv <= 0.0 or cv >= poc_10y * 0.995)
    below_10y_poc = bool(poc_10y > 0.0 and cv > 0.0 and cv < poc_10y * 0.990)

    if d_ctx.get("bull_po"):
        bull_edge += 11.0
        if above_10y_poc:
            bull_edge += 7.0
            bear_edge -= 14.0
    elif d_ctx.get("bear_po"):
        bear_edge += 13.0
        if below_10y_poc:
            bear_edge += 7.0
            bull_edge -= 10.0
    else:
        ma25_v = float(d_ctx.get("ma25", 0.0))
        ma75_v = float(d_ctx.get("ma75", 0.0))
        macd_h = float(d_ctx.get("macd_hist", 0.0))
        pos_52w = float(d_ctx.get("pos_52w_pct", 50.0))
        if ma25_v > 0 and cv > 0:
            if cv >= ma25_v and d_ctx.get("ma25_slope_up", True):
                bull_edge += 6.5
            elif cv < ma25_v and (ma75_v <= 0 or cv < ma75_v):
                bear_edge += 8.5
        if macd_h > 0:
            bull_edge += 4.5
        elif macd_h < 0:
            bear_edge += 5.0
        if pos_52w >= 88.0:
            bull_edge += 5.0
        elif pos_52w <= 22.0 and below_10y_poc:
            bear_edge += 4.5

    if m10.get("has_data"):
        if above_10y_poc and m10.get("ma200w_dev_pct", 0.0) >= 0.0:
            bull_edge += 5.0
        elif below_10y_poc and m10.get("ma200w_dev_pct", 0.0) < -3.0:
            bear_edge += 6.0

    if rel_news_title:
        if any(bw in rel_news_title for bw in BEARISH_NEWS_KEYWORDS): bear_edge += 18.0
        elif below_vwap and upper_wick_pressure >= 35.0: bear_edge += 15.0
        else: bull_edge += 15.0; bear_edge -= 20.0
    return round(float(bull_edge), 2), round(float(bear_edge), 2)

def evaluate_execution_quality_gate(is_short: bool, prev_trend_weak: bool, cv: float, vwap_today: float, eff_pct: int, bull_edge: float, bear_edge: float, rvol: float, min_rvol_req: float, upper_wick_pressure: float, lower_wick_support: float, daily_ctx: dict = None, macro_10y: dict = None, macro: dict = None, rs_alpha: float = 0.0) -> tuple:
    d_ctx = daily_ctx or {}; m10 = macro_10y or {}
    ma25_v = float(d_ctx.get("ma25", 0.0)); poc_10y = float(m10.get("poc_10y_price", 0.0))
    daily_bull_ok = (cv >= ma25_v * 0.992) if ma25_v > 0 else (not prev_trend_weak)
    daily_bear_ok = (cv <= ma25_v * 1.005) if ma25_v > 0 else prev_trend_weak
    weekly_bull_ok = (cv >= poc_10y * 0.985) if poc_10y > 0 else True
    weekly_bear_ok = (cv <= poc_10y * 1.02) if poc_10y > 0 else True

    if is_short:
        cond1_mtf = (cv <= vwap_today * 1.001) and (daily_bear_ok or prev_trend_weak) and (weekly_bear_ok or d_ctx.get("bear_po", False))
    else:
        cond1_mtf = (cv >= vwap_today * 0.998) and daily_bull_ok and (weekly_bull_ok or d_ctx.get("bull_po", False))

    cond2_er = (int(eff_pct) >= 28); cond3_spread = (abs(bull_edge - bear_edge) >= 8.0); cond4_rvol = (float(rvol) >= float(min_rvol_req))
    cond5_wick = (float(lower_wick_support) < 45.0) if is_short else (float(upper_wick_pressure) < 45.0)
    raw_exec_score = int(cond1_mtf) + int(cond2_er) + int(cond3_spread) + int(cond4_rvol) + int(cond5_wick)

    # マクロ地合い（指数クラッシュ）リスクオフ・フィルタ
    macro_risk_off = False
    macro_note = ""
    if isinstance(macro, dict):
        nk_d = float(macro.get("nk_fut", {}).get("diff", 0.0))
        sp_d = float(macro.get("sp500", {}).get("diff", 0.0))
        if (nk_d <= -1.2 or sp_d <= -1.2) and float(rs_alpha) < 1.5:
            macro_risk_off = True
            macro_note = f" / ⚠️指数リスクオフ減点(-1: 先物{nk_d:+.1f}%/SP{sp_d:+.1f}%, RSα={rs_alpha:+.1f}%<1.5%)"

    exec_score = max(0, raw_exec_score - (1 if macro_risk_off else 0))
    exec_grade = "🟢 Grade-A: 即時執行適格（3階層MTF全5条件クリア）" if exec_score >= 5 else ("🔵 Grade-B: 標準執行（VWAP・MA25厳守）" if exec_score == 4 else "🟡 Grade-C: 様子見・押し目/戻り待機（厳選フィルタ/MTF注意）")
    wick_tag = f"下ヒゲ支持({lower_wick_support:.0f}<45)={'OK' if cond5_wick else 'NG(底堅い)'}" if is_short else f"上ヒゲ拒絶({upper_wick_pressure:.0f}<45)={'OK' if cond5_wick else 'NG(寄り天警戒)'}"
    return exec_score, exec_grade, f"3階層MTF(10Y/1D/5m)={'OK' if cond1_mtf else 'NG'} / 効率性ER({eff_pct}%)={'OK' if cond2_er else 'NG'} / 優位差({abs(bull_edge-bear_edge):.1f}pt)={'OK' if cond3_spread else 'NG'} / 時間帯RVOL({rvol}x)={'OK' if cond4_rvol else 'NG'} / {wick_tag}{macro_note}"

def determine_tactic_classification(full_code: str, genre: str, ofi_z: float, vpin: float, rsi: float, pgap: float, expect_pct: float, prev_trend_weak: bool, qm: dict, ms: dict, rel_news_title: str = "", style: str = "", upper_wick_pressure: float = 0.0, lower_wick_support: float = 0.0, cv: float = 0.0, vwap_today: float = 0.0, rs_alpha: float = 0.0, daily_ctx: dict = None, macro_10y: dict = None) -> str:
    is_buy_and_hold = ("バイ＆ホールド" in str(style))
    is_jp_t3 = is_jp_tier3_short_restricted(full_code, genre)
    hurst = float(ms.get("hurst", 0.50)); has_vwap = (cv > 0.0 and vwap_today > 0.0); below_vwap = bool(has_vwap and (cv < vwap_today))
    d_ctx = daily_ctx or {}; m10 = macro_10y or {}
    poc_10y = float(m10.get("poc_10y_price", 0.0))
    ma25_v = float(d_ctx.get("ma25", 0.0))
    ma25_slope_up = bool(d_ctx.get("ma25_slope_up", True))

    # 3階層MTFの上位足ゲート（門番）判定
    daily_clear_downtrend = bool(ma25_v > 0 and cv > 0 and (cv < ma25_v) and (not ma25_slope_up))
    strong_daily_weekly_bull = bool(d_ctx.get("bull_po", False) and (poc_10y <= 0.0 or cv <= 0.0 or cv >= poc_10y))

    if not (is_buy_and_hold or is_jp_t3):
        bull_edge, bear_edge = compute_directional_edges(ofi_z, rsi, prev_trend_weak, hurst, upper_wick_pressure, lower_wick_support, rel_news_title=rel_news_title, rs_alpha=rs_alpha, below_vwap=below_vwap, daily_ctx=d_ctx, macro_10y=m10, cv=cv)
        if ((not has_vwap) or (cv < vwap_today)) and ofi_z <= -0.35 and (bear_edge >= bull_edge + 6.0) and bear_edge >= 14.0:
            return "Type-S1"
        # 日足強気PO＋10年POC以上の銘柄では安易な逆張り空売り(Type-S2)を禁止
        if not strong_daily_weekly_bull:
            strong_bandwalk = bool(hurst >= 0.56 and ((not has_vwap) or (cv > vwap_today * 1.002)) and (lower_wick_support > upper_wick_pressure))
            if not strong_bandwalk:
                if rsi >= 66.0 and upper_wick_pressure >= 38.0 and ((ofi_z <= 0.10) or (has_vwap and cv <= vwap_today * 1.003)) and (bear_edge >= bull_edge + 3.0) and bear_edge >= 11.0:
                    return "Type-S2"

    # 上位足（日足）が明確な下降トレンドの銘柄では順張り買い(Type-A/B/D)を禁止し、Type-E（押し目待機・見送り）に制限
    if daily_clear_downtrend:
        return "Type-E"

    is_good_news = bool(rel_news_title) and not any(bw in rel_news_title for bw in BEARISH_NEWS_KEYWORDS) and not (below_vwap and upper_wick_pressure >= 35.0)
    if is_good_news or ofi_z >= 0.55 or strong_daily_weekly_bull: return "Type-A"
    if pgap >= 0.8 or rsi >= 60.0 or d_ctx.get("is_52w_break", False): return "Type-B"
    if ms.get("kyle_stealth", 0) >= 56.0 or hurst >= 0.53: return "Type-C"
    if qm.get("q_tunnel", 0) >= 60.0: return "Type-D"
    return "Type-E"

def select_dynamic_strategy(code: str, style: str, ofi_z: float, vpin: float, cvar95: float, rsi: float, lot_info: dict, pest_str: str, vwap_str: str, tp_str: str, sl_str: str, qm: dict, ms: dict, name: str = "", theme: str = "", rel_news_title: str = "", pgap: float = 0.0, expect_pct: float = 50.0, prev_trend_weak: bool = False, full_code: str = "", genre: str = "", upper_wick_pressure: float = 0.0, lower_wick_support: float = 0.0, cv: float = 0.0, vwap_today: float = 0.0, rs_alpha: float = 0.0, macro_10y: dict = None, daily_2y: dict = None) -> dict:
    pfx = style.split(" ")[1] if " " in style else "デイトレード"
    sh = int(lot_info["shares"]); odd_note = "（※単元未満株・S株換算）" if lot_info.get("is_odd_lot") else ""
    disp_name = name or code; part_sh = max(1, int(round(sh * 0.50))); rem_sh = max(0, sh - part_sh)
    dur_map = {"スキャルピング": ("9:05〜13:30 確定後次バー始値約定 → 当日完結", f"<b>🚀 {html.escape(disp_name)} スキャルピング実戦講座</b>"), "スイングトレード": ("9:05〜13:30 確定後次バー始値約定 → 最大5営業日保有", f"<b>📈 {html.escape(disp_name)} スイングトレード実戦講座</b>"), "バイ＆ホールド": ("9:05〜13:30 確定後次バー始値約定 → 最大10営業日保有", f"<b>💎 {html.escape(disp_name)} ポジション運用実戦講座</b>")}
    dur_str, beg_intro = dur_map.get(pfx, ("9:05〜13:30 確定後次バー始値約定 → 13:30保護・14:30手仕舞い", f"<b>🔰 {html.escape(disp_name)} デイトレード実戦講座</b>"))

    m10 = macro_10y or {}; d2y = daily_2y or {}
    m10_lbl = str(m10.get("regime_10y_label", "10年大局中立"))
    m10_poc_s = str(m10.get("poc_10y_str", "-"))
    m10_cagr = float(m10.get("cagr_10y", 0.0))
    d2y_lbl = str(d2y.get("regime_1d_label", "日足中立"))
    d2y_ma = str(d2y.get("ma_align_label", "MA均衡"))
    d2y_ma25_s = str(d2y.get("ma25_str", "-"))
    mtf_clause = f"週足10年『{html.escape(m10_lbl)}』（POC {html.escape(m10_poc_s)}）× 日足2年『{html.escape(d2y_lbl)}』（{html.escape(d2y_ma)} / MA25={html.escape(d2y_ma25_s)}）の3階層MTF構造下で、"

    fc_eval = full_code or (f"{code}.T" if re.match(r"^[0-9]{3}[0-9A-Z]$", str(code)) else str(code))
    tactic_type = determine_tactic_classification(fc_eval, genre, ofi_z, vpin, rsi, pgap, expect_pct, prev_trend_weak, qm, ms, rel_news_title=rel_news_title, style=style, upper_wick_pressure=upper_wick_pressure, lower_wick_support=lower_wick_support, cv=cv, vwap_today=vwap_today, rs_alpha=rs_alpha, daily_ctx=d2y, macro_10y=m10)
    is_jp_t3 = is_jp_tier3_short_restricted(fc_eval, genre); is_buy_and_hold = ("バイ＆ホールド" in str(style))

    if tactic_type == "Type-S2":
        short_dur = "9:05〜13:30 確定後次バー始値空売り → 最大2営業日(貸株コスト管理)" if pfx == "スイングトレード" else "9:05〜13:30 確定後次バー始値空売り → 当日完結"
        return {
            "style_name": pfx, "side": "SHORT", "tactic_type": "Type-S2", "entry_mode": "【空売り】過熱・上値拒絶VWAP割れ次バー始値＋50%利確",
            "algo_name": f"🟣 [{pfx} / Type-S2 空売り] 過熱・上ヒゲ拒絶フェード(WRV={upper_wick_pressure:.1f})・VWAP割れ次バー始値空売り ＋ +1.0R 50%分割買い戻し型",
            "risk_posture": f"📉 空売り一括 <b>{sh:,}株</b> → +1.0Rで50%(<b>{part_sh:,}株</b>)利確＋次バー以降建値ロック{odd_note}",
            "core_logic": f"{mtf_clause}【{html.escape(disp_name)}】は高値圏での上ヒゲ拒絶圧力（WRV={upper_wick_pressure:.1f} / RSI {rsi}%）を検知。当日VWAP（{vwap_str}）または5本EMA割れの陰線確定後、次バー始値で空売りエントリーし、日足MA25（{html.escape(d2y_ma25_s)}）・10年POC（{html.escape(m10_poc_s)}）方向への反落幅を収益化します。",
            "adj_shares": sh, "trade_duration": short_dur,
            "step_plan": f"① 【3階層MTF×次バー始値空売り約定】週足10年({html.escape(m10_lbl)})×日足({html.escape(d2y_lbl)})を背に、9:05〜13:30に<b>{vwap_str}</b>または5本EMA割れの陰線確定後、次バー始値で<b>{sh:,}株</b>を空売り（構造的逆指値<b>{sl_str}</b>）。<br>② 【+1.0R 50%買い戻し＋次バー以降建値ロック】初期リスク比1:1(+1.0R)到達で<b>{part_sh:,}株</b>を買い戻し利確、次バー以降に残り<b>{rem_sh:,}株</b>の逆指値を建値以下へロックして目標<b>{tp_str}</b>へ。",
            "beginner_html": f"{beg_intro}<br><b>📉【今回の戦術：週足×日足の抵抗帯×5分足天井拒絶からの『空売り（SHORT）』】</b><br>・<b>3階層根拠：</b> {html.escape(m10_lbl)} × {html.escape(d2y_lbl)}（MA25: <b>{html.escape(d2y_ma25_s)}</b>）<br>・<b>売り方：</b> 9:05〜13:30に<b>{vwap_str}</b>を割り込んで陰線が確定した次の足始値で<b>{sh:,}株</b>を信用新規売り（逆指値<b>{sl_str}</b>）。<br>・<b>買い戻し利確：</b> 損切り幅と同じ利益(+1.0R)が出たら<b>{part_sh:,}株</b>を買い戻し、次バー以降建値ロックで下落目標<b>{tp_str}</b>を狙います。"
        }
    elif tactic_type == "Type-S1":
        short_dur = "9:05〜13:30 確定後次バー始値空売り → 最大2営業日(貸株コスト管理)" if pfx == "スイングトレード" else "9:05〜13:30 確定後次バー始値空売り → 当日完結"
        return {
            "style_name": pfx, "side": "SHORT", "tactic_type": "Type-S1", "entry_mode": "【空売り】VWAP割れ陰線確定次バー始値＋50%利確",
            "algo_name": f"🔴 [{pfx} / Type-S1 空売り] 3階層弱気一致・VWAP下陰線確定次バー始値空売り ＋ +1.0R 50%分割買い戻し型",
            "risk_posture": f"📉 空売り一括 <b>{sh:,}株</b> → +1.0Rで50%(<b>{part_sh:,}株</b>)利確＋次バー以降建値ロック{odd_note}",
            "core_logic": f"{mtf_clause}【{html.escape(disp_name)}】は大口資金流出（CLV Z={ofi_z} / RSα={rs_alpha:+.2f}%）とトレンド持続性（Hurst={ms.get('hurst', 0.5)}）を検知。当日VWAP（{vwap_str}）下での陰線確定後、次バー始値で順張り空売り（SHORT）を仕掛けます。",
            "adj_shares": sh, "trade_duration": short_dur,
            "step_plan": f"① 【3階層MTF×順張り次バー始値空売り】週足({html.escape(m10_lbl)})×日足({html.escape(d2y_lbl)})確認後、9:05〜13:30に<b>{vwap_str}</b>以下で陰線確定後、次バー始値で<b>{sh:,}株</b>を一括空売り（構造的逆指値<b>{sl_str}</b>）。<br>② 【+1.0R 50%買い戻し＋次バー以降建値ロック】+1.0R到達で<b>{part_sh:,}株</b>を買い戻し利確、次バー以降に残り<b>{rem_sh:,}株</b>の逆指値を建値以下へ引き下げて下落目標<b>{tp_str}</b>を追撃。",
            "beginner_html": f"{beg_intro}<br><b>📉【今回の戦術：週足×日足の弱気構造×5分足資金流出に順張りする『空売り（SHORT）』】</b><br>・<b>3階層根拠：</b> {html.escape(m10_lbl)} × {html.escape(d2y_lbl)}（MA25: <b>{html.escape(d2y_ma25_s)}</b>）<br>・<b>売り方：</b> 9:05〜13:30に<b>{vwap_str}</b>より下で陰線が確定した次の足始値で<b>{sh:,}株</b>を信用新規売り（逆指値<b>{sl_str}</b>）。<br>・<b>買い戻し利確：</b> +1.0R到達で50%（<b>{part_sh:,}株</b>）を買い戻し、次バー以降建値ロックで最終下落目標<b>{tp_str}</b>を狙います。"
        }
    elif tactic_type == "Type-A":
        entry_mode = "【買い】押し目確認＋高値更新次バー始値＋50%利確"
        algo_name = f"🚨 [{pfx} / Type-A 買い] 3階層MTF追風×VWAP押し目・高値更新次バー始値買い ＋ +1.0R 50%分割利確型"
        core_logic = f"{mtf_clause}【{html.escape(disp_name)}】の強い資金流入(Z={ofi_z} / RSα={rs_alpha:+.2f}% / 下ヒゲ支持={lower_wick_support:.1f})を検知。VWAP+1.5%超の飛びつきを排除し、VWAP・5本EMA付近への押し目確認後に前バー高値を上抜く陽線確定の次バー始値で一括買い約定します。"
    elif tactic_type == "Type-B":
        entry_mode = "【買い】押し目反発＋高値更新次バー始値＋50%利確"
        algo_name = f"⚡ [{pfx} / Type-B 買い] 日足上昇トレンド×VWAP押し目反発次バー始値買い ＋ +1.0R 50%分割利確型"
        core_logic = f"{mtf_clause}【{html.escape(disp_name)}】は順張り好調圏（ギャップ {pgap:+.2f}% / RSI {rsi}%）。VWAP+1.5%超の過熱追いを避け、VWAP・5本EMAの+0.6%以内への押し目確認後に前バー高値を上抜く陽線確定の次バー始値で一括買い約定します。"
    elif tactic_type == "Type-C":
        t3_note = "（※国内小型Tier3またはバイ＆ホールド選択のため空売りを抑止・押し目サポート反発待機へ自動切替）" if (is_jp_t3 or is_buy_and_hold) else ""
        entry_mode = "【買い】VWAPサポート次バー始値＋50%利確"
        algo_name = f"🏛️ [{pfx} / Type-C 買い] 10年岩盤POC・日足MA支持×5分足ステルス集積次バー始値買い ＋ +1.0R 50%分割利確型"
        core_logic = f"{mtf_clause}【{html.escape(disp_name)}】に下値吸収・集積近似（吸収率={ms['kyle_stealth']}% / 下ヒゲ支持={lower_wick_support:.1f}）を検出。9:05〜13:30にVWAPサポートまたは5本EMA上の陽線確定後、次バー始値で一括買い約定します。{t3_note}"
    elif tactic_type == "Type-D":
        entry_mode = "【買い】ORB朝イチ高値ブレイク逆指値＋50%利確"
        algo_name = f"⚛️ [{pfx} / Type-D 買い] 52週・10年高値圏ブレイク×WKB突破ORB買い ＋ +1.0R 50%分割利確型"
        core_logic = f"{mtf_clause}【{html.escape(disp_name)}】のWKB突破率({qm['q_tunnel']}%)が上昇。VWAP+1.5%超乖離を排除しつつ、9:05〜13:30の朝イチ高値突破逆指値または押し目高値更新次バー始値で一括買い約定します。"
    else:
        t3_note = "（※日足下降トレンド門番または国内小型Tier3保護により順張り追いを抑止・押し目待機）" if (is_jp_t3 or is_buy_and_hold or (d2y.get("ma25", 0) > 0 and cv < d2y.get("ma25", 0))) else ""
        entry_mode = "【買い】安値切り上げ・VWAP上確定次バー始値＋50%利確"
        algo_name = f"🛡️ [{pfx} / Type-E 買い] 3階層岩盤支持×安値切り上げVWAP確定次バー始値買い ＋ +1.0R 50%分割利確型"
        core_logic = f"{mtf_clause}【{html.escape(disp_name)}】は押し目・反発待機局面。9:05〜13:30に安値切り上げかつVWAP（{vwap_str}）維持の陽線確定後、次バー始値で一括買い約定します。{t3_note}"

    return {
        "style_name": pfx, "side": "LONG", "tactic_type": tactic_type, "entry_mode": entry_mode, "algo_name": algo_name,
        "risk_posture": f"🚀 現物/信用買い一括 <b>{sh:,}株</b> → +1.0Rで50%(<b>{part_sh:,}株</b>)利確＋次バー以降建値ロック{odd_note}",
        "core_logic": core_logic, "adj_shares": sh, "trade_duration": dur_str,
        "step_plan": f"① 【3階層MTF×プルバック確定次バー始値買い】週足10年({html.escape(m10_lbl)} / POC: <b>{html.escape(m10_poc_s)}</b>)×日足({html.escape(d2y_lbl)} / MA25: <b>{html.escape(d2y_ma25_s)}</b>)を背に、VWAP+1.5%超の飛びつきを避け<b>{vwap_str}</b>・5本EMA付近への押し目確認＋前バー高値更新陽線確定の次バー始値で<b>{sh:,}株</b>{odd_note}を一括買い（構造的逆指値<b>{sl_str}</b>）。<br>② 【+1.0R 50%利確＋次バー以降建値ロック】+1.0R到達で<b>{part_sh:,}株</b>を利確、次バー以降に残り<b>{rem_sh:,}株</b>を建値ロックして<b>{tp_str}</b>へ。",
        "beginner_html": f"{beg_intro}<br><b>📈【今回の戦術：週足10年×日足2年の上昇トレンド×5分足押し目反発に乗る『順張り買い（LONG）』】</b><br>・<b>3階層MTF根拠：</b> {html.escape(m10_lbl)}（CAGR <b>{m10_cagr:+.1f}%</b>）× {html.escape(d2y_lbl)}（MA25: <b>{html.escape(d2y_ma25_s)}</b>）<br>・<b>買い方：</b> 高値飛びつきを避け、<b>{vwap_str}</b>付近の押し目確認後に前バー高値を上抜く陽線確定の次の足始値で<b>{sh:,}株</b>{odd_note}を一括買い（逆指値<b>{sl_str}</b>）。<br>・<b>利確：</b> 損切り幅と同額(+1.0R)伸びたら<b>{part_sh:,}株</b>を利確し、次バー以降建値ロックで目標<b>{tp_str}</b>を狙います。"
    }

def _is_market_open_now(is_jp: bool) -> bool:
    now_dt = datetime.now()
    if is_jp:
        if now_dt.weekday() >= 5: return False
        mins = now_dt.hour * 60 + now_dt.minute
        return (9 * 60) <= mins <= (15 * 60 + 30)
    else:
        now_utc = datetime.now(timezone.utc)
        if now_utc.weekday() >= 5: return False
        utc_mins = now_utc.hour * 60 + now_utc.minute
        return (13 * 60 + 30) <= utc_mins <= (21 * 60)

def _build_historical_daily_slice_ctx(df_daily_clean: pd.DataFrame, prev_d: str, fallback_close: float, full_code: str = "") -> dict:
    """検証日 prev_d 以前のデータのみから日足指標・過去POC・長期高安位置をリークなしで厳格算出する"""
    default_ctx = {
        "ma25": fallback_close, "ma75": fallback_close, "ma200": fallback_close,
        "ma25_slope_up": True, "bull_po": False, "bear_po": False,
        "macd_hist": 0.0, "pos_52w_pct": 50.0, "daily_atr14": fallback_close * 0.015,
        "prev_trend_weak": False, "poc_10y_price": 0.0, "pos_10y_pct": 50.0,
        "ma200w_dev_pct": 0.0, "has_data": False
    }
    if df_daily_clean is None or df_daily_clean.empty:
        return default_ctx
    sub = df_daily_clean[df_daily_clean["_d_str"] <= prev_d]
    if sub.empty:
        return default_ctx
    h = np.asarray(sub["High"].values, dtype=float).reshape(-1)
    l = np.asarray(sub["Low"].values, dtype=float).reshape(-1)
    c = np.asarray(sub["Close"].values, dtype=float).reshape(-1)
    v = np.asarray(sub["Volume"].values, dtype=float).reshape(-1) if "Volume" in sub.columns else np.ones_like(c)
    px = float(c[-1])
    ma5 = float(np.mean(c[-min(5, len(c)):]))
    ma25 = float(np.mean(c[-min(25, len(c)):]))
    ma75 = float(np.mean(c[-min(75, len(c)):]))
    ma200 = float(np.mean(c[-min(200, len(c)):]))
    ma25_prev5 = float(np.mean(c[-min(30, len(c)):-5])) if len(c) >= 10 else ma25
    ma25_slope_up = bool(ma25 >= ma25_prev5)
    bull_po = bool((px > ma5 > ma25 > ma75) and ma25_slope_up)
    bear_po = bool((px < ma5 < ma25 < ma75) and (not ma25_slope_up))
    c_s = pd.Series(c)
    macd_s = c_s.ewm(span=12, adjust=False).mean() - c_s.ewm(span=26, adjust=False).mean()
    macd_hist = float((macd_s - macd_s.ewm(span=9, adjust=False).mean()).iloc[-1])
    n_52w = min(252, len(c))
    hi_52w = float(np.max(h[-n_52w:])); lo_52w = float(np.min(l[-n_52w:]))
    pos_52w_pct = float(np.clip(((px - lo_52w) / max(hi_52w - lo_52w, 1e-4)) * 100.0, 0.0, 100.0))
    prev_c = np.roll(c, 1); prev_c[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    daily_atr14 = max(float(np.mean(tr[-min(14, len(tr)):])), px * 0.0115)
    prev_trend_weak = bool(px < ma25 * 0.992) if len(c) >= 5 else False

    # prev_d 時点までの日足全期間（最大2年）からリークなしの過去出来高POC・高安位置・200日MA乖離を計算
    hi_hist = float(np.max(h)); lo_hist = float(np.min(l))
    span_hist = max(hi_hist - lo_hist, 1e-4)
    pos_hist_pct = float(np.clip(((px - lo_hist) / span_hist) * 100.0, 0.0, 100.0))
    bins = np.linspace(lo_hist, hi_hist + 1e-4, 16)
    typ_px = (h + l + c) / 3.0
    bin_idx = np.clip(np.digitize(typ_px, bins) - 1, 0, 14)
    vol_profile = np.bincount(bin_idx, weights=np.maximum(v, 1.0), minlength=15)
    poc_bin = int(np.argmax(vol_profile))
    poc_raw = float((bins[poc_bin] + bins[poc_bin + 1]) * 0.5)
    poc_hist_price = round_to_tse_tick(poc_raw, full_code, "nearest") if full_code else poc_raw
    ma200_dev_pct = float(((px - ma200) / max(ma200, 1e-4)) * 100.0)

    return {
        "ma25": ma25, "ma75": ma75, "ma200": ma200,
        "ma25_slope_up": ma25_slope_up, "bull_po": bull_po, "bear_po": bear_po,
        "macd_hist": macd_hist, "pos_52w_pct": pos_52w_pct, "daily_atr14": daily_atr14,
        "prev_trend_weak": prev_trend_weak,
        "poc_10y_price": poc_hist_price, "pos_10y_pct": pos_hist_pct,
        "ma200w_dev_pct": ma200_dev_pct, "has_data": True
    }

def record_and_verify_daily_Forward_test(df: pd.DataFrame, full_code: str, strat: dict, pest: float, vwap20: float, tpv: float, slv: float, shares: int, style: str, total_capital: float = 1000000.0, risk_tolerance_pct: float = 2.0, shared_ledger: dict = None, save_db: bool = True, genre: str = "", daily_2y: dict = None, macro_10y: dict = None, active_boosts: tuple = ("core_inst", "core_mom", "core_vol")) -> dict:
    is_jp = ".T" in full_code; now_dt = datetime.now(); today_str = now_dt.strftime("%Y-%m-%d"); today_utc_str = datetime.now(timezone.utc).strftime("%Y-%m-%d"); is_market_open = _is_market_open_now(is_jp)
    combat_prof = get_ticker_combat_profile(full_code, genre)
    BASE_COST_RATE, tp_prof_mult, sl_prof_mult, max_gu_limit = float(combat_prof["cost_rate"]), float(combat_prof["tp_mult"]), float(combat_prof["sl_mult"]), float(combat_prof["max_gu_limit"])
    is_tier3_small = is_jp_tier3_short_restricted(full_code, genre, combat_prof)
    st_p = style.split(" ")[1] if " " in style else "デイトレード"
    max_hold_days = {"スキャルピング": 1, "デイトレード": 1, "スイングトレード": 5, "バイ＆ホールド": 10}.get(st_p, 1)
    tactic_type = strat.get("tactic_type", "Type-E"); entry_mode = strat.get("entry_mode", "確定後次バー始値一括約定")
    plan_entry_price = round_to_tse_tick(float(vwap20 if tactic_type != "Type-D" else pest), full_code, "nearest")

    d2y = daily_2y or {}
    df_daily_clean = d2y.get("df_daily_clean")
    daily_rs_alpha_map = d2y.get("daily_rs_alpha_map", {})

    boosts_key = "_".join(sorted([str(b) for b in (active_boosts or ())]))
    ledger_key = f"{full_code}__{st_p}__{boosts_key}"
    ledger = shared_ledger if shared_ledger is not None else db_get("daily_forward_ledger", {})
    if not isinstance(ledger, dict): ledger = {}
    with _DB_LOCK:
        existing_sl = ledger.get(ledger_key)
        stock_ledger = {"signals": dict(existing_sl.get("signals", {})), "verified": dict(existing_sl.get("verified", {})), "algo_ver": existing_sl.get("algo_ver", "")} if isinstance(existing_sl, dict) else {"signals": {}, "verified": {}, "algo_ver": ""}

    ALGO_VERSION_TAG = "QWM21_STRICT_NEXTBAR_LEAKFREE"
    if stock_ledger.get("algo_ver") != ALGO_VERSION_TAG:
        stock_ledger["verified"], stock_ledger["algo_ver"] = {}, ALGO_VERSION_TAG

    unique_dates = sorted(df["_trade_date"].unique().tolist()) if df is not None and not df.empty else []
    latest_trade_date = unique_dates[-1] if unique_dates else today_str
    unconf_dates = {today_str, today_utc_str, latest_trade_date} if is_market_open else set()
    if unconf_dates:
        for k_v, v_rec in list(stock_ledger["verified"].items()):
            if k_v in unconf_dates or v_rec.get("exit_date", k_v) in unconf_dates: del stock_ledger["verified"][k_v]

    stock_ledger["signals"][today_str] = {"date": today_str, "entry_type": entry_mode, "tactic_type": tactic_type, "plan_entry_price": round(plan_entry_price, 4), "tp_val": round(float(tpv), 4), "sl_val": round(float(slv), 4), "style": style}
    style_tp_scale, style_sl_scale = {"スキャルピング": (0.80, 0.80), "スイングトレード": (1.25, 1.15), "バイ＆ホールド": (1.40, 1.25)}.get(st_p, (1.00, 1.00))
    PARTIAL_RATIO, REMAINING_RATIO, BASE_LOT = 0.50, 0.50, (100 if is_jp else 1)
    TACTIC_MODE_LABELS = {"Type-S2": "【空売り】過熱・WRV拒絶VWAP割れ", "Type-S1": "【空売り】資金流出VWAP割れ", "Type-A": "【買い】押し目+高値更新次バー始値", "Type-B": "【買い】押し目反発+高値更新始値", "Type-C": "【買い】VWAPサポート次バー始値", "Type-D": "【買い】ORB高値ブレイク", "Type-E": "【買い】安値切上VWAP次バー始値"}

    try:
        if len(unique_dates) >= 2:
            start_idx = max(0, len(unique_dates) - 35)
            for idx_prev in range(start_idx, len(unique_dates) - 1):
                try:
                    prev_d, entry_d = unique_dates[idx_prev], unique_dates[idx_prev + 1]
                    if entry_d in stock_ledger["verified"] or entry_d in unconf_dates: continue
                    prev_bars, entry_day_bars = df[df["_trade_date"] == prev_d], df[df["_trade_date"] == entry_d]
                    if prev_bars.empty or entry_day_bars.empty: continue

                    hist_until_prev = df[df["_trade_date"] <= prev_d]; p_close = float(prev_bars["Close"].iloc[-1]); p_vol = prev_bars["Volume"].values.astype(float)
                    p_typ = (prev_bars["High"].values + prev_bars["Low"].values + prev_bars["Close"].values) / 3.0
                    p_vwap = float(np.sum(p_typ * p_vol) / np.sum(p_vol)) if np.sum(p_vol) > 0 else p_close

                    hist_daily_5m = hist_until_prev.groupby("_trade_date").agg(Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"), Close=("Close", "last"), Volume=("Volume", "sum")).sort_index()
                    # 完全リークフリー: prev_d 以前のみから算出した日足・過去POC・高安位置・200日MA乖離を使用
                    hist_daily_ctx = _build_historical_daily_slice_ctx(df_daily_clean, prev_d, p_close, full_code=full_code)
                    hist_macro_slice = {
                        "poc_10y_price": hist_daily_ctx["poc_10y_price"],
                        "pos_10y_pct": hist_daily_ctx["pos_10y_pct"],
                        "ma200w_dev_pct": hist_daily_ctx["ma200w_dev_pct"],
                        "has_data": hist_daily_ctx["has_data"]
                    }
                    poc_hist_p = float(hist_daily_ctx["poc_10y_price"])
                    pos_hist_p = float(hist_daily_ctx["pos_10y_pct"])
                    p_atr = float(hist_daily_ctx["daily_atr14"])
                    rs_alpha_p = float(daily_rs_alpha_map.get(prev_d, 0.0))
                    is_prev_trend_weak = bool(hist_daily_ctx["prev_trend_weak"])

                    hc, ho, hh, hl, hv = [hist_until_prev[col].values.astype(float) for col in ["Close", "Open", "High", "Low", "Volume"]]
                    ofi_p = compute_smoothed_clv_z(hc, hh, hl, hv, day_bars_count=len(prev_bars))
                    qa_p = compute_advanced_quant_indicators(hc, ho, hh, hl, hv, daily_df=hist_daily_5m, df=hist_until_prev) if len(hc) >= 20 else {"rsi": 50.0, "vpin": 0.50, "eff_pct": 50, "surge_attention_score": 50, "rvol": 1.0, "upper_wick_pressure": 0.0, "lower_wick_support": 0.0}
                    qm_p = compute_quantum_wave_metrics(hc, hh, hl, hv, o=ho, rsi_val=qa_p.get("rsi", 50.0), upper_wick_val=qa_p.get("upper_wick_pressure", 0.0)) if len(hc) >= 20 else {"q_tunnel": 50.0, "q_score": 50}
                    ms_p = compute_inst_microstructure(hc, hh, hl, hv) if len(hc) >= 20 else {"kyle_stealth": 50.0, "hurst": 0.50, "ms_score": 50}

                    r20_p = int(np.sum(np.diff(hc[-21:]) > 0)) if len(hc) >= 21 else 10
                    base_tech_p = float(np.clip((r20_p / 20.0) * 100.0 * 0.65 + (qa_p.get("eff_pct", 50) * 0.35), 10.0, 95.0))
                    inst_flow_p = float(np.clip(50.0 + ofi_p * 14.0 + (0.5 - qa_p.get("vpin", 0.50)) * 35.0, 10.0, 98.0))
                    tot_win_p = float(np.clip((base_tech_p + qm_p.get("q_score", 50) * 0.85 + ms_p.get("ms_score", 50) * 0.80 + inst_flow_p * 0.75 + qa_p.get("surge_attention_score", 50) * 0.65) / 4.05, 5.0, 97.8))
                    expect_pct_p = float(np.clip(tot_win_p * 0.85 + ofi_p * 3.8 + 6.0, 5.0, 99.5))
                    pgap_p = round(float(np.clip(ofi_p * 0.65, -2.5, 3.8)), 2); pest_p = round_to_tse_tick(p_close * (1.0 + pgap_p / 100.0), full_code, "nearest")
                    rsi_p, vpin_p = float(qa_p.get("rsi", 50.0)), float(qa_p.get("vpin", 0.50))
                    u_wick_p, l_wick_p = float(qa_p.get("upper_wick_pressure", 0.0)), float(qa_p.get("lower_wick_support", 0.0))

                    sig_tactic = determine_tactic_classification(full_code, genre, ofi_p, vpin_p, rsi_p, pgap_p, expect_pct_p, is_prev_trend_weak, qm_p, ms_p, rel_news_title="", style=style, upper_wick_pressure=u_wick_p, lower_wick_support=l_wick_p, cv=p_close, vwap_today=p_vwap, rs_alpha=rs_alpha_p, daily_ctx=hist_daily_ctx, macro_10y=hist_macro_slice)
                    sig_mode = TACTIC_MODE_LABELS.get(sig_tactic, "【買い】安値切上VWAP次バー始値")
                    sig_plan_px = pest_p if sig_tactic == "Type-D" else round_to_tse_tick(p_vwap, full_code, "nearest")
                    is_short_sig = sig_tactic in ("Type-S1", "Type-S2")
                    bull_ep, bear_ep = compute_directional_edges(ofi_p, rsi_p, is_prev_trend_weak, float(ms_p.get("hurst", 0.50)), u_wick_p, l_wick_p, rel_news_title="", rs_alpha=rs_alpha_p, below_vwap=(p_close < p_vwap), daily_ctx=hist_daily_ctx, macro_10y=hist_macro_slice, cv=p_close)
                    exec_score_p, _, _ = evaluate_execution_quality_gate(is_short_sig, is_prev_trend_weak, p_close, p_vwap, int(qa_p.get("eff_pct", 50)), bull_ep, bear_ep, float(qa_p.get("rvol", 1.0)), float(combat_prof["min_rvol_req"]), u_wick_p, l_wick_p, daily_ctx=hist_daily_ctx, macro_10y=hist_macro_slice, rs_alpha=rs_alpha_p)
                    eff_max_hold = (1 if is_tier3_small else (2 if st_p == "スイングトレード" else 1)) if is_short_sig else max_hold_days

                    def _calc_structural_tp_sl(entry_px: float, is_short: bool, rec_lows: np.ndarray, rec_highs: np.ndarray) -> tuple:
                        sl_d = compute_structural_sl_delta(rec_lows, rec_highs, entry_px, p_atr, is_short, style_sl_scale, sl_prof_mult, full_code)
                        rr_mult = 2.0 * tp_prof_mult
                        tp_d = float(np.clip(sl_d * rr_mult, sl_d * 1.80, max(entry_px * 0.048, sl_d * 2.25)))
                        if not is_short:
                            if pos_hist_p >= 90.0 and (poc_hist_p <= 0 or entry_px >= poc_hist_p):
                                tp_d *= 1.10
                            elif poc_hist_p > entry_px and (poc_hist_p - entry_px) < tp_d:
                                tp_d = max((poc_hist_p - entry_px) * 0.94, sl_d * 1.35)
                            ma25_h = float(hist_daily_ctx.get("ma25", 0.0))
                            if ma25_h > entry_px and (ma25_h - entry_px) < tp_d * 0.85:
                                tp_d = max((ma25_h - entry_px) * 0.95, sl_d * 1.35)
                        else:
                            for sup_lv in (float(hist_daily_ctx.get("ma25", 0.0)), float(hist_daily_ctx.get("ma75", 0.0)), poc_hist_p):
                                if 0 < sup_lv < entry_px and (entry_px - sup_lv) < tp_d * 0.85:
                                    tp_d = max((entry_px - sup_lv) * 0.95, sl_d * 1.35)
                        if is_short:
                            tp_px = round_to_tse_tick(max(entry_px - tp_d, entry_px * 0.5), full_code, "floor")
                            sl_px = round_to_tse_tick(entry_px + sl_d, full_code, "ceil")
                            return (tp_px, sl_px, max(entry_px - tp_px, entry_px * 0.005), max(sl_px - entry_px, entry_px * 0.004))
                        else:
                            tp_px = round_to_tse_tick(entry_px + tp_d, full_code, "ceil")
                            sl_px = round_to_tse_tick(max(entry_px - sl_d, entry_px * 0.5), full_code, "floor")
                            return (tp_px, sl_px, max(tp_px - entry_px, entry_px * 0.005), max(entry_px - sl_px, entry_px * 0.004))

                    hold_slice_dates = unique_dates[idx_prev + 1 : idx_prev + 1 + eff_max_hold]
                    span_bars = df[df["_trade_date"].isin(hold_slice_dates)].copy()
                    if span_bars.empty: continue

                    n_bo, n_bh, n_bl, n_bc = [span_bars[col].values.astype(float) for col in ["Open", "High", "Low", "Close"]]
                    n_bv, n_dates = span_bars["Volume"].values.astype(float), span_bars["_trade_date"].values; total_span_bars = len(n_bo)
                    day1_bars_count = int(np.sum(n_dates == entry_d))
                    day1_bo, day1_bh, day1_bl, day1_bc = n_bo[:day1_bars_count], n_bh[:day1_bars_count], n_bl[:day1_bars_count], n_bc[:day1_bars_count]
                    morning_high = round_to_tse_tick(float(np.max(day1_bh[:min(2, day1_bars_count)])) if day1_bars_count > 0 else p_close, full_code, "ceil")
                    morning_low = round_to_tse_tick(float(np.min(day1_bl[:min(2, day1_bars_count)])) if day1_bars_count > 0 else p_close, full_code, "floor")
                    day_open_px = float(day1_bo[0]) if day1_bars_count > 0 else p_close
                    open_gap_pct = ((day_open_px - p_close) / max(p_close, 1e-4)) * 100.0

                    entered, avg_entry_px, first_entry_bar = False, 0.0, -1
                    pending_entry_side = ""
                    pending_entry_lows, pending_entry_highs = np.array([]), np.array([])
                    pending_exit_reason = ""
                    half_tp_done, half_tp_px, half_tp_bar_idx = False, 0.0, -1
                    pending_be_sl = None
                    eff_tp, eff_sl, tp_delta, sl_delta = 0.0, 0.0, 0.0, 0.0
                    pullback_touched = False
                    outcome, exit_px, result_category, realized_ret_rate = "", 0.0, "NOTRADE", 0.0
                    exit_date_actual, hold_days_actual = entry_d, 1

                    final_window_date = hold_slice_dates[-1]; final_day_indices = np.where(n_dates == final_window_date)[0]
                    final_day_start = int(final_day_indices[0]) if len(final_day_indices) > 0 else 0; final_day_len = len(final_day_indices)
                    cur_day_str, cum_pv, cum_v, day_bar_idx = "", 0.0, 0.0, 0
                    ema5 = float(n_bc[0]) if total_span_bars > 0 else p_close; alpha_ema5 = 2.0 / (5.0 + 1.0)

                    for b_i in range(total_span_bars):
                        b_date = str(n_dates[b_i])
                        if b_date != cur_day_str: cur_day_str, cum_pv, cum_v, day_bar_idx = b_date, 0.0, 0.0, 0
                        else: day_bar_idx += 1
                        bo, bh, bl, bc, bv = float(n_bo[b_i]), float(n_bh[b_i]), float(n_bl[b_i]), float(n_bc[b_i]), float(n_bv[b_i])
                        prev_vwap_for_entry = (cum_pv / cum_v) if cum_v > 0 else p_vwap
                        cum_pv += ((bh + bl + bc) / 3.0) * max(bv, 1.0); cum_v += max(bv, 1.0); curr_vwap = cum_pv / cum_v
                        ema5 = bc if b_i == 0 else (bc * alpha_ema5 + ema5 * (1.0 - alpha_ema5))

                        is_first_day = (b_date == entry_d)
                        is_final_day = (b_date == final_window_date); final_rel_idx = b_i - final_day_start if is_final_day else -1
                        is_afternoon_protect = is_final_day and (final_rel_idx >= int(final_day_len * 0.65))
                        is_late_session = is_final_day and (final_rel_idx >= int(final_day_len * 0.80))

                        def _finalize_split_exit(rem_exit_px: float, curr_h_days: int) -> tuple:
                            rem_clean = round_to_tse_tick(rem_exit_px, full_code, "nearest")
                            trip_cost = BASE_COST_RATE + (((0.0006 if is_tier3_small else 0.0) + 0.0002 * max(1, curr_h_days)) if is_short_sig else 0.0)
                            if is_short_sig:
                                if half_tp_done:
                                    return (PARTIAL_RATIO * (((avg_entry_px - half_tp_px) / max(avg_entry_px, 1e-4)) - trip_cost) + REMAINING_RATIO * (((avg_entry_px - rem_clean) / max(avg_entry_px, 1e-4)) - trip_cost)), (PARTIAL_RATIO * half_tp_px + REMAINING_RATIO * rem_clean)
                                return (((avg_entry_px - rem_clean) / max(avg_entry_px, 1e-4)) - trip_cost), rem_clean
                            else:
                                if half_tp_done:
                                    return (PARTIAL_RATIO * (((half_tp_px - avg_entry_px) / max(avg_entry_px, 1e-4)) - trip_cost) + REMAINING_RATIO * (((rem_clean - avg_entry_px) / max(avg_entry_px, 1e-4)) - trip_cost)), (PARTIAL_RATIO * half_tp_px + REMAINING_RATIO * rem_clean)
                                return (((rem_clean - avg_entry_px) / max(avg_entry_px, 1e-4)) - trip_cost), rem_clean

                        def _classify_r_outcome(net_ret_rate: float, entry_p: float, risk_d: float, side_lbl: str, day_lbl: str, win_desc: str, lose_desc: str) -> tuple:
                            risk_rate = max(risk_d / max(entry_p, 1e-4), 0.003)
                            r_multiple = net_ret_rate / risk_rate
                            if r_multiple >= 0.15:
                                return f"⭕ {side_lbl}{win_desc} (+{r_multiple:.2f}R){day_lbl} (WIN)", "WIN"
                            elif r_multiple <= -0.15:
                                return f"🛡️ {side_lbl}{lose_desc} ({r_multiple:.2f}R){day_lbl} (LOSE)", "LOSE"
                            else:
                                return f"⚖️ {side_lbl}建値撤退 ({r_multiple:+.2f}R){day_lbl} (SCRATCH)", "SCRATCH"

                        # 1. 前バーで確定した「次バー始値約定（Next-Bar Open + 不利1ティック）」を実行
                        if (not entered) and pending_entry_side and is_first_day:
                            is_long_dir = (pending_entry_side == "LONG")
                            avg_entry_px = apply_unfavorable_tick_slip(bo, full_code, is_long_entry_or_short_exit=is_long_dir)
                            entered, first_entry_bar = True, b_i
                            eff_tp, eff_sl, tp_delta, sl_delta = _calc_structural_tp_sl(avg_entry_px, not is_long_dir, pending_entry_lows, pending_entry_highs)
                            pending_entry_side = ""

                        # 2. 前バー以前で成立した建値ロック（次バー以降から有効）を適用
                        if entered and (pending_be_sl is not None) and (b_i > half_tp_bar_idx):
                            if is_short_sig:
                                eff_sl = min(eff_sl, pending_be_sl)
                            else:
                                eff_sl = max(eff_sl, pending_be_sl)
                            pending_be_sl = None

                        # 3. 建玉保有中の監視・決済処理
                        if entered:
                            curr_hold_days = hold_slice_dates.index(b_date) + 1 if b_date in hold_slice_dates else 1
                            day_tag = f" [{curr_hold_days}日保有]" if eff_max_hold > 1 else ""; side_tag = "[空売り]" if is_short_sig else "[買い]"
                            trip_cost_cur = BASE_COST_RATE + (((0.0006 if is_tier3_small else 0.0) + 0.0002 * curr_hold_days) if is_short_sig else 0.0)

                            # 前バーで確定した「モメンタム失速撤退／時間軸決済」を当バー始値＋不利1ティックで執行
                            if pending_exit_reason and b_i > first_entry_bar:
                                exit_date_actual, hold_days_actual = b_date, curr_hold_days
                                exec_out_px = apply_unfavorable_tick_slip(bo, full_code, is_long_entry_or_short_exit=is_short_sig)
                                realized_ret_rate, exit_px = _finalize_split_exit(exec_out_px, curr_hold_days)
                                if pending_exit_reason == "STALL":
                                    outcome, result_category = _classify_r_outcome(realized_ret_rate, avg_entry_px, sl_delta, side_tag, day_tag, "失速早期利確撤退", "モメンタム失速早期撤退")
                                else:
                                    outcome, result_category = _classify_r_outcome(realized_ret_rate, avg_entry_px, sl_delta, side_tag, day_tag, "時間軸プラス手仕舞い", "時間軸手仕舞い")
                                break

                            active_sl_this_bar = eff_sl
                            bars_held = b_i - first_entry_bar
                            # 部分利確（50%）のトリガーは初期リスク幅と1:1の +1.0R
                            half_target_span = sl_delta

                            if is_short_sig:
                                half_trigger_px = round_to_tse_tick(avg_entry_px - half_target_span, full_code, "floor")
                                # 約定当バーは始値boで約定済みのため、高値bh・安値blの逆指値/指値判定を実行（始値ギャップ貫通は次バー以降）
                                if (b_i > first_entry_bar) and (bo >= active_sl_this_bar):
                                    exit_date_actual, hold_days_actual = b_date, curr_hold_days
                                    sl_fill = apply_unfavorable_tick_slip(max(bo, active_sl_this_bar), full_code, is_long_entry_or_short_exit=True)
                                    realized_ret_rate, exit_px = _finalize_split_exit(sl_fill, curr_hold_days)
                                    outcome, result_category = _classify_r_outcome(realized_ret_rate, avg_entry_px, sl_delta, side_tag, day_tag, "50%利確後建値ロック完遂", "逆指値損切(窓開け貫通含)")
                                    break
                                if bh >= active_sl_this_bar:
                                    exit_date_actual, hold_days_actual = b_date, curr_hold_days
                                    sl_fill = apply_unfavorable_tick_slip(active_sl_this_bar, full_code, is_long_entry_or_short_exit=True)
                                    realized_ret_rate, exit_px = _finalize_split_exit(sl_fill, curr_hold_days)
                                    outcome, result_category = _classify_r_outcome(realized_ret_rate, avg_entry_px, sl_delta, side_tag, day_tag, "50%利確後建値ロック完遂", "構造的逆指値損切")
                                    break
                                elif bl <= eff_tp:
                                    exit_date_actual, hold_days_actual = b_date, curr_hold_days
                                    tp_fill = min(bo, eff_tp) if (b_i > first_entry_bar and bo <= eff_tp) else eff_tp
                                    realized_ret_rate, exit_px = _finalize_split_exit(tp_fill, curr_hold_days)
                                    outcome, result_category = _classify_r_outcome(realized_ret_rate, avg_entry_px, sl_delta, side_tag, day_tag, "下落目標到達・買い戻し完遂", "目標決済")
                                    break

                                # 同一バー内でSLに抵触せず +1.0R に到達した場合のみ50%利確し、建値ロックは「次バー以降」から適用
                                if (not half_tp_done) and (bl <= half_trigger_px):
                                    half_tp_done = True
                                    half_tp_px = min(bo, half_trigger_px) if (b_i > first_entry_bar and bo <= half_trigger_px) else half_trigger_px
                                    half_tp_bar_idx = b_i
                                    pending_be_sl = round_to_tse_tick(avg_entry_px * (1.0 - trip_cost_cur - 0.0005), full_code, "floor")

                                # 失速・時間軸決済は終値検知 → 次バー始値で執行
                                if (not half_tp_done) and (bars_held >= 6) and (bc > avg_entry_px * 0.9985) and (bc > curr_vwap) and (bc > ema5):
                                    pending_exit_reason = "STALL"
                                elif is_late_session and bc <= avg_entry_px * (1.0 - trip_cost_cur - 0.0020):
                                    pending_exit_reason = "TIME"
                                elif is_afternoon_protect and bc <= avg_entry_px * (1.0 - trip_cost_cur - 0.0015):
                                    pending_be_sl = min(pending_be_sl if pending_be_sl is not None else eff_sl, round_to_tse_tick(avg_entry_px * (1.0 - trip_cost_cur - 0.0005), full_code, "floor"))
                            else:
                                half_trigger_px = round_to_tse_tick(avg_entry_px + half_target_span, full_code, "ceil")
                                if (b_i > first_entry_bar) and (bo <= active_sl_this_bar):
                                    exit_date_actual, hold_days_actual = b_date, curr_hold_days
                                    sl_fill = apply_unfavorable_tick_slip(min(bo, active_sl_this_bar), full_code, is_long_entry_or_short_exit=False)
                                    realized_ret_rate, exit_px = _finalize_split_exit(sl_fill, curr_hold_days)
                                    outcome, result_category = _classify_r_outcome(realized_ret_rate, avg_entry_px, sl_delta, side_tag, day_tag, "50%利確後建値ロック完遂", "逆指値損切(窓開け貫通含)")
                                    break
                                if bl <= active_sl_this_bar:
                                    exit_date_actual, hold_days_actual = b_date, curr_hold_days
                                    sl_fill = apply_unfavorable_tick_slip(active_sl_this_bar, full_code, is_long_entry_or_short_exit=False)
                                    realized_ret_rate, exit_px = _finalize_split_exit(sl_fill, curr_hold_days)
                                    outcome, result_category = _classify_r_outcome(realized_ret_rate, avg_entry_px, sl_delta, side_tag, day_tag, "50%利確後建値ロック完遂", "構造的逆指値損切")
                                    break
                                elif bh >= eff_tp:
                                    exit_date_actual, hold_days_actual = b_date, curr_hold_days
                                    tp_fill = max(bo, eff_tp) if (b_i > first_entry_bar and bo >= eff_tp) else eff_tp
                                    realized_ret_rate, exit_px = _finalize_split_exit(tp_fill, curr_hold_days)
                                    outcome, result_category = _classify_r_outcome(realized_ret_rate, avg_entry_px, sl_delta, side_tag, day_tag, "50%分割＋最終目標到達", "目標決済")
                                    break

                                # 同一バー内でSLに抵触せず +1.0R に到達した場合のみ50%利確し、建値ロックは「次バー以降」から適用
                                if (not half_tp_done) and (bh >= half_trigger_px):
                                    half_tp_done = True
                                    half_tp_px = max(bo, half_trigger_px) if (b_i > first_entry_bar and bo >= half_trigger_px) else half_trigger_px
                                    half_tp_bar_idx = b_i
                                    pending_be_sl = round_to_tse_tick(avg_entry_px * (1.0 + trip_cost_cur + 0.0005), full_code, "ceil")

                                # 失速・時間軸決済は終値検知 → 次バー始値で執行
                                if (not half_tp_done) and (bars_held >= 6) and (bc < avg_entry_px * 1.0015) and (bc < curr_vwap) and (bc < ema5):
                                    pending_exit_reason = "STALL"
                                elif is_late_session and bc >= avg_entry_px * (1.0 + trip_cost_cur + 0.0020):
                                    pending_exit_reason = "TIME"
                                elif is_afternoon_protect and bc >= avg_entry_px * (1.0 + trip_cost_cur + 0.0015):
                                    pending_be_sl = max(pending_be_sl if pending_be_sl is not None else eff_sl, round_to_tse_tick(avg_entry_px * (1.0 + trip_cost_cur + 0.0005), full_code, "ceil"))

                        # 4. 未約定時のエントリーシグナル判定（最終バー手前まで。成立したら次バー始値で執行）
                        can_signal = is_first_day and (not entered) and (not pending_entry_side) and (exec_score_p >= 4) and (1 <= day_bar_idx <= max(7, int(day1_bars_count * 0.72))) and (b_i + 1 < total_span_bars) and (str(n_dates[b_i + 1]) == entry_d)
                        if can_signal:
                            prev_close_bar = float(n_bc[b_i - 1]) if day_bar_idx >= 1 else bo
                            prev_high_bar = float(n_bh[b_i - 1]) if day_bar_idx >= 1 else bh
                            rec_start = max(0, b_i - 4)
                            rec_lows = n_bl[rec_start:b_i + 1]
                            rec_highs = n_bh[rec_start:b_i + 1]

                            if is_short_sig:
                                if ((bc <= curr_vwap * 1.001 or bc <= ema5) and bc <= bo) or (day_bar_idx >= 2 and bl <= morning_low and bc < prev_close_bar):
                                    pending_entry_side = "SHORT"
                                    pending_entry_lows, pending_entry_highs = rec_lows, rec_highs
                            else:
                                # 高値ジャンピングキャッチ禁止（VWAPから +1.5% または 0.45*p_atr 以上乖離した過熱バーでは新規LONG禁止）
                                vwap_dev_ratio = (bc - curr_vwap) / max(curr_vwap, 1e-4)
                                vwap_dev_abs = bc - curr_vwap
                                not_overheated_vwap = bool((vwap_dev_ratio <= 0.015) and (vwap_dev_abs <= 0.45 * p_atr))

                                high_gap_ok = True
                                if open_gap_pct > 1.8:
                                    body_len = bc - bo; upper_w_len = bh - bc
                                    high_gap_ok = bool((day_bar_idx >= 2) and (bl >= float(n_bl[b_i - 1]) * 0.999) and (body_len > 0.0) and (upper_w_len <= body_len * 0.6))

                                if not_overheated_vwap and high_gap_ok:
                                    # 押し目（VWAPまたは5本EMAの +0.6% 以内、または直近3本の安値切り上げ）を確認
                                    near_vwap_or_ema = bool((bl <= curr_vwap * 1.006) or (bl <= ema5 * 1.006) or (bc <= curr_vwap * 1.006) or (bc <= ema5 * 1.006))
                                    higher_lows_3 = bool(day_bar_idx >= 2 and (n_bl[b_i] >= n_bl[b_i - 1] >= n_bl[b_i - 2]))
                                    if near_vwap_or_ema or higher_lows_3:
                                        pullback_touched = True

                                    # 前バー高値を上抜く確定陽線（bc > bo かつ bc > n_bh[b_i - 1]）
                                    bull_break_prev_high = bool((bc > bo) and (bc > prev_high_bar))

                                    if sig_tactic in ("Type-A", "Type-B"):
                                        if pullback_touched and bull_break_prev_high and (bc >= curr_vwap * 0.997 or bc >= ema5 * 0.997):
                                            pending_entry_side = "LONG"
                                            pending_entry_lows, pending_entry_highs = rec_lows, rec_highs
                                    elif sig_tactic == "Type-C":
                                        if day_bar_idx >= 1 and pullback_touched and (bc > bo) and (bc >= curr_vwap * 0.997 or bc >= ema5):
                                            pending_entry_side = "LONG"
                                            pending_entry_lows, pending_entry_highs = rec_lows, rec_highs
                                    elif sig_tactic == "Type-D":
                                        if day_bar_idx >= 2:
                                            prev_above_vwap = bool(prev_close_bar >= prev_vwap_for_entry * 0.997)
                                            if prev_above_vwap and (bc >= morning_high) and (bc > bo) and open_gap_pct <= max_gu_limit:
                                                pending_entry_side = "LONG"
                                                pending_entry_lows, pending_entry_highs = rec_lows, rec_highs
                                            elif pullback_touched and bull_break_prev_high:
                                                pending_entry_side = "LONG"
                                                pending_entry_lows, pending_entry_highs = rec_lows, rec_highs
                                    else:
                                        if day_bar_idx >= 1 and higher_lows_3 and (bc > bo) and (bc >= curr_vwap * 0.998):
                                            pending_entry_side = "LONG"
                                            pending_entry_lows, pending_entry_highs = rec_lows, rec_highs

                    if not entered:
                        no_trade_reason = "⚪ 執行ゲートGrade-C・見送り (NO TRADE)" if exec_score_p < 4 else "⚪ 押し目/ブレイク条件未到達・見送り (NO TRADE)"
                        outcome, avg_entry_px, exit_px, result_category, ret_pct, base_100_profit = no_trade_reason, sig_plan_px, sig_plan_px, "NOTRADE", 0.0, 0.0
                    else:
                        if outcome == "":
                            if (len(hold_slice_dates) < eff_max_hold) or (final_window_date in unconf_dates): continue
                            exit_date_actual, hold_days_actual = final_window_date, len(hold_slice_dates)
                            day_tag = f" [{hold_days_actual}日保有]" if eff_max_hold > 1 else ""; side_tag = "[空売り]" if is_short_sig else "[買い]"
                            close_fill = apply_unfavorable_tick_slip(float(n_bc[-1]), full_code, is_long_entry_or_short_exit=is_short_sig)
                            realized_ret_rate, exit_px = _finalize_split_exit(close_fill, hold_days_actual)
                            outcome, result_category = _classify_r_outcome(realized_ret_rate, avg_entry_px, sl_delta, side_tag, day_tag, "最終大引け利確決済", "最終大引け損切決済")
                        ret_pct, base_100_profit = realized_ret_rate * 100.0, (avg_entry_px * BASE_LOT) * realized_ret_rate

                    is_win_bool = True if result_category == "WIN" else (False if result_category == "LOSE" else None)
                    stock_ledger["verified"][entry_d] = {"date": exit_date_actual, "entry_date": entry_d, "exit_date": exit_date_actual, "hold_days": hold_days_actual, "signal_date": prev_d, "plan_short": f"{sig_tactic}({sig_mode[:10]})", "entry_price": round(avg_entry_px, 4), "exit_price": round(exit_px, 4), "entry_str": fmt_px(avg_entry_px, is_jp, full_code) if result_category != "NOTRADE" else f"待機 {fmt_px(sig_plan_px, is_jp, full_code)}", "exit_str": fmt_px(exit_px, is_jp, full_code) if result_category != "NOTRADE" else "未約定", "outcome": outcome, "result_category": result_category, "is_win": is_win_bool, "return_pct": round(ret_pct, 2), "base_100_profit": round(base_100_profit, 2)}
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
    total_days = len(traded_rows)
    notrade_count = len(all_verified) - total_days
    win_count = sum(1 for x in traded_rows if x.get("result_category") == "WIN")
    lose_count = sum(1 for x in traded_rows if x.get("result_category") == "LOSE")
    scratch_count = sum(1 for x in traded_rows if x.get("result_category") == "SCRATCH")
    decisive_trades = win_count + lose_count
    actual_win_rate = round((win_count / decisive_trades) * 100.0, 1) if decisive_trades > 0 else 0.0

    gross_profit = sum(float(x.get("profit_val", 0.0)) for x in traded_rows if float(x.get("profit_val", 0.0)) > 0.0)
    gross_loss = abs(sum(float(x.get("profit_val", 0.0)) for x in traded_rows if float(x.get("profit_val", 0.0)) < 0.0))
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0.0 else (99.9 if gross_profit > 0.0 else 0.0)
    total_profit_yen = round(sum(float(x.get("profit_val", 0.0)) for x in traded_rows), 2)

    latest_result = traded_rows[0] if traded_rows else (all_verified[0] if all_verified else {"date": today_str, "plan_short": f"{tactic_type}({entry_mode[:10]})", "entry_str": fmt_px(plan_entry_price, is_jp, full_code), "exit_str": "-", "outcome": "⏳ 保有中・確定決済待機", "result_category": "NOTRADE", "is_win": None, "return_pct": 0.0, "profit_val": 0.0, "hold_days": 1})
    return {"win_count": win_count, "lose_count": lose_count, "scratch_count": scratch_count, "total_days": total_days, "notrade_count": notrade_count, "actual_win_rate": actual_win_rate, "profit_factor": profit_factor, "total_profit_yen": total_profit_yen, "latest_result": latest_result, "history_rows": all_verified}

def analyze_df(df_raw, code, name, theme, genre, macro, buzz_map, style, core_vol=True, core_inst=True, core_mom=True, total_capital=1000000, risk_tolerance_pct=2.0, shared_ledger=None, save_db=True, macro_10y_map=None, daily_2y_map=None):
    try:
        df = normalize_ohlcv_df(df_raw, min_rows=25)
        if df is None: return None

        daily_df_5m = df.groupby("_trade_date").agg(Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"), Close=("Close", "last"), Volume=("Volume", "sum")).sort_index()
        c, o, h, l, v = [np.asarray(df[col].values, dtype=float).reshape(-1) for col in ["Close", "Open", "High", "Low", "Volume"]]
        cv = float(c[-1]); prev_day_close = float(daily_df_5m["Close"].iloc[-2]) if len(daily_df_5m) >= 2 else float(o[0])
        day_ret = float((cv - prev_day_close) / max(prev_day_close, 1e-4) * 100.0)

        macro_10y = (macro_10y_map or {}).get(code) or _compute_single_10y_metrics(None, code)
        daily_2y = (daily_2y_map or {}).get(code) or _compute_single_daily_metrics(None, pd.Series(dtype=float), code)

        # 本物の日足2年データから算出したATR14とYZボラティリティを優先採用
        if daily_2y.get("has_data") and float(daily_2y.get("daily_atr14", 0.0)) > 0:
            atrv = max(float(daily_2y["daily_atr14"]), cv * 0.0115)
        elif len(daily_df_5m) >= 3:
            dh, dl, dc = [daily_df_5m[col].values.astype(float) for col in ["High", "Low", "Close"]]
            d_prev_c = np.roll(dc, 1); d_prev_c[0] = dc[0]
            atrv = max(float(np.mean(np.maximum(dh - dl, np.maximum(np.abs(dh - d_prev_c), np.abs(dl - d_prev_c)))[-14:])), cv * 0.0115)
        else:
            prev_c = np.roll(c, 1); prev_c[0] = c[0]
            atrv = max(float(np.mean(np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))[-14:])) * 1.8, cv * 0.0115)

        today_bars = df[df["_trade_date"] == df["_trade_date"].iloc[-1]]
        th, tl, tc, tv = [today_bars[col].values.astype(float) for col in ["High", "Low", "Close", "Volume"]]
        vwap_today = float(np.sum(((th + tl + tc) / 3.0) * tv) / np.sum(tv)) if np.sum(tv) > 0 else cv

        news_hits = int((buzz_map or {}).get(code, {}).get("news_hits", 0))
        q_adv = compute_advanced_quant_indicators(c, o, h, l, v, daily_df=daily_df_5m, news_hits=news_hits, df=df, real_daily_yz_vol=(float(daily_2y["daily_yz_vol"]) if daily_2y.get("has_data") else None))
        qm = compute_quantum_wave_metrics(c, h, l, v, o=o, rsi_val=q_adv["rsi"], upper_wick_val=q_adv["upper_wick_pressure"])
        ms = compute_inst_microstructure(c, h, l, v)

        long_10y_score = float(macro_10y.get("long_10y_score", 50))
        cagr_10y = float(macro_10y.get("cagr_10y", 0.0))
        pos_10y_pct = float(macro_10y.get("pos_10y_pct", 50.0))
        poc_10y_price = float(macro_10y.get("poc_10y_price", 0.0))
        ma200w_dev_pct = float(macro_10y.get("ma200w_dev_pct", 0.0))
        daily_trend_score = float(daily_2y.get("daily_trend_score", 50))

        combat_prof = get_ticker_combat_profile(code, genre, rvol=q_adv["rvol"], yz_vol=q_adv["yz_vol"])
        tier_str = str(combat_prof.get("tier_class", ""))
        ofi_z = compute_smoothed_clv_z(c, h, l, v, day_bars_count=len(today_bars))

        r20 = int(np.sum(np.diff(c[-21:]) > 0)) if len(c) >= 21 else 10
        base_tech_score = float(np.clip((r20 / 20.0) * 100.0 * 0.65 + (q_adv["eff_pct"] * 0.35), 10.0, 95.0))
        inst_flow_score = float(np.clip(50.0 + ofi_z * 14.0 + (0.5 - q_adv["vpin"]) * 35.0, 10.0, 98.0))
        bb_exp_score = float(np.clip(35.0 + (q_adv["bb_exp_ratio"] - 0.8) * 32.0, 10.0, 98.0))
        vol_spike_score = float(np.clip(30.0 + q_adv["vol_spike_bull_pct"] * 2.5, 10.0, 98.0))

        core_vol_score = float(qm["q_score"]) * 0.60 + bb_exp_score * 0.40
        core_inst_score = float(ms["ms_score"]) * 0.52 + inst_flow_score * 0.48
        core_mom_score = float(q_adv["surge_attention_score"]) * 0.55 + vol_spike_score * 0.45

        st_p = style.split(" ")[1] if " " in style else "デイトレード"
        m_bias = compute_ticker_macro_bias(code, genre, macro)
        rs_alpha = round(float(daily_2y["latest_rs_alpha"]), 2) if daily_2y.get("has_data") else round(day_ret - m_bias, 2)

        # スタイル別3階層重み付け（5分足コア / 日足2年 w_1d / 週足10年 w_10y）＆特性適合ボーナス
        if st_p == "スキャルピング":
            w_vol, w_inst, w_mom, w_1d, w_10y = 1.3, 1.2, 2.5, 0.6, 0.25
            fit_bonus = 0.0
            if q_adv["yz_vol"] >= 0.35: fit_bonus += 4.5
            if q_adv["rvol"] >= 1.2: fit_bonus += 4.0
            if abs(ofi_z) >= 0.6: fit_bonus += 3.5
            if ("Tier2" in tier_str or "Tier3" in tier_str): fit_bonus += 2.0
            if "Tier4" in tier_str: fit_bonus -= 8.0
            style_fit_bonus = float(np.clip(fit_bonus, -10.0, 12.0))
        elif st_p == "スイングトレード":
            w_vol, w_inst, w_mom, w_1d, w_10y = 1.8, 2.0, 0.9, 2.2, 1.2
            fit_bonus = 0.0
            if ms["hurst"] >= 0.55: fit_bonus += 4.5
            if ms["kyle_stealth"] >= 62.0: fit_bonus += 4.0
            if daily_2y.get("bull_po") or daily_2y.get("bear_po"): fit_bonus += 4.0
            if abs(rs_alpha) >= 1.0: fit_bonus += 3.5
            if ("Tier3" in tier_str and q_adv["eff_pct"] < 35): fit_bonus -= 7.0
            style_fit_bonus = float(np.clip(fit_bonus, -10.0, 14.0))
        elif st_p == "バイ＆ホールド":
            w_vol, w_inst, w_mom, w_1d, w_10y = 0.8, 1.2, 0.4, 1.6, 2.8
            fit_bonus = 0.0
            if cagr_10y >= 12.0: fit_bonus += min((cagr_10y - 10.0) * 0.35 + 4.0, 8.0)
            if ma200w_dev_pct >= 0.0 and macro_10y.get("ma200w_slope_up", True): fit_bonus += 4.0
            if daily_2y.get("ma200_dev_pct", 0.0) >= 0.0: fit_bonus += 3.0
            if ("Tier1" in tier_str or "Tier4" in tier_str): fit_bonus += 4.5
            if ("Tier3" in tier_str and cagr_10y < 5.0) or ma200w_dev_pct < -10.0: fit_bonus -= 10.0
            style_fit_bonus = float(np.clip(fit_bonus, -12.0, 16.0))
        else:
            w_vol, w_inst, w_mom, w_1d, w_10y = 1.45, 1.55, 1.25, 1.1, 0.6
            fit_bonus = 0.0
            if q_adv["eff_pct"] >= 45: fit_bonus += 4.5
            if abs(cv - vwap_today) / max(vwap_today, 1e-4) <= 0.015: fit_bonus += 3.5
            if daily_2y.get("bull_po"): fit_bonus += 2.5
            style_fit_bonus = float(np.clip(fit_bonus, -6.0, 10.0))

        weighted_sum = base_tech_score * 1.0 + daily_trend_score * w_1d + long_10y_score * w_10y
        total_weight = 1.0 + w_1d + w_10y
        if core_vol: weighted_sum += core_vol_score * w_vol; total_weight += w_vol
        if core_inst: weighted_sum += core_inst_score * w_inst; total_weight += w_inst
        if core_mom: weighted_sum += core_mom_score * w_mom; total_weight += w_mom

        tot_win = float(np.clip((weighted_sum / total_weight) + style_fit_bonus * 0.65, 5.0, 97.8))
        kelly_pct = round(float(np.clip(max(0.0, (tot_win / 100.0) - ((1.0 - (tot_win / 100.0)) / max(q_adv["payoff"], 0.1))) * 100.0, 0.0, 35.0)), 1)

        rvol_penalty = -4.5 if q_adv["rvol"] < combat_prof["min_rvol_req"] else 0.0
        raw_expect_pct = float(np.clip(tot_win * 0.85 + ofi_z * 3.8 + m_bias * 1.8 + style_fit_bonus * 0.45 + rvol_penalty + 6.0, 5.0, 99.5))

        if core_vol and q_adv["bb_exp_ratio"] >= 1.35 and not (q_adv["rsi"] > 75.0 and q_adv["upper_wick_pressure"] > 45.0):
            qm["q_state"] = f"🧠 BBスクイーズ拡大初動 ({q_adv['bb_exp_ratio']}x)"
        if core_mom and q_adv["vol_spike_bull_pct"] >= 10.0: ms["ms_regime"] = f"⚠️ 出来高スパイク実体陽線頻度 {q_adv['vol_spike_bull_pct']}%"

        is_jp = ".T" in code; is_mkt_open = _is_market_open_now(is_jp)
        if is_mkt_open and len(today_bars) > 0:
            today_open_px = float(today_bars["Open"].iloc[0])
            pgap = round(float(((today_open_px - prev_day_close) / max(prev_day_close, 1e-4)) * 100.0), 2)
            pest = round_to_tse_tick(today_open_px, code, "nearest")
            pts_label_title = "📊 当日確定始値(Open) ＆ 実測寄付きギャップ率（※場中実測値）"
        else:
            pgap = round(float(np.clip(ofi_z * 0.65 + m_bias * 0.45, -2.5, 3.8)), 2)
            pest = round_to_tse_tick(prev_day_close * (1.0 + pgap / 100.0), code, "nearest")
            pts_label_title = "📊 マクロ・需給連動 理論寄付き試算値（※前日終値基準）"
        vwap_rounded = round_to_tse_tick(vwap_today, code, "nearest")

        hist_gu_rate = float(np.mean(daily_df_5m["Open"].values[1:].astype(float) > daily_df_5m["Close"].values[:-1].astype(float))) * 100.0 if len(daily_df_5m) >= 3 else 50.0
        gu_prob_pct = round(float(np.clip(hist_gu_rate * 0.65 + (50.0 + pgap * 10.0) * 0.35, 5.0, 95.0)), 1)

        n_bar_chk = min(20, len(c)); c_sub20, o_sub20, h_sub20, l_sub20 = c[-n_bar_chk:], o[-n_bar_chk:], h[-n_bar_chk:], l[-n_bar_chk:]
        bull_bar_ratio = float(np.mean(c_sub20 > o_sub20)) * 100.0
        bull_body_strength = float(np.mean(np.clip((c_sub20 - o_sub20) / np.maximum(h_sub20 - l_sub20, 1e-4), -1.0, 1.0))) * 50.0 + 50.0
        intraday_bull_pct = round(float(np.clip(bull_bar_ratio * 0.65 + bull_body_strength * 0.35, 5.0, 95.0)), 1)

        style_tp_scale, style_sl_scale = {"スキャルピング": (0.80, 0.80), "スイングトレード": (1.25, 1.15), "バイ＆ホールド": (1.40, 1.25)}.get(st_p, (1.00, 1.00))
        st_mul = {"スキャルピング": 1.5, "スイングトレード": 1.2, "バイ＆ホールド": 0.9}.get(st_p, 1.65)

        ma25_now = float(daily_2y.get("ma25", 0.0))
        prev_trend_weak = (cv < ma25_now * 0.992) if ma25_now > 0 else ((cv < float(np.mean(daily_df_5m["Close"].values[-5:].astype(float))) * 0.992) if len(daily_df_5m) >= 5 else False)
        rel_news_obj = next((n for n in all_impact_news if code in n.get("detail", {}).get("related_codes", [])), None)
        rel_news_title = rel_news_obj["title"] if rel_news_obj else ""

        u_wick_now, l_wick_now = float(q_adv.get("upper_wick_pressure", 0.0)), float(q_adv.get("lower_wick_support", 0.0))
        bull_edge, bear_edge = compute_directional_edges(ofi_z, q_adv["rsi"], prev_trend_weak, float(ms.get("hurst", 0.50)), u_wick_now, l_wick_now, rel_news_title=rel_news_title, rs_alpha=rs_alpha, below_vwap=(cv < vwap_today), daily_ctx=daily_2y, macro_10y=macro_10y, cv=cv)
        tactic_now = determine_tactic_classification(code, genre, ofi_z, q_adv["vpin"], q_adv["rsi"], pgap, round(raw_expect_pct, 1), prev_trend_weak, qm, ms, rel_news_title=rel_news_title, style=style, upper_wick_pressure=u_wick_now, lower_wick_support=l_wick_now, cv=cv, vwap_today=vwap_today, rs_alpha=rs_alpha, daily_ctx=daily_2y, macro_10y=macro_10y)
        is_short_now = tactic_now in ("Type-S1", "Type-S2")

        # 構造的ストップロス（直近5本の5分足スイング高安と0.60*ATR14比較）＆ 1.8〜2.2倍リスクリワードTP算出
        sl_delta_cur = compute_structural_sl_delta(l[-5:], h[-5:], cv, atrv, is_short_now, style_sl_scale, combat_prof["sl_mult"], code)
        tp_delta_cur = float(np.clip(sl_delta_cur * 2.0 * combat_prof["tp_mult"], sl_delta_cur * 1.80, max(cv * 0.048, sl_delta_cur * 2.25)))

        # 上位足Resistance（10年POC・日足MA25/MA75）が手前にある場合はその手前に調整
        ma75_now = float(daily_2y.get("ma75", 0.0))
        if not is_short_now:
            if pos_10y_pct >= 90.0 and (poc_10y_price <= 0 or cv >= poc_10y_price):
                tp_delta_cur *= 1.10
            elif poc_10y_price > cv and (poc_10y_price - cv) < tp_delta_cur:
                tp_delta_cur = max((poc_10y_price - cv) * 0.94, sl_delta_cur * 1.35)
            for res_ma in (ma25_now, ma75_now):
                if res_ma > cv and (res_ma - cv) < tp_delta_cur * 0.85:
                    tp_delta_cur = max((res_ma - cv) * 0.95, sl_delta_cur * 1.35)
        else:
            for sup_lv in (ma25_now, ma75_now, poc_10y_price):
                if 0 < sup_lv < cv and (cv - sup_lv) < tp_delta_cur * 0.85:
                    tp_delta_cur = max((cv - sup_lv) * 0.95, sl_delta_cur * 1.35)

        exec_score, exec_grade, exec_detail = evaluate_execution_quality_gate(is_short_now, prev_trend_weak, cv, vwap_today, int(q_adv["eff_pct"]), bull_edge, bear_edge, float(q_adv["rvol"]), float(combat_prof["min_rvol_req"]), u_wick_now, l_wick_now, daily_ctx=daily_2y, macro_10y=macro_10y, macro=macro, rs_alpha=rs_alpha)

        if is_short_now:
            tpv = round_to_tse_tick(max(cv - tp_delta_cur, cv * 0.5), code, "floor"); slv = round_to_tse_tick(cv + sl_delta_cur, code, "ceil")
        else:
            tpv = round_to_tse_tick(cv + tp_delta_cur, code, "ceil"); slv = round_to_tse_tick(max(cv - sl_delta_cur, cv * 0.5), code, "floor")

        lot_info = compute_japanese_lot_sizing(cv, slv, total_capital, risk_tolerance_pct, is_jp, st_mul, lot_cap_mult=combat_prof["lot_cap_mult"])
        tp_pct_disp = round((tpv - cv) / max(cv, 1e-4) * 100, 1); sl_pct_disp = round((slv - cv) / max(cv, 1e-4) * 100, 1)
        tp_sign = "+" if tp_pct_disp > 0 else ""; sl_sign = "+" if sl_pct_disp > 0 else ""

        active_boosts_tuple = tuple(sorted([k for k, f in [("core_vol", core_vol), ("core_inst", core_inst), ("core_mom", core_mom)] if f]))
        strat = select_dynamic_strategy(code.replace(".T", ""), style, ofi_z, q_adv["vpin"], q_adv["cvar95"], q_adv["rsi"], lot_info, fmt_px(pest, is_jp, code), fmt_px(vwap_rounded, is_jp, code), f"{fmt_px(tpv, is_jp, code)}({tp_sign}{tp_pct_disp}%)", f"{fmt_px(slv, is_jp, code)}({sl_sign}{sl_pct_disp}%)", qm, ms, name=name, theme=theme, rel_news_title=rel_news_title, pgap=pgap, expect_pct=round(raw_expect_pct, 1), prev_trend_weak=prev_trend_weak, full_code=code, genre=genre, upper_wick_pressure=u_wick_now, lower_wick_support=l_wick_now, cv=cv, vwap_today=vwap_today, rs_alpha=rs_alpha, macro_10y=macro_10y, daily_2y=daily_2y)
        forward_test = record_and_verify_daily_Forward_test(df, code, strat, pest, vwap_rounded, tpv, slv, lot_info["shares"], style, total_capital=total_capital, risk_tolerance_pct=risk_tolerance_pct, shared_ledger=shared_ledger, save_db=save_db, genre=genre, daily_2y=daily_2y, macro_10y=macro_10y, active_boosts=active_boosts_tuple)

        ft_days, ft_wr, ft_prof = int(forward_test.get("total_days", 0)), float(forward_test.get("actual_win_rate", 50.0)), float(forward_test.get("total_profit_yen", 0.0))
        ft_bonus = float(np.clip((ft_wr - 52.0) * 0.14 + (1.8 if ft_prof > 0 else -1.5), -5.0, 6.0)) if ft_days >= 3 else 0.0

        if is_short_now:
            short_base_tech = float(np.clip(((20 - r20) / 20.0) * 100.0 * 0.65 + (q_adv["eff_pct"] * 0.35), 10.0, 95.0))
            short_inst_flow = float(np.clip(50.0 + (-ofi_z) * 14.0 + (q_adv["vpin"] - 0.5) * 35.0, 10.0, 98.0))
            short_tot_win = float(np.clip((short_base_tech + qm["q_score"] * 0.80 + ms["ms_score"] * 0.80 + short_inst_flow * 0.80 + q_adv["surge_attention_score"] * 0.65) / 4.05, 10.0, 97.8))
            short_strength = short_tot_win * 0.82 + bear_edge * 0.42 + u_wick_now * 0.12 + (-m_bias) * 1.8 + style_fit_bonus * 0.40 + rvol_penalty + 4.0
            expect_pct = float(np.clip(short_strength + ft_bonus, 5.0, 98.5))
        else:
            expect_pct = float(np.clip(raw_expect_pct + ft_bonus, 5.0, 98.5))

        edge = round((expect_pct - 50.0) / 10.0 + abs(ofi_z) * 0.5, 2)
        if strat.get("side") == "SHORT":
            t_num, t_lbl, t_col, t_bg = (10, "【📉S級空売り：過熱天井・下落急襲モード】", "#fff", "linear-gradient(90deg,#9f1239,#be123c)") if expect_pct >= 88.0 else ((9, "【📉A級空売り：VWAP割れ順張りショート】", "#fff", "linear-gradient(90deg,#be123c,#6d28d9)") if expect_pct >= 78.0 else (8, "【📉空売り優位：反落収益化モード】", "#fff", "linear-gradient(90deg,#881337,#4c1d95)"))
        else:
            t_num, t_lbl, t_col, t_bg = (10, "【Lv.10：🔥S級・全力買い突破】", "#fff", "linear-gradient(90deg,#7e22ce,#dc2626)") if expect_pct >= 90.0 else ((9, "【Lv.9：⚡超強気順張り買い】", "#fff", "linear-gradient(90deg,#0369a1,#1d4ed8)") if expect_pct >= 80.0 else ((7, "【Lv.7：⭕押し目買い優位】", "#e2e8f0", "linear-gradient(90deg,#065f46,#0f766e)") if expect_pct >= 65.0 else (5, "【Lv.5：⚖️中立・押し目待機】", "#e2e8f0", "linear-gradient(90deg,#334155,#1e293b)")))

        # JSONシリアライズ軽量化のため df_daily_clean を除外した軽量辞書を返却
        daily_2y_serializable = {k: v for k, v in daily_2y.items() if k not in ("df_daily_clean", "daily_rs_alpha_map")}

        return {
            "full_code": code, "code": code.replace(".T", ""), "name": name, "genre": genre, "theme": theme,
            "combat_tier": combat_prof["tier_class"], "combat_cost_pct": round(combat_prof["cost_rate"] * 100, 2),
            "exec_grade": exec_grade, "exec_score": exec_score, "exec_detail": exec_detail, "rs_alpha": rs_alpha,
            "style_fit_bonus": round(style_fit_bonus, 1), "macro_10y": macro_10y, "daily_2y": daily_2y_serializable,
            "price": fmt_px(cv, is_jp, code), "raw_close": cv,
            "tp_price": fmt_px(tpv, is_jp, code), "tp_pct": tp_pct_disp, "sl_price": fmt_px(slv, is_jp, code), "sl_pct": sl_pct_disp, "vwap_price": fmt_px(vwap_rounded, is_jp, code),
            "inst_score": int(np.clip(round((ms["ms_score"] + inst_flow_score) * 0.5), 10, 99)), "vpin": q_adv["vpin"], "ofi_z": round(ofi_z, 2), "yz_vol": q_adv["yz_vol"], "cvar95": q_adv["cvar95"], "eff_pct": q_adv["eff_pct"], "kelly_pct": kelly_pct,
            "bb_exp_ratio": q_adv["bb_exp_ratio"], "vol_spike_bull_pct": q_adv["vol_spike_bull_pct"], "upper_wick_pressure": u_wick_now, "lower_wick_support": l_wick_now, "bull_edge": bull_edge, "bear_edge": bear_edge,
            "q_score": qm["q_score"], "q_tunnel": qm["q_tunnel"], "q_coherence": qm["q_coherence"], "q_entropy": qm["q_entropy"], "q_state": qm["q_state"],
            "ms_score": ms["ms_score"], "hurst": ms["hurst"], "kyle_lambda": ms["kyle_lambda"], "kyle_stealth": ms["kyle_stealth"], "ms_regime": ms["ms_regime"],
            "expect_pct": round(expect_pct, 1), "surge_attention_score": q_adv["surge_attention_score"], "rvol": q_adv["rvol"], "news_hits": news_hits,
            "pts_est_price": fmt_px(pest, is_jp, code), "pts_gap_pct": pgap, "pts_label_title": pts_label_title, "diff": round(day_ret, 2), "prob": gu_prob_pct, "intraday_win_rate": intraday_bull_pct,
            "total_win_rate": round(tot_win, 1), "rsi": q_adv["rsi"], "payoff": q_adv["payoff"], "edge": edge, "ai_score": int(np.clip(round(expect_pct * 0.92 + 4), 10, 99)),
            "tier_num": t_num, "tier_label": t_lbl, "tier_color": t_col, "tier_bg": t_bg, "lot_info": lot_info, "strat": strat, "forward_test": forward_test
        }
    except Exception as e: record_system_error("analyze_df", e, f"Code: {code}"); return None

# 14. 全市場オートディスカバリー＆弱肉強食サバイバル入れ替えスキャン
@st.cache_data(ttl=90)
def fetch_pool_batch(macro, style, core_vol=True, core_inst=True, core_mom=True, total_cap=1000000, risk_pct=2.0):
    base_roster = load_active_market_roster(); existing_codes = tuple(sorted([it[0] for it in base_roster]))
    challengers = discover_challenger_tickers(existing_codes); challenger_codes_set = {it[0] for it in challengers}
    combined_universe, seen_c = [], set()
    for it in base_roster + challengers:
        if it[0] not in seen_c and it[0] not in DELISTED_OR_INVALID_CODES: seen_c.add(it[0]); combined_universe.append((it[0], it[1], it[2], it[3]))
    combined_universe = combined_universe[:45]
    codes_tuple = tuple(c for c, _, _, _ in combined_universe)
    buzz_map = fetch_real_market_buzz(tuple(combined_universe))
    macro_10y_map = fetch_10y_macro_metrics(codes_tuple)
    daily_2y_map = fetch_2y_daily_metrics(codes_tuple)
    codes = list(codes_tuple)

    raw = {}
    for p_str in ("60d", "1mo", "15d"):
        try:
            raw = yf.download(codes, period=p_str, interval="5m", group_by="ticker", threads=True, progress=False, timeout=10.0)
            if raw is not None and not raw.empty: break
        except Exception as e: record_system_error(f"fetch_pool_batch:{p_str}", e)

    shared_ledger = db_get("daily_forward_ledger", {})
    if not isinstance(shared_ledger, dict): shared_ledger = {}
    evaluated_all = []
    def _w(c, n, g, t):
        df = _extract_ticker_df(raw, c, len(codes))
        r = analyze_df(df, c, n, t, g, macro, buzz_map, style, core_vol=core_vol, core_inst=core_inst, core_mom=core_mom, total_capital=total_cap, risk_tolerance_pct=risk_pct, shared_ledger=shared_ledger, save_db=False, macro_10y_map=macro_10y_map, daily_2y_map=daily_2y_map)
        if r: r["is_new_challenger"] = (c in challenger_codes_set)
        return r

    with ThreadPoolExecutor(max_workers=min(len(combined_universe), 8)) as ex:
        for f in as_completed([ex.submit(_w, c, n, g, t) for c, n, g, t in combined_universe]):
            try:
                r = f.result()
                if r: evaluated_all.append(r)
            except Exception as e: record_system_error("fetch_pool_batch:future", e)
    db_set("daily_forward_ledger", shared_ledger)

    st_p = style.split(" ")[1] if " " in style else "デイトレード"
    if st_p == "スキャルピング":
        evaluated_all.sort(key=lambda x: (x["expect_pct"] * 0.72 + x["surge_attention_score"] * 0.28), reverse=True)
    elif st_p == "スイングトレード":
        evaluated_all.sort(key=lambda x: (x["expect_pct"] * 0.68 + x.get("daily_2y", {}).get("daily_trend_score", 50) * 0.20 + x.get("macro_10y", {}).get("long_10y_score", 50) * 0.12), reverse=True)
    elif st_p == "バイ＆ホールド":
        evaluated_all.sort(key=lambda x: (x["expect_pct"] * 0.55 + x.get("daily_2y", {}).get("daily_trend_score", 50) * 0.15 + x.get("macro_10y", {}).get("long_10y_score", 50) * 0.30), reverse=True)
    else:
        evaluated_all.sort(key=lambda x: (x["expect_pct"] * 0.74 + x["surge_attention_score"] * 0.18 + x.get("daily_2y", {}).get("daily_trend_score", 50) * 0.08), reverse=True)

    survivors, survivor_codes = [], set()
    for g in DYNAMIC_GENRES:
        for item in [x for x in evaluated_all if x["genre"] == g][:4]:
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
def fetch_one(code, macro, style, core_vol=True, core_inst=True, core_mom=True, total_cap=1000000, risk_pct=2.0):
    try:
        code = code.strip().upper()
        if re.match(r"^[0-9]{3}[0-9A-Z]$", code): code = f"{code}.T"
        if code in DELISTED_OR_INVALID_CODES: return None
        inf = resolve_ticker_metadata(code)
        local_buzz = {code: {"news_hits": len(search_single_query(f"{inf['name']} 株", 5, trusted_only=False))}}
        macro_10y_map = fetch_10y_macro_metrics((code,))
        daily_2y_map = fetch_2y_daily_metrics((code,))
        tkr = yf.Ticker(code); hist_df = None
        for p_str in ("60d", "1mo", "15d"):
            hist_df = tkr.history(period=p_str, interval="5m")
            if hist_df is not None and not hist_df.empty: break
        return analyze_df(hist_df, code, inf["name"], inf["theme"], inf["genre"], macro, local_buzz, style, core_vol=core_vol, core_inst=core_inst, core_mom=core_mom, total_capital=total_cap, risk_tolerance_pct=risk_pct, macro_10y_map=macro_10y_map, daily_2y_map=daily_2y_map)
    except Exception as e: record_system_error("fetch_one", e, f"Code: {code}"); return None

# 15. ヘッダー / マクロ指標
macro_info = fetch_macro()
mpills = "".join([f'<div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);padding:2px 8px;border-radius:6px;font-size:10.5px;display:inline-flex;gap:4px;"><span style="color:#94a3b8;">{m["label"]}</span><span style="color:{"#10b981" if m["diff"]>=0 else "#ef4444"};font-weight:700;">{"+" if m["diff"]>=0 else ""}{m["diff"]}%</span></div>' for m in macro_info.values()])
st.markdown(f'<div class="glass-header"><div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;"><div class="brand-luxury">YAMASHISHI LAB</div><div style="font-size:10px;color:#94a3b8;">週足10年 × 日足2年 × 5分足60日 3階層MTF融合 × Gemini マルチペルソナ合議</div></div><div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:8px;">{mpills}</div></div>', unsafe_allow_html=True)

_cache_pool_key = f"pool_v22_strict_mtf_{investment_style}_{sorted(list(ac_b))}_{total_capital}_{risk_tolerance_pct}"
if _cache_pool_key not in st.session_state:
    with st.spinner(f"⚛️ 【{investment_style.split(' ')[1]}】週足10年×日足2年×5分足60日 3階層MTFスコアリングを実行中..."):
        g_res, all_res = fetch_pool_batch(macro_info, investment_style, core_vol=("core_vol" in ac_b), core_inst=("core_inst" in ac_b), core_mom=("core_mom" in ac_b), total_cap=total_capital, risk_pct=risk_tolerance_pct)
        st.session_state[_cache_pool_key] = (g_res, all_res)
else: g_res, all_res = st.session_state[_cache_pool_key]

# 16. 画面レンダリング（フォーカス・ニュース・個別診断独立ページ・メインランキング）
focused_item = st.session_state.get("focused_stock_item")
if focused_item:
    st.markdown("### 🔵 銘柄詳細・売買合議フォーカスモード")
    render_card(focused_item, is_custom=False, kp=f"foc_{focused_item['code']}", is_focused=True); st.stop()

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
    ai_deep_block = f'<div class="rank-card" style="border-left-color:#10b981;background:linear-gradient(180deg,#06281e 0%,#090d16 100%)!important;"><div style="font-size:14px;font-weight:800;color:#10b981;margin-bottom:6px;">🧠 Gemini AI生成・個別記事深掘り解析</div><div style="font-size:12.5px;line-height:1.75;color:#ecfdf5;">{html.escape(ai_deep_txt).replace(chr(10), "<br>")}</div></div>' if ai_deep_txt else '<div class="rank-card" style="border-left-color:#f59e0b;background:linear-gradient(180deg,#1e180b 0%,#090d16 100%)!important;"><div style="font-size:13px;font-weight:800;color:#fde047;margin-bottom:4px;">⚙️ 定型セオリー解説モード（Gemini API未接続時）</div><div style="font-size:12px;line-height:1.65;color:#fef3c7;">現在Gemini APIキーが未接続のため、以下のレポートはマルチソース報道要約とテーマ別の<b>定型セオリー解説テンプレート</b>を表示しています。</div></div>'

    st.markdown(f'<div class="glass-header" style="border-left:4px solid #ef4444;"><div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;"><div><span class="pill-badge" style="background:#ef4444;color:#fff;font-weight:800;">🚨 重大ニュース解説レポート ｜ {html.escape(tn.get("cat", "速報"))} (重要度: {tn.get("impact_score", 70)}点)</span>{cross_badge}</div><span style="font-size:11px;color:#94a3b8;">配信元: {html.escape(tn.get("source", "Market Wire"))} ｜ {html.escape(tn.get("pub_date", ""))} (経過: {tn.get("age_hours", 0)}h)</span></div><div style="font-size:17.5px;font-weight:800;color:#f8fafc;margin-top:8px;line-height:1.4;">{html.escape(tn["title"])}</div><div style="font-size:11.5px;color:#fde047;margin-top:6px;font-weight:700;">🎯 直撃テーマ領域: {html.escape(det.get("sector_focus", ""))}</div>{link_btn}</div>{ai_deep_block}<div class="rank-card" style="border-left-color:#38bdf8;"><div style="font-size:14px;font-weight:800;color:#38bdf8;margin-bottom:6px;">📰 1. ニュース要点 ＆ 定型セオリー解説（セクター背景）</div><div style="font-size:12.5px;line-height:1.75;color:#e2e8f0;">{body_html}</div></div><div class="rank-card" style="border-left-color:#a855f7;"><div style="font-size:14px;font-weight:800;color:#e9d5ff;margin-bottom:6px;">🧠 2. 定型セオリー解説（需給波及メカニズム・資金移動ルート）</div><div style="font-size:12.5px;line-height:1.75;color:#e2e8f0;">{mech_html}</div><hr style="border-color:rgba(168,85,247,0.25);margin:12px 0;"><div style="font-size:13.5px;font-weight:800;color:#fde047;margin-bottom:6px;">⏱️ 3. 時間帯別・市場織り込み3フェーズシナリオ（定型モデル）</div><div style="font-size:12px;line-height:1.75;color:#cbd5e1;">{time_html}</div><hr style="border-color:rgba(239,68,68,0.25);margin:12px 0;"><div style="font-size:13px;font-weight:800;color:#f87171;margin-bottom:4px;">⚠️ 4. ダマシ・寄り天警戒リスク ＆ 撤退基準</div><div style="font-size:12px;line-height:1.7;color:#fca5a5;">{risk_html}</div><div class="beginner-action-box" style="margin-top:12px;"><b>⚡ 5. 【{st_short}】統計ルール基準・実践トレード立ち回り手順</b><br>{act_html}</div></div>', unsafe_allow_html=True)
    st.markdown("### 🔗 このニュースに直結する連動注目銘柄（動的抽出）")
    rel_codes = list(det.get("related_codes", [])); matched_stocks = [r_it for r_it in all_res if r_it["full_code"] in rel_codes or r_it["code"] in rel_codes]; existing_matched_codes = {m["full_code"] for m in matched_stocks}
    for rc in rel_codes:
        if rc not in existing_matched_codes and len(matched_stocks) < 3:
            extra_r = fetch_one(rc, macro_info, investment_style, core_vol=("core_vol" in ac_b), core_inst=("core_inst" in ac_b), core_mom=("core_mom" in ac_b), total_cap=total_capital, risk_pct=risk_tolerance_pct)
            if extra_r: matched_stocks.append(extra_r); existing_matched_codes.add(rc)
    for idx, r_item in enumerate(sorted(matched_stocks if matched_stocks else all_res, key=lambda x: x["expect_pct"], reverse=True)[:3], 1): render_card(r_item, rank=idx, kp=f"nr_{tn['id']}")
    if st.button("⬅️ 戻る", use_container_width=True, type="primary"): st.session_state["navigation_page"] = "TOP"; st.session_state["scroll_top_trig"] = int(time.time()*1000); st.rerun()
    st.stop()

c1, c2 = st.columns([3.4, 1])
cin = c1.text_input("🔍 銘柄検索", placeholder="コード入力 (例: 6920 / 7203 / AAPL)", label_visibility="collapsed", key="search_code_input")
if c2.button("🔍 診断", use_container_width=True) and cin:
    st.session_state["custom_search_code"] = clean_k(cin)
    st.session_state["focused_stock_item"] = None
    st.session_state["navigation_page"] = "TOP"
    st.session_state["scroll_top_trig"] = int(time.time() * 1000)
    st.rerun()

if st.session_state.get("custom_search_code"):
    st.markdown("### 🎯 個別銘柄・精密3階層MTFクオンツ診断モード")
    with st.spinner("📡 銘柄正式名称・週足10年・日足2年・5分足60日波形を解析中..."):
        cr = fetch_one(st.session_state["custom_search_code"], macro_info, investment_style, core_vol=("core_vol" in ac_b), core_inst=("core_inst" in ac_b), core_mom=("core_mom" in ac_b), total_cap=total_capital, risk_pct=risk_tolerance_pct)
    if cr:
        render_card(cr, is_custom=True, kp="custom")
    else:
        st.warning("⚠️ 指定された銘柄コードのデータが取得できないか、上場廃止・無効な銘柄です。")
    if st.button("⬅️ トップ画面（ランキング一覧）に戻る", key="btn_back_from_custom_diag", use_container_width=True, type="primary"):
        st.session_state["custom_search_code"] = ""
        if "search_code_input" in st.session_state: st.session_state["search_code_input"] = ""
        st.session_state["scroll_top_trig"] = int(time.time() * 1000)
        st.rerun()
    st.stop()

def cut_stocks(slist, pct): return slist[:max(3, int(round(len(slist) * (pct / 100.0))))] if slist else []

cats = ["🏆 総合TOP5", "⚛️ ボラティリティ突破TOP10", "🏛️ 5分足需給ミクロTOP10", "🚨 重大ニュース＆連動株", "🎟️ 直近IPO・グロース実測分析", "🏦 BVC-VPIN・CLV資金フロー", "🔥 出来高サージ＆市場注目度", "📋 監視シート"] + [f"📂 {g}" for g in DYNAMIC_GENRES]
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
    st.markdown('<div class="glass-header"><div style="font-size:16px;font-weight:800;color:#f8fafc;">🎟️ 2階建てIPO・グロース市場 実測サバイバルターミナル</div></div>', unsafe_allow_html=True)
    with st.spinner("📡 上場前注目IPO報道＆既上場グロース広域プールを実測スキャン中..."): ipo_bundle = fetch_real_ipo_growth_analysis()
    for p_ipo in (ipo_bundle.get("pre_ipo", []) if isinstance(ipo_bundle, dict) else []):
        st.markdown(f'<div class="rank-card" style="border-left-color:#a855f7;background:linear-gradient(180deg,#160d2b 0%,#090d16 100%)!important;"><div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:4px;margin-bottom:6px;"><div><span class="pill-badge" style="background:#a855f7;color:#fff;font-weight:800;">{html.escape(p_ipo["status"])}</span><span class="quantum-badge">報道熱量 {p_ipo["heat_score"]}点</span></div><span style="font-size:11px;color:#cbd5e1;">市場: {html.escape(p_ipo["market"])}</span></div><div style="font-size:16.5px;font-weight:800;color:#f8fafc;">{html.escape(p_ipo["name"])} <span style="font-size:11.5px;color:#c084fc;">({html.escape(p_ipo["code"])})</span></div><div style="font-size:11.5px;color:#38bdf8;margin-top:3px;"><b>🎯 核心事業:</b> {html.escape(p_ipo["theme"])}</div><div style="background:rgba(2,6,23,0.75);border:1px solid rgba(168,85,247,0.3);border-radius:6px;padding:7px 10px;margin-top:6px;font-size:11.5px;color:#e9d5ff;">📰 <b>最新RSS観測:</b> {html.escape(p_ipo["latest_headline"])}</div></div>', unsafe_allow_html=True)
    for ipo in (ipo_bundle.get("survivors", []) if isinstance(ipo_bundle, dict) else []):
        chg_col = "#10b981" if ipo["chg_pct"] >= 0 else "#ef4444"
        st.markdown(f'<div class="rank-card" style="border-left-color:#f59e0b;"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;flex-wrap:wrap;gap:4px;"><div><span class="pill-badge" style="background:#f59e0b;color:#0f172a;font-weight:900;">🏆 生存 第{ipo["rank"]}位</span><span class="pill-badge" style="background:rgba(250,204,21,0.2);color:#fde047;border-color:#facc15;">スコア {ipo["score"]}点</span></div><div style="font-size:11px;color:#38bdf8;font-weight:700;">{html.escape(ipo["tier"])}</div></div><div><span style="font-size:18px;font-weight:800;color:#f8fafc;">{html.escape(ipo["name"])}</span> <span style="font-size:12px;color:#94a3b8;">({ipo["code"]} / {html.escape(ipo["market"])})</span></div><div class="trade-plan-box" style="margin-top:9px;"><div><div style="font-size:9.5px;color:#94a3b8;">💰 現在値</div><div style="font-size:12px;font-weight:800;">{ipo["price"]} (<span style="color:{chg_col};">{ipo["chg_pct"]:+.2f}%</span>)</div></div><div><div style="font-size:9.5px;color:#94a3b8;">📊 RVOL</div><div style="font-size:12px;font-weight:800;color:#fde047;">{ipo["rvol"]}倍</div></div><div><div style="font-size:9.5px;color:#94a3b8;">📈 高値乖離</div><div style="font-size:12px;font-weight:800;">{ipo["from_high_pct"]}%</div></div></div><div style="margin-top:8px;"><a href="{ipo["kabutan_url"]}" target="_blank" class="ipo-link-btn">📊 株探詳細</a><a href="{ipo["yahoo_url"]}" target="_blank" class="ipo-link-btn" style="border-color:#38bdf8;color:#7dd3fc;">💹 Yahoo!ファイナンス</a></div></div>', unsafe_allow_html=True)
        if st.button(f"🔵 {ipo['name']} ({ipo['code']}) の実戦検証と売買戦略詳細を見る", key=f"ipo_diag_{ipo['code']}", use_container_width=True): st.session_state["custom_search_code"] = ipo["full_code"]; st.session_state["scroll_top_trig"] = int(time.time() * 1000); st.rerun()
elif sel_cat == "🏦 BVC-VPIN・CLV資金フロー":
    for i, r in enumerate(sorted(surv, key=lambda x: x["inst_score"], reverse=True)[:10], 1): render_card(r, rank=i, kp="inst")
elif sel_cat == "🔥 出来高サージ＆市場注目度":
    for i, r in enumerate(sorted(surv, key=lambda x: x["surge_attention_score"], reverse=True)[:10], 1): render_card(r, rank=i, kp="mom")
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

# 17. 免責事項（法的表示）
st.markdown('<div class="disclaimer-banner"><b>⚖️ 重要免責事項・法的表示</b><br>本システム「YAMASHISHI LAB」が提供するすべての指標（ボラティリティ突破指数・WKB統計近似モデル、5分足60日OHLCV需給ミクロ構造近似、日足2年中期トレンド・MAパーフェクトオーダー・MACD・52週位置・本物日足ATR14・対ベンチマークRSα、過去10年週足大局アルゴリズム・10年POC価格帯別出来高解析、BVC-VPIN・Kyle-λ統計近似、WRVヒゲ拒絶ベクトル、時間帯補正RVOL・3階層MTF5条件執行品質ゲート、当日実測寄付きギャップ／理論寄付き試算値、期待度パーセンテージ、Geminiマルチペルソナ合議ログ、および買い・空売り双方の売買プラン）は、過去の5分足・日足・週足四本値および出来高(OHLCV)データと数理アルゴリズムに基づく研究シミュレーション・情報提供を目的としたものであり、実際の板情報（Tick）やPTS実勢値に基づくものではなく、特定の有価証券の売買推奨や投資助言（投資助言・代理業等）を行うものではありません。株式投資（特に信用取引・空売り）には元本割れや元本超過損・市場変動のリスクが伴います。最終的な投資判断および資金配分は、必ず利用者ご自身の自己責任にて行っていただけますようお願い申し上げます。</div>', unsafe_allow_html=True)
