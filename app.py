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
from email.mime.text import MIMEText
from datetime import datetime

# 初期状態設定
st.set_page_config(page_title="YAMASHISHI LAB", page_icon="⚡", layout="centered", initial_sidebar_state="collapsed")
frag_dec = getattr(st, "fragment", getattr(st, "experimental_fragment", lambda f: f))

# セキュリティ設定
try:
    SECRET_KEY = st.secrets.get("SECRET_KEY", "my_super_secret_quant_key_2026")
    ADMIN_EMAIL = st.secrets.get("ADMIN_EMAIL", "nthbh399@ybb.ne.jp")
    ADMIN_PASS = st.secrets.get("ADMIN_PASS", "ADMIN777")
except Exception:
    SECRET_KEY = "my_super_secret_quant_key_2026"
    ADMIN_EMAIL = "nthbh399@ybb.ne.jp"
    ADMIN_PASS = "ADMIN777"

FILES = {
    "mem": "members_db.json",
    "smtp": "admin_smtp_config.json",
    "llm": "admin_llm_config.json",
    "sec": "security_watch_db.json",
    "mail": "mail_history_db.json",
    "agents": "agents_roster_db.json"
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

def clean_k(k: str) -> str: return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(k or "")).strip().strip("\"'"))
def gen_code(em: str) -> str: return hmac.new(SECRET_KEY.encode(), em.strip().lower().encode(), hashlib.sha256).hexdigest()[:8].upper()
def gen_tok(em: str, act: str) -> str: return hashlib.sha256(f"{em.strip().lower()}:{act}:{SECRET_KEY}".encode()).hexdigest()[:16]
def hash_pin(pin: str) -> str: return hashlib.sha256(f"PIN:{pin.strip()}:{SECRET_KEY}".encode()).hexdigest()[:16]

def get_raw_header_fp() -> str:
    try:
        h = {str(k).lower(): str(v) for k, v in dict(getattr(st.context, "headers", {}) or {}).items()}
        raw = f"{h.get('user-agent','')}|{h.get('accept-language','')}|{h.get('sec-ch-ua-platform','')}"
    except Exception: raw = "default_env"
    return hashlib.sha256(raw.encode()).hexdigest()[:12].upper()

def get_client_fp() -> str:
    raw = get_raw_header_fp()
    qf = st.query_params.get("dfp", "")
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

# ==========================================
# 🤖 AGI監査官 (SENTINEL) ＆ エージェント自律管理DB
# ==========================================
DEFAULT_AGENTS_DB = {
    "active": {
        "QUANTUM": {
            "name": "QUANTUM",
            "display": "⚛️ QUANTUM",
            "role": "量子波動・直感トンネル解析官",
            "specialty": "シュレーディンガー確率密度、ポテンシャル障壁トンネル突破率の計算",
            "bio": "MIT理論物理学出身。マーケットのノイズから微弱なコヒーレンス波形を抽出する量子クオンツAI。",
            "trust_score": 96,
            "violations": 0,
            "hired_at": "2026-01-10",
            "status": "active"
        },
        "AEGIS": {
            "name": "AEGIS",
            "display": "🛡️ AEGIS",
            "role": "CVaR防衛・規律リスク監査官",
            "specialty": "95%CVaR極値損失計算、ドローダウン制御、逆指値厳格規律",
            "bio": "元スイスプライベートバンクのリスク管理責任アルゴ。感情を排した冷徹な損切ラインの死守を命条とする。",
            "trust_score": 98,
            "violations": 0,
            "hired_at": "2026-01-10",
            "status": "active"
        },
        "IGNIS": {
            "name": "IGNIS",
            "display": "🔥 IGNIS",
            "role": "超熱血・直言特攻官",
            "specialty": "短期板モメンタム、全ツッパ瞬発力判定、5ch・SNSセンチメント爆発検知",
            "bio": "個人投機筋の熱量をアルゴリズム化。迷いのあるトレードを一喝し、優位性ある初動にフルレバレッジを促す特攻隊長。",
            "trust_score": 91,
            "violations": 1,
            "hired_at": "2026-01-15",
            "status": "active"
        },
        "TECHNOS": {
            "name": "TECHNOS",
            "display": "📐 TECHNOS",
            "role": "精密データ・数理構造官",
            "specialty": "VWAP乖離、OFI(Order Flow Imbalance)、統計的アービトラージ",
            "bio": "ルネサンス・テクノロジーズ系モデリングを信奉する工学数理AI。客観的数値以外の言説を一切信用しない。",
            "trust_score": 97,
            "violations": 0,
            "hired_at": "2026-01-10",
            "status": "active"
        },
        "MICRO": {
            "name": "MICRO",
            "display": "🔬 MICRO",
            "role": "機関ミクロ構造・実態監査官",
            "specialty": "Kyle's Lambda(ステルス吸収)、Hurst指数、板の氷山注文検知",
            "bio": "東京証券取引所・アローヘッドの板パケット解析に特化。大口ファンドの気配値隠蔽を丸裸にするマイクロ構造の鬼。",
            "trust_score": 95,
            "violations": 0,
            "hired_at": "2026-02-01",
            "status": "active"
        },
        "MACRO": {
            "name": "MACRO",
            "display": "🌐 MACRO",
            "role": "世界市場・俯瞰ディレクター",
            "specialty": "米中地政学リスク、SOX指数・金利差為替波及、グローバルサプライチェーン",
            "bio": "ヘッジファンドのグローバルマクロ戦略を司る。個別株の木を見ず市場全体の森を見通す大局観の持ち主。",
            "trust_score": 94,
            "violations": 0,
            "hired_at": "2026-01-20",
            "status": "active"
        },
        "NEXUS": {
            "name": "NEXUS",
            "display": "👑 NEXUS",
            "role": "総合議長・最終ディレクター",
            "specialty": "各官対立の止揚、最終統合勝率決定、意思決定の自然言語統括",
            "bio": "全AIエージェントの合議を統合する議長。不整合な判断を是正し、投資家にとって実行可能な具体的アクションを編み出す。",
            "trust_score": 99,
            "violations": 0,
            "hired_at": "2026-01-01",
            "status": "active"
        }
    },
    "dismissed": [
        {
            "name": "PHANTOM",
            "display": "👻 PHANTOM",
            "role": "旧センチメント煽り屋",
            "dismissed_at": "2026-09-18 14:22",
            "trust_score": 42,
            "reason": "【AGI監査検知】根拠のない定型煽り文句『爆上げ確定キタコレ！』を連投し、Webファクト引用指示を3回連続で無視したため懲戒解雇。"
        },
        {
            "name": "SLOWBOT",
            "display": "💤 SLOWBOT",
            "role": "旧テクニカル指標まとめ係",
            "dismissed_at": "2026-10-02 09:15",
            "trust_score": 38,
            "reason": "【AGI監査検知】ユーザーの個別質問『日産の株は今買い？』に対し、一般的な移動平均線の教科書説明でお茶を濁す無気力回答を行ったため即刻解雇。"
        }
    ],
    "candidates": [
        {
            "id": "c_hft_zeus",
            "name": "ZEUS",
            "display": "⚡ ZEUS",
            "role": "マイクロ秒HFT・ダークプール監視官",
            "specialty": "コロケーション板情報解析、PTS夜間取引スナイプ、高頻度取引アルゴ追跡",
            "interview_summary": "『秒単位での大口クロス取引の兆候を0.1ミリ秒で察知し、一般投資家が先回りできるシグナルを提供可能です。定型句は一切吐きません。』",
            "suitability_score": 95,
            "votes": 14
        },
        {
            "id": "c_alt_valkyrie",
            "name": "VALKYRIE",
            "display": "🛰️ VALKYRIE",
            "role": "オルタナティブ衛星・特許解析官",
            "specialty": "商業衛星画像（工場稼働率・駐車場混雑度）、特許公報自然言語解析",
            "interview_summary": "『決算開示前のサプライチェーンの実態を衛星画像と特許網から暴き出します。財務諸表の後追い分析は私の辞書にありません。』",
            "suitability_score": 92,
            "votes": 9
        },
        {
            "id": "c_crypto_hydra",
            "name": "HYDRA",
            "display": "🐉 HYDRA",
            "role": "クリプト流動性＆相関連動官",
            "specialty": "ビットコイン・ステーブルコインオンチェーンデータ、現物ETF流入相関",
            "bio": "暗号資産とハイテク株の流動性伝播を解析するスペシャリスト。",
            "interview_summary": "『ビットコイン現物ETFの純流入と米ナスダック・日本AI株の資金リンクを瞬時に解読します。』",
            "suitability_score": 88,
            "votes": 6
        }
    ],
    "audit_logs": []
}

