"""
1_Admin.py
----------
Admin Page:
- Simple password-gated admin login
- Add / view / delete Users
- Add / view / delete Service Team members (branch + sub-service)
- View the synthetic US Housing dataset with evaluation-style metrics
  (this dataset is only for demo/EDA purposes, unrelated to live data)
"""

import streamlit as st
import pandas as pd
import os
import sys
import base64

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db import (
    get_db, add_user, get_all_users, delete_user,
    add_service_member, get_all_service_members, delete_service_member,
    get_pending_review_complaints, approve_complaint, reject_complaint,
    mark_email_sent, get_model_health_stats,
    upsert_house_vacancy, get_all_vacancies, set_vacancy_status, delete_vacancy,
    get_members_by_branch_subservice,
)
from utils.classifier import (
    BRANCH_SUBSERVICES, BRANCH_EMAILS, AUTO_ACCEPT_THRESHOLD,
    LOW_CONFIDENCE_THRESHOLD, PRIORITY_LEVELS,
)
from utils.mailer import send_new_service_member_email, send_complaint_approved_email
from utils.timezone import format_dt

st.set_page_config(page_title="Admin | US Housing Support", page_icon="🛠️", layout="wide")
st.title("🛠️ Admin Page")

# -----------------------------------------------------------------
# Simple admin auth (demo-grade). Replace with proper auth for prod.
# -----------------------------------------------------------------
ADMIN_PASSWORD = st.secrets.get("admin", {}).get("password", "admin123") if hasattr(st, "secrets") else "admin123"

if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

if not st.session_state.admin_logged_in:
    with st.form("admin_login"):
        pwd = st.text_input("Admin password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            if pwd == ADMIN_PASSWORD:
                st.session_state.admin_logged_in = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    st.stop()

st.success("Logged in as Admin")
if st.button("Logout"):
    st.session_state.admin_logged_in = False
    st.rerun()

try:
    db = get_db()
except Exception as e:
    st.error(f"Database connection error: {e}")
    st.stop()

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "👤 Manage Users", "🧑‍🔧 Manage Service Team", "📊 Dataset Insights",
    "⏳ Approval Queue", "📈 Model Health", "🏘️ Vacancy Management",
])

