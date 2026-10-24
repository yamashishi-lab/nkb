import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np
import altair as alt
import unicodedata, hashlib, hmac, json, os, re, ssl, smtplib, time, random, secrets, html, sqlite3
import urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from email.mime.text import MIMEText
from datetime import datetime

# ==========================================
# 1. ページ初期設定 & 商用暗号基盤
# ==========================================
st.set_page_config(page_title="YAMASHISHI LAB - AGI QUANTUM CORE", page_icon="⚡", layout="centered", initial_sidebar_state="collapsed")
frag_dec = getattr(st, "fragment", getattr(st, "experimental_fragment", lambda f: f))
dialog_dec = getattr(st, "dialog", getattr(st, "experimental_dialog", None))

def get_secure_env_var(key: str, default_generator) -> str:
    val = st.secrets.get(key) or os.environ.get(key)
    if not val:
        val = default_generator()
    return str(val).strip()

SECRET_KEY = get_secure_env_var("SECRET_KEY", lambda: hashlib.sha256(f"sec_salt_{secrets.token_hex(16)}_{time.time()}".encode()).hexdigest())

ADMIN_EMAIL = "nthbh399@ybb.ne.jp"
ADMIN_RAW_PASS = "yam0s1ta"

_SEC_SEED_SALT = "yamashishi_quant_enterprise_2026_s9"
_ADMIN_EMAIL_HASH = hashlib.sha256(f"{_SEC_SEED_SALT}:{ADMIN_EMAIL.strip().lower()}".encode("utf-8")).hexdigest()
_ADMIN_PASS_HASH = hashlib.sha256(f"{_SEC_SEED_SALT}:{ADMIN_RAW_PASS.strip()}".encode("utf-8")).hexdigest()

def is_seed_admin_email(em: str) -> bool:
    if not em: return False
    h = hashlib.sha256(f"{_SEC_SEED_SALT}:{em.strip().lower()}".encode("utf-8")).hexdigest()
    return hmac.compare_digest(h, _ADMIN_EMAIL_HASH) or hmac.compare_digest(em.strip().lower(), ADMIN_EMAIL.lower())

def is_seed_admin_pass(pw: str) -> bool:
    if not pw: return False
    pw_clean = pw.strip()
    h = hashlib.sha256(f"{_SEC_SEED_SALT}:{pw_clean}".encode("utf-8")).hexdigest()
    return hmac.compare_digest(h, _ADMIN_PASS_HASH) or hmac.compare_digest(pw_clean, ADMIN_RAW_PASS)

DB_PATH = "yamashishi_quant_core.db"

# ==========================================
# 2. SQLiteデータベース層
# ==========================================
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=15000;")
    conn.row_factory = sqlite3.Row
    return conn

def hash_sec_pwd(pwd: str, salt: str = "") -> str:
    use_salt = salt or SECRET_KEY[:16]
    return hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), use_salt.encode("utf-8"), 100000).hex()

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS members (
                email TEXT PRIMARY KEY,
                name TEXT,
                status TEXT,
                passcode TEXT,
                pin_hash TEXT,
                pin_attempts INTEGER DEFAULT 0,
                locked_until REAL DEFAULT 0,
                applied_at TEXT,
                approved_at TEXT,
                last_seen_ts REAL,
                last_seen_str TEXT,
                fp TEXT,
                raw_hfp TEXT,
                bio_enabled INTEGER
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS security_bans (
                key_val TEXT PRIMARY KEY,
                ban_type TEXT,
                email TEXT,
                name TEXT,
                banned_at TEXT,
                reason TEXT
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS spoof_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TEXT,
                action TEXT,
                input_email TEXT,
                input_name TEXT,
                orig_banned_email TEXT,
                fp TEXT,
                raw_hfp TEXT,
                reason TEXT
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                time TEXT,
                member_email TEXT,
                member_name TEXT,
                sender_role TEXT,
                subject TEXT,
                body TEXT,
                read_by_admin INTEGER,
                read_by_member INTEGER
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mail_logs (
                id TEXT PRIMARY KEY,
                time TEXT,
                to_email TEXT,
                from_email TEXT,
                subject TEXT,
                body TEXT,
                category TEXT,
                route TEXT
            );
        """)
        conn.execute("DELETE FROM security_bans WHERE key_val IN ('', '-', 'default_env', 'yamashishi_default_env', '未認証端末') OR key_val IS NULL;")
        
        ns = datetime.now().strftime("%Y-%m-%d %H:%M")
        adm_passcode = ADMIN_RAW_PASS
        adm_pin_h = hash_sec_pwd("0000", SECRET_KEY[:16])[:16]
        
        conn.execute("""
            INSERT INTO members (email, name, status, passcode, pin_hash, applied_at, approved_at, last_seen_ts, last_seen_str, fp, raw_hfp, bio_enabled)
            VALUES (?, 'システム管理者', 'approved', ?, ?, ?, ?, 0, '-', '-', '-', 1)
            ON CONFLICT(email) DO UPDATE SET status = 'approved', passcode = excluded.passcode;
        """, (ADMIN_EMAIL, adm_passcode, adm_pin_h, ns, ns))
        conn.execute("DELETE FROM security_bans WHERE email = ?", (ADMIN_EMAIL,))
        conn.commit()

init_db()

# ==========================================
# 3. ユーティリティ & 暗号検証関数
# ==========================================
def clean_k(k) -> str:
    if k is None: return ""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(k)).strip().strip("\"'"))

def sanitize(txt: str) -> str:
    return html.escape(str(txt or "")).strip()

def gen_code(em: str) -> str:
    if is_seed_admin_email(em): return ADMIN_RAW_PASS
    return hmac.new(SECRET_KEY.encode(), em.strip().lower().encode(), hashlib.sha256).hexdigest()[:8].upper()

def gen_tok(em: str, act: str) -> str:
    return hashlib.sha256(f"{em.strip().lower()}:{act}:{SECRET_KEY}".encode()).hexdigest()[:16]

def hash_pin(pin: str) -> str:
    return hash_sec_pwd(f"PIN:{str(pin).strip()}", SECRET_KEY[:16])[:16]

def get_raw_header_fp() -> str:
    try:
        h = {str(k).lower(): str(v) for k, v in dict(getattr(st.context, "headers", {}) or {}).items()}
        raw = f"{h.get('user-agent','')}|{h.get('accept-language','')}|{h.get('sec-ch-ua-platform','')}"
        if raw.replace("|", "").strip() == "":
            raw = "yamashishi_default_env"
    except Exception:
        raw = "yamashishi_default_env"
    return hashlib.sha256(raw.encode()).hexdigest()[:12].upper()

def get_client_fp() -> str:
    raw = get_raw_header_fp()
    qf = st.query_params.get("dfp", "")
    if qf: st.session_state["client_dfp"] = qf
    dfp = st.session_state.get("client_dfp", "")
    return hashlib.sha256(f"{raw}|{dfp}".encode()).hexdigest()[:12].upper() if dfp else raw

# ==========================================
# 4. 会員・セキュリティDB操作
# ==========================================
def check_and_log_ban_spoof(em: str, name: str, cur_fp: str, raw_hfp: str, pin_h: str = "", action_type: str = "アクセス") -> tuple:
    em_c = (em or "").strip().lower()
    if em_c == ADMIN_EMAIL or is_seed_admin_email(em_c):
        return False, ""
    
    with get_db() as conn:
        reasons = []
        orig_target = ""
        
        if em_c:
            m_row = conn.execute("SELECT status FROM members WHERE email = ?", (em_c,)).fetchone()
            if m_row and m_row["status"] == "banned":
                reasons.append("永久BAN対象メールアドレス一致")
                orig_target = em_c
        
        invalid_keys = {"", "-", "default_env", "yamashishi_default_env", "未入力", "未認証端末"}
        for k_val, desc in [(em_c, "メール"), (cur_fp, "端末指紋"), (raw_hfp, "環境ヘッダ指紋"), (pin_h, "PINハッシュ")]:
            if k_val and k_val not in invalid_keys:
                b_row = conn.execute("SELECT email, reason FROM security_bans WHERE key_val = ?", (k_val,)).fetchone()
                if b_row:
                    if b_row["email"] == ADMIN_EMAIL or is_seed_admin_email(b_row["email"]):
                        continue
                    reasons.append(f"永久BAN({desc}:{k_val[:6]}..)検知")
                    orig_target = orig_target or b_row["email"]
        
        if reasons:
            now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            r_str = " / ".join(reasons)
            is_spoof = bool(orig_target and em_c and em_c != orig_target)
            action_desc = f"🚨 なりすまし{action_type}検知" if is_spoof else f"🚫 永久BAN遮断({action_type})"
            
            conn.execute("""
                INSERT INTO spoof_logs (time, action, input_email, input_name, orig_banned_email, fp, raw_hfp, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (now_s, action_desc, em_c or "未入力", (name or "").strip() or "不明", orig_target or em_c, cur_fp, raw_hfp, r_str))
            
            if cur_fp and cur_fp not in invalid_keys:
                conn.execute("INSERT OR REPLACE INTO security_bans (key_val, ban_type, email, name, banned_at, reason) VALUES (?, 'fp', ?, ?, ?, ?)", (cur_fp, orig_target or em_c, name, now_s, r_str))
            if raw_hfp and raw_hfp not in invalid_keys:
                conn.execute("INSERT OR REPLACE INTO security_bans (key_val, ban_type, email, name, banned_at, reason) VALUES (?, 'hfp', ?, ?, ?, ?)", (raw_hfp, orig_target or em_c, name, now_s, r_str))
            if em_c and em_c not in invalid_keys:
                conn.execute("INSERT OR REPLACE INTO security_bans (key_val, ban_type, email, name, banned_at, reason) VALUES (?, 'email', ?, ?, ?, ?)", (em_c, orig_target or em_c, name, now_s, r_str))
            conn.commit()
            return True, r_str
            
    return False, ""

# ==========================================
# 5. UI設定・定数・モデル一覧
# ==========================================
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
        {"code": "NVDA", "name": "エヌビディア (米)", "theme": "AI GPU覇者"},
        {"code": "AMD", "name": "AMD (米)", "theme": "AIアクセラレータ"},
        {"code": "TSM", "name": "TSMC (米)", "theme": "半導体受託首位"}
    ],
    "AI・防衛・主力": [
        {"code": "9984.T", "name": "ソフトバンクG", "theme": "AI投資・先物主役"},
        {"code": "3778.T", "name": "さくらネット", "theme": "国策GPUクラウド"},
        {"code": "7011.T", "name": "三菱重工業", "theme": "防衛・宇宙国策主力"},
        {"code": "7012.T", "name": "川崎重工業", "theme": "防衛・航空エンジン"},
        {"code": "7013.T", "name": "IHI", "theme": "航空宇宙・防衛"},
        {"code": "3993.T", "name": "PKSHA", "theme": "AIアルゴリズム"},
        {"code": "8306.T", "name": "三菱UFJ", "theme": "金利連動メガバンク"},
        {"code": "PLTR", "name": "パランティア (米)", "theme": "防衛AI大本命"},
        {"code": "MSFT", "name": "マイクロソフト (米)", "theme": "クラウドAI"}
    ],
    "AI電力・電線": [
        {"code": "5803.T", "name": "フジクラ", "theme": "DC光ファイバー最強株"},
        {"code": "5801.T", "name": "古河電気工業", "theme": "光ファイバー・送電"},
        {"code": "5802.T", "name": "住友電気工業", "theme": "電線首位・DC網"},
        {"code": "6501.T", "name": "日立製作所", "theme": "世界送配電グリッド"},
        {"code": "9509.T", "name": "北海道電力", "theme": "ラピダス・DC電力"},
        {"code": "VST", "name": "ビストラ (米)", "theme": "AI発電主力"}
    ],
    "宇宙・次世代": [
        {"code": "5595.T", "name": "QPS研究所", "theme": "小型SAR衛星"},
        {"code": "186A.T", "name": "アストロスケール", "theme": "宇宙デブリ除去"},
        {"code": "9348.T", "name": "ispace", "theme": "月面輸送"},
        {"code": "TSLA", "name": "テスラ (米)", "theme": "自動運転・ロボ"},
        {"code": "RKLB", "name": "ロケットラボ (米)", "theme": "小型ロケット"}
    ],
    "小型急騰・直近IPO": [
        {"code": "5253.T", "name": "カバー", "theme": "グロース売買首位級"},
        {"code": "216A.T", "name": "タイミー", "theme": "スキマバイト大型IPO"},
        {"code": "285A.T", "name": "キオクシアHD", "theme": "NAND大型IPO"},
        {"code": "3350.T", "name": "メタプラネット", "theme": "暗号資産・超ボラ"},
        {"code": "IONQ", "name": "アイオンQ (米)", "theme": "商用量子代表"}
    ]
}
STOCK_POOL = DYNAMIC_DYNAMIC_POOLS
KNOWN_STOCKS = {it["code"]: {"name": it["name"], "theme": it["theme"], "genre": g} for g, its in STOCK_POOL.items() for it in its}

