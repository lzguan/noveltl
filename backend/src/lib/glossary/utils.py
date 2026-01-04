from pathlib import Path
import glob
import json
import numpy as np
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return super(NumpyEncoder).default(obj)

def remove_space(entity : dict) -> dict:
    """Remove all spaces in word and strip"""
    new_entity = entity.copy()
    original_word = new_entity['word']
    new_word = original_word.replace(' ', '')
    new_entity['word'] = new_word
    return new_entity

def smart_normalizer(entity: dict) -> dict:
    """
    Strips surrounding punctuation/spaces from an entity's word, removes all
    internal whitespace, and updates its start/end coordinates to match.
    """
    # Create a copy to work with, preserving the original
    new_entity = entity.copy()
    original_word = new_entity['word']

    # 1. Define the comprehensive set of characters to strip from the outside.
    punctuation_to_strip = "·-—”“’‘《》【】…().#&_ "
    
    # 2. Strip the surrounding punctuation.
    stripped_word = original_word.strip(punctuation_to_strip)
    
    # 3. Remove all internal whitespace from the result.
    # e.g., "隗 辛" becomes "隗辛"
    cleaned_word = "".join(stripped_word.split())

    # If no change was made after all cleaning, return the original entity.
    if original_word == cleaned_word:
        return new_entity
        
    # 4. If the word changed, find the new start position.
    # This finds the starting index of the first real character of the cleaned word.
    start_diff = original_word.find(cleaned_word[0]) if cleaned_word else 0

    # 5. Update the entity with the cleaned word and corrected coordinates.
    new_entity['start'] = entity['start'] + start_diff
    new_entity['end'] = new_entity['start'] + len(cleaned_word)
    new_entity['word'] = cleaned_word
    
    return new_entity


def convert_chapter_underscore_num(chapter_name : str) -> int:
    """Converts a chapter name of the form chapter_[chapter_num].txt to chapter_num"""
    return int(chapter_name[8:-4])

def load_chapters(path : str) -> dict[str, str]:
    """Loads all chapters matching path into a dictionary
        chapter_name : chapter_content

    Args:
        path: glob pattern for chapters
    """
    chapters = {}
    file_paths = glob.glob(path)
    for file_path in file_paths:
        with open(file_path, 'r', encoding='utf-8') as file:
            p = Path(file_path)
            content = file.read()
            chapter_name = p.name
            chapters[chapter_name] = content
    return chapters