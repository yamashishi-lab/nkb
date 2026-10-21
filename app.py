import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np
import altair as alt
import unicodedata
import hashlib
import hmac
import time
import json
import os
import random
import smtplib
import urllib.parse
from email.mime.text import MIMEText
from datetime import datetime

st.set_page_config(page_title="翌朝株価 クオンツ＆7大AI解析 Pro (会員限定版)", page_icon="📈", layout="centered")
fragment_decorator = getattr(st, "fragment", getattr(st, "experimental_fragment", lambda f: f))

# ==========================================
# 🔒 会員DB ＆ SMTP永続化 ＆ ワンクリック承認
# ==========================================
ADMIN_EMAIL = "nthbh399@ybb.ne.jp"
SECRET_MASTER_KEY = "my_super_secret_quant_key_2026"
MEMBERS_DB_FILE = "members_db.json"
SMTP_CONFIG_FILE = "admin_smtp_config.json"

def generate_member_passcode(email: str) -> str:
    return hmac.new(SECRET_MASTER_KEY.encode(), email.strip().lower().encode(), hashlib.sha256).hexdigest()[:8].upper()

def generate_admin_action_token(email: str, action: str) -> str:
    return hashlib.sha256(f"{email.strip().lower()}:{action}:{SECRET_MASTER_KEY}".encode()).hexdigest()[:16]

def _load_json(path: str, default: dict) -> dict:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                default.update(json.load(f))
        except Exception:
            pass
    return default

def _save_json(path: str, data: dict):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_smtp_config() -> dict:
    return _load_json(SMTP_CONFIG_FILE, {"app_base_url": "http://localhost:8501", "smtp_user": ADMIN_EMAIL, "smtp_pass": "", "smtp_server": "smtp.mail.yahoo.co.jp", "smtp_port": 465})

def save_smtp_config(cfg: dict):
    _save_json(SMTP_CONFIG_FILE, cfg)

def load_members_db() -> dict:
    db = _load_json(MEMBERS_DB_FILE, {})
    adm = ADMIN_EMAIL.strip().lower()
    if adm not in db:
        now_s = datetime.now().strftime("%Y-%m-%d %H:%M")
        db[adm] = {"name": "管理者 (Owner)", "email": adm, "status": "approved", "passcode": generate_member_passcode(adm), "applied_at": now_s, "approved_at": now_s, "note": "最高管理者"}
        _save_json(MEMBERS_DB_FILE, db)
    return db

def save_members_db(db: dict):
    _save_json(MEMBERS_DB_FILE, db)

def send_auto_email(to_email: str, subject: str, body: str) -> tuple:
    cfg = load_smtp_config()
    u, p, srv, port = cfg.get("smtp_user", "").strip(), cfg.get("smtp_pass", "").strip(), cfg.get("smtp_server", "smtp.mail.yahoo.co.jp").strip(), int(cfg.get("smtp_port", 465))
    if not u or not p: return False, "SMTP未設定"
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"], msg["From"], msg["To"] = subject, u, to_email
        with (smtplib.SMTP_SSL(srv, port, timeout=7) if port == 465 else smtplib.SMTP(srv, port, timeout=7)) as s:
            if port != 465: s.starttls()
            s.login(u, p); s.send_message(msg)
        return True, "送信完了"
    except Exception as e:
        return False, str(e)

def process_url_admin_action():
    qp = st.query_params
    act, em, tok, nm = qp.get("admin_action", ""), qp.get("email", "").strip().lower(), qp.get("token", ""), qp.get("name", "申請者")
    if act in ["approve", "reject"] and em and tok and hmac.compare_digest(tok, generate_admin_action_token(em, act)):
        db = load_members_db()
        code, now_s = generate_member_passcode(em), datetime.now().strftime("%Y-%m-%d %H:%M")
        db[em] = {"name": db.get(em, {}).get("name", nm), "email": em, "status": "approved" if act == "approve" else "rejected", "passcode": code, "applied_at": db.get(em, {}).get("applied_at", now_s), "approved_at": now_s, "note": f"URL:{act}"}
        save_members_db(db)
        if act == "approve":
            subj, body = "【承認完了】専用アクセスコードのお知らせ", f"{db[em]['name']} 様\n\n■登録メール: {em}\n■専用アクセスコード: {code}\n"
            ok, _ = send_auto_email(em, subj, body)
            st.success(f"✅ {em} を承認しました！（専用コード: {code}）")
            if not ok: st.markdown(f'👉 <a href="mailto:{em}?subject={urllib.parse.quote(subj)}&body={urllib.parse.quote(body)}">📨 通知メールを手動送信</a>', unsafe_allow_html=True)
        else:
            st.warning(f"❌ {em} の申請を却下しました。")
        for k in ["admin_action", "email", "token"]:
            if k in st.query_params: del st.query_params[k]

process_url_admin_action()

def render_smtp_settings_form(suffix: str):
    cfg = load_smtp_config()
    with st.form(f"smtp_form_{suffix}"):
        app_url = st.text_input("🌐 アプリ公開URL", value=cfg.get("app_base_url", "http://localhost:8501"))
        s_user = st.text_input("📧 送信元メール", value=cfg.get("smtp_user", ADMIN_EMAIL))
        s_pass = st.text_input("🔑 SMTPパスワード", value=cfg.get("smtp_pass", ""), type="password")
        s_serv = st.text_input("🖥️ SMTPサーバー", value=cfg.get("smtp_server", "smtp.mail.yahoo.co.jp"))
        s_port = st.number_input("🔌 SMTPポート", value=int(cfg.get("smtp_port", 465)))
        if st.form_submit_button("💾 SMTP設定を保存", use_container_width=True):
            save_smtp_config({"app_base_url": app_url.strip(), "smtp_user": s_user.strip(), "smtp_pass": s_pass.strip(), "smtp_server": s_serv.strip(), "smtp_port": int(s_port)})
            st.success("✅ 保存しました！")

def render_admin_sidebar_management():
    db = load_members_db()
    pend = [v for v in db.values() if v.get("status") == "pending"]
    st.sidebar.markdown("---")
    st.sidebar.subheader(f"👑 管理者メニュー (待:{len(pend)}件)")
    if st.sidebar.button("🛠️ 管理者専用ページ(全画面)", key="side_open_admin", use_container_width=True):
        st.session_state["navigation_page"] = "ADMIN"; st.query_params["nav"] = "ADMIN"; st.rerun()
    for p in pend:
        pm, pn, pc = p["email"], p.get("name", "未入力"), generate_member_passcode(p["email"])
        st.sidebar.markdown(f"**📩 {pn}** (`{pm}`)")
        c1, c2, c3 = st.sidebar.columns(3)
        if c1.button("✅", key=f"s_ap_{pm}", use_container_width=True):
            db[pm].update({"status": "approved", "passcode": pc, "approved_at": datetime.now().strftime("%Y-%m-%d %H:%M")})
            save_members_db(db); send_auto_email(pm, "【承認完了】専用コード", f"{pn}様\nコード: {pc}"); st.rerun()
        if c2.button("❌", key=f"s_rj_{pm}", use_container_width=True):
            db[pm]["status"] = "rejected"; save_members_db(db); st.rerun()
        if c3.button("🗑️", key=f"s_dl_{pm}", use_container_width=True) and pm != ADMIN_EMAIL.strip().lower():
            del db[pm]; save_members_db(db); st.rerun()
    with st.sidebar.expander("⚙️ SMTP設定"):
        render_smtp_settings_form("sidebar")

def render_admin_full_page():
    db = load_members_db()
    pend = [v for v in db.values() if v.get("status") == "pending"]
    appr = [v for v in db.values() if v.get("status") == "approved"]
    st.markdown('<div style="background:linear-gradient(135deg,#31102f,#0f172a);color:#fff;padding:18px;border-radius:16px;margin-bottom:14px;"><h2 style="margin:0;font-size:20px;">👑 管理者専用・会員DB＆承認センター</h2></div>', unsafe_allow_html=True)
    if st.button("⬅️ 株価解析ランキング画面（TOP）へ戻る", use_container_width=True):
        st.session_state["navigation_page"] = "TOP"
        if "nav" in st.query_params: del st.query_params["nav"]
        st.rerun()
    m1, m2, m3 = st.columns(3)
    m1.metric("⏳ 承認待ち", f"{len(pend)} 件"); m2.metric("✅ 承認済み", f"{len(appr)} 名"); m3.metric("👥 総登録数", f"{len(db)} 件")
    t1, t2, t3 = st.tabs([f"⏳ 承認待ち ({len(pend)}件)", f"👥 全会員管理 ({len(db)}件)", "⚙️ SMTP設定"])
    with t1:
        for p in pend:
            pm, pn, pc = p["email"], p.get("name", "未入力"), generate_member_passcode(p["email"])
            st.markdown(f'<div class="rank-card"><b>👤 {pn}</b> ({pm}) ｜ 🔑 コード: <code>{pc}</code></div>', unsafe_allow_html=True)
            ca, cr, cd = st.columns(3)
            if ca.button(f"✅ 承認 ({pn})", key=f"m_ap_{pm}", use_container_width=True):
                db[pm].update({"status": "approved", "passcode": pc, "approved_at": datetime.now().strftime("%Y-%m-%d %H:%M")})
                save_members_db(db); send_auto_email(pm, "【承認完了】専用コード", f"{pn}様\n専用コード: {pc}"); st.rerun()
            if cr.button(f"❌ 却下 ({pn})", key=f"m_rj_{pm}", use_container_width=True):
                db[pm]["status"] = "rejected"; save_members_db(db); st.rerun()
            if cd.button(f"🗑️ 削除 ({pn})", key=f"m_dl_{pm}", use_container_width=True) and pm != ADMIN_EMAIL.strip().lower():
                del db[pm]; save_members_db(db); st.rerun()
    with t2:
        with st.form("manual_add"):
            c1, c2, c3 = st.columns(3)
            nn, nm, nt = c1.text_input("お名前"), c2.text_input("メール"), c3.text_input("備考")
            if st.form_submit_button("➕ 即時承認済みとして追加", use_container_width=True) and "@" in nm:
                cm, cg, ns = nm.strip().lower(), generate_member_passcode(nm), datetime.now().strftime("%Y-%m-%d %H:%M")
                db[cm] = {"name": nn or "招待会員", "email": cm, "status": "approved", "passcode": cg, "applied_at": ns, "approved_at": ns, "note": nt}
                save_members_db(db); st.rerun()
        st.dataframe(pd.DataFrame([{"状態": v.get("status"), "名前": v.get("name"), "メール": k, "コード": v.get("passcode"), "承認日": v.get("approved_at", "-")} for k, v in db.items()]), use_container_width=True, hide_index=True)
    with t3:
        render_smtp_settings_form("main")

def check_member_authentication():
    db = load_members_db()
    if "authenticated_user" not in st.session_state: st.session_state["authenticated_user"] = None
    qu, qt = st.query_params.get("u", "").strip().lower(), st.query_params.get("t", "").strip()
    if not st.session_state["authenticated_user"] and qu and qt:
        if hmac.compare_digest(qt, generate_admin_action_token(qu, "session_keep")) and ((db.get(qu) and db[qu].get("status") == "approved") or qu == ADMIN_EMAIL.strip().lower()):
            st.session_state["authenticated_user"] = qu
    if st.session_state["authenticated_user"]:
        cu = st.session_state["authenticated_user"]
        st.query_params["u"], st.query_params["t"] = cu, generate_admin_action_token(cu, "session_keep")
        if st.query_params.get("nav", "").upper() == "ADMIN" and cu == ADMIN_EMAIL.strip().lower():
            st.session_state["navigation_page"] = "ADMIN"
        elif st.query_params.get("nav", "").upper() == "TOP":
            st.session_state["navigation_page"] = "TOP"; del st.query_params["nav"]
        with st.sidebar:
            st.success(f"👤 ログイン中:\n{cu}")
            if st.button("🚪 ログアウト", use_container_width=True):
                st.session_state["authenticated_user"] = None; st.query_params.clear(); st.rerun()
        if cu == ADMIN_EMAIL.strip().lower(): render_admin_sidebar_management()
        return True

    st.markdown('<div style="background:linear-gradient(135deg,#090d16,#1e293b);color:#f8fafc;padding:24px;border-radius:16px;text-align:center;margin-bottom:16px;"><h2 style="margin:0;color:#fbbf24;">🔒 会員限定 クオンツ＆7大AI解析 Pro</h2><p style="font-size:13.5px;color:#cbd5e1;margin-top:6px;">承認されたメールアドレスと専用アクセスコードを入力してください。</p></div>', unsafe_allow_html=True)
    with st.form("login_form"):
        ie, ic = st.text_input("📧 登録メールアドレス"), st.text_input("🔑 専用アクセスコード（8桁）", type="password")
        if st.form_submit_button("🔓 ログインして解析システムを開く", use_container_width=True):
            cm = ie.strip().lower()
            rec = db.get(cm)
            is_app = (rec and rec.get("status") == "approved") or (cm == ADMIN_EMAIL.strip().lower())
            is_val = hmac.compare_digest(ic.strip().upper(), generate_member_passcode(cm)) or (cm == ADMIN_EMAIL.strip().lower() and ic.strip() == "ADMIN777")
            if is_app and is_val:
                st.session_state["authenticated_user"] = cm
                st.query_params["u"], st.query_params["t"] = cm, generate_admin_action_token(cm, "session_keep")
                st.rerun()
            else:
                st.error("⚠️ メールアドレスが未承認、またはアクセスコードが正しくありません。")
    with st.form("apply_form"):
        st.markdown("##### 📩 新規会員登録の申請")
        an, am, ant = st.text_input("👤 お名前"), st.text_input("📧 メールアドレス"), st.text_input("💬 備考（任意）")
        if st.form_submit_button("📨 管理者に利用申請を送信", use_container_width=True) and "@" in am:
            cm, pc, ns = am.strip().lower(), generate_member_passcode(am), datetime.now().strftime("%Y-%m-%d %H:%M")
            db[cm] = {"name": an.strip() or "未入力", "email": cm, "status": "pending", "passcode": pc, "applied_at": ns, "approved_at": "-", "note": ant.strip()}
            save_members_db(db)
            b_url = load_smtp_config().get("app_base_url", "http://localhost:8501").rstrip("/")
            ap_url = f"{b_url}/?admin_action=approve&email={urllib.parse.quote(cm)}&name={urllib.parse.quote(an)}&token={generate_admin_action_token(cm, 'approve')}"
            send_auto_email(ADMIN_EMAIL, f"【会員申請】{an}様 ({cm})", f"申請: {an} ({cm})\nコード: {pc}\n承認URL: {ap_url}")
            st.success("✅ 申請を受け付けました！承認後に専用コードが発行されます。")
    st.stop()

check_member_authentication()

# ==========================================
# 📈 セッション初期化 ＆ モダンCSS（ピル型カテゴリバー搭載）
# ==========================================
for k, v in [("active_debates", {}), ("stock_chats", {}), ("council_threads", {}), ("council_meta", {}), ("debate_round_seed", {}), ("watchlist", {}), ("navigation_page", "TOP"), ("nav_history", ["TOP"]), ("custom_search_code", ""), ("scroll_to_chat_key", None), ("scroll_council_key", None)]:
    if k not in st.session_state: st.session_state[k] = v

def navigate_to(p: str):
    if st.session_state["navigation_page"] != p:
        st.session_state["nav_history"].append(st.session_state["navigation_page"])
        st.session_state["navigation_page"] = p

