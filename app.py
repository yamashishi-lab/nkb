import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import unicodedata

# スマホ画面向けにページ設定
st.set_page_config(page_title="翌朝株価 クオンツ＆AI解析 (弱肉強食ダイナミック版)", page_icon="📈", layout="centered")

# スマホで見やすいカスタムCSS
st.markdown("""
<style>
.market-banner {
    background: linear-gradient(135deg, #0f172a, #1e293b);
    color: #f8fafc;
    border-radius: 12px;
    padding: 12px 10px;
    margin-bottom: 16px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.18);
    box-sizing: border-box;
    width: 100%;
}
.market-title {
    font-size: 11px;
    font-weight: bold;
    color: #94a3b8;
    margin-bottom: 8px;
    text-align: center;
}
.market-grid {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 6px;
    width: 100%;
    box-sizing: border-box;
}
.market-item {
    background: rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 7px 4px;
    text-align: center;
    box-sizing: border-box;
    border: 1px solid rgba(255, 255, 255, 0.07);
}
.span-2 { grid-column: span 2; }
.span-3 { grid-column: span 3; }
@media (max-width: 340px) {
    .span-2, .span-3 { grid-column: span 6; }
}
.stock-card {
    background-color: #ffffff;
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 14px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    border-left: 6px solid #dc2626;
}
.rank-card {
    background-color: #ffffff;
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 14px;
    box-shadow: 0 4px 12px rgba(220, 38, 38, 0.12);
    border-left: 6px solid #e11d48;
}
.search-result-card {
    background-color: #fffbeb;
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 18px;
    box-shadow: 0 4px 12px rgba(217, 119, 6, 0.15);
    border-left: 6px solid #d97706;
}
.prob-badge { font-size: 22px; font-weight: bold; color: #dc2626; }
.rank-badge {
    display: inline-block; background: linear-gradient(135deg, #f59e0b, #d97706);
    color: #ffffff; padding: 3px 9px; border-radius: 20px; font-size: 12px;
    font-weight: bold; margin-right: 4px; margin-bottom: 6px;
}
.score-badge {
    display: inline-block; background: linear-gradient(135deg, #1e293b, #334155);
    color: #f8fafc; padding: 3px 10px; border-radius: 20px; font-size: 12px;
    font-weight: bold; margin-bottom: 6px;
}
.macro-badge {
    display: inline-block; background: #eff6ff; color: #1d4ed8;
    border: 1px solid #bfdbfe; padding: 2px 8px; border-radius: 20px;
    font-size: 11px; font-weight: bold; margin-left: 4px;
}
.edge-badge {
    display: inline-block; background: #f0fdf4; color: #15803d;
    border: 1px solid #bbf7d0; padding: 2px 8px; border-radius: 20px;
    font-size: 11px; font-weight: bold; margin-left: 4px;
}
.genre-badge {
    display: inline-block; background: #f3e8ff; color: #6b21a8;
    border: 1px solid #e9d5ff; padding: 2px 8px; border-radius: 6px;
    font-size: 10px; font-weight: bold; margin-left: 6px; vertical-align: middle;
}
.signal-tag {
    display: inline-block; background: #fef2f2; color: #991b1b;
    border: 1px solid #fecaca; padding: 4px 8px; border-radius: 6px;
    font-size: 12px; font-weight: bold; margin-top: 8px;
}
.metrics-row {
    display: flex; flex-wrap: wrap; gap: 6px 10px; margin-top: 8px;
    font-size: 11px; color: #475569; background: #f8fafc; padding: 8px 10px;
    border-radius: 6px; border: 1px solid #e2e8f0;
}
.trade-plan-box {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px;
    margin-top: 8px; background: #f8fafc; padding: 8px 6px; border-radius: 8px;
    border: 1px dashed #cbd5e1; text-align: center;
}
.trade-plan-item { min-width: 0; }
.factor-box {
    background: #f1f5f9; border-radius: 8px; padding: 10px 12px;
    margin-top: 10px; font-size: 12px; color: #1e293b; line-height: 1.5;
}
.factor-title { font-weight: bold; color: #0f172a; margin-bottom: 4px; font-size: 12px; }
</style>
""", unsafe_allow_html=True)

st.title("📱 翌朝株価 クオンツ＆AI解析 Pro")
st.caption("弱肉強食ダイナミック選抜（高速軽量版） × 世界情勢マクロ連動")

