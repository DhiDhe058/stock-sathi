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
from supabase import create_client
from companies import NIFTY_COMPANIES

# --- 1. PAGE CONFIGURATION (MUST BE FIRST) ---
st.set_page_config(page_title="One Minute Scan", page_icon="📈")

# --- 2. SECRETS & AI SETUP ---
try:
    GENAI_API_KEY = st.secrets["GENAI_API_KEY"]
except:
    GENAI_API_KEY = "PASTE_YOUR_FREE_KEY_HERE"

genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel('gemini-3-flash-preview')

if 'usage_count' not in st.session_state:
    st.session_state.usage_count = 0

# --- 3. DATABASE CONNECTION (GOOGLE SHEETS) ---
def save_feedback(data_dict):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="Sheet1")
        new_row = pd.DataFrame([data_dict])
        
        if df.empty:
            updated_df = new_row
        else:
            updated_df = pd.concat([df, new_row], ignore_index=True)
            
        conn.update(worksheet="Sheet1", data=updated_df)
    except Exception as e:
        st.error(f"Could not connect to Google Sheets: {e}")

# --- 4. THE BILINGUAL DICTIONARY ---
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

# --- 5. SIDEBAR AUTHENTICATION ---
if not st.user.is_logged_in:
    st.sidebar.markdown("### 🔒 Unlock More Scans")
    st.sidebar.write("Sign in to bypass the session limit and get 3 scans every 8 hours.")
    st.sidebar.button("Log in with Google", on_click=st.login, args=["google"])
else:
    st.sidebar.write(f"👋 Welcome, **{st.user.email}**!")
    st.sidebar.button("Log out", on_click=st.logout)

# --- 6. THE ANALYZER ---
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

# --- 7. MAIN UI RENDER ---
st.title(UI[LANG]["title"])
st.write(UI[LANG]["desc"])

company_input = st.selectbox(UI[LANG]["select"], [""] + sorted(NIFTY_COMPANIES))

# Show anonymous counter if not logged in
counter_box = st.empty()
if not st.user.is_logged_in:
    counter_box.write(f"Anonymous searches remaining this session: **{3 - st.session_state.usage_count}/3**")

# --- 8. THE SOFT WALL LOGIC ---
if st.button(UI[LANG]["btn"]):
    if not company_input:
        st.warning("Please select a company from the list first.")
    else:
        can_proceed = True 
        
        # Check Limits
        if not st.user.is_logged_in:
            if st.session_state.usage_count >= 3:
                st.error("🛑 You have reached your 3 free anonymous scans!")
                st.warning("Please use the 'Log in with Google' button in the sidebar to continue.")
                can_proceed = False 
            else:
                st.session_state.usage_count += 1
                counter_box.write(f"Anonymous searches remaining this session: **{3 - st.session_state.usage_count}/3**")
        else:
            st.success("Verifying account limits...")
            # (Supabase logic will go here!)

        # Run AI if allowed
        if can_proceed:
            with st.spinner(f"Analyzing {company_input}..."):
                try:
                    final_text, final_audio_bytes = analyze_company(company_input, LANG)
                    st.success("Analysis Complete!")
                    st.audio(final_audio_bytes, format="audio/mpeg", autoplay=False)
                    st.markdown(final_text)
                except Exception as e:
                    st.error(f"Error: {e}")
                    # Refund the scan count if it fails
                    if not st.user.is_logged_in:
                        st.session_state.usage_count -= 1 
                        counter_box.write(f"Anonymous searches remaining this session: **{3 - st.session_state.usage_count}/3**")

# --- 9. PERMANENT FEEDBACK FOOTER ---
st.markdown("---")
with st.expander("💬 Have a suggestion? Click here!"):
    with st.form("permanent_feedback_form"):
        st.write("Notice a bug or want a new feature? Tell us what you want!")
        fb_name = st.text_input("Name (Optional)")
        fb_email = st.text_input("Email (Required)")
        fb_text = st.text_area("Your Feedback (Required)")
        
        submitted = st.form_submit_button("Submit Feedback")
        
        if submitted:
            if fb_email and fb_text:
                save_feedback({"Name": fb_name, "Email": fb_email, "Feedback": fb_text})
                st.success("Thank you! Your feedback has been saved.")
            else:
                st.error("Please provide both an Email and Feedback.")