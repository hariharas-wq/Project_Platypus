import torch
import transformers.pytorch_utils
import os
import sys
import wave
import time
import re
from pydub import AudioSegment
from pydub.silence import detect_nonsilent

# Auto-accept the XTTS v2 license agreement
os.environ["COQUI_TOS_AGREED"] = "1"

# --- MONKEY-PATCH FOR COQUI TTS COMPATIBILITY ---
if not hasattr(transformers.pytorch_utils, 'isin_mps_friendly'):
    transformers.pytorch_utils.isin_mps_friendly = torch.isin
# ------------------------------------------------

# --- SMART WINDOWS ESPEAK-NG LINKER ---
possible_paths = [
    r"C:\Program Files\eSpeak NG",
    r"C:\Program Files (x86)\eSpeak NG"
]

espeak_path = None
for p in possible_paths:
    if os.path.exists(p):
        espeak_path = p
        break

if not espeak_path:
    print("[Error] eSpeak NG folder not found on your system!")
    print("Please open PowerShell and run: winget install eSpeak-NG.eSpeak-NG")
    sys.exit(1)

os.environ["PHONEMIZER_ESPEAK_LIBRARY"] = os.path.join(espeak_path, "libespeak-ng.dll")
os.environ["PHONEMIZER_ESPEAK_PATH"] = espeak_path
os.environ["PATH"] = espeak_path + os.pathsep + os.environ.get("PATH", "")
print(f"[Setup] Found and linked eSpeak NG at: {espeak_path}")

import asyncio
import websockets
import json
import base64
import subprocess
from TTS.api import TTS

# --- CONFIGURATION ---
PORT = 8000
AUDIO_OUTPUT_PATH = r"koala_git\koala_speech.wav"
RHUBARB_EXE_PATH = r"koala_git\Rhubarb-Lip-Sync-1.14.0-Windows\Rhubarb-Lip-Sync-1.14.0-Windows\rhubarb.exe"

INTER_SENTENCE_PAUSE = -0.15
connected_clients = set()

print("[Init] Loading XTTS v2 Generative Voice Model...")
tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=False, gpu=True)
print("[Init] XTTS v2 Ready.")

print("[System] Pre-computing Australian speaker conditioning latents...")
GPT_COND_LATENT, SPEAKER_EMBEDDING = tts.synthesizer.tts_model.get_conditioning_latents(
    audio_path=[r"koala_git\aussie_clip1.wav", r"koala_git\aussie_clip2.wav", r"koala_git\aussie_clip3.wav"]
)
print("[System] Voice profile locked and loaded into memory!")

# --- CUDA WARM-UP PASS ---
print("[System] Warming up CUDA VRAM allocator for XTTS v2...")
try:
    tts.synthesizer.tts_model.inference(
        text="G'day mate, system online.",
        language="en",
        gpt_cond_latent=GPT_COND_LATENT,
        speaker_embedding=SPEAKER_EMBEDDING
    )
    print("[System] CUDA VRAM warmed up and locked!")
except Exception as e:
    print(f"[Warning] Warm-up pass skipped: {e}")

def get_audio_duration(file_path: str) -> float:
    """Calculates the exact duration of a WAV file in seconds using Python's wave module."""
    try:
        with wave.open(file_path, 'rb') as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return frames / float(rate)
    except Exception as e:
        print(f"[Warning] Could not read WAV duration: {e}")
        return 2.0

