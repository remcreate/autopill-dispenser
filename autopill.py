import streamlit as st
from datetime import datetime, date, timedelta
from pathlib import Path
from html import escape
from supabase import create_client, Client
import math

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
        max-width: 850px;
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

    .section-heading {
        color: #12304a;
        font-size: 1.65rem;
        font-weight: 800;
        margin: 1rem 0;
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
        border-radius: 10px;
        font-size: 1rem;
        font-weight: 700;
    }

    div[data-testid="stNumberInput"] label,
    div[data-testid="stTextInput"] label,
    div[data-testid="stDateInput"] label,
    div[data-testid="stSelectbox"] label,
    div[data-testid="stMultiSelect"] label {
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
    """Convert a 24-hour time to a readable 12-hour time."""
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
    """Convert a database date to a readable date."""
    try:
        parsed_date = datetime.strptime(
            str(date_string),
            "%Y-%m-%d"
        )

        return parsed_date.strftime("%B %d, %Y")

    except ValueError:
        return str(date_string)


def create_date_range(start_date, end_date):
    """Create a list containing every date in the range."""
    number_of_days = (end_date - start_date).days

    return [
        start_date + timedelta(days=offset)
        for offset in range(number_of_days + 1)
    ]


def get_schedules():
    """Retrieve all saved medicine schedules."""
    response = (
        supabase
        .table("medicines")
        .select("*")
        .order("dispense_date")
        .order("dispense_time")
        .execute()
    )

    return response.data or []


def normalize_database_time(time_value):
    """Normalize a Supabase time value to HH:MM."""
    if not time_value:
        return ""

    return str(time_value).split("+")[0][:5]


def get_existing_schedule_keys(start_date, end_date):
    """Retrieve existing schedules within the selected date range."""
    response = (
        supabase
        .table("medicines")
        .select(
            "slot_number,"
            "medicine_name,"
            "dispense_date,"
            "dispense_time"
        )
        .gte("dispense_date", str(start_date))
        .lte("dispense_date", str(end_date))
        .execute()
    )

    existing_keys = set()

    for schedule in response.data or []:
        existing_keys.add(
            (
                int(schedule.get("slot_number", 0)),
                str(schedule.get("medicine_name", "")).strip().casefold(),
                str(schedule.get("dispense_date", "")),
                normalize_database_time(
                    schedule.get("dispense_time")
                )
            )
        )

    return existing_keys


def save_multiple_schedules(
    start_date,
    end_date,
    medicine_entries
):
    """
    Save schedules for every selected date, medicine, and time.

    Returns:
        saved_count: Number of new records inserted
        skipped_count: Number of duplicate records skipped
    """
    existing_keys = get_existing_schedule_keys(
        start_date,
        end_date
    )

    new_keys = set()
    records_to_insert = []
    skipped_count = 0

    for scheduled_date in create_date_range(
        start_date,
        end_date
    ):
        for medicine_entry in medicine_entries:
            for scheduled_time in medicine_entry["times"]:
                schedule_key = (
                    medicine_entry["slot"],
                    medicine_entry["medicine"].casefold(),
                    str(scheduled_date),
                    scheduled_time
                )

                if (
                    schedule_key in existing_keys
                    or schedule_key in new_keys
                ):
                    skipped_count += 1
                    continue

                records_to_insert.append(
                    {
                        "slot_number": medicine_entry["slot"],
                        "medicine_name": medicine_entry["medicine"],
                        "dispense_date": str(scheduled_date),
                        "dispense_time": scheduled_time
                    }
                )

                new_keys.add(schedule_key)

    # Insert in smaller batches to avoid a very large request.
    batch_size = 500

    for start_index in range(
        0,
        len(records_to_insert),
        batch_size
    ):
        current_batch = records_to_insert[
            start_index:start_index + batch_size
        ]

        (
            supabase
            .table("medicines")
            .insert(current_batch)
            .execute()
        )

    return len(records_to_insert), skipped_count


def delete_schedule(schedule_id):
    """Delete one schedule and verify that it was removed."""
    if schedule_id is None:
        raise ValueError(
            "This medicine record has no ID."
        )

    (
        supabase
        .table("medicines")
        .delete()
        .eq("id", schedule_id)
        .execute()
    )

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
            "Check the DELETE policy."
        )

