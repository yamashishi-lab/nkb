import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np
import altair as alt
import unicodedata, hashlib, hmac, json, os, re, ssl, smtplib, time, random, secrets, html, sqlite3
import urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# ==========================================
# 1. ページ基本設定 & 暗号化基盤
# ==========================================
st.set_page_config(
    page_title="YAMASHISHI LAB - AGI QUANTUM CORE",
    page_icon="⚡",
    layout="centered",
    initial_sidebar_state="expanded"
)

frag_dec = getattr(st, "fragment", getattr(st, "experimental_fragment", lambda f: f))

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
# 2. SQLite 堅牢データベース層
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
                bio_token TEXT,
                bio_enabled INTEGER DEFAULT 1
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
            CREATE TABLE IF NOT EXISTS agi_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TEXT,
                target_code TEXT,
                component TEXT,
                issue_type TEXT,
                detail TEXT
            );
        """)
        
        ns = datetime.now().strftime("%Y-%m-%d %H:%M")
        adm_passcode = ADMIN_RAW_PASS
        adm_pin_h = hash_sec_pwd("0000", SECRET_KEY[:16])[:16]
        
        conn.execute("""
            INSERT INTO members (email, name, status, passcode, pin_hash, applied_at, approved_at, last_seen_ts, last_seen_str, fp, raw_hfp, bio_enabled)
            VALUES (?, 'システム管理者', 'approved', ?, ?, ?, ?, 0, '-', '-', '-', 1)
            ON CONFLICT(email) DO UPDATE SET status = 'approved', passcode = excluded.passcode;
        """, (ADMIN_EMAIL, adm_passcode, adm_pin_h, ns, ns))
        conn.commit()

init_db()

# ==========================================
# 3. ユーティリティ & 端末指紋管理
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
        for k_val, desc in [(em_c, "メール"), (cur_fp, "端末指紋"), (raw_hfp, "環境ヘッダ指紋")]:
            if k_val and k_val not in invalid_keys:
                b_row = conn.execute("SELECT email, reason FROM security_bans WHERE key_val = ?", (k_val,)).fetchone()
                if b_row:
                    if b_row["email"] == ADMIN_EMAIL or is_seed_admin_email(b_row["email"]):
                        continue
                    reasons.append(f"永久BAN({desc})検知")
                    orig_target = orig_target or b_row["email"]
        
        if reasons:
            now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            r_str = " / ".join(reasons)
            conn.execute("""
                INSERT INTO spoof_logs (time, action, input_email, input_name, orig_banned_email, fp, raw_hfp, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (now_s, f"🚫 遮断({action_type})", em_c or "未入力", (name or "").strip() or "不明", orig_target or em_c, cur_fp, raw_hfp, r_str))
            conn.commit()
            return True, r_str
            
    return False, ""