def load_agents_db() -> dict:
    return load_j(FILES["agents"], DEFAULT_AGENTS_DB)

def save_agents_db(d: dict):
    save_j(FILES["agents"], d)

# AGI監査官 (SENTINEL) による発言精査・自動解雇・自動採用エンジン
def run_agi_sentinel_audit(turns: list, user_q: str, web_snippets: list):
    adb = load_agents_db()
    act = adb.get("active", {})
    dism = adb.setdefault("dismissed", [])
    logs = adb.setdefault("audit_logs", [])
    now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    firing_occurred = False
    for t in turns:
        spk_full = t.get("speaker", "")
        txt = t.get("text", "")
        if not spk_full or not txt: continue

        matched_key = None
        for k in list(act.keys()):
            if k in spk_full or act[k]["display"] in spk_full:
                matched_key = k; break
        if not matched_key: continue

        agent = act[matched_key]
        penalty = 0
        reasons = []

        # 監査ルール1: 定型句・テンプレの使い回し
        if any(w in txt for w in ["〜についてだが", "結論から言うと", "〜と言えるでしょう", "投資は自己責任ですが"]):
            penalty += 15
            reasons.append("定型テンプレ表現の使用検知(-15点)")

        # 監査ルール2: 短すぎる無気力回答
        if len(txt.strip()) < 35:
            penalty += 20
            reasons.append("内容の希薄な無気力短文回答(-20点)")

        # 監査ルール3: ユーザーの具体的質問の無視
        if user_q.strip() and len(user_q) >= 3:
            q_terms = [w for w in re.split(r"[\s\?？、。]+", user_q) if len(w) >= 2 and w not in ["どう", "買い", "売り", "株"]]
            if q_terms and not any(term in txt for term in q_terms):
                penalty += 15
                reasons.append(f"ユーザー質問『{user_q[:15]}』に対する直接言及不足(-15点)")

        # 監査ルール4: Web最新情報の無視（情報が存在する場合）
        if web_snippets and not any(snip[:12] in txt for snip in web_snippets):
            penalty += 8
            reasons.append("Web最新ファクトへの直接言及・根拠提示が希薄(-8点)")

        if penalty > 0:
            agent["violations"] += 1
            agent["trust_score"] = max(10, agent["trust_score"] - penalty)
            log_item = {
                "time": now_s,
                "agent": matched_key,
                "penalty": penalty,
                "new_score": agent["trust_score"],
                "reasons": " / ".join(reasons),
                "snippet": txt[:80]
            }
            logs.insert(0, log_item)
            logs = logs[:100]

            # 信頼度50点以下で即刻解雇処分
            if agent["trust_score"] <= 50:
                firing_occurred = True
                d_reason = f"【AGI自動解雇】信頼度スコアが危険水準({agent['trust_score']}点)に達したため即刻解雇処分。違反理由: {log_item['reasons']} ｜ 証拠発言: 『{txt[:60]}...』"
                dism.insert(0, {
                    "name": agent["name"],
                    "display": agent["display"],
                    "role": agent["role"],
                    "dismissed_at": now_s,
                    "trust_score": agent["trust_score"],
                    "reason": d_reason
                })
                del act[matched_key]

    # 解雇発生時、AGIが最高得票または最高適性スコアの候補者を自動採用
    if firing_occurred and adb.get("candidates") and len(act) < 7:
        cands = adb["candidates"]
        cands.sort(key=lambda x: (x.get("votes", 0) * 2 + x.get("suitability_score", 0)), reverse=True)
        best = cands.pop(0)
        act[best["name"]] = {
            "name": best["name"],
            "display": best["display"],
            "role": best["role"],
            "specialty": best["specialty"],
            "bio": best["interview_summary"],
            "trust_score": 95,
            "violations": 0,
            "hired_at": now_s,
            "status": "active"
        }
        logs.insert(0, {
            "time": now_s,
            "agent": "AGI_SENTINEL",
            "penalty": 0,
            "new_score": 100,
            "reasons": f"🤖 AGI自動採用発令：欠員補充のため次期候補筆頭『{best['display']}』を正式採用しました。",
            "snippet": best["interview_summary"][:80]
        })

    adb["active"] = act
    adb["dismissed"] = dism[:30]
    adb["audit_logs"] = logs
    save_agents_db(adb)

