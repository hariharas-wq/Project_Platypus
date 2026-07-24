from pydub import AudioSegment
from prep_reference_audio import generate_xtts_reference_clips

print("[Processing] Loading your 3 input files...")
audio1 = AudioSegment.from_file(r"koala_git\aussie_reference.wav")
audio2 = AudioSegment.from_file(r"koala_git\aussie_reference1.wav")
audio3 = AudioSegment.from_file(r"koala_git\aussie_reference2.wav")

print("[Processing] Merging files into a master track...")
combined_audio = audio1 + audio2 + audio3
master_file_name = "master_raw_aussie.wav"
combined_audio.export(master_file_name, format="wav")

print("[Processing] Slicing and extracting optimal XTTS v2 clips...")
generate_xtts_reference_clips(
    input_audio_path=master_file_name,
    output_dir=".",
    min_clip_len_sec=5.0,
    max_clip_len_sec=8.0,  # Capped at 8s to ensure total time stays under 25s
    silence_thresh_db=-40
)