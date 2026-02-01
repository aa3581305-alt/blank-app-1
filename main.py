import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
        "日経平均 (円)": "^N225",
        "S&P 500 (USD)": "^GSPC",
        "オルカン(ACWI) (USD)": "ACWI",
        "金(Gold) (USD)": "GC=F"
    }
    yield_results = {}
    for name, symbol in tickers.items():
        try:
            ticker = yf.Ticker(symbol)
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

# --- 3. 政策金利と為替のデータを取得する関数 ---
@st.cache_data(ttl=86400)
def get_macro_data():
    # 米国政策金利 (実効連邦資金金利の代替として短期国債利回りを使用)
    # 日本政策金利 (短期国債利回りを使用)
    # 為替 (USD/JPY)
    symbols = {"US_Rate": "IR3TIB01USM156N", "JP_Rate": "IR3TIB01JPM156N", "USDJPY": "JPY=X"}
    # FREDデータがyfinanceで取れない場合があるため、金利の代替指標として10年債利回り等を使用
    macro_tickers = {"US10Y": "^TNX", "JP10Y": "JP10Y.BD", "USDJPY": "JPY=X"}
    
    data = {}
    for key, sym in macro_tickers.items():
        try:
            d = yf.Ticker(sym).history(period="5y")['Close']
            data[key] = d
        except:
            pass
    return pd.DataFrame(data).dropna()

# --- 4. UIの構築 ---
st.set_page_config(page_title="新NISA シミュレーター Pro++", layout="wide")
st.title("💰 新NISA 運用シミュレーター")

historical_data = get_historical_yields()

# サイドバー
st.sidebar.header("📊 シミュレーション設定")
monthly_investment = st.sidebar.number_input("月額積立額 (円)", 1000, 300000, 50000)
sp500_avg = historical_data.get("S&P 500 (USD)", {}).get("cagr", 5.0)
annual_rate = st.sidebar.slider("想定年率 (%)", 0.1, 15.0, float(round(sp500_avg, 1)))
years = st.sidebar.slider("運用年数 (年)", 1, 50, 20)

# 計算とグラフ
def calculate_investment(monthly, rate, duration):
    data = []
    total_principal, current_value = 0, 0
    monthly_rate = rate / 100 / 12
    for m in range(1, duration * 12 + 1):
        if total_principal + monthly <= 18000000:
            total_principal += monthly
            current_value += monthly
        current_value *= (1 + monthly_rate)
        if m % 12 == 0:
            data.append({"年": m // 12, "元本": total_principal, "運用益": current_value - total_principal, "合計資産": current_value})
    return pd.DataFrame(data)

df_result = calculate_investment(monthly_investment, annual_rate, years)
st.subheader(f"📈 {years}年後の推定資産: {int(df_result.iloc[-1]['合計資産']):,} 円")
st.plotly_chart(px.area(df_result, x="年", y=["元本", "運用益"]), use_container_width=True)

# 市場実績データ表示
st.divider()
st.subheader("📋 投資判断の参考：市場実績データ")
m_cols = st.columns(len(historical_data))
for i, (name, val) in enumerate(historical_data.items()):
    with m_cols[i]:
        st.metric(label=name, value=f"{val['price']:,.1f}", delta=f"{val['change']:,.1f}")
        st.info(f"30年平均利回り: **{val['cagr']:.2f}%**")

# --- 5. 追加：政策金利と為替の複合チャート ---
st.divider()
st.subheader("🔗 マクロ経済指標：日米金利差と為替レート")
st.markdown("日米の10年債利回り（政策金利の先行指標）と、ドル円為替レートの相関グラフです。")

macro_df = get_macro_data()
if not macro_df.empty:
    fig_macro = go.Figure()
    # 左軸：金利
    fig_macro.add_trace(go.Scatter(x=macro_df.index, y=macro_df['US10Y'], name="米国10年債利回り (%)", yaxis="y1"))
    fig_macro.add_trace(go.Scatter(x=macro_df.index, y=macro_df['JP10Y'], name="日本10年債利回り (%)", yaxis="y1"))
    # 右軸：為替
    fig_macro.add_trace(go.Scatter(x=macro_df.index, y=macro_df['USDJPY'], name="ドル円 (JPY/USD)", yaxis="y2", line=dict(dash='dot')))

    fig_macro.update_layout(
        xaxis=dict(title="日付"),
        yaxis=dict(title="金利 (%)", side="left"),
        yaxis2=dict(title="為替 (円/ドル)", side="right", overlaying="y", showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified"
    )
    st.plotly_chart(fig_macro, use_container_width=True)
else:
    st.warning("マクロ経済データの取得に失敗しました。")

# 保存と履歴
if st.button("この結果を保存する"):
    try:
        supabase.table("nisa_logs").insert({"user_name": "ゲストユーザー", "monthly_investment": monthly_investment, "annual_rate": annual_rate, "years": years, "final_wealth": int(df_result.iloc[-1]["合計資産"])}).execute()
        st.success("保存完了！")
    except: st.error("保存失敗")

st.subheader("💾 最近の保存履歴")
try:
    res = supabase.table("nisa_logs").select("*").order("id", desc=True).limit(5).execute()
    if res.data: st.dataframe(pd.DataFrame(res.data)[["monthly_investment", "annual_rate", "final_wealth", "created_at"]])
except: st.warning("履歴表示不可")