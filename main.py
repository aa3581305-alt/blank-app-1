# --- 4. モンテカルロ法によるリスクシミュレーション (5%境界版) ---
def simulate_investment_risk(monthly, rate, vol, duration):
    n_sims = 300 # 精度向上のため試行回数を増加
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
        "上位5%": np.percentile(res_np, 95, axis=0), # 上位5%の境界
        "下位5%": np.percentile(res_np, 5, axis=0),  # 下位5%の境界
        "元本": [min(monthly * 12 * y, nisa_limit) for y in years_list]
    })

df_res = simulate_investment_risk(monthly_inv, avg_rate, vol_rate, years)

# --- 5. メインチャートの表示 ---
st.subheader(f"📈 {years}年後の予測範囲 (90%信頼区間)")
st.markdown(f"平均的な結果は **{int(df_res.iloc[-1]['平均値']):,} 円** ですが、"
            f"下位5%の悲観ケースでは **{int(df_res.iloc[-1]['下位5%']):,} 円** まで下振れる可能性があります。")

fig = go.Figure()

# エリア表示 (上位5% 〜 下位5% の範囲を塗る)
fig.add_trace(go.Scatter(x=df_res["年"], y=df_res["上位5%"], name="上位5% (絶好調)", line=dict(width=0), showlegend=False))
fig.add_trace(go.Scatter(x=df_res["年"], y=df_res["下位5%"], name="予測範囲 (90%の確率でこの中に収まる)", fill='tonexty', fillcolor='rgba(0,104,201,0.2)', line=dict(width=0)))

# 中央の平均線 (太線)
fig.add_trace(go.Scatter(x=df_res["年"], y=df_res["平均値"], name="平均的な推移", line=dict(color='#0068c9', width=4)))

# 元本線 (点線)
fig.add_trace(go.Scatter(x=df_res["年"], y=df_res["元本"], name="投資元本", line=dict(color='gray', dash='dash')))

fig.update_layout(xaxis_title="経過年数", yaxis_title="資産額 (円)", hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
st.plotly_chart(fig, use_container_width=True)