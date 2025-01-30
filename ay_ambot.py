import requests
import json
import base64
from datetime import datetime, timedelta
from textblob import TextBlob
import re
import pandas as pd
import os

def validate_token(token):
    """Validate token format and basic structure"""
    if not token:
        return False
    # Basic check - tokens are usually longer than 20 characters
    if len(token) < 20:
        return False
    return True

def get_token_region(token):
    """Extract region from token prefix"""
    if token.startswith('dal:'):
        return 'dal'
    elif token.startswith('fra:'):
        return 'fra'
    return None

def create_basic_auth_header(token):
    """Create Basic Auth header from PAT"""
    # For PATs, we use the token as both username and password
    auth_string = base64.b64encode(f"{token}:".encode('utf-8')).decode('utf-8')
    return f"Basic {auth_string}"

def validate_date(date_string):
    """Validate date format"""
    try:
        return datetime.strptime(date_string, "%Y-%m-%d")
    except ValueError:
        return None

def get_date_range(start_date_str=None, end_date_str=None):
    """Get date range in ISO format"""
    if not start_date_str or not end_date_str:
        # Default to last 7 days if no dates provided
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)
    else:
        # Convert input dates to datetime objects
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        # Set end_date to end of day
        end_date = end_date.replace(hour=23, minute=59, second=59)
    
    # Format dates in ISO 8601 format with microseconds
    return (
        start_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        end_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    )

