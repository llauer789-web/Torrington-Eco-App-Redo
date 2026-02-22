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

# --- 2. DATA FUNCTIONS ---
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

# --- 3. INITIALIZATION ---
st.set_page_config(page_title="Torrington Eco-Pulse", layout="wide")

if 'alerts_df' not in st.session_state:
    st.session_state.alerts_df = load_data()

# Store the "Target" location from clicks
if 'clicked_lat' not in st.session_state:
    st.session_state.clicked_lat = 41.8006
if 'clicked_lon' not in st.session_state:
    st.session_state.clicked_lon = -73.1212

# --- 4. SIDEBAR (CHAT & REPORT) ---
with st.sidebar:
    st.title("🚨 Torrington Pulse")
    tab1, tab2 = st.tabs(["💬 Chat", "📢 Report"])
    
    with tab1:
        st.subheader("Community Chat")
        # Direct display of last few messages
        try:
            chat_logs = chat_worksheet.get_all_records()
            for msg in chat_logs[-10:]:
                st.write(f"**{msg['User']}**: {msg['Message']}")
        except: st.write("No messages yet.")
        
        with st.form("chat_form", clear_on_submit=True):
            u_name = st.text_input("Name", value="Guest")
            u_msg = st.text_input("Message")
            if st.form_submit_button("Send"):
                chat_worksheet.append_row([datetime.now().strftime("%H:%M"), u_name, u_msg])
                st.rerun()

    with tab2:
        st.subheader("New Alert")
        st.write("1. Click the map to drop a pin")
        st.write("2. Fill out the details below")
        
        with st.form("alert_form"):
            n_name = st.text_input("Issue Title")
            n_stat = st.selectbox("Status", ["Urgent", "Active", "Watching", "Resolved"])
            
            # These values now update when you click the map!
            st.write(f"**Location Selected:** {st.session_state.clicked_lat:.4f}, {st.session_state.clicked_lon:.4f}")
            
            n_rad = st.slider("Radius (Meters)", 50, 1000, 250)
            if st.form_submit_button("Submit Alert"):
                worksheet.append_row([n_name, n_stat, st.session_state.clicked_lat, st.session_state.clicked_lon, n_rad])
                st.session_state.alerts_df = load_data()
                st.success("Alert Saved!")
                st.rerun()

# --- 5. MAIN UI ---
st.title("🌍 Eco-Pulse Live Map")

# Create Map Layers
# 1. Existing Alerts
alerts_layer = pdk.Layer(
    "ScatterplotLayer", st.session_state.alerts_df,
    get_position='[lon, lat]',
    get_color="color",
    get_radius="radius",
    pickable=True,
)

# 2. The "Pin" you just dropped
pin_df = pd.DataFrame([{"lat": st.session_state.clicked_lat, "lon": st.session_state.clicked_lon}])
pin_layer = pdk.Layer(
    "ScatterplotLayer", pin_df,
    get_position='[lon, lat]',
    get_color=[0, 0, 255, 200], # Blue pin for the new selection
    get_radius=40,
    filled=True
)

r = pdk.Deck(
    map_style='light',
    initial_view_state=pdk.ViewState(latitude=41.8006, longitude=-73.1212, zoom=12),
    layers=[alerts_layer, pin_layer],
    tooltip={"text": "{display_name}\nStatus: {display_status}"}
)

# This is the "Magic" part that detects clicks!
map_click = st.pydeck_chart(r, on_select="rerun", selection_mode="single-click")

# If the user clicks the map, update the session state and refresh
if map_click and map_click.get("selection") and "coordinate" in map_click["selection"]:
    coords = map_click["selection"]["coordinate"]
    st.session_state.clicked_lon = coords[0]
    st.session_state.clicked_lat = coords[1]
    st.rerun()

# Recent alerts feed at the very bottom
st.divider()
st.subheader("📍 Recent Activity")
cols = st.columns(4)
for i, row in enumerate(st.session_state.alerts_df.iloc[::-1].head(4).iterrows()):
    with cols[i]:
        st.info(f"**{row[1]['display_name']}**\n\n{row[1]['display_status']}")
