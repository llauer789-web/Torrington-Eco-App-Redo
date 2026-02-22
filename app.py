import streamlit as st
import pandas as pd
import pydeck as pdk
import gspread
import base64
import requests
import time
from io import BytesIO
from PIL import Image
from google.oauth2.service_account import Credentials
from datetime import datetime
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

# --- 1. SETUP ---
geolocator = Nominatim(user_agent="localsignal_usa_v11_streetmode")

def get_gspread_client():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Credentials Error: {e}")
        return None

# --- 2. THE ENGINE (Street to Coordinates) ---

def safe_geocode(query):
    """Handles the conversion of Street Names to Lat/Lon"""
    if not query: return None
    try:
        # We append 'USA' to ensure we stay in the country
        return geolocator.geocode(f"{query}, USA", timeout=10)
    except:
        return None

@st.cache_data(ttl=300)
def load_data_from_street(sheet_url):
    client = get_gspread_client()
    if not client: return pd.DataFrame()
    try:
        sh = client.open_by_url(sheet_url)
        data = sh.get_worksheet(0).get_all_records()
        df = pd.DataFrame(data)
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        
        # We must create lat/lon columns since they aren't in the sheet
        lats, lons = [], []
        
        with st.spinner("Mapping street addresses..."):
            for street in df['street']:
                loc = safe_geocode(street)
                if loc:
                    lats.append(loc.latitude)
                    lons.append(loc.longitude)
                else:
                    lats.append(None)
                    lons.append(None)
        
        df['lat'] = lats
        df['lon'] = lons
        df['radius'] = pd.to_numeric(df.get('radius', 50), errors='coerce').fillna(50)
        df['verifications'] = pd.to_numeric(df.get('verifications', 0), errors='coerce').fillna(0)
        
        # Drop rows that couldn't be geocoded
        return df.dropna(subset=['lat', 'lon'])
    except Exception as e:
        st.error(f"Error processing streets: {e}")
        return pd.DataFrame()

# --- 3. UI INITIALIZATION ---
st.set_page_config(page_title="LocalSignal USA", layout="wide")
SHEET_URL = "https://docs.google.com/spreadsheets/d/1zEWu2R2ryMDrMMAih1RfU5yBTdNA4uwpR_zcZZ4DXlc/edit"

current_zip = st.query_params.get("zip", "")
df_all = load_data_from_street(SHEET_URL)

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("📡 LocalSignal USA")
    user_zip = st.text_input("Neighborhood Zip", value=current_zip)
    
    if user_zip != current_zip:
        st.query_params["zip"] = user_zip
        st.rerun()

    df_filtered = df_all
    boundary_data = None
    
    if user_zip and not df_all.empty:
        # Get Zip Boundary
        try:
            boundary_url = f"https://nominatim.openstreetmap.org/search?postalcode={user_zip}&country=USA&format=geojson&polygon_geojson=1"
            boundary_data = requests.get(boundary_url).json()['features'][0]
        except: pass
        
        zip_loc = safe_geocode(user_zip)
        if zip_loc:
            st.session_state.map_center = {"lat": zip_loc.latitude, "lon": zip_loc.longitude}
            df_filtered = df_all[
                (df_all['lat'].between(zip_loc.latitude - 0.1, zip_loc.latitude + 0.1)) &
                (df_all['lon'].between(zip_loc.longitude - 0.1, zip_loc.longitude + 0.1))
            ]

    tab1, tab2 = st.tabs(["📢 Report", "💬 Chat"])
    with tab1:
        with st.form("new_report"):
            n_name = st.text_input("Signal Name")
            n_street = st.text_input("Full Street Address (inc. Zip)")
            n_stat = st.selectbox("Status", ["Urgent", "Active", "Watching", "Resolved"])
            n_rad = st.number_input("Radius", min_value=1, value=50)
            if st.form_submit_button("Send"):
                t = datetime.now().strftime("%m/%d/%Y %I:%M %p")
                # Append to sheet (Note: no lat/lon columns here!)
                client = get_gspread_client()
                client.open_by_url(SHEET_URL).get_worksheet(0).append_row([n_name, n_stat, n_rad, n_street, t, "", 0])
                st.cache_data.clear()
                st.rerun()

# --- 5. MAP & RECENT CARDS ---
st.title(f"🌍 LocalSignal: {user_zip if user_zip else 'Neighborhood'}")

if not df_filtered.empty:
    layers = []
    if boundary_data:
        layers.append(pdk.Layer("GeoJsonLayer", boundary_data, opacity=0.1, stroked=True, filled=True, get_fill_color=[0, 150, 255, 30], get_line_color=[0, 100, 255, 200], line_width_min_pixels=2))
    
    # Circles (The Dots)
    df_filtered['color'] = [[255, 75, 75, 180] if "Urgent" in str(s) else [255, 165, 0, 180] for s in df_filtered['status']]
    layers.append(pdk.Layer("ScatterplotLayer", df_filtered, get_position='[lon, lat]', get_color="color", get_radius="radius", radius_units="'meters'", pickable=True))

    st.pydeck_chart(pdk.Deck(map_style='light', initial_view_state=pdk.ViewState(latitude=st.session_state.get('map_center', {"lat": 41.8006})["lat"], longitude=st.session_state.get('map_center', {"lon": -73.1212})["lon"], zoom=13), layers=layers))

    # RESTORED RECENT SIGNALS
    st.divider()
    st.subheader("📍 Recent Signals")
    cols = st.columns(4)
    recent = df_filtered.iloc[::-1].head(4)
    
    for i, (idx, row) in enumerate(recent.iterrows()):
        with cols[i]:
            st.markdown(f"""
                <div style="border:1px solid #ddd; padding:15px; border-radius:10px; background:#fff;">
                    <p style="font-size:10px; color:gray;">📅 {row.get('timestamp')}</p>
                    <h4 style="margin:0;">{row.get('alert_name')}</h4>
                    <p style="font-size:12px;">📍 {row.get('street')}</p>
                    <p><b>{row.get('status')}</b> | ✅ {int(row.get('verifications', 0))}</p>
                </div>
            """, unsafe_allow_html=True)
            if st.button(f"Verify #{i+1}", key=f"v_{idx}"):
                client = get_gspread_client()
                # Assuming Verifications is the 7th column in your new setup
                client.open_by_url(SHEET_URL).get_worksheet(0).update_cell(int(idx) + 2, 7, int(row.get('verifications', 0)) + 1)
                st.cache_data.clear()
                st.rerun()
