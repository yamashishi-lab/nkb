import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import unicodedata

# スマホ画面向けにページ設定
st.set_page_config(page_title="翌朝株価 統計＆AIスコア", page_icon="📈", layout="centered")

# スマホで見やすいカスタムCSS
st.markdown("""
<style>
.market-banner {
    background: linear-gradient(135deg, #0f172a, #1e293b);
    color: #f8fafc;
    border-radius: 12px;
    padding: 12px 14px;
    margin-bottom: 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.12);
}
.market-title {
    font-size: 12px;
    font-weight: bold;
    color: #94a3b8;
    margin-bottom: 8px;
}
.market-grid {
    display: flex;
    justify-content: space-between;
    gap: 8px;
}
.market-item {
    background: rgba(255, 255, 255, 0.07);
    border-radius: 8px;
    padding: 8px 10px;
    flex: 1;
    text-align: center;
}
.stock-card {
    background-color: #ffffff;
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 14px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    border-left: 6px solid #dc2626;
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
    margin-left: 6px;
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
    gap: 8px;
    margin-top: 8px;
    font-size: 11px;
    color: #475569;
    background: #f8fafc;
    padding: 6px 10px;
    border-radius: 6px;
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

st.title("📱 翌朝株価の統計＆アルゴリズム分析")
st.caption("過去1年のシグナル別勝率 × Wilder式RSI・BB・出来高 × 米国市場・為替連動フィルター")

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

# 登録済み銘柄の辞書マップ（カスタム検索時に日本語名やテーマがあれば引き継ぐため）
KNOWN_STOCKS = {}
for g, items in STOCK_LIST.items():
    for item in items:
        KNOWN_STOCKS[item["code"]] = {"name": item["name"], "theme": item["theme"], "genre": g}

def normalize_ticker(raw_input):
    """入力された証券コードを正規化（全角→半角、日本株の.T自動付与）"""
    s = unicodedata.normalize('NFKC', raw_input).strip().upper()
    if not s:
        return ""
    if "." in s or s.startswith("^") or "=" in s:
        return s
    # 数字が含まれる4桁コード（例: 7203, 186A）は日本株として .T を付与
    if len(s) == 4 and any(ch.isdigit() for ch in s):
        return f"{s}.T"
    return s

# --- 米国市場・為替データの取得関数 ---
@st.cache_data(ttl=900)
def fetch_macro_market():
    macro_tickers = {
        "sp500": {"code": "^GSPC", "label": "米S&P500"},
        "sox":   {"code": "^SOX",  "label": "米SOX半導体"},
        "usdjpy":{"code": "JPY=X", "label": "ドル円"}
    }
    macro_data = {}
    for key, info in macro_tickers.items():
        try:
            df_m = yf.Ticker(info["code"]).history(period="5d")
            if len(df_m) >= 2:
                latest_c = float(df_m['Close'].iloc[-1])
                prev_c = float(df_m['Close'].iloc[-2])
                diff_pct = round((latest_c - prev_c) / prev_c * 100, 2)
                macro_data[key] = {"price": latest_c, "diff": diff_pct, "label": info["label"]}
            else:
                macro_data[key] = {"price": 0.0, "diff": 0.0, "label": info["label"]}
        except Exception:
            macro_data[key] = {"price": 0.0, "diff": 0.0, "label": info["label"]}
    return macro_data

@st.cache_data(ttl=1800)
def fetch_and_analyze(code, name=None, theme=None, genre="個別検索", macro=None):
    try:
        ticker_obj = yf.Ticker(code)
        df = ticker_obj.history(period="1y")
        if df.empty or len(df) < 35:
            return None

        # 登録リストにない任意銘柄の場合、銘柄名や業種テーマを自動取得
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

        # --- 基本指標の計算 ---
        df['Prev_Close'] = df['Close'].shift(1)
        df['Day_Return'] = (df['Close'] - df['Prev_Close']) / df['Prev_Close'] * 100
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['Vol_MA20'] = df['Volume'].rolling(20).mean().replace(0, np.nan)
        df['Vol_Ratio'] = (df['Volume'] / df['Vol_MA20']).fillna(1.0)

        # --- アルゴリズム1: RSI (14日・Wilder法 / TradingView・証券会社準拠) ---
        delta = df['Close'].diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss.replace(0, np.nan)
        df['RSI'] = (100 - (100 / (1 + rs))).fillna(50.0)

        # --- アルゴリズム2: ボリンジャーバンド (20日) ---
        df['BB_Std'] = df['Close'].rolling(20).std().replace(0, np.nan)
        df['BB_Sigma'] = ((df['Close'] - df['MA20']) / df['BB_Std']).fillna(0.0)

        # --- アルゴリズム3: ローソク足の実体・陽線強度 ---
        high_low = (df['High'] - df['Low']).replace(0, np.nan)
        df['Close_Pos'] = ((df['Close'] - df['Low']) / high_low).fillna(0.5)

        # 翌朝の始値とギャップ判定
        df['Next_Open'] = df['Open'].shift(-1)
        df['Gap_Pct'] = (df['Next_Open'] - df['Close']) / df['Close'] * 100
        df['Morning_Up'] = df['Next_Open'] > df['Close']

        # --- シグナル条件の定義 ---
        cond_breakout = (df['Close'] > df['MA5']) & (df['Vol_Ratio'] >= 1.2) & (df['Day_Return'] > 0)
        cond_rebound = (df['RSI'] < 40) & (df['Day_Return'] <= -1.5)
        cond_strong_close = (df['Close'] > df['MA20']) & (df['Close_Pos'] >= 0.7) & (df['Day_Return'] > 0)
        cond_uptrend = (df['Close'] > df['MA5']) & (df['Day_Return'] > 0)
        cond_up = df['Day_Return'] > 0
        cond_down = df['Day_Return'] <= 0

        latest = df.iloc[-1]
        history = df.iloc[:-1].dropna(subset=['Next_Open', 'MA20', 'RSI'])

        if len(history) == 0:
            return None

        # 最新日のシグナル判定と類似局面の抽出
        if cond_breakout.iloc[-1]:
            signal = "🔥 出来高伴うブレイクアウト"
            sub = history[cond_breakout.reindex(history.index, fill_value=False)]
        elif cond_rebound.iloc[-1]:
            signal = "⚡ 売られすぎ水準からの反発狙い"
            sub = history[cond_rebound.reindex(history.index, fill_value=False)]
        elif cond_strong_close.iloc[-1]:
            signal = "💪 高値引け・強気モメンタム"
            sub = history[cond_strong_close.reindex(history.index, fill_value=False)]
        elif cond_uptrend.iloc[-1]:
            signal = "📈 5日線キープ＋陽線"
            sub = history[cond_uptrend.reindex(history.index, fill_value=False)]
        elif cond_up.iloc[-1]:
            signal = "☀️ 前日比プラス引け"
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

        # --- アルゴリズム4: 米国市場・為替フィルターによる補正計算 ---
        macro_score = 0
        macro_reasons = []
        if macro:
            sp_diff = macro["sp500"]["diff"]
            sox_diff = macro["sox"]["diff"]
            fx_diff = macro["usdjpy"]["diff"]

            if genre in ["半導体", "AI", "AI電力・インフラ"]:
                if sox_diff >= 1.0:
                    macro_score += 6
                    macro_reasons.append(f"米SOX指数が<b>+{sox_diff}%</b>と強く上昇しており、翌朝の寄り付きに強い追い風です。")
                elif sox_diff > 0:
                    macro_score += 3
                elif sox_diff <= -1.5:
                    macro_score -= 5
                    macro_reasons.append(f"米SOX指数が<b>{sox_diff}%</b>と下落しており、朝方は売り先行への警戒が必要です。")

            if sp_diff >= 0.5:
                macro_score += 3
            elif sp_diff <= -0.8:
                macro_score -= 3

            if ".T" in code:
                if fx_diff >= 0.3:
                    macro_score += 2
                    macro_reasons.append(f"ドル円が<b>+{fx_diff}%</b>と円安推移しており、先物・主力株の買い安心感に繋がっています。")
                elif fx_diff <= -0.5:
                    macro_score -= 2

        # --- アルゴリズム5: 株価が上がりそうな要因の自動テキスト生成 ---
        reasons = []
        if macro_reasons:
            reasons.extend(macro_reasons)

        if latest['Vol_Ratio'] >= 1.5:
            reasons.append(f"出来高が20日平均の<b>{latest['Vol_Ratio']:.1f}倍</b>に急増しており、大口・機関投資家の資金流入が強く示唆されます。")
        elif latest['Vol_Ratio'] >= 1.1:
            reasons.append(f"出来高が平均比<b>{latest['Vol_Ratio']:.1f}倍</b>と堅調に増加し、市場の注目度が高まっています。")

        if latest['Close'] > latest['MA5'] and latest['Close'] > latest['MA20']:
            if latest['Close_Pos'] >= 0.75:
                reasons.append("5日・20日移動平均線を共に上回り、かつ<b>高値圏で引ける（買い残しが強い）</b>ため翌朝の買い気配に繋がりやすい形です。")
            else:
                reasons.append("短期（5日）・中期（20日）の移動平均線の上に位置する順張りトレンドが継続しています。")
        elif latest['Close'] > latest['MA5']:
            reasons.append("5日移動平均線を回復しており、目先の調整から短期上昇トレンドへの転換点にあります。")

        if latest['RSI'] <= 35:
            reasons.append(f"Wilder式RSIが<b>{latest['RSI']:.0f}</b>と売られすぎ水準にあり、空売りの買い戻しや自律反発が入りやすい水準です。")
        elif 50 <= latest['RSI'] <= 70:
            reasons.append(f"Wilder式RSIは<b>{latest['RSI']:.0f}</b>で過熱しすぎない理想的な強気ゾーン（モメンタム継続域）にあります。")
        elif latest['RSI'] > 70:
            reasons.append(f"Wilder式RSIは<b>{latest['RSI']:.0f}</b>と強い買いトレンドですが、短期的な高値警戒感もあるため寄り付き後の利確売りには注意が必要です。")

        if not reasons:
            reasons.append(f"過去の同パターンでは{total}回中{wins}回ギャップアップしており、下値の堅さが意識されやすい局面です。")

        # --- アルゴリズム6: AI総合期待スコア (0〜99点) ---
        base_score = min(max(prob * 0.72, 10), 58)
        gap_score = min(max((avg_gap + 0.5) * 11, 0), 18)
        tech_score = 0
        if latest['Vol_Ratio'] >= 1.2: tech_score += 6
        if latest['Close_Pos'] >= 0.7: tech_score += 5
        if 45 <= latest['RSI'] <= 68 or latest['RSI'] <= 32: tech_score += 7

        ai_score = int(min(max(round(base_score + gap_score + tech_score + macro_score), 15), 99))

        clean_code = code.replace(".T", "")
        price = f"{latest['Close']:,.0f}円" if ".T" in code else f"${latest['Close']:,.2f}"

        return {
            "code": clean_code, "name": name, "price": price,
            "diff": round(float(latest['Day_Return']), 2), "signal": signal,
            "prob": prob, "count": f"{wins}/{total}回", "gap": avg_gap,
            "rsi": round(float(latest['RSI']), 1),
            "vol_ratio": round(float(latest['Vol_Ratio']), 2),
            "bb_sigma": round(float(latest['BB_Sigma']), 2),
            "ai_score": ai_score,
            "macro_score": macro_score,
            "theme": theme,
            "reasons": " / ".join(reasons)
        }
    except Exception:
        return None

def render_stock_card(r, is_custom=False):
    """銘柄カードのHTML描画用共通関数"""
    diff_color = "#dc2626" if r["diff"] > 0 else "#2563eb"
    diff_sign = "+" if r["diff"] > 0 else ""
    gap_sign = "+" if r["gap"] > 0 else ""
    sigma_sign = "+" if r["bb_sigma"] > 0 else ""
    card_class = "search-result-card" if is_custom else "stock-card"

    m_score = r["macro_score"]
    if m_score > 0:
        macro_badge_html = f'<span class="macro-badge">🌐 地合い補正 +{m_score}点</span>'
    elif m_score < 0:
        macro_badge_html = f'<span class="macro-badge" style="background:#fef2f2; color:#b91c1c; border-color:#fecaca;">🌐 地合い補正 {m_score}点</span>'
    else:
        macro_badge_html = '<span class="macro-badge" style="background:#f1f5f9; color:#64748b; border-color:#cbd5e1;">🌐 地合い中立 ±0</span>'

    st.markdown(f"""
    <div class="{card_class}">
        <div>
            <span class="score-badge">🤖 期待度スコア: {r['ai_score']} / 100点</span>
            {macro_badge_html}
        </div>
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
        <div class="metrics-row">
            <span>📊 <b>RSI(14):</b> {r['rsi']}</span>
            <span>｜</span>
            <span>🔊 <b>出来高倍率:</b> {r['vol_ratio']}倍</span>
            <span>｜</span>
            <span>📐 <b>BB位置:</b> {sigma_sign}{r['bb_sigma']}σ</span>
        </div>
        <div class="factor-box">
            <div class="factor-title">💡 上昇期待の背景・テクニカル要因</div>
            <div style="margin-bottom:4px;"><b>【テーマ性・業種】</b> {r['theme']}</div>
            <div><b>【直近の需給・地合い分析】</b> {r['reasons']}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

if st.button("🔄 最新データに更新"):
    st.cache_data.clear()

# --- 画面上部: 米国市場・為替ダッシュボード表示 ---
macro_info = fetch_macro_market()

def fmt_macro(item, is_fx=False):
    d = item["diff"]
    color = "#4ade80" if d > 0 else ("#f87171" if d < 0 else "#cbd5e1")
    sign = "+" if d > 0 else ""
    val_str = f"{item['price']:,.1f}円" if is_fx else f"{item['price']:,.0f}"
    return f"""
    <div class="market-item">
        <div style="font-size:11px; color:#cbd5e1;">{item['label']}</div>
        <div style="font-size:13px; font-weight:bold; margin-top:2px;">{val_str}</div>
        <div style="font-size:12px; font-weight:bold; color:{color};">{sign}{d}%</div>
    </div>
    """

st.markdown(f"""
<div class="market-banner">
    <div class="market-title">🌐 米国市場・為替フィルター（翌朝の寄付き地合い補正に自動反映）</div>
    <div class="market-grid">
        {fmt_macro(macro_info['sp500'])}
        {fmt_macro(macro_info['sox'])}
        {fmt_macro(macro_info['usdjpy'], is_fx=True)}
    </div>
</div>
""", unsafe_allow_html=True)

# --- 任意の証券コード診断セクション ---
with st.container():
    col1, col2 = st.columns([3, 1])
    with col1:
        custom_input = st.text_input(
            "🔍 任意の銘柄コードを診断（日本株は4桁コード、米国株はティッカー）",
            placeholder="例: 7203, 8306, NVDA, AAPL"
        )
    with col2:
        st.write("")  # ラベル分の高さ調整
        search_clicked = st.button("診断する", use_container_width=True)

if custom_input or search_clicked:
    norm_code = normalize_ticker(custom_input)
    if norm_code:
        with st.spinner(f"「{norm_code}」の過去1年データと需給アルゴリズムを解析中..."):
            custom_res = fetch_and_analyze(norm_code, macro=macro_info)
        if custom_res:
            st.markdown("##### 🎯 個別銘柄のリアルタイム診断結果")
            render_stock_card(custom_res, is_custom=True)
        else:
            st.error(f"証券コード「{custom_input}」のデータが見つかりませんでした。東証銘柄は4桁の半角数字（例: 7203）、米国株はティッカー（例: NVDA）を入力してください。")

# --- タブ別銘柄表示 ---
tabs = st.tabs(list(STOCK_LIST.keys()))

for tab, (genre, stocks) in zip(tabs, STOCK_LIST.items()):
    with tab:
        results = []
        with st.spinner(f"{genre}銘柄のアルゴリズム解析中..."):
            for s in stocks:
                res = fetch_and_analyze(s["code"], s["name"], s["theme"], genre, macro_info)
                if res:
                    results.append(res)

        if not results:
            st.warning("データの取得に失敗しました。時間をおいて再試行してください。")
            continue

        # AI総合スコアが高い順（同点なら上昇確率順）にソート
        results.sort(key=lambda x: (x["ai_score"], x["prob"]), reverse=True)

        for r in results:
            render_stock_card(r)
