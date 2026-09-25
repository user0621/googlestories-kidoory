import os
import re

ROOT = "/home/hkserver/myentrykey-auto-youtube/kidoory_engine"

def replace_in_file(path, replacements):
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return
    
    for old, new in replacements:
        content = content.replace(old, new)
        content = re.sub(old, new, content) if old.startswith(r'(?m)') else content
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

# 1. autonomous_daemon.py
replace_in_file(os.path.join(ROOT, "autonomous_daemon.py"), [
    ('from languages import LANGUAGE_CYCLE, get_language, get_next_language, advance_language_index', 'from languages import get_language'),
    ('language: Optional[str] = None, ', ''),
    ('language=args.language', ''),
    ('        if language:\n            target_lang = get_language(language)\n            lang_code = target_lang["code"]\n            cycle_idx = 0', '        target_lang = get_language()\n        lang_code = target_lang["code"]\n        cycle_idx = 0'),
])

# 2. produce_story.py
produce_replacements = [
    ('from languages import LANGUAGE_CYCLE, get_language, get_font_for_language, get_next_language, advance_language_index', 'from languages import get_language, get_font_for_language'),
    ('language: str = "en", ', ''),
    ('language: str = "en"', ''),
    ('self.lang_info = get_language(language)', 'self.lang_info = get_language()'),
    ('--language', '--disabled_language'),
    ('language=args.language,', ''),
    ('args.language = unfinished.get("language", args.language)', ''),
    ('parser.add_argument("--language", type=str, default="en", help="Language code or name (en, hi, pa, fr, es)")', ''),
]
replace_in_file(os.path.join(ROOT, "produce_story.py"), produce_replacements)

# 3. youtube_publisher.py
yt_replacements = [
    ('from languages import get_language', 'from languages import get_language'),
    ('        v["language"] = detect_video_language(v, stories)\n', '        v["language"] = "en"\n'),
]
replace_in_file(os.path.join(ROOT, "youtube_publisher.py"), yt_replacements)

# 4. idea_brain.py
idea_replacements = [
    ('def generate_concepts(self, count: int = 1, ) -> List[StoryConcept]:', 'def generate_concepts(self, count: int = 1) -> List[StoryConcept]:'),
]
replace_in_file(os.path.join(ROOT, "idea_brain.py"), idea_replacements)

# 5. media_synthesizer.py
media_replacements = [
    ('voice=texttospeech.VoiceSelectionParams(\n            language_code=LANGUAGE_CODE,\n            name="en-US-Journey-F"\n        )', 'voice=texttospeech.VoiceSelectionParams(\n            language_code="en-US",\n            name="en-US-Journey-F"\n        )'),
]
replace_in_file(os.path.join(ROOT, "media_synthesizer.py"), media_replacements)
