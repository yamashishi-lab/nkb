import os
import sys
import time
import argparse
import importlib
import traceback

# =========================================================================
# 設定：DEEP DIVE 本体のモジュール名（例: deep_dive.py なら "deep_dive"）
# =========================================================================
DEEP_DIVE_MODULE = os.environ.get("DD_MODULE_NAME", "deep_dive")

DEFAULT_JP_WATCHLIST = [
    "6920.T", "8035.T", "6857.T", "9984.T", "7011.T",
    "7203.T", "8306.T", "6501.T",
]
DEFAULT_US_WATCHLIST = [
    "NVDA", "TSLA", "AAPL", "MSFT", "AMD",
    "PLTR", "SMR", "META",
]


def _parse_watchlist(env_key: str, default_list: list) -> list:
    raw = os.environ.get(env_key, "").strip()
    if not raw:
        return default_list
    return [x.strip().upper() for x in raw.split(",") if x.strip()]


def _normalize_code(code: str, is_jp: bool) -> str:
    c = code.strip().upper()
    if is_jp and not c.endswith(".T") and len(c) == 4:
        return f"{c}.T"
    return c


def run_auto_lock(market: str, force_window: bool = False) -> int:
    sb_url = os.environ.get("SUPABASE_URL", "").strip()
    sb_key = os.environ.get("SUPABASE_KEY", "").strip()
    if not sb_url or not sb_key:
        print("❌ ERROR: SUPABASE_URL / SUPABASE_KEY が環境変数に設定されていません。")
        return 1

    try:
        dd = importlib.import_module(DEEP_DIVE_MODULE)
    except Exception as e:
        print(f"❌ ERROR: 本体モジュール '{DEEP_DIVE_MODULE}.py' の読み込みに失敗: {e}")
        return 1

    # 手動テスト等で寄り前2時間枠外から強制ロックしたい場合のみオーバーライド
    if force_window:
        print("⚠️ --force 指定: 寄り前2時間ウィンドウ制限を一時解除します。")
        dd._is_valid_premarket_lock_window = lambda is_jp, target_date_str: True

    is_jp = (market.upper() == "JP")
    raw_list = _parse_watchlist(
        "WATCHLIST_JP" if is_jp else "WATCHLIST_US",
        DEFAULT_JP_WATCHLIST if is_jp else DEFAULT_US_WATCHLIST,
    )
    tickers = [_normalize_code(c, is_jp) for c in raw_list]

    target_date = dd._get_target_session_date(is_jp)
    in_window = dd._is_valid_premarket_lock_window(is_jp, target_date)
    m_now = dd._get_market_now(is_jp).strftime("%Y-%m-%d %H:%M:%S")

    print("=" * 60)
    print(f"🚀 YAMASHISHI AUTO LOCK CRON | Market={market.upper()} | Now={m_now}")
    print(f"📅 Target Session={target_date} | Premarket Window={in_window} | Count={len(tickers)}")
    print("=" * 60)

    if not in_window:
        print("ℹ️ 現在は寄り前2時間ロック枠外のため、朝ロック保存はスキップされます（SGD未学習分のみチェック）。")

    # 共通データ（マクロ・ベンチマーク5分足・LAB共有データ）を1回だけ取得
    macro_data = dd._load_macro_data()
    df_bench_5m = dd._load_benchmark_5m(is_jp)
    shared_db = dd._dd_db_get("shared_ticker_intel", {})
    if not isinstance(shared_db, dict):
        shared_db = {}

    ok_cnt, skip_cnt, err_cnt = 0, 0, 0

    for idx, fc in enumerate(tickers, 1):
        try:
            print(f"[{idx}/{len(tickers)}] {fc} 解析開始...")
            data = dd._load_stock_core(fc)
            df_1d, df_5m, info = data["df_1d"], data["df_5m"], data["info"]
            if df_1d is None or df_1d.empty:
                print(f"  ⚠️ {fc}: 日足データ取得不可のためスキップ")
                skip_cnt += 1
                continue

            corp_name = info.get("longName") or info.get("shortName") or fc
            short_code = fc.replace(".T", "")
            market_today_str = dd._get_market_now(is_jp).strftime("%Y-%m-%d")
            last_1d_str = (
                df_1d.index[-1].strftime("%Y-%m-%d")
                if hasattr(df_1d.index[-1], "strftime")
                else str(df_1d.index[-1])[:10]
            )
            curr_px = float(df_1d["Close"].iloc[-1])
            prev_px = float(df_1d["Close"].iloc[-2]) if (last_1d_str == market_today_str and len(df_1d) >= 2) else curr_px

            mkt_regime = dd._detect_market_regime(df_1d)
            macro_sens = dd._compute_macro_sens(df_1d["Close"], macro_data)
            dow_stats, next_wd = dd._compute_dow_edge(df_1d, is_jp)
            news_res = dd._fetch_global_intel(corp_name, short_code)
            _, whale_news = dd._fetch_gov_and_whales(corp_name, short_code, is_jp)
            whale_anom = dd._detect_whale_anomaly(data["insider_tx"], whale_news, market_today_str)
            vp = dd._compute_vp(df_1d, curr_px, is_jp)

            # Supabase上のLAB解析データがあれば連携
            entry = shared_db.get(fc) if isinstance(shared_db.get(fc), dict) else {}
            active_lab = entry.get("lab_full") if isinstance(entry.get("lab_full"), dict) else None

            traj = dd._build_dual_5m_trajectory(
                fc, curr_px, prev_px, df_1d, df_5m,
                macro_sens, macro_data, news_res, whale_anom,
                dow_stats[next_wd]["avg"], vp, is_jp,
                mkt_regime=mkt_regime, active_lab=active_lab, df_bench_5m=df_bench_5m,
            )

            we = traj["weights_evolution"]
            sgd_tag = "SGD更新あり" if we.get("weights_updated") else "SGD変化なし"
            lock_tag = "朝ロック保存済" if (not traj["has_actual"] and in_window) else ("場中/済" if traj["has_actual"] else "枠外")
            print(
                f"  ✅ {fc} | {lock_tag} | {sgd_tag} (累計{we['updates_count']}回) | "
                f"Gap {traj['est_open_gap_pct']:+.2f}% → 引け {traj['est_close_chg']:+.2f}%"
            )
            ok_cnt += 1
            time.sleep(1.2)  # Yahoo Finance / RSS レート制限対策
        except Exception as e:
            print(f"  ❌ {fc} エラー: {e}")
            traceback.print_exc()
            err_cnt += 1

    print("=" * 60)
    print(f"🏁 完了: 成功={ok_cnt} / スキップ={skip_cnt} / エラー={err_cnt}")
    print("=" * 60)
    return 0 if err_cnt == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YAMASHISHI DEEP DIVE 毎朝自動ロック＆SGD学習Cron")
    parser.add_argument("--market", choices=["JP", "US"], required=True, help="対象市場 (JP / US)")
    parser.add_argument("--force", action="store_true", help="寄り前2時間枠外でも強制ロック保存（テスト用）")
    args = parser.parse_args()
    sys.exit(run_auto_lock(args.market, force_window=args.force))