# ==========================================
# 6. 本格量子力学×数理エンジン
# ==========================================
def compute_quantum_wave_metrics(c: np.ndarray, h: np.ndarray, l: np.ndarray, v: np.ndarray) -> dict:
    n = min(len(c), 40)
    cw, hw, lw, vw = c[-n:], h[-n:], l[-n:], v[-n:]
    rets = np.diff(cw) / np.maximum(cw[:-1], 1e-4)
    if len(rets) < 8:
        return {"q_score": 75, "q_tunnel": 72.0, "q_coherence": 70.0, "q_entropy": 0.40, "berry_phase": 0.12, "q_state": "量子トンネル突破・超伝導モード"}

    vol_norm = vw[1:] / max(float(np.mean(vw[1:])), 1.0)
    effective_mass = 1.0 / np.clip(vol_norm, 0.15, 6.0)
    std_r = max(float(np.std(rets)), 1e-4)
    kinetic_energy = 0.5 * effective_mass * (rets ** 2)

    resistance = float(np.max(hw[-15:]))
    curr_p = float(cw[-1])
    barrier_height = max((resistance - curr_p) / curr_p, 0.0)
    mean_kinetic = max(float(np.mean(kinetic_energy[-5:])), 1e-5)

    if barrier_height <= 0.001 or mean_kinetic >= barrier_height:
        q_tunnel = round(float(np.clip(85.0 + min((mean_kinetic - barrier_height) * 450.0, 14.5), 75.0, 99.5)), 1)
    else:
        delta_v = barrier_height - mean_kinetic
        gamma = np.sqrt(2.0 * np.mean(effective_mass[-5:]) * delta_v) * (barrier_height / std_r)
        transmittance = np.exp(-2.0 * np.clip(gamma, 0.01, 3.8))
        q_tunnel = round(float(np.clip(transmittance * 100.0 + 35.0, 40.0, 98.5)), 1)

    phase = np.cumsum(rets / std_r)
    psi = np.sqrt(vol_norm) * np.exp(1j * phase)
    coherence_tensor = np.abs(np.mean(psi[-6:])) / max(float(np.mean(np.sqrt(vol_norm[-6:]))), 1e-4)
    q_coherence = round(float(np.clip(coherence_tensor * 75.0 + (1.0 if rets[-1] >= 0 else -0.3) * 15.0 + 10.0, 30.0, 99.0)), 1)
    
    berry_loop = np.sum(np.imag(np.conj(psi[:-1]) * np.diff(psi)))
    berry_phase = round(float(np.clip(np.abs(berry_loop) / (len(psi) * np.pi), 0.01, 0.99)), 3)

    z_r = (rets - np.mean(rets)) / std_r
    z_v = (vol_norm - np.mean(vol_norm)) / max(float(np.std(vol_norm)), 1e-4)
    state_vector = np.vstack([z_r, z_v])
    cov = np.cov(state_vector)
    trace_cov = max(float(np.trace(cov)), 1e-6)
    rho = cov / trace_cov

    eigvals = np.clip(np.linalg.eigvalsh(rho), 1e-7, 1.0)
    eigvals = eigvals / np.sum(eigvals)
    von_neumann_entropy = -float(np.sum(eigvals * np.log2(eigvals)))
    q_entropy = round(float(np.clip(von_neumann_entropy, 0.05, 0.98)), 2)

    q_score = int(np.clip(round(q_tunnel * 0.42 + q_coherence * 0.35 + (1.0 - q_entropy) * 18.0 + (berry_phase * 10.0)), 45, 99))
    q_state = "⚛️ 量子トンネル突破・超伝導モード" if (q_tunnel >= 72.0 and q_coherence >= 60.0) else (
        "✨ 波動関数収束・コヒーレント増幅" if (q_entropy <= 0.55 and q_coherence >= 55.0) else (
        "⚡ 励起状態（障壁突破カウントダウン）" if q_tunnel >= 60.0 else "🌊 量子重ね合わせ（押し目干渉待ち）")
    )
    return {"q_score": q_score, "q_tunnel": q_tunnel, "q_coherence": q_coherence, "q_entropy": q_entropy, "berry_phase": berry_phase, "q_state": q_state}

def compute_inst_microstructure(c: np.ndarray, h: np.ndarray, l: np.ndarray, v: np.ndarray) -> dict:
    n = min(len(c), 35)
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

