import streamlit as st
import time
from datetime import datetime
import pandas as pd
import base64
import io

# Import your existing script functions
from ay_ambot import validate_token, process_and_analyze_chats  # assuming your current script is named ay_ambot.py

def create_download_link(df):
    """Generate a download link for the CSV file"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    filename = f'chat_sentiment_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    return f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'

def main():
    # Display logo and title centered
    st.markdown(
        """
        <div style='text-align: center;'>
            <img src='data:image/png;base64,{}' width='150'>
            <h1 style='margin-top: 10px; font-size: 2em; display: inline-block;'>Data Team LiveChat Sentiment Analysis</h1>
        </div>
        """.format(get_image_as_base64("C:/Users/PM - Shift/Downloads/My Icons/Cenix Logo.png")),
        unsafe_allow_html=True
    )
    
    # Create input fields
    account_id = st.text_input('Account ID')
    token = st.text_input('Personal Access Token', type='password')
    
    # Date input fields
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input('Start Date')
    with col2:
        end_date = st.date_input('End Date')
    
    # Process button
    if st.button('Process Chats'):
        if not account_id or not token:
            st.error('Please enter both Account ID and Token')
            return
            
        # Show progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Process the chats
            status_text.text('Fetching and analyzing chats...')
            
            # Convert dates to string format
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')
            
            # Call your processing function
            result = process_and_analyze_chats(account_id, token, start_date_str, end_date_str)
            
            if result:
                # Assuming the CSV is saved in the current directory
                filename = f'chat_sentiment_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
                df = pd.read_csv(filename)
                
                # Update progress
                progress_bar.progress(100)
                status_text.text('Analysis complete!')
                
                # Show success message and download button
                st.success('Chat analysis completed successfully!')
                st.markdown(create_download_link(df), unsafe_allow_html=True)
                
                # Display preview of the data
                st.subheader('Preview of Analysis Results:')
                st.dataframe(df.head())
                
            else:
                st.error('An error occurred during processing')
                
        except Exception as e:
            st.error(f'Error: {str(e)}')
            
def get_image_as_base64(image_path):
    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode()
    return encoded_string

if __name__ == '__main__':
    main()
