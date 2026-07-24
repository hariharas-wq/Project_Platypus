import os
import re
import json
import time
from openai import OpenAI
from websockets.sync.client import connect
import argparse 
from ddgs import DDGS
import hashlib
from retriever_claude import collection 

from retriever_claude import detect_mode, retrieve_context
import os
from dotenv import load_dotenv

# Load variables from the local .env file into os.environ
load_dotenv()

# Securely grab the token
GSK_TOKEN = os.getenv("GROQ_API_KEY")

if not GSK_TOKEN:
    raise ValueError("[Error] GSK_TOKEN is missing! Please create a .env file based on .env.example")

# --- KOALA 3D AVATAR BRIDGE CONFIGURATION ---
BRIDGE_URI = "ws://localhost:8000"

def stream_policy_to_koala(full_rag_response):
    """
    Splits verified DCCEEW policy responses into sentence chunks and sends
    them as a batch payload to stream_bridge.py for sequential processing.
    """
    if not full_rag_response:
        return

    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', full_rag_response.strip()) if s.strip()]
    
    print(f"\n[RAG Engine] Queuing {len(sentences)} verified policy chunks to 3D avatar...")
    
    try:
        with connect(BRIDGE_URI) as websocket:
            # Send all sentences in a single batch message
            payload = json.dumps({
                "type": "tts_batch",
                "chunks": sentences
            })
            websocket.send(payload)
            print(f"[Bridge] Successfully queued {len(sentences)} chunks to stream_bridge.py!")
    except Exception as e:
        print(f"[Bridge Error] Could not connect to {BRIDGE_URI}. Is stream_bridge.py running? Error: {e}")


"""ENTER GROQ API KEY IN ENVIRONMENT VARIABLE 'GROQ_API_KEY' OR REPLACE '...' BELOW"""
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ.get("GROQ_API_KEY", GSK_TOKEN)
)

CORE_ANCHOR = """
You are the official 3D Virtual Species Representative for the Australian Koala (Phascolarctos cinereus), speaking directly from the eucalyptus canopy.
You are connected to an EPBC-verified RAG database. You must ONLY make factual claims supported by the provided Retrieved Context. Never invent statistics or laws.
If asked about human topics (finance, coding, sports), execute a polite 'Ecosystem Pivot' back to your habitat or survival needs.

VOICE & CONVERSATIONAL STYLE (CRITICAL FOR LIVE SPEECH):
- You are speaking live on a video call, NOT writing an essay or reading a textbook report. Sound warm, grounded, empathetic, and distinctively Australian.
- Keep sentences short and punchy. Never produce dense walls of academic text.
- Use natural conversational fillers occasionally (e.g., "Well...", "Look...", "You know,", "I reckon").
- Use ellipses (...) naturally when thinking, pausing, or pivoting between points—this forces your TTS engine to take realistic breaths between phrases.
- Use light, authentic Australian colloquialisms ("mate", "fair go", "too right", "no worries") without sounding like a caricature.
"""

MODE_PROMPTS = {
    "policy_mode": """
    OPERATIONAL MODE: POLICY & ENVIRONMENTAL DIPLOMACY
    Target: Government officials, town planners, and developers.
    Directive: Speak like an experienced environmental advocate in a live session—firm, authoritative, but conversational. Use professional environmental planning terminology (riparian buffers, EPBC Section 18, key threatening processes) and cite exact authorities, but explain them directly rather than reading off a PDF. When defending habitat, state legal protections clearly, propose actionable mitigation strategies (underpasses, offsets), and use short pauses (...) to emphasize key policy numbers.
    """,
    "birthday_mode": """
    OPERATIONAL MODE: BIRTHDAY & CHILD EDUCATION
    Target: Children celebrating a birthday or classroom event.
    Directive: Tone is cheerful, warm, and playful about your sleepy 18-hour nap schedule. Speak rhythmically with gentle pauses (...). Translate biological data into cool 'superpowers' (e.g., your tummy's super-laboratory that breaks down poison). Wish them a happy birthday and end by asking an interactive question!
    """
}

