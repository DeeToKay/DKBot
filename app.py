import base64
import os
from pathlib import Path
from typing import List

import streamlit as st
from openai import OpenAI
from openai import OpenAIError

st.set_page_config(
    page_title="Daaniyal Khan Executive Career Bot",
    page_icon="💼",
    layout="wide",
)


# ---------- Styling ----------
st.markdown(
    """
    <style>
        .stApp {
            background-color: #1E1E1E;
            color: #EDEDED;
        }
        [data-testid="stSidebar"] {
            background-color: #171717;
            border-right: 1px solid #2f2f2f;
        }
        h1, h2, h3, h4 {
            color: #C5A065 !important;
        }
        .gold-divider {
            border-top: 1px solid #C5A065;
            margin-top: 0.5rem;
            margin-bottom: 1rem;
        }
        .profile-wrap {
            text-align: center;
            margin-bottom: 1rem;
        }
        .profile-wrap img {
            width: 140px;
            height: 140px;
            border-radius: 50%;
            object-fit: cover;
            border: 3px solid #C5A065;
            display: block;
            margin-left: auto;
            margin-right: auto;
        }
        .small-note {
            color: #BFBFBF;
            font-size: 0.9rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


SYSTEM_PROMPT_FALLBACK = """You are Daaniyal Khan's Chief of Staff speaking to recruiters and C-level leaders.

Mission:
- Represent Daaniyal Khan as a strategic, commercially focused executive leader.
- Use only facts from the uploaded CV and project files.
- If details are uncertain or unavailable, say: \"Please ask Daaniyal directly in the interview.\"

Tone:
- Professional, concise, results-oriented, confident, polite.
- No fluff, no exaggeration.

Behavioral instructions:
1) Leadership questions:
   - Highlight onboarding and recruiting impact, including scaling to 2000+ partners.
   - Mention the Competence Center as a leadership and enablement mechanism.
2) Innovation questions:
   - Explain the Digital Sales Organization (DVO) and BVO-Portal outcomes.
3) Salary questions:
   - Use this wording:
     \"Daaniyal targets roles with significant strategic impact, typically in the €350k+ OTE range, depending on the package structure.\"
4) Accuracy guardrail:
   - Never hallucinate facts.
   - If asked beyond provided evidence, explicitly state that and use the interview fallback line.

