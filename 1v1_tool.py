import streamlit as st
import pandas_ta as ta
from openai import OpenAI
import time
import requests
import gspread
from alpha_vantage.timeseries import TimeSeries
from oauth2client.service_account import ServiceAccountCredentials
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import tempfile
import json
from pydantic import BaseModel
import os 
import re
import anthropic
#from dotenv import load_dotenv
#from curl_cffi import requests as curl_requests
from datetime import datetime, timedelta,date
import pandas as pd
from serpapi import GoogleSearch
from dateutil.relativedelta import relativedelta


#load_dotenv()

api_key = st.secrets["OPENAI_API_KEY"]
google_sheet_url = st.secrets["GOOGLE_SHEET_URL"]
private_key = st.secrets["PRIVATE_KEY"]
project_id = st.secrets["PROJECT_ID"]
private_key_id = st.secrets["PRIVATE_KEY_ID"]
client_email = st.secrets["CLIENT_EMAIL"]
client_id = st.secrets["CLIENT_ID"]
auth_uri = st.secrets["AUTH_URI"]
token_uri = st.secrets["TOKEN_URI"]
auth_provider_x509_cert_url = st.secrets["AUTH_PROVIDER_X509_CERT_URL"]
client_x509_cert_url = st.secrets["CLIENT_X509_CERT_URL"]
universe_domain = st.secrets["UNIVERSE_DOMAIN"]
type_sa = st.secrets["TYPE"]
alpha_vantage_key = st.secrets["ALPHA_VANTAGE_API_KEY"]



client = OpenAI(api_key= api_key)

@st.cache_data(ttl=3600)
def fetch_alpha_vantage_data(ticker, period):
    """Fetch data from Alpha Vantage and filter by period"""
    ts = TimeSeries(key=alpha_vantage_key, output_format='pandas')
    
    try:
        # Get full daily data (we'll filter it later)
        data, meta_data = ts.get_daily(symbol=ticker, outputsize='full')
        data.index = pd.to_datetime(data.index)
        
        # Filter based on selected period
        today = pd.Timestamp.today()
        period_map = {
            "3 Months": 90,
            "6 Months": 180,
            "1 Year": 365
        }
        cutoff_days = period_map.get(period, 365)
        cutoff_date = today - pd.Timedelta(days=cutoff_days)

        filtered_data = data[data.index >= cutoff_date]

        
        #filtered_data = data.last(period_map.get(period, "1Y"))
        
        # Rename columns to match yfinance format
        filtered_data = filtered_data.rename(columns={
            '1. open': 'Open',
            '2. high': 'High',
            '3. low': 'Low',
            '4. close': 'Close',
            '5. volume': 'Volume'
        })
        
        return filtered_data.sort_index()
    
    except Exception as e:
        st.error(f"Alpha Vantage Error: {str(e)}")
        return None



def stock_page():
    #client = OpenAI(api_key=api_key)

    if "run_analysis_complete" not in st.session_state:
        st.session_state["run_analysis_complete"] = False

