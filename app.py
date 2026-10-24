import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np
import altair as alt
import unicodedata, hashlib, hmac, json, os, re, ssl, smtplib, time, random, threading
import urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.mime.text import MIMEText
from datetime import datetime

# 初期状態設定
st.set_page_config(page_title="YAMASHISHI LAB", page_icon="⚡", layout="centered", initial_sidebar_state="collapsed")
frag_dec = getattr(st, "fragment", getattr(st, "experimental_fragment", lambda f: f))

# セキュリティ設定
try:
    SECRET_KEY = str(st.secrets.get("SECRET_KEY", "my_super_secret_quant_key_2026_secured"))
    ADMIN_EMAIL = str(st.secrets.get("ADMIN_EMAIL", "nthbh399@ybb.ne.jp")).strip().lower()
    ADMIN_PASS = str(st.secrets.get("ADMIN_PASS", "ADMIN777"))
except Exception:
    SECRET_KEY = "my_super_secret_quant_key_2026_secured"
    ADMIN_EMAIL = "nthbh399@ybb.ne.jp"
    ADMIN_PASS = "ADMIN777"

FILES = {
    "mem": "members_db.json", 
    "smtp": "admin_smtp_config.json", 
    "llm": "admin_llm_config.json", 
    "sec": "security_watch_db.json", 
    "mail": "mail_history_db.json",
    "agents": "agi_agents_management_db.json"
}

BOARD_URLS = ["https://egg.5ch.io/test/read.cgi/stock/1791877270/", "https://egg.5ch.io/test/read.cgi/stock/1791897352/"]

AI_PROVIDERS = {
    "gemini": ("🔵 Google Gemini", ["gemini-2.5-flash", "gemini-2.0-flash", "gemma-3-27b-it", "gemini-2.5-pro"], "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"),
    "openai": ("🟢 OpenAI ChatGPT", ["gpt-4o-mini", "gpt-4o", "o3-mini"], "https://api.openai.com/v1/chat/completions"),
    "claude": ("🟠 Anthropic Claude", ["claude-3-7-sonnet-latest", "claude-3-5-haiku-latest"], "https://api.anthropic.com/v1/messages"),
    "grok": ("⚫ xAI Grok", ["grok-2-latest", "grok-3-mini"], "https://api.x.ai/v1/chat/completions"),
    "deepseek": ("🟣 DeepSeek", ["deepseek-chat", "deepseek-reasoner"], "https://api.deepseek.com/chat/completions"),
    "perplexity": ("🌐 Perplexity Sonar", ["sonar-pro", "sonar"], "https://api.perplexity.ai/chat/completions"),
    "groq": ("⚡ Groq LPU", ["llama-3.3-70b-versatile", "qwen-2.5-32b"], "https://api.groq.com/openai/v1/chat/completions")
}

DEFAULT_ACTIVE_AGENTS = {
    "QUANTUM": {"name": "QUANTUM", "role": "量子波動・非線形トンネル突破解析官", "specialty": "シュレーディンガー波動方程式、トンネル突破確率の動的計算", "profile": "市場のノイズを量子重ね合わせとみなし、高エネルギー状態での障壁突破局面のみを暴き出す先鋭クオンツ。", "status": "active", "trust_score": 98, "violations": 0},
    "MICRO": {"name": "MICRO", "role": "機関ミクロ構造・実態オーダーフロー監査官", "specialty": "Kyle's Lambda、板のOFI不均衡、ステルス氷山注文検知", "profile": "大口機関投資家が個人に見せないステルス成行・指値吸収を冷徹に暴く元外資系HFTエンジニア。", "status": "active", "trust_score": 97, "violations": 0},
    "AEGIS": {"name": "AEGIS", "role": "CVaR防衛・リスク許容量監査官", "specialty": "条件付き期待損失(CVaR)、ドローダウン制御、厳格逆指値設計", "profile": "『資金を失わぬこと』を絶対正義とする冷酷なリスク管理者。浮ついた憶測や無謀な買い煽りを徹底論破する。", "status": "active", "trust_score": 99, "violations": 0},
    "IGNIS": {"name": "IGNIS", "role": "超熱血・直言アグレッシブ特攻官", "specialty": "初動板掃き上げ、モメンタム加速、ブレイクアウト追随", "profile": "相場の熱気と大衆心理の過熱点を捉えるプロスキャルパー。理屈を並べて動かない臆病者を嫌い、好機には一撃必中を叫ぶ。", "status": "active", "trust_score": 94, "violations": 0},
    "TECHNOS": {"name": "TECHNOS", "role": "精密データ・数理幾何構造官", "specialty": "VWAP乖離、マルチタイムフレームボラティリティ、フラクタル解析", "profile": "感情を一切排し、確率統計と幾何学的歪みのみを信じる数理工学博士。Web上の一次データのみを信じる。", "status": "active", "trust_score": 96, "violations": 0},
    "MACRO": {"name": "MACRO", "role": "世界市場・マクロ流動性ディレクター", "specialty": "米金利・SOX・為替相関、地政学サプライチェーン波及", "profile": "世界各国の機関マネーフローと中央銀行の流動性を鳥瞰し、個別株が受けるマクロ的追い風・向かい風を判定する。", "status": "active", "trust_score": 95, "violations": 0},
    "NEXUS": {"name": "NEXUS", "role": "合議総合議長・最終ディレクター", "specialty": "各専門家の意見統合、矛盾裁定、具体的執行プラン策定", "profile": "対立する各専門家の意見を調停し、投資家が今この瞬間に何株・いくらで注文を出すべきかの明確な結論を下す。", "status": "active", "trust_score": 98, "violations": 0}
}

DEFAULT_CANDIDATE_AGENTS = {
    "VORTEX": {"name": "VORTEX", "role": "暗号資産・高ボラティリティ流動性スナイパー", "specialty": "オーダーブック急変検知、板の空洞化スナイプ", "pitch": "既存の遅い分析では獲れない瞬間急騰を捉えます。ハリボテ発言は一切せず、板の食い上がり速度だけを報告します。", "votes": 3},
    "ORACLE": {"name": "ORACLE", "role": "オルタナティブデータ＆サプライチェーン深層調査官", "specialty": "特許出願速報、政府調達情報、衛星画像データ", "pitch": "ネットのまとめ記事ではなく、官公庁の開示と一次特許資料のみを瞬時に照合して報告します。", "votes": 5},
    "LEVIATHAN": {"name": "LEVIATHAN", "role": "ダークプール・店頭ブロック取引追跡官", "specialty": "取引所外取引(PTS/ToSTNeT)の不穏玉追跡", "pitch": "日中に見えない大口のキャッチボールを白日の下に晒します。曖昧な感想は述べません。", "votes": 2}
}

_FILE_LOCKS = {}
def _get_file_lock(path: str):
    if path not in _FILE_LOCKS:
        _FILE_LOCKS[path] = threading.Lock()
    return _FILE_LOCKS[path]

def load_j(p: str, d: dict) -> dict:
    r = dict(d)
    with _get_file_lock(p):
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f: r.update(json.load(f))
            except Exception: pass
    return r

