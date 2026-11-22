import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np
import math
import os
import re
import ssl
import html
import json
import time
import sqlite3
import datetime
import email.utils
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

DB_PATH = "yamashishi_core.db"
WEIGHTS_EVOLUTION_PATH = "weights_evolution_v4.json"
WEIGHTS_KV_KEY = "dd_weights_evolution_v4"

CLUSTER_KEYS = [
    "JP_LOW", "JP_MID", "JP_HIGH",
    "US_LOW", "US_MID", "US_HIGH",
    "JP_ALL", "US_ALL",
]


def _make_default_brain(regime_code: str) -> dict:
    if regime_code == "TREND":
        return {
            "updates_count": 0,
            "open_gap": {
                "macro": 0.50,
                "fx": 0.35,
                "news": 0.95,
                "whale": 1.10,
                "lab_bias": 0.45,
            },
            "intraday_drift": {
                "news": 0.006,
                "dow": 0.30,
                "wick": 0.65,
                "calib": 0.40,
                "lab_bias": 0.95,
            },
        }
    if regime_code == "RANGE":
        return {
            "updates_count": 0,
            "open_gap": {
                "macro": 0.35,
                "fx": 0.30,
                "news": 0.70,
                "whale": 0.90,
                "lab_bias": 0.25,
            },
            "intraday_drift": {
                "news": 0.004,
                "dow": 0.40,
                "wick": 0.95,
                "calib": 0.45,
                "lab_bias": 0.60,
            },
        }
    return {
        "updates_count": 0,
        "open_gap": {
            "macro": 0.45,
            "fx": 0.35,
            "news": 0.85,
            "whale": 1.00,
            "lab_bias": 0.35,
        },
        "intraday_drift": {
            "news": 0.005,
            "dow": 0.35,
            "wick": 0.80,
            "calib": 0.40,
            "lab_bias": 0.80,
        },
    }


def _make_default_regime_set() -> dict:
    return {
        "TREND": _make_default_brain("TREND"),
        "RANGE": _make_default_brain("RANGE"),
        "NEUTRAL": _make_default_brain("NEUTRAL"),
    }


DEFAULT_WEIGHTS_EVOLUTION = {
    "version": 4,
    "lr": 0.035,
    "l2_decay": 0.015,
    "updates_count": 0,
    "last_updated": "",
    "learned_keys": [],
    "clusters": {ck: _make_default_regime_set() for ck in CLUSTER_KEYS},
    "regimes": _make_default_regime_set(),
    "last_decomp": {
        "date": "-",
        "code": "-",
        "cluster": "US_MID",
        "regime": "NEUTRAL",
        "open_err_pct": 0.0,
        "intraday_err_pct": 0.0,
        "culprit_open": "-",
        "culprit_intra": "-",
    },
}


# =========================================================================
# 1. DEEP DIVE v14 専用CSS
# =========================================================================
def _inject_dd_css():
    css = """
    [data-stale="true"] { opacity: 1 !important; transition: none !important; }
    .dd-macro-strip {
        display: flex; flex-wrap: nowrap; overflow-x: auto; gap: 6px;
        padding: 3px 0 5px 0; margin-bottom: 4px; scrollbar-width: none;
    }
    .dd-macro-strip::-webkit-scrollbar { display: none; }
    .dd-macro-chip {
        flex-shrink: 0; background: rgba(15, 23, 42, 0.9);
        border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 6px;
        padding: 3px 8px; font-family: 'JetBrains Mono', monospace;
        font-size: 10.5px; display: inline-flex; align-items: center; gap: 5px;
    }
    .dd-status-strip {
        display: flex; flex-wrap: nowrap; overflow-x: auto; gap: 6px;
        padding: 2px 0 6px 0; scrollbar-width: none;
    }
    .dd-status-strip::-webkit-scrollbar { display: none; }
    .dd-st-pill {
        flex-shrink: 0; font-size: 10.5px; font-weight: 700;
        padding: 3px 9px; border-radius: 99px; border: 1px solid;
        display: inline-flex; align-items: center; gap: 4px;
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
    .dd-sc-bar-bg { width: 100%; height: 5px; background: rgba(148, 163, 184, 0.16); border-radius: 99px; margin-top: 8px; overflow: hidden; }
    .dd-sc-bar-fill { height: 100%; border-radius: 99px; transition: width 0.3s ease; }
    .dd-prob-meter {
        background: rgba(15, 23, 42, 0.92); border: 1px solid rgba(56, 189, 248, 0.25);
        border-radius: 10px; padding: 9px 11px; margin: 6px 0 8px 0;
    }
    .dd-prob-stack {
        display: flex; width: 100%; height: 10px; border-radius: 99px;
        overflow: hidden; background: rgba(15, 23, 42, 0.95); margin: 6px 0 7px 0;
        border: 1px solid rgba(148, 163, 184, 0.22);
    }
    .dd-prob-legend {
        display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px;
        font-family: 'JetBrains Mono', monospace; font-size: 10px; text-align: center;
    }
    @media (max-width: 640px) { .dd-prob-legend { grid-template-columns: repeat(2, 1fr); } }
    .dd-dow-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 5px; margin-top: 6px; }
    .dd-dow-cell { background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(148, 163, 184, 0.18); border-radius: 7px; padding: 6px 4px; text-align: center; }
    .dd-dark-box { background: rgba(15, 23, 42, 0.88); border: 1px solid rgba(148, 163, 184, 0.18); padding: 11px 12px; border-radius: 10px; margin-bottom: 8px; font-size: 12px; line-height: 1.65; color: #cbd5e1; }
    .dd-warn-box { background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.4); border-left: 4px solid #ef4444; padding: 10px 12px; border-radius: 10px; margin-bottom: 8px; font-size: 12px; line-height: 1.6; color: #fecaca; }
    .dd-quant-box { background: rgba(16, 185, 129, 0.10); border: 1px solid rgba(16, 185, 129, 0.35); border-left: 4px solid #10b981; padding: 10px 12px; border-radius: 10px; margin-bottom: 8px; font-size: 12px; line-height: 1.6; color: #d1fae5; }
    .dd-sync-warn { background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.42); border-left: 4px solid #f59e0b; padding: 10px 12px; border-radius: 10px; margin-bottom: 8px; font-size: 12px; line-height: 1.6; color: #fef3c7; }
    .dd-guide-box { background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.28); border-left: 3px solid #38bdf8; padding: 10px 12px; border-radius: 8px; font-size: 11.5px; line-height: 1.65; color: #e0f2fe; }
    .dd-memo-box { background: linear-gradient(180deg, #0b192c 0%, #090d16 100%); border: 1px solid rgba(168, 85, 247, 0.45); border-left: 4px solid #a855f7; padding: 13px 15px; border-radius: 10px; margin-bottom: 10px; font-size: 12.2px; line-height: 1.78; color: #f1f5f9; }
    .dd-factor-row { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 5px 0; border-bottom: 1px solid rgba(148, 163, 184, 0.12); font-size: 11.5px; }
    .dd-factor-row:last-child { border-bottom: none; padding-top: 7px; font-weight: 800; }
    .dd-inst-strip { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-bottom: 8px; }
    @media (max-width: 640px) { .dd-inst-strip { grid-template-columns: repeat(2, 1fr); } }
    .dd-inst-card { background: rgba(15, 23, 42, 0.92); border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 8px; padding: 6px 7px; text-align: center; }
    .dd-ev-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-top: 8px; }
    .dd-ev-cell { background: rgba(9, 13, 22, 0.85); border: 1px solid rgba(56, 189, 248, 0.22); border-radius: 7px; padding: 7px 5px; text-align: center; }
    """
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# =========================================================================
# 2. SQLite ＆ Supabase 予測スナップショット台帳 ＆ 市場現地時刻ヘルパー
# =========================================================================
def _dd_safe_secret(k: str) -> str:
    try:
        v = os.environ.get(k, "")
        if v:
            return str(v).strip()
    except Exception:
        pass
    try:
        v = st.secrets.get(k, "")
        if v:
            return str(v).strip()
    except Exception:
        pass
    return ""


def _dd_sb_headers(sb_key: str) -> dict:
    return {
        "apikey": sb_key,
        "Authorization": f"Bearer {sb_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }


def _dd_sb_get(key: str):
    sb_url = _dd_safe_secret("SUPABASE_URL").rstrip("/")
    sb_key = _dd_safe_secret("SUPABASE_KEY")
    if not sb_url or not sb_key:
        return None
    try:
        q = f"{sb_url}/rest/v1/kv_store?key=eq.{urllib.parse.quote(key)}&select=val"
        req = urllib.request.Request(q, headers=_dd_sb_headers(sb_key), method="GET")
        with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=4.0) as r:
            rows = json.loads(r.read().decode("utf-8"))
            if isinstance(rows, list) and rows and rows[0].get("val") is not None:
                raw_val = rows[0]["val"]
                return json.loads(raw_val) if isinstance(raw_val, str) else raw_val
    except Exception:
        pass
    return None


def _dd_sb_set(key: str, val) -> None:
    sb_url = _dd_safe_secret("SUPABASE_URL").rstrip("/")
    sb_key = _dd_safe_secret("SUPABASE_KEY")
    if not sb_url or not sb_key:
        return
    try:
        url = f"{sb_url}/rest/v1/kv_store?on_conflict=key"
        payload = json.dumps({
            "key": key,
            "val": json.dumps(val, ensure_ascii=False),
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=_dd_sb_headers(sb_key), method="POST")
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
        cur.execute(
            "INSERT INTO kv_store (key, val, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(key) DO UPDATE SET val=excluded.val, updated_at=CURRENT_TIMESTAMP;",
            (key, json.dumps(val, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass
    _dd_sb_set(key, val)


def _get_market_now(is_jp: bool) -> datetime.datetime:
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


def _convert_5m_index_to_market_tz(df_5m: pd.DataFrame, is_jp: bool) -> pd.DatetimeIndex:
    """df_5mのインデックスを必ず市場タイムゾーン（Asia/Tokyo / America/New_York）へ変換"""
    idx = pd.to_datetime(df_5m.index)
    target_tz_name = "Asia/Tokyo" if is_jp else "America/New_York"
    if ZoneInfo is not None:
        tz_target = ZoneInfo(target_tz_name)
        if idx.tz is None:
            idx = idx.tz_localize(tz_target, ambiguous="NaT", nonexistent="shift_forward")
        else:
            idx = idx.tz_convert(tz_target)
        return idx.tz_localize(None)
    if idx.tz is not None:
        offset_h = 9 if is_jp else -5
        idx = idx.tz_convert(datetime.timezone(datetime.timedelta(hours=offset_h))).tz_localize(None)
    return idx


# =========================================================================
# クラスタ別（市場JP/US × ボラティリティ帯LOW/MID/HIGH）3脳SGD・標準化リッジ回帰
# =========================================================================
def _classify_vol_cluster(df_1d: pd.DataFrame, is_jp: bool) -> dict:
    mkt_prefix = "JP" if is_jp else "US"
    if df_1d is None or len(df_1d) < 15:
        return {"cluster": f"{mkt_prefix}_MID", "fallback": f"{mkt_prefix}_ALL", "vol_band": "MID", "atr_pct": 2.0}
    hi = df_1d["High"].values[-15:]
    lo = df_1d["Low"].values[-15:]
    cl = df_1d["Close"].values[-15:]
    prev_c = np.roll(cl, 1)
    prev_c[0] = cl[0]
    tr = np.maximum(hi - lo, np.maximum(np.abs(hi - prev_c), np.abs(lo - prev_c)))
    atr_pct = float(np.mean(tr[-14:] / np.maximum(cl[-14:], 1e-4)) * 100.0)
    if atr_pct < 1.6:
        band = "LOW"
    elif atr_pct > 3.2:
        band = "HIGH"
    else:
        band = "MID"
    return {
        "cluster": f"{mkt_prefix}_{band}",
        "fallback": f"{mkt_prefix}_ALL",
        "vol_band": band,
        "atr_pct": round(atr_pct, 2),
    }


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
        rc = raw_clusters.get(ck)
        if isinstance(rc, dict):
            for r_code in ("TREND", "RANGE", "NEUTRAL"):
                rb = rc.get(r_code)
                if isinstance(rb, dict):
                    if "updates_count" in rb:
                        base["clusters"][ck][r_code]["updates_count"] = int(rb["updates_count"])
                    if isinstance(rb.get("open_gap"), dict):
                        for gk, gv in rb["open_gap"].items():
                            if gk in base["clusters"][ck][r_code]["open_gap"]:
                                base["clusters"][ck][r_code]["open_gap"][gk] = float(gv)
                    if isinstance(rb.get("intraday_drift"), dict):
                        for ik, iv in rb["intraday_drift"].items():
                            if ik in base["clusters"][ck][r_code]["intraday_drift"]:
                                base["clusters"][ck][r_code]["intraday_drift"][ik] = float(iv)

    raw_regimes = raw.get("regimes") if isinstance(raw.get("regimes"), dict) else {}
    for r_code in ("TREND", "RANGE", "NEUTRAL"):
        rb = raw_regimes.get(r_code)
        if isinstance(rb, dict):
            if "updates_count" in rb:
                base["regimes"][r_code]["updates_count"] = int(rb["updates_count"])
            if isinstance(rb.get("open_gap"), dict):
                for gk, gv in rb["open_gap"].items():
                    if gk in base["regimes"][r_code]["open_gap"]:
                        base["regimes"][r_code]["open_gap"][gk] = float(gv)
            if isinstance(rb.get("intraday_drift"), dict):
                for ik, iv in rb["intraday_drift"].items():
                    if ik in base["regimes"][r_code]["intraday_drift"]:
                        base["regimes"][r_code]["intraday_drift"][ik] = float(iv)

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
    if isinstance(db_val, dict) and db_val:
        return _merge_default_weights(db_val)

    return json.loads(json.dumps(DEFAULT_WEIGHTS_EVOLUTION))


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
    """サンプル不足時は市場共通事前分布へシュリンク（経験ベイズ平滑化）"""
    c_brain = w_evo["clusters"].get(cluster_key, _make_default_regime_set()).get(regime_code, _make_default_brain(regime_code))
    f_brain = w_evo["clusters"].get(fallback_key, _make_default_regime_set()).get(regime_code, _make_default_brain(regime_code))
    n_c = int(c_brain.get("updates_count", 0))
    alpha = float(np.clip(n_c / (n_c + 8.0), 0.0, 1.0))

    blended_og = {}
    for gk, f_val in f_brain["open_gap"].items():
        c_val = float(c_brain["open_gap"].get(gk, f_val))
        blended_og[gk] = round(alpha * c_val + (1.0 - alpha) * float(f_val), 4)

    blended_idr = {}
    for ik, f_val in f_brain["intraday_drift"].items():
        c_val = float(c_brain["intraday_drift"].get(ik, f_val))
        blended_idr[ik] = round(alpha * c_val + (1.0 - alpha) * float(f_val), 5 if ik == "news" else 4)

    return blended_og, blended_idr, n_c, round(alpha, 2)


def _detect_market_regime(df_1d: pd.DataFrame) -> dict:
    if df_1d is None or len(df_1d) < 25:
        return {"code": "NEUTRAL", "label": "判定不能", "strategy": "標準", "color": "#94a3b8", "er": 0.0}
    c = df_1d["Close"].values
    diff_net = abs(c[-1] - c[-15])
    diff_sum = float(np.sum(np.abs(np.diff(c[-15:]))))
    er = diff_net / max(diff_sum, 1e-4)
    ma20 = float(np.mean(c[-20:]))
    std20 = float(np.std(c[-20:]))
    bbw = (std20 * 4.0) / max(ma20, 1e-4) * 100.0
    if er >= 0.38 or bbw >= 14.0:
        return {"code": "TREND", "label": "トレンド相場", "strategy": "順張り優位", "color": "#10b981", "er": round(er, 2)}
    if er <= 0.18 and bbw <= 9.0:
        return {"code": "RANGE", "label": "レンジ相場", "strategy": "逆張り優位", "color": "#f59e0b", "er": round(er, 2)}
    return {"code": "NEUTRAL", "label": "移行・中立", "strategy": "押し目待ち", "color": "#38bdf8", "er": round(er, 2)}


def _update_weights_two_stage(
    w_evo: dict, fc_code: str, df_1d: pd.DataFrame, stock_hist: dict,
    market_today_str: str, cluster_key: str, fallback_key: str
) -> tuple:
    """クラスタ別＋特徴量標準化＋L2正則化（リッジ減衰）＋abs最大犯人特定型SGD"""
    updated = _merge_default_weights(w_evo)
    if not isinstance(stock_hist, dict) or df_1d is None or df_1d.empty:
        return updated, False
    if not {"Open", "Close"}.issubset(set(df_1d.columns)):
        return updated, False

    rows_1d = []
    for idx, r_d in df_1d.iterrows():
        d_s = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
        op_v, cl_v = float(r_d["Open"]), float(r_d["Close"])
        if op_v > 0 and cl_v > 0:
            rows_1d.append((d_s, op_v, cl_v))
    if len(rows_1d) < 2:
        return updated, False

    day_map = {d_s: (op_v, cl_v) for d_s, op_v, cl_v in rows_1d}
    prev_close_map = {rows_1d[i][0]: rows_1d[i - 1][2] for i in range(1, len(rows_1d))}
    idx_pos_map = {rows_1d[i][0]: i for i in range(len(rows_1d))}

    learned_set = set(updated.get("learned_keys", []))
    lr = float(np.clip(updated.get("lr", 0.035), 0.005, 0.15))
    l2_decay = float(np.clip(updated.get("l2_decay", 0.015), 0.001, 0.08))

    og_bounds = {"macro": (0.15, 1.20), "fx": (0.10, 0.90), "news": (0.20, 1.80), "whale": (0.20, 2.00), "lab_bias": (0.05, 1.00)}
    idr_bounds = {"news": (0.001, 0.015), "dow": (0.05, 0.90), "wick": (0.20, 1.60), "calib": (0.05, 1.00), "lab_bias": (0.10, 1.60)}

    # 特徴量標準化用スケール
    og_scales = {"macro": 1.2, "fx": 0.8, "news": 0.5, "whale": 0.35, "lab_bias": 0.6}
    idr_scales = {"news": 0.5, "dow": 0.35, "wick": 0.30, "calib": 0.35, "lab_bias": 0.6}

    changed = False
    for dt_k in sorted(stock_hist.keys()):
        if dt_k >= market_today_str:
            continue
        learn_id = f"{fc_code}:{dt_k}"
        if learn_id in learned_set:
            continue
        if dt_k not in day_map or dt_k not in prev_close_map:
            continue

        snap = stock_hist[dt_k]
        if snap.get("locked_premarket") is False:
            continue

        p50_arr = snap.get("p50") or []
        if not p50_arr:
            continue

        r_code = str(snap.get("regime_code") or "").upper()
        if r_code not in ("TREND", "RANGE", "NEUTRAL"):
            pos = idx_pos_map.get(dt_k, 0)
            r_code = _detect_market_regime(df_1d.iloc[:pos])["code"] if pos >= 25 else "NEUTRAL"

        snap_cluster = str(snap.get("cluster_key") or cluster_key)
        if snap_cluster not in updated["clusters"]:
            snap_cluster = cluster_key

        def_brain = _make_default_brain(r_code)
        target_brains = [
            updated["clusters"][snap_cluster][r_code],
            updated["clusters"][fallback_key][r_code],
            updated["regimes"][r_code],
        ]

        act_open, act_close = day_map[dt_k]
        prev_close = prev_close_map[dt_k]
        pred_open = float(snap.get("pred_open_px") or p50_arr[0] or act_open)
        pred_close = float(p50_arr[-1] or act_close)
        if pred_open <= 0 or pred_close <= 0:
            continue

        act_gap_pct = ((act_open - prev_close) / max(prev_close, 1e-4)) * 100.0
        pred_gap_pct = float(snap["pred_open_gap_pct"]) if snap.get("pred_open_gap_pct") is not None else (((pred_open - prev_close) / max(prev_close, 1e-4)) * 100.0)
        open_err_pct = float(np.clip(act_gap_pct - pred_gap_pct, -6.0, 6.0))

        act_intra_pct = ((act_close - act_open) / max(act_open, 1e-4)) * 100.0
        pred_intra_pct = ((pred_close - pred_open) / max(pred_open, 1e-4)) * 100.0
        intraday_err_pct = float(np.clip(act_intra_pct - pred_intra_pct, -6.0, 6.0))

        fc_saved = snap.get("factor_contribs") if isinstance(snap.get("factor_contribs"), dict) else {}
        og_x = fc_saved.get("open_gap") if isinstance(fc_saved.get("open_gap"), dict) else {}
        idr_x = fc_saved.get("intraday_drift") if isinstance(fc_saved.get("intraday_drift"), dict) else {}

        culprit_open = "-"
        if og_x:
            std_og = {gk: float(og_x.get(gk, 0.0)) / og_scales[gk] for gk in og_bounds}
            norm_o = sum(v ** 2 for v in std_og.values()) + 0.50
            max_abs_o, worst_o, worst_o_k = 0.0, 0.0, "-"
            for gk, (b_lo, b_hi) in og_bounds.items():
                xv_std = std_og[gk]
                if abs(xv_std) < 1e-5:
                    continue
                grad_step = lr * open_err_pct * (xv_std / norm_o)
                for b_idx, br in enumerate(target_brains):
                    w_lr_mult = 1.0 if b_idx == 0 else 0.5
                    cur_w = br["open_gap"][gk]
                    prior_w = def_brain["open_gap"][gk]
                    l2_pull = -l2_decay * (cur_w - prior_w)
                    delta = float(np.clip(grad_step * w_lr_mult + l2_pull, -0.055, 0.055))
                    br["open_gap"][gk] = round(float(np.clip(cur_w + delta, b_lo, b_hi)), 4)
                    if b_idx == 0 and abs(delta) > max_abs_o:
                        max_abs_o, worst_o, worst_o_k = abs(delta), delta, gk
            if worst_o_k != "-":
                dir_tag = "過大" if worst_o < 0 else "過小"
                culprit_open = f"{worst_o_k}[{dir_tag}]({worst_o:+.3f})"

        culprit_intra = "-"
        if idr_x:
            std_idr = {ik: float(idr_x.get(ik, 0.0)) / idr_scales[ik] for ik in idr_bounds}
            norm_i = sum(v ** 2 for v in std_idr.values()) + 0.50
            max_abs_i, worst_i, worst_i_k = 0.0, 0.0, "-"
            for ik, (b_lo, b_hi) in idr_bounds.items():
                xv_std = std_idr[ik]
                if abs(xv_std) < 1e-5:
                    continue
                scale_i = 0.004 if ik == "news" else 1.0
                grad_step = lr * intraday_err_pct * (xv_std / norm_i) * scale_i
                for b_idx, br in enumerate(target_brains):
                    w_lr_mult = 1.0 if b_idx == 0 else 0.5
                    cur_w = br["intraday_drift"][ik]
                    prior_w = def_brain["intraday_drift"][ik]
                    l2_pull = -l2_decay * (cur_w - prior_w)
                    delta = float(np.clip(grad_step * w_lr_mult + l2_pull, -0.055 * scale_i, 0.055 * scale_i))
                    br["intraday_drift"][ik] = round(float(np.clip(cur_w + delta, b_lo, b_hi)), 5 if ik == "news" else 4)
                    norm_delta = abs(delta) / scale_i
                    if b_idx == 0 and norm_delta > max_abs_i:
                        max_abs_i, worst_i, worst_i_k = norm_delta, (delta / scale_i), ik
            if worst_i_k != "-":
                dir_tag = "過大" if worst_i < 0 else "過小"
                culprit_intra = f"{worst_i_k}[{dir_tag}]({worst_i:+.3f})"

        for br in target_brains:
            br["updates_count"] = int(br.get("updates_count", 0)) + 1

        updated["last_decomp"] = {
            "date": dt_k,
            "code": fc_code,
            "cluster": snap_cluster,
            "regime": r_code,
            "open_err_pct": round(open_err_pct, 3),
            "intraday_err_pct": round(intraday_err_pct, 3),
            "culprit_open": culprit_open,
            "culprit_intra": culprit_intra,
        }
        updated["updates_count"] = int(updated.get("updates_count", 0)) + 1
        learned_set.add(learn_id)
        changed = True

    if changed:
        updated["learned_keys"] = sorted(learned_set)[-400:]
        _save_weights_evolution(updated)

    return updated, changed


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


def _norm_cdf(x: float) -> float:
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def _calc_first_passage_prob(curr_px: float, target_px: float, rem_sigma_pct: float, rem_drift_pct: float = 0.0) -> float:
    """ドリフト付きブラウン運動の初回到達確率（U字型ボラティリティ積分σ対応）"""
    if curr_px <= 0 or target_px <= 0:
        return 0.0
    raw_dist = (target_px - curr_px) / curr_px
    if abs(raw_dist) <= 1e-6:
        return 99.0
    if raw_dist > 0:
        b = raw_dist
        mu_t = rem_drift_pct
    else:
        b = -raw_dist
        mu_t = -rem_drift_pct

    sig_t = max(rem_sigma_pct, 1e-4)
    term1 = _norm_cdf((-b + mu_t) / sig_t)
    exp_arg = min((2.0 * mu_t * b) / (sig_t ** 2), 50.0)
    term2 = math.exp(exp_arg) * _norm_cdf((-b - mu_t) / sig_t)
    prob = (term1 + term2) * 100.0
    return round(float(np.clip(prob, 1.0, 99.0)), 1)


def _render_echarts(
    option_dict: dict,
    height: int = 300,
    use_hud_tooltip: bool = False,
    is_jp: bool = False,
    enable_fullscreen: bool = False,
):
    opt_json = json.dumps(option_dict, ensure_ascii=False)
    hud_js = f"""
    if ({'true' if use_hud_tooltip else 'false'}) {{
        opt.tooltip = {{
            trigger: 'axis',
            backgroundColor: 'rgba(9, 13, 22, 0.90)',
            borderColor: 'rgba(56, 189, 248, 0.45)',
            borderWidth: 1,
            padding: [4, 8],
            extraCssText: 'white-space: normal; max-width: 90%; line-height: 1.35;',
            textStyle: {{ color: '#f8fafc', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }},
            position: function() {{ return [6, 26]; }},
            axisPointer: {{
                type: 'cross',
                lineStyle: {{ color: 'rgba(56, 189, 248, 0.55)', type: 'dashed', width: 1 }},
                crossStyle: {{ color: 'rgba(56, 189, 248, 0.35)' }},
                label: {{ backgroundColor: '#0f172a', borderColor: '#38bdf8', borderWidth: 1, fontSize: 9 }}
            }},
            formatter: function(params) {{
                if (!params || !params.length) return '';
                var tm = params[0].axisValue;
                var parts = ['<span style="color:#7dd3fc;font-weight:800;">' + tm + '</span>'];
                var shortMap = {{'当日実測':'実測', 'ライブ修正':'ライブ', '朝ロック':'ロック', 'VWAP':'VWAP'}};
                for (var i = 0; i < params.length; i++) {{
                    var p = params[i];
                    if (shortMap[p.seriesName] && p.value !== null && p.value !== undefined) {{
                        var v = Number(p.value);
                        var vs = {'true' if is_jp else 'false'} ? Math.round(v).toLocaleString() + '円' : '$' + v.toFixed(2);
                        parts.push('<span style="color:' + p.color + ';">●</span>' + shortMap[p.seriesName] + ':<b>' + vs + '</b>');
                    }}
                }}
                return parts.join(' ');
            }}
        }};
    }}
    """
    fs_btn_html = '<button id="fs-btn" onclick="toggleFS()" title="スマホ横向きフル大画面">⛶ 横拡大</button>' if enable_fullscreen else ""
    fs_js = """
      var wrap = document.getElementById('wrap');
      var btn = document.getElementById('fs-btn');

      function applyLayout(isFS) {
        if (!isFS) {
          el.classList.remove('force-landscape');
          if (btn) btn.classList.remove('btn-rotated');
          el.style.width = '100%';
          el.style.height = '100%';
          chart.resize();
          return;
        }
        var w = window.innerWidth;
        var h = window.innerHeight;
        if (h > w) {
          el.classList.add('force-landscape');
          if (btn) btn.classList.add('btn-rotated');
          el.style.width = h + 'px';
          el.style.height = w + 'px';
          chart.resize({ width: h, height: w });
        } else {
          el.classList.remove('force-landscape');
          if (btn) btn.classList.remove('btn-rotated');
          el.style.width = '100%';
          el.style.height = '100%';
          chart.resize({ width: w, height: h });
        }
      }

      function toggleFS() {
        var doc = document;
        var isFS = !!(doc.fullscreenElement || doc.webkitFullscreenElement);
        if (!isFS) {
          var req = wrap.requestFullscreen || wrap.webkitRequestFullscreen;
          if (req) {
            Promise.resolve(req.call(wrap)).then(function() {
              if (screen.orientation && screen.orientation.lock) {
                screen.orientation.lock('landscape').catch(function(){});
              }
              setTimeout(function() { applyLayout(true); }, 250);
            }).catch(function(){});
          }
        } else {
          var ex = doc.exitFullscreen || doc.webkitExitFullscreen;
          if (ex) ex.call(doc);
          if (screen.orientation && screen.orientation.unlock) {
            try { screen.orientation.unlock(); } catch(e) {}
          }
        }
      }

      function onFSChange() {
        var isFS = !!(document.fullscreenElement || document.webkitFullscreenElement);
        if (btn) btn.textContent = isFS ? '✕ 戻す' : '⛶ 横拡大';
        if (opt.dataZoom) {
          chart.setOption({
            grid: { bottom: isFS ? 44 : 24, top: isFS ? 48 : 60 },
            dataZoom: isFS
              ? [{ type: 'inside', xAxisIndex: 0, filterMode: 'none' }, { type: 'slider', xAxisIndex: 0, height: 18, bottom: 6, borderColor: 'rgba(56,189,248,0.35)', fillerColor: 'rgba(56,189,248,0.18)', textStyle: { color: '#94a3b8', fontSize: 9 } }]
              : [{ type: 'inside', xAxisIndex: 0, filterMode: 'none' }]
          });
        }
        setTimeout(function() { applyLayout(isFS); }, 150);
        setTimeout(function() { applyLayout(isFS); }, 400);
      }

      document.addEventListener('fullscreenchange', onFSChange);
      document.addEventListener('webkitfullscreenchange', onFSChange);
      window.addEventListener('orientationchange', function() {
        var isFS = !!(document.fullscreenElement || document.webkitFullscreenElement);
        setTimeout(function() { applyLayout(isFS); }, 250);
      });
    """ if enable_fullscreen else ""

    html_code = f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
      html,body{{width:100%;height:100%;margin:0;padding:0;background:#0b1120;overflow:hidden;}}
      #wrap{{position:relative;width:100%;height:100%;background:#0b1120;}}
      #c{{width:100%;height:100%;}}
      #c.force-landscape{{
        position:fixed;
        top:0;
        left:100vw;
        transform:rotate(90deg);
        transform-origin:top left;
      }}
      #fs-btn{{
        position:absolute;top:4px;right:6px;z-index:99;
        background:rgba(15,23,42,0.85);color:#7dd3fc;
        border:1px solid rgba(56,189,248,0.45);border-radius:6px;
        padding:2px 7px;font-size:10.5px;font-weight:700;cursor:pointer;
        font-family:'JetBrains Mono',sans-serif;
      }}
      #fs-btn.btn-rotated{{
        position:fixed;
        top:auto;
        bottom:16px;
        right:8px;
        transform:rotate(90deg);
        transform-origin:center center;
      }}
      #fs-btn:active{{background:rgba(56,189,248,0.25);}}
    </style>
    </head><body>
      <div id="wrap">
        {fs_btn_html}
        <div id="c"></div>
      </div>
      <script>
        var el = document.getElementById('c');
        var chart = echarts.init(el, 'dark');
        var opt = {opt_json};
        {hud_js}
        chart.setOption(opt);
        function doResize() {{
          var isFS = !!(document.fullscreenElement || document.webkitFullscreenElement);
          if (typeof applyLayout === 'function' && isFS) {{
            applyLayout(true);
          }} else {{
            chart.resize();
          }}
        }}
        window.addEventListener('resize', doResize);
        if (typeof ResizeObserver !== 'undefined') {{ new ResizeObserver(doResize).observe(el); }}
        {fs_js}
        setTimeout(doResize, 80); setTimeout(doResize, 300);
      </script>
    </body></html>
    """
    components.html(html_code, height=height + 2)


def _render_live_clock(sync_interval: int = 60, active: bool = True):
    dot_col = "#10b981" if active else "#f59e0b"
    status_lbl = "LIVE FEED" if active else "PAUSED"
    right_html = f'SILENT SYNC <span id="cd" class="cnt">{sync_interval}s</span>' if active else '<span style="color:#f59e0b;font-weight:700;">自動更新 停止中</span>'
    html_code = f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <style>
      html,body{{width:100%;margin:0;padding:0;background:transparent;font-family:'JetBrains Mono',monospace;}}
      .bar{{display:flex;justify-content:space-between;align-items:center;background:rgba(15,23,42,0.85);border:1px solid {'rgba(16,185,129,0.35)' if active else 'rgba(245,158,11,0.4)'};border-radius:8px;padding:4px 10px;font-size:10.5px;color:#e2e8f0;}}
      .dot{{width:7px;height:7px;background:{dot_col};border-radius:50%;display:inline-block;margin-right:6px;box-shadow:0 0 8px {dot_col};}}
      .left{{display:flex;align-items:center;color:{'#6ee7b7' if active else '#fde047'};font-weight:700;}}
      .right{{color:#94a3b8;font-size:10px;}} .cnt{{color:#38bdf8;font-weight:700;}}
    </style></head><body>
    <div class="bar"><div class="left"><span class="dot"></span>{status_lbl} <span id="clk" style="margin-left:8px;color:#fff;">--:--:--</span> JST</div><div class="right">{right_html}</div></div>
    <script>
      var rem = {sync_interval};
      var active = {'true' if active else 'false'};
      function tick(){{
        var now = new Date(); var jst = new Date(now.getTime() + (now.getTimezoneOffset()+540)*60000);
        document.getElementById('clk').textContent = String(jst.getHours()).padStart(2,'0')+':'+String(jst.getMinutes()).padStart(2,'0')+':'+String(jst.getSeconds()).padStart(2,'0');
        if (active) {{
          var cd = document.getElementById('cd');
          if (cd) cd.textContent = rem+'s';
          rem = rem > 1 ? rem - 1 : {sync_interval};
        }}
      }}
      tick(); setInterval(tick, 1000);
    </script></body></html>
    """
    components.html(html_code, height=30)


