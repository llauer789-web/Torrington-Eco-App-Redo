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
        if not data: return pd.DataFrame()
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

def load_chat():
    try:
        chat_data = chat_worksheet.get_all_records()
        return pd.DataFrame(chat_data)
    except: return pd.DataFrame(columns=["Timestamp", "User", "Message"])

# --- 3. INITIALIZATION ---
st.set_page_config(page_title="Torrington Eco-Pulse", layout="wide")

if 'alerts_df' not in st.session_state:
    st.session_state.alerts_df = load_data()
if 'chat_df' not in st.session_state:
    st.session_state.chat_df = load_chat()

# Standard View State
if 'map_view' not in st.session_state:
    st.session_state.map_view = {"latitude": 41.8006, "longitude": -73.1212, "zoom": 13}

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("🚨 Torrington Pulse")
    tab1, tab2 = st.tabs(["💬 Chat", "📢 Report"])
    
    with tab1:
        st.subheader("Community Chat")
        chat_box = st.container(height=300)
        with chat_box:
            for _, msg in st.session_state.chat_df.tail(20).iterrows():
                st.markdown(f"**{msg['User']}**: {msg['Message']}")
        
        with st.form("chat_form", clear_on_submit=True):
            u_name = st.text_input("Name", value="Guest")
            u_msg = st.text_input("Message")
            if st.form_submit_button("Send"):
                if u_msg:
                    chat_worksheet.append_row([datetime.now().strftime("%H:%M:%S"), u_name, u_msg])
                    st.session_state.chat_df = load_chat()
                    st.rerun()

    with tab2:
        st.subheader("New Alert")
        st.info("The form uses the center of your map for the location.")
        with st.form("alert_form", clear_on_submit=True):
            n_name = st.text_input("Issue Title")
            n_stat = st.selectbox("Status", ["Urgent", "Active", "Watching", "Resolved"])
            
            # Using current session state map center
            n_lat = st.number_input("Lat", value=float(st.session_state.map_view["latitude"]), format="%.5f")
            n_lon = st.number_input("Lon", value=float(st.session_state.map_view["longitude"]), format="%.5f")
            
            n_rad = st.slider("Alert Radius (Meters)", 50, 1000, 250)
            if st.form_submit_button("Submit Alert"):
                worksheet.append_row([n_name, n_stat, n_lat, n_lon, n_rad])
                st.session_state.alerts_df = load_data()
                st.success("Alert Saved!")
                st.rerun()

# --- 5. MAIN UI ---
st.title("🌍 Eco-Pulse Live Map")

df_map = st.session_state.alerts_df
sel_stat = st.selectbox("Filter Map:", ["All", "Urgent", "Active", "Watching", "Resolved"])
if not df_map.empty and sel_stat != "All":
    df_map = df_map[df_map['display_status'] == sel_stat]

c1, c2 = st.columns([3, 1])

with c1:
    # Build the map
    view_state = pdk.ViewState(**st.session_state.map_view)
    
    layer = pdk.Layer(
        "ScatterplotLayer", df_map,
        get_position='[lon, lat]',
        get_color="color",
        get_radius="radius",
        pickable=True,
    )

    r = pdk.Deck(
        map_style='light',
        initial_view_state=view_state,
        layers=[layer],
        tooltip={"text": "{display_name}\nStatus: {display_status}"}
    )

    # Simplified chart call to avoid the API Exception
    st.pydeck_chart(r)

with c2:
    st.subheader("📍 Recent Alerts")
    if not df_map.empty:
        for _, row in df_map.iloc[::-1].head(8).iterrows():
            s = row['display_status']
            clr = "#D32F2F" if s == "Urgent" else "#EF6C00" if s == "Active" else "#FBC02D" if s == "Watching" else "#2E7D32"
            st.markdown(f"""
                <div style="border-left: 6px solid {clr}; padding: 12px; background-color: #fcfcfc; border: 1px solid #eeeeee; border-radius: 8px; margin-bottom: 15px;">
                    <h4 style="margin:0; color: #111111; font-size: 16px;">{row['display_name']}</h4>
                    <p style="margin: 5px 0 0 0; color: #333333; font-size: 14px;">Status: <b style="color: {clr};">{s}</b></p>
                </div>
            """, unsafe_allow_html=True)
