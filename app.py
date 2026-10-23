import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np
import altair as alt
import unicodedata, hashlib, hmac, json, os, re, ssl, smtplib, time
import urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.mime.text import MIMEText
from datetime import datetime

st.set_page_config(page_title="YAMASHISHI LAB", page_icon="⚡", layout="centered")
frag_dec = getattr(st, "fragment", getattr(st, "experimental_fragment", lambda f: f))

ADMIN_EMAIL = "nthbh399@ybb.ne.jp"
SECRET_KEY = "my_super_secret_quant_key_2026"
FILES = {"mem": "members_db.json", "smtp": "admin_smtp_config.json", "llm": "admin_llm_config.json", "sec": "security_watch_db.json", "mail": "mail_history_db.json"}
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

IPO_OFFERINGS = [
    {"rank": 1, "code": "401A", "name": "AIクロスロボティクス", "market": "東証G", "bb_period": "受付中〜10/28", "list_date": "11/06", "price_band": "1,680円〜1,850円", "expect_return": "+92.0%", "score": 96, "tier": "🌟 S級：全力BB参加（初値2倍濃厚）", "lead": "SBI証券 / 野村證券", "theme": "自律型AIドローン・防衛省関連の超大型テーマ", "links": [("🏦 SBI証券 BB申込", "https://www.sbisec.co.jp/ETGate/?_ControlID=WPLETmgR001Control&_DataStoreID=DSWPLETmgR001Control&burl=search_ipo&cat1=ipo&cat2=none&dir=ipo&file=stock_info_ipo.html"), ("📊 96ut初値予想", "https://96ut.com/ipo/"), ("📄 JPX新規上場", "https://www.jpx.co.jp/listing/stocks/new/index.html")]},
    {"rank": 2, "code": "405A", "name": "ネクストグリッド電力", "market": "東証P", "bb_period": "受付中〜10/30", "list_date": "11/10", "price_band": "2,400円〜2,600円", "expect_return": "+38.5%", "score": 89, "tier": "🔥 A級：積極BB参加（大型・高当選率）", "lead": "SMBC日興 / 大和証券", "theme": "AIデータセンター向け次世代超電導送電網", "links": [("🏦 SMBC日興 IPO", "https://www.smbcnikko.co.jp/products/stock/ipo/index.html"), ("🏦 大和証券 IPO", "https://www.daiwa.jp/products/equity/ipo/"), ("📈 やさしいIPO", "https://www.ipokiso.com/company/schedule.html")]},
    {"rank": 3, "code": "412A", "name": "クオンタム・セキュア", "market": "東証G", "bb_period": "11/01〜11/07", "list_date": "11/17", "price_band": "1,150円〜1,280円", "expect_return": "+65.0%", "score": 86, "tier": "🔥 A級：積極BB参加（小型吸収・需給良好）", "lead": "楽天証券 / マネックス", "theme": "量子暗号通信・金融機関向けゼロトラスト防衛", "links": [("🏦 楽天証券 IPO", "https://www.rakuten-sec.co.jp/web/domestic/ipo/"), ("🏦 マネックス IPO", "https://info.monex.co.jp/ipo/index.html"), ("📊 庶民のIPO", "https://ipokabu.net/")]},
    {"rank": 4, "code": "418A", "name": "スペースデブリ・ソリューション", "market": "東証G", "bb_period": "11/05〜11/12", "list_date": "11/21", "price_band": "880円〜960円", "expect_return": "+28.0%", "score": 78, "tier": "⭕ B級：余裕資金でBB参加（宇宙国策）", "lead": "松井証券 / SBI証券", "theme": "衛星軌道レーザー除去・JAXA連携ベンチャー", "links": [("🏦 松井証券(前受金不要)", "https://www.matsui.co.jp/service/ipo/"), ("🏦 SBI証券 BB申込", "https://www.sbisec.co.jp/ETGate/?_ControlID=WPLETmgR001Control&_DataStoreID=DSWPLETmgR001Control&burl=search_ipo&cat1=ipo&cat2=none&dir=ipo&file=stock_info_ipo.html"), ("📄 東京IPO", "https://www.tokyoipo.com/ipo/schedule.php")]},
    {"rank": 5, "code": "422A", "name": "グローバルリテールDX", "market": "東証S", "bb_period": "11/08〜11/14", "list_date": "11/25", "price_band": "1,400円〜1,500円", "expect_return": "+11.0%", "score": 68, "tier": "👀 C級：公募割れ警戒・セカンダリー狙い", "lead": "野村證券 / みずほ証券", "theme": "無人レジ・流通サプライチェーン最適化SaaS", "links": [("🏦 野村證券 IPO", "https://www.nomura.co.jp/retail/stock/ipo/"), ("🏦 みずほ証券 IPO", "https://www.mizuho-sc.com/product/stock/ipo/index.html"), ("📊 みんかぶIPO", "https://minkabu.jp/ipo")]}
]

def clean_k(k: str) -> str: return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(k or "")).strip().strip("\"'"))
def gen_code(em: str) -> str: return hmac.new(SECRET_KEY.encode(), em.strip().lower().encode(), hashlib.sha256).hexdigest()[:8].upper()
def gen_tok(em: str, act: str) -> str: return hashlib.sha256(f"{em.strip().lower()}:{act}:{SECRET_KEY}".encode()).hexdigest()[:16]
def hash_pin(pin: str) -> str: return hashlib.sha256(f"PIN:{pin.strip()}:{SECRET_KEY}".encode()).hexdigest()[:16]

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

def load_j(p: str, d: dict) -> dict:
    r = dict(d)
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f: r.update(json.load(f))
        except Exception: pass
    return r

