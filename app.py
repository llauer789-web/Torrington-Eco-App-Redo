import streamlit as st
import pandas as pd
import pydeck as pdk
from PIL import Image
import smtplib
from email.message import EmailMessage

# 1. --- CONFIGURATION (FILL THESE IN) ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1zEWu2R2ryMDrMMAih1RfU5yBTdNA4uwpR_zcZZ4DXlc/gviz/tq?tqx=out:csv"

# Your Gmail info
SENDER_EMAIL = "your_email@gmail.com" 
SENDER_PASSWORD = "your_16_digit_app_password" # Not your regular password!
RECEIVER_EMAIL = "your_squad_leader@email.com" 

# 2. --- NOTIFICATION LOGIC ---
def send_email_notification(title, status, lat, lon):
    msg = EmailMessage()
    
    # The actual email content
    email_body = f"""
    🚨 NEW ECO-PULSE ALERT REPORTED
    
    Issue: {title}
    Status: {status}
    Location: {lat}, {lon}
    
    Check the live map here: {st.query_params.get('app_url', 'Your Streamlit URL')}
    """
    
    msg.set_content(email_body)
    msg['Subject'] = f"🚨 {status} Alert: {title}"
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL

    try:
        # Connect to Google's Mail Server
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_PASSWORD)
            smtp.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Mail Error: {e}")
        return False

# 3. --- DATA LOADING ---
st.set_page_config(page_title="Torrington Eco-Pulse", layout="wide")

def load_data():
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = [c.strip() for c in df.columns]
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
        return df.dropna(subset=['lat', 'lon'])
    except:
        return pd.DataFrame(columns=["Alert_Name", "Status", "lat", "lon"])

if 'alerts_df' not in st.session_state:
    st.session_state.alerts_df = load_data()

# 4. --- SIDEBAR FORM ---
with st.sidebar:
    st.title("🚨 Report Alert")
    with st.form("alert_form", clear_on_submit=True):
        new_name = st.text_input("Issue Title")
        new_status = st.selectbox("Status", ["Urgent", "Active", "Watching", "Resolved"])
        new_lat = st.number_input("Latitude", value=41.8006, format="%.4f")
        new_lon = st.number_input("Longitude", value=-73.1212, format="%.4f")
        uploaded_file = st.file_uploader("Upload Evidence", type=['png', 'jpg', 'jpeg'])
        
        if st.form_submit_button("Submit & Notify"):
            # This triggers the email
            success = send_email_notification(new_name, new_status, new_lat, new_lon)
            if success:
                st.success(f"Email sent to {RECEIVER_EMAIL}!")
            else:
                st.warning("Alert added locally, but email failed. Check your App Password.")

# 5. --- MAIN DASHBOARD ---
st.title("🌍 Torrington Eco-Pulse")

view_state = pdk.ViewState(latitude=41.8006, longitude=-73.1212, zoom=13)
layer = pdk.Layer(
    "ScatterplotLayer",
    st.session_state.alerts_df,
    get_position='[lon, lat]',
    get_color=[255, 0, 0, 100],
    get_radius=250,
    pickable=True,
)

st.pydeck_chart(pdk.Deck(
    map_style='light', 
    initial_view_state=view_state,
    layers=[layer],
    tooltip={"text": "{Alert_Name}\nStatus: {Status}"}
))

st.dataframe(st.session_state.alerts_df)
