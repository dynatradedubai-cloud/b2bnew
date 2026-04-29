import streamlit as st
import pandas as pd
# ---------------------------------------------------------
# GLOBAL THEME / CSS FOR DYNATRADE PORTAL
# ---------------------------------------------------------
st.markdown("""
<style>

    /* GLOBAL FONT */
    html, body, [class*="css"] {
        font-family: 'Segoe UI', sans-serif;
    }

    /* HEADER BAR */
    .header-bar {
        background-color: #004080;
        padding: 12px 20px;
        border-radius: 6px;
        color: white;
    }

    .header-title {
        font-size: 26px;
        font-weight: 700;
        margin-bottom: -5px;
        color: white !important;
    }

    .header-subtitle {
        font-size: 13px;
        color: #d9e6ff !important;
        margin-top: -5px;
    }

    .header-right {
        text-align: right;
        color: white !important;
        font-size: 14px;
    }

    .header-right a {
        color: #ffcccc !important;
        text-decoration: none;
        font-weight: 600;
    }

    /* SEARCH CARD */
    .search-card {
        background-color: #F5F5F5;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #E0E0E0;
    }

    /* TABLE HEADER */
    thead tr th {
        background-color: #004080 !important;
        color: white !important;
        font-weight: 600 !important;
        text-align: center !important;
        padding: 6px !important;
        border-bottom: 2px solid #003366 !important;
    }

    /* TABLE ROW STRIPING */
    tbody tr:nth-child(even) {
        background-color: #F8F8F8 !important;
    }

    tbody tr:nth-child(odd) {
        background-color: #FFFFFF !important;
    }

    /* PRIMARY BUTTONS */
    .stButton>button {
        background-color: #004080 !important;
        color: white !important;
        border-radius: 6px !important;
        padding: 8px 16px !important;
        border: none !important;
        font-weight: 600 !important;
    }

    .stButton>button:hover {
        background-color: #003366 !important;
        color: white !important;
    }

    /* DANGER BUTTONS (Remove, Clear Cart) */
    .danger-btn>button {
        background-color: #D9534F !important;
        color: white !important;
        border-radius: 6px !important;
        padding: 6px 12px !important;
        border: none !important;
        font-weight: 600 !important;
    }

    .danger-btn>button:hover {
        background-color: #C9302C !important;
    }

    /* LINK BUTTONS (Email, WhatsApp) */
    .stLinkButton>a {
        background-color: #004080 !important;
        color: white !important;
        padding: 8px 16px !important;
        border-radius: 6px !important;
        text-decoration: none !important;
        font-weight: 600 !important;
    }

    .stLinkButton>a:hover {
        background-color: #003366 !important;
    }

    /* FOOTER */
    .footer {
        text-align: center;
        color: grey;
        margin-top: 30px;
        font-size: 13px;
    }

</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------
st.set_page_config(page_title="Dynatrade Automotive LLC", layout="wide")

# ---------------------------------------------------------
# HEADER BAR
# ---------------------------------------------------------
col1, col2 = st.columns([6, 2])

with col1:
    st.image("dynatrade_logo.png", width=60)
    st.markdown(
        "<h2 style='color:#004080;margin-bottom:0;'>DYNATRADE AUTOMOTIVE LLC</h2>",
        unsafe_allow_html=True
    )
    st.markdown("<p style='margin-top:-10px;color:grey;'>B2B CUSTOMER PORTAL</p>",
                unsafe_allow_html=True)

with col2:
    st.markdown(
        "<p style='text-align:right;'>Welcome, AL NOOR GARAGE | "
        "<a style='color:red;text-decoration:none;' href='#'>Logout</a></p>",
        unsafe_allow_html=True
    )

st.markdown("<hr>", unsafe_allow_html=True)

# ---------------------------------------------------------
# MAIN LAYOUT
# ---------------------------------------------------------
left, right = st.columns([7, 3])

# ---------------------------------------------------------
# LEFT SIDE – SEARCH PANEL
# ---------------------------------------------------------
with left:
    st.markdown(
        "<div style='background-color:#F5F5F5;padding:15px;border-radius:8px;'>",
        unsafe_allow_html=True
    )
    st.markdown("### Search Parts")

    c1, c2 = st.columns(2)
    brand = c1.selectbox("Brand", ["All", "Toyota", "Nissan", "Ford", "Honda"])
    vehicle = c2.text_input("Vehicle")

    c3, c4 = st.columns(2)
    part_no = c3.text_input("Part Number / OE Number")
    desc = c4.text_input("Description")

    b1, b2 = st.columns([1, 1])
    search = b1.button("Search")
    clear = b2.button("Clear Filters")

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("### Search Results")

    # SAMPLE DATA FOR DESIGN TESTING
    data = pd.DataFrame([
        ["Toyota", "12345-ABC", "Corolla", "90916-03136", "Oil Filter", 150, 25.00, 1],
        ["Nissan", "HYD5678", "Altima", "15208-65F0A", "Brake Pad Set", 80, 120.00, 1],
        ["Ford", "FG-8901", "Focus", "6L8Z-9155-BA", "Fuel Pump", 45, 350.00, 1],
        ["Honda", "33456-TZ2", "Civic", "33100-TBA-A01", "Head Lamp", 60, 180.00, 1]
    ], columns=[
        "Brand", "Manufacturing Part Number", "Vehicle", "OE Part Number",
        "Part Description", "Stock", "Unit Price (AED)", "Qty"
    ])

    edited = st.data_editor(data, num_rows="dynamic")

# ---------------------------------------------------------
# RIGHT SIDE – CART PANEL
# ---------------------------------------------------------
with right:
    st.markdown("### Cart")
    st.button("🗑 Clear Cart")

    cart_df = pd.DataFrame([
        ["Toyota", "12345-ABC", "Corolla", "Oil Filter", 2, 50.00],
        ["Nissan", "HYD5678", "Altima", "Brake Pad Set", 1, 120.00]
    ], columns=["Brand", "Part Number", "Vehicle", "Description", "Qty", "Total (AED)"])

    st.data_editor(cart_df)

    st.markdown("**Items: 3 | Cart Total: AED 170.00**")

    st.download_button(
        "⬇ Download Cart (Excel)",
        data=cart_df.to_csv(index=False),
        file_name="cart.csv"
    )

    st.link_button(
        "📧 Send to Salesman (Email)",
        "mailto:sales@dynatrade.com?subject=Cart&body=Attached Cart"
    )

    st.link_button(
        "🟢 Send via WhatsApp",
        "https://wa.me/971XXXXXXXXX?text=Cart%20details%20attached"
    )
# ---------------------------------------------------------
# THEME / CSS
# ---------------------------------------------------------
st.markdown("""
<style>

    /* Global font */
    html, body, [class*="css"]  {
        font-family: 'Segoe UI', sans-serif;
    }

    /* Header title color */
    h2 {
        color: #004080 !important;
        font-weight: 700 !important;
    }

    /* Table header styling */
    thead tr th {
        background-color: #004080 !important;
        color: white !important;
        font-weight: 600 !important;
        text-align: center !important;
        padding: 6px !important;
    }

    /* Table row striping */
    tbody tr:nth-child(even) {
        background-color: #F8F8F8 !important;
    }

    tbody tr:nth-child(odd) {
        background-color: #FFFFFF !important;
    }

    /* Buttons */
    .stButton>button {
        background-color: #004080 !important;
        color: white !important;
        border-radius: 6px !important;
        padding: 8px 16px !important;
        border: none !important;
    }

    /* Secondary buttons (Clear Cart, Remove, etc.) */
    .stButton>button:hover {
        opacity: 0.9 !important;
    }

    /* Card background */
    .search-card {
        background-color: #F5F5F5;
        padding: 15px;
        border-radius: 8px;
    }

</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# FOOTER
# ---------------------------------------------------------
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align:center;color:grey;'>© Dynatrade Automotive Group – B2B Customer Portal</p>",
    unsafe_allow_html=True
)