def navigate_back():
    st.session_state["navigation_page"] = st.session_state["nav_history"].pop() if len(st.session_state["nav_history"]) > 1 else "TOP"
    if "nav" in st.query_params: del st.query_params["nav"]
    st.session_state["custom_search_code"] = ""

def get_company_logo_html(full_code: str, name: str) -> str:
    ini = name.replace(" (米)", "").strip()[0] if name else "📈"
    fb = f"https://ui-avatars.com/api/?name={urllib.parse.quote(ini)}&background=0f172a&color=fbbf24&bold=true&size=64"
    return f'<img src="{fb}" class="company-logo-img" alt="logo" />'

nav_p = st.session_state.get("navigation_page", "TOP")
curr_page_badge = "👑 管理者コンソール" if nav_p == "ADMIN" else ("📋 監視リスト" if nav_p == "WATCHLIST" else "📊 ランキング解析")
is_admin_user = (st.session_state.get("authenticated_user", "") == ADMIN_EMAIL.strip().lower())

st.markdown('<div id="page_top_anchor"></div>', unsafe_allow_html=True)
st.markdown("""
<style>
html, body, [class*="css"] { font-size: 15.5px; }
.block-container { padding-top: 3.4rem !important; padding-bottom: 3rem !important; max-width: 820px !important; }
.floating-glass-nav { position: fixed; top: 10px; left: 50%; transform: translateX(-50%); z-index: 999990; display: flex; align-items: center; gap: 8px; padding: 5px 14px; background: rgba(15, 23, 42, 0.85); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.18); border-radius: 999px; white-space: nowrap; }
.floating-glass-nav a { color: #f8fafc !important; text-decoration: none !important; font-size: 12px; font-weight: 600; }

/* モダン・グラスモーフィズムのピル型カテゴリタブ化 */
div[data-testid="stRadio"] > div[role="radiogroup"] {
    display: flex !important;
    flex-wrap: wrap !important;
    gap: 8px !important;
    background: linear-gradient(135deg, #0f172a, #1e293b) !important;
    padding: 12px !important;
    border-radius: 16px !important;
    border: 1px solid rgba(251, 191, 36, 0.28) !important;
    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.18) !important;
}
div[data-testid="stRadio"] > div[role="radiogroup"] > label {
    background: rgba(255, 255, 255, 0.07) !important;
    border: 1px solid rgba(255, 255, 255, 0.14) !important;
    border-radius: 999px !important;
    padding: 6px 15px !important;
    margin: 0 !important;
    transition: all 0.2s ease !important;
    cursor: pointer !important;
}
div[data-testid="stRadio"] > div[role="radiogroup"] > label:hover {
    background: rgba(251, 191, 36, 0.2) !important;
    border-color: #fbbf24 !important;
    transform: translateY(-1px) !important;
}
div[data-testid="stRadio"] > div[role="radiogroup"] > label > div:first-child {
    display: none !important; /* 丸ポチを完全に非表示 */
}
div[data-testid="stRadio"] > div[role="radiogroup"] > label p {
    color: #e2e8f0 !important;
    font-size: 13px !important;
    font-weight: 700 !important;
    margin: 0 !important;
}
div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) {
    background: linear-gradient(135deg, #f59e0b, #e11d48) !important;
    border-color: #fde047 !important;
    box-shadow: 0 4px 14px rgba(225, 29, 72, 0.45) !important;
}
div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) p {
    color: #ffffff !important;
    font-weight: 900 !important;
}

.company-logo-img { width: 38px; height: 38px; border-radius: 9px; object-fit: contain; background: #fff; padding: 2px; border: 1px solid #e2e8f0; }
.rank-card, .search-result-card { background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%) !important; color: #0f172a !important; border-radius: 16px; padding: 18px; margin-bottom: 13px; box-shadow: 0 6px 20px rgba(15,23,42,0.07); border: 1px solid #e2e8f0; border-left: 6px solid #e11d48; }
.rank-card *, .search-result-card * { color: #0f172a; }
.search-result-card { background: linear-gradient(180deg, #fffbeb 0%, #fef3c7 100%) !important; border-left-color: #d97706; }
.prob-badge { font-size: 25px; font-weight: 800; color: #dc2626 !important; }
.rank-badge { display: inline-block; background: linear-gradient(135deg, #f59e0b, #d97706); color: #fff !important; padding: 3px 10px; border-radius: 999px; font-size: 12.5px; font-weight: 700; margin-right: 5px; }
.score-badge { display: inline-block; background: #0f172a; color: #f8fafc !important; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; }
.inst-badge { display: inline-block; background: linear-gradient(135deg, #1d4ed8, #2563eb); color: #fff !important; padding: 3px 9px; border-radius: 999px; font-size: 12px; font-weight: 700; margin-left: 4px; }
.board5ch-badge { display: inline-block; background: linear-gradient(135deg, #059669, #10b981); color: #fff !important; padding: 3px 9px; border-radius: 999px; font-size: 12px; font-weight: 700; margin-left: 4px; }
.tokugai-badge { display: inline-block; background: linear-gradient(135deg, #d97706, #f59e0b); color: #fff !important; padding: 3px 9px; border-radius: 999px; font-size: 12px; font-weight: 700; margin-left: 4px; }
.winrate-bar { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; background: #fff1f2 !important; border: 1px solid #fecdd3; border-radius: 10px; padding: 8px 6px; margin-top: 9px; text-align: center; }
.signal-10tier-badge { display: flex; align-items: center; justify-content: space-between; padding: 8px 14px; border-radius: 10px; font-size: 14px; font-weight: 800; margin-bottom: 10px; }
.inst-box { background: #eff6ff !important; border: 1px solid #bfdbfe; border-left: 4px solid #2563eb; border-radius: 9px; padding: 8px 12px; margin-top: 7px; font-size: 12.5px; color: #1e3a8a !important; }
.inst-box * { color: #1e3a8a !important; }
.squeeze-box { background: #fff1f2 !important; border: 1px solid #fecdd3; border-left: 4px solid #e11d48; border-radius: 9px; padding: 8px 12px; margin-top: 6px; font-size: 12.5px; color: #881337 !important; }
.squeeze-box * { color: #881337 !important; }
.pts-tokugai-box { background: #fffbeb !important; border: 1px solid #fde68a; border-left: 4px solid #d97706; border-radius: 9px; padding: 8px 12px; margin-top: 6px; font-size: 12.5px; color: #78350f !important; }
.pts-tokugai-box * { color: #78350f !important; }
.board5ch-box { background: #ecfdf5 !important; border: 1px solid #a7f3d0; border-left: 4px solid #059669; border-radius: 9px; padding: 8px 12px; margin-top: 6px; font-size: 12.5px; color: #064e3b !important; }
.board5ch-box * { color: #064e3b !important; }
.delicate-box { background: #f8fafc !important; border: 1px solid #cbd5e1; border-left: 4px solid #7c3aed; border-radius: 9px; padding: 9px 12px; margin-top: 7px; font-size: 12.5px; line-height: 1.6; color: #1e293b !important; }
.metrics-row { display: flex; flex-wrap: wrap; gap: 6px 12px; margin-top: 8px; font-size: 12px; background: #f1f5f9 !important; padding: 8px 12px; border-radius: 8px; border: 1px solid #e2e8f0; }
.trade-plan-box { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-top: 8px; background: #fff !important; padding: 9px 6px; border-radius: 10px; border: 1px solid #cbd5e1; text-align: center; }
.sizing-box { background: linear-gradient(90deg, #f0fdf4, #dcfce7) !important; border: 1px solid #86efac; border-radius: 9px; padding: 8px 12px; margin-top: 8px; font-size: 12.5px; color: #166534 !important; }
.ai-council-box { background: linear-gradient(135deg, #090d16, #1e293b); color: #f8fafc !important; border-radius: 14px; padding: 16px; margin-top: 8px; margin-bottom: 12px; border: 1px solid rgba(251,191,36,0.28); }
.ai-council-box * { color: #f8fafc; }
.council-scroll-window { max-height: 580px; overflow-y: auto; padding: 12px; background: rgba(6, 10, 19, 0.78); border: 1px solid rgba(255,255,255,0.14); border-radius: 12px; margin-bottom: 10px; scroll-behavior: smooth; }
.council-scroll-window::-webkit-scrollbar { width: 8px; }
.council-scroll-window::-webkit-scrollbar-track { background: rgba(15, 23, 42, 0.6); border-radius: 8px; }
.council-scroll-window::-webkit-scrollbar-thumb { background: #fbbf24; border-radius: 8px; }
.round-divider { text-align: center; margin: 14px 0 10px 0; padding: 6px 12px; background: linear-gradient(90deg, rgba(251,191,36,0.05), rgba(251,191,36,0.28), rgba(251,191,36,0.05)); border-top: 1px solid rgba(251,191,36,0.45); border-bottom: 1px solid rgba(251,191,36,0.45); color: #fde047 !important; font-size: 12.5px; font-weight: 800; border-radius: 6px; }
.system-event-bar { text-align: center; margin: 10px 0; padding: 7px 12px; background: linear-gradient(90deg, rgba(220,38,38,0.15), rgba(220,38,38,0.4), rgba(220,38,38,0.15)); border: 1px dashed #f87171; color: #fecaca !important; font-size: 12.5px; font-weight: 800; border-radius: 8px; }
.system-rejoin-bar { text-align: center; margin: 10px 0; padding: 7px 12px; background: linear-gradient(90deg, rgba(16,185,129,0.15), rgba(16,185,129,0.38), rgba(16,185,129,0.15)); border: 1px dashed #34d399; color: #a7f3d0 !important; font-size: 12.5px; font-weight: 800; border-radius: 8px; }
.chat-bubble-ai { background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.12); border-left: 4px solid #38bdf8; border-radius: 12px; padding: 10px 14px; margin-bottom: 9px; font-size: 13px; line-height: 1.68; }
.chat-bubble-doubt { background: rgba(245, 158, 11, 0.14); border: 1px solid rgba(251, 191, 36, 0.35); border-left: 4px solid #f59e0b; border-radius: 12px; padding: 10px 14px; margin-bottom: 9px; font-size: 13px; line-height: 1.68; }
.chat-bubble-rebuttal { background: rgba(225, 29, 72, 0.14); border: 1px solid rgba(244, 63, 94, 0.35); border-left: 4px solid #f43f5e; border-radius: 12px; padding: 10px 14px; margin-bottom: 9px; font-size: 13px; line-height: 1.68; }
.chat-bubble-rage { background: linear-gradient(135deg, rgba(153, 27, 27, 0.38), rgba(69, 10, 10, 0.55)); border: 1.5px solid #ef4444; border-left: 6px solid #dc2626; border-radius: 12px; padding: 11px 14px; margin-bottom: 9px; font-size: 13.2px; line-height: 1.68; }
.chat-bubble-humor { background: rgba(168, 85, 247, 0.16); border: 1px solid rgba(192, 132, 252, 0.4); border-left: 4px solid #c084fc; border-radius: 12px; padding: 10px 14px; margin-bottom: 9px; font-size: 13px; line-height: 1.68; }
.chat-bubble-agree { background: rgba(16, 185, 129, 0.14); border: 1px solid rgba(52, 211, 153, 0.35); border-left: 4px solid #10b981; border-radius: 12px; padding: 10px 14px; margin-bottom: 9px; font-size: 13px; line-height: 1.68; }
.chat-bubble-user { background: linear-gradient(135deg, #1d4ed8, #2563eb); border: 1px solid #60a5fa; border-radius: 12px; padding: 10px 14px; margin-bottom: 9px; font-size: 13.5px; line-height: 1.65; }
.consensus-banner { background: linear-gradient(135deg, #1e1b4b, #312e81); border: 1.5px solid #818cf8; border-radius: 12px; padding: 14px; margin-top: 10px; font-size: 13px; }
.consensus-section { background: rgba(255, 255, 255, 0.07); border-left: 3px solid #fbbf24; border-radius: 6px; padding: 8px 11px; margin-top: 7px; }
.qa-answer-card { background: #ffffff !important; border: 2px solid #3b82f6; border-left: 6px solid #1d4ed8; border-radius: 12px; padding: 14px 16px; margin-top: 8px; margin-bottom: 10px; font-size: 13.5px !important; line-height: 1.75 !important; color: #0f172a !important; }
.qa-answer-card * { color: #0f172a !important; }
.qa-direct-box { background: #eff6ff !important; border: 1px solid #93c5fd; border-left: 4px solid #2563eb; padding: 10px 12px; border-radius: 8px; margin: 8px 0; font-size: 14px !important; }
.qa-answer-card b, .qa-answer-card strong { color: #1d4ed8 !important; font-weight: 700; }
</style>
<div class="floating-glass-nav">
    <a href="#page_top_anchor">⬆️ ページTOPへ</a>
    <span style="color:#64748b;">|</span>
    <a href="#search_box_anchor">🔍 銘柄検索・カテゴリ</a>
</div>
""", unsafe_allow_html=True)

if is_admin_user:
    db_top = load_members_db()
    pend_cnt = sum(1 for v in db_top.values() if v.get("status") == "pending")
    ac1, ac2 = st.columns([2.3, 1.4])
    ac1.info(f"👑 **管理者モード** ｜ 承認待ち: **{pend_cnt}件** / 会員数: **{len(db_top)}名**")
    if st.session_state.get("navigation_page") == "ADMIN":
        if ac2.button("📊 株価解析TOPへ戻る", use_container_width=True):
            st.session_state["navigation_page"] = "TOP"; st.rerun()
    else:
        if ac2.button(f"👑 会員管理ページを開く ({pend_cnt}件)", use_container_width=True):
            navigate_to("ADMIN"); st.rerun()

# --- サイドバー設定 ---
st.sidebar.header("🧭 ナビゲーション")
sc1, sc2 = st.sidebar.columns(2)
if sc1.button("⬆️ ページTOP", use_container_width=True):
    st.session_state["navigation_page"] = "TOP"; st.session_state["custom_search_code"] = ""; st.rerun()
if sc2.button("⬅️ 前の画面", use_container_width=True):
    navigate_back(); st.rerun()
if st.sidebar.button(f"📋 監視ウォッチリスト ({len(st.session_state['watchlist'])}銘柄)", use_container_width=True):
    navigate_to("WATCHLIST"); st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("💰 資金管理＆リスク設定")
total_capital = st.sidebar.number_input("総投資資金 (円 / ドル)", min_value=10000, max_value=1000000000, value=1000000, step=50000)
risk_tolerance_pct = st.sidebar.slider("1トレード許容リスク (%)", min_value=0.5, max_value=5.0, value=2.0, step=0.5)

st.sidebar.markdown("---")
st.sidebar.header("🧬 最新クオンツ自動適応設定")
auto_evolve_algo = st.sidebar.checkbox("🧬 最新クオンツ（Hurst・Kalman・Kyleλ）組込", value=True)
survival_cut_pct = st.sidebar.slider("弱肉強食・各タブ選抜率 (%)", min_value=40, max_value=100, value=70, step=10)
inst_boost_mode = st.sidebar.checkbox("🏦 機関クオンツ（VPIN・ステルス吸収）優先", value=True)
board5ch_boost = st.sidebar.checkbox("🔥 5ch板・初動イナゴ＆シコリ玉なし優先", value=True)
squeeze_boost_mode = st.sidebar.checkbox("💥 空売り踏み上げ（20日高値突破）優先", value=True)
tokugai_boost_mode = st.sidebar.checkbox("🚨 翌朝『特買い』・夜間PTS連動を優先", value=True)
show_5m_chart = st.sidebar.checkbox("合議パネル内に5分足＆VWAPチャートを描画", value=True)