def clean_text_for_tts(text: str) -> str:
    """Cleans raw LLM text specifically for XTTS v2 to prevent breath hallucinations."""
    if not text:
        return ""

    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'[\*_`>#]', '', text)

    acronym_map = {
        r'\bEPBC\b': 'E P B C', r'\bRAG\b': 'R A G', r'\bNSW\b': 'N S W',
        r'\bWWF\b': 'W W F', r'\bAKF\b': 'A K F', r'\bKPoM\b': 'K-PoM',
        r'\bDCCEEW\b': 'D C C E E W', r'\bLPU\b': 'L P U'
    }
    for pattern, replacement in acronym_map.items():
        text = re.sub(pattern, replacement, text)

    text = re.sub(r'\b([A-Z]{3,})\b', lambda m: " ".join(list(m.group(1))), text)
    text = re.sub(r'\.{2,}', '.', text)
    text = re.sub(r'\s*[\-—]\s*', ', ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    return text

def create_streaming_chunks(text: str) -> list[str]:
    """
    Strict Asymmetric Chunking: Hard-caps chunks to a maximum of 12 words 
    to prevent GPU inference latency blowout spikes on long clauses.
    """
    if not text:
        return []

    cleaned_text = clean_text_for_tts(text)
    clauses = re.split(r'(?<=[.!?,])\s+|\n+', cleaned_text)
    
    optimized_chunks = []
    buffer = ""
    is_first_chunk = True

    for clause in clauses:
        clause = clause.strip()
        if not clause:
            continue

        sub_words = clause.split()
        if len(sub_words) > 12:
            # Break long clauses into smaller sub-chunks manually
            for i in range(0, len(sub_words), 10):
                sub_chunk = " ".join(sub_words[i:i+10])
                if buffer:
                    combined = f"{buffer} {sub_chunk}".strip()
                    if len(combined.split()) <= 12:
                        buffer = combined
                        continue
                    else:
                        optimized_chunks.append(buffer)
                        buffer = sub_chunk
                else:
                    buffer = sub_chunk
            continue

        combined_test = f"{buffer} {clause}".strip() if buffer else clause
        word_count = len(combined_test.split())

        # Strict target: 6 words for chunk 1, max 12 words for subsequent chunks
        target_max = 6 if is_first_chunk else 12

        if word_count <= target_max:
            buffer = combined_test
        else:
            if buffer:
                optimized_chunks.append(buffer)
                buffer = clause
                is_first_chunk = False 
            else:
                optimized_chunks.append(clause)
                buffer = ""
                is_first_chunk = False

    if buffer:
        optimized_chunks.append(buffer)

    return optimized_chunks

def trim_generated_audio(file_path: str, silence_thresh_db: int = -45):
    """Slices off baked-in head/tail silence from the XTTS generated file."""
    try:
        sound = AudioSegment.from_file(file_path)
        nonsilent_ranges = detect_nonsilent(
            sound, 
            min_silence_len=50, 
            silence_thresh=silence_thresh_db
        )
        
        if nonsilent_ranges:
            start_trim = max(0, nonsilent_ranges[0][0] - 25)
            end_trim = min(len(sound), nonsilent_ranges[-1][1] + 25)
            
            trimmed_sound = sound[start_trim:end_trim]
            trimmed_sound.export(file_path, format="wav")
            
    except Exception as e:
        print(f"[Warning] Failed to trim audio: {e}")

def generate_tts_and_visemes(text_input: str) -> dict:
    """Generates audio and visemes while profiling the exact millisecond latency of each step."""
    t_start = time.perf_counter()
    
    t0 = time.perf_counter()
    cleaned_text = clean_text_for_tts(text_input)
    t_prep = (time.perf_counter() - t0) * 1000
    
    print(f"\n--- [Latency Benchmark: '{cleaned_text[:35]}...'] ---")
    print(f" ├─ Text Pre-processing: {t_prep:6.1f} ms")
    
    t1 = time.perf_counter()
    out = tts.synthesizer.tts_model.inference(
        text=cleaned_text,
        language="en",
        gpt_cond_latent=GPT_COND_LATENT,
        speaker_embedding=SPEAKER_EMBEDDING
    )
    tts.synthesizer.save_wav(wav=out["wav"], path=AUDIO_OUTPUT_PATH)
    t_tts = (time.perf_counter() - t1) * 1000
    print(f" ├─ XTTS v2 Synthesis:   {t_tts:6.1f} ms")
    
    t2 = time.perf_counter()
    trim_generated_audio(AUDIO_OUTPUT_PATH)
    t_trim = (time.perf_counter() - t2) * 1000
    print(f" ├─ Pydub Silence Trim:  {t_trim:6.1f} ms")
    
    t3 = time.perf_counter()
    cmd = [
        RHUBARB_EXE_PATH,
        "-f", "json",
        "--machineReadable",
        "-r", "phonetic",
        AUDIO_OUTPUT_PATH
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        rhubarb_data = json.loads(result.stdout)
        visemes = rhubarb_data.get("mouthCues", [])
    except Exception as e:
        print(f"[Error] Rhubarb failed: {e}")
        visemes = []
        
    t_rhubarb = (time.perf_counter() - t3) * 1000
    print(f" └─ Rhubarb Lip-Sync:    {t_rhubarb:6.1f} ms")
    
    total_time = (time.perf_counter() - t_start) * 1000
    print(f" 📊 TOTAL CHUNK LATENCY: {total_time:6.1f} ms\n")

    with open(AUDIO_OUTPUT_PATH, "rb") as wav_file:
        audio_base64 = base64.b64encode(wav_file.read()).decode("utf-8")

    return {
        "audio_base64": audio_base64,
        "visemes": visemes
    }

async def broadcast_payload(payload: dict):
    if not connected_clients:
        print("[Warning] No connected clients to receive broadcast (Is Blender running?)")
        return
    
    for client in list(connected_clients):
        try:
            await client.send(json.dumps(payload))
        except websockets.exceptions.ConnectionClosed:
            connected_clients.discard(client)
            
    print(f"[WebSocket] Broadcasted audio to {len(connected_clients)} active client(s).")

async def handle_connection(websocket, *args):
    connected_clients.add(websocket)
    print(f"[WebSocket] Client connected: {websocket.remote_address}")
    
    try:
        async for message in websocket:
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == "tts_batch":
                raw_text = " ".join(data.get("chunks", []))
            else:
                raw_text = data.get(text, "") if "text" in data else data.get("text", "")

            if not raw_text.strip():
                continue

            streaming_chunks = create_streaming_chunks(raw_text)
            print(f"[Bridge] Pipelining {len(streaming_chunks)} rigid-bounded speech chunks...")

            for i, chunk in enumerate(streaming_chunks, 1):
                clean_chunk = chunk.strip()
                if not clean_chunk:
                    continue

                payload = await asyncio.to_thread(generate_tts_and_visemes, clean_chunk)
                await broadcast_payload(payload)

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.discard(websocket)
        print(f"[WebSocket] Client disconnected. (Remaining active clients: {len(connected_clients)})")

async def main():
    print(f"[System] Stream Bridge WebSocket Server live on ws://localhost:{PORT}")
    async with websockets.serve(
        handle_connection, 
        "localhost", 
        PORT, 
        max_size=10 * 1024 * 1024,
        ping_interval=None,
        ping_timeout=None
    ):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())