import streamlit as st
import pandas as pd
import numpy as np
import requests
import joblib
import pulp
import matplotlib.pyplot as plt
import seaborn as sns

st.set_page_config(page_title="FPL AI Decision Engine", layout="wide")
st.title("⚽ FPL AI Decision Engine")
st.markdown("LightGBM-powered player predictions and optimal team selection via Integer Linear Programming")

# --- CONSTANTS ---
FEATURES = [
    'avg_pts_last3', 'avg_pts_last5', 'form_trend',
    'avg_minutes_last3', 'avg_xgi_last3', 'avg_ict_last3',
    'avg_bps_last3', 'is_home', 'value', 'avg_fixture_difficulty'
]

MODEL_PATH = r'E:\Fpl-Hackathon\Models\fpl_model.pkl'
PREDICTIONS_PATH = r'E:\Fpl-Hackathon\Data\player_predictions.csv'

# --- LOAD MODEL ---
@st.cache_resource
def load_model():
    return joblib.load(MODEL_PATH)

@st.cache_data
def load_data():
    df = pd.read_csv(PREDICTIONS_PATH)

    r = requests.get('https://fantasy.premierleague.com/api/bootstrap-static/').json()
    teams = pd.DataFrame(r['teams'])
    players = pd.DataFrame(r['elements'])[['id', 'status']]

    team_map = teams.set_index('id')['name'].to_dict()
    pos_map = {1: 'GK', 2: 'DEF', 3: 'MID', 4: 'FWD'}

    df['team_name'] = df['team'].map(team_map)
    df['position'] = df['element_type'].map(pos_map)
    df['price'] = df['now_cost'] / 10

    status_map = players.set_index('id')['status'].to_dict()
    df['status'] = df['player_id'].map(status_map)

    return df

model = load_model()
df = load_data()

# --- SIDEBAR ---
st.sidebar.header("⚙️ Filters")
pos_options = ['GK', 'DEF', 'MID', 'FWD']
selected_positions = st.sidebar.multiselect("Position", pos_options, default=pos_options)
max_price = st.sidebar.slider("Max Price (£m)", 4.0, 15.0, 15.0)
only_available = st.sidebar.checkbox("Only available players", value=True)

filtered = df[df['position'].isin(selected_positions)]
filtered = filtered[filtered['price'] <= max_price]
if only_available:
    filtered = filtered[filtered['status'] == 'a']

# --- TABS ---
tab1, tab2, tab3 = st.tabs([
    "🏆 Top Picks",
    "📊 Model Insights",
    "🤖 Optimal Squad"
])

# ── TAB 1: TOP PICKS ──────────────────────────────────────────────────────────
with tab1:
    st.subheader("Top Player Recommendations")
    st.caption("LightGBM model | MAE: 1.021 pts | Trained on 19,069 gameweek records | Features include fixture difficulty")

    display = filtered[['web_name', 'team_name', 'position', 'price', 'predicted_pts']].copy()
    display.columns = ['Player', 'Team', 'Position', 'Price (£m)', 'Predicted Pts']
    display = display.sort_values('Predicted Pts', ascending=False).head(20)

    st.dataframe(
        display.style.background_gradient(cmap='Greens', subset=['Predicted Pts']),
        use_container_width=True
    )