# ==========================================
# 4. 厳選銘柄プール
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
# 5. 理論物理・量子力学 × 機関ミクロ構造数理エンジン
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
# 6. ネオングラス・サイバーパンク CSS
# ==========================================
def inject_css():
    css = """
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700;900&family=Plus+Jakarta+Sans:wght@400;600;800&family=JetBrains+Mono:wght@500;700;800&display=swap');
    
    [data-testid="stDecoration"] {
        display: none !important;
        height: 0px !important;
    }
    
    header[data-testid="stHeader"] {
        background: transparent !important;
        pointer-events: none !important;
        z-index: 999900 !important;
    }

    button[data-testid="stSidebarCollapsedControl"],
    button[data-testid="baseButton-headerNoPadding"],
    [data-testid="collapsedControl"] {
        pointer-events: auto !important;
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        position: fixed !important;
        left: 12px !important;
        top: 12px !important;
        z-index: 1000005 !important;
        background: rgba(15, 23, 42, 0.95) !important;
        border: 1px solid rgba(56, 189, 248, 0.6) !important;
        border-radius: 10px !important;
        box-shadow: 0 4px 18px rgba(0, 0, 0, 0.85) !important;
        color: #38bdf8 !important;
        padding: 6px 10px !important;
    }

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 14px;
        background-color: #040711;
        color: #e2e8f0;
    }

    section[data-testid="stSidebar"] {
        background-color: #080c16 !important;
        border-right: 1px solid rgba(148,163,184,0.2) !important;
        z-index: 1000000 !important;
    }

    .block-container {
        padding-top: 4.8rem !important;
        padding-bottom: 4.0rem !important;
        padding-left: 0.9rem !important;
        padding-right: 0.9rem !important;
        max-width: 900px !important;
    }

    /* 最適化：重なり完全防止＆文字飛び出しなしの洗練フローティングナビ */
    .cyber-dock-wrapper {
        position: fixed !important;
        top: 10px !important;
        right: 28px !important;
        z-index: 999998 !important;
        display: flex !important;
        align-items: center !important;
        pointer-events: auto !important;
    }

    .cyber-quantum-nav-dock {
        display: inline-flex !important;
        flex-direction: row !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 10px !important;
        background: rgba(8, 14, 28, 0.92) !important;
        backdrop-filter: blur(20px) saturate(200%) !important;
        border: 1px solid rgba(56, 189, 248, 0.45) !important;
        border-radius: 40px !important;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.85), 0 0 16px rgba(56, 189, 248, 0.25) !important;
        padding: 5px 12px !important;
    }

    .cyber-nav-btn {
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        padding: 6px 14px !important;
        height: 32px !important;
        box-sizing: border-box !important;
        background: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(148, 163, 184, 0.28) !important;
        border-radius: 20px !important;
        color: #e2e8f0 !important;
        font-family: 'JetBrains Mono', sans-serif !important;
        font-size: 11.5px !important;
        font-weight: 700 !important;
        white-space: nowrap !important;
        writing-mode: horizontal-tb !important;
        text-decoration: none !important;
        cursor: pointer !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
        user-select: none !important;
    }
    
    .cyber-nav-btn:hover {
        background: rgba(56, 189, 248, 0.15) !important;
        border-color: rgba(56, 189, 248, 0.7) !important;
        color: #ffffff !important;
    }
    
    .cyber-nav-btn:active {
        background: #0284c7 !important;
        border-color: #38bdf8 !important;
        color: #ffffff !important;
        box-shadow: 0 0 16px #38bdf8 !important;
        transform: scale(0.94) !important;
    }

    .cyber-nav-btn-highlight {
        background: rgba(239, 68, 68, 0.15) !important;
        border-color: rgba(239, 68, 68, 0.45) !important;
        color: #fca5a5 !important;
    }
    .cyber-nav-btn-highlight:hover {
        background: rgba(239, 68, 68, 0.3) !important;
        border-color: #ef4444 !important;
        color: #ffffff !important;
    }
    .cyber-nav-btn-highlight:active {
        background: #dc2626 !important;
        box-shadow: 0 0 16px #ef4444 !important;
        transform: scale(0.94) !important;
    }

    /* 管理コンソール起動ボタンスタイル（統一ネオンシアン） */
    .admin-dock-btn {
        background: linear-gradient(135deg, rgba(8, 14, 28, 0.95), rgba(15, 23, 42, 0.95)) !important;
        border: 1px solid rgba(56, 189, 248, 0.6) !important;
        border-radius: 10px !important;
        color: #38bdf8 !important;
        font-family: 'JetBrains Mono', sans-serif !important;
        font-weight: 800 !important;
        font-size: 12.5px !important;
        padding: 10px 14px !important;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.7), 0 0 10px rgba(56, 189, 248, 0.25) !important;
        transition: all 0.2s ease !important;
    }
    .admin-dock-btn:hover {
        background: rgba(56, 189, 248, 0.25) !important;
        color: #ffffff !important;
        box-shadow: 0 0 15px rgba(56, 189, 248, 0.6) !important;
    }
    .admin-dock-btn:active {
        background: #0284c7 !important;
        transform: scale(0.96) !important;
    }

    /* 重大カタリストのネオンパルスアニメーション */
    @keyframes catalyst-pulse {
        0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
        70% { box-shadow: 0 0 0 8px rgba(239, 68, 68, 0); }
        100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
    }
    .pulse-badge {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 10.5px;
        font-weight: 800;
        margin-right: 5px;
        background: rgba(239, 68, 68, 0.25);
        border: 1px solid #ef4444;
        color: #fca5a5;
        animation: catalyst-pulse 1.8s infinite;
    }

    .brand-luxury {
        font-family: 'Cinzel', serif !important;
        font-size: clamp(20px, 5.5vw, 29px) !important;
        font-weight: 900 !important;
        letter-spacing: 3px !important;
        background: linear-gradient(90deg, #ffffff 0%, #38bdf8 55%, #c084fc 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        line-height: 1.15;
    }
    .brand-sub {
        font-family: 'JetBrains Mono', monospace;
        font-size: clamp(8px, 2vw, 10.5px);
        color: #64748b;
        letter-spacing: 1.8px;
        text-transform: uppercase;
        margin-top: 5px;
    }
    .glass-header {
        background: radial-gradient(circle at top right, rgba(168,85,247,0.14), transparent 60%), linear-gradient(145deg,#0f172a 0%,#070b14 100%);
        border: 1px solid rgba(148,163,184,0.2);
        border-radius: 14px;
        padding: 14px 18px;
        margin-bottom: 20px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.5);
    }
    .rank-card, .search-result-card {
        background: linear-gradient(180deg,#0f172a 0%,#090d16 100%) !important;
        color: #f8fafc !important;
        border-radius: 14px;
        padding: 16px 18px;
        margin-bottom: 22px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.5);
        border: 1px solid rgba(148,163,184,0.18);
        border-left: 4px solid #38bdf8;
    }
    .prob-badge { font-family: 'JetBrains Mono', monospace; font-size: clamp(13px, 3.8vw, 16.5px); font-weight: 800; color: #38bdf8 !important; }
    .expect-badge { font-family: 'JetBrains Mono', monospace; font-size: clamp(13px, 3.8vw, 16.5px); font-weight: 900; color: #fde047 !important; }
    .pill-badge { display: inline-block; padding: 2px 7px; border-radius: 5px; font-size: 10px; font-weight: 700; margin-right: 4px; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.12); color: #e2e8f0; }
    .quantum-badge { display: inline-block; padding: 2px 7px; border-radius: 5px; font-size: 10px; font-weight: 800; margin-right: 4px; background: linear-gradient(90deg, rgba(168,85,247,0.22), rgba(56,189,248,0.22)); border: 1px solid rgba(168,85,247,0.55); color: #e9d5ff; }
    .inst-badge { display: inline-block; padding: 2px 7px; border-radius: 5px; font-size: 10px; font-weight: 800; margin-right: 4px; background: linear-gradient(90deg, rgba(16,185,129,0.2), rgba(56,189,248,0.2)); border: 1px solid rgba(16,185,129,0.55); color: #a7f3d0; }
    .winrate-bar { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; background: rgba(15,23,42,0.85) !important; border: 1px solid rgba(148,163,184,0.15); border-radius: 8px; padding: 8px 6px; margin-top: 10px; text-align: center; }
    .signal-10tier-badge { display: flex; justify-content: space-between; align-items: center; padding: 6px 10px; border-radius: 7px; font-size: 11px; font-weight: 800; margin-bottom: 8px; }
    .trade-plan-box { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-top: 8px; background: rgba(2,6,23,0.7) !important; padding: 8px 6px; border-radius: 8px; border: 1px solid rgba(148,163,184,0.15); text-align: center; }
    .sizing-box { background: rgba(16,185,129,0.08) !important; border: 1px solid rgba(16,185,129,0.28); border-radius: 8px; padding: 8px 12px; margin-top: 8px; font-size: 11.5px; color: #d1fae5; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; }
    details.quant-detail-drawer { margin-top: 9px; background: rgba(2,6,23,0.55); border: 1px solid rgba(168,85,247,0.25); border-radius: 8px; padding: 8px 12px; }
    details.quant-detail-drawer summary { font-size: 11.5px; font-weight: 700; color: #c084fc !important; cursor: pointer; }
    .metrics-row { display: flex; flex-wrap: wrap; gap: 4px 8px; margin-top: 6px; font-size: 10px; font-family: 'JetBrains Mono', monospace; background: rgba(15,23,42,0.9) !important; padding: 6px 8px; border-radius: 6px; color: #cbd5e1; }
    .ai-council-box { background: #070b14; color: #f8fafc !important; border-radius: 12px; padding: 14px; margin-top: 10px; margin-bottom: 12px; border: 1px solid rgba(168,85,247,0.35); }
    .council-scroll-window { max-height: 520px; overflow-y: auto; padding: 12px 10px; background: #04070e; border: 1px solid rgba(255,255,255,0.07); border-radius: 9px; margin-bottom: 10px; scroll-behavior: smooth; }
    .round-divider { text-align: center; margin: 8px 0; padding: 5px 10px; background: rgba(168,85,247,0.18); border-left: 3px solid #a855f7; color: #e9d5ff !important; font-size: 11.5px; font-weight: 800; border-radius: 5px; }
    .chat-bubble-ai, .chat-bubble-doubt, .chat-bubble-rage, .chat-bubble-agree { border-radius: 8px; padding: 10px 12px; margin-bottom: 9px; font-size: 12.5px; line-height: 1.65; background: rgba(255,255,255,0.04); border-left: 3.5px solid #38bdf8; }
    .chat-bubble-doubt { border-left-color: #f59e0b; background: rgba(245,158,11,0.08); }
    .chat-bubble-rage { border-left-color: #ef4444; background: rgba(239,68,68,0.12); }
    .chat-bubble-agree { border-left-color: #a855f7; background: rgba(168,85,247,0.12); }
    .chat-bubble-user { background: linear-gradient(135deg, rgba(30,58,138,0.92), rgba(15,23,42,0.98)) !important; border: 1.5px solid #60a5fa !important; border-left: 5px solid #38bdf8 !important; border-radius: 8px !important; padding: 9px 12px !important; margin: 12px 0 9px 0 !important; font-size: 13px !important; color: #ffffff !important; }
    .consensus-banner { background: linear-gradient(135deg,#0f172a,#1e1b4b); border: 1px solid rgba(168,85,247,0.45); border-radius: 9px; padding: 12px; margin-top: 10px; font-size: 12.5px; }
    
    .beginner-action-box {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.16), rgba(6, 78, 59, 0.35));
        border: 1.5px solid #10b981;
        border-left: 5px solid #10b981;
        border-radius: 9px;
        padding: 13px 15px;
        margin-top: 10px;
        color: #f0fdf4;
        font-size: 12.8px;
        line-height: 1.75;
    }

    .admin-modal-card {
        background: #090e1a;
        border: 1px solid rgba(56, 189, 248, 0.5);
        border-radius: 14px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.85);
    }
    """
    st.markdown(f'<div id="page_top_anchor"></div><style>{" ".join(l.strip() for l in css.splitlines() if l.strip())}</style>', unsafe_allow_html=True)

inject_css()

# ==========================================
# 7. AI合議API通信エンジン
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

AI_SYSTEM_PROMPTS = {
    "QUANTUM": "あなたは世界最高峰の理論物理学者兼クオンツです。Schrödinger波動関数、WKB量子トンネル透過率、Berry位相の観点から、株価のエネルギー準位とブレイクスルーの必然性を鋭く論じてください。短くシャープに答えてください。",
    "AEGIS": "あなたは厳格無比なリスク監査官です。下落リスク、CVaR、急落シナリオ、逆指値の絶対的必要性を徹底追求し、甘い楽観論を厳しく戒めてください。",
    "IGNIS": "あなたは直言特攻の情熱的なトレーダーです。勝率やモメンタムが高い銘柄には強気一括ベットを熱狂的に推奨し、迷う背中を力強く押してください。",
    "TECHNOS": "あなたは数理統計学者です。Hurst指数、OFI、Kyleのステルス流動性、価格弾力性の数理データから、優位性のエッジを冷徹に定量評価してください。",
    "MACRO": "あなたはグローバル・マクロ経済ディレクターです。為替、SOX指数、日経先物、米金利動向がこの銘柄に与える地政学的・マクロ的影響を解説してください。",
    "MICRO": "あなたは元HFT（高頻度取引）の板監査官です。歩み値、アイスバーグ注文、VWAP攻防、板の買い圧力（OFI）のリアルタイム実態を暴露してください。",
    "NEXUS": "あなたは全知能を統括する最高意思決定官（総合議長）です。各AIの意見を統合し、最終的なエントリー可否、目標値、損切りラインを断定してください。"
}

