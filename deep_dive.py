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
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

DB_PATH = "yamashishi_core.db"
WEIGHTS_EVOLUTION_PATH = "weights_evolution_v3.json"
WEIGHTS_KV_KEY = "dd_weights_evolution_v3"


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


DEFAULT_WEIGHTS_EVOLUTION = {
    "version": 3,
    "lr": 0.035,
    "updates_count": 0,
    "last_updated": "",
    "learned_keys": [],
    "regimes": {
        "TREND": _make_default_brain("TREND"),
        "RANGE": _make_default_brain("RANGE"),
        "NEUTRAL": _make_default_brain("NEUTRAL"),
    },
    "last_decomp": {
        "date": "-",
        "code": "-",
        "regime": "NEUTRAL",
        "open_err_pct": 0.0,
        "intraday_err_pct": 0.0,
        "culprit_open": "-",
        "culprit_intra": "-",
    },
}


# =========================================================================
# 1. DEEP DIVE v13 専用CSS
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
    .dd-sc-bar-bg { width: 100%; height: 4px; background: rgba(148, 163, 184, 0.16); border-radius: 99px; margin-top: 8px; overflow: hidden; }
    .dd-sc-bar-fill { height: 100%; border-radius: 99px; }
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


# =========================================================================
# レジーム別3脳（TREND / RANGE / NEUTRAL）犯人特定型SGD 2分解オンライン学習
# =========================================================================
def _merge_default_weights(raw: dict) -> dict:
    base = json.loads(json.dumps(DEFAULT_WEIGHTS_EVOLUTION))
    if not isinstance(raw, dict):
        return base
    for k in ("version", "lr", "updates_count", "last_updated"):
        if k in raw:
            base[k] = raw[k]
    if isinstance(raw.get("learned_keys"), list):
        base["learned_keys"] = list(dict.fromkeys(str(x) for x in raw["learned_keys"]))[-300:]

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


