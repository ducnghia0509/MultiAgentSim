# app/streamlit_app.py
import streamlit as st
import sys
import os
import time
import traceback # Để hiển thị traceback đầy đủ
import re # Để trích xuất tên agent và parse suy nghĩ

# --- Giao diện Streamlit ---
# ĐẶT LỆNH NÀY LÊN ĐẦU TIÊN!
st.set_page_config(page_title="Multi-Agent Interaction Platform", layout="wide", initial_sidebar_state="expanded")

# Thêm đường dẫn của thư mục gốc dự án vào sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Các import này phải sau khi sys.path được sửa
try:
    from core.agent_manager import AgentManager
    from core.data_pipeline import trigger_data_update, AGENT_NEWSAPI_CONFIG
except ImportError as e:
    st.error(f"Failed to import core modules. Please ensure the project structure is correct and all dependencies are installed. Error: {e}")
    st.stop() # Dừng app nếu không import được module chính

# --- Configuration ---
NATIONAL_PERSONA_DIR = os.path.join(project_root, "National/")
PERSONAL_PERSONA_DIR = os.path.join(project_root, "Personal/")
VECTOR_DB_BASE_DIR = os.path.join(project_root, "vector_stores/")
RAW_DATA_DIR_UI = os.path.join(project_root, "data_sources/raw_news/")

# --- Khởi tạo Agent Manager (chỉ một lần) ---
@st.cache_resource
def load_agent_manager():
    print("Attempting to initialize Agent Manager for Streamlit app...") # Log ra console
    try:
        manager = AgentManager(NATIONAL_PERSONA_DIR, PERSONAL_PERSONA_DIR, VECTOR_DB_BASE_DIR)
        print("Agent Manager Initialized successfully for Streamlit app.") # Log ra console
        return manager
    except Exception as e:
        # Lỗi này sẽ hiển thị trên console chạy Streamlit, và UI sẽ hiển thị thông báo lỗi chung
        print(f"FATAL ERROR in load_agent_manager: {e}")
        print(traceback.format_exc())
        return None

agent_manager = load_agent_manager()

# --- TIÊU ĐỀ CHÍNH CỦA TRANG ---
st.title("🗣️ Multi-Agent Interaction Platform")

# --- Hàm tiện ích Parse Response ---
def parse_agent_response(response_text: str):
    thought_match = re.search(r"<suy_nghĩ>(.*?)</suy_nghĩ>", response_text, re.DOTALL | re.IGNORECASE)
    inner_thoughts = None
    official_statement = response_text

    if thought_match:
        inner_thoughts = thought_match.group(1).strip()
        official_statement = response_text[thought_match.end():].strip()
        if not official_statement and inner_thoughts: # Nếu chỉ có suy nghĩ
             official_statement = "(Chỉ có suy nghĩ, không có phát biểu chính thức riêng biệt)"
        elif not official_statement and not inner_thoughts: # Nếu cả hai đều trống sau khi parse
             official_statement = "(Không có phản hồi nội dung)"

    # Fallback nếu không có tag <suy_nghĩ> nhưng có cấu trúc khác
    elif "phát biểu chính thức:" in response_text.lower():
        parts = re.split(r"phát biểu chính thức:", response_text, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) > 1:
            potential_thoughts = parts[0].strip()
            if potential_thoughts and not potential_thoughts.lower().startswith("bạn là"):
                inner_thoughts = potential_thoughts
            official_statement = parts[1].strip()
    
    return inner_thoughts, official_statement 


# --- Sidebar ---
st.sidebar.header("Controls")

if agent_manager:
    if st.sidebar.button("🔄 Update Agents' Knowledge Now", key="update_knowledge_button"):
        with st.spinner("Updating knowledge bases... This may take a few minutes."):
            try:
                trigger_data_update(
                    manager_instance=agent_manager,
                    raw_data_dir_base_path=RAW_DATA_DIR_UI,
                    agent_news_config_dict_param=AGENT_NEWSAPI_CONFIG
                )
                st.sidebar.success("Knowledge update process triggered!")
                st.toast("Knowledge update started. This runs in the background.", icon="🔄")
            except Exception as e:
                st.sidebar.error(f"Error during manual update trigger: {e}")
                st.sidebar.text(traceback.format_exc())
