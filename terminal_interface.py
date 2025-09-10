import requests
import os
from datetime import datetime
from facebook_config import FACEBOOK_DATA_FILE, MESSAGES_DATA_FILE, USER_PROFILE_FILE
from facebook_data_handlers import load_all_data

def terminal_interface():
    """Terminal interface with proper participant name display"""
    print("\n" + "="*80)
    print("🚀 ENHANCED FACEBOOK MESSENGER WITH PROPER NAME HANDLING")
    print("✅ Participant names from conversation data")
    print("✅ Names properly stored in messages JSON")
    print("✅ Names displayed when sending messages")
    print("="*80)
    
    load_all_data()
    
    while True:
        try:
            print("\n📋 MESSAGING OPTIONS:")
            print("1. 📘 Send Facebook Message (with participant names)")
            print("2. 📨 View Messages for Conversation")
            print("3. 👥 View All Participant Names")
            print("4. 📂 View JSON Files")
            print("5. 🔄 Refresh Login")
            print("6. Exit")
            
            choice = input("\n👉 Choose your option (1-6): ").strip()
            
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
                
                for filename in [FACEBOOK_DATA_FILE, MESSAGES_DATA_FILE, USER_PROFILE_FILE]:
                    if os.path.exists(filename):
                        stat = os.stat(filename)
                        print(f"✅ {filename}")
                        print(f"   Size: {round(stat.st_size / 1024, 2)} KB")
                        print(f"   Modified: {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
                    else:
                        print(f"❌ {filename} - Not found")
            
            elif choice == "5":
                print("🔄 To refresh your data and fetch new messages with participant names:")
                print("   Visit: http://localhost:8000/login")
                print("   This will fetch fresh conversations, messages, and participant names.")
            
            elif choice == "6":
                print("👋 Goodbye!")
                break
            
            else:
                print("❌ Invalid choice. Please enter 1-6.")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {str(e)}")