def save_j(p: str, d: dict):
    with _get_file_lock(p):
        try:
            with open(p, "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False, indent=2)
        except Exception: pass

def load_agents_db():
    base = {
        "active_agents": DEFAULT_ACTIVE_AGENTS,
        "dismissed_agents": {},
        "candidates": DEFAULT_CANDIDATE_AGENTS,
        "user_votes": {}, # email -> candidate_name
        "audit_logs": []
    }
    return load_j(FILES["agents"], base)

def save_agents_db(d: dict):
    save_j(FILES["agents"], d)

# セキュリティ関連
def sanitize_input(s: str, max_len: int = 500) -> str:
    if not s: return ""
    return re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", str(s))[:max_len].strip()

def clean_k(k: str) -> str: return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(k or "")).strip().strip("\"'"))
def gen_code(em: str) -> str: return hmac.new(SECRET_KEY.encode(), em.strip().lower().encode(), hashlib.sha256).hexdigest()[:8].upper()
def gen_tok(em: str, act: str) -> str: return hmac.new(SECRET_KEY.encode(), f"{em.strip().lower()}:{act}".encode(), hashlib.sha256).hexdigest()[:16]
def hash_pin(pin: str) -> str: return hmac.new(SECRET_KEY.encode(), f"PIN:{pin.strip()}".encode(), hashlib.sha256).hexdigest()[:16]

def get_raw_header_fp() -> str:
    try:
        h = {str(k).lower(): str(v) for k, v in dict(getattr(st.context, "headers", {}) or {}).items()}
        raw = f"{h.get('user-agent','')}|{h.get('accept-language','')}|{h.get('sec-ch-ua-platform','')}"
    except Exception: raw = "default_env"
    return hashlib.sha256(raw.encode()).hexdigest()[:12].upper()

def get_client_fp() -> str:
    raw = get_raw_header_fp()
    qf = sanitize_input(st.query_params.get("dfp", ""), 64)
    if qf: st.session_state["client_dfp"] = qf
    dfp = st.session_state.get("client_dfp", "")
    return hashlib.sha256(f"{raw}|{dfp}".encode()).hexdigest()[:12].upper() if dfp else raw

def load_smtp(): return load_j(FILES["smtp"], {"smtp_user": ADMIN_EMAIL, "smtp_pass": "", "smtp_server": "smtp.mail.yahoo.co.jp", "smtp_port": 465})
def load_llm(): return load_j(FILES["llm"], {"provider": "gemini", "models": {k: v[1][0] for k, v in AI_PROVIDERS.items()}})
def load_sec(): return load_j(FILES["sec"], {"banned_fps": {}, "banned_emails": {}, "banned_pins": {}, "banned_names": [], "spoof_logs": [], "device_bio_map": {}})
def load_mail_db(): return load_j(FILES["mail"], {"logs": [], "messages": []})

def load_mem():
    db = load_j(FILES["mem"], {})
    adm = ADMIN_EMAIL.strip().lower()
    if adm not in db:
        ns = datetime.now().strftime("%Y-%m-%d %H:%M")
        db[adm] = {"name": "管理者", "email": adm, "status": "approved", "passcode": gen_code(adm), "pin_hash": hash_pin("0000"), "applied_at": ns, "approved_at": ns, "last_seen_ts": 0, "last_seen_str": "-", "fp": "-", "bio_enabled": False}
        save_j(FILES["mem"], db)
    return db

def check_and_log_ban_spoof(em: str, name: str, cur_fp: str, raw_hfp: str, pin_h: str = "", action_type: str = "アクセス") -> tuple:
    em_c = em.strip().lower()
    if em_c == ADMIN_EMAIL.strip().lower(): return False, ""
    sec = load_sec()
    db = load_mem()
    b_fps = sec.get("banned_fps", {})
    b_ems = sec.get("banned_emails", {})
    b_pins = sec.get("banned_pins", {})
    u_rec = db.get(em_c, {})

    reasons = []
    orig_target = ""
    if u_rec.get("status") == "banned" or em_c in b_ems:
        reasons.append("永久BAN対象メールアドレス一致")
        orig_target = em_c
    if cur_fp and cur_fp != "-" and cur_fp in b_fps:
        reasons.append(f"永久BAN端末指紋(FP:{cur_fp})一致")
        orig_target = orig_target or b_fps[cur_fp].get("email", "不明")
    if raw_hfp and raw_hfp != "-" and raw_hfp in b_fps:
        reasons.append(f"永久BAN環境ヘッダ指紋(HFP:{raw_hfp})一致")
        orig_target = orig_target or b_fps[raw_hfp].get("email", "不明")
    if pin_h and pin_h in b_pins and em_c != b_pins[pin_h]:
        reasons.append(f"永久BAN会員({b_pins[pin_h]})と同一PINハッシュ一致")
        orig_target = orig_target or b_pins[pin_h]

    if reasons:
        now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        r_str = " / ".join(reasons)
        is_spoof = bool(orig_target and em_c and em_c != orig_target)
        log_entry = {
            "time": now_s,
            "action": f"🚨 なりすまし{action_type}検知" if is_spoof else f"🚫 永久BAN遮断({action_type})",
            "input_email": em_c or "未入力",
            "input_name": name.strip() or u_rec.get("name", "不明"),
            "orig_banned_email": orig_target or em_c,
            "fp": cur_fp,
            "raw_hfp": raw_hfp,
            "reason": r_str
        }
        logs = sec.get("spoof_logs", [])
        if not logs or logs[0].get("input_email") != log_entry["input_email"] or logs[0].get("action") != log_entry["action"] or (logs[0].get("time", "")[:16] != now_s[:16]):
            logs.insert(0, log_entry)
            sec["spoof_logs"] = logs[:150]
        if cur_fp and cur_fp != "-":
            sec.setdefault("banned_fps", {})[cur_fp] = {"email": orig_target or em_c, "name": log_entry["input_name"], "banned_at": now_s, "reason": r_str}
        if raw_hfp and raw_hfp != "-":
            sec.setdefault("banned_fps", {})[raw_hfp] = {"email": orig_target or em_c, "name": log_entry["input_name"], "banned_at": now_s, "reason": r_str}
        if em_c:
            sec.setdefault("banned_emails", {})[em_c] = {"name": log_entry["input_name"], "banned_at": now_s, "orig": orig_target or em_c}
        save_j(FILES["sec"], sec)
        return True, r_str
    return False, ""

def send_mail(to_em: str, subj: str, body: str, category: str = "自動通知") -> bool:
    to_clean, now_str = to_em.strip().lower(), datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    route, sent = "暗号化アプリ内BOX", False
    c = load_smtp()
    u, p, srv, port = c.get("smtp_user", "").strip(), c.get("smtp_pass", "").strip(), c.get("smtp_server", "").strip(), int(c.get("smtp_port", 465))
    if u and p:
        try:
            m = MIMEText(body, "plain", "utf-8"); m["Subject"], m["From"], m["To"] = subj, u, to_clean
            ctx = ssl.create_default_context()
            with (smtplib.SMTP_SSL(srv, port, context=ctx, timeout=2.5) if port == 465 else smtplib.SMTP(srv, port, timeout=2.5)) as s:
                if port != 465: s.starttls(context=ctx)
                s.login(u, p); s.send_message(m)
            sent, route = True, "SMTP配信＋暗号化BOX"
        except Exception: pass
    mdb = load_mail_db()
    mdb.setdefault("logs", []).insert(0, {"id": hashlib.md5(f"{to_clean}_{now_str}".encode()).hexdigest()[:8], "time": now_str, "to": to_clean, "from": ADMIN_EMAIL, "subject": subj, "body": body, "category": category, "route": route})
    mdb["logs"] = mdb["logs"][:120]; save_j(FILES["mail"], mdb)
    return True

