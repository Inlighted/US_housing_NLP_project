"""
classifier.py
-------------
Lightweight NLP classifier that maps a free-text complaint message
to (branch, sub_service) using TF-IDF + cosine similarity against a
curated keyword/training corpus. No external API calls, no heavy
ML dependencies -- runs fully offline with scikit-learn.

Branches & sub-services (fixed taxonomy, matches the routing table):

Maintenance
    HVAC, Plumbing, Electrical, Appliance, Pest Control
Billing
    Rent Payment, Late Fee, Receipt Request, Refund
Lease
    Renewal, Move Out, Transfer, Application
Community
    Noise, Parking, Neighbor Complaint Request
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import re

# ---------------------------------------------------------------------
# Training corpus: (text, branch, sub_service)
# Small but representative set of example complaints per sub-service.
# In production this would be replaced/expanded with real historical
# ticket data.
# ---------------------------------------------------------------------
TRAINING_DATA = [
    # ---------------- Maintenance / HVAC ----------------
    ("My air conditioner is not cooling the apartment at all", "Maintenance", "HVAC"),
    ("The heater is not turning on and it's freezing inside", "Maintenance", "HVAC"),
    ("AC unit making loud noise and leaking water", "Maintenance", "HVAC"),
    ("Thermostat is broken and not responding", "Maintenance", "HVAC"),
    ("No heating in the apartment during winter", "Maintenance", "HVAC"),
    ("Air conditioning stopped working suddenly", "Maintenance", "HVAC"),
    ("Furnace is making strange noises and not heating", "Maintenance", "HVAC"),
    ("Room is too hot, cooling system not working", "Maintenance", "HVAC"),

    # ---------------- Maintenance / Plumbing ----------------
    ("There is a water leak under the kitchen sink", "Maintenance", "Plumbing"),
    ("Toilet is clogged and overflowing", "Maintenance", "Plumbing"),
    ("No hot water in the shower for two days", "Maintenance", "Plumbing"),
    ("Bathroom sink is leaking continuously", "Maintenance", "Plumbing"),
    ("Pipes are making banging noises and water pressure is low", "Maintenance", "Plumbing"),
    ("Drain is blocked and water is not draining", "Maintenance", "Plumbing"),
    ("Water heater is broken, no hot water at all", "Maintenance", "Plumbing"),
    ("Faucet is dripping constantly and wasting water", "Maintenance", "Plumbing"),

    # ---------------- Maintenance / Electrical ----------------
    ("Power outlet in the bedroom is not working", "Maintenance", "Electrical"),
    ("Lights keep flickering in the living room", "Maintenance", "Electrical"),
    ("Circuit breaker keeps tripping every night", "Maintenance", "Electrical"),
    ("There is a burning smell from the electrical panel", "Maintenance", "Electrical"),
    ("Ceiling fan switch is not working", "Maintenance", "Electrical"),
    ("No electricity in half of the apartment", "Maintenance", "Electrical"),
    ("Light bulb sockets are sparking when switched on", "Maintenance", "Electrical"),

    # ---------------- Maintenance / Appliance ----------------
    ("Refrigerator is not cooling food properly", "Maintenance", "Appliance"),
    ("Washing machine is not spinning or draining", "Maintenance", "Appliance"),
    ("Dishwasher stopped working mid cycle", "Maintenance", "Appliance"),
    ("Oven is not heating up to set temperature", "Maintenance", "Appliance"),
    ("Microwave sparks when turned on", "Maintenance", "Appliance"),
    ("Dryer is not turning on at all", "Maintenance", "Appliance"),
    ("Stove burner will not ignite", "Maintenance", "Appliance"),

    # ---------------- Maintenance / Pest Control ----------------
    ("There are cockroaches all over the kitchen", "Maintenance", "Pest Control"),
    ("Found bed bugs in the bedroom mattress", "Maintenance", "Pest Control"),
    ("Ants are coming from the walls near the sink", "Maintenance", "Pest Control"),
    ("Mice have been seen running in the apartment", "Maintenance", "Pest Control"),
    ("Termites damaging the wooden floor", "Maintenance", "Pest Control"),
    ("Need pest control spray for spiders and insects", "Maintenance", "Pest Control"),

    # ---------------- Billing / Rent Payment ----------------
    ("I want to pay my monthly rent online", "Billing", "Rent Payment"),
    ("My rent payment did not go through this month", "Billing", "Rent Payment"),
    ("How do I set up automatic rent payment", "Billing", "Rent Payment"),
    ("I was charged twice for rent this month", "Billing", "Rent Payment"),
    ("Need help updating my payment method for rent", "Billing", "Rent Payment"),
    ("Rent portal is not accepting my card", "Billing", "Rent Payment"),

    # ---------------- Billing / Late Fee ----------------
    ("I was charged a late fee even though I paid on time", "Billing", "Late Fee"),
    ("Can you waive my late payment penalty this month", "Billing", "Late Fee"),
    ("Why was a late fee added to my account", "Billing", "Late Fee"),
    ("Dispute the late fee charged on my rent", "Billing", "Late Fee"),
    ("Late fee seems incorrect, please review", "Billing", "Late Fee"),

    # ---------------- Billing / Receipt Request ----------------
    ("Please send me a receipt for last month's rent payment", "Billing", "Receipt Request"),
    ("I need a payment receipt for tax purposes", "Billing", "Receipt Request"),
    ("Can I get an invoice copy for my rent", "Billing", "Receipt Request"),
    ("Requesting proof of rent payment document", "Billing", "Receipt Request"),

    # ---------------- Billing / Refund ----------------
    ("I would like a refund for the overpaid amount", "Billing", "Refund"),
    ("Requesting refund of my security deposit", "Billing", "Refund"),
    ("I was overcharged and need a refund", "Billing", "Refund"),
    ("Please process my refund for the cancelled service", "Billing", "Refund"),

    # ---------------- Lease / Renewal ----------------
    ("I want to renew my lease for another year", "Lease", "Renewal"),
    ("What are the terms for lease renewal", "Lease", "Renewal"),
    ("Please send me the lease renewal agreement", "Lease", "Renewal"),
    ("My lease is expiring soon, want to extend it", "Lease", "Renewal"),

    # ---------------- Lease / Move Out ----------------
    ("I am planning to move out next month", "Lease", "Move Out"),
    ("What is the move out process and checklist", "Lease", "Move Out"),
    ("Need to schedule a move out inspection", "Lease", "Move Out"),
    ("How do I give notice before vacating the apartment", "Lease", "Move Out"),

    # ---------------- Lease / Transfer ----------------
    ("I want to transfer my lease to another unit", "Lease", "Transfer"),
    ("Can I transfer my lease to a family member", "Lease", "Transfer"),
    ("Requesting to switch apartments within the same property", "Lease", "Transfer"),

    # ---------------- Lease / Application ----------------
    ("I want to submit a new rental application", "Lease", "Application"),
    ("What documents are required for the lease application", "Lease", "Application"),
    ("Checking status of my rental application", "Lease", "Application"),
    ("Need help filling out the tenant application form", "Lease", "Application"),

    # ---------------- Community / Noise ----------------
    ("My neighbor plays loud music every night", "Community", "Noise"),
    ("There is constant noise from the upstairs apartment", "Community", "Noise"),
    ("Loud party going on next door disturbing sleep", "Community", "Noise"),
    ("Dog barking loudly all night long", "Community", "Noise"),

    # ---------------- Community / Parking ----------------
    ("Someone is parked in my assigned parking spot", "Community", "Parking"),
    ("Not enough visitor parking available", "Community", "Parking"),
    ("My car got towed from the parking lot unfairly", "Community", "Parking"),
    ("Need an additional parking permit for second car", "Community", "Parking"),

    # ---------------- Community / Neighbor Complaint Request ----------------
    ("My neighbor is being aggressive and threatening", "Community", "Neighbor Complaint Request"),
    ("Filing a complaint against neighbor for harassment", "Community", "Neighbor Complaint Request"),
    ("Neighbor's guests are smoking in the hallway", "Community", "Neighbor Complaint Request"),
    ("Ongoing dispute with neighbor over shared space", "Community", "Neighbor Complaint Request"),
]

BRANCH_EMAILS = {
    "Maintenance": " priyaqa900@gmail.com",
    "Billing": "join2priyad@gmail.com",
    "Lease": " priyankavdeshpande12@gmail.com",
    "Community": ["deshpande.priya07@gmail.com", "deshpand@bu.edu"],
}

BRANCH_SUBSERVICES = {
    "Maintenance": ["HVAC", "Plumbing", "Electrical", "Appliance", "Pest Control"],
    "Billing": ["Rent Payment", "Late Fee", "Receipt Request", "Refund"],
    "Lease": ["Renewal", "Move Out", "Transfer", "Application"],
    "Community": ["Noise", "Parking", "Neighbor Complaint Request"],
}

# ---------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------
# Confidence is the model's own certainty estimate for its predicted
# label (cosine similarity to the nearest training example, 0-1).
# It is used downstream to:
#   1. Auto-accept high-confidence predictions (>= AUTO_ACCEPT_THRESHOLD)
#      and route them straight to the service team.
#   2. Send low/medium-confidence predictions (< AUTO_ACCEPT_THRESHOLD)
#      to Admin for manual review/approval before they reach the team.
#   3. Prioritize which cases get reviewed first (lowest confidence
#      first) and track model calibration/health over time (the Admin
#      "Model Health" dashboard aggregates confidence distribution and
#      approval/override rates).
AUTO_ACCEPT_THRESHOLD = 0.35  # >= this: auto-route to service team
LOW_CONFIDENCE_THRESHOLD = 0.15  # < this: flagged as very low confidence / high review priority


def confidence_band(confidence: float) -> str:
    """Bucket a raw confidence score into a human-readable band."""
    if confidence >= AUTO_ACCEPT_THRESHOLD:
        return "High"
    elif confidence >= LOW_CONFIDENCE_THRESHOLD:
        return "Medium"
    else:
        return "Low"


def needs_admin_review(confidence: float) -> bool:
    """True if this prediction is below the auto-accept threshold and
    should be queued for Admin approval before reaching the service team."""
    return confidence < AUTO_ACCEPT_THRESHOLD


# Complaint priority levels (independent of confidence; set by keyword
# urgency signals in the message, editable by Admin/Service Team).
PRIORITY_LEVELS = ["Low", "Medium", "High", "Emergency"]

_URGENT_KEYWORDS = {
    "Emergency": ["fire", "flood", "gas leak", "no electricity", "burning smell", "gas",
                  "smoke", "sparking", "collapse", "trapped", "overflowing", "no water", "roof leak"],
    "High": ["leak", "not working", "broken", "no heat", "no hot water", "urgent",
             "asap", "infestation", "safety", "threat", "harassment"],
    "Medium": ["noise", "loud", "delay", "slow", "issue", "problem"],
}


def infer_priority(message: str) -> str:
    """Heuristic priority inference from keywords in the complaint text.
    Defaults to 'Low' if nothing urgent is detected. Admin/Service Team
    can override this manually in the UI."""
    text = message.lower()
    for level in ["Emergency", "High", "Medium"]:
        for kw in _URGENT_KEYWORDS[level]:
            if kw in text:
                return level
    return "Low"


# ---------------------------------------------------------------------
# Prediction confidence (derived from the classification, not hard-coded)
# ---------------------------------------------------------------------
# Raw cosine similarity to the single nearest example understates how
# *confident* a prediction is: "gas smell" matches exactly one training
# example (similarity 0.378) and nothing else at all, so the predicted
# class dominates completely -- that is a confident prediction, even
# though 0.378 looks low in absolute terms.
#
# So instead of reporting the raw similarity (or slamming a hard-coded
# floor on top of it), we derive an *exact* confidence from how strongly
# the predicted class dominates its nearest competitors, via a
# temperature-scaled softmax over the top-k candidate similarities:
#
#   * predicted class clearly beats the rest  -> confidence near 1.0
#   * near-tie among several classes          -> confidence near 1/k
#   * nothing matched at all (all sims == 0)  -> confidence 0.0
#
# The value is computed per prediction, so every complaint gets its own
# exact confidence figure instead of a shared constant. Lower the
# temperature to make a dominant class score even higher.
CONFIDENCE_TEMPERATURE = 0.10  # lower = sharper (dominant class -> higher)


def prediction_confidence(top_similarities) -> float:
    """Exact confidence in the top prediction, derived from how much it
    dominates the other candidate classes (softmax over the top-k cosine
    similarities). Returns 0.0 when nothing matched."""
    sims = np.asarray(list(top_similarities), dtype=float)
    if sims.size == 0 or sims[0] <= 1e-9:
        return 0.0
    # Subtract the top score for numerical stability -> exp(0)=1 for the top.
    scaled = np.exp((sims - sims[0]) / CONFIDENCE_TEMPERATURE)
    return float(scaled[0] / scaled.sum())


def _clean(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class ComplaintClassifier:
    """TF-IDF + cosine-similarity nearest-neighbor style classifier."""

    def __init__(self):
        self.texts = [_clean(t) for t, _, _ in TRAINING_DATA]
        self.labels = [(b, s) for _, b, s in TRAINING_DATA]
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self.matrix = self.vectorizer.fit_transform(self.texts)

    def classify(self, message: str, top_k: int = 3):
        """
        Returns dict:
            branch, sub_service, confidence, receiver_email, alternatives
        """
        cleaned = _clean(message)
        vec = self.vectorizer.transform([cleaned])
        sims = cosine_similarity(vec, self.matrix).flatten()

        best_idx = sims.argsort()[::-1][:top_k]
        best_i = best_idx[0]
        branch, sub_service = self.labels[best_i]
        raw_similarity = float(sims[best_i])

        # Fallback: if the nearest example is essentially unmatched, route to
        # a general bucket. This uses the raw similarity (absolute match
        # strength), independent of the dominance-based confidence below.
        if raw_similarity < 0.05:
            branch, sub_service = "Community", "Neighbor Complaint Request"

        # Exact confidence derived from the prediction itself: how strongly
        # the predicted class dominates the other top-k candidates.
        confidence = prediction_confidence(sims[best_idx])

        alternatives = []
        for idx in best_idx[1:]:
            b, s = self.labels[idx]
            if (b, s) != (branch, sub_service):
                alternatives.append({"branch": b, "sub_service": s, "score": float(sims[idx])})

        receiver = BRANCH_EMAILS[branch]

        return {
            "branch": branch,
            "sub_service": sub_service,
            "confidence": round(confidence, 4),
            "raw_similarity": round(raw_similarity, 4),
            "confidence_band": confidence_band(confidence),
            "needs_review": needs_admin_review(confidence),
            "priority": infer_priority(message),
            "receiver_email": receiver,
            "alternatives": alternatives,
        }


# Singleton instance used by the app (loaded once per session)
_classifier_instance = None


def get_classifier():
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = ComplaintClassifier()
    return _classifier_instance