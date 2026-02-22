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
geolocator = Nominatim(user_agent="localsignal_pulse_global")

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

# --- 2. HELPERS ---
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

# --- 3. INITIALIZATION & ZIP PERSISTENCE ---
st.set_page_config(page_title="LocalSignal", layout="wide")

# Persistent Zip via URL
if "zip" in st.query_params:
    saved_zip = st.query_params["zip"]
else:
    saved_zip = ""

if 'map_center' not in st.session_state:
    st.session_state.map_center = {"lat": 41.8006, "lon": -73.1212}

df_all = load_data()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("📡 LocalSignal")
    
    # Neighborhood Zip Filter
    st.subheader("🏘️ My Neighborhood")
    user_zip = st.text_input("Zip Code", value=saved_zip, placeholder="e.g. 06790")
    
    if user_zip != saved_zip:
        st.query_params["zip"] = user_zip # Save to URL
    
    # Filtering Logic
    df_filtered = df_all
    if user_zip:
        try:
            zip_loc = geolocator.geocode(user_zip)
            if zip_loc:
                st.session_state.map_center = {"lat": zip_loc.latitude, "lon": zip_loc.longitude}
                # Show pins within roughly 10-15 miles
                df_filtered = df_all[
                    (df_all['lat'].between(zip_loc.latitude - 0.15, zip_loc.latitude + 0.15)) &
                    (df_all['lon'].between(zip_loc.longitude - 0.15, zip_loc.longitude + 0.15))
                ]
        except: pass

    tab1, tab2 = st.tabs(["📢 Report", "💬 Chat"])

    with tab1:
        st.subheader("New Signal")
        with st.form("report_form", clear_on_submit=True):
            n_name = st.text_input("Signal Name")
            n_street = st.text_input("Address/Street", placeholder="Include Zip for accuracy")
            n_stat = st.selectbox("Urgency", ["Urgent", "Active", "Watching", "Resolved"])
            n_size = st.select_slider("Radius", options=[50, 100, 250, 500, 1000], value=250)
            n_photo = st.file_uploader("Upload Photo", type=['jpg', 'jpeg', 'png'])
            
            if st.form_submit_button("Send Signal"):
                img_data = process_image(n_photo)
                try:
                    location = geolocator.geocode(n_street)
                    f_lat = location.latitude if location else st.session_state.map_center["lat"]
                    f_lon = location.longitude if location else st.session_state.map_center["lon"]
                except:
                    f_lat, f_lon = st.session_state.map_center["lat"], st.session_state.map_center["lon"]

                t_stamp = datetime.now().strftime("%I:%M %p")
                # Order: Name, Status, Lat, Lon, Radius, Street, Time, Image, Verifications
                worksheet.append_row([n_name, n_stat, f_lat, f_lon, n_size, n_street, t_stamp, img_data, 0])
                st.success("Signal Sent!")
                st.rerun()

    with tab2:
        u_msg = st.text_input("Message")
        if st.button("Send Message"):
            chat_worksheet.append_row([datetime.now().strftime("%H:%M"), "Guest", u_msg])
            st.rerun()

# --- 5. MAIN UI ---
st.title(f"🌍 LocalSignal {'| ' + user_zip if user_zip else ''}")

view_state = pdk.ViewState(
    latitude=st.session_state.map_center["lat"], 
    longitude=st.session_state.map_center["lon"], 
    zoom=13 if user_zip else 12
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
        img_html = f'<div style="height: 120px; overflow: hidden; border-radius: 5px; margin-bottom: 10px; background: #eee; display: flex; align-items: center; justify-content: center;">'
        if img_val and str(img_val).startswith('data:image'):
            img_html += f'<img src="{img_val}" style="width: 100%; height: 100%; object-fit: cover;">'
        else:
            img_html += '<span style="color: #aaa; font-size: 24px;">📷</span>'
        img_html += '</div>'
        
        with cols[i]:
            st.markdown(f"""
                <div style="border-left: 8px solid {style['hex']}; padding: 15px; border: 1px solid #ddd; border-radius: 10px; background-color: {style['bg']}; min-height: 380px; display: flex; flex-direction: column;">
                    {img_html}
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
                st.rerun()
else:
    st.info("No signals found in this neighborhood yet. Be the first to report!")
