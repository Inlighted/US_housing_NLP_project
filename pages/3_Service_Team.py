"""
3_Service_Team.py
------------------
Service Team Page:
- Login based on Member ID + Branch + Sub-Service (must be added by Admin)
- View complaints routed to that branch/sub-service
- Update status (Open / In Progress / Resolved)
- See ratings received from users
"""

import streamlit as st
import pandas as pd
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db import (
    get_db, find_service_member, get_complaints_for_branch, update_complaint_status,
    update_complaint_priority,
)
from utils.classifier import BRANCH_SUBSERVICES, PRIORITY_LEVELS
from utils.timezone import format_dt

st.set_page_config(page_title="Service Team | US Housing Support", page_icon="🧑‍🔧", layout="wide")
st.title("🧑‍🔧 Service Team Page")

try:
    db = get_db()
except Exception as e:
    st.error(f"Database connection error: {e}")
    st.stop()

if "service_logged_in" not in st.session_state:
    st.session_state.service_logged_in = False
    st.session_state.service_member = None

# -----------------------------------------------------------------
# Login
# -----------------------------------------------------------------
if not st.session_state.service_logged_in:
    st.subheader("Login")
    # `branch` outside the form so the sub-service dropdown updates
    # immediately on change (widgets inside st.form don't rerun until submit).
    branch = st.selectbox("Branch", list(BRANCH_SUBSERVICES.keys()), key="login_branch")
    with st.form("service_login_form"):
        member_id = st.text_input("Member ID")
        sub_service = st.selectbox("Sub-Service", BRANCH_SUBSERVICES[branch])
        submitted = st.form_submit_button("Login")
        if submitted:
            member = find_service_member(db, member_id.strip(), branch, sub_service)
            if member:
                st.session_state.service_logged_in = True
                st.session_state.service_member = member
                st.rerun()
            else:
                st.error(
                    "No matching service team member found for that ID / Branch / "
                    "Sub-Service combination. Please check with the Admin."
                )
    st.stop()

member = st.session_state.service_member
st.success(
    f"Logged in as **{member['name']}** — {member['branch']} / {member['sub_service']}"
)
if st.button("Logout"):
    st.session_state.service_logged_in = False
    st.session_state.service_member = None
    st.rerun()

st.divider()
st.subheader(f"Tickets: {member['branch']} / {member['sub_service']}")

complaints = get_complaints_for_branch(db, member["branch"], member["sub_service"])

if not complaints:
    st.info("No complaints routed to your queue yet.")
else:
    status_filter = st.selectbox(
        "Filter by status", ["Active (Open + In Progress)", "Open", "In Progress", "Resolved", "All"]
    )
    if status_filter == "Active (Open + In Progress)":
        filtered = [c for c in complaints if c["status"] in ("Open", "In Progress")]
    elif status_filter == "All":
        filtered = complaints
    else:
        filtered = [c for c in complaints if c["status"] == status_filter]

    st.caption(f"Showing {len(filtered)} of {len(complaints)} tickets")

    for c in filtered:
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                priority = c.get("priority", "Low")
                priority_emoji = {"Emergency": "🚨", "High": "🔴", "Medium": "🟡", "Low": "🟢"}.get(priority, "🟢")
                st.markdown(f"**User:** {c['user_name']} ({c['user_id']})  {priority_emoji} **{priority} priority**")
                st.write(c["message"])
                approval = c.get("approval_status", "Auto-Approved")
                st.caption(
                    f"Submitted: {format_dt(c['created_at'])} • "
                    f"Confidence: {c.get('confidence', 'N/A')} ({c.get('confidence_band', 'N/A')}) • "
                    f"Approval: {approval}"
                )
                if c.get("rating"):
                    st.write(f"⭐ Rating received: **{c['rating']} / 5**")
                    if c.get("rating_comment"):
                        st.caption(f"💬 {c['rating_comment']}")
            with col2:
                new_status = st.selectbox(
                    "Status",
                    ["Open", "In Progress", "Resolved"],
                    index=["Open", "In Progress", "Resolved"].index(c["status"]),
                    key=f"status_{c['_id']}",
                )
                new_priority = st.selectbox(
                    "Priority",
                    PRIORITY_LEVELS,
                    index=PRIORITY_LEVELS.index(priority) if priority in PRIORITY_LEVELS else 0,
                    key=f"priority_{c['_id']}",
                )
                if st.button("Update", key=f"update_{c['_id']}"):
                    update_complaint_status(db, str(c["_id"]), new_status)
                    if new_priority != priority:
                        update_complaint_priority(db, str(c["_id"]), new_priority)
                    st.success("Ticket updated.")
                    st.rerun()

    st.divider()
    st.subheader("📊 Team Performance")
    resolved = [c for c in complaints if c["status"] == "Resolved"]
    rated = [c for c in resolved if c.get("rating")]

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Tickets", len(complaints))
    m2.metric("Resolved", len(resolved))
    if rated:
        avg_rating = sum(c["rating"] for c in rated) / len(rated)
        m3.metric("Avg Rating", f"{avg_rating:.2f} ⭐")
    else:
        m3.metric("Avg Rating", "N/A")
