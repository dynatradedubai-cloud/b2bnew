# ============================================================
# Dynatrade B2B Portal - Single File App
# Secure Admin Path: /admin   |   Customer Portal: /
# Under 800 lines
# ============================================================

import os
import io
import uuid
import hashlib
import binascii
import warnings
import pandas as pd
import streamlit as st
from datetime import datetime, date
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
USERS_DERIVED = "users_derived.csv"
PARTS_ENC = "parts_list.enc"
USERS_ENC = "users_list.enc"
CAMPAIGNS_META = "campaigns_meta.csv"
CAMPAIGNS_DIR = "campaigns_enc"
os.makedirs(CAMPAIGNS_DIR, exist_ok=True)

# ------------------------------------------------------------
# PASSWORD HASHING (bcrypt optional, PBKDF2 fallback)
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
        "details": details,
    }
    try:
        if os.path.exists(AUDIT_LOG):
            df = pd.read_csv(AUDIT_LOG)
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        else:
            df = pd.DataFrame([row])
        df.to_csv(AUDIT_LOG, index=False)
    except Exception:
        pass

def encrypt_bytes(raw: bytes):
    key = None
    try:
        key = st.secrets["ENCRYPTION_KEY"]
    except Exception:
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
    except Exception:
        key = os.environ.get("ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("ENCRYPTION_KEY missing.")
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key).decrypt(token)

def safe_read_excel_bytes(raw: bytes):
    try:
        return pd.read_excel(io.BytesIO(raw))
    except Exception:
        return pd.read_csv(io.BytesIO(raw), encoding="latin1", encoding_errors="ignore")

def clean_df(df: pd.DataFrame):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].astype(str).str.replace("\xa0", " ", regex=False).str.strip()
    if "Brand" in df.columns:
        df["Brand"] = df["Brand"].str.upper()
    return df

def load_campaign_meta():
    if os.path.exists(CAMPAIGNS_META):
        try:
            return pd.read_csv(CAMPAIGNS_META)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

def save_campaign_meta(df: pd.DataFrame):
    df.to_csv(CAMPAIGNS_META, index=False)

# ------------------------------------------------------------
# PATH DETECTION (KEY FOR /admin)
# ------------------------------------------------------------
def get_request_path():
    # Streamlit Cloud exposes full URI here, e.g. "/admin" or "/"
    uri = os.environ.get("STREAMLIT_SERVER_REQUEST_URI", "/")
    # Strip query string if present
    return uri.split("?", 1)[0]

REQUEST_PATH = get_request_path()
IS_ADMIN = REQUEST_PATH.rstrip("/").endswith("/admin")

# ------------------------------------------------------------
# SESSION INIT
# ------------------------------------------------------------
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False
if "customer_logged_in" not in st.session_state:
    st.session_state.customer_logged_in = False
if "customer_company" not in st.session_state:
    st.session_state.customer_company = ""
if "cart" not in st.session_state:
    st.session_state.cart = pd.DataFrame(
        columns=[
            "Brand",
            "Manufacturing Part Number",
            "Vehicle",
            "OE Part Number",
            "Part Description",
            "Stock",
            "Unit Price (AED)",
            "Qty",
            "Total (AED)",
        ]
    )
if "parts" not in st.session_state:
    st.session_state.parts = None
if "campaigns_seen" not in st.session_state:
    st.session_state.campaigns_seen = {}

# ------------------------------------------------------------
# HEADER
# ------------------------------------------------------------
st.markdown(
    """
<div style='font-weight:700;font-size:22px;'>DYNATRADE AUTOMOTIVE LLC</div>
<div style='font-size:13px;color:#6c757d;'>Spare Parts Ordering Portal</div>
<hr>
""",
    unsafe_allow_html=True,
)