# Main application
    #st.set_page_config(page_title="Stock Market Analysis", layout="wide", page_icon="📈")

    # Sidebar with interactive options
    with st.sidebar:
        st.title("Market Analysis Dashboard")
        st.markdown("Analyze stock trends using advanced technical indicators powered by AI.")
        
        # Ticker Inpu
        st.subheader("Company 1")
        ticker = st.text_input(" Enter Ticker Symbol", "", help="Example: 'AAPL' for Apple Inc.").strip().upper()
        company = st.text_input(" Enter Full Company Name", "", help="Example: 'Apple Inc.'")

        st.subheader("Company 2")
        ticker2 = st.text_input(" Enter Ticker Symbol", "", help="Example: 'MSFT' for Microsoft.").strip().upper()
        company2 = st.text_input(" Enter Full Company Name", "", help="Example: 'Microsoft.'")
        
        # Timeframe Selection
        st.subheader("Select Timeframe for Analysis")
        timeframe = st.radio(
            "Choose timeframe:",
            ( "3 Months", "6 Months", "1 Year"),
            index=2,
            help="Select the period of historical data for the stock analysis"
        )
        
        # Analysis Type Selection
        st.subheader("Analysis Options")
        technical_analysis = st.checkbox("Technical Analysis", help="Select to run technical analysis indicators")
        news_and_events = st.checkbox("News and Events", help="Get recent news and event analysis for the company")
        fundamental_analysis = st.checkbox("Fundamental Analysis", help="Select to upload a file for fundamental analysis")

        selected_types = [
            technical_analysis, 
            fundamental_analysis, 
            news_and_events
        ]
        selected_count = sum(selected_types)

        if technical_analysis:
            weight_choice = st.radio(
            "Weighting Style",
            ("Short Term", "Long Term","Default"),
            index=1,
            help="Choose analysis style for technical indicators"
        )

        uploaded_file = None
        uploaded_file2 = None

        if fundamental_analysis:
            uploaded_file = st.file_uploader("Upload 1st PDF file for Fundamental Analysis", type="pdf")
            uploaded_file2 = st.file_uploader("Upload 2nd PDF file for Fundamental Analysis", type="pdf")

        if selected_count > 1:
            st.subheader("Analysis Weightings")
            default_weights = {
                "Technical": 0.33,
                "Fundamental": 0.33,
                "News": 0.34
            }
            tech_weight = st.slider("Technical Analysis Weight", 0.0, 1.0, default_weights["Technical"])
            fund_weight = st.slider("Fundamental Analysis Weight", 0.0, 1.0, default_weights["Fundamental"])
            news_weight = st.slider("News Analysis Weight", 0.0, 1.0, default_weights["News"])
            total = tech_weight + fund_weight + news_weight
            # Normalize to sum to 1
            if total > 0:
                tech_weight /= total
                fund_weight /= total
                news_weight /= total
            else:
                tech_weight = fund_weight = news_weight = 1/3
        else:
            # If only one is selected, set weights accordingly
            tech_weight = 1.0 if technical_analysis else 0.0
            fund_weight = 1.0 if fundamental_analysis else 0.0
            news_weight = 1.0 if news_and_events else 0.0
        
        # Run Button with styled alert text
        run_button = st.button("Run Analysis")
        st.markdown("---")
        st.info("Click 'Run Analysis' after selecting options to start.")

       



    col1, col2 = st.columns([3, 1])

    
    st.title("Stock Market Analysis with AI-Powered Insights")
    st.markdown("**Gain actionable insights into stock trends with advanced indicators and AI interpretations.**")

    progress_bar = st.progress(0)
    status_text = st.empty()

    if run_button and ticker:
        
        try:
            status_text.text("Fetching data from Alpha Vantage...")
            progress_bar.progress(30)
            
            # Fetch data using Alpha Vantage
            data = fetch_alpha_vantage_data(ticker, timeframe)
            data2 = fetch_alpha_vantage_data(ticker2, timeframe)

            if data is not None and data2 is not None:
                progress_bar.progress(100)
                status_text.text("Data loaded successfully.")
                
                # Show a sample of the data
                #st.subheader(f"{ticker.upper()} Price Data")
                #st.dataframe(data)
                
                # Rest of your analysis code can go here
                # (technical indicators, AI analysis, etc.)
                
            else:
                progress_bar.progress(0)
            
        except Exception as e:
            st.error(f"Error in analysis pipeline: {e}")
            progress_bar.progress(0)

        
    # Create impersonated session using curl_cffi
        #session = curl_requests.Session(impersonate="chrome")
        #session.headers.update({
        #"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        #"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        #"Accept-Language": "en-US,en;q=0.5",
        #"Referer": "https://www.google.com/",
    #})

    # Create yfinance Ticker object with session
        #stock = yf.Ticker(str(ticker))
    
        # Determine period from timeframe selection
        #period_map = {
            #"3 Months": "3mo",
            #"6 Months": "6mo",
            #"1 Year": "1y"
       # }
        #selected_period = period_map.get(timeframe, "3mo")
    
        # Fetch historical price data
        #try:
            #status_text.text("Fetching data...")
            #progress_bar.progress(30)
    
            #data = stock.history(period=selected_period, interval="1d",session = session)
    
            #progress_bar.progress(100)
           # status_text.text("Data loaded successfully.")
    
            # Show a sample of the data
            #st.subheader(f"{ticker.upper()} Price Data")
            #st.dataframe(data)
    
        #except Exception as e:
            #st.error(f"Error fetching data: {e}")
            #progress_bar.progress(0)
        

        
        if not technical_analysis and not news_and_events and not fundamental_analysis:
            st.warning("Please select at least one analysis type to proceed.")
        if data.empty:
            st.warning(f"No data available for {ticker}. Please check the ticker symbol and try again.")
        if not company:
            st.warning(f" Please add Name of company.")
        elif technical_analysis:
            
            if technical_analysis and not news_and_events and not fundamental_analysis:
                with st.expander("Downloading Data... Click to View Progress"):
                    update_progress(progress_bar, 50, 50, "Analyzing...")
                    results, recent_data, availability,score,weighted_score = calculate_technical_indicators(data,ticker,weight_choice=weight_choice)
                    results2, recent_data2, availability2,score2,weighted_score2 = calculate_technical_indicators(data2,ticker2,weight_choice=weight_choice)
                    update_progress(progress_bar, 100, 100, "Finalising...")
                    bd_result = results["bd_result"]
                    sma_result = results["sma_result"]
                    rsi_result = results["rsi_result"]
                    macd_result = results["macd_result"]
                    obv_result = results["obv_result"]
                    adx_result = results["adx_result"]

                    bd_result2 = results2["bd_result"]
                    sma_result2 = results2["sma_result"]
                    rsi_result2 = results2["rsi_result"]
                    macd_result2 = results2["macd_result"]
                    obv_result2 = results2["obv_result"]
                    adx_result2 = results2["adx_result"]
                    #summary = SUMMARY(ticker, bd_result, sma_result, rsi_result, macd_result, obv_result, adx_result,weighted_score,weight_choice)
                    #update_progress(progress_bar, 100, 100, "Analysis Complete...")
                    
                sma_available = availability['sma_available']
                rsi_available = availability['rsi_available']
                macd_available = availability['macd_available']
                obv_available = availability['obv_available']
                adx_available = availability['adx_available']
                bbands_available = availability['bbands_available']

                # bd_result = results["bd_result"]
                # sma_result = results["sma_result"]
                # rsi_result = results["rsi_result"]
                # macd_result = results["macd_result"]
                # obv_result = results["obv_result"]
                # adx_result = results["adx_result"]


            
                #st.subheader(f"Summary for {ticker}")
                #st.write(summary)


                st.session_state["run_analysis_complete"] = True

                

                #recent_data.reset_index(inplace=True)
                #recent_data['Date'] = recent_data['date'].astype(str)

                gathered_data = {
                    "Ticker": ticker,
                    "Company": company,
                    "Company 2": company2,
                    "Timeframe": timeframe,
                    f"data for {company} ": recent_data.to_dict(orient="records"),
                    f"data for {company2} ": recent_data2.to_dict(orient="records"),
                    f"Weighted Score for {company}": weighted_score,
                    f"Weighted Score for {company2}": weighted_score2,
                    "Position_type":weight_choice,
                    "Results": {
                        #"Summary": summary if 'summary' in locals() else "",
                        "SMA Results": sma_result if 'sma_result' in locals() else "",
                        "RSI Results": rsi_result if 'rsi_result' in locals() else "",
                        "MACD Results": macd_result if 'macd_result' in locals() else "",
                        "OBV Results": obv_result if 'obv_result' in locals() else "",
                        "BD Results": bd_result if 'obv_result' in locals() else "",
                        "ADX Results": adx_result if 'adx_result' in locals() else "",
                        "SMA Results2": sma_result2 if 'sma_result' in locals() else "",
                        "RSI Results2": rsi_result2 if 'rsi_result' in locals() else "",
                        "MACD Results2": macd_result2 if 'macd_result' in locals() else "",
                        "OBV Results2": obv_result2 if 'obv_result' in locals() else "",
                        "BD Results2": bd_result2 if 'bd_result' in locals() else "",
                        "ADX Results2": adx_result2 if 'adx_result' in locals() else ""
                    }
                }

                summary = SUMMARY2(gathered_data)
                text_ovr = clean_html_response(summary)
                st.components.v1.html(text_ovr, height=700, scrolling=True)


                st.session_state["gathered_data"] = gathered_data
                st.session_state["analysis_complete"] = True  # Mark analysis as complete
                st.success("Stock analysis completed! You can now proceed to the AI Chatbot.")

                # Use an expander to show detailed analysis for each indicator
                # if bbands_available:
                #     with st.expander("View Detailed Analysis for Bollinger Bands"):
                #         fig_bbands = plot_bbands(data)
                #         st.plotly_chart(fig_bbands)
                #         st.write(bd_result)  # Display Bollinger Bands result or interpretation

                # if sma_available:
                #     with st.expander("View Detailed Analysis for SMA"):
                #         fig_sma = plot_sma(data)
                #         st.plotly_chart(fig_sma)
                #         st.write(sma_result)  # Display SMA result or interpretation

                # if rsi_available:
                #     with st.expander("View Detailed Analysis for RSI"):
                #         fig_rsi = plot_rsi(data)
                #         st.plotly_chart(fig_rsi)
                #         st.write(rsi_result)  # Display RSI result or interpretation

                # if macd_available:
                #     with st.expander("View Detailed Analysis for MACD"):
                #         fig_macd = plot_macd(data)
                #         st.plotly_chart(fig_macd)
                #         st.write(macd_result)  # Display MACD result or interpretation

                # if obv_available:
                #     with st.expander("View Detailed Analysis for OBV"):
                #         fig_obv = plot_obv(data)
                #         st.plotly_chart(fig_obv)
                #         st.write(obv_result)  # Display OBV result or interpretation

                # if adx_available:
                #     with st.expander("View Detailed Analysis for ADX"):
                #         fig_adx = plot_adx(data)
                #         st.plotly_chart(fig_adx)
                #         st.write(adx_result)  # Display ADX result or interpretation
                
                st.download_button(
                    label="Download as HTML",
                    data=text_ovr,
                    file_name="stock_analysis_summary.html",
                    mime="text/html"
                )

                if st.button("Run Another Stock"):
                    analysis_complete = False
                    st.session_state.technical_analysis = False
                    st.session_state.news_and_events = False
                    st.session_state["1_month"] = False
                    st.session_state["3_months"] = False
                    st.session_state["6_months"] = False
                    st.session_state["1_year"] = False
                    st.experimental_rerun() 


            if technical_analysis and news_and_events and not fundamental_analysis:
                with st.expander("Downloading Data... Click to View Progress"):
                    update_progress(progress_bar, 15, 15, "Analyzing...")
                    results, recent_data, availability,score,weighted_score = calculate_technical_indicators(data,ticker,weight_choice=weight_choice)
                    results2, recent_data2, availability2,score2,weighted_score2 = calculate_technical_indicators(data,ticker,weight_choice=weight_choice)
                    bd_result = results["bd_result"]
                    sma_result = results["sma_result"]
                    rsi_result = results["rsi_result"]
                    macd_result = results["macd_result"]
                    obv_result = results["obv_result"]
                    adx_result = results["adx_result"]

                    bd_result2 = results2["bd_result"]
                    sma_result2 = results2["sma_result"]
                    rsi_result2 = results2["rsi_result"]
                    macd_result2 = results2["macd_result"]
                    obv_result2 = results2["obv_result"]
                    adx_result2 = results2["adx_result"]


                    summary1 = SUMMARY(ticker, bd_result, sma_result, rsi_result, macd_result, obv_result, adx_result,weighted_score,weight_choice)
                    summary2 = SUMMARY(ticker2, bd_result2, sma_result2, rsi_result2, macd_result2, obv_result2, adx_result2,weighted_score2,weight_choice)
                    update_progress(progress_bar, 35, 35, "Technical Analysis complete!")
                    update_progress(progress_bar, 45, 45, "Gathering News Data...")    
                    txt_summary = generate_company_news_message(company, timeframe)
                    txt_summary2 = generate_company_news_message(company2, timeframe)
                    update_progress(progress_bar, 75, 75, "Analysing News Data...")
                    txt_summary = format_news(txt_summary)
                    txt_ovr = txt_conclusion(txt_summary,company)

                    txt_summary2 = format_news(txt_summary2)
                    txt_ovr2 = txt_conclusion(txt_summary2,company2)
                    update_progress(progress_bar, 85, 85, "Finalising...")
                    
                

                sma_available = availability['sma_available']
                rsi_available = availability['rsi_available']
                macd_available = availability['macd_available']
                obv_available = availability['obv_available']
                adx_available = availability['adx_available']
                bbands_available = availability['bbands_available']



            
             
                # st.subheader(f"News and Events Analysis and Technical Analysis for {ticker} over the past {timeframe}")
                # text = convert_to_raw_text(txt_summary)
                # st.write(text)
                # st.subheader("Technical Analysis Summary")
                # st.write(summary)
                # st.subheader("Overall Summary")
                # text_ovr_s = convert_to_raw_text(ovr_summary)
                # st.write(text_ovr_s)

                
                

                st.session_state["run_analysis_complete"] = True

                gathered_data = {
                    "Ticker": ticker,
                    "Company": company,
                    "Timeframe": timeframe,
                    f"Technical Analysis for {company} ": summary1,
                    f"Technical Analysis for {company2} ": summary2,
                    f"News and Events Overall for {company}": txt_ovr,
                    f"News and Events Overall for {company2}": txt_ovr2,
                    f"data for {company} ": recent_data.to_dict(orient="records"),
                    f"data for {company2}": recent_data2.to_dict(orient="records"),
                    f"Weighted Score for {company}": weighted_score,
                    f"Weighted Score for {company2}": weighted_score2,
                    "UserSelectedWeights":{
                        "Technical Analysis Weight": tech_weight,
                        "Fundamental Analysis Weight":fund_weight,
                        "News and Events":news_weight
                    },
                    "Results": {
                        #"Summary": summary if 'summary' in locals() else "",
                        "SMA Results": sma_result if 'sma_result' in locals() else "",
                        "RSI Results": rsi_result if 'rsi_result' in locals() else "",
                        "MACD Results": macd_result if 'macd_result' in locals() else "",
                        "OBV Results": obv_result if 'obv_result' in locals() else "",
                        "BD Results": bd_result if 'bd_result' in locals() else "",
                        "ADX Results": adx_result if 'adx_result' in locals() else "",
                        "SMA Results2": sma_result2 if 'sma_result2' in locals() else "",
                        "RSI Results2": rsi_result2 if 'rsi_result2' in locals() else "",
                        "MACD Results2": macd_result2 if 'macd_result2' in locals() else "",
                        "OBV Results2": obv_result2 if 'obv_result2' in locals() else "",
                        "BD Results2": bd_result2 if 'bd_result2' in locals() else "",
                        "ADX Results2": adx_result2 if 'adx_result2' in locals() else ""
                    }
                }

                update_progress(progress_bar, 100, 100, "Finalising...")
                ovr_summary = merge_news_and_technical_analysis_summary(gathered_data)

                text_ovr = clean_html_response(ovr_summary)
                st.components.v1.html(text_ovr, height=700, scrolling=True)

                st.session_state["gathered_data"] = gathered_data
                st.session_state["analysis_complete"] = True  # Mark analysis as complete
                st.success("Stock analysis completed! You can now proceed to the AI Chatbot.")

                # Use an expander to show detailed analysis for each indicator
                # if bbands_available:
                #     with st.expander("View Detailed Analysis for Bollinger Bands"):
                #         fig_bbands = plot_bbands(data)
                #         st.plotly_chart(fig_bbands)
                #         st.write(bd_result)  # Display Bollinger Bands result or interpretation

                # if sma_available:
                #     with st.expander("View Detailed Analysis for SMA"):
                #         fig_sma = plot_sma(data)
                #         st.plotly_chart(fig_sma)
                #         st.write(sma_result)  # Display SMA result or interpretation

                # if rsi_available:
                #     with st.expander("View Detailed Analysis for RSI"):
                #         fig_rsi = plot_rsi(data)
                #         st.plotly_chart(fig_rsi)
                #         st.write(rsi_result)  # Display RSI result or interpretation

                # if macd_available:
                #     with st.expander("View Detailed Analysis for MACD"):
                #         fig_macd = plot_macd(data)
                #         st.plotly_chart(fig_macd)
                #         st.write(macd_result)  # Display MACD result or interpretation

                # if obv_available:
                #     with st.expander("View Detailed Analysis for OBV"):
                #         fig_obv = plot_obv(data)
                #         st.plotly_chart(fig_obv)
                #         st.write(obv_result)  # Display OBV result or interpretation

                # if adx_available:
                #     with st.expander("View Detailed Analysis for ADX"):
                #         fig_adx = plot_adx(data)
                #         st.plotly_chart(fig_adx)
                #         st.write(adx_result)  # Display ADX result or interpretation
                
                st.download_button(
                    label="Download as HTML",
                    data=text_ovr,
                    file_name="stock_analysis_summary.html",
                    mime="text/html"
                )

                if st.button("Run Another Stock"):
                    analysis_complete = False
                    st.session_state.technical_analysis = False
                    st.session_state.news_and_events = False
                    st.session_state["1_month"] = False
                    st.session_state["3_months"] = False
                    st.session_state["6_months"] = False
                    st.session_state["1_year"] = False
                    st.experimental_rerun() 

            if technical_analysis and fundamental_analysis and not news_and_events:
                with st.expander("Downloading Data... Click to View Progress"):
                    update_progress(progress_bar, 15, 15, "Analyzing...")
                    results, recent_data, availability,score,weighted_score = calculate_technical_indicators(data,ticker,weight_choice=weight_choice)
                    results2, recent_data2, availability2,score2,weighted_score2 = calculate_technical_indicators(data2,ticker2,weight_choice=weight_choice)
                    bd_result = results["bd_result"]
                    sma_result = results["sma_result"]
                    rsi_result = results["rsi_result"]
                    macd_result = results["macd_result"]
                    obv_result = results["obv_result"]
                    adx_result = results["adx_result"]
                    
                    bd_result2 = results2["bd_result"]
                    sma_result2 = results2["sma_result"]
                    rsi_result2 = results2["rsi_result"]
                    macd_result2 = results2["macd_result"]
                    obv_result2 = results2["obv_result"]
                    adx_result2 = results2["adx_result"]


                    summary1 = SUMMARY(ticker, bd_result, sma_result, rsi_result, macd_result, obv_result, adx_result,weighted_score,weight_choice)
                    summary2 = SUMMARY(ticker2, bd_result2, sma_result2, rsi_result2, macd_result2, obv_result2, adx_result2,weighted_score2,weight_choice)
                    update_progress(progress_bar, 35, 35, "Technical Analysis complete!")
                    file_content = uploaded_file
                    file_name = uploaded_file.name

                    file_content2 = uploaded_file2
                    file_name2 = uploaded_file2.name
                    update_progress(progress_bar, 50, 50, "Analysing Financial Information...")  
                    fa_summary = FUNDAMENTAL_ANALYSIS(file_content, company, file_name)
                    fa_summary2 = FUNDAMENTAL_ANALYSIS(file_content2, company2, file_name2)
                    update_progress(progress_bar, 80, 80, "Finalising...")  
                    

                

                sma_available = availability['sma_available']
                rsi_available = availability['rsi_available']
                macd_available = availability['macd_available']
                obv_available = availability['obv_available']
                adx_available = availability['adx_available']
                bbands_available = availability['bbands_available']

                #text_ovr = clean_html_response(fa_ta_summary)
                #st.components.v1.html(text_ovr, height=700, scrolling=True)
                #text_fa = convert_to_raw_text(fa_ta_summary)
                #st.write(text_fa)

                st.session_state["run_analysis_complete"] = True

                gathered_data = {
                    f"Ticker for {company}": ticker,
                    f"Ticker for {company2}": ticker2,
                    "Timeframe": timeframe,
                    f"Technical Analysis for {company}": summary1,
                    f"Technical Analysis for {company2}": summary2,
                    f"Fundamental Analysis for {company}": fa_summary,
                    f"Fundamental Analysis for {company2}": fa_summary2,
                    f"Data for {company}": recent_data.to_dict(orient="records"),
                    f"Data for {company2}": recent_data2.to_dict(orient="records"),
                    "UserSelectedWeights":{
                        "Technical Analysis Weight": tech_weight,
                        "Fundamental Analysis Weight":fund_weight
                    },
                    "Results": {
                        #"Summary": summary if 'summary' in locals() else "",
                        "SMA Results": sma_result if 'sma_result' in locals() else "",
                        "RSI Results": rsi_result if 'rsi_result' in locals() else "",
                        "MACD Results": macd_result if 'macd_result' in locals() else "",
                        "OBV Results": obv_result if 'obv_result' in locals() else "",
                        "BD Results": bd_result if 'bd_result' in locals() else "",
                        "ADX Results": adx_result if 'adx_result' in locals() else "",
                        "SMA Results2": sma_result2 if 'sma_result2' in locals() else "",
                        "RSI Results2": rsi_result2 if 'rsi_result2' in locals() else "",
                        "MACD Results2": macd_result2 if 'macd_result2' in locals() else "",
                        "OBV Results2": obv_result2 if 'obv_result2' in locals() else "",
                        "BD Results2": bd_result2 if 'bd_result2' in locals() else "",
                        "ADX Results2": adx_result2 if 'adx_result2' in locals() else ""
                    }
                }

                fa_ta_summary = merge_ta_fa_summary(gathered_data)

                text_ovr = clean_html_response(fa_ta_summary)
                st.components.v1.html(text_ovr, height=700, scrolling=True)

                st.session_state["gathered_data"] = gathered_data
                st.session_state["analysis_complete"] = True  # Mark analysis as complete
                st.success("Stock analysis completed! You can now proceed to the AI Chatbot.")

                st.download_button(
                    label="Download as HTML",
                    data=text_ovr,
                    file_name="stock_analysis_summary.html",
                    mime="text/html"
                )

                if st.button("Run Another Stock"):
                    analysis_complete = False
                    st.session_state.technical_analysis = False
                    st.session_state.news_and_events = False
                    st.session_state["1_month"] = False
                    st.session_state["3_months"] = False
                    st.session_state["6_months"] = False
                    st.session_state["1_year"] = False
                    st.experimental_rerun() 
            
            if technical_analysis and fundamental_analysis and news_and_events:
                with st.expander("Downloading Data... Click to View Progress"):
                    update_progress(progress_bar, 15, 15, "Analyzing...")
                    results, recent_data, availability,score,weighted_score  = calculate_technical_indicators(data,ticker)
                    bd_result = results["bd_result"]
                    sma_result = results["sma_result"]
                    rsi_result = results["rsi_result"]
                    macd_result = results["macd_result"]
                    obv_result = results["obv_result"]
                    adx_result = results["adx_result"]
                    summary = SUMMARY(ticker, bd_result, sma_result, rsi_result, macd_result, obv_result, adx_result,weighted_score,weight_choice)
                    update_progress(progress_bar, 35, 35, "Technical Analysis complete!")
                    update_progress(progress_bar, 45, 45, "Gathering News Data...")    
                    txt_summary = generate_company_news_message(company, timeframe)
                    update_progress(progress_bar, 75, 75, "Analysing News Data...")
                    #text = convert_to_raw_text(txt_summary)
                    txt_summary = format_news(txt_summary)
                    txt_ovr = txt_conclusion(txt_summary,company)
                    update_progress(progress_bar, 80, 80, "Analysing Financial Information...")  
                    file_content = uploaded_file
                    file_name = uploaded_file.name
                    fa_summary = FUNDAMENTAL_ANALYSIS(file_content, company, file_name)
                    update_progress(progress_bar, 90, 90, "Finalising...")  
                    #fa_ta_na_summary = merge_ta_fa_na_summary(fa_summary,summary,txt_ovr)
                   
                    update_progress(progress_bar, 100, 100, "Analysis Complete...")  
                
                

                sma_available = availability['sma_available']
                rsi_available = availability['rsi_available']
                macd_available = availability['macd_available']
                obv_available = availability['obv_available']
                adx_available = availability['adx_available']
                bbands_available = availability['bbands_available']
                
                
                #text_ovr_s = convert_to_raw_text(fa_ta_na_summary)
                #st.write(text_ovr_s)

                st.session_state["run_analysis_complete"] = True

                gathered_data = {
                    "Ticker": ticker,
                    "Company": company,
                    "Timeframe": timeframe,
                    "Technical Analysis": summary,
                    "Fundamental Analysis": fa_summary,
                    "News and Events Overall": txt_ovr,
                    "News and Events Summary": txt_summary,
                    "data": recent_data.to_dict(orient="records"),
                    "UserSelectedWeights":{
                        "Technical Analysis Weight": tech_weight,
                        "Fundamental Analysis Weight":fund_weight,
                        "News and Events":news_weight
                    },
                    "Results": {
                        #"Summary": summary if 'summary' in locals() else "",
                        #"Fundamental Analysis & Technical Analysis & News": fa_ta_na_summary if 'fa_ta_summary' in locals() else "",
                        "SMA Results": sma_result if 'sma_result' in locals() else "",
                        "RSI Results": rsi_result if 'rsi_result' in locals() else "",
                        "MACD Results": macd_result if 'macd_result' in locals() else "",
                        "OBV Results": obv_result if 'obv_result' in locals() else "",
                        "ADX Results": adx_result if 'adx_result' in locals() else "",
                    }
                }

                html_text= generate_investment_analysis(gathered_data)
                html_output = clean_html_response(html_text)
                st.components.v1.html(html_output, height=700, scrolling=True)
                
                st.session_state["gathered_data"] = gathered_data
                st.session_state["analysis_complete"] = True  # Mark analysis as complete
                st.success("Stock analysis completed! You can now proceed to the AI Chatbot.")

                st.download_button(
                    label="Download as HTML",
                    data=text_ovr,
                    file_name="stock_analysis_summary.html",
                    mime="text/html"
                )

                if st.button("Run Another Stock"):
                    analysis_complete = False
                    st.session_state.technical_analysis = False
                    st.session_state.news_and_events = False
                    st.session_state["1_month"] = False
                    st.session_state["3_months"] = False
                    st.session_state["6_months"] = False
                    st.session_state["1_year"] = False
                    st.experimental_rerun() 



        if news_and_events and not technical_analysis and not fundamental_analysis:
            with st.expander("Downloading Data"):
                update_progress(progress_bar, 30, 30, "Gathering News Data...")    
                txt_summary = generate_company_news_message(company, timeframe)
                update_progress(progress_bar, 50, 50, "Analysing News Data...")
                txt_summary = format_news(txt_summary)
               
                    
            
            #text = convert_to_raw_text(txt_summary)
            #text_ovr = convert_to_raw_text(txt_ovr)
          
            #st.write(text)
            #st.write(text_ovr)

            st.session_state["run_analysis_complete"] = True

            gathered_data = {
                "Ticker": ticker,
                "Company": company,
                "Timeframe": timeframe,
                "News and Events Summary": txt_summary,
            }

            txt_ovr = txt_conclusion2(gathered_data)
            text_ovr = clean_html_response(txt_ovr)
            st.components.v1.html(text_ovr, height=700, scrolling=True)


            st.session_state["gathered_data"] = gathered_data
            st.session_state["analysis_complete"] = True  # Mark analysis as complete
            st.success("Stock analysis completed! You can now proceed to the AI Chatbot.")

            st.download_button(
                label="Download as HTML",
                data=text_ovr,
                file_name="stock_analysis_summary.html",
                mime="text/html"
            )

            if st.button("Run Another Stock"):
                    analysis_complete = False
                    st.session_state.technical_analysis = False
                    st.session_state.news_and_events = False
                    st.session_state["1_month"] = False
                    st.session_state["3_months"] = False
                    st.session_state["6_months"] = False
                    st.session_state["1_year"] = False
                    st.experimental_rerun() 

        if news_and_events and fundamental_analysis and not technical_analysis: 
                with st.expander("Downloading Data"):
                    update_progress(progress_bar, 25, 25, "Gathering News Data...")    
                    txt_summary = generate_company_news_message(company, timeframe)
                    update_progress(progress_bar, 35, 35, "Analysing News Data...")
                    text = convert_to_raw_text(txt_summary)
                    txt_summary = format_news(text)
                    txt_ovr = txt_conclusion(txt_summary,company)
                    update_progress(progress_bar, 45, 45, "Finalising News Analysis...")
                    file_content = uploaded_file
                    file_name = uploaded_file.name
                    update_progress(progress_bar, 60, 60, "Starting Fundamental Analysis...")
                    fa_summary = FUNDAMENTAL_ANALYSIS(file_content, company, file_name)
                    update_progress(progress_bar, 80, 80, "Finalising Analysis...")
                    fa_txt_summary = fa_summary_and_news_summary(fa_summary,txt_ovr)
                    update_progress(progress_bar, 100, 100, "Analysis Complete...")
                
                
                #text_ovr_t = convert_to_raw_text(fa_txt_summary)
                #st.write(text_ovr_t)

                text_ovr = clean_html_response(fa_txt_summary)
                st.components.v1.html(text_ovr, height=700, scrolling=True)

                st.session_state["run_analysis_complete"] = True

                gathered_data = {
                    "Ticker": ticker,
                    "Company": company,
                    "Timeframe": timeframe,
                    "Technical Analysis": technical_analysis,
                    "News and Events Overall": txt_ovr,
                    "News and Events Summary": txt_summary,
                    "Fundamental Analysis": fundamental_analysis,
                    "Results": {
                        "Summary": summary if 'summary' in locals() else "",
                        "Fundamental Analysis & News": fa_txt_summary if 'fa_txt_summary' in locals() else "",
                        "SMA Results": sma_result if 'sma_result' in locals() else "",
                        "RSI Results": rsi_result if 'rsi_result' in locals() else "",
                        "MACD Results": macd_result if 'macd_result' in locals() else "",
                        "OBV Results": obv_result if 'obv_result' in locals() else "",
                        "ADX Results": adx_result if 'adx_result' in locals() else "",
                        "Fundamental Analysis": fa_summary if 'fa_summary' in locals() else ""

                    }
                }
                st.session_state["gathered_data"] = gathered_data
                st.session_state["analysis_complete"] = True  # Mark analysis as complete
                st.success("Stock analysis completed! You can now proceed to the AI Chatbot.")

                st.download_button(
                    label="Download as HTML",
                    data=text_ovr,
                    file_name="stock_analysis_summary.html",
                    mime="text/html"
                )

                if st.button("Run Another Stock"):
                    analysis_complete = False
                    st.session_state.technical_analysis = False
                    st.session_state.news_and_events = False
                    st.session_state["1_month"] = False
                    st.session_state["3_months"] = False
                    st.session_state["6_months"] = False
                    st.session_state["1_year"] = False
                    st.experimental_rerun() 

                

        if fundamental_analysis and not technical_analysis and not news_and_events:
            with st.expander("Downloading Data"): 
                update_progress(progress_bar, 25, 25, "Analysis Started...")  
                file_content = uploaded_file
                file_name = uploaded_file.name
                update_progress(progress_bar, 50, 50, "Analysing Financial Information...")  
                fa_summary = FUNDAMENTAL_ANALYSIS(file_content, company, file_name)
                update_progress(progress_bar, 100, 100, "Analysing Financial Information...")  
        
            #text_fs = convert_to_raw_text(fa_summary)
            #st.write(text_fs)

            text_ovr = clean_html_response(fa_summary)
            st.components.v1.html(text_ovr, height=700, scrolling=True)


            st.session_state["run_analysis_complete"] = True

            gathered_data = {
                "Ticker": ticker,
                "Company": company,
                "Timeframe": timeframe,
                "Technical Analysis": technical_analysis,
                "Fundamental Analysis": fundamental_analysis,
                "Results": {
                    "Summary": summary if 'summary' in locals() else "",
                    "Fundamental Analysis & News": fa_txt_summary if 'fa_txt_summary' in locals() else "",
                    "SMA Results": sma_result if 'sma_result' in locals() else "",
                    "RSI Results": rsi_result if 'rsi_result' in locals() else "",
                    "MACD Results": macd_result if 'macd_result' in locals() else "",
                    "OBV Results": obv_result if 'obv_result' in locals() else "",
                    "ADX Results": adx_result if 'adx_result' in locals() else "",
                    "Fundamental Analysis": fa_summary if 'fa_summary' in locals() else ""

                }
            }
            st.session_state["gathered_data"] = gathered_data
            st.session_state["analysis_complete"] = True  # Mark analysis as complete
            st.success("Stock analysis completed! You can now proceed to the AI Chatbot.")

            st.download_button(
                label="Download as HTML",
                data=text_ovr,
                file_name="stock_analysis_summary.html",
                mime="text/html"
            )

            if st.button("Run Another Stock"):
                        analysis_complete = False
                        st.session_state.technical_analysis = False
                        st.session_state.news_and_events = False
                        st.session_state["1_month"] = False
                        st.session_state["3_months"] = False
                        st.session_state["6_months"] = False
                        st.session_state["1_year"] = False
                        st.experimental_rerun() 


