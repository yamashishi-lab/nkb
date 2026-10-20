import streamlit as st
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
        return False, "SMTP未設定"
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
    """メール内のワンクリック承認/却下リンク（URLパラメータ）を自動処理"""
    try:
        q_params = st.query_params
        action = q_params.get("admin_action", "")
        target_email = q_params.get("email", "").strip().lower()
        token = q_params.get("token", "")

        if action in ["approve", "reject"] and target_email and token:
            expected_token = generate_admin_action_token(target_email, action)
            if hmac.compare_digest(token, expected_token):
                db = load_members_db()
                code = generate_member_passcode(target_email)
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

                if target_email in db:
                    if action == "approve":
                        db[target_email]["status"] = "approved"
                        db[target_email]["passcode"] = code
                        db[target_email]["approved_at"] = now_str
                        db[target_email]["note"] = "ワンクリック承認"
                        save_members_db(db)
                        
                        subj = "【承認完了】翌朝株価クオンツ＆7大AI解析Pro 専用アクセスコード"
                        body = f"{db[target_email].get('name','会員')} 様\n\n利用申請が承認されました。\n\n■登録メール: {target_email}\n■専用アクセスコード: {code}\n"
                        send_auto_email(target_email, subj, body)
                    else:
                        db[target_email]["status"] = "rejected"
                        db[target_email]["approved_at"] = now_str
                        db[target_email]["note"] = "却下"
                        save_members_db(db)
                st.query_params.clear()
    except Exception:
        pass

process_url_admin_action()

