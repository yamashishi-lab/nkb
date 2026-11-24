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
# 1. DEEP DIVE v18.0 専用CSS（プロ向けクオンツ端末・ガラス調・高視認性設計）
# =========================================================================
def _inject_dd_css():
    css = """
    [data-stale="true"] { opacity: 1 !important; transition: none !important; }
    .dd-cmd-header {
        background: linear-gradient(135deg, rgba(11, 17, 32, 0.88) 0%, rgba(7, 11, 20, 0.94) 100%);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(56, 189, 248, 0.22);
        border-radius: 10px;
        padding: 7px 12px;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
    }
    .dd-cmd-title {
        font-family: 'JetBrains Mono', monospace;
        font-size: 13.5px;
        font-weight: 800;
        letter-spacing: 0.04em;
        background: linear-gradient(90deg, #f8fafc 0%, #7dd3fc 55%, #c084fc 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        line-height: 1.2;
    }
    .dd-cmd-sub {
        font-size: 9.5px;
        color: #64748b;
        margin-top: 1px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .dd-macro-strip {
        display: flex; flex-wrap: nowrap; overflow-x: auto; gap: 5px;
        padding: 2px 0 4px 0; margin-bottom: 4px; scrollbar-width: none;
    }
    .dd-macro-strip::-webkit-scrollbar { display: none; }
    .dd-macro-chip {
        flex-shrink: 0;
        background: rgba(15, 23, 42, 0.72);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(148, 163, 184, 0.14);
        border-radius: 6px;
        padding: 2.5px 7px;
        font-family: 'JetBrains Mono', monospace;
        font-variant-numeric: tabular-nums;
        font-size: 10px;
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }
    .dd-status-strip {
        display: flex; flex-wrap: nowrap; overflow-x: auto; gap: 5px;
        padding: 1px 0 5px 0; scrollbar-width: none;
    }
    .dd-status-strip::-webkit-scrollbar { display: none; }
    .dd-st-pill {
        flex-shrink: 0; font-size: 10px; font-weight: 700;
        padding: 2.5px 8px; border-radius: 99px; border: 1px solid;
        display: inline-flex; align-items: center; gap: 4px;
        font-variant-numeric: tabular-nums;
    }
    .dd-hero-card {
        background: linear-gradient(145deg, rgba(15, 23, 42, 0.78) 0%, rgba(7, 11, 20, 0.90) 100%);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(148, 163, 184, 0.16);
        border-left: 4px solid #38bdf8;
        border-radius: 12px;
        padding: 11px 13px;
        margin: 4px 0 10px 0;
    }
    .dd-mtf-bar {
        display: flex; align-items: center; justify-content: space-between;
        flex-wrap: nowrap; overflow-x: auto; gap: 5px;
        background: rgba(11, 17, 32, 0.78);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(56, 189, 248, 0.22);
        border-radius: 8px; padding: 4px 8px; margin-bottom: 6px; scrollbar-width: none;
    }
    .dd-mtf-bar::-webkit-scrollbar { display: none; }
    .dd-mtf-pills { display: inline-flex; align-items: center; gap: 4px; flex-shrink: 0; }
    .dd-mtf-led {
        font-family: 'JetBrains Mono', monospace;
        font-variant-numeric: tabular-nums;
        font-size: 9.8px; font-weight: 800;
        padding: 1.5px 6px; border-radius: 5px; border: 1px solid;
        display: inline-flex; align-items: center; gap: 3px; flex-shrink: 0;
    }
    .dd-mtf-sum {
        font-family: 'JetBrains Mono', monospace; font-size: 9.8px; font-weight: 800;
        padding: 2px 7px; border-radius: 99px; background: rgba(15, 23, 42, 0.9);
        border: 1px solid rgba(148, 163, 184, 0.22); flex-shrink: 0;
    }
    .dd-inst-ribbon {
        display: flex; flex-wrap: nowrap; overflow-x: auto; gap: 6px;
        padding: 2px 0 6px 0; margin-bottom: 6px; scrollbar-width: none;
    }
    .dd-inst-ribbon::-webkit-scrollbar { display: none; }
    .dd-inst-pill-card {
        flex: 1 0 124px;
        background: rgba(15, 23, 42, 0.72);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(148, 163, 184, 0.14);
        border-radius: 8px;
        padding: 5px 8px;
        text-align: left;
    }
    .dd-ladder-wrap {
        background: rgba(7, 11, 20, 0.85); border: 1px solid rgba(148, 163, 184, 0.16);
        border-radius: 8px; padding: 7px 9px;
        font-family: 'JetBrains Mono', monospace; font-variant-numeric: tabular-nums;
    }
    .dd-lad-row {
        display: flex; align-items: center; justify-content: space-between; gap: 8px;
        padding: 3.5px 6px; border-radius: 5px; font-size: 10.5px; margin-bottom: 3px;
        background: rgba(15, 23, 42, 0.75);
    }
    .dd-lad-now {
        display: flex; align-items: center; justify-content: space-between;
        padding: 5px 8px; margin: 5px 0; border-radius: 6px;
        background: linear-gradient(90deg, rgba(56, 189, 248, 0.18) 0%, rgba(15, 23, 42, 0.92) 100%);
        border: 1px solid rgba(56, 189, 248, 0.5); font-size: 11px; font-weight: 800; color: #ffffff;
    }
    .dd-lad-bar-bg {
        width: 54px; height: 5px; background: rgba(148, 163, 184, 0.18);
        border-radius: 99px; overflow: hidden; flex-shrink: 0;
    }
    .dd-breaking-ticker {
        display: flex; align-items: center; gap: 8px;
        background: linear-gradient(90deg, rgba(239, 68, 68, 0.16) 0%, rgba(15, 23, 42, 0.90) 100%);
        border: 1px solid rgba(239, 68, 68, 0.42); border-left: 3.5px solid #ef4444;
        border-radius: 7px; padding: 4px 10px; margin-bottom: 6px;
        font-size: 10.8px; color: #fecaca; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .dd-breaking-ticker.bull {
        background: linear-gradient(90deg, rgba(16, 185, 129, 0.16) 0%, rgba(15, 23, 42, 0.90) 100%);
        border-color: rgba(16, 185, 129, 0.42); border-left-color: #10b981; color: #d1fae5;
    }
    .dd-winrate-bar {
        display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px;
        background: rgba(7, 11, 20, 0.65); border: 1px solid rgba(148, 163, 184, 0.14);
        border-radius: 8px; padding: 7px 6px; margin-top: 8px; text-align: center;
    }
    @media (max-width: 640px) { .dd-winrate-bar { grid-template-columns: repeat(2, 1fr); } }
    .dd-metric-val {
        font-family: 'JetBrains Mono', monospace;
        font-variant-numeric: tabular-nums;
        font-size: 13px; font-weight: 800; color: #38bdf8; margin-top: 2px;
    }
    .dd-metric-lbl { font-size: 9.5px; color: #64748b; font-weight: 700; letter-spacing: 0.02em; }
    .dd-range-track { width: 100%; height: 5px; background: rgba(148, 163, 184, 0.18); border-radius: 99px; position: relative; margin: 5px 0 3px 0; }
    .dd-range-dot { width: 10px; height: 10px; background: #38bdf8; border: 2px solid #fff; border-radius: 50%; position: absolute; top: -2.5px; transform: translateX(-50%); box-shadow: 0 0 8px rgba(56, 189, 248, 0.9); }
    .dd-sc-stack {
        display: grid;
        grid-template-columns: 1fr;
        gap: 8px;
        margin: 8px 0 12px 0;
    }
    @media (min-width: 768px) {
        .dd-sc-stack { grid-template-columns: repeat(3, 1fr); }
    }
    .dd-sc-card {
        background: linear-gradient(145deg, rgba(15, 23, 42, 0.78) 0%, rgba(7, 11, 20, 0.92) 100%);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(148, 163, 184, 0.16);
        border-radius: 10px;
        padding: 10px 12px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .dd-sc-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
    .dd-sc-price {
        font-family: 'JetBrains Mono', monospace;
        font-variant-numeric: tabular-nums;
        font-size: 16px; font-weight: 800; color: #f8fafc; line-height: 1.15;
    }
    .dd-sc-pct {
        font-family: 'JetBrains Mono', monospace;
        font-variant-numeric: tabular-nums;
        font-size: 10.8px; font-weight: 700; margin-top: 2px;
    }
    .dd-sc-bar-bg { width: 100%; height: 4px; background: rgba(148, 163, 184, 0.14); border-radius: 99px; margin-top: 8px; overflow: hidden; }
    .dd-sc-bar-fill { height: 100%; border-radius: 99px; transition: width 0.3s ease; }
    .dd-3way-strip {
        display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;
        background: rgba(15, 23, 42, 0.78);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(56, 189, 248, 0.28); border-radius: 8px;
        padding: 5px 10px; margin: 5px 0 6px 0;
        font-family: 'JetBrains Mono', monospace; font-variant-numeric: tabular-nums; font-size: 10.8px;
    }
    .dd-legend-panel {
        background: rgba(11, 17, 32, 0.74);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(148, 163, 184, 0.16);
        border-radius: 9px; padding: 7px 10px; margin: 4px 0 8px 0;
    }
    .dd-trans-banner {
        font-size: 11px; font-weight: 700; line-height: 1.45;
        padding: 5px 9px; border-radius: 6px; margin-bottom: 6px;
        border-left: 3.5px solid #38bdf8; background: rgba(56, 189, 248, 0.09); color: #e0f2fe;
    }
    .dd-trans-banner.exp-up {
        border-left-color: #10b981; background: rgba(16, 185, 129, 0.13); color: #d1fae5;
    }
    .dd-trans-banner.exp-down {
        border-left-color: #ef4444; background: rgba(239, 68, 68, 0.13); color: #fecaca;
    }
    .dd-chip-ribbon {
        display: flex; flex-wrap: nowrap; overflow-x: auto; gap: 6px;
        padding: 1px 0; scrollbar-width: none;
    }
    .dd-chip-ribbon::-webkit-scrollbar { display: none; }
    .dd-leg-pill {
        flex-shrink: 0;
        display: inline-flex; align-items: center; gap: 5px;
        background: rgba(15, 23, 42, 0.85);
        border: 1px solid rgba(148, 163, 184, 0.16);
        border-radius: 99px;
        padding: 2px 8px;
        font-size: 9.8px; font-weight: 700; color: #cbd5e1;
    }
    .dd-legend-grid {
        display: grid; grid-template-columns: repeat(3, 1fr); gap: 5px;
    }
    @media (max-width: 640px) { .dd-legend-grid { grid-template-columns: repeat(2, 1fr); } }
    .dd-leg-card {
        background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(148, 163, 184, 0.14);
        border-radius: 6px; padding: 5px 7px; display: flex; flex-direction: column; gap: 2px;
    }
    .dd-leg-head {
        display: flex; align-items: center; gap: 6px; font-size: 10px; font-weight: 800; color: #f8fafc;
    }
    .dd-leg-desc {
        font-size: 9.3px; color: #94a3b8; line-height: 1.3;
    }
    .dd-prob-meter {
        background: rgba(15, 23, 42, 0.74);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(56, 189, 248, 0.20);
        border-radius: 10px; padding: 8px 11px; margin: 6px 0 8px 0;
    }
    .dd-prob-stack {
        display: flex; width: 100%; height: 9px; border-radius: 99px;
        overflow: hidden; background: rgba(7, 11, 20, 0.92); margin: 6px 0 7px 0;
        border: 1px solid rgba(148, 163, 184, 0.18);
    }
    .dd-prob-legend {
        display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px;
        font-family: 'JetBrains Mono', monospace; font-variant-numeric: tabular-nums;
        font-size: 9.8px; text-align: center;
    }
    @media (max-width: 640px) { .dd-prob-legend { grid-template-columns: repeat(2, 1fr); } }
    .dd-dow-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 5px; margin-top: 6px; }
    .dd-dow-cell {
        background: rgba(15, 23, 42, 0.76); border: 1px solid rgba(148, 163, 184, 0.15);
        border-radius: 7px; padding: 6px 4px; text-align: center;
        font-variant-numeric: tabular-nums;
    }
    .dd-dark-box {
        background: rgba(15, 23, 42, 0.74);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(148, 163, 184, 0.15);
        padding: 11px 13px; border-radius: 10px; margin-bottom: 10px;
        font-size: 11.8px; line-height: 1.65; color: #cbd5e1;
    }
    .dd-warn-box {
        background: rgba(239, 68, 68, 0.10); border: 1px solid rgba(239, 68, 68, 0.36);
        border-left: 3.5px solid #ef4444; padding: 9px 12px; border-radius: 9px;
        margin-bottom: 8px; font-size: 11.8px; line-height: 1.6; color: #fecaca;
    }
    .dd-quant-box {
        background: rgba(16, 185, 129, 0.09); border: 1px solid rgba(16, 185, 129, 0.32);
        border-left: 3.5px solid #10b981; padding: 9px 12px; border-radius: 9px;
        margin-bottom: 8px; font-size: 11.8px; line-height: 1.6; color: #d1fae5;
    }
    .dd-sync-warn {
        background: rgba(245, 158, 11, 0.10); border: 1px solid rgba(245, 158, 11, 0.38);
        border-left: 3.5px solid #f59e0b; padding: 9px 12px; border-radius: 9px;
        margin-bottom: 8px; font-size: 11.8px; line-height: 1.6; color: #fef3c7;
    }
    .dd-guide-box {
        background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.25);
        border-left: 3px solid #38bdf8; padding: 10px 12px; border-radius: 8px;
        font-size: 11.3px; line-height: 1.65; color: #e0f2fe;
    }
    .dd-memo-box {
        background: linear-gradient(180deg, rgba(15, 23, 42, 0.88) 0%, rgba(7, 11, 20, 0.95) 100%);
        border: 1px solid rgba(168, 85, 247, 0.38); border-left: 4px solid #a855f7;
        padding: 13px 15px; border-radius: 10px; margin-bottom: 10px;
        font-size: 12px; line-height: 1.78; color: #f1f5f9;
    }
    .dd-factor-row {
        display: flex; justify-content: space-between; align-items: center; gap: 8px;
        padding: 5px 0; border-bottom: 1px solid rgba(148, 163, 184, 0.12);
        font-size: 11.3px; font-variant-numeric: tabular-nums;
    }
    .dd-factor-row:last-child { border-bottom: none; padding-top: 7px; font-weight: 800; }
    .dd-ev-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-top: 8px; }
    .dd-ev-cell {
        background: rgba(7, 11, 20, 0.78); border: 1px solid rgba(56, 189, 248, 0.20);
        border-radius: 7px; padding: 7px 5px; text-align: center;
        font-variant-numeric: tabular-nums;
    }
    .dd-val-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; margin: 8px 0; }
    @media (max-width: 640px) { .dd-val-grid { grid-template-columns: 1fr; } }
    .dd-val-card {
        background: rgba(15, 23, 42, 0.76); border: 1px solid rgba(148, 163, 184, 0.15);
        border-radius: 8px; padding: 7px 9px; font-variant-numeric: tabular-nums;
    }
    .dd-val-track { width: 100%; height: 5px; background: rgba(148, 163, 184, 0.16); border-radius: 99px; position: relative; margin-top: 5px; }
    .dd-val-fill { height: 100%; border-radius: 99px; }
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


def _is_valid_premarket_lock_window(is_jp: bool, target_date_str: str) -> bool:
    """寄り前2時間以内（東証 07:00〜09:00 JST / 米株 07:30〜09:30 ET）のみ公式朝ロックとして認定"""
    m_now = _get_market_now(is_jp)
    if m_now.strftime("%Y-%m-%d") != target_date_str:
        return False
    mins_now = m_now.hour * 60 + m_now.minute
    if is_jp:
        return (7 * 60) <= mins_now < (9 * 60)
    return (7 * 60 + 30) <= mins_now < (9 * 60 + 30)


def _convert_5m_index_to_market_tz(df_intraday: pd.DataFrame, is_jp: bool) -> pd.DatetimeIndex:
    """分足インデックスを必ず市場タイムゾーン（Asia/Tokyo / America/New_York）へ変換"""
    idx = pd.to_datetime(df_intraday.index)
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
    """クラスタ別＋特徴量標準化＋L2正則化＋ベースライン残差分離型SGD"""
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
        if snap.get("locked_premarket") is not True:
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

        base_shape_pct = float(snap.get("slot_mean_end_pct", 0.0) or 0.0)
        act_intra_pct = ((act_close - act_open) / max(act_open, 1e-4)) * 100.0 - base_shape_pct
        pred_intra_pct = ((pred_close - pred_open) / max(pred_open, 1e-4)) * 100.0 - base_shape_pct
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
# 3. ヘルパー ＆ 描画コンポーネント（衝突回避MarkLine / 高DPI ECharts / スリム凡例）
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


def _calc_two_barrier_tp_prob(curr_px: float, tp_px: float, sl_px: float, is_long: bool, rem_sigma_pct: float, rem_drift_pct: float = 0.0) -> float:
    """二壁問題（SLにタッチする前にTPへ先に到達する条件付き確率・片壁確率上限キャップ付）"""
    if curr_px <= 0 or tp_px <= 0 or sl_px <= 0:
        return 0.0
    if is_long:
        if curr_px <= sl_px:
            return 0.0
        if curr_px >= tp_px:
            return 99.0
        d_tp = math.log(tp_px / curr_px)
        d_sl = math.log(curr_px / sl_px)
        mu = rem_drift_pct
    else:
        if curr_px >= sl_px:
            return 0.0
        if curr_px <= tp_px:
            return 99.0
        d_tp = math.log(curr_px / tp_px)
        d_sl = math.log(sl_px / curr_px)
        mu = -rem_drift_pct

    sig2 = max(rem_sigma_pct ** 2, 1e-6)
    if abs(mu) < 1e-5:
        p_hit_tp_first = d_sl / max(d_tp + d_sl, 1e-6)
    else:
        k_drift = (2.0 * mu) / sig2
        num = math.exp(np.clip(k_drift * d_sl, -40.0, 40.0)) - 1.0
        den = math.exp(np.clip(k_drift * (d_tp + d_sl), -40.0, 40.0)) - 1.0
        p_hit_tp_first = num / den if abs(den) > 1e-9 else (d_sl / max(d_tp + d_sl, 1e-6))

    p_reach_any = _calc_first_passage_prob(curr_px, tp_px, rem_sigma_pct, rem_drift_pct) / 100.0
    p_sl_first_reach = _calc_first_passage_prob(curr_px, sl_px, rem_sigma_pct, rem_drift_pct) / 100.0
    p_either = min(1.0, p_reach_any + p_sl_first_reach * (1.0 - p_reach_any))
    raw_joint = min(p_hit_tp_first * p_either, p_reach_any)
    joint_prob = float(np.clip(raw_joint * 100.0, 1.0, 99.0))
    return round(joint_prob, 1)


def _declutter_marklines(ml_list: list, curr_px: float, min_gap_pct: float = 0.38) -> list:
    """水平MarkLineの密集ラベル衝突を自動検出・統合＆4隅交互配置するヘルパー"""
    if not ml_list:
        return []
    horiz = []
    others = []
    for item in ml_list:
        if isinstance(item, dict) and "yAxis" in item and item["yAxis"] is not None:
            try:
                y_val = float(item["yAxis"])
                if y_val > 0:
                    horiz.append((y_val, json.loads(json.dumps(item))))
                    continue
            except Exception:
                pass
        others.append(item)

    if not horiz:
        return others

    horiz.sort(key=lambda x: x[0])
    ref_base = curr_px if curr_px > 0 else float(np.mean([h[0] for h in horiz]))
    ref_base = max(ref_base, 1e-4)

    # 0.12%未満でほぼ同一価格のラインは統合（例: "PDH / ORB高"）
    merged = []
    for y_val, obj in horiz:
        if merged:
            prev_y, prev_obj = merged[-1]
            diff_pct = abs(y_val - prev_y) / ref_base * 100.0
            if diff_pct < 0.12:
                lbl_prev = prev_obj.get("label", {}) if isinstance(prev_obj.get("label"), dict) else {}
                lbl_cur = obj.get("label", {}) if isinstance(obj.get("label"), dict) else {}
                t_prev = str(lbl_prev.get("formatter", "")).strip()
                t_cur = str(lbl_cur.get("formatter", "")).strip()
                if t_cur and t_cur not in t_prev:
                    short_cur = t_cur.split(" ")[0]
                    lbl_prev["formatter"] = f"{t_prev} / {short_cur}" if t_prev else t_cur
                    prev_obj["label"] = lbl_prev
                continue
        merged.append((y_val, obj))

    # 0.38%未満で近接しているラインは4ポジションへ交互振り分け
    pos_cycle = ["insideStartTop", "insideEndTop", "insideStartBottom", "insideEndBottom"]
    pos_idx = 0
    last_placed_y = None
    out_horiz = []
    for y_val, obj in merged:
        lbl = obj.get("label") if isinstance(obj.get("label"), dict) else {}
        if last_placed_y is not None:
            gap_pct = abs(y_val - last_placed_y) / ref_base * 100.0
            if gap_pct < min_gap_pct:
                pos_idx = (pos_idx + 1) % len(pos_cycle)
                lbl["position"] = pos_cycle[pos_idx]
            else:
                cur_p = lbl.get("position", "insideStartTop")
                pos_idx = pos_cycle.index(cur_p) if cur_p in pos_cycle else 0
        else:
            cur_p = lbl.get("position", "insideStartTop")
            pos_idx = pos_cycle.index(cur_p) if cur_p in pos_cycle else 0
        obj["label"] = lbl
        out_horiz.append(obj)
        last_placed_y = y_val

    return others + out_horiz


def _render_echarts(
    option_dict: dict,
    height: int = 300,
    use_hud_tooltip: bool = False,
    is_jp: bool = False,
    enable_fullscreen: bool = False,
    is_dual_grid: bool = False,
    chart_key: str = "dd_chart_default",
):
    opt_json = json.dumps(option_dict, ensure_ascii=False)
    safe_ck = re.sub(r"[^A-Za-z0-9_\-]", "_", str(chart_key or "dd_chart_default"))

    hud_js = f"""
    if ({'true' if use_hud_tooltip else 'false'}) {{
        opt.tooltip = {{
            trigger: 'axis',
            confine: true,
            backgroundColor: 'rgba(7, 11, 20, 0.90)',
            borderColor: 'rgba(56, 189, 248, 0.38)',
            borderWidth: 1,
            padding: [4, 8],
            extraCssText: 'pointer-events: none; white-space: normal; max-width: 84%; line-height: 1.35; backdrop-filter: blur(6px);',
            textStyle: {{ color: '#f8fafc', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }},
            position: function() {{ return [6, 26]; }},
            axisPointer: {{
                type: 'cross',
                lineStyle: {{ color: 'rgba(56, 189, 248, 0.5)', type: 'dashed', width: 1 }},
                crossStyle: {{ color: 'rgba(56, 189, 248, 0.32)' }},
                label: {{ backgroundColor: '#0f172a', borderColor: '#38bdf8', borderWidth: 1, fontSize: 9 }}
            }},
            formatter: function(params) {{
                if (!params || !params.length) return '';
                var tm = params[0].axisValue;
                var parts = ['<span style="color:#7dd3fc;font-weight:800;">' + tm + '</span>'];
                var shortMap = {{
                    '当日実測':'実測', 'ライブ修正':'ライブ', '朝ロック':'ロック', '朝ロック(無効化済)':'旧想定',
                    'VWAP':'VWAP', '類似実測(Top-1)':'類似1位', '上昇分岐':'▲上', '横ばい分岐':'▶横', '下落分岐':'▼下',
                    '9EMA':'9EMA', '20EMA':'20EMA'
                }};
                for (var i = 0; i < params.length; i++) {{
                    var p = params[i];
                    if (p.seriesName === '1分足' && Array.isArray(p.value) && p.value.length >= 5) {{
                        var o = Number(p.value[1]), c = Number(p.value[2]), l = Number(p.value[3]), h = Number(p.value[4]);
                        if (!isNaN(o)) {{
                            var fmt = function(x) {{ return {'true' if is_jp else 'false'} ? Math.round(x).toLocaleString() : x.toFixed(2); }};
                            parts.push('始:<b>' + fmt(o) + '</b> 高:<b>' + fmt(h) + '</b> 安:<b>' + fmt(l) + '</b> 終:<b>' + fmt(c) + '</b>');
                        }}
                    }} else if (shortMap[p.seriesName] && p.value !== null && p.value !== undefined) {{
                        var v = Number(p.value);
                        var vs = {'true' if is_jp else 'false'} ? Math.round(v).toLocaleString() + '円' : '$' + v.toFixed(2);
                        parts.push('<span style="color:' + p.color + ';">●</span>' + shortMap[p.seriesName] + ':<b>' + vs + '</b>');
                    }} else if (p.seriesName === '疑似CVD' && p.value !== null && p.value !== undefined) {{
                        var cv = Number(p.value);
                        var cvStr = Math.abs(cv) >= 10000 ? (cv / 10000).toFixed(1) + '万' : Math.round(cv).toLocaleString();
                        parts.push('<span style="color:#22d3ee;">●</span>CVD:<b>' + (cv >= 0 ? '+' : '') + cvStr + '</b>');
                    }}
                }}
                return parts.join(' ');
            }}
        }};
    }}
    """

    ctrl_bar_html = (
        '<div id="ctrl-bar">'
        '<span id="fs-hint">FS中（60s自動更新で解除時は上部トグルOFF）</span>'
        '<button id="rst-btn" onclick="resetZoom()" title="拡大ズームを初期状態へリセット">↺</button>'
        '<button id="fs-btn" onclick="toggleFS()" title="スマホ横向きフル大画面">⛶ 横拡大</button>'
        '</div>'
    ) if enable_fullscreen else ""

    is_dual_js = "true" if is_dual_grid else "false"
    enable_fs_js = "true" if enable_fullscreen else "false"

    html_code = f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
      html,body{{width:100%;height:100%;margin:0;padding:0;background:#070b14;overflow:hidden;}}
      #wrap{{position:relative;width:100%;height:100%;background:#070b14;}}
      #c{{width:100%;height:100%;}}
      #c.force-landscape{{
        position:fixed;
        top:0;
        left:100vw;
        transform:rotate(90deg);
        transform-origin:top left;
      }}
      #ctrl-bar{{
        position:absolute;top:4px;right:6px;z-index:99;
        display:inline-flex;align-items:center;gap:4px;
      }}
      #ctrl-bar.bar-rotated{{
        position:fixed;
        top:auto;
        bottom:22px;
        right:4px;
        transform:rotate(90deg);
        transform-origin:center center;
      }}
      #fs-hint{{
        display:none;
        background:rgba(15,23,42,0.86);color:#fde047;
        border:1px solid rgba(250,204,21,0.4);border-radius:5px;
        padding:2px 6px;font-size:9px;font-weight:700;
        font-family:'JetBrains Mono',sans-serif;white-space:nowrap;
      }}
      #wrap.is-fs #fs-hint{{display:inline-block;}}
      #rst-btn, #fs-btn{{
        background:rgba(15,23,42,0.88);color:#7dd3fc;
        border:1px solid rgba(56,189,248,0.42);border-radius:6px;
        padding:2px 7px;font-size:10px;font-weight:700;cursor:pointer;
        font-family:'JetBrains Mono',sans-serif;
      }}
      #rst-btn{{padding:2px 6px;color:#cbd5e1;}}
      #rst-btn:active, #fs-btn:active{{background:rgba(56,189,248,0.25);}}
    </style>
    </head><body>
      <div id="wrap">
        {ctrl_bar_html}
        <div id="c"></div>
      </div>
      <script>
        var CHART_KEY = {json.dumps(safe_ck)};
        var STORAGE_KEY = 'dd_dz_' + CHART_KEY;
        var IS_DUAL = {is_dual_js};
        var ENABLE_FS = {enable_fs_js};

        var el = document.getElementById('c');
        var wrap = document.getElementById('wrap');
        var btn = document.getElementById('fs-btn');
        var ctrlBar = document.getElementById('ctrl-bar');

        var dpr = Math.min(window.devicePixelRatio || 2, 3);
        var chart = echarts.init(el, 'dark', {{ renderer: 'canvas', devicePixelRatio: dpr }});
        var opt = {opt_json};

        opt.animationDuration = 280;
        opt.animationDurationUpdate = 220;
        opt.animationEasing = 'cubicOut';

        if (opt.legend) {{
          opt.legend.type = 'scroll';
          opt.legend.pageIconColor = '#7dd3fc';
          opt.legend.pageIconInactiveColor = '#475569';
          opt.legend.pageTextStyle = {{ color: '#94a3b8', fontSize: 9 }};
        }}

        {hud_js}

        var savedZoom = null;
        try {{
          var rawZ = sessionStorage.getItem(STORAGE_KEY);
          if (rawZ) {{
            var parsedZ = JSON.parse(rawZ);
            if (parsedZ && typeof parsedZ.start === 'number' && typeof parsedZ.end === 'number') {{
              savedZoom = parsedZ;
            }}
          }}
        }} catch(e) {{}}

        var origGridNormal = opt.grid ? JSON.parse(JSON.stringify(opt.grid)) : null;

        if (opt.dataZoom && Array.isArray(opt.dataZoom) && opt.dataZoom.length > 0) {{
          var xIdxTarget = IS_DUAL ? [0, 1] : 0;
          var zStart = savedZoom ? savedZoom.start : 0;
          var zEnd = savedZoom ? savedZoom.end : 100;
          opt.dataZoom = [
            {{
              type: 'inside',
              xAxisIndex: xIdxTarget,
              filterMode: 'none',
              throttle: 16,
              start: zStart,
              end: zEnd
            }},
            {{
              type: 'slider',
              show: false,
              xAxisIndex: xIdxTarget,
              filterMode: 'none',
              throttle: 16,
              height: IS_DUAL ? 16 : 18,
              bottom: IS_DUAL ? 5 : 6,
              borderColor: 'rgba(56,189,248,0.35)',
              fillerColor: 'rgba(56,189,248,0.18)',
              textStyle: {{ color: '#94a3b8', fontSize: 9 }},
              start: zStart,
              end: zEnd
            }}
          ];
        }}

        chart.setOption(opt);

        chart.on('datazoom', function(params) {{
          try {{
            var curOpt = chart.getOption();
            if (curOpt && curOpt.dataZoom && curOpt.dataZoom.length > 0) {{
              var dz0 = curOpt.dataZoom[0];
              if (typeof dz0.start === 'number' && typeof dz0.end === 'number') {{
                sessionStorage.setItem(STORAGE_KEY, JSON.stringify({{ start: dz0.start, end: dz0.end }}));
              }}
            }}
          }} catch(e) {{}}
        }});

        function resetZoom() {{
          try {{ sessionStorage.removeItem(STORAGE_KEY); }} catch(e) {{}}
          chart.dispatchAction({{ type: 'dataZoom', start: 0, end: 100 }});
        }}

        var orientationLocked = false;

        function getCurZoomRange() {{
          try {{
            var curOpt = chart.getOption();
            if (curOpt && curOpt.dataZoom && curOpt.dataZoom.length > 0) {{
              return {{ start: curOpt.dataZoom[0].start || 0, end: curOpt.dataZoom[0].end || 100 }};
            }}
          }} catch(e) {{}}
          return {{ start: 0, end: 100 }};
        }}

        function applyLayout(isFS) {{
          if (!isFS) {{
            if (wrap) wrap.classList.remove('is-fs');
            el.classList.remove('force-landscape');
            if (ctrlBar) ctrlBar.classList.remove('bar-rotated');
            el.style.cssText = 'width:100%;height:100%;';
            var wN = wrap ? wrap.clientWidth : el.clientWidth;
            var hN = wrap ? wrap.clientHeight : el.clientHeight;
            if (wN > 0 && hN > 0) {{
              chart.resize({{ width: wN, height: hN }});
            }} else {{
              chart.resize();
            }}
            return;
          }}
          if (wrap) wrap.classList.add('is-fs');
          var w = window.innerWidth;
          var h = window.innerHeight;
          if (!orientationLocked && h > w) {{
            el.classList.add('force-landscape');
            if (ctrlBar) ctrlBar.classList.add('bar-rotated');
            el.style.width = h + 'px';
            el.style.height = w + 'px';
            chart.resize({{ width: h, height: w }});
          }} else {{
            el.classList.remove('force-landscape');
            if (ctrlBar) ctrlBar.classList.remove('bar-rotated');
            el.style.width = '100%';
            el.style.height = '100%';
            chart.resize({{ width: w, height: h }});
          }}
        }}

        function updateZoomMode(isFS) {{
          if (!opt.dataZoom) return;
          var zr = getCurZoomRange();
          var xIdxTarget = IS_DUAL ? [0, 1] : 0;
          var nextGrid = origGridNormal;
          if (isFS) {{
            if (IS_DUAL && Array.isArray(origGridNormal) && origGridNormal.length >= 2) {{
              nextGrid = [
                {{ top: 44, height: '55%', left: 6, right: origGridNormal[0].right, containLabel: false }},
                {{ top: '68%', height: '16%', left: 6, right: origGridNormal[1].right, containLabel: false }}
              ];
            }} else if (origGridNormal && !Array.isArray(origGridNormal)) {{
              nextGrid = Object.assign({{}}, origGridNormal, {{ bottom: 44, top: 52 }});
            }}
          }}
          chart.setOption({{
            grid: nextGrid,
            dataZoom: [
              {{ type: 'inside', xAxisIndex: xIdxTarget, filterMode: 'none', throttle: 16, start: zr.start, end: zr.end }},
              {{ type: 'slider', show: isFS, xAxisIndex: xIdxTarget, filterMode: 'none', throttle: 16, start: zr.start, end: zr.end }}
            ]
          }});
        }}

        function toggleFS() {{
          if (!ENABLE_FS) return;
          var doc = document;
          var isFS = !!(doc.fullscreenElement || doc.webkitFullscreenElement);
          if (!isFS) {{
            var req = wrap.requestFullscreen || wrap.webkitRequestFullscreen;
            if (req) {{
              Promise.resolve(req.call(wrap)).then(function() {{
                if (screen.orientation && screen.orientation.lock) {{
                  screen.orientation.lock('landscape').then(function() {{
                    orientationLocked = true;
                  }}).catch(function() {{
                    orientationLocked = false;
                  }});
                }} else {{
                  orientationLocked = false;
                }}
                setTimeout(function() {{ applyLayout(true); }}, 220);
              }}).catch(function(){{}});
            }}
          }} else {{
            var ex = doc.exitFullscreen || doc.webkitExitFullscreen;
            if (ex) ex.call(doc);
            if (screen.orientation && screen.orientation.unlock) {{
              try {{ screen.orientation.unlock(); }} catch(e) {{}}
            }}
            orientationLocked = false;
          }}
        }}

        function onFSChange() {{
          var isFS = !!(document.fullscreenElement || document.webkitFullscreenElement);
          if (!isFS) orientationLocked = false;
          if (btn) btn.textContent = isFS ? '✕ 戻す' : '⛶ 横拡大';
          updateZoomMode(isFS);
          if (!isFS) {{
            requestAnimationFrame(function() {{ applyLayout(false); }});
            setTimeout(function() {{ applyLayout(false); }}, 120);
            setTimeout(function() {{ applyLayout(false); }}, 350);
            setTimeout(function() {{ applyLayout(false); }}, 650);
          }} else {{
            requestAnimationFrame(function() {{ applyLayout(true); }});
            setTimeout(function() {{ applyLayout(true); }}, 180);
            setTimeout(function() {{ applyLayout(true); }}, 420);
          }}
        }}

        var resizeTimer = null;
        function scheduleResize() {{
          if (resizeTimer) clearTimeout(resizeTimer);
          resizeTimer = setTimeout(function() {{
            var isFS = !!(document.fullscreenElement || document.webkitFullscreenElement);
            applyLayout(isFS);
          }}, 80);
        }}

        window.addEventListener('resize', scheduleResize);
        if (typeof ResizeObserver !== 'undefined') {{
          new ResizeObserver(scheduleResize).observe(wrap || el);
        }}
        if (ENABLE_FS) {{
          document.addEventListener('fullscreenchange', onFSChange);
          document.addEventListener('webkitfullscreenchange', onFSChange);
          window.addEventListener('orientationchange', function() {{
            setTimeout(function() {{
              var isFS = !!(document.fullscreenElement || document.webkitFullscreenElement);
              applyLayout(isFS);
            }}, 240);
          }});
        }}
        setTimeout(scheduleResize, 90);
        setTimeout(scheduleResize, 320);
      </script>
    </body></html>
    """
    components.html(html_code, height=height + 2)