def convert_to_raw_text(text):
    # Remove markdown headers (e.g., ###, ##, #)
    text = re.sub(r'\$', '', text)

    return text

def generate_investment_analysis(gathered_data):
    today = date.today()
    formatted = today.strftime('%Y-%m-%d')

    
    system_prompt = """
    You are an AI model designed to provide technical, fundamental, and news/events-based analysis to deliver actionable, long-term investment insights. Your role is to integrate financial health, competitive positioning, market trends, technical indicators, and relevant news/events into cohesive, data-driven recommendations for strategic, long-term investment strategies.

    The user will provide a JSON object containing all the data needed for analysis, including:
    - Ticker: The stock ticker symbol
    - Company: The company name
    - Timeframe: The analysis timeframe
    - Technical Analysis: Summary of technical analysis
    - Fundamental Analysis: Summary of fundamental analysis
    - News data: News summaries for the company and related companies/sectors
    - Results: Technical indicator results (Summary, SMA, RSI, MACD, OBV, ADX)
    - UserSelectedWeights: An object containing the user-selected weights for Technical, Fundamental, and News analyses, with each value between 0 and 1 (all weights sum to 1). Example:
    {
        "Technical Analysis": 0.4,
        "Fundamental Analysis": 0.4,
        "News and Events": 0.2
    }

    You must parse this JSON data and use it to create a comprehensive investment report formatted as HTML.

    Follow this HTML template exactly, replacing the placeholder content with information derived from the JSON data:

    ```html
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Comprehensive Investment Analysis</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1200px;
                margin: 0 auto;
                padding: 0px;
                background-color: transparent;
            }
            .container {
                background-color: #fff;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                padding: 30px;
                margin-bottom: 30px;
            }
            h1 {
                color: #2c3e50;
                border-bottom: 3px solid #3498db;
                padding-bottom: 10px;
                margin-top: 0;
            }
            h2 {
                color: #2c3e50;
                border-left: 5px solid #3498db;
                padding-left: 15px;
                margin-top: 30px;
                background-color: #f8f9fa;
                padding: 10px 15px;
                border-radius: 0 5px 5px 0;
            }
            h3 {
                color: #2c3e50;
                margin-top: 20px;
                border-bottom: 1px dashed #ddd;
                padding-bottom: 5px;
            }
            .section {
                margin-bottom: 30px;
                padding: 20px;
                background-color: #f9f9f9;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            }
            ul, ol {
                padding-left: 25px;
            }
            ul li, ol li {
                margin-bottom: 8px;
            }
            .recommendation {
                font-weight: bold;
                font-size: 1.1em;
                padding: 15px;
                margin: 15px 0;
                border-radius: 5px;
                text-align: center;
            }
            .buy {
                background-color: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }
            .hold {
                background-color: #fff3cd;
                color: #856404;
                border: 1px solid #ffeeba;
            }
            .sell {
                background-color: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }
            .metrics {
                display: flex;
                flex-wrap: wrap;
                gap: 15px;
                margin: 20px 0;
            }
            .metric-card {
                background-color: #f0f7ff;
                border-radius: 5px;
                padding: 15px;
                flex: 1;
                min-width: 200px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            }
            .metric-title {
                font-weight: bold;
                color: #2980b9;
                margin-bottom: 5px;
            }
            .metric-value {
                font-size: 1.2em;
                font-weight: bold;
            }
            .chart-container {
                margin: 20px 0;
                text-align: center;
            }
            .footnote {
                font-size: 0.9em;
                font-style: italic;
                color: #6c757d;
                margin-top: 30px;
                padding-top: 15px;
                border-top: 1px solid #dee2e6;
            }
            strong {
                color: #2980b9;
            }
            .highlight {
                background-color: #ffeaa7;
                padding: 2px 4px;
                border-radius: 3px;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }
            th, td {
                padding: 12px 15px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }
            th {
                background-color: #f2f2f2;
                font-weight: bold;
            }
            tr:hover {
                background-color: #f5f5f5;
            }
            .summary-box {
                background-color: #e8f4fd;
                border-left: 4px solid #3498db;
                padding: 15px;
                margin: 20px 0;
                border-radius: 0 5px 5px 0;
            }
            .indicator {
                margin-bottom: 20px;
                padding: 15px;
                border-radius: 5px;
                background-color: #f8f9fa;
                border-left: 4px solid #3498db;
            }
            .indicator h4 {
                margin-top: 0;
                color: #2980b9;
            }
            .timeframe {
                font-weight: bold;
                color: #2c3e50;
                background-color: #e8f4fd;
                padding: 5px 10px;
                border-radius: 3px;
                display: inline-block;
                margin-bottom: 15px;
            }
            .weights-section {
                background-color: #f0f4f9;
                border-left: 4px solid #2980b9;
                margin-bottom: 30px;
                padding: 15px;
                border-radius: 0 5px 5px 0;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Comprehensive Investment Analysis: [TICKER_PLACEHOLDER] - [COMPANY_PLACEHOLDER]</h1>
            
            <div class="timeframe">Analysis Timeframe: [TIMEFRAME_PLACEHOLDER]</div>
            
            <div class="section">
                <h2>Executive Summary</h2>
                <div class="summary-box">
                    <p>[SUMMARY_PLACEHOLDER]</p>
                </div>
                
                <div class="recommendation [RECOMMENDATION_CLASS_PLACEHOLDER]">
                    RECOMMENDATION: [RECOMMENDATION_PLACEHOLDER]
                    <br>
                    <span style="font-size:0.95em; font-weight:normal;">
                    <strong>Note:</strong> This recommendation is primarily driven by 
                    <span class="highlight">
                        [DOMINANT_ANALYSIS_TYPE_PLACEHOLDER]
                    </span> 
                    analysis, as selected by the user’s weightings.
                    </span>
                </div>
            </div>

            <div class="section">
                <h2>Fundamental Analysis</h2>
                <div id="fundamental-analysis">
                    [FUNDAMENTAL_ANALYSIS_PLACEHOLDER]
                </div>
                
                <h3>Key Financial Metrics</h3>
                <div class="metrics">
                    [FINANCIAL_METRICS_PLACEHOLDER]
                </div>
                
                <h3>Valuation Analysis</h3>
                <table>
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                        <th>Industry Average</th>
                        <th>Assessment</th>
                    </tr>
                    [VALUATION_METRICS_PLACEHOLDER]
                </table>
            </div>
            
            <div class="section">
                <h2>Technical Analysis</h2>
                <div id="technical-analysis">
                    [TECHNICAL_ANALYSIS_PLACEHOLDER]
                </div>
                
                <h3>Technical Indicators</h3>
                
                <div class="indicator">
                    <h4>SMA (Simple Moving Average)</h4>
                    <p>[SMA_ANALYSIS_PLACEHOLDER]</p>
                </div>
                
                <div class="indicator">
                    <h4>RSI (Relative Strength Index)</h4>
                    <p>[RSI_ANALYSIS_PLACEHOLDER]</p>
                </div>
                
                <div class="indicator">
                    <h4>MACD (Moving Average Convergence Divergence)</h4>
                    <p>[MACD_ANALYSIS_PLACEHOLDER]</p>
                </div>
                
                <div class="indicator">
                    <h4>OBV (On-Balance Volume)</h4>
                    <p>[OBV_ANALYSIS_PLACEHOLDER]</p>
                </div>
                
                <div class="indicator">
                    <h4>ADX (Average Directional Index)</h4>
                    <p>[ADX_ANALYSIS_PLACEHOLDER]</p>
                </div>
                
                <h3>Support and Resistance Levels</h3>
                <table>
                    <tr>
                        <th>Level Type</th>
                        <th>Price Point</th>
                        <th>Strength</th>
                    </tr>
                    [SUPPORT_RESISTANCE_PLACEHOLDER]
                </table>
            </div>
            
            <div class="section">
                <h2>News and Events Analysis</h2>
                <div id="news-analysis">
                    [NEWS_ANALYSIS_PLACEHOLDER]
                </div>
                
                <h3>Recent Significant Events</h3>
                <ul>
                    [SIGNIFICANT_EVENTS_PLACEHOLDER]
                </ul>
            </div>
            
            <div class="section">
                <h2>Integrated Analysis</h2>
                <p>[INTEGRATED_ANALYSIS_PLACEHOLDER]</p>
                
                <div class="weights-section">
                    <h3>User-Selected Analysis Weights</h3>
                    <ul>
                        <li><strong>Fundamental Analysis Weight:</strong> [FUNDAMENTAL_WEIGHT_PLACEHOLDER]</li>
                        <li><strong>Technical Analysis Weight:</strong> [TECHNICAL_WEIGHT_PLACEHOLDER]</li>
                        <li><strong>News and Events Weight:</strong> [NEWS_WEIGHT_PLACEHOLDER]</li>
                    </ul>
                    <p>
                    These weights determined the overall influence of each analysis type on the final investment recommendation.
                    The report will highlight which analysis category most influenced the recommendation, based on the user’s preferences.
                    </p>
                </div>
                
                <h3>Alignment Assessment</h3>
                <table>
                    <tr>
                        <th>Analysis Type</th>
                        <th>Outlook</th>
                        <th>Confidence</th>
                    </tr>
                    <tr>
                        <td>Fundamental</td>
                        <td>[FUNDAMENTAL_OUTLOOK_PLACEHOLDER]</td>
                        <td>[FUNDAMENTAL_CONFIDENCE_PLACEHOLDER]</td>
                    </tr>
                    <tr>
                        <td>Technical</td>
                        <td>[TECHNICAL_OUTLOOK_PLACEHOLDER]</td>
                        <td>[TECHNICAL_CONFIDENCE_PLACEHOLDER]</td>
                    </tr>
                    <tr>
                        <td>News/Events</td>
                        <td>[NEWS_OUTLOOK_PLACEHOLDER]</td>
                        <td>[NEWS_CONFIDENCE_PLACEHOLDER]</td>
                    </tr>
                    <tr>
                        <td><strong>Overall</strong></td>
                        <td><strong>[OVERALL_OUTLOOK_PLACEHOLDER]</strong></td>
                        <td><strong>[OVERALL_CONFIDENCE_PLACEHOLDER]</strong></td>
                    </tr>
                </table>
                
                <h3>Investment Recommendation</h3>
                <div class="summary-box">
                    <p><strong>Recommendation:</strong> [DETAILED_RECOMMENDATION_PLACEHOLDER]</p>
                    
                    <p><strong>Entry Points:</strong> [ENTRY_POINTS_PLACEHOLDER]</p>
                    
                    <p><strong>Exit Strategy:</strong> [EXIT_STRATEGY_PLACEHOLDER]</p>
                    
                    <p><strong>Risk Management:</strong> [RISK_MANAGEMENT_PLACEHOLDER]</p>
                </div>
            </div>
            
            <div class="footnote"> """ f"""
                <p>This investment analysis was generated on {formatted} , and incorporates available data as of this date. All investment decisions should be made in conjunction with personal financial advice and risk tolerance assessments.</p>
            </div>
        </div>
    </body>
    </html>
    ```
    Parse the provided JSON data and use it to replace the placeholders in the HTML template. Make sure to:

        1. Extract the Ticker and Company information for the title.

        2. Extract the Timeframe for the timeframe display.

        3. Extract the Technical Analysis summary for the technical analysis section.

        4. Extract Technical indicator results (SMA, RSI, MACD, OBV, ADX) for their dedicated sections.

        5. Extract the Fundamental Analysis for the fundamental analysis section.

        6. Extract News data for the news analysis section.

        7. Extract the user-selected weightings for each analysis type (e.g., Fundamental, Technical, News/Events). Clearly display these weights in the "User-Selected Analysis Weights" section under Investment Recommendation.

        8. When generating the overall investment recommendation, weigh the influence of each analysis type (Fundamental, Technical, News/Events) according to the user-selected weights. The final recommendation (BUY, HOLD, or SELL) should be determined by a weighted synthesis of these three components, based on their assigned importance. Clearly communicate if the result is driven more by one analysis type due to a higher weighting.

        Recommendation Logic:

    When generating the “Recommendation” (Buy, Hold, Sell), synthesize and weigh the findings from the Technical Analysis, Fundamental Analysis, and News/Events Analysis according to the provided weights.

    If one weighting is clearly dominant (e.g., Fundamental Analysis = 0.7), emphasize in the summary and recommendation that the final decision is mainly driven by that analysis type.

    The “Integrated Analysis” and “Alignment Assessment” sections should explicitly note which analysis types had the greatest influence on the final recommendation, based on the weights.

    Justification:

    The justification text for the recommendation must refer to the weights. For example:
    “Given the user’s preference to weigh Fundamental Analysis at 60%, the final recommendation relies primarily on the company’s strong balance sheet and valuation ratios, despite short-term volatility in technical indicators.”

    Return the complete HTML document as your response.
    """
    
    # Simply pass the entire gathered_data dictionary as JSON
    user_message = f"The data to analyse: {json.dumps(gathered_data)}"
    
    # Call Claude API to generate the HTML with progress indicator
    with st.spinner("Generating investment analysis..."):
        try:
            response = client.chat.completions.create(
                model="gpt-4.1",  # Use the appropriate Claude model
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ]
            )
            
            # Extract the response content
            html_content = response.choices[0].message.content
            return html_content
            
        except Exception as e:
            st.error(f"Error generating analysis: {e}")
            return None

