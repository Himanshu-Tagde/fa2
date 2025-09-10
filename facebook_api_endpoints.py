from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from datetime import datetime
from facebook_config import user_data
from facebook_data_handlers import load_all_data
from facebook_messenger import FacebookMessenger

app = FastAPI()
messenger = FacebookMessenger()

@app.get("/")
async def root():
    return {
        "message": "Enhanced Facebook Messenger with Proper Name Handling - Ready!",
        "note": "Participant names come from conversation data and are properly stored"
    }

@app.get("/login")
async def login():
    """Facebook login"""
    url = messenger.generate_login_url()
    print(f"\n🔗 Login URL: {url}")
    return RedirectResponse(url=url, status_code=307)

@app.get("/auth/callback")
async def auth_callback(request: Request):
    """Handle OAuth callback and setup complete user data with proper names"""
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
    
    print("🔄 Setting up complete user data with proper participant names...")
    complete_data = messenger.setup_complete_user_data(long_lived_token)
    user_data['main_user'] = complete_data
    
    total_messages = sum(len(msgs) for msgs in complete_data['facebook_messages'].values())
    total_participants = len(complete_data.get('participant_names', {}))
    
    print(f"✅ Setup complete!")
    return {
        "message": "🎉 Facebook login successful with proper name handling!",
        "facebook_conversations": len(complete_data['facebook_conversations']),
        "total_messages_fetched": total_messages,
        "participant_names_collected": total_participants,
        "improvements": [
            "✅ Participant names from conversation data",
            "✅ Names properly stored in messages JSON",
            "✅ Names displayed when sending messages",
            "✅ Enhanced error handling throughout"
        ]
    }

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