else:
    st.sidebar.error("Agent Manager failed to load. Update functionality disabled. Please check console for errors.")

st.sidebar.subheader("Available Agents")
agent_ids_list = []
agent_name_map = {}
if agent_manager and agent_manager.agents:
    agent_ids_list = sorted(list(agent_manager.agents.keys()))
    for aid in agent_ids_list:
        agent_name = agent_manager.agents[aid].persona.get('full_name', aid)
        agent_name_map[aid] = agent_name
        st.sidebar.markdown(f"- **{aid}** (*{agent_name}*)")
else:
    st.sidebar.markdown("No agents available or Agent Manager not loaded.")

# --- Logic gán Avatar ---
DEFAULT_AVATARS = ["😀", "🧐", "🤓", "😎", "🤩", "🤔", "🤖", "🧑‍💼", "👩‍💼", "👨‍🏫", "👩‍🏫", "🌍", "🇺🇸", "🇨🇳", "🇷🇺", "🇯🇵", "🇰🇵", "🇻🇳", "🇪🇺"]
AGENT_AVATARS_CACHE = {} # Sử dụng cache riêng cho app này, không dùng global
avatar_idx_counter = 0
def get_agent_avatar_streamlit(agent_id_or_name):
    global avatar_idx_counter # Cần global để tăng dần
    # Cố gắng tìm agent_id nếu truyền vào tên đầy đủ
    key_to_use = agent_id_or_name
    if agent_id_or_name in agent_name_map.values(): # Nếu là full_name
        for aid, fname in agent_name_map.items():
            if fname == agent_id_or_name:
                key_to_use = aid # Dùng ID để nhất quán
                break
    
    if key_to_use not in AGENT_AVATARS_CACHE:
        AGENT_AVATARS_CACHE[key_to_use] = DEFAULT_AVATARS[avatar_idx_counter % len(DEFAULT_AVATARS)]
        avatar_idx_counter += 1
    return AGENT_AVATARS_CACHE[key_to_use]

# --- Chế độ tương tác ---
if not agent_manager:
    st.error("🚨 Agent Manager could not be loaded. Core functionalities are disabled. Please check the terminal console where Streamlit is running for detailed error messages (look for 'FATAL ERROR in load_agent_manager').")
    st.stop() # Dừng thực thi nếu manager không load được

interaction_mode = st.selectbox(
    "Select Interaction Mode:",
    ("Chat with a Single Agent", "Observe Multi-Agent Discussion"),
    key="interaction_mode_select"
)