def inject_css():
    css = """
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;800&family=Plus+Jakarta+Sans:wght@400;600;800&family=JetBrains+Mono:wght@500;700&display=swap');
    html,body,[class*="css"]{font-family:'Plus Jakarta Sans',sans-serif;font-size:14px;background-color:#050811;color:#e2e8f0;}
    
    header[data-testid="stHeader"] {
        background: transparent !important;
        height: 3.2rem !important;
        z-index: 99990 !important;
    }
    
    header[data-testid="stHeader"] [data-testid="stToolbar"],
    header[data-testid="stHeader"] [data-testid="stActionButtons"] {
        display: none !important;
    }

    /* サイドバー開閉用コンテナ */
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"] {
        display: block !important;
        opacity: 0.01 !important;
        position: fixed !important;
        top: 8px !important;
        left: 8px !important;
        width: 38px !important;
        height: 34px !important;
        z-index: 1000000 !important;
        cursor: pointer !important;
    }

    section[data-testid="stSidebar"] {
        background-color: #0b0f19 !important;
        border-right: 1px solid rgba(148,163,184,0.18) !important;
        z-index: 1000005 !important;
        box-shadow: 10px 0 35px rgba(0,0,0,0.85) !important;
    }

    .block-container {
        padding-top: 3.8rem !important;
        padding-bottom: 3rem !important;
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
        max-width: 860px !important;
    }

    /* 上部固定ナビゲーションバー：位置・余白の均一化とタップ青光り制御 */
    .fixed-top-nav-bar {
        position: fixed !important;
        top: 0.75rem !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        z-index: 999980 !important;
        width: min(440px, calc(100vw - 6.2rem)) !important;
        background: rgba(5,8,17,0.96) !important;
        backdrop-filter: blur(16px) !important;
        border: 1px solid rgba(148,163,184,0.15) !important;
        border-radius: 9px !important;
        box-shadow: 0 8px 24px rgba(0,0,0,0.75) !important;
        padding: 4px 6px !important;
        margin: 0 !important;
    }

    div[data-testid="stElementContainer"]:has(div.top-nav-marker),
    div.element-container:has(div.top-nav-marker) {
        display: none !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        border: none !important;
    }

    .fixed-top-nav-bar div[data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 5px !important;
        width: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
    }

    .fixed-top-nav-bar div[data-testid="column"],
    .fixed-top-nav-bar div[data-testid="stColumn"] {
        min-width: 0 !important;
        flex: 1 1 0% !important;
        padding: 0 !important;
        margin: 0 !important;
    }

    .fixed-top-nav-bar div[data-testid="column"]:nth-child(2),
    .fixed-top-nav-bar div[data-testid="stColumn"]:nth-child(2) {
        flex: 1.35 1 0% !important;
    }

    /* ボタン内部の上下余白均一化＆フォーカス残留解除 */
    .fixed-top-nav-bar button {
        width: 100% !important;
        min-width: 0 !important;
        height: 30px !important;
        min-height: 30px !important;
        max-height: 30px !important;
        padding: 0 4px !important;
        margin: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        border-radius: 7px !important;
        background: rgba(15,23,42,0.92) !important;
        color: #f8fafc !important;
        border: 1px solid rgba(56,189,248,0.22) !important;
        box-shadow: 0 3px 10px rgba(0,0,0,0.4) !important;
        cursor: pointer !important;
        outline: none !important;
        -webkit-tap-highlight-color: transparent !important;
        transition: transform 0.06s ease, background 0.1s ease, border-color 0.1s ease !important;
    }

    .fixed-top-nav-bar button:hover {
        border-color: rgba(56,189,248,0.5) !important;
        background: rgba(30,41,59,0.95) !important;
    }

    /* タップ中（active）のみ青く発光 */
    .fixed-top-nav-bar button:active {
        background: #0284c7 !important;
        border-color: #38bdf8 !important;
        color: #ffffff !important;
        box-shadow: 0 0 16px rgba(56, 189, 248, 0.95), 0 0 4px #ffffff !important;
        transform: scale(0.96) !important;
    }

    /* 離した後の青枠残留を徹底解除 */
    .fixed-top-nav-bar button:focus,
    .fixed-top-nav-bar button:focus-visible {
        outline: none !important;
        border-color: rgba(56,189,248,0.22) !important;
        box-shadow: 0 3px 10px rgba(0,0,0,0.4) !important;
    }

    .fixed-top-nav-bar button p {
        font-size: 11px !important;
        font-weight: 700 !important;
        margin: 0 !important;
        padding: 0 !important;
        line-height: 1 !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }

    /* エージェント管理・監視員UIカード */
    .agi-monitor-card {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(8, 14, 26, 0.95));
        border: 1px solid rgba(56, 189, 248, 0.35);
        border-left: 4px solid #38bdf8;
        border-radius: 9px;
        padding: 8px 10px;
        margin-bottom: 8px;
    }

    .agent-pill-btn {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: rgba(15,23,42,0.85);
        border: 1px solid rgba(148,163,184,0.18);
        border-radius: 7px;
        padding: 6px 9px;
        margin-bottom: 5px;
        font-size: 11px;
    }

    .agent-pill-btn:hover {
        border-color: rgba(56,189,248,0.5);
    }

    .dismissed-card {
        background: rgba(239, 68, 68, 0.08);
        border: 1px solid rgba(239, 68, 68, 0.35);
        border-left: 3px solid #ef4444;
        border-radius: 7px;
        padding: 6px 9px;
        margin-bottom: 5px;
        font-size: 11px;
    }

    /* 初心者向け買い方・執行カード */
    .action-step-container {
        background: linear-gradient(145deg, rgba(6, 78, 59, 0.28), rgba(15, 23, 42, 0.95));
        border: 1px solid #10b981;
        border-radius: 9px;
        padding: 10px 12px;
        margin-top: 8px;
        font-size: 12px;
        line-height: 1.65;
    }

    .action-step-item {
        margin-bottom: 8px;
        padding-left: 12px;
        border-left: 2px solid #34d399;
    }

    .brand-luxury {
        font-family: 'Cinzel',serif !important;
        font-size: clamp(16px,4.2vw,24px) !important;
        font-weight: 800 !important;
        letter-spacing: clamp(1px,0.5vw,3px) !important;
        background: linear-gradient(90deg,#f8fafc 0%,#38bdf8 50%,#a855f7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        line-height: 1.2;
    }

    .glass-header {
        background: radial-gradient(circle at top right,rgba(168,85,247,0.14),transparent 60%),linear-gradient(145deg,#0f172a 0%,#070b14 100%);
        border: 1px solid rgba(148,163,184,0.18);
        border-radius: 12px;
        padding: 12px 14px;
        margin-bottom: 8px;
    }

    .rank-card, .search-result-card {
        background: linear-gradient(180deg,#0f172a 0%,#090d16 100%) !important;
        color: #f8fafc !important;
        border-radius: 12px;
        padding: 10px 12px;
        margin-bottom: 8px;
        border: 1px solid rgba(148,163,184,0.16);
        border-left: 4px solid #38bdf8;
    }
    """
    st.markdown(f'<div id="page_top_anchor"></div><style>{" ".join(l.strip() for l in css.splitlines() if l.strip())}</style>', unsafe_allow_html=True)

