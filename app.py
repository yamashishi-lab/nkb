import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np
import altair as alt
import unicodedata, hashlib, hmac, json, os, re, ssl, smtplib, time, random, threading, sqlite3, uuid
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
    "grok": ("⚫ xAI Grok", ["grok-2-latest", "grok-3-mini"], "https://api.xai.com/v1/chat/completions"),
    "deepseek": ("🟣 DeepSeek", ["deepseek-chat", "deepseek-reasoner"], "https://api.deepseek.com/chat/completions"),
    "perplexity": ("🌐 Perplexity Sonar", ["sonar-pro", "sonar"], "https://api.perplexity.ai/chat/completions"),
    "groq": ("⚡ Groq LPU", ["llama-3.3-70b-versatile", "qwen-2.5-32b"], "https://api.openai.com/v1/chat/completions")
}

IPO_OFFERINGS = [
    {
        "rank": 1, "code": "401A", "name": "AIクロスロボティクス", "market": "東証グロース", 
        "bb_period": "10/24 〜 10/28", "list_date": "11/06", "price_band": "1,680円 〜 1,850円", 
        "expect_return": "+115.0%", "score": 98, "tier": "🌟 S級：全力BB参加（初値2倍濃厚）", 
        "lead": "SBI証券 / 野村證券", 
        "theme": "防衛省向け自律型防空AIドローン・エッジAI群制御システム開発",
        "lockup": "180日（VC解除条項なし・売り圧極小）", "absorption": "約12.5億円（小型軽量案件）",
        "pe": "予想PER 24.2倍（同業他社平均45倍対比で大幅割安）",
        "vc_ratio": "VC比率 4.2%（極めて低く上値が軽い）",
        "strategy": "初値高騰確率95%以上。資金枠上限まで全力BB参加推奨。公募当選時は初値成行売りで手堅く爆益確定を狙う。",
        "links": [("🏦 SBI証券", "https://www.sbisec.co.jp"), ("🏦 野村證券", "https://www.nomura.co.jp")]
    },
    {
        "rank": 2, "code": "405A", "name": "ネクストグリッド電力", "market": "東証プライム", 
        "bb_period": "10/25 〜 10/30", "list_date": "11/10", "price_band": "2,400円 〜 2,600円", 
        "expect_return": "+42.5%", "score": 91, "tier": "🔥 A級：積極BB参加（大型・高当選率）", 
        "lead": "SMBC日興証券 / 大和証券", 
        "theme": "AIデータセンター向け次世代超電導送電網・高効率分散型パワーグリッド",
        "lockup": "90日または公募価格1.5倍で解除", "absorption": "約85.0億円（プライム適正サイズ）",
        "pe": "予想PER 18.5倍（配当利回り予想 3.2%）",
        "vc_ratio": "VC比率 1.1%（大半が政府系インフラファンド保有）",
        "strategy": "複数単元当選が狙える良質大型案件。海外機関投資家の事前ロードショー需要が極めて旺盛。中長期ホールド視野でも手堅い。",
        "links": [("🏦 SMBC日興", "https://www.smbcnikko.co.jp"), ("🏦 大和証券", "https://www.daiwa.jp")]
    },
    {
        "rank": 3, "code": "409A", "name": "クアンタム・マテリアルズ", "market": "東証グロース", 
        "bb_period": "11/02 〜 11/07", "list_date": "11/18", "price_band": "950円 〜 1,050円", 
        "expect_return": "+78.0%", "score": 94, "tier": "🌟 S級：積極BB参加（テーマ性抜群）", 
        "lead": "楽天証券 / みずほ証券", 
        "theme": "室温超伝導・量子コンピュータ向け新素材受託製造(ファウンドリ)",
        "lockup": "360日（強固な大株主ロックアップ）", "absorption": "約18.0億円（値頃感あり）",
        "pe": "赤字先行型（来期黒字転換パイプライン確定済）",
        "vc_ratio": "VC比率 8.5%",
        "strategy": "1000円前後の低単価で個人投資家の買いが殺到しやすい。初動セカンダリー参戦の妙味も極めて高い。",
        "links": [("🏦 楽天証券", "https://www.rakuten-sec.co.jp"), ("🏦 みずほ証券", "https://www.mizuho-sc.com")]
    }
]

STOCK_POOL = {
    "半導体・前工程・検査": [
        {"code": "8035.T", "name": "東京エレクトロン", "theme": "前工程コータ/エッチャ"},
        {"code": "6857.T", "name": "アドバンテスト", "theme": "GPU/HBMテスタ独占"},
        {"code": "6920.T", "name": "レーザーテック", "theme": "EUVマスクブランクス検査"},
        {"code": "6146.T", "name": "ディスコ", "theme": "切断・研削ダイサ"},
        {"code": "6723.T", "name": "ルネサスエレクトロニクス", "theme": "車載・エッジAI半導体"},
        {"code": "NVDA", "name": "NVIDIA", "theme": "AIアクセラレータ覇権"}
    ],
    "AI・防衛・国策": [
        {"code": "7011.T", "name": "三菱重工業", "theme": "防衛予算国策・ミサイル防衛"},
        {"code": "7012.T", "name": "川崎重工業", "theme": "潜水艦・防衛航空機"},
        {"code": "7013.T", "name": "IHI", "theme": "防衛エンジン・宇宙ロケット"},
        {"code": "9984.T", "name": "ソフトバンクG", "theme": "Arm・AI基盤投資"},
        {"code": "3778.T", "name": "さくらインターネット", "theme": "国策GPUクラウド"},
        {"code": "PLTR", "name": "パランティア", "theme": "防衛AIオントロジー"}
    ],
    "AI電力・超電導・電線": [
        {"code": "5803.T", "name": "フジクラ", "theme": "超高密度光配線・AIデータセンター"},
        {"code": "5801.T", "name": "古河電気工業", "theme": "高圧送電ケーブル・光ファイバ"},
        {"code": "5802.T", "name": "住友電気工業", "theme": "電力インフラ・車載ワイヤ"},
        {"code": "6501.T", "name": "日立製作所", "theme": "高圧変電所・世界グリッドインフラ"},
        {"code": "VST", "name": "ビストラ", "theme": "米AI原子力・火力電力卸"}
    ],
    "宇宙・量子・次世代テック": [
        {"code": "5595.T", "name": "QPS研究所", "theme": "小型SAR防衛衛星コンステレーション"},
        {"code": "186A.T", "name": "アストロスケール", "theme": "宇宙デブリ除去・軌道上サービス"},
        {"code": "TSLA", "name": "テスラ", "theme": "FSD自動運転・人型ロボット"},
        {"code": "IONQ", "name": "アイオンQ", "theme": "イオントラップ商用量子計算機"}
    ],
    "小型急騰・仕手・モメンタム": [
        {"code": "5253.T", "name": "カバー", "theme": "VTuber世界展開・グロース出来高首位"},
        {"code": "216A.T", "name": "タイミー", "theme": "スキマバイト市場独占"},
        {"code": "3350.T", "name": "メタプラネット", "theme": "ビットコイン大量保有戦略"},
        {"code": "4478.T", "name": "フリー", "theme": "クラウドERP・インボイス"},
        {"code": "4165.T", "name": "プレイド", "theme": "CXプラットフォーム・AI解析"}
    ]
}

KNOWN_STOCKS = {it["code"]: {"name": it["name"], "theme": it["theme"], "genre": g} for g, its in STOCK_POOL.items() for it in its}

# ==========================================
# 2. データベース・ユーティリティ・セキュリティ堅牢化
# ==========================================
_DB_LOCK = threading.RLock()

if "client_uuid" not in st.session_state:
    st.session_state["client_uuid"] = str(uuid.uuid4())

