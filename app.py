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
geolocator = Nominatim(user_agent="localsignal_usa_v6")

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
        df['radius'] = pd.to_numeric(df.get('radius', 50), errors='coerce').fillna(50)
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

def get_status_styles(status):
    status = str(status).strip().capitalize()
    styles = {
        "Urgent":  {"map": [255, 75, 75],  "hex": "#FF4B4B", "bg": "#FFF5F5"},
        "Active":  {"map": [255, 165, 0], "hex": "#FFA500", "bg": "#FFFAF0"},
        "Watching":{"map": [255, 215, 0], "hex": "#FFD700", "bg": "#FFFFF0"},
        "Resolved":{"map": [46, 125, 50], "hex": "#2E7D32", "bg": "#F1F8E9"}
    }
    return styles.get(status, {"map": [100, 100, 100], "hex": "#666666", "bg": "#F5F5F5"})

def process_image(uploaded_file):
    if uploaded_file is not None:
        img = Image.open(uploaded_file)
        img.thumbnail((400, 400)) 
        buffered = BytesIO()
        img.save(buffered, format="JPEG", quality=70)
        return f"data:image/jpeg;base64,{base64.b64encode(buffered.getvalue()).decode()}"
    return ""

# --- 3. INITIALIZATION ---
st.set_page_config(page_title="LocalSignal USA", layout="wide")
current_zip = st.query_params.get("zip", "")
if 'map_center' not in st.session_state:
    st.session_state.map_center = {"lat": 41.8006, "lon": -73.1212}

df_all = load_data()

# --- 4. SIDEBAR ---
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
        try:
            zip_loc = geolocator.geocode(user_zip, country_codes="us")
            if zip_loc:
                st.session_state.map_center = {"lat": zip_loc.latitude, "lon": zip_loc.longitude}
                df_filtered = df_all[
                    (df_all['lat'].between(zip_loc.latitude - 0.15, zip_loc.latitude + 0.15)) &
                    (df_all['lon'].between(zip_loc.longitude - 0.15, zip_loc.longitude + 0.15))
                ].copy()
        except: pass

    tab1, tab2 = st.tabs(["📢 Report", "💬 Chat"])
    with tab1:
        with st.form("report_form", clear_on_submit=True):
            n_name = st.text_input("Signal Name")
            n_street = st.text_input("Address", placeholder="Include Zip")
            n_stat = st.selectbox("Urgency", ["Urgent", "Active", "Watching", "Resolved"])
            n_size = st.number_input("Signal Radius (meters)", min_value=1, max_value=2000, value=50, step=1)
            n_photo = st.file_uploader("Upload Photo", type=['jpg', 'png'])
            if st.form_submit_button("Send Signal"):
                img_data = process_image(n_photo)
                loc = geolocator.geocode(n_street, country_codes="us")
                if loc:
                    t_stamp = datetime.now().strftime("%m/%d/%Y %I:%M %p")
                    worksheet.append_row([n_name, n_stat, loc.latitude, loc.longitude, n_size, n_street, t_stamp, img_data, 0])
                    st.cache_data.clear()
                    st.rerun()

# --- 5. MAIN MAP ---
st.title(f"🌍 LocalSignal: {user_zip if user_zip else 'USA'}")
layers = []

if boundary_data:
    layers.append(pdk.Layer("GeoJsonLayer", boundary_data, opacity=0.1, stroked=True, filled=True, get_fill_color=[0, 150, 255, 30], get_line_color=[0, 100, 255, 200], line_width_min_pixels=2))

if not df_filtered.empty:
    df_filtered['color'] = df_filtered.apply(lambda r: get_status_styles(r['status'])['map'] + [180], axis=1)
    layers.append(pdk.Layer(
        "ScatterplotLayer",
        df_filtered,
        get_position='[lon, lat]',
        get_color="color",
        get_radius="radius",
        radius_units="'meters'",
        pickable=True
    ))

st.pydeck_chart(pdk.Deck(map_style='light', initial_view_state=pdk.ViewState(latitude=st.session_state.map_center["lat"], longitude=st.session_state.map_center["lon"], zoom=13), layers=layers))

# --- 6. RECENT SIGNALS (RE-RESTORED) ---
st.divider()
st.subheader(f"📍 Recent Neighborhood Signals {user_zip}")

if not df_filtered.empty:
    # Sort by the spreadsheet order (most recent at bottom of sheet = top of app)
    recent = df_filtered.iloc[::-1].head(4)
    cols = st.columns(4)
    
    for i, (idx, row) in enumerate(recent.iterrows()):
        style = get_status_styles(row.get('status', 'Active'))
        img_val = row.get('image', '')
        
        # Build image HTML
        img_html = f'<div style="height:140px; background:#eee; border-radius:8px; margin-bottom:12px; overflow:hidden;">'
        if img_val and str(img_val).startswith('data:image'):
            img_html += f'<img src="{img_val}" style="width:100%; height:100%; object-fit:cover;">'
        else:
            img_html += '<div style="width:100%; height:100%; display:flex; align-items:center; justify-content:center; color:#bbb; font-size:24px;">📷</div>'
        img_html += '</div>'
        
        with cols[i]:
            st.markdown(f"""
                <div style="border-left: 8px solid {style['hex']}; padding: 15px; border: 1px solid #ddd; border-radius: 10px; background-color: {style['bg']}; min-height: 420px; display: flex; flex-direction: column;">
                    {img_html}
                    <div style="font-size: 11px; color: #666; font-weight: bold;">📅 {row.get('timestamp', 'Just now')}</div>
                    <div style="font-size: 18px; font-weight: bold; color: #111; margin: 6px 0;">{row.get('alert_name', 'Alert')}</div>
                    <div style="font-size: 14px; color: #444; margin-bottom: 8px; flex-grow: 1;">📍 {row.get('street', 'Local Area')}</div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 12px; border-top: 1px solid #eee; padding-top: 10px;">
                        <span style="background-color: {style['hex']}; color: white; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: bold;">{row.get('status', 'Active').upper()}</span>
                        <span style="font-size: 12px; font-weight: bold; color: #555;">✅ {row.get('verifications', 0)} Verified</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            if st.button(f"Verify Signal #{i+1}", key=f"v_btn_{idx}"):
                worksheet.update_cell(int(idx) + 2, 9, int(row.get('verifications', 0)) + 1)
                st.cache_data.clear()
                st.rerun()
else:
    st.info("No active neighborhood signals.")
