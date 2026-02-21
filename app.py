import streamlit as st
import pandas as pd
import pydeck as pdk
import gspread
from google.oauth2.service_account import Credentials
import smtplib
from email.message import EmailMessage

# --- 1. GOOGLE SHEETS CONNECTION ---
# This uses the secrets you just pasted
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)

# Open your sheet (Make sure this URL is your actual Google Sheet URL)
SHEET_URL = "https://docs.google.com/spreadsheets/d/1zEWu2R2ryMDrMMAih1RfU5yBTdNA4uwpR_zcZZ4DXlc/edit"
sh = client.open_by_url(SHEET_URL)
worksheet = sh.get_worksheet(0) # Opens the first tab

# --- 2. NOTIFICATION LOGIC ---
def send_email_notification(title, status):
    try:
        msg = EmailMessage()
        msg.set_content(f"🚨 NEW ALERT: {title}\nStatus: {status}")
        msg['Subject'] = f"🚨 {status} Alert: {title}"
        msg['From'] = st.secrets["SENDER_EMAIL"]
        msg['To'] = st.secrets["RECEIVER_EMAIL"]
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(st.secrets["SENDER_EMAIL"], st.secrets["SENDER_PASSWORD"])
            smtp.send_message(msg)
    except:
        pass

# --- 3. DATA LOADING ---
st.set_page_config(page_title="Torrington Eco-Pulse", layout="wide")

def load_data():
    # We pull fresh data from the sheet every time
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
    df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
    df['radius'] = pd.to_numeric(df.get('radius', 250), errors='coerce').fillna(250)
    return df.dropna(subset=['lat', 'lon'])

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
        new_radius = st.slider("Alert Radius (Meters)", 50, 1000, 250)
        
        if st.form_submit_button("Submit & Save Permanently"):
            # A. PREPARE THE ROW (Must match your Sheet column order!)
            # Assuming columns: Alert_Name, Status, lat, lon, radius
            new_row = [new_name, new_status, new_lat, new_lon, new_radius]
            
            # B. WRITE TO GOOGLE SHEETS
            worksheet.append_row(new_row)
            
            # C. UPDATE LOCAL VIEW & NOTIFY
            st.session_state.alerts_df = load_data()
            send_email_notification(new_name, new_status)
            st.success("Alert saved to Google Sheets!")

# --- 5. MAP ---
st.title("🌍 Torrington Eco-Pulse")
view_state = pdk.ViewState(latitude=41.8006, longitude=-73.1212, zoom=13)
layer = pdk.Layer(
    "ScatterplotLayer",
    st.session_state.alerts_df,
    get_position='[lon, lat]',
    get_color=[255, 0, 0, 140],
    get_radius="radius",
    pickable=True,
)
st.pydeck_chart(pdk.Deck(map_style='light', initial_view_state=view_state, layers=[layer]))
st.dataframe(st.session_state.alerts_df)
