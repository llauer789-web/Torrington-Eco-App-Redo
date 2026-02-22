import streamlit as st
import pandas as pd
import pydeck as pdk
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from geopy.geocoders import Nominatim

# --- 1. SETUP & CONNECTION ---
geolocator = Nominatim(user_agent="torrington_eco_pulse")

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

# --- 2. THE COLOR SYSTEM (Fixed for Clarity) ---
def get_status_styles(status):
    status = str(status).strip().capitalize()
    styles = {
        "Urgent":  {"map": [255, 75, 75, 180],  "hex": "#FF4B4B", "bg": "#FFF5F5"},
        "Active":  {"map": [255, 165, 0, 180], "hex": "#FFA500", "bg": "#FFFAF0"},
        "Watching":{"map": [255, 215, 0, 180], "hex": "#FFD700", "bg": "#FFFFF0"},
        "Resolved":{"map": [46, 125, 50, 180], "hex": "#2E7D32", "bg": "#F1F8E9"}
    }
    return styles.get(status, {"map": [100, 100, 100, 180], "hex": "#666666", "bg": "#F5F5F5"})

# --- 3. DATA LOADING ---
def load_data():
    try:
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        df.columns = [str(c).strip().replace(" ", "_").lower() for c in df.columns]
        
        # Ensure coordinates and size (radius) are numeric
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce').fillna(41.8006)
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce').fillna(-73.1212)
        df['radius'] = pd.to_numeric(df.get('radius', 250), errors='coerce').fillna(250)
        
        # Map styles
        df['map_color'] = df['status'].apply(lambda x: get_status_styles(x)['map'])
        return df
    except: return pd.DataFrame()

# --- 4. INITIALIZATION ---
st.set_page_config(page_title="Torrington Eco-Pulse", layout="wide")
if 'map_center' not in st.session_state:
    st.session_state.map_center = {"lat": 41.8006, "lon": -73.1212}

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("🚨 Torrington Pulse")
    tab1, tab2 = st.tabs(["📢 Report", "💬 Chat"])

    with tab1:
        st.subheader("New Report")
        with st.form("report_form", clear_on_submit=True):
            n_name = st.text_input("What's happening?", placeholder="e.g. Flooded Street")
            n_street = st.text_input("Address/Street Name", placeholder="e.g. 50 Main St")
            n_stat = st.selectbox("Urgency Level", ["Urgent", "Active", "Watching", "Resolved"])
            n_size = st.select_slider("Size of Area (Radius)", options=[50, 100, 250, 500, 1000], value=250)
            
            if st.form_submit_button("Submit Alert"):
                try:
                    # Attempt to find location via street name
                    location = geolocator.geocode(f"{n_street}, Torrington, CT")
                    f_lat = location.latitude if location else st.session_state.map_center["lat"]
                    f_lon = location.longitude if location else st.session_state.map_center["lon"]
                except:
                    f_lat, f_lon = st.session_state.map_center["lat"], st.session_state.map_center["lon"]

                t_stamp = datetime.now().strftime("%I:%M %p")
                # Add to Sheet: Name, Status, Lat, Lon, Radius, Street, Time
                worksheet.append_row([n_name, n_stat, f_lat, f_lon, n_size, n_street, t_stamp])
                st.success("Reported!")
                st.rerun()

    with tab2:
        # Chat Logic
        u_msg = st.text_input("Message")
        if st.button("Send"):
            chat_worksheet.append_row([datetime.now().strftime("%H:%M"), "Guest", u_msg])
            st.rerun()

# --- 6. MAIN MAP ---
st.title("🌍 Eco-Pulse Live Map")
df_map = load_data()

# Render the Map
view_state = pdk.ViewState(latitude=41.8006, longitude=-73.1212, zoom=13)
layer = pdk.Layer(
    "ScatterplotLayer", df_map,
    get_position='[lon, lat]',
    get_color="map_color",
    get_radius="radius",
    pickable=True
)

st.pydeck_chart(pdk.Deck(map_style='light', initial_view_state=view_state, layers=[layer], tooltip={"text": "{alert_name}\nStatus: {status}"}))

# --- 7. RECENT ALERTS (The "Better" State) ---
st.divider()
st.subheader("📍 Recent Activity")

if not df_map.empty:
    recent_items = df_map.iloc[::-1].head(4)
    cols = st.columns(4)
    
    for i, (idx, row) in enumerate(recent_items.iterrows()):
        style = get_status_styles(row.get('status', 'Active'))
        with cols[i]:
            st.markdown(f"""
                <div style="border-left: 8px solid {style['hex']}; padding: 15px; border: 1px solid #ddd; border-radius: 10px; background-color: {style['bg']}; min-height: 140px;">
                    <div style="font-size: 11px; color: #666; font-weight: bold;">{row.get('timestamp', 'Just now')}</div>
                    <div style="font-size: 18px; font-weight: bold; color: #111; margin: 4px 0;">{row.get('alert_name', 'Alert')}</div>
                    <div style="font-size: 14px; color: #333; margin-bottom: 8px;">📍 {row.get('street', 'Torrington')}</div>
                    <span style="background-color: {style['hex']}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: bold;">{row.get('status', 'Active').upper()}</span>
                </div>
            """, unsafe_allow_html=True)
