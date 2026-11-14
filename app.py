import json
from datetime import date, datetime
import pandas as pd
import plotly.express as px
import streamlit as st

# --- 1. PAGE CONFIG & SETUP ---
st.set_page_config(
    page_title="Financial Planner", page_icon="📈", layout="wide"
)

# --- 2. SESSION STATE INITIALIZATION ---
if "plan_config" not in st.session_state:
  st.session_state.plan_config = {
      "start_date": str(date.today()),
      "months": 12,
      "checking_balance": 0,
      "checking_apy": 0.5,
      "savings_balance": 0,
      "savings_apy": 4.0,
      "min_checking_buffer": 0,
      "recurring_flows": [

      ],
      "one_offs": [

      ],
  }

# Initialize widget session states from plan_config if not already set
cfg = st.session_state.plan_config
if "w_start_date" not in st.session_state:
  st.session_state["w_start_date"] = datetime.strptime(
      cfg["start_date"], "%Y-%m-%d"
  ).date()
if "w_months" not in st.session_state:
  st.session_state["w_months"] = int(cfg["months"])
if "w_chk_bal" not in st.session_state:
  st.session_state["w_chk_bal"] = float(cfg["checking_balance"])
if "w_chk_apy" not in st.session_state:
  st.session_state["w_chk_apy"] = float(cfg["checking_apy"])
if "w_sav_bal" not in st.session_state:
  st.session_state["w_sav_bal"] = float(cfg["savings_balance"])
if "w_sav_apy" not in st.session_state:
  st.session_state["w_sav_apy"] = float(cfg["savings_apy"])
if "w_min_buf" not in st.session_state:
  st.session_state["w_min_buf"] = float(cfg["min_checking_buffer"])


# --- FILE UPLOADER CALLBACK ---
def handle_file_load():
  uploaded_file = st.session_state.get("plan_file_uploader")
  if uploaded_file is not None:
    try:
      loaded_data = json.load(uploaded_file)
      st.session_state.plan_config = loaded_data

      st.session_state["w_start_date"] = datetime.strptime(
          loaded_data["start_date"], "%Y-%m-%d"
      ).date()
      st.session_state["w_months"] = int(loaded_data.get("months", 12))
      st.session_state["w_chk_bal"] = float(loaded_data["checking_balance"])
      st.session_state["w_chk_apy"] = float(loaded_data["checking_apy"])
      st.session_state["w_sav_bal"] = float(loaded_data["savings_balance"])
      st.session_state["w_sav_apy"] = float(loaded_data["savings_apy"])
      st.session_state["w_min_buf"] = float(
          loaded_data["min_checking_buffer"]
      )
    except Exception as e:
      st.sidebar.error(f"Error loading file: {e}")


st.title("💰 Financial Future Planner")
st.markdown(
    "Simulate accounts with exact daily transactions, $1,000 increment buffer"
    " sweeps with upcoming transaction safety, and monthly APY compounding."
)

# --- 3. SIDEBAR: BROWSER FILE UPLOAD / DOWNLOAD ---
st.sidebar.header("Save / Load Plan")

st.sidebar.file_uploader(
    "Load Plan JSON",
    type=["json"],
    key="plan_file_uploader",
    on_change=handle_file_load,
)

st.sidebar.markdown("---")

plan_json_str = json.dumps(st.session_state.plan_config, indent=2)
st.sidebar.download_button(
    label="Download Plan JSON",
    data=plan_json_str,
    file_name="financial_plan.json",
    mime="application/json",
)

cfg = st.session_state.plan_config

# --- 4. SIDEBAR INPUTS (BOUND TO WIDGET KEYS) ---
st.sidebar.header("Starting Conditions")
start_date = st.sidebar.date_input(
    "Simulation Start Date", key="w_start_date"
)
months_to_simulate = st.sidebar.slider(
    "Simulation Horizon (Months)", 1, 60, key="w_months", step=1
)

checking_balance = st.sidebar.number_input(
    "Starting Checking Balance ($)", key="w_chk_bal", step=500.0
)
checking_apy = (
    st.sidebar.slider(
        "Checking APY (%)", 0.0, 5.0, key="w_chk_apy", step=0.1
    )
    / 100.0
)