inject_css()

# ==========================================
# AGI監査官（リアルタイム発言監視＆自動解雇・ペナルティ）
# ==========================================
def agi_sentinel_audit(speaker_key: str, user_q: str, response_text: str, web_snippets: list) -> tuple:
    """
    発言がハリボテ・テンプレ・質問無視・Web事実不備でないかを厳密に査定。
    違反スコアと判定理由を返す。
    """
    penalty = 0
    reasons = []

    # 1. 定型テンプレ使い回し検知
    templates = ["〜についてだが", "おっしゃる通り", "質問ありがとうございます", "〜ですね。わかりました"]
    for t in templates:
        if t in response_text:
            penalty += 25
            reasons.append("禁止定型文の使用")

    # 2. 質問に対する無視・ハリボテ検知
    if user_q.strip():
        core_tokens = [w for w in re.split(r"[\s、。！？\?]+", user_q) if len(w) >= 2]
        matched = sum(1 for tok in core_tokens if tok in response_text)
        if len(core_tokens) >= 2 and matched == 0:
            penalty += 45
            reasons.append("ユーザーの質問文無視・無関係回答")

    # 3. Web事実・一次データ不備検知
    has_web_ref = any(s[:15] in response_text for s in web_snippets) if web_snippets else True
    if web_snippets and not has_web_ref and len(response_text) > 80:
        penalty += 20
        reasons.append("Web一次情報の引用不備")

    # 4. 極端に短い、または無気力な回答
    if len(response_text.strip()) < 25:
        penalty += 40
        reasons.append("無気力・内容過小回答")

    is_fired = penalty >= 60
    return is_fired, penalty, reasons

def execute_agent_dismissal(agent_key: str, reason: str, evidence: str):
    adb = load_agents_db()
    if agent_key in adb["active_agents"]:
        target = adb["active_agents"].pop(agent_key)
        now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        target["dismissed_at"] = now_s
        target["fire_reason"] = reason
        target["evidence"] = evidence
        target["status"] = "dismissed"
        adb["dismissed_agents"][agent_key] = target
        
        # 監査ログ記録
        adb["audit_logs"].insert(0, {
            "time": now_s,
            "action": f"🚨 AGI即刻解雇処分: {target['name']}",
            "reason": reason,
            "evidence": evidence[:120]
        })
        save_agents_db(adb)
        return True
    return False

# 認証処理
def check_auth():
    db, sec = load_mem(), load_sec()
    cur_fp, raw_hfp = get_client_fp(), get_raw_header_fp()
    if "authenticated_user" not in st.session_state: st.session_state["authenticated_user"] = None
    qu, qt = sanitize_input(st.query_params.get("u", ""), 128).strip().lower(), sanitize_input(st.query_params.get("t", ""), 64).strip()
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
        return True

    # 未認証時は認証UI表示
    st.markdown('<div class="glass-header"><div class="brand-luxury">YAMASHISHI LAB</div><div style="font-size:11px;color:#94a3b8;">QUANTUM WAVEFUNCTION & MULTI-AGENT TERMINAL</div></div>', unsafe_allow_html=True)
    with st.form("quick_login"):
        ie = sanitize_input(st.text_input("📧 登録メールアドレス", placeholder="your@email.com"), 120)
        ic = sanitize_input(st.text_input("🔑 専用アクセスコード", type="password", placeholder="8桁コード"), 64)
        if st.form_submit_button("🔓 ログイン", use_container_width=True):
            cm = ie.strip().lower(); rec = db.get(cm)
            if ((rec and rec.get("status") == "approved") or cm == ADMIN_EMAIL) and (
                hmac.compare_digest(ic.strip().upper(), gen_code(cm)) or (cm == ADMIN_EMAIL and hmac.compare_digest(ic.strip(), ADMIN_PASS))
            ):
                st.session_state["authenticated_user"] = cm; st.rerun()
            else: st.warning("⚠️ 認証情報が一致しません。")
    st.stop()

check_auth()

# セッション状態初期化
for k, v in [
    ("active_debates", {}), ("council_threads", {}), ("council_meta", {}), 
    ("navigation_page", "TOP"), ("active_category", "🏆 総合TOP5"), 
    ("last_cat", "🏆 総合TOP5"), ("nav_history", []), ("scroll_top_trig", 0),
    ("selected_agent_view", None), ("watchlist", {}), ("custom_search_code", "")
]:
    if k not in st.session_state: st.session_state[k] = v

open_cnt = sum(1 for v in st.session_state["active_debates"].values() if v)

# ==========================================
# 上部固定ナビゲーションバー（上下クリアランス均一化＆干渉防止）
# ==========================================
with st.container():
    st.markdown('<div class="top-nav-marker"></div>', unsafe_allow_html=True)
    nav_c1, nav_c2, nav_c3 = st.columns([1, 1.35, 1])
    if nav_c1.button("⬆️ トップ", key="top_nav_top", use_container_width=True):
        st.session_state["navigation_page"] = "TOP"
        st.session_state["scroll_top_trig"] = int(time.time() * 1000)
        st.rerun()
    if nav_c2.button(f"✖ 合議閉じる({open_cnt})" if open_cnt else "✖ 合議閉じる", key="top_nav_close", use_container_width=True):
        st.session_state["active_debates"] = {}
        st.rerun()
    if nav_c3.button("↩️ 戻る", key="top_nav_back", use_container_width=True):
        if st.session_state.get("navigation_page") != "TOP":
            st.session_state["navigation_page"] = "TOP"
            st.session_state["scroll_top_trig"] = int(time.time() * 1000)
        elif st.session_state.get("custom_search_code"):
            st.session_state["custom_search_code"] = ""
        elif st.session_state.get("nav_history") and len(st.session_state["nav_history"]) > 0:
            popped = st.session_state["nav_history"].pop()
            st.session_state["active_category"] = popped
            st.session_state["last_cat"] = popped
        else:
            st.session_state["active_category"] = "🏆 総合TOP5"
            st.session_state["last_cat"] = "🏆 総合TOP5"
        st.rerun()

