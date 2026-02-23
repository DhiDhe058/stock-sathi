import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
from duckduckgo_search import DDGS
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import edge_tts
import asyncio
import requests
import io
import os
import time
from companies import NIFTY_COMPANIES

# --- SECRETS & AI SETUP ---
try:
    GENAI_API_KEY = st.secrets["GENAI_API_KEY"]
except:
    GENAI_API_KEY = "PASTE_YOUR_FREE_KEY_HERE"

genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel('gemini-3-flash-preview')

if 'usage_count' not in st.session_state:
    st.session_state.usage_count = 0

# --- DATABASE CONNECTION (GOOGLE SHEETS) ---
def save_feedback(data_dict):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        # ⚠️ THE FIX: We must give the bot the direct URL to the spreadsheet!
        SHEET_URL = "https://docs.google.com/spreadsheets/d/1HdCVtR3TgmBkWNSlvYp0wLZq4Xa7r-T61Y5JzGwH_9c/edit?gid=0#gid=0"
        
        df = conn.read(spreadsheet=SHEET_URL, worksheet="Sheet1")
        new_row = pd.DataFrame([data_dict])
        
        if df.empty:
            updated_df = new_row
        else:
            updated_df = pd.concat([df, new_row], ignore_index=True)
            
        conn.update(spreadsheet=SHEET_URL, worksheet="Sheet1", data=updated_df)
    except Exception as e:
        st.error(f"Could not connect to Google Sheets: {e}")

# --- DIALOG POPUP (END OF SESSION) ---
@st.dialog("💬 We need your help! / हमें आपकी मदद चाहिए!")
def end_of_session_popup():
    st.write("You have reached your 3-company limit. We are building more features, tell us what you want!")
    name = st.text_input("Name (Optional)")
    email = st.text_input("Email (Required)")
    feedback = st.text_area("Your Feedback (Required)")
    
    if st.button("Submit Feedback"):
        if not email or not feedback:
            st.error("Please provide both an Email and Feedback.")
        else:
            save_feedback({"Type": "Limit Reached", "Company": "N/A", "Name": name, "Email": email, "Feedback": feedback})
            st.success("Thank you! You can close this window.")
            time.sleep(2)
            st.rerun()

# --- THE BILINGUAL DICTIONARY ---
st.set_page_config(page_title="Stock Sathi", page_icon="📈")

# The Toggle Switch
is_english = st.toggle("Switch to English / अंग्रेजी में बदलें")
LANG = "EN" if is_english else "HI"

UI = {
    "HI": {
        "title": "📈 Stock Sathi",
        "desc": "नीचे दी गई सूची से कंपनी चुनें और हम तुरंत उसका सारांश देंगे।",
        "select": "कंपनी चुनें (Type to search):",
        "btn": "त्वरित सारांश प्राप्त करें",
        "pos": "✅ अच्छी बातें",
        "neg": "🚩 खतरे के संकेत",
        "verdict": "📌 अंतिम निर्णय:",
        "ai_lang": "simple Hindi",
        "voice": "hi-IN-MadhurNeural"
    },
    "EN": {
        "title": "📈 Stock Sathi",
        "desc": "Select a company from the list below for a quick summary.",
        "select": "Select Company (Type to search):",
        "btn": "Get Quick Summary",
        "pos": "✅ Positives",
        "neg": "🚩 Red Flags",
        "verdict": "📌 Verdict:",
        "ai_lang": "simple English",
        "voice": "en-IN-PrabhatNeural"
    }
}

