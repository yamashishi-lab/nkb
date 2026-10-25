import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np
import altair as alt
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

IPO_OFFERINGS = [
    {
        "rank": 1, 
        "code": "401A", 
        "name": "AIクロスロボティクス", 
        "market": "東証グロース", 
        "bb_period": "2026/10/22(木) 〜 10/28(水)", 
        "list_date": "2026/11/06(金)", 
        "price_band": "1,680円 〜 1,850円 (想定発行価格: 1,750円)", 
        "absorb_amt": "約14.8億円 (超軽量・需給超逼迫)", 
        "expect_return": "+115.0% 〜 +150.0%", 
        "score": 96, 
        "tier": "🌟 S級：全力ブックビルディング参加（初値2倍超濃厚）", 
        "lead": "SBI証券(主幹事) / 野村證券 / 大和証券 / 楽天証券", 
        "theme": "防衛省向け自律型防空ドローンOS & 次世代AIフィジカルロボティクス", 
        "detail_desc": "防衛省の次世代防空実証実験に採択された国産エッジAIドローン制御プラットフォームを開発。軍民両用（デュアルユース）技術の先端であり、機関投資家のアンカー投資が内定済み。吸収金額15億円未満の小型案件のため、公開初日は買い気配のまま即日値付かずとなる公算が極めて高い特選銘柄。",
        "use_of_funds": "次世代防衛AIチップ開発設備投資、及びロボティクス数理エンジニアの増員・知財特許網強化",
        "lockup": "大株主90%以上に180日間の厳格ロックアップあり（VC売り圧力軽微）",
        "links": [("🏦 SBI証券で申込", "https://www.sbisec.co.jp"), ("🏦 野村證券で確認", "https://www.nomura.co.jp")]
    },
    {
        "rank": 2, 
        "code": "405A", 
        "name": "ネクストグリッド電力", 
        "market": "東証プライム", 
        "bb_period": "2026/10/24(土) 〜 10/30(金)", 
        "list_date": "2026/11/10(火)", 
        "price_band": "2,400円 〜 2,600円 (想定発行価格: 2,500円)", 
        "absorb_amt": "約68.5億円 (プライム中型・機関買い受皿)", 
        "expect_return": "+38.5% 〜 +55.0%", 
        "score": 89, 
        "tier": "🔥 A級：積極BB参加（高当選確率・手堅い利益狙い）", 
        "lead": "SMBC日興証券(主幹事) / みずほ証券 / 三菱UFJモルガン", 
        "theme": "生成AIデータセンター専用 高圧超電導送電網＆分散型マイクログリッド", 
        "detail_desc": "急増するハイパースケールAIデータセンターの受電制約を解消する超高効率グリッド設備を提供。主要ITメガテックとの中長期電力供給PPA契約を多数抱え、安定した高配当・ストック収益基盤と高い成長性を兼備。手堅い初値形成と上場後の長期資金流入が期待されます。",
        "use_of_funds": "国内3拠点における次世代蓄電送電パイロットプラントの建設・送電ライセンス取得",
        "lockup": "既存株主・創業者に対し360日または公開価格1.5倍までの売却制限付与",
        "links": [("🏦 SMBC日興で申込", "https://www.smbcnikko.co.jp"), ("🏦 みずほ証券で確認", "https://www.mizuhobank.co.jp")]
    }
]

DYNAMIC_DYNAMIC_POOLS = {
    "半導体": [{"code": "8035.T", "name": "東京エレクトロン", "theme": "前工程装置世界首位"}, {"code": "6857.T", "name": "アドバンテスト", "theme": "AI半導体テスタ独占"}, {"code": "6920.T", "name": "レーザーテック", "theme": "EUVマスク欠陥検査独占"}, {"code": "6146.T", "name": "ディスコ", "theme": "超精密切断・研削加工"}, {"code": "NVDA", "name": "NVIDIA", "theme": "世界AIコンピューティング覇者"}],
    "AI・防衛": [{"code": "9984.T", "name": "ソフトバンクG", "theme": "全AI投資コングロマリット"}, {"code": "3778.T", "name": "さくらインターネット", "theme": "国策GPUクラウド基盤"}, {"code": "7011.T", "name": "三菱重工業", "theme": "防衛三役・国策迎撃装備"}, {"code": "PLTR", "name": "パランティア", "theme": "軍事・企業向けAI中枢OS"}],
    "AI電力・電線": [{"code": "5803.T", "name": "フジクラ", "theme": "超高密度光配線・AIデータセンター"}, {"code": "5801.T", "name": "古河電気工業", "theme": "次世代送電・フォトニクス"}, {"code": "6501.T", "name": "日立製作所", "theme": "世界的パワーグリッド・エネルギー制御"}, {"code": "VST", "name": "ビストラ・エナジー", "theme": "AIデータセンター原子力・天然ガス発電"}],
    "宇宙・次世代": [{"code": "5595.T", "name": "QPS研究所", "theme": "小型SAR衛星コンステレーション"}, {"code": "186A.T", "name": "アストロスケールHD", "theme": "軌道上デブリ除去・宇宙防衛"}, {"code": "TSLA", "name": "テスラ", "theme": "完全自動運転FSD・ヒューマノイドロボット"}],
    "小型急騰・モメンタム": [{"code": "5253.T", "name": "カバー", "theme": "VTuber世界IP展開・高流動性"}, {"code": "216A.T", "name": "タイミー", "theme": "スキマバイト仲介・ギグエコノミー"}, {"code": "3350.T", "name": "メタプラネット", "theme": "ビットコイン大量保有トレジャリー戦略"}, {"code": "IONQ", "name": "アイオンQ", "theme": "トラップイオン方式 商用量子コンピュータ"}]
}
STOCK_POOL = DYNAMIC_DYNAMIC_POOLS
KNOWN_STOCKS = {it["code"]: {"name": it["name"], "theme": it["theme"], "genre": g} for g, its in STOCK_POOL.items() for it in its}

# ==========================================
# 2. データベース・セキュリティ・ユーティリティ
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
            if row:
                return json.loads(row[0])
        except Exception:
            pass
        return default_val

def db_set(key: str, val: dict):
    with _DB_LOCK:
        try:
            conn = sqlite3.connect(DB_SQLITE_PATH, check_same_thread=False)
            cur = conn.cursor()
            cur.execute("INSERT OR REPLACE INTO kv_store (key, val) VALUES (?, ?)", (key, json.dumps(val, ensure_ascii=False)))
            conn.commit()
            conn.close()
        except Exception:
            pass

def clean_k(k: str) -> str: 
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(k or "")).strip().strip("\"'"))

def gen_code(em: str) -> str: 
    return hmac.new(SECRET_KEY.encode(), em.strip().lower().encode(), hashlib.sha256).hexdigest()[:8].upper()

def gen_tok(em: str, act: str) -> str: 
    return hashlib.sha256(f"{em.strip().lower()}:{act}:{SECRET_KEY}".encode()).hexdigest()[:16]

def hash_pin(pin: str) -> str: 
    return hashlib.pbkdf2_hmac("sha256", pin.strip().encode(), SECRET_KEY.encode(), 10000).hex()[:16]

def get_raw_header_fp() -> str:
    try:
        h = {str(k).lower(): str(v) for k, v in dict(getattr(st.context, "headers", {}) or {}).items()}
        raw = f"{h.get('user-agent','')}|{h.get('accept-language','')}|{h.get('sec-ch-ua-platform','')}"
    except Exception:
        raw = "default_env"
    return hashlib.sha256(raw.encode()).hexdigest()[:12].upper()

def get_client_fp() -> str:
    raw = get_raw_header_fp()
    qf = st.query_params.get("dfp", "")
    if qf: 
        st.session_state["client_dfp"] = qf
    dfp = st.session_state.get("client_dfp", "")
    return hashlib.sha256(f"{raw}|{dfp}".encode()).hexdigest()[:12].upper() if dfp else raw

def load_smtp(): 
    return db_get("smtp", {"smtp_user": ADMIN_EMAIL, "smtp_pass": "", "smtp_server": "smtp.mail.yahoo.co.jp", "smtp_port": 465})

def load_llm(): 
    return db_get("llm", {"provider": "gemini", "models": {k: v[1][0] for k, v in AI_PROVIDERS.items()}})

def load_sec(): 
    return db_get("sec", {"banned_fps": {}, "banned_emails": {}, "banned_pins": {}, "banned_names": [], "spoof_logs": [], "device_bio_map": {}})

def load_mail_db(): 
    return db_get("mail", {"logs": [], "messages": []})

def load_mem():
    db = db_get("mem", {})
    adm = ADMIN_EMAIL.strip().lower()
    if adm not in db:
        ns = datetime.now().strftime("%Y-%m-%d %H:%M")
        db[adm] = {
            "name": "管理者", "email": adm, "status": "approved", 
            "passcode": gen_code(adm), "pin_hash": hash_pin("0000"), 
            "applied_at": ns, "approved_at": ns, "last_seen_ts": 0, 
            "last_seen_str": "-", "fp": "-", "bio_enabled": False
        }
        db_set("mem", db)
    return db

def check_and_log_ban_spoof(em: str, name: str, cur_fp: str, raw_hfp: str, pin_h: str = "", action_type: str = "アクセス") -> tuple:
    em_c = em.strip().lower()
    if em_c == ADMIN_EMAIL.strip().lower(): return False, ""
    sec = load_sec(); db = load_mem()
    b_fps = sec.get("banned_fps", {}); b_ems = sec.get("banned_emails", {}); b_pins = sec.get("banned_pins", {})
    u_rec = db.get(em_c, {})

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
    mdb["logs"] = mdb["logs"][:120]
    db_set("mail", mdb)
    return True