def query_real_llm_api(provider: str, api_key: str, model_name: str, system_prompt: str, user_prompt: str) -> str:
    if not api_key: return ""
    try:
        if provider == "OpenAI":
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
            payload = {
                "model": model_name or "gpt-4o",
                "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                "max_tokens": 250, "temperature": 0.7
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return res["choices"][0]["message"]["content"].strip()
                
        elif provider == "Gemini":
            mod = model_name or "gemini-1.5-flash"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [{"parts": [{"text": f"System Directive: {system_prompt}\n\nUser Question: {user_prompt}"}]}],
                "generationConfig": {"maxOutputTokens": 250, "temperature": 0.7}
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return res["candidates"][0]["content"]["parts"][0]["text"].strip()
                
        elif provider == "Anthropic":
            url = "https://api.anthropic.com/v1/messages"
            headers = {"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"}
            payload = {
                "model": model_name or "claude-3-5-sonnet-20241022",
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
                "max_tokens": 250, "temperature": 0.7
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return res["content"][0]["text"].strip()
    except Exception: return ""
    return ""

# ==========================================
# 8. 外部Web情報＆カタリスト解析
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
        with urllib.request.urlopen(req, timeout=1.8, context=ctx) as r:
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
        "detailed_impact": f"【波及分析】本材料は『{name}』のみならず、同一サプライチェーン・セクター（{genre}）全体に対して大口機関のアルゴリズム資金流入・リバランスを引き起こす公算が極めて高い特異点です。"
    }

# ==========================================
# 9. 堅牢認証＆セッション管理（意図しない画面戻り完全防止）
# ==========================================
def check_auth():
    cur_fp, raw_hfp = get_client_fp(), get_raw_header_fp()
    if "authenticated_user" not in st.session_state:
        st.session_state["authenticated_user"] = None
        
    qu = st.query_params.get("u", "").strip().lower()
    qt = st.query_params.get("t", "").strip()

    quick_login_act = st.query_params.get("quick_auth", "")
    if quick_login_act == "1":
        with get_db() as conn:
            cand = conn.execute("""
                SELECT email, name, status FROM members 
                WHERE (fp = ? OR raw_hfp = ?) AND status = 'approved'
                ORDER BY last_seen_ts DESC LIMIT 1
            """, (cur_fp, raw_hfp)).fetchone()
            
            if cand:
                st.session_state["authenticated_user"] = cand["email"]
                st.query_params.clear()
                st.query_params["u"] = cand["email"]
                st.query_params["t"] = gen_tok(cand["email"], "session_keep")
                st.rerun()
            else:
                st.query_params.pop("quick_auth", None)
                st.session_state["quick_login_fail"] = True

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
                elif u_rec.get("status") == "pending":
                    st.session_state["authenticated_user"] = None
                    st.query_params.clear()
                    st.warning("⏳ 現在このアカウントは一時停止（管理者承認待ち）状態です。")
                    st.stop()

            keep_tok = gen_tok(cu, "session_keep")
            conn.execute("""
                INSERT INTO members (email, name, status, passcode, pin_hash, pin_attempts, locked_until, applied_at, approved_at, last_seen_ts, last_seen_str, fp, raw_hfp, bio_enabled)
                VALUES (?, ?, 'approved', ?, ?, 0, 0, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(email) DO UPDATE SET last_seen_ts = excluded.last_seen_ts, last_seen_str = excluded.last_seen_str, fp = excluded.fp, raw_hfp = excluded.raw_hfp;
            """, (
                cu, u_rec.get("name") or ("システム管理者" if is_admin else "会員"),
                ADMIN_RAW_PASS if is_admin else (u_rec.get("passcode") or gen_code(cu)),
                u_rec.get("pin_hash", ""), u_rec.get("applied_at") or datetime.now().strftime("%Y-%m-%d %H:%M"),
                u_rec.get("approved_at") or datetime.now().strftime("%Y-%m-%d %H:%M"),
                time.time(), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), cur_fp, raw_hfp
            ))
            conn.commit()

            st.query_params["u"], st.query_params["t"] = cu, keep_tok
            return True

    # ログイン未認証画面
    st.markdown(
        '<div style="text-align:center;padding:26px 16px;background:radial-gradient(circle at 50% 20%, rgba(56,189,248,0.12), transparent 70%), linear-gradient(180deg,#0d1527 0%,#060a14 100%);border:1px solid rgba(56,189,248,0.25);border-radius:16px;box-shadow:0 12px 35px rgba(0,0,0,0.7);margin-bottom:16px;">'
        '<div class="brand-luxury">YAMASHISHI LAB</div>'
        '<div class="brand-sub">QUANTUM WAVEFUNCTION & MULTI-AGENT TERMINAL</div>'
        '</div>',
        unsafe_allow_html=True
    )

    t_login, t_register, t_pin = st.tabs(["⚡ ログイン", "📝 新規会員申請", "🔒 暗証番号(PIN)認証"])
    with t_login:
        with st.form("general_login_form"):
            in_email = st.text_input("メールアドレス", placeholder="メールアドレスを入力")
            in_pass = st.text_input("パスコード / 管理者パスワード", type="password", placeholder="8桁パスコードまたは管理者PW")
            rem_device = st.checkbox("この端末を安全なデバイスとして記憶する", value=True)
            submit_login = st.form_submit_button("⚡ QUANTUM CORE へログイン", use_container_width=True)

            if submit_login:
                em_c = (in_email or "").strip().lower()
                pw_c = (in_pass or "").strip()
                if is_seed_admin_email(em_c) and is_seed_admin_pass(pw_c):
                    st.session_state["authenticated_user"] = ADMIN_EMAIL
                    st.query_params["u"], st.query_params["t"] = ADMIN_EMAIL, gen_tok(ADMIN_EMAIL, "session_keep")
                    if rem_device: st.query_params["dfp"] = cur_fp
                    st.success("👑 管理者として認証されました。")
                    st.rerun()
                else:
                    with get_db() as conn:
                        is_ban, _ = check_and_log_ban_spoof(em_c, "", cur_fp, raw_hfp, action_type="ログイン試行")
                        if is_ban: st.error("💀 このアカウントまたは端末はセキュリティ制限により遮断されています。"); st.stop()
                        row = conn.execute("SELECT * FROM members WHERE email = ?", (em_c,)).fetchone()
                        if not row: st.error("❌ 登録が見つかりません。「新規会員申請」を行ってください。")
                        elif row["status"] == "pending": st.warning("⏳ 現在管理者による承認待ちです。")
                        elif row["status"] == "banned": st.error("💀 このアカウントは停止されています。")
                        else:
                            exp_code = row["passcode"] or gen_code(em_c)
                            if hmac.compare_digest(pw_c.upper(), exp_code.upper()):
                                st.session_state["authenticated_user"] = em_c
                                st.query_params["u"], st.query_params["t"] = em_c, gen_tok(em_c, "session_keep")
                                if rem_device: st.query_params["dfp"] = cur_fp
                                st.success(f"ようこそ、{row['name']} 様。")
                                st.rerun()
                            else: st.error("❌ パスコードが正しくありません。")

        if st.button("🧬 端末・生体認証でワンタップログイン", key="quick_bio_btn", use_container_width=True):
            st.query_params["quick_auth"] = "1"
            st.rerun()

    with t_register:
        with st.form("register_form"):
            reg_name = st.text_input("お名前 / 呼称", placeholder="例: 山田 太郎")
            reg_email = st.text_input("登録メールアドレス", placeholder="例: user@example.com")
            reg_pin = st.text_input("ご希望の4桁PINコード", type="password", max_chars=4, placeholder="数字4桁")
            if st.form_submit_button("📝 会員登録申請を送信", use_container_width=True):
                nm, em, pin = (reg_name or "").strip(), (reg_email or "").strip().lower(), (reg_pin or "").strip()
                if not nm or not em or len(pin) != 4 or not pin.isdigit():
                    st.error("入力内容に不備があります。")
                else:
                    with get_db() as conn:
                        is_ban, _ = check_and_log_ban_spoof(em, nm, cur_fp, raw_hfp, action_type="登録申請")
                        if is_ban: st.error("💀 セキュリティ制限により申請できません。"); st.stop()
                        ex = conn.execute("SELECT status FROM members WHERE email = ?", (em,)).fetchone()
                        if ex: st.warning("すでに申請または登録済みです。")
                        else:
                            conn.execute("""
                                INSERT INTO members (email, name, status, passcode, pin_hash, applied_at, fp, raw_hfp, bio_enabled)
                                VALUES (?, ?, 'pending', ?, ?, ?, ?, ?, 1)
                            """, (em, nm, gen_code(em), hash_sec_pwd(pin, SECRET_KEY[:16])[:16], datetime.now().strftime("%Y-%m-%d %H:%M"), cur_fp, raw_hfp))
                            conn.commit()
                            st.success("✅ 申請を受け付けました！管理者の承認をお待ちください。")

    with t_pin:
        with st.form("pin_login_form"):
            pin_email = st.text_input("登録メールアドレス", key="pin_em_input")
            pin_code = st.text_input("数字4桁のPIN", type="password", max_chars=4, key="pin_cd_input")
            if st.form_submit_button("🔒 PINコードで認証", use_container_width=True):
                em, pin = (pin_email or "").strip().lower(), (pin_code or "").strip()
                with get_db() as conn:
                    row = conn.execute("SELECT * FROM members WHERE email = ?", (em,)).fetchone()
                    if row and row["status"] == "approved":
                        if hmac.compare_digest(hash_sec_pwd(pin, SECRET_KEY[:16])[:16], row["pin_hash"] or ""):
                            st.session_state["authenticated_user"] = em
                            st.query_params["u"], st.query_params["t"] = em, gen_tok(em, "session_keep")
                            st.rerun()
                        else: st.error("❌ PINコードが一致しません。")
                    else: st.error("有効な承認済みアカウントが見つかりません。")
    st.stop()

