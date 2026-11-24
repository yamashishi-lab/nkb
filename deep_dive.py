import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np
import math, os, re, ssl, html, json, time, sqlite3, datetime, email.utils, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

DB_PATH = "yamashishi_core.db"
WEIGHTS_EVOLUTION_PATH = "weights_evolution_v4.json"
WEIGHTS_KV_KEY = "dd_weights_evolution_v4"
CLUSTER_KEYS = ["JP_LOW", "JP_MID", "JP_HIGH", "US_LOW", "US_MID", "US_HIGH", "JP_ALL", "US_ALL"]

_BRAIN_PRESETS = {
    "TREND": ({"macro": 0.50, "fx": 0.35, "news": 0.95, "whale": 1.10, "lab_bias": 0.45},
              {"news": 0.006, "dow": 0.30, "wick": 0.65, "calib": 0.40, "lab_bias": 0.95}),
    "RANGE": ({"macro": 0.35, "fx": 0.30, "news": 0.70, "whale": 0.90, "lab_bias": 0.25},
              {"news": 0.004, "dow": 0.40, "wick": 0.95, "calib": 0.45, "lab_bias": 0.60}),
    "NEUTRAL": ({"macro": 0.45, "fx": 0.35, "news": 0.85, "whale": 1.00, "lab_bias": 0.35},
                {"news": 0.005, "dow": 0.35, "wick": 0.80, "calib": 0.40, "lab_bias": 0.80}),
}


def _make_default_brain(regime_code: str) -> dict:
    og, idr = _BRAIN_PRESETS.get(regime_code, _BRAIN_PRESETS["NEUTRAL"])
    return {"updates_count": 0, "open_gap": dict(og), "intraday_drift": dict(idr)}


def _make_default_regime_set() -> dict:
    return {k: _make_default_brain(k) for k in ("TREND", "RANGE", "NEUTRAL")}


DEFAULT_WEIGHTS_EVOLUTION = {
    "version": 4, "lr": 0.035, "l2_decay": 0.015, "updates_count": 0, "last_updated": "", "learned_keys": [],
    "clusters": {ck: _make_default_regime_set() for ck in CLUSTER_KEYS},
    "regimes": _make_default_regime_set(),
    "last_decomp": {"date": "-", "code": "-", "cluster": "US_MID", "regime": "NEUTRAL", "open_err_pct": 0.0, "intraday_err_pct": 0.0, "culprit_open": "-", "culprit_intra": "-"},
}


# =========================================================================
# 1. DEEP DIVE v19.0 専用CSS（圧縮版・見た目完全同一）
# =========================================================================
def _inject_dd_css():
    css = (
        '[data-stale="true"]{opacity:1!important;transition:none!important;}'
        '.block-container{padding-top:2.85rem!important;}'
        '.dd-cmd-header{background:linear-gradient(135deg,rgba(11,17,32,.88) 0%,rgba(7,11,20,.94) 100%);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border:1px solid rgba(56,189,248,.24);border-radius:10px;padding:7px 12px;margin-bottom:6px;display:flex;align-items:center;justify-content:space-between;gap:8px;}'
        '.dd-cmd-title{font-family:"JetBrains Mono",monospace;font-size:13.5px;font-weight:800;letter-spacing:.04em;background:linear-gradient(90deg,#f8fafc 0%,#7dd3fc 55%,#c084fc 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1.2;}'
        '.dd-cmd-sub{font-size:9.5px;color:#64748b;margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}'
        '.dd-macro-strip,.dd-status-strip,.dd-inst-ribbon,.dd-chip-ribbon{display:flex;flex-wrap:nowrap;overflow-x:auto;gap:5px;scrollbar-width:none;}'
        '.dd-macro-strip::-webkit-scrollbar,.dd-status-strip::-webkit-scrollbar,.dd-inst-ribbon::-webkit-scrollbar,.dd-chip-ribbon::-webkit-scrollbar,.dd-mtf-bar::-webkit-scrollbar{display:none;}'
        '.dd-macro-strip{padding:2px 0 4px 0;margin-bottom:4px;}'
        '.dd-macro-chip{flex-shrink:0;background:rgba(15,23,42,.72);backdrop-filter:blur(8px);border:1px solid rgba(148,163,184,.14);border-radius:6px;padding:2.5px 7px;font-family:"JetBrains Mono",monospace;font-variant-numeric:tabular-nums;font-size:10px;display:inline-flex;align-items:center;gap:4px;}'
        '.dd-status-strip{padding:1px 0 5px 0;}'
        '.dd-st-pill{flex-shrink:0;font-size:10px;font-weight:700;padding:2.5px 8px;border-radius:99px;border:1px solid;display:inline-flex;align-items:center;gap:4px;font-variant-numeric:tabular-nums;}'
        '.dd-hero-card{background:linear-gradient(145deg,rgba(15,23,42,.78) 0%,rgba(7,11,20,.90) 100%);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border:1px solid rgba(148,163,184,.16);border-left:4px solid #38bdf8;border-radius:12px;padding:11px 13px;margin:4px 0 10px 0;}'
        '.dd-fusion-cmd-card{background:linear-gradient(135deg,rgba(15,23,42,.92) 0%,rgba(8,47,73,.85) 100%);backdrop-filter:blur(10px);border:1.5px solid rgba(56,189,248,.45);border-radius:11px;padding:9px 11px;margin-bottom:8px;font-variant-numeric:tabular-nums;}'
        '.dd-fusion-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:5px;margin-top:7px;}'
        '.dd-fusion-cell{background:rgba(7,11,20,.82);border:1px solid rgba(148,163,184,.18);border-radius:7px;padding:5px 7px;}'
        '.dd-mtf-bar{display:flex;align-items:center;justify-content:space-between;flex-wrap:nowrap;overflow-x:auto;gap:5px;background:rgba(11,17,32,.78);backdrop-filter:blur(8px);border:1px solid rgba(56,189,248,.22);border-radius:8px;padding:4px 8px;margin-bottom:6px;scrollbar-width:none;}'
        '.dd-mtf-pills{display:inline-flex;align-items:center;gap:4px;flex-shrink:0;}'
        '.dd-mtf-led{font-family:"JetBrains Mono",monospace;font-variant-numeric:tabular-nums;font-size:9.8px;font-weight:800;padding:1.5px 6px;border-radius:5px;border:1px solid;display:inline-flex;align-items:center;gap:3px;flex-shrink:0;}'
        '.dd-mtf-sum{font-family:"JetBrains Mono",monospace;font-size:9.8px;font-weight:800;padding:2px 7px;border-radius:99px;background:rgba(15,23,42,.9);border:1px solid rgba(148,163,184,.22);flex-shrink:0;}'
        '.dd-inst-ribbon{gap:6px;padding:2px 0 6px 0;margin-bottom:6px;}'
        '.dd-inst-pill-card{flex:1 0 124px;background:rgba(15,23,42,.72);backdrop-filter:blur(8px);border:1px solid rgba(148,163,184,.14);border-radius:8px;padding:5px 8px;text-align:left;}'
        '.dd-ladder-wrap{background:rgba(7,11,20,.85);border:1px solid rgba(148,163,184,.16);border-radius:8px;padding:7px 9px;font-family:"JetBrains Mono",monospace;font-variant-numeric:tabular-nums;}'
        '.dd-lad-row{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:3.5px 6px;border-radius:5px;font-size:10.5px;margin-bottom:3px;background:rgba(15,23,42,.75);}'
        '.dd-lad-now{display:flex;align-items:center;justify-content:space-between;padding:5px 8px;margin:5px 0;border-radius:6px;background:linear-gradient(90deg,rgba(56,189,248,.18) 0%,rgba(15,23,42,.92) 100%);border:1px solid rgba(56,189,248,.5);font-size:11px;font-weight:800;color:#fff;}'
        '.dd-lad-bar-bg{width:54px;height:5px;background:rgba(148,163,184,.18);border-radius:99px;overflow:hidden;flex-shrink:0;}'
        '.dd-breaking-ticker{display:flex;align-items:center;gap:8px;background:linear-gradient(90deg,rgba(239,68,68,.16) 0%,rgba(15,23,42,.90) 100%);border:1px solid rgba(239,68,68,.42);border-left:3.5px solid #ef4444;border-radius:7px;padding:4px 10px;margin-bottom:6px;font-size:10.8px;color:#fecaca;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}'
        '.dd-breaking-ticker.bull{background:linear-gradient(90deg,rgba(16,185,129,.16) 0%,rgba(15,23,42,.90) 100%);border-color:rgba(16,185,129,.42);border-left-color:#10b981;color:#d1fae5;}'
        '.dd-winrate-bar{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;background:rgba(7,11,20,.65);border:1px solid rgba(148,163,184,.14);border-radius:8px;padding:7px 6px;margin-top:8px;text-align:center;}'
        '.dd-metric-val{font-family:"JetBrains Mono",monospace;font-variant-numeric:tabular-nums;font-size:13px;font-weight:800;color:#38bdf8;margin-top:2px;}'
        '.dd-metric-lbl{font-size:9.5px;color:#64748b;font-weight:700;letter-spacing:.02em;}'
        '.dd-range-track{width:100%;height:5px;background:rgba(148,163,184,.18);border-radius:99px;position:relative;margin:5px 0 3px 0;}'
        '.dd-range-dot{width:10px;height:10px;background:#38bdf8;border:2px solid #fff;border-radius:50%;position:absolute;top:-2.5px;transform:translateX(-50%);box-shadow:0 0 8px rgba(56,189,248,.9);}'
        '.dd-sc-stack{display:grid;grid-template-columns:1fr;gap:8px;margin:8px 0 12px 0;}'
        '.dd-sc-card{background:linear-gradient(145deg,rgba(15,23,42,.78) 0%,rgba(7,11,20,.92) 100%);backdrop-filter:blur(8px);border:1px solid rgba(148,163,184,.16);border-radius:10px;padding:10px 12px;display:flex;flex-direction:column;justify-content:space-between;}'
        '.dd-sc-top{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;}'
        '.dd-sc-price{font-family:"JetBrains Mono",monospace;font-variant-numeric:tabular-nums;font-size:16px;font-weight:800;color:#f8fafc;line-height:1.15;}'
        '.dd-sc-pct{font-family:"JetBrains Mono",monospace;font-variant-numeric:tabular-nums;font-size:10.8px;font-weight:700;margin-top:2px;}'
        '.dd-sc-bar-bg{width:100%;height:4px;background:rgba(148,163,184,.14);border-radius:99px;margin-top:8px;overflow:hidden;}'
        '.dd-sc-bar-fill{height:100%;border-radius:99px;transition:width .3s ease;}'
        '.dd-3way-strip{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;background:rgba(15,23,42,.78);backdrop-filter:blur(8px);border:1px solid rgba(56,189,248,.28);border-radius:8px;padding:5px 10px;margin:5px 0 6px 0;font-family:"JetBrains Mono",monospace;font-variant-numeric:tabular-nums;font-size:10.8px;}'
        '.dd-legend-panel{background:rgba(11,17,32,.74);backdrop-filter:blur(8px);border:1px solid rgba(148,163,184,.16);border-radius:9px;padding:7px 10px;margin:4px 0 8px 0;}'
        '.dd-trans-banner{font-size:11px;font-weight:700;line-height:1.45;padding:5px 9px;border-radius:6px;margin-bottom:6px;border-left:3.5px solid #38bdf8;background:rgba(56,189,248,.09);color:#e0f2fe;}'
        '.dd-trans-banner.exp-up{border-left-color:#10b981;background:rgba(16,185,129,.13);color:#d1fae5;}'
        '.dd-trans-banner.exp-down{border-left-color:#ef4444;background:rgba(239,68,68,.13);color:#fecaca;}'
        '.dd-chip-ribbon{gap:6px;padding:1px 0;}'
        '.dd-leg-pill{flex-shrink:0;display:inline-flex;align-items:center;gap:5px;background:rgba(15,23,42,.85);border:1px solid rgba(148,163,184,.16);border-radius:99px;padding:2px 8px;font-size:9.8px;font-weight:700;color:#cbd5e1;}'
        '.dd-legend-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;}'
        '.dd-leg-card{background:rgba(15,23,42,.85);border:1px solid rgba(148,163,184,.14);border-radius:6px;padding:5px 7px;display:flex;flex-direction:column;gap:2px;}'
        '.dd-leg-head{display:flex;align-items:center;gap:6px;font-size:10px;font-weight:800;color:#f8fafc;}'
        '.dd-leg-desc{font-size:9.3px;color:#94a3b8;line-height:1.3;}'
        '.dd-prob-meter{background:rgba(15,23,42,.74);backdrop-filter:blur(8px);border:1px solid rgba(56,189,248,.20);border-radius:10px;padding:8px 11px;margin:6px 0 8px 0;}'
        '.dd-prob-stack{display:flex;width:100%;height:9px;border-radius:99px;overflow:hidden;background:rgba(7,11,20,.92);margin:6px 0 7px 0;border:1px solid rgba(148,163,184,.18);}'
        '.dd-prob-legend{display:grid;grid-template-columns:repeat(4,1fr);gap:4px;font-family:"JetBrains Mono",monospace;font-variant-numeric:tabular-nums;font-size:9.8px;text-align:center;}'
        '.dd-dow-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:5px;margin-top:6px;}'
        '.dd-dow-cell{background:rgba(15,23,42,.76);border:1px solid rgba(148,163,184,.15);border-radius:7px;padding:6px 4px;text-align:center;font-variant-numeric:tabular-nums;}'
        '.dd-dark-box{background:rgba(15,23,42,.74);backdrop-filter:blur(8px);border:1px solid rgba(148,163,184,.15);padding:11px 13px;border-radius:10px;margin-bottom:10px;font-size:11.8px;line-height:1.65;color:#cbd5e1;}'
        '.dd-warn-box{background:rgba(239,68,68,.10);border:1px solid rgba(239,68,68,.36);border-left:3.5px solid #ef4444;padding:9px 12px;border-radius:9px;margin-bottom:8px;font-size:11.8px;line-height:1.6;color:#fecaca;}'
        '.dd-quant-box{background:rgba(16,185,129,.09);border:1px solid rgba(16,185,129,.32);border-left:3.5px solid #10b981;padding:9px 12px;border-radius:9px;margin-bottom:8px;font-size:11.8px;line-height:1.6;color:#d1fae5;}'
        '.dd-sync-warn{background:rgba(245,158,11,.10);border:1px solid rgba(245,158,11,.38);border-left:3.5px solid #f59e0b;padding:9px 12px;border-radius:9px;margin-bottom:8px;font-size:11.8px;line-height:1.6;color:#fef3c7;}'
        '.dd-guide-box{background:rgba(56,189,248,.08);border:1px solid rgba(56,189,248,.25);border-left:3px solid #38bdf8;padding:10px 12px;border-radius:8px;font-size:11.3px;line-height:1.65;color:#e0f2fe;}'
        '.dd-memo-box{background:linear-gradient(180deg,rgba(15,23,42,.88) 0%,rgba(7,11,20,.95) 100%);border:1px solid rgba(168,85,247,.38);border-left:4px solid #a855f7;padding:13px 15px;border-radius:10px;margin-bottom:10px;font-size:12px;line-height:1.78;color:#f1f5f9;}'
        '.dd-factor-row{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:5px 0;border-bottom:1px solid rgba(148,163,184,.12);font-size:11.3px;font-variant-numeric:tabular-nums;}'
        '.dd-factor-row:last-child{border-bottom:none;padding-top:7px;font-weight:800;}'
        '.dd-ev-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:8px;}'
        '.dd-ev-cell{background:rgba(7,11,20,.78);border:1px solid rgba(56,189,248,.20);border-radius:7px;padding:7px 5px;text-align:center;font-variant-numeric:tabular-nums;}'
        '.dd-val-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:6px;margin:8px 0;}'
        '.dd-val-card{background:rgba(15,23,42,.76);border:1px solid rgba(148,163,184,.15);border-radius:8px;padding:7px 9px;font-variant-numeric:tabular-nums;}'
        '.dd-val-track{width:100%;height:5px;background:rgba(148,163,184,.16);border-radius:99px;position:relative;margin-top:5px;}'
        '.dd-val-fill{height:100%;border-radius:99px;}'
        '@media (min-width:768px){.dd-sc-stack{grid-template-columns:repeat(3,1fr);}}'
        '@media (max-width:640px){.dd-fusion-grid,.dd-winrate-bar,.dd-legend-grid,.dd-prob-legend{grid-template-columns:repeat(2,1fr);}.dd-val-grid{grid-template-columns:1fr;}}'
    )
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# =========================================================================
# 2. SQLite ＆ Supabase 予測スナップショット台帳 ＆ 市場現地時刻ヘルパー
# =========================================================================
def _dd_safe_secret(k: str) -> str:
    for src in (os.environ, getattr(st, "secrets", {})):
        try:
            v = src.get(k, "")
            if v:
                return str(v).strip()
        except Exception:
            pass
    return ""


def _dd_sb_headers(sb_key: str) -> dict:
    return {"apikey": sb_key, "Authorization": f"Bearer {sb_key}", "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}


def _dd_sb_get(key: str):
    sb_url, sb_key = _dd_safe_secret("SUPABASE_URL").rstrip("/"), _dd_safe_secret("SUPABASE_KEY")
    if not sb_url or not sb_key:
        return None
    try:
        req = urllib.request.Request(f"{sb_url}/rest/v1/kv_store?key=eq.{urllib.parse.quote(key)}&select=val", headers=_dd_sb_headers(sb_key), method="GET")
        with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=4.0) as r:
            rows = json.loads(r.read().decode("utf-8"))
            if isinstance(rows, list) and rows and rows[0].get("val") is not None:
                raw_val = rows[0]["val"]
                return json.loads(raw_val) if isinstance(raw_val, str) else raw_val
    except Exception:
        pass
    return None


def _dd_sb_set(key: str, val) -> None:
    sb_url, sb_key = _dd_safe_secret("SUPABASE_URL").rstrip("/"), _dd_safe_secret("SUPABASE_KEY")
    if not sb_url or not sb_key:
        return
    try:
        payload = json.dumps({"key": key, "val": json.dumps(val, ensure_ascii=False), "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(f"{sb_url}/rest/v1/kv_store?on_conflict=key", data=payload, headers=_dd_sb_headers(sb_key), method="POST")
        with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=4.0) as r:
            r.read()
    except Exception:
        pass


def _dd_db_get(key: str, default_val):
    sb_val = _dd_sb_get(key)
    if sb_val is not None:
        return sb_val
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
        cur.execute("INSERT INTO kv_store (key, val, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) ON CONFLICT(key) DO UPDATE SET val=excluded.val, updated_at=CURRENT_TIMESTAMP;", (key, json.dumps(val, ensure_ascii=False)))
        conn.commit()
        conn.close()
    except Exception:
        pass
    _dd_sb_set(key, val)


def _get_market_now(is_jp: bool) -> datetime.datetime:
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    if ZoneInfo is not None:
        try:
            return utc_now.astimezone(ZoneInfo("Asia/Tokyo" if is_jp else "America/New_York")).replace(tzinfo=None)
        except Exception:
            pass
    return (utc_now + datetime.timedelta(hours=9 if is_jp else -5)).replace(tzinfo=None)


def _get_target_session_date(is_jp: bool) -> str:
    m_now = _get_market_now(is_jp)
    close_h, close_m = (15, 30) if is_jp else (16, 0)
    d = m_now + datetime.timedelta(days=1) if (m_now.hour > close_h or (m_now.hour == close_h and m_now.minute >= close_m)) else m_now
    while d.weekday() >= 5:
        d += datetime.timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def _is_valid_premarket_lock_window(is_jp: bool, target_date_str: str) -> bool:
    m_now = _get_market_now(is_jp)
    if m_now.strftime("%Y-%m-%d") != target_date_str:
        return False
    mins = m_now.hour * 60 + m_now.minute
    return (420 <= mins < 540) if is_jp else (450 <= mins < 570)


def _convert_5m_index_to_market_tz(df_intraday: pd.DataFrame, is_jp: bool) -> pd.DatetimeIndex:
    idx = pd.to_datetime(df_intraday.index)
    if ZoneInfo is not None:
        tz_t = ZoneInfo("Asia/Tokyo" if is_jp else "America/New_York")
        idx = idx.tz_localize(tz_t, ambiguous="NaT", nonexistent="shift_forward") if idx.tz is None else idx.tz_convert(tz_t)
        return idx.tz_localize(None)
    if idx.tz is not None:
        idx = idx.tz_convert(datetime.timezone(datetime.timedelta(hours=9 if is_jp else -5))).tz_localize(None)
    return idx


# =========================================================================
# クラスタ別（市場JP/US × ボラティリティ帯LOW/MID/HIGH）3脳SGD・標準化リッジ回帰
# =========================================================================
def _classify_vol_cluster(df_1d: pd.DataFrame, is_jp: bool) -> dict:
    pfx = "JP" if is_jp else "US"
    if df_1d is None or len(df_1d) < 15:
        return {"cluster": f"{pfx}_MID", "fallback": f"{pfx}_ALL", "vol_band": "MID", "atr_pct": 2.0}
    hi, lo, cl = df_1d["High"].values[-15:], df_1d["Low"].values[-15:], df_1d["Close"].values[-15:]
    prev_c = np.roll(cl, 1); prev_c[0] = cl[0]
    tr = np.maximum(hi - lo, np.maximum(np.abs(hi - prev_c), np.abs(lo - prev_c)))
    atr_pct = float(np.mean(tr[-14:] / np.maximum(cl[-14:], 1e-4)) * 100.0)
    band = "LOW" if atr_pct < 1.6 else ("HIGH" if atr_pct > 3.2 else "MID")
    return {"cluster": f"{pfx}_{band}", "fallback": f"{pfx}_ALL", "vol_band": band, "atr_pct": round(atr_pct, 2)}


def _merge_regime_set(dst_set: dict, src_set: dict) -> None:
    if not isinstance(src_set, dict):
        return
    for rc in ("TREND", "RANGE", "NEUTRAL"):
        rb = src_set.get(rc)
        if not isinstance(rb, dict):
            continue
        if "updates_count" in rb:
            dst_set[rc]["updates_count"] = int(rb["updates_count"])
        for grp in ("open_gap", "intraday_drift"):
            if isinstance(rb.get(grp), dict):
                for k, v in rb[grp].items():
                    if k in dst_set[rc][grp]:
                        dst_set[rc][grp][k] = float(v)


def _merge_default_weights(raw: dict) -> dict:
    base = json.loads(json.dumps(DEFAULT_WEIGHTS_EVOLUTION))
    if not isinstance(raw, dict):
        return base
    for k in ("version", "lr", "l2_decay", "updates_count", "last_updated"):
        if k in raw:
            base[k] = raw[k]
    if isinstance(raw.get("learned_keys"), list):
        base["learned_keys"] = list(dict.fromkeys(str(x) for x in raw["learned_keys"]))[-400:]
    raw_clusters = raw.get("clusters") if isinstance(raw.get("clusters"), dict) else {}
    for ck in CLUSTER_KEYS:
        _merge_regime_set(base["clusters"][ck], raw_clusters.get(ck))
    _merge_regime_set(base["regimes"], raw.get("regimes"))
    if isinstance(raw.get("last_decomp"), dict):
        base["last_decomp"].update(raw["last_decomp"])
    return base


def _load_weights_evolution() -> dict:
    sb_val = _dd_sb_get(WEIGHTS_KV_KEY)
    if isinstance(sb_val, dict) and sb_val:
        merged = _merge_default_weights(sb_val)
        try:
            with open(WEIGHTS_EVOLUTION_PATH, "w", encoding="utf-8") as f:
                json.dump(merged, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return merged
    if os.path.exists(WEIGHTS_EVOLUTION_PATH):
        try:
            with open(WEIGHTS_EVOLUTION_PATH, "r", encoding="utf-8") as f:
                disk_val = json.load(f)
            if isinstance(disk_val, dict) and disk_val:
                return _merge_default_weights(disk_val)
        except Exception:
            pass
    db_val = _dd_db_get(WEIGHTS_KV_KEY, None)
    return _merge_default_weights(db_val) if (isinstance(db_val, dict) and db_val) else json.loads(json.dumps(DEFAULT_WEIGHTS_EVOLUTION))


def _save_weights_evolution(w_evo: dict) -> None:
    clean_w = _merge_default_weights(w_evo)
    clean_w["last_updated"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(WEIGHTS_EVOLUTION_PATH, "w", encoding="utf-8") as f:
            json.dump(clean_w, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    _dd_db_set(WEIGHTS_KV_KEY, clean_w)


def _get_shrunk_cluster_brain(w_evo: dict, cluster_key: str, fallback_key: str, regime_code: str) -> tuple:
    c_br = w_evo["clusters"].get(cluster_key, _make_default_regime_set()).get(regime_code, _make_default_brain(regime_code))
    f_br = w_evo["clusters"].get(fallback_key, _make_default_regime_set()).get(regime_code, _make_default_brain(regime_code))
    n_c = int(c_br.get("updates_count", 0))
    alpha = float(np.clip(n_c / (n_c + 8.0), 0.0, 1.0))
    og = {k: round(alpha * float(c_br["open_gap"].get(k, fv)) + (1.0 - alpha) * float(fv), 4) for k, fv in f_br["open_gap"].items()}
    idr = {k: round(alpha * float(c_br["intraday_drift"].get(k, fv)) + (1.0 - alpha) * float(fv), 5 if k == "news" else 4) for k, fv in f_br["intraday_drift"].items()}
    return og, idr, n_c, round(alpha, 2)


def _detect_market_regime(df_1d: pd.DataFrame) -> dict:
    if df_1d is None or len(df_1d) < 25:
        return {"code": "NEUTRAL", "label": "判定不能", "strategy": "標準", "color": "#94a3b8", "er": 0.0}
    c = df_1d["Close"].values
    er = abs(c[-1] - c[-15]) / max(float(np.sum(np.abs(np.diff(c[-15:])))), 1e-4)
    ma20, std20 = float(np.mean(c[-20:])), float(np.std(c[-20:]))
    bbw = (std20 * 4.0) / max(ma20, 1e-4) * 100.0
    if er >= 0.38 or bbw >= 14.0:
        return {"code": "TREND", "label": "トレンド相場", "strategy": "順張り優位", "color": "#10b981", "er": round(er, 2)}
    if er <= 0.18 and bbw <= 9.0:
        return {"code": "RANGE", "label": "レンジ相場", "strategy": "逆張り優位", "color": "#f59e0b", "er": round(er, 2)}
    return {"code": "NEUTRAL", "label": "移行・中立", "strategy": "押し目待ち", "color": "#38bdf8", "er": round(er, 2)}


def _update_weights_two_stage(w_evo: dict, fc_code: str, df_1d: pd.DataFrame, stock_hist: dict, market_today_str: str, cluster_key: str, fallback_key: str) -> tuple:
    updated = _merge_default_weights(w_evo)
    if not isinstance(stock_hist, dict) or df_1d is None or df_1d.empty or not {"Open", "Close"}.issubset(set(df_1d.columns)):
        return updated, False
    rows_1d = [(idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10], float(r["Open"]), float(r["Close"])) for idx, r in df_1d.iterrows() if float(r["Open"]) > 0 and float(r["Close"]) > 0]
    if len(rows_1d) < 2:
        return updated, False

    day_map = {d: (o, c) for d, o, c in rows_1d}
    prev_close_map = {rows_1d[i][0]: rows_1d[i - 1][2] for i in range(1, len(rows_1d))}
    idx_pos_map = {rows_1d[i][0]: i for i in range(len(rows_1d))}
    learned_set = set(updated.get("learned_keys", []))
    lr = float(np.clip(updated.get("lr", 0.035), 0.005, 0.15))
    l2_decay = float(np.clip(updated.get("l2_decay", 0.015), 0.001, 0.08))

    og_bounds = {"macro": (0.15, 1.20), "fx": (0.10, 0.90), "news": (0.20, 1.80), "whale": (0.20, 2.00), "lab_bias": (0.05, 1.00)}
    idr_bounds = {"news": (0.001, 0.015), "dow": (0.05, 0.90), "wick": (0.20, 1.60), "calib": (0.05, 1.00), "lab_bias": (0.10, 1.60)}
    og_scales = {"macro": 1.2, "fx": 0.8, "news": 0.5, "whale": 0.35, "lab_bias": 0.6}
    idr_scales = {"news": 0.5, "dow": 0.35, "wick": 0.30, "calib": 0.35, "lab_bias": 0.6}

    def _sgd_step(x_dict, err_pct, bounds, scales, grp_key, target_brains, def_brain):
        if not x_dict:
            return "-"
        std_x = {k: float(x_dict.get(k, 0.0)) / scales[k] for k in bounds}
        norm_v = sum(v ** 2 for v in std_x.values()) + 0.50
        max_abs, worst_d, worst_k = 0.0, 0.0, "-"
        for k, (b_lo, b_hi) in bounds.items():
            xv = std_x[k]
            if abs(xv) < 1e-5:
                continue
            sc = 0.004 if (grp_key == "intraday_drift" and k == "news") else 1.0
            g_step = lr * err_pct * (xv / norm_v) * sc
            for bi, br in enumerate(target_brains):
                cur_w = br[grp_key][k]
                delta = float(np.clip(g_step * (1.0 if bi == 0 else 0.5) - l2_decay * (cur_w - def_brain[grp_key][k]), -0.055 * sc, 0.055 * sc))
                br[grp_key][k] = round(float(np.clip(cur_w + delta, b_lo, b_hi)), 5 if sc < 1.0 else 4)
                nd = abs(delta) / sc
                if bi == 0 and nd > max_abs:
                    max_abs, worst_d, worst_k = nd, delta / sc, k
        return f"{worst_k}[{'過大' if worst_d < 0 else '過小'}]({worst_d:+.3f})" if worst_k != "-" else "-"

    changed = False
    for dt_k in sorted(stock_hist.keys()):
        learn_id = f"{fc_code}:{dt_k}"
        if dt_k >= market_today_str or learn_id in learned_set or dt_k not in day_map or dt_k not in prev_close_map:
            continue
        snap = stock_hist[dt_k]
        p50_arr = snap.get("p50") or []
        if snap.get("locked_premarket") is not True or not p50_arr:
            continue

        r_code = str(snap.get("regime_code") or "").upper()
        if r_code not in ("TREND", "RANGE", "NEUTRAL"):
            pos = idx_pos_map.get(dt_k, 0)
            r_code = _detect_market_regime(df_1d.iloc[:pos])["code"] if pos >= 25 else "NEUTRAL"
        snap_cluster = str(snap.get("cluster_key") or cluster_key)
        if snap_cluster not in updated["clusters"]:
            snap_cluster = cluster_key

        def_brain = _make_default_brain(r_code)
        target_brains = [updated["clusters"][snap_cluster][r_code], updated["clusters"][fallback_key][r_code], updated["regimes"][r_code]]
        act_open, act_close = day_map[dt_k]
        prev_close = prev_close_map[dt_k]
        pred_open = float(snap.get("pred_open_px") or p50_arr[0] or act_open)
        pred_close = float(p50_arr[-1] or act_close)
        if pred_open <= 0 or pred_close <= 0:
            continue

        act_gap_pct = ((act_open - prev_close) / max(prev_close, 1e-4)) * 100.0
        pred_gap_pct = float(snap["pred_open_gap_pct"]) if snap.get("pred_open_gap_pct") is not None else (((pred_open - prev_close) / max(prev_close, 1e-4)) * 100.0)
        open_err_pct = float(np.clip(act_gap_pct - pred_gap_pct, -6.0, 6.0))
        base_shape_pct = float(snap.get("slot_mean_end_pct", 0.0) or 0.0)
        intraday_err_pct = float(np.clip((((act_close - act_open) / max(act_open, 1e-4)) - ((pred_close - pred_open) / max(pred_open, 1e-4))) * 100.0, -6.0, 6.0))

        fc_saved = snap.get("factor_contribs") if isinstance(snap.get("factor_contribs"), dict) else {}
        culprit_open = _sgd_step(fc_saved.get("open_gap") if isinstance(fc_saved.get("open_gap"), dict) else {}, open_err_pct, og_bounds, og_scales, "open_gap", target_brains, def_brain)
        culprit_intra = _sgd_step(fc_saved.get("intraday_drift") if isinstance(fc_saved.get("intraday_drift"), dict) else {}, intraday_err_pct, idr_bounds, idr_scales, "intraday_drift", target_brains, def_brain)

        for br in target_brains:
            br["updates_count"] = int(br.get("updates_count", 0)) + 1
        updated["last_decomp"] = {"date": dt_k, "code": fc_code, "cluster": snap_cluster, "regime": r_code, "open_err_pct": round(open_err_pct, 3), "intraday_err_pct": round(intraday_err_pct, 3), "culprit_open": culprit_open, "culprit_intra": culprit_intra}
        updated["updates_count"] = int(updated.get("updates_count", 0)) + 1
        learned_set.add(learn_id)
        changed = True

    if changed:
        updated["learned_keys"] = sorted(learned_set)[-400:]
        _save_weights_evolution(updated)
    return updated, changed


# =========================================================================
# 3. ヘルパー ＆ 描画コンポーネント
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
    return f"{n/1e4:.1f}万株" if n >= 1e4 else f"{n:,}株"


def _get_gemini_key(passed_key: str = "") -> str:
    return passed_key.strip() if passed_key else _dd_safe_secret("GEMINI_API_KEY")


def _norm_cdf(x: float) -> float:
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def _calc_first_passage_prob(curr_px: float, target_px: float, rem_sigma_pct: float, rem_drift_pct: float = 0.0) -> float:
    if curr_px <= 0 or target_px <= 0:
        return 0.0
    raw_dist = (target_px - curr_px) / curr_px
    if abs(raw_dist) <= 1e-6:
        return 99.0
    b, mu_t = (raw_dist, rem_drift_pct) if raw_dist > 0 else (-raw_dist, -rem_drift_pct)
    sig_t = max(rem_sigma_pct, 1e-4)
    prob = (_norm_cdf((-b + mu_t) / sig_t) + math.exp(min((2.0 * mu_t * b) / (sig_t ** 2), 50.0)) * _norm_cdf((-b - mu_t) / sig_t)) * 100.0
    return round(float(np.clip(prob, 1.0, 99.0)), 1)


def _calc_two_barrier_tp_prob(curr_px: float, tp_px: float, sl_px: float, is_long: bool, rem_sigma_pct: float, rem_drift_pct: float = 0.0) -> float:
    if curr_px <= 0 or tp_px <= 0 or sl_px <= 0:
        return 0.0
    if is_long:
        if curr_px <= sl_px: return 0.0
        if curr_px >= tp_px: return 99.0
        d_tp, d_sl, mu = math.log(tp_px / curr_px), math.log(curr_px / sl_px), rem_drift_pct
    else:
        if curr_px >= sl_px: return 0.0
        if curr_px <= tp_px: return 99.0
        d_tp, d_sl, mu = math.log(curr_px / tp_px), math.log(sl_px / curr_px), -rem_drift_pct
    sig2 = max(rem_sigma_pct ** 2, 1e-6)
    if abs(mu) < 1e-5:
        p_hit = d_sl / max(d_tp + d_sl, 1e-6)
    else:
        kd = (2.0 * mu) / sig2
        den = math.exp(np.clip(kd * (d_tp + d_sl), -40.0, 40.0)) - 1.0
        p_hit = (math.exp(np.clip(kd * d_sl, -40.0, 40.0)) - 1.0) / den if abs(den) > 1e-9 else (d_sl / max(d_tp + d_sl, 1e-6))
    p_tp = _calc_first_passage_prob(curr_px, tp_px, rem_sigma_pct, rem_drift_pct) / 100.0
    p_sl = _calc_first_passage_prob(curr_px, sl_px, rem_sigma_pct, rem_drift_pct) / 100.0
    return round(float(np.clip(min(p_hit * min(1.0, p_tp + p_sl * (1.0 - p_tp)), p_tp) * 100.0, 1.0, 99.0)), 1)


def _declutter_marklines(ml_list: list, curr_px: float, min_gap_pct: float = 0.45, avoid_left: bool = False) -> list:
    if not ml_list:
        return []
    horiz, others = [], []
    def _prio(t: str) -> int:
        if t.startswith(("TP ", "SL ")): return 100
        if "+1.0R" in t: return 95
        if "OB支持" in t or "窓埋目標" in t: return 90
        if "節目" in t: return 85
        if any(k in t for k in ("PDH", "PDL", "HOD", "LOD")): return 80
        return 70 if "ORB" in t else 60
    for item in ml_list:
        if isinstance(item, dict) and item.get("yAxis") is not None:
            try:
                yv = float(item["yAxis"])
                if math.isfinite(yv) and yv > 0:
                    cp = json.loads(json.dumps(item))
                    lbl = cp.get("label") if isinstance(cp.get("label"), dict) else {}
                    horiz.append((yv, _prio(str(lbl.get("formatter", "")).strip()), cp))
                    continue
            except Exception:
                pass
        others.append(item)
    if not horiz:
        return others
    horiz.sort(key=lambda x: x[0])
    ref_base = max(curr_px if (curr_px and curr_px > 0) else float(np.mean([h[0] for h in horiz])), 1e-4)
    merged = []
    for yv, pr, obj in horiz:
        if merged and abs(yv - merged[-1][0]) / ref_base * 100.0 < 0.22:
            py, ppr, pobj = merged[-1]
            lp = pobj.get("label", {}) if isinstance(pobj.get("label"), dict) else {}
            lc = obj.get("label", {}) if isinstance(obj.get("label"), dict) else {}
            tp, tc = str(lp.get("formatter", "")).strip(), str(lc.get("formatter", "")).strip()
            if tc and tc not in tp:
                lp["formatter"] = f"{tp} / {tc.split(' ')[0]}" if tp else tc
                pobj["label"] = lp
            if pr > ppr:
                merged[-1] = (py, pr, pobj)
            continue
        merged.append((yv, pr, obj))
    cl_gap = max(min_gap_pct * 2.2, 0.95)
    clusters = []
    for ent in merged:
        if not clusters or abs(ent[0] - clusters[-1][-1][0]) / ref_base * 100.0 >= cl_gap:
            clusters.append([ent])
        else:
            clusters[-1].append(ent)
    pos_cycle = ["insideMiddleTop", "insideMiddleBottom"] if avoid_left else ["insideStartTop", "insideStartBottom"]
    out_h = []
    for cl in clusters:
        top3 = {i for i, _ in sorted(enumerate(cl), key=lambda x: (-x[1][1], x[0]))[:3]} if len(cl) >= 4 else set(range(len(cl)))
        vc = 0
        for i, (_, _, obj) in enumerate(cl):
            lbl = obj.get("label") if isinstance(obj.get("label"), dict) else {}
            lbl["show"] = i in top3
            if i in top3:
                lbl["position"] = pos_cycle[vc % 2]
                vc += 1
            obj["label"] = lbl
            out_h.append(obj)
    return others + out_h


def _declutter_pulse_points(pulse_pts: list, slots: list) -> list:
    if not pulse_pts or not slots:
        return pulse_pts
    smap, n_tot = {sl: i for i, sl in enumerate(slots)}, len(slots)
    def _sidx(pt):
        v = pt.get("value")
        return smap.get(str(v[0]), n_tot // 2) if (isinstance(v, (list, tuple)) and len(v) >= 1) else n_tot // 2
    non_now = [_sidx(pt) for pt in pulse_pts if str(pt.get("name", "")) != "NOW"]
    indexed = sorted([(i, _sidx(pt), json.loads(json.dumps(pt))) for i, pt in enumerate(pulse_pts)], key=lambda x: (x[1], 0 if str(x[2].get("name", "")) != "NOW" else 1))
    last_s, last_top, cmap = None, True, {}
    for orig_i, si, pt in indexed:
        nm = str(pt.get("name", ""))
        lbl = pt.get("label") if isinstance(pt.get("label"), dict) else {}
        lbl.update({"align": "left" if si <= 4 else ("right" if si >= n_tot - 5 else "center"), "distance": 6, "backgroundColor": "rgba(7,11,20,0.88)", "padding": [1, 4], "borderRadius": 3})
        if nm == "NOW" and any(abs(si - oi) <= 2 for oi in non_now):
            lbl["show"] = False
            pt["label"] = lbl; cmap[orig_i] = pt; continue
        lbl["show"] = True
        if nm == "押目":
            lbl["position"], last_top = "bottom", False
        elif nm == "高値":
            lbl["position"], last_top = "top", True
        elif last_s is not None and abs(si - last_s) <= 8:
            last_top = not last_top
            lbl["position"] = "top" if last_top else "bottom"
        else:
            lbl["position"], last_top = "top", True
        pt["label"] = lbl; last_s = si; cmap[orig_i] = pt
    return [cmap[i] for i in range(len(pulse_pts))]


def _render_echarts(option_dict: dict, height: int = 300, use_hud_tooltip: bool = False, is_jp: bool = False, enable_fullscreen: bool = False, is_dual_grid: bool = False, chart_key: str = "dd_chart_default"):
    opt_json = json.dumps(option_dict, ensure_ascii=False)
    safe_ck = re.sub(r"[^A-Za-z0-9_\-]", "_", str(chart_key or "dd_chart_default"))
    is_jp_js = "true" if is_jp else "false"
    hud_js = f"""
    if ({'true' if use_hud_tooltip else 'false'}) {{
      opt.tooltip = {{
        trigger:'axis',confine:true,backgroundColor:'transparent',borderWidth:0,padding:0,extraCssText:'display:none !important;pointer-events:none !important;',
        axisPointer:{{type:'cross',lineStyle:{{color:'rgba(56,189,248,0.5)',type:'dashed',width:1}},crossStyle:{{color:'rgba(56,189,248,0.32)'}},label:{{backgroundColor:'#0f172a',borderColor:'#38bdf8',borderWidth:1,fontSize:9}}}},
        formatter:function(params){{
          var hudEl=document.getElementById('hud-line');if(!params||!params.length)return '';
          var parts=['<span style="color:#7dd3fc;font-weight:800;">'+params[0].axisValue+'</span>'];
          var sm={{'当日実測':'実測','ライブ修正':'ライブ','朝ロック':'ロック','朝ロック(無効化済)':'旧想定','VWAP':'VWAP','類似実測(Top-1)':'類似1位','上昇分岐':'▲上','横ばい分岐':'▶横','下落分岐':'▼下','9EMA':'9EMA','20EMA':'20EMA'}};
          for(var i=0;i<params.length;i++){{
            var p=params[i];
            if(p.seriesName==='1分足'&&Array.isArray(p.value)&&p.value.length>=5){{
              var o=Number(p.value[1]),c=Number(p.value[2]),l=Number(p.value[3]),h=Number(p.value[4]);
              if(!isNaN(o)){{var f=function(x){{return {is_jp_js}?Math.round(x).toLocaleString():x.toFixed(2);}};parts.push('始:<b>'+f(o)+'</b> 高:<b>'+f(h)+'</b> 安:<b>'+f(l)+'</b> 終:<b>'+f(c)+'</b>');}}
            }}else if(sm[p.seriesName]&&p.value!=null){{
              var v=Number(p.value),vs={is_jp_js}?Math.round(v).toLocaleString()+'円':'$'+v.toFixed(2);
              parts.push('<span style="color:'+p.color+';">●</span>'+sm[p.seriesName]+':<b>'+vs+'</b>');
            }}else if(p.seriesName==='疑似CVD'&&p.value!=null){{
              var cv=Number(p.value),ac=Math.abs(cv),cs=ac>=1e8?(cv/1e8).toFixed(2)+'億':(ac>=1e4?(cv/1e4).toFixed(1)+'万':Math.round(cv).toLocaleString());
              parts.push('<span style="color:#22d3ee;">●</span>CVD:<b>'+(cv>=0?'+':'')+cs+'</b>');
            }}
          }}
          if(hudEl)hudEl.innerHTML=parts.join(' ');return '';
        }}
      }};
    }}
    """
    top_bar = '<div id="top-bar"><div id="hud-line">👆 タップ / ホバーで精密数値表示</div><div id="ctrl-bar"><span id="fs-hint">FS中（60s更新OFF推奨）</span><button id="rst-btn" onclick="resetZoom()" title="拡大ズームを初期状態へリセット">↺</button><button id="fs-btn" onclick="toggleFS()" title="スマホ横向きフル大画面">⛶ 横拡大</button></div></div>' if (enable_fullscreen or use_hud_tooltip) else ""
    html_code = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>html,body{{width:100%;height:100%;margin:0;padding:0;background:#070b14;overflow:hidden;}}#wrap{{display:flex;flex-direction:column;width:100%;height:100%;background:#070b14;overflow:hidden;}}#wrap.force-landscape{{position:fixed!important;top:0!important;left:100vw!important;transform:rotate(90deg)!important;transform-origin:top left!important;z-index:999999!important;}}#top-bar{{height:28px;min-height:28px;max-height:28px;background:#0b1120;border-bottom:1px solid rgba(148,163,184,.16);display:flex;align-items:center;justify-content:space-between;gap:6px;padding:0 6px;box-sizing:border-box;flex-shrink:0;}}#hud-line{{flex:1;min-width:0;font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;font-size:9.8px;color:#94a3b8;white-space:nowrap;overflow-x:auto;scrollbar-width:none;}}#hud-line::-webkit-scrollbar{{display:none;}}#hud-line b{{color:#f8fafc;}}#ctrl-bar{{display:inline-flex;align-items:center;gap:4px;flex-shrink:0;}}#fs-hint{{display:none;background:rgba(15,23,42,.9);color:#fde047;border:1px solid rgba(250,204,21,.4);border-radius:4px;padding:1px 5px;font-size:8.8px;font-weight:700;font-family:'JetBrains Mono',sans-serif;white-space:nowrap;}}#wrap.is-fs #fs-hint{{display:inline-block;}}#rst-btn,#fs-btn{{background:rgba(15,23,42,.92);color:#7dd3fc;border:1px solid rgba(56,189,248,.42);border-radius:5px;padding:1.5px 6px;font-size:9.8px;font-weight:700;cursor:pointer;font-family:'JetBrains Mono',sans-serif;line-height:1.2;}}#rst-btn{{padding:1.5px 5px;color:#cbd5e1;}}#rst-btn:active,#fs-btn:active{{background:rgba(56,189,248,.25);}}#c{{flex:1;min-height:0;width:100%;}}</style>
    </head><body><div id="wrap">{top_bar}<div id="c"></div></div><script>
      var STORAGE_KEY='dd_dz_'+{json.dumps(safe_ck)},IS_DUAL={'true' if is_dual_grid else 'false'},ENABLE_FS={'true' if enable_fullscreen else 'false'},USE_HUD={'true' if use_hud_tooltip else 'false'};
      var el=document.getElementById('c'),wrap=document.getElementById('wrap'),btn=document.getElementById('fs-btn');
      var chart=echarts.init(el,'dark',{{renderer:'canvas',devicePixelRatio:Math.min(window.devicePixelRatio||2,3)}}),opt={opt_json};
      opt.animationDuration=280;opt.animationDurationUpdate=220;opt.animationEasing='cubicOut';
      if(opt.legend){{Object.assign(opt.legend,{{type:'scroll',top:2,left:6,right:8,pageIconColor:'#7dd3fc',pageIconInactiveColor:'#475569',pageTextStyle:{{color:'#94a3b8',fontSize:9}}}});}}
      if(IS_DUAL&&Array.isArray(opt.yAxis)&&opt.yAxis.length>=3){{opt.yAxis[2].axisLabel=Object.assign({{}},opt.yAxis[2].axisLabel||{{}},{{formatter:function(v){{var n=Number(v);if(isNaN(n))return v;var a=Math.abs(n),s=n<0?'-':'';return a>=1e8?s+(a/1e8).toFixed(1)+'億':(a>=1e4?s+Math.round(a/1e4)+'万':Math.round(n).toString());}}}});}}
      {hud_js}
      var savedZoom=null;try{{var rz=sessionStorage.getItem(STORAGE_KEY);if(rz){{var pz=JSON.parse(rz);if(pz&&typeof pz.start==='number'&&typeof pz.end==='number')savedZoom=pz;}}}}catch(e){{}}
      var origGridNormal=opt.grid?JSON.parse(JSON.stringify(opt.grid)):null;
      if(opt.dataZoom&&Array.isArray(opt.dataZoom)&&opt.dataZoom.length>0){{
        var xt=IS_DUAL?[0,1]:0,zs=savedZoom?savedZoom.start:0,ze=savedZoom?savedZoom.end:100;
        opt.dataZoom=[{{type:'inside',xAxisIndex:xt,filterMode:'none',throttle:16,start:zs,end:ze}},{{type:'slider',show:false,xAxisIndex:xt,filterMode:'none',throttle:16,height:IS_DUAL?16:18,bottom:IS_DUAL?5:6,borderColor:'rgba(56,189,248,0.35)',fillerColor:'rgba(56,189,248,0.18)',textStyle:{{color:'#94a3b8',fontSize:9}},start:zs,end:ze}}];
      }}
      chart.setOption(opt);
      if(USE_HUD){{chart.getZr().on('globalout',function(){{var h=document.getElementById('hud-line');if(h)h.innerHTML='👆 タップ / ホバーで精密数値表示';}});}}
      chart.on('datazoom',function(){{try{{var d0=chart.getOption().dataZoom[0];if(typeof d0.start==='number'&&typeof d0.end==='number')sessionStorage.setItem(STORAGE_KEY,JSON.stringify({{start:d0.start,end:d0.end}}));}}catch(e){{}}}});
      function resetZoom(){{try{{sessionStorage.removeItem(STORAGE_KEY);}}catch(e){{}}chart.dispatchAction({{type:'dataZoom',start:0,end:100}});}}
      function getCurZoomRange(){{try{{var d0=chart.getOption().dataZoom[0];return {{start:d0.start||0,end:d0.end||100}};}}catch(e){{}}return {{start:0,end:100}};}}
      function applyLayout(isFS){{
        var topH=document.getElementById('top-bar')?28:0;
        if(!isFS){{if(wrap){{wrap.classList.remove('is-fs','force-landscape');wrap.style.cssText='display:flex;flex-direction:column;width:100%;height:100%;background:#070b14;overflow:hidden;';}}var wN=wrap?wrap.clientWidth:el.clientWidth,hN=wrap?Math.max(wrap.clientHeight-topH,80):el.clientHeight;wN>0&&hN>0?chart.resize({{width:wN,height:hN}}):chart.resize();return;}}
        if(wrap)wrap.classList.add('is-fs');var w=window.innerWidth,h=window.innerHeight;
        if(h>w){{if(wrap){{wrap.classList.add('force-landscape');wrap.style.width=h+'px';wrap.style.height=w+'px';}}chart.resize({{width:h,height:Math.max(w-topH,100)}});}}
        else{{if(wrap){{wrap.classList.remove('force-landscape');wrap.style.width='100%';wrap.style.height='100%';}}chart.resize({{width:w,height:Math.max(h-topH,100)}});}}
      }}
      function updateZoomMode(isFS){{
        if(!opt.dataZoom)return;var zr=getCurZoomRange(),xt=IS_DUAL?[0,1]:0,ng=origGridNormal;
        if(isFS){{if(IS_DUAL&&Array.isArray(origGridNormal)&&origGridNormal.length>=2){{ng=[{{top:40,height:'53%',left:6,right:origGridNormal[0].right,containLabel:false}},{{top:'70%',height:'15%',left:6,right:origGridNormal[1].right,containLabel:false}}];}}else if(origGridNormal&&!Array.isArray(origGridNormal)){{ng=Object.assign({{}},origGridNormal,{{bottom:44,top:40}});}}}}
        chart.setOption({{grid:ng,dataZoom:[{{type:'inside',xAxisIndex:xt,filterMode:'none',throttle:16,start:zr.start,end:zr.end}},{{type:'slider',show:isFS,xAxisIndex:xt,filterMode:'none',throttle:16,start:zr.start,end:zr.end}}]}});
      }}
      function toggleFS(){{
        if(!ENABLE_FS)return;var d=document,isFS=!!(d.fullscreenElement||d.webkitFullscreenElement);
        if(!isFS){{var t=d.documentElement,rq=t.requestFullscreen||t.webkitRequestFullscreen;if(rq)Promise.resolve(rq.call(t)).then(function(){{if(screen.orientation&&screen.orientation.lock)screen.orientation.lock('landscape').catch(function(){{}});setTimeout(function(){{applyLayout(true);}},180);setTimeout(function(){{applyLayout(true);}},420);}}).catch(function(){{}});}}
        else{{var ex=d.exitFullscreen||d.webkitExitFullscreen;if(ex)ex.call(d);if(screen.orientation&&screen.orientation.unlock)try{{screen.orientation.unlock();}}catch(e){{}}}}
      }}
      function onFSChange(){{var isFS=!!(document.fullscreenElement||document.webkitFullscreenElement);if(btn)btn.textContent=isFS?'✕ 戻す':'⛶ 横拡大';updateZoomMode(isFS);[0,120,350,650].forEach(function(ms){{setTimeout(function(){{applyLayout(isFS);}},ms);}});}}
      var rt=null;function scheduleResize(){{if(rt)clearTimeout(rt);rt=setTimeout(function(){{applyLayout(!!(document.fullscreenElement||document.webkitFullscreenElement));}},80);}}
      window.addEventListener('resize',scheduleResize);if(typeof ResizeObserver!=='undefined')new ResizeObserver(scheduleResize).observe(wrap||el);
      if(ENABLE_FS){{document.addEventListener('fullscreenchange',onFSChange);document.addEventListener('webkitfullscreenchange',onFSChange);window.addEventListener('orientationchange',function(){{setTimeout(function(){{applyLayout(!!(document.fullscreenElement||document.webkitFullscreenElement));}},240);}});}}
      setTimeout(scheduleResize,90);setTimeout(scheduleResize,320);
    </script></body></html>"""
    components.html(html_code, height=height + 2)


def _render_live_clock(sync_interval: int = 60, active: bool = True):
    dot_col, st_lbl, b_col, l_col = ("#10b981", "LIVE FEED", "rgba(16,185,129,.28)", "#6ee7b7") if active else ("#f59e0b", "PAUSED", "rgba(245,158,11,.38)", "#fde047")
    r_html = f'SILENT SYNC <span id="cd" class="cnt">{sync_interval}s</span>' if active else '<span style="color:#f59e0b;font-weight:700;">自動更新 停止中（拡大・精査保護）</span>'
    components.html(f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>html,body{{width:100%;margin:0;padding:0;background:transparent;font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;}}.bar{{display:flex;justify-content:space-between;align-items:center;background:rgba(15,23,42,.75);border:1px solid {b_col};border-radius:7px;padding:3px 9px;font-size:10px;color:#e2e8f0;}}.dot{{width:6px;height:6px;background:{dot_col};border-radius:50%;display:inline-block;margin-right:5px;box-shadow:0 0 7px {dot_col};}}.left{{display:flex;align-items:center;color:{l_col};font-weight:700;}}.right{{color:#94a3b8;font-size:9.5px;}}.cnt{{color:#38bdf8;font-weight:700;}}</style></head><body><div class="bar"><div class="left"><span class="dot"></span>{st_lbl} <span id="clk" style="margin-left:7px;color:#fff;">--:--:--</span> JST</div><div class="right">{r_html}</div></div><script>var rem={sync_interval},act={'true' if active else 'false'};function tick(){{var n=new Date(),j=new Date(n.getTime()+(n.getTimezoneOffset()+540)*60000);document.getElementById('clk').textContent=String(j.getHours()).padStart(2,'0')+':'+String(j.getMinutes()).padStart(2,'0')+':'+String(j.getSeconds()).padStart(2,'0');if(act){{var cd=document.getElementById('cd');if(cd)cd.textContent=rem+'s';rem=rem>1?rem-1:{sync_interval};}}}}tick();setInterval(tick,1000);</script></body></html>""", height=26)


def _build_spark_svg(prices: np.ndarray) -> str:
    if len(prices) < 2:
        return ""
    p_min, span = float(np.min(prices)), max(float(np.max(prices)) - float(np.min(prices)), 1e-4)
    pts = [f"{round((i/max(len(prices)-1,1))*88.0,1)},{round(22.0-((float(p)-p_min)/span)*20.0,1)}" for i, p in enumerate(prices)]
    return f'<svg width="88" height="24" viewBox="0 0 88 24" style="display:block;margin-left:auto;"><polyline fill="none" stroke="{"#10b981" if prices[-1]>=prices[0] else "#ef4444"}" stroke-width="1.6" points="{" ".join(pts)}"/></svg>'


def _render_chart_legend_panel(traj: dict, chart_mode: str, opt_lines: list, short_3way: dict, exp_reg: dict, active_dip_time: str, active_peak_time: str, cur_vwap_now, curr_px: float, is_jp: bool, active_lab, is_1m_zoom: bool = False, zoom_1m_data: dict = None):
    exp_active, exp_dir = bool(exp_reg.get("active")), exp_reg.get("dir", "NONE")
    sw_l = lambda c, st="solid", w=2: f'<span style="display:inline-block;width:14px;height:0;border-top:{w}px {st} {c};flex-shrink:0;"></span>'
    sw_b = lambda bg, bd: f'<span style="display:inline-block;width:14px;height:9px;background:{bg};border:1px solid {bd};border-radius:2px;flex-shrink:0;"></span>'
    tri_sw = '<span style="display:inline-flex;flex-direction:column;gap:2px;width:14px;flex-shrink:0;"><span style="border-top:1.5px dashed #10b981;"></span><span style="border-top:1.5px dotted #94a3b8;"></span><span style="border-top:1.5px dashed #ef4444;"></span></span>'

    if is_1m_zoom and isinstance(zoom_1m_data, dict) and zoom_1m_data.get("valid"):
        e9, e20 = zoom_1m_data.get("last_ema9", curr_px), zoom_1m_data.get("last_ema20", curr_px)
        if curr_px >= e9 >= e20:
            b_cls, b_txt = "dd-trans-banner exp-up", "⚡ 1分足ズーム(直近90分)：パーフェクトオーダー上昇中（現在値 > 9EMA > 20EMA）→ 9EMA押し目買い優位"
        elif curr_px <= e9 <= e20:
            b_cls, b_txt = "dd-trans-banner exp-down", "⚡ 1分足ズーム(直近90分)：パーフェクトオーダー下落中（現在値 < 9EMA < 20EMA）→ 9EMA戻り売り・撤退優位"
        else:
            b_cls, b_txt = "dd-trans-banner", "⚡ 1分足ズーム(直近90分)：9EMAと20EMAが交錯する揉み合い局面 → 下段CVDとVWAPの方向確定待ち"
        c_sw = '<span style="display:inline-flex;align-items:center;gap:2px;width:14px;flex-shrink:0;"><span style="display:inline-block;width:5px;height:9px;background:#10b981;border-radius:1px;"></span><span style="display:inline-block;width:5px;height:9px;background:#ef4444;border-radius:1px;"></span></span>'
        cards = [(c_sw, "1分足ローソク", "緑=陽線 / 赤=陰線（ヒゲ先端で反発・失速判定）"), (sw_l("#38bdf8"), "9EMA", "スキャルピングの勢い基準線（割れたら一旦利確）"), (sw_l("#c084fc"), "20EMA", "押し目買い・戻り売りの防波堤ライン"), (sw_l("#fbbf24", "dotted"), "当日VWAP", "機関の平均約定値（上なら買い優勢）"), (tri_sw, "10分先3分岐", "直近1分足ボラから算出した10分後ルート"), (sw_l("#22d3ee"), "下段 出来高&CVD", "陽線/陰線出来高バーと買い売り累積デルタ")]
        if "前日/当日高安（PDH/PDL/HOD/LOD）" in opt_lines:
            cards.append((sw_l("#34d399", "dashed", 1), "PDH/PDL/HOD/LOD", "前日・当日の高値安値（ブレイク基準）"))
    else:
        if exp_active and exp_dir == "UP":
            b_cls, b_txt = "dd-trans-banner exp-up", "🚀 実測(白)が朝想定(紫)を大幅突破 → 急騰ブレイクモード中。紫線は無視し、VWAP(黄点線)や突破ライン付近の押し目追従を優先"
        elif exp_active and exp_dir == "DOWN":
            b_cls, b_txt = "dd-trans-banner exp-down", "🔻 実測(白)が朝想定(紫)を下抜け → 急落ブレイクモード中。紫線は無視し、VWAP(黄点線)での戻り売り・損切り徹底を優先"
        elif traj.get("has_actual"):
            vw_note = ("VWAP(黄点線)上で買い優勢" if curr_px >= cur_vwap_now else "VWAP(黄点線)下で戻り待ち") if (cur_vwap_now and cur_vwap_now > 0) else "VWAP(黄点線)の攻防に注目"
            b_cls, b_txt = "dd-trans-banner", f"📊 実測(白)は朝想定レンジ内で推移中 → 押し目候補 {active_dip_time} 前後の反発と {vw_note}"
        else:
            b_cls, b_txt = "dd-trans-banner", f"🕒 寄り前待機モード → 想定始値 {_fmt_cur(traj['est_open_px'], is_jp)} からの押し目候補 {active_dip_time}・高値想定 {active_peak_time} を事前チェック"

        cards = []
        if traj.get("has_actual"): cards.append((sw_l("#ffffff"), "当日実測", "実際の株価の動き（主役）"))
        if chart_mode in ("🔴 ライブ修正", "⚡ 両方重ね"): cards.append((sw_l("#38bdf8"), "ライブ修正", "今の勢い＋固有波動を反映した最新着地予測"))
        if chart_mode in ("🔒 朝ロック検証", "⚡ 両方重ね"):
            cards.append((sw_l("rgba(148,163,184,0.55)", "dotted"), "朝ロック(無効化)", "想定外ブレイクで参考線へ降格") if exp_active else (sw_l("#c084fc" if chart_mode == "⚡ 両方重ね" else "#38bdf8", "dashed" if chart_mode == "⚡ 両方重ね" else "solid"), "朝ロック", "寄り前固定の当初想定（基準線）"))
        if "場中30分・3分岐点線（スコア比%）" in opt_lines and short_3way.get("active"): cards.append((tri_sw, "短期30分3分岐", "30分後に上/横/下へ進む確率と軌道"))
        if active_lab and "LAB×DD 統合エントリー帯/+1.0R" in opt_lines: cards.append((sw_l("#fde047", "dashed"), "統合Entry/+1.0R", "LABとDDを融合した押し目帯と半分利確ライン"))
        if "VWAP" in opt_lines and traj.get("has_actual"): cards.append((sw_l("#fbbf24", "dotted"), "VWAP", "機関の平均買値（上なら買い優勢）"))
        if "VWAP±σ" in opt_lines and traj.get("has_actual"): cards.append((sw_l("rgba(251,191,36,0.7)", "dashed", 1), "VWAP±1σ/2σ", "買われすぎ・売られすぎの標準偏差帯"))
        if "類似実測波形（Top-1）" in opt_lines and isinstance(traj.get("medoid_analog"), dict) and traj["medoid_analog"].get("data"): cards.append((sw_l("#f59e0b"), "類似実測Top-1", "過去に最も似た日のリアル波形"))
        if "予測レンジ帯（ファン）" in opt_lines: cards.append((sw_b("rgba(56,189,248,0.22)", "rgba(99,102,241,0.48)"), "予測レンジ帯", "値動きが収まりやすい確率ゾーン"))
        if "高ボラ狩り場帯" in opt_lines and traj.get("high_vol_zones"): cards.append((sw_b("rgba(245,158,11,0.16)", "rgba(251,191,36,0.45)"), "高ボラ狩り場帯", "値幅が出やすく仕掛けが入りやすい時間"))
        if "前日/当日高安（PDH/PDL/HOD/LOD）" in opt_lines: cards.append((sw_l("#34d399", "dashed", 1), "PDH/PDL/HOD/LOD", "前日・当日の高値安値（注文集中帯）"))
        if "心理的キリ番節目" in opt_lines: cards.append((sw_l("#fde047", "dotted"), "キリ番節目", "注文が集中しやすいキリの良い価格"))
        if "寄り30分高安（ORB）" in opt_lines and traj.get("orb_high") and traj.get("orb_low"): cards.append((sw_l("#7dd3fc", "dashed", 1), "寄り30分ORB", "寄り30分の高安レンジ（ブレイク基準）"))
        if "大口約定（◆）" in opt_lines and traj.get("vol_spikes"): cards.append(('<span style="display:inline-block;width:14px;text-align:center;color:#10b981;font-size:10px;line-height:1;flex-shrink:0;">◆</span>', "大口約定◆", "通常2.5倍以上の出来高スパイク発生点"))
        if active_lab and "LAB TP/SL" in opt_lines: cards.append((sw_l("#10b981", "dashed"), "LAB TP/SL", "LAB上位足が算出した利確・損切り線"))
        cards.append((sw_l("#22d3ee"), "下段 出来高&CVD", "陽線/陰線出来高と買い売り累積差"))

    pills_html = "".join(f'<span class="dd-leg-pill">{sw}<span>{html.escape(nm)}</span></span>' for sw, nm, _ in cards)
    cards_html = "".join(f'<div class="dd-leg-card"><div class="dd-leg-head">{sw}<span>{html.escape(nm)}</span></div><div class="dd-leg-desc">{html.escape(d)}</div></div>' for sw, nm, d in cards)
    st.markdown(f'<div class="dd-legend-panel"><div class="{b_cls}">{html.escape(b_txt)}</div><div class="dd-chip-ribbon">{pills_html}</div></div>', unsafe_allow_html=True)
    with st.expander("📖 アクティブ凡例の詳細 ＆ 専門指標クイック辞典", expanded=False):
        st.markdown(f'<div class="dd-legend-grid" style="margin-bottom:8px;">{cards_html}</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:11px;line-height:1.65;color:#cbd5e1;">・<b>1分足マイクロ・ズーム：</b> 直近90分の1分足ローソク足＋9EMA/20EMA＋10分先3分岐。スキャルピングの押し目・ブレイク執行に最適です。<br>・<b>下段 出来高＆疑似CVD同期パネル：</b> 上段の価格と完全連動。価格が高値更新しているのに下段のシアン線(CVD)が下がる場合は上ヒゲ売り圧力（天井失速）のサインです。<br>・<b>LAB×DD 統合エントリー帯/+1.0R：</b> LAB上位足のVWAP/OB支持帯とDEEP DIVEの5分足押し目予測を統合した執行ゾーンと、半分利確基準ラインです。<br>・<b>EXPANSION（急騰/急落ブレイク）モード：</b> 実測が朝想定バンドを連続突破・大出来高伴い急変した際に自動発動。古い紫線を無効化し、青線の追従上限とレジサポ転換を解放します。<br>・<b>二壁FPT到達確率：</b> 大引けまでに「損切りライン(SL)へ先に触れずに利確目標(TP)へ到達する」確率モデルに基づく物理確率です。</div>', unsafe_allow_html=True)
# =========================================================================
# 4. マーケット・ニュース・株主・1分足データ取得（TTL分離＆超短期速報）
# =========================================================================
MACRO_TICKERS = {
    "SOX": ("^SOX", "米SOX"), "SP500": ("^GSPC", "S&P500"), "NQ_FUT": ("NQ=F", "NASDAQ先物"),
    "ES_FUT": ("ES=F", "S&P先物"), "NK_FUT": ("NIY=F", "日経先物"), "USDJPY": ("JPY=X", "ドル円"),
    "US10Y": ("^TNX", "米10年債"), "OIL": ("CL=F", "WTI原油"), "VIX": ("^VIX", "VIX"),
}
INTRADAY_RT_MACRO_KEYS = {"NK_FUT", "ES_FUT", "NQ_FUT", "USDJPY"}
TIER1_SOURCES = ["REUTERS", "ロイター", "BLOOMBERG", "ブルームバーグ", "WSJ", "WALL STREET JOURNAL", "FINANCIAL TIMES", "NIKKEI", "日経", "日本経済新聞", "KABUTAN", "株探", "PR TIMES", "CNBC", "SEC", "YAHOO FINANCE"]
TIER2_SOURCES = ["YAHOO", "MINKABU", "みんかぶ", "MARKETWATCH", "BARRON", "FORBES", "東洋経済", "ダイヤモンド", "JIJI", "時事", "共同通信", "GLOBENEWSWIRE", "ACCESSWIRE"]
NOISE_SOURCES = ["まとめ", "ブログ", "2ch", "5ch", "note.com"]
NEG_GUARD_PATTERNS = ["赤字縮小", "赤字脱却", "赤字解消", "下落せず", "懸念後退", "懸念払拭", "リスク軽減", "リスク後退", "不祥事.*他社", "訴訟.*和解", "訴訟.*勝訴"]
GENERIC_CORP_TOKENS = {"THE", "A", "AN", "GLOBAL", "JAPAN", "NIPPON", "INTERNATIONAL", "HOLDINGS", "GROUP", "CORP", "CORPORATION", "INC", "LTD", "CO", "FIRST", "NEW", "AMERICAN"}
CATALYST_POS_JP = ["上方修正", "増配", "自社株買い", "TOB", "業務提携", "資本提携", "ストップ高", "S高", "黒字転換", "最高益", "材料視"]
CATALYST_NEG_JP = ["下方修正", "無配", "増資", "希薄化", "ストップ安", "S安"]
CATALYST_POS_EN = ["GUIDANCE RAISE", "RAISES GUIDANCE", "FDA", "APPROVAL", "BUYBACK", "CONTRACT", "SHORT SQUEEZE", "PRICE TARGET RAISED", "BEAT"]
CATALYST_NEG_EN = ["OFFERING", "DILUTION", "GUIDANCE CUT", "SEC PROBE"]


def _extract_core_corp_token(corp_name: str, short_code: str) -> str:
    for tk in (re.sub(r"[^A-Za-z0-9\-]", "", t) for t in str(corp_name).split()):
        if len(tk) >= 3 and tk.upper() not in GENERIC_CORP_TOKENS:
            return tk
    return short_code


@st.cache_data(ttl=600)
def _load_macro_daily_base() -> dict:
    out = {}
    try:
        raw = yf.download([v[0] for v in MACRO_TICKERS.values()], period="6mo", interval="1d", group_by="ticker", threads=True, progress=False, timeout=8.0)
        for k, (tk, label) in MACRO_TICKERS.items():
            try:
                df_m = raw[tk].dropna(subset=["Close"]) if isinstance(raw.columns, pd.MultiIndex) else raw.dropna(subset=["Close"])
                if len(df_m) >= 2:
                    cl = df_m["Close"].copy()
                    cl.index = pd.to_datetime(cl.index).tz_localize(None).normalize()
                    cl = cl[~cl.index.duplicated(keep="last")]
                    lc, pc = float(cl.iloc[-1]), float(cl.iloc[-2])
                    out[k] = {"label": label, "last": lc, "prev_close": pc, "diff_pct": round((lc - pc) / max(abs(pc), 1e-4) * 100.0, 2), "series": cl, "is_rt": False}
            except Exception:
                pass
    except Exception:
        pass
    return out


@st.cache_data(ttl=20)
def _load_macro_rt_quotes() -> dict:
    rt_map = {}
    try:
        raw_rt = yf.download([MACRO_TICKERS[k][0] for k in INTRADAY_RT_MACRO_KEYS if k in MACRO_TICKERS], period="2d", interval="5m", group_by="ticker", prepost=True, threads=True, progress=False, timeout=5.0)
        for k in INTRADAY_RT_MACRO_KEYS:
            tk = MACRO_TICKERS[k][0]
            try:
                df_rt = raw_rt[tk].dropna(subset=["Close"]) if isinstance(raw_rt.columns, pd.MultiIndex) else raw_rt.dropna(subset=["Close"])
                if not df_rt.empty and float(df_rt["Close"].iloc[-1]) > 0:
                    rt_map[k] = float(df_rt["Close"].iloc[-1])
            except Exception:
                pass
    except Exception:
        pass
    return rt_map


def _load_macro_data() -> dict:
    base, rt_map, out = _load_macro_daily_base(), _load_macro_rt_quotes(), {}
    for k, item in base.items():
        cp = dict(item)
        if k in rt_map and cp.get("prev_close", 0.0) > 0:
            rl, rp = rt_map[k], float(cp["prev_close"])
            cp.update({"last": rl, "diff_pct": round((rl - rp) / max(abs(rp), 1e-4) * 100.0, 2), "is_rt": True})
        out[k] = cp
    return out


@st.cache_data(ttl=20)
def _load_benchmark_5m(is_jp: bool) -> pd.DataFrame:
    for b_tk in (["1306.T", "^N225"] if is_jp else ["QQQ", "SPY"]):
        try:
            df_b = yf.Ticker(b_tk).history(period="1mo", interval="5m", auto_adjust=True)
            if df_b is not None and len(df_b) >= 40:
                return df_b.dropna(subset=["Close"]).copy()
        except Exception:
            continue
    return pd.DataFrame()


@st.cache_data(ttl=3600)
def _fetch_jp_holders(code4: str) -> list:
    holders = []
    try:
        req = urllib.request.Request(f"https://kabutan.jp/stock/holder?code={urllib.parse.quote(code4)}", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=4.0, context=ssl.create_default_context()) as r:
            page = r.read().decode("utf-8", errors="ignore")
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.DOTALL):
            tds = [re.sub(r"<[^>]+>", "", td).strip() for td in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.DOTALL)]
            if len(tds) >= 3:
                mp, ms, nm = re.search(r"([0-9]+\.[0-9]+)", tds[1].replace("%", "")), re.search(r"([0-9,]+)", tds[2]), html.unescape(tds[0]).strip()
                if mp and nm and not any(x in nm for x in ("株主名", "合計", "順位")):
                    pv = float(mp.group(1))
                    if 0.1 <= pv <= 99.0:
                        holders.append({"holder": nm, "pct": pv, "shares": int(ms.group(1).replace(",", "")) * 1000 if ms else 0})
            if len(holders) >= 10:
                break
    except Exception:
        pass
    return holders


@st.cache_data(ttl=1800)
def _load_stock_static(code: str) -> dict:
    tkr = yf.Ticker(code)
    df_1d = tkr.history(period="1y", interval="1d", auto_adjust=True)
    if df_1d is not None and not df_1d.empty:
        df_1d.index = pd.to_datetime(df_1d.index).tz_localize(None).normalize()
        df_1d = df_1d[~df_1d.index.duplicated(keep="last")]
    try:
        info = tkr.info or {}
    except Exception:
        info = {}

    earnings_hist, next_earnings_days = [], None
    try:
        ed = tkr.earnings_dates
        if ed is not None and not ed.empty:
            today_d, future_days = datetime.date.today(), []
            for idx_dt, row in ed.head(12).iterrows():
                dt_obj = idx_dt.date() if hasattr(idx_dt, "date") else None
                if dt_obj and dt_obj >= today_d:
                    future_days.append((dt_obj - today_d).days)
                if (pd.notna(row.get("EPS Estimate")) or pd.notna(row.get("Reported EPS"))) and len(earnings_hist) < 6:
                    earnings_hist.append({
                        "date": idx_dt.strftime("%Y-%m-%d") if hasattr(idx_dt, "strftime") else str(idx_dt)[:10],
                        "est": float(row["EPS Estimate"]) if pd.notna(row.get("EPS Estimate")) else None,
                        "rep": float(row["Reported EPS"]) if pd.notna(row.get("Reported EPS")) else None,
                        "surp": float(row["Surprise(%)"]) if pd.notna(row.get("Surprise(%)")) else None,
                    })
            if future_days:
                next_earnings_days = min(future_days)
    except Exception:
        pass

    inst_holders = []
    try:
        ih = tkr.institutional_holders
        if ih is not None and not ih.empty:
            inst_holders = [{"holder": str(r.get("Holder", "-")), "pct": float(r.get("pctHeld", 0.0)) * 100.0 if pd.notna(r.get("pctHeld")) else 0.0, "shares": int(r.get("Shares", 0)) if pd.notna(r.get("Shares")) else 0} for _, r in ih.head(10).iterrows()]
    except Exception:
        pass
    if not inst_holders and code.endswith(".T"):
        inst_holders = _fetch_jp_holders(code.replace(".T", ""))

    insider_tx = []
    try:
        itx = tkr.insider_transactions
        if itx is not None and not itx.empty:
            for idx_itx, row in itx.head(15).iterrows():
                tx_d = ""
                try:
                    dt_p = pd.to_datetime(row.get("Start Date") or row.get("Date") or row.get("Transaction Date") or idx_itx)
                    if pd.notna(dt_p):
                        tx_d = dt_p.strftime("%Y-%m-%d")
                except Exception:
                    pass
                insider_tx.append({"insider": str(row.get("Insider", "-")), "text": str(row.get("Text", row.get("Transaction", "-"))), "shares": int(row.get("Shares", 0)) if pd.notna(row.get("Shares")) else 0, "date": tx_d})
    except Exception:
        pass
    return {"df_1d": df_1d, "info": info, "earnings_hist": earnings_hist, "next_earnings_days": next_earnings_days, "inst_holders": inst_holders, "insider_tx": insider_tx}


@st.cache_data(ttl=20)
def _load_stock_intraday(code: str) -> pd.DataFrame:
    try:
        df = yf.Ticker(code).history(period="1mo", interval="5m", auto_adjust=True)
        if df is not None and not df.empty:
            return df.dropna(subset=["Close"]).copy()
    except Exception:
        pass
    return pd.DataFrame()


@st.cache_data(ttl=15)
def _load_stock_1m(code: str) -> pd.DataFrame:
    try:
        df = yf.Ticker(code).history(period="2d", interval="1m", auto_adjust=True)
        if df is not None and not df.empty:
            return df.dropna(subset=["Close"]).copy()
    except Exception:
        pass
    return pd.DataFrame()


def _load_stock_core(code: str) -> dict:
    with ThreadPoolExecutor(max_workers=3) as ex:
        f_st, f_5m, f_1m = ex.submit(_load_stock_static, code), ex.submit(_load_stock_intraday, code), ex.submit(_load_stock_1m, code)
        out = dict(f_st.result())
        out["df_5m"], out["df_1m"] = f_5m.result(), f_1m.result()
    return out


def _fetch_rss(url: str, lang_tag: str) -> list:
    out = []
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=3.8) as r:
            for it in ET.fromstring(r.read()).findall("./channel/item")[:14]:
                t, pub_raw = (it.findtext("title") or "").strip(), (it.findtext("pubDate") or "").strip()
                if t:
                    out.append({"title": t, "link": (it.findtext("link") or "").strip(), "source": (it.findtext("source") or "").strip(), "pub": pub_raw[:16], "pub_raw": pub_raw, "lang": lang_tag})
    except Exception:
        pass
    return out


def _fetch_kabutan_news_fast(code4: str) -> list:
    items = []
    try:
        with urllib.request.urlopen(urllib.request.Request(f"https://kabutan.jp/stock/news?code={urllib.parse.quote(code4)}", headers={"User-Agent": "Mozilla/5.0"}), timeout=3.5, context=ssl.create_default_context()) as r:
            page = r.read().decode("utf-8", errors="ignore")
        tz_jst = ZoneInfo("Asia/Tokyo") if ZoneInfo is not None else datetime.timezone(datetime.timedelta(hours=9))
        now_jst = datetime.datetime.now(tz_jst)
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.DOTALL):
            mt, ml = re.search(r"<time[^>]*datetime=[\"']([^\"']+)[\"'][^>]*>([^<]*)</time>", tr), re.search(r"<a[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", tr, re.DOTALL)
            if not ml:
                continue
            href, title_txt = html.unescape(ml.group(1)).strip(), re.sub(r"<[^>]+>", "", html.unescape(ml.group(2))).strip()
            if len(title_txt) < 4:
                continue
            pub_raw, pub_disp = "", ""
            if mt:
                dt_iso, pub_disp = mt.group(1).strip(), mt.group(2).strip() or mt.group(1).strip()[:16]
                try:
                    dp = datetime.datetime.fromisoformat(dt_iso.replace("Z", "+00:00"))
                    pub_raw = email.utils.format_datetime((dp.replace(tzinfo=tz_jst) if dp.tzinfo is None else dp).astimezone(datetime.timezone.utc))
                except Exception:
                    pub_raw = email.utils.format_datetime(now_jst.astimezone(datetime.timezone.utc))
            items.append({"title": title_txt, "link": href if href.startswith("http") else f"https://kabutan.jp{href}", "source": "株探(Kabutan)", "pub": pub_disp or "速報", "pub_raw": pub_raw, "lang": "JP"})
            if len(items) >= 8:
                break
    except Exception:
        pass
    return items


def _fetch_yf_news_fast(code: str) -> list:
    items = []
    try:
        for it in (yf.Ticker(code).news or [])[:10]:
            if not isinstance(it, dict):
                continue
            ct = it.get("content") if isinstance(it.get("content"), dict) else it
            title = str(ct.get("title") or it.get("title") or "").strip()
            if not title:
                continue
            pub_raw, pub_disp = "", ""
            p_iso, ts_u = ct.get("pubDate") or ct.get("displayTime"), it.get("providerPublishTime")
            if p_iso:
                try:
                    dp = datetime.datetime.fromisoformat(str(p_iso).replace("Z", "+00:00"))
                    dp = dp.replace(tzinfo=datetime.timezone.utc) if dp.tzinfo is None else dp
                    pub_raw, pub_disp = email.utils.format_datetime(dp.astimezone(datetime.timezone.utc)), dp.strftime("%m/%d %H:%M")
                except Exception:
                    pass
            elif ts_u:
                try:
                    dp = datetime.datetime.fromtimestamp(float(ts_u), tz=datetime.timezone.utc)
                    pub_raw, pub_disp = email.utils.format_datetime(dp), dp.strftime("%m/%d %H:%M")
                except Exception:
                    pass
            prov = ct.get("provider") if isinstance(ct.get("provider"), dict) else {}
            cu = ct.get("clickThroughUrl") if isinstance(ct.get("clickThroughUrl"), dict) else {}
            ca = ct.get("canonicalUrl") if isinstance(ct.get("canonicalUrl"), dict) else {}
            items.append({"title": title, "link": str(cu.get("url") or ca.get("url") or it.get("link") or "").strip(), "source": str(prov.get("displayName") or it.get("publisher") or "Yahoo Finance").strip(), "pub": pub_disp or "Wire", "pub_raw": pub_raw, "lang": "EN"})
    except Exception:
        pass
    return items


def _calc_rss_time_decay(pub_raw: str, now_utc: datetime.datetime) -> tuple:
    if not pub_raw:
        return 0.0, 999.0
    try:
        dp = email.utils.parsedate_to_datetime(pub_raw)
        if dp is None:
            return 0.0, 999.0
        dp = dp.replace(tzinfo=datetime.timezone.utc) if dp.tzinfo is None else dp.astimezone(datetime.timezone.utc)
        ah = max(0.0, (now_utc - dp).total_seconds() / 3600.0)
        for thr, w, rnd in ((0.25, 3.0, 2), (1.0, 2.0, 2), (3.0, 1.2, 1), (24.0, 0.6, 1), (72.0, 0.2, 1)):
            if ah <= thr:
                return w, round(ah, rnd)
        return 0.0, round(ah, 1)
    except Exception:
        return 0.0, 999.0


def _strip_neg_guards(text: str) -> str:
    for pat in NEG_GUARD_PATTERNS:
        text = re.sub(pat, "", text)
    return text


@st.cache_data(ttl=45)
def _fetch_global_intel(corp_name: str, short_code: str, full_code: str = "") -> dict:
    core_tok = _extract_core_corp_token(corp_name, short_code)
    is_jp_code = full_code.endswith(".T") or bool(re.match(r"^[0-9]{3}[0-9A-Z]$", short_code))
    u_jp = f"https://news.google.com/rss/search?q={urllib.parse.quote(f'{corp_name} OR {short_code} 株価')}&hl=ja&gl=JP&ceid=JP:ja"
    u_en = f"https://news.google.com/rss/search?q={urllib.parse.quote(f'{short_code} OR \"{core_tok}\" stock (Reuters OR Bloomberg OR CNBC OR WSJ)')}&hl=en-US&gl=US&ceid=US:en"
    with ThreadPoolExecutor(max_workers=3) as ex:
        f1, f2 = ex.submit(_fetch_rss, u_jp, "JP"), ex.submit(_fetch_rss, u_en, "EN")
        f3 = ex.submit(_fetch_kabutan_news_fast, short_code) if is_jp_code else ex.submit(_fetch_yf_news_fast, full_code or short_code)
        raw_items = f3.result() + f1.result() + f2.result()

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    pos_w = ["上昇", "急騰", "最高益", "上方修正", "増配", "自社株買い", "好調", "提携", "買い", "黒字", "成長", "SURGE", "BEAT", "UPGRADE", "RECORD", "BUY", "GROWTH", "RALLY"]
    neg_w = ["下落", "急落", "下方修正", "赤字", "減益", "不祥事", "訴訟", "不正", "辞任", "懸念", "売り", "リスク", "DROP", "FALL", "MISS", "DOWNGRADE", "LAWSUIT", "PROBE", "CUT", "SLUMP"]
    filtered, seen_t, catalyst_hits, breaking_list = [], set(), [], []

    for it in raw_items:
        src_up = (it["source"] + " " + it["title"]).upper()
        nk = re.sub(r"\W+", "", it["title"].lower())[:26]
        if any(ns.upper() in src_up for ns in NOISE_SOURCES) or nk in seen_t:
            continue
        seen_t.add(nk)
        decay_w, age_h = _calc_rss_time_decay(it.get("pub_raw", ""), now_utc)
        trust, base_wt = ("S", 2.0) if any(t1 in src_up for t1 in TIER1_SOURCES) else (("A", 1.3) if any(t2 in src_up for t2 in TIER2_SOURCES) else ("B", 0.7))
        cleaned_raw = _strip_neg_guards(it["title"])
        t_up = cleaned_raw.upper()
        p_h, n_h = sum(w in t_up for w in pos_w), sum(w in t_up for w in neg_w)

        cat_dir, cat_kw = None, ""
        for d_tag, kws, tgt in (("POS", CATALYST_POS_JP, cleaned_raw), ("POS", CATALYST_POS_EN, t_up), ("NEG", CATALYST_NEG_JP, cleaned_raw), ("NEG", CATALYST_NEG_EN, t_up)):
            hit = next((kw for kw in kws if kw in tgt), "")
            if hit:
                cat_dir, cat_kw = d_tag, hit
                break

        is_brk = bool(age_h <= 1.0)
        eff_wt = round(base_wt * decay_w * (1.65 if (cat_dir and is_brk) else (1.25 if cat_dir else 1.0)), 3)
        sent = cat_dir or ("POS" if p_h > n_h else ("NEG" if n_h > p_h else "NEU"))
        if cat_dir and is_brk:
            catalyst_hits.append({"dir": cat_dir, "kw": cat_kw, "title": it["title"], "age_min": int(round(age_h * 60))})
        if is_brk and decay_w > 0:
            breaking_list.append({"title": it["title"], "source": it["source"], "sent": sent, "age_min": max(1, int(round(age_h * 60))), "link": it["link"]})
        filtered.append({**it, "trust": trust, "w_trust": eff_wt, "decay_w": decay_w, "age_h": age_h, "is_breaking": is_brk, "catalyst_kw": cat_kw, "sent": sent})

    filtered.sort(key=lambda x: (-x["decay_w"], {"S": 0, "A": 1, "B": 2}[x["trust"]], 0 if x["lang"] == "EN" else 1))
    fresh = [x for x in filtered if x["w_trust"] > 0.0]
    wp, wn, wtot = sum(x["w_trust"] for x in fresh if x["sent"] == "POS"), sum(x["w_trust"] for x in fresh if x["sent"] == "NEG"), max(sum(x["w_trust"] for x in fresh), 1.0)
    has_cat = bool(catalyst_hits)
    shock_sc = round(float(np.clip(((wp - wn) / wtot) * (1.35 if has_cat else 1.0) if fresh else 0.0, -(1.5 if has_cat else 1.0), 1.5 if has_cat else 1.0)), 2)
    cat_alert = {**catalyst_hits[0], "active": True, "boost_drift_pct": 0.85 if catalyst_hits[0]["dir"] == "POS" else -0.85} if has_cat else None
    return {"items": filtered[:12], "all_72h": fresh, "pos_pct": round(wp / wtot * 100) if fresh else 50, "shock_score": shock_sc, "tier1_cnt": sum(x["trust"] == "S" for x in fresh), "fresh_cnt": len(fresh), "catalyst_alert": cat_alert, "breaking_news": breaking_list[0] if breaking_list else None}


@st.cache_data(ttl=180)
def _fetch_gov_and_whales(corp_name: str, short_code: str, is_jp: bool = True) -> tuple:
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    if is_jp:
        u_g = f"https://news.google.com/rss/search?q={urllib.parse.quote(f'{corp_name} (不祥事 OR 不正 OR 訴訟 OR 行政処分 OR 辞任 OR リコール)')}&hl=ja&gl=JP&ceid=JP:ja"
        u_w = f"https://news.google.com/rss/search?q={urllib.parse.quote(f'({corp_name} OR {short_code}) (大量保有 OR 変更報告書 OR 空売り残高 OR 5%ルール OR 買い増し OR 保有割合低下)')}&hl=ja&gl=JP&ceid=JP:ja"
        g_kw, lang, up_chk = ["不祥事", "不正", "訴訟", "行政処分", "辞任", "リコール"], "JP", False
    else:
        ct = _extract_core_corp_token(corp_name, short_code)
        u_g = f"https://news.google.com/rss/search?q={urllib.parse.quote(f'({short_code} OR \"{ct}\") (SEC investigation OR fraud OR lawsuit OR recall OR subpoena OR antitrust)')}&hl=en-US&gl=US&ceid=US:en"
        u_w = f"https://news.google.com/rss/search?q={urllib.parse.quote(f'({short_code} OR \"{ct}\") (13D OR 13G OR insider buying OR insider selling OR Form 4 OR short interest)')}&hl=en-US&gl=US&ceid=US:en"
        g_kw, lang, up_chk = ["SEC", "INVESTIGATION", "FRAUD", "LAWSUIT", "RECALL", "SUBPOENA", "ANTITRUST", "PROBE"], "EN", True
    with ThreadPoolExecutor(max_workers=2) as ex:
        fg, fw = ex.submit(_fetch_rss, u_g, lang), ex.submit(_fetch_rss, u_w, lang)
        gov = [f"{x['title']} ({x['pub']})" for x in fg.result()[:10] if _calc_rss_time_decay(x.get("pub_raw", ""), now_utc)[0] > 0 and any(k in (_strip_neg_guards(x["title"]).upper() if up_chk else _strip_neg_guards(x["title"])) for k in g_kw)][:5]
        wh = [x for x in fw.result()[:8] if _calc_rss_time_decay(x.get("pub_raw", ""), now_utc)[0] > 0][:5]
    return gov, wh


# =========================================================================
# 5. プロ基準価格・MTF同調LED・価格帯ラダー・1分足ズームデータ構築
# =========================================================================
def _compute_round_number_level(curr_px: float, is_jp: bool) -> float:
    try:
        px = float(curr_px)
        if not math.isfinite(px) or px <= 0:
            return 0.0
    except Exception:
        return 0.0
    step = (5000 if px >= 20000 else (1000 if px >= 5000 else (500 if px >= 2000 else 100))) if is_jp else (50 if px >= 400 else (25 if px >= 150 else (10 if px >= 50 else 5)))
    return float(round(px / step) * step)


def _compute_pro_ref_levels(df_1d: pd.DataFrame, df_5m: pd.DataFrame, is_jp: bool, market_today_str: str) -> dict:
    out = {"pdh": None, "pdl": None, "pdc": None, "hod": None, "lod": None}
    if df_1d is not None and not df_1d.empty:
        l1d = df_1d.index[-1].strftime("%Y-%m-%d") if hasattr(df_1d.index[-1], "strftime") else str(df_1d.index[-1])[:10]
        pr = df_1d.iloc[-2] if (l1d == market_today_str and len(df_1d) >= 2) else df_1d.iloc[-1]
        out.update({"pdh": round(float(pr["High"]), 2), "pdl": round(float(pr["Low"]), 2), "pdc": round(float(pr["Close"]), 2)})
    if df_5m is not None and not df_5m.empty:
        tmp = df_5m.copy()
        tmp["_d"] = _convert_5m_index_to_market_tz(tmp, is_jp).strftime("%Y-%m-%d")
        sub = tmp[tmp["_d"] == market_today_str]
        if not sub.empty:
            out.update({"hod": round(float(sub["High"].max()), 2), "lod": round(float(sub["Low"].min()), 2)})
    return out


def _build_1m_zoom_payload(df_1m: pd.DataFrame, is_jp: bool, market_today_str: str, exp_dir: str = "NONE", hvn_wall_px: float = 0.0, ob_sup_px: float = 0.0, vp: dict = None) -> dict:
    if df_1m is None or df_1m.empty or len(df_1m) < 10:
        return {"valid": False}
    try:
        tmp = df_1m.copy()
        idx_dt = _convert_5m_index_to_market_tz(tmp, is_jp)
        tmp["_d"], tmp["_hm"] = idx_dt.strftime("%Y-%m-%d"), idx_dt.strftime("%H:%M")
        target_d = market_today_str if (market_today_str in tmp["_d"].values) else tmp["_d"].iloc[-1]
        sub_day = tmp[tmp["_d"] == target_d].copy()
        if len(sub_day) < 8:
            return {"valid": False}
        ca, oa, ha, la, va = (sub_day[k].values.astype(float) for k in ("Close", "Open", "High", "Low", "Volume"))
        va = np.maximum(va, 0.0)
        n_all = len(ca)
        vwap_all, cvd_all = np.zeros(n_all), np.zeros(n_all)
        cpv, cv, ccvd = 0.0, 0.0, 0.0
        for i in range(n_all):
            cpv += ((ha[i] + la[i] + ca[i]) / 3.0) * va[i]; cv += va[i]
            vwap_all[i] = (cpv / cv) if cv > 0 else ca[i]
            hls = ha[i] - la[i]
            clv = (((ca[i] - la[i]) - (ha[i] - ca[i])) / hls) if hls > 1e-6 else (1.0 if ca[i] >= oa[i] else -1.0)
            ccvd += clv * va[i]; cvd_all[i] = ccvd
        s_cl = pd.Series(ca)
        e9_all, e20_all = s_cl.ewm(span=9, adjust=False).mean().values, s_cl.ewm(span=20, adjust=False).mean().values

        sub_w = sub_day.tail(90); n_w = len(sub_w)
        c_w, o_w, h_w, l_w, v_w, vw_w, cvd_w, e9_w, e20_w = ca[-n_w:], oa[-n_w:], ha[-n_w:], la[-n_w:], va[-n_w:], vwap_all[-n_w:], cvd_all[-n_w:], e9_all[-n_w:], e20_all[-n_w:]
        last_ts = pd.Timestamp(idx_dt[tmp["_d"] == target_d][-1])
        all_times = sub_w["_hm"].tolist() + [(last_ts + datetime.timedelta(minutes=k)).strftime("%H:%M") for k in range(1, 11)]
        n_tot = len(all_times)
        ohlc = [[round(float(o_w[i]), 2), round(float(c_w[i]), 2), round(float(l_w[i]), 2), round(float(h_w[i]), 2)] for i in range(n_w)] + [["-", "-", "-", "-"]] * 10
        vbars = [{"value": round(float(v_w[i]), 1), "itemStyle": {"color": "rgba(16,185,129,.58)" if c_w[i] >= o_w[i] else "rgba(239,68,68,.58)"}} for i in range(n_w)] + [{"value": 0, "itemStyle": {"color": "transparent"}}] * 10

        anchor_px = float(c_w[-1])
        sig_1m = float(np.clip(np.std(np.diff(c_w[-25:]) / np.maximum(c_w[-25:-1], 1e-4)) if len(c_w) >= 5 else 0.001, 0.0005, 0.0065))
        vw_gap = (anchor_px - float(vw_w[-1])) / max(float(vw_w[-1]), 1e-4)
        e_gap = (float(e9_w[-1]) - float(e20_w[-1])) / max(float(e20_w[-1]), 1e-4)
        sc_u = float(np.clip(vw_gap * 110.0 + e_gap * 140.0 + (0.45 if exp_dir == "UP" else 0.0), -0.8, 1.4))
        sc_d = float(np.clip(-vw_gap * 110.0 - e_gap * 140.0 + (0.45 if exp_dir == "DOWN" else 0.0), -0.8, 1.4))
        exps = np.exp(np.array([sc_u, 0.25, sc_d]) - max(sc_u, 0.25, sc_d))
        probs = (exps / np.sum(exps)) * 100.0
        p_up, p_dn = int(np.clip(round(float(probs[0])), 4, 92)), int(np.clip(round(float(probs[2])), 4, 92))
        p_fl = max(2, 100 - p_up - p_dn)

        up_p, fl_p, dn_p = [None] * n_tot, [None] * n_tot, [None] * n_tot
        li = n_w - 1; up_p[li] = fl_p[li] = dn_p[li] = round(anchor_px, 2); vw_l = float(vw_w[-1])
        for k in range(1, 11):
            ss = sig_1m * math.sqrt(k)
            ur, dr = anchor_px * (1.0 + ss * 1.15), anchor_px * (1.0 - ss * 1.15)
            fr = anchor_px + (0.5 * (anchor_px + vw_l) - anchor_px) * (k / 10.0) * 0.45
            if isinstance(vp, dict):
                ur = _apply_hvn_ob_bounce(ur, anchor_px, hvn_wall_px, ob_sup_px, vp, exp_dir=exp_dir)
                dr = _apply_hvn_ob_bounce(dr, anchor_px, hvn_wall_px, ob_sup_px, vp, exp_dir=exp_dir)
            up_p[li + k], fl_p[li + k], dn_p[li + k] = round(float(ur), 2), round(float(fr), 2), round(float(max(dr, anchor_px * 0.5)), 2)

        return {"valid": True, "is_today": bool(target_d == market_today_str), "target_date": target_d, "times": all_times, "ohlc": ohlc, "ema9": [round(float(x), 2) for x in e9_w] + [None] * 10, "ema20": [round(float(x), 2) for x in e20_w] + [None] * 10, "vwap": [round(float(x), 2) for x in vw_w] + [None] * 10, "vol_bars": vbars, "avg_vol_1m": round(float(np.mean(v_w)), 1) if len(v_w) else 0.0, "cvd": [round(float(x), 1) for x in cvd_w] + [None] * 10, "last_ema9": float(e9_w[-1]), "last_ema20": float(e20_w[-1]), "p_up": p_up, "p_flat": p_fl, "p_down": p_dn, "up_path": up_p, "flat_path": fl_p, "down_path": dn_p}
    except Exception:
        return {"valid": False}


def _compute_mtf_alignment(df_1m: pd.DataFrame, df_5m: pd.DataFrame, df_1d: pd.DataFrame, is_jp: bool) -> dict:
    def _ev(s):
        if s is None or len(s) < 12:
            return "NEU", "▶", "#38bdf8"
        e9, e20 = s.ewm(span=9, adjust=False).mean(), s.ewm(span=20, adjust=False).mean()
        cn, e9n, e9p, e20n = float(s.iloc[-1]), float(e9.iloc[-1]), float(e9.iloc[-2]), float(e20.iloc[-1])
        if cn > e9n >= e20n and e9n > e9p: return "BULL", "▲", "#10b981"
        if cn < e9n <= e20n and e9n < e9p: return "BEAR", "▼", "#ef4444"
        return "NEU", "▶", "#38bdf8"

    tfs = [("1m", *_ev(df_1m["Close"].dropna() if (df_1m is not None and not df_1m.empty) else None))]
    if df_5m is not None and not df_5m.empty:
        tmp = df_5m.copy(); tmp.index = _convert_5m_index_to_market_tz(tmp, is_jp); s5 = tmp["Close"].dropna()
        tfs.append(("5m", *_ev(s5)))
        for lbl, freq in (("15m", "15min"), ("60m", "60min")):
            try: tfs.append((lbl, *_ev(s5.resample(freq).last().dropna())))
            except Exception: tfs.append((lbl, "NEU", "▶", "#38bdf8"))
    else:
        tfs.extend([(lbl, "NEU", "▶", "#38bdf8") for lbl in ("5m", "15m", "60m")])
    tfs.append(("1D", *_ev(df_1d["Close"].dropna() if (df_1d is not None and not df_1d.empty) else None)))

    bc, brc = sum(x[1] == "BULL" for x in tfs), sum(x[1] == "BEAR" for x in tfs)
    if bc >= 4: stxt, scol = f"同調 {bc}/5 強気", "#10b981"
    elif brc >= 4: stxt, scol = f"同調 {brc}/5 弱気", "#ef4444"
    elif bc > brc: stxt, scol = f"やや強気 ({bc}/5)", "#6ee7b7"
    elif brc > bc: stxt, scol = f"やや弱気 ({brc}/5)", "#fca5a5"
    else: stxt, scol = "方向拮抗 (中立)", "#94a3b8"
    return {"items": tfs, "bull_cnt": bc, "bear_cnt": brc, "summary": stxt, "color": scol}


def _render_mtf_and_ladder(mtf_res: dict, curr_px: float, is_jp: bool, ref_lv: dict, traj: dict, vp: dict, round_level: float, active_lab):
    leds = "".join(f'<span class="dd-mtf-led" style="border-color:{c};color:{c};background:rgba(15,23,42,.92);">{tf} {ar}</span>' for tf, _, ar, c in mtf_res["items"])
    st.markdown(f'<div class="dd-mtf-bar"><div class="dd-mtf-pills"><span style="font-size:10px;font-weight:800;color:#94a3b8;margin-right:2px;">MTF:</span>{leds}</div><div class="dd-mtf-sum" style="color:{mtf_res["color"]};">{html.escape(mtf_res["summary"])}</div></div>', unsafe_allow_html=True)
    if curr_px <= 0:
        return
    cands = []
    la = traj.get("last_act_idx", -1)
    if traj.get("has_actual") and la >= 0:
        for lbl, key, col in (("当日VWAP", "vwap", "#fbbf24"), ("VWAP+1σ", "vwap_p1", "#f59e0b"), ("VWAP+2σ", "vwap_p2", "#ef4444"), ("VWAP-1σ", "vwap_m1", "#38bdf8"), ("VWAP-2σ", "vwap_m2", "#10b981")):
            if traj[key][la]: cands.append((lbl, float(traj[key][la]), col))
    for lbl, k, col in (("当日高値(HOD)", "hod", "#f43f5e"), ("当日安値(LOD)", "lod", "#10b981"), ("前日高値(PDH)", "pdh", "#fb7185"), ("前日安値(PDL)", "pdl", "#34d399"), ("前日終値(PDC)", "pdc", "#94a3b8")):
        if ref_lv.get(k): cands.append((lbl, float(ref_lv[k]), col))
    for lbl, v, col in (("ORB高値", traj.get("orb_high"), "#7dd3fc"), ("ORB安値", traj.get("orb_low"), "#fda4af"), ("キリ番節目", round_level if round_level > 0 else None, "#fde047"), ("しこり売り壁", vp.get("res_px"), "#c084fc"), ("買い支え帯", vp.get("sup_px"), "#38bdf8")):
        if v: cands.append((lbl, float(v), col))
    f_d = traj.get("factors", {})
    if f_d.get("hvn_wall_px", 0.0) > 0: cands.append(("2Y HVN壁", float(f_d["hvn_wall_px"]), "#d8b4fe"))
    if f_d.get("ob_sup_px", 0.0) > 0: cands.append(("機関OB支持", float(f_d["ob_sup_px"]), "#6ee7b7"))
    if isinstance(active_lab, dict):
        for lbl, ks, col in (("LAB TP目標", ("tp", "raw_tp"), "#10b981"), ("LAB SL撤退", ("sl", "raw_sl"), "#ef4444")):
            v = float(active_lab.get(ks[0], active_lab.get(ks[1], 0.0)) or 0.0)
            if v > 0: cands.append((lbl, v, col))

    res_l, sup_l, seen = [], [], set()
    for lbl, px, col in cands:
        kp = f"{lbl}:{round(px, 2)}"
        if px <= 0 or abs(px - curr_px) / curr_px < 0.0005 or kp in seen:
            continue
        seen.add(kp)
        dp = (px - curr_px) / curr_px * 100.0
        (res_l if dp > 0 else sup_l).append((dp, lbl, px, col))
    res5, sup5 = sorted(res_l, key=lambda x: x[0])[:5][::-1], sorted(sup_l, key=lambda x: abs(x[0]))[:5]
    if res5 or sup5:
        def _lrow(d_pct, lbl, px, col, is_up):
            wb = int(np.clip(abs(d_pct) * 18.0, 8, 100))
            return f'<div class="dd-lad-row"><span style="color:{col};font-weight:700;">{"▲" if is_up else "▼"} {html.escape(lbl)}</span><span style="display:inline-flex;align-items:center;gap:6px;"><span style="color:#f8fafc;font-weight:800;">{_fmt_cur(px, is_jp)}</span><span style="color:{"#fca5a5" if is_up else "#6ee7b7"};min-width:52px;text-align:right;">{d_pct:+.2f}%</span><span class="dd-lad-bar-bg"><span style="display:block;width:{wb}%;height:100%;background:{"#ef4444" if is_up else "#10b981"};"></span></span></span></div>'
        rows = [_lrow(*x, True) for x in res5] + [f'<div class="dd-lad-now"><span>● 現在値（基準）</span><span>{_fmt_cur(curr_px, is_jp)} (0.00%)</span></div>'] + [_lrow(*x, False) for x in sup5]
        with st.expander("🪜 価格帯ラダー：上下の壁・支持帯までの距離", expanded=False):
            st.markdown(f'<div class="dd-ladder-wrap">{"".join(rows)}</div>', unsafe_allow_html=True)


# =========================================================================
# 5B. Phase 3 プロ仕様高度分析エンジン（タブ2・タブ3・タブ4用）
# =========================================================================
def _compute_dow_intraday_heatmap(df_5m: pd.DataFrame, is_jp: bool) -> dict:
    if df_5m is None or df_5m.empty or len(df_5m) < 40:
        return {"valid": False}
    try:
        tmp = df_5m.copy(); idx_dt = _convert_5m_index_to_market_tz(tmp, is_jp)
        tmp.index = idx_dt; tmp["_dow"] = idx_dt.dayofweek; tmp = tmp[tmp["_dow"] < 5].copy()
        if tmp.empty: return {"valid": False}
        tmp["_date"] = tmp.index.strftime("%Y-%m-%d")
        slots = ["09:00", "09:30", "10:00", "10:30", "11:00", "12:30", "13:00", "13:30", "14:00", "14:30", "15:00"] if is_jp else ["09:30", "10:00", "10:30", "11:00", "11:30", "12:00", "12:30", "13:00", "13:30", "14:00", "14:30", "15:00", "15:30"]
        sset, dnames = set(slots), ["月", "火", "水", "木", "金"]
        bkt = {(d, sl): [] for d in range(5) for sl in slots}
        for (_, dv), sd in tmp.groupby(["_date", "_dow"]):
            for ts_b, rb in sd.resample("30min", origin="start_day").agg({"Open": "first", "Close": "last"}).dropna().iterrows():
                hm = ts_b.strftime("%H:%M")
                if hm in sset and float(rb["Open"]) > 0:
                    bkt[(int(dv), hm)].append((float(rb["Close"]) - float(rb["Open"])) / float(rb["Open"]) * 100.0)
        ymap, hm_data, abs_v, best_c, worst_c = {"月": 4, "火": 3, "水": 2, "木": 1, "金": 0}, [], [], None, None
        for di in range(5):
            dn, yp = dnames[di], ymap[dnames[di]]
            for xp, sl in enumerate(slots):
                vs = bkt[(di, sl)]
                if vs:
                    ar, wr, nc = round(float(np.mean(vs)), 3), int(round(float(np.mean([v > 0 for v in vs]) * 100.0))), len(vs)
                    abs_v.append(abs(ar)); hm_data.append([xp, yp, ar, wr, nc])
                    if nc >= 2:
                        if best_c is None or ar > best_c[0]: best_c = (ar, f"{dn}曜 {sl}", wr, nc)
                        if worst_c is None or ar < worst_c[0]: worst_c = (ar, f"{dn}曜 {sl}", wr, nc)
                else:
                    hm_data.append([xp, yp, "-", 50, 0])
        if not abs_v: return {"valid": False}
        return {"valid": True, "x_labels": slots, "y_labels": ["金", "木", "水", "火", "月"], "data": hm_data, "vmax": round(float(np.clip(np.percentile(abs_v, 90), 0.12, 0.80)), 2), "best": best_c, "worst": worst_c}
    except Exception:
        return {"valid": False}


def _compute_rolling_macro_corr(stock_close: pd.Series, macro_item: dict) -> dict:
    if stock_close is None or not isinstance(macro_item, dict) or "series" not in macro_item:
        return {"valid": False}
    try:
        df_j = pd.concat([stock_close.pct_change().dropna().rename("stk"), macro_item["series"].pct_change().dropna().rename("mac")], axis=1).dropna()
        if len(df_j) < 65: return {"valid": False}
        c20, c60 = df_j["stk"].rolling(20).corr(df_j["mac"]), df_j["stk"].rolling(60).corr(df_j["mac"])
        b20 = df_j["stk"].rolling(20).cov(df_j["mac"]) / df_j["mac"].rolling(20).var().replace(0, np.nan)
        sub = pd.DataFrame({"c20": c20, "c60": c60, "b20": b20}).dropna().tail(90)
        if len(sub) < 15: return {"valid": False}
        c20a, c60a, b20a = [round(float(np.clip(x, -1.0, 1.0)), 2) for x in sub["c20"]], [round(float(np.clip(x, -1.0, 1.0)), 2) for x in sub["c60"]], [round(float(np.clip(x, -3.5, 3.5)), 2) for x in sub["b20"]]
        return {"valid": True, "label": macro_item.get("label", "主連動指数"), "dates": [i.strftime("%m/%d") for i in sub.index], "c20": c20a, "c60": c60a, "b20": b20a, "decoupled": bool((c60a[-1] - c20a[-1]) >= 0.25 or (abs(c60a[-1]) - abs(c20a[-1])) >= 0.25), "last_c20": c20a[-1], "last_c60": c60a[-1], "last_b20": b20a[-1]}
    except Exception:
        return {"valid": False}


def _compute_earnings_pead(df_1d: pd.DataFrame, earnings_hist: list) -> dict:
    if df_1d is None or df_1d.empty or not earnings_hist:
        return {"valid": False}
    try:
        d2p = {idx.strftime("%Y-%m-%d"): i for i, idx in enumerate(df_1d.index)}
        ops, cls, rows = df_1d["Open"].values.astype(float), df_1d["Close"].values.astype(float), []
        for e in reversed(earnings_hist):
            eds = str(e.get("date", ""))[:10]
            if eds not in d2p:
                try:
                    nx = (datetime.datetime.strptime(eds, "%Y-%m-%d") + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                    if nx in d2p: eds = nx
                except Exception:
                    pass
            pos = d2p.get(eds, -1)
            if pos < 1 or pos + 5 >= len(cls) or cls[pos - 1] <= 0 or ops[pos] <= 0:
                continue
            rows.append({"date": eds[2:7], "gap": round((ops[pos] - cls[pos - 1]) / cls[pos - 1] * 100.0, 2), "drift5": round((cls[pos + 5] - cls[pos - 1]) / cls[pos - 1] * 100.0, 2)})
        return {"valid": True, "dates": [r["date"] for r in rows], "gaps": [r["gap"] for r in rows], "drifts5": [r["drift5"] for r in rows]} if len(rows) >= 2 else {"valid": False}
    except Exception:
        return {"valid": False}


def _distribute_vp_hist(lows: np.ndarray, highs: np.ndarray, weights: np.ndarray, p_min: float, bins: np.ndarray, n_bins: int) -> np.ndarray:
    hist = np.zeros(n_bins, dtype=float)
    bw = max((bins[-1] - p_min) / n_bins, 1e-6)
    for lo, hi, wv in zip(lows, highs, weights):
        if wv <= 0: continue
        if hi <= lo + 1e-6:
            hist[int(np.clip((lo - p_min) / bw, 0, n_bins - 1))] += wv
        else:
            sp = hi - lo
            for b in range(n_bins):
                ov = min(hi, bins[b + 1]) - max(lo, bins[b])
                if ov > 0: hist[b] += wv * (ov / sp)
    return hist


def _compute_vp(df_1d: pd.DataFrame, curr_px: float, is_jp: bool) -> dict:
    sub = df_1d.tail(250)
    if len(sub) < 20:
        return {"overhead_pct": 0.0, "poc_px": curr_px, "labels": [], "vols": [], "res_px": curr_px, "sup_px": curr_px}
    lo, hi, vo = sub["Low"].values.astype(float), sub["High"].values.astype(float), sub["Volume"].values.astype(float)
    eff = vo * np.power(0.5, np.arange(len(sub) - 1, -1, -1, dtype=float) / 60.0)
    p_min, p_max = float(np.min(lo)), float(np.max(hi))
    if p_max <= p_min: p_max = p_min + 1e-3
    bins = np.linspace(p_min, p_max, 15)
    hist = _distribute_vp_hist(lo, hi, eff, p_min, bins, 14)
    centers = [(bins[i] + bins[i + 1]) * 0.5 for i in range(14)]
    a_idx = [i for i, c in enumerate(centers) if c > curr_px * 1.005]
    b_idx = [i for i, c in enumerate(centers) if c < curr_px * 0.995]
    return {"overhead_pct": round(sum(hist[i] for i in a_idx) / max(float(np.sum(hist)), 1.0) * 100.0, 1), "poc_px": float(centers[int(np.argmax(hist))]), "labels": [_fmt_cur(c, is_jp) for c in centers], "vols": [round(float(v) / 1e6, 2) for v in hist], "res_px": float(centers[max(a_idx, key=lambda i: hist[i])]) if a_idx else curr_px * 1.05, "sup_px": float(centers[max(b_idx, key=lambda i: hist[i])]) if b_idx else curr_px * 0.95}


def _compute_hires_vp_28(df_1d: pd.DataFrame, curr_px: float, is_jp: bool) -> dict:
    if df_1d is None or len(df_1d) < 25:
        return {"valid": False}
    try:
        sub = df_1d.tail(250); n = len(sub)
        lo, hi, vo = sub["Low"].values.astype(float), sub["High"].values.astype(float), sub["Volume"].values.astype(float)
        p_min, p_max = float(np.min(lo)), float(np.max(hi))
        if p_max <= p_min: p_max = p_min + 1e-3
        bins = np.linspace(p_min, p_max, 29)
        ages = np.arange(n - 1, -1, -1, dtype=float)
        h_s = _distribute_vp_hist(lo, hi, np.where(ages < 20, vo, 0.0), p_min, bins, 28)
        h_m = _distribute_vp_hist(lo, hi, np.where(ages >= 20, vo * np.power(0.5, ages / 60.0), 0.0), p_min, bins, 28)
        tot = h_s + h_m; tsum = max(float(np.sum(tot)), 1.0)
        centers = [(bins[i] + bins[i + 1]) * 0.5 for i in range(28)]
        poc_i = int(np.argmax(tot))
        va, acc, lp, hp = {poc_i}, float(tot[poc_i]), poc_i - 1, poc_i + 1
        while acc < tsum * 0.70 and (lp >= 0 or hp < 28):
            vl, vh = float(tot[lp]) if lp >= 0 else -1.0, float(tot[hp]) if hp < 28 else -1.0
            if vh >= vl and hp < 28: va.add(hp); acc += vh; hp += 1
            elif lp >= 0: va.add(lp); acc += vl; lp -= 1
            else: break
        sb, mb = [], []
        for i in range(28):
            cs, cm = ("#f59e0b", "rgba(245,158,11,.45)") if i == poc_i else (("#38bdf8", "rgba(56,189,248,.35)") if i in va else ("#94a3b8", "rgba(100,116,139,.32)"))
            sb.append({"value": round(float(h_s[i]) / 1e6, 2), "itemStyle": {"color": cs}})
            mb.append({"value": round(float(h_m[i]) / 1e6, 2), "itemStyle": {"color": cm}})
        return {"valid": True, "labels": [_fmt_cur(c, is_jp) for c in centers], "short_bars": sb, "mid_bars": mb, "poc_px": float(centers[poc_i]), "vah_px": float(centers[max(va)]), "val_px": float(centers[min(va)]), "curr_bin_idx": int(np.clip((curr_px - p_min) / max((p_max - p_min) / 28.0, 1e-6), 0, 27))}
    except Exception:
        return {"valid": False}


def _compute_bbw_squeeze(df_1d: pd.DataFrame) -> dict:
    if df_1d is None or len(df_1d) < 40:
        return {"valid": False}
    try:
        c = df_1d.tail(145)["Close"]
        ma, sd = c.rolling(20).mean(), c.rolling(20).std()
        up, dn = ma + 2.0 * sd, ma - 2.0 * sd
        vdf = pd.DataFrame({"c": c, "ma": ma, "up": up, "dn": dn, "bbw": ((up - dn) / ma.replace(0, np.nan)) * 100.0}).dropna().tail(120)
        if len(vdf) < 20: return {"valid": False}
        bv = vdf["bbw"].values.astype(float)
        pr = int(round(float(np.mean(bv <= bv[-1]) * 100.0)))
        return {"valid": True, "dates": [i.strftime("%m/%d") for i in vdf.index], "closes": [round(float(x), 2) for x in vdf["c"]], "ma20": [round(float(x), 2) for x in vdf["ma"]], "upper": [round(float(x), 2) for x in vdf["up"]], "lower": [round(float(x), 2) for x in vdf["dn"]], "band_diff": [round(float(u - l), 2) for u, l in zip(vdf["up"], vdf["dn"])], "bbw_pct_series": [int(round(float(np.mean(bv <= v) * 100.0))) for v in bv], "cur_pct": pr, "cur_bbw": round(float(bv[-1]), 1), "is_squeeze": bool(pr <= 20)}
    except Exception:
        return {"valid": False}


def _build_news_72h_timeline(all_72h_items: list) -> dict:
    if not all_72h_items: return {"valid": False}
    counts, scores = [0] * 6, [0.0] * 6
    for it in all_72h_items:
        ah = float(it.get("age_h", 999.0))
        if 0 <= ah <= 72.0:
            bi = int(np.clip(5 - int(ah // 12.0), 0, 5))
            counts[bi] += 1
            scores[bi] += (1.0 if it.get("sent") == "POS" else (-1.0 if it.get("sent") == "NEG" else 0.0)) * float(it.get("w_trust", 1.0))
    return {"valid": True, "labels": ["72-60h前", "60-48h前", "48-36h前", "36-24h前", "24-12h前", "直近12h"], "counts": counts, "scores": [round(x, 2) for x in scores]} if sum(counts) else {"valid": False}


def _extract_ledger_verify_history(ledger: dict, is_jp: bool) -> list:
    if not isinstance(ledger, dict): return []
    recs = []
    for ck, hm in ledger.items():
        if is_jp != ck.endswith(".T") or not isinstance(hm, dict): continue
        for dk, sn in hm.items():
            vs = sn.get("verify_result") if isinstance(sn, dict) else None
            if isinstance(sn, dict) and sn.get("locked_premarket") is True and isinstance(vs, dict) and vs.get("finalized"):
                recs.append({"date": str(dk), "code": ck.replace(".T", ""), "cone": round(float(vs.get("in_cone_pct", 0.0)), 1), "err": round(float(vs.get("err_pct", 0.0)), 2)})
    return sorted(recs, key=lambda x: x["date"])[-15:]


def _detect_whale_anomaly(insider_tx: list, whale_news: list, ref_today_str: str) -> dict:
    bull, bear = [], []
    try: ref_d = datetime.datetime.strptime(ref_today_str, "%Y-%m-%d").date()
    except Exception: ref_d = datetime.date.today()
    for tx in insider_tx:
        tds = str(tx.get("date") or "").strip()
        if not tds: continue
        try:
            age = (ref_d - datetime.datetime.strptime(tds[:10], "%Y-%m-%d").date()).days
            if not (0 <= age <= 30): continue
        except Exception:
            continue
        tu = tx["text"].upper()
        if "PURCHASE" in tu or "BUY" in tu: bull.append(f"役員買付({tds}): {tx['insider']} ({_fmt_sh(tx['shares'])})")
        elif "SALE" in tu or "SELL" in tu: bear.append(f"役員売却({tds}): {tx['insider']} ({_fmt_sh(tx['shares'])})")
    for wn in whale_news:
        t, tu = wn["title"], wn["title"].upper()
        if any(k in t for k in ("新規保有", "買い増し", "保有割合増加", "5%超")) or any(k in tu for k in ("13D", "INSIDER BUY", "STAKE INCREASE", "ACQUIRES STAKE")):
            bull.append(f"大口買付: {t[:34]}")
        elif any(k in t for k in ("保有割合低下", "売却", "空売り残高増加", "売り増し")) or any(k in tu for k in ("INSIDER SELL", "CUTS STAKE", "SHORT INTEREST SURGE")):
            bear.append(f"大口売/空売: {t[:34]}")
    if len(bull) > len(bear): return {"detected": True, "dir": "BULL", "adj_pct": round(min(0.65, 0.25 * (len(bull) - len(bear))), 2), "summary": " / ".join(bull[:2])}
    if len(bear) > len(bull): return {"detected": True, "dir": "BEAR", "adj_pct": round(-min(0.65, 0.25 * (len(bear) - len(bull))), 2), "summary": " / ".join(bear[:2])}
    return {"detected": False, "dir": "NEUTRAL", "adj_pct": 0.0, "summary": "直近30日以内の特異な大口異変なし"}


def _detect_expansion_regime(has_actual: bool, last_act_idx: int, slots: list, actual_arr: list, locked_p85: list, locked_p15: list, is_locked: bool, vwap_arr: list, vwap_p2_arr: list, vwap_m2_arr: list, vwap_p1_arr: list, vwap_m1_arr: list, act_vol_map: dict, act_dir_map: dict, slot_vols: np.ndarray, rvol: float, catalyst_alert: dict = None) -> dict:
    res = {"active": False, "dir": "NONE", "reasons": [], "unconfirmed_catalyst": False, "label": "通常レジーム"}
    if not has_actual or last_act_idx < 1: return res
    rup, rdn, unconf = [], [], False
    if is_locked:
        vp = [(actual_arr[i], locked_p85[i], locked_p15[i]) for i in range(max(0, last_act_idx - 2), last_act_idx + 1) if actual_arr[i] is not None and locked_p85[i] is not None and locked_p15[i] is not None]
        if len(vp) >= 2:
            if all(a > hi for a, hi, _ in vp[-2:]): rup.append("朝ロック上限バンド(85%帯)を2本連続上抜け")
            if all(a < lo for a, _, lo in vp[-2:]): rdn.append("朝ロック下限バンド(15%帯)を2本連続下抜け")
    ca = actual_arr[last_act_idx]
    if rvol is not None and rvol >= 2.2 and ca is not None:
        if vwap_p2_arr[last_act_idx] is not None and ca > vwap_p2_arr[last_act_idx]: rup.append(f"大商いRVOL({rvol:.2f}x)＋VWAP+2σ突破")
        if vwap_m2_arr[last_act_idx] is not None and ca < vwap_m2_arr[last_act_idx]: rdn.append(f"大商いRVOL({rvol:.2f}x)＋VWAP-2σ割れ")
    rec3 = [i for i in range(max(0, last_act_idx - 4), last_act_idx + 1) if actual_arr[i] is not None][-3:]
    if len(rec3) == 3:
        d3 = [act_dir_map.get(slots[i], 0) for i in rec3]
        av3, mv3 = sum(float(act_vol_map.get(slots[i], 0.0)) for i in rec3), sum(float(slot_vols[i]) for i in rec3)
        rv3 = (av3 / mv3) if mv3 > 0 else 0.0
        vw, p1, m1 = vwap_arr[last_act_idx], vwap_p1_arr[last_act_idx], vwap_m1_arr[last_act_idx]
        if rv3 >= 3.0 and vw and p1 and m1 and ca is not None:
            zv = (ca - vw) / max(p1 - vw, 1e-4)
            if all(d > 0 for d in d3) and zv >= 1.5: rup.append(f"直近15分3連続陽線＋出来高{rv3:.1f}倍＋VWAP+{zv:.1f}σ（未確認カタリスト・踏み上げ初動）"); unconf = True
            elif all(d < 0 for d in d3) and zv <= -1.5: rdn.append(f"直近15分3連続陰線＋出来高{rv3:.1f}倍＋VWAP{zv:.1f}σ（未確認悪材料・投げ売り初動）"); unconf = True
    if isinstance(catalyst_alert, dict) and catalyst_alert.get("active"):
        if catalyst_alert.get("dir") == "POS": rup.append(f"速報特大カタリスト検知「{catalyst_alert.get('kw','')}」({catalyst_alert.get('age_min',1)}分前)")
        elif catalyst_alert.get("dir") == "NEG": rdn.append(f"速報悪材料カタリスト検知「{catalyst_alert.get('kw','')}」({catalyst_alert.get('age_min',1)}分前)")
    if rup and len(rup) >= len(rdn): return {"active": True, "dir": "UP", "reasons": rup, "unconfirmed_catalyst": unconf, "label": "急騰ブレイクモード"}
    if rdn: return {"active": True, "dir": "DOWN", "reasons": rdn, "unconfirmed_catalyst": unconf, "label": "急落ブレイクモード"}
    return res


def _detect_cvd_divergence(slots: list, actual_arr: list, cvd_arr: list, act_vol_map: dict) -> dict:
    pts = [(i, slots[i], actual_arr[i], cvd_arr[i], float(act_vol_map.get(slots[i], 0.0))) for i in range(len(slots)) if actual_arr[i] is not None and cvd_arr[i] is not None]
    if len(pts) < 7: return {"state": "WAIT", "label": "計測中", "color": "#94a3b8", "detail": "場中スイングデータ蓄積待ち", "marker": None}
    avg_v = float(np.mean([p[4] for p in pts]))
    sh, sl = [], []
    for idx in range(2, len(pts) - 2):
        pc, vc = pts[idx][2], pts[idx][4]
        if avg_v > 0 and vc < avg_v: continue
        wp = [pts[j][2] for j in range(idx - 2, idx + 3)]
        if pc >= max(wp) and pc > pts[idx - 1][2] and pc >= pts[idx + 1][2]: sh.append(pts[idx])
        if pc <= min(wp) and pc < pts[idx - 1][2] and pc <= pts[idx + 1][2]: sl.append(pts[idx])
    if len(sh) >= 2 and sh[-1][2] > sh[-2][2] * 1.0012 and sh[-1][3] < sh[-2][3]:
        return {"state": "DISTRIBUTION", "label": "上ヒゲ売り圧力", "color": "#ef4444", "detail": f"スイング高値更新（{sh[-2][1]}→{sh[-1][1]}）に対し、OHLCV疑似CVDが切り下げ。高値圏での上ヒゲ売り圧力・失速（弱気ダイバージェンス）の兆候。", "marker": {"time": sh[-1][1], "price": sh[-1][2], "name": "売り圧力", "color": "#ef4444"}}
    if len(sl) >= 2 and sl[-1][2] < sl[-2][2] * 0.9988 and sl[-1][3] > sl[-2][3]:
        return {"state": "ABSORPTION", "label": "下ヒゲ買い支え", "color": "#10b981", "detail": f"スイング安値更新（{sl[-2][1]}→{sl[-1][1]}）に対し、OHLCV疑似CVDが切り上げ。安値圏での下ヒゲ買い支え（強気ダイバージェンス）の兆候。", "marker": {"time": sl[-1][1], "price": sl[-1][2], "name": "買い支え", "color": "#10b981"}}
    lc = pts[-1][3]
    if lc > 0: return {"state": "ALIGNED_BULL", "label": "陽線出来高優位", "color": "#38bdf8", "detail": "OHLCV疑似CVDプラス圏で買い主導の推移。", "marker": None}
    if lc < 0: return {"state": "ALIGNED_BEAR", "label": "陰線出来高優位", "color": "#f59e0b", "detail": "OHLCV疑似CVDマイナス圏で売り主導の推移。", "marker": None}
    return {"state": "NEUTRAL", "label": "均衡", "color": "#94a3b8", "detail": "売り買いのデルタは均衡。", "marker": None}


def _evaluate_gap_open15(has_actual: bool, slots: list, actual_arr: list, vwap_arr: list, act_low_map: dict, act_high_map: dict, act_vol_map: dict, slot_vols: np.ndarray, prev_px: float) -> dict:
    if not has_actual or prev_px <= 0:
        return {"status": "WAIT", "label": "待機中", "color": "#94a3b8", "bias": 0.0, "detail": "", "show_gap_target": False}
    fp = [(i, slots[i], actual_arr[i], vwap_arr[i]) for i in range(len(slots)) if actual_arr[i] is not None][:3]
    if len(fp) < 3:
        return {"status": "WAIT", "label": "待機中", "color": "#94a3b8", "bias": 0.0, "detail": "", "show_gap_target": False}
    gp = (fp[0][2] - prev_px) / max(prev_px, 1e-4) * 100.0
    if abs(gp) < 0.20:
        return {"status": "FLAT", "label": "フラット寄り", "color": "#94a3b8", "bias": 0.0, "detail": f"寄付きギャップ {gp:+.2f}%（通常スタート）", "show_gap_target": False}
    rv15 = (sum(act_vol_map.get(sl, 0.0) for _, sl, _, _ in fp) / sum(float(slot_vols[i]) for i, _, _, _ in fp)) if sum(float(slot_vols[i]) for i, _, _, _ in fp) > 0 else 1.0
    lows3, highs3 = [act_low_map.get(sl, px) for _, sl, px, _ in fp], [act_high_map.get(sl, px) for _, sl, px, _ in fp]
    abv, blw = all(px >= vw for _, _, px, vw in fp if vw is not None), all(px <= vw for _, _, px, vw in fp if vw is not None)
    lp, lvw = fp[-1][2], fp[-1][3] or fp[-1][2]
    if gp >= 0.20:
        if abv and rv15 >= 1.5 and min(lows3[1:]) >= lows3[0] * 0.999:
            return {"status": "GAP_AND_GO_UP", "label": "Gap&Go 上昇確定", "color": "#10b981", "bias": 0.0045, "detail": f"GU({gp:+.2f}%)後15分すべてVWAP上・RVOL {rv15:.2f}x・寄り安値割れなし。窓は埋まらず上昇加速しやすい本物初動。", "show_gap_target": False}
        if rv15 < 1.0 or lp < lvw:
            return {"status": "GAP_AND_FADE_DOWN", "label": "Gap&Fade 窓埋警戒", "color": "#ef4444", "bias": -0.0045, "detail": f"GU({gp:+.2f}%)後に勢い失速（RVOL {rv15:.2f}x / VWAP割れ）。飛びつき買い危険・前日終値までの窓埋め警戒。", "show_gap_target": True}
        return {"status": "GU_HOLD", "label": "GU 様子見", "color": "#38bdf8", "bias": 0.001, "detail": f"GU({gp:+.2f}%)・RVOL {rv15:.2f}x。", "show_gap_target": False}
    if blw and rv15 >= 1.5 and max(highs3[1:]) <= highs3[0] * 1.001:
        return {"status": "GAP_AND_GO_DOWN", "label": "Gap&Go 下落確定", "color": "#ef4444", "bias": -0.0045, "detail": f"GD({gp:+.2f}%)後15分すべてVWAP下・RVOL {rv15:.2f}x。投げ売り継続の本物下落初動。", "show_gap_target": False}
    if rv15 < 1.0 or lp > lvw:
        return {"status": "GAP_AND_FADE_UP", "label": "Gap&Fade 窓埋反発", "color": "#10b981", "bias": 0.0045, "detail": f"GD({gp:+.2f}%)後に売り一巡（RVOL {rv15:.2f}x / VWAP回復）。前日終値に向けた窓埋め反発に優位性。", "show_gap_target": True}
    return {"status": "GD_HOLD", "label": "GD 様子見", "color": "#f59e0b", "bias": -0.001, "detail": f"GD({gp:+.2f}%)・RVOL {rv15:.2f}x。", "show_gap_target": False}


def _compute_macro_sens(stock_close: pd.Series, macro_data: dict) -> list:
    sr, res = stock_close.pct_change().dropna().tail(90), []
    for k, m in macro_data.items():
        if k == "VIX": continue
        j = pd.concat([sr.rename("stk"), m["series"].pct_change().dropna().rename("mac")], axis=1).dropna()
        if len(j) >= 20:
            corr, vm = float(j["stk"].corr(j["mac"])), float(j["mac"].var())
            beta = float(j["stk"].cov(j["mac"]) / vm) if vm > 1e-9 else 0.0
            res.append({"key": k, "label": m["label"], "corr": round(0.0 if np.isnan(corr) else corr, 2), "beta": round(0.0 if np.isnan(beta) else beta, 2), "latest_diff": m["diff_pct"]})
    return sorted(res, key=lambda x: abs(x["corr"]), reverse=True)


def _compute_dow_edge(df_1d: pd.DataFrame, is_jp: bool) -> tuple:
    rets = df_1d["Close"].pct_change().dropna() * 100.0
    stats = [{"dow": d, "label": "月火水木金"[d], "wr": int(round(float((sub > 0).mean() * 100.0), 0)) if len(sub) >= 3 else 50, "avg": round(float(sub.mean()), 2) if len(sub) >= 3 else 0.0} for d in range(5) for sub in (rets[rets.index.dayofweek == d],)]
    try: wd = datetime.datetime.strptime(_get_target_session_date(is_jp), "%Y-%m-%d").weekday()
    except Exception: wd = _get_market_now(is_jp).weekday()
    return stats, min(max(wd, 0), 4)


def _compute_wick_bias(df_1d: pd.DataFrame) -> float:
    sub = df_1d.tail(5)
    if len(sub) < 3: return 0.0
    o, h, l, c = sub["Open"].values, sub["High"].values, sub["Low"].values, sub["Close"].values
    rng = np.maximum(h - l, 1e-4)
    return round(float(np.clip((float(np.mean((np.minimum(o, c) - l) / rng)) - float(np.mean((h - np.maximum(o, c)) / rng))) * 0.8, -0.45, 0.45)), 2)


def _compute_self_calibration(stock_hist: dict, df_1d: pd.DataFrame, market_today_str: str) -> tuple:
    if not stock_hist or df_1d is None or df_1d.empty: return 0.0, 0
    cmap = {idx.strftime("%Y-%m-%d"): float(val) for idx, val in df_1d["Close"].items()}
    diffs = [(cmap[dk] - float(sn["p50"][-1])) / float(sn["p50"][-1]) * 100.0 for dk in sorted(stock_hist.keys()) if dk < market_today_str and stock_hist[dk].get("locked_premarket") is True and dk in cmap and (sn := stock_hist[dk]).get("p50") and float(sn["p50"][-1]) > 0]
    return (round(float(np.clip(np.mean(diffs[-5:]) * 0.40, -0.50, 0.50)), 2), len(diffs[-5:])) if diffs else (0.0, 0)


def _extract_lab_side(active_lab: dict) -> str:
    if not isinstance(active_lab, dict): return "LONG"
    side = active_lab.get("side") or (active_lab.get("strat", {}).get("side") if isinstance(active_lab.get("strat"), dict) else None)
    return str(side or "LONG").upper()


def _parse_float_safe(val, default_val=None):
    if val is None: return default_val
    if isinstance(val, (int, float)): return float(val) if not np.isnan(float(val)) else default_val
    m = re.search(r"[-+]?[0-9]*\.?[0-9]+", str(val).replace(",", ""))
    try: return float(m.group(0)) if m else default_val
    except Exception: return default_val


def _extract_lab_quant_modifiers(active_lab: dict, lab_council: dict) -> dict:
    """LABの22日検証・5名監査官・VPIN・Kyle-λ・30分RSをすべて抽出＆計算係数化"""
    res = {"has_lab": False, "lab_trust_mult": 1.0, "vpin_vboost": 1.0, "kyle_vboost": 1.0, "kyle_warn": False, "vpin_val": None, "kyle_val": None, "rs_30m": None, "council_caution": False, "wf_pf": None, "wf_wr": None}
    if not isinstance(active_lab, dict) or not active_lab:
        return res
    res["has_lab"] = True
    trust = 1.0
    wf22 = next((active_lab[k] for k in ("wf_22d", "walk_forward_22d", "forward_test") if isinstance(active_lab.get(k), dict)), {})
    if wf22:
        pf_v, wr_v = _parse_float_safe(wf22.get("pf", wf22.get("profit_factor"))), _parse_float_safe(wf22.get("win_rate", wf22.get("actual_win_rate")))
        res["wf_pf"], res["wf_wr"] = pf_v, wr_v
        if (pf_v is not None and pf_v < 1.0) or (wr_v is not None and wr_v < 45.0): trust = 0.35
        elif (pf_v is not None and pf_v >= 1.5) and (wr_v is not None and wr_v >= 55.0): trust = 1.15
    if isinstance(lab_council, dict) and lab_council:
        ctxt = str(lab_council.get("verdict") or lab_council.get("conclusion") or lab_council.get("summary") or "").upper()
        if any(kw in ctxt for kw in ("見送り", "回避", "警戒", "様子見", "HOLD", "危険")):
            trust *= 0.45; res["council_caution"] = True
    res["lab_trust_mult"] = round(float(np.clip(trust, 0.10, 1.30)), 3)

    qi = next((active_lab[k] for k in ("quant_metrics", "quants") if isinstance(active_lab.get(k), dict)), {})
    vpin_v = _parse_float_safe(qi.get("vpin", active_lab.get("vpin")))
    kyle_v = _parse_float_safe(qi.get("kyle_lambda", active_lab.get("kyle_lambda")))
    rs30_v = _parse_float_safe(qi.get("rs_30m", active_lab.get("intraday_rs_30m")))
    res.update({"vpin_val": vpin_v, "kyle_val": kyle_v, "rs_30m": rs30_v})
    if vpin_v is not None and vpin_v > 0.55:
        res["vpin_vboost"] = round(float(1.0 + min((vpin_v - 0.55) * 0.65, 0.25)), 3)
    # Kyle-λ（価格インパクト係数）が高い銘柄は板薄ボラ拡張＋スリッページ警戒へ自動連動
    if kyle_v is not None and abs(kyle_v) > 0.05:
        res["kyle_vboost"] = round(float(1.0 + min((abs(kyle_v) - 0.05) * 0.80, 0.18)), 3)
        if abs(kyle_v) >= 0.12:
            res["kyle_warn"] = True
    return res


def _fit_short_3way_logreg(df_5m: pd.DataFrame, is_jp: bool, slots: list, slot_vols: np.ndarray, atr_pct: float, horizon_slots: int = 6) -> dict:
    empty = {"fitted": False, "n_samples": 0, "W": None, "b": None, "mu": None, "sd": None}
    if df_5m is None or df_5m.empty or len(df_5m) < 80: return empty
    try:
        mt_str = _get_market_now(is_jp).strftime("%Y-%m-%d")
        tmp = df_5m.copy(); idx_dt = _convert_5m_index_to_market_tz(tmp, is_jp)
        tmp["_d"], tmp["_hm"] = idx_dt.strftime("%Y-%m-%d"), idx_dt.strftime("%H:%M")
        smap = {sl: i for i, sl in enumerate(slots)}
        cum_avg_v = np.cumsum(slot_vols) if len(slot_vols) == len(slots) else np.zeros(len(slots))
        th = float(np.clip((atr_pct / 100.0) * 0.14, 0.0018, 0.0045))
        Xr, yr = [], []
        for ds, sub in tmp.groupby("_d"):
            if ds == mt_str or len(sub) < horizon_slots + 8: continue
            sv = sub[sub["_hm"].isin(smap)]
            if len(sv) < horizon_slots + 8: continue
            cl = sv["Close"].values.astype(float)
            op = sv["Open"].values.astype(float) if "Open" in sv.columns else cl
            hi = sv["High"].values.astype(float) if "High" in sv.columns else cl
            lo = sv["Low"].values.astype(float) if "Low" in sv.columns else cl
            vo = np.maximum(sv["Volume"].values.astype(float), 0.0) if "Volume" in sv.columns else np.zeros(len(cl))
            hms, nd = sv["_hm"].values, len(cl)
            vw_d, cvd_d, cv_d = np.zeros(nd), np.zeros(nd), np.zeros(nd)
            cpv, cv, ccvd = 0.0, 0.0, 0.0
            for k in range(nd):
                cpv += ((hi[k] + lo[k] + cl[k]) / 3.0) * vo[k]; cv += vo[k]
                vw_d[k] = (cpv / cv) if cv > 0 else cl[k]
                hls = hi[k] - lo[k]
                clv = (((cl[k] - lo[k]) - (hi[k] - cl[k])) / hls) if hls > 1e-6 else (1.0 if cl[k] >= op[k] else -1.0)
                ccvd += clv * vo[k]; cvd_d[k], cv_d[k] = ccvd, cv
            for k in range(3, nd - horizon_slots):
                cn, cf = cl[k], cl[k + horizon_slots]
                if cn <= 0 or cf <= 0: continue
                vwn, cb = vw_d[k] or cn, cl[max(0, k - 6)] or cn
                si = smap.get(hms[k], -1)
                acv = float(cum_avg_v[si]) if 0 <= si < len(cum_avg_v) else 0.0
                lrvol = math.log(max(cv_d[k] / acv, 0.1)) if (acv > 0 and cv_d[k] > 0) else 0.0
                fr = (cf - cn) / cn
                Xr.append([(cn - vwn) / vwn, (cn - cb) / cb, lrvol, math.tanh(cvd_d[k] / max(cv_d[k] * 0.25, 1.0))])
                yr.append(0 if fr > th else (2 if fr < -th else 1))
        ns = len(Xr)
        if ns < 60: return {**empty, "n_samples": ns}
        X, y = np.array(Xr, dtype=float), np.array(yr, dtype=int)
        mu, sd = np.mean(X, axis=0), np.where(np.std(X, axis=0) < 1e-6, 1.0, np.std(X, axis=0))
        Xs = (X - mu) / sd
        Yoh = np.zeros((ns, 3)); Yoh[np.arange(ns), y] = 1.0
        W, b = np.zeros((4, 3)), np.zeros(3)
        for _ in range(120):
            lg = Xs @ W + b; lg -= np.max(lg, axis=1, keepdims=True)
            ex = np.exp(lg); pr = ex / np.sum(ex, axis=1, keepdims=True)
            df = (pr - Yoh) / ns
            W -= 0.15 * ((Xs.T @ df) + 0.05 * W); b -= 0.15 * np.sum(df, axis=0)
        return {"fitted": True, "n_samples": ns, "W": W, "b": b, "mu": mu, "sd": sd}
    except Exception:
        return empty


def _apply_hvn_ob_bounce(mid: float, ref_px: float, hvn_wall_px: float, ob_sup_px: float, vp: dict, exp_dir: str = "NONE") -> float:
    if ref_px <= 0: return mid
    is_hvn = hvn_wall_px > ref_px * 1.002
    res_w = hvn_wall_px if is_hvn else (float(vp.get("res_px", 0.0)) if float(vp.get("res_px", 0.0)) > ref_px * 1.002 else 0.0)
    is_ob = 0 < ob_sup_px < ref_px * 0.998
    sup_f = ob_sup_px if is_ob else (float(vp.get("sup_px", 0.0)) if 0 < float(vp.get("sup_px", 0.0)) < ref_px * 0.998 else 0.0)
    if exp_dir == "UP":
        fls = [p for p in (hvn_wall_px, float(vp.get("res_px", 0.0)), sup_f) if 0 < p < ref_px * 0.999]
        if fls and mid < max(fls) * 1.003:
            bf = max(fls) * 1.003; return bf - (bf - mid) * 0.30
        return mid
    if exp_dir == "DOWN":
        cls = [p for p in (ob_sup_px, float(vp.get("sup_px", 0.0)), res_w) if p > ref_px * 1.001]
        if cls and mid > min(cls) * 0.997:
            bc = min(cls) * 0.997; return bc + (mid - bc) * 0.30
        return mid
    if res_w > 0 and mid > res_w * 0.995:
        damp = 0.35 if is_hvn else (0.45 if vp.get("overhead_pct", 0.0) >= 35.0 else 1.0)
        if damp < 1.0: mid = res_w * 0.995 + (mid - res_w * 0.995) * damp
    if sup_f > 0 and mid < sup_f * 1.005:
        mid = sup_f * 1.005 - (sup_f * 1.005 - mid) * (0.38 if is_ob else 0.65)
    return mid


def _compute_short_horizon_3way(has_actual: bool, last_act_idx: int, n_slots: int, anchor_px: float, cur_vwap: float, mom_30m: float, rvol: float, cvd_div: dict, gap_open15: dict, bench_live_alpha_adj: float, knn_moves: dict, slot_means: np.ndarray, slot_inc_stds: np.ndarray, vboost: float, hvn_wall_px: float, ob_sup_px: float, vp: dict, shock_ext_pct: float = 0.0, horizon_slots: int = 6, ml_model: dict = None, cum_cvd_now: float = 0.0, cum_vol_now: float = 0.0, lab_dir_score: float = 0.0, lab_rs30: float = None, exp_dir: str = "NONE") -> dict:
    empty = {"active": False, "horizon": 0, "end_idx": -1, "p_up": 33, "p_flat": 34, "p_down": 33, "ml_used": False, "ml_samples": 0, "up_path": [None] * n_slots, "flat_path": [None] * n_slots, "down_path": [None] * n_slots}
    if not has_actual or last_act_idx < 0 or anchor_px <= 0: return empty
    horizon = min(int(horizon_slots), n_slots - 1 - last_act_idx)
    if horizon < 1: return empty
    end_idx = last_act_idx + horizon
    vw_ref = cur_vwap if (cur_vwap is not None and cur_vwap > 0) else anchor_px
    vw_gap = (anchor_px - vw_ref) / max(vw_ref, 1e-4)
    lu, lf, ld = 0.0, 0.18, 0.0

    if abs(vw_gap) <= 0.0015: lf += 0.42
    elif vw_gap > 0: lu += float(np.clip(vw_gap * 85.0, 0.15, 1.05)); ld -= float(np.clip(vw_gap * 45.0, 0.05, 0.55))
    else: ld += float(np.clip(-vw_gap * 85.0, 0.15, 1.05)); lu -= float(np.clip(-vw_gap * 45.0, 0.05, 0.55))

    if abs(mom_30m) <= 0.0012: lf += 0.30
    elif mom_30m > 0: lu += float(np.clip(mom_30m * 95.0, 0.10, 1.15))
    else: ld += float(np.clip(-mom_30m * 95.0, 0.10, 1.15))

    if rvol is not None:
        if rvol >= 1.4:
            rb = float(np.clip((rvol - 1.0) * 0.42, 0.15, 0.85))
            if mom_30m >= 0 and vw_gap >= -0.001: lu += rb
            elif mom_30m < 0 and vw_gap <= 0.001: ld += rb
            lf -= rb * 0.65
        elif rvol < 0.85:
            lf += 0.68; lu -= 0.25; ld -= 0.25

    cst = cvd_div.get("state", "NEUTRAL")
    if cst == "ABSORPTION": lu += 0.62; ld -= 0.45
    elif cst == "ALIGNED_BULL": lu += 0.34
    elif cst == "DISTRIBUTION": ld += 0.62; lu -= 0.45
    elif cst == "ALIGNED_BEAR": ld += 0.34

    for val, mul, lo_c, hi_c in ((float(gap_open15.get("bias", 0.0)), 90.0, 0.10, 0.50), (bench_live_alpha_adj, 55.0, 0.05, 0.55)):
        if val > 0: lu += float(np.clip(val * mul, lo_c, hi_c))
        elif val < 0: ld += float(np.clip(-val * mul, lo_c, hi_c))

    kr = float(knn_moves.get(end_idx, 0.0)) if isinstance(knn_moves, dict) else 0.0
    if abs(kr) <= 0.0015: lf += 0.25
    elif kr > 0: lu += float(np.clip(kr * 75.0, 0.08, 0.65))
    else: ld += float(np.clip(-kr * 75.0, 0.08, 0.65))

    if lab_dir_score > 0.01: lu += float(np.clip(lab_dir_score * 0.48, 0.0, 0.55))
    elif lab_dir_score < -0.01: ld += float(np.clip(-lab_dir_score * 0.48, 0.0, 0.55))
    if lab_rs30 is not None:
        if lab_rs30 > 0.15: lu += float(np.clip(lab_rs30 * 0.22, 0.05, 0.40))
        elif lab_rs30 < -0.15: ld += float(np.clip(-lab_rs30 * 0.22, 0.05, 0.40))
    if exp_dir == "UP": lu += 0.55; ld -= 0.35
    elif exp_dir == "DOWN": ld += 0.55; lu -= 0.35
    if shock_ext_pct > 0.01: lu += float(np.clip(shock_ext_pct * 0.70, 0.0, 1.40)); ld -= float(np.clip(shock_ext_pct * 0.35, 0.0, 0.70))
    elif shock_ext_pct < -0.01: ld += float(np.clip(-shock_ext_pct * 0.70, 0.0, 1.40)); lu -= float(np.clip(-shock_ext_pct * 0.35, 0.0, 0.70))

    lg_r = np.array([lu, lf, ld]); lg_r -= np.max(lg_r); pr_f = np.exp(lg_r) / np.sum(np.exp(lg_r))
    ml_used, ml_n = False, int(ml_model.get("n_samples", 0)) if isinstance(ml_model, dict) else 0
    if isinstance(ml_model, dict) and ml_model.get("fitted") and ml_n >= 60:
        try:
            xn = np.array([vw_gap, mom_30m, math.log(max(float(rvol), 0.1)) if (rvol and rvol > 0) else 0.0, math.tanh(float(cum_cvd_now) / max(float(cum_vol_now) * 0.25, 1.0))])
            lm = ((xn - ml_model["mu"]) / ml_model["sd"]) @ ml_model["W"] + ml_model["b"]; lm -= np.max(lm)
            pm = np.exp(lm) / np.sum(np.exp(lm))
            wm = float(np.clip(ml_n / (ml_n + 120.0), 0.25, 0.70)) * (0.65 if exp_dir in ("UP", "DOWN") else 1.0)
            pr_f = wm * pm + (1.0 - wm) * pr_f; pr_f /= np.sum(pr_f); ml_used = True
        except Exception:
            pass

    pp = pr_f * 100.0
    p_up, p_dn = int(np.clip(round(float(pp[0])), 2, 96)), int(np.clip(round(float(pp[2])), 2, 96))
    p_fl = 100 - p_up - p_dn
    if p_fl < 2:
        p_fl = 2
        if p_up >= p_dn: p_up = 98 - p_dn
        else: p_dn = 98 - p_up

    up_p, fl_p, dn_p = [None] * n_slots, [None] * n_slots, [None] * n_slots
    up_p[last_act_idx] = fl_p[last_act_idx] = dn_p[last_act_idx] = round(float(anchor_px), 2)
    am, vmid, sr = float(slot_means[last_act_idx]), 0.5 * (anchor_px + vw_ref), shock_ext_pct / 100.0
    for k in range(1, horizon + 1):
        idx, sf = last_act_idx + k, k / max(horizon, 1)
        cs = max(float(np.sqrt(np.sum(slot_inc_stds[last_act_idx + 1:idx + 1] ** 2))) * vboost, 0.0014 * math.sqrt(k))
        md = float(slot_means[idx]) - am
        ls = 0.45 * md + 0.55 * (float(knn_moves[idx]) if (isinstance(knn_moves, dict) and idx in knn_moves) else md)
        ur = max(_apply_hvn_ob_bounce(anchor_px * (1.0 + ls * 0.72 + cs * 1.05 + max(0.0, sr) * 0.45 * sf), anchor_px, hvn_wall_px, ob_sup_px, vp, exp_dir), anchor_px * (1.0 + 0.0005 * k))
        fr = _apply_hvn_ob_bounce(anchor_px + (vmid - anchor_px) * (0.45 * sf) + anchor_px * (ls * 0.40 + sr * 0.15 * sf), anchor_px, hvn_wall_px, ob_sup_px, vp, exp_dir)
        dr = max(min(_apply_hvn_ob_bounce(anchor_px * (1.0 + ls * 0.72 - cs * 1.05 - max(0.0, -sr) * 0.45 * sf), anchor_px, hvn_wall_px, ob_sup_px, vp, exp_dir), anchor_px * (1.0 - 0.0005 * k)), anchor_px * 0.5)
        up_p[idx], fl_p[idx], dn_p[idx] = round(float(ur), 2), round(float(fr), 2), round(float(dr), 2)
    return {"active": True, "horizon": horizon, "end_idx": end_idx, "p_up": p_up, "p_flat": p_fl, "p_down": p_dn, "ml_used": ml_used, "ml_samples": ml_n, "up_path": up_p, "flat_path": fl_p, "down_path": dn_p}


def _compute_bayesian_scenario_probs(has_actual: bool, curr_px: float, anchor_base_close: float, est_open_gap_pct: float, est_close_chg: float, bull_trig: float, bull_target: float, bear_trig: float, bear_target: float, rem_sigma_pct: float, rem_drift_pct: float, rvol: float, cvd_div: dict, gap_open15: dict, cur_vwap: float, shock_ext_pct: float = 0.0, exp_dir: str = "NONE") -> dict:
    fb, fbr = _calc_first_passage_prob(curr_px, bull_trig, rem_sigma_pct, rem_drift_pct) / 100.0, _calc_first_passage_prob(curr_px, bear_trig, rem_sigma_pct, rem_drift_pct) / 100.0
    lb = math.log(max(fb, 0.05)) + est_close_chg * 0.35 + shock_ext_pct * 0.60
    lbr = math.log(max(fbr, 0.05)) - est_close_chg * 0.35 - shock_ext_pct * 0.60
    lr = math.log(max(1.0 - max(fb, fbr), 0.15)) + 0.55 - abs(est_close_chg) * 0.20
    lf = math.log(max(min(abs(est_open_gap_pct) / 2.5, 0.75), 0.08)) + 0.35
    if exp_dir == "UP": lb += 0.90; lr -= 0.35; lf -= 0.45
    elif exp_dir == "DOWN": lbr += 0.90; lr -= 0.35; lf -= 0.45
    if rvol is not None:
        if rvol >= 1.5:
            bs = min((rvol - 1.0) * 0.45, 0.90)
            if est_close_chg >= 0: lb += bs
            else: lbr += bs
            lr -= bs * 0.5
        elif rvol < 0.85: lr += 0.45; lf += 0.35; lb -= 0.30; lbr -= 0.30
    if has_actual and cur_vwap and cur_vwap > 0:
        vd = (curr_px - cur_vwap) / cur_vwap * 100.0
        lb += float(np.clip(vd * 0.55, -0.8, 0.8)); lbr -= float(np.clip(vd * 0.55, -0.8, 0.8))
        if (est_open_gap_pct > 0.25 and vd < -0.15) or (est_open_gap_pct < -0.25 and vd > 0.15): lf += 0.65
    gs = gap_open15.get("status", "WAIT")
    if gs == "GAP_AND_GO_UP": lb += 0.75; lf -= 0.60
    elif gs == "GAP_AND_GO_DOWN": lbr += 0.75; lf -= 0.60
    elif gs in ("GAP_AND_FADE_DOWN", "GAP_AND_FADE_UP"): lf += 0.85; lr += 0.20
    cs = cvd_div.get("state", "NEUTRAL")
    if cs == "DISTRIBUTION": lbr += 0.45; lf += 0.40; lb -= 0.45
    elif cs == "ABSORPTION": lb += 0.45; lf += 0.40; lbr -= 0.45
    lg = np.array([lb, lr, lf, lbr]); lg -= np.max(lg); ps = (np.exp(lg) / np.sum(np.exp(lg))) * 100.0
    pb, pr, pf = round(float(ps[0]), 1), round(float(ps[1]), 1), round(float(ps[2]), 1)
    return {"bull": pb, "range": pr, "fade": pf, "bear": round(max(0.5, 100.0 - pb - pr - pf), 1), "fpt_bull_pct": round(fb * 100.0, 1), "fpt_bear_pct": round(fbr * 100.0, 1)}


def _audit_meta_labeling_accuracy(ledger: dict, fc_code: str, is_jp: bool, cur_regime: str, cur_rvol: float, cur_gap_pct: float) -> dict:
    if not isinstance(ledger, dict) or not ledger:
        return {"rank": "計測中", "color": "#94a3b8", "n": 0, "hit_rate": 0.0, "mean_err": 0.0, "detail": "事前ロック検証データ蓄積中"}
    c_gb = abs(cur_gap_pct) >= 0.8
    matched, all_m = [], []
    for ck, hm in ledger.items():
        if is_jp != ck.endswith(".T") or not isinstance(hm, dict): continue
        for sn in hm.values():
            vs = sn.get("verify_result") if isinstance(sn, dict) else None
            if not (isinstance(sn, dict) and sn.get("locked_premarket") is True and isinstance(vs, dict) and vs.get("finalized")): continue
            ic, ep = float(vs.get("in_cone_pct", -1.0)), float(vs.get("err_pct", -1.0))
            if ic < 0 or ep < 0: continue
            rec = {"regime": str(sn.get("regime_code") or "NEUTRAL"), "gap_big": abs(float(sn.get("pred_open_gap_pct") or 0.0)) >= 0.8, "in_cone": ic, "err_pct": ep}
            all_m.append(rec)
            if rec["regime"] == cur_regime and rec["gap_big"] == c_gb: matched.append(rec)
    tgt = matched if len(matched) >= 3 else all_m
    if len(tgt) < 3:
        return {"rank": "計測中", "color": "#94a3b8", "n": len(tgt), "hit_rate": 0.0, "mean_err": 0.0, "detail": f"大引け確定済みの事前ロック検証が {len(tgt)}件（3件以上でランク判定）"}
    ac, ae = float(np.mean([r["in_cone"] for r in tgt])), float(np.mean([r["err_pct"] for r in tgt]))
    scope = f"{cur_regime}・{'大Gap' if c_gb else '通常Gap'}" if len(matched) >= 3 else ("日本株全体" if is_jp else "米国株全体")
    rank, col = ("A", "#10b981") if (ac >= 72.0 and ae <= 0.85) else (("B", "#38bdf8") if (ac >= 58.0 and ae <= 1.35) else (("C", "#f59e0b") if ac >= 45.0 else ("D", "#ef4444")))
    return {"rank": rank, "color": col, "n": len(tgt), "hit_rate": round(ac, 1), "mean_err": round(ae, 2), "detail": f"{scope} (大引け確定 N={len(tgt)}): 予測帯収束率 {ac:.1f}% / 平均誤差 {ae:.2f}%"}


def _compute_lab_dd_fusion(active_lab: dict, traj: dict, short_3way: dict, scen_probs: dict, curr_px: float, is_jp: bool, active_dip_px: float, active_dip_time: str, active_peak_px: float, active_peak_time: str, active_bull_tgt: float, active_bear_tgt: float, active_bull_trig: float, active_bear_trig: float, active_close_chg: float, exp_reg: dict, cvd_div: dict) -> dict:
    if not isinstance(active_lab, dict) or not active_lab or curr_px <= 0:
        return {"has_lab": False}
    l_side = _extract_lab_side(active_lab)
    is_long = (l_side != "SHORT")
    sgn = 1.0 if is_long else -1.0
    l_exp = float(active_lab.get("expect_pct", 55.0) or 55.0)
    l_tp, l_sl = float(active_lab.get("tp", active_lab.get("raw_tp", 0.0)) or 0.0), float(active_lab.get("sl", active_lab.get("raw_sl", 0.0)) or 0.0)
    l_vwap, l_ob = float(active_lab.get("vwap", active_lab.get("raw_vwap", 0.0)) or 0.0), float(active_lab.get("ob_support_px", 0.0) or 0.0)
    l_grade = str(active_lab.get("exec_grade", "🔵 Grade-B")).split("（")[0]
    l_shares = int((active_lab.get("lot_info") or {}).get("shares", 100) if isinstance(active_lab.get("lot_info"), dict) else 100)
    l_emode = str((active_lab.get("strat") or {}).get("entry_mode", "押し目・ブレイク確認") if isinstance(active_lab.get("strat"), dict) else "押し目・ブレイク確認")

    ds = 50.0 + float(np.clip(sgn * active_close_chg * 6.5, -18.0, 18.0)) + sgn * (float(scen_probs["bull"]) - float(scen_probs["bear"])) * 0.20
    if short_3way.get("active"): ds += sgn * (float(short_3way["p_up"]) - float(short_3way["p_down"])) * 0.25
    if exp_reg.get("active"): ds += 10.0 if ((is_long and exp_reg.get("dir") == "UP") or (not is_long and exp_reg.get("dir") == "DOWN")) else -14.0
    cst = cvd_div.get("state")
    if cst == ("ABSORPTION" if is_long else "DISTRIBUTION"): ds += 6.0
    elif cst == ("DISTRIBUTION" if is_long else "ABSORPTION"): ds -= 8.0
    ds = float(np.clip(ds, 10.0, 98.0))
    f_sc = round(l_exp * 0.50 + ds * 0.50, 1)
    supp = (active_close_chg >= -0.15) if is_long else (active_close_chg <= 0.15)
    s_st, s_col = ("🟢 完全同期（高確度執行）", "#10b981") if (supp and f_sc >= 68.0) else (("🔵 概ね一致（押し目引きつけ）", "#38bdf8") if (supp or f_sc >= 55.0) else ("🟡 乖離警戒（時間・反転待ち）", "#f59e0b"))

    if is_long:
        ec = [p for p in (l_vwap, l_ob, active_dip_px) if 0 < p <= curr_px * 1.005]
        fe = round(float(np.mean(ec)), 2) if ec else round(min(curr_px, active_dip_px), 2)
        sc = [p for p in (l_sl, active_bear_trig) if 0 < p < fe * 0.998]
        fsl = round(max(sc), 2) if sc else round(fe * 0.985, 2)
        ru = max(fe - fsl, curr_px * 0.004); fhr = round(fe + ru, 2)
        tc = [p for p in (l_tp, active_bull_tgt) if p > fhr]
        ftp, thint = (round(min(tc), 2) if tc else round(fe + ru * 2.0, 2)), f"{active_dip_time}前後 押目"
    else:
        ec = [p for p in (l_vwap, active_peak_px) if p >= curr_px * 0.995]
        fe = round(float(np.mean(ec)), 2) if ec else round(max(curr_px, active_peak_px), 2)
        sc = [p for p in (l_sl, active_bull_trig) if p > fe * 1.002]
        fsl = round(min(sc), 2) if sc else round(fe * 1.015, 2)
        ru = max(fsl - fe, curr_px * 0.004); fhr = round(max(fe - ru, curr_px * 0.5), 2)
        tc = [p for p in (l_tp, active_bear_tgt) if 0 < p < fhr]
        ftp, thint = (round(max(tc), 2) if tc else round(max(fe - ru * 2.0, curr_px * 0.5), 2)), f"{active_peak_time}前後 戻り"
    bh = max(curr_px * 0.0022, ru * 0.28)
    return {"has_lab": True, "side": l_side, "is_long": is_long, "lab_expect": l_exp, "dd_dir_score": round(ds, 1), "fusion_score": f_sc, "sync_state": s_st, "sync_col": s_col, "exec_grade": l_grade, "entry_mode": l_emode, "shares": l_shares, "fusion_entry_px": fe, "entry_zone_lo": round(max(fe - bh, curr_px * 0.5), 2), "entry_zone_hi": round(fe + bh, 2), "fusion_half_r_px": fhr, "fusion_tp_px": ftp, "fusion_sl_px": fsl, "target_time_hint": thint}
# =========================================================================
# 6. デュアル5分足軌道エンジン（振幅保存型・固有波形合成エンジン搭載）
# =========================================================================
def _build_dual_5m_trajectory(fc_code: str, curr_px: float, prev_px: float, df_1d: pd.DataFrame, df_5m: pd.DataFrame, macro_sens: list, macro_data: dict, news_res: dict, whale_anom: dict, dow_next_avg: float, vp: dict, is_jp: bool, mkt_regime: dict, active_lab: dict = None, df_bench_5m: pd.DataFrame = None, lab_mods: dict = None) -> dict:
    if is_jp:
        am = [f"{h:02d}:{m:02d}" for h in range(9, 12) for m in range(0, 60, 5) if not (h == 11 and m > 30)]
        pm = [f"{h:02d}:{m:02d}" for h in range(12, 16) for m in range(0, 60, 5) if not (h == 12 and m < 30) and not (h == 15 and m > 30)]
        slots, lunch_idx = am + pm, len(am) - 1
    else:
        slots = [f"{h:02d}:{m:02d}" for h in range(9, 17) for m in range(0, 60, 5) if not (h == 9 and m < 30) and not (h == 16 and m > 0)]
        lunch_idx = None

    n_slots = len(slots)
    market_today_str, target_date = _get_market_now(is_jp).strftime("%Y-%m-%d"), _get_target_session_date(is_jp)
    regime_code = mkt_regime.get("code", "NEUTRAL")
    vol_cls = _classify_vol_cluster(df_1d, is_jp)
    cluster_key, fallback_key = vol_cls["cluster"], vol_cls["fallback"]

    actual_map, vwap_map, vwap_p1_map, vwap_m1_map, vwap_p2_map, vwap_m2_map = {}, {}, {}, {}, {}, {}
    act_vol_map, act_dir_map, act_low_map, act_high_map, cvd_map = {}, {}, {}, {}, {}
    orb_high, orb_low, cum_cvd_latest, cum_vol_latest = None, None, 0.0, 0.0

    if df_5m is not None and not df_5m.empty:
        tmp_a = df_5m.copy(); idx_a = _convert_5m_index_to_market_tz(tmp_a, is_jp)
        tmp_a["_d"], tmp_a["_hm"] = idx_a.strftime("%Y-%m-%d"), idx_a.strftime("%H:%M")
        if market_today_str in tmp_a["_d"].values:
            sub_td = tmp_a[tmp_a["_d"] == market_today_str]
            cpv, cpv2, cv, ccvd = 0.0, 0.0, 0.0, 0.0
            if len(sub_td.head(6)) >= 2:
                orb_high, orb_low = round(float(sub_td.head(6)["High"].max()), 2), round(float(sub_td.head(6)["Low"].min()), 2)
            for _, r in sub_td.iterrows():
                hm = r["_hm"]
                if hm not in slots: continue
                ov, hv, lv, cv_px, vv = float(r.get("Open", r["Close"])), float(r.get("High", r["Close"])), float(r.get("Low", r["Close"])), float(r["Close"]), max(float(r.get("Volume", 0.0)), 0.0)
                tp = (hv + lv + cv_px) / 3.0
                cpv += tp * vv; cpv2 += (tp ** 2) * vv; cv += vv
                vw = (cpv / cv) if cv > 0 else cv_px
                sd_v = math.sqrt(max((cpv2 / cv) - (vw ** 2), 0.0)) if cv > 0 else 0.0
                hls = hv - lv
                clv = (((cv_px - lv) - (hv - cv_px)) / hls) if hls > 1e-6 else (1.0 if cv_px > ov else (-1.0 if cv_px < ov else 0.0))
                ccvd += clv * vv
                actual_map[hm], vwap_map[hm] = round(cv_px, 2), round(vw, 2)
                vwap_p1_map[hm], vwap_m1_map[hm], vwap_p2_map[hm], vwap_m2_map[hm] = round(vw + sd_v, 2), round(vw - sd_v, 2), round(vw + 2.0 * sd_v, 2), round(vw - 2.0 * sd_v, 2)
                act_vol_map[hm], act_dir_map[hm], act_low_map[hm], act_high_map[hm], cvd_map[hm] = vv, (1 if cv_px >= ov else -1), lv, hv, round(ccvd, 1)
                cum_cvd_latest, cum_vol_latest = ccvd, cv

    actual_arr = [actual_map.get(sl) for sl in slots]
    actual_vols_arr = [round(float(act_vol_map[sl]), 1) if sl in act_vol_map else None for sl in slots]
    actual_dirs_arr = [act_dir_map.get(sl, 1) for sl in slots]
    vwap_arr, vwap_p1_arr, vwap_m1_arr, vwap_p2_arr, vwap_m2_arr, cvd_arr = ([m.get(sl) for sl in slots] for m in (vwap_map, vwap_p1_map, vwap_m1_map, vwap_p2_map, vwap_m2_map, cvd_map))
    has_actual = bool(actual_map)
    last_act_idx = max([i for i, v in enumerate(actual_arr) if v is not None], default=-1)
    anchor_base_close = prev_px if has_actual else curr_px

    ledger = _dd_db_get("dd_forecast_ledger_v9", {})
    if not isinstance(ledger, dict): ledger = {}
    stock_hist = ledger.get(fc_code, {})
    if not isinstance(stock_hist, dict): stock_hist = {}

    w_evo, weights_updated = _update_weights_two_stage(_load_weights_evolution(), fc_code, df_1d, stock_hist, market_today_str, cluster_key, fallback_key)
    og_w, idr_w, cluster_n, shrink_alpha = _get_shrunk_cluster_brain(w_evo, cluster_key, fallback_key, regime_code)

    smap = {x["key"]: x for x in macro_sens}
    mk = "SOX" if ("SOX" in smap and abs(smap["SOX"]["corr"]) > 0.35) else ("NK_FUT" if (is_jp and "NK_FUT" in smap) else "SP500")
    mi = smap.get(mk, {"label": "日経先物" if is_jp else "S&P500", "beta": 0.5, "latest_diff": 0.0})
    fi = smap.get("USDJPY", {"label": "ドル円", "beta": 0.0, "latest_diff": 0.0})
    vix_d = macro_data.get("VIX", {}).get("diff_pct", 0.0)

    raw_macro_x, raw_fx_x, raw_news_x, raw_whale_x, raw_dow_x, raw_wick_x = float(mi["latest_diff"] * mi["beta"]), float(fi["latest_diff"] * fi["beta"]), float(news_res["shock_score"]), float(whale_anom["adj_pct"]), float(dow_next_avg), float(_compute_wick_bias(df_1d))
    mods = lab_mods if isinstance(lab_mods, dict) else {}
    lab_trust_mult, vpin_vboost, kyle_vboost, lab_rs30 = float(mods.get("lab_trust_mult", 1.0)), float(mods.get("vpin_vboost", 1.0)), float(mods.get("kyle_vboost", 1.0)), mods.get("rs_30m")

    lab_strength_dir = 0.0
    if isinstance(active_lab, dict) and active_lab:
        lab_strength_dir = (1.0 if _extract_lab_side(active_lab) == "LONG" else -1.0) * float(np.clip((float(active_lab.get("expect_pct", 50.0)) - 50.0) / 40.0, 0.0, 1.0)) * lab_trust_mult

    mg, fg, ng, wg, lg_open = raw_macro_x * og_w["macro"], raw_fx_x * og_w["fx"], raw_news_x * og_w["news"], raw_whale_x * og_w["whale"], lab_strength_dir * og_w["lab_bias"]
    lab_bias_pct = round(lab_strength_dir * idr_w["lab_bias"], 2)
    dow_adj = float(np.clip(raw_dow_x * idr_w["dow"], -0.4, 0.4))
    wick_adj = round(float(np.clip(raw_wick_x * (idr_w["wick"] / 0.80), -0.55, 0.55)), 2)
    tot_gap = float(np.clip(mg + fg + ng + wg + lg_open, -5.0, 5.0))
    raw_calib_pct, calib_n = _compute_self_calibration(stock_hist, df_1d, market_today_str)
    calib_pct = round(float(np.clip(raw_calib_pct * (idr_w["calib"] / 0.40), -0.65, 0.65)), 2)

    bench_day_rmaps, bench_today_rmap, bench_beta_5m, has_bench_5m = {}, {}, float(np.clip(mi.get("beta", 0.8), -2.5, 2.5)), False
    if df_bench_5m is not None and not df_bench_5m.empty:
        tmp_b = df_bench_5m.copy(); idx_b = _convert_5m_index_to_market_tz(tmp_b, is_jp)
        tmp_b["_d"], tmp_b["_hm"] = idx_b.strftime("%Y-%m-%d"), idx_b.strftime("%H:%M")
        for dsb, sb in tmp_b.groupby("_d"):
            if len(sb) >= 5 and float(sb["Open"].iloc[0]) > 0:
                opb = float(sb["Open"].iloc[0])
                rmb = {r["_hm"]: (float(r["Close"]) - opb) / opb for _, r in sb.iterrows() if r["_hm"] in slots}
                if rmb:
                    if dsb == market_today_str: bench_today_rmap = rmb
                    else: bench_day_rmaps[dsb] = rmb
        has_bench_5m = len(bench_day_rmaps) >= 5

    slot_means, slot_stds, slot_vols, slot_inc_stds = np.zeros(n_slots), np.full(n_slots, 0.003), np.zeros(n_slots), np.full(n_slots, 0.0022)
    slot_q10, slot_q25, slot_q75, slot_q90 = np.zeros(n_slots), np.zeros(n_slots), np.zeros(n_slots), np.zeros(n_slots)
    regime_tag, rmaps, alpha_rmaps, rdates, day_gaps_hist, day_ranges_hist, vmaps, use_maps, weights = "標準", [], [], [], [], [], [], [], []
    gap_fill_stats = {"prob": None, "avg_min": None, "n_samples": 0, "dir": "FLAT"}

    if df_5m is not None and not df_5m.empty:
        tmp = df_5m.copy(); idx_dt = _convert_5m_index_to_market_tz(tmp, is_jp)
        tmp["_d"], tmp["_hm"] = idx_dt.strftime("%Y-%m-%d"), idx_dt.strftime("%H:%M")
        pdays = [d for d in sorted(tmp["_d"].unique().tolist()) if d != market_today_str]
        want_gu, want_gd = tot_gap >= 0.15, tot_gap <= -0.15
        regime_tag = "GU類似加重" if want_gu else ("GD類似加重" if want_gd else "フラット加重")
        gf_total, gf_filled, gf_mins, target_gap_dir, prev_dc = 0, 0, [], (1 if want_gu else (-1 if want_gd else 0)), None

        if has_bench_5m:
            sr_l, br_l = [], []
            for ds in pdays:
                if ds in bench_day_rmaps:
                    ss = tmp[tmp["_d"] == ds]
                    if len(ss) >= 10 and float(ss["Open"].iloc[0]) > 0 and bench_day_rmaps[ds]:
                        sr_l.append((float(ss["Close"].iloc[-1]) - float(ss["Open"].iloc[0])) / float(ss["Open"].iloc[0]))
                        br_l.append(list(bench_day_rmaps[ds].values())[-1])
            if len(sr_l) >= 6 and float(np.var(br_l)) > 1e-8:
                bench_beta_5m = float(np.clip(float(np.cov(sr_l, br_l)[0, 1]) / float(np.var(br_l)), -2.5, 2.5))

        for di, ds in enumerate(pdays):
            sub = tmp[tmp["_d"] == ds]
            if len(sub) < 10 or float(sub["Open"].iloc[0]) <= 0: continue
            op, cl_end = float(sub["Open"].iloc[0]), float(sub["Close"].iloc[-1])
            dgap = ((op - prev_dc) / prev_dc * 100.0) if (prev_dc and prev_dc > 0) else 0.0
            drng = ((float(sub["High"].max()) if "High" in sub.columns else float(sub["Close"].max())) - (float(sub["Low"].min()) if "Low" in sub.columns else float(sub["Close"].min()))) / op * 100.0
            if prev_dc and prev_dc > 0 and abs(dgap) >= 0.20 and (target_gap_dir == 0 or dgap * target_gap_dir > 0):
                gf_total += 1
                hits = np.where(sub["Low"].values <= prev_dc)[0] if dgap > 0 else np.where(sub["High"].values >= prev_dc)[0]
                if len(hits) > 0: gf_filled += 1; gf_mins.append((int(hits[0]) + 1) * 5)
            prev_dc = cl_end
            rm, arm, vm, brm = {}, {}, {}, (bench_day_rmaps.get(ds, {}) if has_bench_5m else {})
            for _, row in sub.iterrows():
                hmk = row["_hm"]
                if hmk in slots:
                    rr = (float(row["Close"]) - op) / op
                    rm[hmk], arm[hmk], vm[hmk] = rr, (rr - bench_beta_5m * brm[hmk] if (has_bench_5m and hmk in brm) else rr), float(row["Volume"])
            if rm:
                bw = float(np.exp(1.2 * (di / max(len(pdays) - 1, 1)))) * (2.5 if ((want_gu and dgap > 0.1) or (want_gd and dgap < -0.1)) else 1.0)
                rmaps.append(rm); alpha_rmaps.append(arm); rdates.append(ds); day_gaps_hist.append(dgap); day_ranges_hist.append(drng); vmaps.append(vm); weights.append(bw)

        if gf_total >= 2:
            gap_fill_stats = {"prob": round(gf_filled / gf_total * 100.0, 0), "avg_min": int(round(float(np.mean(gf_mins)), 0)) if gf_mins else None, "n_samples": gf_total, "dir": "GU" if target_gap_dir > 0 else ("GD" if target_gap_dir < 0 else "BOTH")}

        use_maps = alpha_rmaps if has_bench_5m else rmaps
        for i, sl in enumerate(slots):
            rvm, rvv, wv, vv = [], [], [], []
            for rmu, rmr, vm, w in zip(use_maps, rmaps, vmaps, weights):
                if sl in rmu: rvm.append(rmu[sl]); rvv.append(rmr[sl]); wv.append(w); vv.append(vm[sl])
            if len(rvm) >= 3:
                wa = np.array(wv) / np.sum(wv); ram, rav = np.array(rvm), np.array(rvv)
                wm, wmr = float(np.sum(wa * ram)), float(np.sum(wa * rav))
                slot_means[i], slot_stds[i], slot_vols[i] = wm, max(float(np.sqrt(np.sum(wa * ((rav - wmr) ** 2)))), 0.0025), (float(np.mean(vv)) if vv else 0.0)
                oi = np.argsort(rav); ras, was = rav[oi] - wmr, wa[oi]; cdfs = np.cumsum(was) - 0.5 * was
                slot_q10[i], slot_q25[i], slot_q75[i], slot_q90[i] = (wm + float(np.interp(q, cdfs, ras)) for q in (0.10, 0.25, 0.75, 0.90))
            else:
                sf = 0.003 + 0.009 * np.sqrt((i + 1) / n_slots)
                slot_stds[i], slot_q10[i], slot_q25[i], slot_q75[i], slot_q90[i] = sf, -1.28 * sf, -0.67 * sf, 0.67 * sf, 1.28 * sf

        for i in range(n_slots):
            slc, slp = slots[i], (slots[i - 1] if i > 0 else None)
            iv, iw = [], []
            for rmr, w in zip(rmaps, weights):
                if slp is None and slc in rmr: iv.append(rmr[slc]); iw.append(w)
                elif slp is not None and slc in rmr and slp in rmr: iv.append(rmr[slc] - rmr[slp]); iw.append(w)
            if len(iv) >= 3:
                wai, ia = np.array(iw) / np.sum(iw), np.array(iv)
                slot_inc_stds[i] = max(float(np.sqrt(np.sum(wai * ((ia - float(np.sum(wai * ia))) ** 2)))), 0.0012)
            else:
                slot_inc_stds[i] = 0.0022 * (1.35 if (i < 6 or i >= n_slots - 6) else 0.85)

    vol_clock_active = bool(float(np.sum(slot_vols)) > 0 and n_slots > 1)
    if vol_clock_active:
        cva = np.cumsum(slot_vols)
        vol_frac = np.clip((cva - float(cva[0])) / max(float(cva[-1]) - float(cva[0]), 1e-6), 0.0, 1.0)
    else:
        vol_frac = np.linspace(0.0, 1.0, max(n_slots, 1))

    lunch_jump_std_pct = 0.0
    pm_open_idx = (lunch_idx + 1) if (is_jp and lunch_idx is not None and (lunch_idx + 1) < n_slots) else None
    if pm_open_idx is not None:
        ljv = [(rmr[slots[pm_open_idx]] - rmr[slots[lunch_idx]], w) for rmr, w in zip(rmaps, weights) if slots[lunch_idx] in rmr and slots[pm_open_idx] in rmr]
        if len(ljv) >= 3:
            wal = np.array([x[1] for x in ljv]); wal /= np.sum(wal); lja = np.array([x[0] for x in ljv])
            ljs = max(float(np.sqrt(np.sum(wal * ((lja - float(np.sum(wal * lja))) ** 2)))), float(np.mean(slot_inc_stds)) * 1.4)
        else:
            ljs = float(np.mean(slot_inc_stds)) * 1.8
        slot_inc_stds[pm_open_idx], lunch_jump_std_pct = ljs, round(ljs * 100.0, 2)

    ml_3way_model = _fit_short_3way_logreg(df_5m, is_jp, slots, slot_vols, float(vol_cls["atr_pct"]), horizon_slots=6)
    mean_inc_std = float(np.mean(slot_inc_stds)) if len(slot_inc_stds) else 0.0022
    hv_th = max(mean_inc_std * 1.18, float(np.percentile(slot_inc_stds, 75)) if len(slot_inc_stds) else mean_inc_std * 1.18)
    raw_hv, zs = [], None
    for i in range(n_slots):
        if slot_inc_stds[i] >= hv_th:
            if zs is None: zs = i
        elif zs is not None:
            raw_hv.append([zs, i - 1]); zs = None
    if zs is not None: raw_hv.append([zs, n_slots - 1])
    merged_hv = []
    for sp in raw_hv:
        if merged_hv and sp[0] - merged_hv[-1][1] <= 2: merged_hv[-1][1] = sp[1]
        else: merged_hv.append(list(sp))
    high_vol_zones = [{"start_slot": slots[s], "end_slot": slots[e], "width_slots": e - s + 1, "show_label": bool(e - s + 1 >= 3), "avg_move_pct": round(float(np.mean(slot_inc_stds[s:e + 1])) * 100.0, 2)} for s, e in merged_hv]
    vol_profile_meta = {"mean_move_pct": round(mean_inc_std * 100.0, 2), "max_move_pct": round(float(np.max(slot_inc_stds)) * 100.0, 2) if len(slot_inc_stds) else 0.22, "zone_cnt": len(high_vol_zones)}

    rvol, vol_spikes = None, []
    if has_actual:
        cav, cavg = 0.0, 0.0
        for i, sl in enumerate(slots):
            if sl in act_vol_map:
                av, avgv = act_vol_map[sl], float(slot_vols[i]); cav += av; cavg += avgv
                if avgv > 0 and av >= avgv * 2.5 and actual_arr[i] is not None:
                    vol_spikes.append({"time": sl, "price": actual_arr[i], "dir": act_dir_map.get(sl, 1), "ratio": round(av / avgv, 1)})
        if cavg > 0: rvol = round(cav / cavg, 2)

    pos_vols = [v for v in slot_vols if v > 0]
    avg_5m_vol = float(np.mean(pos_vols)) if pos_vols else (float(df_1d["Volume"].tail(20).mean()) / max(n_slots, 1))
    cvd_div = _detect_cvd_divergence(slots, actual_arr, cvd_arr, act_vol_map)
    gap_open15 = _evaluate_gap_open15(has_actual, slots, actual_arr, vwap_arr, act_low_map, act_high_map, act_vol_map, slot_vols, prev_px)

    cat_al = news_res.get("catalyst_alert")
    cat_drift_boost = (float(cat_al.get("boost_drift_pct", 0.0)) / 100.0) if (isinstance(cat_al, dict) and cat_al.get("active")) else 0.0
    est_open = anchor_base_close * (1.0 + tot_gap / 100.0)
    drift = float(np.clip((raw_news_x * idr_w["news"]) + ((dow_adj + wick_adj + calib_pct + lab_bias_pct) / 100.0) + cat_drift_boost, -0.045, 0.045))
    vboost = (1.0 + abs(raw_news_x) * 0.25) * (1.0 + max(0.0, vix_d / 100.0) * 1.2) * vpin_vboost * kyle_vboost

    start_rem_idx = (last_act_idx + 1) if (has_actual and last_act_idx >= 0) else 0
    rem_frac_now = max(float(1.0 - vol_frac[last_act_idx]), 0.04) if (has_actual and last_act_idx >= 0) else 1.0
    rem_sigma_pct = max(float(np.sqrt(np.sum(slot_inc_stds[start_rem_idx:] ** 2))) if start_rem_idx < n_slots else float(slot_inc_stds[-1]) * 0.5, 0.002) * vboost

    hvn_wall_px, ob_sup_px = 0.0, 0.0
    if isinstance(active_lab, dict) and active_lab:
        d2c = active_lab.get("daily_2y") if isinstance(active_lab.get("daily_2y"), dict) else {}
        hvn_wall_px, ob_sup_px = float(d2c.get("hvn_wall_price", 0.0) or 0.0), float(active_lab.get("ob_support_px", 0.0) or 0.0)

    target_atr = max(float(vol_cls["atr_pct"]), 0.8)
    max_r_cap_pre, premarket_medoid, pre_medoid_rel, pre_eigen_wave, has_pre_eigen = (target_atr * 1.45) / 100.0, None, np.zeros(n_slots), np.zeros(n_slots), False
    if use_maps and rdates:
        nr, max_nr = len(use_maps), max(float(vol_cls["atr_pct"]) * 2.2, 5.0)
        vm_idx = [i for i in range(nr) if abs((day_gaps_hist[i] if i < len(day_gaps_hist) else 0.0) - tot_gap) <= 3.0 and (day_ranges_hist[i] if i < len(day_ranges_hist) else target_atr) <= max_nr]
        scored = sorted([(abs((day_gaps_hist[i] if i < len(day_gaps_hist) else 0.0) - tot_gap) + abs((day_ranges_hist[i] if i < len(day_ranges_hist) else target_atr) - target_atr) * 0.6 + 0.25 * (1.0 - i / max(nr - 1, 1)), i) for i in (vm_idx or range(nr))])
        bi = scored[0][1]
        brm, bds, bgap, brng = use_maps[bi], rdates[bi], (round(float(day_gaps_hist[bi]), 2) if bi < len(day_gaps_hist) else 0.0), (float(day_ranges_hist[bi]) if bi < len(day_ranges_hist) else target_atr)
        amp_s = float(np.clip(target_atr / max(brng, 0.5), 0.40, 1.35))
        med_path, lvr = [], 0.0
        for i, sl in enumerate(slots):
            if sl in brm: lvr = float(brm[sl])
            rs = float(np.clip(lvr * amp_s, -max_r_cap_pre, max_r_cap_pre))
            pre_medoid_rel[i] = rs
            med_path.append(round(float(est_open * (1.0 + rs)), 2) if (sl in brm or med_path) else None)
        if n_slots >= 6:
            m_hf = pre_medoid_rel - (pre_medoid_rel[0] + (pre_medoid_rel[-1] - pre_medoid_rel[0]) * np.linspace(0.0, 1.0, n_slots))
            if float(np.ptp(m_hf)) > 1e-5:
                pre_eigen_wave = m_hf * float(np.clip(((target_atr / 100.0) * 0.55) / max(float(np.ptp(m_hf)), 0.003), 0.35, 0.85))
                has_pre_eigen = True
        premarket_medoid = {"date": bds, "gap_pct": bgap, "amp_scale": round(amp_s, 2), "data": med_path, "mode": "PREMARKET"}

    p50, p85, p15, bdiff, p68, p32, bdiff_inner = [], [], [], [], [], [], []
    for i, sl in enumerate(slots):
        wrel = (0.58 * slot_means[i] + 0.42 * pre_medoid_rel[i]) if has_pre_eigen else slot_means[i]
        mid = _apply_hvn_ob_bounce(est_open * (1.0 + wrel + (pre_eigen_wave[i] * 0.35 if has_pre_eigen else 0.0) + drift * float(vol_frac[i])), est_open, hvn_wall_px, ob_sup_px, vp, "NONE")
        uo, do = max((slot_q90[i] - slot_means[i]) * vboost, slot_stds[i] * vboost * 0.65), max((slot_means[i] - slot_q10[i]) * vboost, slot_stds[i] * vboost * 0.65)
        ui, di_s = max((slot_q75[i] - slot_means[i]) * vboost, uo * 0.42), max((slot_means[i] - slot_q25[i]) * vboost, do * 0.42)
        hi, lo, hi_i, lo_i = mid + est_open * uo, max(mid - est_open * do, anchor_base_close * 0.5), mid + est_open * ui, max(mid - est_open * di_s, anchor_base_close * 0.5)
        p50.append(round(float(mid), 2)); p85.append(round(float(hi), 2)); p15.append(round(float(lo), 2)); bdiff.append(round(float(hi - lo), 2)); p68.append(round(float(hi_i), 2)); p32.append(round(float(lo_i), 2)); bdiff_inner.append(round(float(hi_i - lo_i), 2))

    saved_today = stock_hist.get(market_today_str) if isinstance(stock_hist.get(market_today_str), dict) else None
    if has_actual and bool(saved_today and saved_today.get("locked_premarket") is True):
        locked_p50, locked_p85, locked_p15, locked_bdiff = saved_today["p50"], saved_today["p85"], saved_today["p15"], saved_today["band_diff"]
        locked_p32 = saved_today.get("p32", [round(m - (m - l) * 0.52, 2) for m, l in zip(locked_p50, locked_p15)])
        locked_bdiff_in = saved_today.get("band_diff_in", [round(d * 0.52, 2) for d in locked_bdiff])
        is_locked = True
    else:
        locked_p50, locked_p85, locked_p15, locked_bdiff, locked_p32, locked_bdiff_in, is_locked = p50, p85, p15, bdiff, p32, bdiff_inner, False
        if not has_actual and _is_valid_premarket_lock_window(is_jp, target_date):
            stock_hist[target_date] = {
                "p50": p50, "p85": p85, "p15": p15, "band_diff": bdiff, "p32": p32, "band_diff_in": bdiff_inner,
                "locked_premarket": True, "locked_at": _get_market_now(is_jp).strftime("%Y-%m-%d %H:%M:%S"),
                "regime_code": regime_code, "cluster_key": cluster_key, "pred_open_px": round(float(est_open), 4),
                "pred_open_gap_pct": round(float(tot_gap), 4), "slot_mean_end_pct": round(float(slot_means[-1]) * 100.0, 4),
                "factor_contribs": {"open_gap": {"macro": round(raw_macro_x, 4), "fx": round(raw_fx_x, 4), "news": round(raw_news_x, 4), "whale": round(raw_whale_x, 4), "lab_bias": round(lab_strength_dir, 4)}, "intraday_drift": {"news": round(raw_news_x, 4), "dow": round(raw_dow_x, 4), "wick": round(raw_wick_x, 4), "calib": round(raw_calib_pct, 4), "lab_bias": round(lab_strength_dir, 4)}},
            }
            for old_k in sorted(stock_hist.keys())[:-15]: del stock_hist[old_k]
            ledger[fc_code] = stock_hist; _dd_db_set("dd_forecast_ledger_v9", ledger)

    expansion_reg = _detect_expansion_regime(has_actual, last_act_idx, slots, actual_arr, locked_p85, locked_p15, is_locked, vwap_arr, vwap_p2_arr, vwap_m2_arr, vwap_p1_arr, vwap_m1_arr, act_vol_map, act_dir_map, slot_vols, rvol, cat_al)
    exp_dir = expansion_reg["dir"] if expansion_reg["active"] else "NONE"
    eff_slot_inc_stds = slot_inc_stds.copy()
    if has_actual and last_act_idx >= 2 and expansion_reg["active"]:
        rr30 = [(actual_arr[i] - actual_arr[i - 1]) / actual_arr[i - 1] for i in range(max(1, last_act_idx - 5), last_act_idx + 1) if actual_arr[i] is not None and actual_arr[i - 1] is not None and actual_arr[i - 1] > 0]
        if len(rr30) >= 2:
            eff_slot_inc_stds = np.maximum(eff_slot_inc_stds, float(np.std(rr30)))
            if start_rem_idx < n_slots: rem_sigma_pct = max(float(np.sqrt(np.sum(eff_slot_inc_stds[start_rem_idx:] ** 2))), 0.002) * vboost

    max_r_cap = ((target_atr * 2.8) if expansion_reg["active"] else (target_atr * 1.45)) / 100.0
    knn_match = {"matched_dates": [], "mean_dist": None, "knn_rel_moves": {}, "knn_top1_moves": {}, "knn_q10": {}, "knn_q90": {}, "analog_paths": []}
    atr_norm = max(vol_cls["atr_pct"] / 100.0, 0.005)
    if has_actual and last_act_idx >= 2 and use_maps:
        vslots = [slots[i] for i in range(last_act_idx + 1) if actual_arr[i] is not None]
        if len(vslots) >= 3:
            fpx = actual_map[vslots[0]]; tgap = (fpx - prev_px) / max(prev_px, 1e-4) * 100.0
            trets = [((actual_map[sl] - fpx) / max(fpx, 1e-4)) - (bench_beta_5m * bench_today_rmap[sl] if (has_bench_5m and sl in bench_today_rmap) else 0.0) for sl in vslots]
            tvec = np.array(trets) / atr_norm; tnorm = float(np.linalg.norm(tvec))
            cands = []
            for ds, rm, vm, dg, dr in zip(rdates, use_maps, vmaps, day_gaps_hist, day_ranges_hist):
                if all(sl in rm for sl in vslots):
                    hvec = np.array([rm[sl] for sl in vslots]) / atr_norm; hnorm = float(np.linalg.norm(hvec))
                    csim = float(np.dot(tvec, hvec) / (tnorm * hnorm)) if (tnorm > 1e-6 and hnorm > 1e-6) else (1.0 - min(float(np.linalg.norm(tvec - hvec)), 1.0))
                    rpen = 0.0
                    if rvol and rvol > 0:
                        avs = sum(float(slot_vols[slots.index(sl)]) for sl in vslots)
                        if avs > 0: rpen = min(abs(math.log(max(rvol, 0.1) / max(sum(vm.get(sl, 0.0) for sl in vslots) / avs, 0.1))) * 0.18, 0.35)
                    gpen = (0.22 if tgap * dg < 0 else (-0.06 if abs(tgap - dg) <= 0.6 else 0.0)) if abs(tgap) >= 0.25 else 0.0
                    cands.append((max(0.001, (1.0 - csim) * 0.5 + rpen + gpen), ds, rm, dg, dr))
            if cands:
                top_k = sorted(cands, key=lambda x: x[0])[:5]
                dists = np.array([c[0] for c in top_k]); wknn = (1.0 / (dists + 0.015)); wknn /= wknn.sum()
                asl, apx = slots[last_act_idx], actual_arr[last_act_idx]
                lvr_now = float(np.clip(float(np.ptp(trets)) / max(float(np.sqrt(np.sum(slot_inc_stds[:last_act_idx + 1] ** 2))) * 1.4, 0.003), 0.70, 1.55))
                kr, kt1, kq10, kq90 = {}, {}, {}, {}
                for i in range(last_act_idx, n_slots):
                    sl, vi, wi = slots[i], [], []
                    for rk, (_, _, rmk, _, drk) in enumerate(top_k):
                        if sl in rmk and asl in rmk:
                            rs = float(np.clip((rmk[sl] - rmk[asl]) * float(np.clip((target_atr / max(float(drk), 0.5)) * lvr_now, 0.45, 1.55)), -max_r_cap, max_r_cap))
                            vi.append(rs); wi.append(wknn[rk])
                            if rk == 0: kt1[i] = rs
                    if vi:
                        wa_k = np.array(wi) / np.sum(wi); va_k = np.array(vi)
                        kr[i], kq10[i], kq90[i] = float(np.sum(wa_k * va_k)), float(np.min(va_k)), float(np.max(va_k))
                apaths = []
                for _, dsk, rmk, dgk, drk in top_k:
                    if asl not in rmk: continue
                    ask = float(np.clip((target_atr / max(float(drk), 0.5)) * lvr_now, 0.45, 1.55))
                    pa = [round(float(apx * (1.0 + float(np.clip((rmk[slots[i]] - rmk[asl]) * ask, -max_r_cap, max_r_cap)))), 2) if (i >= last_act_idx and slots[i] in rmk) else None for i in range(n_slots)]
                    apaths.append({"date": dsk, "gap_pct": round(float(dgk), 2), "amp_scale": round(ask, 2), "data": pa})
                knn_match = {"matched_dates": [c[1] for c in top_k], "mean_dist": round(float(np.mean(dists)), 4), "knn_rel_moves": kr, "knn_top1_moves": kt1, "knn_q10": kq10, "knn_q90": kq90, "analog_paths": apaths}

    medoid_analog = {**knn_match["analog_paths"][0], "mode": "INTRADAY_KNN"} if (has_actual and knn_match["analog_paths"]) else premarket_medoid
    live_vwap_bias, bench_live_alpha_adj, mom_30m, cur_vwap_last, lunch_gap_adj_pct = 0.0, 0.0, 0.0, None, 0.0

    if has_actual and last_act_idx >= 0:
        live_p50, live_p85, live_p15, live_bdiff, live_p32, live_bdiff_in = ([None] * n_slots for _ in range(6))
        apx, amean = actual_arr[last_act_idx], slot_means[last_act_idx]
        cur_vwap = cur_vwap_last = vwap_arr[last_act_idx] or apx
        rv6 = [v for v in actual_arr[max(0, last_act_idx - 6):last_act_idx + 1] if v is not None]
        mom_30m = ((rv6[-1] - rv6[0]) / max(rv6[0], 1e-4)) if len(rv6) >= 2 else 0.0
        if has_bench_5m and bench_today_rmap:
            btv = [bench_today_rmap[slots[k]] for k in range(last_act_idx + 1) if slots[k] in bench_today_rmap]
            if len(btv) >= 2: bench_live_alpha_adj = float(np.clip(bench_beta_5m * (btv[-1] - btv[max(0, len(btv) - 6)]) * 0.45, -0.012, 0.012))
        lgr = 0.0
        if is_jp and lunch_idx is not None and last_act_idx == lunch_idx:
            lgp = float(np.clip(float(macro_data.get("NK_FUT", {}).get("diff_pct", 0.0)) * float(smap.get("NK_FUT", {}).get("beta", mi.get("beta", 0.5))) * 0.35 + float(macro_data.get("USDJPY", {}).get("diff_pct", 0.0)) * float(fi.get("beta", 0.0)) * 0.35, -0.8, 0.8))
            lunch_gap_adj_pct, lgr = round(lgp, 2), lgp / 100.0
        drift_eff = float(np.clip(drift, -0.055 if expansion_reg["active"] else -0.032, 0.055 if expansion_reg["active"] else 0.032))
        unc_b = (0.008 if exp_dir == "UP" else (-0.008 if exp_dir == "DOWN" else 0.0)) if expansion_reg.get("unconfirmed_catalyst") else 0.0
        live_vwap_bias = float(np.clip(((apx - cur_vwap) / max(cur_vwap, 1e-4)) * 0.45 + mom_30m * 0.38 + float(gap_open15.get("bias", 0.0)) + bench_live_alpha_adj + unc_b, -0.045 if expansion_reg["active"] else -0.022, 0.045 if expansion_reg["active"] else 0.022))
        km, kt1, kq10, kq90 = knn_match["knn_rel_moves"], knn_match["knn_top1_moves"], knn_match["knn_q10"], knn_match["knn_q90"]
        va0 = float(vol_frac[last_act_idx]); vrd = max(1.0 - va0, 1e-4)
        for i in range(last_act_idx, n_slots):
            rvf = float(np.clip((vol_frac[i] - va0) / vrd, 0.0, 1.0)) if i > last_act_idx else 0.0
            pms = lgr if (pm_open_idx is not None and i >= pm_open_idx) else 0.0
            brel = (slot_means[i] - amean) + (drift_eff * 0.55 + live_vwap_bias) * rvf + pms
            if i in km:
                kw = 0.35 if expansion_reg["active"] else 0.62
                rrel = (1.0 - kw) * brel + kw * ((0.55 * km[i] + 0.45 * kt1[i] if i in kt1 else km[i]) + pms)
            else:
                rrel = brel + (pre_eigen_wave[i] - pre_eigen_wave[last_act_idx]) * 0.55
            mid = _apply_hvn_ob_bounce(apx * (1.0 + rrel), apx, hvn_wall_px, ob_sup_px, vp, exp_dir)
            uss = 0.0012 if i == last_act_idx else float(np.sqrt(np.sum(eff_slot_inc_stds[last_act_idx + 1:i + 1] ** 2)))
            ub = apx * max(uss * max((slot_q90[i] - slot_means[i]) / max(slot_stds[i], 1e-4), 0.75) * vboost, 0.0015)
            db = apx * max(uss * max((slot_means[i] - slot_q10[i]) / max(slot_stds[i], 1e-4), 0.75) * vboost, 0.0015)
            if i in kq90 and i in kq10:
                ub = 0.75 * ub + 0.25 * max(apx * (1.0 + kq90[i] + pms) - mid, ub * 0.5)
                db = 0.75 * db + 0.25 * max(mid - apx * (1.0 + kq10[i] + pms), db * 0.5)
            hi, lo, hi_i, lo_i = mid + ub, max(mid - db, apx * 0.5), mid + ub * 0.52, max(mid - db * 0.52, apx * 0.5)
            live_p50[i], live_p85[i], live_p15[i], live_bdiff[i], live_p32[i], live_bdiff_in[i] = round(float(mid), 2), round(float(hi), 2), round(float(lo), 2), round(float(hi - lo), 2), round(float(lo_i), 2), round(float(hi_i - lo_i), 2)
    else:
        drift_eff = drift
        live_p50, live_p85, live_p15, live_bdiff, live_p32, live_bdiff_in = p50, p85, p15, bdiff, p32, bdiff_inner

    rem_drift_pct = ((drift_eff * 0.6 + live_vwap_bias) * rem_frac_now + (lunch_gap_adj_pct / 100.0)) if has_actual else drift_eff
    verify_stats = {"has_verify": False, "in_cone_pct": 0.0, "err_pct": 0.0, "n_pts": 0, "finalized": False}
    if has_actual and is_locked:
        errs = [abs(a - m) / max(m, 1e-4) * 100.0 for a, m in zip(actual_arr, locked_p50) if a is not None]
        if errs:
            in_c = sum(1 for a, lo, hi in zip(actual_arr, locked_p15, locked_p85) if a is not None and lo <= a <= hi)
            isf = bool(len(errs) >= int(n_slots * 0.80))
            verify_stats = {"has_verify": True, "in_cone_pct": round(in_c / len(errs) * 100.0, 1), "err_pct": round(float(np.mean(errs)), 2), "n_pts": len(errs), "finalized": isf}
            if isf and isinstance(saved_today, dict):
                saved_today["verify_result"] = {"in_cone_pct": verify_stats["in_cone_pct"], "err_pct": verify_stats["err_pct"], "rvol_hi": bool(rvol is not None and rvol >= 1.3), "finalized": True}
                stock_hist[market_today_str] = saved_today; ledger[fc_code] = stock_hist; _dd_db_set("dd_forecast_ledger_v9", ledger)

    inv_reasons = []
    if has_actual and last_act_idx >= 0:
        ca = actual_arr[last_act_idx]
        if is_locked:
            lol, hil = locked_p15[last_act_idx], locked_p85[last_act_idx]; bwl = max(hil - lol, ca * 0.005)
            if ca > hil + bwl * 0.5: inv_reasons.append("上方向へ予測バンド大幅ブレイク（想定超え急騰）")
            elif ca < lol - bwl * 0.5: inv_reasons.append("下方向へ予測バンド大幅割れ（想定超え急落）")
            if verify_stats["n_pts"] >= 6 and verify_stats["in_cone_pct"] < 45.0: inv_reasons.append(f"朝ロック予測の収束率が低下（{verify_stats['in_cone_pct']}%）")
        if isinstance(active_lab, dict) and float(active_lab.get("expect_pct", 0.0)) >= 70.0:
            ls, dc = _extract_lab_side(active_lab), (ca - anchor_base_close) / max(anchor_base_close, 1e-4) * 100.0
            if (ls == "LONG" and dc <= -1.5) or (ls == "SHORT" and dc >= 1.5): inv_reasons.append(f"LAB強シグナル({ls})に対し実測が大きく逆行({dc:+.2f}%)")
        if knn_match["mean_dist"] is not None and knn_match["mean_dist"] > 0.65: inv_reasons.append(f"k-NN過去類似日と大きく乖離（未知レジーム: dist={knn_match['mean_dist']}）")

    imin_lk, imax_lk, lk_ti = int(np.argmin(locked_p50)), int(np.argmax(locked_p50)), min(3, n_slots - 1)
    vli = [i for i, v in enumerate(live_p50) if v is not None]
    if vli:
        imin_lv, imax_lv, lv_ti = min(vli, key=lambda i: live_p50[i]), max(vli, key=lambda i: live_p50[i]), vli[min(2, len(vli) - 1)]
        lv_c, lv_bt, lv_brt, lv_btr, lv_brtr = live_p50[vli[-1]], round(max(live_p85[i] for i in vli), 2), round(min(live_p15[i] for i in vli), 2), round(live_p85[lv_ti], 2), round(live_p15[lv_ti], 2)
    else:
        imin_lv, imax_lv, lv_c, lv_bt, lv_brt, lv_btr, lv_brtr = imin_lk, imax_lk, locked_p50[-1], round(max(locked_p85), 2), round(min(locked_p15), 2), round(locked_p85[lk_ti], 2), round(locked_p15[lk_ti], 2)

    return {
        "target_date": target_date, "is_locked": is_locked, "has_actual": has_actual, "last_act_idx": last_act_idx, "anchor_base_close": anchor_base_close,
        "slots": slots, "lunch_idx": lunch_idx, "vols": [round(float(v), 1) for v in slot_vols], "actual_vols": actual_vols_arr, "actual_dirs": actual_dirs_arr, "cvd_arr": cvd_arr,
        "actual": actual_arr, "vwap": vwap_arr, "vwap_p1": vwap_p1_arr, "vwap_m1": vwap_m1_arr, "vwap_p2": vwap_p2_arr, "vwap_m2": vwap_m2_arr,
        "rvol": rvol, "orb_high": orb_high, "orb_low": orb_low, "vol_spikes": vol_spikes, "avg_5m_vol": avg_5m_vol, "cvd_div": cvd_div, "gap_open15": gap_open15,
        "expansion_regime": expansion_reg, "gap_fill": gap_fill_stats, "rem_sigma_pct": rem_sigma_pct, "rem_drift_pct": rem_drift_pct, "rem_frac_now": rem_frac_now,
        "locked_p50": locked_p50, "locked_p85": locked_p85, "locked_p15": locked_p15, "locked_bdiff": locked_bdiff, "locked_p32": locked_p32, "locked_bdiff_in": locked_bdiff_in,
        "live_p50": live_p50, "live_p85": live_p85, "live_p15": live_p15, "live_bdiff": live_bdiff, "live_p32": live_p32, "live_bdiff_in": live_bdiff_in,
        "est_open_px": round(est_open, 2), "est_open_gap_pct": round(tot_gap, 2),
        "locked_close_px": locked_p50[-1], "locked_close_chg": round((locked_p50[-1] - anchor_base_close) / max(anchor_base_close, 1e-4) * 100.0, 2),
        "locked_dip_idx": imin_lk, "locked_dip_time": slots[imin_lk], "locked_dip_px": locked_p50[imin_lk], "locked_peak_idx": imax_lk, "locked_peak_time": slots[imax_lk], "locked_peak_px": locked_p50[imax_lk],
        "locked_bull_trig": round(locked_p85[lk_ti], 2), "locked_bull_target": round(max(locked_p85), 2), "locked_bear_trig": round(locked_p15[lk_ti], 2), "locked_bear_target": round(min(locked_p15), 2),
        "live_close_px": lv_c, "live_close_chg": round((lv_c - anchor_base_close) / max(anchor_base_close, 1e-4) * 100.0, 2),
        "live_dip_idx": imin_lv, "live_dip_time": slots[imin_lv], "live_dip_px": live_p50[imin_lv], "live_peak_idx": imax_lv, "live_peak_time": slots[imax_lv], "live_peak_px": live_p50[imax_lv],
        "live_bull_trig": lv_btr, "live_bull_target": lv_bt, "live_bear_trig": lv_brtr, "live_bear_target": lv_brt,
        "est_close_px": lv_c if has_actual else locked_p50[-1], "est_close_chg": round(((lv_c if has_actual else locked_p50[-1]) - anchor_base_close) / max(anchor_base_close, 1e-4) * 100.0, 2),
        "dip_idx": imin_lv if has_actual else imin_lk, "dip_time": slots[imin_lv] if has_actual else slots[imin_lk], "dip_px": live_p50[imin_lv] if has_actual else locked_p50[imin_lk],
        "peak_idx": imax_lv if has_actual else imax_lk, "peak_time": slots[imax_lv] if has_actual else slots[imax_lk], "peak_px": live_p50[imax_lv] if has_actual else locked_p50[imax_lk],
        "bull_trig": lv_btr if has_actual else round(locked_p85[lk_ti], 2), "bull_target": lv_bt if has_actual else round(max(locked_p85), 2),
        "bear_trig": lv_brtr if has_actual else round(locked_p15[lk_ti], 2), "bear_target": lv_brt if has_actual else round(min(locked_p15), 2),
        "verify": verify_stats, "verify_hist_15": _extract_ledger_verify_history(ledger, is_jp), "meta_audit": _audit_meta_labeling_accuracy(ledger, fc_code, is_jp, regime_code, rvol, tot_gap),
        "regime_tag": regime_tag, "has_bench_5m": has_bench_5m, "bench_beta_5m": round(bench_beta_5m, 2), "vol_clock_active": vol_clock_active,
        "lunch_jump_std_pct": lunch_jump_std_pct, "lunch_gap_adj_pct": lunch_gap_adj_pct, "ml_3way_model": ml_3way_model,
        "lab_mods": {"has_lab": bool(mods.get("has_lab", False)), "lab_trust_mult": lab_trust_mult, "vpin_vboost": vpin_vboost, "kyle_vboost": kyle_vboost, "kyle_warn": bool(mods.get("kyle_warn", False)), "vpin_val": mods.get("vpin_val"), "kyle_val": mods.get("kyle_val"), "rs_30m": lab_rs30, "council_caution": bool(mods.get("council_caution", False))},
        "medoid_analog": medoid_analog, "high_vol_zones": high_vol_zones, "vol_profile_meta": vol_profile_meta,
        "short_3way_ctx": {"anchor_px": actual_arr[last_act_idx] if (has_actual and last_act_idx >= 0) else 0.0, "cur_vwap": cur_vwap_last, "mom_30m": mom_30m, "bench_live_alpha_adj": bench_live_alpha_adj, "knn_rel_moves": knn_match["knn_rel_moves"], "slot_means": slot_means, "slot_inc_stds": eff_slot_inc_stds, "vboost": vboost, "hvn_wall_px": hvn_wall_px, "ob_sup_px": ob_sup_px, "cum_cvd_now": cum_cvd_latest, "cum_vol_now": cum_vol_latest, "lab_dir_score": lab_strength_dir, "lab_rs30": lab_rs30, "exp_dir": exp_dir},
        "knn_match": {"matched_dates": knn_match["matched_dates"], "mean_dist": knn_match["mean_dist"], "analog_paths": knn_match["analog_paths"]},
        "invalidation_alert": {"triggered": bool(inv_reasons), "severity": "HIGH" if len(inv_reasons) >= 2 else ("MEDIUM" if inv_reasons else "NONE"), "reasons": inv_reasons},
        "weights_evolution": {"active_cluster": cluster_key, "fallback_cluster": fallback_key, "cluster_n": cluster_n, "shrink_alpha": shrink_alpha, "vol_band": vol_cls["vol_band"], "atr_pct": vol_cls["atr_pct"], "active_regime": regime_code, "updates_count": w_evo.get("updates_count", 0), "regime_updates_count": cluster_n, "weights_updated": weights_updated, "open_gap": og_w, "intraday_drift": idr_w, "all_regimes": w_evo.get("clusters", {}).get(cluster_key, w_evo.get("regimes", {})), "last_decomp": w_evo.get("last_decomp", {})},
        "factors": {"mkt_label": mi["label"], "mkt_diff": mi["latest_diff"], "mkt_beta": mi["beta"], "macro_gap_pct": round(mg, 2), "fx_diff": fi["latest_diff"], "fx_beta": fi["beta"], "fx_gap_pct": round(fg, 2), "news_gap_pct": round(ng, 2), "whale_gap_pct": round(wg, 2), "lab_bias_pct": lab_bias_pct, "hvn_wall_px": hvn_wall_px, "ob_sup_px": ob_sup_px, "dow_wick_pct": round(dow_adj + wick_adj, 2), "calib_pct": calib_pct, "calib_n": calib_n, "live_vwap_pct": round(live_vwap_bias * 100.0, 2), "bench_alpha_pct": round(bench_live_alpha_adj * 100.0, 2)},
    }


# =========================================================================
# 7. 実測5軸レーダー・AIメモ生成・LAB共有解決（最新lab_ctx優先修正済）
# =========================================================================
def _compute_real_5axis(info: dict, ovh_pct: float, gov_cnt: int) -> tuple:
    axes, vals, miss = [], [], []
    for k, nm, fn, m_lbl in (("trailingPE", "割安性", lambda v: 100 - (v - 10) * 1.5 if v > 0 else None, "割安性(PER欠損)"), ("revenueGrowth", "成長性", lambda v: 55 + v * 120, "成長性(売上成長率欠損)"), ("returnOnEquity", "収益性", lambda v: 45 + v * 160, "収益性(ROE欠損)")):
        raw = info.get(k)
        sc = fn(raw) if raw is not None else None
        if sc is not None: axes.append({"name": nm, "max": 100}); vals.append(int(np.clip(sc, 15, 98)))
        else: miss.append(m_lbl)
    axes.extend([{"name": "需給軽さ", "max": 100}, {"name": "安全性", "max": 100}])
    vals.extend([int(np.clip(95 - ovh_pct * 0.85, 15, 95)), int(np.clip(95 - gov_cnt * 18, 20, 98))])
    return axes, vals, miss


def _render_valuation_gauges(info: dict, is_jp: bool):
    gs = []
    if (pe := info.get("trailingPE")) is not None and float(pe) > 0:
        v = float(pe); gs.append(("PER (実績)", f"{v:.1f}倍", float(np.clip(v / 60.0 * 100.0, 4.0, 100.0)), "#10b981" if v <= 18 else ("#38bdf8" if v <= 32 else "#f59e0b"), "低PERほど割安目安"))
    if (pb := info.get("priceToBook")) is not None and float(pb) > 0:
        v = float(pb); gs.append(("PBR", f"{v:.2f}倍", float(np.clip(v / 10.0 * 100.0, 4.0, 100.0)), "#10b981" if v <= 1.5 else ("#38bdf8" if v <= 4.0 else "#f59e0b"), "1.0倍近辺が解散価値目安"))
    if (dy := info.get("dividendYield")) is not None and float(dy) > 0:
        v = float(dy) * 100.0 if float(dy) <= 0.25 else float(dy); gs.append(("配当利回り", f"{v:.2f}%", float(np.clip(v / 6.0 * 100.0, 5.0, 100.0)), "#10b981", "インカム下支え水準"))
    if (sf := info.get("shortPercentOfFloat")) is not None and float(sf) > 0:
        v = float(sf) * 100.0 if float(sf) <= 1.0 else float(sf); gs.append(("空売り比率 (Float)", f"{v:.1f}%", float(np.clip(v / 25.0 * 100.0, 5.0, 100.0)), "#ef4444" if v >= 12.0 else ("#f59e0b" if v >= 5.0 else "#38bdf8"), "高水準は踏み上げ燃料候補"))
    if (hi := info.get("heldPercentInstitutions")) is not None and float(hi) > 0:
        v = float(hi) * 100.0 if float(hi) <= 1.0 else float(hi); gs.append(("機関投資家保有率", f"{v:.1f}%", float(np.clip(v, 5.0, 100.0)), "#c084fc", "大口フロー影響度"))
    if not gs: return
    cards = "".join(f'<div class="dd-val-card"><div style="display:flex;justify-content:space-between;align-items:baseline;"><span style="font-size:10.5px;font-weight:700;color:#cbd5e1;">{html.escape(l)}</span><span style="font-family:JetBrains Mono,monospace;font-size:12px;font-weight:800;color:{c};">{html.escape(v)}</span></div><div class="dd-val-track"><div class="dd-val-fill" style="width:{p:.1f}%;background:{c};"></div></div><div style="font-size:9px;color:#94a3b8;margin-top:3px;">{html.escape(s)}</div></div>' for l, v, p, c, s in gs)
    st.markdown(f'<div class="dd-val-grid">{cards}</div>', unsafe_allow_html=True)


@st.cache_data(ttl=900, show_spinner=False)
def _generate_detailed_memo_cached(fc: str, corp_name: str, px_s: str, traj_open: str, traj_close: str, bull_trig: str, bull_tgt: str, bear_trig: str, bear_tgt: str, dip_t: str, peak_t: str, ovh: float, res_s: str, sup_s: str, ml: str, mc: float, mb: float, pos_pct: int, t1: int, gov_cnt: int, whale_sum: str, up: str, lab_note: str, api_key: str, lab_deep_ctx: str = "", trade_style: str = "デイトレード", memo_nonce: int = 0) -> tuple:
    lab_block = f"\n・LAB本体統合データ: {lab_deep_ctx}" if lab_deep_ctx else ""
    lab_extra = f"\n・LAB連携情報: {lab_deep_ctx}" if lab_deep_ctx else ""
    prompt = f"""あなたはヘッジファンドのシニア・エクイティアナリストです。以下の実測データに基づき「超詳細インベストメントメモ」を日本語で作成してください。
・銘柄: {corp_name} ({fc}) / 現在値: {px_s} / 取引スタイル: {trade_style} / アナリスト目標乖離: {up}
・LAB本体判定: {lab_note}{lab_block}
・予測軌道: 想定始値 {traj_open} → 大引け予測 {traj_close}（押し目候補 {dip_t} / ピーク想定 {peak_t}）
・分岐トリガー: 強気突破 {bull_trig}→上値メド {bull_tgt} / 急落警戒 {bear_trig}→下値メド {bear_tgt}
・需給構造: 上値しこり玉 {ovh}% / 大口売り壁 {res_s} / 大口買い支え {sup_s} / 大口異変: {whale_sum}
・マクロ連動: {ml} (相関 {mc}, β={mb}) / 高信頼ニュース強気度 {pos_pct}% (一次報道{t1}件) / ガバナンスリスク検知 {gov_cnt}件

最初に必ず「{trade_style}」に最適化した3行プレイブックを出力し、続けて3セクション構成で具体価格・時間帯・撤退基準まで踏み込んで出力してください：
🎯 If-Then 執行プレイブック（{trade_style}）
・【攻め】IF (具体的価格・VWAP・RVOL条件) → THEN (エントリー＆利確メド)
・【守り】IF (撤退ライン・時間切れ条件) → THEN (即損切り・見送り基準)
・【警戒】IF (想定外ブレイク・マクロ急変条件) → THEN (シナリオ切替ルール)

🟢 Bull Case（強気シナリオ）
🔴 Bear Case（弱気・死角リスク）
⚡ Next Catalyst（注目トリガー）"""

    if api_key:
        for mod in ("gemini-2.5-flash", "gemini-2.0-flash"):
            try:
                body = json.dumps({"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": 1500, "temperature": 0.6}}).encode("utf-8")
                req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent", data=body, headers={"Content-Type": "application/json", "x-goog-api-key": api_key}, method="POST")
                with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=12.0) as r:
                    txt = "".join(p.get("text", "") for p in json.loads(r.read().decode("utf-8"))["candidates"][0]["content"]["parts"] if "text" in p).strip()
                    if txt: return txt, f"🔵 AUTO GLOBAL AI ANALYST ({mod} / {trade_style} / 一次報道{t1}件)"
            except Exception:
                continue

    pb_map = {
        "スキャルピング": (f"・【攻め】IF {bull_trig} 超えまたはVWAP上での9EMA反発＋出来高急増 → THEN 短期回転でエントリーし {bull_tgt} 手前で分割利確", f"・【守り】IF 直近安値割れまたは {bear_trig} 割れ・5分以上ヨコヨコ失速 → THEN 建値〜浅い逆指値で即撤退", f"・【警戒】IF 想定外急騰・{ml} 急変や速報材料発生 → THEN 朝想定を破棄しトレンド追従・ロット半減へ切替"),
        "スイングトレード": (f"・【攻め】IF 押し目帯({dip_t}前後)や支持帯({sup_s})反発・{bull_trig} 上抜け定着 → THEN 数日〜数週ホールドで {bull_tgt} 目標", f"・【守り】IF 日足終値ベースで {bear_trig} 割れまたはしこり壁({res_s})手前での上ヒゲ連発 → THEN ルール損切り・ポジション縮小", f"・【警戒】IF 決算接近・{ml}({mc})のレジーム転換 → THEN 保有比率を調整しイベントリスクを回避"),
        "バイ＆ホールド": (f"・【攻め】IF 調整局面({dip_t}前後・{sup_s}付近)や業績拡大確認 → THEN 段階的な買い増しで中長期成長を取り込む", f"・【守り】IF ガバナンス悪化({gov_cnt}件)やファンダメンタルズ毀損・{bear_trig} 大幅割れ → THEN 保有方針を再点検し一部撤退", f"・【警戒】IF {ml}(β={mb})のトレンド反転や金利・為替急変 → THEN 過熱銘柄の利確リバランスを実施"),
    }
    atk, dfn, alt = pb_map.get(trade_style, (f"・【攻め】IF {bull_trig} 突破または {dip_t} 付近でのVWAP反発 → THEN 当日トレンドに乗せて {bull_tgt} を目指す", f"・【守り】IF {bear_trig} 割れまたは大引け接近時の停滞 → THEN 翌日持ち越しを避け {bear_tgt} 警戒で即損切り・手仕舞い", f"・【警戒】IF 想定外ブレイクや {ml}({mc})急変 → THEN 逆張り停止・ブレイク追従モードへ切替"))
    full = f"🎯 If-Then 執行プレイブック（{trade_style}）\n{atk}\n{dfn}\n{alt}\n\n🟢 Bull Case（強気シナリオ）\n・LAB本体判定: {lab_note}{lab_extra}。現在値 {px_s} に対しアナリスト目標乖離は {up}、高信頼ニュース強気度 {pos_pct}%（一次報道{t1}件）。\n・{bull_trig} を明確に上抜ければ強気突破が発動し、上値メド {bull_tgt} を目指す展開。\n・下値は大口買い支え帯 {sup_s} をサポートとして機能しやすい構造。\n\n🔴 Bear Case（弱気・死角リスク）\n・{ml} との相関係数が {mc}（β={mb}）で、夜間先物や米市場の急変時に連れ安リスクあり。\n・上値しこり玉は {ovh}%、直上の大口売り壁 {res_s} 付近では戻り売りに要注意。\n・{bear_trig} 割れで下値メド {bear_tgt} までの下振れを警戒し早期撤退。ガバナンス報道は {gov_cnt}件検知。\n\n⚡ Next Catalyst（注目トリガー）\n・大口・インサイダー動向: {whale_sum}。\n・勝負時間帯は押し目候補の {dip_t} 前後での反発確認と、ピーク想定の {peak_t} 前後での分割利確。\n・寄付直後に想定始値 {traj_open} を維持できるかが最初の分岐点。"
    return full, f"⚙️ AUTO QUANT MEMO（{trade_style} / 一次報道{t1}件・実測詳細生成）"


def _resolve_shared_lab_entry(fc: str, lab_ctx: dict = None) -> dict:
    """DB→session_state→最新lab_ctxの順でマージ（最新lab_ctxが必ず優先されるよう修正済）"""
    merged = {}
    for src in (_dd_db_get("shared_ticker_intel", {}), st.session_state.get("shared_ticker_intel")):
        if isinstance(src, dict) and isinstance(src.get(fc), dict):
            for k, v in src[fc].items():
                if v is not None: merged[k] = v
    if isinstance(lab_ctx, dict) and lab_ctx and (lab_ctx.get("full_code") == fc or not lab_ctx.get("full_code")):
        merged.update(lab_ctx)
        if any(k in lab_ctx for k in ("side", "expect_pct", "tp", "sl", "exec_grade")):
            merged["lab_full"] = lab_ctx
    return merged


def _format_lab_deep_context(lab_full: dict, lab_council: dict) -> str:
    parts = []
    if isinstance(lab_full, dict) and lab_full:
        side_s = _extract_lab_side(lab_full)
        if side_s or lab_full.get("expect_pct"): parts.append(f"方向={side_s}/期待度={lab_full.get('expect_pct','-')}%/グレード={lab_full.get('exec_grade','-')}")
        if isinstance(m10 := lab_full.get("macro_10y"), dict) and m10: parts.append(f"週足10Y(POC={m10.get('poc_10y_price','-')},CAGR={m10.get('cagr_pct', m10.get('cagr_10y','-'))},Score={m10.get('score', m10.get('long_10y_score','-'))})")
        if isinstance(d2 := lab_full.get("daily_2y"), dict) and d2: parts.append(f"日足2Y(MA={d2.get('ma_align', d2.get('ma_align_label','-'))},HVN={d2.get('hvn_wall_price','-')},ATR14={d2.get('atr14', d2.get('daily_atr14','-'))})")
        if isinstance(wf := (lab_full.get("wf_22d") or lab_full.get("walk_forward_22d") or lab_full.get("forward_test")), dict) and wf: parts.append(f"22日検証(勝率={wf.get('win_rate', wf.get('actual_win_rate','-'))},PF={wf.get('pf', wf.get('profit_factor','-'))},SQN={wf.get('sqn','-')},DD={wf.get('max_dd', wf.get('max_dd_pct','-'))})")
        if isinstance(qi := (lab_full.get("quant_metrics") or lab_full.get("quants")), dict) and qi: parts.append(f"独自クオンツ(WKB={qi.get('wkb','-')},Kyle={qi.get('kyle_lambda','-')},VPIN={qi.get('vpin','-')},CLV={qi.get('clv','-')},RS30={qi.get('rs_30m','-')},OB={lab_full.get('ob_support_px','-')})")
    if isinstance(lab_council, dict) and (vc := (lab_council.get("verdict") or lab_council.get("conclusion") or lab_council.get("summary"))):
        parts.append(f"5名監査官結論={vc}")
    return " | ".join(parts)


def _render_unified_guide():
    st.markdown('<div class="dd-guide-box"><b>🔰 v19.0 クオンツ＆プロ端末ガイド</b><br>1. <b>メイン軌道＆1分足ズーム:</b> 上部ツールバーにHUD数値・ズームリセット(↺)・横拡大ボタンを独立配置し、チャート内の文字被りを完全解消しました。<br>2. <b>LAB × DEEP DIVE 完全統合:</b> LAB経由時は上位足MTF・VWAP・OB支持帯とDDの5分足予測軌道を融合した「統合エントリー帯・+1.0R半分利確・最終TP/SL」をチャート＆コマンドカードへ表示します。<br>3. <b>タブ2（マクロβ・曜日）:</b> 曜日×30分時間帯の期待値ヒートマップ、20日/60日ローリング相関＆ダイナミックβ、決算翌日のPEADドリフトを表示。<br>4. <b>タブ3（財務・大口株主）:</b> 28分割のVA70%/POC出来高プロファイル（短期20日vs中期60日減衰）、BBWボラティリティ・スクイーズ、インサイダー売買プロット、バリュエーション横型ゲージを表示。<br>5. <b>タブ4（リスク・AIメモ）:</b> スタイル別If-Then執行プレイブック内蔵AIメモ、72時間ニュース密度タイムライン、クラスタSGD重み比較＆直近15日検証精度推移を表示。</div>', unsafe_allow_html=True)


# =========================================================================
# 8. メインエントリ関数（YAMASHISHI DEEP DIVE v19.0）
# =========================================================================
def render_deep_dive_page(init_code: str = "NVDA", init_style: str = "デイトレード", gemini_api_key: str = "", lab_ctx: dict = None):
    _inject_dd_css()
    h1, h2, h3 = st.columns([2.6, 0.9, 1.1])
    h1.markdown('<div class="dd-cmd-header"><div style="min-width:0;"><div class="dd-cmd-title">YAMASHISHI DEEP DIVE v19.0</div><div class="dd-cmd-sub">LAB×DD完全統合・衝突ゼロHUDチャート・2段CVD・28分割VA・SGD自己進化</div></div></div>', unsafe_allow_html=True)
    with h2:
        with (st.popover("📖 見方", use_container_width=True) if hasattr(st, "popover") else st.expander("📖 見方")):
            _render_unified_guide()
    if h3.button("⬅️ LAB", key="dd_back_to_lab_btn", use_container_width=True, type="primary"):
        st.session_state["navigation_page"] = "TOP"; st.session_state["scroll_top_trig"] = int(time.time() * 1000); st.rerun()

    STYLES = ["デイトレード", "スキャルピング", "スイングトレード", "バイ＆ホールド"]
    c1, c2, c3 = st.columns([1.8, 1.5, 1.0])
    in_code = c1.text_input("銘柄コード", value=init_code, placeholder="例: NVDA / 6920", label_visibility="collapsed", key="dd_code_in")
    in_style = c2.selectbox("スタイル", STYLES, index=STYLES.index(init_style) if init_style in STYLES else 0, label_visibility="collapsed", key="dd_style_in")
    auto_sync = c3.toggle("自動更新", value=True, key="dd_auto_sync", help="ONで60秒ごとに最新データへ自動同期（拡大精査時はOFF推奨）")

    fc = in_code.strip().upper()
    if not fc: return
    if re.match(r"^[0-9]{3}[0-9A-Z]$", fc): fc = f"{fc}.T"
    is_jp, api_k = fc.endswith(".T"), _get_gemini_key(gemini_api_key)

    shared_entry = _resolve_shared_lab_entry(fc, lab_ctx)
    lab_full = shared_entry.get("lab_full") if isinstance(shared_entry.get("lab_full"), dict) else {}
    lab_council = shared_entry.get("lab_council") if isinstance(shared_entry.get("lab_council"), dict) else {}
    active_lab = lab_full if lab_full else (lab_ctx if (isinstance(lab_ctx, dict) and lab_ctx.get("full_code") == fc) else None)
    lab_deep_ctx, lab_mods = _format_lab_deep_context(lab_full, lab_council), _extract_lab_quant_modifiers(active_lab, lab_council)

    def _body():
        _render_live_clock(sync_interval=60, active=auto_sync)
        with ThreadPoolExecutor(max_workers=3) as ex:
            data, macro_data, df_bench_5m = ex.submit(_load_stock_core, fc).result(), ex.submit(_load_macro_data).result(), ex.submit(_load_benchmark_5m, is_jp).result()

        if macro_data:
            chips = "".join(f'<div class="dd-macro-chip"><span style="color:#64748b;">{macro_data[k]["label"]}{"⚡" if macro_data[k].get("is_rt") else ""}</span><span style="color:{"#10b981" if macro_data[k]["diff_pct"]>=0 else "#ef4444"};font-weight:700;">{macro_data[k]["diff_pct"]:+.2f}%</span></div>' for k in ["SOX", "SP500", "NQ_FUT", "ES_FUT", "NK_FUT", "USDJPY", "US10Y", "OIL", "VIX"] if k in macro_data)
            st.markdown(f'<div class="dd-macro-strip">{chips}</div>', unsafe_allow_html=True)

        df_1d, df_5m, df_1m, info = data["df_1d"], data["df_5m"], data.get("df_1m", pd.DataFrame()), data["info"]
        if df_1d is not None and not df_1d.empty and "Close" in df_1d.columns: df_1d = df_1d.dropna(subset=["Close"])
        if df_1d is None or df_1d.empty:
            st.error(f"❌ 銘柄コード `{fc}` の市場データを取得できませんでした。"); return

        corp_name, short_code = info.get("longName") or info.get("shortName") or fc, fc.replace(".T", "")
        sector, industry = info.get("sector") or "セクター未分類", info.get("industry") or "-"
        market_today_str = _get_market_now(is_jp).strftime("%Y-%m-%d")
        last_1d_str = df_1d.index[-1].strftime("%Y-%m-%d") if hasattr(df_1d.index[-1], "strftime") else str(df_1d.index[-1])[:10]
        curr_px_1d = float(df_1d["Close"].iloc[-1])
        prev_px = float(df_1d["Close"].iloc[-2]) if (last_1d_str == market_today_str and len(df_1d) >= 2) else curr_px_1d

        curr_px_rt = curr_px_1d
        if df_5m is not None and not df_5m.empty:
            t5 = df_5m.copy(); t5["_d"] = _convert_5m_index_to_market_tz(t5, is_jp).strftime("%Y-%m-%d")
            s5 = t5[t5["_d"] == market_today_str]
            if not s5.empty and math.isfinite(float(s5["Close"].iloc[-1])) and float(s5["Close"].iloc[-1]) > 0:
                curr_px_rt = round(float(s5["Close"].iloc[-1]), 2)

        mkt_regime, macro_sens = _detect_market_regime(df_1d), _compute_macro_sens(df_1d["Close"], macro_data)
        dow_stats, next_wd = _compute_dow_edge(df_1d, is_jp)
        with ThreadPoolExecutor(max_workers=2) as exi:
            news_res, (gov_risks, whale_news) = exi.submit(_fetch_global_intel, corp_name, short_code, fc).result(), exi.submit(_fetch_gov_and_whales, corp_name, short_code, is_jp).result()
        whale_anom, vp = _detect_whale_anomaly(data["insider_tx"], whale_news, market_today_str), _compute_vp(df_1d, curr_px_rt, is_jp)
        traj = _build_dual_5m_trajectory(fc, curr_px_rt, prev_px, df_1d, df_5m, macro_sens, macro_data, news_res, whale_anom, dow_stats[next_wd]["avg"], vp, is_jp, mkt_regime, active_lab, df_bench_5m, lab_mods)

        curr_px = float(traj["actual"][traj["last_act_idx"]]) if (traj["has_actual"] and traj["last_act_idx"] >= 0 and traj["actual"][traj["last_act_idx"]] and math.isfinite(float(traj["actual"][traj["last_act_idx"]]))) else curr_px_rt
        round_level, ref_levels, mtf_res = _compute_round_number_level(curr_px, is_jp), _compute_pro_ref_levels(df_1d, df_5m, is_jp, market_today_str), _compute_mtf_alignment(df_1m, df_5m, df_1d, is_jp)
        chg_pct = ((curr_px - prev_px) / max(prev_px, 1e-4)) * 100.0
        chg_col = "#10b981" if chg_pct >= 0 else "#ef4444"
        exp_reg = traj.get("expansion_regime") or {"active": False, "dir": "NONE", "reasons": [], "label": "通常レジーム"}
        exp_active, exp_dir = bool(exp_reg.get("active")), exp_reg.get("dir", "NONE")

        presets, modes = ["📈 今の予測", "🔍 朝の答え合わせ", "🏦 大口・節目"], ["🔴 ライブ修正", "🔒 朝ロック検証", "⚡ 両方重ね"]
        sel_p_now = st.session_state.get("dd_preset_sel", "📈 今の予測")
        cur_cm = modes[2 if sel_p_now == "📈 今の予測" else (1 if sel_p_now == "🔍 朝の答え合わせ" else 0)] if st.session_state.get("dd_last_preset") != sel_p_now else st.session_state.get("dd_chart_mode", "⚡ 両方重ね")
        use_live_basis = bool(traj["has_actual"] and cur_cm in ("🔴 ライブ修正", "⚡ 両方重ね"))

        wi_idx_key, wi_fx_key = f"dd_whatif_idx_{fc}", f"dd_whatif_fx_{fc}"
        f_map = traj["factors"]
        mkt_beta_eff, fx_beta_eff = float(f_map.get("mkt_beta", 0.5)), float(f_map.get("fx_beta", 0.0))
        shock_ext_pct = round(float(st.session_state.get(wi_idx_key, 0.0)) * mkt_beta_eff + (float(st.session_state.get(wi_fx_key, 0.0)) / max(float(macro_data.get("USDJPY", {}).get("last", 150.0) or 150.0), 1.0) * 100.0) * fx_beta_eff, 3)
        shock_mult = 1.0 + (shock_ext_pct / 100.0)
        n_sl_tot, la_idx = len(traj["slots"]), traj["last_act_idx"]

        def _scale_live(arr):
            if not traj["has_actual"] or la_idx < 0: return [round(v * shock_mult, 2) if v is not None else None for v in arr]
            den = max(n_sl_tot - 1 - la_idx, 1)
            return [None if v is None else (round(float(v), 2) if i <= la_idx else round(float(v) * (1.0 + (shock_ext_pct / 100.0) * ((i - la_idx) / den)), 2)) for i, v in enumerate(arr)]

        pfx_b = "live_" if use_live_basis else "locked_"
        sm_eff = shock_mult if (use_live_basis or not traj["has_actual"]) else 1.0
        active_close_px = round(traj[f"{pfx_b}close_px"] * sm_eff, 2)
        active_close_chg = round((active_close_px - traj["anchor_base_close"]) / max(traj["anchor_base_close"], 1e-4) * 100.0, 2)
        active_bull_trig, active_bull_tgt, active_bear_trig, active_bear_tgt = (round(traj[f"{pfx_b}{k}"] * sm_eff, 2) for k in ("bull_trig", "bull_target", "bear_trig", "bear_target"))
        active_dip_time, active_dip_px, active_peak_time, active_peak_px = traj[f"{pfx_b}dip_time"], round(traj[f"{pfx_b}dip_px"] * sm_eff, 2), traj[f"{pfx_b}peak_time"], round(traj[f"{pfx_b}peak_px"] * sm_eff, 2)
        active_open_gap_pct = round(traj["est_open_gap_pct"] + (shock_ext_pct if not traj["has_actual"] else 0.0), 2)
        active_open_px = round(traj["anchor_base_close"] * (1.0 + active_open_gap_pct / 100.0), 2)
        active_rem_drift = traj["rem_drift_pct"] + (shock_ext_pct / 100.0) * 0.65

        disp_locked_p50, disp_locked_p85, disp_locked_p15, disp_locked_bdiff, disp_locked_p32, disp_locked_bdiff_in = (list(traj[k]) for k in ("locked_p50", "locked_p85", "locked_p15", "locked_bdiff", "locked_p32", "locked_bdiff_in"))
        disp_live_p50, disp_live_p85, disp_live_p15, disp_live_bdiff, disp_live_p32, disp_live_bdiff_in = (_scale_live(traj[k]) for k in ("live_p50", "live_p85", "live_p15", "live_bdiff", "live_p32", "live_bdiff_in"))

        s3c = traj["short_3way_ctx"]
        short_3way = _compute_short_horizon_3way(traj["has_actual"], la_idx, n_sl_tot, s3c["anchor_px"], s3c["cur_vwap"], s3c["mom_30m"], traj["rvol"], traj["cvd_div"], traj["gap_open15"], s3c["bench_live_alpha_adj"], s3c["knn_rel_moves"], s3c["slot_means"], s3c["slot_inc_stds"], s3c["vboost"], s3c["hvn_wall_px"], s3c["ob_sup_px"], vp, shock_ext_pct, 6, traj.get("ml_3way_model"), s3c.get("cum_cvd_now", 0.0), s3c.get("cum_vol_now", 0.0), s3c.get("lab_dir_score", 0.0), s3c.get("lab_rs30"), exp_dir)
        cur_vwap_now = traj["vwap"][la_idx] if (traj["has_actual"] and la_idx >= 0) else None
        scen_probs = _compute_bayesian_scenario_probs(traj["has_actual"], curr_px, traj["anchor_base_close"], active_open_gap_pct, active_close_chg, active_bull_trig, active_bull_tgt, active_bear_trig, active_bear_tgt, traj["rem_sigma_pct"], active_rem_drift, traj["rvol"], traj["cvd_div"], traj["gap_open15"], cur_vwap_now, shock_ext_pct, exp_dir)
        fusion = _compute_lab_dd_fusion(active_lab, traj, short_3way, scen_probs, curr_px, is_jp, active_dip_px, active_dip_time, active_peak_px, active_peak_time, active_bull_tgt, active_bear_tgt, active_bull_trig, active_bear_trig, active_close_chg, exp_reg, traj["cvd_div"])

        status_pills, alert_blocks = [], []
        if fusion.get("has_lab"):
            status_pills.append(f'<span class="dd-st-pill" style="border-color:{fusion["sync_col"]};background:rgba(15,23,42,.9);color:{fusion["sync_col"]};">⚡ 統合期待度 {fusion["fusion_score"]:.1f}% ({fusion["side"]})</span>')
        if exp_active:
            is_u = exp_dir == "UP"
            status_pills.append(f'<span class="dd-st-pill" style="border-color:{"#10b981" if is_u else "#ef4444"};background:rgba({"16,185,129" if is_u else "239,68,68"},.20);color:{"#6ee7b7" if is_u else "#fecaca"};">{"🚀 急騰" if is_u else "🔻 急落"}ブレイク稼働中</span>')
            alert_blocks.append(f'<div class="{"dd-quant-box" if is_u else "dd-warn-box"}"><b>{"🚀 急騰" if is_u else "🔻 急落"}ブレイクモード稼働中（朝想定を自動解除・トレンド追従へ切替）</b><br>{"<br>".join(f"・{html.escape(r)}" for r in exp_reg["reasons"])}</div>')
        if isinstance(cat_al := news_res.get("catalyst_alert"), dict) and cat_al.get("active"):
            cc = "#10b981" if cat_al["dir"] == "POS" else "#ef4444"
            status_pills.append(f'<span class="dd-st-pill" style="border-color:{cc};background:rgba(15,23,42,.88);color:{cc};">📰 速報材料: {html.escape(cat_al["kw"])}</span>')
            alert_blocks.append(f'<div class="{"dd-quant-box" if cat_al["dir"]=="POS" else "dd-warn-box"}"><b>📰 60分以内・特大カタリスト速報検知（{cat_al["age_min"]}分前 / キーワード: {html.escape(cat_al["kw"])}）</b><br>{html.escape(cat_al["title"])}（ライブ軌道へ {cat_al["boost_drift_pct"]:+.2f}% 即時反映済）</div>')

        meta_a = traj["meta_audit"]
        meta_hit_s = f" ({meta_a['hit_rate']:.0f}%)" if meta_a["n"] >= 3 else ""
        status_pills.append(f'<span class="dd-st-pill" style="border-color:{meta_a["color"]};background:rgba(15,23,42,.86);color:{meta_a["color"]};">🛡️ モデル信頼度: {html.escape(meta_a["rank"])}{meta_hit_s}</span>')
        alert_blocks.append(f'<div class="dd-quant-box"><b>🛡️ Meta-Labeling モデル信頼度監査（ランク: {html.escape(meta_a["rank"])}）</b><br>{html.escape(meta_a["detail"])}</div>')

        ne_days, earn_badge = data.get("next_earnings_days"), ""
        if ne_days is not None:
            earn_badge = f'<span class="pill-badge" style="border-color:{"#ef4444" if ne_days<=5 else "#f59e0b"};background:rgba(239,68,68,.16);color:#fecaca;">決算あと{ne_days}日</span>'
            if ne_days <= 5:
                status_pills.append(f'<span class="dd-st-pill" style="border-color:#ef4444;background:rgba(239,68,68,.18);color:#fecaca;">⚠️ 決算あと{ne_days}日</span>')
                alert_blocks.append(f'<div class="dd-warn-box"><b>⚠️ 決算イベント接近（あと {ne_days}日）</b><br>決算またぎは通常の5分足軌道モデルが機能しないボラティリティ急変リスクがあります。ポジション縮小を推奨します。</div>')

        cvd_div, g15, inv_al = traj["cvd_div"], traj["gap_open15"], traj.get("invalidation_alert", {})
        if cvd_div["state"] in ("DISTRIBUTION", "ABSORPTION"):
            is_ab = cvd_div["state"] == "ABSORPTION"
            status_pills.append(f'<span class="dd-st-pill" style="border-color:{"#10b981" if is_ab else "#ef4444"};background:rgba({"16,185,129" if is_ab else "239,68,68"},.18);color:{"#6ee7b7" if is_ab else "#fecaca"};">{"🧲 下ヒゲ買い支え乖離" if is_ab else "🚨 上ヒゲ売り圧力乖離"}</span>')
            alert_blocks.append(f'<div class="{"dd-quant-box" if is_ab else "dd-warn-box"}"><b>{"🧲" if is_ab else "🚨"} OHLCV疑似CVD {"強気" if is_ab else "弱気"}ダイバージェンス検知</b><br>{html.escape(cvd_div["detail"])}</div>')
        if g15["status"] in ("GAP_AND_GO_UP", "GAP_AND_FADE_UP", "GAP_AND_GO_DOWN", "GAP_AND_FADE_DOWN"):
            is_gp = g15["status"] in ("GAP_AND_GO_UP", "GAP_AND_FADE_UP")
            status_pills.append(f'<span class="dd-st-pill" style="border-color:{"#10b981" if is_gp else "#ef4444"};background:rgba({"16,185,129" if is_gp else "239,68,68"},.17);color:{"#6ee7b7" if is_gp else "#fecaca"};">⚡ {html.escape(g15["label"])}</span>')
            alert_blocks.append(f'<div class="{"dd-quant-box" if is_gp else "dd-warn-box"}"><b>⚡ 寄り後15分判定: {html.escape(g15["label"])}</b><br>{html.escape(g15["detail"])}</div>')
        if inv_al.get("triggered"):
            status_pills.append(f'<span class="dd-st-pill" style="border-color:#ef4444;background:rgba(239,68,68,.22);color:#fecaca;">🚨 破棄アラート({inv_al["severity"]})</span>')
            alert_blocks.append(f'<div class="dd-warn-box"><b>🚨 予測軌道・破棄アラート発火（重要度: {inv_al["severity"]}）</b><br>{"<br>".join(f"・{html.escape(r)}" for r in inv_al["reasons"])}</div>')

        lab_note = "単体検索モード（LAB未経由）"
        if active_lab:
            ls = _extract_lab_side(active_lab)
            ltp, lsl, tm = float(active_lab.get("tp", active_lab.get("raw_tp", 0.0)) or 0.0), float(active_lab.get("sl", active_lab.get("raw_sl", 0.0)) or 0.0), traj["lab_mods"]["lab_trust_mult"]
            aligned = (ls == "LONG" and active_close_chg >= 0) or (ls == "SHORT" and active_close_chg < 0)
            lab_note = f"LAB判定={ls} (期待度{active_lab.get('expect_pct',0)}% / 信頼度係数×{tm:.2f} / TP:{_fmt_cur(ltp, is_jp)} / SL:{_fmt_cur(lsl, is_jp)})"
            if aligned:
                status_pills.append(f'<span class="dd-st-pill" style="border-color:#10b981;background:rgba(16,185,129,.16);color:#6ee7b7;">✅ LAB一致({ls} ×{tm:.2f})</span>')
                alert_blocks.append(f'<div class="dd-quant-box"><b>✅ LAB × DEEP DIVE 方向性一致（{ls} 同期 / 信頼度係数 ×{tm:.2f}）</b><br>LAB上位足判定（期待度 {active_lab.get("expect_pct",0)}% / {html.escape(str(active_lab.get("exec_grade","")).split("（")[0])}）と5分足予測軌道（{active_close_chg:+.2f}%）が一致。TP: <b>{_fmt_cur(ltp, is_jp)}</b> / SL: <b>{_fmt_cur(lsl, is_jp)}</b></div>')
            else:
                status_pills.append(f'<span class="dd-st-pill" style="border-color:#f59e0b;background:rgba(245,158,11,.16);color:#fef3c7;">⚠️ LAB乖離({ls})</span>')
                alert_blocks.append(f'<div class="dd-sync-warn"><b>⚠️ LAB × DEEP DIVE 方向性に乖離あり（慎重待機推奨）</b><br>LAB上位足判定は <b>{ls}</b>（期待度 {active_lab.get("expect_pct",0)}%）ですが、5分足短期軌道は <b>{active_close_chg:+.2f}%</b> と逆方向を示唆。</div>')

        if whale_anom["detected"]:
            wc = "#10b981" if whale_anom["dir"] == "BULL" else "#ef4444"
            status_pills.append(f'<span class="dd-st-pill" style="border-color:{wc};background:rgba(15,23,42,.85);color:{wc};">🐋 大口{whale_anom["dir"]}({whale_anom["adj_pct"]:+.2f}%)</span>')
            alert_blocks.append(f'<div class="{"dd-quant-box" if whale_anom["dir"]=="BULL" else "dd-warn-box"}"><b>🚨 大口・インサイダー異変検知（予測軌道へ {whale_anom["adj_pct"]:+.2f}% 自動反映済）</b><br>{html.escape(whale_anom["summary"])}</div>')

        if status_pills: st.markdown(f'<div class="dd-status-strip">{"".join(status_pills)}</div>', unsafe_allow_html=True)
        if alert_blocks or lab_full or lab_council:
            with st.expander(f"🔔 アラート・信頼度監査・LAB 3階層MTF詳細 ({len(alert_blocks) + (1 if (lab_full or lab_council) else 0)}件)", expanded=False):
                for blk in alert_blocks: st.markdown(blk, unsafe_allow_html=True)
                if lab_full or lab_council:
                    m10 = lab_full.get("macro_10y") if isinstance(lab_full.get("macro_10y"), dict) else {}
                    d2 = lab_full.get("daily_2y") if isinstance(lab_full.get("daily_2y"), dict) else {}
                    wf22 = next((lab_full[k] for k in ("wf_22d", "walk_forward_22d", "forward_test") if isinstance(lab_full.get(k), dict)), {})
                    qi = next((lab_full[k] for k in ("quant_metrics", "quants") if isinstance(lab_full.get(k), dict)), {})
                    cv = (lab_council.get("verdict") or lab_council.get("conclusion") or lab_council.get("summary") or "-") if isinstance(lab_council, dict) else "-"
                    st.markdown(f'<div class="dd-dark-box" style="margin-bottom:0;"><div><b>■ 週足10Y大局:</b> 10年POC={html.escape(str(m10.get("poc_10y_price","-")))} / CAGR={html.escape(str(m10.get("cagr_pct", m10.get("cagr_10y","-"))))} / スコア={html.escape(str(m10.get("score", m10.get("long_10y_score","-"))))}</div><div><b>■ 日足2Y中期:</b> MA並び={html.escape(str(d2.get("ma_align", d2.get("ma_align_label","-"))))} / HVN/LVN={html.escape(str(d2.get("hvn_wall_price","-")))} / 日足ATR14={html.escape(str(d2.get("atr14", d2.get("daily_atr14","-"))))}</div><div><b>■ 22営業日リークフリー検証:</b> 勝率={html.escape(str(wf22.get("win_rate", wf22.get("actual_win_rate","-"))))} / PF={html.escape(str(wf22.get("pf", wf22.get("profit_factor","-"))))} / SQN={html.escape(str(wf22.get("sqn","-")))} / 平均R={html.escape(str(wf22.get("avg_r","-")))} / 最大DD={html.escape(str(wf22.get("max_dd", wf22.get("max_dd_pct","-"))))} / 累計損益={html.escape(str(wf22.get("total_pnl", wf22.get("total_profit_yen","-"))))}</div><div><b>■ 独自クオンツ指標:</b> WKB={html.escape(str(qi.get("wkb", lab_full.get("q_tunnel","-"))))} / Kyle-λ={html.escape(str(qi.get("kyle_lambda", lab_full.get("kyle_lambda","-"))))} / VPIN={html.escape(str(qi.get("vpin", lab_full.get("vpin","-"))))} / CLV={html.escape(str(qi.get("clv", lab_full.get("ofi_z","-"))))} / 30分RS={html.escape(str(qi.get("rs_30m", lab_full.get("intraday_rs_30m","-"))))} / 機関OB支持帯={html.escape(str(lab_full.get("ob_support_px","-")))}</div><div><b>■ 5名監査官の最新結論:</b> {html.escape(str(cv))}</div></div>', unsafe_allow_html=True)

        comp_score = int(np.clip(round(50 + news_res["shock_score"] * 45 - len(gov_risks) * 9 + whale_anom["adj_pct"] * 12), 5, 98))
        meter_lbl = "EXTREME GREED // 極度の強気" if comp_score >= 75 else ("BULLISH // 強気優勢" if comp_score >= 58 else ("NEUTRAL // 均衡・様子見" if comp_score >= 42 else ("FEAR // 警戒・弱気" if comp_score >= 25 else "EXTREME FEAR // リスク警戒")))
        hi_52, lo_52 = float(df_1d["High"].max()), float(df_1d["Low"].min())
        pos_52 = float(np.clip((curr_px - lo_52) / max(hi_52 - lo_52, 1e-4) * 100.0, 2.0, 98.0))
        aura_col, aura_glow = ("#10b981", "rgba(16,185,129,.18)") if active_close_chg >= 0 else ("#ef4444", "rgba(239,68,68,.18)")
        tmean = info.get("targetMeanPrice")
        upside_str = f"{((tmean - curr_px)/curr_px*100):+.1f}%" if (tmean and curr_px > 0) else "-"
        r_stat, r_col = (f"⚠️ {len(gov_risks)}件", "#f87171") if gov_risks else ("🟢 クリーン", "#10b981")
        top_close_lbl = "大引け予測(ライブ)" if use_live_basis else "大引け予測(ロック)"

        st.markdown(f"""<div class="dd-hero-card" style="border-left-color:{aura_col};box-shadow:0 8px 24px {aura_glow};"><div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;flex-wrap:wrap;"><div style="min-width:0;flex:1;"><div><span class="pill-badge">{html.escape(fc)}</span><span class="pill-badge" style="border-color:rgba(168,85,247,.45);background:rgba(168,85,247,.16);color:#e9d5ff;">{html.escape(in_style)}</span><span class="pill-badge" style="border-color:{mkt_regime['color']};background:rgba(15,23,42,.8);color:{mkt_regime['color']};">{mkt_regime['label']}・{traj['weights_evolution']['active_cluster']}</span>{earn_badge}</div><div style="font-size:16.5px;font-weight:800;color:#f8fafc;margin-top:4px;word-break:break-word;">{html.escape(corp_name)}</div><div style="font-size:10.5px;color:#64748b;margin-top:1px;">{html.escape(sector)} / {html.escape(industry)}</div></div><div style="text-align:right;flex-shrink:0;"><div style="font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;font-size:19px;font-weight:800;color:#fff;">{_fmt_cur(curr_px, is_jp)}</div><div style="font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;font-size:11.5px;font-weight:700;color:{chg_col};margin-bottom:2px;">{chg_pct:+.2f}%</div>{_build_spark_svg(df_1d["Close"].tail(20).values)}</div></div><div style="margin-top:6px;"><div style="display:flex;justify-content:space-between;font-size:9.3px;color:#64748b;font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;"><span>52W安 {_fmt_cur(lo_52, is_jp)}</span><span style="color:#7dd3fc;">52W位置 {pos_52:.0f}%</span><span>52W高 {_fmt_cur(hi_52, is_jp)}</span></div><div class="dd-range-track"><div class="dd-range-dot" style="left:{pos_52:.1f}%;"></div></div></div><div class="dd-winrate-bar"><div><div class="dd-metric-lbl">{top_close_lbl}</div><div class="dd-metric-val" style="color:{aura_col};">{_fmt_cur(active_close_px, is_jp)} ({active_close_chg:+.2f}%)</div></div><div><div class="dd-metric-lbl">アナリスト乖離</div><div class="dd-metric-val" style="color:#fde047;">{upside_str}</div></div><div><div class="dd-metric-lbl">上値しこり玉</div><div class="dd-metric-val" style="color:#c084fc;">{vp['overhead_pct']}%</div></div><div><div class="dd-metric-lbl">ガバナンス</div><div class="dd-metric-val" style="color:{r_col};">{r_stat}</div></div></div></div>""", unsafe_allow_html=True)

        t1, t2, t3, t4 = st.tabs(["翌営業日 1日軌道", "マクロβ・曜日", "財務・大口株主", "リスク・AIメモ"])

        with t1:
            if fusion.get("has_lab"):
                st.markdown(f'<div class="dd-fusion-cmd-card"><div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;"><span style="font-size:11.5px;font-weight:900;color:#7dd3fc;">⚡ LAB × DEEP DIVE 統合執行コマンド（{html.escape(fusion["exec_grade"])}）</span><span style="font-family:JetBrains Mono,monospace;font-size:11px;font-weight:800;color:{fusion["sync_col"]};">統合期待度 {fusion["fusion_score"]:.1f}% ｜ {html.escape(fusion["sync_state"])}</span></div><div style="font-size:10.3px;color:#cbd5e1;margin-top:3px;">推奨売買: <b style="color:{"#6ee7b7" if fusion["is_long"] else "#fda4af"};">{"📈 買い(LONG)" if fusion["is_long"] else "📉 空売り(SHORT)"} {fusion["shares"]:,}株</b> ｜ 戦術: <b>{html.escape(fusion["entry_mode"])}</b> ｜ 狙い時: <b style="color:#fde047;">{html.escape(fusion["target_time_hint"])}</b></div><div class="dd-fusion-grid"><div class="dd-fusion-cell"><div class="dd-metric-lbl">① 統合エントリー目安</div><div style="font-family:JetBrains Mono,monospace;font-size:12px;font-weight:800;color:#38bdf8;">{_fmt_cur(fusion["fusion_entry_px"], is_jp)}</div></div><div class="dd-fusion-cell"><div class="dd-metric-lbl">② +1.0R 半分利確</div><div style="font-family:JetBrains Mono,monospace;font-size:12px;font-weight:800;color:#fde047;">{_fmt_cur(fusion["fusion_half_r_px"], is_jp)}</div></div><div class="dd-fusion-cell"><div class="dd-metric-lbl">③ 統合最終TP目標</div><div style="font-family:JetBrains Mono,monospace;font-size:12px;font-weight:800;color:#10b981;">{_fmt_cur(fusion["fusion_tp_px"], is_jp)}</div></div><div class="dd-fusion-cell"><div class="dd-metric-lbl">④ 厳格逆指値SL</div><div style="font-family:JetBrains Mono,monospace;font-size:12px;font-weight:800;color:#ef4444;">{_fmt_cur(fusion["fusion_sl_px"], is_jp)}</div></div></div></div>', unsafe_allow_html=True)

            if isinstance(brk := news_res.get("breaking_news"), dict) and brk.get("title"):
                st.markdown(f'<div class="{"dd-breaking-ticker bull" if brk.get("sent")=="POS" else "dd-breaking-ticker"}"><span style="font-weight:800;flex-shrink:0;">{"🔥 速報(買い)" if brk.get("sent")=="POS" else ("⚠️ 速報(売り)" if brk.get("sent")=="NEG" else "⚡ 速報")} [{brk.get("age_min",1)}分前]</span><a href="{html.escape(brk.get("link") or "#")}" target="_blank" style="color:inherit;text-decoration:none;overflow:hidden;text-overflow:ellipsis;">{html.escape(brk["title"])} ({html.escape(brk.get("source") or "速報")})</a></div>', unsafe_allow_html=True)

            _render_mtf_and_ladder(mtf_res, curr_px, is_jp, ref_levels, traj, vp, round_level, active_lab)

            rv = traj["rvol"]
            rv_t, rv_c = (f"{rv:.2f}x (機関)", "#10b981") if (rv and rv >= 1.8) else ((f"{rv:.2f}x (閑散)", "#f59e0b") if (rv and rv < 0.75) else ((f"{rv:.2f}x (通常)", "#38bdf8") if rv else ("場前待機", "#94a3b8")))
            gf = traj["gap_fill"]
            if gf["prob"] is not None:
                ngf = int(gf.get("n_samples", 0))
                am_s = f"{gf['avg_min']}分/" if gf["avg_min"] else ""
                gf_t = f"{'参考 ' if ngf<5 else ''}{int(gf['prob'])}% ({am_s}N={ngf})"
                gf_c = "#94a3b8" if ngf < 5 else ("#10b981" if gf["prob"] >= 60 else ("#f59e0b" if gf["prob"] >= 35 else "#38bdf8"))
            else:
                gf_t, gf_c = "データ不足", "#94a3b8"
            nsp = len(traj["vol_spikes"])
            rib = "".join(f'<div class="dd-inst-pill-card"><div class="dd-metric-lbl">{l}</div><div style="font-family:JetBrains Mono,monospace;font-variant-numeric:tabular-nums;font-size:11px;font-weight:800;color:{c};margin-top:1px;">{v}</div></div>' for l, v, c in (("RVOL 相対出来高", rv_t, rv_c), ("窓埋め率 (1M標本)", gf_t, gf_c), ("心理的キリ番節目", _fmt_cur(round_level, is_jp), "#fde047"), ("大口約定スパイク", f"{nsp}回検知 ◆" if nsp else "なし", "#c084fc" if nsp else "#94a3b8"), ("OHLCV疑似CVD", html.escape(cvd_div["label"]), cvd_div["color"]), ("寄り15分 Gap判定", html.escape(g15["label"]), g15["color"])))
            st.markdown(f'<div class="dd-inst-ribbon">{rib}</div>', unsafe_allow_html=True)

            z1_pay = _build_1m_zoom_payload(df_1m, is_jp, market_today_str, exp_dir, f_map.get("hvn_wall_px", 0.0), f_map.get("ob_sup_px", 0.0), vp)
            if st.session_state.get("dd_last_style_tf") != in_style:
                st.session_state["dd_last_style_tf"] = in_style
                st.session_state["dd_tf_mode"] = "1分足(直近90分ズーム)" if (in_style == "スキャルピング" and z1_pay.get("valid")) else "5分足(1日全体)"

            is_short = in_style in ("デイトレード", "スキャルピング")
            line_opts = ["場中30分・3分岐点線（スコア比%）", "類似実測波形（Top-1）", "高ボラ狩り場帯", "予測レンジ帯（ファン）", "類似日スパゲッティ軌道", "転換時間帯ガイド", "押目・利確ゾーン", "VWAP", "VWAP±σ", "前日/当日高安（PDH/PDL/HOD/LOD）", "心理的キリ番節目", "寄り30分高安（ORB）", "大口約定（◆）", "出来高"] + (["LAB×DD 統合エントリー帯/+1.0R", "LAB TP/SL"] if active_lab else [])
            p_col, tf_col, cfg_col = st.columns([2.2, 1.4, 0.9])
            sel_preset = (p_col.pills("表示プリセット", presets, default="📈 今の予測", selection_mode="single", label_visibility="collapsed", key="dd_preset_sel") or "📈 今の予測") if hasattr(st, "pills") else p_col.radio("表示プリセット", presets, index=0, horizontal=True, label_visibility="collapsed", key="dd_preset_sel")
            sel_tf = tf_col.selectbox("表示足", ["5分足(1日全体)", "1分足(直近90分ズーム)"], label_visibility="collapsed", key="dd_tf_mode")

            if sel_preset == "📈 今の予測":
                pmi, prl = 2, (["場中30分・3分岐点線（スコア比%）", "類似実測波形（Top-1）", "高ボラ狩り場帯"] if is_short else ["場中30分・3分岐点線（スコア比%）"]) + ["予測レンジ帯（ファン）", "類似日スパゲッティ軌道", "押目・利確ゾーン", "VWAP", "心理的キリ番節目", "大口約定（◆）", "出来高"] + (["LAB×DD 統合エントリー帯/+1.0R", "LAB TP/SL"] if active_lab else [])
            elif sel_preset == "🔍 朝の答え合わせ":
                pmi, prl = 1, ["場中30分・3分岐点線（スコア比%）", "予測レンジ帯（ファン）", "寄り30分高安（ORB）", "出来高"]
            else:
                pmi, prl = 0, ["場中30分・3分岐点線（スコア比%）", "高ボラ狩り場帯", "VWAP", "VWAP±σ", "前日/当日高安（PDH/PDL/HOD/LOD）", "転換時間帯ガイド", "心理的キリ番節目", "大口約定（◆）", "押目・利確ゾーン", "出来高"] + (["LAB×DD 統合エントリー帯/+1.0R", "LAB TP/SL"] if active_lab else [])

            spsig = f"{sel_preset}::{is_short}"
            if st.session_state.get("dd_last_preset") != sel_preset or st.session_state.get("dd_last_style_sig") != spsig:
                st.session_state.update({"dd_last_preset": sel_preset, "dd_last_style_sig": spsig, "dd_chart_mode": modes[pmi], "dd_opt_lines": [x for x in prl if x in line_opts]})

            with cfg_col:
                with (st.popover("⚙️ 設定", use_container_width=True) if hasattr(st, "popover") else st.expander("⚙️ 設定")):
                    chart_mode = st.radio("軌道モード", modes, index=pmi, key="dd_chart_mode")
                    opt_lines = st.multiselect("表示レイヤー", line_opts, default=[x for x in prl if x in line_opts], key="dd_opt_lines")

            use_1m_zoom = bool(sel_tf == "1分足(直近90分ズーム)" and z1_pay.get("valid"))
            if sel_tf == "1分足(直近90分ズーム)" and not z1_pay.get("valid"):
                st.caption("ℹ️ 1分足データが未取得・場外のため、自動で5分足(1日全体)へフォールバック表示しています。")

            _hb = lambda t, c, p="insideStartTop": {"formatter": t, "color": c, "fontSize": 8.2, "fontWeight": "bold", "position": p, "backgroundColor": "rgba(7,11,20,.88)", "padding": [1, 4], "borderRadius": 3, "distance": 4}
            _vb = lambda t, c: {"formatter": t, "color": c, "fontSize": 8, "rotate": 0, "position": "insideStartBottom", "backgroundColor": "rgba(7,11,20,.86)", "padding": [1, 3], "borderRadius": 3, "distance": 4}
            _ref_ml = lambda rd, cp: [{"yAxis": round(float(px), 2), "lineStyle": {"color": col, "type": "dashed", "width": 1.0, "opacity": 0.72}, "label": _hb(f"{lbl} {_fmt_cur(px, is_jp)}", col, pos)} for lbl, k, col, pos in (("HOD", "hod", "#f43f5e", "insideStartTop"), ("PDH", "pdh", "#fb7185", "insideStartTop"), ("PDC", "pdc", "#94a3b8", "insideStartBottom"), ("PDL", "pdl", "#34d399", "insideStartBottom"), ("LOD", "lod", "#10b981", "insideStartBottom")) if "前日/当日高安（PDH/PDL/HOD/LOD）" in opt_lines and cp > 0 and (px := rd.get(k)) and px > 0 and abs(float(px) - cp) / cp <= 0.06]

            if use_1m_zoom:
                z1 = z1_pay; ml1 = _ref_ml(ref_levels, curr_px)
                if "心理的キリ番節目" in opt_lines and round_level > 0 and curr_px > 0 and abs(round_level - curr_px) / curr_px <= 0.05:
                    ml1.append({"yAxis": round_level, "lineStyle": {"color": "rgba(250,204,21,.52)", "type": "dotted", "width": 1.1}, "label": _hb(f"節目 {_fmt_cur(round_level, is_jp)}", "#fde047")})
                if fusion.get("has_lab") and "LAB×DD 統合エントリー帯/+1.0R" in opt_lines and curr_px > 0 and abs(fusion["fusion_half_r_px"] - curr_px) / curr_px <= 0.08:
                    ml1.append({"yAxis": fusion["fusion_half_r_px"], "lineStyle": {"color": "#facc15", "type": "dashed", "width": 1.2}, "label": _hb(f"+1.0R半分 {_fmt_cur(fusion['fusion_half_r_px'], is_jp)}", "#fde047")})
                if active_lab and "LAB TP/SL" in opt_lines and curr_px > 0:
                    for lbl, ks, col, pos in (("TP", ("tp", "raw_tp"), "#10b981", "insideStartTop"), ("SL", ("sl", "raw_sl"), "#ef4444", "insideStartBottom")):
                        v = float(active_lab.get(ks[0], active_lab.get(ks[1], 0.0)) or 0.0)
                        if v > 0 and abs(v - curr_px) / curr_px <= 0.08: ml1.append({"yAxis": round(v, 2), "lineStyle": {"color": col, "type": "dashed", "width": 1.3}, "label": _hb(f"{lbl} {_fmt_cur(v, is_jp)}", "#6ee7b7" if lbl == "TP" else "#fca5a5", pos)})
                ml1_c = _declutter_marklines(ml1, curr_px, 0.45, False); rp1 = 56 if is_jp else 50
                s_1m = [
                    {"name": "1分足", "type": "candlestick", "xAxisIndex": 0, "yAxisIndex": 0, "data": z1["ohlc"], "itemStyle": {"color": "rgba(16,185,129,.78)", "color0": "rgba(239,68,68,.78)", "borderColor": "#10b981", "borderColor0": "#ef4444", "borderWidth": 1}, "z": 14},
                    {"name": "9EMA", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": z1["ema9"], "itemStyle": {"color": "#38bdf8"}, "lineStyle": {"color": "#38bdf8", "width": 1.4}, "smooth": 0.12, "showSymbol": False, "z": 7},
                    {"name": "20EMA", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": z1["ema20"], "itemStyle": {"color": "#c084fc"}, "lineStyle": {"color": "#c084fc", "width": 1.4}, "smooth": 0.12, "showSymbol": False, "z": 6},
                    {"name": "VWAP", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": z1["vwap"], "itemStyle": {"color": "#fbbf24"}, "lineStyle": {"color": "#fbbf24", "width": 1.3, "type": "dotted"}, "showSymbol": False, "markLine": {"symbol": ["none", "none"], "data": ml1_c} if ml1_c else {}, "z": 6},
                    {"name": "上昇分岐", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": z1["up_path"], "itemStyle": {"color": "#10b981"}, "lineStyle": {"color": "#10b981", "width": 1.8, "type": "dashed"}, "smooth": 0.15, "showSymbol": False, "endLabel": {"show": True, "distance": 4, "formatter": f"▲ {z1['p_up']}%", "color": "#6ee7b7", "fontSize": 9.5, "fontWeight": "bold", "fontFamily": "JetBrains Mono"}, "z": 10},
                    {"name": "横ばい分岐", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": z1["flat_path"], "itemStyle": {"color": "#94a3b8"}, "lineStyle": {"color": "#94a3b8", "width": 1.6, "type": "dotted"}, "smooth": 0.15, "showSymbol": False, "endLabel": {"show": True, "distance": 4, "formatter": f"▶ {z1['p_flat']}%", "color": "#cbd5e1", "fontSize": 9.5, "fontWeight": "bold", "fontFamily": "JetBrains Mono"}, "z": 9},
                    {"name": "下落分岐", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": z1["down_path"], "itemStyle": {"color": "#ef4444"}, "lineStyle": {"color": "#ef4444", "width": 1.8, "type": "dashed"}, "smooth": 0.15, "showSymbol": False, "endLabel": {"show": True, "distance": 4, "formatter": f"▼ {z1['p_down']}%", "color": "#fca5a5", "fontSize": 9.5, "fontWeight": "bold", "fontFamily": "JetBrains Mono"}, "z": 10},
                    {"name": "1分出来高", "type": "bar", "xAxisIndex": 1, "yAxisIndex": 1, "data": z1["vol_bars"], "barMaxWidth": 5, "markLine": {"symbol": ["none", "none"], "silent": True, "data": [{"yAxis": z1["avg_vol_1m"], "lineStyle": {"color": "rgba(148,163,184,.35)", "type": "dashed", "width": 1}, "label": {"show": False}}]} if z1["avg_vol_1m"] > 0 else {}},
                    {"name": "疑似CVD", "type": "line", "xAxisIndex": 1, "yAxisIndex": 2, "data": z1["cvd"], "itemStyle": {"color": "#22d3ee"}, "lineStyle": {"color": "#22d3ee", "width": 1.6}, "areaStyle": {"color": "rgba(34,211,238,.10)"}, "showSymbol": False},
                ]
                st.caption(f"表示中: 1分足マイクロ・ズーム（{z1['target_date']} 直近90本 ＋ 9/20EMA ＋ VWAP ＋ 10分3分岐 ＋ 下段CVD）｜ 拡大精査時は「自動更新」OFF推奨")
                _render_echarts({"backgroundColor": "#070b14", "legend": {"type": "scroll", "data": ["1分足", "9EMA", "20EMA", "VWAP", "疑似CVD"], "textStyle": {"color": "#cbd5e1", "fontSize": 9.5}, "top": 2, "left": 6, "right": 8, "itemWidth": 12, "itemHeight": 8}, "axisPointer": {"link": [{"xAxisIndex": "all"}]}, "grid": [{"top": 42, "height": "57%", "left": 6, "right": rp1, "containLabel": False}, {"top": "74%", "height": "18%", "left": 6, "right": rp1, "containLabel": False}], "dataZoom": [{"type": "inside", "xAxisIndex": [0, 1], "filterMode": "none"}], "xAxis": [{"type": "category", "gridIndex": 0, "boundaryGap": True, "data": z1["times"], "axisLine": {"lineStyle": {"color": "rgba(148,163,184,.18)"}}, "axisLabel": {"show": False}}, {"type": "category", "gridIndex": 1, "boundaryGap": True, "data": z1["times"], "axisLine": {"lineStyle": {"color": "rgba(148,163,184,.18)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9, "interval": "auto", "hideOverlap": True}}], "yAxis": [{"type": "value", "gridIndex": 0, "position": "right", "scale": True, "splitLine": {"lineStyle": {"color": "rgba(255,255,255,.04)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9}}, {"type": "value", "gridIndex": 1, "show": False, "axisPointer": {"show": False}}, {"type": "value", "gridIndex": 1, "position": "right", "scale": True, "splitLine": {"show": False}, "axisLabel": {"color": "#22d3ee", "fontSize": 8}}], "series": s_1m}, 415, True, is_jp, True, True, f"dd_1m_{fc}")
                st.markdown(f'<div class="dd-3way-strip"><span style="color:#7dd3fc;font-weight:800;">⚡ 1分足・直近10分3分岐:</span><span><span style="color:#6ee7b7;font-weight:800;">▲上昇 {z1["p_up"]}%</span> / <span style="color:#cbd5e1;font-weight:800;">▶横ばい {z1["p_flat"]}%</span> / <span style="color:#fca5a5;font-weight:800;">▼下落 {z1["p_down"]}%</span></span></div>', unsafe_allow_html=True)
                _render_chart_legend_panel(traj, chart_mode, opt_lines, short_3way, exp_reg, active_dip_time, active_peak_time, cur_vwap_now, curr_px, is_jp, active_lab, True, z1)
            else:
                med_info = traj.get("medoid_analog")
                med_cap = f" ｜ 最類似実測: {med_info['date']} (Gap {med_info['gap_pct']:+.2f}% / ATR補正×{med_info.get('amp_scale',1.0):.2f})" if ("類似実測波形（Top-1）" in opt_lines and isinstance(med_info, dict) and med_info.get("date")) else ""
                ml_data = _ref_ml(ref_levels, curr_px)
                if traj["lunch_idx"] is not None: ml_data.append({"xAxis": traj["slots"][traj["lunch_idx"]], "lineStyle": {"color": "rgba(148,163,184,.32)", "type": "dashed", "width": 1.0}, "label": _vb("昼休", "#94a3b8")})
                if "転換時間帯ガイド" in opt_lines:
                    for mts, mtl in ([("09:15", "一巡"), ("14:30", "機関"), ("15:25", "引け")] if is_jp else [("10:00", "指標"), ("11:30", "欧州引"), ("15:50", "MOC")]):
                        if mts in traj["slots"]: ml_data.append({"xAxis": mts, "lineStyle": {"color": "rgba(125,211,252,.22)", "type": "dotted", "width": 1.0}, "label": _vb(mtl, "rgba(148,163,184,.85)")})
                if g15.get("show_gap_target") and prev_px > 0: ml_data.append({"yAxis": round(prev_px, 2), "lineStyle": {"color": "#f97316", "type": "dashed", "width": 1.4}, "label": _hb(f"窓埋目標 {_fmt_cur(prev_px, is_jp)}", "#fdba74")})
                if "心理的キリ番節目" in opt_lines and round_level > 0: ml_data.append({"yAxis": round_level, "lineStyle": {"color": "rgba(250,204,21,.52)", "type": "dotted", "width": 1.1}, "label": _hb(f"節目 {_fmt_cur(round_level, is_jp)}", "#fde047")})
                if "寄り30分高安（ORB）" in opt_lines and traj["orb_high"] and traj["orb_low"]:
                    ml_data.extend([{"yAxis": traj["orb_high"], "lineStyle": {"color": "rgba(56,189,248,.42)", "type": "dashed", "width": 1.0}, "label": _hb("ORB高", "#7dd3fc")}, {"yAxis": traj["orb_low"], "lineStyle": {"color": "rgba(244,63,94,.42)", "type": "dashed", "width": 1.0}, "label": _hb("ORB安", "#fda4af", "insideStartBottom")}])
                if exp_active and traj["orb_high"] and traj["orb_low"] and (orng := max(float(traj["orb_high"]) - float(traj["orb_low"]), 0.0)) > 0 and curr_px > 0:
                    oext = round(float(traj["orb_low"]) + orng * 1.618, 2) if exp_dir == "UP" else round(max(float(traj["orb_high"]) - orng * 1.618, curr_px * 0.5), 2)
                    if abs(oext - curr_px) / curr_px <= 0.14: ml_data.append({"yAxis": oext, "lineStyle": {"color": "rgba(34,211,238,.62)" if exp_dir == "UP" else "rgba(251,113,133,.62)", "type": "dotted", "width": 1.2}, "label": _hb(f"ORB拡張1.618 {_fmt_cur(oext, is_jp)}", "#67e8f9" if exp_dir == "UP" else "#fda4af", "insideStartTop" if exp_dir == "UP" else "insideStartBottom")})
                if fusion.get("has_lab") and "LAB×DD 統合エントリー帯/+1.0R" in opt_lines and curr_px > 0 and abs(fusion["fusion_half_r_px"] - curr_px) / curr_px <= 0.12:
                    ml_data.append({"yAxis": fusion["fusion_half_r_px"], "lineStyle": {"color": "#facc15", "type": "dashed", "width": 1.2}, "label": _hb(f"+1.0R半分 {_fmt_cur(fusion['fusion_half_r_px'], is_jp)}", "#fde047")})

                lab_tpsl_hidden = False
                if active_lab and "LAB TP/SL" in opt_lines and curr_px > 0:
                    for lbl, ks, col, pos in (("TP", ("tp", "raw_tp"), "#10b981", "insideStartTop"), ("SL", ("sl", "raw_sl"), "#ef4444", "insideStartBottom")):
                        v = float(active_lab.get(ks[0], active_lab.get(ks[1], 0.0)) or 0.0)
                        if v > 0:
                            if abs(v - curr_px) / curr_px <= 0.12: ml_data.append({"yAxis": round(v, 2), "lineStyle": {"color": col, "type": "dashed", "width": 1.3}, "label": _hb(f"{lbl} {_fmt_cur(v, is_jp)}", "#6ee7b7" if lbl == "TP" else "#fca5a5", pos)})
                            else: lab_tpsl_hidden = True
                    d2a = active_lab.get("daily_2y") if isinstance(active_lab.get("daily_2y"), dict) else {}
                    m10a = active_lab.get("macro_10y") if isinstance(active_lab.get("macro_10y"), dict) else {}
                    for la, rp, ca in (("OB支持", active_lab.get("ob_support_px"), "#34d399"), ("HVN壁", d2a.get("hvn_wall_price"), "#c084fc"), ("10Y POC", m10a.get("poc_10y_price"), "#fbbf24")):
                        try:
                            if rp is not None and float(rp) > 0 and abs(float(rp) - curr_px) / curr_px <= 0.12:
                                ml_data.append({"yAxis": round(float(rp), 2), "lineStyle": {"color": ca, "type": "dotted", "width": 1.1}, "label": _hb(f"{la} {_fmt_cur(float(rp), is_jp)}", ca)})
                        except Exception: pass

                cdi, cpi = (traj["live_dip_idx"], traj["live_peak_idx"]) if use_live_basis else (traj["locked_dip_idx"], traj["locked_peak_idx"])
                ml_cfg = {"symbol": ["none", "none"], "data": _declutter_marklines(ml_data, curr_px, 0.45, bool(cdi <= 6 or cpi <= 6))} if ml_data else {}
                pdesc = {"📈 今の予測": "ライブ修正軌道（固有波動合成）＋ 分位点ファン ＋ 場中30分3分岐 ＋ 下段CVD同期", "🔍 朝の答え合わせ": "寄り前ロック予測 vs 当日実測 ＋ 寄り30分高安 ＋ 下段CVD同期", "🏦 大口・節目": "VWAP±σ ＋ PDH/PDL/HOD/LOD ＋ キリ番 ＋ 大口約定 ＋ 下段CVD"}
                st.caption(f"表示中: {pdesc.get(sel_preset, '')}{med_cap}{' ※LAB TP/SLの一部は現在値±12%外のため非表示' if lab_tpsl_hidden else ''}")

                if chart_mode in ("🔒 朝ロック検証", "⚡ 両方重ね"):
                    if traj["verify"]["has_verify"]:
                        v = traj["verify"]
                        st.markdown(f'<div class="dd-quant-box"><b>📊 寄り前ロック予測 vs 当日実測 検証（実測 {v["n_pts"]}本）</b><br>・<b>分位点ファン内 収束率:</b> <b style="color:#fde047;">{v["in_cone_pct"]}%</b> ｜ <b>平均誤差:</b> <b>{v["err_pct"]}%</b></div>', unsafe_allow_html=True)
                    elif traj["has_actual"] and not traj["is_locked"]:
                        st.markdown('<div class="dd-sync-warn"><b>ℹ️ 本日は寄り前2時間以内の事前ロックがないため「朝ロック検証」対象外</b><br>リーク防止のため、寄り前2時間以内に保存された予測のみを答え合わせ対象としています（現在はライブ修正軌道を基準に表示中）。</div>', unsafe_allow_html=True)

                ma_data = []
                if fusion.get("has_lab") and "LAB×DD 統合エントリー帯/+1.0R" in opt_lines and curr_px > 0 and fusion["entry_zone_hi"] > fusion["entry_zone_lo"] > 0 and abs(fusion["entry_zone_lo"] - curr_px) / curr_px <= 0.12:
                    ma_data.append([{"name": "統合Entry帯", "yAxis": fusion["entry_zone_lo"], "itemStyle": {"color": "rgba(16,185,129,.08)"}, "label": {"position": "insideRight", "color": "#6ee7b7", "fontSize": 8.0, "backgroundColor": "rgba(7,11,20,.82)", "padding": [1, 4], "borderRadius": 2}}, {"yAxis": fusion["entry_zone_hi"]}])
                if "高ボラ狩り場帯" in opt_lines:
                    for hz in traj.get("high_vol_zones", []):
                        ma_data.append([{"name": f"±{hz['avg_move_pct']:.1f}%", "xAxis": hz["start_slot"], "itemStyle": {"color": "rgba(245,158,11,.06)"}, "label": {"show": bool(hz.get("show_label", hz.get("width_slots", 3) >= 3)), "position": "insideBottom", "color": "#fbbf24", "fontSize": 8, "backgroundColor": "rgba(7,11,20,.78)", "padding": [1, 3], "borderRadius": 2}}, {"xAxis": hz["end_slot"]}])
                if "押目・利確ゾーン" in opt_lines:
                    ma_data.append([{"name": "押目帯", "xAxis": traj["slots"][max(0, cdi - 2)], "itemStyle": {"color": "rgba(16,185,129,.07)"}, "label": {"position": "insideBottom" if abs(cdi - cpi) <= 8 else "insideTop", "color": "#6ee7b7", "fontSize": 8.2, "backgroundColor": "rgba(7,11,20,.82)", "padding": [1, 3], "borderRadius": 2}}, {"xAxis": traj["slots"][min(n_sl_tot - 1, cdi + 2)]}])
                    ma_data.append([{"name": "利確帯", "xAxis": traj["slots"][max(0, cpi - 2)], "itemStyle": {"color": "rgba(239,68,68,.07)"}, "label": {"position": "insideTop", "color": "#fca5a5", "fontSize": 8.2, "backgroundColor": "rgba(7,11,20,.82)", "padding": [1, 3], "borderRadius": 2}}, {"xAxis": traj["slots"][min(n_sl_tot - 1, cpi + 2)]}])
                    if vp["overhead_pct"] >= 25.0 and not exp_active:
                        ma_data.append([{"name": "売り壁", "yAxis": round(vp["res_px"] * 0.996, 2), "itemStyle": {"color": "rgba(168,85,247,.10)"}, "label": {"position": "insideRight", "color": "#d8b4fe", "fontSize": 8.2, "backgroundColor": "rgba(7,11,20,.82)", "padding": [1, 3], "borderRadius": 2}}, {"yAxis": round(vp["res_px"] * 1.004, 2)}])
                ma_cfg = {"silent": True, "data": ma_data} if ma_data else {}

                s_list, l_names = [], []
                if "予測レンジ帯（ファン）" in opt_lines:
                    ilv = chart_mode in ("🔴 ライブ修正", "⚡ 両方重ね") and traj["has_actual"]
                    c15, cbd, c32, cbdi = (disp_live_p15, disp_live_bdiff, disp_live_p32, disp_live_bdiff_in) if ilv else (disp_locked_p15, disp_locked_bdiff, disp_locked_p32, disp_locked_bdiff_in)
                    s_list.extend([
                        {"name": "outer_base", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": c15, "stack": "fan_out", "lineStyle": {"opacity": 0}, "smooth": 0.15, "showSymbol": False, "silent": True, "z": 1},
                        {"name": "10-90%分位帯", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": cbd, "stack": "fan_out", "lineStyle": {"opacity": 0}, "areaStyle": {"color": "rgba(99,102,241,.08)"}, "smooth": 0.15, "showSymbol": False, "silent": True, "z": 1},
                        {"name": "inner_base", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": c32, "stack": "fan_in", "lineStyle": {"opacity": 0}, "smooth": 0.15, "showSymbol": False, "silent": True, "z": 2},
                        {"name": "コア帯", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": cbdi, "stack": "fan_in", "itemStyle": {"color": "#38bdf8"}, "lineStyle": {"opacity": 0}, "areaStyle": {"color": "rgba(56,189,248,.14)"}, "smooth": 0.15, "showSymbol": False, "silent": True, "z": 2},
                    ]); l_names.append("コア帯")
                if "類似日スパゲッティ軌道" in opt_lines:
                    for ap in traj["knn_match"].get("analog_paths", []):
                        s_list.append({"name": f"類似_{ap['date']}", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": _scale_live(ap["data"]), "lineStyle": {"color": "#94a3b8", "width": 0.9, "opacity": 0.14}, "smooth": 0.15, "showSymbol": False, "silent": True, "z": 2})
                if "類似実測波形（Top-1）" in opt_lines and isinstance(med_info, dict) and med_info.get("data"):
                    s_list.append({"name": "類似実測(Top-1)", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": _scale_live(med_info["data"]), "itemStyle": {"color": "#f59e0b"}, "lineStyle": {"color": "#f59e0b", "width": 1.3, "opacity": 0.68}, "smooth": 0.12, "showSymbol": False, "z": 6}); l_names.append("類似実測(Top-1)")
                if "VWAP" in opt_lines and traj["has_actual"]:
                    s_list.append({"name": "VWAP", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": traj["vwap"], "itemStyle": {"color": "#fbbf24"}, "lineStyle": {"color": "#fbbf24", "width": 1.3, "type": "dotted"}, "showSymbol": False, "z": 6}); l_names.append("VWAP")
                if "VWAP±σ" in opt_lines and traj["has_actual"]:
                    s_list.extend([{"name": nm, "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": traj[k], "lineStyle": {"color": c, "width": 0.9, "type": tp}, "showSymbol": False, "silent": True, "z": 5} for nm, k, c, tp in (("VWAP+1σ", "vwap_p1", "rgba(251,191,36,.48)", "dashed"), ("VWAP-1σ", "vwap_m1", "rgba(251,191,36,.48)", "dashed"), ("VWAP+2σ", "vwap_p2", "rgba(239,68,68,.40)", "dotted"), ("VWAP-2σ", "vwap_m2", "rgba(16,185,129,.40)", "dotted"))])
                if chart_mode in ("🔒 朝ロック検証", "⚡ 両方重ね"):
                    ib = chart_mode == "⚡ 両方重ね"
                    lkn, lkc, lks = ("朝ロック(無効化済)", "rgba(148,163,184,.30)", {"color": "rgba(148,163,184,.30)", "width": 1.2, "type": "dotted"}) if exp_active else ("朝ロック", "#c084fc" if ib else "#38bdf8", {"color": "#c084fc" if ib else "#38bdf8", "width": 1.6 if ib else 2.0, "type": "dashed" if ib else "solid", "shadowBlur": 6, "shadowColor": "rgba(192,132,252,.35)"})
                    s_list.append({"name": lkn, "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": disp_locked_p50, "itemStyle": {"color": lkc}, "lineStyle": lks, "smooth": 0.12, "showSymbol": False, "markLine": ml_cfg, "markArea": ma_cfg, "z": 8}); l_names.append(lkn)
                if chart_mode in ("🔴 ライブ修正", "⚡ 両方重ね"):
                    s_list.append({"name": "ライブ修正", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": disp_live_p50, "itemStyle": {"color": "#38bdf8"}, "lineStyle": {"color": "#38bdf8", "width": 2.0, "shadowBlur": 10, "shadowColor": "rgba(56,189,248,.55)"}, "smooth": 0.12, "showSymbol": False, "markLine": ml_cfg if chart_mode == "🔴 ライブ修正" else {}, "markArea": ma_cfg if chart_mode == "🔴 ライブ修正" else {}, "z": 10}); l_names.append("ライブ修正")
                if traj["has_actual"]:
                    s_list.append({"name": "当日実測", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": traj["actual"], "itemStyle": {"color": "#ffffff"}, "lineStyle": {"color": "#ffffff", "width": 2.4, "shadowBlur": 8, "shadowColor": "rgba(255,255,255,.55)"}, "smooth": False, "showSymbol": False, "z": 14}); l_names.insert(0, "当日実測")

                show_3w = bool("場中30分・3分岐点線（スコア比%）" in opt_lines and short_3way.get("active"))
                if show_3w:
                    for nm, pk, c, lc, lt, fmt, z in (("上昇分岐", "up_path", "#10b981", "#6ee7b7", "dashed", f"▲ {short_3way['p_up']}%", 11), ("横ばい分岐", "flat_path", "#94a3b8", "#cbd5e1", "dotted", f"▶ {short_3way['p_flat']}%", 10), ("下落分岐", "down_path", "#ef4444", "#fca5a5", "dashed", f"▼ {short_3way['p_down']}%", 11)):
                        s_list.append({"name": nm, "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": short_3way[pk], "itemStyle": {"color": c}, "lineStyle": {"color": c, "width": 1.8 if lt == "dashed" else 1.6, "type": lt}, "smooth": 0.15, "showSymbol": False, "endLabel": {"show": True, "distance": 4, "formatter": fmt, "color": lc, "fontSize": 9.5, "fontWeight": "bold", "fontFamily": "JetBrains Mono"}, "z": z})
                if "大口約定（◆）" in opt_lines and traj["vol_spikes"]:
                    s_list.append({"name": "大口約定", "type": "scatter", "xAxisIndex": 0, "yAxisIndex": 0, "symbol": "diamond", "symbolSize": 8, "data": [{"value": [sp["time"], sp["price"]], "itemStyle": {"color": "#10b981" if sp["dir"] > 0 else "#ef4444", "borderColor": "#ffffff", "borderWidth": 1}} for sp in traj["vol_spikes"]], "z": 12})

                rpts = [{"name": "押目", "value": [active_dip_time, active_dip_px], "itemStyle": {"color": "#10b981"}}, {"name": "高値", "value": [active_peak_time, active_peak_px], "itemStyle": {"color": "#f43f5e"}}]
                if traj["has_actual"] and la_idx >= 0: rpts.append({"name": "NOW", "value": [traj["slots"][la_idx], traj["actual"][la_idx]], "itemStyle": {"color": "#ffffff"}})
                if cvd_div.get("marker"): rpts.append({"name": cvd_div["marker"]["name"], "value": [cvd_div["marker"]["time"], cvd_div["marker"]["price"]], "itemStyle": {"color": cvd_div["marker"]["color"]}})
                s_list.append({"name": "重要点", "type": "effectScatter", "xAxisIndex": 0, "yAxisIndex": 0, "data": _declutter_pulse_points(rpts, traj["slots"]), "symbolSize": 7, "rippleEffect": {"brushType": "stroke", "scale": 3.0}, "label": {"show": True, "position": "top", "formatter": "{b}", "color": "#f8fafc", "fontSize": 8.8, "fontWeight": "bold"}, "z": 15})
                s_list.append({"name": "平均出来高", "type": "line", "xAxisIndex": 1, "yAxisIndex": 1, "data": traj["vols"], "lineStyle": {"color": "rgba(148,163,184,.38)", "width": 1.0, "type": "dashed"}, "showSymbol": False, "silent": True})
                if traj["has_actual"] and any(v is not None for v in traj["actual_vols"]):
                    s_list.append({"name": "当日出来高", "type": "bar", "xAxisIndex": 1, "yAxisIndex": 1, "data": [{"value": 0, "itemStyle": {"color": "transparent"}} if vi is None else {"value": vi, "itemStyle": {"color": "rgba(16,185,129,.52)" if di > 0 else "rgba(239,68,68,.52)"}} for vi, di in zip(traj["actual_vols"], traj["actual_dirs"])], "barMaxWidth": 4})
                    s_list.append({"name": "疑似CVD", "type": "line", "xAxisIndex": 1, "yAxisIndex": 2, "data": traj["cvd_arr"], "itemStyle": {"color": "#22d3ee"}, "lineStyle": {"color": "#22d3ee", "width": 1.6}, "areaStyle": {"color": "rgba(34,211,238,.10)"}, "showSymbol": False, "markLine": {"symbol": ["none", "none"], "silent": True, "data": [{"yAxis": 0, "lineStyle": {"color": "rgba(148,163,184,.25)", "type": "dotted", "width": 1}, "label": {"show": False}}]}})
                    l_names.append("疑似CVD")

                rp5 = (58 if is_jp else 52) if show_3w else (50 if is_jp else 44)
                _render_echarts({"backgroundColor": "#070b14", "legend": {"type": "scroll", "data": l_names, "textStyle": {"color": "#cbd5e1", "fontSize": 9.5}, "top": 2, "left": 6, "right": 8, "itemWidth": 12, "itemHeight": 8}, "axisPointer": {"link": [{"xAxisIndex": "all"}]}, "grid": [{"top": 42, "height": "57%", "left": 6, "right": rp5, "containLabel": False}, {"top": "74%", "height": "18%", "left": 6, "right": rp5, "containLabel": False}], "dataZoom": [{"type": "inside", "xAxisIndex": [0, 1], "filterMode": "none"}], "xAxis": [{"type": "category", "gridIndex": 0, "boundaryGap": False, "data": traj["slots"], "axisLine": {"lineStyle": {"color": "rgba(148,163,184,.18)"}}, "axisLabel": {"show": False}}, {"type": "category", "gridIndex": 1, "boundaryGap": False, "data": traj["slots"], "axisLine": {"lineStyle": {"color": "rgba(148,163,184,.18)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9, "interval": "auto", "hideOverlap": True}}], "yAxis": [{"type": "value", "gridIndex": 0, "position": "right", "scale": True, "splitLine": {"lineStyle": {"color": "rgba(255,255,255,.04)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9}}, {"type": "value", "gridIndex": 1, "show": False, "axisPointer": {"show": False}}, {"type": "value", "gridIndex": 1, "position": "right", "scale": True, "splitLine": {"show": False}, "axisLabel": {"color": "#22d3ee", "fontSize": 8}}], "series": s_list}, 415, True, is_jp, True, True, f"dd_5m_{fc}")

                if show_3w:
                    mlb = f' <span style="background:rgba(168,85,247,.22);border:1px solid rgba(168,85,247,.5);color:#e9d5ff;padding:1px 5px;border-radius:4px;font-size:9.5px;">🤖ML学習(N={short_3way["ml_samples"]})</span>' if short_3way.get("ml_used") else ""
                    st.markdown(f'<div class="dd-3way-strip"><span style="color:#7dd3fc;font-weight:800;">⚡ 短期{short_3way["horizon"]*5}分3分岐:{mlb}</span><span><span style="color:#6ee7b7;font-weight:800;">▲上昇 {short_3way["p_up"]}%</span> / <span style="color:#cbd5e1;font-weight:800;">▶横ばい {short_3way["p_flat"]}%</span> / <span style="color:#fca5a5;font-weight:800;">▼下落 {short_3way["p_down"]}%</span></span></div>', unsafe_allow_html=True)
                _render_chart_legend_panel(traj, chart_mode, opt_lines, short_3way, exp_reg, active_dip_time, active_peak_time, cur_vwap_now, curr_px, is_jp, active_lab, False)

            basis_txt = "ライブ連動" if use_live_basis else "朝ロック基準"
            shk_txt = f" / 衝撃波{shock_ext_pct:+.2f}%" if abs(shock_ext_pct) > 0.01 else ""
            st.markdown(f'<div class="dd-prob-meter"><div style="display:flex;justify-content:space-between;align-items:center;font-size:10px;"><span style="font-weight:800;color:#7dd3fc;">SCENARIO ALLOCATION // リアルタイム・シナリオ配分（スコア比）</span><span style="font-family:JetBrains Mono,monospace;color:#64748b;font-size:9.3px;">{basis_txt}{shk_txt}</span></div><div class="dd-prob-stack"><div style="width:{scen_probs["bull"]}%;background:#10b981;"></div><div style="width:{scen_probs["range"]}%;background:#38bdf8;"></div><div style="width:{scen_probs["fade"]}%;background:#f59e0b;"></div><div style="width:{scen_probs["bear"]}%;background:#ef4444;"></div></div><div class="dd-prob-legend"><div style="color:#6ee7b7;">🟢 上振れ突破 <b>{scen_probs["bull"]:.1f}%</b></div><div style="color:#7dd3fc;">🔵 標準レンジ <b>{scen_probs["range"]:.1f}%</b></div><div style="color:#fde047;">🟠 窓埋め反転 <b>{scen_probs["fade"]:.1f}%</b></div><div style="color:#fca5a5;">🔴 下振れ崩壊 <b>{scen_probs["bear"]:.1f}%</b></div></div></div>', unsafe_allow_html=True)

            with st.expander("⚡ What-If 衝撃波シミュレーター（指数・為替 追加変動テスト）", expanded=False):
                w1, w2 = st.columns(2)
                w1.slider(f"主連動（{f_map['mkt_label']} β={mkt_beta_eff:+.2f}）追加変動 (%)", -2.0, 2.0, step=0.1, key=wi_idx_key)
                w2.slider(f"ドル円（β={fx_beta_eff:+.2f}）追加変動 (円)", -2.0, 2.0, step=0.1, key=wi_fx_key)
                st.caption(f"合成ショック影響: {shock_ext_pct:+.2f}% ｜ 想定大引け: {_fmt_cur(active_close_px, is_jp)} ({active_close_chg:+.2f}%) ｜ 上振れ配分: {scen_probs['bull']:.1f}% / 下振れ配分: {scen_probs['bear']:.1f}%")

            with st.expander("🧮 適正ロット・100株単元・流動性インパクト・二壁FPT電卓", expanded=False):
                l_tp_ev = fusion["fusion_tp_px"] if fusion.get("has_lab") else (float(active_lab.get("tp", active_lab.get("raw_tp", 0.0)) or 0.0) if active_lab else 0.0)
                l_sl_ev = fusion["fusion_sl_px"] if fusion.get("has_lab") else (float(active_lab.get("sl", active_lab.get("raw_sl", 0.0)) or 0.0) if active_lab else 0.0)
                l_side_ev = _extract_lab_side(active_lab) if active_lab else "LONG"; is_long_ev = l_side_ev != "SHORT"
                def_tp, def_sl = (l_tp_ev if l_tp_ev > 0 else (active_bull_tgt if is_long_ev else active_bear_tgt)), (l_sl_ev if l_sl_ev > 0 else (active_bear_trig if is_long_ev else active_bull_trig))
                ec1, ec2 = st.columns([1.4, 1.0])
                risk_amt = ec1.number_input(f"1回の許容損失額 ({'円' if is_jp else '$'})", min_value=10.0, value=10000.0 if is_jp else 100.0, step=1000.0 if is_jp else 25.0, key=f"dd_risk_amt_{'jp' if is_jp else 'us'}")
                win_prob = ec2.slider("想定勝率 (%)", 30, 80, int(np.clip(round(fusion["fusion_score"]) if fusion.get("has_lab") else (int(active_lab.get("expect_pct", 55)) if active_lab else 55), 30, 80)), key="dd_win_prob")
                spx = round(curr_px * (1.0 + shock_ext_pct / 100.0 * 0.35), 2)
                srisk, srew = ((spx - def_sl, def_tp - spx) if is_long_ev else (def_sl - spx, spx - def_tp))
                sl_b, tp_p = bool(srisk <= 0), bool(srew <= 0)
                rps, rwps = (max(srisk, spx * 0.005) if not sl_b else spx * 0.005), max(srew, 0.0)
                rr = (rwps / rps) if (not sl_b and not tp_p) else 0.0
                rsh = 0 if (sl_b or tp_p) else int(risk_amt // rps)
                jp_ul = False
                if sl_b or tp_p: csh, llbl, lcol = 0, "0株 (条件破綻)", "#ef4444"
                elif is_jp:
                    osh = (rsh // 100) * 100; jp_ul = osh < 100; csh = osh if not jp_ul else 100
                    llbl, lcol = (f"{osh:,}株 ({osh//100}単元)", "#38bdf8") if not jp_ul else ("0株 (見送り推奨)", "#ef4444")
                else:
                    csh = max(1, rsh); llbl, lcol = f"{csh:,}株", "#38bdf8"
                bewr = (1.0 / (1.0 + rr)) * 100.0 if rr > 0 else 99.9
                evv = (win_prob / 100.0) * (csh * rwps) - (1.0 - win_prob / 100.0) * (csh * rps)
                imp = (csh / max(float(traj.get("avg_5m_vol", 1.0)), 1.0)) * 100.0
                tp_fpt, sl_fpt, tb_tp = _calc_first_passage_prob(spx, def_tp, traj["rem_sigma_pct"], active_rem_drift), _calc_first_passage_prob(spx, def_sl, traj["rem_sigma_pct"], active_rem_drift), _calc_two_barrier_tp_prob(spx, def_tp, def_sl, is_long_ev, traj["rem_sigma_pct"], active_rem_drift)

                st.markdown(f'<div style="font-size:11px;color:#94a3b8;">基準({l_side_ev}): Entry <b>{_fmt_cur(spx, is_jp)}</b> / TP <b>{_fmt_cur(def_tp, is_jp)}</b> / SL <b>{_fmt_cur(def_sl, is_jp)}</b>（残存σ {traj["rem_sigma_pct"]*100:.2f}% / 残出来高割合 {int(round(traj["rem_frac_now"]*100))}%）</div><div class="dd-ev-grid"><div class="dd-ev-cell"><div class="dd-metric-lbl">適正ロット</div><div style="font-family:JetBrains Mono,monospace;font-size:12.5px;font-weight:800;color:{lcol};">{llbl}</div></div><div class="dd-ev-cell"><div class="dd-metric-lbl">RR比 (損益分岐)</div><div style="font-family:JetBrains Mono,monospace;font-size:12.5px;font-weight:800;color:#fde047;">1:{rr:.2f} ({bewr:.0f}%)</div></div><div class="dd-ev-cell"><div class="dd-metric-lbl">1回あたり期待値</div><div style="font-family:JetBrains Mono,monospace;font-size:12.5px;font-weight:800;color:{"#10b981" if evv>0 else "#ef4444"};">{"+" if evv>=0 else ""}{_fmt_cur(evv, is_jp)}</div></div></div><div class="dd-ev-grid" style="margin-top:6px;"><div class="dd-ev-cell"><div class="dd-metric-lbl">SL前TP先達 (二壁FPT)</div><div style="font-family:JetBrains Mono,monospace;font-size:12.5px;font-weight:800;color:{"#10b981" if tb_tp>=35 else "#f59e0b"};">{tb_tp:.1f}% <span style="font-size:9px;color:#94a3b8;">(片壁{tp_fpt:.0f}%)</span></div></div><div class="dd-ev-cell"><div class="dd-metric-lbl">大引け迄 SLタッチ</div><div style="font-family:JetBrains Mono,monospace;font-size:12.5px;font-weight:800;color:{"#ef4444" if sl_fpt>=45 else "#94a3b8"};">{sl_fpt:.1f}%</div></div><div class="dd-ev-cell"><div class="dd-metric-lbl">流動性インパクト</div><div style="font-family:JetBrains Mono,monospace;font-size:12.5px;font-weight:800;color:{"#ef4444" if imp>=2.0 else ("#f59e0b" if imp>=0.8 else "#10b981")};">{imp:.2f}%</div></div></div>', unsafe_allow_html=True)
                if sl_b: st.markdown('<div class="dd-warn-box" style="margin-top:6px;margin-bottom:0;"><b>⛔ すでに損切りライン（SL）を割り込んでいます</b><br>現在値がSL水準を突破済みのため、新規エントリー不可（0株見送り）です。</div>', unsafe_allow_html=True)
                elif tp_p: st.markdown('<div class="dd-sync-warn" style="margin-top:6px;margin-bottom:0;"><b>⚠️ すでに利確目標（TP）に到達済みです</b><br>値幅を取り切った後の高値掴みリスクが高いため、新規エントリーは見送りを推奨します。</div>', unsafe_allow_html=True)
                elif jp_ul: st.markdown(f'<div class="dd-warn-box" style="margin-top:6px;margin-bottom:0;"><b>⛔ 1単元（100株）で許容損失オーバー</b><br>最小単元100株のSL到達時損失は <b>{_fmt_cur(100.0*rps, True)}</b> で許容損失（{_fmt_cur(risk_amt, True)}）を超過します。</div>', unsafe_allow_html=True)
                if not sl_b and not tp_p and (win_prob - tb_tp) >= 20.0: st.markdown(f'<div class="dd-sync-warn" style="margin-top:6px;margin-bottom:0;"><b>⚠️ 想定勝率({win_prob}%)と大引け迄の二壁FPT到達確率({tb_tp:.1f}%)が乖離</b><br>デイトレ完結ならTPを近づけるか勝率設定を引き下げてください。</div>', unsafe_allow_html=True)
                if imp >= 2.0 or traj["lab_mods"].get("kyle_warn"): st.markdown(f'<div class="dd-warn-box" style="margin-top:6px;margin-bottom:0;"><b>⚠️ 流動性インパクト警戒（出来高比 {imp:.2f}% / LAB Kyle-λ={traj["lab_mods"].get("kyle_val","-")}）</b><br>板が薄くスリッページでRR比が崩壊する恐れがあります。指値分割執行を推奨します。</div>', unsafe_allow_html=True)
                if traj["has_actual"] and tb_tp < 20.0 and traj["rem_frac_now"] < 0.45 and not sl_b and not tp_p: st.markdown('<div class="dd-warn-box" style="margin-top:6px;margin-bottom:0;"><b>⛔ 時間切れ警戒（手遅れエントリー注意）</b><br>残存ボラティリティに対しTPが遠すぎます（二壁到達確率 20%未満）。新規の追っかけエントリーは非推奨です。</div>', unsafe_allow_html=True)

            bp, sp, mp = (active_bull_tgt - curr_px) / max(curr_px, 1e-4) * 100.0, (active_bear_tgt - curr_px) / max(curr_px, 1e-4) * 100.0, round(scen_probs["range"] + scen_probs["fade"], 1)
            st.markdown(f'<div class="dd-sc-stack"><div class="dd-sc-card" style="border-left:4px solid #10b981;"><div class="dd-sc-top"><div><div style="font-weight:800;color:#6ee7b7;font-size:12px;">上振れ突破（配分 {scen_probs["bull"]:.1f}%）</div><div style="font-size:10.5px;color:#cbd5e1;margin-top:2px;">トリガー: <b>{_fmt_cur(active_bull_trig, is_jp)}</b> 超え（FPT {scen_probs["fpt_bull_pct"]:.1f}%）</div></div><div style="text-align:right;flex-shrink:0;"><div class="dd-sc-price" style="color:#6ee7b7;">{_fmt_cur(active_bull_tgt, is_jp)}</div><div class="dd-sc-pct" style="color:#10b981;">{bp:+.2f}%</div></div></div><div class="dd-sc-bar-bg"><div class="dd-sc-bar-fill" style="width:{scen_probs["bull"]:.1f}%;background:#10b981;"></div></div></div><div class="dd-sc-card" style="border-left:4px solid #38bdf8;"><div class="dd-sc-top"><div><div style="font-weight:800;color:#7dd3fc;font-size:12px;">標準レンジ・窓埋（配分 {mp:.1f}%）</div><div style="font-size:10.5px;color:#cbd5e1;margin-top:2px;">押目 <b>{active_dip_time}</b> ({_fmt_cur(active_dip_px, is_jp)}) → 高値 <b>{active_peak_time}</b></div></div><div style="text-align:right;flex-shrink:0;"><div class="dd-sc-price" style="color:#7dd3fc;">{_fmt_cur(active_close_px, is_jp)}</div><div class="dd-sc-pct" style="color:#38bdf8;">{active_close_chg:+.2f}%</div></div></div><div class="dd-sc-bar-bg"><div class="dd-sc-bar-fill" style="width:{mp:.1f}%;background:#38bdf8;"></div></div></div><div class="dd-sc-card" style="border-left:4px solid #ef4444;"><div class="dd-sc-top"><div><div style="font-weight:800;color:#fca5a5;font-size:12px;">下振れ崩壊（配分 {scen_probs["bear"]:.1f}%）</div><div style="font-size:10.5px;color:#cbd5e1;margin-top:2px;">トリガー: <b>{_fmt_cur(active_bear_trig, is_jp)}</b> 割れ（FPT {scen_probs["fpt_bear_pct"]:.1f}%）</div></div><div style="text-align:right;flex-shrink:0;"><div class="dd-sc-price" style="color:#fca5a5;">{_fmt_cur(active_bear_tgt, is_jp)}</div><div class="dd-sc-pct" style="color:#ef4444;">{sp:+.2f}%</div></div></div><div class="dd-sc-bar-bg"><div class="dd-sc-bar-fill" style="width:{scen_probs["bear"]:.1f}%;background:#ef4444;"></div></div></div></div>', unsafe_allow_html=True)

            f, we = traj["factors"], traj["weights_evolution"]
            og_n, idr_n, ld = we["open_gap"], we["intraday_drift"], we.get("last_decomp", {})
            top3 = sorted([(f"主連動（{f['mkt_label']} β{f['mkt_beta']:+.2f}）", f["macro_gap_pct"]), (f"為替（ドル円 β{f['fx_beta']:+.2f}）", f["fx_gap_pct"]), (f"日英高信頼ニュース（一次{news_res['tier1_cnt']}件）", f["news_gap_pct"]), ("大口・インサイダー異変（30日内）", f["whale_gap_pct"]), ("LAB上位足バイアス", f["lab_bias_pct"]), ("曜日エッジ＋ヒゲ圧力", f["dow_wick_pct"]), ("台帳キャリブレーション", f["calib_pct"]), ("場中VWAP・30分勢い・指数α追従", f["live_vwap_pct"])], key=lambda x: abs(x[1]), reverse=True)[:3]
            _frow = lambda l, v, c: f'<div class="dd-factor-row"><span>{html.escape(l)}</span><span style="font-family:JetBrains Mono,monospace;color:{c};">{v}</span></div>'
            st.markdown(f'<div class="dd-dark-box"><div style="font-size:10.5px;font-weight:800;color:#38bdf8;margin-bottom:4px;">KEY DRIVERS // 主要寄与 Top3（{html.escape(we["active_cluster"])}・{we["active_regime"]}脳 N={we["cluster_n"]} / 累計{we["updates_count"]}回）</div>{"".join(_frow(l, f"{v:+.2f}%", "#10b981" if v>=0 else "#ef4444") for l, v in top3)}{_frow("合成・寄付き予測 → 大引け予測", f"{active_open_gap_pct:+.2f}% → {active_close_chg:+.2f}%", "#10b981" if active_close_chg>=0 else "#ef4444")}</div>', unsafe_allow_html=True)

            with st.expander("🔬 全ファクター内訳（17項目）＆ クラスタ別3脳SGD進化重み", expanded=False):
                lm = traj.get("lab_mods", {})
                lmod_s = f"信頼度×{lm.get('lab_trust_mult',1.0):.2f} / VPIN={lm.get('vpin_val','-')} / Kyle-λ={lm.get('kyle_val','-')}{' / 監査官警戒減衰' if lm.get('council_caution') else ''}" if lm.get("has_lab") else "単体検索（デフォルト×1.00）"
                rows17 = [
                    ("EXPANSION レジーム解放ステータス", f"稼働中（{exp_reg['label']} / 紫線降格・レジサポ反転済）" if exp_active else "通常レジーム（朝ロック基準維持）", "#10b981" if exp_active else "#94a3b8"),
                    (f"主連動（{f['mkt_label']} {f['mkt_diff']:+.2f}% × β{f['mkt_beta']:+.2f} × 重み{og_n['macro']:.2f}）", f"{f['macro_gap_pct']:+.2f}%", "#10b981" if f["macro_gap_pct"] >= 0 else "#ef4444"),
                    (f"為替（ドル円 {f['fx_diff']:+.2f}% × β{f['fx_beta']:+.2f} × 重み{og_n['fx']:.2f}）", f"{f['fx_gap_pct']:+.2f}%", "#10b981" if f["fx_gap_pct"] >= 0 else "#ef4444"),
                    (f"日英高信頼ニュース時間減衰スコア（一次 {news_res['tier1_cnt']}件・重み{og_n['news']:.2f}）", f"{f['news_gap_pct']:+.2f}%", "#10b981" if f["news_gap_pct"] >= 0 else "#ef4444"),
                    (f"大口・インサイダー直近30日異変補正（重み{og_n['whale']:.2f}）", f"{f['whale_gap_pct']:+.2f}%", "#10b981" if f["whale_gap_pct"] >= 0 else "#ef4444"),
                    (f"LAB上位足 方向性・期待度バイアス（寄付重み{og_n['lab_bias']:.2f} / 日中重み{idr_n['lab_bias']:.2f}）", f"{f['lab_bias_pct']:+.2f}%", "#10b981" if f["lab_bias_pct"] >= 0 else "#ef4444"),
                    ("LAB高度連動ステータス（22日PF/勝率・VPIN・Kyle-λ・監査官）", lmod_s, "#e9d5ff"),
                    ("出来高時計（Volume Clock）進行エンジン", "有効（累積出来高比例）" if traj.get("vol_clock_active") else "線形時間フォールバック", "#38bdf8"),
                    ("日本株 昼休みジャンプ分散 ＆ 後場ギャップ補正", f"σ={traj.get('lunch_jump_std_pct',0.0):.2f}% / 後場Gap補正={traj.get('lunch_gap_adj_pct',0.0):+.2f}%" if is_jp else "米国市場（昼休みなし）", "#fde047"),
                    ("短期30分3分岐 NumPy軽量ロジスティック回帰", f"稼働中（N={traj['ml_3way_model'].get('n_samples',0)}本学習済）" if traj["ml_3way_model"].get("fitted") else f"サンプル蓄積中（N={traj['ml_3way_model'].get('n_samples',0)}/60本）", "#c084fc"),
                    (f"指数ベータ分離5分足モデル（5m β={traj['bench_beta_5m']:+.2f} / ライブ指数追従 {f['bench_alpha_pct']:+.2f}%）", "有効" if traj["has_bench_5m"] else "フォールバック", "#38bdf8"),
                    ("HVNしこり壁 / 機関OB支持帯", f"HVN {_fmt_cur(f['hvn_wall_px'], is_jp) if f.get('hvn_wall_px',0)>0 else '-'} / OB {_fmt_cur(f['ob_sup_px'], is_jp) if f.get('ob_sup_px',0)>0 else '-'}", "#c084fc"),
                    ("対象日曜日エッジ ＋ 直近5日ヒゲ圧力補正", f"{f['dow_wick_pct']:+.2f}%", "#10b981" if f["dow_wick_pct"] >= 0 else "#ef4444"),
                    (f"台帳自己学習キャリブレーション（過去{f['calib_n']}日）", f"{f['calib_pct']:+.2f}%", "#10b981" if f["calib_pct"] >= 0 else "#ef4444"),
                    ("場中VWAP・30分勢い・初動15分Gap・指数α補正", f"{f['live_vwap_pct']:+.2f}%", "#10b981" if f["live_vwap_pct"] >= 0 else "#ef4444"),
                    ("k-NN複合類似日マッチ（指数分離ATR正規化＋コサイン＋RVOL）", ", ".join(traj["knn_match"]["matched_dates"][:3]) if traj["knn_match"]["matched_dates"] else "場前待機", "#7dd3fc"),
                    (f"クラスタSGD誤差（{ld.get('date','-')} / {ld.get('cluster','-')}・{ld.get('regime','NEUTRAL')}脳）", f"寄付 {float(ld.get('open_err_pct',0)):+.2f}% / 日中残差 {float(ld.get('intraday_err_pct',0)):+.2f}%", "#fde047"),
                    ("直近の最大誤差犯人ファクター（過大/過小特定）", f"寄付:{ld.get('culprit_open','-')} / 日中:{ld.get('culprit_intra','-')}", "#fca5a5"),
                ]
                st.markdown(f'<div class="dd-dark-box" style="margin-bottom:8px;">{"".join(_frow(l, html.escape(v), c) for l, v, c in rows17)}</div>', unsafe_allow_html=True)
                st.json({"active_cluster": we["active_cluster"], "shrinkage_alpha": we["shrink_alpha"], "active_regime_brain": we["active_regime"], "total_updates_count": we["updates_count"], "cluster_regime_brains": we["all_regimes"], "last_decomposition": ld})
                if st.button("🔄 クラスタ別3脳SGD進化重みを初期値にリセット", key="dd_reset_weights_btn", use_container_width=True):
                    _save_weights_evolution(DEFAULT_WEIGHTS_EVOLUTION); st.rerun()

        with t2:
            d_cells = "".join(f'<div class="dd-dow-cell" style="{"border:1.5px solid #fde047;background:rgba(250,204,21,.12);" if d["dow"]==next_wd else ""}"><div style="font-size:10px;color:{"#fde047" if d["dow"]==next_wd else "#94a3b8"};font-weight:800;">{d["label"]}曜 {"★対象" if d["dow"]==next_wd else ""}</div><div style="font-family:JetBrains Mono,monospace;font-size:12.5px;font-weight:800;color:{"#10b981" if d["avg"]>=0 else "#ef4444"};margin-top:2px;">{d["avg"]:+.2f}%</div><div style="font-size:9.5px;color:#cbd5e1;">勝率 {d["wr"]}%</div></div>' for d in dow_stats)
            st.markdown(f'<div class="dd-dark-box"><b>DAY-OF-WEEK EDGE // 曜日別アノマリー（過去1年実測・対象日={traj["target_date"]}）</b><div class="dd-dow-grid">{d_cells}</div></div>', unsafe_allow_html=True)
            if (hm := _compute_dow_intraday_heatmap(df_5m, is_jp)).get("valid"):
                st.markdown("##### 🔥 曜日 × 30分時間帯 期待値ヒートマップ（過去1ヶ月5分足集計）")
                bb, wb = hm.get("best"), hm.get("worst")
                if bb or wb:
                    b_txt = f"🏆 ベスト: <b>{html.escape(bb[1])}</b> ({bb[0]:+.2f}% / 勝率{bb[2]}% / N={bb[3]})" if bb else ""
                    w_txt = f"📉 ワースト: <b>{html.escape(wb[1])}</b> ({wb[0]:+.2f}% / 勝率{wb[2]}% / N={wb[3]})" if wb else ""
                    st.markdown(f'<div class="dd-dark-box" style="padding:7px 10px;margin-bottom:6px;font-size:11px;">{b_txt}　｜　{w_txt}</div>', unsafe_allow_html=True)
                _render_echarts({"backgroundColor": "#070b14", "tooltip": {"position": "top", "backgroundColor": "rgba(7,11,20,.92)", "borderColor": "#38bdf8", "textStyle": {"color": "#f8fafc", "fontSize": 10.5, "fontFamily": "JetBrains Mono, monospace"}}, "grid": {"top": 10, "bottom": 52, "left": 8, "right": 14, "containLabel": True}, "xAxis": {"type": "category", "data": hm["x_labels"], "axisLabel": {"color": "#94a3b8", "fontSize": 9, "interval": 0, "rotate": 35, "hideOverlap": True}, "splitArea": {"show": True}}, "yAxis": {"type": "category", "data": hm["y_labels"], "axisLabel": {"color": "#e2e8f0", "fontSize": 10, "fontWeight": "bold"}, "splitArea": {"show": True}}, "visualMap": {"min": -hm["vmax"], "max": hm["vmax"], "calculable": False, "orient": "horizontal", "left": "center", "bottom": 0, "itemWidth": 10, "itemHeight": 90, "textStyle": {"color": "#94a3b8", "fontSize": 9}, "inRange": {"color": ["#dc2626", "#1e293b", "#10b981"]}}, "series": [{"name": "30分期待値", "type": "heatmap", "data": hm["data"], "label": {"show": False}, "emphasis": {"itemStyle": {"borderColor": "#ffffff", "borderWidth": 1}}}]}, 230, chart_key=f"dd_hm_{fc}")
            if macro_sens:
                if (rc := _compute_rolling_macro_corr(df_1d["Close"], macro_data.get(macro_sens[0]["key"], {}))).get("valid"):
                    dec = ' <span style="background:rgba(245,158,11,.22);border:1px solid #f59e0b;color:#fde047;padding:1px 6px;border-radius:99px;font-size:10px;font-weight:800;">⚡ デカップリング検知（個別材料主導相場）</span>' if rc.get("decoupled") else ""
                    st.markdown(f"##### 📈 ローリング相関（20日 vs 60日）＆ 20日β推移 — {html.escape(rc['label'])}{dec}", unsafe_allow_html=True)
                    _render_echarts({"backgroundColor": "#070b14", "tooltip": {"trigger": "axis", "backgroundColor": "rgba(7,11,20,.92)", "borderColor": "rgba(56,189,248,.45)", "textStyle": {"color": "#f8fafc", "fontSize": 10}}, "legend": {"type": "scroll", "data": ["20日相関", "60日相関", "20日β"], "textStyle": {"color": "#cbd5e1", "fontSize": 9.5}, "top": 2}, "grid": {"top": 30, "bottom": 22, "left": 8, "right": 34, "containLabel": True}, "xAxis": {"type": "category", "boundaryGap": False, "data": rc["dates"], "axisLabel": {"color": "#94a3b8", "fontSize": 9, "interval": "auto", "hideOverlap": True}}, "yAxis": [{"type": "value", "min": -1, "max": 1, "splitLine": {"lineStyle": {"color": "rgba(255,255,255,.05)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9}}, {"type": "value", "position": "right", "scale": True, "splitLine": {"show": False}, "axisLabel": {"color": "#fbbf24", "fontSize": 8.5}}], "series": [{"name": "20日相関", "type": "line", "yAxisIndex": 0, "data": rc["c20"], "itemStyle": {"color": "#38bdf8"}, "lineStyle": {"color": "#38bdf8", "width": 2.0}, "showSymbol": False}, {"name": "60日相関", "type": "line", "yAxisIndex": 0, "data": rc["c60"], "itemStyle": {"color": "#c084fc"}, "lineStyle": {"color": "#c084fc", "width": 1.6, "type": "dashed"}, "showSymbol": False}, {"name": "20日β", "type": "line", "yAxisIndex": 1, "data": rc["b20"], "itemStyle": {"color": "#fbbf24"}, "lineStyle": {"color": "rgba(251,191,36,.55)", "width": 1.2}, "areaStyle": {"color": "rgba(251,191,36,.10)"}, "showSymbol": False}]}, 225, chart_key=f"dd_rc_{fc}")
                st.markdown("##### マクロ感応度マトリクス（過去90営業日の相関係数）")
                _render_echarts({"backgroundColor": "#070b14", "tooltip": {"trigger": "axis"}, "grid": {"top": 12, "bottom": 20, "left": 6, "right": 14, "containLabel": True}, "xAxis": {"type": "value", "min": -1, "max": 1, "splitLine": {"lineStyle": {"color": "rgba(255,255,255,.06)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9.5}}, "yAxis": {"type": "category", "data": [x["label"] for x in macro_sens][::-1], "axisLabel": {"color": "#e2e8f0", "fontSize": 10.5}}, "series": [{"type": "bar", "data": [{"value": x["corr"], "itemStyle": {"color": "#10b981" if x["corr"] >= 0 else "#ef4444"}} for x in macro_sens[::-1]]}]}, 215, chart_key=f"dd_ms_{fc}")
            if eh := [e for e in data["earnings_hist"] if e["est"] is not None or e["rep"] is not None]:
                st.markdown("##### 決算サプライズ（予想EPS vs 実績EPS）"); ehr = eh[::-1]
                _render_echarts({"backgroundColor": "#070b14", "tooltip": {"trigger": "axis"}, "legend": {"type": "scroll", "data": ["予想EPS", "実績EPS"], "textStyle": {"color": "#cbd5e1", "fontSize": 10}, "top": 2}, "grid": {"top": 30, "bottom": 20, "left": 6, "right": 10, "containLabel": True}, "xAxis": {"type": "category", "data": [e["date"][2:7] for e in ehr], "axisLabel": {"color": "#94a3b8", "fontSize": 9.5}}, "yAxis": {"type": "value", "splitLine": {"lineStyle": {"color": "rgba(255,255,255,.06)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9.5}}, "series": [{"name": "予想EPS", "type": "bar", "data": [e["est"] for e in ehr], "itemStyle": {"color": "#64748b"}}, {"name": "実績EPS", "type": "bar", "data": [{"value": e["rep"], "itemStyle": {"color": "#10b981" if (e["surp"] or 0) >= 0 else "#ef4444"}} for e in ehr]}]}, 205, chart_key=f"dd_eh_{fc}")
                if (pead := _compute_earnings_pead(df_1d, data["earnings_hist"])).get("valid"):
                    st.markdown("##### ⚡ 決算PEAD（翌日ギャップ％ vs 決算後5日累計リターン％）")
                    _render_echarts({"backgroundColor": "#070b14", "tooltip": {"trigger": "axis", "backgroundColor": "rgba(7,11,20,.92)", "borderColor": "rgba(56,189,248,.45)", "textStyle": {"color": "#f8fafc", "fontSize": 10}}, "legend": {"type": "scroll", "data": ["翌日ギャップ%", "5日累計%"], "textStyle": {"color": "#cbd5e1", "fontSize": 9.5}, "top": 2}, "grid": {"top": 30, "bottom": 20, "left": 6, "right": 14, "containLabel": True}, "xAxis": {"type": "category", "data": pead["dates"], "axisLabel": {"color": "#94a3b8", "fontSize": 9.5, "hideOverlap": True}}, "yAxis": {"type": "value", "splitLine": {"lineStyle": {"color": "rgba(255,255,255,.06)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9, "formatter": "{value}%"}}, "series": [{"name": "翌日ギャップ%", "type": "bar", "data": [{"value": g, "itemStyle": {"color": "rgba(16,185,129,.75)" if g >= 0 else "rgba(239,68,68,.75)"}} for g in pead["gaps"]], "barMaxWidth": 20}, {"name": "5日累計%", "type": "line", "data": pead["drifts5"], "itemStyle": {"color": "#38bdf8"}, "lineStyle": {"color": "#38bdf8", "width": 2.2}, "symbol": "circle", "symbolSize": 7}]}, 205, chart_key=f"dd_pead_{fc}")

        with t3:
            st.markdown("##### 大口投資家・大株主 Top 10 ランキング")
            if inst_h := data["inst_holders"]:
                revh = sorted(inst_h, key=lambda x: x["pct"], reverse=True)[:10][::-1]
                rcols = ["#f59e0b", "#38bdf8", "#10b981"]
                bd = [{"value": round(x["pct"], 2), "itemStyle": {"color": rcols[len(revh) - 1 - i] if len(revh) - 1 - i < 3 else "#6366f1", "borderRadius": [0, 4, 4, 0]}, "label": {"show": True, "position": "right", "color": "#e2e8f0", "fontSize": 9.5, "formatter": f"{x['pct']:.1f}% ({_fmt_sh(x['shares'])})" if _fmt_sh(x["shares"]) != "-" else f"{x['pct']:.1f}%"}} for i, x in enumerate(revh)]
                _render_echarts({"backgroundColor": "#070b14", "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}}, "grid": {"top": 10, "bottom": 18, "left": 4, "right": 96, "containLabel": True}, "xAxis": {"type": "value", "splitLine": {"lineStyle": {"color": "rgba(255,255,255,.06)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9, "formatter": "{value}%"}}, "yAxis": {"type": "category", "data": [f"#{len(revh)-i} {x['holder'][:14]}" for i, x in enumerate(revh)], "axisLabel": {"color": "#f8fafc", "fontSize": 9.5}}, "series": [{"name": "保有比率", "type": "bar", "data": bd, "barMaxWidth": 15}]}, max(210, len(revh) * 28), chart_key=f"dd_inst_{fc}")
            elif is_jp:
                st.link_button(f"🏛️ 株探で {short_code} の大株主一覧を見る", f"https://kabutan.jp/stock/holder?code={short_code}", use_container_width=True)

            axes_r, vals_r, miss_r = _compute_real_5axis(info, vp["overhead_pct"], len(gov_risks))
            if len(axes_r) >= 3:
                _render_echarts({"backgroundColor": "#070b14", "radar": {"radius": "62%", "indicator": axes_r, "axisName": {"color": "#cbd5e1", "fontSize": 10.5}}, "series": [{"type": "radar", "data": [{"value": vals_r, "name": "実測体力", "itemStyle": {"color": "#38bdf8"}, "areaStyle": {"color": "rgba(56,189,248,.28)"}}]}]}, 215, chart_key=f"dd_rad_{fc}")
            if miss_r: st.caption(f"※ APIデータ未提供のため除外した項目（嘘なし評価）: {', '.join(miss_r)}")
            _render_valuation_gauges(info, is_jp)

            if (vp28 := _compute_hires_vp_28(df_1d, curr_px, is_jp)).get("valid"):
                st.markdown("##### 📊 高解像度 Volume Profile（28分割・VA70% / POC / 短期20日vs中期60日減衰）")
                st.markdown(f'<div class="dd-ev-grid" style="margin-top:4px;margin-bottom:6px;"><div class="dd-ev-cell"><div class="dd-metric-lbl">VAH (VA上限)</div><div style="font-family:JetBrains Mono,monospace;font-size:12px;font-weight:800;color:#38bdf8;">{_fmt_cur(vp28["vah_px"], is_jp)}</div></div><div class="dd-ev-cell"><div class="dd-metric-lbl">POC (最大出来高)</div><div style="font-family:JetBrains Mono,monospace;font-size:12px;font-weight:800;color:#fbbf24;">{_fmt_cur(vp28["poc_px"], is_jp)}</div></div><div class="dd-ev-cell"><div class="dd-metric-lbl">VAL (VA下限)</div><div style="font-family:JetBrains Mono,monospace;font-size:12px;font-weight:800;color:#6ee7b7;">{_fmt_cur(vp28["val_px"], is_jp)}</div></div></div>', unsafe_allow_html=True)
                _render_echarts({"backgroundColor": "#070b14", "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}, "backgroundColor": "rgba(7,11,20,.92)", "borderColor": "rgba(56,189,248,.45)", "textStyle": {"color": "#f8fafc", "fontSize": 10}}, "legend": {"type": "scroll", "data": ["直近20日出来高", "中期60日減衰"], "textStyle": {"color": "#cbd5e1", "fontSize": 9.5}, "top": 2}, "grid": {"top": 28, "bottom": 20, "left": 6, "right": 14, "containLabel": True}, "xAxis": {"type": "value", "splitLine": {"lineStyle": {"color": "rgba(255,255,255,.06)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9}}, "yAxis": {"type": "category", "data": vp28["labels"], "axisLabel": {"color": "#cbd5e1", "fontSize": 8.5, "interval": 1, "hideOverlap": True}}, "series": [{"name": "直近20日出来高", "type": "bar", "stack": "vp28_stack", "data": vp28["short_bars"], "barMaxWidth": 9, "markLine": {"symbol": ["none", "none"], "silent": True, "data": [{"yAxis": vp28["curr_bin_idx"], "lineStyle": {"color": "#ffffff", "type": "dashed", "width": 1.6}, "label": {"formatter": "現在値", "color": "#ffffff", "fontSize": 9, "fontWeight": "bold", "position": "insideEndTop"}}]}}, {"name": "中期60日減衰", "type": "bar", "stack": "vp28_stack", "data": vp28["mid_bars"], "barMaxWidth": 9}]}, 310, chart_key=f"dd_vp28_{fc}")

            if (sq := _compute_bbw_squeeze(df_1d)).get("valid"):
                sqb = f' <span style="background:rgba(239,68,68,.22);border:1px solid #ef4444;color:#fecaca;padding:1px 6px;border-radius:99px;font-size:10px;font-weight:800;">🔥 スクイーズ警戒（BBW下位{sq["cur_pct"]}% / ブレイク前兆）</span>' if sq.get("is_squeeze") else f' <span style="color:#94a3b8;font-size:10px;">(BBWパーセンタイル {sq["cur_pct"]}% / 幅 {sq["cur_bbw"]}%)</span>'
                st.markdown(f"##### 📉 ボラティリティ・スクイーズ ＆ BBW推移（日足6ヶ月）{sqb}", unsafe_allow_html=True)
                _render_echarts({"backgroundColor": "#070b14", "tooltip": {"trigger": "axis", "backgroundColor": "rgba(7,11,20,.92)", "borderColor": "rgba(56,189,248,.45)", "textStyle": {"color": "#f8fafc", "fontSize": 10}}, "legend": {"type": "scroll", "data": ["日足終値", "20MA", "BBW順位%"], "textStyle": {"color": "#cbd5e1", "fontSize": 9.5}, "top": 2}, "axisPointer": {"link": [{"xAxisIndex": "all"}]}, "grid": [{"top": 28, "height": "52%", "left": 6, "right": 14, "containLabel": True}, {"top": "70%", "height": "20%", "left": 6, "right": 14, "containLabel": True}], "xAxis": [{"type": "category", "gridIndex": 0, "boundaryGap": False, "data": sq["dates"], "axisLabel": {"show": False}}, {"type": "category", "gridIndex": 1, "boundaryGap": False, "data": sq["dates"], "axisLabel": {"color": "#94a3b8", "fontSize": 9, "interval": "auto", "hideOverlap": True}}], "yAxis": [{"type": "value", "gridIndex": 0, "position": "right", "scale": True, "splitLine": {"lineStyle": {"color": "rgba(255,255,255,.05)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9}}, {"type": "value", "gridIndex": 1, "position": "right", "min": 0, "max": 100, "splitLine": {"show": False}, "axisLabel": {"color": "#f59e0b", "fontSize": 8, "formatter": "{value}%"}}], "series": [{"name": "bb_lo", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": sq["lower"], "stack": "bb_fan", "lineStyle": {"opacity": 0}, "showSymbol": False, "silent": True}, {"name": "BB±2σ帯", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": sq["band_diff"], "stack": "bb_fan", "lineStyle": {"opacity": 0}, "areaStyle": {"color": "rgba(99,102,241,.12)"}, "showSymbol": False, "silent": True}, {"name": "20MA", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": sq["ma20"], "itemStyle": {"color": "#c084fc"}, "lineStyle": {"color": "#c084fc", "width": 1.2, "type": "dashed"}, "showSymbol": False}, {"name": "日足終値", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": sq["closes"], "itemStyle": {"color": "#38bdf8"}, "lineStyle": {"color": "#38bdf8", "width": 2.0}, "showSymbol": False}, {"name": "BBW順位%", "type": "bar", "xAxisIndex": 1, "yAxisIndex": 1, "data": [{"value": v, "itemStyle": {"color": "#ef4444" if v <= 20 else ("#f59e0b" if v <= 45 else "rgba(56,189,248,.5)")}} for v in sq["bbw_pct_series"]], "barMaxWidth": 4}]}, 280, is_dual_grid=True, chart_key=f"dd_sq_{fc}")

            if (itx := data.get("insider_tx")) and not df_1d.empty:
                d1d, d1c = [idx.strftime("%Y-%m-%d") for idx in df_1d.index], [round(float(x), 2) for x in df_1d["Close"].values]
                pbd = dict(zip(d1d, d1c))
                bpts = [[s[5:], pbd[s]] for tx in itx if (s := str(tx.get("date") or "")[:10]) in pbd and ("PURCHASE" in str(tx.get("text") or "").upper() or "BUY" in str(tx.get("text") or "").upper())]
                spts = [[s[5:], pbd[s]] for tx in itx if (s := str(tx.get("date") or "")[:10]) in pbd and ("SALE" in str(tx.get("text") or "").upper() or "SELL" in str(tx.get("text") or "").upper())]
                if bpts or spts:
                    st.markdown("##### 🕵️ インサイダー売買プロット（日足終値上マーカー）")
                    iser = [{"name": "日足終値", "type": "line", "data": d1c, "itemStyle": {"color": "#94a3b8"}, "lineStyle": {"color": "#94a3b8", "width": 1.6}, "showSymbol": False}] + ([{"name": "役員買付▲", "type": "scatter", "symbol": "triangle", "symbolSize": 10, "itemStyle": {"color": "#10b981"}, "data": bpts}] if bpts else []) + ([{"name": "役員売却▼", "type": "scatter", "symbol": "diamond", "symbolSize": 9, "itemStyle": {"color": "#ef4444"}, "data": spts}] if spts else [])
                    _render_echarts({"backgroundColor": "#070b14", "tooltip": {"trigger": "item", "backgroundColor": "rgba(7,11,20,.92)", "textStyle": {"color": "#f8fafc", "fontSize": 10}}, "legend": {"type": "scroll", "data": [s["name"] for s in iser], "textStyle": {"color": "#cbd5e1", "fontSize": 9.5}, "top": 2}, "grid": {"top": 28, "bottom": 20, "left": 6, "right": 14, "containLabel": True}, "xAxis": {"type": "category", "data": [d[5:] for d in d1d], "axisLabel": {"color": "#94a3b8", "fontSize": 9, "interval": "auto", "hideOverlap": True}}, "yAxis": {"type": "value", "position": "right", "scale": True, "splitLine": {"lineStyle": {"color": "rgba(255,255,255,.05)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9}}, "series": iser}, 205, chart_key=f"dd_ins_{fc}")

        with t4:
            _render_echarts({"backgroundColor": "#070b14", "series": [{"type": "gauge", "startAngle": 180, "endAngle": 0, "min": 0, "max": 100, "splitNumber": 5, "center": ["50%", "74%"], "radius": "112%", "axisLine": {"lineStyle": {"width": 16, "color": [[0.2, "#dc2626"], [0.4, "#f97316"], [0.6, "#38bdf8"], [0.8, "#10b981"], [1.0, "#059669"]]}}, "pointer": {"icon": "path://M12.8,0.7l12,40.1H0.7L12.8,0.7z", "length": "52%", "width": 10, "offsetCenter": [0, "-12%"], "itemStyle": {"color": "#f8fafc", "shadowBlur": 8, "shadowColor": "rgba(56,189,248,.8)"}}, "anchor": {"show": True, "showAbove": True, "size": 14, "itemStyle": {"color": "#38bdf8", "borderWidth": 2, "borderColor": "#fff"}}, "axisTick": {"length": 6, "lineStyle": {"color": "auto", "width": 1.5}}, "splitLine": {"length": 12, "lineStyle": {"color": "auto", "width": 2.5}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9.5, "distance": -36}, "title": {"offsetCenter": [0, "18%"], "fontSize": 10.5, "color": "#7dd3fc", "fontWeight": "bold"}, "detail": {"fontSize": 26, "fontWeight": "bold", "offsetCenter": [0, "-3%"], "valueAnimation": True, "color": "#ffffff", "formatter": "{value}"}, "data": [{"value": comp_score, "name": meter_lbl}]}]}, 225, chart_key=f"dd_gg_{fc}")

            memo_nonce, top_m = st.session_state.get("dd_memo_nonce", 0), (macro_sens[0] if macro_sens else {"label": "市場指数", "corr": 0.0, "beta": 1.0})
            m_txt, m_src = _generate_detailed_memo_cached(fc, corp_name, _fmt_cur(curr_px, is_jp), _fmt_cur(active_open_px, is_jp), _fmt_cur(active_close_px, is_jp), _fmt_cur(active_bull_trig, is_jp), _fmt_cur(active_bull_tgt, is_jp), _fmt_cur(active_bear_trig, is_jp), _fmt_cur(active_bear_tgt, is_jp), active_dip_time, active_peak_time, vp["overhead_pct"], _fmt_cur(vp["res_px"], is_jp), _fmt_cur(vp["sup_px"], is_jp), top_m["label"], top_m["corr"], top_m["beta"], news_res["pos_pct"], news_res["tier1_cnt"], len(gov_risks), whale_anom["summary"], upside_str, lab_note, api_k, lab_deep_ctx, in_style, memo_nonce)
            st.markdown(f'<div class="dd-memo-box"><div style="font-size:10.5px;color:#c084fc;font-weight:800;margin-bottom:6px;">{html.escape(m_src)}</div>{html.escape(m_txt).replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
            if st.button("🔄 AIインベストメントメモを再生成", key="dd_regen_memo_btn", use_container_width=True):
                st.session_state["dd_memo_nonce"] = memo_nonce + 1; st.rerun()

            if (tl72 := _build_news_72h_timeline(news_res.get("all_72h") or news_res.get("items") or [])).get("valid"):
                st.markdown("##### 🕒 72時間ニュース密度＆センチメント推移（12時間刻み）")
                _render_echarts({"backgroundColor": "#070b14", "tooltip": {"trigger": "axis", "backgroundColor": "rgba(7,11,20,.92)", "borderColor": "rgba(56,189,248,.45)", "textStyle": {"color": "#f8fafc", "fontSize": 10}}, "legend": {"type": "scroll", "data": ["報道本数", "ネット強弱スコア"], "textStyle": {"color": "#cbd5e1", "fontSize": 9.5}, "top": 2}, "grid": {"top": 28, "bottom": 20, "left": 6, "right": 28, "containLabel": True}, "xAxis": {"type": "category", "data": tl72["labels"], "axisLabel": {"color": "#94a3b8", "fontSize": 9, "hideOverlap": True}}, "yAxis": [{"type": "value", "minInterval": 1, "splitLine": {"lineStyle": {"color": "rgba(255,255,255,.05)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9}}, {"type": "value", "position": "right", "splitLine": {"show": False}, "axisLabel": {"color": "#38bdf8", "fontSize": 8.5}}], "series": [{"name": "報道本数", "type": "bar", "yAxisIndex": 0, "data": tl72["counts"], "itemStyle": {"color": "rgba(168,85,247,.55)", "borderRadius": [3, 3, 0, 0]}, "barMaxWidth": 22}, {"name": "ネット強弱スコア", "type": "line", "yAxisIndex": 1, "data": tl72["scores"], "itemStyle": {"color": "#10b981"}, "lineStyle": {"color": "#10b981", "width": 2.0}, "symbol": "circle", "symbolSize": 6}]}, 195, chart_key=f"dd_tl72_{fc}")

            if gov_risks: st.markdown(f'<div class="dd-warn-box"><b>ガバナンス・不祥事・訴訟関連ヒット ({len(gov_risks)}件)</b><br>{"<br>".join(f"・{html.escape(x)}" for x in gov_risks)}</div>', unsafe_allow_html=True)
            else: st.markdown(f'<div class="dd-quant-box"><b>ガバナンス・不祥事監査: クリーン（{"日英" if not is_jp else "国内"}72h報道）</b><br>直近72時間以内のニュースにおいて不祥事・不正・訴訟などの特異リスクシグナルは検知されていません。</div>', unsafe_allow_html=True)

            if news_res["items"]:
                n_parts = []
                for it in news_res["items"]:
                    b_tag = '<span style="background:rgba(239,68,68,.25);color:#fecaca;font-weight:800;font-size:9px;padding:0 4px;border-radius:3px;margin-right:4px;">速報</span>' if it.get("is_breaking") else ""
                    c_tag = f'<span style="background:rgba(250,204,21,.2);color:#fde047;font-weight:800;font-size:9px;padding:0 4px;border-radius:3px;margin-right:4px;">材料:{html.escape(it["catalyst_kw"])}</span>' if it.get("catalyst_kw") else ""
                    tc = "#fde047" if it["trust"] == "S" else ("#38bdf8" if it["trust"] == "A" else "#64748b")
                    sc = "#10b981" if it["sent"] == "POS" else ("#ef4444" if it["sent"] == "NEG" else "#94a3b8")
                    n_parts.append(f'<div style="margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid rgba(148,163,184,.12);">{b_tag}{c_tag}<span style="color:{tc};font-weight:800;font-size:10px;border:1px solid;padding:0 4px;border-radius:3px;margin-right:4px;">信頼度{it["trust"]}/{it["lang"]}</span><span style="color:{sc};font-weight:800;font-size:10px;margin-right:4px;">[{it["sent"]}]</span><span style="color:#94a3b8;font-size:9.5px;margin-right:4px;">(鮮度重み {it["decay_w"]:.1f})</span><a href="{html.escape(it["link"])}" target="_blank" style="color:#e2e8f0;text-decoration:none;font-weight:600;">{html.escape(it["title"])}</a> <span style="color:#64748b;font-size:10px;">({html.escape(it["source"] or "Wire")} / {html.escape(it["pub"])})</span></div>')
                st.markdown(f'<div class="dd-dark-box"><b>GLOBAL INTELLIGENCE FEED // 日英高信頼ニュース（有効報道 {news_res["fresh_cnt"]}件 / 一次 {news_res["tier1_cnt"]}件）</b><br><br>{"".join(n_parts)}</div>', unsafe_allow_html=True)

            wed = traj["weights_evolution"]; dbr = _make_default_brain(wed["active_regime"])
            og_k, idr_k = ["macro", "fx", "news", "whale", "lab_bias"], ["news", "dow", "wick", "calib", "lab_bias"]
            st.markdown(f"##### 🧠 クオンツ自己進化監査（{html.escape(wed['active_cluster'])}・{wed['active_regime']}脳 / 累計更新 {wed['updates_count']}回）")
            _render_echarts({"backgroundColor": "#070b14", "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}, "backgroundColor": "rgba(7,11,20,.92)", "textStyle": {"color": "#f8fafc", "fontSize": 10}}, "legend": {"type": "scroll", "data": ["初期事前重み", "現在学習重み"], "textStyle": {"color": "#cbd5e1", "fontSize": 9.5}, "top": 2}, "grid": {"top": 28, "bottom": 22, "left": 6, "right": 14, "containLabel": True}, "xAxis": {"type": "category", "data": ["始値:マクロ", "始値:為替", "始値:ニュース", "始値:大口", "始値:LAB", "日中:ニュース×100", "日中:曜日", "日中:ヒゲ", "日中:校正", "日中:LAB"], "axisLabel": {"color": "#94a3b8", "fontSize": 8.5, "interval": 0, "rotate": 30, "hideOverlap": True}}, "yAxis": {"type": "value", "splitLine": {"lineStyle": {"color": "rgba(255,255,255,.05)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9}}, "series": [{"name": "初期事前重み", "type": "bar", "data": [round(float(dbr["open_gap"][k]), 3) for k in og_k] + [round(float(dbr["intraday_drift"][k]) * (100.0 if k == "news" else 1.0), 3) for k in idr_k], "itemStyle": {"color": "rgba(148,163,184,.45)"}, "barMaxWidth": 12}, {"name": "現在学習重み", "type": "bar", "data": [round(float(wed["open_gap"].get(k, dbr["open_gap"][k])), 3) for k in og_k] + [round(float(wed["intraday_drift"].get(k, dbr["intraday_drift"][k])) * (100.0 if k == "news" else 1.0), 3) for k in idr_k], "itemStyle": {"color": "#38bdf8"}, "barMaxWidth": 12}]}, 225, chart_key=f"dd_sgd_{fc}")

            if len(vh := traj.get("verify_hist_15") or []) >= 3:
                st.markdown("##### 📊 直近15日・大引け確定ロック検証推移（収束率% vs 平均誤差%）")
                _render_echarts({"backgroundColor": "#070b14", "tooltip": {"trigger": "axis", "backgroundColor": "rgba(7,11,20,.92)", "textStyle": {"color": "#f8fafc", "fontSize": 10}}, "legend": {"type": "scroll", "data": ["帯内収束率%", "平均誤差%"], "textStyle": {"color": "#cbd5e1", "fontSize": 9.5}, "top": 2}, "grid": {"top": 28, "bottom": 20, "left": 6, "right": 28, "containLabel": True}, "xAxis": {"type": "category", "data": [f"{r['date'][5:]}({r['code']})" for r in vh], "axisLabel": {"color": "#94a3b8", "fontSize": 8.5, "interval": "auto", "hideOverlap": True}}, "yAxis": [{"type": "value", "min": 0, "max": 100, "splitLine": {"lineStyle": {"color": "rgba(255,255,255,.05)"}}, "axisLabel": {"color": "#10b981", "fontSize": 9, "formatter": "{value}%"}}, {"type": "value", "position": "right", "splitLine": {"show": False}, "axisLabel": {"color": "#f59e0b", "fontSize": 8.5, "formatter": "{value}%"}}], "series": [{"name": "帯内収束率%", "type": "bar", "yAxisIndex": 0, "data": [r["cone"] for r in vh], "itemStyle": {"color": "rgba(16,185,129,.55)", "borderRadius": [3, 3, 0, 0]}, "barMaxWidth": 16}, {"name": "平均誤差%", "type": "line", "yAxisIndex": 1, "data": [r["err"] for r in vh], "itemStyle": {"color": "#f59e0b"}, "lineStyle": {"color": "#f59e0b", "width": 2.0}, "symbol": "circle", "symbolSize": 6}]}, 205, chart_key=f"dd_vh_{fc}")
            else:
                st.markdown(f'<div class="dd-dark-box" style="padding:8px 10px;font-size:11px;"><b>📊 日次検証推移:</b> 大引け確定済みロック検証データ蓄積中（現在 {len(vh)}件 / 3件以上で推移グラフを表示）</div>', unsafe_allow_html=True)

        ma_d = traj.get("medoid_analog") if isinstance(traj.get("medoid_analog"), dict) else {}
        dd_result = {
            "full_code": fc, "style": in_style, "comp_score": int(comp_score), "meter_lbl": str(meter_lbl), "mkt_regime": mkt_regime, "expansion_regime": exp_reg, "mtf_alignment": mtf_res, "pro_ref_levels": ref_levels,
            "fusion_score": float(fusion["fusion_score"]) if fusion.get("has_lab") else float(comp_score), "sync_state": str(fusion["sync_state"]) if fusion.get("has_lab") else "単体解析",
            "fusion_entry_px": float(fusion["fusion_entry_px"]) if fusion.get("has_lab") else float(active_dip_px), "fusion_half_r_px": float(fusion["fusion_half_r_px"]) if fusion.get("has_lab") else float(curr_px),
            "fusion_tp_px": float(fusion["fusion_tp_px"]) if fusion.get("has_lab") else float(active_bull_tgt), "fusion_sl_px": float(fusion["fusion_sl_px"]) if fusion.get("has_lab") else float(active_bear_trig),
            "est_open_px": float(active_open_px), "est_open_gap_pct": float(active_open_gap_pct), "est_close_px": float(active_close_px), "est_close_chg": float(active_close_chg),
            "bull_trig": float(active_bull_trig), "bull_target": float(active_bull_tgt), "bear_trig": float(active_bear_trig), "bear_target": float(active_bear_tgt),
            "dip_time": str(active_dip_time), "dip_px": float(active_dip_px), "peak_time": str(active_peak_time), "peak_px": float(active_peak_px), "scenario_probs": scen_probs,
            "short_horizon_3way": {"active": short_3way["active"], "horizon_min": short_3way["horizon"] * 5, "p_up": short_3way["p_up"], "p_flat": short_3way["p_flat"], "p_down": short_3way["p_down"], "ml_used": short_3way.get("ml_used", False), "ml_samples": short_3way.get("ml_samples", 0)},
            "meta_audit": meta_a, "rvol": traj["rvol"], "gap_fill": traj["gap_fill"], "gap_open15": traj["gap_open15"], "cvd_div": traj["cvd_div"], "round_level": float(round_level),
            "orb_high": traj["orb_high"], "orb_low": traj["orb_low"], "vol_spikes_cnt": len(traj["vol_spikes"]), "whale_anom": whale_anom, "gov_risks_cnt": len(gov_risks),
            "overhead_pct": float(vp["overhead_pct"]), "res_px": float(vp["res_px"]), "sup_px": float(vp["sup_px"]), "verify": traj["verify"], "vol_clock_active": traj.get("vol_clock_active", False),
            "lunch_jump_std_pct": traj.get("lunch_jump_std_pct", 0.0), "lunch_gap_adj_pct": traj.get("lunch_gap_adj_pct", 0.0), "lab_mods": traj.get("lab_mods", {}),
            "medoid_analog": {"date": ma_d.get("date"), "gap_pct": ma_d.get("gap_pct"), "amp_scale": ma_d.get("amp_scale", 1.0) if ma_d else None, "mode": ma_d.get("mode")},
            "vol_profile_meta": traj["vol_profile_meta"], "knn_match": {"matched_dates": traj["knn_match"]["matched_dates"], "mean_dist": traj["knn_match"]["mean_dist"]}, "invalidation_alert": inv_al,
            "weights_evolution": {"active_cluster": we["active_cluster"], "active_regime": we["active_regime"], "updates_count": we["updates_count"], "regime_updates_count": we["regime_updates_count"], "last_decomp": we["last_decomp"]},
            "verdict": f"{meter_lbl} (スコア{comp_score} / 想定大引け{active_close_chg:+.2f}% / {mkt_regime['label']} / 信頼度{meta_a['rank']})",
            "summary": m_txt[:450], "dd_score": int(comp_score), "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        st.session_state["dd_latest_result"] = dd_result
        db_shared = _dd_db_get("shared_ticker_intel", {})
        if not isinstance(db_shared, dict): db_shared = {}
        ss_shared = st.session_state.get("shared_ticker_intel")
        if isinstance(ss_shared, dict): db_shared.update(ss_shared)
        entry_obj = db_shared.get(fc) if isinstance(db_shared.get(fc), dict) else {}
        entry_obj["dd_result"] = dd_result
        entry_obj["dd_updated_at"] = dd_result["updated_at"]
        db_shared[fc] = entry_obj
        st.session_state["shared_ticker_intel"] = db_shared
        _dd_db_set("shared_ticker_intel", db_shared)

    if hasattr(st, "fragment"):
        @st.fragment(run_every="60s" if auto_sync else None)
        def _auto_runner():
            _body()
        _auto_runner()
    else:
        _body()
