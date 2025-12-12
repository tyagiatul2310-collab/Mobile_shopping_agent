"""PhoneGenie - AI-Powered Mobile Shopping Assistant."""
import streamlit as st

from src.services import resources
from src.tabs import query_tab, comparison_tab
from src.styles import APP_CSS, HEADER_HTML, SIDEBAR_HEADER_HTML, get_filter_section_html


# Page configuration
st.set_page_config(
    page_title="📱 PhoneGenie - Smart Mobile Assistant",
    page_icon="📱",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Apply custom CSS
st.markdown(APP_CSS, unsafe_allow_html=True)
st.markdown(HEADER_HTML, unsafe_allow_html=True)

# Get metadata from database
db = resources.db
price_min_range, price_max_range = db.get_price_range()
camera_min_range, camera_max_range = db.get_camera_range()
battery_min_range, battery_max_range = db.get_battery_range()
companies = db.get_companies()

# Sidebar filters
with st.sidebar:
    st.markdown(SIDEBAR_HEADER_HTML, unsafe_allow_html=True)
    st.caption("Filters apply to both tabs")

    # Company Filter
    st.markdown(get_filter_section_html("🏢", "Brand"), unsafe_allow_html=True)
    company_filter = st.selectbox(
        "Select Brand",
        [None] + companies,
        format_func=lambda x: "All Brands" if x is None else x.title(),
        key="company_filter",
        label_visibility="collapsed",
    )

    # Price Filter
    st.markdown(get_filter_section_html("💰", "Price Range"), unsafe_allow_html=True)
    price_enabled = st.toggle("Enable Price Filter", key="price_filter_check")
    if price_enabled:
        price_min, price_max = st.slider(
            "Price (INR)",
            min_value=price_min_range,
            max_value=price_max_range,
            value=(price_min_range, price_max_range),
            format="₹%d",
            key="price_slider",
            label_visibility="collapsed",
        )
        st.caption(f"₹{price_min:,} - ₹{price_max:,}")
    else:
        price_min, price_max = None, None

    # Camera Filter
    st.markdown(get_filter_section_html("📷", "Camera"), unsafe_allow_html=True)
    camera_enabled = st.toggle("Enable Camera Filter", key="camera_filter_check")
    if camera_enabled:
        camera_min, camera_max = st.slider(
            "Back Camera (MP)",
            min_value=camera_min_range,
            max_value=camera_max_range,
            value=(camera_min_range, camera_max_range),
            key="camera_slider",
            label_visibility="collapsed",
        )
        st.caption(f"{camera_min} MP - {camera_max} MP")
    else:
        camera_min, camera_max = None, None

    # Battery Filter
    st.markdown(get_filter_section_html("🔋", "Battery"), unsafe_allow_html=True)
    battery_enabled = st.toggle("Enable Battery Filter", key="battery_filter_check")
    if battery_enabled:
        battery_min, battery_max = st.slider(
            "Battery (mAh)",
            min_value=battery_min_range,
            max_value=battery_max_range,
            value=(battery_min_range, battery_max_range),
            key="battery_slider",
            label_visibility="collapsed",
        )
        st.caption(f"{battery_min:,} mAh - {battery_max:,} mAh")
    else:
        battery_min, battery_max = None, None

    st.divider()

    # Reset Button
    if st.button("🔄 Reset All Filters", use_container_width=True):
        st.session_state.company_filter = None
        st.session_state.price_filter_check = False
        st.session_state.camera_filter_check = False
        st.session_state.battery_filter_check = False
        st.rerun()

    # Active Filters Count
    active_filters = sum([
        company_filter is not None,
        price_enabled,
        camera_enabled,
        battery_enabled,
    ])
    if active_filters > 0:
        st.success(f"✅ {active_filters} filter(s) active")

# Collect filters
filters = {
    "company": company_filter,
    "price_min": price_min,
    "price_max": price_max,
    "camera_min": camera_min,
    "camera_max": camera_max,
    "battery_min": battery_min,
    "battery_max": battery_max,
}

# Render tabs
tab1, tab2 = st.tabs(["💬 AI Chat Assistant", "⚖️ Phone Comparison"])

with tab1:
    query_tab.render(filters)

with tab2:
    comparison_tab.render(filters)
