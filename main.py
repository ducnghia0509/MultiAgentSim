import os
import sys
import time
import datetime # QUAN TRỌNG CHO APSCHEDULER
from apscheduler.schedulers.background import BackgroundScheduler

project_root_from_main = os.path.abspath(os.path.dirname(__file__))
if project_root_from_main not in sys.path:
    sys.path.insert(0, project_root_from_main)

from core.agent_manager import AgentManager
from core.data_pipeline import (
    trigger_data_update, # Sử dụng hàm wrapper mới
    AGENT_NEWSAPI_CONFIG # Import config
)

# --- Configuration ---
NATIONAL_PERSONA_DIR = "National/"
PERSONAL_PERSONA_DIR = "Personal/"
VECTOR_DB_BASE_DIR = "vector_stores/"
RAW_DATA_DIR_BASE = "data_sources/raw_news/"

# --- Initialize Agent Manager ---
print("Initializing Agent Manager for main execution...")
manager = AgentManager(NATIONAL_PERSONA_DIR, PERSONAL_PERSONA_DIR, VECTOR_DB_BASE_DIR)
print("Agent Manager Initialized.")

# --- Data Update Function for Scheduler ---
def scheduled_job_wrapper():
    """Wrapper function to be called by the APScheduler."""
    print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] APScheduler is triggering data update...")
    try:
        trigger_data_update(
            manager_instance=manager,
            raw_data_dir_base_path=RAW_DATA_DIR_BASE,
            agent_news_config_dict_param=AGENT_NEWSAPI_CONFIG
        )
    except Exception as e:
        print(f"Error during scheduled data update: {e}")
        import traceback
        traceback.print_exc()
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] APScheduler job finished.\n")

# --- Scheduler for Automatic Crawling ---
scheduler = BackgroundScheduler()
scheduler.add_job(
    scheduled_job_wrapper,
    'interval',
    hours=1 ,
    next_run_time=datetime.datetime.now() + datetime.timedelta(seconds=10), # Cần datetime
    id='data_update_job'
)

# --- Main Interaction Loop ---
def main_cli_interaction():
    print("\nWelcome to the Multi-Agent Interaction System (CLI)!")
    
    if not scheduler.running:
        try:
            scheduler.start()
            print("Background data update scheduler started. Next run configured by 'next_run_time'.")
        except Exception as e:
            print(f"Error starting scheduler: {e}")

    while True:
        print("\nAvailable CLI commands:")
        print("  ask <agent_id> \"<question>\"")
        print("  chat <agent_id>                       (Start continuous chat)")
        print("  discuss <agent_id1>,<agent_id2>[,<agent_id3>...] \"<topic>\"")
        print("  agents                                (List available agents)")
        print("  update_now                            (Manually trigger data update)")
        print("  exit")

        user_input = input("Enter command: ").strip()

        if user_input.lower() == "exit":
            if scheduler.running:
                print("Shutting down scheduler...")
                scheduler.shutdown()
            print("Exiting system.")
            break
        
        elif user_input.lower() == "agents":
            print("\nAvailable Agents:")
            if manager.agents:
                for agent_id, agent_instance in manager.agents.items():
                    print(f"  - {agent_id} ({agent_instance.persona.get('full_name', 'N/A')})")
            else:
                print("  No agents loaded.")

        elif user_input.lower() == "update_now":
            print("Manually triggering data update...")
            try:
                trigger_data_update(manager, RAW_DATA_DIR_BASE, AGENT_NEWSAPI_CONFIG)
            except Exception as e:
                print(f"Error during manual update: {e}")
                import traceback
                traceback.print_exc()


        elif user_input.startswith("ask "):
            try:
                parts = user_input.split(" ", 2)
                if len(parts) < 3: raise IndexError("Not enough parts")
                agent_id = parts[1]
                question = parts[2].strip('"')
                manager.ask_single_agent(agent_id, question)
            except IndexError:
                print("Invalid ask command. Format: ask <agent_id> \"<question>\"")
        
        elif user_input.startswith("chat "):
            try:
                parts = user_input.split(" ", 1)
                if len(parts) < 2: raise IndexError("Agent ID missing")
                agent_id_chat = parts[1].strip() # Thêm strip
                if not agent_id_chat: raise ValueError("Agent ID cannot be empty")
                
                agent_to_chat = manager.get_agent(agent_id_chat)
                if not agent_to_chat:
                    print(f"Agent {agent_id_chat} not found.")
                    continue

                print(f"\n--- Starting chat with {agent_to_chat.persona.get('full_name', agent_id_chat)} ---")
                print("Type '!!endchat' to stop.")
                chat_session_history = [] 
                while True:
                    user_chat_input = input(f"You ({agent_id_chat}): ")
                    if user_chat_input.lower() == "!!endchat":
                        print(f"--- Ending chat with {agent_id_chat} ---")
                        break
                    ai_response_text = manager.ask_single_agent(agent_id_chat, user_chat_input, chat_session_history)
                    chat_session_history.append((user_chat_input, ai_response_text))
                    if len(chat_session_history) > 5: 
                        chat_session_history.pop(0)
            except IndexError:
                print("Invalid chat command. Format: chat <agent_id>")
            except ValueError as ve:
                print(f"Error in chat command: {ve}")


        elif user_input.startswith("discuss "):
            try:
                parts = user_input.split(" ", 2)
                if len(parts) < 3: raise IndexError("Not enough parts")
                agent_ids_str = parts[1]
                topic = parts[2].strip('"')
                agent_ids_list = [aid.strip() for aid in agent_ids_str.split(',') if aid.strip()]
                if not agent_ids_list: raise ValueError("No agent IDs provided for discussion")
                if len(agent_ids_list) < 2 : raise ValueError("Need at least two agents for discussion")
                manager.simulate_discussion(agent_ids_list, topic, max_turns_per_agent=2) # Sửa tên tham số ở đây
            except IndexError:
                print("Invalid discuss command. Format: discuss <agent_id1>,<agent_id2> \"<topic>\"")
            except ValueError as ve:
                print(f"Error in discuss command: {ve}")
        
        else:
            print("Unknown command.")

if __name__ == "__main__":
    os.makedirs(NATIONAL_PERSONA_DIR, exist_ok=True)
    os.makedirs(PERSONAL_PERSONA_DIR, exist_ok=True)
    os.makedirs(VECTOR_DB_BASE_DIR, exist_ok=True)
    os.makedirs(RAW_DATA_DIR_BASE, exist_ok=True)
    
    core_dir = "core"
    os.makedirs(core_dir, exist_ok=True)
    init_file_path = os.path.join(core_dir, "__init__.py")
    if not os.path.exists(init_file_path):
        with open(init_file_path, "w") as f:
            pass 
    main_cli_interaction()