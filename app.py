import streamlit as st
import pandas as pd
import pydeck as pdk
import gspread
import base64
import requests
from io import BytesIO
from PIL import Image
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- 1. CONNECTION CONFIG ---
# Ensure "google_maps_api_key" is in your Streamlit Secrets
GOOGLE_MAPS_API_KEY = st.secrets["google_maps_api_key"]
SHEET_URL = "https://docs.google.com/spreadsheets/d/1zEWu2R2ryMDrMMAih1RfU5yBTdNA4uwpR_zcZZ4DXlc/edit"

def get_gspread_client():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"GSheet Credentials Error: {e}")
        return None

# --- 2. GOOGLE GEOCODING ENGINE ---
@st.cache_data(ttl=3600) # Cache coordinates for 1 hour to save API costs
def google_geocode(address):
    if not address: return None
    try:
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={GOOGLE_MAPS_API_KEY}"
        response = requests.get(url).json()
        if response['status'] == 'OK':
            loc = response['results'][0]['geometry']['location']
            return loc['lat'], loc['lng']
    except: return None
    return None

@st.cache_data(ttl=60)
def load_all_data():
    client = get_gspread_client()
    if not client: return pd.DataFrame(), pd.DataFrame()
    try:
        sh = client.open_by_url(SHEET_URL)
        # 1. Load Signals
        data = sh.get_worksheet(0).get_all_records()
        df = pd.DataFrame(data)
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        
        # Convert Streets to Lat/Lon on the fly
        lats, lons = [], []
        for street in df['street']:
            coords = google_geocode(street)
            lats.append(coords[0] if coords else None)
            lons.append(coords[1] if coords else None)
        
        df['lat'] = lats
        df['lon'] = lons
        df['radius'] = pd.to_numeric(df.get('radius', 50), errors='coerce').fillna(50)
        df['verifications'] = pd.to_numeric(df.get('verifications', 0), errors='coerce').fillna(0)
        
        # 2. Load Chat
        chat_df = pd.DataFrame(sh.worksheet("Chat").get_all_records())
        chat_df.columns = [str(c).strip().lower() for c in chat_df.columns]
        
        return df.dropna(subset=['lat', 'lon']), chat_df
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return pd.DataFrame(), pd.DataFrame()

# --- 3. UI INITIALIZATION ---
st.set_page_config(page_title="LocalSignal USA", layout="wide")
current_zip = st.query_params.get("zip", "")
df_all, chat_raw = load_all_data()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("📡 LocalSignal")
    user_zip = st.text_input("Neighborhood Zip", value=current_zip, placeholder="e.g. 06790")
    
    if user_zip != current_zip:
        st.query_params["zip"] = user_zip
        st.rerun()

    tab1, tab2 = st.tabs(["📢 Report", "💬 Chat"])
    
    with tab1:
        with st.form("report_form", clear_on_submit=True):
            n_name = st.text_input("Signal Name")
            n_street = st.text_input("Street Address (inc. Zip)")
            n_stat = st.selectbox("Status", ["Urgent", "Active", "Watching", "Resolved"])
            n_rad = st.number_input("Radius (meters)", min_value=1, value=50)
            n_file = st.file_uploader("Photo", type=['jpg', 'png'])
            
            if st.form_submit_button("Send Signal"):
                img_data = ""
                if n_file:
                    img = Image.open(n_file)
                    img.thumbnail((400, 400))
                    buf = BytesIO()
                    img.save(buf, format="JPEG")
                    img_data = f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"
                
                t = datetime.now().strftime("%m/%d/%Y %I:%M %p")
                client = get_gspread_client()
                # Sheet Columns: Alert Name, Status, Radius, Street, Timestamp, Image, Verifications
                client.open_by_url(SHEET_URL).get_worksheet(0).append_row([n_name, n_stat, n_rad, n_street, t, img_data, 0])
                st.cache_data.clear()
                st.rerun()

    with tab2:
        if user_zip:
            neighborhood_chat = chat_raw[chat_raw['zipcode'].astype(str) == str(user_zip)]
            for _, m in neighborhood_chat.tail(10).iterrows():
                st.caption(f"**{m.get('user','Guest')}** • {m.get('time')}")
                st.info(m.get('message'))
            with st.form("chat_send"):
                msg = st.text_input("Message neighborhood")
                if st.form_submit_button("Send"):
                    client = get_gspread_client()
                    client.open_by_url(SHEET_URL).worksheet("Chat").append_row([datetime.now().strftime("%I:%M %p"), "Guest", msg, user_zip])
                    st.cache_data.clear()
                    st.rerun()
        else: st.warning("Enter Zip to Chat")

# --- 5. MAP & RECENT CARDS ---
st.title(f"🌍 LocalSignal: {user_zip if user_zip else 'USA'}")

if not df_all.empty:
    df_filtered = df_all
    center_lat, center_lon = 41.8006, -73.1212 # Default
    
    if user_zip:
        zip_coords = google_geocode(user_zip)
        if zip_coords:
            center_lat, center_lon = zip_coords
            df_filtered = df_all[(df_all['lat'].between(center_lat-0.1, center_lat+0.1))]

    # DRAW THE DOTS
    df_filtered['color'] = [[255, 75, 75, 180] if "Urgent" in str(s) else [255, 165, 0, 180] for s in df_filtered['status']]
    
    view = pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=13)
    layer = pdk.Layer("ScatterplotLayer", df_filtered, get_position='[lon, lat]', 
                      get_radius="radius", radius_units="'meters'", 
                      get_color="color", pickable=True)
    
    st.pydeck_chart(pdk.Deck(map_style='light', initial_view_state=view, layers=[layer]))

    # RECENT SIGNALS CARDS
    st.divider()
    st.subheader("📍 Recent Neighborhood Signals")
    cols = st.columns(4)
    recent = df_filtered.iloc[::-1].head(4)
    
    for i, (idx, row) in enumerate(recent.iterrows()):
        with cols[i]:
            img = row.get('image', '')
            img_html = f'<img src="{img}" style="width:100%; height:140px; object-fit:cover; border-radius:8px;">' if img else '<div style="height:140px; background:#eee; border-radius:8px; display:flex; align-items:center; justify-content:center; color:#999;">📷</div>'
            st.markdown(f"""
                <div style="border:1px solid #ddd; padding:15px; border-radius:10px; background:white; min-height:420px; display:flex; flex-direction:column;">
                    {img_html}
                    <p style="font-size:11px; color:gray; margin-top:10px;">📅 {row.get('timestamp')}</p>
                    <h4 style="margin:0;">{row.get('alert_name')}</h4>
                    <p style="font-size:13px; flex-grow:1;">📍 {row.get('street')}</p>
                    <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid #eee; padding-top:10px;">
                        <b>{row.get('status')}</b>
                        <span>✅ {int(row.get('verifications'))}</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            if st.button(f"Verify Signal #{i+1}", key=f"v_{idx}"):
                client = get_gspread_client()
                # Updates column 7 (Verifications)
                client.open_by_url(SHEET_URL).get_worksheet(0).update_cell(int(idx) + 2, 7, int(row.get('verifications')) + 1)
                st.cache_data.clear()
                st.rerun()
