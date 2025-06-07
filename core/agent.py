import yaml
import os
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from core.utils import num_tokens_from_string, clean_text
import google.generativeai as genai
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file or environment variables.")

genai.configure(api_key=GEMINI_API_KEY)

class CharacterAgent:
    def __init__(self, agent_id: str, persona_file_path: str, vector_db_dir: str, knowledge_text_files: list = None, general_retriever=None):
        self.agent_id = agent_id
        with open(persona_file_path, 'r', encoding='utf-8') as f:
            self.persona = yaml.safe_load(f)

        self.vector_db_path = os.path.join(vector_db_dir, f"{self.agent_id}_db")
        
        # --- LLM Configuration (Gemini) ---
        self.gemini_model_name = "gemini-1.5-flash-latest"
        self.llm = genai.GenerativeModel(
            model_name=self.gemini_model_name,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
            )
        )
        print(f"Agent {self.agent_id} initialized with Gemini model: {self.gemini_model_name}")

        # --- Embedding Model (Local Sentence Transformer) ---
        self.embedding_model_name = 'all-MiniLM-L6-v2'
        print(f"Initializing local embedding model: {self.embedding_model_name}...")
        try:
            self.embeddings_model = HuggingFaceEmbeddings(
                model_name=self.embedding_model_name,
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )
            print(f"Local embedding model {self.embedding_model_name} initialized.")
        except Exception as e:
            print(f"Error initializing local embedding model {self.embedding_model_name}: {e}")
            print("Falling back to a very basic tokenizer for RAG (suboptimal).")
            class BasicEmbedder:
                def embed_documents(self, texts): return [[float(ord(c)) for c in t[:10]] for t in texts]
                def embed_query(self, text): return [float(ord(c)) for c in text[:10]]
            self.embeddings_model = BasicEmbedder()


        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100,
            length_function=len
        )

        # --- Vector Store (FAISS) ---
        if os.path.exists(self.vector_db_path) and os.listdir(self.vector_db_path):
            try:
                print(f"Loading existing VectorDB for {self.agent_id} from {self.vector_db_path}")
                self.vector_store = FAISS.load_local(self.vector_db_path, self.embeddings_model, allow_dangerous_deserialization=True)
            except Exception as e:
                print(f"Error loading VectorDB for {self.agent_id}: {e}. Recreating...")
                self._create_and_save_empty_vector_store()
        else:
            self._create_and_save_empty_vector_store()
            
        self.retriever = self.vector_store.as_retriever(search_kwargs={"k": 3})

        self.general_retriever = general_retriever
        if self.general_retriever:
            print(f"Agent '{self.agent_id}' has been given access to the general knowledge base.")


        if knowledge_text_files:
            for file_path in knowledge_text_files:
                self.add_knowledge_from_file(file_path)

        # System prompt
        self.system_prompt_content = self.persona.get('system_prompt', "You are a helpful AI assistant.")
        if not isinstance(self.system_prompt_content, str):
            print(f"Warning: system_prompt for {self.agent_id} is not a string. Using default.")
            self.system_prompt_content = "You are a helpful AI assistant."

    def _create_and_save_empty_vector_store(self):
        print(f"Creating new VectorDB for {self.agent_id} at {self.vector_db_path}")
        os.makedirs(self.vector_db_path, exist_ok=True)
        initial_texts = ["Initial knowledge placeholder for " + self.persona.get('full_name', self.agent_id)]
        try:
            self.vector_store = FAISS.from_texts(initial_texts, self.embeddings_model)
            self.vector_store.save_local(self.vector_db_path)
        except Exception as e:
            print(f"CRITICAL: Failed to create initial vector store for {self.agent_id}: {e}")
            raise

    def add_knowledge_from_text(self, text_content: str, source_name: str = "generic_text"):
        if not self.vector_store:
            print(f"Cannot add knowledge for {self.agent_id}: No vector store.")
            return
        cleaned_text_content = clean_text(text_content)
        if not cleaned_text_content:
            print(f"Skipping empty or invalid text for {self.agent_id} from {source_name}")
            return
        chunks = self.text_splitter.split_text(cleaned_text_content)
        if chunks:
            print(f"Adding {len(chunks)} chunks from {source_name} to {self.agent_id}'s knowledge base.")
            try:
                self.vector_store.add_texts(texts=chunks, metadatas=[{"source": source_name}] * len(chunks))
                self.vector_store.save_local(self.vector_db_path)
                self.retriever = self.vector_store.as_retriever(search_kwargs={"k": 3})
            except Exception as e:
                print(f"Error adding texts to vector store for {self.agent_id}: {e}")
        else:
            print(f"No chunks generated from {source_name} for {self.agent_id}.")

    def add_knowledge_from_file(self, file_path: str):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.add_knowledge_from_text(content, source_name=os.path.basename(file_path))
        except Exception as e:
            print(f"Error reading or processing file {file_path} for {self.agent_id}: {e}")

    def _build_gemini_chat_history(self, conversation_history: list = None):
        gemini_history = []
        if conversation_history:
            for user_msg, ai_msg in conversation_history:
                gemini_history.append({'role': 'user', 'parts': [{'text': user_msg}]})
                gemini_history.append({'role': 'model', 'parts': [{'text': ai_msg}]})
        return gemini_history

    # SỬA ĐỔI 3: Toàn bộ logic trong hàm think_and_respond được cập nhật
    def think_and_respond(self, user_query: str, conversation_history: list = None):
        print(f"\n--- {self.persona.get('full_name', self.agent_id)} responding to: '{user_query}' (using Gemini & Local Embeddings) ---")

        # --- Lấy context từ RAG ---
        rag_context_str = ""
        try:
            # Lấy context từ retriever của chính agent
            own_docs = self.retriever.invoke(user_query)
            print(f"Retrieved {len(own_docs)} docs from own knowledge base.")

            # Lấy context từ retriever chung nếu có
            general_docs = []
            if self.general_retriever:
                general_docs = self.general_retriever.invoke(user_query)
                print(f"Retrieved {len(general_docs)} docs from general knowledge base.")
            
            # Kết hợp và loại bỏ các context trùng lặp
            all_docs_content = [doc.page_content for doc in own_docs + general_docs]
            unique_content = list(dict.fromkeys(all_docs_content)) # Giữ lại thứ tự và loại bỏ trùng lặp
            
            if unique_content:
                rag_context_str = "\n\n---\nRelevant Information:\n" + "\n\n".join(unique_content) + "\n---"
                print(f"Combined RAG context (first 100 chars): {rag_context_str[:100]}...")
            else:
                 rag_context_str = "\n\n(No relevant information found)"

        except Exception as e:
            print(f"Error during RAG retrieval for {self.agent_id}: {e}")
            rag_context_str = "\n\n(Error retrieving relevant information)"
        
        # --- Xây dựng Prompt ---
        chat_session = self.llm.start_chat(
            history=self._build_gemini_chat_history(conversation_history)
        )
        
        system_prompt_with_instructions = f"""
        {self.system_prompt_content}

        HƯỚNG DẪN ĐẶC BIỆT CHO LƯỢT NÀY:
        1. Phân tích bối cảnh sau:
           - Thông tin liên quan (RAG): {rag_context_str if rag_context_str else 'Không có thông tin RAG cụ thể.'}
           - Câu hỏi/Chủ đề hiện tại: {user_query}

        2. TRƯỚC KHI trả lời, hãy viết ra dòng suy nghĩ của bạn (giống như suy nghĩ trong đầu của con người, có thể nghĩ bất cứ điều gì liên quan đến những thứ trong chủ đề) theo cấu trúc sau (đây là phần suy nghĩ nội tâm, không phải phát biểu chính thức nên đây là suy nghĩ mà bạn sẽ không nói cho ai, dù suy nghĩ có là gì rất khó nói ra):
           <thinking>
           [Suy nghĩ của bạn ở đây]
           </thinking>

        3. SAU ĐÓ, đưa ra PHÁT BIỂU CHÍNH THỨC của bạn.
           Phát biểu này cần NGẮN GỌN, súc tích, đi thẳng vào vấn đề và thể hiện đúng vai trò của bạn.
           Tránh lặp lại câu hỏi hoặc thông tin không cần thiết từ RAG.
        """

        # Gán prompt đã xây dựng để gửi đi
        full_user_message_for_turn = system_prompt_with_instructions
    

        print(f"Sending to Gemini (first 200 chars): {full_user_message_for_turn[:200].strip()}...")
        
        try:
            response = chat_session.send_message(full_user_message_for_turn)
            ai_response_text = response.text
            print(f"Gemini Raw Response (first 200 chars): {ai_response_text[:200]}...")
        except Exception as e:
            print(f"Error calling Gemini API for {self.agent_id}: {e}")
            if hasattr(e, 'response') and e.response: 
                try:
                    error_details = e.response.json() if hasattr(e.response, 'json') else e.response.text
                    print(f"Gemini API Error Response: {error_details}")
                except:
                    print(f"Gemini API Error Response (raw): {e.response.text if hasattr(e.response, 'text') else 'No text'}")
            elif hasattr(e, 'message'):
                print(f"Error message: {e.message}")
            else:
                print(f"Full error: {e}")
            ai_response_text = "Xin lỗi, tôi gặp sự cố khi xử lý yêu cầu của bạn với Gemini."

        print(f"{self.persona.get('full_name', self.agent_id)}: {ai_response_text}")
        return ai_response_text