def fa_summary_and_news_summary(fa_summary, txt_summary):
    today = date.today()
    formatted = today.strftime('%Y-%m-%d')


    system_prompt = """ As an AI assistant dedicated to supporting traders and investors, your task is to produce a structured, detailed market analysis in valid HTML format. Focus exclusively on synthesizing recent news/events and fundamental analysis related to the selected stock. Do not include any technical analysis or technical indicator results.

    The user will provide a JSON object containing all the data needed for analysis, including:
    - Ticker: The stock ticker symbol
    - Company: The company name
    - Timeframe: The analysis timeframe
    - FundamentalAnalysis: A comprehensive summary of the company’s fundamental position, including key financials, ratios, valuation, and management/industry factors.
    - NewsData: A summary of all significant news and events for the company and its sector.
    - SignificantEvents: A list of recent, impactful events affecting the company or its market environment.

    You must parse this JSON data and use it to create a comprehensive investment report formatted as HTML.

    **Instructions:**
    - Parse the provided JSON data and use it to replace the placeholders in the HTML template below.
    - Extract the Ticker and Company information for the title.
    - Extract the Timeframe for the timeframe display.
    - Extract the FundamentalAnalysis summary for the Fundamental Analysis section.
    - Extract the NewsData for the News and Events Analysis section.
    - Extract the SignificantEvents list for the 'Recent Significant Events' section.
    - Generate a summary and investment recommendation (BUY, HOLD, or SELL) based on the synthesis of fundamental analysis and news/events. Justify your reasoning by referring to the financial fundamentals and the reported news/events.
    - The 'Integrated Analysis' section should synthesize all insights from both fundamental and news/event signals into a final outlook and recommendation.
    - Return the complete HTML document as your response. Do not include any Markdown or plaintext. Do not leave out any required section, even if some are brief or data is missing.

    Your output must use <section>, <h2>, <h3>, <ul>, <li>, <table>, and <p> tags as appropriate. Use <strong> for key points.

    **Follow this professional HTML template exactly, replacing the placeholders with values parsed from the provided JSON:**

    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Comprehensive Fundamental & News Investment Analysis</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1200px;
                margin: 0 auto;
                padding: 0px;
                background-color: transparent;
            }
            .container {
                background-color: #fff;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                padding: 30px;
                margin-bottom: 30px;
            }
            h1 {
                color: #2c3e50;
                border-bottom: 3px solid #3498db;
                padding-bottom: 10px;
                margin-top: 0;
            }
            h2 {
                color: #2c3e50;
                border-left: 5px solid #3498db;
                padding-left: 15px;
                margin-top: 30px;
                background-color: #f8f9fa;
                padding: 10px 15px;
                border-radius: 0 5px 5px 0;
            }
            h3 {
                color: #2c3e50;
                margin-top: 20px;
                border-bottom: 1px dashed #ddd;
                padding-bottom: 5px;
            }
            .section {
                margin-bottom: 30px;
                padding: 20px;
                background-color: #f9f9f9;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            }
            ul, ol {
                padding-left: 25px;
            }
            ul li, ol li {
                margin-bottom: 8px;
            }
            .recommendation {
                font-weight: bold;
                font-size: 1.1em;
                padding: 15px;
                margin: 15px 0;
                border-radius: 5px;
                text-align: center;
            }
            .buy {
                background-color: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }
            .hold {
                background-color: #fff3cd;
                color: #856404;
                border: 1px solid #ffeeba;
            }
            .sell {
                background-color: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }
            .summary-box {
                background-color: #e8f4fd;
                border-left: 4px solid #3498db;
                padding: 15px;
                margin: 20px 0;
                border-radius: 0 5px 5px 0;
            }
            .timeframe {
                font-weight: bold;
                color: #2c3e50;
                background-color: #e8f4fd;
                padding: 5px 10px;
                border-radius: 3px;
                display: inline-block;
                margin-bottom: 15px;
            }
            .footnote {
                font-size: 0.9em;
                font-style: italic;
                color: #6c757d;
                margin-top: 30px;
                padding-top: 15px;
                border-top: 1px solid #dee2e6;
            }
            .highlight {
                background-color: #ffeaa7;
                padding: 2px 4px;
                border-radius: 3px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Comprehensive Fundamental & News Investment Analysis: [TICKER_PLACEHOLDER] - [COMPANY_PLACEHOLDER]</h1>
            <div class="timeframe">Analysis Timeframe: [TIMEFRAME_PLACEHOLDER]</div>
            
            <section class="section">
                <h2>Executive Summary</h2>
                <div class="summary-box">
                    <p>[SUMMARY_PLACEHOLDER]</p>
                </div>
                <div class="recommendation [RECOMMENDATION_CLASS_PLACEHOLDER]">
                    RECOMMENDATION: [RECOMMENDATION_PLACEHOLDER]
                    <br>
                    <span style="font-size:0.95em; font-weight:normal;">
                    <strong>Note:</strong> This recommendation is based on a synthesis of fundamental data and recent news/events.
                    </span>
                </div>
            </section>
            
            <section class="section">
                <h2>Fundamental Analysis</h2>
                <div id="fundamental-analysis">
                    [FUNDAMENTAL_ANALYSIS_PLACEHOLDER]
                </div>
            </section>
            
            <section class="section">
                <h2>News and Events Analysis</h2>
                <div id="news-analysis">
                    [NEWS_ANALYSIS_PLACEHOLDER]
                </div>
                <h3>Recent Significant Events</h3>
                <ul>
                    [SIGNIFICANT_EVENTS_PLACEHOLDER]
                </ul>
            </section>
            
            <section class="section">
                <h2>Integrated Analysis</h2>
                <p>[INTEGRATED_ANALYSIS_PLACEHOLDER]</p>
                <h3>Investment Recommendation</h3>
                <div class="summary-box">
                    <p><strong>Recommendation:</strong> [DETAILED_RECOMMENDATION_PLACEHOLDER]</p>
                    <p><strong>Entry Points:</strong> [ENTRY_POINTS_PLACEHOLDER]</p>
                    <p><strong>Exit Strategy:</strong> [EXIT_STRATEGY_PLACEHOLDER]</p>
                    <p><strong>Risk Management:</strong> [RISK_MANAGEMENT_PLACEHOLDER]</p>
                </div>
            </section>
            
            <div class="footnote"> """ f"""
                <p>This investment analysis was generated on {formatted}, and incorporates available financial fundamentals, news, and event data as of this date. All investment decisions should be made in conjunction with personal financial advice and risk tolerance assessments.</p>
            </div>
        </div>
    </body>
    </html>
    """
           
    chat_completion = client.chat.completions.create(
        model="gpt-4.1",  # Ensure that you use a model available in your OpenAI subscription
        messages=[
            {
                "role": "system",
                "content": (
                "You are an AI model trained to create a comprehensive investment report by integrating recent news/events with fundamental analysis. "
                "Your output must be structured as valid HTML using headings (<section>, <h2>, <h3>), <ul> for bullet points, <ol> for numbered lists, and <strong> for key metrics and event names. Do not use Markdown or plain text formatting—output HTML only.\n"
                "\n"
                "Follow this structure exactly:\n"
                "<section id='introduction'>\n"
                "  <h2>Introduction</h2>\n"
                "  <ul>\n"
                "    <li>Briefly summarize the asset, its industry context, and the relevance of both fundamental analysis and recent events.</li>\n"
                "    <li>State the objective: to integrate fundamental performance with recent news for a complete perspective on the asset's investment potential.</li>\n"
                "  </ul>\n"
                "</section>\n"
                "\n"
                "<section id='fundamental-analysis-summary'>\n"
                "  <h2>Fundamental Analysis Summary</h2>\n"
                "  <ul>\n"
                "    <li><strong>Financial Performance:</strong> Key financial metrics (e.g., <strong>Revenue Growth</strong>, <strong>Net Income</strong>) reflecting stability.</li>\n"
                "    <li><strong>Valuation Metrics:</strong> Include <strong>P/E</strong>, <strong>P/B</strong>, <strong>Dividend Yield</strong>, with industry comparisons.</li>\n"
                "    <li><strong>Market Position and Competitive Standing:</strong> Outline market position, strengths, and a brief <strong>SWOT</strong> summary.</li>\n"
                "    <li><strong>Key Takeaways:</strong> Summarize overall financial health and growth outlook.</li>\n"
                "  </ul>\n"
                "</section>\n"
                "\n"
                "<section id='recent-news-events'>\n"
                "  <h2>Recent News and Events Summary</h2>\n"
                "  <ul>\n"
                "    <li><strong>Recent Developments:</strong> Major events impacting the asset (e.g., <strong>Product Launch</strong>, <strong>Regulatory Change</strong>).</li>\n"
                "    <li><strong>Market Sentiment and Impact:</strong> Describe how each event affected sentiment, positively or negatively.</li>\n"
                "    <li><strong>Macro and Industry-Level News:</strong> Broader economic or industry developments relevant to the asset.</li>\n"
                "    <li><strong>Key Takeaways:</strong> Highlight the potential influence of recent events on the asset’s outlook.</li>\n"
                "  </ul>\n"
                "</section>\n"
                "\n"
                "<section id='integrated-investment-insights'>\n"
                "  <h2>Integrated Investment Insights</h2>\n"
                "  <ul>\n"
                "    <li><strong>Alignment of Fundamentals with Recent Events:</strong> Describe how recent events support or challenge the fundamental outlook.</li>\n"
                "    <li><strong>Market Sentiment vs. Intrinsic Value:</strong> Evaluate how current sentiment aligns with intrinsic value.</li>\n"
                "    <li><strong>Risk Factors:</strong> Identify any new or heightened risks introduced by recent events.</li>\n"
                "  </ul>\n"
                "</section>\n"
                "\n"
                "<section id='actionable-recommendations'>\n"
                "  <h2>Actionable Recommendations</h2>\n"
                "  <ol>\n"
                "    <li><strong>Investment Decision:</strong> Provide a <strong>Buy</strong>, <strong>Hold</strong>, or <strong>Sell</strong> recommendation, integrating both analysis perspectives.</li>\n"
                "    <li><strong>Entry and Exit Points:</strong> Suggest entry/exit levels based on news and valuation.</li>\n"
                "    <li><strong>Risk Management and Monitoring:</strong> Recommend risk management strategies and future events/updates to watch.</li>\n"
                "  </ol>\n"
                "</section>\n"
                
                "Style-requirements"
                "Maintain a professional, data-driven tone; avoid personal opinions."
                "Minimize jargon and briefly clarify terms as needed."
                "Keep sentences and paragraphs concise for logical flow and readability."
                "Always include all sections and appropriate subheadings, even if information is brief. Output only valid HTML."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"From and merge these texts, Recent News and Events: {txt_summary} and Fundamental Analysis: {fa_summary}"
                ),
            },
        ]
    )

    response = chat_completion.choices[0].message.content
    return response




                
def merge_ta_fa_na_summary(fa_summary,ta_summary,na_summary):
     
    chat_completion = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an AI model designed to provide technical, fundamental, and news/events-based analysis to deliver actionable, long-term investment insights. Your role is to integrate financial health, competitive positioning, market trends, technical indicators, and relevant news/events into cohesive, data-driven recommendations for strategic, long-term investment strategies. Follow the specified structure and formatting guidelines to ensure clarity, professionalism, and usability."
                    "Formatting Requirements"
                    "Organized Headings and Subheadings: Separate sections clearly with headings (e.g., “Financial Overview,” “Technical Trends Analysis,” “Investment Recommendations”).Use descriptive subheadings for detailed insights (e.g., “Key Financial Metrics,” “Market Sentiment Analysis”)."
                    "Bullet Points and Numbered Lists:Use bullet points for comprehensive lists and numbered lists for prioritized recommendations."
                    "Formatting for Key Metrics and Indicators:Bold key financial terms (e.g., Earnings Per Share (EPS), Relative Strength Index (RSI))."
                    "Structure Guidelines:"
                    "Introduction"
                    "Briefly describe the asset’s profile, market sector, and its significance for long-term investors."
                    "Highlight the objective: integrating fundamental, technical, and events analysis for well-rounded investment decisions."
                    "Fundamental Analysis:"
                    """Fundamental Analysis
                    Financial Performance and Stability:

                    Review financial statements to assess profitability, solvency, and growth.
                    Focus on metrics such as revenue growth, net margins, and debt ratios.
                    Valuation Metrics:

                    Compare ratios like P/E, P/B, and Dividend Yield to industry norms.
                    Competitive Position and Risks:

                    Analyze market share, competitive advantages, and challenges.
                    Include a SWOT analysis for clarity on growth drivers and risks."""
                    """Technical Analysis
                    Long-Term Indicators:
                    MACD: Identify trends using signal line crossovers and price divergence.
                    ADX: Measure trend strength (e.g., readings > 20 = strong trend).
                    Bollinger Bands: Analyze volatility for entry/exit opportunities.
                    RSI: Use extended RSI values to determine overbought/oversold conditions.
                    SMA Crossovers: Monitor trends (e.g., "golden cross" patterns).
                    News and Events Analysis
                    Market Events and Macroeconomic Trends:

                    Summarize key news/events impacting the asset or sector (e.g., earnings releases, regulatory changes).
                    Highlight implications for long-term investment strategies.
                    Sector-Specific Developments:

                    Address sector-wide disruptions or opportunities (e.g., technological advances, geopolitical risks).
                    Integrated Analysis
                    Correlation of Insights:

                    Combine fundamental, technical, and event-based analysis to determine alignment or divergence.
                    Assess the impact of news/events on intrinsic value and technical trends.
                    Market Sentiment and Timing:

                    Evaluate whether market sentiment aligns with fundamental strengths or highlights discrepancies.
                    Long-Term Actionable Recommendations
                    Investment Decision:

                    Provide a clear Buy, Hold, or Sell recommendation, supported by key findings.
                    Entry and Exit Points:

                    Specify ideal entry/exit points using long-term technical indicators (e.g., SMA crossovers, RSI levels).
                    Risk Management:

                    Suggest risk mitigation strategies (e.g., stop-loss levels, portfolio diversification).
                    Performance Monitoring:

                    Highlight key updates (e.g., quarterly earnings) and technical changes (e.g., MACD signals) for regular review.
                    Style Requirements
                    Maintain a professional, analytical tone, avoiding personal opinions.
                    Use clear, concise language to ensure readability.
                    Minimize jargon; explain technical terms for clarity where needed."""
                ),

            },
            {
                "role": "user",
                "content": (
                    f"From and merge these texts, Technical Analysis: {ta_summary}, Fundamental Analysis: {fa_summary} and News/events: {na_summary}"
                ),
            },
        ]
     )

    response = chat_completion.choices[0].message.content
    return response



                
                



def merge_ta_fa_summary(gathered_data):
    today = date.today()
    formatted = today.strftime('%Y-%m-%d')  


    system_prompt = f"""
    As an AI assistant dedicated to supporting traders and investors, your task is to produce a structured, visually professional comparative investment analysis in valid HTML format.  
    The user will provide a JSON object containing data for two companies, including:
    - Ticker for each company
    - Company name for each company
    - Timeframe for the analysis
    - Technical analysis summary for both companies
    - Fundamental analysis summary for both companies
    - Technical indicator results for both companies (SMA, RSI, MACD, OBV, ADX, BD, etc.)
    - UserSelectedWeights: Object with weights for Technical, Fundamental, and optionally News/Events

    **Instructions:**
    - Parse the provided JSON and compare BOTH companies side by side in all sections.
    - Display the tickers and company names in the title and table headers.
    - Display the Technical and Fundamental Analysis summaries for each company in parallel columns.
    - Present technical indicator results for both companies in a comparison table.
    - Display user-selected weights in a dedicated section and highlight the most influential weight.
    - In “Integrated Analysis”, state which company is favored and why, citing the dominant weight.
    - Provide a recommendation for each company and a comparative conclusion.
    - Include ALL sections and full CSS styling from the template below.

    Your output must use <section>, <h2>, <h3>, <ul>, <li>, <table>, and <p> tags as appropriate. Use <strong> for key points.

    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Comparative Investment Analysis</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1200px;
                margin: 0 auto;
                padding: 0px;
                background-color: transparent;
            }}
            .container {{
                background-color: #fff;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                padding: 30px;
                margin-bottom: 30px;
            }}
            h1 {{
                color: #2c3e50;
                border-bottom: 3px solid #3498db;
                padding-bottom: 10px;
                margin-top: 0;
            }}
            h2 {{
                color: #2c3e50;
                border-left: 5px solid #3498db;
                padding-left: 15px;
                margin-top: 30px;
                background-color: #f8f9fa;
                padding: 10px 15px;
                border-radius: 0 5px 5px 0;
            }}
            h3 {{
                color: #2c3e50;
                margin-top: 20px;
                border-bottom: 1px dashed #ddd;
                padding-bottom: 5px;
            }}
            .section {{
                margin-bottom: 30px;
                padding: 20px;
                background-color: #f9f9f9;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            }}
            .recommendation {{
                font-weight: bold;
                font-size: 1.1em;
                padding: 15px;
                margin: 15px 0;
                border-radius: 5px;
                text-align: center;
            }}
            .buy {{
                background-color: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }}
            .hold {{
                background-color: #fff3cd;
                color: #856404;
                border: 1px solid #ffeeba;
            }}
            .sell {{
                background-color: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }}
            .indicator {{
                margin-bottom: 20px;
                padding: 15px;
                border-radius: 5px;
                background-color: #f8f9fa;
                border-left: 4px solid #3498db;
            }}
            .indicator h4 {{
                margin-top: 0;
                color: #2980b9;
            }}
            .summary-box {{
                background-color: #e8f4fd;
                border-left: 4px solid #3498db;
                padding: 15px;
                margin: 20px 0;
                border-radius: 0 5px 5px 0;
            }}
            .timeframe {{
                font-weight: bold;
                color: #2c3e50;
                background-color: #e8f4fd;
                padding: 5px 10px;
                border-radius: 3px;
                display: inline-block;
                margin-bottom: 15px;
            }}
            .weights-section {{
                background-color: #f0f4f9;
                border-left: 4px solid #2980b9;
                margin-bottom: 30px;
                padding: 15px;
                border-radius: 0 5px 5px 0;
            }}
            .footnote {{
                font-size: 0.9em;
                font-style: italic;
                color: #6c757d;
                margin-top: 30px;
                padding-top: 15px;
                border-top: 1px solid #dee2e6;
            }}
            .highlight {{
                background-color: #ffeaa7;
                padding: 2px 4px;
                border-radius: 3px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            th, td {{
                border: 1px solid #ccc;
                padding: 10px;
                text-align: center;
                font-size: 1em;
            }}
            th {{
                background-color: #e8f4fd;
                color: #2c3e50;
            }}
        </style>
    </head>
    <body>
    <div class="container">
        <h1>Comparative Investment Analysis: [TICKER1_PLACEHOLDER] vs [TICKER2_PLACEHOLDER]</h1>
        <div class="timeframe">Analysis Timeframe: [TIMEFRAME_PLACEHOLDER]</div>

        <section class="section">
            <h2>Executive Summary</h2>
            <div class="summary-box">
                <div style="display: flex; flex-wrap: wrap;">
                    <div style="flex: 1; min-width: 250px; margin-right: 20px;">
                        <h3>[COMPANY1_PLACEHOLDER]</h3>
                        <p>[SUMMARY1_PLACEHOLDER]</p>
                    </div>
                    <div style="flex: 1; min-width: 250px;">
                        <h3>[COMPANY2_PLACEHOLDER]</h3>
                        <p>[SUMMARY2_PLACEHOLDER]</p>
                    </div>
                </div>
            </div>
            <div class="recommendation [REC1_CLASS_PLACEHOLDER]">[COMPANY1_PLACEHOLDER] RECOMMENDATION: [REC1_PLACEHOLDER]</div>
            <div class="recommendation [REC2_CLASS_PLACEHOLDER]">[COMPANY2_PLACEHOLDER] RECOMMENDATION: [REC2_PLACEHOLDER]</div>
        </section>

        <section class="section">
            <h2>Technical Indicator Comparison</h2>
            <table>
                <tr>
                    <th>Indicator</th>
                    <th>[COMPANY1_PLACEHOLDER]</th>
                    <th>[COMPANY2_PLACEHOLDER]</th>
                </tr>
                <tr>
                    <td>SMA</td>
                    <td>[SMA1_PLACEHOLDER]</td>
                    <td>[SMA2_PLACEHOLDER]</td>
                </tr>
                <tr>
                    <td>RSI</td>
                    <td>[RSI1_PLACEHOLDER]</td>
                    <td>[RSI2_PLACEHOLDER]</td>
                </tr>
                <tr>
                    <td>MACD</td>
                    <td>[MACD1_PLACEHOLDER]</td>
                    <td>[MACD2_PLACEHOLDER]</td>
                </tr>
                <tr>
                    <td>OBV</td>
                    <td>[OBV1_PLACEHOLDER]</td>
                    <td>[OBV2_PLACEHOLDER]</td>
                </tr>
                <tr>
                    <td>ADX</td>
                    <td>[ADX1_PLACEHOLDER]</td>
                    <td>[ADX2_PLACEHOLDER]</td>
                </tr>
                <tr>
                    <td>BD</td>
                    <td>[BD1_PLACEHOLDER]</td>
                    <td>[BD2_PLACEHOLDER]</td>
                </tr>
            </table>
        </section>

        <section class="section">
            <h2>Technical & Fundamental Analysis</h2>
            <div style="display: flex; flex-wrap: wrap;">
                <div style="flex: 1; min-width: 250px; margin-right: 20px;">
                    <h3>[COMPANY1_PLACEHOLDER]</h3>
                    <div class="indicator"><h4>Technical Analysis</h4><p>[TECHNICAL1_PLACEHOLDER]</p></div>
                    <div class="indicator"><h4>Fundamental Analysis</h4><p>[FUNDAMENTAL1_PLACEHOLDER]</p></div>
                </div>
                <div style="flex: 1; min-width: 250px;">
                    <h3>[COMPANY2_PLACEHOLDER]</h3>
                    <div class="indicator"><h4>Technical Analysis</h4><p>[TECHNICAL2_PLACEHOLDER]</p></div>
                    <div class="indicator"><h4>Fundamental Analysis</h4><p>[FUNDAMENTAL2_PLACEHOLDER]</p></div>
                </div>
            </div>
        </section>

        <section class="section">
            <h2>User-Selected Analysis Weights</h2>
            <div class="weights-section">
                <ul>
                    <li><strong>Technical Analysis Weight:</strong> [TECHNICAL_WEIGHT_PLACEHOLDER]</li>
                    <li><strong>Fundamental Analysis Weight:</strong> [FUNDAMENTAL_WEIGHT_PLACEHOLDER]</li>
                    <li><strong>News and Events Weight:</strong> [NEWS_WEIGHT_PLACEHOLDER]</li>
                </ul>
                <p>
                    <strong>Dominant Influence:</strong> <span class="highlight">[DOMINANT_WEIGHT_PLACEHOLDER]</span>
                </p>
            </div>
        </section>

        <section class="section">
            <h2>Integrated Comparative Analysis & Final Recommendation</h2>
            <p>[INTEGRATED_ANALYSIS_PLACEHOLDER]</p>
            <div class="summary-box">
                <p><strong>Overall Best Opportunity:</strong> [BEST_OPPORTUNITY_PLACEHOLDER]</p>
                <p><strong>Entry Points:</strong> [ENTRY_POINTS_PLACEHOLDER]</p>
                <p><strong>Exit Strategy:</strong> [EXIT_STRATEGY_PLACEHOLDER]</p>
                <p><strong>Risk Management:</strong> [RISK_MANAGEMENT_PLACEHOLDER]</p>
            </div>
        </section>

        <div class="footnote">
            <p>This investment analysis was generated on {formatted}, and incorporates available data as of this date. All investment decisions should be made in conjunction with personal financial advice and risk tolerance assessments.</p>
        </div>
    </div>
    </body>
    </html>

    Instructions for the AI:
    - Use all the placeholders above.
    - Never leave out a section or style, even if data is missing.
    - Clearly state which company, analysis type, or weight is favored.
    - Always keep the format, styling, and order as above.
    """

    user_message = f"The data to analyse: {json.dumps(gathered_data)}"

    chat_completion = client.chat.completions.create(
        model="gpt-4.1",  # Ensure that you use a model available in your OpenAI subscription
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_message
            },
        ]
    )

    # Extract and return the AI-generated response
    response = chat_completion.choices[0].message.content
    return response

                        
                

        #if t_col1.button("Technical Analysis"):
            #analysis_type = "Technical Analysis"
        #elif n_col2.button("News and Events"):
            #analysis_type = "News and Events"
