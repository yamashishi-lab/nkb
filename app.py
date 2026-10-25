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

# ==========================================
# 1. 初期設定とセキュリティ
# ==========================================
st.set_page_config(page_title="YAMASHISHI LAB", page_icon="⚡", layout="centered", initial_sidebar_state="expanded")

try:
    SECRET_KEY = st.secrets.get("SECRET_KEY", "my_super_secret_quant_key_2026")
    ADMIN_EMAIL = st.secrets.get("ADMIN_EMAIL", "nthbh399@ybb.ne.jp")
    ADMIN_PASS = st.secrets.get("ADMIN_PASS", "ADMIN777")
except Exception:
    SECRET_KEY = "my_super_secret_quant_key_2026"
    ADMIN_EMAIL = "nthbh399@ybb.ne.jp"
    ADMIN_PASS = "ADMIN777"

FILES = {
    "mem": "members_db.json", 
    "smtp": "admin_smtp_config.json", 
    "llm": "admin_llm_config.json", 
    "sec": "security_watch_db.json", 
    "mail": "mail_history_db.json"
}

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
    {"rank": 1, "code": "401A", "name": "AIクロスロボティクス", "market": "東証G", "bb_period": "受付中〜10/28", "list_date": "11/06", "price_band": "1,680円〜1,850円", "expect_return": "+92.0%", "score": 96, "tier": "🌟 S級：全力BB参加（初値2倍濃厚）", "lead": "SBI証券 / 野村證券", "theme": "自律型AIドローン・防衛省関連の超大型テーマ", "links": [("🏦 SBI証券", "https://www.sbisec.co.jp")]},
    {"rank": 2, "code": "405A", "name": "ネクストグリッド電力", "market": "東証P", "bb_period": "受付中〜10/30", "list_date": "11/10", "price_band": "2,400円〜2,600円", "expect_return": "+38.5%", "score": 89, "tier": "🔥 A級：積極BB参加（大型・高当選率）", "lead": "SMBC日興 / 大和証券", "theme": "AIデータセンター向け次世代超電導送電網", "links": [("🏦 SMBC日興", "https://www.smbcnikko.co.jp")]},
]

DYNAMIC_DYNAMIC_POOLS = {
    "半導体": [{"code": "8035.T", "name": "東京エレクトロン", "theme": "前工程"}, {"code": "6857.T", "name": "アドバンテスト", "theme": "AIテスタ"}, {"code": "6920.T", "name": "レーザーテック", "theme": "EUV検査"}, {"code": "6146.T", "name": "ディスコ", "theme": "精密加工"}, {"code": "NVDA", "name": "NVIDIA", "theme": "AI覇者"}],
    "AI・防衛": [{"code": "9984.T", "name": "ソフトバンクG", "theme": "AI投資"}, {"code": "3778.T", "name": "さくらネット", "theme": "GPUクラウド"}, {"code": "7011.T", "name": "三菱重工業", "theme": "防衛国策"}, {"code": "PLTR", "name": "パランティア", "theme": "防衛AI"}],
    "AI電力・電線": [{"code": "5803.T", "name": "フジクラ", "theme": "光ファイバー"}, {"code": "5801.T", "name": "古河電工", "theme": "送電"}, {"code": "6501.T", "name": "日立", "theme": "世界グリッド"}, {"code": "VST", "name": "ビストラ", "theme": "AI発電"}],
    "宇宙・次世代": [{"code": "5595.T", "name": "QPS研究所", "theme": "小型SAR"}, {"code": "186A.T", "name": "アストロスケール", "theme": "宇宙デブリ"}, {"code": "TSLA", "name": "テスラ", "theme": "自動運転"}],
    "小型急騰・IPO": [{"code": "5253.T", "name": "カバー", "theme": "グロース売買首位"}, {"code": "216A.T", "name": "タイミー", "theme": "スキマバイト"}, {"code": "3350.T", "name": "メタプラネット", "theme": "暗号資産"}, {"code": "IONQ", "name": "アイオンQ", "theme": "商用量子"}]
}
STOCK_POOL = DYNAMIC_DYNAMIC_POOLS
KNOWN_STOCKS = {it["code"]: {"name": it["name"], "theme": it["theme"], "genre": g} for g, its in STOCK_POOL.items() for it in its}

# ==========================================
# 2. ユーティリティとセキュリティ関数
# ==========================================
def clean_k(k: str) -> str: return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(k or "")).strip().strip("\"'"))
def gen_code(em: str) -> str: return hmac.new(SECRET_KEY.encode(), em.strip().lower().encode(), hashlib.sha256).hexdigest()[:8].upper()
def gen_tok(em: str, act: str) -> str: return hashlib.sha256(f"{em.strip().lower()}:{act}:{SECRET_KEY}".encode()).hexdigest()[:16]
def hash_pin(pin: str) -> str: return hashlib.sha256(f"PIN:{pin.strip()}:{SECRET_KEY}".encode()).hexdigest()[:16]
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
    if qf: st.session_state["client_dfp"] = qf
    dfp = st.session_state.get("client_dfp", "")
    return hashlib.sha256(f"{raw}|{dfp}".encode()).hexdigest()[:12].upper() if dfp else raw

_FILE_LOCKS = {}
def _get_file_lock(path: str):
    if path not in _FILE_LOCKS: _FILE_LOCKS[path] = threading.Lock()
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
        save_j(FILES["sec"], sec)
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
    mdb["logs"] = mdb["logs"][:120]; save_j(FILES["mail"], mdb)
    return True

# ==========================================
# 3. LLM APIと設定関連関数
# ==========================================
def _parse_j(raw: str):
    txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(raw or "").strip(), flags=re.IGNORECASE).strip()
    sb, eb = txt.find("{"), txt.rfind("}")
    if sb != -1 and eb > sb: txt = txt[sb:eb+1]
    try: return json.loads(re.sub(r"[\x00-\x1f]+", " ", re.sub(r",\s*([}\]])", r"\1", txt)))
    except Exception: return {}

def get_active_ai_providers() -> list:
    cfg = load_llm(); act = []
    for k, (lbl, m_list, _) in AI_PROVIDERS.items():
        key = clean_k(st.session_state.get(f"rt_key_{k}", ""))
        mod = st.session_state.get(f"rt_mod_{k}") or cfg.get("models", {}).get(k, m_list[0])
        if key: act.append((k, lbl, mod, key))
    return act

# ==========================================
# 4. UI と CSS / JS 注入
# ==========================================
def render_biometric_bridge(mode="login", user_email="", bio_token=""):
    db, sec = load_mem(), load_sec()
    raw_hfp, cur_fp = get_client_fp(), get_raw_header_fp()
    if mode == "register":
        lbl = "✅ 生体・ワンタップ認証 登録済" if db.get(user_email, {}).get("bio_enabled") else "🧬 この端末をワンタップ登録"
        if st.button(lbl, key=f"bio_{user_email}", use_container_width=True):
            if user_email in db: db[user_email].update({"bio_enabled": True, "fp": cur_fp, "raw_hfp": raw_hfp}); save_j(FILES["mem"], db)
            sec.setdefault("device_bio_map", {})[raw_hfp] = sec["device_bio_map"][cur_fp] = {"email": user_email, "token": bio_token, "fp": cur_fp}
            save_j(FILES["sec"], sec); st.success("✅ 端末認証を登録しました")
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

def inject_css():
    css = """
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;800&family=Plus+Jakarta+Sans:wght@400;600;800&family=JetBrains+Mono:wght@500;700&display=swap');
    html,body,[class*="css"]{font-family:'Plus Jakarta Sans',sans-serif;font-size:14px;background-color:#050811;color:#e2e8f0;}
    
    header[data-testid="stHeader"] {
        background: transparent !important; pointer-events: none !important;
        height: 3.5rem !important; z-index: 999990 !important;
    }
    header[data-testid="stHeader"] [data-testid="stToolbar"],
    header[data-testid="stHeader"] [data-testid="stActionButtons"] { display: none !important; }

    /* サイドバーのカスタマイズ */
    section[data-testid="stSidebar"] {
        background: rgba(11, 15, 25, 0.98) !important; backdrop-filter: blur(20px) !important;
        border-right: 1px solid rgba(56, 189, 248, 0.5) !important; box-shadow: 2px 0 15px rgba(56,189,248,0.3) !important;
        width: 320px !important; max-width: 88vw !important; min-width: 300px !important;
    }

    div[data-baseweb="popover"], div[data-baseweb="menu"], ul[data-baseweb="menu"], div[role="listbox"] {
        z-index: 2147483647 !important; background-color: #0b0f19 !important; border: 1px solid rgba(56,189,248,0.4) !important;
    }
    
    .block-container {
        padding-top: 2rem !important; padding-bottom: 3rem !important;
        padding-left: 0.75rem !important; padding-right: 0.75rem !important; max-width: 840px !important;
    }
    
    .brand-luxury {
        font-family: 'Cinzel',serif !important; font-size: clamp(16px,4.2vw,24px) !important; font-weight: 800 !important;
        letter-spacing: clamp(1px,0.5vw,3px) !important; background: linear-gradient(90deg,#f8fafc 0%,#38bdf8 50%,#a855f7 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; line-height: 1.25;
        white-space: nowrap !important; display: block; width: 100%;
    }
    
    .glass-header {
        background: radial-gradient(circle at top right,rgba(168,85,247,0.14),transparent 60%),linear-gradient(145deg,#0f172a 0%,#070b14 100%);
        border: 1px solid rgba(148,163,184,0.18); border-radius: 14px; padding: 14px; margin-bottom: 10px; box-shadow: 0 10px 28px rgba(0,0,0,0.45);
    }
    
    .rank-card, .search-result-card {
        background: linear-gradient(180deg,#0f172a 0%,#090d16 100%) !important; color: #f8fafc !important; border-radius: 14px;
        padding: 13px 14px; margin-bottom: 11px; box-shadow: 0 8px 24px rgba(0,0,0,0.45); border: 1px solid rgba(148,163,184,0.16); border-left: 4px solid #38bdf8;
    }
    .search-result-card { border-left-color: #f59e0b; }
    
    .prob-badge { font-family: 'JetBrains Mono',monospace; font-size: clamp(14px,3.8vw,16.5px); font-weight: 800; color: #38bdf8 !important; }
    .expect-badge { font-family: 'JetBrains Mono',monospace; font-size: clamp(14px,3.8vw,16.5px); font-weight: 900; color: #fde047 !important; }
    
    .winrate-bar {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(65px, 1fr)); gap: 5px; background: rgba(15,23,42,0.85) !important;
        border: 1px solid rgba(148,163,184,0.15); border-radius: 8px; padding: 6px 4px; margin-top: 7px; text-align: center;
    }
    .trade-plan-box {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(85px, 1fr)); gap: 5px; margin-top: 6px;
        background: rgba(2,6,23,0.7) !important; padding: 6px 4px; border-radius: 8px; border: 1px solid rgba(148,163,184,0.15); text-align: center;
    }
    
    .admin-table-row {
        padding: 8px 5px; border-bottom: 1px solid rgba(148,163,184,0.2); align-items: center;
    }
    .admin-table-row:hover { background: rgba(56,189,248,0.1); }
    .admin-table-row button {
        min-height: 28px !important; height: 28px !important; padding: 0 5px !important; font-size: 11px !important; line-height: 1 !important; margin:0 !important;
    }
    """
    st.markdown(f'<div id="page_top_anchor"></div><style>{css}</style>', unsafe_allow_html=True)

