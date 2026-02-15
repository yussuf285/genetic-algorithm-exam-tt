import pandas as pd
from utils import *


st.set_page_config(page_title="Exam Timetable Generator",
                   page_icon="\U0001F4D8",
                   layout="wide")

# -------------------- HEADER ----------------
st.markdown(f"""
<img src="data:image/jpeg;base64,{open_picture('Yabatech.jpg')}" width="10%"><br>
""", unsafe_allow_html=True)

st.title("\U0001F4D8 Exam Timetable Generator")

# ----------- SIDEBAR ---------------
st.sidebar.header("📂 Departments")

# initialize session state and store departments in upload
if "departments" not in st.session_state:
    st.session_state.departments = []  # list of dicts: {name, file}

# Button to add department
if st.sidebar.button("➕ Add Department"):
    st.session_state.departments.append({
        "name": f"Dept {len(st.session_state.departments) + 1}",
        "file": None
    })

all_dept_files = []
# Render department inputs
for i, dept in enumerate(st.session_state.departments):
    st.sidebar.markdown(f"**Department {i + 1}**")
    dept_name = st.sidebar.text_input(
        f"Department Name {i+1}",
        value=dept["name"],
        key=f"dept_name_{i}"
    )

    dept_file = st.sidebar.file_uploader(
        f"Upload {dept_name} CSV",
        type="csv",
        key=f"dept_file_{i}"
    )

    st.session_state.departments[i]["name"] = dept_name
    st.session_state.departments[i]["file"] = dept_file

    if dept_file:
        all_dept_files.append(dept_file)

    # st.sidebar.divider()

# carryover + venues
st.sidebar.header("📦 Other Uploads")

# upload carryover course
co_file = st.sidebar.file_uploader("Upload Carryover Courses CSV", type="csv")

# Upload venue csv data
venue_file = st.sidebar.file_uploader("Upload Venue Lists CSV", type="csv")

weeks = st.sidebar.number_input("Number of exam weeks (Mon–Fri)", min_value=1, max_value=5, step=1, value=1)

# Selects number of venues
venues = st.sidebar.number_input("How many venues for the exam", min_value=1, max_value=10, step=1, value=2)

generate_btn = st.sidebar.button("Generate Timetable")

exam_days = weeks * 5

# -- VALIDATION ----------
def all_files_uploaded():
    return (
        len(all_dept_files) > 0
        and co_file
        and venue_file
    )


# -------------------- DISPLAY UPLOADED COURSES --------------------
if all_dept_files:
    st.subheader("📋 Uploaded Courses Overview")
    
    # Create tabs for each department
    dept_names = [dept["name"] for dept in st.session_state.departments if dept["file"]]
    
    if dept_names:
        tabs = st.tabs(dept_names)
        
        for tab, dept in zip(tabs, [d for d in st.session_state.departments if d["file"]]):
            with tab:
                dept_df = pd.read_csv(dept["file"])
                dept["file"].seek(0)  # Reset file pointer for later use
                
                # Create a clean display of courses, levels and units
                if "course" in dept_df.columns and "units" in dept_df.columns:
                    # Include level if available
                    if "level" in dept_df.columns:
                        display_df = dept_df[["course", "level", "units"]].copy()
                        display_df.columns = ["Course Code", "Level", "Units"]
                    else:
                        display_df = dept_df[["course", "units"]].copy()
                        display_df.columns = ["Course Code", "Units"]
                    
                    display_df["Course Code"] = display_df["Course Code"].str.upper()
                    
                    # Display metrics at top
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("📚 Total Courses", len(display_df))
                    with col2:
                        st.metric("📝 Total Units", int(display_df["Units"].sum()))
                    with col3:
                        if "Level" in display_df.columns:
                            st.metric("🎓 Levels", display_df["Level"].nunique())
                    
                    st.markdown("---")
                    
                    # Display the courses table
                    st.dataframe(
                        display_df,
                        use_container_width=True,
                        hide_index=True,
                        height=min(len(display_df) * 35 + 38, 400)
                    )
                else:
                    st.warning(f"⚠️ CSV missing 'course' or 'units' columns")
    
    st.divider()