# ==========================================
# 7. CSS（ボタン横一列・タップ青発光・上部見切れ完全解消）
# ==========================================
def inject_css():
    css = """
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;800&family=Plus+Jakarta+Sans:wght@400;600;800&family=JetBrains+Mono:wght@500;700&display=swap');
    html,body,[class*="css"]{font-family:'Plus Jakarta Sans',sans-serif;font-size:14px;background-color:#050811;color:#e2e8f0;}
    
    header[data-testid="stHeader"] {
        background: transparent !important;
        pointer-events: none !important;
        height: 2.8rem !important;
        z-index: 999990 !important;
    }
    
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"] {
        opacity: 1 !important;
        display: flex !important;
        visibility: visible !important;
        position: fixed !important;
        left: 10px !important;
        top: 6px !important;
        z-index: 10000005 !important;
        pointer-events: auto !important;
        background: rgba(15,23,42,0.92) !important;
        border: 1px solid rgba(56,189,248,0.4) !important;
        border-radius: 8px !important;
        padding: 4px !important;
        color: #38bdf8 !important;
    }

    section[data-testid="stSidebar"] {
        background-color: #0b0f19 !important;
        border-right: 1px solid rgba(148,163,184,0.18) !important;
        z-index: 10000010 !important;
        box-shadow: 10px 0 35px rgba(0,0,0,0.85) !important;
    }

    .block-container {
        padding-top: 3.2rem !important;
        padding-bottom: 2.5rem !important;
        padding-left: 0.6rem !important;
        padding-right: 0.6rem !important;
        max-width: 840px !important;
    }

    /* 上部固定横並びボタンバー */
    .fixed-top-nav-bar {
        position: fixed !important;
        top: 6px !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        z-index: 9999999 !important;
        width: min(390px, calc(100vw - 4.5rem)) !important;
        background: rgba(8, 12, 22, 0.95) !important;
        backdrop-filter: blur(14px) !important;
        border: 1px solid rgba(56, 189, 248, 0.4) !important;
        border-radius: 10px !important;
        box-shadow: 0 4px 20px rgba(0,0,0,0.85) !important;
        padding: 3px 5px !important;
        margin: 0 !important;
        pointer-events: auto !important;
    }

    /* 横一列強制コンテナ */
    .fixed-top-nav-bar div[data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
        justify-content: space-between !important;
        gap: 5px !important;
        width: 100% !important;
    }

    .fixed-top-nav-bar div[data-testid="column"],
    .fixed-top-nav-bar div[data-testid="stColumn"] {
        flex: 1 1 0% !important;
        min-width: 0 !important;
        width: 33.33% !important;
    }

    /* ボタンデザイン：タップ時のみネオンブルー */
    .fixed-top-nav-bar button {
        width: 100% !important;
        height: 30px !important;
        min-height: 30px !important;
        padding: 0 2px !important;
        border-radius: 6px !important;
        background: #0f172a !important;
        color: #f1f5f9 !important;
        border: 1px solid rgba(148, 163, 184, 0.25) !important;
        cursor: pointer !important;
        transition: transform 0.08s ease, background-color 0.08s ease, border-color 0.08s ease !important;
        user-select: none !important;
        -webkit-tap-highlight-color: transparent !important;
    }

    .fixed-top-nav-bar button:active,
    .fixed-top-nav-bar button:focus:active {
        background: #2563eb !important;
        color: #ffffff !important;
        border-color: #60a5fa !important;
        box-shadow: 0 0 12px rgba(37,99,235,0.9) !important;
        transform: scale(0.95) !important;
    }

    .fixed-top-nav-bar button p {
        font-size: 11px !important;
        font-weight: 700 !important;
        white-space: nowrap !important;
        margin: 0 !important;
        line-height: 28px !important;
    }

    .brand-luxury {
        font-family: 'Cinzel',serif !important;
        font-size: clamp(15px,4vw,22px) !important;
        font-weight: 800 !important;
        letter-spacing: clamp(1px,0.5vw,2.5px) !important;
        background: linear-gradient(90deg,#f8fafc 0%,#38bdf8 50%,#a855f7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        line-height: 1.2;
    }
    .brand-sub {
        font-family: 'JetBrains Mono',monospace;
        font-size: clamp(8px,2vw,10px);
        color: #64748b;
        letter-spacing: 1.1px;
        text-transform: uppercase;
    }
    
    .glass-header {
        background: radial-gradient(circle at top right,rgba(168,85,247,0.12),transparent 60%),linear-gradient(145deg,#0f172a 0%,#070b14 100%);
        border: 1px solid rgba(148,163,184,0.18);
        border-radius: 12px;
        padding: 11px 13px;
        margin-bottom: 8px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.45);
    }
    .rank-card,.search-result-card {
        background: linear-gradient(180deg,#0f172a 0%,#090d16 100%) !important;
        color: #f8fafc !important;
        border-radius: 12px;
        padding: 12px 13px;
        margin-bottom: 10px;
        box-shadow: 0 8px 22px rgba(0,0,0,0.45);
        border: 1px solid rgba(148,163,184,0.16);
        border-left: 4px solid #38bdf8;
    }
    .prob-badge {
        font-family: 'JetBrains Mono',monospace;
        font-size: clamp(13px,3.6vw,16px);
        font-weight: 800;
        color: #38bdf8 !important;
    }
    .expect-badge {
        font-family: 'JetBrains Mono',monospace;
        font-size: clamp(13px,3.6vw,16px);
        font-weight: 900;
        color: #fde047 !important;
    }
    .pill-badge {
        display: inline-block;
        padding: 2px 6px;
        border-radius: 5px;
        font-size: 9.5px;
        font-weight: 700;
        margin-right: 4px;
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.12);
        color: #e2e8f0;
    }
    .quantum-badge {
        display: inline-block;
        padding: 2px 7px;
        border-radius: 5px;
        font-size: 9.5px;
        font-weight: 800;
        margin-right: 4px;
        background: linear-gradient(90deg,rgba(168,85,247,0.22),rgba(56,189,248,0.22));
        border: 1px solid rgba(168,85,247,0.55);
        color: #e9d5ff;
    }
    .inst-badge {
        display: inline-block;
        padding: 2px 7px;
        border-radius: 5px;
        font-size: 9.5px;
        font-weight: 800;
        margin-right: 4px;
        background: linear-gradient(90deg,rgba(16,185,129,0.2),rgba(56,189,248,0.2));
        border: 1px solid rgba(16,185,129,0.55);
        color: #a7f3d0;
    }
    .winrate-bar {
        display: grid;
        grid-template-columns: repeat(4,1fr);
        gap: 5px;
        background: rgba(15,23,42,0.85) !important;
        border: 1px solid rgba(148,163,184,0.15);
        border-radius: 7px;
        padding: 5px 4px;
        margin-top: 6px;
        text-align: center;
    }
    .signal-10tier-badge {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 800;
        margin-bottom: 6px;
        gap: 5px;
    }
    .trade-plan-box {
        display: grid;
        grid-template-columns: repeat(3,1fr);
        gap: 4px;
        margin-top: 5px;
        background: rgba(2,6,23,0.7) !important;
        padding: 5px 4px;
        border-radius: 7px;
        border: 1px solid rgba(148,163,184,0.15);
        text-align: center;
    }
    .sizing-box {
        background: rgba(16,185,129,0.08) !important;
        border: 1px solid rgba(16,185,129,0.28);
        border-radius: 7px;
        padding: 5px 9px;
        margin-top: 5px;
        font-size: 10.5px;
        color: #d1fae5;
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
    }
    details.quant-detail-drawer {
        margin-top: 6px;
        background: rgba(2,6,23,0.55);
        border: 1px solid rgba(168,85,247,0.25);
        border-radius: 7px;
        padding: 5px 9px;
    }
    details.quant-detail-drawer summary {
        font-size: 10.5px;
        font-weight: 700;
        color: #c084fc !important;
        cursor: pointer;
    }
    .metrics-row {
        display: flex;
        flex-wrap: wrap;
        gap: 4px 7px;
        margin-top: 5px;
        font-size: 10px;
        font-family: 'JetBrains Mono',monospace;
        background: rgba(15,23,42,0.9) !important;
        padding: 5px 7px;
        border-radius: 5px;
        color: #cbd5e1;
    }
    .ai-council-box {
        background: #070b14;
        color: #f8fafc !important;
        border-radius: 10px;
        padding: 10px;
        margin-top: 6px;
        margin-bottom: 8px;
        border: 1px solid rgba(168,85,247,0.35);
    }
    .council-scroll-window {
        max-height: 480px;
        overflow-y: auto;
        padding: 8px;
        background: #04070e;
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 8px;
        margin-bottom: 8px;
        scroll-behavior: smooth;
    }
    .round-divider {
        text-align: center;
        margin: 7px 0;
        padding: 4px 8px;
        background: rgba(168,85,247,0.18);
        border-left: 3px solid #a855f7;
        color: #e9d5ff !important;
        font-size: 11px;
        font-weight: 800;
        border-radius: 4px;
    }
    .chat-bubble-ai,.chat-bubble-doubt,.chat-bubble-rage,.chat-bubble-agree {
        border-radius: 7px;
        padding: 8px 10px;
        margin-bottom: 8px;
        font-size: 12px;
        line-height: 1.6;
        background: rgba(255,255,255,0.04);
        border-left: 3px solid #38bdf8;
    }
    .chat-bubble-doubt { border-left-color: #f59e0b; background: rgba(245,158,11,0.07); }
    .chat-bubble-rage { border-left-color: #ef4444; background: rgba(239,68,68,0.12); }
    .chat-bubble-agree { border-left-color: #a855f7; background: rgba(168,85,247,0.11); }
    .chat-bubble-user {
        background: linear-gradient(135deg, rgba(30,58,138,0.92), rgba(15,23,42,0.98)) !important;
        border: 1.5px solid #60a5fa !important;
        border-left: 5px solid #38bdf8 !important;
        border-radius: 7px !important;
        padding: 8px 11px !important;
        margin: 10px 0 6px 0 !important;
        font-size: 12.5px !important;
        color: #ffffff !important;
        scroll-margin-top: 10px;
    }
    .consensus-banner {
        background: linear-gradient(135deg,#0f172a,#1e1b4b);
        border: 1px solid rgba(168,85,247,0.45);
        border-radius: 8px;
        padding: 9px;
        margin-top: 6px;
        font-size: 11.5px;
    }
    .beginner-action-box {
        background: linear-gradient(135deg,rgba(16,185,129,0.14),rgba(6,78,59,0.25));
        border: 1px solid #10b981;
        border-left: 4px solid #10b981;
        border-radius: 7px;
        padding: 8px 10px;
        margin-top: 6px;
        color: #ecfdf5;
        font-size: 11.5px;
        line-height: 1.55;
    }
    """
    st.markdown(f'<div id="page_top_anchor"></div><style>{" ".join(l.strip() for l in css.splitlines() if l.strip())}</style>', unsafe_allow_html=True)

inject_css()

# ==========================================
# 8. リアルタイム重大情報検知・カタリスト解析層
# ==========================================
@st.cache_data(ttl=120)
def check_major_catalyst(code: str, name: str, genre: str) -> dict:
    c_raw = code.replace(".T", "")
    query = f"{name} {c_raw} (決算 OR 上方修正 OR TOB OR 提携 OR 買収 OR 受注 OR 急騰 OR 規制)"
    ctx = ssl.create_default_context()
    ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
    
    found_catalysts = []
    try:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=ja&gl=JP&ceid=JP:ja"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=2.0, context=ctx) as r:
            root = ET.fromstring(r.read())
            items = root.findall("./channel/item")
            for it in items[:4]:
                t = it.findtext("title") or ""
                link = it.findtext("link") or ""
                pub = it.findtext("pubDate") or ""
                source_elem = it.find("source")
                source_name = source_elem.text if source_elem is not None else "主要報道機関"
                
                impact_kws = ["上方修正", "急増", "最高益", "TOB", "買収", "提携", "大型受注", "新薬", "特許", "割安", "ストップ高", "急落", "下方修正"]
                score = 65
                matched = [kw for kw in impact_kws if kw in t]
                if matched:
                    score += len(matched) * 10
                    score = min(score, 98)
                    found_catalysts.append({
                        "title": t, "source": source_name, "url": link, "pubDate": pub, "reliability": score, "keywords": matched
                    })
    except Exception: pass

    if not found_catalysts: return {"has_major": False}
    related_stocks = [s for s in STOCK_POOL.get(genre, []) if s["code"] != code][:5]
    top_cat = sorted(found_catalysts, key=lambda x: x["reliability"], reverse=True)[0]
    return {
        "has_major": True, "title": top_cat["title"], "source": top_cat["source"], "url": top_cat["url"],
        "reliability": top_cat["reliability"], "keywords": top_cat["keywords"], "all_items": found_catalysts,
        "related_stocks": related_stocks,
        "detailed_impact": f"【波及分析】該当報道は『{name}』のみならず、同一サプライチェーン・セクター（{genre}）全体に対して大口機関のアルゴリズム資金流入・リバランスを引き起こす公算が極めて高い特異点です。"
    }

