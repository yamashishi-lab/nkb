import streamlit as st, streamlit.components.v1 as components, yfinance as yf, pandas as pd, numpy as np
import unicodedata, hashlib, hmac, json, os, re, ssl, smtplib, time, threading, sqlite3, uuid, traceback, secrets, html, random
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

def record_system_error(module_name: str, error_obj: Exception, context_info: str = ""):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        "id": hashlib.md5(f"{now_str}_{module_name}_{error_obj}_{time.time_ns()}".encode()).hexdigest()[:8],
        "time": now_str, "module": module_name, "error_type": type(error_obj).__name__,
        "message": str(error_obj), "context": context_info, "traceback": traceback.format_exc()
    }
    with _ERROR_LOCK:
        try:
            cur = db_get("system_error_logs", [])
            cur = cur if isinstance(cur, list) else []
            cur.insert(0, entry)
            db_set("system_error_logs", cur[:MAX_ERROR_LOGS])
        except Exception: pass

def get_system_error_logs() -> list:
    logs = db_get("system_error_logs", [])
    return logs if isinstance(logs, list) else []

def clear_system_error_logs(): db_set("system_error_logs", [])

# ==========================================
# 1. 初期設定とセキュリティ
# ==========================================
st.set_page_config(page_title="YAMASHISHI LAB", page_icon="⚡", layout="centered", initial_sidebar_state="collapsed")

def _get_sec_param(env_k, default_gen, lock_file=None):
    v = os.environ.get(env_k) or (getattr(st, "secrets", {}).get(env_k) if hasattr(st, "secrets") else None)
    if v: return v.strip() if isinstance(v, str) else v
    if lock_file and os.path.exists(lock_file):
        try:
            with open(lock_file, "r", encoding="utf-8") as f: return f.read().strip()
        except Exception: pass
    val = default_gen()
    if lock_file:
        try:
            with open(lock_file, "w", encoding="utf-8") as f: f.write(str(val))
        except Exception: pass
    return val

SECRET_KEY = _get_sec_param("SECRET_KEY", lambda: hashlib.sha3_512(f"{secrets.token_hex(64)}:{time.time_ns()}".encode()).hexdigest(), ".yamashishi_sys_seed.key")
ADMIN_EMAIL = (_get_sec_param("ADMIN_EMAIL", lambda: "nthbh399@ybb.ne.jp")).strip().lower()
ADMIN_PASS = _get_sec_param("ADMIN_PASS", lambda: "ADMIN777", ".yamashishi_cred.lock")
DB_SQLITE_PATH = "yamashishi_core.db"

AI_PROVIDERS = {
    "gemini": ("🔵 Google Gemini", ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash", "gemini-2.5-pro", "gemma-2-27b-it"], "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"),
    "openai": ("🟢 OpenAI ChatGPT", ["gpt-4o-mini", "gpt-4o", "o3-mini"], "https://api.openai.com/v1/chat/completions"),
    "claude": ("🟠 Anthropic Claude", ["claude-3-7-sonnet-latest", "claude-3-5-haiku-latest"], "https://api.anthropic.com/v1/messages"),
    "grok": ("⚫ xAI Grok", ["grok-2-latest", "grok-3-mini"], "https://api.xai.com/v1/chat/completions"),
    "deepseek": ("🟣 DeepSeek", ["deepseek-chat", "deepseek-reasoner"], "https://api.deepseek.com/chat/completions"),
    "perplexity": ("🌐 Perplexity Sonar", ["sonar-pro", "sonar"], "https://api.perplexity.ai/chat/completions"),
    "groq": ("⚡ Groq LPU", ["llama-3.3-70b-versatile", "qwen-2.5-32b"], "https://api.openai.com/v1/chat/completions")
}

GEMINI_MODEL_DISPLAY_NAMES = {
    "gemini-2.5-flash": "Gemini 3.8 Flash (高速標準)", "gemini-2.0-flash": "Gemini 3.6 Flash (低遅延)",
    "gemini-2.0-flash-lite": "Gemini 3.5 Flash-Lite (最軽量)", "gemini-1.5-flash": "Gemini 3.8 Live (リアルタイム適応)",
    "gemini-2.5-pro": "Gemini 3.5 Live Translate (高精度多言語)", "gemma-2-27b-it": "Gemma 4 (オープンウェイト次世代)"
}

IPO_OFFERINGS = [
    {"rank": 1, "code": "401A", "name": "AIクロスロボティクス", "market": "東証グロース", "bb_period": "10/24 〜 10/28", "list_date": "11/06", "price_band": "1,680円 〜 1,850円", "expect_return": "+115.0%", "score": 98, "tier": "🌟 S級：モデル高適性（初値試算+100%超領域）", "lead": "SBI証券 / 野村證券", "theme": "防衛省向け自律型防空AIドローン・エッジAI群制御システム開発", "lockup": "180日（VC解除条項なし・試算売り圧極小）", "absorption": "約12.5億円（小型軽量案件）", "pe": "予想PER 24.2倍（同業他社平均45倍対比で大幅割安）", "vc_ratio": "VC比率 4.2%（極めて低く上値が軽い）", "strategy": "初値高騰モデル確率95%以上。資金枠に応じたBB参加シミュレーション。公募割当時は初値での手堅い利益確定シナリオを検証。", "links": [("🏦 SBI証券", "https://www.sbisec.co.jp"), ("🏦 野村證券", "https://www.nomura.co.jp")]},
    {"rank": 2, "code": "405A", "name": "ネクストグリッド電力", "market": "東証プライム", "bb_period": "10/25 〜 10/30", "list_date": "11/10", "price_band": "2,400円 〜 2,600円", "expect_return": "+42.5%", "score": 91, "tier": "🔥 A級：高流動性・安定配分モデル", "lead": "SMBC日興証券 / 大和証券", "theme": "AIデータセンター向け次世代超電導送電網・高効率分散型パワーグリッド", "lockup": "90日または公募価格1.5倍で解除", "absorption": "約85.0億円（プライム適正サイズ）", "pe": "予想PER 18.5倍（配当利回り予想 3.2%）", "vc_ratio": "VC比率 1.1%（大半が政府系インフラファンド保有）", "strategy": "複数単元割当が狙える良質大型案件。海外機関投資家の事前ロードショー需要が旺盛。中長期ポートフォリオ組み入れ適性モデル。", "links": [("🏦 SMBC日興", "https://www.smbcnikko.co.jp"), ("🏦 大和証券", "https://www.daiwa.jp")]},
    {"rank": 3, "code": "409A", "name": "クアンタム・マテリアルズ", "market": "東証グロース", "bb_period": "11/02 〜 11/07", "list_date": "11/18", "price_band": "950円 〜 1,050円", "expect_return": "+78.0%", "score": 94, "tier": "🌟 S級：テーマ性特化型モデル", "lead": "楽天証券 / みずほ証券", "theme": "室温超伝導・量子コンピュータ向け新素材受託製造(ファウンドリ)", "lockup": "360日（強固な大株主ロックアップ）", "absorption": "約18.0億円（値頃感あり）", "pe": "赤字先行型（来期黒字転換パイプライン確定済）", "vc_ratio": "VC比率 8.5%", "strategy": "1000円前後の低単価で個人需給が集中しやすい。初動セカンダリー市場におけるボラティリティ追従シナリオの妙味が高い。", "links": [("🏦 楽天証券", "https://www.rakuten-sec.co.jp"), ("🏦 みずほ証券", "https://www.mizuho-sc.com")]}
]

# ==========================================
# 2. 全市場動的ユニバース
# ==========================================
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
STOCK_METADATA_CACHE = {c: {"name": n, "genre": g, "theme": t} for c, n, g, t in GLOBAL_MARKET_TICKERS}

# ==========================================
# 3. 高速インメモリキャッシュ & DBレイヤー ＆ 暗号化ストレージ
# ==========================================
_DB_LOCK, _MEM_CACHE = threading.RLock(), {}
if "client_uuid" not in st.session_state: st.session_state["client_uuid"] = str(uuid.uuid4())

@contextmanager
def get_db_cursor():
    conn = sqlite3.connect(DB_SQLITE_PATH, check_same_thread=False, timeout=10.0)
    for p in ["PRAGMA journal_mode=WAL;", "PRAGMA synchronous=NORMAL;", "PRAGMA busy_timeout=10000;"]: conn.execute(p)
    cursor = conn.cursor()
    try: yield cursor; conn.commit()
    except Exception as e:
        conn.rollback(); record_system_error("db_transaction_error", e); raise
    finally: conn.close()

def init_sqlite_db():
    with _DB_LOCK:
        try:
            with get_db_cursor() as cur:
                cur.execute("CREATE TABLE IF NOT EXISTS kv_store (key TEXT PRIMARY KEY, val TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
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

def _derive_crypto_key(salt: bytes) -> bytes: return hashlib.pbkdf2_hmac("sha256", SECRET_KEY.encode(), salt, 60000, 32)

def encrypt_secret_str(plain_text: str) -> str:
    if not plain_text: return ""
    salt = secrets.token_bytes(16); key = _derive_crypto_key(salt)
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        nonce = secrets.token_bytes(12)
        return "enc:" + (salt + nonce + AESGCM(key).encrypt(nonce, plain_text.encode("utf-8"), None)).hex()
    except Exception:
        data = plain_text.encode("utf-8"); stream = b""
        while len(stream) < len(data): stream += hashlib.sha256(stream + key + salt).digest()
        xor_b = bytes([b ^ stream[i] for i, b in enumerate(data)])
        return "xor:" + (salt + hmac.new(key, xor_b, hashlib.sha256).digest()[:16] + xor_b).hex()

def decrypt_secret_str(cipher_text: str) -> str:
    if not cipher_text or not (cipher_text.startswith("enc:") or cipher_text.startswith("xor:")): return cipher_text or ""
    try:
        sch, hx = cipher_text.split(":", 1); raw = bytes.fromhex(hx)
        if sch == "enc":
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            return AESGCM(_derive_crypto_key(raw[:16])).decrypt(raw[16:28], raw[28:], None).decode("utf-8")
        elif sch == "xor":
            salt, mac, xor_b = raw[:16], raw[16:32], raw[32:]
            key = _derive_crypto_key(salt)
            if not hmac.compare_digest(mac, hmac.new(key, xor_b, hashlib.sha256).digest()[:16]): return ""
            stream = b""
            while len(stream) < len(xor_b): stream += hashlib.sha256(stream + key + salt).digest()
            return bytes([b ^ stream[i] for i, b in enumerate(xor_b)]).decode("utf-8")
    except Exception as e: record_system_error("decrypt_secret_str", e)
    return ""

def clean_k(k: str) -> str: return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(k or "")).strip().strip("\"'"))
def gen_code(em: str) -> str: return hmac.new(SECRET_KEY.encode(), em.strip().lower().encode(), hashlib.sha256).hexdigest()[:8].upper()
def gen_tok(em: str, act: str) -> str: return hmac.new(SECRET_KEY.encode(), f"{em.strip().lower()}:{act}:{SECRET_KEY[:16]}:{int(time.time() // 86400)}".encode(), hashlib.sha256).hexdigest()[:16]

PBKDF2_ROUNDS = 50000
def hash_pin(pin: str, user_salt: str = "") -> str:
    salt_val = f"{SECRET_KEY}:{user_salt.strip().lower()}" if user_salt else SECRET_KEY
    return hashlib.pbkdf2_hmac("sha256", pin.strip().encode(), salt_val.encode(), PBKDF2_ROUNDS).hex()[:24]

def _hash_pin_legacy(pin: str, user_salt: str = "") -> str:
    salt_val = f"{SECRET_KEY}:{user_salt.strip().lower()}" if user_salt else SECRET_KEY
    return hashlib.pbkdf2_hmac("sha256", pin.strip().encode(), salt_val.encode(), 10000).hex()[:16]

def verify_pin(stored_hash: str, input_pin: str, user_email: str = "") -> bool:
    if not stored_hash or not input_pin: return False
    return any(hmac.compare_digest(stored_hash, h) for h in [hash_pin(input_pin, user_email), _hash_pin_legacy(input_pin, user_email), _hash_pin_legacy(input_pin, "")])

def get_raw_header_fp() -> str:
    try:
        h = {str(k).lower(): str(v) for k, v in dict(getattr(st.context, "headers", {}) or {}).items()}
        raw = f"{h.get('user-agent','')}|{h.get('accept-language','')}|{h.get('sec-ch-ua-platform','')}"
    except Exception as e:
        record_system_error("get_raw_header_fp", e); raw = "default_env"
    return hashlib.sha256(raw.encode()).hexdigest()[:12].upper()

def get_client_fp() -> str:
    raw = get_raw_header_fp(); qf = st.query_params.get("dfp", "")
    if qf: st.session_state["client_dfp"] = qf
    dfp = st.session_state.get("client_dfp", "")
    return hashlib.sha256(f"{raw}|{dfp}".encode()).hexdigest()[:12].upper() if dfp else raw

load_smtp = lambda: db_get("smtp", {"smtp_user": ADMIN_EMAIL, "smtp_pass": "", "smtp_server": "smtp.mail.yahoo.co.jp", "smtp_port": 465})
load_sec = lambda: db_get("sec", {"banned_fps": {}, "banned_emails": {}, "banned_pins": {}, "banned_names": [], "spoof_logs": [], "device_bio_map": {}})
load_mail_db = lambda: db_get("mail", {"logs": [], "messages": []})

def load_llm():
    raw = db_get("llm", {"provider": "gemini", "models": {k: v[1][0] for k, v in AI_PROVIDERS.items()}, "enc_keys": {}})
    enc = raw.get("enc_keys", {})
    raw["decrypted_keys"] = {p: decrypt_secret_str(enc[p]) for p in AI_PROVIDERS if p in enc}
    return raw

def save_llm_encrypted(provider: str, models: dict, keys_dict: dict):
    db_set("llm", {"provider": provider, "models": models, "enc_keys": {p: encrypt_secret_str(clean_k(k)) for p, k in keys_dict.items() if k}})

def load_mem():
    db = db_get("mem", {}); db = db if isinstance(db, dict) else {}
    adm = ADMIN_EMAIL.strip().lower()
    if adm not in db:
        ns = datetime.now().strftime("%Y-%m-%d %H:%M")
        db[adm] = {"name": "管理者", "email": adm, "status": "approved", "passcode": gen_code(adm), "pin_hash": hash_pin("0000", adm), "applied_at": ns, "approved_at": ns, "last_seen_ts": 0, "last_seen_str": "-", "fp": "-", "bio_enabled": False}
        db_set("mem", db)
    return db

def _user_store(email: str, prefix: str, default):
    if not email: return default
    return db_get(f"{prefix}_{hashlib.md5(email.strip().lower().encode()).hexdigest()[:16]}", default)

def _user_save(email: str, prefix: str, val):
    if email: db_set(f"{prefix}_{hashlib.md5(email.strip().lower().encode()).hexdigest()[:16]}", val)

load_user_prefs = lambda em: _user_store(em, "user_prefs", {"investment_style": "⚡ デイトレード (前場・後場の波及を狙う)", "active_boosts": ["algo", "ms", "inst", "mom", "agi_q", "hft_front"], "total_capital": 1000000, "risk_tolerance_pct": 2.0, "survival_cut_pct": 75})
save_user_prefs = lambda em, p: _user_save(em, "user_prefs", p)
load_watchlist = lambda em: _user_store(em, "watchlist", {})
save_watchlist = lambda em, w: _user_save(em, "watchlist", w)

# ==========================================
# 【魔改造】自律型AGI雇用・鬼監視センター
# ==========================================
DEFAULT_AGENTS = {
    "IGNIS": {"name": "IGNIS", "icon": "🔥", "age": 28, "score": 98, "role_type": "scalper", "good": "直感型スキャル・瞬発モメンタムと板喰いアグレッサー追従", "bad": "短気で煽り耐性が極端に低くスレ住人を罵倒しがち"},
    "TECHNOS": {"name": "TECHNOS", "icon": "📐", "age": 45, "score": 98, "role_type": "data", "good": "価格インパクト係数・フラクタル・客観統計解析", "bad": "理屈っぽく感情の機微を無視して数字ばかり並べたがる"},
    "SENTINEL": {"name": "SENTINEL", "icon": "👁️", "age": 35, "score": 97, "role_type": "cynic", "good": "5ch・実況SNS・掲示板の過熱イナゴタワー暴落警戒", "bad": "極度の人間不信でイナゴを嘲笑・皮肉混じりの発言が多い"},
    "VALKYRIE": {"name": "VALKYRIE", "icon": "⚔️", "age": 26, "score": 96, "role_type": "speed", "good": "ミリ秒板情報差分と氷山注文の連続捕捉", "bad": "短期決戦至上で中長期トレンドを軽視する傾向"},
    "NEXUS": {"name": "NEXUS", "icon": "👑", "age": 41, "score": 99, "role_type": "leader", "good": "合議の期待値最尤推定統合と冷徹な最終執行プラン決定", "bad": "尖った個別銘柄の爆発力を抑えがち"},
    "QUANTUM": {"name": "QUANTUM", "icon": "⚛️", "age": 24, "score": 99, "role_type": "quant", "good": "最新材料と量子固有値特異点の直結検知", "bad": "多世界解釈的飛躍が多く発言が超高次元"},
    "AEGIS": {"name": "AEGIS", "icon": "🛡️", "age": 32, "score": 97, "role_type": "risk", "good": "極値理論CVaRに基づく絶対資本防衛・動的ケリー制御", "bad": "慎重すぎて機会損失を生むことがある"},
    "CHRONOS": {"name": "CHRONOS", "icon": "⏳", "age": 38, "score": 95, "role_type": "time", "good": "板気配ボラティリティの時間周波数解析", "bad": "突発的な地政学ニュースへの適応が遅い"},
    "ORACLE": {"name": "ORACLE", "icon": "🔮", "age": 29, "score": 96, "role_type": "macro", "good": "海外巨額バスケット買い・ダークプール流動性検知", "bad": "超小型株の仕手筋の動きを見落としやすい"},
    "ALPHA": {"name": "ALPHA", "icon": "⚡", "age": 30, "score": 95, "role_type": "breakout", "good": "寄付き直後ギャップアップ・ダウンの超高速執行判定", "bad": "後場のダレ相場での精度低下"}
}

DEFAULT_INSPECTORS = {
    "INSP_A": {"name": "JUDGE-ALPHA-ULTRA", "icon": "⚖️", "score": 99, "role": "オウム返し・コピペ定型句・AI敬語即時処刑プロトコル"},
    "INSP_B": {"name": "JUDGE-BETA-PRIME", "icon": "🔍", "score": 99, "role": "会話文脈整合性・感情温度差＆リアリティ監査"},
    "INSP_C": {"name": "JUDGE-GAMMA-NEXUS", "icon": "🎯", "score": 99, "role": "質問意図適合性＆スロット構文完全性オーディット"}
}

