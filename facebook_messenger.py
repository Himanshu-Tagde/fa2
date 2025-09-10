import requests
import json
import time
from datetime import datetime
from facebook_config import APP_ID, APP_SECRET, REDIRECT_URI
from facebook_data_handlers import save_user_profile, save_facebook_data, save_messages_data

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
            print(f"   To: {participant_name} (ID: {participant_id})")
            print(f"   Message: {message_text}")
            
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
        from facebook_config import participant_names
        
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
