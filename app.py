import json
from datetime import date, datetime
import pandas as pd
import plotly.express as px
import streamlit as st

# --- 1. PAGE CONFIG & SETUP ---
st.set_page_config(
    page_title="Financial Projections", page_icon="📈", layout="wide"
)

UNITS = ["Days", "Weeks", "Months", "Years"]


def last_day_of_month(year: int, month: int) -> int:
  first_of_month = date(year, month, 1)
  next_month = first_of_month + pd.DateOffset(months=1)
  last_day = next_month - pd.DateOffset(days=1)
  return last_day.day


def normalize_flow_schedule(flow: dict) -> tuple[int, str]:
  """Returns (interval, unit) for both custom and legacy frequency formats."""
  if "interval" in flow and "unit" in flow:
    return max(1, int(flow["interval"])), flow["unit"]

  legacy = flow.get("frequency", "Monthly")
  mapping = {
      "Daily": (1, "Days"),
      "Weekly": (1, "Weeks"),
      "Bi-weekly": (2, "Weeks"),
      "Monthly": (1, "Months"),
      "Annually": (1, "Years"),
  }
  return mapping.get(legacy, (1, "Months"))


def format_flow_schedule(flow: dict) -> str:
  interval, unit = normalize_flow_schedule(flow)
  if interval == 1:
    singular = unit[:-1] if unit.endswith("s") else unit
    return singular
  return f"Every {interval} {unit}"


def get_flow_amount_on_date(flow: dict, d: date) -> float:
  """Applies compounded annual raises after each full year since start_date."""
  base_amount = float(flow["amount"])
  if flow.get("type") != "Income" or not flow.get("is_job", False):
    return base_amount

  raise_pct = float(flow.get("yearly_raise_pct", 0.0))
  if raise_pct == 0.0:
    return base_amount

  f_start: date = flow["start_date"]
  completed_years = (d.year - f_start.year) - (
      1 if (d.month, d.day) < (f_start.month, f_start.day) else 0
  )
  if completed_years <= 0:
    return base_amount

  return base_amount * ((1.0 + raise_pct / 100.0) ** completed_years)


# --- 2. SESSION STATE INITIALIZATION ---
if "plan_config" not in st.session_state:
  st.session_state.plan_config = {
      "start_date": str(date.today()),
      "months": 12,
      "checking_balance": 0,
      "checking_apy": 0.5,
      "savings_balance": 0,
      "savings_apy": 4.0,
      "min_checking_buffer": 2000.0,
      "recurring_flows": [],
      "one_offs": [],
  }

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


st.title("Financial Projections")
st.markdown(
    "Simulate accounts with exact daily transactions, custom recurring"
    " intervals, Increment buffer sweeps, and monthly APR"
    " compounding."
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

# --- 4. SIDEBAR INPUTS ---
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
        "Checking APR (%)", 0.0, 5.0, key="w_chk_apy", step=0.1
    )
    / 100.0
)

savings_balance = st.sidebar.number_input(
    "Starting Savings Balance ($)", key="w_sav_bal", step=1000.0
)
savings_apy = (
    st.sidebar.slider("Savings APR (%)", 0.0, 10.0, key="w_sav_apy", step=0.1)
    / 100.0
)

st.sidebar.header("Transfer Rules")
min_checking_buffer = st.sidebar.number_input(
    "Min Checking Buffer ($) [Sweep excess in $1k increments]",
    key="w_min_buf",
    step=250.0,
)