# -------------------- RUN GA --------------------
# Regenerate timetable if button is pressed
if generate_btn and all_files_uploaded():
    department_dfs = []
    for item in st.session_state.departments:
        if item["file"]:
            df = pd.read_csv(item["file"])
            df["department"] = item["name"]  # enforce consistency
            department_dfs.append(df)

    all_courses_df = pd.concat(department_dfs, ignore_index=True)

    # standardize data
    all_courses_df["units"] = all_courses_df["units"].astype(int)
    all_courses_df["course"] = all_courses_df["course"].str.strip().str.lower()
    all_courses_df["department"] = all_courses_df["department"].str.strip()
    all_courses_df = all_courses_df.reset_index(drop=True)

    all_courses = all_courses_df.to_dict(orient="records")
    course_list = list(range(len(all_courses)))

    # ----- LOAD CARRYOVER ----------
    co_df = pd.read_csv(co_file)

    LEVELS = ["ND1", "ND2", "HND1", "HND2"]
    LEVEL_ORDER = {level: idx for idx, level in enumerate(LEVELS)}

    co_courses = set(co_df[co_df["is_carryover"] == True]["course"].str.strip().str.lower())
    course_levels = {}
    for row in all_courses:
        course = row["course"]
        level = str(row["level"]).strip()

        base_idx = LEVEL_ORDER[level]
        levels = [level]
        if course in co_courses:
            # levels += [i for i in LEVELS if i > level]
            levels += LEVELS[base_idx + 1:]
        course_levels[course] = levels

    # ------- VENUE LOADING -----------
    venues_df = pd.read_csv(venue_file)

    # venue mapping
    venues_list = venues_df.to_dict(orient='records')
    # Use only the number of venues the user selected
    venues_list = venues_list[:venues]  # venues variable from sidebar selectbox
    # quick maps
    venue_capacity = {v['venue_id']: int(v['capacity']) for v in venues_list}
    venue_name = {v['venue_id']: v.get('venue_name', v['venue_id']) for v in venues_list}

    # show chosen venues
    st.sidebar.markdown("**Using venues:**")
    for v in venues_list:
        st.sidebar.markdown(f"- {v.get('venue_name', v['venue_id'])} (ID: {v['venue_id']}, cap: {v['capacity']})")

    # ----UNIQUE TIME SLOTS ----------
    unique_units = sorted(set(row["units"] for row in all_courses))
    slot_cache = {u: get_time_slots(u) for u in unique_units}

    slots = []
    slot_time_cache = {}
    for day in range(1, exam_days + 1):
        for units in unique_units:
            for start, end in slot_cache[units]:
                if start >= "09:00" and end <= "17:45":
                    for venue in venues_list:
                        venue_id = venue["venue_id"]
                        slot = (f"Day {day}", start, end, units, venue_id)
                        slots.append(slot)
                        slot_time_cache[slot] = (time_to_minutes(start), time_to_minutes(end))

    # ---- CONFLICT MAPPING ------
    conflict_map = {i: set() for i in course_list}
    for i in course_list:
        ci = all_courses[i]
        for j in course_list:
            if i == j:
                continue
            cj = all_courses[j]
            if ci["department"] == cj["department"]:
                if not set(course_levels[ci["course"]]).isdisjoint(course_levels[cj["course"]]):
                    conflict_map[i].add(j)

    best = genetic_algorithm(
        generations=200,
        pop_size=30,
        all_courses=all_courses,
        slots=slots,
        slot_time_cache=slot_time_cache,
        course_levels=course_levels,
        conflict_map=conflict_map,
        course_list=course_list,
        venue_capacity=venue_capacity
    )

    timetable = []
    for idx, slot in best.assignments.items():
        row = all_courses[idx]
        venue_id = slot[4]
        timetable.append({
            "Day": slot[0],
            "Start Time": slot[1],
            "End Time": slot[2],
            "Course": row["course"].upper(),
            "Department": row["department"],
            "Level": row["level"],
            "Units": row["units"],
            "Venue ID": venue_id,
            "Venue": venue_name.get(venue_id, venue_id),
            "Venue Capacity": venue_capacity.get(venue_id, None),
            "Enrolled": row.get("enrolled", 0)

        })
    timetable_df = pd.DataFrame(timetable)
    st.session_state["timetable_df"] = timetable_df
    st.session_state["generated"] = True

    # -- DISPLAY -----------------
    pivot_table = timetable_df.copy()
    pivot_table["Slot"] = pivot_table["Start Time"] + "-" + pivot_table["End Time"]
    # pivot_table["Info"] = pivot_table["Course"] + " (" + pivot_table["Department"] + ", Lvl " + pivot_table["Level"].astype(str) + ")"
    pivot_table["Info"] = pivot_table["Course"] + " (" + pivot_table["Department"] + ", " + pivot_table["Level"].astype(str) + ", " + pivot_table["Venue"] + ")"

    pivoted = pivot_table.pivot_table(index="Slot", columns="Day", values="Info", aggfunc=lambda x: '\n'.join(x))

    # Store in session state
    st.session_state["pivoted"] = pivoted
    # st.session_state["departments"] = timetable_df["Department"].unique()
    st.session_state["timetable_departments"] = timetable_df["Department"].unique()
    st.session_state["dept_pivoted"] = {
        dept: timetable_df[timetable_df["Department"] == dept]
        .assign(Slot=lambda df: df["Start Time"] + "-" + df["End Time"])
        # .assign(Info=lambda df: df["Course"] + " (Lvl " + df["Level"].astype(str) + ")")
        .assign(Info=lambda df: df["Course"] + " ( " + df["Level"].astype(str) + ", " + df["Venue"] + ")")
        .pivot_table(index="Slot", columns="Day", values="Info", aggfunc=lambda x: "\n".join(x))
        for dept in timetable_df["Department"].unique()
    }
    st.session_state["summary"] = {
        "total_courses": len(all_courses),
        "total_days": exam_days,
        "unique_slots": len(slots),
        "fitness": best.fitness,
        "hard_conflicts": best.hard_conflicts,
        "soft_conflicts": best.soft_conflicts
    }

