import streamlit as st
from datetime import time, date
from supabase import create_client, Client

# --- Supabase client ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_ANON_KEY"]
supabase: Client = create_client(url, key)

st.subheader("⏰ Schedule Medicine")

# --- DATE INPUT ---
dispense_date = st.date_input(
    "Dispense Date",
    value=date.today()
)

# --- TIME INPUT: 5-minute intervals ---
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

# Convert string to time object
hour, minute = map(int, selected_time.split(":"))
dispense_time = time(hour, minute)

st.caption("✔ Time selectable in 5-minute intervals (5, 10, 15, 30)")

# --- ADD NEW SCHEDULE SIDE BY SIDE ---
slot_number = st.number_input("Slot Number (1-16)", min_value=1, max_value=16, value=1)

col1, col2 = st.columns([3, 1])  # 3:1 width ratio
with col1:
    medicine_name = st.text_input("Medicine Name", "")
with col2:
    add_clicked = st.button("Add Schedule")

# --- SAVE LOGIC ---
if add_clicked:
    if not medicine_name.strip():
        st.error("Please enter a medicine name.")
    else:
        supabase.table("medicines").insert({
            "slot_number": slot_number,
            "medicine_name": medicine_name,
            "dispense_date": str(dispense_date),
            "dispense_time": dispense_time.strftime("%H:%M")
        }).execute()
        st.success(f"Medicine scheduled for {selected_time} on {dispense_date}")
        st.experimental_rerun()  # Refresh the list

# --- DISPLAY EXISTING SCHEDULES BELOW ---
st.subheader("📝 Existing Dispense Times")
existing_times = supabase.table("medicines").select("*").order("dispense_time").execute()
times_list = existing_times.data

if times_list:
    for t in times_list:
        st.write(f"Slot {t['slot_number']} | {t['medicine_name']} | {t['dispense_date']} | {t['dispense_time']}")
else:
    st.write("No medicines scheduled yet.")