# --- 各ジャンルの厳選候補プール（フリーズ対策として主要銘柄に厳選） ---
STOCK_POOL = {
    "半導体": [
        {"code": "8035.T", "name": "東京エレクトロン", "theme": "前工程装置の国内筆頭。海外勢の指数買いが入りやすい"},
        {"code": "6857.T", "name": "アドバンテスト", "theme": "AI半導体向けテスタで高シェア。米SOX指数と連動性大"},
        {"code": "6920.T", "name": "レーザーテック", "theme": "EUVマスク欠陥検査装置。ボラティリティが高く短期資金が集中"},
        {"code": "6146.T", "name": "ディスコ", "theme": "HBM向け切断・研削装置で高収益"},
        {"code": "6723.T", "name": "ルネサス", "theme": "車載・産業・データセンター向けパワー半導体を展開"},
        {"code": "NVDA", "name": "エヌビディア (米国)", "theme": "生成AI向けGPUの圧倒的覇者。世界の半導体・AI相場の羅針盤"},
        {"code": "AMD", "name": "AMD (米国)", "theme": "AIアクセラレータおよびCPUでエヌビディアを追撃"},
        {"code": "TSM", "name": "台湾セミコンダクター (米国)", "theme": "世界最大の半導体ファウンドリ。受託製造の最高峰"}
    ],
    "AI": [
        {"code": "9984.T", "name": "ソフトバンクG", "theme": "傘下ArmやAI投資群の評価益期待。先物主導で寄り付きが動きやすい"},
        {"code": "3778.T", "name": "さくらネット", "theme": "政府クラウド・生成AI向けGPUクラウドの国策銘柄"},
        {"code": "4180.T", "name": "Appier", "theme": "AIマーケティングSaaS。グロース市場の資金流入先"},
        {"code": "MSFT", "name": "マイクロソフト (米国)", "theme": "OpenAI最大株主。クラウド(Azure)とCopilotの収益化"},
        {"code": "PLTR", "name": "パランティア (米国)", "theme": "政府・防衛・企業向けAIプラットフォームの大本命"}
    ],
    "宇宙": [
        {"code": "5595.T", "name": "QPS研究所", "theme": "小型SAR衛星コンステレーション。防衛・安全保障テーマ"},
        {"code": "9348.T", "name": "ispace", "theme": "月面開発・輸送プログラム。イベントドリブンで出来高が急増しやすい"},
        {"code": "186A.T", "name": "アストロスケール", "theme": "スペースデブリ（宇宙ごみ）除去の世界的リーダー"},
        {"code": "7011.T", "name": "三菱重工業", "theme": "H3ロケット打ち上げ及び防衛予算拡大の国策中核銘柄"}
    ],
    "テンバガー小型株": [
        {"code": "5595.T", "name": "QPS研究所", "theme": "小型SAR衛星コンステレーションによる時価総額急拡大の急先鋒"},
        {"code": "186A.T", "name": "アストロスケール", "theme": "宇宙ゴミ除去という唯一無二のニッチトップによる中長期成長"},
        {"code": "9348.T", "name": "ispace", "theme": "民間で月面輸送を手掛ける宇宙ベンチャー。テーマ性抜群"},
        {"code": "5243.T", "name": "ノート", "theme": "クリエイターエコノミーを牽引するメディアプラットフォーム"},
        {"code": "5032.T", "name": "ANYCOLOR", "theme": "VTuber市場のグローバル展開と高収益体質"},
        {"code": "4180.T", "name": "Appier", "theme": "AIを駆使したマーケティングSaaSで海外売上比率が急増"},
        {"code": "3778.T", "name": "さくらインターネット", "theme": "生成AI向けGPUクラウド本格稼働による業績変革期"},
        {"code": "ACHR", "name": "アーチャー・アビエーション (米国)", "theme": "空飛ぶクルマ（eVTOL）実用化の筆頭候補"},
        {"code": "IONQ", "name": "アイオンQ (米国)", "theme": "商用量子コンピューター開発の最先端小型テクノロジー"}
    ]
}

KNOWN_STOCKS = {}
for g, items in STOCK_POOL.items():
    for item in items:
        KNOWN_STOCKS[item["code"]] = {"name": item["name"], "theme": item["theme"], "genre": g}

def normalize_ticker(raw_input):
    s = unicodedata.normalize('NFKC', raw_input).strip().upper()
    if not s: return ""
    if "." in s or s.startswith("^") or "=" in s: return s
    if len(s) == 4 and any(ch.isdigit() for ch in s): return f"{s}.T"
    return s