def process_and_analyze_chats(account_id, token, start_date=None, end_date=None):
    """
    Download chat transcripts and perform sentiment analysis directly
    """
    # Get date range
    from_date, to_date = get_date_range(start_date, end_date)
    print(f"\nFetching chats from {from_date} to {to_date}")
    
    # API endpoint and headers setup
    url = "https://api.livechatinc.com/v3.5/agent/action/list_archives"
    auth_string = base64.b64encode(f"{account_id}:{token}".encode('utf-8')).decode('utf-8')
    headers = {
        'Authorization': f'Basic {auth_string}',
        'Content-Type': 'application/json'
    }
    
    if token.startswith(('dal:', 'fra:')):
        region = token.split(':')[0]
        headers['X-Region'] = region
        print(f"Using region: {region}")

    # Initialize variables
    all_chats = []
    page_id = None
    total_chats = 0
    results = []

    try:
        # Fetch all chats (pagination logic)
        while True:
            payload = {
                "filters": {
                    "from": from_date,
                    "to": to_date
                },
                "limit": 100
            }
            if page_id:
                payload["page_id"] = page_id

            print(f"\nFetching chats (current total: {total_chats})...")
            response = requests.post(url, headers=headers, json=payload)
            
            if response.status_code != 200:
                print(f"\nError Details:")
                print(f"Status Code: {response.status_code}")
                print(f"Response Body: {response.text}")
                return False
                
            data = response.json()
            chats = data.get('chats', [])
            
            if not chats:
                break
                
            # Process each chat directly
            for chat in chats:
                # Get created_at and thread_id from thread
                created_at = 'N/A'
                thread_id = 'N/A'
                if 'thread' in chat:
                    created_at = chat['thread'].get('created_at', 'N/A')
                    thread_id = chat['thread'].get('id', 'N/A')  # Get Thread ID

                chat_analysis = {
                    'Chat_ID': thread_id,  # Use Thread ID but keep column name as Chat_ID
                    'Contact_Date': created_at,
                    'Client_Name': 'N/A',
                    'Client_Email': 'N/A',
                    'Total_Client_Messages': 0,
                    'Positive_Messages': 0,
                    'Negative_Messages': 0,
                    'Neutral_Messages': 0,
                    'Average_Sentiment_Score': 0.0,
                    'Overall_Chat_Sentiment': 'No Messages',
                    'Has_Customer_Messages': 'No'
                }

                # Extract customer info
                for user in chat.get('users', []):
                    if user.get('type') == 'customer':
                        chat_analysis['Client_Name'] = user.get('name', 'Anonymous')
                        chat_analysis['Client_Email'] = user.get('email', 'N/A')

                # Extract and analyze customer messages
                customer_messages = []
                if 'thread' in chat:
                    thread = chat['thread']
                    for event in thread.get('events', []):
                        if event['type'] == 'message':
                            # Check if message is from customer
                            if re.search(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', event['author_id']):
                                customer_messages.append(event['text'])

                # Perform sentiment analysis
                if customer_messages:
                    positive_count = 0
                    negative_count = 0
                    neutral_count = 0
                    total_sentiment = 0

                    for message in customer_messages:
                        blob = TextBlob(message)
                        sentiment = blob.sentiment.polarity

                        if sentiment > 0:
                            positive_count += 1
                        elif sentiment < 0:
                            negative_count += 1
                        else:
                            neutral_count += 1

                        total_sentiment += sentiment

                    total_messages = len(customer_messages)
                    average_sentiment = total_sentiment / total_messages
                    overall_sentiment = 'Positive' if average_sentiment > 0 else 'Negative' if average_sentiment < 0 else 'Neutral'

                    chat_analysis.update({
                        'Total_Client_Messages': total_messages,
                        'Positive_Messages': positive_count,
                        'Negative_Messages': negative_count,
                        'Neutral_Messages': neutral_count,
                        'Average_Sentiment_Score': round(average_sentiment, 2),
                        'Overall_Chat_Sentiment': overall_sentiment,
                        'Has_Customer_Messages': 'Yes'
                    })

                results.append(chat_analysis)
            
            total_chats = len(results)
            
            if 'next_page_id' not in data:
                break
                
            page_id = data['next_page_id']

        # Save results to CSV
        if results:
            df = pd.DataFrame(results)
            # Define column order
            columns = ['Chat_ID', 'Contact_Date', 'Client_Name', 'Client_Email', 
                      'Total_Client_Messages', 'Positive_Messages', 'Negative_Messages', 
                      'Neutral_Messages', 'Average_Sentiment_Score', 
                      'Overall_Chat_Sentiment', 'Has_Customer_Messages']
            df = df[columns]  # Reorder columns
            output_file = f'chat_sentiment_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            df.to_csv(output_file, index=False)
            print(f"\nAnalysis saved to {output_file}")
            print("\nAnalysis Results:")
            print(df)
            print(f"\nTotal chats analyzed: {len(results)}")
            print(f"Chats with customer messages: {len([r for r in results if r['Has_Customer_Messages'] == 'Yes'])}")
            print(f"Chats without customer messages: {len([r for r in results if r['Has_Customer_Messages'] == 'No'])}")
            return True
        else:
            print("\nNo chats found to analyze")
            return True

    except Exception as e:
        print(f"\nError: {str(e)}")
        return False

if __name__ == "__main__":
    print("LiveChat Transcript Downloader and Sentiment Analyzer")
    print("-" * 50)
    
    print("\nIMPORTANT: You'll need both your Account ID and Personal Access Token")
    print("1. Account ID can be found in the LiveChat Console URL or Developer Console")
    print("2. Personal Access Token from Developer Console")
    
    ACCOUNT_ID = input("\nPlease enter your Account ID: ").strip()
    TOKEN = input("Please enter your Personal Access Token: ").strip()
    
    if not ACCOUNT_ID or not TOKEN:
        print("\nError: Both Account ID and Token are required")
        exit(1)
    
    print("\nDate Range (format: YYYY-MM-DD)")
    print("Press Enter for both dates to use last 7 days")
    START_DATE = input("Start date: ").strip()
    END_DATE = input("End date: ").strip()
    
    # Validate dates if provided
    if START_DATE and END_DATE:
        if not validate_date(START_DATE) or not validate_date(END_DATE):
            print("\nError: Invalid date format. Please use YYYY-MM-DD")
            exit(1)
        if validate_date(START_DATE) > validate_date(END_DATE):
            print("\nError: Start date must be before end date")
            exit(1)
    
    print("\nAttempting to download and analyze transcripts...")
    process_and_analyze_chats(ACCOUNT_ID, TOKEN, START_DATE, END_DATE)