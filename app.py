import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import unicodedata

st.set_page_config(page_title="翌朝株価 クオンツ＆AI解析", page_icon="📈", layout="centered")

st.markdown("""
<style>
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
.prob-badge { font-size: 22px; font-weight: bold; color: #dc2626; }
.rank-badge {
    display: inline-block; background: #f59e0b; color: #ffffff;
    padding: 3px 9px; border-radius: 20px; font-size: 12px;
    font-weight: bold; margin-right: 4px; margin-bottom: 6px;
}
.score-badge {
    display: inline-block; background: #1e293b; color: #f8fafc;
    padding: 3px 10px; border-radius: 20px; font-size: 12px;
    font-weight: bold; margin-bottom: 6px;
}
</style>
""", unsafe_allow_html=True)

st.title("📱 翌朝株価 クオンツ＆AI解析 Pro")
st.caption("リアルタイム期待値順に選抜・解析")

# 銘柄プール
STOCK_POOL = {
    "半導体": [
        {"code": "8035.T", "name": "東京エレクトロン", "theme": "前工程装置の国内筆頭"},
        {"code": "6857.T", "name": "アドバンテスト", "theme": "AI半導体向けテスタ"},
        {"code": "6920.T", "name": "レーザーテック", "theme": "EUVマスク検査"},
        {"code": "NVDA", "name": "エヌビディア", "theme": "生成AI向けGPUの覇者"},
        {"code": "AMD", "name": "AMD", "theme": "AIアクセラレータCPU"}
    ],
    "テンバガー小型株": [
        {"code": "5595.T", "name": "QPS研究所", "theme": "小型SAR衛星時価総額急拡大"},
        {"code": "186A.T", "name": "アストロスケール", "theme": "宇宙ゴミ除去ニッチトップ"},
        {"code": "9348.T", "name": "ispace", "theme": "民間月面輸送ベンチャー"},
        {"code": "5243.T", "name": "ノート", "theme": "クリエイターエコノミー"},
        {"code": "PLTR", "name": "パランティア", "theme": "AIプラットフォーム急成長"},
        {"code": "IONQ", "name": "アイオンQ", "theme": "商用量子コンピューター開発"}
    ]
}

KNOWN_STOCKS = {}
for g, items in STOCK_POOL.items():
    for item in items:
        KNOWN_STOCKS[item["code"]] = {"name": item["name"], "theme": item["theme"], "genre": g}

def normalize_ticker(raw):
    s = unicodedata.normalize('NFKC', raw).strip().upper()
    if not s: return ""
    if "." in s or s.startswith("^") or "=" in s: return s
    if len(s) == 4 and any(ch.isdigit() for ch in s): return f"{s}.T"
    return s

@st.cache_data(ttl=1800)
def fetch_and_analyze(code, name=None, theme=None, genre="個別検索"):
    try:
        ticker = yf.Ticker(code)
        df = ticker.history(period="6mo")
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

        ai_score = int(min(max(round(prob * 0.8), 20), 95))
        close_val = float(latest['Close'])
        est_open_val = close_val * (1.0 + (avg_gap / 100.0))
        is_jp = ".T" in code
        
        def fmt_p(v):
            return f"{v:,.0f}円" if is_jp else f"${v:,.2f}"

        return {
            "code": code.replace(".T", ""), "name": name, "genre": genre,
            "price": fmt_p(close_val), "est_open": fmt_p(est_open_val),
            "diff": round(float(latest['Day_Return']), 2),
            "prob": prob, "count": f"{wins}/{total}回", "gap": avg_gap,
            "ai_score": ai_score, "theme": theme
        }
    except Exception:
        return None

# 入力フォーム
custom_input = st.text_input("🔍 銘柄コード診断（例: 7203, 5595, NVDA）")
if custom_input:
    norm = normalize_ticker(custom_input)
    if norm:
        with st.spinner("解析中..."):
            res = fetch_and_analyze(norm)
        if res:
            st.success(f"{res['name']} ({res['code']}) - 翌朝上昇確率: {res['prob']}% (AIスコア: {res['ai_score']})")
        else:
            st.error("データが見つかりませんでした。")

# タブ表示
tabs = st.tabs(list(STOCK_POOL.keys()))
for tab, genre in zip(tabs, STOCK_POOL.keys()):
    with tab:
        for s in STOCK_POOL[genre]:
            res = fetch_and_analyze(s["code"], s["name"], s["theme"], genre)
            if res:
                st.markdown(f"""
                <div class="stock-card">
                    <span class="score-badge">AIスコア: {res['ai_score']}</span>
                    <span style="font-size:16px; font-weight:bold;">{res['name']} ({res['code']})</span><br>
                    終値: <b>{res['price']}</b> ({res['diff']:+.2f}%) | 翌朝上昇確率: <span class="prob-badge">{res['prob']}%</span><br>
                    <small>テーマ: {res['theme']}</small>
                </div>
                """, unsafe_allow_html=True)
