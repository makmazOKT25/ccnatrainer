import os
import random
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# Initialize Gemini Client
client = genai.Client(api_key=api_key) if api_key else None

# Pydantic schema for strict structured output
class CCNAQuestion(BaseModel):
    topic: str = Field(description="CCNA domain name")
    scenario: str = Field(description="Practical scenario or problem statement")
    options: list[str] = Field(description="Four distinct options (A, B, C, D)", min_length=4, max_length=4)
    correct_index: int = Field(description="Zero-based index of the correct answer (0 to 3)", ge=0, le=3)
    explanation: str = Field(description="Clear explanation of why the correct option is right and others are incorrect")
    connection_note: str = Field(description="Brief note connecting this to a previous mistake if applicable, otherwise empty string")

# CCNA 200-301 Official Exam Domains
CCNA_DOMAINS = [
    "Network Fundamentals",
    "Network Access",
    "IP Connectivity",
    "IP Services",
    "Security Fundamentals",
    "Automation & Programmability"
]

# Initialize Session State
if "topic_weights" not in st.session_state:
    st.session_state.topic_weights = {domain: 1.0 for domain in CCNA_DOMAINS}
if "last_mistake" not in st.session_state:
    st.session_state.last_mistake = None
if "current_question" not in st.session_state:
    st.session_state.current_question = None
if "quiz_score" not in st.session_state:
    st.session_state.quiz_score = 0
if "total_answered" not in st.session_state:
    st.session_state.total_answered = 0
if "submitted" not in st.session_state:
    st.session_state.submitted = False
if "selected_option" not in st.session_state:
    st.session_state.selected_option = None

def select_target_topic() -> str:
    topics = list(st.session_state.topic_weights.keys())
    weights = list(st.session_state.topic_weights.values())
    return random.choices(topics, weights=weights, k=1)[0]

import time

def fetch_question(language: str):
    if not client:
        st.error("API Key not found. Please check your .env file.")
        return

    target_topic = select_target_topic()
    prompt = f"""
Generate a realistic, scenario-based CCNA 200-301 exam question.
Target Domain: {target_topic}
Language required for all text fields: {language}
"""
    if st.session_state.last_mistake:
        prompt += f"\nNote: The user previously made a mistake on topic '{st.session_state.last_mistake}'. If conceptually relevant, incorporate a brief connection into 'connection_note'."

    max_retries = 3
    with st.spinner("Generating CCNA question via Gemini..."):
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model="gemini-3.6-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=CCNAQuestion,
                        temperature=0.7,
                    ),
                )
                st.session_state.current_question = CCNAQuestion.model_validate_json(response.text)
                st.session_state.submitted = False
                st.session_state.selected_option = None
                st.rerun()
                return
            except Exception as e:
                if "503" in str(e) and attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                st.error(f"Failed to generate question: {e}")
                break
# Streamlit Page Setup
st.set_page_config(page_title="CCNA Exam Trainer", page_icon="🌐", layout="wide")

# Sidebar Configuration
with st.sidebar:
    st.title("⚙️ Settings & Stats")
    
    language = st.selectbox(
        "Language / Språk",
        options=["English", "Svenska", "Русский", "Українська", "Polski"],
        index=0
    )
    
    st.markdown("---")
    st.metric(label="Current Score", value=f"{st.session_state.quiz_score} / {st.session_state.total_answered}")
    
    st.subheader("Topic Weight Distribution")
    for topic, weight in st.session_state.topic_weights.items():
        st.caption(f"{topic}: {weight:.1f}")
        st.progress(min(weight / 4.0, 1.0))

    if st.button("Reset Session Progress", use_container_width=True):
        st.session_state.topic_weights = {domain: 1.0 for domain in CCNA_DOMAINS}
        st.session_state.last_mistake = None
        st.session_state.current_question = None
        st.session_state.quiz_score = 0
        st.session_state.total_answered = 0
        st.session_state.submitted = False
        st.rerun()

# Main Application Interface
st.title("🌐 CCNA 200-301 Adaptive Exam Trainer")

if st.session_state.current_question is None:
    st.info("Click below to start your practice session.")
    if st.button("Start Exam / New Question", type="primary"):
        fetch_question(language)
else:
    q = st.session_state.current_question

    st.markdown(f"**Domain:** `{q.topic}`")
    st.markdown(f"### {q.scenario}")

    options_formatted = [f"{chr(65 + idx)}) {opt}" for idx, opt in enumerate(q.options)]

    if not st.session_state.submitted:
        user_choice = st.radio(
            "Select the correct answer:",
            options=range(len(q.options)),
            format_func=lambda x: options_formatted[x],
            index=None
        )

        if st.button("Submit Answer", type="primary", disabled=user_choice is None):
            st.session_state.selected_option = user_choice
            st.session_state.submitted = True
            st.session_state.total_answered += 1

            if user_choice == q.correct_index:
                st.session_state.quiz_score += 1
                # Decrease weight on success (minimum 0.5)
                st.session_state.topic_weights[q.topic] = max(0.5, st.session_state.topic_weights[q.topic] - 0.3)
            else:
                st.session_state.last_mistake = q.topic
                # Increase weight on failure (capped at 4.0)
                st.session_state.topic_weights[q.topic] = min(4.0, st.session_state.topic_weights[q.topic] + 0.8)
            
            st.rerun()
    else:
        # Results View
        selected = st.session_state.selected_option
        is_correct = selected == q.correct_index

        if is_correct:
            st.success(f"✅ Correct! You selected: {options_formatted[selected]}")
        else:
            st.error(f"❌ Incorrect. You selected: {options_formatted[selected]}")
            st.info(f"**Correct Answer:** {options_formatted[q.correct_index]}")

        st.markdown("#### Explanation")
        st.write(q.explanation)

        if q.connection_note:
            st.warning(f"🔗 **Connection to Previous Focus:** {q.connection_note}")

        if st.button("Next Question ➡️", type="primary"):
            fetch_question(language)
            st.rerun()