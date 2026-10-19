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
        {"code": "6146.T", "name": "ディスコ", "theme": "HBM（広帯域メモリ）向け切断・研削装置で高収益"},
        {"code": "6723.T", "name": "ルネサス", "theme": "車載・産業・データセンター向けパワー半導体を展開"},
        {"code": "7735.T", "name": "スクリーンHD", "theme": "半導体洗浄装置で世界トップクラス。直近の業績上方修正期待"},
        {"code": "4063.T", "name": "信越化学工業", "theme": "半導体シリコンウエハー世界首位。素材セクターの主力"},
        {"code": "6526.T", "name": "ソシオネクスト", "theme": "先端SoC開発。グロース市場のハイテク看板"},
        {"code": "3436.T", "name": "SUMCO", "theme": "シリコンウエハー大手。需給動向に敏感に反応"},
        {"code": "6976.T", "name": "太陽誘電", "theme": "積層セラミックコンデンサ。電子部品の指標"},
        {"code": "6758.T", "name": "ソニーグループ", "theme": "イメージセンサー世界首位。スマホ・車載向けカメラ需要"},
        {"code": "6981.T", "name": "村田製作所", "theme": "通信・スマホ向け電子部品の世界的リーダー"},
        {"code": "6841.T", "name": "横河電機", "theme": "産業用制御・計測機器。ファクトリーオートメーション関連"},
        {"code": "6701.T", "name": "NEC", "theme": "海底ケーブル・防衛・AIを活用したITインフラ構築"},
        {"code": "6702.T", "name": "富士通", "theme": "ITサービス大手。スーパーコンピュータ・量子コンピューティング"},
        {"code": "6503.T", "name": "三菱電機", "theme": "FA機器・重電・宇宙防衛システム・パワー半導体"},
        {"code": "6963.T", "name": "ローム", "theme": "車載・産業機器向けパワー半導体主力"},
        {"code": "6590.T", "name": "芝浦メカトロニクス", "theme": "半導体後工程・フラットパネルディスプレイ製造装置"},
        {"code": "6315.T", "name": "TOWA", "theme": "半導体樹脂封止装置で世界トップシェア。HBM関連"},
        {"code": "5334.T", "name": "日本特殊陶業", "theme": "半導体パッケージ基板・セラミック部品"},
        {"code": "NVDA", "name": "エヌビディア", "theme": "生成AI向けGPUの圧倒的覇者。世界の半導体相場の羅針盤"},
        {"code": "AMD", "name": "AMD", "theme": "AIアクセラレータおよびCPUでエヌビディアを追撃"},
        {"code": "INTC", "name": "インテル", "theme": "米国ファウンドリ再生・政府支援の半導体老舗"},
        {"code": "MU", "name": "マイクロン", "theme": "HBM・DRAM大手。メモリー市況のバロメーター"},
        {"code": "TSM", "name": "台湾セミコンダクター", "theme": "世界最大の半導体ファウンドリ受託製造"},
        {"code": "QCOM", "name": "クアルコム", "theme": "スマホ・AIチップ向け通信半導体の世界的リーダー"},
        {"code": "AVGO", "name": "ブロードコム", "theme": "AIネットワーク・カスタムシリコンの巨塔"},
        {"code": "AMAT", "name": "アプライドマテリアルズ", "theme": "世界最大の半導体製造装置メーカー"},
        {"code": "LRCX", "name": "ラムリサーチ", "theme": "エッチング・成膜装置で圧倒的な技術力"}
    ],
    "AI": [
        {"code": "9984.T", "name": "ソフトバンクG", "theme": "傘下ArmやAI投資群の評価益期待。先物主導で寄り付きが動きやすい"},
        {"code": "3778.T", "name": "さくらネット", "theme": "政府クラウド・生成AI向けGPUクラウドの国策銘柄"},
        {"code": "3993.T", "name": "PKSHA", "theme": "自然言語処理・AIアルゴリズム開発"},
        {"code": "4180.T", "name": "Appier", "theme": "AIマーケティングSaaS。グロース市場の資金流入先"},
        {"code": "4307.T", "name": "野村総合研究所", "theme": "企業のAI導入・DXシステム刷新およびデータセンター運営"},
        {"code": "4478.T", "name": "フリー", "theme": "クラウド会計ソフト。SaaSセクターのモメンタム連動"},
        {"code": "4483.T", "name": "JMDC", "theme": "医療ビッグデータ・ヘルスケアAIプラットフォーム"},
        {"code": "5032.T", "name": "ANYCOLOR", "theme": "VTuberエンタメテック。グロース市場の売買代金上位"},
        {"code": "5243.T", "name": "ノート", "theme": "メディアプラットフォーム・クリエイターエコノミー関連"},
        {"code": "7342.T", "name": "ウェルスナビ", "theme": "ロボアドバイザーによる資産運用プラットフォーム"},
        {"code": "6182.T", "name": "メタリアル", "theme": "AI自動翻訳・生成AI活用サービス"},
        {"code": "3962.T", "name": "チェンジHD", "theme": "デジタル地方創生・行政DX推進コンサルティング"},
        {"code": "4443.T", "name": "SANS", "theme": "名刺管理・営業DXプラットフォーム"},
        {"code": "4385.T", "name": "メルカリ", "theme": "国内最大のC2Cマーケットプレイス。AIレコメンド技術"},
        {"code": "4689.T", "name": "LINEヤフー", "theme": "国内最大級のポータル・AI検索・デジタル広告基盤"},
        {"code": "4755.T", "name": "楽天グループ", "theme": "モバイル通信・Fintech・AIマーケティングの融合"},
        {"code": "4475.T", "name": "HENNGE", "theme": "クラウドセキュリティ・SaaS認証基盤"},
        {"code": "5031.T", "name": "AndDoホールディングス", "theme": "不動産テック・AI活用プラットフォーム"},
        {"code": "6556.T", "name": "ウェルビー", "theme": "障害福祉・ヘルスケアITプラットフォーム"},
        {"code": "MSFT", "name": "マイクロソフト", "theme": "OpenAI最大株主。クラウドとCopilotの収益化"},
        {"code": "GOOGL", "name": "アルファベット", "theme": "独自生成AIと検索・クラウドプラットフォーム"},
        {"code": "META", "name": "メタ", "theme": "オープンソースAIと広告最適化AI"},
        {"code": "PLTR", "name": "パランティア", "theme": "政府・防衛・企業向けAIプラットフォームの大本命"},
        {"code": "CRM", "name": "セールスフォース", "theme": "CRMプラットフォームとAIの統合"},
        {"code": "NOW", "name": "サービスナウ", "theme": "企業向けワークフロー自動化AIプラットフォーム"}
    ],
    "宇宙": [
        {"code": "5595.T", "name": "QPS研究所", "theme": "小型SAR衛星コンステレーション。防衛・安全保障テーマ"},
        {"code": "9348.T", "name": "ispace", "theme": "月面開発・輸送プログラム。イベントドリブンで出来高急増"},
        {"code": "186A.T", "name": "アストロスケール", "theme": "スペースデブリ除去の世界的リーダー"},
        {"code": "9412.T", "name": "スカパーJSAT", "theme": "アジア最大の衛星通信。防衛省向け宇宙監視"},
        {"code": "7011.T", "name": "三菱重工業", "theme": "H3ロケット打ち上げ及び防衛予算拡大の国策中核銘柄"},
        {"code": "7012.T", "name": "川崎重工業", "theme": "防衛装備品・航空機エンジン・無人機システム"},
        {"code": "7013.T", "name": "IHI", "theme": "航空機用ジェットエンジン・防衛省向けミサイル"},
        {"code": "6201.T", "name": "豊田自動織機", "theme": "トヨタグループのロケット・自動車用電動化技術"},
        {"code": "6502.T", "name": "東芝", "theme": "社会インフラ・重電・宇宙防衛関連の電子システム"},
        {"code": "4272.T", "name": "日本化薬", "theme": "火薬類製造技術をベースにした防衛宇宙用ロケット推進薬"},
        {"code": "6902.T", "name": "デンソー", "theme": "車載半導体・自動運転および航空宇宙向けセンサー"},
        {"code": "7267.T", "name": "ホンダ", "theme": "小型ジェット機技術を応用した次世代宇宙ロケット事業"},
        {"code": "5631.T", "name": "日本製鋼所", "theme": "防衛用艦砲・火砲および原子炉容器の世界的シェア"},
        {"code": "6268.T", "name": "ナブテスコ", "theme": "航空機用フライトコントロールシステム・精密減速機"},
        {"code": "5938.T", "name": "LIXIL", "theme": "宇宙関連の高断熱・先端素材への応用技術"},
        {"code": "3861.T", "name": "王子HD", "theme": "宇宙空間での耐放射線素材・セルロースナノファイバー"},
        {"code": "6701.T", "name": "NEC", "theme": "宇宙ステーション用通信機器・観測衛星システム"},
        {"code": "RKLB", "name": "ロケット・ラボ", "theme": "小型ロケット打ち上げの米宇宙ベンチャー筆頭"},
        {"code": "ASTS", "name": "ASTスペースモバイル", "theme": "宇宙からの直接スマホ通信網構築企業"},
        {"code": "SPCE", "name": "ヴァージン・ギャラクティック", "theme": "有人宇宙飛行・宇宙旅行プログラム"},
        {"code": "LMT", "name": "ロッキード・マーティン", "theme": "世界最大の防衛・宇宙航空コントラクター"},
        {"code": "NOC", "name": "ノースロップ・グラマン", "theme": "軍用機・ミサイル・宇宙望遠鏡開発の主力"},
        {"code": "BA", "name": "ボーイング", "theme": "民間航空機および宇宙船開発"}
    ],
    "AI電力・イン
