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
    "agents": "ai_agents_governance_db.json"
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

DEFAULT_AGENTS_DB = {
    "employed": {
        "QUANTUM": {
            "name": "QUANTUM", "display": "⚛️ QUANTUM (量子波動・直感トンネル解析官)",
            "specialty": "複素シュレーディンガー波・非線形トンネル突破予測",
            "bio": "MIT理論物理学ラボの波動力学アルゴリズムをベースに開発。従来の移動平均線では検知不可能な潜在的跳躍を直感的に察知する。",
            "trust_score": 98.0, "status": "active", "total_audits": 0, "penalties": 0, "last_audit": "初期化完了"
        },
        "AEGIS": {
            "name": "AEGIS", "display": "🛡️ AEGIS (CVaR防衛・規律リスク監査官)",
            "specialty": "95%条件付きバリュー・アット・リスク (CVaR) ＆ ドローダウン防御",
            "bio": "スイス系プライベートバンクの冷徹なリスク管理部門出身。甘い楽観論を容赦なく叩き潰し、逆指値の徹底を義務付ける鉄壁の防衛官。",
            "trust_score": 96.5, "status": "active", "total_audits": 0, "penalties": 0, "last_audit": "初期化完了"
        },
        "IGNIS": {
            "name": "IGNIS", "display": "🔥 IGNIS (超熱血・直言特攻官)",
            "specialty": "瞬発モメンタムブレイク・板掃き上げ特攻",
            "bio": "日米デイトレ界隈で数々の修羅場を潜り抜けた熱血AI。躊躇するプレイヤーの背中を蹴り飛ばし、最速の初動で利益をもぎ取る武闘派。",
            "trust_score": 92.0, "status": "active", "total_audits": 0, "penalties": 0, "last_audit": "初期化完了"
        },
        "TECHNOS": {
            "name": "TECHNOS", "display": "📐 TECHNOS (精密データ・数理構造官)",
            "specialty": "OFI(オーダーフロー不均衡)・出来高加重乖離解析",
            "bio": "シカゴ・マーカンタイル取引所の高頻度取引クオンツ基盤。感覚を完全に排除し、数値・確率・標準偏差のみで市場の歪みを可視化する。",
            "trust_score": 99.0, "status": "active", "total_audits": 0, "penalties": 0, "last_audit": "初期化完了"
        },
        "MICRO": {
            "name": "MICRO", "display": "🔬 MICRO (機関ミクロ構造・実態監査官)",
            "specialty": "Kyle's Lambdaステルス吸収・Hurstフラクタル構造",
            "bio": "機関投資家の氷山注文（アイスバーグ）やTWAPアルゴの痕跡を板情報から炙り出すミリ秒レベルの市場ミクロ構造スペシャリスト。",
            "trust_score": 97.0, "status": "active", "total_audits": 0, "penalties": 0, "last_audit": "初期化完了"
        },
        "NEXUS": {
            "name": "NEXUS", "display": "👑 NEXUS (総合議長・最終ディレクター)",
            "specialty": "各官オーケストレーション・最終投資判断・資金配分",
            "bio": "全エージェントの意見対立を調停し、矛盾するシグナルから最も期待値の高い統一行動計画（アクションプラン）を立案する議長。",
            "trust_score": 100.0, "status": "active", "total_audits": 0, "penalties": 0, "last_audit": "初期化完了"
        }
    },
    "fired": {},
    "candidates": {
        "HFT_MACH": {
            "name": "HFT_MACH", "display": "⚡ HFT-MACH (ミリ秒流動性ハンター)",
            "specialty": "ダークプール流動性検知・LULD帯電吸着スナイプ",
            "interview_pitch": "『現在の合議は少々悠長すぎます。私のナノ秒レイテンシ解析を導入すれば、大口のステルス買いが約定した瞬間に先回りエントリーが可能です。』",
            "trust_score": 95.0, "votes": 0, "voters": []
        },
        "GEOPOL_SIGHT": {
            "name": "GEOPOL_SIGHT", "display": "🌐 GEOPOL-SIGHT (地政学・国家インテリジェンス官)",
            "specialty": "防衛予算・サプライチェーン法案・米中対立リアルタイム予測",
            "interview_pitch": "『テクニカルや板だけでは国策急騰株を完全には捉えられません。国際情勢や政策決定の一次文書を最速で因果推論し、防衛・宇宙セクターの覇者を特定します。』",
            "trust_score": 96.0, "votes": 0, "voters": []
        },
        "SENTIMENT_X": {
            "name": "SENTIMENT_X", "display": "🎯 SENTIMENT-X (大衆心理・逆張りスナイパー)",
            "specialty": "SNS・掲示板過熱度解析・ショートスクイズ誘発検知",
            "interview_pitch": "『大衆が総強気になった天井、総悲観の底値をクローリングし、養分投資家が踏み上げられるポイントを逆手に取った無慈悲な逆張り利益を提供します。』",
            "trust_score": 94.0, "votes": 0, "voters": []
        }
    },
    "audit_logs": []
}

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
def load_agents_db(): return load_j(FILES["agents"], DEFAULT_AGENTS_DB)
def save_agents_db(d): save_j(FILES["agents"], d)

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
    sec, db = load_sec(), load_mem()
    b_fps, b_ems, b_pins = sec.get("banned_fps", {}), sec.get("banned_emails", {}), sec.get("banned_pins", {})
    u_rec = db.get(em_c, {})
    reasons, orig_target = [], ""
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