savings_balance = st.sidebar.number_input(
    "Starting Savings Balance ($)", key="w_sav_bal", step=1000.0
)
savings_apy = (
    st.sidebar.slider("Savings APY (%)", 0.0, 10.0, key="w_sav_apy", step=0.1)
    / 100.0
)

st.sidebar.header("Transfer Rules")
min_checking_buffer = st.sidebar.number_input(
    "Min Checking Buffer ($) [Sweep excess in $1k increments]",
    key="w_min_buf",
    step=250.0,
)

# --- RECURRING FLOWS MANAGER (WITH EDIT & DELETE) ---
st.sidebar.header("Recurring Incomes & Expenditures")
with st.sidebar.expander("Add New Recurring Flow", expanded=False):
  flow_name = st.text_input("Flow Name", value="Side Gig", key="flow_name")
  flow_type = st.selectbox("Type", ["Income", "Expenditure"], key="flow_type")
  flow_amount = st.number_input("Amount ($)", value=500.0, key="flow_amount")
  flow_freq = st.selectbox(
      "Frequency",
      ["Daily", "Weekly", "Bi-weekly", "Monthly", "Annually"],
      key="flow_freq",
  )
  flow_start = st.date_input(
      "Start Date", date.today(), key="flow_start_date"
  )

  has_end_date = st.checkbox("Specify End Date?", value=False, key="flow_has_end")
  flow_end = None
  if has_end_date:
    flow_end = st.date_input(
        "End Date",
        value=date.today() + pd.DateOffset(months=6),
        key="flow_end_date",
    )

  if st.button("Add Recurring Flow"):
    cfg["recurring_flows"].append(
        {
            "name": flow_name,
            "type": flow_type,
            "amount": flow_amount,
            "frequency": flow_freq,
            "start_date": flow_start.strftime("%Y-%m-%d"),
            "end_date": flow_end.strftime("%Y-%m-%d") if flow_end else None,
        }
    )
    st.rerun()

st.sidebar.markdown("### Active Recurring Flows")
for i, flow in enumerate(cfg["recurring_flows"]):
  edit_key = f"edit_flow_mode_{i}"
  if edit_key not in st.session_state:
    st.session_state[edit_key] = False

  if not st.session_state[edit_key]:
    c1, c2, c3 = st.sidebar.columns([3, 1, 1])
    sign = "+" if flow["type"] == "Income" else "-"
    end_str = (
        f" (until {flow['end_date']})" if flow.get("end_date") else " (Ongoing)"
    )
    c1.text(
        f"[{flow['type']}] {flow['name']}: {sign}${flow['amount']}"
        f" ({flow['frequency']}){end_str}"
    )
    if c2.button("Edit", key=f"btn_edit_{i}"):
      st.session_state[edit_key] = True
      st.rerun()
    if c3.button("Del", key=f"btn_del_flow_{i}"):
      cfg["recurring_flows"].pop(i)
      st.rerun()
  else:
    with st.sidebar.container():
      st.markdown(f"**Edit Flow #{i+1}**")
      e_name = st.text_input("Name", value=flow["name"], key=f"e_name_{i}")
      e_type = st.selectbox(
          "Type",
          ["Income", "Expenditure"],
          index=0 if flow["type"] == "Income" else 1,
          key=f"e_type_{i}",
      )
      e_amount = st.number_input(
          "Amount ($)", value=float(flow["amount"]), key=f"e_amount_{i}"
      )
      freqs = ["Daily", "Weekly", "Bi-weekly", "Monthly", "Annually"]
      e_freq = st.selectbox(
          "Frequency",
          freqs,
          index=freqs.index(flow["frequency"])
          if flow["frequency"] in freqs
          else 0,
          key=f"e_freq_{i}",
      )

      e_start_dt = datetime.strptime(flow["start_date"], "%Y-%m-%d").date()
      e_start = st.date_input("Start Date", value=e_start_dt, key=f"e_start_{i}")

      has_end = flow.get("end_date") is not None
      e_has_end = st.checkbox(
          "Specify End Date?", value=has_end, key=f"e_has_end_{i}"
      )
      e_end = None
      if e_has_end:
        e_end_dt = (
            datetime.strptime(flow["end_date"], "%Y-%m-%d").date()
            if flow.get("end_date")
            else date.today()
        )
        e_end = st.date_input("End Date", value=e_end_dt, key=f"e_end_{i}")

      col_save, col_cancel = st.sidebar.columns(2)
      if col_save.button("Save", key=f"save_edit_{i}"):
        cfg["recurring_flows"][i] = {
            "name": e_name,
            "type": e_type,
            "amount": e_amount,
            "frequency": e_freq,
            "start_date": e_start.strftime("%Y-%m-%d"),
            "end_date": e_end.strftime("%Y-%m-%d") if e_end else None,
        }
        st.session_state[edit_key] = False
        st.rerun()
      if col_cancel.button("Cancel", key=f"cancel_edit_{i}"):
        st.session_state[edit_key] = False
        st.rerun()
    st.sidebar.markdown("---")

