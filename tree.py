import streamlit as st
from pyvis.network import Network
import streamlit.components.v1 as components
import json
import os
import uuid
from datetime import date
import base64
from io import BytesIO

st.set_page_config(layout="wide")
st.title("My Stylized Family Tree 🌳")

# --- Configuration for data file ---
DATA_FILE = "family_data.json"

# Default Avatar URLs for male and female
DEFAULT_MALE_AVATAR_URL = "https://cdn-icons-png.flaticon.com/512/147/147142.png"
DEFAULT_FEMALE_AVATAR_URL = "https://cdn-icons-png.flaticon.com/512/147/147137.png"
DEFAULT_NONBINARY_AVATAR_URL = "https://cdn-icons-png.flaticon.com/512/1659/1659727.png" # A neutral avatar icon


# --- Functions to load and save data ---
def load_family_data():
    if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 0:
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            st.error("Error decoding family data from JSON file. File might be corrupted or empty.")
            return {}
    return {}

def save_family_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# --- Generation Level Calculation Function ---
def calculate_generation_levels(family_data):
    if not family_data:
        return family_data

    for person_id in family_data:
        family_data[person_id]['level'] = None

    queue = []
    base_level = 2

    initial_roots = [
        pid for pid, data in family_data.items()
        if not data.get('parents') or all(p not in family_data for p in data.get('parents', []))
    ]

    for root_id in initial_roots:
        if family_data[root_id]['level'] is None:
            family_data[root_id]['level'] = base_level
            queue.append(root_id)

    while queue:
        current_id = queue.pop(0)
        current_level = family_data[current_id]['level']

        for child_id in family_data[current_id].get('children', []):
            if child_id in family_data:
                if family_data[child_id]['level'] is None:
                    family_data[child_id]['level'] = current_level + 1
                    queue.append(child_id)
                else:
                    family_data[child_id]['level'] = min(family_data[child_id]['level'], current_level + 1)

        for parent_id in family_data[current_id].get('parents', []):
            if parent_id in family_data:
                if family_data[parent_id]['level'] is None:
                    family_data[parent_id]['level'] = current_level - 1
                    queue.append(parent_id)
                else:
                    family_data[parent_id]['level'] = max(family_data[parent_id]['level'], current_level - 1)

    for person_id, data in family_data.items():
        if data['level'] is None:
            family_data[person_id]['level'] = base_level

    min_level = min(data['level'] for data in family_data.values()) if family_data else 0
    for person_id in family_data:
        family_data[person_id]['level'] -= min_level

    return family_data

# --- Initialize Session State ---
if 'family_data' not in st.session_state:
    st.session_state.family_data = load_family_data()
    st.session_state.family_data = calculate_generation_levels(st.session_state.family_data)

# State for the form fields, updated via callback
if 'form_person_data' not in st.session_state:
    st.session_state.form_person_data = {}
if 'edit_mode_selected_id' not in st.session_state:
    st.session_state.edit_mode_selected_id = ""
if 'avatar_choice_radio_value' not in st.session_state:
    st.session_state.avatar_choice_radio_value = "Use Default (based on gender)"

# --- Helper for displaying names ---
def get_full_name(person_data):
    first = person_data.get('given_name', '')
    last = person_data.get('family_name', '')
    maiden = person_data.get('maiden_name', '')
    nickname = person_data.get('nickname', '')
    other = person_data.get('other_names', '')

    full_name_parts = []
    if first:
        full_name_parts.append(first)
    if other:
        full_name_parts.append(other)
    if maiden:
        full_name_parts.append(f"({maiden})")
    if last:
        full_name_parts.append(last)

    display_name = " ".join(full_name_parts).strip()
    if nickname:
        display_name += f' "{nickname}"'

    return display_name if display_name else "Unknown Name"