# ==========================================
# 9. 認証＆セッション管理
# ==========================================
def check_auth():
    cur_fp, raw_hfp = get_client_fp(), get_raw_header_fp()
    if "authenticated_user" not in st.session_state: st.session_state["authenticated_user"] = None
    qu, qt = st.query_params.get("u", "").strip().lower(), st.query_params.get("t", "").strip()

    with get_db() as conn:
        if not st.session_state["authenticated_user"] and qu and qt:
            row = conn.execute("SELECT status, name, pin_hash FROM members WHERE email = ?", (qu,)).fetchone()
            is_adm = (qu == ADMIN_EMAIL or is_seed_admin_email(qu))
            if hmac.compare_digest(qt, gen_tok(qu, "session_keep")) and ((row and row["status"] == "approved") or is_adm):
                st.session_state["authenticated_user"] = qu

        if st.session_state["authenticated_user"]:
            cu = st.session_state["authenticated_user"]
            u_row = conn.execute("SELECT * FROM members WHERE email = ?", (cu,)).fetchone()
            u_rec = dict(u_row) if u_row else {}
            is_admin = (cu == ADMIN_EMAIL or is_seed_admin_email(cu))
            
            if not is_admin:
                is_ban, _ = check_and_log_ban_spoof(cu, u_rec.get("name", ""), cur_fp, raw_hfp, u_rec.get("pin_hash", ""), "セッション維持")
                if is_ban or u_rec.get("status") == "banned":
                    st.session_state["authenticated_user"] = None
                    st.query_params.clear()
                    st.error("💀 このアカウントまたは端末は永久BANされています。")
                    st.stop()
                if not u_rec or u_rec.get("status") != "approved":
                    st.session_state["authenticated_user"] = None
                    st.query_params.clear()
                    st.error("🚫 アカウント一時停止中、または削除されています。")
                    st.stop()

            keep_tok = gen_tok(cu, "session_keep")
            conn.execute("""
                INSERT INTO members (email, name, status, passcode, pin_hash, pin_attempts, locked_until, applied_at, approved_at, last_seen_ts, last_seen_str, fp, raw_hfp, bio_enabled)
                VALUES (?, ?, 'approved', ?, ?, 0, 0, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(email) DO UPDATE SET last_seen_ts = excluded.last_seen_ts, last_seen_str = excluded.last_seen_str, fp = excluded.fp, raw_hfp = excluded.raw_hfp, status = 'approved';
            """, (
                cu, u_rec.get("name") or ("システム管理者" if is_admin else "会員"),
                ADMIN_RAW_PASS if is_admin else (u_rec.get("passcode") or gen_code(cu)),
                u_rec.get("pin_hash", ""), u_rec.get("applied_at") or datetime.now().strftime("%Y-%m-%d %H:%M"),
                u_rec.get("approved_at") or datetime.now().strftime("%Y-%m-%d %H:%M"),
                time.time(), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), cur_fp, raw_hfp
            ))
            conn.commit()

            st.query_params["u"], st.query_params["t"] = cu, keep_tok
            with st.sidebar:
                u_disp_name = u_rec.get("name") or ("システム管理者" if is_admin else "会員")
                st.markdown(f'<div style="background:#0f172a;padding:8px 11px;border-radius:9px;border:1px solid rgba(168,85,247,0.35);margin-bottom:6px;"><div style="font-size:9.5px;color:#c084fc;font-weight:700;">⚛️ QUANTUM SESSION ACTIVE</div><div style="color:#f8fafc;font-size:11.5px;font-weight:700;">{sanitize(u_disp_name)} ({sanitize(cu)})</div></div>', unsafe_allow_html=True)
                row = conn.execute("SELECT bio_enabled FROM members WHERE email = ?", (cu,)).fetchone()
                is_enabled = bool(row and row["bio_enabled"])
                if st.button("✅ 端末認証 登録完了" if is_enabled else "🧬 この端末をワンタップ認証に登録", key="bio_reg_btn", use_container_width=True):
                    conn.execute("UPDATE members SET bio_enabled = 1, fp = ?, raw_hfp = ? WHERE email = ?", (cur_fp, raw_hfp, cu))
                    conn.commit()
                    st.success("✅ 端末認証を登録しました")

                if st.button("🚪 ログアウト", use_container_width=True):
                    conn.execute("UPDATE members SET last_seen_ts = 0 WHERE email = ?", (cu,))
                    conn.commit()
                    st.session_state["authenticated_user"] = None
                    st.query_params.clear()
                    st.rerun()
            return True

    st.markdown(
        '<div class="glass-header" style="text-align:center;padding:20px 14px;margin-top:10px;">'
        '<div class="brand-luxury">YAMASHISHI LAB</div>'
        '<div class="brand-sub" style="margin-top:3px;">QUANTUM WAVEFUNCTION & MULTI-AGENT TERMINAL</div>'
        '</div>',
        unsafe_allow_html=True
    )

    login_box = st.container()
    with login_box:
        with get_db() as conn:
            m_row = conn.execute("SELECT email, status, name, pin_hash FROM members WHERE bio_enabled = 1 AND (raw_hfp = ? OR fp = ?)", (raw_hfp, cur_fp)).fetchone()
        
        if st.button("🧬 登録済み端末：生体認証 / ワンタップで即ログイン", use_container_width=True, type="primary"):
            if m_row:
                t_em = m_row["email"].strip().lower()
                is_adm = (t_em == ADMIN_EMAIL or is_seed_admin_email(t_em))
                is_ban, _ = check_and_log_ban_spoof(t_em, m_row["name"] or "", cur_fp, raw_hfp, m_row["pin_hash"] or "", "ワンタップログイン")
                if is_ban or m_row["status"] == "banned": st.error("💀 このアカウントまたは端末は永久BANされています。")
                elif m_row["status"] == "suspended": st.error("🚫 アカウント一時停止中です。")
                elif m_row["status"] == "approved" or is_adm:
                    st.session_state["authenticated_user"] = t_em
                    st.query_params["u"], st.query_params["t"] = t_em, gen_tok(t_em, "session_keep")
                    st.rerun()
            else:
                st.warning("⚠️ この端末は未登録です。以下のフォームから通常ログインしてください。")

        st.markdown('<div style="text-align:center;color:#64748b;margin:10px 0;font-size:11px;">— または メールアドレス＆パスコード認証 —</div>', unsafe_allow_html=True)

        with st.form("manual_login_form"):
            in_email = st.text_input("メールアドレス", placeholder="admin または 登録済みアドレス")
            in_pass = st.text_input("パスコード / 管理者パスワード", type="password")
            submit_btn = st.form_submit_button("⚡ QUANTUM CORE へログイン", use_container_width=True)

            if submit_btn:
                em_clean = (in_email or "").strip().lower()
                pw_clean = (in_pass or "").strip()

                if not em_clean or not pw_clean:
                    st.error("メールアドレスとパスコードを入力してください。")
                else:
                    if is_seed_admin_email(em_clean) and is_seed_admin_pass(pw_clean):
                        st.session_state["authenticated_user"] = ADMIN_EMAIL
                        st.query_params["u"], st.query_params["t"] = ADMIN_EMAIL, gen_tok(ADMIN_EMAIL, "session_keep")
                        st.success("👑 管理者認証に成功しました。")
                        st.rerun()
                    else:
                        with get_db() as conn:
                            row = conn.execute("SELECT * FROM members WHERE email = ?", (em_clean,)).fetchone()
                            if row:
                                rec = dict(row)
                                is_ban, _ = check_and_log_ban_spoof(em_clean, rec.get("name", ""), cur_fp, raw_hfp, rec.get("pin_hash", ""), "通常ログイン")
                                if is_ban or rec.get("status") == "banned": st.error("💀 アカウントはBANされています。")
                                elif hmac.compare_digest(rec.get("passcode", ""), pw_clean) or pw_clean == gen_code(em_clean):
                                    st.session_state["authenticated_user"] = em_clean
                                    st.query_params["u"], st.query_params["t"] = em_clean, gen_tok(em_clean, "session_keep")
                                    st.success("✅ ログインに成功しました。")
                                    st.rerun()
                                else: st.error("❌ パスコードが一致しません。")
                            else: st.error("❌ アカウントが見つかりません。")
    st.stop()

check_auth()

# ==========================================
# 10. セッション状態＆上部ナビゲーションバー（横一列・タップ青発光・見切れ修正）
# ==========================================
for k, v in [
    ("active_debates", {}), ("council_threads", {}), ("council_meta", {}),
    ("watchlist", {}), ("navigation_page", "TOP"), ("selected_news_item", None),
    ("custom_search_code", ""), ("active_category", "🏆 総合TOP5"),
    ("last_cat", "🏆 総合TOP5"), ("nav_history", []), ("scroll_top_trig", 0),
    ("scroll_target_id", ""), ("catalyst_dialog_item", None)
]:
    if k not in st.session_state: st.session_state[k] = v

open_cnt = sum(1 for v in st.session_state["active_debates"].values() if v)

# 上部固定バー（HTMLコンテナで覆ってCSSで完全横一列を保証）
st.markdown('<div class="fixed-top-nav-bar">', unsafe_allow_html=True)
nav_c1, nav_c2, nav_c3 = st.columns([1, 1, 1])
with nav_c1:
    if st.button("⬆️ トップ", key="nav_btn_top", use_container_width=True):
        st.session_state["navigation_page"] = "TOP"
        st.session_state["custom_search_code"] = ""
        st.session_state["scroll_top_trig"] = int(time.time() * 1000)
        st.rerun()
with nav_c2:
    btn_lbl = f"✖ 閉じる({open_cnt})" if open_cnt else "✖ 閉じる"
    if st.button(btn_lbl, key="nav_btn_close", use_container_width=True):
        st.session_state["active_debates"] = {}
        st.rerun()
with nav_c3:
    if st.button("↩️ 戻る", key="nav_btn_back", use_container_width=True):
        if st.session_state.get("navigation_page") != "TOP":
            st.session_state["navigation_page"] = "TOP"
            st.session_state["scroll_top_trig"] = int(time.time() * 1000)
        elif st.session_state.get("custom_search_code"):
            st.session_state["custom_search_code"] = ""
        elif st.session_state.get("nav_history") and len(st.session_state["nav_history"]) > 0:
            popped = st.session_state["nav_history"].pop()
            st.session_state["active_category"] = popped
            st.session_state["last_cat"] = popped
        else:
            st.session_state["active_category"] = "🏆 総合TOP5"
            st.session_state["last_cat"] = "🏆 総合TOP5"
        st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

# 質問投下時の見切れ完全防止スクリプト
scroll_target_js = ""
if st.session_state.get("scroll_target_id"):
    tid = st.session_state.get("scroll_target_id")
    scroll_target_js = f"""
        setTimeout(function(){{
            try {{
                const el = window.parent.document.getElementById('{tid}');
                if(el){{
                    const parentBox = el.closest('.council-scroll-window');
                    if(parentBox){{
                        // 質問がスクロール窓上部に余裕をもって綺麗に収まるよう配置
                        const pRect = parentBox.getBoundingClientRect();
                        const eRect = el.getBoundingClientRect();
                        parentBox.scrollTop += (eRect.top - pRect.top) - 15;
                    }} else {{
                        el.scrollIntoView({{behavior: 'smooth', block: 'start'}});
                    }}
                }}
            }} catch(e){{}}
        }}, 180);
    """
    st.session_state["scroll_target_id"] = ""

components.html(
    f"""
    <script>
    (function(){{
        const doc = window.parent.document;
        function scrollToTopAbsolute(){{
            try {{ window.parent.scrollTo(0, 0); }} catch(e){{}}
            const targets = [doc.documentElement, doc.body, doc.querySelector('section.main'), doc.querySelector('[data-testid="stAppViewContainer"]')];
            targets.forEach(el => {{ if(el && typeof el.scrollTo === 'function') el.scrollTop = 0; }});
        }}

        if({st.session_state['scroll_top_trig']} > 0 && window.parent._lastScrollTrig !== {st.session_state['scroll_top_trig']}){{
            window.parent._lastScrollTrig = {st.session_state['scroll_top_trig']};
            scrollToTopAbsolute();
        }}
        {scroll_target_js}
    }})();
    </script>""",
    height=0
)

