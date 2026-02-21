import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
from duckduckgo_search import DDGS
import edge_tts
import asyncio
import requests
import io
import os

# --- CONFIGURATION ---
GENAI_API_KEY = st.secrets["GENAI_API_KEY"]
genai.configure(api_key=GENAI_API_KEY)
# Using the fast, efficient Flash model
model = genai.GenerativeModel('gemini-3-flash-preview')

# --- THE 3-STRIKE TRACKER (Session State) ---
# Note: For a true production launch, we will upgrade this to Browser Cookies.
# For now, this handles the limit during your active testing session.
if 'usage_count' not in st.session_state:
    st.session_state.usage_count = 0

# --- THE CACHE SYSTEM (Option B) ---
# @st.cache_data tells Streamlit to remember the output of this function.
# If a user types the exact same company name, it skips the heavy lifting!
@st.cache_data(show_spinner=False)
def analyze_company(company_name):
    ddgs = DDGS()
    
    # Step A: Fetch News
    news_text = "Latest News:\n"
    try:
        news_results = ddgs.news(company_name, timelimit="w", max_results=3)
        for result in news_results:
            news_text += f"- {result['title']}: {result['body']}\n"
    except Exception:
        news_text += "No recent news found.\n"

    # Step B: Auto-Fetch PDF from BSE
    pdf_text = ""
    try:
        # The Search Engine Hack
        search_query = f"{company_name} investor presentation filetype:pdf site:bseindia.com"
        pdf_results = ddgs.text(search_query, max_results=1)
        
        if pdf_results and "href" in pdf_results[0]:
            pdf_url = pdf_results[0]["href"]
            # We disguise our script as a standard web browser so BSE doesn't block it
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            response = requests.get(pdf_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                # Read the downloaded PDF directly from memory
                pdf_file = io.BytesIO(response.content)
                reader = PdfReader(pdf_file)
                for page in reader.pages[:10]:
                    pdf_text += page.extract_text() or ""
    except Exception:
        pass # If it fails, we just rely on the news.

    if not pdf_text:
        pdf_text = "[System Note: No presentation PDF found. Base the analysis solely on the news provided.]"

    # Step C: The Upgraded AI Prompt
    prompt = f"""
    Act as a financial friend to a villager in India. 
    Analyze the company: {company_name}.
    
    News Context: {news_text}
    Presentation Data: {pdf_text}
    
    Follow these STRICT instructions:
    1. Start your response EXACTLY with: "Based on the quarterly result published on [Insert Date found in data, or 'recent news' if no date found]..."
    2. Explain the 3 biggest positives and the 3 biggest red flags in simple Hindi.
    3. At the very end, give a Verdict Tag in English: [High Growth], [Stable Growth], or [Slow Growth].
    4. CRITICAL: Do not use any asterisks (*), hashes (#), or bullet points. Write only plain text.
    5. Keep it under 150 words.
    """
    
    ai_response = model.generate_content(prompt)
    summary_text = ai_response.text
    
    # Step D: Audio Generation
    cleaned_text = summary_text.replace("*", "").replace("#", "").replace("_", "")
    # Create a unique audio file name for this company
    audio_path = f"{company_name.replace(' ', '_')}_summary.mp3"
    
    async def generate_audio():
        communicate = edge_tts.Communicate(cleaned_text, "hi-IN-MadhurNeural")
        await communicate.save(audio_path)
    
    asyncio.run(generate_audio())
    
    return summary_text, audio_path

# --- THE UI SETUP ---
st.set_page_config(page_title="Stock Sathi", page_icon="📈")
st.title("📈 Stock Sathi")

# The Custom Welcome Message
st.markdown("### Do you want to know about a company/stock?")
st.write("Type the name below and we will get you a quick summary for it, right away.")

# Check the limit
if st.session_state.usage_count >= 3:
    st.error("🔒 You have reached your limit of 3 companies for today. Please come back tomorrow!")
    st.stop()

st.write(f"Remaining searches today: **{3 - st.session_state.usage_count}/3**")

# --- USER INPUT ---
company_input = st.text_input("Enter Company Name (e.g., Reliance, Zomato)")

if st.button("Get Quick Summary"):
    if not company_input:
        st.warning("Please enter a company name first.")
        st.stop()

    st.session_state.usage_count += 1

    with st.spinner(f"Scouring the web and analyzing {company_input}... this takes about 10 seconds."):
        try:
            # This calls the cached function!
            final_text, final_audio = analyze_company(company_input)
            
            st.success("Analysis Complete!")
            st.write(final_text)
            
            st.subheader("🎧 Listen to Summary")
            st.audio(final_audio, format="audio/mp3", autoplay=True)
            
        except Exception as e:
            st.error(f"Something went wrong while analyzing. Please try another company. Error: {e}")
            # Refund the usage count if it crashes
            st.session_state.usage_count -= 1 

# --- THE LEGAL SHIELD ---
st.write("---")
st.caption("⚠️ **Disclaimer:** This analysis is generated by AI and may contain errors. It is for educational purposes only and does not constitute financial advice. Please verify data and consult a SEBI-registered investment advisor before making any decisions.")