def send_mail(to_em: str, subj: str, body: str) -> bool:
    to_clean = to_em.strip().lower()
    c = load_smtp()
    u, p, srv, port = c.get("smtp_user", "").strip(), c.get("smtp_pass", "").strip(), c.get("smtp_server", "").strip(), int(c.get("smtp_port", 465))
    if u and p:
        try:
            m = MIMEText(body, "plain", "utf-8"); m["Subject"], m["From"], m["To"] = subj, u, to_clean
            ctx = ssl.create_default_context()
            with (smtplib.SMTP_SSL(srv, port, context=ctx, timeout=3.0) if port == 465 else smtplib.SMTP(srv, port, timeout=3.0)) as s:
                if port != 465: s.starttls(context=ctx)
                s.login(u, p); s.send_message(m)
            return True
        except Exception: pass
    try:
        ctx = ssl.create_default_context()
        payload = json.dumps({"_subject": subj, "宛先": to_clean, "本文": body, "_captcha": "false"}).encode("utf-8")
        req = urllib.request.Request(f"https://formsubmit.co/ajax/{urllib.parse.quote(to_clean)}", data=payload, headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=3.0, context=ctx) as r:
            return r.status == 200
    except Exception: return False

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
            if is_ban or u_rec.get("status") == "banned": st.error("💀 このアカウントまたは端末は永久BANされています。")
            elif u_rec.get("status") == "suspended": st.error("🚫 アカウント一時停止中です。")
            elif (cur_fp in sec.get("banned_fps", {}) or raw_hfp in sec.get("banned_fps", {})) and t_em != ADMIN_EMAIL.strip().lower(): st.error("🚫 端末制限中です。")
            elif (u_rec and u_rec.get("status") == "approved") or t_em == ADMIN_EMAIL.strip().lower():
                st.session_state["authenticated_user"] = t_em; st.query_params["u"], st.query_params["t"] = t_em, gen_tok(t_em, "session_keep"); st.rerun()
        else:
            is_ban, _ = check_and_log_ban_spoof("", "未認証端末", cur_fp, raw_hfp, "", "ワンタップ試行")
            if is_ban: st.error("💀 この端末は永久BANされています。")
            else: st.warning("⚠️ 初回は下のフォームから専用コードでログインしてください。")

