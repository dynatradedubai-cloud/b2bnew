# app.py
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

st.set_page_config(page_title="Dynatrade Automotive LLC", layout="wide")

# Defaults (override with env or st.secrets)
ADMIN_USERNAME = os.environ.get("DYNATRADE_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("DYNATRADE_ADMIN_PASS", "Dyn@1234")

# Filenames
AUDIT_LOG = "audit_log.csv"
ORDERS_FILE = "orders.csv"
META_FILE = "uploads_meta.csv"
USERS_DERIVED = "users_derived.csv"
PARTS_ENC = "parts_list.enc"
USERS_ENC = "users_list.enc"
CAMPAIGNS_META = "campaigns_meta.csv"
CAMPAIGNS_DIR = "campaigns_enc"
os.makedirs(CAMPAIGNS_DIR, exist_ok=True)

# --- resilient password hashing (bcrypt optional, fallback PBKDF2) ---
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

# --- utilities ---
def now_uae_iso():
    return datetime.now(ZoneInfo("Asia/Dubai")).isoformat()

def append_audit(event: str, actor: str, details: str):
    row = {"timestamp_utc": datetime.utcnow().isoformat(), "event": event, "actor": actor, "details": details}
    try:
        if os.path.exists(AUDIT_LOG):
            df = pd.read_csv(AUDIT_LOG)
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        else:
            df = pd.DataFrame([row])
        df.to_csv(AUDIT_LOG, index=False)
    except Exception:
        pass

def load_meta():
    if os.path.exists(META_FILE):
        try:
            return pd.read_csv(META_FILE)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

def save_meta(df):
    df.to_csv(META_FILE, index=False)

def load_campaign_meta():
    if os.path.exists(CAMPAIGNS_META):
        try:
            return pd.read_csv(CAMPAIGNS_META)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

def encrypt_bytes(raw: bytes):
    key = None
    try:
        key = st.secrets["ENCRYPTION_KEY"]
    except Exception:
        key = os.environ.get("ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("ENCRYPTION_KEY missing in st.secrets or environment.")
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key).encrypt(raw)

def decrypt_bytes(token: bytes):
    key = None
    try:
        key = st.secrets["ENCRYPTION_KEY"]
    except Exception:
        key = os.environ.get("ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("ENCRYPTION_KEY missing in st.secrets or environment.")
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key).decrypt(token)

def safe_read_excel_bytes(raw: bytes):
    try:
        return pd.read_excel(io.BytesIO(raw))
    except Exception:
        try:
            return pd.read_csv(io.BytesIO(raw))
        except Exception:
            raise

def clean_df(df: pd.DataFrame):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].astype(str).str.replace("\xa0", " ", regex=False).str.strip()
    if "Brand" in df.columns:
        df["Brand"] = df["Brand"].str.upper()
    return df

# Robust query param getter
def get_query_params_safe():
    try:
        return st.experimental_get_query_params()
    except Exception:
        try:
            qs = os.environ.get("QUERY_STRING", "")
            from urllib.parse import parse_qs
            parsed = parse_qs(qs)
            return {k: v for k, v in parsed.items()}
        except Exception:
            return {}

# --- session init ---
if "parts" not in st.session_state:
    st.session_state.parts = None
if "parts_version" not in st.session_state:
    st.session_state.parts_version = None
if "cart" not in st.session_state:
    st.session_state.cart = pd.DataFrame(columns=[
        "Brand","Manufacturing Part Number","Vehicle","OE Part Number",
        "Part Description","Stock","Unit Price (AED)","Qty","Total (AED)"
    ])
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False
if "customer_logged_in" not in st.session_state:
    st.session_state.customer_logged_in = False
if "customer_company" not in st.session_state:
    st.session_state.customer_company = ""
if "campaigns_seen" not in st.session_state:
    st.session_state.campaigns_seen = {}
if "_force_admin_view" not in st.session_state:
    st.session_state._force_admin_view = False

# --- header ---
c1, c2, c3 = st.columns([0.6, 6, 2])
with c1:
    try:
        st.image("dynatrade_logo.png", width=64)
    except Exception:
        st.empty()
