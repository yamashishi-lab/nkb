import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# スマホ画面向けにページ設定
st.set_page_config(page_title="翌朝株価 統計ナビ", page_icon="📈", layout="centered")

# スマホで見やすいカスタムCSS
st.markdown("""
<style>
.stock-card {
    background-color: #ffffff;
    border-radius: 12px;
    padding: 14px;
    margin-bottom: 12px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    border-left: 6px solid #bf0000;
}
.prob-badge {
    font-size: 22px;
    font-weight: bold;
    color: #dc2626;
}
.signal-tag {
    display: inline-block;
    background: #f1f5f9;
    color: #334155;
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 12px;
    margin-top: 4px;
}
.rakuten-btn {
    display: block;
    text-align: center;
    background: #bf0000;
    color: white !important;
    text-decoration: none;
    padding: 8px;
    border-radius: 8px;
    font-weight: bold;
    margin-top: 10px;
    font-size: 13px;
}
</style>
""", unsafe_allow_html=True)

st.title("📱 翌朝株価の上昇統計ナビ")
st.caption("過去1年の日足データから、直近と同じシグナルが出た翌朝（始値）の上昇確率を算出")

STOCK_LIST = {
    "半導体": [
        {"code": "8035.T", "name": "東京エレクトロン"},
        {"code": "6857.T", "name": "アドバンテスト"},
        {"code": "6920.T", "name": "レーザーテック"},
        {"code": "6146.T", "name": "ディスコ"},
        {"code": "6723.T", "name": "ルネサス"},
    ],
    "AI": [
        {"code": "9984.T", "name": "ソフトバンクG"},
        {"code": "3778.T", "name": "さくらネット"},
        {"code": "3993.T", "name": "PKSHA"},
        {"code": "4180.T", "name": "Appier"},
        {"code": "4307.T", "name": "野村総合研究所"},
    ],
    "宇宙": [
        {"code": "5595.T", "name": "QPS研究所"},
        {"code": "9348.T", "name": "ispace"},
        {"code": "186A.T", "name": "アストロスケール"},
        {"code": "9412.T", "name": "スカパーJSAT"},
        {"code": "7011.T", "name": "三菱重工業"},
    ],
    "エネルギー": [
        {"code": "1605.T", "name": "INPEX"},
        {"code": "9501.T", "name": "東京電力HD"},
        {"code": "9503.T", "name": "関西電力"},
        {"code": "5020.T", "name": "ENEOS HD"},
        {"code": "8058.T", "name": "三菱商事"},
    ],
    "イーロン": [
        {"code": "TSLA",   "name": "テスラ (米国)"},
        {"code": "6752.T", "name": "パナソニックHD"},
        {"code": "5713.T", "name": "住友金属鉱山"},
        {"code": "9433.T", "name": "KDDI (Starlink)"},
        {"code": "7270.T", "name": "SUBARU"},
    ]
}

@st.cache_data(ttl=1800)
def fetch_and_analyze(code, name):
    try:
        df = yf.Ticker(code).history(period="1y")
        if len(df) < 30:
            return None

        df['Prev_Close'] = df['Close'].shift(1)
        df['Day_Return'] = (df['Close'] - df['Prev_Close']) / df['Prev_Close'] * 100
        df['MA5'] = df['Close'].rolling(5).mean()
        df['Vol_MA20'] = df['Volume'].rolling(20).mean()
        df['Next_Open'] = df['Open'].shift(-1)
        df['Morning_Up'] = df['Next_Open'] > df['Close']

        cond_breakout = (df['Close'] > df['MA5']) & (df['Volume'] > df['Vol_MA20'] * 1.2)
        cond_uptrend = (df['Close'] > df['MA5']) & (df['Day_Return'] > 0)
        cond_dip = df['Day_Return'] <= -2.0
        cond_up = df['Day_Return'] > 0
        cond_down = df['Day_Return'] <= 0

        latest = df.iloc[-1]
        history = df.iloc[:-1].dropna(subset=['Next_Open', 'MA5', 'Vol_MA20'])

        if cond_breakout.iloc[-1]:
            signal = "🔥 5日線突破＋出来高急増"
            sub = history[cond_breakout.iloc[:-1]]
        elif cond_dip.iloc[-1]:
            signal = "💧 急落後の反発狙い(-2%以下)"
            sub = history[cond_dip.iloc[:-1]]
        elif cond_uptrend.iloc[-1]:
            signal = "📈 5日線キープ＋陽線"
            sub = history[cond_uptrend.iloc[:-1]]
        elif cond_up.iloc[-1]:
            signal = "☀️ 前日比プラス引け"
            sub = history[cond_up.iloc[:-1]]
        else:
            signal = "☁️ 前日比マイナス・調整"
            sub = history[cond_down.iloc[:-1]]

        if len(sub) < 5:
            sub = history
            signal += " (全体統計)"

        total = len(sub)
        wins = int(sub['Morning_Up'].sum())
        prob = round((wins / total) * 100, 1)
        avg_gap = round(((sub['Next_Open'] - sub['Close']) / sub['Close'] * 100).mean(), 2)

        clean_code = code.replace(".T", "")
        if ".T" in code:
            url = f"https://www.rakuten-sec.co.jp/smartphone/market/info/pagecontent.html?ric={clean_code}.T"
            price = f"{latest['Close']:,.0f}円"
        else:
            url = f"https://www.rakuten-sec.co.jp/web/market/search/us_search/quote.html?ric={clean_code}.O"
            price = f"${latest['Close']:,.2f}"

        return {
            "code": clean_code, "name": name, "price": price,
            "diff": round(latest['Day_Return'], 2), "signal": signal,
            "prob": prob, "count": f"{wins}/{total}回", "gap": avg_gap, "url": url
        }
    except Exception:
        return None

if st.button("🔄 最新データに更新"):
    st.cache_data.clear()

tabs = st.tabs(list(STOCK_LIST.keys()))

for tab, (genre, stocks) in zip(tabs, STOCK_LIST.items()):
    with tab:
        results = []
        with st.spinner(f"{genre}銘柄の統計を計算中..."):
            for s in stocks:
                res = fetch_and_analyze(s["code"], s["name"])
                if res:
                    results.append(res)
        
        results.sort(key=lambda x: x["prob"], reverse=True)
        
        for r in results:
            diff_color = "#dc2626" if r["diff"] > 0 else "#2563eb"
            diff_sign = "+" if r["diff"] > 0 else ""
            gap_sign = "+" if r["gap"] > 0 else ""
            
            st.markdown(f"""
            <div class="stock-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <span style="font-size:16px; font-weight:bold; color:#1e293b;">{r['name']}</span>
                        <span style="font-size:12px; color:#64748b;">({r['code']})</span><br>
                        <span style="font-size:14px; color:#334155;">終値: <b>{r['price']}</b> 
                        (<span style="color:{diff_color}; font-weight:bold;">{diff_sign}{r['diff']}%</span>)</span>
                    </div>
                    <div style="text-align:right;">
                        <span style="font-size:11px; color:#64748b;">翌朝上昇確率</span><br>
                        <span class="prob-badge">{r['prob']}%</span>
                        <div style="font-size:11px; color:#64748b;">({r['count']} / 平均{gap_sign}{r['gap']}%)</div>
                    </div>
                </div>
                <div class="signal-tag">{r['signal']}</div>
                <a class="rakuten-btn" href="{r['url']}" target="_blank">楽天証券（スマホ版）で確認 ▶</a>
            </div>
            """, unsafe_allow_html=True)
