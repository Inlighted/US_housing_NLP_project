# 🏠 US Housing Support System

A complete **AI-powered housing/rental property support desk application** built using **Python, Streamlit, NLP, MongoDB Atlas, and Machine Learning concepts**.

The system allows residents to submit housing-related complaints using natural language. An NLP classifier automatically identifies the correct service category and routes the complaint to the responsible service team. Service members can manage tickets, update resolutions, and users can provide feedback after resolution.

---

# 🚀 Project Overview

The **US Housing Support System** simulates a real-world property management customer support platform.

Users can:

- Submit housing complaints in free text
- Automatically classify complaints using NLP
- Receive ticket routing updates
- Track complaint status
- Rate completed services
- Browse available housing vacancies

Administrators can:

- Manage users
- Manage service teams
- Monitor NLP model performance
- Review low-confidence predictions
- Manage property vacancies

Service teams can:

- View assigned complaints
- Update ticket status
- Prioritize urgent issues
- Resolve customer requests

---

# 🛠️ Technology Stack

| Category | Technology |
|---|---|
| Programming Language | Python |
| Frontend Framework | Streamlit |
| Database | MongoDB Atlas |
| NLP | TF-IDF Vectorization |
| Machine Learning | Scikit-learn |
| Similarity Algorithm | Cosine Similarity |
| Data Visualization | Matplotlib |
| Email Service | Gmail SMTP |
| Deployment Ready | Streamlit Cloud / Cloud Platforms |

---

# ✨ Key Features

## 🤖 NLP Complaint Classification

The system automatically understands customer complaints and predicts:

- Service Branch
- Sub-Service Category
- Confidence Score

---

## 📧 Automatic Email Routing

After classification:

- Complaint details are stored in MongoDB
- Responsible service team receives an email notification
- Individual team members can also receive notifications

---

## 🔐 Role-Based Application

The application provides three user roles:

### 👨‍💼 Admin

Capabilities:

- Manage users
- Manage service teams
- Review AI predictions
- Monitor model health
- Manage housing vacancies
- View analytics dashboard


### 👤 Resident/User

Capabilities:

- Login
- Submit complaints
- Track complaints
- Rate completed services
- Browse available properties


### 🛠️ Service Team

Capabilities:

- Login
- View assigned tickets
- Update complaint status
- Modify priority
- Resolve issues

---

# 📂 Project Structure


Example:

User Input:
"My AC is not working and the apartment is very hot"

Prediction:

Branch:
Maintenance

Sub-Service:
HVAC

Confidence:
92%
