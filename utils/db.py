"""
db.py
-----
MongoDB Atlas connection + data access helpers for all collections:

    users            -> tenant/user accounts (id, name, ...)
    service_team      -> service team members (branch, sub_service, email, id, name)
    complaints        -> submitted complaints/tickets + classification + status + rating
    admins            -> admin accounts (optional, simple hardcoded fallback also supported)

Reads Mongo connection string from Streamlit secrets (preferred) or
the MONGO_URI environment variable as a fallback.
"""

import os
import streamlit as st
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

from utils.timezone import now, PACIFIC_TZ


@st.cache_resource(show_spinner=False)
def get_client():
    uri = None
    try:
        uri = st.secrets["mongo"]["uri"]
    except Exception:
        uri = os.environ.get("MONGO_URI")

    if not uri:
        raise RuntimeError(
            "No MongoDB URI found. Add it to .streamlit/secrets.toml as "
            "[mongo]\\nuri = \"mongodb+srv://...\" or set the MONGO_URI env var."
        )

    # tz_aware + tzinfo=PACIFIC_TZ makes PyMongo return stored BSON
    # datetimes as timezone-aware Pacific datetimes instead of naive UTC.
    client = MongoClient(
        uri,
        serverSelectionTimeoutMS=8000,
        tz_aware=True,
        tzinfo=PACIFIC_TZ,
    )
    try:
        client.admin.command("ping")
    except ConnectionFailure as e:
        raise RuntimeError(f"Could not connect to MongoDB Atlas: {e}")
    return client


def get_db():
    client = get_client()
    db_name = st.secrets.get("mongo", {}).get("db_name", "us_housing_app") if hasattr(st, "secrets") else "us_housing_app"
    return client[db_name]


# ---------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------
def add_user(db, user_id, name, email=None, address=None):
    doc = {
        "user_id": user_id,
        "name": name,
        "email": email,
        "address": address,
        "created_at": now(),
    }
    db.users.update_one({"user_id": user_id}, {"$set": doc}, upsert=True)
    return doc


def get_all_users(db):
    return list(db.users.find({}, {"_id": 0}).sort("created_at", -1))


def find_user(db, user_id, name):
    return db.users.find_one(
        {"user_id": user_id, "name": {"$regex": f"^{name}$", "$options": "i"}},
        {"_id": 0},
    )


def delete_user(db, user_id):
    db.users.delete_one({"user_id": user_id})


# ---------------------------------------------------------------------
# Service team
# ---------------------------------------------------------------------
def add_service_member(db, member_id, name, branch, sub_service, email):
    doc = {
        "member_id": member_id,
        "name": name,
        "branch": branch,
        "sub_service": sub_service,
        "email": email,
        "created_at": now(),
    }
    db.service_team.update_one({"member_id": member_id}, {"$set": doc}, upsert=True)
    return doc


def get_all_service_members(db):
    return list(db.service_team.find({}, {"_id": 0}).sort("created_at", -1))


def find_service_member(db, member_id, branch, sub_service):
    return db.service_team.find_one(
        {
            "member_id": member_id,
            "branch": branch,
            "sub_service": sub_service,
        },
        {"_id": 0},
    )


def get_members_by_branch_subservice(db, branch, sub_service):
    return list(db.service_team.find({"branch": branch, "sub_service": sub_service}, {"_id": 0}))


def delete_service_member(db, member_id):
    db.service_team.delete_one({"member_id": member_id})


# ---------------------------------------------------------------------
# Complaints / Tickets
# ---------------------------------------------------------------------
def create_complaint(db, user_id, user_name, message, branch, sub_service,
                      confidence, receiver_email, confidence_band=None,
                      needs_review=False, priority="Low"):
    """
    If needs_review is True (low-confidence classification), the complaint
    is created with approval_status='Pending' and is NOT emailed to the
    service team yet -- it waits in the Admin approval queue. Admin can
    confirm or correct the branch/sub-service before it gets routed.
    High-confidence complaints are auto-approved and routed immediately.
    """
    doc = {
        "user_id": user_id,
        "user_name": user_name,
        "message": message,
        "branch": branch,
        "sub_service": sub_service,
        "confidence": confidence,
        "confidence_band": confidence_band,
        "priority": priority,
        "receiver_email": receiver_email,
        "status": "Open",
        "approval_status": "Pending Review" if needs_review else "Auto-Approved",
        "reviewed_by_admin": False,
        "email_sent": False,
        "rating": None,
        "created_at": now(),
        "updated_at": now(),
    }
    result = db.complaints.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


