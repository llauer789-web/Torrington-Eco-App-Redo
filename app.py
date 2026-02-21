import streamlit as st
import pandas as pd
import pydeck as pdk
from PIL import Image

# 1. Page Config
st.set_page_config(page_title="Torrington Eco-Pulse", layout="wide")

# 2. YOUR GOOGLE SHEET LINK
SHEET_URL = "https://docs.google.com/spreadsheets/d/1zEWu2R2ryMDrMMAih1RfU5yBTdNA4uwpR_zcZZ4DXlc/gviz/tq?tqx=out:csv"

def load_data():
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = [c.strip() for c in df.columns]
        # Force latitude and longitude to be numbers so the map doesn't break
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
        return df.dropna(subset=['lat', 'lon']) # Remove any rows with missing coordinates
    except:
        return pd.DataFrame(columns=["Alert_Name", "Status", "lat", "lon"])

# Initialize Data
if 'alerts_df' not in st.session_state:
    st.session_state.alerts_df = load_data()

# 3. Sidebar with Reporting
with st.sidebar:
    st.title("🚨 Report Alert")
    with st.form("alert_form", clear_on_submit=True):
        new_name = st.text_input("Issue Title")
        new_status = st.selectbox("Status", ["Urgent", "Active", "Watching", "Resolved"])
        new_lat = st.number_input("Latitude", value=41.8006, format="%.4f")
        new_lon = st.number_input("Longitude", value=-73.1212, format="%.4f")
        uploaded_file = st.file_uploader("Upload Evidence", type=['png', 'jpg', 'jpeg'])
        
        if st.form_submit_button("Submit Alert"):
            st.success("Alert added to this session!")

# 4. Main Dashboard UI
st.title("🌍 Torrington Eco-Pulse")

# 5. Map View (The "Safety First" Version)
view_state = pdk.ViewState(
    latitude=41.8006, 
    longitude=-73.1212, 
    zoom=13, 
    pitch=0
)

# We define the color directly here so the spreadsheet can't break it
layer = pdk.Layer(
    "ScatterplotLayer",
    st.session_state.alerts_df,
    get_position='[lon, lat]',
    get_color=[255, 0, 0, 100], # Standard semi-transparent red
    get_radius=250, 
    pickable=True,
)

st.pydeck_chart(pdk.Deck(
    map_style='light', 
    initial_view_state=view_state,
    layers=[layer],
    tooltip={"text": "{Alert_Name}\nStatus: {Status}"}
))

# 6. Evidence Gallery & Data Table
st.markdown("---")
col1, col2 = st.columns([1, 1])

with col1:
    st.markdown("### Evidence Gallery")
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption=f"Evidence: {new_name}", use_container_width=True)
    else:
        st.info("Upload a photo in the sidebar to see it here.")

with col2:
    st.markdown("### Active Data")
    st.dataframe(st.session_state.alerts_df)