if interaction_mode == "Chat with a Single Agent":
    st.header("💬 Chat with a Single Agent")
    if not agent_ids_list:
         st.warning("No agents available to chat with.")
    else:
        selected_agent_id_chat = st.selectbox(
            "Choose an agent to chat with:",
            agent_ids_list,
            key="chat_agent_select",
            format_func=lambda x: agent_name_map.get(x, x) # Hiển thị full_name
        )

        if selected_agent_id_chat:
            agent_to_chat = agent_manager.get_agent(selected_agent_id_chat)
            if agent_to_chat:
                agent_full_name_chat = agent_to_chat.persona.get('full_name', selected_agent_id_chat)
                agent_avatar_chat = get_agent_avatar_streamlit(selected_agent_id_chat)
                st.subheader(f"Talking to: {agent_avatar_chat} {agent_full_name_chat}")

                session_key_chat_hist = f"chat_history_{selected_agent_id_chat}"
                if session_key_chat_hist not in st.session_state:
                    st.session_state[session_key_chat_hist] = []
                
                # Hiển thị lịch sử chat
                chat_display_container = st.container(height=500) # Container cho chat
                with chat_display_container:
                    for i, (user_msg, ai_data_or_msg) in enumerate(st.session_state[session_key_chat_hist]):
                        st.chat_message("user", avatar="🧑‍💻").write(user_msg)
                        if isinstance(ai_data_or_msg, dict): # Format mới với thoughts/statement
                            if ai_data_or_msg.get("thinking"):
                                st.chat_message("assistant", avatar=agent_avatar_chat).write("🤔 Thinking...")
                            else:
                                if ai_data_or_msg.get("thoughts"):
                                    with st.expander(f"Inner thoughts...", expanded=False):
                                        st.caption(ai_data_or_msg["thoughts"])
                                if ai_data_or_msg.get("statement"):
                                    st.chat_message("assistant", avatar=agent_avatar_chat).write(ai_data_or_msg["statement"])
                        elif isinstance(ai_data_or_msg, str): # Tương thích format cũ (chỉ statement)
                            st.chat_message("assistant", avatar=agent_avatar_chat).write(ai_data_or_msg)
                
                # Xử lý input và response
                # Sử dụng key động cho chat_input để nó reset khi agent thay đổi
                user_query_chat = st.chat_input(f"Ask {agent_full_name_chat} something...", key=f"chat_input_for_{selected_agent_id_chat}")

                if user_query_chat:
                    # Thêm tin nhắn user vào history để hiển thị ngay
                    st.session_state[session_key_chat_hist].append((user_query_chat, {"thinking": True, "thoughts": None, "statement": None}))
                    st.rerun() # Rerun để hiển thị tin nhắn user và "Thinking..."

                # Kiểm tra xem có tin nhắn nào đang ở trạng thái "thinking" không (sau khi rerun)
                if st.session_state[session_key_chat_hist] and \
                   isinstance(st.session_state[session_key_chat_hist][-1][1], dict) and \
                   st.session_state[session_key_chat_hist][-1][1].get("thinking"):
                    
                    current_user_query_for_ai, _ = st.session_state[session_key_chat_hist][-1]
                    
                    history_for_agent = []
                    # Lấy tối đa 3 cặp hội thoại (user, ai_statement) gần nhất
                    for h_user, h_ai_data_or_msg in reversed(st.session_state[session_key_chat_hist][:-1]):
                        ai_statement_for_history = None
                        if isinstance(h_ai_data_or_msg, dict) and h_ai_data_or_msg.get("statement"):
                            ai_statement_for_history = h_ai_data_or_msg["statement"]
                        elif isinstance(h_ai_data_or_msg, str):
                            ai_statement_for_history = h_ai_data_or_msg
                        
                        if ai_statement_for_history:
                             history_for_agent.insert(0, (h_user, ai_statement_for_history))
                        if len(history_for_agent) >= 3:
                            break
                    
                    raw_ai_response = agent_manager.ask_single_agent(
                        selected_agent_id_chat,
                        current_user_query_for_ai,
                        conversation_history=history_for_agent
                    )
                    thoughts, statement = parse_agent_response(raw_ai_response)
                    st.session_state[session_key_chat_hist][-1] = (current_user_query_for_ai, {"thinking": False, "thoughts": thoughts, "statement": statement})
                    
                    if len(st.session_state[session_key_chat_hist]) > 10: # Giới hạn lịch sử
                        st.session_state[session_key_chat_hist].pop(0)
                    st.rerun() # Rerun để hiển thị kết quả AI
            else:
                st.error(f"Could not retrieve agent: {selected_agent_id_chat}")

