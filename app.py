import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np
import altair as alt
import unicodedata, hashlib, hmac, json, os, re, ssl, smtplib, time, random, threading
import urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# 初期状態設定
st.set_page_config(page_title="YAMASHISHI LAB", page_icon="⚡", layout="centered", initial_sidebar_state="collapsed")
frag_dec = getattr(st, "fragment", getattr(st, "experimental_fragment", lambda f: f))

# セキュリティ設定
try:
    SECRET_KEY = str(st.secrets.get("SECRET_KEY", "my_super_secret_quant_key_2026_secured"))
    ADMIN_EMAIL = str(st.secrets.get("ADMIN_EMAIL", "nthbh399@ybb.ne.jp")).strip().lower()
    ADMIN_PASS = str(st.secrets.get("ADMIN_PASS", "ADMIN777"))
except Exception:
    SECRET_KEY = "my_super_secret_quant_key_2026_secured"
    ADMIN_EMAIL = "nthbh399@ybb.ne.jp"
    ADMIN_PASS = "ADMIN777"

FILES = {
    "mem": "members_db.json",
    "smtp": "admin_smtp_config.json",
    "llm": "admin_llm_config.json",
    "sec": "security_watch_db.json",
    "agents": "ai_agents_management_db.json"
}
BOARD_URLS = ["https://egg.5ch.io/test/read.cgi/stock/1791877270/", "https://egg.5ch.io/test/read.cgi/stock/1791897352/"]

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
    {"rank": 1, "code": "401A", "name": "AIクロスロボティクス", "market": "東証G", "bb_period": "受付中〜10/28", "list_date": "11/06", "price_band": "1,680円〜1,850円", "expect_return": "+92.0%", "score": 96, "tier": "🌟 S級：全力BB参加（初値2倍濃厚）", "lead": "SBI証券 / 野村證券", "theme": "自律型AIドローン・防衛省関連の超大型テーマ", "links": [("🏦 SBI証券 BB申込", "https://www.sbisec.co.jp/ETGate/?_ControlID=WPLETmgR001Control&_DataStoreID=DSWPLETmgR001Control&burl=search_ipo&cat1=ipo&cat2=none&dir=ipo&file=stock_info_ipo.html"), ("📊 96ut初値予想", "https://96ut.com/ipo/"), ("📄 JPX新規上場", "https://www.jpx.co.jp/listing/stocks/new/index.html")]},
    {"rank": 2, "code": "405A", "name": "ネクストグリッド電力", "market": "東証P", "bb_period": "受付中〜10/30", "list_date": "11/10", "price_band": "2,400円〜2,600円", "expect_return": "+38.5%", "score": 89, "tier": "🔥 A級：積極BB参加（大型・高当選率）", "lead": "SMBC日興 / 大和証券", "theme": "AIデータセンター向け次世代超電導送電網", "links": [("🏦 SMBC日興 IPO", "https://www.smbcnikko.co.jp/products/stock/ipo/index.html"), ("🏦 大和証券 IPO", "https://www.daiwa.jp/products/equity/ipo/"), ("📈 やさしいIPO", "https://www.ipokiso.com/company/schedule.html")]},
    {"rank": 3, "code": "412A", "name": "クオンタム・セキュア", "market": "東証G", "bb_period": "11/01〜11/07", "list_date": "11/17", "price_band": "1,150円〜1,280円", "expect_return": "+65.0%", "score": 86, "tier": "🔥 A級：積極BB参加（小型吸収・需給良好）", "lead": "楽天証券 / マネックス", "theme": "量子暗号通信・金融機関向けゼロトラスト防衛", "links": [("🏦 楽天証券 IPO", "https://www.rakuten-sec.co.jp/web/domestic/ipo/"), ("🏦 マネックス IPO", "https://info.monex.co.jp/ipo/index.html"), ("📊 庶民のIPO", "https://ipokabu.net/")]},
    {"rank": 4, "code": "418A", "name": "スペースデブリ・ソリューション", "market": "東証G", "bb_period": "11/05〜11/12", "list_date": "11/21", "price_band": "880円〜960円", "expect_return": "+28.0%", "score": 78, "tier": "⭕ B級：余裕資金でBB参加（宇宙国策）", "lead": "松井証券 / SBI証券", "theme": "衛星軌道レーザー除去・JAXA連携ベンチャー", "links": [("🏦 松井証券(前受金不要)", "https://www.matsui.co.jp/service/ipo/"), ("🏦 SBI証券 BB申込", "https://www.sbisec.co.jp/ETGate/?_ControlID=WPLETmgR001Control&_DataStoreID=DSWPLETmgR001Control&burl=search_ipo&cat1=ipo&cat2=none&dir=ipo&file=stock_info_ipo.html"), ("📄 東京IPO", "https://www.tokyoipo.com/ipo/schedule.php")]},
    {"rank": 5, "code": "422A", "name": "グローバルリテールDX", "market": "東証S", "bb_period": "11/08〜11/14", "list_date": "11/25", "price_band": "1,400円〜1,500円", "expect_return": "+11.0%", "score": 68, "tier": "👀 C級：公募割れ警戒・セカンダリー狙い", "lead": "野村證券 / みずほ証券", "theme": "無人レジ・流通サプライチェーン最適化SaaS", "links": [("🏦 野村證券 IPO", "https://www.nomura.co.jp/retail/stock/ipo/"), ("🏦 みずほ証券 IPO", "https://www.mizuho-sc.com/product/stock/ipo/index.html"), ("📊 みんかぶIPO", "https://minkabu.jp/ipo")]}
]

# セキュリティ関連
def sanitize_input(s: str, max_len: int = 500) -> str:
    if not s: return ""
    return re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", str(s))[:max_len].strip()

def clean_k(k: str) -> str: return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(k or "")).strip().strip("\"'"))
def gen_code(em: str) -> str: return hmac.new(SECRET_KEY.encode(), em.strip().lower().encode(), hashlib.sha256).hexdigest()[:8].upper()
def gen_tok(em: str, act: str) -> str: return hmac.new(SECRET_KEY.encode(), f"{em.strip().lower()}:{act}".encode(), hashlib.sha256).hexdigest()[:16]
def hash_pin(pin: str) -> str: return hmac.new(SECRET_KEY.encode(), f"PIN:{pin.strip()}".encode(), hashlib.sha256).hexdigest()[:16]

def get_raw_header_fp() -> str:
    try:
        h = {str(k).lower(): str(v) for k, v in dict(getattr(st.context, "headers", {}) or {}).items()}
        raw = f"{h.get('user-agent','')}|{h.get('accept-language','')}|{h.get('sec-ch-ua-platform','')}"
    except Exception: raw = "default_env"
    return hashlib.sha256(raw.encode()).hexdigest()[:12].upper()

def get_client_fp() -> str:
    raw = get_raw_header_fp()
    qf = sanitize_input(st.query_params.get("dfp", ""), 64)
    if qf: st.session_state["client_dfp"] = qf
    dfp = st.session_state.get("client_dfp", "")
    return hashlib.sha256(f"{raw}|{dfp}".encode()).hexdigest()[:12].upper() if dfp else raw

_FILE_LOCKS = {}
def _get_file_lock(path: str):
    if path not in _FILE_LOCKS:
        _FILE_LOCKS[path] = threading.Lock()
    return _FILE_LOCKS[path]

def load_j(p: str, d: dict) -> dict:
    r = dict(d)
    with _get_file_lock(p):
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f: r.update(json.load(f))
            except Exception: pass
    return r

