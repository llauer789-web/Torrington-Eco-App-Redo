import streamlit as st
import pandas as pd
import pydeck as pdk
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from geopy.geocoders import Nominatim  # For turning addresses into coordinates

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

# --- 2. CSS FOR CROSSHAIR ---
st.markdown("""
    <style>
    .map-wrapper { position: relative; }
    .map-crosshair {
        position: absolute; top: 50%; left: 50%;
        width: 24px; height: 24px;
        border: 2px solid #FF4B4B; border-radius: 50%;
        transform: translate(-50%, -50%); z-index: 999;
        pointer-events: none;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. HELPER FUNCTIONS ---
def load_data():
    try:
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        df.columns = [str(c).strip().replace(" ", "_").lower() for c in df.columns]
        # Failsafe for missing columns
        for col in ['lat', 'lon', 'status', 'alert_name', 'street', 'timestamp']:
            if col not in df.columns: df[col] = 0 if col in ['lat', 'lon'] else "N/A"
        return df
    except: return pd.DataFrame()

# --- 4. INITIALIZATION ---
st.set_page_config(page_title="Torrington Eco-Pulse", layout="wide")
if 'map_center' not in st.session_state:
    st.session_state.map_center = {"lat": 41.8006, "lon": -73.1212}

# --- 5. SIDEBAR (The User-Friendly Reporting) ---
with st.sidebar:
    st.title("🚨 Torrington Pulse")
    tab1, tab2 = st.tabs(["📢 Report Issue", "💬 Chat"])

    with tab1:
        st.subheader("How to Report:")
        report_method = st.radio("Choose Method:", ["Type Address", "Use Map Center"])
        
        with st.form("report_form", clear_on_submit=True):
            n_name = st.text_input("What is the issue?", placeholder="e.g. Huge Pothole")
            n_status = st.selectbox("Status", ["Urgent", "Active", "Watching", "Resolved"])
            
            final_lat, final_lon, final_street = 0.0, 0.0, ""

            if report_method == "Type Address":
                n_street = st.text_input("Street Address", placeholder="e.g. 100 Main St, Torrington")
                st.caption("We'll find the coordinates for you!")
            else:
                st.info("The red circle in the center of the map is your target.")
                n_street = st.text_input("Verify Street Name", placeholder="e.g. East Main St")
            
            if st.form_submit_button("Submit to Map"):
                if report_method == "Type Address" and n_street:
                    try:
                        location = geolocator.geocode(f"{n_street}, Torrington, CT")
                        if location:
                            final_lat, final_lon, final_street = location.latitude, location.longitude, n_street
                        else:
                            st.error("Could not find that address. Using map center instead.")
                            final_lat, final_lon, final_street = st.session_state.map_center["lat"], st.session_state.map_center["lon"], "Torrington"
                    except:
                        final_lat, final_lon = st.session_state.map_center["lat"], st.session_state.map_center["lon"]
                else:
                    final_lat, final_lon, final_street = st.session_state.map_center["lat"], st.session_state.map_center["lon"], n_street

                # SAVE TO SHEET
                t_stamp = datetime.now().strftime("%m/%d %I:%M %p")
                worksheet.append_row([n_name, n_status, final_lat, final_lon, 250, final_street, t_stamp])
                st.success("Successfully Reported!")
                st.rerun()

    with tab2:
        # (Chat logic remains the same)
        st.subheader("Community Chat")
        u_msg = st.text_input("Message")
        if st.button("Send"):
            chat_worksheet.append_row([datetime.now().strftime("%H:%M"), "Guest", u_msg])
            st.rerun()

# --- 6. MAIN MAP ---
st.title("🌍 Live Map")
df_map = load_data()

st.markdown('<div class="map-wrapper">', unsafe_allow_html=True)
st.markdown('<div class="map-crosshair"></div>', unsafe_allow_html=True)

view_state = pdk.ViewState(
    latitude=st.session_state.map_center["lat"], 
    longitude=st.session_state.map_center["lon"], 
    zoom=14
)

# Render alerts
layer = pdk.Layer(
    "ScatterplotLayer", df_map,
    get_position='[lon, lat]',
    get_color="[255, 0, 0, 160]",
    get_radius=100,
    pickable=True
)

st.pydeck_chart(pdk.Deck(map_style='light', initial_view_state=view_state, layers=[layer]))
st.markdown('</div>', unsafe_allow_html=True)

# --- 7. RECENT FEED ---
st.divider()
st.subheader("📍 Recent Activity")
if not df_map.empty:
    for _, row in df_map.tail(3).iloc[::-1].iterrows():
        st.write(f"**{row['timestamp']}** | **{row['alert_name']}** at {row['street']} — *{row['status']}*")
