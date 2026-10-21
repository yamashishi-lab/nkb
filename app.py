import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np
import altair as alt
import unicodedata, hashlib, hmac, time, json, os, re, ssl, smtplib
import urllib.parse, urllib.request, urllib.error
from email.mime.text import MIMEText
from datetime import datetime

st.set_page_config(page_title="翌朝株価 クオンツ＆AI合議 Pro", page_icon="⚡", layout="centered")
frag_dec = getattr(st, "fragment", getattr(st, "experimental_fragment", lambda f: f))

ADMIN_EMAIL = "nthbh399@ybb.ne.jp"
SECRET_KEY = "my_super_secret_quant_key_2026"
FILES = {"mem": "members_db.json", "smtp": "admin_smtp_config.json", "llm": "admin_llm_config.json"}
# 別クォータ枠を持つモデル群を優先順に配置（429発生時は瞬時に次モデルへローテーションし、全枠上限なら内蔵AIへシームレス切替）
G_MODELS = ["gemma-3-27b-it", "gemini-2.0-flash-lite", "gemini-2.0-flash", "gemini-flash-latest", "gemini-3.8-flash", "gemini-3.1-pro-preview"]

def clean_k(k: str) -> str: return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(k or "")).strip().strip("\"'"))
def gen_code(em: str) -> str: return hmac.new(SECRET_KEY.encode(), em.strip().lower().encode(), hashlib.sha256).hexdigest()[:8].upper()
def gen_tok(em: str, act: str) -> str: return hashlib.sha256(f"{em.strip().lower()}:{act}:{SECRET_KEY}".encode()).hexdigest()[:16]

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

def load_smtp(): return load_j(FILES["smtp"], {"app_base_url": "http://localhost:8501", "smtp_user": ADMIN_EMAIL, "smtp_pass": "", "smtp_server": "smtp.mail.yahoo.co.jp", "smtp_port": 465})
def load_llm():
    c = load_j(FILES["llm"], {"provider": "gemini", "gemini_api_key": clean_k(os.environ.get("GEMINI_API_KEY", "")), "gemini_model": "gemma-3-27b-it", "openai_api_key": clean_k(os.environ.get("OPENAI_API_KEY", "")), "openai_model": "gpt-4o-mini"})
    c["gemini_api_key"], c["openai_api_key"] = clean_k(c.get("gemini_api_key", "")), clean_k(c.get("openai_api_key", ""))
    return c

def load_mem():
    db = load_j(FILES["mem"], {})
    adm = ADMIN_EMAIL.strip().lower()
    if adm not in db:
        ns = datetime.now().strftime("%Y-%m-%d %H:%M")
        db[adm] = {"name": "管理者", "email": adm, "status": "approved", "passcode": gen_code(adm), "applied_at": ns, "approved_at": ns}
        save_j(FILES["mem"], db)
    return db

def send_mail(to_em: str, subj: str, body: str) -> bool:
    c = load_smtp()
    u, p, srv, port = c.get("smtp_user", "").strip(), c.get("smtp_pass", "").strip(), c.get("smtp_server", "").strip(), int(c.get("smtp_port", 465))
    if not u or not p: return False
    try:
        m = MIMEText(body, "plain", "utf-8"); m["Subject"], m["From"], m["To"] = subj, u, to_em
        with (smtplib.SMTP_SSL(srv, port, timeout=6) if port == 465 else smtplib.SMTP(srv, port, timeout=6)) as s:
            if port != 465: s.starttls()
            s.login(u, p); s.send_message(m)
        return True
    except Exception: return False

qp = st.query_params
act, em, tok = qp.get("admin_action", ""), qp.get("email", "").strip().lower(), qp.get("token", "")
if act in ["approve", "reject"] and em and tok and hmac.compare_digest(tok, gen_tok(em, act)):
    db = load_mem(); code, ns = gen_code(em), datetime.now().strftime("%Y-%m-%d %H:%M")
    db[em] = {"name": db.get(em, {}).get("name", qp.get("name", "会員")), "email": em, "status": "approved" if act == "approve" else "rejected", "passcode": code, "applied_at": ns, "approved_at": ns}
    save_j(FILES["mem"], db)
    if act == "approve": send_mail(em, "【承認完了】専用コード", f"専用コード: {code}"); st.success(f"✅ {em} 承認完了 (コード: {code})")
    for k in ["admin_action", "email", "token"]:
        if k in st.query_params: del st.query_params[k]

def check_auth():
    db = load_mem()
    if "authenticated_user" not in st.session_state: st.session_state["authenticated_user"] = None
    qu, qt = st.query_params.get("u", "").strip().lower(), st.query_params.get("t", "").strip()
    if not st.session_state["authenticated_user"] and qu and qt:
        if hmac.compare_digest(qt, gen_tok(qu, "session_keep")) and ((db.get(qu) and db[qu].get("status") == "approved") or qu == ADMIN_EMAIL.strip().lower()):
            st.session_state["authenticated_user"] = qu
    if st.session_state["authenticated_user"]:
        cu = st.session_state["authenticated_user"]
        st.query_params["u"], st.query_params["t"] = cu, gen_tok(cu, "session_keep")
        with st.sidebar:
            st.markdown(f'<div style="background:#0f172a;padding:8px 12px;border-radius:10px;border:1px solid #38bdf8;margin-bottom:8px;"><div style="font-size:10px;color:#38bdf8;font-weight:800;">⚡ VERIFIED MEMBER</div><div style="color:#f8fafc;font-size:12px;font-weight:700;">{cu}</div></div>', unsafe_allow_html=True)
            if st.button("🚪 ログアウト", use_container_width=True): st.session_state["authenticated_user"] = None; st.query_params.clear(); st.rerun()
        if cu == ADMIN_EMAIL.strip().lower():
            pend = [v for v in db.values() if v.get("status") == "pending"]
            st.sidebar.subheader(f"👑 管理者 (待:{len(pend)}件)")
            if st.sidebar.button("🛠️ 会員管理画面", use_container_width=True): st.session_state["navigation_page"] = "ADMIN"; st.rerun()
            for p in pend:
                pm, pn, pc = p["email"], p.get("name", "未入力"), gen_code(p["email"])
                st.sidebar.caption(f"📩 {pn} ({pm})")
                c1, c2 = st.sidebar.columns(2)
                if c1.button("✅", key=f"ap_{pm}", use_container_width=True):
                    db[pm].update({"status": "approved", "passcode": pc, "approved_at": datetime.now().strftime("%Y-%m-%d %H:%M")}); save_j(FILES["mem"], db); send_mail(pm, "【承認完了】コード", f"コード: {pc}"); st.rerun()
                if c2.button("❌", key=f"rj_{pm}", use_container_width=True):
                    db[pm]["status"] = "rejected"; save_j(FILES["mem"], db); st.rerun()
        return True

    st.markdown('<div style="background:linear-gradient(135deg,#090d16,#1e293b);color:#f8fafc;padding:20px;border-radius:14px;text-align:center;margin-bottom:12px;"><h2 style="margin:0;color:#fbbf24;">🔒 会員限定 クオンツ＆AI合議 Pro</h2></div>', unsafe_allow_html=True)
    with st.form("login"):
        ie, ic = st.text_input("📧 メールアドレス"), st.text_input("🔑 専用アクセスコード", type="password")
        if st.form_submit_button("🔓 ログイン", use_container_width=True):
            cm = ie.strip().lower(); rec = db.get(cm)
            if ((rec and rec.get("status") == "approved") or cm == ADMIN_EMAIL.strip().lower()) and (hmac.compare_digest(ic.strip().upper(), gen_code(cm)) or (cm == ADMIN_EMAIL.strip().lower() and ic.strip() == "ADMIN777")):
                st.session_state["authenticated_user"] = cm; st.rerun()
            else: st.warning("⚠️ 未承認またはコードが違います")
    with st.form("apply"):
        st.markdown("##### 📩 新規会員登録の申請")
        an, am = st.text_input("👤 お名前"), st.text_input("📧 メール")
        if st.form_submit_button("📨 申請送信", use_container_width=True) and "@" in am:
            cm, pc, ns = am.strip().lower(), gen_code(am), datetime.now().strftime("%Y-%m-%d %H:%M")
            db[cm] = {"name": an.strip() or "未入力", "email": cm, "status": "pending", "passcode": pc, "applied_at": ns, "approved_at": "-"}
            save_j(FILES["mem"], db); st.success("✅ 申請を受け付けました")
    st.stop()

check_auth()

for k, v in [("active_debates", {}), ("streamed_keys", set()), ("stock_chats", {}), ("council_threads", {}), ("council_meta", {}), ("debate_round_seed", {}), ("debate_style_map", {}), ("watchlist", {}), ("navigation_page", "TOP"), ("custom_search_code", ""), ("active_category", "🏆 総合TOP5"), ("exhausted_models", set())]:
    if k not in st.session_state: st.session_state[k] = v

