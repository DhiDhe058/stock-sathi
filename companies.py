import pandas as pd

try:
    # 💥 THE BAZOOKA FIX: Read the file directly from the internet, bypassing the server's hard drive!
    # PASTE YOUR GITHUB "RAW" URL HERE:
    csv_url = "https://raw.githubusercontent.com/DhiDhe058/stock-sathi/refs/heads/main/ind_nifty500list.csv" 
    
    df = pd.read_csv(csv_url)
    
    # Find the company column automatically
    company_column = [col for col in df.columns if 'Company' in col][0]
    NIFTY_COMPANIES = df[company_column].dropna().tolist()

except Exception as e:
    NIFTY_COMPANIES = ["Reliance Industries", f"⚠️ URL FETCH FAILED: {str(e)}", "TCS", "HDFC Bank", "ICICI Bank"]