elif interaction_mode == "Observe Multi-Agent Discussion":
    st.header("🔬 Observe Multi-Agent Discussion")
    if not agent_ids_list:
         st.warning("No agents available for discussion.")
    else:
        selected_agent_ids_discuss = st.multiselect(
            "Choose agents for discussion (select at least 2):",
            options=list(agent_ids_list),
            format_func=lambda x: agent_name_map.get(x, x),
            key="discuss_agents_multiselect"
        )
        discussion_topic_input = st.text_input("Enter the discussion topic:", key="discuss_topic_input")
        max_turns_per_agent_discuss = st.slider("Max turns per agent in discussion:", 1, 3, 1, key="discuss_max_turns_slider")

        # Tạo key session state dựa trên các lựa chọn hiện tại để lưu log thảo luận
        # Điều này giúp nếu người dùng thay đổi topic/agents thì sẽ có log mới
        current_discussion_params_str = "_".join(sorted(selected_agent_ids_discuss)) + "_" + discussion_topic_input + "_" + str(max_turns_per_agent_discuss)
        current_discussion_log_key = f"discussion_log_{hash(current_discussion_params_str)}"

        if st.button("Start/Refresh Discussion", key="discuss_start_button"):
            if len(selected_agent_ids_discuss) >= 2 and discussion_topic_input:
                # Đánh dấu là đang xử lý để hiển thị spinner ở lần rerun tiếp theo
                st.session_state[current_discussion_log_key] = "Processing..."
                # Lưu lại params để so sánh, nếu params thay đổi thì chạy lại simulate_discussion
                st.session_state[f"{current_discussion_log_key}_params"] = current_discussion_params_str 
                st.rerun()
            else:
                st.warning("Please select at least 2 agents and enter a discussion topic.")

        # Kiểm tra và thực thi thảo luận nếu đang ở trạng thái "Processing..."
        # hoặc nếu params thay đổi so với lần chạy trước (chưa có trong st.session_state)
        if st.session_state.get(current_discussion_log_key) == "Processing..." or \
           st.session_state.get(f"{current_discussion_log_key}_params") != current_discussion_params_str:
            
            # Chỉ chạy simulate nếu thực sự có yêu cầu (đã nhấn nút và đủ điều kiện)
            # Điều kiện này cần được kiểm tra lại cẩn thận, có thể button click là đủ
            if len(selected_agent_ids_discuss) >= 2 and discussion_topic_input: # Đảm bảo vẫn đủ điều kiện
                with st.spinner("Agents are discussing... Please wait."):
                    try:
                        discussion_log_str = agent_manager.simulate_discussion(
                            selected_agent_ids_discuss,
                            discussion_topic_input,
                            max_turns_per_agent=max_turns_per_agent_discuss
                        )
                        st.session_state[current_discussion_log_key] = discussion_log_str.split("\n")
                        st.session_state[f"{current_discussion_log_key}_params"] = current_discussion_params_str # Cập nhật params đã xử lý
                        st.rerun() # Rerun để hiển thị kết quả
                    except Exception as e:
                        st.error(f"Error during discussion simulation: {e}")
                        st.text(traceback.format_exc())
                        st.session_state[current_discussion_log_key] = [f"Error: {e}"] # Lưu lỗi vào log

        # Hiển thị log thảo luận nếu đã có
        if isinstance(st.session_state.get(current_discussion_log_key), list):
            st.subheader("Discussion Log:")
            discussion_display_container = st.container(height=700) # Tăng chiều cao
            with discussion_display_container:
                for entry_idx, entry in enumerate(st.session_state[current_discussion_log_key]):
                    match = re.match(r"^(.*?):(.*)", entry, re.DOTALL)
                    if match:
                        speaker_name = match.group(1).strip()
                        raw_message_log = match.group(2).strip()
                        thoughts, statement = parse_agent_response(raw_message_log)
                        is_info_line = "Chủ đề" in speaker_name or "Bắt đầu thảo luận" in speaker_name or "Kết thúc thảo luận" in speaker_name
                        
                        if is_info_line:
                            st.info(f"**{speaker_name}:** {statement if statement else raw_message_log}")
                        else:
                            speaker_avatar_discuss = get_agent_avatar_streamlit(speaker_name)
                            # Sử dụng key duy nhất cho mỗi chat_message nếu cần (ít quan trọng hơn chat_input)
                            with st.chat_message("assistant", avatar=speaker_avatar_discuss):
                                st.markdown(f"**{speaker_name}**")
                                if thoughts:
                                    # Sử dụng key duy nhất cho expander để tránh lỗi state
                                    expander_key = f"thoughts_{current_discussion_log_key}_{entry_idx}"
                                    with st.expander("Inner thoughts...", expanded=False):
                                        st.caption(thoughts)
                                if statement:
                                    st.write(statement)
                                elif not thoughts and raw_message_log: # Nếu không parse được gì cả
                                    st.write(raw_message_log)
                    elif entry.strip():
                        st.text(entry)