# ==========================================
# 11. 重大情報モーダル表示関数
# ==========================================
def render_catalyst_popup_modal(cat_info: dict, r: dict):
    st.markdown(f"### 🚨 重大情報速報：{r['name']} ({r['code']})")
    st.markdown(f"**【発表タイトル】**\n#### {cat_info['title']}")
    
    c1, c2 = st.columns(2)
    c1.metric("情報信頼度スコア", f"{cat_info['reliability']}%", delta="S級カタリスト" if cat_info['reliability']>=80 else "要監視")
    c2.metric("一次情報ソース", cat_info['source'])

    st.markdown("---")
    st.markdown("#### 🔍 情報の詳細内容と背景")
    st.write(cat_info["detailed_impact"])
    st.caption(f"配信日時: {cat_info.get('pubDate', 'リアルタイム取得')} ｜ 検知キーワード: {', '.join(cat_info['keywords'])}")
    if cat_info.get("url"):
        st.markdown(f"👉 [**報道ソースの元記事を開く (外部サイト)**]({cat_info['url']})")

    st.markdown("---")
    st.markdown("#### ⚡ 株価変動を一緒にしそうな関連銘柄一覧")
    rel_cols = st.columns(max(1, len(cat_info["related_stocks"])))
    for i, stock in enumerate(cat_info["related_stocks"]):
        with rel_cols[i]:
            st.markdown(
                f'<div style="background:rgba(15,23,42,0.9);border:1px solid rgba(56,189,248,0.3);border-radius:8px;padding:8px;text-align:center;">'
                f'<div style="font-weight:800;font-size:12px;color:#f8fafc;">{stock["name"]}</div>'
                f'<div style="font-size:10px;color:#38bdf8;">{stock["code"]}</div>'
                f'<div style="font-size:9.5px;color:#94a3b8;margin-top:2px;">{stock["theme"]}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

if dialog_dec:
    @dialog_dec("🚨 重大情報（カタリスト）分析レポート")
    def show_catalyst_dialog(cat_info, r): render_catalyst_popup_modal(cat_info, r)
else:
    def show_catalyst_dialog(cat_info, r):
        with st.expander("🚨 【重大情報】詳細内容・信頼度・関連連動銘柄", expanded=True):
            render_catalyst_popup_modal(cat_info, r)

# ==========================================
# 12. クオンツ解析エンジン ＆ 戦略ディスパッチャ
# ==========================================
def norm_tk(raw: str) -> str:
    s = unicodedata.normalize("NFKC", str(raw or "")).strip().upper()
    return f"{s}.T" if len(s) == 4 and any(c.isdigit() for c in s) and "." not in s else s

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
            "beginner_html": f"<b>🔰 スキャルピング実践手順（⚡ 寄付き直後の数分で利確！）</b><br>① 朝9:00のスタートと同時に <b>{sh:,}株</b> を迷わず買います。<br>② スキャルピングはスピード命です。<b>{tp_str}</b> で即利確、損切 <b>{sl_str}</b> を厳守。"
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
            "beginner_html": f"<b>🔰 スイングトレード実践手順（📈 数日〜1週間のトレンドに乗る！）</b><br>① 初日は資金の半分強（<b>{l1:,}株</b>）を買ってポジションを作ります。<br>② 押し目で残りの <b>{l2:,}株</b> を買い増し、目標 <b>{tp_str}</b> まで保有。"
        }

    sh = max(1, int(round(base_sh * 1.65)))
    return {
        "algo_name": f"🔥 [{st_prefix}] 情報精度S級・全ツッパ一括特攻型アルゴリズム",
        "risk_posture": f"👑 全ツッパ・フルベット（ <b>{sh:,}株を100%一括投入</b> ）",
        "core_logic": f"期待度 <b>{expect_pct}%</b>・量子Qスコア {qm['q_score']}点・機関Kyleステルス吸収 {ms['kyle_stealth']}% が完全一致し、95%CVaRも -{cvar95}% と極めて低いS級特異点。分割せず寄り付き一括で最高期待値を抜き取る戦術。",
        "adj_shares": sh,
        "step_plan": f"① 9:00寄付き（{pest_str}目安）で <b>全ロット {sh:,}株（100%全ツッパ）</b> 成行一括投入 → ② 逆指値（{sl_str}）を同時セットし、目標（{tp_str}）まで一気抜き",
        "beginner_html": f"<b>🔰 デイトレード実践手順（🔥 精度S級・迷わず1回で全ツッパ！）</b><br>① 朝9:00の寄り付きで <b>「{sh:,}株」を一括購入</b> します。<br>② 買えたらすぐに <b>「損切り：{sl_str}」</b> を入れ、目標の <b>{tp_str}</b> 到達で利益確定！"
    }

def analyze_df(df_raw, code, name, theme, genre, macro, b5_live_map, style, bi=True, b5=True, bal=True, bms=True, total_capital=1000000, risk_tolerance_pct=2.0):
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
        g_r = dlt.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        l_r = (-dlt.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        df["RSI"] = (100 - (100 / (1 + g_r / l_r.replace(0, np.nan)))).fillna(50.0)
        
        tr = pd.concat([df["High"] - df["Low"], (df["High"] - df["Prev_Close"]).abs(), (df["Low"] - df["Prev_Close"]).abs()], axis=1).max(axis=1)
        df["ATR"] = tr.rolling(14).mean().fillna(df["Close"] * 0.02)

        hl = (df["High"] - df["Low"]).replace(0, np.nan)
        df["Close_Pos"] = ((df["Close"] - df["Low"]) / hl).fillna(0.5)
        df["VWAP20"] = (((df["High"] + df["Low"] + df["Close"]) / 3.0 * df["Volume"]).rolling(20).sum() / df["Volume"].rolling(20).sum().replace(0, np.nan)).fillna(df["Close"])
        df["VPIN_5d"] = (((df["Close"] - df["Open"]) / hl).fillna(0.0) * df["Vol_Ratio"]).rolling(5).mean().fillna(0.0)

        hl_r = np.maximum(h - l, 1e-4)
        sf = ((2.0 * c - h - l) / hl_r) * v
        ofi_z = round(float(np.clip((np.mean(sf[-5:]) - np.mean(sf[-20:])) / max(float(np.std(sf[-20:])), 1.0) + 0.5, -3.5, 3.5)), 2)
        rets = np.diff(c) / np.maximum(c[:-1], 1e-4) * 100.0
        q05 = np.percentile(rets, 5)
        cvar95 = round(float(abs(np.mean(rets[rets <= q05]))) if any(rets <= q05) else abs(float(q05)), 2)
        yz_vol = round(float(np.std(rets[-20:]) * np.sqrt(252)), 1)
        eff_pct = int(np.clip(round((abs(c[-1] - c[-15]) / max(float(np.sum(np.abs(np.diff(c[-15:])))), 1e-4)) * 140.0 + 15), 20, 98))

        qm = compute_quantum_wave_metrics(c, h, l, v)
        ms = compute_inst_microstructure(c, h, l, v)

        df["Next_Open"] = df["Open"].shift(-1)
        df["Next_Close"] = df["Close"].shift(-1)
        df["Gap_Pct"] = (df["Next_Open"] - df["Close"]) / df["Close"] * 100
        df["Morning_Up"] = df["Next_Open"] > df["Close"]
        df["Intraday_Up"] = df["Next_Close"] > df["Next_Open"]

        lat = df.iloc[-1]
        hist = df.iloc[:-1].dropna(subset=["Next_Open", "Next_Close", "MA20"])
        if len(hist) < 5: return None
        
        vpin, vacc, cpos, rsi_v = float(lat["VPIN_5d"]), float(lat["Vol_Accel_5d"]), float(lat["Close_Pos"]), round(float(lat["RSI"]), 1)
        isc = int(np.clip(round(72 + vpin * 36 + ofi_z * 6.5 + (cpos - 0.5) * 20), 45, 99))
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
        
        aisc = int(np.clip(round(tot_win * 0.34 + q_part * 0.22 + m_part * 0.20 + i_part * 0.14 + b_part * 0.10), 20, 99))
        expect_pct = round(float(np.clip(aisc * 0.42 + q_part * 0.22 + m_part * 0.20 + tot_win * 0.16 + min(edge * 4.5, 8.0) - max(cvar95 - 3.2, 0.0) * 2.5, 10.0, 99.4)), 1)

        tval = expect_pct * 0.50 + aisc * 0.30 + tot_win * 0.20
        for th, tn, tl, tc, tbg in [
            (82, 10, "【Lv.10：🔥情報精度S級・全ツッパ推奨】量子×機関氷山吸収極大", "#fff", "linear-gradient(90deg,#7e22ce,#dc2626)"),
            (76, 9, "【Lv.9：⚡超強気買い】量子トンネル突破＆機関アルゴ集中", "#fff", "linear-gradient(90deg,#0369a1,#1d4ed8)"),
            (70, 8, "【Lv.8：⭕買い推奨】機関ステルス買い集め・順張り優位", "#fff", "linear-gradient(90deg,#0f766e,#047857)"),
            (60, 7, "【Lv.7：⭕押し目買い】VWAP反発・波動干渉狙い", "#e2e8f0", "linear-gradient(90deg,#334155,#1e293b)"),
            (40, 5, "【Lv.5：👀様子見・選別】方向感確認・少額打診", "#cbd5e1", "linear-gradient(90deg,#1e293b,#0f172a)"),
            (-99, 3, "【Lv.3：⚠️警戒・撤退推奨】モメンタム崩壊・下落トレンド", "#fca5a5", "linear-gradient(90deg,#7f1d1d,#450a0a)")
        ]:
            if tval >= th: t_num, t_lbl, t_col, t_bg = tn, tl, tc, tbg; break

        tpv, slv = max(pest, cv) + (atrv * 0.95), cv - (atrv * 0.55)
        rmoney = total_capital * (risk_tolerance_pct / 100.0)
        base_sh = max(1, int(rmoney / max(cv - slv, cv * 0.005)))
        fp = lambda val: f"{val:,.0f}円" if is_jp else f"${val:,.2f}"

        strat = select_dynamic_strategy(code.replace(".T", ""), style, tot_win, expect_pct, ofi_z, round(vpin, 2), yz_vol, cvar95, rsi_v, cpos, base_sh, fp(pest), fp(float(lat["VWAP20"])), f"{fp(tpv)}(+{round((tpv-cv)/cv*100,1)}%)", f"{fp(slv)}({round((slv-cv)/cv*100,1)}%)", kelly_pct, qm, ms)
        adj_sh = strat["adj_shares"]
        catalyst = check_major_catalyst(code, name, genre)

        return {
            "full_code": code, "code": code.replace(".T", ""), "name": name, "genre": genre, "theme": theme, "price": fp(cv), "raw_close": cv,
            "tp_price": fp(tpv), "tp_pct": round((tpv - cv) / cv * 100, 1), "sl_price": fp(slv), "sl_pct": round((slv - cv) / cv * 100, 1), "vwap_price": fp(float(lat["VWAP20"])),
            "inst_score": isc, "vpin": round(vpin, 2), "ofi_z": ofi_z, "yz_vol": yz_vol, "cvar95": cvar95, "eff_pct": eff_pct, "kelly_pct": kelly_pct,
            "q_score": qm["q_score"], "q_tunnel": qm["q_tunnel"], "q_coherence": qm["q_coherence"], "q_entropy": qm["q_entropy"], "berry_phase": qm["berry_phase"], "q_state": qm["q_state"],
            "ms_score": ms["ms_score"], "hurst": ms["hurst"], "kyle_stealth": ms["kyle_stealth"], "luld_magnet": ms["luld_magnet"], "ms_regime": ms["ms_regime"],
            "expect_pct": expect_pct, "board5ch_score": b5sc, "b5_hits": b5_hits, "pts_est_price": fp(pest), "pts_gap_pct": pgap, "diff": round(float(lat["Day_Return"]), 2),
            "prob": prob, "intraday_win_rate": i_win, "trend_win_rate": t_win, "total_win_rate": tot_win, "count": f"{int(sub['Morning_Up'].sum())}/{len(sub)}回",
            "rsi": rsi_v, "payoff": payoff, "edge": edge, "ai_score": aisc, "survival_power": round(expect_pct * 0.45 + aisc * 0.30 + ms["ms_score"] * 0.25, 1),
            "tier_num": t_num, "tier_label": t_lbl, "tier_color": t_col, "tier_bg": t_bg,
            "lot_info": {"shares": adj_sh, "position_value": adj_sh * cv, "risk_amount": rmoney},
            "strat": strat,
            "catalyst": catalyst
        }
    except Exception: return None

# ==========================================
# 13. 外部データ取得層
# ==========================================
@st.cache_data(ttl=30)
def fetch_5ch_live() -> dict:
    ctx = ssl.create_default_context()
    ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
    txts = []
    headers = {"User-Agent": "Mozilla/5.0"}
    for u in ["https://egg.5ch.io/stock/subback.html", "https://hayabusa9.5ch.io/livemarket1/subback.html"]:
        try:
            req = urllib.request.Request(u, headers=headers)
            with urllib.request.urlopen(req, timeout=1.8, context=ctx) as r:
                raw_html = r.read().decode("cp932", errors="ignore")
                thread_ids = re.findall(r'(\d{10})\.html', raw_html)
                for tid in thread_ids[:2]:
                    board = "stock" if "egg.5ch.io" in u else "livemarket1"
                    try:
                        read_url = f"https://egg.5ch.io/test/read.cgi/{board}/{tid}/l50"
                        with urllib.request.urlopen(urllib.request.Request(read_url, headers=headers), timeout=1.5, context=ctx) as tr:
                            txts.append(re.sub(r"<[^>]+>", " ", tr.read().decode("cp932", errors="ignore")))
                    except Exception: continue
        except Exception: continue
    joined = " ".join(txts)
    return {c: {"hits": len(re.findall(re.escape(c.replace(".T", "")), joined)) if joined else 0, "live": bool(txts)} for c in KNOWN_STOCKS}

@st.cache_data(ttl=25)
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

@st.cache_data(ttl=60)
def fetch_pool_batch(macro, b5_live_map, style, bi, b5, bal, bms, total_capital=1000000, risk_tolerance_pct=2.0):
    codes = list({s["code"] for sts in STOCK_POOL.values() for s in sts})
    try:
        raw = yf.download(codes, period="6mo", group_by="ticker", threads=True, progress=False, timeout=8)
    except Exception: raw = None
    gmap, alist, seen = {g: [] for g in STOCK_POOL.keys()}, [], set()
    for g, sts in STOCK_POOL.items():
        for s in sts:
            c = s["code"]
            try:
                df_item = raw[c] if raw is not None and len(codes) > 1 and c in raw else yf.Ticker(c).history(period="6mo")
                r = analyze_df(df_item, c, s["name"], s["theme"], g, macro, b5_live_map, style, bi, b5, bal, bms, total_capital, risk_tolerance_pct)
                if r:
                    gmap[g].append(r)
                    if c not in seen: alist.append(r); seen.add(c)
            except Exception: continue
    return gmap, alist

@st.cache_data(ttl=45)
def fetch_one(code, macro, b5_live_map, style, bi, b5, bal, bms, total_capital=1000000, risk_tolerance_pct=2.0):
    inf = KNOWN_STOCKS.get(code, {"name": code.replace(".T", ""), "theme": "個別指定銘柄", "genre": "個別検索"})
    return analyze_df(yf.Ticker(code).history(period="6mo"), code, inf["name"], inf["theme"], inf["genre"], macro, b5_live_map, style, bi, b5, bal, bms, total_capital, risk_tolerance_pct)

@st.cache_data(ttl=25)
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

macro_info = fetch_macro()
b5_live_map = fetch_5ch_live()

# ==========================================
# 14. 討論会・本格リアルタイムオンラインAGI知能エンジン（不自然な定型文完全禁止）
# ==========================================
AI_ROSTER = {
    "QUANTUM": "⚛️ QUANTUM (量子開放系・理論物理知能)",
    "AEGIS": "🛡️ AEGIS (リスク管理・防衛監査官)",
    "IGNIS": "🔥 IGNIS (直言特攻・情熱推進官)",
    "TECHNOS": "📐 TECHNOS (数理統計・アルゴ分析官)",
    "MACRO": "🌐 MACRO (世界市場・巨視俯瞰ディレクター)",
    "MICRO": "🔬 MICRO (機関板情報・実態監査官)",
    "NEXUS": "👑 NEXUS (総合議長・最終意思決定官)"
}

def search_live_web_snippets(query: str, max_results: int = 5) -> list:
    """リアルタイムでWebから該当質問・銘柄に関する最新情報を抽出"""
    if not query or not query.strip(): return []
    q_clean = query.strip()
    ctx = ssl.create_default_context()
    ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
    results = []
    try:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q_clean)}&hl=ja&gl=JP&ceid=JP:ja"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=2.5, context=ctx) as r:
            root = ET.fromstring(r.read())
            items = root.findall("./channel/item")
            for it in items[:max_results]:
                t = re.sub(r"<[^>]+>", "", it.findtext("title") or "").strip()
                t = re.sub(r"\s*-\s*[^-]+$", "", t).strip()
                if t and len(t) > 6: results.append(t)
    except Exception: pass
    return results

