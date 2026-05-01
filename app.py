import streamlit as st
from supabase import create_client, Client
from datetime import date

# --- CONFIGURATION ---
st.set_page_config(page_title="Holiday Tracker", page_icon="🌴")

# Initialize Supabase client
@st.cache_resource
def init_connection() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# --- AUTHENTICATION ---
if "user" not in st.session_state:
    st.title("🌴 Holiday Expense Tracker")
    st.markdown("Please enter your ID to continue.")
    
    code_input = st.text_input("User ID", type="password")
    if st.button("Login"):
        # Query Supabase to see if the ID exists
        response = supabase.table("users").select("name").eq("id", code_input).execute()
        
        if response.data:
            # ID found, log the user in
            st.session_state["user"] = response.data[0]["name"]
            st.rerun()
        else:
            st.error("Invalid ID.")
    st.stop()

current_user = st.session_state["user"]

# --- DYNAMICALLY FETCH USERS ---
# Fetch all users from the database so the app can adapt if you change names
users_response = supabase.table("users").select("name").execute()
all_users = [u["name"] for u in users_response.data]

# Figure out who the other person is
other_user = next((name for name in all_users if name != current_user), "Other Person")

# --- SIDEBAR / LOGOUT ---
with st.sidebar:
    st.write(f"Logged in as: **{current_user}**")
    if st.button("Logout"):
        del st.session_state["user"]
        st.rerun()

# --- DATA FETCHING ---
def fetch_expenses():
    response = supabase.table("expenses").select("*").order("date", desc=True).execute()
    return response.data

expenses_data = fetch_expenses()

# --- CALCULATIONS ---
total_paid_by_me = 0.0
my_share_of_my_payments = 0.0
my_share_of_their_payments = 0.0

for row in expenses_data:
    amount = float(row["amount"])
    payer_share = float(row["payer_share"])
    
    if row["payer"] == current_user:
        total_paid_by_me += amount
        my_share_of_my_payments += payer_share
    else:
        # If the other person paid, my share is the total amount MINUS their share
        my_share_of_their_payments += (amount - payer_share)

total_my_share = my_share_of_my_payments + my_share_of_their_payments
balance = total_paid_by_me - total_my_share

# --- DASHBOARD ---
st.title(f"Dashboard: {current_user}")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="Total Paid by You", value=f"€{total_paid_by_me:.2f}")
with col2:
    st.metric(label="Your Share of Costs", value=f"€{total_my_share:.2f}", help="Total amount you were supposed to pay for the whole trip.")
with col3:
    if balance > 0:
        st.metric(label=f"{other_user} owes you", value=f"€{balance:.2f}")
    elif balance < 0:
        st.metric(label=f"You owe {other_user}", value=f"€{abs(balance):.2f}")
    else:
        st.metric(label="Settled up!", value="€0.00")

st.divider()

# --- LOG NEW EXPENSE FORM ---
st.subheader("Log a New Expense")

with st.form("expense_form", clear_on_submit=True):
    desc = st.text_input("What was it for?", placeholder="e.g., Rental Car, Dinner")
    
    col_a, col_b = st.columns(2)
    with col_a:
        amount = st.number_input("Total Amount Spent (€)", min_value=0.01, step=1.00)
    with col_b:
        expense_date = st.date_input("Date", value=date.today())
        
    col_c, col_d = st.columns(2)
    with col_c:
        payment_method = st.selectbox("Payment Method", ["Card", "Cash"])
    with col_d:
        payer = st.selectbox("Who Paid?", [current_user, other_user])

    st.markdown("**How should this be split?**")
    split_mode = st.radio("Split type", ["Percentage (%)", "Exact Amount (€)"], horizontal=True)
    
    if split_mode == "Percentage (%)":
        share_val = st.number_input(
            "Share of the person who paid (%)", # <-- STATIC LABEL
            min_value=0.0, 
            max_value=100.0, 
            value=50.0, 
            step=5.0,
            key="share_pct"
        )
    else:
        share_val = st.number_input(
            "Share of the person who paid (€)", # <-- STATIC LABEL
            min_value=0.0, 
            value=0.0,                          # <-- STATIC DEFAULT
            step=1.0,
            key="share_exact"
        )

    submit = st.form_submit_button("Log Expense")

    if submit:
        if not desc:
            st.error("Please enter a description.")
        else:
            # Calculate the payer's exact monetary share based on the selected mode
            if split_mode == "Percentage (%)":
                calculated_payer_share = amount * (share_val / 100.0)
            else:
                calculated_payer_share = share_val
            
            # Insert into Supabase
            supabase.table("expenses").insert({
                "date": str(expense_date),
                "description": desc,
                "amount": amount,
                "payment_method": payment_method,
                "payer": payer,
                "payer_share": calculated_payer_share
            }).execute()
            
            st.success("Expense logged successfully!")
            st.rerun()

st.divider()

# --- EXPENSE HISTORY ---
st.subheader("Expense History")
if expenses_data:
    for row in expenses_data:
        amount_val = float(row['amount'])
        payer_share_val = float(row['payer_share'])
        
        # Determine who owes what for this specific transaction
        if row['payer'] == current_user:
            owed_for_this = amount_val - payer_share_val
            split_text = f"You paid €{amount_val:.2f} (Your share: €{payer_share_val:.2f})"
        else:
            my_share = amount_val - payer_share_val
            split_text = f"{other_user} paid €{amount_val:.2f} (Your share: €{my_share:.2f})"

        with st.expander(f"{row['date']} - {row['description']} (€{amount_val:.2f})"):
            st.write(f"**Paid by:** {row['payer']}")
            st.write(f"**Method:** {row['payment_method']}")
            st.write(f"**Breakdown:** {split_text}")
else:
    st.info("No expenses logged yet. Add one above!")