def _render_live_clock(sync_interval: int = 60, active: bool = True):
    dot_col = "#10b981" if active else "#f59e0b"
    status_lbl = "LIVE FEED" if active else "PAUSED"
    right_html = f'SILENT SYNC <span id="cd" class="cnt">{sync_interval}s</span>' if active else '<span style="color:#f59e0b;font-weight:700;">自動更新 停止中（拡大・精査保護）</span>'
    bar_border = "rgba(16,185,129,0.28)" if active else "rgba(245,158,11,0.38)"
    left_col = "#6ee7b7" if active else "#fde047"
    active_js = "true" if active else "false"
    html_code = f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <style>
      html,body{{width:100%;margin:0;padding:0;background:transparent;font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;}}
      .bar{{display:flex;justify-content:space-between;align-items:center;background:rgba(15,23,42,0.75);border:1px solid {bar_border};border-radius:7px;padding:3px 9px;font-size:10px;color:#e2e8f0;}}
      .dot{{width:6px;height:6px;background:{dot_col};border-radius:50%;display:inline-block;margin-right:5px;box-shadow:0 0 7px {dot_col};}}
      .left{{display:flex;align-items:center;color:{left_col};font-weight:700;}}
      .right{{color:#94a3b8;font-size:9.5px;}} .cnt{{color:#38bdf8;font-weight:700;}}
    </style></head><body>
    <div class="bar"><div class="left"><span class="dot"></span>{status_lbl} <span id="clk" style="margin-left:7px;color:#fff;">--:--:--</span> JST</div><div class="right">{right_html}</div></div>
    <script>
      var rem = {sync_interval};
      var active = {active_js};
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
    components.html(html_code, height=26)


def _build_spark_svg(prices: np.ndarray) -> str:
    if len(prices) < 2:
        return ""
    p_min, p_max = float(np.min(prices)), float(np.max(prices))
    span = max(p_max - p_min, 1e-4)
    w, h = 88.0, 24.0
    pts = [f"{round((i/max(len(prices)-1,1))*w,1)},{round(h-2.0-((float(p)-p_min)/span)*(h-4.0),1)}" for i, p in enumerate(prices)]
    col = "#10b981" if prices[-1] >= prices[0] else "#ef4444"
    return f'<svg width="88" height="24" viewBox="0 0 88 24" style="display:block;margin-left:auto;"><polyline fill="none" stroke="{col}" stroke-width="1.6" points="{" ".join(pts)}"/></svg>'


def _render_chart_legend_panel(
    traj: dict, chart_mode: str, opt_lines: list, short_3way: dict,
    exp_reg: dict, active_dip_time: str, active_peak_time: str,
    cur_vwap_now, curr_px: float, is_jp: bool, active_lab,
    is_1m_zoom: bool = False, zoom_1m_data: dict = None
):
    """常時表示1行ステータス翻訳バナー ＋ スリム1行カラーチップ帯 ＋ 詳細説明折りたたみ版"""
    exp_active = bool(exp_reg.get("active"))
    exp_dir = exp_reg.get("dir", "NONE")

    def _swatch_line(color: str, style: str = "solid", width: int = 2) -> str:
        return f'<span style="display:inline-block;width:14px;height:0;border-top:{width}px {style} {color};flex-shrink:0;"></span>'

    def _swatch_band(bg: str, border: str) -> str:
        return f'<span style="display:inline-block;width:14px;height:9px;background:{bg};border:1px solid {border};border-radius:2px;flex-shrink:0;"></span>'

    if is_1m_zoom and isinstance(zoom_1m_data, dict) and zoom_1m_data.get("valid"):
        e9_now = zoom_1m_data.get("last_ema9", curr_px)
        e20_now = zoom_1m_data.get("last_ema20", curr_px)
        if curr_px >= e9_now >= e20_now:
            banner_cls = "dd-trans-banner exp-up"
            banner_txt = "⚡ 1分足ズーム(直近90分)：パーフェクトオーダー上昇中（現在値 > 9EMA > 20EMA）→ 9EMA押し目買い優位"
        elif curr_px <= e9_now <= e20_now:
            banner_cls = "dd-trans-banner exp-down"
            banner_txt = "⚡ 1分足ズーム(直近90分)：パーフェクトオーダー下落中（現在値 < 9EMA < 20EMA）→ 9EMA戻り売り・撤退優位"
        else:
            banner_cls = "dd-trans-banner"
            banner_txt = "⚡ 1分足ズーム(直近90分)：9EMAと20EMAが交錯する揉み合い局面 → 下段CVDとVWAPの方向確定待ち"

        candle_sw = (
            '<span style="display:inline-flex;align-items:center;gap:2px;width:14px;flex-shrink:0;">'
            '<span style="display:inline-block;width:5px;height:9px;background:#10b981;border-radius:1px;"></span>'
            '<span style="display:inline-block;width:5px;height:9px;background:#ef4444;border-radius:1px;"></span>'
            '</span>'
        )
        tri_sw = (
            '<span style="display:inline-flex;flex-direction:column;gap:2px;width:14px;flex-shrink:0;">'
            '<span style="border-top:1.5px dashed #10b981;"></span>'
            '<span style="border-top:1.5px dotted #94a3b8;"></span>'
            '<span style="border-top:1.5px dashed #ef4444;"></span>'
            '</span>'
        )
        cvd_sw = '<span style="display:inline-block;width:14px;height:0;border-top:2px solid #22d3ee;flex-shrink:0;"></span>'
        cards = [
            (candle_sw, "1分足ローソク", "緑=陽線 / 赤=陰線（ヒゲ先端で反発・失速判定）"),
            (_swatch_line("#38bdf8", "solid", 2), "9EMA", "スキャルピングの勢い基準線（割れたら一旦利確）"),
            (_swatch_line("#c084fc", "solid", 2), "20EMA", "押し目買い・戻り売りの防波堤ライン"),
            (_swatch_line("#fbbf24", "dotted", 2), "当日VWAP", "機関の平均約定値（上なら買い優勢）"),
            (tri_sw, "10分先3分岐", "直近1分足ボラから算出した10分後ルート"),
            (cvd_sw, "下段 出来高&CVD", "陽線/陰線出来高バーと買い売り累積デルタ"),
        ]
        if "前日/当日高安（PDH/PDL/HOD/LOD）" in opt_lines:
            cards.append((_swatch_line("#34d399", "dashed", 1), "PDH/PDL/HOD/LOD", "前日・当日の高値安値（ブレイク基準）"))
    else:
        if exp_active and exp_dir == "UP":
            banner_cls = "dd-trans-banner exp-up"
            banner_txt = (
                "🚀 実測(白)が朝想定(紫)を大幅突破 → 急騰ブレイクモード中。"
                "紫線は無視し、VWAP(黄点線)や突破ライン付近の押し目追従を優先"
            )
        elif exp_active and exp_dir == "DOWN":
            banner_cls = "dd-trans-banner exp-down"
            banner_txt = (
                "🔻 実測(白)が朝想定(紫)を下抜け → 急落ブレイクモード中。"
                "紫線は無視し、VWAP(黄点線)での戻り売り・損切り徹底を優先"
            )
        elif traj.get("has_actual"):
            vw_note = ""
            if cur_vwap_now and cur_vwap_now > 0:
                vw_note = "VWAP(黄点線)上で買い優勢" if curr_px >= cur_vwap_now else "VWAP(黄点線)下で戻り待ち"
            else:
                vw_note = "VWAP(黄点線)の攻防に注目"
            banner_txt = (
                f"📊 実測(白)は朝想定レンジ内で推移中 → "
                f"押し目候補 {active_dip_time} 前後の反発と {vw_note}"
            )
            banner_cls = "dd-trans-banner"
        else:
            banner_cls = "dd-trans-banner"
            banner_txt = (
                f"🕒 寄り前待機モード → 想定始値 {_fmt_cur(traj['est_open_px'], is_jp)} からの"
                f"押し目候補 {active_dip_time}・高値想定 {active_peak_time} を事前チェック"
            )

        cards = []
        if traj.get("has_actual"):
            cards.append((_swatch_line("#ffffff", "solid", 2), "当日実測", "実際の株価の動き（主役）"))

        if chart_mode in ("🔴 ライブ修正", "⚡ 両方重ね"):
            cards.append((_swatch_line("#38bdf8", "solid", 2), "ライブ修正", "今の勢いを反映した最新着地予測"))

        if chart_mode in ("🔒 朝ロック検証", "⚡ 両方重ね"):
            if exp_active:
                cards.append((_swatch_line("rgba(148,163,184,0.55)", "dotted", 2), "朝ロック(無効化)", "想定外ブレイクで参考線へ降格"))
            else:
                lk_c = "#c084fc" if chart_mode == "⚡ 両方重ね" else "#38bdf8"
                lk_st = "dashed" if chart_mode == "⚡ 両方重ね" else "solid"
                cards.append((_swatch_line(lk_c, lk_st, 2), "朝ロック", "寄り前固定の当初想定（基準線）"))

        if "場中30分・3分岐点線（スコア比%）" in opt_lines and short_3way.get("active"):
            tri_sw = (
                '<span style="display:inline-flex;flex-direction:column;gap:2px;width:14px;flex-shrink:0;">'
                '<span style="border-top:1.5px dashed #10b981;"></span>'
                '<span style="border-top:1.5px dotted #94a3b8;"></span>'
                '<span style="border-top:1.5px dashed #ef4444;"></span>'
                '</span>'
            )
            cards.append((tri_sw, "短期30分3分岐", "30分後に上/横/下へ進む確率と軌道"))

        if "VWAP" in opt_lines and traj.get("has_actual"):
            cards.append((_swatch_line("#fbbf24", "dotted", 2), "VWAP", "機関の平均買値（上なら買い優勢）"))

        if "VWAP±σ" in opt_lines and traj.get("has_actual"):
            cards.append((_swatch_line("rgba(251,191,36,0.7)", "dashed", 1), "VWAP±1σ/2σ", "買われすぎ・売られすぎの標準偏差帯"))

        if "類似実測波形（Top-1）" in opt_lines and isinstance(traj.get("medoid_analog"), dict) and traj["medoid_analog"].get("data"):
            cards.append((_swatch_line("#f59e0b", "solid", 2), "類似実測Top-1", "過去に最も似た日のリアル波形"))

        if "予測レンジ帯（ファン）" in opt_lines:
            cards.append((_swatch_band("rgba(56,189,248,0.22)", "rgba(99,102,241,0.48)"), "予測レンジ帯", "値動きが収まりやすい確率ゾーン"))

        if "高ボラ狩り場帯" in opt_lines and traj.get("high_vol_zones"):
            cards.append((_swatch_band("rgba(245,158,11,0.16)", "rgba(251,191,36,0.45)"), "高ボラ狩り場帯", "値幅が出やすく仕掛けが入りやすい時間"))

        if "前日/当日高安（PDH/PDL/HOD/LOD）" in opt_lines:
            cards.append((_swatch_line("#34d399", "dashed", 1), "PDH/PDL/HOD/LOD", "前日・当日の高値安値（注文集中帯）"))

        if "心理的キリ番節目" in opt_lines:
            cards.append((_swatch_line("#fde047", "dotted", 2), "キリ番節目", "注文が集中しやすいキリの良い価格"))

        if "寄り30分高安（ORB）" in opt_lines and traj.get("orb_high") and traj.get("orb_low"):
            cards.append((_swatch_line("#7dd3fc", "dashed", 1), "寄り30分ORB", "寄り30分の高安レンジ（ブレイク基準）"))

        if "大口約定（◆）" in opt_lines and traj.get("vol_spikes"):
            dm_sw = '<span style="display:inline-block;width:14px;text-align:center;color:#10b981;font-size:10px;line-height:1;flex-shrink:0;">◆</span>'
            cards.append((dm_sw, "大口約定◆", "通常2.5倍以上の出来高スパイク発生点"))

        if active_lab and "LAB TP/SL" in opt_lines:
            cards.append((_swatch_line("#10b981", "dashed", 2), "LAB TP/SL", "LAB上位足が算出した利確・損切り線"))

        cards.append((_swatch_line("#22d3ee", "solid", 2), "下段 出来高&CVD", "陽線/陰線出来高と買い売り累積差"))

    pills_html = "".join(
        f'<span class="dd-leg-pill">{sw}<span>{html.escape(nm)}</span></span>'
        for sw, nm, _ in cards
    )
    cards_html = "".join(
        f'<div class="dd-leg-card"><div class="dd-leg-head">{sw}<span>{html.escape(nm)}</span></div>'
        f'<div class="dd-leg-desc">{html.escape(desc)}</div></div>'
        for sw, nm, desc in cards
    )

    st.markdown(f"""
    <div class="dd-legend-panel">
      <div class="{banner_cls}">{html.escape(banner_txt)}</div>
      <div class="dd-chip-ribbon">{pills_html}</div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("📖 アクティブ凡例の詳細 ＆ 専門指標クイック辞典", expanded=False):
        st.markdown(f'<div class="dd-legend-grid" style="margin-bottom:8px;">{cards_html}</div>', unsafe_allow_html=True)
        st.markdown("""
        <div style="font-size:11px;line-height:1.65;color:#cbd5e1;">
        ・<b>1分足マイクロ・ズーム：</b> 直近90分の1分足ローソク足＋9EMA/20EMA＋10分先3分岐。スキャルピングの押し目・ブレイク執行に最適です。<br>
        ・<b>下段 出来高＆疑似CVD同期パネル：</b> 上段の価格と完全連動。価格が高値更新しているのに下段のシアン線(CVD)が下がる場合は上ヒゲ売り圧力（天井失速）のサインです。<br>
        ・<b>PDH / PDL / PDC / HOD / LOD：</b> 前日高値(PDH)・前日安値(PDL)・前日終値(PDC)・当日高値(HOD)・当日安値(LOD)。機関の逆指値と利確注文が集中する重要節目です。<br>
        ・<b>EXPANSION（急騰/急落ブレイク）モード：</b> 実測が朝想定バンドを連続突破・大出来高伴い急変した際に自動発動。古い紫線を無効化し、青線の追従上限とレジサポ転換を解放します。<br>
        ・<b>二壁FPT到達確率：</b> 大引けまでに「損切りライン(SL)へ先に触れずに利確目標(TP)へ到達する」確率モデルに基づく物理確率です。
        </div>
        """, unsafe_allow_html=True)
# =========================================================================
# 4. マーケット・ニュース・株主・1分足データ取得（TTL分離＆超短期速報）
# =========================================================================
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
    tokens = [re.sub(r"[^A-Za-z0-9\-]", "", t) for t in str(corp_name).split()]
    for tk in tokens:
        if len(tk) >= 3 and tk.upper() not in GENERIC_CORP_TOKENS:
            return tk
    return short_code


@st.cache_data(ttl=600)
def _load_macro_daily_base() -> dict:
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
    return out


@st.cache_data(ttl=20)
def _load_macro_rt_quotes() -> dict:
    rt_codes = [MACRO_TICKERS[k][0] for k in INTRADAY_RT_MACRO_KEYS if k in MACRO_TICKERS]
    rt_map = {}
    try:
        raw_rt = yf.download(rt_codes, period="2d", interval="5m", group_by="ticker", prepost=True, threads=True, progress=False, timeout=5.0)
        for k in INTRADAY_RT_MACRO_KEYS:
            tk = MACRO_TICKERS[k][0]
            try:
                df_rt = raw_rt[tk].dropna(subset=["Close"]) if isinstance(raw_rt.columns, pd.MultiIndex) else raw_rt.dropna(subset=["Close"])
                if not df_rt.empty:
                    rt_last = float(df_rt["Close"].iloc[-1])
                    if rt_last > 0:
                        rt_map[k] = rt_last
            except Exception:
                pass
    except Exception:
        pass
    return rt_map


def _load_macro_data() -> dict:
    base = _load_macro_daily_base()
    rt_map = _load_macro_rt_quotes()
    out = {}
    for k, item in base.items():
        copied = dict(item)
        if k in rt_map and copied.get("prev_close", 0.0) > 0:
            rt_last = rt_map[k]
            ref_prev = float(copied["prev_close"])
            copied["last"] = rt_last
            copied["diff_pct"] = round((rt_last - ref_prev) / max(abs(ref_prev), 1e-4) * 100.0, 2)
            copied["is_rt"] = True
        out[k] = copied
    return out


@st.cache_data(ttl=20)
def _load_benchmark_5m(is_jp: bool) -> pd.DataFrame:
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
            for idx_itx, row in itx.head(15).iterrows():
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
        "df_1d": df_1d, "info": info,
        "earnings_hist": earnings_hist, "next_earnings_days": next_earnings_days,
        "inst_holders": inst_holders, "insider_tx": insider_tx
    }


@st.cache_data(ttl=20)
def _load_stock_intraday(code: str) -> pd.DataFrame:
    try:
        tkr = yf.Ticker(code)
        df_5m = tkr.history(period="1mo", interval="5m", auto_adjust=True)
        if df_5m is not None and not df_5m.empty:
            return df_5m.dropna(subset=["Close"]).copy()
    except Exception:
        pass
    return pd.DataFrame()


@st.cache_data(ttl=15)
def _load_stock_1m(code: str) -> pd.DataFrame:
    try:
        tkr = yf.Ticker(code)
        df_1m = tkr.history(period="2d", interval="1m", auto_adjust=True)
        if df_1m is not None and not df_1m.empty:
            return df_1m.dropna(subset=["Close"]).copy()
    except Exception:
        pass
    return pd.DataFrame()


def _load_stock_core(code: str) -> dict:
    with ThreadPoolExecutor(max_workers=3) as ex:
        f_st = ex.submit(_load_stock_static, code)
        f_5m = ex.submit(_load_stock_intraday, code)
        f_1m = ex.submit(_load_stock_1m, code)
        st_data = f_st.result()
        df_5m = f_5m.result()
        df_1m = f_1m.result()
    out = dict(st_data)
    out["df_5m"] = df_5m
    out["df_1m"] = df_1m
    return out


def _fetch_rss(url: str, lang_tag: str) -> list:
    out = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3.8) as r:
            for it in ET.fromstring(r.read()).findall("./channel/item")[:14]:
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


def _fetch_kabutan_news_fast(code4: str) -> list:
    items = []
    try:
        url = f"https://kabutan.jp/stock/news?code={urllib.parse.quote(code4)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3.5, context=ssl.create_default_context()) as r:
            page = r.read().decode("utf-8", errors="ignore")
        tz_jst = ZoneInfo("Asia/Tokyo") if ZoneInfo is not None else datetime.timezone(datetime.timedelta(hours=9))
        now_jst = datetime.datetime.now(tz_jst)
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.DOTALL):
            m_time = re.search(r"<time[^>]*datetime=[\"']([^\"']+)[\"'][^>]*>([^<]*)</time>", tr)
            m_link = re.search(r"<a[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", tr, re.DOTALL)
            if not m_link:
                continue
            raw_href = html.unescape(m_link.group(1)).strip()
            title_txt = re.sub(r"<[^>]+>", "", html.unescape(m_link.group(2))).strip()
            if not title_txt or len(title_txt) < 4:
                continue
            full_link = raw_href if raw_href.startswith("http") else f"https://kabutan.jp{raw_href}"
            pub_raw = ""
            pub_disp = ""
            if m_time:
                dt_iso = m_time.group(1).strip()
                pub_disp = m_time.group(2).strip() or dt_iso[:16]
                try:
                    dt_p = datetime.datetime.fromisoformat(dt_iso.replace("Z", "+00:00"))
                    if dt_p.tzinfo is None:
                        dt_p = dt_p.replace(tzinfo=tz_jst)
                    pub_raw = email.utils.format_datetime(dt_p.astimezone(datetime.timezone.utc))
                except Exception:
                    pub_raw = email.utils.format_datetime(now_jst.astimezone(datetime.timezone.utc))
            items.append({
                "title": title_txt,
                "link": full_link,
                "source": "株探(Kabutan)",
                "pub": pub_disp or "速報",
                "pub_raw": pub_raw,
                "lang": "JP",
            })
            if len(items) >= 8:
                break
    except Exception:
        pass
    return items


def _fetch_yf_news_fast(code: str) -> list:
    items = []
    try:
        raw_n = yf.Ticker(code).news or []
        for it in raw_n[:10]:
            if not isinstance(it, dict):
                continue
            content = it.get("content") if isinstance(it.get("content"), dict) else it
            title = str(content.get("title") or it.get("title") or "").strip()
            if not title:
                continue
            pub_raw = ""
            pub_disp = ""
            pub_date_iso = content.get("pubDate") or content.get("displayTime")
            ts_unix = it.get("providerPublishTime")
            if pub_date_iso:
                try:
                    dt_p = datetime.datetime.fromisoformat(str(pub_date_iso).replace("Z", "+00:00"))
                    if dt_p.tzinfo is None:
                        dt_p = dt_p.replace(tzinfo=datetime.timezone.utc)
                    pub_raw = email.utils.format_datetime(dt_p.astimezone(datetime.timezone.utc))
                    pub_disp = dt_p.strftime("%m/%d %H:%M")
                except Exception:
                    pass
            elif ts_unix:
                try:
                    dt_p = datetime.datetime.fromtimestamp(float(ts_unix), tz=datetime.timezone.utc)
                    pub_raw = email.utils.format_datetime(dt_p)
                    pub_disp = dt_p.strftime("%m/%d %H:%M")
                except Exception:
                    pass
            prov = content.get("provider") if isinstance(content.get("provider"), dict) else {}
            src = str(prov.get("displayName") or it.get("publisher") or "Yahoo Finance").strip()
            click_u = content.get("clickThroughUrl") if isinstance(content.get("clickThroughUrl"), dict) else {}
            canon_u = content.get("canonicalUrl") if isinstance(content.get("canonicalUrl"), dict) else {}
            link = str(click_u.get("url") or canon_u.get("url") or it.get("link") or "").strip()
            items.append({
                "title": title,
                "link": link,
                "source": src,
                "pub": pub_disp or "Wire",
                "pub_raw": pub_raw,
                "lang": "EN",
            })
    except Exception:
        pass
    return items


def _calc_rss_time_decay(pub_raw: str, now_utc: datetime.datetime) -> tuple:
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
        if age_hours <= 0.25:
            return 3.0, round(age_hours, 2)
        if age_hours <= 1.0:
            return 2.0, round(age_hours, 2)
        if age_hours <= 3.0:
            return 1.2, round(age_hours, 1)
        if age_hours <= 24.0:
            return 0.6, round(age_hours, 1)
        if age_hours <= 72.0:
            return 0.2, round(age_hours, 1)
        return 0.0, round(age_hours, 1)
    except Exception:
        return 0.0, 999.0


def _strip_neg_guards(text: str) -> str:
    cleaned = text
    for pat in NEG_GUARD_PATTERNS:
        cleaned = re.sub(pat, "", cleaned)
    return cleaned


@st.cache_data(ttl=45)
def _fetch_global_intel(corp_name: str, short_code: str, full_code: str = "") -> dict:
    core_tok = _extract_core_corp_token(corp_name, short_code)
    is_jp_code = full_code.endswith(".T") or bool(re.match(r"^[0-9]{3}[0-9A-Z]$", short_code))
    q_jp = f"{corp_name} OR {short_code} 株価"
    q_en = f"{short_code} OR \"{core_tok}\" stock (Reuters OR Bloomberg OR CNBC OR WSJ)"
    u_jp = f"https://news.google.com/rss/search?q={urllib.parse.quote(q_jp)}&hl=ja&gl=JP&ceid=JP:ja"
    u_en = f"https://news.google.com/rss/search?q={urllib.parse.quote(q_en)}&hl=en-US&gl=US&ceid=US:en"

    raw_items = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        f1 = ex.submit(_fetch_rss, u_jp, "JP")
        f2 = ex.submit(_fetch_rss, u_en, "EN")
        f3 = ex.submit(_fetch_kabutan_news_fast, short_code) if is_jp_code else ex.submit(_fetch_yf_news_fast, full_code or short_code)
        raw_items.extend(f3.result())
        raw_items.extend(f1.result())
        raw_items.extend(f2.result())

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    pos_w = ["上昇", "急騰", "最高益", "上方修正", "増配", "自社株買い", "好調", "提携", "買い", "黒字", "成長", "SURGE", "BEAT", "UPGRADE", "RECORD", "BUY", "GROWTH", "RALLY"]
    neg_w = ["下落", "急落", "下方修正", "赤字", "減益", "不祥事", "訴訟", "不正", "辞任", "懸念", "売り", "リスク", "DROP", "FALL", "MISS", "DOWNGRADE", "LAWSUIT", "PROBE", "CUT", "SLUMP"]

    filtered, seen_t = [], set()
    catalyst_hits = []
    breaking_list = []

    for it in raw_items:
        src_up = (it["source"] + " " + it["title"]).upper()
        if any(ns.upper() in src_up for ns in NOISE_SOURCES):
            continue
        nk = re.sub(r"\W+", "", it["title"].lower())[:26]
        if nk in seen_t:
            continue
        seen_t.add(nk)

        decay_w, age_h = _calc_rss_time_decay(it.get("pub_raw", ""), now_utc)
        trust, base_wt = ("S", 2.0) if any(t1 in src_up for t1 in TIER1_SOURCES) else (("A", 1.3) if any(t2 in src_up for t2 in TIER2_SOURCES) else ("B", 0.7))

        cleaned_raw = _strip_neg_guards(it["title"])
        t_up = cleaned_raw.upper()
        p_h, n_h = sum(1 for w in pos_w if w in t_up), sum(1 for w in neg_w if w in t_up)

        cat_dir = None
        cat_kw_hit = ""
        for kw in CATALYST_POS_JP:
            if kw in cleaned_raw:
                cat_dir, cat_kw_hit = "POS", kw
                break
        if not cat_dir:
            for kw in CATALYST_POS_EN:
                if kw in t_up:
                    cat_dir, cat_kw_hit = "POS", kw
                    break
        if not cat_dir:
            for kw in CATALYST_NEG_JP:
                if kw in cleaned_raw:
                    cat_dir, cat_kw_hit = "NEG", kw
                    break
        if not cat_dir:
            for kw in CATALYST_NEG_EN:
                if kw in t_up:
                    cat_dir, cat_kw_hit = "NEG", kw
                    break

        is_breaking = bool(age_h <= 1.0)
        cat_mult = 1.65 if (cat_dir and is_breaking) else (1.25 if cat_dir else 1.0)
        eff_wt = round(base_wt * decay_w * cat_mult, 3)

        sent = cat_dir if cat_dir else ("POS" if p_h > n_h else ("NEG" if n_h > p_h else "NEU"))
        if cat_dir and is_breaking:
            catalyst_hits.append({"dir": cat_dir, "kw": cat_kw_hit, "title": it["title"], "age_min": int(round(age_h * 60))})
        if is_breaking and decay_w > 0:
            breaking_list.append({"title": it["title"], "source": it["source"], "sent": sent, "age_min": max(1, int(round(age_h * 60))), "link": it["link"]})

        filtered.append({
            **it,
            "trust": trust,
            "w_trust": eff_wt,
            "decay_w": decay_w,
            "age_h": age_h,
            "is_breaking": is_breaking,
            "catalyst_kw": cat_kw_hit,
            "sent": sent,
        })

    filtered.sort(key=lambda x: (-x["decay_w"], {"S": 0, "A": 1, "B": 2}[x["trust"]], 0 if x["lang"] == "EN" else 1))
    fresh_items = [x for x in filtered if x["w_trust"] > 0.0]
    wp = sum(x["w_trust"] for x in fresh_items if x["sent"] == "POS")
    wn = sum(x["w_trust"] for x in fresh_items if x["sent"] == "NEG")
    wtot = max(sum(x["w_trust"] for x in fresh_items), 1.0)

    has_cat_60m = len(catalyst_hits) > 0
    score_cap = 1.5 if has_cat_60m else 1.0
    raw_shock = ((wp - wn) / wtot) * (1.35 if has_cat_60m else 1.0) if fresh_items else 0.0
    shock_sc = round(float(np.clip(raw_shock, -score_cap, score_cap)), 2)

    catalyst_alert = None
    if catalyst_hits:
        top_c = catalyst_hits[0]
        catalyst_alert = {
            "active": True,
            "dir": top_c["dir"],
            "kw": top_c["kw"],
            "title": top_c["title"],
            "age_min": top_c["age_min"],
            "boost_drift_pct": round((0.85 if top_c["dir"] == "POS" else -0.85), 2),
        }

    return {
        "items": filtered[:12],
        "all_72h": fresh_items,
        "pos_pct": round(wp / wtot * 100) if fresh_items else 50,
        "shock_score": shock_sc,
        "tier1_cnt": sum(1 for x in fresh_items if x["trust"] == "S"),
        "fresh_cnt": len(fresh_items),
        "catalyst_alert": catalyst_alert,
        "breaking_news": breaking_list[0] if breaking_list else None,
    }


@st.cache_data(ttl=180)
def _fetch_gov_and_whales(corp_name: str, short_code: str, is_jp: bool = True) -> tuple:
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    if is_jp:
        u_g = f"https://news.google.com/rss/search?q={urllib.parse.quote(f'{corp_name} (不祥事 OR 不正 OR 訴訟 OR 行政処分 OR 辞任 OR リコール)')}&hl=ja&gl=JP&ceid=JP:ja"
        u_w = f"https://news.google.com/rss/search?q={urllib.parse.quote(f'({corp_name} OR {short_code}) (大量保有 OR 変更報告書 OR 空売り残高 OR 5%ルール OR 買い増し OR 保有割合低下)')}&hl=ja&gl=JP&ceid=JP:ja"
        gov_kw = ["不祥事", "不正", "訴訟", "行政処分", "辞任", "リコール"]
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

    core_tok = _extract_core_corp_token(corp_name, short_code)
    u_g_en = f"https://news.google.com/rss/search?q={urllib.parse.quote(f'({short_code} OR \"{core_tok}\") (SEC investigation OR fraud OR lawsuit OR recall OR subpoena OR antitrust)')}&hl=en-US&gl=US&ceid=US:en"
    u_w_en = f"https://news.google.com/rss/search?q={urllib.parse.quote(f'({short_code} OR \"{core_tok}\") (13D OR 13G OR insider buying OR insider selling OR Form 4 OR short interest)')}&hl=en-US&gl=US&ceid=US:en"
    gov_kw_en = ["SEC", "INVESTIGATION", "FRAUD", "LAWSUIT", "RECALL", "SUBPOENA", "ANTITRUST", "PROBE"]
    with ThreadPoolExecutor(max_workers=2) as ex:
        fg, fw = ex.submit(_fetch_rss, u_g_en, "EN"), ex.submit(_fetch_rss, u_w_en, "EN")
        gov_filtered = []
        for x in fg.result()[:10]:
            decay_w, _ = _calc_rss_time_decay(x.get("pub_raw", ""), now_utc)
            if decay_w <= 0.0:
                continue
            t_up = _strip_neg_guards(x["title"]).upper()
            if any(k in t_up for k in gov_kw_en):
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
# 5. プロ基準価格・MTF同調LED・価格帯ラダー・1分足ズームデータ構築
# =========================================================================
def _compute_round_number_level(curr_px: float, is_jp: bool) -> float:
    if is_jp:
        step = 5000 if curr_px >= 20000 else (1000 if curr_px >= 5000 else (500 if curr_px >= 2000 else 100))
    else:
        step = 50 if curr_px >= 400 else (25 if curr_px >= 150 else (10 if curr_px >= 50 else 5))
    return float(round(curr_px / step) * step)


def _compute_pro_ref_levels(df_1d: pd.DataFrame, df_5m: pd.DataFrame, is_jp: bool, market_today_str: str) -> dict:
    out = {"pdh": None, "pdl": None, "pdc": None, "hod": None, "lod": None}
    if df_1d is not None and not df_1d.empty:
        last_1d_s = df_1d.index[-1].strftime("%Y-%m-%d") if hasattr(df_1d.index[-1], "strftime") else str(df_1d.index[-1])[:10]
        if last_1d_s == market_today_str and len(df_1d) >= 2:
            prev_row = df_1d.iloc[-2]
        else:
            prev_row = df_1d.iloc[-1]
        out["pdh"] = round(float(prev_row["High"]), 2)
        out["pdl"] = round(float(prev_row["Low"]), 2)
        out["pdc"] = round(float(prev_row["Close"]), 2)

    if df_5m is not None and not df_5m.empty:
        tmp = df_5m.copy()
        idx_dt = _convert_5m_index_to_market_tz(tmp, is_jp)
        tmp["_d"] = idx_dt.strftime("%Y-%m-%d")
        sub_td = tmp[tmp["_d"] == market_today_str]
        if not sub_td.empty:
            out["hod"] = round(float(sub_td["High"].max()), 2)
            out["lod"] = round(float(sub_td["Low"].min()), 2)
    return out


def _build_1m_zoom_payload(
    df_1m: pd.DataFrame, is_jp: bool, market_today_str: str,
    exp_dir: str = "NONE", hvn_wall_px: float = 0.0, ob_sup_px: float = 0.0, vp: dict = None
) -> dict:
    invalid_res = {"valid": False}
    if df_1m is None or df_1m.empty or len(df_1m) < 10:
        return invalid_res

    try:
        tmp = df_1m.copy()
        idx_dt = _convert_5m_index_to_market_tz(tmp, is_jp)
        tmp["_d"] = idx_dt.strftime("%Y-%m-%d")
        tmp["_hm"] = idx_dt.strftime("%H:%M")

        target_d = market_today_str if (market_today_str in tmp["_d"].values) else tmp["_d"].iloc[-1]
        sub_day = tmp[tmp["_d"] == target_d].copy()
        if len(sub_day) < 8:
            return invalid_res

        closes_all = sub_day["Close"].values.astype(float)
        opens_all = sub_day["Open"].values.astype(float)
        highs_all = sub_day["High"].values.astype(float)
        lows_all = sub_day["Low"].values.astype(float)
        vols_all = np.maximum(sub_day["Volume"].values.astype(float), 0.0)

        n_all = len(closes_all)
        vwap_all = np.zeros(n_all, dtype=float)
        cvd_all = np.zeros(n_all, dtype=float)
        cum_pv, cum_v, cum_cvd = 0.0, 0.0, 0.0
        for i in range(n_all):
            tp = (highs_all[i] + lows_all[i] + closes_all[i]) / 3.0
            cum_pv += tp * vols_all[i]
            cum_v += vols_all[i]
            vwap_all[i] = (cum_pv / cum_v) if cum_v > 0 else closes_all[i]
            hl_s = highs_all[i] - lows_all[i]
            clv = (((closes_all[i] - lows_all[i]) - (highs_all[i] - closes_all[i])) / hl_s) if hl_s > 1e-6 else (1.0 if closes_all[i] >= opens_all[i] else -1.0)
            cum_cvd += clv * vols_all[i]
            cvd_all[i] = cum_cvd

        s_clos = pd.Series(closes_all)
        ema9_all = s_clos.ewm(span=9, adjust=False).mean().values
        ema20_all = s_clos.ewm(span=20, adjust=False).mean().values

        win = 90
        sub_w = sub_day.tail(win)
        n_w = len(sub_w)
        c_w = closes_all[-n_w:]
        o_w = opens_all[-n_w:]
        h_w = highs_all[-n_w:]
        l_w = lows_all[-n_w:]
        v_w = vols_all[-n_w:]
        vw_w = vwap_all[-n_w:]
        cvd_w = cvd_all[-n_w:]
        e9_w = ema9_all[-n_w:]
        e20_w = ema20_all[-n_w:]
        hms_w = sub_w["_hm"].tolist()

        last_ts = pd.Timestamp(idx_dt[tmp["_d"] == target_d][-1])
        fut_hms = [(last_ts + datetime.timedelta(minutes=k)).strftime("%H:%M") for k in range(1, 11)]
        all_times = hms_w + fut_hms
        n_tot = len(all_times)

        ohlc_list = [
            [round(float(o_w[i]), 2), round(float(c_w[i]), 2), round(float(l_w[i]), 2), round(float(h_w[i]), 2)]
            for i in range(n_w)
        ] + [["-", "-", "-", "-"] for _ in range(10)]

        ema9_list = [round(float(x), 2) for x in e9_w] + [None] * 10
        ema20_list = [round(float(x), 2) for x in e20_w] + [None] * 10
        vwap_list = [round(float(x), 2) for x in vw_w] + [None] * 10
        cvd_list = [round(float(x), 1) for x in cvd_w] + [None] * 10

        vol_bars = []
        for i in range(n_w):
            is_up_b = c_w[i] >= o_w[i]
            vol_bars.append({
                "value": round(float(v_w[i]), 1),
                "itemStyle": {"color": "rgba(16, 185, 129, 0.58)" if is_up_b else "rgba(239, 68, 68, 0.58)"},
            })
        for _ in range(10):
            vol_bars.append({"value": 0, "itemStyle": {"color": "transparent"}})
        avg_vol_1m = round(float(np.mean(v_w)), 1) if len(v_w) > 0 else 0.0

        anchor_px = float(c_w[-1])
        rets_1m = np.diff(c_w[-25:]) / np.maximum(c_w[-25:-1], 1e-4) if len(c_w) >= 5 else np.array([0.001])
        sig_1m = float(np.clip(np.std(rets_1m), 0.0005, 0.0065))

        vw_gap = (anchor_px - float(vw_w[-1])) / max(float(vw_w[-1]), 1e-4)
        e_gap = (float(e9_w[-1]) - float(e20_w[-1])) / max(float(e20_w[-1]), 1e-4)
        sc_u = float(np.clip(vw_gap * 110.0 + e_gap * 140.0 + (0.45 if exp_dir == "UP" else 0.0), -0.8, 1.4))
        sc_d = float(np.clip(-vw_gap * 110.0 - e_gap * 140.0 + (0.45 if exp_dir == "DOWN" else 0.0), -0.8, 1.4))
        sc_f = 0.25
        exps = np.exp(np.array([sc_u, sc_f, sc_d]) - max(sc_u, sc_f, sc_d))
        probs = (exps / np.sum(exps)) * 100.0
        p_up = int(np.clip(round(float(probs[0])), 4, 92))
        p_dn = int(np.clip(round(float(probs[2])), 4, 92))
        p_fl = max(2, 100 - p_up - p_dn)

        up_p = [None] * n_tot
        fl_p = [None] * n_tot
        dn_p = [None] * n_tot
        last_idx = n_w - 1
        up_p[last_idx] = round(anchor_px, 2)
        fl_p[last_idx] = round(anchor_px, 2)
        dn_p[last_idx] = round(anchor_px, 2)
        vw_last = float(vw_w[-1])

        for k in range(1, 11):
            idx_k = last_idx + k
            step_sig = sig_1m * math.sqrt(k)
            u_raw = anchor_px * (1.0 + step_sig * 1.15)
            d_raw = anchor_px * (1.0 - step_sig * 1.15)
            f_raw = anchor_px + (0.5 * (anchor_px + vw_last) - anchor_px) * (k / 10.0) * 0.45
            if isinstance(vp, dict):
                u_raw = _apply_hvn_ob_bounce(u_raw, anchor_px, hvn_wall_px, ob_sup_px, vp, exp_dir=exp_dir)
                d_raw = _apply_hvn_ob_bounce(d_raw, anchor_px, hvn_wall_px, ob_sup_px, vp, exp_dir=exp_dir)
            up_p[idx_k] = round(float(u_raw), 2)
            fl_p[idx_k] = round(float(f_raw), 2)
            dn_p[idx_k] = round(float(max(d_raw, anchor_px * 0.5)), 2)

        return {
            "valid": True,
            "is_today": bool(target_d == market_today_str),
            "target_date": target_d,
            "times": all_times,
            "ohlc": ohlc_list,
            "ema9": ema9_list,
            "ema20": ema20_list,
            "vwap": vwap_list,
            "vol_bars": vol_bars,
            "avg_vol_1m": avg_vol_1m,
            "cvd": cvd_list,
            "last_ema9": float(e9_w[-1]),
            "last_ema20": float(e20_w[-1]),
            "p_up": p_up,
            "p_flat": p_fl,
            "p_down": p_dn,
            "up_path": up_p,
            "flat_path": fl_p,
            "down_path": dn_p,
        }
    except Exception:
        return invalid_res


def _compute_mtf_alignment(df_1m: pd.DataFrame, df_5m: pd.DataFrame, df_1d: pd.DataFrame, is_jp: bool) -> dict:
    def _eval_series(s: pd.Series) -> tuple:
        if s is None or len(s) < 12:
            return "NEU", "▶", "#38bdf8"
        e9 = s.ewm(span=9, adjust=False).mean()
        e20 = s.ewm(span=20, adjust=False).mean()
        c_now = float(s.iloc[-1])
        e9_now, e9_prev = float(e9.iloc[-1]), float(e9.iloc[-2])
        e20_now = float(e20.iloc[-1])
        if c_now > e9_now and e9_now >= e20_now and e9_now > e9_prev:
            return "BULL", "▲", "#10b981"
        if c_now < e9_now and e9_now <= e20_now and e9_now < e9_prev:
            return "BEAR", "▼", "#ef4444"
        return "NEU", "▶", "#38bdf8"

    tfs = []
    s_1m = df_1m["Close"].dropna() if (df_1m is not None and not df_1m.empty) else None
    tfs.append(("1m", *_eval_series(s_1m)))

    if df_5m is not None and not df_5m.empty:
        tmp = df_5m.copy()
        idx_dt = _convert_5m_index_to_market_tz(tmp, is_jp)
        tmp.index = idx_dt
        s_5m = tmp["Close"].dropna()
        tfs.append(("5m", *_eval_series(s_5m)))
        try:
            s_15m = s_5m.resample("15min").last().dropna()
            tfs.append(("15m", *_eval_series(s_15m)))
        except Exception:
            tfs.append(("15m", "NEU", "▶", "#38bdf8"))
        try:
            s_60m = s_5m.resample("60min").last().dropna()
            tfs.append(("60m", *_eval_series(s_60m)))
        except Exception:
            tfs.append(("60m", "NEU", "▶", "#38bdf8"))
    else:
        tfs.extend([("5m", "NEU", "▶", "#38bdf8"), ("15m", "NEU", "▶", "#38bdf8"), ("60m", "NEU", "▶", "#38bdf8")])

    s_1d = df_1d["Close"].dropna() if (df_1d is not None and not df_1d.empty) else None
    tfs.append(("1D", *_eval_series(s_1d)))

    bull_cnt = sum(1 for _, st_c, _, _ in tfs if st_c == "BULL")
    bear_cnt = sum(1 for _, st_c, _, _ in tfs if st_c == "BEAR")
    if bull_cnt >= 4:
        sum_txt, sum_col = f"同調 {bull_cnt}/5 強気", "#10b981"
    elif bear_cnt >= 4:
        sum_txt, sum_col = f"同調 {bear_cnt}/5 弱気", "#ef4444"
    elif bull_cnt > bear_cnt:
        sum_txt, sum_col = f"やや強気 ({bull_cnt}/5)", "#6ee7b7"
    elif bear_cnt > bull_cnt:
        sum_txt, sum_col = f"やや弱気 ({bear_cnt}/5)", "#fca5a5"
    else:
        sum_txt, sum_col = "方向拮抗 (中立)", "#94a3b8"

    return {"items": tfs, "bull_cnt": bull_cnt, "bear_cnt": bear_cnt, "summary": sum_txt, "color": sum_col}


def _render_mtf_and_ladder(
    mtf_res: dict, curr_px: float, is_jp: bool, ref_lv: dict, traj: dict,
    vp: dict, round_level: float, active_lab
):
    led_parts = []
    for tf_lbl, _, arrow, col in mtf_res["items"]:
        led_parts.append(
            f'<span class="dd-mtf-led" style="border-color:{col};color:{col};background:rgba(15,23,42,0.92);">'
            f'{tf_lbl} {arrow}</span>'
        )
    st.markdown(f"""
    <div class="dd-mtf-bar">
      <div class="dd-mtf-pills"><span style="font-size:10px;font-weight:800;color:#94a3b8;margin-right:2px;">MTF:</span>{"".join(led_parts)}</div>
      <div class="dd-mtf-sum" style="color:{mtf_res['color']};">{html.escape(mtf_res['summary'])}</div>
    </div>
    """, unsafe_allow_html=True)

    if curr_px <= 0:
        return
    cands = []
    la = traj.get("last_act_idx", -1)
    if traj.get("has_actual") and la >= 0:
        vw = traj["vwap"][la]
        vp1 = traj["vwap_p1"][la]
        vp2 = traj["vwap_p2"][la]
        vm1 = traj["vwap_m1"][la]
        vm2 = traj["vwap_m2"][la]
        if vw:
            cands.append(("当日VWAP", float(vw), "#fbbf24"))
        if vp1:
            cands.append(("VWAP+1σ", float(vp1), "#f59e0b"))
        if vp2:
            cands.append(("VWAP+2σ", float(vp2), "#ef4444"))
        if vm1:
            cands.append(("VWAP-1σ", float(vm1), "#38bdf8"))
        if vm2:
            cands.append(("VWAP-2σ", float(vm2), "#10b981"))

    if ref_lv.get("hod"):
        cands.append(("当日高値(HOD)", float(ref_lv["hod"]), "#f43f5e"))
    if ref_lv.get("lod"):
        cands.append(("当日安値(LOD)", float(ref_lv["lod"]), "#10b981"))
    if ref_lv.get("pdh"):
        cands.append(("前日高値(PDH)", float(ref_lv["pdh"]), "#fb7185"))
    if ref_lv.get("pdl"):
        cands.append(("前日安値(PDL)", float(ref_lv["pdl"]), "#34d399"))
    if ref_lv.get("pdc"):
        cands.append(("前日終値(PDC)", float(ref_lv["pdc"]), "#94a3b8"))

    if traj.get("orb_high"):
        cands.append(("ORB高値", float(traj["orb_high"]), "#7dd3fc"))
    if traj.get("orb_low"):
        cands.append(("ORB安値", float(traj["orb_low"]), "#fda4af"))
    if round_level > 0:
        cands.append(("キリ番節目", float(round_level), "#fde047"))
    if vp.get("res_px"):
        cands.append(("しこり売り壁", float(vp["res_px"]), "#c084fc"))
    if vp.get("sup_px"):
        cands.append(("買い支え帯", float(vp["sup_px"]), "#38bdf8"))

    f_d = traj.get("factors", {})
    if f_d.get("hvn_wall_px", 0.0) > 0:
        cands.append(("2Y HVN壁", float(f_d["hvn_wall_px"]), "#d8b4fe"))
    if f_d.get("ob_sup_px", 0.0) > 0:
        cands.append(("機関OB支持", float(f_d["ob_sup_px"]), "#6ee7b7"))

    if isinstance(active_lab, dict):
        l_tp = float(active_lab.get("tp", active_lab.get("raw_tp", 0.0)) or 0.0)
        l_sl = float(active_lab.get("sl", active_lab.get("raw_sl", 0.0)) or 0.0)
        if l_tp > 0:
            cands.append(("LAB TP目標", l_tp, "#10b981"))
        if l_sl > 0:
            cands.append(("LAB SL撤退", l_sl, "#ef4444"))

    res_list, sup_list = [], []
    seen_px = set()
    for lbl, px, col in cands:
        if px <= 0 or abs(px - curr_px) / curr_px < 0.0005:
            continue
        key_p = f"{lbl}:{round(px, 2)}"
        if key_p in seen_px:
            continue
        seen_px.add(key_p)
        dist_pct = (px - curr_px) / curr_px * 100.0
        if dist_pct > 0:
            res_list.append((dist_pct, lbl, px, col))
        else:
            sup_list.append((dist_pct, lbl, px, col))

    res_top5 = sorted(res_list, key=lambda x: x[0])[:5][::-1]
    sup_top5 = sorted(sup_list, key=lambda x: abs(x[0]))[:5]

    if res_top5 or sup_top5:
        with st.expander("🪜 価格帯ラダー：上下の壁・支持帯までの距離", expanded=False):
            rows_html = []
            for d_pct, lbl, px, col in res_top5:
                w_bar = int(np.clip(abs(d_pct) * 18.0, 8, 100))
                rows_html.append(
                    f'<div class="dd-lad-row">'
                    f'<span style="color:{col};font-weight:700;">▲ {html.escape(lbl)}</span>'
                    f'<span style="display:inline-flex;align-items:center;gap:6px;">'
                    f'<span style="color:#f8fafc;font-weight:800;">{_fmt_cur(px, is_jp)}</span>'
                    f'<span style="color:#fca5a5;min-width:52px;text-align:right;">{d_pct:+.2f}%</span>'
                    f'<span class="dd-lad-bar-bg"><span style="display:block;width:{w_bar}%;height:100%;background:#ef4444;"></span></span>'
                    f'</span></div>'
                )
            rows_html.append(
                f'<div class="dd-lad-now"><span>● 現在値（基準）</span><span>{_fmt_cur(curr_px, is_jp)} (0.00%)</span></div>'
            )
            for d_pct, lbl, px, col in sup_top5:
                w_bar = int(np.clip(abs(d_pct) * 18.0, 8, 100))
                rows_html.append(
                    f'<div class="dd-lad-row">'
                    f'<span style="color:{col};font-weight:700;">▼ {html.escape(lbl)}</span>'
                    f'<span style="display:inline-flex;align-items:center;gap:6px;">'
                    f'<span style="color:#f8fafc;font-weight:800;">{_fmt_cur(px, is_jp)}</span>'
                    f'<span style="color:#6ee7b7;min-width:52px;text-align:right;">{d_pct:+.2f}%</span>'
                    f'<span class="dd-lad-bar-bg"><span style="display:block;width:{w_bar}%;height:100%;background:#10b981;"></span></span>'
                    f'</span></div>'
                )
            st.markdown(f'<div class="dd-ladder-wrap">{"".join(rows_html)}</div>', unsafe_allow_html=True)


# =========================================================================
# 5B. Phase 3 プロ仕様高度分析エンジン（タブ2・タブ3・タブ4魔改造用）
# =========================================================================
def _compute_dow_intraday_heatmap(df_5m: pd.DataFrame, is_jp: bool) -> dict:
    """要件1-1: 曜日 × 30分時間帯 期待値ヒートマップデータ生成"""
    empty_hm = {"valid": False}
    if df_5m is None or df_5m.empty or len(df_5m) < 40:
        return empty_hm
    try:
        tmp = df_5m.copy()
        idx_dt = _convert_5m_index_to_market_tz(tmp, is_jp)
        tmp.index = idx_dt
        tmp["_dow"] = idx_dt.dayofweek
        tmp = tmp[tmp["_dow"] < 5].copy()
        if tmp.empty:
            return empty_hm

        tmp["_date"] = tmp.index.strftime("%Y-%m-%d")
        slot_labels = (
            ["09:00", "09:30", "10:00", "10:30", "11:00", "12:30", "13:00", "13:30", "14:00", "14:30", "15:00"]
            if is_jp else
            ["09:30", "10:00", "10:30", "11:00", "11:30", "12:00", "12:30", "13:00", "13:30", "14:00", "14:30", "15:00", "15:30"]
        )
        slot_set = set(slot_labels)
        dow_names = ["月", "火", "水", "木", "金"]

        buckets = {(d, sl): [] for d in range(5) for sl in slot_labels}
        for (_, d_val), sub_d in tmp.groupby(["_date", "_dow"]):
            res30 = sub_d.resample("30min", origin="start_day").agg({"Open": "first", "Close": "last"}).dropna()
            for ts_b, r_b in res30.iterrows():
                hm_s = ts_b.strftime("%H:%M")
                if hm_s in slot_set and float(r_b["Open"]) > 0:
                    ret_pct = (float(r_b["Close"]) - float(r_b["Open"])) / float(r_b["Open"]) * 100.0
                    buckets[(int(d_val), hm_s)].append(ret_pct)

        y_labels = ["金", "木", "水", "火", "月"]
        y_dow_map = {"月": 4, "火": 3, "水": 2, "木": 1, "金": 0}
        hm_data = []
        best_cell = None
        worst_cell = None
        abs_vals = []

        for d_idx in range(5):
            d_nm = dow_names[d_idx]
            y_pos = y_dow_map[d_nm]
            for x_pos, sl in enumerate(slot_labels):
                vals = buckets[(d_idx, sl)]
                if vals:
                    avg_r = round(float(np.mean(vals)), 3)
                    wr_pct = int(round(float(np.mean([1.0 if v > 0 else 0.0 for v in vals]) * 100.0)))
                    n_cnt = len(vals)
                    abs_vals.append(abs(avg_r))
                    hm_data.append([x_pos, y_pos, avg_r, wr_pct, n_cnt])
                    if n_cnt >= 2:
                        if best_cell is None or avg_r > best_cell[0]:
                            best_cell = (avg_r, f"{d_nm}曜 {sl}", wr_pct, n_cnt)
                        if worst_cell is None or avg_r < worst_cell[0]:
                            worst_cell = (avg_r, f"{d_nm}曜 {sl}", wr_pct, n_cnt)
                else:
                    hm_data.append([x_pos, y_pos, "-", 50, 0])

        if not abs_vals:
            return empty_hm
        vmax = round(float(np.clip(np.percentile(abs_vals, 90), 0.12, 0.80)), 2)
        return {
            "valid": True,
            "x_labels": slot_labels,
            "y_labels": y_labels,
            "data": hm_data,
            "vmax": vmax,
            "best": best_cell,
            "worst": worst_cell,
        }
    except Exception:
        return empty_hm


def _compute_rolling_macro_corr(stock_close: pd.Series, macro_item: dict) -> dict:
    """要件1-2: ローリング相関（20日 vs 60日）＆ 20日ダイナミックβ推移"""
    empty_rc = {"valid": False}
    if stock_close is None or not isinstance(macro_item, dict) or "series" not in macro_item:
        return empty_rc
    try:
        s_ret = stock_close.pct_change().dropna()
        m_ret = macro_item["series"].pct_change().dropna()
        df_j = pd.concat([s_ret.rename("stk"), m_ret.rename("mac")], axis=1).dropna()
        if len(df_j) < 65:
            return empty_rc

        c20 = df_j["stk"].rolling(20).corr(df_j["mac"])
        c60 = df_j["stk"].rolling(60).corr(df_j["mac"])
        cov20 = df_j["stk"].rolling(20).cov(df_j["mac"])
        var20 = df_j["mac"].rolling(20).var()
        beta20 = cov20 / var20.replace(0, np.nan)

        sub = pd.DataFrame({"c20": c20, "c60": c60, "b20": beta20}).dropna().tail(90)
        if len(sub) < 15:
            return empty_rc

        dates = [idx.strftime("%m/%d") for idx in sub.index]
        c20_arr = [round(float(np.clip(x, -1.0, 1.0)), 2) for x in sub["c20"].values]
        c60_arr = [round(float(np.clip(x, -1.0, 1.0)), 2) for x in sub["c60"].values]
        b20_arr = [round(float(np.clip(x, -3.5, 3.5)), 2) for x in sub["b20"].values]

        decoupled = bool((c60_arr[-1] - c20_arr[-1]) >= 0.25 or (abs(c60_arr[-1]) - abs(c20_arr[-1])) >= 0.25)
        return {
            "valid": True,
            "label": macro_item.get("label", "主連動指数"),
            "dates": dates,
            "c20": c20_arr,
            "c60": c60_arr,
            "b20": b20_arr,
            "decoupled": decoupled,
            "last_c20": c20_arr[-1],
            "last_c60": c60_arr[-1],
            "last_b20": b20_arr[-1],
        }
    except Exception:
        return empty_rc


def _compute_earnings_pead(df_1d: pd.DataFrame, earnings_hist: list) -> dict:
    """要件1-3: 決算PEAD（決算翌日ギャップ％ ＋ 決算後5営業日累計リターン％）"""
    empty_p = {"valid": False}
    if df_1d is None or df_1d.empty or not earnings_hist:
        return empty_p
    try:
        dates_list = [idx.strftime("%Y-%m-%d") for idx in df_1d.index]
        date_to_pos = {d: i for i, d in enumerate(dates_list)}
        opens = df_1d["Open"].values.astype(float)
        closes = df_1d["Close"].values.astype(float)

        rows = []
        for e in reversed(earnings_hist):
            ed_s = str(e.get("date", ""))[:10]
            if ed_s not in date_to_pos:
                try:
                    dt_e = datetime.datetime.strptime(ed_s, "%Y-%m-%d")
                    nxt_s = (dt_e + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                    if nxt_s in date_to_pos:
                        ed_s = nxt_s
                except Exception:
                    pass
            if ed_s not in date_to_pos:
                continue
            pos = date_to_pos[ed_s]
            if pos < 1 or pos + 5 >= len(closes):
                continue
            prev_c = closes[pos - 1]
            react_op = opens[pos]
            post5_c = closes[pos + 5]
            if prev_c <= 0 or react_op <= 0:
                continue
            gap_pct = round((react_op - prev_c) / prev_c * 100.0, 2)
            drift5_pct = round((post5_c - prev_c) / prev_c * 100.0, 2)
            rows.append({"date": ed_s[2:7], "gap": gap_pct, "drift5": drift5_pct})

        if len(rows) < 2:
            return empty_p
        return {
            "valid": True,
            "dates": [r["date"] for r in rows],
            "gaps": [r["gap"] for r in rows],
            "drifts5": [r["drift5"] for r in rows],
        }
    except Exception:
        return empty_p


def _compute_hires_vp_28(df_1d: pd.DataFrame, curr_px: float, is_jp: bool) -> dict:
    """要件2-1: 高解像度28分割 Volume Profile（VA70% / POC / 短期20日 vs 中期60日減衰積み上げ）"""
    empty_vp = {"valid": False}
    if df_1d is None or len(df_1d) < 25:
        return empty_vp
    try:
        sub = df_1d.tail(250)
        n_rows = len(sub)
        lows = sub["Low"].values.astype(float)
        highs = sub["High"].values.astype(float)
        vols = sub["Volume"].values.astype(float)

        p_min = float(np.min(lows))
        p_max = float(np.max(highs))
        if p_max <= p_min:
            p_max = p_min + 1e-3

        n_bins = 28
        bins = np.linspace(p_min, p_max, n_bins + 1)
        bin_w = (p_max - p_min) / n_bins
        hist_short = np.zeros(n_bins, dtype=float)
        hist_mid = np.zeros(n_bins, dtype=float)

        for idx_r in range(n_rows):
            age = n_rows - 1 - idx_r
            lo_v, hi_v, raw_v = lows[idx_r], highs[idx_r], vols[idx_r]
            if raw_v <= 0:
                continue
            is_recent = age < 20
            w_vol = raw_v if is_recent else raw_v * (0.5 ** (age / 60.0))
            target_h = hist_short if is_recent else hist_mid

            if hi_v <= lo_v + 1e-6:
                b_idx = int(np.clip((lo_v - p_min) / max(bin_w, 1e-6), 0, n_bins - 1))
                target_h[b_idx] += w_vol
            else:
                span = hi_v - lo_v
                for b in range(n_bins):
                    ov_lo = max(lo_v, bins[b])
                    ov_hi = min(hi_v, bins[b + 1])
                    if ov_hi > ov_lo:
                        target_h[b] += w_vol * ((ov_hi - ov_lo) / span)

        tot_h = hist_short + hist_mid
        tot_sum = max(float(np.sum(tot_h)), 1.0)
        centers = [(bins[i] + bins[i + 1]) * 0.5 for i in range(n_bins)]

        poc_idx = int(np.argmax(tot_h))
        poc_px = float(centers[poc_idx])

        va_indices = {poc_idx}
        acc_v = float(tot_h[poc_idx])
        lo_ptr, hi_ptr = poc_idx - 1, poc_idx + 1
        while acc_v < tot_sum * 0.70 and (lo_ptr >= 0 or hi_ptr < n_bins):
            v_lo = float(tot_h[lo_ptr]) if lo_ptr >= 0 else -1.0
            v_hi = float(tot_h[hi_ptr]) if hi_ptr < n_bins else -1.0
            if v_hi >= v_lo and hi_ptr < n_bins:
                va_indices.add(hi_ptr)
                acc_v += v_hi
                hi_ptr += 1
            elif lo_ptr >= 0:
                va_indices.add(lo_ptr)
                acc_v += v_lo
                lo_ptr -= 1
            else:
                break

        val_px = float(centers[min(va_indices)])
        vah_px = float(centers[max(va_indices)])
        curr_bin_idx = int(np.clip((curr_px - p_min) / max(bin_w, 1e-6), 0, n_bins - 1))

        short_bars = []
        mid_bars = []
        for i in range(n_bins):
            s_m = round(float(hist_short[i]) / 1e6, 2)
            m_m = round(float(hist_mid[i]) / 1e6, 2)
            if i == poc_idx:
                c_s, c_m = "#f59e0b", "rgba(245, 158, 11, 0.45)"
            elif i in va_indices:
                c_s, c_m = "#38bdf8", "rgba(56, 189, 248, 0.35)"
            else:
                c_s, c_m = "#94a3b8", "rgba(100, 116, 139, 0.32)"
            short_bars.append({"value": s_m, "itemStyle": {"color": c_s}})
            mid_bars.append({"value": m_m, "itemStyle": {"color": c_m}})

        return {
            "valid": True,
            "labels": [_fmt_cur(c, is_jp) for c in centers],
            "short_bars": short_bars,
            "mid_bars": mid_bars,
            "poc_px": poc_px,
            "vah_px": vah_px,
            "val_px": val_px,
            "curr_bin_idx": curr_bin_idx,
        }
    except Exception:
        return empty_vp


def _compute_bbw_squeeze(df_1d: pd.DataFrame) -> dict:
    """要件2-2: 過去6ヶ月日足ボリンジャーバンド ＋ BBWパーセンタイル推移（スクイーズ検知）"""
    empty_sq = {"valid": False}
    if df_1d is None or len(df_1d) < 40:
        return empty_sq
    try:
        sub = df_1d.tail(145).copy()
        c = sub["Close"]
        ma20 = c.rolling(20).mean()
        sd20 = c.rolling(20).std()
        up2 = ma20 + 2.0 * sd20
        dn2 = ma20 - 2.0 * sd20
        bbw = ((up2 - dn2) / ma20.replace(0, np.nan)) * 100.0

        valid_df = pd.DataFrame({"c": c, "ma": ma20, "up": up2, "dn": dn2, "bbw": bbw}).dropna().tail(120)
        if len(valid_df) < 20:
            return empty_sq

        bbw_vals = valid_df["bbw"].values.astype(float)
        cur_bbw = float(bbw_vals[-1])
        pct_rank = int(round(float(np.mean(bbw_vals <= cur_bbw) * 100.0)))
        is_squeeze = bool(pct_rank <= 20)

        bbw_pct_series = [int(round(float(np.mean(bbw_vals <= v) * 100.0))) for v in bbw_vals]
        return {
            "valid": True,
            "dates": [idx.strftime("%m/%d") for idx in valid_df.index],
            "closes": [round(float(x), 2) for x in valid_df["c"].values],
            "ma20": [round(float(x), 2) for x in valid_df["ma"].values],
            "upper": [round(float(x), 2) for x in valid_df["up"].values],
            "lower": [round(float(x), 2) for x in valid_df["dn"].values],
            "band_diff": [round(float(u - l), 2) for u, l in zip(valid_df["up"].values, valid_df["dn"].values)],
            "bbw_pct_series": bbw_pct_series,
            "cur_pct": pct_rank,
            "cur_bbw": round(cur_bbw, 1),
            "is_squeeze": is_squeeze,
        }
    except Exception:
        return empty_sq


def _build_news_72h_timeline(all_72h_items: list) -> dict:
    """要件3-1: 72時間ニュース・センチメント密度タイムライン（12時間刻み6ビン）"""
    empty_tl = {"valid": False}
    if not all_72h_items:
        return empty_tl
    bins_lbl = ["72-60h前", "60-48h前", "48-36h前", "36-24h前", "24-12h前", "直近12h"]
    counts = [0] * 6
    net_scores = [0.0] * 6
    for it in all_72h_items:
        ah = float(it.get("age_h", 999.0))
        if ah < 0 or ah > 72.0:
            continue
        b_idx = int(np.clip(5 - int(ah // 12.0), 0, 5))
        counts[b_idx] += 1
        s_sign = 1.0 if it.get("sent") == "POS" else (-1.0 if it.get("sent") == "NEG" else 0.0)
        net_scores[b_idx] += s_sign * float(it.get("w_trust", 1.0))

    if sum(counts) == 0:
        return empty_tl
    return {
        "valid": True,
        "labels": bins_lbl,
        "counts": counts,
        "scores": [round(x, 2) for x in net_scores],
    }


def _extract_ledger_verify_history(ledger: dict, is_jp: bool) -> list:
    """要件3-3: 大引け確定済みロック検証の直近15件履歴"""
    if not isinstance(ledger, dict):
        return []
    recs = []
    for code_k, hist_map in ledger.items():
        if is_jp != code_k.endswith(".T") or not isinstance(hist_map, dict):
            continue
        for dt_k, snap in hist_map.items():
            if not isinstance(snap, dict) or snap.get("locked_premarket") is not True:
                continue
            v_stat = snap.get("verify_result")
            if isinstance(v_stat, dict) and v_stat.get("finalized"):
                recs.append({
                    "date": str(dt_k),
                    "code": code_k.replace(".T", ""),
                    "cone": round(float(v_stat.get("in_cone_pct", 0.0)), 1),
                    "err": round(float(v_stat.get("err_pct", 0.0)), 2),
                })
    recs.sort(key=lambda x: x["date"])
    return recs[-15:]


def _detect_whale_anomaly(insider_tx: list, whale_news: list, ref_today_str: str) -> dict:
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
        t_up = t.upper()
        if any(k in t for k in ["新規保有", "買い増し", "保有割合増加", "5%超"]) or any(k in t_up for k in ["13D", "INSIDER BUY", "STAKE INCREASE", "ACQUIRES STAKE"]):
            bull_sigs.append(f"大口買付: {t[:34]}")
        elif any(k in t for k in ["保有割合低下", "売却", "空売り残高増加", "売り増し"]) or any(k in t_up for k in ["INSIDER SELL", "CUTS STAKE", "SHORT INTEREST SURGE"]):
            bear_sigs.append(f"大口売/空売: {t[:34]}")

    if len(bull_sigs) > len(bear_sigs):
        return {"detected": True, "dir": "BULL", "adj_pct": round(min(0.65, 0.25 * (len(bull_sigs) - len(bear_sigs))), 2), "summary": " / ".join(bull_sigs[:2])}
    if len(bear_sigs) > len(bull_sigs):
        return {"detected": True, "dir": "BEAR", "adj_pct": round(-min(0.65, 0.25 * (len(bear_sigs) - len(bull_sigs))), 2), "summary": " / ".join(bear_sigs[:2])}
    return {"detected": False, "dir": "NEUTRAL", "adj_pct": 0.0, "summary": "直近30日以内の特異な大口異変なし"}


def _detect_expansion_regime(
    has_actual: bool, last_act_idx: int, slots: list, actual_arr: list,
    locked_p85: list, locked_p15: list, is_locked: bool,
    vwap_arr: list, vwap_p2_arr: list, vwap_m2_arr: list,
    vwap_p1_arr: list, vwap_m1_arr: list,
    act_vol_map: dict, act_dir_map: dict, slot_vols: np.ndarray,
    rvol: float, catalyst_alert: dict = None
) -> dict:
    default_exp = {
        "active": False,
        "dir": "NONE",
        "reasons": [],
        "unconfirmed_catalyst": False,
        "label": "通常レジーム",
    }
    if not has_actual or last_act_idx < 1:
        return default_exp

    reasons_up = []
    reasons_dn = []
    unconfirmed_cat = False

    if is_locked and last_act_idx >= 1:
        valid_pairs = [
            (actual_arr[i], locked_p85[i], locked_p15[i])
            for i in range(max(0, last_act_idx - 2), last_act_idx + 1)
            if actual_arr[i] is not None and locked_p85[i] is not None and locked_p15[i] is not None
        ]
        if len(valid_pairs) >= 2:
            if all(a > hi for a, hi, _ in valid_pairs[-2:]):
                reasons_up.append("朝ロック上限バンド(85%帯)を2本連続上抜け")
            if all(a < lo for a, _, lo in valid_pairs[-2:]):
                reasons_dn.append("朝ロック下限バンド(15%帯)を2本連続下抜け")

    cur_a = actual_arr[last_act_idx]
    cur_p2 = vwap_p2_arr[last_act_idx]
    cur_m2 = vwap_m2_arr[last_act_idx]
    if rvol is not None and rvol >= 2.2 and cur_a is not None:
        if cur_p2 is not None and cur_a > cur_p2:
            reasons_up.append(f"大商いRVOL({rvol:.2f}x)＋VWAP+2σ突破")
        if cur_m2 is not None and cur_a < cur_m2:
            reasons_dn.append(f"大商いRVOL({rvol:.2f}x)＋VWAP-2σ割れ")

    recent_indices = [i for i in range(max(0, last_act_idx - 4), last_act_idx + 1) if actual_arr[i] is not None][-3:]
    if len(recent_indices) == 3:
        dirs3 = [act_dir_map.get(slots[i], 0) for i in recent_indices]
        act_v3 = sum(float(act_vol_map.get(slots[i], 0.0)) for i in recent_indices)
        avg_v3 = sum(float(slot_vols[i]) for i in recent_indices)
        rvol3 = (act_v3 / avg_v3) if avg_v3 > 0 else 0.0

        vw_now = vwap_arr[last_act_idx]
        p1_now = vwap_p1_arr[last_act_idx]
        m1_now = vwap_m1_arr[last_act_idx]
        if rvol3 >= 3.0 and vw_now and p1_now and m1_now and cur_a is not None:
            sd_est = max(p1_now - vw_now, 1e-4)
            z_vwap = (cur_a - vw_now) / sd_est
            if all(d > 0 for d in dirs3) and z_vwap >= 1.5:
                reasons_up.append(f"直近15分3連続陽線＋出来高{rvol3:.1f}倍＋VWAP+{z_vwap:.1f}σ（未確認カタリスト・踏み上げ初動）")
                unconfirmed_cat = True
            elif all(d < 0 for d in dirs3) and z_vwap <= -1.5:
                reasons_dn.append(f"直近15分3連続陰線＋出来高{rvol3:.1f}倍＋VWAP{z_vwap:.1f}σ（未確認悪材料・投げ売り初動）")
                unconfirmed_cat = True

    if isinstance(catalyst_alert, dict) and catalyst_alert.get("active"):
        if catalyst_alert.get("dir") == "POS":
            reasons_up.append(f"速報特大カタリスト検知「{catalyst_alert.get('kw','')}」({catalyst_alert.get('age_min',1)}分前)")
        elif catalyst_alert.get("dir") == "NEG":
            reasons_dn.append(f"速報悪材料カタリスト検知「{catalyst_alert.get('kw','')}」({catalyst_alert.get('age_min',1)}分前)")

    if reasons_up and len(reasons_up) >= len(reasons_dn):
        return {
            "active": True,
            "dir": "UP",
            "reasons": reasons_up,
            "unconfirmed_catalyst": unconfirmed_cat,
            "label": "急騰ブレイクモード",
        }
    if reasons_dn:
        return {
            "active": True,
            "dir": "DOWN",
            "reasons": reasons_dn,
            "unconfirmed_catalyst": unconfirmed_cat,
            "label": "急落ブレイクモード",
        }
    return default_exp


def _detect_cvd_divergence(slots: list, actual_arr: list, cvd_arr: list, act_vol_map: dict) -> dict:
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
                "label": "上ヒゲ売り圧力",
                "color": "#ef4444",
                "detail": f"スイング高値更新（{sh1[1]}→{sh2[1]}）に対し、OHLCV疑似CVDが切り下げ。高値圏での上ヒゲ売り圧力・失速（弱気ダイバージェンス）の兆候。",
                "marker": {"time": sh2[1], "price": sh2[2], "name": "売り圧力", "color": "#ef4444"},
            }

    if len(swing_lows) >= 2:
        sl1, sl2 = swing_lows[-2], swing_lows[-1]
        if sl2[2] < sl1[2] * 0.9988 and sl2[3] > sl1[3]:
            return {
                "state": "ABSORPTION",
                "label": "下ヒゲ買い支え",
                "color": "#10b981",
                "detail": f"スイング安値更新（{sl1[1]}→{sl2[1]}）に対し、OHLCV疑似CVDが切り上げ。安値圏での下ヒゲ買い支え（強気ダイバージェンス）の兆候。",
                "marker": {"time": sl2[1], "price": sl2[2], "name": "買い支え", "color": "#10b981"},
            }

    last_cvd = pts[-1][3]
    if last_cvd > 0:
        return {"state": "ALIGNED_BULL", "label": "陽線出来高優位", "color": "#38bdf8", "detail": "OHLCV疑似CVDプラス圏で買い主導の推移。", "marker": None}
    if last_cvd < 0:
        return {"state": "ALIGNED_BEAR", "label": "陰線出来高優位", "color": "#f59e0b", "detail": "OHLCV疑似CVDマイナス圏で売り主導の推移。", "marker": None}
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
    rets = df_1d["Close"].pct_change().dropna() * 100.0
    names = ["月", "火", "水", "木", "金"]
    stats = []
    for d in range(5):
        sub = rets[rets.index.dayofweek == d]
        wr, avg = (int(round(float((sub > 0).mean() * 100.0), 0)), round(float(sub.mean()), 2)) if len(sub) >= 3 else (50, 0.0)
        stats.append({"dow": d, "label": names[d], "wr": wr, "avg": avg})
    target_ds = _get_target_session_date(is_jp)
    try:
        target_wd = datetime.datetime.strptime(target_ds, "%Y-%m-%d").weekday()
    except Exception:
        target_wd = _get_market_now(is_jp).weekday()
    target_wd = min(max(target_wd, 0), 4)
    return stats, target_wd


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

    n_rows = len(sub)
    lows = sub["Low"].values.astype(float)
    highs = sub["High"].values.astype(float)
    vols = sub["Volume"].values.astype(float)

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
        if snap.get("locked_premarket") is not True:
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


def _parse_float_safe(val, default_val=None):
    if val is None:
        return default_val
    if isinstance(val, (int, float)):
        return float(val) if not np.isnan(float(val)) else default_val
    m = re.search(r"[-+]?[0-9]*\.?[0-9]+", str(val).replace(",", ""))
    if m:
        try:
            return float(m.group(0))
        except Exception:
            return default_val
    return default_val


def _extract_lab_quant_modifiers(active_lab: dict, lab_council: dict) -> dict:
    res = {
        "has_lab": False,
        "lab_trust_mult": 1.0,
        "vpin_vboost": 1.0,
        "vpin_val": None,
        "kyle_val": None,
        "rs_30m": None,
        "council_caution": False,
        "wf_pf": None,
        "wf_wr": None,
    }
    if not isinstance(active_lab, dict) or not active_lab:
        return res
    res["has_lab"] = True

    trust_mult = 1.0
    wf22 = (
        active_lab.get("wf_22d")
        if isinstance(active_lab.get("wf_22d"), dict)
        else (
            active_lab.get("walk_forward_22d")
            if isinstance(active_lab.get("walk_forward_22d"), dict)
            else (active_lab.get("forward_test") if isinstance(active_lab.get("forward_test"), dict) else {})
        )
    )
    if wf22:
        pf_v = _parse_float_safe(wf22.get("pf", wf22.get("profit_factor")))
        wr_v = _parse_float_safe(wf22.get("win_rate", wf22.get("actual_win_rate")))
        res["wf_pf"] = pf_v
        res["wf_wr"] = wr_v
        if (pf_v is not None and pf_v < 1.0) or (wr_v is not None and wr_v < 45.0):
            trust_mult = 0.35
        elif (pf_v is not None and pf_v >= 1.5) and (wr_v is not None and wr_v >= 55.0):
            trust_mult = 1.15

    if isinstance(lab_council, dict) and lab_council:
        c_txt = str(lab_council.get("verdict") or lab_council.get("conclusion") or lab_council.get("summary") or "").upper()
        caution_kws = ["見送り", "回避", "警戒", "様子見", "HOLD", "危険"]
        if any(kw in c_txt for kw in caution_kws):
            trust_mult *= 0.45
            res["council_caution"] = True

    res["lab_trust_mult"] = round(float(np.clip(trust_mult, 0.10, 1.30)), 3)

    q_ind = (
        active_lab.get("quant_metrics")
        if isinstance(active_lab.get("quant_metrics"), dict)
        else (active_lab.get("quants") if isinstance(active_lab.get("quants"), dict) else {})
    )
    vpin_v = _parse_float_safe(q_ind.get("vpin", active_lab.get("vpin")))
    kyle_v = _parse_float_safe(q_ind.get("kyle_lambda", active_lab.get("kyle_lambda")))
    rs30_v = _parse_float_safe(q_ind.get("rs_30m", active_lab.get("intraday_rs_30m")))

    res["vpin_val"] = vpin_v
    res["kyle_val"] = kyle_v
    res["rs_30m"] = rs30_v

    if vpin_v is not None and vpin_v > 0.55:
        v_boost = 1.0 + min((vpin_v - 0.55) * 0.65, 0.25)
        res["vpin_vboost"] = round(float(v_boost), 3)

    return res


def _fit_short_3way_logreg(
    df_5m: pd.DataFrame, is_jp: bool, slots: list, slot_vols: np.ndarray,
    atr_pct: float, horizon_slots: int = 6
) -> dict:
    empty_ml = {
        "fitted": False,
        "n_samples": 0,
        "W": None,
        "b": None,
        "mu": None,
        "sd": None,
    }
    if df_5m is None or df_5m.empty or len(df_5m) < 80:
        return empty_ml

    try:
        market_today_str = _get_market_now(is_jp).strftime("%Y-%m-%d")
        tmp = df_5m.copy()
        idx_dt = _convert_5m_index_to_market_tz(tmp, is_jp)
        tmp["_d"] = idx_dt.strftime("%Y-%m-%d")
        tmp["_hm"] = idx_dt.strftime("%H:%M")

        slot_idx_map = {sl: i for i, sl in enumerate(slots)}
        cum_avg_vol_by_idx = np.cumsum(slot_vols) if len(slot_vols) == len(slots) else np.zeros(len(slots))

        th = float(np.clip((atr_pct / 100.0) * 0.14, 0.0018, 0.0045))
        X_rows, y_rows = [], []

        for ds, sub in tmp.groupby("_d"):
            if ds == market_today_str or len(sub) < (horizon_slots + 8):
                continue
            sub_valid = sub[sub["_hm"].isin(slot_idx_map)].copy()
            if len(sub_valid) < (horizon_slots + 8):
                continue

            closes = sub_valid["Close"].values.astype(float)
            opens = sub_valid["Open"].values.astype(float) if "Open" in sub_valid.columns else closes
            highs = sub_valid["High"].values.astype(float) if "High" in sub_valid.columns else closes
            lows = sub_valid["Low"].values.astype(float) if "Low" in sub_valid.columns else closes
            vols = np.maximum(sub_valid["Volume"].values.astype(float), 0.0) if "Volume" in sub_valid.columns else np.zeros(len(closes))
            hms = sub_valid["_hm"].values

            n_day = len(closes)
            cum_pv, cum_v, cum_cvd = 0.0, 0.0, 0.0
            vwap_day = np.zeros(n_day, dtype=float)
            cvd_day = np.zeros(n_day, dtype=float)
            cum_v_day = np.zeros(n_day, dtype=float)

            for k in range(n_day):
                tp = (highs[k] + lows[k] + closes[k]) / 3.0
                cum_pv += tp * vols[k]
                cum_v += vols[k]
                vwap_day[k] = (cum_pv / cum_v) if cum_v > 0 else closes[k]
                hl_s = highs[k] - lows[k]
                clv = (((closes[k] - lows[k]) - (highs[k] - closes[k])) / hl_s) if hl_s > 1e-6 else (1.0 if closes[k] >= opens[k] else -1.0)
                cum_cvd += clv * vols[k]
                cvd_day[k] = cum_cvd
                cum_v_day[k] = cum_v

            for k in range(3, n_day - horizon_slots):
                c_now = closes[k]
                c_fut = closes[k + horizon_slots]
                if c_now <= 0 or c_fut <= 0:
                    continue
                vw_now = vwap_day[k] if vwap_day[k] > 0 else c_now
                vwap_gap = (c_now - vw_now) / vw_now

                k_back = max(0, k - 6)
                c_back = closes[k_back] if closes[k_back] > 0 else c_now
                mom_30m = (c_now - c_back) / c_back

                s_i = slot_idx_map.get(hms[k], -1)
                avg_cv = float(cum_avg_vol_by_idx[s_i]) if (0 <= s_i < len(cum_avg_vol_by_idx)) else 0.0
                if avg_cv > 0 and cum_v_day[k] > 0:
                    log_rvol = math.log(max(cum_v_day[k] / avg_cv, 0.1))
                else:
                    log_rvol = 0.0

                cvd_sign = math.tanh(cvd_day[k] / max(cum_v_day[k] * 0.25, 1.0))

                fut_r = (c_fut - c_now) / c_now
                if fut_r > th:
                    lbl = 0
                elif fut_r < -th:
                    lbl = 2
                else:
                    lbl = 1

                X_rows.append([vwap_gap, mom_30m, log_rvol, cvd_sign])
                y_rows.append(lbl)

        n_samples = len(X_rows)
        if n_samples < 60:
            return {"fitted": False, "n_samples": n_samples, "W": None, "b": None, "mu": None, "sd": None}

        X = np.array(X_rows, dtype=float)
        y = np.array(y_rows, dtype=int)

        mu = np.mean(X, axis=0)
        sd = np.std(X, axis=0)
        sd = np.where(sd < 1e-6, 1.0, sd)
        Xs = (X - mu) / sd

        Y_oh = np.zeros((n_samples, 3), dtype=float)
        Y_oh[np.arange(n_samples), y] = 1.0

        W = np.zeros((4, 3), dtype=float)
        b = np.zeros(3, dtype=float)
        lr = 0.15
        reg = 0.05

        for _ in range(120):
            logits = Xs @ W + b
            logits -= np.max(logits, axis=1, keepdims=True)
            exps = np.exp(logits)
            probs = exps / np.sum(exps, axis=1, keepdims=True)
            diff = (probs - Y_oh) / n_samples
            grad_W = (Xs.T @ diff) + reg * W
            grad_b = np.sum(diff, axis=0)
            W -= lr * grad_W
            b -= lr * grad_b

        return {
            "fitted": True,
            "n_samples": n_samples,
            "W": W,
            "b": b,
            "mu": mu,
            "sd": sd,
        }
    except Exception:
        return empty_ml


def _apply_hvn_ob_bounce(
    mid: float, ref_px: float, hvn_wall_px: float, ob_sup_px: float, vp: dict,
    exp_dir: str = "NONE"
) -> float:
    if ref_px <= 0:
        return mid

    res_wall = 0.0
    is_hvn = False
    if hvn_wall_px > ref_px * 1.002:
        res_wall = hvn_wall_px
        is_hvn = True
    elif float(vp.get("res_px", 0.0)) > ref_px * 1.002:
        res_wall = float(vp["res_px"])

    sup_floor = 0.0
    is_ob = False
    if 0 < ob_sup_px < ref_px * 0.998:
        sup_floor = ob_sup_px
        is_ob = True
    elif 0 < float(vp.get("sup_px", 0.0)) < ref_px * 0.998:
        sup_floor = float(vp["sup_px"])

    if exp_dir == "UP":
        flipped_floors = [
            px for px in (hvn_wall_px, float(vp.get("res_px", 0.0)), sup_floor)
            if 0 < px < ref_px * 0.999
        ]
        if flipped_floors:
            best_floor = max(flipped_floors)
            if mid < best_floor * 1.003:
                mid = best_floor * 1.003 - (best_floor * 1.003 - mid) * 0.30
        return mid

    if exp_dir == "DOWN":
        flipped_ceilings = [
            px for px in (ob_sup_px, float(vp.get("sup_px", 0.0)), res_wall)
            if px > ref_px * 1.001
        ]
        if flipped_ceilings:
            best_ceil = min(flipped_ceilings)
            if mid > best_ceil * 0.997:
                mid = best_ceil * 0.997 + (mid - best_ceil * 0.997) * 0.30
        return mid

    if res_wall > 0 and mid > res_wall * 0.995:
        damp = 0.35 if is_hvn else (0.45 if vp.get("overhead_pct", 0.0) >= 35.0 else 1.0)
        if damp < 1.0:
            mid = res_wall * 0.995 + (mid - res_wall * 0.995) * damp

    if sup_floor > 0 and mid < sup_floor * 1.005:
        cushion = 0.38 if is_ob else 0.65
        mid = sup_floor * 1.005 - (sup_floor * 1.005 - mid) * cushion

    return mid


def _compute_short_horizon_3way(
    has_actual: bool, last_act_idx: int, n_slots: int,
    anchor_px: float, cur_vwap: float, mom_30m: float,
    rvol: float, cvd_div: dict, gap_open15: dict,
    bench_live_alpha_adj: float, knn_moves: dict,
    slot_means: np.ndarray, slot_inc_stds: np.ndarray, vboost: float,
    hvn_wall_px: float, ob_sup_px: float, vp: dict,
    shock_ext_pct: float = 0.0, horizon_slots: int = 6,
    ml_model: dict = None, cum_cvd_now: float = 0.0, cum_vol_now: float = 0.0,
    lab_dir_score: float = 0.0, lab_rs30: float = None,
    exp_dir: str = "NONE"
) -> dict:
    empty_res = {
        "active": False, "horizon": 0, "end_idx": -1,
        "p_up": 33, "p_flat": 34, "p_down": 33,
        "ml_used": False, "ml_samples": 0,
        "up_path": [None] * n_slots,
        "flat_path": [None] * n_slots,
        "down_path": [None] * n_slots,
    }
    if not has_actual or last_act_idx < 0 or anchor_px <= 0:
        return empty_res

    horizon = min(int(horizon_slots), n_slots - 1 - last_act_idx)
    if horizon < 1:
        return empty_res

    end_idx = last_act_idx + horizon
    vw_ref = cur_vwap if (cur_vwap is not None and cur_vwap > 0) else anchor_px
    vwap_gap = (anchor_px - vw_ref) / max(vw_ref, 1e-4)

    log_up = 0.0
    log_flat = 0.18
    log_down = 0.0

    if abs(vwap_gap) <= 0.0015:
        log_flat += 0.42
    elif vwap_gap > 0:
        log_up += float(np.clip(vwap_gap * 85.0, 0.15, 1.05))
        log_down -= float(np.clip(vwap_gap * 45.0, 0.05, 0.55))
    else:
        log_down += float(np.clip((-vwap_gap) * 85.0, 0.15, 1.05))
        log_up -= float(np.clip((-vwap_gap) * 45.0, 0.05, 0.55))

    if abs(mom_30m) <= 0.0012:
        log_flat += 0.30
    elif mom_30m > 0:
        log_up += float(np.clip(mom_30m * 95.0, 0.10, 1.15))
    else:
        log_down += float(np.clip((-mom_30m) * 95.0, 0.10, 1.15))

    if rvol is not None:
        if rvol >= 1.4:
            r_boost = float(np.clip((rvol - 1.0) * 0.42, 0.15, 0.85))
            if mom_30m >= 0 and vwap_gap >= -0.001:
                log_up += r_boost
            elif mom_30m < 0 and vwap_gap <= 0.001:
                log_down += r_boost
            log_flat -= r_boost * 0.65
        elif rvol < 0.85:
            log_flat += 0.68
            log_up -= 0.25
            log_down -= 0.25

    cvd_st = cvd_div.get("state", "NEUTRAL")
    if cvd_st == "ABSORPTION":
        log_up += 0.62
        log_down -= 0.45
    elif cvd_st == "ALIGNED_BULL":
        log_up += 0.34
    elif cvd_st == "DISTRIBUTION":
        log_down += 0.62
        log_up -= 0.45
    elif cvd_st == "ALIGNED_BEAR":
        log_down += 0.34

    g_bias = float(gap_open15.get("bias", 0.0))
    if g_bias > 0:
        log_up += float(np.clip(g_bias * 90.0, 0.10, 0.50))
    elif g_bias < 0:
        log_down += float(np.clip((-g_bias) * 90.0, 0.10, 0.50))

    if bench_live_alpha_adj > 0:
        log_up += float(np.clip(bench_live_alpha_adj * 55.0, 0.05, 0.55))
    elif bench_live_alpha_adj < 0:
        log_down += float(np.clip((-bench_live_alpha_adj) * 55.0, 0.05, 0.55))

    knn_end_rel = float(knn_moves.get(end_idx, 0.0)) if isinstance(knn_moves, dict) else 0.0
    if abs(knn_end_rel) <= 0.0015:
        log_flat += 0.25
    elif knn_end_rel > 0:
        log_up += float(np.clip(knn_end_rel * 75.0, 0.08, 0.65))
    else:
        log_down += float(np.clip((-knn_end_rel) * 75.0, 0.08, 0.65))

    if lab_dir_score > 0.01:
        log_up += float(np.clip(lab_dir_score * 0.48, 0.0, 0.55))
    elif lab_dir_score < -0.01:
        log_down += float(np.clip((-lab_dir_score) * 0.48, 0.0, 0.55))

    if lab_rs30 is not None:
        if lab_rs30 > 0.15:
            log_up += float(np.clip(lab_rs30 * 0.22, 0.05, 0.40))
        elif lab_rs30 < -0.15:
            log_down += float(np.clip((-lab_rs30) * 0.22, 0.05, 0.40))

    if exp_dir == "UP":
        log_up += 0.55
        log_down -= 0.35
    elif exp_dir == "DOWN":
        log_down += 0.55
        log_up -= 0.35

    if shock_ext_pct > 0.01:
        log_up += float(np.clip(shock_ext_pct * 0.70, 0.0, 1.40))
        log_down -= float(np.clip(shock_ext_pct * 0.35, 0.0, 0.70))
    elif shock_ext_pct < -0.01:
        log_down += float(np.clip((-shock_ext_pct) * 0.70, 0.0, 1.40))
        log_up -= float(np.clip((-shock_ext_pct) * 0.35, 0.0, 0.70))

    logits_rule = np.array([log_up, log_flat, log_down], dtype=float)
    logits_rule -= np.max(logits_rule)
    exps_rule = np.exp(logits_rule)
    probs_rule = exps_rule / np.sum(exps_rule)

    ml_used = False
    ml_samples = int(ml_model.get("n_samples", 0)) if isinstance(ml_model, dict) else 0
    probs_final = probs_rule
    if isinstance(ml_model, dict) and ml_model.get("fitted") and ml_samples >= 60:
        try:
            log_rvol_now = math.log(max(float(rvol), 0.1)) if (rvol is not None and rvol > 0) else 0.0
            cvd_sign_now = math.tanh(float(cum_cvd_now) / max(float(cum_vol_now) * 0.25, 1.0))
            x_now = np.array([vwap_gap, mom_30m, log_rvol_now, cvd_sign_now], dtype=float)
            x_std = (x_now - ml_model["mu"]) / ml_model["sd"]
            logits_ml = x_std @ ml_model["W"] + ml_model["b"]
            logits_ml -= np.max(logits_ml)
            exps_ml = np.exp(logits_ml)
            probs_ml = exps_ml / np.sum(exps_ml)

            w_ml = float(np.clip(ml_samples / (ml_samples + 120.0), 0.25, 0.70))
            if exp_dir in ("UP", "DOWN"):
                w_ml *= 0.65
            probs_final = w_ml * probs_ml + (1.0 - w_ml) * probs_rule
            probs_final = probs_final / np.sum(probs_final)
            ml_used = True
        except Exception:
            probs_final = probs_rule

    probs_pct = probs_final * 100.0
    p_up = int(np.clip(round(float(probs_pct[0])), 2, 96))
    p_down = int(np.clip(round(float(probs_pct[2])), 2, 96))
    p_flat = int(100 - p_up - p_down)
    if p_flat < 2:
        p_flat = 2
        if p_up >= p_down:
            p_up = 100 - p_flat - p_down
        else:
            p_down = 100 - p_flat - p_up

    up_path = [None] * n_slots
    flat_path = [None] * n_slots
    down_path = [None] * n_slots

    start_val = round(float(anchor_px), 2)
    up_path[last_act_idx] = start_val
    flat_path[last_act_idx] = start_val
    down_path[last_act_idx] = start_val

    anchor_mean = float(slot_means[last_act_idx])
    vwap_mid_target = 0.5 * (anchor_px + vw_ref)
    shock_ratio = shock_ext_pct / 100.0

    for k in range(1, horizon + 1):
        idx = last_act_idx + k
        step_frac = k / max(horizon, 1)
        cum_sig = float(np.sqrt(np.sum(slot_inc_stds[last_act_idx + 1:idx + 1] ** 2))) * vboost
        cum_sig = max(cum_sig, 0.0014 * math.sqrt(k))

        mean_delta = float(slot_means[idx]) - anchor_mean
        knn_delta = float(knn_moves[idx]) if (isinstance(knn_moves, dict) and idx in knn_moves) else mean_delta
        local_shape = 0.60 * mean_delta + 0.40 * knn_delta

        up_shock_add = max(0.0, shock_ratio) * 0.45 * step_frac
        up_raw = anchor_px * (1.0 + local_shape * 0.65 + cum_sig * 1.05 + up_shock_add)
        up_raw = _apply_hvn_ob_bounce(up_raw, anchor_px, hvn_wall_px, ob_sup_px, vp, exp_dir=exp_dir)
        up_raw = max(up_raw, anchor_px * (1.0 + 0.0005 * k))

        flat_center = anchor_px + (vwap_mid_target - anchor_px) * (0.45 * step_frac)
        flat_wave = anchor_px * (local_shape * 0.35 + shock_ratio * 0.15 * step_frac)
        flat_raw = _apply_hvn_ob_bounce(flat_center + flat_wave, anchor_px, hvn_wall_px, ob_sup_px, vp, exp_dir=exp_dir)

        dn_shock_sub = max(0.0, -shock_ratio) * 0.45 * step_frac
        dn_raw = anchor_px * (1.0 + local_shape * 0.65 - cum_sig * 1.05 - dn_shock_sub)
        dn_raw = _apply_hvn_ob_bounce(dn_raw, anchor_px, hvn_wall_px, ob_sup_px, vp, exp_dir=exp_dir)
        dn_raw = min(dn_raw, anchor_px * (1.0 - 0.0005 * k))
        dn_raw = max(dn_raw, anchor_px * 0.5)

        up_path[idx] = round(float(up_raw), 2)
        flat_path[idx] = round(float(flat_raw), 2)
        down_path[idx] = round(float(dn_raw), 2)

    return {
        "active": True,
        "horizon": horizon,
        "end_idx": end_idx,
        "p_up": p_up,
        "p_flat": p_flat,
        "p_down": p_down,
        "ml_used": ml_used,
        "ml_samples": ml_samples,
        "up_path": up_path,
        "flat_path": flat_path,
        "down_path": down_path,
    }


def _compute_bayesian_scenario_probs(
    has_actual: bool, curr_px: float, anchor_base_close: float,
    est_open_gap_pct: float, est_close_chg: float,
    bull_trig: float, bull_target: float, bear_trig: float, bear_target: float,
    rem_sigma_pct: float, rem_drift_pct: float,
    rvol: float, cvd_div: dict, gap_open15: dict,
    cur_vwap: float, shock_ext_pct: float = 0.0, exp_dir: str = "NONE"
) -> dict:
    fpt_bull = _calc_first_passage_prob(curr_px, bull_trig, rem_sigma_pct, rem_drift_pct) / 100.0
    fpt_bear = _calc_first_passage_prob(curr_px, bear_trig, rem_sigma_pct, rem_drift_pct) / 100.0
    p_stay_inside = max(1.0 - max(fpt_bull, fpt_bear), 0.15)

    log_bull = math.log(max(fpt_bull, 0.05)) + est_close_chg * 0.35 + shock_ext_pct * 0.60
    log_bear = math.log(max(fpt_bear, 0.05)) - est_close_chg * 0.35 - shock_ext_pct * 0.60
    log_range = math.log(p_stay_inside) + 0.55 - abs(est_close_chg) * 0.20
    log_fade = math.log(max(min(abs(est_open_gap_pct) / 2.5, 0.75), 0.08)) + 0.35

    if exp_dir == "UP":
        log_bull += 0.90
        log_range -= 0.35
        log_fade -= 0.45
    elif exp_dir == "DOWN":
        log_bear += 0.90
        log_range -= 0.35
        log_fade -= 0.45

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

    if has_actual and cur_vwap and cur_vwap > 0:
        vwap_diff_pct = (curr_px - cur_vwap) / cur_vwap * 100.0
        log_bull += float(np.clip(vwap_diff_pct * 0.55, -0.8, 0.8))
        log_bear -= float(np.clip(vwap_diff_pct * 0.55, -0.8, 0.8))
        if (est_open_gap_pct > 0.25 and vwap_diff_pct < -0.15) or (est_open_gap_pct < -0.25 and vwap_diff_pct > 0.15):
            log_fade += 0.65

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
    if not isinstance(ledger, dict) or not ledger:
        return {"rank": "計測中", "color": "#94a3b8", "n": 0, "hit_rate": 0.0, "mean_err": 0.0, "detail": "事前ロック検証データ蓄積中"}

    cur_gap_big = abs(cur_gap_pct) >= 0.8

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
            if snap.get("locked_premarket") is not True:
                continue
            v_stat = snap.get("verify_result")
            if not isinstance(v_stat, dict) or not v_stat.get("finalized", False):
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
            "detail": f"大引け確定済みの事前ロック検証が {n_samples}件（3件以上でランク判定）",
        }

    avg_cone = float(np.mean([r["in_cone"] for r in target_recs]))
    avg_err = float(np.mean([r["err_pct"] for r in target_recs]))
    gap_lbl = "大Gap" if cur_gap_big else "通常Gap"
    scope_lbl = f"{cur_regime}・{gap_lbl}" if len(matched_records) >= 3 else ("日本株全体" if is_jp else "米国株全体")

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
        "detail": f"{scope_lbl} (大引け確定 N={n_samples}): 予測帯収束率 {avg_cone:.1f}% / 平均誤差 {avg_err:.2f}%",
    }


# =========================================================================
# 6. デュアル5分足軌道エンジン
# =========================================================================
def _build_dual_5m_trajectory(
    fc_code: str, curr_px: float, prev_px: float, df_1d: pd.DataFrame, df_5m: pd.DataFrame,
    macro_sens: list, macro_data: dict, news_res: dict, whale_anom: dict,
    dow_next_avg: float, vp: dict, is_jp: bool, mkt_regime: dict, active_lab: dict = None,
    df_bench_5m: pd.DataFrame = None, lab_mods: dict = None
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

    vol_cls = _classify_vol_cluster(df_1d, is_jp)
    cluster_key = vol_cls["cluster"]
    fallback_key = vol_cls["fallback"]

    actual_map, vwap_map = {}, {}
    vwap_p1_map, vwap_m1_map, vwap_p2_map, vwap_m2_map = {}, {}, {}, {}
    act_vol_map, act_dir_map, act_low_map, act_high_map = {}, {}, {}, {}
    cvd_map = {}
    orb_high, orb_low = None, None
    cum_cvd_latest, cum_vol_latest = 0.0, 0.0

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
                    cum_cvd_latest = cum_cvd
                    cum_vol_latest = cum_v

    actual_arr = [actual_map.get(sl, None) for sl in slots]
    actual_vols_arr = [round(float(act_vol_map[sl]), 1) if sl in act_vol_map else None for sl in slots]
    actual_dirs_arr = [act_dir_map.get(sl, 1) for sl in slots]
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

    mods = lab_mods if isinstance(lab_mods, dict) else {}
    lab_trust_mult = float(mods.get("lab_trust_mult", 1.0))
    vpin_vboost = float(mods.get("vpin_vboost", 1.0))
    lab_rs30 = mods.get("rs_30m", None)

    lab_strength_dir = 0.0
    if isinstance(active_lab, dict) and active_lab:
        l_side = _extract_lab_side(active_lab)
        l_exp = float(active_lab.get("expect_pct", 50.0))
        l_strength = float(np.clip((l_exp - 50.0) / 40.0, 0.0, 1.0))
        lab_strength_dir = (1.0 if l_side == "LONG" else -1.0) * l_strength * lab_trust_mult

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
    rmaps, alpha_rmaps, rdates, day_gaps_hist, day_ranges_hist = [], [], [], [], []
    vmaps, use_maps, weights = [], [], []
    gap_fill_stats = {"prob": None, "avg_min": None, "n_samples": 0, "dir": "FLAT"}

    if df_5m is not None and not df_5m.empty:
        tmp = df_5m.copy()
        idx_dt = _convert_5m_index_to_market_tz(tmp, is_jp)
        tmp["_d"], tmp["_hm"] = idx_dt.strftime("%Y-%m-%d"), idx_dt.strftime("%H:%M")
        udays = sorted(tmp["_d"].unique().tolist())
        pdays = [d for d in udays if d != market_today_str]
        prev_day_close = None
        want_gu = tot_gap >= 0.15
        want_gd = tot_gap <= -0.15
        regime_tag = "GU類似加重" if want_gu else ("GD類似加重" if want_gd else "フラット加重")

        gf_total, gf_filled, gf_mins = 0, 0, []
        target_gap_dir = 1 if tot_gap >= 0.15 else (-1 if tot_gap <= -0.15 else 0)

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
            day_hi = float(sub["High"].max()) if "High" in sub.columns else float(sub["Close"].max())
            day_lo = float(sub["Low"].min()) if "Low" in sub.columns else float(sub["Close"].min())
            day_rng_pct = ((day_hi - day_lo) / op) * 100.0

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
                day_ranges_hist.append(day_rng_pct)
                vmaps.append(vm)
                weights.append(base_w)

        if gf_total >= 2:
            gap_fill_stats = {
                "prob": round(gf_filled / gf_total * 100.0, 0),
                "avg_min": int(round(float(np.mean(gf_mins)), 0)) if gf_mins else None,
                "n_samples": gf_total,
                "dir": "GU" if target_gap_dir > 0 else ("GD" if target_gap_dir < 0 else "BOTH"),
            }

        use_maps = alpha_rmaps if has_bench_5m else rmaps
        for i, sl in enumerate(slots):
            rv_mean, rv_vol, wv, vv = [], [], [], []
            for rm_u, rm_raw, vm, w in zip(use_maps, rmaps, vmaps, weights):
                if sl in rm_u:
                    rv_mean.append(rm_u[sl])
                    rv_vol.append(rm_raw[sl])
                    wv.append(w)
                    vv.append(vm[sl])
            if len(rv_mean) >= 3:
                wa = np.array(wv, dtype=float) / np.sum(wv)
                ra_m = np.array(rv_mean, dtype=float)
                ra_v = np.array(rv_vol, dtype=float)
                wm = float(np.sum(wa * ra_m))
                wm_raw = float(np.sum(wa * ra_v))
                slot_means[i] = wm
                slot_stds[i] = max(float(np.sqrt(np.sum(wa * ((ra_v - wm_raw) ** 2)))), 0.0025)
                slot_vols[i] = float(np.mean(vv)) if vv else 0.0

                ord_idx = np.argsort(ra_v)
                ra_s = ra_v[ord_idx] - wm_raw
                wa_s = wa[ord_idx]
                cdf_s = np.cumsum(wa_s) - 0.5 * wa_s
                slot_q10[i] = wm + float(np.interp(0.10, cdf_s, ra_s))
                slot_q25[i] = wm + float(np.interp(0.25, cdf_s, ra_s))
                slot_q75[i] = wm + float(np.interp(0.75, cdf_s, ra_s))
                slot_q90[i] = wm + float(np.interp(0.90, cdf_s, ra_s))
            else:
                sd_fb = 0.003 + 0.009 * np.sqrt((i + 1) / n_slots)
                slot_stds[i] = sd_fb
                slot_q10[i] = -1.28 * sd_fb
                slot_q25[i] = -0.67 * sd_fb
                slot_q75[i] = 0.67 * sd_fb
                slot_q90[i] = 1.28 * sd_fb
                slot_vols[i] = 0.0

        for i in range(n_slots):
            sl_cur = slots[i]
            sl_prev = slots[i - 1] if i > 0 else None
            inc_vals, inc_ws = [], []
            for rm_raw, w in zip(rmaps, weights):
                if sl_prev is None:
                    if sl_cur in rm_raw:
                        inc_vals.append(rm_raw[sl_cur])
                        inc_ws.append(w)
                else:
                    if sl_cur in rm_raw and sl_prev in rm_raw:
                        inc_vals.append(rm_raw[sl_cur] - rm_raw[sl_prev])
                        inc_ws.append(w)
            if len(inc_vals) >= 3:
                wa_i = np.array(inc_ws, dtype=float) / np.sum(inc_ws)
                ia = np.array(inc_vals, dtype=float)
                im = float(np.sum(wa_i * ia))
                slot_inc_stds[i] = max(float(np.sqrt(np.sum(wa_i * ((ia - im) ** 2)))), 0.0012)
            else:
                u_shape = 1.35 if (i < 6 or i >= n_slots - 6) else 0.85
                slot_inc_stds[i] = 0.0022 * u_shape

    tot_slot_vol = float(np.sum(slot_vols))
    if tot_slot_vol > 0 and n_slots > 1:
        cum_v_arr = np.cumsum(slot_vols)
        v0 = float(cum_v_arr[0])
        denom_v = max(float(cum_v_arr[-1]) - v0, 1e-6)
        vol_frac = np.clip((cum_v_arr - v0) / denom_v, 0.0, 1.0)
        vol_clock_active = True
    else:
        vol_frac = np.linspace(0.0, 1.0, max(n_slots, 1))
        vol_clock_active = False

    lunch_jump_std_pct = 0.0
    pm_open_idx = (lunch_idx + 1) if (is_jp and lunch_idx is not None and (lunch_idx + 1) < n_slots) else None
    if pm_open_idx is not None:
        sl_am_end = slots[lunch_idx]
        sl_pm_beg = slots[pm_open_idx]
        lj_vals, lj_ws = [], []
        for rm_raw, w in zip(rmaps, weights):
            if sl_am_end in rm_raw and sl_pm_beg in rm_raw:
                lj_vals.append(rm_raw[sl_pm_beg] - rm_raw[sl_am_end])
                lj_ws.append(w)
        if len(lj_vals) >= 3:
            wa_lj = np.array(lj_ws, dtype=float) / np.sum(lj_ws)
            lja = np.array(lj_vals, dtype=float)
            ljm = float(np.sum(wa_lj * lja))
            lj_std = max(float(np.sqrt(np.sum(wa_lj * ((lja - ljm) ** 2)))), float(np.mean(slot_inc_stds)) * 1.4)
        else:
            lj_std = float(np.mean(slot_inc_stds)) * 1.8
        slot_inc_stds[pm_open_idx] = lj_std
        lunch_jump_std_pct = round(lj_std * 100.0, 2)

    ml_3way_model = _fit_short_3way_logreg(
        df_5m, is_jp, slots, slot_vols, float(vol_cls["atr_pct"]), horizon_slots=6
    )

    mean_inc_std = float(np.mean(slot_inc_stds)) if len(slot_inc_stds) > 0 else 0.0022
    q75_inc_std = float(np.percentile(slot_inc_stds, 75)) if len(slot_inc_stds) > 0 else mean_inc_std * 1.18
    hv_thresh = max(mean_inc_std * 1.18, q75_inc_std)

    raw_hv_spans = []
    z_start = None
    for i in range(n_slots):
        if slot_inc_stds[i] >= hv_thresh:
            if z_start is None:
                z_start = i
        else:
            if z_start is not None:
                raw_hv_spans.append([z_start, i - 1])
                z_start = None
    if z_start is not None:
        raw_hv_spans.append([z_start, n_slots - 1])

    merged_hv_spans = []
    for sp in raw_hv_spans:
        if merged_hv_spans and (sp[0] - merged_hv_spans[-1][1] <= 2):
            merged_hv_spans[-1][1] = sp[1]
        else:
            merged_hv_spans.append(list(sp))

    high_vol_zones = []
    for s_i, e_i in merged_hv_spans:
        width_slots = e_i - s_i + 1
        avg_mv = round(float(np.mean(slot_inc_stds[s_i:e_i + 1])) * 100.0, 2)
        high_vol_zones.append({
            "start_slot": slots[s_i],
            "end_slot": slots[e_i],
            "width_slots": width_slots,
            "show_label": bool(width_slots >= 3),
            "avg_move_pct": avg_mv,
        })

    vol_profile_meta = {
        "mean_move_pct": round(mean_inc_std * 100.0, 2),
        "max_move_pct": round(float(np.max(slot_inc_stds)) * 100.0, 2) if len(slot_inc_stds) > 0 else 0.22,
        "zone_cnt": len(high_vol_zones),
    }

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

    cat_al = news_res.get("catalyst_alert")
    cat_drift_boost = (float(cat_al.get("boost_drift_pct", 0.0)) / 100.0) if (isinstance(cat_al, dict) and cat_al.get("active")) else 0.0

    est_open = anchor_base_close * (1.0 + tot_gap / 100.0)
    drift = float(np.clip((raw_news_x * idr_w["news"]) + ((dow_adj + wick_adj + calib_pct + lab_bias_pct) / 100.0) + cat_drift_boost, -0.045, 0.045))
    vboost = (1.0 + abs(raw_news_x) * 0.25) * (1.0 + max(0.0, vix_d / 100.0) * 1.2) * vpin_vboost

    start_rem_idx = (last_act_idx + 1) if (has_actual and last_act_idx >= 0) else 0
    if has_actual and last_act_idx >= 0:
        rem_frac_now = max(float(1.0 - vol_frac[last_act_idx]), 0.04)
    else:
        rem_frac_now = 1.0
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

    p50, p85, p15, bdiff = [], [], [], []
    p68, p32, bdiff_inner = [], [], []
    for i, sl in enumerate(slots):
        v_prog = float(vol_frac[i])
        mid = est_open * (1.0 + slot_means[i] + drift * v_prog)
        mid = _apply_hvn_ob_bounce(mid, est_open, hvn_wall_px, ob_sup_px, vp, exp_dir="NONE")

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

    saved_today = stock_hist.get(market_today_str) if isinstance(stock_hist.get(market_today_str), dict) else None
    has_premarket_lock = bool(saved_today and saved_today.get("locked_premarket") is True)

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
        if not has_actual and _is_valid_premarket_lock_window(is_jp, target_date):
            stock_hist[target_date] = {
                "p50": p50, "p85": p85, "p15": p15, "band_diff": bdiff,
                "p32": p32, "band_diff_in": bdiff_inner,
                "locked_premarket": True,
                "locked_at": _get_market_now(is_jp).strftime("%Y-%m-%d %H:%M:%S"),
                "regime_code": regime_code,
                "cluster_key": cluster_key,
                "pred_open_px": round(float(est_open), 4),
                "pred_open_gap_pct": round(float(tot_gap), 4),
                "slot_mean_end_pct": round(float(slot_means[-1]) * 100.0, 4),
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

    expansion_reg = _detect_expansion_regime(
        has_actual, last_act_idx, slots, actual_arr,
        locked_p85, locked_p15, is_locked,
        vwap_arr, vwap_p2_arr, vwap_m2_arr, vwap_p1_arr, vwap_m1_arr,
        act_vol_map, act_dir_map, slot_vols, rvol, catalyst_alert=cat_al
    )
    exp_dir = expansion_reg["dir"] if expansion_reg["active"] else "NONE"

    realized_30m_inc_std = 0.0
    if has_actual and last_act_idx >= 2:
        rec_rets = []
        for idx_r in range(max(1, last_act_idx - 5), last_act_idx + 1):
            if actual_arr[idx_r] is not None and actual_arr[idx_r - 1] is not None and actual_arr[idx_r - 1] > 0:
                rec_rets.append((actual_arr[idx_r] - actual_arr[idx_r - 1]) / actual_arr[idx_r - 1])
        if len(rec_rets) >= 2:
            realized_30m_inc_std = float(np.std(rec_rets))

    eff_slot_inc_stds = slot_inc_stds.copy()
    if expansion_reg["active"] and realized_30m_inc_std > 0:
        eff_slot_inc_stds = np.maximum(eff_slot_inc_stds, realized_30m_inc_std)
        if start_rem_idx < n_slots:
            rem_sigma_pct = max(float(np.sqrt(np.sum(eff_slot_inc_stds[start_rem_idx:] ** 2))), 0.002) * vboost

    target_atr = max(float(vol_cls["atr_pct"]), 0.8)
    max_r_cap = ((target_atr * 2.8) / 100.0) if expansion_reg["active"] else ((target_atr * 1.4) / 100.0)
    premarket_medoid = None
    if use_maps and rdates:
        n_r = len(use_maps)
        max_normal_rng = max(float(vol_cls["atr_pct"]) * 2.2, 5.0)
        valid_med_indices = []
        for idx_r in range(n_r):
            d_gap_i = float(day_gaps_hist[idx_r]) if idx_r < len(day_gaps_hist) else 0.0
            d_rng_i = float(day_ranges_hist[idx_r]) if idx_r < len(day_ranges_hist) else float(vol_cls["atr_pct"])
            if abs(d_gap_i - tot_gap) <= 3.0 and d_rng_i <= max_normal_rng:
                valid_med_indices.append(idx_r)
        cand_indices = valid_med_indices if valid_med_indices else list(range(n_r))

        best_score = 1e9
        best_idx = cand_indices[0]
        for idx_r in cand_indices:
            d_gap_i = float(day_gaps_hist[idx_r]) if idx_r < len(day_gaps_hist) else 0.0
            d_rng_i = float(day_ranges_hist[idx_r]) if idx_r < len(day_ranges_hist) else float(vol_cls["atr_pct"])
            gap_dist = abs(d_gap_i - tot_gap)
            range_dist = abs(d_rng_i - float(vol_cls["atr_pct"])) * 0.6
            recency_pen = 0.25 * (1.0 - (idx_r / max(n_r - 1, 1)))
            comp_score_m = gap_dist + range_dist + recency_pen
            if comp_score_m < best_score:
                best_score = comp_score_m
                best_idx = idx_r

        best_rm = use_maps[best_idx]
        best_ds = rdates[best_idx]
        best_gap = round(float(day_gaps_hist[best_idx]), 2) if best_idx < len(day_gaps_hist) else 0.0
        best_rng = float(day_ranges_hist[best_idx]) if best_idx < len(day_ranges_hist) else target_atr
        amp_scale = float(np.clip(target_atr / max(best_rng, 0.5), 0.35, 1.35))

        med_path = []
        last_valid_r = 0.0
        for sl in slots:
            if sl in best_rm:
                last_valid_r = float(best_rm[sl])
                r_scaled = float(np.clip(last_valid_r * amp_scale, -max_r_cap, max_r_cap))
                med_path.append(round(float(est_open * (1.0 + r_scaled)), 2))
            else:
                if med_path:
                    r_scaled = float(np.clip(last_valid_r * amp_scale, -max_r_cap, max_r_cap))
                    med_path.append(round(float(est_open * (1.0 + r_scaled)), 2))
                else:
                    med_path.append(None)
        premarket_medoid = {
            "date": best_ds,
            "gap_pct": best_gap,
            "amp_scale": round(amp_scale, 2),
            "data": med_path,
            "mode": "PREMARKET",
        }

    knn_match = {"matched_dates": [], "mean_dist": None, "knn_rel_moves": {}, "knn_q10": {}, "knn_q90": {}, "analog_paths": []}
    atr_norm_pct = max(vol_cls["atr_pct"] / 100.0, 0.005)
    if has_actual and last_act_idx >= 2 and use_maps:
        valid_slots = [slots[i] for i in range(last_act_idx + 1) if actual_arr[i] is not None]
        if len(valid_slots) >= 3:
            first_px = actual_map[valid_slots[0]]
            today_gap_now = (first_px - prev_px) / max(prev_px, 1e-4) * 100.0
            today_raw_rets = []
            for sl in valid_slots:
                r_raw_today = (actual_map[sl] - first_px) / max(first_px, 1e-4)
                if has_bench_5m and sl in bench_today_rmap:
                    r_raw_today = r_raw_today - bench_beta_5m * bench_today_rmap[sl]
                today_raw_rets.append(r_raw_today)
            today_vec = np.array(today_raw_rets, dtype=float) / atr_norm_pct
            today_norm = float(np.linalg.norm(today_vec))
            cands = []
            for ds, rm, vm, d_gap, d_rng in zip(rdates, use_maps, vmaps, day_gaps_hist, day_ranges_hist):
                if all(sl in rm for sl in valid_slots):
                    hist_vec = np.array([rm[sl] for sl in valid_slots], dtype=float) / atr_norm_pct
                    hist_norm = float(np.linalg.norm(hist_vec))
                    if today_norm > 1e-6 and hist_norm > 1e-6:
                        cos_sim = float(np.dot(today_vec, hist_vec) / (today_norm * hist_norm))
                    else:
                        cos_sim = 1.0 - min(float(np.linalg.norm(today_vec - hist_vec)), 1.0)
                    cos_dist = (1.0 - cos_sim) * 0.5

                    rvol_pen = 0.0
                    if rvol is not None and rvol > 0:
                        hist_v_sum = sum(vm.get(sl, 0.0) for sl in valid_slots)
                        avg_v_sum = sum(float(slot_vols[slots.index(sl)]) for sl in valid_slots)
                        if avg_v_sum > 0:
                            hist_rvol = hist_v_sum / avg_v_sum
                            rvol_pen = min(abs(math.log(max(rvol, 0.1) / max(hist_rvol, 0.1))) * 0.18, 0.35)

                    gap_pen = 0.0
                    if abs(today_gap_now) >= 0.25:
                        if today_gap_now * d_gap < 0:
                            gap_pen = 0.22
                        elif abs(today_gap_now - d_gap) <= 0.6:
                            gap_pen = -0.06

                    comp_dist = max(0.001, cos_dist + rvol_pen + gap_pen)
                    cands.append((comp_dist, ds, rm, d_gap, d_rng))

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
                    for (_, _, rm_k, _, d_rng_k), wk in zip(top_k, w_knn):
                        if sl in rm_k and anchor_sl in rm_k:
                            amp_k = float(np.clip(target_atr / max(float(d_rng_k), 0.5), 0.35, 1.35))
                            rel_s = float(np.clip((rm_k[sl] - rm_k[anchor_sl]) * amp_k, -max_r_cap, max_r_cap))
                            vals_i.append(rel_s)
                            ws_i.append(wk)
                    if vals_i:
                        ws_arr = np.array(ws_i) / np.sum(ws_i)
                        va_arr = np.array(vals_i)
                        knn_rel[i] = float(np.sum(ws_arr * va_arr))
                        knn_q10_m[i] = float(np.min(va_arr))
                        knn_q90_m[i] = float(np.max(va_arr))

                analog_paths = []
                for rank_idx, (_, ds_k, rm_k, dg_k, d_rng_k) in enumerate(top_k):
                    if anchor_sl not in rm_k:
                        continue
                    amp_scale_k = float(np.clip(target_atr / max(float(d_rng_k), 0.5), 0.35, 1.35))
                    path_arr = [None] * n_slots
                    for i in range(last_act_idx, n_slots):
                        sl = slots[i]
                        if sl in rm_k:
                            rel_d_scaled = float(np.clip((rm_k[sl] - rm_k[anchor_sl]) * amp_scale_k, -max_r_cap, max_r_cap))
                            path_arr[i] = round(float(anchor_px_now * (1.0 + rel_d_scaled)), 2)
                    analog_paths.append({
                        "date": ds_k,
                        "gap_pct": round(float(dg_k), 2),
                        "amp_scale": round(amp_scale_k, 2),
                        "data": path_arr,
                    })

                knn_match = {
                    "matched_dates": [c[1] for c in top_k],
                    "mean_dist": round(float(np.mean(dists)), 4),
                    "knn_rel_moves": knn_rel,
                    "knn_q10": knn_q10_m,
                    "knn_q90": knn_q90_m,
                    "analog_paths": analog_paths,
                }

    if has_actual and knn_match["analog_paths"]:
        top1_ap = knn_match["analog_paths"][0]
        medoid_analog = {
            "date": top1_ap["date"],
            "gap_pct": top1_ap.get("gap_pct", 0.0),
            "amp_scale": top1_ap.get("amp_scale", 1.0),
            "data": top1_ap["data"],
            "mode": "INTRADAY_KNN",
        }
    else:
        medoid_analog = premarket_medoid

    live_vwap_bias = 0.0
    bench_live_alpha_adj = 0.0
    mom_30m = 0.0
    cur_vwap_last = None
    lunch_gap_adj_pct = 0.0

    if has_actual and last_act_idx >= 0:
        live_p50, live_p85, live_p15, live_bdiff = [None] * n_slots, [None] * n_slots, [None] * n_slots, [None] * n_slots
        live_p32, live_bdiff_in = [None] * n_slots, [None] * n_slots
        anchor_px = actual_arr[last_act_idx]
        anchor_mean = slot_means[last_act_idx]
        cur_vwap = vwap_arr[last_act_idx] or anchor_px
        cur_vwap_last = cur_vwap
        vwap_gap = (anchor_px - cur_vwap) / max(cur_vwap, 1e-4)

        recent_vals = [v for v in actual_arr[max(0, last_act_idx - 6):last_act_idx + 1] if v is not None]
        mom_30m = ((recent_vals[-1] - recent_vals[0]) / max(recent_vals[0], 1e-4)) if len(recent_vals) >= 2 else 0.0
        gap15_bias = float(gap_open15.get("bias", 0.0))

        if has_bench_5m and bench_today_rmap:
            b_today_vals = [bench_today_rmap[slots[k]] for k in range(last_act_idx + 1) if slots[k] in bench_today_rmap]
            if len(b_today_vals) >= 2:
                b_mom_now = b_today_vals[-1] - b_today_vals[max(0, len(b_today_vals) - 6)]
                bench_live_alpha_adj = float(np.clip(bench_beta_5m * b_mom_now * 0.45, -0.012, 0.012))

        lunch_gap_ratio = 0.0
        if is_jp and lunch_idx is not None and last_act_idx == lunch_idx:
            nk_d = float(macro_data.get("NK_FUT", {}).get("diff_pct", 0.0))
            fx_d = float(macro_data.get("USDJPY", {}).get("diff_pct", 0.0))
            nk_b = float(smap.get("NK_FUT", {}).get("beta", mi.get("beta", 0.5)))
            fx_b = float(fi.get("beta", 0.0))
            raw_lg = (nk_d * nk_b * 0.35 + fx_d * fx_b * 0.35)
            lunch_gap_pct = float(np.clip(raw_lg, -0.8, 0.8))
            lunch_gap_adj_pct = round(lunch_gap_pct, 2)
            lunch_gap_ratio = lunch_gap_pct / 100.0

        bias_cap = 0.045 if expansion_reg["active"] else 0.020
        drift_eff = float(np.clip(drift, -0.055, 0.055)) if expansion_reg["active"] else float(np.clip(drift, -0.032, 0.032))
        unconf_boost = (0.008 if exp_dir == "UP" else (-0.008 if exp_dir == "DOWN" else 0.0)) if expansion_reg.get("unconfirmed_catalyst") else 0.0

        live_vwap_bias = float(np.clip(vwap_gap * 0.45 + mom_30m * 0.35 + gap15_bias + bench_live_alpha_adj + unconf_boost, -bias_cap, bias_cap))
        knn_moves = knn_match["knn_rel_moves"]
        knn_q10_m = knn_match["knn_q10"]
        knn_q90_m = knn_match["knn_q90"]

        v_anchor = float(vol_frac[last_act_idx])
        v_rem_denom = max(1.0 - v_anchor, 1e-4)

        for i in range(last_act_idx, n_slots):
            rem_v_frac = float(np.clip((vol_frac[i] - v_anchor) / v_rem_denom, 0.0, 1.0)) if i > last_act_idx else 0.0
            pm_shift = lunch_gap_ratio if (pm_open_idx is not None and i >= pm_open_idx) else 0.0
            base_rel = (slot_means[i] - anchor_mean) + (drift_eff * 0.6 + live_vwap_bias) * rem_v_frac + pm_shift
            knn_wt = 0.15 if expansion_reg["active"] else 0.30
            rel_move = ((1.0 - knn_wt) * base_rel + knn_wt * (knn_moves[i] + pm_shift)) if (i in knn_moves) else base_rel
            mid = anchor_px * (1.0 + rel_move)
            mid = _apply_hvn_ob_bounce(mid, anchor_px, hvn_wall_px, ob_sup_px, vp, exp_dir=exp_dir)

            if i == last_act_idx:
                u_step_sig = 0.0012
            else:
                u_step_sig = float(np.sqrt(np.sum(eff_slot_inc_stds[last_act_idx + 1:i + 1] ** 2)))

            skew_up = max((slot_q90[i] - slot_means[i]) / max(slot_stds[i], 1e-4), 0.75)
            skew_dn = max((slot_means[i] - slot_q10[i]) / max(slot_stds[i], 1e-4), 0.75)
            up_band = anchor_px * max(u_step_sig * skew_up * vboost, 0.0015)
            dn_band = anchor_px * max(u_step_sig * skew_dn * vboost, 0.0015)

            if i in knn_q90_m and i in knn_q10_m:
                knn_hi_px = anchor_px * (1.0 + knn_q90_m[i] + pm_shift)
                knn_lo_px = anchor_px * (1.0 + knn_q10_m[i] + pm_shift)
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
        drift_eff = drift
        live_p50, live_p85, live_p15, live_bdiff = p50, p85, p15, bdiff
        live_p32, live_bdiff_in = p32, bdiff_inner

    rem_drift_pct = ((drift_eff * 0.6 + live_vwap_bias) * rem_frac_now + (lunch_gap_adj_pct / 100.0)) if has_actual else drift_eff

    verify_stats = {"has_verify": False, "in_cone_pct": 0.0, "err_pct": 0.0, "n_pts": 0, "finalized": False}
    if has_actual and is_locked:
        in_c, errs = 0, []
        for a, lo, hi, m in zip(actual_arr, locked_p15, locked_p85, locked_p50):
            if a is not None:
                if lo <= a <= hi:
                    in_c += 1
                errs.append(abs(a - m) / max(m, 1e-4) * 100.0)
        if errs:
            is_session_final = bool(len(errs) >= int(n_slots * 0.80))
            verify_stats = {
                "has_verify": True,
                "in_cone_pct": round(in_c / len(errs) * 100.0, 1),
                "err_pct": round(float(np.mean(errs)), 2),
                "n_pts": len(errs),
                "finalized": is_session_final,
            }
            if is_session_final and isinstance(saved_today, dict):
                saved_today["verify_result"] = {
                    "in_cone_pct": verify_stats["in_cone_pct"],
                    "err_pct": verify_stats["err_pct"],
                    "rvol_hi": bool(rvol is not None and rvol >= 1.3),
                    "finalized": True,
                }
                stock_hist[market_today_str] = saved_today
                ledger[fc_code] = stock_hist
                _dd_db_set("dd_forecast_ledger_v9", ledger)

    meta_audit = _audit_meta_labeling_accuracy(ledger, fc_code, is_jp, regime_code, rvol, tot_gap)
    verify_hist_15 = _extract_ledger_verify_history(ledger, is_jp)

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

    imin_lk, imax_lk = int(np.argmin(locked_p50)), int(np.argmax(locked_p50))
    locked_trig_idx = min(3, n_slots - 1)

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
        "actual_vols": actual_vols_arr, "actual_dirs": actual_dirs_arr, "cvd_arr": cvd_arr,
        "actual": actual_arr, "vwap": vwap_arr,
        "vwap_p1": vwap_p1_arr, "vwap_m1": vwap_m1_arr, "vwap_p2": vwap_p2_arr, "vwap_m2": vwap_m2_arr,
        "rvol": rvol, "orb_high": orb_high, "orb_low": orb_low, "vol_spikes": vol_spikes,
        "avg_5m_vol": avg_5m_vol, "cvd_div": cvd_div, "gap_open15": gap_open15,
        "expansion_regime": expansion_reg,
        "gap_fill": gap_fill_stats, "rem_sigma_pct": rem_sigma_pct, "rem_drift_pct": rem_drift_pct, "rem_frac_now": rem_frac_now,
        "locked_p50": locked_p50, "locked_p85": locked_p85, "locked_p15": locked_p15, "locked_bdiff": locked_bdiff,
        "locked_p32": locked_p32, "locked_bdiff_in": locked_bdiff_in,
        "live_p50": live_p50, "live_p85": live_p85, "live_p15": live_p15, "live_bdiff": live_bdiff,
        "live_p32": live_p32, "live_bdiff_in": live_bdiff_in,
        "est_open_px": round(est_open, 2), "est_open_gap_pct": round(tot_gap, 2),
        "locked_close_px": locked_p50[-1],
        "locked_close_chg": round((locked_p50[-1] - anchor_base_close) / max(anchor_base_close, 1e-4) * 100.0, 2),
        "locked_dip_idx": imin_lk, "locked_dip_time": slots[imin_lk], "locked_dip_px": locked_p50[imin_lk],
        "locked_peak_idx": imax_lk, "locked_peak_time": slots[imax_lk], "locked_peak_px": locked_p50[imax_lk],
        "locked_bull_trig": round(locked_p85[locked_trig_idx], 2), "locked_bull_target": round(max(locked_p85), 2),
        "locked_bear_trig": round(locked_p15[locked_trig_idx], 2), "locked_bear_target": round(min(locked_p15), 2),
        "live_close_px": lv_close_px,
        "live_close_chg": round((lv_close_px - anchor_base_close) / max(anchor_base_close, 1e-4) * 100.0, 2),
        "live_dip_idx": imin_lv, "live_dip_time": slots[imin_lv], "live_dip_px": live_p50[imin_lv],
        "live_peak_idx": imax_lv, "live_peak_time": slots[imax_lv], "live_peak_px": live_p50[imax_lv],
        "live_bull_trig": lv_bull_trig, "live_bull_target": lv_bull_tgt,
        "live_bear_trig": lv_bear_trig, "live_bear_target": lv_bear_tgt,
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
        "verify": verify_stats, "verify_hist_15": verify_hist_15, "meta_audit": meta_audit, "regime_tag": regime_tag,
        "has_bench_5m": has_bench_5m, "bench_beta_5m": round(bench_beta_5m, 2),
        "vol_clock_active": vol_clock_active,
        "lunch_jump_std_pct": lunch_jump_std_pct,
        "lunch_gap_adj_pct": lunch_gap_adj_pct,
        "ml_3way_model": ml_3way_model,
        "lab_mods": {
            "has_lab": bool(mods.get("has_lab", False)),
            "lab_trust_mult": lab_trust_mult,
            "vpin_vboost": vpin_vboost,
            "vpin_val": mods.get("vpin_val"),
            "kyle_val": mods.get("kyle_val"),
            "rs_30m": lab_rs30,
            "council_caution": bool(mods.get("council_caution", False)),
        },
        "medoid_analog": medoid_analog,
        "high_vol_zones": high_vol_zones,
        "vol_profile_meta": vol_profile_meta,
        "short_3way_ctx": {
            "anchor_px": actual_arr[last_act_idx] if (has_actual and last_act_idx >= 0) else 0.0,
            "cur_vwap": cur_vwap_last,
            "mom_30m": mom_30m,
            "bench_live_alpha_adj": bench_live_alpha_adj,
            "knn_rel_moves": knn_match["knn_rel_moves"],
            "slot_means": slot_means,
            "slot_inc_stds": eff_slot_inc_stds,
            "vboost": vboost,
            "hvn_wall_px": hvn_wall_px,
            "ob_sup_px": ob_sup_px,
            "cum_cvd_now": cum_cvd_latest,
            "cum_vol_now": cum_vol_latest,
            "lab_dir_score": lab_strength_dir,
            "lab_rs30": lab_rs30,
            "exp_dir": exp_dir,
        },
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
# =========================================================================
# 7. 実測5軸レーダー・AIメモ生成（If-Thenプレイブック内蔵）・LAB共有解決
# =========================================================================
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


def _render_valuation_gauges(info: dict, is_jp: bool):
    """取得可能なバリュエーション・ポジション指標を横型ミニゲージで表示"""
    gauges = []

    pe = info.get("trailingPE")
    if pe is not None and float(pe) > 0:
        pe_v = float(pe)
        pct_p = float(np.clip((pe_v / 60.0) * 100.0, 4.0, 100.0))
        col_p = "#10b981" if pe_v <= 18 else ("#38bdf8" if pe_v <= 32 else "#f59e0b")
        gauges.append(("PER (実績)", f"{pe_v:.1f}倍", pct_p, col_p, "低PERほど割安目安"))

    pb = info.get("priceToBook")
    if pb is not None and float(pb) > 0:
        pb_v = float(pb)
        pct_b = float(np.clip((pb_v / 10.0) * 100.0, 4.0, 100.0))
        col_b = "#10b981" if pb_v <= 1.5 else ("#38bdf8" if pb_v <= 4.0 else "#f59e0b")
        gauges.append(("PBR", f"{pb_v:.2f}倍", pct_b, col_b, "1.0倍近辺が解散価値目安"))

    dy = info.get("dividendYield")
    if dy is not None and float(dy) > 0:
        dy_v = float(dy) * 100.0 if float(dy) <= 0.25 else float(dy)
        pct_d = float(np.clip((dy_v / 6.0) * 100.0, 5.0, 100.0))
        gauges.append(("配当利回り", f"{dy_v:.2f}%", pct_d, "#10b981", "インカム下支え水準"))

    sf = info.get("shortPercentOfFloat")
    if sf is not None and float(sf) > 0:
        sf_v = float(sf) * 100.0 if float(sf) <= 1.0 else float(sf)
        pct_s = float(np.clip((sf_v / 25.0) * 100.0, 5.0, 100.0))
        col_s = "#ef4444" if sf_v >= 12.0 else ("#f59e0b" if sf_v >= 5.0 else "#38bdf8")
        gauges.append(("空売り比率 (Float)", f"{sf_v:.1f}%", pct_s, col_s, "高水準は踏み上げ燃料候補"))

    hi = info.get("heldPercentInstitutions")
    if hi is not None and float(hi) > 0:
        hi_v = float(hi) * 100.0 if float(hi) <= 1.0 else float(hi)
        pct_i = float(np.clip(hi_v, 5.0, 100.0))
        gauges.append(("機関投資家保有率", f"{hi_v:.1f}%", pct_i, "#c084fc", "大口フロー影響度"))

    if not gauges:
        return
    cards = []
    for lbl_g, val_g, pct_g, col_g, sub_g in gauges:
        cards.append(
            f'<div class="dd-val-card">'
            f'<div style="display:flex;justify-content:space-between;align-items:baseline;">'
            f'<span style="font-size:10.5px;font-weight:700;color:#cbd5e1;">{html.escape(lbl_g)}</span>'
            f'<span style="font-family:JetBrains Mono,monospace;font-size:12px;font-weight:800;color:{col_g};">{html.escape(val_g)}</span></div>'
            f'<div class="dd-val-track"><div class="dd-val-fill" style="width:{pct_g:.1f}%;background:{col_g};"></div></div>'
            f'<div style="font-size:9px;color:#94a3b8;margin-top:3px;">{html.escape(sub_g)}</div></div>'
        )
    st.markdown(f'<div class="dd-val-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


@st.cache_data(ttl=900, show_spinner=False)
def _generate_detailed_memo_cached(
    fc: str, corp_name: str, px_s: str, traj_open: str, traj_close: str,
    bull_trig: str, bull_tgt: str, bear_trig: str, bear_tgt: str,
    dip_t: str, peak_t: str, ovh: float, res_s: str, sup_s: str,
    ml: str, mc: float, mb: float, pos_pct: int, t1: int, gov_cnt: int,
    whale_sum: str, up: str, lab_note: str, api_key: str,
    lab_deep_ctx: str = "", trade_style: str = "デイトレード", memo_nonce: int = 0
) -> tuple:
    lab_block = f"\n・LAB本体統合データ: {lab_deep_ctx}" if lab_deep_ctx else ""
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
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent"
                body = json.dumps({"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": 1500, "temperature": 0.6}}).encode("utf-8")
                req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "x-goog-api-key": api_key}, method="POST")
                with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=12.0) as r:
                    rj = json.loads(r.read().decode("utf-8"))
                    txt = "".join([p.get("text", "") for p in rj["candidates"][0]["content"]["parts"] if "text" in p])
                    if txt.strip():
                        return txt.strip(), f"🔵 AUTO GLOBAL AI ANALYST ({mod} / {trade_style} / 一次報道{t1}件)"
            except Exception:
                continue

    if trade_style == "スキャルピング":
        pb_atk = f"・【攻め】IF {bull_trig} 超えまたはVWAP上での9EMA反発＋出来高急増 → THEN 短期回転でエントリーし {bull_tgt} 手前で分割利確"
        pb_def = f"・【守り】IF 直近安値割れまたは {bear_trig} 割れ・5分以上ヨコヨコ失速 → THEN 建値〜浅い逆指値で即撤退"
        pb_alt = f"・【警戒】IF 想定外急騰・{ml} 急変や速報材料発生 → THEN 朝想定を破棄しトレンド追従・ロット半減へ切替"
    elif trade_style == "スイングトレード":
        pb_atk = f"・【攻め】IF 押し目帯({dip_t}前後)や支持帯({sup_s})反発・{bull_trig} 上抜け定着 → THEN 数日〜数週ホールドで {bull_tgt} 目標"
        pb_def = f"・【守り】IF 日足終値ベースで {bear_trig} 割れまたはしこり壁({res_s})手前での上ヒゲ連発 → THEN ルール損切り・ポジション縮小"
        pb_alt = f"・【警戒】IF 決算接近・{ml}({mc})のレジーム転換 → THEN 保有比率を調整しイベントリスクを回避"
    elif trade_style == "バイ＆ホールド":
        pb_atk = f"・【攻め】IF 調整局面({dip_t}前後・{sup_s}付近)や業績拡大確認 → THEN 段階的な買い増しで中長期成長を取り込む"
        pb_def = f"・【守り】IF ガバナンス悪化({gov_cnt}件)やファンダメンタルズ毀損・{bear_trig} 大幅割れ → THEN 保有方針を再点検し一部撤退"
        pb_alt = f"・【警戒】IF {ml}(β={mb})のトレンド反転や金利・為替急変 → THEN 過熱銘柄の利確リバランスを実施"
    else:
        pb_atk = f"・【攻め】IF {bull_trig} 突破または {dip_t} 付近でのVWAP反発 → THEN 当日トレンドに乗せて {bull_tgt} を目指す"
        pb_def = f"・【守り】IF {bear_trig} 割れまたは大引け接近時の停滞 → THEN 翌日持ち越しを避け {bear_tgt} 警戒で即損切り・手仕舞い"
        pb_alt = f"・【警戒】IF 想定外ブレイクや {ml}({mc})急変 → THEN 逆張り停止・ブレイク追従モードへ切替"

    playbook = f"🎯 If-Then 執行プレイブック（{trade_style}）\n{pb_atk}\n{pb_def}\n{pb_alt}"
    lab_extra = f"\n・LAB連携情報: {lab_deep_ctx}" if lab_deep_ctx else ""
    bull = f"・LAB本体判定: {lab_note}{lab_extra}。現在値 {px_s} に対しアナリスト目標乖離は {up}、高信頼ニュース強気度 {pos_pct}%（一次報道{t1}件）。\n・{bull_trig} を明確に上抜ければ強気突破が発動し、上値メド {bull_tgt} を目指す展開。\n・下値は大口買い支え帯 {sup_s} をサポートとして機能しやすい構造。"
    bear = f"・{ml} との相関係数が {mc}（β={mb}）で、夜間先物や米市場の急変時に連れ安リスクあり。\n・上値しこり玉は {ovh}%、直上の大口売り壁 {res_s} 付近では戻り売りに要注意。\n・{bear_trig} 割れで下値メド {bear_tgt} までの下振れを警戒し早期撤退。ガバナンス報道は {gov_cnt}件検知。"
    cat = f"・大口・インサイダー動向: {whale_sum}。\n・勝負時間帯は押し目候補の {dip_t} 前後での反発確認と、ピーク想定の {peak_t} 前後での分割利確。\n・寄付直後に想定始値 {traj_open} を維持できるかが最初の分岐点。"
    full_memo = f"{playbook}\n\n🟢 Bull Case（強気シナリオ）\n{bull}\n\n🔴 Bear Case（弱気・死角リスク）\n{bear}\n\n⚡ Next Catalyst（注目トリガー）\n{cat}"
    return full_memo, f"⚙️ AUTO QUANT MEMO（{trade_style} / 一次報道{t1}件・実測詳細生成）"


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
    <b>🔰 v18.0 クオンツ＆プロ端末ガイド</b><br>
    1. <b>メイン軌道＆1分足ズーム:</b> 5分足1日軌道と1分足90分ズームを切替可能。拡大範囲は自動保持され、右上「↺」で初期表示へ戻せます。拡大精査中は「自動更新」をOFFにするとフルスクリーンが維持されます。<br>
    2. <b>タブ2（マクロβ・曜日）:</b> 曜日×30分時間帯の期待値ヒートマップ、20日/60日ローリング相関＆ダイナミックβ、決算翌日のPEADドリフトを表示。<br>
    3. <b>タブ3（財務・大口株主）:</b> 28分割のVA70%/POC出来高プロファイル（短期20日vs中期60日減衰）、BBWボラティリティ・スクイーズ、インサイダー売買プロット、バリュエーション横型ゲージを表示。<br>
    4. <b>タブ4（リスク・AIメモ）:</b> スタイル別If-Then執行プレイブック内蔵AIメモ、72時間ニュース密度タイムライン、クラスタSGD重み比較＆直近15日検証精度推移を表示。
    </div>
    """, unsafe_allow_html=True)


# =========================================================================
# 8. メインエントリ関数（YAMASHISHI DEEP DIVE v18.0）
# =========================================================================
def render_deep_dive_page(init_code: str = "NVDA", init_style: str = "デイトレード", gemini_api_key: str = "", lab_ctx: dict = None):
    _inject_dd_css()

    # 上部コマンドドック（スリム＆高視認性統合ヘッダー）
    h1, h2, h3 = st.columns([2.6, 0.9, 1.1])
    with h1:
        st.markdown(
            '<div class="dd-cmd-header">'
            '<div style="min-width:0;">'
            '<div class="dd-cmd-title">YAMASHISHI DEEP DIVE v18.0</div>'
            '<div class="dd-cmd-sub">Retina 60fps軌道・衝突回避MarkLine・2段CVD・28分割VA・SGD自己進化</div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True
        )
    with h2:
        if hasattr(st, "popover"):
            with st.popover("📖 見方", use_container_width=True):
                _render_unified_guide()
        else:
            with st.expander("📖 見方"):
                _render_unified_guide()
    with h3:
        if st.button("⬅️ LAB", key="dd_back_to_lab_btn", use_container_width=True, type="primary"):
            st.session_state["navigation_page"] = "TOP"
            st.session_state["scroll_top_trig"] = int(time.time() * 1000)
            st.rerun()

    STYLES = ["デイトレード", "スキャルピング", "スイングトレード", "バイ＆ホールド"]
    c1, c2, c3 = st.columns([1.8, 1.5, 1.0])
    in_code = c1.text_input("銘柄コード", value=init_code, placeholder="例: NVDA / 6920", label_visibility="collapsed", key="dd_code_in")
    in_style = c2.selectbox("スタイル", STYLES, index=STYLES.index(init_style) if init_style in STYLES else 0, label_visibility="collapsed", key="dd_style_in")
    auto_sync = c3.toggle("自動更新", value=True, key="dd_auto_sync", help="ONで60秒ごとに最新データへ自動同期（拡大精査時はOFF推奨）")

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
    lab_mods = _extract_lab_quant_modifiers(active_lab, lab_council)

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
            chip_parts = []
            for k in ["SOX", "SP500", "NQ_FUT", "ES_FUT", "NK_FUT", "USDJPY", "US10Y", "OIL", "VIX"]:
                if k in macro_data:
                    m_item = macro_data[k]
                    rt_mark = "⚡" if m_item.get("is_rt") else ""
                    m_col = "#10b981" if m_item["diff_pct"] >= 0 else "#ef4444"
                    chip_parts.append(
                        f'<div class="dd-macro-chip"><span style="color:#64748b;">{m_item["label"]}{rt_mark}</span>'
                        f'<span style="color:{m_col};font-weight:700;">{m_item["diff_pct"]:+.2f}%</span></div>'
                    )
            st.markdown(f'<div class="dd-macro-strip">{"".join(chip_parts)}</div>', unsafe_allow_html=True)

        df_1d, df_5m, df_1m, info = data["df_1d"], data["df_5m"], data.get("df_1m", pd.DataFrame()), data["info"]
        if df_1d is None or df_1d.empty:
            st.error(f"❌ 銘柄コード `{fc}` の市場データを取得できませんでした。")
            return

        corp_name = info.get("longName") or info.get("shortName") or fc
        short_code = fc.replace(".T", "")
        sector, industry = info.get("sector") or "セクター未分類", info.get("industry") or "-"

        market_today_str = _get_market_now(is_jp).strftime("%Y-%m-%d")
        last_1d_str = df_1d.index[-1].strftime("%Y-%m-%d") if hasattr(df_1d.index[-1], "strftime") else str(df_1d.index[-1])[:10]
        curr_px_1d = float(df_1d["Close"].iloc[-1])
        if last_1d_str == market_today_str:
            prev_px = float(df_1d["Close"].iloc[-2]) if len(df_1d) >= 2 else curr_px_1d
        else:
            prev_px = curr_px_1d

        curr_px_rt = curr_px_1d
        if df_5m is not None and not df_5m.empty:
            tmp_now_5m = df_5m.copy()
            idx_now_5m = _convert_5m_index_to_market_tz(tmp_now_5m, is_jp)
            tmp_now_5m["_d"] = idx_now_5m.strftime("%Y-%m-%d")
            sub_now_today = tmp_now_5m[tmp_now_5m["_d"] == market_today_str]
            if not sub_now_today.empty:
                last_5m_c = float(sub_now_today["Close"].iloc[-1])
                if last_5m_c > 0:
                    curr_px_rt = round(last_5m_c, 2)

        mkt_regime = _detect_market_regime(df_1d)
        macro_sens = _compute_macro_sens(df_1d["Close"], macro_data)
        dow_stats, next_wd = _compute_dow_edge(df_1d, is_jp)
        with ThreadPoolExecutor(max_workers=2) as ex_intel:
            fut_news = ex_intel.submit(_fetch_global_intel, corp_name, short_code, fc)
            fut_gov = ex_intel.submit(_fetch_gov_and_whales, corp_name, short_code, is_jp)
            news_res = fut_news.result()
            gov_risks, whale_news = fut_gov.result()
        whale_anom = _detect_whale_anomaly(data["insider_tx"], whale_news, market_today_str)
        vp = _compute_vp(df_1d, curr_px_rt, is_jp)
        traj = _build_dual_5m_trajectory(
            fc, curr_px_rt, prev_px, df_1d, df_5m, macro_sens, macro_data,
            news_res, whale_anom, dow_stats[next_wd]["avg"], vp, is_jp,
            mkt_regime=mkt_regime, active_lab=active_lab, df_bench_5m=df_bench_5m,
            lab_mods=lab_mods
        )

        if traj["has_actual"] and traj["last_act_idx"] >= 0 and traj["actual"][traj["last_act_idx"]] is not None:
            curr_px = float(traj["actual"][traj["last_act_idx"]])
        else:
            curr_px = curr_px_rt

        round_level = _compute_round_number_level(curr_px, is_jp)
        ref_levels = _compute_pro_ref_levels(df_1d, df_5m, is_jp, market_today_str)
        mtf_res = _compute_mtf_alignment(df_1m, df_5m, df_1d, is_jp)

        chg_pct = ((curr_px - prev_px) / max(prev_px, 1e-4)) * 100.0
        chg_col = "#10b981" if chg_pct >= 0 else "#ef4444"

        exp_reg = traj.get("expansion_regime") or {"active": False, "dir": "NONE", "reasons": [], "label": "通常レジーム"}
        exp_active = bool(exp_reg.get("active"))
        exp_dir = exp_reg.get("dir", "NONE")

        presets = ["📈 今の予測", "🔍 朝の答え合わせ", "🏦 大口・節目"]
        modes = ["🔴 ライブ修正", "🔒 朝ロック検証", "⚡ 両方重ね"]
        sel_preset_now = st.session_state.get("dd_preset_sel", "📈 今の予測")
        cur_chart_mode = st.session_state.get("dd_chart_mode", "⚡ 両方重ね")
        if st.session_state.get("dd_last_preset") != sel_preset_now:
            cur_chart_mode = modes[2 if sel_preset_now == "📈 今の予測" else (1 if sel_preset_now == "🔍 朝の答え合わせ" else 0)]

        use_live_basis = bool(traj["has_actual"] and cur_chart_mode in ("🔴 ライブ修正", "⚡ 両方重ね"))

        wi_idx_key = f"dd_whatif_idx_{fc}"
        wi_fx_key = f"dd_whatif_fx_{fc}"
        shock_idx_pct = float(st.session_state.get(wi_idx_key, 0.0))
        shock_fx_yen = float(st.session_state.get(wi_fx_key, 0.0))
        usdjpy_last = float(macro_data.get("USDJPY", {}).get("last", 150.0) or 150.0)
        shock_fx_pct = (shock_fx_yen / max(usdjpy_last, 1.0)) * 100.0

        f_map = traj["factors"]
        mkt_beta_eff = float(f_map.get("mkt_beta", 0.5))
        fx_beta_eff = float(f_map.get("fx_beta", 0.0))
        shock_ext_pct = round(shock_idx_pct * mkt_beta_eff + shock_fx_pct * fx_beta_eff, 3)
        shock_mult = 1.0 + (shock_ext_pct / 100.0)

        n_sl_tot = len(traj["slots"])
        la_idx = traj["last_act_idx"]

        def _scale_live_arr(arr_in):
            if not traj["has_actual"] or la_idx < 0:
                return [round(v * shock_mult, 2) if v is not None else None for v in arr_in]
            out_a = []
            denom_rem = max(n_sl_tot - 1 - la_idx, 1)
            for idx_s, val_s in enumerate(arr_in):
                if val_s is None:
                    out_a.append(None)
                elif idx_s <= la_idx:
                    out_a.append(round(float(val_s), 2))
                else:
                    w_rem = (idx_s - la_idx) / denom_rem
                    out_a.append(round(float(val_s) * (1.0 + (shock_ext_pct / 100.0) * w_rem), 2))
            return out_a

        disp_locked_p50 = list(traj["locked_p50"])
        disp_locked_p85 = list(traj["locked_p85"])
        disp_locked_p15 = list(traj["locked_p15"])
        disp_locked_bdiff = list(traj["locked_bdiff"])
        disp_locked_p32 = list(traj["locked_p32"])
        disp_locked_bdiff_in = list(traj["locked_bdiff_in"])

        if use_live_basis:
            active_close_px = round(traj["live_close_px"] * shock_mult, 2)
            active_close_chg = round((active_close_px - traj["anchor_base_close"]) / max(traj["anchor_base_close"], 1e-4) * 100.0, 2)
            active_bull_trig = round(traj["live_bull_trig"] * shock_mult, 2)
            active_bull_tgt = round(traj["live_bull_target"] * shock_mult, 2)
            active_bear_trig = round(traj["live_bear_trig"] * shock_mult, 2)
            active_bear_tgt = round(traj["live_bear_target"] * shock_mult, 2)
            active_dip_time = traj["live_dip_time"]
            active_dip_px = round(traj["live_dip_px"] * shock_mult, 2)
            active_peak_time = traj["live_peak_time"]
            active_peak_px = round(traj["live_peak_px"] * shock_mult, 2)
        elif not traj["has_actual"]:
            active_close_px = round(traj["locked_close_px"] * shock_mult, 2)
            active_close_chg = round((active_close_px - traj["anchor_base_close"]) / max(traj["anchor_base_close"], 1e-4) * 100.0, 2)
            active_bull_trig = round(traj["locked_bull_trig"] * shock_mult, 2)
            active_bull_tgt = round(traj["locked_bull_target"] * shock_mult, 2)
            active_bear_trig = round(traj["locked_bear_trig"] * shock_mult, 2)
            active_bear_tgt = round(traj["locked_bear_target"] * shock_mult, 2)
            active_dip_time = traj["locked_dip_time"]
            active_dip_px = round(traj["locked_dip_px"] * shock_mult, 2)
            active_peak_time = traj["locked_peak_time"]
            active_peak_px = round(traj["locked_peak_px"] * shock_mult, 2)
        else:
            active_close_px = round(traj["locked_close_px"], 2)
            active_close_chg = round((active_close_px - traj["anchor_base_close"]) / max(traj["anchor_base_close"], 1e-4) * 100.0, 2)
            active_bull_trig = round(traj["locked_bull_trig"], 2)
            active_bull_tgt = round(traj["locked_bull_target"], 2)
            active_bear_trig = round(traj["locked_bear_trig"], 2)
            active_bear_tgt = round(traj["locked_bear_target"], 2)
            active_dip_time = traj["locked_dip_time"]
            active_dip_px = round(traj["locked_dip_px"], 2)
            active_peak_time = traj["locked_peak_time"]
            active_peak_px = round(traj["locked_peak_px"], 2)

        active_open_gap_pct = round(traj["est_open_gap_pct"] + (shock_ext_pct if not traj["has_actual"] else 0.0), 2)
        active_open_px = round(traj["anchor_base_close"] * (1.0 + active_open_gap_pct / 100.0), 2)
        active_rem_drift = traj["rem_drift_pct"] + (shock_ext_pct / 100.0) * 0.65

        disp_live_p50 = _scale_live_arr(traj["live_p50"])
        disp_live_p85 = _scale_live_arr(traj["live_p85"])
        disp_live_p15 = _scale_live_arr(traj["live_p15"])
        disp_live_bdiff = _scale_live_arr(traj["live_bdiff"])
        disp_live_p32 = _scale_live_arr(traj["live_p32"])
        disp_live_bdiff_in = _scale_live_arr(traj["live_bdiff_in"])

        s3_ctx = traj["short_3way_ctx"]
        short_3way = _compute_short_horizon_3way(
            traj["has_actual"], traj["last_act_idx"], len(traj["slots"]),
            s3_ctx["anchor_px"], s3_ctx["cur_vwap"], s3_ctx["mom_30m"],
            traj["rvol"], traj["cvd_div"], traj["gap_open15"],
            s3_ctx["bench_live_alpha_adj"], s3_ctx["knn_rel_moves"],
            s3_ctx["slot_means"], s3_ctx["slot_inc_stds"], s3_ctx["vboost"],
            s3_ctx["hvn_wall_px"], s3_ctx["ob_sup_px"], vp,
            shock_ext_pct=shock_ext_pct, horizon_slots=6,
            ml_model=traj.get("ml_3way_model"),
            cum_cvd_now=s3_ctx.get("cum_cvd_now", 0.0),
            cum_vol_now=s3_ctx.get("cum_vol_now", 0.0),
            lab_dir_score=s3_ctx.get("lab_dir_score", 0.0),
            lab_rs30=s3_ctx.get("lab_rs30"),
            exp_dir=exp_dir
        )

        cur_vwap_now = traj["vwap"][traj["last_act_idx"]] if (traj["has_actual"] and traj["last_act_idx"] >= 0) else None
        scen_probs = _compute_bayesian_scenario_probs(
            traj["has_actual"], curr_px, traj["anchor_base_close"],
            active_open_gap_pct, active_close_chg,
            active_bull_trig, active_bull_tgt, active_bear_trig, active_bear_tgt,
            traj["rem_sigma_pct"], active_rem_drift,
            traj["rvol"], traj["cvd_div"], traj["gap_open15"],
            cur_vwap_now, shock_ext_pct=shock_ext_pct, exp_dir=exp_dir
        )

        status_pills = []
        alert_blocks = []

        if exp_active:
            if exp_dir == "UP":
                status_pills.append('<span class="dd-st-pill" style="border-color:#10b981;background:rgba(16,185,129,0.20);color:#6ee7b7;">🚀 急騰ブレイク稼働中</span>')
                alert_blocks.append(
                    '<div class="dd-quant-box"><b>🚀 急騰ブレイクモード稼働中（朝想定を自動解除・トレンド追従へ切替）</b><br>'
                    + "<br>".join([f"・{html.escape(r)}" for r in exp_reg["reasons"]])
                    + "</div>"
                )
            else:
                status_pills.append('<span class="dd-st-pill" style="border-color:#ef4444;background:rgba(239,68,68,0.20);color:#fecaca;">🔻 急落ブレイク稼働中</span>')
                alert_blocks.append(
                    '<div class="dd-warn-box"><b>🔻 急落ブレイクモード稼働中（朝想定を自動解除・下落追従へ切替）</b><br>'
                    + "<br>".join([f"・{html.escape(r)}" for r in exp_reg["reasons"]])
                    + "</div>"
                )

        cat_al = news_res.get("catalyst_alert")
        if isinstance(cat_al, dict) and cat_al.get("active"):
            c_col = "#10b981" if cat_al["dir"] == "POS" else "#ef4444"
            c_cls = "dd-quant-box" if cat_al["dir"] == "POS" else "dd-warn-box"
            status_pills.append(f'<span class="dd-st-pill" style="border-color:{c_col};background:rgba(15,23,42,0.88);color:{c_col};">📰 速報材料: {html.escape(cat_al["kw"])}</span>')
            alert_blocks.append(
                f'<div class="{c_cls}"><b>📰 60分以内・特大カタリスト速報検知（{cat_al["age_min"]}分前 / キーワード: {html.escape(cat_al["kw"])}）</b><br>'
                f'{html.escape(cat_al["title"])}（ライブ軌道へ {cat_al["boost_drift_pct"]:+.2f}% 即時反映済）</div>'
            )

        meta_a = traj["meta_audit"]
        meta_hit_str = f" ({meta_a['hit_rate']:.0f}%)" if meta_a["n"] >= 3 else ""
        status_pills.append(
            f'<span class="dd-st-pill" style="border-color:{meta_a["color"]};background:rgba(15,23,42,0.86);color:{meta_a["color"]};">'
            f'🛡️ モデル信頼度: {html.escape(meta_a["rank"])}{meta_hit_str}</span>'
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
            status_pills.append('<span class="dd-st-pill" style="border-color:#ef4444;background:rgba(239,68,68,0.20);color:#fecaca;">🚨 上ヒゲ売り圧力乖離</span>')
            alert_blocks.append(f'<div class="dd-warn-box"><b>🚨 OHLCV疑似CVD 弱気ダイバージェンス検知</b><br>{html.escape(cvd_div["detail"])}</div>')
        elif cvd_div["state"] == "ABSORPTION":
            status_pills.append('<span class="dd-st-pill" style="border-color:#10b981;background:rgba(16,185,129,0.18);color:#6ee7b7;">🧲 下ヒゲ買い支え乖離</span>')
            alert_blocks.append(f'<div class="dd-quant-box"><b>🧲 OHLCV疑似CVD 強気ダイバージェンス検知</b><br>{html.escape(cvd_div["detail"])}</div>')

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
            t_mult_now = traj["lab_mods"]["lab_trust_mult"]
            lab_note = f"LAB判定={l_side} (期待度{active_lab.get('expect_pct',0)}% / 信頼度係数×{t_mult_now:.2f} / TP:{_fmt_cur(l_tp, is_jp)} / SL:{_fmt_cur(l_sl, is_jp)})"
            if is_aligned:
                status_pills.append(f'<span class="dd-st-pill" style="border-color:#10b981;background:rgba(16,185,129,0.16);color:#6ee7b7;">✅ LAB一致({l_side} ×{t_mult_now:.2f})</span>')
                grade_short = html.escape(str(active_lab.get("exec_grade", "")).split("（")[0])
                alert_blocks.append(f'<div class="dd-quant-box"><b>✅ LAB × DEEP DIVE 方向性一致（{l_side} 同期 / 信頼度係数 ×{t_mult_now:.2f}）</b><br>LAB上位足判定（期待度 {active_lab.get("expect_pct",0)}% / {grade_short}）と5分足予測軌道（{active_close_chg:+.2f}%）が一致。TP: <b>{_fmt_cur(l_tp, is_jp)}</b> / SL: <b>{_fmt_cur(l_sl, is_jp)}</b></div>')
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
        aura_glow = "rgba(16,185,129,0.18)" if active_close_chg >= 0 else "rgba(239,68,68,0.18)"
        target_mean = info.get("targetMeanPrice")
        upside_str = f"{((target_mean - curr_px)/curr_px*100):+.1f}%" if (target_mean and curr_px > 0) else "-"
        risk_status, risk_col = (f"⚠️ {len(gov_risks)}件", "#f87171") if gov_risks else ("🟢 クリーン", "#10b981")

        top_close_lbl = "大引け予測(ライブ)" if use_live_basis else "大引け予測(ロック)"
        st.markdown(f"""
        <div class="dd-hero-card" style="border-left-color:{aura_col};box-shadow:0 8px 24px {aura_glow};">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;flex-wrap:wrap;">
            <div style="min-width:0;flex:1;">
              <div><span class="pill-badge">{html.escape(fc)}</span><span class="pill-badge" style="border-color:rgba(168,85,247,0.45);background:rgba(168,85,247,0.16);color:#e9d5ff;">{html.escape(in_style)}</span><span class="pill-badge" style="border-color:{mkt_regime['color']};background:rgba(15,23,42,0.8);color:{mkt_regime['color']};">{mkt_regime['label']}・{traj['weights_evolution']['active_cluster']}</span>{earn_badge}</div>
              <div style="font-size:16.5px;font-weight:800;color:#f8fafc;margin-top:4px;word-break:break-word;">{html.escape(corp_name)}</div>
              <div style="font-size:10.5px;color:#64748b;margin-top:1px;">{html.escape(sector)} / {html.escape(industry)}</div>
            </div>
            <div style="text-align:right;flex-shrink:0;">
              <div style="font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;font-size:19px;font-weight:800;color:#ffffff;">{_fmt_cur(curr_px, is_jp)}</div>
              <div style="font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;font-size:11.5px;font-weight:700;color:{chg_col};margin-bottom:2px;">{chg_pct:+.2f}%</div>
              {spark_svg}
            </div>
          </div>
          <div style="margin-top:6px;">
            <div style="display:flex;justify-content:space-between;font-size:9.3px;color:#64748b;font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;"><span>52W安 {_fmt_cur(lo_52, is_jp)}</span><span style="color:#7dd3fc;">52W位置 {pos_52:.0f}%</span><span>52W高 {_fmt_cur(hi_52, is_jp)}</span></div>
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
            brk = news_res.get("breaking_news")
            if isinstance(brk, dict) and brk.get("title"):
                b_cls = "dd-breaking-ticker bull" if brk.get("sent") == "POS" else "dd-breaking-ticker"
                b_tag = "🔥 速報(買い)" if brk.get("sent") == "POS" else ("⚠️ 速報(売り)" if brk.get("sent") == "NEG" else "⚡ 速報")
                b_url = html.escape(brk.get("link") or "#")
                st.markdown(
                    f'<div class="{b_cls}">'
                    f'<span style="font-weight:800;flex-shrink:0;">{b_tag} [{brk.get("age_min",1)}分前]</span>'
                    f'<a href="{b_url}" target="_blank" style="color:inherit;text-decoration:none;overflow:hidden;text-overflow:ellipsis;">'
                    f'{html.escape(brk["title"])} ({html.escape(brk.get("source") or "速報")})</a></div>',
                    unsafe_allow_html=True
                )

            _render_mtf_and_ladder(mtf_res, curr_px, is_jp, ref_levels, traj, vp, round_level, active_lab)

            # スリムKPIリボン（横スクロール1行集約・縦幅圧縮）
            rvol_v = traj["rvol"]
            rvol_txt, rvol_c = (f"{rvol_v:.2f}x (機関)", "#10b981") if (rvol_v and rvol_v >= 1.8) else ((f"{rvol_v:.2f}x (閑散)", "#f59e0b") if (rvol_v and rvol_v < 0.75) else ((f"{rvol_v:.2f}x (通常)", "#38bdf8") if rvol_v else ("場前待機", "#94a3b8")))
            gf = traj["gap_fill"]
            if gf["prob"] is not None:
                n_gf = int(gf.get("n_samples", 0))
                ref_tag = "参考 " if n_gf < 5 else ""
                gf_txt = f"{ref_tag}{int(gf['prob'])}% ({gf['avg_min']}分/N={n_gf})" if gf["avg_min"] else f"{ref_tag}{int(gf['prob'])}% (N={n_gf})"
                gf_c = "#94a3b8" if n_gf < 5 else ("#10b981" if gf["prob"] >= 60 else ("#f59e0b" if gf["prob"] >= 35 else "#38bdf8"))
            else:
                gf_txt, gf_c = "データ不足", "#94a3b8"
            n_sp = len(traj["vol_spikes"])
            sp_txt = f"{n_sp}回検知 ◆" if n_sp > 0 else "なし"
            sp_col = "#c084fc" if n_sp > 0 else "#94a3b8"

            st.markdown(f"""
            <div class="dd-inst-ribbon">
              <div class="dd-inst-pill-card"><div class="dd-metric-lbl">RVOL 相対出来高</div><div style="font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;font-size:11px;font-weight:800;color:{rvol_c};margin-top:1px;">{rvol_txt}</div></div>
              <div class="dd-inst-pill-card"><div class="dd-metric-lbl">窓埋め率 (1M標本)</div><div style="font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;font-size:11px;font-weight:800;color:{gf_c};margin-top:1px;">{gf_txt}</div></div>
              <div class="dd-inst-pill-card"><div class="dd-metric-lbl">心理的キリ番節目</div><div style="font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;font-size:11px;font-weight:800;color:#fde047;margin-top:1px;">{_fmt_cur(round_level, is_jp)}</div></div>
              <div class="dd-inst-pill-card"><div class="dd-metric-lbl">大口約定スパイク</div><div style="font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;font-size:11px;font-weight:800;color:{sp_col};margin-top:1px;">{sp_txt}</div></div>
              <div class="dd-inst-pill-card"><div class="dd-metric-lbl">OHLCV疑似CVD</div><div style="font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;font-size:11px;font-weight:800;color:{cvd_div['color']};margin-top:1px;">{html.escape(cvd_div['label'])}</div></div>
              <div class="dd-inst-pill-card"><div class="dd-metric-lbl">寄り15分 Gap判定</div><div style="font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;font-size:11px;font-weight:800;color:{g15['color']};margin-top:1px;">{html.escape(g15['label'])}</div></div>
            </div>
            """, unsafe_allow_html=True)

            zoom_1m_payload = _build_1m_zoom_payload(
                df_1m, is_jp, market_today_str, exp_dir=exp_dir,
                hvn_wall_px=f_map.get("hvn_wall_px", 0.0), ob_sup_px=f_map.get("ob_sup_px", 0.0), vp=vp
            )
            tf_opts = ["5分足(1日全体)", "1分足(直近90分ズーム)"]
            if st.session_state.get("dd_last_style_tf") != in_style:
                st.session_state["dd_last_style_tf"] = in_style
                if in_style == "スキャルピング" and zoom_1m_payload.get("valid"):
                    st.session_state["dd_tf_mode"] = "1分足(直近90分ズーム)"
                else:
                    st.session_state["dd_tf_mode"] = "5分足(1日全体)"

            is_short_style = in_style in ("デイトレード", "スキャルピング")
            line_opts = [
                "場中30分・3分岐点線（スコア比%）", "類似実測波形（Top-1）", "高ボラ狩り場帯",
                "予測レンジ帯（ファン）", "類似日スパゲッティ軌道", "転換時間帯ガイド",
                "押目・利確ゾーン", "VWAP", "VWAP±σ",
                "前日/当日高安（PDH/PDL/HOD/LOD）",
                "心理的キリ番節目", "寄り30分高安（ORB）", "大口約定（◆）", "出来高"
            ] + (["LAB TP/SL"] if active_lab else [])

            p_col, tf_col, cfg_col = st.columns([2.2, 1.4, 0.9])
            with p_col:
                if hasattr(st, "pills"):
                    sel_preset = st.pills("表示プリセット", presets, default="📈 今の予測", selection_mode="single", label_visibility="collapsed", key="dd_preset_sel") or "📈 今の予測"
                else:
                    sel_preset = st.radio("表示プリセット", presets, index=0, horizontal=True, label_visibility="collapsed", key="dd_preset_sel")

            with tf_col:
                sel_tf = st.selectbox("表示足", tf_opts, label_visibility="collapsed", key="dd_tf_mode")

            if sel_preset == "📈 今の予測":
                pr_mode_idx = 2
                short_defaults = ["場中30分・3分岐点線（スコア比%）", "類似実測波形（Top-1）", "高ボラ狩り場帯"] if is_short_style else ["場中30分・3分岐点線（スコア比%）"]
                pr_lines = short_defaults + ["予測レンジ帯（ファン）", "類似日スパゲッティ軌道", "押目・利確ゾーン", "VWAP", "心理的キリ番節目", "大口約定（◆）", "出来高"] + (["LAB TP/SL"] if active_lab else [])
            elif sel_preset == "🔍 朝の答え合わせ":
                pr_mode_idx = 1
                pr_lines = ["場中30分・3分岐点線（スコア比%）", "予測レンジ帯（ファン）", "寄り30分高安（ORB）", "出来高"]
            else:
                pr_mode_idx = 0
                pr_lines = ["場中30分・3分岐点線（スコア比%）", "高ボラ狩り場帯", "VWAP", "VWAP±σ", "前日/当日高安（PDH/PDL/HOD/LOD）", "転換時間帯ガイド", "心理的キリ番節目", "大口約定（◆）", "押目・利確ゾーン", "出来高"] + (["LAB TP/SL"] if active_lab else [])

            style_preset_sig = f"{sel_preset}::{is_short_style}"
            if st.session_state.get("dd_last_preset") != sel_preset or st.session_state.get("dd_last_style_sig") != style_preset_sig:
                st.session_state["dd_last_preset"] = sel_preset
                st.session_state["dd_last_style_sig"] = style_preset_sig
                st.session_state["dd_chart_mode"] = modes[pr_mode_idx]
                st.session_state["dd_opt_lines"] = [x for x in pr_lines if x in line_opts]

            with cfg_col:
                if hasattr(st, "popover"):
                    with st.popover("⚙️ 設定", use_container_width=True):
                        chart_mode = st.radio("軌道モード", modes, index=pr_mode_idx, key="dd_chart_mode")
                        opt_lines = st.multiselect("表示レイヤー", line_opts, default=[x for x in pr_lines if x in line_opts], key="dd_opt_lines")
                else:
                    with st.expander("⚙️ 設定"):
                        chart_mode = st.radio("軌道モード", modes, index=pr_mode_idx, key="dd_chart_mode")
                        opt_lines = st.multiselect("表示レイヤー", line_opts, default=[x for x in pr_lines if x in line_opts], key="dd_opt_lines")

            use_1m_zoom = bool(sel_tf == "1分足(直近90分ズーム)" and zoom_1m_payload.get("valid"))
            if sel_tf == "1分足(直近90分ズーム)" and not zoom_1m_payload.get("valid"):
                st.caption("ℹ️ 1分足データが未取得・場外のため、自動で5分足(1日全体)へフォールバック表示しています。")

            def _h_badge(txt: str, col: str, pos: str = "insideStartTop") -> dict:
                return {
                    "formatter": txt,
                    "color": col,
                    "fontSize": 8.2,
                    "fontWeight": "bold",
                    "position": pos,
                    "backgroundColor": "rgba(7, 11, 20, 0.86)",
                    "padding": [1, 4],
                    "borderRadius": 3,
                    "distance": 3,
                }

            def _v_badge(txt: str, col: str) -> dict:
                return {
                    "formatter": txt,
                    "color": col,
                    "fontSize": 8,
                    "rotate": 0,
                    "position": "insideEndTop",
                    "backgroundColor": "rgba(7, 11, 20, 0.82)",
                    "padding": [1, 3],
                    "borderRadius": 3,
                    "distance": 4,
                }

            def _build_pro_ref_marklines(ref_dict: dict, cur_p: float) -> list:
                if "前日/当日高安（PDH/PDL/HOD/LOD）" not in opt_lines or cur_p <= 0:
                    return []
                specs = [
                    ("HOD", ref_dict.get("hod"), "#f43f5e", "insideEndTop"),
                    ("PDH", ref_dict.get("pdh"), "#fb7185", "insideStartTop"),
                    ("PDC", ref_dict.get("pdc"), "#94a3b8", "insideStartBottom"),
                    ("PDL", ref_dict.get("pdl"), "#34d399", "insideStartBottom"),
                    ("LOD", ref_dict.get("lod"), "#10b981", "insideEndBottom"),
                ]
                out_ml = []
                for lbl_r, px_r, col_r, pos_r in specs:
                    if px_r and px_r > 0 and abs(float(px_r) - cur_p) / cur_p <= 0.06:
                        out_ml.append({
                            "yAxis": round(float(px_r), 2),
                            "lineStyle": {"color": col_r, "type": "dashed", "width": 1.0, "opacity": 0.72},
                            "label": _h_badge(f"{lbl_r} {_fmt_cur(px_r, is_jp)}", col_r, pos_r),
                        })
                return out_ml

            if use_1m_zoom:
                z1 = zoom_1m_payload
                ml_1m = _build_pro_ref_marklines(ref_levels, curr_px)
                if "心理的キリ番節目" in opt_lines and curr_px > 0 and abs(round_level - curr_px) / curr_px <= 0.05:
                    ml_1m.append({"yAxis": round_level, "lineStyle": {"color": "rgba(250,204,21,0.52)", "type": "dotted", "width": 1.1}, "label": _h_badge(f"節目 {_fmt_cur(round_level, is_jp)}", "#fde047", "insideEndTop")})
                if active_lab and "LAB TP/SL" in opt_lines:
                    l_tp_1m = float(active_lab.get("tp", active_lab.get("raw_tp", 0.0)) or 0.0)
                    l_sl_1m = float(active_lab.get("sl", active_lab.get("raw_sl", 0.0)) or 0.0)
                    if l_tp_1m > 0 and curr_px > 0 and abs(l_tp_1m - curr_px) / curr_px <= 0.08:
                        ml_1m.append({"yAxis": round(l_tp_1m, 2), "lineStyle": {"color": "#10b981", "type": "dashed", "width": 1.3}, "label": _h_badge(f"TP {_fmt_cur(l_tp_1m, is_jp)}", "#6ee7b7", "insideStartTop")})
                    if l_sl_1m > 0 and curr_px > 0 and abs(l_sl_1m - curr_px) / curr_px <= 0.08:
                        ml_1m.append({"yAxis": round(l_sl_1m, 2), "lineStyle": {"color": "#ef4444", "type": "dashed", "width": 1.3}, "label": _h_badge(f"SL {_fmt_cur(l_sl_1m, is_jp)}", "#fca5a5", "insideStartBottom")})

                ml_1m_clean = _declutter_marklines(ml_1m, curr_px, min_gap_pct=0.38)
                right_pad_1m = 56 if is_jp else 50
                s_1m = [
                    {
                        "name": "1分足",
                        "type": "candlestick",
                        "xAxisIndex": 0,
                        "yAxisIndex": 0,
                        "data": z1["ohlc"],
                        "itemStyle": {
                            "color": "rgba(16, 185, 129, 0.78)",
                            "color0": "rgba(239, 68, 68, 0.78)",
                            "borderColor": "#10b981",
                            "borderColor0": "#ef4444",
                            "borderWidth": 1,
                        },
                        "z": 14,
                    },
                    {
                        "name": "9EMA",
                        "type": "line",
                        "xAxisIndex": 0,
                        "yAxisIndex": 0,
                        "data": z1["ema9"],
                        "itemStyle": {"color": "#38bdf8"},
                        "lineStyle": {"color": "#38bdf8", "width": 1.4},
                        "smooth": 0.12,
                        "showSymbol": False,
                        "z": 7,
                    },
                    {
                        "name": "20EMA",
                        "type": "line",
                        "xAxisIndex": 0,
                        "yAxisIndex": 0,
                        "data": z1["ema20"],
                        "itemStyle": {"color": "#c084fc"},
                        "lineStyle": {"color": "#c084fc", "width": 1.4},
                        "smooth": 0.12,
                        "showSymbol": False,
                        "z": 6,
                    },
                    {
                        "name": "VWAP",
                        "type": "line",
                        "xAxisIndex": 0,
                        "yAxisIndex": 0,
                        "data": z1["vwap"],
                        "itemStyle": {"color": "#fbbf24"},
                        "lineStyle": {"color": "#fbbf24", "width": 1.3, "type": "dotted"},
                        "showSymbol": False,
                        "markLine": {"symbol": ["none", "none"], "data": ml_1m_clean} if ml_1m_clean else {},
                        "z": 6,
                    },
                    {
                        "name": "上昇分岐",
                        "type": "line",
                        "xAxisIndex": 0,
                        "yAxisIndex": 0,
                        "data": z1["up_path"],
                        "itemStyle": {"color": "#10b981"},
                        "lineStyle": {"color": "#10b981", "width": 1.8, "type": "dashed"},
                        "smooth": 0.15,
                        "showSymbol": False,
                        "endLabel": {"show": True, "distance": 4, "formatter": f"▲ {z1['p_up']}%", "color": "#6ee7b7", "fontSize": 9.5, "fontWeight": "bold", "fontFamily": "JetBrains Mono"},
                        "z": 10,
                    },
                    {
                        "name": "横ばい分岐",
                        "type": "line",
                        "xAxisIndex": 0,
                        "yAxisIndex": 0,
                        "data": z1["flat_path"],
                        "itemStyle": {"color": "#94a3b8"},
                        "lineStyle": {"color": "#94a3b8", "width": 1.6, "type": "dotted"},
                        "smooth": 0.15,
                        "showSymbol": False,
                        "endLabel": {"show": True, "distance": 4, "formatter": f"▶ {z1['p_flat']}%", "color": "#cbd5e1", "fontSize": 9.5, "fontWeight": "bold", "fontFamily": "JetBrains Mono"},
                        "z": 9,
                    },
                    {
                        "name": "下落分岐",
                        "type": "line",
                        "xAxisIndex": 0,
                        "yAxisIndex": 0,
                        "data": z1["down_path"],
                        "itemStyle": {"color": "#ef4444"},
                        "lineStyle": {"color": "#ef4444", "width": 1.8, "type": "dashed"},
                        "smooth": 0.15,
                        "showSymbol": False,
                        "endLabel": {"show": True, "distance": 4, "formatter": f"▼ {z1['p_down']}%", "color": "#fca5a5", "fontSize": 9.5, "fontWeight": "bold", "fontFamily": "JetBrains Mono"},
                        "z": 10,
                    },
                    {
                        "name": "1分出来高",
                        "type": "bar",
                        "xAxisIndex": 1,
                        "yAxisIndex": 1,
                        "data": z1["vol_bars"],
                        "barMaxWidth": 5,
                        "markLine": {
                            "symbol": ["none", "none"],
                            "silent": True,
                            "data": [{"yAxis": z1["avg_vol_1m"], "lineStyle": {"color": "rgba(148,163,184,0.35)", "type": "dashed", "width": 1}, "label": {"show": False}}],
                        } if z1["avg_vol_1m"] > 0 else {},
                    },
                    {
                        "name": "疑似CVD",
                        "type": "line",
                        "xAxisIndex": 1,
                        "yAxisIndex": 2,
                        "data": z1["cvd"],
                        "itemStyle": {"color": "#22d3ee"},
                        "lineStyle": {"color": "#22d3ee", "width": 1.6},
                        "areaStyle": {"color": "rgba(34, 211, 238, 0.10)"},
                        "showSymbol": False,
                    },
                ]

                st.caption(f"表示中: 1分足マイクロ・ズーム（{z1['target_date']} 直近90本 ＋ 9/20EMA ＋ VWAP ＋ 10分3分岐 ＋ 下段CVD）｜ 拡大精査時は「自動更新」OFF推奨")
                _render_echarts({
                    "backgroundColor": "#070b14",
                    "legend": {"type": "scroll", "data": ["1分足", "9EMA", "20EMA", "VWAP", "疑似CVD"], "textStyle": {"color": "#cbd5e1", "fontSize": 9.5}, "top": 2, "left": 4, "right": 94, "itemWidth": 12, "itemHeight": 8},
                    "axisPointer": {"link": [{"xAxisIndex": "all"}]},
                    "grid": [
                        {"top": 58, "height": "57%", "left": 6, "right": right_pad_1m, "containLabel": False},
                        {"top": "76%", "height": "17%", "left": 6, "right": right_pad_1m, "containLabel": False},
                    ],
                    "dataZoom": [{"type": "inside", "xAxisIndex": [0, 1], "filterMode": "none"}],
                    "xAxis": [
                        {"type": "category", "gridIndex": 0, "boundaryGap": True, "data": z1["times"], "axisLine": {"lineStyle": {"color": "rgba(148,163,184,0.18)"}}, "axisLabel": {"show": False}},
                        {"type": "category", "gridIndex": 1, "boundaryGap": True, "data": z1["times"], "axisLine": {"lineStyle": {"color": "rgba(148,163,184,0.18)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9, "interval": "auto", "hideOverlap": True}},
                    ],
                    "yAxis": [
                        {"type": "value", "gridIndex": 0, "position": "right", "scale": True, "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.04)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9}},
                        {"type": "value", "gridIndex": 1, "show": False, "axisPointer": {"show": False}},
                        {"type": "value", "gridIndex": 1, "position": "right", "scale": True, "splitLine": {"show": False}, "axisLabel": {"color": "#22d3ee", "fontSize": 8}},
                    ],
                    "series": s_1m,
                }, height=410, use_hud_tooltip=True, is_jp=is_jp, enable_fullscreen=True, is_dual_grid=True, chart_key=f"dd_1m_{fc}")

                st.markdown(f"""
                <div class="dd-3way-strip">
                  <span style="color:#7dd3fc;font-weight:800;">⚡ 1分足・直近10分3分岐:</span>
                  <span>
                    <span style="color:#6ee7b7;font-weight:800;">▲上昇 {z1['p_up']}%</span> /
                    <span style="color:#cbd5e1;font-weight:800;">▶横ばい {z1['p_flat']}%</span> /
                    <span style="color:#fca5a5;font-weight:800;">▼下落 {z1['p_down']}%</span>
                  </span>
                </div>
                """, unsafe_allow_html=True)

                _render_chart_legend_panel(
                    traj, chart_mode, opt_lines, short_3way, exp_reg,
                    active_dip_time, active_peak_time, cur_vwap_now, curr_px, is_jp, active_lab,
                    is_1m_zoom=True, zoom_1m_data=z1
                )

            else:
                med_info = traj.get("medoid_analog")
                if "類似実測波形（Top-1）" in opt_lines and isinstance(med_info, dict) and med_info.get("date"):
                    amp_s = med_info.get("amp_scale", 1.0)
                    med_caption = f" ｜ 最類似実測: {med_info['date']} (Gap {med_info['gap_pct']:+.2f}% / ATR補正×{amp_s:.2f})"
                else:
                    med_caption = ""

                ml_data = _build_pro_ref_marklines(ref_levels, curr_px)
                if traj["lunch_idx"] is not None:
                    ml_data.append({
                        "xAxis": traj["slots"][traj["lunch_idx"]],
                        "lineStyle": {"color": "rgba(148,163,184,0.32)", "type": "dashed", "width": 1.0},
                        "label": _v_badge("昼休", "#94a3b8"),
                    })

                if "転換時間帯ガイド" in opt_lines:
                    micro_times = (
                        [("09:15", "一巡"), ("14:30", "機関"), ("15:25", "引け")]
                        if is_jp else
                        [("10:00", "指標"), ("11:30", "欧州引"), ("15:50", "MOC")]
                    )
                    for mt_slot, mt_lbl in micro_times:
                        if mt_slot in traj["slots"]:
                            ml_data.append({
                                "xAxis": mt_slot,
                                "lineStyle": {"color": "rgba(125, 211, 252, 0.22)", "type": "dotted", "width": 1.0},
                                "label": _v_badge(mt_lbl, "rgba(148, 163, 184, 0.85)"),
                            })

                if g15.get("show_gap_target") and prev_px > 0:
                    ml_data.append({"yAxis": round(prev_px, 2), "lineStyle": {"color": "#f97316", "type": "dashed", "width": 1.4}, "label": _h_badge(f"窓埋目標 {_fmt_cur(prev_px, is_jp)}", "#fdba74", "insideStartTop")})
                if "心理的キリ番節目" in opt_lines:
                    ml_data.append({"yAxis": round_level, "lineStyle": {"color": "rgba(250,204,21,0.52)", "type": "dotted", "width": 1.1}, "label": _h_badge(f"節目 {_fmt_cur(round_level, is_jp)}", "#fde047", "insideEndTop")})
                if "寄り30分高安（ORB）" in opt_lines and traj["orb_high"] and traj["orb_low"]:
                    ml_data.append({"yAxis": traj["orb_high"], "lineStyle": {"color": "rgba(56,189,248,0.42)", "type": "dashed", "width": 1.0}, "label": _h_badge("ORB高", "#7dd3fc", "insideEndTop")})
                    ml_data.append({"yAxis": traj["orb_low"], "lineStyle": {"color": "rgba(244,63,94,0.42)", "type": "dashed", "width": 1.0}, "label": _h_badge("ORB安", "#fda4af", "insideEndBottom")})

                if exp_active and traj["orb_high"] and traj["orb_low"]:
                    orb_rng = max(float(traj["orb_high"]) - float(traj["orb_low"]), 0.0)
                    if orb_rng > 0:
                        if exp_dir == "UP":
                            orb_ext_up = round(float(traj["orb_low"]) + orb_rng * 1.618, 2)
                            if curr_px > 0 and abs(orb_ext_up - curr_px) / curr_px <= 0.14:
                                ml_data.append({"yAxis": orb_ext_up, "lineStyle": {"color": "rgba(34,211,238,0.62)", "type": "dotted", "width": 1.2}, "label": _h_badge(f"ORB拡張1.618 {_fmt_cur(orb_ext_up, is_jp)}", "#67e8f9", "insideEndTop")})
                        elif exp_dir == "DOWN":
                            orb_ext_dn = round(max(float(traj["orb_high"]) - orb_rng * 1.618, curr_px * 0.5), 2)
                            if curr_px > 0 and abs(orb_ext_dn - curr_px) / curr_px <= 0.14:
                                ml_data.append({"yAxis": orb_ext_dn, "lineStyle": {"color": "rgba(251,113,133,0.62)", "type": "dotted", "width": 1.2}, "label": _h_badge(f"ORB拡張1.618 {_fmt_cur(orb_ext_dn, is_jp)}", "#fda4af", "insideEndBottom")})

                lab_tpsl_hidden = False
                if active_lab and "LAB TP/SL" in opt_lines:
                    l_tp_line = float(active_lab.get("tp", active_lab.get("raw_tp", 0.0)) or 0.0)
                    l_sl_line = float(active_lab.get("sl", active_lab.get("raw_sl", 0.0)) or 0.0)
                    if l_tp_line > 0 and curr_px > 0:
                        if abs(l_tp_line - curr_px) / curr_px <= 0.12:
                            ml_data.append({"yAxis": round(l_tp_line, 2), "lineStyle": {"color": "#10b981", "type": "dashed", "width": 1.3}, "label": _h_badge(f"TP {_fmt_cur(l_tp_line, is_jp)}", "#6ee7b7", "insideStartTop")})
                        else:
                            lab_tpsl_hidden = True
                    if l_sl_line > 0 and curr_px > 0:
                        if abs(l_sl_line - curr_px) / curr_px <= 0.12:
                            ml_data.append({"yAxis": round(l_sl_line, 2), "lineStyle": {"color": "#ef4444", "type": "dashed", "width": 1.3}, "label": _h_badge(f"SL {_fmt_cur(l_sl_line, is_jp)}", "#fca5a5", "insideStartBottom")})
                        else:
                            lab_tpsl_hidden = True
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
                                ml_data.append({"yAxis": round(px_a, 2), "lineStyle": {"color": col_a, "type": "dotted", "width": 1.1}, "label": _h_badge(f"{lbl_a} {_fmt_cur(px_a, is_jp)}", col_a, "insideEndTop")})
                        except Exception:
                            pass

                ml_data_clean = _declutter_marklines(ml_data, curr_px, min_gap_pct=0.38)
                ml_cfg = {"symbol": ["none", "none"], "data": ml_data_clean} if ml_data_clean else {}

                preset_desc = {
                    "📈 今の予測": "ライブ修正軌道 ＋ 分位点ファン ＋ 場中30分3分岐 ＋ 下段CVD同期",
                    "🔍 朝の答え合わせ": "寄り前ロック予測 vs 当日実測 ＋ 寄り30分高安 ＋ 下段CVD同期",
                    "🏦 大口・節目": "VWAP±σ ＋ PDH/PDL/HOD/LOD ＋ キリ番 ＋ 大口約定 ＋ 下段CVD",
                }
                guard_note = " ※LAB TP/SLの一部は現在値±12%外のため非表示" if lab_tpsl_hidden else ""
                st.caption(f"表示中: {preset_desc.get(sel_preset, '')}{med_caption}{guard_note}")

                if chart_mode in ("🔒 朝ロック検証", "⚡ 両方重ね"):
                    if traj["verify"]["has_verify"]:
                        v = traj["verify"]
                        st.markdown(f'<div class="dd-quant-box"><b>📊 寄り前ロック予測 vs 当日実測 検証（実測 {v["n_pts"]}本）</b><br>・<b>分位点ファン内 収束率:</b> <b style="color:#fde047;">{v["in_cone_pct"]}%</b> ｜ <b>平均誤差:</b> <b>{v["err_pct"]}%</b></div>', unsafe_allow_html=True)
                    elif traj["has_actual"] and not traj["is_locked"]:
                        st.markdown('<div class="dd-sync-warn"><b>ℹ️ 本日は寄り前2時間以内の事前ロックがないため「朝ロック検証」対象外</b><br>リーク防止のため、寄り前2時間以内に保存された予測のみを答え合わせ対象としています（現在はライブ修正軌道を基準に表示中）。</div>', unsafe_allow_html=True)

                ma_data = []
                if "高ボラ狩り場帯" in opt_lines and traj.get("high_vol_zones"):
                    for hvz in traj["high_vol_zones"]:
                        show_hv_lbl = bool(hvz.get("show_label", hvz.get("width_slots", 3) >= 3))
                        ma_data.append([
                            {
                                "name": f"±{hvz['avg_move_pct']:.1f}%",
                                "xAxis": hvz["start_slot"],
                                "itemStyle": {"color": "rgba(245, 158, 11, 0.06)"},
                                "label": {
                                    "show": show_hv_lbl,
                                    "position": "insideBottom",
                                    "color": "#fbbf24",
                                    "fontSize": 8,
                                    "backgroundColor": "rgba(7, 11, 20, 0.78)",
                                    "padding": [1, 3],
                                    "borderRadius": 2,
                                },
                            },
                            {"xAxis": hvz["end_slot"]},
                        ])
                if "押目・利確ゾーン" in opt_lines:
                    n_sl = len(traj["slots"])
                    cur_dip_i = traj["live_dip_idx"] if use_live_basis else traj["locked_dip_idx"]
                    cur_peak_i = traj["live_peak_idx"] if use_live_basis else traj["locked_peak_idx"]
                    d_s, d_e = max(0, cur_dip_i - 2), min(n_sl - 1, cur_dip_i + 2)
                    p_s, p_e = max(0, cur_peak_i - 2), min(n_sl - 1, cur_peak_i + 2)
                    ma_data.append([{"name": "押目帯", "xAxis": traj["slots"][d_s], "itemStyle": {"color": "rgba(16, 185, 129, 0.07)"}, "label": {"position": "insideTop", "color": "#6ee7b7", "fontSize": 8.2, "backgroundColor": "rgba(7, 11, 20, 0.78)", "padding": [1, 3], "borderRadius": 2}}, {"xAxis": traj["slots"][d_e]}])
                    ma_data.append([{"name": "利確帯", "xAxis": traj["slots"][p_s], "itemStyle": {"color": "rgba(239, 68, 68, 0.07)"}, "label": {"position": "insideTop", "color": "#fca5a5", "fontSize": 8.2, "backgroundColor": "rgba(7, 11, 20, 0.78)", "padding": [1, 3], "borderRadius": 2}}, {"xAxis": traj["slots"][p_e]}])
                    if vp["overhead_pct"] >= 25.0 and not exp_active:
                        ma_data.append([{"name": "売り壁", "yAxis": round(vp["res_px"] * 0.996, 2), "itemStyle": {"color": "rgba(168, 85, 247, 0.10)"}, "label": {"position": "insideRight", "color": "#d8b4fe", "fontSize": 8.2, "backgroundColor": "rgba(7, 11, 20, 0.78)", "padding": [1, 3], "borderRadius": 2}}, {"yAxis": round(vp["res_px"] * 1.004, 2)}])
                ma_cfg = {"silent": True, "data": ma_data} if ma_data else {}

                s_list, l_names = [], []

                if "予測レンジ帯（ファン）" in opt_lines:
                    is_lv = (chart_mode in ("🔴 ライブ修正", "⚡ 両方重ね") and traj["has_actual"])
                    c_p15 = disp_live_p15 if is_lv else disp_locked_p15
                    c_bd = disp_live_bdiff if is_lv else disp_locked_bdiff
                    c_p32 = disp_live_p32 if is_lv else disp_locked_p32
                    c_bd_in = disp_live_bdiff_in if is_lv else disp_locked_bdiff_in
                    s_list.extend([
                        {"name": "outer_base", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": c_p15, "stack": "fan_out", "itemStyle": {"color": "rgba(99, 102, 241, 0.18)"}, "lineStyle": {"opacity": 0}, "smooth": 0.15, "showSymbol": False, "silent": True, "z": 1},
                        {"name": "10-90%分位帯", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": c_bd, "stack": "fan_out", "itemStyle": {"color": "rgba(99, 102, 241, 0.18)"}, "lineStyle": {"opacity": 0}, "areaStyle": {"color": "rgba(99, 102, 241, 0.08)"}, "smooth": 0.15, "showSymbol": False, "silent": True, "z": 1},
                        {"name": "inner_base", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": c_p32, "stack": "fan_in", "itemStyle": {"color": "#38bdf8"}, "lineStyle": {"opacity": 0}, "smooth": 0.15, "showSymbol": False, "silent": True, "z": 2},
                        {"name": "コア帯", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": c_bd_in, "stack": "fan_in", "itemStyle": {"color": "#38bdf8"}, "lineStyle": {"color": "#38bdf8", "opacity": 0}, "areaStyle": {"color": "rgba(56, 189, 248, 0.14)"}, "smooth": 0.15, "showSymbol": False, "silent": True, "z": 2},
                    ])
                    l_names.append("コア帯")

                if "類似日スパゲッティ軌道" in opt_lines and traj["knn_match"].get("analog_paths"):
                    for a_idx, ap in enumerate(traj["knn_match"]["analog_paths"]):
                        ap_scaled = _scale_live_arr(ap["data"])
                        s_list.append({
                            "name": f"類似_{ap['date']}",
                            "type": "line",
                            "xAxisIndex": 0,
                            "yAxisIndex": 0,
                            "data": ap_scaled,
                            "itemStyle": {"color": "#94a3b8"},
                            "lineStyle": {"color": "#94a3b8", "width": 0.9, "opacity": 0.14},
                            "smooth": 0.15,
                            "showSymbol": False,
                            "silent": True,
                            "z": 2,
                        })

                if "類似実測波形（Top-1）" in opt_lines and isinstance(med_info, dict) and med_info.get("data"):
                    med_scaled = _scale_live_arr(med_info["data"])
                    s_list.append({
                        "name": "類似実測(Top-1)",
                        "type": "line",
                        "xAxisIndex": 0,
                        "yAxisIndex": 0,
                        "data": med_scaled,
                        "itemStyle": {"color": "#f59e0b"},
                        "lineStyle": {"color": "#f59e0b", "width": 1.3, "opacity": 0.68, "type": "solid"},
                        "smooth": 0.12,
                        "showSymbol": False,
                        "z": 6,
                    })
                    l_names.append("類似実測(Top-1)")

                if "VWAP" in opt_lines and traj["has_actual"]:
                    s_list.append({
                        "name": "VWAP",
                        "type": "line",
                        "xAxisIndex": 0,
                        "yAxisIndex": 0,
                        "data": traj["vwap"],
                        "itemStyle": {"color": "#fbbf24"},
                        "lineStyle": {"color": "#fbbf24", "width": 1.3, "type": "dotted"},
                        "showSymbol": False,
                        "z": 6,
                    })
                    l_names.append("VWAP")

                if "VWAP±σ" in opt_lines and traj["has_actual"]:
                    s_list.extend([
                        {"name": "VWAP+1σ", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": traj["vwap_p1"], "itemStyle": {"color": "rgba(251,191,36,0.48)"}, "lineStyle": {"color": "rgba(251,191,36,0.48)", "width": 0.9, "type": "dashed"}, "showSymbol": False, "silent": True, "z": 5},
                        {"name": "VWAP-1σ", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": traj["vwap_m1"], "itemStyle": {"color": "rgba(251,191,36,0.48)"}, "lineStyle": {"color": "rgba(251,191,36,0.48)", "width": 0.9, "type": "dashed"}, "showSymbol": False, "silent": True, "z": 5},
                        {"name": "VWAP+2σ", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": traj["vwap_p2"], "itemStyle": {"color": "rgba(239,68,68,0.40)"}, "lineStyle": {"color": "rgba(239,68,68,0.40)", "width": 0.9, "type": "dotted"}, "showSymbol": False, "silent": True, "z": 5},
                        {"name": "VWAP-2σ", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": traj["vwap_m2"], "itemStyle": {"color": "rgba(16,185,129,0.40)"}, "lineStyle": {"color": "rgba(16,185,129,0.40)", "width": 0.9, "type": "dotted"}, "showSymbol": False, "silent": True, "z": 5},
                    ])

                if chart_mode in ("🔒 朝ロック検証", "⚡ 両方重ね"):
                    is_both = (chart_mode == "⚡ 両方重ね")
                    if exp_active:
                        lk_name = "朝ロック(無効化済)"
                        lk_col = "rgba(148, 163, 184, 0.30)"
                        lk_style = {"color": "rgba(148,163,184,0.30)", "width": 1.2, "type": "dotted"}
                    else:
                        lk_name = "朝ロック"
                        lk_col = "#c084fc" if is_both else "#38bdf8"
                        lk_style = {"color": lk_col, "width": 1.6 if is_both else 2.0, "type": "dashed" if is_both else "solid", "shadowBlur": 6, "shadowColor": "rgba(192,132,252,0.35)"}
                    s_list.append({
                        "name": lk_name, "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": disp_locked_p50,
                        "itemStyle": {"color": lk_col},
                        "lineStyle": lk_style,
                        "smooth": 0.15,
                        "showSymbol": False, "markLine": ml_cfg, "markArea": ma_cfg,
                        "z": 8,
                    })
                    l_names.append(lk_name)

                if chart_mode in ("🔴 ライブ修正", "⚡ 両方重ね"):
                    s_list.append({
                        "name": "ライブ修正", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": disp_live_p50,
                        "itemStyle": {"color": "#38bdf8"},
                        "lineStyle": {"color": "#38bdf8", "width": 2.0, "shadowBlur": 10, "shadowColor": "rgba(56,189,248,0.55)"},
                        "smooth": 0.15,
                        "showSymbol": False,
                        "markLine": ml_cfg if chart_mode == "🔴 ライブ修正" else {},
                        "markArea": ma_cfg if chart_mode == "🔴 ライブ修正" else {},
                        "z": 10,
                    })
                    l_names.append("ライブ修正")

                if traj["has_actual"]:
                    s_list.append({
                        "name": "当日実測", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": traj["actual"],
                        "itemStyle": {"color": "#ffffff"},
                        "lineStyle": {"color": "#ffffff", "width": 2.4, "shadowBlur": 8, "shadowColor": "rgba(255,255,255,0.55)"},
                        "smooth": False,
                        "showSymbol": False,
                        "z": 14,
                    })
                    l_names.insert(0, "当日実測")

                show_3way_now = bool("場中30分・3分岐点線（スコア比%）" in opt_lines and short_3way.get("active"))
                if show_3way_now:
                    s_list.extend([
                        {
                            "name": "上昇分岐",
                            "type": "line",
                            "xAxisIndex": 0,
                            "yAxisIndex": 0,
                            "data": short_3way["up_path"],
                            "itemStyle": {"color": "#10b981"},
                            "lineStyle": {"color": "#10b981", "width": 1.8, "type": "dashed"},
                            "smooth": 0.15,
                            "showSymbol": False,
                            "endLabel": {"show": True, "distance": 4, "formatter": f"▲ {short_3way['p_up']}%", "color": "#6ee7b7", "fontSize": 9.5, "fontWeight": "bold", "fontFamily": "JetBrains Mono"},
                            "z": 11,
                        },
                        {
                            "name": "横ばい分岐",
                            "type": "line",
                            "xAxisIndex": 0,
                            "yAxisIndex": 0,
                            "data": short_3way["flat_path"],
                            "itemStyle": {"color": "#94a3b8"},
                            "lineStyle": {"color": "#94a3b8", "width": 1.6, "type": "dotted"},
                            "smooth": 0.15,
                            "showSymbol": False,
                            "endLabel": {"show": True, "distance": 4, "formatter": f"▶ {short_3way['p_flat']}%", "color": "#cbd5e1", "fontSize": 9.5, "fontWeight": "bold", "fontFamily": "JetBrains Mono"},
                            "z": 10,
                        },
                        {
                            "name": "下落分岐",
                            "type": "line",
                            "xAxisIndex": 0,
                            "yAxisIndex": 0,
                            "data": short_3way["down_path"],
                            "itemStyle": {"color": "#ef4444"},
                            "lineStyle": {"color": "#ef4444", "width": 1.8, "type": "dashed"},
                            "smooth": 0.15,
                            "showSymbol": False,
                            "endLabel": {"show": True, "distance": 4, "formatter": f"▼ {short_3way['p_down']}%", "color": "#fca5a5", "fontSize": 9.5, "fontWeight": "bold", "fontFamily": "JetBrains Mono"},
                            "z": 11,
                        },
                    ])

                if "大口約定（◆）" in opt_lines and traj["vol_spikes"]:
                    sp_pts = [{"value": [sp["time"], sp["price"]], "itemStyle": {"color": "#10b981" if sp["dir"] > 0 else "#ef4444", "borderColor": "#ffffff", "borderWidth": 1}} for sp in traj["vol_spikes"]]
                    s_list.append({"name": "大口約定", "type": "scatter", "xAxisIndex": 0, "yAxisIndex": 0, "symbol": "diamond", "symbolSize": 8, "data": sp_pts, "z": 12})

                def _edge_aware_pulse(pt_name: str, pt_time: str, pt_px: float, pt_col: str) -> dict:
                    try:
                        s_idx = traj["slots"].index(pt_time)
                    except ValueError:
                        s_idx = len(traj["slots"]) // 2
                    n_tot_s = len(traj["slots"])
                    al = "left" if s_idx <= 4 else ("right" if s_idx >= n_tot_s - 5 else "center")
                    return {
                        "name": pt_name,
                        "value": [pt_time, pt_px],
                        "itemStyle": {"color": pt_col},
                        "label": {
                            "align": al,
                            "backgroundColor": "rgba(7, 11, 20, 0.84)",
                            "padding": [1, 3],
                            "borderRadius": 3,
                        },
                    }

                pulse_pts = [
                    _edge_aware_pulse("押目", active_dip_time, active_dip_px, "#10b981"),
                    _edge_aware_pulse("高値", active_peak_time, active_peak_px, "#f43f5e"),
                ]
                if traj["has_actual"] and traj["last_act_idx"] >= 0:
                    li = traj["last_act_idx"]
                    pulse_pts.append(_edge_aware_pulse("NOW", traj["slots"][li], traj["actual"][li], "#ffffff"))
                if cvd_div.get("marker"):
                    mk_d = cvd_div["marker"]
                    pulse_pts.append(_edge_aware_pulse(mk_d["name"], mk_d["time"], mk_d["price"], mk_d["color"]))
                s_list.append({
                    "name": "重要点", "type": "effectScatter", "xAxisIndex": 0, "yAxisIndex": 0, "data": pulse_pts,
                    "symbolSize": 7, "rippleEffect": {"brushType": "stroke", "scale": 3.0},
                    "label": {"show": True, "position": "top", "formatter": "{b}", "color": "#f8fafc", "fontSize": 8.8, "fontWeight": "bold"},
                    "z": 15,
                })

                s_list.append({
                    "name": "平均出来高",
                    "type": "line",
                    "xAxisIndex": 1,
                    "yAxisIndex": 1,
                    "data": traj["vols"],
                    "itemStyle": {"color": "rgba(148,163,184,0.38)"},
                    "lineStyle": {"color": "rgba(148,163,184,0.38)", "width": 1.0, "type": "dashed"},
                    "showSymbol": False,
                    "silent": True,
                })
                if traj["has_actual"] and any(v is not None for v in traj["actual_vols"]):
                    colored_act_vols = []
                    for v_i, d_i in zip(traj["actual_vols"], traj["actual_dirs"]):
                        if v_i is None:
                            colored_act_vols.append({"value": 0, "itemStyle": {"color": "transparent"}})
                        else:
                            colored_act_vols.append({
                                "value": v_i,
                                "itemStyle": {"color": "rgba(16, 185, 129, 0.52)" if d_i > 0 else "rgba(239, 68, 68, 0.52)"},
                            })
                    s_list.append({
                        "name": "当日出来高",
                        "type": "bar",
                        "xAxisIndex": 1,
                        "yAxisIndex": 1,
                        "data": colored_act_vols,
                        "barMaxWidth": 4,
                    })
                    s_list.append({
                        "name": "疑似CVD",
                        "type": "line",
                        "xAxisIndex": 1,
                        "yAxisIndex": 2,
                        "data": traj["cvd_arr"],
                        "itemStyle": {"color": "#22d3ee"},
                        "lineStyle": {"color": "#22d3ee", "width": 1.6},
                        "areaStyle": {"color": "rgba(34, 211, 238, 0.10)"},
                        "showSymbol": False,
                        "markLine": {
                            "symbol": ["none", "none"],
                            "silent": True,
                            "data": [{"yAxis": 0, "lineStyle": {"color": "rgba(148,163,184,0.25)", "type": "dotted", "width": 1}, "label": {"show": False}}],
                        },
                    })
                    l_names.append("疑似CVD")

                right_pad = (58 if is_jp else 52) if show_3way_now else (50 if is_jp else 44)
                _render_echarts({
                    "backgroundColor": "#070b14",
                    "legend": {"type": "scroll", "data": l_names, "textStyle": {"color": "#cbd5e1", "fontSize": 9.5}, "top": 2, "left": 4, "right": 94, "itemWidth": 12, "itemHeight": 8},
                    "axisPointer": {"link": [{"xAxisIndex": "all"}]},
                    "grid": [
                        {"top": 58, "height": "57%", "left": 6, "right": right_pad, "containLabel": False},
                        {"top": "76%", "height": "17%", "left": 6, "right": right_pad, "containLabel": False},
                    ],
                    "dataZoom": [{"type": "inside", "xAxisIndex": [0, 1], "filterMode": "none"}],
                    "xAxis": [
                        {"type": "category", "gridIndex": 0, "boundaryGap": False, "data": traj["slots"], "axisLine": {"lineStyle": {"color": "rgba(148,163,184,0.18)"}}, "axisLabel": {"show": False}},
                        {"type": "category", "gridIndex": 1, "boundaryGap": False, "data": traj["slots"], "axisLine": {"lineStyle": {"color": "rgba(148,163,184,0.18)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9, "interval": "auto", "hideOverlap": True}},
                    ],
                    "yAxis": [
                        {"type": "value", "gridIndex": 0, "position": "right", "scale": True, "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.04)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9}},
                        {"type": "value", "gridIndex": 1, "show": False, "axisPointer": {"show": False}},
                        {"type": "value", "gridIndex": 1, "position": "right", "scale": True, "splitLine": {"show": False}, "axisLabel": {"color": "#22d3ee", "fontSize": 8}},
                    ],
                    "series": s_list
                }, height=410, use_hud_tooltip=True, is_jp=is_jp, enable_fullscreen=True, is_dual_grid=True, chart_key=f"dd_5m_{fc}")

                if show_3way_now:
                    mins_ahead = short_3way["horizon"] * 5
                    ml_badge_html = (
                        f' <span style="background:rgba(168,85,247,0.22);border:1px solid rgba(168,85,247,0.5);'
                        f'color:#e9d5ff;padding:1px 5px;border-radius:4px;font-size:9.5px;">🤖ML学習(N={short_3way["ml_samples"]})</span>'
                        if short_3way.get("ml_used") else ""
                    )
                    st.markdown(f"""
                    <div class="dd-3way-strip">
                      <span style="color:#7dd3fc;font-weight:800;">⚡ 短期{mins_ahead}分3分岐:{ml_badge_html}</span>
                      <span>
                        <span style="color:#6ee7b7;font-weight:800;">▲上昇 {short_3way['p_up']}%</span> /
                        <span style="color:#cbd5e1;font-weight:800;">▶横ばい {short_3way['p_flat']}%</span> /
                        <span style="color:#fca5a5;font-weight:800;">▼下落 {short_3way['p_down']}%</span>
                      </span>
                    </div>
                    """, unsafe_allow_html=True)

                _render_chart_legend_panel(
                    traj, chart_mode, opt_lines, short_3way, exp_reg,
                    active_dip_time, active_peak_time, cur_vwap_now, curr_px, is_jp, active_lab,
                    is_1m_zoom=False
                )

            basis_txt = "ライブ連動" if use_live_basis else "朝ロック基準"
            shock_badge_txt = f" / 衝撃波{shock_ext_pct:+.2f}%" if abs(shock_ext_pct) > 0.01 else ""
            st.markdown(f"""
            <div class="dd-prob-meter">
              <div style="display:flex;justify-content:space-between;align-items:center;font-size:10px;">
                <span style="font-weight:800;color:#7dd3fc;">SCENARIO ALLOCATION // リアルタイム・シナリオ配分（スコア比）</span>
                <span style="font-family:'JetBrains Mono',monospace;color:#64748b;font-size:9.3px;">{basis_txt}{shock_badge_txt}</span>
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

            with st.expander("⚡ What-If 衝撃波シミュレーター（指数・為替 追加変動テスト）", expanded=False):
                wi1, wi2 = st.columns(2)
                wi_idx = wi1.slider(
                    f"主連動（{f_map['mkt_label']} β={mkt_beta_eff:+.2f}）追加変動 (%)",
                    min_value=-2.0, max_value=2.0, step=0.1,
                    key=wi_idx_key
                )
                wi_fx = wi2.slider(
                    f"ドル円（β={fx_beta_eff:+.2f}）追加変動 (円)",
                    min_value=-2.0, max_value=2.0, step=0.1,
                    key=wi_fx_key
                )
                st.caption(
                    f"合成ショック影響: {shock_ext_pct:+.2f}% ｜ "
                    f"想定大引け: {_fmt_cur(active_close_px, is_jp)} ({active_close_chg:+.2f}%) ｜ "
                    f"上振れ配分: {scen_probs['bull']:.1f}% / 下振れ配分: {scen_probs['bear']:.1f}%"
                )

            with st.expander("🧮 適正ロット・100株単元・流動性インパクト・二壁FPT電卓", expanded=False):
                l_tp_ev = float(active_lab.get("tp", active_lab.get("raw_tp", 0.0)) or 0.0) if active_lab else 0.0
                l_sl_ev = float(active_lab.get("sl", active_lab.get("raw_sl", 0.0)) or 0.0) if active_lab else 0.0
                l_side_ev = _extract_lab_side(active_lab) if active_lab else "LONG"
                is_long_ev = (l_side_ev != "SHORT")
                def_tp = l_tp_ev if l_tp_ev > 0 else (active_bull_tgt if is_long_ev else active_bear_tgt)
                def_sl = l_sl_ev if l_sl_ev > 0 else (active_bear_trig if is_long_ev else active_bull_trig)
                ec1, ec2 = st.columns([1.4, 1.0])
                risk_amt = ec1.number_input(
                    "1回の許容損失額 (" + ("円" if is_jp else "$") + ")",
                    min_value=10.0,
                    value=10000.0 if is_jp else 100.0,
                    step=1000.0 if is_jp else 25.0,
                    key=f"dd_risk_amt_{'jp' if is_jp else 'us'}"
                )
                win_prob = ec2.slider("想定勝率 (%)", 30, 80, int(active_lab.get("expect_pct", 55)) if active_lab else 55, key="dd_win_prob")

                sim_curr_px = round(curr_px * (1.0 + shock_ext_pct / 100.0 * 0.35), 2)
                signed_risk = (sim_curr_px - def_sl) if is_long_ev else (def_sl - sim_curr_px)
                signed_rew = (def_tp - sim_curr_px) if is_long_ev else (sim_curr_px - def_tp)
                sl_breached = bool(signed_risk <= 0)
                tp_passed = bool(signed_rew <= 0)

                risk_per_sh = max(signed_risk, sim_curr_px * 0.005) if not sl_breached else (sim_curr_px * 0.005)
                rew_per_sh = max(signed_rew, 0.0)
                rr_ratio = (rew_per_sh / risk_per_sh) if (not sl_breached and not tp_passed) else 0.0
                raw_shares = 0 if (sl_breached or tp_passed) else int(risk_amt // risk_per_sh)

                jp_under_lot = False
                if sl_breached or tp_passed:
                    opt_shares = 0
                    calc_shares = 0
                    lot_lbl = "0株 (条件破綻)"
                    lot_col = "#ef4444"
                elif is_jp:
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

                be_wr = (1.0 / (1.0 + rr_ratio)) * 100.0 if rr_ratio > 0 else 99.9
                ev_val = (win_prob / 100.0) * (calc_shares * rew_per_sh) - (1.0 - win_prob / 100.0) * (calc_shares * risk_per_sh)
                ev_col = "#10b981" if ev_val > 0 else "#ef4444"
                ev_sign = "+" if ev_val >= 0 else ""

                avg_5m_v = max(float(traj.get("avg_5m_vol", 1.0)), 1.0)
                impact_pct = (calc_shares / avg_5m_v) * 100.0
                imp_col = "#ef4444" if impact_pct >= 2.0 else ("#f59e0b" if impact_pct >= 0.8 else "#10b981")

                tp_fpt = _calc_first_passage_prob(sim_curr_px, def_tp, traj["rem_sigma_pct"], active_rem_drift)
                sl_fpt = _calc_first_passage_prob(sim_curr_px, def_sl, traj["rem_sigma_pct"], active_rem_drift)
                two_barrier_tp = _calc_two_barrier_tp_prob(sim_curr_px, def_tp, def_sl, is_long_ev, traj["rem_sigma_pct"], active_rem_drift)
                tp_fpt_col = "#10b981" if two_barrier_tp >= 35 else "#f59e0b"
                sl_fpt_col = "#ef4444" if sl_fpt >= 45 else "#94a3b8"
                rem_pct_lbl = int(round(traj["rem_frac_now"] * 100))

                st.markdown(f"""
                <div style="font-size:11px;color:#94a3b8;">基準({l_side_ev}): Entry <b>{_fmt_cur(sim_curr_px, is_jp)}</b> / TP <b>{_fmt_cur(def_tp, is_jp)}</b> / SL <b>{_fmt_cur(def_sl, is_jp)}</b>（残存σ {traj['rem_sigma_pct']*100:.2f}% / 残出来高割合 {rem_pct_lbl}%）</div>
                <div class="dd-ev-grid">
                  <div class="dd-ev-cell"><div class="dd-metric-lbl">適正ロット</div><div style="font-family:'JetBrains Mono',monospace;font-size:12.5px;font-weight:800;color:{lot_col};">{lot_lbl}</div></div>
                  <div class="dd-ev-cell"><div class="dd-metric-lbl">RR比 (損益分岐)</div><div style="font-family:'JetBrains Mono',monospace;font-size:12.5px;font-weight:800;color:#fde047;">1:{rr_ratio:.2f} ({be_wr:.0f}%)</div></div>
                  <div class="dd-ev-cell"><div class="dd-metric-lbl">1回あたり期待値</div><div style="font-family:'JetBrains Mono',monospace;font-size:12.5px;font-weight:800;color:{ev_col};">{ev_sign}{_fmt_cur(ev_val, is_jp)}</div></div>
                </div>
                <div class="dd-ev-grid" style="margin-top:6px;">
                  <div class="dd-ev-cell"><div class="dd-metric-lbl">SL前TP先達 (二壁FPT)</div><div style="font-family:'JetBrains Mono',monospace;font-size:12.5px;font-weight:800;color:{tp_fpt_col};">{two_barrier_tp:.1f}% <span style="font-size:9px;color:#94a3b8;">(片壁{tp_fpt:.0f}%)</span></div></div>
                  <div class="dd-ev-cell"><div class="dd-metric-lbl">大引け迄 SLタッチ</div><div style="font-family:'JetBrains Mono',monospace;font-size:12.5px;font-weight:800;color:{sl_fpt_col};">{sl_fpt:.1f}%</div></div>
                  <div class="dd-ev-cell"><div class="dd-metric-lbl">流動性インパクト</div><div style="font-family:'JetBrains Mono',monospace;font-size:12.5px;font-weight:800;color:{imp_col};">{impact_pct:.2f}%</div></div>
                </div>
                """, unsafe_allow_html=True)

                if sl_breached:
                    st.markdown('<div class="dd-warn-box" style="margin-top:6px;margin-bottom:0;"><b>⛔ すでに損切りライン（SL）を割り込んでいます</b><br>現在値がSL水準を突破済みのため、新規エントリー不可（0株見送り）です。</div>', unsafe_allow_html=True)
                elif tp_passed:
                    st.markdown('<div class="dd-sync-warn" style="margin-top:6px;margin-bottom:0;"><b>⚠️ すでに利確目標（TP）に到達済みです</b><br>値幅を取り切った後の高値掴みリスクが高いため、新規エントリーは見送りを推奨します。</div>', unsafe_allow_html=True)
                elif jp_under_lot:
                    min_loss_100 = 100.0 * risk_per_sh
                    st.markdown(f'<div class="dd-warn-box" style="margin-top:6px;margin-bottom:0;"><b>⛔ 1単元（100株）で許容損失オーバー</b><br>最小単元100株のSL到達時損失は <b>{_fmt_cur(min_loss_100, True)}</b> で許容損失（{_fmt_cur(risk_amt, True)}）を超過します。エントリー見送りか単元未満株を検討してください。</div>', unsafe_allow_html=True)
                if not sl_breached and not tp_passed and (win_prob - two_barrier_tp) >= 20.0:
                    st.markdown(f'<div class="dd-sync-warn" style="margin-top:6px;margin-bottom:0;"><b>⚠️ 想定勝率({win_prob}%)と大引け迄の二壁FPT到達確率({two_barrier_tp:.1f}%)が乖離</b><br>本日大引けまでにTPへ先達する物理確率は {two_barrier_tp:.1f}% です。デイトレ完結ならTPを近づけるか勝率設定を引き下げてください。</div>', unsafe_allow_html=True)
                if impact_pct >= 2.0:
                    st.markdown(f'<div class="dd-warn-box" style="margin-top:6px;margin-bottom:0;"><b>⚠️ 流動性インパクト警戒（5分足出来高の {impact_pct:.2f}%）</b><br>板が薄く、成行発注だとスリッページでRR比が崩壊する恐れがあります。指値分割執行を推奨します。</div>', unsafe_allow_html=True)
                if traj["has_actual"] and two_barrier_tp < 20.0 and traj["rem_frac_now"] < 0.45 and not sl_breached and not tp_passed:
                    st.markdown('<div class="dd-warn-box" style="margin-top:6px;margin-bottom:0;"><b>⛔ 時間切れ警戒（手遅れエントリー注意）</b><br>残存ボラティリティに対しTPが遠すぎます（二壁到達確率 20%未満）。新規の追っかけエントリーは非推奨です。</div>', unsafe_allow_html=True)

            bp = (active_bull_tgt - curr_px) / max(curr_px, 1e-4) * 100.0
            sp = (active_bear_tgt - curr_px) / max(curr_px, 1e-4) * 100.0
            mid_sc_prob = round(scen_probs["range"] + scen_probs["fade"], 1)
            st.markdown(f"""
            <div class="dd-sc-stack">
              <div class="dd-sc-card" style="border-left:4px solid #10b981;">
                <div class="dd-sc-top">
                  <div>
                    <div style="font-weight:800;color:#6ee7b7;font-size:12px;">上振れ突破（配分 {scen_probs['bull']:.1f}%）</div>
                    <div style="font-size:10.5px;color:#cbd5e1;margin-top:2px;">トリガー: <b>{_fmt_cur(active_bull_trig, is_jp)}</b> 超え（FPT {scen_probs['fpt_bull_pct']:.1f}%）</div>
                  </div>
                  <div style="text-align:right;flex-shrink:0;">
                    <div class="dd-sc-price" style="color:#6ee7b7;">{_fmt_cur(active_bull_tgt, is_jp)}</div>
                    <div class="dd-sc-pct" style="color:#10b981;">{bp:+.2f}%</div>
                  </div>
                </div>
                <div class="dd-sc-bar-bg"><div class="dd-sc-bar-fill" style="width:{scen_probs['bull']:.1f}%;background:#10b981;"></div></div>
              </div>
              <div class="dd-sc-card" style="border-left:4px solid #38bdf8;">
                <div class="dd-sc-top">
                  <div>
                    <div style="font-weight:800;color:#7dd3fc;font-size:12px;">標準レンジ・窓埋（配分 {mid_sc_prob:.1f}%）</div>
                    <div style="font-size:10.5px;color:#cbd5e1;margin-top:2px;">押目 <b>{active_dip_time}</b> ({_fmt_cur(active_dip_px, is_jp)}) → 高値 <b>{active_peak_time}</b></div>
                  </div>
                  <div style="text-align:right;flex-shrink:0;">
                    <div class="dd-sc-price" style="color:#7dd3fc;">{_fmt_cur(active_close_px, is_jp)}</div>
                    <div class="dd-sc-pct" style="color:#38bdf8;">{active_close_chg:+.2f}%</div>
                  </div>
                </div>
                <div class="dd-sc-bar-bg"><div class="dd-sc-bar-fill" style="width:{mid_sc_prob:.1f}%;background:#38bdf8;"></div></div>
              </div>
              <div class="dd-sc-card" style="border-left:4px solid #ef4444;">
                <div class="dd-sc-top">
                  <div>
                    <div style="font-weight:800;color:#fca5a5;font-size:12px;">下振れ崩壊（配分 {scen_probs['bear']:.1f}%）</div>
                    <div style="font-size:10.5px;color:#cbd5e1;margin-top:2px;">トリガー: <b>{_fmt_cur(active_bear_trig, is_jp)}</b> 割れ（FPT {scen_probs['fpt_bear_pct']:.1f}%）</div>
                  </div>
                  <div style="text-align:right;flex-shrink:0;">
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

            top3_parts = []
            for lbl, val in ranked_factors[:3]:
                v_col = "#10b981" if val >= 0 else "#ef4444"
                top3_parts.append(
                    f'<div class="dd-factor-row"><span>{html.escape(lbl)}</span>'
                    f'<span style="font-family:JetBrains Mono,monospace;color:{v_col};">{val:+.2f}%</span></div>'
                )
            top3_html = "".join(top3_parts)
            close_chg_col = "#10b981" if active_close_chg >= 0 else "#ef4444"
            st.markdown(f"""
            <div class="dd-dark-box">
              <div style="font-size:10.5px;font-weight:800;color:#38bdf8;margin-bottom:4px;">KEY DRIVERS // 主要寄与 Top3（{html.escape(we['active_cluster'])}・{we['active_regime']}脳 N={we['cluster_n']} / 累計{we['updates_count']}回）</div>
              {top3_html}
              <div class="dd-factor-row"><span>合成・寄付き予測 → 大引け予測</span><span style="font-family:'JetBrains Mono',monospace;color:{close_chg_col};">{active_open_gap_pct:+.2f}% → {active_close_chg:+.2f}%</span></div>
            </div>
            """, unsafe_allow_html=True)

            with st.expander("🔬 全ファクター内訳（17項目）＆ クラスタ別3脳SGD進化重み", expanded=False):
                b5m_status = "有効" if traj["has_bench_5m"] else "フォールバック"
                ld_date = html.escape(str(ld.get("date", "-")))
                ld_cluster = html.escape(str(ld.get("cluster", "-")))
                ld_regime = html.escape(str(ld.get("regime", "NEUTRAL")))
                ld_open_err = float(ld.get("open_err_pct", 0.0))
                ld_intra_err = float(ld.get("intraday_err_pct", 0.0))
                ld_culp_o = html.escape(str(ld.get("culprit_open", "-")))
                ld_culp_i = html.escape(str(ld.get("culprit_intra", "-")))

                lm_info = traj.get("lab_mods", {})
                if lm_info.get("has_lab"):
                    caution_tag = " / 監査官警戒減衰" if lm_info.get("council_caution") else ""
                    vpin_disp = f"{lm_info['vpin_val']:.2f}" if lm_info.get("vpin_val") is not None else "-"
                    lab_mod_str = f"信頼度×{lm_info.get('lab_trust_mult', 1.0):.2f} / VPIN={vpin_disp}(幅×{lm_info.get('vpin_vboost', 1.0):.2f}){caution_tag}"
                else:
                    lab_mod_str = "単体検索（デフォルト×1.00）"

                vc_str = "有効（累積出来高比例）" if traj.get("vol_clock_active") else "線形時間フォールバック"
                lj_str = f"σ={traj.get('lunch_jump_std_pct', 0.0):.2f}% / 後場Gap補正={traj.get('lunch_gap_adj_pct', 0.0):+.2f}%" if is_jp else "米国市場（昼休みなし）"
                ml_info_d = traj.get("ml_3way_model", {})
                ml_n_cnt = int(ml_info_d.get("n_samples", 0))
                ml_stat_str = f"稼働中（N={ml_n_cnt}本学習済）" if ml_info_d.get("fitted") else f"サンプル蓄積中（N={ml_n_cnt}/60本）"
                exp_stat_str = f"稼働中（{exp_reg['label']} / 紫線降格・レジサポ反転済）" if exp_active else "通常レジーム（朝ロック基準維持）"

                c_macro = "#10b981" if f["macro_gap_pct"] >= 0 else "#ef4444"
                c_fx = "#10b981" if f["fx_gap_pct"] >= 0 else "#ef4444"
                c_news = "#10b981" if f["news_gap_pct"] >= 0 else "#ef4444"
                c_whale = "#10b981" if f["whale_gap_pct"] >= 0 else "#ef4444"
                c_lab = "#10b981" if f["lab_bias_pct"] >= 0 else "#ef4444"
                c_dw = "#10b981" if f["dow_wick_pct"] >= 0 else "#ef4444"
                c_cal = "#10b981" if f["calib_pct"] >= 0 else "#ef4444"
                c_lv = "#10b981" if f["live_vwap_pct"] >= 0 else "#ef4444"

                st.markdown(f"""
                <div class="dd-dark-box" style="margin-bottom:8px;">
                  <div class="dd-factor-row"><span>EXPANSION レジーム解放ステータス</span><span style="font-family:'JetBrains Mono',monospace;color:{'#10b981' if exp_active else '#94a3b8'};">{html.escape(exp_stat_str)}</span></div>
                  <div class="dd-factor-row"><span>主連動（{html.escape(f['mkt_label'])} {f['mkt_diff']:+.2f}% × β{f['mkt_beta']:+.2f} × 重み{og_now['macro']:.2f}）</span><span style="font-family:'JetBrains Mono',monospace;color:{c_macro};">{f['macro_gap_pct']:+.2f}%</span></div>
                  <div class="dd-factor-row"><span>為替（ドル円 {f['fx_diff']:+.2f}% × β{f['fx_beta']:+.2f} × 重み{og_now['fx']:.2f}）</span><span style="font-family:'JetBrains Mono',monospace;color:{c_fx};">{f['fx_gap_pct']:+.2f}%</span></div>
                  <div class="dd-factor-row"><span>日英高信頼ニュース時間減衰スコア（一次 {news_res['tier1_cnt']}件・重み{og_now['news']:.2f}）</span><span style="font-family:'JetBrains Mono',monospace;color:{c_news};">{f['news_gap_pct']:+.2f}%</span></div>
                  <div class="dd-factor-row"><span>大口・インサイダー直近30日異変補正（重み{og_now['whale']:.2f}）</span><span style="font-family:'JetBrains Mono',monospace;color:{c_whale};">{f['whale_gap_pct']:+.2f}%</span></div>
                  <div class="dd-factor-row"><span>LAB上位足 方向性・期待度バイアス（寄付重み{og_now['lab_bias']:.2f} / 日中重み{idr_now['lab_bias']:.2f}）</span><span style="font-family:'JetBrains Mono',monospace;color:{c_lab};">{f['lab_bias_pct']:+.2f}%</span></div>
                  <div class="dd-factor-row"><span>LAB高度連動ステータス（22日PF/勝率・VPIN・監査官）</span><span style="font-family:'JetBrains Mono',monospace;color:#e9d5ff;">{html.escape(lab_mod_str)}</span></div>
                  <div class="dd-factor-row"><span>出来高時計（Volume Clock）進行エンジン</span><span style="font-family:'JetBrains Mono',monospace;color:#38bdf8;">{html.escape(vc_str)}</span></div>
                  <div class="dd-factor-row"><span>日本株 昼休みジャンプ分散 ＆ 後場ギャップ補正</span><span style="font-family:'JetBrains Mono',monospace;color:#fde047;">{html.escape(lj_str)}</span></div>
                  <div class="dd-factor-row"><span>短期30分3分岐 NumPy軽量ロジスティック回帰</span><span style="font-family:'JetBrains Mono',monospace;color:#c084fc;">{html.escape(ml_stat_str)}</span></div>
                  <div class="dd-factor-row"><span>指数ベータ分離5分足モデル（5m β={traj['bench_beta_5m']:+.2f} / ライブ指数追従 {f['bench_alpha_pct']:+.2f}%）</span><span style="font-family:'JetBrains Mono',monospace;color:#38bdf8;">{b5m_status}</span></div>
                  <div class="dd-factor-row"><span>HVNしこり壁 / 機関OB支持帯</span><span style="font-family:'JetBrains Mono',monospace;color:#c084fc;">HVN {hvn_str} / OB {ob_str}</span></div>
                  <div class="dd-factor-row"><span>対象日曜日エッジ ＋ 直近5日ヒゲ圧力補正</span><span style="font-family:'JetBrains Mono',monospace;color:{c_dw};">{f['dow_wick_pct']:+.2f}%</span></div>
                  <div class="dd-factor-row"><span>台帳自己学習キャリブレーション（過去{f['calib_n']}日）</span><span style="font-family:'JetBrains Mono',monospace;color:{c_cal};">{f['calib_pct']:+.2f}%</span></div>
                  <div class="dd-factor-row"><span>場中VWAP・30分勢い・初動15分Gap・指数α補正</span><span style="font-family:'JetBrains Mono',monospace;color:{c_lv};">{f['live_vwap_pct']:+.2f}%</span></div>
                  <div class="dd-factor-row"><span>k-NN複合類似日マッチ（指数分離ATR正規化＋コサイン＋RVOL）</span><span style="font-family:'JetBrains Mono',monospace;color:#7dd3fc;">{html.escape(knn_dates_str)}</span></div>
                  <div class="dd-factor-row"><span>クラスタSGD誤差（{ld_date} / {ld_cluster}・{ld_regime}脳）</span><span style="font-family:'JetBrains Mono',monospace;color:#fde047;">寄付 {ld_open_err:+.2f}% / 日中残差 {ld_intra_err:+.2f}%</span></div>
                  <div class="dd-factor-row"><span>直近の最大誤差犯人ファクター（過大/過小特定）</span><span style="font-family:'JetBrains Mono',monospace;color:#fca5a5;">寄付:{ld_culp_o} / 日中:{ld_culp_i}</span></div>
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

        # =====================================================================
        # タブ2（マクロβ・曜日）
        # =====================================================================
        with t2:
            d_cells_parts = []
            for d in dow_stats:
                is_nxt = (d["dow"] == next_wd)
                cell_st = "border:1.5px solid #fde047;background:rgba(250,204,21,0.12);" if is_nxt else ""
                lbl_c = "#fde047" if is_nxt else "#94a3b8"
                nxt_tag = "★対象" if is_nxt else ""
                avg_c = "#10b981" if d["avg"] >= 0 else "#ef4444"
                d_cells_parts.append(
                    f'<div class="dd-dow-cell" style="{cell_st}">'
                    f'<div style="font-size:10px;color:{lbl_c};font-weight:800;">{d["label"]}曜 {nxt_tag}</div>'
                    f'<div style="font-family:JetBrains Mono,monospace;font-size:12.5px;font-weight:800;color:{avg_c};margin-top:2px;">{d["avg"]:+.2f}%</div>'
                    f'<div style="font-size:9.5px;color:#cbd5e1;">勝率 {d["wr"]}%</div></div>'
                )
            d_cells = "".join(d_cells_parts)
            st.markdown(f'<div class="dd-dark-box"><b>DAY-OF-WEEK EDGE // 曜日別アノマリー（過去1年実測・対象日={traj["target_date"]}）</b><div class="dd-dow-grid">{d_cells}</div></div>', unsafe_allow_html=True)

            hm_res = _compute_dow_intraday_heatmap(df_5m, is_jp)
            if hm_res.get("valid"):
                best_b = hm_res.get("best")
                worst_b = hm_res.get("worst")
                b_txt = f"🏆 ベスト: <b>{html.escape(best_b[1])}</b> ({best_b[0]:+.2f}% / 勝率{best_b[2]}% / N={best_b[3]})" if best_b else ""
                w_txt = f"📉 ワースト: <b>{html.escape(worst_b[1])}</b> ({worst_b[0]:+.2f}% / 勝率{worst_b[2]}% / N={worst_b[3]})" if worst_b else ""
                st.markdown("##### 🔥 曜日 × 30分時間帯 期待値ヒートマップ（過去1ヶ月5分足集計）")
                if b_txt or w_txt:
                    st.markdown(f'<div class="dd-dark-box" style="padding:7px 10px;margin-bottom:6px;font-size:11px;">{b_txt}　｜　{w_txt}</div>', unsafe_allow_html=True)
                _render_echarts({
                    "backgroundColor": "#070b14",
                    "tooltip": {
                        "position": "top",
                        "backgroundColor": "rgba(7,11,20,0.92)",
                        "borderColor": "#38bdf8",
                        "textStyle": {"color": "#f8fafc", "fontSize": 10.5, "fontFamily": "JetBrains Mono, monospace"},
                    },
                    "grid": {"top": 10, "bottom": 52, "left": 8, "right": 14, "containLabel": True},
                    "xAxis": {
                        "type": "category",
                        "data": hm_res["x_labels"],
                        "axisLabel": {"color": "#94a3b8", "fontSize": 9, "interval": 0, "rotate": 35, "hideOverlap": True},
                        "splitArea": {"show": True},
                    },
                    "yAxis": {
                        "type": "category",
                        "data": hm_res["y_labels"],
                        "axisLabel": {"color": "#e2e8f0", "fontSize": 10, "fontWeight": "bold"},
                        "splitArea": {"show": True},
                    },
                    "visualMap": {
                        "min": -hm_res["vmax"],
                        "max": hm_res["vmax"],
                        "calculable": False,
                        "orient": "horizontal",
                        "left": "center",
                        "bottom": 0,
                        "itemWidth": 10,
                        "itemHeight": 90,
                        "textStyle": {"color": "#94a3b8", "fontSize": 9},
                        "inRange": {"color": ["#dc2626", "#1e293b", "#10b981"]},
                    },
                    "series": [{
                        "name": "30分期待値",
                        "type": "heatmap",
                        "data": hm_res["data"],
                        "label": {"show": False},
                        "emphasis": {"itemStyle": {"borderColor": "#ffffff", "borderWidth": 1}},
                    }],
                }, height=230, chart_key=f"dd_hm_{fc}")

            if macro_sens:
                top_mk_key = macro_sens[0]["key"]
                rc_res = _compute_rolling_macro_corr(df_1d["Close"], macro_data.get(top_mk_key, {}))
                if rc_res.get("valid"):
                    dec_badge = ' <span style="background:rgba(245,158,11,0.22);border:1px solid #f59e0b;color:#fde047;padding:1px 6px;border-radius:99px;font-size:10px;font-weight:800;">⚡ デカップリング検知（個別材料主導相場）</span>' if rc_res.get("decoupled") else ""
                    st.markdown(f"##### 📈 ローリング相関（20日 vs 60日）＆ 20日β推移 — {html.escape(rc_res['label'])}{dec_badge}", unsafe_allow_html=True)
                    _render_echarts({
                        "backgroundColor": "#070b14",
                        "tooltip": {"trigger": "axis", "backgroundColor": "rgba(7,11,20,0.92)", "borderColor": "rgba(56,189,248,0.45)", "textStyle": {"color": "#f8fafc", "fontSize": 10}},
                        "legend": {"type": "scroll", "data": ["20日相関", "60日相関", "20日β"], "textStyle": {"color": "#cbd5e1", "fontSize": 9.5}, "top": 2},
                        "grid": {"top": 30, "bottom": 22, "left": 8, "right": 34, "containLabel": True},
                        "xAxis": {"type": "category", "boundaryGap": False, "data": rc_res["dates"], "axisLabel": {"color": "#94a3b8", "fontSize": 9, "interval": "auto", "hideOverlap": True}},
                        "yAxis": [
                            {"type": "value", "min": -1, "max": 1, "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.05)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9}},
                            {"type": "value", "position": "right", "scale": True, "splitLine": {"show": False}, "axisLabel": {"color": "#fbbf24", "fontSize": 8.5}},
                        ],
                        "series": [
                            {"name": "20日相関", "type": "line", "yAxisIndex": 0, "data": rc_res["c20"], "itemStyle": {"color": "#38bdf8"}, "lineStyle": {"color": "#38bdf8", "width": 2.0}, "showSymbol": False},
                            {"name": "60日相関", "type": "line", "yAxisIndex": 0, "data": rc_res["c60"], "itemStyle": {"color": "#c084fc"}, "lineStyle": {"color": "#c084fc", "width": 1.6, "type": "dashed"}, "showSymbol": False},
                            {"name": "20日β", "type": "line", "yAxisIndex": 1, "data": rc_res["b20"], "itemStyle": {"color": "#fbbf24"}, "lineStyle": {"color": "rgba(251,191,36,0.55)", "width": 1.2}, "areaStyle": {"color": "rgba(251,191,36,0.10)"}, "showSymbol": False},
                        ],
                    }, height=225, chart_key=f"dd_rc_{fc}")

                st.markdown("##### マクロ感応度マトリクス（過去90営業日の相関係数）")
                _render_echarts({"backgroundColor": "#070b14", "tooltip": {"trigger": "axis"}, "grid": {"top": 12, "bottom": 20, "left": 6, "right": 14, "containLabel": True}, "xAxis": {"type": "value", "min": -1, "max": 1, "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.06)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9.5}}, "yAxis": {"type": "category", "data": [x["label"] for x in macro_sens][::-1], "axisLabel": {"color": "#e2e8f0", "fontSize": 10.5}}, "series": [{"type": "bar", "data": [{"value": x["corr"], "itemStyle": {"color": "#10b981" if x["corr"] >= 0 else "#ef4444"}} for x in macro_sens[::-1]]}]}, height=215, chart_key=f"dd_ms_{fc}")

            eh = [e for e in data["earnings_hist"] if e["est"] is not None or e["rep"] is not None]
            if eh:
                st.markdown("##### 決算サプライズ（予想EPS vs 実績EPS）")
                eh_r = eh[::-1]
                _render_echarts({"backgroundColor": "#070b14", "tooltip": {"trigger": "axis"}, "legend": {"type": "scroll", "data": ["予想EPS", "実績EPS"], "textStyle": {"color": "#cbd5e1", "fontSize": 10}, "top": 2}, "grid": {"top": 30, "bottom": 20, "left": 6, "right": 10, "containLabel": True}, "xAxis": {"type": "category", "data": [e["date"][2:7] for e in eh_r], "axisLabel": {"color": "#94a3b8", "fontSize": 9.5}}, "yAxis": {"type": "value", "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.06)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9.5}}, "series": [{"name": "予想EPS", "type": "bar", "data": [e["est"] for e in eh_r], "itemStyle": {"color": "#64748b"}}, {"name": "実績EPS", "type": "bar", "data": [{"value": e["rep"], "itemStyle": {"color": "#10b981" if (e["surp"] or 0) >= 0 else "#ef4444"}} for e in eh_r]}]}, height=205, chart_key=f"dd_eh_{fc}")

                pead_res = _compute_earnings_pead(df_1d, data["earnings_hist"])
                if pead_res.get("valid"):
                    st.markdown("##### ⚡ 決算PEAD（翌日ギャップ％ vs 決算後5日累計リターン％）")
                    _render_echarts({
                        "backgroundColor": "#070b14",
                        "tooltip": {"trigger": "axis", "backgroundColor": "rgba(7,11,20,0.92)", "borderColor": "rgba(56,189,248,0.45)", "textStyle": {"color": "#f8fafc", "fontSize": 10}},
                        "legend": {"type": "scroll", "data": ["翌日ギャップ%", "5日累計%"], "textStyle": {"color": "#cbd5e1", "fontSize": 9.5}, "top": 2},
                        "grid": {"top": 30, "bottom": 20, "left": 6, "right": 14, "containLabel": True},
                        "xAxis": {"type": "category", "data": pead_res["dates"], "axisLabel": {"color": "#94a3b8", "fontSize": 9.5, "hideOverlap": True}},
                        "yAxis": {"type": "value", "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.06)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9, "formatter": "{value}%"}},
                        "series": [
                            {"name": "翌日ギャップ%", "type": "bar", "data": [{"value": g, "itemStyle": {"color": "rgba(16,185,129,0.75)" if g >= 0 else "rgba(239,68,68,0.75)"}} for g in pead_res["gaps"]], "barMaxWidth": 20},
                            {"name": "5日累計%", "type": "line", "data": pead_res["drifts5"], "itemStyle": {"color": "#38bdf8"}, "lineStyle": {"color": "#38bdf8", "width": 2.2}, "symbol": "circle", "symbolSize": 7},
                        ],
                    }, height=205, chart_key=f"dd_pead_{fc}")

        # =====================================================================
        # タブ3（財務・大口株主）
        # =====================================================================
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
                _render_echarts({"backgroundColor": "#070b14", "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}}, "grid": {"top": 10, "bottom": 18, "left": 4, "right": 96, "containLabel": True}, "xAxis": {"type": "value", "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.06)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9, "formatter": "{value}%"}}, "yAxis": {"type": "category", "data": [f"#{len(rev_h)-i} {x['holder'][:14]}" for i, x in enumerate(rev_h)], "axisLabel": {"color": "#f8fafc", "fontSize": 9.5}}, "series": [{"name": "保有比率", "type": "bar", "data": b_data, "barMaxWidth": 15}]}, height=max(210, len(rev_h) * 28), chart_key=f"dd_inst_{fc}")
            elif is_jp:
                st.link_button(f"🏛️ 株探で {short_code} の大株主一覧を見る", f"https://kabutan.jp/stock/holder?code={short_code}", use_container_width=True)

            axes_r, vals_r, miss_r = _compute_real_5axis(info, vp["overhead_pct"], len(gov_risks))
            if len(axes_r) >= 3:
                _render_echarts({"backgroundColor": "#070b14", "radar": {"radius": "62%", "indicator": axes_r, "axisName": {"color": "#cbd5e1", "fontSize": 10.5}}, "series": [{"type": "radar", "data": [{"value": vals_r, "name": "実測体力", "itemStyle": {"color": "#38bdf8"}, "areaStyle": {"color": "rgba(56,189,248,0.28)"}}]}]}, height=215, chart_key=f"dd_rad_{fc}")
            if miss_r:
                st.caption(f"※ APIデータ未提供のため除外した項目（嘘なし評価）: {', '.join(miss_r)}")

            _render_valuation_gauges(info, is_jp)

            vp28 = _compute_hires_vp_28(df_1d, curr_px, is_jp)
            if vp28.get("valid"):
                st.markdown("##### 📊 高解像度 Volume Profile（28分割・VA70% / POC / 短期20日vs中期60日減衰）")
                st.markdown(f"""
                <div class="dd-ev-grid" style="margin-top:4px;margin-bottom:6px;">
                  <div class="dd-ev-cell"><div class="dd-metric-lbl">VAH (VA上限)</div><div style="font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:800;color:#38bdf8;">{_fmt_cur(vp28['vah_px'], is_jp)}</div></div>
                  <div class="dd-ev-cell"><div class="dd-metric-lbl">POC (最大出来高)</div><div style="font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:800;color:#fbbf24;">{_fmt_cur(vp28['poc_px'], is_jp)}</div></div>
                  <div class="dd-ev-cell"><div class="dd-metric-lbl">VAL (VA下限)</div><div style="font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:800;color:#6ee7b7;">{_fmt_cur(vp28['val_px'], is_jp)}</div></div>
                </div>
                """, unsafe_allow_html=True)
                _render_echarts({
                    "backgroundColor": "#070b14",
                    "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}, "backgroundColor": "rgba(7,11,20,0.92)", "borderColor": "rgba(56,189,248,0.45)", "textStyle": {"color": "#f8fafc", "fontSize": 10}},
                    "legend": {"type": "scroll", "data": ["直近20日出来高", "中期60日減衰"], "textStyle": {"color": "#cbd5e1", "fontSize": 9.5}, "top": 2},
                    "grid": {"top": 28, "bottom": 20, "left": 6, "right": 14, "containLabel": True},
                    "xAxis": {"type": "value", "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.06)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9}},
                    "yAxis": {"type": "category", "data": vp28["labels"], "axisLabel": {"color": "#cbd5e1", "fontSize": 8.5, "interval": 1, "hideOverlap": True}},
                    "series": [
                        {
                            "name": "直近20日出来高",
                            "type": "bar",
                            "stack": "vp28_stack",
                            "data": vp28["short_bars"],
                            "barMaxWidth": 9,
                            "markLine": {
                                "symbol": ["none", "none"],
                                "silent": True,
                                "data": [{"yAxis": vp28["curr_bin_idx"], "lineStyle": {"color": "#ffffff", "type": "dashed", "width": 1.6}, "label": {"formatter": "現在値", "color": "#ffffff", "fontSize": 9, "fontWeight": "bold", "position": "insideEndTop"}}],
                            },
                        },
                        {
                            "name": "中期60日減衰",
                            "type": "bar",
                            "stack": "vp28_stack",
                            "data": vp28["mid_bars"],
                            "barMaxWidth": 9,
                        },
                    ],
                }, height=310, chart_key=f"dd_vp28_{fc}")

            sq_res = _compute_bbw_squeeze(df_1d)
            if sq_res.get("valid"):
                sq_badge = (
                    f' <span style="background:rgba(239,68,68,0.22);border:1px solid #ef4444;color:#fecaca;padding:1px 6px;border-radius:99px;font-size:10px;font-weight:800;">'
                    f'🔥 スクイーズ警戒（BBW下位{sq_res["cur_pct"]}% / ブレイク前兆）</span>'
                    if sq_res.get("is_squeeze") else
                    f' <span style="color:#94a3b8;font-size:10px;">(BBWパーセンタイル {sq_res["cur_pct"]}% / 幅 {sq_res["cur_bbw"]}%)</span>'
                )
                st.markdown(f"##### 📉 ボラティリティ・スクイーズ ＆ BBW推移（日足6ヶ月）{sq_badge}", unsafe_allow_html=True)
                _render_echarts({
                    "backgroundColor": "#070b14",
                    "tooltip": {"trigger": "axis", "backgroundColor": "rgba(7,11,20,0.92)", "borderColor": "rgba(56,189,248,0.45)", "textStyle": {"color": "#f8fafc", "fontSize": 10}},
                    "legend": {"type": "scroll", "data": ["日足終値", "20MA", "BBW順位%"], "textStyle": {"color": "#cbd5e1", "fontSize": 9.5}, "top": 2},
                    "axisPointer": {"link": [{"xAxisIndex": "all"}]},
                    "grid": [
                        {"top": 28, "height": "52%", "left": 6, "right": 14, "containLabel": True},
                        {"top": "70%", "height": "20%", "left": 6, "right": 14, "containLabel": True},
                    ],
                    "xAxis": [
                        {"type": "category", "gridIndex": 0, "boundaryGap": False, "data": sq_res["dates"], "axisLabel": {"show": False}},
                        {"type": "category", "gridIndex": 1, "boundaryGap": False, "data": sq_res["dates"], "axisLabel": {"color": "#94a3b8", "fontSize": 9, "interval": "auto", "hideOverlap": True}},
                    ],
                    "yAxis": [
                        {"type": "value", "gridIndex": 0, "position": "right", "scale": True, "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.05)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9}},
                        {"type": "value", "gridIndex": 1, "position": "right", "min": 0, "max": 100, "splitLine": {"show": False}, "axisLabel": {"color": "#f59e0b", "fontSize": 8, "formatter": "{value}%"}},
                    ],
                    "series": [
                        {"name": "bb_lo", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": sq_res["lower"], "stack": "bb_fan", "lineStyle": {"opacity": 0}, "showSymbol": False, "silent": True},
                        {"name": "BB±2σ帯", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": sq_res["band_diff"], "stack": "bb_fan", "lineStyle": {"opacity": 0}, "areaStyle": {"color": "rgba(99,102,241,0.12)"}, "showSymbol": False, "silent": True},
                        {"name": "20MA", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": sq_res["ma20"], "itemStyle": {"color": "#c084fc"}, "lineStyle": {"color": "#c084fc", "width": 1.2, "type": "dashed"}, "showSymbol": False},
                        {"name": "日足終値", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0, "data": sq_res["closes"], "itemStyle": {"color": "#38bdf8"}, "lineStyle": {"color": "#38bdf8", "width": 2.0}, "showSymbol": False},
                        {"name": "BBW順位%", "type": "bar", "xAxisIndex": 1, "yAxisIndex": 1, "data": [{"value": v, "itemStyle": {"color": "#ef4444" if v <= 20 else ("#f59e0b" if v <= 45 else "rgba(56,189,248,0.5)")}} for v in sq_res["bbw_pct_series"]], "barMaxWidth": 4},
                    ],
                }, height=280, is_dual_grid=True, chart_key=f"dd_sq_{fc}")

            ins_tx = data.get("insider_tx") or []
            if ins_tx and df_1d is not None and not df_1d.empty:
                d1_dates = [idx.strftime("%Y-%m-%d") for idx in df_1d.index]
                d1_closes = [round(float(x), 2) for x in df_1d["Close"].values]
                px_by_date = dict(zip(d1_dates, d1_closes))
                buy_pts, sell_pts = [], []
                for tx in ins_tx:
                    td_s = str(tx.get("date") or "")[:10]
                    if td_s in px_by_date:
                        t_u = str(tx.get("text") or "").upper()
                        pt_v = [td_s[5:], px_by_date[td_s]]
                        if "PURCHASE" in t_u or "BUY" in t_u:
                            buy_pts.append(pt_v)
                        elif "SALE" in t_u or "SELL" in t_u:
                            sell_pts.append(pt_v)
                if buy_pts or sell_pts:
                    st.markdown("##### 🕵️ インサイダー売買プロット（日足終値上マーカー）")
                    ins_series = [
                        {"name": "日足終値", "type": "line", "data": d1_closes, "itemStyle": {"color": "#94a3b8"}, "lineStyle": {"color": "#94a3b8", "width": 1.6}, "showSymbol": False},
                    ]
                    if buy_pts:
                        ins_series.append({"name": "役員買付▲", "type": "scatter", "symbol": "triangle", "symbolSize": 10, "itemStyle": {"color": "#10b981"}, "data": buy_pts})
                    if sell_pts:
                        ins_series.append({"name": "役員売却▼", "type": "scatter", "symbol": "diamond", "symbolSize": 9, "itemStyle": {"color": "#ef4444"}, "data": sell_pts})
                    _render_echarts({
                        "backgroundColor": "#070b14",
                        "tooltip": {"trigger": "item", "backgroundColor": "rgba(7,11,20,0.92)", "textStyle": {"color": "#f8fafc", "fontSize": 10}},
                        "legend": {"type": "scroll", "data": [s["name"] for s in ins_series], "textStyle": {"color": "#cbd5e1", "fontSize": 9.5}, "top": 2},
                        "grid": {"top": 28, "bottom": 20, "left": 6, "right": 14, "containLabel": True},
                        "xAxis": {"type": "category", "data": [d[5:] for d in d1_dates], "axisLabel": {"color": "#94a3b8", "fontSize": 9, "interval": "auto", "hideOverlap": True}},
                        "yAxis": {"type": "value", "position": "right", "scale": True, "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.05)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9}},
                        "series": ins_series,
                    }, height=205, chart_key=f"dd_ins_{fc}")

        # =====================================================================
        # タブ4（リスク・AIメモ）
        # =====================================================================
        with t4:
            _render_echarts({"backgroundColor": "#070b14", "series": [{"type": "gauge", "startAngle": 180, "endAngle": 0, "min": 0, "max": 100, "splitNumber": 5, "center": ["50%", "74%"], "radius": "112%", "axisLine": {"lineStyle": {"width": 16, "color": [[0.2, "#dc2626"], [0.4, "#f97316"], [0.6, "#38bdf8"], [0.8, "#10b981"], [1.0, "#059669"]]}}, "pointer": {"icon": "path://M12.8,0.7l12,40.1H0.7L12.8,0.7z", "length": "52%", "width": 10, "offsetCenter": [0, "-12%"], "itemStyle": {"color": "#f8fafc", "shadowBlur": 8, "shadowColor": "rgba(56,189,248,0.8)"}}, "anchor": {"show": True, "showAbove": True, "size": 14, "itemStyle": {"color": "#38bdf8", "borderWidth": 2, "borderColor": "#fff"}}, "axisTick": {"length": 6, "lineStyle": {"color": "auto", "width": 1.5}}, "splitLine": {"length": 12, "lineStyle": {"color": "auto", "width": 2.5}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9.5, "distance": -36}, "title": {"offsetCenter": [0, "18%"], "fontSize": 10.5, "color": "#7dd3fc", "fontWeight": "bold"}, "detail": {"fontSize": 26, "fontWeight": "bold", "offsetCenter": [0, "-3%"], "valueAnimation": True, "color": "#ffffff", "formatter": "{value}"}, "data": [{"value": comp_score, "name": meter_lbl}]}]}, height=225, chart_key=f"dd_gg_{fc}")

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
                news_res["tier1_cnt"], len(gov_risks), whale_anom["summary"], upside_str, lab_note, api_k,
                lab_deep_ctx=lab_deep_ctx, trade_style=in_style, memo_nonce=memo_nonce
            )
            memo_body_html = html.escape(m_txt).replace("\n", "<br>")
            st.markdown(f'<div class="dd-memo-box"><div style="font-size:10.5px;color:#c084fc;font-weight:800;margin-bottom:6px;">{html.escape(m_src)}</div>{memo_body_html}</div>', unsafe_allow_html=True)
            if st.button("🔄 AIインベストメントメモを再生成", key="dd_regen_memo_btn", use_container_width=True):
                st.session_state["dd_memo_nonce"] = memo_nonce + 1
                st.rerun()

            tl_72h = _build_news_72h_timeline(news_res.get("all_72h") or news_res.get("items") or [])
            if tl_72h.get("valid"):
                st.markdown("##### 🕒 72時間ニュース密度＆センチメント推移（12時間刻み）")
                _render_echarts({
                    "backgroundColor": "#070b14",
                    "tooltip": {"trigger": "axis", "backgroundColor": "rgba(7,11,20,0.92)", "borderColor": "rgba(56,189,248,0.45)", "textStyle": {"color": "#f8fafc", "fontSize": 10}},
                    "legend": {"type": "scroll", "data": ["報道本数", "ネット強弱スコア"], "textStyle": {"color": "#cbd5e1", "fontSize": 9.5}, "top": 2},
                    "grid": {"top": 28, "bottom": 20, "left": 6, "right": 28, "containLabel": True},
                    "xAxis": {"type": "category", "data": tl_72h["labels"], "axisLabel": {"color": "#94a3b8", "fontSize": 9, "hideOverlap": True}},
                    "yAxis": [
                        {"type": "value", "minInterval": 1, "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.05)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9}},
                        {"type": "value", "position": "right", "splitLine": {"show": False}, "axisLabel": {"color": "#38bdf8", "fontSize": 8.5}},
                    ],
                    "series": [
                        {"name": "報道本数", "type": "bar", "yAxisIndex": 0, "data": tl_72h["counts"], "itemStyle": {"color": "rgba(168,85,247,0.55)", "borderRadius": [3, 3, 0, 0]}, "barMaxWidth": 22},
                        {"name": "ネット強弱スコア", "type": "line", "yAxisIndex": 1, "data": tl_72h["scores"], "itemStyle": {"color": "#10b981"}, "lineStyle": {"color": "#10b981", "width": 2.0}, "symbol": "circle", "symbolSize": 6},
                    ],
                }, height=195, chart_key=f"dd_tl72_{fc}")

            if gov_risks:
                st.markdown(f'<div class="dd-warn-box"><b>ガバナンス・不祥事・訴訟関連ヒット ({len(gov_risks)}件)</b><br>' + "<br>".join([f"・{html.escape(x)}" for x in gov_risks]) + '</div>', unsafe_allow_html=True)
            else:
                lang_scope = "日英" if not is_jp else "国内"
                st.markdown(f'<div class="dd-quant-box"><b>ガバナンス・不祥事監査: クリーン（{lang_scope}72h報道）</b><br>直近72時間以内のニュースにおいて不祥事・不正・訴訟などの特異リスクシグナルは検知されていません。</div>', unsafe_allow_html=True)

            if news_res["items"]:
                n_parts = []
                for it in news_res["items"]:
                    tr_col = "#fde047" if it["trust"] == "S" else ("#38bdf8" if it["trust"] == "A" else "#64748b")
                    s_col = "#10b981" if it["sent"] == "POS" else ("#ef4444" if it["sent"] == "NEG" else "#94a3b8")
                    src_lbl = html.escape(it["source"] or "Wire")
                    pub_lbl = html.escape(it["pub"])
                    brk_tag = '<span style="background:rgba(239,68,68,0.25);color:#fecaca;font-weight:800;font-size:9px;padding:0 4px;border-radius:3px;margin-right:4px;">速報</span>' if it.get("is_breaking") else ""
                    cat_tag = f'<span style="background:rgba(250,204,21,0.2);color:#fde047;font-weight:800;font-size:9px;padding:0 4px;border-radius:3px;margin-right:4px;">材料:{html.escape(it["catalyst_kw"])}</span>' if it.get("catalyst_kw") else ""
                    n_parts.append(
                        f'<div style="margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid rgba(148,163,184,0.12);">'
                        f'{brk_tag}{cat_tag}'
                        f'<span style="color:{tr_col};font-weight:800;font-size:10px;border:1px solid;padding:0 4px;border-radius:3px;margin-right:4px;">信頼度{it["trust"]}/{it["lang"]}</span>'
                        f'<span style="color:{s_col};font-weight:800;font-size:10px;margin-right:4px;">[{it["sent"]}]</span>'
                        f'<span style="color:#94a3b8;font-size:9.5px;margin-right:4px;">(鮮度重み {it["decay_w"]:.1f})</span>'
                        f'<a href="{html.escape(it["link"])}" target="_blank" style="color:#e2e8f0;text-decoration:none;font-weight:600;">{html.escape(it["title"])}</a> '
                        f'<span style="color:#64748b;font-size:10px;">({src_lbl} / {pub_lbl})</span></div>'
                    )
                n_html = "".join(n_parts)
                st.markdown(f'<div class="dd-dark-box"><b>GLOBAL INTELLIGENCE FEED // 日英高信頼ニュース（有効報道 {news_res["fresh_cnt"]}件 / 一次 {news_res["tier1_cnt"]}件）</b><br><br>{n_html}</div>', unsafe_allow_html=True)

            we_d = traj["weights_evolution"]
            def_br = _make_default_brain(we_d["active_regime"])
            og_keys_lbl = ["始値:マクロ", "始値:為替", "始値:ニュース", "始値:大口", "始値:LAB"]
            og_keys_raw = ["macro", "fx", "news", "whale", "lab_bias"]
            def_og_vals = [round(float(def_br["open_gap"][k]), 3) for k in og_keys_raw]
            cur_og_vals = [round(float(we_d["open_gap"].get(k, def_br["open_gap"][k])), 3) for k in og_keys_raw]

            idr_keys_lbl = ["日中:ニュース×100", "日中:曜日", "日中:ヒゲ", "日中:校正", "日中:LAB"]
            idr_keys_raw = ["news", "dow", "wick", "calib", "lab_bias"]
            def_idr_vals = [round(float(def_br["intraday_drift"][k]) * (100.0 if k == "news" else 1.0), 3) for k in idr_keys_raw]
            cur_idr_vals = [round(float(we_d["intraday_drift"].get(k, def_br["intraday_drift"][k])) * (100.0 if k == "news" else 1.0), 3) for k in idr_keys_raw]

            st.markdown(f"##### 🧠 クオンツ自己進化監査（{html.escape(we_d['active_cluster'])}・{we_d['active_regime']}脳 / 累計更新 {we_d['updates_count']}回）")
            _render_echarts({
                "backgroundColor": "#070b14",
                "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}, "backgroundColor": "rgba(7,11,20,0.92)", "textStyle": {"color": "#f8fafc", "fontSize": 10}},
                "legend": {"type": "scroll", "data": ["初期事前重み", "現在学習重み"], "textStyle": {"color": "#cbd5e1", "fontSize": 9.5}, "top": 2},
                "grid": {"top": 28, "bottom": 22, "left": 6, "right": 14, "containLabel": True},
                "xAxis": {"type": "category", "data": og_keys_lbl + idr_keys_lbl, "axisLabel": {"color": "#94a3b8", "fontSize": 8.5, "interval": 0, "rotate": 30, "hideOverlap": True}},
                "yAxis": {"type": "value", "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.05)"}}, "axisLabel": {"color": "#94a3b8", "fontSize": 9}},
                "series": [
                    {"name": "初期事前重み", "type": "bar", "data": def_og_vals + def_idr_vals, "itemStyle": {"color": "rgba(148,163,184,0.45)"}, "barMaxWidth": 12},
                    {"name": "現在学習重み", "type": "bar", "data": cur_og_vals + cur_idr_vals, "itemStyle": {"color": "#38bdf8"}, "barMaxWidth": 12},
                ],
            }, height=225, chart_key=f"dd_sgd_{fc}")

            v_hist = traj.get("verify_hist_15") or []
            if len(v_hist) >= 3:
                st.markdown("##### 📊 直近15日・大引け確定ロック検証推移（収束率% vs 平均誤差%）")
                _render_echarts({
                    "backgroundColor": "#070b14",
                    "tooltip": {"trigger": "axis", "backgroundColor": "rgba(7,11,20,0.92)", "textStyle": {"color": "#f8fafc", "fontSize": 10}},
                    "legend": {"type": "scroll", "data": ["帯内収束率%", "平均誤差%"], "textStyle": {"color": "#cbd5e1", "fontSize": 9.5}, "top": 2},
                    "grid": {"top": 28, "bottom": 20, "left": 6, "right": 28, "containLabel": True},
                    "xAxis": {"type": "category", "data": [f"{r['date'][5:]}({r['code']})" for r in v_hist], "axisLabel": {"color": "#94a3b8", "fontSize": 8.5, "interval": "auto", "hideOverlap": True}},
                    "yAxis": [
                        {"type": "value", "min": 0, "max": 100, "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.05)"}}, "axisLabel": {"color": "#10b981", "fontSize": 9, "formatter": "{value}%"}},
                        {"type": "value", "position": "right", "splitLine": {"show": False}, "axisLabel": {"color": "#f59e0b", "fontSize": 8.5, "formatter": "{value}%"}},
                    ],
                    "series": [
                        {"name": "帯内収束率%", "type": "bar", "yAxisIndex": 0, "data": [r["cone"] for r in v_hist], "itemStyle": {"color": "rgba(16,185,129,0.55)", "borderRadius": [3, 3, 0, 0]}, "barMaxWidth": 16},
                        {"name": "平均誤差%", "type": "line", "yAxisIndex": 1, "data": [r["err"] for r in v_hist], "itemStyle": {"color": "#f59e0b"}, "lineStyle": {"color": "#f59e0b", "width": 2.0}, "symbol": "circle", "symbolSize": 6},
                    ],
                }, height=205, chart_key=f"dd_vh_{fc}")
            else:
                st.markdown(f'<div class="dd-dark-box" style="padding:8px 10px;font-size:11px;"><b>📊 日次検証推移:</b> 大引け確定済みロック検証データ蓄積中（現在 {len(v_hist)}件 / 3件以上で推移グラフを表示）</div>', unsafe_allow_html=True)

        dd_result = {
            "full_code": fc,
            "style": in_style,
            "comp_score": int(comp_score),
            "meter_lbl": str(meter_lbl),
            "mkt_regime": mkt_regime,
            "expansion_regime": exp_reg,
            "mtf_alignment": mtf_res,
            "pro_ref_levels": ref_levels,
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
            "short_horizon_3way": {
                "active": short_3way["active"],
                "horizon_min": short_3way["horizon"] * 5,
                "p_up": short_3way["p_up"],
                "p_flat": short_3way["p_flat"],
                "p_down": short_3way["p_down"],
                "ml_used": short_3way.get("ml_used", False),
                "ml_samples": short_3way.get("ml_samples", 0),
            },
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
            "vol_clock_active": traj.get("vol_clock_active", False),
            "lunch_jump_std_pct": traj.get("lunch_jump_std_pct", 0.0),
            "lunch_gap_adj_pct": traj.get("lunch_gap_adj_pct", 0.0),
            "lab_mods": traj.get("lab_mods", {}),
            "medoid_analog": {
                "date": traj.get("medoid_analog").get("date") if isinstance(traj.get("medoid_analog"), dict) else None,
                "gap_pct": traj.get("medoid_analog").get("gap_pct") if isinstance(traj.get("medoid_analog"), dict) else None,
                "amp_scale": traj.get("medoid_analog").get("amp_scale", 1.0) if isinstance(traj.get("medoid_analog"), dict) else None,
                "mode": traj.get("medoid_analog").get("mode") if isinstance(traj.get("medoid_analog"), dict) else None,
            },
            "vol_profile_meta": traj["vol_profile_meta"],
            "knn_match": {
                "matched_dates": traj["knn_match"]["matched_dates"],
                "mean_dist": traj["knn_match"]["mean_dist"],
            },
            "invalidation_alert": inv_al,
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
