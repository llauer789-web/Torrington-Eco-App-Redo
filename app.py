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
    status = str(status).strip().capitalize()
    colors = {
        "Urgent": [255, 0, 0, 160],
        "Active": [255, 165, 0, 160],
        "Watching": [255, 215, 0, 160],
        "Resolved": [0, 128, 0, 160]
    }
    return colors.get(status, [125, 125, 125, 160])

def load_data():
    try:
        data = worksheet.get_all_records()
        if not data: return pd.DataFrame()
        df = pd.DataFrame(data)
        # Clean headers
        df.columns = [str(c).strip().replace(" ", "_").lower() for c in df.columns]
        
        # Failsafe: Ensure critical columns exist so it never KeyErrors again
        if 'lat' not in df.columns: df['lat'] = 41.8006
        if 'lon' not in df.columns: df['lon'] = -73.1212
        
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce').fillna(41.8006)
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce').fillna(-73.1212)
        
        # Create Display Columns with fallbacks
        df['d_name'] = df['alert_name'] if 'alert_name' in df.columns else (df['name'] if 'name' in df.columns else "Alert")
        df['d_status'] = df['status'] if 'status' in df.columns else "Active"
        df['d_street'] = df['street'] if 'street' in df.columns else "Torrington"
        df['d_time'] = df['timestamp'] if 'timestamp' in df.columns else "Just now"
        
        df['color'] = df['d_status'].apply(get_status_color)
        df['radius'] = pd.to_numeric(df['radius'], errors='coerce').fillna(250) if 'radius' in df.columns else 250
        
        return df
    except Exception as e:
        st.warning(f"Data sync issue: {e}")
        return pd.DataFrame()

# --- 3. INITIALIZATION ---
st.set_page_config(page_title="Torrington Eco-Pulse", layout="wide")

if 'alerts_df' not in st.session_state:
    st.session_state.alerts_df = load_data()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("🚨 Torrington Pulse")
    tab1, tab2 = st.tabs(["💬 Chat", "📢 Report"])
    
    with tab1:
        st.subheader("Community Chat")
        try:
            chat_logs = chat_worksheet.get_all_records()
            for msg in chat_logs[-8:]:
                st.write(f"**{msg.get('User', 'Guest')}**: {msg.get('Message', '')}")
        except: st.write("Chat loading...")
        
        with st.form("chat_form", clear_on_submit=True):
            u_name = st.text_input("Name", value="Guest")
            u_msg = st.text_input("Message")
            if st.form_submit_button("Send"):
                chat_worksheet.append_row([datetime.now().strftime("%m/%d %H:%M"), u_name, u_msg])
                st.rerun()

    with tab2:
        st.subheader("New Alert")
        with st.form("alert_form", clear_on_submit=True):
            n_name = st.text_input("Issue Name")
            n_street = st.text_input("Street Name")
            n_stat = st.selectbox("Status", ["Urgent", "Active", "Watching", "Resolved"])
            n_lat = st.number_input("Lat", value=41.8006, format="%.4f")
            n_lon = st.number_input("Lon", value=-73.1212, format="%.4f")
            
            if st.form_submit_button("Submit Alert"):
                t_stamp = datetime.now().strftime("%I:%M %p")
                # Order: Alert Name, Status, Lat, Lon, Radius, Street, Timestamp
                worksheet.append_row([n_name, n_stat, n_lat, n_lon, 250, n_street, t_stamp])
                st.session_state.alerts_df = load_data()
                st.success("Alert Saved!")
                st.rerun()

# --- 5. MAIN UI ---
st.title("🌍 Eco-Pulse Live Map")

df_map = st.session_state.alerts_df

# MAP VIEW
view_state = pdk.ViewState(latitude=41.8006, longitude=-73.1212, zoom=13)
layer = pdk.Layer(
    "ScatterplotLayer", df_map,
    get_position='[lon, lat]',
    get_color="color",
    get_radius="radius",
    pickable=True,
)
st.pydeck_chart(pdk.Deck(map_style='light', initial_view_state=view_state, layers=[layer]))

# --- 6. RECENT ALERTS FEED ---
st.divider()
st.subheader("📍 Recent Activity")

if not df_map.empty:
    recent_items = df_map.iloc[::-1].head(4)
    cols = st.columns(4)
    
    for i, (index, row) in enumerate(recent_items.iterrows()):
        stat = str(row['d_status'])
        border_clr = "#D32F2F" if stat == "Urgent" else "#EF6C00" if stat == "Active" else "#FBC02D" if stat == "Watching" else "#2E7D32"
        
        with cols[i]:
            st.markdown(f"""
                <div style="border-left: 8px solid {border_clr}; padding: 12px; border: 1px solid #eee; border-left: 8px solid {border_clr}; border-radius: 10px; background: white;">
                    <small style="color: gray;">{row['d_time']}</small>
                    <h4 style="margin: 0; color: black;">{row['d_name']}</h4>
                    <p style="margin: 0; color: #444;">📍 {row['d_street']}</p>
                    <strong style="color: {border_clr};">{stat}</strong>
                </div>
            """, unsafe_allow_html=True)
else:
    st.info("Awaiting first alert report...")
