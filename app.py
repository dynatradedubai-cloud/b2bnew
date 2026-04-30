# ============================================================
#  Dynatrade B2B Portal - Single File App
#  Secure Admin Path: /admin
#  Customer Portal: /
#  Under 800 lines
# ============================================================

import os
import io
import uuid
import hashlib
import binascii
import warnings
import pandas as pd
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from cryptography.fernet import Fernet

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------
st.set_page_config(page_title="Dynatrade Automotive LLC", layout="wide")

ADMIN_USERNAME = os.environ.get("DYNATRADE_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("DYNATRADE_ADMIN_PASS", "Dyn@1234")

AUDIT_LOG = "audit_log.csv"
ORDERS_FILE = "orders.csv"
META_FILE = "uploads_meta.csv"
USERS_DERIVED = "users_derived.csv"
PARTS_ENC = "parts_list.enc"
USERS_ENC = "users_list.enc"
CAMPAIGNS_META = "campaigns_meta.csv"
CAMPAIGNS_DIR = "campaigns_enc"
os.makedirs(CAMPAIGNS_DIR, exist_ok=True)

# ------------------------------------------------------------
# PASSWORD HASHING (bcrypt optional)
# ------------------------------------------------------------
try:
    import bcrypt as _bcrypt
    _BCRYPT_AVAILABLE = True
except Exception:
    _bcrypt = None
    _BCRYPT_AVAILABLE = False
    warnings.warn("bcrypt not available; using PBKDF2 fallback.")

def hash_password(password: str) -> str:
    if _BCRYPT_AVAILABLE:
        h = _bcrypt.hashpw(password.encode(), _bcrypt.gensalt())
        return "bcrypt$" + h.decode()
    iterations = 200_000
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2${iterations}${binascii.hexlify(salt).decode()}${binascii.hexlify(dk).decode()}"

def verify_password(password: str, stored: str) -> bool:
    if stored.startswith("bcrypt$") and _BCRYPT_AVAILABLE:
        try:
            stored_hash = stored.split("$", 1)[1].encode()
            return _bcrypt.checkpw(password.encode(), stored_hash)
        except Exception:
            return False
    if stored.startswith("pbkdf2$"):
        try:
            _, iterations, salt_hex, hash_hex = stored.split("$")
            iterations = int(iterations)
            salt = binascii.unhexlify(salt_hex)
            expected = binascii.unhexlify(hash_hex)
            dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
            return hashlib.compare_digest(dk, expected)
        except Exception:
            return False
    return False

# ------------------------------------------------------------
# UTILITIES
# ------------------------------------------------------------
def now_uae_iso():
    return datetime.now(ZoneInfo("Asia/Dubai")).isoformat()

def append_audit(event, actor, details):
    row = {
        "timestamp_utc": datetime.utcnow().isoformat(),
        "event": event,
        "actor": actor,
        "details": details
    }
    try:
        if os.path.exists(AUDIT_LOG):
            df = pd.read_csv(AUDIT_LOG)
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        else:
            df = pd.DataFrame([row])
        df.to_csv(AUDIT_LOG, index=False)
    except:
        pass

def encrypt_bytes(raw: bytes):
    key = None
    try:
        key = st.secrets["ENCRYPTION_KEY"]
    except:
        key = os.environ.get("ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("ENCRYPTION_KEY missing.")
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key).encrypt(raw)

def decrypt_bytes(token: bytes):
    key = None
    try:
        key = st.secrets["ENCRYPTION_KEY"]
    except:
        key = os.environ.get("ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("ENCRYPTION_KEY missing.")
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key).decrypt(token)

def safe_read_excel_bytes(raw: bytes):
    try:
        return pd.read_excel(io.BytesIO(raw))
    except:
        return pd.read_csv(io.BytesIO(raw), encoding="latin1", encoding_errors="ignore")

def clean_df(df):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].astype(str).str.replace("\xa0", " ", regex=False).str.strip()
    if "Brand" in df.columns:
        df["Brand"] = df["Brand"].str.upper()
    return df

