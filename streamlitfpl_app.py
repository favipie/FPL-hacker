import streamlit as st
import pandas as pd
import requests
import matplotlib.pyplot as plt
import seaborn as sns

# --- CONFIG & STYLING ---
st.set_page_config(page_title="FPL ML Optimizer", layout="wide")
st.title("⚽ FPL AI-Decision Engine")
st.markdown("Predicting Points, Translation Loopholes, and Transfer ROI")

# --- DATA FETCHING ---
@st.cache_data
def get_fpl_data():
    url = 'https://fantasy.premierleague.com/api/bootstrap-static/'
    r = requests.get(url).json()
    df = pd.DataFrame(r['elements'])
    teams = pd.DataFrame(r['teams'])
    # Mapping team names
    team_map = teams.set_index('id')['name'].to_dict()
    df['team_name'] = df['team'].map(team_map)
    return df

try:
    df = get_fpl_data()
except:
    st.error("FPL API Down. Please try again later.")
    st.stop()

# --- ML LOGIC: LEAGUE TRANSLATION ---
# Promoted or New Transfer logic
def calculate_translated_metrics(row):
    # Default Multipliers
    multiplier = 1.0
    # Championship Loophole
    if row['team_name'] in ['Leicester', 'Ipswich', 'Southampton']:
        multiplier = 0.75 
    # Logic: Adjusted xG = raw_xg * multiplier
    return float(row['expected_goals_per_90']) * multiplier

df['adj_xg_90'] = df.apply(calculate_translated_metrics, axis=1)

# --- SIDEBAR FILTERS ---
st.sidebar.header("Filter Players")
pos_map = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}
pos_choice = st.sidebar.multiselect("Position", options=[1,2,3,4], default=[3,4], format_func=lambda x: pos_map[x])
min_price = st.sidebar.slider("Max Price", 4.0, 15.0, 15.0)

filtered_df = df[(df['element_type'].isin(pos_choice)) & (df['now_cost'] <= min_price * 10)]

# --- MAIN DASHBOARD ---
tab1, tab2, tab3 = st.tabs(["🚀 Top Picks", "📈 Translation Loophole", "💸 Transfer ROI (-4)"])

with tab1:
    st.subheader("Top Recommended Players (Context Adjusted)")
    # Simple EV Score: (Form * 0.3) + (xG_90 * 0.7)
    filtered_df['ev_score'] = (filtered_df['form'].astype(float) * 0.4) + (filtered_df['adj_xg_90'] * 5)
    
    display_cols = ['web_name', 'team_name', 'now_cost', 'form', 'adj_xg_90', 'ev_score']
    top_picks = filtered_df.sort_values('ev_score', ascending=False).head(10)
    st.dataframe(top_picks[display_cols].style.background_gradient(cmap='Greens'))

with tab2:
    st.subheader("Championship & Transfer Translation")
    st.info("Showing how 'Raw xG' is adjusted for PL difficulty.")
    
    # Comparison Chart
    comp_df = top_picks[['web_name', 'expected_goals_per_90', 'adj_xg_90']].copy()
    comp_df = comp_df.melt(id_vars='web_name', var_name='Metric', value_name='Value')
    
    fig, ax = plt.subplots()
    sns.barplot(data=comp_df, x='Value', y='web_name', hue='Metric', ax=ax)
    st.pyplot(fig)

with tab3:
    st.subheader("Should you take a -4 Hit?")
    col1, col2 = st.columns(2)
    
    with col1:
        p_out = st.selectbox("Player OUT", df['web_name'].sort_values())
        p_in = st.selectbox("Player IN", df['web_name'].sort_values())
    
    with col2:
        gw_horizon = st.slider("Gameweek Horizon", 1, 5, 3)
        prob_start = st.slider("Probability of Starting (%)", 0, 100, 85) / 100

    # Mock ROI Logic
    pts_out = float(df[df['web_name']==p_out]['form'].values[0]) * gw_horizon
    pts_in = float(df[df['web_name']==p_in]['form'].values[0]) * gw_horizon * prob_start
    
    net_gain = pts_in - pts_out - 4
    
    if net_gain > 0:
        st.success(f"✅ YES: Taking a hit is statistically justified. Estimated Net Gain: {net_gain:.2f} pts")
    else:
        st.error(f"❌ NO: Do not take the hit. Estimated Loss: {net_gain:.2f} pts")

# --- FOOTER ---
st.divider()
st.caption("Data Source: Official FPL API. Machine Learning models are probabilistic; use as a guide, not a certainty.")
