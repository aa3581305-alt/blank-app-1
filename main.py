import streamlit as st
import pandas as pd
import plotly.express as px

# ページ設定
st.set_page_config(page_title="新NISA シミュレーション", layout="wide")

# --- タイトルと説明 ---
st.title("💰 新NISA 運用シミュレーター")
st.markdown("""
毎月の積立額、想定利回り、運用年数を入力して、将来の資産推移をシミュレーションします。
新NISAの生涯投資枠（最大1,800万円）を意識しながら計画を立てましょう。
""")

st.divider()

# --- サイドバー：入力パラメータ ---
st.sidebar.header("📊 シミュレーション条件")

monthly_investment = st.sidebar.number_input(
    "月額積立額 (円)",
    min_value=1000,
    max_value=300000,
    value=50000,
    step=1000,
    format="%d"
)

annual_return_rate = st.sidebar.slider(
    "想定年率 (%)",
    min_value=0.1,
    max_value=15.0,
    value=5.0,
    step=0.1
)

years = st.sidebar.slider(
    "運用年数 (年)",
    min_value=1,
    max_value=50,
    value=20
)

# --- 計算ロジック ---
def calculate_nisa_simulation(monthly_amt, rate_pct, duration_years):
    data = []
    total_invested = 0      # 累計投資額（元本）
    current_value = 0       # 現在の評価額
    monthly_rate = rate_pct / 100 / 12
    nisa_limit = 18000000   # 新NISA 生涯投資枠
    limit_reached = False
    
    for month in range(1, duration_years * 12 + 1):
        # 投資枠が残っている場合のみ追加投資
        if total_invested + monthly_amt <= nisa_limit:
            total_invested += monthly_amt
            current_value += monthly_amt
        elif total_invested < nisa_limit:
            # 枠の残り端数分だけ投資
            remainder = nisa_limit - total_invested
            total_invested += remainder
            current_value += remainder
            limit_reached = True
        else:
            limit_reached = True
        
        # 運用益の加算 (複利計算)
        current_value *= (1 + monthly_rate)
        
        # 年単位のデータを記録（グラフ用）
        if month % 12 == 0:
            year = month // 12
            profit = current_value - total_invested
            data.append({
                "年数": year,
                "元本": total_invested,
                "運用益": profit,
                "資産総額": current_value
            })
            
    return pd.DataFrame(data), limit_reached

# シミュレーション実行
df, is_limit_reached = calculate_nisa_simulation(monthly_investment, annual_return_rate, years)

# --- 結果の表示 ---

# 1. メトリクス（重要数字）の表示
col1, col2, col3 = st.columns(3)
final_data = df.iloc[-1]

with col1:
    st.metric(label="資産総額", value=f"{int(final_data['資産総額']):,} 円")
with col2:
    st.metric(label="投資元本", value=f"{int(final_data['元本']):,} 円")
with col3:
    st.metric(label="運用益 (非課税)", value=f"+{int(final_data['運用益']):,} 円", delta_color="normal")

if is_limit_reached:
    st.warning(f"⚠️ 設定期間中に新NISAの生涯投資枠（1,800万円）に到達しました。それ以降は追加投資なしで運用のみ継続しています。")

# 2. グラフの作成 (Plotly)
st.subheader("📈 資産推移グラフ")

# データをLong形式に変換（Plotlyでの積み上げグラフ用）
df_melted = df.melt(id_vars=["年数"], value_vars=["元本", "運用益"], var_name="内訳", value_name="金額")

fig = px.area(
    df_melted, 
    x="年数", 
    y="金額", 
    color="内訳",
    title=f"積立 {monthly_investment:,}円/月 × {years}年 (年率 {annual_return_rate}%)",
    color_discrete_map={"元本": "#83c9ff", "運用益": "#0068c9"},
    labels={"金額": "評価額 (円)"}
)
fig.update_layout(hovermode="x unified") # ホバー時に詳細を表示

st.plotly_chart(fig, use_container_width=True)

# 3. 詳細データテーブル（オプション）
with st.expander("詳細データを見る"):
    st.dataframe(
        df.style.format({
            "元本": "{:,.0f} 円", 
            "運用益": "{:,.0f} 円", 
            "資産総額": "{:,.0f} 円"
        })
    )