with c2:
    st.markdown("<div style='font-weight:700;font-size:20px;'>DYNATRADE AUTOMOTIVE LLC</div><div style='font-size:12px;color:#6c757d;'>Spare Parts Ordering Portal</div>", unsafe_allow_html=True)
with c3:
    cart_items = int(st.session_state.cart["Qty"].sum()) if not st.session_state.cart.empty else 0
    if st.session_state.customer_logged_in:
        st.markdown(f"<div style='text-align:right;color:#004080;'>Cart: {cart_items} items</div>", unsafe_allow_html=True)
        if st.button("Logout", key="hdr_logout"):
            st.session_state.customer_logged_in = False
            st.session_state.customer_company = ""
            st.success("Logged out.")
    else:
        st.markdown("<div style='text-align:right;color:#6c757d;'>Not logged in</div>", unsafe_allow_html=True)
st.markdown("<hr>", unsafe_allow_html=True)

# --- navigation and admin gating ---
params = get_query_params_safe()
is_admin_url = False
if params:
    val = params.get("admin")
    if isinstance(val, list):
        is_admin_url = val[0] == "1"
    else:
        is_admin_url = str(val) == "1"

if is_admin_url:
    st.session_state._force_admin_view = True

if st.session_state.get("_force_admin_view", False):
    mode = st.sidebar.radio("Select View", ["Admin Portal", "Customer Portal"], index=0)
    mode = "Admin Portal" if mode == "Admin Portal" else "Customer Portal"
else:
    mode = st.sidebar.radio("Select View", ["Customer Portal", "Admin Portal"])

# Diagnostic banner when admin URL detected
if is_admin_url:
    st.info(f"Admin URL detected. Query params: {params} | Active mode: {mode}")