def _build_spark_svg(prices: np.ndarray) -> str:
    if len(prices) < 2:
        return ""
    p_min, p_max = float(np.min(prices)), float(np.max(prices))
    span = max(p_max - p_min, 1e-4)
    w, h = 92.0, 26.0
    pts = [f"{round((i/max(len(prices)-1,1))*w,1)},{round(h-2.0-((float(p)-p_min)/span)*(h-4.0),1)}" for i, p in enumerate(prices)]
    col = "#10b981" if prices[-1] >= prices[0] else "#ef4444"
    return f'<svg width="92" height="26" viewBox="0 0 92 26" style="display:block;margin-left:auto;"><polyline fill="none" stroke="{col}" stroke-width="1.8" points="{" ".join(pts)}"/></svg>'


MACRO_TICKERS = {
    "SOX": ("^SOX", "米SOX"),
    "SP500": ("^GSPC", "S&P500"),
    "NQ_FUT": ("NQ=F", "NASDAQ先物"),
    "ES_FUT": ("ES=F", "S&P先物"),
    "NK_FUT": ("NIY=F", "日経先物"),
    "USDJPY": ("JPY=X", "ドル円"),
    "US10Y": ("^TNX", "米10年債"),
    "OIL": ("CL=F", "WTI原油"),
    "VIX": ("^VIX", "VIX"),
}
INTRADAY_RT_MACRO_KEYS = {"NK_FUT", "ES_FUT", "NQ_FUT", "USDJPY"}
TIER1_SOURCES = ["REUTERS", "ロイター", "BLOOMBERG", "ブルームバーグ", "WSJ", "WALL STREET JOURNAL", "FINANCIAL TIMES", "NIKKEI", "日経", "日本経済新聞", "KABUTAN", "株探", "PR TIMES", "CNBC", "SEC"]
TIER2_SOURCES = ["YAHOO", "MINKABU", "みんかぶ", "MARKETWATCH", "BARRON", "FORBES", "東洋経済", "ダイヤモンド", "JIJI", "時事", "共同通信"]
NOISE_SOURCES = ["まとめ", "ブログ", "2ch", "5ch", "note.com"]
NEG_GUARD_PATTERNS = ["赤字縮小", "赤字脱却", "赤字解消", "下落せず", "懸念後退", "懸念払拭", "リスク軽減", "リスク後退", "不祥事.*他社", "訴訟.*和解", "訴訟.*勝訴"]


@st.cache_data(ttl=90)
def _load_macro_data() -> dict:
    codes = [v[0] for v in MACRO_TICKERS.values()]
    rt_codes = [MACRO_TICKERS[k][0] for k in INTRADAY_RT_MACRO_KEYS if k in MACRO_TICKERS]
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
                    out[k] = {
                        "label": label,
                        "last": last_c,
                        "prev_close": prev_c,
                        "diff_pct": round((last_c - prev_c) / max(abs(prev_c), 1e-4) * 100.0, 2),
                        "series": closes,
                        "is_rt": False,
                    }
            except Exception:
                pass
    except Exception:
        pass

    # B-3: 夜間先物・プレマーケット・為替の15m/5m分足リアルタイム気配ギャップ取得
    try:
        raw_rt = yf.download(rt_codes, period="5d", interval="15m", group_by="ticker", prepost=True, threads=True, progress=False, timeout=6.0)
        for k in INTRADAY_RT_MACRO_KEYS:
            if k not in out:
                continue
            tk = MACRO_TICKERS[k][0]
            try:
                df_rt = raw_rt[tk].dropna(subset=["Close"]) if isinstance(raw_rt.columns, pd.MultiIndex) else raw_rt.dropna(subset=["Close"])
                if len(df_rt) >= 2:
                    rt_last = float(df_rt["Close"].iloc[-1])
                    idx_rt = pd.to_datetime(df_rt.index)
                    if idx_rt.tz is not None:
                        idx_rt = idx_rt.tz_convert("UTC").tz_localize(None)
                    df_rt_tmp = df_rt.copy()
                    df_rt_tmp["_d"] = idx_rt.strftime("%Y-%m-%d")
                    ud = sorted(df_rt_tmp["_d"].unique().tolist())
                    ref_prev = out[k]["prev_close"]
                    if len(ud) >= 2:
                        prev_day_sub = df_rt_tmp[df_rt_tmp["_d"] == ud[-2]]
                        if not prev_day_sub.empty:
                            ref_prev = float(prev_day_sub["Close"].iloc[-1])
                    if rt_last > 0 and ref_prev > 0:
                        out[k]["last"] = rt_last
                        out[k]["diff_pct"] = round((rt_last - ref_prev) / max(abs(ref_prev), 1e-4) * 100.0, 2)
                        out[k]["is_rt"] = True
            except Exception:
                pass
    except Exception:
        pass

    return out


@st.cache_data(ttl=60)
def _load_benchmark_5m(is_jp: bool) -> pd.DataFrame:
    """B-1: 指数ベータ分離用の市場ベンチマーク5分足（日本株=1306.T/^N225, 米国株=QQQ/SPY）"""
    cands = ["1306.T", "^N225"] if is_jp else ["QQQ", "SPY"]
    for b_tk in cands:
        try:
            df_b = yf.Ticker(b_tk).history(period="1mo", interval="5m", auto_adjust=True)
            if df_b is not None and len(df_b) >= 40:
                df_b = df_b.dropna(subset=["Close"]).copy()
                return df_b
        except Exception:
            continue
    return pd.DataFrame()


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

    earnings_hist, next_earnings_days = [], None
    try:
        ed = tkr.earnings_dates
        if ed is not None and not ed.empty:
            today_d = datetime.date.today()
            future_days = []
            for idx_dt, row in ed.head(12).iterrows():
                dt_obj = idx_dt.date() if hasattr(idx_dt, "date") else None
                if dt_obj and dt_obj >= today_d:
                    future_days.append((dt_obj - today_d).days)
                if pd.notna(row.get("EPS Estimate")) or pd.notna(row.get("Reported EPS")):
                    if len(earnings_hist) < 6:
                        earnings_hist.append({
                            "date": idx_dt.strftime("%Y-%m-%d") if hasattr(idx_dt, "strftime") else str(idx_dt)[:10],
                            "est": float(row["EPS Estimate"]) if pd.notna(row.get("EPS Estimate")) else None,
                            "rep": float(row["Reported EPS"]) if pd.notna(row.get("Reported EPS")) else None,
                            "surp": float(row["Surprise(%)"]) if pd.notna(row.get("Surprise(%)")) else None
                        })
            if future_days:
                next_earnings_days = min(future_days)
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

    # A-1: insider_transactions の取引日付を抽出して保持
    insider_tx = []
    try:
        itx = tkr.insider_transactions
        if itx is not None and not itx.empty:
            for idx_itx, row in itx.head(12).iterrows():
                raw_dt = row.get("Start Date") or row.get("Date") or row.get("Transaction Date") or idx_itx
                tx_date_str = ""
                try:
                    dt_parsed = pd.to_datetime(raw_dt)
                    if pd.notna(dt_parsed):
                        tx_date_str = dt_parsed.strftime("%Y-%m-%d")
                except Exception:
                    tx_date_str = ""
                insider_tx.append({
                    "insider": str(row.get("Insider", "-")),
                    "text": str(row.get("Text", row.get("Transaction", "-"))),
                    "shares": int(row.get("Shares", 0)) if pd.notna(row.get("Shares")) else 0,
                    "date": tx_date_str,
                })
    except Exception:
        pass

    return {
        "df_1d": df_1d, "df_5m": df_5m, "info": info,
        "earnings_hist": earnings_hist, "next_earnings_days": next_earnings_days,
        "inst_holders": inst_holders, "insider_tx": insider_tx
    }


def _fetch_rss(url: str, lang_tag: str) -> list:
    out = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=4.0) as r:
            for it in ET.fromstring(r.read()).findall("./channel/item")[:12]:
                t = (it.findtext("title") or "").strip()
                pub_raw = (it.findtext("pubDate") or "").strip()
                if t:
                    out.append({
                        "title": t,
                        "link": (it.findtext("link") or "").strip(),
                        "source": (it.findtext("source") or "").strip(),
                        "pub": pub_raw[:16],
                        "pub_raw": pub_raw,
                        "lang": lang_tag,
                    })
    except Exception:
        pass
    return out


def _calc_rss_time_decay(pub_raw: str, now_utc: datetime.datetime) -> tuple:
    """A-1: RSS pubDate をパースし、24h以内=1.0 / 72h以内=0.3 / それ以前=0.0 の時間減衰を返す"""
    if not pub_raw:
        return 0.0, 999.0
    try:
        dt_parsed = email.utils.parsedate_to_datetime(pub_raw)
        if dt_parsed is None:
            return 0.0, 999.0
        if dt_parsed.tzinfo is None:
            dt_parsed = dt_parsed.replace(tzinfo=datetime.timezone.utc)
        else:
            dt_parsed = dt_parsed.astimezone(datetime.timezone.utc)
        age_hours = max(0.0, (now_utc - dt_parsed).total_seconds() / 3600.0)
        if age_hours <= 24.0:
            return 1.0, round(age_hours, 1)
        if age_hours <= 72.0:
            return 0.3, round(age_hours, 1)
        return 0.0, round(age_hours, 1)
    except Exception:
        return 0.0, 999.0


def _strip_neg_guards(text: str) -> str:
    cleaned = text
    for pat in NEG_GUARD_PATTERNS:
        cleaned = re.sub(pat, "", cleaned)
    return cleaned


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

    now_utc = datetime.datetime.now(datetime.timezone.utc)
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

        decay_w, age_h = _calc_rss_time_decay(it.get("pub_raw", ""), now_utc)
        trust, base_wt = ("S", 2.0) if any(t1 in src_up for t1 in TIER1_SOURCES) else (("A", 1.3) if any(t2 in src_up for t2 in TIER2_SOURCES) else ("B", 0.7))
        eff_wt = round(base_wt * decay_w, 3)

        t_up = _strip_neg_guards(it["title"]).upper()
        p_h, n_h = sum(1 for w in pos_w if w in t_up), sum(1 for w in neg_w if w in t_up)
        filtered.append({
            **it,
            "trust": trust,
            "w_trust": eff_wt,
            "decay_w": decay_w,
            "age_h": age_h,
            "sent": "POS" if p_h > n_h else ("NEG" if n_h > p_h else "NEU"),
        })

    filtered.sort(key=lambda x: (-x["decay_w"], {"S": 0, "A": 1, "B": 2}[x["trust"]], 0 if x["lang"] == "EN" else 1))
    fresh_items = [x for x in filtered if x["w_trust"] > 0.0]
    wp = sum(x["w_trust"] for x in fresh_items if x["sent"] == "POS")
    wn = sum(x["w_trust"] for x in fresh_items if x["sent"] == "NEG")
    wtot = max(sum(x["w_trust"] for x in fresh_items), 1.0)
    return {
        "items": filtered[:10],
        "pos_pct": round(wp / wtot * 100) if fresh_items else 50,
        "shock_score": round(float(np.clip((wp - wn) / wtot, -1.0, 1.0)), 2) if fresh_items else 0.0,
        "tier1_cnt": sum(1 for x in fresh_items if x["trust"] == "S"),
        "fresh_cnt": len(fresh_items),
    }


@st.cache_data(ttl=180)
def _fetch_gov_and_whales(corp_name: str, short_code: str) -> tuple:
    u_g = f"https://news.google.com/rss/search?q={urllib.parse.quote(f'{corp_name} (不祥事 OR 不正 OR 訴訟 OR 行政処分 OR 辞任 OR リコール)')}&hl=ja&gl=JP&ceid=JP:ja"
    u_w = f"https://news.google.com/rss/search?q={urllib.parse.quote(f'({corp_name} OR {short_code}) (大量保有 OR 変更報告書 OR 空売り残高 OR 5%ルール OR 買い増し OR 保有割合低下)')}&hl=ja&gl=JP&ceid=JP:ja"
    gov_kw = ["不祥事", "不正", "訴訟", "行政処分", "辞任", "リコール"]
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    with ThreadPoolExecutor(max_workers=2) as ex:
        fg, fw = ex.submit(_fetch_rss, u_g, "JP"), ex.submit(_fetch_rss, u_w, "JP")
        gov_filtered = []
        for x in fg.result()[:10]:
            decay_w, _ = _calc_rss_time_decay(x.get("pub_raw", ""), now_utc)
            if decay_w <= 0.0:
                continue
            cleaned_t = _strip_neg_guards(x["title"])
            if any(k in cleaned_t for k in gov_kw):
                gov_filtered.append(f"{x['title']} ({x['pub']})")
            if len(gov_filtered) >= 5:
                break
        whale_fresh = []
        for x in fw.result()[:8]:
            decay_w, _ = _calc_rss_time_decay(x.get("pub_raw", ""), now_utc)
            if decay_w > 0.0:
                whale_fresh.append(x)
        return gov_filtered, whale_fresh[:5]


# =========================================================================
# 4. 機関投資家プロ仕様：心理的キリ番節目・スイングCVD・Gap&Go判定・しこり玉VP
# =========================================================================
def _compute_round_number_level(curr_px: float, is_jp: bool) -> float:
    if is_jp:
        step = 5000 if curr_px >= 20000 else (1000 if curr_px >= 5000 else (500 if curr_px >= 2000 else 100))
    else:
        step = 50 if curr_px >= 400 else (25 if curr_px >= 150 else (10 if curr_px >= 50 else 5))
    return float(round(curr_px / step) * step)


def _detect_whale_anomaly(insider_tx: list, whale_news: list, ref_today_str: str) -> dict:
    """A-1: 直近30日以内のインサイダー取引のみ異常検知対象（日付不可は除外）"""
    bull_sigs, bear_sigs = [], []
    try:
        ref_date = datetime.datetime.strptime(ref_today_str, "%Y-%m-%d").date()
    except Exception:
        ref_date = datetime.date.today()

    for tx in insider_tx:
        tx_ds = str(tx.get("date") or "").strip()
        if not tx_ds:
            continue
        try:
            tx_d = datetime.datetime.strptime(tx_ds[:10], "%Y-%m-%d").date()
            age_days = (ref_date - tx_d).days
            if age_days < 0 or age_days > 30:
                continue
        except Exception:
            continue

        t_up = tx["text"].upper()
        if "PURCHASE" in t_up or "BUY" in t_up:
            bull_sigs.append(f"役員買付({tx_ds}): {tx['insider']} ({_fmt_sh(tx['shares'])})")
        elif "SALE" in t_up or "SELL" in t_up:
            bear_sigs.append(f"役員売却({tx_ds}): {tx['insider']} ({_fmt_sh(tx['shares'])})")

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
    return {"detected": False, "dir": "NEUTRAL", "adj_pct": 0.0, "summary": "直近30日以内の特異な大口異変なし"}


