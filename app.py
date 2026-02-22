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

# --- 1. SETUP & CONNECTION ---
geolocator = Nominatim(user_agent="localsignal_usa_v8")

try:
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1zEWu2R2ryMDrMMAih1RfU5yBTdNA4uwpR_zcZZ4DXlc/edit"
    sh = client.open_by_url(SHEET_URL)
    worksheet = sh.get_worksheet(0)
except Exception as e:
    st.error(f"Connection Error: {e}")

# --- 2. HELPERS ---

def safe_geocode(query):
    try:
        return geolocator.geocode(query, country_codes="us", timeout=10)
    except:
        return None

@st.cache_data(ttl=300)
def load_data():
    try:
        data = worksheet.get_all_records()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        # Standardize column names: lowercase, remove spaces
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Data Load Error: {e}")
        return pd.DataFrame()

@st.cache_data
def get_zip_boundary(zip_code):
    try:
        url = f"https://nominatim.openstreetmap.org/search?postalcode={zip_code}&country=USA&format=geojson&polygon_geojson=1"
        response = requests.get(url, timeout=10).json()
        return response['features'][0] if response.get('features') else None
    except:
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

# --- 3. INITIALIZATION ---
st.set_page_config(page_title="LocalSignal USA", layout="wide")
current_zip = st.query_params.get("zip", "")
if 'map_center' not in st.session_state:
    st.session_state.map_center = {"lat": 41.8006, "lon": -73.1212}

df_all = load_data()

# --- 4. DATA VALIDATION (The KeyError Fix) ---
required_cols = ['lat', 'lon', 'alert_name', 'status', 'radius', 'timestamp']
missing = [c for c in required_cols if c not in df_all.columns]

if not df_all.empty and missing:
    st.error(f"⚠️ Your Google Sheet is missing these columns: {', '.join(missing)}")
    st.info("Please ensure your Google Sheet headers are: Alert Name, Status, Lat, Lon, Radius, Street, Timestamp, Image, Verifications")
    st.stop()

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("📡 LocalSignal USA")
    user_zip = st.text_input("Neighborhood Zip", value=current_zip, placeholder="06790")
    
    if user_zip != current_zip:
        st.query_params["zip"] = user_zip
        st.cache_data.clear()

    df_filtered = df_all.copy()
    boundary_data = None
    
    if user_zip:
        boundary_data = get_zip_boundary(user_zip)
        zip_loc = safe_geocode(user_zip)
        if zip_loc:
            st.session_state.map_center = {"lat": zip_loc.latitude, "lon": zip_loc.longitude}
            if not df_all.empty:
                df_filtered = df_all[
                    (pd.to_numeric(df_all['lat']).between(zip_loc.latitude - 0.1, zip_loc.latitude + 0.1)) &
                    (pd.to_numeric(df_all['lon']).between(zip_loc.longitude - 0.1, zip_loc.longitude + 0.1))
                ].copy()

    with st.form("report_form", clear_on_submit=True):
        st.subheader("New Signal")
        n_name = st.text_input("Signal Name")
        n_street = st.text_input("Address")
        n_stat = st.selectbox("Urgency", ["Urgent", "Active", "Watching", "Resolved"])
        n_size = st.number_input("Radius (meters)", min_value=1, value=50)
        if st.form_submit_button("Send Signal"):
            loc = safe_geocode(n_street)
            if loc:
                t_stamp = datetime.now().strftime("%m/%d/%Y %I:%M %p")
                worksheet.append_row([n_name, n_stat, loc.latitude, loc.longitude, n_size, n_street, t_stamp, "", 0])
                st.cache_data
