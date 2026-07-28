"""
Home.py
-------
Entry point for the US Housing Support System Streamlit app.
Provides role selection (Admin / User / Service Team) and routes to
the corresponding page. Also shows the synthetic housing dataset +
evaluation metrics as a demo/insights section.
"""

import streamlit as st

st.set_page_config(
    page_title="US Housing Support System",
    page_icon="🏠",
    layout="wide",
)

st.title("🏠 US Housing Support System")
st.caption("Streamlit • MongoDB Atlas • NLP-based complaint routing")

st.markdown(
    """
Welcome! Use the sidebar to navigate:

- **1_Admin** — Add users & service team members, view dataset insights
- **2_User** — Login and submit a complaint (auto-classified & routed via email)
- **3_Service_Team** — Login by branch/sub-service to view & resolve tickets

---
### How it works
1. A **User** logs in with their ID and name, and submits a complaint message.
2. An **NLP classifier** (TF-IDF + cosine similarity) predicts which
   **branch** and **sub-service** the complaint belongs to.
3. An **email notification** is automatically sent to the right service team inbox.
4. The **Service Team** logs in (filtered by branch & sub-service) and resolves the ticket.
5. Once resolved, the **User** can rate the service team's handling of the issue.
"""
)

st.info(
    "Use the sidebar pages to get started. Make sure MongoDB Atlas and "
    "email credentials are configured in `.streamlit/secrets.toml` "
    "(see `secrets.toml.example`)."
)

with st.expander("📊 Routing Taxonomy (Branch → Sub-Service → Email)"):
    st.markdown(
        """
| Branch | Sub-Services | Receiver Email(s) |
|---|---|---|
| **Maintenance** | HVAC, Plumbing, Electrical, Appliance, Pest Control | priyaqa900@gmail.com |
| **Billing** | Rent Payment, Late Fee, Receipt Request, Refund | join2priyad@gmail.com |
| **Lease** | Renewal, Move Out, Transfer, Application | priyankavdeshpande12@gmail.com |
| **Community** | Noise, Parking, Neighbor Complaint Request | deshpande.priya07@gmail.com, deshpand@bu.edu |
"""
    )