# ------------------------------------------------------------
# PATH DETECTION (THIS IS THE KEY FIX)
# ------------------------------------------------------------
def get_request_path():
    try:
        return st.context.headers.get("X-Streamlit-Request-Path", "/")
    except:
        return "/"

REQUEST_PATH = get_request_path()

IS_ADMIN = REQUEST_PATH.startswith("/admin")

# ------------------------------------------------------------
# SESSION INIT
# ------------------------------------------------------------
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False
if "customer_logged_in" not in st.session_state:
    st.session_state.customer_logged_in = False
if "customer_company" not in st.session_state:
    st.session_state.customer_company = ""

# ------------------------------------------------------------
# HEADER
# ------------------------------------------------------------
st.markdown("""
<div style='font-weight:700;font-size:22px;'>DYNATRADE AUTOMOTIVE LLC</div>
<div style='font-size:13px;color:#6c757d;'>Spare Parts Ordering Portal</div>
<hr>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# ADMIN PORTAL (ONLY ON /admin)
# ------------------------------------------------------------
if IS_ADMIN:

    st.markdown("## Admin Portal")

    if not st.session_state.admin_logged_in:

        st.markdown("### Admin Login")

        with st.form("admin_login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            ok = st.form_submit_button("Login")

        if ok:
            if u == ADMIN_USERNAME and p == ADMIN_PASSWORD:
                st.session_state.admin_logged_in = True
                st.success("Admin logged in.")
                append_audit("admin_login", u, "success")
            else:
                st.error("Invalid admin credentials.")
                append_audit("admin_login_failed", u, "invalid_credentials")

        st.stop()

    # ---------------- ADMIN LOGGED IN ----------------
    st.success("Admin logged in.")

    st.markdown("### Upload Users")
    up = st.file_uploader("Upload users (.xlsx/.csv)")
    if up:
        raw = up.read()
        df = safe_read_excel_bytes(raw)
        df = clean_df(df)
        df["PasswordHash"] = df["Password"].apply(lambda x: hash_password(str(x)))
        df[["Username","PasswordHash","Customer Name","Customer Code",
            "Max search per day","Customer email ID","Sales Man name",
            "Salesman contact no.","Salesman Email ID"]].to_csv(USERS_DERIVED, index=False)
        st.success("Users uploaded and hashed.")

    st.markdown("### Upload Parts")
    up2 = st.file_uploader("Upload parts (.xlsx/.csv)")
    if up2:
        raw = up2.read()
        token = encrypt_bytes(raw)
        with open(PARTS_ENC, "wb") as f:
            f.write(token)
        st.success("Parts encrypted and stored.")

    st.stop()

# ------------------------------------------------------------
# CUSTOMER PORTAL (ONLY ON /)
# ------------------------------------------------------------
st.markdown("## Customer Portal")

if not st.session_state.customer_logged_in:

    st.markdown("### Customer Login")

    with st.form("cust_login"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        ok = st.form_submit_button("Login")

    if ok:
        if not os.path.exists(USERS_DERIVED):
            st.error("No users available. Ask admin to upload user list.")
            st.stop()

        df = pd.read_csv(USERS_DERIVED)
        row = df[df["Username"] == u]

        if row.empty:
            st.error("Invalid credentials.")
            st.stop()

        stored = row.iloc[0]["PasswordHash"]
        if verify_password(p, stored):
            st.session_state.customer_logged_in = True
            st.session_state.customer_company = row.iloc[0]["Customer Name"]
            st.success("Logged in.")
        else:
            st.error("Invalid credentials.")

    st.stop()

# ---------------- CUSTOMER LOGGED IN ----------------
st.success(f"Welcome {st.session_state.customer_company}")
st.info("Customer portal active. Search, cart, etc. can be added here.")

st.markdown("<hr>", unsafe_allow_html=True)
st.markdown("<div style='text-align:center;color:#6c757d;'>© Dynatrade Automotive Group</div>", unsafe_allow_html=True)
