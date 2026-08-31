import streamlit as st
from datetime import datetime, date
from pathlib import Path
from supabase import create_client, Client

# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------
st.set_page_config(
    page_title="Smart Pill Dispenser",
    page_icon="💊",
    layout="centered"
)

# --------------------------------------------------
# MODERN AND ACCESSIBLE DESIGN
# --------------------------------------------------
st.markdown(
    """
    <style>
    .stApp {
        background-color: #f4f8fb;
    }

    .block-container {
        max-width: 800px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    .app-header {
        text-align: center;
        margin-bottom: 1.5rem;
    }

    .app-title {
        color: #12304a;
        font-size: 2.3rem;
        font-weight: 800;
        margin-bottom: 0.3rem;
    }

    .app-subtitle {
        color: #536b7c;
        font-size: 1.15rem;
    }

    .schedule-card {
        background-color: white;
        border: 1px solid #d9e4ec;
        border-left: 7px solid #16856f;
        border-radius: 14px;
        padding: 15px 18px;
        margin-bottom: 8px;
        box-shadow: 0 3px 10px rgba(25, 61, 89, 0.06);
    }

    .schedule-time {
        color: #12304a;
        font-size: 1.4rem;
        font-weight: 800;
        margin-bottom: 5px;
    }

    .medicine-name {
        color: #16856f;
        font-size: 1.15rem;
        font-weight: 700;
    }

    .schedule-detail {
        color: #536b7c;
        font-size: 1rem;
        margin-top: 3px;
    }

    .empty-schedule {
        background-color: #fff8e6;
        border: 1px solid #f0d78c;
        border-radius: 14px;
        padding: 1.3rem;
        text-align: center;
        color: #614d18;
        font-size: 1.1rem;
    }

    div[data-testid="stButton"] button {
        min-height: 48px;
        border-radius: 10px;
        font-size: 1.05rem;
        font-weight: 700;
    }

    div[data-testid="stNumberInput"] label,
    div[data-testid="stTextInput"] label,
    div[data-testid="stDateInput"] label,
    div[data-testid="stSelectbox"] label {
        color: #12304a;
        font-size: 1.05rem;
        font-weight: 700;
    }

    @media (max-width: 600px) {
        .app-title {
            font-size: 1.8rem;
        }

        .schedule-time {
            font-size: 1.2rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --------------------------------------------------
# SUPABASE CONNECTION
# --------------------------------------------------
@st.cache_resource
def initialize_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_ANON_KEY"]
    return create_client(url, key)


supabase = initialize_supabase()

# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------
def format_time(time_string):
    """Convert a 24-hour database time to 12-hour display time."""
    if not time_string:
        return "Time not provided"

    clean_time = str(time_string).split("+")[0]

    try:
        parsed_time = datetime.strptime(
            clean_time[:5],
            "%H:%M"
        )
        return parsed_time.strftime("%I:%M %p").lstrip("0")
    except ValueError:
        return str(time_string)


def format_date(date_string):
    """Convert database date to an easier-to-read date."""
    try:
        parsed_date = datetime.strptime(
            str(date_string),
            "%Y-%m-%d"
        )
        return parsed_date.strftime("%B %d, %Y")
    except ValueError:
        return str(date_string)


def get_schedules():
    """Retrieve all schedules from Supabase."""
    response = (
        supabase
        .table("medicines")
        .select("*")
        .order("dispense_date")
        .order("dispense_time")
        .execute()
    )

    return response.data or []


def schedule_exists(slot, medicine, selected_date, selected_time):
    """Check whether an identical schedule already exists."""
    response = (
        supabase
        .table("medicines")
        .select("id")
        .eq("slot_number", slot)
        .eq("medicine_name", medicine)
        .eq("dispense_date", str(selected_date))
        .eq("dispense_time", selected_time)
        .execute()
    )

    return bool(response.data)


def add_schedule(slot, medicine, selected_date, selected_time):
    """Insert a new schedule into Supabase."""
    supabase.table("medicines").insert(
        {
            "slot_number": slot,
            "medicine_name": medicine.strip(),
            "dispense_date": str(selected_date),
            "dispense_time": selected_time
        }
    ).execute()


def delete_schedule(schedule_id):
    """Delete a schedule and confirm that Supabase removed it."""

    if schedule_id is None:
        raise ValueError(
            "This medicine record has no ID. "
            "Check the medicines table in Supabase."
        )

    # Attempt deletion
    (
        supabase
        .table("medicines")
        .delete()
        .eq("id", schedule_id)
        .execute()
    )

    # Check whether the record still exists
    verification = (
        supabase
        .table("medicines")
        .select("id")
        .eq("id", schedule_id)
        .execute()
    )

    if verification.data:
        raise PermissionError(
            "Supabase blocked the deletion. "
            "A DELETE policy is probably missing."
        )


# --------------------------------------------------
# HEADER AND LOGO
# --------------------------------------------------
logo_path = Path("pill_dispenser_logo.png")

if logo_path.exists():
    left_space, logo_column, right_space = st.columns([1, 1.1, 1])

    with logo_column:
        st.image(
            str(logo_path),
            use_container_width=True
        )
else:
    st.markdown(
        "<div style='text-align:center; font-size:5rem;'>💊</div>",
        unsafe_allow_html=True
    )

st.markdown(
    """
    <div class="app-header">
        <div class="app-title">Smart Pill Dispenser</div>
        <div class="app-subtitle">
            Schedule medicines safely and easily.
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# --------------------------------------------------
# TIME OPTIONS
# --------------------------------------------------
time_options = [
    f"{hour:02d}:{minute:02d}"
    for hour in range(24)
    for minute in range(0, 60, 5)
]

display_time_options = {
    database_time: format_time(database_time)
    for database_time in time_options
}

# --------------------------------------------------
# ADD SCHEDULE FORM
# --------------------------------------------------
st.markdown("### ➕ Add a Medicine Schedule")

with st.form("medicine_schedule_form", clear_on_submit=True):
    dispense_date = st.date_input(
        "Dispense Date",
        value=date.today(),
        min_value=date.today(),
        help="Select the date when the medicine should be dispensed."
    )

    selected_time = st.selectbox(
        "Dispense Time",
        options=time_options,
        index=time_options.index("08:00"),
        format_func=lambda selected: display_time_options[selected],
        help="Times are available at five-minute intervals."
    )

    slot_column, medicine_column = st.columns([1, 2])

    with slot_column:
        slot_number = st.number_input(
            "Medicine Slot",
            min_value=1,
            max_value=16,
            value=1,
            step=1,
            help="Select the dispenser compartment containing the medicine."
        )

    with medicine_column:
        medicine_name = st.text_input(
            "Medicine Name",
            placeholder="Example: Vitamin C",
            help="Enter the name written on the medicine container."
        )

    st.info(
        f"Medicine will be dispensed on "
        f"**{format_date(dispense_date)}** at "
        f"**{format_time(selected_time)}**."
    )

    add_clicked = st.form_submit_button(
        "➕ Add to Schedule",
        type="primary",
        use_container_width=True
    )

# --------------------------------------------------
# SAVE LOGIC
# --------------------------------------------------
if add_clicked:
    cleaned_medicine_name = medicine_name.strip()

    if not cleaned_medicine_name:
        st.error("Please enter the medicine name.")

    else:
        try:
            duplicate_found = schedule_exists(
                int(slot_number),
                cleaned_medicine_name,
                dispense_date,
                selected_time
            )

            if duplicate_found:
                st.warning(
                    "This medicine schedule has already been added."
                )

            else:
                add_schedule(
                    int(slot_number),
                    cleaned_medicine_name,
                    dispense_date,
                    selected_time
                )

                st.success(
                    f"{cleaned_medicine_name} was scheduled for "
                    f"{format_time(selected_time)} on "
                    f"{format_date(dispense_date)}."
                )

                st.rerun()

        except Exception as error:
            st.error(
                "The schedule could not be saved. "
                "Please check the internet connection and try again."
            )
            st.exception(error)

# --------------------------------------------------
# DISPLAY EXISTING SCHEDULES
# --------------------------------------------------
st.markdown("---")

st.markdown(
    """
    <div style="
        color: #12304a;
        font-size: 1.65rem;
        font-weight: 800;
        margin: 1rem 0;
    ">
        📅 Existing Medicine Schedules
    </div>
    """,
    unsafe_allow_html=True
)

try:
    schedules = get_schedules()

except Exception as error:
    schedules = []
    st.error("The schedules could not be loaded.")
    st.exception(error)

if not schedules:
    st.markdown(
        """
<div class="empty-schedule">
<strong>No medicines are scheduled yet.</strong><br>
Complete the form above to add a schedule.
</div>
        """,
        unsafe_allow_html=True
    )

else:
    # Determine which schedules are currently checked.
    selected_schedules = [
        schedule
        for schedule in schedules
        if st.session_state.get(
            f"select_schedule_{schedule.get('id')}",
            False
        )
    ]

    selected_ids = [
        schedule["id"]
        for schedule in selected_schedules
        if schedule.get("id") is not None
    ]

    selected_count = len(selected_ids)

    # ----------------------------------------------
    # ACTION BAR ABOVE THE LIST
    # ----------------------------------------------
    count_column, delete_column = st.columns([3, 1.4])

    with count_column:
        if selected_count:
            st.info(
                f"✓ {selected_count} "
                f"{'schedule' if selected_count == 1 else 'schedules'} "
                "selected"
            )
        else:
            st.caption(
                f"{len(schedules)} medicine "
                f"{'schedule' if len(schedules) == 1 else 'schedules'}"
            )

    with delete_column:
        delete_selected = st.button(
            "🗑️ Delete Checked",
            key="delete_checked_schedules",
            disabled=selected_count == 0,
            use_container_width=True
        )

    # ----------------------------------------------
    # DELETE ALL CHECKED SCHEDULES
    # ----------------------------------------------
    if delete_selected:
        successfully_deleted = 0
        deletion_errors = []

        for schedule in selected_schedules:
            schedule_id = schedule.get("id")
            medicine = schedule.get(
                "medicine_name",
                "Unnamed medicine"
            )

            try:
                delete_schedule(schedule_id)
                successfully_deleted += 1

            except Exception as error:
                deletion_errors.append(
                    f"{medicine}: {str(error)}"
                )

        # Clear the checkbox states after deletion.
        for schedule_id in selected_ids:
            checkbox_key = f"select_schedule_{schedule_id}"

            if checkbox_key in st.session_state:
                del st.session_state[checkbox_key]

        if deletion_errors:
            st.error(
                "Some schedules could not be deleted:"
            )

            for error_message in deletion_errors:
                st.write(f"• {error_message}")

        else:
            st.toast(
                f"{successfully_deleted} "
                f"{'schedule was' if successfully_deleted == 1 else 'schedules were'} "
                "deleted.",
                icon="✅"
            )

            st.rerun()

    # ----------------------------------------------
    # SCHEDULE LIST
    # ----------------------------------------------
    for schedule in schedules:
        schedule_id = schedule.get("id")
        medicine = schedule.get(
            "medicine_name",
            "Unnamed medicine"
        )
        slot = schedule.get(
            "slot_number",
            "Not specified"
        )
        scheduled_date = schedule.get(
            "dispense_date",
            ""
        )
        scheduled_time = schedule.get(
            "dispense_time",
            ""
        )

        checkbox_column, information_column = st.columns(
            [0.45, 5]
        )

        # Checkbox appears before the schedule card.
        with checkbox_column:
            st.checkbox(
                "Select",
                key=f"select_schedule_{schedule_id}",
                label_visibility="collapsed",
                help=f"Select {medicine}"
            )

        with information_column:
            card_html = (
                '<div class="schedule-card">'
                '<div class="schedule-time">'
                f'⏰ {format_time(scheduled_time)}'
                '</div>'
                '<div class="medicine-name">'
                f'💊 {medicine}'
                '</div>'
                '<div class="schedule-detail">'
                f'📅 {format_date(scheduled_date)}'
                f' &nbsp;|&nbsp; Slot {slot}'
                '</div>'
                '</div>'
            )

            st.markdown(
                card_html,
                unsafe_allow_html=True
            )
# --------------------------------------------------
# FOOTER
# --------------------------------------------------
st.markdown("---")
st.caption(
    "Before filling the dispenser, verify the medicine name, "
    "slot number, date, and dispensing time."
)