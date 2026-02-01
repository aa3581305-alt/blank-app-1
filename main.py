import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from supabase import create_client, Client
import datetime
import numpy as np

# --- 1. Supabaseの初期設定 ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_supabase()
except Exception as e:
    st.error(f"Supabase接続エラー: {e}")

# --- 2. 過去30年の平均利回りを計算する関数 ---
@st.cache_data(ttl=86400)
def get_historical_yields():
    tickers = {
        "日経平均": "^N225",
        "S&P 500": "^GSPC",
        "オルカン(ACWI)": "ACWI",
        "金(Gold)": "GC=F"
    }
    yield_results = {}
    
    for name, symbol in tickers.items():
        try:
            ticker = yf.Ticker(symbol)
            # 30年間のデータを取得
            hist = ticker.history(period="30y")
            
            if len(hist) > 1:
                start_price = hist['Close'].iloc[0]
                end_price = hist['Close'].iloc[-1]
                total_years = (hist.index[-1] - hist.index[0]).days / 365.25
                cagr = (pow(end_price / start_price, 1 / total_years) - 1) * 100
                current_price = hist['Close'].iloc[-1]
                change = current_price - hist['Close'].iloc[-2]
                yield_results[name] = {"cagr": cagr, "price": current_price, "change": change}
        except:
            yield_results[name] = {"cagr": 0, "price": 0, "change": 0}
    return yield_results

# --- 3. UIの構築 ---
st.set_page_config(page_title="新NISA シミュレーター Pro+", layout="wide")
st.title("💰 新NISA 運用シミュレーター")

# 市場データの取得
historical_data = get_historical_yields()

# サイドバー：入力設定（名前の入力を削除）
st.sidebar.header("📊 シミュレーション設定")
monthly_investment = st.sidebar.number_input("月額積立額 (円)", min_value=1000, max_value=300000, value=50000, step=1000)

# デフォルト値をS&P500の平均に設定
sp500_avg = historical_data.get("S&P 500", {}).get("cagr", 5.0)
annual_rate = st.sidebar.slider("想定年率 (%)", 0.1, 15.0, float(round(sp500_avg, 1)))
years = st.sidebar.slider("運用年数 (年)", 1, 50, 20)

# --- 4. 計算ロジック ---
def calculate_investment(monthly, rate, duration):
    data = []
    total_principal = 0
    current_value = 0
    monthly_rate = rate / 100 / 12
    nisa_limit = 18000000
    for month in range(1, duration * 12 + 1):
        if total_principal + monthly <= nisa_limit:
            total_principal += monthly
            current_value += monthly
        current_value *= (1 + monthly_rate)
        if month % 12 == 0:
            data.append({"年": month // 12, "元本": total_principal, "運用益": current_value - total_principal, "合計資産": current_value})
    return pd.DataFrame(data)

df_result = calculate_investment(monthly_investment, annual_rate, years)
final_wealth = df_result.iloc[-1]["合計資産"]

# メイン画面表示
st.subheader(f"📈 {years}年後の推定資産: {int(final_wealth):,} 円")
fig = px.area(df_result, x="年", y=["元本", "運用益"], color_discrete_map={"元本": "#83c9ff", "運用益": "#0068c9"})
st.plotly_chart(fig, use_container_width=True)

# 市場実績データ表示
st.divider()
st.subheader("📋 投資判断の参考：市場実績データ")
st.markdown("過去30年の年平均成長率 (CAGR) と現在の市場価格です。")

m_cols = st.columns(len(historical_data))
for i, (name, val) in enumerate(historical_data.items()):
    with m_cols[i]:
        st.metric(label=f"{name}", value=f"{val['price']:,.1f}", delta=f"{val['change']:,.1f}")
        st.info(f"30年平均利回り: **{val['cagr']:.2f}%**")

# --- 5. 保存機能 (user_nameをゲストユーザーに固定) ---
st.divider()
if st.button("このシミュレーション結果を保存する"):
    new_data = {
        "user_name": "ゲストユーザー", # 固定値に変更
        "monthly_investment": monthly_investment,
        "annual_rate": annual_rate,
        "years": years,
        "final_wealth": int(final_wealth)
    }
    try:
        supabase.table("nisa_logs").insert(new_data).execute()
        st.success("データベースに保存しました！")
    except Exception as e:
        st.error(f"保存失敗: {e}")

# 履歴表示
st.subheader("💾 最近の保存履歴")
try:
    res = supabase.table("nisa_logs").select("*").order("id", desc=True).limit(5).execute()
    if res.data:
        st.dataframe(pd.DataFrame(res.data)[["monthly_investment", "annual_rate", "final_wealth", "created_at"]])
except:
    st.warning("履歴を取得できません。")