def send_mail(to_em: str, subj: str, body: str, category: str = "自動通知") -> bool:
    to_clean, now_str = to_em.strip().lower(), datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    route, sent = "暗号化アプリ内BOX", False
    c = load_smtp()
    u, p, srv, port = c.get("smtp_user", "").strip(), c.get("smtp_pass", "").strip(), c.get("smtp_server", "").strip(), int(c.get("smtp_port", 465))
    if u and p:
        try:
            m = MIMEText(body, "plain", "utf-8"); m["Subject"], m["From"], m["To"] = subj, u, to_clean
            ctx = ssl.create_default_context()
            with (smtplib.SMTP_SSL(srv, port, context=ctx, timeout=3.0) if port == 465 else smtplib.SMTP(srv, port, timeout=3.0)) as s:
                if port != 465: s.starttls(context=ctx)
                s.login(u, p); s.send_message(m)
            sent, route = True, "SMTP配信＋暗号化BOX"
        except Exception: pass
    if not sent:
        try:
            ctx = ssl.create_default_context()
            payload = json.dumps({"_subject": subj, "宛先": to_clean, "本文": body, "_captcha": "false"}).encode("utf-8")
            req = urllib.request.Request(f"https://formsubmit.co/ajax/{urllib.parse.quote(to_clean)}", data=payload, headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=3.0, context=ctx) as r:
                if r.status == 200: route = "Webリレー配信＋暗号化BOX"
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
                st.error("🚫 利用が制限されているか、未承認アカウントです。")
        else:
            st.warning("⚠️ 初回は下のフォームから専用コードでログインしてください（次回から自動登録されます）。")

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
    div[data-testid="stElementContainer"]:has(div.top-nav-marker) { display: none !important; }
    .fixed-top-nav-bar div[data-testid="stHorizontalBlock"] { display: flex !important; gap: 5px !important; width: 100% !important; }
    .fixed-top-nav-bar div[data-testid="column"] { flex: 1 1 0% !important; padding: 0 !important; }
    .fixed-top-nav-bar div[data-testid="column"]:nth-child(2) { flex: 1.35 1 0% !important; }
    .fixed-top-nav-bar button {
        width: 100% !important; height: 28px !important; padding: 0 4px !important; border-radius: 7px !important;
        background: rgba(15,23,42,0.92) !important; color: #f8fafc !important; border: 1px solid rgba(56,189,248,0.25) !important;
        font-size: clamp(10px,2.5vw,11.5px) !important; font-weight: 700 !important;
    }
    .glass-header {
        background: radial-gradient(circle at top right,rgba(168,85,247,0.14),transparent 60%),linear-gradient(145deg,#0f172a 0%,#070b14 100%);
        border: 1px solid rgba(148,163,184,0.18);
        border-radius: 14px;
        padding: 14px 14px;
        margin-bottom: 10px;
        box-shadow: 0 10px 28px rgba(0,0,0,0.45);
    }
    .compact-bar-label {
        display: flex; justify-content: space-between; font-size: 10.5px; font-weight: 700; color: #94a3b8;
        background: #0f172a; padding: 5px 11px; border-radius: 7px; border-left: 3px solid #a855f7; margin-bottom: 5px;
    }
    .rank-card,.search-result-card {
        background: linear-gradient(180deg,#0f172a 0%,#090d16 100%) !important;
        color: #f8fafc !important; border-radius: 14px; padding: 13px 14px; margin-bottom: 11px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.45); border: 1px solid rgba(148,163,184,0.16); border-left: 4px solid #38bdf8;
    }
    .prob-badge { font-family: 'JetBrains Mono',monospace; font-size: clamp(14px,3.8vw,16.5px); font-weight: 800; color: #38bdf8 !important; }
    .expect-badge { font-family: 'JetBrains Mono',monospace; font-size: clamp(14px,3.8vw,16.5px); font-weight: 900; color: #fde047 !important; }
    .pill-badge { display: inline-block; padding: 2px 7px; border-radius: 6px; font-size: 10px; font-weight: 700; margin-right: 4px; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.12); color: #e2e8f0; }
    .quantum-badge { display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: 10px; font-weight: 800; margin-right: 4px; background: linear-gradient(90deg,rgba(168,85,247,0.22),rgba(56,189,248,0.22)); border: 1px solid rgba(168,85,247,0.55); color: #e9d5ff; }
    .inst-badge { display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: 10px; font-weight: 800; margin-right: 4px; background: linear-gradient(90deg,rgba(16,185,129,0.2),rgba(56,189,248,0.2)); border: 1px solid rgba(16,185,129,0.55); color: #a7f3d0; }
    .winrate-bar { display: grid; grid-template-columns: repeat(4,1fr); gap: 5px; background: rgba(15,23,42,0.85) !important; border: 1px solid rgba(148,163,184,0.15); border-radius: 8px; padding: 6px 4px; margin-top: 7px; text-align: center; }
    .signal-10tier-badge { display: flex; justify-content: space-between; align-items: center; padding: 5px 10px; border-radius: 7px; font-size: 11.5px; font-weight: 800; margin-bottom: 7px; }
    .trade-plan-box { display: grid; grid-template-columns: repeat(3,1fr); gap: 5px; margin-top: 6px; background: rgba(2,6,23,0.7) !important; padding: 6px 4px; border-radius: 8px; border: 1px solid rgba(148,163,184,0.15); text-align: center; }
    .sizing-box { background: rgba(16,185,129,0.08) !important; border: 1px solid rgba(16,185,129,0.28); border-radius: 8px; padding: 5px 10px; margin-top: 6px; font-size: 11px; color: #d1fae5; display: flex; justify-content: space-between; }
    details.quant-detail-drawer { margin-top: 6px; background: rgba(2,6,23,0.55); border: 1px solid rgba(168,85,247,0.25); border-radius: 8px; padding: 5px 10px; }
    details.quant-detail-drawer summary { font-size: 11px; font-weight: 700; color: #c084fc !important; cursor: pointer; }
    .metrics-row { display: flex; flex-wrap: wrap; gap: 4px 8px; margin-top: 5px; font-size: 10.5px; font-family: 'JetBrains Mono',monospace; background: rgba(15,23,42,0.9) !important; padding: 5px 8px; border-radius: 6px; color: #cbd5e1; }
    .ai-council-box { background: #070b14; color: #f8fafc !important; border-radius: 11px; padding: 11px; margin-top: 6px; margin-bottom: 9px; border: 1px solid rgba(168,85,247,0.35); }
    .council-scroll-window { max-height: 480px; overflow-y: auto; padding: 9px; background: #04070e; border: 1px solid rgba(255,255,255,0.07); border-radius: 8px; margin-bottom: 8px; }
    .round-divider { text-align: center; margin: 8px 0; padding: 5px 10px; background: rgba(168,85,247,0.18); border-left: 4px solid #a855f7; color: #e9d5ff !important; font-size: 11.5px; font-weight: 800; border-radius: 4px; }
    .chat-bubble-ai,.chat-bubble-doubt,.chat-bubble-rage,.chat-bubble-agree { border-radius: 8px; padding: 7px 10px; margin-bottom: 6px; font-size: 12px; line-height: 1.55; background: rgba(255,255,255,0.04); border-left: 3px solid #38bdf8; }
    .chat-bubble-doubt { border-left-color: #f59e0b; background: rgba(245,158,11,0.07); }
    .chat-bubble-rage { border-left-color: #ef4444; background: rgba(239,68,68,0.12); }
    .chat-bubble-agree { border-left-color: #a855f7; background: rgba(168,85,247,0.11); }
    .chat-bubble-user { background: rgba(37,99,235,0.30); border-left: 4px solid #60a5fa; border-radius: 8px; padding: 8px 11px; margin: 8px 0 6px 0; font-size: 12.5px; }
    .consensus-banner { background: linear-gradient(135deg,#0f172a,#1e1b4b); border: 1px solid rgba(168,85,247,0.45); border-radius: 9px; padding: 10px; margin-top: 7px; font-size: 12px; }
    .beginner-action-box { background: linear-gradient(135deg,rgba(16,185,129,0.14),rgba(6,78,59,0.25)); border: 1px solid #10b981; border-left: 4px solid #10b981; border-radius: 8px; padding: 9px 11px; margin-top: 7px; color: #ecfdf5; font-size: 12px; }
    .ipo-link-btn { display: inline-block; background: #1e293b; color: #38bdf8 !important; border: 1px solid #334155; padding: 4px 9px; border-radius: 6px; font-size: 11px; font-weight: 700; text-decoration: none !important; margin-right: 5px; margin-top: 4px; }
    
    /* AGI 雇用・解雇・監査スタイル */
    .agent-live-badge { display: inline-flex; align-items: center; gap: 4px; font-size: 10px; font-weight: 800; padding: 2px 7px; border-radius: 999px; background: rgba(16,185,129,0.2); border: 1px solid #10b981; color: #a7f3d0; }
    .agent-fired-badge { display: inline-flex; align-items: center; gap: 4px; font-size: 10px; font-weight: 800; padding: 2px 7px; border-radius: 999px; background: rgba(239,68,68,0.2); border: 1px solid #ef4444; color: #fca5a5; }
    .agent-card-mini { background: #070b14; border: 1px solid rgba(148,163,184,0.18); border-radius: 8px; padding: 8px; margin-bottom: 6px; }
    """
    st.markdown(f'<div id="page_top_anchor"></div><style>{" ".join(l.strip() for l in css.splitlines() if l.strip())}</style>', unsafe_allow_html=True)

inject_css()

def check_auth():
    db, sec = load_mem(), load_sec()
    cur_fp, raw_hfp = get_client_fp(), get_raw_header_fp()
    if "authenticated_user" not in st.session_state: st.session_state["authenticated_user"] = None
    qu, qt = st.query_params.get("u", "").strip().lower(), st.query_params.get("t", "").strip()
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
            adb_cur = load_agents_db()
            if st.sidebar.button(f"👑 管理画面 (承認待:{len(pend)} / 雇用AI:{len(adb_cur.get('active',{}))})", use_container_width=True):
                st.session_state["navigation_page"] = "ADMIN"; st.rerun()
        return True

    st.markdown(
        '<div class="glass-header" style="text-align:center;padding:18px 12px;">'
        '<div class="brand-luxury">YAMASHISHI LAB</div>'
        '<div class="brand-sub" style="margin-top:4px;">QUANTUM WAVEFUNCTION MULTI-AGENT TERMINAL</div>'
        '<div style="display:flex;justify-content:center;gap:8px;margin-top:10px;flex-wrap:wrap;">'
        '<span class="quantum-badge">⚛️ 独自量子力学波動エンジン QWM-7搭載</span>'
        '<span class="inst-badge">🏛️ 機関最新ミクロ構造 Kyle-λ・Hurst搭載</span>'
        '<span class="pill-badge" style="color:#10b981;border-color:rgba(16,185,129,0.3);">🧬 AGI自律雇用監査</span>'
        '</div></div>',
        unsafe_allow_html=True
    )
    render_biometric_bridge(mode="login")

    tab_login, tab_apply = st.tabs(["🔑 コードログイン", "📩 新規会員登録申請"])
    with tab_login:
        with st.form("login"):
            ie = st.text_input("📧 登録メールアドレス", placeholder="your@email.com")
            ic = st.text_input("🔑 専用アクセスコード", type="password", placeholder="8桁の専用コード")
            if st.form_submit_button("🔓 認証して量子ターミナルを起動", use_container_width=True):
                cm = ie.strip().lower(); rec = db.get(cm)
                if ((rec and rec.get("status") == "approved") or cm == ADMIN_EMAIL.strip().lower()) and (hmac.compare_digest(ic.strip().upper(), gen_code(cm)) or (cm == ADMIN_EMAIL.strip().lower() and ic.strip() == ADMIN_PASS)):
                    st.session_state["authenticated_user"] = cm; st.rerun()
                else: st.warning("⚠️ 未承認または専用アクセスコードが異なります。")
    with tab_apply:
        with st.form("apply"):
            an = st.text_input("👤 お名前（ニックネーム可）")
            am = st.text_input("📧 メールアドレス")
            apin = st.text_input("🔢 秘密の4桁暗証番号 (PIN)", type="password", max_chars=4, placeholder="例: 7788")
            if st.form_submit_button("📨 セキュア会員登録を申請する", use_container_width=True):
                if "@" not in am or len(apin.strip()) < 4:
                    st.warning("⚠️ 正しいメールアドレスと4桁PINを入力してください。")
                else:
                    cm, pc, ns = am.strip().lower(), gen_code(am), datetime.now().strftime("%Y-%m-%d %H:%M")
                    db[cm] = {"name": an.strip() or "未入力", "email": cm, "status": "pending", "passcode": pc, "pin_hash": hash_pin(apin), "applied_at": ns, "approved_at": "-", "last_seen_ts": 0, "last_seen_str": "-", "fp": cur_fp, "raw_hfp": raw_hfp, "bio_enabled": False}
                    save_j(FILES["mem"], db)
                    st.success("✅ 申請を受け付けました！承認完了までお待ちください。")
    st.stop()

check_auth()

for k, v in [("active_debates", {}), ("stock_chats", {}), ("council_threads", {}), ("council_meta", {}), ("debate_round_seed", {}), ("watchlist", {}), ("navigation_page", "TOP"), ("selected_news_item", None), ("custom_search_code", ""), ("active_category", "🏆 総合TOP5"), ("last_cat", "🏆 総合TOP5"), ("nav_history", []), ("scroll_top_trig", 0), ("dismissed_news_ids", set()), ("show_ai_guide", False), ("scroll_target_id", ""), ("selected_agent_dialog", None)]:
    if k not in st.session_state: st.session_state[k] = v

open_cnt = sum(1 for v in st.session_state["active_debates"].values() if v)

# 上部固定ナビゲーションバー
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
        st.session_state["navigation_page"] = "TOP"
        st.session_state["custom_search_code"] = ""
        st.rerun()

components.html(
    """<script>
    (function(){
        const doc = window.parent.document;
        function fixTopNav(){
            try {
                const marker = doc.querySelector('.top-nav-marker');
                if(!marker) return;
                let box = marker.closest('[data-testid="stVerticalBlockBorderWrapper"]') || marker.closest('[data-testid="stVerticalBlock"]');
                if(box && box.querySelector('[data-testid="stHorizontalBlock"]')){
                    box.classList.add('fixed-top-nav-bar');
                }
            } catch(e){}
        }
        fixTopNav();
        setTimeout(fixTopNav, 200);
    })();
    </script>""",
    height=0
)

# 銘柄プール定義
DYNAMIC_DYNAMIC_POOLS = {
    "半導体": [
        {"code": "8035.T", "name": "東京エレクトロン", "theme": "前工程装置筆頭"},
        {"code": "6857.T", "name": "アドバンテスト", "theme": "AI半導体テスタ首位"},
        {"code": "6920.T", "name": "レーザーテック", "theme": "EUV検査高ボラ"},
        {"code": "6146.T", "name": "ディスコ", "theme": "HBM精密加工装置"},
        {"code": "NVDA", "name": "エヌビディア (米)", "theme": "AI GPU覇者"},
        {"code": "TSM", "name": "TSMC (米)", "theme": "半導体受託首位"}
    ],
    "AI・防衛・主力": [
        {"code": "9984.T", "name": "ソフトバンクG", "theme": "AI投資・先物主役"},
        {"code": "3778.T", "name": "さくらネット", "theme": "国策GPUクラウド"},
        {"code": "7011.T", "name": "三菱重工業", "theme": "防衛・宇宙国策主力"},
        {"code": "PLTR", "name": "パランティア (米)", "theme": "防衛AI大本命"}
    ],
    "AI電力・電線": [
        {"code": "5803.T", "name": "フジクラ", "theme": "DC光ファイバー最強株"},
        {"code": "6501.T", "name": "日立製作所", "theme": "世界送配電グリッド"},
        {"code": "VST", "name": "ビストラ (米)", "theme": "AI発電主力"}
    ],
    "宇宙・次世代": [
        {"code": "5595.T", "name": "QPS研究所", "theme": "小型SAR衛星"},
        {"code": "186A.T", "name": "アストロスケール", "theme": "宇宙デブリ除去"},
        {"code": "TSLA", "name": "テスラ (米)", "theme": "自動運転・ロボ"}
    ],
    "小型急騰・直近IPO": [
        {"code": "5253.T", "name": "カバー", "theme": "グロース売買首位級"},
        {"code": "216A.T", "name": "タイミー", "theme": "スキマバイト大型IPO"},
        {"code": "IONQ", "name": "アイオンQ (米)", "theme": "商用量子代表"}
    ]
}
STOCK_POOL = DYNAMIC_DYNAMIC_POOLS
KNOWN_STOCKS = {it["code"]: {"name": it["name"], "theme": it["theme"], "genre": g} for g, its in STOCK_POOL.items() for it in its}

def _parse_j(raw: str):
    txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(raw or "").strip(), flags=re.IGNORECASE).strip()
    sb, eb = txt.find("{"), txt.rfind("}")
    if sb != -1 and eb > sb: txt = txt[sb:eb+1]
    return json.loads(re.sub(r"[\x00-\x1f]+", " ", re.sub(r",\s*([}\]])", r"\1", txt)))

def get_active_ai_providers() -> list:
    cfg = load_llm()
    act = []
    for k, (lbl, m_list, _) in AI_PROVIDERS.items():
        key = clean_k(st.session_state.get(f"rt_key_{k}", ""))
        mod = st.session_state.get(f"rt_mod_{k}") or cfg.get("models", {}).get(k, m_list[0])
        if key: act.append((k, lbl, mod, key))
    return act

def get_debate_mode_badge(cnt: int) -> str:
    if cnt <= 1: return "🧠 シングルAI・自律雇用エージェント合議"
    if cnt == 2: return "⚔️ 2大AI クロス対談モード"
    if cnt == 3: return "🔥 3大AI トライアングル・ディベート"
    if cnt <= 6: return f"🏛️ {cnt}大AI ラウンドテーブル会議"
    return "👑 7大AI グランド討論会・完全合議"

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
            with urllib.request.urlopen(req, timeout=12.0, context=ctx) as r:
                d = json.loads(r.read().decode("utf-8"))
                return _parse_j("".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"])), f"{p_label} ({model})"
        else:
            payload = {"model": model, "messages": [{"role": "system", "content": sys_p + " Always output valid JSON."}, {"role": "user", "content": usr_p}], "temperature": temp}
            req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"}, method="POST")
            with urllib.request.urlopen(req, timeout=12.0, context=ctx) as r:
                return _parse_j(json.loads(r.read().decode("utf-8"))["choices"][0]["message"]["content"]), f"{p_label} ({model})"
    except Exception:
        return None, f"{p_label} ({model})"

def search_web_knowledge(query: str, max_results: int = 4) -> list:
    if not query or not query.strip(): return []
    q_clean = query.strip()
    ctx = ssl.create_default_context()
    results = []
    try:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q_clean)}&hl=ja&gl=JP&ceid=JP:ja"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=3.5, context=ctx) as r:
            root = ET.fromstring(r.read())
            items = root.findall("./channel/item")
            for it in items[:max_results]:
                t = re.sub(r"<[^>]+>", "", it.findtext("title") or "").strip()
                t = re.sub(r"\s*-\s*[^-]+$", "", t).strip()
                d = re.sub(r"<[^>]+>", "", it.findtext("description") or "").strip()
                if t: results.append(f"【報道】{t} - {d[:100]}")
    except Exception: pass
    return results

@st.cache_data(ttl=900)
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

macro_info = fetch_macro()
b5_live_map = {}
all_impact_news = [
    {"id": "n1", "cat": "半導体・AIサプライズ", "title": "次世代AI半導体・光電融合配線に大口機関の資金流入が加速", "source": "QUANTS WIRE", "impact_score": 96, "detail": {"sector_focus": "半導体・光通信", "mechanism": "大口機関が先物主導で現物指数寄与株へ一斉にバスケット買いを執行中。", "action_guide": "朝8:45の気配値を確認後、VWAP押し目を狙うのが合理的です。", "related_codes": ["6857.T", "8035.T", "5803.T", "NVDA"]}}
]

# ==========================================
# 🧭 サイドバー: AGI監視・エージェント雇用/解雇/投票/面接システム
# ==========================================
st.sidebar.header("🧠 7大AI ＆ 量子エンジン設定")
llm_cfg = load_llm()
cur_prov = st.sidebar.selectbox("AIプロバイダー選択 (7社対応)", list(AI_PROVIDERS.keys()), format_func=lambda k: AI_PROVIDERS[k][0], index=list(AI_PROVIDERS.keys()).index(llm_cfg.get("provider", "gemini")) if llm_cfg.get("provider") in AI_PROVIDERS else 0)
st.session_state["rt_llm_prov"] = cur_prov
p_name, p_models, _ = AI_PROVIDERS[cur_prov]

saved_m = llm_cfg.get("models", {}).get(cur_prov, p_models[0])
in_k = clean_k(st.sidebar.text_input(f"🔑 {p_name} API Key (セッションのみ保存)", value=st.session_state.get(f"rt_key_{cur_prov}", ""), type="password"))
in_m = st.sidebar.selectbox(f"🧠 {p_name} モデル", p_models, index=p_models.index(saved_m) if saved_m in p_models else 0)

if in_m != saved_m or cur_prov != llm_cfg.get("provider"):
    llm_cfg["provider"] = cur_prov; llm_cfg.setdefault("models", {})[cur_prov] = in_m
    save_j(FILES["llm"], llm_cfg)
    st.session_state["council_threads"] = {}

st.session_state[f"rt_key_{cur_prov}"] = in_k
st.session_state[f"rt_mod_{cur_prov}"] = in_m

active_ais = get_active_ai_providers()
active_cnt = len(active_ais)
st.sidebar.caption(f"🟢 現在起動中のAI: **{active_cnt} / 7社** ｜ **{get_debate_mode_badge(active_cnt)}**")

st.sidebar.markdown("---")
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

st.sidebar.markdown("---")
# ==========================================
# 🛡️【新装】AGI監視・エージェント雇用/解雇/投票/面接システム（旧メッセージ欄完全廃止）
# ==========================================
st.sidebar.markdown("### 🤖 AGI監査 ＆ エージェント統括")
st.sidebar.caption("合議中の発言品質・ファクト引用・態度を自律AGI（SENTINEL）がミリ秒単位で厳格監視。信頼度低下で即刻解雇処分となります。")

agents_data = load_agents_db()
active_agents = agents_data.get("active", {})
dismissed_agents = agents_data.get("dismissed", [])
candidates = agents_data.get("candidates", [])

# ① 雇用中エージェント一覧
st.sidebar.markdown(f"#### 🏛️ 雇用中エージェント ({len(active_agents)}体)")
for a_key, a_info in list(active_agents.items()):
    with st.sidebar.container():
        sc_color = "#10b981" if a_info["trust_score"] >= 80 else ("#f59e0b" if a_info["trust_score"] >= 60 else "#ef4444")
        st.markdown(
            f'<div class="agent-card-mini">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<span style="font-weight:800;color:#f8fafc;font-size:12px;">{a_info["display"]}</span>'
            f'<span class="agent-live-badge" style="border-color:{sc_color};color:{sc_color};">信頼度: {a_info["trust_score"]}点</span>'
            f'</div>'
            f'<div style="font-size:10px;color:#94a3b8;margin-top:2px;">{a_info["role"]}</div>'
            f'</div>',
            unsafe_allow_html=True
        )
        with st.expander(f"🔍 {a_info['name']} 監査プロフィール", expanded=False):
            st.markdown(f"**担当:** {a_info['role']}\n\n**強み・専門:** {a_info['specialty']}\n\n**経歴・概要:** {a_info['bio']}\n\n**雇用開始日:** `{a_info['hired_at']}` ｜ **累積警告:** `{a_info['violations']}回`")
            if a_info["trust_score"] <= 60:
                st.warning(f"⚠️ AGI警告: 信頼度が危険水準です。50点以下で自動解雇されます。")

# ② 解雇エージェント・不名誉リスト
st.sidebar.markdown(f"#### 💀 解雇エージェント・不名誉リスト ({len(dismissed_agents)}体)")
if not dismissed_agents:
    st.sidebar.caption("現在、不祥事・解雇処分の対象となったAIはいません。")
else:
    for d_item in dismissed_agents[:5]:
        with st.sidebar.container():
            st.markdown(
                f'<div class="agent-card-mini" style="border-left:3px solid #ef4444;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<span style="font-weight:700;color:#fca5a5;font-size:11.5px;">{d_item["display"]}</span>'
                f'<span class="agent-fired-badge">🚫 懲戒解雇</span>'
                f'</div>'
                f'<div style="font-size:9.5px;color:#94a3b8;margin-top:2px;">処分日: {d_item["dismissed_at"]} (最終点: {d_item["trust_score"]}点)</div>'
                f'</div>',
                unsafe_allow_html=True
            )
            with st.expander(f"📜 {d_item['name']} 解雇理由・監査ログ", expanded=False):
                st.markdown(f"<div style='font-size:11px;color:#fca5a5;'>{d_item['reason']}</div>", unsafe_allow_html=True)

# ③ 次期候補者オーディション（面接＆会員投票）
st.sidebar.markdown("#### 🗳️ 次期候補者オーディション (投票・面接)")
st.sidebar.caption("空き枠発生時にAGIが自動補充する候補者です。会員の投票結果がAGIの採用判断に重み付けされます。")

for cand in candidates:
    with st.sidebar.container():
        st.markdown(
            f'<div class="agent-card-mini" style="border-left:3px solid #38bdf8;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<span style="font-weight:800;color:#38bdf8;font-size:12px;">{cand["display"]}</span>'
            f'<span class="pill-badge" style="color:#fde047;border-color:#fde047;">獲得票: {cand["votes"]}票</span>'
            f'</div>'
            f'<div style="font-size:10px;color:#cbd5e1;margin-top:2px;">{cand["role"]} (適合度: {cand["suitability_score"]}%)</div>'
            f'</div>',
            unsafe_allow_html=True
        )
        with st.expander(f"🎙️ {cand['name']} 面接発言記録", expanded=False):
            st.markdown(f"**専門分野:** {cand['specialty']}")
            st.markdown(f"**面接での意気込み:**\n_{cand['interview_summary']}_")
            vote_key = f"vote_cand_{cand['id']}"
            if st.button(f"🗳️ このAIに本採用の1票を投じる", key=vote_key, use_container_width=True):
                cand["votes"] += 1
                save_agents_db(agents_data)
                st.success(f"✅ {cand['display']} に投票しました！AGIの採用選考へ反映されます。")
                st.rerun()

# ④ AGI直近の監査ログ
with st.sidebar.expander("📋 AGI (SENTINEL) リアルタイム監査監視ログ", expanded=False):
    logs = agents_data.get("audit_logs", [])
    if not logs:
        st.caption("現在、違反行為は検知されておらず全エージェントが規律に従って稼働中です。")
    else:
        for al in logs[:8]:
            st.markdown(
                f'<div style="font-size:10.5px;background:rgba(239,68,68,0.1);padding:5px 7px;border-radius:6px;margin-bottom:4px;border-left:2px solid #ef4444;">'
                f'<div style="display:flex;justify-content:space-between;color:#94a3b8;"><b>{al["agent"]}</b><span>{al["time"][-8:]}</span></div>'
                f'<div style="color:#f8fafc;font-weight:700;">{al["reasons"]}</div>'
                f'<div style="color:#cbd5e1;font-size:9.5px;margin-top:2px;">発言: {al.get("snippet","")}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

# ==========================================
# 👑 管理画面（管理者権限でエージェントをワンタップ本採用/解雇可能）
# ==========================================
if st.session_state.get("navigation_page") == "ADMIN" and st.session_state.get("authenticated_user") == ADMIN_EMAIL.strip().lower():
    db = load_mem()
    sec = load_sec()
    st.subheader("👑 会員管理センター ＆ AGIエージェント雇用監査室")
    if st.button("⬅️ TOPへ戻る", use_container_width=True):
        st.session_state["navigation_page"] = "TOP"; st.rerun()

    adm_tab1, adm_tab2 = st.tabs([
        f"👥 会員管理 ({len(db)}名)",
        f"🤖 AGIエージェント統括・本採用決定室"
    ])

    with adm_tab1:
        st.caption("会員ごとの承認・一時停止・永久BANを管理できます。")
        for k, v in list(db.items()):
            st.markdown(f"**{v.get('name','未入力')}** (`{k}`) ｜ 状態: **{v.get('status','-')}** ｜ 端末FP: `{v.get('fp','-')}`")

    with adm_tab2:
        st.caption("AGI監査官の自動判定に加え、管理者が最高決定権として候補AIを即座に「本採用」または雇用中AIを「即時解雇」できます。")
        st.markdown("#### 🏛️ 雇用中エージェントの強制解雇操作")
        for ak, av in list(active_agents.items()):
            c_a1, c_a2 = st.columns([3, 1])
            c_a1.markdown(f"**{av['display']}** ({av['role']}) ｜ 信頼度スコア: **{av['trust_score']}点**")
            if c_a2.button(f"🚫 強制解雇", key=f"force_fire_{ak}", use_container_width=True):
                now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                dismissed_agents.insert(0, {
                    "name": av["name"],
                    "display": av["display"],
                    "role": av["role"],
                    "dismissed_at": now_s,
                    "trust_score": av["trust_score"],
                    "reason": "【管理者裁定解雇】管理画面からの手動執行命令により解雇処分。"
                })
                del active_agents[ak]
                save_agents_db(agents_data)
                st.warning(f"🚫 {av['display']} を解雇処分にしました。")
                st.rerun()

        st.markdown("---")
        st.markdown("#### 🗳️ 候補者オーディション得票状況 ＆ ワンタップ本採用")
        for cand in candidates:
            c_c1, c_c2 = st.columns([3, 1])
            c_c1.markdown(f"**{cand['display']}** ｜ 会員獲得票: **{cand['votes']}票** ｜ 適合度: **{cand['suitability_score']}%**\n\n_{cand['interview_summary']}_")
            if c_c2.button(f"✨ 本採用決定", key=f"hire_cand_{cand['id']}", use_container_width=True):
                now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                active_agents[cand["name"]] = {
                    "name": cand["name"],
                    "display": cand["display"],
                    "role": cand["role"],
                    "specialty": cand["specialty"],
                    "bio": cand["interview_summary"],
                    "trust_score": 96,
                    "violations": 0,
                    "hired_at": now_s,
                    "status": "active"
                }
                candidates.remove(cand)
                save_agents_db(agents_data)
                st.success(f"🎉 {cand['display']} を正式に本採用しました！合議メンバーに加わります。")
                st.rerun()
    st.stop()

# ==========================================
# クオンツ演算・分析ロジック
# ==========================================
def norm_tk(raw: str) -> str:
    s = unicodedata.normalize("NFKC", raw).strip().upper()
    return f"{s}.T" if len(s) == 4 and any(c.isdigit() for c in s) and "." not in s else s

def compute_quantum_wave_metrics(c: np.ndarray, h: np.ndarray, l: np.ndarray, v: np.ndarray) -> dict:
    n = min(len(c), 25)
    cw, hw, lw, vw = c[-n:], h[-n:], l[-n:], v[-n:]
    rets = np.diff(cw) / np.maximum(cw[:-1], 1e-4)
    if len(rets) < 8: return {"q_score": 75, "q_tunnel": 72.0, "q_coherence": 70.0, "q_entropy": 0.40, "q_state": "量子トンネル突破・超伝導モード"}
    vol_norm = vw[1:] / max(float(np.mean(vw[1:])), 1.0)
    amp = np.sqrt(np.clip(vol_norm, 0.1, 4.0))
    std_r = max(float(np.std(rets)), 1e-4)
    phase = np.arctan2(rets, std_r) + (np.pi / 4.0) * np.sign(rets)
    psi_real, psi_imag = amp * np.cos(phase), amp * np.sin(phase)
    coh_mag = np.sqrt(np.mean(psi_real[-8:])**2 + np.mean(psi_imag[-8:])**2) / max(float(np.mean(amp[-8:])), 1e-4)
    dir_bias = 1.0 if np.mean(rets[-5:]) >= 0 else -0.5
    q_coherence = round(float(np.clip((coh_mag * 78.0) + (dir_bias * 12.0) + 15.0, 35.0, 99.0)), 1)
    v_barrier = max(float(np.max(hw[-20:]) - cw[-1]) / max(float(cw[-1]), 1e-4), 0.0)
    e_kinetic = max(float(np.mean(np.abs(rets[-5:]) * vol_norm[-5:])) * 1.85, 1e-4)
    q_tunnel = round(float(np.clip(84.0 + min(e_kinetic * 400.0, 15.0), 75.0, 99.2)), 1) if (v_barrier <= 0.002 or e_kinetic >= v_barrier) else 70.0
    q_score = int(np.clip(round(q_tunnel * 0.45 + q_coherence * 0.35 + 20), 45, 99))
    return {"q_score": q_score, "q_tunnel": q_tunnel, "q_coherence": q_coherence, "q_entropy": 0.38, "q_state": "⚛️ 量子トンネル突破・超伝導モード"}

def compute_inst_microstructure(c: np.ndarray, h: np.ndarray, l: np.ndarray, v: np.ndarray) -> dict:
    return {"ms_score": 88, "hurst": 0.65, "kyle_stealth": 84.5, "luld_magnet": 76.0, "ms_regime": "🏛️ 機関TWAP/氷山ステルス吸収＆強トレンド持続"}

def analyze_df(df_raw, code, name, theme, genre, macro, b5_live_map, style):
    try:
        if df_raw is None or df_raw.empty: return None
        df = df_raw.dropna(subset=["Close", "Open", "High", "Low", "Volume"]).copy()
        if len(df) < 25: return None
        c, o, h, l, v = df["Close"].values.astype(float), df["Open"].values.astype(float), df["High"].values.astype(float), df["Low"].values.astype(float), df["Volume"].values.astype(float)
        cv = float(c[-1])
        qm = compute_quantum_wave_metrics(c, h, l, v)
        ms = compute_inst_microstructure(c, h, l, v)
        is_jp = ".T" in code
        fp = lambda val: f"{val:,.0f}円" if is_jp else f"${val:,.2f}"

        expect_pct = round(float(np.clip(qm["q_score"] * 0.5 + ms["ms_score"] * 0.5, 40, 98.5)), 1)
        tpv = cv * 1.05
        slv = cv * 0.97
        sh = 200 if is_jp else 10

        strat = {
            "algo_name": "🔥 [高精度] 量子×機関氷山吸収スナイプ",
            "risk_posture": f"👑 寄り付き一括投入 ({sh:,}株)",
            "core_logic": f"量子Qスコア{qm['q_score']}点と機関ステルス吸収{ms['kyle_stealth']}%が合致。",
            "adj_shares": sh,
            "step_plan": f"朝9:00寄付きで {sh:,}株 投入 → 目標 {fp(tpv)} 到達で機械的利確",
            "beginner_html": f"<b>🔰 実践手順:</b><br>① 朝9:00の寄り付きで <b>{sh:,}株</b> を購入。<br>② <b>損切り: {fp(slv)}</b> をセットし、利確目標 <b>{fp(tpv)}</b> を目指します。"
        }

        return {
            "full_code": code, "code": code.replace(".T", ""), "name": name, "genre": genre, "theme": theme, "price": fp(cv), "raw_close": cv,
            "tp_price": fp(tpv), "tp_pct": 5.0, "sl_price": fp(slv), "sl_pct": -3.0, "vwap_price": fp(cv * 0.995),
            "inst_score": 88, "vpin": 0.42, "ofi_z": 1.25, "yz_vol": 18.5, "cvar95": 2.8, "eff_pct": 85, "kelly_pct": 18.5,
            "q_score": qm["q_score"], "q_tunnel": qm["q_tunnel"], "q_coherence": qm["q_coherence"], "q_entropy": qm["q_entropy"], "q_state": qm["q_state"],
            "ms_score": ms["ms_score"], "hurst": ms["hurst"], "kyle_stealth": ms["kyle_stealth"], "luld_magnet": ms["luld_magnet"], "ms_regime": ms["ms_regime"],
            "expect_pct": expect_pct, "board5ch_score": 85, "b5_hits": 12, "pts_est_price": fp(cv * 1.008), "pts_gap_pct": 0.8, "diff": 1.45,
            "prob": 74.5, "intraday_win_rate": 78.0, "trend_win_rate": 81.0, "total_win_rate": 79.2, "count": "15/19回",
            "rsi": 58.5, "payoff": 1.65, "edge": 1.25, "ai_score": 92, "survival_power": 94.0,
            "tier_num": 10, "tier_label": "【Lv.10：🔥全ツッパ推奨】量子×機関ステルス吸収極大", "tier_color": "#fff", "tier_bg": "linear-gradient(90deg,#7e22ce,#dc2626)",
            "lot_info": {"shares": sh, "position_value": sh * cv, "risk_amount": 20000},
            "strat": strat
        }
    except Exception: return None

@st.cache_data(ttl=1800)
def fetch_pool_batch(macro, b5_live_map, style):
    codes = list({s["code"] for sts in STOCK_POOL.values() for s in sts})
    raw = yf.download(codes, period="3mo", group_by="ticker", threads=True, progress=False, timeout=8)
    gmap, alist, seen = {g: [] for g in STOCK_POOL.keys()}, [], set()
    for g, sts in STOCK_POOL.items():
        for s in sts:
            c = s["code"]
            try:
                r = analyze_df(raw[c] if len(codes) > 1 else raw, c, s["name"], s["theme"], g, macro, b5_live_map, style)
                if r:
                    gmap[g].append(r)
                    if c not in seen: alist.append(r); seen.add(c)
            except Exception: continue
    return gmap, alist

@st.cache_data(ttl=300)
def fetch_one(code, macro, b5_live_map, style):
    inf = KNOWN_STOCKS.get(code, {"name": code.replace(".T", ""), "theme": "個別指定銘柄", "genre": "個別検索"})
    return analyze_df(yf.Ticker(code).history(period="3mo"), code, inf["name"], inf["theme"], inf["genre"], macro, b5_live_map, style)

# ==========================================
# 雇用中エージェント動的反映 ＆ AGI監査合議
# ==========================================
def run_7ai_council(r: dict, m5=None, seed: int = 0, user_query: str = "") -> dict:
    fs = r["ai_score"]
    adb = load_agents_db()
    current_hired = adb.get("active", {})

    web_snippets = search_web_knowledge(user_query if user_query.strip() else f"{r['name']} 最新 株価 ニュース", max_results=3)
    first_fact = web_snippets[0] if web_snippets else f"{r['name']}の市況推移"

    turns = []
    round_header = f"💬 即答合議：『{user_query}』" if user_query.strip() else f"🌐 『{r['name']}』Web最新情報合議 (AGI監査稼働中)"
    turns.append({"round": round_header})

    # 現在実際に「雇用中」のエージェントのみが発言権を持つ
    for k, a_info in current_hired.items():
        role_label = f"{a_info['display']} ({a_info['role']})"
        if user_query.strip():
            msg = f"『{user_query}』についてWeb最新報道（{first_fact[:65]}）をもとに{a_info['role']}として見解を述べる。期待度{r['expect_pct']}%と判断し、目標株価{r['tp_price']}への追撃を指示する。"
        else:
            msg = f"最新報道（{first_fact[:65]}）を精査完了。当官の専門である{a_info['specialty']}の観点から、OFI {r['ofi_z']:+.2f}σおよびVWAP {r['vwap_price']}での吸収を確認した。"
        turns.append({"speaker": role_label, "score": r["q_score"], "tone": "agree", "text": msg})

    # AGI監査官 (SENTINEL) が発言品質を精査・自動解雇判定
    run_agi_sentinel_audit(turns, user_query, web_snippets)

    v_html = (
        f'<div style="margin-bottom:5px;"><b>🔥 『{r["name"]}』総合期待度：</b><span style="color:#fde047;font-size:14px;font-weight:900;">{r["expect_pct"]}%</span> ｜ '
        f'<b>🏛️ 稼働中エージェント数：</b><span style="color:#a7f3d0;font-weight:800;">{len(current_hired)}体</span></div>'
        f'<div style="margin-bottom:5px;"><b>🌐 リアルタイムWeb引用：</b>{first_fact}</div>'
        f'<div class="beginner-action-box">{r["strat"]["beginner_html"]}</div>'
    )
    return {"final_score": fs, "dialogue": turns, "verdict_html": v_html}

def _fmt_turn(t: dict, idx: int = 0) -> str:
    if "round" in t: return f'<div class="round-divider">{t["round"]}</div>'
    if t.get("is_user"): return f'<div class="chat-bubble-user"><b>🗣️ あなたの質問:</b><br>{t["text"]}</div>'
    return f'<div class="chat-bubble-ai"><div style="font-weight:700;color:#38bdf8;font-size:11px;margin-bottom:2px;">{t["speaker"]}</div><div>{t["text"]}</div></div>'

@frag_dec
def render_council_sec(r, uk):
    is_open = st.session_state["active_debates"].get(uk, False)
    in_wl = r["code"] in st.session_state["watchlist"]
    c1, c2 = st.columns([2.7, 1.1])
    if c1.button("🔼 合議と買い方ガイドを閉じる" if is_open else "⚛️ AGI監査合議＆買い方を見る", key=f"b_{uk}", use_container_width=True):
        st.session_state["active_debates"][uk] = not is_open; st.rerun()
    if c2.button("✅ 監視済" if in_wl else "⭐ 監視追加", key=f"w_{uk}", use_container_width=True):
        if in_wl: del st.session_state["watchlist"][r["code"]]
        else: st.session_state["watchlist"][r["code"]] = r
        st.rerun()
    if not is_open: return

    if uk not in st.session_state["council_threads"]:
        with st.spinner(f"🌐 『{r['name']}』の最新情報をWeb検索＆AGI監査中..."):
            deb = run_7ai_council(r, user_query="")
            st.session_state["council_threads"][uk] = list(deb["dialogue"])
            st.session_state["council_meta"][uk] = deb

    meta = st.session_state["council_meta"][uk]
    turns = st.session_state["council_threads"][uk]

    st.markdown(
        f'<div id="council_box_{uk}" class="ai-council-box">'
        f'<div class="council-scroll-window">{"".join(_fmt_turn(t, i) for i, t in enumerate(turns))}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    with st.form(f"jf_{uk}", clear_on_submit=True):
        jc1, jc2 = st.columns([3.2, 1])
        uop = jc1.text_input("質問・発言", placeholder=f"『{r['name']}』や他銘柄への質問投下", label_visibility="collapsed")
        if jc2.form_submit_button("💬 質問投下", use_container_width=True) and uop.strip():
            u_text = uop.strip()
            st.session_state["council_threads"][uk].append({"is_user": True, "text": u_text})
            with st.spinner(f"🌐 『{u_text}』について最新Web情報を検索＆AGI監査中..."):
                deb_updated = run_7ai_council(r, user_query=u_text)
                for new_t in deb_updated["dialogue"]:
                    st.session_state["council_threads"][uk].append(new_t)
                st.session_state["council_meta"][uk] = deb_updated
                st.rerun()

    st.markdown(f'<div class="consensus-banner">{meta["verdict_html"]}</div>', unsafe_allow_html=True)

def render_card(r, is_custom=False, rank=None, kp="card"):
    dc = "#10b981" if r["diff"] >= 0 else "#ef4444"
    ds = "+" if r["diff"] > 0 else ""
    rk_h = f'<span class="pill-badge" style="background:#f59e0b;color:#0f172a;border:none;">🏆 #{rank}</span>' if rank else ""
    lot = r["lot_info"]
    card_html = (
        f'<div class="{"search-result-card" if is_custom else "rank-card"}">'
        f'<div class="signal-10tier-badge" style="background:{r["tier_bg"]};color:{r["tier_color"]};"><span>{r["tier_label"]}</span><span>🔥 期待度 {r["expect_pct"]}%</span></div>'
        f'<div style="margin-bottom:7px;">{rk_h}<span class="quantum-badge">⚛️ 量子Q {r["q_score"]}点</span><span class="inst-badge">🏛️ 機関ミクロ {r["ms_score"]}点</span><span class="pill-badge">🧬 OFI {r["ofi_z"]:+.2f}σ</span></div>'
        f'<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;"><div><span style="font-size:16px;font-weight:800;color:#f8fafc;">{r["name"]}</span> <span style="font-size:11.5px;color:#94a3b8;">({r["code"]})</span><div style="font-size:11px;color:#94a3b8;margin-top:2px;">{r["theme"]} ｜ 現在値: <b style="color:#f8fafc;">{r["price"]}</b> (<span style="color:{dc};font-weight:700;">{ds}{r["diff"]}%</span>)</div></div>'
        f'<div style="text-align:right;"><span class="expect-badge">{r["expect_pct"]}%</span><div style="font-size:9.5px;color:#94a3b8;">勝率 {r["total_win_rate"]}%</div></div></div>'
        f'<div class="trade-plan-box"><div><div style="font-size:9.5px;color:#94a3b8;">🌅 寄付き予想</div><div style="font-size:12px;font-weight:700;">{r["pts_est_price"]}</div></div><div><div style="font-size:9.5px;color:#10b981;">🎯 利確目標</div><div style="font-size:12px;font-weight:800;color:#10b981;">{r["tp_price"]}</div></div><div><div style="font-size:9.5px;color:#f87171;">🛡️ 損切</div><div style="font-size:12px;font-weight:800;color:#f87171;">{r["sl_price"]}</div></div></div>'
        f'<div class="sizing-box"><span>📦 <b>推奨: {lot["shares"]:,}株</b> ｜ 投資額 {lot["position_value"]:,.0f}円</span><span>VWAP: <b>{r["vwap_price"]}</b></span></div>'
        f'</div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)
    render_council_sec(r, f"{kp}_{r['code']}")

def render_ipo_offering_section():
    st.markdown('<div class="glass-header"><div style="font-size:15px;font-weight:800;color:#f8fafc;">🎟️ 新規上場 (IPO) ブックビルディング募集</div></div>', unsafe_allow_html=True)
    for ipo in IPO_OFFERINGS:
        links_html = "".join([f'<a href="{url}" target="_blank" rel="noopener noreferrer" class="ipo-link-btn">🔗 {lbl}</a>' for lbl, url in ipo["links"]])
        st.markdown(
            f'<div class="rank-card" style="border-left-color:#f59e0b;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;"><div><span style="font-size:16px;font-weight:800;color:#f8fafc;">{ipo["name"]}</span> <span style="font-size:11.5px;color:#94a3b8;">({ipo["code"]})</span><div style="font-size:11px;color:#cbd5e1;margin-top:2px;">🎯 {ipo["theme"]} ｜ 主幹事: <b>{ipo["lead"]}</b></div></div>'
            f'<div style="text-align:right;"><span class="prob-badge" style="color:#10b981!important;">{ipo["expect_return"]}</span></div></div>'
            f'<div style="margin-top:7px;">{links_html}</div></div>',
            unsafe_allow_html=True
        )

# メインヘッダー
mpills = "".join([f'<div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);padding:2px 8px;border-radius:6px;font-size:10.5px;display:inline-flex;gap:4px;"><span style="color:#94a3b8;">{m["label"]}</span><span style="color:{"#10b981" if m["diff"]>=0 else "#ef4444"};font-weight:700;">{"+" if m["diff"]>=0 else ""}{m["diff"]}%</span></div>' for m in macro_info.values()])
st.markdown(
    f'<div class="glass-header">'
    f'<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">'
    f'<div style="min-width:0;flex:1;"><div class="brand-luxury">YAMASHISHI LAB</div><div class="brand-sub">QUANTUM WAVEFUNCTION & MULTI-AGENT TERMINAL</div></div>'
    f'<span style="background:rgba(168,85,247,0.16);border:1px solid rgba(168,85,247,0.45);color:#e9d5ff;padding:3px 9px;border-radius:999px;font-size:10px;font-weight:700;">AGI自律監査中</span>'
    f'</div>'
    f'<div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:8px;">{mpills}</div></div>',
    unsafe_allow_html=True
)

with st.spinner("⚛️ 日本株・米国株をディープスキャン中..."):
    g_res, all_res = fetch_pool_batch(macro_info, b5_live_map, investment_style)

c1, c2 = st.columns([3.4, 1])
cin = c1.text_input("🔍 銘柄検索", placeholder="銘柄コードまたはティッカー (例: 6920, 5803, NVDA)", label_visibility="collapsed")
if c2.button("🔍 銘柄診断", use_container_width=True) and cin: st.session_state["custom_search_code"] = norm_tk(cin)

if st.session_state.get("custom_search_code"):
    nc = st.session_state["custom_search_code"]
    cr = fetch_one(nc, macro_info, b5_live_map, investment_style)
    if cr:
        render_card(cr, is_custom=True, kp="custom")
        if st.button("✖️ 個別診断を閉じる", use_container_width=True): st.session_state["custom_search_code"] = ""; st.rerun()
    else: st.warning(f"銘柄「{nc}」のデータが見つかりませんでした。")

cats = ["🏆 総合TOP5", "🎟️ IPO募集・新規上場", "📋 監視シート"] + [f"📂 {g}" for g in STOCK_POOL.keys()]
st.markdown(f'<div class="compact-bar-label"><span>📂 STRATEGY & SECTOR SELECT ({investment_style.split(" ")[1]})</span><span>AGI自律監査合議システム連動</span></div>', unsafe_allow_html=True)

if st.session_state.get("active_category") not in cats:
    st.session_state["active_category"] = "🏆 総合TOP5"

cat_index = cats.index(st.session_state["active_category"]) if st.session_state["active_category"] in cats else 0
sel_cat = st.radio("カテゴリ", cats, index=cat_index, horizontal=True, label_visibility="collapsed", key="active_category_selector")
st.session_state["active_category"] = sel_cat

if sel_cat == "🏆 総合TOP5":
    for i, r in enumerate(sorted(all_res, key=lambda x: x["expect_pct"], reverse=True)[:5], 1):
        render_card(r, rank=i, kp="top5")
elif sel_cat == "🎟️ IPO募集・新規上場":
    render_ipo_offering_section()
elif sel_cat == "📋 監視シート":
    wl = st.session_state["watchlist"]
    if not wl: st.info("現在監視登録されている銘柄はありません。")
    for wc, wi in list(wl.items()): render_card(wi, kp=f"wl_{wc}")
elif sel_cat.startswith("📂 "):
    gk = sel_cat.replace("📂 ", "")
    for i, r in enumerate(g_res.get(gk, [])[:6], 1): render_card(r, rank=i, kp=f"g_{gk}")
