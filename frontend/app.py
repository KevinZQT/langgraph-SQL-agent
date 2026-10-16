import json
import pandas as pd
import requests

from client import create_thread, run_chat
import streamlit as st


st.set_page_config(
    page_title="Database Assistant",
    page_icon="🔎",
    layout="wide",
)

st.title("Database Assistant")
st.caption("Ask questions, inspect SQL, and explore query results.")


if "session_id" not in st.session_state:
    st.session_state.session_id = None

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


with st.sidebar:
    st.header("Conversation")

    if st.button("New chat", use_container_width=True):
        st.session_state.session_id = None
        st.session_state.chat_history = []
        st.rerun()

    st.caption(
        "Conversation state is persisted by the LangGraph API server."
    )


def render_response(data: dict, index: int):
    st.markdown(data["answer"])

    if not data.get("database_used"):
        return

    if data.get("query_error"):
        st.error(data["query_error"])

    if data.get("sql"):
        with st.expander("View SQL"):
            st.code(data["sql"], language="sql")

    rows = data.get("results", [])

    if rows:
        if data.get("preview_only"):
            st.caption(
                "The assistant used a limited preview. "
                "The table shows all records returned by the backend."
            )

        st.dataframe(
            pd.DataFrame(rows),
            hide_index=True,
            use_container_width=True,
        )

        st.caption(
            f"{len(rows)} rows returned. "
            "The SQL query may include a LIMIT."
        )

        st.download_button(
            label="Download results",
            data=json.dumps(
                rows,
                ensure_ascii=False,
                indent=2,
            ),
            file_name="query_results.json",
            mime="application/json",
            key=f"download_{index}",
        )

    elif data.get("query_status") == "success":
        st.info("The query returned no rows.")


for index, message in enumerate(st.session_state.chat_history):
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.markdown(message["content"])
        else:
            render_response(message["data"], index)


question = st.chat_input(
    "Ask about your database or search the web...",
    max_chars=4000,
)

if question:
    with st.chat_message("user"):
        st.markdown(question)

    try:
        with st.spinner("Working on your question..."):
            if st.session_state.session_id is None:
                st.session_state.session_id = create_thread()

            data = run_chat(st.session_state.session_id, question)

        st.session_state.chat_history.extend(
            [
                {"role": "user", "content": question},
                {"role": "assistant", "data": data},
            ]
        )
        st.rerun()

    except requests.HTTPError as exc:
        details = "The LangGraph API returned an error."
        if exc.response is not None:
            try:
                details = str(exc.response.json().get("detail", details))
            except (ValueError, AttributeError):
                details = exc.response.text[:500] or details
        st.error(details)

    except requests.Timeout:
        st.error(
            "The request timed out. The backend may still be processing it. "
            "Wait before trying again."
        )

    except requests.RequestException:
        st.error(
            "Cannot connect to the backend. "
            "Check that LangGraph API is running."
        )