import math
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
from uuid import uuid4

import streamlit as st
from supabase import Client, create_client


st.set_page_config(
    page_title="Smart Pill Dispenser",
    page_icon="💊",
    layout="centered",
)


st.markdown(
    """
    <style>
    .stApp { background-color: #f4f8fb; }
    .block-container { max-width: 980px; padding-top: 2rem; padding-bottom: 3rem; }
    .app-header { text-align: center; margin-bottom: 1.5rem; }
    .app-title { color: #12304a; font-size: 2.3rem; font-weight: 800; }
    .app-subtitle { color: #536b7c; font-size: 1.15rem; }
    .section-heading { color: #12304a; font-size: 1.65rem; font-weight: 800; margin: 1rem 0; }
    .table-header { color: #36566e; font-size: .92rem; font-weight: 800; }
    .medicine-cell { color: #16856f; font-size: 1.05rem; font-weight: 800; }
    .row-text { color: #36566e; font-size: .98rem; line-height: 1.45; }
    .empty-schedule {
        background-color: #fff8e6; border: 1px solid #f0d78c;
        border-radius: 14px; padding: 1.3rem; text-align: center;
        color: #614d18; font-size: 1.1rem;
    }
    div[data-testid="stButton"] button {
        border-radius: 9px; font-size: .95rem; font-weight: 700;
    }
    div[data-testid="stTextInput"] label,
    div[data-testid="stDateInput"] label,
    div[data-testid="stMultiSelect"] label {
        color: #12304a; font-size: 1.02rem; font-weight: 700;
    }
    @media (max-width: 700px) {
        .app-title { font-size: 1.8rem; }
        .table-header { font-size: .78rem; }
        .row-text, .medicine-cell { font-size: .86rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def initialize_supabase() -> Client:
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_ANON_KEY"],
    )


supabase = initialize_supabase()


# -----------------------------------------------------------------------------
# Formatting and database helpers
# -----------------------------------------------------------------------------
def normalize_time(value):
    if not value:
        return ""
    return str(value).split("+")[0][:5]


def format_time(value):
    try:
        parsed = datetime.strptime(normalize_time(value), "%H:%M")
        return parsed.strftime("%I:%M %p").lstrip("0")
    except (TypeError, ValueError):
        return str(value or "Time not provided")


def format_date(value):
    try:
        parsed = datetime.strptime(str(value), "%Y-%m-%d")
        return parsed.strftime("%b. %d, %Y")
    except (TypeError, ValueError):
        return str(value or "Date not provided")


def format_date_range(start_value, end_value):
    if str(start_value) == str(end_value):
        return format_date(start_value)
    return f"{format_date(start_value)} – {format_date(end_value)}"


def date_range(start_date, end_date):
    days = (end_date - start_date).days
    return [start_date + timedelta(days=offset) for offset in range(days + 1)]


def event_key(dispense_date, dispense_time):
    return str(dispense_date), normalize_time(dispense_time)


def get_schedules():
    response = (
        supabase.table("medicines")
        .select("*")
        .order("dispense_date")
        .order("dispense_time")
        .execute()
    )
    return response.data or []


def get_future_schedules():
    response = (
        supabase.table("medicines")
        .select("*")
        .gte("dispense_date", str(date.today()))
        .order("dispense_date")
        .order("dispense_time")
        .execute()
    )
    return response.data or []


def record_group_key(record):
    group_id = record.get("schedule_group_id")
    if group_id:
        return f"group:{group_id}"
    return f"legacy:{record.get('id')}"


def group_schedules(records):
    """Turn generated daily records back into one display row per medicine plan."""
    grouped = {}

    for record in records:
        key = record_group_key(record)
        group = grouped.setdefault(
            key,
            {
                "key": key,
                "group_id": record.get("schedule_group_id"),
                "record_ids": [],
                "medicine_name": str(record.get("medicine_name", "Unnamed medicine")),
                "dates": set(),
                "times": set(),
            },
        )
        group["record_ids"].append(record.get("id"))
        group["dates"].add(str(record.get("dispense_date", "")))
        group["times"].add(normalize_time(record.get("dispense_time")))

    plans = []
    for group in grouped.values():
        dates = sorted(value for value in group["dates"] if value)
        times = sorted(value for value in group["times"] if value)
        if dates:
            group["start_date"] = dates[0]
            group["end_date"] = dates[-1]
        else:
            group["start_date"] = ""
            group["end_date"] = ""
        group["times"] = times
        plans.append(group)

    return sorted(
        plans,
        key=lambda item: (
            item["start_date"],
            item["times"][0] if item["times"] else "",
            item["medicine_name"].casefold(),
        ),
    )


def delete_plan(plan):
    """Delete all generated records belonging to one displayed medicine row."""
    if plan.get("group_id"):
        (
            supabase.table("medicines")
            .delete()
            .eq("schedule_group_id", plan["group_id"])
            .execute()
        )
        verification = (
            supabase.table("medicines")
            .select("id")
            .eq("schedule_group_id", plan["group_id"])
            .execute()
        )
    else:
        record_id = plan["record_ids"][0]
        (
            supabase.table("medicines")
            .delete()
            .eq("id", record_id)
            .execute()
        )
        verification = (
            supabase.table("medicines")
            .select("id")
            .eq("id", record_id)
            .execute()
        )

    if verification.data:
        raise PermissionError("Supabase blocked the deletion. Check the DELETE policy.")


def reassign_future_slots():
    schedules = get_future_schedules()
    events = sorted(
        {
            event_key(item.get("dispense_date"), item.get("dispense_time"))
            for item in schedules
        }
    )
    if len(events) > 15:
        raise ValueError(
            f"The dispenser has 15 slots, but {len(events)} dispensing events exist."
        )

    assignments = {item: index for index, item in enumerate(events, start=1)}
    for schedule in schedules:
        assigned_slot = assignments[
            event_key(schedule.get("dispense_date"), schedule.get("dispense_time"))
        ]
        if int(schedule.get("slot_number") or 0) != assigned_slot:
            (
                supabase.table("medicines")
                .update({"slot_number": assigned_slot})
                .eq("id", schedule.get("id"))
                .execute()
            )


def plan_matches_excluded_group(record, excluded_plan):
    if not excluded_plan:
        return False
    if excluded_plan.get("group_id"):
        return str(record.get("schedule_group_id")) == str(excluded_plan["group_id"])
    return record.get("id") in excluded_plan.get("record_ids", [])


def save_plans(start_date, end_date, medicine_entries, editing_plan=None):
    """
    Save one group per medicine. When editing, safely replace the selected group.
    Medicines due at the same date and time share one physical slot.
    """
    future_records = get_future_schedules()
    retained_records = [
        record
        for record in future_records
        if not plan_matches_excluded_group(record, editing_plan)
    ]

    existing_keys = {
        (
            str(record.get("medicine_name", "")).strip().casefold(),
            str(record.get("dispense_date", "")),
            normalize_time(record.get("dispense_time")),
        )
        for record in retained_records
    }
    retained_events = {
        event_key(record.get("dispense_date"), record.get("dispense_time"))
        for record in retained_records
    }

    candidate_records = []
    candidate_keys = set()
    candidate_events = set()
    skipped = 0
    new_group_ids = []

    for entry in medicine_entries:
        group_id = str(uuid4())
        new_group_ids.append(group_id)
        for scheduled_date in date_range(start_date, end_date):
            for scheduled_time in entry["times"]:
                key = (
                    entry["medicine"].casefold(),
                    str(scheduled_date),
                    scheduled_time,
                )
                if key in existing_keys or key in candidate_keys:
                    skipped += 1
                    continue
                candidate_keys.add(key)
                candidate_events.add(event_key(scheduled_date, scheduled_time))
                candidate_records.append(
                    {
                        "schedule_group_id": group_id,
                        "medicine_name": entry["medicine"],
                        "dispense_date": str(scheduled_date),
                        "dispense_time": scheduled_time,
                    }
                )

    all_events = sorted(retained_events | candidate_events)
    if len(all_events) > 15:
        raise ValueError(
            f"This plan needs {len(all_events)} dispensing slots, but only 15 are available. "
            "Reduce the date range or the number of different dispensing times."
        )

    if not candidate_records:
        return 0, skipped

    assignments = {item: index for index, item in enumerate(all_events, start=1)}
    for record in candidate_records:
        record["slot_number"] = assignments[
            event_key(record["dispense_date"], record["dispense_time"])
        ]

    # Insert the replacement first. If insertion fails, the old plan remains intact.
    supabase.table("medicines").insert(candidate_records).execute()

    if editing_plan:
        try:
            delete_plan(editing_plan)
        except Exception:
            # Roll back the newly inserted replacement when the old plan cannot be removed.
            for group_id in new_group_ids:
                (
                    supabase.table("medicines")
                    .delete()
                    .eq("schedule_group_id", group_id)
                    .execute()
                )
            raise

    reassign_future_slots()
    return len(candidate_records), skipped


# -----------------------------------------------------------------------------
# Circular loading guide
# -----------------------------------------------------------------------------
def get_slot_medicines(schedules):
    slots = {slot: set() for slot in range(1, 16)}
    today_text = str(date.today())
    for schedule in schedules:
        if str(schedule.get("dispense_date", "")) < today_text:
            continue
        try:
            slot = int(schedule.get("slot_number", 0))
        except (TypeError, ValueError):
            continue
        medicine = str(schedule.get("medicine_name", "")).strip()
        if 1 <= slot <= 15 and medicine:
            slots[slot].add(medicine)
    return slots


def short_slot_label(names):
    if not names:
        return "EMPTY"
    if len(names) > 1:
        return f"{len(names)} MEDS"
    name = next(iter(names))
    return name if len(name) <= 13 else name[:11] + "…"


def create_dispenser_svg(slot_medicines):
    width, height = 700, 720
    center_x, center_y, radius, label_radius = 350, 330, 265, 185
    slot_angle = 360 / 15
    colors = ["#B8E8E0", "#A8DADC", "#BDE0FE", "#CDE7FF", "#D7E3FC"]
    svg = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        'style="width:100%;max-width:700px;height:auto">'
    ]

    for slot in range(1, 16):
        middle = 90 + (slot - 1) * slot_angle
        start = math.radians(middle - slot_angle / 2)
        end = math.radians(middle + slot_angle / 2)
        label = math.radians(middle)
        x1, y1 = center_x + radius * math.cos(start), center_y + radius * math.sin(start)
        x2, y2 = center_x + radius * math.cos(end), center_y + radius * math.sin(end)
        lx = center_x + label_radius * math.cos(label)
        ly = center_y + label_radius * math.sin(label)
        names = slot_medicines.get(slot, set())
        fill = colors[(slot - 1) % len(colors)] if names else "#EEF3F6"
        text = escape(short_slot_label(names))
        path = (
            f"M {center_x} {center_y} L {x1:.2f} {y1:.2f} "
            f"A {radius} {radius} 0 0 1 {x2:.2f} {y2:.2f} Z"
        )
        svg.append(f'<path d="{path}" fill="{fill}" stroke="#fff" stroke-width="4"/>')
        svg.append(
            f'<text x="{lx:.2f}" y="{ly - 7:.2f}" text-anchor="middle" '
            f'font-family="Arial" font-size="18" font-weight="800" fill="#12304A">{slot}</text>'
        )
        svg.append(
            f'<text x="{lx:.2f}" y="{ly + 13:.2f}" text-anchor="middle" '
            f'font-family="Arial" font-size="10" font-weight="700" fill="#36566E">{text}</text>'
        )

    svg.extend(
        [
            f'<circle cx="{center_x}" cy="{center_y}" r="82" fill="#12304A" stroke="#fff" stroke-width="5"/>',
            f'<text x="{center_x}" y="{center_y - 7}" text-anchor="middle" font-family="Arial" '
            'font-size="45" font-weight="800" fill="#fff">↺</text>',
            f'<text x="{center_x}" y="{center_y + 24}" text-anchor="middle" font-family="Arial" '
            'font-size="12" font-weight="700" fill="#fff">COUNTERCLOCKWISE</text>',
            f'<path d="M {center_x - 24} 610 L {center_x} 635 L {center_x + 24} 610 Z" fill="#FF6B5F"/>',
            f'<text x="{center_x}" y="670" text-anchor="middle" font-family="Arial" '
            'font-size="16" font-weight="800" fill="#12304A">DISPENSING OPENING / HOME</text>',
            f'<text x="{center_x}" y="695" text-anchor="middle" font-family="Arial" '
            'font-size="14" fill="#536B7C">Align Slot 1 with this opening</text>',
            "</svg>",
        ]
    )
    return "".join(svg)


# -----------------------------------------------------------------------------
# Form state helpers
# -----------------------------------------------------------------------------
def clear_form_widget_state():
    prefixes = ("plan_medicine_", "plan_times_")
    for key in list(st.session_state.keys()):
        if key.startswith(prefixes) or key in {"plan_start_date", "plan_end_date"}:
            del st.session_state[key]


if "show_schedule_form" not in st.session_state:
    st.session_state.show_schedule_form = False
if "medicine_rows" not in st.session_state:
    st.session_state.medicine_rows = [0]
if "next_medicine_row_id" not in st.session_state:
    st.session_state.next_medicine_row_id = 1
if "editing_plan" not in st.session_state:
    st.session_state.editing_plan = None
if "pending_edit_plan" not in st.session_state:
    st.session_state.pending_edit_plan = None
if "pending_delete_plan" not in st.session_state:
    st.session_state.pending_delete_plan = None


if st.session_state.pop("reset_form_pending", False):
    clear_form_widget_state()
    st.session_state.medicine_rows = [0]
    st.session_state.next_medicine_row_id = 1
    st.session_state.editing_plan = None


pending_edit = st.session_state.pending_edit_plan
if pending_edit:
    clear_form_widget_state()
    st.session_state.medicine_rows = [0]
    st.session_state.next_medicine_row_id = 1
    st.session_state.editing_plan = pending_edit
    st.session_state.plan_start_date = datetime.strptime(
        pending_edit["start_date"], "%Y-%m-%d"
    ).date()
    st.session_state.plan_end_date = datetime.strptime(
        pending_edit["end_date"], "%Y-%m-%d"
    ).date()
    st.session_state.plan_medicine_0 = pending_edit["medicine_name"]
    st.session_state.plan_times_0 = pending_edit["times"]
    st.session_state.show_schedule_form = True
    st.session_state.pending_edit_plan = None


# -----------------------------------------------------------------------------
# Header
# -----------------------------------------------------------------------------
logo_path = Path("pill_dispenser_logo.png")
if logo_path.exists():
    _, logo_column, _ = st.columns([1, 1.1, 1])
    with logo_column:
        st.image(str(logo_path), use_container_width=True)
else:
    st.markdown("<div style='text-align:center;font-size:5rem'>💊</div>", unsafe_allow_html=True)

st.markdown(
    """
    <div class="app-header">
        <div class="app-title">Smart Pill Dispenser</div>
        <div class="app-subtitle">Schedule medicines safely and easily.</div>
    </div>
    """,
    unsafe_allow_html=True,
)


time_options = [
    f"{hour:02d}:{minute:02d}"
    for hour in range(24)
    for minute in range(0, 60, 5)
]


# -----------------------------------------------------------------------------
# Hidden add/edit form
# -----------------------------------------------------------------------------
if not st.session_state.show_schedule_form:
    add_column, _ = st.columns([1.7, 3])
    with add_column:
        if st.button("➕ Add Medicine Schedule", type="primary", use_container_width=True):
            st.session_state.reset_form_pending = True
            st.session_state.show_schedule_form = True
            st.rerun()


if st.session_state.show_schedule_form:
    editing = st.session_state.editing_plan
    title = "✏️ Edit Medicine Schedule" if editing else "➕ Add Medicine Schedule"
    st.markdown(f'<div class="section-heading">{title}</div>', unsafe_allow_html=True)

    if "plan_start_date" not in st.session_state:
        st.session_state.plan_start_date = date.today()
    if "plan_end_date" not in st.session_state:
        st.session_state.plan_end_date = st.session_state.plan_start_date

    minimum_form_date = min(date.today(), st.session_state.plan_start_date)

    from_column, to_column = st.columns(2)
    with from_column:
        start_date = st.date_input(
            "From",
            min_value=minimum_form_date,
            key="plan_start_date",
        )
    with to_column:
        if st.session_state.plan_end_date < start_date:
            st.session_state.plan_end_date = start_date
        end_date = st.date_input(
            "To",
            min_value=start_date,
            key="plan_end_date",
        )

    for row_number, row_id in enumerate(st.session_state.medicine_rows, start=1):
        with st.container(border=True):
            heading_column, remove_column = st.columns([4, 1])
            with heading_column:
                st.markdown(f"**Medicine {row_number}**")
            with remove_column:
                if not editing and len(st.session_state.medicine_rows) > 1:
                    if st.button("✕", key=f"remove_row_{row_id}", help="Remove medicine"):
                        st.session_state.medicine_rows.remove(row_id)
                        st.rerun()

            st.text_input(
                "Medicine Name",
                placeholder="Example: Paracetamol",
                key=f"plan_medicine_{row_id}",
            )
            st.multiselect(
                "Dispensing Times",
                options=time_options,
                default=["08:00"],
                format_func=format_time,
                key=f"plan_times_{row_id}",
                help="Select one or more times.",
            )

    if not editing:
        add_row_column, _ = st.columns([1.6, 3])
        with add_row_column:
            if st.button("➕ Add Another Medicine", use_container_width=True):
                row_id = st.session_state.next_medicine_row_id
                st.session_state.medicine_rows.append(row_id)
                st.session_state.next_medicine_row_id += 1
                st.rerun()

    save_column, cancel_column = st.columns(2)
    with save_column:
        save_clicked = st.button(
            "💾 Save Changes" if editing else "💾 Save Schedules",
            type="primary",
            use_container_width=True,
        )
    with cancel_column:
        if st.button("Cancel", use_container_width=True):
            st.session_state.show_schedule_form = False
            st.session_state.reset_form_pending = True
            st.rerun()

    if save_clicked:
        entries, errors = [], []
        for number, row_id in enumerate(st.session_state.medicine_rows, start=1):
            name = st.session_state.get(f"plan_medicine_{row_id}", "").strip()
            times = sorted(st.session_state.get(f"plan_times_{row_id}", []))
            if not name:
                errors.append(f"Enter the name of Medicine {number}.")
            if not times:
                errors.append(f"Select at least one time for Medicine {number}.")
            if name and times:
                entries.append({"medicine": name, "times": times})

        if end_date < start_date:
            errors.append("The ending date cannot be earlier than the starting date.")

        if errors:
            for message in errors:
                st.error(message)
        else:
            try:
                saved, skipped = save_plans(start_date, end_date, entries, editing)
                if saved:
                    st.success("The medicine schedule was updated." if editing else "Medicine schedules saved.")
                if skipped:
                    st.warning(f"{skipped} duplicate record(s) were not added.")
                st.session_state.show_schedule_form = False
                st.session_state.reset_form_pending = True
                st.rerun()
            except ValueError as error:
                st.error(str(error))
            except Exception as error:
                st.error("The schedule could not be saved. Check the Supabase connection and policies.")
                st.exception(error)


# -----------------------------------------------------------------------------
# Grouped four-column schedule list
# -----------------------------------------------------------------------------
st.markdown("---")
st.markdown('<div class="section-heading">📅 Medicine Schedules</div>', unsafe_allow_html=True)

try:
    schedules = get_schedules()
    plans = group_schedules(schedules)
except Exception as error:
    schedules, plans = [], []
    st.error("Schedules could not be loaded.")
    st.exception(error)


pending_delete = st.session_state.pending_delete_plan
if pending_delete:
    st.warning(
        f"Delete the complete schedule for **{pending_delete['medicine_name']}**? "
        "All of its displayed dates and times will be removed."
    )
    confirm_column, cancel_column, _ = st.columns([1.2, 1, 3])
    with confirm_column:
        if st.button("Yes, Delete", type="primary", use_container_width=True):
            try:
                delete_plan(pending_delete)
                reassign_future_slots()
                st.session_state.pending_delete_plan = None
                st.rerun()
            except Exception as error:
                st.error("The schedule could not be deleted.")
                st.exception(error)
    with cancel_column:
        if st.button("Cancel Delete", use_container_width=True):
            st.session_state.pending_delete_plan = None
            st.rerun()


if not plans:
    st.markdown(
        '<div class="empty-schedule"><strong>No medicine schedules yet.</strong><br>'
        'Click “Add Medicine Schedule” to create one.</div>',
        unsafe_allow_html=True,
    )
else:
    name_header, dates_header, times_header, actions_header = st.columns([2.4, 2.35, 2.4, 1.15])
    with name_header:
        st.markdown('<div class="table-header">MEDICINE NAME</div>', unsafe_allow_html=True)
    with dates_header:
        st.markdown('<div class="table-header">DATES</div>', unsafe_allow_html=True)
    with times_header:
        st.markdown('<div class="table-header">TIME</div>', unsafe_allow_html=True)
    with actions_header:
        st.markdown('<div class="table-header">ACTIONS</div>', unsafe_allow_html=True)
    st.markdown("---")

    for index, plan in enumerate(plans):
        name_column, dates_column, times_column, actions_column = st.columns([2.4, 2.35, 2.4, 1.15])
        with name_column:
            st.markdown(
                f'<div class="medicine-cell">💊 {escape(plan["medicine_name"])}</div>',
                unsafe_allow_html=True,
            )
        with dates_column:
            st.markdown(
                f'<div class="row-text">{escape(format_date_range(plan["start_date"], plan["end_date"]))}</div>',
                unsafe_allow_html=True,
            )
        with times_column:
            time_text = ", ".join(format_time(value) for value in plan["times"])
            st.markdown(f'<div class="row-text">{escape(time_text)}</div>', unsafe_allow_html=True)
        with actions_column:
            edit_column, delete_column = st.columns(2)
            with edit_column:
                if st.button(
                    "✏️",
                    key=f"edit_plan_{index}_{plan['key']}",
                    help="Edit this schedule",
                    disabled=st.session_state.show_schedule_form,
                ):
                    st.session_state.pending_edit_plan = plan
                    st.rerun()
            with delete_column:
                if st.button(
                    "🗑️",
                    key=f"delete_plan_{index}_{plan['key']}",
                    help="Delete this schedule",
                    disabled=st.session_state.show_schedule_form,
                ):
                    st.session_state.pending_delete_plan = plan
                    st.rerun()
        st.markdown("---")


# -----------------------------------------------------------------------------
# Loading guide
# -----------------------------------------------------------------------------
future_schedules = [
    item for item in schedules if str(item.get("dispense_date", "")) >= str(date.today())
]
if future_schedules:
    st.markdown('<div class="section-heading">🍕 Medicine Loading Guide</div>', unsafe_allow_html=True)
    st.info(
        "View the dispenser from above. Align Slot 1 with the dispensing opening. "
        "Because the motor rotates counterclockwise, slot numbers increase clockwise. "
        "Medicines due together are placed together in the same slot."
    )
    slot_medicines = get_slot_medicines(future_schedules)
    st.markdown(create_dispenser_svg(slot_medicines), unsafe_allow_html=True)
    st.markdown("#### Exact Slot Arrangement")
    for slot in range(1, 16):
        names = slot_medicines[slot]
        if names:
            st.write(f"**Slot {slot}:** " + " + ".join(sorted(names)))


st.markdown("---")
st.caption(
    "Verify all medicines, dates, times, and loading positions before filling the dispenser."
)