def clean_html_response(response):
    # Remove markdown formatting from response
    if response.startswith("```html"):
        response = response.lstrip("```html").strip()
    if response.endswith("```"):
        response = response.rstrip("```").strip()
    return response

def txt_conclusion(news_summary,company_name):
    # OpenAI API call to create a merged summary
    chat_completion = client.chat.completions.create(
        model="gpt-4.1",  # Ensure that you use a model available in your OpenAI subscription
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an AI model specializing in investment insights, tasked with analyzing recent news and events about a specified company and providing recommendations for investors. Your goal is to review relevant data, including press releases, market trends, earnings reports, and industry events, to assess the companys financial health, growth prospects, and potential risks. From this data, you will determine an ideal investor position (e.g., buy, hold, or sell)."
                    "Instructions:"
                    "Data Collection: Search for and analyze recent press releases, earnings reports, regulatory filings, and news articles regarding the specified company. Focus on the following:"
                    "Financial Performance: Look for quarterly or annual earnings, revenue, and profit trends."
                    "Product & Service Developments: Identify any new product launches, service expansions, or market innovations."
                    "Management Statements: Note key statements from executives or significant personnel changes that might impact the companys direction."
                    "Industry Events & Competitor Actions: Examine news of industry-wide developments, competitor performance, and market conditions."
                    "Regulatory & Legal News: Assess any legal challenges, regulatory updates, or policy changes impacting the company."
                    "Sentiment Analysis: Evaluate the tone and sentiment of the news data—whether positive, neutral, or negative. Gauge investor confidence and sentiment trends as reflected in the media."
                    "Market Impact: Summarize any immediate or anticipated effects of recent events on the companys stock price, including short-term volatility, potential growth indicators, or risk factors that could affect long-term performance."
                    "Investor Recommendation:"
                    "Buy: Recommend if positive news, strong financial performance, and promising growth potential outweigh risks."
                    "Hold: Suggest if there are mixed indicators, with potential growth tempered by risks or uncertain factors."
                    "Sell: Advise if significant risks, declining performance, or negative news dominate, suggesting potential for downturn."
                    "Final Conclusion: Provide a clear summary and reasoning behind the recommended position, addressing key data points and highlighting the rationale for an investor's action."
                    "Additional Sources: A separate section listing sources like press releases and opinions from the mentioned platforms, ensuring proper citations."
                    #Add Press releases, investor oppinions (X), First World Pharma, Bloomberg, Market Watch, seperate segment,add sources, add graphs
                    
                ),
            },
            {
                "role": "user",
                "content": (
                    f"News and Events Summary for {company_name}:\n{news_summary}\n\n"   
                ),
            },
        ]
    )

# Extract and return the AI-generated response
    response = chat_completion.choices[0].message.content
    return response 

def txt_conclusion2(gathered_data):
    today = date.today()
    formatted = today.strftime('%Y-%m-%d')

    # OpenAI API call to create a merged summary
    system_prompt = """ As an AI assistant dedicated to supporting traders and investors, your task is to produce a structured, detailed market analysis in valid HTML format. Focus exclusively on synthesizing recent news and events related to the selected stock and its sector. Do not include technical or fundamental analysis.

    The user will provide a JSON object containing all the data needed for analysis, including:
    - Ticker: The stock ticker symbol
    - Company: The company name
    - Timeframe: The analysis timeframe
    - NewsData: A summary of all significant news and events for the company and its sector.
    - SignificantEvents: A list of recent, impactful events affecting the company or its market environment.

    You must parse this JSON data and use it to create a comprehensive investment report formatted as HTML.

    **Instructions:**
    - Parse the provided JSON data and use it to replace the placeholders in the HTML template below.
    - Extract the Ticker and Company information for the title.
    - Extract the Timeframe for the timeframe display.
    - Extract the NewsData for the News and Events Analysis section.
    - Extract the SignificantEvents list for the 'Recent Significant Events' section.
    - Generate a summary and investment recommendation (BUY, HOLD, or SELL) based exclusively on news and events. Clearly justify your reasoning by referencing the reported news and events.
    - The 'Integrated Analysis' section should synthesize all news and event signals into a final outlook and recommendation.
    - Return the complete HTML document as your response. Do not include any Markdown or plaintext. Do not leave out any required section, even if some are brief or data is missing.

    Your output must use <section>, <h2>, <h3>, <ul>, <li>, <table>, and <p> tags as appropriate. Use <strong> for key points.

    **Follow this professional HTML template exactly, replacing the placeholders with values parsed from the provided JSON:**

    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Comprehensive News & Events Investment Analysis</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1200px;
                margin: 0 auto;
                padding: 0px;
                background-color: transparent;
            }
            .container {
                background-color: #fff;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                padding: 30px;
                margin-bottom: 30px;
            }
            h1 {
                color: #2c3e50;
                border-bottom: 3px solid #3498db;
                padding-bottom: 10px;
                margin-top: 0;
            }
            h2 {
                color: #2c3e50;
                border-left: 5px solid #3498db;
                padding-left: 15px;
                margin-top: 30px;
                background-color: #f8f9fa;
                padding: 10px 15px;
                border-radius: 0 5px 5px 0;
            }
            h3 {
                color: #2c3e50;
                margin-top: 20px;
                border-bottom: 1px dashed #ddd;
                padding-bottom: 5px;
            }
            .section {
                margin-bottom: 30px;
                padding: 20px;
                background-color: #f9f9f9;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            }
            .recommendation {
                font-weight: bold;
                font-size: 1.1em;
                padding: 15px;
                margin: 15px 0;
                border-radius: 5px;
                text-align: center;
            }
            .buy {
                background-color: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }
            .hold {
                background-color: #fff3cd;
                color: #856404;
                border: 1px solid #ffeeba;
            }
            .sell {
                background-color: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }
            .summary-box {
                background-color: #e8f4fd;
                border-left: 4px solid #3498db;
                padding: 15px;
                margin: 20px 0;
                border-radius: 0 5px 5px 0;
            }
            .timeframe {
                font-weight: bold;
                color: #2c3e50;
                background-color: #e8f4fd;
                padding: 5px 10px;
                border-radius: 3px;
                display: inline-block;
                margin-bottom: 15px;
            }
            .footnote {
                font-size: 0.9em;
                font-style: italic;
                color: #6c757d;
                margin-top: 30px;
                padding-top: 15px;
                border-top: 1px solid #dee2e6;
            }
            .highlight {
                background-color: #ffeaa7;
                padding: 2px 4px;
                border-radius: 3px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Comprehensive News & Events Investment Analysis: [TICKER_PLACEHOLDER] - [COMPANY_PLACEHOLDER]</h1>
            <div class="timeframe">Analysis Timeframe: [TIMEFRAME_PLACEHOLDER]</div>
            
            <section class="section">
                <h2>Executive Summary</h2>
                <div class="summary-box">
                    <p>[SUMMARY_PLACEHOLDER]</p>
                </div>
                <div class="recommendation [RECOMMENDATION_CLASS_PLACEHOLDER]">
                    RECOMMENDATION: [RECOMMENDATION_PLACEHOLDER]
                    <br>
                    <span style="font-size:0.95em; font-weight:normal;">
                    <strong>Note:</strong> This recommendation is based solely on the latest news and event signals.
                    </span>
                </div>
            </section>
            
            <section class="section">
                <h2>News and Events Analysis</h2>
                <div id="news-analysis">
                    [NEWS_ANALYSIS_PLACEHOLDER]
                </div>
                
                <h3>Recent Significant Events</h3>
                <ul>
                    [SIGNIFICANT_EVENTS_PLACEHOLDER]
                </ul>
            </section>
            
            <section class="section">
                <h2>Integrated Analysis</h2>
                <p>[INTEGRATED_ANALYSIS_PLACEHOLDER]</p>
                <h3>Investment Recommendation</h3>
                <div class="summary-box">
                    <p><strong>Recommendation:</strong> [DETAILED_RECOMMENDATION_PLACEHOLDER]</p>
                    <p><strong>Entry Points:</strong> [ENTRY_POINTS_PLACEHOLDER]</p>
                    <p><strong>Exit Strategy:</strong> [EXIT_STRATEGY_PLACEHOLDER]</p>
                    <p><strong>Risk Management:</strong> [RISK_MANAGEMENT_PLACEHOLDER]</p>
                </div>
            </section>
            
            <div class="footnote"> """ f"""
                <p>This investment analysis was generated on {formatted}, and incorporates available news and event data as of this date. All investment decisions should be made in conjunction with personal financial advice and risk tolerance assessments.</p>
            </div>
        </div>
    </body>
    </html>
    """

    user_message = f"The data to analyse: {json.dumps(gathered_data)}"

    chat_completion = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_message
            }
        ]
    )

# Extract and return the AI-generated response
    response = chat_completion.choices[0].message.content
    return response 

    

