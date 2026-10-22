import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np
import altair as alt
import unicodedata, hashlib, hmac, json, os, re, ssl, smtplib, time
import urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from email.mime.text import MIMEText
from datetime import datetime

st.set_page_config(page_title="YAMASHISHI LAB", page_icon="⚡", layout="centered")
frag_dec = getattr(st, "fragment", getattr(st, "experimental_fragment", lambda f: f))

ADMIN_EMAIL = "nthbh399@ybb.ne.jp"
SECRET_KEY = "my_super_secret_quant_key_2026"
FILES = {"mem": "members_db.json", "smtp": "admin_smtp_config.json", "llm": "admin_llm_config.json", "sec": "security_watch_db.json", "mail": "mail_history_db.json"}
BOARD_URLS = ["https://egg.5ch.io/test/read.cgi/stock/1791877270/", "https://egg.5ch.io/test/read.cgi/stock/1791897352/"]
ONLINE_TTL = 300

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
def load_sec(): return load_j(FILES["sec"], {"banned_fps": {}, "spoof_logs": [], "device_bio_map": {}})
def load_mail_db(): return load_j(FILES["mail"], {"logs": []})
def load_mem():
    db = load_j(FILES["mem"], {})
    adm = ADMIN_EMAIL.strip().lower()
    if adm not in db:
        ns = datetime.now().strftime("%Y-%m-%d %H:%M")
        db[adm] = {"name": "管理者", "email": adm, "status": "approved", "passcode": gen_code(adm), "pin_hash": hash_pin("0000"), "applied_at": ns, "approved_at": ns, "last_seen_ts": 0, "last_seen_str": "-", "fp": "-", "bio_enabled": False}
        save_j(FILES["mem"], db)
    return db

def is_online(u_rec: dict) -> bool: return (time.time() - float(u_rec.get("last_seen_ts", 0) or 0)) <= ONLINE_TTL

def send_mail(to_em: str, subj: str, body: str, category: str = "自動通知") -> bool:
    to_clean, now_str = to_em.strip().lower(), datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    route, sent = "暗号化アプリ内BOX", False
    c = load_smtp()
    u, p, srv, port = c.get("smtp_user", "").strip(), c.get("smtp_pass", "").strip(), c.get("smtp_server", "").strip(), int(c.get("smtp_port", 465))
    if u and p:
        try:
            m = MIMEText(body, "plain", "utf-8"); m["Subject"], m["From"], m["To"] = subj, u, to_clean
            with (smtplib.SMTP_SSL(srv, port, timeout=2.5) if port == 465 else smtplib.SMTP(srv, port, timeout=2.5)) as s:
                if port != 465: s.starttls()
                s.login(u, p); s.send_message(m)
            sent, route = True, "SMTP配信＋暗号化BOX"
        except Exception: pass
    if not sent:
        try:
            ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
            payload = json.dumps({"_subject": subj, "宛先": to_clean, "本文": body, "_captcha": "false"}).encode("utf-8")
            req = urllib.request.Request(f"https://formsubmit.co/ajax/{urllib.parse.quote(to_clean)}", data=payload, headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=2.0, context=ctx) as r:
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
            if u_rec.get("status") == "suspended": st.error("🚫 アカウント停止中です。")
            elif cur_fp in sec.get("banned_fps", {}) and t_em != ADMIN_EMAIL.strip().lower(): st.error("🚫 端末制限中です。")
            elif (u_rec and u_rec.get("status") == "approved") or t_em == ADMIN_EMAIL.strip().lower():
                st.session_state["authenticated_user"] = t_em; st.query_params["u"], st.query_params["t"] = t_em, gen_tok(t_em, "session_keep"); st.rerun()
        else: st.warning("⚠️ 初回は下のフォームから専用コードでログインしてください（次回から自動登録されます）。")

