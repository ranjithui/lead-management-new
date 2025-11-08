# app.py
import streamlit as st
import pandas as pd
from datetime import date
from utils.supabase_client import supabase

st.set_page_config(page_title="Lead Management", layout="wide")
st.title("📈 Lead Management System")

tabs = st.tabs(["🏠 Dashboard", "📝 Daily Update", "📊 Reports", "⚙️ Admin"])

# ---------------- DASHBOARD ----------------
with tabs[0]:
    st.header("Dashboard (read-only)")
    leads = supabase.table("leads").select("*").execute().data or []
    members = supabase.table("team_members").select("*").execute().data or []
    teams = supabase.table("teams").select("*").execute().data or []

    df_leads = pd.DataFrame(leads)
    if df_leads.empty:
        st.info("No leads yet. Add leads in 'Daily Update'.")
    else:
        df_leads['lead_date'] = pd.to_datetime(df_leads['lead_date'])
        total_leads = df_leads['num_leads'].sum()
        total_conv = df_leads['converted'].sum()
        rate = (total_conv / total_leads * 100) if total_leads else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Leads", int(total_leads))
        c2.metric("Total Conversions", int(total_conv))
        c3.metric("Conversion Rate", f"{rate:.1f}%")

        st.subheader("Recent Leads")
        st.dataframe(df_leads.sort_values("created_at", ascending=False).head(15))

# ---------------- DAILY UPDATE ----------------
with tabs[1]:
    st.header("Daily Update (Team Lead)")
    members = supabase.table("team_members").select("*").execute().data or []
    members_df = pd.DataFrame(members)
    member_map = {}
    if not members_df.empty:
        member_map = {f"{r['name']} ({r['email']})": r['id'] for _, r in members_df.iterrows()}

    with st.expander("➕ Add Daily Leads"):
        with st.form("add_leads_form"):
            if member_map:
                member_choice = st.selectbox("Team Member", list(member_map.keys()))
                member_id = member_map[member_choice]
            else:
                st.info("No team members found. Add members in Admin tab.")
                member_id = None

            num_leads = st.number_input("Number of Leads", min_value=1, value=1)
            submitted = st.form_submit_button("Submit Leads")
            if submitted:
                if not member_id:
                    st.error("Choose a team member first.")
                else:
                    supabase.table("leads").insert({
                        "member_id": member_id,
                        "lead_date": str(date.today()),
                        "num_leads": int(num_leads),
                        "converted": False
                    }).execute()
                    st.success("Leads added ✅")

    with st.expander("✔️ Update Conversion"):
        with st.form("update_conv_form"):
            # Show unconverted leads for selection
            leads = supabase.table("leads").select("*").eq("converted", False).execute().data or []
            if leads:
                leads_df = pd.DataFrame(leads)
                leads_df['label'] = leads_df.apply(
                    lambda r: f"{r['id']} | member:{r.get('member_id')} | date:{r['lead_date']} | qty:{r['num_leads']}", axis=1
                )
                lead_choice = st.selectbox("Select Lead to mark converted", leads_df['label'].tolist())
                lead_id = lead_choice.split("|")[0].strip()
                conv_sub = st.form_submit_button("Mark Converted")
                if conv_sub:
                    supabase.table("leads").update({
                        "converted": True,
                        "conversion_date": str(date.today())
                    }).eq("id", lead_id).execute()
                    st.success("Lead marked as converted 🎉")
            else:
                st.info("No unconverted leads to update.")

# ---------------- REPORTS ----------------
with tabs[2]:
    st.header("Reports")
    leads = supabase.table("leads").select("*").execute().data or []
    df = pd.DataFrame(leads)
    if df.empty:
        st.warning("No data to report.")
    else:
        df['lead_date'] = pd.to_datetime(df['lead_date'])
        df['week'] = df['lead_date'].dt.isocalendar().week
        df['month'] = df['lead_date'].dt.month

        view = st.radio("Group by", ["Weekly", "Monthly"])
        if view == "Weekly":
            grouped = df.groupby("week")[["num_leads", "converted"]].sum().reset_index()
        else:
            grouped = df.groupby("month")[["num_leads", "converted"]].sum().reset_index()

        st.dataframe(grouped)
        csv = grouped.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download CSV", csv, file_name="report.csv")

# ---------------- ADMIN ----------------
with tabs[3]:
    st.header("Admin — manage teams & members")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Create Team")
        tname = st.text_input("Team Name", key="team_name")
        if st.button("Add Team"):
            if tname.strip():
                supabase.table("teams").insert({"team_name": tname.strip()}).execute()
                st.success("Team created")
            else:
                st.error("Enter a team name")

    with col2:
        st.subheader("Create Team Member")
        m_name = st.text_input("Member Name", key="member_name")
        m_email = st.text_input("Member Email", key="member_email")
        # fetch teams for dropdown
        teams = supabase.table("teams").select("*").execute().data or []
        team_map = {t['team_name']: t['id'] for t in teams} if teams else {}
        team_choice = st.selectbox("Select Team", list(team_map.keys()) if team_map else ["No teams available"])
        weekly_target = st.number_input("Weekly target", min_value=0, value=0)
        monthly_target = st.number_input("Monthly target", min_value=0, value=0)
        if st.button("Add Member"):
            if not team_map:
                st.error("Create a team first")
            elif not m_name.strip():
                st.error("Enter member name")
            else:
                supabase.table("team_members").insert({
                    "name": m_name.strip(),
                    "email": m_email.strip(),
                    "team_id": team_map[team_choice],
                    "weekly_target": int(weekly_target),
                    "monthly_target": int(monthly_target)
                }).execute()
                st.success("Member added")

    st.divider()
    st.subheader("Teams & Members")
    teams = supabase.table("teams").select("*").execute().data or []
    members = supabase.table("team_members").select("*").execute().data or []

    for t in teams:
        st.markdown(f"### {t['team_name']}")
        t_members = [m for m in members if m.get('team_id') == t['id']]
        if not t_members:
            st.info("No members")
        else:
            for m in t_members:
                st.write(f"- {m['name']} ({m.get('email')}) | weekly:{m['weekly_target']} monthly:{m['monthly_target']}")

    st.divider()
    st.subheader("Edit / Reassign / Delete Member")
    members_df = pd.DataFrame(members)
    if not members_df.empty:
        sel_name = st.selectbox("Select member", members_df['name'].tolist())
        sel_row = members_df[members_df['name'] == sel_name].iloc[0]
        new_team = st.selectbox("Change to team", [x['team_name'] for x in teams], index=0)
        if st.button("Change Team"):
            new_team_id = next((x['id'] for x in teams if x['team_name'] == new_team), None)
            supabase.table("team_members").update({"team_id": new_team_id}).eq("id", sel_row['id']).execute()
            st.success("Member reassigned")

        if st.button("Delete Member"):
            supabase.table("team_members").delete().eq("id", sel_row['id']).execute()
            st.success("Member deleted")
    else:
        st.info("No members to manage")
