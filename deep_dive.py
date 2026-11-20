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

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

DB_PATH = "yamashishi_core.db"


# =========================================================================
# 1. DEEP DIVE v10 専用CSS
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
    .dd-sync-warn { background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.42); border-left: 4px solid #f59e0b; padding: 11px 12px; border-radius: 10px; margin-bottom: 10px; font-size: 12px; line-height: 1.65; color: #fef3c7; }
    .dd-guide-box { background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.28); border-left: 3px solid #38bdf8; padding: 10px 12px; border-radius: 8px; font-size: 11.8px; line-height: 1.7; color: #e0f2fe; }
    .dd-memo-box { background: linear-gradient(180deg, #0b192c 0%, #090d16 100%); border: 1px solid rgba(168, 85, 247, 0.45); border-left: 4px solid #a855f7; padding: 13px 15px; border-radius: 10px; margin-bottom: 10px; font-size: 12.2px; line-height: 1.78; color: #f1f5f9; }
    .dd-factor-row { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 5px 0; border-bottom: 1px solid rgba(148, 163, 184, 0.12); font-size: 11.5px; }
    .dd-factor-row:last-child { border-bottom: none; padding-top: 7px; font-weight: 800; }
    """
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# =========================================================================
# 2. SQLite 予測スナップショット台帳 ＆ 市場現地時刻ヘルパー（夏時間対応）
# =========================================================================
def _dd_db_get(key: str, default_val):
    try:
        conn = sqlite3.connect(DB_PATH, timeout=8.0)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS kv_store (key TEXT PRIMARY KEY, val TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
        cur.execute("SELECT val FROM kv_store WHERE key = ?", (key,))
        row = cur.fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
    except Exception:
        pass
    return default_val


def _dd_db_set(key: str, val):
    try:
        conn = sqlite3.connect(DB_PATH, timeout=8.0)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS kv_store (key TEXT PRIMARY KEY, val TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
        cur.execute(
            "INSERT INTO kv_store (key, val, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(key) DO UPDATE SET val=excluded.val, updated_at=CURRENT_TIMESTAMP;",
            (key, json.dumps(val, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _get_market_now(is_jp: bool) -> datetime.datetime:
    """日本株はAsia/Tokyo、米国株はAmerica/New_York（夏時間自動対応）を返す"""
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    if ZoneInfo is not None:
        try:
            tz = ZoneInfo("Asia/Tokyo" if is_jp else "America/New_York")
            return utc_now.astimezone(tz).replace(tzinfo=None)
        except Exception:
            pass
    offset = datetime.timedelta(hours=9 if is_jp else -5)
    return (utc_now + offset).replace(tzinfo=None)


def _get_target_session_date(is_jp: bool) -> str:
    m_now = _get_market_now(is_jp)
    close_h, close_m = (15, 30) if is_jp else (16, 0)
    if m_now.hour > close_h or (m_now.hour == close_h and m_now.minute >= close_m):
        nxt = m_now + datetime.timedelta(days=1)
        while nxt.weekday() >= 5:
            nxt += datetime.timedelta(days=1)
        return nxt.strftime("%Y-%m-%d")
    d = m_now
    while d.weekday() >= 5:
        d += datetime.timedelta(days=1)
    return d.strftime("%Y-%m-%d")


# =========================================================================
# 3. ヘルパー ＆ データ取得
# =========================================================================
def _fmt_cur(val, is_jp: bool) -> str:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "-"
    return f"{val:,.0f}円" if is_jp else f"${val:,.2f}"


def _fmt_sh(n: int) -> str:
    if not n or n <= 0:
        return "-"
    if n >= 1e9:
        return f"{n/1e9:.2f}B株"
    if n >= 1e6:
        return f"{n/1e6:.1f}M株"
    if n >= 1e4:
        return f"{n/1e4:.1f}万株"
    return f"{n:,}株"


def _get_gemini_key(passed_key: str = "") -> str:
    if passed_key:
        return passed_key.strip()
    k = os.environ.get("GEMINI_API_KEY", "")
    if not k:
        try:
            k = st.secrets.get("GEMINI_API_KEY", "")
        except Exception:
            k = ""
    return str(k).strip()


def _render_echarts(option_dict: dict, height: int = 300, use_hud_tooltip: bool = False, is_jp: bool = False):
    """EChartsレンダラ（use_hud_tooltip=True時はスマホ向け上部固定1行HUDツールチップを有効化）"""
    opt_json = json.dumps(option_dict, ensure_ascii=False)
    cur_sym = "円" if is_jp else "$"
    hud_js = f"""
    if ({'true' if use_hud_tooltip else 'false'}) {{
        opt.tooltip = {{
            trigger: 'axis',
            backgroundColor: 'rgba(9, 13, 22, 0.88)',
            borderColor: 'rgba(56, 189, 248, 0.45)',
            borderWidth: 1,
            padding: [4, 10],
            textStyle: {{ color: '#f8fafc', fontSize: 10.5, fontFamily: 'JetBrains Mono, monospace' }},
            position: function() {{ return [8, 28]; }},
            axisPointer: {{
                type: 'cross',
                lineStyle: {{ color: 'rgba(56, 189, 248, 0.55)', type: 'dashed', width: 1 }},
                crossStyle: {{ color: 'rgba(56, 189, 248, 0.35)' }},
                label: {{ backgroundColor: '#0f172a', borderColor: '#38bdf8', borderWidth: 1, fontSize: 9.5 }}
            }},
            formatter: function(params) {{
                if (!params || !params.length) return '';
                var tm = params[0].axisValue;
                var parts = ['<span style="color:#7dd3fc;font-weight:800;">' + tm + '</span>'];
                var showNames = ['当日実測', 'ライブ修正', '朝ロック', 'VWAP', '想定波形'];
                for (var i = 0; i < params.length; i++) {{
                    var p = params[i];
                    if (showNames.indexOf(p.seriesName) !== -1 && p.value !== null && p.value !== undefined) {{
                        var v = Number(p.value);
                        var vs = {'true' if is_jp else 'false'} ? Math.round(v).toLocaleString() + '円' : '$' + v.toFixed(2);
                        parts.push('<span style="color:' + p.color + ';">●</span> ' + p.seriesName + ': <b>' + vs + '</b>');
                    }}
                }}
                return parts.join(' ｜ ');
            }}
        }};
    }}
    """
    html_code = f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>html,body{{width:100%;height:100%;margin:0;padding:0;background:#0b1120;overflow:hidden;}}#c{{width:100%;height:{height}px;}}</style>
    </head><body><div id="c"></div><script>
      var el = document.getElementById('c');
      var chart = echarts.init(el, 'dark');
      var opt = {opt_json};
      {hud_js}
      chart.setOption(opt);
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
    if len(prices) < 2:
        return ""
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
            except Exception:
                pass
    except Exception:
        pass
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
            if len(holders) >= 10:
                break
    except Exception:
        pass
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
    try:
        info = tkr.info or {}
    except Exception:
        info = {}

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
    except Exception:
        pass

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
    except Exception:
        pass
    if not inst_holders and code.endswith(".T"):
        inst_holders = _fetch_jp_holders(code.replace(".T", ""))

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
    except Exception:
        pass

    return {"df_1d": df_1d, "df_5m": df_5m, "info": info, "earnings_hist": earnings_hist, "inst_holders": inst_holders, "insider_tx": insider_tx}


def _fetch_rss(url: str, lang_tag: str) -> list:
    out = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=4.0) as r:
            for it in ET.fromstring(r.read()).findall("./channel/item")[:10]:
                t = (it.findtext("title") or "").strip()
                if t:
                    out.append({"title": t, "link": (it.findtext("link") or "").strip(), "source": (it.findtext("source") or "").strip(), "pub": (it.findtext("pubDate") or "").strip()[:16], "lang": lang_tag})
    except Exception:
        pass
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
        raw_items.extend(f1.result())
        raw_items.extend(f2.result())

    pos_w = ["上昇", "急騰", "最高益", "上方修正", "増配", "自社株買い", "好調", "提携", "買い", "黒字", "成長", "SURGE", "BEAT", "UPGRADE", "RECORD", "BUY", "GROWTH", "RALLY"]
    neg_w = ["下落", "急落", "下方修正", "赤字", "減益", "不祥事", "訴訟", "不正", "辞任", "懸念", "売り", "リスク", "DROP", "FALL", "MISS", "DOWNGRADE", "LAWSUIT", "PROBE", "CUT", "SLUMP"]
    filtered, seen_t = [], set()
    for it in raw_items:
        src_up = (it["source"] + " " + it["title"]).upper()
        if any(ns.upper() in src_up for ns in NOISE_SOURCES):
            continue
        nk = re.sub(r"\W+", "", it["title"].lower())[:24]
        if nk in seen_t:
            continue
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
# 4. 魔改造エンジン：類似地合い加重 × VWAPモメンタム × 自己学習キャリブレーション
# =========================================================================
def _detect_whale_anomaly(insider_tx: list, whale_news: list) -> dict:
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
        if k == "VIX":
            continue
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
    sub = df_1d.tail(5)
    if len(sub) < 3:
        return 0.0
    o, h, l, c = sub["Open"].values, sub["High"].values, sub["Low"].values, sub["Close"].values
    rng = np.maximum(h - l, 1e-4)
    return round(float(np.clip((float(np.mean((np.minimum(o, c) - l) / rng)) - float(np.mean((h - np.maximum(o, c)) / rng))) * 0.8, -0.45, 0.45)), 2)


def _compute_vp(df_1d: pd.DataFrame, curr_px: float, is_jp: bool) -> dict:
    sub = df_1d.tail(250)
    if len(sub) < 20:
        return {"overhead_pct": 0.0, "poc_px": curr_px, "labels": [], "vols": [], "res_px": curr_px, "sup_px": curr_px}
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


def _compute_self_calibration(stock_hist: dict, df_1d: pd.DataFrame, market_today_str: str) -> tuple:
    """SQLite台帳の過去朝ロック予測 vs 実際の大引けから、直近の予測バイアス（クセ）を自己学習"""
    if not stock_hist or df_1d is None or df_1d.empty:
        return 0.0, 0
    close_map = {idx.strftime("%Y-%m-%d"): float(val) for idx, val in df_1d["Close"].items()}
    diffs = []
    for dt_k in sorted(stock_hist.keys()):
        if dt_k >= market_today_str:
            continue
        if dt_k in close_map:
            p50_arr = stock_hist[dt_k].get("p50")
            if p50_arr and len(p50_arr) > 0:
                pred_c = float(p50_arr[-1])
                act_c = close_map[dt_k]
                if pred_c > 0:
                    diffs.append((act_c - pred_c) / pred_c * 100.0)
    if not diffs:
        return 0.0, 0
    recent = diffs[-5:]
    # 過学習防止のため40%減衰＆±0.5%以内にクリップ
    bias_pct = round(float(np.clip(np.mean(recent) * 0.40, -0.50, 0.50)), 2)
    return bias_pct, len(recent)


def _build_dual_5m_trajectory(
    fc_code: str, curr_px: float, prev_px: float, df_1d: pd.DataFrame, df_5m: pd.DataFrame,
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
    market_today_str = _get_market_now(is_jp).strftime("%Y-%m-%d")
    target_date = _get_target_session_date(is_jp)

    # 市場現地日付ベースで当日実測5分足＆リアルタイムVWAPを抽出
    actual_map, vwap_map = {}, {}
    if df_5m is not None and not df_5m.empty:
        tmp_a = df_5m.copy()
        idx_a = pd.to_datetime(tmp_a.index)
        tmp_a["_d"], tmp_a["_hm"] = idx_a.strftime("%Y-%m-%d"), idx_a.strftime("%H:%M")
        if market_today_str in tmp_a["_d"].values:
            sub_today = tmp_a[tmp_a["_d"] == market_today_str]
            cum_pv, cum_v = 0.0, 0.0
            for _, row in sub_today.iterrows():
                hm = row["_hm"]
                if hm in slots:
                    c_val = float(row["Close"])
                    v_val = max(float(row.get("Volume", 0.0)), 0.0)
                    tp_val = (float(row.get("High", c_val)) + float(row.get("Low", c_val)) + c_val) / 3.0
                    cum_pv += tp_val * v_val
                    cum_v += v_val
                    actual_map[hm] = round(c_val, 2)
                    vwap_map[hm] = round(cum_pv / cum_v, 2) if cum_v > 0 else round(c_val, 2)

    actual_arr = [actual_map.get(sl, None) for sl in slots]
    vwap_arr = [vwap_map.get(sl, None) for sl in slots]
    has_actual = bool(actual_map)
    last_act_idx = max([i for i, v in enumerate(actual_arr) if v is not None], default=-1)
    anchor_base_close = prev_px if has_actual else curr_px

    # マクロ・ニュース・大口要因を先に算出（類似地合いGU/GDフィルタに使うため）
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

    # SQLite台帳から自己学習バイアスを取得
    ledger = _dd_db_get("dd_forecast_ledger_v9", {})
    if not isinstance(ledger, dict):
        ledger = {}
    stock_hist = ledger.get(fc_code, {})
    calib_pct, calib_n = _compute_self_calibration(stock_hist, df_1d, market_today_str)

    # 【魔改造①】類似地合いフィルタリング（GUの日／GDの日で過去波形に2.5倍加重）
    slot_means, slot_stds, slot_vols = np.zeros(n_slots), np.full(n_slots, 0.003), np.zeros(n_slots)
    regime_tag = "標準"
    if df_5m is not None and not df_5m.empty:
        tmp = df_5m.copy()
        idx_dt = pd.to_datetime(tmp.index)
        tmp["_d"], tmp["_hm"] = idx_dt.strftime("%Y-%m-%d"), idx_dt.strftime("%H:%M")
        udays = sorted(tmp["_d"].unique().tolist())
        pdays = [d for d in udays if d != market_today_str]
        rmaps, vmaps, weights = [], [], []
        prev_day_close = None
        want_gu = tot_gap >= 0.15
        want_gd = tot_gap <= -0.15
        regime_tag = "GU類似地合い重視" if want_gu else ("GD類似地合い重視" if want_gd else "フラット加重")

        for di, ds in enumerate(pdays):
            sub = tmp[tmp["_d"] == ds]
            if len(sub) < 10:
                continue
            op = float(sub["Open"].iloc[0])
            cl_end = float(sub["Close"].iloc[-1])
            if op <= 0:
                continue
            day_gap = ((op - prev_day_close) / prev_day_close * 100.0) if (prev_day_close and prev_day_close > 0) else 0.0
            prev_day_close = cl_end

            rm, vm = {}, {}
            for _, row in sub.iterrows():
                if row["_hm"] in slots:
                    rm[row["_hm"]] = (float(row["Close"]) - op) / op
                    vm[row["_hm"]] = float(row["Volume"])
            if rm:
                base_w = float(np.exp(1.2 * (di / max(len(pdays) - 1, 1))))
                # 同じGU/GD地合いの日に2.5倍ウェイト
                if (want_gu and day_gap > 0.1) or (want_gd and day_gap < -0.1):
                    base_w *= 2.5
                rmaps.append(rm)
                vmaps.append(vm)
                weights.append(base_w)

        for i, sl in enumerate(slots):
            rv, wv, vv = [], [], []
            for rm, vm, w in zip(rmaps, vmaps, weights):
                if sl in rm:
                    rv.append(rm[sl])
                    wv.append(w)
                    vv.append(vm[sl])
            if len(rv) >= 3:
                wa, ra = np.array(wv) / np.sum(wv), np.array(rv)
                wm = float(np.sum(wa * ra))
                slot_means[i] = wm
                slot_stds[i] = max(float(np.sqrt(np.sum(wa * ((ra - wm) ** 2)))), 0.0025)
                slot_vols[i] = float(np.mean(vv)) if vv else 0.0
            else:
                slot_stds[i] = 0.003 + 0.009 * np.sqrt((i + 1) / n_slots)
                slot_vols[i] = 0.0

    est_open = anchor_base_close * (1.0 + tot_gap / 100.0)
    drift = float(np.clip((news_res["shock_score"] * 0.005) + ((dow_adj + wick_adj + calib_pct) / 100.0), -0.028, 0.028))
    vboost = (1.0 + abs(news_res["shock_score"]) * 0.25) * (1.0 + max(0.0, vix_d / 100.0) * 1.2)
    res_wall = vp["res_px"]

    # 2層ファンチャート用（50%コア帯 & 85%アウター帯）
    p50, p85, p15, bdiff = [], [], [], []
    p68, p32, bdiff_inner = [], [], []
    for i, sl in enumerate(slots):
        frac = i / max(n_slots - 1, 1)
        mid = est_open * (1.0 + slot_means[i] + drift * frac)
        if mid > res_wall * 0.995 and vp["overhead_pct"] >= 35.0:
            mid = res_wall * 0.995 + (mid - res_wall * 0.995) * 0.45
        band_out = est_open * slot_stds[i] * vboost * 1.15
        band_in = band_out * 0.52
        lo, hi = max(mid - band_out, anchor_base_close * 0.5), mid + band_out
        lo_in, hi_in = max(mid - band_in, anchor_base_close * 0.5), mid + band_in
        p50.append(round(float(mid), 2))
        p85.append(round(float(hi), 2))
        p15.append(round(float(lo), 2))
        bdiff.append(round(float(hi - lo), 2))
        p68.append(round(float(hi_in), 2))
        p32.append(round(float(lo_in), 2))
        bdiff_inner.append(round(float(hi_in - lo_in), 2))

    rng_sim = np.random.default_rng(abs(hash(f"{fc_code}_{target_date}")) % (2**32))
    sim_line = [p50[0]]
    for i in range(1, n_slots):
        pull = (p50[i] - sim_line[-1]) * 0.35
        noise = rng_sim.normal(0, est_open * slot_stds[i] * 0.28)
        sim_line.append(round(float(np.clip(sim_line[-1] + pull + noise, p15[i], p85[i])), 2))

    if has_actual and market_today_str in stock_hist:
        locked_p50 = stock_hist[market_today_str]["p50"]
        locked_p85 = stock_hist[market_today_str]["p85"]
        locked_p15 = stock_hist[market_today_str]["p15"]
        locked_bdiff = stock_hist[market_today_str]["band_diff"]
        locked_p32 = stock_hist[market_today_str].get("p32", [round(m - (m - l) * 0.52, 2) for m, l in zip(locked_p50, locked_p15)])
        locked_bdiff_in = stock_hist[market_today_str].get("band_diff_in", [round(d * 0.52, 2) for d in locked_bdiff])
        locked_sim = stock_hist[market_today_str].get("sim_line", locked_p50)
        is_locked = True
    else:
        locked_p50, locked_p85, locked_p15, locked_bdiff = p50, p85, p15, bdiff
        locked_p32, locked_bdiff_in, locked_sim = p32, bdiff_inner, sim_line
        is_locked = has_actual
        save_key = market_today_str if has_actual else target_date
        if (not has_actual) or (save_key not in stock_hist):
            stock_hist[save_key] = {
                "p50": p50, "p85": p85, "p15": p15, "band_diff": bdiff,
                "p32": p32, "band_diff_in": bdiff_inner, "sim_line": sim_line
            }
            if len(stock_hist) > 15:
                for old_k in sorted(stock_hist.keys())[:-15]:
                    del stock_hist[old_k]
            ledger[fc_code] = stock_hist
            _dd_db_set("dd_forecast_ledger_v9", ledger)

    # 【魔改造②】ライブ修正に「当日VWAP乖離＆直近30分モメンタム」を注入
    live_vwap_bias = 0.0
    if has_actual and last_act_idx >= 0:
        live_p50, live_p85, live_p15, live_bdiff = [None]*n_slots, [None]*n_slots, [None]*n_slots, [None]*n_slots
        live_p32, live_bdiff_in = [None]*n_slots, [None]*n_slots
        anchor_px = actual_arr[last_act_idx]
        anchor_mean = slot_means[last_act_idx]
        cur_vwap = vwap_arr[last_act_idx] or anchor_px
        vwap_gap = (anchor_px - cur_vwap) / max(cur_vwap, 1e-4)

        # 直近6本（30分）のモメンタム
        recent_vals = [v for v in actual_arr[max(0, last_act_idx - 6):last_act_idx + 1] if v is not None]
        mom_30m = ((recent_vals[-1] - recent_vals[0]) / max(recent_vals[0], 1e-4)) if len(recent_vals) >= 2 else 0.0
        live_vwap_bias = float(np.clip(vwap_gap * 0.45 + mom_30m * 0.35, -0.015, 0.015))

        for i in range(last_act_idx, n_slots):
            rem_frac = (i - last_act_idx) / max(n_slots - 1 - last_act_idx, 1)
            rel_move = (slot_means[i] - anchor_mean) + (drift * 0.6 + live_vwap_bias) * rem_frac
            mid = anchor_px * (1.0 + rel_move)
            if mid > res_wall * 0.995 and vp["overhead_pct"] >= 35.0:
                mid = res_wall * 0.995 + (mid - res_wall * 0.995) * 0.45
            band_out = anchor_px * max(slot_stds[i] * np.sqrt(rem_frac + 0.05), 0.0015) * vboost
            band_in = band_out * 0.52
            lo, hi = max(mid - band_out, anchor_px * 0.5), mid + band_out
            lo_in, hi_in = max(mid - band_in, anchor_px * 0.5), mid + band_in
            live_p50[i] = round(float(mid), 2)
            live_p85[i] = round(float(hi), 2)
            live_p15[i] = round(float(lo), 2)
            live_bdiff[i] = round(float(hi - lo), 2)
            live_p32[i] = round(float(lo_in), 2)
            live_bdiff_in[i] = round(float(hi_in - lo_in), 2)
    else:
        live_p50, live_p85, live_p15, live_bdiff = p50, p85, p15, bdiff
        live_p32, live_bdiff_in = p32, bdiff_inner

    verify_stats = {"has_verify": False, "in_cone_pct": 0.0, "err_pct": 0.0, "n_pts": 0}
    if has_actual:
        in_c, errs = 0, []
        for a, lo, hi, m in zip(actual_arr, locked_p15, locked_p85, locked_p50):
            if a is not None:
                if lo <= a <= hi:
                    in_c += 1
                errs.append(abs(a - m) / max(m, 1e-4) * 100.0)
        if errs:
            verify_stats = {"has_verify": True, "in_cone_pct": round(in_c / len(errs) * 100.0, 1), "err_pct": round(float(np.mean(errs)), 2), "n_pts": len(errs)}

    imin, imax = int(np.argmin(locked_p50)), int(np.argmax(locked_p50))
    return {
        "target_date": target_date, "is_locked": is_locked, "has_actual": has_actual, "last_act_idx": last_act_idx,
        "slots": slots, "lunch_idx": lunch_idx, "vols": [round(float(v), 1) for v in slot_vols],
        "actual": actual_arr, "vwap": vwap_arr,
        "locked_p50": locked_p50, "locked_p85": locked_p85, "locked_p15": locked_p15, "locked_bdiff": locked_bdiff,
        "locked_p32": locked_p32, "locked_bdiff_in": locked_bdiff_in, "sim_line": locked_sim,
        "live_p50": live_p50, "live_p85": live_p85, "live_p15": live_p15, "live_bdiff": live_bdiff,
        "live_p32": live_p32, "live_bdiff_in": live_bdiff_in,
        "est_open_px": round(est_open, 2), "est_open_gap_pct": round(tot_gap, 2),
        "est_close_px": locked_p50[-1], "est_close_chg": round((locked_p50[-1] - anchor_base_close) / max(anchor_base_close, 1e-4) * 100.0, 2),
        "dip_idx": imin, "dip_time": slots[imin], "dip_px": locked_p50[imin],
        "peak_idx": imax, "peak_time": slots[imax], "peak_px": locked_p50[imax],
        "bull_trig": round(locked_p85[min(3, n_slots - 1)], 2), "bull_target": round(max(locked_p85), 2),
        "bear_trig": round(locked_p15[min(3, n_slots - 1)], 2), "bear_target": round(min(locked_p15), 2),
        "verify": verify_stats, "regime_tag": regime_tag,
        "factors": {
            "mkt_label": mi["label"], "mkt_diff": mi["latest_diff"], "mkt_beta": mi["beta"], "macro_gap_pct": round(mg, 2),
            "fx_diff": fi["latest_diff"], "fx_beta": fi["beta"], "fx_gap_pct": round(fg, 2),
            "news_gap_pct": round(ng, 2), "whale_gap_pct": round(wg, 2),
            "dow_wick_pct": round(dow_adj + wick_adj, 2),
            "calib_pct": calib_pct, "calib_n": calib_n,
            "live_vwap_pct": round(live_vwap_bias * 100.0, 2)
        }
    }


def _compute_real_5axis(info: dict, ovh_pct: float, gov_cnt: int) -> tuple:
    axes, vals, missing = [], [], []
    pe = info.get("trailingPE")
    if pe and pe > 0:
        axes.append({"name": "割安性", "max": 100})
        vals.append(int(np.clip(100 - (pe - 10) * 1.5, 15, 95)))
    else:
        missing.append("割安性(PER欠損)")
    rg = info.get("revenueGrowth")
    if rg is not None:
        axes.append({"name": "成長性", "max": 100})
        vals.append(int(np.clip(55 + rg * 120, 15, 98)))
    else:
        missing.append("成長性(売上成長率欠損)")
    roe = info.get("returnOnEquity")
    if roe is not None:
        axes.append({"name": "収益性", "max": 100})
        vals.append(int(np.clip(45 + roe * 160, 15, 98)))
    else:
        missing.append("収益性(ROE欠損)")
    axes.append({"name": "需給軽さ", "max": 100})
    vals.append(int(np.clip(95 - ovh_pct * 0.85, 15, 95)))
    axes.append({"name": "安全性", "max": 100})
    vals.append(int(np.clip(95 - gov_cnt * 18, 20, 98)))
    return axes, vals, missing


@st.cache_data(ttl=600)
def _generate_detailed_memo(
    fc: str, corp_name: str, px_s: str, traj_open: str, traj_close: str,
    bull_trig: str, bull_tgt: str, bear_trig: str, bear_tgt: str,
    dip_t: str, peak_t: str, ovh: float, res_s: str, sup_s: str,
    ml: str, mc: float, mb: float, pos_pct: int, t1: int, gov_cnt: int,
    whale_sum: str, up: str, lab_note: str, api_key: str
) -> tuple:
    prompt = f"""あなたはヘッジファンドのシニア・エクイティアナリストです。以下の実測データに基づき「超詳細インベストメントメモ（800〜1,100文字）」を日本語で作成してください。
・銘柄: {corp_name} ({fc}) / 現在値: {px_s} / アナリスト目標乖離: {up}
・LAB本体判定: {lab_note}
・翌営業日予測: 想定始値 {traj_open} → 大引け予測 {traj_close}（押し目候補 {dip_t} / ピーク想定 {peak_t}）
・分岐トリガー: 強気突破 {bull_trig}→上値メド {bull_tgt} / 急落警戒 {bear_trig}→下値メド {bear_tgt}
・需給構造: 上値しこり玉 {ovh}% / 大口売り壁 {res_s} / 大口買い支え {sup_s} / 大口異変: {whale_sum}
・マクロ連動: {ml} (相関 {mc}, β={mb}) / 高信頼ニュース強気度 {pos_pct}% (一次報道{t1}件) / ガバナンスリスク検知 {gov_cnt}件
以下の3セクション構成で具体価格・時間帯・撤退基準まで踏み込んで出力：
🟢 Bull Case（強気シナリオ）
🔴 Bear Case（弱気・死角リスク）
⚡ Next Catalyst（注目トリガー）"""

    if api_key:
        for mod in ("gemini-2.5-flash", "gemini-2.0-flash"):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent"
                body = json.dumps({"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": 1400, "temperature": 0.6}}).encode("utf-8")
                req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "x-goog-api-key": api_key}, method="POST")
                with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=12.0) as r:
                    rj = json.loads(r.read().decode("utf-8"))
                    txt = "".join([p.get("text", "") for p in rj["candidates"][0]["content"]["parts"] if "text" in p])
                    if txt.strip():
                        return txt.strip(), f"🔵 AUTO GLOBAL AI ANALYST ({mod} / 一次報道{t1}件反映)"
            except Exception:
                continue

    bull = f"・LAB本体判定: {lab_note}。現在値 {px_s} に対しアナリスト目標乖離は {up}、高信頼ニュース強気度 {pos_pct}%（一次報道{t1}件）。\n・{bull_trig} を明確に上抜ければ強気突破が発動し、上値メド {bull_tgt} を目指す展開。\n・下値は大口買い支え帯 {sup_s} がサポートとして機能しやすい構造。"
    bear = f"・{ml} との相関係数が {mc}（β={mb}）で、夜間先物や米市場の急変時に連れ安リスクあり。\n・上値しこり玉は {ovh}%、直上の大口売り壁 {res_s} 付近では戻り売りに要注意。\n・{bear_trig} 割れで下値メド {bear_tgt} までの下振れを警戒し早期撤退。ガバナンス報道は {gov_cnt}件検知。"
    cat = f"・大口・インサイダー動向: {whale_sum}。\n・明日の勝負時間帯は押し目候補の {dip_t} 前後での反発確認と、ピーク想定の {peak_t} 前後での分割利確。\n・寄付直後に想定始値 {traj_open} を維持できるかが最初の分岐点。"
    return f"🟢 Bull Case（強気シナリオ）\n{bull}\n\n🔴 Bear Case（弱気・死角リスク）\n{bear}\n\n⚡ Next Catalyst（注目トリガー）\n{cat}", f"⚙️ AUTO QUANT MEMO（一次報道{t1}件・実測詳細生成）"


# =========================================================================
# 5. メインエントリ関数（YAMASHISHI LAB から呼び出す）
# =========================================================================
def render_deep_dive_page(init_code: str = "NVDA", init_style: str = "デイトレード", gemini_api_key: str = "", lab_ctx: dict = None):
    _inject_dd_css()

    h1, h2 = st.columns([3.1, 1.3])
    with h1:
        st.markdown(
            '<div class="glass-header" style="margin-bottom:6px;">'
            '<div class="brand-luxury">YAMASHISHI DEEP DIVE v10</div>'
            '<div style="font-size:10.5px;color:#94a3b8;margin-top:2px;">類似地合い加重 × VWAPモメンタム × 自己学習ファンチャート</div>'
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
    if not fc:
        return
    if re.match(r"^[0-9]{3}[0-9A-Z]$", fc):
        fc = f"{fc}.T"
    is_jp = fc.endswith(".T")
    api_k = _get_gemini_key(gemini_api_key)

    active_lab = lab_ctx if (isinstance(lab_ctx, dict) and lab_ctx.get("full_code") == fc) else None

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
        traj = _build_dual_5m_trajectory(fc, curr_px, prev_px, df_1d, df_5m, macro_sens, macro_data, news_res, whale_anom, dow_stats[next_wd]["avg"], vp, is_jp)

        lab_note = "単体検索モード（LAB未経由）"
        if active_lab:
            l_side = active_lab.get("side", "LONG")
            l_tp, l_sl = float(active_lab.get("tp", 0.0)), float(active_lab.get("sl", 0.0))
            dd_bull = (traj["est_close_chg"] >= 0)
            is_aligned = (l_side == "LONG" and dd_bull) or (l_side == "SHORT" and not dd_bull)
            lab_note = f"LAB判定={l_side} (期待度{active_lab.get('expect_pct',0)}% / TP:{_fmt_cur(l_tp, is_jp)} / SL:{_fmt_cur(l_sl, is_jp)})"
            if is_aligned:
                st.markdown(f'<div class="dd-quant-box"><b>✅ LAB × DEEP DIVE 方向性一致（{l_side} 同期）</b><br>LAB上位足判定（期待度 {active_lab.get("expect_pct",0)}% / {html.escape(active_lab.get("exec_grade","").split("（")[0])}）と5分足予測軌道（{traj["est_close_chg"]:+.2f}%）が一致しています。TP: <b>{_fmt_cur(l_tp, is_jp)}</b> / SL: <b>{_fmt_cur(l_sl, is_jp)}</b></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="dd-sync-warn"><b>⚠️ LAB × DEEP DIVE 方向性に乖離あり（慎重待機推奨）</b><br>LAB上位足判定は <b>{l_side}</b>（期待度 {active_lab.get("expect_pct",0)}%）ですが、5分足短期軌道は <b>{traj["est_close_chg"]:+.2f}%</b> と逆方向を示唆しています。押し目／戻りを待って執行してください。</div>', unsafe_allow_html=True)

        if whale_anom["detected"]:
            b_cls = "dd-quant-box" if whale_anom["dir"] == "BULL" else "dd-warn-box"
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
              <div><span class="pill-badge">{html.escape(fc)}</span><span class="pill-badge" style="border-color:rgba(168,85,247,0.45);background:rgba(168,85,247,0.16);color:#e9d5ff;">{html.escape(in_style)}</span><span class="pill-badge" style="border-color:rgba(56,189,248,0.4);background:rgba(56,189,248,0.12);color:#7dd3fc;">{html.escape(traj['regime_tag'])}</span></div>
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

        with t1:
            modes = ["🔴 ライブ修正", "🔒 朝ロック検証", "⚡ 両方重ね"]
            line_opts = ["2層ファン", "ゾーン帯", "VWAP", "想定波形", "出来高"] + (["LAB TP/SL"] if active_lab else [])
            def_opts = ["2層ファン", "ゾーン帯", "出来高"] + (["VWAP"] if traj["has_actual"] else []) + (["LAB TP/SL"] if active_lab else [])
            if hasattr(st, "pills"):
                chart_mode = st.pills("表示モード", modes, default="⚡ 両方重ね", selection_mode="single", label_visibility="collapsed", key="dd_chart_mode") or "⚡ 両方重ね"
                opt_lines = st.pills("追加ライン", line_opts, default=def_opts, selection_mode="multi", label_visibility="collapsed", key="dd_opt_lines") or []
            else:
                chart_mode = st.radio("表示モード", modes, index=2, horizontal=True, label_visibility="collapsed", key="dd_chart_mode")
                opt_lines = st.multiselect("追加ライン", line_opts, default=def_opts, label_visibility="collapsed", key="dd_opt_lines")

            if traj["verify"]["has_verify"] and chart_mode in ("🔒 朝ロック検証", "⚡ 両方重ね"):
                v = traj["verify"]
                st.markdown(f'<div class="dd-quant-box"><b>📊 朝ロック予測 vs 当日実測 ガチ検証（実測 {v["n_pts"]}本取得済）</b><br>・<b>確率ファン内 収束率:</b> <b style="color:#fde047;">{v["in_cone_pct"]}%</b> ｜ <b>朝予測との平均誤差:</b> <b>{v["err_pct"]}%</b></div>', unsafe_allow_html=True)

            # 水平ライン（前場/後場、LAB TP/SL）
            ml_data = []
            if traj["lunch_idx"] is not None:
                ml_data.append({"xAxis": traj["slots"][traj["lunch_idx"]], "lineStyle": {"color": "rgba(148,163,184,0.3)", "type": "dashed"}, "label": {"formatter": "前場/後場", "color": "#94a3b8", "fontSize": 9, "position": "insideEndTop"}})
            if active_lab and "LAB TP/SL" in opt_lines:
                if float(active_lab.get("tp", 0)) > 0:
                    ml_data.append({"yAxis": round(float(active_lab["tp"]), 2), "lineStyle": {"color": "#10b981", "type": "dashed", "width": 1.5}, "label": {"formatter": f"TP {_fmt_cur(active_lab['tp'], is_jp)}", "color": "#6ee7b7", "fontSize": 9, "position": "insideStartTop"}})
                if float(active_lab.get("sl", 0)) > 0:
                    ml_data.append({"yAxis": round(float(active_lab["sl"]), 2), "lineStyle": {"color": "#ef4444", "type": "dashed", "width": 1.5}, "label": {"formatter": f"SL {_fmt_cur(active_lab['sl'], is_jp)}", "color": "#fca5a5", "fontSize": 9, "position": "insideStartBottom"}})
            ml_cfg = {"symbol": ["none", "none"], "data": ml_data} if ml_data else {}

            # 背景ハイライト（狙い目時間帯＆大口売り壁）
            ma_data = []
            if "ゾーン帯" in opt_lines:
                n_sl = len(traj["slots"])
                d_s, d_e = max(0, traj["dip_idx"] - 2), min(n_sl - 1, traj["dip_idx"] + 2)
                p_s, p_e = max(0, traj["peak_idx"] - 2), min(n_sl - 1, traj["peak_idx"] + 2)
                ma_data.append([{"name": "押目帯", "xAxis": traj["slots"][d_s], "itemStyle": {"color": "rgba(16, 185, 129, 0.09)"}}, {"xAxis": traj["slots"][d_e]}])
                ma_data.append([{"name": "利確帯", "xAxis": traj["slots"][p_s], "itemStyle": {"color": "rgba(239, 68, 68, 0.09)"}}, {"xAxis": traj["slots"][p_e]}])
                if vp["overhead_pct"] >= 25.0:
                    ma_data.append([{"name": "売り壁", "yAxis": round(vp["res_px"] * 0.996, 2), "itemStyle": {"color": "rgba(168, 85, 247, 0.12)"}}, {"yAxis": round(vp["res_px"] * 1.004, 2)}])
            ma_cfg = {"silent": True, "label": {"color": "#94a3b8", "fontSize": 8.5, "position": "insideTop"}, "data": ma_data} if ma_data else {}

            s_list, l_names = [], []
            if "出来高" in opt_lines:
                s_list.append({"name": "出来高", "type": "bar", "yAxisIndex": 1, "data": traj["vols"], "itemStyle": {"color": "rgba(148,163,184,0.14)", "borderRadius": [2, 2, 0, 0]}, "barMaxWidth": 4})

            # 2層グラデーション確率ファンチャート
            if "2層ファン" in opt_lines:
                is_lv = (chart_mode == "🔴 ライブ修正")
                c_p15 = traj["live_p15"] if is_lv else traj["locked_p15"]
                c_bd = traj["live_bdiff"] if is_lv else traj["locked_bdiff"]
                c_p32 = traj["live_p32"] if is_lv else traj["locked_p32"]
                c_bd_in = traj["live_bdiff_in"] if is_lv else traj["locked_bdiff_in"]
                s_list.extend([
                    {"name": "outer_base", "type": "line", "yAxisIndex": 0, "data": c_p15, "stack": "fan_out", "lineStyle": {"opacity": 0}, "showSymbol": False, "silent": True},
                    {"name": "85%帯", "type": "line", "yAxisIndex": 0, "data": c_bd, "stack": "fan_out", "lineStyle": {"opacity": 0}, "areaStyle": {"color": "rgba(99, 102, 241, 0.12)"}, "showSymbol": False, "silent": True},
                    {"name": "inner_base", "type": "line", "yAxisIndex": 0, "data": c_p32, "stack": "fan_in", "lineStyle": {"opacity": 0}, "showSymbol": False, "silent": True},
                    {"name": "50%コア帯", "type": "line", "yAxisIndex": 0, "data": c_bd_in, "stack": "fan_in", "lineStyle": {"opacity": 0}, "areaStyle": {"color": "rgba(56, 189, 248, 0.22)"}, "showSymbol": False, "silent": True},
                ])
                l_names.append("50%コア帯")

            if "VWAP" in opt_lines and traj["has_actual"]:
                s_list.append({"name": "VWAP", "type": "line", "yAxisIndex": 0, "data": traj["vwap"], "lineStyle": {"color": "#f59e0b", "width": 1.6, "type": "dotted"}, "showSymbol": False})
                l_names.append("VWAP")

            if "想定波形" in opt_lines:
                s_list.append({"name": "想定波形", "type": "line", "yAxisIndex": 0, "data": traj["sim_line"], "lineStyle": {"color": "#facc15", "width": 1.8}, "showSymbol": False})
                l_names.append("想定波形")

            if chart_mode in ("🔒 朝ロック検証", "⚡ 両方重ね"):
                is_both = (chart_mode == "⚡ 両方重ね")
                s_list.append({
                    "name": "朝ロック", "type": "line", "yAxisIndex": 0, "data": traj["locked_p50"],
                    "lineStyle": {"color": "#c084fc" if is_both else "#38bdf8", "width": 2.0 if is_both else 2.6, "type": "dashed" if is_both else "solid", "shadowBlur": 8, "shadowColor": "rgba(192,132,252,0.45)"},
                    "showSymbol": False, "markLine": ml_cfg, "markArea": ma_cfg
                })
                l_names.append("朝ロック")

            if chart_mode in ("🔴 ライブ修正", "⚡ 両方重ね"):
                s_list.append({
                    "name": "ライブ修正", "type": "line", "yAxisIndex": 0, "data": traj["live_p50"],
                    "lineStyle": {"color": "#38bdf8", "width": 2.6, "shadowBlur": 12, "shadowColor": "rgba(56,189,248,0.65)"},
                    "showSymbol": False,
                    "markLine": ml_cfg if chart_mode == "🔴 ライブ修正" else {},
                    "markArea": ma_cfg if chart_mode == "🔴 ライブ修正" else {}
                })
                l_names.append("ライブ修正")

            if traj["has_actual"]:
                s_list.append({
                    "name": "当日実測", "type": "line", "yAxisIndex": 0, "data": traj["actual"],
                    "lineStyle": {"color": "#ffffff", "width": 2.8, "shadowBlur": 10, "shadowColor": "rgba(255,255,255,0.65)"},
                    "showSymbol": False
                })
                l_names.insert(0, "当日実測")

            # 発光パルスドット（現在値・押し目・高値ピーク）
            pulse_pts = [
                {"name": "押目", "value": [traj["dip_time"], traj["dip_px"]], "itemStyle": {"color": "#10b981"}},
                {"name": "高値", "value": [traj["peak_time"], traj["peak_px"]], "itemStyle": {"color": "#f43f5e"}}
            ]
            if traj["has_actual"] and traj["last_act_idx"] >= 0:
                li = traj["last_act_idx"]
                pulse_pts.append({"name": "NOW", "value": [traj["slots"][li], traj["actual"][li]], "itemStyle": {"color": "#ffffff"}})
            s_list.append({
                "name": "重要点", "type": "effectScatter", "yAxisIndex": 0, "data": pulse_pts,
                "symbolSize": 8, "rippleEffect": {"brushType": "stroke", "scale": 3.2},
                "label": {"show": True, "position": "top", "formatter": "{b}", "color": "#f8fafc", "fontSize": 9, "fontWeight": "bold"}
            })

            _render_echarts({
                "backgroundColor": "#0b1120",
                "legend": {"data": l_names, "textStyle": {"color": "#cbd5e1", "fontSize": 9.5}, "top": 2, "itemWidth": 14, "itemHeight": 8},
                "grid": {"top": 56, "bottom": 22, "left": 8, "right": 8, "containLabel": True},
                "dataZoom": [{"type": "inside", "xAxisIndex": 0, "filterMode": "none"}],
                "xAxis": {"type": "category", "boundaryGap": False, "data": traj["slots"], "axisLine": {"lineStyle": {"color": "rgba(148,163,184,0.2)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9.5, "interval": "auto", "hideOverlap": True}},
                "yAxis": [
                    {"type": "value", "position": "right", "scale": True, "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.05)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9.5}},
                    {"type": "value", "show": False, "max": max(traj["vols"] + [1]) * 4.8}
                ],
                "series": s_list
            }, height=335, use_hud_tooltip=True, is_jp=is_jp)

            with st.expander("🔰 v10 チャートの見方＆操作ガイド（ピンチズーム対応）", expanded=False):
                st.markdown("""
                <div class="dd-guide-box">
                ・<b>ピンチ＆スワイプ:</b> チャート上で2本指ピンチすると寄り付き30分などを拡大表示できます。タップすると上部に1行HUDで数値が固定表示されます。<br>
                ・<b>2層ファンチャート:</b> 濃い水色が「最も収束しやすい50%コア帯」、外側の薄い藍色が「85%許容帯」です。<br>
                ・<b>背景ハイライト:</b> 薄い緑帯が「押し目狙い時間帯」、薄い赤帯が「利確ピーク時間帯」、薄い紫の横帯が「大口売り壁」です。<br>
                ・<b>VWAP（オレンジ点線）:</b> 機関投資家の平均約定単価。白線（実測）がVWAPより上なら強気優勢、下なら弱気優勢です。
                </div>
                """, unsafe_allow_html=True)

            bp = (traj["bull_target"] - curr_px) / max(curr_px, 1e-4) * 100.0
            sp = (traj["bear_target"] - curr_px) / max(curr_px, 1e-4) * 100.0
            st.markdown(f"""
            <div class="dd-sc-stack">
              <div class="dd-sc-card" style="border-left:4px solid #10b981;"><div class="dd-sc-top"><div><div style="font-weight:800;color:#6ee7b7;font-size:12.5px;">上振れ突破シナリオ（統計確率 15%）</div><div style="font-size:11px;color:#cbd5e1;margin-top:2px;">トリガー: <b>{_fmt_cur(traj['bull_trig'], is_jp)}</b> 超えで強気加速</div></div><div style="text-align:right;"><div class="dd-sc-price" style="color:#6ee7b7;">{_fmt_cur(traj['bull_target'], is_jp)}</div><div class="dd-sc-pct" style="color:#10b981;">{bp:+.2f}%</div></div></div><div class="dd-sc-bar-bg"><div class="dd-sc-bar-fill" style="width:15%;background:#10b981;"></div></div></div>
              <div class="dd-sc-card" style="border-left:4px solid #38bdf8;"><div class="dd-sc-top"><div><div style="font-weight:800;color:#7dd3fc;font-size:12.5px;">確率ファン内・標準シナリオ（統計確率 70%）</div><div style="font-size:11px;color:#cbd5e1;margin-top:2px;">押し目: <b>{traj['dip_time']}</b> ({_fmt_cur(traj['dip_px'], is_jp)}) → 高値 <b>{traj['peak_time']}</b></div></div><div style="text-align:right;"><div class="dd-sc-price" style="color:#7dd3fc;">{_fmt_cur(traj['est_close_px'], is_jp)}</div><div class="dd-sc-pct" style="color:#38bdf8;">{traj['est_close_chg']:+.2f}%</div></div></div><div class="dd-sc-bar-bg"><div class="dd-sc-bar-fill" style="width:70%;background:#38bdf8;"></div></div></div>
              <div class="dd-sc-card" style="border-left:4px solid #ef4444;"><div class="dd-sc-top"><div><div style="font-weight:800;color:#fca5a5;font-size:12.5px;">下振れ警戒シナリオ（統計確率 15%）</div><div style="font-size:11px;color:#cbd5e1;margin-top:2px;">トリガー: <b>{_fmt_cur(traj['bear_trig'], is_jp)}</b> 割れで撤退警戒</div></div><div style="text-align:right;"><div class="dd-sc-price" style="color:#fca5a5;">{_fmt_cur(traj['bear_target'], is_jp)}</div><div class="dd-sc-pct" style="color:#ef4444;">{sp:+.2f}%</div></div></div><div class="dd-sc-bar-bg"><div class="dd-sc-bar-fill" style="width:15%;background:#ef4444;"></div></div></div>
            </div>
            """, unsafe_allow_html=True)

            f = traj["factors"]
            st.markdown(f"""
            <div class="dd-dark-box">
              <div style="font-size:11px;font-weight:800;color:#38bdf8;margin-bottom:5px;">FACTOR ATTRIBUTION // v10 魔改造・軌道自動修正の内訳</div>
              <div class="dd-factor-row"><span>主連動（{html.escape(f['mkt_label'])} {f['mkt_diff']:+.2f}% × β{f['mkt_beta']:+.2f}）</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['macro_gap_pct']>=0 else '#ef4444'};">{f['macro_gap_pct']:+.2f}%</span></div>
              <div class="dd-factor-row"><span>為替（ドル円 {f['fx_diff']:+.2f}% × β{f['fx_beta']:+.2f}）</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['fx_gap_pct']>=0 else '#ef4444'};">{f['fx_gap_pct']:+.2f}%</span></div>
              <div class="dd-factor-row"><span>日英高信頼ニュース修正（一次報道 {news_res['tier1_cnt']}件）</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['news_gap_pct']>=0 else '#ef4444'};">{f['news_gap_pct']:+.2f}%</span></div>
              <div class="dd-factor-row"><span>大口・インサイダー異変補正</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['whale_gap_pct']>=0 else '#ef4444'};">{f['whale_gap_pct']:+.2f}%</span></div>
              <div class="dd-factor-row"><span>曜日エッジ ＋ 直近5日ヒゲ圧力補正</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['dow_wick_pct']>=0 else '#ef4444'};">{f['dow_wick_pct']:+.2f}%</span></div>
              <div class="dd-factor-row"><span>台帳自己学習キャリブレーション（過去{f['calib_n']}日）</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['calib_pct']>=0 else '#ef4444'};">{f['calib_pct']:+.2f}%</span></div>
              <div class="dd-factor-row"><span>場中VWAP＆30分モメンタム補正（ライブ反映）</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['live_vwap_pct']>=0 else '#ef4444'};">{f['live_vwap_pct']:+.2f}%</span></div>
              <div class="dd-factor-row"><span>合成・寄付き予測 → 大引け予測</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if traj['est_close_chg']>=0 else '#ef4444'};">{traj['est_open_gap_pct']:+.2f}% → {traj['est_close_chg']:+.2f}%</span></div>
            </div>
            """, unsafe_allow_html=True)

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
                st.markdown('<div class="dd-guide-box">・<b>曜日別アノマリー:</b> 過去1年で何曜日に上がりやすいかの実測データ（黄色枠が翌営業日）。<br>・<b>マクロ感応度:</b> 緑の棒が長い指標ほど、その指標が上がるとこの株も連れ高しやすい傾向があります。<br>・<b>決算サプライズ:</b> 灰色（予想）を緑（実績）が上回り続ける銘柄は上昇トレンドが続きやすいです。</div>', unsafe_allow_html=True)

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
                st.markdown(f'<div class="dd-guide-box">・<b>大口株主ランキング:</b> 大手機関投資家が上位にいるほど下値が堅い傾向。<br>・<b>価格帯別出来高（紫の棒）:</b> 現在値より上の長い棒（売り壁: <b>{_fmt_cur(vp["res_px"], is_jp)}</b>）は上値の抵抗、下の長い棒（買い支え: <b>{_fmt_cur(vp["sup_px"], is_jp)}</b>）は下値サポートになります。</div>', unsafe_allow_html=True)

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
                news_res["tier1_cnt"], len(gov_risks), whale_anom["summary"], upside_str, lab_note, api_k
            )
            st.markdown(f'<div class="dd-memo-box"><div style="font-size:10.5px;color:#c084fc;font-weight:800;margin-bottom:6px;">{html.escape(m_src)}</div>{html.escape(m_txt).replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)

            with st.expander("🔰 メーターと高信頼ニュースの見方（初心者ガイド）", expanded=False):
                st.markdown('<div class="dd-guide-box">・<b>センチメントメーター:</b> 0（警戒）〜100（強気）で市場の空気を数値化。<br>・<b>信頼度バッジ（S/A/B）:</b> ロイター・ブルームバーグ・日経・株探などの一次報道をSランクとして最優先しています。</div>', unsafe_allow_html=True)

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
