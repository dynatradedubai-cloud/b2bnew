import streamlit as st
import pandas as pd
import numpy as np

# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------
st.set_page_config(page_title="Dynatrade Automotive LLC", layout="wide")

# Change these before production
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Dyn@1234"

# ---------------------------------------------------------
# THEME / CSS
# ---------------------------------------------------------
st.markdown("""
<style>
html, body, [class*="css"] { font-family: 'Segoe UI', sans-serif; }
.header-bar { background-color:#004080;padding:12px 20px;border-radius:6px;color:white; }
.header-title { font-size:26px;font-weight:700;margin-bottom:-5px;color:white !important; }
.header-subtitle { font-size:13px;color:#d9e6ff !important;margin-top:-5px; }
.header-right { text-align:right;color:white !important;font-size:14px; }
.header-right a { color:#ffcccc !important;text-decoration:none;font-weight:600; }
.search-card { background-color:#F5F5F5;padding:15px;border-radius:8px;border:1px solid #E0E0E0; }
thead tr th { background-color:#004080 !important;color:white !important;font-weight:600 !important;text-align:center !important; }
tbody tr:nth-child(even) { background-color:#F8F8F8 !important; }
tbody tr:nth-child(odd) { background-color:#FFFFFF !important; }
.stButton>button { background-color:#004080 !important;color:white !important;border-radius:6px !important;padding:8px 16px !important;border:none !important;font-weight:600 !important; }
.stButton>button:hover { background-color:#003366 !important;color:white !important; }
.stLinkButton>a { background-color:#004080 !important;color:white !important;padding:8px 16px !important;border-radius:6px !important;text-decoration:none !important;font-weight:600 !important; }
.stLinkButton>a:hover { background-color:#003366 !important; }
.footer { text-align:center;color:grey;margin-top:30px;font-size:13px; }
.small-muted { color: #6c757d; font-size:12px; }
.result-row { padding:8px 0; border-bottom:1px solid #eee; }
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

# ---------------------------------------------------------
# HELPERS: CLEANING, LOADING, VALIDATION
# ---------------------------------------------------------
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
            ["BOSCH","A000000001066","DAIMLER AG","000000001066","SEAL RING,FUEL LINES-AXOR",3,2.11],
            ["FEBI","A000000001073","DAIMLER AG","000000001073","SEAL RING, OIL DRAIN PLUG",10,2.32],
            ["DAIMLER AG","A000000001085","DAIMLER AG","000000001085","SEAL RING, OIL DRAIN PLUG-MB",10,1.17],
        ], columns=[
            "Brand","Manufacturing Part Number","Vehicle","OE Part Number",
            "Part Description","Stock","Unit Price (AED)"
        ])
        st.session_state.parts = df
        return df

# ---------------------------------------------------------
# HEADER (logo + title + logout for customer)
# ---------------------------------------------------------
col_h1, col_h2 = st.columns([6, 2])
with col_h1:
    # try to show logo if present
    try:
        st.image("dynatrade_logo.png", width=60)
    except Exception:
        pass
    st.markdown(
        "<div style='display:inline-block;vertical-align:top;margin-left:8px;'>"
        "<div class='header-title'>DYNATRADE AUTOMOTIVE LLC</div>"
        "<div class='header-subtitle'>Spare Parts Ordering Portal</div>"
        "</div>",
        unsafe_allow_html=True
    )
with col_h2:
    if st.session_state.customer_logged_in:
        st.markdown(
            "<div style='text-align:right;'>"
            f"<div class='small-muted'>Logged in: {st.session_state.customer_company}</div>"
            "<div style='margin-top:6px;'><button style='background:#D9534F;color:white;border:none;padding:6px 10px;border-radius:6px;' id='logout_btn'>Logout</button></div>"
            "</div>",
            unsafe_allow_html=True
        )
        # Logout handling via a simple button below (since inline HTML button won't trigger)
        if st.button("Logout"):
            st.session_state.customer_logged_in = False
            st.session_state.customer_company = ""
    else:
        st.markdown("<div style='text-align:right;'><span class='small-muted'>Not logged in</span></div>", unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)

# ---------------------------------------------------------
# NAVIGATION
# ---------------------------------------------------------
mode = st.sidebar.radio("Select View", ["Customer Portal", "Admin Portal"])

# ---------------------------------------------------------
# CART HELPERS
# ---------------------------------------------------------
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
            "Brand": row["Brand"],
            "Manufacturing Part Number": row["Manufacturing Part Number"],
            "Vehicle": row["Vehicle"],
            "OE Part Number": row["OE Part Number"],
            "Part Description": row["Part Description"],
            "Stock": int(row.get("Stock", 0)),
            "Unit Price (AED)": float(row.get("Unit Price (AED)", 0.0)),
            "Qty": int(qty),
            "Total (AED)": int(qty) * float(row.get("Unit Price (AED)", 0.0))
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

# ---------------------------------------------------------
# CUSTOMER PORTAL
# ---------------------------------------------------------
if mode == "Customer Portal":
    st.markdown("## Customer Portal")

    # Customer login area (uses customers list uploaded by admin)
    if not st.session_state.customer_logged_in:
        st.markdown("### Customer Login")
        with st.form("customer_login", clear_on_submit=False):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
            if submitted:
                # validate against uploaded customers list
                cust_df = st.session_state.customers
                if cust_df is None:
                    st.error("No customer list available. Ask admin to upload customers CSV in Admin Portal.")
                else:
                    # simple match
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
        # Logged in: show single search box only (no default listing)
        st.markdown(f"### Welcome, **{st.session_state.customer_company}**")
        st.markdown("Search parts by Part Number, OE Number, Description, Brand, or Vehicle.")
        query = st.text_input("Search Part Number / OE / Description / Brand / Vehicle", key="cust_search_box")
        search_clicked = st.button("Search")
        # Only show results after search clicked or query non-empty
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
        elif search_clicked:
            st.info("Enter a search term to find parts.")
        # Display results only if results_df not empty
        if not results_df.empty:
            st.markdown(f"**Showing {len(results_df):,} results (showing first 100)**")
            # limit to first 100 for performance
            display_df = results_df.head(100).reset_index(drop=True)
            # For each row, render a compact row with fields, qty input and Add button
            for i, row in display_df.iterrows():
                cols = st.columns([1.2,1.6,1,1,1,0.8,0.8])
                with cols[0]:
                    st.write(row["Brand"])
                with cols[1]:
                    st.write(row["Part Description"])
                with cols[2]:
                    st.write(row["Manufacturing Part Number"])
                with cols[3]:
                    st.write(row["OE Part Number"])
                with cols[4]:
                    st.write(row["Vehicle"])
                with cols[5]:
                    qty_key = f"qty_{i}"
                    qty_val = st.number_input("", min_value=0, max_value=int(row.get("Stock", 999999)), value=0, key=qty_key)
                with cols[6]:
                    btn_key = f"add_{i}"
                    if st.button("Add", key=btn_key):
                        if qty_val <= 0:
                            st.warning("Enter quantity > 0 to add.")
                        else:
                            add_to_cart_row(row.to_dict(), int(qty_val))
                            st.success(f"Added {int(qty_val)} x {row['Manufacturing Part Number']} to cart.")
            st.markdown("---")
        else:
            st.info("No results to display. Use the search box above to find parts.")

        # Right side cart summary (rendered below search for simplicity)
        st.markdown("### Your Cart")
        if st.button("🗑 Clear Cart"):
            clear_cart()
        cart_df = st.session_state.cart.copy()
        if cart_df.empty:
            st.info("Cart is empty.")
        else:
            cart_df_display = cart_df.copy()
            cart_df_display["Qty"] = cart_df_display["Qty"].astype(int)
            st.dataframe(cart_df_display, use_container_width=True)
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
        st.markdown("<div class='small-muted'>Default admin credentials: admin / Dyn@1234 (change before production)</div>", unsafe_allow_html=True)
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
                    # normalize column names if needed
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

