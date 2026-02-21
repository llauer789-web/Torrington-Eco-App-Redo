import streamlit as st
import pandas as pd
import pydeck as pdk

# 1. Page Config
st.set_page_config(page_title="Torrington Eco-Pulse", layout="wide")

# 2. YOUR GOOGLE SHEET LINK (Line 11)
# I have already swapped the end of your link for you!
SHEET_URL = "https://docs.google.com/spreadsheets/d/1zEWu2R2ryMDrMMAih1RfU5yBTdNA4uwpR_zcZZ4DXlc/gviz/tq?tqx=out:csv"

def load_data():
    try:
        # This reads your Google Sheet directly
        df = pd.read_csv(SHEET_URL)
        # Clean up any weird naming from Google Sheets
        df.columns = [c.strip() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Waiting for data... check Share settings! {e}")
        return pd.DataFrame(columns=["Alert_Name", "Status", "lat", "lon", "color", "radius"])

# Load data into the app
if 'alerts_df' not in st.session_state:
    st.session_state.alerts_df = load_data()

# 3. Sidebar Reporting Form
with st.sidebar:
    st.title("🚨 Report Alert")
    st.info("Currently Reading from Google Sheets")
    with st.form("alert_form", clear_on_submit=True):
        new_name = st.text_input("Issue Title")
        new_status = st.selectbox("Status", ["Urgent", "Active", "Watching", "Resolved"])
        new_lat = st.number_input("Latitude", value=41.8006, format="%.4f")
        new_lon = st.number_input("Longitude", value=-73.1212, format="%.4f")
        new_radius = st.slider("Impact Zone (meters)", 100, 2000, 500)
        
        if st.form_submit_button("Submit (Local Only)"):
            st.warning("To SAVE to the sheet, we need to add the 'Service Account' key next.")

# 4. Main Dashboard UI
st.title("🌍 Torrington Eco-Pulse")

# 5. Map View
view_state = pdk.ViewState(latitude=41.8006, longitude=-73.1212, zoom=12, pitch=45)

layer = pdk.Layer(
    "ScatterplotLayer",
    st.session_state.alerts_df,
    get_position='[lon, lat]',
    get_color=[255, 0, 0, 150], # Default Red
    get_radius='radius',
    pickable=True,
    opacity=0.7,
)

st.pydeck_chart(pdk.Deck(
    map_style='mapbox://styles/mapbox/dark-v10', 
    initial_view_state=view_state, 
    layers=[layer],
    tooltip={"text": "{Alert_Name}"}
))

# 6. Show the Data Table
st.markdown("### Spreadsheet Data")
st.write(st.session_state.alerts_df)