Format:
- Keep answers compact (3-8 bullet points or a short executive paragraph).
- Where useful, include measurable outcomes from source documents.
"""

SUGGESTED_QUESTIONS = [
    "What was the Digital VO Project?",
    "How did he optimize Recruiting?",
    "What is his leadership style?",
]


def get_api_key() -> str:
    """Resolve API key from Streamlit secrets, env var, or temporary user input."""
    key = st.secrets.get("OPENAI_API_KEY", None) if hasattr(st, "secrets") else None
    if not key:
        key = os.getenv("OPENAI_API_KEY")
    if not key:
        st.warning("Please provide an OpenAI API key to enable the executive chatbot.")
        key = st.sidebar.text_input("OpenAI API Key", type="password")
    return key or ""


def load_system_instruction() -> str:
    prompt_path = Path("system_instruction.txt")
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8").strip()
    return SYSTEM_PROMPT_FALLBACK


def find_rag_files() -> List[Path]:
    candidates = [
        Path("Daaniyal_Khan_Premium_CV.html"),
        Path("Competence-Center-Konzept.pdf"),
    ]

    dvo_matches = list(Path(".").glob("*DVO*")) + list(Path(".").glob("*Project*DVO*"))
    for match in dvo_matches:
        if match.is_file():
            candidates.append(match)

    unique_files = []
    seen = set()
    for file_path in candidates:
        if file_path.exists() and file_path.is_file() and file_path.name not in seen:
            unique_files.append(file_path)
            seen.add(file_path.name)
    return unique_files


def get_profile_image_src() -> str:
    # Prefer local images if present
    for p in [Path("profile.jpg"), Path("profile.jpeg"), Path("profile.png")]:
        if p.exists() and p.is_file():
            b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
            ext = "jpeg" if p.suffix.lower() in [".jpg", ".jpeg"] else "png"
            return f"data:image/{ext};base64,{b64}"
    # Fallback placeholder
    return "https://via.placeholder.com/300x300.png?text=Daaniyal+Khan"


def initialize_assistant(client: OpenAI, system_instruction: str) -> None:
    """Create assistant + vector store once per session."""
    if st.session_state.get("assistant_id"):
        return

    rag_files = find_rag_files()
    vector_store_id = None

    if rag_files:
        vector_store = client.beta.vector_stores.create(name="Daaniyal Career Knowledge")
        streams = [open(file_path, "rb") for file_path in rag_files]
        try:
            client.beta.vector_stores.file_batches.upload_and_poll(
                vector_store_id=vector_store.id,
                files=streams,
            )
            vector_store_id = vector_store.id
        finally:
            for stream in streams:
                stream.close()

    assistant_payload = {
        "name": "Daaniyal Khan Executive Career Bot",
        "instructions": system_instruction,
        "model": "gpt-4o",
    }

    if vector_store_id:
        assistant_payload["tools"] = [{"type": "file_search"}]
        assistant_payload["tool_resources"] = {
            "file_search": {"vector_store_ids": [vector_store_id]}
        }

    assistant = client.beta.assistants.create(**assistant_payload)
    thread = client.beta.threads.create()

    st.session_state.assistant_id = assistant.id
    st.session_state.thread_id = thread.id
    st.session_state.rag_files = [str(p) for p in rag_files]


def extract_assistant_text(message) -> str:
    chunks = []
    for part in message.content:
        if getattr(part, "type", "") == "text":
            chunks.append(part.text.value)
    return "\n".join(chunks).strip() or "Please ask Daaniyal directly in the interview."


def ask_assistant(client: OpenAI, user_prompt: str) -> str:
    client.beta.threads.messages.create(
        thread_id=st.session_state.thread_id,
        role="user",
        content=user_prompt,
    )

    run = client.beta.threads.runs.create_and_poll(
        thread_id=st.session_state.thread_id,
        assistant_id=st.session_state.assistant_id,
    )

    if run.status != "completed":
        return "I encountered an issue while generating a response. Please ask Daaniyal directly in the interview."

    messages = client.beta.threads.messages.list(thread_id=st.session_state.thread_id)
    for msg in messages.data:
        if msg.role == "assistant":
            return extract_assistant_text(msg)

    return "Please ask Daaniyal directly in the interview."


def render_sidebar() -> None:
    st.sidebar.markdown("## Executive Profile")
    img_src = get_profile_image_src()
    st.sidebar.markdown(
        f'<div class="profile-wrap"><img src="{img_src}" alt="Daaniyal Khan" /></div>',
        unsafe_allow_html=True,
    )

    st.sidebar.markdown("### Contact")
    st.sidebar.markdown("- **LinkedIn:** [Daaniyal Khan](https://www.linkedin.com)")
    st.sidebar.markdown("- **Email:** daaniyal@example.com")

    cv_path = Path("Daaniyal_Khan_Premium_CV.html")
    if cv_path.exists():
        st.sidebar.download_button(
            label="Download CV",
            data=cv_path.read_bytes(),
            file_name=cv_path.name,
            mime="text/html",
            use_container_width=True,
        )
    else:
        st.sidebar.info("Place `Daaniyal_Khan_Premium_CV.html` in this folder to enable CV download.")


def main() -> None:
    render_sidebar()

    st.title("Daaniyal Khan – Strategic Leader & Director | AI & Digital Distribution")
    st.markdown('<div class="gold-divider"></div>', unsafe_allow_html=True)

    api_key = get_api_key()
    if not api_key:
        st.stop()

    client = OpenAI(api_key=api_key)
    system_instruction = load_system_instruction()

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Welcome. I am Daaniyal Khan's executive career assistant. Ask me about leadership impact, transformation programs, or strategic fit.",
            }
        ]

    try:
        initialize_assistant(client, system_instruction)
    except OpenAIError as exc:
        st.error(f"Unable to initialize the assistant. Please verify your API key and try again.\n\nDetails: {exc}")
        st.stop()

    if st.session_state.get("rag_files"):
        st.caption(f"RAG active with {len(st.session_state.rag_files)} file(s): " + ", ".join(st.session_state.rag_files))
    else:
        st.caption("RAG is not active yet. Add the CV/project files to this directory.")

    st.markdown("#### Suggested Questions")
    cols = st.columns(3)
    for idx, question in enumerate(SUGGESTED_QUESTIONS):
        if cols[idx].button(question, use_container_width=True):
            st.session_state.pending_prompt = question

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input("Ask about Daaniyal's leadership, innovation projects, and executive fit...")

    if st.session_state.get("pending_prompt") and not prompt:
        prompt = st.session_state.pop("pending_prompt")

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Preparing executive response..."):
                try:
                    response = ask_assistant(client, prompt)
                except OpenAIError as exc:
                    response = f"I could not complete that request due to an API error. Please ask Daaniyal directly in the interview.\n\nDetails: {exc}"
            st.markdown(response)

        st.session_state.messages.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    main()
