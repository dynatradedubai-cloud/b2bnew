# ============================================================
# Dynatrade B2B Portal - FINAL APP.PY
# Single File | GitHub + Streamlit Only
# Customer: /
# Admin: ?admin=1
# ============================================================

import streamlit as st
import pandas as pd
import os, io, uuid
from datetime import datetime

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------
st.set_page_config(page_title="Dynatrade B2B Portal", layout="wide")

ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

PARTS_FILE = "parts.xlsx"
USERS_FILE = "users.csv"
ORDERS_FILE = "orders.csv"
LOGO = "logo.png"

# ------------------------------------------------------------
# STYLE
# ------------------------------------------------------------
st.markdown("""
<style>
.block-container {padding-top:1rem;}
.topbar{
background:#003B8E;
padding:14px;
border-radius:10px;
color:white;
font-weight:700;
font-size:24px;
margin-bottom:15px;
}
.card{
border:1px solid #e5e7eb;
padding:12px;
border-radius:10px;
background:white;
margin-bottom:12px;
}
.small{
font-size:13px;
color:#6b7280;
}
.total{
font-size:24px;
font-weight:700;
color:green;
}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# SESSION
# ------------------------------------------------------------
for k,v in {
    "login":False,
    "admin":False,
    "user":"",
    "cart":[]
}.items():
    if k not in st.session_state:
        st.session_state[k]=v

# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------
def load_parts():
    if os.path.exists(PARTS_FILE):
        return pd.read_excel(PARTS_FILE)
    return pd.DataFrame(columns=[
        "Brand","Part No","Description","Vehicle","Stock","Price"
    ])

def load_users():
    if os.path.exists(USERS_FILE):
        return pd.read_csv(USERS_FILE)
    return pd.DataFrame(columns=["Username","Password","Customer"])

def save_order(df):
    if os.path.exists(ORDERS_FILE):
        old = pd.read_csv(ORDERS_FILE)
        df = pd.concat([old,df], ignore_index=True)
    df.to_csv(ORDERS_FILE,index=False)

def cart_total():
    total = 0
    qty = 0
    for x in st.session_state.cart:
        total += x["Total"]
        qty += x["Qty"]
    return qty,total

def reset():
    st.session_state.login=False
    st.session_state.admin=False
    st.session_state.user=""
    st.session_state.cart=[]

# ------------------------------------------------------------
# QUERY PARAM ADMIN
# ------------------------------------------------------------
params = st.query_params
IS_ADMIN = params.get("admin") == "1"

# ------------------------------------------------------------
# HEADER
# ------------------------------------------------------------
c1,c2 = st.columns([6,1])
with c1:
    st.markdown("<div class='topbar'>DYNATRADE AUTOMOTIVE GROUP</div>", unsafe_allow_html=True)
with c2:
    if st.session_state.login or st.session_state.admin:
        if st.button("Logout"):
            reset()
            st.rerun()

# ============================================================
# ADMIN PORTAL
# ============================================================
if IS_ADMIN:

    st.subheader("Admin Portal")

    if not st.session_state.admin:
        with st.form("adminlogin"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            ok = st.form_submit_button("Login")
        if ok:
            if u==ADMIN_USER and p==ADMIN_PASS:
                st.session_state.admin=True
                st.rerun()
            else:
                st.error("Invalid login")
        st.stop()

    tabs = st.tabs(["Upload Parts","Upload Users","Orders"])

    # --------------------------------------------------------
    # UPLOAD PARTS
    # --------------------------------------------------------
    with tabs[0]:
        st.markdown("### Upload Parts Excel")
        file = st.file_uploader("Upload parts.xlsx", type=["xlsx"])
        if file:
            with open(PARTS_FILE,"wb") as f:
                f.write(file.read())
            st.success("Parts uploaded")

        if os.path.exists(PARTS_FILE):
            df = pd.read_excel(PARTS_FILE)
            st.dataframe(df.head(20), use_container_width=True)

    # --------------------------------------------------------
    # USERS
    # --------------------------------------------------------
    with tabs[1]:
        st.markdown("### Upload Users CSV")
        st.caption("Columns: Username,Password,Customer")

        file2 = st.file_uploader("Upload users.csv", type=["csv"])
        if file2:
            with open(USERS_FILE,"wb") as f:
                f.write(file2.read())
            st.success("Users uploaded")

        if os.path.exists(USERS_FILE):
            udf = pd.read_csv(USERS_FILE)
            st.dataframe(udf, use_container_width=True)

    # --------------------------------------------------------
    # ORDERS
    # --------------------------------------------------------
    with tabs[2]:
        st.markdown("### Customer Orders")
        if os.path.exists(ORDERS_FILE):
            odf = pd.read_csv(ORDERS_FILE)
            st.dataframe(odf, use_container_width=True)
            st.download_button(
                "Download Orders CSV",
                odf.to_csv(index=False),
                "orders.csv"
            )
        else:
            st.info("No orders yet")

    st.stop()

# ============================================================
# CUSTOMER PORTAL
# ============================================================
st.subheader("Customer Portal")

# ------------------------------------------------------------
# LOGIN
# ------------------------------------------------------------
if not st.session_state.login:
    with st.form("custlogin"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        ok = st.form_submit_button("Login")

    if ok:
        users = load_users()
        row = users[
            (users["Username"].astype(str)==u) &
            (users["Password"].astype(str)==p)
        ]
        if row.empty:
            st.error("Invalid login")
        else:
            st.session_state.login=True
            st.session_state.user=row.iloc[0]["Customer"]
            st.rerun()
    st.stop()

# ------------------------------------------------------------
# LOGGED IN
# ------------------------------------------------------------
st.success(f"Welcome {st.session_state.user}")

parts = load_parts()

# ------------------------------------------------------------
# MAIN LAYOUT
# ------------------------------------------------------------
left,right = st.columns([2.2,1])

# ============================================================
# LEFT SIDE
# ============================================================
with left:

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("### 🔍 Search Spare Parts")

    query = st.text_input(
        "",
        placeholder="Search by Part No / Description / Brand / Vehicle"
    )

    if query:
        q = query.lower()

        df = parts[
            parts.astype(str).apply(
                lambda x: x.str.lower().str.contains(q)
            ).any(axis=1)
        ]
    else:
        df = parts.head(20)

    st.caption(f"Showing {min(len(df),50)} records")

    show = df.head(50).reset_index(drop=True)

    if len(show)>0:

        h = st.columns([1,1.3,2.2,1.4,0.7,0.9,0.7,0.8])
        heads = ["Brand","Part No","Description","Vehicle","Stock","Price","Qty","Add"]
        for i,x in enumerate(heads):
            h[i].markdown(f"**{x}**")

        for i,row in show.iterrows():
            c = st.columns([1,1.3,2.2,1.4,0.7,0.9,0.7,0.8])

            c[0].write(row["Brand"])
            c[1].write(row["Part No"])
            c[2].write(row["Description"])
            c[3].write(row["Vehicle"])
            c[4].write(int(row["Stock"]))
            c[5].write(f"{row['Price']:.2f}")

            qty = c[6].number_input(
                "",
                min_value=1,
                max_value=int(row["Stock"]) if int(row["Stock"])>0 else 999,
                value=1,
                key=f"q{i}"
            )

            if c[7].button("Add", key=f"a{i}"):

                st.session_state.cart.append({
                    "Brand":row["Brand"],
                    "Part No":row["Part No"],
                    "Description":row["Description"],
                    "Qty":qty,
                    "Price":float(row["Price"]),
                    "Total":qty*float(row["Price"])
                })
                st.success("Added to cart")
                st.rerun()

    else:
        st.warning("No matching parts found")

    st.markdown("</div>", unsafe_allow_html=True)

# ============================================================
# RIGHT SIDE CART
# ============================================================
with right:

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("### 🛒 My Cart")

    if len(st.session_state.cart)==0:
        st.info("Cart empty")

    else:
        remove_index = None

        for i,item in enumerate(st.session_state.cart):

            cc = st.columns([3,1,1])
            cc[0].write(item["Part No"])
            cc[1].write(item["Qty"])
            if cc[2].button("❌", key=f"d{i}"):
                remove_index = i

        if remove_index is not None:
            st.session_state.cart.pop(remove_index)
            st.rerun()

        qty,total = cart_total()

        st.markdown("---")
        st.write(f"Items: {qty}")
        st.markdown(
            f"<div class='total'>AED {total:,.2f}</div>",
            unsafe_allow_html=True
        )

        # ----------------------------------------------------
        # DOWNLOAD EXCEL
        # ----------------------------------------------------
        cartdf = pd.DataFrame(st.session_state.cart)
        bio = io.BytesIO()
        with pd.ExcelWriter(bio, engine="openpyxl") as writer:
            cartdf.to_excel(writer, index=False)

        st.download_button(
            "⬇ Download Excel",
            bio.getvalue(),
            "cart.xlsx"
        )

        # ----------------------------------------------------
        # WHATSAPP
        # ----------------------------------------------------
        msg = "Dynatrade Order%0A"
        for x in st.session_state.cart:
            msg += f"{x['Part No']} Qty {x['Qty']}%0A"

        wa = f"https://wa.me/971500000000?text={msg}"
        st.link_button("🟢 WhatsApp Order", wa)

        # ----------------------------------------------------
        # EMAIL
        # ----------------------------------------------------
        body = "New Order%0A"
        for x in st.session_state.cart:
            body += f"{x['Part No']} Qty {x['Qty']}%0A"

        mail = f"mailto:sales@dynatrade.com?subject=Order&body={body}"
        st.link_button("📧 Email Salesman", mail)

        # ----------------------------------------------------
        # SUBMIT ORDER
        # ----------------------------------------------------
        if st.button("Submit Order"):

            oid = str(uuid.uuid4())[:8].upper()

            odf = pd.DataFrame([{
                "Order ID":oid,
                "Date":datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Customer":st.session_state.user,
                "Items":qty,
                "Total":total
            }])

            save_order(odf)
            st.session_state.cart=[]
            st.success(f"Order {oid} submitted")
            st.rerun()

        if st.button("Clear Cart"):
            st.session_state.cart=[]
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------------------------------------------
# FOOTER
# ------------------------------------------------------------
st.markdown("---")
st.caption("© Dynatrade Automotive Group - B2B Customer Portal")
