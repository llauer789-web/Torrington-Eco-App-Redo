import streamlit as st
import pandas as pd
import pydeck as pdk
import gspread
import base64
import requests
from io import BytesIO
from PIL import Image
from google.oauth2.service_account import Credentials
from datetime import datetime
from geopy.geocoders import Nominatim

# --- 1. SETUP & CONNECTION ---
geolocator = Nominatim(user_agent="localsignal_usa_v2")

try:
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1zEWu2R2ryMDrMMAih1RfU5yBTdNA4uwpR_zcZZ4DXlc/edit"
    sh = client.open_by_url(SHEET_URL)
    worksheet = sh.get_worksheet(0)
    chat_worksheet = sh.worksheet("Chat")
except Exception as e:
    st.error(f"Connection Error: {e}")

# --- 2. CACHED HELPERS ---

@st.cache_data(ttl=300)
def load_data():
    try:
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        df.columns = [str(c).strip().replace(" ", "_").lower() for c in df.columns]
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce').fillna(41.8006)
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce').fillna(-73.1212)
        df['verifications'] = pd.to_numeric(df.get('verifications', 0), errors='coerce').fillna(0).astype(int)
        df['map_color'] = df['status'].apply(lambda x: get_status_styles(x)['map'])
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=60) # Fast refresh for chat
def load_chat(target_zip):
    try:
        data = chat_worksheet.get_all_records()
        df = pd.DataFrame(data)
        df.columns = [str(c).strip().lower() for c in df.columns]
        if 'zipcode' in df.columns:
            # Filter chat by Zip
            return df[df['zipcode'].astype(str) == str(target_zip)]
        return df
    except: return pd.DataFrame()

@st.cache_data
def get_zip_boundary(zip_code):
    """Fetches GeoJSON boundary for a US Zip Code"""
    try:
        # Using a public API for US boundaries
        url = f"https://nominatim.openstreetmap.org/search?postalcode={zip_code}&country=USA&format=geojson&polygon_geojson=1"
        response = requests.get(url).json()
        if response['features']:
            return response['features'][0]
    except: return None
    return None

@st.cache_data
def get_status_styles(status):
    status = str(status).strip().capitalize()
    styles = {
        "Urgent":  {"map": [255, 75, 75, 180],  "hex": "#FF4B4B", "bg": "#FFF5F5"},
        "Active":  {"map": [255, 165, 0, 180], "hex": "#FFA500", "bg": "#FFFAF0"},
        "Watching":{"map": [255, 215, 0, 180], "hex": "#FFD700", "bg": "#FFFFF0"},
        "Resolved":{"map": [46, 125, 50, 180], "hex": "#2E7D32", "bg": "#F1F8E9"}
    }
    return styles.get(status, {"map": [100, 100, 100, 180], "hex": "#666666", "bg": "#F5F5F5"})

# --- 3. INITIALIZATION ---
st.set_page_config(page_title="LocalSignal USA", layout="wide")

current_zip = st.query_params.get("zip", "")
if 'map_center' not in st.session_state:
    st.session_state.map_center = {"lat": 41.8006, "lon": -73.1212}

df_all = load_data()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("📡 LocalSignal USA")
    
    st.subheader("🏘️ Neighborhood Lock")
    user_zip = st.text_input("Enter your Zip", value=current_zip, placeholder="06790")
    
    if user_zip != current_zip:
        st.query_params["zip"] = user_zip
        st.cache_data.clear()

    df_filtered = df_all
    boundary_data = None
    
    if user_zip:
        boundary_data = get_zip_boundary(user_zip)
        try:
            zip_loc = geolocator.geocode(user_zip, country_codes="us")
            if zip_loc:
                st.session_state.map_center = {"lat": zip_loc.latitude, "lon": zip_loc.longitude}
                df_filtered = df_all[
                    (df_all['lat'].between(zip_loc.latitude - 0.1, zip_loc.latitude + 0.1)) &
                    (df_all['lon'].between(zip_loc.longitude - 0.1, zip_loc.longitude + 0.1))
                ]
        except: pass

    tab1, tab2 = st.tabs(["📢 Report", "💬 Chat"])

    with tab1:
        st.subheader("New Signal")
        with st.form("report_form", clear_on_submit=True):
            n_name = st.text_input("Signal Name")
            n_street = st.text_input("US Address")
            n_stat = st.selectbox("Urgency", ["Urgent", "Active", "Watching", "Resolved"])
            n_photo = st.file_uploader("Upload Photo", type=['jpg','png'])
            if st.form_submit_button("Send Signal"):
                # (Logic from previous versions for geocoding and uploading)
                st.success("Signal Sent!")
                st.rerun()

    with tab2:
        if user_zip:
            st.subheader(f"💬 {user_zip} Chat")
            chat_df = load_chat(user_zip)
            if not chat_df.empty:
                for _, msg in chat_df.tail(10).iterrows():
                    st.caption(f"**{msg.get('user', 'Guest')}** ({msg.get('time', '')})")
                    st.info(msg.get('message', ''))
            
            with st.form("chat_form", clear_on_submit=True):
                u_msg = st.text_input("Message neighborhood...")
                if st.form_submit_button("Send"):
                    chat_worksheet.append_row([datetime.now().strftime("%H:%M"), "Guest", u_msg, user_zip])
                    st.cache_data.clear()
                    st.rerun()
        else:
            st.warning("Enter a Zip Code to join the local chat.")

# --- 5. MAIN UI ---
st.title(f"🌍 {user_zip if user_zip else 'LocalSignal USA'}")

# Map Layers
layers = []

# Layer 1: Zip Code Boundary Outline
if boundary_data:
    layers.append(pdk.Layer(
        "GeoJsonLayer",
        boundary_data,
        opacity=0.2,
        stroked=True,
        filled=True,
        get_fill_color=[0, 150, 255, 50],
        get_line_color=[0, 100, 255, 255],
        line_width_min_pixels=3,
    ))

# Layer 2: Signals
layers.append(pdk.Layer(
    "ScatterplotLayer", df_filtered,
    get_position='[lon, lat]',
    get_color="map_color",
    get_radius=150,
    pickable=True
))

st.pydeck_chart(pdk.Deck(map_style='light', initial_view_state=pdk.ViewState(
    latitude=st.session_state.map_center["lat"], 
    longitude=st.session_state.map_center["lon"], 
    zoom=13 if user_zip else 11
), layers=layers))

# (Recent Signals section remains the same)