# --- Callback to update form_person_data when edit selection changes ---
# This function is now designed to be called by a selectbox OUTSIDE the form.
def update_form_on_edit_select():
    selected_id = st.session_state.edit_person_select_global
    st.session_state.edit_mode_selected_id = selected_id
    if selected_id and selected_id in st.session_state.family_data:
        person_data = st.session_state.family_data[selected_id]
        st.session_state.form_person_data = {
            'given_name': person_data.get('given_name', ''),
            'family_name': person_data.get('family_name', ''),
            'maiden_name': person_data.get('maiden_name', ''),
            'other_names': person_data.get('other_names', ''),
            'nickname': person_data.get('nickname', ''),
            'gender': person_data.get('gender', 'Male'),
            'dob': date.fromisoformat(person_data['dob']) if person_data.get('dob') else None,
            'dod': date.fromisoformat(person_data['dod']) if person_data.get('dod') else None,
            'married_to': person_data.get('married_to', ''),
            'divorced_from': person_data.get('divorced_from', ''),
            'parents': person_data.get('parents', []),
            'children': person_data.get('children', []),
            'avatar_url': person_data.get('avatar_url', '')
        }

        current_avatar_data = st.session_state.form_person_data['avatar_url']
        if not current_avatar_data:
            st.session_state.avatar_choice_radio_value = "Use Default (based on gender)"
        elif current_avatar_data.startswith("http"):
            st.session_state.avatar_choice_radio_value = "Provide Image URL"
        elif current_avatar_data.startswith("data:image"):
            st.session_state.avatar_choice_radio_value = "Upload Image File"
    else:
        # Reset form data if no person is selected or if selection is cleared
        st.session_state.form_person_data = {
            'given_name': "", 'family_name': "", 'maiden_name': "",
            'other_names': "", 'nickname': "", 'gender': "Male",
            'dob': None, 'dod': None, 'married_to': "",
            'divorced_from': "", 'parents': [], 'children': [],
            'avatar_url': ""
        }
        st.session_state.avatar_choice_radio_value = "Use Default (based on gender)"

# --- Family Tree Visualization ---
st.markdown("<br>", unsafe_allow_html=True)
st.subheader("Family Tree Visualization")

if not st.session_state.family_data:
    st.info("The family tree is currently empty. Use the 'Add New Person' section below to get started!")
