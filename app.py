import os
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------
st.set_page_config(page_title="Dynatrade Automotive LLC", layout="wide")

# Admin credentials from environment variables (change in deployment)
ADMIN_USERNAME = os.environ.get("DYNATRADE_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("DYNATRADE_ADMIN_PASS", "Dyn@1234")

# Audit log file (local)
AUDIT_LOG_FILE = "audit_log.csv"

# ---------------------------------------------------------
# THEME / CSS
# ---------------------------------------------------------
st.markdown("""
<style>
html, body, [class*="css"] { font-family: 'Segoe UI', sans-serif; }
.header-bar { background-color:#004080;padding:12px 20px;border-radius:6px;color:white; display:flex; align-items:center; }
.header-title { font-size:22px;font-weight:700;margin-left:12px;color:white !important; }
.header-subtitle { font-size:12px;color:#d9e6ff !important;margin-top:2px; }
.header-right { margin-left:auto;color:white !important;font-size:14px; text-align:right; }
.search-card { background-color:#F5F5F5;padding:12px;border-radius:8px;border:1px solid #E0E0E0; }
thead tr th { background-color:#004080 !important;color:white !important;font-weight:600 !important;text-align:center !important; }
tbody tr:nth-child(even) { background-color:#F8F8F8 !important; }
tbody tr:nth-child(odd) { background-color:#FFFFFF !important; }
.stButton>button { background-color:#004080 !important;color:white !important;border-radius:6px !important;padding:8px 14px !important;border:none !important;font-weight:600 !important; }
.stButton>button:hover { background-color:#003366 !important;color:white !important; }
.stLinkButton>a { background-color:#004080 !important;color:white !important;padding:8px 14px !important;border-radius:6px !important;text-decoration:none !important;font-weight:600 !important; }
.stLinkButton>a:hover { background-color:#003366 !important; }
.footer { text-align:center;color:grey;margin-top:30px;font-size:13px; }
.small-muted { color: #6c757d; font-size:12px; }
.result-row { padding:8px 0; border-bottom:1px solid #eee; display:flex; align-items:center; }
.result-col { padding:4px 8px; }
.qty-input { width:80px; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# SESSION STATE INIT
# ---------------------------------------------------------
if "cart" not in st.session_state:
    st.session_state.cart = pd.DataFrame(columns=[
        "Brand", "Manufacturing Part Number", "Vehicle", "OE Part Number",
        "Part Description", "Stock", "Unit Price (AED)", "Qty", "Total (AED)"
    ])

if "parts" not in st.session_state:
    st.session_state.parts = None

if "customers" not in st.session_state:
    st.session_state.customers = None

if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

if "customer_logged_in" not in st.session_state:
    st.session_state.customer_logged_in = False

if "customer_company" not in st.session_state:
    st.session_state.customer_company = ""

if "results_page" not in st.session_state:
    st.session_state.results_page = 0

# ---------------------------------------------------------
# UTILITIES: CLEANING, LOADING, VALIDATION, AUDIT
# ---------------------------------------------------------
def append_audit(action: str, actor: str, details: str):
    """Append an audit row to local CSV (timestamp, action, actor, details)."""
    row = {"timestamp": datetime.utcnow().isoformat(), "action": action, "actor": actor, "details": details}
    try:
        if os.path.exists(AUDIT_LOG_FILE):
            df = pd.read_csv(AUDIT_LOG_FILE)
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        else:
            df = pd.DataFrame([row])
        df.to_csv(AUDIT_LOG_FILE, index=False)
    except Exception:
        # best-effort; do not crash app if audit fails
        pass

def clean_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).str.replace("\xa0", " ", regex=False).str.strip()
    if "Brand" in df.columns:
        df["Brand"] = df["Brand"].str.upper()
    return df

@st.cache_data
def load_parts_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="latin1", encoding_errors="ignore")
    df = clean_df(df)
    rename_map = {}
    if "Manufacturing" in df.columns:
        rename_map["Manufacturing"] = "Manufacturing Part Number"
    if "Part Number" in df.columns and "OE Part Number" not in df.columns:
        rename_map["Part Number"] = "OE Part Number"
    if rename_map:
        df = df.rename(columns=rename_map)
    required = [
        "Brand", "Manufacturing Part Number", "Vehicle",
        "OE Part Number", "Part Description", "Stock", "Unit Price (AED)"
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    df["Stock"] = pd.to_numeric(df["Stock"], errors="coerce").fillna(0).astype(int)
    df["Unit Price (AED)"] = pd.to_numeric(df["Unit Price (AED)"], errors="coerce").fillna(0.0)
    return df

def get_parts_df() -> pd.DataFrame:
    if st.session_state.parts is not None:
        return st.session_state.parts
    try:
        df = load_parts_csv("parts_list.csv")
        st.session_state.parts = df
        return df
    except Exception:
        # fallback sample data for UI testing
        df = pd.DataFrame([
            ["DAIMLER AG","5503","DAIMLER AG","A000000005503","HEXAGON HEAD BOLT-M24X2X190",12,32.28],
            ["BOSCH","A000000001066","DAIMLER AG","000000001066","SEAL RING,FUEL LINES-AXOR",3,2.11],
            ["FEBI","A000000001073","DAIMLER AG","000000001073","SEAL RING, OIL DRAIN PLUG",10,2.32],
        ], columns=[
            "Brand","Manufacturing Part Number","Vehicle","OE Part Number",
            "Part Description","Stock","Unit Price (AED)"
        ])
        st.session_state.parts = df
        return df

# ---------------------------------------------------------
# HEADER (logo + title + logout + cart count)
# ---------------------------------------------------------
header_cols = st.columns([0.6, 6, 2])
with header_cols[0]:
    # logo if present
    try:
        st.image("dynatrade_logo.png", width=64)
    except Exception:
        st.empty()
with header_cols[1]:
    st.markdown("<div style='display:flex;align-items:center;'>"
                "<div style='margin-left:8px;'>"
                "<div class='header-title'>DYNATRADE AUTOMOTIVE LLC</div>"
                "<div class='header-subtitle'>Spare Parts Ordering Portal</div>"
                "</div></div>", unsafe_allow_html=True)
with header_cols[2]:
    # cart count and logout for customer
    cart_items = int(st.session_state.cart["Qty"].sum()) if not st.session_state.cart.empty else 0
    if st.session_state.customer_logged_in:
        st.markdown(f"<div style='text-align:right;color:#fff;'>Cart: {cart_items} items</div>", unsafe_allow_html=True)
        if st.button("Logout", key="header_logout"):
            st.session_state.customer_logged_in = False
            st.session_state.customer_company = ""
            st.success("You have been logged out.")
    else:
        st.markdown("<div style='text-align:right;color:#fff;'>Not logged in</div>", unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)

# ---------------------------------------------------------
# NAVIGATION
# ---------------------------------------------------------
mode = st.sidebar.radio("Select View", ["Customer Portal", "Admin Portal"])

# ---------------------------------------------------------
# CART HELPERS (add per-row, remove, clear)
# ---------------------------------------------------------
def add_to_cart_row(row: dict, qty: int):
    if qty <= 0:
        return
    cart = st.session_state.cart.copy()
    key_cols = ["Brand", "Manufacturing Part Number", "Vehicle", "OE Part Number"]
    if cart.empty:
        mask = pd.Series([], dtype=bool)
    else:
        # create boolean mask comparing key columns
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
            "Total (AED)": int(qty) * float(row.get("Unit Price (AED)", 0.0))
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

# ---------------------------------------------------------
# CUSTOMER PORTAL
# ---------------------------------------------------------
if mode == "Customer Portal":
    st.markdown("## Customer Portal")

    # Customer login area
    if not st.session_state.customer_logged_in:
        st.markdown("### Customer Login")
        with st.form("customer_login", clear_on_submit=False):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
            if submitted:
                cust_df = st.session_state.customers
                if cust_df is None:
                    st.error("No customer list available. Ask admin to upload customers CSV in Admin Portal.")
                else:
                    match = cust_df[
                        (cust_df["Username"].astype(str) == str(username)) &
                        (cust_df["Password"].astype(str) == str(password))
                    ]
                    if not match.empty:
                        st.session_state.customer_logged_in = True
                        st.session_state.customer_company = match.iloc[0]["Company"]
                        st.success(f"Logged in as {st.session_state.customer_company}")
                    else:
                        st.error("Invalid username or password.")
        st.markdown("<div class='small-muted'>If you don't have credentials, contact your Dynatrade admin.</div>", unsafe_allow_html=True)
    else:
        # Logged in: single search box only
        st.markdown(f"### Welcome, **{st.session_state.customer_company}**")
        query = st.text_input("Search Part Number / OE / Description / Brand / Vehicle", key="cust_search_box", value="")
        search_clicked = st.button("Search")
        # Only show results after query non-empty and search clicked or Enter used
        results_df = pd.DataFrame()
        if query and query.strip() != "":
            df = get_parts_df().copy()
            q = query.strip().lower()
            mask = df.apply(lambda r:
                q in str(r.get("Manufacturing Part Number", "")).lower() or
                q in str(r.get("OE Part Number", "")).lower() or
                q in str(r.get("Part Description", "")).lower() or
                q in str(r.get("Brand", "")).lower() or
                q in str(r.get("Vehicle", "")).lower()
            , axis=1)
            results_df = df[mask].copy()
            st.session_state.results_page = 0
        elif search_clicked:
            st.info("Enter a search term to find parts.")

        # Render results only if present
        if not results_df.empty:
            total_results = len(results_df)
            st.markdown(f"**{total_results:,} results found — showing first 100**")
            display_df = results_df.head(100).reset_index(drop=True)
            # header row
            cols = st.columns([1.2, 2.4, 1.2, 1.2, 1.0, 0.8, 0.8])
            headers = ["Brand", "Description", "Manufacturing PN", "OE PN", "Vehicle", "Qty", "Add"]
            for c, h in zip(cols, headers):
                c.markdown(f"**{h}**")
            # rows
            for i, row in display_df.iterrows():
                cols = st.columns([1.2, 2.4, 1.2, 1.2, 1.0, 0.8, 0.8])
                cols[0].write(row.get("Brand", ""))
                cols[1].write(row.get("Part Description", ""))
                cols[2].write(row.get("Manufacturing Part Number", ""))
                cols[3].write(row.get("OE Part Number", ""))
                cols[4].write(row.get("Vehicle", ""))
                qty_key = f"qty_{i}"
                max_stock = int(row.get("Stock", 0)) if pd.notna(row.get("Stock", None)) else 0
                qty_val = cols[5].number_input("", min_value=0, max_value=max_stock if max_stock>0 else 999999, value=0, key=qty_key)
                add_key = f"add_{i}"
                if cols[6].button("Add", key=add_key):
                    if qty_val <= 0:
                        st.warning("Enter quantity > 0 to add.")
                    elif max_stock and qty_val > max_stock:
                        st.error("Quantity exceeds available stock.")
                    else:
                        add_to_cart_row(row.to_dict(), int(qty_val))
                        st.success(f"Added {int(qty_val)} x {row.get('Manufacturing Part Number','')} to cart.")
            st.markdown("---")
        else:
            st.info("No results to display. Use the search box above to find parts.")

        # Cart summary and actions
        st.markdown("### Your Cart")
        if st.button("🗑 Clear Cart"):
            clear_cart()
        cart_df = st.session_state.cart.copy()
        if cart_df.empty:
            st.info("Cart is empty.")
        else:
            # show cart with remove buttons
            cart_display = cart_df.copy()
            cart_display["Qty"] = cart_display["Qty"].astype(int)
            # render table-like rows with remove
            st.write("")
            for idx, r in cart_display.iterrows():
                cols = st.columns([1.2, 2.4, 1.2, 1.2, 1.0, 0.8, 0.8])
                cols[0].write(r["Brand"])
                cols[1].write(r["Part Description"])
                cols[2].write(r["Manufacturing Part Number"])
                cols[3].write(r["OE Part Number"])
                cols[4].write(r["Vehicle"])
                cols[5].write(f"Qty: {int(r['Qty'])}")
                if cols[6].button("Remove", key=f"remove_{idx}"):
                    remove_cart_index(idx)
                    st.experimental_rerun()
        items, total = cart_totals()
        st.markdown(f"**Items: {items} | Cart Total: AED {total:,.2f}**")
        if not cart_df.empty:
            st.download_button("⬇ Download Cart (CSV)", cart_df.to_csv(index=False), "cart.csv")
            body_lines = []
            for _, r in cart_df.iterrows():
                body_lines.append(
                    f"{r['Brand']} | {r['Manufacturing Part Number']} | {r['Part Description']} | Qty: {int(r['Qty'])} | Total: AED {r['Total (AED)']:.2f}"
                )
            body_text = "%0D%0A".join(body_lines)
            st.link_button("📧 Send to Salesman (Email)", f"mailto:sales@dynatrade.com?subject=Parts%20Cart&body={body_text}")
            wa_text = body_text.replace("%0D%0A", "%0A")
            st.link_button("🟢 Send via WhatsApp", f"https://wa.me/971XXXXXXXXX?text={wa_text}")

# ---------------------------------------------------------
# ADMIN PORTAL
# ---------------------------------------------------------
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
                else:
                    st.error("Invalid admin credentials.")
        st.markdown("<div class='small-muted'>Admin credentials come from environment variables DYNATRADE_ADMIN_USER / DYNATRADE_ADMIN_PASS. Defaults are 'admin' / 'Dyn@1234'. Change before production.</div>", unsafe_allow_html=True)
    else:
        tab1, tab2, tab3 = st.tabs(["Upload / Manage", "View Parts", "Dashboard"])
        with tab1:
            st.markdown("### Upload Parts CSV")
            st.write("Required columns: Brand, Manufacturing Part Number, Vehicle, OE Part Number, Part Description, Stock, Unit Price (AED)")
            uploaded = st.file_uploader("Upload parts CSV", type=["csv"])
            if uploaded is not None:
                try:
                    df_new = pd.read_csv(uploaded, encoding="latin1", encoding_errors="ignore")
                    df_new = clean_df(df_new)
                    rename_map = {}
                    if "Manufacturing" in df_new.columns:
                        rename_map["Manufacturing"] = "Manufacturing Part Number"
                    if "Part Number" in df_new.columns and "OE Part Number" not in df_new.columns:
                        rename_map["Part Number"] = "OE Part Number"
                    if rename_map:
                        df_new = df_new.rename(columns=rename_map)
                    required = ["Brand","Manufacturing Part Number","Vehicle","OE Part Number","Part Description","Stock","Unit Price (AED)"]
                    missing = [c for c in required if c not in df_new.columns]
                    if missing:
                        st.error(f"Missing columns: {missing}")
                    else:
                        df_new["Stock"] = pd.to_numeric(df_new["Stock"], errors="coerce").fillna(0).astype(int)
                        df_new["Unit Price (AED)"] = pd.to_numeric(df_new["Unit Price (AED)"], errors="coerce").fillna(0.0)
                        st.session_state.parts = df_new
                        st.success(f"Loaded {len(df_new):,} parts into memory.")
                        append_audit("upload_parts", username, f"rows={len(df_new)}")
                except Exception as e:
                    st.error(f"Error reading file: {e}")

            st.markdown("### Upload Customers CSV (for customer login)")
            st.write("Required columns: Company, Username, Password")
            cust_file = st.file_uploader("Upload customers CSV", type=["csv"], key="cust_upload")
            if cust_file is not None:
                try:
                    cust_df = pd.read_csv(cust_file, encoding="latin1", encoding_errors="ignore")
                    cust_df = clean_df(cust_df)
                    required_c = ["Company","Username","Password"]
                    missing_c = [c for c in required_c if c not in cust_df.columns]
                    if missing_c:
                        st.error(f"Missing customer columns: {missing_c}")
                    else:
                        st.session_state.customers = cust_df[required_c].copy()
                        st.success(f"Loaded {len(cust_df):,} customers.")
                        append_audit("upload_customers", username, f"rows={len(cust_df)}")
                except Exception as e:
                    st.error(f"Error reading customers file: {e}")

            if st.button("Logout Admin"):
                st.session_state.admin_logged_in = False
                st.success("Admin logged out.")

        with tab2:
            st.markdown("### Parts List (first 100 rows)")
            df = get_parts_df()
            st.write(f"Total parts in memory: {len(df):,}")
            st.dataframe(df.head(100), use_container_width=True)

        with tab3:
            st.markdown("### Dashboard")
            df = get_parts_df()
            total_parts = len(df)
            total_brands = df["Brand"].nunique() if "Brand" in df.columns else 0
            total_stock = int(df["Stock"].sum()) if "Stock" in df.columns else 0
            c1, c2, c3 = st.columns(3)
            c1.metric("Total SKUs", f"{total_parts:,}")
            c2.metric("Brands", f"{total_brands:,}")
            c3.metric("Total Stock Units", f"{total_stock:,}")
            if "Unit Price (AED)" in df.columns:
                df["Stock Value"] = df["Stock"] * df["Unit Price (AED)"]
                st.metric("Estimated Stock Value (AED)", f"{df['Stock Value'].sum():,.2f}")
            if "Stock" in df.columns:
                st.markdown("#### Top 10 Parts by Stock")
                st.dataframe(df.sort_values("Stock", ascending=False).head(10), use_container_width=True)

# ---------------------------------------------------------
# FOOTER
# ---------------------------------------------------------
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown("<div class='footer'>© Dynatrade Automotive Group – B2B Customer Portal</div>", unsafe_allow_html=True)

