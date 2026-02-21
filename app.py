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
        return df
    except:
        # Fallback if the sheet is empty
        return pd.DataFrame(columns=["Alert_Name", "Status", "lat", "lon", "color", "radius"])

# Initialize Data
if 'alerts_df' not in st.session_state:
    st.session_state.alerts_df = load_data()

# 3. Sidebar with Reporting & Photo Upload
with st.sidebar:
    st.title("🚨 Report Alert")
    with st.form("alert_form", clear_on_submit=True):
        new_name = st.text_input("Issue Title")
        new_status = st.selectbox("Status", ["Urgent", "Active", "Watching", "Resolved"])
        new_lat = st.number_input("Latitude", value=41.8006, format="%.4f")
        new_lon = st.number_input("Longitude", value=-73.1212, format="%.4f")
        
        # CAMERA/FILE UPLOADER
        uploaded_file = st.file_uploader("Upload Evidence (Photo)", type=['png', 'jpg', 'jpeg'])
        
        if st.form_submit_button("Submit Alert"):
            st.success("Alert visible in this session!")

# 4. Main Dashboard UI
st.title("🌍 Torrington Eco-Pulse")

# 5. Map View
view_state = pdk.ViewState(
    latitude=41.8006, 
    longitude=-73.1212, 
    zoom=13, 
    pitch=0
)

#
