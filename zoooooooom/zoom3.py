import requests
import json
import base64
import os
from flask import Flask, request, redirect, jsonify
from dotenv import load_dotenv
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Zoom OAuth credentials from environment variables
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI')

TOKEN_FILE = 'zoom_tokens.json'

# Helper function to load tokens from a file
def load_tokens():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            return json.load(f)
    return {}

# Helper function to save tokens to a file
def save_tokens(tokens):
    with open(TOKEN_FILE, 'w') as f:
        json.dump(tokens, f)

# Step 1: Get Authorization URL
@app.route('/')
def home():
    try:
        auth_url = (
            f"https://zoom.us/oauth/authorize?response_type=code&client_id={CLIENT_ID}"
            f"&redirect_uri={REDIRECT_URI}"
        )
        logger.info(f"Redirecting to Zoom authorization URL: {auth_url}")
        return redirect(auth_url)
    except Exception as e:
        logger.error(f"Error in home route: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Step 2: Exchange Authorization Code for Access Token
@app.route('/callback')
def callback():
    try:
        code = request.args.get('code')
        token_url = "https://zoom.us/oauth/token"
        headers = {
            "Authorization": f"Basic {base64.b64encode((CLIENT_ID + ':' + CLIENT_SECRET).encode()).decode()}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI
        }
        response = requests.post(token_url, headers=headers, data=payload)
        response_data = response.json()

        if response.status_code != 200:
            logger.error(f"Failed to obtain access token: {response_data}")
            return jsonify({"error": "Failed to obtain access token", "details": response_data}), 500

        if 'access_token' in response_data:
            save_tokens(response_data)
            access_token = response_data.get("access_token")
            join_url = schedule_meeting(access_token)
            if join_url:
                logger.info(f"Meeting scheduled successfully, redirecting to join URL: {join_url}")
                return redirect(join_url)
            else:
                logger.error("Failed to schedule meeting")
                return jsonify({"error": "Failed to schedule meeting"}), 500
        else:
            logger.error(f"Failed to obtain access token: {response_data}")
            return jsonify({"error": "Failed to obtain access token", "details": response_data}), 500
    except Exception as e:
        logger.error(f"Error in callback route: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Step 3: Refresh Access Token
def refresh_access_token(refresh_token):
    try:
        token_url = "https://zoom.us/oauth/token"
        headers = {
            "Authorization": f"Basic {base64.b64encode((CLIENT_ID + ':' + CLIENT_SECRET).encode()).decode()}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }
        response = requests.post(token_url, headers=headers, data=payload)
        response_data = response.json()
        if 'access_token' in response_data:
            save_tokens(response_data)
        return response_data.get("access_token")
    except Exception as e:
        logger.error(f"Error in refresh_access_token function: {str(e)}")
        return None

# Step 4: Schedule a Meeting and Get Join URL
def schedule_meeting(access_token):
    try:
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        meeting_details = {
            "topic": "Automated Meeting",
            "type": 2,  # Scheduled meeting
            "start_time": "2024-08-01T18:30:00Z",  # Meeting start time in ISO 8601 format (converted to UTC)
            "duration": 60,  # Duration in minutes
            "timezone": "UTC",
            "agenda": "This is an automated meeting",
            "settings": {
                "host_video": True,
                "participant_video": True,
                "join_before_host": False,
                "mute_upon_entry": True,
                "watermark": True,
                "use_pmi": False,
                "approval_type": 0,  # Automatically approve
                "registration_type": 1,  # Attendees register once and can attend any of the occurrences
                "audio": "both",  # Both telephony and VoIP
                "auto_recording": "cloud"
            }
        }

        user_id = 'me'  # Use 'me' for the authenticated user, or replace with a specific user ID
        response = requests.post(f'https://api.zoom.us/v2/users/{user_id}/meetings', headers=headers, json=meeting_details)

        if response.status_code == 201:
            meeting = response.json()
            join_url = meeting.get('join_url')
            return join_url
        else:
            logger.error(f"Failed to schedule meeting: {response.json()}")
            return None
    except Exception as e:
        logger.error(f"Error in schedule_meeting function: {str(e)}")
        return None

if __name__ == "__main__":
    app.run(port=3000)