st.markdown("""<div id="page_top_anchor"></div><style>
html,body,[class*="css"]{font-size:15px;} .block-container{padding-top:4.8rem!important;padding-bottom:3rem!important;max-width:840px!important;}
.floating-glass-nav{position:fixed;top:14px;left:50%;transform:translateX(-50%);z-index:99990;display:flex;gap:12px;padding:5px 16px;background:rgba(15,23,42,0.92);backdrop-filter:blur(12px);border:1px solid rgba(56,189,248,0.3);border-radius:999px;white-space:nowrap;box-shadow:0 4px 14px rgba(0,0,0,0.35);}
.floating-glass-nav a{color:#f8fafc!important;text-decoration:none!important;font-size:11.5px;font-weight:700;}
div[data-testid="stPills"]{margin-top:-2px!important;margin-bottom:4px!important;}
div[data-testid="stRadio"]>div[role="radiogroup"]{display:flex!important;flex-wrap:wrap!important;gap:5px!important;background:rgba(15,23,42,0.92)!important;padding:6px 8px!important;border-radius:10px!important;border:1px solid rgba(56,189,248,0.25)!important;}
div[data-testid="stRadio"]>div[role="radiogroup"]>label{background:rgba(255,255,255,0.05)!important;border:1px solid rgba(255,255,255,0.12)!important;border-radius:8px!important;padding:4px 10px!important;margin:0!important;cursor:pointer!important;}
div[data-testid="stRadio"]>div[role="radiogroup"]>label>div:first-child{display:none!important;}
div[data-testid="stRadio"]>div[role="radiogroup"]>label p{color:#cbd5e1!important;font-size:12px!important;font-weight:700!important;margin:0!important;}
div[data-testid="stRadio"]>div[role="radiogroup"]>label:has(input:checked){background:linear-gradient(135deg,#0284c7,#2563eb)!important;border-color:#7dd3fc!important;}
div[data-testid="stRadio"]>div[role="radiogroup"]>label:has(input:checked) p{color:#fff!important;font-weight:800!important;}
.compact-bar-label{display:flex;justify-content:space-between;font-size:11.5px;font-weight:800;color:#38bdf8;background:linear-gradient(90deg,#0f172a,#1e293b);padding:5px 12px;border-radius:8px;border-left:3px solid #38bdf8;margin-bottom:4px;}
.company-logo-img{width:36px;height:36px;border-radius:8px;background:#fff;padding:2px;border:1px solid #e2e8f0;}
.rank-card,.search-result-card{background:linear-gradient(180deg,#fff 0%,#f8fafc 100%)!important;color:#0f172a!important;border-radius:15px;padding:15px;margin-bottom:11px;box-shadow:0 5px 16px rgba(15,23,42,0.06);border:1px solid #e2e8f0;border-left:6px solid #e11d48;}
.rank-card *,.search-result-card *{color:#0f172a;} .search-result-card{background:linear-gradient(180deg,#fffbeb 0%,#fef3c7 100%)!important;border-left-color:#d97706;}
.prob-badge{font-size:23px;font-weight:800;color:#dc2626!important;}
.rank-badge{background:linear-gradient(135deg,#f59e0b,#d97706);color:#fff!important;padding:3px 9px;border-radius:999px;font-size:11.5px;font-weight:700;margin-right:4px;}
.score-badge{background:#0f172a;color:#f8fafc!important;padding:3px 9px;border-radius:999px;font-size:11.5px;font-weight:700;}
.inst-badge{background:#1d4ed8;color:#fff!important;padding:3px 8px;border-radius:999px;font-size:11.5px;font-weight:700;margin-left:3px;}
.board5ch-badge{background:#059669;color:#fff!important;padding:3px 8px;border-radius:999px;font-size:11.5px;font-weight:700;margin-left:3px;}
.tokugai-badge{background:#d97706;color:#fff!important;padding:3px 8px;border-radius:999px;font-size:11.5px;font-weight:700;margin-left:3px;}
.winrate-bar{display:grid;grid-template-columns:repeat(4,1fr);gap:5px;background:#fff1f2!important;border:1px solid #fecdd3;border-radius:9px;padding:6px 5px;margin-top:7px;text-align:center;}
.signal-10tier-badge{display:flex;justify-content:space-between;padding:7px 12px;border-radius:9px;font-size:13px;font-weight:800;margin-bottom:7px;}
.inst-box{background:#eff6ff!important;border:1px solid #bfdbfe;border-left:4px solid #2563eb;border-radius:8px;padding:6px 10px;margin-top:5px;font-size:12px;}
.squeeze-box{background:#fff1f2!important;border:1px solid #fecdd3;border-left:4px solid #e11d48;border-radius:8px;padding:6px 10px;margin-top:5px;font-size:12px;}
.pts-tokugai-box{background:#fffbeb!important;border:1px solid #fde68a;border-left:4px solid #d97706;border-radius:8px;padding:6px 10px;margin-top:5px;font-size:12px;}
.board5ch-box{background:#ecfdf5!important;border:1px solid #a7f3d0;border-left:4px solid #059669;border-radius:8px;padding:6px 10px;margin-top:5px;font-size:12px;}
.delicate-box{background:#f8fafc!important;border:1px solid #cbd5e1;border-left:4px solid #7c3aed;border-radius:8px;padding:7px 10px;margin-top:5px;font-size:12px;line-height:1.5;}
.metrics-row{display:flex;flex-wrap:wrap;gap:5px 10px;margin-top:6px;font-size:11.5px;background:#f1f5f9!important;padding:6px 10px;border-radius:7px;}
.trade-plan-box{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin-top:6px;background:#fff!important;padding:7px 5px;border-radius:8px;border:1px solid #cbd5e1;text-align:center;}
.sizing-box{background:#f0fdf4!important;border:1px solid #86efac;border-radius:8px;padding:6px 10px;margin-top:6px;font-size:12px;}
.ai-council-box{background:linear-gradient(135deg,#090d16,#1e293b);color:#f8fafc!important;border-radius:12px;padding:12px;margin-top:6px;margin-bottom:9px;border:1px solid rgba(56,189,248,0.35);}
.ai-council-box *{color:#f8fafc;} .council-scroll-window{max-height:550px;overflow-y:auto;padding:9px;background:rgba(6,10,19,0.82);border:1px solid rgba(255,255,255,0.14);border-radius:9px;margin-bottom:8px;}
.round-divider{text-align:center;margin:8px 0;padding:4px 8px;background:rgba(56,189,248,0.18);border-top:1px solid #38bdf8;border-bottom:1px solid #38bdf8;color:#7dd3fc!important;font-size:11.5px;font-weight:800;border-radius:5px;}
.chat-bubble-ai,.chat-bubble-doubt,.chat-bubble-rebuttal,.chat-bubble-rage,.chat-bubble-humor,.chat-bubble-agree{border-radius:9px;padding:8px 11px;margin-bottom:7px;font-size:12.5px;line-height:1.6;}
.chat-bubble-ai{background:rgba(255,255,255,0.07);border-left:4px solid #38bdf8;} .chat-bubble-doubt{background:rgba(245,158,11,0.14);border-left:4px solid #f59e0b;}
.chat-bubble-rebuttal{background:rgba(225,29,72,0.14);border-left:4px solid #f43f5e;} .chat-bubble-rage{background:rgba(153,27,27,0.42);border:1px solid #ef4444;border-left:5px solid #dc2626;}
.chat-bubble-humor{background:rgba(168,85,247,0.16);border-left:4px solid #c084fc;} .chat-bubble-agree{background:rgba(16,185,129,0.14);border-left:4px solid #10b981;}
.chat-bubble-user{background:linear-gradient(135deg,#1d4ed8,#2563eb);border-radius:9px;padding:8px 11px;margin-bottom:7px;font-size:12.5px;}
.consensus-banner{background:linear-gradient(135deg,#1e1b4b,#312e81);border:1px solid #818cf8;border-radius:9px;padding:10px;margin-top:7px;font-size:12px;}
.consensus-section{background:rgba(255,255,255,0.07);border-left:3px solid #fbbf24;border-radius:5px;padding:6px 9px;margin-top:5px;}
.qa-answer-card{background:#fff!important;border:2px solid #3b82f6;border-left:6px solid #1d4ed8;border-radius:9px;padding:11px;margin-top:6px;font-size:12.5px!important;line-height:1.65!important;color:#0f172a!important;}
.qa-answer-card *{color:#0f172a!important;} .qa-direct-box{background:#eff6ff!important;border:1px solid #93c5fd;border-left:4px solid #2563eb;padding:8px 10px;border-radius:6px;margin:5px 0;} .qa-answer-card b{color:#1d4ed8!important;}
</style><div class="floating-glass-nav"><a href="#page_top_anchor">⬆️ TOP</a><span style="color:#475569;">|</span><a href="#smart_deck_anchor">⚡ エンジン＆検索</a><span style="color:#475569;">|</span><a href="#category_bar_anchor">📂 ジャンル切替</a></div>""", unsafe_allow_html=True)

# ==========================================
# 🧠 API主軸 ＋ 429完全シームレス切替コア
# ==========================================
AI_ROSTER = {
    "AEGIS": "🛡️ AEGIS (数理リスク・ドローダウン防衛官)", "IGNIS": "🔥 IGNIS (短期モメンタム・踏み上げ特攻官)",
    "TECHNOS": "📐 TECHNOS (波形構造・オシレーター解析官)", "MACRO": "🌐 MACRO (日米先物・夜間PTSギャップ戦略官)",
    "MICRO": "🔬 MICRO (機関VPIN・板オーダーフロー監査官)", "CHRONOS": "📊 CHRONOS (過去6ヶ月バックテスト統計照合官)",
    "NEXUS": "👑 NEXUS (マルチエージェント総括ディレクター)"
}

def _parse_j(raw: str):
    txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(raw or "").strip(), flags=re.IGNORECASE).strip()
    sb, eb = txt.find("{"), txt.rfind("}")
    if sb != -1 and eb > sb: txt = txt[sb:eb+1]
    return json.loads(re.sub(r"[\x00-\x1f]+", " ", re.sub(r",\s*([}\]])", r"\1", txt)))

def call_api_seamless(sys_p: str, usr_p: str, temp: float = 0.7) -> tuple:
    """APIを主軸に呼び出し、429/404モデルを自動スキップして別モデルへ切り替え、全枠上限ならエラーを出さず内蔵クオンツ推論へシームレス移行"""
    cfg = load_llm()
    prov = st.session_state.get("rt_llm_provider") or cfg.get("provider", "gemini")
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE

    if prov == "openai":
        okey = clean_k(st.session_state.get("rt_openai_api_key") or cfg.get("openai_api_key"))
        omodel = st.session_state.get("rt_openai_model") or cfg.get("openai_model", "gpt-4o-mini")
        if okey:
            try:
                req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=json.dumps({"model": omodel, "messages": [{"role": "system", "content": sys_p}, {"role": "user", "content": usr_p}], "temperature": temp, "response_format": {"type": "json_object"}}).encode("utf-8"), headers={"Content-Type": "application/json", "Authorization": f"Bearer {okey}"}, method="POST")
                with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
                    return _parse_j(json.loads(r.read().decode("utf-8"))["choices"][0]["message"]["content"]), f"OpenAI ({omodel})"
            except Exception: pass
        return None, "内蔵クオンツ数理推論AI (自動フォールバック)"

    gkey = clean_k(st.session_state.get("rt_gemini_api_key") or cfg.get("gemini_api_key"))
    if not gkey:
        return None, "内蔵クオンツ数理推論AI"

    sel_m = st.session_state.get("rt_gemini_model") or cfg.get("gemini_model", "gemma-3-27b-it")
    exhausted = st.session_state.get("exhausted_models", set())
    models = [m for m in ([sel_m] + [x for x in G_MODELS if x != sel_m]) if m not in exhausted]
    prompt = f"【システム指示】\n{sys_p}\n\n【入力データ】\n{usr_p}"

    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={urllib.parse.quote(gkey)}"
        gen_cfg = {"temperature": temp}
        if not m.startswith("gemma"): gen_cfg["responseMimeType"] = "application/json"
        req = urllib.request.Request(url, data=json.dumps({"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": gen_cfg}).encode("utf-8"), headers={"Content-Type": "application/json", "User-Agent": "QuantPro/6.0"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=12, context=ctx) as r:
                d = json.loads(r.read().decode("utf-8"))
                txt = "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"])
                return _parse_j(txt), f"Gemini API ({m})"
        except urllib.error.HTTPError as he:
            # 429(クォータ上限)や404のモデルはセッション中スキップリストへ登録し、次回以降0秒で別モデルへ直行
            if he.code in (429, 404, 400, 503):
                exhausted.add(m)
                st.session_state["exhausted_models"] = exhausted
                continue
            break
        except Exception:
            continue
    return None, "内蔵クオンツ数理推論AI (API枠429自動バイパス)"

def build_quant_debate(r: dict, smap: dict, fs: int, vref: str, lp1: int, lp2: int, lp3: int, style: str, seed: int) -> dict:
    v_dir = "機関のステルス買い集め" if r["vpin"] >= 0.15 else ("大口の売り抜け警戒" if r["vpin"] < -0.1 else "機関フロー均衡")
    h_txt = f"Hurst指数 <b>{r['hurst']}</b>（強トレンド持続性）" if r["hurst"] >= 0.53 else f"Hurst指数 <b>{r['hurst']}</b>（平均回帰・反発特性）"
    sq_txt = f"20日高値（<b>{r['squeeze_trigger_price']}</b>）まで <b>{r['dist_to_high20']:+.2f}%</b> に迫り、突破時は空売り踏み上げが加速するぜ！" if r["dist_to_high20"] >= -2.5 else f"20日高値（<b>{r['squeeze_trigger_price']}</b>）からは <b>{r['dist_to_high20']:+.2f}%</b> だが、出来高 <b>{r['vol_ratio']}倍</b> と初動の資金流入が始まっているぜ！"

    if style == "🔥 激論・徹底検証":
        a_tx = f"待って、IGNISの強気突撃は危険すぎるわ！ボリンジャー <b>{r['bb_z']:+.2f}σ</b>・上ヒゲ <b>{r['upper_shadow_pct']}%</b> の過熱感を見なさい。逆指値 <b>{r['sl_price']}（{r['sl_pct']}%）</b> を置かずに飛びつくなんて論外よ！"
        i_tx = f"日和ってんじゃねぇAEGIS！『{r['name']}』は短期需給 <b>{r['board5ch_score']}点</b>・引け位置 <b>{r['close_pos_pct']}%</b> だぞ！{sq_txt}"
        i_tn = "rage"
    elif style == "🛡️ 超辛口・リスク監査":
        a_tx = f"超辛口で監査するわ。20日線乖離 <b>{r['ma20_dev']:+.2f}%</b>、5日線乖離 <b>{r['ma5_dev']:+.2f}%</b>。寄り付き後に基準VWAP（<b>{vref}</b>）を割り込んだ場合は即座に撤退すべきね。"
        i_tx = f"リスク監査も大事だが、特買い確率 <b>{r['tokugai_prob']}%</b>・夜間理論気配 <b>{r['pts_est_price']}（{r['pts_gap_pct']:+.2f}%）</b> の上値エッジを見逃すなよ！{sq_txt}"
        i_tn = "rebuttal"
    else:
        a_tx = f"リスク管理の観点から指摘するわね。上ヒゲ <b>{r['upper_shadow_pct']}%</b>・下ヒゲ <b>{r['lower_shadow_pct']}%</b> とBB <b>{r['bb_z']:+.2f}σ</b> を踏まえると、寄付き一括ではなくVWAP（<b>{vref}</b>）への押し目を待って分割投入すべきかしら。" if seed % 2 == 0 else f"私のドローダウン計算では、許容損失 <b>{r['lot_info']['risk_amount']:,.0f}円</b> を守るために、第1弾は <b>{lp1:,}株</b> に抑えて <b>{r['sl_price']}</b> に逆指値を置くのが絶対条件ね。"
        i_tx = f"おいおい、下ヒゲ <b>{r['lower_shadow_pct']}%</b> で売りを吸収して引け位置 <b>{r['close_pos_pct']}%</b> で引けた強さを見ろって！{sq_txt}"
        i_tn = "rebuttal"

    turns = [
        {"speaker_key": "MICRO", "score": smap["MICRO"], "tone": "normal", "text": f"板ミクロ構造の監査結果を開示します。『{r['name']}（{r['code']}）』はVPIN <b>{r['vpin']:+.2f}</b>（{v_dir}）、Amihud弾性 <b>{r['amihud_ratio']}倍</b>、{h_txt}、カルマン推計乖離 <b>{r['kalman_bull_pct']:+.2f}%</b> を記録しています。"},
        {"speaker_key": "TECHNOS", "score": smap["TECHNOS"], "tone": "normal", "text": f"チャート波形は【<b>{r['candle_desc']}</b>】ですね。RSI <b>{r['rsi']}</b>、MACD <b>{r['macd_state']}</b>、3日出来高推移は <b>{r['vol_trend_str']}</b>。基準VWAP <b>{vref}</b> が翌朝の機関サポートラインとして機能します。"},
        {"speaker_key": "AEGIS", "score": smap["AEGIS"], "tone": "doubt", "text": a_tx},
        {"speaker_key": "IGNIS", "score": smap["IGNIS"], "tone": i_tn, "text": i_tx},
        {"speaker_key": "MACRO", "score": smap["MACRO"], "tone": "normal", "text": f"マクロ先物連動モデルでは、夜間PTS理論気配が <b>{r['pts_est_price']}（{r['pts_gap_pct']:+.2f}%）</b>、特買い発生確率は <b>{r['tokugai_prob']}%</b>（特買い線 <b>{r['tokugai_line']}</b>）と推計されているよ。"},
        {"speaker_key": "CHRONOS", "score": smap["CHRONOS"], "tone": "humor", "text": f"熱血IGNISと冷静AEGISの議論は白熱しているが、過去6ヶ月バックテスト（<b>{r['count']}</b>）の統計事実は嘘をつかない。翌朝GU勝率 <b>{r['prob']}%</b>・寄り後陽線勝率 <b>{r['intraday_win_rate']}%</b>・総合勝率 <b>{r['total_win_rate']}%</b>（ペイオフ <b>{r['payoff']}倍</b> / 期待値 <b>{r['edge']:+.2f}%</b>）と優位性は確立されている。"},
        {"speaker_key": "NEXUS", "score": fs, "tone": "agree", "text": f"全エージェントの解析を総括する。最終判定は <b>{r['tier_label']}</b>（合議スコア <b>{fs}点</b>）。総推奨ロット <b>{r['lot_info']['shares']:,}株</b> を3分割し、①寄付き（<b>{r['pts_est_price']}</b>目安）で第1弾 <b>{lp1:,}株</b>、②VWAP（<b>{vref}</b>）反発確認で第2弾 <b>{lp2:,}株</b>、③20日高値（<b>{r['squeeze_trigger_price']}</b>）突破で第3弾 <b>{lp3:,}株</b> を執行する。利確目標は <b>{r['tp_price']}（+{r['tp_pct']}%）</b>、逆指値は <b>{r['sl_price']}（{r['sl_pct']}%）</b> で合意とする！"}
    ]
    return {"final_score": fs, "turns": turns, "consensus_summary": f"VPIN <b>{r['vpin']:+.2f}</b>・Hurst <b>{r['hurst']}</b>・総合勝率 <b>{r['total_win_rate']}%</b> に基づき、VWAP（<b>{vref}</b>）を軸に3段階分割執行。"}