def _detect_cvd_divergence(slots: list, actual_arr: list, cvd_arr: list, act_vol_map: dict) -> dict:
    """A-6: 前後2本（計5本）スイング極値ベース＋平均出来高以上フィルタの疑似CVDダイバージェンス"""
    pts = [
        (i, slots[i], actual_arr[i], cvd_arr[i], float(act_vol_map.get(slots[i], 0.0)))
        for i in range(len(slots))
        if actual_arr[i] is not None and cvd_arr[i] is not None
    ]
    if len(pts) < 7:
        return {"state": "WAIT", "label": "計測中", "color": "#94a3b8", "detail": "場中スイングデータ蓄積待ち", "marker": None}

    avg_vol = float(np.mean([p[4] for p in pts])) if pts else 0.0
    swing_highs = []
    swing_lows = []

    for idx in range(2, len(pts) - 2):
        p_cur = pts[idx][2]
        v_cur = pts[idx][4]
        if avg_vol > 0 and v_cur < avg_vol:
            continue
        win_px = [pts[j][2] for j in range(idx - 2, idx + 3)]
        if p_cur >= max(win_px) and p_cur > pts[idx - 1][2] and p_cur >= pts[idx + 1][2]:
            swing_highs.append(pts[idx])
        if p_cur <= min(win_px) and p_cur < pts[idx - 1][2] and p_cur <= pts[idx + 1][2]:
            swing_lows.append(pts[idx])

    if len(swing_highs) >= 2:
        sh1, sh2 = swing_highs[-2], swing_highs[-1]
        if sh2[2] > sh1[2] * 1.0012 and sh2[3] < sh1[3]:
            return {
                "state": "DISTRIBUTION",
                "label": "売り抜け警戒",
                "color": "#ef4444",
                "detail": f"スイング高値更新（{sh1[1]}→{sh2[1]}）に対し、疑似CVDが切り下げ。出来高伴う大口の天井売り抜け（Distribution）の兆候。",
                "marker": {"time": sh2[1], "price": sh2[2], "name": "売り抜け", "color": "#ef4444"},
            }

    if len(swing_lows) >= 2:
        sl1, sl2 = swing_lows[-2], swing_lows[-1]
        if sl2[2] < sl1[2] * 0.9988 and sl2[3] > sl1[3]:
            return {
                "state": "ABSORPTION",
                "label": "底値吸収",
                "color": "#10b981",
                "detail": f"スイング安値更新（{sl1[1]}→{sl2[1]}）に対し、疑似CVDが切り上げ。出来高伴う大口の指値買い吸収（Absorption）の兆候。",
                "marker": {"time": sl2[1], "price": sl2[2], "name": "底値吸収", "color": "#10b981"},
            }

    last_cvd = pts[-1][3]
    if last_cvd > 0:
        return {"state": "ALIGNED_BULL", "label": "買い優勢", "color": "#38bdf8", "detail": "疑似CVDプラス圏で買い主導の推移。", "marker": None}
    if last_cvd < 0:
        return {"state": "ALIGNED_BEAR", "label": "売り優勢", "color": "#f59e0b", "detail": "疑似CVDマイナス圏で売り主導の推移。", "marker": None}
    return {"state": "NEUTRAL", "label": "均衡", "color": "#94a3b8", "detail": "売り買いのデルタは均衡。", "marker": None}


def _evaluate_gap_open15(
    has_actual: bool, slots: list, actual_arr: list, vwap_arr: list,
    act_low_map: dict, act_high_map: dict, act_vol_map: dict, slot_vols: np.ndarray,
    prev_px: float
) -> dict:
    default_res = {"status": "WAIT", "label": "待機中", "color": "#94a3b8", "bias": 0.0, "detail": "", "show_gap_target": False}
    if not has_actual or prev_px <= 0:
        return default_res

    first_pts = [(i, slots[i], actual_arr[i], vwap_arr[i]) for i in range(len(slots)) if actual_arr[i] is not None][:3]
    if len(first_pts) < 3:
        return default_res

    open_px = first_pts[0][2]
    gap_pct = (open_px - prev_px) / max(prev_px, 1e-4) * 100.0
    if abs(gap_pct) < 0.20:
        return {"status": "FLAT", "label": "フラット寄り", "color": "#94a3b8", "bias": 0.0, "detail": f"寄付きギャップ {gap_pct:+.2f}%（通常スタート）", "show_gap_target": False}

    act_v3 = sum(act_vol_map.get(sl, 0.0) for _, sl, _, _ in first_pts)
    avg_v3 = sum(float(slot_vols[i]) for i, _, _, _ in first_pts)
    rvol15 = (act_v3 / avg_v3) if avg_v3 > 0 else 1.0

    lows3 = [act_low_map.get(sl, px) for _, sl, px, _ in first_pts]
    highs3 = [act_high_map.get(sl, px) for _, sl, px, _ in first_pts]
    above_vwap_all = all((px >= vw) for _, _, px, vw in first_pts if vw is not None)
    below_vwap_all = all((px <= vw) for _, _, px, vw in first_pts if vw is not None)
    last_px, last_vw = first_pts[-1][2], first_pts[-1][3] or first_pts[-1][2]

    if gap_pct >= 0.20:
        no_open_low_break = min(lows3[1:]) >= lows3[0] * 0.999
        if above_vwap_all and rvol15 >= 1.5 and no_open_low_break:
            return {
                "status": "GAP_AND_GO_UP",
                "label": "Gap&Go 上昇確定",
                "color": "#10b981",
                "bias": 0.0045,
                "detail": f"GU({gap_pct:+.2f}%)後15分すべてVWAP上・RVOL {rvol15:.2f}x・寄り安値割れなし。窓は埋まらず上昇加速しやすい本物初動。",
                "show_gap_target": False,
            }
        if rvol15 < 1.0 or last_px < last_vw:
            return {
                "status": "GAP_AND_FADE_DOWN",
                "label": "Gap&Fade 窓埋警戒",
                "color": "#ef4444",
                "bias": -0.0045,
                "detail": f"GU({gap_pct:+.2f}%)後に勢い失速（RVOL {rvol15:.2f}x / VWAP割れ）。飛びつき買い危険・前日終値までの窓埋め警戒。",
                "show_gap_target": True,
            }
        return {"status": "GU_HOLD", "label": "GU 様子見", "color": "#38bdf8", "bias": 0.001, "detail": f"GU({gap_pct:+.2f}%)・RVOL {rvol15:.2f}x。", "show_gap_target": False}

    no_open_high_break = max(highs3[1:]) <= highs3[0] * 1.001
    if below_vwap_all and rvol15 >= 1.5 and no_open_high_break:
        return {
            "status": "GAP_AND_GO_DOWN",
            "label": "Gap&Go 下落確定",
            "color": "#ef4444",
            "bias": -0.0045,
            "detail": f"GD({gap_pct:+.2f}%)後15分すべてVWAP下・RVOL {rvol15:.2f}x。投げ売り継続の本物下落初動。",
            "show_gap_target": False,
        }
    if rvol15 < 1.0 or last_px > last_vw:
        return {
            "status": "GAP_AND_FADE_UP",
            "label": "Gap&Fade 窓埋反発",
            "color": "#10b981",
            "bias": 0.0045,
            "detail": f"GD({gap_pct:+.2f}%)後に売り一巡（RVOL {rvol15:.2f}x / VWAP回復）。前日終値に向けた窓埋め反発に優位性。",
            "show_gap_target": True,
        }
    return {"status": "GD_HOLD", "label": "GD 様子見", "color": "#f59e0b", "bias": -0.001, "detail": f"GD({gap_pct:+.2f}%)・RVOL {rvol15:.2f}x。", "show_gap_target": False}


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


def _compute_dow_edge(df_1d: pd.DataFrame, is_jp: bool) -> tuple:
    """A-3: datetime.datetime.now() を廃止し、_get_market_now(is_jp).weekday() に統一"""
    rets = df_1d["Close"].pct_change().dropna() * 100.0
    names = ["月", "火", "水", "木", "金"]
    stats = []
    for d in range(5):
        sub = rets[rets.index.dayofweek == d]
        wr, avg = (int(round(float((sub > 0).mean() * 100.0), 0)), round(float(sub.mean()), 2)) if len(sub) >= 3 else (50, 0.0)
        stats.append({"dow": d, "label": names[d], "wr": wr, "avg": avg})
    wd = _get_market_now(is_jp).weekday()
    return stats, (0 if wd >= 4 else wd + 1)


def _compute_wick_bias(df_1d: pd.DataFrame) -> float:
    sub = df_1d.tail(5)
    if len(sub) < 3:
        return 0.0
    o, h, l, c = sub["Open"].values, sub["High"].values, sub["Low"].values, sub["Close"].values
    rng = np.maximum(h - l, 1e-4)
    return round(float(np.clip((float(np.mean((np.minimum(o, c) - l) / rng)) - float(np.mean((h - np.maximum(o, c)) / rng))) * 0.8, -0.45, 0.45)), 2)


def _compute_vp(df_1d: pd.DataFrame, curr_px: float, is_jp: bool) -> dict:
    """A-7: Low〜Highレンジ均等配分 ＋ 指数時間減衰（半減期60営業日）による生きたしこり玉VP"""
    sub = df_1d.tail(250)
    if len(sub) < 20:
        return {"overhead_pct": 0.0, "poc_px": curr_px, "labels": [], "vols": [], "res_px": curr_px, "sup_px": curr_px}

    n_rows = len(sub)
    lows = sub["Low"].values.astype(float)
    highs = sub["High"].values.astype(float)
    vols = sub["Volume"].values.astype(float)

    # 半減期60営業日の指数時間減衰
    ages = np.arange(n_rows - 1, -1, -1, dtype=float)
    decay_weights = np.power(0.5, ages / 60.0)
    eff_vols = vols * decay_weights

    p_min = float(np.min(lows))
    p_max = float(np.max(highs))
    if p_max <= p_min:
        p_max = p_min + 1e-3

    n_bins = 14
    bins = np.linspace(p_min, p_max, n_bins + 1)
    bin_w = (p_max - p_min) / n_bins
    hist = np.zeros(n_bins, dtype=float)

    for lo_v, hi_v, w_vol in zip(lows, highs, eff_vols):
        if w_vol <= 0:
            continue
        if hi_v <= lo_v + 1e-6:
            b_idx = int(np.clip((lo_v - p_min) / max(bin_w, 1e-6), 0, n_bins - 1))
            hist[b_idx] += w_vol
        else:
            span = hi_v - lo_v
            for b in range(n_bins):
                ov_lo = max(lo_v, bins[b])
                ov_hi = min(hi_v, bins[b + 1])
                if ov_hi > ov_lo:
                    hist[b] += w_vol * ((ov_hi - ov_lo) / span)

    centers = [(bins[i] + bins[i + 1]) * 0.5 for i in range(n_bins)]
    tot_hist = max(float(np.sum(hist)), 1.0)
    above_v = sum(hist[i] for i, c in enumerate(centers) if c > curr_px * 1.005)
    a_idx = [i for i, c in enumerate(centers) if c > curr_px * 1.005]
    b_idx = [i for i, c in enumerate(centers) if c < curr_px * 0.995]
    return {
        "overhead_pct": round(above_v / tot_hist * 100.0, 1),
        "poc_px": float(centers[int(np.argmax(hist))]),
        "labels": [_fmt_cur(c, is_jp) for c in centers],
        "vols": [round(float(v) / 1e6, 2) for v in hist],
        "res_px": float(centers[max(a_idx, key=lambda i: hist[i])]) if a_idx else curr_px * 1.05,
        "sup_px": float(centers[max(b_idx, key=lambda i: hist[i])]) if b_idx else curr_px * 0.95,
    }


def _compute_self_calibration(stock_hist: dict, df_1d: pd.DataFrame, market_today_str: str) -> tuple:
    if not stock_hist or df_1d is None or df_1d.empty:
        return 0.0, 0
    close_map = {idx.strftime("%Y-%m-%d"): float(val) for idx, val in df_1d["Close"].items()}
    diffs = []
    for dt_k in sorted(stock_hist.keys()):
        if dt_k >= market_today_str:
            continue
        snap = stock_hist[dt_k]
        if snap.get("locked_premarket") is False:
            continue
        if dt_k in close_map:
            p50_arr = snap.get("p50")
            if p50_arr and len(p50_arr) > 0:
                pred_c = float(p50_arr[-1])
                act_c = close_map[dt_k]
                if pred_c > 0:
                    diffs.append((act_c - pred_c) / pred_c * 100.0)
    if not diffs:
        return 0.0, 0
    recent = diffs[-5:]
    bias_pct = round(float(np.clip(np.mean(recent) * 0.40, -0.50, 0.50)), 2)
    return bias_pct, len(recent)


def _extract_lab_side(active_lab: dict) -> str:
    if not isinstance(active_lab, dict):
        return "LONG"
    side = active_lab.get("side")
    if not side and isinstance(active_lab.get("strat"), dict):
        side = active_lab["strat"].get("side")
    return str(side or "LONG").upper()


def _apply_hvn_ob_bounce(mid: float, hvn_wall_px: float, ob_sup_px: float, vp: dict) -> float:
    res_wall = hvn_wall_px if hvn_wall_px > 0 else vp["res_px"]
    if res_wall > 0 and mid > res_wall * 0.995:
        damp = 0.35 if hvn_wall_px > 0 else (0.45 if vp["overhead_pct"] >= 35.0 else 1.0)
        if damp < 1.0:
            mid = res_wall * 0.995 + (mid - res_wall * 0.995) * damp

    sup_floor = ob_sup_px if ob_sup_px > 0 else vp["sup_px"]
    if sup_floor > 0 and mid < sup_floor * 1.005:
        cushion = 0.38 if ob_sup_px > 0 else 0.65
        mid = sup_floor * 1.005 - (sup_floor * 1.005 - mid) * cushion

    return mid


def _compute_bayesian_scenario_probs(
    has_actual: bool, curr_px: float, anchor_base_close: float,
    est_open_gap_pct: float, est_close_chg: float,
    bull_trig: float, bull_target: float, bear_trig: float, bear_target: float,
    rem_sigma_pct: float, rem_drift_pct: float,
    rvol: float, cvd_div: dict, gap_open15: dict,
    cur_vwap: float, shock_ext_pct: float = 0.0
) -> dict:
    """D-1: ベイズ更新型・リアルタイム4シナリオ事後確率（上振れ突破 / 標準レンジ / 窓埋め反転 / 下振れ崩壊）"""
    fpt_bull = _calc_first_passage_prob(curr_px, bull_trig, rem_sigma_pct, rem_drift_pct) / 100.0
    fpt_bear = _calc_first_passage_prob(curr_px, bear_trig, rem_sigma_pct, rem_drift_pct) / 100.0

    # 事前対数オッズ
    log_bull = math.log(max(fpt_bull, 0.04)) + est_close_chg * 0.38 + shock_ext_pct * 0.65
    log_bear = math.log(max(fpt_bear, 0.04)) - est_close_chg * 0.38 - shock_ext_pct * 0.65
    log_range = 0.65 - abs(est_close_chg) * 0.22
    log_fade = -0.35 + min(abs(est_open_gap_pct), 3.0) * 0.32

    # RVOLによる尤度更新（高出来高＝ブレイク優位、低出来高＝レンジ・窓埋め優位）
    if rvol is not None:
        if rvol >= 1.5:
            boost = min((rvol - 1.0) * 0.45, 0.90)
            if est_close_chg >= 0:
                log_bull += boost
            else:
                log_bear += boost
            log_range -= boost * 0.5
        elif rvol < 0.85:
            log_range += 0.45
            log_fade += 0.35
            log_bull -= 0.30
            log_bear -= 0.30

    # VWAP位置による尤度更新
    if has_actual and cur_vwap and cur_vwap > 0:
        vwap_diff_pct = (curr_px - cur_vwap) / cur_vwap * 100.0
        log_bull += float(np.clip(vwap_diff_pct * 0.55, -0.8, 0.8))
        log_bear -= float(np.clip(vwap_diff_pct * 0.55, -0.8, 0.8))
        if (est_open_gap_pct > 0.25 and vwap_diff_pct < -0.15) or (est_open_gap_pct < -0.25 and vwap_diff_pct > 0.15):
            log_fade += 0.65

    # Gap15判定の尤度反映
    g_st = gap_open15.get("status", "WAIT")
    if g_st == "GAP_AND_GO_UP":
        log_bull += 0.75
        log_fade -= 0.60
    elif g_st == "GAP_AND_GO_DOWN":
        log_bear += 0.75
        log_fade -= 0.60
    elif g_st in ("GAP_AND_FADE_DOWN", "GAP_AND_FADE_UP"):
        log_fade += 0.85
        log_range += 0.20

    # 疑似CVDダイバージェンス反映
    cvd_st = cvd_div.get("state", "NEUTRAL")
    if cvd_st == "DISTRIBUTION":
        log_bear += 0.45
        log_fade += 0.40
        log_bull -= 0.45
    elif cvd_st == "ABSORPTION":
        log_bull += 0.45
        log_fade += 0.40
        log_bear -= 0.45

    logits = np.array([log_bull, log_range, log_fade, log_bear], dtype=float)
    logits -= np.max(logits)
    exps = np.exp(logits)
    probs = (exps / np.sum(exps)) * 100.0

    p_bull = round(float(probs[0]), 1)
    p_range = round(float(probs[1]), 1)
    p_fade = round(float(probs[2]), 1)
    p_bear = round(max(0.5, 100.0 - (p_bull + p_range + p_fade)), 1)

    return {
        "bull": p_bull,
        "range": p_range,
        "fade": p_fade,
        "bear": p_bear,
        "fpt_bull_pct": round(fpt_bull * 100.0, 1),
        "fpt_bear_pct": round(fpt_bear * 100.0, 1),
    }


def _audit_meta_labeling_accuracy(
    ledger: dict, fc_code: str, is_jp: bool,
    cur_regime: str, cur_rvol: float, cur_gap_pct: float
) -> dict:
    """D-2: dd_forecast_ledger_v9 のロック検証実績から現在の地合いクラスタの信頼度ランク(A〜D)を監査"""
    if not isinstance(ledger, dict) or not ledger:
        return {"rank": "計測中", "color": "#94a3b8", "n": 0, "hit_rate": 0.0, "mean_err": 0.0, "detail": "事前ロック検証データ蓄積中"}

    mkt_suffix = ".T" if is_jp else ""
    cur_gap_big = abs(cur_gap_pct) >= 0.8
    cur_rvol_hi = (cur_rvol is not None and cur_rvol >= 1.3)

    matched_records = []
    all_mkt_records = []

    for code_k, hist_map in ledger.items():
        if is_jp != code_k.endswith(".T"):
            continue
        if not isinstance(hist_map, dict):
            continue
        for dt_k, snap in hist_map.items():
            if not isinstance(snap, dict):
                continue
            if snap.get("locked_premarket") is False:
                continue
            v_stat = snap.get("verify_result")
            if not isinstance(v_stat, dict):
                continue
            in_cone = float(v_stat.get("in_cone_pct", -1.0))
            err_p = float(v_stat.get("err_pct", -1.0))
            if in_cone < 0 or err_p < 0:
                continue

            rec = {
                "code": code_k,
                "regime": str(snap.get("regime_code") or "NEUTRAL"),
                "gap_big": abs(float(snap.get("pred_open_gap_pct") or 0.0)) >= 0.8,
                "rvol_hi": bool(v_stat.get("rvol_hi", False)),
                "in_cone": in_cone,
                "err_pct": err_p,
            }
            all_mkt_records.append(rec)
            if rec["regime"] == cur_regime and rec["gap_big"] == cur_gap_big:
                matched_records.append(rec)

    target_recs = matched_records if len(matched_records) >= 3 else all_mkt_records
    n_samples = len(target_recs)
    if n_samples < 3:
        return {
            "rank": "計測中",
            "color": "#94a3b8",
            "n": n_samples,
            "hit_rate": 0.0,
            "mean_err": 0.0,
            "detail": f"同条件の事前ロック検証が {n_samples}件（3件以上でランク判定）",
        }

    avg_cone = float(np.mean([r["in_cone"] for r in target_recs]))
    avg_err = float(np.mean([r["err_pct"] for r in target_recs]))
    scope_lbl = f"{cur_regime}・{'大Gap' if cur_gap_big else '通常Gap'}" if len(matched_records) >= 3 else ("日本株全体" if is_jp else "米国株全体")

    if avg_cone >= 72.0 and avg_err <= 0.85:
        rank, col = "A", "#10b981"
    elif avg_cone >= 58.0 and avg_err <= 1.35:
        rank, col = "B", "#38bdf8"
    elif avg_cone >= 45.0:
        rank, col = "C", "#f59e0b"
    else:
        rank, col = "D", "#ef4444"

    return {
        "rank": rank,
        "color": col,
        "n": n_samples,
        "hit_rate": round(avg_cone, 1),
        "mean_err": round(avg_err, 2),
        "detail": f"{scope_lbl} (N={n_samples}): 予測帯収束率 {avg_cone:.1f}% / 平均誤差 {avg_err:.2f}%",
    }


