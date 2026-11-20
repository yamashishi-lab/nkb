import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np
import os
import re
import ssl
import html
import json
import time
import sqlite3
import datetime
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

DB_PATH = "yamashishi_core.db"

# =========================================================================
# 1. DEEP DIVE v8 専用CSS
# =========================================================================
def _inject_dd_css():
    css = """
    [data-stale="true"] { opacity: 1 !important; transition: none !important; }
    .dd-macro-strip {
        display: flex; flex-wrap: nowrap; overflow-x: auto; gap: 6px;
        padding: 4px 0 6px 0; margin-bottom: 6px; scrollbar-width: none;
    }
    .dd-macro-strip::-webkit-scrollbar { display: none; }
    .dd-macro-chip {
        flex-shrink: 0; background: rgba(15, 23, 42, 0.9);
        border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 6px;
        padding: 3px 8px; font-family: 'JetBrains Mono', monospace;
        font-size: 10.5px; display: inline-flex; align-items: center; gap: 5px;
    }
    .dd-traj-header {
        display: flex; justify-content: space-between; align-items: center; gap: 6px;
        padding: 8px 10px; margin-bottom: 6px;
        background: linear-gradient(90deg, rgba(15, 23, 42, 0.96) 0%, rgba(15, 23, 42, 0.45) 100%);
        border-left: 3px solid #38bdf8; border-bottom: 1px solid rgba(56, 189, 248, 0.2);
        border-radius: 4px; flex-wrap: wrap;
    }
    .dd-traj-title {
        font-family: 'JetBrains Mono', monospace; font-size: clamp(10.5px, 3vw, 12px);
        font-weight: 700; letter-spacing: 0.4px; color: #f8fafc;
        white-space: normal; word-break: break-word;
    }
    .dd-traj-title span { color: #38bdf8; font-weight: 500; }
    .dd-winrate-bar {
        display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px;
        background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 8px; padding: 8px 6px; margin-top: 8px; text-align: center;
    }
    @media (max-width: 640px) { .dd-winrate-bar { grid-template-columns: repeat(2, 1fr); } }
    .dd-metric-val { font-family: 'JetBrains Mono', monospace; font-size: 13.5px; font-weight: 800; color: #38bdf8; margin-top: 2px; }
    .dd-metric-lbl { font-size: 10px; color: #94a3b8; font-weight: 600; }
    .dd-range-track { width: 100%; height: 6px; background: rgba(148, 163, 184, 0.2); border-radius: 99px; position: relative; margin: 6px 0 3px 0; }
    .dd-range-dot { width: 11px; height: 11px; background: #38bdf8; border: 2px solid #fff; border-radius: 50%; position: absolute; top: -2.5px; transform: translateX(-50%); box-shadow: 0 0 8px rgba(56, 189, 248, 0.9); }
    .dd-sc-stack { display: flex; flex-direction: column; gap: 8px; margin: 8px 0 12px 0; }
    .dd-sc-card { background: linear-gradient(135deg, rgba(15, 23, 42, 0.96) 0%, rgba(9, 13, 22, 0.96) 100%); border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 10px; padding: 10px 12px; }
    .dd-sc-top { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
    .dd-sc-price { font-family: 'JetBrains Mono', monospace; font-size: 17px; font-weight: 800; color: #fff; line-height: 1.15; }
    .dd-sc-pct { font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 700; margin-top: 2px; }
    .dd-sc-bar-bg { width: 100%; height: 4px; background: rgba(148, 163, 184, 0.16); border-radius: 99px; margin-top: 8px; overflow: hidden; }
    .dd-sc-bar-fill { height: 100%; border-radius: 99px; }
    .dd-dow-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 5px; margin-top: 6px; }
    .dd-dow-cell { background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(148, 163, 184, 0.18); border-radius: 7px; padding: 6px 4px; text-align: center; }
    .dd-dark-box { background: rgba(15, 23, 42, 0.88); border: 1px solid rgba(148, 163, 184, 0.18); padding: 12px; border-radius: 10px; margin-bottom: 10px; font-size: 12px; line-height: 1.65; color: #cbd5e1; }
    .dd-warn-box { background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.4); border-left: 4px solid #ef4444; padding: 12px; border-radius: 10px; margin-bottom: 10px; font-size: 12px; line-height: 1.65; color: #fecaca; }
    .dd-quant-box { background: rgba(16, 185, 129, 0.10); border: 1px solid rgba(16, 185, 129, 0.35); border-left: 4px solid #10b981; padding: 12px; border-radius: 10px; margin-bottom: 10px; font-size: 12px; line-height: 1.65; color: #d1fae5; }
    .dd-guide-box { background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.28); border-left: 3px solid #38bdf8; padding: 10px 12px; border-radius: 8px; font-size: 11.8px; line-height: 1.7; color: #e0f2fe; }
    .dd-memo-box { background: linear-gradient(180deg, #0b192c 0%, #090d16 100%); border: 1px solid rgba(168, 85, 247, 0.45); border-left: 4px solid #a855f7; padding: 13px 15px; border-radius: 10px; margin-bottom: 10px; font-size: 12.2px; line-height: 1.78; color: #f1f5f9; }
    .dd-factor-row { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 5px 0; border-bottom: 1px solid rgba(148, 163, 184, 0.12); font-size: 11.5px; }
    .dd-factor-row:last-child { border-bottom: none; padding-top: 7px; font-weight: 800; }
    .dd-table-wrap { width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; }
    .dd-data-table { width: 100%; border-collapse: collapse; font-size: 11px; margin-top: 4px; min-width: 310px; }
    .dd-data-table th { background: #1e293b; color: #38bdf8; padding: 6px 7px; text-align: left; border-bottom: 1px solid rgba(56, 189, 248, 0.3); white-space: nowrap; }
    .dd-data-table td { padding: 6px 7px; border-bottom: 1px solid rgba(148, 163, 184, 0.12); color: #e2e8f0; }
    """
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

