import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
from duckduckgo_search import DDGS
import edge_tts
import asyncio
import requests
import io
import os
import time

# --- LOCAL vs LIVE SECURITY ---
try:
    GENAI_API_KEY = st.secrets["GENAI_API_KEY"]
except:
    # PASTE YOUR FREE TIER API KEY HERE JUST FOR LOCAL TESTING
    GENAI_API_KEY = "PASTE_YOUR_FREE_KEY_HERE"

genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel('gemini-3-flash-preview')

if 'usage_count' not in st.session_state:
    st.session_state.usage_count = 0

# --- THE STRICT BOUNCER ---
@st.cache_data(show_spinner=False)
def verify_company_name(input_text):
    prompt = f"""
    You are a strict data validation bot. The user entered this exact text: '{input_text}'. 
    Is this EXACT string the name of a publicly traded Indian company? 
    If it contains conversational words, questions, or extra gibberish (like 'kaun', 'hai', 'tell me about'), it is INVALID. 
    Reply with EXACTLY one word: YES or NO.
    """
    
    for attempt in range(3):
        try:
            response = model.generate_content(prompt)
            return "YES" in response.text.strip().upper()
        except Exception as e:
            if "429" in str(e) or "Quota" in str(e):
                time.sleep(5)  
            else:
                return True 
    return True 

# --- THE ANALYZER WITH AUTO-RETRY ---
@st.cache_data(show_spinner=False)
def analyze_company(company_name):
    ddgs = DDGS()
    
    news_text = "Latest News:\n"
    try:
        news_results = ddgs.news(company_name, timelimit="w", max_results=3)
        for result in news_results:
            news_text += f"- {result['title']}: {result['body']}\n"
    except Exception:
        news_text += "No recent news found.\n"

    pdf_text = ""
    try:
        search_query = f"{company_name} investor presentation filetype:pdf site:bseindia.com"
        pdf_results = ddgs.text(search_query, max_results=1)
        
        if pdf_results and "href" in pdf_results[0]:
            pdf_url = pdf_results[0]["href"]
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(pdf_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                pdf_file = io.BytesIO(response.content)
                reader = PdfReader(pdf_file)
                for page in reader.pages[:10]:
                    pdf_text += page.extract_text() or ""
    except Exception:
        pass 

    if not pdf_text:
        pdf_text = "[System Note: No presentation PDF found. Base analysis on news.]"

    prompt = f"""
    Act as a financial friend to a villager in India. 
    Analyze the company: {company_name}.
    News Context: {news_text}
    Presentation Data: {pdf_text}
    
    1. Start EXACTLY with: "Analyzing [Insert Exact Company Name]. Based on the quarterly result published on [Date or 'recent news']..."
    2. Explain 3 positives and 3 red flags in simple Hindi.
    3. End with Verdict Tag in English: [High Growth], [Stable Growth], or [Slow Growth].
    4. NO asterisks (*), hashes (#), or bullets. Plain text only. Keep under 150 words.
    """
    
    summary_text = ""
    for attempt in range(3):
        try:
            summary_text = model.generate_content(prompt).text
            break 
        except Exception as e:
            if "429" in str(e) or "Quota" in str(e):
                if attempt < 2: 
                    time.sleep(8) 
                else:
                    raise Exception("The AI is currently serving too many users. Please try again in 1 minute.")
            else:
                raise e 

    cleaned_text = summary_text.replace("*", "").replace("#", "").replace("_", "")
    temp_audio_path = f"temp_{company_name.replace(' ', '_')}.mp3"
    
    async def generate_audio():
        communicate = edge_tts.Communicate(cleaned_text, "hi-IN-MadhurNeural")
        await communicate.save(temp_audio_path)
    
    asyncio.run(generate_audio())
    
    with open(temp_audio_path, "rb") as f:
        audio_bytes = f.read()
    os.remove(temp_audio_path)
    
    return summary_text, audio_bytes

# --- THE UI SETUP ---
st.set_page_config(page_title="Stock Sathi", page_icon="📈")
st.title("📈 Stock Sathi")
st.markdown("### Do you want to know about a company/stock?")
st.write("Type the name below and we will get you a quick summary for it, right away.")

counter_box = st.empty()
counter_box.write(f"Remaining searches today: **{3 - st.session_state.usage_count}/3**")

if st.session_state.usage_count >= 3:
    st.error("🔒 You have reached your limit of 3 companies for today. Please come back tomorrow!")
    st.stop()

# Updated UI text to guide the user on ambiguous names
company_input = st.text_input("Enter Company Name (Be specific: e.g., HDFC Bank, ICICI AMC)")

if st.button("Get Quick Summary"):
    if not company_input:
        st.warning("Please enter a company name first.")
        st.stop()

    with st.spinner("Checking company name..."):
        is_valid = verify_company_name(company_input)
        
    if not is_valid:
        st.error("❌ Invalid Input: Please enter a valid Indian stock market company name.")
        st.stop()

    st.session_state.usage_count += 1
    counter_box.write(f"Remaining searches today: **{3 - st.session_state.usage_count}/3**")

    with st.spinner(f"Scouring the web and analyzing {company_input}... this takes about 15-20 seconds."):
        try:
            final_text, final_audio_bytes = analyze_company(company_input)
            st.success("Analysis Complete!")
            st.write(final_text)
            st.subheader("🎧 Listen to Summary")
            st.audio(final_audio_bytes, format="audio/mp3", autoplay=True)
            
        except Exception as e:
            st.error(f"{e}")
            st.session_state.usage_count -= 1 
            counter_box.write(f"Remaining searches today: **{3 - st.session_state.usage_count}/3**")

st.write("---")
st.caption("⚠️ **Disclaimer:** This analysis is generated by AI and may contain errors. It is for educational purposes only and does not constitute financial advice.")