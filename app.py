import streamlit as st
import pandas as pd
import pydeck as pdk
import gspread
import base64
from io import BytesIO
from PIL import Image
from google.oauth2.service_account import Credentials
from datetime import datetime
from geopy.geocoders import Nominatim

# --- 1. SETUP & CONNECTION ---
geolocator = Nominatim(user_agent="localsignal_usa_v1")

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
        df['radius'] = pd.to_numeric(df.get('radius', 250), errors='coerce').fillna(250)
        df['verifications'] = pd.to_numeric(df.get('verifications', 0), errors='coerce').fillna(0).astype(int)
        df['map_color'] = df['status'].apply(lambda x: get_status_styles(x)['map'])
        return df
    except: return pd.DataFrame()

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

def process_image(uploaded_file):
    if uploaded_file is not None:
        img = Image.open(uploaded_file)
        img.thumbnail((400, 400)) 
        buffered = BytesIO()
        img.save(buffered, format="JPEG", quality=70)
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return f"data:image/jpeg;base64,{img_str}"
    return ""

# --- 3. INITIALIZATION ---
st.set_page_config(page_title="LocalSignal USA", layout="wide")

if "zip" in st.query_params:
    saved_zip = st.query_params["zip"]
else:
    saved_zip = ""

if 'map_center' not in st.session_state:
    st.session_state.map_center = {"lat": 41.8006, "lon": -73.1212}

df_all = load_data()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("📡 LocalSignal USA")
    
    st.subheader("🏘️ My Neighborhood")
    user_zip = st.text_input("US Zip Code", value=saved_zip, placeholder="e.g. 06790")
    
    df_filtered = df_all
    if user_zip:
        if user_zip != saved_zip:
            st.query_params["zip"] = user_zip
            st.cache_data.clear()

        try:
            zip_loc = geolocator.geocode(user_zip, country_codes="us")
            if zip_loc:
                st.session_state.map_center = {"lat": zip_loc.latitude, "lon": zip_loc.longitude}
                df_filtered = df_all[
                    (df_all['lat'].between(zip_loc.latitude - 0.15, zip_loc.latitude + 0.15)) &
                    (df_all['lon'].between(zip_loc.longitude - 0.15, zip_loc.longitude + 0.15))
                ]
            else:
                st.warning("Invalid US Zip Code.")
        except: pass

    tab1, tab2 = st.tabs(["📢 Report", "💬 Chat"])

    with tab1:
        st.subheader("New Signal")
        with st.form("report_form", clear_on_submit=True):
            n_name = st.text_input("Signal Name")
            n_street = st.text_input("US Address", placeholder="e.g. 123 Main St, 06790")
            n_stat = st.selectbox("Urgency", ["Urgent", "Active", "Watching", "Resolved"])
            n_size = st.select_slider("Radius", options=[50, 100, 250, 500, 1000], value=250)
            n_photo = st.file_uploader("Upload Photo", type=['jpg', 'jpeg', 'png'])
            
            if st.form_submit_button("Send Signal"):
                img_data = process_image(n_photo)
                try:
                    location = geolocator.geocode(n_street, country_codes="us")
                    if location:
                        f_lat, f_lon = location.latitude, location.longitude
                        worksheet.append_row([n_name, n_stat, f_lat, f_lon, n_size, n_street, datetime.now().strftime("%I:%M %p"), img_data, 0])
                        st.cache_data.clear()
                        st.success("Signal Sent!")
                        st.rerun()
                    else:
                        st.error("Address not found in USA.")
                except:
                    st.error("Geocoding Error.")

    with tab2:
        u_msg = st.text_input("Message")
        if st.button("Send Message"):
            chat_worksheet.append_row([datetime.now().strftime("%H:%M"), "Guest", u_msg])
            st.rerun()

# --- 5. MAIN UI ---
st.title(f"🌍 LocalSignal USA {'| ' + user_zip if user_zip else ''}")

view_state = pdk.ViewState(
    latitude=st.session_state.map_center["lat"], 
    longitude=st.session_state.map_center["lon"], 
    zoom=13 if user_zip else 11
)

layer = pdk.Layer(
    "ScatterplotLayer", df_filtered,
    get_position='[lon, lat]',
    get_color="map_color",
    get_radius="radius",
    pickable=True
)

st.pydeck_chart(pdk.Deck(map_style='light', initial_view_state=view_state, layers=[layer]))

# --- 6. RECENT SIGNALS ---
st.divider()
st.subheader(f"📍 Recent Signals {user_zip}")

if not df_filtered.empty:
    recent_items = df_filtered.iloc[::-1].head(4)
    cols = st.columns(4)
    
    for i, (idx, row) in enumerate(recent_items.iterrows()):
        style = get_status_styles(row.get('status', 'Active'))
        img_val = row.get('image', '')
        
        # Build image HTML safely
        img_display = '<div style="height: 120px; background: #eee; border-radius: 5px; margin-bottom: 10px; display: flex; align-items: center; justify-content: center;"><span style="color: #aaa; font-size: 24px;">📷</span></div>'
        if img_val and str(img_val).startswith('data:image'):
            img_display = f'<div style="height: 120px; overflow: hidden; border-radius: 5px; margin-bottom: 10px;"><img src="{img_val}" style="width: 100%; height: 100%; object-fit: cover;"></div>'
        
        with cols[i]:
            st.markdown(f"""
                <div style="border-left: 8px solid {style['hex']}; padding: 15px; border: 1px solid #ddd; border-radius: 10px; background-color: {style['bg']}; min-height: 380px; display: flex; flex-direction: column;">
                    {img_display}
                    <div style="font-size: 11px; color: #666; font-weight: bold;">{row.get('timestamp', 'Just now')}</div>
                    <div style="font-size: 18px; font-weight: bold; color: #111; margin: 4px 0;">{row.get('alert_name', 'Alert')}</div>
                    <div style="font-size: 14px; color: #333; margin-bottom: 8px; flex-grow: 1;">📍 {row.get('street', 'Local Area')}</div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px;">
                        <span style="background-color: {style['hex']}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: bold;">{row.get('status', 'Active').upper()}</span>
                        <span style="font-size: 12px; color: #555;">✅ {row.get('verifications', 0)}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            if st.button(f"Verify #{i+1}", key=f"v_{idx}"):
                row_to_update = int(idx) + 2 
                current_val = int(row.get('verifications', 0))
                worksheet.update_cell(row_to_update, 9, current_val + 1)
                st.cache_data.clear()
                st.rerun()
else:
    st.info("No neighborhood signals found yet.")