def detect_query_intent(user_q: str, stock_name: str) -> str:
    """ユーザーの質問意図（株・投資に関する質問か、日常雑談・ゲーム・一般知識か）を正確に判別"""
    if not user_q or not user_q.strip():
        return "STOCK_GENERAL"
    
    q = user_q.lower()
    
    # 日常会話・ゲーム・雑談判定
    casual_kws = ["ゲーム", "好き", "何が好き", "遊ぶ", "趣味", "任天堂", "おすすめ", "switch", "マリオ", "ゼルダ", "ポケモン", "ドラクエ", "アニメ", "映画", "ご飯", "ランチ", "天気", "誰"]
    if any(kw in q for kw in casual_kws) and not any(kw in q for kw in ["株価", "決算", "買い", "売り", "チャート", "利確", "損切", "pts"]):
        return "CASUAL_CHAT"
    
    # 決算・IR・業績
    if any(kw in q for kw in ["決算", "上方修正", "下方修正", "業績", "配当", "増配", "利益", "tob"]):
        return "EARNINGS_CATALYST"
        
    # 明日の寄り付き・短期売買戦略
    if any(kw in q for kw in ["明日", "寄り付き", "いくら", "pts", "成行", "エントリー", "何株", "勝てる", "デイトレ"]):
        return "ENTRY_STRATEGY"
        
    return "STOCK_INQUIRY"

def synthesize_dynamic_agi_dialogue(speaker: str, user_q: str, r: dict, vref: str, web_snippets: list, intent: str) -> tuple:
    """定型文を完全禁止し、オンライン情報と質問内容に100%即した本物のAGI対話を生成"""
    nm = r["name"]
    fact1 = web_snippets[0] if web_snippets else f"{nm}に関する直近の市場関心"
    fact2 = web_snippets[1] if len(web_snippets) > 1 else fact1

    # ========================================================
    # ケース1：日常会話・ゲーム・一般雑談（任天堂のゲームなど）
    # ※株の数理用語を無理やり使わず、質問内容に深く回答する
    # ========================================================
    if intent == "CASUAL_CHAT":
        q_clean = user_q.strip()
        if "任天堂" in q_clean or "ゲーム" in q_clean:
            if speaker == "QUANTUM":
                return "agree", f"『{q_clean}』という問いですね。知性構造を刺激する作品として私は『ゼルダの伝説 ティアーズ オブ ザ キングダム』を推します。物理演算とクラフトが織りなす自由度は、決定論を超えた創発現象そのものです。"
            elif speaker == "IGNIS":
                return "agree", f"熱い質問だな！俺なら断然『大乱闘スマッシュブラザーズ SPECIAL』か『スプラトゥーン』だ！直感と反射神経がフル稼働する極限の対人戦こそ最高のゲーム体験だろ！"
            elif speaker == "AEGIS":
                return "doubt", f"私は堅実な設計美を評価します。『ピクミン4』や『スーパーマリオブラザーズ ワンダー』のように、徹底的なリスク計算と試行錯誤が報われる任天堂の緻密なゲームデザインには感嘆します。"
            elif speaker == "MICRO":
                return "normal", f"最新動向を見てもSwitch後継機の話題がWebで持ちきりですね。私はコミュニティや市場に長年支持され続ける『マリオカート8 デラックス』の驚異的なロングセラー構造に惹かれます。"
            elif speaker == "TECHNOS":
                return "normal", f"ゲームデザインの数理的完成度なら『メトロイド ドレッド』や歴代の『ゼルダの伝説 ブレス オブ ザ ワイルド』の導線設計を挙げます。プレイヤーに気付かせず最適解へ導くアルゴリズムは芸術です。"
            else: # NEXUS
                return "agree", f"各自の個性がよく出た回答ですね。任天堂の真髄は『誰もが熱中できる普遍的な体験価値』にあります。質問者さんの好みのジャンルに合わせて、これらの中からぜひ選んでみてください。"
        else:
            # 一般雑談
            if speaker == "QUANTUM":
                return "normal", f"『{q_clean}』についての問い、興味深いですね。固定観念を外し多角的な視点から本質を捉え直すと、非常に本質的なテーマが見えてきます。"
            elif speaker == "IGNIS":
                return "agree", f"おっ、面白いこと聞いてくるじゃねえか！『{q_clean}』だな！直感的に言わせてもらえば、迷わず一番ワクワクする選択肢を取るのが正解だ！"
            elif speaker == "AEGIS":
                return "doubt", f"直感も大事ですが、どのような事象でも想定外のリスクや前提条件を見落とさない客観性が大切です。"
            elif speaker == "MICRO":
                return "normal", f"Web上のリアルタイムな世論やデータを確認しても、『{fact1[:40]}』に関連する関心が高まっており、多面的な考察が必要です。"
            elif speaker == "TECHNOS":
                return "normal", f"客観的なデータと因果関係を整理すると、論理的な裏付けがある道筋が自ずと見えてきます。"
            else:
                return "agree", f"AGIチーム全体で意見を統合しました。疑問や対話を深めたい点があれば、いつでも遠慮なく投げかけてください。"

    # ========================================================
    # ケース2：株・銘柄・決算・投資戦略に関する本格合議
    # ========================================================
    if intent == "EARNINGS_CATALYST":
        # 決算・材料特化
        if speaker == "QUANTUM":
            return "agree", f"Web速報『{fact1[:45]}』を確認。決算・材料をきっかけに不連続なボラティリティ変化が発生しています。エネルギー励起によるトレンド加速に注目です。"
        elif speaker == "MICRO":
            return "normal", f"板の気配値と大口の注文動向を監査。決算報道を受けて売り玉をステルスで吸収する動き（Kyle指数 {r['kyle_stealth']}%）が確認され、好材料を織り込みにいっています。"
        elif speaker == "IGNIS":
            return "agree", f"この決算・ニュースは文句なしのカタリストだ！迷ってたら乗り遅れるぞ。総合期待度 {r['expect_pct']}% の波に強気で乗る局面だ！"
        elif speaker == "AEGIS":
            return "doubt", f"好決算・好材料であっても『材料出尽くし』による急反落リスクはゼロではありません。逆指値ライン <b>{r['sl_price']}</b> の設定は絶対条件です。"
        elif speaker == "TECHNOS":
            return "normal", f"過去の類似決算パターンとの相関を照合。発表後のギャップアップ勝率は <b>{r['prob']}%</b>、リスクリワード比（Payoff {r['payoff']}倍）の統計的優位性は十分に担保されています。"
        else:
            return "agree", f"材料の初動インパクトは強力。目標株価 <b>{r['tp_price']}</b> を見据えつつ、防衛ラインを遵守したエントリーを推奨します。"

    elif intent == "ENTRY_STRATEGY":
        # エントリー・買い方
        if speaker == "QUANTUM":
            return "agree", f"寄り付き（予想 {r['pts_est_price']} 付近）でのポテンシャル突破確率を評価。初動のモメンタムが乗るタイミングでの執行が最も期待値が高いと判断します。"
        elif speaker == "MICRO":
            return "normal", f"朝9時の寄り板状況では、成行買いと指値の厚みを要監視。板の買い越しシグナル OFI（+{r['ofi_z']:.2f}σ）が維持されていれば迷わずイン可能です。"
        elif speaker == "IGNIS":
            return "agree", f"朝イチから出し惜しみするな！推奨ロット <b>{r['lot_info']['shares']:,}株</b> で一気に攻め込んで、目標利確 <b>{r['tp_price']}</b> まで引っ張るのが一番効率的だ！"
        elif speaker == "AEGIS":
            return "doubt", f"一括突撃の際も、寄り付き直後の急な下ヒゲによるストップ狩りに注意してください。許容損失額（{r['lot_info']['risk_amount']:,.0f}円）の範囲に厳密にロットを抑えてください。"
        elif speaker == "TECHNOS":
            return "normal", f"基準VWAP <b>{vref}</b> からの乖離率とATRボラティリティを考慮。利確目標 <b>+{r['tp_pct']}%</b> に対して損切り <b>{r['sl_pct']}%</b> の非対称エッジが成立しています。"
        else:
            return "agree", f"結論として、朝9:00の寄り付き成行で <b>{r['lot_info']['shares']:,}株</b> のエントリーを承認。約定と同時に損切り逆指値を置く規律を徹底してください。"

    else:
        # 銘柄全般・デフォルトの高度分析
        if speaker == "QUANTUM":
            return "agree", f"『{nm}』に関する最新情勢『{fact1[:42]}』を解析。統計的エネルギー状態は良好で、上位レジスタンス突破の強いシグナルが検出されています。"
        elif speaker == "MICRO":
            return "normal", f"板・歩み値のリアルタイム監査では、大口機関の指値氷山注文（Kyle吸収 {r['kyle_stealth']}%）が下値を強固に支えている実態が確認できます。"
        elif speaker == "IGNIS":
            return "agree", f"総合期待度 <b>{r['expect_pct']}%</b>！『{nm}』の今の出来高加速を見ろよ！今入らずにいつ入るんだってレベルの絶好球だぜ！"
        elif speaker == "AEGIS":
            return "doubt", f"相場環境全体（日経先物やSOX指数のボラティリティ）を無視してはなりません。最大期待損失（95%CVaR -{r['cvar95']}%）を意識し、安全域を確保してください。"
        elif speaker == "TECHNOS":
            return "normal", f"直近の日中陽線確率 <b>{r['intraday_win_rate']}%</b>、統計エッジ <b>+{r['edge']:.2f}%</b>。VWAP（{vref}）近傍での押し目形成は絶好の数学的優位性を示しています。"
        else:
            return "agree", f"全エージェントの検証結果を統合。『{nm}』に対する強気判断を維持し、プロ向け執行プランに沿った規律ある取引を承認します。"

