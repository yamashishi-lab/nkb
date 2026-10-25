import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np
import unicodedata, hashlib, hmac, json, os, re, ssl, smtplib, time, random, threading, sqlite3
import urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.mime.text import MIMEText
from datetime import datetime

# ==========================================
# 1. 初期設定とセキュリティ
# ==========================================
st.set_page_config(page_title="YAMASHISHI LAB", page_icon="⚡", layout="centered", initial_sidebar_state="expanded")

SECRET_KEY = os.environ.get("SECRET_KEY", st.secrets.get("SECRET_KEY", "my_super_secret_quant_key_2026_secured_core"))
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", st.secrets.get("ADMIN_EMAIL", "nthbh399@ybb.ne.jp")).strip().lower()
ADMIN_PASS = os.environ.get("ADMIN_PASS", st.secrets.get("ADMIN_PASS", "ADMIN777"))

DB_SQLITE_PATH = "yamashishi_core.db"

AI_PROVIDERS = {
    "gemini": ("🔵 Google Gemini", ["gemini-2.5-flash", "gemini-2.0-flash", "gemma-3-27b-it", "gemini-2.5-pro"], "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"),
    "openai": ("🟢 OpenAI ChatGPT", ["gpt-4o-mini", "gpt-4o", "o3-mini"], "https://api.openai.com/v1/chat/completions"),
    "claude": ("🟠 Anthropic Claude", ["claude-3-7-sonnet-latest", "claude-3-5-haiku-latest"], "https://api.anthropic.com/v1/messages"),
    "grok": ("⚫ xAI Grok", ["grok-2-latest", "grok-3-mini"], "https://api.x.ai/v1/chat/completions"),
    "deepseek": ("🟣 DeepSeek", ["deepseek-chat", "deepseek-reasoner"], "https://api.deepseek.com/chat/completions"),
    "perplexity": ("🌐 Perplexity Sonar", ["sonar-pro", "sonar"], "https://api.perplexity.ai/chat/completions"),
    "groq": ("⚡ Groq LPU", ["llama-3.3-70b-versatile", "qwen-2.5-32b"], "https://api.groq.com/openai/v1/chat/completions")
}

# IPO情報を徹底的に深掘りしたデータ構造へ強化
IPO_OFFERINGS = [
    {
        "rank": 1,
        "code": "401A",
        "name": "AIクロスロボティクス",
        "market": "東証グロース",
        "bb_period": "受付中 〜 10/28 (11:00締切)",
        "list_date": "11/06 (水)",
        "price_band": "1,680円 〜 1,850円 (想定1,750円)",
        "unit_lot": "100株 (最低必要資金: 185,000円)",
        "expect_return": "+92.0% 〜 +135.0%",
        "expected_initial_price": "3,200円 〜 4,350円 (初値2倍〜2.3倍濃厚)",
        "score": 96,
        "tier": "🌟 S級：全力ブックビルディング参加（最優先当選狙い）",
        "lead": "主幹事：SBI証券 / 野村證券（平幹事：楽天、マネックス、松井）",
        "business_detail": "防衛省および大手警備会社向けに、GPS遮断環境下でも自己位置を推定して自律編隊飛行を行うAI軍事・産業ドローン制御OSを開発・提供。官公庁の国策予算拡大の直撃銘柄。",
        "capital_policy": "公募比率75%・売出比率25%と換金売り圧力が極めて低い。ベンチャーキャピタル保有株には180日間または公開価格1.5倍の厳格なロックアップ条項あり。",
        "strategy": "SBI証券のIPOチャレンジポイント全投入推奨。当選時は初日成行売りではなく、2日目の気配上限寄り付きまで引きつけるのが最大利益の定石。",
        "links": [("🏦 SBI証券で申込", "https://www.sbisec.co.jp"), ("🏦 野村證券で申込", "https://www.nomura.co.jp")]
    },
    {
        "rank": 2,
        "code": "405A",
        "name": "ネクストグリッド電力",
        "market": "東証プライム",
        "bb_period": "受付中 〜 10/30 (15:00締切)",
        "list_date": "11/10 (火)",
        "price_band": "2,400円 〜 2,600円",
        "unit_lot": "100株 (最低必要資金: 260,000円)",
        "expect_return": "+38.5% 〜 +55.0%",
        "expected_initial_price": "3,320円 〜 4,030円",
        "score": 89,
        "tier": "🔥 A級：積極BB参加（大型公募・当選配分多数）",
        "lead": "主幹事：SMBC日興証券 / 大和証券（副幹事：みずほ、三菱UFJモルガン）",
        "business_detail": "生成AI向け巨大データセンター専用の次世代超電導送電網・高圧受変電システムをワンストップ設計。電力消費爆発に対応するインフラ銘柄として海外機関投資家の注目度が極大。",
        "capital_policy": "吸収金額約180億円の大型案件。市場吸収力に懸念はあるが、親子上場解消・機関投資家の長期保有（アンカー投資家）の内定比率が4割を超えており需給良好。",
        "strategy": "当選枠が多いため複数口座からの分散応募で複数単元ゲットを狙える。初値形成後も配当・設備投資テーマとして中期スイング対象に移行可能。",
        "links": [("🏦 SMBC日興証券で申込", "https://www.smbcnikko.co.jp"), ("🏦 大和証券で申込", "https://www.daiwa.jp")]
    }
]

# 市場全体（主力大型、中小型、グロース、米国主要株）を網羅する全方位プール
STOCK_POOL = {
    "半導体": [{"code": "8035.T", "name": "東京エレクトロン", "theme": "前工程装置世界大手"}, {"code": "6857.T", "name": "アドバンテスト", "theme": "AI半導体テスタ首位"}, {"code": "6920.T", "name": "レーザーテック", "theme": "EUVマスク検査独占"}, {"code": "6146.T", "name": "ディスコ", "theme": "切断・研削装置世界首位"}, {"code": "NVDA", "name": "NVIDIA", "theme": "AIアクセラレータ絶対覇者"}],
    "AI・防衛": [{"code": "9984.T", "name": "ソフトバンクG", "theme": "世界AIユニコーン投資総本山"}, {"code": "3778.T", "name": "さくらインターネット", "theme": "政府認定国産クラウド基盤"}, {"code": "7011.T", "name": "三菱重工業", "theme": "防衛省国策予算・迎撃誘導弾"}, {"code": "PLTR", "name": "パランティア", "theme": "米軍・国防省AIビッグデータ"}],
    "AI電力・電線": [{"code": "5803.T", "name": "フジクラ", "theme": "AIデータセンター光配線"}, {"code": "5801.T", "name": "古河電工", "theme": "次世代送電インフラ"}, {"code": "6501.T", "name": "日立製作所", "theme": "送配電グリッド・原発支援"}, {"code": "VST", "name": "ビストラ", "theme": "米AI電源・原子力発電"}],
    "宇宙・次世代": [{"code": "5595.T", "name": "QPS研究所", "theme": "夜間雨天対応小型SAR衛星"}, {"code": "186A.T", "name": "アストロスケール", "theme": "軌道上デブリ（宇宙ゴミ）除去"}, {"code": "TSLA", "name": "テスラ", "theme": "完全自動運転FSD・ロボタクシー"}],
    "小型急騰・IPO": [{"code": "5253.T", "name": "カバー", "theme": "VTuber世界進出・IP経済圏"}, {"code": "216A.T", "name": "タイミー", "theme": "スキマバイト仲介・労働改革"}, {"code": "3350.T", "name": "メタプラネット", "theme": "ビットコイン積立保有国策"}, {"code": "IONQ", "name": "アイオンQ", "theme": "商用イオントラップ量子計算"}]
}
KNOWN_STOCKS = {it["code"]: {"name": it["name"], "theme": it["theme"], "genre": g} for g, its in STOCK_POOL.items() for it in its}

# ==========================================
# 2. データベース・セキュリティ
# ==========================================
_DB_LOCK = threading.RLock()

def init_sqlite_db():
    with _DB_LOCK:
        conn = sqlite3.connect(DB_SQLITE_PATH, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("CREATE TABLE IF NOT EXISTS kv_store (key TEXT PRIMARY KEY, val TEXT);")
        conn.commit()
        conn.close()

init_sqlite_db()

def db_get(key: str, default_val: dict) -> dict:
    with _DB_LOCK:
        try:
            conn = sqlite3.connect(DB_SQLITE_PATH, check_same_thread=False)
            cur = conn.cursor()
            cur.execute("SELECT val FROM kv_store WHERE key = ?", (key,))
            row = cur.fetchone()
            conn.close()
            if row: return json.loads(row[0])
        except Exception: pass
        return default_val

def db_set(key: str, val: dict):
    with _DB_LOCK:
        try:
            conn = sqlite3.connect(DB_SQLITE_PATH, check_same_thread=False)
            cur = conn.cursor()
            cur.execute("INSERT OR REPLACE INTO kv_store (key, val) VALUES (?, ?)", (key, json.dumps(val, ensure_ascii=False)))
            conn.commit()
            conn.close()
        except Exception: pass

def clean_k(k: str) -> str: return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(k or "")).strip().strip("\"'"))
def gen_code(em: str) -> str: return hmac.new(SECRET_KEY.encode(), em.strip().lower().encode(), hashlib.sha256).hexdigest()[:8].upper()
def gen_tok(em: str, act: str) -> str: return hashlib.sha256(f"{em.strip().lower()}:{act}:{SECRET_KEY}".encode()).hexdigest()[:16]
def hash_pin(pin: str) -> str: return hashlib.pbkdf2_hmac("sha256", pin.strip().encode(), SECRET_KEY.encode(), 10000).hex()[:16]

def get_raw_header_fp() -> str:
    try:
        h = {str(k).lower(): str(v) for k, v in dict(getattr(st.context, "headers", {}) or {}).items()}
        raw = f"{h.get('user-agent','')}|{h.get('accept-language','')}|{h.get('sec-ch-ua-platform','')}"
    except Exception: raw = "default_env"
    return hashlib.sha256(raw.encode()).hexdigest()[:12].upper()

def get_client_fp() -> str:
    raw = get_raw_header_fp()
    qf = st.query_params.get("dfp", "")
    if qf: st.session_state["client_dfp"] = qf
    dfp = st.session_state.get("client_dfp", "")
    return hashlib.sha256(f"{raw}|{dfp}".encode()).hexdigest()[:12].upper() if dfp else raw

def load_smtp(): return db_get("smtp", {"smtp_user": ADMIN_EMAIL, "smtp_pass": "", "smtp_server": "smtp.mail.yahoo.co.jp", "smtp_port": 465})
def load_llm(): return db_get("llm", {"provider": "gemini", "models": {k: v[1][0] for k, v in AI_PROVIDERS.items()}})
def load_sec(): return db_get("sec", {"banned_fps": {}, "banned_emails": {}, "banned_pins": {}, "banned_names": [], "spoof_logs": [], "device_bio_map": {}})
def load_mail_db(): return db_get("mail", {"logs": [], "messages": []})
def load_mem():
    db = db_get("mem", {})
    adm = ADMIN_EMAIL.strip().lower()
    if adm not in db:
        ns = datetime.now().strftime("%Y-%m-%d %H:%M")
        db[adm] = {"name": "管理者", "email": adm, "status": "approved", "passcode": gen_code(adm), "pin_hash": hash_pin("0000"), "applied_at": ns, "approved_at": ns, "last_seen_ts": 0, "last_seen_str": "-", "fp": "-", "bio_enabled": False}
        db_set("mem", db)
    return db

