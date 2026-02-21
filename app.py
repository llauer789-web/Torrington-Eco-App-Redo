import streamlit as st
import pandas as pd
import pydeck as pdk
import gspread
from google.oauth2.service_account import Credentials
import smtplib
from email.message import EmailMessage

# --- 1. CONFIGURATION & SECRETS ---
# Ensure these match the keys in your Streamlit Cloud Secrets exactly
try:
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    
    # Replace with your actual Google Sheet URL
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1zEWu2R2ryMDrMMAih1RfU5yBTdNA4uwpR_zcZZ4DXlc/edit"
    sh = client.open_by_url(SHEET_URL)
    worksheet = sh.get_worksheet(0)
    
    # Email settings
    SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
    SENDER_PASSWORD = st.secrets["SENDER_PASSWORD"]
    RECEIVER_EMAIL = st.secrets["RECEIVER_EMAIL"]
except Exception as e:
    st.error(f"Setup Error: Check your Secrets and Sheet URL. {e}")

# --- 2. DYNAMIC COLOR LOGIC ---
def get_status_color(status):
    # RGBA: [Red, Green, Blue, Alpha]
    # Alpha at 140 provides the perfect "see-through" look
    colors = {
        "Urgent": [255, 0, 0, 140],      # Red
        "Active": [255, 165, 0, 140],    # Orange
        "Watching": [255, 255, 0, 140],  # Yellow
        "Resolved": [0, 128, 0, 140]     # Green
    }
    return colors.get(status, [125, 125, 125, 140]) # Default Gray