# ------------------------------------------------------------
# PARTS LOADING
# ------------------------------------------------------------
@st.cache_data
def load_parts_from_enc(path: str):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        token = f.read()
    raw = decrypt_bytes(token)
    df = safe_read_excel_bytes(raw)
    df = clean_df(df)
    rename_map = {}
    if "Manufacturing" in df.columns:
        rename_map["Manufacturing"] = "Manufacturing Part Number"
    if "Part Number" in df.columns and "OE Part Number" not in df.columns:
        rename_map["Part Number"] = "OE Part Number"
    if rename_map:
        df = df.rename(columns=rename_map)
    required = [
        "Brand",
        "Manufacturing Part Number",
        "Vehicle",
        "OE Part Number",
        "Part Description",
        "Stock",
        "Unit Price (AED)",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    df["Stock"] = pd.to_numeric(df["Stock"], errors="coerce").fillna(0).astype(int)
    df["Unit Price (AED)"] = pd.to_numeric(df["Unit Price (AED)"], errors="coerce").fillna(0.0)
    df["search_text"] = (
        df["Brand"].fillna("")
        + " "
        + df["Manufacturing Part Number"].astype(str).fillna("")
        + " "
        + df["OE Part Number"].astype(str).fillna("")
        + " "
        + df["Part Description"].fillna("")
        + " "
        + df["Vehicle"].fillna("")
    ).str.lower()
    return df

def ensure_parts_loaded():
    if st.session_state.parts is None and os.path.exists(PARTS_ENC):
        try:
            st.session_state.parts = load_parts_from_enc(PARTS_ENC)
        except Exception as e:
            st.error(f"Error loading parts: {e}")

# ------------------------------------------------------------
# CART HELPERS
# ------------------------------------------------------------
def add_to_cart_row(row: dict, qty: int):
    if qty <= 0:
        return
    cart = st.session_state.cart.copy()
    key_cols = ["Brand", "Manufacturing Part Number", "Vehicle", "OE Part Number"]
    if cart.empty:
        mask = pd.Series([], dtype=bool)
    else:
        mask = (cart[key_cols] == pd.Series(row)[key_cols]).all(axis=1)
    if mask.any():
        idx = cart[mask].index[0]
        cart.loc[idx, "Qty"] += int(qty)
        cart.loc[idx, "Total (AED)"] = cart.loc[idx, "Qty"] * cart.loc[idx, "Unit Price (AED)"]
    else:
        new_row = {
            "Brand": row.get("Brand", ""),
            "Manufacturing Part Number": row.get("Manufacturing Part Number", ""),
            "Vehicle": row.get("Vehicle", ""),
            "OE Part Number": row.get("OE Part Number", ""),
            "Part Description": row.get("Part Description", ""),
            "Stock": int(row.get("Stock", 0)),
            "Unit Price (AED)": float(row.get("Unit Price (AED)", 0.0)),
            "Qty": int(qty),
            "Total (AED)": int(qty) * float(row.get("Unit Price (AED)", 0.0)),
        }
        cart = pd.concat([cart, pd.DataFrame([new_row])], ignore_index=True)
    st.session_state.cart = cart

def clear_cart():
    st.session_state.cart = st.session_state.cart.iloc[0:0]

def cart_totals():
    if st.session_state.cart.empty:
        return 0, 0.0
    items = int(st.session_state.cart["Qty"].sum())
    total = float(st.session_state.cart["Total (AED)"].sum())
    return items, total

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

    tabs = st.tabs(["Users", "Parts", "Campaigns", "Audit"])

    # --- USERS TAB ---
    with tabs[0]:
        st.markdown("### Upload Users (Excel/CSV)")
        up = st.file_uploader("Upload users file", type=["xlsx", "xls", "csv"])
        if up:
            raw = up.read()
            df = safe_read_excel_bytes(raw)
            df = clean_df(df)
            required_u = [
                "Username",
                "Password",
                "Customer Name",
                "Customer Code",
                "Max search per day",
                "Customer email ID",
                "Sales Man name",
                "Salesman contact no.",
                "Salesman Email ID",
            ]
            missing_u = [c for c in required_u if c not in df.columns]
            if missing_u:
                st.error(f"Missing user columns: {missing_u}")
            else:
                df["PasswordHash"] = df["Password"].apply(lambda x: hash_password(str(x)))
                derived = df[
                    [
                        "Username",
                        "PasswordHash",
                        "Customer Name",
                        "Customer Code",
                        "Max search per day",
                        "Customer email ID",
                        "Sales Man name",
                        "Salesman contact no.",
                        "Salesman Email ID",
                    ]
                ].copy()
                derived.to_csv(USERS_DERIVED, index=False)
                st.success("Users uploaded and hashed.")
                append_audit("upload_users", ADMIN_USERNAME, f"rows={len(derived)}")

    # --- PARTS TAB ---
    with tabs[1]:
        st.markdown("### Upload Parts (Excel/CSV)")
        up2 = st.file_uploader("Upload parts file", type=["xlsx", "xls", "csv"])
        if up2:
            raw = up2.read()
            try:
                token = encrypt_bytes(raw)
                with open(PARTS_ENC, "wb") as f:
                    f.write(token)
                st.success("Parts encrypted and stored.")
                append_audit("upload_parts", ADMIN_USERNAME, "ok")
                st.session_state.parts = load_parts_from_enc(PARTS_ENC)
            except Exception as e:
                st.error(f"Failed to encrypt/store parts: {e}")
        ensure_parts_loaded()
        if st.session_state.parts is not None:
            st.markdown("#### Sample of Parts (first 50 rows)")
            st.dataframe(st.session_state.parts.head(50), use_container_width=True)
        else:
            st.info("No parts loaded yet.")

    # --- CAMPAIGNS TAB ---
    with tabs[2]:
        st.markdown("### Upload Campaign / Greeting")
        camp_file = st.file_uploader(
            "Upload campaign (PDF/Excel/Image)", type=["pdf", "xlsx", "xls", "csv", "png", "jpg", "jpeg"]
        )
        camp_name = st.text_input("Campaign name")
        valid_to = st.date_input("Valid until (UAE date)", value=date.today())
        if st.button("Upload Campaign"):
            if not camp_file or not camp_name:
                st.error("Provide file and campaign name.")
            else:
                raw = camp_file.read()
                try:
                    token = encrypt_bytes(raw)
                    cid = str(uuid.uuid4())
                    enc_name = os.path.join(CAMPAIGNS_DIR, f"{cid}.enc")
                    with open(enc_name, "wb") as f:
                        f.write(token)
                    cm = load_campaign_meta()
                    row = {
                        "id": cid,
                        "name": camp_name,
                        "filename_enc": enc_name,
                        "uploaded_by": ADMIN_USERNAME,
                        "uploaded_at_uae": now_uae_iso(),
                        "valid_to": datetime.combine(valid_to, datetime.min.time()).isoformat(),
                    }
                    cm = pd.concat([cm, pd.DataFrame([row])], ignore_index=True) if not cm.empty else pd.DataFrame([row])
                    save_campaign_meta(cm)
                    st.success("Campaign uploaded and encrypted.")
                    append_audit("upload_campaign", ADMIN_USERNAME, f"name={camp_name}")
                except Exception as e:
                    st.error(f"Failed to encrypt/store campaign: {e}")

        st.markdown("#### Active Campaigns")
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
                st.dataframe(active[["id", "name", "uploaded_at_uae", "valid_to"]], use_container_width=True)

    # --- AUDIT TAB ---
    with tabs[3]:
        st.markdown("### Audit Log (last 50)")
        if os.path.exists(AUDIT_LOG):
            try:
                adf = pd.read_csv(AUDIT_LOG)
                adf = adf.sort_values("timestamp_utc", ascending=False).head(50)
                st.dataframe(adf, use_container_width=True)
                st.download_button("Download full audit", adf.to_csv(index=False), "audit_log.csv")
            except Exception:
                st.info("Audit file exists but could not be read.")
        else:
            st.info("No audit logs yet.")

    st.stop()

# ------------------------------------------------------------
# CUSTOMER PORTAL (ONLY ON /)
# ------------------------------------------------------------
st.markdown("## Customer Portal")

# --- CUSTOMER LOGIN ---
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
        row = df[df["Username"].astype(str) == str(u)]
        if row.empty:
            st.error("Invalid credentials.")
            append_audit("login_failed", u, "user_not_found")
            st.stop()
        stored = row.iloc[0]["PasswordHash"]
        if verify_password(p, stored):
            st.session_state.customer_logged_in = True
            st.session_state.customer_company = row.iloc[0]["Customer Name"]
            st.success(f"Welcome {st.session_state.customer_company}")
            append_audit("login_success", u, f"company={st.session_state.customer_company}")
        else:
            st.error("Invalid credentials.")
            append_audit("login_failed", u, "invalid_password")
    st.stop()

# ---------------- CUSTOMER LOGGED IN ----------------
st.success(f"Welcome {st.session_state.customer_company}")

# --- CAMPAIGN BELL ---
cm = load_campaign_meta()
active_campaigns = []
if not cm.empty:
    now_uae = datetime.now(ZoneInfo("Asia/Dubai"))
    cm["valid_to_dt"] = pd.to_datetime(cm["valid_to"], errors="coerce")
    active_campaigns = cm[cm["valid_to_dt"] >= now_uae].to_dict("records")

cust_key = st.session_state.customer_company or "guest"
seen_set = set(st.session_state.campaigns_seen.get(cust_key, []))
unseen = [c for c in active_campaigns if c["id"] not in seen_set]
if unseen:
    st.markdown(
        f"<div style='text-align:right;font-size:16px;color:#d9534f;'>🔔 New Campaigns ({len(unseen)})</div>",
        unsafe_allow_html=True,
    )
    if st.button("Mark campaigns as seen"):
        seen_set.update([c["id"] for c in unseen])
        st.session_state.campaigns_seen[cust_key] = list(seen_set)
else:
    st.markdown(
        "<div style='text-align:right;font-size:14px;color:#6c757d;'>🔔 No new campaigns</div>",
        unsafe_allow_html=True,
    )

# --- SEARCH ---
ensure_parts_loaded()
st.markdown("### Search Parts")
query = st.text_input("Search Part Number / OE / Description / Brand / Vehicle")
if st.button("Search"):
    if not query.strip():
        st.info("Enter a search term.")
    elif st.session_state.parts is None:
        st.error("No parts loaded. Ask admin to upload price list.")
    else:
        q = query.strip().lower()
        parts = st.session_state.parts
        mask = parts["search_text"].str.contains(q, na=False)
        results = parts[mask].copy()
        append_audit("search", st.session_state.customer_company, f"query={query};results={len(results)}")
        if results.empty:
            st.warning("No results found.")
        else:
            st.markdown(f"**Found {len(results)} results (showing first 50)**")
            display = results.head(50).reset_index(drop=True)
            cols = st.columns([1.2, 2.4, 1.2, 1.2, 1.0, 0.8, 0.8, 0.6, 0.6])
            headers = [
                "Brand",
                "Part Description",
                "Manufacturing PN",
                "OE PN",
                "Vehicle",
                "Stock",
                "Unit Price (AED)",
                "Qty",
                "Add",
            ]
            for c, h in zip(cols, headers):
                c.markdown(f"**{h}**")
            for i, row in display.iterrows():
                cols = st.columns([1.2, 2.4, 1.2, 1.2, 1.0, 0.8, 0.8, 0.6, 0.6])
                cols[0].write(row.get("Brand", ""))
                cols[1].write(row.get("Part Description", ""))
                cols[2].write(row.get("Manufacturing Part Number", ""))
                cols[3].write(row.get("OE Part Number", ""))
                cols[4].write(row.get("Vehicle", ""))
                cols[5].write(int(row.get("Stock", 0)))
                cols[6].write(f"AED {row.get('Unit Price (AED)', 0.0):,.2f}")
                max_stock = int(row.get("Stock", 0))
                qty_val = cols[7].number_input(
                    "",
                    min_value=0,
                    max_value=max_stock if max_stock > 0 else 999999,
                    value=0,
                    key=f"qty_{i}",
                )
                if cols[8].button("Add", key=f"add_{i}"):
                    if qty_val <= 0:
                        st.warning("Enter quantity > 0")
                    elif max_stock and qty_val > max_stock:
                        st.error("Quantity exceeds stock")
                    else:
                        add_to_cart_row(row.to_dict(), int(qty_val))
                        st.success(
                            f"Added {int(qty_val)} x {row.get('Manufacturing Part Number','')} to cart."
                        )

# --- CART ---
st.markdown("### Your Cart")
if st.button("Clear Cart"):
    clear_cart()
cart = st.session_state.cart.copy()
if cart.empty:
    st.info("Cart is empty.")
else:
    for idx, r in cart.iterrows():
        cols = st.columns([1.2, 2.4, 1.2, 1.2, 1.0, 0.8, 0.8, 0.6])
        cols[0].write(r["Brand"])
        cols[1].write(r["Part Description"])
        cols[2].write(r["Manufacturing Part Number"])
        cols[3].write(r["OE Part Number"])
        cols[4].write(r["Vehicle"])
        cols[5].write(int(r["Stock"]))
        cols[6].write(f"AED {r['Unit Price (AED)']:,.2f}")
        cols[7].write(f"Qty: {int(r['Qty'])}")
    items, total = cart_totals()
    st.markdown(f"**Items: {items} | Cart Total: AED {total:,.2f}**")
    st.download_button("Download Cart (CSV)", cart.to_csv(index=False), "cart.csv")

    notes = st.text_area("Order Notes (optional)")
    if st.button("Submit Order"):
        order_id = str(uuid.uuid4())[:8].upper()
        timestamp = datetime.utcnow().isoformat()
        customer = st.session_state.customer_company or "UNKNOWN"
        items_list = []
        for _, r in cart.iterrows():
            items_list.append(
                {
                    "Manufacturing Part Number": r["Manufacturing Part Number"],
                    "Part Description": r["Part Description"],
                    "Qty": int(r["Qty"]),
                    "Unit Price (AED)": float(r["Unit Price (AED)"]),
                    "Total (AED)": float(r["Total (AED)"]),
                }
            )
        order_total = float(cart["Total (AED)"].sum())
        order_row = {
            "order_id": order_id,
            "timestamp_utc": timestamp,
            "customer": customer,
            "items_count": len(items_list),
            "order_total_aed": order_total,
            "notes": notes,
            "items_serialized": str(items_list),
        }
        try:
            if os.path.exists(ORDERS_FILE):
                odf = pd.read_csv(ORDERS_FILE)
                odf = pd.concat([odf, pd.DataFrame([order_row])], ignore_index=True)
            else:
                odf = pd.DataFrame([order_row])
            odf.to_csv(ORDERS_FILE, index=False)
        except Exception:
            pass
        append_audit("order_submitted", customer, f"order_id={order_id};total={order_total}")
        clear_cart()
        st.success(f"Order {order_id} submitted. Prepare email to sales.")
        body_lines = [
            f"Order ID: {order_id}",
            f"Customer: {customer}",
            f"Total AED: {order_total:,.2f}",
            "",
            "Items:",
        ]
        for it in items_list:
            body_lines.append(
                f"{it['Manufacturing Part Number']} | {it['Part Description']} | Qty {it['Qty']} | AED {it['Total (AED)']:.2f}"
            )
        if notes:
            body_lines.append("")
            body_lines.append("Notes:")
            body_lines.append(notes)
        body_text = "%0D%0A".join(body_lines)
        mailto = f"mailto:sales@dynatrade.com?subject=New%20Order%20{order_id}&body={body_text}"
        st.markdown(f"[Open email to Sales]({mailto})")

st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(
    "<div style='text-align:center;color:#6c757d;'>© Dynatrade Automotive Group – B2B Customer Portal</div>",
    unsafe_allow_html=True,
)
