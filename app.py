import streamlit as st
import pandas as pd
import numpy as np

# ---------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------
st.set_page_config(page_title="Dynatrade Automotive LLC", layout="wide")

# ---------------------------------------------------------
# GLOBAL THEME / CSS
# ---------------------------------------------------------
st.markdown("""
<style>
html, body, [class*="css"] { font-family: 'Segoe UI', sans-serif; }

/* HEADER BAR */
.header-bar { background-color:#004080;padding:12px 20px;border-radius:6px;color:white; }
.header-title { font-size:26px;font-weight:700;margin-bottom:-5px;color:white !important; }
.header-subtitle { font-size:13px;color:#d9e6ff !important;margin-top:-5px; }
.header-right { text-align:right;color:white !important;font-size:14px; }
.header-right a { color:#ffcccc !important;text-decoration:none;font-weight:600; }

/* SEARCH CARD */
.search-card { background-color:#F5F5F5;padding:15px;border-radius:8px;border:1px solid #E0E0E0; }

/* TABLE HEADER */
thead tr th { background-color:#004080 !important;color:white !important;
              font-weight:600 !important;text-align:center !important;
              padding:6px !important;border-bottom:2px solid #003366 !important; }

/* TABLE ROW STRIPING */
tbody tr:nth-child(even) { background-color:#F8F8F8 !important; }
tbody tr:nth-child(odd) { background-color:#FFFFFF !important; }

/* PRIMARY BUTTONS */
.stButton>button { background-color:#004080 !important;color:white !important;
                   border-radius:6px !important;padding:8px 16px !important;
                   border:none !important;font-weight:600 !important; }
.stButton>button:hover { background-color:#003366 !important;color:white !important; }

/* LINK BUTTONS */
.stLinkButton>a { background-color:#004080 !important;color:white !important;
                  padding:8px 16px !important;border-radius:6px !important;
                  text-decoration:none !important;font-weight:600 !important; }
.stLinkButton>a:hover { background-color:#003366 !important; }

/* FOOTER */
.footer { text-align:center;color:grey;margin-top:30px;font-size:13px; }
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

# ---------------------------------------------------------
# DATA CLEANING HELPERS
# ---------------------------------------------------------
def clean_df(df):
    df.columns = [c.strip() for c in df.columns]

    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).str.replace("\xa0", " ", regex=False)
            df[col] = df[col].str.strip()

    if "Brand" in df.columns:
        df["Brand"] = df["Brand"].str.upper()

    return df

# ---------------------------------------------------------
# LOAD CSV SAFELY
# ---------------------------------------------------------
@st.cache_data
def load_parts_from_csv(path: str):
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
    df["Unit Price (AED)"] = pd.to_numeric(df["Unit Price (AED)"], errors="ignore")

    return df

def get_parts_df():
    if st.session_state.parts is not None:
        return st.session_state.parts
    try:
        df = load_parts_from_csv("parts_list.csv")
        st.session_state.parts = df
        return df
    except Exception:
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
        "<div class='header-bar' style='background-color:transparent;padding:0;text-align:right;'>"
        "<div class='header-right'>Welcome, AL NOOR GARAGE | "
        "<a href='#'>Logout</a></div></div>",
        unsafe_allow_html=True
    )

st.markdown("<hr>", unsafe_allow_html=True)

# ---------------------------------------------------------
# SIDEBAR NAV
# ---------------------------------------------------------
mode = st.sidebar.radio("Select View", ["Customer Portal", "Admin Portal"])

# ---------------------------------------------------------
# CART HELPERS
# ---------------------------------------------------------
def add_to_cart(selected_rows: pd.DataFrame):
    if selected_rows.empty:
        return
    cart = st.session_state.cart.copy()
    for _, row in selected_rows.iterrows():
        key_cols = ["Brand", "Manufacturing Part Number", "Vehicle", "OE Part Number"]
        mask = (cart[key_cols] == row[key_cols]).all(axis=1) if not cart.empty else pd.Series([], dtype=bool)
        if mask.any():
            idx = cart[mask].index[0]
            cart.loc[idx, "Qty"] += row["Qty"]
            cart.loc[idx, "Total (AED)"] = cart.loc[idx, "Qty"] * cart.loc[idx, "Unit Price (AED)"]
        else:
            new_row = row.copy()
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
# CUSTOMER PORTAL
# ---------------------------------------------------------
if mode == "Customer Portal":
    left, right = st.columns([7, 3])

    with left:
        st.markdown("<div class='search-card'>", unsafe_allow_html=True)
        st.markdown("### Search Parts")

        c1, c2 = st.columns(2)
        brand_filter = c1.text_input("Brand")
        vehicle_filter = c2.text_input("Vehicle")

        c3, c4 = st.columns(2)
        part_no_filter = c3.text_input("Part Number / OE Number")
        desc_filter = c4.text_input("Description")

        b1, b2 = st.columns([1, 1])
        search_clicked = b1.button("Search")
        clear_clicked = b2.button("Clear Filters")

        st.markdown("</div>", unsafe_allow_html=True)

        df = get_parts_df().copy()

        if clear_clicked:
            brand_filter = vehicle_filter = part_no_filter = desc_filter = ""

        if search_clicked:
            if brand_filter:
                df = df[df["Brand"].astype(str).str.contains(brand_filter, case=False, na=False)]
            if vehicle_filter:
                df = df[df["Vehicle"].astype(str).str.contains(vehicle_filter, case=False, na=False)]
            if part_no_filter:
                df = df[df["OE Part Number"].astype(str).str.contains(part_no_filter, case=False, na=False)]
            if desc_filter:
                df = df[df["Part Description"].astype(str).str.contains(desc_filter, case=False, na=False)]

        st.markdown("### Search Results")

        if "Qty" not in df.columns:
            df["Qty"] = 0

        edited = st.data_editor(
            df,
            num_rows="dynamic",
            use_container_width=True,
            key="search_results_editor"
        )

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
            csv_data = cart_df.to_csv(index=False)
            st.download_button(
                "⬇ Download Cart (Excel)",
                data=csv_data,
                file_name="cart.csv",
                mime="text/csv"
            )

            body_lines = []
            for _, r in cart_df.iterrows():
                body_lines.append(
                    f"{r['Brand']} | {r['Manufacturing Part Number']} | "
                    f"{r['Vehicle']} | {r['OE Part Number']} | "
                    f"{r['Part Description']} | Qty: {int(r['Qty'])} | "
                    f"Total: AED {r['Total (AED)']:.2f}"
                )
            body_text = "%0D%0A".join(body_lines)
            mailto_link = f"mailto:sales@dynatrade.com?subject=Parts%20Cart&body={body_text}"
            st.link_button("📧 Send to Salesman (Email)", mailto_link)

            wa_text = body_text.replace("%0D%0A", "%0A")
            wa_link = f"https://wa.me/971XXXXXXXXX?text={wa_text}"
            st.link_button("🟢 Send via WhatsApp", wa_link)

# ---------------------------------------------------------
# ADMIN PORTAL
# ---------------------------------------------------------
if mode == "Admin Portal":
    st.markdown("## Admin Portal")

    tab1, tab2, tab3 = st.tabs(["Upload / Manage Parts", "View Parts List", "Dashboard"])

    with tab1:
        st.markdown("### Upload / Replace Parts List")
        st.write("Upload your master parts file (CSV only). Excel is not supported here.")

        uploaded = st.file_uploader("Upload CSV file", type=["csv"])
        if uploaded is not None:
            try:
                df_new = pd.read_csv(
                    uploaded,
                    encoding="latin1",
                    encoding_errors="ignore"
                )
                df_new = clean_df(df_new)
                st.session_state.parts = df_new
                st.success(f"Uploaded and loaded {len(df_new):,} parts.")
            except Exception as e:
                st.error(f"Error reading file: {e}")

        if st.session_state.parts is not None:
            st.info(f"Current parts list in memory: {len(st.session_state.parts):,} rows.")

    with tab2:
        st.markdown("### Parts List")
        df = get_parts_df()
        st.write(f"Total parts: {len(df):,}")
        st.dataframe(df.head(100), use_container_width=True)
        st.caption("Showing first 100 rows for performance. Full list is available in memory.")

    with tab3:
        st.markdown("### Dashboard")
        df = get_parts_df()
        total_parts = len(df)
        total_brands = df["Brand"].nunique() if "Brand" in df.columns else 0
        total_stock = df["Stock"].sum() if "Stock" in df.columns else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Total SKUs", f"{total_parts:,}")
        c2.metric("Brands", f"{total_brands:,}")
        c3.metric("Total Stock Units", f"{int(total_stock):,}")

        if "Unit Price (AED)" in df.columns:
            df["Stock Value"] = df["Stock"] * df["Unit Price (AED)"]
            total_value = df["Stock Value"].sum()
            st.metric("Estimated Stock Value (AED)", f"{total_value:,.2f}")

        st.markdown("#### Top 10 Parts by Stock")
        if "Stock" in df.columns:
            top_stock = df.sort_values("Stock", ascending=False).head(10)
            st.dataframe(top_stock, use_container_width=True)

# ---------------------------------------------------------
# FOOTER
# ---------------------------------------------------------
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(
    "<div class='footer'>© Dynatrade Automotive Group – B2B Customer Portal</div>",
    unsafe_allow_html=True
)

