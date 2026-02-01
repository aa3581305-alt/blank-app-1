import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf
from supabase import create_client, Client
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

# --- 2. 過去30年の平均利回りとボラティリティを計算 ---
@st.cache_data(ttl=86400)
def get_historical_analysis():
    tickers = {
        "日経平均 (円)": "^N225",
        "S&P 500 (USD)": "^GSPC",
        "オルカン(ACWI) (USD)": "ACWI",
        "金(Gold) (USD)": "GC=F"
    }
    results = {}
    for name, symbol in tickers.items():
        try:
            hist = yf.Ticker(symbol).history(period="30y")['Close']
            returns = hist.pct_change().dropna()
            # 年率平均(幾何平均)
            cagr = (pow(hist.iloc[-1] / hist.iloc[0], 1 / (len(hist)/252)) - 1) * 100
            # 年率ボラティリティ (標準偏差)
            volatility = returns.std() * np.sqrt(252) * 100
            results[name] = {"cagr": cagr, "vol": volatility, "price": hist.iloc[-1]}
        except:
            results[name] = {"cagr": 0, "vol": 0, "price": 0}
    return results

# --- 3. UIの構築 ---
st.set_page_config(page_title="新NISA リスク分析シミュレーター", layout="wide")
st.title("💰 新NISA リスク考慮シミュレーター")

h_data = get_historical_analysis()

# サイドバー
st.sidebar.header("📊 シミュレーション設定")
monthly_inv = st.sidebar.number_input("月額積立額 (円)", 1000, 300000, 50000)
sp500 = h_data.get("S&P 500 (USD)", {"cagr": 5.0, "vol": 15.0})
avg_rate = st.sidebar.slider("想定年率 (%)", 0.1, 15.0, float(round(sp500["cagr"], 1)))
vol_rate = st.sidebar.slider("ボラティリティ/リスク (%)", 0.0, 40.0, float(round(sp500["vol"], 1)))
years = st.sidebar.slider("運用年数 (年)", 1, 50, 20)

# --- 4. モンテカルロ法によるリスクシミュレーション ---
def simulate_risk(monthly, rate, vol, duration):
    n_sims = 100 # 計算負荷のため100回試行
    mu = rate / 100 / 12
    sigma = vol / 100 / np.sqrt(12)
    nisa_limit = 18000000
    
    all_results = []
    for _ in range(n_sims):
        current_value = 0
        total_principal = 0
        monthly_values = []
        for m in range(1, duration * 12 + 1):
            if total_principal + monthly <= nisa_limit:
                total_principal += monthly
                current_value += monthly
            # リスク(ボラティリティ)を乗じる
            random_return = np.random.normal(mu, sigma)
            current_value *= (1 + random_return)
            if m % 12 == 0:
                monthly_values.append(current_value)
        all_results.append(monthly_values)
    
    res_np = np.array(all_results)
    years_range = list(range(1, duration + 1))
    
    return pd.DataFrame({
        "年": years_range,
        "中央値": np.median(res_np, axis=0),
        "楽観ケース(上位5%)": np.percentile(res_np, 95, axis=0),
        "悲観ケース(下位5%)": np.percentile(res_np, 5, axis=0),
        "元本": [min(monthly * 12 * y, nisa_limit) for y in years_range]
    })

df_risk = simulate_risk(monthly_inv, avg_rate, vol_rate, years)

# グラフ表示
st.subheader(f"📈 {years}年後の資産予測 (リスク考慮)")
fig = go.Figure()
fig.add_trace(go.Scatter(x=df_risk["年"], y=df_risk["楽観ケース(上位5%)"], name="楽観ケース", line=dict(width=0), showlegend=False))
fig.add_trace(go.Scatter(x=df_risk["年"], y=df_risk["悲観ケース(下位5%)"], name="予測の幅 (95%信頼区間)", fill='tonexty', fillcolor='rgba(0,104,201,0.2)', line=dict(width=0)))
fig.add_trace(go.Scatter(x=df_risk["年"], y=df_risk["中央値"], name="期待値 (中央値)", line=dict(color='#0068c9', width=3)))
fig.add_trace(go.Scatter(x=df_risk["年"], y=df_risk["元本"], name="投資元本", line=dict(color='gray', dash='dash')))
st.plotly_chart(fig, use_container_width=True)

# 市場指標
st.divider()
st.subheader("📋 市場実績データ (ボラティリティ参考)")
m_cols = st.columns(len(h_data))
for i, (name, val) in enumerate(h_data.items()):
    with m_cols[i]:
        st.metric(label=name, value=f"{val['price']:,.0f}")
        st.write(f"平均利回り: **{val['cagr']:.1f}%**")
        st.write(f"リスク(σ): **{val['vol']:.1f}%**")

# 以下、保存機能などは前のコードと同様（省略）