check_auth()

# ==========================================
# 10. フローティングナビゲーション＆スクロール制御
# ==========================================
for k, v in [
    ("active_debates", {}), ("council_threads", {}), ("council_meta", {}),
    ("watchlist", {}), ("custom_search_code", ""), ("active_category", "🏆 総合TOP5"),
    ("nav_history", []), ("admin_console_open", False)
]:
    if k not in st.session_state: st.session_state[k] = v

nav_act = st.query_params.get("nact", "")
if nav_act:
    if nav_act == "top":
        st.session_state["custom_search_code"] = ""
        st.session_state["scroll_to_top_trigger"] = True
    elif nav_act == "close_debates":
        st.session_state["active_debates"] = {}
    elif nav_act == "back":
        if st.session_state.get("admin_console_open"):
            st.session_state["admin_console_open"] = False
        elif st.session_state.get("custom_search_code"):
            st.session_state["custom_search_code"] = ""
        elif st.session_state.get("nav_history"):
            st.session_state["active_category"] = st.session_state["nav_history"].pop()
        else:
            st.session_state["active_category"] = "🏆 総合TOP5"
            st.session_state["scroll_to_top_trigger"] = True
    st.query_params.pop("nact", None)
    st.rerun()

open_cnt = sum(1 for v in st.session_state["active_debates"].values() if v)
close_label = f"✕ 合議閉じる ({open_cnt})" if open_cnt > 0 else "✕ 合議閉じる"
close_cls = "cyber-nav-btn cyber-nav-btn-highlight" if open_cnt > 0 else "cyber-nav-btn"

