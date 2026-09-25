import os

filepath = '/home/hkserver/myentrykey-auto-youtube/kidoory_engine/media_synthesizer.py'
with open(filepath, 'r') as f:
    content = f.read()

mastering_func = """
def master_audio(input_path, output_path, bgm_path=None):
    if bgm_path and os.path.exists(bgm_path):
        # Normalize and mix
        cmd = [
            "ffmpeg", "-y", "-i", input_path, "-i", bgm_path,
            "-filter_complex", 
            "[0:a]loudnorm=I=-16:TP=-1.5:LRA=11[norm0];"
            "[1:a]volume=-24dB,afade=t=in:st=0:d=2,afade=t=out:st=9999:d=4[bgm];"
            "[norm0][bgm]amix=inputs=2:duration=first:dropout_transition=2",
            "-c:a", "libmp3lame", "-q:a", "2", output_path
        ]
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        # Just normalize
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-c:a", "libmp3lame", "-q:a", "2", output_path
        ]
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

"""

if "def master_audio" not in content:
    content = content.replace("def get_audio_duration", mastering_func + "def get_audio_duration")

content = content.replace('audio_file.write(response.audio_content)', 'audio_file.write(response.audio_content)\n\n        # Master audio\n        master_audio(out_path, out_path.replace(".mp3", "_mastered.mp3"))')

with open(filepath, 'w') as f:
    f.write(content)