# --- ONE-OFF EVENTS MANAGER (INCOME & EXPENDITURES) ---
st.sidebar.header("One-off Events")
with st.sidebar.expander("Manage One-off Events", expanded=False):
  oo_desc = st.text_input("Description", value="Bonus", key="oo_desc")
  oo_type = st.selectbox("Type", ["Income", "Expenditure"], key="oo_type")
  oo_amount = st.number_input("Amount ($)", value=1000.0, key="oo_amount")
  oo_date = st.date_input("Event Date", date.today(), key="oo_date")

  if st.button("Add One-off Event"):
    cfg["one_offs"].append(
        {
            "date": oo_date.strftime("%Y-%m-%d"),
            "amount": oo_amount,
            "description": oo_desc,
            "type": oo_type,
        }
    )
    st.rerun()

  for i, ev in enumerate(cfg["one_offs"]):
    c1, c2 = st.columns([3, 1])
    sign = "+" if ev.get("type", "Expenditure") == "Income" else "-"
    ev_type = ev.get("type", "Expenditure")
    c1.text(
        f"{ev['date']}: {sign}${ev['amount']} ({ev['description']} - {ev_type})"
    )
    if c2.button("Del", key=f"del_oneoff_{i}"):
      cfg["one_offs"].pop(i)
      st.rerun()

# Synchronize current widget inputs back to session state configuration dictionary
st.session_state.plan_config.update({
    "start_date": start_date.strftime("%Y-%m-%d"),
    "months": months_to_simulate,
    "checking_balance": checking_balance,
    "checking_apy": checking_apy * 100,
    "savings_balance": savings_balance,
    "savings_apy": savings_apy * 100,
    "min_checking_buffer": min_checking_buffer,
})


# --- 5. SIMULATION ENGINE ---
def is_flow_due(d: date, f_start: date, f_end: date, freq: str) -> bool:
  if d < f_start:
    return False
  if f_end and d > f_end:
    return False

  diff_days = (d - f_start).days
  if freq == "Daily":
    return True
  elif freq == "Weekly":
    return diff_days >= 0 and diff_days % 7 == 0
  elif freq == "Bi-weekly":
    return diff_days >= 0 and diff_days % 14 == 0
  elif freq == "Monthly":
    last_day = (
        d.replace(day=1) + pd.DateOffset(months=1) - pd.DateOffset(days=1)
    ).day
    target_day = min(f_start.day, last_day)
    return d.day == target_day
  elif freq == "Annually":
    return d.month == f_start.month and d.day == f_start.day
  return False


def get_upcoming_outflows(
    current_day, dates_list, parsed_flows, one_offs_list, lookahead_days=7
):
  """Calculates total expected expenditures in the next N days."""
  total_out = 0.0
  curr_idx = None
  for idx, ts in enumerate(dates_list):
    if ts.date() == current_day:
      curr_idx = idx
      break

  if curr_idx is None:
    return 0.0

  for offset in range(1, lookahead_days + 1):
    if curr_idx + offset < len(dates_list):
      future_ts = dates_list[curr_idx + offset]
      future_d = future_ts.date()

      # Check recurring expenditures
      for flow in parsed_flows:
        if flow["type"] == "Expenditure" and is_flow_due(
            future_d, flow["start_date"], flow["end_date"], flow["frequency"]
        ):
          total_out += flow["amount"]

      # Check one-off expenditures
      future_str = future_d.strftime("%Y-%m-%d")
      for ev in one_offs_list:
        if (
            ev["date"] == future_str
            and ev.get("type", "Expenditure") == "Expenditure"
        ):
          total_out += ev["amount"]

  return total_out