def _build_dual_5m_trajectory(
    fc_code: str, curr_px: float, prev_px: float, df_1d: pd.DataFrame, df_5m: pd.DataFrame,
    macro_sens: list, macro_data: dict, news_res: dict, whale_anom: dict,
    dow_next_avg: float, vp: dict, is_jp: bool, mkt_regime: dict, active_lab: dict = None,
    df_bench_5m: pd.DataFrame = None
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
    regime_code = mkt_regime.get("code", "NEUTRAL")

    # A-5: クラスタ分類
    vol_cls = _classify_vol_cluster(df_1d, is_jp)
    cluster_key = vol_cls["cluster"]
    fallback_key = vol_cls["fallback"]

    actual_map, vwap_map = {}, {}
    vwap_p1_map, vwap_m1_map, vwap_p2_map, vwap_m2_map = {}, {}, {}, {}
    act_vol_map, act_dir_map, act_low_map, act_high_map = {}, {}, {}, {}
    cvd_map = {}
    orb_high, orb_low = None, None

    if df_5m is not None and not df_5m.empty:
        tmp_a = df_5m.copy()
        idx_a = _convert_5m_index_to_market_tz(tmp_a, is_jp)
        tmp_a["_d"], tmp_a["_hm"] = idx_a.strftime("%Y-%m-%d"), idx_a.strftime("%H:%M")
        if market_today_str in tmp_a["_d"].values:
            sub_today = tmp_a[tmp_a["_d"] == market_today_str]
            cum_pv, cum_pv2, cum_v, cum_cvd = 0.0, 0.0, 0.0, 0.0
            orb_sub = sub_today.head(6)
            if len(orb_sub) >= 2:
                orb_high = round(float(orb_sub["High"].max()), 2)
                orb_low = round(float(orb_sub["Low"].min()), 2)
            for _, row in sub_today.iterrows():
                hm = row["_hm"]
                if hm in slots:
                    o_val = float(row.get("Open", row["Close"]))
                    h_val = float(row.get("High", row["Close"]))
                    l_val = float(row.get("Low", row["Close"]))
                    c_val = float(row["Close"])
                    v_val = max(float(row.get("Volume", 0.0)), 0.0)
                    tp_val = (h_val + l_val + c_val) / 3.0
                    cum_pv += tp_val * v_val
                    cum_pv2 += (tp_val ** 2) * v_val
                    cum_v += v_val
                    vw = (cum_pv / cum_v) if cum_v > 0 else c_val
                    var_v = max((cum_pv2 / cum_v) - (vw ** 2), 0.0) if cum_v > 0 else 0.0
                    sd_v = math.sqrt(var_v)

                    hl_span = h_val - l_val
                    clv = (((c_val - l_val) - (h_val - c_val)) / hl_span) if hl_span > 1e-6 else (1.0 if c_val > o_val else (-1.0 if c_val < o_val else 0.0))
                    cum_cvd += clv * v_val

                    actual_map[hm] = round(c_val, 2)
                    vwap_map[hm] = round(vw, 2)
                    vwap_p1_map[hm] = round(vw + sd_v, 2)
                    vwap_m1_map[hm] = round(vw - sd_v, 2)
                    vwap_p2_map[hm] = round(vw + 2.0 * sd_v, 2)
                    vwap_m2_map[hm] = round(vw - 2.0 * sd_v, 2)
                    act_vol_map[hm] = v_val
                    act_dir_map[hm] = 1 if c_val >= o_val else -1
                    act_low_map[hm] = l_val
                    act_high_map[hm] = h_val
                    cvd_map[hm] = round(cum_cvd, 1)

    actual_arr = [actual_map.get(sl, None) for sl in slots]
    vwap_arr = [vwap_map.get(sl, None) for sl in slots]
    vwap_p1_arr = [vwap_p1_map.get(sl, None) for sl in slots]
    vwap_m1_arr = [vwap_m1_map.get(sl, None) for sl in slots]
    vwap_p2_arr = [vwap_p2_map.get(sl, None) for sl in slots]
    vwap_m2_arr = [vwap_m2_map.get(sl, None) for sl in slots]
    cvd_arr = [cvd_map.get(sl, None) for sl in slots]
    has_actual = bool(actual_map)
    last_act_idx = max([i for i, v in enumerate(actual_arr) if v is not None], default=-1)
    anchor_base_close = prev_px if has_actual else curr_px

    ledger = _dd_db_get("dd_forecast_ledger_v9", {})
    if not isinstance(ledger, dict):
        ledger = {}
    stock_hist = ledger.get(fc_code, {})
    if not isinstance(stock_hist, dict):
        stock_hist = {}

    # A-5: クラスタ別3脳SGDの読み込み＆更新
    w_evo = _load_weights_evolution()
    w_evo, weights_updated = _update_weights_two_stage(
        w_evo, fc_code, df_1d, stock_hist, market_today_str, cluster_key, fallback_key
    )
    og_w, idr_w, cluster_n, shrink_alpha = _get_shrunk_cluster_brain(w_evo, cluster_key, fallback_key, regime_code)

    smap = {x["key"]: x for x in macro_sens}
    mk = "SOX" if ("SOX" in smap and abs(smap["SOX"]["corr"]) > 0.35) else ("NK_FUT" if (is_jp and "NK_FUT" in smap) else "SP500")
    mi = smap.get(mk, {"label": "日経先物" if is_jp else "S&P500", "beta": 0.5, "latest_diff": 0.0})
    fi = smap.get("USDJPY", {"label": "ドル円", "beta": 0.0, "latest_diff": 0.0})
    vix_d = macro_data.get("VIX", {}).get("diff_pct", 0.0)

    raw_macro_x = float(mi["latest_diff"] * mi["beta"])
    raw_fx_x = float(fi["latest_diff"] * fi["beta"])
    raw_news_x = float(news_res["shock_score"])
    raw_whale_x = float(whale_anom["adj_pct"])
    raw_dow_x = float(dow_next_avg)
    raw_wick_x = float(_compute_wick_bias(df_1d))

    lab_strength_dir = 0.0
    if isinstance(active_lab, dict) and active_lab:
        l_side = _extract_lab_side(active_lab)
        l_exp = float(active_lab.get("expect_pct", 50.0))
        l_strength = float(np.clip((l_exp - 50.0) / 40.0, 0.0, 1.0))
        lab_strength_dir = (1.0 if l_side == "LONG" else -1.0) * l_strength

    mg = raw_macro_x * og_w["macro"]
    fg = raw_fx_x * og_w["fx"]
    ng = raw_news_x * og_w["news"]
    wg = raw_whale_x * og_w["whale"]
    lg_open = lab_strength_dir * og_w["lab_bias"]
    lab_bias_pct = round(lab_strength_dir * idr_w["lab_bias"], 2)
    dow_adj = float(np.clip(raw_dow_x * idr_w["dow"], -0.4, 0.4))
    wick_adj = round(float(np.clip(raw_wick_x * (idr_w["wick"] / 0.80), -0.55, 0.55)), 2)

    tot_gap = float(np.clip(mg + fg + ng + wg + lg_open, -5.0, 5.0))

    raw_calib_pct, calib_n = _compute_self_calibration(stock_hist, df_1d, market_today_str)
    calib_pct = round(float(np.clip(raw_calib_pct * (idr_w["calib"] / 0.40), -0.65, 0.65)), 2)

    # B-1: ベンチマーク5分足マップ構築（指数ベータ分離α＋β予測）
    bench_day_rmaps = {}
    bench_today_rmap = {}
    bench_beta_5m = float(np.clip(mi.get("beta", 0.8), -2.5, 2.5))
    has_bench_5m = False
    if df_bench_5m is not None and not df_bench_5m.empty:
        tmp_b = df_bench_5m.copy()
        idx_b = _convert_5m_index_to_market_tz(tmp_b, is_jp)
        tmp_b["_d"], tmp_b["_hm"] = idx_b.strftime("%Y-%m-%d"), idx_b.strftime("%H:%M")
        for ds_b, sub_b in tmp_b.groupby("_d"):
            if len(sub_b) >= 5:
                op_b = float(sub_b["Open"].iloc[0])
                if op_b > 0:
                    rm_b = {r["_hm"]: (float(r["Close"]) - op_b) / op_b for _, r in sub_b.iterrows() if r["_hm"] in slots}
                    if rm_b:
                        if ds_b == market_today_str:
                            bench_today_rmap = rm_b
                        else:
                            bench_day_rmaps[ds_b] = rm_b
        if len(bench_day_rmaps) >= 5:
            has_bench_5m = True

    slot_means, slot_stds, slot_vols = np.zeros(n_slots), np.full(n_slots, 0.003), np.zeros(n_slots)
    slot_inc_stds = np.full(n_slots, 0.0022)
    slot_q10, slot_q25, slot_q75, slot_q90 = np.zeros(n_slots), np.zeros(n_slots), np.zeros(n_slots), np.zeros(n_slots)
    regime_tag = "標準"
    rmaps, alpha_rmaps, rdates, day_gaps_hist = [], [], [], []
    gap_fill_stats = {"prob": None, "avg_min": None, "n_samples": 0, "dir": "FLAT"}

    if df_5m is not None and not df_5m.empty:
        tmp = df_5m.copy()
        idx_dt = _convert_5m_index_to_market_tz(tmp, is_jp)
        tmp["_d"], tmp["_hm"] = idx_dt.strftime("%Y-%m-%d"), idx_dt.strftime("%H:%M")
        udays = sorted(tmp["_d"].unique().tolist())
        pdays = [d for d in udays if d != market_today_str]
        vmaps, weights = [], []
        prev_day_close = None
        want_gu = tot_gap >= 0.15
        want_gd = tot_gap <= -0.15
        regime_tag = "GU類似加重" if want_gu else ("GD類似加重" if want_gd else "フラット加重")

        gf_total, gf_filled, gf_mins = 0, 0, []
        target_gap_dir = 1 if tot_gap >= 0.15 else (-1 if tot_gap <= -0.15 else 0)

        # B-1: 5分足ベータの実測推定（共通日付の終盤リターンから算出）
        if has_bench_5m:
            stk_end_rets, bmk_end_rets = [], []
            for ds in pdays:
                if ds in bench_day_rmaps:
                    sub_s = tmp[tmp["_d"] == ds]
                    if len(sub_s) >= 10:
                        op_s = float(sub_s["Open"].iloc[0])
                        cl_s = float(sub_s["Close"].iloc[-1])
                        b_vals = list(bench_day_rmaps[ds].values())
                        if op_s > 0 and b_vals:
                            stk_end_rets.append((cl_s - op_s) / op_s)
                            bmk_end_rets.append(b_vals[-1])
            if len(stk_end_rets) >= 6:
                vb = float(np.var(bmk_end_rets))
                if vb > 1e-8:
                    cov_sb = float(np.cov(stk_end_rets, bmk_end_rets)[0, 1])
                    bench_beta_5m = float(np.clip(cov_sb / vb, -2.5, 2.5))

        for di, ds in enumerate(pdays):
            sub = tmp[tmp["_d"] == ds]
            if len(sub) < 10:
                continue
            op = float(sub["Open"].iloc[0])
            cl_end = float(sub["Close"].iloc[-1])
            if op <= 0:
                continue
            day_gap = ((op - prev_day_close) / prev_day_close * 100.0) if (prev_day_close and prev_day_close > 0) else 0.0

            if prev_day_close and prev_day_close > 0 and abs(day_gap) >= 0.20:
                if target_gap_dir == 0 or (day_gap * target_gap_dir > 0):
                    gf_total += 1
                    lows_s = sub["Low"].values
                    highs_s = sub["High"].values
                    hit_idx = None
                    if day_gap > 0:
                        hits = np.where(lows_s <= prev_day_close)[0]
                        hit_idx = int(hits[0]) if len(hits) > 0 else None
                    else:
                        hits = np.where(highs_s >= prev_day_close)[0]
                        hit_idx = int(hits[0]) if len(hits) > 0 else None
                    if hit_idx is not None:
                        gf_filled += 1
                        gf_mins.append((hit_idx + 1) * 5)

            prev_day_close = cl_end

            rm, arm, vm = {}, {}, {}
            b_rm = bench_day_rmaps.get(ds, {}) if has_bench_5m else {}
            for _, row in sub.iterrows():
                hm_k = row["_hm"]
                if hm_k in slots:
                    raw_r = (float(row["Close"]) - op) / op
                    rm[hm_k] = raw_r
                    if has_bench_5m and hm_k in b_rm:
                        arm[hm_k] = raw_r - bench_beta_5m * b_rm[hm_k]
                    else:
                        arm[hm_k] = raw_r
                    vm[hm_k] = float(row["Volume"])
            if rm:
                base_w = float(np.exp(1.2 * (di / max(len(pdays) - 1, 1))))
                if (want_gu and day_gap > 0.1) or (want_gd and day_gap < -0.1):
                    base_w *= 2.5
                rmaps.append(rm)
                alpha_rmaps.append(arm)
                rdates.append(ds)
                day_gaps_hist.append(day_gap)
                vmaps.append(vm)
                weights.append(base_w)

        if gf_total >= 2:
            gap_fill_stats = {
                "prob": round(gf_filled / gf_total * 100.0, 0),
                "avg_min": int(round(float(np.mean(gf_mins)), 0)) if gf_mins else None,
                "n_samples": gf_total,
                "dir": "GU" if target_gap_dir > 0 else ("GD" if target_gap_dir < 0 else "BOTH"),
            }

        # B-1 & C-1: 純粋個別アルファ軌道 + ノンパラメトリック分位点（10/25/50/75/90%）
        use_maps = alpha_rmaps if has_bench_5m else rmaps
        for i, sl in enumerate(slots):
            rv, wv, vv = [], [], []
            for rm_u, vm, w in zip(use_maps, vmaps, weights):
                if sl in rm_u:
                    rv.append(rm_u[sl])
                    wv.append(w)
                    vv.append(vm[sl])
            if len(rv) >= 3:
                wa = np.array(wv, dtype=float) / np.sum(wv)
                ra = np.array(rv, dtype=float)
                wm = float(np.sum(wa * ra))
                slot_means[i] = wm
                slot_stds[i] = max(float(np.sqrt(np.sum(wa * ((ra - wm) ** 2)))), 0.0025)
                slot_vols[i] = float(np.mean(vv)) if vv else 0.0

                # 加重分位点（ノンパラメトリック・スキュー分布）
                ord_idx = np.argsort(ra)
                ra_s = ra[ord_idx]
                wa_s = wa[ord_idx]
                cdf_s = np.cumsum(wa_s) - 0.5 * wa_s
                slot_q10[i] = float(np.interp(0.10, cdf_s, ra_s))
                slot_q25[i] = float(np.interp(0.25, cdf_s, ra_s))
                slot_q75[i] = float(np.interp(0.75, cdf_s, ra_s))
                slot_q90[i] = float(np.interp(0.90, cdf_s, ra_s))
            else:
                sd_fb = 0.003 + 0.009 * np.sqrt((i + 1) / n_slots)
                slot_stds[i] = sd_fb
                slot_q10[i] = -1.28 * sd_fb
                slot_q25[i] = -0.67 * sd_fb
                slot_q75[i] = 0.67 * sd_fb
                slot_q90[i] = 1.28 * sd_fb
                slot_vols[i] = 0.0

        # B-2: U字型ボラティリティ曲線（各5分足スロット増分標準偏差 σ_{Δ,k}）
        for i in range(n_slots):
            sl_cur = slots[i]
            sl_prev = slots[i - 1] if i > 0 else None
            inc_vals, inc_ws = [], []
            for rm_u, w in zip(use_maps, weights):
                if sl_prev is None:
                    if sl_cur in rm_u:
                        inc_vals.append(rm_u[sl_cur])
                        inc_ws.append(w)
                else:
                    if sl_cur in rm_u and sl_prev in rm_u:
                        inc_vals.append(rm_u[sl_cur] - rm_u[sl_prev])
                        inc_ws.append(w)
            if len(inc_vals) >= 3:
                wa_i = np.array(inc_ws, dtype=float) / np.sum(inc_ws)
                ia = np.array(inc_vals, dtype=float)
                im = float(np.sum(wa_i * ia))
                slot_inc_stds[i] = max(float(np.sqrt(np.sum(wa_i * ((ia - im) ** 2)))), 0.0012)
            else:
                u_shape = 1.35 if (i < 6 or i >= n_slots - 6) else 0.85
                slot_inc_stds[i] = 0.0022 * u_shape

    rvol = None
    vol_spikes = []
    if has_actual:
        cum_act_v, cum_avg_v = 0.0, 0.0
        for i, sl in enumerate(slots):
            if sl in act_vol_map:
                av = act_vol_map[sl]
                avg_v = float(slot_vols[i])
                cum_act_v += av
                cum_avg_v += avg_v
                if avg_v > 0 and av >= avg_v * 2.5 and actual_arr[i] is not None:
                    vol_spikes.append({
                        "time": sl, "price": actual_arr[i],
                        "dir": act_dir_map.get(sl, 1), "ratio": round(av / avg_v, 1)
                    })
        if cum_avg_v > 0:
            rvol = round(cum_act_v / cum_avg_v, 2)

    pos_vols = [v for v in slot_vols if v > 0]
    avg_5m_vol = float(np.mean(pos_vols)) if pos_vols else (float(df_1d["Volume"].tail(20).mean()) / max(n_slots, 1))

    cvd_div = _detect_cvd_divergence(slots, actual_arr, cvd_arr, act_vol_map)
    gap_open15 = _evaluate_gap_open15(
        has_actual, slots, actual_arr, vwap_arr,
        act_low_map, act_high_map, act_vol_map, slot_vols, prev_px
    )

    est_open = anchor_base_close * (1.0 + tot_gap / 100.0)
    drift = float(np.clip((raw_news_x * idr_w["news"]) + ((dow_adj + wick_adj + calib_pct + lab_bias_pct) / 100.0), -0.032, 0.032))
    vboost = (1.0 + abs(raw_news_x) * 0.25) * (1.0 + max(0.0, vix_d / 100.0) * 1.2)

    # B-2: U字型ボラティリティ積分 sqrt(sum_{k=t+1}^T sigma_{Delta,k}^2)
    start_rem_idx = (last_act_idx + 1) if (has_actual and last_act_idx >= 0) else 0
    rem_frac_now = max((n_slots - 1 - last_act_idx) / max(n_slots - 1, 1), 0.04) if (has_actual and last_act_idx >= 0) else 1.0
    if start_rem_idx < n_slots:
        u_int_sigma = float(np.sqrt(np.sum(slot_inc_stds[start_rem_idx:] ** 2)))
    else:
        u_int_sigma = float(slot_inc_stds[-1]) * 0.5
    rem_sigma_pct = max(u_int_sigma, 0.002) * vboost

    hvn_wall_px, ob_sup_px = 0.0, 0.0
    if isinstance(active_lab, dict) and active_lab:
        d2_ctx = active_lab.get("daily_2y") if isinstance(active_lab.get("daily_2y"), dict) else {}
        hvn_wall_px = float(d2_ctx.get("hvn_wall_price", 0.0) or 0.0)
        ob_sup_px = float(active_lab.get("ob_support_px", 0.0) or 0.0)

    # C-1: ノンパラメトリック分位点ファン（10% / 25% / 50% / 75% / 90%）による非対称バンド構築
    p50, p85, p15, bdiff = [], [], [], []
    p68, p32, bdiff_inner = [], [], []
    for i, sl in enumerate(slots):
        frac = i / max(n_slots - 1, 1)
        mid = est_open * (1.0 + slot_means[i] + drift * frac)
        mid = _apply_hvn_ob_bounce(mid, hvn_wall_px, ob_sup_px, vp)

        up_out_spread = max((slot_q90[i] - slot_means[i]) * vboost, slot_stds[i] * vboost * 0.65)
        dn_out_spread = max((slot_means[i] - slot_q10[i]) * vboost, slot_stds[i] * vboost * 0.65)
        up_in_spread = max((slot_q75[i] - slot_means[i]) * vboost, up_out_spread * 0.42)
        dn_in_spread = max((slot_means[i] - slot_q25[i]) * vboost, dn_out_spread * 0.42)

        hi = mid + est_open * up_out_spread
        lo = max(mid - est_open * dn_out_spread, anchor_base_close * 0.5)
        hi_in = mid + est_open * up_in_spread
        lo_in = max(mid - est_open * dn_in_spread, anchor_base_close * 0.5)

        p50.append(round(float(mid), 2))
        p85.append(round(float(hi), 2))
        p15.append(round(float(lo), 2))
        bdiff.append(round(float(hi - lo), 2))
        p68.append(round(float(hi_in), 2))
        p32.append(round(float(lo_in), 2))
        bdiff_inner.append(round(float(hi_in - lo_in), 2))

    # リーク防止：寄り前に保存されたスナップショットのみを「朝ロック」として認定
    saved_today = stock_hist.get(market_today_str) if isinstance(stock_hist.get(market_today_str), dict) else None
    has_premarket_lock = bool(saved_today and saved_today.get("locked_premarket", True))

    if has_actual and has_premarket_lock:
        locked_p50 = saved_today["p50"]
        locked_p85 = saved_today["p85"]
        locked_p15 = saved_today["p15"]
        locked_bdiff = saved_today["band_diff"]
        locked_p32 = saved_today.get("p32", [round(m - (m - l) * 0.52, 2) for m, l in zip(locked_p50, locked_p15)])
        locked_bdiff_in = saved_today.get("band_diff_in", [round(d * 0.52, 2) for d in locked_bdiff])
        is_locked = True
    else:
        locked_p50, locked_p85, locked_p15, locked_bdiff = p50, p85, p15, bdiff
        locked_p32, locked_bdiff_in = p32, bdiff_inner
        is_locked = False
        if not has_actual:
            stock_hist[target_date] = {
                "p50": p50, "p85": p85, "p15": p15, "band_diff": bdiff,
                "p32": p32, "band_diff_in": bdiff_inner,
                "locked_premarket": True,
                "regime_code": regime_code,
                "cluster_key": cluster_key,
                "pred_open_px": round(float(est_open), 4),
                "pred_open_gap_pct": round(float(tot_gap), 4),
                "factor_contribs": {
                    "open_gap": {
                        "macro": round(raw_macro_x, 4),
                        "fx": round(raw_fx_x, 4),
                        "news": round(raw_news_x, 4),
                        "whale": round(raw_whale_x, 4),
                        "lab_bias": round(lab_strength_dir, 4),
                    },
                    "intraday_drift": {
                        "news": round(raw_news_x, 4),
                        "dow": round(raw_dow_x, 4),
                        "wick": round(raw_wick_x, 4),
                        "calib": round(raw_calib_pct, 4),
                        "lab_bias": round(lab_strength_dir, 4),
                    },
                },
            }
            if len(stock_hist) > 15:
                for old_k in sorted(stock_hist.keys())[:-15]:
                    del stock_hist[old_k]
            ledger[fc_code] = stock_hist
            _dd_db_set("dd_forecast_ledger_v9", ledger)

    # B-4 & C-1: k-NN類似日マッチ（ATR正規化＋コサイン類似度＋RVOL近さ＋ギャップ方向一致）＋スパゲッティ投影パス
    knn_match = {"matched_dates": [], "mean_dist": None, "knn_rel_moves": {}, "knn_q10": {}, "knn_q90": {}, "analog_paths": []}
    atr_norm_pct = max(vol_cls["atr_pct"] / 100.0, 0.005)
    if has_actual and last_act_idx >= 2 and rmaps:
        valid_slots = [slots[i] for i in range(last_act_idx + 1) if actual_arr[i] is not None]
        if len(valid_slots) >= 3:
            first_px = actual_map[valid_slots[0]]
            today_gap_now = (first_px - prev_px) / max(prev_px, 1e-4) * 100.0
            today_vec = np.array([(actual_map[sl] - first_px) / max(first_px, 1e-4) for sl in valid_slots], dtype=float) / atr_norm_pct
            today_norm = float(np.linalg.norm(today_vec))
            cands = []
            for ds, rm, vm, d_gap in zip(rdates, rmaps, vmaps, day_gaps_hist):
                if all(sl in rm for sl in valid_slots):
                    hist_vec = np.array([rm[sl] for sl in valid_slots], dtype=float) / atr_norm_pct
                    hist_norm = float(np.linalg.norm(hist_vec))
                    if today_norm > 1e-6 and hist_norm > 1e-6:
                        cos_sim = float(np.dot(today_vec, hist_vec) / (today_norm * hist_norm))
                    else:
                        cos_sim = 1.0 - min(float(np.linalg.norm(today_vec - hist_vec)), 1.0)
                    cos_dist = (1.0 - cos_sim) * 0.5

                    # RVOL類似ペナルティ
                    rvol_pen = 0.0
                    if rvol is not None and rvol > 0:
                        hist_v_sum = sum(vm.get(sl, 0.0) for sl in valid_slots)
                        avg_v_sum = sum(float(slot_vols[slots.index(sl)]) for sl in valid_slots)
                        if avg_v_sum > 0:
                            hist_rvol = hist_v_sum / avg_v_sum
                            rvol_pen = min(abs(math.log(max(rvol, 0.1) / max(hist_rvol, 0.1))) * 0.18, 0.35)

                    # ギャップ方向一致ボーナス
                    gap_pen = 0.0
                    if abs(today_gap_now) >= 0.25:
                        if today_gap_now * d_gap < 0:
                            gap_pen = 0.22
                        elif abs(today_gap_now - d_gap) <= 0.6:
                            gap_pen = -0.06

                    comp_dist = max(0.001, cos_dist + rvol_pen + gap_pen)
                    cands.append((comp_dist, ds, rm))

            if cands:
                cands.sort(key=lambda x: x[0])
                top_k = cands[:5]
                dists = np.array([c[0] for c in top_k], dtype=float)
                w_knn = 1.0 / (dists + 0.02)
                w_knn /= w_knn.sum()
                anchor_sl = slots[last_act_idx]
                anchor_px_now = actual_arr[last_act_idx]
                knn_rel, knn_q10_m, knn_q90_m = {}, {}, {}

                for i in range(last_act_idx, n_slots):
                    sl = slots[i]
                    vals_i, ws_i = [], []
                    for (_, _, rm_k), wk in zip(top_k, w_knn):
                        if sl in rm_k and anchor_sl in rm_k:
                            vals_i.append(rm_k[sl] - rm_k[anchor_sl])
                            ws_i.append(wk)
                    if vals_i:
                        ws_arr = np.array(ws_i) / np.sum(ws_i)
                        va_arr = np.array(vals_i)
                        knn_rel[i] = float(np.sum(ws_arr * va_arr))
                        knn_q10_m[i] = float(np.min(va_arr))
                        knn_q90_m[i] = float(np.max(va_arr))

                # スパゲッティ・プロット用の実測投影パス生成
                analog_paths = []
                for rank_idx, (_, ds_k, rm_k) in enumerate(top_k):
                    if anchor_sl not in rm_k:
                        continue
                    path_arr = [None] * n_slots
                    for i in range(last_act_idx, n_slots):
                        sl = slots[i]
                        if sl in rm_k:
                            rel_d = rm_k[sl] - rm_k[anchor_sl]
                            path_arr[i] = round(float(anchor_px_now * (1.0 + rel_d)), 2)
                    analog_paths.append({"date": ds_k, "data": path_arr})

                knn_match = {
                    "matched_dates": [c[1] for c in top_k],
                    "mean_dist": round(float(np.mean(dists)), 4),
                    "knn_rel_moves": knn_rel,
                    "knn_q10": knn_q10_m,
                    "knn_q90": knn_q90_m,
                    "analog_paths": analog_paths,
                }

    # B-1 & C-1: 場中ライブ修正（指数5分足ベータ追従＋ノンパラメトリック分位点＋U字型ボラティリティ積分）
    live_vwap_bias = 0.0
    bench_live_alpha_adj = 0.0
    if has_actual and last_act_idx >= 0:
        live_p50, live_p85, live_p15, live_bdiff = [None] * n_slots, [None] * n_slots, [None] * n_slots, [None] * n_slots
        live_p32, live_bdiff_in = [None] * n_slots, [None] * n_slots
        anchor_px = actual_arr[last_act_idx]
        anchor_mean = slot_means[last_act_idx]
        cur_vwap = vwap_arr[last_act_idx] or anchor_px
        vwap_gap = (anchor_px - cur_vwap) / max(cur_vwap, 1e-4)

        recent_vals = [v for v in actual_arr[max(0, last_act_idx - 6):last_act_idx + 1] if v is not None]
        mom_30m = ((recent_vals[-1] - recent_vals[0]) / max(recent_vals[0], 1e-4)) if len(recent_vals) >= 2 else 0.0
        gap15_bias = float(gap_open15.get("bias", 0.0))

        # B-1: 当日ベンチマーク指数の5分足モメンタムを掛け戻して地合い追従
        if has_bench_5m and bench_today_rmap:
            b_today_vals = [bench_today_rmap[slots[k]] for k in range(last_act_idx + 1) if slots[k] in bench_today_rmap]
            if len(b_today_vals) >= 2:
                b_mom_now = b_today_vals[-1] - b_today_vals[max(0, len(b_today_vals) - 6)]
                bench_live_alpha_adj = float(np.clip(bench_beta_5m * b_mom_now * 0.45, -0.012, 0.012))

        live_vwap_bias = float(np.clip(vwap_gap * 0.45 + mom_30m * 0.35 + gap15_bias + bench_live_alpha_adj, -0.020, 0.020))
        knn_moves = knn_match["knn_rel_moves"]
        knn_q10_m = knn_match["knn_q10"]
        knn_q90_m = knn_match["knn_q90"]

        for i in range(last_act_idx, n_slots):
            rem_frac = (i - last_act_idx) / max(n_slots - 1 - last_act_idx, 1)
            base_rel = (slot_means[i] - anchor_mean) + (drift * 0.6 + live_vwap_bias) * rem_frac
            rel_move = (0.70 * base_rel + 0.30 * knn_moves[i]) if (i in knn_moves) else base_rel
            mid = anchor_px * (1.0 + rel_move)
            mid = _apply_hvn_ob_bounce(mid, hvn_wall_px, ob_sup_px, vp)

            # B-2: U字型スロット増分ボラティリティ積分
            if i == last_act_idx:
                u_step_sig = 0.0012
            else:
                u_step_sig = float(np.sqrt(np.sum(slot_inc_stds[last_act_idx + 1:i + 1] ** 2)))

            # C-1: ノンパラメトリック分位点非対称スケール＋k-NNテール合成
            skew_up = max((slot_q90[i] - slot_means[i]) / max(slot_stds[i], 1e-4), 0.75)
            skew_dn = max((slot_means[i] - slot_q10[i]) / max(slot_stds[i], 1e-4), 0.75)
            up_band = anchor_px * max(u_step_sig * skew_up * vboost, 0.0015)
            dn_band = anchor_px * max(u_step_sig * skew_dn * vboost, 0.0015)

            if i in knn_q90_m and i in knn_q10_m:
                knn_hi_px = anchor_px * (1.0 + knn_q90_m[i])
                knn_lo_px = anchor_px * (1.0 + knn_q10_m[i])
                up_band = 0.75 * up_band + 0.25 * max(knn_hi_px - mid, up_band * 0.5)
                dn_band = 0.75 * dn_band + 0.25 * max(mid - knn_lo_px, dn_band * 0.5)

            hi = mid + up_band
            lo = max(mid - dn_band, anchor_px * 0.5)
            hi_in = mid + up_band * 0.52
            lo_in = max(mid - dn_band * 0.52, anchor_px * 0.5)

            live_p50[i] = round(float(mid), 2)
            live_p85[i] = round(float(hi), 2)
            live_p15[i] = round(float(lo), 2)
            live_bdiff[i] = round(float(hi - lo), 2)
            live_p32[i] = round(float(lo_in), 2)
            live_bdiff_in[i] = round(float(hi_in - lo_in), 2)
    else:
        live_p50, live_p85, live_p15, live_bdiff = p50, p85, p15, bdiff
        live_p32, live_bdiff_in = p32, bdiff_inner

    rem_drift_pct = ((drift * 0.6 + live_vwap_bias) * rem_frac_now) if has_actual else drift

    # 朝ロック検証＋D-2監査用メトリクス保存
    verify_stats = {"has_verify": False, "in_cone_pct": 0.0, "err_pct": 0.0, "n_pts": 0}
    if has_actual and is_locked:
        in_c, errs = 0, []
        for a, lo, hi, m in zip(actual_arr, locked_p15, locked_p85, locked_p50):
            if a is not None:
                if lo <= a <= hi:
                    in_c += 1
                errs.append(abs(a - m) / max(m, 1e-4) * 100.0)
        if errs:
            verify_stats = {
                "has_verify": True,
                "in_cone_pct": round(in_c / len(errs) * 100.0, 1),
                "err_pct": round(float(np.mean(errs)), 2),
                "n_pts": len(errs),
            }
            if len(errs) >= 4 and isinstance(saved_today, dict):
                saved_today["verify_result"] = {
                    "in_cone_pct": verify_stats["in_cone_pct"],
                    "err_pct": verify_stats["err_pct"],
                    "rvol_hi": bool(rvol is not None and rvol >= 1.3),
                }
                stock_hist[market_today_str] = saved_today
                ledger[fc_code] = stock_hist
                _dd_db_set("dd_forecast_ledger_v9", ledger)

    # D-2: メタ信頼度（Meta-Labeling）監査バッジ算出
    meta_audit = _audit_meta_labeling_accuracy(ledger, fc_code, is_jp, regime_code, rvol, tot_gap)

    inv_reasons = []
    if has_actual and last_act_idx >= 0:
        cur_a = actual_arr[last_act_idx]
        if is_locked:
            lo_l, hi_l = locked_p15[last_act_idx], locked_p85[last_act_idx]
            bw_l = max(hi_l - lo_l, cur_a * 0.005)
            if cur_a > hi_l + bw_l * 0.5:
                inv_reasons.append("上方向へ予測バンド大幅ブレイク（想定超え急騰）")
            elif cur_a < lo_l - bw_l * 0.5:
                inv_reasons.append("下方向へ予測バンド大幅割れ（想定超え急落）")
            if verify_stats["n_pts"] >= 6 and verify_stats["in_cone_pct"] < 45.0:
                inv_reasons.append(f"朝ロック予測の収束率が低下（{verify_stats['in_cone_pct']}%）")
        if isinstance(active_lab, dict) and float(active_lab.get("expect_pct", 0.0)) >= 70.0:
            l_side = _extract_lab_side(active_lab)
            day_chg_now = (cur_a - anchor_base_close) / max(anchor_base_close, 1e-4) * 100.0
            if (l_side == "LONG" and day_chg_now <= -1.5) or (l_side == "SHORT" and day_chg_now >= 1.5):
                inv_reasons.append(f"LAB強シグナル({l_side})に対し実測が大きく逆行({day_chg_now:+.2f}%)")
        if knn_match["mean_dist"] is not None and knn_match["mean_dist"] > 0.65:
            inv_reasons.append(f"k-NN過去類似日と大きく乖離（未知レジーム: dist={knn_match['mean_dist']}）")

    invalidation_alert = {
        "triggered": len(inv_reasons) > 0,
        "severity": "HIGH" if len(inv_reasons) >= 2 else ("MEDIUM" if inv_reasons else "NONE"),
        "reasons": inv_reasons
    }

    # 朝ロック基準指標
    imin_lk, imax_lk = int(np.argmin(locked_p50)), int(np.argmax(locked_p50))
    locked_trig_idx = min(3, n_slots - 1)

    # ライブ基準指標（場中有効部分から算出）
    valid_live_indices = [i for i, v in enumerate(live_p50) if v is not None]
    if valid_live_indices:
        imin_lv = min(valid_live_indices, key=lambda i: live_p50[i])
        imax_lv = max(valid_live_indices, key=lambda i: live_p50[i])
        lv_trig_idx = valid_live_indices[min(2, len(valid_live_indices) - 1)]
        lv_close_px = live_p50[valid_live_indices[-1]]
        lv_bull_tgt = round(max(live_p85[i] for i in valid_live_indices), 2)
        lv_bear_tgt = round(min(live_p15[i] for i in valid_live_indices), 2)
        lv_bull_trig = round(live_p85[lv_trig_idx], 2)
        lv_bear_trig = round(live_p15[lv_trig_idx], 2)
    else:
        imin_lv, imax_lv = imin_lk, imax_lk
        lv_close_px = locked_p50[-1]
        lv_bull_tgt = round(max(locked_p85), 2)
        lv_bear_tgt = round(min(locked_p15), 2)
        lv_bull_trig = round(locked_p85[locked_trig_idx], 2)
        lv_bear_trig = round(locked_p15[locked_trig_idx], 2)

    return {
        "target_date": target_date, "is_locked": is_locked, "has_actual": has_actual, "last_act_idx": last_act_idx,
        "anchor_base_close": anchor_base_close,
        "slots": slots, "lunch_idx": lunch_idx, "vols": [round(float(v), 1) for v in slot_vols],
        "actual": actual_arr, "vwap": vwap_arr,
        "vwap_p1": vwap_p1_arr, "vwap_m1": vwap_m1_arr, "vwap_p2": vwap_p2_arr, "vwap_m2": vwap_m2_arr,
        "rvol": rvol, "orb_high": orb_high, "orb_low": orb_low, "vol_spikes": vol_spikes,
        "avg_5m_vol": avg_5m_vol, "cvd_div": cvd_div, "gap_open15": gap_open15,
        "gap_fill": gap_fill_stats, "rem_sigma_pct": rem_sigma_pct, "rem_drift_pct": rem_drift_pct, "rem_frac_now": rem_frac_now,
        "locked_p50": locked_p50, "locked_p85": locked_p85, "locked_p15": locked_p15, "locked_bdiff": locked_bdiff,
        "locked_p32": locked_p32, "locked_bdiff_in": locked_bdiff_in,
        "live_p50": live_p50, "live_p85": live_p85, "live_p15": live_p15, "live_bdiff": live_bdiff,
        "live_p32": live_p32, "live_bdiff_in": live_bdiff_in,
        "est_open_px": round(est_open, 2), "est_open_gap_pct": round(tot_gap, 2),
        # 朝ロック値
        "locked_close_px": locked_p50[-1],
        "locked_close_chg": round((locked_p50[-1] - anchor_base_close) / max(anchor_base_close, 1e-4) * 100.0, 2),
        "locked_dip_idx": imin_lk, "locked_dip_time": slots[imin_lk], "locked_dip_px": locked_p50[imin_lk],
        "locked_peak_idx": imax_lk, "locked_peak_time": slots[imax_lk], "locked_peak_px": locked_p50[imax_lk],
        "locked_bull_trig": round(locked_p85[locked_trig_idx], 2), "locked_bull_target": round(max(locked_p85), 2),
        "locked_bear_trig": round(locked_p15[locked_trig_idx], 2), "locked_bear_target": round(min(locked_p15), 2),
        # ライブ修正値
        "live_close_px": lv_close_px,
        "live_close_chg": round((lv_close_px - anchor_base_close) / max(anchor_base_close, 1e-4) * 100.0, 2),
        "live_dip_idx": imin_lv, "live_dip_time": slots[imin_lv], "live_dip_px": live_p50[imin_lv],
        "live_peak_idx": imax_lv, "live_peak_time": slots[imax_lv], "live_peak_px": live_p50[imax_lv],
        "live_bull_trig": lv_bull_trig, "live_bull_target": lv_bull_tgt,
        "live_bear_trig": lv_bear_trig, "live_bear_target": lv_bear_tgt,
        # デフォルト後方互換フィールド（後段でモード連動上書き）
        "est_close_px": lv_close_px if has_actual else locked_p50[-1],
        "est_close_chg": round(((lv_close_px if has_actual else locked_p50[-1]) - anchor_base_close) / max(anchor_base_close, 1e-4) * 100.0, 2),
        "dip_idx": imin_lv if has_actual else imin_lk,
        "dip_time": slots[imin_lv] if has_actual else slots[imin_lk],
        "dip_px": live_p50[imin_lv] if has_actual else locked_p50[imin_lk],
        "peak_idx": imax_lv if has_actual else imax_lk,
        "peak_time": slots[imax_lv] if has_actual else slots[imax_lk],
        "peak_px": live_p50[imax_lv] if has_actual else locked_p50[imax_lk],
        "bull_trig": lv_bull_trig if has_actual else round(locked_p85[locked_trig_idx], 2),
        "bull_target": lv_bull_tgt if has_actual else round(max(locked_p85), 2),
        "bear_trig": lv_bear_trig if has_actual else round(locked_p15[locked_trig_idx], 2),
        "bear_target": lv_bear_tgt if has_actual else round(min(locked_p15), 2),
        "verify": verify_stats, "meta_audit": meta_audit, "regime_tag": regime_tag,
        "has_bench_5m": has_bench_5m, "bench_beta_5m": round(bench_beta_5m, 2),
        "knn_match": {
            "matched_dates": knn_match["matched_dates"],
            "mean_dist": knn_match["mean_dist"],
            "analog_paths": knn_match["analog_paths"],
        },
        "invalidation_alert": invalidation_alert,
        "weights_evolution": {
            "active_cluster": cluster_key,
            "fallback_cluster": fallback_key,
            "cluster_n": cluster_n,
            "shrink_alpha": shrink_alpha,
            "vol_band": vol_cls["vol_band"],
            "atr_pct": vol_cls["atr_pct"],
            "active_regime": regime_code,
            "updates_count": w_evo.get("updates_count", 0),
            "regime_updates_count": cluster_n,
            "weights_updated": weights_updated,
            "open_gap": og_w,
            "intraday_drift": idr_w,
            "all_regimes": w_evo.get("clusters", {}).get(cluster_key, w_evo.get("regimes", {})),
            "last_decomp": w_evo.get("last_decomp", {}),
        },
        "factors": {
            "mkt_label": mi["label"], "mkt_diff": mi["latest_diff"], "mkt_beta": mi["beta"], "macro_gap_pct": round(mg, 2),
            "fx_diff": fi["latest_diff"], "fx_beta": fi["beta"], "fx_gap_pct": round(fg, 2),
            "news_gap_pct": round(ng, 2), "whale_gap_pct": round(wg, 2),
            "lab_bias_pct": lab_bias_pct,
            "hvn_wall_px": hvn_wall_px, "ob_sup_px": ob_sup_px,
            "dow_wick_pct": round(dow_adj + wick_adj, 2),
            "calib_pct": calib_pct, "calib_n": calib_n,
            "live_vwap_pct": round(live_vwap_bias * 100.0, 2),
            "bench_alpha_pct": round(bench_live_alpha_adj * 100.0, 2),
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


@st.cache_data(ttl=900, show_spinner=False)
def _generate_detailed_memo_cached(
    fc: str, corp_name: str, px_s: str, traj_open: str, traj_close: str,
    bull_trig: str, bull_tgt: str, bear_trig: str, bear_tgt: str,
    dip_t: str, peak_t: str, ovh: float, res_s: str, sup_s: str,
    ml: str, mc: float, mb: float, pos_pct: int, t1: int, gov_cnt: int,
    whale_sum: str, up: str, lab_note: str, api_key: str, lab_deep_ctx: str = "", memo_nonce: int = 0
) -> tuple:
    lab_block = f"\n・LAB本体統合データ: {lab_deep_ctx}" if lab_deep_ctx else ""
    prompt = f"""あなたはヘッジファンドのシニア・エクイティアナリストです。以下の実測データに基づき「超詳細インベストメントメモ（800〜1,100文字）」を日本語で作成してください。
・銘柄: {corp_name} ({fc}) / 現在値: {px_s} / アナリスト目標乖離: {up}
・LAB本体判定: {lab_note}{lab_block}
・予測軌道: 想定始値 {traj_open} → 大引け予測 {traj_close}（押し目候補 {dip_t} / ピーク想定 {peak_t}）
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
                        return txt.strip(), f"🔵 AUTO GLOBAL AI ANALYST ({mod} / 一次報道{t1}件 / 15mキャッシュ)"
            except Exception:
                continue

    lab_extra = f"\n・LAB連携情報: {lab_deep_ctx}" if lab_deep_ctx else ""
    bull = f"・LAB本体判定: {lab_note}{lab_extra}。現在値 {px_s} に対しアナリスト目標乖離は {up}、高信頼ニュース強気度 {pos_pct}%（一次報道{t1}件）。\n・{bull_trig} を明確に上抜ければ強気突破が発動し、上値メド {bull_tgt} を目指す展開。\n・下値は大口買い支え帯 {sup_s} がサポートとして機能しやすい構造。"
    bear = f"・{ml} との相関係数が {mc}（β={mb}）で、夜間先物や米市場の急変時に連れ安リスクあり。\n・上値しこり玉は {ovh}%、直上の大口売り壁 {res_s} 付近では戻り売りに要注意。\n・{bear_trig} 割れで下値メド {bear_tgt} までの下振れを警戒し早期撤退。ガバナンス報道は {gov_cnt}件検知。"
    cat = f"・大口・インサイダー動向: {whale_sum}。\n・勝負時間帯は押し目候補の {dip_t} 前後での反発確認と、ピーク想定の {peak_t} 前後での分割利確。\n・寄付直後に想定始値 {traj_open} を維持できるかが最初の分岐点。"
    return f"🟢 Bull Case（強気シナリオ）\n{bull}\n\n🔴 Bear Case（弱気・死角リスク）\n{bear}\n\n⚡ Next Catalyst（注目トリガー）\n{cat}", f"⚙️ AUTO QUANT MEMO（一次報道{t1}件・実測詳細生成）"


def _resolve_shared_lab_entry(fc: str, lab_ctx: dict = None) -> dict:
    merged = {}
    shared_ss = st.session_state.get("shared_ticker_intel")
    if isinstance(shared_ss, dict) and isinstance(shared_ss.get(fc), dict):
        merged.update(shared_ss[fc])
    shared_db = _dd_db_get("shared_ticker_intel", {})
    if isinstance(shared_db, dict) and isinstance(shared_db.get(fc), dict):
        for k, v in shared_db[fc].items():
            if k not in merged or merged[k] is None:
                merged[k] = v
    if isinstance(lab_ctx, dict) and lab_ctx:
        if lab_ctx.get("full_code") == fc or not lab_ctx.get("full_code"):
            merged.update(lab_ctx)
            if "lab_full" not in merged and any(k in lab_ctx for k in ("side", "expect_pct", "tp", "sl", "exec_grade")):
                merged["lab_full"] = lab_ctx
    return merged


def _format_lab_deep_context(lab_full: dict, lab_council: dict) -> str:
    parts = []
    if isinstance(lab_full, dict) and lab_full:
        side_s = _extract_lab_side(lab_full)
        if side_s or lab_full.get("expect_pct"):
            parts.append(f"方向={side_s}/期待度={lab_full.get('expect_pct','-')}%/グレード={lab_full.get('exec_grade','-')}")
        m10 = lab_full.get("macro_10y")
        if isinstance(m10, dict) and m10:
            parts.append(f"週足10Y(POC={m10.get('poc_10y_price','-')},CAGR={m10.get('cagr_pct', m10.get('cagr_10y','-'))},Score={m10.get('score', m10.get('long_10y_score','-'))})")
        d2 = lab_full.get("daily_2y")
        if isinstance(d2, dict) and d2:
            parts.append(f"日足2Y(MA={d2.get('ma_align', d2.get('ma_align_label','-'))},HVN={d2.get('hvn_wall_price','-')},ATR14={d2.get('atr14', d2.get('daily_atr14','-'))})")
        wf22 = lab_full.get("wf_22d") or lab_full.get("walk_forward_22d") or lab_full.get("forward_test")
        if isinstance(wf22, dict) and wf22:
            parts.append(f"22日検証(勝率={wf22.get('win_rate', wf22.get('actual_win_rate','-'))},PF={wf22.get('pf', wf22.get('profit_factor','-'))},SQN={wf22.get('sqn','-')},DD={wf22.get('max_dd', wf22.get('max_dd_pct','-'))})")
        q_ind = lab_full.get("quant_metrics") or lab_full.get("quants")
        if isinstance(q_ind, dict) and q_ind:
            parts.append(f"独自クオンツ(WKB={q_ind.get('wkb','-')},Kyle={q_ind.get('kyle_lambda','-')},VPIN={q_ind.get('vpin','-')},CLV={q_ind.get('clv','-')},RS30={q_ind.get('rs_30m','-')},OB={lab_full.get('ob_support_px','-')})")
    if isinstance(lab_council, dict) and lab_council:
        verdict_c = lab_council.get("verdict") or lab_council.get("conclusion") or lab_council.get("summary")
        if verdict_c:
            parts.append(f"5名監査官結論={verdict_c}")
    return " | ".join(parts)


def _render_unified_guide():
    st.markdown("""
    <div class="dd-guide-box">
    <b>🔰 最初に見る3ポイント</b><br>
    1. <b>予測軌道チャート:</b> 白線(実測)が青い非対称分位点ファン(10〜90%タイル)の中に収まっているかを確認。右上の <b>⛶ 横拡大</b> でスマホ横向きフル大画面にできます。<br>
    2. <b>ベイズ確率メーター＆シナリオカード:</b> 4シナリオのリアルタイム事後確率と「押し目・高値の時間帯」「上下トリガー価格」をチェック。<br>
    3. <b>What-If衝撃波シミュレーター＆適正ロット電卓:</b> 先物・為替の追加ショックをスライダーで模擬し、100株単元・流動性インパクト・U字ボラ積分FPT到達確率を即算出。<br>
    <hr style="border-color:rgba(56,189,248,0.22);margin:7px 0;">
    <b>■ v14 クオンツ魔改造ガイド</b><br>
    ・<b>指数ベータ分離(α+β):</b> 市場指数5分足を差し引いた純粋個別アルファ軌道＋場中リアルタイム地合い追従。<br>
    ・<b>U字型ボラティリティ曲線:</b> 寄り・引けのボラ増大を反映したスロット増分σ積分をバンド幅・FPT確率へ適用。<br>
    ・<b>スイング疑似CVD:</b> 5本スイング極値×出来高フィルタで大口の売り抜け・底値吸収を精密検出。<br>
    ・<b>クラスタ別3脳SGD＋L2正則化:</b> 市場(JP/US)×ボラ帯(LOW/MID/HIGH)×レジーム別に標準化リッジ学習。
    </div>
    """, unsafe_allow_html=True)


# =========================================================================
# 5. メインエントリ関数（YAMASHISHI LAB から呼び出す）
# =========================================================================
def render_deep_dive_page(init_code: str = "NVDA", init_style: str = "デイトレード", gemini_api_key: str = "", lab_ctx: dict = None):
    _inject_dd_css()

    h1, h2, h3 = st.columns([2.4, 1.0, 1.2])
    with h1:
        st.markdown(
            '<div class="glass-header" style="margin-bottom:4px;padding:8px 12px;">'
            '<div class="brand-luxury" style="font-size:15px;">YAMASHISHI DEEP DIVE v14</div>'
            '<div style="font-size:10px;color:#94a3b8;">α+β分離軌道・U字ボラFPT・ベイズ確率メーター・What-If衝撃波</div>'
            '</div>',
            unsafe_allow_html=True
        )
    with h2:
        st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
        if hasattr(st, "popover"):
            with st.popover("📖 見方", use_container_width=True):
                _render_unified_guide()
        else:
            with st.expander("📖 見方"):
                _render_unified_guide()
    with h3:
        st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
        if st.button("⬅️ LAB", key="dd_back_to_lab_btn", use_container_width=True, type="primary"):
            st.session_state["navigation_page"] = "TOP"
            st.session_state["scroll_top_trig"] = int(time.time() * 1000)
            st.rerun()

    STYLES = ["デイトレード", "スキャルピング", "スイングトレード", "バイ＆ホールド"]
    c1, c2, c3 = st.columns([1.8, 1.5, 1.0])
    in_code = c1.text_input("銘柄コード", value=init_code, placeholder="例: NVDA / 6920", label_visibility="collapsed", key="dd_code_in")
    in_style = c2.selectbox("スタイル", STYLES, index=STYLES.index(init_style) if init_style in STYLES else 0, label_visibility="collapsed", key="dd_style_in")
    auto_sync = c3.toggle("自動更新", value=True, key="dd_auto_sync", help="ONで60秒ごとに最新データへ自動同期します")

    fc = in_code.strip().upper()
    if not fc:
        return
    if re.match(r"^[0-9]{3}[0-9A-Z]$", fc):
        fc = f"{fc}.T"
    is_jp = fc.endswith(".T")
    api_k = _get_gemini_key(gemini_api_key)

    shared_entry = _resolve_shared_lab_entry(fc, lab_ctx)
    lab_full = shared_entry.get("lab_full") if isinstance(shared_entry.get("lab_full"), dict) else {}
    lab_council = shared_entry.get("lab_council") if isinstance(shared_entry.get("lab_council"), dict) else {}
    active_lab = lab_full if lab_full else (lab_ctx if (isinstance(lab_ctx, dict) and lab_ctx.get("full_code") == fc) else None)
    lab_deep_ctx = _format_lab_deep_context(lab_full, lab_council)

    def _body():
        _render_live_clock(sync_interval=60, active=auto_sync)
        with ThreadPoolExecutor(max_workers=3) as ex_core:
            fut_stk = ex_core.submit(_load_stock_core, fc)
            fut_mac = ex_core.submit(_load_macro_data)
            fut_bmk = ex_core.submit(_load_benchmark_5m, is_jp)
            data = fut_stk.result()
            macro_data = fut_mac.result()
            df_bench_5m = fut_bmk.result()

        if macro_data:
            chips = "".join([
                f'<div class="dd-macro-chip"><span style="color:#94a3b8;">{macro_data[k]["label"]}{"⚡" if macro_data[k].get("is_rt") else ""}</span>'
                f'<span style="color:{"#10b981" if macro_data[k]["diff_pct"]>=0 else "#ef4444"};font-weight:700;">{macro_data[k]["diff_pct"]:+.2f}%</span></div>'
                for k in ["SOX", "SP500", "NQ_FUT", "ES_FUT", "NK_FUT", "USDJPY", "US10Y", "OIL", "VIX"] if k in macro_data
            ])
            st.markdown(f'<div class="dd-macro-strip">{chips}</div>', unsafe_allow_html=True)

        df_1d, df_5m, info = data["df_1d"], data["df_5m"], data["info"]
        if df_1d is None or df_1d.empty:
            st.error(f"❌ 銘柄コード `{fc}` の市場データを取得できませんでした。")
            return

        corp_name = info.get("longName") or info.get("shortName") or fc
        short_code = fc.replace(".T", "")
        sector, industry = info.get("sector") or "セクター未分類", info.get("industry") or "-"

        # A-3: anchor_base_close（前日終値）の日付一致明示判定
        market_today_str = _get_market_now(is_jp).strftime("%Y-%m-%d")
        last_1d_str = df_1d.index[-1].strftime("%Y-%m-%d") if hasattr(df_1d.index[-1], "strftime") else str(df_1d.index[-1])[:10]
        curr_px = float(df_1d["Close"].iloc[-1])
        if last_1d_str == market_today_str:
            prev_px = float(df_1d["Close"].iloc[-2]) if len(df_1d) >= 2 else curr_px
        else:
            prev_px = curr_px

        chg_pct = ((curr_px - prev_px) / max(prev_px, 1e-4)) * 100.0
        chg_col = "#10b981" if chg_pct >= 0 else "#ef4444"

        mkt_regime = _detect_market_regime(df_1d)
        round_level = _compute_round_number_level(curr_px, is_jp)
        macro_sens = _compute_macro_sens(df_1d["Close"], macro_data)
        dow_stats, next_wd = _compute_dow_edge(df_1d, is_jp)
        with ThreadPoolExecutor(max_workers=2) as ex_intel:
            fut_news = ex_intel.submit(_fetch_global_intel, corp_name, short_code)
            fut_gov = ex_intel.submit(_fetch_gov_and_whales, corp_name, short_code)
            news_res = fut_news.result()
            gov_risks, whale_news = fut_gov.result()
        whale_anom = _detect_whale_anomaly(data["insider_tx"], whale_news, market_today_str)
        vp = _compute_vp(df_1d, curr_px, is_jp)
        traj = _build_dual_5m_trajectory(
            fc, curr_px, prev_px, df_1d, df_5m, macro_sens, macro_data,
            news_res, whale_anom, dow_stats[next_wd]["avg"], vp, is_jp,
            mkt_regime=mkt_regime, active_lab=active_lab, df_bench_5m=df_bench_5m
        )

        # A-2: チャートモード事前解決（ライブ修正 vs 朝ロック検証の完全連動）
        presets = ["📈 今の予測", "🔍 朝の答え合わせ", "🏦 大口・節目"]
        modes = ["🔴 ライブ修正", "🔒 朝ロック検証", "⚡ 両方重ね"]
        sel_preset_now = st.session_state.get("dd_preset_sel", "📈 今の予測")
        cur_chart_mode = st.session_state.get("dd_chart_mode", "⚡ 両方重ね")
        if st.session_state.get("dd_last_preset") != sel_preset_now:
            cur_chart_mode = modes[2 if sel_preset_now == "📈 今の予測" else (1 if sel_preset_now == "🔍 朝の答え合わせ" else 0)]

        # 場中(has_actual=True)かつ「ライブ修正」または「両方重ね」のとき、ライブ修正値を基準に連動
        use_live_basis = bool(traj["has_actual"] and cur_chart_mode in ("🔴 ライブ修正", "⚡ 両方重ね"))

        # D-3: What-If 衝撃波スライダー値を事前読取（存在すれば即反映）
        shock_idx_pct = float(st.session_state.get("dd_whatif_idx_pct", 0.0))
        shock_fx_yen = float(st.session_state.get("dd_whatif_fx_yen", 0.0))
        usdjpy_last = float(macro_data.get("USDJPY", {}).get("last", 150.0) or 150.0)
        shock_fx_pct = (shock_fx_yen / max(usdjpy_last, 1.0)) * 100.0

        f_map = traj["factors"]
        mkt_beta_eff = float(f_map.get("mkt_beta", 0.5))
        fx_beta_eff = float(f_map.get("fx_beta", 0.0))
        shock_ext_pct = round(shock_idx_pct * mkt_beta_eff + shock_fx_pct * fx_beta_eff, 3)
        shock_mult = 1.0 + (shock_ext_pct / 100.0)

        # 基準値の選択（朝ロック vs ライブ修正）＋ What-If 衝撃波反映
        if use_live_basis:
            base_close_px = traj["live_close_px"]
            base_bull_trig = traj["live_bull_trig"]
            base_bull_tgt = traj["live_bull_target"]
            base_bear_trig = traj["live_bear_trig"]
            base_bear_tgt = traj["live_bear_target"]
            active_dip_time = traj["live_dip_time"]
            active_dip_px = round(traj["live_dip_px"] * shock_mult, 2)
            active_peak_time = traj["live_peak_time"]
            active_peak_px = round(traj["live_peak_px"] * shock_mult, 2)
        else:
            base_close_px = traj["locked_close_px"]
            base_bull_trig = traj["locked_bull_trig"]
            base_bull_tgt = traj["locked_bull_target"]
            base_bear_trig = traj["locked_bear_trig"]
            base_bear_tgt = traj["locked_bear_target"]
            active_dip_time = traj["locked_dip_time"]
            active_dip_px = round(traj["locked_dip_px"] * shock_mult, 2)
            active_peak_time = traj["locked_peak_time"]
            active_peak_px = round(traj["locked_peak_px"] * shock_mult, 2)

        active_close_px = round(base_close_px * shock_mult, 2)
        active_close_chg = round((active_close_px - traj["anchor_base_close"]) / max(traj["anchor_base_close"], 1e-4) * 100.0, 2)
        active_bull_trig = round(base_bull_trig * shock_mult, 2)
        active_bull_tgt = round(base_bull_tgt * shock_mult, 2)
        active_bear_trig = round(base_bear_trig * shock_mult, 2)
        active_bear_tgt = round(base_bear_tgt * shock_mult, 2)
        active_open_gap_pct = round(traj["est_open_gap_pct"] + (shock_ext_pct if not traj["has_actual"] else 0.0), 2)
        active_open_px = round(traj["anchor_base_close"] * (1.0 + active_open_gap_pct / 100.0), 2)
        active_rem_drift = traj["rem_drift_pct"] + (shock_ext_pct / 100.0) * 0.65

        # What-If 反映後のチャート系列
        disp_locked_p50 = [round(v * shock_mult, 2) if v is not None else None for v in traj["locked_p50"]]
        disp_locked_p85 = [round(v * shock_mult, 2) if v is not None else None for v in traj["locked_p85"]]
        disp_locked_p15 = [round(v * shock_mult, 2) if v is not None else None for v in traj["locked_p15"]]
        disp_locked_bdiff = [round(v * shock_mult, 2) if v is not None else None for v in traj["locked_bdiff"]]
        disp_locked_p32 = [round(v * shock_mult, 2) if v is not None else None for v in traj["locked_p32"]]
        disp_locked_bdiff_in = [round(v * shock_mult, 2) if v is not None else None for v in traj["locked_bdiff_in"]]

        disp_live_p50 = [round(v * shock_mult, 2) if v is not None else None for v in traj["live_p50"]]
        disp_live_p85 = [round(v * shock_mult, 2) if v is not None else None for v in traj["live_p85"]]
        disp_live_p15 = [round(v * shock_mult, 2) if v is not None else None for v in traj["live_p15"]]
        disp_live_bdiff = [round(v * shock_mult, 2) if v is not None else None for v in traj["live_bdiff"]]
        disp_live_p32 = [round(v * shock_mult, 2) if v is not None else None for v in traj["live_p32"]]
        disp_live_bdiff_in = [round(v * shock_mult, 2) if v is not None else None for v in traj["live_bdiff_in"]]

        # D-1: ベイズ更新型・リアルタイムシナリオ事後確率の算出
        cur_vwap_now = traj["vwap"][traj["last_act_idx"]] if (traj["has_actual"] and traj["last_act_idx"] >= 0) else None
        scen_probs = _compute_bayesian_scenario_probs(
            traj["has_actual"], curr_px, traj["anchor_base_close"],
            active_open_gap_pct, active_close_chg,
            active_bull_trig, active_bull_tgt, active_bear_trig, active_bear_tgt,
            traj["rem_sigma_pct"], active_rem_drift,
            traj["rvol"], traj["cvd_div"], traj["gap_open15"],
            cur_vwap_now, shock_ext_pct=shock_ext_pct
        )

        # ステータス帯＆D-2 メタ信頼度監査バッジ
        status_pills = []
        alert_blocks = []
        meta_a = traj["meta_audit"]
        status_pills.append(
            f'<span class="dd-st-pill" style="border-color:{meta_a["color"]};background:rgba(15,23,42,0.88);color:{meta_a["color"]};">'
            f'🛡️ モデル信頼度: {html.escape(meta_a["rank"])}{f" ({meta_a[\"hit_rate\"]:.0f}%)" if meta_a["n"]>=3 else ""}</span>'
        )
        alert_blocks.append(f'<div class="dd-quant-box"><b>🛡️ Meta-Labeling モデル信頼度監査（ランク: {html.escape(meta_a["rank"])}）</b><br>{html.escape(meta_a["detail"])}</div>')

        ne_days = data.get("next_earnings_days")
        earn_badge = ""
        if ne_days is not None:
            e_col = "#ef4444" if ne_days <= 5 else "#f59e0b"
            earn_badge = f'<span class="pill-badge" style="border-color:{e_col};background:rgba(239,68,68,0.16);color:#fecaca;">決算あと{ne_days}日</span>'
            if ne_days <= 5:
                status_pills.append(f'<span class="dd-st-pill" style="border-color:#ef4444;background:rgba(239,68,68,0.18);color:#fecaca;">⚠️ 決算あと{ne_days}日</span>')
                alert_blocks.append(f'<div class="dd-warn-box"><b>⚠️ 決算イベント接近（あと {ne_days}日）</b><br>決算またぎは通常の5分足軌道モデルが機能しないボラティリティ急変リスクがあります。ポジション縮小を推奨します。</div>')

        cvd_div = traj["cvd_div"]
        if cvd_div["state"] == "DISTRIBUTION":
            status_pills.append('<span class="dd-st-pill" style="border-color:#ef4444;background:rgba(239,68,68,0.20);color:#fecaca;">🚨 疑似CVD売り抜け</span>')
            alert_blocks.append(f'<div class="dd-warn-box"><b>🚨 疑似オーダーフロー（CVD）天井売り抜け検知</b><br>{html.escape(cvd_div["detail"])}</div>')
        elif cvd_div["state"] == "ABSORPTION":
            status_pills.append('<span class="dd-st-pill" style="border-color:#10b981;background:rgba(16,185,129,0.18);color:#6ee7b7;">🧲 疑似CVD底値吸収</span>')
            alert_blocks.append(f'<div class="dd-quant-box"><b>🧲 疑似オーダーフロー（CVD）底値吸収検知</b><br>{html.escape(cvd_div["detail"])}</div>')

        g15 = traj["gap_open15"]
        if g15["status"] in ("GAP_AND_GO_UP", "GAP_AND_FADE_UP"):
            status_pills.append(f'<span class="dd-st-pill" style="border-color:#10b981;background:rgba(16,185,129,0.16);color:#6ee7b7;">⚡ {html.escape(g15["label"])}</span>')
            alert_blocks.append(f'<div class="dd-quant-box"><b>⚡ 寄り後15分判定: {html.escape(g15["label"])}</b><br>{html.escape(g15["detail"])}</div>')
        elif g15["status"] in ("GAP_AND_GO_DOWN", "GAP_AND_FADE_DOWN"):
            status_pills.append(f'<span class="dd-st-pill" style="border-color:#ef4444;background:rgba(239,68,68,0.18);color:#fecaca;">⚡ {html.escape(g15["label"])}</span>')
            alert_blocks.append(f'<div class="dd-warn-box"><b>⚡ 寄り後15分判定: {html.escape(g15["label"])}</b><br>{html.escape(g15["detail"])}</div>')

        inv_al = traj.get("invalidation_alert", {})
        if inv_al.get("triggered"):
            status_pills.append(f'<span class="dd-st-pill" style="border-color:#ef4444;background:rgba(239,68,68,0.22);color:#fecaca;">🚨 破棄アラート({inv_al["severity"]})</span>')
            alert_blocks.append(f'<div class="dd-warn-box"><b>🚨 予測軌道・破棄アラート発火（重要度: {inv_al["severity"]}）</b><br>' + "<br>".join([f"・{html.escape(r)}" for r in inv_al["reasons"]]) + "</div>")

        lab_note = "単体検索モード（LAB未経由）"
        if active_lab:
            l_side = _extract_lab_side(active_lab)
            l_tp = float(active_lab.get("tp", active_lab.get("raw_tp", 0.0)) or 0.0)
            l_sl = float(active_lab.get("sl", active_lab.get("raw_sl", 0.0)) or 0.0)
            dd_bull = (active_close_chg >= 0)
            is_aligned = (l_side == "LONG" and dd_bull) or (l_side == "SHORT" and not dd_bull)
            lab_note = f"LAB判定={l_side} (期待度{active_lab.get('expect_pct',0)}% / TP:{_fmt_cur(l_tp, is_jp)} / SL:{_fmt_cur(l_sl, is_jp)})"
            if is_aligned:
                status_pills.append(f'<span class="dd-st-pill" style="border-color:#10b981;background:rgba(16,185,129,0.16);color:#6ee7b7;">✅ LAB一致({l_side})</span>')
                alert_blocks.append(f'<div class="dd-quant-box"><b>✅ LAB × DEEP DIVE 方向性一致（{l_side} 同期）</b><br>LAB上位足判定（期待度 {active_lab.get("expect_pct",0)}% / {html.escape(str(active_lab.get("exec_grade","")).split("（")[0])}）と5分足予測軌道（{active_close_chg:+.2f}%）が一致。TP: <b>{_fmt_cur(l_tp, is_jp)}</b> / SL: <b>{_fmt_cur(l_sl, is_jp)}</b></div>')
            else:
                status_pills.append(f'<span class="dd-st-pill" style="border-color:#f59e0b;background:rgba(245,158,11,0.16);color:#fef3c7;">⚠️ LAB乖離({l_side})</span>')
                alert_blocks.append(f'<div class="dd-sync-warn"><b>⚠️ LAB × DEEP DIVE 方向性に乖離あり（慎重待機推奨）</b><br>LAB上位足判定は <b>{l_side}</b>（期待度 {active_lab.get("expect_pct",0)}%）ですが、5分足短期軌道は <b>{active_close_chg:+.2f}%</b> と逆方向を示唆。</div>')

        if whale_anom["detected"]:
            w_col = "#10b981" if whale_anom["dir"] == "BULL" else "#ef4444"
            status_pills.append(f'<span class="dd-st-pill" style="border-color:{w_col};background:rgba(15,23,42,0.85);color:{w_col};">🐋 大口{whale_anom["dir"]}({whale_anom["adj_pct"]:+.2f}%)</span>')
            b_cls = "dd-quant-box" if whale_anom["dir"] == "BULL" else "dd-warn-box"
            alert_blocks.append(f'<div class="{b_cls}"><b>🚨 大口・インサイダー異変検知（予測軌道へ {whale_anom["adj_pct"]:+.2f}% 自動反映済）</b><br>{html.escape(whale_anom["summary"])}</div>')

        if status_pills:
            st.markdown(f'<div class="dd-status-strip">{"".join(status_pills)}</div>', unsafe_allow_html=True)

        if alert_blocks or lab_full or lab_council:
            n_info = len(alert_blocks) + (1 if (lab_full or lab_council) else 0)
            with st.expander(f"🔔 アラート・信頼度監査・LAB 3階層MTF詳細 ({n_info}件)", expanded=False):
                for blk in alert_blocks:
                    st.markdown(blk, unsafe_allow_html=True)
                if lab_full or lab_council:
                    m10 = lab_full.get("macro_10y") if isinstance(lab_full.get("macro_10y"), dict) else {}
                    d2 = lab_full.get("daily_2y") if isinstance(lab_full.get("daily_2y"), dict) else {}
                    wf22 = (lab_full.get("wf_22d") if isinstance(lab_full.get("wf_22d"), dict) else (lab_full.get("walk_forward_22d") if isinstance(lab_full.get("walk_forward_22d"), dict) else (lab_full.get("forward_test") if isinstance(lab_full.get("forward_test"), dict) else {})))
                    q_ind = (lab_full.get("quant_metrics") if isinstance(lab_full.get("quant_metrics"), dict) else (lab_full.get("quants") if isinstance(lab_full.get("quants"), dict) else {}))
                    c_verdict = (lab_council.get("verdict") or lab_council.get("conclusion") or lab_council.get("summary") or "-") if isinstance(lab_council, dict) else "-"
                    st.markdown(f"""
                    <div class="dd-dark-box" style="margin-bottom:0;">
                      <div><b>■ 週足10Y大局:</b> 10年POC={html.escape(str(m10.get("poc_10y_price", "-")))} / CAGR={html.escape(str(m10.get("cagr_pct", m10.get("cagr_10y", "-"))))} / スコア={html.escape(str(m10.get("score", m10.get("long_10y_score", "-"))))}</div>
                      <div><b>■ 日足2Y中期:</b> MA並び={html.escape(str(d2.get("ma_align", d2.get("ma_align_label", "-"))))} / HVN/LVN={html.escape(str(d2.get("hvn_wall_price", "-")))} / 日足ATR14={html.escape(str(d2.get("atr14", d2.get("daily_atr14", "-"))))}</div>
                      <div><b>■ 22営業日リークフリー検証:</b> 勝率={html.escape(str(wf22.get("win_rate", wf22.get("actual_win_rate", "-"))))} / PF={html.escape(str(wf22.get("pf", wf22.get("profit_factor", "-"))))} / SQN={html.escape(str(wf22.get("sqn", "-")))} / 平均R={html.escape(str(wf22.get("avg_r", "-")))} / 最大DD={html.escape(str(wf22.get("max_dd", wf22.get("max_dd_pct", "-"))))} / 累計損益={html.escape(str(wf22.get("total_pnl", wf22.get("total_profit_yen", "-"))))}</div>
                      <div><b>■ 独自クオンツ指標:</b> WKB={html.escape(str(q_ind.get("wkb", lab_full.get("q_tunnel", "-"))))} / Kyle-λ={html.escape(str(q_ind.get("kyle_lambda", lab_full.get("kyle_lambda", "-"))))} / VPIN={html.escape(str(q_ind.get("vpin", lab_full.get("vpin", "-"))))} / CLV={html.escape(str(q_ind.get("clv", lab_full.get("ofi_z", "-"))))} / 30分RS={html.escape(str(q_ind.get("rs_30m", lab_full.get("intraday_rs_30m", "-"))))} / 機関OB支持帯={html.escape(str(lab_full.get("ob_support_px", "-")))}</div>
                      <div><b>■ 5名監査官の最新結論:</b> {html.escape(str(c_verdict))}</div>
                    </div>
                    """, unsafe_allow_html=True)

        comp_score = int(np.clip(round(50 + news_res["shock_score"] * 45 - len(gov_risks) * 9 + whale_anom["adj_pct"] * 12), 5, 98))
        meter_lbl = "EXTREME GREED // 極度の強気" if comp_score >= 75 else ("BULLISH // 強気優勢" if comp_score >= 58 else ("NEUTRAL // 均衡・様子見" if comp_score >= 42 else ("FEAR // 警戒・弱気" if comp_score >= 25 else "EXTREME FEAR // リスク警戒")))

        hi_52, lo_52 = float(df_1d["High"].max()), float(df_1d["Low"].min())
        pos_52 = float(np.clip((curr_px - lo_52) / max(hi_52 - lo_52, 1e-4) * 100.0, 2.0, 98.0))
        spark_svg = _build_spark_svg(df_1d["Close"].tail(20).values)
        aura_col = "#10b981" if active_close_chg >= 0 else "#ef4444"
        aura_glow = "rgba(16,185,129,0.22)" if active_close_chg >= 0 else "rgba(239,68,68,0.22)"
        target_mean = info.get("targetMeanPrice")
        upside_str = f"{((target_mean - curr_px)/curr_px*100):+.1f}%" if (target_mean and curr_px > 0) else "-"
        risk_status, risk_col = (f"⚠️ {len(gov_risks)}件", "#f87171") if gov_risks else ("🟢 クリーン", "#10b981")

        # A-2: トップカードの大引け予測もライブ/朝ロック完全連動
        top_close_lbl = "大引け予測(ライブ)" if use_live_basis else "大引け予測(ロック)"
        st.markdown(f"""
        <div class="rank-card" style="border-left-color:{aura_col};box-shadow:0 8px 26px {aura_glow};margin-top:2px;margin-bottom:8px;">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;flex-wrap:wrap;">
            <div style="min-width:0;flex:1;">
              <div><span class="pill-badge">{html.escape(fc)}</span><span class="pill-badge" style="border-color:rgba(168,85,247,0.45);background:rgba(168,85,247,0.16);color:#e9d5ff;">{html.escape(in_style)}</span><span class="pill-badge" style="border-color:{mkt_regime['color']};background:rgba(15,23,42,0.8);color:{mkt_regime['color']};">{mkt_regime['label']}・{traj['weights_evolution']['active_cluster']}</span>{earn_badge}</div>
              <div style="font-size:17px;font-weight:800;color:#fff;margin-top:4px;word-break:break-word;">{html.escape(corp_name)}</div>
              <div style="font-size:11px;color:#94a3b8;margin-top:2px;">{html.escape(sector)} / {html.escape(industry)}</div>
            </div>
            <div style="text-align:right;flex-shrink:0;">
              <div style="font-family:'JetBrains Mono',monospace;font-size:19px;font-weight:800;color:#fff;">{_fmt_cur(curr_px, is_jp)}</div>
              <div style="font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;color:{chg_col};margin-bottom:3px;">{chg_pct:+.2f}%</div>
              {spark_svg}
            </div>
          </div>
          <div style="margin-top:6px;">
            <div style="display:flex;justify-content:space-between;font-size:9.5px;color:#94a3b8;font-family:'JetBrains Mono',monospace;"><span>52W安 {_fmt_cur(lo_52, is_jp)}</span><span style="color:#7dd3fc;">52W位置 {pos_52:.0f}%</span><span>52W高 {_fmt_cur(hi_52, is_jp)}</span></div>
            <div class="dd-range-track"><div class="dd-range-dot" style="left:{pos_52:.1f}%;"></div></div>
          </div>
          <div class="dd-winrate-bar">
            <div><div class="dd-metric-lbl">{top_close_lbl}</div><div class="dd-metric-val" style="color:{aura_col};">{_fmt_cur(active_close_px, is_jp)} ({active_close_chg:+.2f}%)</div></div>
            <div><div class="dd-metric-lbl">アナリスト乖離</div><div class="dd-metric-val" style="color:#fde047;">{upside_str}</div></div>
            <div><div class="dd-metric-lbl">上値しこり玉</div><div class="dd-metric-val" style="color:#c084fc;">{vp['overhead_pct']}%</div></div>
            <div><div class="dd-metric-lbl">ガバナンス</div><div class="dd-metric-val" style="color:{risk_col};">{risk_status}</div></div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        t1, t2, t3, t4 = st.tabs(["翌営業日 1日軌道", "マクロβ・曜日", "財務・大口株主", "リスク・AIメモ"])

        with t1:
            rvol_v = traj["rvol"]
            rvol_txt, rvol_c = (f"{rvol_v:.2f}x (機関)", "#10b981") if (rvol_v and rvol_v >= 1.8) else ((f"{rvol_v:.2f}x (閑散)", "#f59e0b") if (rvol_v and rvol_v < 0.75) else ((f"{rvol_v:.2f}x (通常)", "#38bdf8") if rvol_v else ("場前待機", "#94a3b8")))
            gf = traj["gap_fill"]
            if gf["prob"] is not None:
                gf_txt = f"{int(gf['prob'])}% ({gf['avg_min']}分)" if gf["avg_min"] else f"{int(gf['prob'])}%"
                gf_c = "#10b981" if gf["prob"] >= 60 else ("#f59e0b" if gf["prob"] >= 35 else "#38bdf8")
            else:
                gf_txt, gf_c = "データ不足", "#94a3b8"
            n_sp = len(traj["vol_spikes"])
            sp_txt = f"{n_sp}回検知 ◆" if n_sp > 0 else "なし"

            st.markdown(f"""
            <div class="dd-inst-strip">
              <div class="dd-inst-card"><div class="dd-metric-lbl">RVOL 相対出来高</div><div style="font-family:'JetBrains Mono',monospace;font-size:11.5px;font-weight:800;color:{rvol_c};margin-top:2px;">{rvol_txt}</div></div>
              <div class="dd-inst-card"><div class="dd-metric-lbl">窓埋め率 (平均)</div><div style="font-family:'JetBrains Mono',monospace;font-size:11.5px;font-weight:800;color:{gf_c};margin-top:2px;">{gf_txt}</div></div>
              <div class="dd-inst-card"><div class="dd-metric-lbl">心理的キリ番節目</div><div style="font-family:'JetBrains Mono',monospace;font-size:11.5px;font-weight:800;color:#fde047;margin-top:2px;">{_fmt_cur(round_level, is_jp)}</div></div>
              <div class="dd-inst-card"><div class="dd-metric-lbl">大口約定スパイク</div><div style="font-family:'JetBrains Mono',monospace;font-size:11.5px;font-weight:800;color:{'#c084fc' if n_sp>0 else '#94a3b8'};margin-top:2px;">{sp_txt}</div></div>
              <div class="dd-inst-card"><div class="dd-metric-lbl">疑似CVDフロー</div><div style="font-family:'JetBrains Mono',monospace;font-size:11.5px;font-weight:800;color:{cvd_div['color']};margin-top:2px;">{html.escape(cvd_div['label'])}</div></div>
              <div class="dd-inst-card"><div class="dd-metric-lbl">寄り15分 Gap判定</div><div style="font-family:'JetBrains Mono',monospace;font-size:11.5px;font-weight:800;color:{g15['color']};margin-top:2px;">{html.escape(g15['label'])}</div></div>
            </div>
            """, unsafe_allow_html=True)

            line_opts = [
                "予測レンジ帯（ファン）", "類似日スパゲッティ軌道", "転換時間帯ガイド",
                "押目・利確ゾーン", "VWAP", "VWAP±σ",
                "心理的キリ番節目", "寄り30分高安（ORB）", "大口約定（◆）", "出来高"
            ] + (["LAB TP/SL"] if active_lab else [])

            p_col, cfg_col = st.columns([3.2, 1.1])
            with p_col:
                if hasattr(st, "pills"):
                    sel_preset = st.pills("表示プリセット", presets, default="📈 今の予測", selection_mode="single", label_visibility="collapsed", key="dd_preset_sel") or "📈 今の予測"
                else:
                    sel_preset = st.radio("表示プリセット", presets, index=0, horizontal=True, label_visibility="collapsed", key="dd_preset_sel")

            if sel_preset == "📈 今の予測":
                pr_mode_idx = 2
                pr_lines = ["予測レンジ帯（ファン）", "類似日スパゲッティ軌道", "転換時間帯ガイド", "押目・利確ゾーン", "VWAP", "心理的キリ番節目", "大口約定（◆）", "出来高"] + (["LAB TP/SL"] if active_lab else [])
            elif sel_preset == "🔍 朝の答え合わせ":
                pr_mode_idx = 1
                pr_lines = ["予測レンジ帯（ファン）", "転換時間帯ガイド", "寄り30分高安（ORB）", "出来高"]
            else:
                pr_mode_idx = 0
                pr_lines = ["VWAP", "VWAP±σ", "転換時間帯ガイド", "心理的キリ番節目", "大口約定（◆）", "押目・利確ゾーン", "出来高"] + (["LAB TP/SL"] if active_lab else [])

            if st.session_state.get("dd_last_preset") != sel_preset:
                st.session_state["dd_last_preset"] = sel_preset
                st.session_state["dd_chart_mode"] = modes[pr_mode_idx]
                st.session_state["dd_opt_lines"] = [x for x in pr_lines if x in line_opts]

            with cfg_col:
                if hasattr(st, "popover"):
                    with st.popover("⚙️ 表示設定", use_container_width=True):
                        chart_mode = st.radio("軌道モード", modes, index=pr_mode_idx, key="dd_chart_mode")
                        opt_lines = st.multiselect("表示レイヤー", line_opts, default=[x for x in pr_lines if x in line_opts], key="dd_opt_lines")
                else:
                    with st.expander("⚙️ 表示設定"):
                        chart_mode = st.radio("軌道モード", modes, index=pr_mode_idx, key="dd_chart_mode")
                        opt_lines = st.multiselect("表示レイヤー", line_opts, default=[x for x in pr_lines if x in line_opts], key="dd_opt_lines")

            preset_desc = {
                "📈 今の予測": "ライブ修正軌道 ＋ ノンパラメトリック分位点ファン ＋ k-NN類似日パス ＋ 転換時間帯",
                "🔍 朝の答え合わせ": "寄り前ロック予測 vs 当日実測 ＋ 寄り30分高安",
                "🏦 大口・節目": "VWAP±σバンド ＋ 心理的キリ番節目 ＋ 大口約定スパイク",
            }
            st.caption(f"表示中: {preset_desc.get(sel_preset, '')}")

            if chart_mode in ("🔒 朝ロック検証", "⚡ 両方重ね"):
                if traj["verify"]["has_verify"]:
                    v = traj["verify"]
                    st.markdown(f'<div class="dd-quant-box"><b>📊 寄り前ロック予測 vs 当日実測 検証（実測 {v["n_pts"]}本）</b><br>・<b>分位点ファン内 収束率:</b> <b style="color:#fde047;">{v["in_cone_pct"]}%</b> ｜ <b>平均誤差:</b> <b>{v["err_pct"]}%</b></div>', unsafe_allow_html=True)
                elif traj["has_actual"] and not traj["is_locked"]:
                    st.markdown('<div class="dd-sync-warn"><b>ℹ️ 本日は場中初回アクセスのため「朝ロック検証」対象外</b><br>リーク防止のため、寄り前に保存された予測のみを答え合わせ対象としています（現在はライブ修正軌道を基準に表示中）。</div>', unsafe_allow_html=True)

            ml_data = []
            if traj["lunch_idx"] is not None:
                ml_data.append({"xAxis": traj["slots"][traj["lunch_idx"]], "lineStyle": {"color": "rgba(148,163,184,0.3)", "type": "dashed"}, "label": {"formatter": "前/後場", "color": "#94a3b8", "fontSize": 9, "position": "insideEndTop"}})

            # C-2: 市場固有の時間帯マイクロストラクチャー縦ガイド
            if "転換時間帯ガイド" in opt_lines:
                micro_times = (
                    [("09:05", "寄付一巡"), ("09:30", "仲値前"), ("11:25", "前引け"), ("12:30", "後場寄"), ("14:30", "機関執行"), ("15:25", "大引け")]
                    if is_jp else
                    [("10:00", "指標/反転"), ("11:30", "欧州引け"), ("15:50", "MOC執行")]
                )
                for mt_slot, mt_lbl in micro_times:
                    if mt_slot in traj["slots"]:
                        ml_data.append({
                            "xAxis": mt_slot,
                            "lineStyle": {"color": "rgba(125, 211, 252, 0.22)", "type": "dotted", "width": 1.0},
                            "label": {"formatter": mt_lbl, "color": "rgba(148, 163, 184, 0.72)", "fontSize": 8, "position": "insideEndBottom"},
                        })

            if g15.get("show_gap_target") and prev_px > 0:
                ml_data.append({"yAxis": round(prev_px, 2), "lineStyle": {"color": "#f97316", "type": "dashed", "width": 1.6}, "label": {"formatter": f"窓埋目標 {_fmt_cur(prev_px, is_jp)}", "color": "#fdba74", "fontSize": 9, "position": "insideEndTop"}})
            if "心理的キリ番節目" in opt_lines:
                ml_data.append({"yAxis": round_level, "lineStyle": {"color": "rgba(250,204,21,0.55)", "type": "dotted", "width": 1.3}, "label": {"formatter": f"節目 {_fmt_cur(round_level, is_jp)}", "color": "#fde047", "fontSize": 8.5, "position": "insideStartTop"}})
            if "寄り30分高安（ORB）" in opt_lines and traj["orb_high"] and traj["orb_low"]:
                ml_data.append({"yAxis": traj["orb_high"], "lineStyle": {"color": "rgba(56,189,248,0.45)", "type": "dashed", "width": 1.0}, "label": {"formatter": "ORB高", "color": "#7dd3fc", "fontSize": 8.5, "position": "insideStartTop"}})
                ml_data.append({"yAxis": traj["orb_low"], "lineStyle": {"color": "rgba(244,63,94,0.45)", "type": "dashed", "width": 1.0}, "label": {"formatter": "ORB安", "color": "#fda4af", "fontSize": 8.5, "position": "insideStartBottom"}})
            if active_lab and "LAB TP/SL" in opt_lines:
                l_tp_line = float(active_lab.get("tp", active_lab.get("raw_tp", 0.0)) or 0.0)
                l_sl_line = float(active_lab.get("sl", active_lab.get("raw_sl", 0.0)) or 0.0)
                if l_tp_line > 0:
                    ml_data.append({"yAxis": round(l_tp_line, 2), "lineStyle": {"color": "#10b981", "type": "dashed", "width": 1.5}, "label": {"formatter": f"TP {_fmt_cur(l_tp_line, is_jp)}", "color": "#6ee7b7", "fontSize": 9, "position": "insideStartTop"}})
                if l_sl_line > 0:
                    ml_data.append({"yAxis": round(l_sl_line, 2), "lineStyle": {"color": "#ef4444", "type": "dashed", "width": 1.5}, "label": {"formatter": f"SL {_fmt_cur(l_sl_line, is_jp)}", "color": "#fca5a5", "fontSize": 9, "position": "insideStartBottom"}})
                aux_cands = []
                if isinstance(lab_full, dict) and lab_full:
                    if lab_full.get("ob_support_px") is not None:
                        aux_cands.append(("OB支持", lab_full.get("ob_support_px"), "#34d399"))
                    d2_aux = lab_full.get("daily_2y") if isinstance(lab_full.get("daily_2y"), dict) else {}
                    if d2_aux.get("hvn_wall_price") is not None:
                        aux_cands.append(("HVN壁", d2_aux.get("hvn_wall_price"), "#c084fc"))
                    m10_aux = lab_full.get("macro_10y") if isinstance(lab_full.get("macro_10y"), dict) else {}
                    if m10_aux.get("poc_10y_price") is not None:
                        aux_cands.append(("10Y POC", m10_aux.get("poc_10y_price"), "#fbbf24"))
                for lbl_a, raw_px_a, col_a in aux_cands:
                    try:
                        px_a = float(raw_px_a)
                        if px_a > 0 and curr_px > 0 and abs(px_a - curr_px) / curr_px <= 0.12:
                            ml_data.append({"yAxis": round(px_a, 2), "lineStyle": {"color": col_a, "type": "dotted", "width": 1.2}, "label": {"formatter": f"{lbl_a} {_fmt_cur(px_a, is_jp)}", "color": col_a, "fontSize": 8.5, "position": "insideStartTop"}})
                    except Exception:
                        pass
            ml_cfg = {"symbol": ["none", "none"], "data": ml_data} if ml_data else {}

            ma_data = []
            if "押目・利確ゾーン" in opt_lines:
                n_sl = len(traj["slots"])
                cur_dip_i = traj["live_dip_idx"] if use_live_basis else traj["locked_dip_idx"]
                cur_peak_i = traj["live_peak_idx"] if use_live_basis else traj["locked_peak_idx"]
                d_s, d_e = max(0, cur_dip_i - 2), min(n_sl - 1, cur_dip_i + 2)
                p_s, p_e = max(0, cur_peak_i - 2), min(n_sl - 1, cur_peak_i + 2)
                ma_data.append([{"name": "押目帯", "xAxis": traj["slots"][d_s], "itemStyle": {"color": "rgba(16, 185, 129, 0.09)"}, "label": {"position": "insideTop", "color": "#6ee7b7", "fontSize": 8.5}}, {"xAxis": traj["slots"][d_e]}])
                ma_data.append([{"name": "利確帯", "xAxis": traj["slots"][p_s], "itemStyle": {"color": "rgba(239, 68, 68, 0.09)"}, "label": {"position": "insideTop", "color": "#fca5a5", "fontSize": 8.5}}, {"xAxis": traj["slots"][p_e]}])
                if vp["overhead_pct"] >= 25.0:
                    ma_data.append([{"name": "売り壁", "yAxis": round(vp["res_px"] * 0.996, 2), "itemStyle": {"color": "rgba(168, 85, 247, 0.13)"}, "label": {"position": "insideLeft", "color": "#d8b4fe", "fontSize": 8.5}}, {"yAxis": round(vp["res_px"] * 1.004, 2)}])
            ma_cfg = {"silent": True, "data": ma_data} if ma_data else {}

            s_list, l_names = [], []
            if "出来高" in opt_lines:
                s_list.append({"name": "出来高", "type": "bar", "yAxisIndex": 1, "data": traj["vols"], "itemStyle": {"color": "rgba(148,163,184,0.14)", "borderRadius": [2, 2, 0, 0]}, "barMaxWidth": 4})

            if "予測レンジ帯（ファン）" in opt_lines:
                is_lv = (chart_mode in ("🔴 ライブ修正", "⚡ 両方重ね") and traj["has_actual"])
                c_p15 = disp_live_p15 if is_lv else disp_locked_p15
                c_bd = disp_live_bdiff if is_lv else disp_locked_bdiff
                c_p32 = disp_live_p32 if is_lv else disp_locked_p32
                c_bd_in = disp_live_bdiff_in if is_lv else disp_locked_bdiff_in
                s_list.extend([
                    {"name": "outer_base", "type": "line", "yAxisIndex": 0, "data": c_p15, "stack": "fan_out", "lineStyle": {"opacity": 0}, "showSymbol": False, "silent": True},
                    {"name": "10-90%分位帯", "type": "line", "yAxisIndex": 0, "data": c_bd, "stack": "fan_out", "lineStyle": {"opacity": 0}, "areaStyle": {"color": "rgba(99, 102, 241, 0.12)"}, "showSymbol": False, "silent": True},
                    {"name": "inner_base", "type": "line", "yAxisIndex": 0, "data": c_p32, "stack": "fan_in", "lineStyle": {"opacity": 0}, "showSymbol": False, "silent": True},
                    {"name": "コア帯", "type": "line", "yAxisIndex": 0, "data": c_bd_in, "stack": "fan_in", "lineStyle": {"opacity": 0}, "areaStyle": {"color": "rgba(56, 189, 248, 0.22)"}, "showSymbol": False, "silent": True},
                ])
                l_names.append("コア帯")

            # C-1: スパゲッティ・プロット（k-NN上位類似日の実測5分足投影パス）
            if "類似日スパゲッティ軌道" in opt_lines and traj["knn_match"].get("analog_paths"):
                for a_idx, ap in enumerate(traj["knn_match"]["analog_paths"]):
                    ap_scaled = [round(v * shock_mult, 2) if v is not None else None for v in ap["data"]]
                    s_list.append({
                        "name": f"類似_{ap['date']}",
                        "type": "line",
                        "yAxisIndex": 0,
                        "data": ap_scaled,
                        "lineStyle": {"color": "#94a3b8", "width": 1.1, "opacity": 0.18},
                        "showSymbol": False,
                        "silent": True,
                        "z": 2,
                    })

            if "VWAP" in opt_lines and traj["has_actual"]:
                s_list.append({"name": "VWAP", "type": "line", "yAxisIndex": 0, "data": traj["vwap"], "lineStyle": {"color": "#f59e0b", "width": 1.6, "type": "dotted"}, "showSymbol": False})
                l_names.append("VWAP")

            if "VWAP±σ" in opt_lines and traj["has_actual"]:
                s_list.extend([
                    {"name": "VWAP+1σ", "type": "line", "yAxisIndex": 0, "data": traj["vwap_p1"], "lineStyle": {"color": "rgba(245,158,11,0.55)", "width": 1.0, "type": "dashed"}, "showSymbol": False, "silent": True},
                    {"name": "VWAP-1σ", "type": "line", "yAxisIndex": 0, "data": traj["vwap_m1"], "lineStyle": {"color": "rgba(245,158,11,0.55)", "width": 1.0, "type": "dashed"}, "showSymbol": False, "silent": True},
                    {"name": "VWAP+2σ", "type": "line", "yAxisIndex": 0, "data": traj["vwap_p2"], "lineStyle": {"color": "rgba(239,68,68,0.45)", "width": 1.0, "type": "dotted"}, "showSymbol": False, "silent": True},
                    {"name": "VWAP-2σ", "type": "line", "yAxisIndex": 0, "data": traj["vwap_m2"], "lineStyle": {"color": "rgba(16,185,129,0.45)", "width": 1.0, "type": "dotted"}, "showSymbol": False, "silent": True},
                ])

            if chart_mode in ("🔒 朝ロック検証", "⚡ 両方重ね"):
                is_both = (chart_mode == "⚡ 両方重ね")
                s_list.append({
                    "name": "朝ロック", "type": "line", "yAxisIndex": 0, "data": disp_locked_p50,
                    "lineStyle": {"color": "#c084fc" if is_both else "#38bdf8", "width": 2.0 if is_both else 2.6, "type": "dashed" if is_both else "solid", "shadowBlur": 8, "shadowColor": "rgba(192,132,252,0.45)"},
                    "showSymbol": False, "markLine": ml_cfg, "markArea": ma_cfg
                })
                l_names.append("朝ロック")

            if chart_mode in ("🔴 ライブ修正", "⚡ 両方重ね"):
                s_list.append({
                    "name": "ライブ修正", "type": "line", "yAxisIndex": 0, "data": disp_live_p50,
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

            if "大口約定（◆）" in opt_lines and traj["vol_spikes"]:
                sp_pts = [{"value": [sp["time"], sp["price"]], "itemStyle": {"color": "#10b981" if sp["dir"] > 0 else "#ef4444", "borderColor": "#ffffff", "borderWidth": 1}} for sp in traj["vol_spikes"]]
                s_list.append({"name": "大口約定", "type": "scatter", "yAxisIndex": 0, "symbol": "diamond", "symbolSize": 9, "data": sp_pts, "z": 10})

            pulse_pts = [
                {"name": "押目", "value": [active_dip_time, active_dip_px], "itemStyle": {"color": "#10b981"}},
                {"name": "高値", "value": [active_peak_time, active_peak_px], "itemStyle": {"color": "#f43f5e"}}
            ]
            if traj["has_actual"] and traj["last_act_idx"] >= 0:
                li = traj["last_act_idx"]
                pulse_pts.append({"name": "NOW", "value": [traj["slots"][li], traj["actual"][li]], "itemStyle": {"color": "#ffffff"}})
            if cvd_div.get("marker"):
                mk_d = cvd_div["marker"]
                pulse_pts.append({"name": mk_d["name"], "value": [mk_d["time"], mk_d["price"]], "itemStyle": {"color": mk_d["color"]}})
            s_list.append({
                "name": "重要点", "type": "effectScatter", "yAxisIndex": 0, "data": pulse_pts,
                "symbolSize": 8, "rippleEffect": {"brushType": "stroke", "scale": 3.2},
                "label": {"show": True, "position": "top", "formatter": "{b}", "color": "#f8fafc", "fontSize": 9, "fontWeight": "bold"}
            })

            _render_echarts({
                "backgroundColor": "#0b1120",
                "legend": {"data": l_names, "textStyle": {"color": "#cbd5e1", "fontSize": 9.5}, "top": 2, "left": 4, "right": 72, "itemWidth": 12, "itemHeight": 8},
                "grid": {"top": 60, "bottom": 24, "left": 6, "right": 50 if is_jp else 44, "containLabel": False},
                "dataZoom": [{"type": "inside", "xAxisIndex": 0, "filterMode": "none"}],
                "xAxis": {"type": "category", "boundaryGap": False, "data": traj["slots"], "axisLine": {"lineStyle": {"color": "rgba(148,163,184,0.2)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9.5, "interval": "auto", "hideOverlap": True}},
                "yAxis": [
                    {"type": "value", "position": "right", "scale": True, "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.05)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9}},
                    {"type": "value", "show": False, "axisPointer": {"show": False}, "max": max(traj["vols"] + [1]) * 4.8}
                ],
                "series": s_list
            }, height=345, use_hud_tooltip=True, is_jp=is_jp, enable_fullscreen=True)

            # D-1: ベイズ更新型「リアルタイム・シナリオ確率メーター」
            st.markdown(f"""
            <div class="dd-prob-meter">
              <div style="display:flex;justify-content:space-between;align-items:center;font-size:10.5px;">
                <span style="font-weight:800;color:#7dd3fc;">BAYESIAN SCENARIO PROBABILITY // リアルタイム事後確率</span>
                <span style="font-family:'JetBrains Mono',monospace;color:#94a3b8;font-size:9.5px;">{'ライブ連動' if use_live_basis else '朝ロック基準'}{f' / 衝撃波{shock_ext_pct:+.2f}%' if abs(shock_ext_pct)>0.01 else ''}</span>
              </div>
              <div class="dd-prob-stack">
                <div style="width:{scen_probs['bull']}%;background:#10b981;" title="上振れ突破 {scen_probs['bull']}%"></div>
                <div style="width:{scen_probs['range']}%;background:#38bdf8;" title="標準レンジ {scen_probs['range']}%"></div>
                <div style="width:{scen_probs['fade']}%;background:#f59e0b;" title="窓埋め反転 {scen_probs['fade']}%"></div>
                <div style="width:{scen_probs['bear']}%;background:#ef4444;" title="下振れ崩壊 {scen_probs['bear']}%"></div>
              </div>
              <div class="dd-prob-legend">
                <div style="color:#6ee7b7;">🟢 上振れ突破 <b>{scen_probs['bull']:.1f}%</b></div>
                <div style="color:#7dd3fc;">🔵 標準レンジ <b>{scen_probs['range']:.1f}%</b></div>
                <div style="color:#fde047;">🟠 窓埋め反転 <b>{scen_probs['fade']:.1f}%</b></div>
                <div style="color:#fca5a5;">🔴 下振れ崩壊 <b>{scen_probs['bear']:.1f}%</b></div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            # D-3: 「What-If 衝撃波シミュレーター（感応度スライダー）」
            with st.expander("⚡ What-If 衝撃波シミュレーター（指数・為替 追加変動テスト）", expanded=False):
                wi1, wi2 = st.columns(2)
                wi_idx = wi1.slider(
                    f"主連動（{f_map['mkt_label']} β={mkt_beta_eff:+.2f}）追加変動 (%)",
                    min_value=-2.0, max_value=2.0, value=shock_idx_pct, step=0.1,
                    key="dd_whatif_idx_pct"
                )
                wi_fx = wi2.slider(
                    f"ドル円（β={fx_beta_eff:+.2f}）追加変動 (円)",
                    min_value=-2.0, max_value=2.0, value=shock_fx_yen, step=0.1,
                    key="dd_whatif_fx_yen"
                )
                st.caption(
                    f"合成ショック影響: {shock_ext_pct:+.2f}% ｜ "
                    f"想定大引け: {_fmt_cur(active_close_px, is_jp)} ({active_close_chg:+.2f}%) ｜ "
                    f"上振れ確率: {scen_probs['bull']:.1f}% / 下振れ確率: {scen_probs['bear']:.1f}%"
                )

            with st.expander("🧮 適正ロット・100株単元・流動性インパクト・FPT電卓", expanded=False):
                l_tp_ev = float(active_lab.get("tp", active_lab.get("raw_tp", 0.0)) or 0.0) if active_lab else 0.0
                l_sl_ev = float(active_lab.get("sl", active_lab.get("raw_sl", 0.0)) or 0.0) if active_lab else 0.0
                def_tp = l_tp_ev if l_tp_ev > 0 else active_bull_tgt
                def_sl = l_sl_ev if l_sl_ev > 0 else active_bear_trig
                ec1, ec2 = st.columns([1.4, 1.0])
                risk_amt = ec1.number_input(
                    "1回の許容損失額 (" + ("円" if is_jp else "$") + ")",
                    min_value=10.0,
                    value=10000.0 if is_jp else 100.0,
                    step=1000.0 if is_jp else 25.0,
                    key=f"dd_risk_amt_{'jp' if is_jp else 'us'}"
                )
                win_prob = ec2.slider("想定勝率 (%)", 30, 80, int(active_lab.get("expect_pct", 55)) if active_lab else 55, key="dd_win_prob")

                # What-Ifショック時の実効エントリー基準価格
                sim_curr_px = round(curr_px * (1.0 + shock_ext_pct / 100.0 * 0.35), 2)
                risk_per_sh = max(abs(sim_curr_px - def_sl), sim_curr_px * 0.005)
                rew_per_sh = max(abs(def_tp - sim_curr_px), sim_curr_px * 0.005)
                rr_ratio = rew_per_sh / risk_per_sh
                raw_shares = int(risk_amt // risk_per_sh)

                jp_under_lot = False
                if is_jp:
                    opt_shares = (raw_shares // 100) * 100
                    if opt_shares < 100:
                        jp_under_lot = True
                    calc_shares = opt_shares if opt_shares >= 100 else 100
                    lot_lbl = f"{opt_shares:,}株 ({opt_shares // 100}単元)" if not jp_under_lot else "0株 (見送り推奨)"
                    lot_col = "#38bdf8" if not jp_under_lot else "#ef4444"
                else:
                    opt_shares = max(1, raw_shares)
                    calc_shares = opt_shares
                    lot_lbl = f"{opt_shares:,}株"
                    lot_col = "#38bdf8"

                be_wr = (1.0 / (1.0 + rr_ratio)) * 100.0
                ev_val = (win_prob / 100.0) * (calc_shares * rew_per_sh) - (1.0 - win_prob / 100.0) * (calc_shares * risk_per_sh)
                ev_col = "#10b981" if ev_val > 0 else "#ef4444"

                avg_5m_v = max(float(traj.get("avg_5m_vol", 1.0)), 1.0)
                impact_pct = (calc_shares / avg_5m_v) * 100.0
                imp_col = "#ef4444" if impact_pct >= 2.0 else ("#f59e0b" if impact_pct >= 0.8 else "#10b981")

                tp_fpt = _calc_first_passage_prob(sim_curr_px, def_tp, traj["rem_sigma_pct"], active_rem_drift)
                sl_fpt = _calc_first_passage_prob(sim_curr_px, def_sl, traj["rem_sigma_pct"], active_rem_drift)
                rem_pct_lbl = int(round(traj["rem_frac_now"] * 100))

                st.markdown(f"""
                <div style="font-size:11px;color:#94a3b8;">基準: Entry <b>{_fmt_cur(sim_curr_px, is_jp)}</b> / TP <b>{_fmt_cur(def_tp, is_jp)}</b> / SL <b>{_fmt_cur(def_sl, is_jp)}</b>（U字残存σ {traj['rem_sigma_pct']*100:.2f}% / 残時間 {rem_pct_lbl}%）</div>
                <div class="dd-ev-grid">
                  <div class="dd-ev-cell"><div class="dd-metric-lbl">適正ロット</div><div style="font-family:'JetBrains Mono',monospace;font-size:12.5px;font-weight:800;color:{lot_col};">{lot_lbl}</div></div>
                  <div class="dd-ev-cell"><div class="dd-metric-lbl">RR比 (損益分岐)</div><div style="font-family:'JetBrains Mono',monospace;font-size:12.5px;font-weight:800;color:#fde047;">1:{rr_ratio:.2f} ({be_wr:.0f}%)</div></div>
                  <div class="dd-ev-cell"><div class="dd-metric-lbl">1回あたり期待値</div><div style="font-family:'JetBrains Mono',monospace;font-size:12.5px;font-weight:800;color:{ev_col};">{'+' if ev_val>=0 else ''}{_fmt_cur(ev_val, is_jp)}</div></div>
                </div>
                <div class="dd-ev-grid" style="margin-top:6px;">
                  <div class="dd-ev-cell"><div class="dd-metric-lbl">大引け迄 TP到達 (FPT)</div><div style="font-family:'JetBrains Mono',monospace;font-size:12.5px;font-weight:800;color:{'#10b981' if tp_fpt>=35 else '#f59e0b'};">{tp_fpt:.1f}%</div></div>
                  <div class="dd-ev-cell"><div class="dd-metric-lbl">大引け迄 SLタッチ</div><div style="font-family:'JetBrains Mono',monospace;font-size:12.5px;font-weight:800;color:{'#ef4444' if sl_fpt>=45 else '#94a3b8'};">{sl_fpt:.1f}%</div></div>
                  <div class="dd-ev-cell"><div class="dd-metric-lbl">流動性インパクト</div><div style="font-family:'JetBrains Mono',monospace;font-size:12.5px;font-weight:800;color:{imp_col};">{impact_pct:.2f}%</div></div>
                </div>
                """, unsafe_allow_html=True)

                if jp_under_lot:
                    min_loss_100 = 100.0 * risk_per_sh
                    st.markdown(f'<div class="dd-warn-box" style="margin-top:6px;margin-bottom:0;"><b>⛔ 1単元（100株）で許容損失オーバー</b><br>最小単元100株のSL到達時損失は <b>{_fmt_cur(min_loss_100, True)}</b> で許容損失（{_fmt_cur(risk_amt, True)}）を超過します。エントリー見送りか単元未満株を検討してください。</div>', unsafe_allow_html=True)
                if impact_pct >= 2.0:
                    st.markdown(f'<div class="dd-warn-box" style="margin-top:6px;margin-bottom:0;"><b>⚠️ 流動性インパクト警戒（5分足出来高の {impact_pct:.2f}%）</b><br>板が薄く、成行発注だとスリッページでRR比が崩壊する恐れがあります。指値分割執行を推奨します。</div>', unsafe_allow_html=True)
                if traj["has_actual"] and tp_fpt < 22.0 and traj["rem_frac_now"] < 0.45:
                    st.markdown('<div class="dd-warn-box" style="margin-top:6px;margin-bottom:0;"><b>⛔ 時間切れ警戒（手遅れエントリー注意）</b><br>残存ボラティリティに対しTPが遠すぎます（到達確率 22%未満）。新規の追っかけエントリーは非推奨です。</div>', unsafe_allow_html=True)

            # A-2 & A-4 & D-1: シナリオカードをライブ/ロック連動価格＋ベイズ事後確率バーで動的描画
            bp = (active_bull_tgt - curr_px) / max(curr_px, 1e-4) * 100.0
            sp = (active_bear_tgt - curr_px) / max(curr_px, 1e-4) * 100.0
            mid_sc_prob = round(scen_probs["range"] + scen_probs["fade"], 1)
            st.markdown(f"""
            <div class="dd-sc-stack">
              <div class="dd-sc-card" style="border-left:4px solid #10b981;">
                <div class="dd-sc-top">
                  <div>
                    <div style="font-weight:800;color:#6ee7b7;font-size:12.5px;">上振れ突破シナリオ（事後確率 {scen_probs['bull']:.1f}%）</div>
                    <div style="font-size:11px;color:#cbd5e1;margin-top:2px;">トリガー: <b>{_fmt_cur(active_bull_trig, is_jp)}</b> 超え（FPT到達率 {scen_probs['fpt_bull_pct']:.1f}%）</div>
                  </div>
                  <div style="text-align:right;">
                    <div class="dd-sc-price" style="color:#6ee7b7;">{_fmt_cur(active_bull_tgt, is_jp)}</div>
                    <div class="dd-sc-pct" style="color:#10b981;">{bp:+.2f}%</div>
                  </div>
                </div>
                <div class="dd-sc-bar-bg"><div class="dd-sc-bar-fill" style="width:{scen_probs['bull']:.1f}%;background:#10b981;"></div></div>
              </div>
              <div class="dd-sc-card" style="border-left:4px solid #38bdf8;">
                <div class="dd-sc-top">
                  <div>
                    <div style="font-weight:800;color:#7dd3fc;font-size:12.5px;">標準レンジ・窓埋めシナリオ（事後確率 {mid_sc_prob:.1f}%）</div>
                    <div style="font-size:11px;color:#cbd5e1;margin-top:2px;">押し目: <b>{active_dip_time}</b> ({_fmt_cur(active_dip_px, is_jp)}) → 高値 <b>{active_peak_time}</b>（窓埋 {scen_probs['fade']:.1f}%）</div>
                  </div>
                  <div style="text-align:right;">
                    <div class="dd-sc-price" style="color:#7dd3fc;">{_fmt_cur(active_close_px, is_jp)}</div>
                    <div class="dd-sc-pct" style="color:#38bdf8;">{active_close_chg:+.2f}%</div>
                  </div>
                </div>
                <div class="dd-sc-bar-bg"><div class="dd-sc-bar-fill" style="width:{mid_sc_prob:.1f}%;background:#38bdf8;"></div></div>
              </div>
              <div class="dd-sc-card" style="border-left:4px solid #ef4444;">
                <div class="dd-sc-top">
                  <div>
                    <div style="font-weight:800;color:#fca5a5;font-size:12.5px;">下振れ崩壊シナリオ（事後確率 {scen_probs['bear']:.1f}%）</div>
                    <div style="font-size:11px;color:#cbd5e1;margin-top:2px;">トリガー: <b>{_fmt_cur(active_bear_trig, is_jp)}</b> 割れ（FPTタッチ率 {scen_probs['fpt_bear_pct']:.1f}%）</div>
                  </div>
                  <div style="text-align:right;">
                    <div class="dd-sc-price" style="color:#fca5a5;">{_fmt_cur(active_bear_tgt, is_jp)}</div>
                    <div class="dd-sc-pct" style="color:#ef4444;">{sp:+.2f}%</div>
                  </div>
                </div>
                <div class="dd-sc-bar-bg"><div class="dd-sc-bar-fill" style="width:{scen_probs['bear']:.1f}%;background:#ef4444;"></div></div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            f = traj["factors"]
            we = traj["weights_evolution"]
            og_now = we["open_gap"]
            idr_now = we["intraday_drift"]
            ld = we.get("last_decomp", {})
            knn_dates_str = ", ".join(traj["knn_match"]["matched_dates"][:3]) if traj["knn_match"]["matched_dates"] else "場前待機"
            hvn_str = _fmt_cur(f["hvn_wall_px"], is_jp) if f.get("hvn_wall_px", 0.0) > 0 else "-"
            ob_str = _fmt_cur(f["ob_sup_px"], is_jp) if f.get("ob_sup_px", 0.0) > 0 else "-"

            ranked_factors = sorted([
                (f"主連動（{f['mkt_label']} β{f['mkt_beta']:+.2f}）", f["macro_gap_pct"]),
                (f"為替（ドル円 β{f['fx_beta']:+.2f}）", f["fx_gap_pct"]),
                (f"日英高信頼ニュース（一次{news_res['tier1_cnt']}件）", f["news_gap_pct"]),
                ("大口・インサイダー異変（30日内）", f["whale_gap_pct"]),
                ("LAB上位足バイアス", f["lab_bias_pct"]),
                ("曜日エッジ＋ヒゲ圧力", f["dow_wick_pct"]),
                ("台帳キャリブレーション", f["calib_pct"]),
                ("場中VWAP・30分勢い・指数α追従", f["live_vwap_pct"]),
            ], key=lambda x: abs(x[1]), reverse=True)

            top3_html = "".join([
                f'<div class="dd-factor-row"><span>{html.escape(lbl)}</span><span style="font-family:JetBrains Mono,monospace;color:{"#10b981" if val>=0 else "#ef4444"};">{val:+.2f}%</span></div>'
                for lbl, val in ranked_factors[:3]
            ])
            st.markdown(f"""
            <div class="dd-dark-box">
              <div style="font-size:11px;font-weight:800;color:#38bdf8;margin-bottom:4px;">KEY DRIVERS // 主要寄与 Top3（{html.escape(we['active_cluster'])}・{we['active_regime']}脳 N={we['cluster_n']} / 累計{we['updates_count']}回）</div>
              {top3_html}
              <div class="dd-factor-row"><span>合成・寄付き予測 → 大引け予測</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if active_close_chg>=0 else '#ef4444'};">{active_open_gap_pct:+.2f}% → {active_close_chg:+.2f}%</span></div>
            </div>
            """, unsafe_allow_html=True)

            with st.expander("🔬 全ファクター内訳（13項目）＆ クラスタ別3脳SGD進化重み", expanded=False):
                st.markdown(f"""
                <div class="dd-dark-box" style="margin-bottom:8px;">
                  <div class="dd-factor-row"><span>主連動（{html.escape(f['mkt_label'])} {f['mkt_diff']:+.2f}% × β{f['mkt_beta']:+.2f} × 重み{og_now['macro']:.2f}）</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['macro_gap_pct']>=0 else '#ef4444'};">{f['macro_gap_pct']:+.2f}%</span></div>
                  <div class="dd-factor-row"><span>為替（ドル円 {f['fx_diff']:+.2f}% × β{f['fx_beta']:+.2f} × 重み{og_now['fx']:.2f}）</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['fx_gap_pct']>=0 else '#ef4444'};">{f['fx_gap_pct']:+.2f}%</span></div>
                  <div class="dd-factor-row"><span>日英高信頼ニュース時間減衰スコア（一次 {news_res['tier1_cnt']}件・重み{og_now['news']:.2f}）</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['news_gap_pct']>=0 else '#ef4444'};">{f['news_gap_pct']:+.2f}%</span></div>
                  <div class="dd-factor-row"><span>大口・インサイダー直近30日異変補正（重み{og_now['whale']:.2f}）</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['whale_gap_pct']>=0 else '#ef4444'};">{f['whale_gap_pct']:+.2f}%</span></div>
                  <div class="dd-factor-row"><span>LAB上位足 方向性・期待度バイアス（寄付重み{og_now['lab_bias']:.2f} / 日中重み{idr_now['lab_bias']:.2f}）</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['lab_bias_pct']>=0 else '#ef4444'};">{f['lab_bias_pct']:+.2f}%</span></div>
                  <div class="dd-factor-row"><span>指数ベータ分離5分足モデル（5m β={traj['bench_beta_5m']:+.2f} / ライブ指数追従 {f['bench_alpha_pct']:+.2f}%）</span><span style="font-family:'JetBrains Mono',monospace;color:#38bdf8;">{'有効' if traj['has_bench_5m'] else 'フォールバック'}</span></div>
                  <div class="dd-factor-row"><span>HVNしこり壁 / 機関OB支持帯</span><span style="font-family:'JetBrains Mono',monospace;color:#c084fc;">HVN {hvn_str} / OB {ob_str}</span></div>
                  <div class="dd-factor-row"><span>曜日エッジ ＋ 直近5日ヒゲ圧力補正</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['dow_wick_pct']>=0 else '#ef4444'};">{f['dow_wick_pct']:+.2f}%</span></div>
                  <div class="dd-factor-row"><span>台帳自己学習キャリブレーション（過去{f['calib_n']}日）</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['calib_pct']>=0 else '#ef4444'};">{f['calib_pct']:+.2f}%</span></div>
                  <div class="dd-factor-row"><span>場中VWAP・30分勢い・初動15分Gap・指数α補正</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['live_vwap_pct']>=0 else '#ef4444'};">{f['live_vwap_pct']:+.2f}%</span></div>
                  <div class="dd-factor-row"><span>k-NN複合類似日マッチ（ATR正規化＋コサイン＋RVOL＋Gap）</span><span style="font-family:'JetBrains Mono',monospace;color:#7dd3fc;">{html.escape(knn_dates_str)}</span></div>
                  <div class="dd-factor-row"><span>クラスタSGD誤差（{html.escape(str(ld.get('date','-')))} / {html.escape(str(ld.get('cluster','-')))}・{html.escape(str(ld.get('regime','NEUTRAL')))}脳）</span><span style="font-family:'JetBrains Mono',monospace;color:#fde047;">寄付 {float(ld.get('open_err_pct',0.0)):+.2f}% / 日中 {float(ld.get('intraday_err_pct',0.0)):+.2f}%</span></div>
                  <div class="dd-factor-row"><span>直近の最大誤差犯人ファクター（過大/過小特定）</span><span style="font-family:'JetBrains Mono',monospace;color:#fca5a5;">寄付:{html.escape(str(ld.get('culprit_open','-')))} / 日中:{html.escape(str(ld.get('culprit_intra','-')))}</span></div>
                </div>
                """, unsafe_allow_html=True)
                st.json({
                    "active_cluster": we["active_cluster"],
                    "shrinkage_alpha": we["shrink_alpha"],
                    "active_regime_brain": we["active_regime"],
                    "total_updates_count": we["updates_count"],
                    "cluster_regime_brains": we["all_regimes"],
                    "last_decomposition": ld,
                })
                if st.button("🔄 クラスタ別3脳SGD進化重みを初期値にリセット", key="dd_reset_weights_btn", use_container_width=True):
                    _save_weights_evolution(DEFAULT_WEIGHTS_EVOLUTION)
                    st.rerun()

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
                st.markdown("##### 価格帯別出来高（60日半減期・レンジ均等配分しこり玉マップ）")
                _render_echarts({"backgroundColor": "#0b1120", "tooltip": {"trigger": "axis"}, "grid": {"top": 10, "bottom": 20, "left": 6, "right": 14, "containLabel": True}, "xAxis": {"type": "value", "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.06)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9.5}}, "yAxis": {"type": "category", "data": vp["labels"], "axisLabel": {"color": "#cbd5e1", "fontSize": 9.5}}, "series": [{"name": "減衰出来高(M)", "type": "bar", "data": vp["vols"], "itemStyle": {"color": "#a855f7"}}]}, height=230)

        with t4:
            _render_echarts({"backgroundColor": "#0b1120", "series": [{"type": "gauge", "startAngle": 180, "endAngle": 0, "min": 0, "max": 100, "splitNumber": 5, "center": ["50%", "74%"], "radius": "112%", "axisLine": {"lineStyle": {"width": 16, "color": [[0.2, "#dc2626"], [0.4, "#f97316"], [0.6, "#38bdf8"], [0.8, "#10b981"], [1.0, "#059669"]]}}, "pointer": {"icon": "path://M12.8,0.7l12,40.1H0.7L12.8,0.7z", "length": "52%", "width": 10, "offsetCenter": [0, "-12%"], "itemStyle": {"color": "#f8fafc", "shadowBlur": 8, "shadowColor": "rgba(56,189,248,0.8)"}}, "anchor": {"show": True, "showAbove": True, "size": 14, "itemStyle": {"color": "#38bdf8", "borderWidth": 2, "borderColor": "#fff"}}, "axisTick": {"length": 6, "lineStyle": {"color": "auto", "width": 1.5}}, "splitLine": {"length": 12, "lineStyle": {"color": "auto", "width": 2.5}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9.5, "distance": -36}, "title": {"offsetCenter": [0, "18%"], "fontSize": 10.5, "color": "#7dd3fc", "fontWeight": "bold"}, "detail": {"fontSize": 26, "fontWeight": "bold", "offsetCenter": [0, "-3%"], "valueAnimation": True, "color": "#ffffff", "formatter": "{value}"}, "data": [{"value": comp_score, "name": meter_lbl}]}]}, height=225)

            # A-2: AIメモもライブ修正値（active_*）を完全連動参照
            memo_nonce = st.session_state.get("dd_memo_nonce", 0)
            top_m = macro_sens[0] if macro_sens else {"label": "市場指数", "corr": 0.0, "beta": 1.0}
            m_txt, m_src = _generate_detailed_memo_cached(
                fc, corp_name, _fmt_cur(curr_px, is_jp),
                _fmt_cur(active_open_px, is_jp), _fmt_cur(active_close_px, is_jp),
                _fmt_cur(active_bull_trig, is_jp), _fmt_cur(active_bull_tgt, is_jp),
                _fmt_cur(active_bear_trig, is_jp), _fmt_cur(active_bear_tgt, is_jp),
                active_dip_time, active_peak_time, vp["overhead_pct"],
                _fmt_cur(vp["res_px"], is_jp), _fmt_cur(vp["sup_px"], is_jp),
                top_m["label"], top_m["corr"], top_m["beta"], news_res["pos_pct"],
                news_res["tier1_cnt"], len(gov_risks), whale_anom["summary"], upside_str, lab_note, api_k, lab_deep_ctx,
                memo_nonce=memo_nonce
            )
            st.markdown(f'<div class="dd-memo-box"><div style="font-size:10.5px;color:#c084fc;font-weight:800;margin-bottom:6px;">{html.escape(m_src)}</div>{html.escape(m_txt).replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
            if st.button("🔄 AIインベストメントメモを再生成", key="dd_regen_memo_btn", use_container_width=True):
                st.session_state["dd_memo_nonce"] = memo_nonce + 1
                st.rerun()

            if gov_risks:
                st.markdown(f'<div class="dd-warn-box"><b>ガバナンス・不祥事・訴訟関連ヒット ({len(gov_risks)}件)</b><br>' + "<br>".join([f"・{html.escape(x)}" for x in gov_risks]) + '</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="dd-quant-box"><b>ガバナンス・不祥事監査: クリーン</b><br>直近72時間以内のニュースにおいて不祥事・不正・訴訟などの特異リスクシグナルは検知されていません。</div>', unsafe_allow_html=True)

            if news_res["items"]:
                n_html = "".join([
                    f'<div style="margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid rgba(148,163,184,0.12);">'
                    f'<span style="color:{"#fde047" if it["trust"]=="S" else ("#38bdf8" if it["trust"]=="A" else "#64748b")};font-weight:800;font-size:10px;border:1px solid;padding:0 4px;border-radius:3px;margin-right:4px;">信頼度{it["trust"]}/{it["lang"]}</span>'
                    f'<span style="color:{"#10b981" if it["sent"]=="POS" else ("#ef4444" if it["sent"]=="NEG" else "#94a3b8")};font-weight:800;font-size:10px;margin-right:4px;">[{it["sent"]}]</span>'
                    f'<span style="color:#94a3b8;font-size:9.5px;margin-right:4px;">(鮮度重み {it["decay_w"]:.1f})</span>'
                    f'<a href="{html.escape(it["link"])}" target="_blank" style="color:#e2e8f0;text-decoration:none;font-weight:600;">{html.escape(it["title"])}</a> '
                    f'<span style="color:#64748b;font-size:10px;">({html.escape(it["source"] or "Wire")} / {html.escape(it["pub"])})</span></div>'
                    for it in news_res["items"]
                ])
                st.markdown(f'<div class="dd-dark-box"><b>GLOBAL INTELLIGENCE FEED // 日英高信頼ニュース（有効報道 {news_res["fresh_cnt"]}件 / 一次 {news_res["tier1_cnt"]}件）</b><br><br>{n_html}</div>', unsafe_allow_html=True)

        # A-2: dd_result もライブ修正値・ベイズ事後確率・メタ信頼度監査を完全同期
        dd_result = {
            "full_code": fc,
            "style": in_style,
            "comp_score": int(comp_score),
            "meter_lbl": str(meter_lbl),
            "mkt_regime": mkt_regime,
            "est_open_gap_pct": float(active_open_gap_pct),
            "est_close_px": float(active_close_px),
            "est_close_chg": float(active_close_chg),
            "bull_trig": float(active_bull_trig),
            "bull_target": float(active_bull_tgt),
            "bear_trig": float(active_bear_trig),
            "bear_target": float(active_bear_tgt),
            "dip_time": str(active_dip_time),
            "peak_time": str(active_peak_time),
            "scenario_probs": scen_probs,
            "meta_audit": meta_a,
            "rvol": traj["rvol"],
            "gap_fill": traj["gap_fill"],
            "gap_open15": traj["gap_open15"],
            "cvd_div": traj["cvd_div"],
            "round_level": float(round_level),
            "orb_high": traj["orb_high"],
            "orb_low": traj["orb_low"],
            "vol_spikes_cnt": len(traj["vol_spikes"]),
            "whale_anom": whale_anom,
            "gov_risks_cnt": len(gov_risks),
            "overhead_pct": float(vp["overhead_pct"]),
            "res_px": float(vp["res_px"]),
            "sup_px": float(vp["sup_px"]),
            "verify": traj["verify"],
            "knn_match": {
                "matched_dates": traj["knn_match"]["matched_dates"],
                "mean_dist": traj["knn_match"]["mean_dist"],
            },
            "invalidation_alert": traj["invalidation_alert"],
            "weights_evolution": {
                "active_cluster": traj["weights_evolution"]["active_cluster"],
                "active_regime": traj["weights_evolution"]["active_regime"],
                "updates_count": traj["weights_evolution"]["updates_count"],
                "regime_updates_count": traj["weights_evolution"]["regime_updates_count"],
                "last_decomp": traj["weights_evolution"]["last_decomp"],
            },
            "verdict": f"{meter_lbl} (スコア{comp_score} / 想定大引け{active_close_chg:+.2f}% / {mkt_regime['label']} / 信頼度{meta_a['rank']})",
            "summary": m_txt[:450],
            "dd_score": int(comp_score),
            "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        st.session_state["dd_latest_result"] = dd_result
        shared_map = st.session_state.setdefault("shared_ticker_intel", {})
        if not isinstance(shared_map, dict):
            shared_map = {}
            st.session_state["shared_ticker_intel"] = shared_map
        entry_obj = shared_map.get(fc)
        if not isinstance(entry_obj, dict):
            entry_obj = {}
        entry_obj["dd_result"] = dd_result
        entry_obj["dd_updated_at"] = dd_result["updated_at"]
        shared_map[fc] = entry_obj
        _dd_db_set("shared_ticker_intel", shared_map)

    if hasattr(st, "fragment"):
        @st.fragment(run_every="60s" if auto_sync else None)
        def _auto_runner():
            _body()
        _auto_runner()
    else:
        _body()