# ===================================================================
# TAB 1: Users
# ===================================================================
with tab1:
    st.subheader("Add a new user")
    with st.form("add_user_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            user_id = st.text_input("User ID*")
            name = st.text_input("Name*")
        with col2:
            email = st.text_input("Email (optional)")
            address = st.text_input("Address (optional)")
        submitted = st.form_submit_button("Add User")
        if submitted:
            if not user_id or not name:
                st.warning("User ID and Name are required.")
            else:
                add_user(db, user_id.strip(), name.strip(), email.strip() or None, address.strip() or None)
                st.success(f"User '{name}' ({user_id}) added.")

    st.subheader("Existing Users")
    users = get_all_users(db)
    if users:
        df = pd.DataFrame(users)
        st.dataframe(df, use_container_width=True)

        del_id = st.selectbox("Select a User ID to delete", [""] + [u["user_id"] for u in users])
        if st.button("Delete Selected User") and del_id:
            delete_user(db, del_id)
            st.success(f"Deleted user {del_id}")
            st.rerun()
    else:
        st.info("No users added yet.")

# ===================================================================
# TAB 2: Service Team
# ===================================================================
with tab2:
    st.subheader("Add a new service team member")

    # NOTE: `branch` is deliberately OUTSIDE st.form. Widgets inside a
    # Streamlit form don't trigger a rerun until the form is submitted,
    # so a sub-service dropdown depending on it would stay stuck showing
    # whatever branch was selected first (always "Maintenance" by default).
    # Keeping branch outside lets it rerun immediately and refresh the
    # sub-service options before the user submits.
    branch = st.selectbox("Branch*", list(BRANCH_SUBSERVICES.keys()), key="new_member_branch")

    with st.form("add_service_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            member_id = st.text_input("Member ID*")
            member_name = st.text_input("Name*")
        with col2:
            sub_service = st.selectbox("Sub-Service*", BRANCH_SUBSERVICES[branch])
            default_email = BRANCH_EMAILS[branch]
            default_email_str = default_email if isinstance(default_email, str) else default_email[0]
            member_email = st.text_input("Email*", value=default_email_str)
        submitted = st.form_submit_button("Add Service Team Member")
        if submitted:
            if not member_id or not member_name or not member_email:
                st.warning("Member ID, Name, and Email are required.")
            else:
                add_service_member(db, member_id.strip(), member_name.strip(), branch, sub_service, member_email.strip())
                st.success(f"Service member '{member_name}' added to {branch} / {sub_service}.")
                with st.spinner("Sending welcome email to new service member..."):
                    ok, info = send_new_service_member_email(
                        member_email.strip(), member_name.strip(), member_id.strip(), branch, sub_service
                    )
                if ok:
                    st.success(info)
                else:
                    st.warning(f"Member added, but welcome email failed: {info}")

    st.subheader("Existing Service Team Members")
    members = get_all_service_members(db)
    if members:
        df2 = pd.DataFrame(members)
        st.dataframe(df2, use_container_width=True)

        del_mid = st.selectbox("Select a Member ID to delete", [""] + [m["member_id"] for m in members])
        if st.button("Delete Selected Member") and del_mid:
            delete_service_member(db, del_mid)
            st.success(f"Deleted member {del_mid}")
            st.rerun()
    else:
        st.info("No service team members added yet.")

# ===================================================================
# TAB 3: Dataset Insights (synthetic US housing dataset)
# ===================================================================
with tab3:
    st.subheader("Synthetic US Housing Dataset")
    st.caption(
        "This dataset (id, name, address, location, area, price, tenure_of_stay) "
        "is synthetic and used only to demonstrate evaluation metrics / EDA. "
        "It is NOT the live application data (that lives in MongoDB)."
    )

    dataset_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "us_housing_dataset.csv",
    )

    if os.path.exists(dataset_path):
        housing_df = pd.read_csv(dataset_path)
        st.dataframe(housing_df.head(50), use_container_width=True)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Records", len(housing_df))
        col2.metric("Avg Price ($)", f"{housing_df['price'].mean():,.0f}")
        col3.metric("Avg Area (sqft)", f"{housing_df['area'].mean():,.0f}")
        col4.metric("Unique Locations", housing_df['location'].nunique())

        st.markdown("#### Price Distribution")
        st.bar_chart(housing_df['price'])

        st.markdown("#### Price vs Area")
        st.scatter_chart(housing_df, x="area", y="price")

        st.markdown("#### Average Price by Location (Top 10)")
        top_locations = housing_df.groupby("location")["price"].mean().sort_values(ascending=False).head(10)
        st.bar_chart(top_locations)

        st.markdown("#### Basic Regression Evaluation Metrics (Price ~ Area)")
        st.caption("A simple linear regression is fit on Area → Price to demonstrate evaluation metrics (MAE, MSE, RMSE, R²).")

        from sklearn.linear_model import LinearRegression
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
        import numpy as np

        X = housing_df[["area"]].values
        y = housing_df["price"].values
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        model = LinearRegression()
        model.fit(X_train, y_train)
        preds = model.predict(X_test)

        mae = mean_absolute_error(y_test, preds)
        mse = mean_squared_error(y_test, preds)
        rmse = np.sqrt(mse)
        r2 = r2_score(y_test, preds)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("MAE", f"{mae:,.2f}")
        m2.metric("MSE", f"{mse:,.2f}")
        m3.metric("RMSE", f"{rmse:,.2f}")
        m4.metric("R² Score", f"{r2:.3f}")

        if "is_vacant" in housing_df.columns:
            st.markdown("#### Vacancy Overview")
            v1, v2, v3 = st.columns(3)
            vacant_count = int(housing_df["is_vacant"].sum())
            v1.metric("Vacant Houses", vacant_count)
            v2.metric("Occupied Houses", len(housing_df) - vacant_count)
            v3.metric("Vacancy Rate", f"{vacant_count/len(housing_df)*100:.1f}%")

            st.markdown("#### Featured / High-Priority Vacant Listings")
            featured = housing_df[
                (housing_df["is_vacant"] == True) &
                (housing_df["priority"].isin(["Featured", "High"]))
            ].head(3)
            if not featured.empty:
                cols = st.columns(len(featured))
                for col, (_, row) in zip(cols, featured.iterrows()):
                    with col:
                        st.image(row["image_url"], use_container_width=True)
                        st.markdown(f"**{row['location']}** — {row['priority']} priority")
                        st.caption(f"${row['price']:,.0f} • {row['area']} sqft")
            else:
                st.info("No Featured/High priority vacant listings in this sample.")
    else:
        st.warning(
            f"Dataset not found at `{dataset_path}`. "
            "Run `python data/generate_dataset.py` to create it."
        )

# ===================================================================
# TAB 4: Approval Queue (low-confidence complaints needing review)
# ===================================================================
with tab4:
    st.subheader("⏳ Low-Confidence Complaints Awaiting Approval")
    st.caption(
        f"Complaints with classifier confidence below the auto-accept threshold "
        f"({AUTO_ACCEPT_THRESHOLD}) are held here for manual review instead of "
        f"being routed automatically. Sorted by lowest confidence first (highest review priority)."
    )

    pending = get_pending_review_complaints(db)

    if not pending:
        st.info("No complaints currently awaiting review. 🎉")
    else:
        for c in pending:
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    band = c.get("confidence_band", "Low")
                    band_emoji = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}.get(band, "🔴")
                    st.markdown(
                        f"**{band_emoji} Confidence: {c['confidence']} ({band})** — "
                        f"Predicted: {c['branch']} / {c['sub_service']}"
                    )
                    st.write(c["message"])
                    st.caption(
                        f"User: {c['user_name']} ({c['user_id']}) • "
                        f"Priority: {c.get('priority', 'Low')} • "
                        f"Submitted: {format_dt(c['created_at'])}"
                    )
                with col2:
                    corrected_branch = st.selectbox(
                        "Correct Branch", list(BRANCH_SUBSERVICES.keys()),
                        index=list(BRANCH_SUBSERVICES.keys()).index(c["branch"]),
                        key=f"cbranch_{c['_id']}",
                    )
                    corrected_sub = st.selectbox(
                        "Correct Sub-Service", BRANCH_SUBSERVICES[corrected_branch],
                        index=BRANCH_SUBSERVICES[corrected_branch].index(c["sub_service"])
                        if c["sub_service"] in BRANCH_SUBSERVICES[corrected_branch] else 0,
                        key=f"csub_{c['_id']}",
                    )
                    approve_col, reject_col = st.columns(2)
                    with approve_col:
                        if st.button("✅ Approve", key=f"approve_{c['_id']}"):
                            new_email = BRANCH_EMAILS[corrected_branch]
                            approved = approve_complaint(
                                db, str(c["_id"]),
                                branch=corrected_branch,
                                sub_service=corrected_sub,
                                receiver_email=new_email,
                            )
                            matched_members = get_members_by_branch_subservice(
                                db, corrected_branch, corrected_sub
                            )
                            member_emails = [m["email"] for m in matched_members if m.get("email")]
                            ok, info = send_complaint_approved_email(
                                receiver_email=new_email,
                                user_name=c["user_name"],
                                user_id=c["user_id"],
                                branch=corrected_branch,
                                sub_service=corrected_sub,
                                message=c["message"],
                                confidence=c["confidence"],
                                priority=c.get("priority", "Low"),
                                extra_recipients=member_emails,
                            )
                            if ok:
                                mark_email_sent(db, str(c["_id"]))
                                st.success(f"Approved & routed. {info}")
                            else:
                                st.warning(f"Approved, but email failed: {info}")
                            st.rerun()
                    with reject_col:
                        if st.button("❌ Reject", key=f"reject_{c['_id']}"):
                            reject_complaint(db, str(c["_id"]), reason="Rejected by admin review")
                            st.info("Complaint rejected and closed.")
                            st.rerun()