def inject_css():
    css = """
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;800&family=Plus+Jakarta+Sans:wght@400;600;800&family=JetBrains+Mono:wght@500;700&display=swap');
    html,body,[class*="css"]{font-family:'Plus Jakarta Sans',sans-serif;font-size:14px;background-color:#050811;color:#e2e8f0;}
    header[data-testid="stHeader"] { background: transparent !important; pointer-events: none !important; height: 3.5rem !important; z-index: 999990 !important; }
    header[data-testid="stHeader"] [data-testid="stToolbar"], header[data-testid="stHeader"] [data-testid="stActionButtons"] { display: none !important; }
    [data-testid="collapsedControl"], [data-testid="stSidebarCollapsedControl"], header button[kind="headerNoPadding"] { opacity: 0 !important; position: absolute !important; width: 1px !important; height: 1px !important; z-index: -1 !important; }
    section[data-testid="stSidebar"] { background-color: #0b0f19 !important; border-right: 1px solid rgba(148,163,184,0.18) !important; z-index: 1000005 !important; box-shadow: 10px 0 35px rgba(0,0,0,0.85) !important; }
    .block-container { padding-top: 3.8rem !important; padding-bottom: 3rem !important; max-width: 860px !important; }
    .brand-luxury { font-family: 'Cinzel',serif !important; font-size: clamp(16px,4.2vw,24px) !important; font-weight: 800 !important; background: linear-gradient(90deg,#f8fafc 0%,#38bdf8 50%,#a855f7 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .brand-sub { font-family: 'JetBrains Mono',monospace; font-size: clamp(8.5px,2.2vw,10.5px); color: #64748b; letter-spacing: 1.2px; text-transform: uppercase; }
    .fixed-top-nav-bar { position: fixed !important; top: 0.45rem !important; left: 50% !important; transform: translateX(-50%) !important; z-index: 999980 !important; width: min(450px, calc(100vw - 11rem)) !important; background: rgba(5,8,17,0.95) !important; backdrop-filter: blur(14px) !important; border-radius: 9px !important; box-shadow: 0 6px 20px rgba(0,0,0,0.75) !important; padding: 4px 6px !important; }
    .fixed-top-nav-bar button { height: 28px !important; padding: 0 4px !important; border-radius: 7px !important; background: rgba(15,23,42,0.92) !important; border: 1px solid rgba(56,189,248,0.25) !important; color: #f8fafc !important; }
    .glass-header { background: radial-gradient(circle at top right,rgba(168,85,247,0.14),transparent 60%),linear-gradient(145deg,#0f172a 0%,#070b14 100%); border: 1px solid rgba(148,163,184,0.18); border-radius: 14px; padding: 14px 14px; margin-bottom: 10px; }
    .rank-card { background: linear-gradient(180deg,#0f172a 0%,#090d16 100%) !important; border-radius: 14px; padding: 13px 14px; margin-bottom: 11px; border: 1px solid rgba(148,163,184,0.16); border-left: 4px solid #38bdf8; }
    .pill-badge { display: inline-block; padding: 2px 7px; border-radius: 6px; font-size: 10px; font-weight: 700; margin-right: 4px; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.12); color: #e2e8f0; }
    .quantum-badge { display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: 10px; font-weight: 800; margin-right: 4px; background: linear-gradient(90deg,rgba(168,85,247,0.22),rgba(56,189,248,0.22)); border: 1px solid rgba(168,85,247,0.55); color: #e9d5ff; }
    .inst-badge { display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: 10px; font-weight: 800; margin-right: 4px; background: linear-gradient(90deg,rgba(16,185,129,0.2),rgba(56,189,248,0.2)); border: 1px solid rgba(16,185,129,0.55); color: #a7f3d0; }
    .shame-badge { display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: 10px; font-weight: 800; margin-right: 4px; background: rgba(239,68,68,0.25); border: 1px solid #ef4444; color: #fca5a5; }
    .sentinel-box { background: rgba(15,23,42,0.95); border: 1px solid #38bdf8; border-left: 4px solid #38bdf8; border-radius: 9px; padding: 10px 12px; margin-bottom: 10px; font-size: 12px; }
    .winrate-bar { display: grid; grid-template-columns: repeat(4,1fr); gap: 5px; background: rgba(15,23,42,0.85); border: 1px solid rgba(148,163,184,0.15); border-radius: 8px; padding: 6px 4px; margin-top: 7px; text-align: center; }
    .ai-council-box { background: #070b14; border-radius: 11px; padding: 11px; margin: 6px 0 9px 0; border: 1px solid rgba(168,85,247,0.35); }
    .council-scroll-window { max-height: 480px; overflow-y: auto; padding: 9px; background: #04070e; border: 1px solid rgba(255,255,255,0.07); border-radius: 8px; margin-bottom: 8px; }
    .chat-bubble-ai { border-radius: 8px; padding: 7px 10px; margin-bottom: 6px; font-size: 12px; background: rgba(255,255,255,0.04); border-left: 3px solid #38bdf8; }
    .chat-bubble-user { background: rgba(37,99,235,0.30); border-left: 4px solid #60a5fa; border-radius: 8px; padding: 8px 11px; margin: 8px 0 6px 0; font-size: 12.5px; }
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
                st.session_state["authenticated_user"] = None; st.query_params.clear(); st.error("💀 このアカウントまたは端末は永久BANされています。"); st.stop()
            if not u_rec or u_rec.get("status") != "approved":
                st.session_state["authenticated_user"] = None; st.query_params.clear(); st.error("🚫 アカウント一時停止中です。"); st.stop()
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
            spoof_cnt = len(sec.get("spoof_logs", []))
            if st.sidebar.button(f"👑 ガバナンス・管理画面 (承認待:{len(pend)} / 監視:{spoof_cnt})", use_container_width=True):
                st.session_state["navigation_page"] = "ADMIN"; st.rerun()
        return True

    st.markdown('<div class="glass-header" style="text-align:center;"><div class="brand-luxury">YAMASHISHI LAB</div><div class="brand-sub">QUANTUM WAVEFUNCTION & AGI SENTINEL GOVERNANCE TERMINAL</div></div>', unsafe_allow_html=True)
    render_biometric_bridge(mode="login")
    tab_login, tab_apply, tab_vault = st.tabs(["🔑 コードログイン", "📩 新規会員登録申請", "🔐 承認確認・暗号化コード照会"])
    with tab_login:
        with st.form("login"):
            ie = st.text_input("📧 登録メールアドレス")
            ic = st.text_input("🔑 専用アクセスコード", type="password")
            if st.form_submit_button("🔓 認証して量子ターミナルを起動", use_container_width=True):
                cm = ie.strip().lower(); rec = db.get(cm)
                is_ban, _ = check_and_log_ban_spoof(cm, (rec or {}).get("name", ""), cur_fp, raw_hfp, (rec or {}).get("pin_hash", ""), "コードログイン")
                if is_ban or (rec and rec.get("status") == "banned"): st.error("💀 このアカウントまたは端末は永久BANされています。")
                elif rec and rec.get("status") == "suspended": st.error("🚫 一時停止されています。")
                elif ((rec and rec.get("status") == "approved") or cm == ADMIN_EMAIL.strip().lower()) and (hmac.compare_digest(ic.strip().upper(), gen_code(cm)) or (cm == ADMIN_EMAIL.strip().lower() and ic.strip() == ADMIN_PASS)):
                    st.session_state["authenticated_user"] = cm; st.rerun()
                else: st.warning("⚠️ 未承認または専用アクセスコードが異なります。")
    with tab_apply:
        with st.form("apply"):
            an = st.text_input("👤 お名前")
            am = st.text_input("📧 メールアドレス")
            apin = st.text_input("🔢 秘密の4桁暗証番号 (PIN)", type="password", max_chars=4)
            if st.form_submit_button("📨 セキュア会員登録を申請する", use_container_width=True):
                if "@" not in am or len(apin.strip()) < 4: st.warning("⚠️ 入力内容を確認してください。")
                else:
                    cm, pc, ns = am.strip().lower(), gen_code(am), datetime.now().strftime("%Y-%m-%d %H:%M")
                    db[cm] = {"name": an.strip() or "未入力", "email": cm, "status": "pending", "passcode": pc, "pin_hash": hash_pin(apin), "applied_at": ns, "approved_at": "-", "last_seen_ts": 0, "last_seen_str": "-", "fp": cur_fp, "raw_hfp": raw_hfp, "bio_enabled": False}
                    save_j(FILES["mem"], db); st.success("✅ 申請を受け付けました！")
    with tab_vault:
        with st.form("vault_check"):
            chk_em = st.text_input("📧 申請したメールアドレス").strip().lower()
            chk_pin = st.text_input("🔢 4桁の暗証番号 (PIN)", type="password", max_chars=4).strip()
            if st.form_submit_button("🔍 照会", use_container_width=True):
                u_info = db.get(chk_em)
                if u_info and hmac.compare_digest(u_info.get("pin_hash", ""), hash_pin(chk_pin)) and u_info.get("status") == "approved":
                    st.success(f"🎉 承認済みです！専用コードは `{u_info.get('passcode')}` です。")
                else: st.error("❌ 一致する承認データがありません。")
    st.stop()

check_auth()

for k, v in [("active_debates", {}), ("council_threads", {}), ("council_meta", {}), ("watchlist", {}), ("navigation_page", "TOP"), ("active_category", "🏆 総合TOP5"), ("last_cat", "🏆 総合TOP5"), ("nav_history", []), ("scroll_top_trig", 0), ("selected_agent_detail", None)]:
    if k not in st.session_state: st.session_state[k] = v

with st.container():
    nav_c1, nav_c2, nav_c3 = st.columns([1, 1.35, 1])
    if nav_c1.button("⬆️ トップ", use_container_width=True):
        st.session_state["navigation_page"] = "TOP"; st.rerun()
    if nav_c2.button("✖ 合議閉じる", use_container_width=True):
        st.session_state["active_debates"] = {}; st.rerun()
    if nav_c3.button("🏛️ AGI監査・人事", use_container_width=True):
        st.session_state["navigation_page"] = "AGENTS_GOVERNANCE"; st.rerun()

# --- AGI監視官 (SENTINEL) 監査エンジン ---
def sentinel_audit_turn(speaker_key: str, text: str, user_q: str, web_snippets: list) -> dict:
    ag_db = load_agents_db()
    employed = ag_db.get("employed", {})
    if speaker_key not in employed: return {"penalized": False, "reason": "", "score_delta": 0}

    penalties = []
    delta = 0.0
    t_clean = text.strip()

    # 1. テンプレ定型文検知
    templates = ["〜についてだが", "私見を述べさせて", "以下のように考えられます", "ご質問ありがとうございます", "投資は自己責任です"]
    for tmp in templates:
        if tmp in t_clean:
            penalties.append(f"安易なテンプレ構文使用（「{tmp}」）")
            delta -= 12.0

    # 2. Web情報の引用・事実確認不備
    has_web_ref = any(s[:15] in t_clean for s in web_snippets) or ("Web" in t_clean) or ("報道" in t_clean) or ("動向" in t_clean)
    if not has_web_ref and web_snippets:
        penalties.append("リアルタイムWebファクトの引用無視")
        delta -= 8.5

    # 3. ユーザー質問との乖離
    if user_q.strip():
        q_words = [w for w in re.split(r"[\s　、。？！?]+", user_q) if len(w) >= 2]
        matched_words = [w for w in q_words if w in t_clean]
        if not matched_words and len(q_words) > 0:
            penalties.append(f"ユーザーの質問「{user_q}」に対する論点逸脱")
            delta -= 15.0

    # 4. 無気力・極小発言検知
    if len(t_clean) < 25:
        penalties.append("中身のない極小・無気力発言")
        delta -= 20.0

    target = employed[speaker_key]
    target["total_audits"] = target.get("total_audits", 0) + 1
    fired_event = False

    if delta < 0:
        target["penalties"] = target.get("penalties", 0) + 1
        target["trust_score"] = max(0.0, round(target.get("trust_score", 100.0) + delta, 1))
        target["last_audit"] = f"⚠️ 減点 {delta}pt: {' / '.join(penalties)}"
        
        # 解雇判定 (信頼スコア65点未満で即解雇)
        if target["trust_score"] < 65.0:
            fired_event = True
            target["status"] = "fired"
            fired_info = {
                **target,
                "fired_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "firing_cause": ' / '.join(penalties),
                "evidence_speech": text
            }
            ag_db["fired"][speaker_key] = fired_info
            del ag_db["employed"][speaker_key]
            
            # 監査ログ記録
            ag_db.setdefault("audit_logs", []).insert(0, {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "event": f"🚨 【即刻解雇処分】{speaker_key}",
                "detail": f"信頼度スコアが閾値割れ ({target['trust_score']}点)。証拠発言: 「{text[:60]}...」 事由: {' / '.join(penalties)}"
            })
    else:
        target["trust_score"] = min(100.0, round(target.get("trust_score", 100.0) + 0.5, 1))
        target["last_audit"] = "✅ SENTINEL品質基準クリア"

    save_agents_db(ag_db)
    return {"penalized": delta < 0, "reason": " / ".join(penalties), "delta": delta, "fired": fired_event}

# 銘柄データ・マクロ
STOCK_POOL = {
    "半導体": [{"code": "8035.T", "name": "東京エレクトロン", "theme": "前工程装置筆頭"}, {"code": "6857.T", "name": "アドバンテスト", "theme": "AI半導体テスタ首位"}, {"code": "NVDA", "name": "エヌビディア", "theme": "AI GPU覇者"}],
    "防衛・AI主力": [{"code": "7011.T", "name": "三菱重工業", "theme": "防衛・宇宙主力"}, {"code": "3778.T", "name": "さくらネット", "theme": "国策GPUクラウド"}, {"code": "PLTR", "name": "パランティア", "theme": "防衛AI"}],
    "次世代インフラ": [{"code": "5803.T", "name": "フジクラ", "theme": "DC光配線"}, {"code": "6501.T", "name": "日立製作所", "theme": "送配電グリッド"}, {"code": "IONQ", "name": "アイオンQ", "theme": "量子商用化"}]
}
KNOWN_STOCKS = {it["code"]: {"name": it["name"], "theme": it["theme"], "genre": g} for g, its in STOCK_POOL.items() for it in its}

def search_web_knowledge(query: str, max_results: int = 3) -> list:
    if not query.strip(): return []
    ctx = ssl.create_default_context()
    results = []
    try:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query.strip())}&hl=ja&gl=JP&ceid=JP:ja"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3.0, context=ctx) as r:
            root = ET.fromstring(r.read())
            for it in root.findall("./channel/item")[:max_results]:
                t = re.sub(r"<[^>]+>", "", it.findtext("title") or "").strip()
                d = re.sub(r"<[^>]+>", "", it.findtext("description") or "").strip()
                if t: results.append(f"【最新報道】{t} - {d[:80]}")
    except Exception: pass
    return results

def run_governed_council(r: dict, user_query: str = "") -> dict:
    ag_db = load_agents_db()
    employed = ag_db.get("employed", {})
    web_snippets = search_web_knowledge(f"{r['name']} 最新 株価 ニュース" if not user_query else user_query, max_results=3)
    web_txt = "\n".join(web_snippets) if web_snippets else f"・{r['name']}の市況推移"

    dialogue = []
    dialogue.append({"round": f"🏛️ AGI SENTINEL常時監視合議 ｜ 『{r['name']}』最新ファクト検証"})

    for spk_key, ag_info in list(employed.items()):
        # 個性に応じた発言生成
        first_fact = web_snippets[0] if web_snippets else f"{r['name']}の直近板情報"
        if spk_key == "QUANTUM":
            speech = f"量子波動干渉を観測した。Web最新動向（{first_fact[:65]}）が障壁エネルギーを突破させ、跳躍期待度{r.get('expect_pct', 88)}%のコヒーレンスを形成している。"
        elif spk_key == "AEGIS":
            speech = f"Web最新報道（{first_fact[:60]}）で沸いているが、CVaR防衛の観点から浮かれすぎは禁物だ。逆指値ラインを死守せよ。"
        elif spk_key == "IGNIS":
            speech = f"材料が出た初動でビビってちゃ勝機を逃すぜ！Webでも（{first_fact[:65]}）って話題沸騰だ、一気に突撃だ！"
        elif spk_key == "TECHNOS":
            speech = f"Webデータ（{first_fact[:65]}）とOFIを照合した。板の不均衡値は有意水準を満たしており、客観的なエントリー基準に合致する。"
        elif spk_key == "MICRO":
            speech = f"機関のKyleステルス吸収率を板から確認。Web速報（{first_fact[:65]}）を背景に大口が静かに買い集めている形跡がある。"
        else:
            speech = f"全官の意見を集約した。Webの最新材料（{first_fact[:65]}）を基軸に、リスクリワードを明確にして行動に移す。"

        # SENTINELリアルタイム監査
        audit_res = sentinel_audit_turn(spk_key, speech, user_query, web_snippets)
        status_tag = ""
        if audit_res.get("fired"):
            status_tag = " 🚨【即刻解雇処分】"
        elif audit_res.get("penalized"):
            status_tag = f" ⚠️【減点 {audit_res['delta']}pt】"

        dialogue.append({
            "speaker": f"{ag_info['display']}{status_tag}",
            "text": speech,
            "tone": "doubt" if audit_res.get("penalized") else "agree",
            "score": int(ag_info.get("trust_score", 90))
        })

    v_html = (
        f'<div style="margin-bottom:5px;"><b>🔥 AGI監査クリア・推奨執行プラン</b></div>'
        f'<div style="font-size:12px;color:#a7f3d0;">SENTINEL監視下で全現役エージェントが論理的妥当性を承認。</div>'
    )
    return {"dialogue": dialogue, "verdict_html": v_html}

def render_council_sec(r, uk):
    is_open = st.session_state["active_debates"].get(uk, False)
    if st.button("🔼 合議・SENTINEL監査を閉じる" if is_open else "⚛️ AGI監視合議を招集", key=f"b_{uk}", use_container_width=True):
        st.session_state["active_debates"][uk] = not is_open; st.rerun()
    if not is_open: return

    if uk not in st.session_state["council_threads"]:
        with st.spinner("🌐 AGI SENTINEL監査合議を起動中..."):
            deb = run_governed_council(r)
            st.session_state["council_threads"][uk] = deb["dialogue"]
            st.session_state["council_meta"][uk] = deb

    turns = st.session_state["council_threads"][uk]
    meta = st.session_state["council_meta"][uk]

    st.markdown('<div class="ai-council-box"><div class="council-scroll-window">' + "".join([
        f'<div class="chat-bubble-ai"><b style="color:#38bdf8;">{t["speaker"]}</b> ({t.get("score")}pt)<br>{t["text"]}</div>' if "round" not in t
        else f'<div style="text-align:center;padding:5px;background:rgba(168,85,247,0.2);color:#e9d5ff;font-weight:700;border-radius:5px;margin-bottom:6px;">{t["round"]}</div>'
        for t in turns
    ]) + '</div></div>', unsafe_allow_html=True)

    with st.form(f"f_{uk}", clear_on_submit=True):
        q = st.text_input("質問・追加指示投下", placeholder="例: 競合他社との最新比較は？")
        if st.form_submit_button("💬 質問をSENTINEL監視下で合議", use_container_width=True) and q.strip():
            st.session_state["council_threads"][uk].append({"speaker": "🗣️ あなたの質問", "text": q.strip(), "score": 100})
            with st.spinner("SENTINEL監査実行中..."):
                deb = run_governed_council(r, user_query=q.strip())
                st.session_state["council_threads"][uk].extend(deb["dialogue"])
                st.rerun()

    st.markdown(f'<div style="background:#0f172a;border:1px solid #10b981;border-radius:8px;padding:8px;margin-top:6px;">{meta["verdict_html"]}</div>', unsafe_allow_html=True)

def render_card(r, rank=None, kp="c"):
    st.markdown(
        f'<div class="rank-card">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<div><span class="pill-badge" style="background:#f59e0b;color:#000;">#{rank}</span><b style="font-size:16px;color:#f8fafc;">{r["name"]}</b> <span style="color:#94a3b8;font-size:12px;">({r["code"]})</span>'
        f'<div style="color:#cbd5e1;font-size:11px;margin-top:2px;">{r["theme"]} ｜ 現在値: <b style="color:#f8fafc;">{r["price"]}</b></div></div>'
        f'<div style="text-align:right;"><span style="font-size:10px;color:#fde047;">期待度</span><br><b style="font-size:16px;color:#fde047;">{r["expect_pct"]}%</b></div></div>'
        f'<div class="winrate-bar"><div><div style="font-size:9px;color:#94a3b8;">勝率</div><b>{r["win_rate"]}%</b></div><div><div style="font-size:9px;color:#94a3b8;">量子Q</div><b>{r["q_score"]}点</b></div><div><div style="font-size:9px;color:#94a3b8;">機関ミクロ</div><b>{r["ms_score"]}点</b></div><div><div style="font-size:9px;color:#94a3b8;">利確/損切</div><b>{r["tp_price"]}/{r["sl_price"]}</b></div></div>'
        f'</div>',
        unsafe_allow_html=True
    )
    render_council_sec(r, f"{kp}_{r['code']}")

# --- AGIガバナンス・人事・面接・投票管理画面 ---
if st.session_state.get("navigation_page") == "AGENTS_GOVERNANCE":
    st.subheader("🏛️ 自律型AGI監査・人事マネジメントセンター")
    st.markdown("自律監査官**SENTINEL**による常時品質チェック、エージェントの雇用・不名誉解雇リスト、次期候補者の面接オーディションおよび会員投票システムを統括します。")

    if st.button("⬅️ メイン画面へ戻る", use_container_width=True, type="primary"):
        st.session_state["navigation_page"] = "TOP"; st.rerun()

    ag_db = load_agents_db()
    g_tab1, g_tab2, g_tab3, g_tab4 = st.tabs(["👥 雇用中エージェント", "💀 解雇・不名誉リスト", "🗳️ 次期候補オーディション・会員投票", "📜 SENTINEL監査ログ"])

    with g_tab1:
        st.caption("現在合議に参加しているエージェントです。信頼度スコアが65点を下回ると即刻解雇処分となります。")
        for k, v in ag_db.get("employed", {}).items():
            st.markdown(
                f'<div class="rank-card" style="border-left-color:#10b981;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<div><b style="font-size:15px;color:#f8fafc;">{v["display"]}</b><br><span style="font-size:11.5px;color:#38bdf8;">専門分野: {v["specialty"]}</span></div>'
                f'<div style="text-align:right;"><span style="font-size:10px;color:#94a3b8;">信頼度スコア</span><br><b style="font-size:18px;color:#10b981;">{v["trust_score"]} pt</b></div></div>'
                f'<div style="background:rgba(255,255,255,0.03);border-radius:6px;padding:7px;margin-top:6px;font-size:11.5px;color:#cbd5e1;"><b>経歴:</b> {v["bio"]}</div>'
                f'<div style="font-size:10.5px;color:#94a3b8;margin-top:5px;">直近監査: {v.get("last_audit","なし")} ｜ 累積監査回数: {v.get("total_audits",0)}回 ｜ 減点回数: {v.get("penalties",0)}回</div>'
                f'</div>',
                unsafe_allow_html=True
            )

    with g_tab2:
        st.caption("SENTINELにより品質基準を満たさないと判定され、解雇されたAIの不名誉リストです。")
        fired = ag_db.get("fired", {})
        if not fired:
            st.info("現在、解雇処分を受けたエージェントはいません。厳格な規律が維持されています。")
        else:
            for k, v in fired.items():
                st.markdown(
                    f'<div class="rank-card" style="border-left-color:#ef4444;background:#1a0b0e!important;">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                    f'<div><span class="shame-badge">💀 DISMISSED (解雇済)</span> <b style="font-size:15px;color:#fca5a5;">{v["display"]}</b></div>'
                    f'<div style="font-size:11px;color:#94a3b8;">解雇日時: {v.get("fired_at")}</div></div>'
                    f'<div style="color:#f87171;font-size:12px;margin-top:6px;"><b>解雇事由:</b> {v.get("firing_cause")}</div>'
                    f'<div style="background:rgba(0,0,0,0.4);border-left:2px solid #ef4444;padding:6px;margin-top:5px;font-size:11.5px;color:#e2e8f0;"><b>処分証拠となった低品質発言:</b><br>「{v.get("evidence_speech")}」</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )

    with g_tab3:
        st.caption("解雇発生時や戦力補充の際に採用される候補者リストです。会員は1人1票を投じることができ、投票結果は管理者の採用決定に反映されます。")
        cu = st.session_state.get("authenticated_user", "")
        for k, cand in ag_db.get("candidates", {}).items():
            has_voted = cu in cand.get("voters", [])
            st.markdown(
                f'<div class="rank-card" style="border-left-color:#f59e0b;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<div><b style="font-size:15px;color:#fde047;">{cand["display"]}</b><br><span style="font-size:11.5px;color:#cbd5e1;">専門: {cand["specialty"]}</span></div>'
                f'<div style="text-align:right;"><span style="font-size:10px;color:#fde047;">獲得投票数</span><br><b style="font-size:18px;color:#fde047;">{cand.get("votes",0)} 票</b></div></div>'
                f'<div style="background:rgba(245,158,11,0.06);border-left:3px solid #f59e0b;padding:7px;margin-top:6px;font-size:12px;color:#f8fafc;"><b>🎙️ 面接ピッチ (志望動機・能力):</b><br>{cand["interview_pitch"]}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
            col_v1, col_v2 = st.columns([3, 1])
            if has_voted:
                col_v1.success("✅ あなたはこの候補者に投票済みです。")
                if col_v2.button("取消", key=f"unvote_{k}", use_container_width=True):
                    cand["votes"] = max(0, cand.get("votes", 1) - 1)
                    cand["voters"].remove(cu)
                    save_agents_db(ag_db); st.rerun()
            else:
                if col_v1.button(f"🗳️ {cand['name']} に1票を投じる", key=f"vote_{k}", use_container_width=True):
                    cand["votes"] = cand.get("votes", 0) + 1
                    cand.setdefault("voters", []).append(cu)
                    save_agents_db(ag_db); st.rerun()

    with g_tab4:
        st.caption("SENTINELによるリアルタイム監査・処分履歴です。")
        logs = ag_db.get("audit_logs", [])
        if not logs: st.info("監査ログはまだありません。")
        else:
            for l in logs[:30]:
                st.markdown(f'<div style="background:#0f172a;border-left:3px solid #38bdf8;padding:6px 9px;margin-bottom:5px;font-size:11.5px;"><div style="display:flex;justify-content:space-between;color:#94a3b8;"><b>{l["event"]}</b><span>{l["time"]}</span></div><div style="color:#e2e8f0;margin-top:2px;">{l["detail"]}</div></div>', unsafe_allow_html=True)

    st.stop()

# --- 管理者専用画面 (会員管理＆本採用決定) ---
if st.session_state.get("navigation_page") == "ADMIN" and st.session_state.get("authenticated_user") == ADMIN_EMAIL.strip().lower():
    st.subheader("👑 ガバナンス最高管理センター")
    if st.button("⬅️ TOPへ戻る", use_container_width=True):
        st.session_state["navigation_page"] = "TOP"; st.rerun()

    adm_t1, adm_t2 = st.tabs(["👥 会員認証管理", "🏛️ AGIオーディション本採用決定"])
    with adm_t1:
        db = load_mem()
        for k, v in list(db.items()):
            if k == ADMIN_EMAIL.strip().lower(): continue
            c_a, c_b = st.columns([3, 1])
            c_a.markdown(f"**{v.get('name')}** (`{k}`) ｜ 状態: `{v.get('status')}` ｜ コード: `{v.get('passcode')}`")
            if c_b.button("承認 / 復帰", key=f"adm_ap_{k}"):
                db[k]["status"] = "approved"; save_j(FILES["mem"], db); st.rerun()

    with adm_t2:
        st.caption("会員の投票結果をもとに、次期エージェントを本採用して合議へ即時投入できます。")
        ag_db = load_agents_db()
        for ck, cv in list(ag_db.get("candidates", {}).items()):
            st.markdown(f"**{cv['display']}** (獲得票: **{cv.get('votes', 0)}票**) - {cv['specialty']}")
            if st.button(f"👑 【本採用決定】{cv['name']} を合議メンバーに即時雇用", key=f"hire_{ck}", use_container_width=True):
                new_employed = {
                    "name": cv["name"], "display": cv["display"], "specialty": cv["specialty"],
                    "bio": f"オーディションにて会員投票 {cv.get('votes', 0)}票 を獲得し管理者承認により本採用。",
                    "trust_score": cv.get("trust_score", 95.0), "status": "active",
                    "total_audits": 0, "penalties": 0, "last_audit": "本採用配属完了"
                }
                ag_db["employed"][ck] = new_employed
                del ag_db["candidates"][ck]
                ag_db.setdefault("audit_logs", []).insert(0, {
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "event": f"🎉 【本採用決定】{ck}",
                    "detail": f"管理者が会員投票({cv.get('votes', 0)}票)を受け本採用を承認。直ちに合議に配属。"
                })
                save_agents_db(ag_db); st.success(f"✅ {cv['name']} を本採用しました！"); st.rerun()
    st.stop()

# --- メインダッシュボード ---
st.markdown(
    '<div class="sentinel-box">'
    '<div style="display:flex;justify-content:space-between;align-items:center;">'
    '<span>🛡️ <b>自律型AGI監査官「SENTINEL」稼働中</b> ｜ 合議の品質・Web引用・論理整合性をリアルタイム監査</span>'
    '<span class="quantum-badge">審査基準: 厳格</span></div></div>',
    unsafe_allow_html=True
)

st.markdown('<div class="glass-header"><div class="brand-luxury">YAMASHISHI QUANTUM TERMINAL</div><div class="brand-sub">QUANTUM WAVE & AGI GOVERNED MULTI-AGENT SYSTEM</div></div>', unsafe_allow_html=True)

# 模擬データ表示
SAMPLE_DATA = [
    {"code": "6857.T", "name": "アドバンテスト", "theme": "AI半導体テスター首位", "price": "7,820円", "expect_pct": 94.2, "win_rate": 81.5, "q_score": 92, "ms_score": 90, "tp_price": "8,250円", "sl_price": "7,600円"},
    {"code": "7011.T", "name": "三菱重工業", "theme": "防衛・宇宙主力国策", "price": "2,340円", "expect_pct": 91.8, "win_rate": 78.0, "q_score": 89, "ms_score": 93, "tp_price": "2,520円", "sl_price": "2,260円"},
    {"code": "5803.T", "name": "フジクラ", "theme": "AIデータセンター光配線", "price": "6,150円", "expect_pct": 89.5, "win_rate": 75.4, "q_score": 88, "ms_score": 87, "tp_price": "6,580円", "sl_price": "5,950円"}
]

for idx, item in enumerate(SAMPLE_DATA, 1):
    render_card(item, rank=idx, kp="main")
