import datetime
import json
import os
import sqlite3
import ssl
import urllib.parse
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "yamashishi_core.db"
WEIGHTS_PATH = ROOT_DIR / "weights_evolution.json"
REPORTS_DIR = ROOT_DIR / "reports"
LATEST_REPORT_PATH = REPORTS_DIR / "weekly_audit_latest.md"

WEIGHTS_KV_KEY = "dd_weights_evolution_v1"
LEDGER_KV_KEY = "dd_forecast_ledger_v9"

DEFAULT_WEIGHTS = {
    "version": 1,
    "lr": 0.03,
    "updates_count": 0,
    "last_updated": "",
    "learned_keys": [],
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
    "last_decomp": {
        "date": "-",
        "code": "-",
        "open_err_pct": 0.0,
        "intraday_err_pct": 0.0,
    },
}


def _env_or_secret(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _sb_headers(api_key: str) -> dict:
    return {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _sb_get(key: str):
    sb_url = _env_or_secret("SUPABASE_URL").rstrip("/")
    sb_key = _env_or_secret("SUPABASE_KEY")
    if not sb_url or not sb_key:
        return None
    try:
        q = f"{sb_url}/rest/v1/kv_store?key=eq.{urllib.parse.quote(key)}&select=val"
        req = urllib.request.Request(q, headers=_sb_headers(sb_key), method="GET")
        with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=8.0) as resp:
            rows = json.loads(resp.read().decode("utf-8"))
            if isinstance(rows, list) and rows and rows[0].get("val") is not None:
                raw_val = rows[0]["val"]
                return json.loads(raw_val) if isinstance(raw_val, str) else raw_val
    except Exception as exc:
        print(f"[WARN] Supabase GET failed for {key}: {exc}")
    return None


def _sb_upsert(key: str, val) -> None:
    sb_url = _env_or_secret("SUPABASE_URL").rstrip("/")
    sb_key = _env_or_secret("SUPABASE_KEY")
    if not sb_url or not sb_key:
        return
    try:
        url = f"{sb_url}/rest/v1/kv_store?on_conflict=key"
        headers = _sb_headers(sb_key)
        headers["Prefer"] = "resolution=merge-duplicates"
        payload = json.dumps(
            {
                "key": key,
                "val": json.dumps(val, ensure_ascii=False),
                "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
            ensure_ascii=False,
        ).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=8.0) as resp:
            resp.read()
    except Exception as exc:
        print(f"[WARN] Supabase UPSERT failed for {key}: {exc}")


def _sqlite_get(key: str):
    if not DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=8.0)
        cur = conn.cursor()
        cur.execute("SELECT val FROM kv_store WHERE key = ?", (key,))
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            return json.loads(row[0])
    except Exception as exc:
        print(f"[WARN] SQLite GET failed for {key}: {exc}")
    return None


def _merge_weights(raw: dict) -> dict:
    base = json.loads(json.dumps(DEFAULT_WEIGHTS))
    if not isinstance(raw, dict):
        return base
    for k in ("version", "lr", "updates_count", "last_updated"):
        if k in raw:
            base[k] = raw[k]
    if isinstance(raw.get("learned_keys"), list):
        base["learned_keys"] = list(dict.fromkeys(str(x) for x in raw["learned_keys"]))[-300:]
    if isinstance(raw.get("open_gap"), dict):
        for gk, gv in raw["open_gap"].items():
            if gk in base["open_gap"]:
                base["open_gap"][gk] = float(gv)
    if isinstance(raw.get("intraday_drift"), dict):
        for ik, iv in raw["intraday_drift"].items():
            if ik in base["intraday_drift"]:
                base["intraday_drift"][ik] = float(iv)
    if isinstance(raw.get("last_decomp"), dict):
        base["last_decomp"].update(raw["last_decomp"])
    return base


def _load_weights() -> dict:
    sb_w = _sb_get(WEIGHTS_KV_KEY)
    if isinstance(sb_w, dict) and sb_w:
        return _merge_weights(sb_w)
    if WEIGHTS_PATH.exists():
        try:
            disk_w = json.loads(WEIGHTS_PATH.read_text(encoding="utf-8"))
            if isinstance(disk_w, dict) and disk_w:
                return _merge_weights(disk_w)
        except Exception as exc:
            print(f"[WARN] Failed reading {WEIGHTS_PATH}: {exc}")
    db_w = _sqlite_get(WEIGHTS_KV_KEY)
    if isinstance(db_w, dict) and db_w:
        return _merge_weights(db_w)
    return json.loads(json.dumps(DEFAULT_WEIGHTS))


