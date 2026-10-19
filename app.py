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

# --- 各ジャンルの厳選候補プール ---
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
    "テンバガー小型株
