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
    st.error(f"Connection Error: {e}")

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
    st.
