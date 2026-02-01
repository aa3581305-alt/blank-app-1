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

# --- 2. 過去の実績データの取得と分析 ---
@st.cache_data(ttl=86400)
def get_market_analysis():
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
            # 幾何平均利回り (CAGR)
            cagr = (pow(hist.iloc[-1] / hist.iloc[0], 1 / (len(hist)/252)) - 1) * 100
            # ボラティリティ (年率標準偏差)
            vol = returns.std() * np.sqrt(252) * 100
            results[name] = {"cagr": cagr, "vol": vol, "price": hist.iloc[-1]}
        except:
            results[name] = {"cagr": 0, "vol": 0, "price": 0}
    
    # 50年為替データ
    try:
        fx = yf.Ticker("JPY=X").history(period="max")['Close']
        fx = fx[fx.index > "1976-01-01"]
    except:
        fx = pd.Series()
        
    return results, fx

# --- 3. UIの構築 ---
st.set_page_config(page_title="新NISA 精密シミュレーター", layout="wide")
st.title("💰 新NISA 精密シミュレーター (リスク分析版)")

market_stats, fx_hist = get_market_analysis()

# サイドバー
st.sidebar.header("📊 シミュレーション設定")
monthly_inv = st.sidebar.number_input("月額積立額 (円)", 1000, 300000, 50000)
sp500_ref = market_stats.get("S&P 500 (USD)", {"cagr": 7.0, "vol": 18.0})
avg_rate = st.sidebar.slider("想定年率 (%)", 0.1, 15.0, float(round(sp500_ref["cagr"], 1)))
vol_rate = st.sidebar.slider("ボラティリティ/リスク (%)", 0.0, 40.0, float(round(sp500_ref["vol"], 1)))
years = st.sidebar.slider("運用年数 (年)", 1, 50, 20)

# --- 4. モンテカルロ法によるリスクシミュレーション (5%境界版) ---
def simulate_investment_risk(monthly, rate, vol, duration):
    n_sims = 500 # 精度向上のため試行回数を増やしました
    mu = rate / 100 / 12
    sigma = vol / 100 / np.sqrt(12)
    nisa_limit = 18000000
    
    all_runs = []
    for _ in range(n_sims):
        val = 0
        principal = 0
        path = []
        for m in range(1, duration * 12 + 1):
            if principal + monthly <= nisa_limit:
                principal += monthly
                val += monthly
            # 正規分布に基づきランダムなリターンを生成
            val *= (1 + np.random.normal(mu, sigma))
            if m % 12 == 0:
                path.append(val)
        all_runs.append(path)
    
    res_np = np.array(all_runs)
    years_list = list(range(1, duration + 1))
    
    return pd.DataFrame({
        "年": years_list,
        "平均値": np.mean(res_np, axis=0),
        "上位5%": np.percentile(res_np, 95, axis=0), # 上位5%の境界点
        "下位5%": np.percentile(res_np, 5, axis=0),  # 下位5%の境界点
        "元本": [min(monthly * 12 * y, nisa_limit) for y in years_list]
    })

df_res = simulate_investment_risk(monthly_inv, avg_rate, vol_rate, years)

# --- 5. メインチャートの表示 ---
st.subheader(f"📈 {years}年後の予測範囲 (90%信頼区間)")
st.markdown(f"平均的な結果は **{int(df_res.iloc[-1]['平均値']):,} 円** です。 "
            f"90%の確率で **{int(df_res.iloc[-1]['下位5%']):,} 円 〜 {int(df_res.iloc[-1]['上位5%']):,} 円** の範囲に収まると予測されます。")

fig = go.Figure()

# エリア表示 (上位5% 〜 下位5% の範囲を塗る)
fig.add_trace(go.Scatter(x=df_res["年"], y=df_res["上位5%"], name="上位5% (絶好調)", line=dict(width=0), showlegend=False))
fig.add_trace(go.Scatter(x=df_res["年"], y=df_res["下位5%"], name="予測範囲 (確率90%)", fill='tonexty', fillcolor='rgba(0,104,201,0.2)', line=dict(width=0)))

# 中央の平均線 (太線)
fig.add_trace(go.Scatter(x=df_res["年"], y=df_res["平均値"], name="平均値", line=dict(color='#0068c9', width=4)))

# 元本線 (点線)
fig.add_trace(go.Scatter(x=df_res["年"], y=df_res["元本"], name="投資元本", line=dict(color='gray', dash='dash')))

fig.update_layout(
    xaxis_title="経過年数", 
    yaxis_title="資産額 (円)", 
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)
st.plotly_chart(fig, use_container_width=True)

# 市場実績データ表示
st.divider()
st.subheader("📋 市場実績データ (利回りとリスクの参考)")
m_cols = st.columns(len(market_stats))
for i, (name, val) in enumerate(market_stats.items()):
    with m_cols[i]:
        st.metric(label=name, value=f"{val['price']:,.0f}")
        st.info(f"平均利回り: {val['cagr']:.1f}%\n\nリスク(σ): {val['vol']:.1f}%")

# 50年為替チャート
st.divider()
st.subheader("💱 ドル円為替レートの推移 (過去50年)")
if not fx_hist.empty:
    fig_fx = px.line(fx_hist)
    fig_fx.add_hline(y=fx_hist.iloc[-1], line_dash="dot", line_color="red", annotation_text=f"現在: {fx_hist.iloc[-1]:.1f}円")
    st.plotly_chart(fig_fx, use_container_width=True)

# 保存機能
if st.button("このシミュレーション結果を保存する"):
    try:
        supabase.table("nisa_logs").insert({
            "user_name": "ゲストユーザー", "monthly_investment": monthly_inv, 
            "annual_rate": avg_rate, "years": years, "final_wealth": int(df_res.iloc[-1]["平均値"])
        }).execute()
        st.success("保存完了！")
    except: st.error("保存失敗")