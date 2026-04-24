"""
Streamlit chat UI — the human face of the knowledge engine.

🫏 Streamlit is the stable door — the donkey waits here for your questions.
You walk in, ask anything, and the donkey trots off into the graph to find your answer.
The 👍/👎 buttons are how you train the donkey to get better every visit.
"""
import streamlit as st
import httpx
import json
from datetime import datetime

API_BASE = st.sidebar.text_input("API URL", value="http://localhost:8200")

st.set_page_config(
    page_title="🧠 Knowledge Engine",
    page_icon="🫏",
    layout="wide",
)

st.title("🧠 Knowledge Engine")
st.caption("Ask anything about your AI portfolio — answers powered by GraphRAG + 🫏 donkey analogy")

# --- Sidebar: status ---
with st.sidebar:
    st.header("📊 Status")
    try:
        resp = httpx.get(f"{API_BASE}/health", timeout=5)
        health = resp.json()
        st.success(f"✅ {health.get('provider', 'unknown').upper()}")
        col1, col2 = st.columns(2)
        col1.metric("Chunks", health.get("vector_store_chunks", "?"))
        col2.metric("Topics", health.get("graph_topics", "?"))
    except Exception as e:
        st.error(f"❌ API offline: {e}")

    st.divider()
    st.header("⚙️ Actions")
    if st.button("🔄 Run Ingestion"):
        with st.spinner("Ingesting docs..."):
            try:
                r = httpx.post(f"{API_BASE}/ingest/run", timeout=10)
                st.success(r.json().get("message", "Started"))
            except Exception as ex:
                st.error(str(ex))

    if st.button("📚 Rebuild Wiki"):
        with st.spinner("Generating wiki pages..."):
            try:
                r = httpx.post(f"{API_BASE}/wiki/rebuild", timeout=300)
                result = r.json()
                st.success(f"Generated {result.get('pages_generated', '?')} pages")
            except Exception as ex:
                st.error(str(ex))

    st.divider()
    st.header("🗺️ Topics")
    try:
        r = httpx.get(f"{API_BASE}/wiki/topics", timeout=5)
        topics = r.json().get("topics", [])
        for t in topics[:20]:
            st.write(f"• {t['name']}")
        if len(topics) > 20:
            st.caption(f"... and {len(topics) - 20} more")
    except Exception:
        st.caption("No topics yet — run ingestion first")

# --- Chat history ---
if "messages" not in st.session_state:
    st.session_state.messages = []

if "session_id" not in st.session_state:
    import uuid
    st.session_state.session_id = str(uuid.uuid4())[:8]

# Render history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("donkey"):
            st.info(msg["donkey"])
        if msg.get("sources"):
            with st.expander("📎 Sources"):
                for s in msg["sources"]:
                    st.caption(s)
        if msg.get("topics"):
            st.caption(f"🔗 Topics: {', '.join(msg['topics'])}")
        if msg.get("latency_ms"):
            st.caption(f"⏱ {msg['latency_ms']}ms | {msg.get('provider', '')}")

# --- Feedback buttons ---
def submit_feedback(question: str, answer: str, thumbs_up: bool, correction: str = ""):
    try:
        httpx.post(f"{API_BASE}/feedback/", json={
            "question": question,
            "answer": answer,
            "thumbs_up": thumbs_up,
            "correction": correction,
            "session_id": st.session_state.session_id,
            "timestamp": datetime.utcnow().isoformat(),
        }, timeout=5)
    except Exception:
        pass

# --- Chat input ---
if prompt := st.chat_input("Ask anything about your AI portfolio..."):
    # Show user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Call API
    with st.chat_message("assistant"):
        with st.spinner("🫏 The donkey is thinking..."):
            try:
                resp = httpx.post(
                    f"{API_BASE}/chat/",
                    json={"question": prompt, "session_id": st.session_state.session_id},
                    timeout=120,
                )
                data = resp.json()
                answer = data.get("answer", "No answer returned.")
                donkey = data.get("donkey_analogy", "")
                sources = data.get("sources", [])
                topics = data.get("topics", [])
                latency = data.get("latency_ms", 0)
                provider = data.get("provider", "")

                st.markdown(answer)
                if donkey:
                    st.info(donkey)
                if sources:
                    with st.expander("📎 Sources"):
                        for s in sources:
                            st.caption(s)
                if topics:
                    st.caption(f"🔗 Topics: {', '.join(topics)}")
                st.caption(f"⏱ {latency}ms | {provider}")

                # Feedback buttons
                col_up, col_down, _ = st.columns([1, 1, 8])
                with col_up:
                    if st.button("👍", key=f"up_{len(st.session_state.messages)}"):
                        submit_feedback(prompt, answer, True)
                        st.toast("✅ Saved to wiki!")
                with col_down:
                    if st.button("👎", key=f"down_{len(st.session_state.messages)}"):
                        correction = st.text_input("What should the answer be?", key=f"corr_{len(st.session_state.messages)}")
                        submit_feedback(prompt, answer, False, correction)
                        st.toast("📝 Added to eval set for improvement")

                # Save to history
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "donkey": donkey,
                    "sources": sources,
                    "topics": topics,
                    "latency_ms": latency,
                    "provider": provider,
                })

            except Exception as e:
                st.error(f"❌ API error: {e}")
                st.session_state.messages.append({"role": "assistant", "content": f"Error: {e}"})