# =========================================================================
# 2. SQLite 予測スナップショット台帳（ガチ検証・嘘なしロック保存）
# =========================================================================
def _dd_db_get(key: str, default_val):
    try:
        conn = sqlite3.connect(DB_PATH, timeout=8.0)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS kv_store (key TEXT PRIMARY KEY, val TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
        cur.execute("SELECT val FROM kv_store WHERE key = ?", (key,))
        row = cur.fetchone()
        conn.close()
        if row: return json.loads(row[0])
    except Exception:
        pass
    return default_val

def _dd_db_set(key: str, val):
    try:
        conn = sqlite3.connect(DB_PATH, timeout=8.0)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS kv_store (key TEXT PRIMARY KEY, val TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
        cur.execute("INSERT INTO kv_store (key, val, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) ON CONFLICT(key) DO UPDATE SET val=excluded.val, updated_at=CURRENT_TIMESTAMP;", (key, json.dumps(val, ensure_ascii=False)))
        conn.commit()
        conn.close()
    except Exception:
        pass

def _get_target_session_date(is_jp: bool) -> str:
    now = datetime.datetime.now()
    # 東証15:30以降は翌営業日をターゲットにする
    if is_jp and (now.hour > 15 or (now.hour == 15 and now.minute >= 30)):
        nxt = now + datetime.timedelta(days=1)
        while nxt.weekday() >= 5:
            nxt += datetime.timedelta(days=1)
        return nxt.strftime("%Y-%m-%d")
    d = now
    while d.weekday() >= 5:
        d += datetime.timedelta(days=1)
    return d.strftime("%Y-%m-%d")

# =========================================================================
# 3. ヘルパー ＆ データ取得
# =========================================================================
def _fmt_cur(val, is_jp: bool) -> str:
    if val is None or (isinstance(val, float) and np.isnan(val)): return "-"
    return f"{val:,.0f}円" if is_jp else f"${val:,.2f}"

def _fmt_sh(n: int) -> str:
    if not n or n <= 0: return "-"
    if n >= 1e9: return f"{n/1e9:.2f}B株"
    if n >= 1e6: return f"{n/1e6:.1f}M株"
    if n >= 1e4: return f"{n/1e4:.1f}万株"
    return f"{n:,}株"

def _get_gemini_key(passed_key: str = "") -> str:
    if passed_key: return passed_key.strip()
    k = os.environ.get("GEMINI_API_KEY", "")
    if not k:
        try: k = st.secrets.get("GEMINI_API_KEY", "")
        except Exception: k = ""
    return str(k).strip()

def _render_echarts(option_dict: dict, height: int = 300):
    opt_json = json.dumps(option_dict, ensure_ascii=False)
    html_code = f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>html,body{{width:100%;height:100%;margin:0;padding:0;background:#0b1120;overflow:hidden;}}#c{{width:100%;height:{height}px;}}</style>
    </head><body><div id="c"></div><script>
      var el = document.getElementById('c');
      var chart = echarts.init(el, 'dark');
      chart.setOption({opt_json});
      function doResize() {{ chart.resize(); }}
      window.addEventListener('resize', doResize);
      if (typeof ResizeObserver !== 'undefined') {{ new ResizeObserver(doResize).observe(el); }}
      setTimeout(doResize, 80); setTimeout(doResize, 300);
    </script></body></html>
    """
    components.html(html_code, height=height + 2)

def _render_live_clock(sync_interval: int = 60):
    html_code = f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <style>
      html,body{{width:100%;margin:0;padding:0;background:transparent;font-family:'JetBrains Mono',monospace;}}
      .bar{{display:flex;justify-content:space-between;align-items:center;background:rgba(15,23,42,0.85);border:1px solid rgba(16,185,129,0.35);border-radius:8px;padding:5px 10px;font-size:11px;color:#e2e8f0;}}
      .dot{{width:7px;height:7px;background:#10b981;border-radius:50%;display:inline-block;margin-right:6px;box-shadow:0 0 8px #10b981;}}
      .left{{display:flex;align-items:center;color:#6ee7b7;font-weight:700;}}
      .right{{color:#94a3b8;font-size:10.5px;}} .cnt{{color:#38bdf8;font-weight:700;}}
    </style></head><body>
    <div class="bar"><div class="left"><span class="dot"></span>LIVE FEED <span id="clk" style="margin-left:8px;color:#fff;">--:--:--</span> JST</div><div class="right">SILENT SYNC <span id="cd" class="cnt">{sync_interval}s</span></div></div>
    <script>
      var rem = {sync_interval};
      function tick(){{
        var now = new Date(); var jst = new Date(now.getTime() + (now.getTimezoneOffset()+540)*60000);
        document.getElementById('clk').textContent = String(jst.getHours()).padStart(2,'0')+':'+String(jst.getMinutes()).padStart(2,'0')+':'+String(jst.getSeconds()).padStart(2,'0');
        document.getElementById('cd').textContent = rem+'s';
        rem = rem > 1 ? rem - 1 : {sync_interval};
      }}
      tick(); setInterval(tick, 1000);
    </script></body></html>
    """
    components.html(html_code, height=34)

def _build_spark_svg(prices: np.ndarray) -> str:
    if len(prices) < 2: return ""
    p_min, p_max = float(np.min(prices)), float(np.max(prices))
    span = max(p_max - p_min, 1e-4)
    w, h = 92.0, 26.0
    pts = [f"{round((i/max(len(prices)-1,1))*w,1)},{round(h-2.0-((float(p)-p_min)/span)*(h-4.0),1)}" for i, p in enumerate(prices)]
    col = "#10b981" if prices[-1] >= prices[0] else "#ef4444"
    return f'<svg width="92" height="26" viewBox="0 0 92 26" style="display:block;margin-left:auto;"><polyline fill="none" stroke="{col}" stroke-width="1.8" points="{" ".join(pts)}"/></svg>'

MACRO_TICKERS = {"SOX": ("^SOX", "米SOX"), "SP500": ("^GSPC", "S&P500"), "NK_FUT": ("NIY=F", "日経先物"), "USDJPY": ("JPY=X", "ドル円"), "US10Y": ("^TNX", "米10年債"), "OIL": ("CL=F", "WTI原油"), "VIX": ("^VIX", "VIX")}
TIER1_SOURCES = ["REUTERS", "ロイター", "BLOOMBERG", "ブルームバーグ", "WSJ", "WALL STREET JOURNAL", "FINANCIAL TIMES", "NIKKEI", "日経", "日本経済新聞", "KABUTAN", "株探", "PR TIMES", "CNBC", "SEC"]
TIER2_SOURCES = ["YAHOO", "MINKABU", "みんかぶ", "MARKETWATCH", "BARRON", "FORBES", "東洋経済", "ダイヤモンド", "JIJI", "時事", "共同通信"]
NOISE_SOURCES = ["まとめ", "ブログ", "2ch", "5ch", "note.com"]

@st.cache_data(ttl=90)
def _load_macro_data() -> dict:
    codes = [v[0] for v in MACRO_TICKERS.values()]
    out = {}
    try:
        raw = yf.download(codes, period="6mo", interval="1d", group_by="ticker", threads=True, progress=False, timeout=8.0)
        for k, (tk, label) in MACRO_TICKERS.items():
            try:
                df_m = raw[tk].dropna(subset=["Close"]) if isinstance(raw.columns, pd.MultiIndex) else raw.dropna(subset=["Close"])
                if len(df_m) >= 2:
                    closes = df_m["Close"].copy()
                    closes.index = pd.to_datetime(closes.index).tz_localize(None).normalize()
                    closes = closes[~closes.index.duplicated(keep="last")]
                    last_c, prev_c = float(closes.iloc[-1]), float(closes.iloc[-2])
                    out[k] = {"label": label, "last": last_c, "diff_pct": round((last_c - prev_c) / max(abs(prev_c), 1e-4) * 100.0, 2), "series": closes}
            except Exception: pass
    except Exception: pass
    return out

@st.cache_data(ttl=3600)
def _fetch_jp_holders(code4: str) -> list:
    holders = []
    try:
        url = f"https://kabutan.jp/stock/holder?code={urllib.parse.quote(code4)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=4.0, context=ssl.create_default_context()) as r:
            page = r.read().decode("utf-8", errors="ignore")
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.DOTALL):
            tds = [re.sub(r"<[^>]+>", "", td).strip() for td in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.DOTALL)]
            if len(tds) >= 3:
                m_pct = re.search(r"([0-9]+\.[0-9]+)", tds[1].replace("%", ""))
                m_sh = re.search(r"([0-9,]+)", tds[2])
                nm = html.unescape(tds[0]).strip()
                if m_pct and nm and not any(x in nm for x in ["株主名", "合計", "順位"]):
                    pct_v = float(m_pct.group(1))
                    sh_v = int(m_sh.group(1).replace(",", "")) * 1000 if m_sh else 0
                    if 0.1 <= pct_v <= 99.0:
                        holders.append({"holder": nm, "pct": pct_v, "shares": sh_v})
            if len(holders) >= 10: break
    except Exception: pass
    return holders

@st.cache_data(ttl=60)
def _load_stock_core(code: str) -> dict:
    tkr = yf.Ticker(code)
    df_1d = tkr.history(period="1y", interval="1d", auto_adjust=True)
    if df_1d is not None and not df_1d.empty:
        df_1d.index = pd.to_datetime(df_1d.index).tz_localize(None).normalize()
        df_1d = df_1d[~df_1d.index.duplicated(keep="last")]
    df_5m = tkr.history(period="1mo", interval="5m", auto_adjust=True)
    if df_5m is not None and not df_5m.empty:
        df_5m = df_5m.dropna(subset=["Close"]).copy()
    try: info = tkr.info or {}
    except Exception: info = {}

    earnings_hist = []
    try:
        ed = tkr.earnings_dates
        if ed is not None and not ed.empty:
            for idx_dt, row in ed.dropna(subset=["EPS Estimate", "Reported EPS"], how="all").head(6).iterrows():
                earnings_hist.append({
                    "date": idx_dt.strftime("%Y-%m-%d") if hasattr(idx_dt, "strftime") else str(idx_dt)[:10],
                    "est": float(row["EPS Estimate"]) if pd.notna(row.get("EPS Estimate")) else None,
                    "rep": float(row["Reported EPS"]) if pd.notna(row.get("Reported EPS")) else None,
                    "surp": float(row["Surprise(%)"]) if pd.notna(row.get("Surprise(%)")) else None
                })
    except Exception: pass

    inst_holders = []
    try:
        ih = tkr.institutional_holders
        if ih is not None and not ih.empty:
            for _, row in ih.head(10).iterrows():
                inst_holders.append({
                    "holder": str(row.get("Holder", "-")),
                    "pct": float(row.get("pctHeld", 0.0)) * 100.0 if pd.notna(row.get("pctHeld")) else 0.0,
                    "shares": int(row.get("Shares", 0)) if pd.notna(row.get("Shares")) else 0
                })
    except Exception: pass
    if not inst_holders and code.endswith(".T"):
        inst_holders = _fetch_jp_holders(code.replace(".T", ""))

    # インサイダー売買（米国株等の大口異変検知用）
    insider_tx = []
    try:
        itx = tkr.insider_transactions
        if itx is not None and not itx.empty:
            for _, row in itx.head(8).iterrows():
                insider_tx.append({
                    "insider": str(row.get("Insider", "-")),
                    "text": str(row.get("Text", row.get("Transaction", "-"))),
                    "shares": int(row.get("Shares", 0)) if pd.notna(row.get("Shares")) else 0
                })
    except Exception: pass

    return {"df_1d": df_1d, "df_5m": df_5m, "info": info, "earnings_hist": earnings_hist, "inst_holders": inst_holders, "insider_tx": insider_tx}

def _fetch_rss(url: str, lang_tag: str) -> list:
    out = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=4.0) as r:
            for it in ET.fromstring(r.read()).findall("./channel/item")[:10]:
                t = (it.findtext("title") or "").strip()
                if t: out.append({"title": t, "link": (it.findtext("link") or "").strip(), "source": (it.findtext("source") or "").strip(), "pub": (it.findtext("pubDate") or "").strip()[:16], "lang": lang_tag})
    except Exception: pass
    return out

@st.cache_data(ttl=120)
def _fetch_global_intel(corp_name: str, short_code: str) -> dict:
    q_jp = f"{corp_name} OR {short_code} 株価"
    q_en = f"{short_code} OR \"{corp_name.split(' ')[0]}\" stock (Reuters OR Bloomberg OR CNBC OR WSJ)"
    u_jp = f"https://news.google.com/rss/search?q={urllib.parse.quote(q_jp)}&hl=ja&gl=JP&ceid=JP:ja"
    u_en = f"https://news.google.com/rss/search?q={urllib.parse.quote(q_en)}&hl=en-US&gl=US&ceid=US:en"
    raw_items = []
    with ThreadPoolExecutor(max_workers=2) as ex:
        f1, f2 = ex.submit(_fetch_rss, u_jp, "JP"), ex.submit(_fetch_rss, u_en, "EN")
        raw_items.extend(f1.result()); raw_items.extend(f2.result())

    pos_w = ["上昇", "急騰", "最高益", "上方修正", "増配", "自社株買い", "好調", "提携", "買い", "黒字", "成長", "SURGE", "BEAT", "UPGRADE", "RECORD", "BUY", "GROWTH", "RALLY"]
    neg_w = ["下落", "急落", "下方修正", "赤字", "減益", "不祥事", "訴訟", "不正", "辞任", "懸念", "売り", "リスク", "DROP", "FALL", "MISS", "DOWNGRADE", "LAWSUIT", "PROBE", "CUT", "SLUMP"]
    filtered, seen_t = [], set()
    for it in raw_items:
        src_up = (it["source"] + " " + it["title"]).upper()
        if any(ns.upper() in src_up for ns in NOISE_SOURCES): continue
        nk = re.sub(r"\W+", "", it["title"].lower())[:24]
        if nk in seen_t: continue
        seen_t.add(nk)
        trust, wt = ("S", 2.0) if any(t1 in src_up for t1 in TIER1_SOURCES) else (("A", 1.3) if any(t2 in src_up for t2 in TIER2_SOURCES) else ("B", 0.7))
        t_up = it["title"].upper()
        p_h, n_h = sum(1 for w in pos_w if w in t_up), sum(1 for w in neg_w if w in t_up)
        filtered.append({**it, "trust": trust, "w_trust": wt, "sent": "POS" if p_h > n_h else ("NEG" if n_h > p_h else "NEU")})

    filtered.sort(key=lambda x: ({"S": 0, "A": 1, "B": 2}[x["trust"]], 0 if x["lang"] == "EN" else 1))
    wp = sum(x["w_trust"] for x in filtered if x["sent"] == "POS")
    wn = sum(x["w_trust"] for x in filtered if x["sent"] == "NEG")
    wtot = max(sum(x["w_trust"] for x in filtered), 1.0)
    return {"items": filtered[:10], "pos_pct": round(wp / wtot * 100), "shock_score": round(float(np.clip((wp - wn) / wtot, -1.0, 1.0)), 2), "tier1_cnt": sum(1 for x in filtered if x["trust"] == "S")}

@st.cache_data(ttl=180)
def _fetch_gov_and_whales(corp_name: str, short_code: str) -> tuple:
    u_g = f"https://news.google.com/rss/search?q={urllib.parse.quote(f'{corp_name} (不祥事 OR 不正 OR 訴訟 OR 行政処分 OR 辞任 OR リコール)')}&hl=ja&gl=JP&ceid=JP:ja"
    u_w = f"https://news.google.com/rss/search?q={urllib.parse.quote(f'({corp_name} OR {short_code}) (大量保有 OR 変更報告書 OR 空売り残高 OR 5%ルール OR 買い増し OR 保有割合低下)')}&hl=ja&gl=JP&ceid=JP:ja"
    with ThreadPoolExecutor(max_workers=2) as ex:
        fg, fw = ex.submit(_fetch_rss, u_g, "JP"), ex.submit(_fetch_rss, u_w, "JP")
        return [f"{x['title']} ({x['pub']})" for x in fg.result()[:5]], fw.result()[:5]

# =========================================================================
# 4. 大口異変検知・4層精度アップ軌道・ガチ検証エンジン
# =========================================================================
def _detect_whale_anomaly(insider_tx: list, whale_news: list) -> dict:
    """インサイダー売買＋大量保有報告から大口の異変（強気/弱気）を実測判定"""
    bull_sigs, bear_sigs = [], []
    for tx in insider_tx:
        t_up = tx["text"].upper()
        if "PURCHASE" in t_up or "BUY" in t_up:
            bull_sigs.append(f"役員買付: {tx['insider']} ({_fmt_sh(tx['shares'])})")
        elif "SALE" in t_up or "SELL" in t_up:
            bear_sigs.append(f"役員売却: {tx['insider']} ({_fmt_sh(tx['shares'])})")
    for wn in whale_news:
        t = wn["title"]
        if any(k in t for k in ["新規保有", "買い増し", "保有割合増加", "5%超"]):
            bull_sigs.append(f"大量保有(買): {t[:34]}")
        elif any(k in t for k in ["保有割合低下", "売却", "空売り残高増加", "売り増し"]):
            bear_sigs.append(f"大口売/空売: {t[:34]}")

    if len(bull_sigs) > len(bear_sigs):
        return {"detected": True, "dir": "BULL", "adj_pct": round(min(0.65, 0.25 * (len(bull_sigs) - len(bear_sigs))), 2), "summary": " / ".join(bull_sigs[:2])}
    if len(bear_sigs) > len(bull_sigs):
        return {"detected": True, "dir": "BEAR", "adj_pct": round(-min(0.65, 0.25 * (len(bear_sigs) - len(bull_sigs))), 2), "summary": " / ".join(bear_sigs[:2])}
    return {"detected": False, "dir": "NEUTRAL", "adj_pct": 0.0, "summary": "特異な大口異変なし"}

def _compute_macro_sens(stock_close: pd.Series, macro_data: dict) -> list:
    s_ret = stock_close.pct_change().dropna().tail(90)
    res = []
    for k, m in macro_data.items():
        if k == "VIX": continue
        j = pd.concat([s_ret.rename("stk"), m["series"].pct_change().dropna().rename("mac")], axis=1).dropna()
        if len(j) >= 20:
            corr = float(j["stk"].corr(j["mac"]))
            vm = float(j["mac"].var())
            beta = float(j["stk"].cov(j["mac"]) / vm) if vm > 1e-9 else 0.0
            res.append({"key": k, "label": m["label"], "corr": round(0.0 if np.isnan(corr) else corr, 2), "beta": round(0.0 if np.isnan(beta) else beta, 2), "latest_diff": m["diff_pct"]})
    res.sort(key=lambda x: abs(x["corr"]), reverse=True)
    return res

def _compute_dow_edge(df_1d: pd.DataFrame) -> tuple:
    rets = df_1d["Close"].pct_change().dropna() * 100.0
    names = ["月", "火", "水", "木", "金"]
    stats = []
    for d in range(5):
        sub = rets[rets.index.dayofweek == d]
        wr, avg = (int(round(float((sub > 0).mean() * 100.0), 0)), round(float(sub.mean()), 2)) if len(sub) >= 3 else (50, 0.0)
        stats.append({"dow": d, "label": names[d], "wr": wr, "avg": avg})
    wd = datetime.datetime.now().weekday()
    return stats, (0 if wd >= 4 else wd + 1)

def _compute_wick_bias(df_1d: pd.DataFrame) -> float:
    """直近5日の上ヒゲ・下ヒゲ圧力から日中ドリフト補正(%)を実測算出"""
    sub = df_1d.tail(5)
    if len(sub) < 3: return 0.0
    o, h, l, c = sub["Open"].values, sub["High"].values, sub["Low"].values, sub["Close"].values
    rng = np.maximum(h - l, 1e-4)
    up_w = float(np.mean((h - np.maximum(o, c)) / rng))
    lo_w = float(np.mean((np.minimum(o, c) - l) / rng))
    return round(float(np.clip((lo_w - up_w) * 0.8, -0.45, 0.45)), 2)

def _compute_vp(df_1d: pd.DataFrame, curr_px: float, is_jp: bool) -> dict:
    sub = df_1d.tail(250)
    if len(sub) < 20: return {"overhead_pct": 0.0, "poc_px": curr_px, "labels": [], "vols": [], "res_px": curr_px, "sup_px": curr_px}
    typ = (sub["High"].values + sub["Low"].values + sub["Close"].values) / 3.0
    vol = sub["Volume"].values.astype(float)
    above_v = float(np.sum(vol[typ > curr_px * 1.01]))
    bins = np.linspace(float(np.min(typ)), float(np.max(typ)) + 1e-4, 15)
    hist = np.bincount(np.clip(np.digitize(typ, bins) - 1, 0, 13), weights=vol, minlength=14)
    centers = [(bins[i] + bins[i + 1]) * 0.5 for i in range(14)]
    a_idx = [i for i, c in enumerate(centers) if c > curr_px * 1.005]
    b_idx = [i for i, c in enumerate(centers) if c < curr_px * 0.995]
    return {
        "overhead_pct": round(above_v / max(float(np.sum(vol)), 1.0) * 100.0, 1),
        "poc_px": float(centers[int(np.argmax(hist))]),
        "labels": [_fmt_cur(c, is_jp) for c in centers], "vols": [round(float(v) / 1e6, 2) for v in hist],
        "res_px": float(centers[max(a_idx, key=lambda i: hist[i])]) if a_idx else curr_px * 1.05,
        "sup_px": float(centers[max(b_idx, key=lambda i: hist[i])]) if b_idx else curr_px * 0.95
    }

def _build_locked_5m_trajectory(
    fc_code: str, curr_px: float, df_1d: pd.DataFrame, df_5m: pd.DataFrame,
    macro_sens: list, macro_data: dict, news_res: dict, whale_anom: dict,
    dow_next_avg: float, vp: dict, is_jp: bool
) -> dict:
    if is_jp:
        am = [f"{h:02d}:{m:02d}" for h in range(9, 12) for m in range(0, 60, 5) if not (h == 11 and m > 30)]
        pm = [f"{h:02d}:{m:02d}" for h in range(12, 16) for m in range(0, 60, 5) if not (h == 12 and m < 30) and not (h == 15 and m > 30)]
        slots, lunch_idx = am + pm, len(am) - 1
    else:
        slots = [f"{h:02d}:{m:02d}" for h in range(9, 17) for m in range(0, 60, 5) if not (h == 9 and m < 30) and not (h == 16 and m > 0)]
        lunch_idx = None

    n_slots = len(slots)
    target_date = _get_target_session_date(is_jp)
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")

    # 当日実測5分足の抽出（ガチ検証用）
    actual_map = {}
    if df_5m is not None and not df_5m.empty:
        tmp_a = df_5m.copy()
        idx_a = pd.to_datetime(tmp_a.index)
        tmp_a["_d"], tmp_a["_hm"] = idx_a.strftime("%Y-%m-%d"), idx_a.strftime("%H:%M")
        if today_str in tmp_a["_d"].values:
            for _, row in tmp_a[tmp_a["_d"] == today_str].iterrows():
                if row["_hm"] in slots:
                    actual_map[row["_hm"]] = round(float(row["Close"]), 2)

    # すでに当日の予測がSQLiteにロック済みならそれを読み込む（場中に予測を書き換えないガチ検証）
    ledger = _dd_db_get("dd_forecast_ledger_v8", {})
    if not isinstance(ledger, dict): ledger = {}
    stock_hist = ledger.get(fc_code, {})
    locked_today = stock_hist.get(today_str)

    if locked_today and actual_map:
        traj = dict(locked_today)
        traj["is_locked"] = True
        traj["actual"] = [actual_map.get(sl, None) for sl in traj["slots"]]
        traj["has_actual"] = True
    else:
        # 新規計算（過去5分足の指数減衰ウェイト＋4層精度アップ）
        slot_means, slot_stds, slot_vols = np.zeros(n_slots), np.full(n_slots, 0.003), np.zeros(n_slots)
        if df_5m is not None and not df_5m.empty:
            tmp = df_5m.copy()
            idx_dt = pd.to_datetime(tmp.index)
            tmp["_d"], tmp["_hm"] = idx_dt.strftime("%Y-%m-%d"), idx_dt.strftime("%H:%M")
            udays = sorted(tmp["_d"].unique().tolist())
            pdays = udays[:-1] if (udays and udays[-1] == today_str) else udays
            rmaps, vmaps, weights = [], [], []
            for di, ds in enumerate(pdays):
                sub = tmp[tmp["_d"] == ds]
                if len(sub) < 10: continue
                op = float(sub["Open"].iloc[0])
                if op <= 0: continue
                rm, vm = {}, {}
                for _, row in sub.iterrows():
                    if row["_hm"] in slots:
                        rm[row["_hm"]] = (float(row["Close"]) - op) / op
                        vm[row["_hm"]] = float(row["Volume"])
                if rm:
                    rmaps.append(rm); vmaps.append(vm); weights.append(float(np.exp(1.2 * (di / max(len(pdays) - 1, 1)))))

            for i, sl in enumerate(slots):
                rv, wv, vv = [], [], []
                for rm, vm, w in zip(rmaps, vmaps, weights):
                    if sl in rm: rv.append(rm[sl]); wv.append(w); vv.append(vm[sl])
                if len(rv) >= 3:
                    wa, ra = np.array(wv) / np.sum(wv), np.array(rv)
                    wm = float(np.sum(wa * ra))
                    slot_means[i] = wm
                    slot_stds[i] = max(float(np.sqrt(np.sum(wa * ((ra - wm) ** 2)))), 0.0025)
                    slot_vols[i] = float(np.mean(vv)) if vv else 0.0
                else:
                    slot_stds[i] = 0.003 + 0.009 * np.sqrt((i + 1) / n_slots)
                    slot_vols[i] = 0.0  # 嘘のU字カーブは描かない

        smap = {x["key"]: x for x in macro_sens}
        mk = "SOX" if ("SOX" in smap and abs(smap["SOX"]["corr"]) > 0.35) else ("NK_FUT" if (is_jp and "NK_FUT" in smap) else "SP500")
        mi = smap.get(mk, {"label": "日経先物" if is_jp else "S&P500", "beta": 0.5, "latest_diff": 0.0})
        fi = smap.get("USDJPY", {"label": "ドル円", "beta": 0.0, "latest_diff": 0.0})
        vix_d = macro_data.get("VIX", {}).get("diff_pct", 0.0)

        mg = (mi["latest_diff"] * mi["beta"]) * 0.45
        fg = (fi["latest_diff"] * fi["beta"]) * 0.35
        ng = news_res["shock_score"] * 0.85
        wg = float(whale_anom["adj_pct"])
        dow_adj = float(np.clip(dow_next_avg * 0.35, -0.4, 0.4))
        wick_adj = _compute_wick_bias(df_1d)

        tot_gap = float(np.clip(mg + fg + ng + wg, -5.0, 5.0))
        est_open = curr_px * (1.0 + tot_gap / 100.0)
        drift = float(np.clip((news_res["shock_score"] * 0.005) + ((dow_adj + wick_adj) / 100.0), -0.025, 0.025))
        vboost = (1.0 + abs(news_res["shock_score"]) * 0.25) * (1.0 + max(0.0, vix_d / 100.0) * 1.2)

        res_wall = vp["res_px"]
        p50, p85, p15, bdiff = [], [], [], []
        for i, sl in enumerate(slots):
            frac = i / max(n_slots - 1, 1)
            mid = est_open * (1.0 + slot_means[i] + drift * frac)
            # しこり壁（抵抗帯）付近での上値抑制補正
            if mid > res_wall * 0.995 and vp["overhead_pct"] >= 35.0:
                mid = res_wall * 0.995 + (mid - res_wall * 0.995) * 0.45
            band = est_open * slot_stds[i] * vboost * 1.15
            lo, hi = max(mid - band, curr_px * 0.5), mid + band
            p50.append(round(float(mid), 2)); p85.append(round(float(hi), 2)); p15.append(round(float(lo), 2))
            bdiff.append(round(float(hi - lo), 2))

        imin, imax = int(np.argmin(p50)), int(np.argmax(p50))
        traj = {
            "target_date": target_date, "base_close": round(curr_px, 2), "is_locked": False,
            "slots": slots, "lunch_idx": lunch_idx, "p50": p50, "p85": p85, "p15": p15, "band_diff": bdiff,
            "vols": [round(float(v), 1) for v in slot_vols],
            "actual": [actual_map.get(sl, None) for sl in slots], "has_actual": bool(actual_map),
            "est_open_px": round(est_open, 2), "est_open_gap_pct": round(tot_gap, 2),
            "est_close_px": p50[-1], "est_close_chg": round((p50[-1] - curr_px) / max(curr_px, 1e-4) * 100.0, 2),
            "dip_idx": imin, "dip_time": slots[imin], "dip_px": p50[imin],
            "peak_idx": imax, "peak_time": slots[imax], "peak_px": p50[imax],
            "bull_trig": round(p85[min(3, n_slots - 1)], 2), "bull_target": round(max(p85), 2),
            "bear_trig": round(p15[min(3, n_slots - 1)], 2), "bear_target": round(min(p15), 2),
            "factors": {
                "mkt_label": mi["label"], "mkt_diff": mi["latest_diff"], "mkt_beta": mi["beta"], "macro_gap_pct": round(mg, 2),
                "fx_diff": fi["latest_diff"], "fx_beta": fi["beta"], "fx_gap_pct": round(fg, 2),
                "news_gap_pct": round(ng, 2), "whale_gap_pct": round(wg, 2), "dow_wick_pct": round(dow_adj + wick_adj, 2)
            }
        }
        # 翌営業日分としてSQLiteにロック保存（1日1回固定）
        if target_date not in stock_hist:
            stock_hist[target_date] = {k: v for k, v in traj.items() if k not in ("actual", "has_actual")}
            if len(stock_hist) > 15:
                for old_k in sorted(stock_hist.keys())[:-15]: del stock_hist[old_k]
            ledger[fc_code] = stock_hist
            _dd_db_set("dd_forecast_ledger_v8", ledger)

    # リアルタイム検証スコアの算出（実測がある場合のみ）
    verify_stats = {"has_verify": False, "in_cone_pct": 0.0, "err_pct": 0.0, "n_pts": 0}
    if traj["has_actual"]:
        in_c, errs = 0, []
        for a, lo, hi, m in zip(traj["actual"], traj["p15"], traj["p85"], traj["p50"]):
            if a is not None:
                if lo <= a <= hi: in_c += 1
                errs.append(abs(a - m) / max(m, 1e-4) * 100.0)
        if errs:
            verify_stats = {"has_verify": True, "in_cone_pct": round(in_c / len(errs) * 100.0, 1), "err_pct": round(float(np.mean(errs)), 2), "n_pts": len(errs)}
    traj["verify"] = verify_stats
    return traj

def _compute_real_5axis(info: dict, ovh_pct: float, gov_cnt: int) -> tuple:
    """欠損値を55点で誤魔化さず、取得できた実測指標のみを正確にスコア化"""
    axes, vals, missing = [], [], []
    pe = info.get("trailingPE")
    if pe and pe > 0:
        axes.append({"name": "割安性", "max": 100}); vals.append(int(np.clip(100 - (pe - 10) * 1.5, 15, 95)))
    else: missing.append("割安性(PER欠損)")
    rg = info.get("revenueGrowth")
    if rg is not None:
        axes.append({"name": "成長性", "max": 100}); vals.append(int(np.clip(55 + rg * 120, 15, 98)))
    else: missing.append("成長性(売上成長率欠損)")
    roe = info.get("returnOnEquity")
    if roe is not None:
        axes.append({"name": "収益性", "max": 100}); vals.append(int(np.clip(45 + roe * 160, 15, 98)))
    else: missing.append("収益性(ROE欠損)")
    axes.append({"name": "需給軽さ", "max": 100}); vals.append(int(np.clip(95 - ovh_pct * 0.85, 15, 95)))
    axes.append({"name": "安全性", "max": 100}); vals.append(int(np.clip(95 - gov_cnt * 18, 20, 98)))
    return axes, vals, missing

@st.cache_data(ttl=600)
def _generate_detailed_memo(
    fc: str, corp_name: str, px_s: str, traj_open: str, traj_close: str,
    bull_trig: str, bull_tgt: str, bear_trig: str, bear_tgt: str,
    dip_t: str, peak_t: str, ovh: float, res_s: str, sup_s: str,
    ml: str, mc: float, mb: float, pos_pct: int, t1: int, gov_cnt: int,
    whale_sum: str, up: str, api_key: str
) -> tuple:
    prompt = f"""あなたはヘッジファンドのシニア・エクイティアナリストです。以下の実測データに基づき、投資判断に直結する「超詳細インベストメントメモ（800〜1,100文字）」を日本語で作成してください。
【実測データ】
・銘柄: {corp_name} ({fc}) / 現在値: {px_s} / アナリスト目標乖離: {up}
・翌営業日予測: 想定始値 {traj_open} → 大引け予測 {traj_close}（押し目候補 {dip_t} / ピーク想定 {peak_t}）
・分岐トリガー: 強気突破 {bull_trig}→上値メド {bull_tgt} / 急落警戒 {bear_trig}→下値メド {bear_tgt}
・需給構造: 上値しこり玉 {ovh}% / 大口売り壁 {res_s} / 大口買い支え {sup_s}
・大口異変: {whale_sum}
・マクロ連動: {ml} (相関 {mc}, β={mb}) / 高信頼ニュース強気度 {pos_pct}% (一次報道{t1}件) / ガバナンスリスク検知 {gov_cnt}件

以下の3セクション構成で、具体的な価格・時間帯・撤退基準まで踏み込んで出力してください：
🟢 Bull Case（強気シナリオ：上がる根拠と突破ライン・上値メド）
🔴 Bear Case（弱気・死角リスク：売り壁・マクロ逆風・ガバナンス懸念と撤退ライン）
⚡ Next Catalyst（注目トリガー：明日の勝負時間帯・大口動向・監視ポイント）"""

    if api_key:
        for mod in ("gemini-2.5-flash", "gemini-2.0-flash"):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent"
                body = json.dumps({"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": 1400, "temperature": 0.6}}).encode("utf-8")
                req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "x-goog-api-key": api_key}, method="POST")
                with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=12.0) as r:
                    rj = json.loads(r.read().decode("utf-8"))
                    txt = "".join([p.get("text", "") for p in rj["candidates"][0]["content"]["parts"] if "text" in p])
                    if txt.strip(): return txt.strip(), f"🔵 AUTO GLOBAL AI ANALYST ({mod} / 一次報道{t1}件反映)"
            except Exception: continue

    bull = (
        f"・現在値 {px_s} に対しアナリスト目標乖離は {up}。高信頼ニュース強気度は {pos_pct}%（一次報道{t1}件）。\n"
        f"・翌営業日は {bull_trig} を明確に上抜ければ強気突破シナリオが発動し、上値メド {bull_tgt} を目指す展開。\n"
        f"・下値は大口買い支え帯 {sup_s} がサポートとして機能しやすい需給構造。"
    )
    bear = (
        f"・{ml} との相関係数が {mc}（β={mb}）と高く、夜間先物や米市場の急変時に連れ安するリスクあり。\n"
        f"・現在値より上の上値しこり玉は {ovh}%、直上の大口売り壁 {res_s} 付近では戻り売りに要注意。\n"
        f"・{bear_trig} を割り込んだ場合は下値メド {bear_tgt} までの下振れを警戒し早期撤退。ガバナンス報道は {gov_cnt}件検知。"
    )
    cat = (
        f"・大口・インサイダー動向: {whale_sum}。\n"
        f"・明日の勝負時間帯は、押し目候補の {dip_t} 前後での反発確認と、ピーク想定の {peak_t} 前後での分割利確。\n"
        f"・寄付直後の値動きが想定始値 {traj_open} を維持できるかが最初の分岐点。"
    )
    return f"🟢 Bull Case（強気シナリオ）\n{bull}\n\n🔴 Bear Case（弱気・死角リスク）\n{bear}\n\n⚡ Next Catalyst（注目トリガー）\n{cat}", f"⚙️ AUTO QUANT MEMO（一次報道{t1}件・実測詳細生成）"