@st.cache_data(ttl=900)
def fetch_macro_market():
    macro_tickers = {
        "sp500":  {"codes": ["^GSPC"], "label": "🇺🇸 米S&P500"},
        "sox":    {"codes": ["^SOX"], "label": "💽 米SOX半導体"},
        "usdjpy": {"codes": ["JPY=X"], "label": "💴 ドル円為替"},
        "nk_fut": {"codes": ["NIY=F", "^N225"], "label": "🇯🇵 CME日経先物"},
        "vix":    {"codes": ["^VIX"], "label": "⚡ VIX恐怖指数"}
    }
    macro_data = {}
    for key, info in macro_tickers.items():
        fetched = False
        for c in info["codes"]:
            try:
                df_m = yf.Ticker(c).history(period="5d")
                if df_m is not None and not df_m.empty:
                    df_m = df_m.dropna(subset=['Close'])
                    if len(df_m) >= 2:
                        latest_c = float(df_m['Close'].iloc[-1])
                        prev_c = float(df_m['Close'].iloc[-2])
                        if not np.isnan(latest_c) and not np.isnan(prev_c) and prev_c != 0:
                            diff_pct = round((latest_c - prev_c) / prev_c * 100, 2)
                            lbl = info["label"]
                            if key == "nk_fut" and c == "^N225": lbl = "🇯🇵 日経平均(現物)"
                            macro_data[key] = {"price": latest_c, "diff": diff_pct, "label": lbl}
                            fetched = True
                            break
            except Exception:
                continue
        if not fetched:
            macro_data[key] = {"price": 0.0, "diff": 0.0, "label": info["label"]}
    return macro_data

