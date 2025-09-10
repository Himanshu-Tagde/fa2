import json
import os
from datetime import datetime
from facebook_config import FACEBOOK_DATA_FILE, USER_PROFILE_FILE, MESSAGES_DATA_FILE

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

def load_all_data():
    """Load all data from JSON files on startup"""
    from facebook_config import user_data, participant_names
    
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
        participant_names.update(facebook_data.get('participant_names', {}) if facebook_data else {})
        return True
    return False