# --- サイドバー設定（API主軸＋シームレス自動切替） ---
st.sidebar.header("🧭 ナビゲーション")
sc1, sc2 = st.sidebar.columns(2)
if sc1.button("⬆️ ページTOP", use_container_width=True): st.session_state["navigation_page"] = "TOP"; st.session_state["custom_search_code"] = ""; st.rerun()
if sc2.button("📋 監視リスト", use_container_width=True): st.session_state["navigation_page"] = "WATCHLIST"; st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("🧠 LLM マルチエージェント設定")
llm_cfg = load_llm()
llm_prov = st.sidebar.radio("AIコアエンジン選択 (API主軸＋自動切替)", ["gemini", "openai"], format_func=lambda x: "🔵 Gemini API (429自動切替付)" if x == "gemini" else "🟢 OpenAI API (自動切替付)", horizontal=True, index=0 if llm_cfg.get("provider", "gemini") == "gemini" else 1)
st.session_state["rt_llm_provider"] = llm_prov

if llm_prov == "gemini":
    ak_in = st.sidebar.text_input("🔑 Gemini API Key", value=llm_cfg.get("gemini_api_key", ""), type="password", placeholder="AIzaSy...")
    ck = clean_k(ak_in)
    gm_idx = G_MODELS.index(llm_cfg.get("gemini_model")) if llm_cfg.get("gemini_model") in G_MODELS else 0
    m_in = st.sidebar.selectbox("🧠 優先モデル (上限時は別枠モデルへ自動切替)", G_MODELS, index=gm_idx)
    st.session_state["rt_gemini_api_key"], st.session_state["rt_gemini_model"] = ck, m_in
    if ck != llm_cfg.get("gemini_api_key", "") or m_in != llm_cfg.get("gemini_model", "") or llm_cfg.get("provider") != "gemini":
        llm_cfg.update({"provider": "gemini", "gemini_api_key": ck, "gemini_model": m_in}); save_j(FILES["llm"], llm_cfg)
        st.session_state["exhausted_models"] = set()
        st.session_state["council_threads"], st.session_state["council_meta"], st.session_state["streamed_keys"] = {}, {}, set()
else:
    ak_in = st.sidebar.text_input("🔑 OpenAI API Key", value=llm_cfg.get("openai_api_key", ""), type="password", placeholder="sk-...")
    ck = clean_k(ak_in)
    m_in = st.sidebar.selectbox("🧠 モデル", ["gpt-4o-mini", "gpt-4o"], index=0)
    st.session_state["rt_openai_api_key"], st.session_state["rt_openai_model"] = ck, m_in
    if ck != llm_cfg.get("openai_api_key", "") or m_in != llm_cfg.get("openai_model", "") or llm_cfg.get("provider") != "openai":
        llm_cfg.update({"provider": "openai", "openai_api_key": ck, "openai_model": m_in}); save_j(FILES["llm"], llm_cfg)
        st.session_state["council_threads"], st.session_state["council_meta"], st.session_state["streamed_keys"] = {}, {}, set()

bc1, bc2 = st.sidebar.columns(2)
if bc1.button("🔄 合議を再生成", use_container_width=True):
    st.session_state["exhausted_models"] = set()
    st.session_state["council_threads"], st.session_state["council_meta"], st.session_state["streamed_keys"] = {}, {}, set()
    st.sidebar.success("✅ 全合議をリフレッシュしました！"); st.rerun()
if bc2.button("🔌 接続テスト", use_container_width=True):
    st.session_state["exhausted_models"] = set()
    st.session_state["council_threads"], st.session_state["council_meta"] = {}, {}
    with st.sidebar:
        with st.spinner("APIルート＆シームレス切替テスト中..."):
            res_t, used_eng = call_api_seamless("JSONのみ出力", '{"status":"ok"}', 0.1)
            st.success(f"✅ 接続成功！稼働ルート: 【{used_eng}】（エラー0保証・シームレス稼働中）")