@st.cache_data(ttl=1800)
def fetch_and_analyze(code, name=None, theme=None, genre="個別検索", macro=None):
    try:
        ticker_obj = yf.Ticker(code)
        df = ticker_obj.history(period="6mo") # 期間を6ヶ月に短縮して高速化
        if df is None or df.empty or len(df) < 30: return None

        df = df.dropna(subset=['Close', 'Open', 'High', 'Low', 'Volume'])
        if len(df) < 30: return None

        if code in KNOWN_STOCKS:
            name = name or KNOWN_STOCKS[code]["name"]
            theme = theme or KNOWN_STOCKS[code]["theme"]
            genre = KNOWN_STOCKS[code]["genre"]
        else:
            name = name or code.replace(".T", "")
            theme = theme or "カスタム指定銘柄"

        df['Prev_Close'] = df['Close'].shift(1)
        df['Day_Return'] = (df['Close'] - df['Prev_Close']) / df['Prev_Close'] * 100
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['Vol_MA20'] = df['Volume'].rolling(20).mean().replace(0, np.nan)
        df['Vol_Ratio'] = (df['Volume'] / df['Vol_MA20']).fillna(1.0)

        delta = df['Close'].diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss.replace(0, np.nan)
        df['RSI'] = (100 - (100 / (1 + rs))).fillna(50.0)

        df['BB_Std'] = df['Close'].rolling(20).std().replace(0, np.nan)
        df['BB_Sigma'] = ((df['Close'] - df['MA20']) / df['BB_Std']).fillna(0.0)

        ema12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = ema12 - ema26
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
        df['MACD_Hist_Diff'] = df['MACD_Hist'].diff()

        tr1 = df['High'] - df['Low']
        tr2 = (df['High'] - df['Prev_Close']).abs()
        tr3 = (df['Low'] - df['Prev_Close']).abs()
        df['TR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['ATR'] = df['TR'].rolling(14).mean().fillna(df['Close'] * 0.02)
        df['ATR_Pct'] = (df['ATR'] / df['Close'] * 100).fillna(2.0)

        high_low = (df['High'] - df['Low']).replace(0, np.nan)
        df['Close_Pos'] = ((df['Close'] - df['Low']) / high_low).fillna(0.5)
        body_bottom = df[['Open', 'Close']].min(axis=1)
        df['Lower_Shadow'] = ((body_bottom - df['Low']) / high_low).fillna(0.0)

        df['Next_Open'] = df['Open'].shift(-1)
        df['Gap_Pct'] = (df['Next_Open'] - df['Close']) / df['Close'] * 100
        df['Morning_Up'] = df['Next_Open'] > df['Close']

        latest = df.iloc[-1]
        history = df.iloc[:-1].dropna(subset=['Next_Open'])
        if len(history) == 0: return None

        total = len(history)
        wins = int(history['Morning_Up'].sum())
        prob = round((wins / total) * 100, 1) if total > 0 else 50.0
        avg_gap = round(float(history['Gap_Pct'].mean()), 2) if total > 0 else 0.0

        win_gaps = history[history['Morning_Up']]['Gap_Pct']
        loss_gaps = history[~history['Morning_Up']]['Gap_Pct']
        avg_win = float(win_gaps.mean()) if len(win_gaps) > 0 else 0.5
        avg_loss = abs(float(loss_gaps.mean())) if len(loss_gaps) > 0 else 0.5
        payoff_ratio = round(avg_win / max(avg_loss, 0.1), 2)
        expected_edge = round((prob / 100 * avg_win) - ((100 - prob) / 100 * avg_loss), 2)

        macro_score = 0
        if macro:
            sox_diff = macro["sox"]["diff"]
            nk_diff = macro["nk_fut"]["diff"]
            if sox_diff >= 1.0: macro_score += 3
            elif sox_diff <= -1.5: macro_score -= 3
            if ".T" in code:
                if nk_diff >= 0.6: macro_score += 2
                elif nk_diff <= -0.6: macro_score -= 2

        signal = "🔥 モメンタム継続・順張り" if latest['Close'] > latest['MA5'] else "⚡ 押し目反発狙い"
        ai_score = int(min(max(round(prob * 0.7 + (expected_edge * 10) + macro_score), 15), 99))

        close_val = float(latest['Close'])
        atr_val = float(latest['ATR'])
        est_open_val = close_val * (1.0 + (avg_gap / 100.0))
        tp_val = max(est_open_val, close_val) + (atr_val * 0.8)
        sl_val = min(est_open_val, close_val) - (atr_val * 0.5)

        is_jp = ".T" in code
        def fmt_p(v): return f"{v:,.0f}円" if is_jp else f"${v:,.2f}"

        return {
            "code": code.replace(".T", ""), "name": name, "genre": genre,
            "price": fmt_p(close_val), "est_open": fmt_p(est_open_val),
            "tp_price": fmt_p(tp_val), "tp_pct": round((tp_val - close_val) / close_val * 100, 1),
            "sl_price": fmt_p(sl_val), "sl_pct": round((sl_val - close_val) / close_val * 100, 1),
            "diff": round(float(latest['Day_Return']), 2), "signal": signal,
            "prob": prob, "count": f"{wins}/{total}回", "gap": avg_gap,
            "rsi": round(float(latest['RSI']), 1), "vol_ratio": round(float(latest['Vol_Ratio']), 2),
            "bb_sigma": round(float(latest['BB_Sigma']), 2), "macd_state": "強気↑" if latest['MACD_Hist'] > 0 else "調整↓",
            "atr_pct": round(float(latest['ATR_Pct']), 1), "payoff": payoff_ratio,
            "edge": expected_edge, "ai_score": ai_score, "macro_score": macro_score,
            "theme": theme, "reasons": f"過去同条件での勝率は {prob}% です。"
        }
    except Exception:
        return None

def render_stock_card(r, is_custom=False, rank=None):
    diff_color = "#dc2626" if r["diff"] > 0 else "#2563eb"
    card_class = "search-result-card" if is_custom else ("rank-card" if rank else "stock-card")
    rank_html = f'<span class="rank-badge">第{rank}位</span>' if rank else ""
    genre_html = f'<span class="genre-badge">{r["genre"]}</span>' if rank else ""

    html_card = (
        f'<div class="{card_class}">'
        f'<div>{rank_html}<span class="score-badge">🤖 AIスコア: {r["ai_score"]} / 100</span></div>'
        f'<div style="display:flex; justify-content:space-between; align-items:center; margin-top:4px;">'
        f'<div><span style="font-size:16px; font-weight:bold; color:#1e293b;">{r["name"]}</span> '
        f'<span style="font-size:12px; color:#64748b;">({r["code"]})</span>{genre_html}<br>'
        f'<span style="font-size:14px; color:#334155;">終値: <b>{r["price"]}</b> '
        f'(<span style="color:{diff_color}; font-weight:bold;">{r["diff"]:+.2f}%</span>)</span></div>'
        f'<div style="text-align:right;"><span style="font-size:11px; color:#64748b;">上昇確率</span><br>'
        f'<span class="prob-badge">{r["prob"]}%</span></div></div>'
        f'<div class="signal-tag">{r["signal"]}</div>'
        f'<div class="metrics-row">'
        f'<span>📊 <b>RSI:</b> {r["rsi']}</span><span>📈 <b>MACD:</b> {r["macd_state"]}</span>'
        f'<span>🔊 <b>出来高:</b> {r["vol_ratio"]}倍</span><span>📏 <b>BB:</b> {r["bb_sigma"]}σ</span>'
        f'</div>'
        f'<div class="trade-plan-box">'
        f'<div class="trade-plan-item"><div style="font-size:10px; color:#64748b;">🌅 寄付目安</div><div style="font-size:12px; font-weight:bold;">{r["est_open"]}</div></div>'
        f'<div class="trade-plan-item" style="border-left:1px solid #e2e8f0; border-right:1px solid #e2e8f0;"><div style="font-size:10px; color:#15803d; font-weight:bold;">🎯 利確</div><div style="font-size:12px; font-weight:bold; color:#15803d;">{r["tp_price"]}</div></div>'
        f'<div class="trade-plan-item"><div style="font-size:10px; color:#b91c1c; font-weight:bold;">🛡️ 損切</div><div style="font-size:12px; font-weight:bold; color:#b91c1c;">{r["sl_price"]}</div></div>'
        f'</div>'
        f'<div class="factor-box"><div class="factor-title">💡 テーマ & 解析</div>'
        f'<div><b>【テーマ】</b> {r["theme"]}</div></div></div>'
    )
    st.markdown(html_card, unsafe_allow_html=True)