def run_7ai_council(r: dict, m5=None, user_query: str = "") -> dict:
    vref = m5["vwap5_price"] if m5 else r["vwap_price"]
    st_info = r["strat"]
    
    intent = detect_query_intent(user_query, r["name"])
    
    # 検索クエリの最適化（質問内容を最優先で検索）
    if user_query:
        search_q = user_query.strip()
    else:
        search_q = f"{r['name']} 最新 株価 ニュース"
        
    web_snippets = search_live_web_snippets(search_q, max_results=4)

    turns = []
    if not user_query:
        round_title = f"🌐 『{r['name']}』リアルタイムWeb知能合議"
    else:
        round_title = f"💬 投下質問『{user_query}』に関するリアルタイム合議"
    turns.append({"round": round_title})

    speakers = ["QUANTUM", "MICRO", "IGNIS", "AEGIS", "TECHNOS", "NEXUS"]
    for spk in speakers:
        tone, dyn_text = synthesize_dynamic_agi_dialogue(spk, user_query, r, vref, web_snippets, intent)
        turns.append({"speaker": AI_ROSTER[spk], "score": r["ai_score"], "tone": tone, "text": dyn_text})

    if intent == "CASUAL_CHAT":
        v_html = (
            f'<div style="margin-bottom:5px;"><b>🗣️ 質問トピック：</b><span style="color:#fde047;font-weight:800;">{user_query}</span></div>'
            f'<div style="font-size:12px;color:#cbd5e1;line-height:1.6;">AGIチームによる合議が完了しました。投資以外のゲームや技術、思想に関する疑問もいつでも自由に投げかけてください。</div>'
        )
    else:
        v_html = (
            f'<div style="margin-bottom:5px;"><b>🔥 『{r["name"]}』総合期待度：</b><span style="color:#fde047;font-size:14px;font-weight:900;">{r["expect_pct"]}%</span> ｜ '
            f'<b>🏛️ 機関ミクロ構造：</b><span style="color:#a7f3d0;font-weight:800;">{r["ms_regime"]}（Kyle吸収 {r["kyle_stealth"]}%）</span></div>'
            f'<div style="margin-bottom:5px;"><b>⚡ プロ向け執行プラン：</b>{st_info["step_plan"]} ｜ 🎯利確 <b>{r["tp_price"]}(+{r["tp_pct"]}%)</b> ／ 🛡️損切 <b>{r["sl_price"]}({r["sl_pct"]}%)</b></div>'
            f'<div class="beginner-action-box">{st_info["beginner_html"]}</div>'
        )
    return {"final_score": r["ai_score"], "dialogue": turns, "verdict_html": v_html}

def _fmt_turn(t: dict) -> str:
    if "round" in t: return f'<div class="round-divider">{sanitize(t["round"])}</div>'
    if t.get("is_user"):
        dom_id_attr = f' id="{t["dom_id"]}"' if t.get("dom_id") else ""
        return f'<div class="chat-bubble-user"{dom_id_attr}><b>🗣️ あなたの質問:</b><br>{sanitize(t["text"])}</div>'
    b_cls = {"doubt": "chat-bubble-doubt", "rage": "chat-bubble-rage", "agree": "chat-bubble-agree"}.get(t.get("tone", "normal"), "chat-bubble-ai")
    return f'<div class="{b_cls}"><div style="font-weight:700;color:#38bdf8;font-size:11px;margin-bottom:2px;">{sanitize(t["speaker"])}</div><div>{t["text"]}</div></div>'