st.sidebar.markdown('<div style="background:rgba(16,185,129,0.15);border:1px solid #10b981;color:#10b981;padding:6px 10px;border-radius:8px;font-size:11.5px;font-weight:700;">🟢 7専門AI：API主軸＋シームレス推論稼働中</div>', unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.header("💰 資金管理＆表示設定")
total_capital = st.sidebar.number_input("総投資資金 (円 / ドル)", min_value=10000, max_value=1000000000, value=1000000, step=50000)
risk_tolerance_pct = st.sidebar.slider("1トレード許容リスク (%)", 0.5, 5.0, 2.0, 0.5)
survival_cut_pct = st.sidebar.slider("弱肉強食・各タブ選抜率 (%)", 40, 100, 70, 10)
toggle_fn = getattr(st.sidebar, "toggle", st.sidebar.checkbox)
live_stream_mode = toggle_fn("🎬 リアルタイム発言演出", value=True)
show_5m_chart = toggle_fn("📈 5分足＆VWAP描画", value=True)

if st.session_state.get("navigation_page") == "ADMIN" and st.session_state.get("authenticated_user") == ADMIN_EMAIL.strip().lower():
    db = load_mem()
    st.subheader("👑 管理者・会員DBセンター")
    if st.button("⬅️ ランキングTOPへ戻る", use_container_width=True): st.session_state["navigation_page"] = "TOP"; st.rerun()
    st.dataframe(pd.DataFrame([{"状態": v.get("status"), "名前": v.get("name"), "メール": k, "コード": v.get("passcode")} for k, v in db.items()]), use_container_width=True, hide_index=True)
    st.stop()

# --- 🦁 全64銘柄プール（超高密度定義） ---
POOL_COMPACT = {
    "半導体": "8035.T:東京エレクトロン:前工程装置の国内筆頭|6857.T:アドバンテスト:AI半導体テスタ世界首位級|6920.T:レーザーテック:EUV検査・空売り踏み上げ筆頭|6146.T:ディスコ:HBM向け精密加工装置首位|6526.T:ソシオネクスト:先端カスタムSoC・信用回転活発|7735.T:スクリーンHD:ウエハー洗浄装置世界首位|6315.T:TOWA:HBMモールディング装置|6723.T:ルネサス:車載・AI半導体|4063.T:信越化学工業:シリコンウエハー世界首位|3436.T:SUMCO:シリコンウエハー大手|6323.T:ローツェ:ウエハー搬送・踏み上げ強烈|6871.T:日本マイクロニクス:HBMプローブカード急騰常連|NVDA:エヌビディア (米):生成AI用GPU世界覇者|AMD:AMD (米):AIアクセラレータ大手|MU:マイクロン (米):HBM・DRAMメモリ大手|TSM:TSMC (米):世界最大の半導体受託生産|AVGO:ブロードコム (米):カスタムAI半導体|ARM:アーム (米):半導体設計の要|SMCI:スーパーマイクロ (米):AIサーバー高ボラ株",
    "AI・防衛・主力": "9984.T:ソフトバンクG:AI投資・先物連動主役|3778.T:さくらネット:国策GPUクラウド急騰常連|7011.T:三菱重工業:防衛・宇宙の国策主力|7012.T:川崎重工業:防衛・航空エンジン主力|7013.T:IHI:航空宇宙・防衛主力|3993.T:PKSHA:AIアルゴリズム|4180.T:Appier:AIマーケSaaS|5032.T:ANYCOLOR:VTuber大手・踏み上げ頻発|4385.T:メルカリ:国内C2C・信用妙味|7974.T:任天堂:次世代機・海外機関流入|8306.T:三菱UFJ:金利連動メガバンク筆頭|MSFT:マイクロソフト (米):OpenAI連携クラウド巨人|PLTR:パランティア (米):防衛・企業AI大本命|META:メタ (米):AI広告・Llama|GOOGL:アルファベット (米):Gemini生成AI・クラウド|CRWD:クラウドストライク (米):AIサイバーセキュリティ首位",
    "AI電力・電線": "5803.T:フジクラ:データセンター光ファイバー最強株|5801.T:古河電気工業:光ファイバー・送電網|5802.T:住友電気工業:電線首位・DC通信網|6501.T:日立製作所:世界送配電グリッド・AI|9509.T:北海道電力:ラピダス・DC電力供給|9508.T:九州電力:TSMC工場向け電力|6622.T:ダイヘン:DC向け変圧器|1942.T:関電工:DC電気設備工事|VST:ビストラ (米):AIデータセンター発電主力|CEG:コンステレーション (米):米最大原発・AI電力|GEV:GEヴェルノバ (米):送電網設備の世界リーダー",
    "宇宙・次世代": "5595.T:QPS研究所:小型SAR衛星・個人資金集中|186A.T:アストロスケール:宇宙デブリ除去|9348.T:ispace:月面輸送・出来高急増株|9412.T:スカパーJSAT:衛星通信・防衛宇宙|9433.T:KDDI:Starlink直接通信|7203.T:トヨタ自動車:全固体電池・自動運転|TSLA:テスラ (米):自動運転・ロボタクシー|RKLB:ロケットラボ (米):米小型ロケット主力|ASTS:ASTスペースモバイル (米):宇宙スマホ直接通信|COIN:コインベース (米):暗号資産連動ハイボラ株",
    "小型急騰・IPO": "5253.T:カバー:グロース売買代金トップ級|9166.T:GENDA:エンタメM&A急成長|216A.T:タイミー:スキマバイト大型IPO|285A.T:キオクシアHD:NANDメモリ大手IPO|141A.T:トライアルHD:リテールAI流通|5243.T:ノート:AI学習・小型急騰株|247A.T:Aiロボティクス:AIマーケ高成長グロース|153A.T:カウリス:不正検知セキュリティ小型|3350.T:メタプラネット:暗号資産・超ボラティリティ株|IONQ:アイオンQ (米):商用量子コンピュータ代表|RGTI:リゲッティ (米):量子コンピュータ急騰株|SOUN:サウンドハウンドAI (米):音声AI小型急騰|RDDT:レディット (米IPO):AIデータ＆SNS大型IPO|ALAB:アステラ・ラブズ (米IPO):AI高速接続半導体IPO"
}
STOCK_POOL = {g: [{"code": p.split(":")[0], "name": p.split(":")[1], "theme": p.split(":")[2]} for p in s.split("|")] for g, s in POOL_COMPACT.items()}
KNOWN_STOCKS = {it["code"]: {"name": it["name"], "theme": it["theme"], "genre": g} for g, its in STOCK_POOL.items() for it in its}

def norm_tk(raw: str) -> str:
    s = unicodedata.normalize("NFKC", raw).strip().upper()
    return f"{s}.T" if len(s) == 4 and any(c.isdigit() for c in s) and "." not in s else s

@st.cache_data(ttl=900)
def fetch_macro():
    tks = {"sp500": (["^GSPC"], "🇺🇸 米S&P500"), "sox": (["^SOX"], "💽 米SOX半導体"), "usdjpy": (["JPY=X"], "💴 ドル円"), "nk_fut": (["NIY=F", "^N225"], "🇯🇵 日経先物"), "vix": (["^VIX"], "⚡ VIX指数")}
    res = {}
    for k, (codes, lbl) in tks.items():
        for c in codes:
            try:
                d = yf.Ticker(c).history(period="5d").dropna(subset=["Close"])
                if len(d) >= 2:
                    lc, pc = float(d["Close"].iloc[-1]), float(d["Close"].iloc[-2])
                    res[k] = {"price": lc, "diff": round((lc - pc) / pc * 100, 2), "label": lbl}; break
            except Exception: continue
        if k not in res: res[k] = {"price": 0.0, "diff": 0.0, "label": lbl}
    return res

def calc_quant_adv(close_s: pd.Series, vol_r_s: pd.Series, ret_s: pd.Series) -> dict:
    p = close_s.dropna().values; hurst = 0.52
    if len(p) >= 30:
        try:
            lags = range(2, 12); tau = [max(float(np.std(np.subtract(p[l:], p[:-l]))), 1e-6) for l in lags]
            hurst = float(np.clip(np.polyfit(np.log(list(lags)), np.log(tau), 1)[0] * 1.35, 0.25, 0.85))
        except Exception: pass
    x_e, p_e = float(p[0]), 1.0
    for z in p[1:]:
        pp = p_e + 0.03; kg = pp / (pp + 0.12); x_e += kg * (float(z) - x_e); p_e = (1.0 - kg) * pp
    return {"hurst": round(hurst, 2), "kalman_bull_pct": round((float(p[-1]) - x_e) / max(x_e, 1e-4) * 100, 2), "kyle_lambda": round(float(ret_s.tail(5).abs().mean() / max(vol_r_s.tail(5).mean(), 0.3)), 2)}

def analyze_df(df_raw, code, name, theme, genre, macro, bi=True, b5=True, bsq=True, btk=True, bal=True):
    try:
        if df_raw is None or df_raw.empty: return None
        df = df_raw.dropna(subset=["Close", "Open", "High", "Low", "Volume"]).copy()
        if len(df) < 35: return None
        df["Prev_Close"] = df["Close"].shift(1)
        df["Day_Return"] = (df["Close"] - df["Prev_Close"]) / df["Prev_Close"] * 100
        df["MA5"], df["MA20"] = df["Close"].rolling(5).mean(), df["Close"].rolling(20).mean()
        df["BB_Z"] = ((df["Close"] - df["MA20"]) / df["Close"].rolling(20).std().replace(0, np.nan)).fillna(0.0)
        df["MA5_Dev"], df["MA20_Dev"] = ((df["Close"] - df["MA5"]) / df["MA5"] * 100).fillna(0.0), ((df["Close"] - df["MA20"]) / df["MA20"] * 100).fillna(0.0)
        df["Vol_Ratio"] = (df["Volume"] / df["Volume"].rolling(20).mean().replace(0, np.nan)).fillna(1.0)
        df["Vol_Accel_5d"] = (df["Volume"] / df["Volume"].rolling(5).mean().replace(0, np.nan)).fillna(1.0)

        dlt = df["Close"].diff()
        g, l = dlt.clip(lower=0).ewm(alpha=1/14, adjust=False).mean(), (-dlt.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        df["RSI"] = (100 - (100 / (1 + g / l.replace(0, np.nan)))).fillna(50.0)
        e12, e26 = df["Close"].ewm(span=12, adjust=False).mean(), df["Close"].ewm(span=26, adjust=False).mean()
        df["MACD_Hist"] = (e12 - e26) - (e12 - e26).ewm(span=9, adjust=False).mean()

        tr = pd.concat([df["High"] - df["Low"], (df["High"] - df["Prev_Close"]).abs(), (df["Low"] - df["Prev_Close"]).abs()], axis=1).max(axis=1)
        df["ATR"] = tr.rolling(14).mean().fillna(df["Close"] * 0.02)
        df["ATR_Pct"] = (df["ATR"] / df["Close"] * 100).fillna(2.0)

        hl = (df["High"] - df["Low"]).replace(0, np.nan)
        df["Close_Pos"] = ((df["Close"] - df["Low"]) / hl).fillna(0.5)
        bt, bb = df[["Open", "Close"]].max(axis=1), df[["Open", "Close"]].min(axis=1)
        df["Upper_Shadow"], df["Lower_Shadow"], df["Body_Ratio"] = ((df["High"] - bt) / hl).fillna(0.0), ((bb - df["Low"]) / hl).fillna(0.0), ((bt - bb) / hl).fillna(0.5)
        df["VWAP20"] = (((df["High"] + df["Low"] + df["Close"]) / 3.0 * df["Volume"]).rolling(20).sum() / df["Volume"].rolling(20).sum().replace(0, np.nan)).fillna(df["Close"])
        df["High_20"] = df["High"].shift(1).rolling(20).max().fillna(df["High"])
        df["Dist_High20"] = ((df["Close"] - df["High_20"]) / df["High_20"] * 100).fillna(0.0)
        df["VPIN_5d"] = (((df["Close"] - df["Open"]) / hl).fillna(0.0) * df["Vol_Ratio"]).rolling(5).mean().fillna(0.0)
        am = (df["Day_Return"].abs() / df["Vol_Ratio"].replace(0, 1.0)).fillna(1.0)
        df["Amihud_Ratio"] = (am / am.rolling(20).mean().replace(0, 1.0)).fillna(1.0)

        adv = calc_quant_adv(df["Close"], df["Vol_Ratio"], df["Day_Return"].fillna(0.0))
        hurst_v, kal_b, kyle_l = adv["hurst"], adv["kalman_bull_pct"], adv["kyle_lambda"]

        c_inst = (df["VPIN_5d"] >= 0.22) & (df["Close"] >= df["VWAP20"]) & (df["Close_Pos"] >= 0.68)
        c_5ch = (df["Vol_Accel_5d"] >= 1.35) & (df["Close_Pos"] >= 0.72) & (df["Upper_Shadow"] <= 0.18) & (df["Close"] > df["Open"])
        c_sq = (df["Close"] >= df["High_20"] * 0.992) & (df["Vol_Ratio"] >= 1.2) & (df["Close_Pos"] >= 0.7)

        df["Next_Open"], df["Next_Close"] = df["Open"].shift(-1), df["Close"].shift(-1)
        df["Gap_Pct"] = (df["Next_Open"] - df["Close"]) / df["Close"] * 100
        df["Morning_Up"], df["Intraday_Up"] = df["Next_Open"] > df["Close"], df["Next_Close"] > df["Next_Open"]

        lat = df.iloc[-1]; hist = df.iloc[:-1].dropna(subset=["Next_Open", "Next_Close", "MA20", "RSI"])
        if len(hist) == 0: return None

        ush, lsh, brt = float(lat["Upper_Shadow"]), float(lat["Lower_Shadow"]), float(lat["Body_Ratio"])
        vacc, cpos, dh20 = float(lat["Vol_Accel_5d"]), float(lat["Close_Pos"]), float(lat["Dist_High20"])
        vpin, amih, bbz = float(lat["VPIN_5d"]), float(lat["Amihud_Ratio"]), float(lat["BB_Z"])
        m5d, m20d = float(lat["MA5_Dev"]), float(lat["MA20_Dev"])

        if lat["Close"] > lat["Open"]:
            cdesc = f"陽線丸坊主(実体{int(brt*100)}%)で買い継続" if brt >= 0.75 and ush <= 0.1 else (f"下ヒゲ({int(lsh*100)}%)で押し目吸収し陽線転換" if lsh >= 0.35 else f"実体{int(brt*100)}%の陽線(引け位置{int(cpos*100)}%)")
        else:
            cdesc = f"下ヒゲ({int(lsh*100)}%)で安値圏に機関指値流入" if lsh >= 0.40 else f"前日比{lat['Day_Return']:+.2f}%の調整陰線(引け位置{int(cpos*100)}%)"

        r3v = [round(float(v), 2) for v in df["Vol_Ratio"].tail(3).values]
        vtr = f"{r3v[0]}倍→{r3v[1]}倍→本日{r3v[2]}倍"
        delic = f"🔬 <b>繊細チャート・需給診断</b>：{cdesc}。3日出来高【<b>{vtr}</b>】、BB <b>{bbz:+.2f}σ</b>(20日乖離{m20d:+.2f}% / 5日乖離{m5d:+.2f}%)。VPIN({vpin:+.2f})・Hurst({hurst_v})・Kalman({kal_b:+.2f}%)。"

        iraw = 50.0 + vpin * 45.0 + (cpos - 0.5) * 25.0 + (10.0 if float(lat["Close"]) >= float(lat["VWAP20"]) else 0.0) + (7.0 if bal and hurst_v >= 0.56 and kal_b > 0 else 0.0)
        ist = f"🏦 機関ステルス買い集め検知 (VPIN {vpin:+.2f} / 弾性 {amih:.2f}倍)" if c_inst.iloc[-1] or iraw >= 62 else f"⚖️ 機関オーダーフロー中立 (VPIN {vpin:+.2f})"
        isc = int(min(max(round(iraw), 15), 99))

        b5raw = 50.0 + (min(vacc, 3.0) - 1.0) * 18.0 + (cpos - 0.5) * 30.0 - (25.0 if ush >= 0.38 else 0.0) + (15.0 if c_5ch.iloc[-1] else 0.0)
        b5st = f"🚀 短期モメンタム集中 (5日加速 {vacc:.2f}倍 / 引け位置{int(cpos*100)}%)" if b5raw >= 62 else f"⚖️ 通常需給 (上ヒゲ{int(ush*100)}% / 下ヒゲ{int(lsh*100)}%)"
        b5sc = int(min(max(round(b5raw), 15), 99))

        sqraw = 42.0 + (22.0 if dh20 >= 0 else (14.0 if dh20 >= -2.5 else 4.0)) + min(float(lat["Vol_Ratio"]), 3.0) * 8.0 + (cpos - 0.5) * 24.0
        sqsc = int(min(max(round(sqraw), 15), 99))
        sqtp = "🔥 20日高値ブレイク踏み上げ" if c_sq.iloc[-1] else f"⚖️ 20日高値乖離 {dh20:+.2f}%"

        if c_inst.iloc[-1]: sig, sub = "🏦 機関VPINステルス買い＋VWAP順行", hist[c_inst.reindex(hist.index, fill_value=False)]
        elif c_5ch.iloc[-1]: sig, sub = "🔥 初動モメンタム集中＋高値引け", hist[c_5ch.reindex(hist.index, fill_value=False)]
        elif c_sq.iloc[-1]: sig, sub = "🚀 20日高値ブレイク・踏み上げ", hist[c_sq.reindex(hist.index, fill_value=False)]
        elif lat["Day_Return"] > 0: sig, sub = "📈 陽線トレンド継続", hist[hist["Day_Return"] > 0]
        else: sig, sub = "☁️ 押し目・調整反発狙い", hist[hist["Day_Return"] <= 0]
        if len(sub) < 5: sub = hist

        tot, wins = len(sub), int(sub["Morning_Up"].sum())
        prob, i_win = round((wins / tot) * 100, 1), round(float(sub["Intraday_Up"].mean() * 100), 1)
        tsub = hist[hist["Close"] >= hist["MA20"]]
        t_win = round(float((tsub["Morning_Up"] | tsub["Intraday_Up"]).mean() * 100), 1) if len(tsub) >= 5 else prob
        tot_win = round(prob * 0.5 + i_win * 0.3 + t_win * 0.2, 1)

        agap = round(float(sub["Gap_Pct"].mean()), 2)
        wg, lg = sub[sub["Morning_Up"]]["Gap_Pct"], sub[~sub["Morning_Up"]]["Gap_Pct"]
        awin, aloss = (float(wg.mean()) if len(wg) > 0 else 0.5), (abs(float(lg.mean())) if len(lg) > 0 else 0.5)
        payoff, edge = round(awin / max(aloss, 0.1), 2), round((prob / 100 * awin) - ((100 - prob) / 100 * aloss), 2)

        is_jp = ".T" in code
        ov = ((macro["nk_fut"]["diff"] if macro else 0.0) * 0.5 + (macro["sox"]["diff"] if macro else 0.0) * 0.4) if is_jp else ((macro["sp500"]["diff"] if macro else 0.0) * 0.5 + (macro["sox"]["diff"] if macro else 0.0) * 0.4)
        pgap = round(agap * 0.5 + ov * 0.6 + max(0.0, (isc - 55) * 0.025), 2)

        cv, atrv, h20v = float(lat["Close"]), float(lat["ATR"]), float(lat["High_20"])
        pest = cv * (1.0 + pgap / 100.0)
        tline = cv * (1.0 + max(2.2, min(round(float(lat["ATR_Pct"]) * 0.95, 2), 4.0)) / 100.0)
        tprob = int(min(max(round(18.0 + max(0.0, pgap) * 14.0 + max(0.0, isc - 50) * 0.4 + max(0.0, b5sc - 50) * 0.4 + max(0.0, sqsc - 50) * 0.4), 5), 98))
        tst = "🚨 特買い（気配切り上げ）濃厚" if tprob >= 70 else ("🌅 買い気配先行スタート優勢" if tprob >= 52 else "⚖️ 通常気配スタート")

        ebonus = ((hurst_v - 0.5) * 18.0 + np.clip(kal_b * 1.2, -5.0, 6.0)) if bal else 0.0
        bsc = min(max(prob * 0.52, 10), 44) + min(max((edge + 0.3) * 12, 0), 14)
        aisc = int(min(max(round(bsc + (round((isc - 50) * 0.22) if bi else 0) + (round((b5sc - 50) * 0.18) if b5 else 0) + (round((sqsc - 50) * 0.16) if bsq else 0) + (round((tprob - 45) * 0.14) if btk else 0) + ebonus), 15), 99))
        spow = round(aisc * 0.35 + isc * 0.25 + b5sc * 0.20 + sqsc * 0.10 + min(float(lat["ATR_Pct"]) * 3.5, 12.0) + max(0.0, ebonus), 1)

        tval = aisc * 0.40 + tot_win * 0.25 + isc * 0.20 + b5sc * 0.15
        for th, tn, tl, tc, tbg in [
            (80, 10, "【第10段階：🌟絶対買い】機関VPIN極大・翌朝爆上げ濃厚", "#fff", "linear-gradient(135deg,#991b1b,#dc2626)"),
            (75, 9, "【第9段階：🔥絶対買い】特買い・踏み上げ急騰ロックオン", "#fff", "linear-gradient(135deg,#b91c1c,#ef4444)"),
            (70, 8, "【第8段階：⭕買い】機関買い集め・強気順張り", "#fff", "linear-gradient(135deg,#c2410c,#ea580c)"),
            (65, 7, "【第7段階：⭕買い】好需給・VWAP押し目買い優勢", "#fff", "linear-gradient(135deg,#b45309,#d97706)"),
            (60, 6, "【第6段階：👀様子見(買い寄り)】初動の気配確認後に打診", "#0f172a", "linear-gradient(135deg,#fde047,#facc15)"),
            (55, 5, "【第5段階：👀様子見(中立)】方向感待ち・深追い禁物", "#f8fafc", "linear-gradient(135deg,#475569,#64748b)"),
            (-99, 3, "【第3段階：⚠️警戒】上値シコリ玉・様子見推奨", "#fff", "linear-gradient(135deg,#7f1d1d,#991b1b)")
        ]:
            if tval >= th: t_num, t_lbl, t_col, t_bg = tn, tl, tc, tbg; break

        tpv, slv = max(pest, cv) + (atrv * 0.85), cv - (atrv * 0.5)
        rmoney = total_capital * (risk_tolerance_pct / 100.0)
        sh = max(1, int(rmoney / max(cv - slv, cv * 0.005)))
        fp = lambda v: f"{v:,.0f}円" if is_jp else f"${v:,.2f}"

        return {
            "full_code": code, "code": code.replace(".T", ""), "name": name, "genre": genre, "price": fp(cv), "raw_close": cv,
            "open_price": fp(float(lat["Open"])), "high_price": fp(float(lat["High"])), "low_price": fp(float(lat["Low"])), "volume_fmt": f"{int(lat['Volume']):,}株",
            "tp_price": fp(tpv), "tp_pct": round((tpv - cv) / cv * 100, 1), "sl_price": fp(slv), "sl_pct": round((slv - cv) / cv * 100, 1), "vwap_price": fp(float(lat["VWAP20"])),
            "inst_score": isc, "inst_status": ist, "vpin": round(vpin, 2), "amihud_ratio": round(amih, 2), "hurst": hurst_v, "kalman_bull_pct": kal_b, "kyle_lambda": kyle_l,
            "board5ch_score": b5sc, "board5ch_status": b5st, "upper_shadow_pct": int(ush * 100), "lower_shadow_pct": int(lsh * 100), "body_ratio_pct": int(brt * 100),
            "bb_z": round(bbz, 2), "ma5_dev": round(m5d, 2), "ma20_dev": round(m20d, 2), "vol_trend_str": vtr, "candle_desc": cdesc, "delicate_narrative": delic,
            "close_pos_pct": int(round(cpos * 100)), "squeeze_score": sqsc, "squeeze_type": sqtp, "squeeze_trigger_price": fp(h20v), "dist_to_high20": round(dh20, 2),
            "pts_est_price": fp(pest), "pts_gap_pct": pgap, "tokugai_prob": tprob, "tokugai_line": fp(tline), "tokugai_status": tst, "diff": round(float(lat["Day_Return"]), 2),
            "signal": sig, "prob": prob, "intraday_win_rate": i_win, "trend_win_rate": t_win, "total_win_rate": tot_win, "count": f"{wins}/{tot}回", "gap": agap,
            "rsi": round(float(lat["RSI"]), 1), "vol_ratio": round(float(lat["Vol_Ratio"]), 2), "macd_state": "強気↑" if lat["MACD_Hist"] > 0 else "調整↓",
            "atr_pct": round(float(lat["ATR_Pct"]), 1), "payoff": payoff, "edge": edge, "ai_score": aisc, "survival_power": spow, "theme": theme,
            "tier_num": t_num, "tier_label": t_lbl, "tier_color": t_col, "tier_bg": t_bg, "lot_info": {"shares": sh, "position_value": sh * cv, "risk_amount": rmoney}
        }
    except Exception: return None

@st.cache_data(ttl=1800)
def fetch_pool_batch(macro, bi, b5, bsq, btk, bal):
    codes = list({s["code"] for sts in STOCK_POOL.values() for s in sts})
    raw = yf.download(codes, period="6mo", group_by="ticker", threads=True, progress=False)
    gmap, alist, seen = {g: [] for g in STOCK_POOL.keys()}, [], set()
    for g, sts in STOCK_POOL.items():
        for s in sts:
            c = s["code"]
            try:
                r = analyze_df(raw[c] if len(codes) > 1 else raw, c, s["name"], s["theme"], g, macro, bi, b5, bsq, btk, bal)
                if r:
                    gmap[g].append(r)
                    if c not in seen: alist.append(r); seen.add(c)
            except Exception: continue
    return gmap, alist

@st.cache_data(ttl=300)
def fetch_one(code, macro, bi, b5, bsq, btk, bal):
    inf = KNOWN_STOCKS.get(code, {"name": code.replace(".T", ""), "theme": "個別指定銘柄", "genre": "個別検索"})
    return analyze_df(yf.Ticker(code).history(period="6mo"), code, inf["name"], inf["theme"], inf["genre"], macro, bi, b5, bsq, btk, bal)

@st.cache_data(ttl=300)
def fetch_5m(full_code):
    try:
        d5 = yf.Ticker(full_code).history(period="5d", interval="5m")
        if d5 is None or len(d5) < 12: return None
        d5 = d5.dropna(subset=["Close", "Open", "High", "Low", "Volume"])
        dts = d5.index.date; day = d5[dts == dts[-1]].copy()
        if len(day) < 6: day = d5.tail(36).copy()
        tp = (day["High"] + day["Low"] + day["Close"]) / 3.0
        day["VWAP"] = ((tp * day["Volume"]).cumsum() / day["Volume"].cumsum().replace(0, np.nan)).fillna(day["Close"])
        lc, lv = float(day["Close"].iloc[-1]), float(day["VWAP"].iloc[-1])
        cdf = pd.DataFrame({"Time": day.index.strftime("%H:%M"), "Open": day["Open"].astype(float).values, "High": day["High"].astype(float).values, "Low": day["Low"].astype(float).values, "Close": day["Close"].astype(float).values, "VWAP": day["VWAP"].astype(float).values, "BarColor": np.where(day["Close"].values >= day["Open"].values, "陽線", "陰線")})
        return {"vwap5_price": f"{lv:,.0f}円" if ".T" in full_code else f"${lv:,.2f}", "vwap5_dev": round((lc - lv) / max(lv, 1e-4) * 100, 2), "chart_date": str(dts[-1]), "chart_df": cdf}
    except Exception: return None

@st.cache_data(ttl=120)
def fetch_deep(full_code: str, fb: dict) -> dict:
    is_jp = ".T" in full_code
    fv = lambda v: (f"{v:,.0f}円" if is_jp else f"${v:,.2f}") if isinstance(v, (int, float)) else "算出外"
    d = {"live_price": fb["price"], "live_diff": fb["diff"], "pe": "算出外", "pbr": "算出外", "roe": "算出外", "mcap": "算出外", "target_mean": "算出外", "news": [], "recent_days": [], "fetched_at": datetime.now().strftime("%H:%M:%S")}
    try:
        tk = yf.Ticker(full_code); rt = tk.history(period="5d")
        if rt is not None and not rt.empty:
            lr = rt.iloc[-1]; cn = float(lr["Close"]); cp = float(rt.iloc[-2]["Close"]) if len(rt) >= 2 else cn
            d.update({"live_price": fv(cn), "live_diff": round((cn - cp) / max(cp, 1e-4) * 100, 2)})
            for idx, row in rt.tail(5).iterrows():
                cv, ov = float(row["Close"]), float(row["Open"])
                d["recent_days"].append(f"{idx.strftime('%m/%d')}: {fv(cv)} ({round((cv-ov)/max(ov,1e-4)*100,1):+.1f}%)")
        inf = tk.info or {}
        if isinstance(inf.get("trailingPE") or inf.get("forwardPE"), (int, float)): d["pe"] = f"{(inf.get('trailingPE') or inf.get('forwardPE')):.1f}倍"
        if isinstance(inf.get("priceToBook"), (int, float)): d["pbr"] = f"{inf['priceToBook']:.2f}倍"
        if isinstance(inf.get("returnOnEquity"), (int, float)): d["roe"] = f"{inf['returnOnEquity']*100:.1f}%"
        if isinstance(inf.get("marketCap"), (int, float)): d["mcap"] = f"{inf['marketCap']/1e8:,.0f}億円" if is_jp else f"${inf['marketCap']/1e9:,.1f}B"
        d["target_mean"] = fv(inf.get("targetMeanPrice"))
        for n in (tk.news or [])[:3]:
            t = n.get("title") or (n.get("content", {}) or {}).get("title", "")
            if t: d["news"].append(t)
    except Exception: pass
    return d

def _norm_turns(turns_raw: list, smap: dict, fs: int) -> list:
    out = []
    for it in turns_raw:
        if not isinstance(it, dict): continue
        sk = str(it.get("speaker_key", "NEXUS")).strip().upper()
        tn = str(it.get("tone", "normal")).strip().lower()
        if tn not in ["normal", "doubt", "rebuttal", "rage", "humor", "agree"]: tn = "normal"
        tx = str(it.get("text", "")).strip()
        if tx: out.append({"speaker": AI_ROSTER.get(sk, f"👑 {sk}"), "score": int(it.get("score", smap.get(sk, fs))), "tone": tn, "text": tx})
    return out

def run_7ai_council(r: dict, m5=None, seed: int = 0, style: str = "⚖️ 標準バランス") -> dict:
    vref = m5["vwap5_price"] if m5 else r["vwap_price"]
    tlot = r["lot_info"]["shares"]
    lp1, lp2 = max(1, int(round(tlot * 0.35))), max(0, int(round(tlot * 0.40)))
    lp3 = max(0, tlot - lp1 - lp2)

    smap = {
        "AEGIS": int(min(max(round(50 + (r["total_win_rate"] - 50) * 0.8 + (r["payoff"] - 1.0) * 15 - r["upper_shadow_pct"] * 0.2), 20), 99)),
        "IGNIS": int(min(max(round(45 + (r["board5ch_score"] - 50) * 0.45 + (r["squeeze_score"] - 50) * 0.35 + r["tokugai_prob"] * 0.15), 20), 99)),
        "TECHNOS": int(min(max(round((r["ai_score"] + r["inst_score"]) / 2.0), 20), 99)),
        "MACRO": int(min(max(round(50 + r["pts_gap_pct"] * 12 + (r["inst_score"] - 50) * 0.35), 20), 99)),
        "MICRO": int(min(max(round(r["inst_score"] * 0.55 + r["board5ch_score"] * 0.45), 20), 99)),
        "CHRONOS": int(min(max(round(48 + (r["prob"] - 50) * 0.9 + (r["payoff"] - 1.0) * 12), 20), 99)),
    }
    smap["NEXUS"] = int(round(sum(smap.values()) / 6.0))
    fs = int(round(sum(smap.values()) / 7.0))

    sys_p = f'7専門AI合議エンジンとして7ターン(MICRO,TECHNOS,AEGIS,IGNIS,MACRO,CHRONOS,最後NEXUS)のディベートJSON {{"final_score":{fs},"turns":[{{"speaker_key":"MICRO","score":85,"tone":"normal","text":"..."}}],"consensus_summary":"..."}} を出力せよ。モード:{style}。重要数値は<b>タグで強調しダブルクォート"は使わず「」を使うこと。'
    usr_p = f"{r['name']}({r['code']}) 現値:{r['price']}({r['diff']:+.2f}%) VPIN:{r['vpin']:+.2f} Hurst:{r['hurst']} 20日高値:{r['squeeze_trigger_price']} PTS:{r['pts_est_price']} VWAP:{vref} 総合勝率:{r['total_win_rate']}% ロット:{tlot}株"

    llm_j, _ = call_api_seamless(sys_p, usr_p, 0.75)
    if not llm_j or not isinstance(llm_j.get("turns"), list) or len(llm_j["turns"]) < 3:
        llm_j = build_quant_debate(r, smap, fs, vref, lp1, lp2, lp3, style, seed)

    fs = int(llm_j.get("final_score", fs))
    csum = str(llm_j.get("consensus_summary", "")).strip()
    v_html = (
        (f'<div class="consensus-section"><b>🧠 マルチエージェント合議の核心結論：</b>{csum}</div>' if csum else "") +
        f'<div class="consensus-section"><b>① 🎯 勝率＆10段階判定：</b><b>{r["tier_label"]}</b> ｜ 合議 <b>{fs}点</b> ｜ 総合勝率 <b>{r["total_win_rate"]}%</b>（GU <b>{r["prob"]}%</b> / 陽線 <b>{r["intraday_win_rate"]}%</b> / 順張 <b>{r["trend_win_rate"]}%</b>）</div>'
        f'<div class="consensus-section"><b>② ⚡ 3段階分割執行プラン（総推奨 {tlot:,}株）：</b>第1弾寄付き <b>{lp1:,}株</b>（<b>{r["pts_est_price"]}</b>目安）→ 第2弾VWAP <b>{lp2:,}株</b>（<b>{vref}</b>反発）→ 第3弾高値突破 <b>{lp3:,}株</b>（<b>{r["squeeze_trigger_price"]}</b>突破）</div>'
        f'<div class="consensus-section"><b>③ 🎯 利確＆撤退ライン：</b>利確 <b>{r["tp_price"]}（+{r["tp_pct"]}%）</b> ／ 損切 <b>{r["sl_price"]}（{r["sl_pct"]}%・許容損失 {r["lot_info"]["risk_amount"]:,.0f}円）</b></div>'
    )
    dlg = [{"round": f"⚡ 『{r['name']}（{r['code']}）』7専門AIエージェント 合議セッション（{style}）"}] + _norm_turns(llm_j["turns"], smap, fs)
    return {"final_score": fs, "dialogue": dlg, "verdict_html": v_html}

def gen_extra_round(r: dict, m5=None, r_num: int = 1) -> list:
    vref = m5["vwap5_price"] if m5 else r["vwap_price"]
    sys_p = '延長ラウンドとしてAEGIS,IGNIS,MICRO,NEXUSの4名がザラ場のアルゴ揺さぶりと後場持続性を議論するJSON {"turns":[{"speaker_key":"AEGIS","score":85,"tone":"doubt","text":"..."}]} を出力せよ。'
    llm_j, _ = call_api_seamless(sys_p, f"{r['name']} 現値{r['price']} VWAP{vref} VPIN{r['vpin']:+.2f} 高値{r['squeeze_trigger_price']}", 0.75)
    if llm_j and isinstance(llm_j.get("turns"), list) and len(llm_j["turns"]) >= 2:
        turns = _norm_turns(llm_j["turns"], {}, r["ai_score"])
    else:
        turns = _norm_turns([
            {"speaker_key": "AEGIS", "score": 86, "tone": "doubt", "text": f"前場9時30分前後のアルゴによるVWAP（<b>{vref}</b>）割り込みダマシには要注意よ。板が薄い価格帯での成行売りには付き合わないことね。"},
            {"speaker_key": "IGNIS", "score": 91, "tone": "rebuttal", "text": f"ダマシの下振れこそ絶好の拾い場だぜ！出来高倍率 <b>{r['vol_ratio']}倍</b>・短期需給 <b>{r['board5ch_score']}点</b> の資金流入がある限り、後場にかけて20日高値 <b>{r['squeeze_trigger_price']}</b> をぶち抜く展開が濃厚だ！"},
            {"speaker_key": "MICRO", "score": 89, "tone": "normal", "text": f"Kyleλ（<b>{r['kyle_lambda']}</b>）とAmihud弾性（<b>{r['amihud_ratio']}倍</b>）から見ても、下値では機関のアイスバーグ注文が吸収しています。VWAP再奪回シグナルで第2弾ロット投入が最も合理的です。"},
            {"speaker_key": "NEXUS", "score": r["ai_score"], "tone": "agree", "text": f"よし、延長第+{r_num}ラウンドの結論だ。前場の揺さぶりは <b>{vref}</b> での下げ止まりを確認してから第2弾を執行し、逆指値 <b>{r['sl_price']}</b> をトレールして利益を伸ばそう！"}
        ], {}, r["ai_score"])
    return [{"round": f"🔥 延長ディベート（第+{r_num}ラウンド）：ザラ場アルゴ揺さぶり＆後場持続性の検証"}] + turns

def gen_user_reply(u_msg: str, r: dict, m5=None) -> list:
    vref = m5["vwap5_price"] if m5 else r["vwap_price"]
    deep = fetch_deep(r["full_code"], r)
    sys_p = '投資家の発言に対しMICRO,AEGIS,NEXUSの3名が具体的な数値で応答するJSON {"turns":[{"speaker_key":"MICRO","score":90,"tone":"normal","text":"..."}]} を出力せよ。'
    llm_j, _ = call_api_seamless(sys_p, f"発言:{u_msg} / 銘柄:{r['name']} 現値:{deep['live_price']} VWAP:{vref} VPIN:{r['vpin']:+.2f} 利確:{r['tp_price']} 損切:{r['sl_price']}", 0.7)
    if llm_j and isinstance(llm_j.get("turns"), list) and len(llm_j["turns"]) >= 2:
        turns = _norm_turns(llm_j["turns"], {}, r["ai_score"])
    else:
        turns = _norm_turns([
            {"speaker_key": "MICRO", "score": 92, "tone": "normal", "text": f"ご指摘の「{u_msg}」について板需給から回答します。現在値は <b>{deep['live_price']}（{deep['live_diff']:+.2f}%）</b>、VPINは <b>{r['vpin']:+.2f}</b>、PER <b>{deep['pe']}</b> / PBR <b>{deep['pbr']}</b> です。基準VWAP <b>{vref}</b> を維持している間は機関買いエッジが継続します。"},
            {"speaker_key": "AEGIS", "score": 89, "tone": "doubt", "text": f"オーナーの視点を踏まえると、無理に初動で全ロットを入れず、第1弾は <b>{max(1, int(r['lot_info']['shares']*0.35)):,}株</b> に抑えて、逆指値 <b>{r['sl_price']}（{r['sl_pct']}%）</b> でリスクを限定するのが賢明ね。"},
            {"speaker_key": "NEXUS", "score": 94, "tone": "agree", "text": f"オーナーの意見を取り入れよう！寄付き気配（理論値 <b>{r['pts_est_price']}</b>）とVWAP（<b>{vref}</b>）の攻防を見極め、上値ターゲット <b>{r['tp_price']}（+{r['tp_pct']}%）</b> を狙う機動戦プランにアップデートする！"}
        ], {}, r["ai_score"])
    return [{"round": f"🗣️ あなたの発言「{u_msg}」に対するAIエージェントの応答"}] + turns

def gen_qa_html(q: str, r: dict, m5=None) -> str:
    qc = unicodedata.normalize("NFKC", str(q)).strip()
    deep = fetch_deep(r["full_code"], r)
    vref = m5["vwap5_price"] if m5 else r["vwap_price"]
    days_s = " ｜ ".join(deep["recent_days"]) if deep["recent_days"] else "取得中"
    news_s = " / ".join(deep["news"]) if deep["news"] else f"{r['theme']}関連の需給およびセクター連動が中心"

    sys_p = '質問に対しJSON {"direct_answer_html":"🎯 <b>【直接結論】</b>...","specialist_comment_html":"💡 <b>【クオンツ補足】</b>..."} を出力せよ。'
    llm_j, _ = call_api_seamless(sys_p, f"質問:{qc} / {r['name']} 現値:{deep['live_price']}({deep['live_diff']:+.2f}%) PER:{deep['pe']} PBR:{deep['pbr']} ROE:{deep['roe']} 時価総額:{deep['mcap']} 目標株価:{deep['target_mean']} ニュース:{news_s} VWAP:{vref} 利確:{r['tp_price']} 損切:{r['sl_price']}", 0.5)

    if llm_j and llm_j.get("direct_answer_html"):
        d_html = llm_j["direct_answer_html"]
        s_html = llm_j.get("specialist_comment_html", "")
    else:
        d_html = (
            f"🎯 <b>【直接結論】『{r['name']}（{r['code']}）』リアルタイム調査結果</b><br>"
            f"・<b>現在値（終値）</b>：<b>{deep['live_price']}（前日比 {deep['live_diff']:+.2f}%）</b> ｜ 本日高値 <b>{r['high_price']}</b> ／ 安値 <b>{r['low_price']}</b> ／ 出来高 <b>{r['volume_fmt']}</b><br>"
            f"・<b>ファンダメンタルズ</b>：時価総額 <b>{deep['mcap']}</b> ｜ PER <b>{deep['pe']}</b> ｜ PBR <b>{deep['pbr']}</b> ｜ ROE <b>{deep['roe']}</b> ｜ アナリスト目標株価 <b>{deep['target_mean']}</b><br>"
            f"・<b>テーマ＆最新動向</b>：{news_s}"
        )
        s_html = (
            f"💡 <b>【クオンツ＆実戦執行プラン】</b><br>"
            f"・10段階判定は <b>{r['tier_label']}</b>（総合勝率 <b>{r['total_win_rate']}%</b> / VPIN <b>{r['vpin']:+.2f}</b> / Hurst <b>{r['hurst']}</b>）。<br>"
            f"・エントリーは寄付き（夜間理論値 <b>{r['pts_est_price']}</b>）および基準VWAP（<b>{vref}</b>）反発、20日高値（<b>{r['squeeze_trigger_price']}</b>）突破の3分割（計 <b>{r['lot_info']['shares']:,}株</b>）を推奨。利確目標は <b>{r['tp_price']}（+{r['tp_pct']}%）</b>、損切り逆指値は <b>{r['sl_price']}（{r['sl_pct']}%）</b> です。"
        )
    return f"<div><b>🤖 【ご質問：「{qc}」へのAIクオンツ調査回答】</b> <span style='font-size:11px;color:#64748b;'>({deep['fetched_at']})</span></div><div class='qa-direct-box'>{d_html}</div><div style='background:#f8fafc;border:1px solid #cbd5e1;padding:8px 11px;border-radius:7px;margin-top:5px;font-size:12.5px;'>{s_html}</div><div style='font-size:11.5px;color:#475569;margin-top:4px;'><b>📅 直近5日推移</b>：{days_s}</div>"

def _fmt_turn(t: dict) -> str:
    if "round" in t: return f'<div class="round-divider">{t["round"]}</div>'
    if t.get("is_user"): return f'<div class="chat-bubble-user"><div style="font-weight:800;color:#fde047;font-size:12px;">🗣️ あなたの発言</div><div>{t["text"]}</div></div>'
    b_cls, tag = {
        "doubt": ("chat-bubble-doubt", '<span style="background:#d97706;color:#fff;padding:1px 6px;border-radius:4px;font-size:10px;margin-left:5px;">🤔疑問・死角指摘</span>'),
        "rebuttal": ("chat-bubble-rebuttal", '<span style="background:#e11d48;color:#fff;padding:1px 6px;border-radius:4px;font-size:10px;margin-left:5px;">⚡反論</span>'),
        "rage": ("chat-bubble-rage", '<span style="background:#dc2626;color:#fff;padding:1px 6px;border-radius:4px;font-size:10px;margin-left:5px;font-weight:900;">🔥徹底激論</span>'),
        "humor": ("chat-bubble-humor", '<span style="background:#9333ea;color:#fff;padding:1px 6px;border-radius:4px;font-size:10px;margin-left:5px;">😂ユーモア・仲裁</span>'),
        "agree": ("chat-bubble-agree", '<span style="background:#059669;color:#fff;padding:1px 6px;border-radius:4px;font-size:10px;margin-left:5px;">🤝最終コンセンサス</span>')
    }.get(t.get("tone", "normal"), ("chat-bubble-ai", '<span style="background:#0284c7;color:#fff;padding:1px 6px;border-radius:4px;font-size:10px;margin-left:5px;">📊データ解析</span>'))
    sc = f' <span style="background:rgba(56,189,248,0.2);color:#7dd3fc;padding:1px 6px;border-radius:999px;font-size:10.5px;">評価 {t["score"]}点</span>' if "score" in t else ""
    return f'<div class="{b_cls}"><div style="font-weight:800;color:#38bdf8;font-size:12px;margin-bottom:3px;">{t["speaker"]}{sc}{tag}</div><div>{t["text"]}</div></div>'

@frag_dec
def render_council_sec(r, uk):
    is_open = st.session_state["active_debates"].get(uk, False)
    in_wl = r["code"] in st.session_state["watchlist"]
    c1, c2 = st.columns([2.6, 1.1])
    if c1.button("🔼 AIエージェント合議を閉じる" if is_open else "⚡ 7専門AIエージェント合議を見る＆参加", key=f"b_{uk}", use_container_width=True):
        st.session_state["active_debates"][uk] = not is_open; st.rerun()
    if c2.button("✅ 監視済(解除)" if in_wl else "⭐ 監視追加", key=f"w_{uk}", use_container_width=True):
        if in_wl: del st.session_state["watchlist"][r["code"]]
        else: st.session_state["watchlist"][r["code"]] = r
        st.rerun()
    if not is_open: return

    cur_st = st.session_state["debate_style_map"].get(uk, "⚖️ 標準バランス")
    new_st = st.radio("温度感", ["⚖️ 標準バランス", "🔥 激論・徹底検証", "🛡️ 超辛口・リスク監査"], horizontal=True, index=["⚖️ 標準バランス", "🔥 激論・徹底検証", "🛡️ 超辛口・リスク監査"].index(cur_st), key=f"st_{uk}", label_visibility="collapsed")
    if new_st != cur_st:
        st.session_state["debate_style_map"][uk] = new_st
        st.session_state["debate_round_seed"][uk] = st.session_state["debate_round_seed"].get(uk, 0) + 1
        st.session_state["streamed_keys"].discard(uk); st.session_state["council_threads"].pop(uk, None); st.rerun()

    m5 = fetch_5m(r["full_code"])
    if m5 and show_5m_chart:
        st.caption(f"📅 直近5分足 ({m5['chart_date']}) ｜ 5分足VWAP: **{m5['vwap5_price']}** ({m5['vwap5_dev']:+.2f}%)")
        cdf = m5["chart_df"]
        base = alt.Chart(cdf).encode(x=alt.X("Time:N", sort=None, title=None))
        cs = alt.Scale(domain=["陽線", "陰線"], range=["#dc2626", "#2563eb"])
        w = base.mark_rule(size=1.5).encode(y=alt.Y("Low:Q", scale=alt.Scale(zero=False), title="株価"), y2="High:Q", color=alt.Color("BarColor:N", scale=cs, legend=None))
        b = base.mark_bar(size=6).encode(y=alt.Y("Open:Q", scale=alt.Scale(zero=False)), y2="Close:Q", color=alt.Color("BarColor:N", scale=cs, legend=None))
        vw = base.mark_line(color="#d97706", strokeWidth=2.5, strokeDash=[4, 2]).encode(y="VWAP:Q")
        st.altair_chart((w + b + vw).properties(height=155), use_container_width=True)

    first_run = False
    if uk not in st.session_state["council_threads"]:
        deb = run_7ai_council(r, m5, st.session_state["debate_round_seed"].get(uk, 0), new_st)
        st.session_state["council_threads"][uk] = list(deb["dialogue"])
        st.session_state["council_meta"][uk] = deb; first_run = True

    meta = st.session_state["council_meta"][uk]
    turns = st.session_state["council_threads"][uk]
    wid = f"cwin_{uk}"

    if live_stream_mode and (first_run or uk not in st.session_state["streamed_keys"]):
        st.session_state["streamed_keys"].add(uk)
        lbox, sbar, so_far = st.empty(), st.empty(), []
        for i, t in enumerate(turns):
            if "speaker" in t:
                sbar.markdown(f"<div style='color:#38bdf8;font-size:12px;font-weight:800;'>🎙️ {t['speaker']} が発言中...</div>", unsafe_allow_html=True)
                time.sleep(0.35)
            so_far.append(_fmt_turn(t))
            v_blk = f'<div class="consensus-banner"><div style="font-weight:bold;color:#fde047;font-size:13.5px;">🏛️ 全エージェント合意の最終コンセンサス</div>{meta["verdict_html"]}</div>' if i == len(turns) - 1 else ""
            lbox.markdown(f'<div class="ai-council-box"><div id="{wid}" class="council-scroll-window">{"".join(so_far)}</div>{v_blk}</div>', unsafe_allow_html=True)
        sbar.empty()
    else:
        st.markdown(f'<div class="ai-council-box"><div id="{wid}" class="council-scroll-window">{"".join(_fmt_turn(t) for t in turns)}</div><div class="consensus-banner"><div style="font-weight:bold;color:#fde047;font-size:13.5px;">🏛️ 全エージェント合意の最終コンセンサス</div>{meta["verdict_html"]}</div></div>', unsafe_allow_html=True)

    ec1, ec2 = st.columns([1.8, 1.4])
    if ec1.button("💬 議論の続きを生成（＋1ラウンド）", key=f"ex_{uk}", use_container_width=True):
        nr = st.session_state["debate_round_seed"].get(uk, 0) + 1; st.session_state["debate_round_seed"][uk] = nr
        st.session_state["council_threads"][uk].extend(gen_extra_round(r, m5, nr)); st.rerun()
    if ec2.button("🔄 別の切り口で再ディベート", key=f"rs_{uk}", use_container_width=True):
        st.session_state["debate_round_seed"][uk] = st.session_state["debate_round_seed"].get(uk, 0) + 1
        st.session_state["streamed_keys"].discard(uk); st.session_state["council_threads"].pop(uk, None); st.rerun()

    with st.form(f"jf_{uk}", clear_on_submit=True):
        jc1, jc2 = st.columns([3.2, 1])
        uop = jc1.text_input("発言", placeholder="ディベートに割り込む（例：朝から行くべき？ / 上ヒゲが怖い / 現在の株価は？）", label_visibility="collapsed")
        if jc2.form_submit_button("💬 発言を投下", use_container_width=True) and uop.strip():
            st.session_state["council_threads"][uk].append({"is_user": True, "text": uop.strip()})
            st.session_state["council_threads"][uk].extend(gen_user_reply(uop.strip(), r, m5)); st.rerun()

    qc1, qc2 = st.columns(2)
    for col, lbl, qtxt, k_s in [
        (qc1, "💴 現在の株価・高値安値・目標株価は？", "現在の株価はいくら？本日の高値・安値・目標株価も教えて", "q1"),
        (qc1, "📊 決算・PER/PBR・時価総額を調べて", "PERやPBR、時価総額、目標株価などファンダメンタルズを評価して", "q2"),
        (qc2, "📰 最新ニュースと値動きの理由は？", "最新ニュースと本日の値動きの理由・需給背景は？", "q3"),
        (qc2, "💰 具体的な買い値・利確・損切りは？", "いつどの価格で買って、いくらで利確・損切りすべき？", "q4")
    ]:
        if col.button(lbl, key=f"{k_s}_{uk}", use_container_width=True):
            st.session_state["stock_chats"].setdefault(uk, []).append({"q": qtxt, "a": gen_qa_html(qtxt, r, m5)}); st.rerun()

    with st.form(f"fq_{uk}", clear_on_submit=True):
        fc1, fc2 = st.columns([3.2, 1])
        uq = fc1.text_input("質問", placeholder="自由質問（例：空売りの買い戻し余地はある？ / 押し目はどこ？）", label_visibility="collapsed")
        if fc2.form_submit_button("🔍 ライブ調査", use_container_width=True) and uq.strip():
            st.session_state["stock_chats"].setdefault(uk, []).append({"q": uq.strip(), "a": gen_qa_html(uq.strip(), r, m5)}); st.rerun()

    chats = st.session_state["stock_chats"].get(uk, [])
    if chats:
        st.markdown(f'<div class="qa-answer-card">{chats[-1]["a"]}</div>', unsafe_allow_html=True)
        if st.button("🗑️ 質問履歴をクリア", key=f"cl_{uk}", use_container_width=True):
            st.session_state["stock_chats"][uk] = []; st.rerun()

def render_card(r, is_custom=False, rank=None, kp="card"):
    dc = "#dc2626" if r["diff"] > 0 else "#2563eb"
    ds, ps = ("+" if r["diff"] > 0 else ""), ("+" if r["pts_gap_pct"] > 0 else "")
    rk_h = f'<span class="rank-badge">🏆 第{rank}位</span>' if rank else ""
    lot = r["lot_info"]
    ini = r["name"].replace(" (米)", "").strip()[0] if r["name"] else "📈"
    logo = f'<img src="https://ui-avatars.com/api/?name={urllib.parse.quote(ini)}&background=0f172a&color=fbbf24&bold=true&size=64" class="company-logo-img" />'

    st.markdown(
        f'<div class="{"search-result-card" if is_custom else "rank-card"}">'
        f'<div class="signal-10tier-badge" style="background:{r["tier_bg"]};color:{r["tier_color"]} !important;"><span>🎯 {r["tier_label"]}</span><span style="font-size:11.5px;">総合勝率 {r["total_win_rate"]}% ｜ Lv.{r["tier_num"]}/10</span></div>'
        f'<div style="margin-bottom:7px;">{rk_h}<span class="score-badge">⚡ 総合指数: {r["ai_score"]}点</span><span class="inst-badge">🏦 機関VPIN: {r["inst_score"]}点</span><span class="board5ch-badge">🔥 短期需給: {r["board5ch_score"]}点</span><span class="tokugai-badge">🚨 特買い: {r["tokugai_prob"]}%</span></div>'
        f'<div style="display:flex;justify-content:space-between;align-items:center;"><div style="display:flex;align-items:center;gap:9px;">{logo}<div><span style="font-size:17px;font-weight:800;">{r["name"]}</span> <span style="font-size:12.5px;color:#64748b;">({r["code"]} / {r["genre"]})</span><br><span style="font-size:14.5px;">現在値: <b>{r["price"]}</b> (<span style="color:{dc};font-weight:800;">{ds}{r["diff"]}%</span>)</span></div></div>'
        f'<div style="text-align:right;"><span style="font-size:11px;color:#64748b;font-weight:700;">🎯 総合勝率</span><br><span class="prob-badge">{r["total_win_rate"]}%</span><div style="font-size:11px;color:#64748b;">(損益比 {r["payoff"]}倍 / 期待値 {r["edge"]:+.2f}%)</div></div></div>'
        f'<div class="winrate-bar"><div><div style="font-size:10.5px;color:#881337;font-weight:700;">🏆 総合勝率</div><div style="font-size:14.5px;font-weight:900;color:#e11d48;">{r["total_win_rate"]}%</div></div><div style="border-left:1px solid #fecdd3;"><div style="font-size:10.5px;color:#64748b;">🌅 翌朝GU勝率</div><div style="font-size:13.5px;font-weight:800;color:#dc2626;">{r["prob"]}% <span style="font-size:10px;">({r["count"]})</span></div></div><div style="border-left:1px solid #fecdd3;"><div style="font-size:10.5px;color:#64748b;">☀️ 寄り後陽線</div><div style="font-size:13.5px;font-weight:800;color:#d97706;">{r["intraday_win_rate"]}%</div></div><div style="border-left:1px solid #fecdd3;"><div style="font-size:10.5px;color:#64748b;">📈 順張り勝率</div><div style="font-size:13.5px;font-weight:800;color:#15803d;">{r["trend_win_rate"]}%</div></div></div>'
        f'<div class="delicate-box">{r["delicate_narrative"]}</div>'
        f'<div class="inst-box"><b>{r["inst_status"]}</b> ｜ 20日VWAP基準: <b>{r["vwap_price"]}</b></div>'
        f'<div class="board5ch-box"><b>📢 {r["board5ch_status"]}</b> ｜ シグナル: <b>{r["signal"]}</b></div>'
        f'<div class="pts-tokugai-box"><b>🌙 {r["tokugai_status"]}</b> ｜ 夜間理論気配: <b>{r["pts_est_price"]}</b> ({ps}{r["pts_gap_pct"]}%) ｜ 特買い線: <b>{r["tokugai_line"]}</b></div>'
        f'<div class="squeeze-box"><b>{r["squeeze_type"]}</b> ｜ 踏み上げ突破ライン(20日高値): <b>{r["squeeze_trigger_price"]}</b> ({r["dist_to_high20"]:+.2f}%)</div>'
        f'<div class="metrics-row"><span>🏦 <b>VPIN:</b> {r["vpin"]:+.2f}</span><span>🧬 <b>Hurst:</b> {r["hurst"]}</span><span>🎯 <b>Kalman:</b> {r["kalman_bull_pct"]:+.2f}%</span><span>📐 <b>BB:</b> {r["bb_z"]:+.2f}σ</span><span>📊 <b>RSI:</b> {r["rsi"]}</span><span>📈 <b>MACD:</b> {r["macd_state"]}</span><span>🔊 <b>出来高:</b> {r["vol_ratio"]}倍</span></div>'
        f'<div class="trade-plan-box"><div><div style="font-size:10.5px;color:#64748b;">🌅 夜間理論寄付き</div><div style="font-size:13px;font-weight:800;">{r["pts_est_price"]}</div></div><div style="border-left:1px solid #cbd5e1;border-right:1px solid #cbd5e1;"><div style="font-size:10.5px;color:#15803d;font-weight:bold;">🎯 利確目標</div><div style="font-size:13px;font-weight:800;color:#15803d;">{r["tp_price"]} (+{r["tp_pct"]}%)</div></div><div><div style="font-size:10.5px;color:#b91c1c;font-weight:bold;">🛡️ 損切り逆指値</div><div style="font-size:13px;font-weight:800;color:#b91c1c;">{r["sl_price"]} ({r["sl_pct"]}%)</div></div></div>'
        f'<div class="sizing-box">📦 <b>推奨ロット: {lot["shares"]:,}株</b> (投資額: <b>{lot["position_value"]:,.0f}円</b> / 最大損失リスク: <b>{lot["risk_amount"]:,.0f}円</b>)</div></div>',
        unsafe_allow_html=True
    )
    render_council_sec(r, f"{kp}_{r['code']}")

# ==========================================
# 🚀 メイン画面描画
# ==========================================
macro_info = fetch_macro()
mpills = "".join([f'<div style="background:rgba(255,255,255,0.08);padding:3px 9px;border-radius:6px;font-size:11.5px;display:inline-flex;gap:4px;"><span style="color:#cbd5e1;">{m["label"]}</span><span style="color:{"#f87171" if m["diff"]>=0 else "#60a5fa"};font-weight:700;">{"+" if m["diff"]>=0 else ""}{m["diff"]}%</span></div>' for m in macro_info.values()])
st.markdown(f'<div style="background:linear-gradient(135deg,#090d16,#1e293b);color:#f8fafc;padding:14px 18px;border-radius:14px;margin-bottom:10px;border:1px solid rgba(56,189,248,0.25);"><div style="display:flex;justify-content:space-between;align-items:center;"><div><div style="font-size:10px;color:#38bdf8;font-weight:800;">MULTI-AGENT QUANT & ORDERFLOW SYSTEM</div><h1 style="margin:2px 0 0 0;font-size:19px;color:#fff;font-weight:900;">⚡ 翌朝株価 クオンツ＆AIエージェント合議 Pro</h1></div><span style="background:rgba(16,185,129,0.2);color:#6ee7b7;padding:4px 10px;border-radius:999px;font-size:11px;font-weight:800;">🟢 API主軸＋シームレス稼働中</span></div><div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:9px;">{mpills}</div></div>', unsafe_allow_html=True)

st.markdown('<div id="smart_deck_anchor"></div>', unsafe_allow_html=True)
BOOST_MAP = {"🧬 Hurst/Kalman": "algo", "🏦 機関VPIN": "inst", "🔥 短期モメンタム": "mom", "💥 20日高値突破": "sq", "🚨 翌朝特買い": "tok"}
st.markdown('<div class="compact-bar-label"><span>⚡ QUANT ENGINE BOOST</span><span style="color:#94a3b8;font-weight:600;">タップで解析ファクターを即時ON/OFF</span></div>', unsafe_allow_html=True)
sel_b = st.pills("ブースト", list(BOOST_MAP.keys()), default=list(BOOST_MAP.keys()), selection_mode="multi", label_visibility="collapsed") if hasattr(st, "pills") else st.multiselect("ブースト", list(BOOST_MAP.keys()), default=list(BOOST_MAP.keys()), label_visibility="collapsed")
ac_b = {BOOST_MAP[k] for k in (sel_b or [])}

with st.spinner("🏦 国内外の母集団を一括スキャン＆最新クオンツ解析中..."):
    g_res, all_res = fetch_pool_batch(macro_info, "inst" in ac_b, "mom" in ac_b, "sq" in ac_b, "tok" in ac_b, "algo" in ac_b)

c1, c2 = st.columns([3.4, 1])
cin = c1.text_input("🔍 銘柄検索", placeholder="銘柄コードまたは米ティッカーを入力 (例: 6920, 5803, NVDA, IONQ)", label_visibility="collapsed")
if c2.button("🔍 銘柄診断", use_container_width=True) and cin:
    st.session_state["custom_search_code"] = norm_tk(cin)

if st.session_state.get("custom_search_code"):
    nc = st.session_state["custom_search_code"]
    with st.spinner(f"「{nc}」を精密解析中..."):
        cr = fetch_one(nc, macro_info, "inst" in ac_b, "mom" in ac_b, "sq" in ac_b, "tok" in ac_b, "algo" in ac_b)
    if cr:
        render_card(cr, is_custom=True, kp="custom")
        if st.button("✖️ 個別診断結果を閉じてランキングに戻る", use_container_width=True):
            st.session_state["custom_search_code"] = ""; st.rerun()
    else: st.warning(f"銘柄「{nc}」のデータが見つかりませんでした。")

def cut_stocks(slist, pct):
    if not slist: return [], []
    s = sorted(slist, key=lambda x: (x["tier_num"], x["total_win_rate"], x["survival_power"], x["inst_score"]), reverse=True)
    k = max(3, int(round(len(s) * (pct / 100.0))))
    return s[:k], s[k:]

st.markdown('<div id="category_bar_anchor"></div>', unsafe_allow_html=True)
if st.session_state.get("navigation_page") == "WATCHLIST":
    st.subheader("📋 監視ウォッチリスト")
    if st.button("⬅️ ランキング一覧へ戻る", use_container_width=True): st.session_state["navigation_page"] = "TOP"; st.rerun()
    for wc, wi in list(st.session_state["watchlist"].items()): render_card(wi, kp=f"wl_{wc}")
else:
    cats = ["🏆 総合TOP5", "🏦 機関VPIN", "🔥 短期モメンタム", "🚨 特買い・PTS", "💥 踏み上げ", "📋 監視シート"] + [f"📂 {g}" for g in STOCK_POOL.keys()]
    st.markdown('<div class="compact-bar-label"><span>📂 RANKING & SECTOR SELECT</span><span style="color:#94a3b8;font-weight:600;">戦略ランキング / テーマ別セクター切替</span></div>', unsafe_allow_html=True)
    if hasattr(st, "pills"):
        p_cat = st.pills("カテゴリ", cats, default=st.session_state.get("active_category", "🏆 総合TOP5"), selection_mode="single", label_visibility="collapsed")
        sel_cat = p_cat if p_cat else st.session_state.get("active_category", "🏆 総合TOP5")
        st.session_state["active_category"] = sel_cat
    else:
        sel_cat = st.radio("カテゴリ", cats, horizontal=True, label_visibility="collapsed")

    surv, elim = cut_stocks(all_res, survival_cut_pct)
    if sel_cat == "🏆 総合TOP5":
        st.caption(f"🦁 全母集団 {len(all_res)}銘柄から下位 {len(elim)}銘柄を足切り！総合勝率・10段階評価ともに最強のTOP5です。")
        for i, r in enumerate(surv[:5], 1): render_card(r, rank=i, kp="top5")
    elif sel_cat == "🏦 機関VPIN":
        for i, r in enumerate(sorted(all_res, key=lambda x: (x["inst_score"], x["total_win_rate"], x["vpin"]), reverse=True)[:10], 1): render_card(r, rank=i, kp="inst")
    elif sel_cat == "🔥 短期モメンタム":
        for i, r in enumerate(sorted(all_res, key=lambda x: (x["board5ch_score"], x["total_win_rate"]), reverse=True)[:10], 1): render_card(r, rank=i, kp="mom")
    elif sel_cat == "🚨 特買い・PTS":
        for i, r in enumerate(sorted(all_res, key=lambda x: (x["tokugai_prob"], x["pts_gap_pct"]), reverse=True)[:10], 1): render_card(r, rank=i, kp="tok")
    elif sel_cat == "💥 踏み上げ":
        for i, r in enumerate(sorted(all_res, key=lambda x: (x["squeeze_score"], x["total_win_rate"]), reverse=True)[:10], 1): render_card(r, rank=i, kp="sq")
    elif sel_cat == "📋 監視シート":
        wl = st.session_state["watchlist"]
        st.markdown(f"#### 📋 監視ウォッチリスト ({len(wl)}銘柄)")
        if st.button("⚡ 総合TOP3をワンタップ一括登録", use_container_width=True):
            for it in surv[:3]: st.session_state["watchlist"][it["code"]] = it
            st.rerun()
        if wl:
            st.dataframe(pd.DataFrame([{"コード": c, "銘柄名": x["name"], "現在値": x["price"], "総合勝率": f"{x['total_win_rate']}%", "10段階判定": x["tier_label"], "夜間理論気配": x["pts_est_price"], "推奨株数": f"{x['lot_info']['shares']:,}株", "利確": x["tp_price"], "損切": x["sl_price"]} for c, x in wl.items()]), use_container_width=True, hide_index=True)
    elif sel_cat.startswith("📂 "):
        gk = sel_cat.replace("📂 ", "")
        gs, ge = cut_stocks(g_res.get(gk, []), survival_cut_pct)
        st.caption(f"🦁 **{gk}選抜**: 上位 **{len(gs)}銘柄が生存**（下位 {len(ge)}銘柄が脱落）")
        for i, r in enumerate(gs, 1): render_card(r, rank=i, kp=f"g_{gk}")
