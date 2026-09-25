import os

def insert_tracker(path):
    if not os.path.exists(path): return
    with open(path, "r") as f:
        content = f.read()
    
    if "track_tts_usage" not in content:
        content = "from tts_tracker import track_tts_usage\n" + content
        content = content.replace(
            "synthesis_input = texttospeech.SynthesisInput(text=narration)", 
            "track_tts_usage(len(narration))\n        synthesis_input = texttospeech.SynthesisInput(text=narration)"
        )
        content = content.replace(
            "synthesis_input = texttospeech.SynthesisInput(text=reflection_text)", 
            "track_tts_usage(len(reflection_text))\n        synthesis_input = texttospeech.SynthesisInput(text=reflection_text)"
        )
        with open(path, "w") as f:
            f.write(content)

insert_tracker("/home/hkserver/myentrykey-auto-youtube/kidoory_engine/produce_story.py")
insert_tracker("/home/hkserver/myentrykey-auto-youtube/kidoory_engine/media_synthesizer.py")

