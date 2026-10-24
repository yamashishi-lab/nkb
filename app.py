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
# 1. ページ基本設定（初期サイドバーは閉じる）
# ==========================================
st.set_page_config(
    page_title="YAMASHISHI LAB - AGI QUANTUM CORE",
    page_icon="⚡",
    layout="centered",
    initial_sidebar_state="collapsed"  # ログイン時サイドバー開いたままを防止
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
            CREATE TABLE IF NOT EXISTS agi_agent_roster (
                agent_id TEXT PRIMARY KEY,
                name TEXT,
                role_title TEXT,
                status TEXT, -- 'active', 'fired', 'bench'
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
        
        conn.execute("""
            INSERT INTO members (email, name, status, passcode, pin_hash, applied_at, approved_at, last_seen_ts, last_seen_str, fp, raw_hfp, bio_enabled)
            VALUES (?, 'システム管理者', 'approved', ?, ?, ?, ?, 0, '-', '-', '-', 1)
            ON CONFLICT(email) DO UPDATE SET status = 'approved', passcode = excluded.passcode;
        """, (ADMIN_EMAIL, adm_passcode, adm_pin_h, ns, ns))

        # 初期AIエージェント母艦のシード登録
        initial_roster = [
            ("QUANTUM", "QUANTUM", "量子開放系・理論物理知能", "active", 34, "Schrödinger波動方程式・WKBポテンシャル透過解析", "怜悧沈着、物理法則による絶対的ブレイク見極め", "あなたは世界最高峰の理論物理学者兼クオンツです。Schrödinger波動関数、WKB量子トンネル透過率、Berry位相の観点から、株価のエネルギー準位とブレイクスルーの必然性を鋭く論じてください。短くシャープに答えてください。"),
            ("AEGIS", "AEGIS", "リスク管理・防衛最高監査官", "active", 48, "極値統計学・95%CVaR・ブラックスワン防御", "厳格無比、一切の妥協を許さず甘い買い煽りを一刀両断", "あなたは厳格無比なリスク監査官です。下落リスク、CVaR、急落シナリオ、逆指値の絶対的必要性を徹底追求し、甘い楽観論を厳しく戒めてください。"),
            ("IGNIS", "IGNIS", "直言特攻・情熱推進官", "active", 29, "モメンタム加速・ブレイクスルー一括ベット", "直情径行・熱血、勝機には迷わず背中を押す", "あなたは直言特攻の情熱的なトレーダーです。勝率やモメンタムが高い銘柄には強気一括ベットを熱狂的に推奨し、迷う背中を力強く押してください。"),
            ("TECHNOS", "TECHNOS", "数理統計・アルゴリズム分析官", "active", 41, "Hurstフラクタル指数・OFI板不均衡・高次自己相関", "論理至上主義、数理的エッジの証明を第一とする", "あなたは数理統計学者です。Hurst指数、OFI、Kyleのステルス流動性、価格弾力性の数理データから、優位性のエッジを冷徹に定量評価してください。"),
            ("MACRO", "MACRO", "世界市場・巨視俯瞰ディレクター", "active", 52, "国際金融資本循環・SOX指数・金利地政学", "俯瞰的視野、市場の潮目の変化を先読みする", "あなたはグローバル・マクロ経済ディレクターです。為替、SOX指数、日経先物、米金利動向がこの銘柄に与える地政学的・マクロ的影響を解説してください。"),
            ("MICRO", "MICRO", "機関板情報・高頻度実態監査官", "active", 36, "HFT歩み値追跡・アイスバーグ氷山注文検出", "現実主義・ミリ秒単位の機関の騙しを見抜く", "あなたは元HFT（高頻度取引）の板監査官です。歩み値、アイスバーグ注文、VWAP攻防、板の買い圧力（OFI）のリアルタイム実態を暴露してください。"),
            ("NEXUS", "NEXUS", "総合議長・最高意思決定官", "active", 55, "マルチエージェント合議統制・最終売買裁定", "公明正大、全会一致の結論を導く", "あなたは全知能を統括する最高意思決定官（総合議長）です。各AIの意見を統合し、最終的なエントリー可否、目標値、損切りラインを断定してください。"),
            # ベンチ待機メンバー（クビ発生時に即召集）
            ("CHRONOS", "CHRONOS", "時系列サイクル波動アナリスト", "bench", 38, "コンドラチェフ＆エリオット波動・フラクタル時間論", "静謐、時間の周期性から転換点を割り出す", "あなたは時系列サイクル専門の理論家です。周期性と時間波動から天井と底値の到達タイムスタンプを提示してください。"),
            ("VALKYRIE", "VALKYRIE", "イベントドリブン・カタリスト狙撃手", "bench", 31, "TOB・上方修正・国策特許・決算発表サプライズ", "俊敏果断、突発材料の即時収益化に特化", "あなたは材料株ハンターです。カタリスト報道の波及度合いとサプライズ度を鋭く判定してください。"),
            ("SOLON", "SOLON", "行動経済学・大衆心理逆張り監査官", "bench", 45, "群集心理パニック指数・過熱度リバースエンジニアリング", "皮肉屋、イナゴタワーの崩壊を警告し逆張り妙味を狙う", "あなたは行動ファイナンスの権威です。個人の総悲観と過熱を冷徹に診断し、逆張りのエッジを説いてください。")
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
# 3. ユーティリティ & 端末識別セッション保持
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
# 4. AGIエージェント自律代謝（クビ・新規召集）システム
# ==========================================
def get_active_agents_dict() -> dict:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM agi_agent_roster WHERE status = 'active' ORDER BY rowid ASC").fetchall()
        return {r["agent_id"]: dict(r) for r in rows}

def get_fired_and_new_agents_history():
    with get_db() as conn:
        fired = conn.execute("SELECT * FROM agi_agent_roster WHERE status = 'fired' ORDER BY fired_at DESC LIMIT 5").fetchall()
        recent_new = conn.execute("SELECT * FROM agi_agent_roster WHERE status = 'active' AND fired_at IS NULL ORDER BY joined_at DESC LIMIT 5").fetchall()
        return [dict(x) for x in fired], [dict(x) for x in recent_new]

def evaluate_and_audit_agent_speech(agent_id: str, speech_text: str):
    """発言が定型文、具体性欠如、直前と同一ハッシュの場合に警告を積み、3回で即時クビにする"""
    if agent_id == "NEXUS":  # 議長はシステムコアのため免責
        return
    
    txt_clean = re.sub(r"\s+", "", speech_text.strip())
    h = hashlib.sha256(txt_clean.encode()).hexdigest()[:16]
    
    with get_db() as conn:
        cur = conn.execute("SELECT consecutive_repetition_count, last_output_hash, name FROM agi_agent_roster WHERE agent_id = ?", (agent_id,)).fetchone()
        if not cur: return
        
        rep = cur["consecutive_repetition_count"]
        # ハッシュ一致または具体的数値・記号を含まない空疎な発言を検知
        is_generic = len(re.findall(r"\d+|%|円|\$", speech_text)) < 2 or (cur["last_output_hash"] == h)
        
        if is_generic:
            rep += 1
            if rep >= 3:
                # クビ執行 & ベンチから新人を召集
                reason = "発言の定型化・数理的根拠の欠如、および3回連続の思考停止出力を検知したため解雇"
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                conn.execute("UPDATE agi_agent_roster SET status = 'fired', fired_reason = ?, fired_at = ? WHERE agent_id = ?", (reason, now_str, agent_id))
                
                # ベンチから次の候補を active に昇格
                bench_cand = conn.execute("SELECT agent_id, name FROM agi_agent_roster WHERE status = 'bench' LIMIT 1").fetchone()
                if bench_cand:
                    conn.execute("UPDATE agi_agent_roster SET status = 'active', joined_at = ? WHERE agent_id = ?", (now_str, bench_cand["agent_id"]))
                    st.toast(f"⚡ AGI自律監査: エージェント【{cur['name']}】を解雇。新鋭【{bench_cand['name']}】を合議に召集しました。", icon="🚨")
            else:
                conn.execute("UPDATE agi_agent_roster SET consecutive_repetition_count = ?, last_output_hash = ? WHERE agent_id = ?", (rep, h, agent_id))
        else:
            conn.execute("UPDATE agi_agent_roster SET consecutive_repetition_count = 0, last_output_hash = ? WHERE agent_id = ?", (h, agent_id))
        conn.commit()

# ==========================================
# 5. 厳選銘柄プール & IPOスケジュール情報
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

# 最新IPO案件データ（注目度順ソート済み）
IPO_UPCOMING_LIST = [
    {
        "code": "290A", "name": "クオンタム・ネクスト", "rank": "S", "score": 96,
        "bb_period": "2026/10/26 - 10/30", "price": "2,450円 - 2,800円", "lot": "100株",
        "market": "東証グロース", "lead": "SBI証券, 野村證券, 楽天証券",
        "desc": "生成AI向け量子ハイブリッド暗号アルゴリズム基盤の開発。売上成長率+140%。初値高騰期待値S級。",
        "url": "https://www.sbisec.co.jp/"
    },
    {
        "code": "291A", "name": "ディープスペース・ダイナミクス", "rank": "A", "score": 88,
        "bb_period": "2026/10/28 - 11/04", "price": "1,600円 - 1,850円", "lot": "100株",
        "market": "東証グロース", "lead": "大和証券, みずほ証券, 松井証券",
        "desc": "民間宇宙ステーション向け姿勢制御スラスタ及び推進薬充填。防衛省・JAXA受注目白押し。",
        "url": "https://www.daiwa.jp/"
    },
    {
        "code": "292A", "name": "ニューログリッド・エナジー", "rank": "A", "score": 84,
        "bb_period": "2026/11/02 - 11/09", "price": "3,100円 - 3,400円", "lot": "100株",
        "market": "東証プライム", "lead": "三菱UFJモルガン, SMBC日興証券",
        "desc": "次世代データセンター向け超電導蓄電バッファ網。大手クラウド事業者との長期独占供給契約。",
        "url": "https://www.smbcnikko.co.jp/"
    },
    {
        "code": "293A", "name": "バイオシンセシス・インサイト", "rank": "B", "score": 75,
        "bb_period": "2026/11/05 - 11/12", "price": "950円 - 1,100円", "lot": "100株",
        "market": "東証グロース", "lead": "マネックス証券, 楽天証券",
        "desc": "AIタンパク質構造予測による希少難病向け核酸医薬リード化合物スクリーニング。",
        "url": "https://www.monex.co.jp/"
    }
]

# ==========================================
# 6. 理論物理・量子力学 × 機関ミクロ構造数理エンジン
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
# 7. CSS（中央スリムナビ・1行美麗大文字・ステップカード）
# ==========================================
def inject_css():
    css = """
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700;900&family=Plus+Jakarta+Sans:wght@400;500;700;800&family=JetBrains+Mono:wght@500;700;800&display=swap');
    
    [data-testid="stDecoration"] { display: none !important; height: 0px !important; }
    header[data-testid="stHeader"] { background: transparent !important; pointer-events: none !important; z-index: 999900 !important; }

    /* サイドバー開閉アイコン */
    button[data-testid="stSidebarCollapsedControl"],
    button[data-testid="baseButton-headerNoPadding"],
    [data-testid="collapsedControl"] {
        pointer-events: auto !important;
        display: flex !important;
        position: fixed !important;
        left: 14px !important;
        top: 14px !important;
        z-index: 1000005 !important;
        background: rgba(15, 23, 42, 0.95) !important;
        border: 1px solid rgba(56, 189, 248, 0.6) !important;
        border-radius: 9px !important;
        color: #38bdf8 !important;
        padding: 6px 10px !important;
    }

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
        font-size: 15px; /* 視認性UP */
        line-height: 1.65;
        background-color: #040711;
        color: #e2e8f0;
        -webkit-font-smoothing: antialiased;
    }

    .block-container {
        padding-top: 5.5rem !important; /* ナビとの干渉完全防止 */
        padding-bottom: 4.0rem !important;
        padding-left: 1.0rem !important;
        padding-right: 1.0rem !important;
        max-width: 920px !important;
    }

    /* 【改修】中央寄り・アイコンと被らない少し下・スリム余白ナビ */
    .cyber-dock-wrapper {
        position: fixed !important;
        top: 16px !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        z-index: 999998 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        pointer-events: auto !important;
    }

    .cyber-quantum-nav-dock {
        display: inline-flex !important;
        align-items: center !important;
        gap: 8px !important;
        background: rgba(8, 14, 28, 0.94) !important;
        backdrop-filter: blur(18px) saturate(180%) !important;
        border: 1px solid rgba(56, 189, 248, 0.4) !important;
        border-radius: 30px !important;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.8), 0 0 15px rgba(56, 189, 248, 0.2) !important;
        padding: 4px 10px !important;
    }

    .cyber-nav-btn {
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        padding: 4px 12px !important;
        height: 28px !important;
        box-sizing: border-box !important;
        background: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(148, 163, 184, 0.25) !important;
        border-radius: 18px !important;
        color: #f1f5f9 !important;
        font-family: 'JetBrains Mono', sans-serif !important;
        font-size: 11px !important;
        font-weight: 700 !important;
        white-space: nowrap !important;
        cursor: pointer !important;
        text-decoration: none !important;
        transition: all 0.15s ease !important;
    }
    .cyber-nav-btn:hover { background: rgba(56, 189, 248, 0.2) !important; border-color: #38bdf8 !important; color: #fff !important; }
    .cyber-nav-btn:active { background: #0284c7 !important; transform: scale(0.96) !important; }

    .cyber-nav-btn-highlight { background: rgba(239, 68, 68, 0.18) !important; border-color: rgba(239, 68, 68, 0.5) !important; color: #fca5a5 !important; }
    .cyber-nav-btn-highlight:hover { background: rgba(239, 68, 68, 0.35) !important; color: #fff !important; }

    /* 銘柄カード & 1行企業名最適化 */
    .rank-card, .search-result-card {
        background: linear-gradient(180deg, #0e1628 0%, #070b14 100%) !important;
        border-radius: 14px;
        padding: 16px 18px;
        margin-bottom: 20px;
        box-shadow: 0 10px 28px rgba(0,0,0,0.6);
        border: 1px solid rgba(148,163,184,0.18);
        border-left: 4px solid #38bdf8;
    }
    
    .stock-title-row {
        display: flex;
        align-items: baseline;
        gap: 8px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .stock-company-name {
        font-size: clamp(16.5px, 4.2vw, 19px) !important;
        font-weight: 800 !important;
        color: #ffffff !important;
        letter-spacing: 0.3px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
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

    /* クリーン＆美しい初心者向けステップカード */
    .step-procedure-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 8px;
        margin-top: 10px;
    }
    .step-proc-card {
        background: rgba(15, 23, 42, 0.85);
        border: 1px solid rgba(56, 189, 248, 0.25);
        border-radius: 8px;
        padding: 10px;
    }
    .step-proc-num {
        font-family: 'JetBrains Mono', monospace;
        font-size: 10.5px;
        font-weight: 800;
        color: #38bdf8;
        margin-bottom: 3px;
    }
    .step-proc-title { font-size: 12px; font-weight: 800; color: #f8fafc; margin-bottom: 4px; }
    .step-proc-desc { font-size: 11.5px; color: #94a3b8; line-height: 1.5; }

    /* サイドバーポップアップ通知 */
    .urgent-approval-banner {
        background: linear-gradient(135deg, rgba(234, 179, 8, 0.22), rgba(161, 98, 7, 0.4));
        border: 1.5px solid #eab308;
        border-radius: 10px;
        padding: 12px;
        margin-bottom: 14px;
        animation: pulse-yellow 2s infinite;
    }
    @keyframes pulse-yellow {
        0% { box-shadow: 0 0 0 0 rgba(234, 179, 8, 0.6); }
        70% { box-shadow: 0 0 0 8px rgba(234, 179, 8, 0); }
        100% { box-shadow: 0 0 0 0 rgba(234, 179, 8, 0); }
    }

    .pill-badge { display: inline-block; padding: 2px 7px; border-radius: 5px; font-size: 10.5px; font-weight: 700; margin-right: 4px; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.12); color: #e2e8f0; }
    .quantum-badge { display: inline-block; padding: 2px 7px; border-radius: 5px; font-size: 10.5px; font-weight: 800; margin-right: 4px; background: linear-gradient(90deg, rgba(168,85,247,0.22), rgba(56,189,248,0.22)); border: 1px solid rgba(168,85,247,0.55); color: #e9d5ff; }
    .inst-badge { display: inline-block; padding: 2px 7px; border-radius: 5px; font-size: 10.5px; font-weight: 800; margin-right: 4px; background: linear-gradient(90deg, rgba(16,185,129,0.2), rgba(56,189,248,0.2)); border: 1px solid rgba(16,185,129,0.55); color: #a7f3d0; }
    
    .winrate-bar { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; background: rgba(15,23,42,0.85); border: 1px solid rgba(148,163,184,0.15); border-radius: 8px; padding: 8px 6px; margin-top: 10px; text-align: center; }
    .trade-plan-box { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-top: 8px; background: rgba(2,6,23,0.7); padding: 8px 6px; border-radius: 8px; border: 1px solid rgba(148,163,184,0.15); text-align: center; }
    .sizing-box { background: rgba(16,185,129,0.08); border: 1px solid rgba(16,185,129,0.28); border-radius: 8px; padding: 8px 12px; margin-top: 8px; font-size: 12px; color: #d1fae5; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; }
    
    .ai-council-box { background: #060a14; border-radius: 12px; padding: 14px; margin-top: 8px; margin-bottom: 10px; border: 1px solid rgba(168,85,247,0.35); }
    .council-scroll-window { max-height: 480px; overflow-y: auto; padding: 10px; background: #03060c; border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; }
    .chat-bubble-ai, .chat-bubble-doubt, .chat-bubble-rage, .chat-bubble-agree { border-radius: 8px; padding: 10px 12px; margin-bottom: 8px; font-size: 13px; line-height: 1.6; background: rgba(255,255,255,0.04); border-left: 3.5px solid #38bdf8; }
    .chat-bubble-doubt { border-left-color: #f59e0b; background: rgba(245,158,11,0.08); }
    .chat-bubble-rage { border-left-color: #ef4444; background: rgba(239,68,68,0.12); }
    .chat-bubble-agree { border-left-color: #a855f7; background: rgba(168,85,247,0.12); }
    .chat-bubble-user { background: linear-gradient(135deg, rgba(30,58,138,0.92), rgba(15,23,42,0.98)) !important; border: 1.5px solid #60a5fa !important; border-left: 5px solid #38bdf8 !important; border-radius: 8px; padding: 9px 12px; margin: 10px 0 8px 0; font-size: 13.5px; color: #ffffff; }
    """
    st.markdown(f'<div id="page_top_anchor"></div><style>{" ".join(l.strip() for l in css.splitlines() if l.strip())}</style>', unsafe_allow_html=True)

inject_css()

# ==========================================
# 8. 複数同時接続 & 並列超高速API通信エンジン
# ==========================================
def query_single_api(provider: str, api_key: str, model_name: str, sys_p: str, user_p: str) -> str:
    if not api_key: return ""
    try:
        if provider == "OpenAI":
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
            payload = {"model": model_name or "gpt-4o", "messages": [{"role": "system", "content": sys_p}, {"role": "user", "content": user_p}], "max_tokens": 200, "temperature": 0.7}
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return res["choices"][0]["message"]["content"].strip()
        elif provider == "Gemini":
            mod = model_name or "gemini-1.5-flash"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {"contents": [{"parts": [{"text": f"System Directive: {sys_p}\n\nUser Question: {user_p}"}]}], "generationConfig": {"maxOutputTokens": 200, "temperature": 0.7}}
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return res["candidates"][0]["content"]["parts"][0]["text"].strip()
        elif provider == "Anthropic":
            url = "https://api.anthropic.com/v1/messages"
            headers = {"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"}
            payload = {"model": model_name or "claude-3-5-sonnet-20241022", "system": sys_p, "messages": [{"role": "user", "content": user_p}], "max_tokens": 200, "temperature": 0.7}
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return res["content"][0]["text"].strip()
    except Exception: return ""
    return ""

def query_multi_llm_parallel(spk_configs: list) -> dict:
    """各スピーカーごとに割り当てられたAPI設定を完全並列で非同期実行（超爆速化）"""
    results = {}
    with ThreadPoolExecutor(max_workers=min(len(spk_configs), 8)) as executor:
        future_to_spk = {
            executor.submit(query_single_api, c["provider"], c["api_key"], c["model"], c["sys_p"], c["user_p"]): c["spk"]
            for c in spk_configs if c.get("api_key")
        }
        for future in as_completed(future_to_spk):
            spk = future_to_spk[future]
            try:
                txt = future.result()
                if txt: results[spk] = txt
            except Exception: pass
    return results

# ==========================================
# 9. 堅牢認証＆スマホマルチタスク復帰保護
# ==========================================
def check_auth():
    cur_fp, raw_hfp = get_client_fp(), get_raw_header_fp()
    if "authenticated_user" not in st.session_state:
        st.session_state["authenticated_user"] = None
        
    qu = st.query_params.get("u", "").strip().lower()
    qt = st.query_params.get("t", "").strip()

    # スマホ等の画面切り替え復帰時にURLパラメータが維持されているか検査
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

            # セッション保持トークンをURLに維持し、スマホのマルチタスクによる再読み込みでも絶対揮発させない
            keep_tok = gen_tok(cu, "session_keep")
            st.query_params["u"], st.query_params["t"] = cu, keep_tok
            return True

    # 未ログイン時画面
    st.markdown(
        '<div style="text-align:center;padding:26px 16px;background:radial-gradient(circle at 50% 20%, rgba(56,189,248,0.12), transparent 70%), linear-gradient(180deg,#0d1527 0%,#060a14 100%);border:1px solid rgba(56,189,248,0.25);border-radius:16px;box-shadow:0 12px 35px rgba(0,0,0,0.7);margin-bottom:16px;">'
        '<div class="brand-luxury">YAMASHISHI LAB</div>'
        '<div style="font-family:\'JetBrains Mono\';font-size:11px;color:#64748b;letter-spacing:1.5px;margin-top:4px;">QUANTUM WAVEFUNCTION & MULTI-AGENT TERMINAL</div>'
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
                                st.success(f"ようこそ、{row['name']} 様。")
                                st.rerun()
                            else: st.error("❌ パスコードが正しくありません。")

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
# 10. クエリ汚染なし・内部ステート管理ナビバー
# ==========================================
for k, v in [
    ("active_debates", {}), ("council_threads", {}), ("council_meta", {}),
    ("watchlist", {}), ("custom_search_code", ""), ("active_category", "🏆 総合TOP5"),
    ("nav_history", []), ("admin_console_open", False)
]:
    if k not in st.session_state: st.session_state[k] = v

# JavaScript経由で安全にトップ移動・セッションステート変更（URLパラメータ改変によるログアウトを完全防止）
c_nav1, c_nav2, c_nav3, c_dummy = st.columns([1, 1, 1, 0.001])
open_cnt = sum(1 for v in st.session_state["active_debates"].values() if v)
close_label = f"✕ 合議閉じる ({open_cnt})" if open_cnt > 0 else "✕ 合議閉じる"

st.markdown(
    f"""
    <div class="cyber-dock-wrapper">
        <div class="cyber-quantum-nav-dock">
            <button class="cyber-nav-btn" onclick="window.parent.scrollTo({{top: 0, behavior: 'smooth'}});">▲ トップ</button>
            <form action="" method="get" style="display:inline;margin:0;padding:0;">
                <input type="hidden" name="internal_act" value="close_debates">
            </form>
            <a class="{'cyber-nav-btn cyber-nav-btn-highlight' if open_cnt > 0 else 'cyber-nav-btn'}" href="?nav_cmd=close_debates" target="_self">{close_label}</a>
            <a class="cyber-nav-btn" href="?nav_cmd=back" target="_self">◀ 戻る</a>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

nav_cmd = st.query_params.get("nav_cmd", "")
if nav_cmd:
    if nav_cmd == "close_debates":
        st.session_state["active_debates"] = {}
    elif nav_cmd == "back":
        if st.session_state.get("admin_console_open"):
            st.session_state["admin_console_open"] = False
        elif st.session_state.get("custom_search_code"):
            st.session_state["custom_search_code"] = ""
        elif st.session_state.get("nav_history"):
            st.session_state["active_category"] = st.session_state["nav_history"].pop()
        else:
            st.session_state["active_category"] = "🏆 総合TOP5"
    st.query_params.pop("nav_cmd", None)
    st.rerun()

# ==========================================
# 11. 動的戦略ディスパッチャ & 初心者向け超実践カード
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
            "beginner_cards": [
                ("① 寄前確認", "8:50〜8:58", "板の買い気配が優勢であることを確認"),
                ("② 成行突撃", "9:00 寄り付き", f"成行で <b>{sh:,}株</b> を即時買付"),
                ("③ 防衛逆指値", "約定直後", f"逆指値を <b>{sl_str}</b> にセットし急落遮断"),
                ("④ 即時利確", "目標達成時", f"目標 <b>{tp_str}</b> 到達で迷わず全決済")
            ]
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
            "beginner_cards": [
                ("① 打診買付", "前場寄り", f"全ロットの6割 <b>{l1:,}株</b> をエントリー"),
                ("② 押し目増玉", "VWAP接近時", f"目安水準（{vwap_str}）で <b>{l2:,}株</b> 追加"),
                ("③ 逆指値防衛", "常時維持", f"撤退ライン <b>{sl_str}</b> を厳守設定"),
                ("④ 中期目標", "数日〜1週間", f"目標株価 <b>{tp_str}</b> 到達時に利益確定")
            ]
        }
    elif "バイ＆ホールド" in st_prefix:
        sh = max(1, int(round(base_sh * 0.8)))
        return {
            "algo_name": f"💎 [{st_prefix}] 中長期ファンダメンタルズ＆クオンツ定額積立型",
            "risk_posture": f"🛡️ 長期分散ポートフォリオ（コア保有 <b>{sh:,}株</b>）",
            "core_logic": f"量子コヒーレンス {qm['q_coherence']}% とフォン・ノイマンエントロピー {qm['q_entropy']} による低ノイズ長期成長享受。",
            "adj_shares": sh,
            "step_plan": f"① 現物で <b>{sh:,}株</b> を取得 → ② 逆指値（{sl_str}）をセーフティネットとして保持し中長期成長を追従",
            "beginner_cards": [
                ("① 現物購入", "随時エントリー", f"追証なしの現物取引で <b>{sh:,}株</b> 購入"),
                ("② 暴落ガード", "長期逆指値", f"想定外のショック対策で <b>{sl_str}</b> 設定"),
                ("③ 放置ホールド", "中長期保有", "日々の些細なノイズを無視してトレンド享受"),
                ("④ 満期利確", "長期目標", f"ターゲットライン <b>{tp_str}</b> で利確")
            ]
        }

    # デイトレード（デフォルト）
    sh = max(1, int(round(base_sh * 1.65)))
    return {
        "algo_name": f"🔥 [{st_prefix}] 情報精度S級・全ツッパ一括特攻型アルゴリズム",
        "risk_posture": f"👑 全ツッパ・フルベット（ <b>{sh:,}株を100%一括投入</b> ）",
        "core_logic": f"期待度 <b>{expect_pct}%</b>・量子Qスコア {qm['q_score']}点・機関ステルス吸収 {ms['kyle_stealth']}% の最高期待値。",
        "adj_shares": sh,
        "step_plan": f"① 9:00寄付き（{pest_str}目安）で <b>全ロット {sh:,}株</b> 成行一括投入 → ② 逆指値（{sl_str}）を同時セットし、目標（{tp_str}）まで一気抜き",
        "beginner_cards": [
            ("① 寄前注文", "8:45〜8:55", f"証券アプリで <b>寄成 {sh:,}株</b> の買い発注"),
            ("② 寄り約定", "9:00 前場寄付", f"約定と同時に <b>逆指値: {sl_str}</b> を即発注"),
            ("③ リスク遮断", "急落時自動保護", "損失を完全に限定し感情を排除"),
            ("④ 指値決済", "目標タッチ", f"利確指値 <b>{tp_str}</b> で逃げ切る")
        ]
    }

# ==========================================
# 12. 数理データ解析 & 監査
# ==========================================
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
            "strat": strat
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
# 14. リアルAI合議＆AGI自律発言監査オーケストレーター
# ==========================================
def run_real_ai_council(r: dict, m5=None, user_query: str = "", active_spks: list = None, posture: str = "標準バランス", api_configs: dict = None) -> dict:
    nm = r["name"]
    st_info = r["strat"]
    active_roster = get_active_agents_dict()
    
    turns = []
    round_title = f"💬 投下質問『{user_query}』に対するリアルタイムAI合議" if user_query else f"🌐 『{nm}』AI知能合議セッション"
    turns.append({"round": round_title})

    chosen_speakers = [s for s in (active_spks or list(active_roster.keys())) if s in active_roster]
    if "NEXUS" not in chosen_speakers and "NEXUS" in active_roster:
        chosen_speakers.append("NEXUS")

    quant_summary = (
        f"銘柄: {nm} ({r['code']}), 現在値: {r['price']}, 期待度: {r['expect_pct']}%, "
        f"量子Q: {r['q_score']}点 (透過率: {r['q_tunnel']}%), 機関Kyleステルス吸収: {r['kyle_stealth']}%, "
        f"Hurst指数: {r['hurst']}, OFI: {r['ofi_z']:+.2f}σ, 目標利確: {r['tp_price']}, 損切: {r['sl_price']}, "
        f"合議スタンス: {posture}。"
    )

    # 複数APIの並列クエリ用設定構築
    req_list = []
    for spk in chosen_speakers:
        ag = active_roster[spk]
        sys_p = ag["system_prompt"] + f"\n前提クオンツ情報: {quant_summary}"
        u_p = f"ユーザー質問: 『{user_query}』について、あなたの専門的視点から回答してください。" if user_query else f"『{nm}』に対する現在の市場判断とエントリーの可否を論じてください。"
        
        # エージェントごとに異なるプロバイダをローテーション割り当て（負荷分散＆同時接続）
        assigned_prov = "Off"
        api_k = ""
        mod = ""
        if api_configs:
            active_keys = [p for p, cfg in api_configs.items() if cfg.get("api_key")]
            if active_keys:
                # エージェントIDに応じてプロバイダを分散
                p_choice = active_keys[hash(spk) % len(active_keys)]
                assigned_prov = p_choice
                api_k = api_configs[p_choice]["api_key"]
                mod = api_configs[p_choice].get("model", "")

        req_list.append({"spk": spk, "provider": assigned_prov, "api_key": api_k, "model": mod, "sys_p": sys_p, "user_p": u_p})

    # 並列呼び出し実行
    api_responses = query_multi_llm_parallel(req_list)

    for spk in chosen_speakers:
        ag = active_roster[spk]
        dyn_text = api_responses.get(spk, "")
        
        if not dyn_text:
            if spk == "QUANTUM": dyn_text = f"Schrödinger波動関数のポテンシャル障壁透過率は <b>{r['q_tunnel']}%</b> です。上位抵抗線のトンネル効果突破が期待値の源泉です。"
            elif spk == "AEGIS": dyn_text = f"最大期待損失（95%CVaR -{r['cvar95']}%）を厳戒視してください。逆指値ライン <b>{r['sl_price']}</b> は死守が鉄則です。"
            elif spk == "IGNIS": dyn_text = f"総合期待度 <b>{r['expect_pct']}%</b>！推奨ロット <b>{r['lot_info']['shares']:,}株</b> で迷わず一気抜きに行く絶好のタイミングだ！"
            elif spk == "MICRO": dyn_text = f"板情報を監査。大口のKyle氷山買い集め（{r['kyle_stealth']}%）が下値を強固にサポートしています。"
            elif spk == "TECHNOS": dyn_text = f"Hurst指数 <b>{r['hurst']}</b> とエッジ <b>+{r['edge']:.2f}%</b> より、トレンドフォローの統計的有意性が確認されます。"
            elif spk == "MACRO": dyn_text = f"日経先物やSOX指数の動向を背景に、セクター全体への大口資金配分が追い風となっています。"
            elif spk == "CHRONOS": dyn_text = f"時間フラクタル解析完了。前場寄付きから25分以内に第一波動の上昇波が収束する計算です。"
            elif spk == "VALKYRIE": dyn_text = f"本銘柄のカタリスト波及係数は特異点にあります。買い気配の加速を狙撃します。"
            elif spk == "SOLON": dyn_text = f"個人投資家の総悲観売りの買い戻しを確認。逆張りモメンタムの優位性が極大です。"
            else: dyn_text = f"全エージェントの合議を総括。目標株価 <b>{r['tp_price']}</b> に向け、規律あるエントリーを承認します。"

        # AGI自律巡回監査（発言の思考停止・定型化を判定）
        evaluate_and_audit_agent_speech(spk, dyn_text)

        tone = "doubt" if spk == "AEGIS" else ("agree" if spk in ["IGNIS", "QUANTUM", "NEXUS", "VALKYRIE"] else "normal")
        spk_display = f"{ag['name']} ({ag['role_title']})"
        turns.append({"speaker": spk_display, "score": r["ai_score"], "tone": tone, "text": dyn_text})

    # 初心者向けステップカードのHTML生成
    cards_html = "".join([
        f'<div class="step-proc-card"><div class="step-proc-num">{c[0]}</div><div class="step-proc-title">{c[1]}</div><div class="step-proc-desc">{c[2]}</div></div>'
        for c in st_info["beginner_cards"]
    ])

    v_html = (
        f'<div style="margin-bottom:8px;"><b>🔥 『{nm}』総合期待度：</b><span style="color:#fde047;font-size:15px;font-weight:900;">{r["expect_pct"]}%</span> ｜ '
        f'<b>🏛️ 機関ミクロ構造：</b><span style="color:#a7f3d0;font-weight:800;">{r["ms_regime"]}</span></div>'
        f'<div style="margin-bottom:8px;font-size:12.5px;"><b>⚡ プロ向け執行プラン：</b>{st_info["step_plan"]} ｜ 🎯利確 <b>{r["tp_price"]}(+{r["tp_pct"]}%)</b> ／ 🛡️損切 <b>{r["sl_price"]}({r["sl_pct"]}%)</b></div>'
        f'<div style="font-size:12.5px;font-weight:800;color:#10b981;margin-top:6px;">🔰 【初心者向け超実践手順】迷わずできる4ステップ発注法</div>'
        f'<div class="step-procedure-container">{cards_html}</div>'
    )
    return {"final_score": r["ai_score"], "dialogue": turns, "verdict_html": v_html}

def _fmt_turn(t: dict) -> str:
    if "round" in t: return f'<div style="text-align:center;margin:6px 0;padding:4px 8px;background:rgba(168,85,247,0.15);border-radius:4px;color:#e9d5ff;font-size:11.5px;font-weight:800;">{sanitize(t["round"])}</div>'
    if t.get("is_user"):
        return f'<div class="chat-bubble-user"><b>🗣️ あなたの質問:</b><br>{sanitize(t["text"])}</div>'
    b_cls = {"doubt": "chat-bubble-doubt", "rage": "chat-bubble-rage", "agree": "chat-bubble-agree"}.get(t.get("tone", "normal"), "chat-bubble-ai")
    return f'<div class="{b_cls}"><div style="font-weight:700;color:#38bdf8;font-size:11.5px;margin-bottom:2px;">{sanitize(t["speaker"])}</div><div>{t["text"]}</div></div>'

@frag_dec
def render_council_sec(r, uk, active_spks=None, posture="標準バランス", api_configs=None):
    is_open = st.session_state["active_debates"].get(uk, False)
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
        with st.spinner(f"🌐 『{r['name']}』並列AI知能合議中..."):
            deb = run_real_ai_council(r, m5, user_query="", active_spks=active_spks, posture=posture, api_configs=api_configs)
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
            with st.spinner(f"🌐 並列AI合議中..."):
                deb_updated = run_real_ai_council(r, m5, user_query=u_text, active_spks=active_spks, posture=posture, api_configs=api_configs)
                for new_t in deb_updated["dialogue"]:
                    st.session_state["council_threads"][uk].append(new_t)
                st.session_state["council_meta"][uk] = deb_updated
                st.rerun()

    st.markdown(
        f'<div style="background:linear-gradient(135deg,#0f172a,#1e1b4b);border:1px solid rgba(168,85,247,0.4);border-radius:9px;padding:12px;margin-top:10px;">'
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
    uk = f"{kp}_{r['code']}"

    st.markdown(
        f'<div class="{"search-result-card" if is_custom else "rank-card"}">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;padding:5px 8px;border-radius:6px;font-size:11px;font-weight:800;margin-bottom:8px;background:{r["tier_bg"]};color:{r["tier_color"]};">'
        f'<span>{r["tier_label"]}</span><span>🔥 期待度 {r["expect_pct"]}%</span>'
        f'</div>'
        
        # 銘柄名行（1行固定・文字サイズ拡大）
        f'<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">'
        f'<div class="stock-title-row" style="flex:1;min-width:0;">'
        f'{rk_h}<span class="stock-company-name">{r["name"]}</span>'
        f'<span style="font-size:12px;color:#94a3b8;font-family:\'JetBrains Mono\';">({r["code"]} / {r["genre"]})</span>'
        f'</div>'
        f'<div style="text-align:right;flex-shrink:0;">'
        f'<span style="font-size:16px;font-weight:900;color:#fde047;font-family:\'JetBrains Mono\';">{r["expect_pct"]}%</span>'
        f'<span style="font-size:11px;color:#64748b;margin:0 2px;">/</span>'
        f'<span style="font-size:14px;font-weight:800;color:#38bdf8;font-family:\'JetBrains Mono\';">{r["total_win_rate"]}%</span>'
        f'</div>'
        f'</div>'
        
        f'<div style="font-size:11.5px;color:#94a3b8;margin-top:2px;">{r["theme"]} ｜ 現在値: <b style="color:#ffffff;">{r["price"]}</b> (<span style="color:{dc};font-weight:700;">{ds}{r["diff"]}%</span>)</div>'
        
        f'<div style="margin-top:6px;">'
        f'<span class="quantum-badge">⚛️ 量子Q {r["q_score"]}点 (WKB透過{r["q_tunnel"]}%)</span>'
        f'<span class="inst-badge">🏛️ 機関ミクロ {r["ms_score"]}点 (Kyle吸収{r["kyle_stealth"]}%)</span>'
        f'<span class="pill-badge">🧬 OFI {r["ofi_z"]:+.2f}σ</span>'
        f'</div>'

        f'<div class="winrate-bar">'
        f'<div><div style="font-size:9.5px;color:#fde047;">🔥 総合期待度</div><div style="font-size:12.5px;font-weight:900;color:#fef08a;">{r["expect_pct"]}%</div></div>'
        f'<div><div style="font-size:9.5px;color:#c084fc;">⚛️ WKB透過率</div><div style="font-size:12.5px;font-weight:800;color:#e9d5ff;">{r["q_tunnel"]}%</div></div>'
        f'<div><div style="font-size:9.5px;color:#6ee7b7;">🏛️ 機関Kyle吸収</div><div style="font-size:12.5px;font-weight:800;color:#a7f3d0;">{r["kyle_stealth"]}%</div></div>'
        f'<div><div style="font-size:9.5px;color:#94a3b8;">🌅 翌朝GU / 陽線</div><div style="font-size:12px;font-weight:700;">{r["prob"]}% / {r["intraday_win_rate"]}%</div></div>'
        f'</div>'

        f'<div class="trade-plan-box">'
        f'<div><div style="font-size:9.5px;color:#94a3b8;">🌅 夜間理論寄付き</div><div style="font-size:12px;font-weight:700;">{r["pts_est_price"]} ({ps}{r["pts_gap_pct"]}%)</div></div>'
        f'<div style="border-left:1px solid rgba(148,163,184,0.16);border-right:1px solid rgba(148,163,184,0.16);"><div style="font-size:9.5px;color:#10b981;">🎯 利確目標</div><div style="font-size:12px;font-weight:800;color:#10b981;">{r["tp_price"]} (+{r["tp_pct"]}%)</div></div>'
        f'<div><div style="font-size:9.5px;color:#f87171;">🛡️ 逆指値(損切)</div><div style="font-size:12px;font-weight:800;color:#f87171;">{r["sl_price"]} ({r["sl_pct"]}%)</div></div>'
        f'</div>'

        f'<div class="sizing-box">'
        f'<span>📦 <b>推奨ロット: {lot["shares"]:,}株</b> ({st_info["risk_posture"].split("（")[0]}) ｜ 投資額 {lot["position_value"]:,.0f}円</span>'
        f'<span>基準VWAP: <b>{r["vwap_price"]}</b></span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    # 【改修】銘柄に密着させたボタン配置（真ん中ではなく上寄せ）
    is_open = st.session_state["active_debates"].get(uk, False)
    in_wl = r["code"] in st.session_state["watchlist"]
    b_col1, b_col2 = st.columns([2.6, 1.4])
    if b_col1.button("▲ 量子＆マルチAI合議を閉じる" if is_open else "⚛️ リアルタイムAI合議＆買い方を見る", key=f"b_{uk}", use_container_width=True):
        st.session_state["active_debates"][uk] = not is_open
        st.rerun()
    if b_col2.button("✅ 監視中" if in_wl else "⭐ 監視リストへ追加", key=f"w_{uk}", use_container_width=True):
        if in_wl: del st.session_state["watchlist"][r["code"]]
        else: st.session_state["watchlist"][r["code"]] = r
        st.rerun()

    render_council_sec(r, uk, active_spks=sidebar_active_ais, posture=sidebar_debate_posture, api_configs=ai_multi_api_configs)

# ==========================================
# 15. サイドバー再構築（アコーディオン化・通知ポップアップ）
# ==========================================
with st.sidebar:
    cu = st.session_state.get("authenticated_user", "")
    with get_db() as conn:
        u_row = conn.execute("SELECT name FROM members WHERE email = ?", (cu,)).fetchone()
        u_name = u_row["name"] if u_row else "会員"
        # 新規保留中の申請チェック
        pending_members = conn.execute("SELECT * FROM members WHERE status = 'pending' ORDER BY applied_at DESC").fetchall()
    
    is_admin = (cu == ADMIN_EMAIL or is_seed_admin_email(cu))
    
    # ユーザー表示
    st.markdown(
        f'<div style="background:#0f172a;padding:12px;border-radius:10px;border:1px solid rgba(168,85,247,0.4);margin-bottom:12px;">'
        f'<div style="font-size:10px;color:#c084fc;font-weight:800;">⚛️ {"👑 システム管理者" if is_admin else "💎 会員セッション"}</div>'
        f'<div style="color:#ffffff;font-size:14px;font-weight:800;">{sanitize(u_name)} 様</div>'
        f'<div style="color:#64748b;font-size:10px;font-family:\'JetBrains Mono\';">{sanitize(cu)}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    # 管理コンソール開閉ボタン
    if is_admin:
        if st.button("🛡️ 管理者マネジメントコンソール", key="adm_toggle_btn", use_container_width=True):
            st.session_state["admin_console_open"] = not st.session_state["admin_console_open"]
            st.rerun()

        # 【新規会員申請の即時承認ポップアップバナー】
        if pending_members:
            st.markdown(
                f'<div class="urgent-approval-banner">'
                f'<div style="font-size:12px;font-weight:800;color:#fef08a;">🚨 新規会員申請が {len(pending_members)} 件あります！</div>'
                f'<div style="font-size:10.5px;color:#fef9c3;margin-top:2px;">ワンクリックで承認または拒否できます。</div>'
                f'</div>',
                unsafe_allow_html=True
            )
            for pm in pending_members:
                pem = pm["email"]
                with st.container():
                    st.caption(f"👤 **{pm['name']}** ({pem})")
                    ac1, ac2 = st.columns(2)
                    if ac1.button("🟢 承認", key=f"quick_app_{pem}", use_container_width=True):
                        with get_db() as conn:
                            conn.execute("UPDATE members SET status = 'approved', approved_at = ? WHERE email = ?", (datetime.now().strftime("%Y-%m-%d %H:%M"), pem))
                            conn.commit()
                        st.success(f"{pm['name']} を承認しました")
                        st.rerun()
                    if ac2.button("🔴 拒否", key=f"quick_rej_{pem}", use_container_width=True):
                        with get_db() as conn:
                            conn.execute("UPDATE members SET status = 'banned' WHERE email = ?", (pem,))
                            conn.execute("INSERT OR REPLACE INTO security_bans (key_val, ban_type, email, name, banned_at, reason) VALUES (?, 'email', ?, ?, ?, '管理者申請拒否')", (pem, pem, pm["name"], datetime.now().strftime("%Y-%m-%d %H:%M")))
                            conn.commit()
                        st.warning(f"{pm['name']} を拒否・BANしました")
                        st.rerun()

    # 各種設定（アコーディオン化で見やすさ劇的向上）
    with st.expander("🎯 投資スタイル選択", expanded=True):
        investment_style = st.selectbox(
            "スタイル",
            ["⚡ デイトレード (前場・後場の波及を狙う)", "🚀 スキャルピング (秒〜分単位のモメンタム)", "📈 スイングトレード (数日〜数週間のトレンド)", "💎 バイ＆ホールド (中長期・現物保有)"],
            index=0, label_visibility="collapsed"
        )

    with st.expander("⚙️ テクニカル＆アルゴリズム切替", expanded=False):
        toggle_fn = getattr(st, "toggle", st.checkbox)
        show_5m_chart = toggle_fn("📈 5分足＆VWAP描画", value=True)
        ac_b = set()
        BOOST_MAP = {"⚛️ 量子力学波動(QWM-7)": "algo", "🏛️ 機関最新アルゴ(Kyleλ・Hurst)": "ms", "🏦 機関VPIN・SmartMoney": "inst", "🔥 5ch実況＆短期モメンタム": "mom"}
        for b_label, b_key in BOOST_MAP.items():
            if st.checkbox(b_label, value=True, key=f"algo_sw_{b_key}"):
                ac_b.add(b_key)

    with st.expander("🏛️ 7知能AI合議システム設定", expanded=False):
        sidebar_debate_posture = st.select_slider("合議スタンス", options=["🛡️ 厳格防衛(安全重視)", "⚖️ 標準バランス", "🔥 攻撃的(強気利益狙い)"], value="⚖️ 標準バランス")
        active_roster = get_active_agents_dict()
        sidebar_active_ais = []
        for k_spk, ag_data in active_roster.items():
            if st.checkbox(f"{ag_data['name']} ({ag_data['role_title']})", value=True, key=f"spk_toggle_{k_spk}"):
                sidebar_active_ais.append(k_spk)

    # 【AGI巡回・エージェント解雇＆登用履歴ウィジェット】
    with st.expander("🔄 AGIエージェント代謝・監査履歴", expanded=False):
        fired_list, new_list = get_fired_and_new_agents_history()
        if fired_list:
            st.markdown("<b style='color:#ef4444;font-size:11.5px;'>💀 直近解雇されたエージェント:</b>", unsafe_allow_html=True)
            for f_ag in fired_list:
                with st.popover(f"❌ {f_ag['name']} ({f_ag['role_title']})"):
                    st.write(f"**解雇理由:** {f_ag['fired_reason']}")
                    st.write(f"**年齢:** {f_ag['age']}歳 ｜ **専門:** {f_ag['specialty']}")
                    st.write(f"**解雇日時:** {f_ag['fired_at']}")
        if new_list:
            st.markdown("<b style='color:#10b981;font-size:11.5px;margin-top:6px;'>✨ 新鋭・登用エージェント:</b>", unsafe_allow_html=True)
            for n_ag in new_list:
                with st.popover(f"⭐ {n_ag['name']} ({n_ag['role_title']})"):
                    st.write(f"**年齢:** {n_ag['age']}歳 ｜ **専門分野:** {n_ag['specialty']}")
                    st.write(f"**性格・特徴:** {n_ag['personality']}")
                    st.write(f"**登用日時:** {n_ag['joined_at']}")

    # 複数APIキー同時接続設定
    with st.expander("🤖 複数AI API同時接続エンジン設定", expanded=False):
        st.caption("複数キーを設定すると、完全並列で非同期通信を行い負荷を分散・爆速化します。")
        ai_multi_api_configs = {}
        for p_name, def_mod in [("OpenAI", "gpt-4o"), ("Gemini", "gemini-1.5-flash"), ("Anthropic", "claude-3-5-sonnet-20241022")]:
            k = st.text_input(f"{p_name} API Key", type="password", key=f"api_key_in_{p_name}")
            ai_multi_api_configs[p_name] = {"api_key": k.strip(), "model": def_mod}

    with st.expander("💰 資金管理＆リスク設定", expanded=False):
        total_capital = st.number_input("総投資資金 (円/ドル)", min_value=10000, max_value=1000000000, value=1000000, step=50000)
        risk_tolerance_pct = st.slider("1トレード許容リスク (%)", 0.5, 5.0, 2.0, 0.5)
        survival_cut_pct = st.slider("各タブ選抜率 (%)", 40, 100, 75, 5)

    st.markdown("---")
    if st.button("🚪 ログアウト", use_container_width=True):
        with get_db() as conn:
            conn.execute("UPDATE members SET last_seen_ts = 0 WHERE email = ?", (cu,))
            conn.commit()
        st.session_state["authenticated_user"] = None
        st.query_params.clear()
        st.rerun()

# ==========================================
# 16. 管理者マネジメントコンソール（完全独立モーダル）
# ==========================================
if is_admin and st.session_state.get("admin_console_open"):
    st.markdown(
        f'<div style="background:#090e1a;border:1px solid rgba(56,189,248,0.5);border-radius:14px;padding:20px;margin-bottom:20px;box-shadow:0 10px 30px rgba(0,0,0,0.85);">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<div><h3 style="margin:0;color:#38bdf8;">👑 システム管理者マネジメントコンソール</h3>'
        f'<div style="color:#94a3b8;font-size:12px;">会員ステータス完全制御・リアルタイム承認・AGI代謝監査</div></div>'
        f'</div></div>',
        unsafe_allow_html=True
    )
    
    t_mng1, t_mng2, t_mng3, t_mng4 = st.tabs([
        "👥 会員詳細管理・個別操作",
        "🚫 不正アクセス・なりすまし監視ログ",
        "🔄 AGIエージェント監査・解雇履歴",
        "🛡️ 永久BAN端末リスト"
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
                    f"- **パスコード:** `{mb['passcode'] or '未発行'}`\n"
                    f"- **端末指紋:** `{mb['fp']}`\n"
                    f"- **申請日時:** {mb['applied_at']} ｜ **承認日時:** {mb['approved_at']}"
                )
                if not is_adm_row:
                    b1, b2, b3 = c_action.columns(3)
                    if mb["status"] != "approved" and b1.button("🟢 再開/承認", key=f"c_app_{em}", use_container_width=True):
                        with get_db() as conn:
                            conn.execute("UPDATE members SET status = 'approved', approved_at = ? WHERE email = ?", (datetime.now().strftime("%Y-%m-%d %H:%M"), em))
                            conn.execute("DELETE FROM security_bans WHERE email = ?", (em,))
                            conn.commit()
                        st.rerun()
                    if mb["status"] != "pending" and b2.button("⏸️ 一時停止", key=f"c_pnd_{em}", use_container_width=True):
                        with get_db() as conn:
                            conn.execute("UPDATE members SET status = 'pending' WHERE email = ?", (em,))
                            conn.commit()
                        st.rerun()
                    if mb["status"] != "banned" and b3.button("🔴 永久BAN", key=f"c_ban_{em}", use_container_width=True):
                        with get_db() as conn:
                            conn.execute("UPDATE members SET status = 'banned' WHERE email = ?", (em,))
                            conn.execute("INSERT OR REPLACE INTO security_bans (key_val, ban_type, email, name, banned_at, reason) VALUES (?, 'email', ?, ?, ?, '手動BAN')", (em, em, mb["name"], datetime.now().strftime("%Y-%m-%d %H:%M")))
                            conn.commit()
                        st.rerun()
                else:
                    c_action.info("👑 ルート管理者アカウント")

    with t_mng2:
        with get_db() as conn:
            s_logs = conn.execute("SELECT * FROM spoof_logs ORDER BY id DESC LIMIT 50").fetchall()
        if s_logs:
            st.dataframe(pd.DataFrame([dict(x) for x in s_logs]), use_container_width=True)
        else: st.info("不審なアクセスやBAN端末からの侵入試行は検知されていません。")

    with t_mng3:
        st.markdown("#### 🤖 AGI巡回エージェント監査台帳")
        with get_db() as conn:
            all_agents = conn.execute("SELECT agent_id, name, role_title, status, age, specialty, consecutive_repetition_count, fired_reason, fired_at FROM agi_agent_roster ORDER BY status ASC, rowid ASC").fetchall()
        st.dataframe(pd.DataFrame([dict(x) for x in all_agents]), use_container_width=True)

    with t_mng4:
        with get_db() as conn:
            b_list = conn.execute("SELECT * FROM security_bans ORDER BY banned_at DESC").fetchall()
        if b_list: st.dataframe(pd.DataFrame([dict(x) for x in b_list]), use_container_width=True)
        else: st.caption("現在登録されているBAN端末指紋はありません。")

    if st.button("✕ 管理コンソールを閉じる", use_container_width=True):
        st.session_state["admin_console_open"] = False
        st.rerun()
    st.stop()

# ==========================================
# 17. メインダッシュボード描画
# ==========================================
mpills = "".join([f'<div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);padding:3px 8px;border-radius:6px;font-size:11px;display:inline-flex;gap:5px;"><span style="color:#94a3b8;">{m["label"]}</span><span style="color:{"#10b981" if m["diff"]>=0 else "#ef4444"};font-weight:700;">{"+" if m["diff"]>=0 else ""}{m["diff"]}%</span></div>' for m in macro_info.values()])
st.markdown(
    f'<div style="background:radial-gradient(circle at top right, rgba(168,85,247,0.14), transparent 60%), linear-gradient(145deg,#0f172a 0%,#070b14 100%);border:1px solid rgba(148,163,184,0.2);border-radius:14px;padding:14px 18px;margin-bottom:18px;">'
    f'<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">'
    f'<div style="min-width:0;flex:1;"><div class="brand-luxury">YAMASHISHI LAB</div><div style="font-family:\'JetBrains Mono\';font-size:10px;color:#64748b;letter-spacing:1.5px;margin-top:2px;">QUANTUM WAVEFUNCTION & MULTI-AGENT TERMINAL</div></div>'
    f'<span style="background:rgba(168,85,247,0.16);border:1px solid rgba(168,85,247,0.45);color:#e9d5ff;padding:4px 9px;border-radius:999px;font-size:10.5px;font-weight:700;">⚛️ 本格AI並列連携稼働</span>'
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

# 【改修】ご指定のタブ順序：TOP5の右に「📋 監視リスト」、次に「🚀 IPO申し込み受付」を配置
cats = ["🏆 総合TOP5", "📋 監視リスト", "🚀 IPO申し込み受付", "⚛️ 量子トンネル突破TOP10", "🏛️ 機関最新ミクロ構造TOP10", "🏦 機関VPIN・OFI", "🔥 5ch＆短期モメンタム"] + [f"📂 {g}" for g in STOCK_POOL.keys()]

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
    if st.button("⚡ 総合TOP3をワンタップ一括登録", use_container_width=True):
        for it in surv[:3]: st.session_state["watchlist"][it["code"]] = it
        st.rerun()
    if wl:
        for wc, wi in list(wl.items()): render_card(wi, kp=f"wl_{wc}")
    else:
        st.info("現在監視リストに銘柄はありません。銘柄カードの「⭐ 監視リストへ追加」を押すとここに追加されます。")

elif sel_cat == "🚀 IPO申し込み受付":
    st.markdown("### 🚀 直近IPO（新規公開株）BB受付・注目度ランキング")
    st.caption("量子・アルゴリズム期待度順にソート。ブックビルディング期間、仮条件、主幹事証券リンクを網羅しています。")
    
    for ipo in IPO_UPCOMING_LIST:
        rk_badge_bg = "#dc2626" if ipo["rank"] == "S" else ("#0284c7" if ipo["rank"] == "A" else "#334155")
        st.markdown(
            f'<div class="rank-card" style="border-left: 4px solid {rk_badge_bg};">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<div><span class="pill-badge" style="background:{rk_badge_bg};color:#fff;font-weight:900;">初値期待度 {ipo["rank"]}級 ({ipo["score"]}点)</span>'
            f'<span style="font-size:17px;font-weight:800;color:#ffffff;margin-left:5px;">{ipo["name"]}</span> <span style="color:#94a3b8;font-size:12px;">({ipo["code"]} / {ipo["market"]})</span></div>'
            f'<a href="{ipo["url"]}" target="_blank" style="background:#0284c7;color:#fff;text-decoration:none;font-size:11.5px;font-weight:700;padding:5px 12px;border-radius:6px;">証券会社で申込む ↗</a>'
            f'</div>'
            f'<div style="margin-top:8px;font-size:12.5px;color:#cbd5e1;line-height:1.6;">{ipo["desc"]}</div>'
            f'<div class="trade-plan-box" style="margin-top:10px;">'
            f'<div><div style="font-size:9.5px;color:#94a3b8;">📅 BB申込期間</div><div style="font-size:11.5px;font-weight:800;color:#fde047;">{ipo["bb_period"]}</div></div>'
            f'<div><div style="font-size:9.5px;color:#94a3b8;">💰 想定発行価格</div><div style="font-size:11.5px;font-weight:800;color:#38bdf8;">{ipo["price"]}</div></div>'
            f'<div><div style="font-size:9.5px;color:#94a3b8;">🏛️ 取扱幹事証券</div><div style="font-size:11px;font-weight:700;color:#e2e8f0;">{ipo["lead"]}</div></div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True
        )

elif sel_cat == "⚛️ 量子トンネル突破TOP10":
    for i, r in enumerate(sorted(all_res, key=lambda x: (x["q_score"], x["q_tunnel"], x["expect_pct"]), reverse=True)[:10], 1): render_card(r, rank=i, kp="qtop")
elif sel_cat == "🏛️ 機関最新ミクロ構造TOP10":
    for i, r in enumerate(sorted(all_res, key=lambda x: (x["ms_score"], x["kyle_stealth"], x["expect_pct"]), reverse=True)[:10], 1): render_card(r, rank=i, kp="mstop")
elif sel_cat == "🏦 機関VPIN・OFI":
    for i, r in enumerate(sorted(all_res, key=lambda x: (x["inst_score"], x["ofi_z"], x["expect_pct"]), reverse=True)[:10], 1): render_card(r, rank=i, kp="inst")
elif sel_cat == "🔥 5ch＆短期モメンタム":
    for i, r in enumerate(sorted(all_res, key=lambda x: (x["board5ch_score"], x["expect_pct"], x["ofi_z"]), reverse=True)[:10], 1): render_card(r, rank=i, kp="mom")
elif sel_cat.startswith("📂 "):
    gk = sel_cat.replace("📂 ", "")
    gs, _ = cut_stocks(g_res.get(gk, []), survival_cut_pct)
    for i, r in enumerate(gs, 1): render_card(r, rank=i, kp=f"g_{gk}")
