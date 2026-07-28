"""
2_User.py
---------
User Page:
- User logs in with ID + Name (must have been added by Admin)
- User submits a problem/complaint message
- NLP classifier predicts branch & sub-service
- Email notification is sent automatically to the right team
- User can view their complaint history and rate resolved complaints
"""

import streamlit as st
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db import (
    get_db, find_user, create_complaint, get_complaints_for_user, submit_rating,
    get_all_vacancies, get_members_by_branch_subservice,
)
from utils.classifier import get_classifier, AUTO_ACCEPT_THRESHOLD
from utils.timezone import format_dt
from utils.mailer import send_complaint_email

st.set_page_config(page_title="User | US Housing Support", page_icon="👤", layout="wide")
st.title("👤 User Page")

try:
    db = get_db()
except Exception as e:
    st.error(f"Database connection error: {e}")
    st.stop()

if "user_logged_in" not in st.session_state:
    st.session_state.user_logged_in = False
    st.session_state.user_id = None
    st.session_state.user_name = None

# -----------------------------------------------------------------
# Login
# -----------------------------------------------------------------
if not st.session_state.user_logged_in:
    st.subheader("Login")
    with st.form("user_login_form"):
        uid = st.text_input("User ID")
        uname = st.text_input("Name")
        submitted = st.form_submit_button("Login")
        if submitted:
            user = find_user(db, uid.strip(), uname.strip())
            if user:
                st.session_state.user_logged_in = True
                st.session_state.user_id = user["user_id"]
                st.session_state.user_name = user["name"]
                st.rerun()
            else:
                st.error("No matching user found. Please check your ID and Name, or contact the Admin.")
    st.stop()

st.success(f"Logged in as **{st.session_state.user_name}** (ID: {st.session_state.user_id})")
if st.button("Logout"):
    st.session_state.user_logged_in = False
    st.session_state.user_id = None
    st.session_state.user_name = None
    st.rerun()

tab1, tab2, tab3 = st.tabs(["📝 Submit a Complaint", "📋 My Complaints & Ratings", "🏘️ Browse Vacancies"])

# ===================================================================
# TAB 1: Submit complaint
# ===================================================================
with tab1:
    st.subheader("Describe your problem")
    message = st.text_area(
        "Message",
        placeholder="e.g. My AC has stopped cooling and it's very hot in my apartment...",
        height=150,
    )

    if st.button("Submit", type="primary"):
        if not message.strip():
            st.warning("Please enter a message describing your problem.")
        else:
            with st.spinner("Classifying your complaint..."):
                clf = get_classifier()
                result = clf.classify(message)

            band_emoji = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}.get(result["confidence_band"], "🔴")
            priority_emoji = {"Emergency": "🚨", "High": "🔴", "Medium": "🟡", "Low": "🟢"}.get(result["priority"], "🟢")
            st.info(
                f"**Predicted Branch:** {result['branch']}  \n"
                f"**Predicted Sub-Service:** {result['sub_service']}  \n"
                f"**Confidence:** {result['confidence']} {band_emoji} ({result['confidence_band']})  \n"
                f"**Priority:** {priority_emoji} {result['priority']}"
            )

            complaint = create_complaint(
                db,
                user_id=st.session_state.user_id,
                user_name=st.session_state.user_name,
                message=message.strip(),
                branch=result["branch"],
                sub_service=result["sub_service"],
                confidence=result["confidence"],
                receiver_email=result["receiver_email"],
                confidence_band=result["confidence_band"],
                needs_review=result["needs_review"],
                priority=result["priority"],
            )

            if result["needs_review"]:
                st.warning(
                    f"⏳ Confidence ({result['confidence']}) is below the auto-accept "
                    f"threshold ({AUTO_ACCEPT_THRESHOLD}), so this complaint has been sent "
                    f"to **Admin for review and approval** before it reaches the service team. "
                    f"You'll see it move to 'Approved' status in your complaint history once reviewed."
                )
            else:
                with st.spinner("Sending notification email to the service team..."):
                    matched_members = get_members_by_branch_subservice(
                        db, result["branch"], result["sub_service"]
                    )
                    member_emails = [m["email"] for m in matched_members if m.get("email")]
                    ok, info = send_complaint_email(
                        receiver_email=result["receiver_email"],
                        user_name=st.session_state.user_name,
                        user_id=st.session_state.user_id,
                        branch=result["branch"],
                        sub_service=result["sub_service"],
                        message=message.strip(),
                        confidence=result["confidence"],
                        extra_recipients=member_emails,
                    )
                if ok:
                    st.success(f"Complaint submitted and routed! {info}")
                else:
                    st.warning(f"Complaint saved, but email notification failed: {info}")

            st.balloons()