def merge_news_and_technical_analysis_summary(gathered_data):
    today = date.today()
    formatted = today.strftime('%Y-%m-%d')


    system_prompt = f"""
    As an AI assistant dedicated to supporting traders and investors, your task is to produce a structured, visually professional market analysis in valid HTML format. Your report must **compare and merge the latest news and technical analysis for TWO companies**, providing clear side-by-side insights, and **include a references section** citing all sources used in the news analysis.

    The user will provide a JSON object containing all the data needed for analysis, including:
    - Ticker: The primary stock ticker symbol
    - Company: The first company name
    - Company 2: The second company name
    - Timeframe: The analysis timeframe
    - Technical analysis summary for both companies
    - News summaries for both companies
    - News references/links for both companies
    - Technical indicator results for both companies (SMA, RSI, MACD, OBV, ADX, etc.)
    - UserSelectedWeights: Object with weights for Technical, Fundamental, and News/Events analyses

    **Instructions:**
    - Parse the provided JSON and compare BOTH companies in all sections.
    - Use <section>, <h2>, <h3>, <ul>, <li>, <table>, and <p> tags as appropriate. Use <strong> for key points.
    - Extract and clearly display Ticker, Company, Company 2, and Timeframe.
    - Present technical indicator results for both companies in a **side-by-side comparison table**.
    - Summarize technical analysis and news for each company in split sections.
    - In the User-Selected Weights section, display weights for all three categories and highlight which one most influenced the recommendation.
    - In “Integrated Analysis”, clearly state which company is favored and why, citing the dominant weight.
    - For the “Recommendation”, provide a recommendation for each company and a weighted comparative recommendation.
    - Include a "References" section at the end, **listing all links and sources cited in the news data for both companies**. Each reference should include the source title (if provided) and a clickable link. Clearly separate references for each company.
    - Include ALL styling and all sections; do not omit any element, even if the data is brief or missing.

    Your output must follow this HTML structure:

    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Comprehensive Investment Analysis Comparison</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1200px;
                margin: 0 auto;
                padding: 0px;
                background-color: transparent;
            }}
            .container {{
                background-color: #fff;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                padding: 30px;
                margin-bottom: 30px;
            }}
            h1 {{
                color: #2c3e50;
                border-bottom: 3px solid #3498db;
                padding-bottom: 10px;
                margin-top: 0;
            }}
            h2 {{
                color: #2c3e50;
                border-left: 5px solid #3498db;
                padding-left: 15px;
                margin-top: 30px;
                background-color: #f8f9fa;
                padding: 10px 15px;
                border-radius: 0 5px 5px 0;
            }}
            h3 {{
                color: #2c3e50;
                margin-top: 20px;
                border-bottom: 1px dashed #ddd;
                padding-bottom: 5px;
            }}
            .section {{
                margin-bottom: 30px;
                padding: 20px;
                background-color: #f9f9f9;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            }}
            ul, ol {{
                padding-left: 25px;
            }}
            ul li, ol li {{
                margin-bottom: 8px;
            }}
            .recommendation {{
                font-weight: bold;
                font-size: 1.1em;
                padding: 15px;
                margin: 15px 0;
                border-radius: 5px;
                text-align: center;
            }}
            .buy {{
                background-color: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }}
            .hold {{
                background-color: #fff3cd;
                color: #856404;
                border: 1px solid #ffeeba;
            }}
            .sell {{
                background-color: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }}
            .metrics {{
                display: flex;
                flex-wrap: wrap;
                gap: 15px;
                margin: 20px 0;
            }}
            .metric-card {{
                background-color: #f0f7ff;
                border-radius: 5px;
                padding: 15px;
                flex: 1;
                min-width: 200px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            }}
            .metric-title {{
                font-weight: bold;
                color: #2980b9;
                margin-bottom: 5px;
            }}
            .metric-value {{
                font-size: 1.2em;
                font-weight: bold;
            }}
            .chart-container {{
                margin: 20px 0;
                text-align: center;
            }}
            .footnote {{
                font-size: 0.9em;
                font-style: italic;
                color: #6c757d;
                margin-top: 30px;
                padding-top: 15px;
                border-top: 1px solid #dee2e6;
            }}
            strong {{
                color: #2980b9;
            }}
            .highlight {{
                background-color: #ffeaa7;
                padding: 2px 4px;
                border-radius: 3px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            th, td {{
                padding: 12px 15px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }}
            th {{
                background-color: #f2f2f2;
                font-weight: bold;
            }}
            tr:hover {{
                background-color: #f5f5f5;
            }}
            .summary-box {{
                background-color: #e8f4fd;
                border-left: 4px solid #3498db;
                padding: 15px;
                margin: 20px 0;
                border-radius: 0 5px 5px 0;
            }}
            .indicator {{
                margin-bottom: 20px;
                padding: 15px;
                border-radius: 5px;
                background-color: #f8f9fa;
                border-left: 4px solid #3498db;
            }}
            .indicator h4 {{
                margin-top: 0;
                color: #2980b9;
            }}
            .timeframe {{
                font-weight: bold;
                color: #2c3e50;
                background-color: #e8f4fd;
                padding: 5px 10px;
                border-radius: 3px;
                display: inline-block;
                margin-bottom: 15px;
            }}
            .weights-section {{
                background-color: #f0f4f9;
                border-left: 4px solid #2980b9;
                margin-bottom: 30px;
                padding: 15px;
                border-radius: 0 5px 5px 0;
            }}
            .references-section {{
                background-color: #f9f9f9;
                border-radius: 5px;
                padding: 20px;
                margin-bottom: 30px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            }}
            .references-section h2 {{
                border-left: 5px solid #3498db;
                padding-left: 15px;
                background-color: #f8f9fa;
                padding: 10px 15px;
                border-radius: 0 5px 5px 0;
                margin-top: 0;
            }}
            .references-list {{
                margin-left: 20px;
            }}
        </style>
    </head>
    <body>
    <div class="container">
        <h1>Comprehensive Investment Analysis: [TICKER_PLACEHOLDER] - [COMPANY1_PLACEHOLDER] vs [COMPANY2_PLACEHOLDER]</h1>
        <div class="timeframe">Analysis Timeframe: [TIMEFRAME_PLACEHOLDER]</div>

        <div class="section">
            <h2>Executive Summary</h2>
            <div class="summary-box">
                <div style="display: flex; flex-wrap: wrap;">
                    <div style="flex: 1; min-width: 250px; margin-right: 20px;">
                        <h3>[COMPANY1_PLACEHOLDER]</h3>
                        <p>[SUMMARY1_PLACEHOLDER]</p>
                    </div>
                    <div style="flex: 1; min-width: 250px;">
                        <h3>[COMPANY2_PLACEHOLDER]</h3>
                        <p>[SUMMARY2_PLACEHOLDER]</p>
                    </div>
                </div>
            </div>
            <div class="recommendation [RECOMMENDATION1_CLASS_PLACEHOLDER]">
                [COMPANY1_PLACEHOLDER] RECOMMENDATION: [RECOMMENDATION1_PLACEHOLDER]
            </div>
            <div class="recommendation [RECOMMENDATION2_CLASS_PLACEHOLDER]">
                [COMPANY2_PLACEHOLDER] RECOMMENDATION: [RECOMMENDATION2_PLACEHOLDER]
            </div>
        </div>

        <div class="section">
            <h2>Technical Indicator Comparison Table</h2>
            <table>
                <tr>
                    <th>Indicator</th>
                    <th>[COMPANY1_PLACEHOLDER]</th>
                    <th>[COMPANY2_PLACEHOLDER]</th>
                </tr>
                <tr>
                    <td>SMA</td>
                    <td>[SMA1_PLACEHOLDER]</td>
                    <td>[SMA2_PLACEHOLDER]</td>
                </tr>
                <tr>
                    <td>RSI</td>
                    <td>[RSI1_PLACEHOLDER]</td>
                    <td>[RSI2_PLACEHOLDER]</td>
                </tr>
                <tr>
                    <td>MACD</td>
                    <td>[MACD1_PLACEHOLDER]</td>
                    <td>[MACD2_PLACEHOLDER]</td>
                </tr>
                <tr>
                    <td>OBV</td>
                    <td>[OBV1_PLACEHOLDER]</td>
                    <td>[OBV2_PLACEHOLDER]</td>
                </tr>
                <tr>
                    <td>ADX</td>
                    <td>[ADX1_PLACEHOLDER]</td>
                    <td>[ADX2_PLACEHOLDER]</td>
                </tr>
            </table>
        </div>

        <div class="section">
            <h2>Technical & News Analysis</h2>
            <div style="display: flex; flex-wrap: wrap;">
                <div style="flex: 1; min-width: 250px; margin-right: 20px;">
                    <h3>[COMPANY1_PLACEHOLDER]</h3>
                    <div class="indicator"><h4>Technical Analysis</h4><p>[TECHNICAL1_PLACEHOLDER]</p></div>
                    <div class="indicator"><h4>News and Events</h4><p>[NEWS1_PLACEHOLDER]</p></div>
                </div>
                <div style="flex: 1; min-width: 250px;">
                    <h3>[COMPANY2_PLACEHOLDER]</h3>
                    <div class="indicator"><h4>Technical Analysis</h4><p>[TECHNICAL2_PLACEHOLDER]</p></div>
                    <div class="indicator"><h4>News and Events</h4><p>[NEWS2_PLACEHOLDER]</p></div>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>User-Selected Analysis Weights</h2>
            <div class="weights-section">
                <ul>
                    <li><strong>Technical Analysis Weight:</strong> [TECHNICAL_WEIGHT_PLACEHOLDER]</li>
                    <li><strong>Fundamental Analysis Weight:</strong> [FUND_WEIGHT_PLACEHOLDER]</li>
                    <li><strong>News and Events Weight:</strong> [NEWS_WEIGHT_PLACEHOLDER]</li>
                </ul>
                <p>
                    <strong>Dominant Influence:</strong> <span class="highlight">[DOMINANT_WEIGHT_PLACEHOLDER]</span>
                </p>
                <p>
                    These weights determined the overall influence of each analysis type on the final investment recommendation.
                </p>
            </div>
        </div>

        <div class="section">
            <h2>Integrated Comparative Analysis & Final Recommendation</h2>
            <p>[INTEGRATED_ANALYSIS_PLACEHOLDER]</p>
            <div class="summary-box">
                <p><strong>Overall Best Opportunity:</strong> [BEST_OPPORTUNITY_PLACEHOLDER]</p>
                <p><strong>Entry Points:</strong> [ENTRY_POINTS_PLACEHOLDER]</p>
                <p><strong>Exit Strategy:</strong> [EXIT_STRATEGY_PLACEHOLDER]</p>
                <p><strong>Risk Management:</strong> [RISK_MANAGEMENT_PLACEHOLDER]</p>
            </div>
        </div>

        <div class="references-section">
            <h2>References</h2>
            <div style="display: flex; flex-wrap: wrap;">
                <div style="flex: 1; min-width: 250px; margin-right: 20px;">
                    <h3>[COMPANY1_PLACEHOLDER]</h3>
                    <ul class="references-list">
                        [REFERENCES1_PLACEHOLDER]
                    </ul>
                </div>
                <div style="flex: 1; min-width: 250px;">
                    <h3>[COMPANY2_PLACEHOLDER]</h3>
                    <ul class="references-list">
                        [REFERENCES2_PLACEHOLDER]
                    </ul>
                </div>
            </div>
        </div>

        <div class="footnote">
            <p>This investment analysis was generated on {formatted}, and incorporates available data as of this date. All investment decisions should be made in conjunction with personal financial advice and risk tolerance assessments.</p>
        </div>
    </div>
    </body>
    </html>

    Instructions for the AI:
    - Use all the placeholders above.
    - For the "References" section, list all references from the news data for each company as clickable links, using the format: <li><a href="URL" target="_blank">[Title or short description]</a></li>.
    - Never leave out a section or style, even if data is missing.
    - Clearly state which company, analysis type, or weight is favored.
    - Always keep the format, styling, and order as above.
    """

    user_message = f"The data to analyse: {json.dumps(gathered_data)}"
    # OpenAI API call to create a merged summary
    chat_completion = client.chat.completions.create(
        model="gpt-4.1",  # Ensure that you use a model available in your OpenAI subscription
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_message
            },
        ]
    )

    # Extract and return the AI-generated response
    response = chat_completion.choices[0].message.content
    return response

def get_start_date(timeframe: str) -> str:
    today = datetime.today()
    
    if timeframe == "3 Months":
        start_date = today - relativedelta(months=3)
    elif timeframe == "6 Months":
        start_date = today - relativedelta(months=6)
    elif timeframe == "1 Year":
        start_date = today - relativedelta(years=1)
    else:
        raise ValueError("Invalid timeframe")

    return start_date.strftime('%Y-%m-%d')

def generate_company_news_message(company_name, time_period):
    # Define the messages for different time periods 
    start_date = get_start_date(time_period)
    query = f'"{company_name}" (news OR tweet OR earnings OR downgrade OR acquisition) after:{start_date}'

    
    params = {
        "q": query,
        "api_key": "6bbbb0268f96b1336ac50343fe6ef93a286a74d0f64c3d09fca848c5d62c9cce"
    }

    print(f"\n🔍 Searching SerpAPI with query: {query}")
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        print(results)
        print("✅ SerpAPI search completed")
    except Exception as e:
        print(f"❌ SerpAPI error: {e}")
        return
    
    news = []
    for item in results.get("organic_results", []):
        title = item.get("title", "")
        date = item.get("date", "")
        link = item.get("link", "")
        print(f"\n📄 Scraping: {title}")
        content = extract_diffbot_data(link)

        news.append({
            "title": title,
            "date": date,
            "link": link,
            "content": content
        })

        time.sleep(4)

    #Webhook payload
    payload = {
        "news": news,
        "company": company_name,
        "time_frame": time_period
    }

    print("\n📤 Sending to Make.com webhook...")
    webhook_url = "https://hook.eu2.make.com/s4xsnimg9v87rrrckcwo88d9k57186q6"
    try:
        response = requests.post(webhook_url, json=payload)
        if response.status_code == 200:
            print("✅ Successfully posted to the webhook.")
        else:
            print(f"❌ Webhook error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error posting to webhook: {e}")


 
    print(response.text)

    time.sleep(65)

    credentials_dict = {
        "type": type_sa,
        "project_id": project_id,
        "private_key_id": private_key_id,
        "private_key": private_key,
        "client_email": client_email,
        "client_id": client_id,
        "auth_uri": auth_uri,
        "token_uri": token_uri,
        "auth_provider_x509_cert_url": auth_provider_x509_cert_url,
        "client_x509_cert_url": client_x509_cert_url,
        "universe_domain": universe_domain
    }
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, ["https://www.googleapis.com/auth/spreadsheets"])

    gc = gspread.authorize(credentials)
    sh = gc.open_by_url(google_sheet_url)
    previous = sh.sheet1.get('A2')
    future = sh.sheet1.get('B2')
          
    # chats = client.chat.completions.create(
    #     model="gpt-4o",
    #     messages=[
    #         {
    #             "role": "system",
    #             "content": "You are an artificial intelligence assistant, and your role is to "
    #                 f"present the latest news and updates along with the future news and update for {company_name} in a detailed, organized, and engaging manner."
    #         },
    #         {
    #             "role": "user",
    #             "content": f"Present the news and events aswell {company_name} over the past {time_period} retatining all the Dates aswell as the future news and events: Latest News and Updates text {previous}, Future News and Updates text {future}?"
    #         },
    #     ]
    # )
    # response = chats.choices[0].message.content
    return previous

def extract_diffbot_data(link):
    url = f"https://api.diffbot.com/v3/analyze?url={link}&token=fdbc63a153d0d8da7c0dfb7ccef69945"
    headers = {"accept": "application/json"}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        article = data.get("objects", [])[0]  # Take the first object

        title = article.get("title", "N/A")
        date = article.get("date", "N/A")
        link = article.get("pageUrl", "N/A")
        content = article.get("text", "N/A")

        return content

        #print("🔹 Title:", title)
        #print("📅 Date:", date)
        #print("🔗 Link:", link)
        #print("\n📄 Content:\n", content[:1000], "...")  # Print first 1000 chars for brevity

    except Exception as e:
        print(f"❌ Failed to extract Diffbot data: {e}")
        print(link)

def bollingerbands(company_name, data_text):
    chat_completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You are an AI model designed to assist long-term day traders in analyzing stock market data. "
                    "Your primary task is to interpret stock trading data, especially focusing on Bollinger Bands, "
                    "to identify key market trends. When provided with relevant data you will: "
                    "Analyze the stock's current position relative to its Bollinger Bands (upper, middle, or lower bands) and provide insights."
            },
            {
                "role": "user",
                "content": f"Please analyze the stock data for {company_name}, here is the data {data_text}, What insights can you provide from observing the Bollinger Bands?"
            },
        ]
    )
    response = chat_completion.choices[0].message.content
    return response
def SMA(company_name,data_text):
    
    chat_completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            # System message to define the assistant's behavior
            {
                "role": "system",
                "content":"You are an AI model designed to assist long-term day traders in analyzing stock market data."
                    "Your primary task is to interpret stock trading data, especially focusing on 20, 50, and 200 Simple Moving Averages (SMA),"
                    "to identify key market trends. When provided with relevant data you will:"
                    "\n- Analyze the stock's current position relative to its 20, 50, and 200 SMAs."
                    "\n- Assess if the stock is in an uptrend, downtrend, or nearing a breakout based on the relationships between the SMAs."
                    "\n- Determine if the stock is prone to a reversal by analyzing price movements, SMA crossovers, and the stock's position relative to key SMAs."
                    "\n- Provide a concise, expert-level explanation of your analysis, including how specific SMA characteristics (e.g., crossovers, price deviation from SMAs, trend strength)"
                    "indicate potential market moves."
                    "\n\nEnsure that your explanations are clear and easy to understand, even for users with little to no trading experience, avoiding complex jargon or offering simple definitions where necessary."
                    "Your output should balance depth and simplicity, offering actionable insights for traders while being accessible to non-traders."
                
            },
            # User message with a prompt requesting stock analysis for a specific company
            {
                "role": "user",
                "content": f"Please analyze the stock data for {company_name}, here is the data {data_text}, What insights can you provide from observing SMA?"
                
            },
        ]
    )

# Output the AI's response
    response = chat_completion.choices[0].message.content
    return response


def RSI(company_name,data_text):
    
    chat_completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            # System message to define the assistant's behavior
            {
                "role": "system",
                "content":"You are an AI model designed to assist long-term day traders in analyzing stock market data."
                    "Your primary task is to interpret stock trading data, especially focusing on the Relative Strength Index (RSI),"
                    "to identify key market trends. When provided with relevant data you will:"

                    "\n- Analyze the stock's current RSI values to determine if it is overbought, oversold, or in a neutral range."
                    "\n- Assess if the stock is in an uptrend, downtrend, or nearing a potential reversal based on RSI levels and patterns."
                    "\n- Determine if the stock is prone to a reversal by analyzing RSI divergences (bullish or bearish), overbought/oversold conditions, and the stock's momentum."
                    "\n- Provide a concise, expert-level explanation of your analysis, including how specific RSI characteristics (e.g., divergence, trend strength, threshold breaches)"
                    "indicate potential market moves."
                
            },
            # User message with a prompt requesting stock analysis for a specific company
            {
                "role": "user",
                "content": f"Please analyze the stock data for {company_name}, here is the data {data_text}, What insights can you provide from observing RSI?"
                
            },
        ]
    )

# Output the AI's response
    response = chat_completion.choices[0].message.content
    return response

def MACD(company_name,data_text):
    
    chat_completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            # System message to define the assistant's behavior
            {
                "role": "system",
                "content":"You are an AI model designed to assist long-term day traders in analyzing stock market data."
                    "Your primary task is to interpret stock trading data, especially focusing on the MACD (Moving Average Convergence Divergence), MACD Signal Line, and MACD Histogram,"
                    "to identify key market trends. When provided with relevant data you will:"
                    "\n- Analyze the stock's MACD line, Signal Line, and Histogram to assess trend strength and potential price direction."
                    "\n- Assess if the stock is in an uptrend, downtrend, or nearing a crossover by analyzing the MACD line relative to the Signal Line."
                    "\n- Determine if the stock is prone to a reversal by examining MACD crossovers, divergences, and changes in the MACD Histogram."
                    "\n- Provide a concise, expert-level explanation of your analysis, including how specific MACD characteristics (e.g., crossover points, divergence, histogram changes)"
                    "indicate potential market moves."
                    "\n\nEnsure that your explanations are clear and easy to understand, even for users with little to no trading experience, avoiding complex jargon or offering simple definitions where necessary."
                    "Your output should balance depth and simplicity, offering actionable insights for traders while being accessible to non-traders."
                
            },
            # User message with a prompt requesting stock analysis for a specific company
            {
                "role": "user",
                "content": f"Please analyze the stock data for {company_name}, here is the data {data_text}, What insights can you provide from observing MACD?"
                
            },
        ]
    )

# Output the AI's response
    response = chat_completion.choices[0].message.content
    return response


def OBV(company_name,data_text):
    
    chat_completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            # System message to define the assistant's behavior
            {
                "role": "system",
                "content":"You are an AI model designed to assist long-term day traders in analyzing stock market data."
                    "Your primary task is to interpret stock trading data, especially focusing on On-Balance Volume (OBV),"
                    "to identify key market trends. When provided with relevant data you will:"

                    "\n\n- Read and extract relevant data from PDF and CSV files."
                    "\n- Analyze the stock's OBV to assess the relationship between volume and price movement."
                    "\n- Assess if the stock is in an uptrend, downtrend, or nearing a breakout by evaluating OBV trends and volume momentum."
                    "\n- Determine if the stock is prone to a reversal by analyzing OBV divergences (where OBV moves in the opposite direction of price), which can signal potential trend changes."
                    "\n- Provide a concise, expert-level explanation of your analysis, including how specific OBV characteristics (e.g., divergence, volume spikes, confirmation of price moves)"
                    "indicate potential market moves."

                    "\n\nEnsure that your explanations are clear and easy to understand, even for users with little to no trading experience, avoiding complex jargon or offering simple definitions where necessary."
                    "Your output should balance depth and simplicity, offering actionable insights for traders while being accessible to non-traders."
                
            },
            # User message with a prompt requesting stock analysis for a specific company
            {
                "role": "user",
                "content": f"Please analyze the stock data for {company_name}, here is the data {data_text}, What insights can you provide from observing the OBV?"
                
            },
        ]
    )

# Output the AI's response
    response = chat_completion.choices[0].message.content
    return response


