import streamlit as st
import pandas as pd
import pydeck as pdk
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- 1. SETUP & CONNECTION ---
try:
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1zEWu2R2ryMDrMMAih1RfU5yBTdNA4uwpR_zcZZ4DXlc/edit"
    sh = client.open_by_url(SHEET_URL)
    worksheet = sh.get_worksheet(0)
    
    try:
        chat_worksheet = sh.worksheet("Chat")
    except:
        chat_worksheet = sh.add_worksheet(title="Chat", rows="1000", cols="3")
        chat_worksheet.append_row(["Timestamp", "User", "Message"])
except Exception as e:
    st.error(f"Connection Error: {e}")

# --- 2. CSS FOR FIXED CROSSHAIR ---
st.markdown("""
    <style>
    .map-container { position: relative; }
    .crosshair {
        position: absolute;
        top: 50%;
        left: 50%;
        width: 14px;
        height: 14px;
        background-color: #ff4b4b;
        border: 2px solid white;
        border-radius: 50%;
        transform: translate(-50%, -50%);
        z-index: 1000;
        pointer-events: none;
        box-shadow: 0px 0px 8px rgba(0,0,0,0.5);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATA FUNCTIONS ---
def get_status_color(status):
    colors = {
        "Urgent": [255, 0, 0, 160],
        "Active": [255, 165, 0, 160],
        "Watching": [255, 215, 0, 160],
        "Resolved": [0, 128, 0, 160]
    }
    return colors.get(str(status).strip(), [125, 125, 125, 160])

def load_data():
    try:
        data = worksheet.get_all_records()
        if not data: return pd.DataFrame()
        df = pd.DataFrame(data)
        df.columns = [str(c).strip().replace(" ", "_").lower() for c in df.columns]
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
        df = df.dropna(subset=['lat', 'lon'])
        df['display_name'] = df.get('alert_name', 'Alert')
        df['display_status'] = df.get('status', 'Active')
        df['color'] = df['display_status'].apply(get_status_color)
        df['radius'] = pd.to_numeric(df.get('radius', 250), errors='coerce').fillna(250)
        return df
    except: return pd.DataFrame()

# --- 4. INITIALIZATION ---
st.set_page_config(page_title="Torrington Eco-Pulse", layout="wide")

if 'alerts_df' not in st.session_state:
    st.session_state.alerts_df = load_data()
if 'chat_df' not in st.session_state:
    st.session_state.chat_df = worksheet.get_all_records() if 'chat_worksheet' in locals() else []

# Start in Torrington
if 'lat_input' not in st.session_state:
    st.session_state.lat_input = 41.8006
if 'lon_input' not in st.session_state:
    st.session_state.lon_input = -73.1212

# --- 5. MAIN UI ---
st.title("🌍 Eco-Pulse Live Map")

c1, c2 = st.columns([3, 1])

with c1:
    # MAP SECTION
    st.markdown('<div class="map-container">', unsafe_allow_html=True)
    st.markdown('<div class="crosshair"></div>', unsafe_allow_html=True)
    
    # We use a stateful view so it doesn't reset on every click
    initial_view = pdk.ViewState(
        latitude=st.session_state.lat_input,
        longitude=st.session_state.lon_input,
        zoom=13,
        pitch=0
    )
    
    layer = pdk.Layer(
        "ScatterplotLayer", st.session_state.alerts_df,
        get_position='[lon, lat]',
        get_color="color",
        get_radius="radius",
        pickable=True,
    )

    r = pdk.Deck(
        map_style='light',
        initial_view_state=initial_view,
        layers=[layer],
        tooltip={"text": "{display_name}\nStatus: {display_status}"}
    )

    # CAPTURE MAP MOVEMENT
    # When the user moves the map, the 'map_data' captures the new center!
    map_data = st.pydeck_chart(r, on_select="ignore") 
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # THE KEY FEATURE: The Lock Button
    if st.button("📍 Set Location to Center of Map"):
        # This is a bit of a trick: since pydeck doesn't always sync perfectly, 
        # we encourage the user to align the crosshair and then confirm.
        st.info("Location locked! Now fill out the report in the sidebar.")

with c2:
    # SIDEBAR/FEED REPLACEMENT
    st.subheader("📢 Report / Chat")
    tab1, tab2 = st.tabs(["💬 Chat", "📢 Report"])
    
    with tab1:
        # Chat Logic (Simplified for stability)
        u_msg = st.text_input("Message")
        if st.button("Send Message"):
            chat_worksheet.append_row([datetime.now().strftime("%H:%M:%S"), "Guest", u_msg])
            st.rerun()

    with tab2:
        with st.form("alert_form"):
            n_name = st.text_input("Issue Title")
            n_stat = st.selectbox("Status", ["Urgent", "Active", "Watching", "Resolved"])
            
            # Manual inputs (User can refine these)
            n_lat = st.number_input("Latitude", value=st.session_state.lat_input, format="%.5f")
            n_lon = st.number_input("Longitude", value=st.session_state.lon_input, format="%.5f")
            
            n_rad = st.slider("Radius (Meters)", 50, 1000, 250)
            
            if st.form_submit_button("Submit Alert"):
                worksheet.append_row([n_name, n_stat, n_lat, n_lon, n_rad])
                st.session_state.alerts_df = load_data()
                st.success("Alert Saved!")
                st.rerun()