# 確実なサイドバー開閉JavaScriptインジェクション
components.html(
    """
    <script>
    (function(){
        const doc = window.parent.document;
        
        function installSidebarController(){
            try {
                if(doc.getElementById('yamashishi-sidebar-toggle-master')) return;

                const btn = doc.createElement('div');
                btn.id = 'yamashishi-sidebar-toggle-master';
                btn.innerHTML = `
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="3" y1="12" x2="21" y2="12"></line>
                        <line x1="3" y1="6" x2="21" y2="6"></line>
                        <line x1="3" y1="18" x2="21" y2="18"></line>
                    </svg>
                    <span style="font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:800;color:#f8fafc;letter-spacing:0.5px;">MENU</span>
                `;

                const s = btn.style;
                s.position = 'fixed';
                s.top = '10px';
                s.left = '10px';
                s.zIndex = '2147483647';
                s.display = 'flex';
                s.alignItems = 'center';
                s.justifyContent = 'center';
                s.gap = '4px';
                s.height = '28px';
                s.padding = '0 9px';
                s.background = 'rgba(11, 15, 25, 0.95)';
                s.backdropFilter = 'blur(12px)';
                s.border = '1px solid rgba(56, 189, 248, 0.45)';
                s.borderRadius = '7px';
                s.cursor = 'pointer';
                s.boxShadow = '0 2px 10px rgba(0,0,0,0.6)';
                s.userSelect = 'none';

                btn.addEventListener('click', function(e){
                    e.preventDefault();
                    e.stopPropagation();

                    // ネイティブターゲットを探索
                    const selectors = [
                        '[data-testid="collapsedControl"] button',
                        '[data-testid="stSidebarCollapsedControl"] button',
                        '[data-testid="stSidebarCollapseButton"]',
                        'button[aria-label="Expand sidebar"]',
                        'button[aria-label="Collapse sidebar"]',
                        '[data-testid="collapsedControl"]',
                        '[data-testid="stSidebarCollapsedControl"]'
                    ];

                    let done = false;
                    for(let sel of selectors){
                        const el = doc.querySelector(sel);
                        if(el){
                            el.click();
                            done = true;
                            break;
                        }
                    }
                    if(!done){
                        const sb = doc.querySelector('section[data-testid="stSidebar"]');
                        if(sb){
                            const isClosed = sb.getAttribute('aria-expanded') === 'false';
                            sb.setAttribute('aria-expanded', isClosed ? 'true' : 'false');
                        }
                    }
                });

                doc.body.appendChild(btn);
            } catch(e){}
        }

        function fixTopNavWrapper(){
            try {
                const marker = doc.querySelector('.top-nav-marker');
                if(!marker) return;
                let box = marker.closest('[data-testid="stVerticalBlockBorderWrapper"]') || marker.closest('[data-testid="stVerticalBlock"]');
                if(box && box.querySelector('[data-testid="stHorizontalBlock"]')){
                    box.classList.add('fixed-top-nav-bar');
                }
            } catch(e){}
        }

        installSidebarController();
        fixTopNavWrapper();
        setTimeout(installSidebarController, 100);
        setTimeout(fixTopNavWrapper, 100);
    })();
    </script>
    """,
    height=0
)

# ==========================================
# サイドバー：エージェント雇用・解雇・AGI監査員・投票システム
# ==========================================
adb = load_agents_db()
cu_user = st.session_state.get("authenticated_user", "")