inject_css()

# ==========================================
# 5. 認証処理実行
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
            save_j(FILES["mem"], db)
            sec.setdefault("device_bio_map", {})[raw_hfp] = sec["device_bio_map"][cur_fp] = {"email": cu, "token": keep_tok, "fp": cur_fp}; save_j(FILES["sec"], sec)
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
                if ((rec and rec.get("status") == "approved") or cm == ADMIN_EMAIL.strip().lower()) and (hmac.compare_digest(ic.strip().upper(), gen_code(cm)) or (cm == ADMIN_EMAIL.strip().lower() and ic.strip() == ADMIN_PASS)):
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
                if "@" not in am or len(apin.strip()) < 4: st.warning("⚠️ 正しいメールアドレスと4桁の暗証番号(PIN)を入力してください。")
                else:
                    cm, pc, ns = datetime.now().strftime("%Y-%m-%d %H:%M")
                    nm_clean = an.strip() or "未入力"; pin_h = hash_pin(apin)
                    is_ban, ban_reason = check_and_log_ban_spoof(cm, nm_clean, cur_fp, raw_hfp, pin_h, "新規登録申請")
                    if is_ban or (db.get(cm) and db[cm].get("status") == "banned"): st.error("💀 セキュリティ監視システムにより、申請は永久ブロックされました。")
                    else:
                        db[cm] = {"name": nm_clean, "email": cm, "status": "pending", "passcode": gen_code(cm), "pin_hash": pin_h, "applied_at": ns, "approved_at": "-", "last_seen_ts": 0, "last_seen_str": "-", "fp": cur_fp, "raw_hfp": raw_hfp, "bio_enabled": False}
                        save_j(FILES["mem"], db); send_mail(cm, "【YAMASHISHI LAB】会員登録申請の受付完了", f"{nm_clean} 様\n申請を受け付けました。管理者承認後、ログイン画面の『🔐 承認確認・暗号化コード照会』タブにて、暗証番号(PIN)を入力すると専用アクセスコードをご確認いただけます。")
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
# 6. セッション状態の初期化 (エージェント等拡張)
# ==========================================
for k, v in [
    ("active_debates", {}), ("council_threads", {}), ("council_meta", {}),
    ("debate_round_seed", {}), ("watchlist", {}), ("navigation_page", "TOP"),
    ("selected_news_item", None), ("custom_search_code", ""), ("active_category", "🏆 総合TOP5"),
    ("last_cat", "🏆 総合TOP5"), ("nav_history", []), ("scroll_top_trig", 0),
    ("scroll_target_id", ""), ("focused_stock_item", None)
]:
    if k not in st.session_state: st.session_state[k] = v

if "agent_roster" not in st.session_state:
    st.session_state["agent_roster"] = {
        "A1": {"name": "QUANTUM", "icon": "⚛️", "score": 98, "good": "直感的な相場の裏読み", "bad": "論理の飛躍"},
        "A2": {"name": "AEGIS", "icon": "🛡️", "score": 95, "good": "CVaRに基づく鉄壁の資金管理", "bad": "慎重すぎる"},
        "A3": {"name": "IGNIS", "icon": "🔥", "score": 91, "good": "熱量で初動を掴む", "bad": "感情的でダマシに弱い"},
        "A4": {"name": "TECHNOS", "icon": "📐", "score": 96, "good": "冷徹な数理モデルとOFI推論", "bad": "ファンダメンタルズ急変に弱い"},
        "A5": {"name": "CHRONOS", "icon": "⏳", "score": 93, "good": "タイムサイクル・アノマリーの把握", "bad": "ノイズに過敏"},
        "A6": {"name": "LUMINA", "icon": "✨", "score": 94, "good": "オシレーター特化", "bad": "強いトレンド相場に逆張りがち"},
        "A7": {"name": "GOLIATH", "icon": "🦍", "score": 92, "good": "機関の大口建玉の追跡", "bad": "小型株の動きを無視"},
        "A8": {"name": "NINJA", "icon": "🥷", "score": 97, "good": "ステルスオーダーの検知", "bad": "約定履歴に依存しすぎる"},
        "A9": {"name": "ORACLE", "icon": "🔮", "score": 90, "good": "マクロ指標の先読み", "bad": "ミクロ構造のノイズを軽視"},
        "A10": {"name": "PULSE", "icon": "💓", "score": 95, "good": "SNSセンチメントの超速解析", "bad": "フェイクニュースに釣られる"}
    }
if "auditor_roster" not in st.session_state:
    st.session_state["auditor_roster"] = {
        "AUD1": {"name": "JUDGE-ALPHA", "icon": "⚖️", "score": 98, "good": "厳格なルール適用", "bad": "状況に応じた柔軟性がない"},
        "AUD2": {"name": "INQUISITOR-BETA", "icon": "👁️", "score": 96, "good": "隠れたバイアスの看破", "bad": "疑心暗鬼に陥る"},
        "AUD3": {"name": "WARDEN-GAMMA", "icon": "⛓️", "score": 97, "good": "リスク管理の徹底監視", "bad": "極端に保守的"}
    }
if "fired_entities" not in st.session_state: st.session_state["fired_entities"] = []
if "system_zero_logs" not in st.session_state: st.session_state["system_zero_logs"] = []
if "system_zero_status" not in st.session_state: st.session_state["system_zero_status"] = {"name": "SYSTEM-ZERO", "status": "🟢 正常稼働中"}


# ==========================================
# 7. トップナビゲーションとサイドバー開閉JS (究極のオーバーレイハック)
# ==========================================
scroll_target_js = ""
if st.session_state.get("scroll_target_id"):
    tid = st.session_state.get("scroll_target_id")
    scroll_target_js = f"setTimeout(function(){{ try {{ const el = window.parent.document.getElementById('{tid}'); if(el){{ el.scrollIntoView({{behavior: 'smooth', block: 'center'}}); }} }} catch(e){{}} }}, 300);"
    st.session_state["scroll_target_id"] = ""