def _load_ledger() -> dict:
    sb_l = _sb_get(LEDGER_KV_KEY)
    if isinstance(sb_l, dict) and sb_l:
        return sb_l
    db_l = _sqlite_get(LEDGER_KV_KEY)
    if isinstance(db_l, dict) and db_l:
        return db_l
    return {}


def _fetch_actual_daily_bars(codes: list[str], start_date: str) -> dict[str, dict[str, tuple[float, float, float]]]:
    """yfinance経由で対象銘柄の日足(prev_close, open, close)を取得。ネットワーク制限時は空を返す。"""
    if not codes:
        return {}
    out: dict[str, dict[str, tuple[float, float, float]]] = {}
    try:
        import yfinance as yf  # type: ignore

        start_dt = (datetime.date.fromisoformat(start_date) - datetime.timedelta(days=10)).isoformat()
        raw = yf.download(
            codes,
            start=start_dt,
            interval="1d",
            auto_adjust=True,
            group_by="ticker",
            threads=True,
            progress=False,
            timeout=10.0,
        )
        if raw is None or raw.empty:
            return out

        for code in codes:
            try:
                if len(codes) == 1 and not isinstance(raw.columns, tuple):
                    df_c = raw
                elif isinstance(raw.columns, tuple) or hasattr(raw.columns, "levels"):
                    df_c = raw[code] if code in raw else None
                else:
                    df_c = raw
                if df_c is None or df_c.empty:
                    continue
                df_c = df_c.dropna(subset=["Open", "Close"])
                rows = []
                for idx, r in df_c.iterrows():
                    ds = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
                    op_v = float(r["Open"])
                    cl_v = float(r["Close"])
                    if op_v > 0 and cl_v > 0:
                        rows.append((ds, op_v, cl_v))
                bar_map = {}
                for i in range(1, len(rows)):
                    ds, op_v, cl_v = rows[i]
                    prev_cl = rows[i - 1][2]
                    bar_map[ds] = (prev_cl, op_v, cl_v)
                if bar_map:
                    out[code] = bar_map
            except Exception:
                continue
    except Exception as exc:
        print(f"[INFO] Actual bar fetch skipped/failed: {exc}")
    return out


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def _analyze_and_propose(weights: dict, ledger: dict) -> tuple[dict, dict, list[str]]:
    """
    予測台帳の誤差を集計し、週次改善提案（重み調整・レポート項目）を算出する。
    """
    today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    cutoff_str = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=14)).strftime("%Y-%m-%d")

    entries = []
    codes = set()
    for code, hist in ledger.items():
        if not isinstance(hist, dict):
            continue
        codes.add(code)
        for dt_k, snap in hist.items():
            if not isinstance(snap, dict) or dt_k >= today_str:
                continue
            p50 = snap.get("p50") or []
            if not p50:
                continue
            pred_open = snap.get("pred_open_px")
            pred_open_gap = snap.get("pred_open_gap_pct")
            pred_close = p50[-1]
            entries.append(
                {
                    "code": code,
                    "date": dt_k,
                    "pred_open": float(pred_open) if pred_open is not None else float(p50[0]),
                    "pred_open_gap": float(pred_open_gap) if pred_open_gap is not None else None,
                    "pred_close": float(pred_close),
                    "in_window": dt_k >= cutoff_str,
                }
            )

    bars_by_code = _fetch_actual_daily_bars(sorted(codes), cutoff_str) if entries else {}

    matched_all = []
    matched_recent = []
    for item in entries:
        bmap = bars_by_code.get(item["code"], {})
        if item["date"] not in bmap:
            continue
        prev_cl, act_open, act_close = bmap[item["date"]]
        act_gap_pct = ((act_open - prev_cl) / max(prev_cl, 1e-4)) * 100.0
        pred_gap_pct = (
            item["pred_open_gap"]
            if item["pred_open_gap"] is not None
            else (((item["pred_open"] - prev_cl) / max(prev_cl, 1e-4)) * 100.0)
        )
        open_err_pct = act_gap_pct - pred_gap_pct

        act_intra_pct = ((act_close - act_open) / max(act_open, 1e-4)) * 100.0
        pred_intra_pct = ((item["pred_close"] - item["pred_open"]) / max(item["pred_open"], 1e-4)) * 100.0
        intra_err_pct = act_intra_pct - pred_intra_pct

        close_err_pct = ((act_close - item["pred_close"]) / max(item["pred_close"], 1e-4)) * 100.0

        rec = {
            **item,
            "open_err_pct": round(open_err_pct, 3),
            "intra_err_pct": round(intra_err_pct, 3),
            "close_err_pct": round(close_err_pct, 3),
        }
        matched_all.append(rec)
        if item["in_window"]:
            matched_recent.append(rec)

    target_recs = matched_recent if matched_recent else matched_all

    def _stats(recs: list[dict]) -> dict:
        if not recs:
            return {
                "count": 0,
                "open_bias": 0.0,
                "open_mae": 0.0,
                "intra_bias": 0.0,
                "intra_mae": 0.0,
                "close_mae": 0.0,
            }
        o_errs = [r["open_err_pct"] for r in recs]
        i_errs = [r["intra_err_pct"] for r in recs]
        c_errs = [r["close_err_pct"] for r in recs]
        return {
            "count": len(recs),
            "open_bias": round(sum(o_errs) / len(o_errs), 3),
            "open_mae": round(sum(abs(x) for x in o_errs) / len(o_errs), 3),
            "intra_bias": round(sum(i_errs) / len(i_errs), 3),
            "intra_mae": round(sum(abs(x) for x in i_errs) / len(i_errs), 3),
            "close_mae": round(sum(abs(x) for x in c_errs) / len(c_errs), 3),
        }

    st_recent = _stats(target_recs)
    st_total = _stats(matched_all)

    next_w = _merge_weights(weights)
    changes_log: list[str] = []

    og = next_w["open_gap"]
    idr = next_w["intraday_drift"]

    # 週次構造改善：寄付き誤差・日中誤差の偏り（平均誤差）が大きい場合のみ穏やかに重みを調整
    if st_recent["count"] >= 2:
        if abs(st_recent["open_bias"]) >= 0.25:
            delta_og = _clamp(st_recent["open_bias"] * 0.02, -0.05, 0.05)
            old_m, old_n = og["macro"], og["news"]
            og["macro"] = round(_clamp(old_m + delta_og * 0.6, 0.15, 1.20), 4)
            og["news"] = round(_clamp(old_n + delta_og * 0.4, 0.20, 1.80), 4)
            changes_log.append(
                f"寄付き誤差バイアス `{st_recent['open_bias']:+.3f}%` に応じ `open_gap.macro` ({old_m:.4f} -> {og['macro']:.4f}), "
                f"`open_gap.news` ({old_n:.4f} -> {og['news']:.4f}) を調整"
            )

        if abs(st_recent["intra_bias"]) >= 0.25:
            delta_idr = _clamp(st_recent["intra_bias"] * 0.02, -0.05, 0.05)
            old_c, old_l = idr["calib"], idr["lab_bias"]
            idr["calib"] = round(_clamp(old_c + delta_idr * 0.5, 0.05, 1.00), 4)
            idr["lab_bias"] = round(_clamp(old_l + delta_idr * 0.5, 0.10, 1.60), 4)
            changes_log.append(
                f"日中誤差バイアス `{st_recent['intra_bias']:+.3f}%` に応じ `intraday_drift.calib` ({old_c:.4f} -> {idr['calib']:.4f}), "
                f"`intraday_drift.lab_bias` ({old_l:.4f} -> {idr['lab_bias']:.4f}) を調整"
            )

    if not changes_log:
        changes_log.append("直近誤差バイアスは許容範囲内のため、現行の進化重みを維持（過学習防止）")

    summary = {
        "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "ledger_tickers": len(codes),
        "ledger_snapshots": len(entries),
        "recent": st_recent,
        "all_time": st_total,
        "top_errors": sorted(target_recs, key=lambda r: abs(r["close_err_pct"]), reverse=True)[:8],
    }
    return summary, next_w, changes_log


