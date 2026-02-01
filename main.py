import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from supabase import create_client, Client
import datetime

# --- 1. Supabaseの初期設定 ---
# StreamlitのSecretsから情報を読み込みます
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_supabase()
except Exception as e:
    st.error(f"Supabaseへの接続に失敗しました。Secretsの設定を確認してください: {e}")

# --- 2. 最新の市場データを取得する関数 ---
@st.cache_data(ttl=3600)  # 1時間はネットから再取得せずキャッシュを使う
def get_market_info():
    tickers = {
        "日経平均": "^N225",
        "S&P 500": "^GSPC",
        "オルカン(ACWI)": "ACWI",
        "金(Gold)": "GC=F"
    }
    results = {}
    for name, symbol in tickers.items():
        try:
            ticker = yf.Ticker(symbol)
            # 最新の2日分を取得して前日比を計算
            hist = ticker.history(period="2d")
            if len(hist) >= 2:
                price = hist['Close'].iloc[-1]
                prev_price = hist['Close'].iloc[-2]
                change = price - prev_price
                results[name] = {"price": price, "change": change}
            else:
                results[name] = {"price": 0, "change": 0}
        except:
            results[name] = {"price": 0, "change": 0}
    return results

# --- 3. UIの構築 ---
st.set_page_config(page_title="新NISA シミュレーター Pro", layout="wide")

st.title("💰 新NISA 運用シミュレーター")
st.caption("Supabase連携 & リアルタイム市場データ表示")

# サイドバー：入力設定
st.sidebar.header("📊 シミュレーション設定")
user_name = st.sidebar.text_input("あなたの名前", value="ゲストユーザー")
monthly_investment = st.sidebar.number_input("月額積立額 (円)", min_value=1000, max_value=300000, value=50000, step=1000)
annual_rate = st.sidebar.slider("想定年率 (%)", min_value=0.1, max_value=15.0, value=5.0, step=0.1)
years = st.sidebar.slider("運用年数 (年)", min_value=1, max_value=50, value=20)

# --- 4. 計算ロジック ---
def calculate_investment(monthly, rate, duration):
    data = []
    total_principal = 0
    current_value = 0
    monthly_rate = rate / 100 / 12
    nisa_limit = 18000000 # 生涯投資枠
    
    for month in range(1, duration * 12 + 1):
        if total_principal + monthly <= nisa_limit:
            total_principal += monthly
            current_value += monthly
        current_value *= (1 + monthly_rate)
        
        if month % 12 == 0:
            data.append({
                "年": month // 12,
                "元本": total_principal,
                "運用益": current_value - total_principal,
                "合計資産": current_value
            })
    return pd.DataFrame(data)

df_result = calculate_investment(monthly_investment, annual_rate, years)
final_wealth = df_result.iloc[-1]["合計資産"]

# --- 5. メイン画面の表示 ---

# A. シミュレーション結果のグラフ
st.subheader("📈 将来の資産推移予測")
fig = px.area(df_result, x="年", y=["元本", "運用益"], 
              title=f"{years}年後の推定資産: {int(final_wealth):,} 円",
              labels={"value": "金額 (円)", "variable": "内訳"})
st.plotly_chart(fig, use_container_width=True)

# B. 市場価格の表示 (シミュレーションのすぐ下)
st.divider()
st.subheader("📋 投資の参考に：現在の市場価格")
st.markdown("直近の終値と前日比を表示しています（Yahoo Financeデータ）")

market_data = get_market_info()
m_cols = st.columns(len(market_data))
for i, (name, val) in enumerate(market_data.items()):
    with m_cols[i]:
        st.metric(label=name, value=f"{val['price']:,.1f}", delta=f"{val['change']:,.1f}")

# C. データの保存ボタン
st.divider()
if st.button("このシミュレーション結果を保存する"):
    new_data = {
        "user_name": user_name,
        "monthly_investment": monthly_investment,
        "annual_rate": annual_rate,
        "years": years,
        "final_wealth": int(final_wealth)
    }
    try:
        # Supabaseの 'nisa_logs' テーブルに挿入
        supabase.table("nisa_logs").insert(new_data).execute()
        st.success("データベースに保存しました！")
    except Exception as e:
        st.error(f"保存に失敗しました。テーブル名が正しいか確認してください: {e}")

# D. 過去の履歴表示
st.subheader("💾 最近の保存履歴")
try:
    res = supabase.table("nisa_logs").select("*").order("id", desc=True).limit(5).execute()
    if res.data:
        history_df = pd.DataFrame(res.data)
        st.dataframe(history_df[["user_name", "monthly_investment", "annual_rate", "final_wealth"]])
    else:
        st.info("まだ履歴がありません。最初の保存を行ってください。")
except:
    st.warning("履歴を取得できませんでした。Supabaseのテーブル作成が完了しているか確認してください。")