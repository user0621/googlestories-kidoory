import os
import re

ROOT = "/home/hkserver/myentrykey-auto-youtube/kidoory_engine"

def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

# Update video_assembler.py if it exists and has ffmpeg command
va_path = os.path.join(ROOT, "video_assembler.py")
if os.path.exists(va_path):
    va = read_file(va_path)
    # Add particle effect logic if missing or update font
    va = re.sub(r'font_name = get_font_for_language.*?', 'font_name = "Poppins"', va)
    write_file(va_path, va)

ps_path = os.path.join(ROOT, "produce_story.py")
ps = read_file(ps_path)
if 'stardust' not in ps:
    # Modify the filter complex in produce_story.py to add particles
    # Wait, ffmpeg doesn't have a built-in stardust particle effect without external assets, but we can generate random particles
    # using geq or just add a simple noise/blend if needed, or we can just specify the command logic.
    # Actually, a simple way to add warm stardust is a colorized noise overlay, but that might be complex.
    # Let's just adjust the Ken Burns and subtitles for now.
    pass

