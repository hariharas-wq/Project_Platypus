import bpy
import json
import base64
import os
import aud
import threading
import time
import asyncio
import sys
import subprocess

# --- AUTO-INSTALL DEPENDENCIES INTO BLENDER ---
try:
    import websockets
except ModuleNotFoundError:
    print("[Setup] WebSockets not found. Installing into Blender's bundled Python...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
    import websockets
    print("[Setup] WebSockets installed successfully!")

# --- BLENDER RIG CONFIGURATION ---
MESH_OBJECT_NAME = "Koala_Low_poly"  # Ensure this matches your mesh name exactly

# Mapping all 9 Rhubarb speech phonemes to your custom shape keys
VISEME_MAP = {
    "X": "Basis",       # Silence / Resting closed mouth
    "A": "Basis",       # Closed lips (M, P, B sounds)
    "B": "Mouth_Open",  # Slightly open, teeth visible (S, T, K sounds)
    "C": "Mouth_Open",  # Wide open mouth (E, AE sounds)
    "D": "Mouth_Open",  # Wide open mouth (A, I sounds)
    "E": "Mouth_O",     # Rounded lips (O, U sounds)
    "F": "Mouth_Open",  # Upper teeth on lower lip (F, V sounds)
    "G": "Mouth_Open",  # Tongue behind teeth (Th sounds)
    "H": "Mouth_Open"   # General open mouth (L sounds)
}

def reset_all_shape_keys(mesh_obj):
    """Sets all lip-sync shape keys to 0.0"""
    if not mesh_obj.data.shape_keys:
        return
    for shape_name in VISEME_MAP.values():
        if shape_name in mesh_obj.data.shape_keys.key_blocks:
            mesh_obj.data.shape_keys.key_blocks[shape_name].value = 0.0

def apply_viseme(mesh_obj, viseme_char):
    """Activates the specific shape key for the current phoneme."""
    reset_all_shape_keys(mesh_obj)
    target_key = VISEME_MAP.get(viseme_char, "Basis")
    
    if target_key in mesh_obj.data.shape_keys.key_blocks:
        mesh_obj.data.shape_keys.key_blocks[target_key].value = 1.0

def play_speech_animation(audio_path, visemes):
    """Runs on a background thread to sync audio playback with Blender shape keys."""
    mesh_obj = bpy.data.objects.get(MESH_OBJECT_NAME)
    if not mesh_obj:
        print(f"[Error] Could not find object named {MESH_OBJECT_NAME}")
        return

    # 1. Play Audio using Blender's aud module
    device = aud.Device()
    sound = aud.Sound(audio_path)
    handle = device.play(sound)
    
    start_time = time.time()
    
    # 2. Iterate through timestamped visemes
    for cue in visemes:
        cue_start = cue["start"]
        cue_end = cue["end"]
        viseme_val = cue["value"]
        
        # Wait until the audio reaches this cue's timestamp
        while (time.time() - start_time) < cue_start:
            time.sleep(0.005)
            
        # Push Shape Key update to Blender's main thread safely
        bpy.app.timers.register(lambda v=viseme_val: apply_viseme(mesh_obj, v) or None)
        
    # Wait for audio to finish then reset mouth to Rest
    while handle.status == aud.STATUS_PLAYING:
        time.sleep(0.05)
    bpy.app.timers.register(lambda: reset_all_shape_keys(mesh_obj) or None)
    print("[Playback] Animation Finished.")

async def listen_to_bridge():
    uri = "ws://localhost:8000"
    async with websockets.connect(uri) as websocket:
        print("[Blender] Connected to Stream Bridge!")
        
        # Send a test string representing what our RAG engine produced
        test_msg = json.dumps({"text": "G'day! I am the official Australian Koala representative. Let's protect our forest canopy!"})
        await websocket.send(test_msg)
        
        while True:
            response = await websocket.recv()
            data = json.loads(response)
            
            # Decode audio
            temp_wav = os.path.join(bpy.app.tempdir, "temp_koala_stream.wav")
            with open(temp_wav, "wb") as f:
                f.write(base64.b64decode(data["audio_base64"]))
                
            visemes = data.get("visemes", [])
            
            # Trigger playback thread so we don't freeze the Blender UI
            threading.Thread(target=play_speech_animation, args=(temp_wav, visemes), daemon=True).start()

def start_client_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(listen_to_bridge())

# Launch client in background
threading.Thread(target=start_client_thread, daemon=True).start()
print("[Blender Script] Listening thread started.")