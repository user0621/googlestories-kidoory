import os
import json

path = "/home/hkserver/myentrykey-auto-youtube/kidoory_engine/produce_episode.py"
with open(path, "r") as f:
    content = f.read()

new_prompt = """
        prompt = f'''You are the Autonomous Story Director.
        Write Episode {ep_id} of the movie {movie_struct.get("movie_title")}.
        Episode Summary: {theme}
        Character Continuity: {json.dumps(char_bible)}
        
        CRITICAL RULES:
        1. Generate exactly 8 scenes.
        2. 'narration' MUST be 80-110 words per scene (total ~650-900 words).
        3. 'visual_prompt' MUST use: "Masterpiece 3D children's storybook illustration in the heartwarming style of modern Pixar and Studio Ghibli, 8k resolution, dreamy volumetric golden-hour lighting, cozy magical atmosphere, rich vibrant color palette, endearing character design with large soft expressive eyes, award-winning concept art, trending on ArtStation."
        4. In every 'visual_prompt', YOU MUST explicitly include the character's exact visual specifications from the Character Continuity (e.g., boots, pendant, braided hair) to prevent clothing shifts.
        5. Add negative prompt to every 'visual_prompt': "text, letters, watermarks, signature, words".
        6. Maintain strict continuity (wardrobe, items).
        '''
"""
import re
content = re.sub(r'prompt = f"""(.*?)"""', new_prompt.strip(), content, flags=re.DOTALL)
with open(path, "w") as f:
    f.write(content)
