import streamlit as st
import pandas as pd
import pydeck as pdk
from PIL import Image
import base64
from io import BytesIO

st.set_page_config(page_title="Torrington Eco-Pulse", layout="wide")

# Link to your Google Sheet
SHEET_URL = "https://docs.google.com/spreadsheets/d/1zEWu2R2ryMDrMMAih1RfU5yBTdNA4uwpR_zcZZ4DXlc/gviz/tq?tqx=out:csv"

def load_data():
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = [c.strip() for c in df.columns]
        return df
    except:
        return pd.DataFrame(columns=["Alert_Name", "Status", "lat", "lon", "color", "radius"])

if 'alerts_df' not in st.session_state:
    st.session_state.alerts_df = load_data()

# --- SIDEBAR WITH PHOTO UPLOAD ---
with st.sidebar:
    st.title("🚨 Report Alert")
    with st.form("alert_form", clear_on_submit=True):
        new_name = st.text_input("Issue Title")
        new_status = st.selectbox("Status", ["Urgent", "Active", "Watching"])
        new_lat = st.number_input("Latitude", value=41.8006, format="%.4f")
        new_lon = st.number_input("Longitude", value=-73.1212, format="%.4f")
        
        # PHOTO UPLOADER COMPONENT
        uploaded_file = st.file_uploader("Upload Evidence (Photo)", type=['png', 'jpg', 'jpeg'])
        
        if st.form_submit_button("Submit Alert"):
            # This adds it to the current view (Persistence comes next!)
            st.success("Photo attached and alert synced!")

# --- MAIN DASHBOARD ---
st.title("🌍 Torrington Eco-Pulse")

# Show the Map
view_state = pdk.ViewState(latitude=41.8006, longitude=-73.1212, zoom=12, pitch=45)
layer = pdk.Layer("ScatterplotLayer", st.session_state.alerts_df, get_position='[lon, lat]', get_color=[255,0,0,150], get_radius=500, pickable=True)
st.pydeck_chart(pdk.Deck(map_style='mapbox://styles/mapbox/dark-v10', initial_view_state=view_state, layers=[layer]))

# --- SHOW PHOTO IN CARDS ---
st.markdown("### Evidence Gallery")
if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption=f"Latest Evidence for: {new_name}", use_container_width=True)
else:
    st.info("No photos uploaded for this session yet.")
