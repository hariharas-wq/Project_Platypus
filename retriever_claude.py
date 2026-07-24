import chromadb
from chromadb.utils import embedding_functions

local_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

chroma_client = chromadb.PersistentClient(path=r"koala_git\koala_vector_db_claude")
collection = chroma_client.get_collection(
    name="koala_government_data", 
    embedding_function=local_ef
)

POLICY_KEYWORDS = {"zoning", "development", "epbc", "clearing", "council", "policy", "hearing", "offset", "road", "corridor"}
BIRTHDAY_KEYWORDS = {"birthday", "party", "kids", "celebrate", "school", "game", "fun", "eat", "sleep", "sleepy"}

def detect_mode(user_query: str) -> str:
    """Dynamically route between Policy Defense and Birthday/Education mode."""
    tokens = set(user_query.lower().replace("?", "").replace(".", "").split())
    
    policy_overlap = len(tokens.intersection(POLICY_KEYWORDS))
    birthday_overlap = len(tokens.intersection(BIRTHDAY_KEYWORDS))
    
    if birthday_overlap > policy_overlap:
        return "birthday_mode"
    return "policy_mode" # Default fallback for advocacy

def retrieve_context(query: str, mode: str, top_k: int = 2) -> list[dict]:
    """Retrieve verified facts, filtering by source_type."""
    where_filter = None
    if mode == "policy_mode":
        where_filter = {"source_type": "policy_legal"}
    elif mode == "birthday_mode":
        where_filter = {"source_type": "general_biology"}

    # Query ChromaDB using raw text (it embeds automatically)
    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        where=where_filter
    )
    
    formatted_context = []
    for i in range(len(results["ids"][0])):
        formatted_context.append({
            "text": results["documents"][0][i],
            "title": results["metadatas"][0][i]["title"],
            "authority": results["metadatas"][0][i]["authority"]
        })
        
    return formatted_context