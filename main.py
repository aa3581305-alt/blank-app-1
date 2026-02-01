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

# --- 2. 市場データの取得関数 (過去実績) ---
@st.cache_data(ttl=86400)
def get_historical_data():
    # 利回り計算用の30年データ
    yield_tickers = {
        "日経平均 (円)": "^N225",
        "S&P 500 (USD)": "^GSPC",
        "オルカン(ACWI) (USD)": "ACWI",
        "金(Gold) (USD)": "GC=F"
    }
    yield_results = {}
    for name, symbol in yield_tickers.items():
        try:
            hist = yf.Ticker(symbol).history(period="30y")
            if len(hist) > 1:
                cagr = (pow(hist['Close'].iloc[-1] / hist['Close'].iloc[0], 1 / (len(hist)/252)) - 1) * 100
                yield_results[name] = {"cagr": cagr, "price": hist['Close'].iloc[-1], "change": hist['Close'].iloc[-1] - hist['Close'].iloc[-2]}
        except:
            yield_results[name] = {"cagr": 0, "price": 0, "change": 0}

    # ドル円の50年データ
    try:
        usdjpy_50y = yf.Ticker("JPY=X").history(period="max")['Close']
        # 1976年以降に絞り込む（約50年前）
        usdjpy_50y = usdjpy_50y[usdjpy_50y.index > "1976-01-01"]
    except:
        usdjpy_50y = pd.Series()

    return yield_results, usdjpy_50y

# --- 3. UIの構築 ---
st.set_page_config(page_title="新NISA シミュレーター Pro++", layout="wide")
st.title("💰 新NISA 運用シミュレーター")

yield_data, fx_hist = get_historical_data()

# サイドバー設定
st.sidebar.header("📊 シミュレーション設定")
monthly_inv = st.sidebar.number_input("月額積立額 (円)", 1000, 300000, 50000)
sp500_avg = yield_data.get("S&P 500 (USD)", {}).get("cagr", 5.0)
annual_rate = st.sidebar.slider("想定年率 (%)", 0.1, 15.0, float(round(sp500_avg, 1)))
years = st.sidebar.slider("運用年数 (年)", 1, 50, 20)

# シミュレーション計算
def calculate_nisa(monthly, rate, duration):
    data = []
    total_principal, current_value = 0, 0
    m_rate = rate / 100 / 12
    for m in range(1, duration * 12 + 1):
        if total_principal + monthly <= 18000000:
            total_principal += monthly
            current_value += monthly
        current_value *= (1 + m_rate)
        if m % 12 == 0:
            data.append({"年": m // 12, "元本": total_principal, "運用益": current_value - total_principal, "資産総額": current_value})
    return pd.DataFrame(data)

df_sim = calculate_nisa(monthly_inv, annual_rate, years)
st.subheader(f"📈 {years}年後の推定資産: {int(df_sim.iloc[-1]['資産総額']):,} 円")
st.plotly_chart(px.area(df_sim, x="年", y=["元本", "運用益"]), use_container_width=True)

# 市場実績データ表示
st.divider()
st.subheader("📋 投資判断の参考：市場実績データ (過去30年)")
m_cols = st.columns(len(yield_data))
for i, (name, val) in enumerate(yield_data.items()):
    with m_cols[i]:
        st.metric(label=name, value=f"{val['price']:,.1f}", delta=f"{val['change']:,.1f}")
        st.info(f"30年平均利回り: **{val['cagr']:.2f}%**")

# --- 4. ドル円50年チャート ---
st.divider()
st.subheader("💱 歴史的背景：ドル円為替レートの推移 (過去50年)")
st.markdown("新NISAでの海外資産（S&P500等）投資において、為替変動は重要な要素です。1970年代からの推移を確認しましょう。")

if not fx_hist.empty:
    fig_fx = px.line(fx_hist, labels={'value': '円/ドル', 'Date': '年'})
    fig_fx.update_layout(showlegend=False, hovermode="x unified")
    # 現在の円安水準を分かりやすくするためのハイライト
    fig_fx.add_hline(y=fx_hist.iloc[-1], line_dash="dot", line_color="red", annotation_text=f"現在: {fx_hist.iloc[-1]:.1f}円")
    st.plotly_chart(fig_fx, use_container_width=True)
else:
    st.warning("為替データの取得に失敗しました。")

# 保存と履歴
if st.button("このシミュレーション結果を保存する"):
    try:
        supabase.table("nisa_logs").insert({
            "user_name": "ゲストユーザー", "monthly_investment": monthly_inv, 
            "annual_rate": annual_rate, "years": years, "final_wealth": int(df_sim.iloc[-1]["資産総額"])
        }).execute()
        st.success("保存完了！")
    except: st.error("保存失敗")

st.subheader("💾 最近の保存履歴")
try:
    res = supabase.table("nisa_logs").select("*").order("id", desc=True).limit(5).execute()
    if res.data: st.dataframe(pd.DataFrame(res.data)[["monthly_investment", "annual_rate", "final_wealth", "created_at"]])
except: st.warning("履歴表示不可")