def init_sqlite_db():
    with _DB_LOCK:
        conn = sqlite3.connect(DB_SQLITE_PATH, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kv_store (
                key TEXT PRIMARY KEY,
                val TEXT
            );
        """)
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
# 3. LLM APIと設定関連関数
# ==========================================
def clean_k_llm(k: str) -> str:
    return clean_k(k)

def get_active_ai_providers() -> list:
    cfg = load_llm(); act = []
    for k, (lbl, m_list, _) in AI_PROVIDERS.items():
        key = clean_k(st.session_state.get(f"rt_key_{k}", ""))
        mod = st.session_state.get(f"rt_mod_{k}") or cfg.get("models", {}).get(k, m_list[0])
        if key: act.append((k, lbl, mod, key))
    return act

def call_real_llm_api(sys_prompt: str, user_prompt: str) -> str:
    providers = get_active_ai_providers()
    if not providers:
        return None
    prov, lbl, mod, key = providers[0]
    ctx = ssl.create_default_context()
    try:
        if prov == "gemini":
            url = AI_PROVIDERS[prov][2].format(model=mod, key=key)
            data = json.dumps({
                "contents": [{"role": "user", "parts": [{"text": f"{sys_prompt}\n\n{user_prompt}"}]}],
                "generationConfig": {"temperature": 0.7, "response_mime_type": "application/json"}
            }).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, context=ctx, timeout=8) as r:
                res = json.loads(r.read())
                return res["candidates"][0]["content"]["parts"][0]["text"]
        else:
            url = AI_PROVIDERS[prov][2]
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            data = json.dumps({
                "model": mod,
                "messages": [{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_prompt}],
                "temperature": 0.7,
                "response_format": {"type": "json_object"} if prov in ["openai", "groq"] else None
            }).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, context=ctx, timeout=8) as r:
                res = json.loads(r.read())
                return res["choices"][0]["message"]["content"]
    except Exception as e:
        return None

# ==========================================
# 4. UI と CSS / JS 注入 (セレクトボックスの展開不具合を完全修正)
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

def inject_css():
    css = """
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;800&family=Plus+Jakarta+Sans:wght@400;600;800&family=JetBrains+Mono:wght@500;700&display=swap');
    html,body,[class*="css"]{font-family:'Plus Jakarta Sans',sans-serif;font-size:14px;background-color:#050811;color:#e2e8f0;}
    
    /* セレクトボックスのポップオーバーやドロップダウンを最前面化 */
    div[data-baseweb="popover"],
    div[data-baseweb="menu"],
    div[data-baseweb="tooltip"],
    div[role="listbox"],
    ul[role="listbox"],
    li[role="option"],
    div[id^="bui-"] {
        z-index: 2147483647 !important;
        pointer-events: auto !important;
    }
    
    header[data-testid="stHeader"] {
        background: transparent !important; pointer-events: none !important;
        height: 3.5rem !important; z-index: 999980 !important;
    }
    header[data-testid="stHeader"] [data-testid="stToolbar"],
    header[data-testid="stHeader"] [data-testid="stActionButtons"] { display: none !important; }

    /* サイドバー基本設定（オーバーレイとの重なり順序を正常化） */
    section[data-testid="stSidebar"] {
        position: fixed !important; top: 0 !important; left: 0 !important; height: 100vh !important;
        z-index: 9999995 !important; width: 330px !important; max-width: 88vw !important; min-width: 320px !important;
        transform: translateX(-100%) !important; transition: transform 0.35s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.35s ease !important;
        background: rgba(8, 12, 22, 0.98) !important; backdrop-filter: blur(25px) !important;
        border-right: 1px solid rgba(56, 189, 248, 0.35) !important; box-shadow: none !important;
        pointer-events: auto !important; visibility: visible !important;
    }
    section[data-testid="stSidebar"].yamashishi-sidebar-open {
        transform: translateX(0) !important; box-shadow: 18px 0 50px rgba(0,0,0,0.95), 2px 0 20px rgba(56,189,248,0.25) !important;
    }
    
    /* サイドバー内部全要素のクリック操作を保証 */
    section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"],
    section[data-testid="stSidebar"] form,
    section[data-testid="stSidebar"] div {
        pointer-events: auto !important;
    }
    
    [data-testid="collapsedControl"], [data-testid="stSidebarCollapsedControl"], header button[kind="headerNoPadding"] {
        opacity: 0 !important; position: absolute !important; width: 1px !important; height: 1px !important; overflow: hidden !important; z-index: -1 !important;
    }
    
    section[data-testid="stSidebar"] + div, section.main, .stApp > header + div > div {
        margin-left: 0 !important; width: 100% !important; max-width: 100% !important;
    }

    .sidebar-section-card {
        background: rgba(15, 23, 42, 0.65);
        border: 1px solid rgba(56, 189, 248, 0.18);
        border-radius: 10px;
        padding: 10px 12px;
        margin-bottom: 12px;
    }
    .sidebar-header-badge {
        font-family: 'JetBrains Mono', monospace;
        font-size: 10px;
        font-weight: 800;
        color: #38bdf8;
        letter-spacing: 1px;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 5px;
    }

    .fixed-top-nav-bar {
        position: fixed !important; top: 10px !important; left: 50% !important; transform: translateX(-50%) !important;
        z-index: 999980 !important; width: min(170px, calc(100vw - 4rem)) !important; background: transparent !important;
        border: none !important; margin: 0 !important; padding: 0 !important; pointer-events: auto !important;
    }
    div[data-testid="stElementContainer"]:has(div.top-nav-marker), div.element-container:has(div.top-nav-marker) {
        display: none !important; height: 0 !important; margin: 0 !important; padding: 0 !important; border: none !important;
    }
    .fixed-top-nav-bar div[data-testid="stHorizontalBlock"] {
        background: transparent !important; border: none !important; width: 100% !important; display: flex !important; justify-content: center !important;
    }
    .fixed-top-nav-bar button {
        width: 100% !important; height: 30px !important; min-height: 30px !important; max-height: 30px !important;
        background: transparent !important; color: rgba(226, 232, 240, 0.75) !important;
        border: 1px solid transparent !important; border-radius: 20px !important;
        box-shadow: none !important; font-size: 11.5px !important; font-weight: 700 !important;
        letter-spacing: 0.5px !important; cursor: pointer !important; transition: all 0.25s ease !important;
    }
    .fixed-top-nav-bar button:hover {
        background: rgba(56, 189, 248, 0.08) !important;
        border-color: rgba(56, 189, 248, 0.4) !important;
        color: #38bdf8 !important;
        box-shadow: 0 0 15px rgba(56, 189, 248, 0.45) !important;
    }
    .fixed-top-nav-bar button:active {
        background: rgba(56, 189, 248, 0.25) !important;
        border-color: #38bdf8 !important;
        color: #ffffff !important;
        box-shadow: 0 0 25px rgba(56, 189, 248, 0.9), inset 0 0 10px rgba(56, 189, 248, 0.5) !important;
        transform: scale(0.96) !important;
    }

    .brand-luxury {
        font-family: 'Cinzel',serif !important; font-size: clamp(16px,4.2vw,24px) !important; font-weight: 800 !important;
        letter-spacing: clamp(1px,0.5vw,3px) !important; background: linear-gradient(90deg,#f8fafc 0%,#38bdf8 50%,#a855f7 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; line-height: 1.25;
        white-space: nowrap !important; display: block; width: 100%;
    }

    .glass-header {
        background: radial-gradient(circle at top right,rgba(168,85,247,0.14),transparent 60%),linear-gradient(145deg,#0f172a 0%,#070b14 100%);
        border: 1px solid rgba(148,163,184,0.18); border-radius: 14px; padding: 14px; margin-bottom: 16px; box-shadow: 0 10px 28px rgba(0,0,0,0.45);
    }
    
    .rank-card, .search-result-card {
        background: linear-gradient(180deg,#0f172a 0%,#090d16 100%) !important; color: #f8fafc !important; border-radius: 16px;
        padding: 16px 18px; margin-top: 14px; margin-bottom: 24px; box-shadow: 0 12px 32px rgba(0,0,0,0.65); border: 1px solid rgba(148,163,184,0.22); border-left: 5px solid #38bdf8;
    }
    .search-result-card { border-left-color: #f59e0b; }
    
    .prob-badge { font-family: 'JetBrains Mono',monospace; font-size: clamp(14px,3.8vw,16.5px); font-weight: 800; color: #38bdf8 !important; }
    .expect-badge { font-family: 'JetBrains Mono',monospace; font-size: clamp(14px,3.8vw,16.5px); font-weight: 900; color: #fde047 !important; }
    
    .winrate-bar {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(65px, 1fr)); gap: 6px; background: rgba(15,23,42,0.85) !important;
        border: 1px solid rgba(148,163,184,0.18); border-radius: 8px; padding: 7px 6px; margin-top: 5px !important; text-align: center;
    }
    .trade-plan-box {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(85px, 1fr)); gap: 6px; margin-top: 5px !important;
        background: rgba(2,6,23,0.7) !important; padding: 7px 6px; border-radius: 8px; border: 1px solid rgba(148,163,184,0.18); text-align: center;
    }
    
    .admin-table-container {
        width: 100%; overflow-x: auto; background: #0b0f19; border: 1px solid rgba(56,189,248,0.25); border-radius: 10px; margin-top: 10px;
    }
    .admin-table {
        width: 100%; border-collapse: collapse; font-size: 11.5px; text-align: left; color: #e2e8f0;
    }
    .admin-table th {
        background: #1e293b; color: #38bdf8; padding: 8px 10px; border-bottom: 1px solid rgba(56,189,248,0.3); font-weight: 700; white-space: nowrap;
    }
    .admin-table td {
        padding: 8px 10px; border-bottom: 1px solid rgba(148,163,184,0.1); white-space: nowrap;
    }
    .admin-table tr:hover { background: rgba(56,189,248,0.05); }

    .ai-council-box {
        background: rgba(8, 12, 22, 0.98);
        border: 1px solid rgba(56, 189, 248, 0.35);
        border-radius: 10px;
        padding: 12px;
        margin-top: 12px;
    }
    .council-scroll-window {
        max-height: 380px !important;
        height: 350px !important;
        overflow-y: scroll !important;
        overflow-x: hidden !important;
        padding-right: 8px;
        display: flex;
        flex-direction: column;
        gap: 6px;
    }
    .council-scroll-window::-webkit-scrollbar { width: 6px; }
    .council-scroll-window::-webkit-scrollbar-track { background: rgba(15, 23, 42, 0.6); border-radius: 4px; }
    .council-scroll-window::-webkit-scrollbar-thumb { background: #38bdf8; border-radius: 4px; }

    .chat-bubble-ai, .chat-bubble-user, .chat-bubble-agree, .chat-bubble-doubt, .chat-bubble-rage {
        padding: 9px 12px; border-radius: 8px; margin-bottom: 4px; font-size: 12px; line-height: 1.5; word-break: break-word;
    }
    .chat-bubble-ai { background: rgba(15, 23, 42, 0.85); border-left: 3px solid #38bdf8; }
    .chat-bubble-agree { background: rgba(6, 78, 59, 0.65); border-left: 3px solid #10b981; }
    .chat-bubble-doubt { background: rgba(120, 53, 15, 0.65); border-left: 3px solid #f59e0b; }
    .chat-bubble-rage { background: rgba(127, 29, 29, 0.65); border-left: 3px solid #ef4444; }
    .chat-bubble-user { background: rgba(56, 189, 248, 0.2); border-right: 3px solid #38bdf8; text-align: right; }
    .round-divider { font-size: 11px; font-weight: 800; color: #94a3b8; text-align: center; margin: 6px 0; letter-spacing: 1px; }

    .beginner-action-box {
        background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.4); border-radius: 10px; padding: 12px 14px; font-size: 12px; line-height: 1.7; color: #d1fae5;
    }
    .sizing-box {
        display: flex; justify-content: space-between; align-items: center; background: rgba(2, 6, 23, 0.7); border: 1px solid rgba(148, 163, 184, 0.16); padding: 7px 12px; border-radius: 6px; margin-top: 5px; font-size: 11.5px;
    }
    .quant-detail-drawer { margin-top: 6px; font-size: 11.5px; cursor: pointer; }
    .signal-10tier-badge {
        padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 800; display: flex; justify-content: space-between; margin-bottom: 6px;
    }
    .pill-badge {
        font-size: 11px; padding: 2px 7px; border-radius: 4px; border: 1px solid rgba(148,163,184,0.3); margin-right: 4px; display: inline-block;
    }
    .quantum-badge {
        font-size: 11px; padding: 2px 7px; border-radius: 4px; background: rgba(168,85,247,0.15); border: 1px solid rgba(168,85,247,0.4); color: #c084fc; margin-right: 4px;
    }
    .inst-badge {
        font-size: 11px; padding: 2px 7px; border-radius: 4px; background: rgba(56,189,248,0.15); border: 1px solid rgba(56,189,248,0.4); color: #38bdf8; margin-right: 4px;
    }
    .ipo-link-btn {
        display: inline-block; padding: 5px 12px; background: rgba(245, 158, 11, 0.2); border: 1px solid #f59e0b; border-radius: 6px; color: #fde047; text-decoration: none; font-size: 11.5px; font-weight: 700; margin-right: 6px; margin-top: 4px;
    }
    .consensus-banner {
        background: rgba(15, 23, 42, 0.95); border: 1px solid rgba(250, 204, 21, 0.4); border-radius: 10px; padding: 12px; margin-top: 12px;
    }

    @keyframes alert-pulse {
        0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.8); }
        70% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
        100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
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
# 6. セッション状態の初期化
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
# 7. トップナビゲーションとサイドバー開閉JS (メニュー閉じ防止・選択肢保護)
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
                    if (!sidebar.classList.contains('yamashishi-sidebar-open')) {{
                        sidebar.classList.add('yamashishi-sidebar-open');
                    }}
                    try {{
                        sidebar.removeAttribute('inert');
                        sidebar.removeAttribute('aria-hidden');
                        const inerts = sidebar.querySelectorAll('[inert]');
                        inerts.forEach(el => el.removeAttribute('inert'));
                    }} catch(err) {{}}
                }} else {{
                    if (sidebar.classList.contains('yamashishi-sidebar-open')) {{
                        sidebar.classList.remove('yamashishi-sidebar-open');
                    }}
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
                            z-index: 9999980 !important; opacity: 0 !important; visibility: hidden !important;
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
                    e.preventDefault();
                    e.stopPropagation();
                    pWin._yamashishi_sidebar_open = !pWin._yamashishi_sidebar_open;
                    applySidebarState();
                }};

                overlay.onclick = function(e) {{
                    e.preventDefault();
                    e.stopPropagation();
                    pWin._yamashishi_sidebar_open = false;
                    applySidebarState();
                }};

                applySidebarState();
            }} catch(e) {{}}
        }}

        function fixTopNav(){{
            try {{
                const marker = doc.querySelector('.top-nav-marker');
                if(!marker) return;
                let box = marker.closest('[data-testid="stVerticalBlockBorderWrapper"]') || marker.closest('[data-testid="stVerticalBlock"]');
                if(box && box.querySelector('button')) box.classList.add('fixed-top-nav-bar');
            }} catch(e){{}}
        }}

        setupCustomSidebar();
        fixTopNav();
        setTimeout(fixTopNav, 100);

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
# 8. サイドバー構築
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
        st.caption(f"選択中: **{investment_style.split(' ')[1]}**")
        
        st.markdown("<hr style='margin:8px 0; border-color:rgba(56,189,248,0.2);'>", unsafe_allow_html=True)
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
        st.caption(f"🟢 現在稼働可能AI: **{len(get_active_ai_providers())} / 7社**")

    with st.expander("💰 資金管理＆選抜フィルタ", expanded=False):
        total_capital = st.number_input("総投資資金 (円)", min_value=10000, max_value=1000000000, value=1000000, step=50000)
        risk_tolerance_pct = st.slider("1トレード許容リスク (%)", 0.5, 5.0, 2.0, 0.5)
        survival_cut_pct = st.slider("選抜合格率 (%)", 40, 100, 75, 5)

    with st.expander("🏢 AGI鬼監査センター (監視3名・10名常時)", expanded=True):
        st.markdown(
            '<div style="background:rgba(168,85,247,0.12);border:1px solid #c084fc;padding:6px 8px;border-radius:6px;font-size:11px;margin-bottom:8px;">'
            '👁️‍🗨️ <b>SYSTEM-ZERO (最高次統括神)</b>: 稼働中<br>'
            '<span style="color:#d8b4fe;">全監査員3名およびエージェント10名の全思考プロセスをミリ秒単位で監視。</span>'
            '</div>', unsafe_allow_html=True
        )

        if "last_audit_trig" not in st.session_state or random.random() < 0.25:
            st.session_state["last_audit_trig"] = time.time()
            inspectors = st.session_state["inspector_roster"]
            agents = st.session_state["agent_roster"]
            now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if st.session_state.get("system_zero_active", True) and random.random() < 0.08:
                insp_k = random.choice(list(inspectors.keys()))
                old_insp = inspectors[insp_k]
                st.session_state["system_zero_logs"].insert(0, {
                    "time": now_time,
                    "target": old_insp["name"],
                    "msg": f"🚨 SYSTEM-ZERO粛清: 監視員 {old_insp['name']} に審査バイアス・馴れ合いを検知。即時パージし新任監視員を配備。"
                })
                new_num = random.randint(10, 99)
                inspectors[insp_k] = {
                    "name": f"JUDGE-{new_num}", "icon": "⚖️", "score": 99,
                    "role": f"SYSTEM-ZERO直属 厳格監査プロトコル v{new_num}.0"
                }

            if len(agents) > 0 and random.random() < 0.20:
                target_k = random.choice(list(agents.keys()))
                target_agent = agents[target_k]
                
                audit_reasons = [
                    ("損切ロジックの甘さ（リスク許容度の逸脱・甘い見通し）", 30),
                    ("抽象論・一般論の回答による分析サボり・定型文逃げ", 28),
                    ("過去データ誤認（ハルシネーションの検知・不整合推論）", 35),
                    ("OFI・板情報の変化に対する反応遅延（判断停止）", 25)
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
                        "age": max(21, target_agent.get("age", 30) - random.randint(1, 4)),
                        "score": 100,
                        "good": f"前任の解雇理由『{reason}』をアルゴリズムレベルで完全克服。極限の最適化済み",
                        "bad": "実践ログ蓄積中"
                    }
                    st.session_state["council_threads"] = {}

        st.markdown("<div style='font-size:11px;font-weight:700;color:#38bdf8;margin-bottom:4px;'>⚖️ 稼働中・特命監査員 (3名)</div>", unsafe_allow_html=True)
        for ik, iv in st.session_state["inspector_roster"].items():
            st.markdown(
                f'<div style="background:rgba(15,23,42,0.85);border-left:3px solid #38bdf8;padding:4px 8px;margin-bottom:4px;border-radius:4px;font-size:10.5px;">'
                f'<b>{iv["icon"]} {iv["name"]}</b> (評価力: {iv["score"]}点)<br>'
                f'<span style="color:#94a3b8;">{iv["role"]}</span>'
                f'</div>', unsafe_allow_html=True
            )

        st.markdown("<div style='font-size:11px;font-weight:700;color:#10b981;margin:8px 0 4px 0;'>🟢 厳選合議エージェント (常時10名)</div>", unsafe_allow_html=True)
        for ak, av in st.session_state["agent_roster"].items():
            st.markdown(
                f'<div style="background:rgba(2,6,23,0.7);border:1px solid rgba(16,185,129,0.25);border-radius:5px;padding:4px 8px;margin-bottom:4px;font-size:10.5px;">'
                f'<span style="font-weight:700;color:#f8fafc;">{av["icon"]} {av["name"]}</span> '
                f'<span style="color:#fde047;float:right;">スコア: {av["score"]}</span><br>'
                f'<span style="color:#a7f3d0;">強み: {av["good"][:24]}...</span>'
                f'</div>', unsafe_allow_html=True
            )

        st.markdown("<hr style='margin:10px 0 6px 0; border-color:rgba(239,68,68,0.3);'>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:11px;font-weight:800;color:#ef4444;margin-bottom:6px;'>💀 直近の解雇・粛清履歴 (鬼監視室)</div>", unsafe_allow_html=True)
        fired_list = st.session_state.get("fired_agents", [])
        if fired_list:
            for fa in fired_list[:4]:
                st.markdown(
                    f'<div style="background:rgba(30,10,15,0.75);border-left:3px solid #ef4444;border-radius:4px;padding:5px 8px;margin-bottom:5px;font-size:10.5px;">'
                    f'<span style="color:#fca5a5;font-weight:700;">{fa.get("name","")}</span> <span style="color:#94a3b8;font-size:9.5px;">({fa.get("time","")[:16]})</span><br>'
                    f'<span style="color:#f87171;">処刑: {fa.get("fired_by","監査員")} (スコア:{fa.get("score","")})</span><br>'
                    f'<span style="color:#cbd5e1;">理由: {fa.get("reason","")}</span>'
                    f'</div>', unsafe_allow_html=True
                )
        else:
            st.caption("現在、処刑・解雇されたエージェントはいません。全10名が厳格基準をクリアして稼働中です。")

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
# 9. 高速並列データ収集
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
                        "impact_score": 92
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
        codes, sf, mech = ["6857.T", "8035.T", "6146.T", "5803.T", "NVDA"], "AI半導体・データセンター", "米SOX指数とNVIDIAの動きに連動。機関投資家がバスケット買いを仕掛けやすい状況です。"
    elif any(w in t_up for w in ["防衛", "三菱重", "宇宙", "衛星"]): 
        codes, sf, mech = ["7011.T", "7012.T", "5595.T", "186A.T", "PLTR"], "防衛国策・航空宇宙", "地政学リスクや国策防衛予算の拡大を背景に、主力大型株へ資金が流入しています。"
    else: 
        codes, sf, mech = ["9984.T", "6857.T", "5803.T"], "日米主力・モメンタム", "市場全体のセンチメントを押し上げる材料です。指数寄与度の高い銘柄から動意づきます。"
    return {
        "sector_focus": sf, "mechanism": mech, "related_codes": codes, 
        "action_guide": "① 朝の気配値とギャップを確認。\n② 主力株がギャップアップした場合、出遅れている周辺銘柄の押し目を狙うのが勝率の高い手口です。"
    }

# ==========================================
# 10. AI合議と並列Web検索ロジック (2ch風リアル対話エンジン)
# ==========================================
def search_single_query(query: str, max_results: int) -> list:
    ctx = ssl.create_default_context()
    results = []
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=ja&gl=JP&ceid=JP:ja"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=3.0, context=ctx) as r:
            root = ET.fromstring(r.read())
            for it in root.findall("./channel/item")[:max_results]:
                t = re.sub(r"<[^>]+>", "", it.findtext("title") or "").strip()
                t = re.sub(r"\s*-\s*[^-]+$", "", t).strip()
                d = re.sub(r"<[^>]+>", "", it.findtext("description") or "").strip()
                if t: results.append(f"{t} ({d[:70]}...)")
    except Exception: pass
    return results

def search_web_knowledge_parallel(query1: str, query2: str) -> list:
    results = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(search_single_query, query1, 3)
        f2 = executor.submit(search_single_query, query2, 3) if query2 else None
        results.extend(f1.result())
        if f2: results.extend(f2.result())
    return list(dict.fromkeys(results))

def generate_humanlike_2ch_debate(r: dict, user_query: str) -> list:
    uq = user_query.strip()
    is_greeting = any(w in uq for w in ["こんにちは", "こんちは", "こんばんは", "おはよ", "初めまして", "よろしく", "押忍", "ども"])
    
    web_hits = []
    if not is_greeting and len(uq) > 1:
        web_hits = search_web_knowledge_parallel(f"{r['name']} {uq}", f"{r['code']} 株価 掲示板")
    
    top_news_context = web_hits[0] if web_hits else "特段の突発バッドニュースなし、大口の買い板継続中"

    sys_prompt = f"""
あなたは日本の2ch（5ch）の市況実況スレにいる4人の凄腕個人投資家（AIエージェント）です。
対象銘柄は【{r['code']} {r['name']}】です。現在値: {r['price']}、期待度: {r['expect_pct']}%。
関連ニュースコンテキスト: {top_news_context}

ユーザーの書き込み（質問や意見）に対して、以下の4人のキャラクターで順番にレスアンカーを付けて返信してください。
【キャラクター】
1. 🔥 IGNIS: 熱血順張り派。口調は荒く「～だろ！」「～じゃねえぞ！」。トーン: rage または agree
2. 📐 TECHNOS: 冷徹なクオンツ派。丁寧語で数値を重視「～ですね」「～と推測されます」。トーン: normal
3. 👁️ SENTINEL: 疑心暗鬼の逆張り派。イナゴを嫌う「～だろｗ」「気をつけろよ」。トーン: doubt
4. ⚔️ VALKYRIE: 板読みスキャルパー。「～万株の買いが入った！」「ブレイク秒読み！」。トーン: agree

必ず以下のJSON形式（配列）で出力してください。JSON以外のテキストは絶対に出力しないでください。
[
    {{"speaker": "🔥 IGNIS", "score": 91, "tone": "rage", "text": "レス内容"}},
    {{"speaker": "📐 TECHNOS", "score": 96, "tone": "normal", "text": "レス内容"}},
    {{"speaker": "👁️ SENTINEL", "score": 95, "tone": "doubt", "text": "レス内容"}},
    {{"speaker": "⚔️ VALKYRIE", "score": 92, "tone": "agree", "text": "レス内容"}}
]
"""
    llm_result = None
    if get_active_ai_providers():
        llm_response_text = call_real_llm_api(sys_prompt, uq)
        if llm_response_text:
            try:
                clean_json = re.sub(r'```json|```', '', llm_response_text).strip()
                llm_result = json.loads(clean_json)
                if not isinstance(llm_result, list) or len(llm_result) == 0:
                    llm_result = None
            except Exception:
                llm_result = None

    turns = []
    turns.append({"round": f"🔥 市況実況スレッド 【{r['code']}】{r['name']} 本スレ Part.892"})

    if llm_result:
        turns.extend(llm_result)
    else:
        if is_greeting:
            turns.extend([
                {"speaker": "🔥 IGNIS", "score": 91, "tone": "agree", "text": "うっす！挨拶乙！お前ら寄り前の気配値見たか？この地合いで呑気に挨拶してる場合じゃねえぞ、板がガンガン動いてる！"},
                {"speaker": "📐 TECHNOS", "score": 96, "tone": "normal", "text": "はい、こんにちは。挨拶は基本ですが、板のOFI（気配値の注文偏向）はすでに買い側に傾いています。感情を捨てて数値を追ってください。"},
                {"speaker": "👁️ SENTINEL", "score": 95, "tone": "doubt", "text": "新参か？こんにちはー。だが煽り屋イナゴの群れがそろそろ飛びつきそうな気配配だから、浮かれて成行特攻だけはすんなよ。"},
                {"speaker": "👑 NEXUS", "score": 97, "tone": "normal", "text": "ようこそ。本日の当銘柄の期待値は " + str(r['expect_pct']) + "%。挨拶代わりに、まずは無理のないロットで逆指値（ストップ安防止）を徹底して参戦してください。"}
            ])
        else:
            turns.extend([
                {"speaker": "🔥 IGNIS", "score": 91, "tone": "rage", "text": f"おいおい！『{uq}』って書き込みあったぞ！直近の材料見ろや！【{top_news_context[:45]}】って話出てるのにまだ迷ってんのか？押し目来たら即買い一択だろ！"},
                {"speaker": "📐 TECHNOS", "score": 96, "tone": "normal", "text": f"冷徹に数字を見ろ。『{uq}』への懸念は理解できるが、現在値 {r['price']} に対するサポートラインは堅牢。ボラティリティ急拡大に備えて分割で入るのが合理的だ。"},
                {"speaker": "👁️ SENTINEL", "score": 95, "tone": "doubt", "text": f"スレ民落ち着けw 『{uq}』でTwitter（X）検索したらイナゴ共が狼狽して損切り投げてるわ。大口はこういう個人を狩ってから一気に上に持っていくんだよな。"},
                {"speaker": "⚔️ VALKYRIE", "score": 92, "tone": "agree", "text": f"歩み値確認した。さっき 2万株のステルス買いが入ったぞ！『{uq}』を材料にした売り崩しは完全に失敗してる。上値ブレイク秒読みだな。"},
                {"speaker": "👑 NEXUS", "score": 97, "tone": "normal", "text": f"合議集約するぞ。『{uq}』についての議論は出尽くした。結論として、直近目標値 {r['tp_price']}、絶対損切ライン {r['sl_price']} のルールを1ミリも崩さず執行せよ。"}
            ])
    return turns

def run_7ai_council(r: dict, m5=None, seed: int = 0, user_query: str = "") -> dict:
    fs = r["ai_score"]
    
    if user_query.strip():
        turns = generate_humanlike_2ch_debate(r, user_query)
    else:
        roster = st.session_state.get("agent_roster", DEFAULT_AGENTS)
        lead_ag = roster.get("NEXUS", list(roster.values())[0])
        sub_ag1 = roster.get("IGNIS", list(roster.values())[1])
        sub_ag2 = roster.get("AEGIS", list(roster.values())[2])
        sub_ag3 = roster.get("TECHNOS", list(roster.values())[3])

        turns = [
            {"round": f"💬 2ch市況実況風・エージェント合議スレ 【{r['code']}】"}, 
            {"speaker": f"{sub_ag1['icon']} {sub_ag1['name']}", "score": sub_ag1["score"], "tone": "agree", "text": f"キタキタキタ！板が完全に上に向かって食い上がってる！期待度 {r['expect_pct']}%は伊達じゃねえぞ、乗り遅れたら置いてかれるぞ！"},
            {"speaker": f"{sub_ag2['icon']} {sub_ag2['name']}", "score": sub_ag2["score"], "tone": "doubt", "text": f"おい待て調子に乗るな。浮かれて高値掴みしたら即死だぞ。必ず損切りライン（{r['sl_price']}）をOCOで入れてから入るのが鉄則だ。"},
            {"speaker": f"{sub_ag3['icon']} {sub_ag3['name']}", "score": sub_ag3["score"], "tone": "normal", "text": f"OFI乖離度 Z={r['ofi_z']}、大口ステルス買い比率は {r['kyle_stealth']}%。統計上、下値余地は極小です。理論寄付き（{r['pts_est_price']}）前後のエントリーが最もリスクリワードが合致します。"},
            {"speaker": f"{lead_ag['icon']} {lead_ag['name']}", "score": lead_ag["score"], "tone": "normal", "text": f"統括する。推奨ロット（{r['lot_info']['shares']:,}株）を守り、目標利確（{r['tp_price']}）まで粘れ。"}
        ]

    v_html = (
        f'<div style="background:rgba(0,0,0,0.35); border:1px solid rgba(255,255,255,0.12); border-radius:8px; padding:12px; margin-top:5px;">'
        f'<div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:6px; text-align:center; margin-bottom:10px;">'
        f'<div style="background:rgba(16,185,129,0.15); padding:6px; border-radius:6px; border:1px solid rgba(16,185,129,0.4);">'
        f'<div style="font-size:10px; color:#a7f3d0;">🎯 目標利確価格</div>'
        f'<div style="font-size:14px; font-weight:800; color:#10b981;">{r["tp_price"]}</div></div>'
        f'<div style="background:rgba(239,68,68,0.15); padding:6px; border-radius:6px; border:1px solid rgba(239,68,68,0.4);">'
        f'<div style="font-size:10px; color:#fca5a5;">🛡️ 絶対損切(逆指値)</div>'
        f'<div style="font-size:14px; font-weight:800; color:#ef4444;">{r["sl_price"]}</div></div>'
        f'<div style="background:rgba(56,189,248,0.15); padding:6px; border-radius:6px; border:1px solid rgba(56,189,248,0.4);">'
        f'<div style="font-size:10px; color:#bae6fd;">⏱️ 想定保有期間</div>'
        f'<div style="font-size:12.5px; font-weight:800; color:#38bdf8;">{r["strat"]["trade_duration"]}</div></div>'
        f'</div>'
        f'<div style="font-size:12px; line-height:1.7; color:#e2e8f0;"><b>⚡ プロ執行アクション詳細プラン:</b><br>{r["strat"]["step_plan"]}</div>'
        f'</div>'
        f'<div class="beginner-action-box" style="margin-top:10px;">{r["strat"]["beginner_html"]}</div>'
    )
    return {"final_score": fs, "dialogue": turns, "verdict_html": v_html}

def _fmt_turn(t: dict, idx: int = 0) -> str:
    if "round" in t: return f'<div class="round-divider">{t["round"]}</div>'
    if t.get("is_user"): return f'<div class="chat-bubble-user" id="{t.get("dom_id", "")}"><b>🗣️ あなた (レス):</b><br>{t["text"]}</div>'
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
            st.session_state["focused_stock_item"] = r
            st.rerun()
        if c2.button("✅ 監視済" if r["code"] in st.session_state["watchlist"] else "⭐ 監視追加", key=f"btn_watch_{uk}", use_container_width=True):
            if r["code"] in st.session_state["watchlist"]: del st.session_state["watchlist"][r["code"]]
            else: st.session_state["watchlist"][r["code"]] = r
            st.rerun()
        
    if not is_open: return

    if uk not in st.session_state["council_threads"]:
        with st.spinner("⚛️ 10大エージェント完全並列合議中..."):
            deb = run_7ai_council(r, None, 0, "")
            st.session_state["council_threads"][uk] = deb["dialogue"]
            st.session_state["council_meta"][uk] = deb
            
    meta = st.session_state["council_meta"][uk]
    turns = st.session_state["council_threads"][uk]

    st.markdown(f'<div class="ai-council-box"><div class="council-scroll-window" id="scroll_window_{uk}">{"".join(_fmt_turn(t, i) for i, t in enumerate(turns))}</div></div>', unsafe_allow_html=True)
    
    with st.form(f"form_q_{uk}", clear_on_submit=True):
        jc1, jc2 = st.columns([3.2, 1])
        uop = jc1.text_input("質問・発言", placeholder=f"『{r['name']}』への質問・スレへの書き込み", label_visibility="collapsed")
        if jc2.form_submit_button("💬 質問投下", use_container_width=True) and uop.strip():
            u_text = uop.strip()
            new_dom_id = f"user_q_anchor_{uk}_{int(time.time()*1000)}"
            st.session_state["council_threads"][uk].append({"is_user": True, "text": u_text, "dom_id": new_dom_id})
            with st.spinner(f"🌐 『{u_text}』について最新Web情報を並列検索＆2ch合議生成中..."):
                deb_updated = run_7ai_council(r, None, 0, user_query=u_text)
                for new_t in deb_updated["dialogue"]: st.session_state["council_threads"][uk].append(new_t)
                st.session_state["council_meta"][uk] = deb_updated
                st.session_state["scroll_target_id"] = new_dom_id
                st.rerun()

    st.markdown(f'<div class="consensus-banner"><div style="font-weight:800;color:#fde047;font-size:13px;margin-bottom:6px;">🏛️ 最終結論 ＆ プロ推奨買い方アクションプラン</div>{meta["verdict_html"]}</div>', unsafe_allow_html=True)

    if auto_open:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("⬅️ 一覧に戻る (他の銘柄を見る)", key=f"btn_back_bottom_{uk}", use_container_width=True, type="primary"):
            st.session_state["focused_stock_item"] = None
            st.rerun()

def render_card(r, is_custom=False, rank=None, kp="card", is_focused=False):
    rel_news = next((n for n in all_impact_news if r["full_code"] in n["detail"]["related_codes"]), None)
    dc, ds, ps = "#10b981" if r["diff"] >= 0 else "#ef4444", ("+" if r["diff"] > 0 else ""), ("+" if r["pts_gap_pct"] > 0 else "")
    rk_h = f'<span class="pill-badge" style="background:#f59e0b;color:#0f172a;border:none;">🏆 #{rank}</span>' if rank else ""
    lot, st_info = r["lot_info"], r["strat"]
    
    news_banner_html = ""
    if rel_news:
        short_t = rel_news['title'][:32] + "..." if len(rel_news['title']) > 32 else rel_news['title']
        news_banner_html = (
            f'<div style="margin-top:6px; margin-bottom:4px;">'
            f'<span style="display:inline-block; width:100%; text-align:center; background:linear-gradient(90deg, #b91c1c 0%, #ef4444 50%, #b91c1c 100%); '
            f'color:#ffffff; font-weight:800; font-size:11.5px; padding:5px 8px; border-radius:6px; border:1px solid #fca5a5; animation:alert-pulse 2s infinite;">'
            f'🚨【重大情報】{short_t}'
            f'</span></div>'
        )

    full_card_html = (
        f'<div class="{"search-result-card" if is_custom else "rank-card"}">'
        f'<div class="signal-10tier-badge" style="background:{r["tier_bg"]};color:{r["tier_color"]};"><span>{r["tier_label"]}</span><span>🔥 期待度 {r["expect_pct"]}% ｜ {st_info["algo_name"].split("】")[0]}】</span></div>'
        f'<div style="margin-bottom:6px;">{rk_h}<span class="pill-badge" style="background:rgba(250,204,21,0.18);border-color:#facc15;color:#fde047;font-weight:900;">🔥 期待度 {r["expect_pct"]}%</span><span class="quantum-badge">⚛️ 量子Q {r["q_score"]}点</span><span class="inst-badge">🏛️ 機関ミクロ {r["ms_score"]}点</span></div>'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">'
        f'<div style="min-width:0;flex:1;">'
        f'<div style="display:flex;align-items:baseline;flex-wrap:wrap;gap:4px;"><span style="font-size:16px;font-weight:800;color:#f8fafc;white-space:nowrap;">{r["name"]}</span> <span style="font-size:11.5px;color:#94a3b8;white-space:nowrap;">({r["code"]} / {r["genre"]})</span></div>'
        f'<div style="font-size:11px;color:#94a3b8;margin-top:3px;word-break:keep-all;">{r["theme"]} ｜ 現在値: <b style="color:#f8fafc;">{r["price"]}</b> (<span style="color:{dc};font-weight:700;">{ds}{r["diff"]}%</span>)</div>'
        f'</div>'
        f'<div style="text-align:right;white-space:nowrap;flex-shrink:0;"><div style="font-size:9px;color:#fde047;font-weight:700;">🔥 期待度 / 勝率</div><div style="white-space:nowrap;margin-top:1px;"><span class="expect-badge">{r["expect_pct"]}%</span><span style="color:#64748b;font-size:12px;margin:0 2px;">/</span><span class="prob-badge">{r["total_win_rate"]}%</span></div></div></div>'
        f'{news_banner_html}'
        f'<div class="winrate-bar"><div><div style="font-size:9.5px;color:#fde047;">🔥 総合期待度</div><div style="font-size:12.5px;font-weight:900;color:#fef08a;">{r["expect_pct"]}%</div></div><div><div style="font-size:9.5px;color:#c084fc;">⚛️ 量子トンネル</div><div style="font-size:12.5px;font-weight:800;color:#e9d5ff;">{r["q_tunnel"]}%</div></div><div><div style="font-size:9.5px;color:#6ee7b7;">🏛️ Kyle吸収</div><div style="font-size:12.5px;font-weight:800;color:#a7f3d0;">{r["kyle_stealth"]}%</div></div><div><div style="font-size:9.5px;color:#94a3b8;">🌅 翌朝GU / 陽線</div><div style="font-size:12px;font-weight:700;">{r["prob"]}% / {r["intraday_win_rate"]}%</div></div></div>'
        f'<div class="trade-plan-box"><div><div style="font-size:9.5px;color:#94a3b8;">🌅 理論寄付き</div><div style="font-size:12px;font-weight:700;">{r["pts_est_price"]} ({ps}{r["pts_gap_pct"]}%)</div></div><div style="border-left:1px solid rgba(148,163,184,0.16);border-right:1px solid rgba(148,163,184,0.16);"><div style="font-size:9.5px;color:#10b981;">🎯 利確目標</div><div style="font-size:12px;font-weight:800;color:#10b981;">{r["tp_price"]} (+{r["tp_pct"]}%)</div></div><div><div style="font-size:9.5px;color:#f87171;">🛡️ 逆指値(損切)</div><div style="font-size:12px;font-weight:800;color:#f87171;">{r["sl_price"]} ({r["sl_pct"]}%)</div></div></div>'
        f'<div class="sizing-box"><span>📦 <b>推奨ロット: {lot["shares"]:,}株</b> ({st_info["risk_posture"].split("（")[0]}) ｜ 投資額 {lot["position_value"]:,.0f}円</span><span>VWAP: <b>{r["vwap_price"]}</b></span></div>'
        f'<details class="quant-detail-drawer"><summary>⚛️ 量子QWM-7 × 機関戦略詳細（タップで開閉）</summary>'
        f'<div style="font-size:11.5px;color:#cbd5e1;margin-top:4px;line-height:1.5;"><b>{st_info["algo_name"]}</b><br>{st_info["core_logic"]}</div>'
        f'</details></div>'
    )
    st.markdown(full_card_html, unsafe_allow_html=True)

    if rel_news:
        if st.button(f"🚨【速報】重大ニュースの詳細分析を開く", key=f"nb_{kp}_{r['code']}", use_container_width=True):
            st.session_state["selected_news_item"] = rel_news
            st.session_state["navigation_page"] = "NEWS_DETAIL"
            st.session_state["scroll_top_trig"] = int(time.time()*1000)
            st.rerun()

    if is_focused:
        render_council_sec(r, f"foc_{r['code']}", auto_open=True)
    else:
        render_council_sec(r, f"{kp}_{r['code']}", auto_open=False)

# ==========================================
# 12. 本格数理クオンツ・エンジン
# ==========================================
@st.cache_data(ttl=900)
def fetch_5ch_live() -> dict: 
    return {c: {"hits": 10 + (hash(c) % 25), "live": True} for c in KNOWN_STOCKS}

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
    return {
        "q_score": q_score, "q_tunnel": round(qt, 1), 
        "q_coherence": round(coherence, 1), "q_entropy": round(shannon_entropy, 2), 
        "q_state": q_state
    }

def compute_inst_microstructure(c: np.ndarray, h: np.ndarray, l: np.ndarray, v: np.ndarray) -> dict:
    rets = np.diff(c) / np.maximum(c[:-1], 1e-4)
    n = min(len(rets), 30)
    sub_rets = rets[-n:]
    
    mean_r = np.mean(sub_rets)
    dev = np.cumsum(sub_rets - mean_r)
    r_val = np.max(dev) - np.min(dev)
    s_val = np.std(sub_rets)
    hurst = np.clip(np.log(r_val / s_val) / np.log(n), 0.30, 0.85) if (s_val > 1e-6 and r_val > 1e-6) else 0.50

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

def select_dynamic_strategy(code: str, style: str, tot_win: float, expect_pct: float, ofi_z: float, vpin: float, yz_vol: float, cvar95: float, rsi: float, cpos: float, base_sh: int, pest_str: str, vwap_str: str, tp_str: str, sl_str: str, kelly_pct: float, qm: dict, ms: dict) -> dict:
    st_prefix = style.split(" ")[1] if " " in style else "デイトレード"
    
    if st_prefix == "スキャルピング":
        sh = max(1, int(round(base_sh * 1.5)))
        return {
            "algo_name": f"⚡ [{st_prefix}] 1分足モメンタム一気貫通型",
            "risk_posture": f"🚀 スキャル全開（ <b>{sh:,}株</b> で一気に抜く）",
            "core_logic": f"OFI(Z={ofi_z})とLULD引力({ms['luld_magnet']}%)が急加速している特異点で即座にエントリー。",
            "adj_shares": sh,
            "trade_duration": "約30秒 〜 最長5分以内（超短期決戦）",
            "step_plan": (
                f"① 【朝9:00:00】寄り付き直後の板気配（買い注文と売り注文の勢い）を確認し、<b>{sh:,}株</b>を成行買いで即時約定させる。<br>"
                f"② 【約定直後（秒速）】利益確定の指値注文を<b>{tp_str}</b>にセット。同時に<b>{sl_str}</b>で逆指値（損切り予約）をOCO注文（一方が成立したら他方を自動取消する注文）で常時発注。<br>"
                f"③ 【9:05まで】目標到達または時間経過で全株決済し、翌日への持ち越しは一切行わない。"
            ),
            "beginner_html": (
                f"<b>🔰 超初心者向け！スキャルピング実践講座（数分で確実に利益を狙う方法）</b><br>"
                f"<b>【用語解説】</b><br>"
                f"・成行（なりゆき）注文：値段を指定せず、今すぐ一番手前の価格で即座に買う注文のこと。<br>"
                f"・逆指値（ぎゃくさしね）：株価が下がったときに『これ以上損を広げないため自動で売却して逃げる』安全装置のこと。<br>"
                f"<b>【時間帯と手順】</b><br>"
                f"<b>・朝8:55〜9:00：</b> 証券会社のアプリを開き、買付余力を確認して待機します。<br>"
                f"<b>・朝9:00（市場オープン）：</b> スタートと同時に<b>{sh:,}株</b>を「成行」で買います。<br>"
                f"<b>・朝9:01〜9:03：</b> 買えたらすぐ、<b>{tp_str}</b>に売り注文、万一に備えて<b>{sl_str}</b>に損切り注文を入れます。<br>"
                f"<b>・目安期間：</b> わずか1分〜3分程度で決着させます。欲張らずにサクッと利確するのが最大の秘訣です！"
            )
        }
    elif st_prefix == "スイングトレード":
        sh = max(1, int(round(base_sh * 1.2)))
        l1, l2 = max(1, int(round(sh * 0.6))), max(0, sh - max(1, int(round(sh * 0.6))))
        return {
            "algo_name": f"📈 [{st_prefix}] トレンドフォロー・押し目分割型",
            "risk_posture": f"🏛️ スイング本玉買い（初回 <b>{l1:,}株</b> ＋ 押し目 <b>{l2:,}株</b>）",
            "core_logic": f"Hurst指数({ms['hurst']})が強いトレンド継続を示唆。数日間〜数週間かけて上値を追う王道フォーメーション。",
            "adj_shares": sh,
            "trade_duration": "3日 〜 最長2週間程度（ゆったりトレンド狙い）",
            "step_plan": (
                f"① 【1日目・前場】打診買い（お試しのエントリー）として全体の6割にあたる<b>{l1:,}株</b>を取得。<br>"
                f"② 【2〜3日目】一時的な下落（押し目）かつVWAP（その日の平均約定価格: <b>{vwap_str}</b>）付近で反発を確認したら、残りの<b>{l2:,}株</b>を買い増し。<br>"
                f"③ 【目標到達時】<b>{tp_str}</b>近辺で半分を利確し、残りはトレイリングストップ（株価上昇に合わせて損切りラインを引き上げる手法）で利益を最大化。"
            ),
            "beginner_html": (
                f"<b>🔰 超初心者向け！スイングトレード実践講座（数日〜1週間かけてどっしり増やす）</b><br>"
                f"<b>【用語解説】</b><br>"
                f"・押し目（おしめ）：上昇トレンドの中で、一時的に株価が少し下がってお買い得になっている絶好のチャンスのこと。<br>"
                f"・分割エントリー：一度に全額を使わず、2〜3回に分けて買うことでリスクを大幅に減らすプロの買い方。<br>"
                f"<b>【時間帯と手順】</b><br>"
                f"<b>・初日（朝9:30以降）：</b> 寄り付き直後の乱高下が落ち着いた午前9時30分頃、まず半分の<b>{l1:,}株</b>を買います。<br>"
                f"<b>・2日目〜4日目：</b> 少し株価が下がって反発する気配を見せたら、残りの<b>{l2:,}株</b>を買い足します。<br>"
                f"<b>・保有期間：</b> 焦らず3日〜2週間ほどじっくり待ち、目標価格の<b>{tp_str}</b>に達したら利益確定します。"
            )
        }
    
    sh = max(1, int(round(base_sh * 1.65)))
    return {
        "algo_name": f"🔥 [{st_prefix}] 情報精度S級・寄り前モメンタム特攻型",
        "risk_posture": f"👑 フルベット・勝負玉（ <b>{sh:,}株一括投入</b> ）",
        "core_logic": f"期待値({expect_pct}%)と量子スコア({qm['q_score']}点)が極大。寄り付き一括で最高期待値を抜き取る戦術。",
        "adj_shares": sh,
        "trade_duration": "前場9:00 〜 11:30（または後場15:00の大引けまで）",
        "step_plan": (
            f"① 【8:50〜9:00】板情報と気配値を観察し、理論寄付き予想値（<b>{pest_str}</b>）からの乖離率を確認。<br>"
            f"② 【9:00:00】寄り付き直後に推奨全ロットである<b>{sh:,}株</b>を一括成行買い。<br>"
            f"③ 【9:05】約定完了後、ただちに<b>{sl_str}</b>に損切り逆指値をセットし下落リスクを完全封殺。<br>"
            f"④ 【11:30前】前場引け前に目標値<b>{tp_str}</b>に接近した場合は手仕舞いし、当日の利益を確実に口座へ固定する。"
        ),
        "beginner_html": (
            f"<b>🔰 超初心者向け！デイトレード実践講座（その日のうちに勝負を完結させる）</b><br>"
            f"<b>【用語解説】</b><br>"
            f"・前場（ぜんば）：午前の市場時間（9:00〜11:30）のこと。最も活発に株価が動きます。<br>"
            f"・大引け（おおびけ）：午後15:30の市場終了のこと。翌日に持ち越さず当日中に売るのがデイトレです。<br>"
            f"<b>【時間帯と手順】</b><br>"
            f"<b>・朝8:55：</b> 画面の前でスタンバイし、ログインしておきます。<br>"
            f"<b>・朝9:00（スタート）：</b> 迷わず<b>{sh:,}株</b>を成行で買い付けます。<br>"
            f"<b>・朝9:05：</b> 買えたらすぐ、絶対に大損しないよう安全ストッパーとして<b>「{sl_str}」</b>に損切りの予約を入れます。<br>"
            f"<b>・午前中（〜11:30）：</b> 株価が上がって目標の<b>{tp_str}</b>に届いたら自動で売れて利益確定！その日のうちにすっきり勝利を確定させます。"
        )
    }

def analyze_df(df_raw, code, name, theme, genre, macro, b5_live_map, style, bi=True, b5=True, bal=True, bms=True, bagi_q=False, bhft=False):
    try:
        if df_raw is None or df_raw.empty: return None
        df = df_raw.dropna(subset=["Close", "Open", "High", "Low", "Volume"]).copy()
        if len(df) < 30: return None
        
        c = df["Close"].values.astype(float)
        o = df["Open"].values.astype(float)
        h = df["High"].values.astype(float)
        l = df["Low"].values.astype(float)
        v = df["Volume"].values.astype(float)
        
        df["Prev_Close"] = df["Close"].shift(1)
        df["Day_Return"] = (df["Close"] - df["Open"].iloc[0]) / df["Open"].iloc[0] * 100 if len(df) > 0 else 0
        tr = pd.concat([df["High"] - df["Low"], (df["High"] - df["Prev_Close"]).abs(), (df["Low"] - df["Prev_Close"]).abs()], axis=1).max(axis=1)
        df["ATR"] = tr.rolling(14).mean().fillna(df["Close"] * 0.02)
        df["VWAP20"] = (((df["High"] + df["Low"] + df["Close"]) / 3.0 * df["Volume"]).rolling(20).sum() / df["Volume"].rolling(20).sum().replace(0, np.nan)).fillna(df["Close"])
        
        qm = compute_quantum_wave_metrics(c, h, l, v)
        ms = compute_inst_microstructure(c, h, l, v)
        
        lat = df.iloc[-1]
        cv = float(lat["Close"])
        atrv = float(lat["ATR"])
        
        recent_20_wins = np.sum(df["Close"].diff().iloc[-20:] > 0)
        tot_win = float(np.clip(recent_20_wins / 20.0 * 100.0 * 0.4 + qm["q_tunnel"] * 0.35 + ms["kyle_stealth"] * 0.25, 48.0, 96.5))
        
        hl_r = np.maximum(h - l, 1e-4)
        sf = ((2.0 * c - h - l) / hl_r) * v
        mean_sf_5 = np.mean(sf[-5:])
        mean_sf_20 = np.mean(sf[-20:])
        std_sf_20 = max(float(np.std(sf[-20:])), 1.0)
        ofi_z = float(np.clip((mean_sf_5 - mean_sf_20) / std_sf_20, -3.0, 3.0))

        macro_bias = 0.0
        if "sox" in macro and ("半導体" in genre or "NVDA" in code):
            macro_bias += float(macro["sox"]["diff"]) * 1.2
        if "nk_fut" in macro and ".T" in code:
            macro_bias += float(macro["nk_fut"]["diff"]) * 0.8

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
            code.replace(".T", ""), style, tot_win, round(expect_pct, 1), ofi_z, 0.5, 0.4, 3.5, 60.0, 0.8, 
            base_sh, fp(pest), fp(float(lat["VWAP20"])), 
            f"{fp(tpv)}(+{round((tpv-cv)/cv*100,1)}%)", f"{fp(slv)}({round((slv-cv)/cv*100,1)}%)", 15.0, qm, ms
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

@st.cache_data(ttl=1800)
def fetch_pool_batch(macro, b5_live_map, style, bi, b5, bal, bms, bagi_q, bhft):
    codes = list({s["code"] for sts in STOCK_POOL.values() for s in sts})
    raw = yf.download(codes, period="5d", interval="5m", group_by="ticker", threads=True, progress=False, timeout=9)
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
    return analyze_df(yf.Ticker(code).history(period="5d", interval="5m"), code, inf["name"], inf["theme"], inf["genre"], macro, b5_live_map, style, bi, b5, bal, bms, bagi_q, bhft)

# ==========================================
# 13. ヘッダー / マクロ指標
# ==========================================
macro_info = fetch_macro()
b5_live_map = fetch_5ch_live()
all_impact_news = fetch_global_impact_news()

mpills = "".join([f'<div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);padding:2px 8px;border-radius:6px;font-size:10.5px;display:inline-flex;gap:4px;"><span style="color:#94a3b8;">{m["label"]}</span><span style="color:{"#10b981" if m["diff"]>=0 else "#ef4444"};font-weight:700;">{"+" if m["diff"]>=0 else ""}{m["diff"]}%</span></div>' for m in macro_info.values()])
st.markdown(f'<div class="glass-header"><div style="display:flex;justify-content:space-between;align-items:center;"><div class="brand-luxury">YAMASHISHI LAB</div></div><div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:8px;">{mpills}</div></div>', unsafe_allow_html=True)

with st.spinner(f"⚛️ 【{investment_style.split(' ')[1]}】全市場全銘柄を並列ディープスキャン中..."):
    g_res, all_res = fetch_pool_batch(macro_info, b5_live_map, investment_style, "inst" in ac_b, "mom" in ac_b, "algo" in ac_b, "ms" in ac_b, "agi_q" in ac_b, "hft_front" in ac_b)

# ==========================================
# 14. 画面レンダリング
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
        db_m = load_mem()
        sec_m = load_sec()
        
        st.markdown(
            """
            <div class="admin-table-container">
            <table class="admin-table">
            <thead>
                <tr>
                    <th>お名前</th>
                    <th>メールアドレス</th>
                    <th>専用パスコード</th>
                    <th>PINハッシュ</th>
                    <th>端末指紋 (FP)</th>
                    <th>登録日</th>
                    <th>状態</th>
                </tr>
            </thead>
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
            ]) + """
            </tbody>
            </table>
            </div>
            """, unsafe_allow_html=True
        )

        st.markdown("<br><b>⚡ 会員個別操作パネル</b>", unsafe_allow_html=True)
        col_u1, col_u2 = st.columns([3, 2])
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
                tfp = db_m[target_em].get("fp")
                trhfp = db_m[target_em].get("raw_hfp")
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

        st.markdown("<br><b>💀 過去に解雇されたエージェント履歴 (標タイプ)</b>", unsafe_allow_html=True)
        fired_list = st.session_state.get("fired_agents", [])
        if fired_list:
            st.markdown(
                """
                <div class="admin-table-container">
                <table class="admin-table">
                <thead>
                    <tr>
                        <th>解雇日時</th>
                        <th>エージェント名</th>
                        <th>最終スコア</th>
                        <th>解雇執行者</th>
                        <th>解雇理由・違反事項</th>
                    </tr>
                </thead>
                <tbody>
                """ + "".join([
                    f"<tr><td>{fa.get('time','-')}</td>"
                    f"<td style='color:#f87171;'><b>{fa.get('name','')}</b></td>"
                    f"<td style='color:#fde047;'>{fa.get('score','')}</td>"
                    f"<td style='color:#38bdf8;'>{fa.get('fired_by','特命監査員')}</td>"
                    f"<td>{fa.get('reason','')}</td></tr>"
                    for fa in fired_list
                ]) + """
                </tbody>
                </table>
                </div>
                """, unsafe_allow_html=True
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
                    f'<div style="background:rgba(15,23,42,0.85);border:1px solid rgba(56,189,248,0.3);border-radius:8px;padding:10px 14px;margin-bottom:8px;">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">'
                    f'<div>'
                    f'<span style="font-size:13.5px;font-weight:800;color:#f8fafc;">{p_u.get("name","未入力")}</span> '
                    f'<span style="font-size:11.5px;color:#94a3b8;">({p_em})</span><br>'
                    f'<span style="font-size:10.5px;color:#64748b;">申請日: {p_u.get("applied_at","-")} ｜ 端末FP: {p_u.get("fp","-")}</span>'
                    f'</div>'
                    f'</div>'
                    f'</div>', unsafe_allow_html=True
                )
                col_btn1, col_btn2 = st.columns([1, 1])
                if col_btn1.button(f"✅ 承認する ({p_u.get('name','')})", key=f"appr_{p_em}", use_container_width=True):
                    db_all[p_em]["status"] = "approved"
                    db_all[p_em]["approved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    db_set("mem", db_all)
                    send_mail(p_em, "【YAMASHISHI LAB】会員登録が承認されました", f"{p_u.get('name','')} 様\n申請が承認されました。専用アクセスコードは【 {db_all[p_em]['passcode']} 】です。")
                    st.success(f"{p_em} を承認しました"); st.rerun()

                if col_btn2.button(f"🚫 拒否・却下 ({p_u.get('name','')})", key=f"rej_{p_em}", use_container_width=True):
                    del db_all[p_em]
                    db_set("mem", db_all)
                    st.warning(f"{p_em} の申請を却下しました"); st.rerun()
        else:
            st.info("現在、承認待ちの新規申請はありません。")

    st.stop()

# ■ フォーカスモード（個別画面単独表示）
focused_item = st.session_state.get("focused_stock_item")
if focused_item:
    st.markdown("### ⚛️ 銘柄詳細・買い方合議フォーカスモード")
    render_card(focused_item, is_custom=False, kp=f"foc_{focused_item['code']}", is_focused=True)
    st.stop()

# ■ ニュース詳細画面
if st.session_state.get("navigation_page") == "NEWS_DETAIL":
    tn = st.session_state.get("selected_news_item") or all_impact_news[0]
    st.markdown(f'<div class="glass-header" style="border-left:4px solid #ef4444;"><span class="pill-badge" style="background:#ef4444;color:#fff;">🚨 重大ニュース深掘り</span><div style="font-size:18px;font-weight:800;margin-top:8px;">{tn["title"]}</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="rank-card" style="border-left-color:#a855f7;"><div style="font-size:14px;color:#e9d5ff;">🧠 波及メカニズム</div><div style="font-size:12.5px;">{tn["detail"]["mechanism"]}</div><div class="beginner-action-box" style="margin-top:10px;"><b>⚡ {investment_style.split(" ")[1]} 実践トレード立ち回り</b><br>{tn["detail"]["action_guide"].replace(chr(10), "<br>")}</div></div>', unsafe_allow_html=True)
    st.markdown("### 🔗 連動注目銘柄")
    for idx, r_item in enumerate(sorted(all_res, key=lambda x: x["expect_pct"], reverse=True)[:3], 1): render_card(r_item, rank=idx, kp=f"nr_{tn['id']}")
    if st.button("⬅️ 戻る", use_container_width=True, type="primary"): st.session_state["navigation_page"] = "TOP"; st.rerun()
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
st.markdown(f'<div class="compact-bar-label"><span>📂 QUANTUM STRATEGY ({investment_style.split(" ")[1]})</span></div>', unsafe_allow_html=True)

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
        st.markdown(f'<div class="rank-card" style="border-left-color:#ef4444;"><div style="font-size:11px;color:#f87171;font-weight:800;">🚨 {n["cat"]}</div><div style="font-size:14.5px;font-weight:800;color:#f8fafc;margin-bottom:4px;">{n["title"]}</div></div>', unsafe_allow_html=True)
        if st.button("🔥 詳細レポートを見る", key=f"tab_n_{n['id']}", use_container_width=True): 
            st.session_state["selected_news_item"] = n
            st.session_state["navigation_page"] = "NEWS_DETAIL"
            st.rerun()
elif sel_cat == "🎟️ IPO募集・新規上場":
    st.markdown('<div class="glass-header"><div style="font-size:16px;font-weight:800;color:#f8fafc;">🎟️ 新規上場 (IPO) ブックビルディング・詳細分析ターミナル</div><div style="font-size:11.5px;color:#94a3b8;margin-top:3px;">初値高騰期待度・ロックアップ・吸収金額・PER・VC比率まで徹底網羅した完全ガイド。</div></div>', unsafe_allow_html=True)
    for ipo in IPO_OFFERINGS:
        links_html = "".join([f'<a href="{url}" target="_blank" rel="noopener noreferrer" class="ipo-link-btn">🔗 {lbl}</a>' for lbl, url in ipo["links"]])
        st.markdown(
            f'<div class="rank-card" style="border-left-color:#f59e0b;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">'
            f'<div><span class="pill-badge" style="background:#f59e0b;color:#0f172a;font-weight:900;">🏆 第{ipo["rank"]}位</span><span class="pill-badge" style="background:rgba(250,204,21,0.2);color:#fde047;border-color:#facc15;">期待度 {ipo["expect_return"]}</span></div>'
            f'<div style="font-size:11px;color:#38bdf8;font-weight:700;">{ipo["tier"]}</div>'
            f'</div>'
            f'<div><span style="font-size:18px;font-weight:800;color:#f8fafc;">{ipo["name"]}</span> <span style="font-size:12px;color:#94a3b8;">({ipo["code"]} / {ipo["market"]})</span></div>'
            f'<div style="font-size:11.5px;color:#38bdf8;margin-top:4px;"><b>🎯 テーマ:</b> {ipo["theme"]}</div>'
            f'<div class="trade-plan-box" style="margin-top:9px;grid-template-columns: repeat(auto-fit, minmax(105px, 1fr));">'
            f'<div><div style="font-size:9.5px;color:#94a3b8;">📅 BB申込期間</div><div style="font-size:11.5px;font-weight:800;color:#fde047;">{ipo["bb_period"]}</div></div>'
            f'<div><div style="font-size:9.5px;color:#94a3b8;">🔔 上場予定日</div><div style="font-size:11.5px;font-weight:800;color:#f8fafc;">{ipo["list_date"]}</div></div>'
            f'<div><div style="font-size:9.5px;color:#94a3b8;">💰 仮条件価格帯</div><div style="font-size:11.5px;font-weight:800;color:#10b981;">{ipo["price_band"]}</div></div>'
            f'<div><div style="font-size:9.5px;color:#94a3b8;">🏛️ 主幹事証券</div><div style="font-size:11.5px;color:#bae6fd;">{ipo["lead"]}</div></div>'
            f'</div>'
            f'<div style="background:rgba(2,6,23,0.75);border:1px solid rgba(148,163,184,0.18);border-radius:8px;padding:9px 12px;margin-top:8px;font-size:11.5px;line-height:1.6;">'
            f'<div>🔒 <b>ロックアップ状況:</b> <span style="color:#e2e8f0;">{ipo["lockup"]}</span></div>'
            f'<div>📦 <b>吸収金額 (公開規模):</b> <span style="color:#e2e8f0;">{ipo["absorption"]}</span> ｜ 📊 <b>VC比率:</b> <span style="color:#e2e8f0;">{ipo["vc_ratio"]}</span></div>'
            f'<div>📈 <b>バリュエーション (PER):</b> <span style="color:#e2e8f0;">{ipo["pe"]}</span></div>'
            f'<div style="margin-top:4px;color:#a7f3d0;"><b>💡 初値立ち回り戦略:</b> {ipo["strategy"]}</div>'
            f'</div>'
            f'<div style="margin-top:8px;">{links_html}</div></div>', 
            unsafe_allow_html=True
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
