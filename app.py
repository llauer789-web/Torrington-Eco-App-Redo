import streamlit as st
import pandas as pd
import pydeck as pdk
import gspread
from google.oauth2.service_account import Credentials

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

# --- 2. DYNAMIC COLOR LOGIC ---
def get_status_color(status):
    colors = {
        "Urgent": [255, 0, 0, 160],
        "Active": [255, 165, 0, 160],
        "Watching": [255, 255, 0, 160],
        "Resolved": [0, 128, 0, 160]
    }
    return colors.get(str(status).strip(), [125, 125, 125, 160])

# --- 3. DATA LOADING ---
st.set_page_config(page_title="Torrington Eco-Pulse", layout="wide")

def load_data():
    try:
        data = worksheet.get_all_records()
        if not data: return pd.DataFrame()
        df = pd.DataFrame(data)
        
        # Standardize column names (lowercase and no spaces)
        df.columns = [str(c).strip().replace(" ", "_").lower() for c in df.columns]
        
        # Mapping variations to internal names
        name_col = next((c for c in df.columns if 'name' in c), 'alert_name')
        stat_col = next((c for c in df.columns if 'stat' in c), 'status')
        
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
        df = df.dropna(subset=['lat', 'lon'])
        
        # Create display columns
        df['display_name'] = df[name_col]
        df['display_status'] = df[stat_col]
        df['color'] = df['display_status'].apply(get_status_color)
        df['radius'] = pd.to_numeric(df.get('radius', 250), errors='coerce').fillna(250)
        return df
    except Exception as e:
        st.error(f"Load Error: {e}")
        return pd.DataFrame()

if 'alerts_df' not in st.session_state:
    st.session_state.alerts_df = load_data()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("🚨 Torrington Pulse")
    sel_stat = st.selectbox("Filter Map:", ["All", "Urgent", "Active", "Watching", "Resolved"])
    st.divider()
    
    with st.expander("➕ Report New Alert"):
        with st.form("alert_form", clear_on_submit=True):
            n_name = st.text_input("Issue Title")
            n_stat = st.selectbox("Status", ["Urgent", "Active", "Watching", "Resolved"])
            n_lat = st.number_input("Lat", value=41.8006, format="%.4f")
            n_lon = st.number_input("Lon", value=-73.1212, format="%.4f")
            n_rad = st.slider("Radius (Meters)", 50, 1000, 250)
            
            if st.form_submit_button("Submit"):
                worksheet.append_row([n_name, n_stat, n_lat, n_lon, n_rad])
                st.session_state.alerts_df = load_data()
                st.success("Saved!")
                st.rerun()

# --- 5. MAIN UI ---
st.title("🌍 Eco-Pulse Live Map")
df_map = st.session_state.alerts_df

if not df_map.empty and sel_stat != "All":
    df_map = df_map[df_map['display_status'] == sel_stat]

c1, c2 = st.columns([3, 1])

with c1:
    if not df_map.empty:
        v_state = pdk.ViewState(latitude=41.8006, longitude=-73.1212, zoom=13)
        layer = pdk.Layer(
            "ScatterplotLayer", df_map,
            get_position='[lon, lat]',
            get_color="color",
            get_radius="radius",
            pickable=True,
        )
        st.pydeck_chart(pdk.Deck(map_style='light', initial_view_state=v_state, layers=[layer], tooltip={"text": "{display_name}\nStatus: {display_status}"}))
    else:
        st.info("No active alerts.")

with c2:
    st.subheader("📍 Recent Alerts")
    if not df_map.empty:
        for _, row in df_map.iloc[::-1].head(10).iterrows():
            s = row['display_status']
            clr = "#FF4B4B" if s == "Urgent" else "#FFA500" if s == "Active" else "#FFE119" if s == "Watching" else "#00CC96"
            st.markdown(f"""
                <div style="border-left: 5px solid {clr}; padding: 10px; background-color: #f0f2f6; border-radius: 8px; margin-bottom: 12px;">
                    <strong style="font-size: 15px;">{row['display_name']}</strong><br>
                    <span style="font-size: 12px;">Status: <b>{s}</b> | {row['radius']}m</span>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.write("Feed empty.")
