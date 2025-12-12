"""Query Tab - AI Chat Assistant UI."""
import hashlib
import streamlit as st
from typing import Dict, Any

from src.services import resources
from src.utils.logger import get_logger, log_timing

logger = get_logger(__name__)


MAX_HISTORY = 5


def _get_cache_key(query: str, filters: Dict) -> str:
    """Generate cache key from query + filters."""
    filter_str = str(sorted(filters.items()))
    return hashlib.md5(f"{query.lower().strip()}|{filter_str}".encode()).hexdigest()


def _init_session_state():
    """Initialize all session state variables."""
    defaults = {
        "chat_history": [],
        "query_cache": {},
        "pending_query": None,
        "current_response": None,
        "current_query": None,
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


def _add_to_history(role: str, content: str, extra: Dict = None):
    """Add message to chat history (keeps last MAX_HISTORY exchanges)."""
    entry = {"role": role, "content": content}
    if extra:
        entry["extra"] = extra
    st.session_state.chat_history.append(entry)

    # Keep only last MAX_HISTORY user queries
    user_count = sum(1 for m in st.session_state.chat_history if m["role"] == "user")
    while user_count > MAX_HISTORY:
        for i, m in enumerate(st.session_state.chat_history):
            if m["role"] == "user":
                st.session_state.chat_history.pop(i)
                if i < len(st.session_state.chat_history) and st.session_state.chat_history[i]["role"] == "assistant":
                    st.session_state.chat_history.pop(i)
                break
        user_count = sum(1 for m in st.session_state.chat_history if m["role"] == "user")


def _display_response(response_data: Dict):
    """Display response content."""
    if response_data.get("corrections"):
        with st.expander("✏️ Name Corrections Applied", expanded=False):
            for c in response_data["corrections"]:
                st.info(c)

    if response_data.get("content"):
        st.markdown(response_data["content"])


def _display_chat_history():
    """Display chat history in reverse order (newest first)."""
    pairs = []
    i = 0
    history = st.session_state.chat_history

    while i < len(history):
        if history[i]["role"] == "user":
            user_msg = history[i]
            assistant_msg = history[i + 1] if i + 1 < len(history) and history[i + 1]["role"] == "assistant" else None
            pairs.append((user_msg, assistant_msg))
            i += 2 if assistant_msg else 1
        else:
            i += 1

    for user_msg, assistant_msg in reversed(pairs):
        if assistant_msg:
            with st.chat_message("assistant"):
                extra = assistant_msg.get("extra", {})

                if extra.get("corrections"):
                    with st.expander("✏️ Name Corrections Applied"):
                        for c in extra["corrections"]:
                            st.info(c)

                st.markdown(assistant_msg["content"])

        with st.chat_message("user"):
            st.write(user_msg["content"])

        st.divider()


def _process_query(user_query: str, filters: Dict) -> Dict[str, Any]:
    """Process query using QueryProcessor with status updates."""
    logger.info(f"Processing user query: {user_query[:100]}")
    
    status_messages = []

    def on_status(msg: str):
        status_messages.append(msg)

    with st.status("🚀 Processing your query...", expanded=True) as status:
        with log_timing("Query processing"):
            # Use QueryProcessor
            response = resources.query_processor.process(
                user_query,
                filters,
                on_status=lambda msg: status.write(f"✅ {msg}"),
            )
            status.update(label="✨ Complete!", state="complete")
            logger.info(f"Query processing completed. Task: {response.get('task')}, "
                       f"Results: {len(response.get('results', [])) if response.get('results') is not None else 0}")

    return response


def render(filters: Dict):
    """Render the Query & Search tab."""
    _init_session_state()

    # Welcome header
    st.markdown("""
    <div style="background: linear-gradient(135deg, rgba(102,126,234,0.1), rgba(118,75,162,0.1)); 
                padding: 1.5rem; border-radius: 12px; margin-bottom: 1.5rem;
                border: 1px solid rgba(102,126,234,0.2);">
        <h3 style="margin:0; color: #667eea; font-size: 1.4rem;">🤖 Your Personal Phone Advisor</h3>
        <p style="margin: 0.8rem 0 0 0; color: rgba(255,255,255,0.8); font-size: 1rem; line-height: 1.6;">
            💬 Ask me anything about phones! I can help you compare models, find the best deals, 
            get recommendations, or answer tech questions. Just type your question below!
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Quick suggestion chips
    st.markdown("**💡 Quick Questions to Get Started:**")
    suggestions = [
        "Best phone under ₹30,000",
        "Compare iPhone 16 vs Samsung S24",
        "Best camera phone",
        "Phones with 5000mAh battery",
    ]

    chip_cols = st.columns(4)
    for i, suggestion in enumerate(suggestions):
        with chip_cols[i]:
            if st.button(suggestion, key=f"suggestion_{i}", use_container_width=True):
                st.session_state.pending_query = suggestion
                st.rerun()

    st.markdown("")

    # Input form (Enter key submits)
    with st.form(key="query_form", clear_on_submit=True):
        col1, col2, col3 = st.columns([6, 1, 1])
        with col1:
            user_query = st.text_input(
                "Ask about phones...",
                placeholder="💬 Example: 'Best gaming phone under ₹40,000' or 'Compare iPhone 16 vs OnePlus 12'...",
                key="query_input",
                label_visibility="collapsed",
            )
        with col2:
            submit = st.form_submit_button("🚀 Ask", type="primary", use_container_width=True)
        with col3:
            clear = st.form_submit_button("🗑️ Clear", use_container_width=True)

    # Handle clear
    if clear:
        logger.info("Clearing chat history and cache")
        st.session_state.chat_history = []
        st.session_state.query_cache = {}
        st.session_state.pending_query = None
        st.session_state.current_response = None
        st.session_state.current_query = None
        st.rerun()

    # Handle pending query from suggestions
    if st.session_state.pending_query:
        user_query = st.session_state.pending_query
        st.session_state.pending_query = None
        submit = True

    st.divider()

    # Process new query
    if submit and user_query:
        logger.info(f"New query submitted: {user_query[:100]}")
        st.session_state.current_response = None
        st.session_state.current_query = user_query

        _add_to_history("user", user_query)

        # Check cache
        cache_key = _get_cache_key(user_query, filters)
        cached = st.session_state.query_cache.get(cache_key)

        with st.chat_message("user"):
            st.write(user_query)

        with st.chat_message("assistant"):
            if cached:
                logger.info("Using cached response")
                st.caption("⚡ *Cached response*")
                response_data = cached
            else:
                logger.info("Processing new query (not cached)")
                response_data = _process_query(user_query, filters)
                st.session_state.query_cache[cache_key] = response_data

            st.session_state.current_response = response_data
            _display_response(response_data)

        _add_to_history("assistant", response_data["content"], extra={
            "corrections": response_data.get("corrections", []),
            "task": response_data.get("task"),
        })

        st.divider()

    # Show last response if exists
    elif st.session_state.current_response and st.session_state.current_query:
        with st.chat_message("user"):
            st.write(st.session_state.current_query)
        with st.chat_message("assistant"):
            _display_response(st.session_state.current_response)
        st.divider()

    # Chat history (collapsible)
    if st.session_state.chat_history:
        query_count = sum(1 for m in st.session_state.chat_history if m["role"] == "user")
        with st.expander(f"📜 Previous Queries ({query_count})", expanded=False):
            _display_chat_history()