if st.button("🔄 最新データに更新"):
    st.cache_data.clear()

macro_info = fetch_macro_market()

def fmt_macro(item, span="span-2"):
    d = item["diff"]
    col = "#4ade80" if d > 0 else ("#f87171" if d < 0 else "#cbd5e1")
    val = f"{item['price']:,.2f}" if item['price'] < 100 else f"{item['price']:,.0f}"
    return f'<div class="market-item {span}"><div style="font-size:10px; color:#cbd5e1;">{item["label"]}</div><div style="font-size:13px; font-weight:bold; color:#f8fafc;">{val}</div><div style="font-size:11px; font-weight:bold; color:{col};">{d:+.2f}%</div></div>'

st.markdown(f"""
<div class="market-banner">
<div class="market-title">🌐 市場環境フィルター</div>
<div class="market-grid">
{fmt_macro(macro_info.get("sp500", {"price":0,"diff":0,"label":"S&P500"}), "span-2")}
{fmt_macro(macro_info.get("sox", {"price":0,"diff":0,"label":"SOX"}), "span-2")}
{fmt_macro(macro_info.get("usdjpy", {"price":0,"diff":0,"label":"ドル円"}), "span-2")}
{fmt_macro(macro_info.get("nk_fut", {"price":0,"diff":0,"label":"日経先物"}), "span-3")}
{fmt_macro(macro_info.get("vix", {"price":0,"diff":0,"label":"VIX"}), "span-3")}
</div></div>
""", unsafe_allow_html=True)

c1, c2 = st.columns([3, 1])
with c1: custom_input = st.text_input("🔍 銘柄コード診断", placeholder="例: 7203, NVDA")
with c2: 
    st.write("")
    search_clicked = st.button("診断する", use_container_width=True)

if custom_input or search_clicked:
    norm = normalize_ticker(custom_input)
    if norm:
        with st.spinner(f"「{norm}」解析中..."):
            res = fetch_and_analyze(norm, macro=macro_info)
        if res: render_stock_card(res, is_custom=True)
        else: st.error("データが見つかりませんでした。")

genre_results = {g: [] for g in STOCK_POOL.keys()}
all_results = []

with st.spinner("全候補を高速スキャン中..."):
    for g, stocks in STOCK_POOL.items():
        for s in stocks:
            res = fetch_and_analyze(s["code"], s["name"], s["theme"], g, macro_info)
            if res:
                genre_results[g].append(res)
                all_results.append(res)

tabs = st.tabs(["🏆 総合TOP5"] + list(STOCK_POOL.keys()))

with tabs[0]:
    if all_results:
        for idx, r in enumerate(sorted(all_results, key=lambda x: (x["ai_score"], x["edge"]), reverse=True)[:5], 1):
            render_stock_card(r, rank=idx)

for tab, genre in zip(tabs[1:], STOCK_POOL.keys()):
    with tab:
        results = sorted(genre_results.get(genre, []), key=lambda x: (x["ai_score"], x["edge"]), reverse=True)[:20]
        for idx, r in enumerate(results, 1):
            render_stock_card(r, rank=idx)