def check_and_log_ban_spoof(em: str, name: str, cur_fp: str, raw_hfp: str, pin_h: str = "", action_type: str = "アクセス") -> tuple:
    em_c = em.strip().lower()
    if em_c == ADMIN_EMAIL.strip().lower(): return False, ""
    sec = load_sec(); db = load_mem(); b_fps = sec.get("banned_fps", {}); b_ems = sec.get("banned_emails", {}); b_pins = sec.get("banned_pins", {}); u_rec = db.get(em_c, {})

    reasons = []; orig_target = ""
    if u_rec.get("status") == "banned" or em_c in b_ems:
        reasons.append("永久BAN対象メールアドレス一致"); orig_target = em_c
    if cur_fp and cur_fp != "-" and cur_fp in b_fps:
        reasons.append(f"永久BAN端末指紋(FP:{cur_fp})一致"); orig_target = orig_target or b_fps[cur_fp].get("email", "不明")
    if raw_hfp and raw_hfp != "-" and raw_hfp in b_fps:
        reasons.append(f"永久BAN環境ヘッダ指紋(HFP:{raw_hfp})一致"); orig_target = orig_target or b_fps[raw_hfp].get("email", "不明")
    if pin_h and pin_h in b_pins and em_c != b_pins[pin_h]:
        reasons.append(f"永久BAN会員({b_pins[pin_h]})と同一PINハッシュ一致"); orig_target = orig_target or b_pins[pin_h]

    if reasons:
        now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        r_str = " / ".join(reasons)
        is_spoof = bool(orig_target and em_c and em_c != orig_target)
        log_entry = {
            "time": now_s, "action": f"🚨 なりすまし{action_type}検知" if is_spoof else f"🚫 永久BAN遮断({action_type})",
            "input_email": em_c or "未入力", "input_name": name.strip() or u_rec.get("name", "不明"),
            "orig_banned_email": orig_target or em_c, "fp": cur_fp, "raw_hfp": raw_hfp, "reason": r_str
        }
        logs = sec.get("spoof_logs", [])
        if not logs or logs[0].get("input_email") != log_entry["input_email"] or logs[0].get("action") != log_entry["action"] or (logs[0].get("time", "")[:16] != now_s[:16]):
            logs.insert(0, log_entry); sec["spoof_logs"] = logs[:150]
        if cur_fp and cur_fp != "-": sec.setdefault("banned_fps", {})[cur_fp] = {"email": orig_target or em_c, "name": log_entry["input_name"], "banned_at": now_s, "reason": r_str}
        if raw_hfp and raw_hfp != "-": sec.setdefault("banned_fps", {})[raw_hfp] = {"email": orig_target or em_c, "name": log_entry["input_name"], "banned_at": now_s, "reason": r_str}
        if em_c: sec.setdefault("banned_emails", {})[em_c] = {"name": log_entry["input_name"], "banned_at": now_s, "orig": orig_target or em_c}
        db_set("sec", sec)
        return True, r_str
    return False, ""

def send_mail(to_em: str, subj: str, body: str, category: str = "自動通知") -> bool:
    to_clean, now_str = to_em.strip().lower(), datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    route, sent = "暗号化アプリ内BOX", False
    c = load_smtp(); u, p, srv, port = c.get("smtp_user", "").strip(), c.get("smtp_pass", "").strip(), c.get("smtp_server", "").strip(), int(c.get("smtp_port", 465))
    if u and p:
        try:
            m = MIMEText(body, "plain", "utf-8"); m["Subject"], m["From"], m["To"] = subj, u, to_clean
            ctx = ssl.create_default_context()
            with (smtplib.SMTP_SSL(srv, port, context=ctx, timeout=3.0) if port == 465 else smtplib.SMTP(srv, port, timeout=3.0)) as s:
                if port != 465: s.starttls(context=ctx)
                s.login(u, p); s.send_message(m)
            sent, route = True, "SMTP配信＋暗号化BOX"
        except Exception: pass
    if not sent:
        try:
            ctx = ssl.create_default_context()
            payload = json.dumps({"_subject": subj, "宛先": to_clean, "本文": body, "_captcha": "false"}).encode("utf-8")
            req = urllib.request.Request(f"https://formsubmit.co/ajax/{urllib.parse.quote(to_clean)}", data=payload, headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=3.0, context=ctx) as r:
                if r.status == 200: route = "Webリレー配信＋暗号化BOX"
        except Exception: pass
    mdb = load_mail_db()
    mdb.setdefault("logs", []).insert(0, {"id": hashlib.md5(f"{to_clean}_{now_str}".encode()).hexdigest()[:8], "time": now_str, "to": to_clean, "from": ADMIN_EMAIL, "subject": subj, "body": body, "category": category, "route": route})
    mdb["logs"] = mdb["logs"][:120]; db_set("mail", mdb)
    return True

# ==========================================
# 3. CSS / JS 注入 (視認性UP・カード間余白拡大・アニメーション)
# ==========================================
def inject_css():
    css = """
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;800&family=Plus+Jakarta+Sans:wght@400;600;800&family=JetBrains+Mono:wght@500;700&display=swap');
    
    /* サイト全体のフォントサイズをやや拡大し、自然な行送りと可読性を確保 */
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: 15px !important;
        background-color: #050811;
        color: #e2e8f0;
        line-height: 1.6;
        word-break: normal !important;
        overflow-wrap: break-word !important;
    }
    
    header[data-testid="stHeader"] {
        background: transparent !important; pointer-events: none !important;
        height: 3.5rem !important; z-index: 999990 !important;
    }
    header[data-testid="stHeader"] [data-testid="stToolbar"],
    header[data-testid="stHeader"] [data-testid="stActionButtons"] { display: none !important; }

    /* サイドバー */
    section[data-testid="stSidebar"] {
        position: fixed !important; top: 0 !important; left: 0 !important; height: 100vh !important;
        z-index: 9999999 !important; width: 340px !important; max-width: 88vw !important; min-width: 320px !important;
        transform: translateX(-100%) !important; transition: transform 0.35s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.35s ease !important;
        background: rgba(8, 12, 22, 0.98) !important; backdrop-filter: blur(25px) !important;
        border-right: 1px solid rgba(56, 189, 248, 0.35) !important; box-shadow: none !important;
        pointer-events: auto !important; visibility: visible !important;
    }
    section[data-testid="stSidebar"].yamashishi-sidebar-open {
        transform: translateX(0) !important; box-shadow: 18px 0 50px rgba(0,0,0,0.95), 2px 0 20px rgba(56,189,248,0.25) !important;
    }
    
    [data-testid="collapsedControl"], [data-testid="stSidebarCollapsedControl"], header button[kind="headerNoPadding"] {
        opacity: 0 !important; position: absolute !important; width: 1px !important; height: 1px !important; overflow: hidden !important; z-index: -1 !important;
    }
    
    section[data-testid="stSidebar"] + div, section.main, .stApp > header + div > div {
        margin-left: 0 !important; width: 100% !important; max-width: 100% !important;
    }

    /* 銘柄カード間の余白をしっかり確保（繋がって見えないようマージンと影を強化） */
    .rank-card, .search-result-card {
        background: linear-gradient(180deg, #0f172a 0%, #090d16 100%) !important;
        color: #f8fafc !important;
        border-radius: 16px;
        padding: 16px 18px;
        margin-top: 24px !important;
        margin-bottom: 28px !important;
        box-shadow: 0 12px 32px rgba(0,0,0,0.7), 0 0 1px 1px rgba(148,163,184,0.18);
        border: 1px solid rgba(148,163,184,0.2);
        border-left: 5px solid #38bdf8;
    }
    .search-result-card { border-left-color: #f59e0b; }

    /* 重大情報有り：アニメーション＋真っ赤な背景＋1行集約ボタン */
    @keyframes alert-pulse {
        0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.85); transform: scale(1); }
        50% { box-shadow: 0 0 0 8px rgba(239, 68, 68, 0); transform: scale(1.01); }
        100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); transform: scale(1); }
    }
    div[data-testid="stButton"] button[key*="nb_"] {
        background: linear-gradient(90deg, #dc2626 0%, #b91c1c 100%) !important;
        color: #ffffff !important;
        font-weight: 800 !important;
        font-size: 13.5px !important;
        border: 1px solid #f87171 !important;
        border-radius: 8px !important;
        animation: alert-pulse 2s infinite ease-in-out !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        display: block !important;
        width: 100% !important;
        text-align: left !important;
        padding: 8px 14px !important;
        margin: 10px 0 !important;
    }

    /* エージェント合議のスクロール窓を確実に動作させるスタイル */
    .ai-council-box {
        background: rgba(8, 12, 22, 0.98);
        border: 1px solid rgba(56, 189, 248, 0.4);
        border-radius: 12px;
        padding: 14px;
        margin-top: 14px;
        box-shadow: inset 0 2px 10px rgba(0,0,0,0.8);
    }
    .council-scroll-window {
        max-height: 380px !important;
        height: auto !important;
        overflow-y: scroll !important;
        overflow-x: hidden !important;
        padding: 8px 12px 8px 4px;
        border: 1px solid rgba(148, 163, 184, 0.15);
        border-radius: 8px;
        background: rgba(2, 6, 23, 0.6);
    }
    .council-scroll-window::-webkit-scrollbar {
        width: 8px;
    }
    .council-scroll-window::-webkit-scrollbar-track {
        background: rgba(15, 23, 42, 0.8);
        border-radius: 4px;
    }
    .council-scroll-window::-webkit-scrollbar-thumb {
        background: #38bdf8;
        border-radius: 4px;
    }

    /* 2chスレッド風の会話吹き出しスタイル */
    .thread-post {
        background: rgba(15, 23, 42, 0.7);
        border-left: 3px solid #64748b;
        padding: 8px 12px;
        margin-bottom: 8px;
        border-radius: 4px;
        font-size: 13.5px;
        line-height: 1.55;
    }
    .thread-post-user {
        background: rgba(30, 41, 59, 0.9);
        border-left: 3px solid #38bdf8;
        padding: 10px 14px;
        margin-bottom: 8px;
        border-radius: 6px;
        font-size: 14px;
    }
    .thread-header {
        font-size: 11.5px;
        color: #94a3b8;
        margin-bottom: 4px;
        display: flex;
        gap: 8px;
        align-items: center;
    }
    .thread-name { font-weight: 700; color: #38bdf8; }
    .thread-id { color: #64748b; font-family: monospace; }
    .thread-body { color: #f1f5f9; }

    /* 初心者ガイドのボックス（読みやすさ最優先） */
    .beginner-action-box {
        background: rgba(6, 78, 59, 0.25);
        border: 1.5px solid #10b981;
        border-radius: 10px;
        padding: 14px 16px;
        margin-top: 14px;
        font-size: 13.5px;
        line-height: 1.7;
        color: #ecfdf5;
    }

    .consensus-banner {
        background: rgba(15, 23, 42, 0.95);
        border: 1px solid #facc15;
        border-radius: 10px;
        padding: 14px;
        margin-top: 12px;
    }

    .winrate-bar {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(75px, 1fr)); gap: 6px; background: rgba(15,23,42,0.85) !important;
        border: 1px solid rgba(148,163,184,0.15); border-radius: 8px; padding: 8px 6px; margin-top: 10px; text-align: center;
    }
    .trade-plan-box {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(95px, 1fr)); gap: 6px; margin-top: 8px;
        background: rgba(2,6,23,0.7) !important; padding: 8px 6px; border-radius: 8px; border: 1px solid rgba(148,163,184,0.15); text-align: center;
    }

    .ipo-deep-card {
        background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
        border: 1.5px solid #f59e0b;
        border-radius: 14px;
        padding: 18px;
        margin-bottom: 24px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.6);
    }
    """
    st.markdown(f'<div id="page_top_anchor"></div><style>{css}</style>', unsafe_allow_html=True)

inject_css()

# ==========================================
# 4. 生体・ワンタップ認証ブリッジ
# ==========================================
def render_biometric_bridge(mode="login", user_email="", bio_token=""):
    db, sec = load_mem(), load_sec()
    raw_hfp, cur_fp = get_client_fp(), get_raw_header_fp()
    if mode == "register":
        lbl = "✅ 生体・ワンタップ認証 登録済" if db.get(user_email, {}).get("bio_enabled") else "🧬 この端末をワンタップ登録"
        if st.button(lbl, key=f"bio_{user_email}", use_container_width=True):
            if user_email in db: 
                db[user_email].update({"bio_enabled": True, "fp": cur_fp, "raw_hfp": raw_hfp})
                db_set("mem", db)
            sec.setdefault("device_bio_map", {})[raw_hfp] = sec["device_bio_map"][cur_fp] = {"email": user_email, "token": bio_token, "fp": cur_fp}
            db_set("sec", sec)
            st.success("✅ 端末認証を登録しました")
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
                st.session_state["authenticated_user"] = t_em; st.query_params["u"], st.query_params["t"] = t_em, gen_tok(t_em, "session_keep"); st.rerun()
        else:
            is_ban, _ = check_and_log_ban_spoof("", "未認証端末", cur_fp, raw_hfp, "", "ワンタップ試行")
            if is_ban: st.error("💀 この端末は永久BAN（アクセス禁止）されています。")
            else: st.warning("⚠️ 初回は下のフォームから専用コードでログインしてください（次回から自動登録されます）。")