def _render_report_markdown(summary: dict, prev_w: dict, next_w: dict, changes_log: list[str]) -> str:
    rec = summary["recent"]
    tot = summary["all_time"]
    lines = [
        "# YAMASHISHI DEEP DIVE 週次予測誤差・重み監査レポート",
        "",
        f"- **生成日時**: {summary['generated_at_utc']}",
        f"- **台帳対象銘柄数**: {summary['ledger_tickers']} 銘柄 / **保存スナップショット数**: {summary['ledger_snapshots']} 件",
        f"- **オンライン学習更新回数**: `{prev_w.get('updates_count', 0)}` 回",
        "",
        "## 1. 誤差サマリー（2分解：寄付き誤差 / 日中誤差）",
        "",
        "| 集計区分 | 照合件数 | 寄付き平均誤差(Bias) | 寄付きMAE | 日中平均誤差(Bias) | 日中MAE | 大引けMAE |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| 直近14日 | {rec['count']} | {rec['open_bias']:+.3f}% | {rec['open_mae']:.3f}% | {rec['intra_bias']:+.3f}% | {rec['intra_mae']:.3f}% | {rec['close_mae']:.3f}% |",
        f"| 全期間 | {tot['count']} | {tot['open_bias']:+.3f}% | {tot['open_mae']:.3f}% | {tot['intra_bias']:+.3f}% | {tot['intra_mae']:.3f}% | {tot['close_mae']:.3f}% |",
        "",
        "## 2. 週次改善アクション",
        "",
    ]
    for c in changes_log:
        lines.append(f"- {c}")

    lines.extend(
        [
            "",
            "## 3. ファクター重み比較（`weights_evolution.json`）",
            "",
            "### 寄付きギャップ重み（`open_gap`）",
            "",
            "| ファクター | 変更前 | 提案後 |",
            "| --- | ---: | ---: |",
        ]
    )
    for k in DEFAULT_WEIGHTS["open_gap"]:
        b_val = float(prev_w.get("open_gap", {}).get(k, DEFAULT_WEIGHTS["open_gap"][k]))
        a_val = float(next_w.get("open_gap", {}).get(k, DEFAULT_WEIGHTS["open_gap"][k]))
        lines.append(f"| `{k}` | {b_val:.4f} | {a_val:.4f} |")

    lines.extend(
        [
            "",
            "### 日中ドリフト重み（`intraday_drift`）",
            "",
            "| ファクター | 変更前 | 提案後 |",
            "| --- | ---: | ---: |",
        ]
    )
    for k in DEFAULT_WEIGHTS["intraday_drift"]:
        b_val = float(prev_w.get("intraday_drift", {}).get(k, DEFAULT_WEIGHTS["intraday_drift"][k]))
        a_val = float(next_w.get("intraday_drift", {}).get(k, DEFAULT_WEIGHTS["intraday_drift"][k]))
        fmt = ".5f" if k == "news" else ".4f"
        lines.append(f"| `{k}` | {format(b_val, fmt)} | {format(a_val, fmt)} |")

    top_errs = summary.get("top_errors") or []
    if top_errs:
        lines.extend(
            [
                "",
                "## 4. 乖離が大きかった直近セッション（Top 8）",
                "",
                "| 日付 | 銘柄 | 寄付き誤差 | 日中誤差 | 大引け誤差 |",
                "| --- | --- | ---: | ---: | ---: |",
            ]
        )
        for row in top_errs:
            lines.append(
                f"| {row['date']} | `{row['code']}` | {row['open_err_pct']:+.2f}% | {row['intra_err_pct']:+.2f}% | {row['close_err_pct']:+.2f}% |"
            )

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    prev_w = _load_weights()
    ledger = _load_ledger()

    summary, next_w, changes_log = _analyze_and_propose(prev_w, ledger)
    report_md = _render_report_markdown(summary, prev_w, next_w, changes_log)

    date_tag = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    dated_report_path = REPORTS_DIR / f"weekly_audit_{date_tag}.md"
    dated_report_path.write_text(report_md, encoding="utf-8")
    LATEST_REPORT_PATH.write_text(report_md, encoding="utf-8")

    next_w["last_updated"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    WEIGHTS_PATH.write_text(json.dumps(next_w, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _sb_upsert(WEIGHTS_KV_KEY, next_w)

    print(f"[OK] Report written to {dated_report_path} and {LATEST_REPORT_PATH}")
    print(f"[OK] Updated {WEIGHTS_PATH}")


if __name__ == "__main__":
    main()
