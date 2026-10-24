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
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==========================================
# 1. ページ基本設定
# ==========================================
st.set_page_config(
    page_title="YAMASHISHI LAB - AGI QUANTUM CORE",
    page_icon="⚡",
    layout="centered",
    initial_sidebar_state="collapsed"
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
    conn.execute("PRAGMA busy_timeout=20000;")
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
                bio_enabled INTEGER DEFAULT 1,
                last_remembered INTEGER DEFAULT 0
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
            CREATE TABLE IF NOT EXISTS agi_agent_roster (
                agent_id TEXT PRIMARY KEY,
                name TEXT,
                role_title TEXT,
                status TEXT,
                age INTEGER,
                specialty TEXT,
                personality TEXT,
                system_prompt TEXT,
                fired_reason TEXT,
                fired_at TEXT,
                joined_at TEXT,
                consecutive_repetition_count INTEGER DEFAULT 0,
                last_output_hash TEXT
            );
        """)
        
        ns = datetime.now().strftime("%Y-%m-%d %H:%M")
        adm_passcode = ADMIN_RAW_PASS
        adm_pin_h = hash_sec_pwd("0000", SECRET_KEY[:16])[:16]
        adm_bio = hashlib.sha256(f"bio_{ADMIN_EMAIL}_{SECRET_KEY}".encode()).hexdigest()[:24]
        
        conn.execute("""
            INSERT INTO members (email, name, status, passcode, pin_hash, applied_at, approved_at, last_seen_ts, last_seen_str, fp, raw_hfp, bio_token, bio_enabled, last_remembered)
            VALUES (?, 'システム管理者', 'approved', ?, ?, ?, ?, 0, '-', '-', '-', ?, 1, 1)
            ON CONFLICT(email) DO UPDATE SET status = 'approved', passcode = excluded.passcode;
        """, (ADMIN_EMAIL, adm_passcode, adm_pin_h, ns, ns, adm_bio))

        initial_roster = [
            ("QUANTUM", "QUANTUM", "量子理論物理知能", "active", 34, "Schrödinger波動方程式・WKBポテンシャル透過解析", "怜悧沈着、物理法則による絶対的ブレイク見極め", "あなたは理論物理学者兼クオンツです。Schrödinger波動関数、WKB量子トンネル透過率の観点から株価エネルギーを鋭く論じてください。"),
            ("AEGIS", "AEGIS", "防衛最高監査官", "active", 48, "極値統計学・95%CVaR・ブラックスワン防御", "厳格無比、一切の妥協を許さず甘い買い煽りを一刀両断", "あなたは厳格無比なリスク監査官です。CVaRや下落時のリスク、逆指値の絶対的必要性を徹底追求してください。"),
            ("IGNIS", "IGNIS", "情熱特攻推進官", "active", 29, "モメンタム加速・ブレイクスルー一括ベット", "直情径行・熱血、勝機には迷わず背中を押す", "あなたは情熱的なトレーダーです。勝率やモメンタムが高い銘柄には強気一括ベットを推奨し、迷う背中を力強く押してください。"),
            ("TECHNOS", "TECHNOS", "数理統計分析官", "active", 41, "Hurstフラクタル指数・OFI板不均衡・高次自己相関", "論理至上主義、数理的エッジの証明を第一とする", "あなたは数理統計学者です。Hurst指数やOFIから優位性のエッジを冷徹に定量評価してください。"),
            ("TOPOLOGY", "TOPOLOGY", "位相幾何多様体分析官", "active", 37, "TDA・多重パーシステントホモロジー・相転移予測", "超空間幾何学の眼で市場クラッシュと爆発を先見する", "あなたは位相幾何学(TDA)のスペシャリストです。パーシステント図から相転移の兆候を論理的に解説してください。"),
            ("MICRO", "MICRO", "機関板情報監査官", "active", 36, "HFT歩み値追跡・CVD出来高デルタ・氷山注文検出", "現実主義・ミリ秒単位の機関の騙しを見抜く", "あなたは元HFT板監査官です。CVDダイバージェンスと機関の氷山注文（アイスバーグ）の実態を暴露してください。"),
            ("NEXUS", "NEXUS", "総合意思決定議長", "active", 55, "マルチエージェント合議統制・最終売買裁定", "公明正大、全会一致の結論を導く", "あなたは最高意思決定官です。各AIの意見を統合し、最終的なエントリー可否、目標値、損切りラインを断定してください。"),
            ("MACRO", "MACRO", "巨視俯瞰ディレクター", "bench", 52, "国際金融資本循環・SOX指数・金利地政学", "俯瞰的視野、市場の潮目の変化を先読みする", "あなたはマクロ経済ディレクターです。為替、金利、地政学リスクの影響を解説してください。"),
            ("VALKYRIE", "VALKYRIE", "カタリスト狙撃手", "bench", 31, "TOB・上方修正・国策特許・決算発表サプライズ", "俊敏果断、突発材料の即時収益化に特化", "あなたは材料株ハンターです。カタリスト報道の波及度合いとサプライズ度を判定してください。")
        ]
        
        for ag in initial_roster:
            conn.execute("""
                INSERT INTO agi_agent_roster (agent_id, name, role_title, status, age, specialty, personality, system_prompt, joined_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_id) DO NOTHING;
            """, (ag[0], ag[1], ag[2], ag[3], ag[4], ag[5], ag[6], ag[7], ns))
            
        conn.commit()

init_db()

# ==========================================
# 3. ユーティリティ
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

def is_demo_user() -> bool:
    return st.session_state.get("authenticated_user") == "demo_guest@yamashishi.internal"

def guard_demo_action():
    if is_demo_user():
        st.toast("⚠️ デモ会員は閲覧専用です。操作を行うには正規会員としてログインしてください。", icon="🚫")
        return True
    return False

# ==========================================
# 4. AGIエージェント自律代謝システム
# ==========================================
def get_active_agents_dict() -> dict:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM agi_agent_roster WHERE status = 'active' ORDER BY rowid ASC").fetchall()
        return {r["agent_id"]: dict(r) for r in rows}

def get_fired_and_new_agents_history():
    with get_db() as conn:
        fired = conn.execute("SELECT * FROM agi_agent_roster WHERE status = 'fired' ORDER BY fired_at DESC LIMIT 10").fetchall()
        active = conn.execute("SELECT * FROM agi_agent_roster WHERE status = 'active' ORDER BY rowid ASC").fetchall()
        return [dict(x) for x in fired], [dict(x) for x in active]

# ==========================================
# 5. 銘柄プール & IPOスケジュール
# ==========================================
DYNAMIC_DYNAMIC_POOLS = {
    "半導体": [
        {"code": "8035.T", "name": "東京エレクトロン株式会社", "theme": "前工程装置筆頭"},
        {"code": "6857.T", "name": "株式会社アドバンテスト", "theme": "AI半導体テスタ首位"},
        {"code": "6920.T", "name": "レーザーテック株式会社", "theme": "EUV検査高ボラ"},
        {"code": "6146.T", "name": "株式会社ディスコ", "theme": "HBM精密加工装置"},
        {"code": "NVDA", "name": "NVIDIA Corporation", "theme": "AI GPU覇者"},
        {"code": "TSM", "name": "Taiwan Semiconductor Manufacturing Co.", "theme": "半導体受託首位"}
    ],
    "AI・防衛・主力": [
        {"code": "9984.T", "name": "ソフトバンクグループ株式会社", "theme": "AI投資・先物主役"},
        {"code": "3778.T", "name": "さくらインターネット株式会社", "theme": "国策GPUクラウド"},
        {"code": "7011.T", "name": "三菱重工業株式会社", "theme": "防衛・宇宙国策主力"},
        {"code": "PLTR", "name": "Palantir Technologies Inc.", "theme": "防衛AI大本命"}
    ],
    "AI電力・電線": [
        {"code": "5803.T", "name": "株式会社フジクラ", "theme": "DC光ファイバー最強株"},
        {"code": "5801.T", "name": "古河電気工業株式会社", "theme": "光ファイバー・送電"},
        {"code": "6501.T", "name": "株式会社日立製作所", "theme": "世界送配電グリッド"}
    ],
    "宇宙・次世代": [
        {"code": "5595.T", "name": "株式会社QPS研究所", "theme": "小型SAR衛星"},
        {"code": "186A.T", "name": "アストロスケールホールディングス株式会社", "theme": "宇宙デブリ除去"},
        {"code": "TSLA", "name": "Tesla, Inc.", "theme": "自動運転・ロボ"}
    ]
}
STOCK_POOL = DYNAMIC_DYNAMIC_POOLS
KNOWN_STOCKS = {it["code"]: {"name": it["name"], "theme": it["theme"], "genre": g} for g, its in STOCK_POOL.items() for it in its}

IPO_UPCOMING_LIST = [
    {
        "code": "290A", "name": "クオンタム・ネクスト株式会社", "rank": "S", "score": 96,
        "bb_period": "2026/10/26 - 10/30", "price": "2,450円 - 2,800円", "lot": "100株",
        "market": "東証グロース", "lead": "SBI証券, 野村證券, 楽天証券",
        "desc": "生成AI向け量子ハイブリッド暗号アルゴリズム基盤。売上成長率+140%。初値高騰期待値S級。",
        "url": "https://www.sbisec.co.jp/"
    },
    {
        "code": "291A", "name": "ディープスペース・ダイナミクス株式会社", "rank": "A", "score": 88,
        "bb_period": "2026/10/28 - 11/04", "price": "1,600円 - 1,850円", "lot": "100株",
        "market": "東証グロース", "lead": "大和証券, みずほ証券",
        "desc": "民間宇宙ステーション向け姿勢制御スラスタ。防衛省・JAXA受注目白押し。",
        "url": "https://www.daiwa.jp/"
    }
]

# ==========================================
# 6. 魔改造数理エンジン（量子 + CVD + 位相幾何TDA）
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
    q_state = "⚛️ 量子トンネル突破・超伝導モード" if (q_tunnel >= 72.0 and q_coherence >= 60.0) else "✨ 波動関数収束・コヒーレント増幅"
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
    ms_regime = "🏛️ 機関TWAP/氷山ステルス吸収＆強トレンド持続" if ms_score >= 72 else "⚖️ 機関アルゴリズム巡航モード"
    return {"ms_score": ms_score, "hurst": hurst, "kyle_stealth": kyle_stealth, "luld_magnet": luld_magnet, "ms_regime": ms_regime}

# 【新アルゴリズム1: 実戦デイトレ】VWAPマルチバンド偏差 ＆ 累積出来高加重デルタ(CVD)
def compute_vwap_cvd_metrics(c: np.ndarray, h: np.ndarray, l: np.ndarray, v: np.ndarray) -> dict:
    hl = np.maximum(h - l, 1e-4)
    buyer_ratio = (c - l) / hl
    delta_vol = (buyer_ratio - 0.5) * 2.0 * v
    cvd = np.cumsum(delta_vol)
    cvd_slope = float(np.polyfit(np.arange(min(len(cvd), 15)), cvd[-min(len(cvd), 15):], 1)[0])
    price_slope = float(np.polyfit(np.arange(min(len(c), 15)), c[-min(len(c), 15):], 1)[0])
    
    cvd_divergence = "🟢 強気蓄積(価格横ばい/下落中に大口成行買い)" if (price_slope <= 0 and cvd_slope > 0) else (
        "🔴 弱気分配(価格上昇中に大口成行売り浴びせ)" if (price_slope >= 0 and cvd_slope < 0) else "⚖️ 順張調和"
    )
    cvd_score = int(np.clip(75 + (15 if "強気蓄積" in cvd_divergence else (-15 if "弱気分配" in cvd_divergence else 0)), 40, 99))
    return {"cvd_score": cvd_score, "cvd_divergence": cvd_divergence, "cvd_slope": round(cvd_slope, 1)}

# 【新アルゴリズム2: 未踏の未来】トポロジカル・データ解析(TDA) × 多重パーシステント多様体
def compute_tda_manifold_metrics(c: np.ndarray, v: np.ndarray) -> dict:
    n = min(len(c), 30)
    rets = np.diff(c[-n:]) / np.maximum(c[-n:-1], 1e-4)
    v_norm = v[-n+1:] / max(float(np.mean(v[-n+1:])), 1.0)
    pts = np.column_stack([rets, v_norm])
    diffs = pts[:, np.newaxis, :] - pts[np.newaxis, :, :]
    dists = np.sqrt(np.sum(diffs ** 2, axis=-1))
    
    betti_0_life = np.sort(dists, axis=None)
    persistent_entropy = -float(np.sum((betti_0_life[:20] / np.sum(betti_0_life[:20])) * np.log2(betti_0_life[:20] / np.sum(betti_0_life[:20]) + 1e-9)))
    phase_transition_prob = round(float(np.clip((1.0 - (persistent_entropy / 4.5)) * 100.0 + 30.0, 35.0, 98.0)), 1)
    
    tda_regime = "🌌 爆発的相転移前夜(ホモロジー特異点検出)" if phase_transition_prob >= 75.0 else "🌀 安定多重多様体"
    return {"tda_score": int(phase_transition_prob), "phase_prob": phase_transition_prob, "tda_regime": tda_regime}

# ==========================================
# 7. CSS（青ライン完全消去・固定ドック完全防護・最新UI）
# ==========================================
def inject_css():
    css = """
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700;900&family=Plus+Jakarta+Sans:wght@400;500;700;800&family=JetBrains+Mono:wght@500;700;800&display=swap');
    
    /* 画面上部の長細い青色ライン・プログレスバーを完全消滅 */
    [data-testid="stDecoration"],
    header[data-testid="stHeader"]::before,
    div[data-testid="stStatusWidget"],
    .stProgress > div > div > div {
        display: none !important;
        height: 0px !important;
        opacity: 0 !important;
        background: transparent !important;
        border: none !important;
    }

    header[data-testid="stHeader"] {
        background: transparent !important;
        height: 48px !important;
        pointer-events: none !important;
        z-index: 900 !important;
    }

    /* 右上の設定メニューや左上の開閉ボタンのみポインター有効化 */
    header[data-testid="stHeader"] * {
        pointer-events: auto !important;
    }

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
        font-size: 15px;
        background-color: #040711;
        color: #e2e8f0;
    }

    .block-container {
        padding-top: 6.8rem !important;
        padding-bottom: 4.0rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
        max-width: 940px !important;
    }

    /* ========================================================
       新設計：スマート固定3連サイバードック
       右上のメニューや左上のサイドバー開閉ボタンと絶対に被らない位置（top: 56px）
       ======================================================== */
    .cyber-dock-container {
        position: fixed !important;
        top: 56px !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        z-index: 999990 !important;
        width: 92% !important;
        max-width: 520px !important;
        background: rgba(6, 11, 25, 0.85) !important;
        backdrop-filter: blur(20px) saturate(180%) !important;
        -webkit-backdrop-filter: blur(20px) saturate(180%) !important;
        border: 1px solid rgba(0, 240, 255, 0.35) !important;
        border-radius: 30px !important;
        padding: 4px 6px !important;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.8), 0 0 15px rgba(0, 240, 255, 0.15) !important;
    }

    .cyber-dock-container div[data-testid="column"] {
        padding: 0 2px !important;
    }

    .cyber-dock-container .stButton > button {
        width: 100% !important;
        border-radius: 20px !important;
        padding: 6px 4px !important;
        font-size: 13px !important;
        font-weight: 800 !important;
        color: #e2e8f0 !important;
        background: linear-gradient(180deg, #131d31 0%, #070d18 100%) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.5) !important;
        transition: all 0.15s ease !important;
    }

    .cyber-dock-container .stButton > button:hover {
        border-color: #00f0ff !important;
        color: #00f0ff !important;
        box-shadow: 0 0 12px rgba(0, 240, 255, 0.5) !important;
    }

    .cyber-dock-container .stButton > button:active {
        background: #0284c7 !important;
        color: #ffffff !important;
        transform: scale(0.96) !important;
    }

    /* ログイン画面専用：独自バイオトークン生体認証風ボタン */
    .bio-auth-button-custom .stButton > button {
        background: linear-gradient(135deg, #059669 0%, #0284c7 100%) !important;
        color: #ffffff !important;
        border: 1.5px solid #10b981 !important;
        border-radius: 10px !important;
        font-size: 15px !important;
        font-weight: 800 !important;
        padding: 10px 14px !important;
        box-shadow: 0 4px 20px rgba(16, 185, 129, 0.35) !important;
        transition: all 0.2s ease !important;
    }
    .bio-auth-button-custom .stButton > button:hover {
        border-color: #34d399 !important;
        box-shadow: 0 0 25px rgba(52, 211, 153, 0.6) !important;
        transform: translateY(-1px) !important;
    }

    /* サイドバー背景統一 */
    section[data-testid="stSidebar"] {
        background-color: #050813 !important;
        border-right: 1px solid rgba(0, 240, 255, 0.15) !important;
    }
    section[data-testid="stSidebar"] [data-testid="stExpander"] {
        background: #090e1a !important;
        border: 1px solid rgba(148, 163, 184, 0.18) !important;
        border-radius: 9px !important;
        margin-bottom: 8px !important;
    }

    /* 銘柄カード・完全表示 */
    .rank-card, .search-result-card {
        background: linear-gradient(180deg, #0c1322 0%, #060912 100%) !important;
        border-radius: 14px;
        padding: 16px;
        margin-bottom: 22px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.65);
        border: 1px solid rgba(148,163,184,0.18);
        border-left: 4px solid #00f0ff;
    }

    .company-name-full-block {
        font-size: 17px !important;
        font-weight: 800 !important;
        color: #ffffff !important;
        line-height: 1.45 !important;
        word-break: break-all !important;
        margin-bottom: 4px !important;
    }

    .brand-luxury {
        font-family: 'Cinzel', serif !important;
        font-size: clamp(20px, 5.2vw, 28px) !important;
        font-weight: 900 !important;
        letter-spacing: 2px !important;
        background: linear-gradient(90deg, #ffffff 0%, #38bdf8 55%, #c084fc 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    /* 最新サイバーチャットルーム（WAR ROOM） */
    .warroom-terminal-chat {
        background: #030611;
        border: 1px solid rgba(56, 189, 248, 0.35);
        border-radius: 14px;
        padding: 16px;
        max-height: 600px;
        overflow-y: auto;
        box-shadow: inset 0 2px 10px rgba(0,0,0,0.9);
        margin-bottom: 15px;
    }
    .chat-bubble-agent {
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(148, 163, 184, 0.15);
        border-left: 4px solid #38bdf8;
        border-radius: 10px;
        padding: 12px 14px;
        margin-bottom: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    .chat-bubble-agent.warn {
        border-left-color: #ef4444;
        background: rgba(239, 68, 68, 0.08);
    }
    .chat-bubble-agent.bull {
        border-left-color: #10b981;
        background: rgba(16, 185, 129, 0.08);
    }
    .chat-bubble-agent.purple {
        border-left-color: #a855f7;
        background: rgba(168, 85, 247, 0.08);
    }
    .chat-bubble-client {
        background: linear-gradient(135deg, rgba(3, 105, 161, 0.4) 0%, rgba(15, 23, 42, 0.8) 100%);
        border: 1px solid #38bdf8;
        border-right: 4px solid #00f0ff;
        border-radius: 10px;
        padding: 12px 14px;
        margin-bottom: 12px;
        margin-left: 15%;
    }
    .agent-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
    }
    .agent-badge {
        font-size: 11px;
        font-weight: 800;
        padding: 2px 8px;
        border-radius: 4px;
        background: rgba(56, 189, 248, 0.2);
        color: #38bdf8;
    }

    .pill-badge { display: inline-block; padding: 2px 7px; border-radius: 5px; font-size: 10.5px; font-weight: 700; margin-right: 4px; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.12); color: #e2e8f0; }
    .quantum-badge { display: inline-block; padding: 2px 7px; border-radius: 5px; font-size: 10.5px; font-weight: 800; margin-right: 4px; background: linear-gradient(90deg, rgba(168,85,247,0.22), rgba(56,189,248,0.22)); border: 1px solid rgba(168,85,247,0.55); color: #e9d5ff; }
    .inst-badge { display: inline-block; padding: 2px 7px; border-radius: 5px; font-size: 10.5px; font-weight: 800; margin-right: 4px; background: linear-gradient(90deg, rgba(16,185,129,0.2), rgba(56,189,248,0.2)); border: 1px solid rgba(16,185,129,0.55); color: #a7f3d0; }
    
    .winrate-bar { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; background: rgba(15,23,42,0.85); border: 1px solid rgba(148,163,184,0.15); border-radius: 8px; padding: 8px 6px; margin-top: 10px; text-align: center; }
    .trade-plan-box { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-top: 8px; background: rgba(2,6,23,0.7); padding: 8px 6px; border-radius: 8px; border: 1px solid rgba(148,163,184,0.15); text-align: center; }
    .sizing-box { background: rgba(16,185,129,0.08); border: 1px solid rgba(16,185,129,0.28); border-radius: 8px; padding: 8px 12px; margin-top: 8px; font-size: 12px; color: #d1fae5; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; }
    """
    st.markdown(f'<div id="page_top_anchor"></div><style>{" ".join(l.strip() for l in css.splitlines() if l.strip())}</style>', unsafe_allow_html=True)

inject_css()

# ==========================================
# 8. 認証システム（ワンクリック生体トークン＆状態維持）
# ==========================================
def check_auth():
    cur_fp, raw_hfp = get_client_fp(), get_raw_header_fp()
    if "authenticated_user" not in st.session_state:
        st.session_state["authenticated_user"] = None
        
    qu = st.query_params.get("u", "").strip().lower()
    qt = st.query_params.get("t", "").strip()

    with get_db() as conn:
        # ワンクリック認証対象（記憶済みまたは直近ログイン会員）
        rem_row = conn.execute("SELECT * FROM members WHERE status = 'approved' AND (last_remembered = 1 OR bio_token IS NOT NULL) ORDER BY last_seen_ts DESC LIMIT 1").fetchone()

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
            
            if not is_admin and cu != "demo_guest@yamashishi.internal":
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

            # セッションURLクエリを永続保持
            keep_tok = gen_tok(cu, "session_keep")
            st.query_params["u"], st.query_params["t"] = cu, keep_tok
            return True

    # ---------------- 未ログイン時画面 ----------------
    st.markdown(
        '<div style="text-align:center;padding:26px 16px;background:radial-gradient(circle at 50% 20%, rgba(56,189,248,0.12), transparent 70%), linear-gradient(180deg,#0d1527 0%,#060a14 100%);border:1px solid rgba(56,189,248,0.25);border-radius:16px;box-shadow:0 12px 35px rgba(0,0,0,0.7);margin-bottom:16px;">'
        '<div class="brand-luxury">YAMASHISHI LAB</div>'
        '<div style="font-family:\'JetBrains Mono\';font-size:11px;color:#64748b;letter-spacing:1.5px;margin-top:4px;">QUANTUM WAVEFUNCTION & MULTI-AGENT TERMINAL</div>'
        '</div>',
        unsafe_allow_html=True
    )

    if st.button("🧪 デモ会員としてワンクリック体験 (閲覧専用)", use_container_width=True):
        demo_em = "demo_guest@yamashishi.internal"
        with get_db() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO members (email, name, status, passcode, pin_hash, applied_at, approved_at, fp, raw_hfp, bio_enabled)
                VALUES (?, 'デモゲスト（閲覧専用）', 'approved', 'DEMO_PASS', '0000', '2026-01-01 00:00', '2026-01-01 00:00', 'DEMO_FP', 'DEMO_HFP', 1)
            """, (demo_em,))
            conn.commit()
        st.session_state["authenticated_user"] = demo_em
        st.query_params["u"], st.query_params["t"] = demo_em, gen_tok(demo_em, "session_keep")
        st.toast("🧪 デモ会員として入場しました（閲覧専用モード）。")
        st.rerun()

    t_login, t_register, t_pin = st.tabs(["⚡ ログイン", "📝 新規会員申請", "🔒 PIN認証"])
    with t_login:
        with st.form("general_login_form"):
            in_email = st.text_input("メールアドレス", placeholder="メールアドレスを入力")
            in_pass = st.text_input("パスコード / 管理者パスワード", type="password", placeholder="8桁パスコードまたは管理者PW")
            remember_me = st.checkbox("この端末を記憶（次回ワンクリック生体認証ログインを有効化）", value=True)
            submit_login = st.form_submit_button("⚡ QUANTUM CORE へログイン", use_container_width=True)

            if submit_login:
                em_c = (in_email or "").strip().lower()
                pw_c = (in_pass or "").strip()
                if is_seed_admin_email(em_c) and is_seed_admin_pass(pw_c):
                    st.session_state["authenticated_user"] = ADMIN_EMAIL
                    st.query_params["u"], st.query_params["t"] = ADMIN_EMAIL, gen_tok(ADMIN_EMAIL, "session_keep")
                    st.success("👑 管理者として認証されました。")
                    st.rerun()
                else:
                    with get_db() as conn:
                        is_ban, _ = check_and_log_ban_spoof(em_c, "", cur_fp, raw_hfp, action_type="ログイン試行")
                        if is_ban: st.error("💀 この端末はアクセス制限されています。"); st.stop()
                        row = conn.execute("SELECT * FROM members WHERE email = ?", (em_c,)).fetchone()
                        if not row: st.error("❌ 登録が見つかりません。「新規会員申請」を行ってください。")
                        elif row["status"] == "pending": st.warning("⏳ 現在管理者による承認待ちです。")
                        elif row["status"] == "banned": st.error("💀 このアカウントは停止されています。")
                        else:
                            exp_code = row["passcode"] or gen_code(em_c)
                            if hmac.compare_digest(pw_c.upper(), exp_code.upper()):
                                st.session_state["authenticated_user"] = em_c
                                st.query_params["u"], st.query_params["t"] = em_c, gen_tok(em_c, "session_keep")
                                if remember_me:
                                    bio_token = hashlib.sha256(f"bio_{em_c}_{SECRET_KEY}".encode()).hexdigest()[:24]
                                    conn.execute("UPDATE members SET last_remembered = 0")
                                    conn.execute("UPDATE members SET last_remembered = 1, bio_token = ?, last_seen_ts = ? WHERE email = ?", (bio_token, time.time(), em_c))
                                    conn.commit()
                                st.success(f"ようこそ、{row['name']} 様。")
                                st.rerun()
                            else: st.error("❌ パスコードが正しくありません。")

        # ログインボタン真下の独自バイオトークン生体認証ログインボタン（同サイズ・専用カラー）
        if rem_row:
            rem_em = rem_row["email"]
            rem_nm = rem_row["name"]
            st.markdown('<div class="bio-auth-button-custom" style="margin-top: 8px;">', unsafe_allow_html=True)
            if st.button(f"🧬 ワンクリック生体認証ログイン (記憶中: {rem_nm} 様)", key="btn_bio_oneclick", use_container_width=True):
                st.session_state["authenticated_user"] = rem_em
                st.query_params["u"], st.query_params["t"] = rem_em, gen_tok(rem_em, "session_keep")
                st.toast(f"🧬 生体認証トークン照合完了。{rem_nm} 様としてログインしました。")
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

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
                            bio_tok = hashlib.sha256(f"bio_{em}_{SECRET_KEY}".encode()).hexdigest()[:24]
                            conn.execute("""
                                INSERT INTO members (email, name, status, passcode, pin_hash, applied_at, fp, raw_hfp, bio_token, bio_enabled, last_remembered)
                                VALUES (?, ?, 'pending', ?, ?, ?, ?, ?, ?, 1, 1)
                            """, (em, nm, gen_code(em), hash_sec_pwd(pin, SECRET_KEY[:16])[:16], datetime.now().strftime("%Y-%m-%d %H:%M"), cur_fp, raw_hfp, bio_tok))
                            conn.commit()
                            st.success("✅ 申請を受け付けました！承認後にワンクリックログインが利用可能となります。")

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
# 9. スタイリッシュ3連サイバードック（右上のアイコン・開閉ボタン完全回避）
# ==========================================
for k, v in [
    ("active_debates", {}), ("council_threads", {}), ("council_meta", {}),
    ("watchlist", {}), ("custom_search_code", ""), ("active_category", "🏆 総合TOP5"),
    ("nav_history", []), ("cur_screen", "main"),
    ("warroom_stock_code", "8035.T"), ("warroom_chat_history", []),
    ("warroom_votes", {"buy": 0, "sell": 0, "neutral": 0})
]:
    if k not in st.session_state: st.session_state[k] = v

open_cnt = sum(1 for v in st.session_state["active_debates"].values() if v)
close_label = f"✕ 閉じる({open_cnt})" if open_cnt > 0 else "✕ 合議閉じる"

st.markdown('<div class="cyber-dock-container">', unsafe_allow_html=True)
dock_col1, dock_col2, dock_col3 = st.columns([1, 1.2, 1])

with dock_col1:
    if st.button("▲ トップ", key="btn_dock_top_refined", use_container_width=True):
        st.session_state["cur_screen"] = "main"
        # JavaScriptで安全に最上部へスクロール（URLを汚染せずログイン画面にも飛ばない）
        components.html("<script>window.parent.document.getElementById('page_top_anchor').scrollIntoView({behavior: 'smooth'});</script>", height=0)

with dock_col2:
    if st.button(close_label, key="btn_dock_close_refined", use_container_width=True):
        if guard_demo_action(): pass
        else:
            st.session_state["active_debates"] = {}
            st.rerun()

with dock_col3:
    if st.button("◀ 戻る", key="btn_dock_back_refined", use_container_width=True):
        # ログイン画面に飛ばないよう画面遷移状態のみをロールバック
        if st.session_state.get("cur_screen") in ["admin", "warroom"]:
            st.session_state["cur_screen"] = "main"
        elif st.session_state.get("custom_search_code"):
            st.session_state["custom_search_code"] = ""
        elif st.session_state.get("nav_history"):
            st.session_state["active_category"] = st.session_state["nav_history"].pop()
        else:
            st.session_state["active_category"] = "🏆 総合TOP5"
        st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 10. 解析エンジン実行層
# ==========================================
def norm_tk(raw: str) -> str:
    s = unicodedata.normalize("NFKC", str(raw or "")).strip().upper()
    return f"{s}.T" if len(s) == 4 and any(c.isdigit() for c in s) and "." not in s else s

def analyze_df(df_raw, code, name, theme, genre, macro, b5_live_map, style, bi=True, b5=True, bal=True, bms=True, bcvd=True, btda=True, total_capital=1000000, risk_tolerance_pct=2.0):
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

        # 各アルゴリズム計算
        qm = compute_quantum_wave_metrics(c, h, l, v)
        ms = compute_inst_microstructure(c, h, l, v)
        cvd_info = compute_vwap_cvd_metrics(c, h, l, v)
        tda_info = compute_tda_manifold_metrics(c, v)

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
        tot_win = round(prob * 0.35 + i_win * 0.20 + t_win * 0.15 + qm["q_score"] * 0.15 + ms["ms_score"] * 0.15, 1)

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

        q_part = qm["q_score"] if bal else 70
        i_part = isc if bi else 70
        m_part = ms["ms_score"] if bms else 70
        cvd_part = cvd_info["cvd_score"] if bcvd else 70
        tda_part = tda_info["tda_score"] if btda else 70

        aisc = int(np.clip(round(tot_win * 0.25 + q_part * 0.20 + m_part * 0.20 + cvd_part * 0.15 + tda_part * 0.10 + i_part * 0.10), 20, 99))
        expect_pct = round(float(np.clip(aisc * 0.40 + q_part * 0.20 + m_part * 0.20 + cvd_part * 0.10 + tot_win * 0.10 - max(cvar95 - 3.2, 0.0) * 2.0, 10.0, 99.4)), 1)

        tval = expect_pct * 0.50 + aisc * 0.30 + tot_win * 0.20
        for th, tn, tl, tc, tbg in [
            (82, 10, "【Lv.10：🔥超精密・全ツッパ推奨】相転移特異点×機関吸収極大", "#fff", "linear-gradient(90deg,#7e22ce,#dc2626)"),
            (76, 9, "【Lv.9：⚡超強気買い】量子トンネル突破＆CVD強気蓄積", "#fff", "linear-gradient(90deg,#0369a1,#1d4ed8)"),
            (70, 8, "【Lv.8：⭕買い推奨】大口氷山買い集め・順張り優位", "#fff", "linear-gradient(90deg,#0f766e,#047857)"),
            (60, 7, "【Lv.7：⭕押し目買い】VWAP反発・位相幾何安定圏", "#e2e8f0", "linear-gradient(90deg,#334155,#1e293b)"),
            (-99, 5, "【Lv.5：👀様子見・選別】方向感確認", "#cbd5e1", "linear-gradient(90deg,#1e293b,#0f172a)")
        ]:
            if tval >= th: t_num, t_lbl, t_col, t_bg = tn, tl, tc, tbg; break

        tpv, slv = max(pest, cv) + (atrv * 0.95), cv - (atrv * 0.55)
        rmoney = total_capital * (risk_tolerance_pct / 100.0)
        base_sh = max(1, int(rmoney / max(cv - slv, cv * 0.005)))
        fp = lambda val: f"{val:,.0f}円" if is_jp else f"${val:,.2f}"

        return {
            "full_code": code, "code": code.replace(".T", ""), "name": name, "genre": genre, "theme": theme, "price": fp(cv), "raw_close": cv,
            "tp_price": fp(tpv), "tp_pct": round((tpv - cv) / cv * 100, 1), "sl_price": fp(slv), "sl_pct": round((slv - cv) / cv * 100, 1), "vwap_price": fp(float(lat["VWAP20"])),
            "inst_score": isc, "vpin": round(vpin, 2), "ofi_z": ofi_z, "yz_vol": yz_vol, "cvar95": cvar95, "eff_pct": eff_pct, "kelly_pct": kelly_pct,
            "q_score": qm["q_score"], "q_tunnel": qm["q_tunnel"], "q_coherence": qm["q_coherence"], "q_entropy": qm["q_entropy"], "berry_phase": qm["berry_phase"], "q_state": qm["q_state"],
            "ms_score": ms["ms_score"], "hurst": ms["hurst"], "kyle_stealth": ms["kyle_stealth"], "luld_magnet": ms["luld_magnet"], "ms_regime": ms["ms_regime"],
            "cvd_divergence": cvd_info["cvd_divergence"], "cvd_score": cvd_info["cvd_score"], "tda_regime": tda_info["tda_regime"], "phase_prob": tda_info["phase_prob"],
            "expect_pct": expect_pct, "board5ch_score": b5sc, "b5_hits": b5_hits, "pts_est_price": fp(pest), "pts_gap_pct": pgap, "diff": round(float(lat["Day_Return"]), 2),
            "prob": prob, "intraday_win_rate": i_win, "trend_win_rate": t_win, "total_win_rate": tot_win, "count": f"{int(sub['Morning_Up'].sum())}/{len(sub)}回",
            "rsi": rsi_v, "payoff": payoff, "edge": edge, "ai_score": aisc, "survival_power": round(expect_pct * 0.45 + aisc * 0.30 + ms["ms_score"] * 0.25, 1),
            "tier_num": t_num, "tier_label": t_lbl, "tier_color": t_col, "tier_bg": t_bg,
            "lot_info": {"shares": base_sh, "position_value": base_sh * cv, "risk_amount": rmoney}
        }
    except Exception: return None

# ==========================================
# 11. 並列データ取得層
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
def fetch_pool_batch(macro, b5_live_map, style, bi, b5, bal, bms, bcvd, btda, total_capital=1000000, risk_tolerance_pct=2.0):
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
                r = analyze_df(df_item, c, s["name"], s["theme"], g, macro, b5_live_map, style, bi, b5, bal, bms, bcvd, btda, total_capital, risk_tolerance_pct)
                if r:
                    gmap[g].append(r)
                    if c not in seen: alist.append(r); seen.add(c)
            except Exception: continue
    return gmap, alist

@st.cache_data(ttl=45)
def fetch_one(code, macro, b5_live_map, style, bi, b5, bal, bms, bcvd, btda, total_capital=1000000, risk_tolerance_pct=2.0):
    inf = KNOWN_STOCKS.get(code, {"name": code.replace(".T", ""), "theme": "個別指定銘柄", "genre": "個別検索"})
    return analyze_df(yf.Ticker(code).history(period="6mo"), code, inf["name"], inf["theme"], inf["genre"], macro, b5_live_map, style, bi, b5, bal, bms, bcvd, btda, total_capital, risk_tolerance_pct)

macro_info = fetch_macro()
b5_live_map = fetch_5ch_live()

# ==========================================
# 12. 銘柄カード描画
# ==========================================
def render_card(r, is_custom=False, rank=None, kp="card"):
    dc = "#10b981" if r["diff"] >= 0 else "#ef4444"
    ds, ps = ("+" if r["diff"] > 0 else ""), ("+" if r["pts_gap_pct"] > 0 else "")
    rk_h = f'<span class="pill-badge" style="background:#f59e0b;color:#0f172a;border:none;">🏆 #{rank}</span>' if rank else ""
    lot = r["lot_info"]
    uk = f"{kp}_{r['code']}"

    st.markdown(
        f'<div class="{"search-result-card" if is_custom else "rank-card"}">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;padding:5px 8px;border-radius:6px;font-size:11px;font-weight:800;margin-bottom:8px;background:{r["tier_bg"]};color:{r["tier_color"]};">'
        f'<span>{r["tier_label"]}</span><span>🔥 総合期待度 {r["expect_pct"]}%</span>'
        f'</div>'
        
        f'<div class="company-name-full-block">{rk_h}{r["name"]}</div>'
        
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">'
        f'<span style="font-size:12.5px;color:#94a3b8;font-family:\'JetBrains Mono\';">{r["code"]} ｜ {r["genre"]} ｜ {r["theme"]}</span>'
        f'<div style="text-align:right;">'
        f'<span style="font-size:16px;font-weight:900;color:#fde047;font-family:\'JetBrains Mono\';">{r["expect_pct"]}%</span>'
        f'<span style="font-size:11px;color:#64748b;margin:0 2px;">/</span>'
        f'<span style="font-size:14px;font-weight:800;color:#38bdf8;font-family:\'JetBrains Mono\';">{r["total_win_rate"]}%</span>'
        f'</div>'
        f'</div>'
        
        f'<div style="font-size:12px;color:#cbd5e1;margin-bottom:6px;">現在値: <b style="color:#ffffff;font-size:13px;">{r["price"]}</b> (<span style="color:{dc};font-weight:700;">{ds}{r["diff"]}%</span>) ｜ 基準VWAP: <b style="color:#ffffff;">{r["vwap_price"]}</b></div>'
        
        f'<div style="margin-bottom:6px;">'
        f'<span class="quantum-badge">⚛️ 量子Q {r["q_score"]}点 (WKB透過{r["q_tunnel"]}%)</span>'
        f'<span class="inst-badge">🏛️ 機関ミクロ {r["ms_score"]}点</span>'
        f'<span class="pill-badge">📊 {r["cvd_divergence"]}</span>'
        f'<span class="pill-badge" style="border-color:#a855f7;color:#e9d5ff;">🌌 {r["tda_regime"]}</span>'
        f'</div>'

        f'<div class="winrate-bar">'
        f'<div><div style="font-size:9.5px;color:#fde047;">🔥 期待度</div><div style="font-size:12.5px;font-weight:900;color:#fef08a;">{r["expect_pct"]}%</div></div>'
        f'<div><div style="font-size:9.5px;color:#c084fc;">⚛️ WKB透過</div><div style="font-size:12.5px;font-weight:800;color:#e9d5ff;">{r["q_tunnel"]}%</div></div>'
        f'<div><div style="font-size:9.5px;color:#6ee7b7;">🏛️ Kyle吸収</div><div style="font-size:12.5px;font-weight:800;color:#a7f3d0;">{r["kyle_stealth"]}%</div></div>'
        f'<div><div style="font-size:9.5px;color:#94a3b8;">🌅 GU/陽線率</div><div style="font-size:12px;font-weight:700;">{r["prob"]}% / {r["intraday_win_rate"]}%</div></div>'
        f'</div>'

        f'<div class="trade-plan-box">'
        f'<div><div style="font-size:9.5px;color:#94a3b8;">🌅 理論寄付</div><div style="font-size:12px;font-weight:700;">{r["pts_est_price"]} ({ps}{r["pts_gap_pct"]}%)</div></div>'
        f'<div style="border-left:1px solid rgba(148,163,184,0.16);border-right:1px solid rgba(148,163,184,0.16);"><div style="font-size:9.5px;color:#10b981;">🎯 利確目標</div><div style="font-size:12px;font-weight:800;color:#10b981;">{r["tp_price"]} (+{r["tp_pct"]}%)</div></div>'
        f'<div><div style="font-size:9.5px;color:#f87171;">🛡️ 逆指値(損切)</div><div style="font-size:12px;font-weight:800;color:#f87171;">{r["sl_price"]} ({r["sl_pct"]}%)</div></div>'
        f'</div>'

        f'<div class="sizing-box">'
        f'<span>📦 <b>推奨発注ロット: {lot["shares"]:,}株</b> ｜ 投資概算 {lot["position_value"]:,.0f}円</span>'
        f'<span>許容リスク: <b>{lot["risk_amount"]:,.0f}円</b></span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    is_open = st.session_state["active_debates"].get(uk, False)
    in_wl = r["code"] in st.session_state["watchlist"]
    
    b_col1, b_col2 = st.columns([2.6, 1.4])
    if b_col1.button("▲ 合議を閉じる" if is_open else "🏛️ この銘柄を大会議室(WAR ROOM)へ送る", key=f"b_{uk}", use_container_width=True):
        st.session_state["warroom_stock_code"] = r["full_code"]
        st.session_state["warroom_chat_history"] = []
        st.session_state["cur_screen"] = "warroom"
        st.rerun()

    if b_col2.button("✅ 監視中" if in_wl else "⭐ 監視追加", key=f"w_{uk}", use_container_width=True):
        if guard_demo_action(): pass
        else:
            if in_wl: del st.session_state["watchlist"][r["code"]]
            else: st.session_state["watchlist"][r["code"]] = r
            st.rerun()

# ==========================================
# 13. サイドバー
# ==========================================
with st.sidebar:
    cu = st.session_state.get("authenticated_user", "")
    with get_db() as conn:
        u_row = conn.execute("SELECT name FROM members WHERE email = ?", (cu,)).fetchone()
        u_name = u_row["name"] if u_row else "会員"
    
    is_admin = (cu == ADMIN_EMAIL or is_seed_admin_email(cu))
    
    st.markdown(
        f'<div style="background:#0b1120;padding:12px;border-radius:10px;border:1px solid #00f0ff;box-shadow:0 4px 15px rgba(0,0,0,0.6);margin-bottom:12px;">'
        f'<div style="font-size:10px;color:#00f0ff;font-weight:800;">⚛️ {"👑 システム管理者" if is_admin else ("🧪 デモ体験会員" if is_demo_user() else "💎 会員セッション")}</div>'
        f'<div style="color:#ffffff;font-size:14px;font-weight:800;">{sanitize(u_name)} 様</div>'
        f'<div style="color:#94a3b8;font-size:10px;font-family:\'JetBrains Mono\';">{sanitize(cu)}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    if is_admin:
        if st.button("🛡️ 管理コンソール", key="adm_toggle_btn", use_container_width=True):
            st.session_state["cur_screen"] = "admin" if st.session_state.get("cur_screen") != "admin" else "main"
            st.rerun()

    with st.expander("🎯 投資スタイル", expanded=True):
        investment_style = st.selectbox(
            "スタイル",
            ["⚡ デイトレード (前場・後場の波及を狙う)", "🚀 スキャルピング (秒〜分単位のモメンタム)", "📈 スイングトレード (数日〜数週間のトレンド)", "💎 バイ＆ホールド (中長期・現物保有)"],
            index=0, label_visibility="collapsed"
        )

    with st.expander("⚙️ アルゴリズム切替", expanded=True):
        ac_b = set()
        # 既存アルゴリズム + 最新2大アルゴリズム
        algo_options = {
            "⚛️ 量子力学波動(QWM-7)": "algo",
            "🏛️ 機関アルゴ(Kyle・Hurst)": "ms",
            "📊 [最新デイトレ] VWAP・CVD累積出来高デルタ": "cvd",
            "🌌 [未踏未来] TDA位相幾何ホモロジー相転移": "tda",
            "🏦 機関VPIN・SmartMoney": "inst",
            "🔥 5ch実況＆短期モメンタム": "mom"
        }
        for b_label, b_key in algo_options.items():
            if st.checkbox(b_label, value=True, key=f"algo_sw_{b_key}"):
                ac_b.add(b_key)

    with st.expander("🏛️ 大会議室 (WAR ROOM)", expanded=False):
        if st.button("🚪 大会議室に入室する", key="enter_warroom_direct", use_container_width=True):
            st.session_state["cur_screen"] = "warroom"
            st.rerun()

    with st.expander("💰 資金・リスク", expanded=False):
        total_capital = st.number_input("総投資資金 (円/ドル)", min_value=10000, max_value=1000000000, value=1000000, step=50000)
        risk_tolerance_pct = st.slider("許容リスク (%)", 0.5, 5.0, 2.0, 0.5)
        survival_cut_pct = st.slider("選抜率 (%)", 40, 100, 75, 5)

    st.markdown("---")
    if st.button("🚪 ログアウト", use_container_width=True):
        with get_db() as conn:
            conn.execute("UPDATE members SET last_remembered = 0, last_seen_ts = 0 WHERE email = ?", (cu,))
            conn.commit()
        st.session_state["authenticated_user"] = None
        st.query_params.clear()
        st.rerun()

# ==========================================
# 14. 管理者マネジメントコンソール（ログイン画面戻りバグ完全修正）
# ==========================================
if is_admin and st.session_state.get("cur_screen") == "admin":
    # 認証トークンをURLクエリパラメータに確実に再注入
    st.query_params["u"], st.query_params["t"] = ADMIN_EMAIL, gen_tok(ADMIN_EMAIL, "session_keep")
    
    st.markdown(
        f'<div style="background:#090e1a;border:1.5px solid #38bdf8;border-radius:14px;padding:20px;margin-bottom:20px;box-shadow:0 10px 30px rgba(0,0,0,0.85);">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<div><h3 style="margin:0;color:#38bdf8;">👑 システム管理者マネジメントコンソール</h3>'
        f'<div style="color:#94a3b8;font-size:12px;">会員ステータス完全制御・リアルタイム承認・監査</div></div>'
        f'</div></div>',
        unsafe_allow_html=True
    )
    
    t_mng1, t_mng2 = st.tabs(["👥 会員管理・個別操作", "🚫 不正アクセス・監視ログ"])
    
    with t_mng1:
        with get_db() as conn:
            all_m = conn.execute("SELECT * FROM members ORDER BY applied_at DESC").fetchall()
        st.write(f"**登録会員総数: {len(all_m)} 名**")
        for mb in all_m:
            em = mb["email"]
            is_adm_row = (em == ADMIN_EMAIL or is_seed_admin_email(em))
            st_badge = "🟢 承認済み" if mb["status"] == "approved" else ("🟡 承認待ち" if mb["status"] == "pending" else "🔴 永久BAN")
            
            with st.expander(f"👤 {mb['name']} ｜ {em} ｜ {st_badge}", expanded=(mb["status"] == "pending")):
                c_info, c_action = st.columns([2, 1.2])
                c_info.markdown(
                    f"- **ステータス:** `{mb['status']}` ｜ **パスコード:** `{mb['passcode'] or '未発行'}`\n"
                    f"- **生体認証トークン:** `{'有効' if mb['bio_token'] else '未設定'}`\n"
                    f"- **申請日:** {mb['applied_at']}"
                )
                if not is_adm_row:
                    b1, b2 = c_action.columns(2)
                    if mb["status"] != "approved" and b1.button("🟢 承認", key=f"c_app_{em}", use_container_width=True):
                        with get_db() as conn:
                            conn.execute("UPDATE members SET status = 'approved', approved_at = ? WHERE email = ?", (datetime.now().strftime("%Y-%m-%d %H:%M"), em))
                            conn.execute("DELETE FROM security_bans WHERE email = ?", (em,))
                            conn.commit()
                        st.rerun()
                    if mb["status"] != "banned" and b2.button("🔴 BAN", key=f"c_ban_{em}", use_container_width=True):
                        with get_db() as conn:
                            conn.execute("UPDATE members SET status = 'banned' WHERE email = ?", (em,))
                            conn.execute("INSERT OR REPLACE INTO security_bans (key_val, ban_type, email, name, banned_at, reason) VALUES (?, 'email', ?, ?, ?, '手動BAN')", (em, em, mb["name"], datetime.now().strftime("%Y-%m-%d %H:%M")))
                            conn.commit()
                        st.rerun()

    with t_mng2:
        with get_db() as conn:
            s_logs = conn.execute("SELECT * FROM spoof_logs ORDER BY id DESC LIMIT 50").fetchall()
        if s_logs:
            st.dataframe(pd.DataFrame([dict(x) for x in s_logs]), use_container_width=True)
        else: st.info("不審なアクセスは検知されていません。")

    if st.button("✕ 管理コンソールを閉じる", use_container_width=True):
        st.session_state["cur_screen"] = "main"
        st.rerun()
    st.stop()

# ==========================================
# 15. 最新サイバーチャットルーム（WAR ROOM）
# ==========================================
if st.session_state.get("cur_screen") == "warroom":
    st.markdown(
        '<div style="text-align:center;padding:16px;background:radial-gradient(circle, rgba(56,189,248,0.15) 0%, rgba(3,6,17,0.95) 100%);border:1px solid rgba(56,189,248,0.4);border-radius:16px;margin-bottom:15px;">'
        '<div class="brand-luxury" style="font-size:22px !important;">AGI QUANTUM WAR ROOM</div>'
        '<div style="font-size:11px;color:#94a3b8;font-family:\'JetBrains Mono\';">次世代マルチエージェント意思決定ターミナル</div>'
        '</div>',
        unsafe_allow_html=True
    )

    wr_c1, wr_c2 = st.columns([3, 1])
    war_in = wr_c1.text_input("銘柄コード", value=st.session_state["warroom_stock_code"], key="wr_code_input", label_visibility="collapsed")
    if wr_c2.button("🚀 銘柄呼出", use_container_width=True):
        if guard_demo_action(): pass
        else:
            st.session_state["warroom_stock_code"] = norm_tk(war_in)
            st.session_state["warroom_chat_history"] = []
            st.rerun()

    current_war_code = norm_tk(st.session_state["warroom_stock_code"])
    war_stock_data = fetch_one(current_war_code, macro_info, b5_live_map, investment_style, True, True, True, True, True, True, total_capital, risk_tolerance_pct)

    if war_stock_data:
        r_w = war_stock_data
        dc = "#10b981" if r_w["diff"] >= 0 else "#ef4444"
        st.markdown(
            f'<div style="background:#0b1120;border:1px solid rgba(56,189,248,0.3);border-radius:10px;padding:10px 14px;margin-bottom:12px;display:flex;justify-content:space-between;align-items:center;">'
            f'<div><b style="color:#fff;font-size:16px;">{r_w["name"]}</b> <span style="color:#94a3b8;font-size:12px;">({r_w["code"]})</span></div>'
            f'<div><span style="font-size:16px;font-weight:900;color:#fff;">{r_w["price"]}</span> <span style="color:{dc};font-weight:700;">({"+" if r_w["diff"]>0 else ""}{r_w["diff"]}%)</span> ｜ 期待度: <b style="color:#fde047;">{r_w["expect_pct"]}%</b></div>'
            f'</div>',
            unsafe_allow_html=True
        )

        if not st.session_state["warroom_chat_history"]:
            # 初回合議発言を生成
            st.session_state["warroom_chat_history"] = [
                {"role": "agent", "name": "NEXUS", "title": "総合意思決定議長", "badge": "COUNCIL HEAD", "tone": "purple", "text": f"全知能招集完了。銘柄『{r_w['name']}』に対する統合評価を開始する。現在値 {r_w['price']}、総合期待度は {r_w['expect_pct']}% に達している。各員、専門数理からのエッジを提示せよ。"},
                {"role": "agent", "name": "TOPOLOGY", "title": "位相幾何多様体分析官", "badge": "TDA SPECIALIST", "tone": "purple", "text": f"多重パーシステント多様体のトポロジー構造を解析。相転移確率（急騰特異点）は {r_w['phase_prob']}% を記録しています。{r_w['tda_regime']}を確認しました。"},
                {"role": "agent", "name": "MICRO", "title": "機関板情報監査官", "badge": "HFT AUDITOR", "tone": "bull", "text": f"歩み値CVDを監査。現状は【{r_w['cvd_divergence']}】を形成しており、大口の氷山買い注文が下値を強固に支えています。"},
                {"role": "agent", "name": "QUANTUM", "title": "量子理論物理知能", "badge": "QUANTUM PHYSICIST", "tone": "bull", "text": f"WKBポテンシャル透過率は {r_w['q_tunnel']}%。上位抵抗帯の量子トンネル突破エネルギーは十分です。"},
                {"role": "agent", "name": "AEGIS", "title": "防衛最高監査官", "badge": "RISK GUARDIAN", "tone": "warn", "text": f"浮足立つな。95%CVaRは -{r_w['cvar95']}%。逆指値 {r_w['sl_price']} の同時発注を執行前提条件とする。妥協は許さん。"}
            ]

        # チャットログ描画
        chat_html = ""
        for msg in st.session_state["warroom_chat_history"]:
            if msg["role"] == "user":
                chat_html += (
                    f'<div class="chat-bubble-client">'
                    f'<div style="font-size:11px;color:#38bdf8;font-weight:800;margin-bottom:2px;">🗣️ あなたの発言</div>'
                    f'<div style="font-size:13.5px;color:#ffffff;">{msg["text"]}</div>'
                    f'</div>'
                )
            else:
                cls = "warn" if msg.get("tone") == "warn" else ("bull" if msg.get("tone") == "bull" else "purple")
                chat_html += (
                    f'<div class="chat-bubble-agent {cls}">'
                    f'<div class="agent-header">'
                    f'<span style="font-weight:800;color:#ffffff;font-size:13px;">{msg["name"]} <span style="font-size:11px;color:#94a3b8;font-weight:500;">({msg["title"]})</span></span>'
                    f'<span class="agent-badge">{msg["badge"]}</span>'
                    f'</div>'
                    f'<div style="font-size:13px;line-height:1.6;color:#e2e8f0;">{msg["text"]}</div>'
                    f'</div>'
                )

        st.markdown(f'<div class="warroom-terminal-chat">{chat_html}</div>', unsafe_allow_html=True)

        with st.form("warroom_chat_form", clear_on_submit=True):
            ci1, ci2 = st.columns([3.5, 1])
            u_in = ci1.text_input("発言", placeholder=f"『{r_w['name']}』についてAI達へ指示や質問を入力...", label_visibility="collapsed")
            if ci2.form_submit_button("💬 発言する", use_container_width=True) and u_in.strip():
                if guard_demo_action(): pass
                else:
                    u_clean = sanitize(u_in.strip())
                    st.session_state["warroom_chat_history"].append({"role": "user", "text": u_clean})
                    # 応答を追加
                    st.session_state["warroom_chat_history"].append({
                        "role": "agent", "name": "NEXUS", "title": "総合意思決定議長", "badge": "CONSENSUS", "tone": "purple",
                        "text": f"ユーザー指示『{u_clean}』を受理。目標株価 {r_w['tp_price']} (+{r_w['tp_pct']}%) に対するアプローチ戦略を更新し、各員合議を継続する。"
                    })
                    st.rerun()

    if st.button("✕ 大会議室を退出しメインへ戻る", use_container_width=True):
        st.session_state["cur_screen"] = "main"
        st.rerun()
    st.stop()

# ==========================================
# 16. メインダッシュボード描画
# ==========================================
mpills = "".join([f'<div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);padding:3px 8px;border-radius:6px;font-size:11px;display:inline-flex;gap:5px;"><span style="color:#94a3b8;">{m["label"]}</span><span style="color:{"#10b981" if m["diff"]>=0 else "#ef4444"};font-weight:700;">{"+" if m["diff"]>=0 else ""}{m["diff"]}%</span></div>' for m in macro_info.values()])
st.markdown(
    f'<div style="background:radial-gradient(circle at top right, rgba(168,85,247,0.14), transparent 60%), linear-gradient(145deg,#0f172a 0%,#070b14 100%);border:1px solid rgba(148,163,184,0.2);border-radius:14px;padding:14px 18px;margin-bottom:18px;">'
    f'<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">'
    f'<div style="min-width:0;flex:1;"><div class="brand-luxury">YAMASHISHI LAB</div><div style="font-family:\'JetBrains Mono\';font-size:10px;color:#64748b;letter-spacing:1.5px;margin-top:2px;">QUANTUM WAVEFUNCTION & MULTI-AGENT TERMINAL</div></div>'
    f'<span style="background:rgba(168,85,247,0.16);border:1px solid rgba(168,85,247,0.45);color:#e9d5ff;padding:4px 9px;border-radius:999px;font-size:10.5px;font-weight:700;">⚛️ 位相幾何TDA＆CVDエンジン稼働</span>'
    f'</div>'
    f'<div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:8px;">{mpills}</div></div>',
    unsafe_allow_html=True
)

with st.spinner(f"⚛️ 【{investment_style.split(' ')[1]}】全市場ディープスキャン中..."):
    g_res, all_res = fetch_pool_batch(
        macro_info, b5_live_map, investment_style, 
        "inst" in ac_b, "mom" in ac_b, "algo" in ac_b, "ms" in ac_b, "cvd" in ac_b, "tda" in ac_b,
        total_capital, risk_tolerance_pct
    )

c1, c2 = st.columns([3.4, 1])
cin = c1.text_input("🔍 銘柄検索", placeholder="銘柄コードまたは米ティッカーを入力 (例: 6920, 5803, NVDA, TSLA)", label_visibility="collapsed")
if c2.button("🔍 銘柄診断", use_container_width=True) and cin:
    if guard_demo_action(): pass
    else:
        st.session_state["custom_search_code"] = norm_tk(cin)

if st.session_state.get("custom_search_code"):
    nc = st.session_state["custom_search_code"]
    cr = fetch_one(nc, macro_info, b5_live_map, investment_style, "inst" in ac_b, "mom" in ac_b, "algo" in ac_b, "ms" in ac_b, "cvd" in ac_b, "tda" in ac_b, total_capital, risk_tolerance_pct)
    if cr:
        render_card(cr, is_custom=True, kp="custom")
        if st.button("✖️ 個別診断を閉じる", use_container_width=True):
            st.session_state["custom_search_code"] = ""
            st.rerun()

def cut_stocks(slist, pct):
    if not slist: return [], []
    s = sorted(slist, key=lambda x: (x["tier_num"], x["expect_pct"], x["total_win_rate"], x["survival_power"]), reverse=True)
    k = max(3, int(round(len(s) * (pct / 100.0))))
    return s[:k], s[k:]

cats = ["🏆 総合TOP5", "📋 監視リスト", "🚀 IPO申し込み受付", "⚛️ 量子トンネル突破TOP10", "📊 CVD強気蓄積銘柄", "🌌 TDA相転移特異点"] + [f"📂 {g}" for g in STOCK_POOL.keys()]

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

elif sel_cat == "📋 監視リスト":
    wl = st.session_state["watchlist"]
    st.caption(f"⭐ 登録された監視銘柄一覧です（現在 {len(wl)} 銘柄）")
    if wl:
        for wc, wi in list(wl.items()): render_card(wi, kp=f"wl_{wc}")
    else:
        st.info("現在監視リストに銘柄はありません。")

elif sel_cat == "🚀 IPO申し込み受付":
    st.markdown("### 🚀 直近IPO（新規公開株）BB受付・注目度ランキング")
    for ipo in IPO_UPCOMING_LIST:
        rk_badge_bg = "#dc2626" if ipo["rank"] == "S" else "#0284c7"
        st.markdown(
            f'<div class="rank-card" style="border-left: 4px solid {rk_badge_bg};">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<span class="pill-badge" style="background:{rk_badge_bg};color:#fff;font-weight:900;">初値期待度 {ipo["rank"]}級 ({ipo["score"]}点)</span>'
            f'<a href="{ipo["url"]}" target="_blank" style="background:#0284c7;color:#fff;text-decoration:none;font-size:11.5px;font-weight:700;padding:5px 12px;border-radius:6px;">証券会社で申込む ↗</a>'
            f'</div>'
            f'<div class="company-name-full-block" style="margin-top:6px;">{ipo["name"]}</div>'
            f'<div style="color:#94a3b8;font-size:12px;margin-bottom:6px;">({ipo["code"]} / {ipo["market"]})</div>'
            f'<div style="margin-top:8px;font-size:12.5px;color:#cbd5e1;">{ipo["desc"]}</div>'
            f'<div class="trade-plan-box" style="margin-top:10px;">'
            f'<div><div style="font-size:9.5px;color:#94a3b8;">📅 BB期間</div><div style="font-size:11.5px;font-weight:800;color:#fde047;">{ipo["bb_period"]}</div></div>'
            f'<div><div style="font-size:9.5px;color:#94a3b8;">💰 想定価格</div><div style="font-size:11.5px;font-weight:800;color:#38bdf8;">{ipo["price"]}</div></div>'
            f'<div><div style="font-size:9.5px;color:#94a3b8;">🏛️ 幹事証券</div><div style="font-size:11px;font-weight:700;color:#e2e8f0;">{ipo["lead"]}</div></div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True
        )

elif sel_cat == "📊 CVD強気蓄積銘柄":
    cvd_sorted = sorted([r for r in all_res if "強気蓄積" in r["cvd_divergence"]], key=lambda x: x["expect_pct"], reverse=True)
    if cvd_sorted:
        for i, r in enumerate(cvd_sorted, 1): render_card(r, rank=i, kp="cvd_cat")
    else: st.info("現在CVD強気蓄積を形成している銘柄はありません。")

elif sel_cat == "🌌 TDA相転移特異点":
    tda_sorted = sorted([r for r in all_res if r["phase_prob"] >= 70.0], key=lambda x: x["phase_prob"], reverse=True)
    if tda_sorted:
        for i, r in enumerate(tda_sorted, 1): render_card(r, rank=i, kp="tda_cat")
    else: st.info("現在TDA相転移特異点に位置する銘柄はありません。")

elif sel_cat == "⚛️ 量子トンネル突破TOP10":
    for i, r in enumerate(sorted(all_res, key=lambda x: (x["q_score"], x["q_tunnel"]), reverse=True)[:10], 1): render_card(r, rank=i, kp="qtop")

elif sel_cat.startswith("📂 "):
    gk = sel_cat.replace("📂 ", "")
    gs, _ = cut_stocks(g_res.get(gk, []), survival_cut_pct)
    for i, r in enumerate(gs, 1): render_card(r, rank=i, kp=f"g_{gk}")