# ── TAB 2: MODEL INSIGHTS ─────────────────────────────────────────────────────
with tab2:
    st.subheader("Model Performance & Feature Importance")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Model", "LightGBM (Tuned)")
    col2.metric("Model MAE", "1.021 pts")
    col3.metric("Baseline MAE", "1.563 pts")
    col4.metric("Improvement vs Baseline", "34.7%")

    st.divider()

    # Feature importance
    st.markdown("#### Feature Importance")
    importances = pd.Series(
        model.feature_importances_, index=FEATURES
    ).sort_values(ascending=True)

    fig, ax = plt.subplots(figsize=(8, 4))
    importances.plot(kind='barh', ax=ax, color='steelblue')
    ax.set_title('Feature Importance — LightGBM (Tuned)')
    ax.set_xlabel('Importance Score')
    plt.tight_layout()
    st.pyplot(fig)

    st.info("**Key insight:** Minutes played is the strongest predictor — "
            "availability matters more than raw talent for FPL points. "
            "Fixture difficulty is included as a forward-looking feature.")

    st.divider()

    # Model comparison table
    st.markdown("#### Model Comparison")
    comparison = pd.DataFrame({
        'Model': [
            'Baseline (mean)',
            'Linear Regression',
            'Random Forest',
            'LightGBM',
            'LightGBM + Fixture Difficulty',
            'LightGBM Tuned (Optuna)'
        ],
        'MAE': [1.563, 1.053, 1.052, 1.040, 1.040, 1.021],
        'Improvement vs Baseline': ['—', '32.6%', '32.7%', '33.5%', '33.5%', '34.7%']
    })
    st.dataframe(comparison, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### Predicted vs Actual Validation (GW 22-26)")
    st.image(r'E:\Fpl-Hackathon\Data\validation_chart.png')
    st.caption("Overall validation MAE: 0.754 across 5 unseen gameweeks")

# ── TAB 3: OPTIMAL SQUAD ──────────────────────────────────────────────────────
with tab3:
    st.subheader("ILP Optimal Squad Selector")
    st.caption("Integer Linear Programming — selects full 15-man squad then picks best starting 11")

    col_a, col_b = st.columns(2)
    with col_a:
        budget = st.slider("Budget (£m)", 80.0, 100.0, 100.0, step=0.5)
    with col_b:
        st.markdown("**Constraints applied:**")
        st.markdown("- 15-man squad: 2 GK, 5 DEF, 5 MID, 3 FWD\n- Starting 11: 1 GK, 3-5 DEF, 3-5 MID, 1-3 FWD\n- Max 3 per club\n- Budget enforced")

    if st.button("🚀 Generate Optimal Squad", type="primary"):
        with st.spinner("Running ILP optimizer..."):

            opt_df = df[df['status'] == 'a'].copy().reset_index(drop=True)
            n = len(opt_df)
            budget_raw = int(budget * 10)

            # ── Phase 1: Select 15-man squad ──────────────────────────────────
            prob = pulp.LpProblem("FPL_Squad", pulp.LpMaximize)
            x = [pulp.LpVariable(f"x{i}", cat='Binary') for i in range(n)]

            prob += pulp.lpSum(opt_df['predicted_pts'][i] * x[i] for i in range(n))
            prob += pulp.lpSum(x) == 15
            prob += pulp.lpSum(opt_df['now_cost'][i] * x[i] for i in range(n)) <= budget_raw

            for pos, mn, mx in [('GK',2,2),('DEF',5,5),('MID',5,5),('FWD',3,3)]:
                idx = opt_df[opt_df['position']==pos].index.tolist()
                prob += pulp.lpSum(x[i] for i in idx) >= mn
                prob += pulp.lpSum(x[i] for i in idx) <= mx

            for team_id in opt_df['team'].unique():
                idx = opt_df[opt_df['team']==team_id].index.tolist()
                prob += pulp.lpSum(x[i] for i in idx) <= 3

            prob.solve(pulp.PULP_CBC_CMD(msg=0))
            squad = opt_df[[x[i].value() == 1 for i in range(n)]].copy().reset_index(drop=True)

            # ── Phase 2: Pick best starting 11 from squad ─────────────────────
            m = len(squad)
            prob2 = pulp.LpProblem("FPL_Starting11", pulp.LpMaximize)
            y = [pulp.LpVariable(f"y{i}", cat='Binary') for i in range(m)]

            prob2 += pulp.lpSum(squad['predicted_pts'][i] * y[i] for i in range(m))
            prob2 += pulp.lpSum(y) == 11

            for pos, mn, mx in [('GK',1,1),('DEF',3,5),('MID',3,5),('FWD',1,3)]:
                idx = squad[squad['position']==pos].index.tolist()
                prob2 += pulp.lpSum(y[i] for i in idx) >= mn
                prob2 += pulp.lpSum(y[i] for i in idx) <= mx

            prob2.solve(pulp.PULP_CBC_CMD(msg=0))
            squad['is_starter'] = [y[i].value() == 1 for i in range(m)]

        starters = squad[squad['is_starter'] == True]
        bench    = squad[squad['is_starter'] == False]

        total_cost = squad['now_cost'].sum() / 10
        total_pts  = starters['predicted_pts'].sum()

        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Squad Size", "15 players")
        col2.metric("Total Cost", f"£{total_cost:.1f}m")
        col3.metric("Budget Remaining", f"£{budget - total_cost:.1f}m")
        col4.metric("Starting 11 Predicted Pts", f"{total_pts:.1f}")

        st.divider()

        # Starting 11
        st.markdown("### ⚡ Starting 11")
        for pos in ['GK', 'DEF', 'MID', 'FWD']:
            pos_players = starters[starters['position'] == pos][
                ['web_name', 'team_name', 'price', 'predicted_pts']
            ].copy()
            pos_players.columns = ['Player', 'Team', 'Price (£m)', 'Predicted Pts']
            if len(pos_players) > 0:
                st.markdown(f"**{pos}**")
                st.dataframe(
                    pos_players.style.background_gradient(cmap='Greens', subset=['Predicted Pts']),
                    use_container_width=True,
                    hide_index=True
                )

        st.divider()

        # Bench
        st.markdown("### 🪑 Bench (4)")
        bench_display = bench[['web_name', 'team_name', 'position', 'price', 'predicted_pts']].copy()
        bench_display.columns = ['Player', 'Team', 'Position', 'Price (£m)', 'Predicted Pts']
        st.dataframe(
            bench_display.style.background_gradient(cmap='Blues', subset=['Predicted Pts']),
            use_container_width=True,
            hide_index=True
        )