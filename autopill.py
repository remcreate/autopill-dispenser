import streamlit as st
from supabase import create_client
from datetime import date, time

# -----------------------------
# SUPABASE CONFIG
# -----------------------------
SUPABASE_URL = "https://upaosgbtlhoswfexnxmq.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVwYW9zZ2J0bGhvc3dmZXhueG1xIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMyNTUwMjcsImV4cCI6MjA4ODgzMTAyN30.BYehjjT2H4niCoe_WfBTmxCD1jX83uB8V-wou8RGwUQ"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Smart Pill Dispenser", layout="wide")

st.title("💊 Smart Pill Dispenser")

# -----------------------------
# ADD MEDICINE SCHEDULE
# -----------------------------
st.header("➕ Schedule Medicine")

with st.form("add_medicine"):
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        slot_number = st.number_input("Slot Number", min_value=1, max_value=16)

    with col2:
        medicine_name = st.text_input("Medicine Name")

    with col3:
        dispense_date = st.date_input("Dispense Date", value=date.today())

    with col4:
        dispense_time = st.time_input("Dispense Time")

    submitted = st.form_submit_button("Save Schedule")

    if submitted:
        if medicine_name.strip() == "":
            st.error("Medicine name is required")
        else:
            supabase.table("medicines").insert({
                "slot_number": slot_number,
                "medicine_name": medicine_name,
                "dispense_date": str(dispense_date),
                "dispense_time": str(dispense_time)
            }).execute()

            st.success("Medicine scheduled successfully")

# -----------------------------
# VIEW SCHEDULES
# -----------------------------
st.header("📅 Scheduled Medicines")

data = supabase.table("medicines").select("*").order("dispense_date").execute()

if data.data:
    for med in data.data:
        with st.expander(f"Slot {med['slot_number']} – {med['medicine_name']}"):
            col1, col2, col3 = st.columns(3)

            col1.write(f"📅 Date: {med['dispense_date']}")
            col2.write(f"⏰ Time: {med['dispense_time']}")

            status = "✅ Taken" if med["is_taken"] else "🕒 Pending"
            col3.write(f"Status: {status}")

            col4, col5 = st.columns(2)

            if col4.button("Mark as Dispensed", key=f"d_{med['id']}"):
                supabase.table("medicines").update(
                    {"is_dispensed": True}
                ).eq("id", med["id"]).execute()

                supabase.table("dispense_logs").insert({
                    "medicine_id": med["id"],
                    "event": "DISPENSED"
                }).execute()

                st.experimental_rerun()

            if col5.button("Mark as Taken", key=f"t_{med['id']}"):
                supabase.table("medicines").update(
                    {"is_taken": True}
                ).eq("id", med["id"]).execute()

                supabase.table("dispense_logs").insert({
                    "medicine_id": med["id"],
                    "event": "TAKEN"
                }).execute()

                st.experimental_rerun()
else:
    st.info("No medicine schedules yet")

# -----------------------------
# LOG HISTORY
# -----------------------------
st.header("📜 Dispense History")

logs = supabase.table("dispense_logs").select(
    "event, event_time, medicines(medicine_name, slot_number)"
).order("event_time", desc=True).execute()

if logs.data:
    for log in logs.data:
        med = log["medicines"]
        st.write(
            f"{log['event_time']} — Slot {med['slot_number']} "
            f"({med['medicine_name']}): {log['event']}"
        )
else:
    st.info("No activity yet")