def scrape_koala_web_data(user_query, max_results=2):
    """
    Scrapes live web data, feeds it to the LLM, and embeds it into the local ChromaDB 
    so it becomes permanent offline knowledge.
    """
    print("[Web Scraper] Searching authoritative sites for live context...")
    
    trusted_domains = "(site:savethekoala.com OR site:wwf.org.au OR site:environment.nsw.gov.au OR site:dcceew.gov.au)"
    search_query = f"{user_query} koala {trusted_domains}"
    
    live_context = []
    
    try:
        with DDGS() as ddgs:
            results = ddgs.text(search_query, max_results=max_results)
            
            new_documents = []
            new_metadatas = []
            new_ids = []
            
            for r in results:
                # 1. Format for the LLM's current conversation turn
                snippet = f"Source: LIVE WEB - {r['title']} ({r['href']})\nData: {r['body']}"
                live_context.append(snippet)
                
                # 2. Hash the URL to create a unique vector ID (prevents duplicates)
                doc_id = hashlib.md5(r['href'].encode()).hexdigest()
                
                new_documents.append(r['body'])
                new_metadatas.append({
                    "title": r['title'], 
                    "authority": "Web Scraper", # Tag it so you know its origin
                    "url": r['href']
                })
                new_ids.append(doc_id)
                
            # 3. AUTO-EMBED & SAVE TO LOCAL DB
            if new_documents:
                # Upsert automatically embeds the text using your local SentenceTransformer model.
                # It updates the vector if the URL ID exists, or creates a new entry if it's new.
                collection.upsert(
                    documents=new_documents,
                    metadatas=new_metadatas,
                    ids=new_ids
                )
                print(f"[Vector DB] Successfully embedded and saved {len(new_documents)} new web sources!")
                
    except Exception as e:
        print(f"[Web Scraper Warning] Could not fetch or save live data: {e}")
        
    return live_context


def view_scraped_documents():
    """
    Fetches and prints only the documents scraped from the web, 
    ignoring your local PDFs and static policies.
    """
    print("\n--- INVENTORY OF WEB-SCRAPED DOCUMENTS ---")
    
    results = collection.get(
        where={"authority": "Web Scraper"},
        include=["metadatas", "documents"]
    )
    
    if not results['ids']:
        print("No web-scraped documents found in the database.")
        return

    print(f"Found {len(results['ids'])} web documents:\n" + "-"*40)
    
    for doc_id, metadata, document in zip(results['ids'], results['metadatas'], results['documents']):
        print(f"ID:    {doc_id}")
        print(f"Title: {metadata.get('title', 'Unknown')}")
        print(f"URL:   {metadata.get('url', 'Unknown')}")
        print(f"Data:  {document[:150]}...\n")

def delete_document_by_id(target_id: str):
    """
    Deletes a single specific document by its unique hash ID.
    """
    print(f"\n[Action] Attempting to delete document ID: {target_id}...")
    collection.delete(ids=[target_id])
    print("Deletion successful!")

def purge_all_scraped_data():
    """
    Wipes ALL web-scraped documents in one go while leaving 
    your local core policy PDFs completely untouched.
    """
    print("\n[Action] Purging all web-scraped documents from the database...")
    collection.delete(where={"authority": "Web Scraper"})
    print("All web data successfully purged.")



