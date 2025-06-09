import tiktoken
import re
import unicodedata

def num_tokens_from_string(string: str, encoding_name: str = "cl100k_base") -> int:
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens

def clean_text(text: str) -> str:
    """Basic text cleaning."""
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8', 'ignore') # Remove accents
    text = re.sub(r'http\S+', '', text) # Remove URLs
    text = re.sub(r'\s+', ' ', text).strip() # Remove extra whitespace
    return text

def split_text_into_chunks(text: str, max_tokens_per_chunk: int = 400, overlap: int = 50):
    """Splits text into chunks with overlap, respecting sentence boundaries if possible."""
    words = text.split()
    chunks = []
    current_chunk_words = []
    current_tokens = 0

    for word in words:
        word_tokens = num_tokens_from_string(word + " ")
        if current_tokens + word_tokens <= max_tokens_per_chunk:
            current_chunk_words.append(word)
            current_tokens += word_tokens
        else:
            chunks.append(" ".join(current_chunk_words))
            # Start new chunk with overlap
            overlap_words = current_chunk_words[-int(len(current_chunk_words) * (overlap / max_tokens_per_chunk)):] if overlap > 0 else [] # Rough overlap
            current_chunk_words = overlap_words + [word]
            current_tokens = num_tokens_from_string(" ".join(current_chunk_words) + " ")

    if current_chunk_words:
        chunks.append(" ".join(current_chunk_words))
    return chunks