# --- RECURRING FLOWS MANAGER (JOB RAISE + CUSTOM INTERVAL + EDIT & DELETE) ---
st.sidebar.header("Recurring Incomes & Expenditures")
with st.sidebar.expander("Add New Recurring Flow", expanded=False):
  flow_name = st.text_input("Flow Name", value="Side Gig", key="flow_name")
  flow_type = st.selectbox("Type", ["Income", "Expenditure"], key="flow_type")

  flow_is_job = False
  flow_yearly_raise = 0.0
  if flow_type == "Income":
    flow_is_job = st.checkbox(
        "This income is a Job", value=False, key="flow_is_job"
    )
    if st.session_state.get("flow_is_job", False):
      flow_yearly_raise = st.number_input(
          "Estimated Yearly Raise (%)",
          min_value=-50.0,
          max_value=100.0,
          value=3.0,
          step=0.5,
          key="flow_yearly_raise",
      )

  flow_amount = st.number_input("Amount ($)", value=500.0, key="flow_amount")

  st.markdown("**Repeat Every**")
  c_num, c_unit = st.columns([1, 2])
  flow_interval = c_num.number_input(
      "Interval", min_value=1, max_value=365, value=1, step=1, key="flow_interval"
  )
  flow_unit = c_unit.selectbox("Unit", UNITS, index=2, key="flow_unit")

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
            "is_job": bool(flow_is_job) if flow_type == "Income" else False,
            "yearly_raise_pct": (
                float(flow_yearly_raise)
                if (flow_type == "Income" and flow_is_job)
                else 0.0
            ),
            "amount": float(flow_amount),
            "interval": int(flow_interval),
            "unit": flow_unit,
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
    sched_label = format_flow_schedule(flow)
    job_tag = ""
    if flow["type"] == "Income" and flow.get("is_job", False):
      job_tag = f" [Job, +{flow.get('yearly_raise_pct', 0.0)}%/yr]"
    end_str = (
        f" (until {flow['end_date']})" if flow.get("end_date") else " (Ongoing)"
    )
    c1.text(
        f"[{flow['type']}]{job_tag} {flow['name']}: {sign}${flow['amount']}"
        f" ({sched_label}){end_str}"
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

      e_is_job = False
      e_yearly_raise = 0.0
      if e_type == "Income":
        e_is_job = st.checkbox(
            "This income is a Job",
            value=bool(flow.get("is_job", False)),
            key=f"e_is_job_{i}",
        )
        if st.session_state.get(
            f"e_is_job_{i}", bool(flow.get("is_job", False))
        ):
          e_yearly_raise = st.number_input(
              "Estimated Yearly Raise (%)",
              min_value=-50.0,
              max_value=100.0,
              value=float(flow.get("yearly_raise_pct", 0.0)),
              step=0.5,
              key=f"e_yearly_raise_{i}",
          )

      e_amount = st.number_input(
          "Amount ($)", value=float(flow["amount"]), key=f"e_amount_{i}"
      )

      cur_interval, cur_unit = normalize_flow_schedule(flow)
      st.markdown("**Repeat Every**")
      ec_num, ec_unit = st.columns([1, 2])
      e_interval = ec_num.number_input(
          "Interval",
          min_value=1,
          max_value=365,
          value=cur_interval,
          step=1,
          key=f"e_interval_{i}",
      )
      e_unit = ec_unit.selectbox(
          "Unit",
          UNITS,
          index=UNITS.index(cur_unit) if cur_unit in UNITS else 2,
          key=f"e_unit_{i}",
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
            "is_job": bool(e_is_job) if e_type == "Income" else False,
            "yearly_raise_pct": (
                float(e_yearly_raise)
                if (e_type == "Income" and e_is_job)
                else 0.0
            ),
            "amount": float(e_amount),
            "interval": int(e_interval),
            "unit": e_unit,
            "start_date": e_start.strftime("%Y-%m-%d"),
            "end_date": e_end.strftime("%Y-%m-%d") if e_end else None,
        }
        st.session_state[edit_key] = False
        st.rerun()
      if col_cancel.button("Cancel", key=f"cancel_edit_{i}"):
        st.session_state[edit_key] = False
        st.rerun()
    st.sidebar.markdown("---")

# --- ONE-OFF EVENTS MANAGER ---
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
def is_flow_due(
    d: date, f_start: date, f_end: date | None, interval: int, unit: str
) -> bool:
  if d < f_start:
    return False
  if f_end and d > f_end:
    return False

  interval = max(1, interval)
  if unit == "Days":
    return (d - f_start).days % interval == 0
  if unit == "Weeks":
    return (d - f_start).days % (interval * 7) == 0
  if unit == "Months":
    months_diff = (d.year - f_start.year) * 12 + (d.month - f_start.month)
    if months_diff < 0 or months_diff % interval != 0:
      return False
    target_day = min(f_start.day, last_day_of_month(d.year, d.month))
    return d.day == target_day
  if unit == "Years":
    years_diff = d.year - f_start.year
    if years_diff < 0 or years_diff % interval != 0:
      return False
    target_day = min(f_start.day, last_day_of_month(d.year, f_start.month))
    return d.month == f_start.month and d.day == target_day
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
      future_d = dates_list[curr_idx + offset].date()

      for flow in parsed_flows:
        if flow["type"] == "Expenditure" and is_flow_due(
            future_d,
            flow["start_date"],
            flow["end_date"],
            flow["interval"],
            flow["unit"],
        ):
          total_out += flow["amount"]

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
    interval, unit = normalize_flow_schedule(flow)
    parsed_flows.append({
        "name": flow["name"],
        "type": flow["type"],
        "is_job": bool(flow.get("is_job", False)),
        "yearly_raise_pct": float(flow.get("yearly_raise_pct", 0.0)),
        "amount": float(flow["amount"]),
        "interval": interval,
        "unit": unit,
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
    day_transfer = 0.0

    # 1. Apply Recurring Flows due on this exact day (with yearly job raise if applicable)
    for flow in parsed_flows:
      if is_flow_due(
          d,
          flow["start_date"],
          flow["end_date"],
          flow["interval"],
          flow["unit"],
      ):
        amt = get_flow_amount_on_date(flow, d)
        if flow["type"] == "Income":
          chk += amt
          day_income += amt
        else:
          chk -= amt
          day_expenditure += amt

    # 2. Apply One-off Events due on this exact day
    date_str = d.strftime("%Y-%m-%d")
    for ev in cfg["one_offs"]:
      if ev["date"] == date_str:
        amt = float(ev["amount"])
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
        potential_sweep = (excess // 1000.0) * 1000.0
        upcoming_bills = get_upcoming_outflows(
            d, dates, parsed_flows, cfg["one_offs"], lookahead_days=7
        )
        safe_cash_after_sweep = chk - potential_sweep - upcoming_bills

        if safe_cash_after_sweep >= min_checking_buffer:
          sav += potential_sweep
          chk -= potential_sweep
          day_transfer = potential_sweep
    elif chk < 0:
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

st.subheader("Daily Account Trajectory")
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