def _update_weights_two_stage(w_evo: dict, fc_code: str, df_1d: pd.DataFrame, stock_hist: dict, market_today_str: str) -> tuple:
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

    og_bounds = {"macro": (0.15, 1.20), "fx": (0.10, 0.90), "news": (0.20, 1.80), "whale": (0.20, 2.00), "lab_bias": (0.05, 1.00)}
    idr_bounds = {"news": (0.001, 0.015), "dow": (0.05, 0.90), "wick": (0.20, 1.60), "calib": (0.05, 1.00), "lab_bias": (0.10, 1.60)}

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
        p50_arr = snap.get("p50") or []
        if not p50_arr:
            continue

        # リークフリー：スナップショット保存時のレジーム、なければ前日までのデータから当時のレジームを判定
        r_code = str(snap.get("regime_code") or "").upper()
        if r_code not in ("TREND", "RANGE", "NEUTRAL"):
            pos = idx_pos_map.get(dt_k, 0)
            if pos >= 25:
                r_code = _detect_market_regime(df_1d.iloc[:pos])["code"]
            else:
                r_code = "NEUTRAL"

        brain = updated["regimes"][r_code]
        og = brain["open_gap"]
        idr = brain["intraday_drift"]

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
            norm_o = sum(float(v) ** 2 for v in og_x.values()) + 0.25
            worst_o, worst_o_k = 0.0, "-"
            for gk, (b_lo, b_hi) in og_bounds.items():
                xv = float(og_x.get(gk, 0.0))
                if abs(xv) < 1e-5:
                    continue
                delta = float(np.clip(lr * open_err_pct * (xv / norm_o), -0.06, 0.06))
                og[gk] = round(float(np.clip(og[gk] + delta, b_lo, b_hi)), 4)
                if delta < worst_o:
                    worst_o, worst_o_k = delta, gk
            if worst_o_k != "-":
                culprit_open = f"{worst_o_k}({worst_o:+.3f})"
        else:
            step_open = float(np.clip(open_err_pct * lr * 0.06, -0.03, 0.03))
            for gk, (b_lo, b_hi) in og_bounds.items():
                og[gk] = round(float(np.clip(og[gk] + step_open * 0.5, b_lo, b_hi)), 4)

        culprit_intra = "-"
        if idr_x:
            norm_i = sum(float(v) ** 2 for v in idr_x.values()) + 0.25
            worst_i, worst_i_k = 0.0, "-"
            for ik, (b_lo, b_hi) in idr_bounds.items():
                xv = float(idr_x.get(ik, 0.0))
                if abs(xv) < 1e-5:
                    continue
                scale_i = 0.004 if ik == "news" else 1.0
                delta = float(np.clip(lr * intraday_err_pct * (xv / norm_i) * scale_i, -0.06 * scale_i, 0.06 * scale_i))
                idr[ik] = round(float(np.clip(idr[ik] + delta, b_lo, b_hi)), 5 if ik == "news" else 4)
                if (delta / scale_i) < worst_i:
                    worst_i, worst_i_k = (delta / scale_i), ik
            if worst_i_k != "-":
                culprit_intra = f"{worst_i_k}({worst_i:+.3f})"
        else:
            step_intra = float(np.clip(intraday_err_pct * lr * 0.06, -0.03, 0.03))
            for ik, (b_lo, b_hi) in idr_bounds.items():
                if ik == "news":
                    idr[ik] = round(float(np.clip(idr[ik] + step_intra * 0.004, b_lo, b_hi)), 5)
                else:
                    idr[ik] = round(float(np.clip(idr[ik] + step_intra * 0.5, b_lo, b_hi)), 4)

        brain["updates_count"] = int(brain.get("updates_count", 0)) + 1
        updated["last_decomp"] = {
            "date": dt_k,
            "code": fc_code,
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
        updated["learned_keys"] = sorted(learned_set)[-300:]
        _save_weights_evolution(updated)

    return updated, changed


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


def _calc_first_passage_prob(curr_px: float, target_px: float, rem_sigma_pct: float) -> float:
    if curr_px <= 0 or target_px <= 0:
        return 0.0
    dist_pct = abs(target_px - curr_px) / curr_px
    if dist_pct <= 1e-6:
        return 99.0
    sig = max(rem_sigma_pct, 1e-4)
    z = dist_pct / (sig * math.sqrt(2.0))
    prob = math.erfc(z) * 100.0
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
                var shortMap = {{'当日実測':'実測', 'ライブ修正':'ライブ', '朝ロック':'ロック', 'VWAP':'VWAP', '想定波形':'波形'}};
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
# 4. 機関投資家プロ仕様：ガンマピン・CVDダイバージェンス・Gap&Go判定等
# =========================================================================
def _compute_gamma_pin(curr_px: float, is_jp: bool) -> float:
    if is_jp:
        step = 5000 if curr_px >= 20000 else (1000 if curr_px >= 5000 else (500 if curr_px >= 2000 else 100))
    else:
        step = 50 if curr_px >= 400 else (25 if curr_px >= 150 else (10 if curr_px >= 50 else 5))
    return float(round(curr_px / step) * step)


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


def _detect_cvd_divergence(slots: list, actual_arr: list, cvd_arr: list) -> dict:
    pts = [(i, slots[i], actual_arr[i], cvd_arr[i]) for i in range(len(slots)) if actual_arr[i] is not None and cvd_arr[i] is not None]
    if len(pts) < 8:
        return {"state": "WAIT", "label": "計測中", "color": "#94a3b8", "detail": "場中データ蓄積待ち", "marker": None}

    split_i = max(4, len(pts) // 2)
    first_h = pts[:split_i]
    second_h = pts[split_i:]

    p1_hi = max(first_h, key=lambda x: x[2])
    p2_hi = max(second_h, key=lambda x: x[2])
    p1_lo = min(first_h, key=lambda x: x[2])
    p2_lo = min(second_h, key=lambda x: x[2])

    # 天井売り抜け（Bearish Distribution）: 価格が高値更新なのにCVDが切り下がり
    if p2_hi[2] > p1_hi[2] * 1.0015 and p2_hi[3] < p1_hi[3]:
        return {
            "state": "DISTRIBUTION",
            "label": "売り抜け警戒",
            "color": "#ef4444",
            "detail": f"価格が高値更新（{p1_hi[1]}→{p2_hi[1]}）する一方、累積出来高デルタ(CVD)が減少。大口の天井売り抜け（Distribution）の兆候。",
            "marker": {"time": p2_hi[1], "price": p2_hi[2], "name": "売り抜け", "color": "#ef4444"},
        }

    # 底値吸収（Bullish Absorption）: 価格が安値更新なのにCVDが切り上がり
    if p2_lo[2] < p1_lo[2] * 0.9985 and p2_lo[3] > p1_lo[3]:
        return {
            "state": "ABSORPTION",
            "label": "底値吸収",
            "color": "#10b981",
            "detail": f"価格が安値更新（{p1_lo[1]}→{p2_lo[1]}）する一方、累積出来高デルタ(CVD)が上昇。大口の指値買い吸収（Absorption）の兆候。",
            "marker": {"time": p2_lo[1], "price": p2_lo[2], "name": "底値吸収", "color": "#10b981"},
        }

    # ダイバージェンスなし：CVD方向の一致状況
    last_cvd = pts[-1][3]
    if last_cvd > 0:
        return {"state": "ALIGNED_BULL", "label": "買い優勢", "color": "#38bdf8", "detail": "CVDプラス圏で買い主導の推移。", "marker": None}
    if last_cvd < 0:
        return {"state": "ALIGNED_BEAR", "label": "売り優勢", "color": "#f59e0b", "detail": "CVDマイナス圏で売り主導の推移。", "marker": None}
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

    # ギャップダウン (gap_pct <= -0.20)
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


def _build_dual_5m_trajectory(
    fc_code: str, curr_px: float, prev_px: float, df_1d: pd.DataFrame, df_5m: pd.DataFrame,
    macro_sens: list, macro_data: dict, news_res: dict, whale_anom: dict,
    dow_next_avg: float, vp: dict, is_jp: bool, mkt_regime: dict, active_lab: dict = None
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

    actual_map, vwap_map = {}, {}
    vwap_p1_map, vwap_m1_map, vwap_p2_map, vwap_m2_map = {}, {}, {}, {}
    act_vol_map, act_dir_map, act_low_map, act_high_map = {}, {}, {}, {}
    cvd_map = {}
    orb_high, orb_low = None, None

    if df_5m is not None and not df_5m.empty:
        tmp_a = df_5m.copy()
        idx_a = pd.to_datetime(tmp_a.index)
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

                    # 疑似オーダーフロー（Intraday CVD）: CLV * Volume の累積
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

    # レジーム別3脳SGDの読み込み＆更新
    w_evo = _load_weights_evolution()
    w_evo, weights_updated = _update_weights_two_stage(w_evo, fc_code, df_1d, stock_hist, market_today_str)
    active_brain = w_evo["regimes"].get(regime_code, w_evo["regimes"]["NEUTRAL"])
    og_w = active_brain["open_gap"]
    idr_w = active_brain["intraday_drift"]

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
    lab_bias_pct = round(lab_strength_dir * idr_w["lab_bias"], 2)
    dow_adj = float(np.clip(raw_dow_x * idr_w["dow"], -0.4, 0.4))
    wick_adj = round(float(np.clip(raw_wick_x * (idr_w["wick"] / 0.80), -0.55, 0.55)), 2)

    tot_gap = float(np.clip(mg + fg + ng + wg + lab_bias_pct * og_w["lab_bias"], -5.0, 5.0))

    raw_calib_pct, calib_n = _compute_self_calibration(stock_hist, df_1d, market_today_str)
    calib_pct = round(float(np.clip(raw_calib_pct * (idr_w["calib"] / 0.40), -0.65, 0.65)), 2)

    slot_means, slot_stds, slot_vols = np.zeros(n_slots), np.full(n_slots, 0.003), np.zeros(n_slots)
    regime_tag = "標準"
    rmaps, rdates = [], []
    gap_fill_stats = {"prob": None, "avg_min": None, "n_samples": 0, "dir": "FLAT"}

    if df_5m is not None and not df_5m.empty:
        tmp = df_5m.copy()
        idx_dt = pd.to_datetime(tmp.index)
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

            rm, vm = {}, {}
            for _, row in sub.iterrows():
                if row["_hm"] in slots:
                    rm[row["_hm"]] = (float(row["Close"]) - op) / op
                    vm[row["_hm"]] = float(row["Volume"])
            if rm:
                base_w = float(np.exp(1.2 * (di / max(len(pdays) - 1, 1))))
                if (want_gu and day_gap > 0.1) or (want_gd and day_gap < -0.1):
                    base_w *= 2.5
                rmaps.append(rm)
                rdates.append(ds)
                vmaps.append(vm)
                weights.append(base_w)

        if gf_total >= 2:
            gap_fill_stats = {
                "prob": round(gf_filled / gf_total * 100.0, 0),
                "avg_min": int(round(float(np.mean(gf_mins)), 0)) if gf_mins else None,
                "n_samples": gf_total,
                "dir": "GU" if target_gap_dir > 0 else ("GD" if target_gap_dir < 0 else "BOTH"),
            }

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

    # 流動性インパクト計算用の平均5分足出来高
    pos_vols = [v for v in slot_vols if v > 0]
    avg_5m_vol = float(np.mean(pos_vols)) if pos_vols else (float(df_1d["Volume"].tail(20).mean()) / max(n_slots, 1))

    # CVDダイバージェンス ＆ 寄り後15分 Gap & Go / Fade 判定
    cvd_div = _detect_cvd_divergence(slots, actual_arr, cvd_arr)
    gap_open15 = _evaluate_gap_open15(
        has_actual, slots, actual_arr, vwap_arr,
        act_low_map, act_high_map, act_vol_map, slot_vols, prev_px
    )

    est_open = anchor_base_close * (1.0 + tot_gap / 100.0)
    drift = float(np.clip((raw_news_x * idr_w["news"]) + ((dow_adj + wick_adj + calib_pct + lab_bias_pct) / 100.0), -0.032, 0.032))
    vboost = (1.0 + abs(raw_news_x) * 0.25) * (1.0 + max(0.0, vix_d / 100.0) * 1.2)

    rem_frac_now = max((n_slots - 1 - last_act_idx) / max(n_slots - 1, 1), 0.04) if (has_actual and last_act_idx >= 0) else 1.0
    rem_sigma_pct = float(slot_stds[-1]) * math.sqrt(rem_frac_now) * vboost

    hvn_wall_px, ob_sup_px = 0.0, 0.0
    if isinstance(active_lab, dict) and active_lab:
        d2_ctx = active_lab.get("daily_2y") if isinstance(active_lab.get("daily_2y"), dict) else {}
        hvn_wall_px = float(d2_ctx.get("hvn_wall_price", 0.0) or 0.0)
        ob_sup_px = float(active_lab.get("ob_support_px", 0.0) or 0.0)

    p50, p85, p15, bdiff = [], [], [], []
    p68, p32, bdiff_inner = [], [], []
    for i, sl in enumerate(slots):
        frac = i / max(n_slots - 1, 1)
        mid = est_open * (1.0 + slot_means[i] + drift * frac)
        mid = _apply_hvn_ob_bounce(mid, hvn_wall_px, ob_sup_px, vp)
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
                "p32": p32, "band_diff_in": bdiff_inner, "sim_line": sim_line,
                "regime_code": regime_code,
                "pred_open_px": round(float(est_open), 4),
                "pred_open_gap_pct": round(float(tot_gap), 4),
                "factor_contribs": {
                    "open_gap": {
                        "macro": round(raw_macro_x, 4),
                        "fx": round(raw_fx_x, 4),
                        "news": round(raw_news_x, 4),
                        "whale": round(raw_whale_x, 4),
                        "lab_bias": round(lab_bias_pct, 4),
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

    knn_match = {"matched_dates": [], "mean_dist": None, "knn_rel_moves": {}}
    if has_actual and last_act_idx >= 2 and rmaps:
        valid_slots = [slots[i] for i in range(last_act_idx + 1) if actual_arr[i] is not None]
        if len(valid_slots) >= 3:
            first_px = actual_map[valid_slots[0]]
            today_vec = np.array([(actual_map[sl] - first_px) / max(first_px, 1e-4) for sl in valid_slots], dtype=float)
            cands = []
            for ds, rm in zip(rdates, rmaps):
                if all(sl in rm for sl in valid_slots):
                    hist_vec = np.array([rm[sl] for sl in valid_slots], dtype=float)
                    dist = float(np.linalg.norm(today_vec - hist_vec))
                    cands.append((dist, ds, rm))
            if cands:
                cands.sort(key=lambda x: x[0])
                top_k = cands[:5]
                dists = np.array([c[0] for c in top_k], dtype=float)
                w_knn = 1.0 / (dists + 1e-6)
                w_knn /= w_knn.sum()
                anchor_sl = slots[last_act_idx]
                knn_rel = {}
                for i in range(last_act_idx, n_slots):
                    sl = slots[i]
                    vals_i, ws_i = [], []
                    for (_, _, rm_k), wk in zip(top_k, w_knn):
                        if sl in rm_k and anchor_sl in rm_k:
                            vals_i.append(rm_k[sl] - rm_k[anchor_sl])
                            ws_i.append(wk)
                    if vals_i:
                        ws_arr = np.array(ws_i) / np.sum(ws_i)
                        knn_rel[i] = float(np.sum(ws_arr * np.array(vals_i)))
                knn_match = {
                    "matched_dates": [c[1] for c in top_k],
                    "mean_dist": round(float(np.mean(dists)), 5),
                    "knn_rel_moves": knn_rel
                }

    live_vwap_bias = 0.0
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
        live_vwap_bias = float(np.clip(vwap_gap * 0.45 + mom_30m * 0.35 + gap15_bias, -0.018, 0.018))
        knn_moves = knn_match["knn_rel_moves"]

        for i in range(last_act_idx, n_slots):
            rem_frac = (i - last_act_idx) / max(n_slots - 1 - last_act_idx, 1)
            base_rel = (slot_means[i] - anchor_mean) + (drift * 0.6 + live_vwap_bias) * rem_frac
            rel_move = (0.70 * base_rel + 0.30 * knn_moves[i]) if (i in knn_moves) else base_rel
            mid = anchor_px * (1.0 + rel_move)
            mid = _apply_hvn_ob_bounce(mid, hvn_wall_px, ob_sup_px, vp)
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

    inv_reasons = []
    if has_actual and last_act_idx >= 0:
        cur_a = actual_arr[last_act_idx]
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
        if knn_match["mean_dist"] is not None and knn_match["mean_dist"] > 0.06:
            inv_reasons.append(f"k-NN過去類似日と大きく乖離（未知レジーム: dist={knn_match['mean_dist']}）")

    invalidation_alert = {
        "triggered": len(inv_reasons) > 0,
        "severity": "HIGH" if len(inv_reasons) >= 2 else ("MEDIUM" if inv_reasons else "NONE"),
        "reasons": inv_reasons
    }

    imin, imax = int(np.argmin(locked_p50)), int(np.argmax(locked_p50))
    return {
        "target_date": target_date, "is_locked": is_locked, "has_actual": has_actual, "last_act_idx": last_act_idx,
        "slots": slots, "lunch_idx": lunch_idx, "vols": [round(float(v), 1) for v in slot_vols],
        "actual": actual_arr, "vwap": vwap_arr,
        "vwap_p1": vwap_p1_arr, "vwap_m1": vwap_m1_arr, "vwap_p2": vwap_p2_arr, "vwap_m2": vwap_m2_arr,
        "rvol": rvol, "orb_high": orb_high, "orb_low": orb_low, "vol_spikes": vol_spikes,
        "avg_5m_vol": avg_5m_vol, "cvd_div": cvd_div, "gap_open15": gap_open15,
        "gap_fill": gap_fill_stats, "rem_sigma_pct": rem_sigma_pct, "rem_frac_now": rem_frac_now,
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
        "knn_match": {"matched_dates": knn_match["matched_dates"], "mean_dist": knn_match["mean_dist"]},
        "invalidation_alert": invalidation_alert,
        "weights_evolution": {
            "active_regime": regime_code,
            "updates_count": w_evo.get("updates_count", 0),
            "regime_updates_count": active_brain.get("updates_count", 0),
            "weights_updated": weights_updated,
            "open_gap": og_w,
            "intraday_drift": idr_w,
            "all_regimes": w_evo.get("regimes", {}),
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
                        return txt.strip(), f"🔵 AUTO GLOBAL AI ANALYST ({mod} / 一次報道{t1}件 / 15mキャッシュ)"
            except Exception:
                continue

    lab_extra = f"\n・LAB連携情報: {lab_deep_ctx}" if lab_deep_ctx else ""
    bull = f"・LAB本体判定: {lab_note}{lab_extra}。現在値 {px_s} に対しアナリスト目標乖離は {up}、高信頼ニュース強気度 {pos_pct}%（一次報道{t1}件）。\n・{bull_trig} を明確に上抜ければ強気突破が発動し、上値メド {bull_tgt} を目指す展開。\n・下値は大口買い支え帯 {sup_s} がサポートとして機能しやすい構造。"
    bear = f"・{ml} との相関係数が {mc}（β={mb}）で、夜間先物や米市場の急変時に連れ安リスクあり。\n・上値しこり玉は {ovh}%、直上の大口売り壁 {res_s} 付近では戻り売りに要注意。\n・{bear_trig} 割れで下値メド {bear_tgt} までの下振れを警戒し早期撤退。ガバナンス報道は {gov_cnt}件検知。"
    cat = f"・大口・インサイダー動向: {whale_sum}。\n・明日の勝負時間帯は押し目候補の {dip_t} 前後での反発確認と、ピーク想定の {peak_t} 前後での分割利確。\n・寄付直後に想定始値 {traj_open} を維持できるかが最初の分岐点。"
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
    """初心者向けの3ステップ＋専門用語の階層化ガイド"""
    st.markdown("""
    <div class="dd-guide-box">
    <b>🔰 最初に見る3ポイント</b><br>
    1. <b>予測軌道チャート:</b> 白線(実測)が青い帯(予測レンジ)の中に収まっているかを確認。右上の <b>⛶ 横拡大</b> でスマホ横向きフル大画面にできます。<br>
    2. <b>3つのシナリオカード:</b> 「押し目・高値の時間帯」と「上振れ/下振れトリガー価格」をチェック。<br>
    3. <b>適正ロット電卓:</b> 許容損失額を入れると、日本株100株単元・流動性インパクト・TP到達確率(FPT)を自動計算します。<br>
    <hr style="border-color:rgba(56,189,248,0.22);margin:7px 0;">
    <b>■ プロ仕様 魔改造インジケーターガイド</b><br>
    ・<b>疑似オーダーフロー(CVD):</b> 高値更新なのにCVD低下＝大口の売り抜け警戒 / 安値更新なのにCVD上昇＝大口の底値吸収。<br>
    ・<b>初動15分 Gap&Go / Fade:</b> 寄り3本のVWAP位置×RVOLから本物トレンドか窓埋め騙しかを即判定。<br>
    ・<b>3脳SGD学習:</b> トレンド脳・レンジ脳・中立脳の重みを独立学習し、相場転換時の揺り戻しを防止。<br>
    ・<b>RVOL / VWAP±σ / 流動性インパクト:</b> 同時刻出来高比、機関執行帯、自分の注文が板に与えるスリッページ負荷を計測。
    </div>
    """, unsafe_allow_html=True)


# =========================================================================
# 5. メインエントリ関数（YAMASHISHI LAB から呼び出す）
# =========================================================================
def render_deep_dive_page(init_code: str = "NVDA", init_style: str = "デイトレード", gemini_api_key: str = "", lab_ctx: dict = None):
    _inject_dd_css()

    # コンパクト・ヘッダー（タイトル + 📖 見方ガイド + LABへ戻る）
    h1, h2, h3 = st.columns([2.4, 1.0, 1.2])
    with h1:
        st.markdown(
            '<div class="glass-header" style="margin-bottom:4px;padding:8px 12px;">'
            '<div class="brand-luxury" style="font-size:15px;">YAMASHISHI DEEP DIVE v13</div>'
            '<div style="font-size:10px;color:#94a3b8;">3脳SGD・CVD大口透視・初動15分Gap判定・100株流動性電卓</div>'
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
        with ThreadPoolExecutor(max_workers=2) as ex_core:
            fut_stk = ex_core.submit(_load_stock_core, fc)
            fut_mac = ex_core.submit(_load_macro_data)
            data = fut_stk.result()
            macro_data = fut_mac.result()

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

        mkt_regime = _detect_market_regime(df_1d)
        gamma_pin = _compute_gamma_pin(curr_px, is_jp)
        macro_sens = _compute_macro_sens(df_1d["Close"], macro_data)
        dow_stats, next_wd = _compute_dow_edge(df_1d)
        with ThreadPoolExecutor(max_workers=2) as ex_intel:
            fut_news = ex_intel.submit(_fetch_global_intel, corp_name, short_code)
            fut_gov = ex_intel.submit(_fetch_gov_and_whales, corp_name, short_code)
            news_res = fut_news.result()
            gov_risks, whale_news = fut_gov.result()
        whale_anom = _detect_whale_anomaly(data["insider_tx"], whale_news)
        vp = _compute_vp(df_1d, curr_px, is_jp)
        traj = _build_dual_5m_trajectory(
            fc, curr_px, prev_px, df_1d, df_5m, macro_sens, macro_data,
            news_res, whale_anom, dow_stats[next_wd]["avg"], vp, is_jp,
            mkt_regime=mkt_regime, active_lab=active_lab
        )

        # ステータス・ピル＋統合詳細ドロワー
        status_pills = []
        alert_blocks = []
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
            status_pills.append('<span class="dd-st-pill" style="border-color:#ef4444;background:rgba(239,68,68,0.20);color:#fecaca;">🚨 CVD売り抜け</span>')
            alert_blocks.append(f'<div class="dd-warn-box"><b>🚨 疑似オーダーフロー（CVD）天井売り抜け検知</b><br>{html.escape(cvd_div["detail"])}</div>')
        elif cvd_div["state"] == "ABSORPTION":
            status_pills.append('<span class="dd-st-pill" style="border-color:#10b981;background:rgba(16,185,129,0.18);color:#6ee7b7;">🧲 CVD底値吸収</span>')
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
            dd_bull = (traj["est_close_chg"] >= 0)
            is_aligned = (l_side == "LONG" and dd_bull) or (l_side == "SHORT" and not dd_bull)
            lab_note = f"LAB判定={l_side} (期待度{active_lab.get('expect_pct',0)}% / TP:{_fmt_cur(l_tp, is_jp)} / SL:{_fmt_cur(l_sl, is_jp)})"
            if is_aligned:
                status_pills.append(f'<span class="dd-st-pill" style="border-color:#10b981;background:rgba(16,185,129,0.16);color:#6ee7b7;">✅ LAB一致({l_side})</span>')
                alert_blocks.append(f'<div class="dd-quant-box"><b>✅ LAB × DEEP DIVE 方向性一致（{l_side} 同期）</b><br>LAB上位足判定（期待度 {active_lab.get("expect_pct",0)}% / {html.escape(str(active_lab.get("exec_grade","")).split("（")[0])}）と5分足予測軌道（{traj["est_close_chg"]:+.2f}%）が一致。TP: <b>{_fmt_cur(l_tp, is_jp)}</b> / SL: <b>{_fmt_cur(l_sl, is_jp)}</b></div>')
            else:
                status_pills.append(f'<span class="dd-st-pill" style="border-color:#f59e0b;background:rgba(245,158,11,0.16);color:#fef3c7;">⚠️ LAB乖離({l_side})</span>')
                alert_blocks.append(f'<div class="dd-sync-warn"><b>⚠️ LAB × DEEP DIVE 方向性に乖離あり（慎重待機推奨）</b><br>LAB上位足判定は <b>{l_side}</b>（期待度 {active_lab.get("expect_pct",0)}%）ですが、5分足短期軌道は <b>{traj["est_close_chg"]:+.2f}%</b> と逆方向を示唆。</div>')

        if whale_anom["detected"]:
            w_col = "#10b981" if whale_anom["dir"] == "BULL" else "#ef4444"
            status_pills.append(f'<span class="dd-st-pill" style="border-color:{w_col};background:rgba(15,23,42,0.85);color:{w_col};">🐋 大口{whale_anom["dir"]}({whale_anom["adj_pct"]:+.2f}%)</span>')
            b_cls = "dd-quant-box" if whale_anom["dir"] == "BULL" else "dd-warn-box"
            alert_blocks.append(f'<div class="{b_cls}"><b>🚨 大口・インサイダー異変検知（予測軌道へ {whale_anom["adj_pct"]:+.2f}% 自動反映済）</b><br>{html.escape(whale_anom["summary"])}</div>')

        if status_pills:
            st.markdown(f'<div class="dd-status-strip">{"".join(status_pills)}</div>', unsafe_allow_html=True)

        if alert_blocks or lab_full or lab_council:
            n_info = len(alert_blocks) + (1 if (lab_full or lab_council) else 0)
            with st.expander(f"🔔 アラート・LAB 3階層MTF詳細 ({n_info}件)", expanded=False):
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
        aura_col = "#10b981" if traj["est_open_gap_pct"] >= 0 else "#ef4444"
        aura_glow = "rgba(16,185,129,0.22)" if traj["est_open_gap_pct"] >= 0 else "rgba(239,68,68,0.22)"
        target_mean = info.get("targetMeanPrice")
        upside_str = f"{((target_mean - curr_px)/curr_px*100):+.1f}%" if (target_mean and curr_px > 0) else "-"
        risk_status, risk_col = (f"⚠️ {len(gov_risks)}件", "#f87171") if gov_risks else ("🟢 クリーン", "#10b981")

        # ヒーローカード
        st.markdown(f"""
        <div class="rank-card" style="border-left-color:{aura_col};box-shadow:0 8px 26px {aura_glow};margin-top:2px;margin-bottom:8px;">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;flex-wrap:wrap;">
            <div style="min-width:0;flex:1;">
              <div><span class="pill-badge">{html.escape(fc)}</span><span class="pill-badge" style="border-color:rgba(168,85,247,0.45);background:rgba(168,85,247,0.16);color:#e9d5ff;">{html.escape(in_style)}</span><span class="pill-badge" style="border-color:{mkt_regime['color']};background:rgba(15,23,42,0.8);color:{mkt_regime['color']};">{mkt_regime['label']}・{mkt_regime['code']}脳</span>{earn_badge}</div>
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
            <div><div class="dd-metric-lbl">寄付き予測</div><div class="dd-metric-val" style="color:{aura_col};">{traj['est_open_gap_pct']:+.2f}%</div></div>
            <div><div class="dd-metric-lbl">アナリスト乖離</div><div class="dd-metric-val" style="color:#fde047;">{upside_str}</div></div>
            <div><div class="dd-metric-lbl">上値しこり玉</div><div class="dd-metric-val" style="color:#c084fc;">{vp['overhead_pct']}%</div></div>
            <div><div class="dd-metric-lbl">ガバナンス</div><div class="dd-metric-val" style="color:{risk_col};">{risk_status}</div></div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        t1, t2, t3, t4 = st.tabs(["翌営業日 1日軌道", "マクロβ・曜日", "財務・大口株主", "リスク・AIメモ"])

        with t1:
            # 機関投資家テレメトリバー（6項目：RVOL / 窓埋め / キリ番 / 大口◆ / CVD / 初動15分）
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
              <div class="dd-inst-card"><div class="dd-metric-lbl">キリ番節目 (Pin)</div><div style="font-family:'JetBrains Mono',monospace;font-size:11.5px;font-weight:800;color:#fde047;margin-top:2px;">{_fmt_cur(gamma_pin, is_jp)}</div></div>
              <div class="dd-inst-card"><div class="dd-metric-lbl">大口約定スパイク</div><div style="font-family:'JetBrains Mono',monospace;font-size:11.5px;font-weight:800;color:{'#c084fc' if n_sp>0 else '#94a3b8'};margin-top:2px;">{sp_txt}</div></div>
              <div class="dd-inst-card"><div class="dd-metric-lbl">CVD オーダーフロー</div><div style="font-family:'JetBrains Mono',monospace;font-size:11.5px;font-weight:800;color:{cvd_div['color']};margin-top:2px;">{html.escape(cvd_div['label'])}</div></div>
              <div class="dd-inst-card"><div class="dd-metric-lbl">寄り15分 Gap判定</div><div style="font-family:'JetBrains Mono',monospace;font-size:11.5px;font-weight:800;color:{g15['color']};margin-top:2px;">{html.escape(g15['label'])}</div></div>
            </div>
            """, unsafe_allow_html=True)

            # 目的別プリセット ＋ ⚙️表示設定
            presets = ["📈 今の予測", "🔍 朝の答え合わせ", "🏦 大口・節目"]
            modes = ["🔴 ライブ修正", "🔒 朝ロック検証", "⚡ 両方重ね"]
            line_opts = [
                "予測レンジ帯（ファン）", "押目・利確ゾーン", "VWAP", "VWAP±σ",
                "キリ番節目（Pin）", "寄り30分高安（ORB）", "大口約定（◆）", "想定波形", "出来高"
            ] + (["LAB TP/SL"] if active_lab else [])

            p_col, cfg_col = st.columns([3.2, 1.1])
            with p_col:
                if hasattr(st, "pills"):
                    sel_preset = st.pills("表示プリセット", presets, default="📈 今の予測", selection_mode="single", label_visibility="collapsed", key="dd_preset_sel") or "📈 今の予測"
                else:
                    sel_preset = st.radio("表示プリセット", presets, index=0, horizontal=True, label_visibility="collapsed", key="dd_preset_sel")

            if sel_preset == "📈 今の予測":
                pr_mode_idx = 2
                pr_lines = ["予測レンジ帯（ファン）", "押目・利確ゾーン", "VWAP", "キリ番節目（Pin）", "大口約定（◆）", "出来高"] + (["LAB TP/SL"] if active_lab else [])
            elif sel_preset == "🔍 朝の答え合わせ":
                pr_mode_idx = 1
                pr_lines = ["予測レンジ帯（ファン）", "想定波形", "寄り30分高安（ORB）", "出来高"]
            else:
                pr_mode_idx = 0
                pr_lines = ["VWAP", "VWAP±σ", "キリ番節目（Pin）", "大口約定（◆）", "押目・利確ゾーン", "出来高"] + (["LAB TP/SL"] if active_lab else [])

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
                "📈 今の予測": "ライブ修正軌道 ＋ 押し目/利確帯 ＋ 大口約定（右上の「⛶ 横拡大」で横向き大画面）",
                "🔍 朝の答え合わせ": "朝ロック予測 vs 当日実測 ＋ 想定波形 ＋ 寄り30分高安",
                "🏦 大口・節目": "VWAP±σバンド ＋ キリ番節目 ＋ 大口約定スパイク",
            }
            st.caption(f"表示中: {preset_desc.get(sel_preset, '')}")

            if traj["verify"]["has_verify"] and chart_mode in ("🔒 朝ロック検証", "⚡ 両方重ね"):
                v = traj["verify"]
                st.markdown(f'<div class="dd-quant-box"><b>📊 朝ロック予測 vs 当日実測 ガチ検証（実測 {v["n_pts"]}本）</b><br>・<b>確率ファン内 収束率:</b> <b style="color:#fde047;">{v["in_cone_pct"]}%</b> ｜ <b>平均誤差:</b> <b>{v["err_pct"]}%</b></div>', unsafe_allow_html=True)

            # 水平・垂直ライン
            ml_data = []
            if traj["lunch_idx"] is not None:
                ml_data.append({"xAxis": traj["slots"][traj["lunch_idx"]], "lineStyle": {"color": "rgba(148,163,184,0.3)", "type": "dashed"}, "label": {"formatter": "前/後場", "color": "#94a3b8", "fontSize": 9, "position": "insideEndTop"}})
            if g15.get("show_gap_target") and prev_px > 0:
                ml_data.append({"yAxis": round(prev_px, 2), "lineStyle": {"color": "#f97316", "type": "dashed", "width": 1.6}, "label": {"formatter": f"窓埋目標 {_fmt_cur(prev_px, is_jp)}", "color": "#fdba74", "fontSize": 9, "position": "insideEndTop"}})
            if "キリ番節目（Pin）" in opt_lines:
                ml_data.append({"yAxis": gamma_pin, "lineStyle": {"color": "rgba(250,204,21,0.55)", "type": "dotted", "width": 1.3}, "label": {"formatter": f"Pin {_fmt_cur(gamma_pin, is_jp)}", "color": "#fde047", "fontSize": 8.5, "position": "insideStartTop"}})
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
                d_s, d_e = max(0, traj["dip_idx"] - 2), min(n_sl - 1, traj["dip_idx"] + 2)
                p_s, p_e = max(0, traj["peak_idx"] - 2), min(n_sl - 1, traj["peak_idx"] + 2)
                ma_data.append([{"name": "押目帯", "xAxis": traj["slots"][d_s], "itemStyle": {"color": "rgba(16, 185, 129, 0.09)"}, "label": {"position": "insideTop", "color": "#6ee7b7", "fontSize": 8.5}}, {"xAxis": traj["slots"][d_e]}])
                ma_data.append([{"name": "利確帯", "xAxis": traj["slots"][p_s], "itemStyle": {"color": "rgba(239, 68, 68, 0.09)"}, "label": {"position": "insideTop", "color": "#fca5a5", "fontSize": 8.5}}, {"xAxis": traj["slots"][p_e]}])
                if vp["overhead_pct"] >= 25.0:
                    ma_data.append([{"name": "売り壁", "yAxis": round(vp["res_px"] * 0.996, 2), "itemStyle": {"color": "rgba(168, 85, 247, 0.13)"}, "label": {"position": "insideLeft", "color": "#d8b4fe", "fontSize": 8.5}}, {"yAxis": round(vp["res_px"] * 1.004, 2)}])
            ma_cfg = {"silent": True, "data": ma_data} if ma_data else {}

            s_list, l_names = [], []
            if "出来高" in opt_lines:
                s_list.append({"name": "出来高", "type": "bar", "yAxisIndex": 1, "data": traj["vols"], "itemStyle": {"color": "rgba(148,163,184,0.14)", "borderRadius": [2, 2, 0, 0]}, "barMaxWidth": 4})

            if "予測レンジ帯（ファン）" in opt_lines:
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

            if "VWAP±σ" in opt_lines and traj["has_actual"]:
                s_list.extend([
                    {"name": "VWAP+1σ", "type": "line", "yAxisIndex": 0, "data": traj["vwap_p1"], "lineStyle": {"color": "rgba(245,158,11,0.55)", "width": 1.0, "type": "dashed"}, "showSymbol": False, "silent": True},
                    {"name": "VWAP-1σ", "type": "line", "yAxisIndex": 0, "data": traj["vwap_m1"], "lineStyle": {"color": "rgba(245,158,11,0.55)", "width": 1.0, "type": "dashed"}, "showSymbol": False, "silent": True},
                    {"name": "VWAP+2σ", "type": "line", "yAxisIndex": 0, "data": traj["vwap_p2"], "lineStyle": {"color": "rgba(239,68,68,0.45)", "width": 1.0, "type": "dotted"}, "showSymbol": False, "silent": True},
                    {"name": "VWAP-2σ", "type": "line", "yAxisIndex": 0, "data": traj["vwap_m2"], "lineStyle": {"color": "rgba(16,185,129,0.45)", "width": 1.0, "type": "dotted"}, "showSymbol": False, "silent": True},
                ])

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

            if "大口約定（◆）" in opt_lines and traj["vol_spikes"]:
                sp_pts = [{"value": [sp["time"], sp["price"]], "itemStyle": {"color": "#10b981" if sp["dir"] > 0 else "#ef4444", "borderColor": "#ffffff", "borderWidth": 1}} for sp in traj["vol_spikes"]]
                s_list.append({"name": "大口約定", "type": "scatter", "yAxisIndex": 0, "symbol": "diamond", "symbolSize": 9, "data": sp_pts, "z": 10})

            pulse_pts = [
                {"name": "押目", "value": [traj["dip_time"], traj["dip_px"]], "itemStyle": {"color": "#10b981"}},
                {"name": "高値", "value": [traj["peak_time"], traj["peak_px"]], "itemStyle": {"color": "#f43f5e"}}
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

            # 適正ロット＆EV電卓 ＋ 日本株100株単元 ＋ 流動性インパクト ＋ FPT到達確率
            with st.expander("🧮 適正ロット・100株単元・流動性インパクト・FPT電卓", expanded=False):
                l_tp_ev = float(active_lab.get("tp", active_lab.get("raw_tp", 0.0)) or 0.0) if active_lab else 0.0
                l_sl_ev = float(active_lab.get("sl", active_lab.get("raw_sl", 0.0)) or 0.0) if active_lab else 0.0
                def_tp = l_tp_ev if l_tp_ev > 0 else traj["bull_target"]
                def_sl = l_sl_ev if l_sl_ev > 0 else traj["bear_trig"]
                ec1, ec2 = st.columns([1.4, 1.0])
                risk_amt = ec1.number_input(
                    "1回の許容損失額 (" + ("円" if is_jp else "$") + ")",
                    min_value=10.0,
                    value=10000.0 if is_jp else 100.0,
                    step=1000.0 if is_jp else 25.0,
                    key=f"dd_risk_amt_{'jp' if is_jp else 'us'}"
                )
                win_prob = ec2.slider("想定勝率 (%)", 30, 80, int(active_lab.get("expect_pct", 55)) if active_lab else 55, key="dd_win_prob")

                risk_per_sh = max(abs(curr_px - def_sl), curr_px * 0.005)
                rew_per_sh = max(abs(def_tp - curr_px), curr_px * 0.005)
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

                # 流動性インパクト（自分の注文株数 ÷ 5分足平均出来高）
                avg_5m_v = max(float(traj.get("avg_5m_vol", 1.0)), 1.0)
                impact_pct = (calc_shares / avg_5m_v) * 100.0
                imp_col = "#ef4444" if impact_pct >= 2.0 else ("#f59e0b" if impact_pct >= 0.8 else "#10b981")

                tp_fpt = _calc_first_passage_prob(curr_px, def_tp, traj["rem_sigma_pct"])
                sl_fpt = _calc_first_passage_prob(curr_px, def_sl, traj["rem_sigma_pct"])
                rem_pct_lbl = int(round(traj["rem_frac_now"] * 100))

                st.markdown(f"""
                <div style="font-size:11px;color:#94a3b8;">基準: Entry <b>{_fmt_cur(curr_px, is_jp)}</b> / TP <b>{_fmt_cur(def_tp, is_jp)}</b> / SL <b>{_fmt_cur(def_sl, is_jp)}</b>（残存時間 {rem_pct_lbl}%）</div>
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
                ("大口・インサイダー異変", f["whale_gap_pct"]),
                ("LAB上位足バイアス", f["lab_bias_pct"]),
                ("曜日エッジ＋ヒゲ圧力", f["dow_wick_pct"]),
                ("台帳キャリブレーション", f["calib_pct"]),
                ("場中VWAP・30分勢い・Gap15", f["live_vwap_pct"]),
            ], key=lambda x: abs(x[1]), reverse=True)

            top3_html = "".join([
                f'<div class="dd-factor-row"><span>{html.escape(lbl)}</span><span style="font-family:JetBrains Mono,monospace;color:{"#10b981" if val>=0 else "#ef4444"};">{val:+.2f}%</span></div>'
                for lbl, val in ranked_factors[:3]
            ])
            st.markdown(f"""
            <div class="dd-dark-box">
              <div style="font-size:11px;font-weight:800;color:#38bdf8;margin-bottom:4px;">KEY DRIVERS // 主要寄与 Top3（{html.escape(traj['regime_tag'])}・{we['active_regime']}脳 {we['regime_updates_count']}回 / 累計{we['updates_count']}回）</div>
              {top3_html}
              <div class="dd-factor-row"><span>合成・寄付き予測 → 大引け予測</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if traj['est_close_chg']>=0 else '#ef4444'};">{traj['est_open_gap_pct']:+.2f}% → {traj['est_close_chg']:+.2f}%</span></div>
            </div>
            """, unsafe_allow_html=True)

            with st.expander("🔬 全ファクター内訳（12項目）＆ 3脳SGD進化重み", expanded=False):
                st.markdown(f"""
                <div class="dd-dark-box" style="margin-bottom:8px;">
                  <div class="dd-factor-row"><span>主連動（{html.escape(f['mkt_label'])} {f['mkt_diff']:+.2f}% × β{f['mkt_beta']:+.2f} × 重み{og_now['macro']:.2f}）</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['macro_gap_pct']>=0 else '#ef4444'};">{f['macro_gap_pct']:+.2f}%</span></div>
                  <div class="dd-factor-row"><span>為替（ドル円 {f['fx_diff']:+.2f}% × β{f['fx_beta']:+.2f} × 重み{og_now['fx']:.2f}）</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['fx_gap_pct']>=0 else '#ef4444'};">{f['fx_gap_pct']:+.2f}%</span></div>
                  <div class="dd-factor-row"><span>日英高信頼ニュース修正（一次報道 {news_res['tier1_cnt']}件・重み{og_now['news']:.2f}）</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['news_gap_pct']>=0 else '#ef4444'};">{f['news_gap_pct']:+.2f}%</span></div>
                  <div class="dd-factor-row"><span>大口・インサイダー異変補正（重み{og_now['whale']:.2f}）</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['whale_gap_pct']>=0 else '#ef4444'};">{f['whale_gap_pct']:+.2f}%</span></div>
                  <div class="dd-factor-row"><span>LAB上位足 方向性・期待度バイアス（日中重み{idr_now['lab_bias']:.2f}）</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['lab_bias_pct']>=0 else '#ef4444'};">{f['lab_bias_pct']:+.2f}%</span></div>
                  <div class="dd-factor-row"><span>HVNしこり壁 / 機関OB支持帯</span><span style="font-family:'JetBrains Mono',monospace;color:#c084fc;">HVN {hvn_str} / OB {ob_str}</span></div>
                  <div class="dd-factor-row"><span>曜日エッジ ＋ 直近5日ヒゲ圧力補正</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['dow_wick_pct']>=0 else '#ef4444'};">{f['dow_wick_pct']:+.2f}%</span></div>
                  <div class="dd-factor-row"><span>台帳自己学習キャリブレーション（過去{f['calib_n']}日）</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['calib_pct']>=0 else '#ef4444'};">{f['calib_pct']:+.2f}%</span></div>
                  <div class="dd-factor-row"><span>場中VWAP・30分勢い・初動15分Gap補正（ライブ反映）</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if f['live_vwap_pct']>=0 else '#ef4444'};">{f['live_vwap_pct']:+.2f}%</span></div>
                  <div class="dd-factor-row"><span>k-NN類似日マッチ（上位類似日）</span><span style="font-family:'JetBrains Mono',monospace;color:#7dd3fc;">{html.escape(knn_dates_str)}</span></div>
                  <div class="dd-factor-row"><span>3脳SGD誤差（{html.escape(str(ld.get('date','-')))} / {html.escape(str(ld.get('regime','NEUTRAL')))}脳）</span><span style="font-family:'JetBrains Mono',monospace;color:#fde047;">寄付 {float(ld.get('open_err_pct',0.0)):+.2f}% / 日中 {float(ld.get('intraday_err_pct',0.0)):+.2f}%</span></div>
                  <div class="dd-factor-row"><span>直近の減点犯人ファクター</span><span style="font-family:'JetBrains Mono',monospace;color:#fca5a5;">寄付:{html.escape(str(ld.get('culprit_open','-')))} / 日中:{html.escape(str(ld.get('culprit_intra','-')))}</span></div>
                </div>
                """, unsafe_allow_html=True)
                st.json({
                    "active_regime_brain": we["active_regime"],
                    "total_updates_count": we["updates_count"],
                    "all_regime_brains": we["all_regimes"],
                    "last_decomposition": ld,
                })
                if st.button("🔄 3脳SGD進化重みを初期値にリセット", key="dd_reset_weights_btn", use_container_width=True):
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
                st.markdown("##### 価格帯別出来高（仮想板・しこり玉マップ）")
                _render_echarts({"backgroundColor": "#0b1120", "tooltip": {"trigger": "axis"}, "grid": {"top": 10, "bottom": 20, "left": 6, "right": 14, "containLabel": True}, "xAxis": {"type": "value", "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.06)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9.5}}, "yAxis": {"type": "category", "data": vp["labels"], "axisLabel": {"color": "#cbd5e1", "fontSize": 9.5}}, "series": [{"name": "出来高(M)", "type": "bar", "data": vp["vols"], "itemStyle": {"color": "#a855f7"}}]}, height=230)

        with t4:
            _render_echarts({"backgroundColor": "#0b1120", "series": [{"type": "gauge", "startAngle": 180, "endAngle": 0, "min": 0, "max": 100, "splitNumber": 5, "center": ["50%", "74%"], "radius": "112%", "axisLine": {"lineStyle": {"width": 16, "color": [[0.2, "#dc2626"], [0.4, "#f97316"], [0.6, "#38bdf8"], [0.8, "#10b981"], [1.0, "#059669"]]}}, "pointer": {"icon": "path://M12.8,0.7l12,40.1H0.7L12.8,0.7z", "length": "52%", "width": 10, "offsetCenter": [0, "-12%"], "itemStyle": {"color": "#f8fafc", "shadowBlur": 8, "shadowColor": "rgba(56,189,248,0.8)"}}, "anchor": {"show": True, "showAbove": True, "size": 14, "itemStyle": {"color": "#38bdf8", "borderWidth": 2, "borderColor": "#fff"}}, "axisTick": {"length": 6, "lineStyle": {"color": "auto", "width": 1.5}}, "splitLine": {"length": 12, "lineStyle": {"color": "auto", "width": 2.5}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9.5, "distance": -36}, "title": {"offsetCenter": [0, "18%"], "fontSize": 10.5, "color": "#7dd3fc", "fontWeight": "bold"}, "detail": {"fontSize": 26, "fontWeight": "bold", "offsetCenter": [0, "-3%"], "valueAnimation": True, "color": "#ffffff", "formatter": "{value}"}, "data": [{"value": comp_score, "name": meter_lbl}]}]}, height=225)

            memo_nonce = st.session_state.get("dd_memo_nonce", 0)
            top_m = macro_sens[0] if macro_sens else {"label": "市場指数", "corr": 0.0, "beta": 1.0}
            m_txt, m_src = _generate_detailed_memo_cached(
                fc, corp_name, _fmt_cur(curr_px, is_jp),
                _fmt_cur(traj["est_open_px"], is_jp), _fmt_cur(traj["est_close_px"], is_jp),
                _fmt_cur(traj["bull_trig"], is_jp), _fmt_cur(traj["bull_target"], is_jp),
                _fmt_cur(traj["bear_trig"], is_jp), _fmt_cur(traj["bear_target"], is_jp),
                traj["dip_time"], traj["peak_time"], vp["overhead_pct"],
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
                st.markdown('<div class="dd-quant-box"><b>ガバナンス・不祥事監査: クリーン</b><br>直近ニュースにおいて不祥事・不正・訴訟などの特異リスクシグナルは検知されていません。</div>', unsafe_allow_html=True)

            if news_res["items"]:
                n_html = "".join([f'<div style="margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid rgba(148,163,184,0.12);"><span style="color:{"#fde047" if it["trust"]=="S" else ("#38bdf8" if it["trust"]=="A" else "#64748b")};font-weight:800;font-size:10px;border:1px solid;padding:0 4px;border-radius:3px;margin-right:4px;">信頼度{it["trust"]}/{it["lang"]}</span><span style="color:{"#10b981" if it["sent"]=="POS" else ("#ef4444" if it["sent"]=="NEG" else "#94a3b8")};font-weight:800;font-size:10px;margin-right:4px;">[{it["sent"]}]</span><a href="{html.escape(it["link"])}" target="_blank" style="color:#e2e8f0;text-decoration:none;font-weight:600;">{html.escape(it["title"])}</a> <span style="color:#64748b;font-size:10px;">({html.escape(it["source"] or "Wire")} / {html.escape(it["pub"])})</span></div>' for it in news_res["items"]])
                st.markdown(f'<div class="dd-dark-box"><b>GLOBAL INTELLIGENCE FEED // 日英高信頼ニュース（一次報道 {news_res["tier1_cnt"]}件）</b><br><br>{n_html}</div>', unsafe_allow_html=True)

        dd_result = {
            "full_code": fc,
            "style": in_style,
            "comp_score": int(comp_score),
            "meter_lbl": str(meter_lbl),
            "mkt_regime": mkt_regime,
            "est_open_gap_pct": float(traj["est_open_gap_pct"]),
            "est_close_px": float(traj["est_close_px"]),
            "est_close_chg": float(traj["est_close_chg"]),
            "bull_trig": float(traj["bull_trig"]),
            "bull_target": float(traj["bull_target"]),
            "bear_trig": float(traj["bear_trig"]),
            "bear_target": float(traj["bear_target"]),
            "dip_time": str(traj["dip_time"]),
            "peak_time": str(traj["peak_time"]),
            "rvol": traj["rvol"],
            "gap_fill": traj["gap_fill"],
            "gap_open15": traj["gap_open15"],
            "cvd_div": traj["cvd_div"],
            "gamma_pin": float(gamma_pin),
            "orb_high": traj["orb_high"],
            "orb_low": traj["orb_low"],
            "vol_spikes_cnt": len(traj["vol_spikes"]),
            "whale_anom": whale_anom,
            "gov_risks_cnt": len(gov_risks),
            "overhead_pct": float(vp["overhead_pct"]),
            "res_px": float(vp["res_px"]),
            "sup_px": float(vp["sup_px"]),
            "verify": traj["verify"],
            "knn_match": traj["knn_match"],
            "invalidation_alert": traj["invalidation_alert"],
            "weights_evolution": {
                "active_regime": traj["weights_evolution"]["active_regime"],
                "updates_count": traj["weights_evolution"]["updates_count"],
                "regime_updates_count": traj["weights_evolution"]["regime_updates_count"],
                "last_decomp": traj["weights_evolution"]["last_decomp"],
            },
            "verdict": f"{meter_lbl} (スコア{comp_score} / 想定大引け{traj['est_close_chg']:+.2f}% / {mkt_regime['label']})",
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