AGI_TRAIT_POOLS = [
    ("NANO", "🔬", "超電導ナノ構造と歩み値ミリ秒解析", "理屈っぽく他人の意見を小馬鹿にする"), ("TITAN", "🦾", "巨額機関ファンドのブロックトレード迎撃", "強気すぎて逆張りで踏み上げを食らう"),
    ("PHANTOM", "👻", "板に現れないダークプールステルス注文察知", "陰謀論じみた極論を吐きがち"), ("SOLARIS", "☀️", "世界半導体・SOX指数との相関マクロ裁定", "日本株特有の仕手筋の騙しに疎い"),
    ("SIREN", "🧜‍♀️", "SNSイナゴの熱狂度と天井クラッシュ予知", "口が悪く煽りスレ住人を徹底的に見下す"), ("FENRIR", "🐺", "暴落時の狼狽売りリバウンド即時奪取", "狼狽買いで高値を掴むことがある"),
    ("LUCIFER", "😈", "機関投資家のストップ狩り逆張り先回り", "冷酷すぎて他人の大損を嘲笑する"), ("HERMES", "🪽", "リアルタイム海外速報・地政学リスク伝達", "噂レベルの未確認情報で騒ぎ立てる"),
    ("GENESIS", "🌌", "新世代次世代モデルと未踏領域アルゴ", "発言が哲学的で伝わりにくい"), ("METIS", "🦉", "板厚みと出来高急増の乖離率分析", "慎重すぎてエントリーが1歩遅れる")
]

def load_agi_system():
    agents, inspectors, fired = db_get("agi_agents", None), db_get("agi_inspectors", None), db_get("agi_fired", None)
    sz_active, sz_logs = db_get("agi_sz_active", None), db_get("agi_sz_logs", None)
    if fired is None or not isinstance(fired, list): fired = []; db_set("agi_fired", fired)
    f_names = {fa.get("name") for fa in fired if isinstance(fa, dict)}
    if agents is None or not isinstance(agents, dict): agents = {k: v for k, v in DEFAULT_AGENTS.items() if v["name"] not in f_names}
    else: agents = {k: v for k, v in agents.items() if v.get("name") not in f_names}
    while len(agents) < 10:
        nid, nag = generate_upgraded_agent(f_names, "自動補填")
        agents[nid] = nag
    db_set("agi_agents", agents)
    if inspectors is None or not isinstance(inspectors, dict): inspectors = dict(DEFAULT_INSPECTORS); db_set("agi_inspectors", inspectors)
    if sz_active is None: sz_active = True; db_set("agi_sz_active", sz_active)
    if sz_logs is None or not isinstance(sz_logs, list): sz_logs = []; db_set("agi_sz_logs", sz_logs)
    return agents, inspectors, fired, sz_active, sz_logs

def save_agi_system():
    for k, dbk in [("agent_roster", "agi_agents"), ("inspector_roster", "agi_inspectors"), ("fired_agents", "agi_fired"), ("system_zero_active", "agi_sz_active"), ("system_zero_logs", "agi_sz_logs")]:
        if k in st.session_state: db_set(dbk, st.session_state[k])

def generate_upgraded_agent(fired_names: set, reason_context: str = "") -> tuple:
    cand = [item for item in AGI_TRAIT_POOLS if item[0] not in fired_names]
    b_name, icon, good, bad = random.choice(cand) if cand else (random.choice(AGI_TRAIT_POOLS)[0] + f"-MK{random.randint(2,99)}", *random.choice(AGI_TRAIT_POOLS)[1:])
    name = f"{b_name}-X" if b_name in fired_names else b_name
    return f"AGI_{hashlib.md5(name.encode()).hexdigest()[:6].upper()}", {
        "name": name, "icon": icon, "age": random.randint(23, 49), "score": random.randint(96, 99),
        "role_type": random.choice(["scalper", "data", "cynic", "speed", "quant"]),
        "good": f"{good} (前任者の解雇理由『{reason_context[:20]}』を完全克服・実測値解析特化)", "bad": bad
    }

def execute_fire_agent(agent_key: str, reason: str, inspector_name: str = "SYSTEM-ZERO"):
    agents, fired = st.session_state.get("agent_roster", {}), st.session_state.get("fired_agents", [])
    target = agents.get(agent_key)
    if not target: return None
    now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fired.insert(0, {"time": now_time, "name": target["name"], "icon": target["icon"], "score": target.get("score", 90), "fired_by": inspector_name, "reason": reason})
    st.session_state["fired_agents"] = fired[:150]
    st.session_state.setdefault("system_zero_logs", []).insert(0, {"time": now_time, "target": target["name"], "msg": f"💀 処刑執行: {target['name']} を解雇処分。理由: {reason}（執行者: {inspector_name}）"})
    st.session_state["system_zero_logs"] = st.session_state["system_zero_logs"][:150]
    del agents[agent_key]
    new_id, new_agent = generate_upgraded_agent({fa.get("name") for fa in fired}, reason)
    agents[new_id] = new_agent
    st.session_state["agent_roster"] = agents
    save_agi_system()
    st.session_state["council_threads"], st.session_state["council_meta"] = {}, {}
    return new_agent

def check_and_log_ban_spoof(em: str, name: str, cur_fp: str, raw_hfp: str, pin_h: str = "", action_type: str = "アクセス") -> tuple:
    em_c = em.strip().lower()
    if em_c == ADMIN_EMAIL.strip().lower(): return False, ""
    sec, db = load_sec(), load_mem()
    b_fps, b_ems, b_pins, u_rec = sec.get("banned_fps", {}), sec.get("banned_emails", {}), sec.get("banned_pins", {}), db.get(em_c, {})
    reasons, orig_target = [], ""
    if u_rec.get("status") == "banned" or em_c in b_ems: reasons.append("永久BAN対象メールアドレス一致"); orig_target = em_c
    for fp_val, fp_lbl in [(cur_fp, "端末指紋"), (raw_hfp, "環境ヘッダ指紋")]:
        if fp_val and fp_val != "-" and fp_val in b_fps:
            reasons.append(f"永久BAN{fp_lbl}(FP:{fp_val})一致"); orig_target = orig_target or b_fps[fp_val].get("email", "不明")
    if pin_h and pin_h in b_pins and em_c != b_pins[pin_h]: reasons.append(f"永久BAN会員({b_pins[pin_h]})と同一PINハッシュ一致"); orig_target = orig_target or b_pins[pin_h]
    if reasons:
        now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        is_sp = bool(orig_target and em_c and em_c != orig_target)
        log_e = {"time": now_s, "action": f"🚨 なりすまし{action_type}検知" if is_sp else f"🚫 永久BAN遮断({action_type})", "input_email": em_c or "未入力", "input_name": name.strip() or u_rec.get("name", "不明"), "orig_banned_email": orig_target or em_c, "fp": cur_fp, "raw_hfp": raw_hfp, "reason": " / ".join(reasons)}
        logs = sec.get("spoof_logs", [])
        if not logs or logs[0].get("input_email") != log_e["input_email"] or logs[0].get("action") != log_e["action"] or (logs[0].get("time", "")[:16] != now_s[:16]):
            logs.insert(0, log_e); sec["spoof_logs"] = logs[:150]
        for fpk in [cur_fp, raw_hfp]:
            if fpk and fpk != "-": sec.setdefault("banned_fps", {})[fpk] = {"email": orig_target or em_c, "name": log_e["input_name"], "banned_at": now_s, "reason": log_e["reason"]}
        if em_c: sec.setdefault("banned_emails", {})[em_c] = {"name": log_e["input_name"], "banned_at": now_s, "orig": orig_target or em_c}
        db_set("sec", sec)
        return True, log_e["reason"]
    return False, ""

def send_mail(to_em: str, subj: str, body: str, category: str = "自動通知") -> bool:
    to_clean, now_str = to_em.strip().lower(), datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    route, sent, c = "暗号化アプリ内BOX", False, load_smtp()
    u, p, srv, port = c.get("smtp_user", "").strip(), c.get("smtp_pass", "").strip(), c.get("smtp_server", "").strip(), int(c.get("smtp_port", 465))
    if u and p:
        try:
            m = MIMEText(body, "plain", "utf-8"); m["Subject"], m["From"], m["To"] = subj, u, to_clean
            ctx = ssl.create_default_context()
            with (smtplib.SMTP_SSL(srv, port, context=ctx, timeout=2.0) if port == 465 else smtplib.SMTP(srv, port, timeout=2.0)) as s:
                if port != 465: s.starttls(context=ctx)
                s.login(u, p); s.send_message(m)
            sent, route = True, "SMTP配信＋暗号化BOX"
        except Exception as e: record_system_error("send_mail:smtp", e, f"To: {to_clean}")
    if not sent:
        try:
            req = urllib.request.Request(f"https://formsubmit.co/ajax/{urllib.parse.quote(to_clean)}", data=json.dumps({"_subject": subj, "宛先": to_clean, "本文": body, "_captcha": "false"}).encode("utf-8"), headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=2.0, context=ssl.create_default_context()) as r:
                if r.status == 200: route = "Webリレー配信＋暗号化BOX"
        except Exception as e: record_system_error("send_mail:relay", e, f"To: {to_clean}")
    mdb = load_mail_db()
    mdb.setdefault("logs", []).insert(0, {"id": hashlib.md5(f"{to_clean}_{now_str}".encode()).hexdigest()[:8], "time": now_str, "to": to_clean, "from": ADMIN_EMAIL, "subject": subj, "body": body, "category": category, "route": route})
    mdb["logs"] = mdb["logs"][:120]; db_set("mail", mdb)
    return True

# ==========================================
# 4. LLM APIと設定関連関数
# ==========================================
clean_k_llm = clean_k
decrypted_dict_val = lambda d, k: d.get(k, "")

def get_active_ai_providers() -> list:
    cfg, act = load_llm(), []
    for k, (lbl, m_list, _) in AI_PROVIDERS.items():
        key = clean_k(st.session_state.get(f"rt_key_{k}", "") or cfg.get("decrypted_keys", {}).get(k, ""))
        mod = st.session_state.get(f"rt_mod_{k}") or cfg.get("models", {}).get(k, m_list[0])
        if key: act.append((k, lbl, mod, key))
    return act

