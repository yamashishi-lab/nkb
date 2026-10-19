import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import unicodedata

# スマホ画面向けにページ設定
st.set_page_config(page_title="翌朝株価 クオンツ＆AIスコア Pro", page_icon="📈", layout="centered")

# スマホで見やすいカスタムCSS（6分割マクロバナー＆トレード目安ボックス搭載）
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
.span-2 {
    grid-column: span 2;
}
.span-3 {
    grid-column: span 3;
}
@media (max-width: 340px) {
    .span-2, .span-3 {
        grid-column: span 6;
    }
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
.prob-badge {
    font-size: 22px;
    font-weight: bold;
    color: #dc2626;
}
.rank-badge {
    display: inline-block;
    background: linear-gradient(135deg, #f59e0b, #d97706);
    color: #ffffff;
    padding: 3px 9px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: bold;
    margin-right: 4px;
    margin-bottom: 6px;
}
.score-badge {
    display: inline-block;
    background: linear-gradient(135deg, #1e293b, #334155);
    color: #f8fafc;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: bold;
    margin-bottom: 6px;
}
.macro-badge {
    display: inline-block;
    background: #eff6ff;
    color: #1d4ed8;
    border: 1px solid #bfdbfe;
    padding: 2px 8px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: bold;
    margin-left: 4px;
}
.edge-badge {
    display: inline-block;
    background: #f0fdf4;
    color: #15803d;
    border: 1px solid #bbf7d0;
    padding: 2px 8px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: bold;
    margin-left: 4px;
}
.genre-badge {
    display: inline-block;
    background: #f3e8ff;
    color: #6b21a8;
    border: 1px solid #e9d5ff;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 10px;
    font-weight: bold;
    margin-left: 6px;
    vertical-align: middle;
}
.signal-tag {
    display: inline-block;
    background: #fef2f2;
    color: #991b1b;
    border: 1px solid #fecaca;
    padding: 4px 8px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: bold;
    margin-top: 8px;
}
.metrics-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px 10px;
    margin-top: 8px;
    font-size: 11px;
    color: #475569;
    background: #f8fafc;
    padding: 8px 10px;
    border-radius: 6px;
    border: 1px solid #e2e8f0;
}
/* 翌朝トレード目安ライン（ATR自動算出）の3列グリッド */
.trade-plan-box {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
    margin-top: 8px;
    background: #f8fafc;
    padding: 8px 6px;
    border-radius: 8px;
    border: 1px dashed #cbd5e1;
    text-align: center;
}
.trade-plan-item {
    min-width: 0;
}
.factor-box {
    background: #f1f5f9;
    border-radius: 8px;
    padding: 10px 12px;
    margin-top: 10px;
    font-size: 12px;
    color: #1e293b;
    line-height: 1.5;
}
.factor-title {
    font-weight: bold;
    color: #0f172a;
    margin-bottom: 4px;
    font-size: 12px;
}
</style>
""", unsafe_allow_html=True)

st.title("📱 翌朝株価 クオンツ＆AI解析")
st.caption("総合TOP5ランキング × ATR利確・損切り算出 × 米国市場・為替・CME先物・VIX連動")

STOCK_LIST = {
    "半導体": [
        {"code": "8035.T", "name": "東京エレクトロン", "theme": "前工程装置の国内筆頭。海外勢の指数買いが入りやすい"},
        {"code": "6857.T", "name": "アドバンテスト", "theme": "AI半導体向けテスタで高シェア。米SOX指数と連動性大"},
        {"code": "6920.T", "name": "レーザーテック", "theme": "EUVマスク欠陥検査装置。ボラティリティが高く短期資金が集中"},
        {"code": "6146.T", "name": "ディスコ", "theme": "HBM（広帯域メモリ）向け切断・研削装置で高収益"},
        {"code": "6723.T", "name": "ルネサス", "theme": "車載・産業・データセンター向けパワー半導体を展開"},
    ],
    "AI": [
        {"code": "9984.T", "name": "ソフトバンクG", "theme": "傘下ArmやAI投資群の評価益期待。先物主導で寄り付きが動きやすい"},
        {"code": "3778.T", "name": "さくらネット", "theme": "政府クラウド・生成AI向けGPUクラウドの国策銘柄"},
        {"code": "3993.T", "name": "PKSHA", "theme": "自然言語処理・AIアルゴリズム開発。好採算のソフトウエア需要"},
        {"code": "4180.T", "name": "Appier", "theme": "AIマーケティングSaaS。グロース市場の資金流入先"},
        {"code": "4307.T", "name": "野村総合研究所", "theme": "企業のAI導入・DXシステム刷新およびデータセンター運営"},
    ],
    "宇宙": [
        {"code": "5595.T", "name": "QPS研究所", "theme": "小型SAR衛星コンステレーション。防衛・安全保障テーマ"},
        {"code": "9348.T", "name": "ispace", "theme": "月面開発・輸送プログラム。イベントドリブンで出来高が急増しやすい"},
        {"code": "186A.T", "name": "アストロスケール", "theme": "スペースデブリ（宇宙ごみ）除去の世界的リーダー"},
        {"code": "9412.T", "name": "スカパーJSAT", "theme": "アジア最大の衛星通信。防衛省向け宇宙監視・低軌道衛星連携"},
        {"code": "7011.T", "name": "三菱重工業", "theme": "H3ロケット打ち上げ及び防衛予算拡大の国策中核銘柄"},
    ],
    "AI電力・インフラ": [
        {"code": "9509.T", "name": "北海道電力", "theme": "ラピダスおよび大規模AIデータセンター誘致による電力需要急増期待"},
        {"code": "9508.T", "name": "九州電力", "theme": "TSMC熊本工場や半導体工場群の増設に伴う大口産業用電力の拡大"},
        {"code": "5803.T", "name": "フジクラ", "theme": "生成AIデータセンター向け超多芯光ファイバー・コネクタ需要が世界的に逼迫"},
        {"code": "6501.T", "name": "日立製作所", "theme": "世界の送配電網（グリッド）設備更新とAIデータセンター向け変電システム"},
        {"code": "6622.T", "name": "ダイヘン", "theme": "AIデータセンターや再生可能エネルギー接続に不可欠な変圧器・受変電設備"},
    ],
    "イーロン": [
        {"code": "TSLA",   "name": "テスラ (米国)", "theme": "自動運転(FSD)・ロボタクシー・人型ロボットOptimusのAI展開"},
        {"code": "6752.T", "name": "パナソニックHD", "theme": "北米EV向け車載電池およびデータセンター向け蓄電システム"},
        {"code": "5713.T", "name": "住友金属鉱山", "theme": "EV電池向け正極材（ニッケル）および銅などの資源価格連動"},
        {"code": "9433.T", "name": "KDDI (Starlink)", "theme": "SpaceXのStarlinkを活用した衛星・スマホ直接通信サービス"},
        {"code": "7270.T", "name": "SUBARU", "theme": "北米市場でのEV展開・テスラ充電規格（NACS）採用など米国関連"},
    ]
}

KNOWN_STOCKS = {}
for g, items in STOCK_LIST.items():
    for item in items:
        KNOWN_STOCKS[item["code"]] = {"name": item["name"], "theme": item["theme"], "genre": g}

def normalize_ticker(raw_input):
    s = unicodedata.normalize('NFKC', raw_input).strip().upper()
    if not s:
        return ""
    if "." in s or s.startswith("^") or "=" in s:
        return s
    if len(s) == 4 and any(ch.isdigit() for ch in s):
        return f"{s}.T"
    return s

# --- 米国市場・為替・CME日経先物・VIXの取得関数 ---
@st.cache_data(ttl=900)
def fetch_macro_market():
    macro_tickers = {
        "sp500":  {"codes": ["^GSPC"],         "label": "🇺🇸 米S&P500"},
        "sox":    {"codes": ["^SOX"],          "label": "💽 米SOX半導体"},
        "usdjpy": {"codes": ["JPY=X"],         "label": "💴 ドル円為替"},
        "nk_fut": {"codes": ["NIY=F", "^N225"], "label": "🇯🇵 CME日経先物"},
        "vix":    {"codes": ["^VIX"],          "label": "⚡ VIX恐怖指数"}
    }
    macro_data = {}
    for key, info in macro_tickers.items():
        fetched = False
        for c in info["codes"]:
            try:
                df_m = yf.Ticker(c).history(period="5d")
                df_m = df_m.dropna(subset=['Close'])
                if not df_m.empty and len(df_m) >= 2:
                    latest_c = float(df_m['Close'].iloc[-1])
                    prev_c = float(df_m['Close'].iloc[-2])
                    diff_pct = round((latest_c - prev_c) / prev_c * 100, 2)
                    lbl = info["label"]
                    if key == "nk_fut" and c == "^N225":
                        lbl = "🇯🇵 日経平均(現物)"
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
        df = ticker_obj.history(period="1y")
        if df.empty or len(df) < 40:
            return None

        if code in KNOWN_STOCKS:
            name = name or KNOWN_STOCKS[code]["name"]
            theme = theme or KNOWN_STOCKS[code]["theme"]
            genre = KNOWN_STOCKS[code]["genre"]
        else:
            if not name or not theme:
                try:
                    info = ticker_obj.info
                    if not name:
                        name = info.get("shortName") or info.get("longName") or code.replace(".T", "")
                    if not theme:
                        sector = info.get("sector", "")
                        industry = info.get("industry", "")
                        if sector or industry:
                            theme = f"セクター: {sector} / 業種: {industry}（カスタム銘柄診断）"
                            if "Technology" in sector or "Semiconductor" in industry:
                                genre = "半導体"
                        else:
                            theme = "カスタム指定銘柄（過去1年の日足・需給データに基づく統計解析）"
                except Exception:
                    name = name or code.replace(".T", "")
                    theme = theme or "カスタム指定銘柄（過去1年の日足・需給データに基づく統計解析）"

        # 1. 基本移動平均・出来高
        df['Prev_Close'] = df['Close'].shift(1)
        df['Day_Return'] = (df['Close'] - df['Prev_Close']) / df['Prev_Close'] * 100
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['Vol_MA20'] = df['Volume'].rolling(20).mean().replace(0, np.nan)
        df['Vol_Ratio'] = (df['Volume'] / df['Vol_MA20']).fillna(1.0)

        # 2. Wilder式RSI (14日)
        delta = df['Close'].diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss.replace(0, np.nan)
        df['RSI'] = (100 - (100 / (1 + rs))).fillna(50.0)

        # 3. ボリンジャーバンド (20日)
        df['BB_Std'] = df['Close'].rolling(20).std().replace(0, np.nan)
        df['BB_Sigma'] = ((df['Close'] - df['MA20']) / df['BB_Std']).fillna(0.0)

        # 4. MACD (12, 26, 9) モメンタム解析
        ema12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = ema12 - ema26
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
        df['MACD_Hist_Diff'] = df['MACD_Hist'].diff()

        # 5. ATR (Average True Range: 14日ボラティリティ)
        tr1 = df['High'] - df['Low']
        tr2 = (df['High'] - df['Prev_Close']).abs()
        tr3 = (df['Low'] - df['Prev_Close']).abs()
        df['TR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['ATR'] = df['TR'].rolling(14).mean().fillna(df['Close'] * 0.02)
        df['ATR_Pct'] = (df['ATR'] / df['Close'] * 100).fillna(2.0)

        # 6. ローソク足プライスアクション（引け位置・下ヒゲ吸収率）
        high_low = (df['High'] - df['Low']).replace(0, np.nan)
        df['Close_Pos'] = ((df['Close'] - df['Low']) / high_low).fillna(0.5)
        body_bottom = df[['Open', 'Close']].min(axis=1)
        df['Lower_Shadow'] = ((body_bottom - df['Low']) / high_low).fillna(0.0)

        # 翌朝ギャップ計測
        df['Next_Open'] = df['Open'].shift(-1)
        df['Gap_Pct'] = (df['Next_Open'] - df['Close']) / df['Close'] * 100
        df['Morning_Up'] = df['Next_Open'] > df['Close']

        # マルチファクター・シグナル定義
        cond_squeeze_break = (df['Close'] > df['MA20']) & (df['MACD_Hist'] > 0) & (df['MACD_Hist_Diff'] > 0) & (df['Vol_Ratio'] >= 1.2)
        cond_pinbar_rev = (df['Lower_Shadow'] >= 0.45) & (df['Close_Pos'] >= 0.6) & (df['RSI'] < 50)
        cond_strong_close = (df['Close'] > df['MA5']) & (df['Close_Pos'] >= 0.75) & (df['Day_Return'] > 0)
        cond_oversold = (df['RSI'] < 38) & (df['BB_Sigma'] <= -1.3)
        cond_uptrend = (df['Close'] > df['MA5']) & (df['MACD'] > df['MACD_Signal'])
        cond_up = df['Day_Return'] > 0
        cond_down = df['Day_Return'] <= 0

        latest = df.iloc[-1]
        history = df.iloc[:-1].dropna(subset=['Next_Open', 'MA20', 'RSI', 'MACD_Hist'])

        if len(history) == 0:
            return None

        if cond_squeeze_break.iloc[-1]:
            signal = "🔥 MACD加速＋出来高ブレイク"
            sub = history[cond_squeeze_break.reindex(history.index, fill_value=False)]
        elif cond_pinbar_rev.iloc[-1]:
            signal = "🔨 下ヒゲ吸収（大口の買い支え）"
            sub = history[cond_pinbar_rev.reindex(history.index, fill_value=False)]
        elif cond_strong_close.iloc[-1]:
            signal = "💪 高値引け・強気モメンタム"
            sub = history[cond_strong_close.reindex(history.index, fill_value=False)]
        elif cond_oversold.iloc[-1]:
            signal = "⚡ BBマイナス圏・売られすぎ反発"
            sub = history[cond_oversold.reindex(history.index, fill_value=False)]
        elif cond_uptrend.iloc[-1]:
            signal = "📈 5日線＆MACDゴールデンクロス圏"
            sub = history[cond_uptrend.reindex(history.index, fill_value=False)]
        elif cond_up.iloc[-1]:
            signal = "☀️ 陽線・プラス引け推移"
            sub = history[cond_up.reindex(history.index, fill_value=False)]
        else:
            signal = "☁️ 押し目・調整局面"
            sub = history[cond_down.reindex(history.index, fill_value=False)]

        if len(sub) < 5:
            sub = history
            signal += " (全体統計)"

        total = len(sub)
        wins = int(sub['Morning_Up'].sum())
        prob = round((wins / total) * 100, 1)
        avg_gap = round(float(sub['Gap_Pct'].mean()), 2)

        # 7. ケリー基準ベースの期待値エッジ計算
        win_gaps = sub[sub['Morning_Up']]['Gap_Pct']
        loss_gaps = sub[~sub['Morning_Up']]['Gap_Pct']
        avg_win = float(win_gaps.mean()) if len(win_gaps) > 0 else 0.5
        avg_loss = abs(float(loss_gaps.mean())) if len(loss_gaps) > 0 else 0.5
        payoff_ratio = round(avg_win / max(avg_loss, 0.1), 2)
        expected_edge = round((prob / 100 * avg_win) - ((100 - prob) / 100 * avg_loss), 2)

        # 8. 5指標マクロ地合い補正
        macro_score = 0
        macro_reasons = []
        if macro:
            sp_diff = macro["sp500"]["diff"]
            sox_diff = macro["sox"]["diff"]
            fx_diff = macro["usdjpy"]["diff"]
            nk_diff = macro["nk_fut"]["diff"]
            vix_price = macro["vix"]["price"]
            vix_diff = macro["vix"]["diff"]

            if genre in ["半導体", "AI", "AI電力・インフラ"]:
                if sox_diff >= 1.0:
                    macro_score += 5
                    macro_reasons.append(f"米SOX指数が<b>+{sox_diff}%</b>と強く上昇しており、ハイテク・半導体関連の寄付きに強い追い風です。")
                elif sox_diff > 0:
                    macro_score += 2
                elif sox_diff <= -1.5:
                    macro_score -= 5
                    macro_reasons.append(f"米SOX指数が<b>{sox_diff}%</b>と下落しており、朝方はハイテク株の売り先行に警戒が必要です。")

            if sp_diff >= 0.5:
                macro_score += 2
            elif sp_diff <= -0.8:
                macro_score -= 2

            if ".T" in code:
                if nk_diff >= 0.6:
                    macro_score += 4
                    macro_reasons.append(f"CME日経先物が<b>+{nk_diff}%</b>と上昇しており、日本市場全体のギャップアップ期待を高めています。")
                elif nk_diff >= 0.2:
                    macro_score += 2
                elif nk_diff <= -0.6:
                    macro_score -= 4
                    macro_reasons.append(f"CME日経先物が<b>{nk_diff}%</b>と軟調で、寄り付きは指数主導の売り気配に注意が必要です。")

                if fx_diff >= 0.3:
                    macro_score += 2
                    macro_reasons.append(f"ドル円が<b>+{fx_diff}%</b>と円安推移しており、先物・主力株の下支え要因となっています。")
                elif fx_diff <= -0.5:
                    macro_score -= 2

            if vix_price > 0:
                if vix_price >= 22.0 or vix_diff >= 8.0:
                    macro_score -= 4
                    macro_reasons.append(f"VIX恐怖指数が<b>{vix_price:.1f} ({vix_diff:+.1f}%)</b>と警戒域にあり、機関投資家のリスク回避売りに注意が必要です。")
                elif vix_price < 18.0 or vix_diff <= -5.0:
                    macro_score += 2
                    if vix_diff <= -5.0:
                        macro_reasons.append(f"VIX恐怖指数が<b>{vix_diff}%</b>と低下しており、市場心理の改善から買い安心感が広がっています。")

        # 解説テキスト生成
        reasons = []
        if macro_reasons:
            reasons.extend(macro_reasons)

        if latest['MACD_Hist'] > 0 and latest['MACD_Hist_Diff'] > 0:
            reasons.append("MACDヒストグラムがプラス圏で拡大しており、<b>機関投資家のトレンドフォロー買い</b>が加速しやすい波形です。")
        elif latest['Lower_Shadow'] >= 0.45:
            reasons.append(f"日中の下押しから<b>下ヒゲ（全体の{latest['Lower_Shadow']*100:.0f}%）</b>を引いて買い戻されており、下値の強い買い板が確認できます。")

        if latest['Vol_Ratio'] >= 1.4:
            reasons.append(f"出来高が20日平均の<b>{latest['Vol_Ratio']:.1f}倍</b>に急増し、大口資金の流入が顕著です。")

        if latest['Close'] > latest['MA5'] and latest['Close_Pos'] >= 0.75:
            reasons.append("5日移動平均線の上で<b>高値引け（買い残し大）</b>しており、翌朝も成行買いが先行しやすい形です。")

        if expected_edge > 0.15:
            reasons.append(f"損益レシオが<b>{payoff_ratio}倍</b>（期待値<b>+{expected_edge}%</b>）と高く、リスクに対してリターンが優位な局面です。")

        if not reasons:
            reasons.append(f"過去同条件では{total}回中<b>{wins}回</b>ギャップアップ（平均{avg_gap:+.2f}%）しています。")

        # 総合AIスコア算出
        base_score = min(max(prob * 0.65, 10), 52)
        edge_score = min(max((expected_edge + 0.3) * 15, 0), 18)
        tech_score = 0
        if latest['Vol_Ratio'] >= 1.2: tech_score += 5
        if latest['Close_Pos'] >= 0.7: tech_score += 5
        if latest['MACD_Hist_Diff'] > 0: tech_score += 5
        if payoff_ratio >= 1.2: tech_score += 5
        if 45 <= latest['RSI'] <= 68 or latest['RSI'] <= 35: tech_score += 4

        ai_score = int(min(max(round(base_score + edge_score + tech_score + macro_score), 15), 99))

        # 9. 【新規】ATRベースの翌朝トレード目安ライン算出（予想寄付き・利確目標・損切り目安）
        close_val = float(latest['Close'])
        atr_val = float(latest['ATR'])
        est_open_val = close_val * (1.0 + (avg_gap / 100.0))
        tp_val = max(est_open_val, close_val) + (atr_val * 0.8)  # 利確目標: +0.8 ATR
        sl_val = min(est_open_val, close_val) - (atr_val * 0.5)  # 損切り目安: -0.5 ATR

        tp_pct = round((tp_val - close_val) / close_val * 100, 1)
        sl_pct = round((sl_val - close_val) / close_val * 100, 1)

        is_jp = ".T" in code
        def fmt_p(v):
            return f"{v:,.0f}円" if is_jp else f"${v:,.2f}"

        clean_code = code.replace(".T", "")
        macd_state = "強気↑" if latest['MACD_Hist'] > 0 else "調整↓"

        return {
            "code": clean_code, "name": name, "genre": genre,
            "price": fmt_p(close_val),
            "est_open": fmt_p(est_open_val),
            "tp_price": fmt_p(tp_val), "tp_pct": tp_pct,
            "sl_price": fmt_p(sl_val), "sl_pct": sl_pct,
            "diff": round(float(latest['Day_Return']), 2), "signal": signal,
            "prob": prob, "count": f"{wins}/{total}回", "gap": avg_gap,
            "rsi": round(float(latest['RSI']), 1),
            "vol_ratio": round(float(latest['Vol_Ratio']), 2),
            "bb_sigma": round(float(latest['BB_Sigma']), 2),
            "macd_state": macd_state,
            "atr_pct": round(float(latest['ATR_Pct']), 1),
            "payoff": payoff_ratio,
            "edge": expected_edge,
            "ai_score": ai_score,
            "macro_score": macro_score,
            "theme": theme,
            "reasons": " / ".join(reasons)
        }
    except Exception:
        return None

def render_stock_card(r, is_custom=False, rank=None):
    diff_color = "#dc2626" if r["diff"] > 0 else "#2563eb"
    diff_sign = "+" if r["diff"] > 0 else ""
    gap_sign = "+" if r["gap"] > 0 else ""
    sigma_sign = "+" if r["bb_sigma"] > 0 else ""
    edge_sign = "+" if r["edge"] > 0 else ""

    if is_custom:
        card_class = "search-result-card"
    elif rank is not None:
        card_class = "rank-card"
    else:
        card_class = "stock-card"

    rank_html = ""
    genre_html = ""
    if rank is not None:
        medals = {1: "🥇 第1位", 2: "🥈 第2位", 3: "🥉 第3位", 4: "🏅 第4位", 5: "🏅 第5位"}
        rank_label = medals.get(rank, f"第{rank}位")
        rank_html = f'<span class="rank-badge">{rank_label}</span>'
        genre_html = f'<span class="genre-badge">{r["genre"]}</span>'

    m_score = r["macro_score"]
    if m_score > 0:
        macro_badge_html = f'<span class="macro-badge">🌐 地合い +{m_score}点</span>'
    elif m_score < 0:
        macro_badge_html = f'<span class="macro-badge" style="background:#fef2f2; color:#b91c1c; border-color:#fecaca;">🌐 地合い {m_score}点</span>'
    else:
        macro_badge_html = '<span class="macro-badge" style="background:#f1f5f9; color:#64748b; border-color:#cbd5e1;">🌐 地合い ±0</span>'

    edge_badge_html = f'<span class="edge-badge">📐 損益比 {r["payoff"]}倍 (期待値{edge_sign}{r["edge"]}%)</span>'

    html_card = (
        f'<div class="{card_class}">'
        f'<div>{rank_html}<span class="score-badge">🤖 AIスコア: {r["ai_score"]} / 100</span>{macro_badge_html}{edge_badge_html}</div>'
        f'<div style="display:flex; justify-content:space-between; align-items:center; margin-top:4px;">'
        f'<div><span style="font-size:16px; font-weight:bold; color:#1e293b;">{r["name"]}</span> '
        f'<span style="font-size:12px; color:#64748b;">({r["code"]})</span>{genre_html}<br>'
        f'<span style="font-size:14px; color:#334155;">終値: <b>{r["price"]}</b> '
        f'(<span style="color:{diff_color}; font-weight:bold;">{diff_sign}{r["diff"]}%</span>)</span></div>'
        f'<div style="text-align:right;"><span style="font-size:11px; color:#64748b;">翌朝上昇確率</span><br>'
        f'<span class="prob-badge">{r["prob"]}%</span>'
        f'<div style="font-size:11px; color:#64748b;">({r["count"]} / 平均{gap_sign}{r["gap"]}%)</div></div>'
        f'</div>'
        f'<div class="signal-tag">{r["signal"]}</div>'
        f'<div class="metrics-row">'
        f'<span>📊 <b>RSI:</b> {r["rsi"]}</span>'
        f'<span>📈 <b>MACD:</b> {r["macd_state"]}</span>'
        f'<span>🔊 <b>出来高:</b> {r["vol_ratio"]}倍</span>'
        f'<span>📏 <b>BB:</b> {sigma_sign}{r["bb_sigma"]}σ</span>'
        f'<span>⚡ <b>1日変動(ATR):</b> {r["atr_pct"]}%</span>'
        f'</div>'
        f'<div class="trade-plan-box">'
        f'<div class="trade-plan-item">'
        f'<div style="font-size:10px; color:#64748b;">🌅 予想寄付き目安</div>'
        f'<div style="font-size:12px; font-weight:bold; color:#0f172a; margin-top:2px;">{r["est_open"]}</div>'
        f'<div style="font-size:10px; color:#64748b;">(平均{gap_sign}{r["gap"]}%)</div>'
        f'</div>'
        f'<div class="trade-plan-item" style="border-left:1px solid #e2e8f0; border-right:1px solid #e2e8f0;">'
        f'<div style="font-size:10px; color:#15803d; font-weight:bold;">🎯 利確目標 (+0.8ATR)</div>'
        f'<div style="font-size:12px; font-weight:bold; color:#15803d; margin-top:2px;">{r["tp_price"]}</div>'
        f'<div style="font-size:10px; color:#16a34a;">(+{r["tp_pct"]}%)</div>'
        f'</div>'
        f'<div class="trade-plan-item">'
        f'<div style="font-size:10px; color:#b91c1c; font-weight:bold;">🛡️ 損切り目安 (-0.5ATR)</div>'
        f'<div style="font-size:12px; font-weight:bold; color:#b91c1c; margin-top:2px;">{r["sl_price"]}</div>'
        f'<div style="font-size:10px; color:#dc2626;">({r["sl_pct"]}%)</div>'
        f'</div>'
        f'</div>'
        f'<div class="factor-box">'
        f'<div class="factor-title">💡 クオンツ解析・上昇期待の背景</div>'
        f'<div style="margin-bottom:4px;"><b>【テーマ】</b> {r["theme"]}</div>'
        f'<div><b>【需給・テクニカル判定】</b> {r["reasons"]}</div>'
        f'</div></div>'
    )
    st.markdown(html_card, unsafe_allow_html=True)

if st.button("🔄 最新データに更新"):
    st.cache_data.clear()

# --- 画面上部: 5指標マクロダッシュボード ---
macro_info = fetch_macro_market()

def fmt_macro(item, span_class="span-2", mode="index"):
    d = item["diff"]
    sign = "+" if d > 0 else ""

    if mode == "vix":
        color = "#f87171" if (d > 3.0 or item["price"] >= 22) else ("#4ade80" if d < 0 else "#cbd5e1")
    else:
        color = "#4ade80" if d > 0 else ("#f87171" if d < 0 else "#cbd5e1")

    if item["price"] == 0:
        val_str = "取得中/休場"
        diff_str = "-"
    else:
        if mode == "fx":
            val_str = f"{item['price']:,.2f}円"
        elif mode == "vix":
            val_str = f"{item['price']:,.2f} pt"
        elif mode == "nk":
            val_str = f"{item['price']:,.0f}円"
        else:
            val_str = f"{item['price']:,.0f}"
        diff_str = f"{sign}{d}%"

    return (
        f'<div class="market-item {span_class}">'
        f'<div style="font-size:10px; color:#cbd5e1; white-space:nowrap;">{item["label"]}</div>'
        f'<div style="font-size:13px; font-weight:bold; margin-top:2px; color:#f8fafc;">{val_str}</div>'
        f'<div style="font-size:11px; font-weight:bold; color:{color};">{diff_str}</div>'
        f'</div>'
    )

sp_item  = macro_info.get("sp500",  {"price": 0, "diff": 0, "label": "🇺🇸 米S&P500"})
sox_item = macro_info.get("sox",    {"price": 0, "diff": 0, "label": "💽 米SOX半導体"})
fx_item  = macro_info.get("usdjpy", {"price": 0, "diff": 0, "label": "💴 ドル円為替"})
nk_item  = macro_info.get("nk_fut", {"price": 0, "diff": 0, "label": "🇯🇵 CME日経先物"})
vix_item = macro_info.get("vix",    {"price": 0, "diff": 0, "label": "⚡ VIX恐怖指数"})

banner_html = (
    '<div class="market-banner">'
    '<div class="market-title">🌐 米国市場・為替・CME先物・VIXフィルター（翌朝の寄付き地合い補正）</div>'
    '<div class="market-grid">'
    f'{fmt_macro(sp_item, span_class="span-2", mode="index")}'
    f'{fmt_macro(sox_item, span_class="span-2", mode="index")}'
    f'{fmt_macro(fx_item, span_class="span-2", mode="fx")}'
    f'{fmt_macro(nk_item, span_class="span-3", mode="nk")}'
    f'{fmt_macro(vix_item, span_class="span-3", mode="vix")}'
    '</div></div>'
)
st.markdown(banner_html, unsafe_allow_html=True)

# --- 任意の証券コード診断セクション ---
with st.container():
    col1, col2 = st.columns([3, 1])
    with col1:
        custom_input = st.text_input(
            "🔍 任意の銘柄コードを診断（日本株は4桁、米国株はティッカー）",
            placeholder="例: 7203, 8306, NVDA, AAPL"
        )
    with col2:
        st.write("")
        search_clicked = st.button("診断する", use_container_width=True)

if custom_input or search_clicked:
    norm_code = normalize_ticker(custom_input)
    if norm_code:
        with st.spinner(f"「{norm_code}」のマルチファクター・アルゴリズムを解析中..."):
            custom_res = fetch_and_analyze(norm_code, macro=macro_info)
        if custom_res:
            st.markdown("##### 🎯 個別銘柄のリアルタイム診断結果")
            render_stock_card(custom_res, is_custom=True)
        else:
            st.error(f"証券コード「{custom_input}」のデータが見つかりませんでした。半角で正しいコードを入力してください。")

# --- 全銘柄の一括解析（重複実行を防ぎ高速化） ---
genre_results = {g: [] for g in STOCK_LIST.keys()}
all_results = []

with st.spinner("全25銘柄のクオンツアルゴリズム＆総合ランキングを一括解析中..."):
    for genre, stocks in STOCK_LIST.items():
        for s in stocks:
            res = fetch_and_analyze(s["code"], s["name"], s["theme"], genre, macro_info)
            if res:
                genre_results[genre].append(res)
                all_results.append(res)

# --- タブ表示（先頭に「🏆 総合TOP5」を配置） ---
tab_labels = ["🏆 総合TOP5"] + list(STOCK_LIST.keys())
tabs = st.tabs(tab_labels)

# 1. 総合TOP5タブ
with tabs[0]:
    st.caption("全ジャンル25銘柄から、AIスコア・期待値エッジ・翌朝勝率が最も高い上位5銘柄を自動抽出しています。")
    if not all_results:
        st.warning("データの取得に失敗しました。時間をおいて再試行してください。")
    else:
        top5_list = sorted(all_results, key=lambda x: (x["ai_score"], x["edge"], x["prob"]), reverse=True)[:5]
        for idx, r in enumerate(top5_list, start=1):
            render_stock_card(r, rank=idx)

# 2. 各ジャンル別タブ
for tab, genre in zip(tabs[1:], STOCK_LIST.keys()):
    with tab:
        results = genre_results.get(genre, [])
        if not results:
            st.warning("データの取得に失敗しました。時間をおいて再試行してください。")
            continue

        results.sort(key=lambda x: (x["ai_score"], x["edge"], x["prob"]), reverse=True)
        for r in results:
            render_stock_card(r)
