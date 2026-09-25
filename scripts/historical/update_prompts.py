import os
import re

ROOT = "/home/hkserver/myentrykey-auto-youtube/kidoory_engine"

def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

# Update produce_story.py
ps_path = os.path.join(ROOT, "produce_story.py")
ps = read_file(ps_path)
ps = re.sub(
    r"2\. For each scene, 'narration' MUST be warm, evocative storybook prose strictly between 60 and 80 words\.",
    r"2. For each scene, 'narration' MUST be warm, evocative storybook prose strictly between 60 and 80 words. The total story length MUST be 450 to 600 words. Narrative structure: Gentle protagonist discovery -> magical world element -> heartwarming act of kindness/courage -> serene, sleep-inducing ending.",
    ps
)
ps = re.sub(
    r"3\. 'visual_prompt' must describe high-fidelity 8k Pixar/Ghibli style visuals maintaining strict character & lighting consistency \(in English\)\.",
    r"3. 'visual_prompt' must describe visuals using EXACTLY: 'Masterpiece 3D children's storybook illustration in the heartwarming style of modern Pixar and Studio Ghibli, 8k resolution, dreamy volumetric golden-hour lighting, cozy magical atmosphere, rich vibrant color palette, endearing character design with large soft expressive eyes, award-winning concept art, trending on ArtStation.' Negative constraints to include: 'Exclude photorealistic human skin pores, uncanny valley facial distortion, creepy horror elements, dark grim aesthetics, text, watermarks, bad anatomy, deformed limbs.'",
    ps
)
# Update font to Poppins/Fredoka
ps = re.sub(r'font_name = get_font_for_language.*?', 'font_name = "Poppins"', ps)
write_file(ps_path, ps)

# Update idea_brain.py
ib_path = os.path.join(ROOT, "idea_brain.py")
ib = read_file(ib_path)
ib = re.sub(
    r"Cinematic visual palette, lighting conditions, and aesthetic tone \(Pixar and Studio Ghibli inspired\)\.",
    r"Masterpiece 3D children's storybook illustration in the heartwarming style of modern Pixar and Studio Ghibli, 8k resolution, dreamy volumetric golden-hour lighting, cozy magical atmosphere, rich vibrant color palette, endearing character design with large soft expressive eyes, award-winning concept art, trending on ArtStation. HARD NEGATIVE: Exclude photorealistic human skin pores, uncanny valley facial distortion, creepy horror elements, dark grim aesthetics, text, watermarks, bad anatomy, deformed limbs.",
    ib
)
write_file(ib_path, ib)

# Update batch_image_generator.py
big_path = os.path.join(ROOT, "batch_image_generator.py")
big = read_file(big_path)
big = re.sub(r'Cinematic 3D animation, blending Pixar character warmth and Studio Ghibli painterly landscapes\.', "Masterpiece 3D children's storybook illustration in the heartwarming style of modern Pixar and Studio Ghibli, 8k resolution, dreamy volumetric golden-hour lighting, cozy magical atmosphere, rich vibrant color palette, endearing character design with large soft expressive eyes, award-winning concept art, trending on ArtStation.", big)
write_file(big_path, big)

