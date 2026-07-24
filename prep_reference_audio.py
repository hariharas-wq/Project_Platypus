# prep_reference_audio.py
import os
from pydub import AudioSegment, effects
from pydub.silence import split_on_silence

def generate_xtts_reference_clips(
    input_audio_path: str,
    output_dir: str = r"koala_git",
    min_clip_len_sec: float = 5.0,
    max_clip_len_sec: float = 10.0,
    silence_thresh_db: int = -40,
    min_silence_len_ms: int = 400
):
    """
    Cleans a long audio file by stripping silence, normalizing volume, 
    and combining audio segments into ideal 5-10s clips for XTTS v2.
    """
    if not os.path.exists(input_audio_path):
        print(f"[Error] Source audio file not found at: {input_audio_path}")
        return []

    print(f"[Loading] Reading source audio: {input_audio_path}...")
    sound = AudioSegment.from_file(input_audio_path)
    
    print("[Processing] Normalizing audio volume levels...")
    sound = effects.normalize(sound)
    
    print("[Processing] Detecting and removing dead air/silence...")
    raw_chunks = split_on_silence(
        sound,
        min_silence_len=min_silence_len_ms,
        silence_thresh=silence_thresh_db,
        keep_silence=150  # Retain a tiny 150ms natural breath padding around spoken words
    )
    
    if not raw_chunks:
        print("[Error] Couldn't isolate any speech. Try raising silence_thresh_db (e.g. to -35).")
        return []

    print(f"[Info] Found {len(raw_chunks)} spoken segments. Grouping into {min_clip_len_sec}-{max_clip_len_sec}s clips...")
    
    combined_clips = []
    current_clip = AudioSegment.empty()
    
    for chunk in raw_chunks:
        if (len(current_clip) + len(chunk)) / 1000.0 <= max_clip_len_sec:
            current_clip += chunk
        else:
            if len(current_clip) / 1000.0 >= min_clip_len_sec:
                combined_clips.append(current_clip)
            current_clip = chunk  
            
    # Append any remaining audio chunk
    if len(current_clip) / 1000.0 >= min_clip_len_sec:
        combined_clips.append(current_clip)
        
    if not combined_clips:
        print("[Warning] Could not assemble any clips meeting the length criteria. Lower min_clip_len_sec.")
        return []

    os.makedirs(output_dir, exist_ok=True)
    saved_files = []
    
    # Take up to the 3 best clips (XTTS v2 performs best with 2 to 3 distinct clips)
    for i, clip in enumerate(combined_clips[:3], 1):
        output_filename = f"aussie_clip{i}.wav"
        output_path = os.path.join(output_dir, output_filename)
        
        # Resample to 22,050Hz Mono WAV for neural audio models
        processed_clip = clip.set_frame_rate(22050).set_channels(1)
        processed_clip.export(output_path, format="wav")
        
        duration = len(processed_clip) / 1000.0
        print(f"  -> Exported: {output_filename} ({duration:.2f}s)")
        saved_files.append(output_filename)
        
    print(f"\n[Success] Done! Generated {len(saved_files)} reference clips ready for XTTS v2.")
    return saved_files