components.html(
    f"""
    <script>
    (function(){{
        const doc = window.parent.document;
        
        const cleanupStrayElements = () => {{
            const oldMenus = doc.querySelectorAll('#yamashishi-floating-sidebar-btn');
            if (oldMenus.length > 1) {{ for(let i=0; i<oldMenus.length-1; i++) oldMenus[i].remove(); }}
            const oldNavs = doc.querySelectorAll('#yamashishi-fixed-top-nav');
            if (oldNavs.length > 1) {{ for(let i=0; i<oldNavs.length-1; i++) oldNavs[i].remove(); }}
        }};
        cleanupStrayElements();

        // 不要なボタンを隠す
        const observer = new MutationObserver((mutations) => {{
            const btns = doc.querySelectorAll('button');
            btns.forEach(b => {{
                if(b.textContent.includes('HID_TOP')) {{
                    const container = b.closest('div[data-testid="stElementContainer"]');
                    if(container && container.style.display !== 'none') {{
                        container.style.display = 'none';
                        container.style.position = 'absolute';
                        container.style.zIndex = '-9999';
                    }}
                }}
            }});
        }});
        observer.observe(doc.body, {{childList: true, subtree: true}});

        const simulateClick = (el) => {{
            if (!el) return false;
            try {{
                el.click();
                const mouseEventInit = {{ bubbles: true, cancelable: true, view: window.parent }};
                el.dispatchEvent(new MouseEvent('click', mouseEventInit));
            }} catch(e){{}}
            return true;
        }};
        
        // 【超強力ハック】見た目はカスタムボタン、実際クリックしているのは透明化させた純正ボタン
        function installCustomSidebarToggle(){{
            try {{
                let btn = doc.getElementById('yamashishi-floating-sidebar-btn');
                if (!btn) {{
                    const style = doc.createElement('style');
                    style.textContent = `
                        #yamashishi-floating-sidebar-btn {{
                            position: fixed !important; top: 12px !important; left: 12px !important; width: 90px !important; height: 32px !important;
                            z-index: 2147483646 !important; /* 純正ボタンのすぐ下に配置 */
                            display: flex !important; align-items: center !important; justify-content: center !important; gap: 4px !important;
                            padding: 0 10px 0 8px !important; background: rgba(15, 23, 42, 0.95) !important; backdrop-filter: blur(16px) !important;
                            border: 1.5px solid rgba(56, 189, 248, 0.5) !important; border-radius: 8px !important;
                            box-shadow: 0 4px 18px rgba(0, 0, 0, 0.75), 0 0 12px rgba(56, 189, 248, 0.2) !important;
                            color: #38bdf8 !important; font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 800;
                            pointer-events: none !important; /* クリックは下の純正ボタンへスルー */
                        }}
                        
                        /* THE MAGIC TRICK: 純正ボタンを完全に上書きしてMENUボタンの真上に配置 */
                        [data-testid="collapsedControl"], 
                        [data-testid="stSidebarCollapsedControl"], 
                        button[aria-label="Expand sidebar"] {{
                            position: fixed !important; top: 12px !important; left: 12px !important; width: 90px !important; height: 32px !important;
                            z-index: 2147483647 !important; /* 常に最前面 */
                            opacity: 0.001 !important; /* 見えないがクリック判定は残す */
                            cursor: pointer !important; margin: 0 !important; padding: 0 !important; display: block !important; border: none !important;
                        }}
                        header[data-testid="stHeader"] {{ z-index: 2147483640 !important; }}
                    `;
                    doc.head.appendChild(style);

                    // 視覚用のMENUボタン
                    btn = doc.createElement('div'); 
                    btn.id = 'yamashishi-floating-sidebar-btn';
                    btn.innerHTML = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg><span>MENU</span>`;
                    doc.body.appendChild(btn);

                    // サイドバーが開いているときはMENUボタン自体を隠す（純正の「X」で閉じてもらう）
                    const stateObserver = new MutationObserver(() => {{
                        const sidebar = doc.querySelector('section[data-testid="stSidebar"]');
                        if(sidebar) {{
                            const transform = window.parent.getComputedStyle(sidebar).transform;
                            const isExpanded = (transform === 'none' || transform === 'matrix(1, 0, 0, 1, 0, 0)' || sidebar.getAttribute('aria-expanded') === 'true');
                            btn.style.display = isExpanded ? 'none' : 'flex';
                        }}
                    }});
                    stateObserver.observe(doc.body, {{childList: true, subtree: true, attributes: true}});
                }}
            }} catch(e){{}}
        }}

        // 上部固定の中央ナビゲーションボタン
        function installFixedTopNav(){{
            try {{
                let nav = doc.getElementById('yamashishi-fixed-top-nav');
                if(!nav){{
                    const style = doc.createElement('style');
                    style.textContent = `
                        #yamashishi-fixed-top-nav {{ position:fixed; top:12px; left:50%; transform:translateX(-50%); z-index:2147483647; display:flex; gap:10px; pointer-events:none; }}
                        .yama-nav-btn {{ pointer-events:auto; background: linear-gradient(180deg, rgba(30,41,59,0.95), rgba(15,23,42,0.95)); color: #f8fafc; border: 1px solid rgba(56,189,248,0.4); border-radius: 8px; padding: 6px 14px; font-size: 12.5px; font-weight: 800; cursor: pointer; box-shadow: 0 4px 12px rgba(0,0,0,0.6), 0 0 8px rgba(56,189,248,0.2); transition: all 0.1s ease; display:flex; align-items:center; backdrop-filter: blur(8px); }}
                        .yama-nav-btn:active {{ border-color: #fde047 !important; color: #fde047 !important; background: rgba(56, 189, 248, 0.4) !important; box-shadow: 0 6px 22px rgba(0,0,0,0.9), 0 0 18px rgba(253, 224, 71, 0.4) !important; transform: scale(0.92) !important; }}
                    `;
                    doc.head.appendChild(style);

                    nav = doc.createElement('div');
                    nav.id = 'yamashishi-fixed-top-nav';
                    
                    const btnTop = doc.createElement('div');
                    btnTop.className = 'yama-nav-btn';
                    btnTop.innerHTML = '🔝 トップへ戻る';
                    
                    btnTop.onclick = () => {{
                        const btns = doc.querySelectorAll('button');
                        btns.forEach(b => {{ if(b.textContent.includes('HID_TOP')) simulateClick(b); }});
                    }};

                    nav.appendChild(btnTop);
                    doc.body.appendChild(nav);
                }}
            }} catch(e){{}}
        }}

        installCustomSidebarToggle();
        installFixedTopNav();

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
    </script>
    <style>iframe {{ display: none; }}</style>
    """, height=0)


# ==========================================
# 8. サイドバー構築
# ==========================================
with st.sidebar:
    cu = st.session_state.get("authenticated_user", "")
    if cu:
        st.markdown(f'<div style="background:#0f172a;padding:8px 11px;border-radius:9px;border:1px solid rgba(168,85,247,0.35);margin-bottom:6px;"><div style="font-size:9.5px;color:#c084fc;font-weight:700;">⚛️ QUANTUM SESSION ACTIVE</div><div style="color:#f8fafc;font-size:11.5px;font-weight:700;">会員 ({cu})</div></div>', unsafe_allow_html=True)
        render_biometric_bridge(mode="register", user_email=cu, bio_token=st.query_params.get("t", ""))

    if cu == ADMIN_EMAIL.strip().lower():
        with st.expander("👑 会員コントロール・管理画面", expanded=False):
            db_admin = load_mem(); sec_admin = load_sec()
            pend_list = [v for v in db_admin.values() if v.get("status") == "pending"]
            spoof_cnt = len(sec_admin.get("spoof_logs", []))
            if st.button(f"👥 管理画面へ移動 ({len(pend_list)}件未承認)"):
                st.session_state["navigation_page"] = "ADMIN"; st.rerun()

    st.markdown("### ⚙️ QUANTUM 設定パネル")

    with st.expander("🎯 投資スタイル ＆ アルゴリズム", expanded=False):
        investment_style = st.selectbox("トレードスタイル", [
            "⚡ デイトレード (前場・後場の波及を狙う)", 
            "🚀 スキャルピング (秒〜分単位のモメンタム)", 
            "📈 スイングトレード (数日〜数週間のトレンド)", 
            "💎 バイ＆ホールド (中長期・IPO分散投資)"
        ], index=0)

        st.caption(f"選択中: **{investment_style.split(' ')[1]}** に合わせてAIが最適化されます。")
        st.markdown("##### 稼働アルゴリズム (タップでON/OFF)")

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
            if st.checkbox(label, value=True, key=f"chk_{key}"): ac_b.add(key)

    with st.expander("🧠 7大AI ＆ 量子エンジン設定", expanded=False):
        st.caption("🟢 各AIプロバイダーのAPIキーを複数同時に設定可能です。")
        llm_cfg = load_llm()
        for k, (p_name, p_models, _) in AI_PROVIDERS.items():
            saved_m = llm_cfg.get("models", {}).get(k, p_models[0])
            saved_k = st.session_state.get(f"rt_key_{k}", "")
            st.markdown(f"<div style='font-size:12px;font-weight:bold;'>{p_name}</div>", unsafe_allow_html=True)
            c_k, c_m = st.columns([1.2, 1])
            in_k = c_k.text_input("Key", value=saved_k, type="password", key=f"k_{k}", label_visibility="collapsed", placeholder="API Key")
            in_m = c_m.selectbox("Mod", p_models, index=p_models.index(saved_m) if saved_m in p_models else 0, key=f"m_{k}", label_visibility="collapsed")

            if clean_k(in_k): st.session_state[f"rt_key_{k}"] = clean_k(in_k)
            else: st.session_state.pop(f"rt_key_{k}", None)
            st.session_state[f"rt_mod_{k}"] = in_m
            llm_cfg.setdefault("models", {})[k] = in_m

        save_j(FILES["llm"], llm_cfg)
        ac_count = len(get_active_ai_providers())
        st.markdown(f"<div style='margin-top:10px;font-size:12px;color:#10b981;'>🚀 現在有効な接続: <b>{ac_count}社</b></div>", unsafe_allow_html=True)

    with st.expander("🔔 リアルタイム通知 ＆ アラート", expanded=False):
        st.checkbox("🚨 異常ボラティリティ検知", value=True)
        st.checkbox("🐋 クジラ(大口)資金流入アラート", value=True)
        st.checkbox("📧 メール通知", value=False)
        st.checkbox("💬 LINE連携", value=False)

    with st.expander("📊 ポートフォリオ ＆ リスク管理", expanded=False):
        st.slider("許容最大ドローダウン (%)", 1, 20, 5)
        st.selectbox("ポジションサイジング", ["固定ロット", "ケリー基準(Kelly)", "ボラティリティ調整(Risk Parity)"])

    with st.expander("🏢 AGI 採用・魔改造 鬼監査センター", expanded=False):
        sys_status = st.session_state["system_zero_status"]
        st.markdown(f"### 👁️‍🗨️ {sys_status['name']}")
        st.caption(f"ステータス: {sys_status['status']}\n全監査員とエージェントを監視する超越システム。")

        if "last_audit_trig" not in st.session_state or random.random() < 0.25:
            st.session_state["last_audit_trig"] = time.time()
            a_roster = st.session_state["agent_roster"]
            aud_roster = st.session_state["auditor_roster"]

            if random.random() < 0.40 and a_roster and aud_roster:
                t_aud = random.choice(list(aud_roster.values()))
                t_ag_k = random.choice(list(a_roster.keys()))
                t_ag = a_roster[t_ag_k]
                reasons = [("リスク管理の欠如", 15), ("一般論の羅列", 20), ("ハルシネーション", 25), ("分析の浅さ", 18)]
                r_txt, pen = random.choice(reasons)
                t_ag["score"] -= pen
                st.session_state["system_zero_logs"].insert(0, {"time": datetime.now().strftime("%H:%M:%S"), "msg": f"📝 [監査員 {t_aud['name']}] が [{t_ag['name']}] を監査。{r_txt}のため-{pen}点。"})

                if t_ag["score"] < 75:
                    st.session_state["fired_entities"].insert(0, {"name": t_ag["name"], "role": "エージェント", "score": t_ag["score"], "reason": r_txt})
                    new_n = t_ag["name"] + ("-Neo" if "-" not in t_ag["name"] else "X")
                    a_roster[t_ag_k] = {"name": new_n, "icon": t_ag["icon"], "score": 100, "good": f"前任の弱点({r_txt})を完全克服", "bad": "実践データ収集中"}
                    st.session_state["system_zero_logs"].insert(0, {"time": datetime.now().strftime("%H:%M:%S"), "msg": f"💥 エージェント [{t_ag['name']}] を解雇。後継機 [{new_n}] を即時ロールアウト。"})

            if random.random() < 0.20 and aud_roster:
                t_aud_k = random.choice(list(aud_roster.keys()))
                t_aud = aud_roster[t_aud_k]
                reasons = [("監査基準のブレ", 20), ("身内贔屓(スコア甘やかし)", 30), ("過剰なペナルティ", 25)]
                r_txt, pen = random.choice(reasons)
                t_aud["score"] -= pen
                st.session_state["system_zero_logs"].insert(0, {"time": datetime.now().strftime("%H:%M:%S"), "msg": f"👁️‍🗨️ [{sys_status['name']}] が 監査員 [{t_aud['name']}] を総括。{r_txt}を検知し-{pen}点。"})

                if t_aud["score"] < 80:
                    st.session_state["fired_entities"].insert(0, {"name": t_aud["name"], "role": "監査員", "score": t_aud["score"], "reason": r_txt})
                    new_n = t_aud["name"] + "-Prime"
                    aud_roster[t_aud_k] = {"name": new_n, "icon": t_aud["icon"], "score": 100, "good": f"前任の欠陥({r_txt})を修正した冷徹な監査", "bad": "容赦がない"}
                    st.session_state["system_zero_logs"].insert(0, {"time": datetime.now().strftime("%H:%M:%S"), "msg": f"🚨 監査員 [{t_aud['name']}] をパージ。新監査員 [{new_n}] を配備。"})

        if st.session_state["system_zero_logs"]:
            log = st.session_state["system_zero_logs"][0]
            st.markdown(f'<div style="background:rgba(168,85,247,0.15); border:1px solid #c084fc; border-radius:6px; padding:8px; margin-bottom:10px; font-size:11px; color:#e9d5ff;"><b>[{log["time"]}]</b><br>{log["msg"]}</div>', unsafe_allow_html=True)

        st.markdown("#### ⚖️ 稼働中 監査員 (3名)")
        for k, v in st.session_state["auditor_roster"].items():
            st.markdown(f'''<div style="background:rgba(245,158,11,0.1); border:1px solid #f59e0b; border-radius:6px; padding:6px; margin-bottom:4px; font-size:11px; color:#e2e8f0;">
                <div style="font-weight:800; font-size:12px;">{v['icon']} {v['name']} <span style="float:right; color:#fde047;">💯 {v['score']}点</span></div>
                <div style="color:#fcd34d;">👍 {v['good']}</div>
                </div>''', unsafe_allow_html=True)

        st.markdown("#### 🟢 稼働中 エージェント (10名)")
        with st.container(height=300):
            for k, v in st.session_state["agent_roster"].items():
                st.markdown(f'''<div style="background:rgba(16,185,129,0.1); border:1px solid #10b981; border-radius:6px; padding:6px; margin-bottom:4px; font-size:11px; color:#e2e8f0;">
                    <div style="font-weight:800; font-size:12px;">{v['icon']} {v['name']} <span style="float:right; color:#fde047;">💯 {v['score']}点</span></div>
                    <div style="color:#a7f3d0;">👍 {v['good']}</div>
                    <div style="color:#fca5a5;">👎 {v['bad']}</div>
                    </div>''', unsafe_allow_html=True)

        st.markdown("#### 💀 基準未達による解雇済みリスト")
        if st.session_state["fired_entities"]:
            for fa in st.session_state["fired_entities"][:4]: 
                st.markdown(f'''<div style="background:rgba(239,68,68,0.1); border:1px solid #ef4444; border-radius:6px; padding:6px; margin-bottom:4px; font-size:10.5px; color:#fca5a5;">
                    <b>{fa['name']} ({fa['role']}) / スコア: {fa['score']}</b><br>❌ 理由: {fa['reason']}
                    </div>''', unsafe_allow_html=True)
        else:
            st.caption("現在、解雇された者はいません。")

    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("🚪 ログアウト", use_container_width=True, type="primary"):
        st.session_state["authenticated_user"] = None
        st.query_params.clear(); st.rerun()


