import streamlit as st
import pandas as pd
import pydeck as pdk

# 1. Setup Page & Session Data (This keeps your alerts active)
st.set_page_config(page_title="Torrington Eco Zoning", layout="wide")

if 'alerts_df' not in st.session_state:
    # Starting data centered in Torrington
    initial_data = {
        "Alert_Name": ["Wetland Filling (Naugatuck River)", "Unauthorized Clearing", "Runoff Near Burr Pond"],
        "Status": ["Urgent", "Watching", "Active"],
        "lat": [41.8006, 41.8150, 41.8300],
        "lon": [-73.1212, -73.1350, -73.1000],
        "color": [[255, 0, 0, 150], [255, 165, 0, 150], [0, 0, 255, 150]],
        "radius": [400, 250, 600]
    }
    st.session_state.alerts_df = pd.DataFrame(initial_data)

# 2. Sidebar - Report New Alert
with st.sidebar:
    st.header("🚨 Report New Activity")
    with st.form("alert_form", clear_on_submit=True):
        new_name = st.text_input("Alert Title (e.g., Soil Erosion)")
        new_status = st.selectbox("Status", ["Urgent", "Active", "Watching", "Resolved"])
        # Defaults to center of Torrington
        new_lat = st.number_input("Latitude", value=41.8006, format="%.4f")
        new_lon = st.number_input("Longitude", value=-73.1212, format="%.4f")
        new_radius = st.slider("Impact Radius (meters)", 100, 2000, 500)
        
        submitted = st.form_submit_button("Submit to Pulse Map")
        
        if submitted:
            # Assign color based on status
            colors = {"Urgent": [255, 0, 0, 150], "Active": [0, 0, 255, 150], 
                      "Watching": [255, 165, 0, 150], "Resolved": [0, 255, 0, 150]}
            
            new_row = {
                "Alert_Name": new_name,
                "Status": new_status,
                "lat": new_lat,
                "lon": new_lon,
                "color": colors[new_status],
                "radius": new_radius
            }
            st.session_state.alerts_df = pd.concat([st.session_state.alerts_df, pd.DataFrame([new_row])], ignore_index=True)
            st.success("Alert added to the map!")

# 3. Main Dashboard UI
st.title("🌍 Torrington Eco-Pulse")
st.markdown(f"**Tracking {len(st.session_state.alerts_df)} active environmental zones in Torrington, CT.**")

# 4. The 3D Pulse Map
view_state = pdk.ViewState(latitude=41.8006, longitude=-73.1212, zoom=13, pitch=45)

layer = pdk.Layer(
    "ScatterplotLayer",
    st.session_state.alerts_df,
    get_position='[lon, lat]',
    get_color='color',
    get_radius='radius',
    pickable=True,
    opacity=0.6,
    stroked=True,
    filled=True,
)

st.pydeck_chart(pdk.Deck(
    map_style='mapbox://styles/mapbox/dark-v10',
    initial_view_state=view_state,
    layers=[layer],
    tooltip={"text": "{Alert_Name}\nStatus: {Status}"}
))

# 5. Alert Cards
st.markdown("---")
cols = st.columns(3)
for i, row in st.session_state.alerts_df.iterrows():
    with cols[i % 3]:
        color_code = "🔴" if row['Status'] == "Urgent" else "🔵"
        st.info(f"{color_code} **{row['Alert_Name']}**\n\nStatus: {row['Status']}")