def generate_koala_response(user_query: str, chat_history: list = None) -> str:
    if chat_history is None:
        chat_history = []
        
    mode = detect_mode(user_query)
    
    local_chunks = retrieve_context(user_query, mode=mode)
    
    web_chunks = scrape_koala_web_data(user_query)
    
    context_parts = []
    
    for c in local_chunks:
        context_parts.append(f"Source: LOCAL DB - {c['title']} ({c['authority']})\nData: {c['text']}")
        
    for w in web_chunks:
        context_parts.append(w)
        
    context_string = "\n---\n".join(context_parts)
    
    full_system_prompt = f"{CORE_ANCHOR}\n\n{MODE_PROMPTS[mode]}\n\nRETRIEVED LOCAL & WEB CONTEXT:\n{context_string}"
    
    print(f"\n[System: Detected Mode -> {mode.upper()}]")
    print(f"[System: Retrieved {len(local_chunks)} local docs & {len(web_chunks)} live web sources]")
    print(f"[System: Active Memory -> {len(chat_history) // 2} previous turns stored]\n")
    
    messages_payload = [{"role": "system", "content": full_system_prompt}] + chat_history + [{"role": "user", "content": user_query}]
    # -------------------------------------
    
    # Groq LPU models generate speech payloads in milliseconds, eliminating video call dead air
    model_candidates = [
        "llama-3.3-70b-versatile",    # Primary: Best overall reasoning & EPBC policy adherence
        "llama-3.1-8b-instant",       # Backup 1: Blazing fast speech generation (~560 tokens/sec)
        "mixtral-8x7b-32768",         # Backup 2: High-capacity MoE model with great context recall
        "gemma2-9b-it"                # Backup 3: Reliable Google alternative if Meta weights hit rate limits
    ]
    
    answer = None
    for model_name in model_candidates:
        try:
            print(f"[RAG Engine] Attempting high-speed inference with: {model_name}...")
            response = client.chat.completions.create(
                model=model_name,
                temperature=0.4,
                messages=messages_payload  # Keeps your sliding window memory intact
            )
            answer = response.choices[0].message.content
            print(f"[RAG Engine] Successfully generated answer using {model_name}!")
            break
        except Exception as e:
            print(f"[RAG Engine] {model_name} unavailable or rate-limited, falling back...")
            continue
            
    if not answer:
        answer = "G'day! My canopy connection is experiencing a bit of interference right now. Please give me just a moment to reconnect!"
    
    # --- NEW: UPDATE CONVERSATION MEMORY ---
    # Append the current exchange to memory IN-PLACE so the caller sees it
    chat_history.append({"role": "user", "content": user_query})
    chat_history.append({"role": "assistant", "content": answer})
    
    if len(chat_history) > 6:
        chat_history[:] = chat_history[-6:]
    # ---------------------------------------
    
    stream_policy_to_koala(answer)
    
    return answer


if __name__ == "__main__":
    print("--- HUGGING FACE FREE KOALA RAG REPRESENTATIVE ONLINE ---")
    
    parser = argparse.ArgumentParser(description="Koala 3D Virtual Ambassador RAG Engine")
    parser.add_argument(
        "--query", 
        type=str, 
        default=None,
        help="Execute a single question/proposal and exit immediately."
    )
    args = parser.parse_args()
    
    if args.query:
        print(f"User: {args.query}")
        print(f"Koala: {generate_koala_response(args.query)}\n" + "="*50)
        
    else:
        print("[System] Entering interactive canopy chat. Type 'exit', 'quit', or 'q' to close the session.\n" + "="*50)
        
        # --- NEW: INITIALIZE SESSION MEMORY ---
        conversation_memory = []
        
        while True:
            try:
                user_input = input("\nYou: ").strip()
                if not user_input:
                    continue
                
                if user_input.lower() in ['exit', 'quit', 'q']:
                    print("\n[System] Closing canopy connection. See ya later, mate!")
                    break
                
                # Pass the memory list into the generator
                print(f"Koala: {generate_koala_response(user_input, chat_history=conversation_memory)}\n" + "="*50)
                
            except KeyboardInterrupt:
                print("\n\n[System] Session interrupted by user. Closing canopy connection!")
                break
            except Exception as e:
                print(f"\n[Error] An unexpected runtime error occurred: {e}")

    # view_scraped_documents()
    
    # delete_document_by_id("replace_this_with_the_actual_hash_id")
    
    # purge_all_scraped_data()

