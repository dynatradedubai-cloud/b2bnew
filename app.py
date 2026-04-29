import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Dynatrade Automotive LLC", layout="wide")

# ---------------------------------------------------------
# GLOBAL THEME
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
.stButton>button:hover { background-color:#003366 !important; }
.stLinkButton>a { background-color:#004080 !important;color:white !important;padding:8px 16px !important;border-radius:6px !important;text-decoration:none !important;font-weight:600 !important; }
.stLinkButton>a:hover { background-color:#003366 !important; }
.footer { text-align:center;color:grey;margin-top:30px;font-size:13px; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------
if "cart" not in st.session_state:
    st.session_state.cart = pd.DataFrame(columns=[
        "Brand","Manufacturing Part Number","Vehicle","OE Part Number",
        "Part Description","Stock","Unit Price (AED)","Qty","Total (AED)"
    ])

if "parts" not in st.session_state:
    st.session_state.parts = None

# ---------------------------------------------------------
# CLEANING
# ---------------------------------------------------------
def clean_df(df):
    df.columns = [c.strip() for c in df.columns]
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).str.replace("\xa0"," ",regex=False).str.strip()
    if "Brand" in df.columns:
        df["Brand"] = df["Brand"].str.upper()
    return df

# ---------------------------------------------------------
# LOAD CSV
# ---------------------------------------------------------
@st.cache_data
def load_parts_csv(path):
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
        "Brand","Manufacturing Part Number","Vehicle","OE Part Number",
        "Part Description","Stock","Unit Price (AED)"
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df["Stock"] = pd.to_numeric(df["Stock"], errors="coerce").fillna(0).astype(int)
    df["Unit Price (AED)"] = pd.to_numeric(df["Unit Price (AED)"], errors="coerce")

    return df

def get_parts_df():
    if st.session_state.parts is not None:
        return st.session_state.parts
    try:
        df = load_parts_csv("parts_list.csv")
        st.session_state.parts = df
        return df
    except:
        df = pd.DataFrame([
            ["BOSCH","A000000001066","DAIMLER AG","000000001066","SEAL RING",3,2.11],
            ["FEBI","A000000001073","DAIMLER AG","000000001073","OIL DRAIN PLUG",10,2.32],
        ], columns=[
            "Brand","Manufacturing Part Number","Vehicle","OE Part Number",
            "Part Description","Stock","Unit Price (AED)"
        ])
        st.session_state.parts = df
        return df

# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------
col1, col2 = st.columns([6,2])
with col1:
    st.markdown(
        "<div class='header-bar'><div class='header-title'>DYNATRADE AUTOMOTIVE LLC</div>"
        "<div class='header-subtitle'>Spare Parts Ordering Portal</div></div>",
        unsafe_allow_html=True
    )
with col2:
    st.markdown(
        "<div class='header-bar' style='background-color:transparent;padding:0;text-align:right;'>"
        "<div class='header-right'>Welcome, AL NOOR GARAGE | <a href='#'>Logout</a></div></div>",
        unsafe_allow_html=True
    )

st.markdown("<hr>", unsafe_allow_html=True)

# ---------------------------------------------------------
# NAVIGATION
# ---------------------------------------------------------
mode = st.sidebar.radio("Select View", ["Customer Portal", "Admin Portal"])

# ---------------------------------------------------------
# CART FUNCTIONS
# ---------------------------------------------------------
def add_to_cart(rows):
    cart = st.session_state.cart.copy()
    for _, row in rows.iterrows():
        key = ["Brand","Manufacturing Part Number","Vehicle","OE Part Number"]
        mask = (cart[key] == row[key]).all(axis=1) if not cart.empty else pd.Series([],dtype=bool)
        if mask.any():
            idx = cart[mask].index[0]
            cart.loc[idx,"Qty"] += row["Qty"]
            cart.loc[idx,"Total (AED)"] = cart.loc[idx,"Qty"] * cart.loc[idx,"Unit Price (AED)"]
        else:
            new = row.copy()
            new["Total (AED)"] = new["Qty"] * new["Unit Price (AED)"]
            cart = pd.concat([cart,pd.DataFrame([new])],ignore_index=True)
    st.session_state.cart = cart

def clear_cart():
    st.session_state.cart = st.session_state.cart.iloc[0:0]

def cart_totals():
    if st.session_state.cart.empty:
        return 0,0
    return int(st.session_state.cart["Qty"].sum()), float(st.session_state.cart["Total (AED)"].sum())

# ---------------------------------------------------------
# CUSTOMER PORTAL
# ---------------------------------------------------------
if mode == "Customer Portal":

    left, right = st.columns([7,3])

    with left:
        st.markdown("<div class='search-card'>", unsafe_allow_html=True)
        st.markdown("### Search Parts")

        # ⭐ ONE SINGLE SEARCH BOX
        query = st.text_input("Search Part Number / OE / Description / Brand / Vehicle")

        search_btn = st.button("Search")
        clear_btn = st.button("Clear")

        st.markdown("</div>", unsafe_allow_html=True)

        df = get_parts_df().copy()

        if clear_btn:
            query = ""

        if search_btn and query.strip() != "":
            q = query.strip().lower()
            df = df[
                df.apply(lambda r:
                    q in str(r["Manufacturing Part Number"]).lower() or
                    q in str(r["OE Part Number"]).lower() or
                    q in str(r["Part Description"]).lower() or
                    q in str(r["Brand"]).lower() or
                    q in str(r["Vehicle"]).lower()
                , axis=1)
            ]

        st.markdown("### Search Results")

        df["Qty"] = 0
        edited = st.data_editor(df, use_container_width=True, key="search_editor")

        st.caption("Set Qty > 0 then click Add to Cart")

        if st.button("🛒 Add to Cart"):
            add_to_cart(edited[edited["Qty"] > 0])

    with right:
        st.markdown("### Cart")
        st.button("🗑 Clear Cart", on_click=clear_cart)

        cart = st.session_state.cart.copy()
        if cart.empty:
            st.info("Cart is empty.")
        else:
            cart["Qty"] = cart["Qty"].astype(int)
            st.data_editor(cart, disabled=True, use_container_width=True)

        items, total = cart_totals()
        st.markdown(f"**Items: {items} | Total: AED {total:,.2f}**")

        if not cart.empty:
            st.download_button("⬇ Download Cart", cart.to_csv(index=False), "cart.csv")

            body = "%0D%0A".join([
                f"{r['Brand']} | {r['Manufacturing Part Number']} | {r['Part Description']} | Qty {int(r['Qty'])}"
                for _, r in cart.iterrows()
            ])
            st.link_button("📧 Email", f"mailto:sales@dynatrade.com?subject=Cart&body={body}")
            st.link_button("🟢 WhatsApp", f"https://wa.me/971XXXXXXXXX?text={body}")

# ---------------------------------------------------------
# ADMIN PORTAL
# ---------------------------------------------------------
if mode == "Admin Portal":
    st.markdown("## Admin Portal")

    tab1, tab2, tab3 = st.tabs(["Upload Parts", "View Parts", "Dashboard"])

    with tab1:
        st.markdown("### Upload CSV")
        file = st.file_uploader("Upload CSV", type=["csv"])
        if file:
            try:
                df = pd.read_csv(file, encoding="latin1", encoding_errors="ignore")
                df = clean_df(df)
                st.session_state.parts = df
                st.success(f"Loaded {len(df):,} rows")
            except Exception as e:
                st.error(str(e))

    with tab2:
        df = get_parts_df()
        st.write(f"Total parts: {len(df):,}")
        st.dataframe(df.head(100), use_container_width=True)

    with tab3:
        df = get_parts_df()
        st.metric("Total SKUs", len(df))
        st.metric("Brands", df["Brand"].nunique())
        st.metric("Total Stock", df["Stock"].sum())

        if "Unit Price (AED)" in df.columns:
            df["Value"] = df["Stock"] * df["Unit Price (AED)"]
            st.metric("Stock Value", f"AED {df['Value'].sum():,.2f}")

# ---------------------------------------------------------
# FOOTER
# ---------------------------------------------------------
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown("<div class='footer'>© Dynatrade Automotive Group – B2B Customer Portal</div>", unsafe_allow_html=True)