# --- THE ANALYZER (UPGRADED FOR COLUMNS) ---
@st.cache_data(show_spinner=False)
def analyze_company(company_name, language_code):
    ddgs = DDGS()
    
    news_text = "Latest News:\n"
    try:
        news_results = ddgs.news(company_name, timelimit="w", max_results=3)
        for result in news_results:
            news_text += f"- {result['title']}: {result['body']}\n"
    except:
        pass

    pdf_text = ""
    try:
        search_query = f"{company_name} investor presentation filetype:pdf site:bseindia.com"
        pdf_results = ddgs.text(search_query, max_results=1)
        if pdf_results and "href" in pdf_results[0]:
            pdf_url = pdf_results[0]["href"]
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(pdf_url, headers=headers, timeout=10)
            if response.status_code == 200:
                reader = PdfReader(io.BytesIO(response.content))
                for page in reader.pages[:10]:
                    pdf_text += page.extract_text() or ""
    except:
        pass 

    # THE NEW PROMPT: Forces AI to split the text perfectly for our UI columns
    prompt = f"""
    Analyze {company_name} using this news: {news_text} and presentation: {pdf_text}.
    Write entirely in {UI[language_code]['ai_lang']}.
    
    You MUST format your exact response using these ||| dividers so my code can read it:
    
    [Spoken Audio Script: Act as a financial friend. "Analyzing {company_name}..." Keep under 100 words. Plain text only.]
    |||
    [Positive 1]
    [Positive 2]
    [Positive 3]
    |||
    [Red Flag 1]
    [Red Flag 2]
    [Red Flag 3]
    |||
    [Verdict Tag: High Growth / Stable Growth / Slow Growth]
    """
    
    summary_text = ""
    for attempt in range(3):
        try:
            summary_text = model.generate_content(prompt).text
            break 
        except Exception as e:
            if "429" in str(e) or "Quota" in str(e):
                time.sleep(5) 
            else:
                raise e 

    # Parse the AI response into our 4 variables
    try:
        parts = summary_text.split("|||")
        audio_script = parts[0].strip()
        positives = parts[1].strip()
        negatives = parts[2].strip()
        verdict = parts[3].strip()
    except:
        audio_script = summary_text # Fallback if AI hallucinates formatting
        positives = "Data error."
        negatives = "Data error."
        verdict = "Unknown"

    # --- NEW AUDIO FIX ---
    # Stitch all the parts together so the voice reads everything naturally!
    full_text_to_read = f"{audio_script}. {positives}. {negatives}. {verdict}."
    cleaned_text = full_text_to_read.replace("*", "").replace("#", "").replace("_", "").replace("|", "")
    temp_audio_path = f"temp_{company_name.replace(' ', '_')}.mp3"
    
    async def generate_audio():
        communicate = edge_tts.Communicate(cleaned_text, UI[language_code]['voice'])
        await communicate.save(temp_audio_path)
    asyncio.run(generate_audio())
    
    with open(temp_audio_path, "rb") as f:
        audio_bytes = f.read()
    os.remove(temp_audio_path)
    
    # ⚠️ THIS IS THE LINE YOU ARE MISSING! IT MUST BE AT THE VERY END OF THE FUNCTION:
    return audio_script, positives, negatives, verdict, audio_bytes

# --- UI RENDER ---
st.title(UI[LANG]["title"])
st.write(UI[LANG]["desc"])

# The Dropdown (Replaces the Bouncer completely)
company_input = st.selectbox(UI[LANG]["select"], [""] + NIFTY_COMPANIES)

counter_box = st.empty()
counter_box.write(f"Remaining searches today: **{3 - st.session_state.usage_count}/3**")

# Trigger Popup if limit reached
if st.session_state.usage_count >= 3:
    end_of_session_popup()
    st.stop()

if st.button(UI[LANG]["btn"]):
    if not company_input:
        st.warning("Please select a company from the list first.")
        st.stop()

    st.session_state.usage_count += 1
    counter_box.write(f"Remaining searches today: **{3 - st.session_state.usage_count}/3**")

    with st.spinner("Scouring the web and analyzing..."):
        try:
            script, pos, neg, verd, audio_bytes = analyze_company(company_input, LANG)
            
            # The UI Table Layout
            st.success("Analysis Complete!")
            st.audio(audio_bytes, format="audio/mp3", autoplay=True)
            st.write(script)
            
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                st.subheader(UI[LANG]["neg"])
                st.write(neg)
            with col2:
                st.subheader(UI[LANG]["pos"])
                st.write(pos)
                
            st.markdown("---")
            st.subheader(f"{UI[LANG]['verdict']} **{verd}**")
            
        except Exception as e:
            st.error(f"Error: {e}")
            st.session_state.usage_count -= 1 
            counter_box.write(f"Remaining searches today: **{3 - st.session_state.usage_count}/3**")

# --- INSTANT FEEDBACK POPOVER (BOTTOM OF SCREEN) ---
st.write("---")
with st.popover("💬 Have a suggestion? Click here!"):
    st.write("Notice a bug or want a new feature?")
    p_email = st.text_input("Your Email", key="p_email")
    p_fb = st.text_area("Your Thoughts", key="p_fb")
    if st.button("Send Feedback", key="p_send"):
        if p_email and p_fb:
            save_feedback({"Type": "Manual", "Company": "N/A", "Name": "N/A", "Email": p_email, "Feedback": p_fb})
            st.success("Sent successfully!")
        else:
            st.error("Please fill in all fields.")