def get_slot_medicines(schedules):
    """
    Organize current and future medicines according to slot.

    Repeated schedules for the same medicine are shown only once.
    """
    slot_medicines = {
        slot_number: set()
        for slot_number in range(1, 16)
    }

    today_string = str(date.today())

    for schedule in schedules:
        dispense_date = str(
            schedule.get("dispense_date", "")
        )

        # Do not include expired schedules in the loading guide.
        if dispense_date and dispense_date < today_string:
            continue

        try:
            slot_number = int(
                schedule.get("slot_number", 0)
            )
        except (TypeError, ValueError):
            continue

        medicine_name = str(
            schedule.get("medicine_name", "")
        ).strip()

        if (
            1 <= slot_number <= 15
            and medicine_name
        ):
            slot_medicines[slot_number].add(
                medicine_name
            )

    return slot_medicines


def shorten_medicine_name(medicine_names):
    """Create a short label that fits inside a slot."""
    if not medicine_names:
        return "EMPTY"

    if len(medicine_names) > 1:
        return "MULTIPLE"

    medicine_name = next(iter(medicine_names))

    if len(medicine_name) > 13:
        return medicine_name[:11] + "…"

    return medicine_name


def create_dispenser_svg(slot_medicines):
    """
    Create a circular 15-slot dispenser diagram.

    Slot 1 is placed at the dispensing opening at the bottom.
    Slot numbers increase clockwise because the motor turns
    counterclockwise.
    """
    width = 700
    height = 720
    center_x = 350
    center_y = 330
    radius = 265
    label_radius = 185
    slot_angle = 360 / 15

    occupied_colors = [
        "#B8E8E0",
        "#A8DADC",
        "#BDE0FE",
        "#CDE7FF",
        "#D7E3FC"
    ]

    empty_color = "#EEF3F6"

    svg_parts = [
        (
            f'<svg viewBox="0 0 {width} {height}" '
            'xmlns="http://www.w3.org/2000/svg" '
            'style="width:100%; max-width:700px; height:auto;">'
        ),
        (
            '<rect width="100%" height="100%" '
            'fill="transparent"/>'
        )
    ]

    for slot_number in range(1, 16):
        # Slot 1 is centered at 90 degrees, or the bottom.
        # Increasing SVG angles move clockwise.
        center_angle = 90 + (
            (slot_number - 1) * slot_angle
        )

        start_angle = center_angle - slot_angle / 2
        end_angle = center_angle + slot_angle / 2

        start_radians = math.radians(start_angle)
        end_radians = math.radians(end_angle)
        center_radians = math.radians(center_angle)

        start_x = (
            center_x
            + radius * math.cos(start_radians)
        )
        start_y = (
            center_y
            + radius * math.sin(start_radians)
        )

        end_x = (
            center_x
            + radius * math.cos(end_radians)
        )
        end_y = (
            center_y
            + radius * math.sin(end_radians)
        )

        label_x = (
            center_x
            + label_radius * math.cos(center_radians)
        )
        label_y = (
            center_y
            + label_radius * math.sin(center_radians)
        )

        medicine_names = slot_medicines.get(
            slot_number,
            set()
        )

        if medicine_names:
            fill_color = occupied_colors[
                (slot_number - 1) % len(occupied_colors)
            ]
        else:
            fill_color = empty_color

        short_name = escape(
            shorten_medicine_name(medicine_names)
        )

        path = (
            f"M {center_x} {center_y} "
            f"L {start_x:.2f} {start_y:.2f} "
            f"A {radius} {radius} 0 0 1 "
            f"{end_x:.2f} {end_y:.2f} Z"
        )

        svg_parts.append(
            f'<path d="{path}" '
            f'fill="{fill_color}" '
            'stroke="#FFFFFF" '
            'stroke-width="4"/>'
        )

        svg_parts.append(
            f'<text x="{label_x:.2f}" '
            f'y="{label_y - 7:.2f}" '
            'text-anchor="middle" '
            'font-family="Arial, sans-serif" '
            'font-size="18" '
            'font-weight="800" '
            'fill="#12304A">'
            f'{slot_number}'
            '</text>'
        )

        svg_parts.append(
            f'<text x="{label_x:.2f}" '
            f'y="{label_y + 13:.2f}" '
            'text-anchor="middle" '
            'font-family="Arial, sans-serif" '
            'font-size="10" '
            'font-weight="700" '
            'fill="#36566E">'
            f'{short_name}'
            '</text>'
        )

    # Center circle and motor direction
    svg_parts.extend(
        [
            (
                f'<circle cx="{center_x}" '
                f'cy="{center_y}" r="82" '
                'fill="#12304A" '
                'stroke="#FFFFFF" '
                'stroke-width="5"/>'
            ),
            (
                f'<text x="{center_x}" '
                f'y="{center_y - 7}" '
                'text-anchor="middle" '
                'font-family="Arial, sans-serif" '
                'font-size="45" '
                'font-weight="800" '
                'fill="#FFFFFF">↺</text>'
            ),
            (
                f'<text x="{center_x}" '
                f'y="{center_y + 24}" '
                'text-anchor="middle" '
                'font-family="Arial, sans-serif" '
                'font-size="12" '
                'font-weight="700" '
                'fill="#FFFFFF">'
                'COUNTERCLOCKWISE'
                '</text>'
            ),
            # Dispensing opening marker
            (
                f'<path d="M {center_x - 24} 610 '
                f'L {center_x} 635 '
                f'L {center_x + 24} 610 Z" '
                'fill="#FF6B5F"/>'
            ),
            (
                f'<text x="{center_x}" y="670" '
                'text-anchor="middle" '
                'font-family="Arial, sans-serif" '
                'font-size="16" '
                'font-weight="800" '
                'fill="#12304A">'
                'DISPENSING OPENING / HOME POSITION'
                '</text>'
            ),
            (
                f'<text x="{center_x}" y="695" '
                'text-anchor="middle" '
                'font-family="Arial, sans-serif" '
                'font-size="14" '
                'fill="#536B7C">'
                'Align Slot 1 with this opening before loading'
                '</text>'
            ),
            '</svg>'
        ]
    )

    return "".join(svg_parts)

# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------
if "medicine_rows" not in st.session_state:
    st.session_state["medicine_rows"] = [0]

if "next_medicine_row_id" not in st.session_state:
    st.session_state["next_medicine_row_id"] = 1

# --------------------------------------------------
# HEADER AND LOGO
# --------------------------------------------------
logo_path = Path("pill_dispenser_logo.png")

if logo_path.exists():
    left_space, logo_column, right_space = st.columns(
        [1, 1.1, 1]
    )

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
# CREATE SCHEDULE
# --------------------------------------------------
st.markdown(
    '<div class="section-heading">➕ Create Medicine Schedule</div>',
    unsafe_allow_html=True
)

st.write(
    "Choose the dates, then add each medicine and its "
    "dispensing times."
)

# --------------------------------------------------
# DATE RANGE
# --------------------------------------------------
st.markdown("#### 📅 Dispensing Dates")

from_column, to_column = st.columns(2)

with from_column:
    start_date = st.date_input(
        "From",
        value=date.today(),
        min_value=date.today(),
        key="schedule_start_date"
    )

with to_column:
    end_date = st.date_input(
        "To",
        value=max(
            start_date,
            st.session_state.get(
                "schedule_end_date",
                start_date
            )
        ),
        min_value=start_date,
        key="schedule_end_date"
    )

date_range_is_valid = end_date >= start_date

if not date_range_is_valid:
    st.error(
        "The ending date cannot be earlier than "
        "the starting date."
    )

number_of_days = (
    (end_date - start_date).days + 1
    if date_range_is_valid
    else 0
)

if date_range_is_valid:
    st.info(
        f"Schedules will be created from "
        f"**{format_date(start_date)}** to "
        f"**{format_date(end_date)}** "
        f"({number_of_days} "
        f"{'day' if number_of_days == 1 else 'days'})."
    )