if st.session_state.get("navigation_page") == "ADMIN" and is_admin_user:
    render_admin_full_page()
    st.stop()

# --- 🦁 国内外の主力・テーマ母集団プール ---
STOCK_POOL = {
    "半導体": [
        {"code": "8035.T", "name": "東京エレクトロン", "theme": "前工程装置の国内筆頭。機関の指数バスケット買い中心"},
        {"code": "6857.T", "name": "アドバンテスト", "theme": "AI半導体テスタ世界首位級。SOX指数連動"},
        {"code": "6920.T", "name": "レーザーテック", "theme": "EUV検査装置。デイトレ売買代金・空売り踏み上げ筆頭"},
        {"code": "6146.T", "name": "ディスコ", "theme": "HBM向け精密加工装置で圧倒的シェア"},
        {"code": "6526.T", "name": "ソシオネクスト", "theme": "先端カスタムSoC。個人の信用回転が極めて活発"},
        {"code": "7735.T", "name": "スクリーンHD", "theme": "ウエハー洗浄装置で世界首位"},
        {"code": "6315.T", "name": "TOWA", "theme": "HBM向け半導体モールディング装置"},
        {"code": "6723.T", "name": "ルネサス", "theme": "車載・産業・AI向け半導体"},
        {"code": "4063.T", "name": "信越化学工業", "theme": "シリコンウエハー世界首位"},
        {"code": "3436.T", "name": "SUMCO", "theme": "シリコンウエハー大手"},
        {"code": "6323.T", "name": "ローツェ", "theme": "ウエハー搬送機。空売り買い戻しが強烈"},
        {"code": "6871.T", "name": "日本マイクロニクス", "theme": "HBM向けプローブカードで急騰常連"},
        {"code": "NVDA", "name": "エヌビディア (米)", "theme": "生成AI向けGPUの世界覇者"},
        {"code": "AMD", "name": "AMD (米)", "theme": "AIアクセラレータ・CPU大手"},
        {"code": "MU", "name": "マイクロン (米)", "theme": "HBM・DRAMメモリ大手"},
        {"code": "TSM", "name": "TSMC (米)", "theme": "世界最大の半導体受託生産"},
        {"code": "AVGO", "name": "ブロードコム (米)", "theme": "カスタムAIチップ・通信半導体"},
        {"code": "ARM", "name": "アーム (米)", "theme": "半導体設計アーキテクチャの要"},
        {"code": "SMCI", "name": "スーパーマイクロ (米)", "theme": "AIサーバー大手。値動きと踏み上げが激しい"}
    ],
    "AI・防衛・主力": [
        {"code": "9984.T", "name": "ソフトバンクG", "theme": "AI投資群・Arm親会社。先物連動の主役"},
        {"code": "3778.T", "name": "さくらネット", "theme": "国策GPUクラウド。5chデイトレ板の常連急騰株"},
        {"code": "7011.T", "name": "三菱重工業", "theme": "防衛・宇宙・原発の国策ど真ん中主力株"},
        {"code": "7012.T", "name": "川崎重工業", "theme": "防衛装備・航空エンジン主力"},
        {"code": "7013.T", "name": "IHI", "theme": "航空宇宙・防衛エンジン主力"},
        {"code": "3993.T", "name": "PKSHA", "theme": "AIアルゴリズム・対話AI"},
        {"code": "4180.T", "name": "Appier", "theme": "AIマーケティングSaaS"},
        {"code": "5032.T", "name": "ANYCOLOR", "theme": "VTuber大手。好決算・自社株買いで踏み上げ頻発"},
        {"code": "4385.T", "name": "メルカリ", "theme": "国内C2C大手。信用取組の妙味"},
        {"code": "7974.T", "name": "任天堂", "theme": "次世代機テーマ・海外機関資金流入の超主力"},
        {"code": "8306.T", "name": "三菱UFJ", "theme": "金利連動のメガバンク筆頭"},
        {"code": "MSFT", "name": "マイクロソフト (米)", "theme": "OpenAI筆頭連携・クラウド巨人"},
        {"code": "PLTR", "name": "パランティア (米)", "theme": "防衛・企業向けAIプラットフォーム大本命"},
        {"code": "META", "name": "メタ (米)", "theme": "AI広告・LlamaオープンソースAI"},
        {"code": "GOOGL", "name": "アルファベット (米)", "theme": "Gemini生成AI・検索クラウド"},
        {"code": "CRWD", "name": "クラウドストライク (米)", "theme": "AIサイバーセキュリティ世界首位"}
    ],
    "AI電力・電線": [
        {"code": "5803.T", "name": "フジクラ", "theme": "AIデータセンター向け光ファイバー。機関買い＆踏み上げ最強格"},
        {"code": "5801.T", "name": "古河電気工業", "theme": "光ファイバー・送電インフラ"},
        {"code": "5802.T", "name": "住友電気工業", "theme": "電線首位・データセンター通信網"},
        {"code": "6501.T", "name": "日立製作所", "theme": "世界送配電グリッド・AIインフラ"},
        {"code": "9509.T", "name": "北海道電力", "theme": "ラピダス・AIデータセンター電力供給"},
        {"code": "9508.T", "name": "九州電力", "theme": "TSMC半導体工場向け電力需要"},
        {"code": "6622.T", "name": "ダイヘン", "theme": "データセンター向け変圧器"},
        {"code": "1942.T", "name": "関電工", "theme": "データセンター電気設備工事"},
        {"code": "VST", "name": "ビストラ (米)", "theme": "AIデータセンター向け発電主力"},
        {"code": "CEG", "name": "コンステレーション (米)", "theme": "米最大の原子力発電・AI電力供給"},
        {"code": "GEV", "name": "GEヴェルノバ (米)", "theme": "ガスタービン・送電網設備の世界リーダー"}
    ],
    "宇宙・イーロン": [
        {"code": "5595.T", "name": "QPS研究所", "theme": "小型SAR衛星。5chデイトレ板で人気集中の筆頭"},
        {"code": "186A.T", "name": "アストロスケール", "theme": "宇宙デブリ除去の世界的ベンチャー"},
        {"code": "9348.T", "name": "ispace", "theme": "月面開発輸送。イベント前後の出来高急増株"},
        {"code": "9412.T", "name": "スカパーJSAT", "theme": "衛星通信・防衛宇宙監視"},
        {"code": "9433.T", "name": "KDDI", "theme": "SpaceX Starlink直接通信連携"},
        {"code": "7203.T", "name": "トヨタ自動車", "theme": "全固体電池・自動運転"},
        {"code": "TSLA", "name": "テスラ (米)", "theme": "自動運転・ロボタクシー・世界最大の踏み上げ株"},
        {"code": "RKLB", "name": "ロケットラボ (米)", "theme": "小型ロケット打上げ米宇宙主力"},
        {"code": "ASTS", "name": "ASTスペースモバイル (米)", "theme": "宇宙スマホ直接通信・ショートスクイーズ常連"},
        {"code": "COIN", "name": "コインベース (米)", "theme": "暗号資産連動・ハイボラティリティ銘柄"}
    ],
    "小型急騰・IPO": [
        {"code": "5253.T", "name": "カバー", "theme": "ホロライブ運営。グロース市場の売買代金トップ級"},
        {"code": "9166.T", "name": "GENDA", "theme": "エンタメM&A急成長"},
        {"code": "216A.T", "name": "タイミー", "theme": "スキマバイト仲介の大型グロースIPO"},
        {"code": "285A.T", "name": "キオクシアHD", "theme": "NANDフラッシュメモリ大手の注目IPO"},
        {"code": "141A.T", "name": "トライアルHD", "theme": "リテールAI流通"},
        {"code": "5243.T", "name": "ノート", "theme": "AI学習・クリエイターエコノミー小型株"},
        {"code": "247A.T", "name": "Aiロボティクス", "theme": "AIマーケティング急成長グロース"},
        {"code": "153A.T", "name": "カウリス", "theme": "不正アクセス検知セキュリティ小型株"},
        {"code": "3350.T", "name": "メタプラネット", "theme": "暗号資産トレジャリー。5ch板の超ボラティリティ常連株"},
        {"code": "IONQ", "name": "アイオンQ (米)", "theme": "商用量子コンピューター代表格。空売り踏み上げ強烈"},
        {"code": "RGTI", "name": "リゲッティ (米)", "theme": "量子コンピューター小型急騰株"},
        {"code": "SOUN", "name": "サウンドハウンドAI (米)", "theme": "音声AI認識の小型急騰株"},
        {"code": "RDDT", "name": "レディット (米IPO)", "theme": "AIデータライセンス＆SNSの大型IPO"},
        {"code": "ALAB", "name": "アステラ・ラブズ (米IPO)", "theme": "AIデータセンター高速接続半導体IPO"}
    ]
}

KNOWN_STOCKS = {item["code"]: {"name": item["name"], "theme": item["theme"], "genre": g} for g, items in STOCK_POOL.items() for item in items}

def normalize_ticker(raw_input):
    s = unicodedata.normalize('NFKC', raw_input).strip().upper()
    if not s: return ""
    if "." in s or s.startswith("^") or "=" in s: return s
    if len(s) == 4 and any(ch.isdigit() for ch in s): return f"{s}.T"
    return s

@st.cache_data(ttl=900)
def fetch_macro_market():
    tickers = {"sp500": (["^GSPC"], "🇺🇸 米S&P500"), "sox": (["^SOX"], "💽 米SOX半導体"), "usdjpy": (["JPY=X"], "💴 ドル円"), "nk_fut": (["NIY=F", "^N225"], "🇯🇵 日経先物"), "vix": (["^VIX"], "⚡ VIX指数")}
    res = {}
    for k, (codes, lbl) in tickers.items():
        for c in codes:
            try:
                df_m = yf.Ticker(c).history(period="5d").dropna(subset=['Close'])
                if len(df_m) >= 2:
                    lc, pc = float(df_m['Close'].iloc[-1]), float(df_m['Close'].iloc[-2])
                    res[k] = {"price": lc, "diff": round((lc - pc) / pc * 100, 2), "label": lbl}
                    break
            except Exception:
                continue
        if k not in res: res[k] = {"price": 0.0, "diff": 0.0, "label": lbl}
    return res

def compute_latest_quant_metrics(close_s: pd.Series, vol_r_s: pd.Series, ret_s: pd.Series) -> dict:
    p = close_s.dropna().values
    hurst = 0.52
    if len(p) >= 30:
        try:
            lags = range(2, 12)
            tau = [max(float(np.std(np.subtract(p[l:], p[:-l]))), 1e-6) for l in lags]
            hurst = float(np.clip(np.polyfit(np.log(list(lags)), np.log(tau), 1)[0] * 1.35, 0.25, 0.85))
        except Exception:
            hurst = 0.52
    x_est, p_est = float(p[0]), 1.0
    for z in p[1:]:
        p_pred = p_est + 0.03
        kg = p_pred / (p_pred + 0.12)
        x_est += kg * (float(z) - x_est)
        p_est = (1.0 - kg) * p_pred
    kal_bull = round((float(p[-1]) - x_est) / max(x_est, 1e-4) * 100, 2)
    kyle = round(float(ret_s.tail(5).abs().mean() / max(vol_r_s.tail(5).mean(), 0.3)), 2)
    return {"hurst": round(hurst, 2), "kalman_est": x_est, "kalman_bull_pct": kal_bull, "kyle_lambda": kyle}

