import json
from datetime import date, datetime
import pandas as pd
import plotly.express as px
import streamlit as st
from pathlib import Path
from platformdirs import user_data_dir

# --- 1. PAGE CONFIG & STORAGE SETUP ---
st.set_page_config(
    page_title="Financial Planner", page_icon="📈", layout="wide"
)

APP_NAME = "FinancialPlanner"
SAVE_DIR = Path(user_data_dir(APP_NAME, appauthor=False, ensure_exists=True))

# --- 2. SESSION STATE INITIALIZATION ---
if "plan_config" not in st.session_state:
  st.session_state.plan_config = {
      "start_date": str(date.today()),
      "months": 12,
      "checking_balance": 3000.0,
      "checking_apy": 0.5,
      "savings_balance": 15000.0,
      "savings_apy": 4.5,
      "min_checking_buffer": 2000.0,
      "recurring_flows": [
          {
              "name": "Salary",
              "type": "Income",
              "amount": 2250.0,
              "frequency": "Bi-weekly",
              "start_date": "2026-01-02",
              "end_date": None,
          },
          {
              "name": "Car Loan",
              "type": "Expenditure",
              "amount": 350.0,
              "frequency": "Monthly",
              "start_date": "2026-01-01",
              "end_date": "2026-12-31",
          },
          {
              "name": "Groceries",
              "type": "Expenditure",
              "amount": 150.0,
              "frequency": "Weekly",
              "start_date": "2026-01-01",
              "end_date": None,
          },
      ],
      "one_offs": [
          {
              "date": "2026-07-15",
              "amount": 2500.0,
              "description": "Work Bonus",
              "type": "Income",
          },
          {
              "date": "2026-12-15",
              "amount": 1200.0,
              "description": "Holiday Trip",
              "type": "Expenditure",
          },
          {
              "date": "2027-06-01",
              "amount": 3500.0,
              "description": "Car Repair",
              "type": "Expenditure",
          },
      ],
  }

cfg = st.session_state.plan_config

st.title("💰 Modern Financial Planner (Daily & Monthly Engine)")
st.markdown(
    "Simulate accounts with exact daily transactions, one-off incomes &"
    " expenses, editable recurring flows, buffer sweeps, and monthly APY"
    " compounding."
)

# --- 3. SIDEBAR: LOCAL SAVE / LOAD ---
st.sidebar.header("6. Local Save / Load")
save_filename = st.sidebar.text_input("Filename to save", value="my_plan.json")
if st.sidebar.button("Save Plan to Disk"):
  if not save_filename.endswith(".json"):
    save_filename += ".json"
  file_path = SAVE_DIR / save_filename
  try:
    with open(file_path, "w") as f:
      json.dump(st.session_state.plan_config, f, indent=2)
    st.sidebar.success(f"Saved successfully to {file_path}!")
  except Exception as e:
    st.sidebar.error(f"Error saving file: {e}")

st.sidebar.markdown("---")

saved_files = [f.name for f in SAVE_DIR.glob("*.json")]
if saved_files:
  selected_file = st.sidebar.selectbox("Select Saved Plan", saved_files)
  if st.sidebar.button("Load Selected Plan"):
    file_path = SAVE_DIR / selected_file
    try:
      with open(file_path, "r") as f:
        loaded_data = json.load(f)
      st.session_state.plan_config = loaded_data
      st.sidebar.success(f"Loaded '{selected_file}' successfully!")
      st.rerun()
    except Exception as e:
      st.sidebar.error(f"Error loading file: {e}")
else:
  st.sidebar.info("No saved plans found in `saved_plans/` yet.")

cfg = st.session_state.plan_config

# --- 4. SIDEBAR INPUTS ---
st.sidebar.header("1. Starting Conditions")
parsed_start_date = datetime.strptime(cfg["start_date"], "%Y-%m-%d").date()
start_date = st.sidebar.date_input("Simulation Start Date", value=parsed_start_date)

# Updated slider to step by 1 month (min 1 month, max 60 months)
months_to_simulate = st.sidebar.slider(
    "Simulation Horizon (Months)", 1, 60, int(cfg.get("months", 12)), 1
)

checking_balance = st.sidebar.number_input(
    "Starting Checking Balance ($)",
    value=float(cfg["checking_balance"]),
    step=500.0,
)
checking_apy = (
    st.sidebar.slider(
        "Checking APY (%)", 0.0, 5.0, float(cfg["checking_apy"]), 0.1
    )
    / 100.0
)

savings_balance = st.sidebar.number_input(
    "Starting Savings Balance ($)",
    value=float(cfg["savings_balance"]),
    step=1000.0,
)
savings_apy = (
    st.sidebar.slider(
        "Savings APY (%)", 0.0, 10.0, float(cfg["savings_apy"]), 0.1
    )
    / 100.0
)

st.sidebar.header("2. Transfer Rules")
min_checking_buffer = st.sidebar.number_input(
    "Min Checking Buffer ($) [Sweep excess to savings]",
    value=float(cfg["min_checking_buffer"]),
    step=250.0,
)

# --- RECURRING FLOWS MANAGER (WITH EDIT & DELETE) ---
st.sidebar.header("3. Recurring Incomes & Expenditures")
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
st.sidebar.header("4. One-off Events")
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

# Synchronize config back to session state
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

    # 1. Apply Recurring Flows due on this exact day
    for flow in parsed_flows:
      if is_flow_due(d, flow["start_date"], flow["end_date"], flow["frequency"]):
        if flow["type"] == "Income":
          chk += flow["amount"]
        else:
          chk -= flow["amount"]

    # 2. Apply One-off Events due on this exact day
    date_str = d.strftime("%Y-%m-%d")
    for ev in cfg["one_offs"]:
      if ev["date"] == date_str:
        if ev.get("type", "Expenditure") == "Income":
          chk += ev["amount"]
        else:
          chk -= ev["amount"]

    # 3. Apply daily transfer rules (checking buffer sweep / deficit pull)
    if chk > min_checking_buffer:
      excess = chk - min_checking_buffer
      sav += excess
      chk = min_checking_buffer
    elif chk < 0:
      deficit = abs(chk)
      sav -= deficit
      chk = 0.0

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

with st.expander("View Detailed Monthly Breakdown Table"):
  st.dataframe(df_sim, use_container_width=True)