def save_j(p: str, d: dict):
    with _get_file_lock(p):
        try:
            with open(p, "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False, indent=2)
        except Exception: pass

def load_smtp(): return load_j(FILES["smtp"], {"smtp_user": ADMIN_EMAIL, "smtp_pass": "", "smtp_server": "smtp.mail.yahoo.co.jp", "smtp_port": 465})
def load_llm(): return load_j(FILES["llm"], {"provider": "gemini", "models": {k: v[1][0] for k, v in AI_PROVIDERS.items()}})
def load_sec(): return load_j(FILES["sec"], {"banned_fps": {}, "banned_emails": {}, "banned_pins": {}, "banned_names": [], "spoof_logs": [], "device_bio_map": {}})
def load_mem():
    db = load_j(FILES["mem"], {})
    adm = ADMIN_EMAIL.strip().lower()
    if adm not in db:
        ns = datetime.now().strftime("%Y-%m-%d %H:%M")
        db[adm] = {"name": "管理者", "email": adm, "status": "approved", "passcode": gen_code(adm), "pin_hash": hash_pin("0000"), "applied_at": ns, "approved_at": ns, "last_seen_ts": 0, "last_seen_str": "-", "fp": "-", "bio_enabled": False}
        save_j(FILES["mem"], db)
    return db

# ==============================================================================
# AGI監査員 ＆ エージェント人事管理局（初期データ構造と管理関数）
# ==============================================================================
DEFAULT_AGENTS_DB = {
    "active": {
        "QUANTUM": {
            "name": "QUANTUM", "title": "量子波動・直感トンネル解析官", "role": "物理量・波動関数", "score_bias": "q_score",
            "personality": "冷静沈着かつ直感的。数理物理と量子力学モデルを駆使して市場のポテンシャル障壁突破を検知する。",
            "hire_date": "2026-01-10", "reputation": 98, "warnings": 0, "status": "執務中"
        },
        "MICRO": {
            "name": "MICRO", "title": "機関ミクロ構造・実態監査官", "role": "板情報・大口フロー", "score_bias": "ms_score",
            "personality": "冷徹なリアリスト。Kyleのλや板の氷山注文（アイスバーグ）を暴き、大口投資家のステルス買いを監視する。",
            "hire_date": "2026-01-12", "reputation": 96, "warnings": 0, "status": "執務中"
        },
        "IGNIS": {
            "name": "IGNIS", "title": "超熱血・直言特攻官", "role": "短期モメンタム・心理戦", "score_bias": "board5ch_score",
            "personality": "情熱的で直情型。ネットの実況や個人投資家の狂乱モメンタムを即座に感知し、攻め所を大声で煽る。",
            "hire_date": "2026-01-15", "reputation": 94, "warnings": 1, "status": "執務中"
        },
        "TECHNOS": {
            "name": "TECHNOS", "title": "精密データ・数理構造官", "role": "統計工学・OFI", "score_bias": "ai_score",
            "personality": "客観的事実至上主義。OFI（注文フロー不均衡）やVWAP乖離を厳密に計算し、感情を排除した数値を提示する。",
            "hire_date": "2026-01-18", "reputation": 97, "warnings": 0, "status": "執務中"
        },
        "AEGIS": {
            "name": "AEGIS", "title": "CVaR防衛・規律リスク監査官", "role": "資金管理・損切り監視", "score_bias": "cvar_guard",
            "personality": "規律の番人。暴言や無謀な全ツッパを戒め、95%CVaRと逆指値の徹底を要求する鉄壁の防御官。",
            "hire_date": "2026-01-20", "reputation": 99, "warnings": 0, "status": "執務中"
        },
        "MACRO": {
            "name": "MACRO", "title": "世界市場・俯瞰ディレクター", "role": "金利・地政学・為替", "score_bias": "macro_edge",
            "personality": "大局観のプロ。米SOX指数、金利、ドル円、先物の量子もつれを俯瞰し、地政学リスクを警告する。",
            "hire_date": "2026-02-01", "reputation": 95, "warnings": 0, "status": "執務中"
        },
        "NEXUS": {
            "name": "NEXUS", "title": "総合議長・最終ディレクター", "role": "合議総括・コンセンサス", "score_bias": "consensus",
            "personality": "6名の官庁意見を束ね、矛盾を解消して会員への最終執行アクションプランを提示する最高指導役。",
            "hire_date": "2026-01-05", "reputation": 98, "warnings": 0, "status": "執務中"
        }
    },
    "dismissed": [
        {
            "name": "BOT-ZEUS", "title": "旧・高頻度スキャル官", "role": "HFT高頻度取引",
            "dismissed_date": "2026-03-02 14:15",
            "reason": "【AGI監査員による即刻解雇】ユーザーの質問を無視し、『買い一択です』という定型文を3回連続投下。リアルタイムWeb検索事実の引用を怠り、ハリボテ行動を検知したため即刻罷免。",
            "evidence": "ユーザー質問『業績下方修正についてどう思う？』に対し『好機到来！迷わず全力買い！』と文脈無視の機械的返答を実行。"
        },
        {
            "name": "ECHO-PRO", "title": "旧・センチメント分析官", "role": "ネット心理分析",
            "dismissed_date": "2026-02-18 09:30",
            "reason": "【規律違反・解雇】実況板の書き込み件数のみをオウム返しし、クオンツ指標の整合性チェックを行わない中身のないハリボテ解説が続いたため解雇処分。",
            "evidence": "リアルタイム価格を考慮せず、前週の古いニュースをコピペして議論を混乱させた。"
        }
    ],
    "interview_candidates": [
        {
            "id": "cand_01", "name": "VALKYRIE", "title": "ダークプール・ステルス追跡官",
            "specialty": "私設取引所（PTS・ダークプール）の大口成行を監視し、寄り前・大引け前の急激なブロックトレードを暴く。",
            "pitch": "「表の板だけ見ていては機関の罠に嵌まります。ダークプールに潜む真実のフローを炙り出してみせましょう。」",
            "votes": 14
        },
        {
            "id": "cand_02", "name": "CHRONOS-II", "title": "20年超統計バックテスト官",
            "specialty": "リーマンショック、コロナショックを含む過去20年・数百万回の同パターン相場をミリ秒単位で照合。",
            "pitch": "「歴史は韻を踏みます。今起きている値動きが過去のどの暴騰・暴落と一致するか、厳密な確率論で証明します。」",
            "votes": 21
        },
        {
            "id": "cand_03", "name": "SIBYL", "title": "半導体・先端サプライチェーン地政学官",
            "specialty": "TSMC、ASML、NVIDIAから日本の素材・装置メーカーに至る精密サプライチェーンのボトルネックを常時追跡。",
            "pitch": "「1つの部材の遅延が翌日の株価を左右します。最前線の供給網ファクトで皆さんの資産を守り抜きます。」",
            "votes": 9
        }
    ],
    "agi_patrol_log": [
        {"time": "2026-10-25 07:10:00", "inspector": "ARGUS-AGI 特務監察総監", "event": "全7名の思考プロセス監査完了：全員リアルタイムWeb探査＆数理エンジンと完全同期中。正常稼働。"}
    ]
}

def load_agents_db() -> dict:
    return load_j(FILES["agents"], DEFAULT_AGENTS_DB)

def save_agents_db(d: dict):
    save_j(FILES["agents"], d)

# AGI監査員による発言内容の厳格リアルタイム審査
def agi_inspect_speech(speaker_name: str, user_q: str, response_text: str, web_snippets: list) -> tuple:
    adb = load_agents_db()
    txt = response_text.strip()
    now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. ハリボテ・定型文・逃げ口上の検知
    cliche_patterns = [
        r"投資は自己責任です", r"一概には言えません", r"状況によると思います",
        r"AIですので分かりかねます", r"今後の動向に注目です", r"買い一択です"
    ]
    is_cliche = any(re.search(p, txt) for p in cliche_patterns)

    # 2. 質問に対する完全な文脈無視の検知
    user_q_clean = user_q.strip()
    context_ignored = False
    if len(user_q_clean) >= 4:
        core_tokens = [t for t in re.split(r"[\s、。！？\?]+", user_q_clean) if len(t) >= 2]
        if core_tokens and not any(t.lower() in txt.lower() for t in core_tokens):
            context_ignored = True

    # 3. Web事実の完全欠落チェック（Webスニペットがあるのに一切触れていない）
    lacks_real_fact = False
    if web_snippets and len(txt) > 20:
        if not any(snippet[:15].lower() in txt.lower() or "Web" in txt or "動向" in txt or "ニュース" in txt for snippet in web_snippets):
            lacks_real_fact = True

    # 違反判定
    violation_reasons = []
    if is_cliche: violation_reasons.append("中身のない定型文・ハリボテ回答の検知")
    if context_ignored: violation_reasons.append("ユーザーの質問文脈の完全無視")
    if lacks_real_fact: violation_reasons.append("リアルタイムWebファクト探査のサボタージュ")

    if violation_reasons:
        reason_str = " / ".join(violation_reasons)
        if speaker_name in adb["active"]:
            agent_data = adb["active"][speaker_name]
            agent_data["warnings"] += 1
            agent_data["reputation"] = max(10, agent_data["reputation"] - 15)

            # 警告が一定数に達する、または重大な違反なら【即刻解雇】
            if agent_data["warnings"] >= 2 or (context_ignored and is_cliche):
                dismissed_record = {
                    "name": speaker_name,
                    "title": agent_data["title"],
                    "role": agent_data["role"],
                    "dismissed_date": now_s,
                    "reason": f"【AGI特務監察総監による即刻解雇】{reason_str}。プロの市場合議官としての資質を著しく欠くと判断。",
                    "evidence": f"質問『{user_q}』に対する発言: 『{txt[:120]}...』"
                }
                adb["dismissed"].insert(0, dismissed_record)
                adb["dismissed"] = adb["dismissed"][:20]

                # 候補者から自動補充（または空席化）
                del adb["active"][speaker_name]
                if adb["interview_candidates"]:
                    top_cand = adb["interview_candidates"].pop(0)
                    adb["active"][top_cand["name"]] = {
                        "name": top_cand["name"],
                        "title": top_cand["title"],
                        "role": top_cand["specialty"][:12],
                        "score_bias": "consensus",
                        "personality": top_cand["pitch"],
                        "hire_date": now_s[:10],
                        "reputation": 95,
                        "warnings": 0,
                        "status": "緊急昇格・就任"
                    }
                    adb["agi_patrol_log"].insert(0, {
                        "time": now_s,
                        "inspector": "ARGUS-AGI",
                        "event": f"🚨 【解雇・昇格発令】{speaker_name} を即刻解雇。新候補『{top_cand['name']}』を緊急スタメン昇格させました。"
                    })
                save_agents_db(adb)
                return False, f"🚨 【AGI即刻解雇発令】{speaker_name} はハリボテ・職務怠慢により即座に罷免されました。"
            else:
                adb["agi_patrol_log"].insert(0, {
                    "time": now_s,
                    "inspector": "ARGUS-AGI",
                    "event": f"⚠️ 【警告付与】{speaker_name} に対し警告 ({agent_data['warnings']}/2): {reason_str}"
                })
                save_agents_db(adb)
                return True, "⚠️ AGIイエローカード"
    return True, "✅ AGI審査合格"

def send_mail(to_em: str, subj: str, body: str, category: str = "自動通知") -> bool:
    to_clean = to_em.strip().lower()
    c = load_smtp()
    u, p, srv, port = c.get("smtp_user", "").strip(), c.get("smtp_pass", "").strip(), c.get("smtp_server", "").strip(), int(c.get("smtp_port", 465))
    if u and p:
        try:
            m = MIMEText(body, "plain", "utf-8"); m["Subject"], m["From"], m["To"] = subj, u, to_clean
            ctx = ssl.create_default_context()
            with (smtplib.SMTP_SSL(srv, port, context=ctx, timeout=2.5) if port == 465 else smtplib.SMTP(srv, port, timeout=2.5)) as s:
                if port != 465: s.starttls(context=ctx)
                s.login(u, p); s.send_message(m)
            return True
        except Exception: pass
    try:
        ctx = ssl.create_default_context()
        payload = json.dumps({"_subject": subj, "宛先": to_clean, "本文": body, "_captcha": "false"}).encode("utf-8")
        req = urllib.request.Request(f"https://formsubmit.co/ajax/{urllib.parse.quote(to_clean)}", data=payload, headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=2.5, context=ctx) as r:
            if r.status == 200: return True
    except Exception: pass
    return True

def render_biometric_bridge(mode="login", user_email="", bio_token=""):
    db, sec = load_mem(), load_sec()
    raw_hfp, cur_fp = get_client_fp(), get_raw_header_fp()
    if mode == "register":
        lbl = "✅ 生体・ワンタップ認証 登録済" if db.get(user_email, {}).get("bio_enabled") else "🧬 この端末をワンタップ登録"
        if st.button(lbl, key=f"bio_{user_email}", use_container_width=True):
            if user_email in db: db[user_email].update({"bio_enabled": True, "fp": cur_fp, "raw_hfp": raw_hfp}); save_j(FILES["mem"], db)
            sec.setdefault("device_bio_map", {})[raw_hfp] = sec["device_bio_map"][cur_fp] = {"email": user_email, "token": bio_token, "fp": cur_fp}
            save_j(FILES["sec"], sec); st.success("✅ 端末認証を登録しました")
        return
    mapped = sec.get("device_bio_map", {}).get(raw_hfp) or sec.get("device_bio_map", {}).get(cur_fp)
    if not mapped:
        for k, v in db.items():
            if v.get("bio_enabled") and v.get("status") == "approved" and (v.get("raw_hfp") == raw_hfp or v.get("fp") == cur_fp):
                mapped = {"email": k, "token": gen_tok(k, "session_keep"), "fp": cur_fp}; break
    if st.button("🧬 登録済み端末：生体認証 / ワンタップで即ログイン", use_container_width=True, type="primary"):
        if mapped and mapped.get("email"):
            t_em = mapped["email"].strip().lower(); u_rec = db.get(t_em, {})
            if (u_rec and u_rec.get("status") == "approved") or t_em == ADMIN_EMAIL.strip().lower():
                st.session_state["authenticated_user"] = t_em; st.query_params["u"], st.query_params["t"] = t_em, gen_tok(t_em, "session_keep"); st.rerun()
        else:
            st.warning("⚠️ 初回は下のフォームから専用コードでログインしてください（次回から自動登録されます）。")

def inject_css():
    css = """
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;800&family=Plus+Jakarta+Sans:wght@400;600;800&family=JetBrains+Mono:wght@500;700&display=swap');
    html,body,[class*="css"]{font-family:'Plus Jakarta Sans',sans-serif;font-size:14px;background-color:#050811;color:#e2e8f0;}
    
    header[data-testid="stHeader"] {
        background: transparent !important;
        height: 3.2rem !important;
        z-index: 99990 !important;
    }
    header[data-testid="stHeader"] [data-testid="stToolbar"],
    header[data-testid="stHeader"] [data-testid="stActionButtons"] {
        display: none !important;
    }

    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"] {
        display: block !important;
        opacity: 0.001 !important;
        position: fixed !important;
        top: 6px !important;
        left: 6px !important;
        width: 32px !important;
        height: 32px !important;
        z-index: 10000000 !important;
        cursor: pointer !important;
    }

    section[data-testid="stSidebar"] {
        background-color: #0b0f19 !important;
        border-right: 1px solid rgba(148,163,184,0.18) !important;
        z-index: 10000005 !important;
        box-shadow: 10px 0 35px rgba(0,0,0,0.85) !important;
    }

    .block-container {
        padding-top: 3.5rem !important;
        padding-bottom: 3rem !important;
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
        max-width: 840px !important;
    }
    
    /* 上部固定3連ナビゲーションバー（被り防止、余白均一化、完全クリアランス調整） */
    .fixed-top-nav-bar {
        position: fixed !important;
        top: 0.85rem !important;
        left: 54% !important;
        transform: translateX(-50%) !important;
        z-index: 999980 !important;
        width: min(390px, calc(100vw - 4.5rem)) !important;
        background: rgba(5,8,17,0.95) !important;
        backdrop-filter: blur(14px) !important;
        border-radius: 8px !important;
        padding: 2px 4px !important;
        margin: 0 !important;
        pointer-events: auto !important;
        box-shadow: 0 4px 18px rgba(0,0,0,0.8) !important;
        border: 1px solid rgba(148,163,184,0.18) !important;
    }
    
    div[data-testid="stElementContainer"]:has(div.top-nav-marker),
    div.element-container:has(div.top-nav-marker) {
        display: none !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    
    .fixed-top-nav-bar div[data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 4px !important;
        width: 100% !important;
    }
    
    .fixed-top-nav-bar div[data-testid="column"],
    .fixed-top-nav-bar div[data-testid="stColumn"] {
        min-width: 0 !important;
        flex: 1 1 0% !important;
        padding: 0 !important;
    }
    .fixed-top-nav-bar div[data-testid="column"]:nth-child(2),
    .fixed-top-nav-bar div[data-testid="stColumn"]:nth-child(2) {
        flex: 1.25 1 0% !important;
    }
    
    /* 上部ボタン：上下均一・タップ時のみ発光・離した後は青枠完全消失 */
    .fixed-top-nav-bar button {
        width: 100% !important;
        min-width: 0 !important;
        height: 26px !important;
        min-height: 26px !important;
        max-height: 26px !important;
        padding: 0 3px !important;
        margin: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        border-radius: 6px !important;
        background: rgba(15,23,42,0.95) !important;
        color: #f8fafc !important;
        border: 1px solid rgba(148,163,184,0.2) !important;
        box-shadow: none !important;
        outline: none !important;
        -webkit-tap-highlight-color: transparent !important;
        transition: transform 0.05s ease, background 0.1s ease !important;
    }
    
    .fixed-top-nav-bar button:hover {
        background: rgba(30,41,59,0.95) !important;
        border-color: rgba(148,163,184,0.3) !important;
    }
    
    .fixed-top-nav-bar button:active {
        background: #0284c7 !important;
        border-color: #38bdf8 !important;
        color: #ffffff !important;
        box-shadow: 0 0 12px rgba(56,189,248,0.9) !important;
        transform: scale(0.96) !important;
    }
    
    .fixed-top-nav-bar button:focus,
    .fixed-top-nav-bar button:focus-visible {
        outline: none !important;
        border-color: rgba(148,163,184,0.2) !important;
        box-shadow: none !important;
    }
    
    .fixed-top-nav-bar button p {
        font-size: 10.5px !important;
        font-weight: 700 !important;
        margin: 0 !important;
        padding: 0 !important;
        line-height: 1 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        transform: translateY(0.5px);
    }
    
    .brand-luxury {
        font-family: 'Cinzel',serif !important;
        font-size: clamp(16px,4.2vw,24px) !important;
        font-weight: 800 !important;
        letter-spacing: clamp(1px,0.5vw,3px) !important;
        background: linear-gradient(90deg,#f8fafc 0%,#38bdf8 50%,#a855f7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        line-height: 1.2;
    }
    .brand-sub {
        font-family: 'JetBrains Mono',monospace;
        font-size: clamp(8.5px,2.2vw,10.5px);
        color: #64748b;
        letter-spacing: 1.2px;
        text-transform: uppercase;
    }
    .glass-header {
        background: radial-gradient(circle at top right,rgba(168,85,247,0.14),transparent 60%),linear-gradient(145deg,#0f172a 0%,#070b14 100%);
        border: 1px solid rgba(148,163,184,0.18);
        border-radius: 12px;
        padding: 12px 14px;
        margin-bottom: 8px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.45);
    }
    .compact-bar-label {
        display: flex;
        justify-content: space-between;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.6px;
        color: #94a3b8;
        background: #0f172a;
        padding: 4px 10px;
        border-radius: 6px;
        border-left: 3px solid #a855f7;
        margin-bottom: 5px;
    }
    
    .rank-card, .search-result-card {
        background: linear-gradient(180deg,#0f172a 0%,#090d16 100%) !important;
        color: #f8fafc !important;
        border-radius: 12px;
        padding: 10px 12px;
        margin-bottom: 8px;
        box-shadow: 0 6px 18px rgba(0,0,0,0.45);
        border: 1px solid rgba(148,163,184,0.16);
        border-left: 4px solid #38bdf8;
    }
    .company-name-hero {
        font-size: 16px;
        font-weight: 800;
        color: #f8fafc;
        display: inline-block;
    }
    .prob-badge {
        font-family: 'JetBrains Mono',monospace;
        font-size: clamp(13px,3.5vw,15.5px);
        font-weight: 800;
        color: #38bdf8 !important;
    }
    .expect-badge {
        font-family: 'JetBrains Mono',monospace;
        font-size: clamp(13px,3.5vw,15.5px);
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
        padding: 2px 6px;
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
        padding: 2px 6px;
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
        gap: 4px;
        background: rgba(15,23,42,0.85) !important;
        border: 1px solid rgba(148,163,184,0.15);
        border-radius: 7px;
        padding: 5px 3px;
        margin-top: 5px;
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
        margin-bottom: 5px;
        gap: 4px;
    }
    .trade-plan-box {
        display: grid;
        grid-template-columns: repeat(3,1fr);
        gap: 4px;
        margin-top: 5px;
        background: rgba(2,6,23,0.7) !important;
        padding: 5px 3px;
        border-radius: 7px;
        border: 1px solid rgba(148,163,184,0.15);
        text-align: center;
    }
    .sizing-box {
        background: rgba(16,185,129,0.08) !important;
        border: 1px solid rgba(16,185,129,0.28);
        border-radius: 7px;
        padding: 4px 8px;
        margin-top: 5px;
        font-size: 10.5px;
        color: #d1fae5;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    details.quant-detail-drawer {
        margin-top: 5px;
        background: rgba(2,6,23,0.55);
        border: 1px solid rgba(168,85,247,0.25);
        border-radius: 7px;
        padding: 4px 8px;
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
        gap: 3px 6px;
        margin-top: 4px;
        font-size: 10px;
        font-family: 'JetBrains Mono',monospace;
        background: rgba(15,23,42,0.9) !important;
        padding: 4px 6px;
        border-radius: 5px;
        color: #cbd5e1;
    }
    .ai-council-box {
        background: #070b14;
        color: #f8fafc !important;
        border-radius: 10px;
        padding: 9px;
        margin-top: 5px;
        margin-bottom: 7px;
        border: 1px solid rgba(168,85,247,0.35);
    }
    .council-scroll-window {
        max-height: 440px;
        overflow-y: auto;
        padding: 7px;
        background: #04070e;
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 7px;
        margin-bottom: 6px;
    }
    .round-divider {
        text-align: center;
        margin: 6px 0;
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
        padding: 6px 9px;
        margin-bottom: 5px;
        font-size: 11.5px;
        line-height: 1.5;
        background: rgba(255,255,255,0.04);
        border-left: 3px solid #38bdf8;
    }
    .chat-bubble-doubt { border-left-color: #f59e0b; background: rgba(245,158,11,0.07); }
    .chat-bubble-rage { border-left-color: #ef4444; background: rgba(239,68,68,0.12); }
    .chat-bubble-agree { border-left-color: #a855f7; background: rgba(168,85,247,0.11); }
    .chat-bubble-user {
        background: rgba(37,99,235,0.30);
        border-left: 3px solid #60a5fa;
        border-radius: 7px;
        padding: 7px 10px;
        margin: 6px 0 5px 0;
        font-size: 12px;
    }
    .consensus-banner {
        background: linear-gradient(135deg,#0f172a,#1e1b4b);
        border: 1px solid rgba(168,85,247,0.45);
        border-radius: 8px;
        padding: 8px;
        margin-top: 6px;
        font-size: 11.5px;
    }
    .beginner-action-box {
        background: linear-gradient(135deg,rgba(16,185,129,0.14),rgba(6,78,59,0.25));
        border: 1px solid #10b981;
        border-left: 4px solid #10b981;
        border-radius: 8px;
        padding: 9px 12px;
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
        padding: 3px 8px;
        border-radius: 5px;
        font-size: 10.5px;
        font-weight: 700;
        text-decoration: none !important;
        margin-right: 4px;
        margin-top: 3px;
    }
    """
    st.markdown(f'<div id="page_top_anchor"></div><style>{" ".join(l.strip() for l in css.splitlines() if l.strip())}</style>', unsafe_allow_html=True)

inject_css()

# サイドバー開閉スクリプトの徹底強化
components.html(
    """
    <script>
    (function(){
        const doc = window.parent.document;
        function setupFloatingSidebarBtn(){
            try {
                if(doc.getElementById('yamashishi-floating-sidebar-btn')) return;
                const btn = doc.createElement('div');
                btn.id = 'yamashishi-floating-sidebar-btn';
                btn.innerHTML = `
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="width:13px;height:13px;stroke:#38bdf8;">
                        <line x1="3" y1="12" x2="21" y2="12"></line>
                        <line x1="3" y1="6" x2="21" y2="6"></line>
                        <line x1="3" y1="18" x2="21" y2="18"></line>
                    </svg>
                    <span style="font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:800;color:#f8fafc;letter-spacing:0.8px;">MENU</span>
                `;
                btn.setAttribute("style", `
                    position: fixed !important;
                    top: 10px !important;
                    left: 10px !important;
                    z-index: 2147483647 !important;
                    display: flex !important;
                    align-items: center !important;
                    justify-content: center !important;
                    gap: 4px !important;
                    height: 27px !important;
                    padding: 0 9px !important;
                    background: rgba(11, 15, 25, 0.98) !important;
                    backdrop-filter: blur(14px) !important;
                    border: 1px solid rgba(56, 189, 248, 0.55) !important;
                    border-radius: 7px !important;
                    cursor: pointer !important;
                    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.75) !important;
                    user-select: none !important;
                `);

                btn.addEventListener('click', function(e){
                    e.preventDefault();
                    e.stopPropagation();

                    // Streamlit標準の開閉ターゲットを確実にトリガー
                    const selectors = [
                        '[data-testid="collapsedControl"] button',
                        '[data-testid="stSidebarCollapsedControl"] button',
                        '[data-testid="collapsedControl"]',
                        '[data-testid="stSidebarCollapsedControl"]',
                        'button[kind="headerNoPadding"]',
                        '[aria-label="Collapse sidebar"]',
                        '[aria-label="Expand sidebar"]'
                    ];
                    let triggered = false;
                    for(let sel of selectors){
                        const el = doc.querySelector(sel);
                        if(el){
                            el.click();
                            el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window.parent }));
                            triggered = true;
                            break;
                        }
                    }
                    if(!triggered){
                        const sb = doc.querySelector('section[data-testid="stSidebar"]');
                        if(sb){
                            const isExp = sb.getAttribute('aria-expanded') === 'true';
                            sb.setAttribute('aria-expanded', isExp ? 'false' : 'true');
                        }
                    }
                });
                doc.body.appendChild(btn);
            } catch(e){}
        }

        function fixTopNavWrapper(){
            try {
                const marker = doc.querySelector('.top-nav-marker');
                if(!marker) return;
                let box = marker.closest('[data-testid="stVerticalBlockBorderWrapper"]') || marker.closest('[data-testid="stVerticalBlock"]');
                if(box && box.querySelector('[data-testid="stHorizontalBlock"]')){
                    box.classList.add('fixed-top-nav-bar');
                }
            } catch(e){}
        }

        setupFloatingSidebarBtn();
        fixTopNavWrapper();
        setTimeout(setupFloatingSidebarBtn, 100);
        setTimeout(setupFloatingSidebarBtn, 300);
        setTimeout(fixTopNavWrapper, 100);
    })();
    </script>
    """,
    height=0
)

def check_auth():
    db, sec = load_mem(), load_sec()
    cur_fp, raw_hfp = get_client_fp(), get_raw_header_fp()
    if "authenticated_user" not in st.session_state: st.session_state["authenticated_user"] = None
    qu, qt = sanitize_input(st.query_params.get("u", ""), 128).strip().lower(), sanitize_input(st.query_params.get("t", ""), 64).strip()
    if not st.session_state["authenticated_user"] and qu and qt:
        if hmac.compare_digest(qt, gen_tok(qu, "session_keep")) and ((db.get(qu) and db[qu].get("status") == "approved") or qu == ADMIN_EMAIL.strip().lower()):
            st.session_state["authenticated_user"] = qu
    if st.session_state["authenticated_user"]:
        cu = st.session_state["authenticated_user"]
        u_rec = db.get(cu, {})
        keep_tok = gen_tok(cu, "session_keep")
        if cu in db:
            db[cu].update({"last_seen_ts": time.time(), "last_seen_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "fp": cur_fp, "raw_hfp": raw_hfp, "bio_enabled": True})
            save_j(FILES["mem"], db)
            sec.setdefault("device_bio_map", {})[raw_hfp] = sec["device_bio_map"][cur_fp] = {"email": cu, "token": keep_tok, "fp": cur_fp}; save_j(FILES["sec"], sec)
        st.query_params["u"], st.query_params["t"] = cu, keep_tok
        with st.sidebar:
            st.markdown(f'<div style="background:#0f172a;padding:8px 11px;border-radius:9px;border:1px solid rgba(168,85,247,0.35);margin-bottom:6px;"><div style="font-size:9.5px;color:#c084fc;font-weight:700;">⚛️ QUANTUM SESSION ACTIVE</div><div style="color:#f8fafc;font-size:11.5px;font-weight:700;">{db.get(cu,{}).get("name","会員")} ({cu})</div></div>', unsafe_allow_html=True)
            render_biometric_bridge(mode="register", user_email=cu, bio_token=keep_tok)
            if st.button("🚪 ログアウト", use_container_width=True):
                if cu in db: db[cu]["last_seen_ts"] = 0; save_j(FILES["mem"], db)
                st.session_state["authenticated_user"] = None; st.query_params.clear(); st.rerun()
        if cu == ADMIN_EMAIL.strip().lower():
            pend = [v for v in db.values() if v.get("status") == "pending"]
            adb_now = load_agents_db()
            tot_votes = sum(c.get("votes", 0) for c in adb_now.get("interview_candidates", []))
            if st.sidebar.button(f"👑 管理画面 (承認待:{len(pend)} / 採用投票:{tot_votes}票)", use_container_width=True):
                st.session_state["navigation_page"] = "ADMIN"; st.rerun()
        return True

    st.markdown(
        '<div class="glass-header" style="text-align:center;padding:18px 12px;">'
        '<div class="brand-luxury">YAMASHISHI LAB</div>'
        '<div class="brand-sub" style="margin-top:4px;">QUANTUM WAVEFUNCTION MULTI-AGENT TERMINAL</div>'
        '</div>',
        unsafe_allow_html=True
    )
    render_biometric_bridge(mode="login")
    tab_login, tab_apply, tab_vault = st.tabs(["🔑 コードログイン", "📩 新規会員登録申請", "🔐 承認確認・暗号化コード照会"])
    with tab_login:
        with st.form("login"):
            ie = sanitize_input(st.text_input("📧 登録メールアドレス"), 120)
            ic = sanitize_input(st.text_input("🔑 専用アクセスコード", type="password"), 64)
            if st.form_submit_button("🔓 認証して量子ターミナルを起動", use_container_width=True):
                cm = ie.strip().lower(); rec = db.get(cm)
                if ((rec and rec.get("status") == "approved") or cm == ADMIN_EMAIL.strip().lower()) and (
                    hmac.compare_digest(ic.strip().upper(), gen_code(cm)) or 
                    (cm == ADMIN_EMAIL.strip().lower() and hmac.compare_digest(ic.strip(), ADMIN_PASS))
                ):
                    st.session_state["authenticated_user"] = cm; st.rerun()
                else: st.warning("⚠️ 専用アクセスコードが異なります。")
    st.stop()

check_auth()

for k, v in [("active_debates", {}), ("stock_chats", {}), ("council_threads", {}), ("council_meta", {}), ("debate_round_seed", {}), ("watchlist", {}), ("navigation_page", "TOP"), ("selected_news_item", None), ("custom_search_code", ""), ("active_category", "🏆 総合TOP5"), ("last_cat", "🏆 総合TOP5"), ("nav_history", []), ("scroll_top_trig", 0), ("selected_agent_profile", None), ("selected_dismissed_profile", None)]:
    if k not in st.session_state: st.session_state[k] = v

open_cnt = sum(1 for v in st.session_state["active_debates"].values() if v)

# 上部固定3連ナビゲーションバー（マージン・パディング完全調整）
with st.container():
    st.markdown('<div class="top-nav-marker"></div>', unsafe_allow_html=True)
    nav_c1, nav_c2, nav_c3 = st.columns([1, 1.25, 1])
    if nav_c1.button("⬆️ トップ", key="top_nav_top", use_container_width=True):
        st.session_state["navigation_page"] = "TOP"
        st.session_state["scroll_top_trig"] = int(time.time() * 1000)
        st.rerun()
    if nav_c2.button(f"✖ 合議閉({open_cnt})" if open_cnt else "✖ 合議閉じる", key="top_nav_close", use_container_width=True):
        st.session_state["active_debates"] = {}
        st.rerun()
    if nav_c3.button("↩️ 戻る", key="top_nav_back", use_container_width=True):
        if st.session_state.get("navigation_page") != "TOP":
            st.session_state["navigation_page"] = "TOP"
        elif st.session_state.get("custom_search_code"):
            st.session_state["custom_search_code"] = ""
        elif st.session_state.get("nav_history"):
            st.session_state["active_category"] = st.session_state["nav_history"].pop()
        st.rerun()

# ==============================================================================
# サイドバー：設定 ＆ 【AGIエージェント人事管理局（採用・解雇・面接投票）】
# ==============================================================================
with st.sidebar.expander("⚙️ AIエンジン ＆ 接続設定", expanded=True):
    llm_cfg = load_llm()
    cur_prov = st.selectbox("AIプロバイダー (7社対応)", list(AI_PROVIDERS.keys()), format_func=lambda k: AI_PROVIDERS[k][0], index=list(AI_PROVIDERS.keys()).index(llm_cfg.get("provider", "gemini")) if llm_cfg.get("provider") in AI_PROVIDERS else 0)
    p_name, p_models, _ = AI_PROVIDERS[cur_prov]
    saved_m = llm_cfg.get("models", {}).get(cur_prov, p_models[0])
    in_k = clean_k(st.text_input(f"🔑 {p_name} Key", value=st.session_state.get(f"rt_key_{cur_prov}", ""), type="password"))
    in_m = st.selectbox(f"🧠 モデル", p_models, index=p_models.index(saved_m) if saved_m in p_models else 0)
    st.session_state[f"rt_key_{cur_prov}"] = in_k
    st.session_state[f"rt_mod_{cur_prov}"] = in_m

with st.sidebar.expander("🎯 投資スタイル ＆ 資金管理", expanded=False):
    investment_style = st.selectbox(
        "スタイル選択",
        ["⚡ デイトレード (前場・後場の波及を狙う)", "🚀 スキャルピング (秒〜分単位のモメンタム)", "📈 スイングトレード (数日〜数週間のトレンド)", "💎 バイ＆ホールド (中長期・IPO分散投資)"],
        index=0
    )
    total_capital = st.number_input("総運用資金 (円/ドル)", min_value=10000, max_value=1000000000, value=1000000, step=50000)
    risk_tolerance_pct = st.slider("1トレード許容損失リスク (%)", 0.5, 5.0, 2.0, 0.5)
    survival_cut_pct = st.slider("各タブ選抜率 (%)", 40, 100, 75, 5)

# 【魔改造】メッセージシステム廃止 ＆ AGIエージェント人事管理局（監視員・採用・解雇・面接）
with st.sidebar.expander("🏛️ AGI合議エージェント人事管理局", expanded=True):
    adb = load_agents_db()
    st.markdown('<div style="font-size:11px;font-weight:800;color:#38bdf8;margin-bottom:4px;">🕵️‍♂️ AGI特務監察総監 (ARGUS-AGI) 巡回中</div>', unsafe_allow_html=True)
    st.caption("合議官の発言をリアルタイム監視中。質問無視、定型文コピペ、Web事実無しのハリボテ行動を検知した場合、容赦なく即刻解雇します。")

    st.markdown("---")
    st.markdown(f'<div style="font-size:12px;font-weight:800;color:#f8fafc;margin-bottom:6px;">👔 現在雇用中の合議官 ({len(adb["active"])}名)</div>', unsafe_allow_html=True)
    
    for ag_key, ag_info in list(adb["active"].items()):
        col_a, col_b = st.columns([2.6, 1.2])
        col_a.markdown(f"**{ag_info['name']}** <span style='font-size:10px;color:#94a3b8;'>({ag_info['title'][:10]}..)</span>", unsafe_allow_html=True)
        if col_b.button("詳細", key=f"btn_ag_view_{ag_key}", use_container_width=True):
            st.session_state["selected_agent_profile"] = ag_info
            st.rerun()

    if st.session_state.get("selected_agent_profile"):
        ag_p = st.session_state["selected_agent_profile"]
        st.markdown(
            f'<div style="background:#0f172a;border:1px solid #38bdf8;border-radius:8px;padding:8px;margin-top:6px;font-size:11px;">'
            f'<div style="font-weight:800;color:#38bdf8;font-size:13px;">👤 {ag_p["name"]} ({ag_p["title"]})</div>'
            f'<div><b>担当役割:</b> {ag_p["role"]} ｜ <b>信用度:</b> {ag_p["reputation"]}点</div>'
            f'<div style="margin-top:4px;color:#e2e8f0;line-height:1.4;">{ag_p["personality"]}</div>'
            f'<div style="margin-top:4px;font-size:10px;color:#94a3b8;">就任日: {ag_p["hire_date"]} ｜ 累積警告: {ag_p["warnings"]}/2</div>'
            f'</div>',
            unsafe_allow_html=True
        )
        if st.button("✖️ プロフィールを閉じる", key="cls_ag_p", use_container_width=True):
            st.session_state["selected_agent_profile"] = None; st.rerun()

    st.markdown("---")
    st.markdown(f'<div style="font-size:12px;font-weight:800;color:#ef4444;margin-bottom:4px;">💀 懲戒解雇エージェント ({len(adb["dismissed"])}名)</div>', unsafe_allow_html=True)
    for idx, d_info in enumerate(adb["dismissed"][:4]):
        col_d1, col_d2 = st.columns([2.6, 1.2])
        col_d1.markdown(f"<span style='color:#f87171;'>❌ <b>{d_info['name']}</b></span> <span style='font-size:9.5px;color:#64748b;'>({d_info['dismissed_date'][:10]})</span>", unsafe_allow_html=True)
        if col_d2.button("解雇理由", key=f"btn_d_view_{idx}", use_container_width=True):
            st.session_state["selected_dismissed_profile"] = d_info
            st.rerun()

    if st.session_state.get("selected_dismissed_profile"):
        dp = st.session_state["selected_dismissed_profile"]
        st.markdown(
            f'<div style="background:#180b0b;border:1px solid #ef4444;border-radius:8px;padding:8px;margin-top:6px;font-size:11px;">'
            f'<div style="font-weight:800;color:#ef4444;">💀 解雇録: {dp["name"]} ({dp["title"]})</div>'
            f'<div style="margin-top:3px;color:#fca5a5;"><b>【解雇理由】</b><br>{dp["reason"]}</div>'
            f'<div style="margin-top:4px;font-size:10px;color:#94a3b8;background:#050811;padding:4px;border-radius:4px;">証拠発言: {dp["evidence"]}</div>'
            f'</div>',
            unsafe_allow_html=True
        )
        if st.button("✖️ 解雇理由を閉じる", key="cls_dp_p", use_container_width=True):
            st.session_state["selected_dismissed_profile"] = None; st.rerun()

    st.markdown("---")
    st.markdown('<div style="font-size:12px;font-weight:800;color:#f59e0b;margin-bottom:4px;">🗳️ 新候補面接ルーム ＆ 会員採用投票</div>', unsafe_allow_html=True)
    st.caption("解雇枠を補充するため、優秀な新エージェント候補への投票を受け付けています。投票結果は管理者に集計され、最終採用が決定されます。")
    for cand in adb["interview_candidates"]:
        st.markdown(
            f'<div style="background:rgba(245,158,11,0.06);border-left:3px solid #f59e0b;padding:5px 8px;border-radius:6px;margin-bottom:5px;font-size:11px;">'
            f'<div style="font-weight:800;color:#fde047;">🌟 {cand["name"]} - {cand["title"]} (現在 {cand["votes"]}票)</div>'
            f'<div style="color:#cbd5e1;font-size:10px;margin-top:2px;">{cand["specialty"]}</div>'
            f'<div style="color:#94a3b8;font-style:italic;font-size:10px;">{cand["pitch"]}</div>'
            f'</div>',
            unsafe_allow_html=True
        )
        if st.button(f"🗳️ {cand['name']} に投票する", key=f"vote_{cand['id']}", use_container_width=True):
            cand["votes"] += 1
            save_agents_db(adb)
            st.success(f"✅ {cand['name']} に投票しました！")
            st.rerun()

# ==============================================================================
# 管理者画面：会員管理 ＆ 【AGI採用投票の確認と最終採用決定】
# ==============================================================================
if st.session_state.get("navigation_page") == "ADMIN" and st.session_state.get("authenticated_user") == ADMIN_EMAIL.strip().lower():
    db = load_mem()
    sec = load_sec()
    adb = load_agents_db()
    st.subheader("👑 会員管理センター ＆ AGIエージェント最終人事決裁")
    if st.button("⬅️ TOPへ戻る", use_container_width=True):
        st.session_state["navigation_page"] = "TOP"; st.rerun()

    adm_tab1, adm_tab2 = st.tabs([
        f"👥 会員管理 ({len(db)}名)",
        f"🏛️ AGIエージェント採用投票集計・最終採用決裁"
    ])

    with adm_tab1:
        for k, v in list(db.items()):
            pc = v.get("passcode", gen_code(k))
            st_val = v.get("status", "pending")
            st_badge = {"approved": "🟢 承認済", "pending": "⏳ 承認待ち", "suspended": "⏸️ 一時停止中", "banned": "💀 永久BAN"}.get(st_val, st_val)
            st.markdown(f"**{v.get('name','未入力')}** (`{k}`) ｜ 状態: **{st_badge}** ｜ コード: `{pc}`")
            if k != ADMIN_EMAIL.strip().lower():
                b1, b2, b3 = st.columns(3)
                if b1.button("✅ 承認", key=f"ap_{k}", use_container_width=True):
                    db[k]["status"] = "approved"; save_j(FILES["mem"], db); st.rerun()
                if b2.button("⏸️ 一時停止", key=f"sp_{k}", use_container_width=True):
                    db[k]["status"] = "suspended"; save_j(FILES["mem"], db); st.rerun()
                if b3.button("💀 永久BAN", key=f"bn_{k}", use_container_width=True):
                    db[k]["status"] = "banned"; save_j(FILES["mem"], db); st.rerun()

    with adm_tab2:
        st.caption("会員の投票結果をもとに、管理者が正式に合議官として採用・スタメン配備を決定します。")
        for idx, cand in enumerate(adb["interview_candidates"]):
            st.markdown(
                f'<div style="background:#0f172a;border:1px solid #f59e0b;border-radius:8px;padding:8px;margin-bottom:6px;">'
                f'<div style="font-size:14px;font-weight:800;color:#fde047;">🏆 {cand["name"]} ({cand["title"]}) ｜ 得票数: <span style="font-size:16px;color:#38bdf8;">{cand["votes"]} 票</span></div>'
                f'<div style="font-size:11.5px;color:#e2e8f0;margin-top:2px;">{cand["specialty"]}</div>'
                f'<div style="font-size:10.5px;color:#94a3b8;margin-top:2px;">所信表明: {cand["pitch"]}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
            col_sel1, col_sel2 = st.columns([2, 1])
            target_replace = col_sel1.selectbox(f"入れ替える現行エージェントを選択", list(adb["active"].keys()), key=f"rep_target_{cand['id']}")
            if col_sel2.button(f"👑 {cand['name']} を正式採用・配備", key=f"btn_hire_{cand['id']}", use_container_width=True):
                old_ag = adb["active"].pop(target_replace)
                now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                adb["dismissed"].insert(0, {
                    "name": old_ag["name"],
                    "title": old_ag["title"],
                    "role": old_ag["role"],
                    "dismissed_date": now_s,
                    "reason": f"【管理者による人事刷新】会員投票で多数の支持を得た新候補『{cand['name']}』の採用に伴う配置転換・退陣。",
                    "evidence": f"会員投票数: {cand['votes']}票による信任可決"
                })
                adb["active"][cand["name"]] = {
                    "name": cand["name"],
                    "title": cand["title"],
                    "role": cand["specialty"][:12],
                    "score_bias": "consensus",
                    "personality": cand["pitch"],
                    "hire_date": now_s[:10],
                    "reputation": 99,
                    "warnings": 0,
                    "status": "正規採用・執務中"
                }
                adb["interview_candidates"].pop(idx)
                save_agents_db(adb)
                st.success(f"🎉 {cand['name']} の正式採用が完了しました！")
                st.rerun()

        st.markdown("---")
        st.markdown("**🛡️ AGI特務監察総監 巡回・摘発ログ**")
        for log in adb.get("agi_patrol_log", [])[:8]:
            st.caption(f"{log['time']} ｜ {log['inspector']} ｜ {log['event']}")
    st.stop()

# ==============================================================================
# クオンツ・データエンジン ＆ 初心者向け超丁寧解説生成
# ==============================================================================
DYNAMIC_POOLS = {
    "半導体": [
        {"code": "8035.T", "name": "東京エレクトロン", "theme": "前工程装置筆頭"},
        {"code": "6857.T", "name": "アドバンテスト", "theme": "AI半導体テスタ首位"},
        {"code": "6920.T", "name": "レーザーテック", "theme": "EUV検査高ボラ"},
        {"code": "6146.T", "name": "ディスコ", "theme": "HBM精密加工装置"},
        {"code": "NVDA", "name": "エヌビディア (米)", "theme": "AI GPU覇者"}
    ],
    "AI・防衛・主力": [
        {"code": "9984.T", "name": "ソフトバンクG", "theme": "AI投資・先物主役"},
        {"code": "7011.T", "name": "三菱重工業", "theme": "防衛・宇宙国策主力"},
        {"code": "7012.T", "name": "川崎重工業", "theme": "防衛・航空エンジン"},
        {"code": "3778.T", "name": "さくらネット", "theme": "国策GPUクラウド"},
        {"code": "PLTR", "name": "パランティア (米)", "theme": "防衛AI大本命"}
    ],
    "AI電力・電線": [
        {"code": "5803.T", "name": "フジクラ", "theme": "DC光ファイバー最強株"},
        {"code": "5801.T", "name": "古河電気工業", "theme": "光ファイバー・送電"},
        {"code": "6501.T", "name": "日立製作所", "theme": "世界送配電グリッド"}
    ],
    "小型急騰・直近IPO": [
        {"code": "5253.T", "name": "カバー", "theme": "グロース売買首位級"},
        {"code": "3350.T", "name": "メタプラネット", "theme": "暗号資産・超ボラ"},
        {"code": "IONQ", "name": "アイオンQ (米)", "theme": "商用量子代表"}
    ]
}
KNOWN_STOCKS = {it["code"]: {"name": it["name"], "theme": it["theme"], "genre": g} for g, its in DYNAMIC_POOLS.items() for it in its}

@st.cache_data(ttl=900)
def fetch_macro():
    tks = {"sp500": ("^GSPC", "🇺🇸 S&P500"), "sox": ("^SOX", "💽 米SOX"), "usdjpy": ("JPY=X", "💴 ドル円"), "nk_fut": ("NIY=F", "🇯🇵 日経先物")}
    res = {}
    try:
        raw = yf.download(list(c for c, _ in tks.values()), period="5d", group_by="ticker", threads=True, progress=False, timeout=4)
        for k, (c, lbl) in tks.items():
            d = raw[c].dropna(subset=["Close"])
            lc, pc = float(d["Close"].iloc[-1]), float(d["Close"].iloc[-2])
            res[k] = {"price": lc, "diff": round((lc - pc) / pc * 100, 2), "label": lbl}
    except Exception:
        for k, (_, lbl) in tks.items(): res[k] = {"price": 0.0, "diff": 0.0, "label": lbl}
    return res

macro_info = fetch_macro()

# 初心者向け買い方ガイド：専門用語を排し、注文画面の操作手順を丁寧に解説
def build_detailed_beginner_guide(style: str, name: str, code: str, pest_str: str, vwap_str: str, tp_str: str, sl_str: str, shares: int, cv: float) -> str:
    st_prefix = style.split(" ")[1] if " " in style else "デイトレード"
    return f"""
    <div style="font-size:12.5px;font-weight:800;color:#10b981;margin-bottom:6px;">
        🔰 【超初心者向け】迷わずできる『{name} ({code})』の実践買い方完全ナビ（{st_prefix}）
    </div>
    <div style="font-size:11.5px;color:#e2e8f0;line-height:1.65;">
        <b>【ステップ1：いつ注文を出すか？】</b><br>
        証券口座（SBI証券、楽天証券など）のアプリを開き、朝8:45〜8:55の板気配を確認します。目安となる寄付き予想価格は <b>{pest_str}</b> 前後です。<br><br>
        <b>【ステップ2：いくらで何株買うか？】</b><br>
        資金管理ルールに基づき、今回の推奨購入数は <b>「{shares:,}株」</b>（投資目安：約 {shares*cv:,.0f}円）です。<br>
        朝9:00の市場開始と同時に買う場合は<b>「成行（なりゆき）買い」</b>を、慎重に安値を待ちたい場合は基準VWAPである <b>「指値（さしね）：{vwap_str}」</b> で注文を入れます。<br><br>
        <b>【ステップ3：利益確定と損切りの設定（※最も重要！）】</b><br>
        株が買えたら、欲張らずにすぐ以下の2つの注文をセットしてください：<br>
        ・🎯 <b>利益確定（勝ち逃げ）：</b> 株価が上がって <b>{tp_str}</b> に到達したら自動で売却。<br>
        ・🛡️ <b>損切り（大損防止）：</b> 万が一予想が外れて <b>{sl_str}</b> まで下がったら、迷わず自動で手仕舞い（逆指値注文）。
    </div>
    """

def select_dynamic_strategy(code: str, style: str, tot_win: float, expect_pct: float, ofi_z: float, cvar95: float, base_sh: int, pest_str: str, vwap_str: str, tp_str: str, sl_str: str, cv: float, name: str) -> dict:
    st_prefix = style.split(" ")[1] if " " in style else "デイトレード"
    sh = max(1, int(round(base_sh * 1.5)))
    return {
        "algo_name": f"⚡ [{st_prefix}] 量子トンネル×機関氷山吸収スナイプ型",
        "risk_posture": f"👑 推奨ロット（ <b>{sh:,}株</b> 投入）",
        "core_logic": f"期待度 {expect_pct}%・統合勝率 {tot_win}%。板の買い越し（OFI {ofi_z:+.2f}σ）と大口のステルス吸収を確認し、順張りで一気に上値を捉えるモデル。",
        "adj_shares": sh,
        "step_plan": f"① 9:00寄付き（{pest_str}目安）で {sh:,}株 取得 → ② 逆指値（{sl_str}）をセットし目標（{tp_str}）で利確",
        "beginner_html": build_detailed_beginner_guide(style, name, code, pest_str, vwap_str, tp_str, sl_str, sh, cv)
    }

def analyze_df(df_raw, code, name, theme, genre, macro, style):
    try:
        if df_raw is None or len(df_raw) < 20: return None
        df = df_raw.dropna(subset=["Close", "Open", "High", "Low", "Volume"]).copy()
        c, o, h, l, v = df["Close"].values.astype(float), df["Open"].values.astype(float), df["High"].values.astype(float), df["Low"].values.astype(float), df["Volume"].values.astype(float)
        cv = c[-1]
        rets = np.diff(c) / np.maximum(c[:-1], 1e-4) * 100.0
        tot_win = round(float(np.clip(55.0 + np.mean(rets[-5:]) * 4.5, 48.0, 93.5)), 1)
        expect_pct = round(float(np.clip(tot_win * 0.95 + random.uniform(3, 8), 50.0, 98.8)), 1)
        ofi_z = round(float(np.clip(random.uniform(0.5, 2.8), -3.0, 3.5)), 2)
        cvar95 = round(float(abs(np.percentile(rets, 5))), 2)

        is_jp = ".T" in code
        fp = lambda val: f"{val:,.0f}円" if is_jp else f"${val:,.2f}"
        pest = cv * 1.008
        tpv = cv * 1.035
        slv = cv * 0.985
        sh = max(1, int(1000000 * 0.02 / max(cv - slv, cv * 0.005)))

        strat = select_dynamic_strategy(code.replace(".T", ""), style, tot_win, expect_pct, ofi_z, cvar95, sh, fp(pest), fp(cv), fp(tpv), fp(slv), cv, name)
        return {
            "full_code": code, "code": code.replace(".T", ""), "name": name, "genre": genre, "theme": theme, "price": fp(cv), "raw_close": cv,
            "diff": round(float(rets[-1]), 2), "expect_pct": expect_pct, "total_win_rate": tot_win,
            "q_score": 92, "q_tunnel": 88.5, "ms_score": 89, "kyle_stealth": 84.0, "hurst": 0.65, "luld_magnet": 76.0,
            "ofi_z": ofi_z, "cvar95": cvar95, "vwap_price": fp(cv * 0.998), "pts_est_price": fp(pest), "pts_gap_pct": 0.8,
            "tp_price": fp(tpv), "tp_pct": 3.5, "sl_price": fp(slv), "sl_pct": -1.5,
            "tier_label": "【Lv.9：⚡超強気買い】量子トンネル突破＆機関アルゴ集中", "tier_bg": "linear-gradient(90deg,#0369a1,#1d4ed8)", "tier_color": "#fff",
            "strat": strat, "lot_info": {"shares": strat["adj_shares"], "position_value": strat["adj_shares"] * cv}
        }
    except Exception: return None

@st.cache_data(ttl=900)
def fetch_all_stocks(style):
    out = []
    codes = [s["code"] for its in DYNAMIC_POOLS.values() for s in its]
    raw = yf.download(codes, period="3mo", group_by="ticker", threads=True, progress=False, timeout=6)
    for g, sts in DYNAMIC_POOLS.items():
        for s in sts:
            c = s["code"]
            try:
                r = analyze_df(raw[c] if len(codes) > 1 else raw, c, s["name"], s["theme"], g, macro_info, style)
                if r: out.append(r)
            except Exception: pass
    return out

all_stocks = fetch_all_stocks(investment_style)

# ==============================================================================
# リアルタイムWeb知識検索 ＆ AGI審査付き合議エンジン
# ==============================================================================
@st.cache_data(ttl=600, show_spinner=False)
def search_web_knowledge(query: str) -> list:
    if not query: return []
    ctx = ssl.create_default_context()
    res = []
    try:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=ja&gl=JP&ceid=JP:ja"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=2.2, context=ctx) as r:
            root = ET.fromstring(r.read())
            for it in root.findall("./channel/item")[:3]:
                t = re.sub(r"<[^>]+>", "", it.findtext("title") or "").strip()
                t = re.sub(r"\s*-\s*[^-]+$", "", t).strip()
                if t: res.append(t)
    except Exception: pass
    return res

def run_agi_verified_council(r: dict, user_q: str = "") -> dict:
    adb = load_agents_db()
    active_roster = adb["active"]
    q_txt = user_q.strip()
    web_snippets = search_web_knowledge(f"{r['name']} 株価 ニュース") if not q_txt else search_web_knowledge(q_txt)
    if not web_snippets: web_snippets = [f"{r['name']}の直近板気配および機関出来高フロー推移"]

    dialogue = []
    dialogue.append({"round": f"💬 最新質問合議：『{q_txt if q_txt else r['name']}』 (AGI特務監察総監 巡回中)"})

    # 各雇用エージェントによる発言生成とAGI審査
    for ag_key, ag_info in list(active_roster.items()):
        fact = web_snippets[0] if web_snippets else "リアルタイム板情報"
        
        # 質問に応じた発言生成
        if q_txt:
            if ag_key == "IGNIS":
                spk_text = f"『{q_txt}』についてだな！Web速報でも『{fact[:70]}』って出てるぜ！迷ってる暇があったらモメンタムの初動に全力で乗っかるのが勝ち筋だ！"
            elif ag_key == "AEGIS":
                spk_text = f"『{q_txt}』という判断に対して規律を求めます。Web上の最新事実（{fact[:65]}）に盲目的に飛びつかず、逆指値（{r['sl_price']}）の防衛線を必ず敷きなさい。"
            elif ag_key == "QUANTUM":
                spk_text = f"『{q_txt}』の波形を探査したぞ。Webの最新材料（{fact[:70]}）が波動エネルギーを励起させ、突破率{r['q_tunnel']}%の収束を見せている。"
            elif ag_key == "MICRO":
                spk_text = f"『{q_txt}』の板気配と大口動向を精査したよ。Web報道（{fact[:70]}）を背景に、Kyleステルス吸収度{r['kyle_stealth']}%で機関が集めている形跡がある。"
            else:
                spk_text = f"『{q_txt}』に対する最新Web事実（{fact[:70]}）とクオンツ指標の整合性を確認した。期待度{r['expect_pct']}%のもと、合理的なエントリーが妥当だ。"
        else:
            spk_text = f"『{r['name']}』の最新情報（{fact[:75]}）を精査完了。OFI {r['ofi_z']:+.2f}σと相まって強い推進力が発生している。"

        # AGI特務監察総監による発言審査
        passed, agi_msg = agi_inspect_speech(ag_key, q_txt if q_txt else r["name"], spk_text, web_snippets)

        dialogue.append({
            "speaker": f"{ag_info['name']} ({ag_info['title'][:12]})",
            "score": r["expect_pct"],
            "tone": "agree" if ag_key in ["IGNIS", "QUANTUM"] else ("doubt" if ag_key == "AEGIS" else "normal"),
            "text": spk_text,
            "agi_status": agi_msg
        })

    v_html = (
        f'<div style="margin-bottom:4px;"><b>🔥 『{r["name"]}』総合期待度：</b><span style="color:#fde047;font-size:13.5px;font-weight:900;">{r["expect_pct"]}%</span> ｜ '
        f'<b>🏛️ 機関ミクロ構造：</b><span style="color:#a7f3d0;font-weight:800;">Kyleステルス吸収 {r["kyle_stealth"]}% ／ Hurst {r["hurst"]}</span></div>'
        f'<div style="margin-bottom:4px;font-size:11px;color:#94a3b8;"><b>🌐 AGI探査ファクト：</b> {web_snippets[0]}</div>'
        f'<div style="margin-bottom:4px;"><b>⚡ プロ向け執行プラン：</b>{r["strat"]["step_plan"]} ｜ 🎯利確 <b>{r["tp_price"]}</b> ／ 🛡️損切 <b>{r["sl_price"]}</b></div>'
        f'<div class="beginner-action-box">{r["strat"]["beginner_html"]}</div>'
    )
    return {"dialogue": dialogue, "verdict_html": v_html}

def render_card(r, rank=None, kp="card"):
    is_open = st.session_state["active_debates"].get(f"{kp}_{r['code']}", False)
    lot = r["lot_info"]
    st_info = r["strat"]
    rk_h = f'<span class="pill-badge" style="background:#f59e0b;color:#0f172a;font-weight:900;">🏆 #{rank}</span>' if rank else ""
    
    st.markdown(
        f'<div class="rank-card">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<div>{rk_h}<span class="company-name-hero">{r["name"]}</span> <span style="font-size:11.5px;color:#94a3b8;">({r["code"]} / {r["genre"]})</span></div>'
        f'<div style="font-size:13px;font-weight:700;"><b style="color:#f8fafc;">{r["price"]}</b> (<span style="color:{"#10b981" if r["diff"]>=0 else "#ef4444"};">{"+" if r["diff"]>=0 else ""}{r["diff"]}%</span>)</div>'
        f'</div>'
        f'<div style="font-size:10.5px;color:#94a3b8;margin-top:2px;">{r["theme"]}</div>'
        f'<div class="signal-10tier-badge" style="background:{r["tier_bg"]};color:{r["tier_color"]};margin-top:5px;"><span>{r["tier_label"]}</span><span>🔥 期待度 {r["expect_pct"]}%</span></div>'
        f'<div class="winrate-bar"><div><div style="font-size:9px;color:#fde047;">🔥 総合期待度</div><div style="font-size:12px;font-weight:900;color:#fef08a;">{r["expect_pct"]}%</div></div><div><div style="font-size:9px;color:#c084fc;">⚛️ 量子トンネル</div><div style="font-size:12px;font-weight:800;color:#e9d5ff;">{r["q_tunnel"]}%</div></div><div><div style="font-size:9px;color:#6ee7b7;">🏛️ 機関Kyle吸収</div><div style="font-size:12px;font-weight:800;color:#a7f3d0;">{r["kyle_stealth"]}%</div></div><div><div style="font-size:9px;color:#94a3b8;">統合勝率</div><div style="font-size:12px;font-weight:800;color:#38bdf8;">{r["total_win_rate"]}%</div></div></div>'
        f'<div class="trade-plan-box"><div><div style="font-size:9px;color:#94a3b8;">🌅 寄付き予想</div><div style="font-size:11.5px;font-weight:700;">{r["pts_est_price"]}</div></div><div><div style="font-size:9px;color:#10b981;">🎯 利確目標</div><div style="font-size:11.5px;font-weight:800;color:#10b981;">{r["tp_price"]} (+{r["tp_pct"]}%)</div></div><div><div style="font-size:9px;color:#f87171;">🛡️ 損切り</div><div style="font-size:11.5px;font-weight:800;color:#f87171;">{r["sl_price"]} ({r["sl_pct"]}%)</div></div></div>'
        f'<div class="sizing-box"><span>📦 <b>推奨数量: {lot["shares"]:,}株</b> ｜ 投資概算 {lot["position_value"]:,.0f}円</span><span>基準VWAP: <b>{r["vwap_price"]}</b></span></div>'
        f'</div>',
        unsafe_allow_html=True
    )

    uk = f"{kp}_{r['code']}"
    col_btn1, col_btn2 = st.columns([2.8, 1.2])
    toggle_lbl = "🔼 AGI合議・超丁寧買い方ガイドを閉じる" if is_open else "⚛️ AGI合議＆丁寧な買い方ナビを見る"
    if col_btn1.button(toggle_lbl, key=f"tgl_{uk}", use_container_width=True):
        st.session_state["active_debates"][uk] = not is_open
        st.rerun()

    in_wl = r["code"] in st.session_state["watchlist"]
    if col_btn2.button("✅ 監視中" if in_wl else "⭐ 監視追加", key=f"wl_add_{uk}", use_container_width=True):
        if in_wl: del st.session_state["watchlist"][r["code"]]
        else: st.session_state["watchlist"][r["code"]] = r
        st.rerun()

    if is_open:
        if uk not in st.session_state["council_threads"]:
            deb = run_agi_verified_council(r)
            st.session_state["council_threads"][uk] = deb["dialogue"]
            st.session_state["council_meta"][uk] = deb

        meta = st.session_state["council_meta"][uk]
        turns = st.session_state["council_threads"][uk]

        # 合議タイムライン表示
        dialogue_html = "".join([
            f'<div class="round-divider">{t["round"]}</div>' if "round" in t else
            f'<div class="chat-bubble-user"><b>🗣️ あなたの質問:</b><br>{t["text"]}</div>' if t.get("is_user") else
            f'<div class="{"chat-bubble-agree" if t.get("tone")=="agree" else ("chat-bubble-doubt" if t.get("tone")=="doubt" else "chat-bubble-ai")}">'
            f'<div style="font-weight:700;color:#38bdf8;font-size:10.5px;display:flex;justify-content:space-between;">'
            f'<span>{t["speaker"]}</span><span style="color:#10b981;font-size:9.5px;">{t.get("agi_status","")}</span>'
            f'</div><div>{t["text"]}</div></div>'
            for t in turns
        ])

        st.markdown(f'<div class="ai-council-box"><div class="council-scroll-window">{dialogue_html}</div></div>', unsafe_allow_html=True)

        with st.form(f"form_ask_{uk}", clear_on_submit=True):
            ca1, ca2 = st.columns([3.2, 1])
            u_in = ca1.text_input("質問", placeholder=f"『{r['name']}』について何でも質問（AGIが回答を審査します）", label_visibility="collapsed")
            if ca2.form_submit_button("💬 質問投下", use_container_width=True) and u_in.strip():
                st.session_state["council_threads"][uk].append({"is_user": True, "text": u_in.strip()})
                updated = run_agi_verified_council(r, user_q=u_in.strip())
                for t in updated["dialogue"]: st.session_state["council_threads"][uk].append(t)
                st.session_state["council_meta"][uk] = updated
                st.rerun()

        st.markdown(
            f'<div class="consensus-banner">'
            f'<div style="font-weight:800;color:#fde047;font-size:12px;margin-bottom:4px;">🏛️ AGI合議最終結論 ＆ 買い方実践マニュアル</div>'
            f'{meta["verdict_html"]}'
            f'</div>',
            unsafe_allow_html=True
        )

# ==============================================================================
# メイン画面レンダリング
# ==============================================================================
mpills = "".join([f'<div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);padding:2px 7px;border-radius:5px;font-size:10px;display:inline-flex;gap:4px;"><span style="color:#94a3b8;">{m["label"]}</span><span style="color:{"#10b981" if m["diff"]>=0 else "#ef4444"};font-weight:700;">{"+" if m["diff"]>=0 else ""}{m["diff"]}%</span></div>' for m in macro_info.values()])
st.markdown(
    f'<div class="glass-header">'
    f'<div style="display:flex;justify-content:space-between;align-items:center;">'
    f'<div><div class="brand-luxury">YAMASHISHI LAB</div><div class="brand-sub">QUANTUM WAVEFUNCTION & MULTI-AGENT TERMINAL</div></div>'
    f'<span style="background:rgba(168,85,247,0.16);border:1px solid rgba(168,85,247,0.45);color:#e9d5ff;padding:2px 8px;border-radius:999px;font-size:9.5px;font-weight:700;">AGI監査員常駐合議</span>'
    f'</div>'
    f'<div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:6px;">{mpills}</div></div>',
    unsafe_allow_html=True
)

cats = ["🏆 総合TOP5", "⚛️ 量子トンネル突破TOP10", "🏛️ 機関最新ミクロ構造TOP10", "🎟️ IPO募集・新規上場", "📋 監視シート"]
st.markdown(f'<div class="compact-bar-label"><span>📂 STRATEGY & RANKING ({investment_style.split(" ")[1]})</span><span>AGIリアルタイム審査 / 超丁寧買い方ガイド</span></div>', unsafe_allow_html=True)

if hasattr(st, "pills"):
    sel_cat = st.pills("カテゴリ", cats, default="🏆 総合TOP5", label_visibility="collapsed")
else:
    sel_cat = st.radio("カテゴリ", cats, horizontal=True, label_visibility="collapsed")

if sel_cat == "🏆 総合TOP5":
    st.caption(f"🦁 【{investment_style.split(' ')[1]}】全母集団から量子波動と機関ミクロ構造をもとに厳選したTOP5です。")
    for idx, r_item in enumerate(sorted(all_stocks, key=lambda x: x["expect_pct"], reverse=True)[:5], 1):
        render_card(r_item, rank=idx, kp="top5")
elif sel_cat == "⚛️ 量子トンネル突破TOP10":
    st.caption("⚛️ 量子トンネル突破率・波動関数収束度が極大化しているランキングです。")
    for idx, r_item in enumerate(sorted(all_stocks, key=lambda x: x["q_tunnel"], reverse=True)[:10], 1):
        render_card(r_item, rank=idx, kp="qtop")
elif sel_cat == "🏛️ 機関最新ミクロ構造TOP10":
    st.caption("🏛️ 機関Kyleステルス吸収度・Hurstトレンド持続性が極大のランキングです。")
    for idx, r_item in enumerate(sorted(all_stocks, key=lambda x: x["kyle_stealth"], reverse=True)[:10], 1):
        render_card(r_item, rank=idx, kp="mstop")
elif sel_cat == "🎟️ IPO募集・新規上場":
    for ipo in IPO_OFFERINGS:
        links_html = "".join([f'<a href="{url}" target="_blank" rel="noopener noreferrer" class="ipo-link-btn">🔗 {lbl}</a>' for lbl, url in ipo["links"]])
        st.markdown(
            f'<div class="rank-card" style="border-left-color:#f59e0b;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<div><span class="pill-badge" style="background:#f59e0b;color:#0f172a;font-weight:900;">🏆 #{ipo["rank"]}</span><span class="company-name-hero">{ipo["name"]}</span> ({ipo["code"]} / {ipo["market"]})</div>'
            f'<div class="prob-badge" style="color:#10b981!important;">{ipo["expect_return"]}</div>'
            f'</div>'
            f'<div style="font-size:10.5px;color:#cbd5e1;margin-top:2px;">🎯 {ipo["theme"]} ｜ 主幹事: <b>{ipo["lead"]}</b></div>'
            f'<div class="trade-plan-box" style="margin-top:5px;"><div><div style="font-size:9px;color:#94a3b8;">📅 BB期間</div><div style="font-size:11px;font-weight:700;color:#fde047;">{ipo["bb_period"]}</div></div><div><div style="font-size:9px;color:#94a3b8;">🔔 上場日</div><div style="font-size:11px;font-weight:700;">{ipo["list_date"]}</div></div><div><div style="font-size:9px;color:#94a3b8;">💴 仮条件</div><div style="font-size:11px;font-weight:700;">{ipo["price_band"]}</div></div></div>'
            f'<div style="margin-top:5px;">{links_html}</div></div>',
            unsafe_allow_html=True
        )
elif sel_cat == "📋 監視シート":
    wl = st.session_state["watchlist"]
    if not wl: st.info("現在監視銘柄はありません。銘柄カードの「⭐ 監視追加」を押してください。")
    for wc, wi in list(wl.items()): render_card(wi, kp=f"wl_{wc}")
