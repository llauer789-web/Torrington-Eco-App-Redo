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

# --- 3. DATA LOADING (The Fail-Safe Version) ---
st.set_page_config(page_title="Torrington Eco-Pulse", layout="wide")

def load_data():
    try:
        data = worksheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=["Alert_Name", "Status", "lat", "lon", "radius", "color"])
        
        df = pd.DataFrame(data)
        
        # Ensure lat/lon are numbers and drop any rows that aren't
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
        df['radius'] = pd.to_numeric(df.get('radius', 250), errors='coerce').fillna(250)
        
        # Filter out rows with missing coordinates
        df = df.dropna(subset=['lat', 'lon'])
        
        # Force fresh colors
        df['color'] = df['Status'].apply(get_status_color)
        return df
    except Exception as e:
        st.error(f"Sheet Loading Error: {e}")
        return pd.DataFrame()

if 'alerts_df' not in st.session_state:
    st.session_state.alerts_df = load_data()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("🚨 Report Alert")
    with st.form("alert_form", clear_on_submit=True):
        new_name = st.text_input("Issue Title")
        new_status = st.selectbox("Status", ["Urgent", "Active", "Watching", "Resolved"])
        new_lat = st.number_input("Latitude", value=41.8006, format="%.4f")
        new_lon = st.number_input("Longitude", value=-73.1212, format="%.4f")
        new_radius = st.slider("Radius (Meters)", 50, 1000, 250)
        
        if st.form_submit_button("Submit"):
            worksheet.append_row([new_name, new_status, new_lat, new_lon, new_radius])
            st.session_state.alerts_df = load_data()
            st.success("Saved!")

# --- 5. THE MAP ---
st.title("🌍 Torrington Eco-Pulse")

if not st.session_state.alerts_df.empty:
    view_state = pdk.ViewState(latitude=41.8006, longitude=-73.1212, zoom=12)
    
    layer = pdk.Layer(
        "ScatterplotLayer",
        st.session_state.alerts_df,
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
    
    st.dataframe(st.session_state.alerts_df[["Alert_Name", "Status", "lat", "lon", "radius"]])
else:
    st.info("No valid alerts found in the Google Sheet. Add one in the sidebar!")