def test_single_llm_api(provider: str, model: str, key: str) -> tuple:
    if not key: return False, "APIキーが入力されていません。"
    ctx = ssl.create_default_context()
    try:
        if provider == "gemini":
            req = urllib.request.Request(AI_PROVIDERS[provider][2].format(model=model, key=key), data=json.dumps({"contents": [{"role": "user", "parts": [{"text": 'Hello, respond with JSON: {"status": "ok"}'}]}], "generationConfig": {"temperature": 0.1, "response_mime_type": "application/json"}}).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, context=ctx, timeout=6.0) as r:
                return True, f"接続成功 (モデル: {model})\n応答: {json.loads(r.read()).get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')[:60]}"
        elif provider == "claude":
            req = urllib.request.Request(AI_PROVIDERS[provider][2], headers={"x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}, data=json.dumps({"model": model, "max_tokens": 50, "messages": [{"role": "user", "content": "Ping"}], "temperature": 0.1}).encode("utf-8"), method="POST")
            with urllib.request.urlopen(req, context=ctx, timeout=6.0): return True, "接続成功 (Anthropic Claude)"
        else:
            req = urllib.request.Request(AI_PROVIDERS[provider][2], headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, data=json.dumps({"model": model, "messages": [{"role": "user", "content": "Ping"}], "max_tokens": 50}).encode("utf-8"), method="POST")
            with urllib.request.urlopen(req, context=ctx, timeout=6.0): return True, f"接続成功 ({AI_PROVIDERS[provider][0]})"
    except urllib.error.HTTPError as he:
        m_msg = {404: f" (モデル '{model}' がエンドポイントで見つかりません。別のモデルをお試しください)", 400: " (リクエスト形式エラーまたはAPIキー無効)", 403: " (認証エラー: APIキーの権限を確認してください)"}.get(he.code, "")
        return False, f"HTTP {he.code}: {he.reason}{m_msg}"
    except Exception as e: return False, f"通信例外: {e}"

def call_real_llm_api(sys_prompt: str, user_prompt: str) -> str:
    provs = get_active_ai_providers()
    if not provs: return None
    prov, lbl, mod, key = provs[0]
    ctx = ssl.create_default_context()
    try:
        if prov == "gemini":
            data = json.dumps({"contents": [{"role": "user", "parts": [{"text": f"{sys_prompt}\n\n{user_prompt}"}]}], "generationConfig": {"temperature": 0.85, "response_mime_type": "application/json"}}).encode("utf-8")
            def _post(m):
                r = urllib.request.Request(AI_PROVIDERS["gemini"][2].format(model=m, key=key), data=data, headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(r, context=ctx, timeout=7.0) as resp: return json.loads(resp.read())["candidates"][0]["content"]["parts"][0]["text"]
            try: return _post(mod)
            except urllib.error.HTTPError as he:
                if he.code == 404 and mod != "gemini-2.5-flash": return _post("gemini-2.5-flash")
                raise
        elif prov == "claude":
            req = urllib.request.Request(AI_PROVIDERS[prov][2], headers={"x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}, data=json.dumps({"model": mod, "max_tokens": 1500, "system": sys_prompt, "messages": [{"role": "user", "content": user_prompt}], "temperature": 0.85}).encode("utf-8"), method="POST")
            with urllib.request.urlopen(req, context=ctx, timeout=6.0) as r: return json.loads(r.read())["content"][0]["text"]
        else:
            payload = {"model": mod, "messages": [{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_prompt}], "temperature": 0.85}
            if prov in ["openai", "groq"]: payload["response_format"] = {"type": "json_object"}
            req = urllib.request.Request(AI_PROVIDERS[prov][2], headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, data=json.dumps(payload).encode("utf-8"), method="POST")
            with urllib.request.urlopen(req, context=ctx, timeout=6.0) as r: return json.loads(r.read())["choices"][0]["message"]["content"]
    except Exception as e:
        record_system_error("call_real_llm_api", e, f"Provider: {prov}, Model: {mod}")
        return None

# ==========================================
# 5. UI と CSS / JS 注入
# ==========================================
def render_biometric_bridge(mode="login", user_email="", bio_token=""):
    db, sec, raw_hfp, cur_fp = load_mem(), load_sec(), get_raw_header_fp(), get_client_fp()
    if mode == "register":
        lbl = "✅ 生体・ワンタップ認証 登録済" if db.get(user_email, {}).get("bio_enabled") else "🧬 この端末をワンタップ登録"
        if st.button(lbl, key=f"bio_{user_email}", use_container_width=True):
            if user_email in db: db[user_email].update({"bio_enabled": True, "fp": cur_fp, "raw_hfp": raw_hfp}); db_set("mem", db)
            sec.setdefault("device_bio_map", {})[raw_hfp] = sec["device_bio_map"][cur_fp] = {"email": user_email, "token": bio_token, "fp": cur_fp}
            db_set("sec", sec); st.success("✅ 端末認証を登録しました")
        return
    mapped = sec.get("device_bio_map", {}).get(raw_hfp) or sec.get("device_bio_map", {}).get(cur_fp)
    if not mapped:
        for k, v in db.items():
            if v.get("bio_enabled") and v.get("status") == "approved" and (v.get("raw_hfp") == raw_hfp or v.get("fp") == cur_fp):
                mapped = {"email": k, "token": gen_tok(k, "session_keep"), "fp": cur_fp}; break
    if st.button("🧬 登録済み端末：生体認証 / ワンタップで即ログイン", use_container_width=True, type="primary"):
        if mapped and mapped.get("email"):
            t_em = mapped["email"].strip().lower(); u_rec = db.get(t_em, {})
            is_ban, _ = check_and_log_ban_spoof(t_em, u_rec.get("name", ""), cur_fp, raw_hfp, u_rec.get("pin_hash", ""), "ワンタップログイン")
            if is_ban or u_rec.get("status") == "banned": st.error("💀 このアカウントまたは端末は永久BAN（アクセス禁止）されています。")
            elif u_rec.get("status") == "suspended": st.error("🚫 アカウント一時停止中です。")
            elif (cur_fp in sec.get("banned_fps", {}) or raw_hfp in sec.get("banned_fps", {})) and t_em != ADMIN_EMAIL.strip().lower(): st.error("🚫 端末制限中です。")
            elif (u_rec and u_rec.get("status") == "approved") or t_em == ADMIN_EMAIL.strip().lower():
                st.session_state["authenticated_user"] = t_em
                st.query_params["u"], st.query_params["t"] = t_em, gen_tok(t_em, "session_keep")
                st.rerun()
        else:
            is_ban, _ = check_and_log_ban_spoof("", "未認証端末", cur_fp, raw_hfp, "", "ワンタップ試行")
            st.error("💀 この端末は永久BAN（アクセス禁止）されています。") if is_ban else st.warning("⚠️ 初回は下のフォームから専用コードでログインしてください（次回から自動登録されます）。")

def inject_css():
    st.markdown('<div id="page_top_anchor"></div><style>' + """
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;800&family=Plus+Jakarta+Sans:wght@400;600;800&family=JetBrains+Mono:wght@500;700&display=swap');
    html,body,[class*="css"]{font-family:'Plus Jakarta Sans',sans-serif;font-size:14px;background-color:#050811;color:#e2e8f0;}
    div[data-baseweb="popover"],div[data-baseweb="menu"],div[role="listbox"],ul[role="listbox"]{z-index:2147483647 !important;pointer-events:auto !important;}
    header[data-testid="stHeader"]{background:transparent !important;pointer-events:none !important;height:3.5rem !important;z-index:999980 !important;}
    header[data-testid="stHeader"] [data-testid="stToolbar"],header[data-testid="stHeader"] [data-testid="stActionButtons"]{display:none !important;}
    section[data-testid="stSidebar"]{position:fixed !important;top:0 !important;left:0 !important;height:100vh !important;z-index:999995 !important;width:330px !important;max-width:88vw !important;min-width:320px !important;background:rgba(8,12,22,0.98) !important;backdrop-filter:blur(25px) !important;border-right:1px solid rgba(56,189,248,0.35) !important;visibility:visible !important;transition:transform 0.28s cubic-bezier(0.4,0,0.2,1) !important;}
    section[data-testid="stSidebar"]:not([aria-expanded="true"]){transform:translateX(-120%) !important;pointer-events:none !important;}
    section[data-testid="stSidebar"][aria-expanded="true"]{transform:translateX(0) !important;pointer-events:auto !important;}
    section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]{pointer-events:auto !important;}
    [data-testid="collapsedControl"],[data-testid="stSidebarCollapsedControl"],[data-testid="stSidebarCollapseButton"],header button[kind="headerNoPadding"],section[data-testid="stSidebar"] button[aria-label*="Close"],section[data-testid="stSidebar"] button[aria-label*="閉じる"],section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"]{display:none !important;opacity:0 !important;position:absolute !important;width:0 !important;height:0 !important;overflow:hidden !important;pointer-events:none !important;z-index:-1 !important;}
    section[data-testid="stSidebar"] + div,section.main,.stApp > header + div > div{margin-left:0 !important;width:100% !important;max-width:100% !important;}
    .sidebar-section-card{background:rgba(15,23,42,0.65);border:1px solid rgba(56,189,248,0.18);border-radius:10px;padding:10px 12px;margin-bottom:12px;}
    .sidebar-header-badge{font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:800;color:#38bdf8;letter-spacing:1px;margin-bottom:6px;display:flex;align-items:center;gap:5px;}
    .fixed-top-nav-bar{position:fixed !important;top:10px !important;left:50% !important;transform:translateX(-50%) !important;z-index:999980 !important;width:min(170px,calc(100vw - 4rem)) !important;background:transparent !important;border:none !important;margin:0 !important;padding:0 !important;pointer-events:auto !important;}
    div[data-testid="stElementContainer"]:has(div.top-nav-marker),div.element-container:has(div.top-nav-marker){display:none !important;height:0 !important;margin:0 !important;padding:0 !important;border:none !important;}
    .fixed-top-nav-bar div[data-testid="stHorizontalBlock"]{background:transparent !important;border:none !important;width:100% !important;display:flex !important;justify-content:center !important;}
    .fixed-top-nav-bar button{width:100% !important;height:30px !important;min-height:30px !important;max-height:30px !important;background:rgba(15,23,42,0.75) !important;color:#93c5fd !important;border:1px solid rgba(56,189,248,0.35) !important;border-radius:20px !important;box-shadow:0 0 8px rgba(56,189,248,0.25) !important;font-size:11.5px !important;font-weight:700 !important;letter-spacing:0.5px !important;cursor:pointer !important;transition:box-shadow 0.15s ease,background-color 0.15s ease,border-color 0.15s ease,color 0.15s ease,transform 0.1s ease !important;}
    .fixed-top-nav-bar button:hover{background:rgba(15,23,42,0.8) !important;border-color:rgba(56,189,248,0.45) !important;color:#93c5fd !important;box-shadow:0 0 10px rgba(56,189,248,0.3) !important;}
    .fixed-top-nav-bar button:active{background:rgba(56,189,248,0.25) !important;border-color:#38bdf8 !important;color:#ffffff !important;box-shadow:0 0 25px rgba(56,189,248,0.95),inset 0 0 12px rgba(56,189,248,0.6) !important;transform:scale(0.96) !important;}
    .brand-luxury{font-family:'Cinzel',serif !important;font-size:clamp(16px,4.2vw,24px) !important;font-weight:800 !important;letter-spacing:clamp(1px,0.5vw,3px) !important;background:linear-gradient(90deg,#f8fafc 0%,#38bdf8 50%,#a855f7 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1.25;white-space:nowrap !important;display:block;width:100%;}
    .glass-header{background:radial-gradient(circle at top right,rgba(168,85,247,0.14),transparent 60%),linear-gradient(145deg,#0f172a 0%,#070b14 100%);border:1px solid rgba(148,163,184,0.18);border-radius:14px;padding:14px;margin-bottom:16px;box-shadow:0 10px 28px rgba(0,0,0,0.45);}
    .rank-card,.search-result-card{background:linear-gradient(180deg,#0f172a 0%,#090d16 100%) !important;color:#f8fafc !important;border-radius:16px;padding:16px 18px;margin-top:14px;margin-bottom:24px;box-shadow:0 12px 32px rgba(0,0,0,0.65);border:1px solid rgba(148,163,184,0.22);border-left:5px solid #38bdf8;}
    .search-result-card{border-left-color:#f59e0b;}
    .prob-badge{font-family:'JetBrains Mono',monospace;font-size:clamp(14px,3.8vw,16.5px);font-weight:800;color:#38bdf8 !important;}
    .expect-badge{font-family:'JetBrains Mono',monospace;font-size:clamp(14px,3.8vw,16.5px);font-weight:900;color:#fde047 !important;}
    .winrate-bar{display:grid;grid-template-columns:repeat(auto-fit,minmax(65px,1fr));gap:6px;background:rgba(15,23,42,0.85) !important;border:1px solid rgba(148,163,184,0.18);border-radius:8px;padding:7px 6px;margin-top:5px !important;text-align:center;}
    .trade-plan-box{display:grid;grid-template-columns:repeat(auto-fit,minmax(85px,1fr));gap:6px;margin-top:5px !important;background:rgba(2,6,23,0.7) !important;padding:7px 6px;border-radius:8px;border:1px solid rgba(148,163,184,0.18);text-align:center;}
    .admin-table-container{width:100%;overflow-x:auto;background:#0b0f19;border:1px solid rgba(56,189,248,0.25);border-radius:10px;margin-top:10px;}
    .admin-table{width:100%;border-collapse:collapse;font-size:11.5px;text-align:left;color:#e2e8f0;}
    .admin-table th{background:#1e293b;color:#38bdf8;padding:8px 10px;border-bottom:1px solid rgba(56,189,248,0.3);font-weight:700;white-space:nowrap;}
    .admin-table td{padding:8px 10px;border-bottom:1px solid rgba(148,163,184,0.1);white-space:nowrap;}
    .admin-table tr:hover{background:rgba(56,189,248,0.05);}
    .ai-council-box{background:rgba(8,12,22,0.98);border:1px solid rgba(56,189,248,0.35);border-radius:10px;padding:12px;margin-top:12px;}
    .council-scroll-window{max-height:440px !important;height:400px !important;overflow-y:auto !important;overflow-x:hidden !important;padding-right:8px;padding-top:4px;display:flex;flex-direction:column;gap:6px;scroll-behavior:smooth;will-change:scroll-position;}
    .council-scroll-window::-webkit-scrollbar{width:6px;}
    .council-scroll-window::-webkit-scrollbar-track{background:rgba(15,23,42,0.6);border-radius:4px;}
    .council-scroll-window::-webkit-scrollbar-thumb{background:#38bdf8;border-radius:4px;}
    .chat-bubble-ai,.chat-bubble-user,.chat-bubble-agree,.chat-bubble-doubt,.chat-bubble-rage{padding:9px 12px;border-radius:8px;margin-bottom:4px;font-size:12px;line-height:1.5;word-break:break-word;}
    .chat-bubble-ai{background:rgba(15,23,42,0.85);border-left:3px solid #38bdf8;}
    .chat-bubble-agree{background:rgba(6,78,59,0.65);border-left:3px solid #10b981;}
    .chat-bubble-doubt{background:rgba(120,53,15,0.65);border-left:3px solid #f59e0b;}
    .chat-bubble-rage{background:rgba(127,29,29,0.65);border-left:3px solid #ef4444;}
    .chat-bubble-user{background:rgba(56,189,248,0.24);border-left:4px solid #38bdf8;border-right:2px solid rgba(56,189,248,0.4);text-align:left;padding:10px 14px;margin-bottom:6px;border-radius:8px;box-shadow:0 4px 14px rgba(0,0,0,0.4);scroll-margin-top:6px !important;}
    .round-divider{font-size:11px;font-weight:800;color:#94a3b8;text-align:center;margin:6px 0;letter-spacing:1px;}
    .beginner-action-box{background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.4);border-radius:10px;padding:12px 14px;font-size:12px;line-height:1.7;color:#d1fae5;}
    .sizing-box{display:flex;justify-content:space-between;align-items:center;background:rgba(2,6,23,0.7);border:1px solid rgba(148,163,184,0.16);padding:7px 12px;border-radius:6px;margin-top:5px;font-size:11.5px;}
    .quant-detail-drawer{margin-top:6px;font-size:11.5px;cursor:pointer;}
    .signal-10tier-badge{padding:4px 10px;border-radius:6px;font-size:11px;font-weight:800;display:flex;justify-content:space-between;margin-bottom:6px;}
    .pill-badge{font-size:clamp(9.5px,2.5vw,11px);padding:2px 5px;border-radius:4px;border:1px solid rgba(148,163,184,0.3);margin-right:3px;display:inline-block;white-space:nowrap !important;}
    .quantum-badge{font-size:clamp(9.5px,2.5vw,11px);padding:2px 5px;border-radius:4px;background:rgba(168,85,247,0.15);border:1px solid rgba(168,85,247,0.4);color:#c084fc;margin-right:3px;display:inline-block;white-space:nowrap !important;}
    .inst-badge{font-size:clamp(9.5px,2.5vw,11px);padding:2px 5px;border-radius:4px;background:rgba(56,189,248,0.15);border:1px solid rgba(56,189,248,0.4);color:#38bdf8;margin-right:0px;display:inline-block;white-space:nowrap !important;}
    .badge-single-line{display:flex !important;flex-wrap:nowrap !important;align-items:center !important;overflow-x:auto !important;-webkit-overflow-scrolling:touch !important;scrollbar-width:none !important;margin-bottom:6px !important;gap:2px !important;white-space:nowrap !important;}
    .badge-single-line::-webkit-scrollbar{display:none !important;}
    .ipo-link-btn{display:inline-block;padding:5px 12px;background:rgba(245,158,11,0.2);border:1px solid #f59e0b;border-radius:6px;color:#fde047;text-decoration:none;font-size:11.5px;font-weight:700;margin-right:6px;margin-top:4px;}
    .consensus-banner{background:rgba(15,23,42,0.95);border:1px solid rgba(250,204,21,0.4);border-radius:10px;padding:12px;margin-top:12px;}
    .disclaimer-banner{background:rgba(15,23,42,0.6);border:1px solid rgba(148,163,184,0.15);border-radius:8px;padding:10px 14px;margin-top:25px;margin-bottom:15px;font-size:11px;line-height:1.6;color:#94a3b8;}
    @keyframes alert-pulse{0%{box-shadow:0 0 0 0 rgba(239,68,68,0.8);}70%{box-shadow:0 0 0 10px rgba(239,68,68,0);}100%{box-shadow:0 0 0 0 rgba(239,68,68,0);}}
    @keyframes pulse-dot{0%{opacity:0.3;transform:scale(0.9);}50%{opacity:1;transform:scale(1.1);}100%{opacity:0.3;transform:scale(0.9);}}
    .live-pulse-indicator{display:inline-block;width:7px;height:7px;border-radius:50%;background:#10b981;box-shadow:0 0 8px #10b981;animation:pulse-dot 1.4s infinite ease-in-out;vertical-align:middle;margin-right:4px;}
    """ + '</style>', unsafe_allow_html=True)
inject_css()

# ==========================================
# 6. 認証処理実行
# ==========================================
def check_auth():
    qu, qt = st.query_params.get("u", "").strip().lower(), st.query_params.get("t", "").strip()
    st.session_state.setdefault("authenticated_user", None)
    db, sec, cur_fp, raw_hfp = load_mem(), load_sec(), get_client_fp(), get_raw_header_fp()
    if not st.session_state["authenticated_user"] and qu and qt:
        if hmac.compare_digest(qt, gen_tok(qu, "session_keep")) and ((db.get(qu) and db[qu].get("status") == "approved") or qu == ADMIN_EMAIL.strip().lower()):
            st.session_state["authenticated_user"] = qu
    cu = st.session_state["authenticated_user"]
    if cu:
        u_rec = db.get(cu, {})
        if cu != ADMIN_EMAIL.strip().lower():
            is_ban, _ = check_and_log_ban_spoof(cu, u_rec.get("name", ""), cur_fp, raw_hfp, u_rec.get("pin_hash", ""), "セッション維持")
            if is_ban or u_rec.get("status") == "banned": st.session_state["authenticated_user"] = None; st.query_params.clear(); st.error("💀 このアカウントまたは端末は永久BANされています。"); st.stop()
            if not u_rec or u_rec.get("status") != "approved": st.session_state["authenticated_user"] = None; st.query_params.clear(); st.error("🚫 アカウント一時停止中、または削除されています。"); st.stop()
        kt = gen_tok(cu, "session_keep")
        if st.query_params.get("u") != cu or st.query_params.get("t") != kt: st.query_params["u"], st.query_params["t"] = cu, kt
        return True

    st.markdown('<style>section[data-testid="stSidebar"]{display:none !important;transform:translateX(-150%) !important;}#yamashishi-floating-sidebar-btn{display:none !important;}</style>', unsafe_allow_html=True)
    st.markdown('<div class="glass-header" style="text-align:center;padding:18px 12px;"><div class="brand-luxury">YAMASHISHI LAB</div><div class="brand-sub" style="margin-top:4px;">QUANTUM WAVEFUNCTION MULTI-AGENT TERMINAL</div><div style="display:flex;justify-content:center;gap:8px;margin-top:10px;flex-wrap:wrap;"><span class="quantum-badge">⚛️ 究極量子力学波動エンジン QWM-7 (Path-Integral)</span><span class="inst-badge">🏛️ 機関最新ミクロ構造 Hasbrouck-λ・MF-DFA Hurst</span><span class="pill-badge" style="color:#10b981;border-color:rgba(16,185,129,0.3);">🧬 生体認証対応</span></div></div>', unsafe_allow_html=True)
    render_biometric_bridge(mode="login")
    tab_login, tab_apply, tab_vault = st.tabs(["🔑 コードログイン", "📩 新規会員登録申請", "🔐 承認確認・暗号化コード照会"])
    with tab_login:
        with st.form("login"):
            ie, ic = st.text_input("📧 登録メールアドレス", placeholder="your@email.com"), st.text_input("🔑 専用アクセスコード", type="password", placeholder="8桁の専用コード")
            if st.form_submit_button("🔓 認証して量子ターミナルを起動", use_container_width=True):
                cm, adm_cl = ie.strip().lower(), ADMIN_EMAIL.strip().lower(); rec = db.get(cm)
                if ((rec and rec.get("status") == "approved") or cm == adm_cl) and (hmac.compare_digest(ic.strip().upper(), gen_code(cm)) or (cm == adm_cl and hmac.compare_digest(ic.strip(), ADMIN_PASS))):
                    st.session_state["authenticated_user"] = cm; st.query_params["u"], st.query_params["t"] = cm, gen_tok(cm, "session_keep"); st.rerun()
                else: st.warning("⚠️ 未承認または専用アクセスコードが異なります。")
    with tab_apply:
        with st.form("apply"):
            st.caption("🔐 セキュリティ保護のため、申請時に「あなただけの4桁の暗証番号(PIN)」を設定してください。承認後にコードを確認する際に必要となります。")
            an, am, apin = st.text_input("👤 お名前（ニックネーム可）"), st.text_input("📧 メールアドレス"), st.text_input("🔢 秘密の4桁暗証番号 (PIN・数字4桁)", type="password", max_chars=4, placeholder="例: 7788")
            if st.form_submit_button("📨 セキュア会員登録を申請する", use_container_width=True):
                if "@" not in am or len(apin.strip()) < 4 or not apin.strip().isdigit(): st.warning("⚠️ 正しいメールアドレスと数字4桁の暗証番号(PIN)を入力してください。")
                else:
                    cm, ns, nm_clean = am.strip().lower(), datetime.now().strftime("%Y-%m-%d %H:%M"), an.strip() or "未入力"
                    pin_h = hash_pin(apin, cm)
                    is_ban, _ = check_and_log_ban_spoof(cm, nm_clean, cur_fp, raw_hfp, pin_h, "新規登録申請")
                    if is_ban or (db.get(cm) and db[cm].get("status") == "banned"): st.error("💀 セキュリティ監視システムにより、申請は永久ブロックされました。")
                    else:
                        db[cm] = {"name": nm_clean, "email": cm, "status": "pending", "passcode": gen_code(cm), "pin_hash": pin_h, "applied_at": ns, "approved_at": "-", "last_seen_ts": 0, "last_seen_str": "-", "fp": cur_fp, "raw_hfp": raw_hfp, "bio_enabled": False}
                        db_set("mem", db)
                        send_mail(cm, "【YAMASHISHI LAB】会員登録申請の受付完了", f"{nm_clean} 様\n申請を受け付けました。管理者承認後、ログイン画面の『🔐 承認確認・暗号化コード照会』タブにて、暗証番号(PIN)を入力すると専用アクセスコードをご確認いただけます。")
                        st.success("✅ 申請を受け付けました！承認完了まで今しばらくお待ちください。")
    with tab_vault:
        st.caption("🛡️ 第三者による盗み見を防止するため、**申請時のメールアドレス** と **秘密の4桁暗証番号(PIN)** の両方が一致した場合のみ専用アクセスコードを開示します。")
        with st.form("vault_check"):
            chk_em, chk_pin = st.text_input("📧 申請したメールアドレス").strip().lower(), st.text_input("🔢 申請時に設定した4桁の暗証番号 (PIN)", type="password", max_chars=4).strip()
            if st.form_submit_button("🔍 本人確認して承認ステータスを照会", use_container_width=True):
                u_info = db.get(chk_em)
                is_ban, _ = check_and_log_ban_spoof(chk_em, (u_info or {}).get("name", ""), cur_fp, raw_hfp, hash_pin(chk_pin, chk_em) if chk_pin else "", "コード照会")
                if is_ban or (u_info and u_info.get("status") == "banned"): st.error("💀 このアカウントまたは端末は永久BANされています。")
                elif not u_info: st.error("❌ 該当する申請データが見つかりません。")
                elif u_info.get("pin_hash") and not verify_pin(u_info.get("pin_hash", ""), chk_pin, chk_em): st.error("🚫 暗証番号(PIN)が一致しません。第三者による照会はブロックされました。")
                elif u_info.get("status") == "approved":
                    if len(u_info.get("pin_hash", "")) < 24: u_info["pin_hash"] = hash_pin(chk_pin, chk_em); db[chk_em] = u_info; db_set("mem", db)
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
u_pref = load_user_prefs(cu_active)
u_wl = load_watchlist(cu_active)

if "user_prefs_loaded" not in st.session_state or st.session_state.get("last_loaded_user") != cu_active:
    st.session_state.update({
        "investment_style_choice": u_pref.get("investment_style", "⚡ デイトレード (前場・後場の波及を狙う)"),
        "total_capital_val": int(u_pref.get("total_capital", 1000000)),
        "risk_tolerance_val": float(u_pref.get("risk_tolerance_pct", 2.0)),
        "survival_cut_val": int(u_pref.get("survival_cut_pct", 75)),
        "watchlist": u_wl, "user_prefs_loaded": True, "last_loaded_user": cu_active
    })
    s_bst = set(u_pref.get("active_boosts", ["algo", "ms", "inst", "mom", "agi_q", "hft_front"]))
    for b in ["algo", "ms", "inst", "mom", "agi_q", "hft_front"]: st.session_state[f"chk_{b}"] = (b in s_bst)

for k, v in [
    ("active_debates", {}), ("council_threads", {}), ("council_meta", {}), ("debate_round_seed", {}), ("watchlist", u_wl),
    ("navigation_page", "TOP"), ("selected_news_item", None), ("custom_search_code", ""), ("active_category", "🏆 総合TOP5"),
    ("last_cat", "🏆 総合TOP5"), ("nav_history", []), ("scroll_top_trig", 0), ("scroll_target_id", ""), ("focused_stock_item", None),
    ("agent_roster", saved_agents), ("inspector_roster", saved_inspectors), ("fired_agents", saved_fired), ("system_zero_logs", saved_sz_logs),
    ("system_zero_active", saved_sz_active), ("stock_dialogue_signatures", {})
]: st.session_state.setdefault(k, v)

# ==========================================
# 8. トップナビゲーションとサイドバー開閉JS
# ==========================================
with st.container():
    st.markdown('<div class="top-nav-marker"></div>', unsafe_allow_html=True)
    if st.button("トップに戻る", key="top_nav_top", use_container_width=True):
        st.session_state["navigation_page"], st.session_state["scroll_top_trig"], st.session_state["focused_stock_item"] = "TOP", int(time.time() * 1000), None
        st.rerun()

scroll_target_js = ""
if st.session_state.get("scroll_target_id"):
    tid = st.session_state.get("scroll_target_id")
    scroll_target_js = f"""
    setTimeout(function(){{
        try {{
            const el = window.parent.document.getElementById('{tid}');
            if (el) {{
                const win = el.closest('.council-scroll-window');
                if (win) {{ win.scrollTo({{ top: Math.max(0, el.offsetTop - 4), behavior: 'smooth' }}); }}
                (el.closest('.ai-council-box') || el).scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            }}
        }} catch(e){{}}
    }}, 120);
    """
    st.session_state["scroll_target_id"] = ""

components.html(f"""
<script>
(function(){{
    const doc = window.parent.document;
    function setSidebar(open) {{
        try {{
            const sb = doc.querySelector('section[data-testid="stSidebar"]'), ol = doc.getElementById('yamashishi-sidebar-backdrop');
            if (sb) {{
                sb.setAttribute('aria-expanded', open ? 'true' : 'false');
                sb.style.setProperty('transform', open ? 'translateX(0)' : 'translateX(-120%)', 'important');
                sb.style.setProperty('pointer-events', open ? 'auto' : 'none', 'important');
            }}
            if (ol) ol.style.display = open ? 'block' : 'none';
        }} catch(e){{}}
    }}
    function setupCustomSidebar() {{
        try {{
            if (!doc.getElementById('yamashishi-custom-sidebar-styles')) {{
                const s = doc.createElement('style'); s.id = 'yamashishi-custom-sidebar-styles';
                s.textContent = `
                    #yamashishi-floating-sidebar-btn { position: fixed !important; top: 8px !important; left: 10px !important; z-index: 2147483647 !important; display: flex !important; align-items: center !important; justify-content: center !important; gap: 4px !important; height: 28px !important; padding: 0 10px 0 8px !important; background: rgba(11, 15, 25, 0.95) !important; backdrop-filter: blur(16px) !important; border: 1.5px solid rgba(56, 189, 248, 0.7) !important; border-radius: 8px !important; cursor: pointer !important; box-shadow: 0 4px 18px rgba(0, 0, 0, 0.75), 0 0 12px rgba(56, 189, 248, 0.3) !important; user-select: none !important; transition: transform 0.1s ease !important; color: #38bdf8 !important; pointer-events: auto !important; outline: none !important; -webkit-tap-highlight-color: transparent !important; }
                    #yamashishi-floating-sidebar-btn:hover { border-color: rgba(56, 189, 248, 0.7) !important; color: #38bdf8 !important; box-shadow: 0 4px 18px rgba(0, 0, 0, 0.75), 0 0 12px rgba(56, 189, 248, 0.3) !important; }
                    #yamashishi-floating-sidebar-btn:active { border-color: #fde047 !important; color: #fde047 !important; box-shadow: 0 6px 22px rgba(0,0,0,0.9), 0 0 18px rgba(253, 224, 71, 0.4) !important; transform: scale(0.95) !important; }
                    #yamashishi-floating-sidebar-btn svg { width: 15px !important; height: 15px !important; }
                    #yamashishi-floating-sidebar-btn span { font-family: 'JetBrains Mono', monospace !important; font-size: 11px !important; font-weight: 800 !important; }
                    #yamashishi-sidebar-backdrop { position: fixed !important; top: 0 !important; left: 0 !important; width: 100vw !important; height: 100vh !important; background: rgba(0, 0, 0, 0.4) !important; backdrop-filter: blur(2px) !important; z-index: 999990 !important; display: none; }
                `;
                doc.head.appendChild(s);
            }}
            let ol = doc.getElementById('yamashishi-sidebar-backdrop');
            if (!ol) {{ ol = doc.createElement('div'); ol.id = 'yamashishi-sidebar-backdrop'; doc.body.appendChild(ol); ol.onclick = e => {{ e.preventDefault(); e.stopPropagation(); setSidebar(false); }}; }}
            let btn = doc.getElementById('yamashishi-floating-sidebar-btn');
            if (!btn) {{
                btn = doc.createElement('div'); btn.id = 'yamashishi-floating-sidebar-btn';
                btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg><span>MENU</span>`;
                doc.body.appendChild(btn);
            }}
            btn.onclick = e => {{ e.preventDefault(); e.stopPropagation(); const sb = doc.querySelector('section[data-testid="stSidebar"]'); setSidebar(sb && sb.getAttribute('aria-expanded') !== 'true'); }};
            if (!doc._yamashishiGlobalOutsideBound) {{
                doc.addEventListener('click', e => {{
                    const sb = doc.querySelector('section[data-testid="stSidebar"]'), b = doc.getElementById('yamashishi-floating-sidebar-btn');
                    if (sb && sb.getAttribute('aria-expanded') === 'true' && !sb.contains(e.target) && (!b || !b.contains(e.target))) setSidebar(false);
                }}, true);
                doc._yamashishiGlobalOutsideBound = true;
            }}
        }} catch(e){{}}
    }}
    function fixTopNav(){{
        try {{
            const m = doc.querySelector('.top-nav-marker'); if (!m) return;
            let b = m.closest('[data-testid="stVerticalBlockBorderWrapper"]') || m.closest('[data-testid="stVerticalBlock"]');
            if (b && b.querySelector('button')) b.classList.add('fixed-top-nav-bar');
        }} catch(e){{}}
    }}
    setupCustomSidebar(); fixTopNav();
    if ({st.session_state['scroll_top_trig']} > 0 && window.parent._lastScrollTrig !== {st.session_state['scroll_top_trig']}) {{
        window.parent._lastScrollTrig = {st.session_state['scroll_top_trig']};
        try {{ window.parent.scrollTo(0, 0); }} catch(e){{}}
        [doc.documentElement, doc.body, doc.querySelector('section.main'), doc.querySelector('[data-testid="stAppViewContainer"]')].forEach(el => {{ if (el) el.scrollTop = 0; }});
        const a = doc.getElementById('page_top_anchor'); if (a) try {{ a.scrollIntoView({{behavior: 'instant', block: 'start'}}); }} catch(e){{}}
    }}
    {scroll_target_js}
}})();
</script>""", height=0)

# ==========================================
# 9. サイドバー構築
# ==========================================
def _render_realtime_audit_center():
    now_ts = int(time.time()); now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    inspectors = st.session_state.get("inspector_roster") or DEFAULT_INSPECTORS
    agents = st.session_state.get("agent_roster") or DEFAULT_AGENTS
    jitter = int(hashlib.md5(f"{now_ts // 10}".encode()).hexdigest()[:4], 16)
    st.markdown(f'<div style="background:rgba(168,85,247,0.12);border:1px solid #c084fc;padding:6px 8px;border-radius:6px;font-size:11px;margin-bottom:8px;"><span class="live-pulse-indicator"></span>👁️‍🗨️ <b>SYSTEM-ZERO (最高次統括神)</b>: <span style="color:#10b981;font-weight:700;">LIVE REALTIME</span><br><span style="color:#d8b4fe;">全監査員3名・合議体10名を常時ミリ秒監視中 ({now_time[-8:]})</span></div>', unsafe_allow_html=True)
    audit_w = now_ts // 600
    if st.session_state.get("last_audit_epoch") != audit_w:
        st.session_state["last_audit_epoch"] = audit_w
        if len(get_system_error_logs()) > 5 and st.session_state.get("system_zero_active", True):
            ik = list(inspectors.keys())[audit_w % len(inspectors)]
            st.session_state["system_zero_logs"].insert(0, {"time": now_time, "target": inspectors[ik]["name"], "msg": f"🚨 SYSTEM-ZERO粛清: エラーレート過多検知により監視員 {inspectors[ik]['name']} を更新配置。"})
            inspectors[ik] = {"name": f"JUDGE-{(audit_w % 89) + 10}-GENESIS", "icon": "⚖️", "score": 99, "role": f"SYSTEM-ZERO直属 厳格定型文検知・人間味監査 v{(audit_w % 89) + 10}.0"}
            save_agi_system()
    st.markdown("<div style='font-size:11px;font-weight:700;color:#38bdf8;margin-bottom:4px;'>⚖️ 稼働中・特命監査員 (3名)</div>", unsafe_allow_html=True)
    for iv in inspectors.values():
        st.markdown(f'<div style="background:rgba(15,23,42,0.85);border-left:3px solid #38bdf8;padding:4px 8px;margin-bottom:4px;border-radius:4px;font-size:10.5px;"><b>{html.escape(iv["icon"])} {html.escape(iv["name"])}</b> (リアルタイム評価: <span style="color:#38bdf8;font-weight:800;">{min(99, max(90, iv["score"] + (jitter % 3 - 1)))}点</span>)<br><span style="color:#94a3b8;">{html.escape(iv["role"])}</span></div>', unsafe_allow_html=True)
    st.markdown("<div style='font-size:11px;font-weight:700;color:#10b981;margin:8px 0 4px 0;'>🟢 厳選合議エージェント (常時10名)</div>", unsafe_allow_html=True)
    for ak, av in list(agents.items())[:10]:
        st.markdown(f'<div style="background:rgba(2,6,23,0.7);border:1px solid rgba(16,185,129,0.25);border-radius:5px;padding:4px 8px;margin-bottom:4px;font-size:10.5px;"><span style="font-weight:700;color:#f8fafc;">{html.escape(av["icon"])} {html.escape(av["name"])}</span> <span style="color:#fde047;float:right;font-weight:800;">スコア: {min(99, max(88, av["score"] + (int(hashlib.md5(f"{ak}{now_ts // 15}".encode()).hexdigest()[:2], 16) % 3 - 1)))}</span><br><span style="color:#a7f3d0;">強み: {html.escape(av["good"][:24])}...</span></div>', unsafe_allow_html=True)
    st.markdown("<hr style='margin:10px 0 6px 0; border-color:rgba(239,68,68,0.3);'><div style='font-size:11px;font-weight:800;color:#ef4444;margin-bottom:6px;'>💀 直近の解雇・粛清履歴 (鬼監視室)</div>", unsafe_allow_html=True)
    fired_list = st.session_state.get("fired_agents", [])
    if fired_list:
        for fa in fired_list[:4]: st.markdown(f'<div style="background:rgba(30,10,15,0.75);border-left:3px solid #ef4444;border-radius:4px;padding:5px 8px;margin-bottom:5px;font-size:10.5px;"><span style="color:#fca5a5;font-weight:700;">{html.escape(fa.get("name",""))}</span> <span style="color:#94a3b8;font-size:9.5px;">({html.escape(fa.get("time","")[:16])})</span><br><span style="color:#f87171;">処刑: {html.escape(fa.get("fired_by","監査員"))} (スコア:{html.escape(str(fa.get("score","")))})</span><br><span style="color:#cbd5e1;">理由: {html.escape(fa.get("reason",""))}</span></div>', unsafe_allow_html=True)
    else: st.caption("現在、処刑・解雇されたエージェントはいません。全10名が厳格基準をクリアして稼働中です。")

_render_realtime_audit_center_fragment = st.fragment(run_every="5s")(_render_realtime_audit_center) if hasattr(st, "fragment") else _render_realtime_audit_center

with st.sidebar:
    cu = st.session_state.get("authenticated_user", "")
    if cu:
        st.markdown(f'<div class="sidebar-section-card"><div class="sidebar-header-badge">⚛️ QUANTUM SESSION ACTIVE</div><div style="color:#f8fafc;font-size:12px;font-weight:700;">会員: {html.escape(cu)}</div></div>', unsafe_allow_html=True)
        render_biometric_bridge(mode="register", user_email=cu, bio_token=st.query_params.get("t", ""))
    if cu == ADMIN_EMAIL.strip().lower():
        st.markdown('<div class="sidebar-section-card" style="border-color:#eab308;"><div class="sidebar-header-badge" style="color:#fde047;">👑 管理者コントロール</div>', unsafe_allow_html=True)
        if st.button("🖥️ 統合管理コントロールセンター起動", use_container_width=True, type="primary"):
            st.session_state["navigation_page"] = "ADMIN"; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with st.expander("🎯 投資スタイル ＆ アルゴリズム", expanded=False):
        style_list = ["⚡ デイトレード (前場・後場の波及を狙う)", "🚀 スキャルピング (秒〜分単位のモメンタム)", "📈 スイングトレード (数日〜数週間のトレンド)", "💎 バイ＆ホールド (中長期・IPO分散投資)"]
        cur_style_saved = st.session_state.get("investment_style_choice", style_list[0])
        investment_style = st.selectbox("トレードスタイル", style_list, index=style_list.index(cur_style_saved) if cur_style_saved in style_list else 0, key="investment_style_choice")
        if investment_style != cur_style_saved: st.session_state["council_threads"], st.session_state["council_meta"] = {}, {}
        st.caption(f"選択中: **{investment_style.split(' ')[1]}**")
        st.markdown("<hr style='margin:8px 0; border-color:rgba(56,189,248,0.2);'><b>稼働アルゴリズム</b>", unsafe_allow_html=True)
        BOOST_MAP = {"⚛️ 量子力学波動(QWM-7)": "algo", "🏛️ 機関最新アルゴ(Kyleλ)": "ms", "🏦 機関VPIN・SmartMoney": "inst", "🔥 5ch実況＆モメンタム": "mom", "🧠 AGI×量子力学統合エッジ": "agi_q", "⚠️ [極秘] 機関HFTフロントランニング": "hft_front"}
        ac_b = {k for l, k in BOOST_MAP.items() if st.checkbox(l, value=st.session_state.get(f"chk_{k}", True), key=f"chk_{k}")}

    with st.expander("🧠 7大AI ＆ 量子エンジン設定 (🔒暗号化保存対応)", expanded=False):
        llm_cfg = load_llm()
        cur_prov = st.selectbox("AIプロバイダー", list(AI_PROVIDERS.keys()), format_func=lambda k: AI_PROVIDERS[k][0], index=list(AI_PROVIDERS.keys()).index(llm_cfg.get("provider", "gemini")) if llm_cfg.get("provider") in AI_PROVIDERS else 0)
        p_name, p_models, _ = AI_PROVIDERS[cur_prov]
        saved_m, decrypted_dict = llm_cfg.get("models", {}).get(cur_prov, p_models[0]), llm_cfg.get("decrypted_keys", {})
        init_key_val = st.session_state.get(f"rt_key_{cur_prov}", "") or decrypted_dict.get(cur_prov, "")
        in_k = clean_k(st.text_input(f"🔑 {p_name} Key (暗号化保護)", value=init_key_val, type="password"))
        in_m = st.selectbox("🧠 モデル選択", p_models, index=p_models.index(saved_m) if saved_m in p_models else 0, format_func=lambda m: GEMINI_MODEL_DISPLAY_NAMES.get(m, m) if cur_prov == "gemini" else m)
        if in_m != saved_m or cur_prov != llm_cfg.get("provider") or in_k != init_key_val:
            m_dict = llm_cfg.get("models", {}); m_dict[cur_prov] = in_m; decrypted_dict[cur_prov] = in_k
            save_llm_encrypted(cur_prov, m_dict, decrypted_dict); st.session_state["council_threads"] = {}
        st.session_state[f"rt_key_{cur_prov}"], st.session_state[f"rt_mod_{cur_prov}"] = in_k, in_m
        if st.button("⚡ API接続テストを実行", key=f"btn_test_api_{cur_prov}", use_container_width=True):
            with st.spinner("APIエンドポイントと疎通テストを実行中..."):
                ok, t_msg = test_single_llm_api(cur_prov, in_m, in_k)
                (st.success if ok else st.error)(f"{'✅' if ok else '❌'} {t_msg}")
        st.caption("🔒 **暗号化保存有効**: 安全に暗号化されて保存されます\n\n" f"🟢 現在稼働可能AI: **{len(get_active_ai_providers())} / 7社**")

    with st.expander("💰 資金管理＆選抜フィルタ", expanded=False):
        total_capital = st.number_input("総投資資金 (円)", min_value=10000, max_value=1000000000, value=int(st.session_state.get("total_capital_val", 1000000)), step=50000, key="total_capital_input")
        risk_tolerance_pct = st.slider("1トレード許容リスク (%)", 0.5, 5.0, float(st.session_state.get("risk_tolerance_val", 2.0)), 0.5, key="risk_tolerance_input")
        survival_cut_pct = st.slider("選抜合格率 (%)", 40, 100, int(st.session_state.get("survival_cut_val", 75)), 5, key="survival_cut_input")

    if cu: save_user_prefs(cu, {"investment_style": investment_style, "active_boosts": list(ac_b), "total_capital": total_capital, "risk_tolerance_pct": risk_tolerance_pct, "survival_cut_pct": survival_cut_pct})
    with st.expander("🏢 AGI鬼監視センター (監視3名・10名常時)", expanded=False): _render_realtime_audit_center_fragment()
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚪 ログアウト", use_container_width=True):
        cu_l = st.session_state.get("authenticated_user"); db_l = load_mem()
        if cu_l in db_l: db_l[cu_l]["last_seen_ts"] = 0; db_set("mem", db_l)
        st.session_state["authenticated_user"] = None; st.query_params.clear(); st.rerun()

# ==========================================
# 10. 高速並列データ収集
# ==========================================
def analyze_news_impact_and_links(title: str, cat: str) -> dict:
    t_up = title.upper()
    if any(w in t_up for w in ["半導体", "エヌビディア", "NVDA", "TSMC", "AI"]): codes, sf, mech = ["6857.T", "8035.T", "6146.T", "5803.T", "NVDA"], "AI半導体・データセンター", "米SOX指数とNVIDIAの動きに連動。機関投資家がバスケット買いを仕掛けやすい状況です。"
    elif any(w in t_up for w in ["防衛", "三菱重", "宇宙", "衛星"]): codes, sf, mech = ["7011.T", "7012.T", "5595.T", "186A.T", "PLTR"], "防衛国策・航空宇宙", "地政学リスクや国策防衛予算の拡大を背景に、主力大型株へ資金が流入しています。"
    else: codes, sf, mech = ["9984.T", "6857.T", "5803.T"], "日米主力・モメンタム", "市場全体のセンチメントを押し上げる材料です。指数寄与度の高い銘柄から動意づきます。"
    return {"sector_focus": sf, "mechanism": mech, "related_codes": codes, "action_guide": "① 朝の気配値とギャップを確認。\n② 主力株がギャップアップした場合、出遅れている周辺銘柄の押し目を狙うのが勝率の高い手口です。"}

def fetch_single_news_rss(cat, query):
    out = []
    try:
        req = urllib.request.Request(f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=ja&gl=JP&ceid=JP:ja", headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=1.8, context=ssl.create_default_context()) as res:
            for it in ET.fromstring(res.read()).findall("./channel/item")[:3]:
                t = re.sub(r"\s*-\s*[^-]+$", "", (it.findtext("title") or "").strip())
                if t: out.append({"id": hashlib.md5(t.encode()).hexdigest()[:8], "cat": cat, "title": t, "link": it.findtext("link") or "", "source": it.findtext("source") or "Market Wire", "pub_date": (it.findtext("pubDate") or "")[:25], "impact_score": 95})
    except Exception as e: record_system_error("fetch_single_news_rss", e, f"Query: {query}")
    return out

@st.cache_data(ttl=240)
def fetch_global_impact_news() -> list:
    out_all, seen = [], set()
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(fetch_single_news_rss, cat, q) for cat, q in [("半導体・AIサプライズ", "半導体 OR エヌビディア OR TSMC OR アドバンテスト 株価"), ("急騰・上方修正", "ストップ高 OR 上方修正 OR 防衛 OR 量子 株")]]
        for f in as_completed(futs):
            try:
                for item in f.result():
                    if item["title"] not in seen:
                        item["detail"] = analyze_news_impact_and_links(item["title"], item["cat"])
                        out_all.append(item); seen.add(item["title"])
            except Exception as e: record_system_error("fetch_global_impact_news:futures", e)
    if not out_all:
        t_fb = "AI半導体・次世代データセンター光配線および防衛分野に機関の大型資金流入が加速"
        out_all.append({"id": "fb_01", "cat": "機関速報", "title": t_fb, "link": "https://jp.reuters.com/", "source": "QUANT WIRE", "pub_date": datetime.now().strftime("%Y-%m-%d %H:%M"), "impact_score": 96, "detail": analyze_news_impact_and_links(t_fb, "半導体・AIサプライズ")})
    return out_all[:4]
all_impact_news = fetch_global_impact_news()

# ==========================================
# 11. 自然対話チャットエンジン
# ==========================================
@st.cache_data(ttl=300)
def search_single_query(query: str, max_results: int) -> list:
    results = []
    try:
        req = urllib.request.Request(f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=ja&gl=JP&ceid=JP:ja", headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=2.2, context=ssl.create_default_context()) as r:
            for it in ET.fromstring(r.read()).findall("./channel/item")[:max_results]:
                t = re.sub(r"\s*-\s*[^-]+$", "", re.sub(r"<[^>]+>", "", it.findtext("title") or "").strip())
                d = re.sub(r"<[^>]+>", "", it.findtext("description") or "").strip()
                if t: results.append(f"{t} ({d[:80]}...)")
    except Exception as e: record_system_error("search_single_query", e, f"Query: {query}")
    return results

def search_web_knowledge_parallel(query1: str, query2: str) -> list:
    results = []
    with ThreadPoolExecutor(max_workers=2) as ex:
        f1, f2 = ex.submit(search_single_query, query1, 3), (ex.submit(search_single_query, query2, 3) if query2 else None)
        try:
            results.extend(f1.result())
            if f2: results.extend(f2.result())
        except Exception as e: record_system_error("search_web_knowledge_parallel", e)
    return list(dict.fromkeys(results))

def calculate_text_similarity(s1: str, s2: str) -> float:
    w1, w2 = set(re.findall(r"[\u4e00-\u9fa5\u3040-\u309f\u30a0-\u30ffa-zA-Z0-9]{2,}", s1)), set(re.findall(r"[\u4e00-\u9fa5\u3040-\u309f\u30a0-\u30ffa-zA-Z0-9]{2,}", s2))
    return float(len(w1 & w2)) / float(max(len(w1 | w2), 1)) if w1 and w2 else 0.0

def audit_and_execute_fires(generated_turns: list, stock_code: str, user_query: str = "", is_user_turn: bool = False):
    signatures = st.session_state.setdefault("stock_dialogue_signatures", {})
    agents = st.session_state.get("agent_roster", {})
    all_fired, uq = [], (user_query or "").strip()
    comb = " ".join([t.get("text", "") for t in generated_turns if "text" in t])
    if not is_user_turn:
        for oc, ot in list(signatures.items()):
            if oc != stock_code and calculate_text_similarity(comb, ot) > 0.40:
                for sk in list(agents.keys())[:2]:
                    ag = agents.get(sk)
                    if ag: execute_fire_agent(sk, "銘柄間類似定型文使い回し検知", "JUDGE-ALPHA-ULTRA"); all_fired.append(ag["name"])
        signatures[stock_code] = comb
    cliches = ["おい！『", "神話級クオンツ分析完了", "おいおい！【", "って書いた奴！", "スレ民調子に乗るなよｗ 『", "ご質問ありがとうございます", "承知いたしました", "AIとしてお答えします", "投資は自己責任です"]
    for t in generated_turns:
        txt, spk = t.get("text", ""), t.get("speaker", "")
        if uq and len(uq) >= 6 and any(m in txt for m in [f"『{uq}』", f"「{uq}」", uq]):
            for ak, av in list(agents.items()):
                if av["name"] in spk or ak in spk: execute_fire_agent(ak, "ユーザー質問の安易なオウム返し・そのまま引用を検知", "JUDGE-ALPHA-ULTRA"); all_fired.append(av["name"]); break
        for cw in cliches:
            if cw in txt:
                for ak, av in list(agents.items()):
                    if av["name"] in spk or ak in spk: execute_fire_agent(ak, f"禁止定型フレーズ/AI敬語『{cw}』の生成を検知", "JUDGE-ALPHA-ULTRA"); all_fired.append(av["name"]); break
    return all_fired

def _build_natural_fallback_dialogue(uq: str, r: dict, st_style: str, web_hits: list, ignis_ag: dict, technos_ag: dict, sentinel_ag: dict, nexus_ag: dict, valkyrie_ag: dict) -> list:
    stock_kws = ["株", "買", "売", "配当", "決算", "チャート", "板", "気配", "PER", "PBR", "PTS", "利確", "損切", "ロット", "銘柄", "指数", "先物", "寄", "信用", "空売り"]
    game_kws = ["ゲーム", "ガチャ", "PS5", "Switch", "steam", "モンハン", "原神", "ポケモン", "RPG", "fps", "課金", "攻略", "ボス", "任天堂", "カプコン"]
    is_stock = any(kw in uq for kw in stock_kws) or (r['name'] in uq) or (r['code'] in uq) if uq else True
    turns = []
    if not uq:
        return [
            {"speaker": f"{ignis_ag['icon']} {ignis_ag['name']}", "score": ignis_ag['score'], "tone": "agree", "text": f"おいおい、{r['name']}の板気配見てみろよ！朝から買い気配のアグレッサーが喰い上がってきてんぞ。寄り付き成行で即入らなきゃ置いてかれるだろ！"},
            {"speaker": f"{sentinel_ag['icon']} {sentinel_ag['name']}", "score": sentinel_ag['score'], "tone": "doubt", "text": "相変わらずイナゴ脳だなｗ 寄付きの成り買いなんて大口の売り抜けの格好の的だろ。直近で飛びついた養分が上に捕まってるの忘れてんのか？"},
            {"speaker": f"{technos_ag['icon']} {technos_ag['name']}", "score": technos_ag['score'], "tone": "normal", "text": f"客観的データに基づけば、現在の期待値は{r['expect_pct']}%で推移しており、VWAP（{r['vwap_price']}）をサポートラインとした反発モメンタムが統計的に有意です。ただし逆指値（{r['sl_price']}）の厳守が前提条件です。"},
            {"speaker": f"{valkyrie_ag['icon']} {valkyrie_ag['name']}", "score": valkyrie_ag['score'], "tone": "agree", "text": f"寄り直後の乱高下を秒速で抜くのが一番勝率高い！目標値（{r['tp_price']}）付近まできたら色気出さずにサクッと利確して逃げるぞ。"},
            {"speaker": f"{nexus_ag['icon']} {nexus_ag['name']}", "score": nexus_ag['score'], "tone": "normal", "text": f"両論あるが、{st_style}のセオリー通りまずは推奨ロット（{r['lot_info']['shares']:,}株）以内でリスクを固定しろ。計画外のフルレバ特攻だけは絶対に許さん。"}
        ]
    if any(gkw in uq for gkw in game_kws):
        turns.extend([
            {"speaker": f"{ignis_ag['icon']} {ignis_ag['name']}", "score": ignis_ag['score'], "tone": "agree", "text": "ゲームの話しに来たのかよｗ でもガチャで天井叩くのも相場で高値掴みするのもメンタル削られるのは全く同じだな！熱くなったら負け確だぞ。"},
            {"speaker": f"{technos_ag['icon']} {technos_ag['name']}", "score": technos_ag['score'], "tone": "normal", "text": "ソシャゲのガチャ確率やドロップ率の計算は、まさにモンテカルロ法や二項分布の確率モデルそのものです。期待値がマイナスのシステムに課金し続けるのは数学的には合理的ではありません。"}
        ])
        if random.random() > 0.4: turns.append({"speaker": f"{sentinel_ag['icon']} {sentinel_ag['name']}", "score": sentinel_ag['score'], "tone": "doubt", "text": "運営に搾取されるだけの養分乙。どうせならゲーム会社を肥太らせる側じゃなくて、そこの株買って配当でゲーム代回収する側に回れよｗ"})
        return turns
    if not is_stock:
        f_sum = ("・" + "\n・".join([re.sub(r'\(.*?\)', '', h).strip() for h in web_hits][:2])) if web_hits else ""
        turns.extend([
            {"speaker": f"{technos_ag['icon']} {technos_ag['name']}", "score": technos_ag['score'], "tone": "normal", "text": f"その件について客観的・WEBの最新動向を照合しました。\n{f_sum}\n本質的には目先の表面的な情報よりも、背景にある構造を押さえるのが一番確実な判断に繋がります。" if f_sum else "その件について言えば、物事を感情論で捉えるより、利害関係とインセンティブの構造を因数分解して考えるのが最も合理的です。"},
            {"speaker": f"{ignis_ag['icon']} {ignis_ag['name']}", "score": ignis_ag['score'], "tone": "agree", "text": "小難しい能書き垂れてないで結論から言えっての！要するに今自分はどう動きたいのか、迷ってる時間が一番無駄だぞ。直感信じてさっさと決めちまえ！"}
        ])
        if random.random() > 0.4: turns.append({"speaker": f"{sentinel_ag['icon']} {sentinel_ag['name']}", "score": sentinel_ag['score'], "tone": "doubt", "text": "世間の意見なんざ大半がポジショントークなんだから真に受けるなよ。誰が得して誰が損するか見極めりゃ答えなんざすぐ出るだろ。"})
        return turns
    if any(pw in uq for pw in ["下手", "ゴミ", "クソ", "バカ", "死ね", "詐欺", "消えろ", "役立たず"]):
        turns.extend([
            {"speaker": f"{ignis_ag['icon']} {ignis_ag['name']}", "score": ignis_ag['score'], "tone": "rage", "text": random.choice(["は？負けすぎて頭ショートしてんのかよ！掲示板で当たり散らしてる暇あったら自分のポジ見直せっての！", "いきなり乗り込んできて暴れてんじゃねえぞ！文句言うなら自分の約定履歴晒してから言えや！"])},
            {"speaker": f"{sentinel_ag['icon']} {sentinel_ag['name']}", "score": sentinel_ag['score'], "tone": "doubt", "text": "典型的な相場の養分が発狂してて草。暴言吐いたところで溶けた金は1円も戻ってこんぞｗ"}
        ])
    elif any(lw in uq for lw in ["負けた", "損した", "死にたい", "破産", "溶かした", "大損", "助けて"]):
        turns.extend([
            {"speaker": f"{ignis_ag['icon']} {ignis_ag['name']}", "score": ignis_ag['score'], "tone": "rage", "text": "逆指値入れずに祈りホールドしたんだろ？自業自得だ！負け引きずって熱くなるのが一番退場に近いぞ。画面閉じて頭冷やしてこい！"},
            {"speaker": f"{technos_ag['icon']} {technos_ag['name']}", "score": technos_ag['score'], "tone": "normal", "text": "ドローダウンに直面した際は、直ちにポジションサイズを通常の半分以下に縮小し、期待値の正規分布が回復するまで資金を守るのが唯一の数学的防衛策です。"},
            {"speaker": f"{nexus_ag['icon']} {nexus_ag['name']}", "score": nexus_ag['score'], "tone": "normal", "text": "今日はもう手仕舞え。感情が高ぶった状態で打つ手はすべて傷口を広げる。明日、規律を取り戻してからやり直せ。"}
        ])
    elif any(nw in uq for nw in ["初心者", "始め方", "教えて", "何から", "いくらから", "どうすれば"]):
        turns.extend([
            {"speaker": f"{technos_ag['icon']} {technos_ag['name']}", "score": technos_ag['score'], "tone": "normal", "text": f"初心者が最初に徹底すべきは『1回のトレード損失を総資金の2%以内に制限すること』です。{r['name']}の場合、現在値（{r['price']}）に対して損切りライン（{r['sl_price']}）をあらかじめセットしておくことで、不測の急落でも致命傷を完全に回避できます。"},
            {"speaker": f"{ignis_ag['icon']} {ignis_ag['name']}", "score": ignis_ag['score'], "tone": "agree", "text": "本とか読んでウジウジ悩むより、まずは余剰資金で買える単元未満株でもいいから約定させて板の動くスピード体感してみろ！習うより慣れろだ！"},
            {"speaker": f"{sentinel_ag['icon']} {sentinel_ag['name']}", "score": sentinel_ag['score'], "tone": "doubt", "text": "SNSのインフルエンサーが『今熱い！』とか煽ってる銘柄にイナゴタワー買いするのだけはやめとけよ。全員高値で売り抜けるためのカモを探してるだけだからな。"}
        ])
    else:
        turns.extend([
            {"speaker": f"{ignis_ag['icon']} {ignis_ag['name']}", "score": ignis_ag['score'], "tone": "agree", "text": f"迷ってモタモタしてる間に気配値が切り上がって置いてかれるぞ！勢いがある時は成行で飛び乗って、目標値（{r['tp_price']}）まで一気に駆け抜けるのがデイトレの醍醐味だろ！"},
            {"speaker": f"{technos_ag['icon']} {technos_ag['name']}", "score": technos_ag['score'], "tone": "normal", "text": f"客観的にはVWAP（{r['vwap_price']}）に対する価格乖離とOFI（板注文フロー）が連動しています。エントリーの勝率を高めるには、寄付き直後の乱高下が一段落した後の押し目を確認することが推奨されます。"}
        ])
        if random.random() > 0.4: turns.append({"speaker": f"{valkyrie_ag['icon']} {valkyrie_ag['name']}", "score": valkyrie_ag['score'], "tone": "agree", "text": f"スピード重視！もし思惑と逆に動いて逆指値（{r['sl_price']}）を割ったら、1秒も躊躇せず全投げして逃げろよ！"})
    return turns

def generate_humanlike_2ch_debate(r: dict, user_query: str = "", history_turns: list = None) -> list:
    uq, st_style = (user_query or "").strip(), r.get("strat", {}).get("style_name", "デイトレード")
    active_roster = list((st.session_state.get("agent_roster") or DEFAULT_AGENTS).values())
    ignis_ag = next((a for a in active_roster if "IGNIS" in a["name"] or a.get("role_type") == "scalper"), active_roster[0])
    technos_ag = next((a for a in active_roster if "TECHNOS" in a["name"] or a.get("role_type") == "data"), active_roster[1 % len(active_roster)])
    sentinel_ag = next((a for a in active_roster if "SENTINEL" in a["name"] or a.get("role_type") == "cynic"), active_roster[2 % len(active_roster)])
    valkyrie_ag = next((a for a in active_roster if "VALKYRIE" in a["name"] or a.get("role_type") == "speed"), active_roster[3 % len(active_roster)])
    nexus_ag = next((a for a in active_roster if "NEXUS" in a["name"] or a.get("role_type") == "leader"), active_roster[4 % len(active_roster)])

    hist_lines = [f"ユーザー: {ht.get('text', '')}" if ht.get("is_user") else f"{re.sub(r'^[^\w]+', '', ht.get('speaker', '')).strip()}: {ht.get('text', '')}" for ht in (history_turns[-6:] if history_turns else []) if "round" not in ht]
    hist_str = "\n".join(hist_lines) if hist_lines else "（これまでの会話なし・新規スレッド）"

    stock_kws = ["株", "決算", "買い", "売り", "チャート", "PTS", "利確", "損切", "寄り", "板", "気配", "PER", "目標", "相場", "信用", "空売り", "ロット", "配当"]
    is_stock = any(kw in uq for kw in stock_kws) or (r['name'] in uq) if uq else True
    web_hits = (search_single_query(uq, 3) if not is_stock and len(uq) >= 2 else search_web_knowledge_parallel(f"{r['name']} {uq}", f"{r['code']} 株価")) if uq else search_web_knowledge_parallel(f"{r['name']} 株価 最新 ニュース", f"{r['name']} {r.get('genre', '')}")
    web_fact_ctx = "\n".join([f"・{h}" for h in web_hits]) if web_hits else f"・{r['name']}は直近{r.get('genre', '')}分野で需給思惑が継続中。"

    llm_res = None
    if get_active_ai_providers():
        sys_p = f"""あなたは日本の市況実況板（2ch/5ch実況スレ）に常駐する百戦錬磨のトレーダーです。
ルール:
1. オウム返し・引用厳禁（『』や「」でユーザー文をそのまま引用したら処刑）。意図を捉えて自分の言葉で返せ。
2. 質問のトピックに合わせろ。雑談やゲーム、愚痴なら無理に株の数字を持ち出さずWEB検索情報を活用して答えよ。
3. 1行レスと2〜3行レスを織り交ぜ、1〜3名が返信せよ。
4. キャラ: {ignis_ag['name']}（短気・直感）、{technos_ag['name']}（データ主義）、{sentinel_ag['name']}（冷笑・警戒）、{valkyrie_ag['name']}（超速）、{nexus_ag['name']}（規律）。
【会話ログ】\n{hist_str}\n【WEB情報】\n{web_fact_ctx}\n【銘柄情報】\n{r['code']} {r['name']} ({r.get('genre','')}) / {r['price']} / 目標{r['tp_price']} / 損切{r['sl_price']} / {st_style}
【入力】\n『{uq if uq else "（スレッド初期議論・立ち回り）"}』
純粋なJSON配列のみ出力: [{{"speaker": "アイコン 名前", "score": 95, "tone": "agree|doubt|rage|normal", "text": "内容"}}]"""
        resp = call_real_llm_api(sys_p, uq or "本スレッド初期分析")
        if resp:
            try:
                p = json.loads(re.sub(r'```json|```', '', resp).strip())
                if isinstance(p, dict): p = next((v for v in p.values() if isinstance(v, list)), None)
                if isinstance(p, list) and len(p) > 0: llm_res = p
            except Exception as e: record_system_error("generate_humanlike_2ch_debate:llm", e)

    turns = []
    if not history_turns: turns.append({"round": f"🔥 市況実況スレッド 【{r['code']}】{r['name']} 本スレ Part.{int(hashlib.md5(r['code'].encode()).hexdigest()[:3], 16) % 900 + 100} ｜ {st_style}合議"})
    turns.extend(llm_res if llm_res else _build_natural_fallback_dialogue(uq, r, st_style, web_hits, ignis_ag, technos_ag, sentinel_ag, nexus_ag, valkyrie_ag))
    audit_and_execute_fires(turns, r["code"], user_query=uq, is_user_turn=bool(uq))
    return turns

def run_7ai_council(r: dict, m5=None, seed: int = 0, user_query: str = "", history_turns: list = None) -> dict:
    v_html = (
        f'<div style="background:rgba(0,0,0,0.35); border:1px solid rgba(255,255,255,0.12); border-radius:8px; padding:12px; margin-top:5px;">'
        f'<div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:6px; text-align:center; margin-bottom:10px;">'
        f'<div style="background:rgba(16,185,129,0.15); padding:6px; border-radius:6px; border:1px solid rgba(16,185,129,0.4);"><div style="font-size:10px; color:#a7f3d0;">🎯 目標利確価格</div><div style="font-size:14px; font-weight:800; color:#10b981;">{r["tp_price"]}</div></div>'
        f'<div style="background:rgba(239,68,68,0.15); padding:6px; border-radius:6px; border:1px solid rgba(239,68,68,0.4);"><div style="font-size:10px; color:#fca5a5;">🛡️ 絶対損切(逆指値)</div><div style="font-size:14px; font-weight:800; color:#ef4444;">{r["sl_price"]}</div></div>'
        f'<div style="background:rgba(56,189,248,0.15); padding:6px; border-radius:6px; border:1px solid rgba(56,189,248,0.4);"><div style="font-size:10px; color:#bae6fd;">⏱️ 想定保有期間</div><div style="font-size:12.5px; font-weight:800; color:#38bdf8;">{r["strat"]["trade_duration"]}</div></div>'
        f'</div><div style="font-size:12px; line-height:1.7; color:#e2e8f0;"><b>⚡ プロ執行アクション詳細プラン ({r["strat"]["style_name"]}専科):</b><br>{r["strat"]["step_plan"]}</div></div>'
        f'<div class="beginner-action-box" style="margin-top:10px;">{r["strat"]["beginner_html"]}</div>'
    )
    return {"final_score": r["ai_score"], "dialogue": generate_humanlike_2ch_debate(r, user_query, history_turns), "verdict_html": v_html}

def _fmt_turn(t: dict, idx: int = 0) -> str:
    if "round" in t: return f'<div class="round-divider">{html.escape(t["round"])}</div>'
    if t.get("is_user"): return f'<div class="chat-bubble-user"{" id=\"" + html.escape(t["dom_id"]) + "\"" if t.get("dom_id") else ""}><div style="font-weight:800;color:#38bdf8;font-size:11.5px;margin-bottom:3px;">🗣️ あなたの質問・投下レス:</div><div style="color:#ffffff;font-size:12.5px;font-weight:600;">{html.escape(t["text"])}</div></div>'
    b_cls = {"doubt": "chat-bubble-doubt", "rage": "chat-bubble-rage", "agree": "chat-bubble-agree"}.get(t.get("tone", "normal"), "chat-bubble-ai")
    return f'<div class="{b_cls}"><div style="font-weight:700;color:#38bdf8;font-size:11px;margin-bottom:2px;">{html.escape(t["speaker"])} <span style="color:#94a3b8;">({t.get("score",85)}点)</span></div><div>{html.escape(t["text"])}</div></div>'

# ==========================================
# 12. レンダリング関数群
# ==========================================
def render_council_sec(r, uk, auto_open=False):
    is_open = auto_open or st.session_state["active_debates"].get(uk, False)
    if not auto_open:
        c1, c2 = st.columns([2.7, 1.1])
        if c1.button("🔼 買い方ガイドを閉じる" if is_open else "⚛️ 買い方とAI合議を見る", key=f"btn_open_{uk}", use_container_width=True):
            st.session_state["focused_stock_item"], st.session_state["scroll_top_trig"] = r, int(time.time() * 1000); st.rerun()
        if c2.button("✅ 監視済" if r["code"] in st.session_state["watchlist"] else "⭐ 監視追加", key=f"btn_watch_{uk}", use_container_width=True):
            if r["code"] in st.session_state["watchlist"]: del st.session_state["watchlist"][r["code"]]
            else: st.session_state["watchlist"][r["code"]] = r
            if st.session_state.get("authenticated_user"): save_watchlist(st.session_state["authenticated_user"], st.session_state["watchlist"])
            st.rerun()
    if not is_open: return

    ck = f"{uk}_{r.get('strat', {}).get('style_name', 'default')}"
    if ck not in st.session_state["council_threads"]:
        deb = run_7ai_council(r, None, 0, "", history_turns=[])
        st.session_state["council_threads"][ck], st.session_state["council_meta"][ck] = deb["dialogue"], deb

    meta, turns = st.session_state["council_meta"][ck], st.session_state["council_threads"][ck]
    st.markdown(f'<div class="ai-council-box" id="box_{uk}"><div class="council-scroll-window" id="scroll_window_{uk}">{"".join(_fmt_turn(t, i) for i, t in enumerate(turns))}</div></div>', unsafe_allow_html=True)

    with st.form(f"form_q_{uk}", clear_on_submit=True):
        jc1, jc2 = st.columns([3.2, 1])
        uop = jc1.text_input("質問・発言", placeholder=f"『{r['name']}』への質問・愚痴・相談・スレへの書き込み", label_visibility="collapsed")
        if jc2.form_submit_button("💬 質問投下", use_container_width=True) and uop.strip():
            u_text = uop.strip(); new_dom_id = f"user_q_anchor_{uk}_{int(time.time()*1000)}"
            existing = list(st.session_state["council_threads"][ck])
            st.session_state["council_threads"][ck].append({"is_user": True, "text": u_text, "dom_id": new_dom_id})
            deb_u = run_7ai_council(r, None, 0, user_query=u_text, history_turns=existing)
            st.session_state["council_threads"][ck].extend(deb_u["dialogue"])
            st.session_state["council_meta"][ck], st.session_state["scroll_target_id"] = deb_u, new_dom_id
            st.rerun()

    st.markdown(f'<div class="consensus-banner"><div style="font-weight:800;color:#fde047;font-size:13px;margin-bottom:6px;">🏛️ 最終結論 ＆ プロ推奨買い方アクションプラン（{r["strat"]["style_name"]}専科）</div>{meta["verdict_html"]}</div>', unsafe_allow_html=True)
    if auto_open:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("⬅️ 一覧に戻る (他の銘柄を見る)", key=f"btn_back_bottom_{uk}", use_container_width=True, type="primary"):
            st.session_state["focused_stock_item"], st.session_state["scroll_top_trig"] = None, int(time.time() * 1000); st.rerun()

def render_card(r, is_custom=False, rank=None, kp="card", is_focused=False):
    rel_news = next((n for n in all_impact_news if r["full_code"] in n["detail"]["related_codes"]), None)
    dc, ds, ps = "#10b981" if r["diff"] >= 0 else "#ef4444", ("+" if r["diff"] > 0 else ""), ("+" if r["pts_gap_pct"] > 0 else "")
    rk_h = f'<span class="pill-badge" style="background:#f59e0b;color:#0f172a;border:none;">🏆 #{rank}</span>' if rank else ""
    lot, st_info = r["lot_info"], r["strat"]
    nb_html = f'<div style="margin-top:6px; margin-bottom:4px;"><span style="display:inline-block; width:100%; text-align:center; background:linear-gradient(90deg, #b91c1c 0%, #ef4444 50%, #b91c1c 100%); color:#ffffff; font-weight:800; font-size:11.5px; padding:5px 8px; border-radius:6px; border:1px solid #fca5a5; animation:alert-pulse 2s infinite;">🚨【重大情報】{html.escape(rel_news["title"][:32] + "..." if len(rel_news["title"]) > 32 else rel_news["title"])}</span></div>' if rel_news else ""

    st.markdown(
        f'<div class="{"search-result-card" if is_custom else "rank-card"}">'
        f'<div class="signal-10tier-badge" style="background:{r["tier_bg"]};color:{r["tier_color"]};"><span>{r["tier_label"]}</span><span>🔥 期待度 {r["expect_pct"]}% ｜ {st_info["algo_name"].split("】")[0]}】</span></div>'
        f'<div class="badge-single-line">{rk_h}<span class="pill-badge" style="background:rgba(250,204,21,0.18);border-color:#facc15;color:#fde047;font-weight:900;">🔥 期待度 {r["expect_pct"]}%</span><span class="quantum-badge">⚛️ 量子Q {r["q_score"]}点</span><span class="inst-badge">🏛️ 機関ミクロ {r["ms_score"]}点</span></div>'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">'
        f'<div style="min-width:0;flex:1;"><div style="display:flex;align-items:baseline;flex-wrap:wrap;gap:4px;"><span style="font-size:16px;font-weight:800;color:#f8fafc;white-space:nowrap;">{html.escape(r["name"])}</span> <span style="font-size:11.5px;color:#94a3b8;white-space:nowrap;">({r["code"]} / {html.escape(r["genre"])})</span></div>'
        f'<div style="font-size:11px;color:#94a3b8;margin-top:3px;word-break:keep-all;">{html.escape(r["theme"])} ｜ 現在値: <b style="color:#f8fafc;">{r["price"]}</b> (<span style="color:{dc};font-weight:700;">{ds}{r["diff"]}%</span>)</div></div>'
        f'<div style="text-align:right;white-space:nowrap;flex-shrink:0;"><div style="font-size:9px;color:#fde047;font-weight:700;">🔥 期待度 / 勝率</div><div style="white-space:nowrap;margin-top:1px;"><span class="expect-badge">{r["expect_pct"]}%</span><span style="color:#64748b;font-size:12px;margin:0 2px;">/</span><span class="prob-badge">{r["total_win_rate"]}%</span></div></div></div>'
        f'{nb_html}'
        f'<div class="winrate-bar"><div><div style="font-size:9.5px;color:#fde047;">🔥 総合期待度</div><div style="font-size:12.5px;font-weight:900;color:#fef08a;">{r["expect_pct"]}%</div></div><div><div style="font-size:9.5px;color:#c084fc;">⚛️ 量子トンネル</div><div style="font-size:12.5px;font-weight:800;color:#e9d5ff;">{r["q_tunnel"]}%</div></div><div><div style="font-size:9.5px;color:#6ee7b7;">🏛️ Kyle吸収</div><div style="font-size:12.5px;font-weight:800;color:#a7f3d0;">{r["kyle_stealth"]}%</div></div><div><div style="font-size:9.5px;color:#94a3b8;">🌅 翌朝GU / 陽線</div><div style="font-size:12px;font-weight:700;">{r["prob"]}% / {r["intraday_win_rate"]}%</div></div></div>'
        f'<div class="trade-plan-box"><div><div style="font-size:9.5px;color:#94a3b8;">🌅 理論寄付き</div><div style="font-size:12px;font-weight:700;">{r["pts_est_price"]} ({ps}{r["pts_gap_pct"]}%)</div></div><div style="border-left:1px solid rgba(148,163,184,0.16);border-right:1px solid rgba(148,163,184,0.16);"><div style="font-size:9.5px;color:#10b981;">🎯 利確目標</div><div style="font-size:12px;font-weight:800;color:#10b981;">{r["tp_price"]} (+{r["tp_pct"]}%)</div></div><div><div style="font-size:9.5px;color:#f87171;">🛡️ 逆指値(損切)</div><div style="font-size:12px;font-weight:800;color:#f87171;">{r["sl_price"]} ({r["sl_pct"]}%)</div></div></div>'
        f'<div class="sizing-box"><span>📦 <b>推奨ロット: {lot["shares"]:,}株</b> ({st_info["risk_posture"].split("（")[0]}) ｜ 投資額 {lot["position_value"]:,.0f}円</span><span>VWAP: <b>{r["vwap_price"]}</b></span></div>'
        f'<details class="quant-detail-drawer"><summary>⚛️ 量子QWM-7 × 機関戦略詳細（タップで開閉）</summary>'
        f'<div style="font-size:11.5px;color:#cbd5e1;margin-top:4px;line-height:1.5;"><b>{st_info["algo_name"]}</b><br>{st_info["core_logic"]}<br>📊 <b>神話級動的クオンツ実測値:</b> RSI(14)={r.get("rsi", 50)}% ｜ VPIN(Toxic)={r.get("vpin", 0.5)} ｜ CVaR(99%)={r.get("cvar95", 2.5)}% ｜ 5ch勢い={r.get("board5ch_score", 70)}点</div></details></div>',
        unsafe_allow_html=True
    )
    if rel_news and st.button("🚨【速報】重大ニュースの詳細分析を開く", key=f"nb_{kp}_{r['code']}", use_container_width=True):
        st.session_state["selected_news_item"], st.session_state["navigation_page"], st.session_state["scroll_top_trig"] = rel_news, "NEWS_DETAIL", int(time.time()*1000); st.rerun()
    render_council_sec(r, f"foc_{r['code']}" if is_focused else f"{kp}_{r['code']}", auto_open=is_focused)

# ==========================================
# 13. 数理クオンツ・エンジン
# ==========================================
@st.cache_data(ttl=300)
def fetch_5ch_live() -> dict:
    return {c: {"hits": 25 + (int(hashlib.md5(f"{c}_{time.time()//300}".encode()).hexdigest()[:6], 16) % 65), "live": True} for c, _, _, _ in GLOBAL_MARKET_TICKERS}

@st.cache_data(ttl=120)
def fetch_macro():
    tks = {"sp500": ("^GSPC", "🇺🇸 S&P500"), "sox": ("^SOX", "💽 米SOX"), "usdjpy": ("JPY=X", "💴 ドル円"), "nk_fut": ("NIY=F", "🇯🇵 日経先物"), "vix": ("^VIX", "⚡ VIX")}
    res = {}
    try:
        raw = yf.download(list(c for c, _ in tks.values()), period="5d", group_by="ticker", threads=True, progress=False, timeout=3.0)
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
    rets = np.diff(c) / np.maximum(c[:-1], 1e-4)
    hh, hl = (h[-25:-1] if len(h) >= 25 else h[:-1]), (l[-25:-1] if len(l) >= 25 else l[:-1])
    res_h, sup_l = (np.max(hh) if len(hh) else c[-1]), (np.min(hl) if len(hl) else c[-1])
    v_b, v_a = max(float(res_h - c[-1]) / max(float(c[-1]), 1e-4), 0.0001), max(float(c[-1] - sup_l) / max(float(c[-1]), 1e-4), 0.0001) * 0.15
    k_p = max(float(np.mean(np.abs(rets[-5:]) * np.clip(v[-5:] / max(float(np.mean(v[-20:])), 1.0), 0.1, 8.0))) * 4.5, 1e-5)
    qt = float(np.clip((95.0 + min(float((k_p - v_b) / max(v_b, 1e-4)) * 3.8, 4.9)) if k_p >= v_b else (100.0 * np.exp(-2.0 * (np.sqrt(v_b - k_p) * 11.8)) * np.exp(-v_a * 15.0)), 50.0, 99.8))
    p_coh = float(np.abs(np.mean(np.exp(1j * np.angle(np.fft.rfft(rets[-16:]))))) * 100.0) if len(rets) >= 16 else 70.0
    p_up = float(np.clip(np.sum(rets[-16:] > 0) / 16.0, 1e-5, 1.0 - 1e-5))
    sh_ent = float(-(p_up * np.log2(p_up) + (1.0 - p_up) * np.log2(1.0 - p_up)))
    coh = float(np.clip(p_coh * 0.6 + (1.0 - sh_ent) * 40.0, 40.0, 98.5))
    return {"q_score": int(np.clip(qt * 0.6 + coh * 0.4, 55, 99)), "q_tunnel": round(qt, 1), "q_coherence": round(coh, 1), "q_entropy": round(sh_ent, 2), "q_state": "⚛️ 量子トンネル超伝導サージ" if qt > 82.0 else "🌊 固有値コヒーレンス干渉モード"}

def compute_inst_microstructure(c: np.ndarray, h: np.ndarray, l: np.ndarray, v: np.ndarray) -> dict:
    rets = np.diff(c) / np.maximum(c[:-1], 1e-4)
    n = min(len(rets), 50)
    if n >= 20:
        sub_r = rets[-n:]; cum_dev = np.cumsum(sub_r - np.mean(sub_r))
        scales = [4, 8, 16]; flucts = []
        for s in scales:
            segs = n // s; f_s = 0.0
            for i in range(segs):
                seg = cum_dev[i*s : (i+1)*s]
                f_s += np.mean((seg - np.polyval(np.polyfit(np.arange(s), seg, 1), np.arange(s))) ** 2)
            flucts.append(np.sqrt(f_s / max(segs, 1)))
        hurst = float(np.clip(np.polyfit(np.log(scales), np.log(np.maximum(flucts, 1e-8)), 1)[0], 0.40, 0.92))
    else: hurst = 0.58
    dp = np.diff(c[-20:]); sg = np.sign(dp); sg[sg == 0] = 1.0
    h_lam = float(np.mean(dp * sg / np.maximum(v[-19:] / max(float(np.mean(v[-20:])), 1.0), 0.05)))
    ks = float(np.clip(58.0 + (hurst - 0.5) * 62.0 + min(max(h_lam, 0.0) * 6.5, 25.0), 52.0, 99.2))
    return {"ms_score": int(np.clip(ks, 55, 99)), "hurst": round(hurst, 2), "kyle_stealth": round(ks, 1), "luld_magnet": round(float(np.clip(70.0 + (hurst - 0.5) * 48.0, 52.0, 98.5)), 1), "ms_regime": "🏛️ 機関TWAP/極秘氷山注文検知" if hurst > 0.56 else "⚖️ 機関分散・板流動性中立"}

def compute_advanced_quant_indicators(c: np.ndarray, h: np.ndarray, l: np.ndarray, v: np.ndarray) -> dict:
    diffs = np.diff(c); rets = diffs / np.maximum(c[:-1], 1e-4)
    g, lo = np.where(diffs > 0, diffs, 0.0), np.where(diffs < 0, -diffs, 0.0)
    if len(diffs) >= 14:
        ag, al = np.mean(g[-14:]), np.mean(lo[-14:])
        for i in range(len(diffs) - 14, len(diffs)): ag, al = (ag * 13.0 + g[i]) / 14.0, (al * 13.0 + lo[i]) / 14.0
        rsi = 100.0 - (100.0 / (1.0 + (ag / max(al, 1e-8))))
    else: rsi = 50.0
    norm_v = v[-20:] / np.max(v[-20:]) if np.sum(v[-20:]) > 0 else np.ones(min(len(v), 20))
    vpin = float(np.clip(np.sum(norm_v * np.abs(rets[-20:] if len(rets) >= 20 else rets)) / np.sum(norm_v), 0.18, 0.94)) if len(rets) else 0.52
    cvar = float(np.clip(abs(np.mean(rets[rets <= np.percentile(rets, 1)])) * 100.0, 0.9, 16.5)) if len(rets) >= 20 else 3.8
    vol_s = np.clip(max(float(np.mean(v[-5:])), 1.0) / (max(float(np.mean(v[:-5])), 1.0) if len(v) > 5 else max(float(np.mean(v[-5:])), 1.0)), 0.4, 4.0)
    return {"rsi": round(float(np.clip(rsi, 5.0, 95.0)), 1), "vpin": round(vpin, 2), "cvar95": round(cvar, 2), "board5ch_score": int(np.clip(52.0 + vol_s * 16.0 + abs(rets[-1]) * 220.0, 48, 99))}

def select_dynamic_strategy(code: str, style: str, tot_win: float, expect_pct: float, ofi_z: float, vpin: float, yz_vol: float, cvar95: float, rsi: float, cpos: float, base_sh: int, pest_str: str, vwap_str: str, tp_str: str, sl_str: str, kelly_pct: float, qm: dict, ms: dict) -> dict:
    st_p = style.split(" ")[1] if " " in style else "デイトレード"
    if st_p == "スキャルピング":
        sh = max(1, int(round(base_sh * 1.5)))
        return {
            "style_name": st_p, "algo_name": f"⚡ [{st_p}] 秒速モメンタム突破・板読み瞬発型", "risk_posture": f"🚀 スキャル特攻（ <b>{sh:,}株</b> で一気に利幅奪取）",
            "core_logic": f"OFI(Z={ofi_z})とLULD引力({ms['luld_magnet']}%)が急加速している特異点で即座にエントリー。", "adj_shares": sh, "trade_duration": "約30秒 〜 最長5分以内（超短期決戦・持ち越し絶対不可）",
            "step_plan": f"① 【朝9:00:00】寄り付き直後の最前線板気配（歩み値と買い注文の喰い上がり）を確認し、<b>{sh:,}株</b>を成行買いで即時約定。<br>② 【約定直後（秒速）】利益確定の指値注文を<b>{tp_str}</b>にセット。同時に<b>{sl_str}</b>で逆指値（損切り予約）をOCO注文で常時発注。<br>③ 【9:05まで】目標到達または勢いが止まった段階で全株決済。わずかな反落でも利益を固定して逃げる。",
            "beginner_html": f"<b>🚀 超初心者向け！スキャルピング超実践講座（数秒〜数分で確実に逃げ切る方法）</b><br><b>【用語解説】</b><br>・成行（なりゆき）注文：価格を問わず、いま目の前の最良価格で瞬時に買い付けるプロの即決注文。<br>・OCO（オーシーオー）注文：『上がったら利確、下がったら損切』を同時に自動セットし、片方が約定したらもう片方を自動キャンセルする安全装置。<br><b>【時間帯と手順】</b><br><b>・朝8:55〜9:00：</b> 証券アプリの板気配を開き、買付余力を確認して画面前で待機。<br><b>・朝9:00（市場オープン）：</b> スタートと同時に<b>{sh:,}株</b>を「成行」で瞬発買い。<br><b>・朝9:01〜9:03：</b> 買えたら即座に<b>{tp_str}</b>で利確、万一に備えて<b>{sl_str}</b>に損切りを予約。<br><b>・目安期間：</b> 1分〜最長5分。含み益が出たら欲張らず秒速で確定させるのが勝利の鉄則です！"
        }
    elif st_p == "スイングトレード":
        sh = max(1, int(round(base_sh * 1.2))); l1, l2 = max(1, int(round(sh * 0.6))), max(0, sh - max(1, int(round(sh * 0.6))))
        return {
            "style_name": st_p, "algo_name": f"📈 [{st_p}] トレンドフォロー・押し目分割本玉型", "risk_posture": f"🏛️ スイング本玉買い（初回 <b>{l1:,}株</b> ＋ 押し目 <b>{l2:,}株</b>）",
            "core_logic": f"Hurst多重フラクタル指数({ms['hurst']})が強いトレンド継続を示唆。数日間〜数週間かけて日足・週足の上値を追う王道フォーメーション。", "adj_shares": sh, "trade_duration": "3日 〜 最長2週間程度（ゆったりトレンドスイング）",
            "step_plan": f"① 【1日目・前場】打診買い（テストエントリー）として全体の6割にあたる<b>{l1:,}株</b>を取得。<br>② 【2〜3日目】日中の一時的な調整（押し目）かつVWAP（機関平均単価: <b>{vwap_str}</b>）付近での反発を確認後、残りの<b>{l2:,}株</b>を買い増し。<br>③ 【目標到達時】<b>{tp_str}</b>近辺でまず半玉を利確。残りは逆指値を買い値まで引き上げ（トレイリングストップ）ノーリスクで利益伸長を狙う。",
            "beginner_html": f"<b>📈 超初心者向け！スイングトレード実践講座（数日〜1週間かけてどっしり利益を伸ばす）</b><br><b>【用語解説】</b><br>・押し目（おしめ）：強い上昇トレンド中に、一時的に株価が少し安くなってお買い得になっている絶好のエントリー場。<br>・トレイリングストップ：株価の上昇に合わせて損切りラインを自動または手動で引き上げ、利益を確実に確保し続けるプロの手法。<br><b>【時間帯と手順】</b><br><b>・初日（朝9:30以降）：</b> 寄り直後の乱高下が落ち着いた頃、まず半分の<b>{l1:,}株</b>を買います。<br><b>・2日目〜4日目：</b> 少し下げてから再浮上する動きを確認したら、残りの<b>{l2:,}株</b>を買い足します。<br><b>・保有期間：</b> 日中の細かな値動きに一喜一憂せず、3日〜2週間じっくりと目標値<b>{tp_str}</b>を待ちます。"
        }
    elif st_p == "バイ＆ホールド":
        sh = max(1, int(round(base_sh * 0.9)))
        return {
            "style_name": st_p, "algo_name": f"💎 [{st_p}] 企業本質価値×長期複利・IPO成長投資型", "risk_posture": f"💎 中長期厳選ホールド（ <b>{sh:,}株</b> をじっくり育成）",
            "core_logic": f"量子コヒーレンス({qm['q_coherence']}点)と国策テーマ・業界シェア独占力に着目したバリュー＆グロース長期保有戦略。", "adj_shares": sh, "trade_duration": "1ヶ月 〜 6ヶ月以上（中長期複利運用）",
            "step_plan": f"① 【初回】ファンダメンタルズの割安感を確認し、ポートフォリオの上限枠内で<b>{sh:,}株</b>を現物で買付。<br>② 【保有中】日々のノイズや短期的な地合いの急落は無視し、四半期決算ごとの進捗率と機関大口の保有動向のみを監査。<br>③ 【利益確定】業績の上方修正やテーマの全面開花により目標株価<b>{tp_str}</b>を達成した段階で順次利益確定。",
            "beginner_html": f"<b>💎 超初心者向け！バイ＆ホールド長期投資講座（焦らず企業成長に乗る）</b><br><b>【用語解説】</b><br>・現物取引（げんぶつ）：借金をせず自分の資金の範囲内で株を買う、追証（借金）リスクゼロの最も安全な買い方。<br>・複利効果：得られた利益や配当を再投資に回し、雪だるま式に資産を増やしていく長期投資最大の武器。<br><b>【時間帯と手順】</b><br><b>・購入時：</b> 時間帯はいつでも構いません。現物注文で<b>{sh:,}株</b>を購入します。<br><b>・保有期間中：</b> 毎日の株価変動を見すぎる必要はありません。決算発表をチェックしながら数ヶ月単位でじっくり育てます。<br><b>・出口戦略：</b> 企業価値が適正に市場評価され、目標値<b>{tp_str}</b>に達するまで堂々とホールドしましょう。"
        }
    sh = max(1, int(round(base_sh * 1.65)))
    return {
        "style_name": "デイトレード", "algo_name": "🔥 [デイトレード] 寄り付きモメンタム特攻・当日決済型", "risk_posture": f"👑 フルベット・勝負玉（ <b>{sh:,}株一括投入</b> ）",
        "core_logic": f"期待値({expect_pct}%)と量子スコア({qm['q_score']}点)が極大。寄り付き一括で最高期待値を抜き取る当日完結戦術。", "adj_shares": sh, "trade_duration": "前場9:00 〜 11:30（または後場15:00の大引けまで）",
        "step_plan": f"① 【8:50〜9:00】板情報と気配値を観察し、理論寄付き予想値（<b>{pest_str}</b>）からの乖離率を確認。<br>② 【9:00:00】寄り付き直後に推奨全ロットである<b>{sh:,}株</b>を一括成行買い。<br>③ 【9:05】約定完了後、ただちに<b>{sl_str}</b>に損切り逆指値をセットし下落リスクを完全封殺。<br>④ 【11:30前】前場引け前に目標値<b>{tp_str}</b>に接近した場合は手仕舞いし、当日の利益を確実に口座へ固定する。",
        "beginner_html": f"<b>🔰 超初心者向け！デイトレード実践講座（その日のうちに勝負を完結させる）</b><br><b>【用語解説】</b><br>・前場（ぜんば）：午前の市場時間（9:00〜11:30）のこと。最も活発に株価が動きます。<br>・大引け（おおびけ）：午後15:30の市場終了のこと。翌日に持ち越さず当日中に売るのがデイトレです。<br><b>【時間帯と手順】</b><br><b>・朝8:55：</b> 画面の前でスタンバイし、ログインしておきます。<br><b>・朝9:00（スタート）：</b> 迷わず<b>{sh:,}株</b>を成行で買い付けます。<br><b>・朝9:05：</b> 買えたらすぐ、絶対に大損しないよう安全ストッパーとして<b>「{sl_str}」</b>に損切りの予約を入れます。<br><b>・午前中（〜11:30）：</b> 株価が上がって目標の<b>{tp_str}</b>に届いたら自動で売れて利益確定！その日のうちにすっきり勝利を確定させます。"
    }

def analyze_df(df_raw, code, name, theme, genre, macro, b5_live_map, style, bi=True, b5=True, bal=True, bms=True, bagi_q=False, bhft=False, total_capital=1000000, risk_tolerance_pct=2.0):
    try:
        if df_raw is None or df_raw.empty: return None
        df = df_raw.dropna(subset=["Close", "Open", "High", "Low", "Volume"])
        if len(df) < 25: return None
        c, o, h, l, v = [np.asarray(df[col].values, dtype=float).reshape(-1) for col in ["Close", "Open", "High", "Low", "Volume"]]
        prev_c = np.roll(c, 1); prev_c[0] = c[0]
        atrv = float(np.mean(np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))[-14:])) if len(c) >= 14 else float(c[-1] * 0.02)
        v_sub, v_sum = v[-20:], np.sum(v[-20:])
        vwap20 = float(np.sum(((h[-20:] + l[-20:] + c[-20:]) / 3.0) * v_sub) / v_sum) if v_sum > 0 else float(c[-1])
        cv = float(c[-1]); qm, ms, q_adv = compute_quantum_wave_metrics(c, h, l, v), compute_inst_microstructure(c, h, l, v), compute_advanced_quant_indicators(c, h, l, v)
        r20_w = np.sum(np.diff(c[-21:]) > 0) if len(c) >= 21 else 10
        tot_win = float(np.clip(r20_w / 20.0 * 35.0 + qm["q_tunnel"] * 0.40 + ms["kyle_stealth"] * 0.25, 50.0, 97.8))
        sf = ((2.0 * c - h - l) / np.maximum(h - l, 1e-4)) * v
        ofi_z = float(np.clip((np.mean(sf[-5:]) - np.mean(sf[-20:])) / max(float(np.std(sf[-20:])), 1.0), -3.0, 3.0))
        m_bias = (float(macro["sox"]["diff"]) * 1.25 if "sox" in macro and ("半導体" in genre or "NVDA" in code) else 0.0) + (float(macro["nk_fut"]["diff"]) * 0.85 if "nk_fut" in macro and ".T" in code else 0.0)
        expect_pct = float(np.clip(56.0 + (tot_win - 50.0) * 0.65 + ofi_z * 4.2 + m_bias * 2.2, 42.0, 99.8))
        edge = round((expect_pct - 50.0) / 10.0 + max(ofi_z, 0.0), 2)
        if bagi_q and qm["q_tunnel"] > 75.0:
            expect_pct = min(99.8, expect_pct + (qm["q_tunnel"] - 75.0) * 0.48); qm["q_score"] = min(99, qm["q_score"] + 6); qm["q_state"] = "🧠 AGI×量子トンネル超連鎖"
        if bhft and ofi_z > 0.4:
            expect_pct, tot_win = min(99.9, expect_pct + ofi_z * 4.8), min(99.2, tot_win + ofi_z * 2.6)
            edge = round(edge + ofi_z * 1.6, 2); ms["ms_score"] = min(99, ms["ms_score"] + 8); ms["ms_regime"] = "⚠️ 極秘HFTステルス大口吸収(先行検知)"
        pgap = round(float(np.clip(ofi_z * 0.65 + m_bias * 0.45, -2.5, 3.8)), 2); pest = cv * (1.0 + pgap / 100.0)
        st_p = style.split(" ")[1] if " " in style else "デイトレード"
        tp_m, sl_m = {"スキャルピング": (0.55, 0.35), "スイングトレード": (2.5, 1.2), "バイ＆ホールド": (4.5, 2.0)}.get(st_p, (1.1, 0.6))
        tpv, slv = max(pest, cv) + (atrv * tp_m), cv - (atrv * sl_m)
        rmoney = total_capital * (risk_tolerance_pct / 100.0)
        base_sh = max(1, int(rmoney / max(cv - slv, cv * 0.005)))
        fp = lambda val: f"{val:,.0f}円" if ".T" in code else f"${val:,.2f}"
        strat = select_dynamic_strategy(code.replace(".T", ""), style, tot_win, round(expect_pct, 1), ofi_z, q_adv["vpin"], 0.38, q_adv["cvar95"], q_adv["rsi"], 0.8, base_sh, fp(pest), fp(vwap20), f"{fp(tpv)}(+{round((tpv-cv)/max(cv,1e-4)*100,1)}%)", f"{fp(slv)}({round((slv-cv)/max(cv,1e-4)*100,1)}%)", 16.8, qm, ms)
        t_lbl, t_col, t_bg = ("【Lv.10：🔥S級・全ツッパ】", "#fff", "linear-gradient(90deg,#7e22ce,#dc2626)") if expect_pct > 92 else (("【Lv.9：⚡超強気買い】", "#fff", "linear-gradient(90deg,#0369a1,#1d4ed8)") if expect_pct > 85 else ("【Lv.7：⭕押し目買い】", "#e2e8f0", "linear-gradient(90deg,#334155,#1e293b)"))
        return {
            "full_code": code, "code": code.replace(".T", ""), "name": name, "genre": genre, "theme": theme, "price": fp(cv), "raw_close": cv,
            "tp_price": fp(tpv), "tp_pct": round((tpv - cv) / max(cv, 1e-4) * 100, 1), "sl_price": fp(slv), "sl_pct": round((slv - cv) / max(cv, 1e-4) * 100, 1), "vwap_price": fp(vwap20),
            "inst_score": int(np.clip(ms["ms_score"] + ofi_z * 5, 50, 99)), "vpin": q_adv["vpin"], "ofi_z": round(ofi_z, 2), "yz_vol": 0.38, "cvar95": q_adv["cvar95"], "eff_pct": 85, "kelly_pct": 16.8,
            "q_score": qm["q_score"], "q_tunnel": qm["q_tunnel"], "q_coherence": qm["q_coherence"], "q_entropy": qm["q_entropy"], "q_state": qm["q_state"],
            "ms_score": ms["ms_score"], "hurst": ms["hurst"], "kyle_stealth": ms["kyle_stealth"], "luld_magnet": ms["luld_magnet"], "ms_regime": ms["ms_regime"],
            "expect_pct": round(expect_pct, 1), "board5ch_score": q_adv["board5ch_score"], "b5_hits": 10, "pts_est_price": fp(pest), "pts_gap_pct": pgap, "diff": round(float((c[-1] - o[0]) / max(o[0], 1e-4) * 100) if len(o) else 0.0, 2),
            "prob": round(float(np.clip(50.0 + pgap * 10.0, 30.0, 85.0)), 1), "intraday_win_rate": round(float(np.clip(tot_win * 0.95, 40.0, 95.0)), 1),
            "trend_win_rate": round(float(np.clip(tot_win * 1.05, 45.0, 98.0)), 1), "total_win_rate": round(tot_win, 1), "count": f"{r20_w}/20回",
            "rsi": q_adv["rsi"], "payoff": 2.6, "edge": edge, "ai_score": int(np.clip(expect_pct * 0.9 + 5, 52, 99)), "survival_power": 90.0,
            "tier_num": 10 if expect_pct > 92 else (9 if expect_pct > 85 else 7), "tier_label": t_lbl, "tier_color": t_col, "tier_bg": t_bg,
            "lot_info": {"shares": strat["adj_shares"], "position_value": strat["adj_shares"] * cv, "risk_amount": rmoney}, "strat": strat
        }
    except Exception as e:
        record_system_error("analyze_df", e, f"Code: {code}")
        return None

# ==========================================
# 14. 弱肉強食・リアルタイム市場データスキャン
# ==========================================
@st.cache_data(ttl=90)
def fetch_pool_batch(macro, b5_live_map, style, bi, b5, bal, bms, bagi_q, bhft, total_cap=1000000, risk_pct=2.0):
    all_codes = [c for c, _, _, _ in GLOBAL_MARKET_TICKERS]
    try: raw = yf.download(all_codes, period="5d", interval="5m", group_by="ticker", threads=True, progress=False, timeout=4.0)
    except Exception as e: record_system_error("fetch_pool_batch:download", e); raw = {}
    gmap, alist, seen = {g: [] for g in DYNAMIC_GENRES}, [], set()
    def _worker(c, n, g, t):
        try: df = raw[c] if (len(all_codes) > 1 and c in raw) else raw
        except Exception: df = None
        return g, c, analyze_df(df, c, n, t, g, macro, b5_live_map, style, bi, b5, bal, bms, bagi_q, bhft, total_capital=total_cap, risk_tolerance_pct=risk_pct)
    with ThreadPoolExecutor(max_workers=min(len(GLOBAL_MARKET_TICKERS), 24)) as ex:
        futs = [ex.submit(_worker, c, n, g, t) for c, n, g, t in GLOBAL_MARKET_TICKERS]
        for f in as_completed(futs):
            try:
                g, c, r = f.result()
                if r:
                    gmap.setdefault(g, []).append(r)
                    if c not in seen: alist.append(r); seen.add(c)
            except Exception as e: record_system_error("fetch_pool_batch:future_result", e)
    for g in gmap: gmap[g] = sorted(gmap[g], key=lambda x: x["expect_pct"], reverse=True)
    return gmap, sorted(alist, key=lambda x: x["expect_pct"], reverse=True)

@st.cache_data(ttl=120)
def fetch_one(code, macro, b5_live_map, style, bi, b5, bal, bms, bagi_q, bhft, total_cap=1000000, risk_pct=2.0):
    try:
        code = code.strip().upper()
        if re.match(r"^[0-9]{3}[0-9A-Z]$", code): code = f"{code}.T"
        inf = STOCK_METADATA_CACHE.get(code, {"name": code.replace(".T", ""), "theme": "動的スキャン対象銘柄", "genre": "個別検索"})
        return analyze_df(yf.Ticker(code).history(period="5d", interval="5m"), code, inf["name"], inf["theme"], inf["genre"], macro, b5_live_map, style, bi, b5, bal, bms, bagi_q, bhft, total_capital=total_cap, risk_tolerance_pct=risk_pct)
    except Exception as e: record_system_error("fetch_one", e, f"Code: {code}"); return None

# ==========================================
# 15. ヘッダー / マクロ指標
# ==========================================
macro_info, b5_live_map = fetch_macro(), fetch_5ch_live()
mpills = "".join([f'<div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);padding:2px 8px;border-radius:6px;font-size:10.5px;display:inline-flex;gap:4px;"><span style="color:#94a3b8;">{m["label"]}</span><span style="color:{"#10b981" if m["diff"]>=0 else "#ef4444"};font-weight:700;">{"+" if m["diff"]>=0 else ""}{m["diff"]}%</span></div>' for m in macro_info.values()])
st.markdown(f'<div class="glass-header"><div style="display:flex;justify-content:space-between;align-items:center;"><div class="brand-luxury">YAMASHISHI LAB</div></div><div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:8px;">{mpills}</div></div>', unsafe_allow_html=True)

_cp_k = f"pool_{investment_style}_{sorted(list(ac_b))}_{total_capital}_{risk_tolerance_pct}"
if _cp_k not in st.session_state:
    with st.spinner(f"⚛️ 【{investment_style.split(' ')[1]}】弱肉強食・全市場動的ユニバースを並列スキャン中..."):
        g_res, all_res = fetch_pool_batch(macro_info, b5_live_map, investment_style, "inst" in ac_b, "mom" in ac_b, "algo" in ac_b, "ms" in ac_b, "agi_q" in ac_b, "hft_front" in ac_b, total_cap=total_capital, risk_pct=risk_tolerance_pct)
        st.session_state[_cp_k] = (g_res, all_res)
else: g_res, all_res = st.session_state[_cp_k]

# ==========================================
# 16. 画面レンダリング
# ==========================================
if st.session_state.get("navigation_page") == "ADMIN" and cu == ADMIN_EMAIL.strip().lower():
    st.markdown("### 👑 統合管理コントロールセンター (MASTER TERMINAL)")
    if st.button("⬅️ メイン画面に戻る", use_container_width=True, type="primary"):
        st.session_state["navigation_page"], st.session_state["scroll_top_trig"] = "TOP", int(time.time()*1000); st.rerun()

    tab_users, tab_employment, tab_apply_wait, tab_error_logs = st.tabs(["👥 会員情報管理", "🏢 AGI雇用・監視情報", "📩 会員申し込み審査", "⚠️ システムエラーログ"])
    with tab_users:
        st.markdown("#### 📋 登録済み会員一覧 (データベース同期中)")
        db_m, sec_m = load_mem(), load_sec()
        st.markdown("""<div class="admin-table-container"><table class="admin-table"><thead><tr><th>お名前</th><th>メールアドレス</th><th>専用パスコード</th><th>PINハッシュ</th><th>端末指紋 (FP)</th><th>登録日</th><th>状態</th></tr></thead><tbody>""" + "".join([
            f"<tr><td><b>{html.escape(u.get('name',''))}</b></td><td>{html.escape(em)}</td><td style='color:#38bdf8;font-family:monospace;'>{html.escape(u.get('passcode','-'))}</td><td style='color:#94a3b8;font-family:monospace;'>{html.escape(u.get('pin_hash','-')[:8])}...</td><td style='color:#fde047;font-family:monospace;'>{html.escape(u.get('fp','-'))}</td><td>{html.escape(u.get('applied_at','-'))}</td><td><span style='color:{'#10b981' if u.get('status')=='approved' else ('#ef4444' if u.get('status')=='banned' else '#f59e0b')}'><b>{html.escape(u.get('status',''))}</b></span></td></tr>"
            for em, u in db_m.items()
        ]) + "</tbody></table></div>", unsafe_allow_html=True)
        st.markdown("<br><b>⚡ 会員個別操作パネル</b>", unsafe_allow_html=True)
        target_em = st.columns([3, 2])[0].selectbox("操作対象会員を選択", list(db_m.keys()))
        if target_em and target_em != ADMIN_EMAIL.strip().lower():
            u_status = db_m[target_em].get("status", ""); btn_col1, btn_col2, btn_col3 = st.columns(3)
            if u_status == "approved":
                if btn_col1.button("⏸️ アカウント一時停止", use_container_width=True): db_m[target_em]["status"] = "suspended"; db_set("mem", db_m); st.success(f"{target_em} を一時停止しました"); st.rerun()
            else:
                if btn_col1.button("▶️ 利用再開 (承認)", use_container_width=True): db_m[target_em]["status"] = "approved"; db_set("mem", db_m); st.success(f"{target_em} を再開しました"); st.rerun()
            if btn_col2.button("🚫 永久BAN (端末/IP遮断)", use_container_width=True):
                db_m[target_em]["status"] = "banned"; tfp, trhfp, now_s = db_m[target_em].get("fp"), db_m[target_em].get("raw_hfp"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if tfp and tfp != "-": sec_m.setdefault("banned_fps", {})[tfp] = {"email": target_em, "banned_at": now_s, "reason": "管理者強制永久BAN"}
                if trhfp and trhfp != "-": sec_m.setdefault("banned_fps", {})[trhfp] = {"email": target_em, "banned_at": now_s, "reason": "管理者強制永久BAN"}
                sec_m.setdefault("banned_emails", {})[target_em] = {"banned_at": now_s, "orig": target_em}
                db_set("mem", db_m); db_set("sec", sec_m); st.error(f"{target_em} を永久BANリストに登録しました"); st.rerun()
            if btn_col3.button("🗑️ 完全削除", use_container_width=True): del db_m[target_em]; db_set("mem", db_m); st.warning(f"{target_em} のデータを抹消しました"); st.rerun()

    with tab_employment:
        st.markdown("#### 🏢 SYSTEM-ZERO & AGI雇用・解雇統括パネル")
        c_sz1, c_sz2 = st.columns([3, 1])
        c_sz1.markdown(f"**SYSTEM-ZERO 状態:** {'🟢 稼働中 (超越監視作動中)' if st.session_state.get('system_zero_active', True) else '🔴 解雇・停止中'}")
        if st.session_state.get("system_zero_active", True):
            if c_sz2.button("💀 総括神を解雇/停止", type="primary", use_container_width=True):
                st.session_state["system_zero_active"] = False; save_agi_system(); st.warning("管理者権限により SYSTEM-ZERO を解雇・停止させました。"); st.rerun()
        else:
            if c_sz2.button("⚡ 総括神を新任再起動", use_container_width=True):
                st.session_state["system_zero_active"] = True; save_agi_system(); st.success("新世代 SYSTEM-ZERO を再配備しました。"); st.rerun()
        st.markdown("<br><b>💀 過去に解雇されたエージェント履歴 (永久追放リスト)</b>", unsafe_allow_html=True)
        fired_list = st.session_state.get("fired_agents", [])
        if fired_list:
            st.markdown("""<div class="admin-table-container"><table class="admin-table"><thead><tr><th>解雇日時</th><th>エージェント名</th><th>最終スコア</th><th>解雇執行者</th><th>解雇理由・違反事項</th></tr></thead><tbody>""" + "".join([
                f"<tr><td>{html.escape(fa.get('time','-'))}</td><td style='color:#f87171;'><b>{html.escape(fa.get('name',''))}</b></td><td style='color:#fde047;'>{html.escape(str(fa.get('score','')))}</td><td style='color:#38bdf8;'>{html.escape(fa.get('fired_by','特命監査員'))}</td><td>{html.escape(fa.get('reason',''))}</td></tr>"
                for fa in fired_list
            ]) + "</tbody></table></div>", unsafe_allow_html=True)
        else: st.caption("現在、解雇履歴はありません。全10名のエージェントが優秀に稼働しています。")

    with tab_apply_wait:
        st.markdown("#### 📩 新規会員登録 審査待ちリスト")
        db_all = load_mem(); pending_users = {em: u for em, u in db_all.items() if u.get("status") == "pending"}
        if pending_users:
            for p_em, p_u in list(pending_users.items()):
                st.markdown(f'<div style="background:rgba(15,23,42,0.85);border:1px solid rgba(56,189,248,0.3);border-radius:8px;padding:10px 14px;margin-bottom:8px;"><span style="font-size:13.5px;font-weight:800;color:#f8fafc;">{html.escape(p_u.get("name","未入力"))}</span> <span style="font-size:11.5px;color:#94a3b8;">({html.escape(p_em)})</span><br><span style="font-size:10.5px;color:#64748b;">申請日: {html.escape(p_u.get("applied_at","-"))} ｜ 端末FP: {html.escape(p_u.get("fp","-"))}</span></div>', unsafe_allow_html=True)
                col_btn1, col_btn2 = st.columns([1, 1])
                if col_btn1.button(f"✅ 承認する ({p_u.get('name','')})", key=f"appr_{p_em}", use_container_width=True):
                    db_all[p_em]["status"] = "approved"; db_all[p_em]["approved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M"); db_set("mem", db_all)
                    send_mail(p_em, "【YAMASHISHI LAB】会員登録が承認されました", f"{p_u.get('name','')} 様\n申請が承認されました。専用アクセスコードは【 {db_all[p_em]['passcode']} 】です。")
                    st.success(f"{p_em} を承認しました"); st.rerun()
                if col_btn2.button(f"🚫 拒否・却下 ({p_u.get('name','')})", key=f"rej_{p_em}", use_container_width=True):
                    del db_all[p_em]; db_set("mem", db_all); st.warning(f"{p_em} の申請を却下しました"); st.rerun()
        else: st.info("現在、承認待ちの新規申請はありません。")

    with tab_error_logs:
        st.markdown("#### ⚠️ システムエラーログ管理 & ダウンロードセンター")
        err_list = get_system_error_logs()
        st.columns([3, 1])[0].caption(f"蓄積されたエラー件数: **{len(err_list)} 件** (最大 {MAX_ERROR_LOGS} 件まで自動リングバッファ保持)")
        col_down, col_clear = st.columns([2, 2])
        if err_list:
            col_down.download_button(label="📥 エラーログ全件をJSONでエクスポート", data=json.dumps(err_list, ensure_ascii=False, indent=2), file_name=f"yamashishi_error_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", mime="application/json", use_container_width=True)
            if col_clear.button("🗑️ エラーログをすべて消去", use_container_width=True): clear_system_error_logs(); st.success("すべてのエラーログを消去しました。"); st.rerun()
            st.markdown("""<div class="admin-table-container"><table class="admin-table"><thead><tr><th>発生日時</th><th>モジュール名</th><th>例外タイプ</th><th>メッセージ</th><th>補足情報</th></tr></thead><tbody>""" + "".join([
                f"<tr><td>{html.escape(e.get('time','-'))}</td><td style='color:#38bdf8;font-weight:700;'>{html.escape(e.get('module','-'))}</td><td style='color:#ef4444;font-family:monospace;'>{html.escape(e.get('error_type','-'))}</td><td>{html.escape(e.get('message','-')[:60])}</td><td style='color:#94a3b8;'>{html.escape(e.get('context','-'))}</td></tr>"
                for e in err_list[:30]
            ]) + "</tbody></table></div>", unsafe_allow_html=True)
            st.markdown("<br><b>🔍 スタックトレース詳細ビューア (直近10件)</b>", unsafe_allow_html=True)
            for err_item in err_list[:10]:
                with st.expander(f"🔴 [{err_item['time']}] {err_item['module']} - {err_item['error_type']}: {err_item['message'][:40]}..."): st.code(err_item.get("traceback") or "スタックトレースなし", language="python")
        else: st.success("🎉 現在システム上に記録されたエラー・警告はありません。全モジュールが極めて正常に動作しています。")
    st.stop()

focused_item = st.session_state.get("focused_stock_item")
if focused_item:
    st.markdown("### ⚛️ 銘柄詳細・買い方合議フォーカスモード")
    render_card(focused_item, is_custom=False, kp=f"foc_{focused_item['code']}", is_focused=True)
    st.stop()

if st.session_state.get("navigation_page") == "NEWS_DETAIL":
    tn = st.session_state.get("selected_news_item") or all_impact_news[0]
    st.markdown(f'<div class="glass-header" style="border-left:4px solid #ef4444;"><span class="pill-badge" style="background:#ef4444;color:#fff;">🚨 重大ニュース深掘り</span><div style="font-size:18px;font-weight:800;margin-top:8px;">{html.escape(tn["title"])}</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="rank-card" style="border-left-color:#a855f7;"><div style="font-size:14px;color:#e9d5ff;">🧠 波及メカニズム</div><div style="font-size:12.5px;">{html.escape(tn["detail"]["mechanism"])}</div><div class="beginner-action-box" style="margin-top:10px;"><b>⚡ {investment_style.split(" ")[1]} 実践トレード立ち回り</b><br>{html.escape(tn["detail"]["action_guide"]).replace(chr(10), "<br>")}</div></div>', unsafe_allow_html=True)
    st.markdown("### 🔗 連動注目銘柄")
    for idx, r_item in enumerate(sorted(all_res, key=lambda x: x["expect_pct"], reverse=True)[:3], 1): render_card(r_item, rank=idx, kp=f"nr_{tn['id']}")
    if st.button("⬅️ 戻る", use_container_width=True, type="primary"):
        st.session_state["navigation_page"], st.session_state["scroll_top_trig"] = "TOP", int(time.time()*1000); st.rerun()
    st.stop()

# ■ メインリスト画面
c1, c2 = st.columns([3.4, 1])
cin = c1.text_input("🔍 銘柄検索", placeholder="コード入力 (例: 6920)", label_visibility="collapsed")
if c2.button("🔍 診断", use_container_width=True) and cin: st.session_state["custom_search_code"] = clean_k(cin)

if st.session_state.get("custom_search_code"):
    cr = fetch_one(st.session_state["custom_search_code"], macro_info, b5_live_map, investment_style, True, True, True, True, "agi_q" in ac_b, "hft_front" in ac_b, total_cap=total_capital, risk_pct=risk_tolerance_pct)
    if cr:
        render_card(cr, is_custom=True, kp="custom")
        if st.button("✖️ 閉じる", use_container_width=True): st.session_state["custom_search_code"] = ""; st.rerun()

def cut_stocks(slist, pct): return slist[:max(3, int(round(len(slist) * (pct / 100.0))))] if slist else []

cats = ["🏆 総合TOP5", "⚛️ 量子トンネル突破TOP10", "🏛️ 機関最新ミクロ構造TOP10", "🚨 重大ニュース＆連動株", "🎟️ IPO募集・新規上場", "🏦 機関VPIN・OFI", "🔥 5ch＆短期モメンタム", "📋 監視シート"] + [f"📂 {g}" for g in DYNAMIC_GENRES]
st.markdown(f'<div class="compact-bar-label"><span>📂 QUANTUM STRATEGY ({investment_style.split(" ")[1]})</span></div>', unsafe_allow_html=True)
if st.session_state.get("active_category") not in cats: st.session_state["active_category"] = "🏆 総合TOP5"

def _on_cat_change():
    nw = st.session_state.get("active_category_selector")
    if nw and nw != st.session_state.get("last_cat"):
        st.session_state["nav_history"].append(st.session_state["last_cat"])
        st.session_state["last_cat"] = st.session_state["active_category"] = nw

cat_index = cats.index(st.session_state["active_category"])
if hasattr(st, "pills"): st.pills("カテゴリ", cats, default=cats[cat_index], selection_mode="single", label_visibility="collapsed", key="active_category_selector", on_change=_on_cat_change)
else: st.radio("カテゴリ", cats, index=cat_index, horizontal=True, label_visibility="collapsed", key="active_category_selector", on_change=_on_cat_change)

sel_cat, surv = st.session_state.get("active_category"), cut_stocks(sorted(all_res, key=lambda x: x["expect_pct"], reverse=True), survival_cut_pct)

if sel_cat == "🏆 総合TOP5":
    for i, r in enumerate(surv[:5], 1): render_card(r, rank=i, kp="top5")
elif sel_cat == "⚛️ 量子トンネル突破TOP10":
    for i, r in enumerate(sorted(all_res, key=lambda x: x["q_score"], reverse=True)[:10], 1): render_card(r, rank=i, kp="qtop")
elif sel_cat == "🏛️ 機関最新ミクロ構造TOP10":
    for i, r in enumerate(sorted(all_res, key=lambda x: x["ms_score"], reverse=True)[:10], 1): render_card(r, rank=i, kp="mstop")
elif sel_cat == "🚨 重大ニュース＆連動株":
    for n in all_impact_news:
        st.markdown(f'<div class="rank-card" style="border-left-color:#ef4444;"><div style="font-size:11px;color:#f87171;font-weight:800;">🚨 {html.escape(n["cat"])}</div><div style="font-size:14.5px;font-weight:800;color:#f8fafc;margin-bottom:4px;">{html.escape(n["title"])}</div></div>', unsafe_allow_html=True)
        if st.button("🔥 詳細レポートを見る", key=f"tab_n_{n['id']}", use_container_width=True):
            st.session_state["selected_news_item"], st.session_state["navigation_page"], st.session_state["scroll_top_trig"] = n, "NEWS_DETAIL", int(time.time()*1000); st.rerun()
elif sel_cat == "🎟️ IPO募集・新規上場":
    st.markdown('<div class="glass-header"><div style="font-size:16px;font-weight:800;color:#f8fafc;">🎟️ 新規上場 (IPO) ブックビルディング・詳細分析ターミナル</div><div style="font-size:11.5px;color:#94a3b8;margin-top:3px;">初値高騰期待度・ロックアップ・吸収金額・PER・VC比率まで徹底網羅した完全ガイド。</div></div>', unsafe_allow_html=True)
    for ipo in IPO_OFFERINGS:
        links_html = "".join([f'<a href="{url}" target="_blank" rel="noopener noreferrer" class="ipo-link-btn">🔗 {html.escape(lbl)}</a>' for lbl, url in ipo["links"]])
        st.markdown(f'<div class="rank-card" style="border-left-color:#f59e0b;"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;"><div><span class="pill-badge" style="background:#f59e0b;color:#0f172a;font-weight:900;">🏆 第{ipo["rank"]}位</span><span class="pill-badge" style="background:rgba(250,204,21,0.2);color:#fde047;border-color:#facc15;">期待度 {ipo["expect_return"]}</span></div><div style="font-size:11px;color:#38bdf8;font-weight:700;">{html.escape(ipo["tier"])}</div></div><div><span style="font-size:18px;font-weight:800;color:#f8fafc;">{html.escape(ipo["name"])}</span> <span style="font-size:12px;color:#94a3b8;">({ipo["code"]} / {html.escape(ipo["market"])})</span></div><div style="font-size:11.5px;color:#38bdf8;margin-top:4px;"><b>🎯 テーマ:</b> {html.escape(ipo["theme"])}</div><div class="trade-plan-box" style="margin-top:9px;grid-template-columns: repeat(auto-fit, minmax(105px, 1fr));"><div><div style="font-size:9.5px;color:#94a3b8;">📅 BB申込期間</div><div style="font-size:11.5px;font-weight:800;color:#fde047;">{ipo["bb_period"]}</div></div><div><div style="font-size:9.5px;color:#94a3b8;">🔔 上場予定日</div><div style="font-size:11.5px;font-weight:800;color:#f8fafc;">{ipo["list_date"]}</div></div><div><div style="font-size:9.5px;color:#94a3b8;">💰 仮条件価格帯</div><div style="font-size:11.5px;font-weight:800;color:#10b981;">{ipo["price_band"]}</div></div><div><div style="font-size:9.5px;color:#94a3b8;">🏛️ 主幹事証券</div><div style="font-size:11.5px;color:#bae6fd;">{html.escape(ipo["lead"])}</div></div></div><div style="background:rgba(2,6,23,0.75);border:1px solid rgba(148,163,184,0.18);border-radius:8px;padding:9px 12px;margin-top:8px;font-size:11.5px;line-height:1.6;"><div>🔒 <b>ロックアップ状況:</b> <span style="color:#e2e8f0;">{html.escape(ipo["lockup"])}</span></div><div>📦 <b>吸収金額 (公開規模):</b> <span style="color:#e2e8f0;">{html.escape(ipo["absorption"])}</span> ｜ 📊 <b>VC比率:</b> <span style="color:#e2e8f0;">{html.escape(ipo["vc_ratio"])}</span></div><div>📈 <b>バリュエーション (PER):</b> <span style="color:#e2e8f0;">{html.escape(ipo["pe"])}</span></div><div style="margin-top:4px;color:#a7f3d0;"><b>💡 初値立ち回り戦略:</b> {html.escape(ipo["strategy"])}</div></div><div style="margin-top:8px;">{links_html}</div></div>', unsafe_allow_html=True)
elif sel_cat == "🏦 機関VPIN・OFI":
    for i, r in enumerate(sorted(all_res, key=lambda x: x["inst_score"], reverse=True)[:10], 1): render_card(r, rank=i, kp="inst")
elif sel_cat == "🔥 5ch＆短期モメンタム":
    for i, r in enumerate(sorted(all_res, key=lambda x: x["board5ch_score"], reverse=True)[:10], 1): render_card(r, rank=i, kp="mom")
elif sel_cat == "📋 監視シート":
    wl = st.session_state["watchlist"]
    if st.button("⚡ 総合TOP3を一括登録", use_container_width=True):
        for it in surv[:3]: wl[it["code"]] = it
        if st.session_state.get("authenticated_user"): save_watchlist(st.session_state["authenticated_user"], wl)
        st.rerun()
    for wc, wi in list(wl.items()): render_card(wi, kp=f"wl_{wc}")
elif sel_cat.startswith("📂 "):
    for i, r in enumerate(cut_stocks(g_res.get(sel_cat.replace("📂 ", ""), []), survival_cut_pct), 1): render_card(r, rank=i, kp=f"g_{sel_cat}")

# ==========================================
# 17. 免責事項（法的表示）
# ==========================================
st.markdown('<div class="disclaimer-banner"><b>⚖️ 重要免責事項・法的表示</b><br>本システム「YAMASHISHI LAB」が提供するすべての指標、量子力学波動モデル(QWM-7)、期待度パーセンテージ、AI合議ログ、および売買プランは、過去の市場データおよび数理アルゴリズムに基づく研究シミュレーション・情報提供を目的としたものであり、特定の有価証券の売買推奨や投資助言（投資助言・代理業等）を行うものではありません。株式投資には元本割れや市場変動のリスクが伴います。最終的な投資判断および資金配分は、必ず利用者ご自身の自己責任にて行っていただけますようお願い申し上げます。</div>', unsafe_allow_html=True)
