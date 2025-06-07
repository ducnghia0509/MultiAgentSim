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
        
        # TODO: Link personal agents (leaders) to their national agents if applicable
        # This requires a field in personal_persona.yaml like 'represents_nation_id: usa_nation'
        # Then you can access nation's knowledge or system prompt components if needed.


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
            print("Cần ít nhất 2 agent để thảo luận.")
            return "Cần ít nhất 2 agent để thảo luận."

        print(f"\n=== Bắt đầu thảo luận về: '{topic}' ===")
        discussion_log = [f"Chủ đề: {topic}"]
        
        # agent_conversation_histories[agent_id] = [(human_q, ai_r), ...]
        agent_conversation_histories = {agent_id: [] for agent_id in agent_ids}


        for turn in range(max_turns_per_agent * len(agent_ids)):
            current_agent_idx = turn % len(agent_ids)
            current_agent_id = agent_ids[current_agent_idx]
            
            agent = self.get_agent(current_agent_id)
            if not agent:
                print(f"Bỏ qua agent không tồn tại: {current_agent_id}")
                continue

            # Construct the prompt for the current agent, including the main topic and recent exchanges
            # The "question" to the agent will be the topic + a request for their input based on prior turns.
            if turn == 0: # First turn for the first agent
                question_for_agent = f"Về chủ đề '{topic}', {agent.persona.get('full_name', current_agent_id)}, xin mời bạn cho ý kiến đầu tiên."
            else:
                # Get the last 1-2 statements from other agents as context
                recent_statements = []
                if len(discussion_log) > 1: # if there's more than just the topic
                    # Take last N statements, but not from the current agent itself.
                    # This logic can be improved.
                    context_statements_count = 0
                    for i in range(len(discussion_log) - 1, 0, -1): # Iterate backwards from last statement
                        if not discussion_log[i].startswith(agent.persona.get('full_name', current_agent_id) + ":"):
                             recent_statements.insert(0, discussion_log[i]) # Prepend to keep order
                             context_statements_count +=1
                        if context_statements_count >= 2 : # Get up to 2 prior statements from OTHERS
                            break
                
                if recent_statements:
                    context_str = "\n".join(recent_statements)
                    question_for_agent = (
                        f"Tiếp tục thảo luận về '{topic}'.\n"
                        f"Đây là các ý kiến gần nhất từ các bên khác:\n{context_str}\n\n"
                        f"{agent.persona.get('full_name', current_agent_id)}, "
                        f"bạn hãy phân tích những ý kiến này. Điểm nào bạn đồng tình, điểm nào bạn phản đối? "
                        f"Kế hoạch/phản ứng của bạn sẽ thay đổi như thế nào dựa trên những phát biểu này? "
                        f"Hãy trình bày rõ ràng."
                    )
                else: # Lượt thứ hai của agent đầu tiên, chưa có ai khác nói
                    question_for_agent = f"Tiếp tục thảo luận về '{topic}'. {agent.persona.get('full_name', current_agent_id)}, bạn có muốn bổ sung hoặc làm rõ thêm điều gì không sau khi đã suy nghĩ kỹ hơn?"

            # Use the agent's own conversation history for context specific to it
            # This is a simplified approach. LangChain's ConversationBufferWindowMemory is better.
            history_for_current_agent = agent_conversation_histories[current_agent_id]
            
            # The `think_and_respond` method will print its own output
            response_text = agent.think_and_respond(question_for_agent, history_for_current_agent)
            
            # Update logs
            full_statement = f"{agent.persona.get('full_name', current_agent_id)}: {response_text}"
            discussion_log.append(full_statement)
            
            # Update this agent's specific history for next time it speaks
            # The "human" part is the complex question we just constructed for it
            agent_conversation_histories[current_agent_id].append((question_for_agent, response_text))
            if len(agent_conversation_histories[current_agent_id]) > 3: # Keep history short
                agent_conversation_histories[current_agent_id].pop(0)


        print("\n=== Kết thúc thảo luận ===")
        return "\n".join(discussion_log)