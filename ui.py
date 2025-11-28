import base64
import streamlit as st
from datetime import datetime
from scrape import scrape_multiple
from search import get_search_results
from llm_utils import BufferedStreamingHandler, get_model_choices
from llm import get_llm, refine_query, filter_results, generate_summary


# Cache expensive backend calls
@st.cache_data(ttl=200, show_spinner=False)
def cached_search_results(refined_query: str, threads: int):
    return get_search_results(refined_query.replace(" ", "+"), max_workers=threads)


@st.cache_data(ttl=200, show_spinner=False)
def cached_scrape_multiple(filtered: list, threads: int):
    return scrape_multiple(filtered, max_workers=threads)


# Streamlit page configuration
st.set_page_config(
    page_title="Robin: AI-Powered Dark Web OSINT Tool",
    page_icon="🕵️‍♂️",
    initial_sidebar_state="expanded",
)

# Custom CSS for dark web terminal styling
st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');

        body {
            font-family: 'JetBrains Mono', 'Courier New', monospace;
            background-color: #000000;
            color: #00FF41;
        }

        .terminal {
            background: #000000;
            border: 2px solid #00FF41;
            border-radius: 5px;
            box-shadow: 0 0 15px #00FF41;
            font-family: 'JetBrains Mono', monospace;
            color: #00FF41;
            padding: 10px;
        }

        .glitch {
            animation: glitch 3s infinite;
            color: #00FF41;
            text-shadow: 0 0 5px #00FF41;
        }

        @keyframes glitch {
            0%, 100% { transform: translate(0); text-shadow: 0 0 5px #00FF41; }
            20% { transform: translate(-1px, 1px); text-shadow: 1px 0 5px #FF0040; }
            40% { transform: translate(-1px, -1px); text-shadow: -1px 0 5px #00FF41; }
            60% { transform: translate(1px, 1px); text-shadow: 0 1px 5px #FF0040; }
            80% { transform: translate(1px, -1px); text-shadow: 0 -1px 5px #00FF41; }
        }

        .danger-text {
            color: #FF0040;
            text-shadow: 0 0 5px #FF0040;
            font-weight: bold;
        }

        .colHeight {
            max-height: 40vh;
            overflow-y: auto;
            text-align: center;
            background: #0a0a0a;
            border: 1px solid #333;
            border-radius: 3px;
        }

        .pTitle {
            font-weight: bold;
            color: #00FF41;
            margin-bottom: 0.5em;
            text-shadow: 0 0 3px #00FF41;
        }

        .aStyle {
            font-size: 18px;
            font-weight: bold;
            padding: 5px;
            padding-left: 0px;
            text-align: center;
            color: #00FF41;
        }

        .ascii-art {
            font-family: 'Courier New', monospace;
            color: #00FF41;
            text-align: center;
            white-space: pre;
            font-size: 12px;
        }

        .status-terminal {
            background: #000000;
            border: 1px solid #00FF41;
            padding: 10px;
            margin: 5px 0;
            font-family: 'Courier New', monospace;
            color: #00FF41;
        }

        .sidebar-terminal {
            background: #0a0a0a;
            border: 1px solid #333;
            padding: 10px;
            border-radius: 3px;
        }

        .stButton>button {
            background-color: #0a0a0a !important;
            color: #00FF41 !important;
            border: 1px solid #00FF41 !important;
            border-radius: 3px !important;
        }

        .stButton>button:hover {
            background-color: #00FF41 !important;
            color: #000000 !important;
            box-shadow: 0 0 5px #00FF41 !important;
        }

        .stTextInput>div>div>input {
            background-color: #0a0a0a !important;
            color: #00FF41 !important;
            border: 1px solid #00FF41 !important;
        }

        .stSelectbox>div>div>select {
            background-color: #0a0a0a !important;
            color: #00FF41 !important;
            border: 1px solid #00FF41 !important;
        }
    </style>""",
    unsafe_allow_html=True,
)


# Sidebar - Terminal Style
st.sidebar.markdown("""
<div class="ascii-art">
██████╗  ██████╗ ██████╗ ██╗███╗   ██╗
██╔══██╗██╔═══██╗██╔══██╗██║████╗  ██║
██████╔╝██║   ██║██████╔╝██║██╔██╗ ██║
██╔══██╗██║   ██║██╔══██╗██║██║╚██╗██║
██║  ██║╚██████╔╝██████╔╝██║██║ ╚████║
╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═╝╚═╝  ╚═══╝
</div>
<div class="status-terminal">
> INITIALIZING DARK WEB OSINT MODULE...<br>
> TOR CONNECTION: ESTABLISHED<br>
> STATUS: READY FOR INVESTIGATION
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.markdown('<div class="danger-text">⚠️ CLASSIFIED ACCESS ONLY</div>', unsafe_allow_html=True)
st.sidebar.markdown("---")
st.sidebar.markdown('<div class="sidebar-terminal">', unsafe_allow_html=True)
st.sidebar.markdown("```bash\n> CONFIGURATION TERMINAL\n```")

model_options = get_model_choices()
default_model_index = (
    next(
        (idx for idx, name in enumerate(model_options) if name.lower() == "gpt4o"),
        0,
    )
    if model_options
    else 0
)
model = st.sidebar.selectbox(
    "> Select AI Model:",
    model_options,
    index=default_model_index,
    key="model_select",
)
if any(name not in {"gpt4o", "gpt-4.1", "claude-3-5-sonnet-latest", "llama3.1", "gemini-2.5-flash"} for name in model_options):
    st.sidebar.caption("⚠️ Local Ollama models detected")

threads = st.sidebar.slider("> Scraping Threads:", 1, 16, 4, key="thread_slider")
st.sidebar.markdown("```bash\n> STATUS: CONFIGURATION LOADED\n```")
st.sidebar.markdown('</div>', unsafe_allow_html=True)


# Main UI - Terminal Interface
st.markdown("""
<div class="ascii-art">
╔══════════════════════════════════════════════════════════════════════════════╗
║                    DARK WEB OSINT INVESTIGATION TERMINAL                     ║
║                    =======================================                   ║
║                                                                              ║
║  ██▀███   ▒█████   ▄▄▄█████▓ ██▓    ▄▄▄█████▓ ██▓ ██▓    ▄▄▄█████▓ ██▓       ║
║  ▓██ ▒ ██▒▒██▒  ██▒▓  ██▒ ▓▒▓██▒    ▓  ██▒ ▓▒▓██▒▓██▒    ▓  ██▒ ▓▒▓██▒       ║
║  ▓██ ░▄█ ▒▒██░  ██▒▒ ▓██░ ▒░▒██░    ▒ ▓██░ ▒░▒██▒▒██░    ▒ ▓██░ ▒░▒██░       ║
║  ▒██▀▀█▄  ▒██   ██░░ ▓██▓ ░ ▒██░    ░ ▓██▓ ░ ░██░░██░    ░ ▓██▓ ░ ▒██░       ║
║  ░██▓ ▒██▒░ ████▓▒░  ▒██▒ ░ ░██████▒  ▒██▒ ░ ░██░▓██▒ ░    ▒██▒ ░ ░██████▒   ║
║  ░ ▒▓ ░▒▓░░ ▒░▒░▒░   ▒ ░░   ░ ▒░▓  ░  ▒ ░░   ░▓  ▒ ░░      ▒ ░░   ░ ▒░▓  ░   ║
║    ░▒ ░ ▒░  ░ ▒ ▒░     ░    ░ ░ ▒  ░    ░     ▒ ░░ ░         ░    ░ ░ ▒  ░   ║
║    ░░   ░ ░ ░ ░ ▒    ░        ░ ░     ░       ▒ ░  ░ ░       ░        ░ ░    ║
║     ░         ░ ░                 ░  ░        ░                   ░  ░       ║
║                                                                              ║
║                    [CLASSIFIED] AI-POWERED DARK WEB ANALYSIS                 ║
╚══════════════════════════════════════════════════════════════════════════════╝
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="danger-text">⚠️ WARNING: This tool accesses restricted networks. Use at your own risk.</div>', unsafe_allow_html=True)

# Terminal-style input form
st.markdown('<div class="terminal">', unsafe_allow_html=True)
with st.form("search_form", clear_on_submit=True):
    st.markdown("```bash\n> Enter your investigation query:\n```")
    col_input, col_button = st.columns([10, 1])
    query = col_input.text_input(
        "",
        placeholder="e.g., ransomware payments, zero-day exploits...",
        label_visibility="collapsed",
        key="query_input",
    )
    run_button = col_button.form_submit_button("EXECUTE")
st.markdown('</div>', unsafe_allow_html=True)

# Terminal status display
st.markdown('<div class="status-terminal">', unsafe_allow_html=True)
status_slot = st.empty()
st.markdown('</div>', unsafe_allow_html=True)

# Investigation progress terminals
cols = st.columns(3)
p1, p2, p3 = [col.empty() for col in cols]

# Intelligence summary terminal
summary_container_placeholder = st.empty()


# Process the query
if run_button and query:
    # clear old state
    for k in ["refined", "results", "filtered", "scraped", "streamed_summary"]:
        st.session_state.pop(k, None)

    # Stage 1 - Load LLM
    with status_slot.container():
        with st.spinner("🔄 Loading LLM..."):
            llm = get_llm(model)

    # Stage 2 - Refine query
    with status_slot.container():
        with st.spinner("🔄 Refining query..."):
            st.session_state.refined = refine_query(llm, query)
    p1.container(border=True).markdown(
        f"<div class='colHeight'><p class='pTitle'>Refined Query</p><p>{st.session_state.refined}</p></div>",
        unsafe_allow_html=True,
    )

    # Stage 3 - Search dark web
    with status_slot.container():
        with st.spinner("🔍 Searching dark web..."):
            st.session_state.results = cached_search_results(
                st.session_state.refined, threads
            )
    p2.container(border=True).markdown(
        f"<div class='colHeight'><p class='pTitle'>Search Results</p><p>{len(st.session_state.results)}</p></div>",
        unsafe_allow_html=True,
    )

    # Stage 4 - Filter results
    with status_slot.container():
        with st.spinner("🗂️ Filtering results..."):
            st.session_state.filtered = filter_results(
                llm, st.session_state.refined, st.session_state.results
            )
    p3.container(border=True).markdown(
        f"<div class='colHeight'><p class='pTitle'>Filtered Results</p><p>{len(st.session_state.filtered)}</p></div>",
        unsafe_allow_html=True,
    )

    # Stage 5 - Scrape content
    with status_slot.container():
        with st.spinner("📜 Scraping content..."):
            st.session_state.scraped = cached_scrape_multiple(
                st.session_state.filtered, threads
            )

    # Stage 6 - Summarize
    # 6a) Prepare session state for streaming text
    st.session_state.streamed_summary = ""

    # 6c) UI callback for each chunk
    def ui_emit(chunk: str):
        st.session_state.streamed_summary += chunk
        summary_slot.markdown(st.session_state.streamed_summary)

    with summary_container_placeholder.container():
        st.markdown("""
<div class="terminal">
╔══════════════════════════════════════════════════════════════════════════════╗
║                        INTELLIGENCE ANALYSIS COMPLETE                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
</div>
        """, unsafe_allow_html=True)
        summary_slot = st.empty()

    # 6d) Inject your two callbacks and invoke exactly as before
    with status_slot.container():
        with st.spinner("✍️ Generating summary..."):
            stream_handler = BufferedStreamingHandler(ui_callback=ui_emit)
            llm.callbacks = [stream_handler]
            _ = generate_summary(llm, query, st.session_state.scraped)

        st.markdown("""
<div class="terminal">
║ DOWNLOAD INTELLIGENCE REPORT                                                 ║
╚══════════════════════════════════════════════════════════════════════════════╝
</div>
        """, unsafe_allow_html=True)

        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        fname = f"intelligence_report_{now}.md"
        b64 = base64.b64encode(st.session_state.streamed_summary.encode()).decode()
        href = f'<div class="aStyle">⬇️ <a href="data:file/markdown;base64,{b64}" download="{fname}">DOWNLOAD CLASSIFIED REPORT</a></div>'
        st.markdown(href, unsafe_allow_html=True)

    st.markdown('<div class="status-terminal">> INVESTIGATION COMPLETE - DATA SECURED</div>', unsafe_allow_html=True)
