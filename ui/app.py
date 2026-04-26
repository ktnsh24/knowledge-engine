"""
Streamlit chat UI — the human face of the knowledge engine.

🚚 Streamlit is the depot door — the courier waits here for your questions.
You walk in, ask anything, and the courier trots off into the graph to find your answer.
The 👍/👎 buttons are how you train the courier to get better every visit.
The 🗺️ Knowledge Gaps sidebar shows where the roads are missing — fix those first.
"""
import streamlit as st
import httpx
import json
from datetime import datetime, timezone

API_BASE = st.sidebar.text_input("API URL", value="http://localhost:8200")

st.set_page_config(
    page_title="🧠 Knowledge Engine",
    page_icon="🚚",
    layout="wide",
)

st.title("🧠 Knowledge Engine")
st.caption("Ask anything about your AI portfolio — answers powered by GraphRAG + 🚚 courier analogy")

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

    # --- Knowledge Gaps panel ---
    st.header("🗺️ Knowledge Gaps")
    st.caption("Questions the courier couldn't answer from your docs")
    try:
        r = httpx.get(f"{API_BASE}/wiki/gaps?status=open", timeout=5)
        gaps_data = r.json()
        summary = gaps_data.get("summary", {})
        gaps = gaps_data.get("gaps", [])

        col_r, col_y, col_res = st.columns(3)
        col_r.metric("🔴 Gaps", summary.get("red_gaps", 0))
        col_y.metric("🟡 Partial", summary.get("yellow_partials", 0))
        col_res.metric("✅ Fixed", summary.get("resolved", 0))

        if gaps:
            with st.expander(f"View {len(gaps)} open gap(s)", expanded=False):
                for gap in gaps[:10]:
                    label = "🔴" if gap["confidence"] == "gap" else "🟡"
                    st.markdown(f"**{label} `{gap['id']}`** — {gap['question'][:60]}...")
                    st.caption(gap["reason"])
                    if gap.get("suggestion"):
                        st.info(f"💡 {gap['suggestion']}", icon="💡")
                    if st.button(f"✅ Mark resolved — {gap['id']}", key=f"resolve_{gap['id']}"):
                        try:
                            httpx.delete(f"{API_BASE}/wiki/gaps/{gap['id']}", timeout=5)
                            st.success("Marked as resolved!")
                            st.rerun()
                        except Exception as ex:
                            st.error(str(ex))
                    st.divider()
        else:
            st.success("No open gaps — knowledge base fully covers recent questions!")
    except Exception:
        st.caption("No gap data yet — ask some questions first")

    st.divider()

    # --- Candidates review panel ---
    st.header("🔵 Candidates for Review")
    st.caption("LLM answers to gap questions — promote to add to your knowledge base")
    try:
        r = httpx.get(f"{API_BASE}/wiki/candidates?status=pending", timeout=5)
        cdata = r.json()
        csummary = cdata.get("summary", {})
        candidates = cdata.get("candidates", [])

        col_p, col_pr, col_d = st.columns(3)
        col_p.metric("⏳ Pending", csummary.get("pending", 0))
        col_pr.metric("✅ Promoted", csummary.get("promoted", 0))
        col_d.metric("🗑 Discarded", csummary.get("discarded", 0))

        if candidates:
            with st.expander(f"Review {len(candidates)} pending answer(s)", expanded=False):
                for cand in candidates[:5]:
                    st.markdown(f"**Q:** {cand['question']}")
                    st.markdown(f"**A:** {cand['answer'][:300]}...")
                    st.info(cand.get("courier_analogy", ""))
                    col_promote, col_discard, _ = st.columns([1, 1, 4])
                    with col_promote:
                        if st.button("👍 Promote", key=f"promote_{cand['id']}"):
                            try:
                                httpx.post(f"{API_BASE}/wiki/candidates/{cand['id']}/promote", timeout=5)
                                st.success("Promoted! Run ingestion to absorb into knowledge base.")
                                st.rerun()
                            except Exception as ex:
                                st.error(str(ex))
                    with col_discard:
                        if st.button("👎 Discard", key=f"discard_{cand['id']}"):
                            try:
                                httpx.post(f"{API_BASE}/wiki/candidates/{cand['id']}/discard", timeout=5)
                                st.warning("Discarded.")
                                st.rerun()
                            except Exception as ex:
                                st.error(str(ex))
                    st.divider()
        else:
            st.caption("No pending candidates")
    except Exception:
        st.caption("No candidate data yet")

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
        if msg.get("courier"):
            st.info(msg["courier"])
        # Show gap warning if present
        if msg.get("confidence") == "gap":
            st.error(f"🔴 **Knowledge Gap** — {msg.get('gap_reason', '')}\n\n💡 {msg.get('gap_suggestion', '')}")
        elif msg.get("confidence") == "partial":
            st.warning(f"🟡 **Partial Coverage** — {msg.get('gap_reason', '')}\n\n💡 {msg.get('gap_suggestion', '')}")
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
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
        with st.spinner("🚚 The courier is thinking..."):
            try:
                resp = httpx.post(
                    f"{API_BASE}/chat/",
                    json={"question": prompt, "session_id": st.session_state.session_id},
                    timeout=120,
                )
                data = resp.json()
                answer = data.get("answer", "No answer returned.")
                courier = data.get("courier_analogy", "")
                sources = data.get("sources", [])
                topics = data.get("topics", [])
                latency = data.get("latency_ms", 0)
                provider = data.get("provider", "")
                confidence = data.get("confidence", "high")
                gap_reason = data.get("gap_reason", "")
                gap_suggestion = data.get("gap_suggestion", "")

                st.markdown(answer)
                if courier:
                    st.info(courier)

                # Show confidence / source indicator
                if confidence == "gap":
                    st.error(f"🔵 **LLM Knowledge (not in your docs yet)**\n\n{gap_reason}\n\n💡 Review the candidate answer in the sidebar — promote with 👍 to add it to your knowledge base.")
                elif confidence == "partial":
                    st.warning(f"🟡 **Partial coverage** — answer may be incomplete.\n\n{gap_reason}\n\n💡 {gap_suggestion}")
                else:
                    st.success("🟢 Answer grounded in your docs")

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
                    "courier": courier,
                    "sources": sources,
                    "topics": topics,
                    "latency_ms": latency,
                    "provider": provider,
                    "confidence": confidence,
                    "gap_reason": gap_reason,
                    "gap_suggestion": gap_suggestion,
                })

            except Exception as e:
                st.error(f"❌ API error: {e}")
                st.session_state.messages.append({"role": "assistant", "content": f"Error: {e}"})

st.set_page_config(
    page_title="🧠 Knowledge Engine",
    page_icon="🚚",
    layout="wide",
)

st.title("🧠 Knowledge Engine")
st.caption("Ask anything about your AI portfolio — answers powered by GraphRAG + 🚚 courier analogy")

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
        if msg.get("courier"):
            st.info(msg["courier"])
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
        with st.spinner("🚚 The courier is thinking..."):
            try:
                resp = httpx.post(
                    f"{API_BASE}/chat/",
                    json={"question": prompt, "session_id": st.session_state.session_id},
                    timeout=120,
                )
                data = resp.json()
                answer = data.get("answer", "No answer returned.")
                courier = data.get("courier_analogy", "")
                sources = data.get("sources", [])
                topics = data.get("topics", [])
                latency = data.get("latency_ms", 0)
                provider = data.get("provider", "")

                st.markdown(answer)
                if courier:
                    st.info(courier)
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
                    "courier": courier,
                    "sources": sources,
                    "topics": topics,
                    "latency_ms": latency,
                    "provider": provider,
                })

            except Exception as e:
                st.error(f"❌ API error: {e}")
                st.session_state.messages.append({"role": "assistant", "content": f"Error: {e}"})
