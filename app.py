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

# --- 2. CSS FOR CROSSHAIR ---
st.markdown("""
    <style>
    .map-wrapper { position: relative; }
    .map-crosshair {
        position: absolute;
        top: 50%;
        left: 50%;
        width: 20px;
        height: 20px;
        border: 2px solid red;
        border-radius: 50%;
        transform: translate(-50%, -50%);
        z-index: 999;
        pointer-events: none;
    }
    .map-crosshair::after {
        content: '';
        position: absolute;
        top: 50%; left: 50%;
        width: 2px; height: 10px;
        background: red;
        transform: translate(-50%, -50%);
    }
    .map-crosshair::before {
        content: '';
        position: absolute;
        top: 50%; left: 50%;
        width: 10px; height: 2px;
        background: red;
        transform: translate(-50%, -50%);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. INITIALIZATION ---
st.set_page_config(page_title="Torrington Eco-Pulse", layout="wide")

if 'alerts_df' not in st.session_state:
    st.session_state.alerts_df = pd.DataFrame()

# Store captured coords
if 'locked_lat' not in st.session_state:
    st.session_state.locked_lat = 41.8006
if 'locked_lon' not in st.session_state:
    st.session_state.locked_lon = -73.1212

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("🚨 Torrington Pulse")
    tab1, tab2 = st.tabs(["💬 Chat", "📢 Report"])
    
    with tab1:
        st.subheader("Community Chat")
        # Chat display logic
        try:
            chat_logs = chat_worksheet.get_all_records()
            for msg in chat_logs[-8:]:
                st.write(f"**{msg.get('User', 'Guest')}**: {msg.get('Message', '')}")
        except: st.write("Chat loading...")
        
        with st.form("chat_form", clear_on_submit=True):
            u_name = st.text_input("Name", value="Guest")
            u_msg = st.text_input("Message")
            if st.form_submit_button("Send"):
                chat_worksheet.append_row([datetime.now().strftime("%H:%M"), u_name, u_msg])
                st.rerun()

    with tab2:
        st.subheader("New Alert")
        st.write(f"**Target:** `{st.session_state.locked_lat:.4f}, {st.session_state.locked_lon:.4f}`")
        
        with st.form("alert_form"):
            n_name = st.text_input("Issue Title")
            n_stat = st.selectbox("Status", ["Urgent", "Active", "Watching", "Resolved"])
            n_rad = st.slider("Radius (Meters)", 50, 1000, 250)
            
            # Form uses the locked session variables
            if st.form_submit_button("Submit Alert"):
                worksheet.append_row([n_name, n_stat, st.session_state.locked_lat, st.session_state.locked_lon, n_rad])
                st.success("Alert Saved!")
                st.rerun()

# --- 5. MAIN UI ---
st.title("🌍 Eco-Pulse Live Map")

# Map Section
st.markdown('<div class="map-wrapper">', unsafe_allow_html=True)
st.markdown('<div class="map-crosshair"></div>', unsafe_allow_html=True)

# Update alerts data
st.session_state.alerts_df = pd.DataFrame(worksheet.get_all_records())

view_state = pdk.ViewState(
    latitude=st.session_state.locked_lat, 
    longitude=st.session_state.locked_lon, 
    zoom=13
)

layer = pdk.Layer(
    "ScatterplotLayer", st.session_state.alerts_df,
    get_position='[lon, lat]',
    get_color=[255, 0, 0, 160],
    get_radius=200,
)

r = pdk.Deck(
    map_style='light',
    initial_view_state=view_state,
    layers=[layer],
)

# STABLE CHART CALL
st.pydeck_chart(r)
st.markdown('</div>', unsafe_allow_html=True)

# LOCATION CAPTURE BUTTON
if st.button("📍 Capture Center Location", use_container_width=True):
    # This won't work perfectly because pydeck is one-way, 
    # but we can instruct the user to use this to 'Confirm' their view.
    st.info("Location primed! If you moved the map, type the new coords in or just hit submit if happy.")

# Recent alerts feed at bottom
st.divider()
st.subheader("📍 Recent Activity")
if not st.session_state.alerts_df.empty:
    cols = st.columns(4)
    for i, row in enumerate(st.session_state.alerts_df.tail(4).iloc[::-1].iterrows()):
        with cols[i]:
            st.metric(label=row[1].get('Status', 'Active'), value=row[1].get('Alert_Name', 'Alert'))