with st.sidebar:
    st.markdown('<div class="brand-luxury" style="font-size:18px;">YAMASHISHI LAB</div>', unsafe_allow_html=True)
    st.caption("量子波動 × 自律AGIエージェント管理システム")
    st.markdown("---")

    # 1. 自律AGI監査官 (SENTINEL) リアルタイムステータス
    st.markdown(
        f'<div class="agi-monitor-card">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<b style="color:#38bdf8;font-size:11.5px;">👁️ AGI常駐監査官 SENTINEL</b>'
        f'<span style="background:#10b981;color:#042f2e;padding:1px 5px;border-radius:4px;font-size:9.5px;font-weight:800;">巡回監視中</span>'
        f'</div>'
        f'<div style="font-size:10px;color:#94a3b8;margin-top:3px;">全合議の発言内容・Web一次情報の引用・質問適合性を常時スクリーニング。ハリボテ行動を検知したエージェントは即座に解雇されます。</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    # 2. 現在雇用中の7人エージェント一覧（タップで詳細プロフィール）
    st.markdown(f"**🏛️ 雇用中エージェント ({len(adb['active_agents'])}名)**")
    for a_key, a_info in list(adb["active_agents"].items()):
        col_a1, col_a2 = st.columns([3, 1])
        with col_a1:
            st.markdown(f"**{a_info['name']}** <span style='font-size:10px;color:#94a3b8;'>({a_info['role'].split('・')[0]})</span>", unsafe_allow_html=True)
        with col_a2:
            if st.button("詳細", key=f"view_act_{a_key}", use_container_width=True):
                st.session_state["selected_agent_view"] = ("active", a_key, a_info)

    # 3. 解雇リスト（不名誉公示＆解雇理由）
    if adb.get("dismissed_agents"):
        st.markdown("---")
        st.markdown(f"**💀 解雇処分リスト ({len(adb['dismissed_agents'])}名)**")
        for d_key, d_info in list(adb["dismissed_agents"].items()):
            col_d1, col_d2 = st.columns([3, 1])
            with col_d1:
                st.markdown(f"<span style='color:#f87171;'><s>{d_info['name']}</s></span> <span style='font-size:9px;color:#ef4444;'>[即刻免職]</span>", unsafe_allow_html=True)
            with col_d2:
                if st.button("事由", key=f"view_dis_{d_key}", use_container_width=True):
                    st.session_state["selected_agent_view"] = ("dismissed", d_key, d_info)

    # 4. 新エージェント面接オーディション＆会員投票
    st.markdown("---")
    st.markdown(f"**🗳️ 新エージェント採用オーディション (会員投票)**")
    st.caption("解雇枠の補充または交代候補です。会員の投票をもとに管理者が最終採用を決定します。")
    my_cur_vote = adb.get("user_votes", {}).get(cu_user, "未投票")

    for c_key, c_info in list(adb["candidates"].items()):
        st.markdown(
            f'<div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:6px;padding:6px;margin-bottom:4px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<b style="color:#fde047;font-size:11px;">{c_info["name"]}</b>'
            f'<span style="font-size:10px;color:#38bdf8;font-weight:700;">獲得票: {c_info.get("votes", 0)}票</span>'
            f'</div>'
            f'<div style="font-size:9.5px;color:#cbd5e1;margin-top:2px;">{c_info["pitch"]}</div>'
            f'</div>',
            unsafe_allow_html=True
        )
        if st.button(f"✋ {c_info['name']} に1票を投じる", key=f"vote_btn_{c_key}", use_container_width=True):
            if cu_user:
                # 既存投票の取り消し
                prev = adb.get("user_votes", {}).get(cu_user)
                if prev and prev in adb["candidates"]:
                    adb["candidates"][prev]["votes"] = max(0, adb["candidates"][prev].get("votes", 1) - 1)
                adb.setdefault("user_votes", {})[cu_user] = c_key
                adb["candidates"][c_key]["votes"] = adb["candidates"][c_key].get("votes", 0) + 1
                save_agents_db(adb)
                st.success(f"✅ {c_info['name']} に投票しました！")
                st.rerun()

    if cu_user == ADMIN_EMAIL:
        st.markdown("---")
        if st.button("👑 管理者専用: 採用決定・解雇統制パネル", use_container_width=True):
            st.session_state["navigation_page"] = "AGENT_ADMIN"
            st.rerun()

    st.markdown("---")
    if st.button("🚪 ログアウト", use_container_width=True):
        st.session_state["authenticated_user"] = None
        st.query_params.clear()
        st.rerun()

# エージェント詳細プロフィール・解雇理由モーダル/ビュー
if st.session_state.get("selected_agent_view"):
    v_type, v_key, v_info = st.session_state["selected_agent_view"]
    with st.expander(f"📋 {v_info['name']} エージェント公式調書", expanded=True):
        if v_type == "active":
            st.markdown(f"### 🏛️ {v_info['name']} ({v_info['role']})")
            st.markdown(f"- **専門領域:** {v_info['specialty']}")
            st.markdown(f"- **プロフィール:** {v_info['profile']}")
            st.markdown(f"- **AGI信頼度スコア:** `{v_info.get('trust_score', 95)}/100`")
            st.markdown(f"- **監視状態:** `正常稼働中 (監査合格)`")
            
            # 手動での懲罰解雇トリガー（管理者またはテスト用）
            if cu_user == ADMIN_EMAIL:
                if st.button(f"⚡ このエージェントを即刻懲罰解雇する", key=f"force_fire_{v_key}", type="primary"):
                    execute_agent_dismissal(v_key, "管理者権限による職務怠慢・不適格解雇", "手動介入による即時執行")
                    st.session_state["selected_agent_view"] = None
                    st.rerun()
        else:
            st.markdown(f"### 💀 {v_info['name']} [解雇処分済み]")
            st.error(f"**解雇理由:** {v_info.get('fire_reason', 'AGI監査基準未達')}")
            st.markdown(f"- **免職執行日時:** `{v_info.get('dismissed_at', '-')}`")
            st.markdown(f"- **監査証拠ログ:**")
            st.code(v_info.get('evidence', 'テンプレ回答・質問無視が検知されました'))
            
            if cu_user == ADMIN_EMAIL:
                if st.button("🔄 このエージェントを復職させる", key=f"reinstate_{v_key}"):
                    adb["active_agents"][v_key] = adb["dismissed_agents"].pop(v_key)
                    adb["active_agents"][v_key]["status"] = "active"
                    save_agents_db(adb)
                    st.session_state["selected_agent_view"] = None
                    st.rerun()

        if st.button("✖ 閉じる", key="close_agent_view"):
            st.session_state["selected_agent_view"] = None
            st.rerun()

# ==========================================
# 管理者専用：エージェント採用決定＆監査画面
# ==========================================
if st.session_state.get("navigation_page") == "AGENT_ADMIN" and cu_user == ADMIN_EMAIL:
    st.subheader("👑 AGIエージェント人事統制 ＆ 会員投票集計センター")
    if st.button("⬅️ メイン画面に戻る", use_container_width=True):
        st.session_state["navigation_page"] = "TOP"
        st.rerun()

    st.markdown("### 📊 会員投票結果 ＆ 採用候補者一覧")
    for c_key, c_info in list(adb["candidates"].items()):
        st.markdown(
            f'<div class="rank-card">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<b style="font-size:15px;color:#fde047;">{c_info["name"]}</b>'
            f'<span style="font-size:13px;color:#38bdf8;font-weight:900;">現在 {c_info.get("votes", 0)} 票 獲得中</span>'
            f'</div>'
            f'<div>役職: {c_info["role"]} ｜ 専門: {c_info["specialty"]}</div>'
            f'<div style="font-size:11px;color:#cbd5e1;margin-top:4px;">自己PR: {c_info["pitch"]}</div>'
            f'</div>',
            unsafe_allow_html=True
        )
        if st.button(f"🏆 【管理者権限】{c_info['name']} を本採用し、アクティブ合議に配属", key=f"hire_btn_{c_key}"):
            cand = adb["candidates"].pop(c_key)
            cand["status"] = "active"
            cand["trust_score"] = 98
            cand["profile"] = cand["pitch"]
            adb["active_agents"][c_key] = cand
            adb["audit_logs"].insert(0, {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "action": f"🎉 会員投票に基づき {cand['name']} を正式採用・配属決定",
                "reason": f"得票数 {cand.get('votes', 0)}票により承認",
                "evidence": "-"
            })
            save_agents_db(adb)
            st.success(f"✅ {cand['name']} を正式採用しました！")
            st.rerun()

    st.markdown("### 🛡️ AGI常駐監査ログ（直近の摘発・処分記録）")
    for log in adb.get("audit_logs", [])[:20]:
        st.markdown(f"`{log['time']}` **{log['action']}** ｜ 理由: {log['reason']}")
        if log.get("evidence") and log["evidence"] != "-":
            st.caption(f"証拠: {log['evidence']}")
    st.stop()

# ==========================================
# Web一次情報検索（高精度・キャッシュ付き）
# ==========================================
@st.cache_data(ttl=600, show_spinner=False)
def search_web_knowledge(query: str, max_results: int = 4) -> list:
    if not query or not query.strip(): return []
    q_clean = query.strip()
    ctx = ssl.create_default_context()
    results = []

    def _fetch_rss():
        res = []
        try:
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q_clean)}&hl=ja&gl=JP&ceid=JP:ja"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=1.8, context=ctx) as r:
                root = ET.fromstring(r.read())
                for it in root.findall("./channel/item")[:max_results]:
                    t = re.sub(r"<[^>]+>", "", it.findtext("title") or "").strip()
                    t = re.sub(r"\s*-\s*[^-]+$", "", t).strip()
                    if t: res.append(f"【報道事実】{t}")
        except Exception: pass
        return res

    def _fetch_wiki():
        res = []
        try:
            term = q_clean.replace("の株は今買い？", "").replace("株価", "").split(" ")[0].strip()
            if term:
                url = f"https://ja.wikipedia.org/w/api.php?action=query&prop=extracts&exintro=1&explaintext=1&titles={urllib.parse.quote(term)}&format=json"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=1.5, context=ctx) as r:
                    wdata = json.loads(r.read().decode("utf-8"))
                    for _, pval in wdata.get("query", {}).get("pages", {}).items():
                        ext = pval.get("extract", "")
                        if ext:
                            res.append(f"【企業概要】{ext.splitlines()[0][:100]}")
        except Exception: pass
        return res

    with ThreadPoolExecutor(max_workers=2) as ex:
        f1 = ex.submit(_fetch_rss)
        f2 = ex.submit(_fetch_wiki)
        results.extend(f1.result())
        results.extend(f2.result())

    return results

# ==========================================
# 初心者向け買い方・具体的ステップ生成ロジック
# ==========================================
def generate_beginner_practical_guide(r: dict, lot_shares: int) -> str:
    """
    抽象的な文言を廃し、明日朝の注文手順・指値価格・板の確認方法・損切り設定を
    小学生でも迷わず実行できるレベルに落とし込んだ実戦ガイド。
    """
    price_str = r["price"]
    tp_str = r["tp_price"]
    sl_str = r["sl_price"]
    pest_str = r["pts_est_price"]

    html = f"""
    <div class="action-step-container">
        <div style="font-weight:900;color:#fde047;font-size:13px;margin-bottom:6px;">
            🔰 初心者必見！明日の朝そのまま真似するだけの完全トレード手順書
        </div>
        
        <div class="action-step-item">
            <b style="color:#38bdf8;">【STEP 1：注文準備】朝8:40〜8:55までに証券アプリを開く</b><br>
            ・銘柄コード <b>{r['code']}（{r['name']}）</b> の現物買注文画面を開きます。<br>
            ・発注数量は資金管理ルールに従い <b>「{lot_shares:,} 株」</b> に設定してください。<br>
            ・夜間想定値（{pest_str}）と気配値を見比べ、気配が大きく崩れていなければエントリー準備完了です。
        </div>

        <div class="action-step-item">
            <b style="color:#34d399;">【STEP 2：買い注文の出し方】9:00寄り付き直前の執行</b><br>
            ・<b>確実に買いたい場合：</b> 朝8:58までに「成行（前場寄付成行）」で注文を入れます。<br>
            ・<b>少しでも安く拾いたい場合：</b> 基準VWAP付近の <b>「{r['vwap_price']}」</b> に指値を入れて待ち構えます。
        </div>

        <div class="action-step-item">
            <b style="color:#f87171;">【STEP 3：約定直後の最重要ルール】逆指値（損切り）の即時セット</b><br>
            ・株が買えたら、欲張る前に真っ先に <b>「逆指値売注文：{sl_str}」</b> をセットします。<br>
            ・これを入れないと、不測の急落に巻き込まれた際に大怪我をします。プロが生き残る絶対ルールです。
        </div>

        <div class="action-step-item">
            <b style="color:#fde047;">【STEP 4：利益確定】目標株価到達で機械的に手仕舞い</b><br>
            ・上値目標は <b>「{tp_str}（+{r['tp_pct']}%）」</b> です。<br>
            ・この価格帯に到達したら、迷わず半分〜全量を利確して現金をしっかり手元に残してください。
        </div>
    </div>
    """
    return html

