"""PhoneGenie - AI-Powered Mobile Shopping Assistant."""
import os
import streamlit as st

from src.config import DB_PATH, CSV_PATH
from src.services import resources
from src.tabs import query_tab, comparison_tab
from src.styles import APP_CSS, HEADER_HTML, SIDEBAR_HEADER_HTML, get_filter_section_html
from src.utils.logger import get_logger, log_timing

logger = get_logger(__name__)


# Page configuration
st.set_page_config(
    page_title="📱 PhoneGenie - Smart Mobile Assistant",
    page_icon="📱",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Auto-initialize database if it doesn't exist (first-time setup)
if not os.path.exists(DB_PATH):
    logger.info("Database not found, initializing from CSV")
    if os.path.exists(CSV_PATH):
        with st.spinner("🔄 Initializing database (first time setup)..."):
            try:
                with log_timing("Database initialization"):
                    resources.db.create_from_csv()
                logger.info("Database initialized successfully")
                st.success("✅ Database initialized successfully!")
                st.rerun()
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}", exc_info=True)
                st.error(f"❌ Failed to initialize database: {e}")
                st.stop()
    else:
        logger.error(f"CSV file not found at {CSV_PATH}")
        st.error(f"❌ CSV file not found at {CSV_PATH}. Please ensure the data file exists.")
        st.stop()
else:
    logger.debug("Database already exists")

# Apply custom CSS
st.markdown(APP_CSS, unsafe_allow_html=True)
st.markdown(HEADER_HTML, unsafe_allow_html=True)

# Get metadata from database
logger.debug("Loading metadata from database")
with log_timing("Load metadata"):
    db = resources.db
    price_min_range, price_max_range = db.get_price_range()
    camera_min_range, camera_max_range = db.get_camera_range()
    battery_min_range, battery_max_range = db.get_battery_range()
    companies = db.get_companies()
    logger.info(f"Loaded metadata: {len(companies)} companies, "
               f"price range: {price_min_range}-{price_max_range}, "
               f"camera range: {camera_min_range}-{camera_max_range}, "
               f"battery range: {battery_min_range}-{battery_max_range}")

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
        logger.info("Resetting all filters")
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

logger.debug(f"Active filters: {filters}")

# Render tabs
logger.debug("Rendering application tabs")
tab1, tab2 = st.tabs(["💬 AI Chat Assistant", "⚖️ Phone Comparison"])

with tab1:
    query_tab.render(filters)

with tab2:
    comparison_tab.render(filters)