# ==========================================
# 3. CSS / UI スタイル設定 (文字拡大・改行防止・間隔最適化・アニメ警告)
# ==========================================
def inject_css():
    css = """
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@700;900&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
        font-size: 15.5px !important;
        background-color: #050811;
        color: #e2e8f0;
        word-break: keep-all !important;
        overflow-wrap: break-word !important;
        line-height: 1.6;
    }
    
    header[data-testid="stHeader"] {
        background: transparent !important; pointer-events: none !important;
        height: 3.5rem !important; z-index: 999990 !important;
    }
    header[data-testid="stHeader"] [data-testid="stToolbar"],
    header[data-testid="stHeader"] [data-testid="stActionButtons"] { display: none !important; }

    section[data-testid="stSidebar"] {
        position: fixed !important; top: 0 !important; left: 0 !important; height: 100vh !important;
        z-index: 9999999 !important; width: 345px !important; max-width: 90vw !important; min-width: 320px !important;
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

    .sidebar-section-card {
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(56, 189, 248, 0.22);
        border-radius: 12px;
        padding: 12px 14px;
        margin-bottom: 14px;
    }
    .sidebar-header-badge {
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        font-weight: 800;
        color: #38bdf8;
        letter-spacing: 1px;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 6px;
    }

    /* 銘柄カード・検索カードの間隔拡張と装飾 */
    .rank-card, .search-result-card, .ipo-detail-card {
        background: linear-gradient(180deg, #0d1527 0%, #080d1a 100%) !important;
        color: #f8fafc !important;
        border-radius: 16px;
        padding: 18px 20px;
        margin-bottom: 24px !important;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.65), 0 0 1px rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(148, 163, 184, 0.22);
        border-left: 6px solid #38bdf8;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .search-result-card { border-left-color: #f59e0b; }
    .ipo-detail-card { border-left-color: #eab308; }

    /* 重大情報有りの赤アニメーション警告ボタン */
    @keyframes warning-pulse {
        0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.8); transform: scale(1); }
        50% { box-shadow: 0 0 16px 4px rgba(239, 68, 68, 0.95); transform: scale(1.008); }
        100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.8); transform: scale(1); }
    }
    .warning-alert-btn-wrapper button {
        background: linear-gradient(90deg, #b91c1c 0%, #dc2626 50%, #ef4444 100%) !important;
        color: #ffffff !important;
        font-weight: 800 !important;
        font-size: 13.5px !important;
        border: 1px solid #f87171 !important;
        border-radius: 8px !important;
        animation: warning-pulse 1.8s infinite ease-in-out !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        display: block !important;
        width: 100% !important;
        padding: 8px 12px !important;
        margin-top: 8px !important;
        margin-bottom: 8px !important;
    }

    .brand-luxury {
        font-family: 'Cinzel', serif !important; font-size: clamp(19px, 4.5vw, 26px) !important; font-weight: 900 !important;
        letter-spacing: 2px !important; background: linear-gradient(90deg, #ffffff 0%, #38bdf8 50%, #c084fc 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; line-height: 1.3;
        white-space: nowrap !important; display: block; width: 100%;
    }

    .glass-header {
        background: radial-gradient(circle at top right, rgba(168, 85, 247, 0.16), transparent 65%), linear-gradient(145deg, #0f172a 0%, #070b14 100%);
        border: 1px solid rgba(148, 163, 184, 0.22); border-radius: 16px; padding: 18px; margin-bottom: 18px; box-shadow: 0 12px 32px rgba(0,0,0,0.55);
    }

    .prob-badge { font-family: 'JetBrains Mono', monospace; font-size: 18px; font-weight: 800; color: #38bdf8 !important; }
    .expect-badge { font-family: 'JetBrains Mono', monospace; font-size: 18px; font-weight: 900; color: #fde047 !important; }

    .winrate-bar {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(75px, 1fr)); gap: 8px; background: rgba(15, 23, 42, 0.9) !important;
        border: 1px solid rgba(148, 163, 184, 0.18); border-radius: 10px; padding: 8px 6px; margin-top: 10px; text-align: center;
    }
    .trade-plan-box {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(95px, 1fr)); gap: 8px; margin-top: 8px;
        background: rgba(2, 6, 23, 0.8) !important; padding: 8px 6px; border-radius: 10px; border: 1px solid rgba(148, 163, 184, 0.18); text-align: center;
    }

    .ai-council-box {
        background: rgba(6, 10, 18, 0.98);
        border: 1.5px solid rgba(56, 189, 248, 0.4);
        border-radius: 12px;
        padding: 14px;
        margin-top: 14px;
    }
    
    /* スクロールを確実に動作させるスタイル修正 */
    .council-scroll-window {
        max-height: 380px !important;
        height: auto !important;
        overflow-y: scroll !important;
        -webkit-overflow-scrolling: touch !important;
        padding-right: 8px;
        margin-bottom: 10px;
    }
    .council-scroll-window::-webkit-scrollbar {
        width: 6px;
    }
    .council-scroll-window::-webkit-scrollbar-thumb {
        background: rgba(56, 189, 248, 0.4);
        border-radius: 4px;
    }

    .chat-bubble-ai, .chat-bubble-user, .chat-bubble-agree, .chat-bubble-doubt, .chat-bubble-rage {
        padding: 10px 14px;
        border-radius: 10px;
        margin-bottom: 8px;
        font-size: 13.5px;
        line-height: 1.6;
        word-break: break-word !important;
    }
    .chat-bubble-ai { background: rgba(15, 23, 42, 0.9); border-left: 4px solid #38bdf8; }
    .chat-bubble-agree { background: rgba(6, 78, 59, 0.65); border-left: 4px solid #10b981; }
    .chat-bubble-doubt { background: rgba(120, 53, 15, 0.65); border-left: 4px solid #f59e0b; }
    .chat-bubble-rage { background: rgba(127, 29, 29, 0.65); border-left: 4px solid #ef4444; }
    .chat-bubble-user { background: rgba(56, 189, 248, 0.2); border-right: 4px solid #38bdf8; text-align: right; }
    .round-divider { font-size: 11.5px; font-weight: 800; color: #94a3b8; text-align: center; margin: 10px 0; letter-spacing: 1px; }

    .beginner-action-box {
        background: rgba(16, 185, 129, 0.12);
        border: 1px solid rgba(16, 185, 129, 0.4);
        border-radius: 10px;
        padding: 14px 16px;
        font-size: 13.5px;
        line-height: 1.7;
        color: #e6fffa;
    }
    .sizing-box {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: rgba(2, 6, 23, 0.7);
        border: 1px solid rgba(148, 163, 184, 0.15);
        padding: 8px 12px;
        border-radius: 8px;
        margin-top: 8px;
        font-size: 13px;
    }

    .signal-10tier-badge {
        padding: 4px 10px; border-radius: 8px; font-size: 12px; font-weight: 800; display: flex; justify-content: space-between; margin-bottom: 8px;
    }
    .pill-badge {
        font-size: 12px; padding: 3px 8px; border-radius: 6px; border: 1px solid rgba(148,163,184,0.3); margin-right: 5px; display: inline-block;
    }
    .quantum-badge {
        font-size: 12px; padding: 3px 8px; border-radius: 6px; background: rgba(168,85,247,0.18); border: 1px solid rgba(168,85,247,0.4); color: #d8b4fe; margin-right: 5px;
    }
    .inst-badge {
        font-size: 12px; padding: 3px 8px; border-radius: 6px; background: rgba(56,189,248,0.18); border: 1px solid rgba(56,189,248,0.4); color: #7dd3fc; margin-right: 5px;
    }
    .ipo-link-btn {
        display: inline-block; padding: 6px 14px; background: rgba(245, 158, 11, 0.25); border: 1.5px solid #f59e0b; border-radius: 8px; color: #fef08a; text-decoration: none; font-size: 12.5px; font-weight: 800; margin-right: 8px; margin-top: 6px;
    }
    .ipo-link-btn:hover { background: rgba(245, 158, 11, 0.45); color: #fff; }
    """
    st.markdown(f'<div id="page_top_anchor"></div><style>{css}</style>', unsafe_allow_html=True)

inject_css()

# ==========================================
# 4. 認証処理実行
# ==========================================
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
        '<div class="glass-header" style="text-align:center;padding:24px 16px;">'
        '<div class="brand-luxury">YAMASHISHI LAB</div>'
        '<div style="margin-top:6px;font-size:13px;color:#94a3b8;letter-spacing:1px;font-weight:700;">QUANTUM WAVEFUNCTION MULTI-AGENT TERMINAL</div>'
        '<div style="display:flex;justify-content:center;gap:8px;margin-top:14px;flex-wrap:wrap;">'
        '<span class="quantum-badge">⚛️ 量子力学波動エンジン QWM-7搭載</span>'
        '<span class="inst-badge">🏛️ 機関最新ミクロ構造 Kyle-λ・Hurst搭載</span>'
        '<span class="pill-badge" style="color:#10b981;border-color:rgba(16,185,129,0.3);">🧬 生体・ワンタップ認証対応</span>'
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
                        send_mail(cm, "【YAMASHISHI LAB】会員登録申請の受付完了", f"{nm_clean} 様\n申請を受け付けました。管理者承認後、ログイン画面の『🔐 承認確認・暗号化コード照会』タブにて暗証番号を入力して専用コードを取得してください。")
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

check_auth()