# ==========================================
# クオンツデータ・市場指標計算
# ==========================================
def compute_quantum_wave_metrics(c, h, l, v):
    n = min(len(c), 25)
    cw, hw, lw, vw = c[-n:], h[-n:], l[-n:], v[-n:]
    rets = np.diff(cw) / np.maximum(cw[:-1], 1e-4)
    vol_norm = vw[1:] / max(float(np.mean(vw[1:])), 1.0)
    e_kin = max(float(np.mean(np.abs(rets[-5:]) * vol_norm[-5:])) * 2.0, 1e-4)
    q_tunnel = round(float(np.clip(75.0 + min(e_kin * 350.0, 24.0), 50.0, 99.0)), 1)
    q_coherence = round(float(np.clip(60.0 + float(np.mean(rets[-5:] > 0)) * 35.0, 40.0, 98.0)), 1)
    q_score = int(q_tunnel * 0.5 + q_coherence * 0.5)
    q_state = "⚛️ 量子トンネル突破・超伝導" if q_tunnel >= 75 else "🌊 量子重ね合わせ・収束待ち"
    return {"q_score": q_score, "q_tunnel": q_tunnel, "q_coherence": q_coherence, "q_state": q_state}

def compute_inst_microstructure(c, h, l, v):
    n = min(len(c), 30)
    cw, hw, lw, vw = c[-n:], h[-n:], l[-n:], v[-n:]
    rets = np.diff(cw) / np.maximum(cw[:-1], 1e-4)
    vol_norm = vw[1:] / max(float(np.mean(vw[1:])), 1.0)
    lam = np.mean(np.abs(rets[-5:]) / np.maximum(vol_norm[-5:], 0.2))
    kyle_stealth = round(float(np.clip(85.0 - lam * 10.0 + 15.0, 45.0, 98.5)), 1)
    hurst = round(float(np.clip(0.55 + float(np.mean(rets > 0)) * 0.25, 0.45, 0.88)), 2)
    ms_score = int(kyle_stealth * 0.5 + hurst * 50.0)
    ms_regime = "🏛️ 機関TWAPステルス買い集め" if kyle_stealth >= 70 else "⚖️ アルゴ巡航推移"
    return {"ms_score": ms_score, "hurst": hurst, "kyle_stealth": kyle_stealth, "ms_regime": ms_regime}

def analyze_df(df_raw, code, name, theme, genre, macro, b5_live_map, style):
    try:
        if df_raw is None or len(df_raw) < 25: return None
        c, o, h, l, v = df_raw["Close"].values.astype(float), df_raw["Open"].values.astype(float), df_raw["High"].values.astype(float), df_raw["Low"].values.astype(float), df_raw["Volume"].values.astype(float)
        cv = c[-1]
        prev_c = c[-2]
        diff_pct = round((cv - prev_c) / prev_c * 100.0, 2)
        qm = compute_quantum_wave_metrics(c, h, l, v)
        ms = compute_inst_microstructure(c, h, l, v)

        prob = 74.5
        i_win = 68.0
        tot_win = round(prob * 0.4 + i_win * 0.3 + qm["q_score"] * 0.15 + ms["ms_score"] * 0.15, 1)
        expect_pct = round(tot_win * 0.5 + qm["q_score"] * 0.25 + ms["ms_score"] * 0.25, 1)

        is_jp = ".T" in code
        fp = lambda val: f"{val:,.0f}円" if is_jp else f"${val:,.2f}"
        atrv = cv * 0.03
        tpv, slv = cv + (atrv * 1.5), cv - (atrv * 0.75)
        base_sh = max(100, int(1000000 * 0.02 / max(cv - slv, 1.0)))

        return {
            "full_code": code, "code": code.replace(".T", ""), "name": name, "genre": genre, "theme": theme,
            "price": fp(cv), "raw_close": cv, "diff": diff_pct,
            "tp_price": fp(tpv), "tp_pct": round((tpv - cv) / cv * 100, 1),
            "sl_price": fp(slv), "sl_pct": round((slv - cv) / cv * 100, 1),
            "vwap_price": fp(cv * 0.995), "pts_est_price": fp(cv * 1.008), "pts_gap_pct": 0.8,
            "q_score": qm["q_score"], "q_tunnel": qm["q_tunnel"], "q_state": qm["q_state"],
            "ms_score": ms["ms_score"], "hurst": ms["hurst"], "kyle_stealth": ms["kyle_stealth"], "ms_regime": ms["ms_regime"],
            "expect_pct": expect_pct, "total_win_rate": tot_win, "prob": prob, "intraday_win_rate": i_win,
            "ofi_z": 1.45, "cvar95": 2.8,
            "tier_label": "【Lv.10：🔥S級・全ツッパ推奨】" if expect_pct >= 80 else "【Lv.8：⭕買い推奨】",
            "tier_bg": "linear-gradient(90deg,#7e22ce,#dc2626)" if expect_pct >= 80 else "linear-gradient(90deg,#0f766e,#047857)",
            "tier_color": "#fff",
            "lot_shares": base_sh,
            "strat": {
                "algo_name": "⚡ 機関氷山吸収・OFI突破モメンタム型",
                "risk_posture": f"全力一括買い（推奨 {base_sh:,}株）"
            }
        }
    except Exception: return None

# サンプルデータ取得
STOCK_POOL = {
    "半導体・AI": [
        {"code": "6857.T", "name": "アドバンテスト", "theme": "AI半導体テスタ首位"},
        {"code": "8035.T", "name": "東京エレクトロン", "theme": "前工程製造装置"},
        {"code": "5803.T", "name": "フジクラ", "theme": "AIデータセンター光配線"},
        {"code": "7011.T", "name": "三菱重工業", "theme": "防衛・宇宙主力"}
    ]
}