# =========================================================================
# 5. メインエントリ関数（YAMASHISHI LAB から呼び出す）
# =========================================================================
def render_deep_dive_page(init_code: str = "NVDA", init_style: str = "デイトレード", gemini_api_key: str = ""):
    _inject_dd_css()

    h1, h2 = st.columns([3.1, 1.3])
    with h1:
        st.markdown(
            '<div class="glass-header" style="margin-bottom:6px;">'
            '<div class="brand-luxury">YAMASHISHI DEEP DIVE v8</div>'
            '<div style="font-size:10.5px;color:#94a3b8;margin-top:2px;">ガチ検証ロック軌道 × 大口異変検知 × 嘘なし完全実測ターミナル</div>'
            '</div>',
            unsafe_allow_html=True
        )
    with h2:
        st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
        if st.button("⬅️ LABへ戻る", key="dd_back_to_lab_btn", use_container_width=True, type="primary"):
            st.session_state["navigation_page"] = "TOP"
            st.session_state["scroll_top_trig"] = int(time.time() * 1000)
            st.rerun()

    STYLES = ["デイトレード", "スキャルピング", "スイングトレード", "バイ＆ホールド"]
    c1, c2 = st.columns([2.2, 1.6])
    in_code = c1.text_input("銘柄コード", value=init_code, placeholder="例: NVDA / 6920", label_visibility="collapsed", key="dd_code_in")
    in_style = c2.selectbox("スタイル", STYLES, index=STYLES.index(init_style) if init_style in STYLES else 0, label_visibility="collapsed", key="dd_style_in")

    fc = in_code.strip().upper()
    if not fc: return
    if re.match(r"^[0-9]{3}[0-9A-Z]$", fc): fc = f"{fc}.T"
    is_jp = fc.endswith(".T")
    api_k = _get_gemini_key(gemini_api_key)

    def _body():
        _render_live_clock(sync_interval=60)
        data = _load_stock_core(fc)
        macro_data = _load_macro_data()

        if macro_data:
            chips = "".join([f'<div class="dd-macro-chip"><span style="color:#94a3b8;">{macro_data[k]["label"]}</span><span style="color:{"#10b981" if macro_data[k]["diff_pct"]>=0 else "#ef4444"};font-weight:700;">{macro_data[k]["diff_pct"]:+.2f}%</span></div>' for k in ["SOX", "SP500", "NK_FUT", "USDJPY", "US10Y", "OIL", "VIX"] if k in macro_data])
            st.markdown(f'<div class="dd-macro-strip">{chips}</div>', unsafe_allow_html=True)

        df_1d, df_5m, info = data["df_1d"], data["df_5m"], data["info"]
        if df_1d is None or df_1d.empty:
            st.error(f"❌ 銘柄コード `{fc}` の市場データを取得できませんでした。")
            return

        corp_name = info.get("longName") or info.get("shortName") or fc
        short_code = fc.replace(".T", "")
        sector, industry = info.get("sector") or "セクター未分類", info.get("industry") or "-"
        curr_px = float(df_1d["Close"].iloc[-1])
        prev_px = float(df_1d["Close"].iloc[-2]) if len(df_1d) >= 2 else curr_px
        chg_pct = ((curr_px - prev_px) / max(prev_px, 1e-4)) * 100.0
        chg_col = "#10b981" if chg_pct >= 0 else "#ef4444"

        macro_sens = _compute_macro_sens(df_1d["Close"], macro_data)
        dow_stats, next_wd = _compute_dow_edge(df_1d)
        news_res = _fetch_global_intel(corp_name, short_code)
        gov_risks, whale_news = _fetch_gov_and_whales(corp_name, short_code)
        whale_anom = _detect_whale_anomaly(data["insider_tx"], whale_news)
        vp = _compute_vp(df_1d, curr_px, is_jp)
        traj = _build_locked_5m_trajectory(fc, curr_px, df_1d, df_5m, macro_sens, macro_data, news_res, whale_anom, dow_stats[next_wd]["avg"], vp, is_jp)

        # 大口異変緊急アラート（検知時のみ最上部に表示）
        if whale_anom["detected"]:
            is_b = (whale_anom["dir"] == "BULL")
            b_cls = "dd-quant-box" if is_b else "dd-warn-box"
            st.markdown(f'<div class="{b_cls}"><b>🚨 大口・インサイダー異変検知（予測軌道へ {whale_anom["adj_pct"]:+.2f}% 自動反映済）</b><br>{html.escape(whale_anom["summary"])}</div>', unsafe_allow_html=True)

        comp_score = int(np.clip(round(50 + news_res["shock_score"] * 45 - len(gov_risks) * 9 + whale_anom["adj_pct"] * 12), 5, 98))
        meter_lbl = "EXTREME GREED // 極度の強気" if comp_score >= 75 else ("BULLISH // 強気優勢" if comp_score >= 58 else ("NEUTRAL // 均衡・様子見" if comp_score >= 42 else ("FEAR // 警戒・弱気" if comp_score >= 25 else "EXTREME FEAR // リスク警戒")))

        hi_52, lo_52 = float(df_1d["High"].max()), float(df_1d["Low"].min())
        pos_52 = float(np.clip((curr_px - lo_52) / max(hi_52 - lo_52, 1e-4) * 100.0, 2.0, 98.0))
        spark_svg = _build_spark_svg(df_1d["Close"].tail(20).values)
        aura_col = "#10b981" if traj["est_open_gap_pct"] >= 0 else "#ef4444"
        aura_glow = "rgba(16,185,129,0.22)" if traj["est_open_gap_pct"] >= 0 else "rgba(239,68,68,0.22)"
        target_mean = info.get("targetMeanPrice")
        upside_str = f"{((target_mean - curr_px)/curr_px*100):+.1f}%" if (target_mean and curr_px > 0) else "-"
        risk_status, risk_col = (f"⚠️ {len(gov_risks)}件", "#f87171") if gov_risks else ("🟢 クリーン", "#10b981")

        st.markdown(f"""
        <div class="rank-card" style="border-left-color:{aura_col};box-shadow:0 8px 26px {aura_glow};margin-top:4px;margin-bottom:12px;">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;flex-wrap:wrap;">
            <div style="min-width:0;flex:1;">
              <div><span class="pill-badge">{html.escape(fc)}</span><span class="pill-badge" style="border-color:rgba(168,85,247,0.45);background:rgba(168,85,247,0.16);color:#e9d5ff;">{html.escape(in_style)}</span></div>
              <div style="font-size:17.5px;font-weight:800;color:#fff;margin-top:4px;word-break:break-word;">{html.escape(corp_name)}</div>
              <div style="font-size:11px;color:#94a3b8;margin-top:2px;">{html.escape(sector)} / {html.escape(industry)}</div>
            </div>
            <div style="text-align:right;flex-shrink:0;">
              <div style="font-family:'JetBrains Mono',monospace;font-size:19.5px;font-weight:800;color:#fff;">{_fmt_cur(curr_px, is_jp)}</div>
              <div style="font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;color:{chg_col};margin-bottom:3px;">{chg_pct:+.2f}%</div>
              {spark_svg}
            </div>
          </div>
          <div style="margin-top:8px;">
            <div style="display:flex;justify-content:space-between;font-size:9.5px;color:#94a3b8;font-family:'JetBrains Mono',monospace;"><span>52W安 {_fmt_cur(lo_52, is_jp)}</span><span style="color:#7dd3fc;">52W位置 {pos_52:.0f}%</span><span>52W高 {_fmt_cur(hi_52, is_jp)}</span></div>
            <div class="dd-range-track"><div class="dd-range-dot" style="left:{pos_52:.1f}%;"></div></div>
          </div>
          <div class="dd-winrate-bar">
            <div><div class="dd-metric-lbl">寄付き予測</div><div class="dd-metric-val" style="color:{aura_col};">{traj['est_open_gap_pct']:+.2f}%</div></div>
            <div><div class="dd-metric-lbl">アナリスト乖離</div><div class="dd-metric-val" style="color:#fde047;">{upside_str}</div></div>
            <div><div class="dd-metric-lbl">上値しこり玉</div><div class="dd-metric-val" style="color:#c084fc;">{vp['overhead_pct']}%</div></div>
            <div><div class="dd-metric-lbl">ガバナンス</div><div class="dd-metric-val" style="color:{risk_col};">{risk_status}</div></div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        t1, t2, t3, t4 = st.tabs(["翌営業日 1日軌道", "マクロβ・曜日", "財務・大口株主", "リスク・AIメモ"])

        # -----------------------------------------------------------------
        # TAB 1: 5分刻み予測軌道 ＋ ガチ検証 ＋ 初心者ガイド
        # -----------------------------------------------------------------
        with t1:
            lock_tag = "🔒 朝予測ロック中（場中ガチ検証モード）" if traj.get("is_locked") else f"対象営業日: {traj.get('target_date', '-')}"
            st.markdown(f'<div class="dd-traj-header"><div class="dd-traj-title">NEXT SESSION 5M TRAJECTORY <span>// {html.escape(lock_tag)}</span></div></div>', unsafe_allow_html=True)

            if traj["verify"]["has_verify"]:
                v = traj["verify"]
                st.markdown(f'<div class="dd-quant-box"><b>📊 リアルタイム予測 vs 実測 ガチ検証（実測 {v["n_pts"]}本取得済）</b><br>・<b>確率コーン内 収束率:</b> <b style="color:#fde047;">{v["in_cone_pct"]}%</b> ｜ <b>予測中央値との平均誤差:</b> <b>{v["err_pct"]}%</b></div>', unsafe_allow_html=True)

            ml_cfg = {"symbol": ["none", "none"], "lineStyle": {"color": "rgba(148,163,184,0.35)", "type": "dashed"}, "label": {"formatter": "前場/後場", "color": "#94a3b8", "fontSize": 9, "position": "insideEndTop"}, "data": [{"xAxis": traj["lunch_idx"]}]} if traj["lunch_idx"] is not None else {}
            s_list = [
                {"name": "実測平均出来高", "type": "bar", "yAxisIndex": 1, "data": traj["vols"], "itemStyle": {"color": "rgba(148,163,184,0.16)"}, "barMaxWidth": 4},
                {"name": "下限ベース", "type": "line", "yAxisIndex": 0, "data": traj["p15"], "stack": "cone", "lineStyle": {"opacity": 0}, "showSymbol": False, "silent": True},
                {"name": "確率コーン(70%)", "type": "line", "yAxisIndex": 0, "data": traj["band_diff"], "stack": "cone", "lineStyle": {"opacity": 0}, "areaStyle": {"color": "rgba(56, 189, 248, 0.16)"}, "showSymbol": False, "silent": True},
                {"name": "強気上限(85%)", "type": "line", "yAxisIndex": 0, "data": traj["p85"], "lineStyle": {"color": "rgba(16,185,129,0.55)", "width": 1.1, "type": "dashed"}, "showSymbol": False},
                {"name": "予測中央値", "type": "line", "yAxisIndex": 0, "data": traj["p50"], "lineStyle": {"color": "#38bdf8", "width": 2.4}, "showSymbol": False, "markLine": ml_cfg, "markPoint": {"symbolSize": 32, "label": {"fontSize": 9, "color": "#050811", "fontWeight": "bold"}, "data": [{"name": "押目", "coord": [traj["dip_idx"], traj["dip_px"]], "value": "押目", "itemStyle": {"color": "#f59e0b"}}, {"name": "高値", "coord": [traj["peak_idx"], traj["peak_px"]], "value": "高値", "itemStyle": {"color": "#10b981"}}]}},
                {"name": "弱気下限(15%)", "type": "line", "yAxisIndex": 0, "data": traj["p15"], "lineStyle": {"color": "rgba(239,68,68,0.55)", "width": 1.1, "type": "dashed"}, "showSymbol": False}
            ]
            l_names = ["予測中央値", "確率コーン(70%)", "実測平均出来高"]
            if traj["has_actual"]:
                s_list.append({"name": "当日実測(白線)", "type": "line", "yAxisIndex": 0, "data": traj["actual"], "lineStyle": {"color": "#ffffff", "width": 2.8}, "showSymbol": False})
                l_names.insert(0, "当日実測(白線)")
            _render_echarts({
                "backgroundColor": "#0b1120", "tooltip": {"trigger": "axis"},
                "legend": {"data": l_names, "textStyle": {"color": "#cbd5e1", "fontSize": 9.5}, "top": 2},
                "grid": {"top": 32, "bottom": 20, "left": 4, "right": 6, "containLabel": True},
                "xAxis": {"type": "category", "boundaryGap": False, "data": traj["slots"], "axisLabel": {"color": "#94a3b8", "fontSize": 9.5, "interval": "auto", "hideOverlap": True}},
                "yAxis": [{"type": "value", "scale": True, "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.06)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9.5}}, {"type": "value", "show": False, "axisLabel": {"show": False}, "axisTick": {"show": False}, "splitLine": {"show": False}, "max": max(traj["vols"] + [1]) * 4.5}],
                "series": s_list
            }, height=315)

            with st.expander("🔰 このチャートの見方・初心者ガイド（各線の意味）", expanded=False):
                st.markdown("""
                <div class="dd-guide-box">
                ・<b>青い太線（予測中央値）:</b> 過去30日の5分足のクセ・夜間先物・ニュース・大口異変を合成した「最も可能性が高い1日のルート」です。<br>
                ・<b>水色の帯（確率コーン 70%）:</b> 統計的に70%の確率で株価が収まる想定レンジです。上の緑点線が強気上限（85%）、下の赤点線が弱気下限（15%）です。<br>
                ・<b>白い太線（当日実測）:</b> 市場が開くとリアルタイムに伸びていきます。<b>白線が水色の帯を上に抜けたら「想定以上の強さ」</b>、下に割れたら「シナリオ崩れ（撤退サイン）」と判断します。<br>
                ・<b>押目 / 高値ピン:</b> 過去波形上、1日の中で最も安くなりやすい時刻（買い狙い）と高くなりやすい時刻（利確目安）を自動表示しています。
                </div>
                """, unsafe_allow_html=True)

            # 確率コーン定義（15% / 70% / 15%）と完全一致させた嘘なしシナリオカード
            bp = (traj["bull_target"] - curr_px) / max(curr_px, 1e-4) * 100.0
            sp = (traj["bear_target"] - curr_px) / max(curr_px, 1e-4) * 100.0
            st.markdown(f"""
            <div class="dd-sc-stack">
              <div class="dd-sc-card" style="border-left:4px solid #10b981;"><div class="dd-sc-top"><div><div style="font-weight:800;color:#6ee7b7;font-size:12.5px;">上振れ突破シナリオ（統計確率 15%）</div><div style="font-size:11px;color:#cbd5e1;margin-top:2px;">トリガー: <b>{_fmt_cur(traj['bull_trig'], is_jp)}</b> 超えで強気加速</div></div><div style="text-align:right;"><div class="dd-sc-price" style="color:#6ee7b7;">{_fmt_cur(traj['bull_target'], is_jp)}</div><div class="dd-sc-pct" style="color:#10b981;">{bp:+.2f}%</div></div></div><div class="dd-sc-bar-bg"><div class="dd-sc-bar-fill" style="width:15%;background:#10b981;"></div></div></div>
              <div class="dd-sc-card" style="border-left:4px solid #38bdf8;"><div class="dd-sc-top"><div><div style="font-weight:800;color:#7dd3fc;font-size:12.5px;">確率コーン内・標準シナリオ（統計確率 70%）</div><div style="font-size:11px;color:#cbd5e1;margin-top:2px;">押し目: <b>{traj['dip_time']}</b> ({_fmt_cur(traj['dip_px'], is_jp)}) → 高値 <b>{traj['peak_time']}</b></div></div><div style="text-align:right;"><div class="dd-sc-price" style="color:#7dd3fc;">{_fmt_cur(traj['est_close_px'], is_jp)}</div><div class="dd-sc-pct" style="color:#38bdf8;">{traj['est_close_chg']:+.2f}%</div></div></div><div class="dd-sc-bar-bg"><div class="dd-sc-bar-fill" style="width:70%;background:#38bdf8;"></div></div></div>
              <div class="dd-sc-card" style="border-left:4px solid #ef4444;"><div class="dd-sc-top"><div><div style="font-weight:800;color:#fca5a5;font-size:12.5px;">下振れ警戒シナリオ（統計確率 15%）</div><div style="font-size:11px;color:#cbd5e1;margin-top:2px;">トリガー: <b>{_fmt_cur(traj['bear_trig'], is_jp)}</b> 割れで撤退警戒</div></div><div style="text-align:right;"><div class="dd-sc-price" style="color:#fca5a5;">{_fmt_cur(traj['bear_target'], is_jp)}</div><div class="dd-sc-pct" style="color:#ef4444;">{sp:+.2f}%</div></div></div><div class="dd-sc-bar-bg"><div class="dd-sc-bar-fill" style="width:15%;background:#ef4444;"></div></div></div>
            </div>
            """, unsafe_allow_html=True)

            f = traj["factors"]
            st.markdown(f"""
            <div class="dd-dark-box">
              <div style="font-size:11px;font-weight:800;color:#38bdf8;margin-bottom:5px;">FACTOR ATTRIBUTION // 軌道自動修正の内訳（嘘なし実測合算）</div>
              <div class="dd-factor-row"><span>主連動（{html.escape(f['mkt_label'])} {f['mkt_diff']:+.2f}% × β{f['mkt_beta']:+.2f}）</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['macro_gap_pct']>=0 else '#ef4444'};">{f['macro_gap_pct']:+.2f}%</span></div>
              <div class="dd-factor-row"><span>為替（ドル円 {f['fx_diff']:+.2f}% × β{f['fx_beta']:+.2f}）</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['fx_gap_pct']>=0 else '#ef4444'};">{f['fx_gap_pct']:+.2f}%</span></div>
              <div class="dd-factor-row"><span>日英高信頼ニュース修正（一次報道 {news_res['tier1_cnt']}件）</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['news_gap_pct']>=0 else '#ef4444'};">{f['news_gap_pct']:+.2f}%</span></div>
              <div class="dd-factor-row"><span>大口・インサイダー異変補正</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['whale_gap_pct']>=0 else '#ef4444'};">{f['whale_gap_pct']:+.2f}%</span></div>
              <div class="dd-factor-row"><span>曜日エッジ ＋ 直近5日ヒゲ圧力補正</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['dow_wick_pct']>=0 else '#ef4444'};">{f['dow_wick_pct']:+.2f}%</span></div>
              <div class="dd-factor-row"><span>合成・寄付き予測 → 大引け予測</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if traj['est_close_chg']>=0 else '#ef4444'};">{traj['est_open_gap_pct']:+.2f}% → {traj['est_close_chg']:+.2f}%</span></div>
            </div>
            """, unsafe_allow_html=True)

        # -----------------------------------------------------------------
        # TAB 2: 曜日エッジ ＋ マクロβ ＋ 決算サプライズ ＋ 初心者ガイド
        # -----------------------------------------------------------------
        with t2:
            d_cells = "".join([f'<div class="dd-dow-cell" style="{"border:1.5px solid #fde047;background:rgba(250,204,21,0.12);" if d["dow"]==next_wd else ""}"><div style="font-size:10px;color:{"#fde047" if d["dow"]==next_wd else "#94a3b8"};font-weight:800;">{d["label"]}曜 {"★翌" if d["dow"]==next_wd else ""}</div><div style="font-family:JetBrains Mono,monospace;font-size:12.5px;font-weight:800;color:{"#10b981" if d["avg"]>=0 else "#ef4444"};margin-top:2px;">{d["avg"]:+.2f}%</div><div style="font-size:9.5px;color:#cbd5e1;">勝率 {d["wr"]}%</div></div>' for d in dow_stats])
            st.markdown(f'<div class="dd-dark-box"><b>DAY-OF-WEEK EDGE // 曜日別アノマリー（過去1年実測）</b><div class="dd-dow-grid">{d_cells}</div></div>', unsafe_allow_html=True)

            if macro_sens:
                st.markdown("##### マクロ感応度マトリクス（過去90営業日の相関係数）")
                _render_echarts({"backgroundColor": "#0b1120", "tooltip": {"trigger": "axis"}, "grid": {"top": 12, "bottom": 20, "left": 6, "right": 14, "containLabel": True}, "xAxis": {"type": "value", "min": -1, "max": 1, "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.06)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9.5}}, "yAxis": {"type": "category", "data": [x["label"] for x in macro_sens][::-1], "axisLabel": {"color": "#e2e8f0", "fontSize": 10.5}}, "series": [{"type": "bar", "data": [{"value": x["corr"], "itemStyle": {"color": "#10b981" if x["corr"] >= 0 else "#ef4444"}} for x in macro_sens[::-1]]}]}, height=215)

            eh = [e for e in data["earnings_hist"] if e["est"] is not None or e["rep"] is not None]
            if eh:
                st.markdown("##### 決算サプライズ（予想EPS vs 実績EPS）")
                eh_r = eh[::-1]
                _render_echarts({"backgroundColor": "#0b1120", "tooltip": {"trigger": "axis"}, "legend": {"data": ["予想EPS", "実績EPS"], "textStyle": {"color": "#cbd5e1", "fontSize": 10}, "top": 2}, "grid": {"top": 30, "bottom": 20, "left": 6, "right": 10, "containLabel": True}, "xAxis": {"type": "category", "data": [e["date"][2:7] for e in eh_r], "axisLabel": {"color": "#94a3b8", "fontSize": 9.5}}, "yAxis": {"type": "value", "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.06)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9.5}}, "series": [{"name": "予想EPS", "type": "bar", "data": [e["est"] for e in eh_r], "itemStyle": {"color": "#64748b"}}, {"name": "実績EPS", "type": "bar", "data": [{"value": e["rep"], "itemStyle": {"color": "#10b981" if (e["surp"] or 0) >= 0 else "#ef4444"}} for e in eh_r]}]}, height=205)

            with st.expander("🔰 マクロβ・曜日・決算の見方（初心者ガイド）", expanded=False):
                st.markdown("""
                <div class="dd-guide-box">
                ・<b>曜日別アノマリー:</b> 過去1年間で「何曜日に上がりやすいか」の実測データです。黄色枠（★翌）が次の営業日の曜日です。<br>
                ・<b>マクロ感応度（相関）:</b> 緑の棒が長いほど、その指標（例：米SOXやドル円）が上がるとこの株も一緒に上がりやすいことを意味します。赤い棒は逆の動きをします。<br>
                ・<b>決算サプライズ:</b> 灰色の棒（市場の事前予想）を、緑の棒（実際の決算）が上回り続けている銘柄は、機関投資家に好まれ上昇トレンドが続きやすいです。
                </div>
                """, unsafe_allow_html=True)

        # -----------------------------------------------------------------
        # TAB 3: 大口Top10ランキング ＋ 実測レーダー ＋ 仮想板 ＋ 初心者ガイド
        # -----------------------------------------------------------------
        with t3:
            st.markdown("##### 大口投資家・大株主 Top 10 ランキング")
            inst_h = data["inst_holders"]
            if inst_h:
                top_h = sorted(inst_h, key=lambda x: x["pct"], reverse=True)[:10]
                rev_h = top_h[::-1]
                r_cols = ["#f59e0b", "#38bdf8", "#10b981"]
                b_data = []
                for i, x in enumerate(rev_h):
                    ri = len(rev_h) - 1 - i
                    sh_l = _fmt_sh(x["shares"])
                    b_data.append({"value": round(x["pct"], 2), "itemStyle": {"color": r_cols[ri] if ri < 3 else "#6366f1", "borderRadius": [0, 4, 4, 0]}, "label": {"show": True, "position": "right", "color": "#e2e8f0", "fontSize": 9.5, "formatter": f"{x['pct']:.1f}% ({sh_l})" if sh_l != "-" else f"{x['pct']:.1f}%"}})
                _render_echarts({"backgroundColor": "#0b1120", "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}}, "grid": {"top": 10, "bottom": 18, "left": 4, "right": 96, "containLabel": True}, "xAxis": {"type": "value", "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.06)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9, "formatter": "{value}%"}}, "yAxis": {"type": "category", "data": [f"#{len(rev_h)-i} {x['holder'][:14]}" for i, x in enumerate(rev_h)], "axisLabel": {"color": "#f8fafc", "fontSize": 9.5}}, "series": [{"name": "保有比率", "type": "bar", "data": b_data, "barMaxWidth": 15}]}, height=max(210, len(rev_h) * 28))
            elif is_jp:
                st.link_button(f"🏛️ 株探で {short_code} の大株主一覧を見る", f"https://kabutan.jp/stock/holder?code={short_code}", use_container_width=True)

            axes_r, vals_r, miss_r = _compute_real_5axis(info, vp["overhead_pct"], len(gov_risks))
            if len(axes_r) >= 3:
                _render_echarts({"backgroundColor": "#0b1120", "radar": {"radius": "62%", "indicator": axes_r, "axisName": {"color": "#cbd5e1", "fontSize": 10.5}}, "series": [{"type": "radar", "data": [{"value": vals_r, "name": "実測体力", "itemStyle": {"color": "#38bdf8"}, "areaStyle": {"color": "rgba(56,189,248,0.28)"}}]}]}, height=215)
            if miss_r:
                st.caption(f"※ APIデータ未提供のため除外した項目（嘘なし評価）: {', '.join(miss_r)}")

            if vp["labels"]:
                st.markdown("##### 価格帯別出来高（仮想板・しこり玉マップ）")
                _render_echarts({"backgroundColor": "#0b1120", "tooltip": {"trigger": "axis"}, "grid": {"top": 10, "bottom": 20, "left": 6, "right": 14, "containLabel": True}, "xAxis": {"type": "value", "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.06)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9.5}}, "yAxis": {"type": "category", "data": vp["labels"], "axisLabel": {"color": "#cbd5e1", "fontSize": 9.5}}, "series": [{"name": "出来高(M)", "type": "bar", "data": vp["vols"], "itemStyle": {"color": "#a855f7"}}]}, height=230)

            with st.expander("🔰 大口株主・レーダー・価格帯別出来高の見方（初心者ガイド）", expanded=False):
                st.markdown(f"""
                <div class="dd-guide-box">
                ・<b>大口株主ランキング:</b> 世界的な巨大ファンドや優良企業が上位に入っているほど、下値が堅く信頼性が高い傾向があります。<br>
                ・<b>価格帯別出来高（紫の横棒）:</b> 過去1年間に「どの価格帯で一番株が売買されたか」を示します。現在値より上に長い棒（大口売り壁: <b>{_fmt_cur(vp['res_px'], is_jp)}</b>）があると、そこまで上がった時に「やれやれ売り」が出やすくなります。逆に下に長い棒（買い支え: <b>{_fmt_cur(vp['sup_px'], is_jp)}</b>）があると下がりにくくなります。
                </div>
                """, unsafe_allow_html=True)

        # -----------------------------------------------------------------
        # TAB 4: リアル計器メーター ＋ 超詳細AIメモ ＋ 高信頼フィード
        # -----------------------------------------------------------------
        with t4:
            _render_echarts({"backgroundColor": "#0b1120", "series": [{"type": "gauge", "startAngle": 180, "endAngle": 0, "min": 0, "max": 100, "splitNumber": 5, "center": ["50%", "74%"], "radius": "112%", "axisLine": {"lineStyle": {"width": 16, "color": [[0.2, "#dc2626"], [0.4, "#f97316"], [0.6, "#38bdf8"], [0.8, "#10b981"], [1.0, "#059669"]]}}, "pointer": {"icon": "path://M12.8,0.7l12,40.1H0.7L12.8,0.7z", "length": "52%", "width": 10, "offsetCenter": [0, "-12%"], "itemStyle": {"color": "#f8fafc", "shadowBlur": 8, "shadowColor": "rgba(56,189,248,0.8)"}}, "anchor": {"show": True, "showAbove": True, "size": 14, "itemStyle": {"color": "#38bdf8", "borderWidth": 2, "borderColor": "#fff"}}, "axisTick": {"length": 6, "lineStyle": {"color": "auto", "width": 1.5}}, "splitLine": {"length": 12, "lineStyle": {"color": "auto", "width": 2.5}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9.5, "distance": -36}, "title": {"offsetCenter": [0, "18%"], "fontSize": 10.5, "color": "#7dd3fc", "fontWeight": "bold"}, "detail": {"fontSize": 26, "fontWeight": "bold", "offsetCenter": [0, "-3%"], "valueAnimation": True, "color": "#ffffff", "formatter": "{value}"}, "data": [{"value": comp_score, "name": meter_lbl}]}]}, height=225)

            top_m = macro_sens[0] if macro_sens else {"label": "市場指数", "corr": 0.0, "beta": 1.0}
            m_txt, m_src = _generate_detailed_memo(
                fc, corp_name, _fmt_cur(curr_px, is_jp),
                _fmt_cur(traj["est_open_px"], is_jp), _fmt_cur(traj["est_close_px"], is_jp),
                _fmt_cur(traj["bull_trig"], is_jp), _fmt_cur(traj["bull_target"], is_jp),
                _fmt_cur(traj["bear_trig"], is_jp), _fmt_cur(traj["bear_target"], is_jp),
                traj["dip_time"], traj["peak_time"], vp["overhead_pct"],
                _fmt_cur(vp["res_px"], is_jp), _fmt_cur(vp["sup_px"], is_jp),
                top_m["label"], top_m["corr"], top_m["beta"], news_res["pos_pct"],
                news_res["tier1_cnt"], len(gov_risks), whale_anom["summary"], upside_str, api_k
            )
            st.markdown(f'<div class="dd-memo-box"><div style="font-size:10.5px;color:#c084fc;font-weight:800;margin-bottom:6px;">{html.escape(m_src)}</div>{html.escape(m_txt).replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)

            with st.expander("🔰 メーターと高信頼ニュースの見方（初心者ガイド）", expanded=False):
                st.markdown("""
                <div class="dd-guide-box">
                ・<b>総合センチメントメーター:</b> 0（極度の警戒）〜100（極度の強気）で市場の空気を数値化しています。日英の一次報道・大口異変・不祥事リスクを合算しています。<br>
                ・<b>信頼度バッジ（S/A/B）:</b> ロイター・ブルームバーグ・日経・株探などの一次報道を「信頼度S」として最優先し、まとめサイト等のノイズは自動で除外しています。
                </div>
                """, unsafe_allow_html=True)

            if gov_risks:
                st.markdown(f'<div class="dd-warn-box"><b>ガバナンス・不祥事・訴訟関連ヒット ({len(gov_risks)}件)</b><br>' + "<br>".join([f"・{html.escape(x)}" for x in gov_risks]) + '</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="dd-quant-box"><b>ガバナンス・不祥事監査: クリーン</b><br>直近ニュースにおいて不祥事・不正・訴訟などの特異リスクシグナルは検知されていません。</div>', unsafe_allow_html=True)

            if news_res["items"]:
                n_html = "".join([f'<div style="margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid rgba(148,163,184,0.12);"><span style="color:{"#fde047" if it["trust"]=="S" else ("#38bdf8" if it["trust"]=="A" else "#64748b")};font-weight:800;font-size:10px;border:1px solid;padding:0 4px;border-radius:3px;margin-right:4px;">信頼度{it["trust"]}/{it["lang"]}</span><span style="color:{"#10b981" if it["sent"]=="POS" else ("#ef4444" if it["sent"]=="NEG" else "#94a3b8")};font-weight:800;font-size:10px;margin-right:4px;">[{it["sent"]}]</span><a href="{html.escape(it["link"])}" target="_blank" style="color:#e2e8f0;text-decoration:none;font-weight:600;">{html.escape(it["title"])}</a> <span style="color:#64748b;font-size:10px;">({html.escape(it["source"] or "Wire")} / {html.escape(it["pub"])})</span></div>' for it in news_res["items"]])
                st.markdown(f'<div class="dd-dark-box"><b>GLOBAL INTELLIGENCE FEED // 日英高信頼ニュース（一次報道 {news_res["tier1_cnt"]}件）</b><br><br>{n_html}</div>', unsafe_allow_html=True)

    if hasattr(st, "fragment"):
        @st.fragment(run_every="60s")
        def _auto_runner():
            _body()
        _auto_runner()
    else:
        _body()
