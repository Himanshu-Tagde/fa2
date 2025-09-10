import uvicorn
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse
from datetime import datetime
import uuid
import json
import threading
import sys
import time
import os

app = FastAPI()

# ================================
# FACEBOOK APP CONFIGURATION
# ================================

APP_ID = ""
APP_SECRET = ""
REDIRECT_URI = "http://localhost:8000/auth/callback"
WEBHOOK_VERIFY_TOKEN = "crmsecret123"

# JSON file names
FACEBOOK_DATA_FILE = "facebook_data.json"
USER_PROFILE_FILE = "user_profile.json"
MESSAGES_DATA_FILE = "messages_data.json"
LOGIN_TRACK_FILE = "facebook_login_track.json"  # NEW: Login tracking file

# Storage
user_data = {}
participant_names = {}

# ================================
# LOGIN TRACKING FUNCTIONS - NEW
# ================================

def save_login_track(login_info):
    """Save login tracking information to JSON file"""
    try:
        # Load existing login history if exists
        if os.path.exists(LOGIN_TRACK_FILE):
            with open(LOGIN_TRACK_FILE, 'r', encoding='utf-8') as f:
                login_history = json.load(f)
        else:
            login_history = {
                "total_logins": 0,
                "login_sessions": []
            }
        
        # Add session ID and timestamp
        login_info['session_id'] = str(uuid.uuid4())
        login_info['login_time'] = datetime.now().isoformat()
        login_info['status'] = 'active'
        
        # Add to login history
        login_history['login_sessions'].append(login_info)
        login_history['total_logins'] = len(login_history['login_sessions'])
        login_history['last_login'] = login_info['login_time']
        
        # Keep only last 50 login sessions to prevent file from getting too large
        if len(login_history['login_sessions']) > 50:
            login_history['login_sessions'] = login_history['login_sessions'][-50:]
        
        # Save to file
        with open(LOGIN_TRACK_FILE, 'w', encoding='utf-8') as f:
            json.dump(login_history, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Login track saved to {LOGIN_TRACK_FILE}")
        return True, login_info['session_id']
    except Exception as e:
        print(f"❌ Failed to save login track: {e}")
        return False, None

def load_login_track():
    """Load login tracking information from JSON file"""
    try:
        if os.path.exists(LOGIN_TRACK_FILE):
            with open(LOGIN_TRACK_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"total_logins": 0, "login_sessions": []}
    except Exception as e:
        print(f"❌ Failed to load login track: {e}")
        return {"total_logins": 0, "login_sessions": []}

def update_login_status(session_id, status, additional_info=None):
    """Update login session status (active, expired, logout)"""
    try:
        login_history = load_login_track()
        
        for session in login_history['login_sessions']:
            if session.get('session_id') == session_id:
                session['status'] = status
                session['last_updated'] = datetime.now().isoformat()
                if additional_info:
                    session.update(additional_info)
                break
        
        # Save updated data
        with open(LOGIN_TRACK_FILE, 'w', encoding='utf-8') as f:
            json.dump(login_history, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        print(f"❌ Failed to update login status: {e}")
        return False

# ================================
# EXISTING JSON FILE HANDLERS
# ================================

def save_facebook_data(data):
    """Save Facebook data to JSON file"""
    try:
        facebook_data = {
            "last_updated": datetime.now().isoformat(),
            "pages": data.get("facebook_pages", []),
            "conversations": data.get("facebook_conversations", []),
            "messages": data.get("facebook_messages", {}),
            "participant_names": data.get("participant_names", {}),
            "statistics": {
                "total_conversations": len(data.get("facebook_conversations", [])),
                "total_messages": sum(len(msgs) for msgs in data.get("facebook_messages", {}).values()),
                "total_participants": len(data.get("participant_names", {}))
            }
        }

        with open(FACEBOOK_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(facebook_data, f, indent=2, ensure_ascii=False)
        print(f"✅ Facebook data saved to {FACEBOOK_DATA_FILE}")
        return True
    except Exception as e:
        print(f"❌ Failed to save Facebook data: {e}")
        return False

def save_messages_data(data):
    """Save detailed messages data to separate JSON file"""
    try:
        messages_data = {
            "last_updated": datetime.now().isoformat(),
            "total_conversations": len(data.get("facebook_messages", {})),
            "total_messages": sum(len(msgs) for msgs in data.get("facebook_messages", {}).values()),
            "messages_by_conversation": data.get("facebook_messages", {}),
            "participant_names": data.get("participant_names", {}),
            "note": "Names come from conversation participant data, emails not available due to Facebook privacy"
        }

        with open(MESSAGES_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(messages_data, f, indent=2, ensure_ascii=False)
        print(f"✅ Messages data saved to {MESSAGES_DATA_FILE}")
        return True
    except Exception as e:
        print(f"❌ Failed to save messages data: {e}")
        return False

def save_user_profile(profile):
    """Save user profile to JSON file"""
    try:
        profile_data = {
            "last_updated": datetime.now().isoformat(),
            "profile": profile
        }

        with open(USER_PROFILE_FILE, 'w', encoding='utf-8') as f:
            json.dump(profile_data, f, indent=2, ensure_ascii=False)
        print(f"✅ User profile saved to {USER_PROFILE_FILE}")
        return True
    except Exception as e:
        print(f"❌ Failed to save user profile: {e}")
        return False

def load_facebook_data():
    """Load Facebook data from JSON file"""
    try:
        if os.path.exists(FACEBOOK_DATA_FILE):
            with open(FACEBOOK_DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        return None
    except Exception as e:
        print(f"❌ Failed to load Facebook data: {e}")
        return None

def load_user_profile():
    """Load user profile from JSON file"""
    try:
        if os.path.exists(USER_PROFILE_FILE):
            with open(USER_PROFILE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('profile', {})
        return {}
    except Exception as e:
        print(f"❌ Failed to load user profile: {e}")
        return {}

# ================================
# ENHANCED FACEBOOK MESSENGER CLASS
# ================================

class FacebookMessenger:
    def __init__(self):
        self.graph_version = "v18.0"
        self.base_url = f"https://graph.facebook.com/{self.graph_version}"
        self.app_id = APP_ID
        self.app_secret = APP_SECRET
        self.redirect_uri = REDIRECT_URI

    def generate_login_url(self):
        """Generate login URL with Facebook permissions"""
        scopes = [
            'pages_messaging',
            'pages_show_list',
            'pages_manage_metadata',
            'pages_read_engagement',
            'pages_read_user_content',
            'email',
            'public_profile',
            'business_management'
        ]

        params = {
            'client_id': self.app_id,
            'redirect_uri': self.redirect_uri,
            'scope': ','.join(scopes),
            'response_type': 'code',
            'state': 'facebook_login'
        }

        query_params = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"https://www.facebook.com/{self.graph_version}/dialog/oauth?{query_params}"

    def get_access_token(self, code):
        """Exchange code for access token"""
        params = {
            'client_id': self.app_id,
            'client_secret': self.app_secret,
            'redirect_uri': self.redirect_uri,
            'code': code
        }

        try:
            response = requests.get(f"{self.base_url}/oauth/access_token", params=params)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"❌ Token exchange error: {e}")
            return None

    def get_long_lived_token(self, short_token):
        """Convert to long-lived token"""
        params = {
            'grant_type': 'fb_exchange_token',
            'client_id': self.app_id,
            'client_secret': self.app_secret,
            'fb_exchange_token': short_token
        }

        try:
            response = requests.get(f"{self.base_url}/oauth/access_token", params=params)
            if response.status_code == 200:
                return response.json()
            return {'access_token': short_token}
        except Exception as e:
            return {'access_token': short_token}

    def check_message_window(self, conversation_id, access_token):
        """Check if we can send messages (within 24-hour window)"""
        try:
            print(f"🔍 Checking message window for conversation: {conversation_id}")
            url = f"{self.base_url}/{conversation_id}"
            params = {
                'fields': 'messages{created_time,from}',
                'access_token': access_token
            }

            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                messages = data.get('messages', {}).get('data', [])
                
                if not messages:
                    print("📭 No messages found in conversation")
                    return False, 999

                # Get the most recent message
                last_msg = messages[0]
                created_time = last_msg.get('created_time')
                
                if not created_time:
                    print("⚠️ No timestamp found in last message")
                    return False, 999

                # Parse timestamp
                try:
                    last_msg_time = datetime.fromisoformat(created_time.replace('Z', '+00:00'))
                    now = datetime.now(last_msg_time.tzinfo)
                    hours_diff = (now - last_msg_time).total_seconds() / 3600
                    
                    is_within_window = hours_diff <= 24
                    print(f"⏰ Last message: {hours_diff:.1f} hours ago, within window: {is_within_window}")
                    return is_within_window, hours_diff
                except Exception as time_error:
                    print(f"❌ Error parsing message timestamp: {time_error}")
                    return False, 999
            else:
                print(f"❌ API error checking message window: {response.status_code} - {response.text}")
                return False, 999

        except requests.exceptions.RequestException as req_error:
            print(f"🌐 Network error checking message window: {req_error}")
            return False, 999
        except Exception as e:
            print(f"⚠️ Unexpected error checking message window: {e}")
            return False, 999

    def send_facebook_message_with_templates(self, conversation_id, participant_id, message_text, access_token, participant_name="Unknown User"):
        """Send Facebook message with participant name displayed"""
        # First check if we're within the messaging window
        can_send, hours_since = self.check_message_window(conversation_id, access_token)
        
        if not can_send:
            print(f"⚠️ Outside 24-hour window ({hours_since:.1f} hours since last message)")
            print("🔄 Trying to send as message template...")
            # Try to send as a message template (for businesses)
            payload = {
                'recipient': json.dumps({'id': participant_id}),
                'message': json.dumps({'text': message_text}),
                'messaging_type': 'MESSAGE_TAG',
                'tag': 'CONFIRMED_EVENT_UPDATE',
                'access_token': access_token
            }
        else:
            print(f"✅ Within messaging window ({hours_since:.1f} hours)")
            payload = {
                'recipient': json.dumps({'id': participant_id}),
                'message': json.dumps({'text': message_text}),
                'messaging_type': 'RESPONSE',
                'access_token': access_token
            }

        try:
            print(f"📤 Sending Facebook message...")
            print(f"  To: {participant_name} (ID: {participant_id})")
            print(f"  Message: {message_text}")
            
            response = requests.post(f"{self.base_url}/me/messages", data=payload)
            
            if response.status_code == 200:
                result = response.json()
                message_id = result.get('message_id', 'Message sent')
                print(f"✅ Facebook message sent to {participant_name}! Message ID: {message_id}")
                return True, message_id
            else:
                error_info = response.json()
                error_msg = error_info.get('error', {}).get('message', 'Unknown error')
                print(f"❌ Failed to send Facebook message to {participant_name}: {error_msg}")
                
                if "outside the allowed window" in error_msg.lower():
                    suggestion = "💡 SOLUTION: Ask the user to send you a message first, then you can reply within 24 hours."
                    print(suggestion)
                    return False, f"{error_msg}\n{suggestion}"
                
                return False, error_msg

        except Exception as e:
            print(f"❌ Exception while sending Facebook message to {participant_name}: {e}")
            return False, str(e)

    def get_conversation_messages(self, conversation_id, access_token, participant_name_map, limit=100):
        """Get messages from Facebook conversation with participant names from conversation data"""
        try:
            print(f"📨 Fetching messages for conversation: {conversation_id}")
            
            # Get messages with available fields
            fields = "messages{id,message,from{id,name},created_time,attachments{name,mime_type,size}}"
            response = requests.get(
                f"{self.base_url}/{conversation_id}?fields={fields}&limit={limit}&access_token={access_token}",
                timeout=30
            )

            if response.status_code == 200:
                messages_data = response.json().get('messages', {}).get('data', [])
                processed_messages = []
                
                print(f"🔍 Processing {len(messages_data)} messages...")

                for msg in messages_data:
                    from_info = msg.get('from', {})
                    sender_id = from_info.get('id')
                    
                    # Use participant name from conversation data first, fallback to message data
                    sender_name = participant_name_map.get(sender_id, from_info.get('name', 'Unknown User'))

                    # Process attachments
                    attachments_data = []
                    attachments = msg.get('attachments', {}).get('data', [])
                    for attachment in attachments:
                        attachments_data.append({
                            'name': attachment.get('name', 'Unknown'),
                            'mime_type': attachment.get('mime_type', 'Unknown'),
                            'size': attachment.get('size', 0)
                        })

                    processed_message = {
                        'message_id': msg.get('id'),
                        'message_text': msg.get('message', 'No text content'),
                        'created_time': msg.get('created_time'),
                        'sender': {
                            'id': sender_id,
                            'name': sender_name,
                            'email': 'Not available (Facebook privacy policy)'
                        },
                        'attachments': attachments_data,
                        'attachment_count': len(attachments_data),
                        'retrieved_at': datetime.now().isoformat()
                    }

                    processed_messages.append(processed_message)

                print(f"✅ Processed {len(processed_messages)} messages for conversation {conversation_id}")
                return processed_messages

            else:
                print(f"❌ Error fetching messages: {response.status_code} - {response.text}")
                return []

        except Exception as e:
            print(f"❌ Error getting messages for conversation {conversation_id}: {e}")
            return []

    def setup_complete_user_data(self, access_token):
        """Setup complete user data using participant names from conversation data"""
        user_info = {
            'access_token': access_token,
            'connected_at': datetime.now().isoformat(),
            'facebook_pages': [],
            'facebook_conversations': [],
            'facebook_messages': {},
            'participant_names': {}
        }

        # Get YOUR profile (this will have email if you granted permission)
        print("👤 Getting your user profile...")
        try:
            profile_response = requests.get(
                f"{self.base_url}/me?fields=id,name,email,first_name,last_name&access_token={access_token}"
            )

            if profile_response.status_code == 200:
                profile = profile_response.json()
                user_info['profile'] = profile
                save_user_profile(profile)
                
                # Your email should be available since you authorized the app
                your_email = profile.get('email', 'Not granted permission')
                print(f"✅ Your profile: {profile.get('name')} ({your_email})")
            else:
                print(f"⚠️ Could not get your profile: {profile_response.text}")
                user_info['profile'] = {}

        except Exception as e:
            print(f"⚠️ Error getting your profile: {e}")
            user_info['profile'] = {}

        # Get Facebook pages
        print("📄 Getting Facebook pages...")
        try:
            pages_response = requests.get(
                f"{self.base_url}/me/accounts?access_token={access_token}"
            )

            if pages_response.status_code == 200:
                pages = pages_response.json().get('data', [])
                for page in pages:
                    page_data = {
                        'id': page['id'],
                        'name': page['name'],
                        'access_token': page['access_token'],
                        'platform': 'facebook',
                        'retrieved_at': datetime.now().isoformat()
                    }

                    user_info['facebook_pages'].append(page_data)

                print(f"✅ Found {len(pages)} Facebook pages")

        except Exception as e:
            print(f"⚠️ Error getting pages: {e}")

        # Get Facebook conversations and extract participant names
        print("💬 Getting Facebook conversations and participant names...")
        for page in user_info['facebook_pages']:
            print(f"📄 Processing Facebook page: {page['name']}")
            try:
                url = f"{self.base_url}/{page['id']}/conversations"
                params = {
                    'fields': 'id,participants,updated_time,message_count',
                    'access_token': page['access_token']
                }

                conv_response = requests.get(url, params=params, timeout=30)
                
                if conv_response.status_code == 200:
                    conversations_data = conv_response.json()
                    conversations = conversations_data.get('data', [])
                    print(f"✅ Found {len(conversations)} conversations for {page['name']}")

                    for conv in conversations:
                        try:
                            participants = conv.get('participants', {}).get('data', [])
                            
                            for participant in participants:
                                if participant.get('id') != page['id']:  # Skip page itself
                                    participant_id = participant.get('id')
                                    participant_name = participant.get('name', 'Unknown User')
                                    
                                    # Store participant name for later use
                                    user_info['participant_names'][participant_id] = participant_name
                                    print(f"👤 Found participant: {participant_name} (ID: {participant_id})")

                                    # Check message window
                                    try:
                                        can_send, hours_since = self.check_message_window(conv['id'], page['access_token'])
                                    except Exception:
                                        can_send, hours_since = False, 999

                                    conversation_data = {
                                        'conversation_id': conv['id'],
                                        'page_id': page['id'],
                                        'page_name': page['name'],
                                        'page_access_token': page['access_token'],
                                        'participant_id': participant_id,
                                        'participant_name': participant_name,
                                        'participant_email': 'Not available (Facebook privacy policy)',
                                        'updated_time': conv.get('updated_time'),
                                        'message_count': conv.get('message_count', 0),
                                        'platform': 'facebook',
                                        'can_send_message': can_send,
                                        'hours_since_last_message': round(hours_since, 1),
                                        'retrieved_at': datetime.now().isoformat()
                                    }

                                    user_info['facebook_conversations'].append(conversation_data)

                        except Exception as conv_error:
                            print(f"❌ Error processing conversation: {conv_error}")
                            continue

                else:
                    print(f"❌ HTTP Error for page {page['name']}: {conv_response.text}")

            except Exception as page_error:
                print(f"⚠️ Error processing page: {page_error}")

        print(f"✅ Total Facebook conversations processed: {len(user_info['facebook_conversations'])}")
        print(f"✅ Total participant names collected: {len(user_info['participant_names'])}")

        # Update global participant_names for easy access
        global participant_names
        participant_names.update(user_info['participant_names'])

        # Fetch messages for each conversation
        print("📨 Fetching messages for conversations with participant names...")
        total_messages = 0
        
        for conv in user_info['facebook_conversations']:
            conv_id = conv['conversation_id']
            participant_name = conv['participant_name']
            
            try:
                print(f"💬 Getting messages for conversation with {participant_name}...")
                messages = self.get_conversation_messages(conv_id, conv['page_access_token'], user_info['participant_names'])
                user_info['facebook_messages'][conv_id] = messages
                total_messages += len(messages)
                print(f"✅ Fetched {len(messages)} messages for {participant_name} (conversation {conv_id})")

                # Add a small delay to avoid hitting rate limits
                time.sleep(1)

            except Exception as e:
                print(f"❌ Error fetching messages for conversation with {participant_name}: {e}")
                user_info['facebook_messages'][conv_id] = []

        print(f"🎉 Setup complete! Fetched {total_messages} messages from {len(user_info['facebook_conversations'])} conversations")
        print(f"📊 All participant names properly stored and available for messaging")

        # Save data
        print("💾 Saving data to JSON files...")
        save_facebook_data(user_info)
        save_messages_data(user_info)

        return user_info

messenger = FacebookMessenger()

# ================================
# LOAD DATA ON STARTUP
# ================================

def load_all_data():
    """Load all data from JSON files on startup"""
    facebook_data = load_facebook_data()
    profile_data = load_user_profile()
    
    if facebook_data or profile_data:
        user_data['main_user'] = {
            'profile': profile_data,
            'facebook_pages': facebook_data.get('pages', []) if facebook_data else [],
            'facebook_conversations': facebook_data.get('conversations', []) if facebook_data else [],
            'facebook_messages': facebook_data.get('messages', {}) if facebook_data else {},
            'participant_names': facebook_data.get('participant_names', {}) if facebook_data else {}
        }
        
        # Update global participant_names
        global participant_names
        participant_names.update(facebook_data.get('participant_names', {}) if facebook_data else {})
        return True
    return False

# ================================
# FASTAPI ENDPOINTS
# ================================

@app.get("/")
async def root():
    return {
        "message": "Enhanced Facebook Messenger with Login Tracking - Ready!",
        "note": "Now includes comprehensive login session tracking"
    }

@app.get("/login")
async def login():
    """Facebook login"""
    url = messenger.generate_login_url()
    print(f"\n🔗 Login URL: {url}")
    return RedirectResponse(url=url, status_code=307)

@app.get("/auth/callback")
async def auth_callback(request: Request):
    """Handle OAuth callback and setup complete user data with login tracking"""
    code = request.query_params.get("code")
    error = request.query_params.get("error")
    
    if error:
        return {"error": f"Authorization failed: {error}"}
    
    if not code:
        return {"error": "Missing authorization code"}

    print("🔄 Exchanging code for token...")
    token_data = messenger.get_access_token(code)
    if not token_data:
        return {"error": "Failed to get access token"}

    access_token = token_data['access_token']
    
    print("🔄 Getting long-lived token...")
    long_token_data = messenger.get_long_lived_token(access_token)
    long_lived_token = long_token_data['access_token']

    # NEW: Prepare login tracking information
    login_info = {
        "platform": "facebook",
        "access_token": long_lived_token[:20] + "...",  # Store only first 20 chars for security
        "token_type": long_token_data.get('token_type', 'bearer'),
        "expires_in": long_token_data.get('expires_in', 'unknown'),
        "client_ip": str(request.client.host),
        "user_agent": request.headers.get('user-agent', 'unknown'),
        "authorization_code": code[:10] + "...",  # Store only first 10 chars
        "redirect_uri": REDIRECT_URI,
        "app_id": APP_ID
    }

    print("🔄 Setting up complete user data with proper participant names...")
    complete_data = messenger.setup_complete_user_data(long_lived_token)
    
    # Add user profile info to login tracking
    user_profile = complete_data.get('profile', {})
    login_info.update({
        "user_id": user_profile.get('id', 'unknown'),
        "user_name": user_profile.get('name', 'unknown'),
        "user_email": user_profile.get('email', 'not_available'),
        "total_pages": len(complete_data.get('facebook_pages', [])),
        "total_conversations": len(complete_data.get('facebook_conversations', [])),
        "total_messages": sum(len(msgs) for msgs in complete_data.get('facebook_messages', {}).values())
    })

    # NEW: Save login tracking information
    success, session_id = save_login_track(login_info)
    if success:
        print(f"✅ Login session tracked: {session_id}")
        complete_data['current_session_id'] = session_id
    
    user_data['main_user'] = complete_data

    total_messages = sum(len(msgs) for msgs in complete_data['facebook_messages'].values())
    total_participants = len(complete_data.get('participant_names', {}))

    print(f"✅ Setup complete!")
    
    return {
        "message": "🎉 Facebook login successful with comprehensive tracking!",
        "session_id": session_id if success else "tracking_failed",
        "facebook_conversations": len(complete_data['facebook_conversations']),
        "total_messages_fetched": total_messages,
        "participant_names_collected": total_participants,
        "login_tracked": success,
        "improvements": [
            "✅ Participant names from conversation data",
            "✅ Names properly stored in messages JSON", 
            "✅ Names displayed when sending messages",
            "✅ Enhanced error handling throughout",
            "✅ Comprehensive login session tracking"
        ]
    }

# NEW: Login tracking endpoints
@app.get("/login/history")
async def get_login_history():
    """Get login history and statistics"""
    login_data = load_login_track()
    
    # Calculate statistics
    total_logins = login_data.get('total_logins', 0)
    sessions = login_data.get('login_sessions', [])
    
    active_sessions = [s for s in sessions if s.get('status') == 'active']
    recent_sessions = sessions[-10:] if sessions else []
    
    return {
        "total_logins": total_logins,
        "active_sessions": len(active_sessions),
        "last_login": login_data.get('last_login', 'never'),
        "recent_sessions": recent_sessions,
        "note": "Login tracking includes session management and security details"
    }

@app.post("/login/logout")
async def logout_session(request: Request):
    """Logout current session"""
    data = await request.json()
    session_id = data.get('session_id')
    
    if not session_id:
        return {"error": "session_id required"}
    
    success = update_login_status(session_id, 'logged_out', {
        'logout_time': datetime.now().isoformat(),
        'logout_ip': str(request.client.host)
    })
    
    if success:
        return {"message": "Session logged out successfully", "session_id": session_id}
    else:
        return {"error": "Failed to logout session"}

@app.get("/facebook/conversations")
async def get_facebook_conversations():
    """Get Facebook conversations with proper participant names"""
    if 'main_user' not in user_data:
        if not load_all_data():
            return {"error": "Please login first"}

    conversations = user_data['main_user']['facebook_conversations']
    messages_data = user_data['main_user']['facebook_messages']

    formatted_conversations = []
    for i, conv in enumerate(conversations, 1):
        status = "✅ Can send" if conv.get('can_send_message', False) else f"⏰ Wait {conv.get('hours_since_last_message', 999):.1f}h"
        conv_messages = messages_data.get(conv['conversation_id'], [])

        formatted_conversations.append({
            'number': i,
            'conversation_id': conv['conversation_id'],
            'participant_name': conv['participant_name'],
            'participant_email': conv.get('participant_email', 'Not available'),
            'participant_id': conv['participant_id'],
            'page_name': conv['page_name'],
            'message_count': len(conv_messages),
            'status': status,
            'can_send': conv.get('can_send_message', False),
            'access_token': conv['page_access_token']
        })

    return {
        "platform": "📘 Facebook",
        "total_conversations": len(formatted_conversations),
        "note": "Participant names come from conversation data",
        "conversations": formatted_conversations
    }

@app.get("/facebook/messages/{conversation_id}")
async def get_messages_for_conversation(conversation_id: str):
    """Get all messages for a specific conversation with proper names"""
    if 'main_user' not in user_data:
        if not load_all_data():
            return {"error": "Please login first"}

    messages = user_data['main_user']['facebook_messages'].get(conversation_id, [])
    if not messages:
        return {"error": f"No messages found for conversation {conversation_id}"}

    # Find conversation name
    conversations = user_data['main_user']['facebook_conversations']
    conv_name = "Unknown"
    for conv in conversations:
        if conv['conversation_id'] == conversation_id:
            conv_name = conv['participant_name']
            break

    return {
        "conversation_id": conversation_id,
        "participant_name": conv_name,
        "total_messages": len(messages),
        "note": "Names come from conversation participant data",
        "messages": messages
    }

@app.get("/facebook/participants")
async def get_participant_names():
    """Get all participant names collected from conversations"""
    if 'main_user' not in user_data:
        if not load_all_data():
            return {"error": "Please login first"}

    participant_names_data = user_data['main_user'].get('participant_names', {})

    return {
        "total_participants": len(participant_names_data),
        "note": "Names collected from conversation participant data",
        "participant_names": participant_names_data
    }

@app.post("/facebook/send")
async def send_facebook_message(request: Request):
    """Send Facebook message with proper participant name display"""
    if 'main_user' not in user_data:
        if not load_all_data():
            return {"error": "Please login first"}

    data = await request.json()
    conversation_id = data.get('conversation_id')
    message_text = data.get('message')

    if not conversation_id or not message_text:
        return {"error": "conversation_id and message are required"}

    # Find conversation details
    conversations = user_data['main_user']['facebook_conversations']
    target_conv = None
    for conv in conversations:
        if conv['conversation_id'] == conversation_id:
            target_conv = conv
            break

    if not target_conv:
        return {"error": f"Conversation ID {conversation_id} not found"}

    # Send message with participant name
    success, result = messenger.send_facebook_message_with_templates(
        conversation_id,
        target_conv['participant_id'],
        message_text,
        target_conv['page_access_token'],
        target_conv['participant_name']  # Pass the participant name
    )

    if success:
        return {
            "success": True,
            "platform": "📘 Facebook",
            "message": f"Message sent to {target_conv['participant_name']}",
            "participant_name": target_conv['participant_name'],
            "participant_email": target_conv.get('participant_email', 'Not available'),
            "conversation_id": conversation_id,
            "message_id": result,
            "sent_at": datetime.now().isoformat()
        }
    else:
        return {
            "success": False,
            "platform": "📘 Facebook",
            "error": result,
            "conversation_id": conversation_id,
            "participant_name": target_conv['participant_name']
        }

# ================================
# ENHANCED TERMINAL INTERFACE
# ================================

def terminal_interface():
    """Terminal interface with login tracking display"""
    print("\n" + "="*80)
    print("🚀 ENHANCED FACEBOOK MESSENGER WITH LOGIN TRACKING")
    print("✅ Participant names from conversation data")
    print("✅ Names properly stored in messages JSON")
    print("✅ Names displayed when sending messages")
    print("✅ Comprehensive login session tracking")
    print("="*80)
    
    load_all_data()
    
    while True:
        try:
            print("\n📋 MESSAGING OPTIONS:")
            print("1. 📘 Send Facebook Message (with participant names)")
            print("2. 📨 View Messages for Conversation")
            print("3. 👥 View All Participant Names")
            print("4. 📂 View JSON Files")
            print("5. 📊 View Login History (NEW)")  # NEW option
            print("6. 🔄 Refresh Login")
            print("7. Exit")
            
            choice = input("\n👉 Choose your option (1-7): ").strip()
            
            if choice == "1":
                print("\n📘 FACEBOOK MESSAGING")
                print("="*50)
                
                response = requests.get("http://localhost:8000/facebook/conversations")
                if response.status_code == 200:
                    data = response.json()
                    if "error" in data:
                        print(f"❌ {data['error']}")
                        continue

                    conversations = data.get('conversations', [])
                    if not conversations:
                        print("📭 No Facebook conversations found")
                        continue

                    print(f"\n💬 Available Facebook Conversations ({len(conversations)}):")
                    for conv in conversations:
                        print(f"{conv['number']:2d}. {conv['participant_name']} | {conv['page_name']} - {conv['status']}")
                        print(f"     📨 {conv['message_count']} messages | ID: {conv['conversation_id']}")
                        if not conv.get('can_send', False):
                            print(f"     ⚠️ Outside messaging window - user needs to message you first")

                    conv_selection = input(f"\n👉 Select conversation (1-{len(conversations)}) or enter conversation ID: ").strip()

                    conversation_id = None
                    selected_conv = None

                    if conv_selection.isdigit() and 1 <= int(conv_selection) <= len(conversations):
                        selected_conv = conversations[int(conv_selection) - 1]
                        conversation_id = selected_conv['conversation_id']
                    else:
                        conversation_id = conv_selection
                        # Find conversation by ID
                        for conv in conversations:
                            if conv['conversation_id'] == conversation_id:
                                selected_conv = conv
                                break

                    if not selected_conv:
                        print("❌ Conversation not found!")
                        continue

                    print(f"\n💬 Sending message to: {selected_conv['participant_name']}")
                    message_text = input("📝 Enter your Facebook message: ").strip()

                    if conversation_id and message_text:
                        payload = {"conversation_id": conversation_id, "message": message_text}
                        print(f"🔄 Sending Facebook message to {selected_conv['participant_name']}...")

                        response = requests.post(
                            "http://localhost:8000/facebook/send",
                            json=payload,
                            headers={"Content-Type": "application/json"}
                        )

                        if response.status_code == 200:
                            result = response.json()
                            if result.get("success"):
                                print(f"\n✅ SUCCESS: Message sent to {result.get('participant_name', 'Unknown')}")
                                print(f"📨 Message ID: {result['message_id']}")
                                print(f"🕒 Sent at: {result['sent_at']}")
                            else:
                                print(f"\n❌ FAILED: {result.get('error', 'Unknown error')}")
                        else:
                            print(f"\n❌ HTTP Error: {response.text}")
                    else:
                        print("❌ Both conversation ID and message are required!")
                else:
                    print("❌ Failed to get Facebook conversations")

            elif choice == "2":
                print("\n📨 VIEW CONVERSATION MESSAGES")
                print("="*50)
                
                response = requests.get("http://localhost:8000/facebook/conversations")
                if response.status_code == 200:
                    data = response.json()
                    conversations = data.get('conversations', [])
                    
                    if not conversations:
                        print("📭 No conversations found")
                        continue

                    print(f"\n💬 Select Conversation to View Messages:")
                    for conv in conversations:
                        print(f"{conv['number']:2d}. {conv['participant_name']} - {conv['message_count']} messages")

                    conv_selection = input(f"\n👉 Select conversation (1-{len(conversations)}): ").strip()

                    if conv_selection.isdigit() and 1 <= int(conv_selection) <= len(conversations):
                        selected_conv = conversations[int(conv_selection) - 1]
                        conv_id = selected_conv['conversation_id']

                        response = requests.get(f"http://localhost:8000/facebook/messages/{conv_id}")
                        if response.status_code == 200:
                            msg_data = response.json()
                            messages = msg_data.get('messages', [])
                            participant_name = msg_data.get('participant_name', 'Unknown')

                            print(f"\n📨 Messages for {participant_name} ({len(messages)} total):")
                            print("-" * 80)

                            for i, msg in enumerate(messages[-10:], 1):  # Show last 10 messages
                                sender = msg.get('sender', {})
                                print(f"{i}. {sender.get('name', 'Unknown')} - {msg.get('created_time')}")
                                print(f"   💬 {msg.get('message_text')}")
                                if msg.get('attachment_count', 0) > 0:
                                    print(f"   📎 {msg.get('attachment_count')} attachments")
                                print()
                        else:
                            print("❌ Failed to get messages")
                else:
                    print("❌ Failed to get conversations")

            elif choice == "3":
                print("\n👥 ALL PARTICIPANT NAMES")
                print("="*50)
                
                response = requests.get("http://localhost:8000/facebook/participants")
                if response.status_code == 200:
                    data = response.json()
                    participants = data.get('participant_names', {})
                    
                    print(f"\n📊 Total Participants: {len(participants)}")
                    print("✅ Names collected from conversation participant data")
                    print("-" * 80)
                    
                    for participant_id, name in participants.items():
                        print(f"👤 {name} (ID: {participant_id})")
                else:
                    print("❌ Failed to get participant names")

            elif choice == "4":
                print("\n📂 JSON FILES INFORMATION:")
                print("="*50)
                
                for filename in [FACEBOOK_DATA_FILE, MESSAGES_DATA_FILE, USER_PROFILE_FILE, LOGIN_TRACK_FILE]:
                    if os.path.exists(filename):
                        stat = os.stat(filename)
                        print(f"✅ {filename}")
                        print(f"   Size: {round(stat.st_size / 1024, 2)} KB")
                        print(f"   Modified: {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
                    else:
                        print(f"❌ {filename} - Not found")

            elif choice == "5":  # NEW: Login history option
                print("\n📊 LOGIN HISTORY & STATISTICS")
                print("="*50)
                
                response = requests.get("http://localhost:8000/login/history")
                if response.status_code == 200:
                    data = response.json()
                    
                    print(f"🔢 Total Logins: {data['total_logins']}")
                    print(f"🟢 Active Sessions: {data['active_sessions']}")
                    print(f"🕒 Last Login: {data['last_login']}")
                    print("\n📋 Recent Login Sessions:")
                    print("-" * 80)
                    
                    for i, session in enumerate(data['recent_sessions'], 1):
                        status_emoji = "🟢" if session['status'] == 'active' else "🔴"
                        print(f"{i}. {status_emoji} {session.get('user_name', 'Unknown')} - {session['login_time']}")
                        print(f"   📧 {session.get('user_email', 'N/A')} | IP: {session.get('client_ip', 'N/A')}")
                        print(f"   💬 {session.get('total_conversations', 0)} conversations | 📨 {session.get('total_messages', 0)} messages")
                        print(f"   🆔 Session: {session.get('session_id', 'N/A')[:8]}...")
                        print()
                else:
                    print("❌ Failed to get login history")
                    
            elif choice == "6":
                print("🔄 To refresh your data and create new login session:")
                print("   Visit: http://localhost:8000/login")
                print("   This will create a new tracked session with fresh data.")
                
            elif choice == "7":
                print("👋 Goodbye!")
                break
                
            else:
                print("❌ Invalid choice. Please enter 1-7.")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {str(e)}")

# ================================
# MAIN EXECUTION
# ================================

if __name__ == "__main__":
    print("=" * 100)
    print("🚀 ENHANCED FACEBOOK MESSENGER WITH LOGIN TRACKING")
    print("🔧 Key Features:")
    print("  ✅ Participant names from conversation data")
    print("  ✅ Names properly stored in messages JSON")
    print("  ✅ Names displayed when sending messages")
    print("  ✅ All messages include sender names")
    print("  ✅ Comprehensive participant name database")
    print("  ✅ Complete login session tracking")
    print("  ✅ Login history and statistics")
    print("📱 Running at http://localhost:8000")
    print("\n🔗 LOGIN URL: http://localhost:8000/login")
    print("=" * 100)

    # Start the server in a separate thread
    server_thread = threading.Thread(
        target=lambda: uvicorn.run(app, host="127.0.0.1", port=8000, reload=False),
        daemon=True
    )
    server_thread.start()

    # Wait for server to start
    time.sleep(3)

    # Load existing data and show status
    if load_all_data():
        fb_convs = len(user_data['main_user']['facebook_conversations'])
        total_messages = sum(len(msgs) for msgs in user_data['main_user']['facebook_messages'].values())
        total_participants = len(user_data['main_user'].get('participant_names', {}))
        
        # Show login statistics
        login_data = load_login_track()
        total_logins = login_data.get('total_logins', 0)
        
        print(f"\n✅ Server started! Enhanced capabilities loaded:")
        print(f"   📘 Facebook: {fb_convs} conversations")
        print(f"   📨 Messages: {total_messages} total messages")
        print(f"   👥 Participants: {total_participants} names collected")
        print(f"   🔐 Login History: {total_logins} total logins tracked")
        print("   ✅ All participant names properly stored and available")
    else:
        print("\n✅ Server started! Please visit http://localhost:8000/login to get started")

    # Start terminal interface
    try:
        terminal_interface()
    except KeyboardInterrupt:
        print("\n👋 Server shutting down...")
        sys.exit(0)

