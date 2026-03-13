import streamlit as st
from datetime import time, date
from supabase import create_client, Client

# --- Supabase client ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_ANON_KEY"]
supabase: Client = create_client(url, key)

st.title("💊 Smart Pill Dispenser Scheduler")

# --- DATE INPUT ---
dispense_date = st.date_input("Dispense Date", value=date.today())

# --- TIME INPUT: 5-minute intervals ---
time_options = [f"{hour:02d}:{minute:02d}" for hour in range(24) for minute in range(0, 60, 5)]
selected_time = st.selectbox(
    "Dispense Time",
    time_options,
    index=time_options.index("08:00") if "08:00" in time_options else 0
)
hour, minute = map(int, selected_time.split(":"))
dispense_time = time(hour, minute)
st.caption("✔ Time selectable in 5-minute intervals (5, 10, 15, 30)")

# --- ADD NEW SCHEDULE IN ONE ROW ---
col1, col2, col3 = st.columns([1, 3, 1])
with col1:
    slot_number = st.number_input("Slot Number", min_value=1, max_value=16, value=1, key="slot_input")
with col2:
    # Use a temporary variable instead of binding to session_state
    medicine_name_temp = st.text_input("Medicine Name", "")
with col3:
    add_clicked = st.button("Add Schedule", key="add_button")

# --- SAVE LOGIC ---
if add_clicked:
    if not medicine_name_temp.strip():
        st.error("Please enter a medicine name.")
    else:
        supabase.table("medicines").insert({
            "slot_number": slot_number,
            "medicine_name": medicine_name_temp,
            "dispense_date": str(dispense_date),
            "dispense_time": dispense_time.strftime("%H:%M")
        }).execute()
        st.success(f"Medicine scheduled for {selected_time} on {dispense_date}")
        # No need to reset session_state key — using a temp variable avoids the error

# --- DISPLAY EXISTING SCHEDULES BELOW ---
st.subheader("📝 Existing Dispense Times")
existing_times = supabase.table("medicines").select("*").order("dispense_time").execute()
times_list = existing_times.data

if times_list:
    for t in times_list:
        st.write(f"Slot {t['slot_number']} | {t['medicine_name']} | {t['dispense_date']} | {t['dispense_time']}")
else:
    st.write("No medicines scheduled yet.")