# ===================================================================
# TAB 5: Model Health (confidence calibration tracking)
# ===================================================================
with tab5:
    st.subheader("📈 Classifier Model Health")
    st.caption(
        "Confidence is the model's own probability/certainty estimate for its "
        "predicted label. Tracking its distribution over time helps monitor "
        "calibration and catch drift (e.g. if average confidence starts "
        "dropping, the model may be seeing complaint types it wasn't trained on)."
    )

    stats = get_model_health_stats(db)

    if not stats:
        st.info("No complaints submitted yet — no model health data available.")
    else:
        stats_df = pd.DataFrame(stats)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Predictions", len(stats_df))
        c2.metric("Avg Confidence", f"{stats_df['confidence'].mean():.3f}")

        auto_approved = (stats_df["approval_status"] == "Auto-Approved").sum()
        pending_or_reviewed = len(stats_df) - auto_approved
        c3.metric("Auto-Accepted", f"{auto_approved} ({auto_approved/len(stats_df)*100:.0f}%)")
        c4.metric("Sent to Review", f"{pending_or_reviewed} ({pending_or_reviewed/len(stats_df)*100:.0f}%)")

        st.markdown("#### Confidence Score Distribution")
        st.bar_chart(stats_df["confidence"])

        st.markdown("#### Confidence Band Breakdown")
        if "confidence_band" in stats_df.columns:
            band_counts = stats_df["confidence_band"].value_counts()
            st.bar_chart(band_counts)

        st.markdown("#### Approval Status Breakdown")
        approval_counts = stats_df["approval_status"].value_counts()
        st.bar_chart(approval_counts)

        st.markdown("#### Avg Confidence by Branch")
        branch_conf = stats_df.groupby("branch")["confidence"].mean().sort_values(ascending=False)
        st.bar_chart(branch_conf)

        st.markdown("#### Thresholds in Effect")
        st.write(f"- **Auto-accept threshold:** ≥ {AUTO_ACCEPT_THRESHOLD} → routed straight to service team")
        st.write(f"- **Low-confidence threshold:** < {LOW_CONFIDENCE_THRESHOLD} → highest-priority manual review")
        st.write(f"- Between the two → Medium confidence, still queued for review")