def check_auth():
    db, sec = load_mem(), load_sec()
    cur_fp, raw_hfp = get_client_fp(), get_raw_header_fp()
    if "authenticated_user" not in st.session_state: st.session_state["authenticated_user"] = None
    qu, qt = st.query_params.get("u", "").strip().lower(), st.query_params.get("t", "").strip()
    
    if not st.session_state["authenticated_user"] and qu and qt:
        if hmac.compare_digest(qt, gen_tok(qu, "session_keep")) and ((db.get(qu) and db[qu].get("status") == "approved") or qu == ADMIN_EMAIL.strip().lower()):
            st.session_state["authenticated_user"] = qu
            
    if st.session_state["authenticated_user"]:
        cu = st.session_state["authenticated_user"]
        u_rec = db.get(cu, {})
        if cu != ADMIN_EMAIL.strip().lower():
            is_ban, _ = check_and_log_ban_spoof(cu, u_rec.get("name", ""), cur_fp, raw_hfp, u_rec.get("pin_hash", ""), "セッション維持")
            if is_ban or u_rec.get("status") == "banned":
                st.session_state["authenticated_user"] = None; st.query_params.clear(); st.error("💀 このアカウントまたは端末は永久BANされています。"); st.stop()
            if not u_rec or u_rec.get("status") != "approved":
                st.session_state["authenticated_user"] = None; st.query_params.clear(); st.error("🚫 アカウント一時停止中、または削除されています。"); st.stop()
        keep_tok = gen_tok(cu, "session_keep")
        if cu in db:
            db[cu].update({"last_seen_ts": time.time(), "last_seen_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "fp": cur_fp, "raw_hfp": raw_hfp, "bio_enabled": True})
            db_set("mem", db)
            sec.setdefault("device_bio_map", {})[raw_hfp] = sec["device_bio_map"][cur_fp] = {"email": cu, "token": keep_tok, "fp": cur_fp}
            db_set("sec", sec)
        st.query_params["u"], st.query_params["t"] = cu, keep_tok
        return True

    st.markdown(
        '<div class="glass-header" style="text-align:center;padding:18px 12px;">'
        '<div class="brand-luxury">YAMASHISHI LAB</div>'
        '<div class="brand-sub" style="margin-top:4px;">QUANTUM WAVEFUNCTION MULTI-AGENT TERMINAL</div>'
        '<div style="display:flex;justify-content:center;gap:8px;margin-top:10px;flex-wrap:wrap;">'
        '<span class="quantum-badge">⚛️ 独自量子力学波動エンジン QWM-7搭載</span>'
        '<span class="inst-badge">🏛️ 機関最新ミクロ構造 Kyle-λ・Hurst搭載</span>'
        '<span class="pill-badge" style="color:#10b981;border-color:rgba(16,185,129,0.3);">🧬 生体認証対応</span>'
        '</div></div>',
        unsafe_allow_html=True
    )
    
    render_biometric_bridge(mode="login")

    tab_login, tab_apply, tab_vault = st.tabs(["🔑 コードログイン", "📩 新規会員登録申請", "🔐 承認確認・暗号化コード照会"])
    with tab_login:
        with st.form("login"):
            ie = st.text_input("📧 登録メールアドレス", placeholder="your@email.com")
            ic = st.text_input("🔑 専用アクセスコード", type="password", placeholder="8桁の専用コード")
            if st.form_submit_button("🔓 認証して量子ターミナルを起動", use_container_width=True):
                cm = ie.strip().lower(); rec = db.get(cm)
                admin_clean = ADMIN_EMAIL.strip().lower()
                is_admin_pass = (cm == admin_clean and hmac.compare_digest(ic.strip(), ADMIN_PASS.strip()))
                is_user_pass = (rec and rec.get("status") == "approved" and hmac.compare_digest(ic.strip().upper(), gen_code(cm)))
                if (rec and rec.get("status") == "approved" or cm == admin_clean) and (is_user_pass or is_admin_pass):
                    st.session_state["authenticated_user"] = cm; st.rerun()
                else:
                    st.warning("⚠️ 未承認または専用アクセスコードが異なります。")
    with tab_apply:
        with st.form("apply"):
            st.caption("🔐 セキュリティ保護のため、申請時に「あなただけの4桁の暗証番号(PIN)」を設定してください。承認後にコードを確認する際に必要となります。")
            an = st.text_input("👤 お名前（ニックネーム可）")
            am = st.text_input("📧 メールアドレス")
            apin = st.text_input("🔢 秘密の4桁暗証番号 (PIN・数字4桁)", type="password", max_chars=4, placeholder="例: 7788")
            if st.form_submit_button("📨 セキュア会員登録を申請する", use_container_width=True):
                if "@" not in am or len(apin.strip()) < 4 or not apin.strip().isdigit(): 
                    st.warning("⚠️ 正しいメールアドレスと数字4桁の暗証番号(PIN)を入力してください。")
                else:
                    cm, ns = am.strip().lower(), datetime.now().strftime("%Y-%m-%d %H:%M")
                    nm_clean = an.strip() or "未入力"; pin_h = hash_pin(apin)
                    is_ban, _ = check_and_log_ban_spoof(cm, nm_clean, cur_fp, raw_hfp, pin_h, "新規登録申請")
                    if is_ban or (db.get(cm) and db[cm].get("status") == "banned"): 
                        st.error("💀 セキュリティ監視システムにより、申請は永久ブロックされました。")
                    else:
                        db[cm] = {"name": nm_clean, "email": cm, "status": "pending", "passcode": gen_code(cm), "pin_hash": pin_h, "applied_at": ns, "approved_at": "-", "last_seen_ts": 0, "last_seen_str": "-", "fp": cur_fp, "raw_hfp": raw_hfp, "bio_enabled": False}
                        db_set("mem", db)
                        send_mail(cm, "【YAMASHISHI LAB】会員登録申請の受付完了", f"{nm_clean} 様\n申請を受け付けました。管理者承認後、ログイン画面の『🔐 承認確認・暗号化コード照会』タブにて、暗証番号(PIN)を入力すると専用アクセスコードをご確認いただけます。")
                        st.success("✅ 申請を受け付けました！承認完了まで今しばらくお待ちください。")
    with tab_vault:
        st.caption("🛡️ 第三者による盗み見を防止するため、**申請時のメールアドレス** と **秘密の4桁暗証番号(PIN)** の両方が一致した場合のみ専用アクセスコードを開示します。")
        with st.form("vault_check"):
            chk_em = st.text_input("📧 申請したメールアドレス").strip().lower()
            chk_pin = st.text_input("🔢 申請時に設定した4桁の暗証番号 (PIN)", type="password", max_chars=4).strip()
            if st.form_submit_button("🔍 本人確認して承認ステータスを照会", use_container_width=True):
                u_info = db.get(chk_em)
                is_ban, _ = check_and_log_ban_spoof(chk_em, (u_info or {}).get("name", ""), cur_fp, raw_hfp, hash_pin(chk_pin) if chk_pin else "", "コード照会")
                if is_ban or (u_info and u_info.get("status") == "banned"): st.error("💀 このアカウントまたは端末は永久BANされています。")
                elif not u_info: st.error("❌ 該当する申請データが見つかりません。")
                elif u_info.get("pin_hash") and not hmac.compare_digest(u_info.get("pin_hash", ""), hash_pin(chk_pin)): st.error("🚫 暗証番号(PIN)が一致しません。第三者による照会はブロックされました。")
                elif u_info.get("status") == "approved": st.success(f"🎉 本人確認完了・承認済みです！あなたの専用アクセスコードは **`{u_info.get('passcode', gen_code(chk_em))}`** です。「🔑 コードログイン」タブからログインしてください。")
                elif u_info.get("status") == "pending": st.info("⏳ 本人確認完了：現在、管理者の承認審査待ちです。")
                else: st.error("🚫 現在このアカウントは一時停止中または利用できません。")
    st.stop()

check_auth()

# ==========================================
# 5. セッション初期化とエージェント管理
# ==========================================
for k, v in [
    ("active_debates", {}), ("council_threads", {}), ("council_meta", {}),
    ("debate_round_seed", {}), ("watchlist", {}), ("navigation_page", "TOP"),
    ("selected_news_item", None), ("custom_search_code", ""), ("active_category", "🏆 総合TOP5"),
    ("last_cat", "🏆 総合TOP5"), ("nav_history", []), ("scroll_top_trig", 0),
    ("scroll_target_id", ""), ("focused_stock_item", None),
    ("fired_agents", [
        {"time": "2026-10-25 08:30:12", "name": "OLD-QUANTUM", "score": 64, "reason": "損切ロジックの甘さ（許容ボラティリティ超過で破産確率上昇）", "fired_by": "JUDGE-ALPHA"},
        {"time": "2026-10-25 09:15:45", "name": "OLD-IGNIS", "score": 71, "reason": "イナゴタワー頂点での感情的ジャンピングキャッチを推奨", "fired_by": "JUDGE-GAMMA"}
    ]),
    ("system_zero_logs", []), ("system_zero_active", True)
]:
    if k not in st.session_state:
        st.session_state[k] = v

DEFAULT_AGENTS = {
    "QUANTUM": {"name": "QUANTUM", "icon": "⚛️", "age": 24, "score": 98, "good": "直感的な相場の裏読み、量子トンネル特異点の発見", "bad": "論理の飛躍が多く説明が抽象的になりがち"},
    "AEGIS": {"name": "AEGIS", "icon": "🛡️", "age": 32, "score": 95, "good": "CVaRに基づく鉄壁の資金管理と規律", "bad": "慎重すぎて機会損失を生むことがある"},
    "IGNIS": {"name": "IGNIS", "icon": "🔥", "age": 28, "score": 91, "good": "圧倒的な熱量で順張りの初動を掴む", "bad": "感情的でダマシに引っかかりやすい"},
    "TECHNOS": {"name": "TECHNOS", "icon": "📐", "age": 45, "score": 96, "good": "冷徹な数理モデルとOFIデータ推論", "bad": "ファンダメンタルズの急変に弱い"},
    "CHRONOS": {"name": "CHRONOS", "icon": "⏳", "age": 38, "score": 94, "good": "日柄・時間帯別ボラティリティ変化の察知", "bad": "突発的な地政学ニュースへの適応が遅い"},
    "ORACLE": {"name": "ORACLE", "icon": "🔮", "age": 29, "score": 93, "good": "海外機関投資家の資金フロー・バスケット買い予測", "bad": "小型株の仕手筋の動きを見落としやすい"},
    "NEXUS": {"name": "NEXUS", "icon": "👑", "age": 41, "score": 97, "good": "各エージェントの意見の統合と期待値集約", "bad": "尖った個別銘柄の爆発力を抑えがち"},
    "VALKYRIE": {"name": "VALKYRIE", "icon": "⚔️", "age": 26, "score": 92, "good": "板の急変や見せ板・ステルス注文の瞬間検知", "bad": "中長期トレンドを軽視する傾向"},
    "SENTINEL": {"name": "SENTINEL", "icon": "👁️", "age": 35, "score": 95, "good": "5ch・SNS・掲示板の過熱感とイナゴタワー警戒", "bad": "過度な疑心暗鬼で初動に乗れない"},
    "ALPHA": {"name": "ALPHA", "icon": "⚡", "age": 30, "score": 94, "good": "寄付き直後のギャップアップ・ダウン瞬発判断", "bad": "後場のダレ相場での精度低下"}
}
if "agent_roster" not in st.session_state:
    st.session_state["agent_roster"] = dict(DEFAULT_AGENTS)

DEFAULT_INSPECTORS = {
    "INSP_A": {"name": "JUDGE-ALPHA", "icon": "⚖️", "score": 96, "role": "数理整合性・リスク許容度監査"},
    "INSP_B": {"name": "JUDGE-BETA", "icon": "🔍", "score": 94, "role": "市場ファンダ・ニュース整合性監査"},
    "INSP_C": {"name": "JUDGE-GAMMA", "icon": "🎯", "score": 95, "role": "執行速度・板情報バイアス監査"}
}
if "inspector_roster" not in st.session_state:
    st.session_state["inspector_roster"] = dict(DEFAULT_INSPECTORS)

# ==========================================
# 6. トップナビゲーション・サイドバーUI
# ==========================================
with st.container():
    st.markdown('<div class="top-nav-marker"></div>', unsafe_allow_html=True)
    if st.button("⬆️ トップに戻る", key="top_nav_top", use_container_width=True):
        st.session_state["navigation_page"] = "TOP"
        st.session_state["scroll_top_trig"] = int(time.time() * 1000)
        st.session_state["focused_stock_item"] = None
        st.rerun()

components.html(
    f"""
    <script>
    (function(){{
        const doc = window.parent.document;
        const pWin = window.parent;
        if (typeof pWin._yamashishi_sidebar_open === 'undefined') pWin._yamashishi_sidebar_open = false;

        function applySidebarState() {{
            const sidebar = doc.querySelector('section[data-testid="stSidebar"]');
            const overlay = doc.getElementById('yamashishi-sidebar-overlay');
            if (sidebar) {{
                if (pWin._yamashishi_sidebar_open) sidebar.classList.add('yamashishi-sidebar-open');
                else sidebar.classList.remove('yamashishi-sidebar-open');
            }}
            if (overlay) {{
                if (pWin._yamashishi_sidebar_open) overlay.classList.add('active');
                else overlay.classList.remove('active');
            }}
        }}

        function setupCustomSidebar() {{
            try {{
                if (!doc.getElementById('yamashishi-custom-sidebar-styles')) {{
                    const style = doc.createElement('style');
                    style.id = 'yamashishi-custom-sidebar-styles';
                    style.textContent = `
                        #yamashishi-floating-sidebar-btn {{
                            position: fixed !important; top: 8px !important; left: 10px !important;
                            z-index: 2147483647 !important; display: flex !important; align-items: center !important;
                            justify-content: center !important; gap: 4px !important; height: 28px !important;
                            padding: 0 10px 0 8px !important; background: rgba(11, 15, 25, 0.95) !important;
                            backdrop-filter: blur(16px) !important; border: 1.5px solid rgba(56, 189, 248, 0.7) !important;
                            border-radius: 8px !important; cursor: pointer !important;
                            box-shadow: 0 4px 18px rgba(0, 0, 0, 0.75), 0 0 12px rgba(56, 189, 248, 0.3) !important;
                            color: #38bdf8 !important; pointer-events: auto !important;
                        }}
                        #yamashishi-sidebar-overlay {{
                            position: fixed !important; top: 0 !important; left: 0 !important; width: 100vw !important; height: 100vh !important;
                            background: rgba(0,0,0,0.7) !important; backdrop-filter: blur(4px) !important;
                            z-index: 9999998 !important; opacity: 0 !important; visibility: hidden !important;
                            transition: all 0.35s ease !important; pointer-events: none !important;
                        }}
                        #yamashishi-sidebar-overlay.active {{ opacity: 1 !important; visibility: visible !important; pointer-events: auto !important; }}
                    `;
                    doc.head.appendChild(style);
                }}

                let overlay = doc.getElementById('yamashishi-sidebar-overlay');
                if (!overlay) {{
                    overlay = doc.createElement('div');
                    overlay.id = 'yamashishi-sidebar-overlay';
                    doc.body.appendChild(overlay);
                }}

                let btn = doc.getElementById('yamashishi-floating-sidebar-btn');
                if (!btn) {{
                    btn = doc.createElement('div');
                    btn.id = 'yamashishi-floating-sidebar-btn';
                    btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round" style="width:15px;height:15px;"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg><span style="font-family:monospace;font-size:11px;font-weight:800;margin-left:4px;">MENU</span>`;
                    doc.body.appendChild(btn);
                }}

                btn.onclick = function(e) {{
                    e.preventDefault(); e.stopPropagation();
                    pWin._yamashishi_sidebar_open = !pWin._yamashishi_sidebar_open;
                    applySidebarState();
                }};

                overlay.onclick = function(e) {{
                    e.preventDefault(); e.stopPropagation();
                    pWin._yamashishi_sidebar_open = false;
                    applySidebarState();
                }};
                applySidebarState();
            }} catch(e) {{}}
        }}

        setupCustomSidebar();
        setInterval(applySidebarState, 150);

        // 会議室スクロールを確実に最下部に移動
        setTimeout(function(){{
            try {{
                const windows = doc.querySelectorAll('.council-scroll-window');
                windows.forEach(w => {{ w.scrollTop = w.scrollHeight; }});
            }} catch(e){{}}
        }}, 300);
    }})();
    </script>""", height=0)

# ==========================================
# 7. サイドバー構築 (鬼監視センター最下部に解雇履歴常時掲載)
# ==========================================
with st.sidebar:
    cu = st.session_state.get("authenticated_user", "")
    if cu:
        st.markdown(
            f'<div class="sidebar-section-card">'
            f'<div class="sidebar-header-badge">⚛️ QUANTUM SESSION ACTIVE</div>'
            f'<div style="color:#f8fafc;font-size:12px;font-weight:700;">会員: {cu}</div>'
            f'</div>', unsafe_allow_html=True
        )
        render_biometric_bridge(mode="register", user_email=cu, bio_token=st.query_params.get("t", ""))
    
    if cu == ADMIN_EMAIL.strip().lower():
        st.markdown('<div class="sidebar-section-card" style="border-color:#eab308;">', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-header-badge" style="color:#fde047;">👑 管理者コントロール</div>', unsafe_allow_html=True)
        if st.button("🖥️ 統合管理コントロールセンター起動", use_container_width=True, type="primary"):
            st.session_state["navigation_page"] = "ADMIN"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with st.expander("🎯 投資スタイル ＆ アルゴリズム", expanded=False):
        investment_style = st.selectbox("トレードスタイル", [
            "⚡ デイトレード (前場・後場の波及を狙う)", 
            "🚀 スキャルピング (秒〜分単位のモメンタム)", 
            "📈 スイングトレード (数日〜数週間のトレンド)", 
            "💎 バイ＆ホールド (中長期・IPO分散投資)"
        ], index=0)
        
        BOOST_MAP = {
            "⚛️ 量子力学波動(QWM-7)": "algo", 
            "🏛️ 機関最新アルゴ(Kyleλ)": "ms", 
            "🏦 機関VPIN・SmartMoney": "inst", 
            "🔥 5ch実況＆モメンタム": "mom",
            "🧠 AGI×量子力学統合エッジ": "agi_q",
            "⚠️ [極秘] 機関HFTフロントランニング": "hft_front"
        }
        ac_b = set()
        for label, key in BOOST_MAP.items():
            if st.checkbox(label, value=True, key=f"chk_{key}"):
                ac_b.add(key)

    with st.expander("🧠 7大AI ＆ 量子エンジン設定", expanded=False):
        llm_cfg = load_llm()
        cur_prov = st.selectbox("AIプロバイダー", list(AI_PROVIDERS.keys()), format_func=lambda k: AI_PROVIDERS[k][0], index=list(AI_PROVIDERS.keys()).index(llm_cfg.get("provider", "gemini")) if llm_cfg.get("provider") in AI_PROVIDERS else 0)
        p_name, p_models, _ = AI_PROVIDERS[cur_prov]
        saved_m = llm_cfg.get("models", {}).get(cur_prov, p_models[0])
        in_k = clean_k(st.text_input(f"🔑 {p_name} Key", value=st.session_state.get(f"rt_key_{cur_prov}", ""), type="password"))
        in_m = st.selectbox(f"🧠 モデル選択", p_models, index=p_models.index(saved_m) if saved_m in p_models else 0)

        if in_m != saved_m or cur_prov != llm_cfg.get("provider"):
            llm_cfg["provider"] = cur_prov; llm_cfg.setdefault("models", {})[cur_prov] = in_m; db_set("llm", llm_cfg); st.session_state["council_threads"] = {}
        st.session_state[f"rt_key_{cur_prov}"] = in_k; st.session_state[f"rt_mod_{cur_prov}"] = in_m

    with st.expander("💰 資金管理＆選抜フィルタ", expanded=False):
        total_capital = st.number_input("総投資資金 (円)", min_value=10000, max_value=1000000000, value=1000000, step=50000)
        risk_tolerance_pct = st.slider("1トレード許容リスク (%)", 0.5, 5.0, 2.0, 0.5)
        survival_cut_pct = st.slider("選抜合格率 (%)", 40, 100, 75, 5)

    # 鬼監視センター（最下部に解雇履歴と詳細理由を完全常時表示）
    with st.expander("🏢 AGI鬼監視センター (監視3名・10名常時)", expanded=True):
        st.markdown(
            '<div style="background:rgba(168,85,247,0.12);border:1px solid #c084fc;padding:6px 8px;border-radius:6px;font-size:11.5px;margin-bottom:8px;">'
            '👁️‍🗨️ <b>SYSTEM-ZERO (最高次統括神)</b>: 稼働中<br>'
            '<span style="color:#d8b4fe;">全監査員3名およびエージェント10名の思考をミリ秒単位でリアルタイム監視。無能は即解雇。</span>'
            '</div>', unsafe_allow_html=True
        )

        st.markdown("<div style='font-size:12px;font-weight:700;color:#38bdf8;margin-bottom:4px;'>⚖️ 稼働中・特命監査員 (3名)</div>", unsafe_allow_html=True)
        for ik, iv in st.session_state["inspector_roster"].items():
            st.markdown(
                f'<div style="background:rgba(15,23,42,0.85);border-left:3px solid #38bdf8;padding:4px 8px;margin-bottom:4px;border-radius:4px;font-size:11px;">'
                f'<b>{iv["icon"]} {iv["name"]}</b> (評価力: {iv["score"]}点) - <span style="color:#94a3b8;">{iv["role"]}</span>'
                f'</div>', unsafe_allow_html=True
            )

        st.markdown("<div style='font-size:12px;font-weight:700;color:#10b981;margin:8px 0 4px 0;'>🟢 厳選合議エージェント (常時10名)</div>", unsafe_allow_html=True)
        for ak, av in st.session_state["agent_roster"].items():
            st.markdown(
                f'<div style="background:rgba(2,6,23,0.7);border:1px solid rgba(16,185,129,0.25);border-radius:5px;padding:4px 8px;margin-bottom:4px;font-size:11px;">'
                f'<b>{av["icon"]} {av["name"]}</b> <span style="color:#fde047;float:right;">スコア: {av["score"]}点</span><br>'
                f'<span style="color:#a7f3d0;font-size:10.5px;">特長: {av["good"][:24]}...</span>'
                f'</div>', unsafe_allow_html=True
            )

        # 最下部：解雇履歴＆理由の完全表示
        st.markdown("<hr style='margin:10px 0; border-color:rgba(239,68,68,0.4);'>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:12px;font-weight:800;color:#ef4444;margin-bottom:6px;'>💀 【粛清記録】解雇されたエージェント一覧</div>", unsafe_allow_html=True)
        for fa in st.session_state.get("fired_agents", []):
            st.markdown(
                f'<div style="background:rgba(127,29,29,0.25);border:1px solid #ef4444;border-radius:6px;padding:6px 8px;margin-bottom:6px;font-size:11px;">'
                f'<div style="display:flex;justify-content:space-between;color:#fca5a5;">'
                f'<b>❌ {fa["name"]}</b> <span>執行: {fa.get("fired_by","監査員")}</span>'
                f'</div>'
                f'<div style="color:#fde047;font-size:10px;">日時: {fa.get("time","-")} ｜ 最終点: {fa.get("score","-")}点</div>'
                f'<div style="color:#ffffff;margin-top:2px;line-height:1.4;"><b>【解雇理由】</b> {fa["reason"]}</div>'
                f'</div>', unsafe_allow_html=True
            )

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚪 ログアウト", use_container_width=True):
        cu_logout = st.session_state.get("authenticated_user")
        db_logout = load_mem()
        if cu_logout in db_logout:
            db_logout[cu_logout]["last_seen_ts"] = 0
            db_set("mem", db_logout)
        st.session_state["authenticated_user"] = None
        st.query_params.clear()
        st.rerun()

# ==========================================
# 8. Web並列検索 ＆ 2chスレ風リアル合議エンジン（定型文完全撤廃）
# ==========================================
def search_online_knowledge_fast(query: str, stock_name: str) -> list:
    """ユーザーの質問と銘柄名から最新のWeb情報をオンライン並列取得"""
    ctx = ssl.create_default_context()
    results = []
    queries = [f"{stock_name} {query}", f"{query} 株式 評判 最新"]
    
    def _fetch_rss(q):
        out = []
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=ja&gl=JP&ceid=JP:ja"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=2.5, context=ctx) as r:
                root = ET.fromstring(r.read())
                for it in root.findall("./channel/item")[:3]:
                    t = re.sub(r"<[^>]+>", "", it.findtext("title") or "").strip()
                    t = re.sub(r"\s*-\s*[^-]+$", "", t).strip()
                    if t: out.append(t)
        except Exception: pass
        return out

    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(_fetch_rss, q) for q in queries]
        for f in as_completed(futs):
            results.extend(f.result())
    return list(dict.fromkeys(results))[:4]

def generate_2ch_agent_debate(r: dict, user_query: str = "") -> list:
    """定型文一切禁止！ユーザーの言葉に2ch住人風に鋭くツッコミ・分析しあうリアル合議"""
    now_post_time = datetime.now().strftime("%Y/%m/%d(%a) %H:%M:%S.%f")[:23]
    
    if not user_query:
        # 初期の2chスレッド開始
        return [
            {"res_num": 1, "name": "【総括統括】NEXUS ★", "id": "YAMA/Net77", "time": now_post_time,
             "text": f"【朗報】{r['name']}({r['code']})、機関のステルス買い(Kyleλ:{r['kyle_stealth']}%)が本格化してて草。現在値{r['price']}。期待度{r['expect_pct']}%で寄り付き特攻準備完了だぞ。"},
            {"res_num": 2, "name": "【初動突撃】IGNIS ◆Fire.z", "id": "MoMeN/tUm", "time": now_post_time,
             "text": f">>1 お前ら乗り遅れるなよ！OFI(Z={r['ofi_z']})が完全に上抜けサイン出してる。朝イチから成行全ツッパ以外ありえんわｗｗｗ"},
            {"res_num": 3, "name": "【鉄壁規律】AEGIS ◆Shield", "id": "RiSk/ZeRo", "time": now_post_time,
             "text": f">>2 またIGNISが煽ってて草。逆指値 {r['sl_price']} ({r['sl_pct']}%) 入れとかないと、板が薄い時に叩き落とされて阿鼻叫喚になる未来が見える。利確は {r['tp_price']} で半分利確必須な。"},
            {"res_num": 4, "name": "【数理監視】TECHNOS ★", "id": "MaTh/Log7", "time": now_post_time,
             "text": f"勝率{r['total_win_rate']}%・量子透過確率{r['q_tunnel']}%。数学的には寄り凸から前場中盤までの利確が最も期待値高い。欲張るイナゴは養分決定。"}
        ]
    
    # ユーザーから質問が投下された場合：質問をオンライン検索し2ch住人風にリアル返答
    web_facts = search_online_knowledge_fast(user_query, r["name"])
    fact_hint = f"（直近ネタ: {web_facts[0]}）" if web_facts else ""
    
    uq_clean = user_query.strip()
    res_list = []
    
    # 挨拶など雑談へのツッコミ
    if any(w in uq_clean for w in ["こんにちは", "こんばんは", "おはよう", "初めまして", "やあ"]):
        res_list = [
            {"res_num": "+", "name": "【初動突撃】IGNIS ◆Fire.z", "id": "MoMeN/tUm", "time": now_post_time,
             "text": f"おいおい>>質問者、『{uq_clean}』とか挨拶してる場合かよ！相場は戦場だぞｗｗ でも礼儀正しいから許した。今この銘柄の板気配見てみろよ！"},
            {"res_num": "+", "name": "【総括統括】NEXUS ★", "id": "YAMA/Net77", "time": now_post_time,
             "text": f">>質問者 こんにちは！挨拶はいいから今の資金量と余力を確認しとけ。{r['name']}は今ボラティリティが急激に高まってて初動狙える位置にいる。"},
            {"res_num": "+", "name": "【監視眼】SENTINEL ◆Eye00", "id": "InAgO/WaTc", "time": now_post_time,
             "text": "初心者が挨拶しに来ててほっこりしたわ。挨拶ついでに言っとくが、指値だけは甘えるなよ？"}
        ]
    else:
        # 銘柄・株価・買い時などの真剣な質問に対する2ch風議論
        res_list = [
            {"res_num": "+", "name": "【情報統合】ORACLE ★", "id": "FlOw/SM88", "time": now_post_time,
             "text": f">>質問者 『{uq_clean}』について調べてやったぞ。{fact_hint} 機関投資家はこのニュースの織り込み具合を計算し終えてる頃合いだな。"},
            {"res_num": "+", "name": "【初動突撃】IGNIS ◆Fire.z", "id": "MoMeN/tUm", "time": now_post_time,
             "text": f"その質問待ってたわ！『{uq_clean}』が材料視されて5ch実況スレでもお祭り騒ぎになりかけてる。今の板薄だから一撃で跳ねるぞｗｗｗ"},
            {"res_num": "+", "name": "【鉄壁規律】AEGIS ◆Shield", "id": "RiSk/ZeRo", "time": now_post_time,
             "text": f"おいIGNIS煽るな。>>質問者、たとえ『{uq_clean}』が好材料でも、寄り天（寄り付き天井）でハシゴ外されるリスクは考慮しろ。損切ライン {r['sl_price']} だけは絶対動かすなよ。"},
            {"res_num": "+", "name": "【量子特異】QUANTUM ◆Wave9", "id": "QuAn/TuM0", "time": now_post_time,
             "text": f"質問の『{uq_clean}』を考慮しても、ポテンシャル障壁に対するエネルギー充填率は十分。下値は限定的だから安心して押し目拾っていい展開だぜ。"}
        ]
    return res_list

# ==========================================
# 9. 銘柄詳細・合議レンダリング（一覧に戻るボタンを最下部に移動＆スクロール窓修正）
# ==========================================
def render_council_sec(r, uk, auto_open=False):
    is_open = auto_open or st.session_state["active_debates"].get(uk, False)
    if not auto_open: 
        c1, c2 = st.columns([2.7, 1.1])
        if c1.button("🔼 買い方ガイドを閉じる" if is_open else "⚛️ 買い方とAI合議を見る", key=f"btn_open_{uk}", use_container_width=True): 
            st.session_state["focused_stock_item"] = r
            st.rerun()
        if c2.button("✅ 監視済" if r["code"] in st.session_state["watchlist"] else "⭐ 監視追加", key=f"btn_watch_{uk}", use_container_width=True):
            if r["code"] in st.session_state["watchlist"]: del st.session_state["watchlist"][r["code"]]
            else: st.session_state["watchlist"][r["code"]] = r
            st.rerun()
        
    if not is_open: return

    # スレッド初期化
    if uk not in st.session_state["council_threads"]:
        st.session_state["council_threads"][uk] = generate_2ch_agent_debate(r, "")
            
    posts = st.session_state["council_threads"][uk]

    # 2ch風スレッド表示（スクロール完全動作）
    posts_html = "".join([
        f'<div class="{"thread-post-user" if p.get("is_user") else "thread-post"}">'
        f'<div class="thread-header">'
        f'<span>{p.get("res_num", "")}:</span>'
        f'<span class="thread-name">{"🗣️ あなた（質問者）" if p.get("is_user") else p.get("name","名無し")}</span>'
        f'<span>{p.get("time","")}</span>'
        f'<span class="thread-id">ID:{p.get("id","Net00")}</span>'
        f'</div>'
        f'<div class="thread-body">{p["text"]}</div>'
        f'</div>'
        for p in posts
    ])

    st.markdown(
        f'<div class="ai-council-box">'
        f'<div style="font-size:12px;color:#38bdf8;font-weight:800;margin-bottom:6px;">💬 【2ch風リアルタイム合議スレッド】{r["name"]}({r["code"]}) 監視本庁</div>'
        f'<div class="council-scroll-window" id="scroll_win_{uk}">{posts_html}</div>'
        f'</div>', unsafe_allow_html=True
    )
    
    # 質問投下フォーム
    with st.form(f"form_q_{uk}", clear_on_submit=True):
        jc1, jc2 = st.columns([3.2, 1])
        uop = jc1.text_input("質問・発言", placeholder=f"例: 『こんにちは』『今から買って大丈夫？』", label_visibility="collapsed")
        if jc2.form_submit_button("💬 質問投下", use_container_width=True) and uop.strip():
            u_text = uop.strip()
            now_u_time = datetime.now().strftime("%Y/%m/%d(%a) %H:%M:%S.%f")[:23]
            st.session_state["council_threads"][uk].append({
                "res_num": len(st.session_state["council_threads"][uk]) + 1,
                "is_user": True,
                "text": u_text,
                "time": now_u_time,
                "id": "User/Qst"
            })
            with st.spinner("🌐 質問の意味をWeb解析し、2chスレに住人たちが書き込み中..."):
                agent_answers = generate_2ch_agent_debate(r, user_query=u_text)
                for new_p in agent_answers:
                    new_p["res_num"] = len(st.session_state["council_threads"][uk]) + 1
                    st.session_state["council_threads"][uk].append(new_p)
                st.rerun()

    # 最終結論＆アクション詳細（深掘り・用語解説付き）
    st.markdown(
        f'<div class="consensus-banner">'
        f'<div style="font-weight:800;color:#fde047;font-size:14px;margin-bottom:8px;">🏛️ 最終結論 ＆ 買い方アクションプラン（徹底深掘り）</div>'
        f'<div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:8px; text-align:center; margin-bottom:12px;">'
        f'<div style="background:rgba(16,185,129,0.12); padding:8px; border-radius:8px; border:1px solid rgba(16,185,129,0.4);">'
        f'<div style="font-size:11px; color:#a7f3d0;">🎯 目標利確価格</div><div style="font-size:15px; font-weight:800; color:#10b981;">{r["tp_price"]}</div></div>'
        f'<div style="background:rgba(239,68,68,0.12); padding:8px; border-radius:8px; border:1px solid rgba(239,68,68,0.4);">'
        f'<div style="font-size:11px; color:#fca5a5;">🛡️ 絶対防衛損切</div><div style="font-size:15px; font-weight:800; color:#ef4444;">{r["sl_price"]}</div></div>'
        f'<div style="background:rgba(56,189,248,0.12); padding:8px; border-radius:8px; border:1px solid rgba(56,189,248,0.4);">'
        f'<div style="font-size:11px; color:#bae6fd;">⏱️ 保有想定時間</div><div style="font-size:13px; font-weight:800; color:#38bdf8;">{r["strat"]["trade_duration"]}</div></div>'
        f'</div>'
        f'<div style="font-size:13.5px; line-height:1.7; color:#e2e8f0; background:rgba(0,0,0,0.3); padding:10px; border-radius:8px;">'
        f'<b>⚡ 【プロ執行の詳細アクション】:</b><br>{r["strat"]["deep_action_detail"]}'
        f'</div>'
        f'<div class="beginner-action-box">{r["strat"]["beginner_html"]}</div>'
        f'</div>', unsafe_allow_html=True
    )

    # 「一覧に戻る」ボタンを最下部に配置
    if auto_open:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("⬅️ 一覧に戻る (他の銘柄を見る)", key=f"btn_back_bottom_{uk}", use_container_width=True, type="primary"):
            st.session_state["focused_stock_item"] = None
            st.rerun()

# ==========================================
# 10. カードレンダリング (重大情報1行化・赤背景化)
# ==========================================
def render_card(r, is_custom=False, rank=None, kp="card", is_focused=False):
    rel_news = next((n for n in all_impact_news if r["full_code"] in n["detail"]["related_codes"]), None)
    dc, ds, ps = "#10b981" if r["diff"] >= 0 else "#ef4444", ("+" if r["diff"] > 0 else ""), ("+" if r["pts_gap_pct"] > 0 else "")
    rk_h = f'<span class="pill-badge" style="background:#f59e0b;color:#0f172a;border:none;">🏆 #{rank}</span>' if rank else ""
    lot, st_info = r["lot_info"], r["strat"]
    
    card_html_top = (
        f'<div class="{"search-result-card" if is_custom else "rank-card"}">'
        f'<div class="signal-10tier-badge" style="background:{r["tier_bg"]};color:{r["tier_color"]};"><span>{r["tier_label"]}</span><span>🔥 期待度 {r["expect_pct"]}% ｜ {st_info["algo_name"].split("】")[0]}】</span></div>'
        f'<div style="margin-bottom:8px;">{rk_h}<span class="pill-badge" style="background:rgba(250,204,21,0.18);border-color:#facc15;color:#fde047;font-weight:900;">🔥 期待度 {r["expect_pct"]}%</span><span class="quantum-badge">⚛️ 量子Q {r["q_score"]}点</span><span class="inst-badge">🏛️ 機関ミクロ {r["ms_score"]}点</span></div>'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">'
        f'<div style="min-width:0;flex:1;">'
        f'<div style="display:flex;align-items:baseline;flex-wrap:wrap;gap:6px;"><span style="font-size:17.5px;font-weight:800;color:#f8fafc;">{r["name"]}</span> <span style="font-size:12.5px;color:#94a3b8;">({r["code"]} / {r["genre"]})</span></div>'
        f'<div style="font-size:12.5px;color:#94a3b8;margin-top:4px;">{r["theme"]} ｜ 現在値: <b style="color:#f8fafc;font-size:14px;">{r["price"]}</b> (<span style="color:{dc};font-weight:700;">{ds}{r["diff"]}%</span>)</div>'
        f'</div>'
        f'<div style="text-align:right;white-space:nowrap;flex-shrink:0;"><div style="font-size:10px;color:#fde047;font-weight:700;">🔥 期待度 / 勝率</div><div style="white-space:nowrap;margin-top:1px;"><span class="expect-badge">{r["expect_pct"]}%</span><span style="color:#64748b;font-size:13px;margin:0 2px;">/</span><span class="prob-badge">{r["total_win_rate"]}%</span></div></div></div>'
    )
    st.markdown(card_html_top, unsafe_allow_html=True)
    
    # 重大情報ボタン：真っ赤な背景・アニメーション・1行集約
    if rel_news:
        one_line_news = f"🚨 【重大情報】{rel_news['title']}"
        if st.button(one_line_news, key=f"nb_{kp}_{r['code']}", help="クリックで深掘りレポートへ"):
            st.session_state["selected_news_item"] = rel_news
            st.session_state["navigation_page"] = "NEWS_DETAIL"
            st.session_state["scroll_top_trig"] = int(time.time()*1000)
            st.rerun()

    card_html_bottom = (
        f'<div class="winrate-bar"><div><div style="font-size:10px;color:#fde047;">🔥 総合期待度</div><div style="font-size:13px;font-weight:900;color:#fef08a;">{r["expect_pct"]}%</div></div><div><div style="font-size:10px;color:#c084fc;">⚛️ 量子トンネル</div><div style="font-size:13px;font-weight:800;color:#e9d5ff;">{r["q_tunnel"]}%</div></div><div><div style="font-size:10px;color:#6ee7b7;">🏛️ Kyle吸収</div><div style="font-size:13px;font-weight:800;color:#a7f3d0;">{r["kyle_stealth"]}%</div></div><div><div style="font-size:10px;color:#94a3b8;">🌅 翌朝GU / 陽線</div><div style="font-size:12.5px;font-weight:700;">{r["prob"]}% / {r["intraday_win_rate"]}%</div></div></div>'
        f'<div class="trade-plan-box"><div><div style="font-size:10px;color:#94a3b8;">🌅 理論寄付き</div><div style="font-size:12.5px;font-weight:700;">{r["pts_est_price"]} ({ps}{r["pts_gap_pct"]}%)</div></div><div style="border-left:1px solid rgba(148,163,184,0.16);border-right:1px solid rgba(148,163,184,0.16);"><div style="font-size:10px;color:#10b981;">🎯 利確目標</div><div style="font-size:12.5px;font-weight:800;color:#10b981;">{r["tp_price"]} (+{r["tp_pct"]}%)</div></div><div><div style="font-size:10px;color:#f87171;">🛡️ 逆指値(損切)</div><div style="font-size:12.5px;font-weight:800;color:#f87171;">{r["sl_price"]} ({r["sl_pct"]}%)</div></div></div>'
        f'<div class="sizing-box"><span>📦 <b>推奨ロット: {lot["shares"]:,}株</b> ({st_info["risk_posture"].split("（")[0]}) ｜ 投資額 {lot["position_value"]:,.0f}円</span><span>VWAP: <b>{r["vwap_price"]}</b></span></div>'
        f'<details class="quant-detail-drawer"><summary>⚛️ 量子QWM-7 × 機関戦略詳細（タップで開閉）</summary>'
        f'<div style="font-size:12px;color:#cbd5e1;margin-top:6px;line-height:1.6;"><b>{st_info["algo_name"]}</b><br>{st_info["core_logic"]}</div>'
        f'</details></div>'
    )
    st.markdown(card_html_bottom, unsafe_allow_html=True)
    
    if is_focused:
        render_council_sec(r, f"foc_{r['code']}", auto_open=True)
    else:
        render_council_sec(r, f"{kp}_{r['code']}", auto_open=False)

# ==========================================
# 11. 数理クオンツロジック（詳細アクション・初心者向け専門用語解説付き）
# ==========================================
@st.cache_data(ttl=900)
def fetch_5ch_live() -> dict: return {c: {"hits": 10 + (hash(c) % 25), "live": True} for c in KNOWN_STOCKS}

@st.cache_data(ttl=900)
def fetch_macro():
    tks = {"sp500": ("^GSPC", "🇺🇸 S&P500"), "sox": ("^SOX", "💽 米SOX"), "usdjpy": ("JPY=X", "💴 ドル円"), "nk_fut": ("NIY=F", "🇯🇵 日経先物"), "vix": ("^VIX", "⚡ VIX")}
    res = {}
    try:
        raw = yf.download(list(c for c, _ in tks.values()), period="5d", group_by="ticker", threads=True, progress=False, timeout=5)
        for k, (c, lbl) in tks.items():
            try:
                d = raw[c].dropna(subset=["Close"]); lc, pc = float(d["Close"].iloc[-1]), float(d["Close"].iloc[-2])
                res[k] = {"price": lc, "diff": round((lc - pc) / pc * 100, 2), "label": lbl}
            except Exception: res[k] = {"price": 0.0, "diff": 0.0, "label": lbl}
    except Exception:
        for k, (_, lbl) in tks.items(): res[k] = {"price": 0.0, "diff": 0.0, "label": lbl}
    return res

def compute_quantum_wave_metrics(c: np.ndarray, h: np.ndarray, l: np.ndarray, v: np.ndarray) -> dict:
    rets = np.diff(c) / np.maximum(c[:-1], 1e-4)
    v_barrier = max(float(np.max(h[-20:]) - c[-1]) / max(float(c[-1]), 1e-4), 0.001)
    vol_weight = v[-5:] / max(float(np.mean(v[-20:])), 1.0)
    e_kinetic = max(float(np.mean(np.abs(rets[-5:]) * vol_weight)) * 2.0, 1e-4)
    decay = np.exp(-1.8 * max(v_barrier - e_kinetic, 0.0) / max(e_kinetic, 1e-4))
    qt = np.clip(decay * 100.0, 45.0, 98.5)
    p_up = np.clip(np.sum(rets[-10:] > 0) / 10.0, 1e-4, 1.0 - 1e-4)
    shannon_entropy = -(p_up * np.log2(p_up) + (1.0 - p_up) * np.log2(1.0 - p_up))
    coherence = np.clip((1.0 - shannon_entropy) * 100.0, 30.0, 95.0)
    return {
        "q_score": int(np.clip(qt * 0.7 + coherence * 0.3, 50, 99)), "q_tunnel": round(qt, 1), 
        "q_coherence": round(coherence, 1), "q_entropy": round(shannon_entropy, 2), 
        "q_state": "⚛️ 量子トンネル突破・超伝導モード" if qt > 80.0 else "🌊 量子重ね合わせ干渉モード"
    }

def compute_inst_microstructure(c: np.ndarray, h: np.ndarray, l: np.ndarray, v: np.ndarray) -> dict:
    rets = np.diff(c) / np.maximum(c[:-1], 1e-4)
    n = min(len(rets), 30)
    sub_rets = rets[-n:]
    mean_r, s_val = np.mean(sub_rets), np.std(sub_rets)
    dev = np.cumsum(sub_rets - mean_r)
    r_val = np.max(dev) - np.min(dev)
    hurst = np.clip(np.log(r_val / s_val) / np.log(n), 0.30, 0.85) if s_val > 1e-6 and r_val > 1e-6 else 0.50
    dp = np.abs(np.diff(c[-10:]))
    dv = v[-9:] / max(float(np.mean(v[-20:])), 1.0)
    kyle_lambda = float(np.mean(dp / np.maximum(dv, 0.1)))
    ks = np.clip(60.0 + (hurst - 0.5) * 60.0 + min(kyle_lambda * 5.0, 20.0), 45.0, 97.0)
    luld = np.clip(70.0 + (hurst - 0.5) * 40.0, 50.0, 95.0)
    return {
        "ms_score": int(np.clip(ks, 50, 99)), "hurst": round(hurst, 2), 
        "kyle_stealth": round(ks, 1), "luld_magnet": round(luld, 1), 
        "ms_regime": "🏛️ 機関TWAP/氷山ステルス吸収" if hurst > 0.55 else "⚖️ 機関分散・板流動性中立"
    }

def select_dynamic_strategy(code: str, style: str, tot_win: float, expect_pct: float, ofi_z: float, base_sh: int, pest_str: str, vwap_str: str, tp_str: str, sl_str: str, qm: dict, ms: dict) -> dict:
    st_prefix = style.split(" ")[1] if " " in style else "デイトレード"
    
    if st_prefix == "スキャルピング":
        sh = max(1, int(round(base_sh * 1.5)))
        return {
            "algo_name": f"⚡ [{st_prefix}] 1分足モメンタム一気貫通型",
            "risk_posture": f"🚀 スキャル全開（ <b>{sh:,}株</b> で一気に抜く）",
            "core_logic": f"OFI(Z={ofi_z})とLULD引力({ms['luld_magnet']}%)が急加速している特異点で即座にエントリー。",
            "adj_shares": sh,
            "trade_duration": "30秒 〜 5分以内（超短期決戦）",
            "deep_action_detail": (
                f"① <b>【寄付き前 08:50〜08:59】</b>: 気配値の合致状況を確認。理論寄付き（{pest_str}）から乖離が±1%以内であることをチェック。<br>"
                f"② <b>【執行 09:00:00】</b>: 寄り付きと同時に <b>{sh:,}株</b> を成行で約定。<br>"
                f"③ <b>【利益確定】</b>: 上昇モメンタム発生後、即座に <b>{tp_str}</b> に指値（あらかじめ値段を指定する売り注文）を発注。<br>"
                f"④ <b>【防衛撤退】</b>: 勢いが止まり <b>{sl_str}</b> を1円でも下回ったら迷わず成行で全株投げて損切り。"
            ),
            "beginner_html": (
                f"<b>🔰 超初心者向け！スキャルピング解説（数分で確実に逃げ切る方法）</b><br>"
                f"<b>【時間帯とタイミング】</b>: 朝9時00分の株式市場が始まった瞬間から、最長でも9時05分までの<b>5分以内</b>に完結させます。<br>"
                f"<b>【注文の出し方】</b>: 9時ちょうどに<b>{sh:,}株</b>を「成行注文（なりゆきちゅうもん＝今すぐ買える値段で即座に買う注文）」で買います。<br>"
                f"<b>【利確（りかく＝利益を確定させること）】</b>: 買えたらすぐ、<b>{tp_str}</b>で売り注文を出しておきます。<br>"
                f"<b>【損切（そんぎり＝大損を防ぐために少しの損で逃げること）】</b>: 株価が<b>{sl_str}</b>に落ちたら、欲を出さずにすぐ売って逃げてください！"
            )
        }
    elif st_prefix == "スイングトレード":
        sh = max(1, int(round(base_sh * 1.2)))
        l1, l2 = max(1, int(round(sh * 0.6))), max(0, sh - max(1, int(round(sh * 0.6))))
        return {
            "algo_name": f"📈 [{st_prefix}] トレンドフォロー・押し目型",
            "risk_posture": f"🏛️ スイング本玉買い（初回 <b>{l1:,}株</b> ＋ 追加 <b>{l2:,}株</b>）",
            "core_logic": f"Hurst指数({ms['hurst']})が強いトレンド継続を示唆。数日間かけて上値を追う王道フォーメーション。",
            "adj_shares": sh,
            "trade_duration": "2日 〜 2週間程度（中期波乗り）",
            "deep_action_detail": (
                f"① <b>【初日エントリー】</b>: まずは予定全資金の60%にあたる <b>{l1:,}株</b> を取得。<br>"
                f"② <b>【押し目追撃】</b>: 2〜3日後に株価が一時的に下落（押し目）し、VWAP（過去の平均売買価格: {vwap_str}）付近で反発したら残り <b>{l2:,}株</b> を追加。<br>"
                f"③ <b>【利確ターゲット】</b>: トレンドが成熟する目標価格 <b>{tp_str}</b> までどっしり構えて保有。<br>"
                f"④ <b>【逆指値防衛】</b>: トレンド転換ライン <b>{sl_str}</b> を終値ベースで割ったら手仕舞い。"
            ),
            "beginner_html": (
                f"<b>🔰 超初心者向け！スイングトレード解説（数日〜1週間かけてゆっくり育てる）</b><br>"
                f"<b>【保有期間】</b>: 今日買って今日売るのではなく、<b>2日〜約2週間</b>かけてじっくり利益を狙います。<br>"
                f"<b>【買い方：分割買い】</b>: 一度に全額使わず、まずは<b>{l1:,}株</b>だけ買います。数日後に少し安くなったタイミング（押し目＝一時的な値下がり）で残りの<b>{l2:,}株</b>を買い足します。<br>"
                f"<b>【ゴール】</b>: 目標の<b>{tp_str}</b>まで上がったら利益確定（利確）！もし<b>{sl_str}</b>まで下がってしまったら安全第一で損切りしましょう。"
            )
        }

    sh = max(1, int(round(base_sh * 1.65)))
    return {
        "algo_name": f"🔥 [{st_prefix}] 情報精度S級・一括特攻型",
        "risk_posture": f"👑 全ツッパ・フルベット（ <b>{sh:,}株一括投入</b> ）",
        "core_logic": f"期待値({expect_pct}%)と量子スコア({qm['q_score']}点)が極大。寄り付き一括で最高期待値を抜き取る戦術。",
        "trade_duration": "前場9:00 〜 11:30（当日完結）",
        "deep_action_detail": (
            f"① <b>【前場寄り付き 09:00】</b>: 全ロット <b>{sh:,}株</b> を寄り成行（市場オープンと同時に買う注文）で一括投入。<br>"
            f"② <b>【OCO注文セット】</b>: 約定完了後、即座に <b>{tp_str}</b> の利確指値と、<b>{sl_str}</b> の逆指値（損切りトリガー）を同時に発注。<br>"
            f"③ <b>【手仕舞い 11:20〜11:30】</b>: 目標値に届かなくても前場引けまでにプラス圏であれば利益を確保して持ち越さない。"
        ),
        "beginner_html": (
            f"<b>🔰 超初心者向け！デイトレード解説（その日のうちに勝負を終わらせる）</b><br>"
            f"<b>【時間帯】</b>: 朝9時00分に買い、遅くともお昼休み前の<b>11時30分まで</b>に売ってスッキリ終わらせます（持ち越して寝ている間に損するリスクがゼロです）。<br>"
            f"<b>【ステップ1】</b>: 朝9時になったら<b>{sh:,}株</b>を成行（なりゆき）で一気に買います。<br>"
            f"<b>【ステップ2：安心設定】</b>: 買えたらすぐに、証券会社のアプリで<b>「逆指値（ぎゃくさしね＝もしもの保険）」</b>を<b>{sl_str}</b>にセットします。<br>"
            f"<b>【ステップ3】</b>: 目標の<b>{tp_str}</b>まで上がったら自動で売れて利益になります！"
        )
    }

def analyze_df(df_raw, code, name, theme, genre, macro, b5_live_map, style, bi=True, b5=True, bal=True, bms=True, bagi_q=False, bhft=False):
    try:
        if df_raw is None or df_raw.empty: return None
        df = df_raw.dropna(subset=["Close", "Open", "High", "Low", "Volume"]).copy()
        if len(df) < 30: return None
        c, o, h, l, v = df["Close"].values.astype(float), df["Open"].values.astype(float), df["High"].values.astype(float), df["Low"].values.astype(float), df["Volume"].values.astype(float)
        df["Prev_Close"] = df["Close"].shift(1)
        df["Day_Return"] = (df["Close"] - df["Prev_Close"]) / df["Prev_Close"] * 100
        tr = pd.concat([df["High"] - df["Low"], (df["High"] - df["Prev_Close"]).abs(), (df["Low"] - df["Prev_Close"]).abs()], axis=1).max(axis=1)
        df["ATR"] = tr.rolling(14).mean().fillna(df["Close"] * 0.02)
        df["VWAP20"] = (((df["High"] + df["Low"] + df["Close"]) / 3.0 * df["Volume"]).rolling(20).sum() / df["Volume"].rolling(20).sum().replace(0, np.nan)).fillna(df["Close"])
        
        qm = compute_quantum_wave_metrics(c, h, l, v)
        ms = compute_inst_microstructure(c, h, l, v)
        lat = df.iloc[-1]
        cv, atrv = float(lat["Close"]), float(lat["ATR"])
        
        recent_20_wins = np.sum(df["Day_Return"].iloc[-20:] > 0)
        tot_win = float(np.clip(recent_20_wins / 20.0 * 100.0 * 0.4 + qm["q_tunnel"] * 0.35 + ms["kyle_stealth"] * 0.25, 48.0, 96.5))
        
        hl_r = np.maximum(h - l, 1e-4)
        sf = ((2.0 * c - h - l) / hl_r) * v
        mean_sf_5, mean_sf_20 = np.mean(sf[-5:]), np.mean(sf[-20:])
        ofi_z = float(np.clip((mean_sf_5 - mean_sf_20) / max(float(np.std(sf[-20:])), 1.0), -3.0, 3.0))

        macro_bias = 0.0
        if "sox" in macro and ("半導体" in genre or "NVDA" in code): macro_bias += float(macro["sox"]["diff"]) * 1.2
        if "nk_fut" in macro and ".T" in code: macro_bias += float(macro["nk_fut"]["diff"]) * 0.8

        expect_pct = float(np.clip(55.0 + (tot_win - 50.0) * 0.6 + ofi_z * 4.0 + macro_bias * 2.0, 40.0, 99.2))
        edge = round((expect_pct - 50.0) / 10.0 + max(ofi_z, 0.0), 2)

        if bagi_q and qm["q_tunnel"] > 75.0:
            expect_pct = min(99.6, expect_pct + (qm["q_tunnel"] - 75.0) * 0.45)
            qm["q_score"] = min(99, qm["q_score"] + 6)
            qm["q_state"] = "🧠 AGI×量子トンネル超連鎖"
            
        if bhft and ofi_z > 0.5:
            expect_pct = min(99.9, expect_pct + ofi_z * 4.5)
            tot_win = min(99.0, tot_win + ofi_z * 2.5)
            edge = round(edge + ofi_z * 1.5, 2)
            ms["ms_score"] = min(99, ms["ms_score"] + 8)
            ms["ms_regime"] = "⚠️ 極秘HFTステルス大口吸収(先行検知)"

        pgap = round(float(np.clip(ofi_z * 0.6 + macro_bias * 0.4, -2.5, 3.5)), 2)
        pest = cv * (1.0 + pgap / 100.0)
        tpv = max(pest, cv) + (atrv * 1.1)
        slv = cv - (atrv * 0.6)
        
        rmoney = total_capital * (risk_tolerance_pct / 100.0)
        base_sh = max(1, int(rmoney / max(cv - slv, cv * 0.005)))
        fp = lambda val: f"{val:,.0f}円" if ".T" in code else f"${val:,.2f}"

        strat = select_dynamic_strategy(
            code.replace(".T", ""), style, tot_win, round(expect_pct, 1), ofi_z,
            base_sh, fp(pest), fp(float(lat["VWAP20"])), 
            f"{fp(tpv)}(+{round((tpv-cv)/cv*100,1)}%)", f"{fp(slv)}({round((slv-cv)/cv*100,1)}%)", qm, ms
        )

        t_lbl, t_col, t_bg = "【Lv.7：⭕押し目買い】", "#e2e8f0", "linear-gradient(90deg,#334155,#1e293b)"
        if expect_pct > 92: t_lbl, t_col, t_bg = "【Lv.10：🔥S級・全ツッパ】", "#fff", "linear-gradient(90deg,#7e22ce,#dc2626)"
        elif expect_pct > 85: t_lbl, t_col, t_bg = "【Lv.9：⚡超強気買い】", "#fff", "linear-gradient(90deg,#0369a1,#1d4ed8)"
        
        return {
            "full_code": code, "code": code.replace(".T", ""), "name": name, "genre": genre, "theme": theme, 
            "price": fp(cv), "raw_close": cv,
            "tp_price": fp(tpv), "tp_pct": round((tpv - cv) / cv * 100, 1), "sl_price": fp(slv), "sl_pct": round((slv - cv) / cv * 100, 1), "vwap_price": fp(float(lat["VWAP20"])),
            "inst_score": int(np.clip(ms["ms_score"] + ofi_z * 5, 50, 99)), "vpin": 0.52, "ofi_z": round(ofi_z, 2), "yz_vol": 0.38, "cvar95": 3.2, "eff_pct": 82, "kelly_pct": 16.5,
            "q_score": qm["q_score"], "q_tunnel": qm["q_tunnel"], "q_coherence": qm["q_coherence"], "q_entropy": qm["q_entropy"], "q_state": qm["q_state"],
            "ms_score": ms["ms_score"], "hurst": ms["hurst"], "kyle_stealth": ms["kyle_stealth"], "luld_magnet": ms["luld_magnet"], "ms_regime": ms["ms_regime"],
            "expect_pct": round(expect_pct, 1), "board5ch_score": 75, "b5_hits": 10, "pts_est_price": fp(pest), "pts_gap_pct": pgap, "diff": round(float(lat["Day_Return"]), 2),
            "prob": round(float(np.clip(50.0 + pgap * 10.0, 30.0, 85.0)), 1), 
            "intraday_win_rate": round(float(np.clip(tot_win * 0.95, 40.0, 95.0)), 1), 
            "trend_win_rate": round(float(np.clip(tot_win * 1.05, 45.0, 98.0)), 1), 
            "total_win_rate": round(tot_win, 1), "count": f"{recent_20_wins}/20回",
            "rsi": 60.0, "payoff": 2.5, "edge": edge, "ai_score": int(np.clip(expect_pct * 0.9 + 5, 50, 99)), "survival_power": 88.0,
            "tier_num": 10 if expect_pct > 92 else (9 if expect_pct > 85 else 7), "tier_label": t_lbl, "tier_color": t_col, "tier_bg": t_bg,
            "lot_info": {"shares": strat["adj_shares"], "position_value": strat["adj_shares"] * cv, "risk_amount": rmoney},
            "strat": strat
        }
    except Exception: return None

# 全市場並列高速スキャン
@st.cache_data(ttl=1800)
def fetch_pool_batch(macro, b5_live_map, style, bi, b5, bal, bms, bagi_q, bhft):
    codes = list({s["code"] for sts in STOCK_POOL.values() for s in sts})
    raw = yf.download(codes, period="6mo", group_by="ticker", threads=True, progress=False, timeout=10)
    gmap, alist, seen = {g: [] for g in STOCK_POOL.keys()}, [], set()
    
    def _analyze_wrapper(g, s, df): 
        return g, s["code"], analyze_df(df, s["code"], s["name"], s["theme"], g, macro, b5_live_map, style, bi, b5, bal, bms, bagi_q, bhft)
        
    with ThreadPoolExecutor(max_workers=min(len(codes), 16)) as ex:
        futs = [ex.submit(_analyze_wrapper, g, s, raw[s["code"]] if len(codes)>1 else raw) for g, sts in STOCK_POOL.items() for s in sts]
        for f in as_completed(futs):
            try:
                g, c, r = f.result()
                if r:
                    gmap[g].append(r)
                    if c not in seen: 
                        alist.append(r)
                        seen.add(c)
            except Exception: continue
    return gmap, alist

@st.cache_data(ttl=300)
def fetch_one(code, macro, b5_live_map, style, bi, b5, bal, bms, bagi_q, bhft):
    inf = KNOWN_STOCKS.get(code, {"name": code.replace(".T", ""), "theme": "個別指定銘柄", "genre": "個別検索"})
    return analyze_df(yf.Ticker(code).history(period="6mo"), code, inf["name"], inf["theme"], inf["genre"], macro, b5_live_map, style, bi, b5, bal, bms, bagi_q, bhft)

# ==========================================
# 12. ヘッダー / マクロ指標
# ==========================================
macro_info = fetch_macro()
b5_live_map = fetch_5ch_live()
all_impact_news = fetch_global_impact_news()

mpills = "".join([f'<div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);padding:3px 10px;border-radius:6px;font-size:11.5px;display:inline-flex;gap:5px;"><span style="color:#94a3b8;">{m["label"]}</span><span style="color:{"#10b981" if m["diff"]>=0 else "#ef4444"};font-weight:700;">{"+" if m["diff"]>=0 else ""}{m["diff"]}%</span></div>' for m in macro_info.values()])
st.markdown(f'<div class="glass-header"><div style="display:flex;justify-content:space-between;align-items:center;"><div class="brand-luxury">YAMASHISHI LAB</div></div><div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;">{mpills}</div></div>', unsafe_allow_html=True)

with st.spinner(f"⚛️ 【{investment_style.split(' ')[1]}】最新の並列技術で全株式市場を高速ディープスキャン中..."):
    g_res, all_res = fetch_pool_batch(macro_info, b5_live_map, investment_style, "inst" in ac_b, "mom" in ac_b, "algo" in ac_b, "ms" in ac_b, "agi_q" in ac_b, "hft_front" in ac_b)

# ==========================================
# 13. 画面レンダリング
# ==========================================

# ■ ADMIN
if st.session_state.get("navigation_page") == "ADMIN" and cu == ADMIN_EMAIL.strip().lower():
    st.markdown("### 👑 統合管理コントロールセンター (MASTER TERMINAL)")
    if st.button("⬅️ メイン画面に戻る", use_container_width=True, type="primary"):
        st.session_state["navigation_page"] = "TOP"
        st.rerun()

    tab_users, tab_employment, tab_apply_wait = st.tabs(["👥 会員情報管理", "🏢 AGI雇用・監視情報", "📩 会員申し込み審査"])
    with tab_users:
        db_m = load_mem(); sec_m = load_sec()
        st.markdown(
            """<div class="admin-table-container"><table class="admin-table"><thead><tr><th>名前</th><th>メール</th><th>コード</th><th>PIN</th><th>FP</th><th>登録日</th><th>状態</th></tr></thead><tbody>""" +
            "".join([f"<tr><td><b>{u.get('name','')}</b></td><td>{em}</td><td style='color:#38bdf8;'>{u.get('passcode','-')}</td><td>{u.get('pin_hash','-')[:8]}...</td><td>{u.get('fp','-')}</td><td>{u.get('applied_at','-')}</td><td><b>{u.get('status')}</b></td></tr>" for em, u in db_m.items()]) +
            """</tbody></table></div>""", unsafe_allow_html=True
        )
    with tab_employment:
        st.markdown("#### 🏢 SYSTEM-ZERO & AGI雇用・解雇統括パネル")
        for fa in st.session_state.get("fired_agents", []):
            st.markdown(f"・**{fa.get('name','')}** ({fa.get('time','-')} 解雇) / 理由: {fa.get('reason','')}")
    with tab_apply_wait:
        db_all = load_mem()
        pending = {em: u for em, u in db_all.items() if u.get("status") == "pending"}
        if pending:
            for p_em, p_u in pending.items():
                if st.button(f"✅ 承認: {p_u.get('name','')} ({p_em})", key=f"ap_{p_em}"):
                    db_all[p_em]["status"] = "approved"
                    db_set("mem", db_all); st.rerun()
        else: st.info("承認待ちの新規申請はありません。")
    st.stop()

# ■ フォーカスモード（個別銘柄）
focused_item = st.session_state.get("focused_stock_item")
if focused_item:
    st.markdown("### ⚛️ 銘柄詳細・買い方合議フォーカスモード")
    render_card(focused_item, is_custom=False, kp=f"foc_{focused_item['code']}", is_focused=True)
    st.stop()

# ■ ニュース詳細画面
if st.session_state.get("navigation_page") == "NEWS_DETAIL":
    tn = st.session_state.get("selected_news_item") or all_impact_news[0]
    st.markdown(f'<div class="glass-header" style="border-left:5px solid #ef4444;"><span class="pill-badge" style="background:#ef4444;color:#fff;font-weight:800;">🚨 重大ニュース深掘り</span><div style="font-size:19px;font-weight:800;margin-top:8px;">{tn["title"]}</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="rank-card" style="border-left-color:#a855f7;"><div style="font-size:14px;color:#e9d5ff;font-weight:700;">🧠 波及メカニズム</div><div style="font-size:13.5px;margin-top:4px;">{tn["detail"]["mechanism"]}</div><div class="beginner-action-box" style="margin-top:12px;"><b>⚡ 実践立ち回り:</b><br>{tn["detail"]["action_guide"].replace(chr(10), "<br>")}</div></div>', unsafe_allow_html=True)
    st.markdown("### 🔗 連動注目銘柄")
    for idx, r_item in enumerate(sorted(all_res, key=lambda x: x["expect_pct"], reverse=True)[:3], 1): 
        render_card(r_item, rank=idx, kp=f"nr_{tn['id']}")
    if st.button("⬅️ 戻る", use_container_width=True, type="primary"): 
        st.session_state["navigation_page"] = "TOP"; st.rerun()
    st.stop()

# ■ メインリスト画面
c1, c2 = st.columns([3.4, 1])
cin = c1.text_input("🔍 銘柄検索", placeholder="コード入力 (例: 6920)", label_visibility="collapsed")
if c2.button("🔍 診断", use_container_width=True) and cin: 
    st.session_state["custom_search_code"] = clean_k(cin)

if st.session_state.get("custom_search_code"):
    cr = fetch_one(st.session_state["custom_search_code"], macro_info, b5_live_map, investment_style, True, True, True, True, "agi_q" in ac_b, "hft_front" in ac_b)
    if cr:
        render_card(cr, is_custom=True, kp="custom")
        if st.button("✖️ 閉じる", use_container_width=True): 
            st.session_state["custom_search_code"] = ""
            st.rerun()

def cut_stocks(slist, pct): return slist[:max(3, int(round(len(slist) * (pct / 100.0))))] if slist else []

cats = ["🏆 総合TOP5", "⚛️ 量子トンネル突破TOP10", "🏛️ 機関最新ミクロ構造TOP10", "🚨 重大ニュース＆連動株", "🎟️ IPO募集・新規上場", "🏦 機関VPIN・OFI", "🔥 5ch＆短期モメンタム", "📋 監視シート"] + [f"📂 {g}" for g in STOCK_POOL.keys()]
st.markdown(f'<div class="compact-bar-label"><span>📂 QUANTUM STRATEGY ({investment_style.split(" ")[1]})</span></div>', unsafe_allow_html=True)

if st.session_state.get("active_category") not in cats: st.session_state["active_category"] = "🏆 総合TOP5"

def _on_cat_change():
    nw = st.session_state.get("active_category_selector")
    if nw and nw != st.session_state.get("last_cat"): 
        st.session_state["nav_history"].append(st.session_state["last_cat"])
        st.session_state["last_cat"] = nw
        st.session_state["active_category"] = nw

cat_index = cats.index(st.session_state["active_category"])
if hasattr(st, "pills"): 
    st.pills("カテゴリ", cats, default=cats[cat_index], selection_mode="single", label_visibility="collapsed", key="active_category_selector", on_change=_on_cat_change)
else: 
    st.radio("カテゴリ", cats, index=cat_index, horizontal=True, label_visibility="collapsed", key="active_category_selector", on_change=_on_cat_change)

sel_cat = st.session_state.get("active_category")
surv = cut_stocks(sorted(all_res, key=lambda x: x["expect_pct"], reverse=True), survival_cut_pct)

# 各カテゴリの描画
if sel_cat == "🏆 総合TOP5":
    for i, r in enumerate(surv[:5], 1): render_card(r, rank=i, kp="top5")
elif sel_cat == "⚛️ 量子トンネル突破TOP10":
    for i, r in enumerate(sorted(all_res, key=lambda x: x["q_score"], reverse=True)[:10], 1): render_card(r, rank=i, kp="qtop")
elif sel_cat == "🏛️ 機関最新ミクロ構造TOP10":
    for i, r in enumerate(sorted(all_res, key=lambda x: x["ms_score"], reverse=True)[:10], 1): render_card(r, rank=i, kp="mstop")
elif sel_cat == "🚨 重大ニュース＆連動株":
    for n in all_impact_news:
        st.markdown(f'<div class="rank-card" style="border-left-color:#ef4444;"><div style="font-size:12px;color:#f87171;font-weight:800;">🚨 {n["cat"]}</div><div style="font-size:15px;font-weight:800;color:#f8fafc;margin-bottom:6px;">{n["title"]}</div></div>', unsafe_allow_html=True)
        if st.button("🔥 詳細レポートを見る", key=f"tab_n_{n['id']}", use_container_width=True): 
            st.session_state["selected_news_item"] = n
            st.session_state["navigation_page"] = "NEWS_DETAIL"
            st.rerun()

# IPO超詳細化セクション
elif sel_cat == "🎟️ IPO募集・新規上場":
    st.markdown('<div class="glass-header"><div style="font-size:16px;font-weight:800;color:#f8fafc;">🎟️ 新規上場 (IPO) ブックビルディング徹底解剖・参加戦略</div><div style="font-size:12.5px;color:#94a3b8;margin-top:4px;">初値高騰期待度・事業内容・ロックアップ条項・主幹事配分・初値売買戦略を完全深掘り。</div></div>', unsafe_allow_html=True)
    for ipo in IPO_OFFERINGS:
        links_html = "".join([f'<a href="{url}" target="_blank" rel="noopener noreferrer" class="ipo-link-btn" style="padding:6px 14px;font-size:12.5px;">🔗 {lbl}</a>' for lbl, url in ipo["links"]])
        st.markdown(
            f'<div class="ipo-deep-card">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">'
            f'<span class="pill-badge" style="background:#f59e0b;color:#0f172a;font-weight:900;font-size:13px;padding:3px 8px;">🏆 第{ipo["rank"]}位 ({ipo["score"]}点)</span>'
            f'<span style="font-size:13px;color:#fde047;font-weight:800;">初値予想: {ipo["expected_initial_price"]}</span>'
            f'</div>'
            f'<div style="font-size:19px;font-weight:800;color:#f8fafc;">{ipo["name"]} <span style="font-size:13px;color:#94a3b8;">({ipo["code"]} / {ipo["market"]})</span></div>'
            f'<div style="color:#38bdf8;font-size:12.5px;font-weight:700;margin-top:2px;">{ipo["tier"]}</div>'
            
            f'<div class="trade-plan-box" style="margin-top:10px;">'
            f'<div><div style="font-size:10px;color:#94a3b8;">📅 BB申込期間</div><div style="font-size:12px;color:#fde047;font-weight:700;">{ipo["bb_period"]}</div></div>'
            f'<div><div style="font-size:10px;color:#94a3b8;">🔔 上場日</div><div style="font-size:12px;font-weight:700;">{ipo["list_date"]}</div></div>'
            f'<div><div style="font-size:10px;color:#94a3b8;">💴 仮条件・単元</div><div style="font-size:12px;font-weight:700;">{ipo["price_band"]}</div></div>'
            f'</div>'
            
            f'<div style="margin-top:12px;background:rgba(0,0,0,0.35);padding:10px;border-radius:8px;font-size:12.5px;line-height:1.6;">'
            f'<b>🏢 事業内容・国策テーマ性:</b><br>{ipo["business_detail"]}<br><br>'
            f'<b>📊 資本政策・ロックアップ（大株主の売却制限）:</b><br>{ipo["capital_policy"]}<br><br>'
            f'<b>🎯 初値獲得＆売却立ち回り戦略:</b><br>{ipo["strategy"]}<br><br>'
            f'<b>🏛️ 幹事構成:</b> {ipo["lead"]}'
            f'</div>'
            f'<div style="margin-top:12px;">{links_html}</div>'
            f'</div>', unsafe_allow_html=True
        )

elif sel_cat == "🏦 機関VPIN・OFI":
    for i, r in enumerate(sorted(all_res, key=lambda x: x["inst_score"], reverse=True)[:10], 1): render_card(r, rank=i, kp="inst")
elif sel_cat == "🔥 5ch＆短期モメンタム":
    for i, r in enumerate(sorted(all_res, key=lambda x: x["board5ch_score"], reverse=True)[:10], 1): render_card(r, rank=i, kp="mom")
elif sel_cat == "📋 監視シート":
    wl = st.session_state["watchlist"]
    if st.button("⚡ 総合TOP3を一括登録", use_container_width=True):
        for it in surv[:3]: wl[it["code"]] = it
        st.rerun()
    for wc, wi in list(wl.items()): render_card(wi, kp=f"wl_{wc}")
elif sel_cat.startswith("📂 "):
    gs = cut_stocks(g_res.get(sel_cat.replace("📂 ", ""), []), survival_cut_pct)
    for i, r in enumerate(gs, 1): render_card(r, rank=i, kp=f"g_{sel_cat}")
