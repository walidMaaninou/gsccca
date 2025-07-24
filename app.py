import streamlit as st
from auth import login_to_gsccca
from search import loop_document_scrape
from download import use_session_in_headless_chrome_batch
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests

load_dotenv()

st.set_page_config(page_title="GSCCCA Document Downloader", layout="centered")

# --- Session State ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "session" not in st.session_state:
    st.session_state.session = None



if not st.session_state.logged_in:
    # --- Step 1: Login ---
    st.title("🔐 Login to GSCCCA")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Connect")

        if submitted:
            try:
                st.session_state.username = username
                st.session_state.password = password
                st.session_state.logged_in = True
                st.rerun()
            except Exception as e:
                st.error(f"Login failed: {e}")


# --- Step 2: Document Search ---
if st.session_state.logged_in:
    st.title("📄 Search & Download Documents")

    st.session_state.session = login_to_gsccca(st.session_state.username, st.session_state.password)
    st.session_state.session.get("https://search.gsccca.org/RealEstatePremium/InstrumentTypeSearch.aspx", verify=False)
    # Load dropdown options
    with open("instrument_types.json") as f:
        instrument_types = json.load(f)
    with open("counties.json") as f:
        counties = json.load(f)

    # Dropdown selections
    selected_instrument = st.selectbox("Instrument Type", list(instrument_types.keys()))
    selected_county = st.selectbox("County", list(counties.keys()))
    selected_period = st.selectbox("Period", ["1 month", "2 months", "3 months"])

    if st.button("Start Search"):
        st.info("Searching for documents...")

        # Convert period to date range
        months = int(selected_period.split()[0])
        end_date = datetime.today()
        start_date = end_date - timedelta(days=30 * months)

        instrument_id = instrument_types[selected_instrument]
        county_id = counties[selected_county]

        results_docs = loop_document_scrape(
            st.session_state.session,
            instrument_type=int(instrument_id),
            county_id=int(county_id),
            start_date=start_date.strftime("%m/%d/%Y"),
            end_date=end_date.strftime("%m/%d/%Y")
        )

        st.success(f"Found {len(results_docs)} document links.")
        # Create dynamic table placeholder
        if results_docs:
            st.info("Downloading documents...")
            table_placeholder = st.empty()
            results = []
            use_session_in_headless_chrome_batch(st.session_state.session, results_docs, results, table_placeholder)
            st.success("All documents downloaded successfully!")