# --------------------------------------------------
# MEDICINE INPUTS
# --------------------------------------------------
st.markdown("#### 💊 Medicines and Times")

for row_number, row_id in enumerate(
    st.session_state["medicine_rows"],
    start=1
):
    with st.container(border=True):
        heading_column, remove_column = st.columns(
            [4, 1.3]
        )

        with heading_column:
            st.markdown(
                f"##### Medicine {row_number}"
            )

        with remove_column:
            if len(st.session_state["medicine_rows"]) > 1:
                if st.button(
                    "✕ Remove",
                    key=f"remove_medicine_{row_id}",
                    use_container_width=True
                ):
                    st.session_state["medicine_rows"].remove(
                        row_id
                    )
                    st.rerun()

        medicine_column, slot_column = st.columns([3, 1])

        with medicine_column:
            st.text_input(
                "Medicine Name",
                placeholder="Example: Paracetamol",
                key=f"medicine_name_{row_id}"
            )

        with slot_column:
            st.number_input(
                "Slot",
                min_value=1,
                max_value=16,
                value=min(row_number, 16),
                step=1,
                key=f"medicine_slot_{row_id}",
                help="Dispenser compartment number"
            )

        st.multiselect(
            "Dispensing Times",
            options=time_options,
            default=["08:00"],
            format_func=lambda selected: (
                display_time_options[selected]
            ),
            key=f"medicine_times_{row_id}",
            help=(
                "Select one or more dispensing times "
                "for this medicine."
            )
        )

# --------------------------------------------------
# ADD ANOTHER MEDICINE
# --------------------------------------------------
add_medicine_column, blank_column = st.columns([2, 3])

with add_medicine_column:
    if st.button(
        "➕ Add Another Medicine",
        use_container_width=True
    ):
        new_row_id = st.session_state[
            "next_medicine_row_id"
        ]

        st.session_state["medicine_rows"].append(
            new_row_id
        )

        st.session_state[
            "next_medicine_row_id"
        ] += 1

        st.rerun()

# --------------------------------------------------
# PREVIEW TOTAL
# --------------------------------------------------
times_per_day = 0

for row_id in st.session_state["medicine_rows"]:
    preview_name = st.session_state.get(
        f"medicine_name_{row_id}",
        ""
    ).strip()

    preview_times = st.session_state.get(
        f"medicine_times_{row_id}",
        []
    )

    if preview_name and preview_times:
        times_per_day += len(preview_times)

total_preview_schedules = (
    times_per_day * number_of_days
)

if total_preview_schedules:
    st.info(
        f"This will create up to "
        f"**{total_preview_schedules} dispensing schedules**."
    )

# --------------------------------------------------
# SAVE ALL SCHEDULES
# --------------------------------------------------
save_schedules_clicked = st.button(
    "💾 Save All Schedules",
    type="primary",
    use_container_width=True,
    disabled=not date_range_is_valid
)

if save_schedules_clicked:
    medicine_entries = []
    validation_errors = []

    for row_number, row_id in enumerate(
        st.session_state["medicine_rows"],
        start=1
    ):
        medicine_name = st.session_state.get(
            f"medicine_name_{row_id}",
            ""
        ).strip()

        medicine_slot = st.session_state.get(
            f"medicine_slot_{row_id}",
            1
        )

        medicine_times = st.session_state.get(
            f"medicine_times_{row_id}",
            []
        )

        if not medicine_name:
            validation_errors.append(
                f"Enter the name of Medicine {row_number}."
            )

        if not medicine_times:
            validation_errors.append(
                f"Select at least one time for "
                f"Medicine {row_number}."
            )

        if medicine_name and medicine_times:
            medicine_entries.append(
                {
                    "medicine": medicine_name,
                    "slot": int(medicine_slot),
                    "times": sorted(medicine_times)
                }
            )

    if validation_errors:
        for validation_message in validation_errors:
            st.error(validation_message)

    elif not date_range_is_valid:
        st.error(
            "Please select a valid date range."
        )

    else:
        try:
            saved_count, skipped_count = (
                save_multiple_schedules(
                    start_date,
                    end_date,
                    medicine_entries
                )
            )

            if saved_count:
                st.success(
                    f"{saved_count} dispensing "
                    f"{'schedule was' if saved_count == 1 else 'schedules were'} "
                    "saved successfully."
                )

            if skipped_count:
                st.warning(
                    f"{skipped_count} duplicate "
                    f"{'schedule was' if skipped_count == 1 else 'schedules were'} "
                    "not added."
                )

            if not saved_count and not skipped_count:
                st.warning(
                    "There were no schedules to save."
                )

        except Exception as error:
            st.error(
                "The schedules could not be saved. "
                "Please check the Supabase connection."
            )
            st.exception(error)

