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

st.title("翌朝株価 クオンツ＆AI解析 Pro")
st.caption("弱肉強食ダイナミック選抜（リアルタイム期待値順に自動入替） × 世界情勢マクロ連動")

# --- 各ジャンルの候補プール ---
STOCK_POOL = {
    "半導体": [
        {"code": "8035.T", "name": "東京エレクトロン", "theme": "前工程装置の国内筆頭。海外勢の指数買いが入りやすい"},
        {"code": "6857.T", "name": "アドバンテスト", "theme": "AI半導体向けテスタで高シェア。米SOX指数と連動性大"},
        {"code": "6920.T", "name": "レーザーテック", "theme": "EUVマスク欠陥検査装置。ボラティリティが高く短期資金が集中"},
        {"code": "6146.T", "name": "ディスコ", "theme": "HBM向け切断・研削装置で高収益"},
        {"code": "6723.T", "name": "ルネサス", "theme": "車載・産業・データセンター向けパワー半導体を展開"},
        {"code": "7735.T", "name": "スクリーンHD", "theme": "半導体洗浄装置で世界トップクラス"},
        {"code": "4063.T", "name": "信越化学工業", "theme": "半導体シリコンウエハー世界首位"},
        {"code": "6526.T", "name": "ソシオネクスト", "theme": "先端SoC開発。グロース市場のハイテク看板"},
        {"code": "3436.T", "name": "SUMCO", "theme": "シリコンウエハー大手。需給動向に敏感に反応"},
        {"code": "6976.T", "name": "太陽誘電", "theme": "積層セラミックコンデンサ。電子部品の指標"},
        {"code": "6758.T", "name": "ソニーグループ", "theme": "イメージセンサー世界首位"},
        {"code": "6981.T", "name": "村田製作所", "theme": "通信・スマホ向け電子部品の世界的リーダー"},
        {"code": "6841.T", "name": "横河電機", "theme": "産業用制御・計測機器"},
        {"code": "6701.T", "name": "NEC", "theme": "海底ケーブル・防衛・AIを活用したITインフラ構築"},
        {"code": "6702.T", "name": "富士通", "theme": "ITサービス大手。量子コンピューティング関連"},
        {"code": "6503.T", "name": "三菱電機", "theme": "FA機器・重電・宇宙防衛システム・パワー半導体"},
        {"code": "6963.T", "name": "ローム", "theme": "車載・産業機器向けパワー半導体主力"},
        {"code": "6590.T", "name": "芝浦メカトロニクス", "theme": "半導体後工程製造装置"},
        {"code": "6315.T", "name": "TOWA", "theme": "半導体樹脂封止装置で世界トップシェア"},
        {"code": "5334.T", "name": "日本特殊陶業", "theme": "半導体パッケージ基板・セラミック部品"},
        {"code": "NVDA", "name": "エヌビディア", "theme": "生成AI向けGPUの圧倒的覇者"},
        {"code": "AMD", "name": "AMD", "theme": "AIアクセラレータおよびCPU"},
        {"code": "INTC", "name": "インテル", "theme": "米国ファウンドリ再生・政府支援"},
        {"code": "MU", "name": "マイクロン", "theme": "HBM・DRAM大手"},
        {"code": "TSM", "name": "台湾セミコンダクター", "theme": "世界最大の半導体ファウンドリ受託製造"},
        {"code": "QCOM", "name": "クアルコム", "theme": "スマホ・AIチップ向け通信半導体"},
        {"code": "AVGO", "name": "ブロードコム", "theme": "AIネットワーク・カスタムシリコン"},
        {"code": "AMAT", "name": "アプライドマテリアルズ", "theme": "世界最大の半導体製造装置メーカー"},
        {"code": "LRCX", "name": "ラムリサーチ", "theme": "エッチング・成膜装置の技術力"}
    ],
    "AI": [
        {"code": "9984.T", "name": "ソフトバンクG", "theme": "傘下ArmやAI投資群の評価益期待"},
        {"code": "3778.T", "name": "さくらネット", "theme": "政府クラウド・生成AI向けGPUクラウド"},
        {"code": "3993.T", "name": "PKSHA", "theme": "自然言語処理・AIアルゴリズム開発"},
        {"code": "4180.T", "name": "Appier", "theme": "AIマーケティングSaaS"},
        {"code": "4307.T", "name": "野村総合研究所", "theme": "企業のAI導入・DXシステム刷新"},
        {"code": "4478.T", "name": "フリー", "theme": "クラウド会計ソフト・SaaSセクター"},
        {"code": "4483.T", "name": "JMDC", "theme": "医療ビッグデータ・ヘルスケアAI"},
        {"code": "5032.T", "name": "ANYCOLOR", "theme": "VTuberエンタメテック"},
        {"code": "5243.T", "name": "ノート", "theme": "メディアプラットフォーム"},
        {"code": "7342.T", "name": "ウェルスナビ", "theme": "ロボアドバイザー資産運用"},
        {"code": "6182.T", "name": "メタリアル", "theme": "AI自動翻訳・生成AIサービス"},
        {"code": "3962.T", "name": "チェンジHD", "theme": "デジタル地方創生・行政DX"},
        {"code": "4443.T", "name": "SANS", "theme": "名刺管理・営業DXプラットフォーム"},
        {"code": "4385.T", "name": "メルカリ", "theme": "C2Cマーケットプレイス・AIレコメンド"},
        {"code": "4689.T", "name": "LINEヤフー", "theme": "ポータル・AI検索・デジタル広告"},
        {"code": "4755.T", "name": "楽天グループ", "theme": "通信・Fintech・AIマーケティング"},
        {"code": "4475.T", "name": "HENNGE", "theme": "クラウドセキュリティ・SaaS認証"},
        {"code": "5031.T", "name": "AndDoホールディングス", "theme": "不動産テック・AI活用"},
        {"code": "6556.T", "name": "ウェルビー", "theme": "障害福祉・ヘルスケアIT"},
        {"code": "MSFT", "name": "マイクロソフト", "theme": "OpenAI最大株主・Azure"},
        {"code": "GOOGL", "name": "アルファベット", "theme": "独自生成AI Gemini・検索"},
        {"code": "META", "name": "メタ", "theme": "オープンソースAI Llama・広告AI"},
        {"code": "PLTR", "name": "パランティア", "theme": "政府・防衛向けAIプラットフォーム"},
        {"code": "CRM", "name": "セールスフォース", "theme": "CRMとEinstein AIの統合"},
        {"code": "NOW", "name": "サービスナウ", "theme": "ワークフロー自動化AI"}
    ],
    "宇宙": [
        {"code": "5595.T", "name": "QPS研究所", "theme": "小型SAR衛星コンステレーション"},
        {"code": "9348.T", "name": "ispace", "theme": "月面開発・輸送プログラム"},
        {"code": "186A.T", "name": "アストロスケール", "theme": "スペースデブリ除去の世界的リーダー"},
        {"code": "9412.T", "name": "スカパーJSAT", "theme": "衛星通信・防衛省向け宇宙監視"},
        {"code": "7011.T", "name": "三菱重工業", "theme": "H3ロケット・防衛予算拡大の中核"},
        {"code": "7012.T", "name": "川崎重工業", "theme": "防衛装備品・航空機エンジン"},
        {"code": "7013.T", "name": "IHI", "theme": "航空機エンジン・宇宙ロケット"},
        {"code": "6201.T", "name": "豊田自動織機", "theme": "ロケット・自動車電動化技術"},
        {"code": "6502.T", "name": "東芝", "theme": "社会インフラ・宇宙防衛システム"},
        {"code": "4272.T", "name": "日本化薬", "theme": "防衛・宇宙用ロケット推進薬"},
        {"code": "6902.T", "name": "デンソー", "theme": "航空宇宙向け高精度センサー"},
        {"code": "7267.T", "name": "ホンダ", "theme": "次世代宇宙ロケット事業"},
        {"code": "5631.T", "name": "日本製鋼所", "theme": "防衛用艦砲・火砲の世界的シェア"},
        {"code": "6268.T", "name": "ナブテスコ", "theme": "航空機用コントロールシステム"},
        {"code": "5938.T", "name": "LIXIL", "theme": "宇宙関連の先端素材応用技術"},
        {"code": "3861.T", "name": "王子HD", "theme": "耐放射線素材・セルロースナノファイバー"},
        {"code": "6701.T", "name": "NEC", "theme": "宇宙ステーション用通信機器"},
        {"code": "RKLB", "name": "ロケット・ラボ", "theme": "小型ロケット打ち上げの米ベンチャー"},
        {"code": "ASTS", "name": "ASTスペースモバイル", "theme": "宇宙からの直接スマホ通信網"},
        {"code": "SPCE", "name": "ヴァージンギャラクティック", "theme": "有人宇宙飛行・宇宙旅行"},
        {"code": "LMT", "name": "ロッキードマーティン", "theme": "防衛・宇宙航空コントラクター"},
        {"code": "NOC", "name": "ノースロップグラマン", "theme": "軍用機・宇宙望遠鏡開発"},
        {"code": "BA", "name": "ボーイング", "theme": "民間航空機および宇宙船開発"}
    ],
    "AI電力・インフラ": [
        {"code": "9509.T", "name": "北海道電力", "theme": "ラピダス・AIデータセンター誘致"},
        {"code": "9508.T", "name": "九州電力", "theme": "TSMC工場等による産業用電力拡大"},
        {"code": "5803.T", "name": "フジクラ", "theme": "AIデータセンター向け光ファイバー"},
        {"code": "6501.T", "name": "日立製作所", "theme": "送配電網設備更新と変電システム"},
        {"code": "6622.T", "name": "ダイヘン", "theme": "変圧器・受変電設備"},
        {"code": "5801.T", "name": "古河電気工業", "theme": "超高圧送電線・高速通信ケーブル"},
        {"code": "5802.T", "name": "住友電気工業", "theme": "電線業界最大手・電力網インフラ"},
        {"code": "6504.T", "name": "富士電機", "theme": "パワー半導体・無停電電源装置"},
        {"code": "9501.T", "name": "東京電力HD", "theme": "首都圏の巨大電力需要・データセンター"},
        {"code": "9502.T", "name": "中部電力", "theme": "中京圏の安定電源確保"},
        {"code": "9503.T", "name": "関西電力", "theme": "関西圏の電力インフラと次世代エネルギー"},
        {"code": "9506.T", "name": "東北電力", "theme": "グリーンデータセンター集積地帯"},
        {"code": "1963.T", "name": "日揮HD", "theme": "プラントエンジニアリング・水素"},
        {"code": "1951.T", "name": "協和エクシオ", "theme": "通信インフラ・データセンター構築"},
        {"code": "1942.T", "name": "関電工", "theme": "電気設備工事・データセンター配線"},
        {"code": "1973.T", "name": "NECネッツエスアイ", "theme": "ネットワーク構築支援"},
        {"code": "9504.T", "name": "中国電力", "theme": "中国地方の電力供給インフラ"},
        {"code": "9505.T", "name": "北陸電力", "theme": "北陸地域の電力網・再エネ接続"},
        {"code": "9507.T", "name": "四国電力", "theme": "四国地域の電力網強化"},
        {"code": "VST", "name": "ビストラ", "theme": "原子力・電力供給の米有力企業"},
        {"code": "CEG", "name": "コンステレーションエナジー", "theme": "米最大の原子力発電企業"},
        {"code": "NEE", "name": "ネクステラエナジー", "theme": "クリーンエネルギー発電"},
        {"code": "GEV", "name": "GEヴェルノバ", "theme": "ガスタービン・送電グリッド"},
        {"code": "DUK", "name": "デュークエナジー", "theme": "米国最大級のユーティリティ"}
    ],
    "イーロン": [
        {"code": "TSLA", "name": "テスラ", "theme": "自動運転FSD・ロボタクシー"},
        {"code": "6752.T", "name": "パナソニックHD", "theme": "北米EV向け車載電池・蓄電"},
        {"code": "5713.T", "name": "住友金属鉱山", "theme": "EV電池向けニッケル正極材"},
        {"code": "9433.T", "name": "KDDI", "theme": "Starlink衛星スマホ通信"},
        {"code": "7270.T", "name": "SUBARU", "theme": "北米EV展開・テスラ充電規格"},
        {"code": "7203.T", "name": "トヨタ自動車", "theme": "北米EV・全固体電池動向"},
        {"code": "7269.T", "name": "スズキ", "theme": "インド市場首位・小型車"},
        {"code": "6902.T", "name": "デンソー", "theme": "EV用サーマルマネジメント"},
        {"code": "7282.T", "name": "豊田合成", "theme": "自動車用ゴム・樹脂・軽量化"},
        {"code": "5108.T", "name": "ブリヂストン", "theme": "EV向け高負荷対応タイヤ"},
        {"code": "5332.T", "name": "TOTO", "theme": "米国住宅市場向け建材"},
        {"code": "6594.T", "name": "ニデック", "theme": "EV用トラクションモーター"},
        {"code": "4208.T", "name": "UBE", "theme": "EVバッテリー用セパレーター"},
        {"code": "3407.T", "name": "旭化成", "theme": "リチウムイオン電池用セパレーター"},
        {"code": "4005.T", "name": "住友化学", "theme": "ペロブスカイト太陽電池素材"},
        {"code": "4188.T", "name": "三菱ケミカルG", "theme": "炭素繊維複合材料・電池部材"},
        {"code": "7201.T", "name": "日産自動車", "theme": "EVパイオニア戦略"},
        {"code": "AAPL", "name": "アップル", "theme": "Apple Intelligence展開"},
        {"code": "AMZN", "name": "アマゾン", "theme": "AWS・宇宙プロジェクト"},
        {"code": "NFLX", "name": "ネットフリックス", "theme": "ストリーミング指標"},
        {"code": "COIN", "name": "コインベース", "theme": "暗号資産フィンテック"},
        {"code": "UBER", "name": "ウーバー", "theme": "ライドシェア・自動運転提携"}
    ],
    "テンバガー小型株": [
        {"code": "5595.T", "name": "QPS研究所", "theme": "小型SAR衛星による時価総額急拡大期待"},
        {"code": "186A.T", "name": "アストロスケール", "theme": "宇宙ゴミ除去のニッチトップ"},
        {"code": "9348.T", "name": "ispace", "theme": "民間月面輸送ベンチャー"},
        {"code": "5243.T", "name": "ノート", "theme": "クリエイターエコノミー関連"},
        {"code": "5032.T", "name": "ANYCOLOR", "theme": "VTuberグローバル展開"},
        {"code": "4180.T", "name": "Appier", "theme": "AIマーケティングで海外売上急増"},
        {"code": "3778.T", "name": "さくらインターネット", "theme": "GPUクラウド本格稼働"},
        {"code": "6526.T", "name": "ソシオネクスト", "theme": "先端SoC設計受託の爆発力"},
        {"code": "4478.T", "name": "フリー", "theme": "中小企業向けSaaSのシェア獲得"},
        {"code": "4483.T", "name": "JMDC", "theme": "医療ビッグデータプラットフォーム"},
        {"code": "7342.T", "name": "ウェルスナビ", "theme": "ロボアドバイザートップ"},
        {"code": "6182.T", "name": "メタリアル", "theme": "生成AI翻訳・メタバース高成長"},
        {"code": "4475.T", "name": "HENNGE", "theme": "クラウドセキュリティ認証"},
        {"code": "ACHR", "name": "アーチャーアビエーション", "theme": "空飛ぶクルマeVTOL実用化"},
        {"code": "JOBY", "name": "ジョビーアビエーション", "theme": "トヨタ出資の空飛ぶクルマ"},
        {"code": "PLTR", "name": "パランティア", "theme": "AIプラットフォーム需要で急成長"},
        {"code": "IONQ", "name": "アイオンQ", "theme": "商用量子コンピューター開発"},
        {"code": "SOUN", "name": "サウンドハウンドAI", "theme": "音声AI認識技術の注目株"},
        {"code": "BBAI", "name": "ビッグベア.ai", "theme": "防衛・政府向けAI予測"}
    ]
}

KNOWN_STOCKS = {}
for g, items in STOCK_POOL.items():
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

# --- マクロ市場データの取得関数 ---
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
                if df_m is not None and not df_m.empty:
                    df_m = df_m.dropna(subset=['Close'])
                    if len(df_m) >= 2:
                        latest_c = float(df_m['Close'].iloc[-1])
                        prev_c = float(df_m['Close'].iloc[-2])
                        if not np.isnan(latest_c) and not np.isnan(prev_c) and prev_c != 0:
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
        if df is None or df.empty or len(df) < 40:
            return None

        df = df.dropna(subset=['Close', 'Open', 'High', 'Low', 'Volume'])
        if len(df) < 40:
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
                        else:
                            theme = "カスタム指定銘柄（過去1年の日足・需給データに基づく統計解析）"
                except Exception:
                    name = name or code.replace(".T", "")
                    theme = theme or "カスタム指定銘柄（過去1年の日足・需給データに基づく統計解析）"

        df['Prev_Close'] = df['Close'].shift(1)
        df['Day_Return'] = (df['Close'] - df['Prev_Close']) / df['Prev_Close'] * 100
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['Vol_MA20'] = df['Volume'].