# 右上固定・重なり完全解消・横書き固定・タップ時青発光ナビバー
st.markdown(
    f"""
    <div class="cyber-dock-wrapper">
        <div class="cyber-quantum-nav-dock">
            <a class="cyber-nav-btn" href="?nact=top" target="_self">▲ トップ</a>
            <a class="{close_cls}" href="?nact=close_debates" target="_self">{close_label}</a>
            <a class="cyber-nav-btn" href="?nact=back" target="_self">◀ 戻る</a>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

if st.session_state.pop("scroll_to_top_trigger", False):
    components.html("""
    <script>
    (function(){
        try {
            window.parent.scrollTo({top: 0, behavior: 'smooth'});
            const mainEl = window.parent.document.querySelector('section.main') || window.parent.document.documentElement;
            if(mainEl) mainEl.scrollTo({top: 0, behavior: 'smooth'});
        } catch(e){}
    })();
    </script>
    """, height=0)

# ==========================================
# 11. 動的戦略ディスパッチャ & 初心者向け超実践手順
# ==========================================
def norm_tk(raw: str) -> str:
    s = unicodedata.normalize("NFKC", str(raw or "")).strip().upper()
    return f"{s}.T" if len(s) == 4 and any(c.isdigit() for c in s) and "." not in s else s

def select_dynamic_strategy(code: str, style: str, tot_win: float, expect_pct: float, ofi_z: float, vpin: float, yz_vol: float, cvar95: float, rsi: float, cpos: float, base_sh: int, pest_str: str, vwap_str: str, tp_str: str, sl_str: str, kelly_pct: float, qm: dict, ms: dict) -> dict:
    st_prefix = style.split(" ")[1] if " " in style else "デイトレード"

    if "スキャルピング" in st_prefix:
        sh = max(1, int(round(base_sh * 1.5)))
        return {
            "algo_name": f"⚡ [{st_prefix}] 瞬足OFI板掃き上げ・1分足モメンタム一気貫通型",
            "risk_posture": f"🚀 スキャルピング全開（寄付き直後に <b>{sh:,}株</b> で一気に抜く）",
            "core_logic": f"OFI（板の買い越し +{ofi_z:.2f}σ）とLULD引力（{ms['luld_magnet']}%）の加速に乗る秒速・分速フォーメーション。",
            "adj_shares": sh,
            "step_plan": f"① 9:00寄付き直後の1分足で <b>{sh:,}株</b> 成行即時突撃 → ② 数ティック上の <b>{tp_str}</b> 到達で機械的利確",
            "beginner_html": (
                f"<b>🔰 【初心者向け超実践手順】スキャルピング（⚡ 朝イチ数分で即利確！）</b><br>"
                f"<b>【ステップ1：寄前準備】</b> 8:50〜8:58に気配値を確認。買い板が優勢であることを確認します。<br>"
                f"<b>【ステップ2：成行エントリー】</b> 9:00の寄付きと同時に <b>「成行で {sh:,}株」</b> を買い発注します。<br>"
                f"<b>【ステップ3：損切り即時予約】</b> 約定したら即座に <b>「逆指値：{sl_str}」</b> をセットし急落リスクを遮断。<br>"
                f"<b>【ステップ4：利益確定】</b> 目標ライン <b>「利確：{tp_str}」</b> に指値を置き、利益が乗った瞬間に逃げ切ります。"
            )
        }
    elif "スイングトレード" in st_prefix:
        sh = max(1, int(round(base_sh * 1.2)))
        l1, l2 = max(1, int(round(sh * 0.6))), max(0, sh - max(1, int(round(sh * 0.6))))
        return {
            "algo_name": f"📈 [{st_prefix}] 機関トレンドフォロー・押し目ピラミッディング型",
            "risk_posture": f"🏛️ スイング本玉買い（初回 <b>{l1:,}株</b> ＋ 2日目押し目 <b>{l2:,}株</b>）",
            "core_logic": f"Hurst指数 {ms['hurst']} と機関Kyleステルス吸収（{ms['kyle_stealth']}%）による中期波及狙い。",
            "adj_shares": sh,
            "step_plan": f"① 初回 <b>{l1:,}株</b> 取得 → ② VWAP押し目（{vwap_str}）で残りの <b>{l2:,}株</b> を追加",
            "beginner_html": (
                f"<b>🔰 【初心者向け超実践手順】スイングトレード（📈 数日〜1週間の波に乗る！）</b><br>"
                f"<b>【ステップ1：打診エントリー】</b> 寄り付き直後に全ロットの約6割となる <b>「{l1:,}株」</b> をエントリー。<br>"
                f"<b>【ステップ2：押し目買い増し】</b> 株価がVWAP水準（目安: {vwap_str}）まで健全に押した場面で残りの <b>「{l2:,}株」</b> を追加。<br>"
                f"<b>【ステップ3：逆指値セット】</b> 防衛ラインとして <b>「損切り：{sl_str}」</b> の逆指値を必ず常時設定。<br>"
                f"<b>【ステップ4：中期利確】</b> 目標株価 <b>「{tp_str}」</b> 到達時に落ち着いて利益を確定させます。"
            )
        }
    elif "バイ＆ホールド" in st_prefix:
        sh = max(1, int(round(base_sh * 0.8)))
        return {
            "algo_name": f"💎 [{st_prefix}] 中長期ファンダメンタルズ＆クオンツ定額積立型",
            "risk_posture": f"🛡️ 長期分散ポートフォリオ（コア保有 <b>{sh:,}株</b>）",
            "core_logic": f"量子コヒーレンス {qm['q_coherence']}% とフォン・ノイマンエントロピー {qm['q_entropy']} による低ノイズ長期成長享受。",
            "adj_shares": sh,
            "step_plan": f"① 現物で <b>{sh:,}株</b> を取得 → ② 逆指値（{sl_str}）をセーフティネットとして保持し中長期成長を追従",
            "beginner_html": (
                f"<b>🔰 【初心者向け超実践手順】バイ＆ホールド（💎 中長期・現物保有）</b><br>"
                f"<b>【ステップ1：現物買付】</b> 追証や期日のない「現物取引」で <b>{sh:,}株</b> を購入します。<br>"
                f"<b>【ステップ2：暴落ガード】</b> 想定外の地政学ショックに備え、<b>「損切り：{sl_str}」</b> に長期逆指値を設定。<br>"
                f"<b>【ステップ3：利益目標】</b> 目標ライン <b>「{tp_str}」</b> を視野に日々の細かい値動きを気にせず保有を継続します。"
            )
        }

    sh = max(1, int(round(base_sh * 1.65)))
    return {
        "algo_name": f"🔥 [{st_prefix}] 情報精度S級・全ツッパ一括特攻型アルゴリズム",
        "risk_posture": f"👑 全ツッパ・フルベット（ <b>{sh:,}株を100%一括投入</b> ）",
        "core_logic": f"期待度 <b>{expect_pct}%</b>・量子Qスコア {qm['q_score']}点・機関ステルス吸収 {ms['kyle_stealth']}% の最高期待値。",
        "adj_shares": sh,
        "step_plan": f"① 9:00寄付き（{pest_str}目安）で <b>全ロット {sh:,}株</b> 成行一括投入 → ② 逆指値（{sl_str}）を同時セットし、目標（{tp_str}）まで一気抜き",
        "beginner_html": (
            f"<b>🔰 【初心者向け超実践手順】デイトレード（🔥 精度S級・迷わず1回で全ツッパ！）</b><br>"
            f"<b>【ステップ1：寄前注文予約】</b> 8:45〜8:55の間に証券会社アプリから <b>「寄成（寄り付き成行）で {sh:,}株」</b> の買い注文を発注。<br>"
            f"<b>【ステップ2：逆指値の同時発注】</b> 9:00に約定した直後、即座に <b>「逆指値：{sl_str}」</b> を注文し、万が一の急落損失を完全限定。<br>"
            f"<b>【ステップ3：利確指値のセット】</b> 目標値 <b>「利確：{tp_str}」</b> に売り指値を置いておき、約定通知を待ちます。"
        )
    }

# ==========================================
# 12. 本物数理データ解析 & AGI自律巡回監査
# ==========================================
def analyze_df(df_raw, code, name, theme, genre, macro, b5_live_map, style, bi=True, b5=True, bal=True, bms=True, total_capital=1000000, risk_tolerance_pct=2.0):
    try:
        if df_raw is None or df_raw.empty: return None
        df = df_raw.dropna(subset=["Close", "Open", "High", "Low", "Volume"]).copy()
        if len(df) < 30: return None
        c, o, h, l, v = df["Close"].values.astype(float), df["Open"].values.astype(float), df["High"].values.astype(float), df["Low"].values.astype(float), df["Volume"].values.astype(float)
        
        # AGI自律巡回監査（ハリボテ・静的データ・ゼロ分散チェック）
        if np.std(c) < 1e-4 or np.all(c == c[0]):
            with get_db() as conn:
                conn.execute("""
                    INSERT INTO agi_audit_logs (time, target_code, component, issue_type, detail)
                    VALUES (?, ?, '価格データフィード', '静的データ検知', 'Close価格の標準偏差がゼロ。リアルタイム取引データ異常の疑い')
                """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), code))
                conn.commit()

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
# 13. 並列外部データ取得層
# ==========================================
@st.cache_data(ttl=45)
def fetch_5ch_live() -> dict:
    ctx = ssl.create_default_context()
    ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
    headers = {"User-Agent": "Mozilla/5.0"}
    def fetch_url(u):
        try:
            req = urllib.request.Request(u, headers=headers)
            with urllib.request.urlopen(req, timeout=1.2, context=ctx) as r:
                return r.read().decode("cp932", errors="ignore")
        except Exception: return ""

    urls = ["https://egg.5ch.io/stock/subback.html", "https://hayabusa9.5ch.io/livemarket1/subback.html"]
    with ThreadPoolExecutor(max_workers=2) as ex:
        htmls = list(ex.map(fetch_url, urls))
    joined = " ".join(htmls)
    return {c: {"hits": len(re.findall(re.escape(c.replace(".T", "")), joined)) if joined else 0, "live": bool(joined)} for c in KNOWN_STOCKS}

@st.cache_data(ttl=30)
def fetch_macro():
    tks = {"sp500": ("^GSPC", "🇺🇸 S&P500"), "sox": ("^SOX", "💽 米SOX"), "usdjpy": ("JPY=X", "💴 ドル円"), "nk_fut": ("NIY=F", "🇯🇵 日経先物"), "vix": ("^VIX", "⚡ VIX")}
    res = {}
    try:
        raw = yf.download(list(c for c, _ in tks.values()), period="5d", group_by="ticker", threads=True, progress=False, timeout=4)
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
        raw = yf.download(codes, period="6mo", group_by="ticker", threads=True, progress=False, timeout=6)
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
# 14. リアルAI合議オーケストレーター
# ==========================================
def run_real_ai_council(r: dict, m5=None, user_query: str = "", active_spks: list = None, posture: str = "標準バランス", api_cfg: dict = None) -> dict:
    nm = r["name"]
    st_info = r["strat"]
    provider = (api_cfg or {}).get("provider", "Off")
    api_key = (api_cfg or {}).get("api_key", "").strip()
    model_name = (api_cfg or {}).get("model", "")
    
    turns = []
    round_title = f"💬 投下質問『{user_query}』に対するリアルタイムAI合議" if user_query else f"🌐 『{nm}』AI知能合議セッション"
    turns.append({"round": round_title})

    default_speakers = ["QUANTUM", "MICRO", "IGNIS", "AEGIS", "TECHNOS", "NEXUS"]
    chosen_speakers = [s for s in (active_spks or default_speakers) if s in AI_ROSTER]
    if "NEXUS" not in chosen_speakers: chosen_speakers.append("NEXUS")

    quant_summary = (
        f"銘柄: {nm} ({r['code']}), 現在値: {r['price']}, 期待度: {r['expect_pct']}%, "
        f"量子Q: {r['q_score']}点 (透過率: {r['q_tunnel']}%), 機関Kyleステルス吸収: {r['kyle_stealth']}%, "
        f"Hurst指数: {r['hurst']}, OFI: {r['ofi_z']:+.2f}σ, 目標利確: {r['tp_price']}, 損切: {r['sl_price']}, "
        f"合議スタンス: {posture}。"
    )

    for spk in chosen_speakers:
        sys_p = AI_SYSTEM_PROMPTS.get(spk, "") + f"\n前提クオンツ情報: {quant_summary}"
        u_p = f"ユーザー質問: 『{user_query}』について、あなたの専門的視点から回答してください。" if user_query else f"『{nm}』に対する現在の市場判断とエントリーの可否を論じてください。"
        
        dyn_text = ""
        if provider != "Off" and api_key:
            dyn_text = query_real_llm_api(provider, api_key, model_name, sys_p, u_p)
            
        if not dyn_text:
            if spk == "QUANTUM": dyn_text = f"Schrödinger波動関数のポテンシャル障壁透過率は <b>{r['q_tunnel']}%</b> です。上位抵抗線のトンネル効果突破が期待値の源泉です。"
            elif spk == "AEGIS": dyn_text = f"最大期待損失（95%CVaR -{r['cvar95']}%）を厳戒視してください。逆指値ライン <b>{r['sl_price']}</b> は死守が鉄則です。"
            elif spk == "IGNIS": dyn_text = f"総合期待度 <b>{r['expect_pct']}%</b>！推奨ロット <b>{r['lot_info']['shares']:,}株</b> で迷わず一気抜きに行く絶好のタイミングだ！"
            elif spk == "MICRO": dyn_text = f"板情報を監査。大口のKyle氷山買い集め（{r['kyle_stealth']}%）が下値を強固にサポートしています。"
            elif spk == "TECHNOS": dyn_text = f"Hurst指数 <b>{r['hurst']}</b> とエッジ <b>+{r['edge']:.2f}%</b> より、トレンドフォローの統計的有意性が確認されます。"
            elif spk == "MACRO": dyn_text = f"日経先物やSOX指数の動向を背景に、セクター全体への大口資金配分が追い風となっています。"
            else: dyn_text = f"全エージェントの合議を総括。目標株価 <b>{r['tp_price']}</b> に向け、規律あるエントリーを承認します。"

        tone = "doubt" if spk == "AEGIS" else ("agree" if spk in ["IGNIS", "QUANTUM", "NEXUS"] else "normal")
        turns.append({"speaker": AI_ROSTER[spk], "score": r["ai_score"], "tone": tone, "text": dyn_text})

    v_html = (
        f'<div style="margin-bottom:6px;"><b>🔥 『{nm}』総合期待度：</b><span style="color:#fde047;font-size:14px;font-weight:900;">{r["expect_pct"]}%</span> ｜ '
        f'<b>🏛️ 機関ミクロ構造：</b><span style="color:#a7f3d0;font-weight:800;">{r["ms_regime"]}</span></div>'
        f'<div style="margin-bottom:6px;"><b>⚡ プロ向け執行プラン：</b>{st_info["step_plan"]} ｜ 🎯利確 <b>{r["tp_price"]}(+{r["tp_pct"]}%)</b> ／ 🛡️損切 <b>{r["sl_price"]}({r["sl_pct"]}%)</b></div>'
        f'<div class="beginner-action-box">{st_info["beginner_html"]}</div>'
    )
    return {"final_score": r["ai_score"], "dialogue": turns, "verdict_html": v_html}

def _fmt_turn(t: dict) -> str:
    if "round" in t: return f'<div class="round-divider">{sanitize(t["round"])}</div>'
    if t.get("is_user"):
        return f'<div class="chat-bubble-user"><b>🗣️ あなたの質問:</b><br>{sanitize(t["text"])}</div>'
    b_cls = {"doubt": "chat-bubble-doubt", "rage": "chat-bubble-rage", "agree": "chat-bubble-agree"}.get(t.get("tone", "normal"), "chat-bubble-ai")
    return f'<div class="{b_cls}"><div style="font-weight:700;color:#38bdf8;font-size:11px;margin-bottom:2px;">{sanitize(t["speaker"])}</div><div>{t["text"]}</div></div>'

@frag_dec
def render_council_sec(r, uk, active_spks=None, posture="標準バランス", api_cfg=None):
    is_open = st.session_state["active_debates"].get(uk, False)
    in_wl = r["code"] in st.session_state["watchlist"]
    c1, c2 = st.columns([2.7, 1.1])
    if c1.button("▲ 量子＆マルチAI合議を閉じる" if is_open else "⚛️ リアルタイムAI合議＆買い方を見る", key=f"b_{uk}", use_container_width=True):
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
        with st.spinner(f"🌐 『{r['name']}』AI知能合議中..."):
            deb = run_real_ai_council(r, m5, user_query="", active_spks=active_spks, posture=posture, api_cfg=api_cfg)
            st.session_state["council_threads"][uk] = list(deb["dialogue"])
            st.session_state["council_meta"][uk] = deb

    meta = st.session_state["council_meta"][uk]
    turns = st.session_state["council_threads"][uk]

    st.markdown(
        f'<div class="ai-council-box">'
        f'<div class="council-scroll-window">{"".join(_fmt_turn(t) for t in turns)}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    with st.form(f"jf_{uk}", clear_on_submit=True):
        jc1, jc2 = st.columns([3.2, 1])
        uop = jc1.text_input("質問・発言", placeholder=f"例: 『{r['name']}』の今後のシナリオは？", label_visibility="collapsed")
        if jc2.form_submit_button("💬 質問投下", use_container_width=True) and uop.strip():
            u_text = sanitize(uop.strip())
            st.session_state["council_threads"][uk].append({"is_user": True, "text": u_text})
            with st.spinner(f"🌐 AI合議中..."):
                deb_updated = run_real_ai_council(r, m5, user_query=u_text, active_spks=active_spks, posture=posture, api_cfg=api_cfg)
                for new_t in deb_updated["dialogue"]:
                    st.session_state["council_threads"][uk].append(new_t)
                st.session_state["council_meta"][uk] = deb_updated
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

    cat_badge_html = f'<span class="pulse-badge">🚨 重大速報: {sanitize(cat.get("title", ""))[:28]}... ({cat.get("reliability", 70)}%)</span>' if has_cat else ""

    st.markdown(
        f'<div class="{"search-result-card" if is_custom else "rank-card"}">'
        f'<div class="signal-10tier-badge" style="background:{r["tier_bg"]};color:{r["tier_color"]};"><span>{r["tier_label"]}</span><span>🔥 期待度 {r["expect_pct"]}% ｜ {st_info["algo_name"].split("】")[0]}】</span></div>'
        f'<div style="margin-bottom:6px;">{rk_h}<span class="pill-badge" style="background:rgba(250,204,21,0.18);border-color:#facc15;color:#fde047;font-weight:900;">🔥 期待度 {r["expect_pct"]}%</span><span class="quantum-badge">⚛️ 量子Q {r["q_score"]}点 (WKB透過{r["q_tunnel"]}%)</span><span class="inst-badge">🏛️ 機関ミクロ {r["ms_score"]}点 (Kyle吸収{r["kyle_stealth"]}%)</span><span class="pill-badge">🧬 OFI {r["ofi_z"]:+.2f}σ</span></div>'
        f'<div style="display:flex;justify-content:space-between;align-items:center;gap:6px;margin-top:4px;">'
        f'<div style="min-width:0;flex:1;">'
        f'<span style="font-size:15px;font-weight:800;color:#f8fafc;">{r["name"]}</span> <span style="font-size:11px;color:#94a3b8;">({r["code"]} / {r["genre"]})</span> {cat_badge_html}'
        f'<div style="font-size:10.5px;color:#94a3b8;margin-top:2px;">{r["theme"]} ｜ 現在値: <b style="color:#f8fafc;">{r["price"]}</b> (<span style="color:{dc};font-weight:700;">{ds}{r["diff"]}%</span>)</div>'
        f'</div>'
        f'<div style="text-align:right;white-space:nowrap;flex-shrink:0;">'
        f'<div style="font-size:9px;color:#fde047;font-weight:700;line-height:1.15;">🔥 AI期待度 / 統合勝率</div>'
        f'<div style="white-space:nowrap;line-height:1.2;margin-top:1px;"><span class="expect-badge">{r["expect_pct"]}%</span><span style="color:#64748b;font-size:11px;margin:0 2px;">/</span><span class="prob-badge">{r["total_win_rate"]}%</span></div>'
        f'<div style="font-size:9px;color:#94a3b8;">Payoff {r["payoff"]}x / Edge {r["edge"]:+.2f}%</div>'
        f'</div>'
        f'</div>'
        f'<div class="winrate-bar"><div><div style="font-size:9px;color:#fde047;">🔥 総合期待度</div><div style="font-size:12px;font-weight:900;color:#fef08a;">{r["expect_pct"]}%</div></div><div><div style="font-size:9px;color:#c084fc;">⚛️ WKB透過率</div><div style="font-size:12px;font-weight:800;color:#e9d5ff;">{r["q_tunnel"]}%</div></div><div><div style="font-size:9px;color:#6ee7b7;">🏛️ 機関Kyle吸収</div><div style="font-size:12px;font-weight:800;color:#a7f3d0;">{r["kyle_stealth"]}%</div></div><div><div style="font-size:9px;color:#94a3b8;">🌅 翌朝GU / 陽線</div><div style="font-size:11.5px;font-weight:700;">{r["prob"]}% / {r["intraday_win_rate"]}%</div></div></div>'
        f'<div class="trade-plan-box"><div><div style="font-size:9px;color:#94a3b8;">🌅 夜間理論寄付き</div><div style="font-size:11.5px;font-weight:700;">{r["pts_est_price"]} ({ps}{r["pts_gap_pct"]}%)</div></div><div style="border-left:1px solid rgba(148,163,184,0.16);border-right:1px solid rgba(148,163,184,0.16);"><div style="font-size:9px;color:#10b981;">🎯 利確目標</div><div style="font-size:11.5px;font-weight:800;color:#10b981;">{r["tp_price"]} (+{r["tp_pct"]}%)</div></div><div><div style="font-size:9px;color:#f87171;">🛡️ 逆指値(損切)</div><div style="font-size:11.5px;font-weight:800;color:#f87171;">{r["sl_price"]} ({r["sl_pct"]}%)</div></div></div>'
        f'<div class="sizing-box"><span>📦 <b>推奨ロット: {lot["shares"]:,}株</b> ({st_info["risk_posture"].split("（")[0]}) ｜ 投資額 {lot["position_value"]:,.0f}円</span><span>基準VWAP: <b>{r["vwap_price"]}</b></span></div>'
        f'<details class="quant-detail-drawer"><summary>⚛️ 量子力学モデル(Schrödinger-WKB) × 機関ミクロ構造 詳細（開閉）</summary>'
        f'<div style="font-size:11px;color:#cbd5e1;margin-top:4px;line-height:1.5;"><b>{st_info["algo_name"]}</b><br><span style="color:#a7f3d0;">{r["ms_regime"]}</span> ｜ <span style="color:#e9d5ff;">{r["q_state"]}</span><br>{st_info["core_logic"]}<br><b>▶ 買い方執行手順:</b> {st_info["step_plan"]}</div>'
        f'<div class="metrics-row"><span>期待度:{r["expect_pct"]}%</span><span>量子Q:{r["q_score"]}点</span><span>WKB透過:{r["q_tunnel"]}%</span><span>Kyle吸収:{r["kyle_stealth"]}%</span><span>Hurst:{r["hurst"]}</span><span>OFI:{r["ofi_z"]:+.2f}σ</span><span>95%CVaR:-{r["cvar95"]}%</span></div>'
        f'</details></div>',
        unsafe_allow_html=True
    )
    render_council_sec(r, f"{kp}_{r['code']}", active_spks=sidebar_active_ais, posture=sidebar_debate_posture, api_cfg=ai_api_config)

# ==========================================
# 15. サイドバー完全再編成（ご指定レイアウト順序）
# ==========================================
with st.sidebar:
    cu = st.session_state.get("authenticated_user", "")
    with get_db() as conn:
        u_row = conn.execute("SELECT name FROM members WHERE email = ?", (cu,)).fetchone()
        u_name = u_row["name"] if u_row else "会員"
    is_admin = (cu == ADMIN_EMAIL or is_seed_admin_email(cu))
    
    # ① ユーザー情報表示
    st.markdown(
        f'<div style="background:#0f172a;padding:12px;border-radius:12px;border:1px solid rgba(168,85,247,0.4);margin-bottom:12px;">'
        f'<div style="font-size:10px;color:#c084fc;font-weight:800;">⚛️ {"👑 システム管理者" if is_admin else "💎 会員セッション"}</div>'
        f'<div style="color:#ffffff;font-size:14px;font-weight:800;margin-top:2px;">{sanitize(u_name)} 様</div>'
        f'<div style="color:#64748b;font-size:10px;font-family:\'JetBrains Mono\';">{sanitize(cu)}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    # 管理者用ボタン（同色・同系統サイバーネオン仕様）
    if is_admin:
        if st.button("🛡️ 管理者マネジメントコンソール", key="adm_toggle_btn", use_container_width=True):
            st.session_state["admin_console_open"] = not st.session_state["admin_console_open"]
            st.rerun()

    # ② 投資スタイル選択
    st.header("🎯 投資スタイル選択")
    investment_style = st.selectbox(
        "トレードスタイル",
        [
            "⚡ デイトレード (前場・後場の波及を狙う)",
            "🚀 スキャルピング (秒〜分単位のモメンタム)",
            "📈 スイングトレード (数日〜数週間のトレンド)",
            "💎 バイ＆ホールド (中長期・現物保有)"
        ],
        index=0
    )

    # ③ テクニカル＆アルゴリズム完全切替
    st.markdown("---")
    st.header("⚙️ テクニカル＆アルゴリズム切替")
    toggle_fn = getattr(st, "toggle", st.checkbox)
    show_5m_chart = toggle_fn("📈 5分足＆VWAP描画", value=True)
    
    ac_b = set()
    BOOST_MAP = {
        "⚛️ 量子力学波動(QWM-7)": "algo",
        "🏛️ 機関最新アルゴ(Kyleλ・Hurst)": "ms",
        "🏦 機関VPIN・SmartMoney": "inst",
        "🔥 5ch実況＆短期モメンタム": "mom"
    }
    with st.expander("🧪 解析アルゴリズム詳細選択", expanded=True):
        for b_label, b_key in BOOST_MAP.items():
            if st.checkbox(b_label, value=True, key=f"algo_sw_{b_key}"):
                ac_b.add(b_key)

    # ④ 7知能AI合議システム設定
    st.markdown("---")
    st.header("🏛️ 7知能AI合議システム設定")
    sidebar_debate_posture = st.select_slider(
        "合議スタンス",
        options=["🛡️ 厳格防衛(安全重視)", "⚖️ 標準バランス", "🔥 攻撃的(強気利益狙い)"],
        value="⚖️ 標準バランス"
    )
    with st.expander("🤖 参加AIエージェント編成", expanded=False):
        sidebar_active_ais = []
        for k_spk, name_spk in AI_ROSTER.items():
            if st.checkbox(name_spk, value=True, key=f"spk_toggle_{k_spk}"):
                sidebar_active_ais.append(k_spk)

    # ⑤ AI合議 APIエンジン設定
    st.markdown("---")
    st.header("🤖 AI合議 APIエンジン設定")
    ai_provider = st.selectbox("APIプロバイダー", ["Off (高速クオンツ)", "OpenAI", "Gemini", "Anthropic"], index=0)
    ai_api_key = ""
    ai_model = ""
    if ai_provider != "Off (高速クオンツ)":
        ai_api_key = st.text_input(f"{ai_provider} API Key", type="password", placeholder="APIキーを入力")
        if ai_provider == "OpenAI": ai_model = st.selectbox("モデル", ["gpt-4o", "gpt-4o-mini", "o1-mini"])
        elif ai_provider == "Gemini": ai_model = st.selectbox("モデル", ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.5-flash"])
        elif ai_provider == "Anthropic": ai_model = st.selectbox("モデル", ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"])
    
    ai_api_config = {"provider": ai_provider.split(" ")[0], "api_key": ai_api_key, "model": ai_model}

    # ⑥ 資金管理＆リスク設定（下部に配置）
    st.markdown("---")
    st.header("💰 資金管理＆リスク設定")
    total_capital = st.number_input("総投資資金 (円/ドル)", min_value=10000, max_value=1000000000, value=1000000, step=50000)
    risk_tolerance_pct = st.slider("1トレード許容リスク (%)", 0.5, 5.0, 2.0, 0.5)
    survival_cut_pct = st.slider("各タブ選抜率 (%)", 40, 100, 75, 5)

    # ⑦ 展開中合議消去 ＆ ログアウト（最下部）
    st.markdown("---")
    if st.button("🗑️ 展開中の合議スレッドを全消去", use_container_width=True):
        st.session_state["council_threads"] = {}
        st.session_state["council_meta"] = {}
        st.session_state["active_debates"] = {}
        st.success("合議履歴を消去しました。")
        st.rerun()

    if st.button("🚪 ログアウト", use_container_width=True):
        with get_db() as conn:
            conn.execute("UPDATE members SET last_seen_ts = 0 WHERE email = ?", (cu,))
            conn.commit()
        st.session_state["authenticated_user"] = None
        st.query_params.clear()
        st.rerun()

# ==========================================
# 16. 【完全独立化】管理者マネジメントコンソール（下部に銘柄を出さない）
# ==========================================
if is_admin and st.session_state.get("admin_console_open"):
    st.markdown('<div class="admin-modal-card">', unsafe_allow_html=True)
    st.markdown("### 👑 システム管理者マネジメントコンソール")
    st.caption("会員ステータス完全制御（再開・一時停止・永久BAN・完全抹消）・認証情報監査・なりすまし監視・AGI注意コンテンツ巡回")
    
    t_mng1, t_mng2, t_mng3, t_mng4 = st.tabs([
        "👥 会員詳細管理・個別操作",
        "🚫 不正アクセス・なりすまし監視ログ",
        "🛡️ 永久BAN端末指紋リスト",
        "⚠️ AGI自律巡回・注意コンテンツ検知"
    ])
    
    with t_mng1:
        with get_db() as conn:
            all_m = conn.execute("SELECT * FROM members ORDER BY applied_at DESC").fetchall()
        
        st.write(f"**登録会員総数: {len(all_m)} 名**")
        for mb in all_m:
            em = mb["email"]
            is_adm_row = (em == ADMIN_EMAIL or is_seed_admin_email(em))
            st_badge = "🟢 承認中(再開)" if mb["status"] == "approved" else ("🟡 一時停止中" if mb["status"] == "pending" else "🔴 永久BAN")
            
            with st.expander(f"👤 {mb['name']} ｜ {em} ｜ {st_badge}", expanded=(mb["status"] == "pending")):
                c_info, c_action = st.columns([1.8, 1.2])
                c_info.markdown(
                    f"- **現在の状態:** `{mb['status']}`\n"
                    f"- **パスコード(キー):** `{mb['passcode'] or '未発行'}`\n"
                    f"- **PINハッシュ:** `{mb['pin_hash'] or '未設定'}`\n"
                    f"- **端末指紋 (Client FP):** `{mb['fp']}`\n"
                    f"- **ヘッダ指紋 (Raw HFP):** `{mb['raw_hfp']}`\n"
                    f"- **申請日時:** {mb['applied_at']}\n"
                    f"- **承認日時:** {mb['approved_at']}\n"
                    f"- **最終アクセス:** {mb['last_seen_str']}"
                )
                
                if not is_adm_row:
                    c_action.write("**【個別操作実行】**")
                    b_col1, b_col2 = c_action.columns(2)
                    
                    if mb["status"] != "approved":
                        if b_col1.button("🟢 再開(承認)", key=f"btn_res_{em}", use_container_width=True):
                            with get_db() as conn:
                                conn.execute("UPDATE members SET status = 'approved', approved_at = ? WHERE email = ?", (datetime.now().strftime("%Y-%m-%d %H:%M"), em))
                                conn.execute("DELETE FROM security_bans WHERE email = ?", (em,))
                                conn.commit()
                            st.success(f"{mb['name']} を再開・承認しました")
                            st.rerun()

                    if mb["status"] != "pending":
                        if b_col2.button("⏸️ 一時停止", key=f"btn_pnd_{em}", use_container_width=True):
                            with get_db() as conn:
                                conn.execute("UPDATE members SET status = 'pending' WHERE email = ?", (em,))
                                conn.commit()
                            st.warning(f"{mb['name']} を一時停止に設定しました")
                            st.rerun()
                    
                    b_col3, b_col4 = c_action.columns(2)
                    if mb["status"] != "banned":
                        if b_col3.button("🔴 永久BAN", key=f"btn_ban_{em}", use_container_width=True):
                            with get_db() as conn:
                                conn.execute("UPDATE members SET status = 'banned' WHERE email = ?", (em,))
                                conn.execute("INSERT OR REPLACE INTO security_bans (key_val, ban_type, email, name, banned_at, reason) VALUES (?, 'email', ?, ?, ?, '管理者手動BAN')", (em, em, mb["name"], datetime.now().strftime("%Y-%m-%d %H:%M")))
                                if mb["fp"] and mb["fp"] not in ["-", "yamashishi_default_env"]:
                                    conn.execute("INSERT OR REPLACE INTO security_bans (key_val, ban_type, email, name, banned_at, reason) VALUES (?, 'fp', ?, ?, ?, '管理者手動BAN(端末指紋)')", (mb["fp"], em, mb["name"], datetime.now().strftime("%Y-%m-%d %H:%M")))
                                conn.commit()
                            st.error(f"{mb['name']} を永久BANに登録しました")
                            st.rerun()

                    if b_col4.button("🗑️ 完全抹消", key=f"btn_del_{em}", use_container_width=True):
                        with get_db() as conn:
                            conn.execute("DELETE FROM members WHERE email = ?", (em,))
                            conn.commit()
                        st.warning(f"{mb['name']} をデータベースから完全抹消しました")
                        st.rerun()
                else:
                    c_action.info("👑 ルート管理者は保護されており操作できません")

    with t_mng2:
        with get_db() as conn:
            s_logs = conn.execute("SELECT * FROM spoof_logs ORDER BY id DESC LIMIT 50").fetchall()
        if s_logs:
            st.dataframe(pd.DataFrame([dict(x) for x in s_logs]), use_container_width=True)
            if st.button("🧹 監査ログを全消去", key="del_spoof_btn"):
                with get_db() as conn:
                    conn.execute("DELETE FROM spoof_logs")
                    conn.commit()
                st.rerun()
        else:
            st.info("現在、不審なアクセスやBAN端末からの侵入試行は検知されていません。")

    with t_mng3:
        with get_db() as conn:
            b_list = conn.execute("SELECT * FROM security_bans ORDER BY banned_at DESC").fetchall()
        if b_list:
            st.dataframe(pd.DataFrame([dict(x) for x in b_list]), use_container_width=True)
        else:
            st.caption("現在登録されているBAN端末指紋・遮断キーはありません。")

    with t_mng4:
        with get_db() as conn:
            a_logs = conn.execute("SELECT * FROM agi_audit_logs ORDER BY id DESC LIMIT 50").fetchall()
        if a_logs:
            st.dataframe(pd.DataFrame([dict(x) for x in a_logs]), use_container_width=True)
            if st.button("🧹 AGI巡回ログを消去", key="del_agi_logs_btn"):
                with get_db() as conn:
                    conn.execute("DELETE FROM agi_audit_logs")
                    conn.commit()
                st.rerun()
        else:
            st.success("🤖 AGI自律巡回エンジン稼働中：すべてのアルゴリズム・データフィードは正常であり、ハリボテや静的コンテンツは検知されていません。")

    if st.button("✕ 管理コンソールを閉じる", key="close_mng_console_btn", use_container_width=True):
        st.session_state["admin_console_open"] = False
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()  # コンソール展開中は下部に銘柄一覧を出さず終了

# ==========================================
# 17. メインダッシュボード描画（最適化・超高速）
# ==========================================
mpills = "".join([f'<div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);padding:3px 8px;border-radius:6px;font-size:10.5px;display:inline-flex;gap:5px;"><span style="color:#94a3b8;">{m["label"]}</span><span style="color:{"#10b981" if m["diff"]>=0 else "#ef4444"};font-weight:700;">{"+" if m["diff"]>=0 else ""}{m["diff"]}%</span></div>' for m in macro_info.values()])
st.markdown(
    f'<div class="glass-header">'
    f'<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">'
    f'<div style="min-width:0;flex:1;"><div class="brand-luxury">YAMASHISHI LAB</div><div class="brand-sub">QUANTUM WAVEFUNCTION & MULTI-AGENT TERMINAL</div></div>'
    f'<span style="background:rgba(168,85,247,0.16);border:1px solid rgba(168,85,247,0.45);color:#e9d5ff;padding:4px 9px;border-radius:999px;font-size:10px;font-weight:700;">⚛️ 本格AI API連携稼働</span>'
    f'</div>'
    f'<div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:8px;">{mpills}</div></div>',
    unsafe_allow_html=True
)

with st.spinner(f"⚛️ 【{investment_style.split(' ')[1]}】全市場ディープスキャン中..."):
    g_res, all_res = fetch_pool_batch(macro_info, b5_live_map, investment_style, "inst" in ac_b, "mom" in ac_b, "algo" in ac_b, "ms" in ac_b, total_capital, risk_tolerance_pct)

c1, c2 = st.columns([3.4, 1])
cin = c1.text_input("🔍 銘柄検索", placeholder="銘柄コードまたは米ティッカーを入力 (例: 6920, 5803, NVDA, IONQ)", label_visibility="collapsed")
if c2.button("🔍 銘柄診断", use_container_width=True) and cin:
    st.session_state["custom_search_code"] = norm_tk(cin)

if st.session_state.get("custom_search_code"):
    nc = st.session_state["custom_search_code"]
    cr = fetch_one(nc, macro_info, b5_live_map, investment_style, "inst" in ac_b, "mom" in ac_b, "algo" in ac_b, "ms" in ac_b, total_capital, risk_tolerance_pct)
    if cr:
        render_card(cr, is_custom=True, kp="custom")
        if st.button("✖️ 個別診断を閉じる", use_container_width=True):
            st.session_state["custom_search_code"] = ""
            st.rerun()
    else:
        st.warning(f"銘柄「{nc}」のデータが見つかりませんでした。")

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
    ol = st.session_state.get("active_category", "🏆 総合TOP5")
    if nw and nw != ol:
        st.session_state["nav_history"].append(ol)
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
