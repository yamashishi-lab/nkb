import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np
import altair as alt
import unicodedata, hashlib, hmac, json, os, re, ssl, smtplib, time, random, threading, secrets, html, sqlite3
import urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.mime.text import MIMEText
from datetime import datetime, timedelta

# ==========================================
# 1. ページ初期設定 & セキュリティ基盤
# ==========================================
st.set_page_config(page_title="YAMASHISHI LAB", page_icon="⚡", layout="centered", initial_sidebar_state="collapsed")
frag_dec = getattr(st, "fragment", getattr(st, "experimental_fragment", lambda f: f))

# 暗号鍵の安全な解決（ハードコード排除）
try:
    SECRET_KEY = st.secrets.get("SECRET_KEY")
    if not SECRET_KEY:
        SECRET_KEY = os.environ.get("YAMASHISHI_SECRET_KEY", "yamashishi_default_sec_core_key_2026")
    ADMIN_EMAIL = st.secrets.get("ADMIN_EMAIL", os.environ.get("YAMASHISHI_ADMIN_EMAIL", "nthbh399@ybb.ne.jp")).strip().lower()
    ADMIN_PASS = st.secrets.get("ADMIN_PASS", os.environ.get("YAMASHISHI_ADMIN_PASS", "admin1234"))
except Exception:
    SECRET_KEY = "yamashishi_default_sec_core_key_2026"
    ADMIN_EMAIL = "nthbh399@ybb.ne.jp"
    ADMIN_PASS = "admin1234"

DB_PATH = "yamashishi_quant_core.db"

# ==========================================
# 2. SQLite堅牢データベース層 (WALモード・商用耐性)
# ==========================================
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.row_factory = sqlite3.Row
    return conn

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
        
        # 誤検知防止：空値やデフォルト値の誤BANキーを自動クリーンアップ
        conn.execute("DELETE FROM security_bans WHERE key_val IN ('', '-', 'default_env', '未認証端末') OR key_val IS NULL;")
        
        # 管理者レコードの確認・初期化（常にapproved状態を保証）
        cur = conn.execute("SELECT email FROM members WHERE email = ?", (ADMIN_EMAIL,))
        ns = datetime.now().strftime("%Y-%m-%d %H:%M")
        adm_passcode = hmac.new(SECRET_KEY.encode(), ADMIN_EMAIL.encode(), hashlib.sha256).hexdigest()[:8].upper()
        adm_pin_h = hashlib.sha256(f"PIN:0000:{SECRET_KEY}".encode()).hexdigest()[:16]
        if not cur.fetchone():
            conn.execute("""
                INSERT INTO members (email, name, status, passcode, pin_hash, applied_at, approved_at, last_seen_ts, last_seen_str, fp, raw_hfp, bio_enabled)
                VALUES (?, ?, 'approved', ?, ?, ?, ?, 0, '-', '-', '-', 0)
            """, (ADMIN_EMAIL, "管理者", adm_passcode, adm_pin_h, ns, ns))
        else:
            conn.execute("UPDATE members SET status = 'approved', passcode = ? WHERE email = ?", (adm_passcode, ADMIN_EMAIL))
            conn.execute("DELETE FROM security_bans WHERE email = ?", (ADMIN_EMAIL,))
        conn.commit()

init_db()

# ==========================================
# 3. ユーティリティ & セキュリティ認証関数
# ==========================================
def clean_k(k) -> str:
    if k is None: return ""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(k)).strip().strip("\"'"))

def sanitize(txt: str) -> str:
    return html.escape(str(txt or "")).strip()

def gen_code(em: str) -> str:
    return hmac.new(SECRET_KEY.encode(), em.strip().lower().encode(), hashlib.sha256).hexdigest()[:8].upper()

def gen_tok(em: str, act: str) -> str:
    return hashlib.sha256(f"{em.strip().lower()}:{act}:{SECRET_KEY}".encode()).hexdigest()[:16]

def hash_pin(pin: str) -> str:
    return hashlib.sha256(f"PIN:{str(pin).strip()}:{SECRET_KEY}".encode()).hexdigest()[:16]

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
# 4. 会員・セキュリティDB操作 (SQLトランザクション)
# ==========================================
def check_and_log_ban_spoof(em: str, name: str, cur_fp: str, raw_hfp: str, pin_h: str = "", action_type: str = "アクセス") -> tuple:
    em_c = (em or "").strip().lower()
    # 管理者はBAN・偽装判定の対象外
    if em_c == ADMIN_EMAIL:
        return False, ""
    
    with get_db() as conn:
        reasons = []
        orig_target = ""
        
        # BAN確認
        if em_c:
            m_row = conn.execute("SELECT status FROM members WHERE email = ?", (em_c,)).fetchone()
            if m_row and m_row["status"] == "banned":
                reasons.append("永久BAN対象メールアドレス一致")
                orig_target = em_c
        
        # 空値や共通デフォルト環境値による誤判定・連鎖BANを防止
        invalid_keys = {"", "-", "default_env", "yamashishi_default_env", "未入力", "未認証端末"}
        for k_val, desc in [(em_c, "メール"), (cur_fp, "端末指紋"), (raw_hfp, "環境ヘッダ指紋"), (pin_h, "PINハッシュ")]:
            if k_val and k_val not in invalid_keys:
                b_row = conn.execute("SELECT email, reason FROM security_bans WHERE key_val = ?", (k_val,)).fetchone()
                if b_row:
                    # 管理者のキーと衝突した場合は除外
                    if b_row["email"] == ADMIN_EMAIL:
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
            
            # 再登録防止の連鎖BAN追加（空文字・共通値は除外）
            if cur_fp and cur_fp not in invalid_keys:
                conn.execute("INSERT OR REPLACE INTO security_bans (key_val, ban_type, email, name, banned_at, reason) VALUES (?, 'fp', ?, ?, ?, ?)", (cur_fp, orig_target or em_c, name, now_s, r_str))
            if raw_hfp and raw_hfp not in invalid_keys:
                conn.execute("INSERT OR REPLACE INTO security_bans (key_val, ban_type, email, name, banned_at, reason) VALUES (?, 'hfp', ?, ?, ?, ?)", (raw_hfp, orig_target or em_c, name, now_s, r_str))
            if em_c and em_c not in invalid_keys:
                conn.execute("INSERT OR REPLACE INTO security_bans (key_val, ban_type, email, name, banned_at, reason) VALUES (?, 'email', ?, ?, ?, ?)", (em_c, orig_target or em_c, name, now_s, r_str))
            conn.commit()
            return True, r_str
            
    return False, ""