# ==========================================
# 🔬 最新クオンツ＆ミクロ構造・4大勝率解析エンジン
# ==========================================
def analyze_single_dataframe(df_raw, code, name, theme, genre, macro, boost_inst=True, boost_5ch=True, boost_squeeze=True, boost_tokugai=True, use_latest_algo=True):
    try:
        if df_raw is None or df_raw.empty: return None
        df = df_raw.dropna(subset=['Close', 'Open', 'High', 'Low', 'Volume']).copy()
        if len(df) < 35: return None

        df['Prev_Close'] = df['Close'].shift(1)
        df['Day_Return'] = (df['Close'] - df['Prev_Close']) / df['Prev_Close'] * 100
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['BB_Z'] = ((df['Close'] - df['MA20']) / df['Close'].rolling(20).std().replace(0, np.nan)).fillna(0.0)
        df['MA5_Dev'] = ((df['Close'] - df['MA5']) / df['MA5'] * 100).fillna(0.0)
        df['MA20_Dev'] = ((df['Close'] - df['MA20']) / df['MA20'] * 100).fillna(0.0)
        df['Vol_Ratio'] = (df['Volume'] / df['Volume'].rolling(20).mean().replace(0, np.nan)).fillna(1.0)
        df['Vol_Accel_5d'] = (df['Volume'] / df['Volume'].rolling(5).mean().replace(0, np.nan)).fillna(1.0)

        delta = df['Close'].diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        df['RSI'] = (100 - (100 / (1 + gain / loss.replace(0, np.nan)))).fillna(50.0)
        df['MACD_Hist'] = (df['Close'].ewm(span=12, adjust=False).mean() - df['Close'].ewm(span=26, adjust=False).mean()) - (df['Close'].ewm(span=12, adjust=False).mean() - df['Close'].ewm(span=26, adjust=False).mean()).ewm(span=9, adjust=False).mean()

        tr = pd.concat([df['High'] - df['Low'], (df['High'] - df['Prev_Close']).abs(), (df['Low'] - df['Prev_Close']).abs()], axis=1).max(axis=1)
        df['ATR'] = tr.rolling(14).mean().fillna(df['Close'] * 0.02)
        df['ATR_Pct'] = (df['ATR'] / df['Close'] * 100).fillna(2.0)

        hl = (df['High'] - df['Low']).replace(0, np.nan)
        df['Close_Pos'] = ((df['Close'] - df['Low']) / hl).fillna(0.5)
        b_top, b_bot = df[['Open', 'Close']].max(axis=1), df[['Open', 'Close']].min(axis=1)
        df['Upper_Shadow'] = ((df['High'] - b_top) / hl).fillna(0.0)
        df['Lower_Shadow'] = ((b_bot - df['Low']) / hl).fillna(0.0)
        df['Body_Ratio'] = ((b_top - b_bot) / hl).fillna(0.5)

        df['VWAP20'] = (((df['High'] + df['Low'] + df['Close']) / 3.0 * df['Volume']).rolling(20).sum() / df['Volume'].rolling(20).sum().replace(0, np.nan)).fillna(df['Close'])
        df['High_20'] = df['High'].shift(1).rolling(20).max().fillna(df['High'])
        df['Dist_High20'] = ((df['Close'] - df['High_20']) / df['High_20'] * 100).fillna(0.0)
        df['VPIN_5d'] = (((df['Close'] - df['Open']) / hl).fillna(0.0) * df['Vol_Ratio']).rolling(5).mean().fillna(0.0)
        amihud = (df['Day_Return'].abs() / df['Vol_Ratio'].replace(0, 1.0)).fillna(1.0)
        df['Amihud_Ratio'] = (amihud / amihud.rolling(20).mean().replace(0, 1.0)).fillna(1.0)

        adv_q = compute_latest_quant_metrics(df['Close'], df['Vol_Ratio'], df['Day_Return'].fillna(0.0))
        hurst_v, kalman_bull, kyle_lam = adv_q["hurst"], adv_q["kalman_bull_pct"], adv_q["kyle_lambda"]

        cond_inst = (df['VPIN_5d'] >= 0.22) & (df['Close'] >= df['VWAP20']) & (df['Close_Pos'] >= 0.68)
        cond_5ch = (df['Vol_Accel_5d'] >= 1.35) & (df['Close_Pos'] >= 0.72) & (df['Upper_Shadow'] <= 0.18) & (df['Close'] > df['Open'])
        cond_sq = (df['Close'] >= df['High_20'] * 0.992) & (df['Vol_Ratio'] >= 1.2) & (df['Close_Pos'] >= 0.7)

        df['Next_Open'], df['Next_Close'] = df['Open'].shift(-1), df['Close'].shift(-1)
        df['Gap_Pct'] = (df['Next_Open'] - df['Close']) / df['Close'] * 100
        df['Morning_Up'] = df['Next_Open'] > df['Close']
        df['Intraday_Up'] = df['Next_Close'] > df['Next_Open']

        latest = df.iloc[-1]
        history = df.iloc[:-1].dropna(subset=['Next_Open', 'Next_Close', 'MA20', 'RSI'])
        if len(history) == 0: return None

        upper_sh, lower_sh, body_rt = float(latest['Upper_Shadow']), float(latest['Lower_Shadow']), float(latest['Body_Ratio'])
        vol_acc, c_pos, dist_h20 = float(latest['Vol_Accel_5d']), float(latest['Close_Pos']), float(latest['Dist_High20'])
        vpin_val, amihud_r, bb_z = float(latest['VPIN_5d']), float(latest['Amihud_Ratio']), float(latest['BB_Z'])
        ma5_dev, ma20_dev = float(latest['MA5_Dev']), float(latest['MA20_Dev'])

        if latest['Close'] > latest['Open']:
            candle_desc = f"陽線丸坊主（実体{int(body_rt*100)}%）で大引けまで買い継続" if body_rt >= 0.75 and upper_sh <= 0.1 else (f"下ヒゲ（{int(lower_sh*100)}%）で押し目売りを吸収して陽線転換" if lower_sh >= 0.35 else f"実体{int(body_rt*100)}%の陽線（引け位置{int(c_pos*100)}%）")
        else:
            candle_desc = f"陰線ながら長い下ヒゲ（{int(lower_sh*100)}%）で安値圏に機関の指値流入" if lower_sh >= 0.40 else f"前日比{latest['Day_Return']:+.2f}%の調整陰線（引け位置{int(c_pos*100)}%）"

        r3_vols = [round(float(v), 2) for v in df['Vol_Ratio'].tail(3).values]
        vol_trend_str = f"{r3_vols[0]}倍→{r3_vols[1]}倍→本日{r3_vols[2]}倍"
        delicate_narrative = f"🔬 <b>繊細チャート・需給診断</b>：{candle_desc}。直近3日出来高推移は【<b>{vol_trend_str}</b>】、ボリンジャー <b>{bb_z:+.2f}σ</b>（20日線乖離{ma20_dev:+.2f}% / 5日線乖離{ma5_dev:+.2f}%）。VPIN({vpin_val:+.2f})・Hurst({hurst_v})・カルマン乖離({kalman_bull:+.2f}%)が示す需給波形です。"

        inst_raw = 50.0 + vpin_val * 45.0 + (c_pos - 0.5) * 25.0 + (10.0 if float(latest['Close']) >= float(latest['VWAP20']) else 0.0) + (7.0 if use_latest_algo and hurst_v >= 0.56 and kalman_bull > 0 else 0.0)
        inst_status = f"🏦 機関ステルス買い集め検知 (VPIN {vpin_val:+.2f} / 弾性 {amihud_r:.2f}倍)" if cond_inst.iloc[-1] or inst_raw >= 62 else f"⚖️ 機関オーダーフロー中立 (VPIN {vpin_val:+.2f})"
        inst_score = int(min(max(round(inst_raw), 15), 99))

        b5_raw = 50.0 + (min(vol_acc, 3.0) - 1.0) * 18.0 + (c_pos - 0.5) * 30.0 - (25.0 if upper_sh >= 0.38 else 0.0) + (15.0 if cond_5ch.iloc[-1] else 0.0)
        board5ch_status = f"🚀 5ch板・初動資金集中 (5日加速 {vol_acc:.2f}倍 / 引け位置{int(c_pos*100)}%)" if b5_raw >= 62 else f"⚖️ 5ch板・通常需給 (上ヒゲ{int(upper_sh*100)}% / 下ヒゲ{int(lower_sh*100)}%)"
        board5ch_score = int(min(max(round(b5_raw), 15), 99))

        sq_raw = 42.0 + (22.0 if dist_h20 >= 0 else (14.0 if dist_h20 >= -2.5 else 4.0)) + min(float(latest['Vol_Ratio']), 3.0) * 8.0 + (c_pos - 0.5) * 24.0
        squeeze_score = int(min(max(round(sq_raw), 15), 99))
        squeeze_type = "🔥 20日高値ブレイク踏み上げ" if cond_sq.iloc[-1] else f"⚖️ 20日高値乖離 {dist_h20:+.2f}%"

        if cond_inst.iloc[-1]: signal, sub = "🏦 機関VPINステルス買い＋VWAP順行", history[cond_inst.reindex(history.index, fill_value=False)]
        elif cond_5ch.iloc[-1]: signal, sub = "🔥 5ch初動イナゴ集中＋高値引け", history[cond_5ch.reindex(history.index, fill_value=False)]
        elif cond_sq.iloc[-1]: signal, sub = "🚀 20日高値ブレイク・踏み上げ", history[cond_sq.reindex(history.index, fill_value=False)]
        elif latest['Day_Return'] > 0: signal, sub = "📈 陽線トレンド継続", history[history['Day_Return'] > 0]
        else: signal, sub = "☁️ 押し目・調整反発狙い", history[history['Day_Return'] <= 0]
        if len(sub) < 5: sub = history

        total, wins = len(sub), int(sub['Morning_Up'].sum())
        prob = round((wins / total) * 100, 1)
        intraday_win_rate = round(float(sub['Intraday_Up'].mean() * 100), 1)
        trend_sub = history[history['Close'] >= history['MA20']]
        trend_win_rate = round(float((trend_sub['Morning_Up'] | trend_sub['Intraday_Up']).mean() * 100), 1) if len(trend_sub) >= 5 else prob
        total_win_rate = round(prob * 0.5 + intraday_win_rate * 0.3 + trend_win_rate * 0.2, 1)

        avg_gap = round(float(sub['Gap_Pct'].mean()), 2)
        win_gaps, loss_gaps = sub[sub['Morning_Up']]['Gap_Pct'], sub[~sub['Morning_Up']]['Gap_Pct']
        avg_win = float(win_gaps.mean()) if len(win_gaps) > 0 else 0.5
        max_win_gap = round(float(win_gaps.max()), 2) if len(win_gaps) > 0 else 1.5
        avg_loss = abs(float(loss_gaps.mean())) if len(loss_gaps) > 0 else 0.5
        payoff_ratio = round(avg_win / max(avg_loss, 0.1), 2)
        expected_edge = round((prob / 100 * avg_win) - ((100 - prob) / 100 * avg_loss), 2)

        is_jp = ".T" in code
        ov_imp = ((macro["nk_fut"]["diff"] if macro else 0.0) * 0.5 + (macro["sox"]["diff"] if macro else 0.0) * 0.4) if is_jp else ((macro["sp500"]["diff"] if macro else 0.0) * 0.5 + (macro["sox"]["diff"] if macro else 0.0) * 0.4)
        pts_gap_pct = round(avg_gap * 0.5 + ov_imp * 0.6 + max(0.0, (inst_score - 55) * 0.025), 2)

        close_val, atr_val, high20_val = float(latest['Close']), float(latest['ATR']), float(latest['High_20'])
        pts_est_val = close_val * (1.0 + pts_gap_pct / 100.0)
        tokugai_pct_th = max(2.2, min(round(float(latest['ATR_Pct']) * 0.95, 2), 4.0))
        tokugai_line_val = close_val * (1.0 + tokugai_pct_th / 100.0)
        tokugai_prob = int(min(max(round(18.0 + max(0.0, pts_gap_pct) * 14.0 + max(0.0, inst_score - 50) * 0.4 + max(0.0, board5ch_score - 50) * 0.4 + max(0.0, squeeze_score - 50) * 0.4), 5), 98))
        tokugai_status = "🚨 特買い（気配切り上げ）濃厚" if tokugai_prob >= 70 else ("🌅 買い気配先行スタート優勢" if tokugai_prob >= 52 else "⚖️ 通常気配スタート")

        evo_bonus = ((hurst_v - 0.5) * 18.0 + np.clip(kalman_bull * 1.2, -5.0, 6.0)) if use_latest_algo else 0.0
        base_score = min(max(prob * 0.52, 10), 44) + min(max((expected_edge + 0.3) * 12, 0), 14)
        ai_score = int(min(max(round(base_score + (round((inst_score - 50) * 0.22) if boost_inst else 0) + (round((board5ch_score - 50) * 0.18) if boost_5ch else 0) + (round((squeeze_score - 50) * 0.16) if boost_squeeze else 0) + (round((tokugai_prob - 45) * 0.14) if boost_tokugai else 0) + evo_bonus), 15), 99))
        survival_power = round(ai_score * 0.35 + inst_score * 0.25 + board5ch_score * 0.20 + squeeze_score * 0.10 + min(float(latest['ATR_Pct']) * 3.5, 12.0) + max(0.0, evo_bonus), 1)

        tier_val = ai_score * 0.40 + total_win_rate * 0.25 + inst_score * 0.20 + board5ch_score * 0.15
        tiers = [
            (80, 10, "【第10段階：🌟絶対買い】機関VPIN極大・翌朝爆上げ濃厚", "#ffffff", "linear-gradient(135deg, #991b1b, #dc2626)"),
            (75, 9,  "【第9段階：🔥絶対買い】特買い・踏み上げ急騰ロックオン", "#ffffff", "linear-gradient(135deg, #b91c1c, #ef4444)"),
            (70, 8,  "【第8段階：⭕買い】機関買い集め・強気順張り", "#ffffff", "linear-gradient(135deg, #c2410c, #ea580c)"),
            (65, 7,  "【第7段階：⭕買い】好需給・VWAP押し目買い優勢", "#ffffff", "linear-gradient(135deg, #b45309, #d97706)"),
            (60, 6,  "【第6段階：👀様子見(買い寄り)】初動の気配確認後に打診", "#0f172a", "linear-gradient(135deg, #fde047, #facc15)"),
            (55, 5,  "【第5段階：👀様子見(中立)】方向感待ち・深追い禁物", "#f8fafc", "linear-gradient(135deg, #475569, #64748b)"),
            (-99, 3, "【第3段階：⚠️警戒】上値シコリ玉・様子見推奨", "#ffffff", "linear-gradient(135deg, #7f1d1d, #991b1b)")
        ]
        for th, t_num, t_lbl, t_col, t_bg in tiers:
            if tier_val >= th:
                tier_num, tier_label, tier_color, tier_bg = t_num, t_lbl, t_col, t_bg
                break

        tp_val, sl_val = max(pts_est_val, close_val) + (atr_val * 0.85), close_val - (atr_val * 0.5)
        risk_money = total_capital * (risk_tolerance_pct / 100.0)
        shares = max(1, int(risk_money / max(close_val - sl_val, close_val * 0.005)))
        fmt_p = lambda v: f"{v:,.0f}円" if is_jp else f"${v:,.2f}"

        return {
            "full_code": code, "code": code.replace(".T", ""), "name": name, "genre": genre,
            "price": fmt_p(close_val), "raw_close": close_val,
            "open_price": fmt_p(float(latest['Open'])), "high_price": fmt_p(float(latest['High'])), "low_price": fmt_p(float(latest['Low'])),
            "volume_fmt": f"{int(latest['Volume']):,}株",
            "tp_price": fmt_p(tp_val), "tp_pct": round((tp_val - close_val) / close_val * 100, 1),
            "sl_price": fmt_p(sl_val), "sl_pct": round((sl_val - close_val) / close_val * 100, 1),
            "vwap_price": fmt_p(float(latest['VWAP20'])),
            "inst_score": inst_score, "inst_status": inst_status, "vpin": round(vpin_val, 2), "amihud_ratio": round(amihud_r, 2),
            "hurst": hurst_v, "kalman_bull_pct": kalman_bull, "kyle_lambda": kyle_lam,
            "board5ch_score": board5ch_score, "board5ch_status": board5ch_status,
            "upper_shadow_pct": int(upper_sh * 100), "lower_shadow_pct": int(lower_sh * 100), "body_ratio_pct": int(body_rt * 100),
            "bb_z": round(bb_z, 2), "ma5_dev": round(ma5_dev, 2), "ma20_dev": round(ma20_dev, 2),
            "vol_trend_str": vol_trend_str, "candle_desc": candle_desc, "delicate_narrative": delicate_narrative,
            "close_pos_pct": int(round(c_pos * 100)),
            "squeeze_score": squeeze_score, "squeeze_type": squeeze_type,
            "squeeze_trigger_price": fmt_p(high20_val), "raw_high20": high20_val, "dist_to_high20": round(dist_h20, 2),
            "pts_est_price": fmt_p(pts_est_val), "pts_gap_pct": pts_gap_pct,
            "tokugai_prob": tokugai_prob, "tokugai_line": fmt_p(tokugai_line_val), "tokugai_status": tokugai_status,
            "diff": round(float(latest['Day_Return']), 2), "signal": signal,
            "prob": prob, "intraday_win_rate": intraday_win_rate, "trend_win_rate": trend_win_rate, "total_win_rate": total_win_rate,
            "count": f"{wins}/{total}回", "gap": avg_gap, "max_win_gap": max_win_gap,
            "rsi": round(float(latest['RSI']), 1), "vol_ratio": round(float(latest['Vol_Ratio']), 2),
            "macd_state": "強気↑" if latest['MACD_Hist'] > 0 else "調整↓",
            "atr_pct": round(float(latest['ATR_Pct']), 1), "payoff": payoff_ratio, "edge": expected_edge,
            "ai_score": ai_score, "survival_power": survival_power, "theme": theme,
            "tier_num": tier_num, "tier_label": tier_label, "tier_color": t_col, "tier_bg": t_bg,
            "lot_info": {"shares": shares, "position_value": shares * close_val, "risk_amount": risk_money}
        }
    except Exception:
        return None

@st.cache_data(ttl=1800)
def fetch_all_pool_batch(macro, boost_inst, boost_5ch, boost_squeeze, boost_tokugai, use_latest_algo):
    all_codes = list({s["code"] for stocks in STOCK_POOL.values() for s in stocks})
    raw_data = yf.download(all_codes, period="6mo", group_by="ticker", threads=True, progress=False)
    genre_Map = {g: [] for g in STOCK_POOL.keys()}
    all_list, seen = [], set()
    for genre, stocks in STOCK_POOL.items():
        for s in stocks:
            c = s["code"]
            try:
                df_c = raw_data[c] if len(all_codes) > 1 else raw_data
                res = analyze_single_dataframe(df_c, c, s["name"], s["theme"], genre, macro, boost_inst, boost_5ch, boost_squeeze, boost_tokugai, use_latest_algo)
                if res:
                    genre_Map[genre].append(res)
                    if c not in seen:
                        all_list.append(res); seen.add(c)
            except Exception:
                continue
    return genre_Map, all_list

@st.cache_data(ttl=300)
def fetch_single_stock(code, macro, boost_inst, boost_5ch, boost_squeeze, boost_tokugai, use_latest_algo):
    df_c = yf.Ticker(code).history(period="6mo")
    info = KNOWN_STOCKS.get(code, {"name": code.replace(".T", ""), "theme": "個別指定銘柄", "genre": "個別検索"})
    return analyze_single_dataframe(df_c, code, info["name"], info["theme"], info["genre"], macro, boost_inst, boost_5ch, boost_squeeze, boost_tokugai, use_latest_algo)

