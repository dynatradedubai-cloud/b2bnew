import streamlit as st
import pandas as pd
import numpy as np

# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------
st.set_page_config(page_title="Dynatrade Automotive LLC", layout="wide")

# Default admin credentials (change before production)
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

if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

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
# HEADER
# ---------------------------------------------------------
col_h1, col_h2 = st.columns([6, 2])
with col_h1:
    st.markdown(
        "<div class='header-bar'>"
        "<div class='header-title'>DYNATRADE AUTOMOTIVE LLC</div>"
        "<div class='header-subtitle'>Spare Parts Ordering Portal</div>"
        "</div>",
        unsafe_allow_html=True
    )
with col_h2:
    st.markdown(
        "<div style='text-align:right;'><span class='small-muted'>Welcome, AL NOOR GARAGE</span></div>",
        unsafe_allow_html=True
    )
st.markdown("<hr>", unsafe_allow_html=True)

# ---------------------------------------------------------
# NAVIGATION
# ---------------------------------------------------------
mode = st.sidebar.radio("Select View", ["Customer Portal", "Admin Portal"])

# ---------------------------------------------------------
# CART LOGIC
# ---------------------------------------------------------
def add_to_cart(selected_rows: pd.DataFrame):
    if selected_rows.empty:
        return
    cart = st.session_state.cart.copy()
    for _, row in selected_rows.iterrows():
        key_cols = ["Brand", "Manufacturing Part Number", "Vehicle", "OE Part Number"]
        if cart.empty:
            mask = pd.Series([], dtype=bool)
        else:
            mask = (cart[key_cols] == row[key_cols]).all(axis=1)
        if mask.any():
            idx = cart[mask].index[0]
            cart.loc[idx, "Qty"] += int(row["Qty"])
            cart.loc[idx, "Total (AED)"] = cart.loc[idx, "Qty"] * cart.loc[idx, "Unit Price (AED)"]
        else:
            new_row = row.copy()
            new_row["Qty"] = int(new_row.get("Qty", 0))
            new_row["Total (AED)"] = new_row["Qty"] * new_row["Unit Price (AED)"]
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
# CUSTOMER PORTAL (Single search box)
# ---------------------------------------------------------
if mode == "Customer Portal":
    left, right = st.columns([7, 3])

    with left:
        st.markdown("<div class='search-card'>", unsafe_allow_html=True)
        st.markdown("### Search Parts")
        query = st.text_input("Search Part Number / OE / Description / Brand / Vehicle")
        search_btn = st.button("Search")
        clear_btn = st.button("Clear")
        st.markdown("</div>", unsafe_allow_html=True)

        df = get_parts_df().copy()
        if clear_btn:
            query = ""

        if query and query.strip() != "":
            q = query.strip().lower()
            df = df[df.apply(lambda r:
                q in str(r.get("Manufacturing Part Number", "")).lower() or
                q in str(r.get("OE Part Number", "")).lower() or
                q in str(r.get("Part Description", "")).lower() or
                q in str(r.get("Brand", "")).lower() or
                q in str(r.get("Vehicle", "")).lower()
            , axis=1)]

        st.markdown("### Search Results")
        if "Qty" not in df.columns:
            df["Qty"] = 0
        edited = st.data_editor(df, use_container_width=True, key="search_editor")
        st.caption("Set Qty > 0 for lines you want to add to cart, then click 'Add Selected to Cart'.")

        if st.button("🛒 Add Selected to Cart"):
            to_add = edited[edited["Qty"] > 0].copy()
            if not to_add.empty:
                add_to_cart(to_add)

    with right:
        st.markdown("### Cart")
        st.button("🗑 Clear Cart", on_click=clear_cart)
        cart_df = st.session_state.cart.copy()
        if cart_df.empty:
            st.info("Cart is empty.")
        else:
            cart_df_display = cart_df.copy()
            cart_df_display["Qty"] = cart_df_display["Qty"].astype(int)
            st.data_editor(cart_df_display, use_container_width=True, disabled=True)
        items, total = cart_totals()
        st.markdown(f"**Items: {items} | Cart Total: AED {total:,.2f}**")
        if not cart_df.empty:
            st.download_button("⬇ Download Cart (CSV)", cart_df.to_csv(index=False), "cart.csv")
            body_lines = []
            for _, r in cart_df.iterrows():
                body_lines.append(
                    f"{r['Brand']} | {r['Manufacturing Part Number']} | {r['Vehicle']} | {r['OE Part Number']} | {r['Part Description']} | Qty: {int(r['Qty'])} | Total: AED {r['Total (AED)']:.2f}"
                )
            body_text = "%0D%0A".join(body_lines)
            st.link_button("📧 Send to Salesman (Email)", f"mailto:sales@dynatrade.com?subject=Parts%20Cart&body={body_text}")
            wa_text = body_text.replace("%0D%0A", "%0A")
            st.link_button("🟢 Send via WhatsApp", f"https://wa.me/971XXXXXXXXX?text={wa_text}")

# ---------------------------------------------------------
# ADMIN PORTAL (requires login)
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
                    st.success("Logged in as admin.")
                else:
                    st.error("Invalid credentials. Change defaults in app.py before production.")
        st.markdown("<div class='small-muted'>Default admin credentials: admin / Dyn@1234 (change before production)</div>", unsafe_allow_html=True)
    else:
        tab1, tab2, tab3 = st.tabs(["Upload / Manage Parts", "View Parts List", "Dashboard"])

        with tab1:
            st.markdown("### Upload / Replace Parts List (CSV only)")
            st.write("Required columns: Brand, Manufacturing Part Number, Vehicle, OE Part Number, Part Description, Stock, Unit Price (AED)")
            uploaded = st.file_uploader("Upload CSV file", type=["csv"])
            if uploaded is not None:
                try:
                    df_new = pd.read_csv(uploaded, encoding="latin1", encoding_errors="ignore")
                    df_new = clean_df(df_new)
                    # Basic validation
                    required = ["Brand","Manufacturing Part Number","Vehicle","OE Part Number","Part Description","Stock","Unit Price (AED)"]
                    missing = [c for c in required if c not in df_new.columns]
                    if missing:
                        st.error(f"Missing columns: {missing}")
                    else:
                        # normalize numeric columns
                        df_new["Stock"] = pd.to_numeric(df_new["Stock"], errors="coerce").fillna(0).astype(int)
                        df_new["Unit Price (AED)"] = pd.to_numeric(df_new["Unit Price (AED)"], errors="coerce").fillna(0.0)
                        st.session_state.parts = df_new
                        st.success(f"Uploaded and loaded {len(df_new):,} parts.")
                except Exception as e:
                    st.error(f"Error reading file: {e}")

            if st.button("Logout Admin"):
                st.session_state.admin_logged_in = False
                st.success("Logged out.")

        with tab2:
            st.markdown("### Parts List (first 100 rows)")
            df = get_parts_df()
            st.write(f"Total parts in memory: {len(df):,}")
            st.dataframe(df.head(100), use_container_width=True)
            st.caption("If your CSV is large, upload via the Upload tab. The app keeps the list in memory for fast search.")

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