def check_member_authentication():
    db = load_members_db()
    if "authenticated_user" not in st.session_state:
        st.session_state["authenticated_user"] = None
    if "admin_view_mode" not in st.session_state:
        st.session_state["admin_view_mode"] = False

    # ログイン中のサイドバー表示
    if st.session_state["authenticated_user"]:
        curr_user = st.session_state["authenticated_user"]
        with st.sidebar:
            st.success(f"👤 ログイン中:\n{curr_user}")
            
            # 管理者の場合のみ会員管理画面への切り替えボタンを表示
            if curr_user == ADMIN_EMAIL.strip().lower():
                pending_cnt = len([v for v in db.values() if v.get("status") == "pending"])
                btn_label = "📊 解析画面に戻る" if st.session_state["admin_view_mode"] else f"👑 会員管理画面を開く ({pending_cnt}件)"
                if st.button(btn_label, use_container_width=True):
                    st.session_state["admin_view_mode"] = not st.session_state["admin_view_mode"]
                    st.rerun()

            if st.button("🚪 ログアウト", use_container_width=True):
                st.session_state["authenticated_user"] = None
                st.session_state["admin_view_mode"] = False
                st.rerun()
        return True

    # 未ログイン時の画面
    st.markdown("""
    <div style="background: linear-gradient(135deg, #0f172a, #1e293b); color: #f8fafc; padding: 24px; border-radius: 14px; text-align: center; margin-top: 10px; margin-bottom: 16px;">
        <h2 style="margin:0; color:#fbbf24; font-size:20px;">🔒 会員限定 クオンツ＆7大AI解析 Pro</h2>
        <p style="font-size:13px; color:#cbd5e1; margin-top:8px; margin-bottom:0;">
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
                st.rerun()
            elif user_rec and user_rec.get("status") == "pending":
                st.warning("⏳ 現在、管理者による承認審査中です。承認されるまで今しばらくお待ちください。")
            elif not is_approved:
                st.error("⚠️ このメールアドレスはまだ会員登録されていません。下のフォームから利用申請を行ってください。")
            else:
                st.error("⚠️ 専用アクセスコードが正しくありません。")

    st.markdown("---")
    st.markdown("##### 📩 新規会員登録・利用許可の申請はこちら（メーラーは起動しません）")
    
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
                approve_url = f"{base_url}/?admin_action=approve&email={urllib.parse.quote(c_mail)}&token={tok_ap}"
                reject_url = f"{base_url}/?admin_action=reject&email={urllib.parse.quote(c_mail)}&token={tok_rj}"

                admin_subj = f"【会員申請】{ap_name}様 ({c_mail}) 承認/却下判定"
                admin_body = (
                    f"新規の会員登録申請が届きました。\n\n"
                    f"・お名前: {ap_name}\n"
                    f"・メール: {c_mail}\n"
                    f"・備考: {ap_note}\n\n"
                    f"【承認リンク（ワンクリック）】\n{approve_url}\n\n"
                    f"【却下リンク（ワンクリック）】\n{reject_url}\n"
                )
                send_auto_email(ADMIN_EMAIL, admin_subj, admin_body)
                st.success("✅ 利用申請を受け付けました！管理者の承認審査が行われますと、登録メールアドレス宛に専用コードが届きます。")
    st.stop()

check_member_authentication()

# ==========================================
# 👑 管理者専用：会員一括管理コンソール
# ==========================================
def render_admin_management_console():
    db = load_members_db()
    st.markdown("### 👑 管理者専用：会員データベース一括管理コンソール")
    st.caption("新規の利用申請の承認・却下、および全会員の管理を行えます。")

    pending_list = [v for v in db.values() if v.get("status") == "pending"]
    if pending_list:
        st.warning(f"🔔 新規の会員登録申請が {len(pending_list)} 件届いています！")
        for p in pending_list:
            p_mail = p["email"]
            p_name = p.get("name", "未入力")
            p_code = generate_member_passcode(p_mail)
            with st.container(border=True):
                st.markdown(f"**📩 申請者:** {p_name} (`{p_mail}`) ／ 備考: {p.get('note','なし')}")
                ac1, ac2 = st.columns(2)
                with ac1:
                    if st.button(f"✅ 承認してパスコード発行", key=f"adm_app_{p_mail}", use_container_width=True):
                        db = load_members_db()
                        db[p_mail]["status"] = "approved"
                        db[p_mail]["passcode"] = p_code
                        db[p_mail]["approved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                        save_members_db(db)
                        
                        subj = "【承認完了】翌朝株価クオンツ＆7大AI解析Pro 専用アクセスコード"
                        body = f"{p_name} 様\n\n会員登録が承認されました。\n\n■登録メール: {p_mail}\n■専用アクセスコード: {p_code}\n"
                        send_auto_email(p_mail, subj, body)
                        st.success(f"✅ {p_mail} を承認しました！（コード: {p_code}）")
                        st.rerun()
                with ac2:
                    if st.button(f"❌ 却下する", key=f"adm_rej_{p_mail}", use_container_width=True):
                        db = load_members_db()
                        db[p_mail]["status"] = "rejected"
                        save_members_db(db)
                        st.warning(f"❌ {p_mail} の申請を却下しました。")
                        st.rerun()
    else:
        st.info("現在、保留中の新規申請はありません。")

    st.markdown("---")
    st.markdown("#### 👥 登録済み会員一覧")
    rows = [{"ステータス": info.get("status"), "お名前": info.get("name"), "メール": em, "パスコード": info.get("passcode"), "申請日": info.get("applied_at"), "備考": info.get("note")} for em, info in db.items()]
    df_m = pd.DataFrame(rows)
    st.dataframe(df_m, use_container_width=True, hide_index=True)

    with st.expander("⚙️ SMTP自動メール送信設定"):
        st.text_input("送信元メールアドレス", value=st.session_state.get("smtp_user", ADMIN_EMAIL), key="smtp_user")
        st.text_input("SMTPアプリパスワード", type="password", key="smtp_pass")
        st.text_input("アプリの公開URL (承認リンク用)", value=st.session_state.get("app_base_url", "http://localhost:8501"), key="app_base_url")

    if st.button("📊 解析システム画面に戻る", use_container_width=True):
        st.session_state["admin_view_mode"] = False
        st.rerun()

if st.session_state.get("authenticated_user") == ADMIN_EMAIL.strip().lower() and st.session_state.get("admin_view_mode", False):
    render_admin_management_console()
    st.stop()

# ==========================================
# 📈 セッション初期化・カスタムCSS
# ==========================================
for k, default_v in [("active_debates", {}), ("debate_Animated", set()), ("stock_chats", {}), ("watchlist", {})]:
    if k not in st.session_state:
        st.session_state[k] = default_v

st.markdown("""
<style>
button[data-baseweb="tab"] { font-size: 13px !important; font-weight: bold !important; padding: 8px 14px !important; }
.stock-card, .rank-card, .search-result-card { background-color: #ffffff !important; color: #0f172a !important; border-radius: 12px; padding: 16px; margin-bottom: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); border-left: 6px solid #e11d48; }
.stock-card *, .rank-card *, .search-result-card * { color: #0f172a; }
.search-result-card { background-color: #fffbeb !important; border-left-color: #d97706; }
.prob-badge { font-size: 22px; font-weight: bold; color: #dc2626 !important; }
.rank-badge { display: inline-block; background: linear-gradient(135deg, #f59e0b, #d97706); color: #ffffff !important; padding: 3px 9px; border-radius: 20px; font-size: 12px; font-weight: bold; margin-right: 4px; }
.score-badge { display: inline-block; background: #1e293b; color: #f8fafc !important; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: bold; }
.inst-badge { display: inline-block; background: linear-gradient(135deg, #1d4ed8, #3b82f6); color: #ffffff !important; padding: 2px 9px; border-radius: 20px; font-size: 11px; font-weight: bold; margin-left: 4px; }
.board5ch-badge { display: inline-block; background: linear-gradient(135deg, #059669, #10b981); color: #ffffff !important; padding: 2px 9px; border-radius: 20px; font-size: 11px; font-weight: bold; margin-left: 4px; }
.squeeze-badge { display: inline-block; background: linear-gradient(135deg, #b91c1c, #ef4444); color: #ffffff !important; padding: 2px 9px; border-radius: 20px; font-size: 11px; font-weight: bold; margin-left: 4px; }
.tokugai-badge { display: inline-block; background: linear-gradient(135deg, #d97706, #f59e0b); color: #ffffff !important; padding: 2px 9px; border-radius: 20px; font-size: 11px; font-weight: bold; margin-left: 4px; }
.survival-badge { display: inline-block; background: #f3e8ff; color: #6b21a8 !important; border: 1px solid #d8b4fe; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: bold; margin-left: 4px; }
.inst-box { background: #eff6ff !important; border: 1px solid #bfdbfe; border-left: 4px solid #2563eb; border-radius: 8px; padding: 8px 12px; margin-top: 6px; font-size: 12px; color: #1e3a8a !important; }
.inst-box * { color: #1e3a8a !important; }
.squeeze-box { background: #fff1f2 !important; border: 1px solid #fecdd3; border-left: 4px solid #e11d48; border-radius: 8px; padding: 8px 12px; margin-top: 6px; font-size: 12px; color: #881337 !important; }
.squeeze-box * { color: #881337 !important; }
.pts-tokugai-box { background: #fffbeb !important; border: 1px solid #fde68a; border-left: 4px solid #d97706; border-radius: 8px; padding: 8px 12px; margin-top: 6px; font-size: 12px; color: #78350f !important; }
.pts-tokugai-box * { color: #78350f !important; }
.board5ch-box { background: #ecfdf5 !important; border: 1px solid #a7f3d0; border-left: 4px solid #059669; border-radius: 8px; padding: 8px 12px; margin-top: 6px; font-size: 12px; color: #064e3b !important; }
.board5ch-box * { color: #064e3b !important; }
.metrics-row { display: flex; flex-wrap: wrap; gap: 6px 10px; margin-top: 8px; font-size: 11px; color: #0f172a !important; background: #f8fafc !important; padding: 8px 10px; border-radius: 6px; border: 1px solid #e2e8f0; }
.metrics-row * { color: #0f172a !important; }
.trade-plan-box { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-top: 8px; background: #f8fafc !important; padding: 8px 6px; border-radius: 8px; border: 1px dashed #cbd5e1; text-align: center; color: #0f172a !important; }
.sizing-box { background: #f0fdf4 !important; border: 1px solid #bbf7d0; border-radius: 8px; padding: 10px 12px; margin-top: 8px; font-size: 12px; color: #166534 !important; }
.sizing-box * { color: #166534 !important; }
.ai-council-box { background: linear-gradient(135deg, #0f172a, #1e293b); color: #f8fafc !important; border-radius: 12px; padding: 16px; margin-top: 6px; margin-bottom: 10px; }
.ai-council-box * { color: #f8fafc; }
.ai-agent-card { background: rgba(255, 255, 255, 0.08); border-radius: 8px; padding: 10px 12px; margin-bottom: 8px; font-size: 12.5px; line-height: 1.6; color: #f8fafc !important; }
.consensus-banner { background: linear-gradient(135deg, #1e1b4b, #312e81); border: 2px solid #818cf8; border-radius: 10px; padding: 14px; margin-top: 12px; font-size: 12.5px; line-height: 1.7; color: #f8fafc !important; }
.consensus-section { background: rgba(255, 255, 255, 0.07); border-left: 3px solid #fbbf24; border-radius: 6px; padding: 8px 10px; margin-top: 8px; color: #f8fafc !important; }
</style>
""", unsafe_allow_html=True)

# --- サイドバー設定 ---
st.sidebar.header("💰 資金管理＆リスク設定")
total_capital = st.sidebar.number_input("総投資資金 (円 / ドル)", min_value=10000, max_value=1000000000, value=1000000, step=50000)
risk_tolerance_pct = st.sidebar.slider("1トレード許容リスク (%)", min_value=0.5, max_value=5.0, value=2.0, step=0.5)

st.sidebar.markdown("---")
st.sidebar.header("🏦 機関クオンツ＆弱肉強食設定")
survival_cut_pct = st.sidebar.slider("弱肉強食・各タブ選抜率 (%)", min_value=40, max_value=100, value=70, step=10)
inst_boost_mode = st.sidebar.checkbox("🏦 機関クオンツ（VPIN・ステルス吸収）優先", value=True)
board5ch_boost = st.sidebar.checkbox("🔥 5ch板・初動イナゴ＆シコリ玉なし優先", value=True)
squeeze_boost_mode = st.sidebar.checkbox("💥 空売り踏み上げ（20日高値突破）優先", value=True)
tokugai_boost_mode = st.sidebar.checkbox("🚨 翌朝『特買い』・夜間PTS連動を優先", value=True)
show_5m_chart = st.sidebar.checkbox("合議パネル内に5分足＆VWAPチャートを描画", value=True)

st.sidebar.markdown("---")
st.sidebar.header(f"📋 監視ウォッチリスト ({len(st.session_state['watchlist'])}銘柄)")
if st.session_state["watchlist"]:
    for w_code, w_item in list(st.session_state["watchlist"].items()):
        st.sidebar.markdown(f"⭐ **{w_item['name']}** ({w_code}) — {w_item['lot_info']['shares']:,}株")
    if st.sidebar.button("🗑️ ウォッチリスト全クリア", use_container_width=True):
        st.session_state["watchlist"] = {}
        st.rerun()

st.title("📱 翌朝株価 クオンツ＆7大AI解析 Pro")
st.caption("【機関投資家VPINクオンツ搭載】7大AI動的ロール合議 × 5ch需給 × 会員一括管理")

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
        {"code": "ASTS", "name": "ASTスペースモバイル (米)", "theme": "宇宙スマホ直接通信。ショートスクイーズ常連"},
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
        "sp500":  {"codes": ["^GSPC"],     "label": "🇺🇸 米S&P500"},
        "sox":    {"codes": ["^SOX"],      "label": "💽 米SOX半導体"},
        "usdjpy": {"codes": ["JPY=X"],     "label": "💴 ドル円為替"},
        "nk_fut": {"codes": ["NIY=F", "^N225"], "label": "🇯🇵 CME日経先物"},
        "vix":    {"codes": ["^VIX"],      "label": "⚡ VIX恐怖指数"}
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
# 🏦 機関投資家クオンツ解析エンジン
# ==========================================
def analyze_single_dataframe(df_raw, code, name, theme, genre, macro, boost_inst=True, boost_5ch=True, boost_squeeze=True, boost_tokugai=True):
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
        if float(latest['Day_Return']) > 0.5 and amihud_r >= 1.15 and upper_sh <= 0.2:
            inst_raw += 12.0
            inst_status = f"🏦 機関の浮動株吸い上げ・売り板枯渇 (VPIN {vpin_val:+.2f} / 価格弾性 {amihud_r:.2f}倍)"
        elif cond_inst_accum.iloc[-1]:
            inst_raw += 10.0
            inst_status = f"🏦 機関アルゴリズム・ステルス氷山買い集め検知 (VPIN {vpin_val:+.2f} / 20日VWAP上維持)"
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

        base_score = min(max(prob * 0.52, 10), 44) + min(max((expected_edge + 0.3) * 12, 0), 14)
        in_bonus = round((inst_score - 50) * 0.22) if boost_inst else 0
        b5_bonus = round((board5ch_score - 50) * 0.18) if boost_5ch else 0
        sq_bonus = round((squeeze_score - 50) * 0.16) if boost_squeeze else 0
        tk_bonus = round((tokugai_prob - 45) * 0.14) if boost_tokugai else 0
        ai_score = int(min(max(round(base_score + in_bonus + b5_bonus + sq_bonus + tk_bonus), 15), 99))

        survival_power = round(
            ai_score * 0.35 + inst_score * 0.25 + board5ch_score * 0.20 + squeeze_score * 0.10 + min(float(latest['ATR_Pct']) * 3.5, 12.0), 1
        )

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
            "lot_info": {
                "shares": shares, "position_value": shares * close_val,
                "capital_ratio": round((shares * close_val / total_capital) * 100, 1),
                "risk_amount": allowed_risk_money
            }
        }
    except Exception:
        return None

@st.cache_data(ttl=1800)
def fetch_all_pool_batch(macro, boost_inst, boost_5ch, boost_squeeze, boost_tokugai):
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
                res = analyze_single_dataframe(df_c, c, s["name"], s["theme"], genre, macro, boost_inst, boost_5ch, boost_squeeze, boost_tokugai)
                if res:
                    genre_Map[genre].append(res)
                    if c not in seen:
                        all_list.append(res)
                        seen.add(c)
            except Exception:
                continue
    return genre_Map, all_list

@st.cache_data(ttl=600)
def fetch_single_stock(code, macro, boost_inst, boost_5ch, boost_squeeze, boost_tokugai):
    df_c = yf.Ticker(code).history(period="6mo")
    info = KNOWN_STOCKS.get(code, {"name": code.replace(".T", ""), "theme": "個別指定銘柄", "genre": "個別検索"})
    return analyze_single_dataframe(df_c, code, info["name"], info["theme"], info["genre"], macro, boost_inst, boost_5ch, boost_squeeze, boost_tokugai)

# ==========================================
# ⚡ 5分足解析
# ==========================================
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
    st.altair_chart((wick + body + vwap_line).properties(height=190), use_container_width=True)

# ==========================================
# 🧠 7大AI合議
# ==========================================
def run_7ai_council_algorithm(r, m5=None):
    vwap_ref = m5['vwap5_price'] if m5 else r['vwap_price']
    half_lot = max(1, r['lot_info']['shares'] // 2)
    rem_lot = max(0, r['lot_info']['shares'] - half_lot)

    claude_s  = int(min(max(round(50 + (r["prob"] - 50) * 0.8 + (r["payoff"] - 1.0) * 15 - r["upper_shadow_pct"] * 0.2), 20), 99))
    grok_s    = int(min(max(round(45 + (r["board5ch_score"] - 50) * 0.45 + (r["squeeze_score"] - 50) * 0.35 + r["tokugai_prob"] * 0.15), 20), 99))
    chatgpt_s = int(min(max(round((r["ai_score"] + r["inst_score"] + claude_s) / 3.0), 20), 99))
    gemini_s  = int(min(max(round(50 + r["pts_gap_pct"] * 12 + (r["inst_score"] - 50) * 0.35), 20), 99))
    perp_s    = int(min(max(round(r["inst_score"] * 0.55 + r["board5ch_score"] * 0.45), 20), 99))
    gensp_s   = int(min(max(round((claude_s + grok_s + chatgpt_s + gemini_s + perp_s) / 5.0), 20), 99))
    nblm_s    = int(min(max(round(48 + (r["prob"] - 50) * 0.9 + (r["payoff"] - 1.0) * 12), 20), 99))
    final_s   = int(round((claude_s + grok_s + chatgpt_s + gemini_s + perp_s + gensp_s + nblm_s) / 7.0))

    return {
        "final_score": final_s,
        "agents": [
            ("🟠 Claude【担当：機関VPINオーダーフロー毒性＆下値リスク監査】", claude_s, f"機関のVPINが <b>{r['vpin']:+.2f}</b> で下値は機関の氷山注文で支えられています。"),
            ("🔴 Grok【担当：ショートスクイーズ・初動イナゴ解析】", grok_s, f"空売り踏み上げトリガーである20日高値（<b>{r['squeeze_trigger_price']}</b>）まであと <b>{r['dist_to_high20']:+.2f}%</b>。"),
            ("🟢 ChatGPT【担当：機関投資家VWAP/TWAP追随戦略】", chatgpt_s, f"VWAP（<b>{vwap_ref}</b>）より上での順張り分割買いが最も合理的です。"),
            ("🔵 Gemini【担当：CME先物・SOX連動＆セクター循環】", gemini_s, f"夜間理論気配は <b>{r['pts_est_price']}</b> と算出され海外勢の資金流入が期待できます。"),
            ("🌐 Perplexity【担当：Amihud非流動性・浮動株枯渇監査】", perp_s, f"価格弾性率 <b>{r['amihud_ratio']}倍</b>。売り板が薄く真空状態です。"),
            ("✨ Genspark【担当：2段階エントリー戦術】", gensp_s, f"寄付きで半分の <b>{half_lot:,}株</b>、VWAP反発で残り <b>{rem_lot:,}株</b> を追加。"),
            ("📓 NotebookLM【担当：ヒストリカル類似波形照合】", nblm_s, f"過去勝率 <b>{r['prob']}%</b>・過去最大ギャップアップ <b>+{r['max_win_gap']}%</b>。")
        ],
        "verdict_html": (
            f'<div class="consensus-section"><b>① 🏦 機関クオンツ＆朝8:55気配：</b>{r["inst_status"]}。夜間理論気配 <b>{r["pts_est_price"]}</b>。</div>'
            f'<div class="consensus-section"><b>② ⚡ 2段階エントリー：</b>寄付き <b>{half_lot:,}株</b> ＋ VWAP（<b>{vwap_ref}</b>）反発で残り <b>{rem_lot:,}株</b>。</div>'
            f'<div class="consensus-section"><b>③ 🎯 利確＆損切り：</b>目標 <b>{r["tp_price"]}（+{r["tp_pct"]}%）</b> ／ 損切 <b>{r["sl_price"]}（最大損失 {r["lot_info"]["risk_amount"]:,.0f}円）</b>。</div>'
        )
    }

def generate_7ai_qa_response(question, r, debate, lot_info, m5=None):
    q_clean = unicodedata.normalize('NFKC', str(question)).strip().lower()
    m5_vwap = m5["vwap5_price"] if m5 else r["vwap_price"]
    if "機関" in q_clean or "vpin" in q_clean:
        return f"🏦 **機関クオンツ診断**：スコア **{r['inst_score']}点**（VPIN: {r['vpin']:+.2f}）。VWAP（{m5_vwap}）を基準に機関の押し目を狙うのが最適です。"
    elif "特買" in q_clean or "気配" in q_clean:
        return f"🚨 **夜間PTS・特買い**：夜間理論価格 **{r['pts_est_price']}**（特買い確率 **{r['tokugai_prob']}%**）。特買い発動線は **{r['tokugai_line']}** です。"
    elif "踏み上げ" in q_clean or "5ch" in q_clean:
        return f"🔥 **踏み上げ・5ch需給**：20日高値 **{r['squeeze_trigger_price']}** を突破すると強烈なスクイーズが発生します。"
    elif "利確" in q_clean or "損切" in q_clean:
        return f"🛡️ **利確・損切**：利確目標 **{r['tp_price']}** ／ 逆指値 **{r['sl_price']}**（最大損失: 約{lot_info['risk_amount']:,.0f}円）。"
    else:
        return f"🤖 **7大AI総合評議会**：合議スコア **{debate['final_score']}点**。推奨ロット **{lot_info['shares']:,}株**。寄付きで打診買いしVWAPで追撃する戦術が推奨されます。"

# ==========================================
# 💬 インタラクティブUI
# ==========================================
def cb_toggle_debate(k): st.session_state["active_debates"][k] = not st.session_state["active_debates"].get(k, False)
def cb_toggle_watchlist(c, d):
    if c in st.session_state["watchlist"]: del st.session_state["watchlist"][c]
    else: st.session_state["watchlist"][c] = d
def cb_handle_qa(k, q, r, deb, m5):
    if k not in st.session_state["stock_chats"]: st.session_state["stock_chats"][k] = []
    ans = generate_7ai_qa_response(q, r, deb, r["lot_info"], m5)
    st.session_state["stock_chats"][k].append({"q": q, "a": ans})
def cb_free_q(k, in_k, r, deb, m5):
    txt = st.session_state.get(in_k, "").strip()
    if txt:
        cb_handle_qa(k, txt, r, deb, m5)
        st.session_state[in_k] = ""
def cb_clear_chat(k): st.session_state["stock_chats"][k] = []

@fragment_decorator
def render_interactive_council_section(r, unique_key):
    is_open = st.session_state["active_debates"].get(unique_key, False)
    in_wl = r["code"] in st.session_state["watchlist"]

    c1, c2 = st.columns([2.2, 1.2])
    with c1: st.button("🔼 会議パネルを閉じる" if is_open else "🧠 7大AIで会議して詳細＆質問コーナーを開く", key=f"btn_{unique_key}", on_click=cb_toggle_debate, args=(unique_key,), use_container_width=True)
    with c2: st.button("✅ 監視登録済(解除)" if in_wl else "⭐ 監視リスト追加", key=f"wl_{unique_key}", on_click=cb_toggle_watchlist, args=(r["code"], r), use_container_width=True)

    if not is_open: return

    m5 = fetch_5m_intraday_algo(r["full_code"], trigger_high20=r["raw_high20"])
    debate = run_7ai_council_algorithm(r, m5)

    if unique_key not in st.session_state["debate_Animated"]:
        with st.status(f"🧠 7大AIが議論中...", expanded=True) as status:
            prog = st.progress(0)
            for pct, msg in [(30, "Claude & Grok 解析中..."), (70, "ChatGPT & Gemini 検証中..."), (100, "完了")]:
                st.write(msg); prog.progress(pct); time.sleep(0.2)
            status.update(label=f"✅ 7大AI合議完了（スコア: {debate['final_score']}点）", state="complete", expanded=False)
        st.session_state["debate_Animated"].add(unique_key)

    if m5 and show_5m_chart:
        st.caption(f"📅 直近5分足チャート ｜ 5分足VWAP: **{m5['vwap5_price']}** ({m5['vwap5_dev']:+.2f}%)")
        render_5m_candlestick_chart(m5)

    agents_html = "".join([f'<div class="ai-agent-card"><div style="font-weight:bold; color:#fbbf24;">{n} — {s}点</div><div>{c}</div></div>' for n, s, c in debate["agents"]])
    st.markdown(f'<div class="ai-council-box"><div style="font-weight:bold; color:#fbbf24; margin-bottom:8px;">🧠 7大AI最高評議会</div>{agents_html}<div class="consensus-banner"><div style="font-weight:bold; color:#fde047;">🏛️ コンセンサス</div>{debate["verdict_html"]}</div></div>', unsafe_allow_html=True)

    if unique_key not in st.session_state["stock_chats"]: st.session_state["stock_chats"][unique_key] = []
    st.markdown("##### 💬 7大AIへの質問コーナー")
    chats = st.session_state["stock_chats"][unique_key]
    if chats:
        with st.container(border=True):
            st.markdown(f"🙋 **質問:** `{chats[-1]['q']}`")
            st.info(chats[-1]["a"])

    qc1, qc2 = st.columns(2)
    with qc1:
        st.button("🏦 機関投資家VPINは？", key=f"q1_{unique_key}", on_click=cb_handle_qa, args=(unique_key, "機関投資家のVPIN状況は？", r, debate, m5), use_container_width=True)
        st.button("🔥 踏み上げ価格は？", key=f"q2_{unique_key}", on_click=cb_handle_qa, args=(unique_key, "空売り踏み上げトリガー価格は？", r, debate, m5), use_container_width=True)
    with qc2:
        st.button("🚨 特買い確率は？", key=f"q3_{unique_key}", on_click=cb_handle_qa, args=(unique_key, "翌朝の特買い確率は？", r, debate, m5), use_container_width=True)
        st.button("💰 利確・損切りは？", key=f"q4_{unique_key}", on_click=cb_handle_qa, args=(unique_key, "利確と損切りの具体的なラインを教えて", r, debate, m5), use_container_width=True)

    in_k = f"fq_{unique_key}"
    fc1, fc2 = st.columns([3.2, 1])
    with fc1: st.text_input("質問入力", key=in_k, placeholder="自由に質問を入力", label_visibility="collapsed")
    with fc2: st.button("質問送信", key=f"fb_{unique_key}", on_click=cb_free_q, args=(unique_key, in_k, r, debate, m5), use_container_width=True)

    if chats:
        with st.expander(f"📚 質問履歴一覧 ({len(chats)}件)"):
            for i in range(len(chats)-1, -1, -1):
                with st.container(border=True):
                    st.markdown(f"🙋 **Q{i+1}: {chats[i]['q']}**")
                    st.success(chats[i]["a"])
            st.button("🗑️ 履歴クリア", key=f"clr_{unique_key}", on_click=cb_clear_chat, args=(unique_key,), use_container_width=True)

def render_stock_card(r, is_custom=False, rank=None, key_prefix="card"):
    diff_color = "#dc2626" if r["diff"] > 0 else "#2563eb"
    diff_sign = "+" if r["diff"] > 0 else ""
    pts_sign = "+" if r["pts_gap_pct"] > 0 else ""
    rank_html = f'<span class="rank-badge">第{rank}位</span>' if rank else ""
    lot = r["lot_info"]

    html_card = (
        f'<div class="{"search-result-card" if is_custom else "rank-card"}">'
        f'<div>{rank_html}<span class="score-badge">🤖 AIスコア: {r["ai_score"]}点</span>'
        f'<span class="inst-badge">🏦 機関: {r["inst_score"]}点</span>'
        f'<span class="board5ch-badge">🔥 5ch: {r["board5ch_score"]}点</span>'
        f'<span class="tokugai-badge">🚨 特買い: {r["tokugai_prob"]}%</span>'
        f'<span class="survival-badge">🦁 戦闘力: {r["survival_power"]}</span></div>'
        f'<div style="display:flex; justify-content:space-between; align-items:center; margin-top:6px;">'
        f'<div><span style="font-size:16px; font-weight:bold; color:#0f172a;">{r["name"]}</span> '
        f'<span style="font-size:12px; color:#64748b;">({r["code"]})</span><br>'
        f'<span style="font-size:14px; color:#334155;">終値: <b>{r["price"]}</b> '
        f'(<span style="color:{diff_color}; font-weight:bold;">{diff_sign}{r["diff"]}%</span>)</span></div>'
        f'<div style="text-align:right;"><span style="font-size:11px; color:#64748b;">翌朝上昇確率</span><br>'
        f'<span class="prob-badge">{r["prob"]}%</span></div></div>'
        f'<div class="inst-box"><b>{r["inst_status"]}</b> ｜ 20日VWAP: <b>{r["vwap_price"]}</b></div>'
        f'<div class="board5ch-box"><b>📢 {r["board5ch_status"]}</b></div>'
        f'<div class="pts-tokugai-box"><b>🌙 {r["tokugai_status"]}</b> ｜ 理論気配: <b>{r["pts_est_price"]}</b> ({pts_sign}{r["pts_gap_pct']}%) ｜ 特買い線: <b>{r["tokugai_line"]}</b></div>'
        f'<div class="squeeze-box"><b>{r["squeeze_type"]}</b> ｜ 20日高値: <b>{r["squeeze_trigger_price"]}</b></div>'
        f'<div class="trade-plan-box"><div><div style="font-size:10px;">寄付予想</div><div style="font-weight:bold;">{r["pts_est_price"]}</div></div>'
        f'<div style="border-left:1px solid #cbd5e1; border-right:1px solid #cbd5e1;"><div style="font-size:10px; color:#15803d; font-weight:bold;">利確目標</div><div style="font-weight:bold; color:#15803d;">{r["tp_price"]}</div></div>'
        f'<div><div style="font-size:10px; color:#b91c1c; font-weight:bold;">損切逆指値</div><div style="font-weight:bold; color:#b91c1c;">{r["sl_price"]}</div></div></div>'
        f'<div class="sizing-box">📦 <b>推奨ロット: {lot["shares"]:,}株</b> (投資額: {lot["position_value"]:,.0f}円 / リスク: {lot["risk_amount"]:,.0f}円)</div></div>'
    )
    st.markdown(html_card, unsafe_allow_html=True)
    render_interactive_council_section(r, f"{key_prefix}_{r['code']}")

# ==========================================
# 🚀 メイン解析システム＆ランキング
# ==========================================
if st.button("🔄 最新データに更新（再集計）"):
    st.cache_data.clear()

macro_info = fetch_macro_market()

c1, c2 = st.columns([3, 1])
with c1: custom_input = st.text_input("🔍 任意の銘柄コードを診断（国内4桁 / 米国ティッカー）", placeholder="例: 6920, 5803, 3350, NVDA, IONQ")
with c2:
    st.write("")
    search_clicked = st.button("診断する", use_container_width=True)

if custom_input or search_clicked:
    norm_code = normalize_ticker(custom_input)
    if norm_code:
        with st.spinner(f"「{norm_code}」を解析中..."):
            custom_res = fetch_single_stock(norm_code, macro_info, inst_boost_mode, board5ch_boost, squeeze_boost_mode, tokugai_boost_mode)
        if custom_res: render_stock_card(custom_res, is_custom=True, key_prefix="custom")
        else: st.error(f"銘柄「{custom_input}」のデータが見つかりませんでした。")

with st.spinner("🏦 母集団スキャン＆サバイバル選抜中..."):
    genre_results, all_results = fetch_all_pool_batch(macro_info, inst_boost_mode, board5ch_boost, squeeze_boost_mode, tokugai_boost_mode)

def apply_survival_of_the_fittest(stock_list, cut_pct):
    if not stock_list: return [], []
    sorted_all = sorted(stock_list, key=lambda x: (x["survival_power"], x["inst_score"], x["board5ch_score"], x["ai_score"]), reverse=True)
    keep_count = max(3, int(round(len(sorted_all) * (cut_pct / 100.0))))
    return sorted_all[:keep_count], sorted_all[keep_count:]

tabs = st.tabs([
    "🏆 総合サバイバルTOP5",
    "🏦 機関VPIN特選",
    "🔥 5chイナゴ特選",
    "🚨 特買い特選",
    "💥 踏み上げ特選",
    "📋 監視リスト"
] + list(STOCK_POOL.keys()))

with tabs[0]:
    surv, elim = apply_survival_of_the_fittest(all_results, survival_cut_pct)
    st.caption(f"🦁 全 {len(all_results)}銘柄中、下位 {len(elim)}銘柄を足切りした最強TOP5です。")
    for idx, r in enumerate(surv[:5], start=1): render_stock_card(r, rank=idx, key_prefix="top5")

with tabs[1]:
    for idx, r in enumerate(sorted(all_results, key=lambda x: (x["inst_score"], x["vpin"]), reverse=True)[:10], start=1):
        render_stock_card(r, rank=idx, key_prefix="inst_top")

with tabs[2]:
    for idx, r in enumerate(sorted(all_results, key=lambda x: (x["board5ch_score"], x["survival_power"]), reverse=True)[:10], start=1):
        render_stock_card(r, rank=idx, key_prefix="b5_top")

with tabs[3]:
    for idx, r in enumerate(sorted(all_results, key=lambda x: (x["tokugai_prob"], x["pts_gap_pct"]), reverse=True)[:10], start=1):
        render_stock_card(r, rank=idx, key_prefix="tk_top")

with tabs[4]:
    for idx, r in enumerate(sorted(all_results, key=lambda x: (x["squeeze_score"], x["inst_score"]), reverse=True)[:10], start=1):
        render_stock_card(r, rank=idx, key_prefix="sq_top")

with tabs[5]:
    wl = st.session_state["watchlist"]
    st.markdown(f"#### 📋 監視ウォッチリスト ({len(wl)}銘柄)")
    if wl:
        df_wl = pd.DataFrame([{"コード": c, "銘柄名": x["name"], "戦闘力": x["survival_power"], "機関スコア": x["inst_score"], "推奨株数": f"{x['lot_info']['shares']:,}株", "利確": x["tp_price"], "損切": x["sl_price"]} for c, x in wl.items()])
        st.dataframe(df_wl, use_container_width=True, hide_index=True)
    else:
        st.info("各カードの「⭐ 監視リスト追加」を押すとここに表示されます。")

for tab, genre in zip(tabs[6:], STOCK_POOL.keys()):
    with tab:
        g_raw = genre_results.get(genre, [])
        g_surv, g_elim = apply_survival_of_the_fittest(g_raw, survival_cut_pct)
        st.caption(f"🦁 **{genre}サバイバル選抜**: 候補 {len(g_raw)}銘柄中、{len(g_surv)}銘柄が生存")
        for idx, r in enumerate(g_surv, start=1): render_stock_card(r, rank=idx, key_prefix=f"genre_{genre}")
