import pandas as pd

try:
    # Make sure this is the exact name of your file!
    file_path = "ind_nifty500list.csv" 
    df = pd.read_csv(file_path)
    
    # Let's be smart: Find ANY column that has the word 'Company' in it, 
    # regardless of hidden spaces or extra words.
    company_column = [col for col in df.columns if 'Company' in col][0]
    
    NIFTY_COMPANIES = df[company_column].dropna().tolist()

except Exception as e:
    # The Trojan Horse: If it crashes, put the EXACT error message inside the dropdown menu!
    NIFTY_COMPANIES = ["Reliance Industries", f"⚠️ BUG FOUND: {str(e)}", "TCS", "HDFC Bank", "ICICI Bank"]