# 💰 新NISA 運用シミュレーター Pro++

本アプリケーションは、新NISA（少額投資非課税制度）における資産運用を、過去の実績データやマクロ経済指標に基づき詳細にシミュレーションするWebアプリです。

## 🚀 アプリ試用URL
[https://blank-app-1-nvrv9voytnfolp4abllcz9.streamlit.app/](https://blank-app-1-nvrv9voytnfolp4abllcz9.streamlit.app/)

## ✨ 主な機能
1.  **高精度シミュレーション**:
    * 生涯投資枠（1,800万円）の制限を自動考慮した資産推移の算出。
    * 元本と運用益を分離して視覚化した積立グラフ。
2.  **市場実績データの動的取得**:
    * `yfinance` APIを利用し、日経平均、S&P 500、全世界株式（ACWI）、金の最新価格を取得。
    * 過去30年の幾何平均（CAGR）に基づいた平均利回りの算出。
3.  **歴史的為替データの表示**:
    * 過去50年間のドル円為替レート推移チャート。
    * 1970年代からの長期トレンドを確認することで、現在の為替水準を客観的に評価可能。
4.  **データベース連携**:
    * Supabase（PostgreSQL）と連携。
    * シミュレーション結果をクラウドに保存し、最近の保存履歴を一覧表示。

## 🛠 技術スタック
* **Frontend**: Streamlit
* **Database**: Supabase
* **Data**: Yahoo Finance API (via yfinance)
* **Mathematical Analysis**: Pandas, NumPy (幾何平均を用いた利回り算出)。