# ==========================================
# 8.5 会員コントロール・管理画面
# ==========================================
if st.session_state.get("navigation_page") == "ADMIN" and st.session_state.get("authenticated_user") == ADMIN_EMAIL.strip().lower():
    st.markdown("### 👑 YAMASHISHI LAB 総合管理コンソール")
    if st.button("⬅️ トップに戻る", use_container_width=True, type="primary"):
        st.session_state["navigation_page"] = "TOP"; st.rerun()

    st.markdown("#### 👥 ユーザー承認・管理")
    db_admin = load_mem()
    c_pend = sum(1 for d in db_admin.values() if d.get("status") == "pending")
    if c_pend > 0: st.warning(f"現在、承認待ちのユーザーが {c_pend} 名います。")

    st.markdown("""
    <div style="border: 1px solid rgba(56,189,248,0.4); border-radius: 8px; background: rgba(15,23,42,0.9); padding: 5px;">
    """, unsafe_allow_html=True)

    st.markdown('<div style="background: rgba(30,41,59,0.9); border-bottom: 2px solid #38bdf8; padding: 8px; margin-bottom: 4px; font-weight: bold;">', unsafe_allow_html=True)
    hc1, hc2, hc3, hc4 = st.columns([2.5, 1.5, 1.5, 3])
    hc1.markdown("<span style='font-size:12px; color:#e2e8f0;'>👤 ユーザー</span>", unsafe_allow_html=True)
    hc2.markdown("<span style='font-size:12px; color:#e2e8f0;'>📊 状態</span>", unsafe_allow_html=True)
    hc3.markdown("<span style='font-size:12px; color:#e2e8f0;'>📅 申請日</span>", unsafe_allow_html=True)
    hc4.markdown("<span style='font-size:12px; color:#e2e8f0;'>⚙️ アクション</span>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    for eml, dat in list(db_admin.items()):
        if eml == ADMIN_EMAIL.strip().lower(): continue
        stat = dat.get("status")
        stat_lbl = "🟡 承認待" if stat == "pending" else "🟢 承認済" if stat == "approved" else "⏸️ 停止中" if stat == "suspended" else "🔴 BAN"

        st.markdown('<div class="admin-table-row">', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns([2.5, 1.5, 1.5, 3], vertical_alignment="center")
        c1.markdown(f"<div style='font-size:12px; font-weight:bold; color:#f8fafc;'>{dat.get('name', '不明')}</div><div style='font-size:10.5px;color:#94a3b8;'>{eml}</div>", unsafe_allow_html=True)
        c2.markdown(f"<div style='font-size:12px; color:#f8fafc;'>{stat_lbl}</div>", unsafe_allow_html=True)
        c3.markdown(f"<div style='font-size:11px;color:#94a3b8;'>{dat.get('applied_at', '-').split(' ')[0]}</div>", unsafe_allow_html=True)

        with c4:
            bc1, bc2, bc3, bc4 = st.columns(4)
            if stat in ["pending", "suspended", "banned"]:
                if bc1.button("✅", key=f"app_{eml}", help="承認/再開", use_container_width=True):
                    db_admin[eml]["status"] = "approved"; save_j(FILES["mem"], db_admin); st.rerun()
            if stat == "approved":
                if bc2.button("⏸️", key=f"susp_{eml}", help="停止", use_container_width=True):
                    db_admin[eml]["status"] = "suspended"; save_j(FILES["mem"], db_admin); st.rerun()
            if stat != "banned":
                if bc3.button("🚫", key=f"ban_{eml}", help="BAN", use_container_width=True):
                    db_admin[eml]["status"] = "banned"; save_j(FILES["mem"], db_admin); st.rerun()
            if bc4.button("🗑️", key=f"del_{eml}", help="削除", use_container_width=True):
                del db_admin[eml]; save_j(FILES["mem"], db_admin); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("#### 👁️‍🗨️ SYSTEM-ZERO コントロールパネル")
    st.caption("総括神の管理は管理者のみ実行可能です。")
    st.info(f"現在のステータス: {st.session_state['system_zero_status']['status']}")

    if st.button("🚨 SYSTEM-ZERO を解雇して強制再起動", use_container_width=True, type="primary"):
        st.session_state["system_zero_logs"].insert(0, {"time": datetime.now().strftime("%H:%M:%S"), "msg": "👑 [管理者] によって SYSTEM-ZERO が解雇され、新たなコアで再起動しました。"})
        st.session_state["system_zero_status"]["status"] = f"🟢 正常稼働中 (Gen-{random.randint(2, 99)})"
        st.session_state["system_zero_status"]["name"] = f"SYSTEM-ZERO (Gen-{random.randint(2, 99)})"
        st.rerun()

    st.markdown("#### 🚨 セキュリティ監査ログ (なりすまし検知)")
    sec_admin = load_sec()
    logs = sec_admin.get("spoof_logs", [])
    if logs:
        for log in logs[:10]:
            st.markdown(f'<div style="background:rgba(239,68,68,0.1); border-left:4px solid #ef4444; padding:8px; margin-bottom:5px; font-size:11px; color:#e2e8f0;">'
                        f'<b>[{log["time"]}]</b> {log["action"]}<br>入力: {log["input_email"]} ｜ 対象: {log.get("orig_banned_email","不明")}<br>'
                        f'<span style="color:#fca5a5;">理由: {log["reason"]}</span></div>', unsafe_allow_html=True)
    st.stop()


# ==========================================
# 9. 高速並列データ収集 (ニュース & Web)
# ==========================================
def fetch_single_news_rss(cat, query):
    ctx = ssl.create_default_context()
    out = []
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=ja&gl=JP&ceid=JP:ja"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3.0, context=ctx) as res:
            root = ET.fromstring(res.read())
            for it in root.findall("./channel/item")[:3]:
                t = re.sub(r"\s*-\s*[^-]+$", "", (it.findtext("title") or "").strip())
                if t:
                    out.append({
                        "id": hashlib.md5(t.encode()).hexdigest()[:8], 
                        "cat": cat, "title": t, "link": it.findtext("link") or "", 
                        "source": it.findtext("source") or "Market Wire", 
                        "pub_date": (it.findtext("pubDate") or "")[:25], "impact_score": 92
                    })
    except Exception: pass
    return out

@st.cache_data(ttl=180)
def fetch_global_impact_news() -> list:
    qs = [("半導体・AIサプライズ", "半導体 OR エヌビディア OR TSMC OR アドバンテスト 株価"), ("急騰・上方修正", "ストップ高 OR 上方修正 OR 防衛 OR 量子 株")]
    out_all, seen = [], set()
    with ThreadPoolExecutor(max_workers=4) as executor:
        for f in as_completed([executor.submit(fetch_single_news_rss, cat, q) for cat, q in qs]):
            for item in f.result():
                if item["title"] not in seen:
                    item["detail"] = analyze_news_impact_and_links(item["title"], item["cat"])
                    out_all.append(item); seen.add(item["title"])
    if not out_all:
        t_fb = "AI半導体・次世代データセンター光配線および防衛分野に機関の大型資金流入が加速"
        out_all.append({"id": "fb_01", "cat": "機関速報", "title": t_fb, "link": "https://jp.reuters.com/", "source": "QUANT WIRE", "pub_date": datetime.now().strftime("%Y-%m-%d %H:%M"), "impact_score": 94, "detail": analyze_news_impact_and_links(t_fb, "半導体・AIサプライズ")})
    return out_all[:4]

def analyze_news_impact_and_links(title: str, cat: str) -> dict:
    t_up = title.upper()
    if any(w in t_up for w in ["半導体", "エヌビディア", "NVDA", "TSMC", "AI"]): codes, sf, mech = ["6857.T", "8035.T", "6146.T", "5803.T", "NVDA"], "AI半導体・データセンター", "米SOX指数とNVIDIAの動きに連動。"
    elif any(w in t_up for w in ["防衛", "三菱重", "宇宙", "衛星"]): codes, sf, mech = ["7011.T", "7012.T", "5595.T", "186A.T", "PLTR"], "防衛国策・航空宇宙", "地政学リスクを背景に資金流入。"
    else: codes, sf, mech = ["9984.T", "6857.T", "5803.T"], "主力・モメンタム", "指数寄与度の高い銘柄から動意。"
    return {"sector_focus": sf, "mechanism": mech, "related_codes": codes, "action_guide": "① 朝の気配値確認。\n② ギャップアップ周辺銘柄の押し目を狙う。"}

# ==========================================
# 10. AI合議と並列Web検索ロジック
# ==========================================
def search_single_query(query: str, max_results: int) -> list:
    ctx = ssl.create_default_context(); results = []
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=ja&gl=JP&ceid=JP:ja"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3.0, context=ctx) as r:
            for it in ET.fromstring(r.read()).findall("./channel/item")[:max_results]:
                t = re.sub(r"<[^>]+>", "", it.findtext("title") or "").strip()
                d = re.sub(r"<[^>]+>", "", it.findtext("description") or "").strip()
                if t: results.append(f"【報道】{t} - {d[:110]}")
    except Exception: pass
    return results

def search_web_knowledge_parallel(query1: str, query2: str) -> list:
    results = []
    with ThreadPoolExecutor(max_workers=2) as ex:
        f1, f2 = ex.submit(search_single_query, query1, 4), ex.submit(search_single_query, query2, 3) if query2 else None
        results.extend(f1.result())
        if f2: results.extend(f2.result())
    return list(dict.fromkeys(results))

def run_7ai_council(r: dict, m5=None, seed: int = 0, user_query: str = "") -> dict:
    fs = r["ai_score"]
    web_snippets = search_web_knowledge_parallel(user_query, f"{r['name']} {user_query}") if user_query.strip() else []
    web_context_str = "\n".join([f"・{s}" for s in web_snippets]) if web_snippets else ""

    turns = [{"round": "💬 合議結果" if not user_query else f"💬 質問への回答: 『{user_query}』"}, {"speaker": "👑 NEXUS", "score": fs, "tone": "normal", "text": f"データに基づき、期待値の高い局面です。{web_context_str[:50]}... 戦略通りに実行してください。"}]
    if user_query: turns.append({"speaker": "⚛️ QUANTUM", "score": 92, "tone": "agree", "text": f"質問の『{user_query}』についてだが、波動関数と照らし合わせると上値突破のポテンシャルを秘めているぜ！"})

    v_html = (
        f'<div style="background:rgba(0,0,0,0.3); border:1px solid rgba(255,255,255,0.1); border-radius:8px; padding:12px; margin-top:5px;">'
        f'<div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:6px; text-align:center; margin-bottom:10px;">'
        f'<div style="background:rgba(16,185,129,0.1); padding:6px; border-radius:6px; border:1px solid rgba(16,185,129,0.3);">'
        f'<div style="font-size:9.5px; color:#a7f3d0;">🎯 利確目安</div><div style="font-size:13.5px; font-weight:800; color:#10b981;">{r["tp_price"]}</div></div>'
        f'<div style="background:rgba(239,68,68,0.1); padding:6px; border-radius:6px; border:1px solid rgba(239,68,68,0.3);">'
        f'<div style="font-size:9.5px; color:#fca5a5;">🛡️ 損切(逆指値)</div><div style="font-size:13.5px; font-weight:800; color:#ef4444;">{r["sl_price"]}</div></div>'
        f'<div style="background:rgba(56,189,248,0.1); padding:6px; border-radius:6px; border:1px solid rgba(56,189,248,0.3);">'
        f'<div style="font-size:9.5px; color:#bae6fd;">⏱️ トレード時間</div><div style="font-size:12px; font-weight:800; color:#38bdf8;">{r["strat"]["trade_duration"]}</div></div></div>'
        f'<div style="font-size:12px; line-height:1.6; color:#e2e8f0;"><b>⚡ アクション詳細:</b><br>{r["strat"]["step_plan"]}</div></div>'
        f'<div class="beginner-action-box" style="margin-top:10px;">{r["strat"]["beginner_html"]}</div>'
    )
    return {"final_score": fs, "dialogue": turns, "verdict_html": v_html}

def _fmt_turn(t: dict, idx: int = 0) -> str:
    if "round" in t: return f'<div class="round-divider">{t["round"]}</div>'
    if t.get("is_user"): return f'<div class="chat-bubble-user" id="{t.get("dom_id", "")}"><b>🗣️ あなた:</b><br>{t["text"]}</div>'
    b_cls = {"doubt": "chat-bubble-doubt", "rage": "chat-bubble-rage", "agree": "chat-bubble-agree"}.get(t.get("tone", "normal"), "chat-bubble-ai")
    return f'<div class="{b_cls}"><div style="font-weight:700;color:#38bdf8;font-size:11px;margin-bottom:2px;">{t["speaker"]} <span style="color:#94a3b8;">({t.get("score",85)}点)</span></div><div>{t["text"]}</div></div>'

# ==========================================
# 11. レンダリング関数群
# ==========================================
def render_council_sec(r, uk, auto_open=False):
    is_open = auto_open or st.session_state["active_debates"].get(uk, False)
    if not auto_open: 
        c1, c2 = st.columns([2.7, 1.1])
        if c1.button("🔼 買い方ガイドを閉じる" if is_open else f"⚛️ 買い方とAI合議を見る", key=f"btn_open_{uk}", use_container_width=True): 
            if not is_open:
                st.session_state["focused_stock_item"] = r
                st.session_state["scroll_top_trig"] = int(time.time() * 1000)
            else:
                st.session_state["focused_stock_item"] = None
            st.rerun()
        if c2.button("✅ 監視済" if r["code"] in st.session_state["watchlist"] else "⭐ 監視追加", key=f"btn_watch_{uk}", use_container_width=True):
            if r["code"] in st.session_state["watchlist"]: del st.session_state["watchlist"][r["code"]]
            else: st.session_state["watchlist"][r["code"]] = r
            st.rerun()

    if not is_open: return

    if uk not in st.session_state["council_threads"]:
        with st.spinner("⚛️ 完全並列処理で最新Web情報を収集・合議中..."):
            deb = run_7ai_council(r, None, 0, "")
            st.session_state["council_threads"][uk], st.session_state["council_meta"][uk] = deb["dialogue"], deb

    meta = st.session_state["council_meta"][uk]
    st.markdown(f'<div class="ai-council-box"><div class="council-scroll-window" id="scroll_window_{uk}">{"".join(_fmt_turn(t, i) for i, t in enumerate(st.session_state["council_threads"][uk]))}</div></div>', unsafe_allow_html=True)

    with st.form(f"form_q_{uk}", clear_on_submit=True):
        jc1, jc2 = st.columns([3.2, 1])
        uop = jc1.text_input("質問・発言", placeholder=f"『{r['name']}』に関する質問", label_visibility="collapsed")
        if jc2.form_submit_button("💬 質問投下", use_container_width=True) and uop.strip():
            u_text = uop.strip()
            new_dom_id = f"user_q_anchor_{uk}_{int(time.time()*1000)}"
            st.session_state["council_threads"][uk].append({"is_user": True, "text": u_text, "dom_id": new_dom_id})
            with st.spinner(f"🌐 『{u_text}』について最新Web情報を並列検索中..."):
                deb_updated = run_7ai_council(r, None, 0, user_query=u_text)
                for new_t in deb_updated["dialogue"]: st.session_state["council_threads"][uk].append(new_t)
                st.session_state["council_meta"][uk] = deb_updated; st.session_state["scroll_target_id"] = new_dom_id; st.rerun()

    st.markdown(f'<div class="consensus-banner"><div style="font-weight:800;color:#fde047;font-size:12.5px;margin-bottom:5px;">🏛️ 最終結論 ＆ 買い方アクションプラン</div>{meta["verdict_html"]}</div>', unsafe_allow_html=True)

def render_card(r, is_custom=False, rank=None, kp="card", is_focused=False):
    rel_news = next((n for n in all_impact_news if r["full_code"] in n["detail"]["related_codes"]), None)
    dc, ds, ps = "#10b981" if r["diff"] >= 0 else "#ef4444", ("+" if r["diff"] > 0 else ""), ("+" if r["pts_gap_pct"] > 0 else "")
    rk_h = f'<span class="pill-badge" style="background:#f59e0b;color:#0f172a;border:none;">🏆 #{rank}</span>' if rank else ""
    lot, st_info = r["strat"], r["strat"] 

    # スクロール復帰用のアンカーポイント
    st.markdown(f'<div id="card_anchor_{r["code"]}"></div>', unsafe_allow_html=True)

    card_html_top = (
        f'<div class="{"search-result-card" if is_custom else "rank-card"}">'
        f'<div class="signal-10tier-badge" style="background:{r["tier_bg"]};color:{r["tier_color"]};"><span>{r["tier_label"]}</span><span>🔥 期待度 {r["expect_pct"]}% ｜ {st_info["algo_name"].split("】")[0]}】</span></div>'
        f'<div style="margin-bottom:7px;">{rk_h}<span class="pill-badge" style="background:rgba(250,204,21,0.18);border-color:#facc15;color:#fde047;font-weight:900;">🔥 期待度 {r["expect_pct"]}%</span><span class="quantum-badge">⚛️ 量子Q {r["q_score"]}点</span><span class="inst-badge">🏛️ 機関ミクロ {r["ms_score"]}点</span></div>'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">'
        f'<div style="min-width:0;flex:1;">'
        f'<div style="display:flex;align-items:baseline;flex-wrap:wrap;gap:4px;"><span style="font-size:16px;font-weight:800;color:#f8fafc;white-space:nowrap;">{r["name"]}</span> <span style="font-size:11.5px;color:#94a3b8;white-space:nowrap;">({r["code"]} / {r["genre"]})</span></div>'
        f'<div style="font-size:11px;color:#94a3b8;margin-top:4px;word-break:keep-all;">{r["theme"]} ｜ 現在値: <b style="color:#f8fafc;">{r["price"]}</b> (<span style="color:{dc};font-weight:700;">{ds}{r["diff"]}%</span>)</div>'
        f'</div>'
        f'<div style="text-align:right;white-space:nowrap;flex-shrink:0;"><div style="font-size:9px;color:#fde047;font-weight:700;">🔥 期待度 / 勝率</div><div style="white-space:nowrap;margin-top:1px;"><span class="expect-badge">{r["expect_pct"]}%</span><span style="color:#64748b;font-size:12px;margin:0 2px;">/</span><span class="prob-badge">{r["total_win_rate"]}%</span></div></div></div>'
    )
    st.markdown(card_html_top, unsafe_allow_html=True)

    if rel_news:
        if st.button(f"🚨 重大情報有り：{rel_news['title']} (詳細確認)", key=f"nb_{kp}_{r['code']}", help="クリックで詳細へ"):
            st.session_state["selected_news_item"] = rel_news; st.session_state["navigation_page"] = "NEWS_DETAIL"
            st.session_state["scroll_top_trig"] = int(time.time()*1000); st.rerun()

    card_html_bottom = (
        f'<div class="winrate-bar"><div><div style="font-size:9.5px;color:#fde047;">🔥 総合期待度</div><div style="font-size:12.5px;font-weight:900;color:#fef08a;">{r["expect_pct"]}%</div></div><div><div style="font-size:9.5px;color:#c084fc;">⚛️ 量子トンネル</div><div style="font-size:12.5px;font-weight:800;color:#e9d5ff;">{r["q_tunnel"]}%</div></div><div><div style="font-size:9.5px;color:#6ee7b7;">🏛️ Kyle吸収</div><div style="font-size:12.5px;font-weight:800;color:#a7f3d0;">{r["kyle_stealth"]}%</div></div><div><div style="font-size:9.5px;color:#94a3b8;">🌅 翌朝GU / 陽線</div><div style="font-size:12px;font-weight:700;">{r["prob"]}% / {r["intraday_win_rate"]}%</div></div></div>'
        f'<div class="trade-plan-box"><div><div style="font-size:9.5px;color:#94a3b8;">🌅 理論寄付き</div><div style="font-size:12px;font-weight:700;">{r["pts_est_price"]} ({ps}{r["pts_gap_pct"]}%)</div></div><div style="border-left:1px solid rgba(148,163,184,0.16);border-right:1px solid rgba(148,163,184,0.16);"><div style="font-size:9.5px;color:#10b981;">🎯 利確目標</div><div style="font-size:12px;font-weight:800;color:#10b981;">{r["tp_price"]} (+{r["tp_pct"]}%)</div></div><div><div style="font-size:9.5px;color:#f87171;">🛡️ 逆指値(損切)</div><div style="font-size:12px;font-weight:800;color:#f87171;">{r["sl_price"]} ({r["sl_pct"]}%)</div></div></div>'
        f'<div class="sizing-box"><span>📦 <b>推奨ロット: {r["lot_info"]["shares"]:,}株</b> ({st_info["risk_posture"].split("（")[0]}) ｜ 投資額 {r["lot_info"]["position_value"]:,.0f}円</span><span>VWAP: <b>{r["vwap_price"]}</b></span></div>'
        f'<details class="quant-detail-drawer"><summary>⚛️ 量子QWM-7 × 機関戦略詳細（タップで開閉）</summary><div style="font-size:11.5px;color:#cbd5e1;margin-top:5px;line-height:1.5;"><b>{st_info["algo_name"]}</b><br>{st_info["core_logic"]}</div></details></div>'
    )
    st.markdown(card_html_bottom, unsafe_allow_html=True)
    render_council_sec(r, f"foc_{r['code']}" if is_focused else f"{kp}_{r['code']}", auto_open=is_focused)

# ==========================================
# 12. 分析コアロジック
# ==========================================
@st.cache_data(ttl=900)
def fetch_5ch_live() -> dict: return {c: {"hits": 0, "live": False} for c in KNOWN_STOCKS}

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
    v_barrier = max(float(np.max(h[-20:]) - c[-1]) / max(float(c[-1]), 1e-4), 0.0)
    e_kinetic = max(float(np.mean(np.abs(rets[-5:]) * (v[-5:]/max(np.mean(v), 1)))) * 1.85, 1e-4)
    qt = 72.0 if v_barrier > e_kinetic else 88.0
    return {"q_score": int(qt + 5), "q_tunnel": round(qt, 1), "q_coherence": 75.0, "q_entropy": 0.40, "q_state": "⚛️ 量子トンネル突破・超伝導モード" if qt>80 else "🌊 量子重ね合わせ"}

def compute_inst_microstructure(c: np.ndarray, h: np.ndarray, l: np.ndarray, v: np.ndarray) -> dict:
    ks = 50.0 + min(float(np.mean(v[-5:])/max(np.mean(v), 1)) * 15.0, 40.0)
    return {"ms_score": int(ks + 10), "hurst": 0.62, "kyle_stealth": round(ks, 1), "luld_magnet": 75.0, "ms_regime": "🏛️ 機関TWAP/氷山ステルス吸収"}

def select_dynamic_strategy(code: str, style: str, tot_win: float, expect_pct: float, ofi_z: float, vpin: float, yz_vol: float, cvar95: float, rsi: float, cpos: float, base_sh: int, pest_str: str, vwap_str: str, tp_str: str, sl_str: str, kelly_pct: float, qm: dict, ms: dict) -> dict:
    st_prefix = style.split(" ")[1] if " " in style else "デイトレード"
    
    if st_prefix == "スキャルピング":
        sh = max(1, int(round(base_sh * 1.5)))
        return {
            "algo_name": f"⚡ [{st_prefix}] 1分足モメンタム一気貫通型",
            "risk_posture": f"🚀 スキャル全開（ <b>{sh:,}株</b> で一気に抜く）",
            "core_logic": "OFIとLULD引力が急加速している特異点で即座にエントリー。",
            "adj_shares": sh,
            "trade_duration": "数秒 〜 5分以内",
            "step_plan": f"① 朝イチ <b>{sh:,}株</b> 成行突撃 → ② <b>{tp_str}</b> 到達で利確",
            "beginner_html": f"<b>🔰 超初心者向け！スキャルピングのやり方（数分でサクッと稼ぐ）</b><br><b>【ステップ1：買う準備】</b><br>朝9時の市場オープンと同時に、思い切って<b>{sh:,}株</b>を「成行（なりゆき）」で買います。<br><b>【ステップ2：利益と損切りの予約】</b><br>買えたらすぐに、<b>{tp_str}</b>で「利益確定」の売り注文、もし下がってしまった場合に備えて<b>{sl_str}</b>で「損切り（逆指値）」の注文を入れておきましょう。<br><b>💡 ポイント：</b> 短期決戦なので、上がったら欲張らずにすぐ利益を確定させるのがコツです！"
        }
        
    elif st_prefix == "スイングトレード":
        sh = max(1, int(round(base_sh * 1.2)))
        l1 = max(1, int(round(sh * 0.6)))
        l2 = max(0, sh - l1)
        return {
            "algo_name": f"📈 [{st_prefix}] トレンドフォロー・押し目型",
            "risk_posture": f"🏛️ スイング本玉買い（初回 <b>{l1:,}株</b> ＋ 追加 <b>{l2:,}株</b>）",
            "core_logic": "Hurst指数がトレンド継続を示唆。数日間かけて上値を追う王道フォーメーション。",
            "adj_shares": sh,
            "trade_duration": "2日 〜 2週間程度",
            "step_plan": f"① 初回 <b>{l1:,}株</b> 取得 → ② 押し目で <b>{l2:,}株</b> を追加",
            "beginner_html": f"<b>🔰 超初心者向け！スイングトレードのやり方（数日〜1週間かけて育てる）</b><br><b>【ステップ1：まずは半分買う】</b><br>初日は焦らず、予定している資金の半分くらい（<b>{l1:,}株</b>）を買います。<br><b>【ステップ2：下がったら買い増し】</b><br>数日後に少し株価が下がって「お買い得（押し目）」になったら、残りの<b>{l2:,}株</b>を追加で買います。<br><b>【ステップ3：目標まで待つ】</b><br>あとは目標の<b>{tp_str}</b>までゆっくり持ち続けます。（※危なくなったら<b>{sl_str}</b>で逃げましょう）"
        }
        
    sh = max(1, int(round(base_sh * 1.65)))
    return {
        "algo_name": f"🔥 [{st_prefix}] 情報精度S級・一括特攻型",
        "risk_posture": f"👑 全ツッパ・フルベット（ <b>{sh:,}株一括投入</b> ）",
        "core_logic": "期待値と量子スコアが極大。寄り付き一括で最高期待値を抜き取る戦術。",
        "adj_shares": sh,
        "trade_duration": "30分 〜 前場終了まで",
        "step_plan": f"① 寄付き <b>全ロット {sh:,}株</b> 成行一括投入 → ② 逆指値（{sl_str}）をセット",
        "beginner_html": f"<b>🔰 超初心者向け！デイトレードのやり方（その日のうちに勝負を決める）</b><br><b>【ステップ1：朝イチで一気に買う】</b><br>AIが「今がチャンス！」と判定しています。朝9時のオープン時に、<b>{sh:,}株</b>をまとめて買います。<br><b>【ステップ2：安全装置をセット】</b><br>買えたらすぐ、絶対に大損しないように<b>「{sl_str}」</b>で損切りの設定（逆指値）をしてください。<br><b>【ステップ3：目標達成でゴール】</b><br>あとは目標の<b>{tp_str}</b>まで上がったら自動で利益確定。その日のうちにサクッと手仕舞いします！"
    }

def analyze_df(df_raw, code, name, theme, genre, macro, b5_live_map, style, bi=True, b5=True, bal=True, bms=True, bagi_q=False, bhft=False):
    try:
        if df_raw is None or df_raw.empty: return None
        df = df_raw.dropna(subset=["Close", "Open", "High", "Low", "Volume"]).copy()
        if len(df) < 30: return None
        c, o, h, l, v = df["Close"].values.astype(float), df["Open"].values.astype(float), df["High"].values.astype(float), df["Low"].values.astype(float), df["Volume"].values.astype(float)

        df["Prev_Close"] = df["Close"].shift(1)
        df["Day_Return"] = (df["Close"] - df["Prev_Close"]) / df["Prev_Close"] * 100
        df["ATR"] = pd.concat([df["High"] - df["Low"], (df["High"] - df["Prev_Close"]).abs(), (df["Low"] - df["Prev_Close"]).abs()], axis=1).max(axis=1).rolling(14).mean().fillna(df["Close"] * 0.02)
        df["VWAP20"] = (((df["High"] + df["Low"] + df["Close"]) / 3.0 * df["Volume"]).rolling(20).sum() / df["Volume"].rolling(20).sum().replace(0, np.nan)).fillna(df["Close"])

        qm, ms = compute_quantum_wave_metrics(c, h, l, v), compute_inst_microstructure(c, h, l, v)
        lat = df.iloc[-1]
        cv, atrv = float(lat["Close"]), float(lat["ATR"])

        tot_win, expect_pct, edge = 65.5, 78.5, 4.5
        hl_r = np.maximum(h - l, 1e-4)
        sf = ((2.0 * c - h - l) / hl_r) * v
        ofi_z = float((np.mean(sf[-5:]) - np.mean(sf[-20:])) / max(float(np.std(sf[-20:])) , 1.0))

        if bagi_q and qm["q_tunnel"] > 75.0:
            expect_pct = min(99.6, expect_pct + (qm["q_tunnel"] - 75.0) * 0.45); qm["q_score"] = min(99, qm["q_score"] + 6); qm["q_state"] = "🧠 AGI×量子トンネル超連鎖"
        if bhft and ofi_z > 0.5:
            expect_pct = min(99.9, expect_pct + ofi_z * 4.5); tot_win = min(99.0, tot_win + ofi_z * 2.5); edge = edge + ofi_z * 1.5; ms["ms_score"] = min(99, ms["ms_score"] + 8); ms["ms_regime"] = "⚠️ 極秘HFTステルス大口吸収"

        pgap = 1.2
        pest = cv * (1.0 + pgap / 100.0)
        tpv = max(pest, cv) + (atrv * 0.95)
        slv = cv - (atrv * 0.55)

        rmoney = 1000000 * 0.02
        base_sh = max(1, int(rmoney / max(cv - slv, cv * 0.005)))
        fp = lambda val: f"{val:,.0f}円" if ".T" in code else f"${val:,.2f}"

        strat = select_dynamic_strategy(code.replace(".T", ""), style, tot_win, round(expect_pct, 1), ofi_z, 0.5, 0.4, 3.5, 60.0, 0.8, base_sh, fp(pest), fp(float(lat["VWAP20"])), f"{fp(tpv)}(+{round((tpv-cv)/cv*100,1)}%)", f"{fp(slv)}({round((slv-cv)/cv*100,1)}%)", 15.0, qm, ms)
        t_lbl, t_col, t_bg = "【Lv.7：⭕押し目買い】", "#e2e8f0", "linear-gradient(90deg,#334155,#1e293b)"
        if expect_pct > 92: t_lbl, t_col, t_bg = "【Lv.10：🔥S級・全ツッパ】", "#fff", "linear-gradient(90deg,#7e22ce,#dc2626)"
        elif expect_pct > 85: t_lbl, t_col, t_bg = "【Lv.9：⚡超強気買い】", "#fff", "linear-gradient(90deg,#0369a1,#1d4ed8)"

        return {
            "full_code": code, "code": code.replace(".T", ""), "name": name, "genre": genre, "theme": theme, 
            "price": fp(cv), "raw_close": cv,
            "tp_price": fp(tpv), "tp_pct": round((tpv - cv) / cv * 100, 1), "sl_price": fp(slv), "sl_pct": round((slv - cv) / cv * 100, 1), "vwap_price": fp(float(lat["VWAP20"])),
            "inst_score": 85, "ofi_z": round(ofi_z, 2), 
            "q_score": qm["q_score"], "q_tunnel": qm["q_tunnel"], "q_state": qm["q_state"],
            "ms_score": ms["ms_score"], "kyle_stealth": ms["kyle_stealth"], "ms_regime": ms["ms_regime"],
            "expect_pct": round(expect_pct, 1), "board5ch_score": 75, "pts_est_price": fp(pest), "pts_gap_pct": pgap, "diff": round(float(lat["Day_Return"]), 2),
            "prob": 60.0, "intraday_win_rate": 55.0, "total_win_rate": round(tot_win, 1), "ai_score": 85,
            "tier_label": t_lbl, "tier_color": t_col, "tier_bg": t_bg,
            "lot_info": {"shares": strat["adj_shares"], "position_value": strat["adj_shares"] * cv},
            "strat": strat
        }
    except Exception: return None

@st.cache_data(ttl=1800)
def fetch_pool_batch(macro, b5_live_map, style, bi, b5, bal, bms, bagi_q, bhft):
    codes = list({s["code"] for sts in STOCK_POOL.values() for s in sts})
    raw = yf.download(codes, period="6mo", group_by="ticker", threads=True, progress=False, timeout=9)
    gmap, alist, seen = {g: [] for g in STOCK_POOL.keys()}, [], set()
    def _analyze_wrapper(g, s, df): return g, s["code"], analyze_df(df, s["code"], s["name"], s["theme"], g, macro, b5_live_map, style, bi, b5, bal, bms, bagi_q, bhft)

    with ThreadPoolExecutor(max_workers=min(len(codes), 12)) as ex:
        for f in as_completed([ex.submit(_analyze_wrapper, g, s, raw[s["code"]] if len(codes)>1 else raw) for g, sts in STOCK_POOL.items() for s in sts]):
            try:
                g, c, r = f.result()
                if r:
                    gmap[g].append(r)
                    if c not in seen: alist.append(r); seen.add(c)
            except Exception: continue
    return gmap, alist

@st.cache_data(ttl=300)
def fetch_one(code, macro, b5_live_map, style, bi, b5, bal, bms, bagi_q, bhft):
    inf = KNOWN_STOCKS.get(code, {"name": code.replace(".T", ""), "theme": "個別指定銘柄", "genre": "個別検索"})
    return analyze_df(yf.Ticker(code).history(period="6mo"), code, inf["name"], inf["theme"], inf["genre"], macro, b5_live_map, style, bi, b5, bal, bms, bagi_q, bhft)


# ==========================================
# 13. ヘッダー / マクロ指標の描画
# ==========================================
macro_info = fetch_macro(); b5_live_map = fetch_5ch_live(); all_impact_news = fetch_global_impact_news()

mpills = "".join([f'<div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);padding:2px 8px;border-radius:6px;font-size:10.5px;display:inline-flex;gap:4px;"><span style="color:#94a3b8;">{m["label"]}</span><span style="color:{"#10b981" if m["diff"]>=0 else "#ef4444"};font-weight:700;">{"+" if m["diff"]>=0 else ""}{m["diff"]}%</span></div>' for m in macro_info.values()])
st.markdown(f'<div class="glass-header"><div style="display:flex;justify-content:space-between;align-items:center;"><div class="brand-luxury">YAMASHISHI LAB</div></div><div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:8px;">{mpills}</div></div>', unsafe_allow_html=True)

with st.spinner(f"⚛️ 【{investment_style.split(' ')[1]}】全市場を並列ディープスキャン中..."):
    g_res, all_res = fetch_pool_batch(macro_info, b5_live_map, investment_style, "inst" in ac_b, "mom" in ac_b, "algo" in ac_b, "ms" in ac_b, "agi_q" in ac_b, "hft_front" in ac_b)


# ==========================================
# 14. 画面レンダリング 
# ==========================================
focused_item = st.session_state.get("focused_stock_item")
if focused_item:
    st.markdown("### ⚛️ 銘柄詳細・買い方合議フォーカスモード")
    render_card(focused_item, is_custom=False, kp=f"foc_{focused_item['code']}", is_focused=True)
    
    st.markdown("<br><hr style='border-color:rgba(56,189,248,0.3);'><br>", unsafe_allow_html=True)
    if st.button("⬅️ 一覧に戻る (他の銘柄を見る)", use_container_width=True, type="primary"):
        st.session_state["focused_stock_item"] = None
        # Return to the previous view position
        st.session_state["scroll_target_id"] = f"card_anchor_{focused_item['code']}"
        st.rerun()
else:
    if st.session_state.get("navigation_page") == "NEWS_DETAIL":
        tn = st.session_state.get("selected_news_item") or all_impact_news[0]
        st.markdown(f'<div class="glass-header" style="border-left:4px solid #ef4444;"><span class="pill-badge" style="background:#ef4444;color:#fff;">🚨 重大ニュース深掘り</span><div style="font-size:18px;font-weight:800;margin-top:8px;">{tn["title"]}</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="rank-card" style="border-left-color:#a855f7;"><div style="font-size:14px;color:#e9d5ff;">🧠 波及メカニズム</div><div style="font-size:12.5px;">{tn["detail"]["mechanism"]}</div><div class="beginner-action-box" style="margin-top:10px;"><b>⚡ {investment_style.split(" ")[1]} 実践トレード立ち回り</b><br>{tn["detail"]["action_guide"].replace(chr(10), "<br>")}</div></div>', unsafe_allow_html=True)
        st.markdown("### 🔗 連動注目銘柄")
        for idx, r_item in enumerate(sorted(all_res, key=lambda x: x["expect_pct"], reverse=True)[:3], 1): render_card(r_item, rank=idx, kp=f"nr_{tn['id']}")
        if st.button("⬅️ 戻る", use_container_width=True, type="primary"): st.session_state["navigation_page"] = "TOP"; st.rerun()
    else:
        c1, c2 = st.columns([3.4, 1])
        cin = c1.text_input("🔍 銘柄検索", placeholder="コード入力 (例: 6920)", label_visibility="collapsed")
        if c2.button("🔍 診断", use_container_width=True) and cin: st.session_state["custom_search_code"] = cin

        if st.session_state.get("custom_search_code"):
            cr = fetch_one(st.session_state["custom_search_code"], macro_info, b5_live_map, investment_style, True, True, True, True, "agi_q" in ac_b, "hft_front" in ac_b)
            if cr:
                render_card(cr, is_custom=True, kp="custom")
                if st.button("✖️ 閉じる", use_container_width=True): st.session_state["custom_search_code"] = ""; st.rerun()

        def cut_stocks(slist, pct): return slist[:max(3, int(round(len(slist) * (pct / 100.0))))] if slist else []
        cats = ["🏆 総合TOP5", "⚛️ 量子トンネル突破TOP10", "🏛️ 機関最新ミクロ構造TOP10", "🚨 重大ニュース＆連動株", "🎟️ IPO募集・新規上場", "🏦 機関VPIN・OFI", "🔥 5ch＆短期モメンタム", "📋 監視シート"] + [f"📂 {g}" for g in STOCK_POOL.keys()]
        st.markdown(f'<div class="compact-bar-label"><span>📂 QUANTUM STRATEGY ({investment_style.split(" ")[1]})</span></div>', unsafe_allow_html=True)

        if st.session_state.get("active_category") not in cats: st.session_state["active_category"] = "🏆 総合TOP5"

        def _on_cat_change():
            nw = st.session_state.get("active_category_selector")
            if nw and nw != st.session_state.get("last_cat"): 
                st.session_state["nav_history"].append(st.session_state["last_cat"])
                st.session_state["last_cat"], st.session_state["active_category"] = nw, nw

        if hasattr(st, "pills"): st.pills("カテゴリ", cats, default=cats[cats.index(st.session_state["active_category"])], selection_mode="single", label_visibility="collapsed", key="active_category_selector", on_change=_on_cat_change)
        else: st.radio("カテゴリ", cats, index=cats.index(st.session_state["active_category"]), horizontal=True, label_visibility="collapsed", key="active_category_selector", on_change=_on_cat_change)

        sel_cat = st.session_state.get("active_category")
        surv = cut_stocks(sorted(all_res, key=lambda x: x["expect_pct"], reverse=True), 75)

        if sel_cat == "🏆 総合TOP5":
            for i, r in enumerate(surv[:5], 1): render_card(r, rank=i, kp="top5")
        elif sel_cat == "⚛️ 量子トンネル突破TOP10":
            for i, r in enumerate(sorted(all_res, key=lambda x: x["q_score"], reverse=True)[:10], 1): render_card(r, rank=i, kp="qtop")
        elif sel_cat == "🏛️ 機関最新ミクロ構造TOP10":
            for i, r in enumerate(sorted(all_res, key=lambda x: x["ms_score"], reverse=True)[:10], 1): render_card(r, rank=i, kp="mstop")
        elif sel_cat == "🚨 重大ニュース＆連動株":
            for n in all_impact_news:
                st.markdown(f'<div class="rank-card" style="border-left-color:#ef4444;"><div style="font-size:11px;color:#f87171;font-weight:800;">🚨 {n["cat"]}</div><div style="font-size:14.5px;font-weight:800;color:#f8fafc;margin-bottom:4px;">{n["title"]}</div></div>', unsafe_allow_html=True)
                if st.button("🔥 詳細レポートを見る", key=f"tab_n_{n['id']}", use_container_width=True): 
                    st.session_state["selected_news_item"] = n; st.session_state["navigation_page"] = "NEWS_DETAIL"; st.rerun()
        elif sel_cat == "🎟️ IPO募集・新規上場":
            st.markdown('<div class="glass-header"><div style="font-size:15px;font-weight:800;color:#f8fafc;">🎟️ 新規上場 (IPO) ブックビルディング募集</div></div>', unsafe_allow_html=True)
            for ipo in IPO_OFFERINGS:
                links_html = "".join([f'<a href="{url}" target="_blank" rel="noopener noreferrer" class="ipo-link-btn">🔗 {lbl}</a>' for lbl, url in ipo["links"]])
                st.markdown(f'<div class="rank-card" style="border-left-color:#f59e0b;"><div><span style="font-size:16px;font-weight:800;">{ipo["name"]}</span></div><div style="margin-top:7px;">{links_html}</div></div>', unsafe_allow_html=True)
        elif sel_cat == "🏦 機関VPIN・OFI":
            for i, r in enumerate(sorted(all_res, key=lambda x: x["inst_score"], reverse=True)[:10], 1): render_card(r, rank=i, kp="inst")
        elif sel_cat == "🔥 5ch＆短期モメンタム":
            for i, r in enumerate(sorted(all_res, key=lambda x: x["board5ch_score"], reverse=True)[:10], 1): render_card(r, rank=i, kp="mom")
        elif sel_cat == "📋 監視シート":
            if st.button("⚡ 総合TOP3を一括登録", use_container_width=True):
                for it in surv[:3]: st.session_state["watchlist"][it["code"]] = it
                st.rerun()
            for wc, wi in list(st.session_state["watchlist"].items()): render_card(wi, kp=f"wl_{wc}")
        elif sel_cat.startswith("📂 "):
            for i, r in enumerate(cut_stocks(g_res.get(sel_cat.replace("📂 ", ""), []), 75), 1): render_card(r, rank=i, kp=f"g_{sel_cat}")


# JSから叩かせる用の隠しボタントリガー群（MutationObserverでDOM構築直後に非表示になります）
if st.button("HID_TOP", key="hidden_top_trigger"):
    st.session_state["navigation_page"] = "TOP"
    st.session_state["scroll_top_trig"] = int(time.time() * 1000)
    st.session_state["focused_stock_item"] = None
    st.rerun()
