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
        # MAKE SURE YOUR SHEET URL IS STILL IN YOUR SECRETS OR PASTED HERE
        df = conn.read(worksheet="Sheet1")
        new_row = pd.DataFrame([data_dict])
        
        if df.empty:
            updated_df = new_row
        else:
            updated_df = pd.concat([df, new_row], ignore_index=True)
            
        conn.update(worksheet="Sheet1", data=updated_df)
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
st.set_page_config(page_title="One Minute Scan", page_icon="📈")

is_english = st.toggle("Switch to English / अंग्रेजी में बदलें")
LANG = "EN" if is_english else "HI"

UI = {
    "HI": {
        "title": "📈 One Minute Scan",
        "desc": "नीचे दी गई सूची से कंपनी चुनें और हम तुरंत उसका सारांश देंगे।",
        "select": "कंपनी चुनें (Type to search):",
        "btn": "त्वरित सारांश प्राप्त करें",
        "ai_lang": "simple Hindi",
        "voice": "hi-IN-MadhurNeural",
        "verdict_text": "अंतिम निर्णय"
    },
    "EN": {
        "title": "📈 One Minute Scan",
        "desc": "Select a company from the list below for a quick summary.",
        "select": "Select Company (Type to search):",
        "btn": "Get Quick Summary",
        "ai_lang": "simple English",
        "voice": "en-IN-PrabhatNeural",
        "verdict_text": "End Result"
    }
}

# --- THE ANALYZER (SIMPLIFIED & FOOLPROOF) ---
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

    # THE NEW, BULLETPROOF PROMPT
    prompt = f"""
    Analyze {company_name} using this news: {news_text} and presentation: {pdf_text}.
    Write entirely in {UI[language_code]['ai_lang']}.
    
    Structure your response EXACTLY like this layout below. Do not deviate.
    
    [Write a brief 3-sentence introduction analyzing {company_name}]
    
    ✅ [Good point 1]
    ✅ [Good point 2]
    ✅ [Good point 3]
    
    🚩 [Red flag 1]
    🚩 [Red flag 2]
    🚩 [Red flag 3]
    
    **{UI[language_code]['verdict_text']}: [Choose one: High Growth / Stable Growth / Slow Growth]**
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

    if not summary_text:
        summary_text = "Analysis failed. Please try again."

    # AUDIO FIX: Strip emojis and bold marks so the voice reads it smoothly
    cleaned_text = summary_text.replace("*", "").replace("✅", "").replace("🚩", "").replace("#", "")
    temp_audio_path = f"temp_{company_name.replace(' ', '_')}.mp3"
    
    async def generate_audio():
        communicate = edge_tts.Communicate(cleaned_text, UI[language_code]['voice'])
        await communicate.save(temp_audio_path)
    asyncio.run(generate_audio())
    
    with open(temp_audio_path, "rb") as f:
        audio_bytes = f.read()
    os.remove(temp_audio_path)
    
    return summary_text, audio_bytes

# --- UI RENDER ---
st.title(UI[LANG]["title"])
st.write(UI[LANG]["desc"])

# Dropdown uses the hardcoded list
company_input = st.selectbox(UI[LANG]["select"], [""] + sorted(NIFTY_COMPANIES))

counter_box = st.empty()
counter_box.write(f"Remaining searches today: **{3 - st.session_state.usage_count}/3**")

if st.session_state.usage_count >= 3:
    end_of_session_popup()
    st.stop()

if st.button(UI[LANG]["btn"]):
    if not company_input:
        st.warning("Please select a company from the list first.")
        st.stop()

    st.session_state.usage_count += 1
    counter_box.write(f"Remaining searches today: **{3 - st.session_state.usage_count}/3**")

    with st.spinner(f"Analyzing {company_input}..."):
        try:
            final_text, final_audio_bytes = analyze_company(company_input, LANG)
            
            st.success("Analysis Complete!")
            st.audio(final_audio_bytes, format="audio/mpeg", autoplay=False)
            
            # Print the exact text directly to the screen (No columns, no tables!)
            st.markdown(final_text)
            
        except Exception as e:
            st.error(f"Error: {e}")
            st.session_state.usage_count -= 1 
            counter_box.write(f"Remaining searches today: **{3 - st.session_state.usage_count}/3**")

# --- INSTANT FEEDBACK POPOVER ---
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