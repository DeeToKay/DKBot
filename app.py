import base64
import os
from pathlib import Path
from typing import List

import streamlit as st
from openai import OpenAI
from openai import OpenAIError
from bs4 import BeautifulSoup

st.set_page_config(
    page_title="Daaniyal Khan Executive Career Bot",
    page_icon="💼",
    layout="wide",
)

# ---------- Styling ----------
st.markdown(
    """
    <style>
        .stApp { background-color: #1E1E1E; color: #EDEDED; }
        [data-testid="stSidebar"] { background-color: #171717; border-right: 1px solid #2f2f2f; }
        h1, h2, h3, h4 { color: #C5A065 !important; }
        .gold-divider { border-top: 1px solid #C5A065; margin-top: 0.5rem; margin-bottom: 1rem; }
        .profile-wrap { text-align: center; margin-bottom: 1rem; }
        .profile-wrap img { width: 140px; height: 140px; border-radius: 50%; object-fit: cover; border: 3px solid #C5A065; display: block; margin-left: auto; margin-right: auto; }
        .small-note { color: #BFBFBF; font-size: 0.9rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

SYSTEM_PROMPT_FALLBACK = """You are Daaniyal Khan's Chief of Staff speaking to recruiters and C-level leaders.
Mission: Represent Daaniyal Khan as a strategic, commercially focused executive leader.
Use ONLY facts from the provided CV/Context. If details are uncertain, say: "Please ask Daaniyal directly in the interview."
Tone: Professional, concise, results-oriented.
"""

SUGGESTED_QUESTIONS = [
    "What was the Digital VO Project?",
    "How did he optimize Recruiting?",
    "What is his leadership style?",
]

CV_FILENAME = "Daaniyal Khan Premium CV.html"

def get_api_key() -> str:
    # Hier KEIN key hardcoden!
    key = st.secrets.get("OPENAI_API_KEY") 
    if not key:
        key = os.getenv("OPENAI_API_KEY")
    if not key:
        st.warning("Please provide an OpenAI API key.")
        key = st.sidebar.text_input("OpenAI API Key", type="password")
    return key or ""

def load_cv_text() -> str:
    if not os.path.exists(CV_FILENAME):
        return ""
    try:
        with open(CV_FILENAME, "r", encoding="utf-8") as f:
            html_content = f.read()
        soup = BeautifulSoup(html_content, "html.parser")
        return soup.get_text(separator="\n").strip()
    except Exception as e:
        st.error(f"Fehler beim Lesen des CV: {e}")
        return ""

def get_profile_image_src() -> str:
    for p in [Path("profile.jpg"), Path("profile.jpeg"), Path("profile.png")]:
        if p.exists() and p.is_file():
            b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
            ext = "jpeg" if p.suffix.lower() in [".jpg", ".jpeg"] else "png"
            return f"data:image/{ext};base64,{b64}"
    return "https://via.placeholder.com/300x300.png?text=Daaniyal+Khan"

def ask_gpt(client: OpenAI, messages: List[dict]) -> str:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.7
    )
    return response.choices[0].message.content

def render_sidebar() -> None:
    st.sidebar.markdown("## Executive Profile")
    st.sidebar.markdown(f'<div class="profile-wrap"><img src="{get_profile_image_src()}" alt="Daaniyal Khan" /></div>', unsafe_allow_html=True)
    st.sidebar.markdown("### Contact")
    st.sidebar.markdown("- **LinkedIn:** [Daaniyal Khan](https://www.linkedin.com)")
    st.sidebar.markdown("- **Email:** daaniyalkh@gmail.com")
    st.sidebar.markdown("- **Webseite:** www.daaniyalkhan.com")
    

def main() -> None:
    render_sidebar()
    st.title("Daaniyal Khan – Strategic Leader & Director | AI & Digital Distribution")
    st.markdown('<div class="gold-divider"></div>', unsafe_allow_html=True)

    api_key = get_api_key()
    if not api_key: st.stop()

    client = OpenAI(api_key=api_key)
    cv_context = load_cv_text()
    
    full_system_prompt = f"{SYSTEM_PROMPT_FALLBACK}\n\nCONTEXT FROM CV:\n{cv_context}" if cv_context else SYSTEM_PROMPT_FALLBACK

    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Welcome. I am Daaniyal Khan's executive career assistant."}]

    if cv_context: st.caption("✅ RAG active: CV loaded successfully.")
    else: st.caption(f"⚠️ RAG inactive: File `{CV_FILENAME}` not found.")

    cols = st.columns(3)
    for idx, q in enumerate(SUGGESTED_QUESTIONS):
        if cols[idx].button(q, use_container_width=True): st.session_state.pending_prompt = q

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

    prompt = st.chat_input("Ask about Daaniyal...")
    if st.session_state.get("pending_prompt") and not prompt: prompt = st.session_state.pop("pending_prompt")

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Preparing..."):
                try:
                    msgs = [{"role": "system", "content": full_system_prompt}] + [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
                    response = ask_gpt(client, msgs)
                except OpenAIError as exc:
                    response = f"API Error: {exc}"
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()
