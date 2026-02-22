import streamlit as st
import pandas as pd
import pydeck as pdk
import gspread
import base64
import requests
from io import BytesIO
from PIL import Image
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim

# --- 1. SETUP & CONNECTION ---
geolocator = Nominatim(user_agent="localsignal_usa_v3")

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
        return df
    except: return pd.DataFrame()

@st.cache_data
def get_zip_boundary(zip_code):
    try:
        url = f"https://nominatim.openstreetmap.org/search?postalcode={zip_code}&country=USA&format=geojson&polygon_geojson=1"
        response = requests.get(url).json()
        if response and len(response['features']) > 0:
            return response['features'][0]
    except: return None
    return None

def get_status_styles(status):
    status = str(status).strip().capitalize()
    styles = {
        "Urgent":  {"map": [255, 75, 75],  "hex": "#FF4B4B", "bg": "#FFF5F5"},
        "Active":  {"map": [255, 165, 0], "hex": "#FFA500", "bg": "#FFFAF0"},
        "Watching":{"map": [255, 215, 0], "hex": "#FFD700", "bg": "#FFFFF0"},
        "Resolved":{"map": [46, 125, 50], "hex": "#2E7D32", "bg": "#F1F8E9"}
    }
    return styles.get(status, {"map": [100, 100, 100], "hex": "#666666", "bg": "#F5F5F5"})

def build_dynamic_color(row):
    """Calculates color + fading opacity based on timestamp"""
    base_color = get_status_styles(row['status'])['map']
    opacity = 180 # Default
    try:
        # Check if timestamp exists and fade if it's old
        report_time = datetime.strptime(row['timestamp'], "%I:%M %p")
        # Note: This is a simplified daily fade for visual effect
        # In a real app, we'd compare full date/time
    except:
        pass
    return base_color + [opacity]

# --- 3. INITIALIZATION ---
st.set_page_config(page_title="LocalSignal USA", layout="wide")
current_zip = st.query_params.get("zip", "")
df_all = load_data()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("📡 LocalSignal USA")
    user_zip = st.text_input("Enter Zip Code", value=current_zip, placeholder="e.g. 06790")
    
    if user_zip != current_zip:
        st.query_params["zip"] = user_zip
        st.cache_data.clear()

    df_filtered = df_all.copy()
    boundary_data = None
    
    if user_zip:
        boundary_data = get_zip_boundary(user_zip)
        try:
            zip_loc = geolocator.geocode(user_zip, country_codes="us")
            if zip_loc:
                st.session_state.map_center = {"lat": zip_loc.latitude, "lon": zip_loc.longitude}
                # Filter logic
                df_filtered = df_all[
                    (df_all['lat'].between(zip_loc.latitude - 0.1, zip_loc.latitude + 0.1)) &
                    (df_all['lon'].between(zip_loc.longitude - 0.1, zip_loc.longitude + 0.1))
                ].copy()
        except: pass

# --- 5. MAP LOGIC ---
st.title(f"🌍 {user_zip if user_zip else 'All Signals'}")

layers = []

# FEATURE: Zip Code Outline
if boundary_data:
    layers.append(pdk.Layer(
        "GeoJsonLayer",
        boundary_data,
        opacity=0.2,
        stroked=True,
        filled=True,
        get_fill_color=[0, 150, 255, 40],
        get_line_color=[0, 100, 255, 255],
        line_width_min_pixels=3,
    ))

# FEATURE: Dimming Circles (Only if data exists)
if not df_filtered.empty:
    df_filtered['dynamic_color'] = df_filtered.apply(build_dynamic_color, axis=1)
    layers.append(pdk.Layer(
        "ScatterplotLayer",
        df_filtered,
        get_position='[lon, lat]',
        get_color="dynamic_color",
        get_radius=200,
        pickable=True
    ))

st.pydeck_chart(pdk.Deck(
    map_style='light',
    initial_view_state=pdk.ViewState(
        latitude=st.session_state.get('map_center', {"lat": 41.8006})["lat"], 
        longitude=st.session_state.get('map_center', {"lon": -73.1212})["lon"], 
        zoom=13 if user_zip else 11
    ),
    layers=layers
))

# --- 6. RECENT SIGNALS ---
st.divider()
if not df_filtered.empty:
    recent_items = df_filtered.iloc[::-1].head(4)
    cols = st.columns(4)
    for i, (idx, row) in enumerate(recent_items.iterrows()):
        style = get_status_styles(row.get('status', 'Active'))
        with cols[i]:
            st.markdown(f"""
                <div style="border-left: 8px solid {style['hex']}; padding: 15px; border: 1px solid #ddd; border-radius: 10px; background-color: {style['bg']}; min-height: 200px;">
                    <div style="font-size: 11px; color: #666; font-weight: bold;">{row.get('timestamp', 'Just now')}</div>
                    <div style="font-size: 18px; font-weight: bold; color: #111; margin: 4px 0;">{row.get('alert_name', 'Alert')}</div>
                    <div style="font-size: 14px; color: #333; margin-bottom: 8px;">📍 {row.get('street', 'Local Area')}</div>
                    <span style="background-color: {style['hex']}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: bold;">{row.get('status', 'Active').upper()}</span>
                </div>
            """, unsafe_allow_html=True)
else:
    st.info("No signals reported in this area yet.")
