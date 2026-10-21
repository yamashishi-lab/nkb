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
import smtplib
import urllib.parse
from email.mime.text import MIMEText
from datetime import datetime

st.set_page_config(page_title="翌朝株価 クオンツ＆7大AI解析 Pro (会員限定版)", page_icon="📈", layout="centered")
fragment_decorator = getattr(st, "fragment", getattr(st, "experimental_fragment", lambda f: f))

# ==========================================
# 🔒 会員DB ＆ SMTP永続化 ＆ ワンクリック承認管理
# ==========================================
ADMIN_EMAIL = "nthbh399@ybb.ne.jp"
SECRET_MASTER_KEY = "my_super_secret_quant_key_2026"
MEMBERS_DB_FILE = "members_db.json"
SMTP_CONFIG_FILE = "admin_smtp_config.json"

def generate_member_passcode(email: str) -> str:
    clean_email = email.strip().lower()
    return hmac.new(SECRET_MASTER_KEY.encode(), clean_email.encode(), hashlib.sha256).hexdigest()[:8].upper()

def generate_admin_action_token(email: str, action: str) -> str:
    msg = f"{email.strip().lower()}:{action}:{SECRET_MASTER_KEY}"
    return hashlib.sha256(msg.encode()).hexdigest()[:16]

def load_smtp_config() -> dict:
    default_cfg = {
        "app_base_url": "http://localhost:8501",
        "smtp_user": ADMIN_EMAIL,
        "smtp_pass": "",
        "smtp_server": "smtp.mail.yahoo.co.jp",
        "smtp_port": 465
    }
    if os.path.exists(SMTP_CONFIG_FILE):
        try:
            with open(SMTP_CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                default_cfg.update(saved)
        except Exception:
            pass
    return default_cfg

def save_smtp_config(cfg: dict):
    try:
        with open(SMTP_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_members_db() -> dict:
    db = {}
    if os.path.exists(MEMBERS_DB_FILE):
        try:
            with open(MEMBERS_DB_FILE, "r", encoding="utf-8") as f:
                db = json.load(f)
        except Exception:
            db = {}
    admin_clean = ADMIN_EMAIL.strip().lower()
    if admin_clean not in db:
        now_s = datetime.now().strftime("%Y-%m-%d %H:%M")
        db[admin_clean] = {
            "name": "管理者 (Owner)", "email": admin_clean, "status": "approved",
            "passcode": generate_member_passcode(admin_clean),
            "applied_at": now_s, "approved_at": now_s, "note": "システム最高管理者"
        }
        save_members_db(db)
    return db

def save_members_db(db: dict):
    try:
        with open(MEMBERS_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def send_auto_email(to_email: str, subject: str, body: str) -> tuple:
    cfg = load_smtp_config()
    smtp_user = cfg.get("smtp_user", "").strip()
    smtp_pass = cfg.get("smtp_pass", "").strip()
    smtp_server = cfg.get("smtp_server", "smtp.mail.yahoo.co.jp").strip()
    smtp_port = int(cfg.get("smtp_port", 465))

    if not smtp_user or not smtp_pass:
        return False, "SMTP未設定（管理画面で設定・保存してください）"
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = smtp_user
        msg["To"] = to_email
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10) as server:
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        return True, "自動メール送信完了"
    except Exception as e:
        return False, str(e)

def process_url_admin_action():
    q_params = st.query_params
    action = q_params.get("admin_action", "")
    target_email = q_params.get("email", "").strip().lower()
    token = q_params.get("token", "")
    target_name = q_params.get("name", "申請者")

    if action in ["approve", "reject"] and target_email and token:
        if hmac.compare_digest(token, generate_admin_action_token(target_email, action)):
            db = load_members_db()
            code = generate_member_passcode(target_email)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            if action == "approve":
                db[target_email] = {
                    "name": db.get(target_email, {}).get("name", target_name), "email": target_email,
                    "status": "approved", "passcode": code,
                    "applied_at": db.get(target_email, {}).get("applied_at", now_str),
                    "approved_at": now_str, "note": "メールリンクからワンクリック承認"
                }
                save_members_db(db)
                subj = "【承認完了】翌朝株価クオンツ＆7大AI解析 Pro 専用アクセスコードのお知らせ"
                body = f"{db[target_email]['name']} 様\n\nご利用申請が承認されました。\n\n■ 登録メールアドレス: {target_email}\n■ 専用アクセスコード: {code}\n"
                sent_ok, _ = send_auto_email(target_email, subj, body)
                st.success(f"✅ 【承認完了】 {target_email} を承認しました！（専用コード: {code}）")
                if sent_ok:
                    st.info(f"📨 {target_email} 宛てにパスコード通知メールを自動送信しました！")
                else:
                    mailto_url = f"mailto:{target_email}?subject={urllib.parse.quote(subj)}&body={urllib.parse.quote(body)}"
                    st.markdown(f'👉 <a href="{mailto_url}" style="background:#16a34a;color:#fff;padding:8px 14px;border-radius:6px;text-decoration:none;font-weight:bold;">📨 申請者へ通知メールを送信する</a>', unsafe_allow_html=True)
            else:
                db[target_email] = {
                    "name": db.get(target_email, {}).get("name", target_name), "email": target_email,
                    "status": "rejected", "passcode": code,
                    "applied_at": db.get(target_email, {}).get("applied_at", now_str),
                    "approved_at": now_str, "note": "メールリンクから却下"
                }
                save_members_db(db)
                st.warning(f"❌ {target_email} の申請を却下しました。")
            for k in ["admin_action", "email", "token"]:
                if k in st.query_params:
                    del st.query_params[k]

process_url_admin_action()

def render_smtp_settings_form(form_key_suffix: str):
    cfg = load_smtp_config()
    with st.form(f"smtp_cfg_form_{form_key_suffix}"):
        app_url = st.text_input("🌐 アプリ公開URL", value=cfg.get("app_base_url", "http://localhost:8501"))
        s_user = st.text_input("📧 送信元メールアドレス", value=cfg.get("smtp_user", ADMIN_EMAIL))
        s_pass = st.text_input("🔑 SMTPアプリパスワード", value=cfg.get("smtp_pass", ""), type="password")
        s_serv = st.text_input("🖥️ SMTPサーバー", value=cfg.get("smtp_server", "smtp.mail.yahoo.co.jp"))
        s_port = st.number_input("🔌 SMTPポート", value=int(cfg.get("smtp_port", 465)))
        if st.form_submit_button("💾 SMTP設定をファイルに永続保存する", use_container_width=True):
            new_cfg = {
                "app_base_url": app_url.strip(),
                "smtp_user": s_user.strip(),
                "smtp_pass": s_pass.strip(),
                "smtp_server": s_serv.strip(),
                "smtp_port": int(s_port)
            }
            save_smtp_config(new_cfg)
            st.success("✅ SMTP設定を永続保存しました！（ログアウト・再ログインしても消えません）")

def render_admin_sidebar_management():
    db = load_members_db()
    pending_list = [v for v in db.values() if v.get("status") == "pending"]
    st.sidebar.markdown("---")
    st.sidebar.subheader(f"👑 管理者メニュー (承認待:{len(pending_list)}件)")

    if st.sidebar.button("🛠️ 管理者専用ページ(全画面)を開く", key="side_open_admin_page", use_container_width=True):
        st.session_state["navigation_page"] = "ADMIN"
        st.query_params["nav"] = "ADMIN"
        st.rerun()

    mode = st.sidebar.radio("クイック管理", ["⏳ 申請承認待ち一覧", "👥 全会員DB管理・削除"], key="admin_sidebar_mode")
    if mode == "⏳ 申請承認待ち一覧":
        if pending_list:
            for p in pending_list:
                p_mail, p_name = p["email"], p.get("name", "未入力")
                p_code = generate_member_passcode(p_mail)
                st.sidebar.markdown(f"**📩 {p_name}** (`{p_mail}`)")
                c1, c2, c3 = st.sidebar.columns(3)
                with c1:
                    if st.button("✅承認", key=f"s_ap_{p_mail}", use_container_width=True):
                        db[p_mail].update({"status": "approved", "passcode": p_code, "approved_at": datetime.now().strftime("%Y-%m-%d %H:%M")})
                        save_members_db(db)
                        subj = "【承認完了】翌朝株価クオンツ＆7大AI解析Pro 専用アクセスコード"
                        body = f"{p_name} 様\n\n会員登録が承認されました。\n■登録メール: {p_mail}\n■専用アクセスコード: {p_code}\n"
                        ok, _ = send_auto_email(p_mail, subj, body)
                        st.session_state["last_approved_mailto"] = {"email": p_mail, "code": p_code, "auto_sent": ok, "url": f"mailto:{p_mail}?subject={urllib.parse.quote(subj)}&body={urllib.parse.quote(body)}"}
                        st.rerun()
                with c2:
                    if st.button("❌却下", key=f"s_rj_{p_mail}", use_container_width=True):
                        db[p_mail]["status"] = "rejected"
                        save_members_db(db)
                        st.rerun()
                with c3:
                    if st.button("🗑️削除", key=f"s_dl_{p_mail}", use_container_width=True):
                        if p_mail != ADMIN_EMAIL.strip().lower():
                            del db[p_mail]
                            save_members_db(db)
                            st.rerun()
        else:
            st.sidebar.info("現在、承認待ちの申請はありません。")
    else:
        rows = [{"状態": info.get("status"), "名前": info.get("name"), "メール": em, "コード": info.get("passcode")} for em, info in db.items()]
        df_members = pd.DataFrame(rows)
        st.sidebar.dataframe(df_members, use_container_width=True, hide_index=True)
        target_em = st.sidebar.selectbox("操作する会員を選択", options=list(db.keys()), format_func=lambda x: f"{db[x].get('name','')} ({x})")
        if target_em:
            b1, b2, b3 = st.sidebar.columns(3)
            with b1:
                if st.button("✅有効", key="adm_act_btn", use_container_width=True):
                    db[target_em].update({"status": "approved", "passcode": generate_member_passcode(target_em)})
                    save_members_db(db)
                    st.rerun()
            with b2:
                if st.button("⏸️停止", key="adm_stop_btn", use_container_width=True):
                    if target_em != ADMIN_EMAIL.strip().lower():
                        db[target_em]["status"] = "rejected"
                        save_members_db(db)
                        st.rerun()
            with b3:
                if st.button("🗑️削除", key="adm_del_btn", use_container_width=True):
                    if target_em != ADMIN_EMAIL.strip().lower():
                        del db[target_em]
                        save_members_db(db)
                        st.sidebar.success(f"{target_em} を削除しました。")
                        st.rerun()
                    else:
                        st.sidebar.error("管理者は削除不可")

    with st.sidebar.expander("⚙️ 自動メール送信(SMTP)永続設定"):
        render_smtp_settings_form("sidebar")

def render_admin_full_page():
    db = load_members_db()
    pending_list = [v for v in db.values() if v.get("status") == "pending"]
    approved_list = [v for v in db.values() if v.get("status") == "approved"]

    st.markdown("""
    <div style="background: linear-gradient(135deg, #31102f 0%, #0f172a 100%); color: #f8fafc; padding: 18px 22px; border-radius: 16px; margin-bottom: 14px; border: 1px solid rgba(251,191,36,0.35);">
        <div style="font-size:12px; color:#fbbf24; font-weight:700;">ADMINISTRATOR ONLY CONSOLE</div>
        <h2 style="margin:2px 0 4px 0; font-size:21px; color:#ffffff;">👑 管理者専用・会員データベース＆承認・削除センター</h2>
        <div style="font-size:13px; color:#cbd5e1;">新規申請の承認・会員の完全削除・手動会員登録・SMTP設定の永続保存を一括管理できます。</div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("⬅️ 株価解析ランキング画面（TOP）へ戻る", key="back_from_admin_top", use_container_width=True):
        st.session_state["navigation_page"] = "TOP"
        if "nav" in st.query_params: del st.query_params["nav"]
        st.rerun()

    m1, m2, m3 = st.columns(3)
    m1.metric("⏳ 承認待ち申請", f"{len(pending_list)} 件")
    m2.metric("✅ 承認済み会員数", f"{len(approved_list)} 名")
    m3.metric("👥 総登録データ数", f"{len(db)} 件")

    adm_tab1, adm_tab2, adm_tab3 = st.tabs([
        f"⏳ 承認待ち申請 ({len(pending_list)}件)",
        f"👥 全会員リスト＆追加・削除 ({len(db)}件)",
        "⚙️ 自動メール送信(SMTP)永続設定"
    ])

    with adm_tab1:
        if pending_list:
            for p in pending_list:
                p_mail, p_name, p_note, p_time = p["email"], p.get("name", "未入力"), p.get("note", "-"), p.get("applied_at", "-")
                p_code = generate_member_passcode(p_mail)
                st.markdown(
                    f'<div class="rank-card" style="border-left-color:#f59e0b;">'
                    f'<div style="font-size:16px; font-weight:800;">👤 {p_name} <span style="font-size:13.5px; color:#475569;">({p_mail})</span></div>'
                    f'<div style="font-size:13px; color:#334155; margin-top:4px;">💬 備考: <b>{p_note or "なし"}</b> ｜ 🕒 申請: {p_time} ｜ 🔑 コード: <code>{p_code}</code></div></div>',
                    unsafe_allow_html=True
                )
                ca, cr, cd = st.columns(3)
                with ca:
                    if st.button(f"✅ 承認してコード発行 ({p_name})", key=f"main_ap_{p_mail}", use_container_width=True):
                        db[p_mail].update({"status": "approved", "passcode": p_code, "approved_at": datetime.now().strftime("%Y-%m-%d %H:%M")})
                        save_members_db(db)
                        subj = "【承認完了】翌朝株価クオンツ＆7大AI解析Pro 専用アクセスコード"
                        body = f"{p_name} 様\n\n会員登録が承認されました。\n■登録メール: {p_mail}\n■専用アクセスコード: {p_code}\n"
                        ok, _ = send_auto_email(p_mail, subj, body)
                        st.session_state["last_approved_mailto"] = {"email": p_mail, "code": p_code, "auto_sent": ok, "url": f"mailto:{p_mail}?subject={urllib.parse.quote(subj)}&body={urllib.parse.quote(body)}"}
                        st.rerun()
                with cr:
                    if st.button(f"❌ 却下する ({p_name})", key=f"main_rj_{p_mail}", use_container_width=True):
                        db[p_mail]["status"] = "rejected"
                        save_members_db(db)
                        st.rerun()
                with cd:
                    if st.button(f"🗑️ 完全削除 ({p_name})", key=f"main_dl_{p_mail}", use_container_width=True):
                        if p_mail != ADMIN_EMAIL.strip().lower():
                            del db[p_mail]
                            save_members_db(db)
                            st.rerun()
        else:
            st.success("🎉 現在、承認待ちの申請はありません。")

        if "last_approved_mailto" in st.session_state:
            la = st.session_state["last_approved_mailto"]
            if la["auto_sent"]:
                st.success(f"📨 {la['email']} へ専用パスコード（{la['code']}）を自動メール送信しました！")
            else:
                st.success(f"✅ {la['email']} を承認しました！（専用パスコード: `{la['code']}`）")
                st.markdown(f'<a href="{la["url"]}" style="display:inline-block;background:#16a34a;color:#fff;padding:8px 16px;border-radius:8px;text-decoration:none;font-weight:bold;">✉️ 承認通知メールをメーラーで送信する</a>', unsafe_allow_html=True)

    with adm_tab2:
        st.markdown("##### ➕ 新規会員の手動即時追加")
        with st.form("admin_manual_add_form"):
            mc1, mc2, mc3 = st.columns([1.5, 2, 1.5])
            with mc1: new_m_name = st.text_input("お名前", placeholder="佐藤 一郎")
            with mc2: new_m_mail = st.text_input("メールアドレス", placeholder="user@example.com")
            with mc3: new_m_note = st.text_input("備考", placeholder="VIP招待")
            if st.form_submit_button("➕ 即時承認済みとして追加・パスコード発行", use_container_width=True):
                cm = new_m_mail.strip().lower()
                if cm and "@" in cm:
                    code_gen = generate_member_passcode(cm)
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                    db[cm] = {"name": new_m_name.strip() or "招待会員", "email": cm, "status": "approved", "passcode": code_gen, "applied_at": now_str, "approved_at": now_str, "note": new_m_note.strip() or "管理者手動追加"}
                    save_members_db(db)
                    st.success(f"✅ {cm} を追加しました！ 専用パスコード: `{code_gen}`")
                    st.rerun()
                else:
                    st.error("正しいメールアドレスを入力してください。")

        st.markdown("---")
        st.markdown("##### 👥 登録会員一覧 ＆ ステータス変更・完全削除")
        rows = [{"状態": info.get("status"), "名前": info.get("name"), "メールアドレス": em, "専用8桁コード": info.get("passcode"), "申請日時": info.get("applied_at", "-"), "承認日時": info.get("approved_at", "-"), "備考": info.get("note", "")} for em, info in db.items()]
        df_members = pd.DataFrame(rows)
        st.dataframe(df_members, use_container_width=True, hide_index=True)

        c_sel, c_act1, c_act2, c_act3 = st.columns([2.2, 1, 1, 1])
        with c_sel:
            target_em = st.selectbox("操作する会員を選択", options=list(db.keys()), format_func=lambda x: f"{db[x].get('name','')} ({x}) - [{db[x].get('status')}]")
        with c_act1:
            st.write("")
            if st.button("✅ 有効化(承認)", key="main_adm_act", use_container_width=True):
                db[target_em].update({"status": "approved", "passcode": generate_member_passcode(target_em), "approved_at": datetime.now().strftime("%Y-%m-%d %H:%M")})
                save_members_db(db)
                st.rerun()
        with c_act2:
            st.write("")
            if st.button("⏸️ 利用停止", key="main_adm_stop", use_container_width=True):
                if target_em != ADMIN_EMAIL.strip().lower():
                    db[target_em]["status"] = "rejected"
                    save_members_db(db)
                    st.rerun()
                else:
                    st.warning("管理者は停止不可")
        with c_act3:
            st.write("")
            if st.button("🗑️ 完全削除", key="main_adm_del", use_container_width=True):
                if target_em != ADMIN_EMAIL.strip().lower():
                    del db[target_em]
                    save_members_db(db)
                    st.success(f"🗑️ {target_em} をデータベースから完全に削除しました。")
                    st.rerun()
                else:
                    st.warning("管理者自身は削除できません。")

        csv_mem = df_members.to_csv(index=False).encode("utf-8-sig")
        st.download_button("📥 全会員リストをCSVでダウンロード", data=csv_mem, file_name="members_backup.csv", mime="text/csv", use_container_width=True)

    with adm_tab3:
        st.markdown("##### ⚙️ 自動メール送信 (SMTP) 設定（永続保存対応）")
        st.caption("ここで保存した設定はサーバー内のファイル（`admin_smtp_config.json`）に保存されるため、ログアウトしても消えません。")
        render_smtp_settings_form("main_page")

def check_member_authentication():
    db = load_members_db()
    if "authenticated_user" not in st.session_state:
        st.session_state["authenticated_user"] = None

    q_user = st.query_params.get("u", "").strip().lower()
    q_tok = st.query_params.get("t", "").strip()
    if not st.session_state["authenticated_user"] and q_user and q_tok:
        expected_tok = generate_admin_action_token(q_user, "session_keep")
        user_rec = db.get(q_user)
        if hmac.compare_digest(q_tok, expected_tok) and ((user_rec and user_rec.get("status") == "approved") or q_user == ADMIN_EMAIL.strip().lower()):
            st.session_state["authenticated_user"] = q_user

    if st.session_state["authenticated_user"]:
        curr_user = st.session_state["authenticated_user"]
        st.query_params["u"] = curr_user
        st.query_params["t"] = generate_admin_action_token(curr_user, "session_keep")

        q_nav = st.query_params.get("nav", "").upper()
        if q_nav == "ADMIN" and curr_user == ADMIN_EMAIL.strip().lower():
            st.session_state["navigation_page"] = "ADMIN"
        elif q_nav == "TOP":
            st.session_state["navigation_page"] = "TOP"
            del st.query_params["nav"]

        with st.sidebar:
            st.success(f"👤 ログイン中:\n{curr_user}")
            if st.button("🚪 ログアウト", use_container_width=True):
                st.session_state["authenticated_user"] = None
                st.query_params.clear()
                st.rerun()
        if curr_user == ADMIN_EMAIL.strip().lower():
            render_admin_sidebar_management()
        return True

    st.markdown("""
    <div style="background: linear-gradient(135deg, #090d16, #1e293b); color: #f8fafc; padding: 28px 24px; border-radius: 16px; text-align: center; margin-top: 10px; margin-bottom: 18px; border: 1px solid rgba(255,255,255,0.1);">
        <h2 style="margin:0; color:#fbbf24; font-size:22px;">🔒 会員限定 クオンツ＆7大AI解析 Pro</h2>
        <p style="font-size:14px; color:#cbd5e1; margin-top:8px; margin-bottom:0;">承認されたメールアドレスと専用アクセスコードを入力してください。</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("member_login_form"):
        input_email = st.text_input("📧 登録メールアドレス", placeholder="example@gmail.com")
        input_code = st.text_input("🔑 専用アクセスコード（8桁コード）", type="password")
        if st.form_submit_button("🔓 ログインして解析システムを開く", use_container_width=True):
            clean_mail = input_email.strip().lower()
            expected_code = generate_member_passcode(clean_mail)
            user_rec = db.get(clean_mail)
            is_approved = (user_rec and user_rec.get("status") == "approved") or (clean_mail == ADMIN_EMAIL.strip().lower())
            is_valid_code = hmac.compare_digest(input_code.strip().upper(), expected_code) or (clean_mail == ADMIN_EMAIL.strip().lower() and input_code.strip() == "ADMIN777")
            if is_approved and is_valid_code:
                st.session_state["authenticated_user"] = clean_mail
                st.query_params["u"] = clean_mail
                st.query_params["t"] = generate_admin_action_token(clean_mail, "session_keep")
                st.rerun()
            elif user_rec and user_rec.get("status") == "pending":
                st.warning("⏳ 現在、管理者による承認審査中です。")
            elif not is_approved:
                st.error("⚠️ このメールアドレスは未登録または利用停止中です。下のフォームから申請してください。")
            else:
                st.error("⚠️ 専用アクセスコードが正しくありません。")

    st.markdown("---")
    st.markdown("##### 📩 新規会員登録・利用許可の申請はこちら")
    with st.form("member_apply_form"):
        ap_name = st.text_input("👤 お名前（ニックネーム可）", placeholder="山田 太郎")
        ap_mail = st.text_input("📧 メールアドレス", placeholder="your_email@example.com")
        ap_note = st.text_input("💬 ひとこと・紹介者など（任意）")
        if st.form_submit_button("📨 管理者に利用申請を送信する", use_container_width=True):
            c_mail = ap_mail.strip().lower()
            if not c_mail or "@" not in c_mail:
                st.error("⚠️ 正しいメールアドレスを入力してください。")
            else:
                now_s = datetime.now().strftime("%Y-%m-%d %H:%M")
                passcode = generate_member_passcode(c_mail)
                db[c_mail] = {"name": ap_name.strip() or "未入力", "email": c_mail, "status": "pending", "passcode": passcode, "applied_at": now_s, "approved_at": "-", "note": ap_note.strip()}
                save_members_db(db)
                cfg = load_smtp_config()
                base_url = cfg.get("app_base_url", "http://localhost:8501").rstrip("/")
                tok_ap = generate_admin_action_token(c_mail, "approve")
                tok_rj = generate_admin_action_token(c_mail, "reject")
                approve_url = f"{base_url}/?admin_action=approve&email={urllib.parse.quote(c_mail)}&name={urllib.parse.quote(ap_name)}&token={tok_ap}"
                reject_url = f"{base_url}/?admin_action=reject&email={urllib.parse.quote(c_mail)}&token={tok_rj}"
                admin_body = f"会員登録申請が届きました。\n・名前: {ap_name}\n・メール: {c_mail}\n・備考: {ap_note}\n・発行コード: {passcode}\n\n▼ワンクリック承認\n{approve_url}\n\n▼ワンクリック却下\n{reject_url}\n"
                send_auto_email(ADMIN_EMAIL, f"【会員申請】{ap_name}様 ({c_mail})", admin_body)
                st.success("✅ 申請を受け付けました！管理者の承認が完了すると専用パスコードが発行されます。")
    st.stop()

check_member_authentication()

# ==========================================
# 📈 セッション初期化 ＆ ページ履歴管理
# ==========================================
for k, default_v in [
    ("active_debates", {}), ("debate_Animated", set()), ("stock_chats", {}),
    ("watchlist", {}), ("navigation_page", "TOP"), ("nav_history", ["TOP"]),
    ("custom_search_code", ""), ("scroll_to_chat_key", None), ("trigger_scroll_top", False)
]:
    if k not in st.session_state:
        st.session_state[k] = default_v

def navigate_to(page_name: str):
    if st.session_state["navigation_page"] != page_name:
        st.session_state["nav_history"].append(st.session_state["navigation_page"])
        st.session_state["navigation_page"] = page_name

def navigate_back():
    if len(st.session_state["nav_history"]) > 1:
        st.session_state["navigation_page"] = st.session_state["nav_history"].pop()
    else:
        st.session_state["navigation_page"] = "TOP"
    if "nav" in st.query_params: del st.query_params["nav"]
    st.session_state["custom_search_code"] = ""
    st.session_state["trigger_scroll_top"] = True

# ==========================================
# 🏢 企業ロゴマーク ＆ CSSスタイル
# ==========================================
COMPANY_DOMAINS = {
    "8035.T": "tel.co.jp", "6857.T": "advantest.com", "6920.T": "lasertec.co.jp", "6146.T": "disco.co.jp",
    "6526.T": "socionext.com", "7735.T": "screen.co.jp", "6315.T": "towa.co.jp", "6723.T": "renesas.com",
    "4063.T": "shinetsu.co.jp", "3436.T": "sumcosi.com", "6323.T": "rorze.com", "6871.T": "micronics.co.jp",
    "NVDA": "nvidia.com", "AMD": "amd.com", "MU": "micron.com", "TSM": "tsmc.com", "AVGO": "broadcom.com", "ARM": "arm.com", "SMCI": "supermicro.com",
    "9984.T": "group.softbank", "3778.T": "sakura.ad.jp", "7011.T": "mhi.com", "7012.T": "khi.co.jp",
    "7013.T": "ihi.co.jp", "3993.T": "pkshatech.com", "4180.T": "appier.com", "5032.T": "anycolor.co.jp",
    "4385.T": "about.mercari.com", "7974.T": "nintendo.co.jp", "8306.T": "mufg.jp",
    "MSFT": "microsoft.com", "PLTR": "palantir.com", "META": "meta.com", "GOOGL": "abc.xyz", "CRWD": "crowdstrike.com",
    "5803.T": "fujikura.co.jp", "5801.T": "furukawa.co.jp", "5802.T": "sei.co.jp", "6501.T": "hitachi.co.jp",
    "9509.T": "hepco.co.jp", "9508.T": "kyuden.co.jp", "6622.T": "daihen.co.jp", "1942.T": "kandenko.co.jp",
    "VST": "vistracorp.com", "CEG": "constellationenergy.com", "GEV": "gevernova.com",
    "5595.T": "i-qps.net", "186A.T": "astroscale.com", "9348.T": "ispace-inc.com", "9412.T": "skyperfectjsat.space",
    "9433.T": "kddi.com", "7203.T": "global.toyota", "TSLA": "tesla.com", "RKLB": "rocketlabusa.com", "ASTS": "ast-science.com", "COIN": "coinbase.com",
    "5253.T": "cover-corp.com", "9166.T": "genda.jp", "216A.T": "corp.timee.co.jp", "285A.T": "kioxia.com",
    "141A.T": "trial-holdings.inc", "5243.T": "note.jp", "247A.T": "ai-robotics.co.jp", "153A.T": "caulis.jp", "3350.T": "metaplanet.jp",
    "IONQ": "ionq.com", "RGTI": "rigetti.com", "SOUN": "soundhound.com", "RDDT": "redditinc.com", "ALAB": "asteralabs.com"
}

def get_company_logo_html(full_code: str, name: str) -> str:
    domain = COMPANY_DOMAINS.get(full_code, "")
    clean_name = name.replace(" (米)", "").replace(" (米IPO)", "").strip()
    initial = clean_name[0] if clean_name else "📈"
    fallback_url = f"https://ui-avatars.com/api/?name={urllib.parse.quote(initial)}&background=0f172a&color=fbbf24&bold=true&size=64"
    logo_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=128" if domain else fallback_url
    return f'<img src="{logo_url}" onerror="this.onerror=null;this.src=\'{fallback_url}\';" class="company-logo-img" alt="logo" />'

nav_p = st.session_state.get("navigation_page", "TOP")
curr_page_badge = "👑 管理者コンソール" if nav_p == "ADMIN" else ("📋 監視リスト表示中" if nav_p == "WATCHLIST" else "📊 ランキング解析")
curr_login_user = st.session_state.get("authenticated_user", "")
is_admin_user = (curr_login_user == ADMIN_EMAIL.strip().lower())

admin_floating_link_html = ""
if is_admin_user:
    db_now = load_members_db()
    pend_cnt = sum(1 for v in db_now.values() if v.get("status") == "pending")
    u_enc = urllib.parse.quote(curr_login_user)
    t_enc = generate_admin_action_token(curr_login_user, "session_keep")
    pend_badge = f"({pend_cnt})" if pend_cnt > 0 else ""
    target_nav = "TOP" if nav_p == "ADMIN" else "ADMIN"
    btn_txt = "📊 解析TOPへ戻る" if nav_p == "ADMIN" else f"👑 管理ページ{pend_badge}"
    admin_floating_link_html = f'<div class="nav-divider"></div><a href="?u={u_enc}&t={t_enc}&nav={target_nav}" target="_self" class="admin-pill">{btn_txt}</a>'

st.markdown('<div id="page_top_anchor"></div>', unsafe_allow_html=True)
st.markdown(f"""
<style>
html, body, [class*="css"] {{ font-size: 15.5px; }}
.block-container {{ padding-top: 3.6rem !important; padding-bottom: 3rem !important; max-width: 800px !important; }}
button[data-baseweb="tab"] {{ font-size: 13.5px !important; font-weight: 700 !important; padding: 8px 14px !important; }}
.floating-glass-nav {{ position: fixed; top: 10px; left: 50%; transform: translateX(-50%); z-index: 999990; display: flex; align-items: center; gap: 6px; padding: 5px 13px; background: rgba(15, 23, 42, 0.78); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.18); border-radius: 999px; box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25); white-space: nowrap; }}
.floating-glass-nav a {{ color: #f8fafc !important; text-decoration: none !important; font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 999px; }}
.floating-glass-nav .nav-divider {{ width: 1px; height: 12px; background: rgba(255, 255, 255, 0.2); }}
.floating-glass-nav .algo-pill {{ background: rgba(16, 185, 129, 0.2); border: 1px solid rgba(16, 185, 129, 0.45); color: #6ee7b7 !important; font-size: 11.5px; padding: 2px 8px; border-radius: 999px; }}
.floating-glass-nav .admin-pill {{ background: linear-gradient(135deg, #f59e0b, #d97706); color: #0f172a !important; font-weight: 800 !important; padding: 3px 10px !important; border-radius: 999px; }}
.company-logo-img {{ width: 38px; height: 38px; border-radius: 9px; object-fit: contain; background: #ffffff; padding: 3px; border: 1px solid #e2e8f0; }}
.rank-card, .search-result-card {{ background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%) !important; color: #0f172a !important; border-radius: 16px; padding: 18px; margin-bottom: 13px; box-shadow: 0 6px 20px rgba(15, 23, 42, 0.07); border: 1px solid #e2e8f0; border-left: 6px solid #e11d48; }}
.rank-card *, .search-result-card * {{ color: #0f172a; }}
.search-result-card {{ background: linear-gradient(180deg, #fffbeb 0%, #fef3c7 100%) !important; border-left-color: #d97706; }}
.prob-badge {{ font-size: 25px; font-weight: 800; color: #dc2626 !important; }}
.rank-badge {{ display: inline-block; background: linear-gradient(135deg, #f59e0b, #d97706); color: #ffffff !important; padding: 3px 10px; border-radius: 999px; font-size: 12.5px; font-weight: 700; margin-right: 5px; }}
.score-badge {{ display: inline-block; background: #0f172a; color: #f8fafc !important; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; }}
.inst-badge {{ display: inline-block; background: linear-gradient(135deg, #1d4ed8, #2563eb); color: #ffffff !important; padding: 3px 9px; border-radius: 999px; font-size: 12px; font-weight: 700; margin-left: 4px; }}
.board5ch-badge {{ display: inline-block; background: linear-gradient(135deg, #059669, #10b981); color: #ffffff !important; padding: 3px 9px; border-radius: 999px; font-size: 12px; font-weight: 700; margin-left: 4px; }}
.tokugai-badge {{ display: inline-block; background: linear-gradient(135deg, #d97706, #f59e0b); color: #ffffff !important; padding: 3px 9px; border-radius: 999px; font-size: 12px; font-weight: 700; margin-left: 4px; }}
.winrate-bar {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; background: #fff1f2 !important; border: 1px solid #fecdd3; border-radius: 10px; padding: 8px 6px; margin-top: 9px; text-align: center; }}
.signal-10tier-badge {{ display: flex; align-items: center; justify-content: space-between; padding: 8px 14px; border-radius: 10px; font-size: 14px; font-weight: 800; margin-bottom: 10px; }}
.inst-box {{ background: #eff6ff !important; border: 1px solid #bfdbfe; border-left: 4px solid #2563eb; border-radius: 9px; padding: 8px 12px; margin-top: 7px; font-size: 12.5px; color: #1e3a8a !important; }}
.inst-box * {{ color: #1e3a8a !important; }}
.squeeze-box {{ background: #fff1f2 !important; border: 1px solid #fecdd3; border-left: 4px solid #e11d48; border-radius: 9px; padding: 8px 12px; margin-top: 6px; font-size: 12.5px; color: #881337 !important; }}
.squeeze-box * {{ color: #881337 !important; }}
.pts-tokugai-box {{ background: #fffbeb !important; border: 1px solid #fde68a; border-left: 4px solid #d97706; border-radius: 9px; padding: 8px 12px; margin-top: 6px; font-size: 12.5px; color: #78350f !important; }}
.pts-tokugai-box * {{ color: #78350f !important; }}
.board5ch-box {{ background: #ecfdf5 !important; border: 1px solid #a7f3d0; border-left: 4px solid #059669; border-radius: 9px; padding: 8px 12px; margin-top: 6px; font-size: 12.5px; color: #064e3b !important; }}
.board5ch-box * {{ color: #064e3b !important; }}
.delicate-box {{ background: #f8fafc !important; border: 1px solid #cbd5e1; border-left: 4px solid #7c3aed; border-radius: 9px; padding: 9px 12px; margin-top: 7px; font-size: 12.5px; line-height: 1.6; color: #1e293b !important; }}
.metrics-row {{ display: flex; flex-wrap: wrap; gap: 6px 12px; margin-top: 8px; font-size: 12px; background: #f1f5f9 !important; padding: 8px 12px; border-radius: 8px; border: 1px solid #e2e8f0; }}
.trade-plan-box {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-top: 8px; background: #ffffff !important; padding: 9px 6px; border-radius: 10px; border: 1px solid #cbd5e1; text-align: center; }}
.sizing-box {{ background: linear-gradient(90deg, #f0fdf4, #dcfce7) !important; border: 1px solid #86efac; border-radius: 9px; padding: 8px 12px; margin-top: 8px; font-size: 12.5px; color: #166534 !important; }}
.ai-council-box {{ background: linear-gradient(135deg, #090d16, #1e293b); color: #f8fafc !important; border-radius: 14px; padding: 16px; margin-top: 8px; margin-bottom: 12px; }}
.ai-council-box * {{ color: #f8fafc; }}
.ai-agent-card {{ background: rgba(255, 255, 255, 0.06); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 10px 13px; margin-bottom: 7px; font-size: 13px; line-height: 1.6; }}
.consensus-banner {{ background: linear-gradient(135deg, #1e1b4b, #312e81); border: 1.5px solid #818cf8; border-radius: 12px; padding: 14px; margin-top: 10px; font-size: 13px; }}
.consensus-section {{ background: rgba(255, 255, 255, 0.07); border-left: 3px solid #fbbf24; border-radius: 6px; padding: 8px 11px; margin-top: 7px; }}
.qa-answer-card {{ background: #f8fafc !important; border: 1px solid #cbd5e1; border-left: 4px solid #3b82f6; border-radius: 10px; padding: 13px 15px; margin-top: 8px; margin-bottom: 10px; font-size: 13px !important; line-height: 1.75 !important; color: #1e293b !important; }}
.qa-answer-card * {{ color: #1e293b !important; }}
.qa-answer-card .qa-q-header {{ font-weight: 700; background: #e2e8f0; padding: 4px 10px; border-radius: 6px; margin-bottom: 8px; display: inline-block; font-size: 12px !important; }}
.qa-answer-card b, .qa-answer-card strong {{ color: #1d4ed8 !important; font-weight: 700; }}
</style>
<div class="floating-glass-nav">
    <a href="#page_top_anchor">⬆️ ページTOPへ</a>
    <div class="nav-divider"></div>
    <a href="#search_box_anchor">🔍 検索・タブ</a>
    <div class="nav-divider"></div>
    <span class="algo-pill">🧬 繊細クオンツ＆勝率解析</span>
    {admin_floating_link_html}
</div>
""", unsafe_allow_html=True)

if is_admin_user:
    db_top = load_members_db()
    pend_top_cnt = sum(1 for v in db_top.values() if v.get("status") == "pending")
    adm_bar_c1, adm_bar_c2 = st.columns([2.3, 1.4])
    with adm_bar_c1:
        st.info(f"👑 **管理者モード** ｜ 承認待ち: **{pend_top_cnt}件** / 登録会員: **{len(db_top)}名**")
    with adm_bar_c2:
        if st.session_state.get("navigation_page") == "ADMIN":
            if st.button("📊 株価解析TOP画面へ戻る", key="top_bar_to_main_btn", use_container_width=True):
                st.session_state["navigation_page"] = "TOP"
                if "nav" in st.query_params: del st.query_params["nav"]
                st.rerun()
        else:
            if st.button(f"👑 会員管理・削除ページを開く ({pend_top_cnt}件待)", key="top_bar_to_admin_btn", use_container_width=True):
                navigate_to("ADMIN")
                st.query_params["nav"] = "ADMIN"
                st.rerun()

if st.session_state.get("trigger_scroll_top"):
    components.html('<script>setTimeout(function(){window.parent.scrollTo({top:0,behavior:"smooth"});},80);</script>', height=0)
    st.session_state["trigger_scroll_top"] = False

# --- サイドバー設定 ---
st.sidebar.header("🧭 ナビゲーション")
s_col1, s_col2 = st.sidebar.columns(2)
with s_col1:
    if st.button("⬆️ ページTOP", key="side_top_btn", use_container_width=True):
        st.session_state["navigation_page"] = "TOP"
        if "nav" in st.query_params: del st.query_params["nav"]
        st.session_state["custom_search_code"] = ""
        st.session_state["trigger_scroll_top"] = True
        st.rerun()
with s_col2:
    if st.button("⬅️ 前の画面", key="side_back_btn", use_container_width=True):
        navigate_back()
        st.rerun()

if st.sidebar.button(f"📋 監視ウォッチリスト ({len(st.session_state['watchlist'])}銘柄)", key="side_wl_btn", use_container_width=True):
    navigate_to("WATCHLIST")
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("💰 資金管理＆リスク設定")
total_capital = st.sidebar.number_input("総投資資金 (円 / ドル)", min_value=10000, max_value=1000000000, value=1000000, step=50000)
risk_tolerance_pct = st.sidebar.slider("1トレード許容リスク (%)", min_value=0.5, max_value=5.0, value=2.0, step=0.5)

st.sidebar.markdown("---")
st.sidebar.header("🧬 最新クオンツ自動適応設定")
auto_evolve_algo = st.sidebar.checkbox("🧬 最新クオンツ（Hurst指数・Kalman・Kyleλ）自動組込", value=True)
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
    macro_tickers = {
        "sp500":  {"codes": ["^GSPC"],         "label": "🇺🇸 米S&P500"},
        "sox":    {"codes": ["^SOX"],          "label": "💽 米SOX半導体"},
        "usdjpy": {"codes": ["JPY=X"],         "label": "💴 ドル円"},
        "nk_fut": {"codes": ["NIY=F", "^N225"], "label": "🇯🇵 日経先物"},
        "vix":    {"codes": ["^VIX"],          "label": "⚡ VIX指数"}
    }
    macro_data = {}
    for key, info in macro_tickers.items():
        fetched = False
        for c in info["codes"]:
            try:
                df_m = yf.Ticker(c).history(period="5d")
                if df_m is not None and not df_m.empty:
                    df_m = df_m.dropna(subset=['Close'])
                    if len(df_m) >= 2:
                        latest_c, prev_c = float(df_m['Close'].iloc[-1]), float(df_m['Close'].iloc[-2])
                        if prev_c != 0:
                            macro_data[key] = {"price": latest_c, "diff": round((latest_c - prev_c) / prev_c * 100, 2), "label": info["label"]}
                            fetched = True
                            break
            except Exception:
                continue
        if not fetched:
            macro_data[key] = {"price": 0.0, "diff": 0.0, "label": info["label"]}
    return macro_data

def compute_latest_quant_metrics(close_series: pd.Series, vol_ratio_series: pd.Series, day_ret_series: pd.Series) -> dict:
    prices = close_series.dropna().values
    hurst_val = 0.52
    if len(prices) >= 30:
        try:
            lags = range(2, 12)
            tau = [max(float(np.std(np.subtract(prices[lag:], prices[:-lag]))), 1e-6) for lag in lags]
            poly = np.polyfit(np.log(list(lags)), np.log(tau), 1)
            hurst_val = float(np.clip(poly[0] * 1.35, 0.25, 0.85))
        except Exception:
            hurst_val = 0.52

    kalman_est = float(prices[-1])
    if len(prices) >= 10:
        x_est, p_est = float(prices[0]), 1.0
        for z in prices[1:]:
            p_pred = p_est + 0.03
            k_gain = p_pred / (p_pred + 0.12)
            x_est = x_est + k_gain * (float(z) - x_est)
            p_est = (1.0 - k_gain) * p_pred
        kalman_est = x_est
    kalman_bull_pct = round((float(prices[-1]) - kalman_est) / max(kalman_est, 1e-4) * 100, 2)
    kyle_lambda = round(float(day_ret_series.tail(5).abs().mean() / max(vol_ratio_series.tail(5).mean(), 0.3)), 2)
    return {"hurst": round(hurst_val, 2), "kalman_est": kalman_est, "kalman_bull_pct": kalman_bull_pct, "kyle_lambda": kyle_lambda}

# ==========================================
# 🔬 繊細な銘柄別ミクロ構造・勝率解析エンジン
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
        df['BB_Std'] = df['Close'].rolling(20).std().replace(0, np.nan)
        df['BB_Z'] = ((df['Close'] - df['MA20']) / df['BB_Std']).fillna(0.0)
        df['MA5_Dev'] = ((df['Close'] - df['MA5']) / df['MA5'] * 100).fillna(0.0)
        df['MA20_Dev'] = ((df['Close'] - df['MA20']) / df['MA20'] * 100).fillna(0.0)

        df['Vol_MA5'] = df['Volume'].rolling(5).mean().replace(0, np.nan)
        df['Vol_MA20'] = df['Volume'].rolling(20).mean().replace(0, np.nan)
        df['Vol_Ratio'] = (df['Volume'] / df['Vol_MA20']).fillna(1.0)
        df['Vol_Accel_5d'] = (df['Volume'] / df['Vol_MA5']).fillna(1.0)

        delta = df['Close'].diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        df['RSI'] = (100 - (100 / (1 + gain / loss.replace(0, np.nan)))).fillna(50.0)

        ema12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = ema12 - ema26
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

        tr = pd.concat([df['High'] - df['Low'], (df['High'] - df['Prev_Close']).abs(), (df['Low'] - df['Prev_Close']).abs()], axis=1).max(axis=1)
        df['ATR'] = tr.rolling(14).mean().fillna(df['Close'] * 0.02)
        df['ATR_Pct'] = (df['ATR'] / df['Close'] * 100).fillna(2.0)

        high_low = (df['High'] - df['Low']).replace(0, np.nan)
        df['Close_Pos'] = ((df['Close'] - df['Low']) / high_low).fillna(0.5)
        body_top = df[['Open', 'Close']].max(axis=1)
        body_bot = df[['Open', 'Close']].min(axis=1)
        df['Upper_Shadow'] = ((df['High'] - body_top) / high_low).fillna(0.0)
        df['Lower_Shadow'] = ((body_bot - df['Low']) / high_low).fillna(0.0)
        df['Body_Ratio'] = ((body_top - body_bot) / high_low).fillna(0.5)

        df['VWAP20'] = (((df['High'] + df['Low'] + df['Close']) / 3.0 * df['Volume']).rolling(20).sum() / df['Volume'].rolling(20).sum().replace(0, np.nan)).fillna(df['Close'])
        df['High_20'] = df['High'].shift(1).rolling(20).max().fillna(df['High'])
        df['Dist_High20'] = ((df['Close'] - df['High_20']) / df['High_20'] * 100).fillna(0.0)

        df['Signed_Order_Flow'] = ((df['Close'] - df['Open']) / high_low).fillna(0.0) * df['Vol_Ratio']
        df['VPIN_5d'] = df['Signed_Order_Flow'].rolling(5).mean().fillna(0.0)
        df['Amihud_Impact'] = (df['Day_Return'].abs() / df['Vol_Ratio'].replace(0, 1.0)).fillna(1.0)
        df['Amihud_Ratio'] = (df['Amihud_Impact'] / df['Amihud_Impact'].rolling(20).mean().replace(0, 1.0)).fillna(1.0)

        adv_q = compute_latest_quant_metrics(df['Close'], df['Vol_Ratio'], df['Day_Return'].fillna(0.0))
        hurst_v, kalman_bull, kyle_lam = adv_q["hurst"], adv_q["kalman_bull_pct"], adv_q["kyle_lambda"]

        cond_inst_accum = (df['VPIN_5d'] >= 0.22) & (df['Close'] >= df['VWAP20']) & (df['Close_Pos'] >= 0.68)
        cond_5ch_surge = (df['Vol_Accel_5d'] >= 1.35) & (df['Close_Pos'] >= 0.72) & (df['Upper_Shadow'] <= 0.18) & (df['Close'] > df['Open'])
        cond_sq_breakout = (df['Close'] >= df['High_20'] * 0.992) & (df['Vol_Ratio'] >= 1.2) & (df['Close_Pos'] >= 0.7)

        df['Next_Open'] = df['Open'].shift(-1)
        df['Next_Close'] = df['Close'].shift(-1)
        df['Gap_Pct'] = (df['Next_Open'] - df['Close']) / df['Close'] * 100
        df['Morning_Up'] = df['Next_Open'] > df['Close']
        df['Intraday_Up'] = df['Next_Close'] > df['Next_Open']

        latest = df.iloc[-1]
        history = df.iloc[:-1].dropna(subset=['Next_Open', 'Next_Close', 'MA20', 'RSI'])
        if len(history) == 0: return None

        upper_sh = float(latest['Upper_Shadow'])
        lower_sh = float(latest['Lower_Shadow'])
        body_rt = float(latest['Body_Ratio'])
        vol_acc = float(latest['Vol_Accel_5d'])
        c_pos = float(latest['Close_Pos'])
        dist_h20 = float(latest['Dist_High20'])
        vpin_val = float(latest['VPIN_5d'])
        amihud_r = float(latest['Amihud_Ratio'])
        bb_z = float(latest['BB_Z'])
        ma5_dev = float(latest['MA5_Dev'])
        ma20_dev = float(latest['MA20_Dev'])

        # 🔬 ローソク足・板ミクロ構造の繊細な個別言語化
        if latest['Close'] > latest['Open']:
            if body_rt >= 0.75 and upper_sh <= 0.1:
                candle_desc = f"陽線丸坊主（実体率{int(body_rt*100)}%）で大引けまで買い注文が途切れない強い引け味"
            elif lower_sh >= 0.35:
                candle_desc = f"下ヒゲ（{int(lower_sh*100)}%）で場中の押し目売りを完全に吸収して陽線転換"
            elif upper_sh >= 0.35:
                candle_desc = f"陽線ながら上ヒゲ（{int(upper_sh*100)}%）が残り高値圏での利確売りも交錯"
            else:
                candle_desc = f"実体{int(body_rt*100)}%の堅調な陽線（引け位置{int(c_pos*100)}%）"
        else:
            if lower_sh >= 0.40:
                candle_desc = f"陰線ながら長い下ヒゲ（{int(lower_sh*100)}%）を付け安値圏で機関の指値買いが流入"
            elif upper_sh >= 0.35:
                candle_desc = f"上ヒゲ（{int(upper_sh*100)}%）を伴う陰線で戻り待ちのシコリ玉消化が必要な波形"
            else:
                candle_desc = f"前日比{latest['Day_Return']:+.2f}%の調整陰線（引け位置{int(c_pos*100)}%）"

        # 出来高3日推移とボリンジャー位置の繊細記述
        r3_vols = [round(float(v), 2) for v in df['Vol_Ratio'].tail(3).values]
        vol_trend_str = f"{r3_vols[0]}倍→{r3_vols[1]}倍→本日{r3_vols[2]}倍"
        bb_desc = f"ボリンジャー{bb_z:+.2f}σ（20日線乖離{ma20_dev:+.2f}% / 5日線乖離{ma5_dev:+.2f}%）"

        delicate_narrative = (
            f"🔬 <b>繊細チャート・需給診断</b>：{candle_desc}。"
            f"直近3日間の出来高推移は【<b>{vol_trend_str}</b>】、位置は <b>{bb_desc}</b>。"
            f"VPIN({vpin_val:+.2f})と価格弾性({amihud_r:.2f}倍)から、"
            f"{'売り板が薄く少額の成行買いで上値へ飛びやすい状態' if amihud_r >= 1.08 else '板の厚みを伴いながらVWAP沿いに実需が積み上がる状態'}です。"
        )

        # スコア算出
        inst_raw = 50.0 + vpin_val * 45.0 + (c_pos - 0.5) * 25.0 + (10.0 if float(latest['Close']) >= float(latest['VWAP20']) else 0.0)
        if use_latest_algo and hurst_v >= 0.56 and kalman_bull > 0: inst_raw += 7.0
        if float(latest['Day_Return']) > 0.5 and amihud_r >= 1.15 and upper_sh <= 0.2:
            inst_raw += 12.0
            inst_status = f"🏦 機関の浮動株吸収・売り板枯渇 (VPIN {vpin_val:+.2f} / 弾性 {amihud_r:.2f}倍)"
        elif cond_inst_accum.iloc[-1]:
            inst_raw += 10.0
            inst_status = f"🏦 機関ステルス氷山買い集め検知 (VPIN {vpin_val:+.2f} / Kal乖離 {kalman_bull:+.1f}%)"
        elif vpin_val < -0.15:
            inst_raw -= 12.0
            inst_status = f"⚠️ 機関のTWAP売り執行警戒 (VPIN {vpin_val:+.2f})"
        else:
            inst_status = f"⚖️ 機関オーダーフロー中立 (VPIN {vpin_val:+.2f} / 弾性 {amihud_r:.2f}倍)"
        inst_score = int(min(max(round(inst_raw), 15), 99))

        board5ch_raw = 50.0 + (min(vol_acc, 3.0) - 1.0) * 18.0 + (c_pos - 0.5) * 30.0
        if upper_sh >= 0.38:
            board5ch_raw -= 25.0
            board5ch_status = f"⚠️ 上ヒゲシコリ玉警戒 (上ヒゲ{int(upper_sh*100)}%・下ヒゲ{int(lower_sh*100)}%)"
        elif dist_h20 >= -0.5 and upper_sh <= 0.15 and vol_acc >= 1.2:
            board5ch_raw += 18.0
            board5ch_status = f"🚀 5ch板・青天井ブレイク (上値シコリなし・5日出来高加速 {vol_acc:.2f}倍)"
        elif cond_5ch_surge.iloc[-1]:
            board5ch_raw += 12.0
            board5ch_status = f"🔥 5ch板・初動資金集中 (5日比 {vol_acc:.2f}倍急増＆引け位置{int(c_pos*100)}%)"
        else:
            board5ch_status = f"⚖️ 5ch板・通常需給 (5日加速 {vol_acc:.2f}倍 / 上ヒゲ{int(upper_sh*100)}% / 下ヒゲ{int(lower_sh*100)}%)"
        board5ch_score = int(min(max(round(board5ch_raw), 15), 99))

        sq_raw = 42.0 + (22.0 if dist_h20 >= 0 else (14.0 if dist_h20 >= -2.5 else 4.0)) + min(float(latest['Vol_Ratio']), 3.0) * 8.0 + (c_pos - 0.5) * 24.0
        squeeze_score = int(min(max(round(sq_raw), 15), 99))
        squeeze_type = "🔥 20日高値ブレイク踏み上げ" if cond_sq_breakout.iloc[-1] else ("⚡ 踏み上げトリガー寸前" if dist_h20 >= -2.0 and c_pos >= 0.72 else f"⚖️ 20日高値乖離 {dist_h20:+.2f}%")

        if cond_inst_accum.iloc[-1]:
            signal = "🏦 機関VPINステルス買い＋VWAP順行"
            sub = history[cond_inst_accum.reindex(history.index, fill_value=False)]
        elif cond_5ch_surge.iloc[-1]:
            signal = "🔥 5ch初動イナゴ集中＋高値引け"
            sub = history[cond_5ch_surge.reindex(history.index, fill_value=False)]
        elif cond_sq_breakout.iloc[-1]:
            signal = "🚀 20日高値ブレイク・踏み上げ"
            sub = history[cond_sq_breakout.reindex(history.index, fill_value=False)]
        elif latest['Day_Return'] > 0:
            signal = "📈 陽線トレンド継続"
            sub = history[history['Day_Return'] > 0]
        else:
            signal = "☁️ 押し目・調整反発狙い"
            sub = history[history['Day_Return'] <= 0]

        if len(sub) < 5: sub = history

        # 🎯 4大勝率の精密算出
        total = len(sub)
        wins = int(sub['Morning_Up'].sum())
        prob = round((wins / total) * 100, 1)  # ①翌朝GU勝率
        intraday_win_rate = round(float(sub['Intraday_Up'].mean() * 100), 1)  # ②寄り後陽線勝率
        trend_sub = history[history['Close'] >= history['MA20']]
        trend_win_rate = round(float((trend_sub['Morning_Up'] | trend_sub['Intraday_Up']).mean() * 100), 1) if len(trend_sub) >= 5 else prob  # ③トレンド順張り勝率
        total_win_rate = round(prob * 0.5 + intraday_win_rate * 0.3 + trend_win_rate * 0.2, 1)  # ④総合勝率

        avg_gap = round(float(sub['Gap_Pct'].mean()), 2)
        win_gaps = sub[sub['Morning_Up']]['Gap_Pct']
        loss_gaps = sub[~sub['Morning_Up']]['Gap_Pct']
        avg_win = float(win_gaps.mean()) if len(win_gaps) > 0 else 0.5
        max_win_gap = round(float(win_gaps.max()), 2) if len(win_gaps) > 0 else 1.5
        avg_loss = abs(float(loss_gaps.mean())) if len(loss_gaps) > 0 else 0.5
        payoff_ratio = round(avg_win / max(avg_loss, 0.1), 2)
        expected_edge = round((prob / 100 * avg_win) - ((100 - prob) / 100 * avg_loss), 2)

        sox_diff = macro["sox"]["diff"] if macro else 0.0
        nk_diff = macro["nk_fut"]["diff"] if macro else 0.0
        sp_diff = macro["sp500"]["diff"] if macro else 0.0
        vix_val = macro["vix"]["price"] if macro else 18.0
        is_jp = ".T" in code
        overnight_impact = (nk_diff * 0.5 + sox_diff * 0.4) if is_jp else (sp_diff * 0.5 + sox_diff * 0.4)
        pts_gap_pct = round(avg_gap * 0.5 + overnight_impact * 0.6 + max(0.0, (inst_score - 55) * 0.025), 2)

        close_val = float(latest['Close'])
        atr_val = float(latest['ATR'])
        high20_val = float(latest['High_20'])
        pts_est_val = close_val * (1.0 + pts_gap_pct / 100.0)
        tokugai_pct_threshold = max(2.2, min(round(float(latest['ATR_Pct']) * 0.95, 2), 4.0))
        tokugai_line_val = close_val * (1.0 + tokugai_pct_threshold / 100.0)

        tokugai_raw = 18.0 + max(0.0, pts_gap_pct) * 14.0 + max(0.0, inst_score - 50) * 0.4 + max(0.0, board5ch_score - 50) * 0.4 + max(0.0, squeeze_score - 50) * 0.4
        tokugai_prob = int(min(max(round(tokugai_raw), 5), 98))
        tokugai_status = "🚨 特買い（気配切り上げ）濃厚" if tokugai_prob >= 70 else ("🌅 買い気配先行スタート優勢" if tokugai_prob >= 52 else "⚖️ 通常気配スタート")

        evo_bonus = ((hurst_v - 0.5) * 18.0 + np.clip(kalman_bull * 1.2, -5.0, 6.0) + (4.0 if vix_val >= 22.0 and inst_score >= 65 else 0.0)) if use_latest_algo else 0.0
        base_score = min(max(prob * 0.52, 10), 44) + min(max((expected_edge + 0.3) * 12, 0), 14)
        ai_score = int(min(max(round(base_score + (round((inst_score - 50) * 0.22) if boost_inst else 0) + (round((board5ch_score - 50) * 0.18) if boost_5ch else 0) + (round((squeeze_score - 50) * 0.16) if boost_squeeze else 0) + (round((tokugai_prob - 45) * 0.14) if boost_tokugai else 0) + evo_bonus), 15), 99))
        survival_power = round(ai_score * 0.35 + inst_score * 0.25 + board5ch_score * 0.20 + squeeze_score * 0.10 + min(float(latest['ATR_Pct']) * 3.5, 12.0) + max(0.0, evo_bonus), 1)

        tier_val = ai_score * 0.40 + total_win_rate * 0.25 + inst_score * 0.20 + board5ch_score * 0.15 - (12.0 if upper_sh >= 0.42 else 0.0) - (10.0 if vpin_val <= -0.20 else 0.0)
        tiers = [
            (80, 10, "【第10段階：🌟絶対買い】機関VPIN極大・翌朝爆上げ濃厚", "#ffffff", "linear-gradient(135deg, #991b1b, #dc2626)"),
            (75, 9,  "【第9段階：🔥絶対買い】特買い・踏み上げ急騰ロックオン", "#ffffff", "linear-gradient(135deg, #b91c1c, #ef4444)"),
            (70, 8,  "【第8段階：⭕買い】機関買い集め・強気順張り", "#ffffff", "linear-gradient(135deg, #c2410c, #ea580c)"),
            (65, 7,  "【第7段階：⭕買い】好需給・VWAP押し目買い優勢", "#ffffff", "linear-gradient(135deg, #b45309, #d97706)"),
            (60, 6,  "【第6段階：👀様子見(買い寄り)】初動の気配確認後に打診", "#0f172a", "linear-gradient(135deg, #fde047, #facc15)"),
            (55, 5,  "【第5段階：👀様子見(中立)】方向感待ち・深追い禁物", "#f8fafc", "linear-gradient(135deg, #475569, #64748b)"),
            (50, 4,  "【第4段階：⚠️危険(売り優勢)】上値シコリ玉・寄り天警戒", "#ffffff", "linear-gradient(135deg, #78350f, #b45309)"),
            (45, 3,  "【第3段階：⚠️危険】機関の売り浴びせ・下落リスク大", "#ffffff", "linear-gradient(135deg, #7f1d1d, #991b1b)"),
            (40, 2,  "【第2段階：☠️絶対手を出すな】需給崩壊・高値掴み厳禁", "#ffffff", "linear-gradient(135deg, #450a0a, #7f1d1d)"),
            (-99, 1, "【第1段階：☠️絶対手を出すな】全面売り圧力・エントリー禁止", "#ffffff", "linear-gradient(135deg, #1e1b4b, #450a0a)")
        ]
        for th, t_num, t_lbl, t_col, t_bg in tiers:
            if tier_val >= th:
                tier_num, tier_label, tier_color, tier_bg = t_num, t_lbl, t_col, t_bg
                break

        tp_val = max(pts_est_val, close_val) + (atr_val * 0.85)
        sl_val = close_val - (atr_val * 0.5)
        allowed_risk_money = total_capital * (risk_tolerance_pct / 100.0)
        shares = max(1, int(allowed_risk_money / max(close_val - sl_val, close_val * 0.005)))
        fmt_p = lambda v: f"{v:,.0f}円" if is_jp else f"${v:,.2f}"

        return {
            "full_code": code, "code": code.replace(".T", ""), "name": name, "genre": genre,
            "price": fmt_p(close_val), "raw_close": close_val,
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
            "tokugai_prob": tokugai_prob, "tokugai_line": fmt_p(tokugai_line_val),
            "tokugai_pct_threshold": tokugai_pct_threshold, "tokugai_status": tokugai_status,
            "diff": round(float(latest['Day_Return']), 2), "signal": signal,
            "prob": prob, "intraday_win_rate": intraday_win_rate, "trend_win_rate": trend_win_rate, "total_win_rate": total_win_rate,
            "count": f"{wins}/{total}回", "gap": avg_gap, "max_win_gap": max_win_gap,
            "rsi": round(float(latest['RSI']), 1), "vol_ratio": round(float(latest['Vol_Ratio']), 2),
            "macd_state": "強気↑" if latest['MACD_Hist'] > 0 else "調整↓",
            "atr_pct": round(float(latest['ATR_Pct']), 1), "payoff": payoff_ratio, "edge": expected_edge,
            "ai_score": ai_score, "survival_power": survival_power, "theme": theme,
            "tier_num": tier_num, "tier_label": tier_label, "tier_color": tier_color, "tier_bg": tier_bg,
            "lot_info": {"shares": shares, "position_value": shares * close_val, "capital_ratio": round((shares * close_val / total_capital) * 100, 1), "risk_amount": allowed_risk_money}
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
                        all_list.append(res)
                        seen.add(c)
            except Exception:
                continue
    return genre_Map, all_list

@st.cache_data(ttl=600)
def fetch_single_stock(code, macro, boost_inst, boost_5ch, boost_squeeze, boost_tokugai, use_latest_algo):
    df_c = yf.Ticker(code).history(period="6mo")
    info = KNOWN_STOCKS.get(code, {"name": code.replace(".T", ""), "theme": "個別指定銘柄", "genre": "個別検索"})
    return analyze_single_dataframe(df_c, code, info["name"], info["theme"], info["genre"], macro, boost_inst, boost_5ch, boost_squeeze, boost_tokugai, use_latest_algo)

@st.cache_data(ttl=300)
def fetch_5m_intraday_algo(full_code, trigger_high20=None):
    try:
        df5 = yf.Ticker(full_code).history(period="5d", interval="5m")
        if df5 is None or df5.empty or len(df5) < 12: return None
        df5 = df5.dropna(subset=['Close', 'Open', 'High', 'Low', 'Volume'])
        dates = df5.index.date
        day_df = df5[dates == dates[-1]].copy()
        if len(day_df) < 6: day_df = df5.tail(36).copy()

        tp = (day_df['High'] + day_df['Low'] + day_df['Close']) / 3.0
        day_df['VWAP_5m'] = ((tp * day_df['Volume']).cumsum() / day_df['Volume'].cumsum().replace(0, np.nan)).fillna(day_df['Close'])
        latest_c = float(day_df['Close'].iloc[-1])
        latest_vwap5 = float(day_df['VWAP_5m'].iloc[-1])
        vwap5_dev = round((latest_c - latest_vwap5) / latest_vwap5 * 100, 2) if latest_vwap5 != 0 else 0.0
        is_jp = ".T" in full_code
        vwap5_fmt = f"{latest_vwap5:,.0f}円" if is_jp else f"${latest_vwap5:,.2f}"

        chart_df = pd.DataFrame({
            "Time": day_df.index.strftime("%H:%M"),
            "Open": day_df["Open"].astype(float).values, "High": day_df["High"].astype(float).values,
            "Low": day_df["Low"].astype(float).values, "Close": day_df["Close"].astype(float).values,
            "VWAP": day_df["VWAP_5m"].astype(float).values,
            "BarColor": np.where(day_df["Close"].values >= day_df["Open"].values, "陽線", "陰線")
        })
        return {"vwap5_price": vwap5_fmt, "vwap5_dev": vwap5_dev, "chart_date": str(dates[-1]), "chart_df": chart_df}
    except Exception:
        return None

def render_5m_candlestick_chart(m5):
    if not m5 or "chart_df" not in m5: return
    cdf = m5["chart_df"]
    base = alt.Chart(cdf).encode(x=alt.X("Time:N", sort=None, title=None))
    color_scale = alt.Scale(domain=["陽線", "陰線"], range=["#dc2626", "#2563eb"])
    wick = base.mark_rule(size=1.5).encode(y=alt.Y("Low:Q", scale=alt.Scale(zero=False), title="株価"), y2="High:Q", color=alt.Color("BarColor:N", scale=color_scale, legend=None))
    body = base.mark_bar(size=6).encode(y=alt.Y("Open:Q", scale=alt.Scale(zero=False)), y2="Close:Q", color=alt.Color("BarColor:N", scale=color_scale, legend=None))
    vwap_line = base.mark_line(color="#d97706", strokeWidth=2.5, strokeDash=[4, 2]).encode(y="VWAP:Q")
    st.altair_chart((wick + body + vwap_line).properties(height=180), use_container_width=True)

# ==========================================
# 🧠 7大AI【銘柄別・繊細コンテキスト合議】＆【リアルタイム深層リサーチ質問エンジン】
# ==========================================
def run_7ai_council_algorithm(r, m5=None):
    vwap_ref = m5['vwap5_price'] if m5 else r['vwap_price']
    half_lot = max(1, r['lot_info']['shares'] // 2)
    rem_lot = max(0, r['lot_info']['shares'] - half_lot)

    claude_s  = int(min(max(round(50 + (r["total_win_rate"] - 50) * 0.8 + (r["payoff"] - 1.0) * 15 - r["upper_shadow_pct"] * 0.2), 20), 99))
    grok_s    = int(min(max(round(45 + (r["board5ch_score"] - 50) * 0.45 + (r["squeeze_score"] - 50) * 0.35 + r["tokugai_prob"] * 0.15), 20), 99))
    chatgpt_s = int(min(max(round((r["ai_score"] + r["inst_score"] + claude_s) / 3.0), 20), 99))
    gemini_s  = int(min(max(round(50 + r["pts_gap_pct"] * 12 + (r["inst_score"] - 50) * 0.35), 20), 99))
    perp_s    = int(min(max(round(r["inst_score"] * 0.55 + r["board5ch_score"] * 0.45), 20), 99))
    gensp_s   = int(min(max(round((claude_s + grok_s + chatgpt_s + gemini_s + perp_s) / 5.0), 20), 99))
    nblm_s    = int(min(max(round(48 + (r["prob"] - 50) * 0.9 + (r["payoff"] - 1.0) * 12), 20), 99))
    final_s   = int(round((claude_s + grok_s + chatgpt_s + gemini_s + perp_s + gensp_s + nblm_s) / 7.0))

    claude_msg = (
        f"総合勝率 <b>{r['total_win_rate']}%</b>（翌朝GU勝率 <b>{r['prob']}%</b>・寄り後陽線勝率 <b>{r['intraday_win_rate']}%</b>）、"
        f"Hurst指数 <b>{r['hurst']}</b>、カルマン乖離 <b>{r['kalman_bull_pct']:+.2f}%</b> を監査。"
        f"本日の足型は「{r['candle_desc']}」のため、逆指値 <b>{r['sl_price']}</b> を置いた <b>{r['lot_info']['shares']:,}株</b> 投入が数理的最適解です。"
    )
    grok_msg = (
        f"出来高3日推移【<b>{r['vol_trend_str']}</b>】と5ch需給（{r['board5ch_status']}）を解析。"
        f"20日高値（<b>{r['squeeze_trigger_price']}</b>）まであと <b>{r['dist_to_high20']:+.2f}%</b> に迫っており、"
        f"特買い確率 <b>{r['tokugai_prob']}%</b>（発動ライン <b>{r['tokugai_line']}</b>）からのショートカバー連鎖を狙えます。"
    )
    chatgpt_msg = (
        f"ボリンジャー <b>{r['bb_z']:+.2f}σ</b>・5日線乖離 <b>{r['ma5_dev']:+.2f}%</b>・20日線乖離 <b>{r['ma20_dev']:+.2f}%</b>。"
        f"機関の執行基準であるVWAP（<b>{vwap_ref}</b>）を軸に、トレンド勝率 <b>{r['trend_win_rate']}%</b> の優位性を活かした分割エントリーを推奨します。"
    )
    gemini_msg = (
        f"「{r['genre']}」セクター（{r['theme']}）へのマクロ資金流入と先物感応度を計算。"
        f"夜間理論スタート値は <b>{r['pts_est_price']}（{r['pts_gap_pct']:+.2f}%）</b> と推計され、寄付きからの順張り資金が入りやすい地合いです。"
    )
    perp_msg = (
        f"VPIN <b>{r['vpin']:+.2f}</b>・板弾性 <b>{r['amihud_ratio']}倍</b>・Kyleλ <b>{r['kyle_lambda']}</b> をファクトチェック。"
        f"引け位置 <b>{r['close_pos_pct']}%</b>（上ヒゲ{r['upper_shadow_pct']}% / 下ヒゲ{r['lower_shadow_pct']}%）から、大引けにかけて実需の板吸収が確認されています。"
    )
    gensp_msg = (
        f"①朝イチで打診 <b>{half_lot:,}株</b> → ②VWAP（<b>{vwap_ref}</b>）での下ヒゲ支持または20日高値（<b>{r['squeeze_trigger_price']}</b>）突破で残り <b>{rem_lot:,}株</b> を追撃し、<b>{r['tp_price']}</b> で利確する2段階戦術がベストです。"
    )
    nblm_msg = (
        f"過去データで「{r['signal']}」が出現した <b>{r['count']}</b> を照合。翌朝GU勝率 <b>{r['prob']}%</b>・損益比 <b>{r['payoff']}倍</b>・過去最大GU <b>+{r['max_win_gap']}%</b> と高い統計的エッジ（期待値 <b>{r['edge']:+.2f}%</b>）を記録しています。"
    )

    return {
        "final_score": final_s,
        "agents": [
            ("🟠 Claude【数理勝率・ローソク足監査】", claude_s, claude_msg),
            ("🔴 Grok【5ch板・出来高推移・踏み上げ解析】", grok_s, grok_msg),
            ("🟢 ChatGPT【ボリンジャー・移動平均・VWAP戦略】", chatgpt_s, chatgpt_msg),
            ("🔵 Gemini【セクターテーマ・夜間PTS気配推計】", gemini_s, gemini_msg),
            ("🌐 Perplexity【VPIN・Kyleλ・板ミクロ構造検証】", perp_s, perp_msg),
            ("✨ Genspark【2段階分割エントリー実戦戦術】", gensp_s, gensp_msg),
            ("📓 NotebookLM【過去シグナル勝率・アノマリー照合】", nblm_s, nblm_msg),
        ],
        "verdict_html": (
            f'<div class="consensus-section"><b>① 🎯 勝率＆10段階判定：</b><b>{r["tier_label"]}</b> ｜ 総合勝率 <b>{r["total_win_rate"]}%</b>（翌朝GU勝率 <b>{r["prob"]}%</b> / 寄り後陽線勝率 <b>{r["intraday_win_rate"]}%</b>）。</div>'
            f'<div class="consensus-section"><b>② ⚡ 2段階エントリー：</b>推奨総数 <b>{r["lot_info"]["shares"]:,}株</b> のうち寄付きで <b>{half_lot:,}株</b>、VWAP（<b>{vwap_ref}</b>）反発または <b>{r["squeeze_trigger_price"]}</b> 突破で残り <b>{rem_lot:,}株</b> を投入。</div>'
            f'<div class="consensus-section"><b>③ 🎯 利確＆絶対損切り：</b>利確目標 <b>{r["tp_price"]}（+{r["tp_pct"]}%）</b> ／ 逆指値 <b>{r["sl_price"]}（最大損失 {r["lot_info"]["risk_amount"]:,.0f}円）</b>。</div>'
        )
    }

@st.cache_data(ttl=300)
def fetch_realtime_deep_research(full_code: str) -> dict:
    """質問された瞬間にyfinanceからファンダメンタル・最新ニュース・直近5日間の日別足データをライブ取得"""
    data = {"pe": None, "pbr": None, "roe": None, "mcap": None, "div": None, "target_mean": None, "w52_high": None, "w52_low": None, "short_ratio": None, "news": [], "recent_days": []}
    try:
        tk = yf.Ticker(full_code)
        info = tk.info or {}
        data["pe"] = info.get("trailingPE") or info.get("forwardPE")
        data["pbr"] = info.get("priceToBook")
        data["roe"] = info.get("returnOnEquity")
        data["mcap"] = info.get("marketCap")
        data["div"] = info.get("dividendYield")
        data["target_mean"] = info.get("targetMeanPrice")
        data["w52_high"] = info.get("fiftyTwoWeekHigh")
        data["w52_low"] = info.get("fiftyTwoWeekLow")
        data["short_ratio"] = info.get("shortRatio")

        raw_news = tk.news or []
        for n in raw_news[:3]:
            title = n.get("title") or (n.get("content", {}) or {}).get("title", "")
            if title:
                data["news"].append(title)

        df_hist = tk.history(period="10d")
        if df_hist is not None and not df_hist.empty:
            for dt_idx, row in df_hist.tail(5).iterrows():
                d_str = dt_idx.strftime("%m/%d")
                c_v, o_v, h_v, l_v, v_v = float(row["Close"]), float(row["Open"]), float(row["High"]), float(row["Low"]), int(row["Volume"])
                chg = round((c_v - o_v) / max(o_v, 1e-4) * 100, 2)
                data["recent_days"].append(f"{d_str}: 終値{c_v:,.0f} (日中{chg:+.2f}%, 高値{h_v:,.0f}/安値{l_v:,.0f}, 出来高{v_v:,})")
    except Exception:
        pass
    return data

def generate_7ai_qa_response_html(question, r, debate, lot_info, m5=None) -> str:
    """質問文の意図を細かく解析し、ライブ調査データ＋数理クオンツを組み合わせてオーダーメイド回答を生成"""
    q_clean = unicodedata.normalize('NFKC', str(question)).strip()
    q_low = q_clean.lower()
    m5_vwap = m5["vwap5_price"] if m5 else r["vwap_price"]
    half_s = max(1, lot_info['shares'] // 2)
    rem_s = max(0, lot_info['shares'] - half_s)

    # リアルタイム深層データを取得
    deep = fetch_realtime_deep_research(r["full_code"])
    is_jp = ".T" in r["full_code"]
    fmt_v = lambda v: (f"{v:,.0f}円" if is_jp else f"${v:,.2f}") if v is not None else "データなし"

    pe_str = f"{deep['pe']:.1f}倍" if isinstance(deep['pe'], (int, float)) else "算出外"
    pbr_str = f"{deep['pbr']:.2f}倍" if isinstance(deep['pbr'], (int, float)) else "算出外"
    roe_str = f"{deep['roe']*100:.1f}%" if isinstance(deep['roe'], (int, float)) else "算出外"
    mcap_str = (f"{deep['mcap']/1e8:,.0f}億円" if is_jp else f"${deep['mcap']/1e9:,.1f}B") if isinstance(deep['mcap'], (int, float)) else "算出外"
    target_str = fmt_v(deep['target_mean'])
    w52_str = f"高値 {fmt_v(deep['w52_high'])} ／ 安値 {fmt_v(deep['w52_low'])}"
    news_html = "".join([f"<li>📰 {t}</li>" for t in deep["news"]]) if deep["news"] else "<li>直近の特出しヘッドラインなし（板需給・テクニカル主導相場）</li>"
    days_html = " ｜ ".join(deep["recent_days"]) if deep["recent_days"] else "取得中"

    # 質問内容に応じた専用深掘りセクションの作成
    if any(k in q_low for k in ["決算", "業績", "per", "pbr", "割安", "割高", "ファンダ", "時価総額", "配当", "目標株価", "理論株価"]):
        focus_title = "📊 リアルタイム・ファンダメンタル＆バリュエーション深層調査"
        focus_body = (
            f"<div>・<b>バリュエーション指標</b>：時価総額 <b>{mcap_str}</b> ／ PER <b>{pe_str}</b> ／ PBR <b>{pbr_str}</b> ／ ROE <b>{roe_str}</b></div>"
            f"<div>・<b>アナリスト平均目標株価</b>：<b>{target_str}</b>（現在値 <b>{r['price']}</b> からの上値余地を評価）</div>"
            f"<div>・<b>52週レンジ位置</b>：{w52_str}</div>"
            f"<div>・<b>AI評議会の結論</b>：テーマ「{r['theme']}」の成長期待に加え、短期クオンツではカルマンフィルタ推計乖離が <b>{r['kalman_bull_pct']:+.2f}%</b> のため、ファンダメンタルズの下支えを背景に <b>{r['tp_price']}</b> を狙える水準です。</div>"
        )
    elif any(k in q_low for k in ["ニュース", "材料", "なぜ", "理由", "原因", "テーマ", "背景", "何があった"]):
        focus_title = "📰 値動きの背景・材料ニュース＆板ミクロ構造の深層分析"
        focus_body = (
            f"<div>・<b>セクター＆中核テーマ</b>：【{r['genre']}】<b>{r['theme']}</b></div>"
            f"<div>・<b>リアルタイム取得ヘッドライン</b>：<ul style='margin:2px 0 4px 18px;padding:0;'>{news_html}</ul></div>"
            f"<div>・<b>なぜこの波形なのか（需給の真相）</b>：{r['delicate_narrative']}</div>"
        )
    elif any(k in q_low for k in ["いつ", "タイミング", "何時", "エントリー", "買", "いくら", "指値", "成行", "ロット", "株数"]):
        focus_title = "⚡ 具体的な買いタイミング・指値価格・最適ロット配分"
        focus_body = (
            f"<div>・<b>推奨エントリー価格帯</b>：夜間理論気配 <b>{r['pts_est_price']}</b> 前後、または5分足VWAP（<b>{m5_vwap}</b>）付近での指値・押し目買い。</div>"
            f"<div>・<b>時間帯別アクション</b>：①<b>朝8:50〜8:55</b>に気配値が特買いライン（<b>{r['tokugai_line']}</b>）や20日高値（<b>{r['squeeze_trigger_price']}</b>）を意識しているか確認 → ②<b>9:00寄付き</b>でまず半分の <b>{half_s:,}株</b> を打診買い → ③<b>9:10〜9:30</b>にVWAP（<b>{m5_vwap}</b>）割れず反発を確認して残り <b>{rem_s:,}株</b> を追加投入。</div>"
        )
    elif any(k in q_low for k in ["売", "利確", "損切", "目標", "出口", "下が", "リスク", "ホールド", "握", "塩漬け"]):
        focus_title = "🛡️ 出口戦略（利確ターゲット・逆指値・ホールド継続判定）"
        focus_body = (
            f"<div>・<b>第一利確ターゲット</b>：<b>{r['tp_price']}（+{r['tp_pct']}%）</b> に到達した時点で半分を利益確定してください（過去最大GU実績 <b>+{r['max_win_gap']}%</b>）。</div>"
            f"<div>・<b>撤退・損切り逆指値</b>：<b>{r['sl_price']}（{r['sl_pct']}%）</b> を割ったら機械的に撤退します（最大損失額 <b>{lot_info['risk_amount']:,.0f}円</b> に限定）。</div>"
            f"<div>・<b>ホールド継続の判断基準</b>：場中に5分足VWAP（<b>{m5_vwap}</b>）および5日移動平均線（現在乖離 <b>{r['ma5_dev']:+.2f}%</b>）の上を維持している限り、機関の買い支え（VPIN <b>{r['vpin']:+.2f}</b>）が効いているため上値追いが可能です。</div>"
        )
    elif any(k in q_low for k in ["空売", "踏み上げ", "機関", "大口", "シコリ", "板", "需給", "5ch", "イナゴ", "特買", "pts"]):
        focus_title = "🏦 機関オーダーフロー・空売り踏み上げ・5chシコリ玉の精密検査"
        focus_body = (
            f"<div>・<b>機関アルゴ動向</b>：機関スコア <b>{r['inst_score']}点</b>（{r['inst_status']}） ／ VPIN <b>{r['vpin']:+.2f}</b> ／ Kyleλ <b>{r['kyle_lambda']}</b></div>"
            f"<div>・<b>空売り踏み上げ（ショートスクイーズ）</b>：20日高値 <b>{r['squeeze_trigger_price']}（あと{r['dist_to_high20']:+.2f}%）</b> を超えると売り方の強制買い戻しが発動。</div>"
            f"<div>・<b>5ch板シコリ玉＆夜間気配</b>：{r['board5ch_status']} ｜ 翌朝特買い確率 <b>{r['tokugai_prob']}%</b>（理論気配 <b>{r['pts_est_price']}</b>）</div>"
        )
    else:
        focus_title = f"🔬 「{q_clean}」に対する7大AIリアルタイム総合リサーチ回答"
        focus_body = (
            f"<div>・<b>現在の株価位置と需給の結論</b>：『{r['name']}（{r['code']}）』は現在 <b>{r['tier_label']}</b>（総合勝率 <b>{r['total_win_rate']}%</b>・合議スコア <b>{debate['final_score']}点</b>）と判定されています。</div>"
            f"<div>・<b>繊細チャート分析</b>：{r['delicate_narrative']}</div>"
            f"<div>・<b>ファンダ＆目標株価参考</b>：時価総額 <b>{mcap_str}</b> ／ PER <b>{pe_str}</b> ／ PBR <b>{pbr_str}</b> ／ アナリスト目標平均 <b>{target_str}</b></div>"
            f"<div>・<b>最も有利な立ち回り</b>：寄付き（目安 <b>{r['pts_est_price']}</b>）で <b>{half_s:,}株</b>、VWAP（<b>{m5_vwap}</b>）支持または <b>{r['squeeze_trigger_price']}</b> 突破で <b>{rem_s:,}株</b> 追加し、利確 <b>{r['tp_price']}</b>・損切り <b>{r['sl_price']}</b> で臨むのが期待値 <b>{r['edge']:+.2f}%</b>（損益比 <b>{r['payoff']}倍</b>）のベストプランです。</div>"
        )

    return (
        f"<div><b>🤖 【ご質問：「{q_clean}」へのリアルタイム深層リサーチ結果】</b></div>"
        f"<div style='margin-top:6px; background:#eff6ff; padding:8px 10px; border-radius:6px; border-left:3px solid #1d4ed8;'>"
        f"<b>{focus_title}</b>{focus_body}</div>"
        f"<div style='margin-top:6px;'><b>🎯 4大勝率データ</b>：総合勝率 <b>{r['total_win_rate']}%</b> ｜ 翌朝GU勝率 <b>{r['prob']}%</b>（{r['count']}） ｜ 寄り後陽線勝率 <b>{r['intraday_win_rate']}%</b> ｜ トレンド順張り勝率 <b>{r['trend_win_rate']}%</b></div>"
        f"<div style='margin-top:4px; font-size:12px; color:#475569;'><b>📅 直近5日間のリアル値動き推移</b>：{days_html}</div>"
    )

# ==========================================
# 💬 会議パネル＆質問コーナー
# ==========================================
def cb_toggle_debate(unique_key):
    st.session_state["active_debates"][unique_key] = not st.session_state["active_debates"].get(unique_key, False)

def cb_toggle_watchlist(code, r_data):
    if code in st.session_state["watchlist"]:
        del st.session_state["watchlist"][code]
    else:
        st.session_state["watchlist"][code] = r_data

def cb_handle_qa_action(unique_key, q_text, r, debate, m5):
    if unique_key not in st.session_state["stock_chats"]:
        st.session_state["stock_chats"][unique_key] = []
    ans_html = generate_7ai_qa_response_html(q_text, r, debate, r["lot_info"], m5)
    st.session_state["stock_chats"][unique_key].append({"q": q_text, "a": ans_html})
    st.session_state["scroll_to_chat_key"] = unique_key

def cb_clear_chat(unique_key):
    st.session_state["stock_chats"][unique_key] = []

@fragment_decorator
def render_interactive_council_section(r, unique_key):
    is_open = st.session_state["active_debates"].get(unique_key, False)
    in_wl = r["code"] in st.session_state["watchlist"]

    c1, c2 = st.columns([2.2, 1.2])
    with c1:
        st.button("🔼 会議パネルを閉じる" if is_open else "🧠 7大AIで会議して詳細＆リアルタイム質問を開く", key=f"btn_{unique_key}", on_click=cb_toggle_debate, args=(unique_key,), use_container_width=True)
    with c2:
        st.button("✅ 監視登録済(解除)" if in_wl else "⭐ 監視リスト追加", key=f"wl_{unique_key}", on_click=cb_toggle_watchlist, args=(r["code"], r), use_container_width=True)

    if not st.session_state["active_debates"].get(unique_key, False):
        return

    m5 = fetch_5m_intraday_algo(r["full_code"], trigger_high20=r["raw_high20"])
    debate = run_7ai_council_algorithm(r, m5)

    if unique_key not in st.session_state["debate_Animated"]:
        with st.status(f"🧠 7大AIが「{r['name']}」のローソク足・板弾性・4大勝率を精密議論中...", expanded=True) as status:
            prog = st.progress(0)
            for pct, msg in [
                (35, "🟠 Claude & 🔴 Grok が4大勝率・上下ヒゲ比率・3日出来高推移を解析中..."),
                (70, "🟢 ChatGPT & 🔵 Gemini & 🌐 Perplexity がボリンジャー位置とVPIN・Kyleλを検証中..."),
                (100, "✨ Genspark & 📓 NotebookLM が2段階エントリー戦術を統合中...")
            ]:
                st.write(msg)
                prog.progress(pct)
                time.sleep(0.25)
            status.update(label=f"✅ 7大AI合議完了！（総合勝率 {r['total_win_rate']}% ／ {r['tier_label']}）", state="complete", expanded=False)
        st.session_state["debate_Animated"].add(unique_key)

    if m5 and show_5m_chart:
        st.caption(f"📅 直近5分足チャート ({m5['chart_date']}) ｜ 5分足VWAP: **{m5['vwap5_price']}** ({m5['vwap5_dev']:+.2f}%)")
        render_5m_candlestick_chart(m5)

    agents_html = "".join([
        f'<div class="ai-agent-card"><div style="font-weight:bold; color:#fbbf24;">{ag_name} — {ag_score}点</div><div>{ag_comm}</div></div>'
        for ag_name, ag_score, ag_comm in debate["agents"]
    ])
    st.markdown(
        f'<div class="ai-council-box">'
        f'<div style="display:flex; justify-content:space-between; margin-bottom:10px; flex-wrap:wrap; gap:6px;">'
        f'<span style="font-weight:bold; color:#fbbf24; font-size:13.5px;">🧠 7大AI最高評議会（銘柄別ミクロ構造・勝率検証）</span>'
        f'<span style="background:{r["tier_bg"]}; color:{r["tier_color"]}; padding:3px 10px; border-radius:12px; font-size:12px; font-weight:bold;">{r["tier_label"]}</span>'
        f'</div>{agents_html}'
        f'<div class="consensus-banner"><div style="font-weight:bold; color:#fde047;">🏛️ 7大AI最終コンセンサス</div>{debate["verdict_html"]}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    if unique_key not in st.session_state["stock_chats"]:
        st.session_state["stock_chats"][unique_key] = []

    st.markdown("##### 💬 7大AI評議会へのワンタップ＆リアルタイム自由質問コーナー")
    q_col1, q_col2 = st.columns(2)
    with q_col1:
        st.button("🏦 機関のステルス買い・空売り需給は？", key=f"q1_{unique_key}", on_click=cb_handle_qa_action, args=(unique_key, "機関投資家のステルス買いと空売り踏み上げ需給は？", r, debate, m5), use_container_width=True)
        st.button("📊 決算・PER/PBR・目標株価を調べて", key=f"q2_{unique_key}", on_click=cb_handle_qa_action, args=(unique_key, "PERやPBR、時価総額、アナリスト目標株価などファンダメンタルズを調べて", r, debate, m5), use_container_width=True)
    with q_col2:
        st.button("📰 最新ニュースと値動きの理由は？", key=f"q3_{unique_key}", on_click=cb_handle_qa_action, args=(unique_key, "最新ニュースヘッドラインと本日の値動きの理由・背景は？", r, debate, m5), use_container_width=True)
        st.button("💰 具体的な買い値・利確・損切りは？", key=f"q4_{unique_key}", on_click=cb_handle_qa_action, args=(unique_key, "いつどの価格で買って、いくらで利確・損切りすべき？", r, debate, m5), use_container_width=True)

    with st.form(f"free_q_form_{unique_key}", clear_on_submit=True):
        f_col1, f_col2 = st.columns([3.2, 1])
        with f_col1:
            user_q_txt = st.text_input("自由質問を入力", placeholder="自由に質問（例：なぜ上がった？ / 割安？ / いつ売るべき？ / ニュースは？）", label_visibility="collapsed")
        with f_col2:
            sub_q = st.form_submit_button("🔍 丁寧に調査", use_container_width=True)
        if sub_q and user_q_txt.strip():
            with st.spinner(f"🔍 「{r['name']}」のリアルタイム指標・ニュース・過去波形を丁寧に調査中..."):
                cb_handle_qa_action(unique_key, user_q_txt.strip(), r, debate, m5)

    anchor_id = f"qa_ans_anchor_{unique_key}"
    st.markdown(f'<div id="{anchor_id}"></div>', unsafe_allow_html=True)

    chat_history = st.session_state["stock_chats"].get(unique_key, [])
    if chat_history:
        latest_item = chat_history[-1]
        st.markdown(f'<div class="qa-answer-card"><div class="qa-q-header">🙋 質問 #{len(chat_history)}：{latest_item["q"]}</div>{latest_item["a"]}</div>', unsafe_allow_html=True)
        if st.session_state.get("scroll_to_chat_key") == unique_key:
            components.html(f'<script>setTimeout(function(){{const el=window.parent.document.getElementById("{anchor_id}");if(el)el.scrollIntoView({{behavior:"smooth",block:"center"}});}},100);</script>', height=0)
            st.session_state["scroll_to_chat_key"] = None

        if len(chat_history) > 1:
            with st.expander(f"📚 過去の質問履歴をすべて見る（全 {len(chat_history)} 件）", expanded=False):
                for idx_h in range(len(chat_history) - 2, -1, -1):
                    item = chat_history[idx_h]
                    st.markdown(f'<div class="qa-answer-card"><div class="qa-q-header">🙋 質問 #{idx_h + 1}：{item["q"]}</div>{item["a"]}</div>', unsafe_allow_html=True)
        st.button("🗑️ この銘柄の質問履歴をクリア", key=f"clr_{unique_key}", on_click=cb_clear_chat, args=(unique_key,), use_container_width=True)

# ==========================================
# 🃏 銘柄カード描画（4大勝率バー ＆ 繊細診断ボックス付き）
# ==========================================
def render_stock_card(r, is_custom=False, rank=None, key_prefix="card"):
    diff_color = "#dc2626" if r["diff"] > 0 else "#2563eb"
    diff_sign = "+" if r["diff"] > 0 else ""
    pts_sign = "+" if r["pts_gap_pct"] > 0 else ""
    rank_html = f'<span class="rank-badge">🏆 第{rank}位</span>' if rank else ""
    lot = r["lot_info"]
    logo_html = get_company_logo_html(r["full_code"], r["name"])

    tier_badge_html = (
        f'<div class="signal-10tier-badge" style="background: {r["tier_bg"]}; color: {r["tier_color"]} !important;">'
        f'<span>🎯 {r["tier_label"]}</span>'
        f'<span style="font-size:12px; opacity:0.92;">総合勝率 {r["total_win_rate"]}% ｜ Lv.{r["tier_num"]}/10</span></div>'
    )

    winrate_bar_html = (
        f'<div class="winrate-bar">'
        f'<div><div style="font-size:11px; color:#881337; font-weight:700;">🏆 総合勝率</div><div style="font-size:15px; font-weight:900; color:#e11d48;">{r["total_win_rate"]}%</div></div>'
        f'<div style="border-left:1px solid #fecdd3;"><div style="font-size:11px; color:#64748b;">🌅 翌朝GU勝率</div><div style="font-size:14px; font-weight:800; color:#dc2626;">{r["prob"]}% <span style="font-size:10.5px;">({r["count"]})</span></div></div>'
        f'<div style="border-left:1px solid #fecdd3;"><div style="font-size:11px; color:#64748b;">☀️ 寄り後陽線勝率</div><div style="font-size:14px; font-weight:800; color:#d97706;">{r["intraday_win_rate"]}%</div></div>'
        f'<div style="border-left:1px solid #fecdd3;"><div style="font-size:11px; color:#64748b;">📈 順張り勝率</div><div style="font-size:14px; font-weight:800; color:#15803d;">{r["trend_win_rate"]}%</div></div>'
        f'</div>'
    )

    html_card = (
        f'<div class="{"search-result-card" if is_custom else "rank-card"}">'
        f'{tier_badge_html}'
        f'<div style="margin-bottom:8px;">{rank_html}<span class="score-badge">🤖 AI: {r["ai_score"]}点</span>'
        f'<span class="inst-badge">🏦 機関: {r["inst_score"]}点</span>'
        f'<span class="board5ch-badge">🔥 5ch需給: {r["board5ch_score"]}点</span>'
        f'<span class="tokugai-badge">🚨 特買い: {r["tokugai_prob"]}%</span></div>'
        f'<div style="display:flex; justify-content:space-between; align-items:center; margin-top:6px;">'
        f'<div style="display:flex; align-items:center; gap:10px;">{logo_html}'
        f'<div><span style="font-size:17.5px; font-weight:800; color:#0f172a;">{r["name"]}</span> '
        f'<span style="font-size:13px; color:#64748b; font-weight:600;">({r["code"]} / {r["genre"]})</span><br>'
        f'<span style="font-size:15px; color:#334155;">終値: <b>{r["price"]}</b> (<span style="color:{diff_color}; font-weight:800;">{diff_sign}{r["diff"]}%</span>)</span></div></div>'
        f'<div style="text-align:right;"><span style="font-size:11.5px; color:#64748b; font-weight:700;">🎯 総合勝率</span><br>'
        f'<span class="prob-badge">{r["total_win_rate"]}%</span>'
        f'<div style="font-size:11.5px; color:#64748b;">(損益比 {r["payoff"]}倍 / 期待値 {r["edge"]:+.2f}%)</div></div></div>'
        f'{winrate_bar_html}'
        f'<div class="delicate-box">{r["delicate_narrative"]}</div>'
        f'<div class="inst-box"><b>{r["inst_status"]}</b> ｜ 20日VWAP基準: <b>{r["vwap_price"]}</b></div>'
        f'<div class="board5ch-box"><b>📢 {r["board5ch_status"]}</b> ｜ シグナル: <b>{r["signal"]}</b></div>'
        f'<div class="pts-tokugai-box"><b>🌙 {r["tokugai_status"]}</b> ｜ 夜間理論気配: <b>{r["pts_est_price"]}</b> ({pts_sign}{r["pts_gap_pct"]}%) ｜ 特買い線: <b>{r["tokugai_line"]}</b></div>'
        f'<div class="squeeze-box"><b>{r["squeeze_type"]}</b> ｜ 踏み上げ突破ライン(20日高値): <b>{r["squeeze_trigger_price"]}</b> ({r["dist_to_high20"]:+.2f}%)</div>'
        f'<div class="metrics-row">'
        f'<span>🏦 <b>VPIN:</b> {r["vpin"]:+.2f}</span><span>🧬 <b>Hurst:</b> {r["hurst"]}</span>'
        f'<span>📐 <b>BB位置:</b> {r["bb_z"]:+.2f}σ</span><span>📊 <b>RSI:</b> {r["rsi"]}</span>'
        f'<span>📈 <b>MACD:</b> {r["macd_state"]}</span><span>🔊 <b>出来高:</b> {r["vol_ratio"]}倍</span></div>'
        f'<div class="trade-plan-box">'
        f'<div><div style="font-size:11px; color:#64748b;">🌅 夜間理論寄付き</div><div style="font-size:13.5px; font-weight:800;">{r["pts_est_price"]}</div></div>'
        f'<div style="border-left:1px solid #cbd5e1; border-right:1px solid #cbd5e1;"><div style="font-size:11px; color:#15803d; font-weight:bold;">🎯 利確目標</div><div style="font-size:13.5px; font-weight:800; color:#15803d;">{r["tp_price"]} (+{r["tp_pct"]}%)</div></div>'
        f'<div><div style="font-size:11px; color:#b91c1c; font-weight:bold;">🛡️ 損切り逆指値</div><div style="font-size:13.5px; font-weight:800; color:#b91c1c;">{r["sl_price"]} ({r["sl_pct"]}%)</div></div></div>'
        f'<div class="sizing-box">📦 <b>推奨ロット: {lot["shares"]:,}株</b> (投資額: <b>{lot["position_value"]:,.0f}円</b> / 最大損失リスク: <b>{lot["risk_amount"]:,.0f}円</b>)</div></div>'
    )
    st.markdown(html_card, unsafe_allow_html=True)
    render_interactive_council_section(r, f"{key_prefix}_{r['code']}")

# ==========================================
# 🚀 メイン画面ヘッダー＆ランキング描画
# ==========================================
macro_info = fetch_macro_market()
macro_pills_html = "".join([
    f'<div style="background:rgba(255,255,255,0.08); padding:4px 10px; border-radius:8px; font-size:12px; display:inline-flex; align-items:center; gap:5px; border:1px solid rgba(255,255,255,0.1);">'
    f'<span style="color:#cbd5e1;">{m["label"]}</span>'
    f'<span style="color:{"#f87171" if m["diff"]>=0 else "#60a5fa"}; font-weight:700;">{"+" if m["diff"]>=0 else ""}{m["diff"]}%</span></div>'
    for m in macro_info.values()
])

st.markdown(f"""
<div style="background: linear-gradient(135deg, #090d16 0%, #1e293b 100%); color: #f8fafc; padding: 18px 20px; border-radius: 16px; margin-bottom: 12px;">
    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
        <div>
            <div style="font-size:11.5px; color:#fbbf24; font-weight:700;">AUTO-EVOLVING QUANT (4-WINRATES × MICROSTRUCTURE) & 7-AI TERMINAL</div>
            <h1 style="margin:2px 0 0 0; font-size:21px; color:#ffffff; font-weight:800;">📈 翌朝株価 クオンツ＆7大AI解析 Pro</h1>
        </div>
        <span style="background:rgba(251,191,36,0.15); color:#fde047; border:1px solid rgba(251,191,36,0.4); padding:4px 10px; border-radius:999px; font-size:12px; font-weight:700;">{curr_page_badge}</span>
    </div>
    <div style="display:flex; flex-wrap:wrap; gap:6px; margin-top:12px;">{macro_pills_html}</div>
</div>
""", unsafe_allow_html=True)

st.markdown('<div id="search_box_anchor"></div>', unsafe_allow_html=True)
c1, c2 = st.columns([3.2, 1])
with c1:
    custom_input = st.text_input("🔍 任意の銘柄コードを診断（国内4桁 / 米国ティッカー）", placeholder="例: 6920, 5803, 3350, NVDA, IONQ", label_visibility="collapsed")
with c2:
    search_clicked = st.button("🔍 銘柄診断", use_container_width=True)

if search_clicked and custom_input:
    st.session_state["custom_search_code"] = normalize_ticker(custom_input)
    navigate_to("SEARCH_RESULT")

if st.session_state.get("custom_search_code"):
    norm_code = st.session_state["custom_search_code"]
    with st.spinner(f"「{norm_code}」の4大勝率＆ミクロ需給を精密解析中..."):
        custom_res = fetch_single_stock(norm_code, macro_info, inst_boost_mode, board5ch_boost, squeeze_boost_mode, tokugai_boost_mode, auto_evolve_algo)
    if custom_res:
        render_stock_card(custom_res, is_custom=True, key_prefix="custom")
        if st.button("✖️ 個別診断結果を閉じてランキング一覧に戻る", use_container_width=True):
            st.session_state["custom_search_code"] = ""
            st.session_state["navigation_page"] = "TOP"
            st.rerun()
    else:
        st.error(f"銘柄「{norm_code}」のデータが見つかりませんでした。")

with st.spinner("🏦 国内外の母集団を一括スキャン＆4大勝率・繊細チャート解析中..."):
    genre_results, all_results = fetch_all_pool_batch(macro_info, inst_boost_mode, board5ch_boost, squeeze_boost_mode, tokugai_boost_mode, auto_evolve_algo)

def apply_survival_of_the_fittest(stock_list, cut_pct):
    if not stock_list: return [], []
    sorted_all = sorted(stock_list, key=lambda x: (x["tier_num"], x["total_win_rate"], x["survival_power"], x["inst_score"]), reverse=True)
    keep_count = max(3, int(round(len(sorted_all) * (cut_pct / 100.0))))
    return sorted_all[:keep_count], sorted_all[keep_count:]

if st.session_state.get("navigation_page", "TOP") == "WATCHLIST":
    st.subheader("📋 監視ウォッチリスト (マイ銘柄一覧)")
    if st.button("⬅️ ランキング一覧画面へ戻る", use_container_width=True):
        st.session_state["navigation_page"] = "TOP"
        st.rerun()
    wl = st.session_state["watchlist"]
    if wl:
        for w_code, w_item in list(wl.items()):
            render_stock_card(w_item, is_custom=False, key_prefix=f"wl_page_{w_code}")
    else:
        st.info("⭐ 監視リストに登録されている銘柄はありません。")
else:
    base_tabs = ["🏆 総合サバイバルTOP5", "🏦 機関VPIN・最新クオンツ", "🔥 5ch板・初動イナゴ", "🚨 特買い・夜間PTS", "💥 空売り踏み上げ", "📋 監視＆注文シート"]
    tabs = st.tabs(base_tabs + list(STOCK_POOL.keys()))

    with tabs[0]:
        survivors_all, elim_all = apply_survival_of_the_fittest(all_results, survival_cut_pct)
        st.caption(f"🦁 全母集団 {len(all_results)}銘柄から下位 {len(elim_all)}銘柄を足切り！総合勝率・10段階評価ともに最強のTOP5です。")
        for idx, r in enumerate(survivors_all[:5], start=1):
            render_stock_card(r, rank=idx, key_prefix="top5")

    with tabs[1]:
        inst_list = sorted(all_results, key=lambda x: (x["inst_score"], x["total_win_rate"], x["vpin"]), reverse=True)[:10]
        for idx, r in enumerate(inst_list, start=1):
            render_stock_card(r, rank=idx, key_prefix="inst_top")

    with tabs[2]:
        b5_list = sorted(all_results, key=lambda x: (x["board5ch_score"], x["total_win_rate"]), reverse=True)[:10]
        for idx, r in enumerate(b5_list, start=1):
            render_stock_card(r, rank=idx, key_prefix="b5_top")

    with tabs[3]:
        tk_list = sorted(all_results, key=lambda x: (x["tokugai_prob"], x["pts_gap_pct"]), reverse=True)[:10]
        for idx, r in enumerate(tk_list, start=1):
            render_stock_card(r, rank=idx, key_prefix="tk_top")

    with tabs[4]:
        sq_list = sorted(all_results, key=lambda x: (x["squeeze_score"], x["total_win_rate"]), reverse=True)[:10]
        for idx, r in enumerate(sq_list, start=1):
            render_stock_card(r, rank=idx, key_prefix="sq_top")

    with tabs[5]:
        wl = st.session_state["watchlist"]
        st.markdown(f"#### 📋 監視ウォッチリスト ({len(wl)}銘柄)")
        if st.button("⚡ 総合TOP3をワンタップ一括登録", use_container_width=True):
            for item in survivors_all[:3]:
                st.session_state["watchlist"][item["code"]] = item
            st.rerun()
        if wl:
            df_wl = pd.DataFrame([{
                "コード": c, "銘柄名": x["name"], "総合勝率": f"{x['total_win_rate']}%", "翌朝GU勝率": f"{x['prob']}%",
                "10段階判定": x["tier_label"], "夜間理論気配": x["pts_est_price"], "推奨株数": f"{x['lot_info']['shares']:,}株",
                "利確": x["tp_price"], "損切": x["sl_price"]
            } for c, x in wl.items()])
            st.dataframe(df_wl, use_container_width=True, hide_index=True)

    for tab, genre in zip(tabs[6:], STOCK_POOL.keys()):
        with tab:
            g_surv, g_elim = apply_survival_of_the_fittest(genre_results.get(genre, []), survival_cut_pct)
            st.caption(f"🦁 **{genre}選抜**: 上位 **{len(g_surv)}銘柄が生存**（下位 {len(g_elim)}銘柄が脱落）")
            for idx, r in enumerate(g_surv, start=1):
                render_stock_card(r, rank=idx, key_prefix=f"genre_{genre}")
