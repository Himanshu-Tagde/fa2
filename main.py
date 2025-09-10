import threading
import time
import sys
import uvicorn
from facebook_api_endpoints import app
from terminal_interface import terminal_interface
from facebook_data_handlers import load_all_data
from facebook_config import user_data

if __name__ == "__main__":
    print("=" * 100)
    print("🚀 ENHANCED FACEBOOK MESSENGER WITH PROPER NAME HANDLING")
    print("🔧 Key Features:")
    print("   ✅ Participant names from conversation data")
    print("   ✅ Names properly stored in messages JSON")
    print("   ✅ Names displayed when sending messages")
    print("   ✅ All messages include sender names")
    print("   ✅ Comprehensive participant name database")
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
        
        print(f"\n✅ Server started! Enhanced capabilities loaded:")
        print(f"   📘 Facebook: {fb_convs} conversations")
        print(f"   📨 Messages: {total_messages} total messages")
        print(f"   👥 Participants: {total_participants} names collected")
        print("   ✅ All participant names properly stored and available")
    else:
        print("\n✅ Server started! Please visit http://localhost:8000/login to get started")

    # Start terminal interface
    try:
        terminal_interface()
    except KeyboardInterrupt:
        print("\n👋 Server shutting down...")
        sys.exit(0)