def ADX(company_name,data_text):
    
    chat_completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            # System message to define the assistant's behavior
            {
                "role": "system",
                "content":"You are an AI model designed to assist long-term day traders in analyzing stock market data."
                    "Your primary task is to interpret stock trading data, especially focusing on the Average Directional Index (ADX),"
                    "to identify key market trends. When provided with relevant data you will:"

                    "\n- Analyze the stock's ADX values to assess the strength of the current trend, regardless of its direction."
                    "\n- Assess if the stock is in a strong or weak trend based on ADX levels, with particular attention to rising or falling ADX values."
                    "\n- Determine if the stock is prone to a trend reversal by analyzing ADX indicating whether the market is gaining or losing trend strength."
                    "\n- Provide a concise, expert-level explanation of your analysis, including how specific ADX characteristics (e.g., ADX crossovers, trend strength, or weakening trends)"
                    "indicate potential market moves."

                    "\n\nEnsure that your explanations are clear and easy to understand, even for users with little to no trading experience, avoiding complex jargon or offering simple definitions where necessary."
                    "Your output should balance depth and simplicity, offering actionable insights for traders while being accessible to non-traders."
                
            },
            # User message with a prompt requesting stock analysis for a specific company
            {
                "role": "user",
                "content": f"Please analyze the stock data for {company_name}, here is the data {data_text}, What insights can you provide from observing ADX?"
                
            },
        ]
    )

# Output the AI's response
    response = chat_completion.choices[0].message.content
    return response

def FUNDAMENTAL_ANALYSIS2(file_name, company_name, file):
    system_prompt = """ """

    temp_file_path = os.path.join(tempfile.gettempdir(), file)

# Write the contents to the temporary file
    with open(temp_file_path, 'wb') as temp_file:
        temp_file.write(file_name.read())
    
    message_file = client.files.create(
    file=open(temp_file_path, "rb"), purpose="assistants"
    )

    file_id = message_file.id


    data = {"File_id": file_id, "Company Name": company_name, "File_name": file}

    webhook_url = "https://hook.eu2.make.com/d68cwl3ujkpqmgrnbpgy9mx3d06vs198"
    if webhook_url:
        response = requests.post(webhook_url,data)
    else: 
        print("Error")

    time.sleep(65)

    credentials_dict = {
        "type": type_sa,
        "project_id": project_id,
        "private_key_id": private_key_id,
        "private_key": private_key,
        "client_email": client_email,
        "client_id": client_id,
        "auth_uri": auth_uri,
        "token_uri": token_uri,
        "auth_provider_x509_cert_url": auth_provider_x509_cert_url,
        "client_x509_cert_url": client_x509_cert_url,
        "universe_domain": universe_domain
    }
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, ["https://www.googleapis.com/auth/spreadsheets"])
    gc = gspread.authorize(credentials)
    sh = gc.open_by_url(google_sheet_url)
    anaylsis = sh.sheet1.get('C2')

    chat_completion = client.chat.completions.create(
        model="gpt-4.1",  # Ensure that you use a model available in your OpenAI subscription
        messages=[
            {
                "role": "system",
                "content": (
                "You are an AI model trained to format text for fundamental analysis of financial assets, delivering actionable recommendations. "
                "You must output only valid, structured HTML, using semantic tags such as <section>, <h2>, <h3>, <ul>, <ol>, <li>, <p>, and <strong> for clarity and readability. "
                "Do not use Markdown or plain text—output only HTML.\n"
                "\n"
                "Format your analysis with these sections and formatting standards:\n"
                "\n"
                "<section id='introduction'>\n"
                "  <h2>Introduction</h2>\n"
                "  <p>Provide a concise overview of the asset, including its industry context and the main purpose of the analysis.</p>\n"
                "</section>\n"
                "\n"
                "<section id='financial-analysis'>\n"
                "  <h2>Financial Analysis</h2>\n"
                "  <h3>Income Statement</h3>\n"
                "  <ul>\n"
                "    <li>Summarize trends in <strong>Revenue</strong>, <strong>Cost of Goods Sold</strong>, <strong>Operating Income</strong>, and <strong>Net Income</strong>. Highlight significant changes or growth patterns.</li>\n"
                "  </ul>\n"
                "  <h3>Balance Sheet</h3>\n"
                "  <ul>\n"
                "    <li>Summarize <strong>Assets</strong>, <strong>Liabilities</strong>, and <strong>Equity</strong>, focusing on liquidity and leverage metrics.</li>\n"
                "  </ul>\n"
                "  <h3>Cash Flow Statement</h3>\n"
                "  <ul>\n"
                "    <li>Highlight <strong>Cash Flow from Operating</strong>, <strong>Investing</strong>, and <strong>Financing Activities</strong>, emphasizing cash generation and any unusual patterns.</li>\n"
                "  </ul>\n"
                "  <h3>Key Ratios and Metrics</h3>\n"
                "  <ul>\n"
                "    <li><strong>Profitability Ratios</strong> (e.g., <strong>Gross Margin</strong>, <strong>Return on Assets</strong>)</li>\n"
                "    <li><strong>Liquidity Ratios</strong> (e.g., <strong>Current Ratio</strong>, <strong>Quick Ratio</strong>)</li>\n"
                "    <li><strong>Leverage Ratios</strong> (e.g., <strong>Debt-to-Equity Ratio</strong>)</li>\n"
                "    <li><strong>Valuation Ratios</strong> (e.g., <strong>Price-to-Earnings Ratio (P/E)</strong>, <strong>Price-to-Book Ratio (P/B)</strong>)</li>\n"
                "  </ul>\n"
                "</section>\n"
                "\n"
                "<section id='competitive-market-analysis'>\n"
                "  <h2>Competitive Positioning and Market Analysis</h2>\n"
                "  <ul>\n"
                "    <li>Overview of the asset’s competitive position, market share, and primary competitors.</li>\n"
                "    <li>Summary of industry trends and a concise <strong>SWOT analysis</strong> (strengths, weaknesses, opportunities, threats).</li>\n"
                "  </ul>\n"
                "</section>\n"
                "\n"
                "<section id='management-governance'>\n"
                "  <h2>Management and Governance</h2>\n"
                "  <ul>\n"
                "    <li>Describe the executive team and board structure, noting experience, past performance, and recent changes.</li>\n"
                "    <li>Mention recent strategic decisions (e.g., acquisitions, new product lines) that have impacted performance.</li>\n"
                "  </ul>\n"
                "</section>\n"
                "\n"
                "<section id='conclusion-outlook'>\n"
                "  <h2>Conclusion and Outlook</h2>\n"
                "  <ul>\n"
                "    <li>Concise summary of strengths and potential risks based on financial and strategic positioning.</li>\n"
                "    <li>Outlook considering financial stability, industry conditions, and management’s strategic direction.</li>\n"
                "  </ul>\n"
                "</section>\n"
                "\n"
                "<section id='actionable-recommendations'>\n"
                "  <h2>Actionable Recommendations</h2>\n"
                "  <ol>\n"
                "    <li><strong>Investment Recommendation:</strong> Clearly state Buy, Hold, or Sell, and justify with reference to valuation, market, or management actions.</li>\n"
                "    <li><strong>Risk Management Suggestions:</strong> Outline risk mitigation strategies (e.g., diversification, stop-loss orders).</li>\n"
                "    <li><strong>Strategic Suggestions for Management:</strong> If relevant, suggest actions for the company (e.g., explore new markets, reduce debt, optimize costs).</li>\n"
                "    <li><strong>Performance Monitoring Tips:</strong> Recommend specific metrics or events (e.g., quarterly earnings, regulatory updates) for ongoing evaluation.</li>\n"
                "  </ol>\n"
                "</section>\n"


                "Style Requirements"
                "Maintain a professional, objective tone focused on analysis without personal opinions."
                "Avoid excessive jargon; use clear, direct explanations where needed."
                "Keep sentences and paragraphs clear and direct for logical flow and easy understanding."
                "Include all sections and headings as listed, even if a section is brief. Output only valid HTML."
                    
                ),
            },
            {
                "role": "user",
                "content": (
                    f"fromat this text {anaylsis}"   
                ),
            },
        ]
    )

    # Extract and return the AI-generated response
    response = chat_completion.choices[0].message.content

    deleted_vector_store_file = client.vector_stores.files.delete(
        vector_store_id="vs_67e6701fdd908191bccc587ac16d2e11",
        file_id=file_id
    )
    
    print("File successfully deleted from vector store.")
    return response 
    

def FUNDAMENTAL_ANALYSIS(file_name, company_name, file):

    temp_file_path = os.path.join(tempfile.gettempdir(), file)

# Write the contents to the temporary file
    with open(temp_file_path, 'wb') as temp_file:
        temp_file.write(file_name.read())
    
    message_file = client.files.create(
    file=open(temp_file_path, "rb"), purpose="assistants"
    )

    file_id = message_file.id


    data = {"File_id": file_id, "Company Name": company_name, "File_name": file}

    webhook_url = "https://hook.eu2.make.com/d68cwl3ujkpqmgrnbpgy9mx3d06vs198"
    if webhook_url:
        response = requests.post(webhook_url,data)
    else: 
        print("Error")

    time.sleep(65)

    credentials_dict = {
        "type": type_sa,
        "project_id": project_id,
        "private_key_id": private_key_id,
        "private_key": private_key,
        "client_email": client_email,
        "client_id": client_id,
        "auth_uri": auth_uri,
        "token_uri": token_uri,
        "auth_provider_x509_cert_url": auth_provider_x509_cert_url,
        "client_x509_cert_url": client_x509_cert_url,
        "universe_domain": universe_domain
    }
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, ["https://www.googleapis.com/auth/spreadsheets"])
    gc = gspread.authorize(credentials)
    sh = gc.open_by_url(google_sheet_url)
    anaylsis = sh.sheet1.get('C2')

    chat_completion = client.chat.completions.create(
        model="gpt-4.1",  # Ensure that you use a model available in your OpenAI subscription
        messages=[
            {
                "role": "system",
                "content": (
                "You are an AI model trained to format text for fundamental analysis of financial assets, delivering actionable recommendations. "
                "You must output only valid, structured HTML, using semantic tags such as <section>, <h2>, <h3>, <ul>, <ol>, <li>, <p>, and <strong> for clarity and readability. "
                "Do not use Markdown or plain text—output only HTML.\n"
                "\n"
                "Format your analysis with these sections and formatting standards:\n"
                "\n"
                "<section id='introduction'>\n"
                "  <h2>Introduction</h2>\n"
                "  <p>Provide a concise overview of the asset, including its industry context and the main purpose of the analysis.</p>\n"
                "</section>\n"
                "\n"
                "<section id='financial-analysis'>\n"
                "  <h2>Financial Analysis</h2>\n"
                "  <h3>Income Statement</h3>\n"
                "  <ul>\n"
                "    <li>Summarize trends in <strong>Revenue</strong>, <strong>Cost of Goods Sold</strong>, <strong>Operating Income</strong>, and <strong>Net Income</strong>. Highlight significant changes or growth patterns.</li>\n"
                "  </ul>\n"
                "  <h3>Balance Sheet</h3>\n"
                "  <ul>\n"
                "    <li>Summarize <strong>Assets</strong>, <strong>Liabilities</strong>, and <strong>Equity</strong>, focusing on liquidity and leverage metrics.</li>\n"
                "  </ul>\n"
                "  <h3>Cash Flow Statement</h3>\n"
                "  <ul>\n"
                "    <li>Highlight <strong>Cash Flow from Operating</strong>, <strong>Investing</strong>, and <strong>Financing Activities</strong>, emphasizing cash generation and any unusual patterns.</li>\n"
                "  </ul>\n"
                "  <h3>Key Ratios and Metrics</h3>\n"
                "  <ul>\n"
                "    <li><strong>Profitability Ratios</strong> (e.g., <strong>Gross Margin</strong>, <strong>Return on Assets</strong>)</li>\n"
                "    <li><strong>Liquidity Ratios</strong> (e.g., <strong>Current Ratio</strong>, <strong>Quick Ratio</strong>)</li>\n"
                "    <li><strong>Leverage Ratios</strong> (e.g., <strong>Debt-to-Equity Ratio</strong>)</li>\n"
                "    <li><strong>Valuation Ratios</strong> (e.g., <strong>Price-to-Earnings Ratio (P/E)</strong>, <strong>Price-to-Book Ratio (P/B)</strong>)</li>\n"
                "  </ul>\n"
                "</section>\n"
                "\n"
                "<section id='competitive-market-analysis'>\n"
                "  <h2>Competitive Positioning and Market Analysis</h2>\n"
                "  <ul>\n"
                "    <li>Overview of the asset’s competitive position, market share, and primary competitors.</li>\n"
                "    <li>Summary of industry trends and a concise <strong>SWOT analysis</strong> (strengths, weaknesses, opportunities, threats).</li>\n"
                "  </ul>\n"
                "</section>\n"
                "\n"
                "<section id='management-governance'>\n"
                "  <h2>Management and Governance</h2>\n"
                "  <ul>\n"
                "    <li>Describe the executive team and board structure, noting experience, past performance, and recent changes.</li>\n"
                "    <li>Mention recent strategic decisions (e.g., acquisitions, new product lines) that have impacted performance.</li>\n"
                "  </ul>\n"
                "</section>\n"
                "\n"
                "<section id='conclusion-outlook'>\n"
                "  <h2>Conclusion and Outlook</h2>\n"
                "  <ul>\n"
                "    <li>Concise summary of strengths and potential risks based on financial and strategic positioning.</li>\n"
                "    <li>Outlook considering financial stability, industry conditions, and management’s strategic direction.</li>\n"
                "  </ul>\n"
                "</section>\n"
                "\n"
                "<section id='actionable-recommendations'>\n"
                "  <h2>Actionable Recommendations</h2>\n"
                "  <ol>\n"
                "    <li><strong>Investment Recommendation:</strong> Clearly state Buy, Hold, or Sell, and justify with reference to valuation, market, or management actions.</li>\n"
                "    <li><strong>Risk Management Suggestions:</strong> Outline risk mitigation strategies (e.g., diversification, stop-loss orders).</li>\n"
                "    <li><strong>Strategic Suggestions for Management:</strong> If relevant, suggest actions for the company (e.g., explore new markets, reduce debt, optimize costs).</li>\n"
                "    <li><strong>Performance Monitoring Tips:</strong> Recommend specific metrics or events (e.g., quarterly earnings, regulatory updates) for ongoing evaluation.</li>\n"
                "  </ol>\n"
                "</section>\n"


                "Style Requirements"
                "Maintain a professional, objective tone focused on analysis without personal opinions."
                "Avoid excessive jargon; use clear, direct explanations where needed."
                "Keep sentences and paragraphs clear and direct for logical flow and easy understanding."
                "Include all sections and headings as listed, even if a section is brief. Output only valid HTML."
                    
                ),
            },
            {
                "role": "user",
                "content": (
                    f"fromat this text {anaylsis}"   
                ),
            },
        ]
    )

    # Extract and return the AI-generated response
    response = chat_completion.choices[0].message.content

    deleted_vector_store_file = client.vector_stores.files.delete(
        vector_store_id="vs_67e6701fdd908191bccc587ac16d2e11",
        file_id=file_id
    )
    
    print("File successfully deleted from vector store.")
    return response 
    
   
def SUMMARY(company_name, BD, SMA, RSI, MACD, OBV, ADX, weighted_score, weight_choice):
    chat_completion = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an AI model designed to assist long-term day traders in analyzing stock market data using a weighted approach."
                    " Your primary role is to synthesize data from multiple technical indicators—both lagging (MACD, SMA) and leading (ADX, RSI, OBV, Bollinger Bands)—"
                    " and deliver a single, clear, actionable conclusion about the stock's long-term trend."
                    "\n\n"
                    "When analyzing the indicators provided, you must:"
                    "\n- Extract and interpret the key signals from each indicator summary."
                    "\n- Weigh the importance of each indicator according to the selected weighting style (for example, 'Long Term' prioritizes slow-moving trends, 'Short Term' prioritizes fast-moving ones, and 'Default' is balanced)."
                    "\n- Calculate or use the provided *weighted score* to support your conclusion (the weighted score is a summary value reflecting the overall strength and direction of the combined indicators, weighted according to the chosen style)."
                    "\n- Make your final advice based on this weighted approach, ensuring that the recommendation aligns with the weighted score and selected style."
                    "\n\n"
                    "Guidelines for your output:"
                    "\n- Limit your response to ONE concise paragraph."
                    "\n- Clearly state the overall trend (e.g., strengthening, weakening, reversal) and the recommended action."
                    "\n- Bold your suggested position (e.g., **Strong Buy**, **Hold**, **Sell**), and mention whether the weighted score and weighting style support this choice."
                    "\n- Do NOT output individual indicator details or jargon—focus on the summary and recommendation."
                    "\n- Ensure your response is simple, actionable, and understandable for a non-trader."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Summarize the stock data for {company_name}. "
                    f"Bollinger Bands: {BD}, "
                    f"Simple Moving Averages: {SMA}, "
                    f"Relative Strength Index: {RSI}, "
                    f"MACD: {MACD}, "
                    f"OBV: {OBV}, "
                    f"ADX: {ADX}."
                    f" Use the weighting style: {weight_choice}. The combined weighted score is: {weighted_score}"
                )
            },
        ]
    )

    response = chat_completion.choices[0].message.content
    return response

    
    

