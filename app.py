import streamlit as st
import pandas as pd
import pydeck as pdk
from PIL import Image
import smtplib
from email.message import EmailMessage

# 1. --- GET SECRETS ---
try:
    SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
    SENDER_PASSWORD = st.secrets["SENDER_PASSWORD"]
    RECEIVER_EMAIL = st.secrets["RECEIVER_EMAIL"]
except:
    st.error("Secrets not set up! Go to Streamlit Settings > Secrets.")

SHEET_URL = "https://docs.google.com/spreadsheets/d/1zEWu2R2ryMDrMMAih1RfU5yBTdNA4uwpR_zcZZ4DXlc/gviz/tq?tqx=out:csv"

# 2. --- EMAIL LOGIC ---
def send_email_notification(title, status, lat, lon):
    msg = EmailMessage()
    email_body = f"🚨 NEW ALERT\n\nIssue: {title}\nStatus: {status}\nCoords: {lat}, {lon}"
    msg.set_content(email_body)
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

# 3. --- DATA LOADING & SYNC ---
st.set_page_config(page_title="Torrington Eco-Pulse", layout="wide")

def load_data():
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = [c.strip() for c in df.columns]
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
        df['radius'] = pd.to_numeric(df.get('radius', 250), errors='coerce').fillna(250)
        return df.dropna(subset=['lat', 'lon'])
    except:
        return pd.DataFrame(columns=["Alert_Name", "Status", "lat", "lon", "radius"])

# Initialize session memory
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
        new_radius = st.slider("Alert Radius (Meters)", 50, 1000, 250)
        uploaded_file = st.file_uploader("Upload Evidence", type=['png', 'jpg', 'jpeg'])
        
        submit = st.form_submit_button("Submit & Notify")
        
        if submit:
            # CREATE THE NEW DATA ROW
            new_row = pd.DataFrame([{
                "Alert_Name": new_name,
                "Status": new_status,
                "lat": new_lat,
                "lon": new_lon,
                "radius": new_radius
            }])
            
            # ATTACH TO THE MAP DATA
            st.session_state.alerts_df = pd.concat([st.session_state.alerts_df, new_row], ignore_index=True)
            
            # TRIGGER EMAIL
            send_email_notification(new_name, new_status, new_lat, new_lon)
            st.success("Alert live on map!")

# 5. --- MAIN DASHBOARD ---
st.title("🌍 Torrington Eco-Pulse")

view_state = pdk.ViewState(latitude=41.8006, longitude=-73.1212, zoom=13)

# Map now looks at st.session_state.alerts_df (which we just updated)
layer = pdk.Layer(
    "ScatterplotLayer",
    st.session_state.alerts_df,
    get_position='[lon, lat]',
    get_color=[255, 0, 0, 140],
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