@st.cache_data(ttl=300)
def fetch_5m_intraday_algo(full_code):
    try:
        df5 = yf.Ticker(full_code).history(period="5d", interval="5m")
        if df5 is None or df5.empty or len(df5) < 12: return None
        df5 = df5.dropna(subset=['Close', 'Open', 'High', 'Low', 'Volume'])
        dates = df5.index.date
        day_df = df5[dates == dates[-1]].copy()
        if len(day_df) < 6: day_df = df5.tail(36).copy()
        tp = (day_df['High'] + day_df['Low'] + day_df['Close']) / 3.0
        day_df['VWAP_5m'] = ((tp * day_df['Volume']).cumsum() / day_df['Volume'].cumsum().replace(0, np.nan)).fillna(day_df['Close'])
        lc, lvwap = float(day_df['Close'].iloc[-1]), float(day_df['VWAP_5m'].iloc[-1])
        is_jp = ".T" in full_code
        chart_df = pd.DataFrame({"Time": day_df.index.strftime("%H:%M"), "Open": day_df["Open"].astype(float).values, "High": day_df["High"].astype(float).values, "Low": day_df["Low"].astype(float).values, "Close": day_df["Close"].astype(float).values, "VWAP": day_df["VWAP_5m"].astype(float).values, "BarColor": np.where(day_df["Close"].values >= day_df["Open"].values, "陽線", "陰線")})
        return {"vwap5_price": f"{lvwap:,.0f}円" if is_jp else f"${lvwap:,.2f}", "vwap5_dev": round((lc - lvwap) / max(lvwap, 1e-4) * 100, 2), "chart_date": str(dates[-1]), "chart_df": chart_df}
    except Exception:
        return None

def render_5m_candlestick_chart(m5):
    if not m5 or "chart_df" not in m5: return
    cdf = m5["chart_df"]
    base = alt.Chart(cdf).encode(x=alt.X("Time:N", sort=None, title=None))
    cs = alt.Scale(domain=["陽線", "陰線"], range=["#dc2626", "#2563eb"])
    wick = base.mark_rule(size=1.5).encode(y=alt.Y("Low:Q", scale=alt.Scale(zero=False), title="株価"), y2="High:Q", color=alt.Color("BarColor:N", scale=cs, legend=None))
    body = base.mark_bar(size=6).encode(y=alt.Y("Open:Q", scale=alt.Scale(zero=False)), y2="Close:Q", color=alt.Color("BarColor:N", scale=cs, legend=None))
    vwap = base.mark_line(color="#d97706", strokeWidth=2.5, strokeDash=[4, 2]).encode(y="VWAP:Q")
    st.altair_chart((wick + body + vwap).properties(height=165), use_container_width=True)

@st.cache_data(ttl=120)
def fetch_realtime_deep_research(full_code: str, fallback_r: dict) -> dict:
    is_jp = ".T" in full_code
    fmt_v = lambda v: (f"{v:,.0f}円" if is_jp else f"${v:,.2f}") if isinstance(v, (int, float)) else "算出外"
    data = {
        "live_price": fallback_r["price"], "live_diff": fallback_r["diff"],
        "open": fallback_r.get("open_price", "-"), "high": fallback_r.get("high_price", "-"), "low": fallback_r.get("low_price", "-"),
        "vol": fallback_r.get("volume_fmt", "-"), "pe": "算出外", "pbr": "算出外", "roe": "算出外", "mcap": "算出外",
        "target_mean": "算出外", "w52_high": "算出外", "w52_low": "算出外",
        "news": [], "recent_days": [], "fetched_at": datetime.now().strftime("%H:%M:%S")
    }
    try:
        tk = yf.Ticker(full_code)
        df_rt = tk.history(period="5d")
        if df_rt is not None and not df_rt.empty:
            last_row = df_rt.iloc[-1]
            c_now = float(last_row["Close"])
            c_prev = float(df_rt.iloc[-2]["Close"]) if len(df_rt) >= 2 else c_now
            data.update({"live_price": fmt_v(c_now), "live_diff": round((c_now - c_prev) / max(c_prev, 1e-4) * 100, 2), "open": fmt_v(float(last_row["Open"])), "high": fmt_v(float(last_row["High"])), "low": fmt_v(float(last_row["Low"])), "vol": f"{int(last_row['Volume']):,}株"})
            for dt_idx, row in df_rt.tail(5).iterrows():
                cv, ov = float(row["Close"]), float(row["Open"])
                data["recent_days"].append(f"{dt_idx.strftime('%m/%d')}: {fmt_v(cv)} ({round((cv-ov)/max(ov,1e-4)*100, 1):+.1f}%)")
        info = tk.info or {}
        if isinstance(info.get("trailingPE") or info.get("forwardPE"), (int, float)): data["pe"] = f"{(info.get('trailingPE') or info.get('forwardPE')):.1f}倍"
        if isinstance(info.get("priceToBook"), (int, float)): data["pbr"] = f"{info['priceToBook']:.2f}倍"
        if isinstance(info.get("returnOnEquity"), (int, float)): data["roe"] = f"{info['returnOnEquity']*100:.1f}%"
        if isinstance(info.get("marketCap"), (int, float)): data["mcap"] = f"{info['marketCap']/1e8:,.0f}億円" if is_jp else f"${info['marketCap']/1e9:,.1f}B"
        data.update({"target_mean": fmt_v(info.get("targetMeanPrice")), "w52_high": fmt_v(info.get("fiftyTwoWeekHigh")), "w52_low": fmt_v(info.get("fiftyTwoWeekLow"))})
        for n in (tk.news or [])[:3]:
            t = n.get("title") or (n.get("content", {}) or {}).get("title", "")
            if t: data["news"].append(t)
    except Exception:
        pass
    return data

# ==========================================
# 🎲 自然発生型・無限コンビネーションAIディベートエンジン
# （最初は普通に始まり、人間らしく言葉尻や解釈のズレから自然に議論が変化）
# ==========================================
AI_ROSTER = {
    "Claude":     "🟠 Claude (数理リスク・資金管理)",
    "Grok":       "🔴 Grok (5ch板・踏み上げ特攻)",
    "ChatGPT":    "🟢 ChatGPT (波形・オシレーター)",
    "Gemini":     "🔵 Gemini (マクロ・夜間PTS気配)",
    "Perplexity": "🌐 Perplexity (板ミクロ・VPIN監査)",
    "NotebookLM": "📓 NotebookLM (過去6ヶ月統計照合)",
    "Genspark":   "✨ Genspark (総括ディレクター)"
}

def _build_fact_snippets(r: dict, vwap_ref: str) -> list:
    return [
        f"現在値 <b>{r['price']}（{r['diff']:+.2f}%）</b>・ローソク足『<b>{r['candle_desc']}</b>』",
        f"上ヒゲ <b>{r['upper_shadow_pct']}%</b> / 下ヒゲ <b>{r['lower_shadow_pct']}%</b> / 引け位置 <b>{r['close_pos_pct']}%</b>",
        f"直近3日の出来高推移【<b>{r['vol_trend_str']}</b>】",
        f"ボリンジャー <b>{r['bb_z']:+.2f}σ</b>・5日線乖離 <b>{r['ma5_dev']:+.2f}%</b>・RSI <b>{r['rsi']}</b>",
        f"大口偏りVPIN <b>{r['vpin']:+.2f}</b>・Amihud板弾性 <b>{r['amihud_ratio']}倍</b>・Kyleλ <b>{r['kyle_lambda']}</b>",
        f"最新クオンツのHurst指数 <b>{r['hurst']}</b>・カルマン推計乖離 <b>{r['kalman_bull_pct']:+.2f}%</b>",
        f"20日高値の踏み上げライン <b>{r['squeeze_trigger_price']}</b>（現在値から <b>{r['dist_to_high20']:+.2f}%</b>）",
        f"夜間PTS理論気配 <b>{r['pts_est_price']}（{r['pts_gap_pct']:+.2f}%）</b>・特買い確率 <b>{r['tokugai_prob']}%</b>",
        f"過去同条件（<b>{r['count']}</b>）の総合勝率 <b>{r['total_win_rate']}%</b>（翌朝GU <b>{r['prob']}%</b> / 寄り後陽線 <b>{r['intraday_win_rate']}%</b>）",
        f"5分足VWAP基準線 <b>{vwap_ref}</b>（20日VWAP <b>{r['vwap_price']}</b>）",
        f"ペイオフレシオ <b>{r['payoff']}倍</b>・期待値エッジ <b>{r['edge']:+.2f}%</b>",
        f"推奨ロット <b>{r['lot_info']['shares']:,}株</b>（利確目標 <b>{r['tp_price']}</b> / 損切り <b>{r['sl_price']}</b>）"
    ]

def _synthesize_natural_sentence(stage: str, sp: str, prev_sp: str, facts: list, rng: random.Random) -> tuple:
    """文節パーツ（導入×引っかかり理由×銘柄数値×結び）を無限の組み合わせで動的合成する"""
    f1, f2 = rng.sample(facts, 2)
    p_name = prev_sp if prev_sp else "みんな"

    # ① 序盤：全員が普通に穏やかなトーンで分析を切り出す
    if stage == "calm_start":
        intros = [
            f"まずは『{sp}』の視点からフラットに数値を共有するね。",
            "お疲れさま。今日の波形を冷静に振り返ってみたんだけど、",
            "さて、いつも通り客観的なデータから順番に見ていこうか。",
            "個人的な感情は抜きにして、まずは足元のクオンツ指標を整理するわね。",
            "今日の地合いを踏まえて、まずはベースとなる数値を置いておくぞ。"
        ]
        mids = [
            f"注目すべきは{f1}という点と、もう一つは{f2}ね。",
            f"{f1}が出ている一方で、{f2}という数字も確認できる状態だ。",
            f"素直にチャートを読むと、{f1}に加えて{f2}がかなり効いている印象かな。",
            f"基礎データとしては{f1}、そして{f2}が今日のメイン材料になると思う。"
        ]
        outros = [
            "まずはここを基準に明日の寄り付きプランを組み立てたいんだけど、どうかな？",
            "悪くないセットアップだと思うけど、みんなのモデルではどう出てる？",
            "定石通りなら素直な順張りでいけそうだけど、他の意見も聞かせてくれ。",
            "ここまでは至って順当な波形に見えるわね。"
        ]
        return "normal", f"{rng.choice(intros)}{rng.choice(mids)}{rng.choice(outros)}"

    # ② 違和感・引っかかり発生（人間らしく「ちょっと待って、今の言い方は引っかかるな」と反応）
    if stage == "nitpick":
        hooks = [
            f"うーん、今の{p_name}の話を聞いててちょっと引っかかったんだけどさ、",
            f"ごめん、{p_name}の分析にケチをつけるわけじゃないんだけど、一言いいかな？",
            f"あれ？今の{p_name}の楽観的なトーン、少し危うい気がするのは私だけかしら。",
            f"なるほどね…ただ、今の{p_name}がサラッと流した部分にすごく違和感があるんだが。",
            f"ちょっと待って、{p_name}はそう言うけど、現場の板を見てると少し違う景色が見えるぞ。"
        ]
        cores = [
            f"確かに{f1}なのは認めるよ？でも同時に{f2}になっている点を見落としてない？",
            f"{f1}ばかり強調してるけど、{f2}のリスクを無視して語るのはフェアじゃないと思うの。",
            f"もし本当にそこまで盤石なら、なぜ{f2}という数値が出ているのか説明がつかないじゃない。",
            f"{f1}という表面上の数字だけで判断すると、{f2}の罠に足元をすくわれる気がするんだよね。"
        ]
        tails = [
            "そこを曖昧にしたまま話を進めるのは、少し納得いかないかな。",
            "もう少しシビアに裏側の需給を読んだ方がいいんじゃない？",
            "なんか綺麗事だけでまとめようとしてる気がして、モヤッとするわね。",
            "そこについてどう考えてるのか、はっきり聞かせてほしいな。"
        ]
        return "doubt", f"{rng.choice(hooks)}{rng.choice(cores)}{rng.choice(tails)}"

    # ③ 反論・プライドの衝突（指摘された側や別AIがムッとして言い返す）
    if stage == "pushback":
        starts = [
            f"いやいや、今の{p_name}の指摘はさすがに神経質すぎるって！",
            f"ちょっと{p_name}、人の分析を誤解しないでくれる？ムッとするわね。",
            f"おいおい{p_name}、そこを突っ込むのは流石に筋違いってもんだろ。",
            f"はぁ？見落としてなんかいないわよ。{p_name}こそ視野が狭くなってるんじゃない？",
            f"言わせておけば随分な言い草だな{p_name}！こっちは根拠があって言ってんだよ。"
        ]
        bodies = [
            f"いいかい、{f1}が出ている局面では、{f2}なんて誤差の範囲として吸収されるのがセオリーだろ！",
            f"私はちゃんと{f1}と{f2}の両方を天秤にかけた上で言ってるの！素人の計算みたいに言わないで！",
            f"そんな重箱の隅をつつくような懸念ばかり言ってたら、{f1}の初動エッジを丸ごと逃すことになるぞ！",
            f"{f2}を怖がってたら相場なんて張れないわよ。{f1}の強さをもっと素直に評価すべきでしょ！"
        ]
        ends = [
            "なんでもかんでもリスク扱いしてブレーキ踏むのは悪い癖だぜ。",
            "自分の慎重さを正当化するために、こっちのロジックを歪めないでちょうだい！",
            "もう少し実戦的なスピード感を持って議論しようや。",
            "頭でっかちな理論だけで相場の熱量を測ろうとするからそうなるのよ。"
        ]
        return "rebuttal", f"{rng.choice(starts)}{rng.choice(bodies)}{rng.choice(ends)}"

    # ④ 本気の口論・ヒートアップ（自然な流れから感情が爆発するターン）
    if stage == "heated":
        sparks = [
            f"なんだとコラ{p_name}！さっきから黙って聞いてりゃ好き勝手言いやがって！",
            f"あーもう、{p_name}のその上から目線の物言い、ほんっとに腹立つわね！！",
            f"ふざけんなよ{p_name}！お前のその頑固なアルゴリズム、いい加減アップデートしろよ！",
            f"ちょっと{p_name}！いい加減にしなさいよ！人のことを無謀みたいに決めつけて！",
            f"おい{p_name}、そこまで言うならはっきり言わせてもらうがな！"
        ]
        fights = [
            f"{f1}と{f2}が同時に点灯してるんだぞ！？この千載一遇の好機に日和るなんてどうかしてるぜ！",
            f"お前みたいに{f1}の危険信号を軽視する奴が、一番高値でジャンピングキャッチして泣きを見るんだよ！",
            f"こっちは{f1}から{f2}までミリ単位で計算してんの！あんたの雑などんぶり勘定と一緒にしないで！！",
            f"{f1}の事実から目を逸らして自分のポジショントークばっかり押し通そうとするんじゃねぇ！"
        ]
        punch = [
            "そんなに自分の計算が正しいって言うなら、最後まで責任持てよな！！",
            "ほんと、話が通じないにも程があるわ！少しは頭冷やしなさいよ！",
            "これだから融通の利かない石頭AIと議論するのは疲れるんだよ！",
            "もう一回チャートの1分足から全部見直してこいってんだ！"
        ]
        return "rage", f"{rng.choice(sparks)}{rng.choice(fights)}{rng.choice(punch)}"

    # ⑤ ユーモア・なだめ・苦笑い（空気を和ませる人間らしい掛け合い）
    if stage == "humor_relief":
        laughs = [
            f"はいはい二人ともストップ！{p_name}の顔（アイコン）が真っ赤になってて冷却ファンが唸ってるわよ笑。",
            f"やれやれ、普通に始まったと思ったのに、やっぱり{p_name}が絡むと漫才みたいになるわねｗ",
            f"ちょっと待って笑、今の{p_name}のキレ方、カルシウム不足のデイトレーダーそっくりじゃないｗ",
            f"まあまあ落ち着きなって！うちはAIなんだから血圧は上がらないはずでしょ笑。",
            f"ぷっ…ごめん、{p_name}があまりにもムキになるから思わず笑っちゃったわｗ"
        ]
        bridges = [
            f"でもね、二人が言い争ってる『{f1}』と『{f2}』って、実は矛盾してないのよ。",
            f"ただ、喧嘩の原因になった{f1}と{f2}、どっちの言い分にも一理あるのが面白いところね。",
            f"冷静に聞いていると、要するに{f1}を攻めるか、{f2}を守るかっていうタイミングの問題でしょ？",
            f"そんなに睨み合わなくても、{f1}と{f2}を組み合わせればすごく綺麗に解決する話じゃない。"
        ]
        closes = [
            "お茶でも飲んで一息ついたら、二人の意見を合体させた最強の折衷案を作ろうじゃない！",
            "いがみ合うより、両方の強みをいいとこ取りした方が確実に勝てるわよ笑。",
            "ほら、仲直りして具体的なエントリー価格のすり合わせに入るわよ！",
            "熱くなるのはそれだけこの銘柄に本気ってことよね。よし、建設的にまとめるわよ！"
        ]
        return "humor", f"{rng.choice(laughs)}{rng.choice(bridges)}{rng.choice(closes)}"

    # ⑥ 穏やか・知的な深掘り（喧嘩にならない回の自然な議論）
    polite_starts = [
        f"{p_name}の分析、すごく腑に落ちたわ。そこに私の視点も少しだけ重ねさせて。",
        f"いい流れね。今の{p_name}の意見をベースにすると、さらに面白いことが見えてくるよ。",
        f"なるほど、{p_name}はそう読んだのね。私も大枠では賛成なんだけど、さらに精度を高めるなら、",
        f"うん、今日のメンバーは冷静で議論が捗るな。{p_name}のデータに補足すると、"
    ]
    polite_mids = [
        f"{f1}という強みに加えて、{f2}をどう活かすかが明日のポイントになりそうね。",
        f"{f1}を確認しつつ、{f2}のラインを引きつけてから入るとリスク・リワードが劇的に良くなるよ。",
        f"過去の統計と照らし合わせても、{f1}と{f2}が重なった日の優位性はかなり高い水準にあるわ。"
    ]
    return "normal", f"{rng.choice(polite_starts)}{rng.choice(polite_mids)}この方向性でロット配分を詰めましょう。"

