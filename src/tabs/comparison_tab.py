"""Comparison Tab - Phone Comparison UI."""
import streamlit as st
from typing import Dict

from src.services import resources
from src.utils.logger import get_logger, log_timing

logger = get_logger(__name__)


def render(filters: Dict):
    """Render the Phone Comparison tab."""

    # Header
    st.markdown("""
    <div style="background: linear-gradient(135deg, rgba(102,126,234,0.1), rgba(118,75,162,0.1)); 
                padding: 1.2rem; border-radius: 12px; margin-bottom: 1.5rem;
                border: 1px solid rgba(102,126,234,0.2);">
        <h3 style="margin:0; color: #667eea;">⚖️ Side-by-Side Comparison</h3>
        <p style="margin: 0.5rem 0 0 0; color: rgba(255,255,255,0.7); font-size: 0.9rem;">
            Select up to 4 phones to compare their specs
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Initialize session state
    if "num_phones" not in st.session_state:
        st.session_state.num_phones = 2

    # Get filtered phones from database
    logger.debug(f"Getting filtered phones with filters: {filters}")
    db = resources.db
    
    with log_timing("Get filtered phones for comparison"):
        filtered_phones = db.get_filtered_phones(
            company=filters.get("company"),
            price_min=filters.get("price_min"),
            price_max=filters.get("price_max"),
            camera_min=filters.get("camera_min"),
            camera_max=filters.get("camera_max"),
            battery_min=filters.get("battery_min"),
            battery_max=filters.get("battery_max"),
        )
        logger.info(f"Retrieved {len(filtered_phones)} filtered phones for comparison")

    if not filtered_phones:
        st.warning("🔍 No phones found matching your filters. Try adjusting the sidebar filters.")
        return

    # Stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📱 Available Phones", len(filtered_phones))
    with col2:
        st.metric("✅ Selected", st.session_state.num_phones)
    with col3:
        st.metric("📊 Max Comparison", "4 phones")

    st.divider()

    # Phone selection
    st.markdown("### 📱 Select Phones")

    selected_phones = []
    phone_cols = st.columns(st.session_state.num_phones)

    for i in range(st.session_state.num_phones):
        with phone_cols[i]:
            st.markdown(f"""
            <div style="background: rgba(102,126,234,0.1); padding: 0.5rem 1rem; 
                        border-radius: 8px; text-align: center; margin-bottom: 0.5rem;">
                <span style="font-weight: 600; color: #667eea;">Phone {i+1}</span>
            </div>
            """, unsafe_allow_html=True)

            phone = st.selectbox(
                f"Select Phone {i+1}",
                [""] + filtered_phones,
                key=f"phone_selector_{i}",
                label_visibility="collapsed",
            )
            if phone:
                selected_phones.append(phone)
                st.success(f"✅ {phone[:30]}...")

    # Add/Remove buttons
    st.markdown("")
    btn_cols = st.columns([1, 1, 3])
    with btn_cols[0]:
        if st.session_state.num_phones < 4:
            if st.button("➕ Add Phone", use_container_width=True):
                st.session_state.num_phones += 1
                st.rerun()
    with btn_cols[1]:
        if st.session_state.num_phones > 1:
            if st.button("➖ Remove", use_container_width=True):
                st.session_state.num_phones -= 1
                key = f"phone_selector_{st.session_state.num_phones}"
                if key in st.session_state:
                    del st.session_state[key]
                st.rerun()

    st.divider()

    # Compare button
    if len(selected_phones) >= 2:
        if st.button("🔍 Compare Selected Phones", type="primary", use_container_width=True):
            logger.info(f"Comparing {len(selected_phones)} phones: {selected_phones}")
            with st.spinner("📊 Analyzing phones..."):
                with log_timing("Phone comparison"):
                    df = db.get_phone_data(selected_phones)
                    logger.info(f"Retrieved data for {len(df)} phone record(s)")

            if not df.empty:
                _display_comparison(df, selected_phones)
            else:
                logger.warning("No data found for selected phones")
                st.warning("⚠️ No data found for selected phones. Please try selecting different phones or check the spelling.")

    elif len(selected_phones) == 1:
        st.info("👆 Select at least 2 phones to compare")
    else:
        st.info("👆 Select phones from the dropdowns above to start comparing")


def _display_comparison(df, selected_phones):
    """Display comparison results."""
    # Summary cards
    st.markdown("### 📊 Quick Summary")
    summary_cols = st.columns(len(df))

    for idx, (_, row) in enumerate(df.iterrows()):
        with summary_cols[idx]:
            st.markdown(f"""
            <div style="background: linear-gradient(145deg, #1e1e2f, #2a2a4a);
                        border-radius: 12px; padding: 1rem; text-align: center;
                        border: 1px solid rgba(102,126,234,0.3);">
                <h4 style="color: #667eea; margin: 0 0 0.5rem 0; font-size: 0.9rem;">
                    {row.get('Company Name', 'N/A')}
                </h4>
                <p style="color: white; font-weight: 600; margin: 0 0 0.8rem 0;">
                    {str(row.get('Model Name', 'N/A'))[:25]}
                </p>
                <p style="color: #4ade80; font-size: 1.2rem; font-weight: 700; margin: 0;">
                    ₹{row.get('Launched Price (INR)', 0):,.0f}
                </p>
            </div>
            """, unsafe_allow_html=True)

            st.metric("🔋 Battery", f"{row.get('Battery Capacity (mAh)', 'N/A')} mAh")
            st.metric("📷 Camera", f"{row.get('Back Camera (MP)', 'N/A')} MP")
            st.metric("💾 RAM", f"{row.get('RAM (GB)', 'N/A')} GB")

    st.divider()

    # Detailed comparison table
    st.markdown("### 📋 Detailed Comparison")

    df_display = df.copy()
    df_display["Phone"] = df_display["Company Name"] + " " + df_display["Model Name"]

    important_cols = [
        "Phone", "Launched Price (INR)", "Battery Capacity (mAh)",
        "Back Camera (MP)", "Front Camera (MP)", "RAM (GB)",
        "Memory (GB)", "Screen Size (inches)", "Processor", "User Rating.1",
    ]
    display_cols = [col for col in important_cols if col in df_display.columns]
    df_selected = df_display[display_cols]

    df_transposed = df_selected.set_index("Phone").T
    df_transposed.index.name = "Specification"

    st.dataframe(df_transposed, use_container_width=True, height=400)

    # Winner highlights
    st.markdown("### 🏆 Category Winners")
    winner_cols = st.columns(4)

    winners = [
        ("💰 Best Price", "Launched Price (INR)", "min", "rgba(74,222,128,0.1)", "#4ade80"),
        ("🔋 Best Battery", "Battery Capacity (mAh)", "max", "rgba(251,191,36,0.1)", "#fbbf24"),
        ("📷 Best Camera", "Back Camera (MP)", "max", "rgba(168,85,247,0.1)", "#a855f7"),
        ("💾 Most RAM", "RAM (GB)", "max", "rgba(59,130,246,0.1)", "#3b82f6"),
    ]

    for i, (label, col, func, bg_color, text_color) in enumerate(winners):
        with winner_cols[i]:
            if col in df.columns:
                if func == "min":
                    winner = df.loc[df[col].idxmin()]
                else:
                    winner = df.loc[df[col].idxmax()]

                st.markdown(f"""
                <div style="background: {bg_color}; padding: 1rem; border-radius: 8px; text-align: center;">
                    <p style="color: {text_color}; font-weight: 600; margin: 0;">{label}</p>
                    <p style="color: white; margin: 0.3rem 0 0 0; font-size: 0.85rem;">
                        {str(winner['Model Name'])[:20]}
                    </p>
                </div>
                """, unsafe_allow_html=True)
