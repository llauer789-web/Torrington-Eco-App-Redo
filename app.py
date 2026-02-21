import streamlit as st
import pandas as pd
import pydeck as pdk
import gspread
from google.oauth2.service_account import Credentials
import smtplib
from email.message import EmailMessage

# --- 1. SETUP & CONNECTION ---
try:
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1zEWu2R2ryMDrMMAih1RfU5yBTdNA4uwpR_zcZZ4DXlc/edit"
    sh = client.open_by_url(SHEET_URL)
    worksheet = sh.get_worksheet(0)
except Exception as e:
    st.error(f"Secret or Connection Error: {e}")

# --- 2. COLOR LOGIC ---
def get_status_color(status):
    colors = {
        "Urgent": [255, 0, 0, 150],
        "Active": [255, 165, 0, 150],
        "Watching": [255, 255, 0, 150],
        "Resolved": [0, 128, 0, 150]
    }
    return colors.get(str(status).strip(), [125, 125, 125, 150])

# --- 3. DATA LOADING ---
st.set_page_config(page_title="Torrington Eco-Pulse", layout="wide")

def load_data():
    try:
        data = worksheet.get_all_records()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
        df['radius'] = pd.to_numeric(df.get('radius', 250), errors='coerce').fillna(250)
        df = df.dropna(subset=['lat', 'lon'])
        df['color'] = df['Status'].apply(get_status_color)
        return df
    except:
        return pd.DataFrame()

if 'alerts_df' not in st.session_state:
    st.session_state.alerts_df = load_data()

# --- 4. SIDEBAR & FILTERS ---
with st.sidebar:
    st.title("🚨 Torrington Pulse")
    
    # 4a. Filter the Map
    st.subheader("Filter Map")
    all_statuses = ["All", "Urgent", "Active", "Watching", "Resolved"]
    selected_status = st.selectbox("Show Status:", all_statuses)
    
    st.divider()
    
    # 4b. Reporting Form
    with st.expander("➕ Report New Alert"):
        with st.form("alert_form", clear_on_submit=True):
            new_name = st.text_input("Issue Title")
            new_status = st.selectbox("Status", ["Urgent", "Active", "Watching", "Resolved"])
            new_lat = st.number_input("Latitude", value=41.8006, format="%.4f")
            new_lon = st.number_input("Longitude", value=-73.1212, format="%.4f")
            new_radius = st.slider("Radius (Meters)", 50, 1000, 250)
            
            if st.form_submit_button("Submit"):
                worksheet.append_row([new_name, new_status, new_lat, new_lon, new_radius])
                st.session_state.alerts_df = load_data()
                st.success("Alert Saved!")
                st.rerun()

# --- 5. MAIN UI ---
st.title("🌍 Eco-Pulse Live Map")

# Filter data based on sidebar selection
display_df = st.session_state.alerts_df
if selected_status != "All":
    display_df = display_df[display_df['Status'] == selected_status]

# Layout: Map on left, Alert Feed on right
col1, col2 = st.columns([3, 1])

with col1:
    if not display_df.empty:
        view_state = pdk.ViewState(latitude=41.8006, longitude=-73.1212, zoom=13)
        layer = pdk.Layer(
            "ScatterplotLayer",
            display_df,
            get_position='[lon, lat]',
            get_color="color",
            get_radius="radius",
            pickable=True,
        )
        st.pydeck_chart(pdk.Deck(
            map_style='light',
            initial_view_state=view_state,
            layers=[layer],
            tooltip={"text": "{Alert_Name}\nStatus: {Status}"}
        ))
    else:
        st.info("No alerts found for this filter.")

with col2:
    st.subheader("📍 Alerts in Area")
    if not display_df.empty:
        # Show the most recent 10 alerts as "Cards"
        for _, row in display_df.iloc[::-1].head(10).iterrows():
            # Create a simple colored card
            color_hex = "#FF0000" if row['Status'] == "Urgent" else "#FFA500" if row['Status'] == "Active" else "#2ECC71"
            
            with st.container():
                st.markdown(f"""
                <div style="border-left: 5px solid {color_hex}; padding: 10px; background-color: #f0f2f6; border-radius: 5px; margin-bottom: 10px;">
                    <h4 style="margin:0;">{row['Alert_Name']}</h4>
                    <small>Status: <b>{row['Status']}</b></small><br>
                    <small>Radius: {row['radius']}m</small>
                </div>
                """, unsafe_content_address=True, unsafe_allow_html=True)
    else:
        st.write("No