def get_pending_review_complaints(db):
    """Low-confidence complaints awaiting Admin approval, lowest
    confidence (highest review priority) first."""
    return list(
        db.complaints.find({"approval_status": "Pending Review"}).sort("confidence", 1)
    )


def approve_complaint(db, complaint_id, branch=None, sub_service=None, receiver_email=None):
    """Admin approves (optionally correcting branch/sub_service/receiver_email)
    a pending complaint, marking it ready to be emailed to the service team."""
    from bson import ObjectId
    update = {
        "approval_status": "Approved",
        "reviewed_by_admin": True,
        "updated_at": now(),
    }
    if branch:
        update["branch"] = branch
    if sub_service:
        update["sub_service"] = sub_service
    if receiver_email:
        update["receiver_email"] = receiver_email
    db.complaints.update_one({"_id": ObjectId(complaint_id)}, {"$set": update})
    return db.complaints.find_one({"_id": ObjectId(complaint_id)})


def reject_complaint(db, complaint_id, reason=""):
    from bson import ObjectId
    db.complaints.update_one(
        {"_id": ObjectId(complaint_id)},
        {"$set": {
            "approval_status": "Rejected",
            "reviewed_by_admin": True,
            "rejection_reason": reason,
            "status": "Closed",
            "updated_at": now(),
        }},
    )


def mark_email_sent(db, complaint_id):
    from bson import ObjectId
    db.complaints.update_one(
        {"_id": ObjectId(complaint_id)},
        {"$set": {"email_sent": True, "updated_at": now()}},
    )


def update_complaint_priority(db, complaint_id, priority):
    from bson import ObjectId
    db.complaints.update_one(
        {"_id": ObjectId(complaint_id)},
        {"$set": {"priority": priority, "updated_at": now()}},
    )


def get_model_health_stats(db):
    """Aggregate confidence-score distribution & review/approval stats
    for the Admin 'Model Health' dashboard -- used to track model
    calibration and health over time."""
    all_complaints = list(db.complaints.find({}, {
        "_id": 0, "confidence": 1, "confidence_band": 1,
        "approval_status": 1, "branch": 1, "sub_service": 1,
        "created_at": 1,
    }))
    return all_complaints


def get_complaints_for_user(db, user_id):
    return list(db.complaints.find({"user_id": user_id}).sort("created_at", -1))


def get_complaints_for_branch(db, branch, sub_service=None):
    """Service team only sees complaints that are Auto-Approved or
    Admin-Approved (i.e. not still pending low-confidence review)."""
    query = {"branch": branch, "approval_status": {"$in": ["Auto-Approved", "Approved"]}}
    if sub_service:
        query["sub_service"] = sub_service
    return list(db.complaints.find(query).sort([("priority", 1), ("created_at", -1)]))


def update_complaint_status(db, complaint_id, status):
    from bson import ObjectId
    db.complaints.update_one(
        {"_id": ObjectId(complaint_id)},
        {"$set": {"status": status, "updated_at": now()}},
    )


def submit_rating(db, complaint_id, rating, comment=None):
    from bson import ObjectId
    db.complaints.update_one(
        {"_id": ObjectId(complaint_id)},
        {"$set": {
            "rating": rating,
            "rating_comment": comment,
            "updated_at": now(),
        }},
    )


def get_all_complaints(db):
    return list(db.complaints.find({}).sort("created_at", -1))


# ---------------------------------------------------------------------
# House Vacancy
# ---------------------------------------------------------------------
def upsert_house_vacancy(db, house_id, name, address, location, area, price,
                          image_url=None, is_vacant=True, priority="Medium"):
    doc = {
        "house_id": house_id,
        "name": name,
        "address": address,
        "location": location,
        "area": area,
        "price": price,
        "image_url": image_url,
        "is_vacant": is_vacant,
        "priority": priority,  # listing priority: Low / Medium / High / Featured
        "updated_at": now(),
    }
    db.house_vacancy.update_one({"house_id": house_id}, {"$set": doc}, upsert=True)
    return doc


def get_all_vacancies(db, vacant_only=False):
    query = {"is_vacant": True} if vacant_only else {}
    return list(db.house_vacancy.find(query, {"_id": 0}).sort([("priority", 1), ("updated_at", -1)]))


def set_vacancy_status(db, house_id, is_vacant):
    db.house_vacancy.update_one(
        {"house_id": house_id},
        {"$set": {"is_vacant": is_vacant, "updated_at": now()}},
    )


def delete_vacancy(db, house_id):
    db.house_vacancy.delete_one({"house_id": house_id})