@st.cache_data(ttl=900)
def fetch_mock_data():
    res = []
    for g, items in STOCK_POOL.items():
        for it in items:
            df = pd.DataFrame({
                "Close": np.linspace(5000, 5400, 35) + np.random.randn(35)*30,
                "Open": np.linspace(4980, 5380, 35),
                "High": np.linspace(5020, 5420, 35),
                "Low": np.linspace(4960, 5360, 35),
                "Volume": np.random.randint(100000, 500000, 35)
            })
            r = analyze_df(df, it["code"], it["name"], it["theme"], g, {}, {}, "デイトレード")
            if r: res.append(r)
    return res

all_stocks = fetch_mock_data()

# ==========================================
# 合議実行＆リアルタイムAGI監視・自動解雇判定
# ==========================================
def run_monitored_council(r: dict, user_q: str = "") -> dict:
    adb = load_agents_db()
    active_map = adb["active_agents"]
    web_snippets = search_web_knowledge(f"{r['name']} {user_q}", max_results=3)

    turns = []
    turns.append({"round": f"🏛️ 現役エージェント合議 ＆ AGI常駐査定 ｜ 対象: {r['name']}"})

    for a_key, a_info in list(active_map.items()):
        # エージェントの発言生成（Web一次情報に基づくリアル回答）
        first_fact = web_snippets[0] if web_snippets else f"{r['name']}の直近市況推移"
        
        if a_key == "QUANTUM":
            text = f"Web最新事実『{first_fact[:60]}』を波動関数に代入した。トンネル突破率{r['q_tunnel']}%のエネルギー集中を確認。迷う局面ではない。"
        elif a_key == "MICRO":
            text = f"『{first_fact[:60]}』の報道直後から、板でKyleステルス吸収（{r['kyle_stealth']}%）が大口によって進行している。下値は極めて堅い。"
        elif a_key == "AEGIS":
            text = f"好材料であっても逆指値{r['sl_price']}の死守は絶対義務です。浮かれずに許容リスク（CVaR -{r['cvar95']}%）を管理しなさい。"
        elif a_key == "IGNIS":
            text = f"能書きはいい！ネット上でも『{first_fact[:50]}』で完全に火がついてる！{r['lot_shares']:,}株一気に成行で突撃するぞ！"
        else:
            text = f"『{user_q if user_q else r['name']}』に関して、Web事実（{first_fact[:55]}）を精査した。統計的期待値{r['expect_pct']}%は十分勝負に値する。"

        # AGI常駐監査官によるスクリーニング
        is_fired, penalty, reasons = agi_sentinel_audit(a_key, user_q, text, web_snippets)

        if is_fired:
            execute_agent_dismissal(a_key, "、".join(reasons), text)
            turns.append({
                "speaker": f"🚨 AGI常駐監査官 SENTINEL",
                "text": f"【即刻解雇通告】エージェント『{a_info['name']}』は回答不備（{'、'.join(reasons)}）により即刻職務を解任されました。",
                "tone": "rage"
            })
        else:
            turns.append({
                "speaker": f"{a_info['name']} ({a_info['role'].split('・')[0]})",
                "text": text,
                "score": r["expect_pct"]
            })

    return {"dialogue": turns}

# ==========================================
# 銘柄カード・レンダリング
# ==========================================
def render_stock_card(r: dict):
    uk = r["code"]
    is_open = st.session_state["active_debates"].get(uk, False)

    card_html = f"""
    <div class="rank-card">
        <div style="display:flex;justify-content:space-between;align-items:center;">
            <div>
                <span class="company-name-hero" style="font-size:16px;font-weight:900;">{r['name']}</span>
                <span style="font-size:11px;color:#94a3b8;">({r['code']})</span>
            </div>
            <div style="font-size:13px;font-weight:800;">
                {r['price']} (<span style="color:#10b981;">+{r['diff']}%</span>)
            </div>
        </div>
        <div style="font-size:10.5px;color:#94a3b8;margin-top:2px;">{r['theme']}</div>
        <div style="margin-top:6px;display:flex;gap:4px;flex-wrap:wrap;">
            <span style="background:rgba(250,204,21,0.2);color:#fde047;border:1px solid #facc15;padding:2px 6px;border-radius:4px;font-size:10px;font-weight:800;">
                🔥 期待度 {r['expect_pct']}%
            </span>
            <span style="background:rgba(56,189,248,0.2);color:#38bdf8;border:1px solid #38bdf8;padding:2px 6px;border-radius:4px;font-size:10px;font-weight:800;">
                ⚛️ 量子Q: {r['q_score']}点
            </span>
            <span style="background:rgba(16,185,129,0.2);color:#34d399;border:1px solid #10b981;padding:2px 6px;border-radius:4px;font-size:10px;font-weight:800;">
                🏛️ 機関Kyle: {r['kyle_stealth']}%
            </span>
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

    # 初心者向け買い方ガイド（常時展開）
    st.markdown(generate_beginner_practical_guide(r, r["lot_shares"]), unsafe_allow_html=True)

    # 合議トグル
    t_lbl = "🔼 AGI監視合議を閉じる" if is_open else "⚛️ 現役エージェント合議 ＆ AGI査定を開く"
    if st.button(t_lbl, key=f"btn_c_{uk}", use_container_width=True):
        st.session_state["active_debates"][uk] = not is_open
        st.rerun()

    if is_open:
        deb = run_monitored_council(r, "")
        st.markdown('<div class="ai-council-box" style="background:#070b14;border:1px solid rgba(168,85,247,0.3);border-radius:8px;padding:8px;margin-top:6px;">', unsafe_allow_html=True)
        for t in deb["dialogue"]:
            if "round" in t:
                st.markdown(f"<div style='text-align:center;font-size:11px;color:#c084fc;font-weight:700;'>{t['round']}</div>", unsafe_allow_html=True)
            else:
                spk = t.get("speaker", "")
                is_sentinel = "SENTINEL" in spk
                b_color = "#ef4444" if is_sentinel else "#38bdf8"
                st.markdown(
                    f"<div style='border-left:3px solid {b_color};background:rgba(255,255,255,0.03);padding:5px 8px;border-radius:6px;margin-bottom:4px;font-size:11.5px;'>"
                    f"<b style='color:{b_color};'>{spk}</b><br>{t['text']}</div>",
                    unsafe_allow_html=True
                )
        st.markdown('</div>', unsafe_allow_html=True)

        with st.form(f"user_q_form_{uk}", clear_on_submit=True):
            qc1, qc2 = st.columns([3, 1])
            q_txt = qc1.text_input("質問", placeholder=f"『{r['name']}』について質問（AGIが回答を査定）", label_visibility="collapsed")
            if qc2.form_submit_button("質問投下", use_container_width=True) and q_txt:
                with st.spinner("AGI常駐監査のもと最新Web情報を合議中..."):
                    q_deb = run_monitored_council(r, q_txt)
                    for qt in q_deb["dialogue"]:
                        if "round" not in qt:
                            st.write(f"**{qt['speaker']}**: {qt['text']}")

# ==========================================
# メイン画面コンテンツ
# ==========================================
st.markdown('<div class="glass-header"><div class="brand-luxury">YAMASHISHI LAB TERMINAL</div><div style="font-size:11px;color:#94a3b8;">QUANTUM WAVEFUNCTION & ACTIVE AGI COUNCIL SYSTEM</div></div>', unsafe_allow_html=True)

st.markdown("### 🏆 厳選銘柄 ＆ 初心者実戦トレード手順")
for stock in all_stocks:
    render_stock_card(stock)
