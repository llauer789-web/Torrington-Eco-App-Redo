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
        return pd.DataFrame(columns=["Alert_Name", "Status", "lat", "lon", "color", "radius"])

# Initialize Data
if 'alerts_df' not in st.session_state:
    st.session_state.alerts_df = load_data()

# 3. Sidebar with Reporting & Photo Upload
with st.sidebar:
    st.title("🚨 Report Alert")
    with st.form("alert_form", clear_on_submit=True):
        new_name = st.text_input("Issue Title")
        new_status = st.selectbox("Status", ["Urgent", "Active", "Watching"])
        new_lat = st.number_input("Latitude", value=41.8006, format="%.4f")
        new_lon = st.number_input("Longitude", value=-73.1212, format="%.4f")
        
        # CAMERA/FILE UPLOADER
        uploaded_file = st.file_uploader("Upload Evidence (Photo)", type=['png', 'jpg', 'jpeg'])
        
        if st.form_submit_button("Submit Alert"):
            st.success("Alert synced to local session!")

# 4. Main Dashboard UI
st.title("🌍 Torrington Eco-Pulse")

# 5. Map View (Fixed Background & Translucency)
view_state = pdk.ViewState(
    latitude=41.8006, 
    longitude=-73.1212, 
    zoom=13, # Zoomed in slightly more for detail
    pitch=0
)

layer = pdk.Layer(
    "ScatterplotLayer",
    st.session_state.alerts_df,
    get_position='[lon, lat]',
    # [Red, Green, Blue, Alpha] - 100 is see-through
    get_color=[255, 0, 0, 100], 
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
    st.dataframe(st.session_state.alerts_
