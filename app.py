import streamlit as st
import pandas as pd
import pydeck as pdk
import gspread
from google.oauth2.service_account import Credentials
import smtplib
from email.message import EmailMessage

# --- 1. GOOGLE SHEETS & SECRETS SETUP ---
try:
    # Google Service Account Connection
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    
    # Open your specific sheet
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1zEWu2R2ryMDrMMAih1RfU5yBTdNA4uwpR_zcZZ4DXlc/edit"
    sh = client.open_by_url(SHEET_URL)
    worksheet = sh.get_worksheet(0)
    
    # Email Secrets
    SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
    SENDER_PASSWORD = st.secrets["SENDER_PASSWORD"]
    RECEIVER_EMAIL = st.secrets["RECEIVER_EMAIL"]
except Exception as e:
    st.error(f"Configuration Error: {e}")

# --- 2. DYNAMIC COLOR LOGIC ---
def get_status_color(status):
    # Format: [Red, Green, Blue, Alpha (0-255)]
    # Alpha is set to 140 for transparency
    colors = {
        "Urgent": [255, 0, 0, 140],      # Red
        "Active": [255, 165, 0, 140],    # Orange
        "Watching": [255, 255, 0, 140],  # Yellow
        "Resolved": [0, 128, 0, 140]     # Green
    }
    return colors.get(status, [125, 125, 125, 140]) # Default Gray

# --- 3. NOTIFICATION LOGIC ---
def send_email_notification(title, status, lat, lon):
    msg = EmailMessage()
    msg.set_content(f"🚨 NEW ECO-PULSE ALERT\n\nIssue: {title}\nStatus: {status}\nCoords: {lat}, {lon}")
    msg['Subject'] = f"🚨 {status} Alert: {title}"
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_PASSWORD)
            smtp.send_message(msg)
        return True
    except:
        return False

# --- 4. DATA LOADING ---
st.set_page_config(page_title="Torrington Eco-Pulse", layout="wide")

def load_data():
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    # Convert columns to numbers safely
    df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
    df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
    df['radius'] = pd.to_numeric(df.get('radius', 250), errors='coerce').fillna(250)
    
    # Assign the dynamic color based on Status
    df['color'] = df['Status'].apply(get_status_color)
    
    return df.dropna(subset=['lat', 'lon'])

# Initialize session state for speed, but always load fresh from Sheets
if 'alerts_df' not in st.session_state:
    st.session_state.alerts_df = load_data()

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("🚨 Report Alert")
    with st.form("alert_form", clear_on_submit=True):
        new_name = st.text_input("Issue Title")
        new_status = st.selectbox("Status", ["Urgent", "Active", "Watching", "Resolved"])
        new_lat = st.number_input("Latitude", value=41.8006, format="%.4f")
        new_lon = st.number_input("Longitude", value=-73.1212, format="%.4f")
        new_radius = st.slider("Alert Radius (Meters)", 50, 1000, 250)
        
        if st.form_submit_button("Submit & Save"):
            # A. Prepare the list for Google Sheets
            new_row = [new_name, new_status, new_lat, new_lon, new_radius]
            
            # B. Save to Sheet
            worksheet.append_row(new_row)
            
            # C. Trigger Notification
            send_email_notification(new_name, new_status, new_lat, new_lon)
            
            # D. Refresh Local Data
            st.session_state.alerts_df = load_data()
            st.success("Success! Alert saved and Squad notified.")

    # Simple Color Key for users
    st.markdown("---")
    st.markdown("**Color Key:**")
    st.markdown("🔴 Urgent | 🟠 Active | 🟡 Watching | 🟢 Resolved")

# --- 6. MAIN DASHBOARD ---
st.title("🌍 Torrington Eco-Pulse")

view_state = pdk.ViewState(latitude=41.8006, longitude=-73.1212, zoom=13)

# The Map Layer
layer = pdk.Layer(
    "ScatterplotLayer",
    st.session_state.alerts_df,
    get_position='[lon, lat]',
    get_color="color", # Pulls from our dynamic color column
    get_radius="radius",
    pickable=True,
)

st.pydeck_chart(pdk.Deck(
    map_style='light', 
    initial_view_state=view_state, 
    layers=[layer],
    tooltip={"text": "{Alert_Name}\nStatus: {Status}\nRadius: {radius}m"}
))

st.dataframe(st.session_state.alerts_df)
