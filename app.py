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
# --------------------------------------------------
# 4️⃣ ADMIN TAB
# --------------------------------------------------
with tabs[3]:
    st.header("⚙️ Admin — Manage Teams & Members")

    # --------------------------------------------------
    # CREATE / DELETE TEAM
    # --------------------------------------------------
    col1, col2 = st.columns(2)

    # --- Create Team ---
    with col1:
        st.subheader("➕ Create New Team")
        team_name = st.text_input("Team Name", key="create_team_name")
        if st.button("Add Team"):
            if not team_name.strip():
                st.error("Please enter a valid team name.")
            else:
                supabase.table("teams").insert({"team_name": team_name.strip()}).execute()
                st.success(f"✅ Team '{team_name}' created successfully!")
                st.experimental_rerun()

    # --- Delete Team ---
    with col2:
        st.subheader("🗑️ Delete Team")
        teams_data = supabase.table("teams").select("*").execute().data or []
        if not teams_data:
            st.info("No teams available to delete.")
        else:
            team_names = [t["team_name"] for t in teams_data]
            team_to_delete = st.selectbox("Select Team to Delete", team_names, key="delete_team_select")

            if st.button("Delete Selected Team"):
                team_id = next(t["id"] for t in teams_data if t["team_name"] == team_to_delete)
                supabase.table("team_members").delete().eq("team_id", team_id).execute()
                supabase.table("teams").delete().eq("id", team_id).execute()
                st.success(f"🗑️ Team '{team_to_delete}' and its members were deleted successfully!")
                st.experimental_rerun()

    st.divider()

    # --------------------------------------------------
    # ADD TEAM MEMBER
    # --------------------------------------------------
    st.subheader("👤 Add Team Member")

    teams_data = supabase.table("teams").select("*").execute().data or []
    if not teams_data:
        st.info("No teams available. Please create one first.")
    else:
        team_map = {t["team_name"]: t["id"] for t in teams_data}
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            member_name = st.text_input("Member Name", key="member_name")
        with col_b:
            member_email = st.text_input("Email", key="member_email")
        with col_c:
            team_choice = st.selectbox("Team", list(team_map.keys()), key="member_team")

        col_d, col_e = st.columns(2)
        with col_d:
            weekly_target = st.number_input("Weekly Target", min_value=0, value=0, key="member_weekly_target")
        with col_e:
            monthly_target = st.number_input("Monthly Target", min_value=0, value=0, key="member_monthly_target")

        if st.button("Add Member"):
            if not member_name.strip():
                st.error("Please enter member name.")
            else:
                supabase.table("team_members").insert({
                    "name": member_name.strip(),
                    "email": member_email.strip(),
                    "team_id": team_map[team_choice],
                    "weekly_target": weekly_target,
                    "monthly_target": monthly_target
                }).execute()
                st.success(f"✅ Member '{member_name}' added to '{team_choice}' successfully!")
                st.experimental_rerun()

    st.divider()

    # --------------------------------------------------
    # TEAM OVERVIEW (TABLE FORMAT)
    # --------------------------------------------------
    st.subheader("📋 Team Overview")

    teams_data = supabase.table("teams").select("*").execute().data or []
    members_data = supabase.table("team_members").select("*").execute().data or []

    if not teams_data:
        st.info("No teams available yet.")
    else:
        rows = []
        for team in teams_data:
            team_members = [m for m in members_data if m.get("team_id") == team["id"]]
            if team_members:
                for m in team_members:
                    rows.append({
                        "Team Name": team["team_name"],
                        "Member Name": m["name"],
                        "Email": m.get("email", "-"),
                        "Weekly Target": m.get("weekly_target", 0),
                        "Monthly Target": m.get("monthly_target", 0),
                    })
            else:
                rows.append({
                    "Team Name": team["team_name"],
                    "Member Name": "-",
                    "Email": "-",
                    "Weekly Target": "-",
                    "Monthly Target": "-",
                })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    # --------------------------------------------------
    # REASSIGN MEMBER TO ANOTHER TEAM (TOGGLE)
    # --------------------------------------------------
    reassign_toggle = st.checkbox("🔁 Reassign Member to Another Team")

    if reassign_toggle:
        members_data = supabase.table("team_members").select("*").execute().data or []
        teams_data = supabase.table("teams").select("*").execute().data or []

        if not members_data:
            st.info("No members found.")
        elif not teams_data:
            st.warning("No teams available for reassignment.")
        else:
            member_map = {m["name"]: m for m in members_data}
            team_map = {t["team_name"]: t["id"] for t in teams_data}

            col_m, col_t = st.columns(2)
            with col_m:
                member_choice = st.selectbox("Select Member", list(member_map.keys()), key="reassign_member")
            with col_t:
                team_choice = st.selectbox("Select New Team", list(team_map.keys()), key="reassign_team")

            # Show current team info
            selected_member = member_map[member_choice]
            current_team_id = selected_member["team_id"]
            current_team = next((t["team_name"] for t in teams_data if t["id"] == current_team_id), "Unknown")

            st.write(f"👀 **Current Team:** {current_team}")

            if st.button("Confirm Reassignment"):
                new_team_id = team_map[team_choice]
                if new_team_id == current_team_id:
                    st.warning("⚠️ Member is already in this team.")
                else:
                    supabase.table("team_members").update({"team_id": new_team_id}).eq("id", selected_member["id"]).execute()
                    st.success(f"✅ Member '{member_choice}' reassigned from '{current_team}' to '{team_choice}'.")
                    st.experimental_rerun()

    st.divider()

    # --------------------------------------------------
    # EDIT / DELETE MEMBER
    # --------------------------------------------------
    st.subheader("🛠️ Edit or Delete Member")

    members_data = supabase.table("team_members").select("*").execute().data or []
    if not members_data:
        st.info("No team members found.")
    else:
        members_df = pd.DataFrame(members_data)
        member_choice = st.selectbox("Select Member", members_df["name"].tolist(), key="edit_member_select")
        selected_member = members_df[members_df["name"] == member_choice].iloc[0]

        new_name = st.text_input("Edit Name", value=selected_member["name"], key="edit_member_name")
        new_email = st.text_input("Edit Email", value=selected_member.get("email", ""), key="edit_member_email")
        new_weekly = st.number_input("Edit Weekly Target", min_value=0, value=int(selected_member["weekly_target"]), key="edit_member_weekly")
        new_monthly = st.number_input("Edit Monthly Target", min_value=0, value=int(selected_member["monthly_target"]), key="edit_member_monthly")

        col_save, col_delete = st.columns(2)

        with col_save:
            if st.button("💾 Save Changes"):
                supabase.table("team_members").update({
                    "name": new_name.strip(),
                    "email": new_email.strip(),
                    "weekly_target": new_weekly,
                    "monthly_target": new_monthly
                }).eq("id", selected_member["id"]).execute()
                st.success(f"✅ Member '{new_name}' updated successfully!")
                st.experimental_rerun()

        with col_delete:
            if st.button("🗑️ Delete Member"):
                supabase.table("team_members").delete().eq("id", selected_member["id"]).execute()
                st.success(f"❌ Member '{selected_member['name']}' deleted successfully!")
                st.experimental_rerun()