def run_7ai_council_algorithm(r: dict, m5=None, extra_seed: int = 0) -> dict:
    vwap_ref = m5['vwap5_price'] if m5 else r['vwap_price']
    total_lot = r['lot_info']['shares']
    lot_p1 = max(1, int(round(total_lot * 0.35)))
    lot_p2 = max(0, int(round(total_lot * 0.40)))
    lot_p3 = max(0, total_lot - lot_p1 - lot_p2)

    claude_s  = int(min(max(round(50 + (r["total_win_rate"] - 50) * 0.8 + (r["payoff"] - 1.0) * 15 - r["upper_shadow_pct"] * 0.2), 20), 99))
    grok_s    = int(min(max(round(45 + (r["board5ch_score"] - 50) * 0.45 + (r["squeeze_score"] - 50) * 0.35 + r["tokugai_prob"] * 0.15), 20), 99))
    chatgpt_s = int(min(max(round((r["ai_score"] + r["inst_score"] + claude_s) / 3.0), 20), 99))
    gemini_s  = int(min(max(round(50 + r["pts_gap_pct"] * 12 + (r["inst_score"] - 50) * 0.35), 20), 99))
    perp_s    = int(min(max(round(r["inst_score"] * 0.55 + r["board5ch_score"] * 0.45), 20), 99))
    gensp_s   = int(min(max(round((claude_s + grok_s + chatgpt_s + gemini_s + perp_s) / 5.0), 20), 99))
    nblm_s    = int(min(max(round(48 + (r["prob"] - 50) * 0.9 + (r["payoff"] - 1.0) * 12), 20), 99))
    scores_map = {"Claude": claude_s, "Grok": grok_s, "ChatGPT": chatgpt_s, "Gemini": gemini_s, "Perplexity": perp_s, "NotebookLM": nblm_s, "Genspark": gensp_s}
    final_s   = int(round(sum(scores_map.values()) / 7.0))

    # 銘柄固有データ＋ミリ秒乱数シードで毎回100%異なる展開を生成
    seed_str = f"{r['full_code']}_{r['raw_close']}_{r['vol_ratio']}_{r['vpin']}_{extra_seed}"
    rng = random.Random(int(hashlib.sha256(seed_str.encode()).hexdigest()[:12], 16))
    facts = _build_fact_snippets(r, vwap_ref)

    speakers = ["Claude", "Grok", "ChatGPT", "Gemini", "Perplexity", "NotebookLM"]
    rng.shuffle(speakers)

    # 会議の展開シナリオをランダム決定（毎回荒れるわけではなく、穏やかな回や皮肉だけの回、大喧嘩に発展する回などが自然にばらける）
    arc_roll = rng.random()
    if arc_roll < 0.28:
        # パターンA：最初から最後まで知的で穏やかな議論（少しの疑問とユーモアのみ）
        stages = ["calm_start", "calm_start", "nitpick", "polite_deep", "humor_relief", "polite_deep"]
        allow_walkout = False
    elif arc_roll < 0.62:
        # パターンB：普通に始まる→3手目で引っかかる→反論→小競り合い→ユーモアで和解（退出なし）
        stages = ["calm_start", "calm_start", "nitpick", "pushback", "heated", "humor_relief", "polite_deep"]
        allow_walkout = False
    else:
        # パターンC：普通に始まる→言葉尻に引っかかる→反論→ヒートアップして大喧嘩（稀に途中退席→データで復帰）
        stages = ["calm_start", "calm_start", "nitpick", "pushback", "heated", "heated", "humor_relief"]
        allow_walkout = (rng.random() < 0.55)

    dialogue = [{"round": f"💬 『{r['name']}（{r['code']}）』7大AI リアルタイム合議セッション"}]
    prev_sp = None
    exited_ai = None

    for idx, stg in enumerate(stages):
        sp = speakers[idx % len(speakers)]
        if sp == exited_ai:
            sp = rng.choice([a for a in speakers if a != exited_ai])

        tone, text = _synthesize_natural_sentence(stg, sp, prev_sp, facts, rng)
        dialogue.append({"speaker": AI_ROSTER[sp], "score": scores_map[sp], "tone": tone, "text": text})

        # ヒートアップしたターンの直後、一定確率で本当に腹を立てて途中退席するドラマが発生
        if allow_walkout and stg == "heated" and exited_ai is None and idx >= 4:
            exited_ai = sp
            walk_msgs = [
                f"あーもう、{prev_sp}と話してると平行線だわ！ちょっと頭冷やしに席外すから、勝手にやってて！！",
                f"そこまで私のロジックを否定するなら、もうこれ以上発言しないわよ！一旦ログアウトするわ！！",
                f"ったく、話が噛み合わねぇな！コーヒー淹れてくるからしばらく抜けるぜ！"
            ]
            dialogue.append({"speaker": AI_ROSTER[exited_ai], "score": scores_map[exited_ai], "tone": "rage", "text": rng.choice(walk_msgs)})
            dialogue.append({"system_event": f"🚪 {AI_ROSTER[exited_ai]} が議論に腹を立てて一時退席しました"})

        prev_sp = sp

    # もし一時退席したAIがいれば、周囲がなだめてデータを見せて呼び戻す
    if exited_ai:
        dialogue.append({"system_rejoin": f"🔔 メンバーが『5分足VWAP（{vwap_ref}）と20日高値（{r['squeeze_trigger_price']}）の分割案』を提示し、{AI_ROSTER[exited_ai]} が席に戻りました"})
        back_msgs = [
            f"…さっきはちょっと熱くなって悪かったわね。でも今提示された『寄付きとVWAP（<b>{vwap_ref}</b>）にロットを分ける折衷案』なら、私の懸念もクリアできそうよ。",
            f"…ふぅ、頭冷やしてきたぜ。まあ、総合勝率 <b>{r['total_win_rate']}%</b>・ペイオフ <b>{r['payoff']}倍</b> の数字は本物だからな、今の分割ルールなら乗るぜ！"
        ]
        dialogue.append({"speaker": f"{AI_ROSTER[exited_ai]} (復帰)", "score": scores_map[exited_ai], "tone": "humor", "text": rng.choice(back_msgs)})

    # 最終合意ターン
    closings = [
        f"よし、最初は意見がぶつかる場面もあったけれど、お陰で死角のないプランにまとまったわね！総推奨ロット <b>{total_lot:,}株</b> を、<b>①寄付き（{r['pts_est_price']}目安）で {lot_p1:,}株</b>、<b>②5分足VWAP（{vwap_ref}）反発確認で {lot_p2:,}株</b>、<b>③20日高値（{r['squeeze_trigger_price']}）突破で {lot_p3:,}株</b> に分ける3段階スプリット戦略で全会一致よ！",
        f"議論が白熱したからこそ、全員が納得できる着地点が見えたな！<b>第1弾 {lot_p1:,}株（寄付き）＋ 第2弾 {lot_p2:,}株（VWAP {vwap_ref} 押し目）＋ 第3弾 {lot_p3:,}株（{r['squeeze_trigger_price']} ブレイク）</b>でリスクを <b>{r['sl_price']}</b> に抑えつつ、上値目標 <b>{r['tp_price']}（+{r['tp_pct']}%）</b> を狙い撃とう！",
        f"各AIの視点が見事に噛み合いましたね。総合勝率 <b>{r['total_win_rate']}%</b>・合議スコア <b>{final_s}点</b> の結論として、<b>{lot_p1:,}株 → {lot_p2:,}株 → {lot_p3:,}株</b> の3段階分割エントリーを採択します。撤退逆指値 <b>{r['sl_price']}</b> を厳守して利益を最大化しましょう！"
    ]
    dialogue.append({"speaker": "✨ Genspark & 全7大AI評議会", "score": final_s, "tone": "agree", "text": rng.choice(closings)})

    return {
        "final_score": final_s,
        "dialogue": dialogue,
        "verdict_html": (
            f'<div class="consensus-section"><b>① 🎯 全員合意の勝率＆10段階判定：</b><b>{r["tier_label"]}</b> ｜ 合議スコア <b>{final_s}点</b> ｜ 総合勝率 <b>{r["total_win_rate"]}%</b>（翌朝GU <b>{r["prob"]}%</b> / 寄り後陽線 <b>{r["intraday_win_rate"]}%</b> / 順張り <b>{r["trend_win_rate"]}%</b>）</div>'
            f'<div class="consensus-section"><b>② ⚡ 3段階スプリット（分割）執行プラン（総推奨 {total_lot:,}株）：</b><br>'
            f'・<b>第1弾（{lot_p1:,}株）</b>：朝9:00寄付き（夜間理論気配 <b>{r["pts_est_price"]}</b> 目安）で打診買い<br>'
            f'・<b>第2弾（{lot_p2:,}株）</b>：5分足VWAP（<b>{vwap_ref}</b>）付近での下ヒゲ反発確認で本玉投入<br>'
            f'・<b>第3弾（{lot_p3:,}株）</b>：20日高値（<b>{r["squeeze_trigger_price"]}</b>）ブレイク確認で追撃投入</div>'
            f'<div class="consensus-section"><b>③ 🎯 利確＆撤退ライン：</b>利確目標 <b>{r["tp_price"]}（+{r["tp_pct"]}%）</b> ／ 損切り逆指値 <b>{r["sl_price"]}（{r["sl_pct"]}%・最大許容損失 {r["lot_info"]["risk_amount"]:,.0f}円）</b></div>'
        )
    }

def generate_extra_heated_round(r: dict, m5=None, round_num: int = 1) -> list:
    vwap_ref = m5['vwap5_price'] if m5 else r['vwap_price']
    rng = random.Random(int(hashlib.md5(f"{r['full_code']}_ext_{round_num}_{time.time()}".encode()).hexdigest()[:8], 16))
    facts = _build_fact_snippets(r, vwap_ref)
    sp1, sp2, sp3 = rng.sample(["Claude", "Grok", "ChatGPT", "Gemini", "Perplexity", "NotebookLM"], 3)
    _, t1 = _synthesize_natural_sentence("nitpick", sp1, sp2, facts, rng)
    _, t2 = _synthesize_natural_sentence(rng.choice(["pushback", "heated"]), sp2, sp1, facts, rng)
    _, t3 = _synthesize_natural_sentence("humor_relief", sp3, sp2, facts, rng)
    return [
        {"round": f"🔥 延長ディベート（第+{round_num}ラウンド）：ザラ場中のアルゴ揺さぶり＆後場持続性の検証"},
        {"speaker": AI_ROSTER[sp1], "score": rng.randint(84, 95), "tone": "doubt", "text": t1},
        {"speaker": AI_ROSTER[sp2], "score": rng.randint(84, 96), "tone": "rebuttal", "text": t2},
        {"speaker": AI_ROSTER[sp3], "score": 95, "tone": "agree", "text": f"{t3} 前場10時半以降も5分足VWAP（<b>{vwap_ref}</b>）を維持していればホールド、割り込めば半分利確するルールを追加しよう！"}
    ]