else:
    # Adjust width to be slightly less than 100% to avoid scrollbar.
    # Also, ensure 'notebook=True' is set for pyvis to embed correctly.
    net = Network(height="700px", width="99%", bgcolor="#f9f9f9", font_color="black", notebook=True)

    net.set_options("""
    {
      "layout": {
        "hierarchical": {
          "enabled": true,
          "levelSeparation": 150,
          "nodeSpacing": 120,
          "treeSpacing": 220,
          "direction": "UD",
          "sortMethod": "directed"
        }
      },
      "physics": {
        "enabled": false
      },
      "edges": {
        "color": { "inherit": "from" },
        "smooth": { "enabled": true, "type": "cubicBezier", "roundness": 0.6 },
        "arrows": { "to": { "enabled": false } }
      }
    }
    """)

    for person_id, data in st.session_state.family_data.items():
        avatar_src = data.get('avatar_url')
        if not avatar_src:
            if data["gender"] == "Male":
                avatar_src = DEFAULT_MALE_AVATAR_URL
            elif data["gender"] == "Female":
                avatar_src = DEFAULT_FEMALE_AVATAR_URL
            else: # For Gender Non-Binary, Prefer Not to Say, or any other new gender
                avatar_src = DEFAULT_NONBINARY_AVATAR_URL


        display_name_for_node = get_full_name(data)
        married_to_name = get_full_name(st.session_state.family_data[data['married_to']]) if data.get('married_to') and data['married_to'] in st.session_state.family_data else "N/A"
        divorced_from_name = get_full_name(st.session_state.family_data[data['divorced_from']]) if data.get('divorced_from') and data['divorced_from'] in st.session_state.family_data else "N/A"

        tooltip_info = (
            f"Full Name: {get_full_name(data)}\n"
            f"Given Name: {data.get('given_name', 'N/A')}\n"
            f"Family Name: {data.get('family_name', 'N/A')}\n"
            f"Maiden Name: {data.get('maiden_name', 'N/A')}\n"
            f"Other Names: {data.get('other_names', 'N/A')}\n"
            f"Nickname: {data.get('nickname', 'N/A')}\n"
            f"Born: {data.get('dob', 'N/A')}\n"
            f"Died: {data.get('dod', 'N/A')}\n"
            f"Married To: {married_to_name}\n"
            f"Divorced From: {divorced_from_name}"
        )

        net.add_node(
            person_id,
            label=display_name_for_node,
            title=tooltip_info,
            level=data["level"],
            shape='circularImage',
            image=avatar_src,
            size=55,
            font={"size": 14, "color": "#333333"},
            color={
                "border": "#666666",
                "background": "#ffffff",
                "highlight": {"border": "#0057b7", "background": "#cce5ff"},
                "hover": {"border": "#003d80", "background": "#99ccff"}
            },
        )

    for person_id, data in st.session_state.family_data.items():
        for child in data["children"]:
            if child in st.session_state.family_data:
                net.add_edge(person_id, child, color="#999999", width=1.7)

    drawn_spouse_edges = set()
    for person_id, data in st.session_state.family_data.items():
        married_to_id = data.get('married_to')
        if married_to_id and married_to_id in st.session_state.family_data:
            if st.session_state.family_data[married_to_id].get('married_to') == person_id:
                edge_key = tuple(sorted((person_id, married_to_id)))
                if edge_key not in drawn_spouse_edges:
                    net.add_edge(person_id, married_to_id, color="#bbbbbb", dashes=True, width=2)
                    drawn_spouse_edges.add(edge_key)

    try:
        net.save_graph("family_tree.html")
        with st.container():
            st.markdown(
                """
                <div style="border: 2px solid #ddd; border-radius: 10px; padding: 15px; background-color: #ffffff;">
                """
                , unsafe_allow_html=True)
            with open("family_tree.html", "r", encoding="utf-8") as f:
                html_data = f.read()

                # --- Inject CSS to remove body margins/padding within the iframe ---
                # This ensures the vis.js canvas uses the full available space without overflow.
                css_fix = """
                <style>
                    body {
                        margin: 0 !important;
                        padding: 0 !important;
                        overflow: hidden; /* Hide scrollbars if content still slightly overflows */
                    }
                    html {
                        overflow: hidden; /* Hide scrollbars for html as well */
                    }
                </style>
                """
                # Insert the CSS right after the <body> tag or at the end of <head>
                html_data = html_data.replace("</head>", css_fix + "</head>")


                components.html(html_data, height=700, scrolling=False) # Set scrolling to False
            st.markdown("</div>", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error generating graph: {e}")
        st.warning("This might happen if the family data becomes too complex or contains invalid relationships. Try simplifying or checking for circular references.")


st.markdown("<br><hr><br>", unsafe_allow_html=True)

# --- Explore Individual Profiles ---
st.subheader("Explore Individual Profiles")

if not st.session_state.family_data:
    st.info("No profiles to display yet. Add people using the form below.")
else:
    col1, col2 = st.columns([1, 2])

    with col1:
        selected_person_id_display = st.selectbox(
            "Select a person:",
            options=[""] + list(st.session_state.family_data.keys()),
            format_func=lambda x: get_full_name(st.session_state.family_data[x]) if x else "Select a person...",
            key="profile_select"
        )

    with col2:
        if selected_person_id_display:
            p = st.session_state.family_data[selected_person_id_display]
            st.markdown(f"### {get_full_name(p)}")
            st.write(f"**Unique ID:** `{selected_person_id_display}`")
            st.write(f"**Generation Level:** {p.get('level', 'N/A')}")
            st.write(f"**Gender:** {p.get('gender', 'N/A')}")
            st.write(f"**Given Name:** {p.get('given_name', 'N/A')}")
            st.write(f"**Family Name:** {p.get('family_name', 'N/A')}")
            st.write(f"**Maiden Name:** {p.get('maiden_name', 'N/A')}")
            st.write(f"**Other Names:** {p.get('other_names', 'N/A')}")
            st.write(f"**Nickname:** {p.get('nickname', 'N/A')}")

            current_avatar_url = p.get('avatar_url')
            if not current_avatar_url:
                if p["gender"] == "Male":
                    current_avatar_url = DEFAULT_MALE_AVATAR_URL
                elif p["gender"] == "Female":
                    current_avatar_url = DEFAULT_FEMALE_AVATAR_URL
                else:
                    current_avatar_url = DEFAULT_NONBINARY_AVATAR_URL

            st.write("Current Avatar:")
            st.image(current_avatar_url, width=100)

            if p.get('avatar_url'):
                if p['avatar_url'].startswith("data:image"):
                    st.write(f"**Avatar Data (Base64):** (truncated for display) {p['avatar_url'][:100]}...")
                else:
                    st.write(f"**Avatar Data (URL):** {p['avatar_url']}")
            else:
                st.write(f"**Avatar Data:** Using default avatar.")


            st.write(f"**Date of Birth:** {p.get('dob', 'N/A')}")
            st.write(f"**Date of Death:** {p.get('dod', 'N/A')}")

            married_to_id = p.get('married_to')
            if married_to_id and married_to_id in st.session_state.family_data:
                st.write(f"**Married To:** {get_full_name(st.session_state.family_data[married_to_id])}")
            else:
                st.write("**Married To:** N/A")

            divorced_from_id = p.get('divorced_from')
            if divorced_from_id and divorced_from_id in st.session_state.family_data:
                st.write(f"**Divorced From:** {get_full_name(st.session_state.family_data[divorced_from_id])}")
            else:
                st.write("**Divorced From:** N/A")

            if p['parents']:
                parents_names = ", ".join(get_full_name(st.session_state.family_data[p_id]) for p_id in p['parents'] if p_id in st.session_state.family_data)
                st.write(f"**Parents:** {parents_names}")
            else:
                st.write("**Parents:** None listed")

            if p['children']:
                children_names = ", ".join(get_full_name(st.session_state.family_data[c_id]) for c_id in p['children'] if c_id in st.session_state.family_data)
                st.write(f"**Children:** {children_names}")
            else:
                st.write("**Children:** None listed")

st.markdown("<br><hr><br>", unsafe_allow_html=True)

# --- Add New Person / Edit Person ---
st.subheader("Add or Edit Person")

mode = st.radio("Choose mode:", ("Add New Person", "Edit Existing Person"), key="mode_radio")

# Logic to reset form data when switching to "Add New Person" mode
if mode == "Add New Person" and st.session_state.edit_mode_selected_id != "":
    st.session_state.edit_mode_selected_id = ""
    st.session_state.form_person_data = {
        'given_name': "", 'family_name': "", 'maiden_name': "",
        'other_names': "", 'nickname': "", 'gender': "Male",
        'dob': None, 'dod': None, 'married_to': "",
        'divorced_from': "", 'parents': [], 'children': [],
        'avatar_url': ""
    }
    st.session_state.avatar_choice_radio_value = "Use Default (based on gender)"
    st.rerun()

# --- Selectbox for editing moved OUTSIDE the form ---
person_id_to_process = None
if mode == "Edit Existing Person":
    st.markdown("#### Edit Existing Person")
    if not st.session_state.family_data:
        st.warning("No people to edit yet. Add a new person first.")
        st.session_state.edit_mode_selected_id = ""
    else:
        # This selectbox is now outside the st.form and can use on_change
        selected_person_edit_id = st.selectbox(
            "Select person to edit:",
            options=[""] + list(st.session_state.family_data.keys()),
            index=(list(st.session_state.family_data.keys()).index(st.session_state.edit_mode_selected_id) + 1 if st.session_state.edit_mode_selected_id and st.session_state.edit_mode_selected_id in st.session_state.family_data else 0),
            format_func=lambda x: get_full_name(st.session_state.family_data[x]) if x else "Select a person...",
            key="edit_person_select_global", # Changed key for clarity
            on_change=update_form_on_edit_select # on_change is now valid here
        )
        person_id_to_process = st.session_state.edit_mode_selected_id # This will be set by the callback
        if person_id_to_process:
            st.info(f"**Currently Editing ID:** `{person_id_to_process}`")
else: # Add New Person mode
    st.markdown("#### Add New Person")
    person_id_to_process = None


# --- The actual form for data input ---
with st.form("person_form"):
    given_name_val = st.session_state.form_person_data.get('given_name', "")
    family_name_val = st.session_state.form_person_data.get('family_name', "")
    maiden_name_val = st.session_state.form_person_data.get('maiden_name', "")
    other_names_val = st.session_state.form_person_data.get('other_names', "")
    nickname_val = st.session_state.form_person_data.get('nickname', "")
    dob_val = st.session_state.form_person_data.get('dob')
    dod_val = st.session_state.form_person_data.get('dod')
    married_to_val = st.session_state.form_person_data.get('married_to', "")
    divorced_from_val = st.session_state.form_person_data.get('divorced_from', "")
    gender_val = st.session_state.form_person_data.get('gender', "Male")

    # Define all gender options and find the current index
    gender_options = ["Male", "Female", "Gender Non-Binary", "Prefer Not to Say"]
    try:
        gender_idx = gender_options.index(gender_val)
    except ValueError:
        gender_idx = 0 # Default to Male if value is not in options (e.g., old "M"/"F" values)

    initial_parents = st.session_state.form_person_data.get('parents', [])
    initial_children = st.session_state.form_person_data.get('children', [])
    avatar_url_for_input = st.session_state.form_person_data.get('avatar_url', '')

    given_name = st.text_input("Given Name (required):", value=given_name_val, key="given_name_input")
    family_name = st.text_input("Family Name:", value=family_name_val, key="family_name_input")
    maiden_name = st.text_input("Maiden Name (if applicable):", value=maiden_name_val, key="maiden_name_input")
    other_names = st.text_input("Other Names (e.g., middle names):", value=other_names_val, key="other_names_input")
    nickname = st.text_input("Nickname:", value=nickname_val, key="nickname_input")

    st.markdown("---")
    st.markdown("#### Avatar Image Options")

    avatar_choice = st.radio(
        "Choose avatar source:",
        ("Use Default (based on gender)", "Provide Image URL", "Upload Image File"),
        key="avatar_choice_radio",
        index=["Use Default (based on gender)", "Provide Image URL", "Upload Image File"].index(st.session_state.avatar_choice_radio_value)
    )

    final_avatar_data_to_store = None

    if avatar_choice == "Provide Image URL":
        avatar_url = st.text_input(
            "Enter Custom Avatar Image URL:",
            value=avatar_url_for_input if avatar_url_for_input and avatar_url_for_input.startswith("http") else "",
            help="Enter a direct URL to an image file (e.g., .png, .jpg).",
            key="avatar_url_input_manual"
        )
        if avatar_url:
            final_avatar_data_to_store = avatar_url
    elif avatar_choice == "Upload Image File":
        if avatar_url_for_input and avatar_url_for_input.startswith("data:image"):
            st.info("A custom image was previously uploaded for this person.")
            st.image(avatar_url_for_input, caption="Previously uploaded image", width=150)
            final_avatar_data_to_store = avatar_url_for_input

        uploaded_file = st.file_uploader(
            "Upload New Avatar Image File (overwrites previous custom image):",
            type=["png", "jpg", "jpeg"],
            help="Upload a small image file (PNG, JPG). Larger files will increase the size of your family_data.json.",
            key="avatar_file_uploader"
        )
        if uploaded_file is not None:
            st.image(uploaded_file, caption="New Uploaded Image Preview", width=150)
            image_bytes = uploaded_file.getvalue()
            encoded_image = base64.b64encode(image_bytes).decode('utf-8')
            mime_type = f"image/{uploaded_file.type.split('/')[-1]}"
            final_avatar_data_to_store = f"data:{mime_type};base64,{encoded_image}"
            st.success("Image uploaded and ready for storage.")


    gender = st.selectbox("Gender:", gender_options, index=gender_idx, key="gender_select")

    dob = st.date_input(
        "Date of Birth (optional):",
        value=dob_val,
        min_value=date(1700, 1, 1),
        max_value=date.today(),
        key="dob_input"
    )
    dod = st.date_input(
        "Date of Death (optional):",
        value=dod_val,
        min_value=date(1700, 1, 1),
        max_value=date.today(),
        key="dod_input"
    )

    all_person_ids = sorted(list(st.session_state.family_data.keys()))
    available_relationship_options = [pid for pid in all_person_ids if pid != person_id_to_process]
    available_relationship_options_with_none = [""] + available_relationship_options

    married_to = st.selectbox(
        "Married to (select existing person):",
        options=available_relationship_options_with_none,
        index=available_relationship_options_with_none.index(married_to_val) if married_to_val in available_relationship_options_with_none else 0,
        format_func=lambda x: get_full_name(st.session_state.family_data[x]) if x in st.session_state.family_data else "N/A",
        key="married_to_select_form"
    )

    divorced_from = st.selectbox(
        "Divorced from (select existing person):",
        options=available_relationship_options_with_none,
        index=available_relationship_options_with_none.index(divorced_from_val) if divorced_from_val in available_relationship_options_with_none else 0,
        format_func=lambda x: get_full_name(st.session_state.family_data[x]) if x in st.session_state.family_data else "N/A",
        key="divorced_from_select_form"
    )

    parents = st.multiselect("Parents (select existing people):",
                             options=available_relationship_options,
                             default=initial_parents,
                             format_func=lambda x: get_full_name(st.session_state.family_data[x]) if x in st.session_state.family_data else x,
                             key="parents_select_form")
    children = st.multiselect("Children (select existing people):",
                              options=available_relationship_options,
                              default=initial_children,
                              format_func=lambda x: get_full_name(st.session_state.family_data[x]) if x in st.session_state.family_data else x,
                              key="children_select_form")

    submitted = st.form_submit_button("Submit")

    if submitted:
        if mode == "Add New Person":
            if not given_name:
                st.error("Given Name is required to add a new person.")
                st.stop()
            person_id_to_process = str(uuid.uuid4())
        else:
            if not st.session_state.edit_mode_selected_id:
                st.error("Please select a person to edit using the dropdown above the form.")
                st.stop()
            if not given_name:
                st.error("Given Name is required to update a person.")
                st.stop()
            person_id_to_process = st.session_state.edit_mode_selected_id


        old_parents = st.session_state.family_data.get(person_id_to_process, {}).get('parents', [])
        old_children = st.session_state.family_data.get(person_id_to_process, {}).get('children', [])
        old_married_to = st.session_state.family_data.get(person_id_to_process, {}).get('married_to')
        old_divorced_from = st.session_state.family_data.get(person_id_to_process, {}).get('divorced_from')

        new_person_data = {
            "given_name": given_name,
            "family_name": family_name if family_name else None,
            "maiden_name": maiden_name if maiden_name else None,
            "other_names": other_names if other_names else None,
            "nickname": nickname if nickname else None,
            "avatar_url": final_avatar_data_to_store,
            "gender": gender,
            "dob": dob.isoformat() if dob else None,
            "dod": dod.isoformat() if dod else None,
            "married_to": married_to if married_to else None,
            "divorced_from": divorced_from if divorced_from else None,
            "children": children,
            "parents": parents,
            "level": 0
        }

        st.session_state.family_data[person_id_to_process] = new_person_data
        st.success(f"Successfully {'added' if mode == 'Add New Person' else 'updated'} {get_full_name(new_person_data)}!")

        old_parents_set = set(old_parents)
        new_parents_set = set(parents)
        old_children_set = set(old_children)
        new_children_set = set(children)

        for p_id in (old_parents_set - new_parents_set):
            if p_id in st.session_state.family_data and person_id_to_process in st.session_state.family_data[p_id]['children']:
                st.session_state.family_data[p_id]['children'].remove(person_id_to_process)
        for p_id in (new_parents_set - old_parents_set):
            if p_id in st.session_state.family_data and person_id_to_process not in st.session_state.family_data[p_id]['children']:
                st.session_state.family_data[p_id]['children'].append(person_id_to_process)

        for c_id in (old_children_set - new_children_set):
            if c_id in st.session_state.family_data and person_id_to_process in st.session_state.family_data[c_id]['parents']:
                st.session_state.family_data[c_id]['parents'].remove(person_id_to_process)
        for c_id in (new_children_set - old_children_set):
            if c_id in st.session_state.family_data and person_id_to_process not in st.session_state.family_data[c_id]['parents']:
                st.session_state.family_data[c_id]['parents'].append(person_id_to_process)

        if old_married_to and old_married_to in st.session_state.family_data and st.session_state.family_data[old_married_to].get('married_to') == person_id_to_process:
            st.session_state.family_data[old_married_to]['married_to'] = None
        if married_to and married_to in st.session_state.family_data:
            st.session_state.family_data[married_to]['married_to'] = person_id_to_process
            st.session_state.family_data[person_id_to_process]['married_to'] = married_to

        if old_divorced_from and old_divorced_from in st.session_state.family_data and st.session_state.family_data[old_divorced_from].get('divorced_from') == person_id_to_process:
            st.session_state.family_data[old_divorced_from]['divorced_from'] = None
        if divorced_from and divorced_from in st.session_state.family_data:
            st.session_state.family_data[divorced_from]['divorced_from'] = person_id_to_process
            st.session_state.family_data[person_id_to_process]['divorced_from'] = divorced_from

        st.session_state.family_data = calculate_generation_levels(st.session_state.family_data)
        save_family_data(st.session_state.family_data)

        # Reset form after submission
        st.session_state.form_person_data = {
            'given_name': "", 'family_name': "", 'maiden_name': "",
            'other_names': "", 'nickname': "", 'gender': "Male",
            'dob': None, 'dod': None, 'married_to': "",
            'divorced_from': "", 'parents': [], 'children': [],
            'avatar_url': ""
        }
        st.session_state.edit_mode_selected_id = ""
        st.session_state.avatar_choice_radio_value = "Use Default (based on gender)"

        st.rerun()

### **Delete Person Section**

st.markdown("<br><hr><br>", unsafe_allow_html=True)
st.subheader("Delete Person")

if not st.session_state.family_data:
    st.info("No people to delete. The family tree is empty.")
else:
    with st.form("delete_person_form"):
        person_to_delete_id = st.selectbox(
            "Select a person to delete:",
            options=[""] + list(st.session_state.family_data.keys()),
            format_func=lambda x: get_full_name(st.session_state.family_data[x]) if x else "Select a person...",
            key="delete_person_select"
        )

        if person_to_delete_id:
            st.warning(f"You are about to delete **{get_full_name(st.session_state.family_data[person_to_delete_id])}**.")
            st.warning("This action cannot be undone. All relationships to this person will also be removed.")

        delete_confirmed = st.form_submit_button("Confirm Delete")

        if delete_confirmed and person_to_delete_id:
            person_name = get_full_name(st.session_state.family_data[person_to_delete_id])

            # --- Clean up relationships referencing the deleted person ---
            for p_id, p_data in st.session_state.family_data.items():
                if p_id == person_to_delete_id: # Skip the person being deleted itself
                    continue

                # Remove from parents' children list
                if person_to_delete_id in p_data.get('children', []):
                    st.session_state.family_data[p_id]['children'].remove(person_to_delete_id)

                # Remove from children's parents list
                if person_to_delete_id in p_data.get('parents', []):
                    st.session_state.family_data[p_id]['parents'].remove(person_to_delete_id)

                # Remove married_to link
                if p_data.get('married_to') == person_to_delete_id:
                    st.session_state.family_data[p_id]['married_to'] = None

                # Remove divorced_from link
                if p_data.get('divorced_from') == person_to_delete_id:
                    st.session_state.family_data[p_id]['divorced_from'] = None

            # --- Finally, delete the person ---
            del st.session_state.family_data[person_to_delete_id]
            st.success(f"Successfully deleted {person_name}.")

            # --- Recalculate levels and save ---
            st.session_state.family_data = calculate_generation_levels(st.session_state.family_data)
            save_family_data(st.session_state.family_data)

            # Clear form data related to editing if the deleted person was selected for edit
            if st.session_state.edit_mode_selected_id == person_to_delete_id:
                st.session_state.edit_mode_selected_id = ""
                st.session_state.form_person_data = {
                    'given_name': "", 'family_name': "", 'maiden_name': "",
                    'other_names': "", 'nickname': "", 'gender': "Male",
                    'dob': None, 'dod': None, 'married_to': "",
                    'divorced_from': "", 'parents': [], 'children': [],
                    'avatar_url': ""
                }
                st.session_state.avatar_choice_radio_value = "Use Default (based on gender)"

            st.rerun()
        elif delete_confirmed and not person_to_delete_id:
            st.error("Please select a person to delete.")

st.markdown("<br>", unsafe_allow_html=True)

st.info(
    """
    **Notes:**
    - Nodes use circular avatar images.
    - Hover nodes to see detailed tooltip.
    - Edges show parent-child relationships.
    - Dashed edges show spouse relationships.
    - Tree layout is vertical and hierarchical for clarity.
    - All changes made to the family tree are now saved to `family_data.json` and will persist across app restarts.
    - Generation levels are now automatically calculated based on parent/child relationships.
    - New person IDs are automatically generated.
    - Date of Birth, Date of Death, Married To, and Divorced From fields have been added.
    - Name fields are now separated into Given Name, Family Name, Maiden Name, Other Names, and Nickname.
    - Date range for birth/death is expanded to allow older dates.
    - You can now choose a custom Avatar Image by providing a URL or uploading an image file!
        - Uploaded images are converted to a Base64 string and stored in the `family_data.json` file.
        - **Warning:** Uploading large image files will significantly increase the size of your `family_data.json` and can impact app performance. Please use small, optimized images for avatars.
    - **Form fields for editing now update immediately when you select a person from the dropdown, as the selection mechanism has been moved outside the form.**
    - A new 'Delete Person' section has been added to remove individuals from the tree.
        - Deleting a person will also automatically remove all their associated relationships (parent, child, spouse) from other individuals in the tree.
        - A confirmation step is included to prevent accidental deletion.
    - The empty band (horizontal scrollbar) above the visualization should now be removed! This was achieved by:
        - Setting `width="99%"` for the `pyvis.Network`.
        - Setting `scrolling=False` for `st.components.v1.html`.
        - Injecting custom CSS into the generated HTML to remove default `margin` and `padding` from the `body` and `html` tags within the iframe, and setting `overflow: hidden;`.
    - New Gender Options: Added "Gender Non-Binary" and "Prefer Not to Say" options for gender selection, with a neutral default avatar.
    """
)