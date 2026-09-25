import os
import re

def insert_ssml(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Find the synthesis input
    old_input = "synthesis_input = texttospeech.SynthesisInput(text=narration)"
    new_input = """
        def text_to_ssml(text):
            import re
            t = re.sub(r'([”"])([\s]*)([A-Z])', r'\\1<break time="450ms"/>\\2\\3', text)
            t = re.sub(r'([.?!])\s+', r'\\1<break time="750ms"/> ', t)
            return f'<speak><prosody rate="0.9" pitch="-1.5st">{t}</prosody></speak>'

        synthesis_input = texttospeech.SynthesisInput(ssml=text_to_ssml(narration))
    """
    content = content.replace(old_input, new_input)
    
    old_refl_input = "synthesis_input = texttospeech.SynthesisInput(text=reflection_text)"
    new_refl_input = "synthesis_input = texttospeech.SynthesisInput(ssml=text_to_ssml(reflection_text))"
    content = content.replace(old_refl_input, new_refl_input)

    with open(filepath, 'w') as f:
        f.write(content)

insert_ssml('/home/hkserver/myentrykey-auto-youtube/kidoory_engine/media_synthesizer.py')