# ===================================================================
# TAB 2: History + Rating
# ===================================================================
with tab2:
    st.subheader("My Complaint History")
    complaints = get_complaints_for_user(db, st.session_state.user_id)

    if not complaints:
        st.info("You haven't submitted any complaints yet.")
    else:
        for c in complaints:
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    priority_emoji = {"Emergency": "🚨", "High": "🔴", "Medium": "🟡", "Low": "🟢"}.get(
                        c.get("priority", "Low"), "🟢"
                    )
                    st.markdown(f"**{c['branch']} / {c['sub_service']}** {priority_emoji} {c.get('priority', 'Low')}")
                    st.write(c["message"])
                    approval = c.get("approval_status", "Auto-Approved")
                    st.caption(
                        f"Status: {c['status']} • Approval: {approval} • "
                        f"Submitted: {format_dt(c['created_at'])}"
                    )
                    if approval == "Pending Review":
                        st.caption("⏳ Awaiting Admin review before it reaches the service team.")
                    elif approval == "Rejected":
                        st.caption(f"❌ Rejected by admin: {c.get('rejection_reason', '')}")
                with col2:
                    if c["status"] == "Resolved":
                        if c.get("rating"):
                            st.metric("Your Rating", f"{c['rating']} ⭐")
                            if c.get("rating_comment"):
                                st.caption(f"💬 {c['rating_comment']}")
                        else:
                            rating = st.slider(
                                "Rate this service",
                                1, 5, 5,
                                key=f"rate_{c['_id']}",
                            )
                            comment = st.text_area(
                                "Comment (optional)",
                                key=f"comment_{c['_id']}",
                                placeholder="Anything you'd like to add...",
                                height=80,
                            )
                            if st.button("Submit Rating", key=f"submit_rate_{c['_id']}"):
                                submit_rating(db, str(c["_id"]), rating, comment.strip() or None)
                                st.success("Thank you for your feedback!")
                                st.rerun()
                    else:
                        st.caption("⏳ Awaiting resolution")

# ===================================================================
# TAB 3: Browse Vacancies
# ===================================================================
with tab3:
    st.subheader("🏘️ Available House Listings")
    vacant_only = st.checkbox("Show vacant only", value=True)
    vacancies = get_all_vacancies(db, vacant_only=vacant_only)

    if not vacancies:
        st.info("No listings available right now. Check back later!")
    else:
        priority_order = {"Featured": 0, "High": 1, "Medium": 2, "Low": 3}
        vacancies_sorted = sorted(vacancies, key=lambda v: priority_order.get(v.get("priority", "Low"), 3))

        cols_per_row = 3
        for i in range(0, len(vacancies_sorted), cols_per_row):
            row_items = vacancies_sorted[i:i + cols_per_row]
            cols = st.columns(cols_per_row)
            for col, v in zip(cols, row_items):
                with col:
                    with st.container(border=True):
                        if v.get("image_url"):
                            st.image(v["image_url"], use_container_width=True)
                        priority_badge = {"Featured": "⭐", "High": "🔴", "Medium": "🟡", "Low": "🟢"}.get(
                            v.get("priority", "Low"), "🟢"
                        )
                        st.markdown(f"**{v['name']}** {priority_badge} {v.get('priority', 'Low')}")
                        st.caption(f"{v['address']}, {v['location']}")
                        st.write(f"${v['price']:,.0f} • {v['area']} sqft")
                        st.write("🟩 Vacant" if v.get("is_vacant") else "🟥 Occupied")