def run_simulation():
  total_days = int(months_to_simulate * 30.4375)
  end_date = start_date + pd.DateOffset(days=total_days)
  dates = pd.date_range(start=start_date, end=end_date, freq="D")

  chk = checking_balance
  sav = savings_balance
  history = []

  parsed_flows = []
  for flow in cfg["recurring_flows"]:
    f_end_str = flow.get("end_date")
    parsed_flows.append({
        "name": flow["name"],
        "type": flow["type"],
        "amount": flow["amount"],
        "frequency": flow["frequency"],
        "start_date": datetime.strptime(flow["start_date"], "%Y-%m-%d").date(),
        "end_date": (
            datetime.strptime(f_end_str, "%Y-%m-%d").date()
            if f_end_str
            else None
        ),
    })

  for i, ts in enumerate(dates):
    d = ts.date()
    day_income = 0.0
    day_expenditure = 0.0
    day_transfer = 0.0  # Positive = to savings, Negative = from savings

    # 1. Apply Recurring Flows due on this exact day
    for flow in parsed_flows:
      if is_flow_due(d, flow["start_date"], flow["end_date"], flow["frequency"]):
        if flow["type"] == "Income":
          chk += flow["amount"]
          day_income += flow["amount"]
        else:
          chk -= flow["amount"]
          day_expenditure += flow["amount"]

    # 2. Apply One-off Events due on this exact day
    date_str = d.strftime("%Y-%m-%d")
    for ev in cfg["one_offs"]:
      if ev["date"] == date_str:
        amt = ev["amount"]
        if ev.get("type", "Expenditure") == "Income":
          chk += amt
          day_income += amt
        else:
          chk -= amt
          day_expenditure += amt

    # 3. Apply transfer rules ($1,000 increments + buffer safety lookahead)
    if chk > min_checking_buffer:
      excess = chk - min_checking_buffer
      if excess >= 1000.0:
        # Calculate raw $1,000 increment sweep amount
        potential_sweep = (excess // 1000.0) * 1000.0

        # Check upcoming 7-day outflows to ensure buffer safety
        upcoming_bills = get_upcoming_outflows(
            d, dates, parsed_flows, cfg["one_offs"], lookahead_days=7
        )
        safe_cash_after_sweep = (
            chk - potential_sweep - upcoming_bills
        )  # estimating checking position

        # Only sweep if checking won't drop below min buffer after upcoming bills
        if safe_cash_after_sweep >= min_checking_buffer:
          sav += potential_sweep
          chk -= potential_sweep
          day_transfer = potential_sweep
    elif chk < 0:
      # Deficit pull from savings
      deficit = abs(chk)
      sav -= deficit
      chk = 0.0
      day_transfer = -deficit

    # 4. Apply monthly compound interest on the LAST day of each month
    is_last_day_of_month = False
    if i == len(dates) - 1:
      is_last_day_of_month = True
    else:
      next_d = dates[i + 1].date()
      if next_d.month != d.month:
        is_last_day_of_month = True

    if is_last_day_of_month:
      chk += chk * (checking_apy / 12.0)
      sav += sav * (savings_apy / 12.0)

    history.append(
        {
            "Date": ts,
            "Income": round(day_income, 2),
            "Expenditure": round(day_expenditure, 2),
            "Transfer": round(day_transfer, 2),
            "Checking": round(chk, 2),
            "Savings": round(sav, 2),
            "Total Wealth": round(chk + sav, 2),
        }
    )

  return pd.DataFrame(history)


df_sim = run_simulation()

# --- 6. MAIN DASHBOARD DISPLAY ---
col1, col2, col3 = st.columns(3)
col1.metric("Ending Total Wealth", f"${df_sim['Total Wealth'].iloc[-1]:,.2f}")
col2.metric("Ending Checking", f"${df_sim['Checking'].iloc[-1]:,.2f}")
col3.metric("Ending Savings", f"${df_sim['Savings'].iloc[-1]:,.2f}")

st.subheader("Daily Net Worth & Account Trajectory")
fig = px.line(
    df_sim,
    x="Date",
    y=["Total Wealth", "Savings", "Checking"],
    labels={"value": "Amount ($)", "variable": "Account"},
    template="plotly_white",
)
fig.update_layout(hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)

with st.expander("View Detailed Daily Transaction Breakdown Table"):
  st.dataframe(df_sim, use_container_width=True)