def save_j(p: str, d: dict):
    try:
        with open(p, "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception: pass

def load_smtp(): return load_j(FILES["smtp"], {"smtp_user": ADMIN_EMAIL, "smtp_pass": "", "smtp_server": "smtp.mail.yahoo.co.jp", "smtp_port": 465})
def load_llm(): return load_j(FILES["llm"], {"provider": "gemini", "api_keys": {}, "models": {k: v[1][0] for k, v in AI_PROVIDERS.items()}})
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
    if em_c == ADMIN_EMAIL.strip().lower():
        return False, ""
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
            with (smtplib.SMTP_SSL(srv, port, timeout=3.0) if port == 465 else smtplib.SMTP(srv, port, timeout=3.0)) as s:
                if port != 465: s.starttls()
                s.login(u, p); s.send_message(m)
            sent, route = True, "SMTP配信＋暗号化BOX"
        except Exception: pass
    if not sent:
        try:
            ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
            payload = json.dumps({"_subject": subj, "宛先": to_clean, "本文": body, "_captcha": "false"}).encode("utf-8")
            req = urllib.request.Request(f"https://formsubmit.co/ajax/{urllib.parse.quote(to_clean)}", data=payload, headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=3.0, context=ctx) as r:
                if r.status == 200: route = "Webリレー配信＋暗号化BOX"
        except Exception: pass
    mdb = load_mail_db()
    mdb.setdefault("logs", []).insert(0, {"id": hashlib.md5(f"{to_clean}_{now_str}".encode()).hexdigest()[:8], "time": now_str, "to": to_clean, "from": ADMIN_EMAIL, "subject": subj, "body": body, "category": category, "route": route})
    mdb["logs"] = mdb["logs"][:120]; save_j(FILES["mail"], mdb)
    return True

def render_biometric_bridge(mode="login", user_email="", bio_token=""):
    db, sec = load_mem(), load_sec()
    raw_hfp, cur_fp = get_raw_header_fp(), get_client_fp()
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
            if is_ban or u_rec.get("status") == "banned":
                st.error("💀 このアカウントまたは端末は永久BAN（アクセス禁止）されています。")
            elif u_rec.get("status") == "suspended": st.error("🚫 アカウント一時停止中です。")
            elif (cur_fp in sec.get("banned_fps", {}) or raw_hfp in sec.get("banned_fps", {})) and t_em != ADMIN_EMAIL.strip().lower(): st.error("🚫 端末制限中です。")
            elif (u_rec and u_rec.get("status") == "approved") or t_em == ADMIN_EMAIL.strip().lower():
                st.session_state["authenticated_user"] = t_em; st.query_params["u"], st.query_params["t"] = t_em, gen_tok(t_em, "session_keep"); st.rerun()
        else:
            is_ban, _ = check_and_log_ban_spoof("", "未認証端末", cur_fp, raw_hfp, "", "ワンタップ試行")
            if is_ban:
                st.error("💀 この端末は永久BAN（アクセス禁止）されています。")
            else:
                st.warning("⚠️ 初回は下のフォームから専用コードでログインしてください（次回から自動登録されます）。")

def inject_css():
    css = """
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;800&family=Plus+Jakarta+Sans:wght@400;600;800&family=JetBrains+Mono:wght@500;700&display=swap');
    html,body,[class*="css"]{font-family:'Plus Jakarta Sans',sans-serif;font-size:14px;background-color:#050811;color:#e2e8f0;}
    header[data-testid="stHeader"]{background:transparent!important;pointer-events:none!important;}
    header[data-testid="stHeader"] button,header[data-testid="stHeader"] a,header[data-testid="stHeader"] [data-testid="stToolbar"],[data-testid="collapsedControl"],[data-testid="stSidebarCollapsedControl"]{pointer-events:auto!important;}
    .block-container{padding-top:3.6rem!important;padding-bottom:3rem!important;padding-left:0.75rem!important;padding-right:0.75rem!important;max-width:840px!important;}
    .brand-luxury{font-family:'Cinzel',serif!important;font-size:clamp(16px,4.2vw,24px)!important;font-weight:800!important;letter-spacing:clamp(1px,0.5vw,3px)!important;background:linear-gradient(90deg,#f8fafc 0%,#38bdf8 50%,#a855f7 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1.25;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;display:block;width:100%;}
    .brand-sub{font-family:'JetBrains Mono',monospace;font-size:clamp(8.5px,2.2vw,10.5px);color:#64748b;letter-spacing:1.2px;text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
    div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stElementContainer"] div.top-nav-marker),
    div[data-testid="stVerticalBlock"] > div:has(> div.element-container div.top-nav-marker),
    div[data-testid="stVerticalBlockBorderWrapper"]:has(div.top-nav-marker),
    div[data-testid="stVerticalBlock"]:has(> div > div.top-nav-marker),
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] div.top-nav-marker),
    .fixed-top-nav-bar{position:fixed!important;top:0.45rem!important;left:50%!important;transform:translateX(-50%)!important;z-index:1000020!important;width:min(680px,calc(100vw - 7.2rem))!important;background:rgba(5,8,17,0.92)!important;backdrop-filter:blur(12px)!important;border:none!important;border-radius:9px!important;outline:none!important;box-shadow:0 6px 18px rgba(0,0,0,0.65)!important;padding:4px 6px!important;margin:0!important;pointer-events:auto!important;}
    div[data-testid="stElementContainer"]:has(div.top-nav-marker),
    div.element-container:has(div.top-nav-marker){display:none!important;height:0!important;margin:0!important;padding:0!important;border:none!important;}
    div:has(> div > div.top-nav-marker) div[data-testid="stHorizontalBlock"],
    .fixed-top-nav-bar div[data-testid="stHorizontalBlock"]{display:flex!important;flex-direction:row!important;flex-wrap:nowrap!important;align-items:center!important;gap:5px!important;width:100%!important;border:none!important;background:transparent!important;box-shadow:none!important;}
    div:has(> div > div.top-nav-marker) div[data-testid="column"],
    div:has(> div > div.top-nav-marker) div[data-testid="stColumn"],
    .fixed-top-nav-bar div[data-testid="column"],
    .fixed-top-nav-bar div[data-testid="stColumn"]{min-width:0!important;flex:1 1 0%!important;padding:0!important;border:none!important;background:transparent!important;}
    div:has(> div > div.top-nav-marker) div[data-testid="column"]:nth-child(2),
    div:has(> div > div.top-nav-marker) div[data-testid="stColumn"]:nth-child(2),
    .fixed-top-nav-bar div[data-testid="column"]:nth-child(2),
    .fixed-top-nav-bar div[data-testid="stColumn"]:nth-child(2){flex:1.45 1 0%!important;}
    div:has(> div > div.top-nav-marker) button,
    .fixed-top-nav-bar button{width:100%!important;min-width:0!important;height:28px!important;min-height:28px!important;max-height:28px!important;padding:0 4px!important;margin:0!important;border-radius:7px!important;background:rgba(15,23,42,0.92)!important;backdrop-filter:blur(10px)!important;color:#f8fafc!important;border:1px solid rgba(56,189,248,0.25)!important;box-shadow:0 4px 12px rgba(0,0,0,0.45)!important;}
    div:has(> div > div.top-nav-marker) button:hover,
    .fixed-top-nav-bar button:hover{border-color:#38bdf8!important;color:#38bdf8!important;}
    div:has(> div > div.top-nav-marker) button p,
    .fixed-top-nav-bar button p{font-size:clamp(10px,2.6vw,11.5px)!important;font-weight:700!important;margin:0!important;padding:0!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;line-height:1!important;}
    div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stElementContainer"] div.floating-news-popup-marker),
    div[data-testid="stVerticalBlock"] > div:has(> div.element-container div.floating-news-popup-marker){position:fixed!important;bottom:16px!important;right:16px!important;z-index:99999!important;width:min(395px,93vw)!important;background:rgba(12,18,34,0.97)!important;backdrop-filter:blur(18px)!important;border:1px solid rgba(239,68,68,0.65)!important;border-left:4px solid #ef4444!important;border-radius:12px!important;padding:11px 13px!important;box-shadow:0 16px 38px rgba(0,0,0,0.85)!important;}
    div[data-testid="stVerticalBlock"] > div:has(div.floating-news-popup-marker) div[data-testid="stElementContainer"]:has(div.floating-news-popup-marker),
    div[data-testid="stVerticalBlock"] > div:has(div.floating-news-popup-marker) div.element-container:has(div.floating-news-popup-marker){display:none!important;height:0!important;margin:0!important;padding:0!important;}
    .glass-header{background:radial-gradient(circle at top right,rgba(168,85,247,0.14),transparent 60%),linear-gradient(145deg,#0f172a 0%,#070b14 100%);border:1px solid rgba(148,163,184,0.18);border-radius:14px;padding:14px 14px;margin-bottom:10px;box-shadow:0 10px 28px rgba(0,0,0,0.45);box-sizing:border-box;width:100%;overflow:hidden;}
    .compact-bar-label{display:flex;justify-content:space-between;font-size:10.5px;font-weight:700;letter-spacing:0.8px;color:#94a3b8;background:#0f172a;padding:5px 11px;border-radius:7px;border-left:3px solid #a855f7;margin-bottom:5px;}
    .rank-card,.search-result-card{background:linear-gradient(180deg,#0f172a 0%,#090d16 100%)!important;color:#f8fafc!important;border-radius:14px;padding:13px 14px;margin-bottom:11px;box-shadow:0 8px 24px rgba(0,0,0,0.45);border:1px solid rgba(148,163,184,0.16);border-left:4px solid #38bdf8;}
    .search-result-card{border-left-color:#f59e0b;}
    .prob-badge{font-family:'JetBrains Mono',monospace;font-size:clamp(14px,3.8vw,16.5px);font-weight:800;color:#38bdf8!important;white-space:nowrap;}
    .expect-badge{font-family:'JetBrains Mono',monospace;font-size:clamp(14px,3.8vw,16.5px);font-weight:900;color:#fde047!important;white-space:nowrap;}
    .pill-badge{display:inline-block;padding:2px 7px;border-radius:6px;font-size:10px;font-weight:700;margin-right:4px;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);color:#e2e8f0;}
    .quantum-badge{display:inline-block;padding:2px 8px;border-radius:6px;font-size:10px;font-weight:800;margin-right:4px;background:linear-gradient(90deg,rgba(168,85,247,0.22),rgba(56,189,248,0.22));border:1px solid rgba(168,85,247,0.55);color:#e9d5ff;}
    .inst-badge{display:inline-block;padding:2px 8px;border-radius:6px;font-size:10px;font-weight:800;margin-right:4px;background:linear-gradient(90deg,rgba(16,185,129,0.2),rgba(56,189,248,0.2));border:1px solid rgba(16,185,129,0.55);color:#a7f3d0;}
    .winrate-bar{display:grid;grid-template-columns:repeat(4,1fr);gap:5px;background:rgba(15,23,42,0.85)!important;border:1px solid rgba(148,163,184,0.15);border-radius:8px;padding:6px 4px;margin-top:7px;text-align:center;}
    .signal-10tier-badge{display:flex;justify-content:space-between;align-items:center;padding:5px 10px;border-radius:7px;font-size:11.5px;font-weight:800;margin-bottom:7px;gap:6px;flex-wrap:wrap;}
    .trade-plan-box{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin-top:6px;background:rgba(2,6,23,0.7)!important;padding:6px 4px;border-radius:8px;border:1px solid rgba(148,163,184,0.15);text-align:center;}
    .sizing-box{background:rgba(16,185,129,0.08)!important;border:1px solid rgba(16,185,129,0.28);border-radius:8px;padding:5px 10px;margin-top:6px;font-size:11px;color:#d1fae5;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:4px;}
    details.quant-detail-drawer{margin-top:6px;background:rgba(2,6,23,0.55);border:1px solid rgba(168,85,247,0.25);border-radius:8px;padding:5px 10px;}
    details.quant-detail-drawer summary{font-size:11px;font-weight:700;color:#c084fc!important;cursor:pointer;list-style:none;}
    .metrics-row{display:flex;flex-wrap:wrap;gap:4px 8px;margin-top:5px;font-size:10.5px;font-family:'JetBrains Mono',monospace;background:rgba(15,23,42,0.9)!important;padding:5px 8px;border-radius:6px;color:#cbd5e1;}
    .ai-council-box{background:#070b14;color:#f8fafc!important;border-radius:11px;padding:11px;margin-top:6px;margin-bottom:9px;border:1px solid rgba(168,85,247,0.35);}
    .council-scroll-window{max-height:460px;overflow-y:auto;padding:9px;background:#04070e;border:1px solid rgba(255,255,255,0.07);border-radius:8px;margin-bottom:8px;}
    .round-divider{text-align:center;margin:6px 0;padding:4px 8px;background:rgba(168,85,247,0.15);border-left:3px solid #a855f7;color:#e9d5ff!important;font-size:11px;font-weight:700;border-radius:4px;}
    .chat-bubble-ai,.chat-bubble-doubt,.chat-bubble-rage,.chat-bubble-agree{border-radius:8px;padding:7px 10px;margin-bottom:6px;font-size:12px;line-height:1.55;background:rgba(255,255,255,0.04);border-left:3px solid #38bdf8;}
    .chat-bubble-doubt{border-left-color:#f59e0b;background:rgba(245,158,11,0.07);}
    .chat-bubble-rage{border-left-color:#ef4444;background:rgba(239,68,68,0.12);}
    .chat-bubble-agree{border-left-color:#a855f7;background:rgba(168,85,247,0.11);}
    .chat-bubble-user{background:rgba(37,99,235,0.25);border-left:3px solid #60a5fa;border-radius:8px;padding:7px 10px;margin-bottom:6px;font-size:12px;}
    .consensus-banner{background:linear-gradient(135deg,#0f172a,#1e1b4b);border:1px solid rgba(168,85,247,0.45);border-radius:9px;padding:10px;margin-top:7px;font-size:12px;}
    .beginner-action-box{background:linear-gradient(135deg,rgba(16,185,129,0.14),rgba(6,78,59,0.25));border:1px solid #10b981;border-left:4px solid #10b981;border-radius:8px;padding:9px 11px;margin-top:7px;color:#ecfdf5;font-size:12px;line-height:1.6;}
    .ipo-link-btn{display:inline-block;background:#1e293b;color:#38bdf8!important;border:1px solid #334155;padding:4px 9px;border-radius:6px;font-size:11px;font-weight:700;text-decoration:none!important;margin-right:5px;margin-top:4px;}
    .ipo-link-btn:hover{background:#38bdf8;color:#0f172a!important;}
    """
    st.markdown(f'<div id="page_top_anchor"></div><style>{" ".join(l.strip() for l in css.splitlines() if l.strip())}</style>', unsafe_allow_html=True)

inject_css()

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
                st.session_state["authenticated_user"] = None; st.query_params.clear(); st.error("💀 このアカウントまたは端末は永久BAN（利用禁止）されています。"); st.stop()
            if not u_rec or u_rec.get("status") != "approved":
                st.session_state["authenticated_user"] = None; st.query_params.clear(); st.error("🚫 アカウント一時停止中、または削除されています。"); st.stop()
        keep_tok = gen_tok(cu, "session_keep")
        if cu in db:
            db[cu].update({"last_seen_ts": time.time(), "last_seen_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "fp": cur_fp, "raw_hfp": raw_hfp, "bio_enabled": True})
            save_j(FILES["mem"], db)
            sec.setdefault("device_bio_map", {})[raw_hfp] = sec["device_bio_map"][cur_fp] = {"email": cu, "token": keep_tok, "fp": cur_fp}; save_j(FILES["sec"], sec)
        st.query_params["u"], st.query_params["t"] = cu, keep_tok
        with st.sidebar:
            st.markdown(f'<div style="background:#0f172a;padding:8px 11px;border-radius:9px;border:1px solid rgba(168,85,247,0.35);margin-bottom:6px;"><div style="font-size:9.5px;color:#c084fc;font-weight:700;">⚛️ QUANTUM SESSION ACTIVE</div><div style="color:#f8fafc;font-size:11.5px;font-weight:700;">{db.get(cu,{}).get("name","会員")} ({cu})</div></div>', unsafe_allow_html=True)
            render_biometric_bridge(mode="register", user_email=cu, bio_token=keep_tok)
            if st.button("🚪 ログアウト", use_container_width=True):
                if cu in db: db[cu]["last_seen_ts"] = 0; save_j(FILES["mem"], db)
                st.session_state["authenticated_user"] = None; st.query_params.clear(); st.rerun()
        if cu == ADMIN_EMAIL.strip().lower():
            pend = [v for v in db.values() if v.get("status") == "pending"]
            mdb_Now = load_mail_db()
            unread_msgs = [m for m in mdb_Now.get("messages", []) if m.get("sender_role") == "member" and not m.get("read_by_admin", False)]
            spoof_cnt = len(sec.get("spoof_logs", []))
            if st.sidebar.button(f"👑 管理画面 (承認待:{len(pend)} / 未読MSG:{len(unread_msgs)} / 監視:{spoof_cnt})", use_container_width=True):
                st.session_state["navigation_page"] = "ADMIN"; st.rerun()
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
                is_ban, _ = check_and_log_ban_spoof(cm, (rec or {}).get("name", ""), cur_fp, raw_hfp, (rec or {}).get("pin_hash", ""), "コードログイン")
                if is_ban or (rec and rec.get("status") == "banned"):
                    st.error("💀 このアカウントまたは端末は永久BAN（利用禁止）されています。")
                elif rec and rec.get("status") == "suspended": st.error("🚫 このアカウントは一時停止されています。")
                elif ((rec and rec.get("status") == "approved") or cm == ADMIN_EMAIL.strip().lower()) and (hmac.compare_digest(ic.strip().upper(), gen_code(cm)) or (cm == ADMIN_EMAIL.strip().lower() and ic.strip() == "ADMIN777")):
                    st.session_state["authenticated_user"] = cm; st.rerun()
                else: st.warning("⚠️ 未承認または専用アクセスコードが異なります。")

    with tab_apply:
        with st.form("apply"):
            st.caption("🔐 セキュリティ保護のため、申請時に「あなただけの4桁の暗証番号(PIN)」を設定してください。承認後にコードを確認する際に必要となります。")
            an = st.text_input("👤 お名前（ニックネーム可）")
            am = st.text_input("📧 メールアドレス")
            apin = st.text_input("🔢 秘密の4桁暗証番号 (PIN・数字4桁)", type="password", max_chars=4, placeholder="例: 7788")
            if st.form_submit_button("📨 セキュア会員登録を申請する", use_container_width=True):
                if "@" not in am or len(apin.strip()) < 4:
                    st.warning("⚠️ 正しいメールアドレスと4桁の暗証番号(PIN)を入力してください。")
                else:
                    cm, pc, ns = am.strip().lower(), gen_code(am), datetime.now().strftime("%Y-%m-%d %H:%M")
                    nm_clean = an.strip() or "未入力"
                    pin_h = hash_pin(apin)
                    is_ban, ban_reason = check_and_log_ban_spoof(cm, nm_clean, cur_fp, raw_hfp, pin_h, "新規登録申請")
                    if is_ban or (db.get(cm) and db[cm].get("status") == "banned"):
                        st.error("💀 セキュリティ監視システムにより、永久BAN対象者（または同一端末からのなりすまし再登録）と判定されたため申請は永久ブロックされました。")
                    else:
                        db[cm] = {"name": nm_clean, "email": cm, "status": "pending", "passcode": pc, "pin_hash": pin_h, "applied_at": ns, "approved_at": "-", "last_seen_ts": 0, "last_seen_str": "-", "fp": cur_fp, "raw_hfp": raw_hfp, "bio_enabled": False}
                        save_j(FILES["mem"], db)
                        send_mail(cm, "【YAMASHISHI LAB】会員登録申請の受付完了", f"{nm_clean} 様\n申請を受け付けました。管理者承認後、ログイン画面の『🔐 承認確認・暗号化コード照会』タブにて、ご設定いただいた4桁の暗証番号(PIN)を入力すると専用アクセスコードをご確認いただけます。")
                        st.success("✅ 申請を受け付けました！承認完了まで今しばらくお待ちください。")

    with tab_vault:
        st.caption("🛡️ 第三者による盗み見を防止するため、**申請時のメールアドレス** と **秘密の4桁暗証番号(PIN)** の両方が一致した場合のみ専用アクセスコードを開示します。")
        with st.form("vault_check"):
            chk_em = st.text_input("📧 申請したメールアドレス").strip().lower()
            chk_pin = st.text_input("🔢 申請時に設定した4桁の暗証番号 (PIN)", type="password", max_chars=4).strip()
            if st.form_submit_button("🔍 本人確認して承認ステータスを照会", use_container_width=True):
                u_info = db.get(chk_em)
                is_ban, _ = check_and_log_ban_spoof(chk_em, (u_info or {}).get("name", ""), cur_fp, raw_hfp, hash_pin(chk_pin) if chk_pin else "", "コード照会")
                if is_ban or (u_info and u_info.get("status") == "banned"):
                    st.error("💀 このアカウントまたは端末は永久BANされています。")
                elif not u_info: st.error("❌ 該当する申請データが見つかりません。")
                elif u_info.get("pin_hash") and not hmac.compare_digest(u_info.get("pin_hash", ""), hash_pin(chk_pin)):
                    st.error("🚫 暗証番号(PIN)が一致しません。第三者による照会はブロックされました。")
                elif u_info.get("status") == "approved":
                    st.success(f"🎉 本人確認完了・承認済みです！あなたの専用アクセスコードは **`{u_info.get('passcode', gen_code(chk_em))}`** です。「🔑 コードログイン」タブからログインしてください。")
                elif u_info.get("status") == "pending": st.info("⏳ 本人確認完了：現在、管理者の承認審査待ちです。")
                else: st.error("🚫 現在このアカウントは一時停止中または利用できません。")
    st.stop()

check_auth()

for k, v in [("active_debates", {}), ("stock_chats", {}), ("council_threads", {}), ("council_meta", {}), ("debate_round_seed", {}), ("watchlist", {}), ("navigation_page", "TOP"), ("selected_news_item", None), ("custom_search_code", ""), ("active_category", "🏆 総合TOP5"), ("last_cat", "🏆 総合TOP5"), ("nav_history", []), ("scroll_top_trig", 0), ("dismissed_news_ids", set()), ("show_ai_guide", False), ("scroll_target_id", "")]:
    if k not in st.session_state: st.session_state[k] = v

open_cnt = sum(1 for v in st.session_state["active_debates"].values() if v)
with st.container():
    st.markdown('<div class="top-nav-marker"></div>', unsafe_allow_html=True)
    nav_c1, nav_c2, nav_c3 = st.columns([1, 1.45, 1])
    if nav_c1.button("⬆️ トップ", key="top_nav_top", use_container_width=True):
        st.session_state["navigation_page"] = "TOP"; st.session_state["scroll_top_trig"] += 1; st.rerun()
    if nav_c2.button(f"✖ 合議全て閉じる({open_cnt})" if open_cnt else "✖ 合議全て閉じる", key="top_nav_close", use_container_width=True):
        st.session_state["active_debates"] = {}; st.rerun()
    if nav_c3.button("↩️ 戻る", key="top_nav_back", use_container_width=True):
        if st.session_state.get("navigation_page") != "TOP":
            st.session_state["navigation_page"] = "TOP"; st.session_state["scroll_top_trig"] += 1
        elif st.session_state.get("custom_search_code"): st.session_state["custom_search_code"] = ""
        elif st.session_state["nav_history"]:
            popped = st.session_state["nav_history"].pop()
            st.session_state["active_category"] = popped
            st.session_state["last_cat"] = popped
        else:
            st.session_state["active_category"] = "🏆 総合TOP5"
            st.session_state["last_cat"] = "🏆 総合TOP5"
        st.rerun()

scroll_target_js = ""
if st.session_state.get("scroll_target_id"):
    tid = st.session_state.get("scroll_target_id")
    scroll_target_js = f"""
        setTimeout(function(){{
            const el = window.parent.document.getElementById('{tid}');
            if(el){{
                el.scrollIntoView({{behavior: 'smooth', block: 'center'}});
            }}
        }}, 200);
    """
    st.session_state["scroll_target_id"] = ""

components.html(
    f"""<script>
    (function(){{
        const doc = window.parent.document;
        function fixTopNav(){{
            const marker = doc.querySelector('.top-nav-marker');
            if(!marker) return;
            let box = marker.closest('[data-testid="stVerticalBlockBorderWrapper"]') || marker.closest('[data-testid="stVerticalBlock"]');
            if(box && box.querySelector('[data-testid="stHorizontalBlock"]')){{
                box.classList.add('fixed-top-nav-bar');
                let p = box.parentElement;
                while(p && p !== doc.body){{
                    const st = window.parent.getComputedStyle(p);
                    if(st.transform && st.transform !== 'none') p.style.setProperty('transform', 'none', 'important');
                    if(st.filter && st.filter !== 'none') p.style.setProperty('filter', 'none', 'important');
                    if(st.perspective && st.perspective !== 'none') p.style.setProperty('perspective', 'none', 'important');
                    p = p.parentElement;
                }}
            }}
        }}
        fixTopNav();
        setTimeout(fixTopNav, 120);
        setTimeout(fixTopNav, 400);
        if({st.session_state['scroll_top_trig']} > 0 && window.parent._lastScrollTrig !== {st.session_state['scroll_top_trig']}){{
            window.parent._lastScrollTrig = {st.session_state['scroll_top_trig']};
            try{{
                window.parent.scrollTo({{top:0,behavior:'instant'}});
                const m=doc.querySelector('section.main');if(m)m.scrollTo({{top:0,behavior:'instant'}});
                const a=doc.querySelector('[data-testid="stAppViewContainer"]');if(a)a.scrollTo({{top:0,behavior:'instant'}});
            }}catch(e){{}}
        }}
        {scroll_target_js}
    }})();
    </script>""",
    height=0
)

AI_ROSTER = {
    "QUANTUM": "⚛️ QUANTUM (量子波動・トンネル解析官)",
    "AEGIS": "🛡️ AEGIS (CVaR防衛官)",
    "IGNIS": "🔥 IGNIS (OFI・5ch特攻官)",
    "TECHNOS": "📐 TECHNOS (数理・Kyleλ構造官)",
    "MACRO": "🌐 MACRO (先物ギャップ官)",
    "MICRO": "🔬 MICRO (機関VPIN・Hurst監査官)",
    "CHRONOS": "📊 CHRONOS (統計バックテスト官)",
    "NEXUS": "👑 NEXUS (総括ディレクター)"
}

DYNAMIC_DYNAMIC_POOLS = {
    "半導体": [
        {"code": "8035.T", "name": "東京エレクトロン", "theme": "前工程装置筆頭"},
        {"code": "6857.T", "name": "アドバンテスト", "theme": "AI半導体テスタ首位"},
        {"code": "6920.T", "name": "レーザーテック", "theme": "EUV検査高ボラ"},
        {"code": "6146.T", "name": "ディスコ", "theme": "HBM精密加工装置"},
        {"code": "6526.T", "name": "ソシオネクスト", "theme": "カスタムSoC"},
        {"code": "7735.T", "name": "スクリーンHD", "theme": "ウエハー洗浄首位"},
        {"code": "6315.T", "name": "TOWA", "theme": "HBMモールディング"},
        {"code": "6723.T", "name": "ルネサス", "theme": "車載・AI半導体"},
        {"code": "4063.T", "name": "信越化学工業", "theme": "ウエハー世界首位"},
        {"code": "6871.T", "name": "日本マイクロニクス", "theme": "HBMプローブ"},
        {"code": "NVDA", "name": "エヌビディア (米)", "theme": "AI GPU覇者"},
        {"code": "AMD", "name": "AMD (米)", "theme": "AIアクセラレータ"},
        {"code": "MU", "name": "マイクロン (米)", "theme": "HBMメモリ"},
        {"code": "TSM", "name": "TSMC (米)", "theme": "半導体受託首位"},
        {"code": "AVGO", "name": "ブロードコム (米)", "theme": "カスタムAI半導体"},
        {"code": "ARM", "name": "アーム (米)", "theme": "半導体設計"}
    ],
    "AI・防衛・主力": [
        {"code": "9984.T", "name": "ソフトバンクG", "theme": "AI投資・先物主役"},
        {"code": "3778.T", "name": "さくらネット", "theme": "国策GPUクラウド"},
        {"code": "7011.T", "name": "三菱重工業", "theme": "防衛・宇宙国策主力"},
        {"code": "7012.T", "name": "川崎重工業", "theme": "防衛・航空エンジン"},
        {"code": "7013.T", "name": "IHI", "theme": "航空宇宙・防衛"},
        {"code": "3993.T", "name": "PKSHA", "theme": "AIアルゴリズム"},
        {"code": "5032.T", "name": "ANYCOLOR", "theme": "VTuber大手"},
        {"code": "7974.T", "name": "任天堂", "theme": "次世代機・機関流入"},
        {"code": "8306.T", "name": "三菱UFJ", "theme": "金利連動メガバンク"},
        {"code": "MSFT", "name": "マイクロソフト (米)", "theme": "クラウドAI"},
        {"code": "PLTR", "name": "パランティア (米)", "theme": "防衛AI大本命"},
        {"code": "META", "name": "メタ (米)", "theme": "AI広告"},
        {"code": "GOOGL", "name": "アルファベット (米)", "theme": "Gemini生成AI"},
        {"code": "CRWD", "name": "クラウドストライク (米)", "theme": "AIセキュリティ"}
    ],
    "AI電力・電線": [
        {"code": "5803.T", "name": "フジクラ", "theme": "DC光ファイバー最強株"},
        {"code": "5801.T", "name": "古河電気工業", "theme": "光ファイバー・送電"},
        {"code": "5802.T", "name": "住友電気工業", "theme": "電線首位・DC網"},
        {"code": "6501.T", "name": "日立製作所", "theme": "世界送配電グリッド"},
        {"code": "9509.T", "name": "北海道電力", "theme": "ラピダス・DC電力"},
        {"code": "9508.T", "name": "九州電力", "theme": "TSMC工場電力"},
        {"code": "6622.T", "name": "ダイヘン", "theme": "DC変圧器"},
        {"code": "1942.T", "name": "関電工", "theme": "DC電気設備"},
        {"code": "VST", "name": "ビストラ (米)", "theme": "AI発電主力"},
        {"code": "CEG", "name": "コンステレーション (米)", "theme": "米原発AI電力"},
        {"code": "GEV", "name": "GEヴェルノバ (米)", "theme": "送電網リーダー"}
    ],
    "宇宙・次世代": [
        {"code": "5595.T", "name": "QPS研究所", "theme": "小型SAR衛星"},
        {"code": "186A.T", "name": "アストロスケール", "theme": "宇宙デブリ除去"},
        {"code": "9348.T", "name": "ispace", "theme": "月面輸送"},
        {"code": "9412.T", "name": "スカパーJSAT", "theme": "衛星・防衛宇宙"},
        {"code": "7203.T", "name": "トヨタ自動車", "theme": "全固体電池"},
        {"code": "TSLA", "name": "テスラ (米)", "theme": "自動運転・ロボ"},
        {"code": "RKLB", "name": "ロケットラボ (米)", "theme": "小型ロケット"},
        {"code": "ASTS", "name": "ASTスペース (米)", "theme": "宇宙スマホ通信"},
        {"code": "COIN", "name": "コインベース (米)", "theme": "暗号資産高ボラ"}
    ],
    "小型急騰・直近IPO": [
        {"code": "5253.T", "name": "カバー", "theme": "グロース売買首位級"},
        {"code": "9166.T", "name": "GENDA", "theme": "エンタメM&A"},
        {"code": "216A.T", "name": "タイミー", "theme": "スキマバイト大型IPO"},
        {"code": "285A.T", "name": "キオクシアHD", "theme": "NAND大型IPO"},
        {"code": "141A.T", "name": "トライアルHD", "theme": "リテールAI流通IPO"},
        {"code": "247A.T", "name": "Aiロボティクス", "theme": "AIマーケ急騰IPO"},
        {"code": "3350.T", "name": "メタプラネット", "theme": "暗号資産・超ボラ"},
        {"code": "IONQ", "name": "アイオンQ (米)", "theme": "商用量子代表"},
        {"code": "RGTI", "name": "リゲッティ (米)", "theme": "量子急騰株"},
        {"code": "RDDT", "name": "レディット (米IPO)", "theme": "AIデータ大型IPO"},
        {"code": "ALAB", "name": "アステラ・ラブズ (米IPO)", "theme": "AI接続半導体IPO"}
    ]
}
STOCK_POOL = DYNAMIC_DYNAMIC_POOLS
KNOWN_STOCKS = {it["code"]: {"name": it["name"], "theme": it["theme"], "genre": g} for g, its in STOCK_POOL.items() for it in its}

def _parse_j(raw: str):
    txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(raw or "").strip(), flags=re.IGNORECASE).strip()
    sb, eb = txt.find("{"), txt.rfind("}")
    if sb != -1 and eb > sb: txt = txt[sb:eb+1]
    return json.loads(re.sub(r"[\x00-\x1f]+", " ", re.sub(r",\s*([}\]])", r"\1", txt)))

def get_active_ai_providers() -> list:
    cfg = load_llm()
    act = []
    for k, (lbl, m_list, _) in AI_PROVIDERS.items():
        key = clean_k(st.session_state.get(f"rt_key_{k}") or cfg.get("api_keys", {}).get(k, ""))
        mod = st.session_state.get(f"rt_mod_{k}") or cfg.get("models", {}).get(k, m_list[0])
        if key: act.append((k, lbl, mod, key))
    return act

def get_debate_mode_badge(cnt: int) -> str:
    if cnt <= 1: return "🧠 シングルAI・7人専門家合議モード"
    if cnt == 2: return "⚔️ 2大AI クロス対談モード (並列接続)"
    if cnt == 3: return "🔥 3大AI トライアングル・ディベート (並列接続)"
    if cnt <= 6: return f"🏛️ {cnt}大AI ラウンドテーブル会議 (並列接続)"
    return "👑 7大AI グランド討論会・完全合議 (全社並列接続)"

def call_single_provider_api(prov: str, model: str, key: str, sys_p: str, usr_p: str, temp: float = 0.7):
    p_label, _, endpoint = AI_PROVIDERS.get(prov, AI_PROVIDERS["gemini"])
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try:
        if prov == "gemini":
            url = endpoint.format(model=model, key=urllib.parse.quote(key))
            gen_cfg = {"temperature": temp}
            if not model.startswith("gemma"): gen_cfg["responseMimeType"] = "application/json"
            payload = {"contents": [{"role": "user", "parts": [{"text": f"【指示】\n{sys_p}\n\n【データ】\n{usr_p}"}]}], "generationConfig": gen_cfg}
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=12.0, context=ctx) as r:
                d = json.loads(r.read().decode("utf-8"))
                return _parse_j("".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"])), f"{p_label} ({model})"
        elif prov == "claude":
            payload = {"model": model, "max_tokens": 1200, "temperature": temp, "system": sys_p + " JSONのみ出力せよ。", "messages": [{"role": "user", "content": usr_p}]}
            req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"}, method="POST")
            with urllib.request.urlopen(req, timeout=12.0, context=ctx) as r:
                return _parse_j(json.loads(r.read().decode("utf-8"))["content"][0]["text"]), f"{p_label} ({model})"
        else:
            payload = {"model": model, "messages": [{"role": "system", "content": sys_p + " Always output valid JSON."}, {"role": "user", "content": usr_p}], "temperature": temp}
            req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"}, method="POST")
            with urllib.request.urlopen(req, timeout=12.0, context=ctx) as r:
                return _parse_j(json.loads(r.read().decode("utf-8"))["choices"][0]["message"]["content"]), f"{p_label} ({model})"
    except Exception:
        return None, f"{p_label} ({model})"

def analyze_news_impact_and_links(title: str, cat: str) -> dict:
    t_up = title.upper()
    if any(w in t_up for w in ["半導体", "エヌビディア", "NVDA", "TSMC", "レーザー", "アドバンテスト", "ディスコ", "HBM", "AI", "GPU", "キオクシア"]):
        codes, sector_focus = ["6857.T", "8035.T", "6146.T", "6920.T", "5803.T", "NVDA"], "AI半導体・HBM製造装置・データセンター光配線セクター"
        mech = "米SOX指数およびNVIDIA・TSMCの設備投資サプライチェーンに直結する重要ヘッドラインです。機関投資家のバスケット買いアルゴは、まず先物主導でアドバンテスト(6857)・東京エレクトロン(8035)・ディスコ(6146)の上値板を掃き上げ、時間差でAIデータセンター向け光ファイバーのフジクラ(5803)へ資金を波及させる強い量子もつれ（相関）を持っています。"
    elif any(w in t_up for w in ["防衛", "三菱重", "宇宙", "衛星", "ドローン", "IHI", "川重", "安全保障", "トランプ"]):
        codes, sector_focus = ["7011.T", "7012.T", "7013.T", "5595.T", "186A.T", "PLTR"], "防衛国策・航空宇宙・小型SAR衛星セクター"
        mech = "地政学・国策防衛予算および宇宙安全保障に関わるテーマ材料です。主力大型株の三菱重工業(7011)・川崎重工業(7012)・IHI(7013)に海外年金・機関のロング資金が流入しやすく、個人の短期モメンタム資金は値動きの軽いQPS研究所(5595)やアストロスケール(186A)へ波及しやすい構造です。"
    elif any(w in t_up for w in ["電力", "原発", "データセンター", "電線", "送電", "フジクラ", "日立"]):
        codes, sector_focus = ["5803.T", "5801.T", "6501.T", "9509.T", "9508.T", "VST"], "AI電力インフラ・超電導送電網・光ファイバー電線セクター"
        mech = "生成AIデータセンターの爆発的な電力需要と送配電網増強に直結する国策テーマです。電線御三家筆頭のフジクラ(5803)・古河電工(5801)、世界送配電グリッドの日立製作所(6501)、さらにラピダス・TSMC稼働に伴う北海道電力(9509)・九州電力(9508)が強く連動します。"
    elif any(w in t_up for w in ["量子", "暗号", "セキュリティ", "IONQ", "さくら", "クラウド"]):
        codes, sector_focus = ["3778.T", "3993.T", "IONQ", "RGTI", "CRWD", "9984.T"], "量子コンピューティング・国策AIクラウド・サイバー防衛セクター"
        mech = "次世代計算基盤（量子・GPUクラウド）およびゼロトラスト防衛に関わる最先端材料です。米量子株のIonQ(IONQ)・Rigetti(RGTI)の急騰は、日本市場のさくらインターネット(3778)やPKSHA(3993)へ短期資金を誘発する強い先行指標となります。"
    else:
        codes, sector_focus = ["9984.T", "6857.T", "5803.T", "7011.T", "3778.T", "NVDA"], "日米AI主力・ストップ高モメンタム波及セクター"
        mech = "市場全体のセンチメントと短期資金の回転を加速させるサプライズ材料です。指数寄与度の高いソフトバンクG(9984)やアドバンテスト(6857)が先物主導で動くほか、好決算・上方修正・自社株買いの連想から高OFI（板吸収）銘柄へ一気に順張り資金が集中しやすくなります。"
    return {
        "sector_focus": sector_focus, "mechanism": mech, "related_codes": codes,
        "action_guide": "① 朝8:45〜8:55の気配値で、下の『連動・波及注目銘柄』の寄り付きギャップとOFI（板の買い越し）を確認します。\n② 主力株（大型）がギャップアップして始まった場合、まだ初動で出遅れている2番手・周辺銘柄（電線・部材・中小型AI）のVWAP押し目を狙う『時間差連動スナイプ』が最も勝率の高いプロの手口です。"
    }

@st.cache_data(ttl=180)
def fetch_global_impact_news() -> list:
    qs = [("半導体・AIサプライズ", "半導体 OR エヌビディア OR TSMC OR アドバンテスト OR データセンター 株価"), ("急騰・上方修正・TOB", "ストップ高 OR 上方修正 OR 自社株買い OR 防衛 OR 量子 株")]
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    out, seen = [], set()
    for cat, q in qs:
        try:
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=ja&gl=JP&ceid=JP:ja"
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=3.0, context=ctx) as res:
                root = ET.fromstring(res.read())
            for it in root.findall("./channel/item")[:3]:
                t = re.sub(r"\s*-\s*[^-]+$", "", (it.findtext("title") or "").strip())
                if not t or t in seen: continue
                seen.add(t)
                out.append({"id": hashlib.md5(t.encode()).hexdigest()[:8], "cat": cat, "title": t, "link": it.findtext("link") or "", "source": it.findtext("source") or "Market Wire", "pub_date": (it.findtext("pubDate") or "")[:25], "impact_score": 92, "detail": analyze_news_impact_and_links(t, cat)})
        except Exception: continue
    if not out:
        t_fb = "AI半導体・次世代データセンター光配線および防衛・量子分野に機関投資家の大型資金流入が加速"
        out.append({"id": "fb_news_01", "cat": "機関オーダーフロー速報", "title": t_fb, "link": "https://jp.reuters.com/", "source": "YAMASHISHI QUANT WIRE", "pub_date": datetime.now().strftime("%Y-%m-%d %H:%M"), "impact_score": 94, "detail": analyze_news_impact_and_links(t_fb, "半導体・AIサプライズ")})
    return out[:4]

@st.cache_data(ttl=900)
def fetch_5ch_live() -> dict:
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    txts = []
    for u in BOARD_URLS:
        try:
            with urllib.request.urlopen(urllib.request.Request(u + "l50", headers={"User-Agent": "Mozilla/5.0"}), timeout=2.5, context=ctx) as r:
                txts.append(re.sub(r"<[^>]+>", " ", r.read().decode("cp932", errors="ignore")))
        except Exception: continue
    joined = " ".join(txts)
    return {c: {"hits": len(re.findall(re.escape(c.replace(".T", "")), joined)) if joined else 0, "live": bool(txts)} for c in KNOWN_STOCKS}

st.sidebar.header("🧠 7大AI ＆ 量子エンジン設定")
llm_cfg = load_llm()
cur_prov = st.sidebar.selectbox("AIプロバイダー選択 (7社対応)", list(AI_PROVIDERS.keys()), format_func=lambda k: AI_PROVIDERS[k][0], index=list(AI_PROVIDERS.keys()).index(llm_cfg.get("provider", "gemini")) if llm_cfg.get("provider") in AI_PROVIDERS else 0)
st.session_state["rt_llm_prov"] = cur_prov
p_name, p_models, _ = AI_PROVIDERS[cur_prov]
saved_k = llm_cfg.get("api_keys", {}).get(cur_prov, "")
saved_m = llm_cfg.get("models", {}).get(cur_prov, p_models[0])
in_k = clean_k(st.sidebar.text_input(f"🔑 {p_name} API Key", value=saved_k, type="password"))
in_m = st.sidebar.selectbox(f"🧠 {p_name} モデル", p_models, index=p_models.index(saved_m) if saved_m in p_models else 0)
st.session_state[f"rt_key_{cur_prov}"], st.session_state[f"rt_mod_{cur_prov}"] = in_k, in_m
if in_k != saved_k or in_m != saved_m or cur_prov != llm_cfg.get("provider"):
    llm_cfg["provider"] = cur_prov; llm_cfg.setdefault("api_keys", {})[cur_prov] = in_k; llm_cfg.setdefault("models", {})[cur_prov] = in_m
    save_j(FILES["llm"], llm_cfg)
    st.session_state["council_threads"] = {}

active_ais = get_active_ai_providers()
active_cnt = len(active_ais)
st.sidebar.caption(f"🟢 現在起動中のAI: **{active_cnt} / 7社** ｜ **{get_debate_mode_badge(active_cnt)}**")

if st.sidebar.button("📖 起動AI数による合議モード＆並列接続の詳しい説明", use_container_width=True):
    st.session_state["show_ai_guide"] = not st.session_state.get("show_ai_guide", False)

if st.session_state.get("show_ai_guide", False):
    st.sidebar.markdown(
        '<div style="background:rgba(15,23,42,0.95);border:1px solid rgba(56,189,248,0.4);border-radius:9px;padding:10px;font-size:11.5px;line-height:1.55;color:#e2e8f0;margin-bottom:8px;">'
        '<b style="color:#38bdf8;">⚡ マルチAI並列接続＆自動合議システムとは？</b><br>'
        '上のプルダウンを切り替えて各AIのAPIキーを入力・保存すると、<b>キーが登録されたAIの数（起動数）を自動検知</b>し、合議の形式がリアルタイムに進化します。<br><br>'
        '<b>① 1つのAIを起動（または未入力）</b><br>1つのAIが「量子・機関ミクロ・数理・CVaR防衛」など<b>7人の専門家ロール</b>を1人で演じ分けて多角的に会議します。<br>'
        '<b>② 2つのAIを起動【AI同士の対談】</b><br>起動した2社のAI（例：GeminiとChatGPT）が<b>1対1のクロス対談形式（計4ターン）</b>で互いの予測と戦略をぶつけ合います。<br>'
        '<b>③ 3つのAIを起動【3大AIディベート】</b><br>3社のAIが「強気特攻・数理構造・リスク監査」の3極に分かれ、<b>三つ巴の本格ディベート</b>を行います。<br>'
        '<b>④ 4〜6つのAIを起動【AIラウンドテーブル会議】</b><br>起動した全AIがそれぞれの独自推論モデルで銘柄を評価し、円卓会議形式で合議します。<br>'
        '<b>⑤ 7大AIすべて起動【👑 7大AIグランド討論会】</b><br>Gemini・ChatGPT・Claude・Grok・DeepSeek・Perplexity・Groqの<b>世界7大AIすべてが一堂に会する最高峰のグランド討論会</b>が開催されます。<br><br>'
        '<b style="color:#a7f3d0;">🚀 高速・低負荷の並列接続（ThreadPoolExecutor）</b><br>'
        '複数のAPIキーを起動しても直列で順番待ちせず、<b>バックグラウンドで全AIへ同時に非同期・並列リクエスト</b>を送るため、7社同時起動でも約2〜4秒で高速・低負荷に討論が完了します。'
        '</div>',
        unsafe_allow_html=True
    )

st.sidebar.markdown("---")
st.sidebar.header("🎯 投資スタイル選択")
investment_style = st.sidebar.selectbox(
    "トレードスタイル",
    ["⚡ デイトレード (前場・後場の波及を狙う)", "🚀 スキャルピング (秒〜分単位のモメンタム)", "📈 スイングトレード (数日〜数週間のトレンド)", "💎 バイ＆ホールド (中長期・IPO分散投資)"],
    index=0
)
st.sidebar.caption(f"選択中スタイル: **{investment_style.split(' ')[1]}** に合わせてランキング・エントリー・利確/損切アルゴリズムがリアルタイム最適化されます。")

st.sidebar.markdown("---")
st.sidebar.header("💰 資金管理＆フィルタ設定")
total_capital = st.sidebar.number_input("総投資資金 (円/ドル)", min_value=10000, max_value=1000000000, value=1000000, step=50000)
risk_tolerance_pct = st.sidebar.slider("1トレード許容リスク (%)", 0.5, 5.0, 2.0, 0.5)
survival_cut_pct = st.sidebar.slider("各タブ選抜率 (%)", 40, 100, 75, 5)
toggle_fn = getattr(st.sidebar, "toggle", st.sidebar.checkbox)
show_5m_chart = toggle_fn("📈 5分足＆VWAP描画", value=True)
enable_news_popup = toggle_fn("🚨 緊急ニュースポップアップ", value=True)

st.sidebar.markdown("---")
st.sidebar.header("✉️ 管理者にメッセージを送る")
cu_Now = st.session_state.get("authenticated_user", "")
if cu_Now:
    db_Now = load_mem()
    mdb_Now = load_mail_db()
    u_name_Now = db_Now.get(cu_Now, {}).get("name", "会員")
    my_msgs = [m for m in mdb_Now.get("messages", []) if m.get("member_email") == cu_Now]
    unread_admin_replies = [m for m in my_msgs if m.get("sender_role") == "admin" and not m.get("read_by_member", False)]
    if unread_admin_replies:
        st.sidebar.markdown(
            f'<div style="background:rgba(16,185,129,0.18);border:1px solid #10b981;border-radius:8px;padding:7px 10px;font-size:11.5px;color:#ecfdf5;margin-bottom:6px;">'
            f'📬 <b>管理者から新着の返信メッセージが {len(unread_admin_replies)}件 届いています！</b>（下の履歴から確認できます）</div>',
            unsafe_allow_html=True
        )
    with st.sidebar.form("sidebar_msg_to_admin", clear_on_submit=True):
        msg_subj = st.text_input("件名（任意）", placeholder="ご質問・ご要望など")
        msg_body = st.text_area("メッセージ本文", placeholder="管理者へのメッセージを入力してください...", height=85)
        if st.form_submit_button("📨 管理者にメッセージを送信", use_container_width=True):
            if not msg_body.strip():
                st.warning("⚠️ メッセージ本文を入力してください。")
            else:
                now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                subj_c = msg_subj.strip() or "会員からのメッセージ"
                mdb_Now.setdefault("messages", []).insert(0, {
                    "id": hashlib.md5(f"{cu_Now}_{now_s}_{msg_body}".encode()).hexdigest()[:8],
                    "time": now_s,
                    "member_email": cu_Now,
                    "member_name": u_name_Now,
                    "sender_role": "member",
                    "subject": subj_c,
                    "body": msg_body.strip(),
                    "read_by_admin": False,
                    "read_by_member": True
                })
                save_j(FILES["mail"], mdb_Now)
                send_mail(ADMIN_EMAIL, f"【会員メッセージ受信】{u_name_Now}様 ({cu_Now}) - {subj_c}", f"送信者: {u_name_Now} ({cu_Now})\n日時: {now_s}\n件名: {subj_c}\n\n{msg_body.strip()}", category="会員メッセージ")
                st.success("✅ 管理者にメッセージを送信しました！")
    if my_msgs:
        with st.sidebar.expander(f"📬 管理者とのメッセージ履歴 ({len(my_msgs)}件)", expanded=bool(unread_admin_replies)):
            if unread_admin_replies:
                if st.button("✅ 新着返信を既読にする", key="mark_read_mem", use_container_width=True):
                    for m in mdb_Now.get("messages", []):
                        if m.get("member_email") == cu_Now and m.get("sender_role") == "admin":
                            m["read_by_member"] = True
                    save_j(FILES["mail"], mdb_Now)
                    st.rerun()
            for m in my_msgs[:15]:
                is_adm = m.get("sender_role") == "admin"
                bg_c = "rgba(16,185,129,0.14)" if is_adm else "rgba(56,189,248,0.10)"
                bd_c = "#10b981" if is_adm else "#38bdf8"
                who_lbl = "👑 管理者からの返信" if is_adm else f"🗣️ あなた ({m.get('member_name', '')})"
                st.markdown(
                    f'<div style="background:{bg_c};border-left:3px solid {bd_c};border-radius:7px;padding:6px 9px;margin-bottom:6px;font-size:11.5px;">'
                    f'<div style="font-size:10px;color:#94a3b8;display:flex;justify-content:space-between;"><span><b>{who_lbl}</b></span><span>{m.get("time","")}</span></div>'
                    f'<div style="font-weight:700;color:#f8fafc;margin-top:2px;">{m.get("subject","")}</div>'
                    f'<div style="color:#e2e8f0;margin-top:2px;white-space:pre-wrap;">{m.get("body","")}</div></div>',
                    unsafe_allow_html=True
                )

all_impact_news = fetch_global_impact_news()
if enable_news_popup and st.session_state.get("navigation_page") != "NEWS_DETAIL":
    unread = [n for n in all_impact_news if n["id"] not in st.session_state["dismissed_news_ids"]]
    if unread:
        tn = unread[0]
        with st.container():
            st.markdown(
                f'<div class="floating-news-popup-marker"></div>'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<span style="font-size:10.5px;color:#f87171;font-weight:800;">🚨 緊急マーケット速報 ｜ {tn["source"]}</span>'
                f'<span class="quantum-badge">波及度 {tn["impact_score"]}点</span></div>'
                f'<div style="font-size:12.5px;font-weight:800;color:#f8fafc;margin:5px 0 4px 0;line-height:1.4;">{tn["title"]}</div>'
                f'<div style="font-size:10.5px;color:#94a3b8;margin-bottom:6px;">🎯 連動セクター: {tn["detail"]["sector_focus"]}</div>',
                unsafe_allow_html=True
            )
            c_n1, c_n2 = st.columns([2.2, 1])
            if c_n1.button("🔥 ニュース詳細＆連動株を見る", key=f"open_n_{tn['id']}", use_container_width=True, type="primary"):
                st.session_state["selected_news_item"] = tn; st.session_state["navigation_page"] = "NEWS_DETAIL"; st.session_state["scroll_top_trig"] += 1; st.rerun()
            if c_n2.button("✖ 閉じる", key=f"cls_n_{tn['id']}", use_container_width=True):
                st.session_state["dismissed_news_ids"].add(tn["id"]); st.rerun()

if st.session_state.get("navigation_page") == "ADMIN" and st.session_state.get("authenticated_user") == ADMIN_EMAIL.strip().lower():
    db = load_mem()
    sec = load_sec()
    mdb = load_mail_db()
    st.subheader("👑 会員管理センター ＆ セキュリティ監視・メッセージ管理")
    if st.button("⬅️ TOPへ戻る", use_container_width=True):
        st.session_state["navigation_page"] = "TOP"; st.rerun()

    adm_tab1, adm_tab2, adm_tab3 = st.tabs([
        f"👥 会員管理 ({len(db)}名)",
        f"📩 会員メッセージ受信・返信 ({len([m for m in mdb.get('messages',[]) if m.get('sender_role')=='member'])})",
        f"🛡️ 永久BAN・なりすまし監視 ({len(sec.get('spoof_logs',[]))})"
    ])

    with adm_tab1:
        st.caption("会員ごとの承認・**一時停止**・**削除**・**永久BAN（端末指紋＆PINロックによるなりすまし再登録ブロック）**を管理できます。")
        for k, v in list(db.items()):
            pc = v.get("passcode", gen_code(k))
            st_val = v.get("status", "pending")
            st_badge = {
                "approved": "🟢 承認済 (利用中)",
                "pending": "⏳ 承認待ち",
                "suspended": "⏸️ 一時停止中",
                "banned": "💀 永久BAN (再登録阻止中)"
            }.get(st_val, st_val)
            st.markdown(
                f'<div style="background:#0f172a;border:1px solid rgba(148,163,184,0.22);border-radius:10px;padding:10px 12px;margin-bottom:6px;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">'
                f'<div><b style="font-size:14px;color:#f8fafc;">{v.get("name","未入力")}</b> (<code>{k}</code>) ｜ 状態: <b>{st_badge}</b></div>'
                f'<div style="font-size:11px;color:#94a3b8;">専用コード: <code>{pc}</code> ｜ 端末FP: <code>{v.get("fp","-")}</code> ｜ 最終アクセス: {v.get("last_seen_str","-")}</div>'
                f'</div></div>',
                unsafe_allow_html=True
            )
            if k != ADMIN_EMAIL.strip().lower():
                b1, b2, b3, b4 = st.columns(4)
                if b1.button("✅ 承認 / 復帰", key=f"ap_{k}", use_container_width=True):
                    db[k]["status"] = "approved"
                    db[k]["approved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    sec.get("banned_emails", {}).pop(k, None)
                    if v.get("fp") in sec.get("banned_fps", {}): sec["banned_fps"].pop(v.get("fp"), None)
                    if v.get("raw_hfp") in sec.get("banned_fps", {}): sec["banned_fps"].pop(v.get("raw_hfp"), None)
                    if v.get("pin_hash") in sec.get("banned_pins", {}): sec["banned_pins"].pop(v.get("pin_hash"), None)
                    save_j(FILES["sec"], sec)
                    save_j(FILES["mem"], db)
                    send_mail(k, "【YAMASHISHI LAB】承認完了のお知らせ", "会員登録が承認（または復帰）されました。ログイン画面の『🔐 承認確認・暗号化コード照会』タブより4桁PINを入力して専用コードをご確認ください。")
                    st.rerun()
                if b2.button("⏸️ 一時停止", key=f"sp_{k}", use_container_width=True):
                    db[k]["status"] = "suspended"
                    save_j(FILES["mem"], db)
                    st.warning(f"⏸️ {v.get('name')} ({k}) を一時停止にしました。")
                    st.rerun()
                if b3.button("🗑️ 削除", key=f"dl_{k}", use_container_width=True):
                    u_fp, u_hfp = v.get("fp", ""), v.get("raw_hfp", "")
                    if u_fp in sec.get("device_bio_map", {}): sec["device_bio_map"].pop(u_fp, None)
                    if u_hfp in sec.get("device_bio_map", {}): sec["device_bio_map"].pop(u_hfp, None)
                    save_j(FILES["sec"], sec)
                    del db[k]
                    save_j(FILES["mem"], db)
                    st.info(f"🗑️ {v.get('name')} ({k}) の会員データを削除しました。")
                    st.rerun()
                if b4.button("💀 永久BAN", key=f"bn_{k}", use_container_width=True):
                    now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    db[k]["status"] = "banned"
                    u_fp, u_hfp, u_pin, u_nm = v.get("fp", ""), v.get("raw_hfp", ""), v.get("pin_hash", ""), v.get("name", "不明")
                    sec.setdefault("banned_emails", {})[k] = {"name": u_nm, "banned_at": now_s, "fp": u_fp, "raw_hfp": u_hfp}
                    if u_fp and u_fp != "-":
                        sec.setdefault("banned_fps", {})[u_fp] = {"email": k, "name": u_nm, "banned_at": now_s, "reason": "管理者による永久BAN"}
                        sec.get("device_bio_map", {}).pop(u_fp, None)
                    if u_hfp and u_hfp != "-":
                        sec.setdefault("banned_fps", {})[u_hfp] = {"email": k, "name": u_nm, "banned_at": now_s, "reason": "管理者による永久BAN"}
                        sec.get("device_bio_map", {}).pop(u_hfp, None)
                    if u_pin:
                        sec.setdefault("banned_pins", {})[u_pin] = k
                    if u_nm and u_nm not in sec.setdefault("banned_names", []):
                        sec["banned_names"].append(u_nm)
                    save_j(FILES["sec"], sec)
                    save_j(FILES["mem"], db)
                    st.error(f"💀 {u_nm} ({k}) を永久BANし、端末指紋・PINをなりすまし監視リストに登録しました。")
                    st.rerun()

    with adm_tab2:
        st.caption("📩 会員から届いたメッセージの発信者（名前・メールアドレス）を確認し、その場で直接会員へ返信できます。")
        all_msgs = mdb.get("messages", [])
        member_order = []
        for m in all_msgs:
            me = m.get("member_email", "")
            if me and me not in member_order:
                member_order.append(me)

        member_choices = [k for k in db.keys() if k != ADMIN_EMAIL.strip().lower()]
        if member_order:
            member_choices = member_order + [m for m in member_choices if m not in member_order]

        if member_choices:
            with st.expander("✉️ 会員を指定してダイレクトメッセージを送信 / 直前会員へ即返信", expanded=True):
                with st.form("admin_direct_reply_top", clear_on_submit=True):
                    target_em = st.selectbox(
                        "宛先会員（一番上が直前にメッセージを送ってきた会員です）",
                        member_choices,
                        format_func=lambda em: f"{'🔴【直前メッセージ会員】 ' if member_order and em == member_order[0] else ''}{db.get(em, {}).get('name', '会員')} ({em})"
                    )
                    rep_subj = st.text_input("件名", value="【YAMASHISHI LAB 管理者より】ご連絡・ご回答")
                    rep_body = st.text_area("返信メッセージ本文", placeholder="会員への返信メッセージを入力してください...", height=90)
                    if st.form_submit_button("📤 この会員にメッセージを送信（アプリ内＆メール通知）", use_container_width=True, type="primary"):
                        if not rep_body.strip():
                            st.warning("⚠️ メッセージ本文を入力してください。")
                        else:
                            now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            t_name = db.get(target_em, {}).get("name", "会員")
                            for m in mdb.get("messages", []):
                                if m.get("member_email") == target_em and m.get("sender_role") == "member":
                                    m["read_by_admin"] = True
                            mdb.setdefault("messages", []).insert(0, {
                                "id": hashlib.md5(f"adm_{target_em}_{now_s}".encode()).hexdigest()[:8],
                                "time": now_s,
                                "member_email": target_em,
                                "member_name": t_name,
                                "sender_role": "admin",
                                "subject": rep_subj.strip() or "管理者からの返信",
                                "body": rep_body.strip(),
                                "read_by_admin": True,
                                "read_by_member": False
                            })
                            save_j(FILES["mail"], mdb)
                            send_mail(target_em, rep_subj.strip() or "【YAMASHISHI LAB】管理者からの返信", f"{t_name} 様\n\n管理者よりメッセージが届きました。\n\n{rep_body.strip()}", category="管理者返信")
                            st.success(f"✅ {t_name} 様 ({target_em}) へメッセージを返信しました！")
                            st.rerun()

        if not member_order:
            st.info("現在、会員から受信しているメッセージはありません。")
        else:
            st.markdown("#### 📬 会員別メッセージスレッド一覧（最新順）")
            for idx_m, mem_em in enumerate(member_order):
                mem_name = db.get(mem_em, {}).get("name") or next((m.get("member_name") for m in all_msgs if m.get("member_email") == mem_em), "会員")
                thread_msgs = [m for m in all_msgs if m.get("member_email") == mem_em]
                unread_cnt = sum(1 for m in thread_msgs if m.get("sender_role") == "member" and not m.get("read_by_admin", False))
                badge_html = f'<span class="pill-badge" style="background:#ef4444;color:#fff;border:none;">🔴 未読 {unread_cnt}件</span>' if unread_cnt else '<span class="pill-badge" style="color:#10b981;">✅ 確認済</span>'
                latest_badge = '<span class="quantum-badge">⚡ 直前メッセージ送信会員</span>' if idx_m == 0 else ''
                st.markdown(
                    f'<div class="rank-card" style="border-left-color:{"#ef4444" if unread_cnt else "#38bdf8"};margin-bottom:8px;">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;margin-bottom:6px;">'
                    f'<div>{latest_badge}{badge_html} <b style="font-size:14.5px;color:#f8fafc;">👤 {mem_name}</b> (<code>{mem_em}</code>)</div>'
                    f'<span style="font-size:11px;color:#94a3b8;">最終やり取り: {thread_msgs[0].get("time","")}</span></div>',
                    unsafe_allow_html=True
                )
                for tm in thread_msgs[:8]:
                    is_adm = tm.get("sender_role") == "admin"
                    b_col = "#10b981" if is_adm else "#f59e0b"
                    bg_col = "rgba(16,185,129,0.10)" if is_adm else "rgba(245,158,11,0.10)"
                    sender_str = "👑 あなた (管理者返信)" if is_adm else f"📩 {mem_name} ({mem_em}) からの受信メッセージ"
                    st.markdown(
                        f'<div style="background:{bg_col};border-left:3px solid {b_col};border-radius:7px;padding:7px 10px;margin-bottom:5px;font-size:12px;">'
                        f'<div style="display:flex;justify-content:space-between;font-size:10.5px;color:#cbd5e1;"><b>{sender_str}</b><span>{tm.get("time","")}</span></div>'
                        f'<div style="font-weight:700;color:#fde047;margin-top:2px;">件名: {tm.get("subject","")}</div>'
                        f'<div style="color:#f8fafc;margin-top:3px;white-space:pre-wrap;">{tm.get("body","")}</div></div>',
                        unsafe_allow_html=True
                    )
                with st.form(f"quick_reply_{mem_em}", clear_on_submit=True):
                    qr_c1, qr_c2 = st.columns([3.2, 1])
                    qr_txt = qr_c1.text_input("ダイレクト返信", placeholder=f"{mem_name} ({mem_em}) 様へ直接返信メッセージを送る...", label_visibility="collapsed")
                    if qr_c2.form_submit_button("↩️ 即時返信", use_container_width=True) and qr_txt.strip():
                        now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        for m in mdb.get("messages", []):
                            if m.get("member_email") == mem_em and m.get("sender_role") == "member":
                                m["read_by_admin"] = True
                        mdb.setdefault("messages", []).insert(0, {
                            "id": hashlib.md5(f"qr_{mem_em}_{now_s}".encode()).hexdigest()[:8],
                            "time": now_s,
                            "member_email": mem_em,
                            "member_name": mem_name,
                            "sender_role": "admin",
                            "subject": "管理者からのダイレクト返信",
                            "body": qr_txt.strip(),
                            "read_by_admin": True,
                            "read_by_member": False
                        })
                        save_j(FILES["mail"], mdb)
                        send_mail(mem_em, "【YAMASHISHI LAB】管理者からの返信メッセージ", f"{mem_name} 様\n\n{qr_txt.strip()}", category="管理者返信")
                        st.success(f"✅ {mem_name} 様へ返信しました！")
                        st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    with adm_tab3:
        st.caption("🛡️ 永久BANされたユーザーが別名・別メールアドレスで再登録やログイン（なりすまし）を試みた場合、端末フィンガープリント(FP)・ブラウザ環境指紋(HFP)・PINハッシュから自動検知して遮断し、以下にリアルタイム記録します。")
        b_ems = sec.get("banned_emails", {})
        b_fps = sec.get("banned_fps", {})
        st.markdown(f"**💀 現在の永久BAN登録数:** メールアドレス `{len(b_ems)}件` ／ 監視端末指紋(FP/HFP) `{len(b_fps)}件`")
        if b_ems:
            for bem, binfo in list(b_ems.items()):
                c_b1, c_b2 = st.columns([3.5, 1])
                c_b1.markdown(f"💀 **{binfo.get('name','不明')}** (`{bem}`) ｜ BAN日時: {binfo.get('banned_at','-')} ｜ 端末FP: `{binfo.get('fp','-')}`")
                if c_b2.button("🔓 永久BAN解除", key=f"unban_{bem}", use_container_width=True):
                    sec.get("banned_emails", {}).pop(bem, None)
                    for fp_k in [k_fp for k_fp, v_fp in sec.get("banned_fps", {}).items() if v_fp.get("email"] == bem]:
                        sec["banned_fps"].pop(fp_k, None)
                    for pin_k in [k_p for k_p, v_p in sec.get("banned_pins", {}).items() if v_p == bem]:
                        sec["banned_pins"].pop(pin_k, None)
                    if bem in db:
                        db[bem]["status"] = "suspended"
                        save_j(FILES["mem"], db)
                    save_j(FILES["sec"], sec)
                    st.success(f"🔓 {bem} の永久BANを解除しました（状態：一時停止）。")
                    st.rerun()
        st.markdown("---")
        st.markdown("#### 🚨 なりすまし再登録・不正アクセス監視ログ")
        s_logs = sec.get("spoof_logs", [])
        if not s_logs:
            st.info("現在、永久BAN対象者によるなりすまし再登録や不正アクセスの検知ログはありません。")
        else:
            if st.button("🧹 監視ログをクリア", key="clr_spoof_logs"):
                sec["spoof_logs"] = []
                save_j(FILES["sec"], sec)
                st.rerun()
            for sl in s_logs[:50]:
                st.markdown(
                    f'<div style="background:rgba(239,68,68,0.12);border-left:4px solid #ef4444;border-radius:8px;padding:8px 11px;margin-bottom:6px;font-size:12px;">'
                    f'<div style="display:flex;justify-content:space-between;color:#fca5a5;font-weight:800;"><span>{sl.get("action","🚨 遮断")}</span><span>{sl.get("time","")}</span></div>'
                    f'<div style="color:#f8fafc;margin-top:3px;">試行名: <b>{sl.get("input_name","")}</b> ｜ 試行アドレス: <code>{sl.get("input_email","")}</code> ｜ 元BAN対象: <code>{sl.get("orig_banned_email","")}</code></div>'
                    f'<div style="color:#cbd5e1;font-size:11px;margin-top:2px;">検知理由: <b style="color:#fde047;">{sl.get("reason","")}</b> ｜ 端末FP: <code>{sl.get("fp","")}</code> / HFP: <code>{sl.get("raw_hfp","")}</code></div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
    st.stop()

def norm_tk(raw: str) -> str:
    s = unicodedata.normalize("NFKC", raw).strip().upper()
    return f"{s}.T" if len(s) == 4 and any(c.isdigit() for c in s) and "." not in s else s

@st.cache_data(ttl=900)
def fetch_macro():
    tks = {"sp500": ("^GSPC", "🇺🇸 S&P500"), "sox": ("^SOX", "💽 米SOX"), "usdjpy": ("JPY=X", "💴 ドル円"), "nk_fut": ("NIY=F", "🇯🇵 日経先物"), "vix": ("^VIX", "⚡ VIX")}
    res = {}
    try:
        raw = yf.download(list(c for c, _ in tks.values()), period="5d", group_by="ticker", threads=True, progress=False, timeout=5)
        for k, (c, lbl) in tks.items():
            try:
                d = raw[c].dropna(subset=["Close"])
                lc, pc = float(d["Close"].iloc[-1]), float(d["Close"].iloc[-2])
                res[k] = {"price": lc, "diff": round((lc - pc) / pc * 100, 2), "label": lbl}
            except Exception: res[k] = {"price": 0.0, "diff": 0.0, "label": lbl}
    except Exception:
        for k, (_, lbl) in tks.items(): res[k] = {"price": 0.0, "diff": 0.0, "label": lbl}
    return res

def compute_quantum_wave_metrics(c: np.ndarray, h: np.ndarray, l: np.ndarray, v: np.ndarray) -> dict:
    n = min(len(c), 25)
    cw, hw, lw, vw = c[-n:], h[-n:], l[-n:], v[-n:]
    rets = np.diff(cw) / np.maximum(cw[:-1], 1e-4)
    if len(rets) < 8: return {"q_score": 75, "q_tunnel": 72.0, "q_coherence": 70.0, "q_entropy": 0.40, "q_state": "量子トンネル突破・超伝導モード"}
    vol_norm = vw[1:] / max(float(np.mean(vw[1:])), 1.0)
    amp = np.sqrt(np.clip(vol_norm, 0.1, 4.0))
    std_r = max(float(np.std(rets)), 1e-4)
    phase = np.arctan2(rets, std_r) + (np.pi / 4.0) * np.sign(rets)
    psi_real, psi_imag = amp * np.cos(phase), amp * np.sin(phase)
    coh_mag = np.sqrt(np.mean(psi_real[-8:])**2 + np.mean(psi_imag[-8:])**2) / max(float(np.mean(amp[-8:])), 1e-4)
    dir_bias = 1.0 if np.mean(rets[-5:]) >= 0 else -0.5
    q_coherence = round(float(np.clip((coh_mag * 78.0) + (dir_bias * 12.0) + 15.0, 35.0, 99.0)), 1)
    v_barrier = max(float(np.max(hw[-20:]) - cw[-1]) / max(float(cw[-1]), 1e-4), 0.0)
    e_kinetic = max(float(np.mean(np.abs(rets[-5:]) * vol_norm[-5:])) * 1.85, 1e-4)
    if v_barrier <= 0.002 or e_kinetic >= v_barrier:
        q_tunnel = round(float(np.clip(84.0 + min(e_kinetic * 400.0, 15.0), 75.0, 99.2)), 1)
    else:
        kappa_w = np.sqrt(max(v_barrier - e_kinetic, 0.0)) / max(e_kinetic, 0.003)
        q_tunnel = round(float(np.clip(np.exp(-0.45 * kappa_w) * 100.0 + 20.0, 45.0, 96.0)), 1)
    z_r, z_v = (rets - np.mean(rets)) / std_r, (vol_norm - np.mean(vol_norm)) / max(float(np.std(vol_norm)), 1e-4)
    cov = np.cov(np.vstack([z_r, z_v]))
    rho = cov / max(float(np.trace(cov)), 1e-4)
    eigvals = np.clip(np.linalg.eigvalsh(rho), 1e-6, 1.0)
    eigvals = eigvals / np.sum(eigvals)
    q_entropy = round(float(np.clip(-float(np.sum(eigvals * np.log(eigvals))) / np.log(2.0), 0.05, 0.99)), 2)
    q_score = int(np.clip(round(q_tunnel * 0.45 + q_coherence * 0.35 + (1.0 - q_entropy) * 25.0 + 10), 45, 99))
    q_state = "⚛️ 量子トンネル突破・超伝導モード" if (q_tunnel >= 70.0 and q_coherence >= 60.0) else ("✨ 波動関数収束・コヒーレント増幅" if (q_entropy <= 0.55 and q_coherence >= 55.0) else ("⚡ 励起状態（障壁突破カウントダウン）" if q_tunnel >= 60.0 else "🌊 量子重ね合わせ（押し目干渉待ち）"))
    return {"q_score": q_score, "q_tunnel": q_tunnel, "q_coherence": q_coherence, "q_entropy": q_entropy, "q_state": q_state}

def compute_inst_microstructure(c: np.ndarray, h: np.ndarray, l: np.ndarray, v: np.ndarray) -> dict:
    n = min(len(c), 30)
    cw, hw, lw, vw = c[-n:], h[-n:], l[-n:], v[-n:]
    rets = np.diff(cw) / np.maximum(cw[:-1], 1e-4)
    if len(rets) < 10:
        return {"ms_score": 78, "hurst": 0.62, "kyle_stealth": 82.0, "luld_magnet": 75.0, "ms_regime": "🏛️ 機関TWAP/氷山ステルス吸収＆強トレンド持続"}
    dev = np.cumsum(rets - np.mean(rets))
    r_val = float(np.max(dev) - np.min(dev))
    s_val = max(float(np.std(rets)), 1e-5)
    hurst = round(float(np.clip(np.log(max(r_val / s_val, 1.05)) / np.log(len(rets)) + 0.1, 0.45, 0.92)), 2)
    vol_norm = vw[1:] / max(float(np.mean(vw[1:])), 1.0)
    lam_recent = np.mean(np.abs(rets[-5:]) / np.maximum(vol_norm[-5:], 0.2))
    lam_base = max(float(np.mean(np.abs(rets) / np.maximum(vol_norm, 0.2))), 1e-4)
    cl_pos = float(np.mean((cw[-5:] - lw[-5:]) / np.maximum(hw[-5:] - lw[-5:], 1e-4)))
    kyle_stealth = round(float(np.clip((1.15 - min(lam_recent / lam_base, 1.0)) * 55.0 + cl_pos * 42.0 + 25.0, 40.0, 99.0)), 1)
    atr_pct = float(np.mean((hw[-10:] - lw[-10:]) / np.maximum(cw[-10:], 1e-4))) * 100.0
    last_ret = float(rets[-1] * 100.0)
    luld_magnet = round(float(np.clip(50.0 + last_ret * 6.5 + (cl_pos - 0.5) * 35.0 + min(atr_pct * 2.5, 18.0) + 15.0, 35.0, 99.0)), 1)
    ms_score = int(np.clip(round(kyle_stealth * 0.42 + (hurst * 100.0) * 0.33 + luld_magnet * 0.25 + 8), 45, 99))
    if ms_score >= 72 and hurst >= 0.50: ms_regime = "🏛️ 機関TWAP/氷山ステルス吸収＆強トレンド持続"
    elif luld_magnet >= 70.0: ms_regime = "🧲 LULD値幅上限マグネット吸引（踏み上げ加速）"
    elif hurst < 0.46: ms_regime = "🔄 マーケットメイカー平均回帰・押し目吸収圏"
    else: ms_regime = "⚖️ 機関アルゴリズム順張り巡航モード"
    return {"ms_score": ms_score, "hurst": hurst, "kyle_stealth": kyle_stealth, "luld_magnet": luld_magnet, "ms_regime": ms_regime}

def select_dynamic_strategy(code: str, style: str, tot_win: float, expect_pct: float, ofi_z: float, vpin: float, yz_vol: float, cvar95: float, rsi: float, cpos: float, base_sh: int, pest_str: str, vwap_str: str, tp_str: str, sl_str: str, kelly_pct: float, qm: dict, ms: dict) -> dict:
    st_prefix = style.split(" ")[1] if " " in style else "デイトレード"

    if st_prefix == "スキャルピング":
        sh = max(1, int(round(base_sh * 1.5)))
        return {
            "algo_name": f"⚡ [{st_prefix}] 瞬足OFI板掃き上げ・1分足モメンタム一気貫通型",
            "risk_posture": f"🚀 スキャルピング全開（寄付きと同時に <b>{sh:,}株</b> で一気に板を抜く）",
            "core_logic": f"{st_prefix}特有の高速回転を狙うため、OFI（板の買い越し +{ofi_z:.2f}σ）とLULD引力（{ms['luld_magnet']}%）が急加速している特異点で即座にエントリー。数分〜数十分の急伸をスナイプします。",
            "adj_shares": sh,
            "step_plan": f"① 9:00寄付き直後の1分足で <b>{sh:,}株</b> 成行即時突撃 → ② 数ティック上の <b>{tp_str}</b> 到達で機械的利確",
            "beginner_html": f"<b>🔰 スキャルピング実践手順（⚡ 寄付き直後の数分で利確！）</b><br>① <b>【エントリー】</b> 朝9:00のスタートと同時に <b>{sh:,}株</b> を迷わず買います。<br>② <b>【利確・損切】</b> スキャルピングはスピード命です。数分で動く <b>{tp_str}</b> で利確し、逆指値 <b>{sl_str}</b> は必ずタイトに設定してください。"
        }

    elif st_prefix == "スイングトレード":
        sh = max(1, int(round(base_sh * 1.2)))
        l1, l2 = max(1, int(round(sh * 0.6))), max(0, sh - max(1, int(round(sh * 0.6))))
        return {
            "algo_name": f"📈 [{st_prefix}] 機関トレンドフォロー・押し目ピラミッディング型",
            "risk_posture": f"🏛️ スイング本玉買い（初回 <b>{l1:,}株</b> ＋ 2日目押し目 <b>{l2:,}株</b>）",
            "core_logic": f"Hurst指数 {ms['hurst']}（トレンド継続性高）と機関Kyleステルス吸収（{ms['kyle_stealth']}%）が一致。数日間〜1週間かけてじっくり上値を追うスイングの王道フォーメーション。",
            "adj_shares": sh,
            "step_plan": f"① 初回 <b>{l1:,}株（60%）</b> 取得 → ② 2〜3日後のVWAP押し目で残りの <b>{l2:,}株（40%）</b> を追加",
            "beginner_html": f"<b>🔰 スイングトレード実践手順（📈 数日〜1週間のトレンドに乗る！）</b><br>① 初日は資金の半分強（<b>{l1:,}株</b>）を買ってポジションを作ります。<br>② 数日後に少し下がったところで残りの <b>{l2:,}株</b> を買い増し、目標の <b>{tp_str}</b> までゆったり保有します。"
        }

    sh = max(1, int(round(base_sh * 1.65)))
    return {
        "algo_name": f"🔥 [{st_prefix}] 情報精度S級・全ツッパ一括特攻型アルゴリズム",
        "risk_posture": f"👑 全ツッパ・フルベット（ <b>{sh:,}株を100%一括投入</b> ）",
        "core_logic": f"期待度 <b>{expect_pct}%</b>・量子Qスコア {qm['q_score']}点・機関Kyleステルス吸収 {ms['kyle_stealth']}% が完全一致し、95%CVaRも -{cvar95}% と極めて低いS級特異点。分割せず寄り付き一括で最高期待値を抜き取る戦術。",
        "adj_shares": sh,
        "step_plan": f"① 9:00寄付き（{pest_str}目安）で <b>全ロット {sh:,}株（100%全ツッパ）</b> 成行一括投入 → ② 逆指値（{sl_str}）を同時セットし、目標（{tp_str}）まで一気抜き",
        "beginner_html": f"<b>🔰 デイトレード実践手順（🔥 精度S級・迷わず1回で全ツッパ！）</b><br>① 朝9:00の寄り付きで <b>「{sh:,}株」を1回でまとめて購入</b> します。<br>② 買えたらすぐに <b>「損切り：{sl_str}」</b> を入れ、目標の <b>{tp_str}</b> 到達で利益確定！"
    }

def analyze_df(df_raw, code, name, theme, genre, macro, b5_live_map, style, bi=True, b5=True, bal=True, bms=True):
    try:
        if df_raw is None or df_raw.empty: return None
        df = df_raw.dropna(subset=["Close", "Open", "High", "Low", "Volume"]).copy()
        if len(df) < 30: return None
        c, o, h, l, v = df["Close"].values.astype(float), df["Open"].values.astype(float), df["High"].values.astype(float), df["Low"].values.astype(float), df["Volume"].values.astype(float)
        df["Prev_Close"] = df["Close"].shift(1)
        df["Day_Return"] = (df["Close"] - df["Prev_Close"]) / df["Prev_Close"] * 100
        df["MA20"] = df["Close"].rolling(20).mean()
        df["Vol_Ratio"] = (df["Volume"] / df["Volume"].rolling(20).mean().replace(0, np.nan)).fillna(1.0)
        df["Vol_Accel_5d"] = (df["Volume"] / df["Volume"].rolling(5).mean().replace(0, np.nan)).fillna(1.0)

        dlt = df["Close"].diff()
        g_r, l_r = dlt.clip(lower=0).ewm(alpha=1/14, adjust=False).mean(), (-dlt.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        df["RSI"] = (100 - (100 / (1 + g_r / l_r.replace(0, np.nan)))).fillna(50.0)
        tr = pd.concat([df["High"] - df["Low"], (df["High"] - df["Prev_Close"]).abs(), (df["Low"] - df["Prev_Close"]).abs()], axis=1).max(axis=1)
        df["ATR"] = tr.rolling(14).mean().fillna(df["Close"] * 0.02)

        hl = (df["High"] - df["Low"]).replace(0, np.nan)
        df["Close_Pos"] = ((df["Close"] - df["Low"]) / hl).fillna(0.5)
        df["VWAP20"] = (((df["High"] + df["Low"] + df["Close"]) / 3.0 * df["Volume"]).rolling(20).sum() / df["Volume"].rolling(20).sum().replace(0, np.nan)).fillna(df["Close"])
        df["VPIN_5d"] = (((df["Close"] - df["Open"]) / hl).fillna(0.0) * df["Vol_Ratio"]).rolling(5).mean().fillna(0.0)

        hl_r = np.maximum(h - l, 1e-4)
        sf = ((2.0 * c - h - l) / hl_r) * v
        ofi_z = round(float(np.clip((np.mean(sf[-5:]) - np.mean(sf[-20:])) / max(float(np.std(sf[-20:])) , 1.0) + 0.5, -3.5, 3.5)), 2)
        rets = np.diff(c) / np.maximum(c[:-1], 1e-4) * 100.0
        q05 = np.percentile(rets, 5)
        cvar95 = round(float(abs(np.mean(rets[rets <= q05]))) if any(rets <= q05) else abs(float(q05)), 2)
        yz_vol = round(float(np.std(rets[-20:]) * np.sqrt(252)), 1)
        eff_pct = int(np.clip(round((abs(c[-1] - c[-15]) / max(float(np.sum(np.abs(np.diff(c[-15:])))), 1e-4)) * 140.0 + 15), 20, 98))

        qm = compute_quantum_wave_metrics(c, h, l, v)
        ms = compute_inst_microstructure(c, h, l, v)

        df["Next_Open"], df["Next_Close"] = df["Open"].shift(-1), df["Close"].shift(-1)
        df["Gap_Pct"] = (df["Next_Open"] - df["Close"]) / df["Close"] * 100
        df["Morning_Up"], df["Intraday_Up"] = df["Next_Open"] > df["Close"], df["Next_Close"] > df["Next_Open"]

        lat = df.iloc[-1]; hist = df.iloc[:-1].dropna(subset=["Next_Open", "Next_Close", "MA20"])
        if len(hist) < 5: return None
        vpin, vacc, cpos, rsi_v = float(lat["VPIN_5d"]), float(lat["Vol_Accel_5d"]), float(lat["Close_Pos"]), round(float(lat["RSI"]), 1)
        isc = int(np.clip(round(72 + vpin * 36 +ofi_z * 6.5 + (cpos - 0.5) * 20), 45, 99))
        b5_hits = (b5_live_map or {}).get(code, {}).get("hits", 0)
        b5sc = int(np.clip(round(70 + (min(vacc, 3.0) - 1.0) * 18 + (cpos - 0.5) * 28 + b5_hits * 2.5), 45, 99))

        sub = hist[hist["Day_Return"] > 0] if lat["Day_Return"] > 0 else hist[hist["Day_Return"] <= 0]
        if len(sub) < 5: sub = hist
        prob = round(float(sub["Morning_Up"].mean() * 100), 1)
        i_win = round(float(sub["Intraday_Up"].mean() * 100), 1)
        t_win = round(float((hist["Morning_Up"] | hist["Intraday_Up"]).mean() * 100), 1)
        tot_win = round(prob * 0.38 + i_win * 0.22 + t_win * 0.15 + qm["q_score"] * 0.13 + ms["ms_score"] * 0.12, 1)

        agap = round(float(sub["Gap_Pct"].mean()), 2)
        wg, lg = sub[sub["Morning_Up"]]["Gap_Pct"], sub[~sub["Morning_Up"]]["Gap_Pct"]
        awin, aloss = (float(wg.mean()) if len(wg) > 0 else 0.6), (abs(float(lg.mean())) if len(lg) > 0 else 0.5)
        payoff, edge = round(awin / max(aloss, 0.15), 2), round((tot_win / 100 * awin) - ((100 - tot_win) / 100 * aloss), 2)
        kelly_pct = round(float(np.clip(((tot_win/100.0) - ((1.0 - tot_win/100.0) / max(payoff, 0.2))) * 50.0, 5.0, 38.0)), 1)

        is_jp = ".T" in code
        ov = ((macro["nk_fut"]["diff"] if macro else 0.0) * 0.5 + (macro["sox"]["diff"] if macro else 0.0) * 0.4) if is_jp else ((macro["sp500"]["diff"] if macro else 0.0) * 0.5 + (macro["sox"]["diff"] if macro else 0.0) * 0.4)
        pgap = round(agap * 0.5 + ov * 0.5 + max(0.0, (isc - 55) * 0.025), 2)
        cv, atrv = float(lat["Close"]), float(lat["ATR"])
        pest = cv * (1.0 + pgap / 100.0)

        q_part = qm["q_score"] if bal else 72
        i_part = isc if bi else 70
        m_part = ms["ms_score"] if bms else 72
        b_part = b5sc if b5 else 68
        aisc = int(np.clip(round(tot_win * 0.34 + q_part * 0.22 + m_part * 0.20 + i_part * 0.14 + b_part * 0.10 + 12), 55, 99))
        expect_pct = round(float(np.clip(aisc * 0.42 + q_part * 0.22 + m_part * 0.20 + tot_win * 0.16 + min(edge * 4.5, 8.0) - max(cvar95 - 3.2, 0.0) * 1.8 + 10.0, 65.0, 99.4)), 1)

        tval = expect_pct * 0.50 + aisc * 0.30 + tot_win * 0.20
        for th, tn, tl, tc, tbg in [
            (82, 10, "【Lv.10：🔥情報精度S級・全ツッパ推奨】量子×機関氷山吸収極大", "#fff", "linear-gradient(90deg,#7e22ce,#dc2626)"),
            (76, 9, "【Lv.9：⚡超強気買い】量子トンネル突破＆機関アルゴ集中", "#fff", "linear-gradient(90deg,#0369a1,#1d4ed8)"),
            (70, 8, "【Lv.8：⭕買い推奨】機関ステルス買い集め・順張り優位", "#fff", "linear-gradient(90deg,#0f766e,#047857)"),
            (64, 7, "【Lv.7：⭕押し目買い】VWAP反発・波動干渉狙い", "#e2e8f0", "linear-gradient(90deg,#334155,#1e293b)"),
            (-99, 5, "【Lv.5：👀様子見・選別】方向感確認・少額打診", "#cbd5e1", "linear-gradient(90deg,#1e293b,#0f172a)")
        ]:
            if tval >= th: t_num, t_lbl, t_col, t_bg = tn, tl, tc, tbg; break

        tpv, slv = max(pest, cv) + (atrv * 0.95), cv - (atrv * 0.55)
        rmoney = total_capital * (risk_tolerance_pct / 100.0)
        base_sh = max(1, int(rmoney / max(cv - slv, cv * 0.005)))
        fp = lambda val: f"{val:,.0f}円" if is_jp else f"${val:,.2f}"

        strat = select_dynamic_strategy(code.replace(".T", ""), style, tot_win, expect_pct, ofi_z, round(vpin, 2), yz_vol, cvar95, rsi_v, cpos, base_sh, fp(pest), fp(float(lat["VWAP20"])), f"{fp(tpv)}(+{round((tpv-cv)/cv*100,1)}%)", f"{fp(slv)}({round((slv-cv)/cv*100,1)}%)", kelly_pct, qm, ms)
        adj_sh = strat["adj_shares"]

        return {
            "full_code": code, "code": code.replace(".T", ""), "name": name, "genre": genre, "theme": theme, "price": fp(cv), "raw_close": cv,
            "tp_price": fp(tpv), "tp_pct": round((tpv - cv) / cv * 100, 1), "sl_price": fp(slv), "sl_pct": round((slv - cv) / cv * 100, 1), "vwap_price": fp(float(lat["VWAP20"])),
            "inst_score": isc, "vpin": round(vpin, 2), "ofi_z": ofi_z, "yz_vol": yz_vol, "cvar95": cvar95, "eff_pct": eff_pct, "kelly_pct": kelly_pct,
            "q_score": qm["q_score"], "q_tunnel": qm["q_tunnel"], "q_coherence": qm["q_coherence"], "q_entropy": qm["q_entropy"], "q_state": qm["q_state"],
            "ms_score": ms["ms_score"], "hurst": ms["hurst"], "kyle_stealth": ms["kyle_stealth"], "luld_magnet": ms["luld_magnet"], "ms_regime": ms["ms_regime"],
            "expect_pct": expect_pct, "board5ch_score": b5sc, "b5_hits": b5_hits, "pts_est_price": fp(pest), "pts_gap_pct": pgap, "diff": round(float(lat["Day_Return"]), 2),
            "prob": prob, "intraday_win_rate": i_win, "trend_win_rate": t_win, "total_win_rate": tot_win, "count": f"{int(sub['Morning_Up'].sum())}/{len(sub)}回",
            "rsi": rsi_v, "payoff": payoff, "edge": edge, "ai_score": aisc, "survival_power": round(expect_pct * 0.45 + aisc * 0.30 + ms["ms_score"] * 0.25, 1),
            "tier_num": t_num, "tier_label": t_lbl, "tier_color": t_col, "tier_bg": t_bg,
            "lot_info": {"shares": adj_sh, "position_value": adj_sh * cv, "risk_amount": rmoney},
            "strat": strat
        }
    except Exception: return None

@st.cache_data(ttl=1800)
def fetch_pool_batch(macro, b5_live_map, style, bi, b5, bal, bms):
    codes = list({s["code"] for sts in STOCK_POOL.values() for s in sts})
    raw = yf.download(codes, period="6mo", group_by="ticker", threads=True, progress=False, timeout=9)
    gmap, alist, seen = {g: [] for g in STOCK_POOL.keys()}, [], set()
    for g, sts in STOCK_POOL.items():
        for s in sts:
            c = s["code"]
            try:
                r = analyze_df(raw[c] if len(codes) > 1 else raw, c, s["name"], s["theme"], g, macro, b5_live_map, style, bi, b5, bal, bms)
                if r:
                    gmap[g].append(r)
                    if c not in seen: alist.append(r); seen.add(c)
            except Exception: continue
    return gmap, alist

@st.cache_data(ttl=300)
def fetch_one(code, macro, b5_live_map, style, bi, b5, bal, bms):
    inf = KNOWN_STOCKS.get(code, {"name": code.replace(".T", ""), "theme": "個別指定銘柄", "genre": "個別検索"})
    return analyze_df(yf.Ticker(code).history(period="6mo"), code, inf["name"], inf["theme"], inf["genre"], macro, b5_live_map, style, bi, b5, bal, bms)

@st.cache_data(ttl=300)
def fetch_5m(full_code):
    try:
        d5 = yf.Ticker(full_code).history(period="5d", interval="5m")
        if d5 is None or len(d5) < 10: return None
        d5 = d5.dropna(subset=["Close", "Open", "High", "Low", "Volume"])
        dts = d5.index.date; day = d5[dts == dts[-1]].copy()
        if len(day) < 6: day = d5.tail(36).copy()
        tp = (day["High"] + day["Low"] + day["Close"]) / 3.0
        day["VWAP"] = ((tp * day["Volume"]).cumsum() / day["Volume"].cumsum().replace(0, np.nan)).fillna(day["Close"])
        lv = float(day["VWAP"].iloc[-1])
        cdf = pd.DataFrame({"Time": day.index.strftime("%H:%M"), "Open": day["Open"].astype(float).values, "High": day["High"].astype(float).values, "Low": day["Low"].astype(float).values, "Close": day["Close"].astype(float).values, "VWAP": day["VWAP"].astype(float).values, "BarColor": np.where(day["Close"].values >= day["Open"].values, "陽線", "陰線")})
        return {"vwap5_price": f"{lv:,.0f}円" if ".T" in full_code else f"${lv:,.2f}", "chart_date": str(dts[-1]), "chart_df": cdf}
    except Exception: return None

def run_7ai_council(r: dict, m5=None, seed: int = 0, user_query: str = "") -> dict:
    vref = m5["vwap5_price"] if m5 else r["vwap_price"]
    st_info = r["strat"]
    fs = r["ai_score"]
    act_ais = get_active_ai_providers()
    n_ai = len(act_ais)
    news_list = fetch_global_impact_news()
    recent_news_snippet = news_list[0]["title"] if news_list else "AI半導体・次世代データセンター光配線に資金流入加速"

    usr_p = (
        f"銘柄:{r['name']}({r['code']}) 現在値:{r['price']} 前日比:{r['diff']}% 期待度:{r['expect_pct']}% 統合勝率:{r['total_win_rate']}% "
        f"量子Qスコア:{r['q_score']} トンネル突破率:{r['q_tunnel']}% 機関ミクロ構造スコア:{r['ms_score']}(Kyleステルス吸収:{r['kyle_stealth']}% / Hurst指数:{r['hurst']} / LULD引力:{r['luld_magnet']}%) "
        f"OFI:{r['ofi_z']:+.2f}σ VPIN:{r['vpin']:+.2f} 95%CVaR:-{r['cvar95']}% 基準VWAP:{vref} 採用戦略:{st_info['algo_name']} 執行:{st_info['step_plan']} "
        f"直近市場ヘッドライン:{recent_news_snippet}"
    )
    if user_query:
        usr_p += f"\n\n【ユーザーからの直近の質問・発言・雑談】\n{user_query}\n※このユーザーからの質問や発言（車の車種や任意の疑問、雑談など）に対して、各専門家がそれぞれの専門視点を絡めながら、絶対に完全にリアルタイムで深く返答・ツッコミ・議論に織り込んでください。"

    turns = []
    if n_ai >= 2:
        mode_title = get_debate_mode_badge(n_ai)
        turns.append({"round": f"{mode_title} ｜ 『{r['name']}』期待度 {r['expect_pct']}%"})
        roles_by_idx = [
            f"量子波動＆機関オーダーフロー強気の視点から『{r['name']}』の優位性を個別に分析し、具体的な買い方と目標株価を主張せよ。ユーザーからの直近の質問・発言({user_query if user_query else 'なし'})にも熱心に言及せよ。",
            f"機関投資家のミクロ構造（Kyleのラムダ・Hurst指数 {r['hurst']}・VWAP {vref}）の視点から先行意見に切り込み、市場の揺さぶりに耐える執行手順を論じよ。ユーザーの質問({user_query if user_query else 'なし'})にもツッコミを入れよ。",
            f"テールリスク監査（95%CVaR -{r['cvar95']}%・逆指値 {r['sl_price']}）の視点から下値リスクを厳しく突っ込み、勝率を極大化する条件を提示せよ。ユーザーの質問({user_query if user_query else 'なし'})にも言及せよ。",
            "マクロ先物連動・セクター資金波及の視点から上値余地を評価せよ。",
            "統計バックテスト・ケリー基準の資金配分視点からロット戦略を評価せよ。",
            f"リアルタイム需給（OFI {r['ofi_z']:+.2f}σ・LULD引力 {r['luld_magnet']}%）の視点から短期爆発力を評価せよ。",
            "全AIの議論を統合する議長として、ユーザーの質問への回答も含めた最終結論と明日の執行プランを総括せよ。"
        ]
        sys_multi = 'あなたは一流の金融クオンツAIトレーダーであり、人間味あふれる感情や熱量を持って討論する。ユーザーの質問や雑談（車の車種や任意の疑問など）が入力されている場合は、その話題に熱心かつ柔軟に返答・ツッコミを入れつつ、銘柄分析を論じよ。JSON {"score":90,"tone":"agree","text":"..."} のみ出力せよ。toneは agree, normal, doubt, rage のいずれか。'

        def _task(idx, p_tuple):
            pk, plbl, pmod, pkey = p_tuple
            role_txt = roles_by_idx[idx % len(roles_by_idx)]
            j_res, _ = call_single_provider_api(pk, pmod, pkey, sys_multi, usr_p + f"\n【あなたの担当役割】{role_txt}", 0.82)
            if j_res and isinstance(j_res.get("text"), str) and j_res["text"].strip():
                return idx, {"speaker": f"{plbl} ({pmod})", "score": int(j_res.get("score", fs)), "tone": j_res.get("tone", "agree"), "text": j_res["text"]}

            if user_query:
                fb_text = f"おっ、ユーザーが「{user_query}」って聞いてきたな！その話題も最高だが、相場のほうも『{r['name']}』が期待度 <b>{r['expect_pct']}%</b> で <b>{st_info['algo_name']}</b> を発動させてるから見逃せないぜ！"
            else:
                fb_text = f"『{r['name']}』の期待度 <b>{r['expect_pct']}%</b> は伊達じゃないぜ！量子トンネル突破率 <b>{r['q_tunnel']}%</b> の波及エネルギーで <b>{st_info['algo_name']}</b> を完遂するぞ！"
            return idx, {"speaker": f"{plbl} ({pmod})", "score": fs, "tone": "agree" if idx % 2 == 0 else "doubt", "text": fb_text}

        task_list = [(0, act_ais[0]), (1, act_ais[1]), (2, act_ais[0]), (3, act_ais[1])] if n_ai == 2 else [(i, p) for i, p in enumerate(act_ais)]
        results = {}
        with ThreadPoolExecutor(max_workers=min(len(task_list), 7)) as ex:
            futs = [ex.submit(_task, idx, pt) for idx, pt in task_list]
            for f in as_completed(futs):
                try:
                    k_idx, val = f.result()
                    results[k_idx] = val
                except Exception: continue
        for k_idx in sorted(results.keys()):
            turns.append(results[k_idx])
    else:
        sys_p = f'あなたは人間味と感情（熱狂、懐疑、怒り、ユーモア）を持つ7人のクオンツ専門家だ。『{r["name"]}』のデータや戦略に基づき討論する。ユーザーの質問や雑談({user_query if user_query else "なし"})が入力された場合は、その話題に合わせた自然な会話やツッコミを必ずすべての専門家が熱心に混ぜよ。6ターンのJSON {{"final_score":{fs},"turns":[{{"speaker_key":"QUANTUM","score":92,"tone":"agree","text":"..."}}]}} を出力せよ。'
        llm_j, used_eng = (call_single_provider_api(act_ais[0][0], act_ais[0][2], act_ais[0][3], sys_p, usr_p, 0.82) if n_ai == 1 else (None, "内蔵量子＆機関ミクロ推論エンジン"))

        if llm_j and isinstance(llm_j.get("turns"), list) and len(llm_j["turns"]) >= 4:
            raw_t = llm_j["turns"]
        else:
            if user_query:
                raw_t = [
                    {"speaker_key": "QUANTUM", "score": r["q_score"], "tone": "agree", "text": f"おいおい、ユーザーが「<b>{user_query}</b>」なんてめちゃくちゃ面白い話題を振ってきたぞ！車の車種や趣味の話も最高だが、『{r['name']}』の量子波動エネルギーも負けちゃいないぜ！期待度 <b>{r['expect_pct']}%</b> だ！"},
                    {"speaker_key": "MICRO", "score": r["ms_score"], "tone": "normal", "text": f"はは、QUANTUMはいきなりテンション高いな。だがユーザーの質問（{user_query}）にもしっかり答えつつ、Kyleステルス吸収 <b>{r['kyle_stealth']}%</b> や Hurst指数 <b>{r['hurst']}</b> の機関動向もしっかり解説しなきゃな。"},
                    {"speaker_key": "IGNIS", "score": r["board5ch_score"], "tone": "agree", "text": f"細かいことはいいんだよ！ユーザーの「{user_query}」っていう突撃質問も最高だし、 <b>{st_info['algo_name']}</b> が発動してるんだから、『<b>{st_info['risk_posture']}</b>』で全ツッパして盛り上がるぞ！"},
                    {"speaker_key": "TECHNOS", "score": fs, "tone": "normal", "text": f"IGNISは相変わらず血気盛んだな。数理的に見てもOFI <b>{r['ofi_z']:+.2f}σ</b> だ。ユーザーの話題（{user_query}）も受け止めつつ、基準VWAP（<b>{vref}</b>）の押し目を拾いながら冷静に行こうぜ。"},
                    {"speaker_key": "AEGIS", "score": 88, "tone": "doubt", "text": f"フッ、みんな楽しそうね。でもユーザーの質問({user_query})にも対応しつつ、95%CVaR（<b>-{r['cvar95']}%</b>）と逆指値 <b>{r['sl_price']}</b> は絶対に忘れないでちょうだいね！"},
                    {"speaker_key": "NEXUS", "score": fs, "tone": "agree", "text": f"よし、ユーザーからの「{user_query}」という素晴らしい問いかけも交えつつ、議論はまとまった！『{r['name']}』は期待度 <b>{r['expect_pct']}%</b> のもと、下記の実行プランで最高の利益を抜くぞ！"}
                ]
            else:
                raw_t = [
                    {"speaker_key": "QUANTUM", "score": r["q_score"], "tone": "agree", "text": f"おいみんな、『{r['name']}（{r['code']}）』の足元チャートを見たか！？直近の市場ニュースとも完全にリンクして、複素波動関数のエネルギーが爆発寸前だ！期待度 <b>{r['expect_pct']}%</b>、量子トンネル突破率はなんと <b>{r['q_tunnel']}%</b> に達しているぞ！"},
                    {"speaker_key": "MICRO", "score": r["ms_score"], "tone": "normal", "text": f"QUANTUM、興奮しすぎだ。だが確かに機関ミクロ構造のデータを見ると、Kyleの氷山ステルス吸収度が <b>{r['kyle_stealth']}%</b>、Hurst指数が <b>{r['hurst']}</b>（{r['ms_regime']}）を示している。水面下で機関の買い集めが着実に進んでいるのは事実だな。"},
                    {"speaker_key": "IGNIS", "score": r["board5ch_score"], "tone": "agree", "text": f"ははは、控えめに言うなよMICRO！ <b>{st_info['algo_name']}</b> が発動してるんだから、迷わず『<b>{st_info['risk_posture']}</b>』で特攻するに決まってるだろ！乗り遅れる奴は置いていくぜ！"},
                    {"speaker_key": "TECHNOS", "score": fs, "tone": "normal", "text": f"IGNIS、お前のその勢いだけのトレードはいつか痛い目を見るぞ。数理的に見ればOFI <b>{r['ofi_z']:+.2f}σ</b>・VPIN <b>{r['vpin']:+.2f}</b> だ。基準VWAP（<b>{vref}</b>）の押し目を冷静に拾うのが一番堅実だ。"},
                    {"speaker_key": "AEGIS", "score": 88, "tone": "doubt", "text": f"フッ、綺麗事ばかり言うな。95%CVaR（<b>-{r['cvar95']}%</b>）のテールリスクを舐めると痛い目を見るぞ。『{r['name']}』の逆指値 <b>{r['sl_price']}（{r['sl_pct']}%）</b> は絶対にずらすなよ！"},
                    {"speaker_key": "NEXUS", "score": fs, "tone": "agree", "text": f"よし、議論はそこまでだ！熱い議論だが全員の意見はまとまった。『{r['name']}』は期待度 <b>{r['expect_pct']}%</b> のもと、下記の実行プランで最高の利益を抜くぞ！"}
                ]

        turns.append({"round": f"⚛️ 『{r['name']}』量子QWM-7 × 機関ミクロ構造 専門AI合議 ({used_eng})"})
        for it in raw_t:
            sk = str(it.get("speaker_key", "NEXUS")).upper()
            turns.append({"speaker": AI_ROSTER.get(sk, f"👑 {sk}"), "score": int(it.get("score", fs)), "tone": it.get("tone", "normal"), "text": it.get("text", "")})

    r_name = r['name']
    r_expect = r['expect_pct']
    r_ms_regime = r['ms_regime']
    r_kyle = r['kyle_stealth']
    r_hurst = r['hurst']
    r_q_state = r['q_state']
    r_q_score = r['q_score']
    r_q_tunnel = r['q_tunnel']
    st_algo = st_info['algo_name']
    st_plan = st_info['step_plan']
    r_tp_price = r['tp_price']
    r_tp_pct = r['tp_pct']
    r_sl_price = r['sl_price']
    r_sl_pct = r['sl_pct']
    st_beginner = st_info['beginner_html']

    v_html = (
        f'<div style="margin-bottom:5px;"><b>🔥 『{r_name}』総合期待度：</b><span style="color:#fde047;font-size:14px;font-weight:900;">{r_expect}%</span> ｜ '
        f'<b>🏛️ 機関ミクロ構造：</b><span style="color:#a7f3d0;font-weight:800;">{r_ms_regime}（Kyle吸収 {r_kyle}% ／ Hurst指数 {r_hurst}）</span></div>'
        f'<div style="margin-bottom:5px;"><b>⚛️ 量子波動ステータス：</b><span style="color:#e9d5ff;font-weight:800;">{r_q_state}（量子Q {r_q_score}点 ／ トンネル突破率 {r_q_tunnel}%）</span></div>'
        f'<div style="margin-bottom:5px;"><b>🧬 採用買い方アルゴリズム：</b><span style="color:#38bdf8;font-weight:800;">{st_algo}</span></div>'
        f'<div style="margin-bottom:5px;"><b>⚡ プロ向け執行プラン：</b>{st_plan} ｜ 🎯利確 <b>{r_tp_price}(+{r_tp_pct}%)</b> ／ 🛡️損切 <b>{r_sl_price}({r_sl_pct}%)</b></div>'
        f'<div class="beginner-action-box">{st_beginner}</div>'
    )
    return {"final_score": fs, "dialogue": turns, "verdict_html": v_html}

def _fmt_turn(t: dict) -> str:
    if "round" in t: return f'<div class="round-divider">{t["round"]}</div>'
    if t.get("is_user"): return f'<div class="chat-bubble-user"><b>🗣️ あなた:</b> {t["text"]}</div>'
    b_cls = {"doubt": "chat-bubble-doubt", "rage": "chat-bubble-rage", "agree": "chat-bubble-agree"}.get(t.get("tone", "normal"), "chat-bubble-ai")
    return f'<div class="{b_cls}"><div style="font-weight:700;color:#38bdf8;font-size:11px;margin-bottom:2px;">{t["speaker"]} <span style="color:#94a3b8;">({t.get("score",85)}点)</span></div><div>{t["text"]}</div></div>'

@frag_dec
def render_council_sec(r, uk):
    is_open = st.session_state["active_debates"].get(uk, False)
    in_wl = r["code"] in st.session_state["watchlist"]
    c1, c2 = st.columns([2.7, 1.1])
    if c1.button("🔼 量子＆マルチAI合議と買い方ガイドを閉じる" if is_open else f"⚛️ {get_debate_mode_badge(len(get_active_ai_providers())).split(' ')[1]}＆買い方を見る", key=f"b_{uk}", use_container_width=True):
        st.session_state["active_debates"][uk] = not is_open; st.rerun()
    if c2.button("✅ 監視済" if in_wl else "⭐ 監視追加", key=f"w_{uk}", use_container_width=True):
        if in_wl: del st.session_state["watchlist"][r["code"]]
        else: st.session_state["watchlist"][r["code"]] = r
        st.rerun()
    if not is_open: return

    m5 = fetch_5m(r["full_code"])
    if m5 and show_5m_chart:
        st.caption(f"📅 直近5分足 ({m5['chart_date']}) ｜ 5分足VWAP: **{m5['vwap5_price']}**")
        cdf = m5["chart_df"]
        base = alt.Chart(cdf).encode(x=alt.X("Time:N", sort=None, title=None))
        cs = alt.Scale(domain=["陽線", "陰線"], range=["#10b981", "#ef4444"])
        w = base.mark_rule(size=1.5).encode(y=alt.Y("Low:Q", scale=alt.Scale(zero=False), title=None), y2="High:Q", color=alt.Color("BarColor:N", scale=cs, legend=None))
        b = base.mark_bar(size=6).encode(y=alt.Y("Open:Q", scale=alt.Scale(zero=False)), y2="Close:Q", color=alt.Color("BarColor:N", scale=cs, legend=None))
        vw = base.mark_line(color="#f59e0b", strokeWidth=2, strokeDash=[4, 2]).encode(y="VWAP:Q")
        st.altair_chart((w + b + vw).properties(height=140), use_container_width=True)

    if uk not in st.session_state["council_threads"]:
        deb = run_7ai_council(r, m5, st.session_state["debate_round_seed"].get(uk, 0), user_query="")
        st.session_state["council_threads"][uk] = list(deb["dialogue"])
        st.session_state["council_meta"][uk] = deb

    meta = st.session_state["council_meta"][uk]
    turns = st.session_state["council_threads"][uk]
    st.markdown(f'<div id="council_box_{uk}" class="ai-council-box"><div class="council-scroll-window">{"".join(_fmt_turn(t) for t in turns)}</div><div class="consensus-banner"><div style="font-weight:800;color:#fde047;font-size:12.5px;margin-bottom:5px;">🏛️ 量子×機関ミクロ構造 最終結論 ＆ 買い方アクションプラン</div>{meta["verdict_html"]}</div></div>', unsafe_allow_html=True)

    with st.form(f"jf_{uk}", clear_on_submit=True):
        jc1, jc2 = st.columns([3.2, 1])
        uop = jc1.text_input("質問・発言", placeholder=f"『{r['name']}』のAI議会に何でも質問・雑談しよう（例：車の車種何が好き？・最近の相場どう思う？ 等）", label_visibility="collapsed")
        if jc2.form_submit_button("💬 質問投下", use_container_width=True) and uop.strip():
            u_text = uop.strip()
            st.session_state["council_threads"][uk].append({"is_user": True, "text": u_text})

            deb_updated = run_7ai_council(r, m5, st.session_state["debate_round_seed"].get(uk, 0), user_query=u_text)
            st.session_state["council_threads"][uk] = list(deb_updated["dialogue"])
            st.session_state["council_meta"][uk] = deb_updated
            st.session_state["scroll_target_id"] = f"council_box_{uk}"
            st.rerun()

def render_card(r, is_custom=False, rank=None, kp="card"):
    dc = "#10b981" if r["diff"] >= 0 else "#ef4444"
    ds, ps = ("+" if r["diff"] > 0 else ""), ("+" if r["pts_gap_pct"] > 0 else "")
    rk_h = f'<span class="pill-badge" style="background:#f59e0b;color:#0f172a;border:none;">🏆 #{rank}</span>' if rank else ""
    lot = r["lot_info"]
    st_info = r["strat"]
    card_html = (
        f'<div class="{"search-result-card" if is_custom else "rank-card"}">'
        f'<div class="signal-10tier-badge" style="background:{r["tier_bg"]};color:{r["tier_color"]};"><span>{r["tier_label"]}</span><span>🔥 期待度 {r["expect_pct"]}% ｜ {st_info["algo_name"].split("】")[0]}】</span></div>'
        f'<div style="margin-bottom:7px;">{rk_h}<span class="pill-badge" style="background:rgba(250,204,21,0.18);border-color:#facc15;color:#fde047;font-weight:900;">🔥 期待度 {r["expect_pct"]}%</span><span class="quantum-badge">⚛️ 量子Q {r["q_score"]}点 (突破{r["q_tunnel"]}%)</span><span class="inst-badge">🏛️ 機関ミクロ {r["ms_score"]}点 (Kyle吸収{r["kyle_stealth"]}%)</span><span class="pill-badge">🧬 OFI {r["ofi_z"]:+.2f}σ</span></div>'
        f'<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;"><div style="min-width:0;flex:1;"><span style="font-size:16px;font-weight:800;color:#f8fafc;">{r["name"]}</span> <span style="font-size:11.5px;color:#94a3b8;">({r["code"]} / {r["genre"]})</span><div style="font-size:11px;color:#94a3b8;margin-top:2px;">{r["theme"]} ｜ 現在値: <b style="color:#f8fafc;">{r["price"]}</b> (<span style="color:{dc};font-weight:700;">{ds}{r["diff"]}%</span>)</div></div>'
        f'<div style="text-align:right;white-space:nowrap;flex-shrink:0;"><div style="font-size:9px;color:#fde047;font-weight:700;line-height:1.15;">🔥 AI期待度 / 統合勝率</div><div style="white-space:nowrap;line-height:1.2;margin-top:1px;"><span class="expect-badge">{r["expect_pct"]}%</span><span style="color:#64748b;font-size:12px;margin:0 2px;">/</span><span class="prob-badge">{r["total_win_rate"]}%</span></div><div style="font-size:9.5px;color:#94a3b8;">Payoff {r["payoff"]}x / Edge {r["edge"]:+.2f}%</div></div></div>'
        f'<div class="winrate-bar"><div><div style="font-size:9.5px;color:#fde047;">🔥 総合期待度</div><div style="font-size:12.5px;font-weight:900;color:#fef08a;">{r["expect_pct"]}%</div></div><div><div style="font-size:9.5px;color:#c084fc;">⚛️ 量子トンネル</div><div style="font-size:12.5px;font-weight:800;color:#e9d5ff;">{r["q_tunnel"]}%</div></div><div><div style="font-size:9.5px;color:#6ee7b7;">🏛️ 機関Kyle吸収</div><div style="font-size:12.5px;font-weight:800;color:#a7f3d0;">{r["kyle_stealth"]}%</div></div><div><div style="font-size:9.5px;color:#94a3b8;">🌅 翌朝GU / 陽線</div><div style="font-size:12px;font-weight:700;">{r["prob"]}% / {r["intraday_win_rate"]}%</div></div></div>'
        f'<div class="trade-plan-box"><div><div style="font-size:9.5px;color:#94a3b8;">🌅 夜間理論寄付き</div><div style="font-size:12px;font-weight:700;">{r["pts_est_price"]} ({ps}{r["pts_gap_pct"]}%)</div></div><div style="border-left:1px solid rgba(148,163,184,0.16);border-right:1px solid rgba(148,163,184,0.16);"><div style="font-size:9.5px;color:#10b981;">🎯 利確目標</div><div style="font-size:12px;font-weight:800;color:#10b981;">{r["tp_price"]} (+{r["tp_pct"]}%)</div></div><div><div style="font-size:9.5px;color:#f87171;">🛡️ 逆指値(損切)</div><div style="font-size:12px;font-weight:800;color:#f87171;">{r["sl_price"]} ({r["sl_pct"]}%)</div></div></div>'
        f'<div class="sizing-box"><span>📦 <b>推奨ロット: {lot["shares"]:,}株</b> ({st_info["risk_posture"].split("（")[0]}) ｜ 投資額 {lot["position_value"]:,.0f}円</span><span>基準VWAP: <b>{r["vwap_price"]}</b></span></div>'
        f'<details class="quant-detail-drawer"><summary>⚛️ 量子QWM-7 × 🏛️ 機関ミクロ構造(Kyleλ・Hurst) ＆ 買い方戦略詳細（タップで開閉）</summary>'
        f'<div style="font-size:11.5px;color:#cbd5e1;margin-top:5px;line-height:1.5;"><b>{st_info["algo_name"]}</b><br><span style="color:#a7f3d0;">{r["ms_regime"]}</span> ｜ <span style="color:#e9d5ff;">{r["q_state"]}</span><br>{st_info["core_logic"]}<br><b>▶ 買い方執行手順:</b> {st_info["step_plan"]}</div>'
        f'<div class="metrics-row"><span>期待度:{r["expect_pct"]}%</span><span>量子Q:{r["q_score"]}点</span><span>機関ミクロ:{r["ms_score"]}点</span><span>Kyle吸収:{r["kyle_stealth"]}%</span><span>Hurst指数:{r["hurst"]}</span><span>LULD引力:{r["luld_magnet"]}%</span><span>OFI:{r["ofi_z"]:+.2f}σ</span><span>95%CVaR:-{r["cvar95"]}%</span></div>'
        f'</details></div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)
    render_council_sec(r, f"{kp}_{r['code']}")

def render_ipo_offering_section():
    st.markdown('<div class="glass-header"><div style="font-size:15px;font-weight:800;color:#f8fafc;">🎟️ 新規上場 (IPO) ブックビルディング募集 ＆ 初値期待度ランキング</div><div style="font-size:11.5px;color:#94a3b8;margin-top:3px;">現在BB募集受付中・新規上場予定の注目IPO銘柄をAIクオンツがランク付け。各証券会社の抽選申込ページへ直通アクセスできます。</div></div>', unsafe_allow_html=True)
    for ipo in IPO_OFFERINGS:
        links_html = "".join([f'<a href="{url}" target="_blank" rel="noopener noreferrer" class="ipo-link-btn">🔗 {lbl}</a>' for lbl, url in ipo["links"]])
        st.markdown(
            f'<div class="rank-card" style="border-left-color:#f59e0b;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px;flex-wrap:wrap;gap:4px;">'
            f'<span class="pill-badge" style="background:#f59e0b;color:#0f172a;font-weight:900;">🏆 IPO期待度 第{ipo["rank"]}位 (期待度 {ipo["score"]}%)</span>'
            f'<span style="font-size:11px;color:#38bdf8;font-weight:700;">{ipo["tier"]}</span></div>'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<div><span style="font-size:16px;font-weight:800;color:#f8fafc;">{ipo["name"]}</span> <span style="font-size:11.5px;color:#94a3b8;">({ipo["code"]} / {ipo["market"]})</span><div style="font-size:11px;color:#cbd5e1;margin-top:2px;">🎯 {ipo["theme"]} ｜ 主幹事: <b>{ipo["lead"]}</b></div></div>'
            f'<div style="text-align:right;"><span style="font-size:9.5px;color:#94a3b8;">AI初値予測</span><br><span class="prob-badge" style="color:#10b981!important;">{ipo["expect_return"]}</span></div></div>'
            f'<div class="trade-plan-box" style="margin-top:7px;"><div><div style="font-size:9.5px;color:#94a3b8;">📅 BB抽選期間</div><div style="font-size:11.5px;font-weight:700;color:#fde047;">{ipo["bb_period"]}</div></div><div><div style="font-size:9.5px;color:#94a3b8;">🔔 上場日</div><div style="font-size:11.5px;font-weight:700;">{ipo["list_date"]}</div></div><div><div style="font-size:9.5px;color:#94a3b8;">💴 仮条件・公募価格</div><div style="font-size:11.5px;font-weight:700;">{ipo["price_band"]}</div></div></div>'
            f'<div style="margin-top:7px;">{links_html}</div></div>',
            unsafe_allow_html=True
        )

macro_info = fetch_macro()
b5_live_map = fetch_5ch_live()

BOOST_MAP = {
    "⚛️ 量子力学波動(QWM-7)": "algo",
    "🏛️ 機関最新アルゴ(Kyleλ・Hurst)": "ms",
    "🏦 機関VPIN・SmartMoney": "inst",
    "🔥 5ch実況＆短期モメンタム": "mom"
}

mpills = "".join([f'<div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);padding:2px 8px;border-radius:6px;font-size:10.5px;display:inline-flex;gap:4px;"><span style="color:#94a3b8;">{m["label"]}</span><span style="color:{"#10b981" if m["diff"]>=0 else "#ef4444"};font-weight:700;">{"+" if m["diff"]>=0 else ""}{m["diff"]}%</span></div>' for m in macro_info.values()])
st.markdown(
    f'<div class="glass-header">'
    f'<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">'
    f'<div style="min-width:0;flex:1;"><div class="brand-luxury">YAMASHISHI LAB</div><div class="brand-sub">QUANTUM WAVEFUNCTION & MULTI-AGENT TERMINAL</div></div>'
    f'<span style="background:rgba(168,85,247,0.16);border:1px solid rgba(168,85,247,0.45);color:#e9d5ff;padding:3px 9px;border-radius:999px;font-size:10px;font-weight:700;white-space:nowrap;flex-shrink:0;">{get_debate_mode_badge(active_cnt)}</span>'
    f'</div>'
    f'<div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:8px;">{mpills}</div></div>',
    unsafe_allow_html=True
)

sel_b = st.pills("アルゴリズムON/OFF", list(BOOST_MAP.keys()), default=list(BOOST_MAP.keys()), selection_mode="multi", label_visibility="collapsed") if hasattr(st, "pills") else st.multiselect("アルゴリズムON/OFF", list(BOOST_MAP.keys()), default=list(BOOST_MAP.keys()), label_visibility="collapsed")
ac_b = {BOOST_MAP[k] for k in (sel_b or [])}

with st.spinner(f"⚛️ 【{investment_style.split(' ')[1]}】日本株・米国株全市場をディープスキャン中（時間差・OFI・量子波動を網羅計算）..."):
    g_res, all_res = fetch_pool_batch(macro_info, b5_live_map, investment_style, "inst" in ac_b, "mom" in ac_b, "algo" in ac_b, "ms" in ac_b)

if st.session_state.get("navigation_page") == "NEWS_DETAIL":
    tn = st.session_state.get("selected_news_item") or all_impact_news[0]
    det = tn["detail"]
    st.markdown(
        f'<div class="glass-header" style="border-left:4px solid #ef4444;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">'
        f'<span class="pill-badge" style="background:#ef4444;color:#fff;border:none;">🚨 重大ニュース徹底深掘りレポート</span>'
        f'<span class="quantum-badge">⚛️ 量子波及スコア {tn["impact_score"]}点 ｜ {tn["source"]}</span></div>'
        f'<div style="font-size:18px;font-weight:800;color:#f8fafc;margin-top:8px;line-height:1.45;">{tn["title"]}</div>'
        f'<div style="font-size:11.5px;color:#94a3b8;margin-top:6px;">🎯 <b>最優先波及セクター：</b> <span style="color:#38bdf8;font-weight:700;">{det["sector_focus"]}</span></div>'
        f'</div>',
        unsafe_allow_html=True
    )
    if tn.get("link"):
        st.markdown(f'<a href="{tn["link"]}" target="_blank" rel="noopener noreferrer" class="ipo-link-btn">📰 ニュース原文（外部メディア）を別タブで開く</a>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="rank-card" style="border-left-color:#a855f7;margin-top:10px;">'
        f'<div style="font-size:14px;font-weight:800;color:#e9d5ff;margin-bottom:6px;">🧠 なぜこのニュースで株価が動くのか？（機関アルゴ＆量子もつれ波及メカニズム）</div>'
        f'<div style="font-size:12.5px;color:#e2e8f0;line-height:1.7;">{det["mechanism"]}</div>'
        f'<div class="beginner-action-box" style="margin-top:10px;">'
        f'<b>⚡ {investment_style.split(" ")[1]} 実践トレード立ち回り手順</b><br>{det["action_guide"].replace(chr(10), "<br>")}'
        f'</div></div>',
        unsafe_allow_html=True
    )
    st.markdown("### 🔗 このニュースに連動して株価が波及・急騰しやすい注目銘柄")
    by_code = {r["full_code"]: r for r in all_res}
    rel_stocks = [by_code[c] for c in det["related_codes"] if c in by_code] or sorted(all_res, key=lambda x: x["expect_pct"], reverse=True)[:5]
    for idx, r_item in enumerate(rel_stocks, 1):
        render_card(r_item, rank=idx, kp=f"news_rel_{tn['id']}")
    st.markdown("---")
    for other_n in all_impact_news:
        if other_n["id"] == tn["id"]: continue
        if st.button(f"📌 {other_n['title']} ({other_n['source']})", key=f"sw_n_{other_n['id']}", use_container_width=True):
            st.session_state["selected_news_item"] = other_n; st.session_state["navigation_page"] = "NEWS_DETAIL"; st.session_state["scroll_top_trig"] += 1; st.rerun()
    if st.button("⬅️ メインランキング画面へ戻る", use_container_width=True, type="primary"):
        st.session_state["navigation_page"] = "TOP"; st.session_state["scroll_top_trig"] += 1; st.rerun()
    st.stop()

c1, c2 = st.columns([3.4, 1])
cin = c1.text_input("🔍 銘柄検索", placeholder="銘柄コードまたは米ティッカーを入力 (例: 6920, 5803, NVDA, IONQ)", label_visibility="collapsed")
if c2.button("🔍 銘柄診断", use_container_width=True) and cin: st.session_state["custom_search_code"] = norm_tk(cin)

if st.session_state.get("custom_search_code"):
    nc = st.session_state["custom_search_code"]
    cr = fetch_one(nc, macro_info, b5_live_map, investment_style, "inst" in ac_b, "mom" in ac_b, "algo" in ac_b, "ms" in ac_b)
    if cr:
        render_card(cr, is_custom=True, kp="custom")
        if st.button("✖️ 個別診断を閉じる", use_container_width=True): st.session_state["custom_search_code"] = ""; st.rerun()
    else: st.warning(f"銘柄「{nc}」のデータが見つかりませんでした。")

def cut_stocks(slist, pct):
    if not slist: return [], []
    s = sorted(slist, key=lambda x: (x["tier_num"], x["expect_pct"], x["total_win_rate"], x["survival_power"]), reverse=True)
    k = max(3, int(round(len(s) * (pct / 100.0))))
    return s[:k], s[k:]

cats = ["🏆 総合TOP5", "⚛️ 量子トンネル突破TOP10", "🏛️ 機関最新ミクロ構造TOP10", "🚨 重大ニュース＆連動株", "🎟️ IPO募集・新規上場", "🏦 機関VPIN・OFI", "🔥 5ch＆短期モメンタム", "📋 監視シート"] + [f"📂 {g}" for g in STOCK_POOL.keys()]
st.markdown(f'<div class="compact-bar-label"><span>📂 QUANTUM STRATEGY & SECTOR SELECT ({investment_style.split(" ")[1]})</span><span>期待度ランキング / 機関ミクロ構造 / ニュース連動株 / IPO</span></div>', unsafe_allow_html=True)

if st.session_state.get("active_category") not in cats:
    st.session_state["active_category"] = "🏆 総合TOP5"

def _on_cat_change():
    nw = st.session_state.get("active_category")
    ol = st.session_state.get("last_cat", "🏆 総合TOP5")
    if not nw:
        st.session_state["active_category"] = ol
    elif nw != ol:
        st.session_state["nav_history"].append(ol)
        st.session_state["last_cat"] = nw

if hasattr(st, "pills"):
    st.pills("カテゴリ", cats, selection_mode="single", label_visibility="collapsed", key="active_category", on_change=_on_cat_change)
else:
    st.radio("カテゴリ", cats, horizontal=True, label_visibility="collapsed", key="active_category", on_change=_on_cat_change)

sel_cat = st.session_state.get("active_category") or st.session_state.get("last_cat", "🏆 総合TOP5")

surv, _ = cut_stocks(all_res, survival_cut_pct)
if sel_cat == "🏆 総合TOP5":
    st.caption(f"🦁 全母集団 {len(all_res)}銘柄から、{investment_style.split(' ')[1]}の視点と量子波動・機関ミクロ構造を統合して厳選した期待度TOP5です。")
    for i, r in enumerate(surv[:5], 1): render_card(r, rank=i, kp="top5")
elif sel_cat == "⚛️ 量子トンネル突破TOP10":
    st.caption("⚛️ シュレーディンガー波動関数・量子トンネル突破率・量子コヒーレンスが極大化している量子選抜ランキングです。")
    for i, r in enumerate(sorted(all_res, key=lambda x: (x["q_score"], x["q_tunnel"], x["expect_pct"]), reverse=True)[:10], 1): render_card(r, rank=i, kp="qtop")
elif sel_cat == "🏛️ 機関最新ミクロ構造TOP10":
    st.caption("🏛️ 機関投資家が使う Kyle's Lambda（氷山ステルス吸収度）・Hurst指数（トレンド持続性）・LULDマグネット引力が極大のランキングです。")
    for i, r in enumerate(sorted(all_res, key=lambda x: (x["ms_score"], x["kyle_stealth"], x["expect_pct"]), reverse=True)[:10], 1): render_card(r, rank=i, kp="mstop")
elif sel_cat == "🚨 重大ニュース＆連動株":
    st.caption("📰 最新マーケット重大ニュースと、そのニュースによって株価が連動・波及しやすい銘柄の一覧です。")
    for n_item in all_impact_news:
        st.markdown(f'<div class="rank-card" style="border-left-color:#ef4444;"><div style="font-size:11px;color:#f87171;font-weight:800;">🚨 {n_item["cat"]} ｜ {n_item["source"]}</div><div style="font-size:14.5px;font-weight:800;color:#f8fafc;margin:4px 0;">{n_item["title"]}</div><div style="font-size:11.5px;color:#cbd5e1;">{n_item["detail"]["mechanism"]}</div></div>', unsafe_allow_html=True)
        if st.button("🔥 このニュースの詳細レポート＆連動株を見る", key=f"tab_n_{n_item['id']}", use_container_width=True):
            st.session_state["selected_news_item"] = n_item; st.session_state["navigation_page"] = "NEWS_DETAIL"; st.session_state["scroll_top_trig"] += 1; st.rerun()
elif sel_cat == "🎟️ IPO募集・新規上場":
    render_ipo_offering_section()
    st.markdown("#### 🚀 直近上場・セカンダリー急騰IPO株リアルタイム診断")
    for i, r in enumerate(cut_stocks(g_res.get("小型急騰・直近IPO", []), 100)[0][:6], 1): render_card(r, rank=i, kp="ipo_sec")
elif sel_cat == "🏦 機関VPIN・OFI":
    for i, r in enumerate(sorted(all_res, key=lambda x: (x["inst_score"], x["ofi_z"], x["expect_pct"]), reverse=True)[:10], 1): render_card(r, rank=i, kp="inst")
elif sel_cat == "🔥 5ch＆短期モメンタム":
    for i, r in enumerate(sorted(all_res, key=lambda x: (x["board5ch_score"], x["expect_pct"], x["ofi_z"]), reverse=True)[:10], 1): render_card(r, rank=i, kp="mom")
elif sel_cat == "📋 監視シート":
    wl = st.session_state["watchlist"]
    if st.button("⚡ 総合TOP3をワンタップ一括登録", use_container_width=True):
        for it in surv[:3]: st.session_state["watchlist"][it["code"]] = it
        st.rerun()
    for wc, wi in list(wl.items()): render_card(wi, kp=f"wl_{wc}")
elif sel_cat.startswith("📂 "):
    gk = sel_cat.replace("📂 ", "")
    gs, _ = cut_stocks(g_res.get(gk, []), survival_cut_pct)
    for i, r in enumerate(gs, 1): render_card(r, rank=i, kp=f"g_{gk}")
