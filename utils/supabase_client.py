import streamlit as st
from supabase import create_client, Client

@st.cache_resource
def init_supabase() -> Client:
    """Initialize Supabase client using secrets from Streamlit Cloud"""
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]

        client = create_client(url, key)

        # Quick connection test
        try:
            _ = client.table("teams").select("*").limit(1).execute()
            st.sidebar.success("✅ Connected to Supabase")
        except Exception as e:
            st.sidebar.error(f"⚠️ Supabase query failed: {e}")

        return client
    except KeyError:
        st.error("❌ Supabase secrets missing. Add them in Streamlit Cloud → Settings → Secrets.")
        st.stop()

supabase = init_supabase()