# --- parts loader ---
@st.cache_data
def load_parts_from_enc(enc_path: str):
    if not os.path.exists(enc_path):
        raise FileNotFoundError("Encrypted parts file not found.")
    with open(enc_path, "rb") as fh:
        token = fh.read()
    raw = decrypt_bytes(token)
    try:
        df = safe_read_excel_bytes(raw)
    except Exception:
        try:
            df = pd.read_csv(io.BytesIO(raw), encoding="latin1", encoding_errors="ignore")
        except Exception as e:
            raise RuntimeError("Unable to parse decrypted parts file.") from e
    df = clean_df(df)
    rename_map = {}
    if "Manufacturing" in df.columns:
        rename_map["Manufacturing"] = "Manufacturing Part Number"
    if "Part Number" in df.columns and "OE Part Number" not in df.columns:
        rename_map["Part Number"] = "OE Part Number"
    if rename_map:
        df = df.rename(columns=rename_map)
    required = ["Brand","Manufacturing Part Number","Vehicle","OE Part Number","Part Description","Stock","Unit Price (AED)"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    df["Stock"] = pd.to_numeric(df["Stock"], errors="coerce").fillna(0).astype(int)
    df["Unit Price (AED)"] = pd.to_numeric(df["Unit Price (AED)"], errors="coerce").fillna(0.0)
    df["search_text"] = (
        df["Brand"].fillna("") + " " +
        df["Manufacturing Part Number"].astype(str).fillna("") + " " +
        df["OE Part Number"].astype(str).fillna("") + " " +
        df["Part Description"].fillna("") + " " +
        df["Vehicle"].fillna("")
    ).str.lower()
    return df

def load_parts_if_exists():
    if os.path.exists(PARTS_ENC):
        try:
            df = load_parts_from_enc(PARTS_ENC)
            st.session_state.parts = df
            st.session_state.parts_version = datetime.utcnow().isoformat()
            return df
        except Exception as e:
            st.error(f"Error loading parts: {e}")
            return None
    return None

if st.session_state.parts is None:
    try:
        load_parts_if_exists()
    except Exception:
        pass

# --- cart helpers ---
def add_to_cart_row(row: dict, qty: int):
    if qty <= 0:
        return
    cart = st.session_state.cart.copy()
    key_cols = ["Brand","Manufacturing Part Number","Vehicle","OE Part Number"]
    if cart.empty:
        mask = pd.Series([], dtype=bool)
    else:
        mask = (cart[key_cols] == pd.Series(row)[key_cols]).all(axis=1)
    if mask.any():
        idx = cart[mask].index[0]
        cart.loc[idx,"Qty"] += int(qty)
        cart.loc[idx,"Total (AED)"] = cart.loc[idx,"Qty"] * cart.loc[idx,"Unit Price (AED)"]
    else:
        new_row = {
            "Brand": row.get("Brand",""),
            "Manufacturing Part Number": row.get("Manufacturing Part Number",""),
            "Vehicle": row.get("Vehicle",""),
            "OE Part Number": row.get("OE Part Number",""),
            "Part Description": row.get("Part Description",""),
            "Stock": int(row.get("Stock",0)),
            "Unit Price (AED)": float(row.get("Unit Price (AED)",0.0)),
            "Qty": int(qty),
            "Total (AED)": int(qty) * float(row.get("Unit Price (AED)",0.0))
        }
        cart = pd.concat([cart, pd.DataFrame([new_row])], ignore_index=True)
    st.session_state.cart = cart

def remove_cart_index(idx: int):
    cart = st.session_state.cart.copy()
    if idx in cart.index:
        cart = cart.drop(idx).reset_index(drop=True)
        st.session_state.cart = cart

def clear_cart():
    st.session_state.cart = st.session_state.cart.iloc[0:0]

def cart_totals():
    if st.session_state.cart.empty:
        return 0, 0.0
    items = int(st.session_state.cart["Qty"].sum())
    total = float(st.session_state.cart["Total (AED)"].sum())
    return items, total

# --- Customer Portal (only when selected) ---
if mode == "Customer Portal":
    st.markdown("## Customer Portal")
    if not st.session_state.customer_logged_in:
        st.markdown("### Customer Login")
        with st.form("cust_login", clear_on_submit=False):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
            if submitted:
                if os.path.exists(USERS_DERIVED):
                    try:
                        users = pd.read_csv(USERS_DERIVED)
                        match = users[users["Username"].astype(str) == str(username)]
                        if not match.empty:
                            stored_hash = match.iloc[0]["PasswordHash"]
                            ok = verify_password(password, stored_hash)
                            if ok:
                                st.session_state.customer_logged_in = True
                                st.session_state.customer_company = match.iloc[0].get("Customer Name","")
                                st.success(f"Logged in as {st.session_state.customer_company}")
                                append_audit("login_success", username, f"company={st.session_state.customer_company}")
                            else:
                                st.error("Invalid credentials.")
                                append_audit("login_failed", username, "invalid_password")
                        else:
                            st.error("Invalid credentials.")
                            append_audit("login_failed", username, "user_not_found")
                    except Exception:
                        st.error("User database error.")
                else:
                    st.error("No users available. Ask admin to upload user list.")
    else:
        st.markdown(f"### Welcome, **{st.session_state.customer_company}**")
        # (search, cart, campaigns — omitted here for brevity; same as earlier)
        st.info("Customer UI active. Use search to find parts.")

# --- Admin Portal (only when selected) ---
if mode == "Admin Portal":
    st.markdown("## Admin Portal")
    if not st.session_state.admin_logged_in:
        st.markdown("### Admin Login")
        with st.form("admin_login", clear_on_submit=False):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
            if submitted:
                if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                    st.session_state.admin_logged_in = True
                    st.success("Admin logged in.")
                    append_audit("admin_login", username, "success")
                else:
                    st.error("Invalid admin credentials.")
                    append_audit("admin_login_failed", username, "invalid_credentials")
        st.markdown("<div style='font-size:12px;color:#6c757d;'>Admin UI requires ?admin=1 in URL or use the sidebar. Use environment variables for credentials.</div>", unsafe_allow_html=True)
    else:
        tabs = st.tabs(["Upload / Manage", "View Parts", "Audit & Campaigns"])
        with tabs[0]:
            st.markdown("### Upload Parts (Excel/CSV) — encrypted to .enc")
            uploaded = st.file_uploader("Upload parts file (.xlsx/.xls/.csv)", type=["xlsx","xls","csv"])
            if uploaded is not None:
                raw = uploaded.read()
                parsed_ok = False
                try:
                    df_try = safe_read_excel_bytes(raw)
                    df_try = clean_df(df_try)
                    rename_map = {}
                    if "Manufacturing" in df_try.columns:
                        rename_map["Manufacturing"] = "Manufacturing Part Number"
                    if "Part Number" in df_try.columns and "OE Part Number" not in df_try.columns:
                        rename_map["Part Number"] = "OE Part Number"
                    if rename_map:
                        df_try = df_try.rename(columns=rename_map)
                    required = ["Brand","Manufacturing Part Number","Vehicle","OE Part Number","Part Description","Stock","Unit Price (AED)"]
                    missing = [c for c in required if c not in df_try.columns]
                    if missing:
                        st.error(f"Missing required columns: {missing}. File will still be encrypted and stored.")
                    else:
                        parsed_ok = True
                except Exception:
                    st.warning("Could not parse uploaded file for validation. File will still be encrypted and stored.")
                try:
                    token = encrypt_bytes(raw)
                    with open(PARTS_ENC, "wb") as fh:
                        fh.write(token)
                    meta = load_meta()
                    row = {"id": str(uuid.uuid4()), "type":"parts", "filename_enc": PARTS_ENC, "uploaded_by": ADMIN_USERNAME, "uploaded_at_uae": now_uae_iso()}
                    meta = pd.concat([meta, pd.DataFrame([row])], ignore_index=True) if not meta.empty else pd.DataFrame([row])
                    save_meta(meta)
                    st.success("Parts file encrypted and stored.")
                    append_audit("upload_parts", ADMIN_USERNAME, f"parsed_ok={parsed_ok}")
                    if parsed_ok:
                        try:
                            df_new = clean_df(df_try)
                            df_new["Stock"] = pd.to_numeric(df_new["Stock"], errors="coerce").fillna(0).astype(int)
                            df_new["Unit Price (AED)"] = pd.to_numeric(df_new["Unit Price (AED)"], errors="coerce").fillna(0.0)
                            df_new["search_text"] = (
                                df_new["Brand"].fillna("") + " " +
                                df_new["Manufacturing Part Number"].astype(str).fillna("") + " " +
                                df_new["OE Part Number"].astype(str).fillna("") + " " +
                                df_new["Part Description"].fillna("") + " " +
                                df_new["Vehicle"].fillna("")
                            ).str.lower()
                            st.session_state.parts = df_new
                            st.session_state.parts_version = datetime.utcnow().isoformat()
                            st.success("In-memory parts updated and search index rebuilt.")
                        except Exception:
                            pass
                except Exception as e:
                    st.error(f"Encryption failed: {e}")

            st.markdown("### Upload Users (Excel/CSV) — encrypted and passwords hashed")
            uploaded_u = st.file_uploader("Upload users file (.xlsx/.xls/.csv)", type=["xlsx","xls","csv"], key="users_upload")
            if uploaded_u is not None:
                raw = uploaded_u.read()
                parsed_ok = False
                try:
                    dfu = safe_read_excel_bytes(raw)
                    dfu = clean_df(dfu)
                    required_u = ["Username","Password","Customer Name","Customer Code","Max search per day","Customer email ID","Sales Man name","Salesman contact no.","Salesman Email ID"]
                    missing_u = [c for c in required_u if c not in dfu.columns]
                    if missing_u:
                        st.error(f"Missing user columns: {missing_u}. File will still be encrypted and stored.")
                    else:
                        parsed_ok = True
                except Exception:
                    st.warning("Could not parse users file for validation. File will still be encrypted and stored.")
                try:
                    token = encrypt_bytes(raw)
                    with open(USERS_ENC, "wb") as fh:
                        fh.write(token)
                    meta = load_meta()
                    row = {"id": str(uuid.uuid4()), "type":"users", "filename_enc": USERS_ENC, "uploaded_by": ADMIN_USERNAME, "uploaded_at_uae": now_uae_iso()}
                    meta = pd.concat([meta, pd.DataFrame([row])], ignore_index=True) if not meta.empty else pd.DataFrame([row])
                    save_meta(meta)
                    st.success("Users file encrypted and stored.")
                    append_audit("upload_users", ADMIN_USERNAME, f"parsed_ok={parsed_ok}")
                    if parsed_ok:
                        try:
                            dfu2 = dfu.copy()
                            dfu2["PasswordHash"] = dfu2["Password"].apply(lambda p: hash_password(str(p)))
                            derived = dfu2[["Username","PasswordHash","Customer Name","Customer Code","Max search per day","Customer email ID","Sales Man name","Salesman contact no.","Salesman Email ID"]].copy()
                            derived.to_csv(USERS_DERIVED, index=False)
                            st.success("Derived users table created with password hashes.")
                        except Exception:
                            st.error("Failed to create derived users table.")
                except Exception as e:
                    st.error(f"Encryption failed: {e}")

            st.markdown("### Upload Campaign / Greeting (PDF/Excel/PNG/JPG) with validity")
            camp_file = st.file_uploader("Upload campaign/greeting", type=["pdf","xlsx","xls","csv","png","jpg","jpeg"], key="camp_upload")
            camp_name = st.text_input("Campaign name")
            valid_to = st.date_input("Valid until (UAE date)")
            if st.button("Upload Campaign"):
                if camp_file is None or not camp_name:
                    st.error("Provide file and campaign name.")
                else:
                    raw = camp_file.read()
                    try:
                        token = encrypt_bytes(raw)
                        cid = str(uuid.uuid4())
                        enc_name = os.path.join(CAMPAIGNS_DIR, f"{cid}.enc")
                        with open(enc_name, "wb") as fh:
                            fh.write(token)
                        cm = load_campaign_meta()
                        row = {"id": cid, "name": camp_name, "filename_enc": enc_name, "uploaded_by": ADMIN_USERNAME, "uploaded_at_uae": now_uae_iso(), "valid_to": datetime.combine(valid_to, datetime.min.time()).isoformat()}
                        cm = pd.concat([cm, pd.DataFrame([row])], ignore_index=True) if not cm.empty else pd.DataFrame([row])
                        save_campaign_meta(cm)
                        st.success("Campaign uploaded and encrypted.")
                        append_audit("upload_campaign", ADMIN_USERNAME, f"name={camp_name};valid_to={valid_to.isoformat()}")
                    except Exception as e:
                        st.error(f"Encryption failed: {e}")

            if st.button("Logout Admin"):
                st.session_state.admin_logged_in = False
                st.success("Admin logged out.")

        with tabs[1]:
            st.markdown("### Parts List (first 100 rows)")
            if st.session_state.parts is None:
                st.info("No parts loaded in memory.")
            else:
                st.write(f"Total parts in memory: {len(st.session_state.parts):,}")
                st.dataframe(st.session_state.parts.head(100), use_container_width=True)
            meta = load_meta()
            if not meta.empty:
                parts_meta = meta[meta["type"]=="parts"]
                if not parts_meta.empty:
                    last = parts_meta.iloc[-1]["uploaded_at_uae"]
                    st.markdown(f"**Parts last updated (UAE time):** {last}")

        with tabs[2]:
            st.markdown("### Audit Log (last 10)")
            if os.path.exists(AUDIT_LOG):
                try:
                    adf = pd.read_csv(AUDIT_LOG)
                    st.dataframe(adf.sort_values("timestamp_utc", ascending=False).head(10), use_container_width=True)
                    st.download_button("Download full audit", adf.to_csv(index=False), "audit_full.csv")
                except Exception:
                    st.info("Audit file exists but could not be read.")
            else:
                st.info("No audit logs yet.")
            st.markdown("### Campaigns (active)")
            cm = load_campaign_meta()
            if cm.empty:
                st.info("No campaigns uploaded.")
            else:
                now_uae = datetime.now(ZoneInfo("Asia/Dubai"))
                cm["valid_to_dt"] = pd.to_datetime(cm["valid_to"], errors="coerce")
                active = cm[cm["valid_to_dt"] >= now_uae]
                if active.empty:
                    st.info("No active campaigns.")
                else:
                    st.dataframe(active[["id","name","uploaded_at_uae","valid_to"]], use_container_width=True)

# footer
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown("<div style='text-align:center;color:#6c757d;'>© Dynatrade Automotive Group – B2B Customer Portal</div>", unsafe_allow_html=True)