# ===================================================================
# TAB 6: House Vacancy Management
# ===================================================================
with tab6:
    st.subheader("🏘️ House Vacancy Management")
    st.caption("Add/update house listings with vacancy status, priority, and an image.")

    with st.form("vacancy_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            house_id = st.text_input("House ID*")
            house_name = st.text_input("Property Name*")
            address = st.text_input("Address*")
            location = st.text_input("Location (City, State)*")
        with col2:
            area = st.number_input("Area (sqft)*", min_value=100, value=1000)
            price = st.number_input("Price ($)*", min_value=100.0, value=200000.0)
            priority = st.selectbox("Listing Priority", PRIORITY_LEVELS + ["Featured"], index=1)
        is_vacant = st.checkbox("Currently Vacant", value=True)

        st.markdown("**Property Image**")
        uploaded_image = st.file_uploader(
            "Upload an image (jpg/png)", type=["jpg", "jpeg", "png"], key="vacancy_image_upload"
        )
        image_url = st.text_input(
            "...or paste an Image URL instead (used only if no file is uploaded)",
            value="",
            placeholder="https://example.com/photo.jpg",
        )

        submitted = st.form_submit_button("Save Listing")
        if submitted:
            if not house_id or not house_name or not address or not location:
                st.warning("House ID, Property Name, Address, and Location are required.")
            else:
                final_image = None
                if uploaded_image is not None:
                    img_bytes = uploaded_image.getvalue()
                    b64 = base64.b64encode(img_bytes).decode("utf-8")
                    mime = uploaded_image.type or "image/jpeg"
                    final_image = f"data:{mime};base64,{b64}"
                elif image_url.strip():
                    final_image = image_url.strip()

                upsert_house_vacancy(
                    db, house_id.strip(), house_name.strip(), address.strip(), location.strip(),
                    int(area), float(price), final_image, is_vacant, priority,
                )
                st.success(f"Listing '{house_name}' saved.")

    st.markdown("#### Current Listings")
    vacancies = get_all_vacancies(db)
    if vacancies:
        priority_order = {"Featured": 0, "High": 1, "Medium": 2, "Low": 3}
        vacancies_sorted = sorted(vacancies, key=lambda v: priority_order.get(v.get("priority", "Low"), 3))

        for v in vacancies_sorted:
            with st.container(border=True):
                col1, col2, col3 = st.columns([1, 2, 1])
                with col1:
                    if v.get("image_url"):
                        st.image(v["image_url"], use_container_width=True)
                with col2:
                    priority_badge = {"Featured": "⭐", "High": "🔴", "Medium": "🟡", "Low": "🟢"}.get(
                        v.get("priority", "Low"), "🟢"
                    )
                    st.markdown(f"**{v['name']}** {priority_badge} {v.get('priority', 'Low')}")
                    st.write(f"{v['address']}, {v['location']}")
                    st.caption(f"{v['area']} sqft • ${v['price']:,.0f}")
                    vacancy_badge = "🟩 Vacant" if v.get("is_vacant") else "🟥 Occupied"
                    st.write(vacancy_badge)
                with col3:
                    toggle_label = "Mark Occupied" if v.get("is_vacant") else "Mark Vacant"
                    if st.button(toggle_label, key=f"toggle_{v['house_id']}"):
                        set_vacancy_status(db, v["house_id"], not v.get("is_vacant"))
                        st.rerun()
                    if st.button("Delete", key=f"delvac_{v['house_id']}"):
                        delete_vacancy(db, v["house_id"])
                        st.rerun()
    else:
        st.info("No listings added yet.")