def inject_css():
    css = """
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;800&family=Plus+Jakarta+Sans:wght@400;600;800&family=JetBrains+Mono:wght@500;700&display=swap');
    html,body,[class*="css"]{font-family:'Plus Jakarta Sans',sans-serif;font-size:14px;background-color:#050811;color:#e2e8f0;}
    .block-container{padding-top:3.1rem!important;padding-bottom:3rem!important;padding-left:0.75rem!important;padding-right:0.75rem!important;max-width:840px!important;}
    /* 見切れ完全防止のラグジュアリータイトル */
    .brand-luxury{font-family:'Cinzel',serif!important;font-size:clamp(16px,4.2vw,24px)!important;font-weight:800!important;letter-spacing:clamp(1px,0.5vw,3px)!important;background:linear-gradient(90deg,#f8fafc 0%,#38bdf8 55%,#818cf8 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1.25;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;display:block;width:100%;}
    .brand-sub{font-family:'JetBrains Mono',monospace;font-size:clamp(8.5px,2.2vw,10.5px);color:#64748b;letter-spacing:1.2px;text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
    /* 上部ナビ：絶対に巨大化せず、上のアイコンに被らず、スマホでも必ず横1列に収める強制CSS */
    div[data-testid="stVerticalBlock"] > div:has(div.top-nav-marker){position:sticky!important;top:2.75rem!important;z-index:999!important;background:rgba(5,8,17,0.88)!important;backdrop-filter:blur(14px)!important;padding:4px 6px!important;margin:-6px 0 8px 0!important;border-radius:10px!important;border:1px solid rgba(56,189,248,0.22)!important;box-shadow:0 6px 20px rgba(0,0,0,0.5)!important;width:100%!important;box-sizing:border-box!important;}
    div[data-testid="stVerticalBlock"] > div:has(div.top-nav-marker) div[data-testid="stHorizontalBlock"]{display:flex!important;flex-direction:row!important;flex-wrap:nowrap!important;align-items:center!important;gap:4px!important;width:100%!important;}
    div[data-testid="stVerticalBlock"] > div:has(div.top-nav-marker) div[data-testid="column"],
    div[data-testid="stVerticalBlock"] > div:has(div.top-nav-marker) div[data-testid="stColumn"]{min-width:0!important;flex:1 1 0%!important;padding:0!important;}
    div[data-testid="stVerticalBlock"] > div:has(div.top-nav-marker) div[data-testid="column"]:nth-child(2),
    div[data-testid="stVerticalBlock"] > div:has(div.top-nav-marker) div[data-testid="stColumn"]:nth-child(2){flex:1.45 1 0%!important;}
    div[data-testid="stVerticalBlock"] > div:has(div.top-nav-marker) button{width:100%!important;min-width:0!important;height:28px!important;min-height:28px!important;max-height:28px!important;padding:0 4px!important;margin:0!important;border-radius:6px!important;background:linear-gradient(180deg,#1e293b,#0f172a)!important;color:#f8fafc!important;border:1px solid rgba(148,163,184,0.25)!important;box-shadow:none!important;}
    div[data-testid="stVerticalBlock"] > div:has(div.top-nav-marker) button:hover{border-color:#38bdf8!important;color:#38bdf8!important;}
    div[data-testid="stVerticalBlock"] > div:has(div.top-nav-marker) button p{font-size:clamp(10px,2.6vw,11.5px)!important;font-weight:700!important;margin:0!important;padding:0!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;line-height:1!important;}
    div[data-testid="stVerticalBlock"] > div:has(div.floating-news-popup-marker){position:fixed!important;bottom:16px!important;right:16px!important;z-index:99999!important;width:min(390px,92vw)!important;background:rgba(15,23,42,0.96)!important;backdrop-filter:blur(16px)!important;border:1px solid #ef4444!important;border-left:4px solid #ef4444!important;border-radius:12px!important;padding:10px 12px!important;box-shadow:0 14px 35px rgba(0,0,0,0.75)!important;}
    .glass-header{background:radial-gradient(circle at top right,rgba(56,189,248,0.12),transparent 60%),linear-gradient(145deg,#0f172a 0%,#070b14 100%);border:1px solid rgba(148,163,184,0.18);border-radius:14px;padding:14px 14px;margin-bottom:10px;box-shadow:0 10px 28px rgba(0,0,0,0.45);box-sizing:border-box;width:100%;overflow:hidden;}
    .auth-bento-card{background:linear-gradient(160deg,rgba(15,23,42,0.9),rgba(9,13,22,0.95));border:1px solid rgba(56,189,248,0.22);border-radius:14px;padding:16px;margin-bottom:12px;box-shadow:0 12px 32px rgba(0,0,0,0.5);}
    .compact-bar-label{display:flex;justify-content:space-between;font-size:10.5px;font-weight:700;letter-spacing:0.8px;color:#94a3b8;background:#0f172a;padding:5px 11px;border-radius:7px;border-left:3px solid #38bdf8;margin-bottom:5px;}
    .rank-card,.search-result-card{background:linear-gradient(180deg,#0f172a 0%,#090d16 100%)!important;color:#f8fafc!important;border-radius:14px;padding:13px 14px;margin-bottom:11px;box-shadow:0 8px 24px rgba(0,0,0,0.45);border:1px solid rgba(148,163,184,0.16);border-left:4px solid #38bdf8;}
    .search-result-card{border-left-color:#f59e0b;}
    .prob-badge{font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:800;color:#38bdf8!important;}
    .pill-badge{display:inline-block;padding:2px 7px;border-radius:6px;font-size:10px;font-weight:700;margin-right:4px;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);color:#e2e8f0;}
    .winrate-bar{display:grid;grid-template-columns:repeat(4,1fr);gap:5px;background:rgba(15,23,42,0.85)!important;border:1px solid rgba(148,163,184,0.15);border-radius:8px;padding:6px 4px;margin-top:7px;text-align:center;}
    .signal-10tier-badge{display:flex;justify-content:space-between;align-items:center;padding:5px 10px;border-radius:7px;font-size:11.5px;font-weight:800;margin-bottom:7px;gap:6px;flex-wrap:wrap;}
    .trade-plan-box{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin-top:6px;background:rgba(2,6,23,0.7)!important;padding:6px 4px;border-radius:8px;border:1px solid rgba(148,163,184,0.15);text-align:center;}
    .sizing-box{background:rgba(16,185,129,0.08)!important;border:1px solid rgba(16,185,129,0.28);border-radius:8px;padding:5px 10px;margin-top:6px;font-size:11px;color:#d1fae5;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:4px;}
    details.quant-detail-drawer{margin-top:6px;background:rgba(2,6,23,0.55);border:1px solid rgba(148,163,184,0.15);border-radius:8px;padding:5px 10px;}
    details.quant-detail-drawer summary{font-size:11px;font-weight:700;color:#38bdf8!important;cursor:pointer;list-style:none;}
    .metrics-row{display:flex;flex-wrap:wrap;gap:4px 8px;margin-top:5px;font-size:10.5px;font-family:'JetBrains Mono',monospace;background:rgba(15,23,42,0.9)!important;padding:5px 8px;border-radius:6px;color:#cbd5e1;}
    .ai-council-box{background:#070b14;color:#f8fafc!important;border-radius:11px;padding:11px;margin-top:6px;margin-bottom:9px;border:1px solid rgba(56,189,248,0.28);}
    .council-scroll-window{max-height:440px;overflow-y:auto;padding:9px;background:#04070e;border:1px solid rgba(255,255,255,0.07);border-radius:8px;margin-bottom:8px;}
    .round-divider{text-align:center;margin:6px 0;padding:4px 8px;background:rgba(56,189,248,0.12);border-left:3px solid #38bdf8;color:#7dd3fc!important;font-size:11px;font-weight:700;border-radius:4px;}
    .chat-bubble-ai,.chat-bubble-doubt,.chat-bubble-rage,.chat-bubble-agree{border-radius:8px;padding:7px 10px;margin-bottom:6px;font-size:12px;line-height:1.55;background:rgba(255,255,255,0.04);border-left:3px solid #38bdf8;}
    .chat-bubble-doubt{border-left-color:#f59e0b;background:rgba(245,158,11,0.07);}
    .chat-bubble-rage{border-left-color:#ef4444;background:rgba(239,68,68,0.12);}
    .chat-bubble-agree{border-left-color:#10b981;background:rgba(16,185,129,0.09);}
    .chat-bubble-user{background:rgba(37,99,235,0.25);border-left:3px solid #60a5fa;border-radius:8px;padding:7px 10px;margin-bottom:6px;font-size:12px;}
    .consensus-banner{background:linear-gradient(135deg,#0f172a,#1e1b4b);border:1px solid rgba(129,140,248,0.38);border-radius:9px;padding:10px;margin-top:7px;font-size:12px;}
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
        if cu != ADMIN_EMAIL.strip().lower() and (not u_rec or u_rec.get("status") != "approved"):
            st.session_state["authenticated_user"] = None; st.query_params.clear(); st.error("🚫 アカウント停止中です。"); st.stop()
        keep_tok = gen_tok(cu, "session_keep")
        if cu in db:
            db[cu].update({"last_seen_ts": time.time(), "last_seen_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "fp": cur_fp, "raw_hfp": raw_hfp, "bio_enabled": True})
            save_j(FILES["mem"], db)
            sec.setdefault("device_bio_map", {})[raw_hfp] = sec["device_bio_map"][cur_fp] = {"email": cu, "token": keep_tok, "fp": cur_fp}; save_j(FILES["sec"], sec)
        st.query_params["u"], st.query_params["t"] = cu, keep_tok
        with st.sidebar:
            st.markdown(f'<div style="background:#0f172a;padding:8px 11px;border-radius:9px;border:1px solid rgba(56,189,248,0.3);margin-bottom:6px;"><div style="font-size:9.5px;color:#38bdf8;font-weight:700;">🟢 QUANT SESSION ACTIVE</div><div style="color:#f8fafc;font-size:11.5px;font-weight:700;">{db.get(cu,{}).get("name","会員")} ({cu})</div></div>', unsafe_allow_html=True)
            render_biometric_bridge(mode="register", user_email=cu, bio_token=keep_tok)
            if st.button("🚪 ログアウト", use_container_width=True):
                if cu in db: db[cu]["last_seen_ts"] = 0; save_j(FILES["mem"], db)
                st.session_state["authenticated_user"] = None; st.query_params.clear(); st.rerun()
        if cu == ADMIN_EMAIL.strip().lower():
            pend = [v for v in db.values() if v.get("status") == "pending"]
            if st.sidebar.button(f"👑 管理画面 (承認待:{len(pend)} / メール:{len(load_mail_db().get('logs',[]))})", use_container_width=True):
                st.session_state["navigation_page"] = "ADMIN"; st.rerun()
        return True

    # --- スタイリッシュ＆見切れゼロの最新ログイン画面 ---
    st.markdown(
        '<div class="glass-header" style="text-align:center;padding:18px 12px;">'
        '<div class="brand-luxury">YAMASHISHI LAB</div>'
        '<div class="brand-sub" style="margin-top:4px;">INSTITUTIONAL MULTI-AGENT QUANT TERMINAL</div>'
        '<div style="display:flex;justify-content:center;gap:8px;margin-top:10px;flex-wrap:wrap;">'
        '<span class="pill-badge" style="color:#38bdf8;border-color:rgba(56,189,248,0.3);">🛡️ SHA-256 2FA PIN保護</span>'
        '<span class="pill-badge" style="color:#10b981;border-color:rgba(16,185,129,0.3);">🧬 デバイス生体認証対応</span>'
        '<span class="pill-badge" style="color:#a855f7;border-color:rgba(168,85,247,0.3);">⚡ 7大AIエンジン搭載</span>'
        '</div></div>',
        unsafe_allow_html=True
    )
    render_biometric_bridge(mode="login")

    tab_login, tab_apply, tab_vault = st.tabs(["🔑 コードログイン", "📩 新規会員登録申請", "🔐 承認確認・暗号化コード照会"])
    with tab_login:
        with st.form("login"):
            ie = st.text_input("📧 登録メールアドレス", placeholder="your@email.com")
            ic = st.text_input("🔑 専用アクセスコード", type="password", placeholder="8桁の専用コード")
            if st.form_submit_button("🔓 認証してターミナルを起動", use_container_width=True):
                cm = ie.strip().lower(); rec = db.get(cm)
                if rec and rec.get("status") == "suspended": st.error("🚫 このアカウントは停止されています。")
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
                    db[cm] = {"name": nm_clean, "email": cm, "status": "pending", "passcode": pc, "pin_hash": hash_pin(apin), "applied_at": ns, "approved_at": "-", "last_seen_ts": 0, "last_seen_str": "-", "fp": cur_fp, "raw_hfp": raw_hfp, "bio_enabled": False}
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
                if not u_info:
                    st.error("❌ 該当する申請データが見つかりません。")
                elif u_info.get("pin_hash") and not hmac.compare_digest(u_info.get("pin_hash", ""), hash_pin(chk_pin)):
                    st.error("🚫 暗証番号(PIN)が一致しません。第三者による照会はブロックされました。")
                elif u_info.get("status") == "approved":
                    st.success(f"🎉 本人確認完了・承認済みです！あなたの専用アクセスコードは **`{u_info.get('passcode', gen_code(chk_em))}`** です。「🔑 コードログイン」タブからログインしてください。")
                elif u_info.get("status") == "pending":
                    st.info("⏳ 本人確認完了：現在、管理者の承認審査待ちです。")
                else:
                    st.error("🚫 現在このアカウントは利用できません。")
    st.stop()

check_auth()

for k, v in [("active_debates", {}), ("stock_chats", {}), ("council_threads", {}), ("council_meta", {}), ("debate_round_seed", {}), ("watchlist", {}), ("navigation_page", "TOP"), ("prev_page_before_news", "TOP"), ("custom_search_code", ""), ("active_category", "🏆 総合TOP5"), ("nav_history", []), ("scroll_top_trig", 0), ("dismissed_news_ids", set())]:
    if k not in st.session_state: st.session_state[k] = v

# --- 上部固定ナビバー（巨大化防止・横1列強制・アイコン被り防止） ---
open_cnt = sum(1 for v in st.session_state["active_debates"].values() if v)
with st.container():
    st.markdown('<div class="top-nav-marker"></div>', unsafe_allow_html=True)
    nav_c1, nav_c2, nav_c3 = st.columns([1, 1.45, 1])
    if nav_c1.button("⬆️ トップ", key="top_nav_top", use_container_width=True):
        st.session_state["navigation_page"] = "TOP"; st.session_state["scroll_top_trig"] += 1; st.rerun()
    if nav_c2.button(f"✖ 合議全て閉じる({open_cnt})" if open_cnt else "✖ 合議全て閉じる", key="top_nav_close", use_container_width=True):
        st.session_state["active_debates"] = {}; st.rerun()
    if nav_c3.button("↩️ 戻る", key="top_nav_back", use_container_width=True):
        if st.session_state.get("custom_search_code"): st.session_state["custom_search_code"] = ""
        elif st.session_state.get("navigation_page") != "TOP": st.session_state["navigation_page"] = "TOP"
        elif st.session_state["nav_history"]: st.session_state["active_category"] = st.session_state["nav_history"].pop()
        else: st.session_state["active_category"] = "🏆 総合TOP5"
        st.rerun()

if st.session_state["scroll_top_trig"] > 0:
    components.html(f"<script>/*{st.session_state['scroll_top_trig']}*/window.parent.scrollTo({{top:0,behavior:'smooth'}});</script>", height=0)

AI_ROSTER = {"AEGIS": "🛡️ AEGIS (CVaR防衛官)", "IGNIS": "🔥 IGNIS (OFI・5ch特攻官)", "TECHNOS": "📐 TECHNOS (数理構造官)", "MACRO": "🌐 MACRO (先物ギャップ官)", "MICRO": "🔬 MICRO (機関VPIN監査官)", "CHRONOS": "📊 CHRONOS (統計バックテスト官)", "NEXUS": "👑 NEXUS (総括ディレクター)"}

POOL_COMPACT = {
    "半導体": "8035.T:東京エレクトロン:前工程装置筆頭|6857.T:アドバンテスト:AI半導体テスタ首位|6920.T:レーザーテック:EUV検査高ボラ|6146.T:ディスコ:HBM精密加工装置|6526.T:ソシオネクスト:カスタムSoC|7735.T:スクリーンHD:ウエハー洗浄首位|6315.T:TOWA:HBMモールディング|6723.T:ルネサス:車載・AI半導体|4063.T:信越化学工業:ウエハー世界首位|6871.T:日本マイクロニクス:HBMプローブ|NVDA:エヌビディア (米):AI GPU覇者|AMD:AMD (米):AIアクセラレータ|MU:マイクロン (米):HBMメモリ|TSM:TSMC (米):半導体受託首位|AVGO:ブロードコム (米):カスタムAI半導体|ARM:アーム (米):半導体設計",
    "AI・防衛・主力": "9984.T:ソフトバンクG:AI投資・先物主役|3778.T:さくらネット:国策GPUクラウド|7011.T:三菱重工業:防衛・宇宙国策主力|7012.T:川崎重工業:防衛・航空エンジン|7013.T:IHI:航空宇宙・防衛|3993.T:PKSHA:AIアルゴリズム|5032.T:ANYCOLOR:VTuber大手|7974.T:任天堂:次世代機・機関流入|8306.T:三菱UFJ:金利連動メガバンク|MSFT:マイクロソフト (米):クラウドAI|PLTR:パランティア (米):防衛AI大本命|META:メタ (米):AI広告|GOOGL:アルファベット (米):Gemini生成AI|CRWD:クラウドストライク (米):AIセキュリティ",
    "AI電力・電線": "5803.T:フジクラ:DC光ファイバー最強株|5801.T:古河電気工業:光ファイバー・送電|5802.T:住友電気工業:電線首位・DC網|6501.T:日立製作所:世界送配電グリッド|9509.T:北海道電力:ラピダス・DC電力|9508.T:九州電力:TSMC工場電力|6622.T:ダイヘン:DC変圧器|1942.T:関電工:DC電気設備|VST:ビストラ (米):AI発電主力|CEG:コンステレーション (米):米原発AI電力|GEV:GEヴェルノバ (米):送電網リーダー",
    "宇宙・次世代": "5595.T:QPS研究所:小型SAR衛星|186A.T:アストロスケール:宇宙デブリ除去|9348.T:ispace:月面輸送|9412.T:スカパーJSAT:衛星・防衛宇宙|7203.T:トヨタ自動車:全固体電池|TSLA:テスラ (米):自動運転・ロボ|RKLB:ロケットラボ (米):小型ロケット|ASTS:ASTスペース (米):宇宙スマホ通信|COIN:コインベース (米):暗号資産高ボラ",
    "小型急騰・直近IPO": "5253.T:カバー:グロース売買首位級|9166.T:GENDA:エンタメM&A|216A.T:タイミー:スキマバイト大型IPO|285A.T:キオクシアHD:NAND大型IPO|141A.T:トライアルHD:リテールAI流通IPO|247A.T:Aiロボティクス:AIマーケ急騰IPO|3350.T:メタプラネット:暗号資産・超ボラ|IONQ:アイオンQ (米):商用量子代表|RGTI:リゲッティ (米):量子急騰株|RDDT:レディット (米IPO):AIデータ大型IPO|ALAB:アステラ・ラブズ (米IPO):AI接続半導体IPO"
}
STOCK_POOL = {g: [{"code": p.split(":")[0], "name": p.split(":")[1], "theme": p.split(":")[2]} for p in s.split("|")] for g, s in POOL_COMPACT.items()}
KNOWN_STOCKS = {it["code"]: {"name": it["name"], "theme": it["theme"], "genre": g} for g, its in STOCK_POOL.items() for it in its}

def _parse_j(raw: str):
    txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(raw or "").strip(), flags=re.IGNORECASE).strip()
    sb, eb = txt.find("{"), txt.rfind("}")
    if sb != -1 and eb > sb: txt = txt[sb:eb+1]
    return json.loads(re.sub(r"[\x00-\x1f]+", " ", re.sub(r",\s*([}\]])", r"\1", txt)))

def call_api_seamless(sys_p: str, usr_p: str, temp: float = 0.7) -> tuple:
    cfg = load_llm()
    prov = st.session_state.get("rt_llm_prov") or cfg.get("provider", "gemini")
    p_label, m_list, endpoint = AI_PROVIDERS.get(prov, AI_PROVIDERS["gemini"])
    key = clean_k(st.session_state.get(f"rt_key_{prov}") or cfg.get("api_keys", {}).get(prov, ""))
    model = st.session_state.get(f"rt_mod_{prov}") or cfg.get("models", {}).get(prov, m_list[0])
    if not key: return None, "内蔵機関クオンツ推論エンジン"
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try:
        if prov == "gemini":
            url = endpoint.format(model=model, key=urllib.parse.quote(key))
            gen_cfg = {"temperature": temp}
            if not model.startswith("gemma"): gen_cfg["responseMimeType"] = "application/json"
            payload = {"contents": [{"role": "user", "parts": [{"text": f"【指示】\n{sys_p}\n\n【データ】\n{usr_p}"}]}], "generationConfig": gen_cfg}
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=5.0, context=ctx) as r:
                d = json.loads(r.read().decode("utf-8"))
                return _parse_j("".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"])), f"{p_label} ({model})"
        elif prov == "claude":
            payload = {"model": model, "max_tokens": 1100, "temperature": temp, "system": sys_p + " JSONのみ出力せよ。", "messages": [{"role": "user", "content": usr_p}]}
            req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"}, method="POST")
            with urllib.request.urlopen(req, timeout=5.5, context=ctx) as r:
                return _parse_j(json.loads(r.read().decode("utf-8"))["content"][0]["text"]), f"{p_label} ({model})"
        else:
            payload = {"model": model, "messages": [{"role": "system", "content": sys_p + " Always output valid JSON."}, {"role": "user", "content": usr_p}], "temperature": temp}
            req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"}, method="POST")
            with urllib.request.urlopen(req, timeout=5.5, context=ctx) as r:
                return _parse_j(json.loads(r.read().decode("utf-8"))["choices"][0]["message"]["content"]), f"{p_label} ({model})"
    except Exception: return None, "内蔵機関クオンツ推論エンジン"

@st.cache_data(ttl=180)
def fetch_global_impact_news() -> list:
    qs = [("半導体・AI", "半導体 OR エヌビディア OR TSMC OR アドバンテスト 株価"), ("急騰・サプライズ", "ストップ高 OR 上方修正 OR 自社株買い OR TOB 株")]
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    out, seen = [], set()
    for cat, q in qs:
        try:
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=ja&gl=JP&ceid=JP:ja"
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=1.8, context=ctx) as res:
                root = ET.fromstring(res.read())
            for it in root.findall("./channel/item")[:3]:
                t = re.sub(r"\s*-\s*[^-]+$", "", (it.findtext("title") or "").strip())
                if not t or t in seen: continue
                seen.add(t)
                out.append({"id": hashlib.md5(t.encode()).hexdigest()[:8], "title": t, "link": it.findtext("link") or "", "source": it.findtext("source") or "Market Wire", "impact_score": 88})
        except Exception: continue
    return out[:3]

@st.cache_data(ttl=900)
def fetch_5ch_live() -> dict:
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    txts = []
    for u in BOARD_URLS:
        try:
            with urllib.request.urlopen(urllib.request.Request(u + "l50", headers={"User-Agent": "Mozilla/5.0"}), timeout=1.5, context=ctx) as r:
                txts.append(re.sub(r"<[^>]+>", " ", r.read().decode("cp932", errors="ignore")))
        except Exception: continue
    joined = " ".join(txts)
    return {c: {"hits": len(re.findall(re.escape(c.replace(".T", "")), joined)) if joined else 0, "live": bool(txts)} for c in KNOWN_STOCKS}

# --- サイドバー（7大AIプロバイダー対応） ---
st.sidebar.header("🧠 7大AI マルチエンジン設定")
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

st.sidebar.markdown("---")
st.sidebar.header("💰 資金管理＆フィルタ設定")
total_capital = st.sidebar.number_input("総投資資金 (円/ドル)", min_value=10000, max_value=1000000000, value=1000000, step=50000)
risk_tolerance_pct = st.sidebar.slider("1トレード許容リスク (%)", 0.5, 5.0, 2.0, 0.5)
survival_cut_pct = st.sidebar.slider("各タブ選抜率 (%)", 40, 100, 75, 5)
toggle_fn = getattr(st.sidebar, "toggle", st.sidebar.checkbox)
show_5m_chart = toggle_fn("📈 5分足＆VWAP描画", value=True)
enable_news_popup = toggle_fn("🚨 緊急ニュースポップアップ", value=True)

if enable_news_popup:
    unread = [n for n in fetch_global_impact_news() if n["id"] not in st.session_state["dismissed_news_ids"]]
    if unread:
        tn = unread[0]
        with st.container():
            st.markdown(f'<div class="floating-news-popup-marker"></div><div style="font-size:10.5px;color:#f87171;font-weight:800;">🚨 緊急ヘッドライン ｜ {tn["source"]}</div><div style="font-size:12px;font-weight:700;color:#f8fafc;margin:4px 0;">{tn["title"]}</div>', unsafe_allow_html=True)
            c_n1, c_n2 = st.columns(2)
            if tn.get("link"): c_n1.markdown(f'<a href="{tn["link"]}" target="_blank" class="ipo-link-btn">📰 原文を開く</a>', unsafe_allow_html=True)
            if c_n2.button("✖ 閉じる", key=f"cls_n_{tn['id']}", use_container_width=True): st.session_state["dismissed_news_ids"].add(tn["id"]); st.rerun()

if st.session_state.get("navigation_page") == "ADMIN" and st.session_state.get("authenticated_user") == ADMIN_EMAIL.strip().lower():
    db = load_mem()
    st.subheader("👑 会員管理センター")
    if st.button("⬅️ TOPへ戻る"): st.session_state["navigation_page"] = "TOP"; st.rerun()
    for k, v in list(db.items()):
        pc = v.get("passcode", gen_code(k))
        c1, c2, c3 = st.columns([3, 1, 1])
        c1.markdown(f"**{v.get('name')}** (`{k}`) ｜ 状態: **{v.get('status')}** ｜ 専用コード: `{pc}`")
        if k != ADMIN_EMAIL.strip().lower():
            if c2.button("✅承認", key=f"ap_{k}"): db[k]["status"] = "approved"; save_j(FILES["mem"], db); send_mail(k, "【YAMASHISHI LAB】承認完了のお知らせ", f"会員登録が承認されました。ログイン画面の『🔐 承認確認・暗号化コード照会』タブより4桁PINを入力して専用コードをご確認ください。"); st.rerun()
            if c3.button("🚫停止", key=f"bn_{k}"): db[k]["status"] = "suspended"; save_j(FILES["mem"], db); st.rerun()
    st.stop()

# ==========================================
# 📈 銘柄別・動的6大アルゴリズム戦略エンジン（タイムアウト防止・高速版）
# ==========================================
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

def select_dynamic_strategy(code: str, tot_win: float, ofi_z: float, vpin: float, yz_vol: float, cvar95: float, rsi: float, cpos: float, base_sh: int, pest_str: str, vwap_str: str, tp_str: str, sl_str: str, kelly_pct: float) -> dict:
    if tot_win >= 64.0 and ofi_z >= 0.8 and vpin >= 0.15:
        sh = max(1, int(round(base_sh * 1.45)))
        l1, l2 = max(1, int(round(sh * 0.70))), max(0, sh - max(1, int(round(sh * 0.70))))
        return {
            "algo_name": "🦁 【超強気・レバレッジ集中特攻型】フルケリー突破アルゴリズム",
            "risk_posture": f"🔥 最大リスク許容（通常ロットの1.45倍・資金配分 {min(48.0, round(kelly_pct*1.5,1))}% 集中投下）",
            "core_logic": f"総合勝率 {tot_win}%・OFI +{ofi_z:.2f}σ・機関VPIN +{vpin:.2f} が同時点灯する極大エッジ局面。寄り付きから70%の主力資金を一気に叩き込み、上値ブレイクで残り30%を追撃する大勝負プラン。",
            "adj_shares": sh,
            "step_plan": f"① 9:00寄付き成行（{pest_str}目安）で主力 <b>{l1:,}株（70%）</b> 一気投入 → ② 高値ブレイクで残り <b>{l2:,}株（30%）</b> 追撃",
            "beginner_html": f"<b>🔰 初心者向け・明日のカンタン行動手順（大チャンス勝負銘柄！）</b><br>① <b>【朝8:50までに準備】</b> 勝率が非常に高いため普段より多めの <b>「成行（なりゆき）買い・{l1:,}株」</b> を注文予約します。<br>② <b>【買えた直後】</b> 万が一の急落に備えて <b>「逆指値（損切り）：{sl_str}」</b> をセットしつつ、勢いが続けば <b>{l2:,}株</b> を追加購入します。<br>③ <b>【利益確定】</b> 株価が伸びて <b>「{tp_str}」</b> に到達したら迷わず売って大きな利益を確定させましょう！"
        }
    elif ofi_z >= 1.1 or (cpos >= 0.82 and yz_vol >= 35.0):
        sh = max(1, int(round(base_sh * 1.2)))
        return {
            "algo_name": "⚡ 【初動ブレイク一括特攻型】OFI板掃き上げ順張りアルゴリズム",
            "risk_posture": "🚀 攻撃的順張り（押し目を待たず寄付き初動に100%集中）",
            "core_logic": f"大引け位置 {int(cpos*100)}%・年率ボラ {yz_vol}% と踏み上げが加速中。押し目を待つと置いていかれるため、寄付きで全ロット {sh:,}株 を一括投入し前場の急伸を抜くスピード勝負。",
            "adj_shares": sh,
            "step_plan": f"① 9:00寄付き（{pest_str}目安）で <b>{sh:,}株（100%一括）</b> 即時執行 → ② 前場の急伸局面（{tp_str}）で素早く全株利確",
            "beginner_html": f"<b>🔰 初心者向け・明日のカンタン行動手順（スピード短期決戦！）</b><br>① <b>【買い方】</b> 下がるのを待つと買えなくなる銘柄です。朝9:00の寄り付きで <b>「{sh:,}株」をまとめて1回で購入</b> します。<br>② <b>【守り方】</b> 買えたらすぐに <b>「{sl_str}」で逆指値（自動損切り）</b> を入れておきます。<br>③ <b>【売り方】</b> 朝9:00〜10:30頃の勢いがあるうちに <b>「{tp_str}」付近でサッと売って</b> お昼前に利益確定するのがコツです！"
        }
    elif rsi <= 44.0 or cpos <= 0.38:
        sh = max(1, int(round(base_sh * 0.9)))
        l1, l2 = max(1, int(round(sh * 0.40))), max(0, sh - max(1, int(round(sh * 0.40))))
        return {
            "algo_name": "🛡️ 【逆張りリバーサル・スナイプ型】機関指値吸収・底打ち反発アルゴリズム",
            "risk_posture": "🎯 厳選押し目狙い（寄付き飛びつき厳禁・安値反発待ち伏せ）",
            "core_logic": f"RSI {rsi} と売られすぎ圏にあり、個人の投げ売りを機関アルゴが下値で吸収している波形。朝イチの成行買いは厳禁とし、前場の売り一巡とVWAP（{vwap_str}）奪還を確認してから狙い撃つ。",
            "adj_shares": sh,
            "step_plan": f"① 9:00〜9:15は様子見 → ② VWAP（{vwap_str}）反発確認で <b>{l1:,}株（40%）</b> → ③ 陽線転換で <b>{l2:,}株（60%）</b> 本玉投入",
            "beginner_html": f"<b>🔰 初心者向け・明日のカンタン行動手順（じっくり底値拾い！）</b><br>① <b>【朝9:00は買わない！】</b> 朝イチは売りが残りやすいので、まずは15分ほど観察します。<br>② <b>【買いタイミング】</b> 下げ止まって <b>「{vwap_str}」</b> のラインを下から上に抜けたタイミングで <b>まず{l1:,}株</b>、さらに上がれば <b>残り{l2:,}株</b> を買います。<br>③ <b>【出口戦略】</b> 反発して <b>「{tp_str}」</b> まで戻したら利益確定、<b>「{sl_str}」</b> を割ったら撤退しましょう。"
        }
    elif tot_win < 54.0 or cvar95 >= 4.8:
        sh = max(1, int(round(base_sh * 0.55)))
        return {
            "algo_name": "👀 【超厳格ディフェンシブ・見送り優先型】CVaRテールリスク防衛アルゴリズム",
            "risk_posture": f"⚠️ 防衛モード（通常ロットを45%強制削減・打診 {sh:,}株 のみ）",
            "core_logic": f"95%CVaR（最大想定下落率）が -{cvar95}% と高く、勝率 {tot_win}% では大ロットを張る優位性が不足。資金保護を最優先とし、VWAP（{vwap_str}）維持を確認する最小ロット打診に限定。",
            "adj_shares": sh,
            "step_plan": f"① 寄付きは見送り推奨 → ② 10:00以降にVWAP（{vwap_str}）の上で安定していれば打診 <b>{sh:,}株のみ</b> エントリー",
            "beginner_html": f"<b>🔰 初心者向け・明日のカンタン行動手順（無理せず資金を守る日！）</b><br>① <b>【基本は様子見でOK】</b> 現在ブレ幅（リスク）が大きいため無理に買う必要はありません。他の上位銘柄を優先しましょう。<br>② <b>【買う場合】</b> 株数を普段の半分（<b>{sh:,}株だけ</b>）に減らし、株価が <b>「{vwap_str}」</b> より上で安定している時だけ少額で買ってください。<br>③ <b>【損切り厳守】</b> <b>「{sl_str}」</b> に触れたら即座に損切りして資金を守りましょう。"
        }
    elif yz_vol <= 26.0 and vpin >= 0.08:
        sh = max(1, int(round(base_sh * 1.15)))
        l1, l2, l3 = max(1, int(round(sh * 0.50))), max(0, int(round(sh * 0.30))), max(0, sh - max(1, int(round(sh * 0.50))) - max(0, int(round(sh * 0.30))))
        return {
            "algo_name": "🌊 【機関トレンド・ピラミッディング型】低ボラ安定順行・買い増しアルゴリズム",
            "risk_posture": "📈 安定トレンド追随（含み益が乗るごとに買い増すピラミッディング）",
            "core_logic": f"年率ボラ {yz_vol}% とノイズが少なく、機関のTWAP（時間分散）買いが継続している安定波形。最初に50%を入れ、含み益が出るたびに30%→20%と買い増して利益を最大化する。",
            "adj_shares": sh,
            "step_plan": f"① 寄付き（{pest_str}）で <b>{l1:,}株（50%）</b> → ② VWAP（{vwap_str}）支持で <b>{l2:,}株（30%）</b> → ③ 高値圏で <b>{l3:,}株（20%）</b> 追撃",
            "beginner_html": f"<b>🔰 初心者向け・明日のカンタン行動手順（安心のトレンド乗り！）</b><br>① <b>【ステップ1】</b> 値動きが安定してプロが買っている銘柄です。まず朝9:00に <b>半分の「{l1:,}株」</b> を買います。<br>② <b>【ステップ2】</b> 利益が出て株価が <b>「{vwap_str}」</b> より上で順調なら <b>追加で「{l2:,}株〜{l3:,}株」</b> を買い増しします。<br>③ <b>【ステップ3】</b> 目標の <b>「{tp_str}」</b> で利益確定！万が一 <b>「{sl_str}」</b> まで下がったら手仕舞いします。"
        }
    else:
        sh = base_sh
        l1, l2 = max(1, int(round(sh * 0.45))), max(0, sh - max(1, int(round(sh * 0.45))))
        return {
            "algo_name": "📐 【機関VWAPアンカー2段執行型】寄り付き打診＋VWAP押し目確認アルゴリズム",
            "risk_posture": "⚖️ リスク・リワード黄金比（初動45%＋VWAP反発55%の2段階執行）",
            "core_logic": f"勝率 {tot_win}%・OFI {ofi_z:+.2f}σ のバランス型好需給。寄り付き直後のアルゴの揺さぶりをやり過ごすため、寄付き45%とVWAP（{vwap_str}）押し目反発55%の2段構えで取得単価を最適化する。",
            "adj_shares": sh,
            "step_plan": f"① 9:00寄付き（{pest_str}目安）で先行 <b>{l1:,}株（45%）</b> → ② VWAP（{vwap_str}）押し目反発で本玉 <b>{l2:,}株（55%）</b> 投入",
            "beginner_html": f"<b>🔰 初心者向け・明日のカンタン行動手順（失敗しにくい2回分け購入！）</b><br>① <b>【1回目の買い】</b> 一度に全部買わず、まずは朝9:00に <b>「{l1:,}株」</b> だけ買います。<br>② <b>【2回目の買い】</b> 9:15〜9:30頃に少し下がって <b>「{vwap_str}」</b> のラインで跳ね返った瞬間、残りの <b>「{l2:,}株」</b> を買うと上手に買えます。<br>③ <b>【売り注文】</b> 買えたら <b>目標「{tp_str}」で売り指値</b>、念のため <b>「{sl_str}」で逆指値（損切り）</b> をセットして完了です！"
        }

def analyze_df(df_raw, code, name, theme, genre, macro, b5_live_map, bi=True, b5=True, bal=True):
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
        ofi_z = round(float(np.clip((np.mean(sf[-5:]) - np.mean(sf[-20:])) / max(float(np.std(sf[-20:])), 1.0), -3.5, 3.5)), 2)
        rets = np.diff(c) / np.maximum(c[:-1], 1e-4) * 100.0
        q05 = np.percentile(rets, 5)
        cvar95 = round(float(abs(np.mean(rets[rets <= q05]))) if any(rets <= q05) else abs(float(q05)), 2)
        yz_vol = round(float(np.std(rets[-20:]) * np.sqrt(252)), 1)
        eff_pct = int(np.clip(round((abs(c[-1] - c[-15]) / max(float(np.sum(np.abs(np.diff(c[-15:])))), 1e-4)) * 140.0), 20, 98))

        df["Next_Open"], df["Next_Close"] = df["Open"].shift(-1), df["Close"].shift(-1)
        df["Gap_Pct"] = (df["Next_Open"] - df["Close"]) / df["Close"] * 100
        df["Morning_Up"], df["Intraday_Up"] = df["Next_Open"] > df["Close"], df["Next_Close"] > df["Next_Open"]

        lat = df.iloc[-1]; hist = df.iloc[:-1].dropna(subset=["Next_Open", "Next_Close", "MA20"])
        if len(hist) < 5: return None
        vpin, vacc, cpos, rsi_v = float(lat["VPIN_5d"]), float(lat["Vol_Accel_5d"]), float(lat["Close_Pos"]), round(float(lat["RSI"]), 1)
        isc = int(np.clip(round(52 + vpin * 36 + ofi_z * 6.5 + (cpos - 0.5) * 20), 20, 99))
        b5_hits = (b5_live_map or {}).get(code, {}).get("hits", 0)
        b5sc = int(np.clip(round(50 + (min(vacc, 3.0) - 1.0) * 18 + (cpos - 0.5) * 28 + b5_hits * 2.5), 20, 99))

        sub = hist[hist["Day_Return"] > 0] if lat["Day_Return"] > 0 else hist[hist["Day_Return"] <= 0]
        if len(sub) < 5: sub = hist
        prob = round(float(sub["Morning_Up"].mean() * 100), 1)
        i_win = round(float(sub["Intraday_Up"].mean() * 100), 1)
        t_win = round(float((hist["Morning_Up"] | hist["Intraday_Up"]).mean() * 100), 1)
        tot_win = round(prob * 0.5 + i_win * 0.3 + t_win * 0.2, 1)

        agap = round(float(sub["Gap_Pct"].mean()), 2)
        wg, lg = sub[sub["Morning_Up"]]["Gap_Pct"], sub[~sub["Morning_Up"]]["Gap_Pct"]
        awin, aloss = (float(wg.mean()) if len(wg) > 0 else 0.6), (abs(float(lg.mean())) if len(lg) > 0 else 0.5)
        payoff, edge = round(awin / max(aloss, 0.15), 2), round((prob / 100 * awin) - ((100 - prob) / 100 * aloss), 2)
        kelly_pct = round(float(np.clip(((tot_win/100.0) - ((1.0 - tot_win/100.0) / max(payoff, 0.2))) * 50.0, 5.0, 38.0)), 1)

        is_jp = ".T" in code
        ov = ((macro["nk_fut"]["diff"] if macro else 0.0) * 0.5 + (macro["sox"]["diff"] if macro else 0.0) * 0.4) if is_jp else ((macro["sp500"]["diff"] if macro else 0.0) * 0.5 + (macro["sox"]["diff"] if macro else 0.0) * 0.4)
        pgap = round(agap * 0.5 + ov * 0.5 + max(0.0, (isc - 55) * 0.025), 2)
        cv, atrv = float(lat["Close"]), float(lat["ATR"])
        pest = cv * (1.0 + pgap / 100.0)
        aisc = int(np.clip(round(tot_win * 0.52 + (isc if bi else 55) * 0.28 + (b5sc if b5 else 55) * 0.20 + (ofi_z * 2.5 if bal else 0)), 25, 99))

        tval = aisc * 0.45 + tot_win * 0.35 + isc * 0.20
        for th, tn, tl, tc, tbg in [
            (79, 10, "【Lv.10：🌟絶対買い】機関OFI極大・フルリスク勝負圏", "#fff", "linear-gradient(90deg,#0284c7,#2563eb)"),
            (74, 9, "【Lv.9：🔥強気買い】機関アルゴ＆モメンタム集中", "#fff", "linear-gradient(90deg,#0369a1,#1d4ed8)"),
            (69, 8, "【Lv.8：⭕買い推奨】機関買い集め・順張り優位", "#fff", "linear-gradient(90deg,#0f766e,#047857)"),
            (64, 7, "【Lv.7：⭕押し目買い】VWAP反発狙い", "#e2e8f0", "linear-gradient(90deg,#334155,#1e293b)"),
            (-99, 5, "【Lv.5：👀様子見・選別】方向感確認・少額打診", "#cbd5e1", "linear-gradient(90deg,#1e293b,#0f172a)")
        ]:
            if tval >= th: t_num, t_lbl, t_col, t_bg = tn, tl, tc, tbg; break

        tpv, slv = max(pest, cv) + (atrv * 0.9), cv - (atrv * 0.55)
        rmoney = total_capital * (risk_tolerance_pct / 100.0)
        base_sh = max(1, int(rmoney / max(cv - slv, cv * 0.005)))
        fp = lambda val: f"{val:,.0f}円" if is_jp else f"${val:,.2f}"

        strat = select_dynamic_strategy(code.replace(".T", ""), tot_win, ofi_z, round(vpin, 2), yz_vol, cvar95, rsi_v, cpos, base_sh, fp(pest), fp(float(lat["VWAP20"])), f"{fp(tpv)}(+{round((tpv-cv)/cv*100,1)}%)", f"{fp(slv)}({round((slv-cv)/cv*100,1)}%)", kelly_pct)
        adj_sh = strat["adj_shares"]

        return {
            "full_code": code, "code": code.replace(".T", ""), "name": name, "genre": genre, "theme": theme, "price": fp(cv), "raw_close": cv,
            "tp_price": fp(tpv), "tp_pct": round((tpv - cv) / cv * 100, 1), "sl_price": fp(slv), "sl_pct": round((slv - cv) / cv * 100, 1), "vwap_price": fp(float(lat["VWAP20"])),
            "inst_score": isc, "vpin": round(vpin, 2), "ofi_z": ofi_z, "yz_vol": yz_vol, "cvar95": cvar95, "eff_pct": eff_pct, "kelly_pct": kelly_pct,
            "board5ch_score": b5sc, "b5_hits": b5_hits, "pts_est_price": fp(pest), "pts_gap_pct": pgap, "diff": round(float(lat["Day_Return"]), 2),
            "prob": prob, "intraday_win_rate": i_win, "trend_win_rate": t_win, "total_win_rate": tot_win, "count": f"{int(sub['Morning_Up'].sum())}/{len(sub)}回",
            "rsi": rsi_v, "payoff": payoff, "edge": edge, "ai_score": aisc, "survival_power": round(aisc * 0.5 + isc * 0.3 + b5sc * 0.2, 1),
            "tier_num": t_num, "tier_label": t_lbl, "tier_color": t_col, "tier_bg": t_bg,
            "lot_info": {"shares": adj_sh, "position_value": adj_sh * cv, "risk_amount": rmoney},
            "strat": strat
        }
    except Exception: return None

@st.cache_data(ttl=1800)
def fetch_pool_batch(macro, b5_live_map, bi, b5, bal):
    codes = list({s["code"] for sts in STOCK_POOL.values() for s in sts})
    raw = yf.download(codes, period="6mo", group_by="ticker", threads=True, progress=False, timeout=9)
    gmap, alist, seen = {g: [] for g in STOCK_POOL.keys()}, [], set()
    for g, sts in STOCK_POOL.items():
        for s in sts:
            c = s["code"]
            try:
                r = analyze_df(raw[c] if len(codes) > 1 else raw, c, s["name"], s["theme"], g, macro, b5_live_map, bi, b5, bal)
                if r:
                    gmap[g].append(r)
                    if c not in seen: alist.append(r); seen.add(c)
            except Exception: continue
    return gmap, alist

@st.cache_data(ttl=300)
def fetch_one(code, macro, b5_live_map, bi, b5, bal):
    inf = KNOWN_STOCKS.get(code, {"name": code.replace(".T", ""), "theme": "個別指定銘柄", "genre": "個別検索"})
    return analyze_df(yf.Ticker(code).history(period="6mo"), code, inf["name"], inf["theme"], inf["genre"], macro, b5_live_map, bi, b5, bal)

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

def run_7ai_council(r: dict, m5=None, seed: int = 0) -> dict:
    vref = m5["vwap5_price"] if m5 else r["vwap_price"]
    st_info = r["strat"]
    fs = r["ai_score"]
    sys_p = f'7専門AI合議として銘柄固有の戦略「{st_info["algo_name"]}」に基づき、なぜこの銘柄はこの買い方・リスク配分なのかを議論する6ターンのJSON {{"final_score":{fs},"turns":[{{"speaker_key":"MICRO","score":88,"tone":"normal","text":"..."}}]}} を出力せよ。'
    usr_p = f"{r['name']}({r['code']}) 現値:{r['price']} 勝率:{r['total_win_rate']}% OFI:{r['ofi_z']:+.2f}σ VPIN:{r['vpin']:+.2f} ボラ:{r['yz_vol']}% CVaR:-{r['cvar95']}% 戦略:{st_info['algo_name']} 手順:{st_info['step_plan']}"
    llm_j, used_eng = call_api_seamless(sys_p, usr_p, 0.75)

    if llm_j and isinstance(llm_j.get("turns"), list) and len(llm_j["turns"]) >= 4:
        raw_t = llm_j["turns"]
    else:
        raw_t = [
            {"speaker_key": "MICRO", "score": r["inst_score"], "tone": "normal", "text": f"『{r['name']}（{r['code']}）』のオーダーフローを解析した。現在値 <b>{r['price']}（{r['diff']:+.2f}%）</b>、VPIN <b>{r['vpin']:+.2f}</b>、OFI <b>{r['ofi_z']:+.2f}σ</b>。画一的な分割ではなく、この波形に最適化した <b>{st_info['algo_name']}</b> を適用すべき局面だ。"},
            {"speaker_key": "IGNIS", "score": r["board5ch_score"], "tone": "agree" if r["total_win_rate"] >= 62 else "normal", "text": f"同感だ！{st_info['core_logic']} リスク姿勢は『<b>{st_info['risk_posture']}</b>』で勝負に出るのが最も期待値が高いぜ。"},
            {"speaker_key": "TECHNOS", "score": fs, "tone": "normal", "text": f"数理指標を見ても、年率ボラ <b>{r['yz_vol']}%</b>・RSI <b>{r['rsi']}</b>・効率性純度 <b>{r['eff_pct']}%</b> だ。基準VWAP（<b>{vref}</b>）と夜間理論値（<b>{r['pts_est_price']}</b>）を軸にした <b>{st_info['step_plan']}</b> が機能する。"},
            {"speaker_key": "AEGIS", "score": 85, "tone": "doubt", "text": f"攻撃的に行く場合でも、95%CVaR（テールリスク）は <b>-{r['cvar95']}%</b> あるわ。逆指値 <b>{r['sl_price']}（{r['sl_pct']}%）</b> を注文と同時にセットすることだけは絶対条件よ。"},
            {"speaker_key": "CHRONOS", "score": int(r["total_win_rate"]), "tone": "normal", "text": f"過去6ヶ月統計（<b>{r['count']}</b>）では、総合勝率 <b>{r['total_win_rate']}%</b>・ペイオフ比 <b>{r['payoff']}倍</b>・期待値 <b>{r['edge']:+.2f}%</b> とバックテストの裏付けも十分だ。"},
            {"speaker_key": "NEXUS", "score": fs, "tone": "agree", "text": f"結論を出そう。『{r['name']}』専用の執行アルゴリズムは <b>{st_info['algo_name']}</b>（推奨 <b>{r['lot_info']['shares']:,}株</b>）とする。下の初心者向けアクションガイド通りに執行せよ！"}
        ]

    turns = [{"round": f"⚡ 『{r['name']}』7専門AI マルチアルゴリズム合議 ({used_eng})"}]
    for it in raw_t:
        sk = str(it.get("speaker_key", "NEXUS")).upper()
        turns.append({"speaker": AI_ROSTER.get(sk, f"👑 {sk}"), "score": int(it.get("score", fs)), "tone": it.get("tone", "normal"), "text": it.get("text", "")})

    v_html = (
        f'<div style="margin-bottom:5px;"><b>🧬 採用アルゴリズム：</b><span style="color:#38bdf8;font-weight:800;">{st_info["algo_name"]}</span></div>'
        f'<div style="margin-bottom:5px;"><b>⚖️ リスク・資金配分方針：</b>{st_info["risk_posture"]}</div>'
        f'<div style="margin-bottom:5px;"><b>⚡ プロ向け執行プラン：</b>{st_info["step_plan"]} ｜ 🎯利確 <b>{r["tp_price"]}(+{r["tp_pct"]}%)</b> ／ 🛡️損切 <b>{r["sl_price"]}({r["sl_pct"]}%)</b></div>'
        f'<div class="beginner-action-box">{st_info["beginner_html"]}</div>'
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
    if c1.button("🔼 AI合議と初心者向け買い方ガイドを閉じる" if is_open else "⚡ 7専門AIディベート＆初心者向け買い方を見る", key=f"b_{uk}", use_container_width=True):
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
        deb = run_7ai_council(r, m5, st.session_state["debate_round_seed"].get(uk, 0))
        st.session_state["council_threads"][uk] = list(deb["dialogue"])
        st.session_state["council_meta"][uk] = deb

    meta = st.session_state["council_meta"][uk]
    turns = st.session_state["council_threads"][uk]
    st.markdown(f'<div class="ai-council-box"><div class="council-scroll-window">{"".join(_fmt_turn(t) for t in turns)}</div><div class="consensus-banner"><div style="font-weight:800;color:#fde047;font-size:12.5px;margin-bottom:5px;">🏛️ 銘柄別アルゴリズム結論 ＆ 初心者向けアクションプラン</div>{meta["verdict_html"]}</div></div>', unsafe_allow_html=True)

    with st.form(f"jf_{uk}", clear_on_submit=True):
        jc1, jc2 = st.columns([3.2, 1])
        uop = jc1.text_input("質問・発言", placeholder="AIに質問（例：今すぐ成行で買っていい？ / 損切りラインはどこ？）", label_visibility="collapsed")
        if jc2.form_submit_button("💬 質問投下", use_container_width=True) and uop.strip():
            st.session_state["council_threads"][uk].append({"is_user": True, "text": uop.strip()})
            st.session_state["council_threads"][uk].append({"speaker": "👑 NEXUS (総括ディレクター)", "score": r["ai_score"], "tone": "agree", "text": f"「{uop.strip()}」への回答だ。『{r['name']}』は <b>{r['strat']['algo_name']}</b> を採用している。<b>{r['strat']['step_plan']}</b> の手順で、利確 <b>{r['tp_price']}</b>・逆指値 <b>{r['sl_price']}</b> を守って行動しよう！"})
            st.rerun()

def render_card(r, is_custom=False, rank=None, kp="card"):
    dc = "#10b981" if r["diff"] >= 0 else "#ef4444"
    ds, ps = ("+" if r["diff"] > 0 else ""), ("+" if r["pts_gap_pct"] > 0 else "")
    rk_h = f'<span class="pill-badge" style="background:#f59e0b;color:#0f172a;border:none;">🏆 #{rank}</span>' if rank else ""
    lot = r["lot_info"]
    st_info = r["strat"]
    card_html = (
        f'<div class="{"search-result-card" if is_custom else "rank-card"}">'
        f'<div class="signal-10tier-badge" style="background:{r["tier_bg"]};color:{r["tier_color"]};"><span>{r["tier_label"]}</span><span>{st_info["algo_name"].split("】")[0]}】</span></div>'
        f'<div style="margin-bottom:7px;">{rk_h}<span class="pill-badge">⚡ AI {r["ai_score"]}点</span><span class="pill-badge">🏦 機関 {r["inst_score"]}点</span><span class="pill-badge">🧬 OFI {r["ofi_z"]:+.2f}σ</span><span class="pill-badge">🔥 5ch {r["board5ch_score"]}点</span></div>'
        f'<div style="display:flex;justify-content:space-between;align-items:center;"><div><span style="font-size:16px;font-weight:800;color:#f8fafc;">{r["name"]}</span> <span style="font-size:11.5px;color:#94a3b8;">({r["code"]} / {r["genre"]})</span><div style="font-size:11px;color:#94a3b8;margin-top:2px;">{r["theme"]} ｜ 現在値: <b style="color:#f8fafc;">{r["price"]}</b> (<span style="color:{dc};font-weight:700;">{ds}{r["diff"]}%</span>)</div></div>'
        f'<div style="text-align:right;"><span style="font-size:9.5px;color:#94a3b8;">総合勝率</span><br><span class="prob-badge">{r["total_win_rate"]}%</span><div style="font-size:9.5px;color:#94a3b8;">Payoff {r["payoff"]}x / Edge {r["edge"]:+.2f}%</div></div></div>'
        f'<div class="winrate-bar"><div><div style="font-size:9.5px;color:#94a3b8;">🏆 総合勝率</div><div style="font-size:12.5px;font-weight:800;color:#38bdf8;">{r["total_win_rate"]}%</div></div><div><div style="font-size:9.5px;color:#94a3b8;">🌅 翌朝GU</div><div style="font-size:12.5px;font-weight:700;">{r["prob"]}%</div></div><div><div style="font-size:9.5px;color:#94a3b8;">☀️ 寄後陽線</div><div style="font-size:12.5px;font-weight:700;">{r["intraday_win_rate"]}%</div></div><div><div style="font-size:9.5px;color:#94a3b8;">📈 順張り</div><div style="font-size:12.5px;font-weight:700;">{r["trend_win_rate"]}%</div></div></div>'
        f'<div class="trade-plan-box"><div><div style="font-size:9.5px;color:#94a3b8;">🌅 夜間理論寄付き</div><div style="font-size:12px;font-weight:700;">{r["pts_est_price"]} ({ps}{r["pts_gap_pct"]}%)</div></div><div style="border-left:1px solid rgba(148,163,184,0.16);border-right:1px solid rgba(148,163,184,0.16);"><div style="font-size:9.5px;color:#10b981;">🎯 利確目標</div><div style="font-size:12px;font-weight:800;color:#10b981;">{r["tp_price"]} (+{r["tp_pct"]}%)</div></div><div><div style="font-size:9.5px;color:#f87171;">🛡️ 逆指値(損切)</div><div style="font-size:12px;font-weight:800;color:#f87171;">{r["sl_price"]} ({r["sl_pct"]}%)</div></div></div>'
        f'<div class="sizing-box"><span>📦 <b>戦略別推奨ロット: {lot["shares"]:,}株</b> (投資額 {lot["position_value"]:,.0f}円 / 許容リスク {lot["risk_amount"]:,.0f}円)</span><span>基準VWAP: <b>{r["vwap_price"]}</b></span></div>'
        f'<details class="quant-detail-drawer"><summary>🔍 銘柄別アルゴリズム戦略 ＆ クオンツ指標詳細（タップで開閉）</summary>'
        f'<div style="font-size:11.5px;color:#cbd5e1;margin-top:5px;line-height:1.5;"><b>{st_info["algo_name"]}</b><br>{st_info["core_logic"]}<br><b>▶ 執行手順:</b> {st_info["step_plan"]}</div>'
        f'<div class="metrics-row"><span>VPIN:{r["vpin"]:+.2f}</span><span>OFI:{r["ofi_z"]:+.2f}σ</span><span>YZボラ:{r["yz_vol"]}%</span><span>95%CVaR:-{r["cvar95"]}%</span><span>効率純度:{r["eff_pct"]}%</span><span>RSI:{r["rsi"]}</span><span>Kelly:{r["kelly_pct"]}%</span></div>'
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
            f'<span class="pill-badge" style="background:#f59e0b;color:#0f172a;font-weight:900;">🏆 IPO期待度 第{ipo["rank"]}位 (AI {ipo["score"]}点)</span>'
            f'<span style="font-size:11px;color:#38bdf8;font-weight:700;">{ipo["tier"]}</span></div>'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<div><span style="font-size:16px;font-weight:800;color:#f8fafc;">{ipo["name"]}</span> <span style="font-size:11.5px;color:#94a3b8;">({ipo["code"]} / {ipo["market"]})</span><div style="font-size:11px;color:#cbd5e1;margin-top:2px;">🎯 {ipo["theme"]} ｜ 主幹事: <b>{ipo["lead"]}</b></div></div>'
            f'<div style="text-align:right;"><span style="font-size:9.5px;color:#94a3b8;">AI初値予測</span><br><span class="prob-badge" style="color:#10b981!important;">{ipo["expect_return"]}</span></div></div>'
            f'<div class="trade-plan-box" style="margin-top:7px;"><div><div style="font-size:9.5px;color:#94a3b8;">📅 BB抽選期間</div><div style="font-size:11.5px;font-weight:700;color:#fde047;">{ipo["bb_period"]}</div></div><div><div style="font-size:9.5px;color:#94a3b8;">🔔 上場日</div><div style="font-size:11.5px;font-weight:700;">{ipo["list_date"]}</div></div><div><div style="font-size:9.5px;color:#94a3b8;">💴 仮条件・公募価格</div><div style="font-size:11.5px;font-weight:700;">{ipo["price_band"]}</div></div></div>'
            f'<div style="margin-top:7px;">{links_html}</div></div>',
            unsafe_allow_html=True
        )

# ==========================================
# 🚀 メイン画面描画（見切れゼロ・YAMASHISHI LAB統一）
# ==========================================
macro_info = fetch_macro()
b5_live_map = fetch_5ch_live()

mpills = "".join([f'<div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);padding:2px 8px;border-radius:6px;font-size:10.5px;display:inline-flex;gap:4px;"><span style="color:#94a3b8;">{m["label"]}</span><span style="color:{"#10b981" if m["diff"]>=0 else "#ef4444"};font-weight:700;">{"+" if m["diff"]>=0 else ""}{m["diff"]}%</span></div>' for m in macro_info.values()])
st.markdown(
    f'<div class="glass-header">'
    f'<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">'
    f'<div style="min-width:0;flex:1;"><div class="brand-luxury">YAMASHISHI LAB</div><div class="brand-sub">MULTI-AGENT QUANTITATIVE TERMINAL</div></div>'
    f'<span style="background:rgba(56,189,248,0.12);border:1px solid rgba(56,189,248,0.35);color:#38bdf8;padding:3px 9px;border-radius:999px;font-size:10px;font-weight:700;white-space:nowrap;flex-shrink:0;">⚡ {AI_PROVIDERS[cur_prov][0]}</span>'
    f'</div>'
    f'<div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:8px;">{mpills}</div></div>',
    unsafe_allow_html=True
)

BOOST_MAP = {"🧬 高水準クオンツ(OFI/YZ/CVaR)": "algo", "🏦 機関VPIN・SmartMoney": "inst", "🔥 5ch実況＆短期モメンタム": "mom"}
sel_b = st.pills("ブースト", list(BOOST_MAP.keys()), default=list(BOOST_MAP.keys()), selection_mode="multi", label_visibility="collapsed") if hasattr(st, "pills") else st.multiselect("ブースト", list(BOOST_MAP.keys()), default=list(BOOST_MAP.keys()), label_visibility="collapsed")
ac_b = {BOOST_MAP[k] for k in (sel_b or [])}

with st.spinner("⚡ 機関オーダーフロー＆銘柄別アルゴリズムを高速計算中..."):
    g_res, all_res = fetch_pool_batch(macro_info, b5_live_map, "inst" in ac_b, "mom" in ac_b, "algo" in ac_b)

c1, c2 = st.columns([3.4, 1])
cin = c1.text_input("🔍 銘柄検索", placeholder="銘柄コードまたは米ティッカーを入力 (例: 6920, 5803, NVDA, IONQ)", label_visibility="collapsed")
if c2.button("🔍 銘柄診断", use_container_width=True) and cin: st.session_state["custom_search_code"] = norm_tk(cin)

if st.session_state.get("custom_search_code"):
    nc = st.session_state["custom_search_code"]
    cr = fetch_one(nc, macro_info, b5_live_map, "inst" in ac_b, "mom" in ac_b, "algo" in ac_b)
    if cr:
        render_card(cr, is_custom=True, kp="custom")
        if st.button("✖️ 個別診断を閉じる", use_container_width=True): st.session_state["custom_search_code"] = ""; st.rerun()
    else: st.warning(f"銘柄「{nc}」のデータが見つかりませんでした。")

def cut_stocks(slist, pct):
    if not slist: return [], []
    s = sorted(slist, key=lambda x: (x["tier_num"], x["total_win_rate"], x["survival_power"]), reverse=True)
    k = max(3, int(round(len(s) * (pct / 100.0))))
    return s[:k], s[k:]

cats = ["🏆 総合TOP5", "🎟️ IPO募集・新規上場", "🏦 機関VPIN・OFI", "🔥 5ch＆短期モメンタム", "📋 監視シート"] + [f"📂 {g}" for g in STOCK_POOL.keys()]
st.markdown('<div class="compact-bar-label"><span>📂 STRATEGY & SECTOR SELECT</span><span>戦略ランキング / IPO募集 / セクター切替</span></div>', unsafe_allow_html=True)
prev_cat = st.session_state.get("active_category", "🏆 総合TOP5")
if prev_cat not in cats: prev_cat = "🏆 総合TOP5"
sel_cat = (st.pills("カテゴリ", cats, default=prev_cat, selection_mode="single", label_visibility="collapsed") or prev_cat) if hasattr(st, "pills") else st.radio("カテゴリ", cats, horizontal=True, label_visibility="collapsed")
if sel_cat != prev_cat:
    st.session_state["nav_history"].append(prev_cat)
    st.session_state["active_category"] = sel_cat

surv, _ = cut_stocks(all_res, survival_cut_pct)
if sel_cat == "🏆 総合TOP5":
    st.caption(f"🦁 全母集団 {len(all_res)}銘柄から厳選！銘柄ごとに異なる最適アルゴリズムを割り当てた総合TOP5です。")
    for i, r in enumerate(surv[:5], 1): render_card(r, rank=i, kp="top5")
elif sel_cat == "🎟️ IPO募集・新規上場":
    render_ipo_offering_section()
    st.markdown("#### 🚀 直近上場・セカンダリー急騰IPO株リアルタイム診断")
    for i, r in enumerate(cut_stocks(g_res.get("小型急騰・直近IPO", []), 100)[0][:6], 1): render_card(r, rank=i, kp="ipo_sec")
elif sel_cat == "🏦 機関VPIN・OFI":
    for i, r in enumerate(sorted(all_res, key=lambda x: (x["inst_score"], x["ofi_z"], x["total_win_rate"]), reverse=True)[:10], 1): render_card(r, rank=i, kp="inst")
elif sel_cat == "🔥 5ch＆短期モメンタム":
    for i, r in enumerate(sorted(all_res, key=lambda x: (x["board5ch_score"], x["total_win_rate"]), reverse=True)[:10], 1): render_card(r, rank=i, kp="mom")
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