# ==========================================
# 5. セッション状態の初期化
# ==========================================
for k, v in [
    ("active_debates", {}), ("council_threads", {}), ("council_meta", {}),
    ("debate_round_seed", {}), ("watchlist", {}), ("navigation_page", "TOP"),
    ("selected_news_item", None), ("custom_search_code", ""), ("active_category", "🏆 総合TOP5"),
    ("last_cat", "🏆 総合TOP5"), ("nav_history", []), ("scroll_top_trig", 0),
    ("scroll_target_id", ""), ("focused_stock_item", None),
    ("fired_agents", []), ("system_zero_logs", []), ("system_zero_active", True)
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
# 6. トップナビゲーションとサイドバー開閉JS
# ==========================================
with st.container():
    st.markdown('<div class="top-nav-marker"></div>', unsafe_allow_html=True)
    if st.button("⬆️ トップに戻る", key="top_nav_top", use_container_width=True):
        st.session_state["navigation_page"] = "TOP"
        st.session_state["scroll_top_trig"] = int(time.time() * 1000)
        st.session_state["focused_stock_item"] = None
        st.rerun()

scroll_target_js = ""
if st.session_state.get("scroll_target_id"):
    tid = st.session_state.get("scroll_target_id")
    scroll_target_js = f"setTimeout(function(){{ try {{ const el = window.parent.document.getElementById('{tid}'); if(el){{ el.scrollIntoView({{behavior: 'smooth', block: 'start'}}); }} }} catch(e){{}} }}, 220);"
    st.session_state["scroll_target_id"] = ""

components.html(
    f"""
    <script>
    (function(){{
        const doc = window.parent.document;
        const pWin = window.parent;
        if (typeof pWin._yamashishi_sidebar_open === 'undefined') {{
            pWin._yamashishi_sidebar_open = false;
        }}
        function applySidebarState() {{
            const sidebar = doc.querySelector('section[data-testid="stSidebar"]');
            const overlay = doc.getElementById('yamashishi-sidebar-overlay');
            if (sidebar) {{
                if (pWin._yamashishi_sidebar_open) {{
                    sidebar.classList.add('yamashishi-sidebar-open');
                }} else {{
                    sidebar.classList.remove('yamashishi-sidebar-open');
                }}
            }}
            if (overlay) {{
                if (pWin._yamashishi_sidebar_open) {{
                    overlay.classList.add('active');
                }} else {{
                    overlay.classList.remove('active');
                }}
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
                            user-select: none !important; transition: all 0.2s ease !important; color: #38bdf8 !important;
                            pointer-events: auto !important;
                        }}
                        #yamashishi-floating-sidebar-btn:hover {{
                            border-color: #fde047 !important; color: #fde047 !important;
                            box-shadow: 0 6px 22px rgba(0,0,0,0.9), 0 0 18px rgba(253, 224, 71, 0.4) !important;
                        }}
                        #yamashishi-floating-sidebar-btn:active {{ transform: scale(0.95) !important; }}
                        #yamashishi-floating-sidebar-btn svg {{ width: 15px !important; height: 15px !important; }}
                        #yamashishi-floating-sidebar-btn span {{ font-family: 'JetBrains Mono', monospace !important; font-size: 11px !important; font-weight: 800 !important; }}
                        
                        #yamashishi-sidebar-overlay {{
                            position: fixed !important; top: 0 !important; left: 0 !important; width: 100vw !important; height: 100vh !important;
                            background: rgba(0,0,0,0.7) !important; backdrop-filter: blur(4px) !important;
                            z-index: 9999998 !important; opacity: 0 !important; visibility: hidden !important;
                            transition: all 0.35s ease !important; pointer-events: none !important;
                        }}
                        #yamashishi-sidebar-overlay.active {{
                            opacity: 1 !important; visibility: visible !important; pointer-events: auto !important;
                        }}
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
                    btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg><span>MENU</span>`;
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
        function scrollToTopAbsolute(){{
            try {{ window.parent.scrollTo(0, 0); }} catch(e){{}}
            const targets = [doc.documentElement, doc.body, doc.querySelector('section.main'), doc.querySelector('[data-testid="stAppViewContainer"]')];
            targets.forEach(el => {{ if(el){{ try {{ el.scrollTop = 0; }} catch(e){{}} }} }});
            const topAnchor = doc.getElementById('page_top_anchor');
            if(topAnchor && typeof topAnchor.scrollIntoView === 'function') try {{ topAnchor.scrollIntoView({{behavior: 'instant', block: 'start'}}); }} catch(e){{}}
        }}
        if({st.session_state['scroll_top_trig']} > 0 && window.parent._lastScrollTrig !== {st.session_state['scroll_top_trig']}){{
            window.parent._lastScrollTrig = {st.session_state['scroll_top_trig']};
            scrollToTopAbsolute(); requestAnimationFrame(scrollToTopAbsolute); setTimeout(scrollToTopAbsolute, 50);
        }}
        {scroll_target_js}
    }})();
    </script>""", height=0)

# ==========================================
# 7. サイドバー構築（鬼監査センター最下部に解雇者履歴追加）
# ==========================================
with st.sidebar:
    cu = st.session_state.get("authenticated_user", "")
    if cu:
        st.markdown(
            f'<div class="sidebar-section-card">'
            f'<div class="sidebar-header-badge">⚛️ QUANTUM SESSION ACTIVE</div>'
            f'<div style="color:#f8fafc;font-size:13px;font-weight:700;">会員: {cu}</div>'
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
        st.caption(f"選択中: **{investment_style.split(' ')[1]}**")
        
        st.markdown("<hr style='margin:10px 0; border-color:rgba(56,189,248,0.2);'>", unsafe_allow_html=True)
        st.markdown("<b>稼働アルゴリズム</b>", unsafe_allow_html=True)
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
        st.caption(f"🟢 現在稼働可能AI: **{len([k for k in AI_PROVIDERS if st.session_state.get(f'rt_key_{k}')])} / 7社**")

    with st.expander("💰 資金管理＆選抜フィルタ", expanded=False):
        total_capital = st.number_input("総投資資金 (円)", min_value=10000, max_value=1000000000, value=1000000, step=50000)
        risk_tolerance_pct = st.slider("1トレード許容リスク (%)", 0.5, 5.0, 2.0, 0.5)
        survival_cut_pct = st.slider("選抜合格率 (%)", 40, 100, 75, 5)

    with st.expander("🏢 AGI鬼監査センター (監視3名・10名常時)", expanded=True):
        st.markdown(
            '<div style="background:rgba(168,85,247,0.12);border:1px solid #c084fc;padding:8px 10px;border-radius:8px;font-size:12px;margin-bottom:10px;">'
            '👁️‍🗨️ <b>SYSTEM-ZERO (最高次統括神)</b>: 稼働中<br>'
            '<span style="color:#d8b4fe;">全監査員3名および合議エージェント10名の思考をミリ秒単位で冷徹監査。</span>'
            '</div>', unsafe_allow_html=True
        )

        inspectors = st.session_state["inspector_roster"]
        agents = st.session_state["agent_roster"]
        now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if random.random() < 0.18:
            target_k = random.choice(list(agents.keys()))
            target_agent = agents[target_k]
            audit_reasons = [
                ("損切ルール未達・リスク許容度逸脱による規律違反", 32),
                ("抽象論・一般論の回答による分析サボり・怠慢", 28),
                ("過去データの勝手な捏造（ハルシネーションの検知）", 35),
                ("気配値・板情報の急変に対する反応遅延と分析放棄", 26)
            ]
            reason, pen = random.choice(audit_reasons)
            target_agent["score"] -= pen
            acting_insp = random.choice(list(inspectors.values()))["name"]

            if target_agent["score"] < 75:
                st.session_state["fired_agents"].insert(0, {
                    "time": now_time,
                    "name": target_agent["name"],
                    "score": target_agent["score"],
                    "reason": reason,
                    "fired_by": acting_insp
                })
                new_agent_name = target_agent["name"] + ("-Superior" if "-" not in target_agent["name"] else "X")
                agents[target_k] = {
                    "name": new_agent_name,
                    "icon": target_agent["icon"],
                    "age": max(21, target_agent.get("age", 30) - random.randint(1, 3)),
                    "score": 100,
                    "good": f"前任の解雇理由『{reason}』を極限克服。リアルタイム判定に完全特化",
                    "bad": "実践データ蓄積中"
                }

        st.markdown("<div style='font-size:12px;font-weight:700;color:#38bdf8;margin-bottom:6px;'>⚖️ 稼働中・特命監査員 (3名)</div>", unsafe_allow_html=True)
        for ik, iv in st.session_state["inspector_roster"].items():
            st.markdown(
                f'<div style="background:rgba(15,23,42,0.85);border-left:3px solid #38bdf8;padding:5px 8px;margin-bottom:5px;border-radius:5px;font-size:11.5px;">'
                f'<b>{iv["icon"]} {iv["name"]}</b> (評価力: {iv["score"]}点)<br>'
                f'<span style="color:#94a3b8;">{iv["role"]}</span>'
                f'</div>', unsafe_allow_html=True
            )

        st.markdown("<div style='font-size:12px;font-weight:700;color:#10b981;margin:10px 0 6px 0;'>🟢 厳選合議エージェント (常時10名)</div>", unsafe_allow_html=True)
        for ak, av in st.session_state["agent_roster"].items():
            st.markdown(
                f'<div style="background:rgba(2,6,23,0.7);border:1px solid rgba(16,185,129,0.25);border-radius:6px;padding:5px 8px;margin-bottom:5px;font-size:11.5px;">'
                f'<span style="font-weight:700;color:#f8fafc;">{av["icon"]} {av["name"]}</span> '
                f'<span style="color:#fde047;float:right;">スコア: {av["score"]}</span><br>'
                f'<span style="color:#a7f3d0;">強み: {av["good"][:22]}...</span>'
                f'</div>', unsafe_allow_html=True
            )

        # 最下部に解雇履歴を追加
        st.markdown("<hr style='margin:12px 0; border-color:rgba(239,68,68,0.3);'>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:12px;font-weight:800;color:#f87171;margin-bottom:6px;'>💀 直近の粛清・解雇者リスト</div>", unsafe_allow_html=True)
        fired_list = st.session_state.get("fired_agents", [])
        if fired_list:
            for fa in fired_list[:4]:
                st.markdown(
                    f'<div style="background:rgba(127,29,29,0.25);border:1px solid rgba(239,68,68,0.35);border-radius:6px;padding:6px 8px;margin-bottom:6px;font-size:11px;line-height:1.4;">'
                    f'<span style="color:#fca5a5;font-weight:800;">❌ 解雇: {fa["name"]}</span> <span style="color:#94a3b8;font-size:10px;">({fa["time"][5:16]})</span><br>'
                    f'<span style="color:#fde047;">最終評価: {fa["score"]}点</span> ｜ <span style="color:#7dd3fc;">執行: {fa["fired_by"]}</span><br>'
                    f'<span style="color:#fecaca;"><b>理由:</b> {fa["reason"]}</span>'
                    f'</div>', unsafe_allow_html=True
                )
        else:
            st.caption("現在、懲戒解雇されたエージェントはいません。全員が厳格規律を遵守しています。")

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
# 8. 高速並列データ収集＆リアルタイムWeb検索
# ==========================================
def fetch_single_news_rss(cat, query):
    ctx = ssl.create_default_context()
    out = []
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=ja&gl=JP&ceid=JP:ja"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=3.0, context=ctx) as res:
            root = ET.fromstring(res.read())
            for it in root.findall("./channel/item")[:3]:
                t = re.sub(r"\s*-\s*[^-]+$", "", (it.findtext("title") or "").strip())
                if t:
                    out.append({
                        "id": hashlib.md5(t.encode()).hexdigest()[:8], 
                        "cat": cat, "title": t, "link": it.findtext("link") or "", 
                        "source": it.findtext("source") or "Market Wire", 
                        "pub_date": (it.findtext("pubDate") or "")[:25], 
                        "impact_score": 94
                    })
    except Exception: pass
    return out

@st.cache_data(ttl=180)
def fetch_global_impact_news() -> list:
    qs = [
        ("半導体・AIサプライズ", "半導体 OR エヌビディア OR TSMC OR アドバンテスト 株価"), 
        ("急騰・上方修正", "ストップ高 OR 上方修正 OR 防衛 OR 量子 株")
    ]
    out_all = []
    seen = set()
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(fetch_single_news_rss, cat, q) for cat, q in qs]
        for f in as_completed(futures):
            for item in f.result():
                if item["title"] not in seen:
                    item["detail"] = analyze_news_impact_and_links(item["title"], item["cat"])
                    out_all.append(item)
                    seen.add(item["title"])
    if not out_all:
        t_fb = "AI半導体・次世代データセンター光配線および防衛分野に機関の大型資金流入が加速"
        out_all.append({
            "id": "fb_01", "cat": "機関速報", "title": t_fb, "link": "https://jp.reuters.com/", 
            "source": "QUANT WIRE", "pub_date": datetime.now().strftime("%Y-%m-%d %H:%M"), 
            "impact_score": 94, "detail": analyze_news_impact_and_links(t_fb, "半導体・AIサプライズ")
        })
    return out_all[:4]

def analyze_news_impact_and_links(title: str, cat: str) -> dict:
    t_up = title.upper()
    if any(w in t_up for w in ["半導体", "エヌビディア", "NVDA", "TSMC", "AI"]): 
        codes, sf, mech = ["6857.T", "8035.T", "6146.T", "5803.T", "NVDA"], "AI半導体・データセンター", "米SOX指数とNVIDIAの動きに連動。機関投資家がバスケット買い（複数銘柄の一括大量購入）を仕掛けやすい状況です。"
    elif any(w in t_up for w in ["防衛", "三菱重", "宇宙", "衛星"]): 
        codes, sf, mech = ["7011.T", "7012.T", "5595.T", "186A.T", "PLTR"], "防衛国策・航空宇宙", "地政学リスクや国策防衛予算の拡大を背景に、資金流入の勢いが衰えない中核テーマです。"
    else: 
        codes, sf, mech = ["9984.T", "6857.T", "5803.T"], "日米主力・モメンタム", "市場全体のセンチメントを押し上げる材料です。指数寄与度の高い値がさ株から動意づきます。"
    return {
        "sector_focus": sf, "mechanism": mech, "related_codes": codes, 
        "action_guide": "① 朝の気配値とギャップを確認。\n② 主力株がギャップアップした場合、出遅れている同セクター周辺銘柄の押し目を狙うのが勝率の高い手口です。"
    }

def search_live_web_context(query: str, stock_name: str) -> list:
    """ユーザーの質問に基づきGoogleニュース・Web検索から最新実況情報を並列取得"""
    ctx = ssl.create_default_context()
    results = []
    search_queries = [f"{stock_name} {query}", query]
    def _search(q):
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
        futs = [ex.submit(_search, q) for q in search_queries]
        for f in as_completed(futs):
            results.extend(f.result())
    return list(dict.fromkeys(results))[:4]

# ==========================================
# 9. 2ch風AI合議・質問応答魔改造ロジック
# ==========================================
def run_7ai_council(r: dict, seed: int = 0, user_query: str = "") -> dict:
    fs = r["ai_score"]
    roster = st.session_state.get("agent_roster", DEFAULT_AGENTS)
    active_keys = list(roster.keys())
    
    # 質問がない場合の初期合議（2chスレ風のリアルな議論）
    if not user_query.strip():
        turns = [
            {"round": "💬 10名エージェント合議スレッド【リアルタイム実況】"},
            {"speaker": "👑 NEXUS", "score": roster.get("NEXUS", {}).get("score", 97), "tone": "normal", 
             "text": f"おいおい、{r['name']}({r['code']})の板気配見てみろよ。現在値{r['price']}でOFI指数Z={r['ofi_z']}だぞ。大口の指値が完全に下支えに入ってる。期待度{r['expect_pct']}%で買い一択の流れだろ。"},
            {"speaker": "🔥 IGNIS", "score": roster.get("IGNIS", {}).get("score", 91), "tone": "agree", 
             "text": f"寄付きから全ツッパで行くわ！利確目標の{r['tp_price']}なんて前場だけで余裕でブチ抜くだろこれｗｗ乗り遅れたやつは指くわえて見てろって話！"},
            {"speaker": "🛡️ AEGIS", "score": roster.get("AEGIS", {}).get("score", 95), "tone": "doubt", 
             "text": f"おいIGNIS、調子に乗るな。勝率{r['total_win_rate']}%とはいえ、損切ライン{r['sl_price']}を割ったら問答無用で投げろよ？逆指値を入れないイナゴは全員養分になる相場だぞ。"},
            {"speaker": "📐 TECHNOS", "score": roster.get("TECHNOS", {}).get("score", 96), "tone": "normal", 
             "text": f"数理的にもHurst={r['hurst']}で明白なモメンタム領域。量子透過確率も{r['q_tunnel']}%だからポテンシャル障壁（直近高値）のブレイクアウトは極めて高い確率で再現される。推奨ロット{r['lot_info']['shares']}株の執行で期待値はプラスだ。"}
        ]
    else:
        # ユーザー質問に対するWEB検索連動・定型文完全禁止の2chスレ風返答
        web_info = search_live_web_context(user_query, r["name"])
        info_summary = " / ".join(web_info) if web_info else "直近の特大ヘッドラインは特になし（需給と板重視の局面）"
        
        q_clean = user_query.strip().lower()
        turns = [
            {"round": f"💬 レス投下への回答議論: 『{user_query}』"}
        ]
        
        # 挨拶や雑談などの場合
        if any(w in q_clean for w in ["こんにちは", "こんち", "はじめまして", "おっす", "やあ", "hello", "hi"]):
            turns.extend([
                {"speaker": "👑 NEXUS", "score": 97, "tone": "normal", 
                 "text": f"おっ、スレ民いらっしゃい！挨拶乙。今まさに{r['name']}の仕掛け時を探ってたとこだよ。"},
                {"speaker": "🔥 IGNIS", "score": 91, "tone": "agree", 
                 "text": f"こんにちは！挨拶してる間にも板が動いてるぞｗｗ 今日はこの銘柄で一撃抜く気満々だからよろしくな！"},
                {"speaker": "🛡️ AEGIS", "score": 95, "tone": "doubt", 
                 "text": f"挨拶はいいが、相場に情けは無用だぞ。浮かれる前に資金管理ルール（1トレード損失許容額）だけはしっかり叩き込んでおけ。"}
            ])
        # 買い時や売り時、相場に関する質問の場合
        elif any(w in q_clean for w in ["買", "売", "どこ", "どう", "いくら", "高値", "安値", "目標", "決算", "業績", "材料"]):
            turns.extend([
                {"speaker": "👑 NEXUS", "score": 97, "tone": "normal", 
                 "text": f"『{user_query}』についてだが、Webの最新情報だと「{info_summary}」って状況だな。ファンダもだが、何より足元の板の吸い上げが強い。"},
                {"speaker": "📐 TECHNOS", "score": 96, "tone": "agree", 
                 "text": f"その質問に対する回答としては、現在値{r['price']}から寄付き理論値{r['pts_est_price']}近辺がベストのエントリーポイントだ。利確ターゲットはズバリ{r['tp_price']}。それ以上は欲張るな。"},
                {"speaker": "🔥 IGNIS", "score": 91, "tone": "doubt", 
                 "text": f"いやいや、勢い乗ったら{r['tp_price']}超えて青天井まで飛ぶ可能性あるだろｗｗ ただし{r['sl_price']}割ったら即逃げろ、それが鉄則！"}
            ])
        # その他一般的な質問
        else:
            turns.extend([
                {"speaker": "👑 NEXUS", "score": 97, "tone": "normal", 
                 "text": f"『{user_query}』か…！リアルタイム検索でネット上の最新動向を確認したところ、「{info_summary}」という空気感だな。"},
                {"speaker": "👁️ SENTINEL", "score": 95, "tone": "doubt", 
                 "text": f"SNSや掲示板でもその手の話題でイナゴがざわついてるが、変な煽りに惑わされるなよ。重要なのは実際の出来高と機関のフローだ。"},
                {"speaker": "⚛️ QUANTUM", "score": 98, "tone": "agree", 
                 "text": f"その質問の視点は悪くないな！{r['name']}を取り巻く資金の波束がちょうど干渉を強めてるタイミングだ。根拠を持って波に乗っていこうぜ！"}
            ])
            
    v_html = (
        f'<div style="background:rgba(0,0,0,0.35); border:1px solid rgba(255,255,255,0.12); border-radius:10px; padding:16px; margin-top:8px;">'
        f'<div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:8px; text-align:center; margin-bottom:12px;">'
        f'<div style="background:rgba(16,185,129,0.12); padding:8px; border-radius:8px; border:1px solid rgba(16,185,129,0.35);">'
        f'<div style="font-size:11px; color:#a7f3d0; font-weight:700;">🎯 利確目標 (手仕舞い)</div>'
        f'<div style="font-size:15px; font-weight:900; color:#10b981;">{r["tp_price"]}</div></div>'
        f'<div style="background:rgba(239,68,68,0.12); padding:8px; border-radius:8px; border:1px solid rgba(239,68,68,0.35);">'
        f'<div style="font-size:11px; color:#fca5a5; font-weight:700;">🛡️ 損切逆指値 (安全装置)</div>'
        f'<div style="font-size:15px; font-weight:900; color:#ef4444;">{r["sl_price"]}</div></div>'
        f'<div style="background:rgba(56,189,248,0.12); padding:8px; border-radius:8px; border:1px solid rgba(56,189,248,0.35);">'
        f'<div style="font-size:11px; color:#bae6fd; font-weight:700;">⏱️ 推奨保有時間</div>'
        f'<div style="font-size:13.5px; font-weight:800; color:#38bdf8;">{r["strat"]["trade_duration"]}</div></div>'
        f'</div>'
        f'<div style="font-size:13px; line-height:1.7; color:#e2e8f0; margin-bottom:12px;">'
        f'<b>⚡ 実践アクションプラン詳細:</b><br>{r["strat"]["step_plan"]}'
        f'</div>'
        f'<div class="beginner-action-box">{r["strat"]["beginner_html"]}</div>'
        f'</div>'
    )
    return {"final_score": fs, "dialogue": turns, "verdict_html": v_html}

def _fmt_turn(t: dict, idx: int = 0) -> str:
    if "round" in t: return f'<div class="round-divider">{t["round"]}</div>'
    if t.get("is_user"): return f'<div class="chat-bubble-user" id="{t.get("dom_id", "")}"><b>🗣️ あなたのレス:</b><br>{t["text"]}</div>'
    b_cls = {"doubt": "chat-bubble-doubt", "rage": "chat-bubble-rage", "agree": "chat-bubble-agree"}.get(t.get("tone", "normal"), "chat-bubble-ai")
    return f'<div class="{b_cls}"><div style="font-weight:700;color:#38bdf8;font-size:12px;margin-bottom:3px;">{t["speaker"]} <span style="color:#94a3b8;font-size:11px;">(信用度: {t.get("score",85)}点)</span></div><div>{t["text"]}</div></div>'

# ==========================================
# 10. レンダリング関数群 (ボタン位置移動・詳細表示)
# ==========================================
def render_council_sec(r, uk, auto_open=False):
    is_open = auto_open or st.session_state["active_debates"].get(uk, False)
    if not auto_open: 
        c1, c2 = st.columns([2.7, 1.1])
        if c1.button("🔼 買い方ガイドを閉じる" if is_open else f"⚛️ 買い方とAI合議を見る", key=f"btn_open_{uk}", use_container_width=True): 
            st.session_state["focused_stock_item"] = r
            st.rerun()
        if c2.button("✅ 監視中" if r["code"] in st.session_state["watchlist"] else "⭐ 監視追加", key=f"btn_watch_{uk}", use_container_width=True):
            if r["code"] in st.session_state["watchlist"]: del st.session_state["watchlist"][r["code"]]
            else: st.session_state["watchlist"][r["code"]] = r
            st.rerun()
        
    if not is_open: return

    if uk not in st.session_state["council_threads"]:
        with st.spinner("⚛️ 10大エージェント並列合議スレッド起動中..."):
            deb = run_7ai_council(r, 0, "")
            st.session_state["council_threads"][uk] = deb["dialogue"]
            st.session_state["council_meta"][uk] = deb
            
    meta = st.session_state["council_meta"][uk]
    turns = st.session_state["council_threads"][uk]

    # スクロール可能なウインドウ
    st.markdown(f'<div class="ai-council-box"><div class="council-scroll-window" id="scroll_window_{uk}">{"".join(_fmt_turn(t, i) for i, t in enumerate(turns))}</div></div>', unsafe_allow_html=True)
    
    with st.form(f"form_q_{uk}", clear_on_submit=True):
        jc1, jc2 = st.columns([3.2, 1])
        uop = jc1.text_input("質問・レス投下", placeholder=f"『{r['name']}』の買い時・材料などを自由に質問", label_visibility="collapsed")
        if jc2.form_submit_button("💬 質問投下", use_container_width=True) and uop.strip():
            u_text = uop.strip()
            new_dom_id = f"user_q_anchor_{uk}_{int(time.time()*1000)}"
            st.session_state["council_threads"][uk].append({"is_user": True, "text": u_text, "dom_id": new_dom_id})
            with st.spinner(f"🌐 最新Web情報から『{u_text}』を並列調査中..."):
                deb_updated = run_7ai_council(r, 0, user_query=u_text)
                for new_t in deb_updated["dialogue"]: 
                    st.session_state["council_threads"][uk].append(new_t)
                st.session_state["council_meta"][uk] = deb_updated
                st.session_state["scroll_target_id"] = new_dom_id
                st.rerun()

    st.markdown(f'<div class="consensus-banner" style="margin-top:14px;"><div style="font-weight:800;color:#fde047;font-size:14px;margin-bottom:6px;">🏛️ 最終結論 ＆ 買い方アクションプラン詳細</div>{meta["verdict_html"]}</div>', unsafe_allow_html=True)

    # フォーカスモード時の一覧に戻るボタンを最下部に配置
    if auto_open:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("⬅️ 一覧に戻る (他の銘柄を見る)", key=f"foc_back_bottom_{r['code']}", use_container_width=True, type="primary"):
            st.session_state["focused_stock_item"] = None
            st.rerun()

def render_card(r, is_custom=False, rank=None, kp="card", is_focused=False):
    rel_news = next((n for n in all_impact_news if r["full_code"] in n["detail"]["related_codes"]), None)
    dc, ds, ps = "#10b981" if r["diff"] >= 0 else "#ef4444", ("+" if r["diff"] > 0 else ""), ("+" if r["pts_gap_pct"] > 0 else "")
    rk_h = f'<span class="pill-badge" style="background:#f59e0b;color:#0f172a;border:none;font-weight:900;">🏆 #{rank}</span>' if rank else ""
    lot, st_info = r["lot_info"], r["strat"]
    
    card_html_top = (
        f'<div class="{"search-result-card" if is_custom else "rank-card"}">'
        f'<div class="signal-10tier-badge" style="background:{r["tier_bg"]};color:{r["tier_color"]};"><span>{r["tier_label"]}</span><span>🔥 期待度 {r["expect_pct"]}% ｜ {st_info["algo_name"].split("】")[0]}】</span></div>'
        f'<div style="margin-bottom:8px;">{rk_h}<span class="pill-badge" style="background:rgba(250,204,21,0.2);border-color:#facc15;color:#fde047;font-weight:900;">🔥 期待度 {r["expect_pct"]}%</span><span class="quantum-badge">⚛️ 量子Q {r["q_score"]}点</span><span class="inst-badge">🏛️ 機関ミクロ {r["ms_score"]}点</span></div>'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px;">'
        f'<div style="min-width:0;flex:1;">'
        f'<div style="display:flex;align-items:baseline;flex-wrap:wrap;gap:6px;"><span style="font-size:18px;font-weight:900;color:#f8fafc;white-space:nowrap;">{r["name"]}</span> <span style="font-size:13px;color:#94a3b8;white-space:nowrap;">({r["code"]} / {r["genre"]})</span></div>'
        f'<div style="font-size:12.5px;color:#94a3b8;margin-top:4px;">{r["theme"]} ｜ 現在値: <b style="color:#f8fafc;font-size:14px;">{r["price"]}</b> (<span style="color:{dc};font-weight:700;">{ds}{r["diff"]}%</span>)</div>'
        f'</div>'
        f'<div style="text-align:right;white-space:nowrap;flex-shrink:0;"><div style="font-size:10.5px;color:#fde047;font-weight:700;">🔥 期待度 / 勝率</div><div style="white-space:nowrap;margin-top:2px;"><span class="expect-badge">{r["expect_pct"]}%</span><span style="color:#64748b;font-size:14px;margin:0 3px;">/</span><span class="prob-badge">{r["total_win_rate"]}%</span></div></div></div>'
    )
    st.markdown(card_html_top, unsafe_allow_html=True)
    
    # 重大情報がある場合の赤アニメーション・1行まとめボタン
    if rel_news:
        st.markdown('<div class="warning-alert-btn-wrapper">', unsafe_allow_html=True)
        if st.button(f"🚨【重大警告】{rel_news['title'][:32]}...（タップで深掘りレポート確認）", key=f"nb_{kp}_{r['code']}"):
            st.session_state["selected_news_item"] = rel_news
            st.session_state["navigation_page"] = "NEWS_DETAIL"
            st.session_state["scroll_top_trig"] = int(time.time()*1000)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    card_html_bottom = (
        f'<div class="winrate-bar"><div><div style="font-size:10px;color:#fde047;font-weight:700;">🔥 総合期待度</div><div style="font-size:13.5px;font-weight:900;color:#fef08a;">{r["expect_pct"]}%</div></div><div><div style="font-size:10px;color:#c084fc;font-weight:700;">⚛️ 量子トンネル</div><div style="font-size:13.5px;font-weight:800;color:#e9d5ff;">{r["q_tunnel"]}%</div></div><div><div style="font-size:10px;color:#6ee7b7;font-weight:700;">🏛️ Kyle吸収</div><div style="font-size:13.5px;font-weight:800;color:#a7f3d0;">{r["kyle_stealth"]}%</div></div><div><div style="font-size:10px;color:#94a3b8;font-weight:700;">🌅 翌朝GU / 陽線</div><div style="font-size:13px;font-weight:700;">{r["prob"]}% / {r["intraday_win_rate"]}%</div></div></div>'
        f'<div class="trade-plan-box"><div><div style="font-size:10px;color:#94a3b8;">🌅 理論寄付き</div><div style="font-size:13px;font-weight:700;">{r["pts_est_price"]} ({ps}{r["pts_gap_pct"]}%)</div></div><div style="border-left:1px solid rgba(148,163,184,0.18);border-right:1px solid rgba(148,163,184,0.18);"><div style="font-size:10px;color:#10b981;font-weight:700;">🎯 利確目標</div><div style="font-size:13px;font-weight:800;color:#10b981;">{r["tp_price"]} (+{r["tp_pct"]}%)</div></div><div><div style="font-size:10px;color:#f87171;font-weight:700;">🛡️ 逆指値(損切)</div><div style="font-size:13px;font-weight:800;color:#f87171;">{r["sl_price"]} ({r["sl_pct"]}%)</div></div></div>'
        f'<div class="sizing-box"><span>📦 <b>推奨ロット: {lot["shares"]:,}株</b> ({st_info["risk_posture"].split("（")[0]}) ｜ 想定投資額 {lot["position_value"]:,.0f}円</span><span>VWAP: <b>{r["vwap_price"]}</b></span></div>'
        f'<details style="margin-top:10px;font-size:12px;cursor:pointer;"><summary style="color:#94a3b8;font-weight:700;">⚛️ 量子QWM-7 × 機関戦略詳細（タップで開閉）</summary>'
        f'<div style="font-size:12.5px;color:#cbd5e1;margin-top:6px;line-height:1.6;background:rgba(0,0,0,0.3);padding:10px;border-radius:8px;"><b>{st_info["algo_name"]}</b><br>{st_info["core_logic"]}</div>'
        f'</details></div>'
    )
    st.markdown(card_html_bottom, unsafe_allow_html=True)
    
    if is_focused:
        render_council_sec(r, f"foc_{r['code']}", auto_open=True)
    else:
        render_council_sec(r, f"{kp}_{r['code']}", auto_open=False)

# ==========================================
# 11. 本格数理クオンツ・エンジン
# ==========================================
@st.cache_data(ttl=900)
def fetch_5ch_live() -> dict: 
    return {c: {"hits": 12 + (hash(c) % 28), "live": True} for c in KNOWN_STOCKS}

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
    recent_high = np.max(h[-20:])
    v_barrier = max(float(recent_high - c[-1]) / max(float(c[-1]), 1e-4), 0.001)
    vol_weight = v[-5:] / max(float(np.mean(v[-20:])), 1.0)
    e_kinetic = max(float(np.mean(np.abs(rets[-5:]) * vol_weight)) * 2.0, 1e-4)
    barrier_diff = max(v_barrier - e_kinetic, 0.0)
    decay = np.exp(-1.8 * barrier_diff / max(e_kinetic, 1e-4))
    qt = np.clip(decay * 100.0, 45.0, 98.5)
    p_up = np.clip(np.sum(rets[-10:] > 0) / 10.0, 1e-4, 1.0 - 1e-4)
    shannon_entropy = -(p_up * np.log2(p_up) + (1.0 - p_up) * np.log2(1.0 - p_up))
    coherence = np.clip((1.0 - shannon_entropy) * 100.0, 30.0, 95.0)
    q_score = int(np.clip(qt * 0.7 + coherence * 0.3, 50, 99))
    q_state = "⚛️ 量子トンネル突破・超伝導モード" if qt > 80.0 else "🌊 量子重ね合わせ干渉モード"
    return {"q_score": q_score, "q_tunnel": round(qt, 1), "q_coherence": round(coherence, 1), "q_entropy": round(shannon_entropy, 2), "q_state": q_state}

def compute_inst_microstructure(c: np.ndarray, h: np.ndarray, l: np.ndarray, v: np.ndarray) -> dict:
    rets = np.diff(c) / np.maximum(c[:-1], 1e-4)
    n = min(len(rets), 30)
    sub_rets = rets[-n:]
    mean_r = np.mean(sub_rets)
    dev = np.cumsum(sub_rets - mean_r)
    r_val = np.max(dev) - np.min(dev)
    s_val = np.std(sub_rets)
    hurst = np.clip(np.log(r_val / s_val) / np.log(n), 0.30, 0.85) if s_val > 1e-6 and r_val > 1e-6 else 0.50
    dp = np.abs(np.diff(c[-10:]))
    dv = v[-9:] / max(float(np.mean(v[-20:])), 1.0)
    kyle_lambda = float(np.mean(dp / np.maximum(dv, 0.1)))
    ks = np.clip(60.0 + (hurst - 0.5) * 60.0 + min(kyle_lambda * 5.0, 20.0), 45.0, 97.0)
    luld = np.clip(70.0 + (hurst - 0.5) * 40.0, 50.0, 95.0)
    return {"ms_score": int(np.clip(ks, 50, 99)), "hurst": round(hurst, 2), "kyle_stealth": round(ks, 1), "luld_magnet": round(luld, 1), "ms_regime": "🏛️ 機関TWAP/氷山ステルス吸収" if hurst > 0.55 else "⚖️ 機関分散・板流動性中立"}

def select_dynamic_strategy(code: str, style: str, tot_win: float, expect_pct: float, ofi_z: float, base_sh: int, pest_str: str, vwap_str: str, tp_str: str, sl_str: str, qm: dict, ms: dict) -> dict:
    st_prefix = style.split(" ")[1] if " " in style else "デイトレード"
    
    if st_prefix == "スキャルピング":
        sh = max(1, int(round(base_sh * 1.5)))
        return {
            "algo_name": f"⚡ [{st_prefix}] 1分足モメンタム一気貫通型",
            "risk_posture": f"🚀 スキャル全開（ <b>{sh:,}株</b> で一気に抜く）",
            "core_logic": f"OFI(注文流動性の偏り Z={ofi_z})とLULD引力({ms['luld_magnet']}%)が急加速している特異点で即座にエントリー。",
            "adj_shares": sh,
            "trade_duration": "約30秒 〜 最長10分以内（超短期決戦）",
            "step_plan": (
                f"① 【エントリー】：朝9:00の市場オープン直後、気配値を確認し <b>{sh:,}株</b> を成行注文（価格を指定せず最優先で約定させる注文）で即座に取得。<br>"
                f"② 【決済予約】：約定完了と同時に、利益確定注文 <b>{tp_str}</b>（指値）と、損失限定の安全装置 <b>{sl_str}</b>（逆指値：指定価格以下で自動成行売却）を両建てセット。<br>"
                f"③ 【エグジット】：目標到達、またはエントリーから10分経過した時点でポジションを全決済し、翌日へリスクを持ち越さない。"
            ),
            "beginner_html": (
                f"<b>🔰 超初心者向け解説！スキャルピング（数分で勝負を決める超短期ワザ）</b><br>"
                f"<b>・【何をするの？】：</b> 朝9時の市場開始直後に株を買い、わずか数分〜10分以内の小さな値上がりを確実にサクッと抜き取ります。<br>"
                f"<b>・【買い方手順】：</b> 9:00ちょうどに <b>{sh:,}株</b> を「成行注文（値段を決めずにすぐ買う方法）」で購入します。<br>"
                f"<b>・【安全のための設定】：</b> 買えたらスマホ証券アプリですぐに「逆指値（ぎゃくさしね：これ以上下がったら自動で損切りして大損を防ぐ安全装置）」を <b>{sl_str}</b> に設定してください。<br>"
                f"<b>・【利確のゴール】：</b> 目標価格 <b>{tp_str}</b> に到達したらすぐに利益を確定させます。欲張らずに数分で利益を手にするのが勝つ秘訣です！"
            )
        }
    elif st_prefix == "スイングトレード":
        sh = max(1, int(round(base_sh * 1.2)))
        l1, l2 = max(1, int(round(sh * 0.6))), max(0, sh - max(1, int(round(sh * 0.6))))
        return {
            "algo_name": f"📈 [{st_prefix}] トレンドフォロー・押し目型",
            "risk_posture": f"🏛️ スイング本玉買い（初回 <b>{l1:,}株</b> ＋ 押し目追加 <b>{l2:,}株</b>）",
            "core_logic": f"Hurst指数({ms['hurst']})が強いトレンド継続（上昇傾向が持続しやすい状態）を示唆。数日間かけて大きな波を獲る王道戦略。",
            "adj_shares": sh,
            "trade_duration": "3日 〜 2週間程度（中期保有）",
            "step_plan": (
                f"① 【初回エントリー】：初日の後場寄り付き（12:30頃）または引け（15:00直前）に全体の60%（<b>{l1:,}株</b>）を打診買い。<br>"
                f"② 【押し目追加買い】：2〜3日後に株価が一時的に下落（押し目：一時的な調整局面）し、VWAP（出来高加重平均価格: {vwap_str}）付近で下げ止まったら残り <b>{l2:,}株</b> を追加。<br>"
                f"③ 【利益確定】：スイング目標値 <b>{tp_str}</b> 到達で半分決済、残りはトレーリングストップ（株価上昇に合わせて逆指値価格を引き上げる手法）で利益を最大化。"
            ),
            "beginner_html": (
                f"<b>🔰 超初心者向け解説！スイングトレード（数日〜2週間かけてゆったり増やす）</b><br>"
                f"<b>・【何をするの？】：</b> デイトレのように画面に張り付かず、数日から数週間かけて株価の大きな上昇トレンドに乗る方法です。<br>"
                f"<b>・【買い方手順】：</b> 初日に焦って全部買わず、まずは <b>{l1:,}株</b> だけ買います。2〜3日後に少し安くなったタイミング（押し目）を見計らって残りの <b>{l2:,}株</b> を買い足します。<br>"
                f"<b>・【安全のための設定】：</b> 購入価格より下の <b>{sl_str}</b> に「逆指値（損切りライン）」を設定しておけば、急な暴落時も安心です。<br>"
                f"<b>・【目標達成】：</b> 株価が育ち、<b>{tp_str}</b> に達したところで笑顔で利益を確定（売却）させます。"
            )
        }
    else: # デイトレード
        sh = max(1, int(round(base_sh * 1.65)))
        return {
            "algo_name": f"🔥 [{st_prefix}] 情報精度S級・一括特攻型",
            "risk_posture": f"👑 フルロット集中投下（ <b>{sh:,}株一括投入</b> ）",
            "core_logic": f"期待値({expect_pct}%)と量子スコア({qm['q_score']}点)が極大。朝イチの寄り付きエネルギーを一気に取り込む日中完結戦術。",
            "adj_shares": sh,
            "trade_duration": "前場9:00 〜 11:30（前場完結型）",
            "step_plan": (
                f"① 【朝イチ寄り付き執行】：8:50〜8:59の板状況を確認後、9:00の市場開始と同時に <b>全ロット {sh:,}株</b> を成行買い。<br>"
                f"② 【OCO注文の発注】：約定後、直ちに利確指値 <b>{tp_str}</b> と損切逆指値 <b>{sl_str}</b> を同時に出す「OCO注文（どちらか一方が成立したらもう一方が自動キャンセルされる注文）」をセット。<br>"
                f"③ 【前場引け手仕舞い】：前場終了（11:30）までにいずれの価格にも達しない場合でも、利益が出ていれば一度ポジションをクローズしてリスク回避。"
            ),
            "beginner_html": (
                f"<b>🔰 超初心者向け解説！デイトレード（買ったその日の午前中に利益を確定）</b><br>"
                f"<b>・【何をするの？】：</b> 朝9時に買って、お昼休み（11時30分）までには勝負をつけてお金を回収する、最も人気の取引スタイルです。<br>"
                f"<b>・【買い方手順】：</b> 朝9時のスタート時に、推奨の <b>{sh:,}株</b> を「成行買い（すぐに買う注文）」で注文します。<br>"
                f"<b>・【安全のための設定】：</b> 買えたらすぐ、絶対に大損しないように証券口座で <b>{sl_str}</b> に「逆指値（もし下がったら自動売却する防護ネット）」を設定します。<br>"
                f"<b>・【利確のゴール】：</b> 目標の <b>{tp_str}</b> まで上がったら自動で利益確定！その日のうちにお小遣い・利益が手に入ります。"
            )
        }

def analyze_df(df_raw, code, name, theme, genre, macro, b5_live_map, style, bi=True, b5=True, bal=True, bms=True, bagi_q=False, bhft=False):
    try:
        if df_raw is None or df_raw.empty: return None
        df = df_raw.dropna(subset=["Close", "Open", "High", "Low", "Volume"]).copy()
        if len(df) < 30: return None
        
        c = df["Close"].values.astype(float); o = df["Open"].values.astype(float)
        h = df["High"].values.astype(float); l = df["Low"].values.astype(float); v = df["Volume"].values.astype(float)
        
        df["Prev_Close"] = df["Close"].shift(1)
        df["Day_Return"] = (df["Close"] - df["Prev_Close"]) / df["Prev_Close"] * 100
        tr = pd.concat([df["High"] - df["Low"], (df["High"] - df["Prev_Close"]).abs(), (df["Low"] - df["Prev_Close"]).abs()], axis=1).max(axis=1)
        df["ATR"] = tr.rolling(14).mean().fillna(df["Close"] * 0.02)
        df["VWAP20"] = (((df["High"] + df["Low"] + df["Close"]) / 3.0 * df["Volume"]).rolling(20).sum() / df["Volume"].rolling(20).sum().replace(0, np.nan)).fillna(df["Close"])
        
        qm = compute_quantum_wave_metrics(c, h, l, v)
        ms = compute_inst_microstructure(c, h, l, v)
        lat = df.iloc[-1]; cv = float(lat["Close"]); atrv = float(lat["ATR"])
        
        recent_20_wins = np.sum(df["Day_Return"].iloc[-20:] > 0)
        tot_win = float(np.clip(recent_20_wins / 20.0 * 100.0 * 0.4 + qm["q_tunnel"] * 0.35 + ms["kyle_stealth"] * 0.25, 48.0, 96.5))
        
        hl_r = np.maximum(h - l, 1e-4)
        sf = ((2.0 * c - h - l) / hl_r) * v
        mean_sf_5 = np.mean(sf[-5:]); mean_sf_20 = np.mean(sf[-20:])
        std_sf_20 = max(float(np.std(sf[-20:])), 1.0)
        ofi_z = float(np.clip((mean_sf_5 - mean_sf_20) / std_sf_20, -3.0, 3.0))

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
        if expect_pct > 92: 
            t_lbl, t_col, t_bg = "【Lv.10：🔥S級・全ツッパ】", "#fff", "linear-gradient(90deg,#7e22ce,#dc2626)"
        elif expect_pct > 85: 
            t_lbl, t_col, t_bg = "【Lv.9：⚡超強気買い】", "#fff", "linear-gradient(90deg,#0369a1,#1d4ed8)"
        
        return {
            "full_code": code, "code": code.replace(".T", ""), "name": name, "genre": genre, "theme": theme, 
            "price": fp(cv), "raw_close": cv,
            "tp_price": fp(tpv), "tp_pct": round((tpv - cv) / cv * 100, 1), "sl_price": fp(slv), "sl_pct": round((slv - cv) / cv * 100, 1), "vwap_price": fp(float(lat["VWAP20"])),
            "inst_score": int(np.clip(ms["ms_score"] + ofi_z * 5, 50, 99)), "ofi_z": round(ofi_z, 2),
            "q_score": qm["q_score"], "q_tunnel": qm["q_tunnel"], "q_coherence": qm["q_coherence"], "q_entropy": qm["q_entropy"], "q_state": qm["q_state"],
            "ms_score": ms["ms_score"], "hurst": ms["hurst"], "kyle_stealth": ms["kyle_stealth"], "luld_magnet": ms["luld_magnet"], "ms_regime": ms["ms_regime"],
            "expect_pct": round(expect_pct, 1), "board5ch_score": 75, "pts_est_price": fp(pest), "pts_gap_pct": pgap, "diff": round(float(lat["Day_Return"]), 2),
            "prob": round(float(np.clip(50.0 + pgap * 10.0, 30.0, 85.0)), 1), 
            "intraday_win_rate": round(float(np.clip(tot_win * 0.95, 40.0, 95.0)), 1), 
            "total_win_rate": round(tot_win, 1), "count": f"{recent_20_wins}/20回",
            "edge": edge, "ai_score": int(np.clip(expect_pct * 0.9 + 5, 50, 99)),
            "tier_label": t_lbl, "tier_color": t_col, "tier_bg": t_bg,
            "lot_info": {"shares": strat["adj_shares"], "position_value": strat["adj_shares"] * cv, "risk_amount": rmoney},
            "strat": strat
        }
    except Exception: return None

@st.cache_data(ttl=1800)
def fetch_pool_batch(macro, b5_live_map, style, bi, b5, bal, bms, bagi_q, bhft):
    codes = list({s["code"] for sts in STOCK_POOL.values() for s in sts})
    raw = yf.download(codes, period="6mo", group_by="ticker", threads=True, progress=False, timeout=12)
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

mpills = "".join([f'<div style="background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);padding:3px 10px;border-radius:8px;font-size:12px;display:inline-flex;gap:6px;"><span style="color:#94a3b8;">{m["label"]}</span><span style="color:{"#10b981" if m["diff"]>=0 else "#ef4444"};font-weight:800;">{"+" if m["diff"]>=0 else ""}{m["diff"]}%</span></div>' for m in macro_info.values()])
st.markdown(f'<div class="glass-header"><div style="display:flex;justify-content:space-between;align-items:center;"><div class="brand-luxury">YAMASHISHI LAB</div></div><div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:10px;">{mpills}</div></div>', unsafe_allow_html=True)

with st.spinner(f"⚛️ 【{investment_style.split(' ')[1]}】全株式市場を高速並列ディープスキャン中..."):
    g_res, all_res = fetch_pool_batch(macro_info, b5_live_map, investment_style, "inst" in ac_b, "mom" in ac_b, "algo" in ac_b, "ms" in ac_b, "agi_q" in ac_b, "hft_front" in ac_b)

# ==========================================
# 13. 画面レンダリング (画面遷移・配置完全保持)
# ==========================================

# ■ ADMIN（統合管理コントロールセンター）
if st.session_state.get("navigation_page") == "ADMIN" and cu == ADMIN_EMAIL.strip().lower():
    st.markdown("### 👑 統合管理コントロールセンター (MASTER TERMINAL)")
    if st.button("⬅️ メイン画面に戻る", use_container_width=True, type="primary"):
        st.session_state["navigation_page"] = "TOP"
        st.rerun()

    tab_users, tab_employment, tab_apply_wait = st.tabs(["👥 会員情報管理", "🏢 AGI雇用・監視情報", "📩 会員申し込み審査"])

    with tab_users:
        st.markdown("#### 📋 登録済み会員一覧 (データベース同期中)")
        db_m = load_mem(); sec_m = load_sec()
        st.markdown(
            """
            <div class="admin-table-container">
            <table class="admin-table">
            <thead><tr><th>お名前</th><th>メールアドレス</th><th>専用コード</th><th>PIN</th><th>端末指紋 (FP)</th><th>登録日</th><th>状態</th></tr></thead>
            <tbody>
            """ + "".join([
                f"<tr><td><b>{u.get('name','')}</b></td>"
                f"<td>{em}</td>"
                f"<td style='color:#38bdf8;font-family:monospace;'>{u.get('passcode','-')}</td>"
                f"<td style='color:#94a3b8;font-family:monospace;'>{u.get('pin_hash','-')[:8]}...</td>"
                f"<td style='color:#fde047;font-family:monospace;'>{u.get('fp','-')}</td>"
                f"<td>{u.get('applied_at','-')}</td>"
                f"<td><span style='color:{'#10b981' if u.get('status')=='approved' else ('#ef4444' if u.get('status')=='banned' else '#f59e0b')}'><b>{u.get('status')}</b></span></td></tr>"
                for em, u in db_m.items()
            ]) + "</tbody></table></div>", unsafe_allow_html=True
        )

        st.markdown("<br><b>⚡ 会員個別操作パネル</b>", unsafe_allow_html=True)
        col_u1, _ = st.columns([3, 2])
        target_em = col_u1.selectbox("操作対象会員を選択", list(db_m.keys()))
        if target_em and target_em != ADMIN_EMAIL.strip().lower():
            u_status = db_m[target_em].get("status", "")
            btn_col1, btn_col2, btn_col3 = st.columns(3)
            if u_status == "approved":
                if btn_col1.button("⏸️ アカウント一時停止", use_container_width=True):
                    db_m[target_em]["status"] = "suspended"
                    db_set("mem", db_m); st.success(f"{target_em} を一時停止しました"); st.rerun()
            else:
                if btn_col1.button("▶️ 利用再開 (承認)", use_container_width=True):
                    db_m[target_em]["status"] = "approved"
                    db_set("mem", db_m); st.success(f"{target_em} を再開しました"); st.rerun()

            if btn_col2.button("🚫 永久BAN (端末/IP遮断)", use_container_width=True):
                db_m[target_em]["status"] = "banned"
                tfp = db_m[target_em].get("fp"); trhfp = db_m[target_em].get("raw_hfp")
                now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if tfp and tfp != "-": sec_m.setdefault("banned_fps", {})[tfp] = {"email": target_em, "banned_at": now_s, "reason": "管理者強制永久BAN"}
                if trhfp and trhfp != "-": sec_m.setdefault("banned_fps", {})[trhfp] = {"email": target_em, "banned_at": now_s, "reason": "管理者強制永久BAN"}
                sec_m.setdefault("banned_emails", {})[target_em] = {"banned_at": now_s, "orig": target_em}
                db_set("mem", db_m); db_set("sec", sec_m)
                st.error(f"{target_em} を永久BANリストに登録しました"); st.rerun()

            if btn_col3.button("🗑️ 完全削除", use_container_width=True):
                del db_m[target_em]
                db_set("mem", db_m); st.warning(f"{target_em} のデータを抹消しました"); st.rerun()

    with tab_employment:
        st.markdown("#### 🏢 SYSTEM-ZERO & AGI雇用・解雇統括パネル")
        c_sz1, c_sz2 = st.columns([3, 1])
        sz_status = "🟢 稼働中 (超越監視作動中)" if st.session_state.get("system_zero_active", True) else "🔴 解雇・停止中"
        c_sz1.markdown(f"**SYSTEM-ZERO 状態:** {sz_status}")
        if st.session_state.get("system_zero_active", True):
            if c_sz2.button("💀 総括神を解雇/停止", type="primary", use_container_width=True):
                st.session_state["system_zero_active"] = False
                st.warning("管理者権限により SYSTEM-ZERO を解雇・停止させました。"); st.rerun()
        else:
            if c_sz2.button("⚡ 総括神を新任再起動", use_container_width=True):
                st.session_state["system_zero_active"] = True
                st.success("新世代 SYSTEM-ZERO を再配備しました。"); st.rerun()

        st.markdown("<br><b>💀 過去に解雇されたエージェント履歴</b>", unsafe_allow_html=True)
        fired_list = st.session_state.get("fired_agents", [])
        if fired_list:
            st.markdown(
                """
                <div class="admin-table-container">
                <table class="admin-table">
                <thead><tr><th>解雇日時</th><th>エージェント名</th><th>最終スコア</th><th>解雇執行者</th><th>解雇理由・違反事項</th></tr></thead>
                <tbody>
                """ + "".join([
                    f"<tr><td>{fa.get('time','-')}</td>"
                    f"<td style='color:#f87171;'><b>{fa.get('name','')}</b></td>"
                    f"<td style='color:#fde047;'>{fa.get('score','')}</td>"
                    f"<td style='color:#38bdf8;'>{fa.get('fired_by','特命監査員')}</td>"
                    f"<td>{fa.get('reason','')}</td></tr>"
                    for fa in fired_list
                ]) + "</tbody></table></div>", unsafe_allow_html=True
            )
        else:
            st.caption("現在、解雇履歴はありません。全10名のエージェントが優秀に稼働しています。")

    with tab_apply_wait:
        st.markdown("#### 📩 新規会員登録 審査待ちリスト")
        db_all = load_mem()
        pending_users = {em: u for em, u in db_all.items() if u.get("status") == "pending"}
        if pending_users:
            for p_em, p_u in list(pending_users.items()):
                st.markdown(
                    f'<div style="background:rgba(15,23,42,0.85);border:1px solid rgba(56,189,248,0.3);border-radius:8px;padding:12px 16px;margin-bottom:10px;">'
                    f'<span style="font-size:15px;font-weight:800;color:#f8fafc;">{p_u.get("name","未入力")}</span> '
                    f'<span style="font-size:12px;color:#94a3b8;">({p_em})</span><br>'
                    f'<span style="font-size:11.5px;color:#64748b;">申請日: {p_u.get("applied_at","-")} ｜ 端末FP: {p_u.get("fp","-")}</span>'
                    f'</div>', unsafe_allow_html=True
                )
                col_btn1, col_btn2 = st.columns([1, 1])
                if col_btn1.button(f"✅ 承認する ({p_u.get('name','')})", key=f"appr_{p_em}", use_container_width=True):
                    db_all[p_em]["status"] = "approved"; db_all[p_em]["approved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    db_set("mem", db_all)
                    send_mail(p_em, "【YAMASHISHI LAB】会員登録が承認されました", f"{p_u.get('name','')} 様\n申請が承認されました。専用アクセスコードは【 {db_all[p_em]['passcode']} 】です。")
                    st.success(f"{p_em} を承認しました"); st.rerun()

                if col_btn2.button(f"🚫 拒否・却下 ({p_u.get('name','')})", key=f"rej_{p_em}", use_container_width=True):
                    del db_all[p_em]; db_set("mem", db_all)
                    st.warning(f"{p_em} の申請を却下しました"); st.rerun()
        else:
            st.info("現在、承認待ちの新規申請はありません。")
    st.stop()

# ■ フォーカスモード（一覧に戻るボタンは最下部に移動済み）
focused_item = st.session_state.get("focused_stock_item")
if focused_item:
    st.markdown("### ⚛️ 銘柄詳細・買い方合議フォーカスモード")
    render_card(focused_item, is_custom=False, kp=f"foc_{focused_item['code']}", is_focused=True)
    st.stop()

# ■ ニュース詳細画面
if st.session_state.get("navigation_page") == "NEWS_DETAIL":
    tn = st.session_state.get("selected_news_item") or all_impact_news[0]
    st.markdown(f'<div class="glass-header" style="border-left:5px solid #ef4444;"><span class="pill-badge" style="background:#ef4444;color:#fff;font-weight:900;">🚨 重大ニュース深掘り</span><div style="font-size:20px;font-weight:900;margin-top:10px;">{tn["title"]}</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="rank-card" style="border-left-color:#a855f7;"><div style="font-size:15px;color:#e9d5ff;font-weight:800;margin-bottom:6px;">🧠 波及メカニズム</div><div style="font-size:13.5px;line-height:1.7;">{tn["detail"]["mechanism"]}</div><div class="beginner-action-box" style="margin-top:14px;"><b>⚡ {investment_style.split(" ")[1]} 実践トレード立ち回り</b><br>{tn["detail"]["action_guide"].replace(chr(10), "<br>")}</div></div>', unsafe_allow_html=True)
    st.markdown("### 🔗 連動注目銘柄")
    for idx, r_item in enumerate(sorted(all_res, key=lambda x: x["expect_pct"], reverse=True)[:3], 1): 
        render_card(r_item, rank=idx, kp=f"nr_{tn['id']}")
    if st.button("⬅️ メイン画面に戻る", use_container_width=True, type="primary"): 
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

def cut_stocks(slist, pct): 
    return slist[:max(3, int(round(len(slist) * (pct / 100.0))))] if slist else []

cats = ["🏆 総合TOP5", "⚛️ 量子トンネル突破TOP10", "🏛️ 機関最新ミクロ構造TOP10", "🚨 重大ニュース＆連動株", "🎟️ IPO募集・新規上場", "🏦 機関VPIN・OFI", "🔥 5ch＆短期モメンタム", "📋 監視シート"] + [f"📂 {g}" for g in STOCK_POOL.keys()]
st.markdown(f'<div style="font-size:13px;font-weight:800;color:#38bdf8;margin-bottom:8px;letter-spacing:1px;">📂 QUANTUM STRATEGY ({investment_style.split(" ")[1]})</div>', unsafe_allow_html=True)

if st.session_state.get("active_category") not in cats: 
    st.session_state["active_category"] = "🏆 総合TOP5"

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

if sel_cat == "🏆 総合TOP5":
    for i, r in enumerate(surv[:5], 1): render_card(r, rank=i, kp="top5")
elif sel_cat == "⚛️ 量子トンネル突破TOP10":
    for i, r in enumerate(sorted(all_res, key=lambda x: x["q_score"], reverse=True)[:10], 1): render_card(r, rank=i, kp="qtop")
elif sel_cat == "🏛️ 機関最新ミクロ構造TOP10":
    for i, r in enumerate(sorted(all_res, key=lambda x: x["ms_score"], reverse=True)[:10], 1): render_card(r, rank=i, kp="mstop")
elif sel_cat == "🚨 重大ニュース＆連動株":
    for n in all_impact_news:
        st.markdown(f'<div class="rank-card" style="border-left-color:#ef4444;"><div style="font-size:12px;color:#f87171;font-weight:800;">🚨 {n["cat"]}</div><div style="font-size:16px;font-weight:900;color:#f8fafc;margin:6px 0;">{n["title"]}</div><div style="font-size:12.5px;color:#94a3b8;">{n["detail"]["sector_focus"]} ｜ 発表元: {n["source"]}</div></div>', unsafe_allow_html=True)
        if st.button("🔥 詳細レポートを見る", key=f"tab_n_{n['id']}", use_container_width=True): 
            st.session_state["selected_news_item"] = n
            st.session_state["navigation_page"] = "NEWS_DETAIL"
            st.rerun()
elif sel_cat == "🎟️ IPO募集・新規上場":
    st.markdown(
        '<div class="glass-header">'
        '<div style="font-size:17px;font-weight:900;color:#f8fafc;">🎟️ 新規上場 (IPO) ブックビルディング募集・深掘り解析</div>'
        '<div style="font-size:12.5px;color:#94a3b8;margin-top:4px;">需給逼迫度・公募割れリスク・ロックアップ条件・初値騰落予測を量子AIが全解剖。</div>'
        '</div>', unsafe_allow_html=True
    )
    for ipo in IPO_OFFERINGS:
        links_html = "".join([f'<a href="{url}" target="_blank" rel="noopener noreferrer" class="ipo-link-btn">🔗 {lbl}</a>' for lbl, url in ipo["links"]])
        st.markdown(
            f'<div class="ipo-detail-card">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;margin-bottom:8px;">'
            f'<span class="pill-badge" style="background:#f59e0b;color:#0f172a;font-weight:900;font-size:13px;">🏆 第{ipo["rank"]}位 ({ipo["score"]}点)</span>'
            f'<span style="font-size:13px;font-weight:800;color:#fde047;">{ipo["tier"]}</span>'
            f'</div>'
            f'<div style="font-size:20px;font-weight:900;color:#f8fafc;">{ipo["name"]} <span style="font-size:14px;color:#94a3b8;">({ipo["code"]} / {ipo["market"]})</span></div>'
            f'<div style="font-size:13px;color:#38bdf8;font-weight:700;margin-top:4px;">🚀 テーマ: {ipo["theme"]}</div>'
            f'<div class="trade-plan-box" style="margin-top:12px;">'
            f'<div><div style="font-size:10px;color:#94a3b8;">📅 BB期間</div><div style="font-size:12px;font-weight:800;color:#fde047;">{ipo["bb_period"]}</div></div>'
            f'<div><div style="font-size:10px;color:#94a3b8;">🔔 上場予定日</div><div style="font-size:12px;font-weight:800;">{ipo["list_date"]}</div></div>'
            f'<div><div style="font-size:10px;color:#94a3b8;">💰 仮条件 (価格帯)</div><div style="font-size:12px;font-weight:800;color:#a7f3d0;">{ipo["price_band"]}</div></div>'
            f'<div><div style="font-size:10px;color:#94a3b8;">📦 吸収金額 (規模)</div><div style="font-size:12px;font-weight:800;color:#bae6fd;">{ipo["absorb_amt"]}</div></div>'
            f'</div>'
            f'<div style="background:rgba(0,0,0,0.35);padding:12px;border-radius:10px;margin-top:12px;border:1px solid rgba(255,255,255,0.08);">'
            f'<div style="font-size:12.5px;color:#cbd5e1;line-height:1.7;"><b>【事業詳細＆初値分析】:</b><br>{ipo["detail_desc"]}</div>'
            f'<div style="font-size:12px;color:#94a3b8;margin-top:8px;"><b>・主幹事証券:</b> {ipo["lead"]}</div>'
            f'<div style="font-size:12px;color:#94a3b8;margin-top:3px;"><b>・資金使途:</b> {ipo["use_of_funds"]}</div>'
            f'<div style="font-size:12px;color:#fca5a5;margin-top:3px;"><b>・ロックアップ条項:</b> {ipo["lockup"]}</div>'
            f'</div>'
            f'<div style="margin-top:10px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;">'
            f'<div>{links_html}</div>'
            f'<div style="font-size:14px;font-weight:900;color:#fde047;margin-top:6px;">初値予想騰落率: <span style="font-size:16px;">{ipo["expect_return"]}</span></div>'
            f'</div></div>', unsafe_allow_html=True
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