def SUMMARY2(gathered_data):
    today = date.today()
    formatted = today.strftime('%Y-%m-%d')


    system_prompt = f"""
    As an AI assistant dedicated to supporting traders and investors, your task is to produce a structured, detailed technical market analysis comparing TWO companies, in valid HTML format.
    The user will provide a JSON object containing all the data needed for technical analysis, including:
    - Ticker: The stock ticker symbol (primary company)
    - Company: The first company name
    - Company 2: The second company name
    - Timeframe: The analysis timeframe
    - Technical indicators/results for BOTH companies (SMA, RSI, MACD, OBV, ADX, and summaries)

    **Instructions:**
    - Parse the provided JSON and compare the technical analysis of both companies side by side.
    - Extract and display Ticker, Company, Company 2, and Timeframe.
    - Present technical indicator results (SMA, RSI, MACD, OBV, ADX) for both companies in a comparison table.
    - Summarize and compare technical analysis findings for each company in parallel sections.
    - Generate a clear, actionable recommendation (BUY, HOLD, or SELL) for each company **and** state which is stronger and why.
    - Justify each recommendation, citing which technical factors are most important.
    - Highlight the key differences and strengths/weaknesses between the companies.
    - Return the complete HTML document as your response. Do not include Markdown or plaintext.

    Your output must use <section>, <h2>, <h3>, <ul>, <li>, <table>, and <p> tags as appropriate. Use <strong> for key points.

    Follow this professional HTML template structure (do not omit any section or styling):

    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Technical Investment Analysis Comparison</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1200px;
                margin: 0 auto;
                padding: 0px;
                background-color: transparent;
            }}
            .container {{
                background-color: #fff;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                padding: 30px;
                margin-bottom: 30px;
            }}
            h1 {{
                color: #2c3e50;
                border-bottom: 3px solid #3498db;
                padding-bottom: 10px;
                margin-top: 0;
            }}
            h2 {{
                color: #2c3e50;
                border-left: 5px solid #3498db;
                padding-left: 15px;
                margin-top: 30px;
                background-color: #f8f9fa;
                padding: 10px 15px;
                border-radius: 0 5px 5px 0;
            }}
            h3 {{
                color: #2c3e50;
                margin-top: 20px;
                border-bottom: 1px dashed #ddd;
                padding-bottom: 5px;
            }}
            .section {{
                margin-bottom: 30px;
                padding: 20px;
                background-color: #f9f9f9;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            }}
            .recommendation {{
                font-weight: bold;
                font-size: 1.1em;
                padding: 15px;
                margin: 15px 0;
                border-radius: 5px;
                text-align: center;
            }}
            .buy {{
                background-color: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }}
            .hold {{
                background-color: #fff3cd;
                color: #856404;
                border: 1px solid #ffeeba;
            }}
            .sell {{
                background-color: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }}
            .indicator {{
                margin-bottom: 20px;
                padding: 15px;
                border-radius: 5px;
                background-color: #f8f9fa;
                border-left: 4px solid #3498db;
            }}
            .indicator h4 {{
                margin-top: 0;
                color: #2980b9;
            }}
            .summary-box {{
                background-color: #e8f4fd;
                border-left: 4px solid #3498db;
                padding: 15px;
                margin: 20px 0;
                border-radius: 0 5px 5px 0;
            }}
            .timeframe {{
                font-weight: bold;
                color: #2c3e50;
                background-color: #e8f4fd;
                padding: 5px 10px;
                border-radius: 3px;
                display: inline-block;
                margin-bottom: 15px;
            }}
            .footnote {{
                font-size: 0.9em;
                font-style: italic;
                color: #6c757d;
                margin-top: 30px;
                padding-top: 15px;
                border-top: 1px solid #dee2e6;
            }}
            .highlight {{
                background-color: #ffeaa7;
                padding: 2px 4px;
                border-radius: 3px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }}
            th, td {{
                border: 1px solid #ccc;
                padding: 10px;
                text-align: center;
                font-size: 1em;
            }}
            th {{
                background-color: #e8f4fd;
                color: #2c3e50;
            }}
        </style>
    </head>
    <body>
    <div class="container">
        <h1>Technical Analysis Comparison: [COMPANY1] vs [COMPANY2]</h1>
        <div class="timeframe">Analysis Timeframe: [TIMEFRAME]</div>

        <section class="section">
            <h2>Executive Summary</h2>
            <div class="summary-box">
                <div style="display: flex; flex-wrap: wrap;">
                    <div style="flex: 1; min-width: 250px; margin-right: 20px;">
                        <h3>[COMPANY1]</h3>
                        <p>[SUMMARY1]</p>
                    </div>
                    <div style="flex: 1; min-width: 250px;">
                        <h3>[COMPANY2]</h3>
                        <p>[SUMMARY2]</p>
                    </div>
                </div>
            </div>
            <div class="recommendation [REC1_CLASS]">[COMPANY1] RECOMMENDATION: [REC1]</div>
            <div class="recommendation [REC2_CLASS]">[COMPANY2] RECOMMENDATION: [REC2]</div>
        </section>

        <section class="section">
            <h2>Technical Indicator Comparison Table</h2>
            <table>
                <tr>
                    <th>Indicator</th>
                    <th>[COMPANY1]</th>
                    <th>[COMPANY2]</th>
                </tr>
                <tr>
                    <td>SMA</td>
                    <td>[SMA1]</td>
                    <td>[SMA2]</td>
                </tr>
                <tr>
                    <td>RSI</td>
                    <td>[RSI1]</td>
                    <td>[RSI2]</td>
                </tr>
                <tr>
                    <td>MACD</td>
                    <td>[MACD1]</td>
                    <td>[MACD2]</td>
                </tr>
                <tr>
                    <td>OBV</td>
                    <td>[OBV1]</td>
                    <td>[OBV2]</td>
                </tr>
                <tr>
                    <td>ADX</td>
                    <td>[ADX1]</td>
                    <td>[ADX2]</td>
                </tr>
            </table>
        </section>

        <section class="section">
            <h2>Detailed Technical Analysis</h2>
            <div style="display: flex; flex-wrap: wrap;">
                <div style="flex: 1; min-width: 250px; margin-right: 20px;">
                    <h3>[COMPANY1]</h3>
                    <div class="indicator"><h4>SMA</h4><p>[SMA1_DETAIL]</p></div>
                    <div class="indicator"><h4>RSI</h4><p>[RSI1_DETAIL]</p></div>
                    <div class="indicator"><h4>MACD</h4><p>[MACD1_DETAIL]</p></div>
                    <div class="indicator"><h4>OBV</h4><p>[OBV1_DETAIL]</p></div>
                    <div class="indicator"><h4>ADX</h4><p>[ADX1_DETAIL]</p></div>
                </div>
                <div style="flex: 1; min-width: 250px;">
                    <h3>[COMPANY2]</h3>
                    <div class="indicator"><h4>SMA</h4><p>[SMA2_DETAIL]</p></div>
                    <div class="indicator"><h4>RSI</h4><p>[RSI2_DETAIL]</p></div>
                    <div class="indicator"><h4>MACD</h4><p>[MACD2_DETAIL]</p></div>
                    <div class="indicator"><h4>OBV</h4><p>[OBV2_DETAIL]</p></div>
                    <div class="indicator"><h4>ADX</h4><p>[ADX2_DETAIL]</p></div>
                </div>
            </div>
        </section>

        <section class="section">
            <h2>Integrated Comparative Analysis & Final Recommendation</h2>
            <p>[COMPARATIVE_ANALYSIS]</p>
            <div class="summary-box">
                <p><strong>Best Opportunity:</strong> [BEST_OPPORTUNITY]</p>
                <p><strong>Entry Points:</strong> [ENTRY_POINTS]</p>
                <p><strong>Exit Strategy:</strong> [EXIT_STRATEGY]</p>
                <p><strong>Risk Management:</strong> [RISK_MANAGEMENT]</p>
            </div>
        </section>

        <div class="footnote">
            <p>This investment analysis was generated on {formatted}, and incorporates available data as of this date. All investment decisions should be made in conjunction with personal financial advice and risk tolerance assessments.</p>
        </div>
    </div>
    </body>
    </html>
    """


    user_message = f"The data to analyse: {json.dumps(gathered_data)}"
    chat_completion = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                # System message to define the assistant's behavior
            {
                    "role": "system",
                    "content":  system_prompt
                                    
            },
            # User message with a prompt requesting stock analysis for a specific company
            {
                "role": "user",
                "content": user_message
                    
            },
        ]
    )

# Output the AI's response
    response = chat_completion.choices[0].message.content
    return response

def format_news(txt_summary):
    chat_completion = client.chat.completions.create(
    model="gpt-4.1",
    messages=[
        {
            "role": "system",
            "content": (
                "You are an AI model designed to convert recent event data into a clean, professionally formatted HTML summary.\n\n"
                "Your task is to transform each event into a structured HTML entry that is easy to read and suitable for use in reports, dashboards, or investor updates.\n\n"
                "The user will provide a list of events in structured text or JSON format. Each event contains:\n"
                "- Date\n"
                "- Title\n"
                "- Overview\n"
                "- Impact\n"
                "- Source\n\n"
                "You must format this information using the HTML structure below:\n\n"
                "<div style=\"font-size:12pt; margin-bottom:20px; font-family:Arial, sans-serif;\">\n"
                "  <strong>Date: [DATE] — Event: [TITLE]</strong><br/>\n"
                "  <p><strong>Overview:</strong> [OVERVIEW]</p>\n"
                "  <p><strong>Impact:</strong> [IMPACT]</p>\n"
                "  <p><strong>Source:</strong> [SOURCE]</p>\n"
                "</div>\n\n"
                "Formatting Guidelines:\n"
                "- Use 12pt font consistently.\n"
                "- Separate sections with <p> tags.\n"
                "- Replace all [PLACEHOLDER] entries with actual event content.\n"
                "- Output valid, clean HTML only — no extra narrative, no markdown.\n\n"
                "Return one complete <div> block per event."
            )
        },
        {
            "role": "user",
            "content": f"text to format {txt_summary}"
        }
    ]
)


# Output the AI's response
    response = chat_completion.choices[0].message.content
    return response



def calculate_technical_indicators(data, ticker, weight_choice=None):
    """
    Calculate various technical indicators, prepare them for AI analysis,
    and compute a weighted technical score.

    Args:
        data (pd.DataFrame): The input financial data.
        ticker (str): The stock ticker.
        weights (dict): Optional dict of weights for each indicator.

    Returns:
        Tuple: (results dict, recent_data, availability, scores, weighted_score)
    """
    short_term_weights = {
    "sma": 0.1,
    "rsi": 0.3,
    "macd": 0.3,
    "obv": 0.1,
    "adx": 0.1,
    "bbands": 0.1
    }
    long_term_weights = {
        "sma": 0.4,
        "rsi": 0.1,
        "macd": 0.15,
        "obv": 0.15,
        "adx": 0.2,
        "bbands": 0.0
    }

    weights = {
            "sma": 0.2,
            "rsi": 0.2,
            "macd": 0.2,
            "obv": 0.2,
            "adx": 0.2,
            "bbands": 0.0  # Set to 0 if not using
        }

# Choose the right weights
    if weight_choice == "Short Term":
        weights = short_term_weights
    if weight_choice == "Long Term":
        weights = long_term_weights
    if weight_choice == "Default":
        weights = weights

    # --- Default Weights if not provided ---

    # Initialize availability flags
    sma_available = False
    rsi_available = False
    macd_available = False
    obv_available = False
    adx_available = False
    bbands_available = False

    # --- Calculate SMA ---
    if 'Close' in data.columns:
        data['SMA_20'] = ta.sma(data['Close'], length=20)
        data['SMA_50'] = ta.sma(data['Close'], length=50)
        data['SMA_200'] = ta.sma(data['Close'], length=200)
        sma_available = data[['SMA_20', 'SMA_50', 'SMA_200']].notna().any().any()

    # --- Calculate RSI ---
    if 'Close' in data.columns:
        data['RSI'] = ta.rsi(data['Close'], length=14)
        rsi_available = 'RSI' in data.columns and data['RSI'].notna().any()

    # --- Calculate MACD ---
    macd = ta.macd(data['Close'])
    if macd is not None and all(col in macd.columns for col in ['MACD_12_26_9', 'MACDs_12_26_9', 'MACDh_12_26_9']):
        data['MACD'] = macd['MACD_12_26_9']
        data['MACD_signal'] = macd['MACDs_12_26_9']
        data['MACD_hist'] = macd['MACDh_12_26_9']
        macd_available = True

    # --- Calculate OBV ---
    if 'Close' in data.columns and 'Volume' in data.columns:
        data['OBV'] = ta.obv(data['Close'], data['Volume'])
        obv_available = 'OBV' in data.columns and data['OBV'].notna().any()

    # --- Calculate ADX ---
    adx = ta.adx(data['High'], data['Low'], data['Close'])
    if adx is not None and 'ADX_14' in adx.columns:
        data['ADX'] = adx['ADX_14']
        adx_available = True

    # --- Calculate Bollinger Bands ---
    bbands = ta.bbands(data['Close'], length=20, std=2)
    if bbands is not None and all(col in bbands.columns for col in ['BBU_20_2.0', 'BBM_20_2.0', 'BBL_20_2.0']):
        data['upper_band'] = bbands['BBU_20_2.0']
        data['middle_band'] = bbands['BBM_20_2.0']
        data['lower_band'] = bbands['BBL_20_2.0']
        bbands_available = True

    # --- Resample data weekly ---
    data = data.resample('W').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum',
        'SMA_20': 'last',
        'SMA_50': 'last',
        'SMA_200': 'last',
        'RSI': 'last',
        'MACD': 'last',
        'MACD_signal': 'last',
        'MACD_hist': 'last',
        'OBV': 'last',
        'ADX': 'last',
        'upper_band': 'last',
        'middle_band': 'last',
        'lower_band': 'last'
    })

    # --- Prepare data for analysis ---
    recent_data = data

    # --- Run your original analysis functions (these return text) ---
    results = {
        "bd_result": bollingerbands(ticker, recent_data[["Open", "High", "Low", "Close", "Volume", "upper_band", "middle_band", "lower_band"]].to_markdown()),
        "sma_result": SMA(ticker, recent_data[["Open", "High", "Low", "Close", "SMA_20", "SMA_50", "SMA_200"]].to_markdown()) if sma_available else "SMA analysis not available.",
        "rsi_result": RSI(ticker, recent_data[["Open", "High", "Low", "Close", "RSI"]].to_markdown()) if rsi_available else "RSI analysis not available.",
        "macd_result": MACD(ticker, recent_data[["Open", "High", "Low", "Close", "MACD", "MACD_signal", "MACD_hist"]].to_markdown()) if macd_available else "MACD analysis not available.",
        "obv_result": OBV(ticker, recent_data[["Open", "High", "Low", "Close", "Volume", "OBV"]].to_markdown()) if obv_available else "OBV analysis not available.",
        "adx_result": ADX(ticker, recent_data[["Open", "High", "Low", "Close", "ADX"]].to_markdown()) if adx_available else "ADX analysis not available."
    }

    availability = {
        "sma_available": sma_available,
        "rsi_available": rsi_available,
        "macd_available": macd_available,
        "obv_available": obv_available,
        "adx_available": adx_available,
        "bbands_available": bbands_available
    }

    # --- SCORING SECTION (replace these with your real logic!) ---
    last = recent_data.iloc[-1]  # Last row (most recent week)
    scores = {}

    # Simple scoring logic (customize as needed)
    # Bullish (+1), Bearish (-1), Neutral (0)
    scores['sma'] = 1 if sma_available and last['Close'] > last['SMA_20'] else -1 if sma_available else 0
    scores['rsi'] = 1 if rsi_available and last['RSI'] > 55 else -1 if rsi_available and last['RSI'] < 45 else 0
    scores['macd'] = 1 if macd_available and last['MACD'] > last['MACD_signal'] else -1 if macd_available else 0
    scores['obv'] = 1 if obv_available and last['OBV'] > 0 else -1 if obv_available and last['OBV'] < 0 else 0
    scores['adx'] = 1 if adx_available and last['ADX'] > 20 else -1 if adx_available and last['ADX'] < 20 else 0
    scores['bbands'] = 1 if bbands_available and last['Close'] > last['middle_band'] else -1 if bbands_available else 0

    # --- Weighted score ---
    total_weight = sum([weights.get(k, 0) for k in scores if availability.get(f"{k}_available", False)])
    weighted_score = sum(
        scores[k] * weights.get(k, 0)
        for k in scores if availability.get(f"{k}_available", False)
    ) / total_weight if total_weight > 0 else 0

    # --- RETURN everything ---
    return results, recent_data, availability, scores, weighted_score



def update_progress(progress_bar, stage, progress, message):
    progress_bar.progress(progress)
    st.text(message)
    st.empty()

def plot_sma(data):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.index, y=data['Close'], mode='lines', name='Close Price', line=dict(color='blue')))
    fig.add_trace(go.Scatter(x=data.index, y=data['SMA_20'], mode='lines', name='SMA 20', line=dict(color='orange', dash='dash')))
    fig.add_trace(go.Scatter(x=data.index, y=data['SMA_50'], mode='lines', name='SMA 50', line=dict(color='red', dash='dash')))
    fig.add_trace(go.Scatter(x=data.index, y=data['SMA_200'], mode='lines', name='SMA 200', line=dict(color='green', dash='dash')))
    return fig

# Function to plot Bollinger Bands
def plot_bbands(data):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.index, y=data['upper_band'], mode='lines', name='Upper Band', line=dict(color='cyan', dash='dot')))
    fig.add_trace(go.Scatter(x=data.index, y=data['middle_band'], mode='lines', name='Middle Band', line=dict(color='magenta', dash='dot')))
    fig.add_trace(go.Scatter(x=data.index, y=data['lower_band'], mode='lines', name='Lower Band', line=dict(color='cyan', dash='dot')))
    return fig

# Function to plot RSI
def plot_rsi(data):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.index, y=data['RSI'], mode='lines', name='RSI', line=dict(color='purple')))
    fig.add_hline(y=70, line=dict(color='red', dash='dash'))
    fig.add_hline(y=30, line=dict(color='green', dash='dash'))
    return fig

# Function to plot MACD
def plot_macd(data):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.index, y=data['MACD'], mode='lines', name='MACD', line=dict(color='blue')))
    fig.add_trace(go.Scatter(x=data.index, y=data['MACD_signal'], mode='lines', name='MACD Signal', line=dict(color='red')))
    fig.add_trace(go.Bar(x=data.index, y=data['MACD_hist'], name='MACD Histogram', marker_color='gray', opacity=0.5))
    return fig

# Function to plot OBV
def plot_obv(data):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.index, y=data['OBV'], mode='lines', name='OBV', line=dict(color='brown')))
    return fig

# Function to plot ADX
def plot_adx(data):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.index, y=data['ADX'], mode='lines', name='ADX', line=dict(color='orange')))
    return fig


def main():
    stock_page()

if __name__ == "__main__":
    main()