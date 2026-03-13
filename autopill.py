import streamlit as st
from datetime import time, date

st.subheader("⏰ Schedule Medicine")

# -----------------------------
# DATE INPUT
# -----------------------------
dispense_date = st.date_input(
    "Dispense Date",
    value=date.today()
)

# -----------------------------
# TIME INPUT (5-minute steps)
# -----------------------------
time_options = [
    f"{hour:02d}:{minute:02d}"
    for hour in range(24)
    for minute in range(0, 60, 5)
]

selected_time = st.selectbox(
    "Dispense Time",
    time_options,
    index=time_options.index("08:00") if "08:00" in time_options else 0
)

# Convert selected string to time object
hour, minute = map(int, selected_time.split(":"))
dispense_time = time(hour, minute)

st.caption("✔ Time selectable in 5-minute intervals (5, 10, 15, 30)")