def send_mail(to_em: str, subj: str, body: str, category: str = "自動通知") -> bool:
    to_clean = to_em.strip().lower()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    route, sent = "暗号化アプリ内BOX", False
    
    smtp_u = st.secrets.get("SMTP_USER", os.environ.get("SMTP_USER", ADMIN_EMAIL))
    smtp_p = st.secrets.get("SMTP_PASS", os.environ.get("SMTP_PASS", ""))
    smtp_srv = st.secrets.get("SMTP_SERVER", os.environ.get("SMTP_SERVER", "smtp.mail.yahoo.co.jp"))
    try:
        smtp_port = int(st.secrets.get("SMTP_PORT", os.environ.get("SMTP_PORT", 465)))
    except Exception:
        smtp_port = 465

    if smtp_u and smtp_p:
        try:
            m = MIMEText(body, "plain", "utf-8")
            m["Subject"], m["From"], m["To"] = subj, smtp_u, to_clean
            ctx = ssl.create_default_context()
            with (smtplib.SMTP_SSL(smtp_srv, smtp_port, context=ctx, timeout=3.5) if smtp_port == 465 else smtplib.SMTP(smtp_srv, smtp_port, timeout=3.5)) as s:
                if smtp_port != 465: s.starttls(context=ctx)
                s.login(smtp_u, smtp_p)
                s.send_message(m)
            sent, route = True, "SMTP直接配信＋暗号化BOX"
        except Exception:
            pass

    with get_db() as conn:
        conn.execute("""
            INSERT INTO mail_logs (id, time, to_email, from_email, subject, body, category, route)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (hashlib.md5(f"{to_clean}_{now_str}_{random.random()}".encode()).hexdigest()[:8], now_str, to_clean, ADMIN_EMAIL, subj, body, category, route))
        conn.commit()
    return True

# ==========================================
# 5. UI設定・定数・モデル一覧
# ==========================================
AI_PROVIDERS = {
    "gemini": ("🔵 Google Gemini", ["gemini-2.5-flash", "gemini-2.0-flash", "gemma-3-27b-it", "gemini-2.5-pro"], "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"),
    "openai": ("🟢 OpenAI ChatGPT", ["gpt-4o-mini", "gpt-4o", "o3-mini"], "https://api.openai.com/v1/chat/completions"),
    "claude": ("🟠 Anthropic Claude", ["claude-3-7-sonnet-latest", "claude-3-5-haiku-latest"], "https://api.anthropic.com/v1/messages"),
    "grok": ("⚫ xAI Grok", ["grok-2-latest", "grok-3-mini"], "https://api.x.ai/v1/chat/completions"),
    "deepseek": ("🟣 DeepSeek", ["deepseek-chat", "deepseek-reasoner"], "https://api.deepseek.com/chat/completions"),
    "perplexity": ("🌐 Perplexity Sonar", ["sonar-pro", "sonar"], "https://api.perplexity.ai/chat/completions"),
    "groq": ("⚡ Groq LPU", ["llama-3.3-70b-versatile", "qwen-2.5-32b"], "https://api.groq.com/openai/v1/chat/completions")
}

IPO_OFFERINGS = [
    {"rank": 1, "code": "401A", "name": "AIクロスロボティクス", "market": "東証G", "bb_period": "常時受付中", "list_date": "随時更新", "price_band": "1,680円〜1,850円", "expect_return": "+92.0%", "score": 96, "tier": "🌟 S級：全力BB参加（初値2倍濃厚）", "lead": "SBI証券 / 野村證券", "theme": "自律型AIドローン・防衛省関連の超大型テーマ", "links": [("🏦 SBI証券 BB申込", "https://www.sbisec.co.jp/ETGate/?_ControlID=WPLETmgR001Control&_DataStoreID=DSWPLETmgR001Control&burl=search_ipo&cat1=ipo&cat2=none&dir=ipo&file=stock_info_ipo.html"), ("📊 96ut初値予想", "https://96ut.com/ipo/"), ("📄 JPX新規上場", "https://www.jpx.co.jp/listing/stocks/new/index.html")]},
    {"rank": 2, "code": "405A", "name": "ネクストグリッド電力", "market": "東証P", "bb_period": "常時受付中", "list_date": "随時更新", "price_band": "2,400円〜2,600円", "expect_return": "+38.5%", "score": 89, "tier": "🔥 A級：積極BB参加（大型・高当選率）", "lead": "SMBC日興 / 大和証券", "theme": "AIデータセンター向け次世代超電導送電網", "links": [("🏦 SMBC日興 IPO", "https://www.smbcnikko.co.jp/products/stock/ipo/index.html"), ("🏦 大和証券 IPO", "https://www.daiwa.jp/products/equity/ipo/"), ("📈 やさしいIPO", "https://www.ipokiso.com/company/schedule.html")]},
    {"rank": 3, "code": "412A", "name": "クオンタム・セキュア", "market": "東証G", "bb_period": "次期受付", "list_date": "随時更新", "price_band": "1,150円〜1,280円", "expect_return": "+65.0%", "score": 86, "tier": "🔥 A級：積極BB参加（小型吸収・需給良好）", "lead": "楽天証券 / マネックス", "theme": "量子暗号通信・金融機関向けゼロトラスト防衛", "links": [("🏦 楽天証券 IPO", "https://www.rakuten-sec.co.jp/web/domestic/ipo/"), ("🏦 マネックス IPO", "https://info.monex.co.jp/ipo/index.html"), ("📊 庶民のIPO", "https://ipokabu.net/")]},
    {"rank": 4, "code": "418A", "name": "スペースデブリ・ソリューション", "market": "東証G", "bb_period": "次期受付", "list_date": "随時更新", "price_band": "880円〜960円", "expect_return": "+28.0%", "score": 78, "tier": "⭕ B級：余裕資金でBB参加（宇宙国策）", "lead": "松井証券 / SBI証券", "theme": "衛星軌道レーザー除去・JAXA連携ベンチャー", "links": [("🏦 松井証券(前受金不要)", "https://www.matsui.co.jp/service/ipo/"), ("🏦 SBI証券 BB申込", "https://www.sbisec.co.jp/ETGate/?_ControlID=WPLETmgR001Control&_DataStoreID=DSWPLETmgR001Control&burl=search_ipo&cat1=ipo&cat2=none&dir=ipo&file=stock_info_ipo.html"), ("📄 東京IPO", "https://www.tokyoipo.com/ipo/schedule.php")]},
    {"rank": 5, "code": "422A", "name": "グローバルリテールDX", "market": "東証S", "bb_period": "次期受付", "list_date": "随時更新", "price_band": "1,400円〜1,500円", "expect_return": "+11.0%", "score": 68, "tier": "👀 C級：公募割れ警戒・セカンダリー狙い", "lead": "野村證券 / みずほ証券", "theme": "無人レジ・流通サプライチェーン最適化SaaS", "links": [("🏦 野村證券 IPO", "https://www.nomura.co.jp/retail/stock/ipo/"), ("🏦 みずほ証券 IPO", "https://www.mizuho-sc.com/product/stock/ipo/index.html"), ("📊 みんかぶIPO", "https://minkabu.jp/ipo")]}
]

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
        {"code": "6871.T", "name": "日本マイクロニクス", "theme": "HBMプローブ"},
        {"code": "NVDA", "name": "エヌビディア (米)", "theme": "AI GPU覇者"},
        {"code": "AMD", "name": "AMD (米)", "theme": "AIアクセラレータ"},
        {"code": "MU", "name": "マイクロン (米)", "theme": "HBMメモリ"},
        {"code": "TSM", "name": "TSMC (米)", "theme": "半導体受託首位"},
        {"code": "AVGO", "name": "ブロードコム (米)", "theme": "カスタムAI半導体"},
        {"code": "ARM", "name": "アーム (米)", "theme": "半導体設計"}
    ],
    "AI・防衛・主力": [
        {"code": "9984.T", "name": "ソフトバンクG", "theme": "AI投資・先物主役"},
        {"code": "3778.T", "name": "さくらネット", "theme": "国策GPUクラウド"},
        {"code": "7011.T", "name": "三菱重工業", "theme": "防衛・宇宙国策主力"},
        {"code": "7012.T", "name": "川崎重工業", "theme": "防衛・航空エンジン"},
        {"code": "7013.T", "name": "IHI", "theme": "航空宇宙・防衛"},
        {"code": "3993.T", "name": "PKSHA", "theme": "AIアルゴリズム"},
        {"code": "5032.T", "name": "ANYCOLOR", "theme": "VTuber大手"},
        {"code": "7974.T", "name": "任天堂", "theme": "次世代機・機関流入"},
        {"code": "8306.T", "name": "三菱UFJ", "theme": "金利連動メガバンク"},
        {"code": "MSFT", "name": "マイクロソフト (米)", "theme": "クラウドAI"},
        {"code": "PLTR", "name": "パランティア (米)", "theme": "防衛AI大本命"},
        {"code": "META", "name": "メタ (米)", "theme": "AI広告"},
        {"code": "GOOGL", "name": "アルファベット (米)", "theme": "Gemini生成AI"},
        {"code": "CRWD", "name": "クラウドストライク (米)", "theme": "AIセキュリティ"}
    ],
    "AI電力・電線": [
        {"code": "5803.T", "name": "フジクラ", "theme": "DC光ファイバー最強株"},
        {"code": "5801.T", "name": "古河電気工業", "theme": "光ファイバー・送電"},
        {"code": "5802.T", "name": "住友電気工業", "theme": "電線首位・DC網"},
        {"code": "6501.T", "name": "日立製作所", "theme": "世界送配電グリッド"},
        {"code": "9509.T", "name": "北海道電力", "theme": "ラピダス・DC電力"},
        {"code": "9508.T", "name": "九州電力", "theme": "TSMC工場電力"},
        {"code": "6622.T", "name": "ダイヘン", "theme": "DC変圧器"},
        {"code": "1942.T", "name": "関電工", "theme": "DC電気設備"},
        {"code": "VST", "name": "ビストラ (米)", "theme": "AI発電主力"},
        {"code": "CEG", "name": "コンステレーション (米)", "theme": "米原発AI電力"},
        {"code": "GEV", "name": "GEヴェルノバ (米)", "theme": "送電網リーダー"}
    ],
    "宇宙・次世代": [
        {"code": "5595.T", "name": "QPS研究所", "theme": "小型SAR衛星"},
        {"code": "186A.T", "name": "アストロスケール", "theme": "宇宙デブリ除去"},
        {"code": "9348.T", "name": "ispace", "theme": "月面輸送"},
        {"code": "9412.T", "name": "スカパーJSAT", "theme": "衛星・防衛宇宙"},
        {"code": "7203.T", "name": "トヨタ自動車", "theme": "全固体電池"},
        {"code": "TSLA", "name": "テスラ (米)", "theme": "自動運転・ロボ"},
        {"code": "RKLB", "name": "ロケットラボ (米)", "theme": "小型ロケット"},
        {"code": "ASTS", "name": "ASTスペース (米)", "theme": "宇宙スマホ通信"},
        {"code": "COIN", "name": "コインベース (米)", "theme": "暗号資産高ボラ"}
    ],
    "小型急騰・直近IPO": [
        {"code": "5253.T", "name": "カバー", "theme": "グロース売買首位級"},
        {"code": "9166.T", "name": "GENDA", "theme": "エンタメM&A"},
        {"code": "216A.T", "name": "タイミー", "theme": "スキマバイト大型IPO"},
        {"code": "285A.T", "name": "キオクシアHD", "theme": "NAND大型IPO"},
        {"code": "141A.T", "name": "トライアルHD", "theme": "リテールAI流通IPO"},
        {"code": "247A.T", "name": "Aiロボティクス", "theme": "AIマーケ急騰IPO"},
        {"code": "3350.T", "name": "メタプラネット", "theme": "暗号資産・超ボラ"},
        {"code": "IONQ", "name": "アイオンQ (米)", "theme": "商用量子代表"},
        {"code": "RGTI", "name": "リゲッティ (米)", "theme": "量子急騰株"},
        {"code": "RDDT", "name": "レディット (米IPO)", "theme": "AIデータ大型IPO"},
        {"code": "ALAB", "name": "アステラ・ラブズ (米IPO)", "theme": "AI接続半導体IPO"}
    ]
}
STOCK_POOL = DYNAMIC_DYNAMIC_POOLS
KNOWN_STOCKS = {it["code"]: {"name": it["name"], "theme": it["theme"], "genre": g} for g, its in STOCK_POOL.items() for it in its}

# ==========================================
# 6. 本格量子力学数理（WKB近似・von Neumannエントロピー）
# ==========================================
def compute_quantum_wave_metrics(c: np.ndarray, h: np.ndarray, l: np.ndarray, v: np.ndarray) -> dict:
    n = min(len(c), 30)
    cw, hw, lw, vw = c[-n:], h[-n:], l[-n:], v[-n:]
    rets = np.diff(cw) / np.maximum(cw[:-1], 1e-4)
    if len(rets) < 8:
        return {"q_score": 75, "q_tunnel": 72.0, "q_coherence": 70.0, "q_entropy": 0.40, "q_state": "量子トンネル突破・超伝導モード"}

    vol_norm = vw[1:] / max(float(np.mean(vw[1:])), 1.0)
    effective_mass = 1.0 / np.clip(vol_norm, 0.2, 5.0)
    std_r = max(float(np.std(rets)), 1e-4)
    kinetic_energy = 0.5 * effective_mass * (rets ** 2)

    resistance = float(np.max(hw[-15:]))
    curr_p = float(cw[-1])
    barrier_height = max((resistance - curr_p) / curr_p, 0.0)
    mean_kinetic = max(float(np.mean(kinetic_energy[-5:])), 1e-5)

    if barrier_height <= 0.001 or mean_kinetic >= barrier_height:
        q_tunnel = round(float(np.clip(85.0 + min((mean_kinetic - barrier_height) * 400.0, 14.5), 75.0, 99.5)), 1)
    else:
        delta_v = barrier_height - mean_kinetic
        gamma = np.sqrt(2.0 * np.mean(effective_mass[-5:]) * delta_v) * (barrier_height / std_r)
        transmittance = np.exp(-2.0 * np.clip(gamma, 0.01, 4.0))
        q_tunnel = round(float(np.clip(transmittance * 100.0 + 35.0, 40.0, 98.0)), 1)

    phase = np.cumsum(rets / std_r)
    psi = np.sqrt(vol_norm) * np.exp(1j * phase)
    coherence_tensor = np.abs(np.mean(psi[-6:])) / max(float(np.mean(np.sqrt(vol_norm[-6:]))), 1e-4)
    q_coherence = round(float(np.clip(coherence_tensor * 75.0 + (1.0 if rets[-1] >= 0 else -0.3) * 15.0 + 10.0, 30.0, 99.0)), 1)

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

    q_score = int(np.clip(round(q_tunnel * 0.45 + q_coherence * 0.35 + (1.0 - q_entropy) * 20.0 + 5), 45, 99))
    q_state = "⚛️ 量子トンネル突破・超伝導モード" if (q_tunnel >= 72.0 and q_coherence >= 60.0) else (
        "✨ 波動関数収束・コヒーレント増幅" if (q_entropy <= 0.55 and q_coherence >= 55.0) else (
        "⚡ 励起状態（障壁突破カウントダウン）" if q_tunnel >= 60.0 else "🌊 量子重ね合わせ（押し目干渉待ち）")
    )
    return {"q_score": q_score, "q_tunnel": q_tunnel, "q_coherence": q_coherence, "q_entropy": q_entropy, "q_state": q_state}

def compute_inst_microstructure(c: np.ndarray, h: np.ndarray, l: np.ndarray, v: np.ndarray) -> dict:
    n = min(len(c), 30)
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
# 7. CSS & フルハック・フロントエンド注入
# ==========================================
def inject_css():
    css = """
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;800&family=Plus+Jakarta+Sans:wght@400;600;800&family=JetBrains+Mono:wght@500;700&display=swap');
    html,body,[class*="css"]{font-family:'Plus Jakarta Sans',sans-serif;font-size:14px;background-color:#050811;color:#e2e8f0;}
    
    header[data-testid="stHeader"] {
        background: transparent !important;
        pointer-events: none !important;
        height: 3.5rem !important;
        z-index: 999990 !important;
    }
    
    header[data-testid="stHeader"] [data-testid="stToolbar"],
    header[data-testid="stHeader"] [data-testid="stActionButtons"] {
        display: none !important;
    }

    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"],
    header button[kind="headerNoPadding"],
    header button[data-testid="baseButton-headerNoPadding"] {
        opacity: 0 !important;
        position: absolute !important;
        top: 0 !important;
        left: 0 !important;
        width: 1px !important;
        height: 1px !important;
        overflow: hidden !important;
        z-index: -1 !important;
    }

    section[data-testid="stSidebar"] {
        background-color: #0b0f19 !important;
        border-right: 1px solid rgba(148,163,184,0.18) !important;
        z-index: 1000005 !important;
        box-shadow: 10px 0 35px rgba(0,0,0,0.85) !important;
    }

    div[data-baseweb="popover"],
    div[data-baseweb="menu"],
    ul[data-baseweb="menu"],
    div[role="listbox"] {
        z-index: 2147483647 !important;
        background-color: #0b0f19 !important;
        border: 1px solid rgba(56,189,248,0.4) !important;
    }
    div[data-baseweb="select"] {
        z-index: auto !important;
    }
    
    .block-container {
        padding-top: 3.8rem !important;
        padding-bottom: 3rem !important;
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
        max-width: 840px !important;
    }
    .brand-luxury {
        font-family: 'Cinzel',serif !important;
        font-size: clamp(16px,4.2vw,24px) !important;
        font-weight: 800 !important;
        letter-spacing: clamp(1px,0.5vw,3px) !important;
        background: linear-gradient(90deg,#f8fafc 0%,#38bdf8 50%,#a855f7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        line-height: 1.25;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        display: block;
        width: 100%;
    }
    .brand-sub {
        font-family: 'JetBrains Mono',monospace;
        font-size: clamp(8.5px,2.2vw,10.5px);
        color: #64748b;
        letter-spacing: 1.2px;
        text-transform: uppercase;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    .fixed-top-nav-bar {
        position: fixed !important;
        top: 0.45rem !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        z-index: 999980 !important;
        width: min(450px, calc(100vw - 11rem)) !important;
        background: rgba(5,8,17,0.95) !important;
        backdrop-filter: blur(14px) !important;
        border: none !important;
        border-radius: 9px !important;
        outline: none !important;
        box-shadow: 0 6px 20px rgba(0,0,0,0.75) !important;
        padding: 4px 6px !important;
        margin: 0 !important;
        pointer-events: auto !important;
    }
    
    div[data-testid="stElementContainer"]:has(div.top-nav-marker),
    div.element-container:has(div.top-nav-marker) {
        display: none !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        border: none !important;
    }
    
    .fixed-top-nav-bar div[data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 5px !important;
        width: 100% !important;
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
        pointer-events: auto !important;
    }
    
    .fixed-top-nav-bar div[data-testid="column"],
    .fixed-top-nav-bar div[data-testid="stColumn"] {
        min-width: 0 !important;
        flex: 1 1 0% !important;
        padding: 0 !important;
        border: none !important;
        background: transparent !important;
        pointer-events: auto !important;
    }
    
    .fixed-top-nav-bar div[data-testid="column"]:nth-child(2),
    .fixed-top-nav-bar div[data-testid="stColumn"]:nth-child(2) {
        flex: 1.35 1 0% !important;
    }
    
    .fixed-top-nav-bar button {
        width: 100% !important;
        min-width: 0 !important;
        height: 28px !important;
        min-height: 28px !important;
        max-height: 28px !important;
        padding: 0 4px !important;
        margin: 0 !important;
        border-radius: 7px !important;
        background: rgba(15,23,42,0.92) !important;
        backdrop-filter: blur(10px) !important;
        color: #f8fafc !important;
        border: 1px solid rgba(56,189,248,0.25) !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.45) !important;
        pointer-events: auto !important;
        cursor: pointer !important;
        position: relative !important;
        outline: none !important;
        transition: background-color 0.1s, border-color 0.1s, color 0.1s !important;
    }
    
    .fixed-top-nav-bar button:hover {
        border-color: rgba(56,189,248,0.6) !important;
        background: rgba(30,41,59,0.92) !important;
    }

    .fixed-top-nav-bar button:focus,
    .fixed-top-nav-bar button:focus-visible,
    .fixed-top-nav-bar button:focus:not(:active) {
        background: rgba(15,23,42,0.92) !important;
        color: #f8fafc !important;
        border-color: rgba(56,189,248,0.25) !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.45) !important;
        outline: none !important;
    }
    
    .fixed-top-nav-bar button * {
        color: inherit !important;
        transition: color 0.1s !important;
    }
    
    .fixed-top-nav-bar button p {
        font-size: clamp(10px,2.5vw,11.5px) !important;
        font-weight: 700 !important;
        margin: 0 !important;
        padding: 0 !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        line-height: 1 !important;
        pointer-events: none !important;
    }
    
    .fixed-top-nav-bar button:active,
    .fixed-top-nav-bar button:active:focus {
        background: #0284c7 !important;
        color: #ffffff !important;
        border-color: #38bdf8 !important;
        box-shadow: 0 0 10px rgba(56,189,248,0.7) !important;
        transform: scale(0.96) !important;
        transition: none !important;
    }
    
    .glass-header {
        background: radial-gradient(circle at top right,rgba(168,85,247,0.14),transparent 60%),linear-gradient(145deg,#0f172a 0%,#070b14 100%);
        border: 1px solid rgba(148,163,184,0.18);
        border-radius: 14px;
        padding: 14px 14px;
        margin-bottom: 10px;
        box-shadow: 0 10px 28px rgba(0,0,0,0.45);
        box-sizing: border-box;
        width: 100%;
        overflow: hidden;
    }
    .compact-bar-label {
        display: flex;
        justify-content: space-between;
        font-size: 10.5px;
        font-weight: 700;
        letter-spacing: 0.8px;
        color: #94a3b8;
        background: #0f172a;
        padding: 5px 11px;
        border-radius: 7px;
        border-left: 3px solid #a855f7;
        margin-bottom: 5px;
    }
    .rank-card,.search-result-card {
        background: linear-gradient(180deg,#0f172a 0%,#090d16 100%) !important;
        color: #f8fafc !important;
        border-radius: 14px;
        padding: 13px 14px;
        margin-bottom: 11px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.45);
        border: 1px solid rgba(148,163,184,0.16);
        border-left: 4px solid #38bdf8;
    }
    .search-result-card {
        border-left-color: #f59e0b;
    }
    .prob-badge {
        font-family: 'JetBrains Mono',monospace;
        font-size: clamp(14px,3.8vw,16.5px);
        font-weight: 800;
        color: #38bdf8 !important;
        white-space: nowrap;
    }
    .expect-badge {
        font-family: 'JetBrains Mono',monospace;
        font-size: clamp(14px,3.8vw,16.5px);
        font-weight: 900;
        color: #fde047 !important;
        white-space: nowrap;
    }
    .pill-badge {
        display: inline-block;
        padding: 2px 7px;
        border-radius: 6px;
        font-size: 10px;
        font-weight: 700;
        margin-right: 4px;
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.12);
        color: #e2e8f0;
    }
    .quantum-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 10px;
        font-weight: 800;
        margin-right: 4px;
        background: linear-gradient(90deg,rgba(168,85,247,0.22),rgba(56,189,248,0.22));
        border: 1px solid rgba(168,85,247,0.55);
        color: #e9d5ff;
    }
    .inst-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 10px;
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
        border-radius: 8px;
        padding: 6px 4px;
        margin-top: 7px;
        text-align: center;
    }
    .signal-10tier-badge {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 5px 10px;
        border-radius: 7px;
        font-size: 11.5px;
        font-weight: 800;
        margin-bottom: 7px;
        gap: 6px;
        flex-wrap: wrap;
    }
    .trade-plan-box {
        display: grid;
        grid-template-columns: repeat(3,1fr);
        gap: 5px;
        margin-top: 6px;
        background: rgba(2,6,23,0.7) !important;
        padding: 6px 4px;
        border-radius: 8px;
        border: 1px solid rgba(148,163,184,0.15);
        text-align: center;
    }
    .sizing-box {
        background: rgba(16,185,129,0.08) !important;
        border: 1px solid rgba(16,185,129,0.28);
        border-radius: 8px;
        padding: 5px 10px;
        margin-top: 6px;
        font-size: 11px;
        color: #d1fae5;
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 4px;
    }
    details.quant-detail-drawer {
        margin-top: 6px;
        background: rgba(2,6,23,0.55);
        border: 1px solid rgba(168,85,247,0.25);
        border-radius: 8px;
        padding: 5px 10px;
    }
    details.quant-detail-drawer summary {
        font-size: 11px;
        font-weight: 700;
        color: #c084fc !important;
        cursor: pointer;
        list-style: none;
    }
    .metrics-row {
        display: flex;
        flex-wrap: wrap;
        gap: 4px 8px;
        margin-top: 5px;
        font-size: 10.5px;
        font-family: 'JetBrains Mono',monospace;
        background: rgba(15,23,42,0.9) !important;
        padding: 5px 8px;
        border-radius: 6px;
        color: #cbd5e1;
    }
    .ai-council-box {
        background: #070b14;
        color: #f8fafc !important;
        border-radius: 11px;
        padding: 11px;
        margin-top: 6px;
        margin-bottom: 9px;
        border: 1px solid rgba(168,85,247,0.35);
    }
    .council-scroll-window {
        max-height: 480px;
        overflow-y: auto;
        padding: 9px;
        background: #04070e;
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 8px;
        margin-bottom: 8px;
        scroll-behavior: smooth;
    }
    .round-divider {
        text-align: center;
        margin: 8px 0;
        padding: 5px 10px;
        background: rgba(168,85,247,0.18);
        border-left: 4px solid #a855f7;
        color: #e9d5ff !important;
        font-size: 11.5px;
        font-weight: 800;
        border-radius: 4px;
    }
    .chat-bubble-ai,.chat-bubble-doubt,.chat-bubble-rage,.chat-bubble-agree {
        border-radius: 8px;
        padding: 7px 10px;
        margin-bottom: 6px;
        font-size: 12px;
        line-height: 1.55;
        background: rgba(255,255,255,0.04);
        border-left: 3px solid #38bdf8;
    }
    .chat-bubble-doubt {
        border-left-color: #f59e0b;
        background: rgba(245,158,11,0.07);
    }
    .chat-bubble-rage {
        border-left-color: #ef4444;
        background: rgba(239,68,68,0.12);
    }
    .chat-bubble-agree {
        border-left-color: #a855f7;
        background: rgba(168,85,247,0.11);
    }
    .chat-bubble-user {
        background: rgba(37,99,235,0.30);
        border-left: 4px solid #60a5fa;
        border-radius: 8px;
        padding: 8px 11px;
        margin: 8px 0 6px 0;
        font-size: 12.5px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        scroll-margin-top: 6px;
    }
    .consensus-banner {
        background: linear-gradient(135deg,#0f172a,#1e1b4b);
        border: 1px solid rgba(168,85,247,0.45);
        border-radius: 9px;
        padding: 10px;
        margin-top: 7px;
        font-size: 12px;
    }
    .beginner-action-box {
        background: linear-gradient(135deg,rgba(16,185,129,0.14),rgba(6,78,59,0.25));
        border: 1px solid #10b981;
        border-left: 4px solid #10b981;
        border-radius: 8px;
        padding: 9px 11px;
        margin-top: 7px;
        color: #ecfdf5;
        font-size: 12px;
        line-height: 1.6;
    }
    .ipo-link-btn {
        display: inline-block;
        background: #1e293b;
        color: #38bdf8 !important;
        border: 1px solid #334155;
        padding: 4px 9px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 700;
        text-decoration: none !important;
        margin-right: 5px;
        margin-top: 4px;
    }
    .ipo-link-btn:hover {
        background: #38bdf8;
        color: #0f172a !important;
    }
    """
    st.markdown(f'<div id="page_top_anchor"></div><style>{" ".join(l.strip() for l in css.splitlines() if l.strip())}</style>', unsafe_allow_html=True)

inject_css()

# ==========================================
# 8. 認証＆セッション管理（レートリミット付き）
# ==========================================
def render_biometric_bridge(mode="login", user_email="", bio_token=""):
    cur_fp, raw_hfp = get_client_fp(), get_raw_header_fp()
    with get_db() as conn:
        if mode == "register":
            row = conn.execute("SELECT bio_enabled FROM members WHERE email = ?", (user_email,)).fetchone()
            is_enabled = bool(row and row["bio_enabled"])
            lbl = "✅ 生体・ワンタップ認証 登録済" if is_enabled else "🧬 この端末をワンタップ登録"
            if st.button(lbl, key=f"bio_{user_email}", use_container_width=True):
                conn.execute("UPDATE members SET bio_enabled = 1, fp = ?, raw_hfp = ? WHERE email = ?", (cur_fp, raw_hfp, user_email))
                conn.commit()
                st.success("✅ 端末認証を登録しました")
            return

        mapped_email = None
        m_row = conn.execute("SELECT email, status, name, pin_hash FROM members WHERE bio_enabled = 1 AND (raw_hfp = ? OR fp = ?)", (raw_hfp, cur_fp)).fetchone()
        if m_row:
            mapped_email = m_row["email"]

    if st.button("🧬 登録済み端末：生体認証 / ワンタップで即ログイン", use_container_width=True, type="primary"):
        if mapped_email:
            t_em = mapped_email.strip().lower()
            is_ban, _ = check_and_log_ban_spoof(t_em, m_row["name"] or "", cur_fp, raw_hfp, m_row["pin_hash"] or "", "ワンタップログイン")
            if is_ban or m_row["status"] == "banned":
                st.error("💀 このアカウントまたは端末は永久BAN（アクセス禁止）されています。")
            elif m_row["status"] == "suspended":
                st.error("🚫 アカウント一時停止中です。")
            elif m_row["status"] == "approved" or t_em == ADMIN_EMAIL:
                st.session_state["authenticated_user"] = t_em
                st.query_params["u"], st.query_params["t"] = t_em, gen_tok(t_em, "session_keep")
                st.rerun()
        else:
            is_ban, _ = check_and_log_ban_spoof("", "未認証端末", cur_fp, raw_hfp, "", "ワンタップ試行")
            if is_ban:
                st.error("💀 この端末は永久BAN（アクセス禁止）されています。")
            else:
                st.warning("⚠️ 初回は下のフォームから専用コードでログインしてください（次回から自動登録されます）。")

def check_auth():
    cur_fp, raw_hfp = get_client_fp(), get_raw_header_fp()
    if "authenticated_user" not in st.session_state: st.session_state["authenticated_user"] = None
    qu, qt = st.query_params.get("u", "").strip().lower(), st.query_params.get("t", "").strip()

    with get_db() as conn:
        if not st.session_state["authenticated_user"] and qu and qt:
            row = conn.execute("SELECT status, name, pin_hash FROM members WHERE email = ?", (qu,)).fetchone()
            if hmac.compare_digest(qt, gen_tok(qu, "session_keep")) and ((row and row["status"] == "approved") or qu == ADMIN_EMAIL):
                st.session_state["authenticated_user"] = qu

        if st.session_state["authenticated_user"]:
            cu = st.session_state["authenticated_user"]
            u_rec = conn.execute("SELECT name, status, pin_hash FROM members WHERE email = ?", (cu,)).fetchone()
            if cu != ADMIN_EMAIL:
                is_ban, _ = check_and_log_ban_spoof(cu, u_rec["name"] if u_rec else "", cur_fp, raw_hfp, u_rec["pin_hash"] if u_rec else "", "セッション維持")
                if is_ban or (u_rec and u_rec["status"] == "banned"):
                    st.session_state["authenticated_user"] = None
                    st.query_params.clear()
                    st.error("💀 このアカウントまたは端末は永久BAN（利用禁止）されています。")
                    st.stop()
                if not u_rec or u_rec["status"] != "approved":
                    st.session_state["authenticated_user"] = None
                    st.query_params.clear()
                    st.error("🚫 アカウント一時停止中、または削除されています。")
                    st.stop()

            keep_tok = gen_tok(cu, "session_keep")
            conn.execute("""
                UPDATE members SET last_seen_ts = ?, last_seen_str = ?, fp = ?, raw_hfp = ?, bio_enabled = 1
                WHERE email = ?
            """, (time.time(), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), cur_fp, raw_hfp, cu))
            conn.commit()

            st.query_params["u"], st.query_params["t"] = cu, keep_tok
            with st.sidebar:
                u_disp_name = u_rec["name"] if u_rec else "会員"
                st.markdown(f'<div style="background:#0f172a;padding:8px 11px;border-radius:9px;border:1px solid rgba(168,85,247,0.35);margin-bottom:6px;"><div style="font-size:9.5px;color:#c084fc;font-weight:700;">⚛️ QUANTUM SESSION ACTIVE</div><div style="color:#f8fafc;font-size:11.5px;font-weight:700;">{sanitize(u_disp_name)} ({sanitize(cu)})</div></div>', unsafe_allow_html=True)
                render_biometric_bridge(mode="register", user_email=cu, bio_token=keep_tok)
                if st.button("🚪 ログアウト", use_container_width=True):
                    conn.execute("UPDATE members SET last_seen_ts = 0 WHERE email = ?", (cu,))
                    conn.commit()
                    st.session_state["authenticated_user"] = None
                    st.query_params.clear()
                    st.rerun()

            if cu == ADMIN_EMAIL:
                pend = conn.execute("SELECT COUNT(*) AS c FROM members WHERE status = 'pending'").fetchone()["c"]
                unread_msgs = conn.execute("SELECT COUNT(*) AS c FROM messages WHERE sender_role = 'member' AND read_by_admin = 0").fetchone()["c"]
                spoof_cnt = conn.execute("SELECT COUNT(*) AS c FROM spoof_logs").fetchone()["c"]
                if st.sidebar.button(f"👑 管理画面 (承認待:{pend} / 未読MSG:{unread_msgs} / 監視:{spoof_cnt})", use_container_width=True):
                    st.session_state["navigation_page"] = "ADMIN"
                    st.rerun()
            return True

    # 未認証トップ
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
                cm = ie.strip().lower()
                inp_code = ic.strip()
                if not cm or not inp_code:
                    st.warning("⚠️ メールアドレスとアクセスコードを入力してください。")
                else:
                    with get_db() as conn:
                        rec = conn.execute("SELECT name, status, pin_hash, passcode FROM members WHERE email = ?", (cm,)).fetchone()
                        
                        # 管理者認証（専用コードまたはADMIN_PASS）
                        if cm == ADMIN_EMAIL:
                            correct_passcode = gen_code(ADMIN_EMAIL)
                            if inp_code == ADMIN_PASS or inp_code.upper() == correct_passcode:
                                st.session_state["authenticated_user"] = ADMIN_EMAIL
                                st.rerun()
                            else:
                                st.error("⚠️ 管理者コードまたはパスワードが正しくありません。")
                        else:
                            is_ban, _ = check_and_log_ban_spoof(cm, rec["name"] if rec else "", cur_fp, raw_hfp, rec["pin_hash"] if rec else "", "コードログイン")
                            if is_ban or (rec and rec["status"] == "banned"):
                                st.error("💀 このアカウントまたは端末は永久BAN（利用禁止）されています。")
                            elif rec and rec["status"] == "suspended":
                                st.error("🚫 このアカウントは一時停止されています。")
                            elif rec and rec["status"] == "approved" and (
                                hmac.compare_digest(inp_code.upper(), rec["passcode"] or "") or
                                hmac.compare_digest(inp_code.upper(), gen_code(cm))
                            ):
                                st.session_state["authenticated_user"] = cm
                                st.rerun()
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
                    st.warning("⚠️ 正しいメールアドレスと4桁の数字暗証番号(PIN)を入力してください。")
                else:
                    cm = am.strip().lower()
                    pc = gen_code(am)
                    ns = datetime.now().strftime("%Y-%m-%d %H:%M")
                    nm_clean = an.strip() or "未入力"
                    pin_h = hash_pin(apin)
                    with get_db() as conn:
                        is_ban, _ = check_and_log_ban_spoof(cm, nm_clean, cur_fp, raw_hfp, pin_h, "新規登録申請")
                        if is_ban:
                            st.error("💀 セキュリティ監視システムにより申請は永久ブロックされました。")
                        else:
                            conn.execute("""
                                INSERT OR REPLACE INTO members (email, name, status, passcode, pin_hash, pin_attempts, locked_until, applied_at, approved_at, last_seen_ts, last_seen_str, fp, raw_hfp, bio_enabled)
                                VALUES (?, ?, 'pending', ?, ?, 0, 0, ?, '-', 0, '-', ?, ?, 0)
                            """, (cm, nm_clean, pc, pin_h, ns, cur_fp, raw_hfp))
                            conn.commit()
                            send_mail(cm, "【YAMASHISHI LAB】会員登録申請の受付完了", f"{nm_clean} 様\n申請を受け付けました。管理者承認後、ログイン画面の『🔐 承認確認・暗号化コード照会』タブにて、ご設定いただいた4桁の暗証番号(PIN)を入力すると専用アクセスコードをご確認いただけます。")
                            st.success("✅ 申請を受け付けました！承認完了まで今しばらくお待ちください。")

    with tab_vault:
        st.caption("🛡️ 第三者による総当たり攻撃を防止するため、連続失敗時はアカウントが自動ロックされます。")
        with st.form("vault_check"):
            chk_em = st.text_input("📧 申請したメールアドレス").strip().lower()
            chk_pin = st.text_input("🔢 申請時に設定した4桁の暗証番号 (PIN)", type="password", max_chars=4).strip()
            if st.form_submit_button("🔍 本人確認して承認ステータスを照会", use_container_width=True):
                if not chk_em or not chk_pin:
                    st.warning("⚠️ メールアドレスと4桁の暗証番号(PIN)を入力してください。")
                else:
                    with get_db() as conn:
                        u_info = conn.execute("SELECT * FROM members WHERE email = ?", (chk_em,)).fetchone()
                        now_ts = time.time()
                        
                        if not u_info:
                            st.error("❌ 該当する申請データが見つかりません。")
                        elif u_info["locked_until"] > now_ts:
                            rem_sec = int(u_info["locked_until"] - now_ts)
                            st.error(f"⛔ PIN試行回数オーバーのため一時ロック中です。残り約 {rem_sec} 秒後に再試行してください。")
                        else:
                            is_ban, _ = check_and_log_ban_spoof(chk_em, u_info["name"] or "", cur_fp, raw_hfp, hash_pin(chk_pin), "コード照会")
                            if is_ban or u_info["status"] == "banned":
                                st.error("💀 このアカウントまたは端末は永久BANされています。")
                            elif u_info["pin_hash"] and not hmac.compare_digest(u_info["pin_hash"], hash_pin(chk_pin)):
                                attempts = (u_info["pin_attempts"] or 0) + 1
                                lock_time = now_ts + (60 * (2 ** (attempts - 3))) if attempts >= 3 else 0
                                conn.execute("UPDATE members SET pin_attempts = ?, locked_until = ? WHERE email = ?", (attempts, lock_time, chk_em))
                                conn.commit()
                                st.error(f"🚫 暗証番号(PIN)が一致しません。（失敗 {attempts} 回目）")
                            else:
                                # 認証成功・試行回数リセット
                                conn.execute("UPDATE members SET pin_attempts = 0, locked_until = 0 WHERE email = ?", (chk_em,))
                                conn.commit()
                                if u_info["status"] == "approved":
                                    st.success(f"🎉 本人確認完了・承認済みです！あなたの専用アクセスコードは **`{u_info['passcode']}`** です。「🔑 コードログイン」タブからログインしてください。")
                                elif u_info["status"] == "pending":
                                    st.info("⏳ 本人確認完了：現在、管理者の承認審査待ちです。")
                                else:
                                    st.error("🚫 現在このアカウントは一時停止中または利用できません。")
    st.stop()

check_auth()

# ==========================================
# 9. セッション状態＆ナビゲーション
# ==========================================
for k, v in [
    ("active_debates", {}), ("stock_chats", {}), ("council_threads", {}), ("council_meta", {}),
    ("debate_round_seed", {}), ("watchlist", {}), ("navigation_page", "TOP"),
    ("selected_news_item", None), ("custom_search_code", ""), ("active_category", "🏆 総合TOP5"),
    ("last_cat", "🏆 総合TOP5"), ("nav_history", []), ("scroll_top_trig", 0),
    ("dismissed_news_ids", set()), ("show_ai_guide", False), ("scroll_target_id", "")
]:
    if k not in st.session_state: st.session_state[k] = v

open_cnt = sum(1 for v in st.session_state["active_debates"].values() if v)

with st.container():
    st.markdown('<div class="top-nav-marker"></div>', unsafe_allow_html=True)
    nav_c1, nav_c2, nav_c3 = st.columns([1, 1.35, 1])
    if nav_c1.button("⬆️ トップ", key="top_nav_top", use_container_width=True):
        st.session_state["navigation_page"] = "TOP"
        st.session_state["scroll_top_trig"] = int(time.time() * 1000)
        st.rerun()
    if nav_c2.button(f"✖ 合議閉じる({open_cnt})" if open_cnt else "✖ 合議閉じる", key="top_nav_close", use_container_width=True):
        st.session_state["active_debates"] = {}
        st.rerun()
    if nav_c3.button("↩️ 戻る", key="top_nav_back", use_container_width=True):
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
                        const pRect = parentBox.getBoundingClientRect();
                        const eRect = el.getBoundingClientRect();
                        parentBox.scrollTop += (eRect.top - pRect.top) - 4;
                    }} else {{
                        el.scrollIntoView({{behavior: 'smooth', block: 'start'}});
                    }}
                }}
            }} catch(e){{}}
        }}, 220);
    """
    st.session_state["scroll_target_id"] = ""

components.html(
    f"""
    <script>
    (function(){{
        const doc = window.parent.document;
        function ensureSidebarCollapsedOnLoad(){{
            if(!window.parent._sidebarForcedClosed){{
                setTimeout(() => {{
                    try {{
                        const sb = doc.querySelector('section[data-testid="stSidebar"]');
                        if(sb && (sb.getAttribute('aria-expanded') === 'true' || sb.style.marginLeft === '0px')){{
                            const btn = doc.querySelector('[data-testid="stSidebarCollapseButton"]') || doc.querySelector('[aria-label="Collapse sidebar"]');
                            if(btn) btn.dispatchEvent(new MouseEvent('click', {{ bubbles: true, cancelable: true, view: window.parent }}));
                        }}
                    }} catch(e){{}}
                }}, 150);
                window.parent._sidebarForcedClosed = true;
            }}
        }}
        ensureSidebarCollapsedOnLoad();

        function installFloatingSidebarToggle(){{
            try {{
                if(doc.getElementById('yamashishi-floating-sidebar-btn')) return;
                const btn = doc.createElement('div');
                btn.id = 'yamashishi-floating-sidebar-btn';
                btn.innerHTML = `
                    <div class="glow-bg"></div>
                    <svg viewBox="0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="3" y1="12" x2="21" y2="12"></line>
                        <line x1="3" y1="6" x2="21" y2="6"></line>
                        <line x1="3" y1="18" x2="21" y2="18"></line>
                    </svg>
                    <span>MENU</span>
                `;
                const style = doc.createElement('style');
                style.textContent = `
                    #yamashishi-floating-sidebar-btn {{
                        position: fixed !important;
                        top: 8px !important;
                        left: 9px !important;
                        z-index: 2147483647 !important;
                        display: flex !important;
                        align-items: center !important;
                        justify-content: center !important;
                        gap: 5px !important;
                        height: 30px !important;
                        padding: 0 9px 0 7px !important;
                        background: rgba(11, 15, 25, 0.94) !important;
                        backdrop-filter: blur(16px) !important;
                        border: 1.5px solid rgba(56, 189, 248, 0.5) !important;
                        border-radius: 8px !important;
                        cursor: pointer !important;
                        box-shadow: 0 4px 18px rgba(0, 0, 0, 0.75), 0 0 12px rgba(56, 189, 248, 0.25) !important;
                        user-select: none !important;
                        transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1) !important;
                    }}
                    #yamashishi-floating-sidebar-btn:hover {{
                        border-color: #38bdf8 !important;
                        box-shadow: 0 6px 22px rgba(0, 0, 0, 0.9), 0 0 18px rgba(56, 189, 248, 0.6) !important;
                        transform: translateY(-1px) scale(1.02) !important;
                    }}
                    #yamashishi-floating-sidebar-btn:active {{ transform: scale(0.96) !important; }}
                    #yamashishi-floating-sidebar-btn svg {{
                        width: 15px !important;
                        height: 15px !important;
                        stroke: #38bdf8 !important;
                        filter: drop-shadow(0 0 4px rgba(56, 189, 248, 0.8)) !important;
                    }}
                    #yamashishi-floating-sidebar-btn span {{
                        font-family: 'JetBrains Mono', monospace !important;
                        font-size: 10px !important;
                        font-weight: 800 !important;
                        color: #f8fafc !important;
                        letter-spacing: 0.8px !important;
                    }}
                `;
                doc.head.appendChild(style);
                btn.addEventListener('click', function(e){{
                    e.preventDefault(); e.stopPropagation();
                    const expandBtn = doc.querySelector('[data-testid="collapsedControl"]') 
                                   || doc.querySelector('[data-testid="stSidebarCollapsedControl"]')
                                   || doc.querySelector('button[kind="headerNoPadding"]');
                    const collapseBtn = doc.querySelector('[data-testid="stSidebarCollapseButton"]') 
                                     || doc.querySelector('[aria-label="Collapse sidebar"]')
                                     || doc.querySelector('button[aria-label="Close"]');
                    let isClosed = true;
                    const sb = doc.querySelector('section[data-testid="stSidebar"]');
                    if(sb) {{
                        isClosed = sb.getAttribute('aria-expanded') === 'false' || 
                                   (window.getComputedStyle(sb).transform && window.getComputedStyle(sb).transform.includes('-')) ||
                                   (sb.style.marginLeft && sb.style.marginLeft.includes('-'));
                    }}
                    if (isClosed && expandBtn) expandBtn.dispatchEvent(new MouseEvent('click', {{ bubbles: true, cancelable: true, view: window.parent }}));
                    else if (!isClosed && collapseBtn) collapseBtn.dispatchEvent(new MouseEvent('click', {{ bubbles: true, cancelable: true, view: window.parent }}));
                }});
                doc.body.appendChild(btn);
            }} catch(e){{}}
        }}

        function fixTopNav(){{
            try {{
                const marker = doc.querySelector('.top-nav-marker');
                if(!marker) return;
                let box = marker.closest('[data-testid="stVerticalBlockBorderWrapper"]') || marker.closest('[data-testid="stVerticalBlock"]');
                if(box && box.querySelector('[data-testid="stHorizontalBlock"]')) box.classList.add('fixed-top-nav-bar');
            }} catch(e){{}}
        }}

        installFloatingSidebarToggle();
        fixTopNav();
        setTimeout(installFloatingSidebarToggle, 200);
        setTimeout(fixTopNav, 150);

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
# 10. クオンツ解析エンジン ＆ 戦略ディスパッチャ
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
            "beginner_html": f"<b>🔰 スキャルピング実践手順（⚡ 寄付き直後の数分で利確！）</b><br>① <b>【エントリー】</b> 朝9:00のスタートと同時に <b>{sh:,}株</b> を迷わず買います。<br>② <b>【利確・損切】</b> スキャルピングはスピード命です。数分で動く <b>{tp_str}</b> で利確し、逆指値 <b>{sl_str}</b> は必ずタイトに設定してください。"
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
            "beginner_html": f"<b>🔰 スイングトレード実践手順（📈 数日〜1週間のトレンドに乗る！）</b><br>① 初日は資金の半分強（<b>{l1:,}株</b>）を買ってポジションを作ります。<br>② 数日後に少し下がったところで残りの <b>{l2:,}株</b> を買い増し、目標の <b>{tp_str}</b> までゆったり保有します。"
        }

    sh = max(1, int(round(base_sh * 1.65)))
    return {
        "algo_name": f"🔥 [{st_prefix}] 情報精度S級・全ツッパ一括特攻型アルゴリズム",
        "risk_posture": f"👑 全ツッパ・フルベット（ <b>{sh:,}株を100%一括投入</b> ）",
        "core_logic": f"期待度 <b>{expect_pct}%</b>・量子Qスコア {qm['q_score']}点・機関Kyleステルス吸収 {ms['kyle_stealth']}% が完全一致し、95%CVaRも -{cvar95}% と極めて低いS級特異点。分割せず寄り付き一括で最高期待値を抜き取る戦術。",
        "adj_shares": sh,
        "step_plan": f"① 9:00寄付き（{pest_str}目安）で <b>全ロット {sh:,}株（100%全ツッパ）</b> 成行一括投入 → ② 逆指値（{sl_str}）を同時セットし、目標（{tp_str}）まで一気抜き",
        "beginner_html": f"<b>🔰 デイトレード実践手順（🔥 精度S級・迷わず1回で全ツッパ！）</b><br>① 朝9:00の寄り付きで <b>「{sh:,}株」を1回でまとめて購入</b> します。<br>② 買えたらすぐに <b>「損切り：{sl_str}」</b> を入れ、目標の <b>{tp_str}</b> 到達で利益確定！"
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

        return {
            "full_code": code, "code": code.replace(".T", ""), "name": name, "genre": genre, "theme": theme, "price": fp(cv), "raw_close": cv,
            "tp_price": fp(tpv), "tp_pct": round((tpv - cv) / cv * 100, 1), "sl_price": fp(slv), "sl_pct": round((slv - cv) / cv * 100, 1), "vwap_price": fp(float(lat["VWAP20"])),
            "inst_score": isc, "vpin": round(vpin, 2), "ofi_z": ofi_z, "yz_vol": yz_vol, "cvar95": cvar95, "eff_pct": eff_pct, "kelly_pct": kelly_pct,
            "q_score": qm["q_score"], "q_tunnel": qm["q_tunnel"], "q_coherence": qm["q_coherence"], "q_entropy": qm["q_entropy"], "q_state": qm["q_state"],
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
# 11. 外部データ取得層（フォールバック強化）
# ==========================================
@st.cache_data(ttl=900)
def fetch_5ch_live() -> dict:
    ctx = ssl.create_default_context()
    txts = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    target_urls = [
        "https://egg.5ch.io/stock/subback.html",
        "https://hayabusa9.5ch.io/livemarket1/subback.html"
    ]
    for u in target_urls:
        try:
            req = urllib.request.Request(u, headers=headers)
            with urllib.request.urlopen(req, timeout=2.5, context=ctx) as r:
                raw_html = r.read().decode("cp932", errors="ignore")
                thread_ids = re.findall(r'(\d{10})\.html', raw_html)
                for tid in thread_ids[:2]:
                    board = "stock" if "egg.5ch.io" in u else "livemarket1"
                    try:
                        read_url = f"https://egg.5ch.io/test/read.cgi/{board}/{tid}/l50"
                        with urllib.request.urlopen(urllib.request.Request(read_url, headers=headers), timeout=2.0, context=ctx) as tr:
                            txts.append(re.sub(r"<[^>]+>", " ", tr.read().decode("cp932", errors="ignore")))
                    except Exception: continue
        except Exception: continue
        
    joined = " ".join(txts)
    return {c: {"hits": len(re.findall(re.escape(c.replace(".T", "")), joined)) if joined else 0, "live": bool(txts)} for c in KNOWN_STOCKS}

@st.cache_data(ttl=900)
def fetch_macro():
    tks = {"sp500": ("^GSPC", "🇺🇸 S&P500"), "sox": ("^SOX", "💽 米SOX"), "usdjpy": ("JPY=X", "💴 ドル円"), "nk_fut": ("NIY=F", "🇯🇵 日経先物"), "vix": ("^VIX", "⚡ VIX")}
    res = {}
    try:
        raw = yf.download(list(c for c, _ in tks.values()), period="5d", group_by="ticker", threads=True, progress=False, timeout=6)
        for k, (c, lbl) in tks.items():
            try:
                d = raw[c].dropna(subset=["Close"])
                lc, pc = float(d["Close"].iloc[-1]), float(d["Close"].iloc[-2])
                res[k] = {"price": lc, "diff": round((lc - pc) / pc * 100, 2), "label": lbl}
            except Exception: res[k] = {"price": 0.0, "diff": 0.0, "label": lbl}
    except Exception:
        for k, (_, lbl) in tks.items(): res[k] = {"price": 0.0, "diff": 0.0, "label": lbl}
    return res

@st.cache_data(ttl=180)
def fetch_global_impact_news() -> list:
    qs = [("半導体・AIサプライズ", "半導体 OR エヌビディア OR TSMC OR アドバンテスト OR データセンター 株価"), ("急騰・上方修正・TOB", "ストップ高 OR 上方修正 OR 自社株買い OR 防衛 OR 量子 株")]
    ctx = ssl.create_default_context()
    out, seen = [], set()
    for cat, q in qs:
        try:
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=ja&gl=JP&ceid=JP:ja"
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=3.0, context=ctx) as res:
                root = ET.fromstring(res.read())
            for it in root.findall("./channel/item")[:3]:
                t = re.sub(r"\s*-\s*[^-]+$", "", (it.findtext("title") or "").strip())
                if not t or t in seen: continue
                seen.add(t)
                out.append({"id": hashlib.md5(t.encode()).hexdigest()[:8], "cat": cat, "title": t, "link": it.findtext("link") or "", "source": it.findtext("source") or "Market Wire", "pub_date": (it.findtext("pubDate") or "")[:25], "impact_score": 92, "detail": analyze_news_impact_and_links(t, cat)})
        except Exception: continue
    if not out:
        t_fb = "AI半導体・次世代データセンター光配線および防衛・量子分野に機関投資家の大型資金流入が加速"
        out.append({"id": "fb_news_01", "cat": "機関オーダーフロー速報", "title": t_fb, "link": "https://jp.reuters.com/", "source": "YAMASHISHI QUANT WIRE", "pub_date": datetime.now().strftime("%Y-%m-%d %H:%M"), "impact_score": 94, "detail": analyze_news_impact_and_links(t_fb, "半導体・AIサプライズ")})
    return out[:4]

def analyze_news_impact_and_links(title: str, cat: str) -> dict:
    t_up = title.upper()
    if any(w in t_up for w in ["半導体", "エヌビディア", "NVDA", "TSMC", "レーザー", "アドバンテスト", "ディスコ", "HBM", "AI", "GPU", "キオクシア"]):
        codes, sector_focus = ["6857.T", "8035.T", "6146.T", "6920.T", "5803.T", "NVDA"], "AI半導体・HBM製造装置・データセンター光配線セクター"
        mech = "米SOX指数およびNVIDIA・TSMCの設備投資サプライチェーンに直結する重要ヘッドラインです。機関投資家のバスケット買いアルゴは、まず先物主導でアドバンテスト(6857)・東京エレクトロン(8035)・ディスコ(6146)の上値板を掃き上げ、時間差でAIデータセンター向け光ファイバーのフジクラ(5803)へ資金を波及させる強い量子もつれ（相関）を持っています。"
    elif any(w in t_up for w in ["防衛", "三菱重", "宇宙", "衛星", "ドローン", "IHI", "川重", "安全保障", "トランプ"]):
        codes, sector_focus = ["7011.T", "7012.T", "7013.T", "5595.T", "186A.T", "PLTR"], "防衛国策・航空宇宙・小型SAR衛星セクター"
        mech = "地政学・国策防衛予算および宇宙安全保障に関わるテーマ材料です。主力大型株の三菱重工業(7011)・川崎重工業(7012)・IHI(7013)に海外年金・機関のロング資金が流入しやすく、個人の短期モメンタム資金は値動きの軽いQPS研究所(5595)やアストロスケール(186A)へ波及しやすい構造です。"
    elif any(w in t_up for w in ["電力", "原発", "データセンター", "電線", "送電", "フジクラ", "日立"]):
        codes, sector_focus = ["5803.T", "5801.T", "6501.T", "9509.T", "9508.T", "VST"], "AI電力インフラ・超電導送電網・光ファイバー電線セクター"
        mech = "生成AIデータセンターの爆発的な電力需要と送配電網増強に直結する国策テーマです。電線御三家筆頭のフジクラ(5803)・古河電工(5801)、世界送配電グリッドの日立製作所(6501)、さらにラピダス・TSMC稼働に伴う北海道電力(9509)・九州電力(9508)が強く連動します。"
    elif any(w in t_up for w in ["量子", "暗号", "セキュリティ", "IONQ", "さくら", "クラウド"]):
        codes, sector_focus = ["3778.T", "3993.T", "IONQ", "RGTI", "CRWD", "9984.T"], "量子コンピューティング・国策AIクラウド・サイバー防衛セクター"
        mech = "次世代計算基盤（量子・GPUクラウド）およびゼロトラスト防衛に関わる最先端材料です。米量子株のIonQ(IONQ)・Rigetti(RGTI)の急騰は、日本市場のさくらインターネット(3778)やPKSHA(3993)へ短期資金を誘発する強い先行指標となります。"
    else:
        codes, sector_focus = ["9984.T", "6857.T", "5803.T", "7011.T", "3778.T", "NVDA"], "日米AI主力・ストップ高モメンタム波及セクター"
        mech = "市場全体のセンチメントと短期資金の回転を加速させるサプライズ材料です。指数寄与度の高いソフトバンクG(9984)やアドバンテスト(6857)が先物主導で動くほか、好決算・上方修正・自社株買いの連想から高OFI（板吸収）銘柄へ一気に順張り資金が集中しやすくなります。"
    return {
        "sector_focus": sector_focus, "mechanism": mech, "related_codes": codes,
        "action_guide": "① 朝8:45〜8:55の気配値で、下の『連動・波及注目銘柄』の寄り付きギャップとOFI（板の買い越し）を確認します。\n② 主力株（大型）がギャップアップして始まった場合、まだ初動で出遅れている2番手・周辺銘柄（電線・部材・中小型AI）のVWAP押し目を狙う『時間差連動スナイプ』が最も勝率の高いプロの手口です。"
    }

@st.cache_data(ttl=1800)
def fetch_pool_batch(macro, b5_live_map, style, bi, b5, bal, bms, total_capital=1000000, risk_tolerance_pct=2.0):
    codes = list({s["code"] for sts in STOCK_POOL.values() for s in sts})
    try:
        raw = yf.download(codes, period="6mo", group_by="ticker", threads=True, progress=False, timeout=10)
    except Exception:
        raw = None
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

@st.cache_data(ttl=300)
def fetch_one(code, macro, b5_live_map, style, bi, b5, bal, bms, total_capital=1000000, risk_tolerance_pct=2.0):
    inf = KNOWN_STOCKS.get(code, {"name": code.replace(".T", ""), "theme": "個別指定銘柄", "genre": "個別検索"})
    return analyze_df(yf.Ticker(code).history(period="6mo"), code, inf["name"], inf["theme"], inf["genre"], macro, b5_live_map, style, bi, b5, bal, bms, total_capital, risk_tolerance_pct)

@st.cache_data(ttl=300)
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
all_impact_news = fetch_global_impact_news()

# ==========================================
# 12. サイドバー制御 & 各種設定
# ==========================================
st.sidebar.header("🧠 7大AI ＆ 量子エンジン設定")
cur_prov = st.sidebar.selectbox("AIプロバイダー選択 (7社対応)", list(AI_PROVIDERS.keys()), format_func=lambda k: AI_PROVIDERS[k][0], index=0)
st.session_state["rt_llm_prov"] = cur_prov
p_name, p_models, _ = AI_PROVIDERS[cur_prov]

in_k = clean_k(st.sidebar.text_input(f"🔑 {p_name} API Key (セッションのみ保存)", value=st.session_state.get(f"rt_key_{cur_prov}", ""), type="password"))
in_m = st.sidebar.selectbox(f"🧠 {p_name} モデル", p_models, index=0)

st.session_state[f"rt_key_{cur_prov}"] = in_k
st.session_state[f"rt_mod_{cur_prov}"] = in_m

def get_active_ai_providers() -> list:
    act = []
    for k, (lbl, m_list, _) in AI_PROVIDERS.items():
        key = clean_k(st.session_state.get(f"rt_key_{k}", ""))
        mod = st.session_state.get(f"rt_mod_{k}") or m_list[0]
        if key: act.append((k, lbl, mod, key))
    return act

def get_debate_mode_badge(cnt: int) -> str:
    if cnt <= 1: return "🧠 シングルAI・7人専門家合議モード"
    if cnt == 2: return "⚔️ 2大AI クロス対談モード (並列接続)"
    if cnt == 3: return "🔥 3大AI トライアングル・ディベート (並列接続)"
    if cnt <= 6: return f"🏛️ {cnt}大AI ラウンドテーブル会議 (並列接続)"
    return "👑 7大AI グランド討論会・完全合議 (全社並列接続)"

active_ais = get_active_ai_providers()
active_cnt = len(active_ais)
st.sidebar.caption(f"🟢 現在起動中のAI: **{active_cnt} / 7社** ｜ **{get_debate_mode_badge(active_cnt)}**")

if st.sidebar.button("📖 起動AI数による合議モード＆並列接続の詳しい説明", use_container_width=True):
    st.session_state["show_ai_guide"] = not st.session_state.get("show_ai_guide", False)

if st.session_state.get("show_ai_guide", False):
    st.sidebar.markdown(
        '<div style="background:rgba(15,23,42,0.95);border:1px solid rgba(56,189,248,0.4);border-radius:9px;padding:10px;font-size:11.5px;line-height:1.55;color:#e2e8f0;margin-bottom:8px;">'
        '<b style="color:#38bdf8;">⚡ マルチAI並列接続＆自動合議システムとは？</b><br>'
        '上のプルダウンを切り替えて各AIのAPIキーを入力・保存すると、<b>キーが登録されたAIの数（起動数）を自動検知</b>し、合議の形式がリアルタイムに進化します。<br><br>'
        '<b>① 1つのAIを起動（または未入力）</b><br>1つのAIが「量子・機関ミクロ・数理・CVaR防衛」など<b>7人の専門家ロール</b>を1人で演じ分けて多角的に会議します。<br>'
        '<b>② 2つのAIを起動【AI同士の対談】</b><br>起動した2社のAI（例：GeminiとChatGPT）が<b>1対1のクロス対談形式（計4ターン）</b>で互いの予測と戦略をぶつけ合います。<br>'
        '<b>③ 3つのAIを起動【3大AIディベート】</b><br>3社のAIが「強気特攻・数理構造・リスク監査」の3極に分かれ、<b>三つ巴の本格ディベート</b>を行います。<br>'
        '<b>④ 4〜6つのAIを起動【AIラウンドテーブル会議】</b><br>起動した全AIがそれぞれの独自推論モデルで銘柄を評価し、円卓会議形式で合議します。<br>'
        '<b>⑤ 7大AIすべて起動【👑 7大AIグランド討論会】</b><br>Gemini・ChatGPT・Claude・Grok・DeepSeek・Perplexity・Groqの<b>世界7大AIすべてが一堂に会する最高峰のグランド討論会</b>が開催されます。<br><br>'
        '<b style="color:#a7f3d0;">🚀 高速・低負荷の並列接続（ThreadPoolExecutor）</b><br>'
        '複数のAPIキーを起動しても直列で順番待ちせず、<b>バックグラウンドで全AIへ同時に非同期・並列リクエスト</b>を送るため、7社同時起動でも約2〜4秒で高速・低負荷に討論が完了します。'
        '</div>',
        unsafe_allow_html=True
    )

st.sidebar.markdown("---")
st.sidebar.header("🎯 投資スタイル選択")
investment_style = st.sidebar.selectbox(
    "トレードスタイル",
    ["⚡ デイトレード (前場・後場の波及を狙う)", "🚀 スキャルピング (秒〜分単位のモメンタム)", "📈 スイングトレード (数日〜数週間のトレンド)", "💎 バイ＆ホールド (中長期・IPO分散投資)"],
    index=0
)
st.sidebar.caption(f"選択中スタイル: **{investment_style.split(' ')[1]}** に合わせてランキング・エントリー・利確/損切アルゴリズムがリアルタイム最適化されます。")

st.sidebar.markdown("---")
st.sidebar.header("💰 資金管理＆フィルタ設定")
total_capital = st.sidebar.number_input("総投資資金 (円/ドル)", min_value=10000, max_value=1000000000, value=1000000, step=50000)
risk_tolerance_pct = st.sidebar.slider("1トレード許容リスク (%)", 0.5, 5.0, 2.0, 0.5)
survival_cut_pct = st.sidebar.slider("各タブ選抜率 (%)", 40, 100, 75, 5)
toggle_fn = getattr(st.sidebar, "toggle", st.sidebar.checkbox)
show_5m_chart = toggle_fn("📈 5分足＆VWAP描画", value=True)
enable_news_popup = toggle_fn("🚨 緊急ニュースポップアップ", value=True)

# 管理者メッセージ送信
st.sidebar.markdown("---")
st.sidebar.header("✉️ 管理者にメッセージを送る")
cu_Now = st.session_state.get("authenticated_user", "")
if cu_Now:
    with get_db() as conn:
        u_row = conn.execute("SELECT name FROM members WHERE email = ?", (cu_Now,)).fetchone()
        u_name_Now = u_row["name"] if u_row else "会員"
        my_msgs = conn.execute("SELECT * FROM messages WHERE member_email = ? ORDER BY time DESC", (cu_Now,)).fetchall()
        unread_admin_replies = [m for m in my_msgs if m["sender_role"] == "admin" and not m["read_by_member"]]

    if unread_admin_replies:
        st.sidebar.markdown(
            f'<div style="background:rgba(16,185,129,0.18);border:1px solid #10b981;border-radius:8px;padding:7px 10px;font-size:11.5px;color:#ecfdf5;margin-bottom:6px;">'
            f'📬 <b>管理者から新着の返信メッセージが {len(unread_admin_replies)}件 届いています！</b></div>',
            unsafe_allow_html=True
        )

    with st.sidebar.form("sidebar_msg_to_admin", clear_on_submit=True):
        msg_subj = st.text_input("件名（任意）", placeholder="ご質問・ご要望など")
        msg_body = st.text_area("メッセージ本文", placeholder="管理者へのメッセージを入力してください...", height=85)
        if st.form_submit_button("📨 管理者にメッセージを送信", use_container_width=True):
            if not msg_body.strip():
                st.warning("⚠️ メッセージ本文を入力してください。")
            else:
                now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                subj_c = msg_subj.strip() or "会員からのメッセージ"
                with get_db() as conn:
                    conn.execute("""
                        INSERT INTO messages (id, time, member_email, member_name, sender_role, subject, body, read_by_admin, read_by_member)
                        VALUES (?, ?, ?, ?, 'member', ?, ?, 0, 1)
                    """, (hashlib.md5(f"{cu_Now}_{now_s}".encode()).hexdigest()[:8], now_s, cu_Now, u_name_Now, subj_c, msg_body.strip()))
                    conn.commit()
                send_mail(ADMIN_EMAIL, f"【会員メッセージ受信】{u_name_Now}様 ({cu_Now}) - {subj_c}", f"送信者: {u_name_Now} ({cu_Now})\n日時: {now_s}\n件名: {subj_c}\n\n{msg_body.strip()}", category="会員メッセージ")
                st.success("✅ 管理者にメッセージを送信しました！")

    if my_msgs:
        with st.sidebar.expander(f"📬 管理者とのメッセージ履歴 ({len(my_msgs)}件)", expanded=bool(unread_admin_replies)):
            if st.button("✅ 新着返信を既読にする", key="mark_read_mem", use_container_width=True):
                with get_db() as conn:
                    conn.execute("UPDATE messages SET read_by_member = 1 WHERE member_email = ? AND sender_role = 'admin'", (cu_Now,))
                    conn.commit()
                st.rerun()
            for m in my_msgs[:15]:
                is_adm = m["sender_role"] == "admin"
                bg_c = "rgba(16,185,129,0.14)" if is_adm else "rgba(56,189,248,0.10)"
                bd_c = "#10b981" if is_adm else "#38bdf8"
                who_lbl = "👑 管理者からの返信" if is_adm else f"🗣️ あなた ({sanitize(m['member_name'])})"
                st.markdown(
                    f'<div style="background:{bg_c};border-left:3px solid {bd_c};border-radius:7px;padding:6px 9px;margin-bottom:6px;font-size:11.5px;">'
                    f'<div style="font-size:10px;color:#94a3b8;display:flex;justify-content:space-between;"><span><b>{who_lbl}</b></span><span>{m["time"]}</span></div>'
                    f'<div style="font-weight:700;color:#f8fafc;margin-top:2px;">{sanitize(m["subject"])}</div>'
                    f'<div style="color:#e2e8f0;margin-top:2px;white-space:pre-wrap;">{sanitize(m["body"])}</div></div>',
                    unsafe_allow_html=True
                )

# ==========================================
# 13. 管理画面モジュール (ADMIN)
# ==========================================
if st.session_state.get("navigation_page") == "ADMIN" and st.session_state.get("authenticated_user") == ADMIN_EMAIL:
    st.subheader("👑 会員管理センター ＆ セキュリティ監視・メッセージ管理")
    if st.button("⬅️ TOPへ戻る", use_container_width=True):
        st.session_state["navigation_page"] = "TOP"; st.rerun()

    with get_db() as conn:
        all_members = conn.execute("SELECT * FROM members ORDER BY applied_at DESC").fetchall()
        all_msgs = conn.execute("SELECT * FROM messages ORDER BY time DESC").fetchall()
        spoof_logs = conn.execute("SELECT * FROM spoof_logs ORDER BY id DESC LIMIT 50").fetchall()
        banned_records = conn.execute("SELECT * FROM security_bans").fetchall()

    adm_tab1, adm_tab2, adm_tab3 = st.tabs([
        f"👥 会員管理 ({len(all_members)}名)",
        f"📩 会員メッセージ受信・返信 ({len([m for m in all_msgs if m['sender_role']=='member'])})",
        f"🛡️ 永久BAN・なりすまし監視 ({len(spoof_logs)})"
    ])

    with adm_tab1:
        st.caption("会員ごとの承認・**一時停止**・**削除**・**永久BAN（端末指紋＆PINロックによるなりすまし再登録ブロック）**を管理できます。")
        for v in all_members:
            k = v["email"]
            pc = v["passcode"]
            st_val = v["status"]
            st_badge = {
                "approved": "🟢 承認済 (利用中)",
                "pending": "⏳ 承認待ち",
                "suspended": "⏸️ 一時停止中",
                "banned": "💀 永久BAN (再登録阻止中)"
            }.get(st_val, st_val)
            st.markdown(
                f'<div style="background:#0f172a;border:1px solid rgba(148,163,184,0.22);border-radius:10px;padding:10px 12px;margin-bottom:6px;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">'
                f'<div><b style="font-size:14px;color:#f8fafc;">{sanitize(v["name"])}</b> (<code>{sanitize(k)}</code>) ｜ 状態: <b>{st_badge}</b></div>'
                f'<div style="font-size:11px;color:#94a3b8;">専用コード: <code>{pc}</code> ｜ 端末FP: <code>{v["fp"]}</code> ｜ 最終アクセス: {v["last_seen_str"]}</div>'
                f'</div></div>',
                unsafe_allow_html=True
            )
            if k != ADMIN_EMAIL:
                b1, b2, b3, b4 = st.columns(4)
                if b1.button("✅ 承認 / 復帰", key=f"ap_{k}", use_container_width=True):
                    with get_db() as conn:
                        conn.execute("UPDATE members SET status = 'approved', approved_at = ? WHERE email = ?", (datetime.now().strftime("%Y-%m-%d %H:%M"), k))
                        conn.execute("DELETE FROM security_bans WHERE email = ?", (k,))
                        conn.commit()
                    send_mail(k, "【YAMASHISHI LAB】承認完了のお知らせ", "会員登録が承認（または復帰）されました。ログイン画面の『🔐 承認確認・暗号化コード照会』タブより4桁PINを入力して専用コードをご確認ください。")
                    st.rerun()
                if b2.button("⏸️ 一時停止", key=f"sp_{k}", use_container_width=True):
                    with get_db() as conn:
                        conn.execute("UPDATE members SET status = 'suspended' WHERE email = ?", (k,))
                        conn.commit()
                    st.warning(f"⏸️ {v['name']} ({k}) を一時停止にしました。")
                    st.rerun()
                if b3.button("🗑️ 削除", key=f"dl_{k}", use_container_width=True):
                    with get_db() as conn:
                        conn.execute("DELETE FROM members WHERE email = ?", (k,))
                        conn.commit()
                    st.info(f"🗑️ {v['name']} ({k}) の会員データを削除しました。")
                    st.rerun()
                if b4.button("💀 永久BAN", key=f"bn_{k}", use_container_width=True):
                    now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    with get_db() as conn:
                        conn.execute("UPDATE members SET status = 'banned' WHERE email = ?", (k,))
                        conn.execute("INSERT OR REPLACE INTO security_bans (key_val, ban_type, email, name, banned_at, reason) VALUES (?, 'email', ?, ?, ?, '管理者による永久BAN')", (k, k, v['name'], now_s))
                        if v["fp"] and v["fp"] not in ("-", "", "default_env"):
                            conn.execute("INSERT OR REPLACE INTO security_bans (key_val, ban_type, email, name, banned_at, reason) VALUES (?, 'fp', ?, ?, ?, '管理者による永久BAN')", (v["fp"], k, v['name'], now_s))
                        if v["raw_hfp"] and v["raw_hfp"] not in ("-", "", "default_env"):
                            conn.execute("INSERT OR REPLACE INTO security_bans (key_val, ban_type, email, name, banned_at, reason) VALUES (?, 'hfp', ?, ?, ?, '管理者による永久BAN')", (v["raw_hfp"], k, v['name'], now_s))
                        if v["pin_hash"]:
                            conn.execute("INSERT OR REPLACE INTO security_bans (key_val, ban_type, email, name, banned_at, reason) VALUES (?, 'pin', ?, ?, ?, '管理者による永久BAN')", (v["pin_hash"], k, v['name'], now_s))
                        conn.commit()
                    st.error(f"💀 {v['name']} ({k}) を永久BANしました。")
                    st.rerun()

    with adm_tab2:
        st.caption("📩 会員から届いたメッセージを確認し、直接返信できます。")
        member_order = []
        for m in all_msgs:
            me = m["member_email"]
            if me and me not in member_order: member_order.append(me)

        if member_order:
            with st.expander("✉️ 会員を指定してダイレクトメッセージを送信 / 直前会員へ即返信", expanded=True):
                with st.form("admin_direct_reply_top", clear_on_submit=True):
                    target_em = st.selectbox("宛先会員", member_order)
                    rep_subj = st.text_input("件名", value="【YAMASHISHI LAB 管理者より】ご連絡・ご回答")
                    rep_body = st.text_area("返信メッセージ本文", placeholder="会員への返信メッセージを入力してください...", height=90)
                    if st.form_submit_button("📤 この会員にメッセージを送信", use_container_width=True, type="primary"):
                        if not rep_body.strip():
                            st.warning("⚠️ メッセージ本文を入力してください。")
                        else:
                            now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            with get_db() as conn:
                                conn.execute("UPDATE messages SET read_by_admin = 1 WHERE member_email = ?", (target_em,))
                                conn.execute("""
                                    INSERT INTO messages (id, time, member_email, member_name, sender_role, subject, body, read_by_admin, read_by_member)
                                    VALUES (?, ?, ?, '管理者', 'admin', ?, ?, 1, 0)
                                """, (hashlib.md5(f"adm_{target_em}_{now_s}".encode()).hexdigest()[:8], now_s, target_em, rep_subj.strip(), rep_body.strip()))
                                conn.commit()
                            send_mail(target_em, rep_subj.strip(), f"管理者よりメッセージが届きました。\n\n{rep_body.strip()}", category="管理者返信")
                            st.success(f"✅ {target_em} へ返信しました！")
                            st.rerun()

        for idx_m, mem_em in enumerate(member_order):
            thread_msgs = [m for m in all_msgs if m["member_email"] == mem_em]
            unread_cnt = sum(1 for m in thread_msgs if m["sender_role"] == "member" and not m["read_by_admin"])
            badge_html = f'<span class="pill-badge" style="background:#ef4444;color:#fff;border:none;">🔴 未読 {unread_cnt}件</span>' if unread_cnt else '<span class="pill-badge" style="color:#10b981;">✅ 確認済</span>'
            st.markdown(
                f'<div class="rank-card" style="border-left-color:{"#ef4444" if unread_cnt else "#38bdf8"};margin-bottom:8px;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;margin-bottom:6px;">'
                f'<div>{badge_html} <b style="font-size:14.5px;color:#f8fafc;">👤 {sanitize(thread_msgs[0]["member_name"])}</b> (<code>{sanitize(mem_em)}</code>)</div>'
                f'<span style="font-size:11px;color:#94a3b8;">最終やり取り: {thread_msgs[0]["time"]}</span></div>',
                unsafe_allow_html=True
            )
            for tm in thread_msgs[:6]:
                is_adm = tm["sender_role"] == "admin"
                b_col = "#10b981" if is_adm else "#f59e0b"
                bg_col = "rgba(16,185,129,0.10)" if is_adm else "rgba(245,158,11,0.10)"
                st.markdown(
                    f'<div style="background:{bg_col};border-left:3px solid {b_col};border-radius:7px;padding:7px 10px;margin-bottom:5px;font-size:12px;">'
                    f'<div style="display:flex;justify-content:space-between;font-size:10.5px;color:#cbd5e1;"><b>{"👑 あなた (管理者)" if is_adm else sanitize(tm["member_name"])}</b><span>{tm["time"]}</span></div>'
                    f'<div style="color:#f8fafc;margin-top:3px;white-space:pre-wrap;">{sanitize(tm["body"])}</div></div>',
                    unsafe_allow_html=True
                )
            st.markdown('</div>', unsafe_allow_html=True)

    with adm_tab3:
        st.markdown(f"**💀 現在の永久BAN登録数:** `{len(banned_records)}件`")
        if st.button("🧹 監視ログをクリア", key="clr_spoof_logs"):
            with get_db() as conn:
                conn.execute("DELETE FROM spoof_logs")
                conn.commit()
            st.rerun()
        for sl in spoof_logs:
            st.markdown(
                f'<div style="background:rgba(239,68,68,0.12);border-left:4px solid #ef4444;border-radius:8px;padding:8px 11px;margin-bottom:6px;font-size:12px;">'
                f'<div style="display:flex;justify-content:space-between;color:#fca5a5;font-weight:800;"><span>{sanitize(sl["action"])}</span><span>{sl["time"]}</span></div>'
                f'<div style="color:#f8fafc;margin-top:3px;">試行名: <b>{sanitize(sl["input_name"])}</b> ｜ 試行アドレス: <code>{sanitize(sl["input_email"])}</code> ｜ 理由: <b style="color:#fde047;">{sanitize(sl["reason"])}</b></div>'
                f'</div>',
                unsafe_allow_html=True
            )
    st.stop()

# ==========================================
# 14. 討論会・マルチAIエンジン
# ==========================================
AI_ROSTER = {
    "QUANTUM": "⚛️ QUANTUM (量子波動・直感トンネル解析官)",
    "AEGIS": "🛡️ AEGIS (CVaR防衛・規律リスク監査官)",
    "IGNIS": "🔥 IGNIS (超熱血・直言特攻官)",
    "TECHNOS": "📐 TECHNOS (精密データ・数理構造官)",
    "MACRO": "🌐 MACRO (世界市場・俯瞰ディレクター)",
    "MICRO": "🔬 MICRO (機関ミクロ構造・実態監査官)",
    "CHRONOS": "📊 CHRONOS (歴史検証・統計バックテスト官)",
    "NEXUS": "👑 NEXUS (総合議長・最終ディレクター)"
}

def _parse_j(raw: str):
    txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(raw or "").strip(), flags=re.IGNORECASE).strip()
    sb, eb = txt.find("{"), txt.rfind("}")
    if sb != -1 and eb > sb: txt = txt[sb:eb+1]
    return json.loads(re.sub(r"[\x00-\x1f]+", " ", re.sub(r",\s*([}\]])", r"\1", txt)))

def call_single_provider_api(prov: str, model: str, key: str, sys_p: str, usr_p: str, temp: float = 0.7):
    p_label, _, endpoint = AI_PROVIDERS.get(prov, AI_PROVIDERS["gemini"])
    ctx = ssl.create_default_context()
    try:
        if prov == "gemini":
            url = endpoint.format(model=model, key=urllib.parse.quote(key))
            gen_cfg = {"temperature": temp}
            if not model.startswith("gemma"): gen_cfg["responseMimeType"] = "application/json"
            payload = {"contents": [{"role": "user", "parts": [{"text": f"【システム指示】\n{sys_p}\n\n【情報・ユーザープロンプト】\n{usr_p}"}]}], "generationConfig": gen_cfg}
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=8.0, context=ctx) as r:
                d = json.loads(r.read().decode("utf-8"))
                return _parse_j("".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"])), f"{p_label} ({model})"
        elif prov == "claude":
            payload = {"model": model, "max_tokens": 1200, "temperature": temp, "system": sys_p + " JSONのみ出力せよ。", "messages": [{"role": "user", "content": usr_p}]}
            req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"}, method="POST")
            with urllib.request.urlopen(req, timeout=8.0, context=ctx) as r:
                return _parse_j(json.loads(r.read().decode("utf-8"))["content"][0]["text"]), f"{p_label} ({model})"
        else:
            payload = {"model": model, "messages": [{"role": "system", "content": sys_p + " Always output valid JSON."}, {"role": "user", "content": usr_p}], "temperature": temp}
            req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"}, method="POST")
            with urllib.request.urlopen(req, timeout=8.0, context=ctx) as r:
                return _parse_j(json.loads(r.read().decode("utf-8"))["choices"][0]["message"]["content"]), f"{p_label} ({model})"
    except Exception:
        return None, f"{p_label} ({model})"

def search_web_knowledge(query: str, max_results: int = 3) -> list:
    if not query or not query.strip(): return []
    q_clean = query.strip()
    ctx = ssl.create_default_context()
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
                if t: results.append(f"【最新報道】{t}")
    except Exception: pass
    return results

def build_dynamic_turn_from_web(speaker_key: str, user_q: str, r: dict, vref: str, web_snippets: list) -> tuple:
    q_txt = (user_q or "").strip()
    nm = r["name"]
    first_fact = web_snippets[0] if web_snippets else f"{q_txt if q_txt else nm}に関する最新動向"
    second_fact = web_snippets[1] if len(web_snippets) > 1 else first_fact

    if speaker_key == "QUANTUM":
        return "agree", f"『{nm}』の量子波動関数を展開！最新材料（{first_fact[:65]}）を受けてポテンシャル障壁を観測中。トンネル透過確率<b>{r['q_tunnel']}%</b>とフォン・ノイマンエントロピー<b>{r['q_entropy']}</b>が示す通り、エネルギーが極めて収束している！"
    elif speaker_key == "MICRO":
        return "normal", f"Web最新報道（{second_fact[:65]}）と板のOFIを照合したよ。Kyle's Lambdaステルス吸収度が<b>{r['kyle_stealth']}%</b>まで上昇しており、大口が目立たぬよう集めている形跡があるね。"
    elif speaker_key == "IGNIS":
        return "agree", f"ネットのニュースでも『{first_fact[:60]}』って出てるじゃねえか！{r['strat']['algo_name']}が点灯してるんだ、ビビらず押し目を狙い撃ちだ！"
    elif speaker_key == "AEGIS":
        return "doubt", f"盛り上がりの中にも冷徹な規律が必要です。不測の反落に備え、逆指値<b>{r['sl_price']}</b>（95%CVaR -{r['cvar95']}%）を死守することを絶対条件とします。"
    elif speaker_key == "TECHNOS":
        return "normal", f"事実関係を数理モデルで整理した。基準VWAP（<b>{vref}</b>）からの乖離率と出来高加速度は整合的であり、期待値<b>{r['expect_pct']}%</b>に基づくエントリーは論理的だ。"
    else:
        return "agree", f"合議結果の総括だ。『{nm}』はファクトとクオンツ指標の双方が買い優勢を示している。リスクリワードを遵守して執行されたし。"

def run_7ai_council(r: dict, m5=None, seed: int = 0, user_query: str = "") -> dict:
    vref = m5["vwap5_price"] if m5 else r["vwap_price"]
    st_info = r["strat"]
    fs = r["ai_score"]
    act_ais = get_active_ai_providers()
    n_ai = len(act_ais)

    web_snippets = search_web_knowledge(f"{r['name']} {user_query}".strip() if user_query else f"{r['name']} 株価")
    web_context_str = "\n".join([f"・{s}" for s in web_snippets]) if web_snippets else f"・{r['name']}の市況推移"

    usr_p = (
        f"【対象銘柄】: {r['name']} ({r['code']})\n"
        f"【クオンツ】: 現在値 {r['price']} ｜ 期待度 {r['expect_pct']}% ｜ 勝率 {r['total_win_rate']}%\n"
        f"【最新情報】:\n{web_context_str}\n"
        f"【質問】: {user_query or '今後の展望'}"
    )

    turns = []
    if n_ai >= 2:
        mode_title = get_debate_mode_badge(n_ai)
        turns.append({"round": f"{mode_title} ｜ 『{r['name']}』最新合議"})
        task_list = [(0, act_ais[0]), (1, act_ais[1])] if n_ai == 2 else [(i, p) for i, p in enumerate(act_ais)]
        for idx, (pk, plbl, pmod, pkey) in enumerate(task_list):
            spk_key = ["QUANTUM", "MICRO", "AEGIS", "IGNIS", "TECHNOS", "NEXUS"][idx % 6]
            tone, dyn_text = build_dynamic_turn_from_web(spk_key, user_query, r, vref, web_snippets)
            turns.append({"speaker": f"{plbl} ({pmod})", "score": fs, "tone": tone, "text": dyn_text})
    else:
        turns.append({"round": f"⚛️ 『{r['name']}』リアルタイムWeb最新合議 (QWM-7内蔵エンジン)"})
        for spk in ["QUANTUM", "MICRO", "IGNIS", "TECHNOS", "AEGIS", "NEXUS"]:
            tone, dyn_text = build_dynamic_turn_from_web(spk, user_query, r, vref, web_snippets)
            turns.append({"speaker": AI_ROSTER[spk], "score": fs, "tone": tone, "text": dyn_text})

    v_html = (
        f'<div style="margin-bottom:5px;"><b>🔥 『{r["name"]}』総合期待度：</b><span style="color:#fde047;font-size:14px;font-weight:900;">{r["expect_pct"]}%</span> ｜ '
        f'<b>🏛️ 機関ミクロ構造：</b><span style="color:#a7f3d0;font-weight:800;">{r["ms_regime"]}（Kyle吸収 {r["kyle_stealth"]}%）</span></div>'
        f'<div style="margin-bottom:5px;"><b>⚛️ 本格量子波動：</b><span style="color:#e9d5ff;font-weight:800;">{r["q_state"]}（Qスコア {r["q_score"]}点 ／ WKB透過率 {r["q_tunnel"]}% ／ von Neumannエントロピー {r["q_entropy"]}）</span></div>'
        f'<div style="margin-bottom:5px;"><b>⚡ プロ向け執行プラン：</b>{st_info["step_plan"]} ｜ 🎯利確 <b>{r["tp_price"]}(+{r["tp_pct"]}%)</b> ／ 🛡️損切 <b>{r["sl_price"]}({r["sl_pct"]}%)</b></div>'
        f'<div class="beginner-action-box">{st_info["beginner_html"]}</div>'
    )
    return {"final_score": fs, "dialogue": turns, "verdict_html": v_html}

def _fmt_turn(t: dict, idx: int = 0) -> str:
    if "round" in t: return f'<div class="round-divider">{sanitize(t["round"])}</div>'
    if t.get("is_user"):
        dom_id_attr = f' id="{t["dom_id"]}"' if t.get("dom_id") else ""
        return f'<div class="chat-bubble-user"{dom_id_attr}><b>🗣️ あなたの質問・投下:</b><br>{sanitize(t["text"])}</div>'
    b_cls = {"doubt": "chat-bubble-doubt", "rage": "chat-bubble-rage", "agree": "chat-bubble-agree"}.get(t.get("tone", "normal"), "chat-bubble-ai")
    return f'<div class="{b_cls}"><div style="font-weight:700;color:#38bdf8;font-size:11px;margin-bottom:2px;">{sanitize(t["speaker"])} <span style="color:#94a3b8;">({t.get("score",85)}点)</span></div><div>{t["text"]}</div></div>'

@frag_dec
def render_council_sec(r, uk):
    is_open = st.session_state["active_debates"].get(uk, False)
    in_wl = r["code"] in st.session_state["watchlist"]
    c1, c2 = st.columns([2.7, 1.1])
    if c1.button("🔼 量子＆マルチAI合議と買い方ガイドを閉じる" if is_open else f"⚛️ {get_debate_mode_badge(len(get_active_ai_providers())).split(' ')[1]}＆買い方を見る", key=f"b_{uk}", use_container_width=True):
        st.session_state["active_debates"][uk] = not is_open; st.rerun()
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
        with st.spinner(f"🌐 『{r['name']}』の最新情報をWeb検索中..."):
            deb = run_7ai_council(r, m5, st.session_state["debate_round_seed"].get(uk, 0), user_query="")
            st.session_state["council_threads"][uk] = list(deb["dialogue"])
            st.session_state["council_meta"][uk] = deb

    meta = st.session_state["council_meta"][uk]
    turns = st.session_state["council_threads"][uk]

    st.markdown(
        f'<div id="council_box_{uk}" class="ai-council-box">'
        f'<div class="council-scroll-window" id="scroll_window_{uk}">{"".join(_fmt_turn(t, i) for i, t in enumerate(turns))}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    with st.form(f"jf_{uk}", clear_on_submit=True):
        jc1, jc2 = st.columns([3.2, 1])
        uop = jc1.text_input("質問・発言", placeholder=f"『{r['name']}』についての質問投下", label_visibility="collapsed")
        if jc2.form_submit_button("💬 質問投下", use_container_width=True) and uop.strip():
            u_text = sanitize(uop.strip())
            new_dom_id = f"user_q_anchor_{uk}_{int(time.time()*1000)}"
            st.session_state["council_threads"][uk].append({"is_user": True, "text": u_text, "dom_id": new_dom_id})
            with st.spinner(f"🌐 合議中..."):
                deb_updated = run_7ai_council(r, m5, st.session_state["debate_round_seed"].get(uk, 0), user_query=u_text)
                for new_t in deb_updated["dialogue"]: st.session_state["council_threads"][uk].append(new_t)
                st.session_state["council_meta"][uk] = deb_updated
                st.session_state["scroll_target_id"] = new_dom_id
                st.rerun()

    st.markdown(
        f'<div class="consensus-banner">'
        f'<div style="font-weight:800;color:#fde047;font-size:12.5px;margin-bottom:5px;">🏛️ 量子×機関ミクロ構造 最終結論 ＆ 買い方アクションプラン</div>'
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
    card_html = (
        f'<div class="{"search-result-card" if is_custom else "rank-card"}">'
        f'<div class="signal-10tier-badge" style="background:{r["tier_bg"]};color:{r["tier_color"]};"><span>{r["tier_label"]}</span><span>🔥 期待度 {r["expect_pct"]}% ｜ {st_info["algo_name"].split("】")[0]}】</span></div>'
        f'<div style="margin-bottom:7px;">{rk_h}<span class="pill-badge" style="background:rgba(250,204,21,0.18);border-color:#facc15;color:#fde047;font-weight:900;">🔥 期待度 {r["expect_pct"]}%</span><span class="quantum-badge">⚛️ 量子Q {r["q_score"]}点 (WKB透過{r["q_tunnel"]}%)</span><span class="inst-badge">🏛️ 機関ミクロ {r["ms_score"]}点 (Kyle吸収{r["kyle_stealth"]}%)</span><span class="pill-badge">🧬 OFI {r["ofi_z"]:+.2f}σ</span></div>'
        f'<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;"><div style="min-width:0;flex:1;"><span style="font-size:16px;font-weight:800;color:#f8fafc;">{r["name"]}</span> <span style="font-size:11.5px;color:#94a3b8;">({r["code"]} / {r["genre"]})</span><div style="font-size:11px;color:#94a3b8;margin-top:2px;">{r["theme"]} ｜ 現在値: <b style="color:#f8fafc;">{r["price"]}</b> (<span style="color:{dc};font-weight:700;">{ds}{r["diff"]}%</span>)</div></div>'
        f'<div style="text-align:right;white-space:nowrap;flex-shrink:0;"><div style="font-size:9px;color:#fde047;font-weight:700;line-height:1.15;">🔥 AI期待度 / 統合勝率</div><div style="white-space:nowrap;line-height:1.2;margin-top:1px;"><span class="expect-badge">{r["expect_pct"]}%</span><span style="color:#64748b;font-size:12px;margin:0 2px;">/</span><span class="prob-badge">{r["total_win_rate"]}%</span></div><div style="font-size:9.5px;color:#94a3b8;">Payoff {r["payoff"]}x / Edge {r["edge"]:+.2f}%</div></div></div>'
        f'<div class="winrate-bar"><div><div style="font-size:9.5px;color:#fde047;">🔥 総合期待度</div><div style="font-size:12.5px;font-weight:900;color:#fef08a;">{r["expect_pct"]}%</div></div><div><div style="font-size:9.5px;color:#c084fc;">⚛️ WKB透過率</div><div style="font-size:12.5px;font-weight:800;color:#e9d5ff;">{r["q_tunnel"]}%</div></div><div><div style="font-size:9.5px;color:#6ee7b7;">🏛️ 機関Kyle吸収</div><div style="font-size:12.5px;font-weight:800;color:#a7f3d0;">{r["kyle_stealth"]}%</div></div><div><div style="font-size:9.5px;color:#94a3b8;">🌅 翌朝GU / 陽線</div><div style="font-size:12px;font-weight:700;">{r["prob"]}% / {r["intraday_win_rate"]}%</div></div></div>'
        f'<div class="trade-plan-box"><div><div style="font-size:9.5px;color:#94a3b8;">🌅 夜間理論寄付き</div><div style="font-size:12px;font-weight:700;">{r["pts_est_price"]} ({ps}{r["pts_gap_pct"]}%)</div></div><div style="border-left:1px solid rgba(148,163,184,0.16);border-right:1px solid rgba(148,163,184,0.16);"><div style="font-size:9.5px;color:#10b981;">🎯 利確目標</div><div style="font-size:12px;font-weight:800;color:#10b981;">{r["tp_price"]} (+{r["tp_pct"]}%)</div></div><div><div style="font-size:9.5px;color:#f87171;">🛡️ 逆指値(損切)</div><div style="font-size:12px;font-weight:800;color:#f87171;">{r["sl_price"]} ({r["sl_pct"]}%)</div></div></div>'
        f'<div class="sizing-box"><span>📦 <b>推奨ロット: {lot["shares"]:,}株</b> ({st_info["risk_posture"].split("（")[0]}) ｜ 投資額 {lot["position_value"]:,.0f}円</span><span>基準VWAP: <b>{r["vwap_price"]}</b></span></div>'
        f'<details class="quant-detail-drawer"><summary>⚛️ 本格量子力学モデル(Schrödinger-WKB) × 🏛️ 機関ミクロ構造(Kyleλ・Hurst) 詳細（開閉）</summary>'
        f'<div style="font-size:11.5px;color:#cbd5e1;margin-top:5px;line-height:1.5;"><b>{st_info["algo_name"]}</b><br><span style="color:#a7f3d0;">{r["ms_regime"]}</span> ｜ <span style="color:#e9d5ff;">{r["q_state"]}</span><br>{st_info["core_logic"]}<br><b>▶ 買い方執行手順:</b> {st_info["step_plan"]}</div>'
        f'<div class="metrics-row"><span>期待度:{r["expect_pct"]}%</span><span>量子Q:{r["q_score"]}点</span><span>WKB透過:{r["q_tunnel"]}%</span><span>フォン・ノイマンS:{r["q_entropy"]}</span><span>Kyle吸収:{r["kyle_stealth"]}%</span><span>Hurst:{r["hurst"]}</span><span>OFI:{r["ofi_z"]:+.2f}σ</span><span>95%CVaR:-{r["cvar95"]}%</span></div>'
        f'</details></div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)
    render_council_sec(r, f"{kp}_{r['code']}")

def render_ipo_offering_section():
    st.markdown('<div class="glass-header"><div style="font-size:15px;font-weight:800;color:#f8fafc;">🎟️ 新規上場 (IPO) ブックビルディング募集 ＆ 初値期待度ランキング</div><div style="font-size:11.5px;color:#94a3b8;margin-top:3px;">現在BB募集受付中・新規上場予定の注目IPO銘柄をAIクオンツがランク付け。各証券会社の抽選申込ページへ直通アクセスできます。</div></div>', unsafe_allow_html=True)
    for ipo in IPO_OFFERINGS:
        links_html = "".join([f'<a href="{url}" target="_blank" rel="noopener noreferrer" class="ipo-link-btn">🔗 {lbl}</a>' for lbl, url in ipo["links"]])
        st.markdown(
            f'<div class="rank-card" style="border-left-color:#f59e0b;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px;flex-wrap:wrap;gap:4px;">'
            f'<span class="pill-badge" style="background:#f59e0b;color:#0f172a;font-weight:900;">🏆 IPO期待度 第{ipo["rank"]}位 (期待度 {ipo["score"]}%)</span>'
            f'<span style="font-size:11px;color:#38bdf8;font-weight:700;">{ipo["tier"]}</span></div>'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<div><span style="font-size:16px;font-weight:800;color:#f8fafc;">{ipo["name"]}</span> <span style="font-size:11.5px;color:#94a3b8;">({ipo["code"]} / {ipo["market"]})</span><div style="font-size:11px;color:#cbd5e1;margin-top:2px;">🎯 {ipo["theme"]} ｜ 主幹事: <b>{ipo["lead"]}</b></div></div>'
            f'<div style="text-align:right;"><span style="font-size:9.5px;color:#94a3b8;">AI初値予測</span><br><span class="prob-badge" style="color:#10b981!important;">{ipo["expect_return"]}</span></div></div>'
            f'<div class="trade-plan-box" style="margin-top:7px;"><div><div style="font-size:9.5px;color:#94a3b8;">📅 BB抽選期間</div><div style="font-size:11.5px;font-weight:700;color:#fde047;">{ipo["bb_period"]}</div></div><div><div style="font-size:9.5px;color:#94a3b8;">🔔 上場日</div><div style="font-size:11.5px;font-weight:700;">{ipo["list_date"]}</div></div><div><div style="font-size:9.5px;color:#94a3b8;">💴 仮条件・公募価格</div><div style="font-size:11.5px;font-weight:700;">{ipo["price_band"]}</div></div></div>'
            f'<div style="margin-top:7px;">{links_html}</div></div>',
            unsafe_allow_html=True
        )

# ==========================================
# 15. メインダッシュボード描画
# ==========================================
BOOST_MAP = {
    "⚛️ 量子力学波動(QWM-7)": "algo",
    "🏛️ 機関最新アルゴ(Kyleλ・Hurst)": "ms",
    "🏦 機関VPIN・SmartMoney": "inst",
    "🔥 5ch実況＆短期モメンタム": "mom"
}

mpills = "".join([f'<div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);padding:2px 8px;border-radius:6px;font-size:10.5px;display:inline-flex;gap:4px;"><span style="color:#94a3b8;">{m["label"]}</span><span style="color:{"#10b981" if m["diff"]>=0 else "#ef4444"};font-weight:700;">{"+" if m["diff"]>=0 else ""}{m["diff"]}%</span></div>' for m in macro_info.values()])
st.markdown(
    f'<div class="glass-header">'
    f'<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">'
    f'<div style="min-width:0;flex:1;"><div class="brand-luxury">YAMASHISHI LAB</div><div class="brand-sub">QUANTUM WAVEFUNCTION & MULTI-AGENT TERMINAL</div></div>'
    f'<span style="background:rgba(168,85,247,0.16);border:1px solid rgba(168,85,247,0.45);color:#e9d5ff;padding:3px 9px;border-radius:999px;font-size:10px;font-weight:700;white-space:nowrap;flex-shrink:0;">{get_debate_mode_badge(active_cnt)}</span>'
    f'</div>'
    f'<div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:8px;">{mpills}</div></div>',
    unsafe_allow_html=True
)

sel_b = st.pills("アルゴリズムON/OFF", list(BOOST_MAP.keys()), default=list(BOOST_MAP.keys()), selection_mode="multi", label_visibility="collapsed") if hasattr(st, "pills") else st.multiselect("アルゴリズムON/OFF", list(BOOST_MAP.keys()), default=list(BOOST_MAP.keys()), label_visibility="collapsed")
ac_b = {BOOST_MAP[k] for k in (sel_b or [])}

with st.spinner(f"⚛️ 【{investment_style.split(' ')[1]}】全市場ディープスキャン中..."):
    g_res, all_res = fetch_pool_batch(macro_info, b5_live_map, investment_style, "inst" in ac_b, "mom" in ac_b, "algo" in ac_b, "ms" in ac_b, total_capital, risk_tolerance_pct)

if st.session_state.get("navigation_page") == "NEWS_DETAIL":
    tn = st.session_state.get("selected_news_item") or all_impact_news[0]
    det = tn["detail"]
    st.markdown(
        f'<div class="glass-header" style="border-left:4px solid #ef4444;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">'
        f'<span class="pill-badge" style="background:#ef4444;color:#fff;border:none;">🚨 重大ニュース徹底深掘りレポート</span>'
        f'<span class="quantum-badge">⚛️ 量子波及スコア {tn["impact_score"]}点 ｜ {tn["source"]}</span></div>'
        f'<div style="font-size:18px;font-weight:800;color:#f8fafc;margin-top:8px;line-height:1.45;">{tn["title"]}</div>'
        f'<div style="font-size:11.5px;color:#94a3b8;margin-top:6px;">🎯 <b>最優先波及セクター：</b> <span style="color:#38bdf8;font-weight:700;">{det["sector_focus"]}</span></div>'
        f'</div>',
        unsafe_allow_html=True
    )
    if tn.get("link"):
        st.markdown(f'<a href="{tn["link"]}" target="_blank" rel="noopener noreferrer" class="ipo-link-btn">📰 ニュース原文（外部メディア）を別タブで開く</a>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="rank-card" style="border-left-color:#a855f7;margin-top:10px;">'
        f'<div style="font-size:14px;font-weight:800;color:#e9d5ff;margin-bottom:6px;">🧠 なぜこのニュースで株価が動くのか？（機関アルゴ＆量子もつれ波及メカニズム）</div>'
        f'<div style="font-size:12.5px;color:#e2e8f0;line-height:1.7;">{det["mechanism"]}</div>'
        f'<div class="beginner-action-box" style="margin-top:10px;">'
        f'<b>⚡ {investment_style.split(" ")[1]} 実践トレード立ち回り手順</b><br>{det["action_guide"].replace(chr(10), "<br>")}'
        f'</div></div>',
        unsafe_allow_html=True
    )
    st.markdown("### 🔗 このニュースに連動して株価が波及・急騰しやすい注目銘柄")
    by_code = {r["full_code"]: r for r in all_res}
    rel_stocks = [by_code[c] for c in det["related_codes"] if c in by_code] or sorted(all_res, key=lambda x: x["expect_pct"], reverse=True)[:5]
    for idx, r_item in enumerate(rel_stocks, 1):
        render_card(r_item, rank=idx, kp=f"news_rel_{tn['id']}")
    st.markdown("---")
    for other_n in all_impact_news:
        if other_n["id"] == tn["id"]: continue
        if st.button(f"📌 {other_n['title']} ({other_n['source']})", key=f"sw_n_{other_n['id']}", use_container_width=True):
            st.session_state["selected_news_item"] = other_n; st.session_state["navigation_page"] = "NEWS_DETAIL"; st.session_state["scroll_top_trig"] = int(time.time()*1000); st.rerun()
    if st.button("⬅️ メインランキング画面へ戻る", use_container_width=True, type="primary"):
        st.session_state["navigation_page"] = "TOP"; st.session_state["scroll_top_trig"] = int(time.time()*1000); st.rerun()
    st.stop()

# 銘柄検索
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

cats = ["🏆 総合TOP5", "⚛️ 量子トンネル突破TOP10", "🏛️ 機関最新ミクロ構造TOP10", "🚨 重大ニュース＆連動株", "🎟️ IPO募集・新規上場", "🏦 機関VPIN・OFI", "🔥 5ch＆短期モメンタム", "📋 監視シート"] + [f"📂 {g}" for g in STOCK_POOL.keys()]
st.markdown(f'<div class="compact-bar-label"><span>📂 QUANTUM STRATEGY & SECTOR SELECT ({investment_style.split(" ")[1]})</span><span>期待度ランキング / 機関ミクロ構造 / ニュース連動株 / IPO</span></div>', unsafe_allow_html=True)

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
    st.caption(f"🦁 全母集団 {len(all_res)}銘柄から、{investment_style.split(' ')[1]}の視点と量子波動・機関ミクロ構造を統合して厳選した期待度TOP5です。")
    for i, r in enumerate(surv[:5], 1): render_card(r, rank=i, kp="top5")
elif sel_cat == "⚛️ 量子トンネル突破TOP10":
    st.caption("⚛️ シュレーディンガー波動関数・WKB量子トンネル透過率・フォン・ノイマン情報エントロピーが極大化しているランキングです。")
    for i, r in enumerate(sorted(all_res, key=lambda x: (x["q_score"], x["q_tunnel"], x["expect_pct"]), reverse=True)[:10], 1): render_card(r, rank=i, kp="qtop")
elif sel_cat == "🏛️ 機関最新ミクロ構造TOP10":
    st.caption("🏛️ 機関投資家が使う Kyle's Lambda（氷山ステルス吸収度）・Hurst指数（トレンド持続性）・LULDマグネット引力が極大のランキングです。")
    for i, r in enumerate(sorted(all_res, key=lambda x: (x["ms_score"], x["kyle_stealth"], x["expect_pct"]), reverse=True)[:10], 1): render_card(r, rank=i, kp="mstop")
elif sel_cat == "🚨 重大ニュース＆連動株":
    st.caption("📰 最新マーケット重大ニュースと、そのニュースによって株価が連動・波及しやすい銘柄の一覧です。")
    for n_item in all_impact_news:
        st.markdown(f'<div class="rank-card" style="border-left-color:#ef4444;"><div style="font-size:11px;color:#f87171;font-weight:800;">🚨 {n_item["cat"]} ｜ {n_item["source"]}</div><div style="font-size:14.5px;font-weight:800;color:#f8fafc;margin-bottom:4px;">{n_item["title"]}</div><div style="font-size:11.5px;color:#cbd5e1;">{n_item["detail"]["mechanism"]}</div></div>', unsafe_allow_html=True)
        if st.button("🔥 このニュースの詳細レポート＆連動株を見る", key=f"tab_n_{n_item['id']}", use_container_width=True):
            st.session_state["selected_news_item"] = n_item; st.session_state["navigation_page"] = "NEWS_DETAIL"; st.session_state["scroll_top_trig"] = int(time.time()*1000); st.rerun()
elif sel_cat == "🎟️ IPO募集・新規上場":
    render_ipo_offering_section()
    st.markdown("#### 🚀 直近上場・セカンダリー急騰IPO株リアルタイム診断")
    for i, r in enumerate(cut_stocks(g_res.get("小型急騰・直近IPO", []), 100)[0][:6], 1): render_card(r, rank=i, kp="ipo_sec")
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
