import os
from core.agent import CharacterAgent

class AgentManager:
    def __init__(self, national_persona_dir: str, personal_persona_dir: str, vector_db_base_dir: str):
        self.agents = {}
        self.national_persona_dir = national_persona_dir
        self.personal_persona_dir = personal_persona_dir
        self.vector_db_base_dir = vector_db_base_dir
        os.makedirs(self.vector_db_base_dir, exist_ok=True)
        self._load_agents()

    def _load_agents(self):
        # Load national agents
        for persona_file in os.listdir(self.national_persona_dir):
            if persona_file.endswith(".yaml"):
                agent_id = persona_file.replace(".yaml", "")
                persona_path = os.path.join(self.national_persona_dir, persona_file)
                self.agents[agent_id] = CharacterAgent(agent_id, persona_path, self.vector_db_base_dir)
                print(f"Loaded National Agent: {self.agents[agent_id].persona.get('full_name', agent_id)}")

        # Load personal agents
        for persona_file in os.listdir(self.personal_persona_dir):
            if persona_file.endswith(".yaml"):
                agent_id = persona_file.replace(".yaml", "")
                persona_path = os.path.join(self.personal_persona_dir, persona_file)
                self.agents[agent_id] = CharacterAgent(agent_id, persona_path, self.vector_db_base_dir)
                print(f"Loaded Personal Agent: {self.agents[agent_id].persona.get('full_name', agent_id)}")
        
    def get_agent(self, agent_id: str) -> CharacterAgent | None:
        return self.agents.get(agent_id)

    def ask_single_agent(self, agent_id: str, question: str, conversation_history: list = None):
        agent = self.get_agent(agent_id)
        if agent:
            return agent.think_and_respond(question, conversation_history)
        else:
            print(f"Error: Agent with ID '{agent_id}' not found.")
            return f"Agent '{agent_id}' không tồn tại."

    def ask_multiple_agents_sequentially(self, agent_ids: list, question: str):
        responses = {}
        print(f"\n=== Câu hỏi cho nhiều agent: '{question}' ===")
        for agent_id in agent_ids:
            agent_response = self.ask_single_agent(agent_id, question)
            if agent_response: # Check if agent exists and responded
                 responses[agent_id] = agent_response
        return responses

    def simulate_discussion(self, agent_ids: list, topic: str, max_turns_per_agent: int = 1):
        if len(agent_ids) < 2:
            return "Cần ít nhất 2 agent để thảo luận."

        print(f"\n=== Bắt đầu thảo luận về: '{topic}' ===")
        discussion_log = [f"Chủ đề: {topic}"]
        
        # Initialize conversation histories for each agent ID provided
        agent_conversation_histories = {agent_id: [] for agent_id in agent_ids}
        
        # Gather all valid participating agents and their names
        active_participants_info = [] # Will store dicts: {"object": agent, "id": agent_id, "name": agent_name}
        for agent_id_in_discussion in agent_ids:
            agent = self.get_agent(agent_id_in_discussion)
            if agent:
                agent_name = agent.persona.get('full_name', agent_id_in_discussion)
                active_participants_info.append({
                    "object": agent, 
                    "id": agent_id_in_discussion, 
                    "name": agent_name
                })
            else:
                print(f"Cảnh báo: Agent với ID '{agent_id_in_discussion}' không tìm thấy và sẽ bị bỏ qua trong thảo luận.")
        
        if len(active_participants_info) < 2:
            return "Cần ít nhất 2 agent hợp lệ để thảo luận sau khi lọc các agent không tồn tại."

        for turn in range(max_turns_per_agent * len(active_participants_info)):
            current_participant_data = active_participants_info[turn % len(active_participants_info)]
            current_agent_object = current_participant_data["object"]
            current_agent_id = current_participant_data["id"]
            current_agent_name = current_participant_data["name"]

            # Identify other participants for the prompt
            other_participant_names = [
                p_info["name"] for p_info in active_participants_info if p_info["id"] != current_agent_id
            ]
            
            if other_participant_names:
                other_participants_str = ", ".join(other_participant_names)
                participants_context_str = f"Bạn ({current_agent_name}) đang trong một cuộc thảo luận cùng với: {other_participants_str}."
            else:
                # This case should ideally not happen if len(active_participants_info) >= 2
                participants_context_str = f"Bạn ({current_agent_name}) đang phát biểu (không có người tham gia nào khác được liệt kê)." 

            # Construct the prompt for the current agent
            if turn == 0: # First turn for the first agent in the (potentially filtered) list
                question_for_agent = (
                    f"{participants_context_str}\n"
                    f"Chủ đề thảo luận là: '{topic}'.\n"
                    f"Xin mời bạn ({current_agent_name}) bắt đầu cuộc thảo luận."
                )
            else:
                recent_statements = []
                if len(discussion_log) > 1: 
                    context_statements_count = 0
                    # Iterate backwards from the last statement in the general discussion_log
                    for i in range(len(discussion_log) - 1, 0, -1): 
                        # Ensure the statement is not from the current agent
                        if not discussion_log[i].startswith(current_agent_name + ":"):
                             recent_statements.insert(0, discussion_log[i]) # Prepend to keep chronological order
                             context_statements_count +=1
                        if context_statements_count >= 2 : # Get up to 2 prior statements from OTHERS
                            break
                
                if recent_statements:
                    context_str = "\n".join(recent_statements)
                    question_for_agent = (
                        f"{participants_context_str}\n"
                        f"Chủ đề thảo luận là: '{topic}'.\n"
                        f"Đây là những ý kiến gần nhất từ những người khác trong cuộc thảo luận:\n{context_str}\n\n"
                        f"Dựa trên những ý kiến này, bạn ({current_agent_name}) hãy phân tích và đưa ra phản hồi của mình. "
                        f"Hãy trình bày rõ ràng."
                    )
                else: # No recent statements from others, or it's this agent's first turn after the very first speaker
                    question_for_agent = (
                        f"{participants_context_str}\n"
                        f"Chủ đề thảo luận là: '{topic}'.\n"
                        f"Hiện tại chưa có ý kiến nào trước đó từ người khác (trong những lượt gần nhất) hoặc bạn là người tiếp theo sau lượt mở đầu.\n"
                        f"Bạn ({current_agent_name}), bạn có muốn bổ sung, làm rõ thêm điều gì, hoặc đưa ra ý kiến tiếp theo của mình không?"
                    )

            # Use the agent's own conversation history for context specific to it
            history_for_current_agent = agent_conversation_histories[current_agent_id]
            
            response_text = current_agent_object.think_and_respond(question_for_agent, history_for_current_agent)
            
            # Update logs
            full_statement = f"{current_agent_name}: {response_text}"
            discussion_log.append(full_statement)
            
            # Update this agent's specific history for next time it speaks
            agent_conversation_histories[current_agent_id].append((question_for_agent, response_text))
            if len(agent_conversation_histories[current_agent_id]) > 3: # Keep history short (e.g., last 3 exchanges)
                agent_conversation_histories[current_agent_id].pop(0)

        print("\n=== Kết thúc thảo luận ===")
        return "\n".join(discussion_log)