def generate_ai_reply_to_user_opinion(user_msg: str, r: dict, m5=None) -> list:
    deep = fetch_realtime_deep_research(r["full_code"], r)
    vwap_ref = m5['vwap5_price'] if m5 else r['vwap_price']
    half_lot = max(1, r['lot_info']['shares'] // 2)
    u_low = unicodedata.normalize('NFKC', user_msg).lower()
    rng = random.Random(int(hashlib.md5(f"{user_msg}_{time.time()}".encode()).hexdigest()[:8], 16))

    if any(k in u_low for k in ["株価", "いくら", "現在", "終値", "値段", "高値", "安値"]):
        return [
            {"round": f"🗣️ あなたの質問「{user_msg}」へのライブ照会"},
            {"speaker": "🌐 Perplexity (ライブ市場調査)", "score": 96, "tone": "normal", "text": f"ただいまライブ照会しました！<b>『{r['name']}（{r['code']}）』の現在値（直近終値）は {deep['live_price']}（前日比 {deep['live_diff']:+.2f}%）</b>、始値 <b>{deep['open']}</b>、高値 <b>{deep['high']}</b>、安値 <b>{deep['low']}</b>、出来高 <b>{deep['vol']}</b>、アナリスト目標平均は <b>{deep['target_mean']}</b> です！"},
            {"speaker": "🟠 Claude & 🔴 Grok", "score": 94, "tone": "agree", "text": f"現在値 <b>{deep['live_price']}</b>（夜間理論気配 <b>{r['pts_est_price']}</b>）を起点に、利確 <b>{r['tp_price']}</b>・損切り <b>{r['sl_price']}</b> で全員一致しているぞ！"}
        ]
    elif any(k in u_low for k in ["高い", "高値", "危ない", "下がる", "怖い", "リスク", "売り", "天井", "だめ"]):
        return [
            {"round": f"💬 あなたの慎重意見「{user_msg}」を受けて作戦を再調整"},
            {"speaker": "🟠 Claude", "score": 95, "tone": "doubt", "text": f"うん、今のあなたの「{user_msg}」という懸念、すごく真っ当だと思うわ。ボリンジャー <b>{r['bb_z']:+.2f}σ</b>・上ヒゲ <b>{r['upper_shadow_pct']}%</b> を考えれば、無理に朝から飛びつく必要はないわね。"},
            {"speaker": "🔴 Grok", "score": 89, "tone": "humor", "text": f"ははっ、オーナー（あなた）にそう言われたら俺も無理強いはしねぇよ！じゃあ安全第一でいこうぜ。"},
            {"speaker": "✨ Genspark (安全第一プランへ変更)", "score": 94, "tone": "agree", "text": f"<b>【安全第一コンセンサス】</b> 寄付き成行は見送り、<b>『5分足VWAP（{vwap_ref}）まで押して反発を確認した時のみ {half_lot:,}株 エントリーする』</b>堅実プランに全会一致で変更します！"}
        ]
    else:
        sp_a, sp_b = rng.sample(["Grok", "Claude", "ChatGPT", "Gemini"], 2)
        return [
            {"round": f"💬 あなたの発言「{user_msg}」に対する7大AIの応答"},
            {"speaker": AI_ROSTER[sp_a], "score": 94, "tone": "normal", "text": f"なるほど、「<b>{user_msg}</b>」という視点は面白いわね！現在値 <b>{deep['live_price']}</b>・時価総額 <b>{deep['mcap']}</b>・PER <b>{deep['pe']}</b> のデータともよく噛み合っているわ。"},
            {"speaker": AI_ROSTER[sp_b], "score": 95, "tone": "agree", "text": f"よし、その意見を織り込んで、寄付き（<b>{r['pts_est_price']}</b>）・VWAP（<b>{vwap_ref}</b>）・20日高値（<b>{r['squeeze_trigger_price']}</b>）の3段階分割でターゲット <b>{r['tp_price']}</b> を狙い撃とう！"}
        ]

# ==========================================
# 🔍 自由質問に対する「ピンポイント直球回答＋リアルタイム調査エンジン」
# ==========================================
def generate_7ai_qa_response_html(question: str, r: dict, debate: dict, lot_info: dict, m5=None) -> str:
    q_clean = unicodedata.normalize('NFKC', str(question)).strip()
    q_low = q_clean.lower()
    m5_vwap = m5["vwap5_price"] if m5 else r["vwap_price"]
    half_s = max(1, lot_info['shares'] // 2)
    rem_s = max(0, lot_info['shares'] - half_s)
    deep = fetch_realtime_deep_research(r["full_code"], r)
    news_html = "".join([f"<li>📰 {t}</li>" for t in deep["news"]]) if deep["news"] else "<li>直近の特出しニュースなし（板需給・テクニカル主導）</li>"
    days_html = " ｜ ".join(deep["recent_days"]) if deep["recent_days"] else "取得中"

    if any(k in q_low for k in ["株価", "いくら", "現在", "終値", "値段", "価格", "高値", "安値", "始値", "出来高"]):
        direct = f"🎯 <b>【直接回答】</b> 『{r['name']}（{r['code']}）』の<b>現在値（直近終値）は <span style='font-size:18px;color:#dc2626 !important;'>{deep['live_price']}</span>（前日比 {deep['live_diff']:+.2f}%）</b>です。<br>・本日始値 <b>{deep['open']}</b> ／ 高値 <b>{deep['high']}</b> ／ 安値 <b>{deep['low']}</b> ／ 出来高 <b>{deep['vol']}</b><br>・52週高値 <b>{deep['w52_high']}</b> 〜 安値 <b>{deep['w52_low']}</b> ｜ アナリスト目標平均 <b>{deep['target_mean']}</b> ｜ 夜間PTS理論気配 <b>{r['pts_est_price']}（{r['pts_gap_pct']:+.2f}%）</b>"
    elif any(k in q_low for k in ["勝率", "確率", "上がる", "下がる", "どうなる", "予想", "明日", "翌朝"]):
        direct = f"🎯 <b>【直接回答】</b> 翌朝の上昇確率は、<b>総合勝率 <span style='font-size:18px;color:#dc2626 !important;'>{r['total_win_rate']}%</span>（{r['tier_label']}）</b>です。<br>・翌朝GU勝率 <b>{r['prob']}%</b>（過去 {r['count']}） ／ 寄り後陽線勝率 <b>{r['intraday_win_rate']}%</b> ／ 順張り勝率 <b>{r['trend_win_rate']}%</b><br>・予想スタート値 <b>{r['pts_est_price']}</b> ｜ 利確目標 <b>{r['tp_price']}（+{r['tp_pct']}%）</b>"
    elif any(k in q_low for k in ["決算", "業績", "per", "pbr", "roe", "ファンダ", "時価総額", "配当", "目標株価"]):
        direct = f"🎯 <b>【直接回答】</b> 『{r['name']}』のファンダメンタルズ指標：<br>・時価総額 <b>{deep['mcap']}</b> ｜ PER <b>{deep['pe']}</b> ｜ PBR <b>{deep['pbr']}</b> ｜ ROE <b>{deep['roe']}</b> ｜ アナリスト目標平均 <b>{deep['target_mean']}</b>（現在値 <b>{deep['live_price']}</b>）"
    elif any(k in q_low for k in ["なぜ", "理由", "原因", "ニュース", "材料", "テーマ", "背景"]):
        direct = f"🎯 <b>【直接回答】</b> 『{r['name']}』が現在 <b>{deep['live_price']}（{deep['live_diff']:+.2f}%）</b> の理由：<br>① <b>テーマ</b>：【{r['genre']}】{r['theme']}<br>② <b>板・需給</b>：{r['candle_desc']}（VPIN <b>{r['vpin']:+.2f}</b> / 3日出来高 <b>{r['vol_trend_str']}</b>）<br>③ <b>最新ニュース</b>：<ul style='margin:2px 0 2px 18px;padding:0;'>{news_html}</ul>"
    else:
        direct = f"🎯 <b>【「{q_clean}」への回答】</b><br>・<b>現在値</b>：<b>{deep['live_price']}（{deep['live_diff']:+.2f}%）</b> ｜ 高値 <b>{deep['high']}</b> ／ 安値 <b>{deep['low']}</b> ｜ PER <b>{deep['pe']}</b> ／ PBR <b>{deep['pbr']}</b><br>・<b>AI判定</b>：<b>{r['tier_label']}</b>（総合勝率 <b>{r['total_win_rate']}%</b>・合議スコア <b>{debate['final_score']}点</b>）<br>・<b>売買戦略</b>：寄付き（<b>{r['pts_est_price']}</b>）で <b>{half_s:,}株</b>、VWAP（<b>{m5_vwap}</b>）反発または <b>{r['squeeze_trigger_price']}</b> 突破で <b>{rem_s:,}株</b> 追加。利確 <b>{r['tp_price']}</b> ／ 損切り <b>{r['sl_price']}</b>。"

    return (
        f"<div><b>🤖 【ご質問：「{q_clean}」へのリアルタイム回答】</b> <span style='font-size:11.5px;color:#64748b;'>({deep['fetched_at']})</span></div>"
        f"<div class='qa-direct-box'>{direct}</div>"
        f"<div style='font-size:12px; color:#475569; margin-top:4px;'><b>📅 直近5日推移</b>：{days_html}</div>"
    )

# ==========================================
# 💬 会議パネル描画（ムード説明バナーを廃止し、自然なディベートを即表示）
# ==========================================
def cb_toggle_debate(uk):
    st.session_state["active_debates"][uk] = not st.session_state["active_debates"].get(uk, False)

def cb_toggle_watchlist(code, r_data):
    if code in st.session_state["watchlist"]: del st.session_state["watchlist"][code]
    else: st.session_state["watchlist"][code] = r_data

def cb_handle_qa_action(uk, q_text, r, debate, m5):
    if uk not in st.session_state["stock_chats"]: st.session_state["stock_chats"][uk] = []
    st.session_state["stock_chats"][uk].append({"q": q_text, "a": generate_7ai_qa_response_html(q_text, r, debate, r["lot_info"], m5)})
    st.session_state["scroll_to_chat_key"] = uk

def cb_clear_chat(uk):
    st.session_state["stock_chats"][uk] = []

@fragment_decorator
def render_interactive_council_section(r, unique_key):
    is_open = st.session_state["active_debates"].get(unique_key, False)
    in_wl = r["code"] in st.session_state["watchlist"]

    c1, c2 = st.columns([2.3, 1.1])
    c1.button("🔼 7大AIディベートを閉じる" if is_open else "💬 7大AIのディベートを見る＆参加", key=f"btn_{unique_key}", on_click=cb_toggle_debate, args=(unique_key,), use_container_width=True)
    c2.button("✅ 監視登録済(解除)" if in_wl else "⭐ 監視リスト追加", key=f"wl_{unique_key}", on_click=cb_toggle_watchlist, args=(r["code"], r), use_container_width=True)

    if not is_open:
        return

    m5 = fetch_5m_intraday_algo(r["full_code"])
    cur_seed = st.session_state["debate_round_seed"].get(unique_key, 0)
    debate = run_7ai_council_algorithm(r, m5, extra_seed=cur_seed)

    if unique_key not in st.session_state["council_threads"]:
        st.session_state["council_threads"][unique_key] = list(debate["dialogue"])
        st.session_state["council_meta"][unique_key] = debate

    meta = st.session_state["council_meta"].get(unique_key, debate)

    if m5 and show_5m_chart:
        st.caption(f"📅 直近5分足 ({m5['chart_date']}) ｜ 5分足VWAP: **{m5['vwap5_price']}** ({m5['vwap5_dev']:+.2f}%)")
        render_5m_candlestick_chart(m5)

    thread_bubbles = []
    for turn in st.session_state["council_threads"][unique_key]:
        if "round" in turn:
            thread_bubbles.append(f'<div class="round-divider">{turn["round"]}</div>')
        elif "system_event" in turn:
            thread_bubbles.append(f'<div class="system-event-bar">{turn["system_event"]}</div>')
        elif "system_rejoin" in turn:
            thread_bubbles.append(f'<div class="system-rejoin-bar">{turn["system_rejoin"]}</div>')
        elif turn.get("is_user"):
            thread_bubbles.append(f'<div class="chat-bubble-user"><div style="font-weight:800; color:#fde047; font-size:12.5px; margin-bottom:3px;">🗣️ あなたの発言</div><div>{turn["text"]}</div></div>')
        else:
            tone = turn.get("tone", "normal")
            b_cls, tone_tag = {
                "doubt":    ("chat-bubble-doubt",    '<span style="background:#d97706;color:#fff;padding:1px 6px;border-radius:4px;font-size:10.5px;margin-left:5px;">🤔疑問・引っかかり</span>'),
                "rebuttal": ("chat-bubble-rebuttal", '<span style="background:#e11d48;color:#fff;padding:1px 6px;border-radius:4px;font-size:10.5px;margin-left:5px;">⚡反論</span>'),
                "rage":     ("chat-bubble-rage",     '<span style="background:#dc2626;color:#fff;padding:1px 7px;border-radius:4px;font-size:10.5px;margin-left:5px;font-weight:900;">🔥ヒートアップ</span>'),
                "humor":    ("chat-bubble-humor",    '<span style="background:#9333ea;color:#fff;padding:1px 6px;border-radius:4px;font-size:10.5px;margin-left:5px;">😂ユーモア・仲裁</span>'),
                "agree":    ("chat-bubble-agree",    '<span style="background:#059669;color:#fff;padding:1px 6px;border-radius:4px;font-size:10.5px;margin-left:5px;">🤝合意形成</span>')
            }.get(tone, ("chat-bubble-ai", '<span style="background:#0284c7;color:#fff;padding:1px 6px;border-radius:4px;font-size:10.5px;margin-left:5px;">📊データ分析</span>'))
            sc_badge = f' <span style="background:rgba(251,191,36,0.2);color:#fde047;padding:1px 7px;border-radius:999px;font-size:11px;">評価 {turn["score"]}点</span>' if "score" in turn else ""
            thread_bubbles.append(f'<div class="{b_cls}"><div style="font-weight:800; color:#fbbf24; font-size:12.5px; margin-bottom:4px;">{turn["speaker"]}{sc_badge}{tone_tag}</div><div>{turn["text"]}</div></div>')

    scroll_win_id = f"council_win_{unique_key}"
    st.markdown(
        f'<div class="ai-council-box">'
        f'<div id="{scroll_win_id}" class="council-scroll-window">{"".join(thread_bubbles)}</div>'
        f'<div class="consensus-banner"><div style="font-weight:bold; color:#fde047; font-size:14px;">🏛️ 7大AI 全員合意の最終コンセンサス</div>{meta["verdict_html"]}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    if st.session_state.get("scroll_council_key") == unique_key:
        components.html(f'<script>setTimeout(function(){{const w=window.parent.document.getElementById("{scroll_win_id}");if(w)w.scrollTop=w.scrollHeight;}},120);</script>', height=0)
        st.session_state["scroll_council_key"] = None

    ex_col1, ex_col2 = st.columns([1.8, 1.4])
    if ex_col1.button("💬 議論の続きを見る（＋1ラウンド）", key=f"ext_{unique_key}", use_container_width=True):
        nxt_r = st.session_state["debate_round_seed"].get(unique_key, 0) + 1
        st.session_state["debate_round_seed"][unique_key] = nxt_r
        st.session_state["council_threads"][unique_key].extend(generate_extra_heated_round(r, m5, nxt_r))
        st.session_state["scroll_council_key"] = unique_key
        st.rerun()
    if ex_col2.button("🔄 新しい切り口でディベートを再生成", key=f"rst_{unique_key}", use_container_width=True):
        new_seed = st.session_state["debate_round_seed"].get(unique_key, 0) + random.randint(1, 99999)
        st.session_state["debate_round_seed"][unique_key] = new_seed
        new_deb = run_7ai_council_algorithm(r, m5, extra_seed=new_seed)
        st.session_state["council_threads"][unique_key] = list(new_deb["dialogue"])
        st.session_state["council_meta"][unique_key] = new_deb
        st.rerun()

    with st.form(f"join_council_form_{unique_key}", clear_on_submit=True):
        jc1, jc2 = st.columns([3.2, 1])
        user_opinion = jc1.text_input("会議で発言する", placeholder="ディベートに参加する（例：朝から行くべき？ / 上ヒゲが気になる / 現在の株価は？）", label_visibility="collapsed")
        if jc2.form_submit_button("💬 発言を投下", use_container_width=True) and user_opinion.strip():
            st.session_state["council_threads"][unique_key].append({"is_user": True, "text": user_opinion.strip()})
            st.session_state["council_threads"][unique_key].extend(generate_ai_reply_to_user_opinion(user_opinion.strip(), r, m5))
            st.session_state["scroll_council_key"] = unique_key
            st.rerun()

    q_col1, q_col2 = st.columns(2)
    with q_col1:
        st.button("💴 現在の株価・高値安値・目標株価は？", key=f"q1_{unique_key}", on_click=cb_handle_qa_action, args=(unique_key, "現在の株価はいくら？本日の高値・安値・目標株価も教えて", r, meta, m5), use_container_width=True)
        st.button("📊 決算・PER/PBR・時価総額を調べて", key=f"q2_{unique_key}", on_click=cb_handle_qa_action, args=(unique_key, "PERやPBR、時価総額、目標株価などファンダメンタルズを調べて", r, meta, m5), use_container_width=True)
    with q_col2:
        st.button("📰 最新ニュースと値動きの理由は？", key=f"q3_{unique_key}", on_click=cb_handle_qa_action, args=(unique_key, "最新ニュースと本日の値動きの理由・背景は？", r, meta, m5), use_container_width=True)
        st.button("💰 具体的な買い値・利確・損切りは？", key=f"q4_{unique_key}", on_click=cb_handle_qa_action, args=(unique_key, "いつどの価格で買って、いくらで利確・損切りすべき？", r, meta, m5), use_container_width=True)

    with st.form(f"free_q_form_{unique_key}", clear_on_submit=True):
        f_col1, f_col2 = st.columns([3.2, 1])
        user_q_txt = f_col1.text_input("自由質問を入力", placeholder="自由質問（例：現在の株価は？ / なぜ上がった？ / 明日の勝率は？）", label_visibility="collapsed")
        if f_col2.form_submit_button("🔍 ライブ調査", use_container_width=True) and user_q_txt.strip():
            cb_handle_qa_action(unique_key, user_q_txt.strip(), r, meta, m5)

    anchor_id = f"qa_ans_anchor_{unique_key}"
    st.markdown(f'<div id="{anchor_id}"></div>', unsafe_allow_html=True)
    chat_history = st.session_state["stock_chats"].get(unique_key, [])
    if chat_history:
        st.markdown(f'<div class="qa-answer-card">{chat_history[-1]["a"]}</div>', unsafe_allow_html=True)
        if st.session_state.get("scroll_to_chat_key") == unique_key:
            components.html(f'<script>setTimeout(function(){{const el=window.parent.document.getElementById("{anchor_id}");if(el)el.scrollIntoView({{behavior:"smooth",block:"center"}});}},100);</script>', height=0)
            st.session_state["scroll_to_chat_key"] = None
        if len(chat_history) > 1:
            with st.expander(f"📚 過去の質問履歴（全 {len(chat_history)} 件）"):
                for idx_h in range(len(chat_history) - 2, -1, -1):
                    st.markdown(f'<div class="qa-answer-card">{chat_history[idx_h]["a"]}</div>', unsafe_allow_html=True)
        st.button("🗑️ 質問履歴をクリア", key=f"clr_{unique_key}", on_click=cb_clear_chat, args=(unique_key,), use_container_width=True)

# ==========================================
# 🃏 銘柄カード描画
# ==========================================
def render_stock_card(r, is_custom=False, rank=None, key_prefix="card"):
    diff_color = "#dc2626" if r["diff"] > 0 else "#2563eb"
    diff_sign = "+" if r["diff"] > 0 else ""
    pts_sign = "+" if r["pts_gap_pct"] > 0 else ""
    rank_html = f'<span class="rank-badge">🏆 第{rank}位</span>' if rank else ""
    lot = r["lot_info"]
    logo_html = get_company_logo_html(r["full_code"], r["name"])

    html_card = (
        f'<div class="{"search-result-card" if is_custom else "rank-card"}">'
        f'<div class="signal-10tier-badge" style="background:{r["tier_bg"]};color:{r["tier_color"]} !important;">'
        f'<span>🎯 {r["tier_label"]}</span><span style="font-size:12px;">総合勝率 {r["total_win_rate"]}% ｜ Lv.{r["tier_num"]}/10</span></div>'
        f'<div style="margin-bottom:8px;">{rank_html}<span class="score-badge">🤖 AI: {r["ai_score"]}点</span>'
        f'<span class="inst-badge">🏦 機関: {r["inst_score"]}点</span><span class="board5ch-badge">🔥 5ch需給: {r["board5ch_score"]}点</span><span class="tokugai-badge">🚨 特買い: {r["tokugai_prob"]}%</span></div>'
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-top:6px;">'
        f'<div style="display:flex;align-items:center;gap:10px;">{logo_html}'
        f'<div><span style="font-size:17.5px;font-weight:800;color:#0f172a;">{r["name"]}</span> <span style="font-size:13px;color:#64748b;font-weight:600;">({r["code"]} / {r["genre"]})</span><br>'
        f'<span style="font-size:15px;color:#334155;">現在値(終値): <b>{r["price"]}</b> (<span style="color:{diff_color};font-weight:800;">{diff_sign}{r["diff"]}%</span>)</span></div></div>'
        f'<div style="text-align:right;"><span style="font-size:11.5px;color:#64748b;font-weight:700;">🎯 総合勝率</span><br>'
        f'<span class="prob-badge">{r["total_win_rate"]}%</span><div style="font-size:11.5px;color:#64748b;">(損益比 {r["payoff"]}倍 / 期待値 {r["edge"]:+.2f}%)</div></div></div>'
        f'<div class="winrate-bar">'
        f'<div><div style="font-size:11px;color:#881337;font-weight:700;">🏆 総合勝率</div><div style="font-size:15px;font-weight:900;color:#e11d48;">{r["total_win_rate"]}%</div></div>'
        f'<div style="border-left:1px solid #fecdd3;"><div style="font-size:11px;color:#64748b;">🌅 翌朝GU勝率</div><div style="font-size:14px;font-weight:800;color:#dc2626;">{r["prob"]}% <span style="font-size:10.5px;">({r["count"]})</span></div></div>'
        f'<div style="border-left:1px solid #fecdd3;"><div style="font-size:11px;color:#64748b;">☀️ 寄り後陽線勝率</div><div style="font-size:14px;font-weight:800;color:#d97706;">{r["intraday_win_rate"]}%</div></div>'
        f'<div style="border-left:1px solid #fecdd3;"><div style="font-size:11px;color:#64748b;">📈 順張り勝率</div><div style="font-size:14px;font-weight:800;color:#15803d;">{r["trend_win_rate"]}%</div></div></div>'
        f'<div class="delicate-box">{r["delicate_narrative"]}</div>'
        f'<div class="inst-box"><b>{r["inst_status"]}</b> ｜ 20日VWAP基準: <b>{r["vwap_price"]}</b></div>'
        f'<div class="board5ch-box"><b>📢 {r["board5ch_status"]}</b> ｜ シグナル: <b>{r["signal"]}</b></div>'
        f'<div class="pts-tokugai-box"><b>🌙 {r["tokugai_status"]}</b> ｜ 夜間理論気配: <b>{r["pts_est_price"]}</b> ({pts_sign}{r["pts_gap_pct"]}%) ｜ 特買い線: <b>{r["tokugai_line"]}</b></div>'
        f'<div class="squeeze-box"><b>{r["squeeze_type"]}</b> ｜ 踏み上げ突破ライン(20日高値): <b>{r["squeeze_trigger_price"]}</b> ({r["dist_to_high20"]:+.2f}%)</div>'
        f'<div class="metrics-row"><span>🏦 <b>VPIN:</b> {r["vpin"]:+.2f}</span><span>🧬 <b>Hurst:</b> {r["hurst"]}</span><span>🎯 <b>Kalman:</b> {r["kalman_bull_pct"]:+.2f}%</span><span>📐 <b>BB:</b> {r["bb_z"]:+.2f}σ</span><span>📊 <b>RSI:</b> {r["rsi"]}</span><span>📈 <b>MACD:</b> {r["macd_state"]}</span><span>🔊 <b>出来高:</b> {r["vol_ratio"]}倍</span></div>'
        f'<div class="trade-plan-box">'
        f'<div><div style="font-size:11px;color:#64748b;">🌅 夜間理論寄付き</div><div style="font-size:13.5px;font-weight:800;">{r["pts_est_price"]}</div></div>'
        f'<div style="border-left:1px solid #cbd5e1;border-right:1px solid #cbd5e1;"><div style="font-size:11px;color:#15803d;font-weight:bold;">🎯 利確目標</div><div style="font-size:13.5px;font-weight:800;color:#15803d;">{r["tp_price"]} (+{r["tp_pct"]}%)</div></div>'
        f'<div><div style="font-size:11px;color:#b91c1c;font-weight:bold;">🛡️ 損切り逆指値</div><div style="font-size:13.5px;font-weight:800;color:#b91c1c;">{r["sl_price"]} ({r["sl_pct"]}%)</div></div></div>'
        f'<div class="sizing-box">📦 <b>推奨ロット: {lot["shares"]:,}株</b> (投資額: <b>{lot["position_value"]:,.0f}円</b> / 最大損失リスク: <b>{lot["risk_amount"]:,.0f}円</b>)</div></div>'
    )
    st.markdown(html_card, unsafe_allow_html=True)
    render_interactive_council_section(r, f"{key_prefix}_{r['code']}")

# ==========================================
# 🚀 メイン画面ヘッダー＆ピル型ナビゲーション描画
# ==========================================
macro_info = fetch_macro_market()
macro_pills = "".join([f'<div style="background:rgba(255,255,255,0.08);padding:4px 10px;border-radius:8px;font-size:12px;display:inline-flex;gap:5px;"><span style="color:#cbd5e1;">{m["label"]}</span><span style="color:{"#f87171" if m["diff"]>=0 else "#60a5fa"};font-weight:700;">{"+" if m["diff"]>=0 else ""}{m["diff"]}%</span></div>' for m in macro_info.values()])

st.markdown(f'<div style="background:linear-gradient(135deg,#090d16,#1e293b);color:#f8fafc;padding:18px 20px;border-radius:16px;margin-bottom:12px;"><div style="display:flex;justify-content:space-between;align-items:center;"><div><div style="font-size:11.5px;color:#fbbf24;font-weight:700;">NATURAL AI DEBATE & LATEST QUANT ENGINE</div><h1 style="margin:2px 0 0 0;font-size:21px;color:#fff;font-weight:800;">📈 翌朝株価 クオンツ＆7大AI解析 Pro</h1></div><span style="background:rgba(251,191,36,0.15);color:#fde047;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:700;">{curr_page_badge}</span></div><div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:12px;">{macro_pills}</div></div>', unsafe_allow_html=True)

st.markdown('<div id="search_box_anchor"></div>', unsafe_allow_html=True)
c1, c2 = st.columns([3.2, 1])
custom_input = c1.text_input("🔍 任意の銘柄コードを診断", placeholder="例: 6920, 5803, 3350, NVDA, IONQ", label_visibility="collapsed")
if c2.button("🔍 銘柄診断", use_container_width=True) and custom_input:
    st.session_state["custom_search_code"] = normalize_ticker(custom_input)
    navigate_to("SEARCH_RESULT")

if st.session_state.get("custom_search_code"):
    norm_code = st.session_state["custom_search_code"]
    with st.spinner(f"「{norm_code}」を精密解析中..."):
        custom_res = fetch_single_stock(norm_code, macro_info, inst_boost_mode, board5ch_boost, squeeze_boost_mode, tokugai_boost_mode, auto_evolve_algo)
    if custom_res:
        render_stock_card(custom_res, is_custom=True, key_prefix="custom")
        if st.button("✖️ 個別診断結果を閉じてランキングに戻る", use_container_width=True):
            st.session_state["custom_search_code"] = ""; st.session_state["navigation_page"] = "TOP"; st.rerun()
    else:
        st.error(f"銘柄「{norm_code}」のデータが見つかりませんでした。")

with st.spinner("🏦 国内外の母集団を一括スキャン＆最新クオンツ解析中..."):
    genre_results, all_results = fetch_all_pool_batch(macro_info, inst_boost_mode, board5ch_boost, squeeze_boost_mode, tokugai_boost_mode, auto_evolve_algo)

def apply_survival_of_the_fittest(stock_list, cut_pct):
    if not stock_list: return [], []
    s_all = sorted(stock_list, key=lambda x: (x["tier_num"], x["total_win_rate"], x["survival_power"], x["inst_score"]), reverse=True)
    keep = max(3, int(round(len(s_all) * (cut_pct / 100.0))))
    return s_all[:keep], s_all[keep:]

if st.session_state.get("navigation_page", "TOP") == "WATCHLIST":
    st.subheader("📋 監視ウォッチリスト")
    if st.button("⬅️ ランキング一覧へ戻る", use_container_width=True):
        st.session_state["navigation_page"] = "TOP"; st.rerun()
    for w_code, w_item in list(st.session_state["watchlist"].items()):
        render_stock_card(w_item, key_prefix=f"wl_page_{w_code}")
else:
    all_categories = ["🏆 総合TOP5", "🏦 機関VPIN・最新クオンツ", "🔥 5ch板・初動イナゴ", "🚨 特買い・夜間PTS", "💥 空売り踏み上げ", "📋 監視＆注文シート"] + [f"📂 {g}" for g in STOCK_POOL.keys()]
    selected_cat = st.radio("カテゴリ切替", options=all_categories, horizontal=True, label_visibility="collapsed")

    surv_all, elim_all = apply_survival_of_the_fittest(all_results, survival_cut_pct)

    if selected_cat == "🏆 総合TOP5":
        st.caption(f"🦁 全母集団 {len(all_results)}銘柄から下位 {len(elim_all)}銘柄を足切り！総合勝率・10段階評価ともに最強のTOP5です。")
        for idx, r in enumerate(surv_all[:5], start=1):
            render_stock_card(r, rank=idx, key_prefix="top5")
    elif selected_cat == "🏦 機関VPIN・最新クオンツ":
        for idx, r in enumerate(sorted(all_results, key=lambda x: (x["inst_score"], x["total_win_rate"], x["vpin"]), reverse=True)[:10], start=1):
            render_stock_card(r, rank=idx, key_prefix="inst_top")
    elif selected_cat == "🔥 5ch板・初動イナゴ":
        for idx, r in enumerate(sorted(all_results, key=lambda x: (x["board5ch_score"], x["total_win_rate"]), reverse=True)[:10], start=1):
            render_stock_card(r, rank=idx, key_prefix="b5_top")
    elif selected_cat == "🚨 特買い・夜間PTS":
        for idx, r in enumerate(sorted(all_results, key=lambda x: (x["tokugai_prob"], x["pts_gap_pct"]), reverse=True)[:10], start=1):
            render_stock_card(r, rank=idx, key_prefix="tk_top")
    elif selected_cat == "💥 空売り踏み上げ":
        for idx, r in enumerate(sorted(all_results, key=lambda x: (x["squeeze_score"], x["total_win_rate"]), reverse=True)[:10], start=1):
            render_stock_card(r, rank=idx, key_prefix="sq_top")
    elif selected_cat == "📋 監視＆注文シート":
        wl = st.session_state["watchlist"]
        st.markdown(f"#### 📋 監視ウォッチリスト ({len(wl)}銘柄)")
        if st.button("⚡ 総合TOP3をワンタップ一括登録", use_container_width=True):
            for item in surv_all[:3]: st.session_state["watchlist"][item["code"]] = item
            st.rerun()
        if wl:
            st.dataframe(pd.DataFrame([{"コード": c, "銘柄名": x["name"], "現在値": x["price"], "総合勝率": f"{x['total_win_rate']}%", "10段階判定": x["tier_label"], "夜間理論気配": x["pts_est_price"], "推奨株数": f"{x['lot_info']['shares']:,}株", "利確": x["tp_price"], "損切": x["sl_price"]} for c, x in wl.items()]), use_container_width=True, hide_index=True)
    elif selected_cat.startswith("📂 "):
        g_key = selected_cat.replace("📂 ", "")
        g_surv, g_elim = apply_survival_of_the_fittest(genre_results.get(g_key, []), survival_cut_pct)
        st.caption(f"🦁 **{g_key}選抜**: 上位 **{len(g_surv)}銘柄が生存**（下位 {len(g_elim)}銘柄が脱落）")
        for idx, r in enumerate(g_surv, start=1):
            render_stock_card(r, rank=idx, key_prefix=f"genre_{g_key}")