# --------------------------------------------------
# DISPLAY EXISTING SCHEDULES
# --------------------------------------------------
st.markdown("---")

st.markdown(
    '<div class="section-heading">'
    '📅 Existing Medicine Schedules'
    '</div>',
    unsafe_allow_html=True
)

try:
    schedules = get_schedules()

except Exception as error:
    schedules = []
    st.error("The schedules could not be loaded.")
    st.exception(error)
# --------------------------------------------------
# MEDICINE LOADING GUIDE
# --------------------------------------------------
if schedules:
    st.markdown(
        '<div class="section-heading">'
        '🍕 Medicine Loading Guide'
        '</div>',
        unsafe_allow_html=True
    )

    st.info(
        "View the dispenser from above. Align Slot 1 with the "
        "dispensing opening. Because the motor rotates "
        "counterclockwise, the slot numbers increase clockwise."
    )

    slot_medicines = get_slot_medicines(schedules)

    dispenser_svg = create_dispenser_svg(
        slot_medicines
    )

    st.markdown(
        dispenser_svg,
        unsafe_allow_html=True
    )

    # Check for multiple medicines assigned to one slot.
    conflicting_slots = {
        slot: medicines
        for slot, medicines in slot_medicines.items()
        if len(medicines) > 1
    }

    if conflicting_slots:
        st.error(
            "Some slots have more than one medicine assigned. "
            "Place only one medicine type in each slot."
        )

        for slot, medicines in conflicting_slots.items():
            st.write(
                f"**Slot {slot}:** "
                + ", ".join(sorted(medicines))
            )

    # Exact loading list
    st.markdown("#### Exact Slot Arrangement")

    loading_list_found = False

    for slot_number in range(1, 16):
        medicine_names = slot_medicines[
            slot_number
        ]

        if medicine_names:
            loading_list_found = True

            st.write(
                f"**Slot {slot_number}:** "
                + ", ".join(sorted(medicine_names))
            )

    if not loading_list_found:
        st.warning(
            "There are no current or future medicines to load."
        )

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
    # Determine selected schedules using checkbox states.
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
    # DELETE CHECKED BUTTON
    # ----------------------------------------------
    count_column, delete_column = st.columns([3, 1.35])

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
    # DELETE SELECTED RECORDS
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

        # Clear deleted checkbox states.
        for schedule_id in selected_ids:
            checkbox_key = (
                f"select_schedule_{schedule_id}"
            )

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

        medicine = str(
            schedule.get(
                "medicine_name",
                "Unnamed medicine"
            )
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

        with checkbox_column:
            st.checkbox(
                "Select",
                key=f"select_schedule_{schedule_id}",
                label_visibility="collapsed",
                help=f"Select {medicine}"
            )

        with information_column:
            # Escape database text before placing it in HTML.
            safe_medicine = escape(medicine)
            safe_slot = escape(str(slot))

            card_html = (
                '<div class="schedule-card">'
                '<div class="schedule-time">'
                f'⏰ {format_time(scheduled_time)}'
                '</div>'
                '<div class="medicine-name">'
                f'💊 {safe_medicine}'
                '</div>'
                '<div class="schedule-detail">'
                f'📅 {format_date(scheduled_date)}'
                f' &nbsp;|&nbsp; Slot {safe_slot}'
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
    "slot number, dates, and dispensing times."
)