# Display timetable if generated
if st.session_state.get("generated", False):
    timetable_df = st.session_state["timetable_df"]
    pivoted = st.session_state["pivoted"]
    departments = st.session_state["timetable_departments"]
    dept_pivoted = st.session_state["dept_pivoted"]
    summary = st.session_state["summary"]

    # Sort days in columns
    pivoted_sort = sort_days(pivoted.columns)
    pivoted = pivoted[pivoted_sort]

    st.subheader("\U0001F4C4 General Timetable for all departments.")
    st.dataframe(pivoted.fillna(""))
    csv = pivoted.to_csv(index=True).encode("utf-8")
    st.download_button("Download General Timetable for all departments", csv, file_name="exam_timetable.csv", mime="text/csv")

    st.subheader("\U0001F4CA Summary Stats")
    st.markdown(f"- Total Courses: **{summary['total_courses']}**")
    st.markdown(f"- Total Days: **{summary['total_days']}**")
    st.markdown(f"- Unique Time Slots: **{summary['unique_slots']}**")
    st.markdown(f"- Final Fitness Score: **{summary['fitness']}**")

    st.markdown("### 🧠 Interpretation")
    if summary["hard_conflicts"] == 0 and summary["soft_conflicts"] == 0:
        st.success("✅ No hard or soft conflicts. Timetable is fully optimized!")
    else:
        st.info(f"""
    - **Hard Conflicts**: {summary['hard_conflicts']} (overlapping exams)
    - **Soft Conflicts**: {summary['soft_conflicts']} (e.g., exams scheduled with <30 mins gap)
    - Timetable is **feasible** and can be improved if needed.
    """)

    st.subheader("📚 Department-Specific Timetables")
    for dept in sorted(departments):
        st.markdown(f"### 🏛️ {dept} Department")
        pivoted_dept = dept_pivoted[dept]
        sorted_cols = sort_days(pivoted_dept.columns)
        pivoted_dept = pivoted_dept[sorted_cols]
        st.dataframe(pivoted_dept.fillna(""))
        csv_dept = pivoted_dept.to_csv(index=True).encode("utf-8")
        st.download_button(
            f"⬇️ Download {dept} Timetable",
            csv_dept,
            file_name=f"{dept.lower().replace(' ', '_')}_timetable.csv",
            mime="text/csv",
        )
else:
    st.info("Upload all required CSVs and click **Generate Timetable** to begin.")


