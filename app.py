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

# スマホ画面向けにページ設定
st.set_page_config(page_title="翌朝株価 クオンツ＆7大AI解析 Pro (会員限定版)", page_icon="📈", layout="centered")

# Fragmentデコレータ（部分更新用）の取得
fragment_decorator = getattr(st, "fragment", getattr(st, "experimental_fragment", lambda f: f))

# ==========================================
# 🔒 会員データベース一括管理 ＆ ワンクリック承認・自動メール送信システム
# ==========================================
ADMIN_EMAIL = "nthbh399@ybb.ne.jp"  # 管理者メールアドレス
SECRET_MASTER_KEY = "my_super_secret_quant_key_2026"
MEMBERS_DB_FILE = "members_db.json"

def generate_member_passcode(email: str) -> str:
    clean_email = email.strip().lower()
    h = hmac.new(SECRET_MASTER_KEY.encode(), clean_email.encode(), hashlib.sha256).hexdigest()
    return h[:8].upper()

def generate_admin_action_token(email: str, action: str) -> str:
    msg = f"{email.strip().lower()}:{action}:{SECRET_MASTER_KEY}"
    return hashlib.sha256(msg.encode()).hexdigest()[:16]

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
        db[admin_clean] = {
            "name": "管理者 (Owner)",
            "email": admin_clean,
            "status": "approved",
            "passcode": generate_member_passcode(admin_clean),
            "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "approved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "note": "システム最高管理者"
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
    """SMTP設定があれば自動メール送信、なければFalseを返す"""
    smtp_user = st.session_state.get("smtp_user", "").strip()
    smtp_pass = st.session_state.get("smtp_pass", "").strip()
    smtp_server = st.session_state.get("smtp_server", "smtp.mail.yahoo.co.jp").strip()
    smtp_port = int(st.session_state.get("smtp_port", 465))

    if not smtp_user or not smtp_pass:
        return False, "SMTP未設定（手動メールリンクを使用可能）"
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
        expected_token = generate_admin_action_token(target_email, action)
        if hmac.compare_digest(token, expected_token):
            db = load_members_db()
            code = generate_member_passcode(target_email)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

            if action == "approve":
                db[target_email] = {
                    "name": db.get(target_email, {}).get("name", target_name),
                    "email": target_email,
                    "status": "approved",
                    "passcode": code,
                    "applied_at": db.get(target_email, {}).get("applied_at", now_str),
                    "approved_at": now_str,
                    "note": "メールリンクからワンクリック承認"
                }
                save_members_db(db)
                subj = "【承認完了】翌朝株価クオンツ＆7大AI解析 Pro 専用アクセスコードのお知らせ"
                body = (
                    f"{db[target_email]['name']} 様\n\n"
                    f"「翌朝株価 クオンツ＆7大AI解析 Pro」のご利用申請が承認されました。\n"
                    f"以下の登録メールアドレスと専用8桁アクセスコードでログインしてください。\n\n"
                    f"■ 登録メールアドレス: {target_email}\n"
                    f"■ 専用アクセスコード: {code}\n\n"
                    f"今後ともよろしくお願いいたします。"
                )
                sent_ok, _ = send_auto_email(target_email, subj, body)
                st.success(f"✅ 【ワンクリック承認完了】 {target_email} を会員リストに追加しました！（専用コード: {code}）")
                if sent_ok:
                    st.info(f"📨 {target_email} 宛てに専用パスコード通知メールを自動送信しました！")
                else:
                    mailto_approve = f"mailto:{target_email}?subject={urllib.parse.quote(subj)}&body={urllib.parse.quote(body)}"
                    st.markdown(f'👉 <a href="{mailto_approve}" style="background:#16a34a;color:#fff;padding:8px 14px;border-radius:6px;text-decoration:none;font-weight:bold;">📨 申請者（{target_email}）へパスコード通知メールをワンタップ送信する</a>', unsafe_allow_html=True)
            else:
                db[target_email] = {
                    "name": db.get(target_email, {}).get("name", target_name),
                    "email": target_email,
                    "status": "rejected",
                    "passcode": code,
                    "applied_at": db.get(target_email, {}).get("applied_at", now_str),
                    "approved_at": now_str,
                    "note": "メールリンクから却下"
                }
                save_members_db(db)
                st.warning(f"❌ 【ワンクリック却下完了】 {target_email} の申請を却下しました。")
            try:
                del st.query_params["admin_action"]
                del st.query_params["email"]
                del st.query_params["token"]
            except Exception:
                pass

process_url_admin_action()

def render_admin_sidebar_management():
    """管理者専用のサイドバー管理コンソール"""
    db = load_members_db()
    pending_list = [v for v in db.values() if v.get("status") == "pending"]

    st.sidebar.markdown("---")
    st.sidebar.subheader(f"👑 管理者一括管理メニュー (承認待:{len(pending_list)}件)")

    admin_action_mode = st.sidebar.radio("管理機能選択", ["⏳ 申請承認待ち一覧", "👥 全会員データベース管理"], key="admin_sidebar_mode")

    if admin_action_mode == "⏳ 申請承認待ち一覧":
        if pending_list:
            st.sidebar.warning(f"🔔 新規の会員登録申請が {len(pending_list)} 件届いています！")
            for p in pending_list:
                p_mail = p["email"]
                p_name = p.get("name", "未入力")
                p_code = generate_member_passcode(p_mail)
                st.sidebar.markdown(f"**📩 {p_name}** (`{p_mail}`)")
                c_ap, c_rj = st.sidebar.columns(2)
                with c_ap:
                    if st.button("✅ 承認", key=f"side_ap_{p_mail}", use_container_width=True):
                        db[p_mail]["status"] = "approved"
                        db[p_mail]["passcode"] = p_code
                        db[p_mail]["approved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                        save_members_db(db)
                        subj = "【承認完了】翌朝株価クオンツ＆7大AI解析Pro 専用アクセスコード"
                        body = f"{p_name} 様\n\n会員登録が承認されました。\n\n■登録メール: {p_mail}\n■専用アクセスコード: {p_code}\n"
                        ok, _ = send_auto_email(p_mail, subj, body)
                        st.session_state["last_approved_mailto"] = {
                            "email": p_mail, "code": p_code, "auto_sent": ok,
                            "url": f"mailto:{p_mail}?subject={urllib.parse.quote(subj)}&body={urllib.parse.quote(body)}"
                        }
                        st.rerun()
                with c_rj:
                    if st.button("❌ 却下", key=f"side_rj_{p_mail}", use_container_width=True):
                        db[p_mail]["status"] = "rejected"
                        save_members_db(db)
                        st.rerun()
        else:
            st.sidebar.info("現在、承認待ちの申請はありません。")

        if "last_approved_mailto" in st.session_state:
            la = st.session_state["last_approved_mailto"]
            if la["auto_sent"]:
                st.sidebar.success(f"📨 {la['email']} へパスコードを自動送信しました！")
            else:
                st.sidebar.success(f"✅ {la['email']} を承認しました！（コード: `{la['code']}`）")
                st.sidebar.markdown(f'<a href="{la["url"]}" style="display:block;text-align:center;background:#16a34a;color:#fff;padding:6px;border-radius:6px;text-decoration:none;font-weight:bold;font-size:12px;">✉️ 相手にメールを送る</a>', unsafe_allow_html=True)

    else:
        st.sidebar.markdown("##### 👥 全会員リスト＆個別操作")
        rows = [{"状態": info.get("status"), "名前": info.get("name"), "メール": em, "コード": info.get("passcode")} for em, info in db.items()]
        df_members = pd.DataFrame(rows)
        st.sidebar.dataframe(df_members, use_container_width=True, hide_index=True)

        target_em = st.sidebar.selectbox("操作する会員を選択", options=list(db.keys()), format_func=lambda x: f"{db[x].get('name','')} ({x})")
        if target_em:
            t_code = generate_member_passcode(target_em)
            b1, b2 = st.sidebar.columns(2)
            with b1:
                if st.button("✅ 有効化", key="adm_act_btn", use_container_width=True):
                    db[target_em]["status"] = "approved"
                    db[target_em]["passcode"] = t_code
                    save_members_db(db)
                    st.rerun()
            with b2:
                if st.button("⏸️ 停止", key="adm_stop_btn", use_container_width=True):
                    if target_em != ADMIN_EMAIL.strip().lower():
                        db[target_em]["status"] = "rejected"
                        save_members_db(db)
                        st.rerun()

        csv_mem = df_members.to_csv(index=False).encode("utf-8-sig")
        st.sidebar.download_button("📥 会員CSV出力", data=csv_mem, file_name="members_backup.csv", mime="text/csv", use_container_width=True)

    with st.sidebar.expander("⚙️ 自動メール送信(SMTP)＆URL設定"):
        st.text_input("アプリ公開URL", value=st.session_state.get("app_base_url", "http://localhost:8501"), key="app_base_url")
        st.text_input("送信元メールアドレス", value=st.session_state.get("smtp_user", ADMIN_EMAIL), key="smtp_user")
        st.text_input("SMTPアプリパスワード", type="password", key="smtp_pass")
        st.text_input("SMTPサーバー", value=st.session_state.get("smtp_server", "smtp.mail.yahoo.co.jp"), key="smtp_server")
        st.number_input("SMTPポート", value=int(st.session_state.get("smtp_port", 465)), key="smtp_port")

def check_member_authentication():
    db = load_members_db()
    if "authenticated_user" not in st.session_state:
        st.session_state["authenticated_user"] = None

    # URLクエリパラメータによるセッション維持（リロードや戻るでもログアウトしない対策）
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
    <div style="background: linear-gradient(135deg, #090d16, #1e293b); color: #f8fafc; padding: 28px 24px; border-radius: 16px; text-align: center; margin-top: 10px; margin-bottom: 18px; box-shadow: 0 10px 25px rgba(0,0,0,0.25); border: 1px solid rgba(255,255,255,0.1);">
        <h2 style="margin:0; color:#fbbf24; font-size:21px; letter-spacing:0.5px;">🔒 会員限定 クオンツ＆7大AI解析 Pro</h2>
        <p style="font-size:13px; color:#cbd5e1; margin-top:8px; margin-bottom:0; line-height:1.6;">
            本システムは完全招待・承認制です。<br>承認されたメールアドレスと専用アクセスコードを入力してください。
        </p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("member_login_form"):
        input_email = st.text_input("📧 登録メールアドレス", placeholder="example@gmail.com")
        input_code = st.text_input("🔑 専用アクセスコード（8桁コード）", type="password")
        login_btn = st.form_submit_button("🔓 ログインして解析システムを開く", use_container_width=True)

        if login_btn:
            clean_mail = input_email.strip().lower()
            expected_code = generate_member_passcode(clean_mail)
            user_rec = db.get(clean_mail)
            is_approved = (user_rec and user_rec.get("status") == "approved") or (clean_mail == ADMIN_EMAIL.strip().lower())
            is_valid_code = hmac.compare_digest(input_code.strip().upper(), expected_code) or (
                clean_mail == ADMIN_EMAIL.strip().lower() and input_code.strip() == "ADMIN777"
            )
            if is_approved and is_valid_code:
                st.session_state["authenticated_user"] = clean_mail
                st.query_params["u"] = clean_mail
                st.query_params["t"] = generate_admin_action_token(clean_mail, "session_keep")
                st.rerun()
            elif user_rec and user_rec.get("status") == "pending":
                st.warning("⏳ 現在、管理者による承認審査中です。承認メールが届くまで今しばらくお待ちください。")
            elif not is_approved:
                st.error("⚠️ このメールアドレスはまだ会員登録されていません。下のフォームから利用申請を行ってください。")
            else:
                st.error("⚠️ 専用アクセスコードが正しくありません。")

    st.markdown("---")
    st.markdown("##### 📩 新規会員登録・利用許可の申請はこちら")
    with st.form("member_apply_form"):
        ap_name = st.text_input("👤 お名前（ニックネーム可）", placeholder="山田 太郎")
        ap_mail = st.text_input("📧 ご希望のメールアドレス", placeholder="your_email@example.com")
        ap_note = st.text_input("💬 ひとこと・紹介者など（任意）")
        ap_btn = st.form_submit_button("📨 管理者に利用申請を送信する", use_container_width=True)

        if ap_btn:
            c_mail = ap_mail.strip().lower()
            if not c_mail or "@" not in c_mail:
                st.error("⚠️ 正しいメールアドレスを入力してください。")
            else:
                now_s = datetime.now().strftime("%Y-%m-%d %H:%M")
                passcode = generate_member_passcode(c_mail)
                db[c_mail] = {
                    "name": ap_name.strip() or "未入力",
                    "email": c_mail,
                    "status": "pending",
                    "passcode": passcode,
                    "applied_at": now_s,
                    "approved_at": "-",
                    "note": ap_note.strip()
                }
                save_members_db(db)

                base_url = st.session_state.get("app_base_url", "http://localhost:8501").rstrip("/")
                tok_ap = generate_admin_action_token(c_mail, "approve")
                tok_rj = generate_admin_action_token(c_mail, "reject")
                approve_url = f"{base_url}/?admin_action=approve&email={urllib.parse.quote(c_mail)}&name={urllib.parse.quote(ap_name)}&token={tok_ap}"
                reject_url = f"{base_url}/?admin_action=reject&email={urllib.parse.quote(c_mail)}&token={tok_rj}"

                admin_subj = f"【会員申請】{ap_name}様 ({c_mail}) 承認/却下判定"
                admin_body = (
                    f"以下のユーザーから会員登録申請が届きました。\n\n"
                    f"・お名前: {ap_name}\n"
                    f"・メール: {c_mail}\n"
                    f"・備考: {ap_note}\n"
                    f"・発行予定パスコード: {passcode}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"▼ 【✅ 承認して会員に追加する（ワンクリック）】\n"
                    f"{approve_url}\n\n"
                    f"▼ 【❌ 却下する（ワンクリック）】\n"
                    f"{reject_url}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                )
                ok_admin, _ = send_auto_email(ADMIN_EMAIL, admin_subj, admin_body)
                st.success("✅ 申請を受け付けました！管理者の承認審査が完了すると専用パスコードが発行されます。")
                if not ok_admin:
                    mailto_admin = f"mailto:{ADMIN_EMAIL}?subject={urllib.parse.quote(admin_subj)}&body={urllib.parse.quote(admin_body)}"
                    st.markdown(f'<a href="{mailto_admin}" style="display:block;text-align:center;background:#2563eb;color:#fff;padding:12px;border-radius:8px;text-decoration:none;font-weight:bold;">📧 メールアプリを開いて管理者に申請内容を通知する</a>', unsafe_allow_html=True)
    st.stop()

check_member_authentication()

# ==========================================
# 📈 セッション初期化 ＆ ページ履歴管理
# ==========================================
for k, default_v in [
    ("active_debates", {}),
    ("debate_Animated", set()),
    ("stock_chats", {}),
    ("watchlist", {}),
    ("navigation_page", "TOP"),
    ("nav_history", ["TOP"]),
    ("custom_search_code", ""),
    ("scroll_to_chat_key", None),
    ("trigger_scroll_top", False)
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
    st.session_state["custom_search_code"] = ""
    st.session_state["trigger_scroll_top"] = True

# ==========================================
# 🏢 企業ロゴマーク自動取得システム
# ==========================================
COMPANY_DOMAINS = {
    "8035.T": "tel.co.jp", "6857.T": "advantest.com", "6920.T": "lasertec.co.jp", "6146.T": "disco.co.jp",
    "6526.T": "socionext.com", "7735.T": "screen.co.jp", "6315.T": "towa.co.jp", "6723.T": "renesas.com",
    "4063.T": "shinetsu.co.jp", "3436.T": "sumcosi.com", "6323.T": "rorze.com", "6871.T": "micronics.co.jp",
    "NVDA": "nvidia.com", "AMD": "amd.com", "MU": "micron.com", "TSM": "tsmc.com",
    "AVGO": "broadcom.com", "ARM": "arm.com", "SMCI": "supermicro.com",
    "9984.T": "group.softbank", "3778.T": "sakura.ad.jp", "7011.T": "mhi.com", "7012.T": "khi.co.jp",
    "7013.T": "ihi.co.jp", "3993.T": "pkshatech.com", "4180.T": "appier.com", "5032.T": "anycolor.co.jp",
    "4385.T": "about.mercari.com", "7974.T": "nintendo.co.jp", "8306.T": "mufg.jp",
    "MSFT": "microsoft.com", "PLTR": "palantir.com", "META": "meta.com", "GOOGL": "abc.xyz", "CRWD": "crowdstrike.com",
    "5803.T": "fujikura.co.jp", "5801.T": "furukawa.co.jp", "5802.T": "sei.co.jp", "6501.T": "hitachi.co.jp",
    "9509.T": "hepco.co.jp", "9508.T": "kyuden.co.jp", "6622.T": "daihen.co.jp", "1942.T": "kandenko.co.jp",
    "VST": "vistracorp.com", "CEG": "constellationenergy.com", "GEV": "gevernova.com",
    "5595.T": "i-qps.net", "186A.T": "astroscale.com", "9348.T": "ispace-inc.com", "9412.T": "skyperfectjsat.space",
    "9433.T": "kddi.com", "7203.T": "global.toyota", "TSLA": "tesla.com", "RKLB": "rocketlabusa.com",
    "ASTS": "ast-science.com", "COIN": "coinbase.com",
    "5253.T": "cover-corp.com", "9166.T": "genda.jp", "216A.T": "corp.timee.co.jp", "285A.T": "kioxia.com",
    "141A.T": "trial-holdings.inc", "5243.T": "note.jp", "247A.T": "ai-robotics.co.jp", "153A.T": "caulis.jp",
    "3350.T": "metaplanet.jp", "IONQ": "ionq.com", "RGTI": "rigetti.com", "SOUN": "soundhound.com",
    "RDDT": "redditinc.com", "ALAB": "asteralabs.com"
}

def get_company_logo_html(full_code: str, name: str) -> str:
    domain = COMPANY_DOMAINS.get(full_code, "")
    clean_name = name.replace(" (米)", "").replace(" (米IPO)", "").strip()
    initial = clean_name[0] if clean_name else "📈"
    fallback_url = f"https://ui-avatars.com/api/?name={urllib.parse.quote(initial)}&background=0f172a&color=fbbf24&bold=true&size=64"
    if domain:
        logo_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
    else:
        logo_url = fallback_url
    return (
        f'<img src="{logo_url}" onerror="this.onerror=null;this.src=\'{fallback_url}\';" '
        f'class="company-logo-img" alt="logo" />'
    )

# ==========================================
# 🎨 カスタムCSS ＆ 半透明フローティングナビバー（ログイン維持＆ページTOPスムーズスクロール）
# ==========================================
wl_count = len(st.session_state.get("watchlist", {}))
curr_page_badge = "監視リスト表示中" if st.session_state.get("navigation_page") == "WATCHLIST" else "ランキング解析"

# ページ最上部のアンカー配置
st.markdown('<div id="page_top_anchor"></div>', unsafe_allow_html=True)

st.markdown(f"""
<style>
/* 全体のタイポグラフィと余白 */
.block-container {{
    padding-top: 3.6rem !important;
    padding-bottom: 3rem !important;
    max-width: 780px !important;
}}
button[data-baseweb="tab"] {{
    font-size: 12.5px !important;
    font-weight: 700 !important;
    padding: 8px 13px !important;
    border-radius: 8px 8px 0 0 !important;
}}

/* 💎 スクロール追従・半透明グラスモーフィズム上部ナビバー（リロードなし・ログイン維持） */
.floating-glass-nav {{
    position: fixed;
    top: 10px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 999990;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px;
    background: rgba(15, 23, 42, 0.72);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 999px;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25);
    white-space: nowrap;
}}
.floating-glass-nav a {{
    color: #f8fafc !important;
    text-decoration: none !important;
    font-size: 11px;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 999px;
    transition: all 0.18s ease;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    cursor: pointer;
}}
.floating-glass-nav a:hover {{
    background: rgba(255, 255, 255, 0.18);
    color: #fbbf24 !important;
    transform: translateY(-1px);
}}
.floating-glass-nav .nav-divider {{
    width: 1px;
    height: 12px;
    background: rgba(255, 255, 255, 0.2);
}}
.floating-glass-nav .algo-pill {{
    background: rgba(16, 185, 129, 0.2);
    border: 1px solid rgba(16, 185, 129, 0.45);
    color: #6ee7b7 !important;
    font-size: 10.5px;
}}

/* 🏢 企業ロゴマーク */
.company-logo-img {{
    width: 34px;
    height: 34px;
    border-radius: 9px;
    object-fit: contain;
    background: #ffffff;
    padding: 3px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 2px 5px rgba(0,0,0,0.06);
    flex-shrink: 0;
}}

/* 🃏 プレミアム銘柄カードデザイン */
.stock-card, .rank-card, .search-result-card {{
    background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%) !important;
    color: #0f172a !important;
    border-radius: 16px;
    padding: 18px;
    margin-bottom: 12px;
    box-shadow: 0 6px 20px rgba(15, 23, 42, 0.07);
    border: 1px solid #e2e8f0;
    border-left: 6px solid #e11d48;
}}
.stock-card *, .rank-card *, .search-result-card * {{ color: #0f172a; }}
.search-result-card {{
    background: linear-gradient(180deg, #fffbeb 0%, #fef3c7 100%) !important;
    border-left-color: #d97706;
}}

/* バッジ類 */
.prob-badge {{ font-size: 24px; font-weight: 800; color: #dc2626 !important; letter-spacing: -0.5px; }}
.rank-badge {{ display: inline-block; background: linear-gradient(135deg, #f59e0b, #d97706); color: #ffffff !important; padding: 3px 10px; border-radius: 999px; font-size: 11.5px; font-weight: 700; margin-right: 5px; }}
.score-badge {{ display: inline-block; background: #0f172a; color: #f8fafc !important; padding: 3px 10px; border-radius: 999px; font-size: 11.5px; font-weight: 700; }}
.inst-badge {{ display: inline-block; background: linear-gradient(135deg, #1d4ed8, #2563eb); color: #ffffff !important; padding: 3px 9px; border-radius: 999px; font-size: 11px; font-weight: 700; margin-left: 4px; }}
.board5ch-badge {{ display: inline-block; background: linear-gradient(135deg, #059669, #10b981); color: #ffffff !important; padding: 3px 9px; border-radius: 999px; font-size: 11px; font-weight: 700; margin-left: 4px; }}
.tokugai-badge {{ display: inline-block; background: linear-gradient(135deg, #d97706, #f59e0b); color: #ffffff !important; padding: 3px 9px; border-radius: 999px; font-size: 11px; font-weight: 700; margin-left: 4px; }}
.survival-badge {{ display: inline-block; background: #f3e8ff; color: #6b21a8 !important; border: 1px solid #d8b4fe; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 700; margin-left: 4px; }}
.quant-evo-badge {{ display: inline-block; background: #ecfeff; color: #0e7490 !important; border: 1px solid #a5f3fc; padding: 2px 8px; border-radius: 6px; font-size: 10.5px; font-weight: 700; margin-left: 4px; }}

/* 10段階シグナルバー */
.signal-10tier-badge {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 7px 14px;
    border-radius: 10px;
    font-size: 13px;
    font-weight: 800;
    margin-bottom: 10px;
    box-shadow: 0 3px 10px rgba(0,0,0,0.12);
}}

/* 情報ボックス */
.inst-box {{ background: #eff6ff !important; border: 1px solid #bfdbfe; border-left: 4px solid #2563eb; border-radius: 9px; padding: 8px 12px; margin-top: 7px; font-size: 11.5px; color: #1e3a8a !important; }}
.inst-box * {{ color: #1e3a8a !important; }}
.squeeze-box {{ background: #fff1f2 !important; border: 1px solid #fecdd3; border-left: 4px solid #e11d48; border-radius: 9px; padding: 8px 12px; margin-top: 6px; font-size: 11.5px; color: #881337 !important; }}
.squeeze-box * {{ color: #881337 !important; }}
.pts-tokugai-box {{ background: #fffbeb !important; border: 1px solid #fde68a; border-left: 4px solid #d97706; border-radius: 9px; padding: 8px 12px; margin-top: 6px; font-size: 11.5px; color: #78350f !important; }}
.pts-tokugai-box * {{ color: #78350f !important; }}
.board5ch-box {{ background: #ecfdf5 !important; border: 1px solid #a7f3d0; border-left: 4px solid #059669; border-radius: 9px; padding: 8px 12px; margin-top: 6px; font-size: 11.5px; color: #064e3b !important; }}
.board5ch-box * {{ color: #064e3b !important; }}
.metrics-row {{ display: flex; flex-wrap: wrap; gap: 6px 11px; margin-top: 9px; font-size: 11px; color: #0f172a !important; background: #f1f5f9 !important; padding: 8px 12px; border-radius: 8px; border: 1px solid #e2e8f0; }}
.metrics-row * {{ color: #0f172a !important; }}
.trade-plan-box {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-top: 9px; background: #ffffff !important; padding: 9px 6px; border-radius: 10px; border: 1px solid #cbd5e1; text-align: center; color: #0f172a !important; }}
.sizing-box {{ background: linear-gradient(90deg, #f0fdf4, #dcfce7) !important; border: 1px solid #86efac; border-radius: 9px; padding: 9px 12px; margin-top: 8px; font-size: 11.5px; color: #166534 !important; }}
.sizing-box * {{ color: #166534 !important; }}

/* 7大AI評議会ダークパネル */
.ai-council-box {{ background: linear-gradient(135deg, #090d16, #1e293b); color: #f8fafc !important; border-radius: 14px; padding: 15px; margin-top: 8px; margin-bottom: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.22); border: 1px solid rgba(255,255,255,0.1); }}
.ai-council-box * {{ color: #f8fafc; }}
.ai-agent-card {{ background: rgba(255, 255, 255, 0.06); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 9px 12px; margin-bottom: 7px; font-size: 12px; line-height: 1.55; color: #f8fafc !important; }}
.consensus-banner {{ background: linear-gradient(135deg, #1e1b4b, #312e81); border: 1.5px solid #818cf8; border-radius: 12px; padding: 13px; margin-top: 10px; font-size: 12px; line-height: 1.65; color: #f8fafc !important; }}
.consensus-section {{ background: rgba(255, 255, 255, 0.07); border-left: 3px solid #fbbf24; border-radius: 6px; padding: 7px 10px; margin-top: 7px; color: #f8fafc !important; }}

/* 💬 見やすく目に優しい・少し小さめ文字（11.5px）の質問回答専用カード */
.qa-answer-card {{
    background: #f8fafc !important;
    border: 1px solid #cbd5e1;
    border-left: 4px solid #3b82f6;
    border-radius: 10px;
    padding: 12px 14px;
    margin-top: 8px;
    margin-bottom: 10px;
    font-size: 11.5px !important;
    line-height: 1.65 !important;
    color: #1e293b !important;
    box-shadow: 0 2px 8px rgba(15, 23, 42, 0.05);
}}
.qa-answer-card * {{
    color: #1e293b !important;
    font-size: 11.5px !important;
    line-height: 1.65 !important;
}}
.qa-answer-card .qa-q-header {{
    font-weight: 700;
    color: #0f172a !important;
    background: #e2e8f0;
    padding: 4px 10px;
    border-radius: 6px;
    margin-bottom: 8px;
    display: inline-block;
    font-size: 11px !important;
}}
.qa-answer-card b, .qa-answer-card strong {{
    color: #1d4ed8 !important;
    font-weight: 700;
}}
</style>

<!-- 🧭 上部追従・半透明フローティングナビバー（ログイン画面に戻らずページ最上部へスムーズスクロール） -->
<div class="floating-glass-nav">
    <a href="#page_top_anchor" title="ページの最上部へ戻る">⬆️ ページTOPへ</a>
    <div class="nav-divider"></div>
    <a href="#search_box_anchor" title="銘柄検索・タブ選択へ移動">🔍 検索・タブ</a>
    <div class="nav-divider"></div>
    <span class="algo-pill" title="Hurst指数・Kalmanフィルタ・Kyleラムダ自動適応中">🧬 最新Algo自動適応中</span>
</div>
""", unsafe_allow_html=True)

# ページトップへのプログラム的スクロール発火処理
if st.session_state.get("trigger_scroll_top"):
    components.html(
        """
        <script>
        setTimeout(function() {
            const topEl = window.parent.document.getElementById("page_top_anchor");
            if (topEl) {
                topEl.scrollIntoView({ behavior: "smooth", block: "start" });
            } else {
                window.parent.scrollTo({ top: 0, behavior: "smooth" });
            }
        }, 80);
        </script>
        """,
        height=0,
    )
    st.session_state["trigger_scroll_top"] = False

# --- サイドバー設定 ---
st.sidebar.header("🧭 ナビゲーション")
s_col1, s_col2 = st.sidebar.columns(2)
with s_col1:
    if st.button("⬆️ ページTOP", key="side_top_btn", use_container_width=True):
        st.session_state["navigation_page"] = "TOP"
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
auto_evolve_algo = st.sidebar.checkbox("🧬 最新クオンツ（Hurst指数・Kalman・Kyleλ）自動組込", value=True, help="相場レジームに応じて最新の数理クオンツアルゴリズムを自動で組み込み、重みを動的最適化します。")
survival_cut_pct = st.sidebar.slider("弱肉強食・各タブ選抜率 (%)", min_value=40, max_value=100, value=70, step=10)
inst_boost_mode = st.sidebar.checkbox("🏦 機関クオンツ（VPIN・ステルス吸収）優先", value=True)
board5ch_boost = st.sidebar.checkbox("🔥 5ch板・初動イナゴ＆シコリ玉なし優先", value=True)
squeeze_boost_mode = st.sidebar.checkbox("💥 空売り踏み上げ（20日高値突破）優先", value=True)
tokugai_boost_mode = st.sidebar.checkbox("🚨 翌朝『特買い』・夜間PTS連動を優先", value=True)
show_5m_chart = st.sidebar.checkbox("合議パネル内に5分足＆VWAPチャートを描画", value=True)

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

KNOWN_STOCKS = {}
for g, items in STOCK_POOL.items():
    for item in items:
        KNOWN_STOCKS[item["code"]] = {"name": item["name"], "theme": item["theme"], "genre": g}

def normalize_ticker(raw_input):
    s = unicodedata.normalize('NFKC', raw_input).strip().upper()
    if not s: return ""
    if "." in s or s.startswith("^") or "=" in s: return s
    if len(s) == 4 and any(ch.isdigit() for ch in s): return f"{s}.T"
    return s

# ==========================================
# 🌐 マクロ市場データ取得
# ==========================================
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

# ==========================================
# 🧬 最新クオンツ数理モジュール（Hurst指数・Kalmanフィルタ・Kyleラムダ）
# ==========================================
def compute_latest_quant_metrics(close_series: pd.Series, vol_ratio_series: pd.Series, day_ret_series: pd.Series) -> dict:
    """最新のウォール街数理クオンツ指標を自動計算して返す"""
    prices = close_series.dropna().values
    # 1. Hurst指数（ハースト指数：H > 0.5ならトレンド持続性が強い、H < 0.5なら平均回帰）
    hurst_val = 0.52
    if len(prices) >= 30:
        try:
            lags = range(2, 12)
            tau = [np.std(np.subtract(prices[lag:], prices[:-lag])) for lag in lags]
            tau = [t if t > 0 else 1e-6 for t in tau]
            poly = np.polyfit(np.log(list(lags)), np.log(tau), 1)
            hurst_val = float(np.clip(poly[0] * 1.35, 0.25, 0.85))
        except Exception:
            hurst_val = 0.52

    # 2. 1次元適応カルマンフィルタ（ノイズ除去トレンド推計値）
    kalman_est = float(prices[-1])
    if len(prices) >= 10:
        x_est = float(prices[0])
        p_est = 1.0
        q_noise = 0.03  # プロセスノイズ
        r_noise = 0.12  # 観測ノイズ
        for z in prices[1:]:
            p_pred = p_est + q_noise
            k_gain = p_pred / (p_pred + r_noise)
            x_est = x_est + k_gain * (float(z) - x_est)
            p_est = (1.0 - k_gain) * p_pred
        kalman_est = x_est
    kalman_bull_pct = round((float(prices[-1]) - kalman_est) / max(kalman_est, 1e-4) * 100, 2)

    # 3. Kyle's Lambda（カイルのラムダ：大口注文による価格冲击・流動性枯渇係数）
    recent_ret = day_ret_series.tail(5).abs().mean()
    recent_vol = vol_ratio_series.tail(5).mean()
    kyle_lambda = round(float(recent_ret / max(recent_vol, 0.3)), 2)

    return {
        "hurst": round(hurst_val, 2),
        "kalman_est": kalman_est,
        "kalman_bull_pct": kalman_bull_pct,
        "kyle_lambda": kyle_lambda
    }

# ==========================================
# 🏦 機関投資家クオンツ ＆ 10段階シグナル判定エンジン
# ==========================================
def analyze_single_dataframe(df_raw, code, name, theme, genre, macro, boost_inst=True, boost_5ch=True, boost_squeeze=True, boost_tokugai=True, use_latest_algo=True):
    try:
        if df_raw is None or df_raw.empty:
            return None
        df = df_raw.dropna(subset=['Close', 'Open', 'High', 'Low', 'Volume']).copy()
        if len(df) < 35:
            return None

        df['Prev_Close'] = df['Close'].shift(1)
        df['Day_Return'] = (df['Close'] - df['Prev_Close']) / df['Prev_Close'] * 100
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['Vol_MA5'] = df['Volume'].rolling(5).mean().replace(0, np.nan)
        df['Vol_MA20'] = df['Volume'].rolling(20).mean().replace(0, np.nan)
        df['Vol_Ratio'] = (df['Volume'] / df['Vol_MA20']).fillna(1.0)
        df['Vol_Accel_5d'] = (df['Volume'] / df['Vol_MA5']).fillna(1.0)

        delta = df['Close'].diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss.replace(0, np.nan)
        df['RSI'] = (100 - (100 / (1 + rs))).fillna(50.0)

        ema12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = ema12 - ema26
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

        tr = pd.concat([
            df['High'] - df['Low'],
            (df['High'] - df['Prev_Close']).abs(),
            (df['Low'] - df['Prev_Close']).abs()
        ], axis=1).max(axis=1)
        df['ATR'] = tr.rolling(14).mean().fillna(df['Close'] * 0.02)
        df['ATR_Pct'] = (df['ATR'] / df['Close'] * 100).fillna(2.0)

        high_low = (df['High'] - df['Low']).replace(0, np.nan)
        df['Close_Pos'] = ((df['Close'] - df['Low']) / high_low).fillna(0.5)
        body_top = df[['Open', 'Close']].max(axis=1)
        df['Upper_Shadow'] = ((df['High'] - body_top) / high_low).fillna(0.0)
        df['VWAP20'] = (((df['High'] + df['Low'] + df['Close']) / 3.0 * df['Volume']).rolling(20).sum() / df['Volume'].rolling(20).sum().replace(0, np.nan)).fillna(df['Close'])

        df['High_20'] = df['High'].shift(1).rolling(20).max().fillna(df['High'])
        df['Dist_High20'] = ((df['Close'] - df['High_20']) / df['High_20'] * 100).fillna(0.0)

        df['Signed_Order_Flow'] = ((df['Close'] - df['Open']) / high_low).fillna(0.0) * df['Vol_Ratio']
        df['VPIN_5d'] = df['Signed_Order_Flow'].rolling(5).mean().fillna(0.0)

        df['Amihud_Impact'] = (df['Day_Return'].abs() / df['Vol_Ratio'].replace(0, 1.0)).fillna(1.0)
        df['Amihud_Ratio'] = (df['Amihud_Impact'] / df['Amihud_Impact'].rolling(20).mean().replace(0, 1.0)).fillna(1.0)

        # 🧬 最新クオンツ指標（Hurst / Kalman / Kyleλ）の自動算出
        adv_q = compute_latest_quant_metrics(df['Close'], df['Vol_Ratio'], df['Day_Return'].fillna(0.0))
        hurst_v = adv_q["hurst"]
        kalman_bull = adv_q["kalman_bull_pct"]
        kyle_lam = adv_q["kyle_lambda"]

        cond_inst_accum = (df['VPIN_5d'] >= 0.22) & (df['Close'] >= df['VWAP20']) & (df['Close_Pos'] >= 0.68)
        cond_5ch_surge = (df['Vol_Accel_5d'] >= 1.35) & (df['Close_Pos'] >= 0.72) & (df['Upper_Shadow'] <= 0.18) & (df['Close'] > df['Open'])
        cond_sq_breakout = (df['Close'] >= df['High_20'] * 0.992) & (df['Vol_Ratio'] >= 1.2) & (df['Close_Pos'] >= 0.7)

        df['Next_Open'] = df['Open'].shift(-1)
        df['Gap_Pct'] = (df['Next_Open'] - df['Close']) / df['Close'] * 100
        df['Morning_Up'] = df['Next_Open'] > df['Close']

        latest = df.iloc[-1]
        history = df.iloc[:-1].dropna(subset=['Next_Open', 'MA20', 'RSI'])
        if len(history) == 0:
            return None

        upper_sh = float(latest['Upper_Shadow'])
        vol_acc = float(latest['Vol_Accel_5d'])
        c_pos = float(latest['Close_Pos'])
        dist_h20 = float(latest['Dist_High20'])
        vpin_val = float(latest['VPIN_5d'])
        amihud_r = float(latest['Amihud_Ratio'])

        inst_raw = 50.0 + vpin_val * 45.0 + (c_pos - 0.5) * 25.0
        if float(latest['Close']) >= float(latest['VWAP20']):
            inst_raw += 10.0
        if use_latest_algo and hurst_v >= 0.56 and kalman_bull > 0:
            inst_raw += 7.0
        if float(latest['Day_Return']) > 0.5 and amihud_r >= 1.15 and upper_sh <= 0.2:
            inst_raw += 12.0
            inst_status = f"🏦 機関の浮動株吸い上げ・売り板枯渇 (VPIN {vpin_val:+.2f} / 弾性 {amihud_r:.2f}倍)"
        elif cond_inst_accum.iloc[-1]:
            inst_raw += 10.0
            inst_status = f"🏦 機関アルゴリズム・ステルス氷山買い集め検知 (VPIN {vpin_val:+.2f})"
        elif vpin_val < -0.15:
            inst_raw -= 12.0
            inst_status = f"⚠️ 機関のTWAP/VWAP売り執行警戒 (VPIN {vpin_val:+.2f})"
        else:
            inst_status = f"⚖️ 機関オーダーフロー中立 (VPIN {vpin_val:+.2f} / 弾性 {amihud_r:.2f}倍)"
        inst_score = int(min(max(round(inst_raw), 15), 99))

        board5ch_raw = 50.0 + (min(vol_acc, 3.0) - 1.0) * 18.0 + (c_pos - 0.5) * 30.0
        if upper_sh >= 0.38:
            board5ch_raw -= 25.0
            board5ch_status = f"⚠️ 上ヒゲシコリ玉警戒 (上ヒゲ率{int(upper_sh*100)}%・ヤレヤレ売り注意)"
        elif dist_h20 >= -0.5 and upper_sh <= 0.15 and vol_acc >= 1.2:
            board5ch_raw += 18.0
            board5ch_status = "🚀 5ch板・青天井ブレイク (上値シコリ玉なし・イナゴ初動集中)"
        elif cond_5ch_surge.iloc[-1]:
            board5ch_raw += 12.0
            board5ch_status = f"🔥 5ch板・初動資金集中 (5日平均比 {vol_acc:.2f}倍の出来高急増＆高値引け)"
        else:
            board5ch_status = f"⚖️ 5ch板・通常需給 (5日出来高加速 {vol_acc:.2f}倍 / 上ヒゲ率 {int(upper_sh*100)}%)"
        board5ch_score = int(min(max(round(board5ch_raw), 15), 99))

        sq_raw = 42.0 + (22.0 if dist_h20 >= 0 else (14.0 if dist_h20 >= -2.5 else 4.0))
        sq_raw += min(float(latest['Vol_Ratio']), 3.0) * 8.0 + (c_pos - 0.5) * 24.0
        squeeze_score = int(min(max(round(sq_raw), 15), 99))
        if cond_sq_breakout.iloc[-1]:
            squeeze_type = "🔥 20日高値ブレイク踏み上げ (売り方全員含み損)"
        elif dist_h20 >= -2.0 and c_pos >= 0.72:
            squeeze_type = "⚡ 踏み上げトリガーロックオン (高値突破寸前)"
        else:
            squeeze_type = f"⚖️ 20日高値乖離 {dist_h20:+.2f}%"

        close_pos_pct = int(round(c_pos * 100))
        closing_power_score = int(min(max(round(40.0 + c_pos * 35.0 + min(float(latest['Vol_Ratio']), 2.5) * 10.0), 15), 99))

        if cond_inst_accum.iloc[-1]:
            signal = "🏦 機関VPINステルス買い集め＋VWAP順行"
            sub = history[cond_inst_accum.reindex(history.index, fill_value=False)]
        elif cond_5ch_surge.iloc[-1]:
            signal = "🔥 5ch初動イナゴ集中＋シコリ玉なし高値引け"
            sub = history[cond_5ch_surge.reindex(history.index, fill_value=False)]
        elif cond_sq_breakout.iloc[-1]:
            signal = "🚀 20日高値ブレイク・ショートスクイーズ"
            sub = history[cond_sq_breakout.reindex(history.index, fill_value=False)]
        elif latest['Day_Return'] > 0:
            signal = "📈 陽線トレンド継続"
            sub = history[history['Day_Return'] > 0]
        else:
            signal = "☁️ 押し目・調整局面"
            sub = history[history['Day_Return'] <= 0]

        if len(sub) < 5:
            sub = history

        total = len(sub)
        wins = int(sub['Morning_Up'].sum())
        prob = round((wins / total) * 100, 1)
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

        # 🧬 最新アルゴリズム自動進化ボーナス（VIXとHurst指数・Kalmanによるレジーム適応）
        evo_bonus = 0.0
        if use_latest_algo:
            evo_bonus += (hurst_v - 0.5) * 18.0
            evo_bonus += np.clip(kalman_bull * 1.2, -5.0, 6.0)
            if vix_val >= 22.0 and inst_score >= 65:
                evo_bonus += 4.0  # 高VIX下で機関が買っているディフェンシブ強気銘柄を優遇

        base_score = min(max(prob * 0.52, 10), 44) + min(max((expected_edge + 0.3) * 12, 0), 14)
        in_bonus = round((inst_score - 50) * 0.22) if boost_inst else 0
        b5_bonus = round((board5ch_score - 50) * 0.18) if boost_5ch else 0
        sq_bonus = round((squeeze_score - 50) * 0.16) if boost_squeeze else 0
        tk_bonus = round((tokugai_prob - 45) * 0.14) if boost_tokugai else 0
        ai_score = int(min(max(round(base_score + in_bonus + b5_bonus + sq_bonus + tk_bonus + evo_bonus), 15), 99))

        survival_power = round(
            ai_score * 0.35 + inst_score * 0.25 + board5ch_score * 0.20 + squeeze_score * 0.10 + min(float(latest['ATR_Pct']) * 3.5, 12.0) + max(0.0, evo_bonus), 1
        )

        # 🎯 翌朝株価 10段階シグナル評価（絶対買い / 買い / 様子見 / 危険 / 絶対手を出すな）
        tier_val = ai_score * 0.40 + prob * 0.25 + inst_score * 0.20 + board5ch_score * 0.15
        if upper_sh >= 0.42:
            tier_val -= 12.0
        if vpin_val <= -0.20:
            tier_val -= 10.0

        if tier_val >= 80:
            tier_num, tier_label, tier_color, tier_bg = 10, "【第10段階：🌟絶対買い】機関VPIN極大・翌朝爆上げ濃厚", "#ffffff", "linear-gradient(135deg, #991b1b, #dc2626)"
        elif tier_val >= 75:
            tier_num, tier_label, tier_color, tier_bg = 9, "【第9段階：🔥絶対買い】特買い・踏み上げ急騰ロックオン", "#ffffff", "linear-gradient(135deg, #b91c1c, #ef4444)"
        elif tier_val >= 70:
            tier_num, tier_label, tier_color, tier_bg = 8, "【第8段階：⭕買い】機関買い集め・強気順張り", "#ffffff", "linear-gradient(135deg, #c2410c, #ea580c)"
        elif tier_val >= 65:
            tier_num, tier_label, tier_color, tier_bg = 7, "【第7段階：⭕買い】好需給・VWAP押し目買い優勢", "#ffffff", "linear-gradient(135deg, #b45309, #d97706)"
        elif tier_val >= 60:
            tier_num, tier_label, tier_color, tier_bg = 6, "【第6段階：👀様子見(買い寄り)】初動の気配確認後に打診", "#0f172a", "linear-gradient(135deg, #fde047, #facc15)"
        elif tier_val >= 55:
            tier_num, tier_label, tier_color, tier_bg = 5, "【第5段階：👀様子見(中立)】方向感待ち・深追い禁物", "#f8fafc", "linear-gradient(135deg, #475569, #64748b)"
        elif tier_val >= 50:
            tier_num, tier_label, tier_color, tier_bg = 4, "【第4段階：⚠️危険(売り優勢)】上値シコリ玉・寄り天警戒", "#ffffff", "linear-gradient(135deg, #78350f, #b45309)"
        elif tier_val >= 45:
            tier_num, tier_label, tier_color, tier_bg = 3, "【第3段階：⚠️危険】機関の売り浴びせ・下落リスク大", "#ffffff", "linear-gradient(135deg, #7f1d1d, #991b1b)"
        elif tier_val >= 40:
            tier_num, tier_label, tier_color, tier_bg = 2, "【第2段階：☠️絶対手を出すな】需給崩壊・高値掴み厳禁", "#ffffff", "linear-gradient(135deg, #450a0a, #7f1d1d)"
        else:
            tier_num, tier_label, tier_color, tier_bg = 1, "【第1段階：☠️絶対手を出すな】全面売り圧力・エントリー禁止", "#ffffff", "linear-gradient(135deg, #1e1b4b, #450a0a)"

        tp_val = max(pts_est_val, close_val) + (atr_val * 0.85)
        sl_val = close_val - (atr_val * 0.5)
        risk_per_share = max(close_val - sl_val, close_val * 0.005)
        allowed_risk_money = total_capital * (risk_tolerance_pct / 100.0)
        shares = max(1, int(allowed_risk_money / risk_per_share))

        def fmt_p(v):
            return f"{v:,.0f}円" if is_jp else f"${v:,.2f}"

        return {
            "full_code": code, "code": code.replace(".T", ""), "name": name, "genre": genre,
            "price": fmt_p(close_val), "raw_close": close_val,
            "tp_price": fmt_p(tp_val), "tp_pct": round((tp_val - close_val) / close_val * 100, 1),
            "sl_price": fmt_p(sl_val), "sl_pct": round((sl_val - close_val) / close_val * 100, 1),
            "vwap_price": fmt_p(float(latest['VWAP20'])),
            "inst_score": inst_score, "inst_status": inst_status, "vpin": round(vpin_val, 2), "amihud_ratio": round(amihud_r, 2),
            "hurst": hurst_v, "kalman_bull_pct": kalman_bull, "kyle_lambda": kyle_lam,
            "board5ch_score": board5ch_score, "board5ch_status": board5ch_status, "upper_shadow_pct": int(upper_sh * 100),
            "close_pos_pct": close_pos_pct, "closing_power_score": closing_power_score,
            "squeeze_score": squeeze_score, "squeeze_type": squeeze_type,
            "squeeze_trigger_price": fmt_p(high20_val), "raw_high20": high20_val, "dist_to_high20": round(dist_h20, 2),
            "pts_est_price": fmt_p(pts_est_val), "pts_gap_pct": pts_gap_pct,
            "tokugai_prob": tokugai_prob, "tokugai_line": fmt_p(tokugai_line_val),
            "tokugai_pct_threshold": tokugai_pct_threshold, "tokugai_status": tokugai_status,
            "diff": round(float(latest['Day_Return']), 2), "signal": signal,
            "prob": prob, "count": f"{wins}/{total}回", "gap": avg_gap, "max_win_gap": max_win_gap,
            "rsi": round(float(latest['RSI']), 1), "vol_ratio": round(float(latest['Vol_Ratio']), 2),
            "macd_state": "強気↑" if latest['MACD_Hist'] > 0 else "調整↓",
            "atr_pct": round(float(latest['ATR_Pct']), 1), "payoff": payoff_ratio, "edge": expected_edge,
            "ai_score": ai_score, "survival_power": survival_power, "theme": theme,
            "tier_num": tier_num, "tier_label": tier_label, "tier_color": tier_color, "tier_bg": tier_bg,
            "lot_info": {
                "shares": shares, "position_value": shares * close_val,
                "capital_ratio": round((shares * close_val / total_capital) * 100, 1),
                "risk_amount": allowed_risk_money
            }
        }
    except Exception:
        return None

@st.cache_data(ttl=1800)
def fetch_all_pool_batch(macro, boost_inst, boost_5ch, boost_squeeze, boost_tokugai, use_latest_algo):
    all_codes = list({s["code"] for stocks in STOCK_POOL.values() for s in stocks})
    raw_data = yf.download(all_codes, period="6mo", group_by="ticker", threads=True, progress=False)

    genre_Map = {g: [] for g in STOCK_POOL.keys()}
    all_list = []
    seen = set()

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

# --- ⚡ 5分足（Intraday）解析エンジン ---
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

        recent_12 = day_df.tail(12)
        twap_green = round(int((recent_12['Close'] >= recent_12['Open']).sum()) / len(recent_12) * 100, 1)
        is_jp = ".T" in full_code
        vwap5_fmt = f"{latest_vwap5:,.0f}円" if is_jp else f"${latest_vwap5:,.2f}"

        status_5m = "🔥 5分足VWAP上・機関TWAP順行" if vwap5_dev >= 0 else "🧊 5分足VWAP下・押し目待機"
        chart_df = pd.DataFrame({
            "Time": day_df.index.strftime("%H:%M"),
            "Open": day_df["Open"].astype(float).values, "High": day_df["High"].astype(float).values,
            "Low": day_df["Low"].astype(float).values, "Close": day_df["Close"].astype(float).values,
            "VWAP": day_df["VWAP_5m"].astype(float).values,
            "TriggerLine": float(trigger_high20) if trigger_high20 else latest_vwap5,
            "BarColor": np.where(day_df["Close"].values >= day_df["Open"].values, "陽線", "陰線")
        })
        return {"vwap5_price": vwap5_fmt, "vwap5_dev": vwap5_dev, "twap_green_ratio": twap_green, "status_5m": status_5m, "chart_date": str(dates[-1]), "chart_df": chart_df}
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
    st.altair_chart((wick + body + vwap_line).properties(height=185), use_container_width=True)

# ==========================================
# 🧠 7大AI【動的ロール割り当て＋最新クオンツ組込】合議アルゴリズム
# ==========================================
def run_7ai_council_algorithm(r, m5=None):
    vwap_ref = m5['vwap5_price'] if m5 else r['vwap_price']
    half_lot = max(1, r['lot_info']['shares'] // 2)
    rem_lot = max(0, r['lot_info']['shares'] - half_lot)

    code_seed = sum(ord(ch) for ch in r["code"])
    is_squeeze_hot = r["squeeze_score"] >= 68
    is_inst_hot = r["inst_score"] >= 68
    is_5ch_hot = r["board5ch_score"] >= 68

    claude_s  = int(min(max(round(50 + (r["prob"] - 50) * 0.8 + (r["payoff"] - 1.0) * 15 - r["upper_shadow_pct"] * 0.2), 20), 99))
    grok_s    = int(min(max(round(45 + (r["board5ch_score"] - 50) * 0.45 + (r["squeeze_score"] - 50) * 0.35 + r["tokugai_prob"] * 0.15), 20), 99))
    chatgpt_s = int(min(max(round((r["ai_score"] + r["inst_score"] + claude_s) / 3.0), 20), 99))
    gemini_s  = int(min(max(round(50 + r["pts_gap_pct"] * 12 + (r["inst_score"] - 50) * 0.35), 20), 99))
    perp_s    = int(min(max(round(r["inst_score"] * 0.55 + r["board5ch_score"] * 0.45), 20), 99))
    gensp_s   = int(min(max(round((claude_s + grok_s + chatgpt_s + gemini_s + perp_s) / 5.0), 20), 99))
    nblm_s    = int(min(max(round(48 + (r["prob"] - 50) * 0.9 + (r["payoff"] - 1.0) * 12), 20), 99))
    final_s   = int(round((claude_s + grok_s + chatgpt_s + gemini_s + perp_s + gensp_s + nblm_s) / 7.0))

    if is_inst_hot:
        claude_role = "🟠 Claude【担当：機関VPIN＆カルマンフィルタ数理監査】"
        claude_msg = f"VPINが <b>{r['vpin']:+.2f}</b>、カルマン推計乖離 <b>{r['kalman_bull_pct']:+.2f}%</b> と機関の買い支えが顕著です。逆指値 <b>{r['sl_price']}</b> を置けばリスク対比の期待値は抜群です。"
    elif r["upper_shadow_pct"] >= 30:
        claude_role = "🟠 Claude【担当：高値掴みドローダウン制御＆シコリ玉警戒】"
        claude_msg = f"上ヒゲ率 <b>{r['upper_shadow_pct']}%</b> の戻り売りリスクを計算しました。朝イチの成行飛びつきは避け、<b>{vwap_ref}</b> までの押し目を待つことで最大損失を <b>{r['lot_info']['risk_amount']:,.0f}円</b> 以内にロックできます。"
    else:
        claude_role = "🟠 Claude【担当：ハースト指数(H={r['hurst']})＆ケリー基準検証】"
        claude_msg = f"ハースト指数 <b>{r['hurst']}</b>、過去勝率 <b>{r['prob']}%</b>・損益比 <b>{r['payoff']}倍</b>（期待値 <b>{r['edge']:+.2f}%</b>）。総資金の <b>{r['lot_info']['capital_ratio']}%（{r['lot_info']['shares']:,}株）</b> 投入が数学的最適解です。"

    if is_squeeze_hot:
        grok_role = "🔴 Grok【担当：ショートスクイーズ（空売り丸焦げ踏み上げ）解析】"
        grok_msg = f"空売り勢の防衛線である20日高値（<b>{r['squeeze_trigger_price']}</b>）まであと <b>{r['dist_to_high20']:+.2f}%</b>！突破した瞬間、売り方の強制ロスカット買い戻しが連鎖爆発します。"
    elif is_5ch_hot:
        grok_role = "🔴 Grok【担当：5chデイトレ実況板・初動イナゴモメンタム解析】"
        grok_msg = f"5ch板需給は「<b>{r['board5ch_status']}</b>」。シコリ玉が極めて少なく、寄付きからデイトレーダーの順張り資金が一気に集中しやすい波形です。"
    else:
        grok_role = "🔴 Grok【担当：SNSセンチメント＆寄り前『特買い』気配爆発力】"
        grok_msg = f"翌朝の特買い発生確率は <b>{r['tokugai_prob']}%</b>（特買い発動ライン <b>{r['tokugai_line']}</b>）。朝8:50の気配値が <b>{r['pts_est_price']}</b> 超えなら初動に乗るチャンスです。"

    if code_seed % 3 == 0:
        chatgpt_role = "🟢 ChatGPT【担当：機関投資家VWAP/TWAPアルゴリズム追随戦略】"
        chatgpt_msg = f"機関投資家の執行基準線であるVWAP（<b>{vwap_ref}</b>）と日足MACD（<b>{r['macd_state']}</b>）を統合評価。機関アルゴと同様にVWAPより上での順張り分割買いが最も合理的です。"
    elif code_seed % 3 == 1:
        chatgpt_role = "🟢 ChatGPT【担当：日足×5分足マルチタイムフレーム・シナリオ構築】"
        chatgpt_msg = f"日足のトレンド強度はAIスコア <b>{r['ai_score']}点</b>、夜間理論ギャップは <b>{r['pts_gap_pct']:+.2f}%</b>。9:10以降のトレンド確定に乗る王道シナリオを推奨します。"
    else:
        chatgpt_role = "🟢 ChatGPT【担当：総合クオンツバランス＆機関ステルス吸収判定】"
        chatgpt_msg = f"機関クオンツ評価「<b>{r['inst_status']}</b>」と個人需給のバランスが高水準で一致。第一利確ターゲット <b>{r['tp_price']}（+{r['tp_pct']}%）</b> を狙うメイン銘柄です。"

    if ".T" in r["full_code"]:
        gemini_role = f"🔵 Gemini【担当：CME日経先物・米SOX連動＆『{r['genre']}』資金循環】"
        gemini_msg = f"海外マクロ地合いと「{r['genre']}」テーマ（{r['theme']}）の資金流入を解析。夜間理論気配は <b>{r['pts_est_price']}</b> と算出され、海外勢のバスケット買いが入りやすい環境です。"
    else:
        gemini_role = f"🔵 Gemini【担当：米国ウォール街セクターローテーション＆金利・VIX連動】"
        gemini_msg = f"米国「{r['genre']}」セクターへの機関資金フローは堅調。プレマーケット気配（理論値 <b>{r['pts_est_price']}</b>）から寄り付き後の上値追いが期待できます。"

    if r["amihud_ratio"] >= 1.1:
        perp_role = "🌐 Perplexity【担当：Amihud非流動性＆Kyleラムダ（浮動株枯渇）監査】"
        perp_msg = f"価格弾性率が <b>{r['amihud_ratio']}倍</b>（Kyleλ: <b>{r['kyle_lambda']}</b>）に上昇中。機関が浮動株を吸収したことで売り板が薄くなっており、まとまった買いで一気に値が飛びやすい真空状態です。"
    else:
        perp_role = "🌐 Perplexity【担当：大引けMOC機関買い集め＆朝8:55見せ板ファクトチェック】"
        perp_msg = f"出来高倍率 <b>{r['vol_ratio']}倍</b>・引け位置 <b>{r['close_pos_pct']}%</b> を検証。フェイクの見せ板を排除するため、注文取消が制限される朝8:55以降の成行買い残を確認してください。"

    if is_squeeze_hot:
        gensp_role = "✨ Genspark【担当：高値ブレイクアウト追撃（ピラミッディング）戦術】"
        gensp_msg = f"①寄付きでまず <b>{half_lot:,}株</b> エントリー → ②空売り踏み上げトリガーである <b>{r['squeeze_trigger_price']}</b> を突破した瞬間に残り <b>{rem_lot:,}株</b> を追撃投入する戦術がベストです！"
    else:
        gensp_role = "✨ Genspark【担当：機関流・5分足VWAP押し目2分割エントリー戦術】"
        gensp_msg = f"①朝9:00に打診買い <b>{half_lot:,}株</b> → ②9:05〜9:25に5分足VWAP（<b>{vwap_ref}</b>）で下ヒゲ反発を確認して残り <b>{rem_lot:,}株</b> を追加し、<b>{r['tp_price']}</b> で利確します。"

    nblm_role = "📓 NotebookLM【担当：過去1年ヒストリカル類似波形＆アノマリー照合】"
    nblm_msg = f"過去1年間で「{r['signal']}」が出現した <b>{r['count']}</b> を照合した結果、翌朝上昇率は <b>{r['prob']}%</b>、過去最大ギャップアップは <b>+{r['max_win_gap']}%</b> と高い再現性を記録しています。"

    return {
        "final_score": final_s,
        "agents": [
            (claude_role, claude_s, claude_msg),
            (grok_role, grok_s, grok_msg),
            (chatgpt_role, chatgpt_s, chatgpt_msg),
            (gemini_role, gemini_s, gemini_msg),
            (perp_role, perp_s, perp_msg),
            (gensp_role, gensp_s, gensp_msg),
            (nblm_role, nblm_s, nblm_msg),
        ],
        "verdict_html": (
            f'<div class="consensus-section"><b>① 🏦 10段階シグナル＆気配判定：</b><b>{r["tier_label"]}</b>（{r["inst_status"]}）。夜間理論気配 <b>{r["pts_est_price"]}</b>（特買い線 <b>{r["tokugai_line"]}</b>）を維持しているか確認。</div>'
            f'<div class="consensus-section"><b>② ⚡ 2段階エントリー：</b>推奨総数 <b>{r["lot_info"]["shares"]:,}株</b> のうち、寄付きで <b>{half_lot:,}株</b>、VWAP（<b>{vwap_ref}</b>）反発または20日高値（<b>{r["squeeze_trigger_price"]}</b>）突破で残り <b>{rem_lot:,}株</b> を投入。</div>'
            f'<div class="consensus-section"><b>③ 🎯 利確＆絶対損切り：</b>利確目標 <b>{r["tp_price"]}（+{r["tp_pct"]}%）</b> ／ 逆指値 <b>{r["sl_price"]}（最大損失 {r["lot_info"]["risk_amount"]:,.0f}円）</b>。</div>'
        )
    }

def generate_7ai_qa_response_html(question, r, debate, lot_info, m5=None) -> str:
    """見やすい高コントラスト配色＆小さめ文字（11.5px）で出力するHTML回答ジェネレーター"""
    q_clean = unicodedata.normalize('NFKC', str(question)).strip()
    q_low = q_clean.lower()
    m5_vwap = m5["vwap5_price"] if m5 else r["vwap_price"]
    half_s = max(1, lot_info['shares'] // 2)
    rem_s = max(0, lot_info['shares'] - half_s)

    if any(k in q_low for k in ["機関", "アルゴ", "vpin", "大口", "ステルス", "浮動株", "板", "最新", "クオンツ"]):
        return (
            f"<div><b>🏦 【担当：ChatGPT ＆ Perplexity（機関クオンツ＆最新数理モデル解析）】</b></div>"
            f"<div style='margin-top:4px;'>・<b>10段階ジャッジ</b>：<b>{r['tier_label']}</b></div>"
            f"<div>・<b>機関オーダーフロー</b>：機関スコア <b>{r['inst_score']}点</b>（{r['inst_status']}）</div>"
            f"<div>・<b>最新クオンツ指標</b>：VPIN <b>{r['vpin']:+.2f}</b> ／ ハースト指数(H) <b>{r['hurst']}</b> ／ カルマン推計乖離 <b>{r['kalman_bull_pct']:+.2f}%</b> ／ Kyleλ(板衝撃度) <b>{r['kyle_lambda']}</b></div>"
            f"<div>・<b>実戦での乗り方</b>：機関の執行アルゴは <b>VWAP（{m5_vwap}）</b> を基準に買い集めます。朝イチにVWAP上で推移していれば機関の買いが継続しているため、押し目を一緒に拾うのが最も高勝率です。</div>"
        )
    elif any(k in q_low for k in ["特買", "気配", "pts", "夜間", "8時", "寄"]):
        return (
            f"<div><b>🚨 【担当：Grok ＆ Gemini（夜間PTS・特買い気配解析）】</b></div>"
            f"<div style='margin-top:4px;'>・<b>夜間理論スタート価格</b>：<b>{r['pts_est_price']}（前日比 {r['pts_gap_pct']:+.2f}%）</b> ／ 特買い発生確率 <b>{r['tokugai_prob']}%</b></div>"
            f"<div>・<b>特買い発動ライン</b>：気配値が <b>{r['tokugai_line']}（+{r['tokugai_pct_threshold']}%）</b> を超えると特別買い気配になります。高値掴みを防ぐため、寄付きはまず半分の <b>{half_s:,}株</b> で入り、<b>{m5_vwap}（VWAP）</b> サポート確認後に残り <b>{rem_s:,}株</b> を追加してください。</div>"
        )
    elif any(k in q_low for k in ["踏み上げ", "空売", "スクイーズ", "高値", "シコリ", "5ch", "イナゴ"]):
        return (
            f"<div><b>🔥 【担当：Grok ＆ Claude（5chシコリ玉＆空売り踏み上げ解析）】</b></div>"
            f"<div style='margin-top:4px;'>・<b>5ch板・シコリ玉診断</b>：現在「<b>{r['board5ch_status']}</b>」（5ch需給スコア <b>{r['board5ch_score']}点</b> / 上ヒゲ率 <b>{r['upper_shadow_pct']}%</b>）</div>"
            f"<div>・<b>踏み上げトリガー価格</b>：直近20日高値の <b>{r['squeeze_trigger_price']}（現在値から {r['dist_to_high20']:+.2f}%）</b> を突破すると、空売り勢の強制ロスカット（成行買い戻し）が連鎖し <b>{r['tp_price']}</b> へ急伸しやすくなります。</div>"
        )
    elif any(k in q_low for k in ["5分", "vwap", "チャート", "初動", "テクニカル", "rsi", "macd"]):
        return (
            f"<div><b>⚡ 【担当：ChatGPT ＆ Genspark（5分足＆テクニカル執行戦術）】</b></div>"
            f"<div style='margin-top:4px;'>・<b>現在のテクニカル指標</b>：5分足VWAP <b>{m5_vwap}</b> ／ 日足RSI <b>{r['rsi']}</b> ／ MACD <b>{r['macd_state']}</b> ／ 出来高倍率 <b>{r['vol_ratio']}倍</b></div>"
            f"<div>・<b>初動の乗り方</b>：朝9:00〜9:15の初動でローソク足が <b>{m5_vwap}</b> より上をキープしていれば機関・大口が買い支えていますので、順張りホールドが正解です。</div>"
        )
    elif any(k in q_low for k in ["損切", "利確", "目標", "売", "出口", "リスク", "下が"]):
        return (
            f"<div><b>🛡️ 【担当：Claude ＆ NotebookLM（利確目標＆リスク管理）】</b></div>"
            f"<div style='margin-top:4px;'>・<b>🎯 第一利確目標</b>：<b>{r['tp_price']}（+{r['tp_pct']}%）</b> で半分を利益確定し、残りは5分足VWAP（<b>{m5_vwap}</b>）を割るまで利益を伸ばします（過去最大GU実績 <b>+{r['max_win_gap']}%</b>）。</div>"
            f"<div>・<b>🛡️ 絶対損切りライン</b>：購入直後に必ず <b>{r['sl_price']}（{r['sl_pct']}%）</b> に逆指値を入れてください。最大損失は <b>約{lot_info['risk_amount']:,.0f}円（総資金の{risk_tolerance_pct}%）</b> に完全に抑えられます。</div>"
        )
    else:
        return (
            f"<div><b>🤖 【担当：ChatGPT・Claude・Grok 7大AI合同評議会】</b></div>"
            f"<div style='margin-top:4px;'>・<b>総合ジャッジ</b>：「{r['name']}（{r['code']}）」の合議スコアは <b>{debate['final_score']}点</b>、10段階評価は <b>『{r['tier_label']}』</b> です。</div>"
            f"<div>・<b>最適ロットと資金配分</b>：総資金 {total_capital:,.0f}円 に対する推奨購入数は <b>{lot_info['shares']:,}株（投資額 {lot_info['position_value']:,.0f}円）</b> です。</div>"
            f"<div>・<b>具体的なアクション</b>：明日の朝はまず寄付き（目安 <b>{r['pts_est_price']}</b>）で半分の <b>{half_s:,}株</b> を買い、<b>{m5_vwap}（VWAP）</b> 反発または <b>{r['squeeze_trigger_price']}（20日高値）</b> 突破で残り <b>{rem_s:,}株</b> を追加、利確 <b>{r['tp_price']}</b>・損切り <b>{r['sl_price']}</b> で臨むのが最も期待値（<b>{r['edge']:+.2f}%</b>・過去勝率 <b>{r['prob']}%</b>）の高い戦術です。</div>"
        )

# ==========================================
# 💬 会議パネル＆質問コーナー（自動スムーズスクロール＆高視認性コンパクト回答カード）
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

def cb_handle_free_q(unique_key, input_key, r, debate, m5):
    user_txt = st.session_state.get(input_key, "").strip()
    if user_txt:
        cb_handle_qa_action(unique_key, user_txt, r, debate, m5)
        st.session_state[input_key] = ""

def cb_clear_chat(unique_key):
    st.session_state["stock_chats"][unique_key] = []

@fragment_decorator
def render_interactive_council_section(r, unique_key):
    is_open = st.session_state["active_debates"].get(unique_key, False)
    in_wl = r["code"] in st.session_state["watchlist"]

    c1, c2 = st.columns([2.2, 1.2])
    with c1:
        st.button(
            "🔼 会議パネルを閉じる" if is_open else "🧠 7大AIで会議して詳細＆質問コーナーを開く",
            key=f"btn_{unique_key}", on_click=cb_toggle_debate, args=(unique_key,), use_container_width=True
        )
    with c2:
        st.button(
            "✅ 監視登録済(解除)" if in_wl else "⭐ 監視リスト追加",
            key=f"wl_{unique_key}", on_click=cb_toggle_watchlist, args=(r["code"], r), use_container_width=True
        )

    if not st.session_state["active_debates"].get(unique_key, False):
        return

    m5 = fetch_5m_intraday_algo(r["full_code"], trigger_high20=r["raw_high20"])
    debate = run_7ai_council_algorithm(r, m5)

    if unique_key not in st.session_state["debate_Animated"]:
        with st.status(f"🧠 7大AIが最新クオンツ指標を含めて「{r['name']}」を徹底議論中...", expanded=True) as status:
            prog = st.progress(0)
            for pct, msg in [
                (25, "🟠 Claude & 🔴 Grok が機関VPIN・Hurst指数・5ch需給を解析中..."),
                (60, "🟢 ChatGPT & 🔵 Gemini & 🌐 Perplexity がカルマンフィルタと浮動株枯渇度を検証中..."),
                (100, "✨ Genspark & 📓 NotebookLM が2段階エントリー戦術を統合中...")
            ]:
                st.write(msg)
                prog.progress(pct)
                time.sleep(0.3)
            status.update(label=f"✅ 7大AI合議完了！（{r['tier_label']}）", state="complete", expanded=False)
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
        f'<span style="font-weight:bold; color:#fbbf24;">🧠 7大AI最高評議会（銘柄別・動的専門ロール検証）</span>'
        f'<span style="background:{r["tier_bg"]}; color:{r["tier_color"]}; padding:2px 10px; border-radius:12px; font-size:11px; font-weight:bold;">{r["tier_label"]}</span>'
        f'</div>{agents_html}'
        f'<div class="consensus-banner"><div style="font-weight:bold; color:#fde047;">🏛️ 7大AI最終コンセンサス</div>{debate["verdict_html"]}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    if unique_key not in st.session_state["stock_chats"]:
        st.session_state["stock_chats"][unique_key] = []

    st.markdown("##### 💬 7大AI評議会へのワンタップ＆自由質問コーナー")

    q_col1, q_col2 = st.columns(2)
    with q_col1:
        st.button("🏦 機関のステルス買い・最新クオンツは？", key=f"q1_{unique_key}", on_click=cb_handle_qa_action, args=(unique_key, "機関投資家のステルス買いや最新クオンツ指標の状況は？", r, debate, m5), use_container_width=True)
        st.button("🔥 5chシコリ玉と踏み上げ価格は？", key=f"q2_{unique_key}", on_click=cb_handle_qa_action, args=(unique_key, "5ch板のシコリ玉と空売り踏み上げトリガー価格は？", r, debate, m5), use_container_width=True)
    with q_col2:
        st.button("🚨 特買い確率と8:50気配の見方は？", key=f"q3_{unique_key}", on_click=cb_handle_qa_action, args=(unique_key, "翌朝の特買い確率と8:50気配の見方は？", r, debate, m5), use_container_width=True)
        st.button("💰 具体的な買い方・利確・損切りは？", key=f"q4_{unique_key}", on_click=cb_handle_qa_action, args=(unique_key, "具体的な買い方と利確・損切りラインを教えて", r, debate, m5), use_container_width=True)

    input_key = f"free_q_in_{unique_key}"
    f_col1, f_col2 = st.columns([3.2, 1])
    with f_col1:
        st.text_input("自由質問を入力", key=input_key, placeholder="自由に質問を入力（例：いつ売るべき？ / なぜ上がる？）", label_visibility="collapsed")
    with f_col2:
        st.button("AIに質問", key=f"free_q_btn_{unique_key}", on_click=cb_handle_free_q, args=(unique_key, input_key, r, debate, m5), use_container_width=True)

    # スクロール先アンカー（回答表示エリア）
    anchor_id = f"qa_ans_anchor_{unique_key}"
    st.markdown(f'<div id="{anchor_id}"></div>', unsafe_allow_html=True)

    chat_history = st.session_state["stock_chats"].get(unique_key, [])
    if chat_history:
        latest_item = chat_history[-1]
        st.markdown(
            f'<div class="qa-answer-card">'
            f'<div class="qa-q-header">🙋 質問 #{len(chat_history)}：{latest_item["q"]}</div>'
            f'{latest_item["a"]}'
            f'</div>',
            unsafe_allow_html=True
        )

        # 質問送信直後に回答カードへさりげなくスムーズスクロール
        if st.session_state.get("scroll_to_chat_key") == unique_key:
            components.html(
                f"""
                <script>
                setTimeout(function() {{
                    const el = window.parent.document.getElementById("{anchor_id}");
                    if (el) {{
                        el.scrollIntoView({{ behavior: "smooth", block: "center" }});
                    }}
                }}, 100);
                </script>
                """,
                height=0,
            )
            st.session_state["scroll_to_chat_key"] = None

        if len(chat_history) > 1:
            with st.expander(f"📚 過去の質問履歴をすべて見る（全 {len(chat_history)} 件）", expanded=False):
                for idx_h in range(len(chat_history) - 2, -1, -1):
                    item = chat_history[idx_h]
                    st.markdown(
                        f'<div class="qa-answer-card">'
                        f'<div class="qa-q-header">🙋 質問 #{idx_h + 1}：{item["q"]}</div>'
                        f'{item["a"]}'
                        f'</div>',
                        unsafe_allow_html=True
                    )
        st.button("🗑️ この銘柄の質問履歴をクリア", key=f"clr_{unique_key}", on_click=cb_clear_chat, args=(unique_key,), use_container_width=True)
    else:
        st.caption("👇 上のボタンまたは自由入力欄から質問すると、直下に読みやすいコンパクトカードで回答が表示され自動でスクロールします。")

# ==========================================
# 🃏 銘柄カード描画 (企業ロゴ ＆ 10段階評価 ＆ 最新クオンツ指標付き)
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
        f'<span style="font-size:11px; opacity:0.92;">Lv.{r["tier_num"]}/10</span>'
        f'</div>'
    )

    html_card = (
        f'<div class="{"search-result-card" if is_custom else "rank-card"}">'
        f'{tier_badge_html}'
        f'<div style="margin-bottom:8px;">{rank_html}<span class="score-badge">🤖 AI: {r["ai_score"]}点</span>'
        f'<span class="inst-badge">🏦 機関: {r["inst_score"]}点</span>'
        f'<span class="board5ch-badge">🔥 5ch需給: {r["board5ch_score"]}点</span>'
        f'<span class="tokugai-badge">🚨 特買い: {r["tokugai_prob"]}%</span>'
        f'<span class="survival-badge">🦁 戦闘力: {r["survival_power"]}</span>'
        f'<span class="quant-evo-badge">🧬 Hurst:{r["hurst"]} / Kal:{r["kalman_bull_pct"]:+.1f}%</span></div>'
        f'<div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">'
        f'<div style="display:flex; align-items:center; gap:10px;">'
        f'{logo_html}'
        f'<div><span style="font-size:16.5px; font-weight:800; color:#0f172a;">{r["name"]}</span> '
        f'<span style="font-size:12px; color:#64748b; font-weight:600;">({r["code"]} / {r["genre"]})</span><br>'
        f'<span style="font-size:14px; color:#334155;">終値: <b>{r["price"]}</b> '
        f'(<span style="color:{diff_color}; font-weight:800;">{diff_sign}{r["diff"]}%</span>)</span></div>'
        f'</div>'
        f'<div style="text-align:right;"><span style="font-size:11px; color:#64748b; font-weight:600;">翌朝上昇確率</span><br>'
        f'<span class="prob-badge">{r["prob"]}%</span>'
        f'<div style="font-size:11px; color:#64748b;">({r["count"]} / 損益比{r["payoff"]}倍)</div></div>'
        f'</div>'
        f'<div class="inst-box"><b>{r["inst_status"]}</b> ｜ 20日VWAP基準: <b>{r["vwap_price"]}</b></div>'
        f'<div class="board5ch-box"><b>📢 {r["board5ch_status"]}</b> ｜ シグナル: <b>{r["signal"]}</b></div>'
        f'<div class="pts-tokugai-box">'
        f'<b>🌙 {r["tokugai_status"]}</b> ｜ 夜間理論気配: <b>{r["pts_est_price"]}</b> ({pts_sign}{r["pts_gap_pct"]}%) ｜ 特買い線: <b>{r["tokugai_line"]}</b>'
        f'</div>'
        f'<div class="squeeze-box">'
        f'<b>{r["squeeze_type"]}</b> ｜ 踏み上げ突破ライン(20日高値): <b>{r["squeeze_trigger_price"]}</b> ({r["dist_to_high20"]:+.2f}%)'
        f'</div>'
        f'<div class="metrics-row">'
        f'<span>🏦 <b>VPIN:</b> {r["vpin"]:+.2f}</span><span>💎 <b>板弾性:</b> {r["amihud_ratio"]}倍</span>'
        f'<span>🧬 <b>Kyleλ:</b> {r["kyle_lambda"]}</span><span>📊 <b>RSI:</b> {r["rsi"]}</span>'
        f'<span>📈 <b>MACD:</b> {r["macd_state"]}</span><span>🔊 <b>出来高:</b> {r["vol_ratio"]}倍</span>'
        f'</div>'
        f'<div class="trade-plan-box">'
        f'<div><div style="font-size:10px; color:#64748b;">🌅 夜間理論寄付き</div><div style="font-size:12.5px; font-weight:800;">{r["pts_est_price"]}</div></div>'
        f'<div style="border-left:1px solid #cbd5e1; border-right:1px solid #cbd5e1;"><div style="font-size:10px; color:#15803d; font-weight:bold;">🎯 利確目標</div><div style="font-size:12.5px; font-weight:800; color:#15803d;">{r["tp_price"]} (+{r["tp_pct"]}%)</div></div>'
        f'<div><div style="font-size:10px; color:#b91c1c; font-weight:bold;">🛡️ 損切り逆指値</div><div style="font-size:12.5px; font-weight:800; color:#b91c1c;">{r["sl_price"]} ({r["sl_pct"]}%)</div></div>'
        f'</div>'
        f'<div class="sizing-box">'
        f'📦 <b>推奨ロット: {lot["shares"]:,}株</b> (投資額: <b>{lot["position_value"]:,.0f}円</b> / 最大損失リスク: <b>{lot["risk_amount"]:,.0f}円</b>)'
        f'</div></div>'
    )
    st.markdown(html_card, unsafe_allow_html=True)
    render_interactive_council_section(r, f"{key_prefix}_{r['code']}")

# ==========================================
# 🚀 メイン画面ヘッダー＆マクロティッカーバー
# ==========================================
macro_info = fetch_macro_market()

macro_pills_html = "".join([
    f'<div style="background:rgba(255,255,255,0.08); padding:4px 10px; border-radius:8px; font-size:11px; display:inline-flex; align-items:center; gap:5px; border:1px solid rgba(255,255,255,0.1);">'
    f'<span style="color:#cbd5e1;">{m["label"]}</span>'
    f'<span style="color:{"#f87171" if m["diff"]>=0 else "#60a5fa"}; font-weight:700;">{"+" if m["diff"]>=0 else ""}{m["diff"]}%</span>'
    f'</div>'
    for m in macro_info.values()
])

st.markdown(f"""
<div style="background: linear-gradient(135deg, #090d16 0%, #1e293b 100%); color: #f8fafc; padding: 18px 20px; border-radius: 16px; margin-bottom: 12px; box-shadow: 0 8px 24px rgba(15,23,42,0.18); border: 1px solid rgba(255,255,255,0.08);">
    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
        <div>
            <div style="font-size:10.5px; color:#fbbf24; font-weight:700; letter-spacing:0.8px;">AUTO-EVOLVING QUANT (VPIN × HURST × KALMAN) & 7-AI TERMINAL</div>
            <h1 style="margin:2px 0 0 0; font-size:20px; color:#ffffff; font-weight:800;">📈 翌朝株価 クオンツ＆7大AI解析 Pro</h1>
        </div>
        <span style="background:rgba(251,191,36,0.15); color:#fde047; border:1px solid rgba(251,191,36,0.4); padding:4px 10px; border-radius:999px; font-size:11px; font-weight:700;">{curr_page_badge}</span>
    </div>
    <div style="display:flex; flex-wrap:wrap; gap:6px; margin-top:12px;">
        {macro_pills_html}
    </div>
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
    with st.spinner(f"「{norm_code}」を機関クオンツ＆最新数理モデルで10段階解析中..."):
        custom_res = fetch_single_stock(norm_code, macro_info, inst_boost_mode, board5ch_boost, squeeze_boost_mode, tokugai_boost_mode, auto_evolve_algo)
    if custom_res:
        render_stock_card(custom_res, is_custom=True, key_prefix="custom")
        if st.button("✖️ 個別診断結果を閉じてランキング一覧に戻る", use_container_width=True):
            st.session_state["custom_search_code"] = ""
            st.session_state["navigation_page"] = "TOP"
            st.rerun()
    else:
        st.error(f"銘柄「{norm_code}」のデータが見つかりませんでした。")

with st.spinner("🏦 国内外の母集団を一括高速スキャン＆最新クオンツ・10段階シグナル選抜中..."):
    genre_results, all_results = fetch_all_pool_batch(macro_info, inst_boost_mode, board5ch_boost, squeeze_boost_mode, tokugai_boost_mode, auto_evolve_algo)

def apply_survival_of_the_fittest(stock_list, cut_pct):
    if not stock_list: return [], []
    sorted_all = sorted(stock_list, key=lambda x: (x["tier_num"], x["survival_power"], x["inst_score"], x["board5ch_score"], x["ai_score"]), reverse=True)
    keep_count = max(3, int(round(len(sorted_all) * (cut_pct / 100.0))))
    return sorted_all[:keep_count], sorted_all[keep_count:]

# --- アプリ内ページ表示切り替え ---
current_page = st.session_state.get("navigation_page", "TOP")

if current_page == "WATCHLIST":
    st.subheader("📋 監視ウォッチリスト (マイ銘柄一覧)")
    if st.button("⬅️ ランキング一覧画面へ戻る", use_container_width=True):
        st.session_state["navigation_page"] = "TOP"
        st.session_state["trigger_scroll_top"] = True
        st.rerun()
    wl = st.session_state["watchlist"]
    if wl:
        for w_code, w_item in list(wl.items()):
            render_stock_card(w_item, is_custom=False, key_prefix=f"wl_page_{w_code}")
    else:
        st.info("⭐ 監視リストに登録されている銘柄はありません。ランキングや検索結果から「監視リスト追加」ボタンを押してください。")

else:
    base_tabs = [
        "🏆 総合サバイバルTOP5",
        "🏦 機関VPIN・最新クオンツ",
        "🔥 5ch板・初動イナゴ",
        "🚨 特買い・夜間PTS",
        "💥 空売り踏み上げ",
        "📋 監視＆注文シート"
    ]
    tab_labels = base_tabs + list(STOCK_POOL.keys())
    tabs = st.tabs(tab_labels)

    with tabs[0]:
        survivors_all, elim_all = apply_survival_of_the_fittest(all_results, survival_cut_pct)
        st.caption(f"🦁 全母集団 {len(all_results)}銘柄から下位 {len(elim_all)}銘柄を足切り！10段階評価・最新クオンツともに最強のTOP5です。")
        for idx, r in enumerate(survivors_all[:5], start=1):
            render_stock_card(r, rank=idx, key_prefix="top5")

    with tabs[1]:
        st.info("🏦 **機関VPIN ＆ 最新数理クオンツ（Hurst指数・Kalman推計・Kyleλ）特選**: 機関のステルス氷山買いとトレンド持続性が検知された上位10銘柄です。")
        inst_list = sorted(all_results, key=lambda x: (x["inst_score"], x["hurst"], x["vpin"], x["survival_power"]), reverse=True)[:10]
        for idx, r in enumerate(inst_list, start=1):
            render_stock_card(r, rank=idx, key_prefix="inst_top")

    with tabs[2]:
        st.info("🔥 **5chデイトレ板・初動イナゴ集中＆シコリ玉排除**: 5日平均出来高からの急増率が高く、上ヒゲ（高値掴みのシコリ玉）が極めて少ない初動TOP10です。")
        b5_list = sorted(all_results, key=lambda x: (x["board5ch_score"], x["survival_power"]), reverse=True)[:10]
        for idx, r in enumerate(b5_list, start=1):
            render_stock_card(r, rank=idx, key_prefix="b5_top")

    with tabs[3]:
        st.info("🚨 **翌朝『特買い』・夜間PTS連動**: 夜間先物・SOX指数の追い風と機関の買い残しから、翌朝9:00に特別買い気配になりやすい上位10銘柄です。")
        tk_list = sorted(all_results, key=lambda x: (x["tokugai_prob"], x["pts_gap_pct"]), reverse=True)[:10]
        for idx, r in enumerate(tk_list, start=1):
            render_stock_card(r, rank=idx, key_prefix="tk_top")

    with tabs[4]:
        st.info("💥 **空売り踏み上げ（ショートスクイーズ）**: 20日高値ブレイクにより、空売り勢が朝イチに強制ロスカットを迫られる上位10銘柄です。")
        sq_list = sorted(all_results, key=lambda x: (x["squeeze_score"], x["inst_score"]), reverse=True)[:10]
        for idx, r in enumerate(sq_list, start=1):
            render_stock_card(r, rank=idx, key_prefix="sq_top")

    with tabs[5]:
        wl = st.session_state["watchlist"]
        st.markdown(f"#### 📋 監視ウォッチリスト ({len(wl)}銘柄)")
        if st.button("⚡ 総合TOP3をワンタップ一括登録", use_container_width=True):
            for item in survivors_all[:3]:
                st.session_state["watchlist"][item["code"]] = item
            st.rerun()
        if st.button("📂 監視ウォッチリスト専用ページで詳細カードを見る", use_container_width=True):
            navigate_to("WATCHLIST")
            st.rerun()
        if wl:
            df_wl = pd.DataFrame([{
                "コード": c, "銘柄名": x["name"], "10段階判定": x["tier_label"], "戦闘力": x["survival_power"],
                "機関スコア": x["inst_score"], "夜間理論気配": x["pts_est_price"], "特買い線": x["tokugai_line"],
                "推奨株数": f"{x['lot_info']['shares']:,}株", "利確": x["tp_price"], "損切": x["sl_price"]
            } for c, x in wl.items()])
            st.dataframe(df_wl, use_container_width=True, hide_index=True)
        else:
            st.info("各カードの「⭐ 監視リスト追加」を押すとここに一覧表示されます。")

    genre_start_idx = 6
    for tab, genre in zip(tabs[genre_start_idx:], STOCK_POOL.keys()):
        with tab:
            g_raw = genre_results.get(genre, [])
            g_surv, g_elim = apply_survival_of_the_fittest(g_raw, survival_cut_pct)
            st.caption(f"🦁 **{genre}サバイバル選抜**: 候補 {len(g_raw)}銘柄中、戦闘力上位 **{len(g_surv)}銘柄が生存**（下位 {len(g_elim)}銘柄が脱落）")
            for idx, r in enumerate(g_surv, start=1):
                render_stock_card(r, rank=idx, key_prefix=f"genre_{genre}")
            if g_elim:
                with st.expander(f"💀 本日のサバイバル脱落・入れ替え候補銘柄を見る（{len(g_elim)}銘柄）"):
                    for e_item in g_elim:
                        st.caption(f"▼ **{e_item['name']} ({e_item['code']})** — {e_item['tier_label']} / 戦闘力: {e_item['survival_power']}pt")