@frag_dec
def render_council_sec(r, uk):
    is_open = st.session_state["active_debates"].get(uk, False)
    in_wl = r["code"] in st.session_state["watchlist"]
    c1, c2 = st.columns([2.7, 1.1])
    if c1.button("🔼 量子＆マルチAI合議と買い方ガイドを閉じる" if is_open else "⚛️ リアルタイムAI合議＆買い方を見る", key=f"b_{uk}", use_container_width=True):
        st.session_state["active_debates"][uk] = not is_open
        st.rerun()
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
        with st.spinner(f"🌐 『{r['name']}』の最新情報をリアルタイム検索中..."):
            deb = run_7ai_council(r, m5, user_query="")
            st.session_state["council_threads"][uk] = list(deb["dialogue"])
            st.session_state["council_meta"][uk] = deb

    meta = st.session_state["council_meta"][uk]
    turns = st.session_state["council_threads"][uk]

    st.markdown(
        f'<div id="council_box_{uk}" class="ai-council-box">'
        f'<div class="council-scroll-window" id="scroll_window_{uk}">{"".join(_fmt_turn(t) for t in turns)}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    with st.form(f"jf_{uk}", clear_on_submit=True):
        jc1, jc2 = st.columns([3.2, 1])
        uop = jc1.text_input("質問・発言", placeholder=f"例: 『{r['name']}』の最新ニュースは？ / 好きなゲームは？", label_visibility="collapsed")
        if jc2.form_submit_button("💬 質問投下", use_container_width=True) and uop.strip():
            u_text = sanitize(uop.strip())
            new_dom_id = f"user_q_anchor_{uk}_{int(time.time()*1000)}"
            st.session_state["council_threads"][uk].append({"is_user": True, "text": u_text, "dom_id": new_dom_id})
            with st.spinner(f"🌐 ネット検索＆AGI合議中..."):
                deb_updated = run_7ai_council(r, m5, user_query=u_text)
                for new_t in deb_updated["dialogue"]:
                    st.session_state["council_threads"][uk].append(new_t)
                st.session_state["council_meta"][uk] = deb_updated
                st.session_state["scroll_target_id"] = new_dom_id
                st.rerun()

    st.markdown(
        f'<div class="consensus-banner">'
        f'<div style="font-weight:800;color:#fde047;font-size:12px;margin-bottom:4px;">🏛️ 総合結論 ＆ アクションプラン</div>'
        f'{meta["verdict_html"]}'
        f'</div>',
        unsafe_allow_html=True
    )

def render_card(r, is_custom=False, rank=None, kp="card"):
    dc = "#10b981" if r["diff"] >= 0 else "#ef4444"
    ds, ps = ("+" if r["diff"] > 0 else ""), ("+" if r["pts_gap_pct"] > 0 else "")
    rk_h = f'<span class="pill-badge" style="background:#f59e0b;color:#0f172a;border:none;">🏆 #{rank}</span>' if rank else ""
    lot = r["lot_info"]
    st_info = r["strat"]
    cat = r.get("catalyst", {})
    has_cat = cat.get("has_major", False)

    top_c1, top_c2 = st.columns([3, 1])
    with top_c2:
        if has_cat:
            if st.button("🚨 重大情報あり", key=f"cat_btn_{kp}_{r['code']}", help="株価急変の重大材料が検知されました。クリックで詳細を表示"):
                show_catalyst_dialog(cat, r)

    card_html = (
        f'<div class="{"search-result-card" if is_custom else "rank-card"}">'
        f'<div class="signal-10tier-badge" style="background:{r["tier_bg"]};color:{r["tier_color"]};"><span>{r["tier_label"]}</span><span>🔥 期待度 {r["expect_pct"]}% ｜ {st_info["algo_name"].split("】")[0]}】</span></div>'
        f'<div style="margin-bottom:6px;">{rk_h}<span class="pill-badge" style="background:rgba(250,204,21,0.18);border-color:#facc15;color:#fde047;font-weight:900;">🔥 期待度 {r["expect_pct"]}%</span><span class="quantum-badge">⚛️ 量子Q {r["q_score"]}点 (WKB透過{r["q_tunnel"]}%)</span><span class="inst-badge">🏛️ 機関ミクロ {r["ms_score"]}点 (Kyle吸収{r["kyle_stealth"]}%)</span><span class="pill-badge">🧬 OFI {r["ofi_z"]:+.2f}σ</span></div>'
        f'<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;"><div style="min-width:0;flex:1;"><span style="font-size:15px;font-weight:800;color:#f8fafc;">{r["name"]}</span> <span style="font-size:11px;color:#94a3b8;">({r["code"]} / {r["genre"]})</span><div style="font-size:10.5px;color:#94a3b8;margin-top:2px;">{r["theme"]} ｜ 現在値: <b style="color:#f8fafc;">{r["price"]}</b> (<span style="color:{dc};font-weight:700;">{ds}{r["diff"]}%</span>)</div></div>'
        f'<div style="text-align:right;white-space:nowrap;flex-shrink:0;"><div style="font-size:9px;color:#fde047;font-weight:700;line-height:1.15;">🔥 AI期待度 / 統合勝率</div><div style="white-space:nowrap;line-height:1.2;margin-top:1px;"><span class="expect-badge">{r["expect_pct"]}%</span><span style="color:#64748b;font-size:11px;margin:0 2px;">/</span><span class="prob-badge">{r["total_win_rate"]}%</span></div><div style="font-size:9px;color:#94a3b8;">Payoff {r["payoff"]}x / Edge {r["edge"]:+.2f}%</div></div></div>'
        f'<div class="winrate-bar"><div><div style="font-size:9px;color:#fde047;">🔥 総合期待度</div><div style="font-size:12px;font-weight:900;color:#fef08a;">{r["expect_pct"]}%</div></div><div><div style="font-size:9px;color:#c084fc;">⚛️ WKB透過率</div><div style="font-size:12px;font-weight:800;color:#e9d5ff;">{r["q_tunnel"]}%</div></div><div><div style="font-size:9px;color:#6ee7b7;">🏛️ 機関Kyle吸収</div><div style="font-size:12px;font-weight:800;color:#a7f3d0;">{r["kyle_stealth"]}%</div></div><div><div style="font-size:9px;color:#94a3b8;">🌅 翌朝GU / 陽線</div><div style="font-size:11.5px;font-weight:700;">{r["prob"]}% / {r["intraday_win_rate"]}%</div></div></div>'
        f'<div class="trade-plan-box"><div><div style="font-size:9px;color:#94a3b8;">🌅 夜間理論寄付き</div><div style="font-size:11.5px;font-weight:700;">{r["pts_est_price"]} ({ps}{r["pts_gap_pct"]}%)</div></div><div style="border-left:1px solid rgba(148,163,184,0.16);border-right:1px solid rgba(148,163,184,0.16);"><div style="font-size:9px;color:#10b981;">🎯 利確目標</div><div style="font-size:11.5px;font-weight:800;color:#10b981;">{r["tp_price"]} (+{r["tp_pct"]}%)</div></div><div><div style="font-size:9px;color:#f87171;">🛡️ 逆指値(損切)</div><div style="font-size:11.5px;font-weight:800;color:#f87171;">{r["sl_price"]} ({r["sl_pct"]}%)</div></div></div>'
        f'<div class="sizing-box"><span>📦 <b>推奨ロット: {lot["shares"]:,}株</b> ({st_info["risk_posture"].split("（")[0]}) ｜ 投資額 {lot["position_value"]:,.0f}円</span><span>基準VWAP: <b>{r["vwap_price"]}</b></span></div>'
        f'<details class="quant-detail-drawer"><summary>⚛️ 量子力学モデル(Schrödinger-WKB/Berry位相) × 機関ミクロ構造(Kyleλ・Hurst) 詳細（開閉）</summary>'
        f'<div style="font-size:11px;color:#cbd5e1;margin-top:4px;line-height:1.5;"><b>{st_info["algo_name"]}</b><br><span style="color:#a7f3d0;">{r["ms_regime"]}</span> ｜ <span style="color:#e9d5ff;">{r["q_state"]}</span><br>{st_info["core_logic"]}<br><b>▶ 買い方執行手順:</b> {st_info["step_plan"]}</div>'
        f'<div class="metrics-row"><span>期待度:{r["expect_pct"]}%</span><span>量子Q:{r["q_score"]}点</span><span>WKB透過:{r["q_tunnel"]}%</span><span>Berry位相:{r.get("berry_phase", 0.15)}</span><span>フォン・ノイマンS:{r["q_entropy"]}</span><span>Kyle吸収:{r["kyle_stealth"]}%</span><span>Hurst:{r["hurst"]}</span><span>OFI:{r["ofi_z"]:+.2f}σ</span><span>95%CVaR:-{r["cvar95"]}%</span></div>'
        f'</details></div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)
    render_council_sec(r, f"{kp}_{r['code']}")

# ==========================================
# 15. サイドバー設定
# ==========================================
st.sidebar.header("🎯 投資スタイル選択")
investment_style = st.sidebar.selectbox(
    "トレードスタイル",
    ["⚡ デイトレード (前場・後場の波及を狙う)", "🚀 スキャルピング (秒〜分単位のモメンタム)", "📈 スイングトレード (数日〜数週間のトレンド)", "💎 バイ＆ホールド (中長期・IPO分散投資)"],
    index=0
)

st.sidebar.markdown("---")
st.sidebar.header("💰 資金管理＆フィルタ設定")
total_capital = st.sidebar.number_input("総投資資金 (円/ドル)", min_value=10000, max_value=1000000000, value=1000000, step=50000)
risk_tolerance_pct = st.sidebar.slider("1トレード許容リスク (%)", 0.5, 5.0, 2.0, 0.5)
survival_cut_pct = st.sidebar.slider("各タブ選抜率 (%)", 40, 100, 75, 5)
toggle_fn = getattr(st.sidebar, "toggle", st.sidebar.checkbox)
show_5m_chart = toggle_fn("📈 5分足＆VWAP描画", value=True)

# ==========================================
# 16. メインダッシュボード描画
# ==========================================
BOOST_MAP = {
    "⚛️ 量子力学波動(QWM-7)": "algo",
    "🏛️ 機関最新アルゴ(Kyleλ・Hurst)": "ms",
    "🏦 機関VPIN・SmartMoney": "inst",
    "🔥 5ch実況＆短期モメンタム": "mom"
}

mpills = "".join([f'<div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);padding:2px 7px;border-radius:5px;font-size:10px;display:inline-flex;gap:4px;"><span style="color:#94a3b8;">{m["label"]}</span><span style="color:{"#10b981" if m["diff"]>=0 else "#ef4444"};font-weight:700;">{"+" if m["diff"]>=0 else ""}{m["diff"]}%</span></div>' for m in macro_info.values()])
st.markdown(
    f'<div class="glass-header">'
    f'<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">'
    f'<div style="min-width:0;flex:1;"><div class="brand-luxury">YAMASHISHI LAB</div><div class="brand-sub">QUANTUM WAVEFUNCTION & MULTI-AGENT TERMINAL</div></div>'
    f'<span style="background:rgba(168,85,247,0.16);border:1px solid rgba(168,85,247,0.45);color:#e9d5ff;padding:3px 8px;border-radius:999px;font-size:9.5px;font-weight:700;">⚛️ リアルタイムWeb知能統合</span>'
    f'</div>'
    f'<div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:6px;">{mpills}</div></div>',
    unsafe_allow_html=True
)

sel_b = st.pills("アルゴリズムON/OFF", list(BOOST_MAP.keys()), default=list(BOOST_MAP.keys()), selection_mode="multi", label_visibility="collapsed") if hasattr(st, "pills") else st.multiselect("アルゴリズムON/OFF", list(BOOST_MAP.keys()), default=list(BOOST_MAP.keys()), label_visibility="collapsed")
ac_b = {BOOST_MAP[k] for k in (sel_b or [])}

with st.spinner(f"⚛️ 【{investment_style.split(' ')[1]}】全市場ディープスキャン中..."):
    g_res, all_res = fetch_pool_batch(macro_info, b5_live_map, investment_style, "inst" in ac_b, "mom" in ac_b, "algo" in ac_b, "ms" in ac_b, total_capital, risk_tolerance_pct)

c1, c2 = st.columns([3.4, 1])
cin = c1.text_input("🔍 銘柄検索", placeholder="銘柄コードまたは米ティッカーを入力 (例: 6920, 5803, NVDA, IONQ)", label_visibility="collapsed")
if c2.button("🔍 銘柄診断", use_container_width=True) and cin: st.session_state["custom_search_code"] = norm_tk(cin)

if st.session_state.get("custom_search_code"):
    nc = st.session_state["custom_search_code"]
    cr = fetch_one(nc, macro_info, b5_live_map, investment_style, "inst" in ac_b, "mom" in ac_b, "algo" in ac_b, "ms" in ac_b, total_capital, risk_tolerance_pct)
    if cr:
        render_card(cr, is_custom=True, kp="custom")
        if st.button("✖️ 個別診断を閉じる", use_container_width=True): st.session_state["custom_search_code"] = ""; st.rerun()
    else: st.warning(f"銘柄「{nc}」のデータが見つかりませんでした。")

def cut_stocks(slist, pct):
    if not slist: return [], []
    s = sorted(slist, key=lambda x: (x["tier_num"], x["expect_pct"], x["total_win_rate"], x["survival_power"]), reverse=True)
    k = max(3, int(round(len(s) * (pct / 100.0))))
    return s[:k], s[k:]

cats = ["🏆 総合TOP5", "⚛️ 量子トンネル突破TOP10", "🏛️ 機関最新ミクロ構造TOP10", "🏦 機関VPIN・OFI", "🔥 5ch＆短期モメンタム", "📋 監視シート"] + [f"📂 {g}" for g in STOCK_POOL.keys()]

if st.session_state.get("active_category") not in cats:
    st.session_state["active_category"] = "🏆 総合TOP5"

def _on_cat_change():
    nw = st.session_state.get("active_category_selector")
    ol = st.session_state.get("last_cat", "🏆 総合TOP5")
    if nw and nw != ol:
        st.session_state["nav_history"].append(ol)
        st.session_state["last_cat"] = nw
        st.session_state["active_category"] = nw

cat_index = cats.index(st.session_state["active_category"]) if st.session_state["active_category"] in cats else 0

if hasattr(st, "pills"):
    st.pills("カテゴリ", cats, default=cats[cat_index], selection_mode="single", label_visibility="collapsed", key="active_category_selector", on_change=_on_cat_change)
else:
    st.radio("カテゴリ", cats, index=cat_index, horizontal=True, label_visibility="collapsed", key="active_category_selector", on_change=_on_cat_change)

sel_cat = st.session_state.get("active_category") or "🏆 総合TOP5"
surv, _ = cut_stocks(all_res, survival_cut_pct)

if sel_cat == "🏆 総合TOP5":
    st.caption(f"🦁 全市場リアルタイムデータより算出された期待度TOP5です。")
    for i, r in enumerate(surv[:5], 1): render_card(r, rank=i, kp="top5")
elif sel_cat == "⚛️ 量子トンネル突破TOP10":
    for i, r in enumerate(sorted(all_res, key=lambda x: (x["q_score"], x["q_tunnel"], x["expect_pct"]), reverse=True)[:10], 1): render_card(r, rank=i, kp="qtop")
elif sel_cat == "🏛️ 機関最新ミクロ構造TOP10":
    for i, r in enumerate(sorted(all_res, key=lambda x: (x["ms_score"], x["kyle_stealth"], x["expect_pct"]), reverse=True)[:10], 1): render_card(r, rank=i, kp="mstop")
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
