def filter_by_score(flattened : list[dict], min_score: float = 0.5, **kwargs):
    """Filters entity of the form
        {
            'entity_group' : ...
            'score' : ...
            'word' : ...
            'start' : ...
            'end' : ...
        }
        by minimum score
    
    Args:
        flattened: flattened list of entities
        min_score: minimum score of entities to include
    """
    return [entity for entity in flattened if entity['score'] >= min_score]

def filter_by_chapter_frequency(flattened : list[dict], freq_table : dict, min_chapter_freq : int = 2, **kwargs):
    """Filters out entities that appear in less than min_chapter_freq chapters"""
    return [entity for entity in flattened if freq_table[entity['word']]['chapter_count'] >= min_chapter_freq]

def filter_by_word_length(flattened : list[dict], min_length : int = 2, **kwargs):
    """Filters out entities whose names are less than min_length"""
    return [entity for entity in flattened if len(entity['word']) > min_length]


def merge_adjacent_entities(
    entities : list[dict], 
    chapters_by_num : dict, 
    gap_tolerance : int = 1, 
    separators : set | None = None,
    length_checks : dict | None = None,
    wordy : bool=False, 
    **kwargs
) -> list[dict]:
    """
    Merges adjacent entities by looking up text from a chapter dictionary.

    Args:
        entities: A list of entity dictionaries
        chapters_by_num: A dictionary mapping {chapter_num: chapter_content}
        gap_tolerance: Max characters between entities to merge them
        separators: List of strings to blacklist from being between words when merging
        length_checks: A dict of the form { entity_group : max_length } that prevents two words of that category from being merged if the merged string is longer than max_length
    """
    if not entities:
        return []
    
    if not separators:
        separators = set()
    
    if not length_checks:
        length_checks = {}

    sorted_entities = sorted(entities, key=lambda x: (x['chapter'], x['start']))

    merged_entities = []
    current_merge = sorted_entities[0].copy()

    for next_entity in sorted_entities[1:]:
        ent_group = current_merge['entity_group']
        if (next_entity['chapter'] != current_merge['chapter'] or
            next_entity['entity_group'] != ent_group):
            merged_entities.append(current_merge)
            current_merge = next_entity.copy()
            continue
        
        gap = next_entity['start'] - current_merge['end']
        
        if gap < 0 or gap > gap_tolerance:
            merged_entities.append(current_merge)
            current_merge = next_entity.copy()
            continue

        # Merge the entities
        chapter_num = current_merge['chapter']
        chapter_text = chapters_by_num.get(chapter_num)

        if not chapter_text:
            merged_entities.append(current_merge)
            current_merge = next_entity.copy()
            continue
        merged_word = chapter_text[current_merge['start']:next_entity['end']]
        gap_text = chapter_text[current_merge['end']:next_entity['start']]
        if ent_group in length_checks and len(merged_word) > length_checks[ent_group]:
            merged_entities.append(current_merge)
            current_merge = next_entity.copy()
            continue

        if any(char in separators for char in gap_text):
            merged_entities.append(current_merge)
            current_merge = next_entity.copy()
            continue
        
        # Passed all checks
        if wordy:
            print(f"performing merge on\n{current_merge}\n{next_entity}")
        current_merge['word'] = merged_word
        current_merge['end'] = next_entity['end']
        current_merge['score'] = (current_merge['score'] + next_entity['score']) / 2
        current_merge['dirty'] = True
        if wordy:
            print(f"resulting merge\n{current_merge}")
        merged_entities.append(current_merge)
    
    return merged_entities

def filter_substrings(flattened : list[dict], chapters_by_num : dict, wordy : bool=False):
    """Given a flattened list of entities, replace the entities that appear as a substring of another entity in the list in the text by an entity that contains it"""
    words = {entity['word'] for entity in flattened}
    containing = { word : [big_word for big_word in words if word in big_word and word != big_word] for word in words} # can be made more efficient

    filtered = []

    for entity in flattened:
        chapter = chapters_by_num[entity['chapter']]
        superstrings = containing[entity['word']]
        if not superstrings:
            filtered.append(entity.copy())
            continue

        half_wnd_size = max([len(big_word) for big_word in superstrings])
        sample_start = max(0, entity['start'] - half_wnd_size)
        sample_end = min(len(chapter), entity['start'] + half_wnd_size)
        sample = chapter[sample_start:sample_end]

        relative_entity_start = entity['start'] - sample_start
        relative_entity_end = entity['end'] - sample_start
        # sample looks like [... | ...]
        #                       word
        #                      starts
        #                       here
        # index is half_wnd_size
        found = False
        for big_word in superstrings:
            start_idx = 0
            found_idx = sample.find(big_word, start_idx)
            # find instances of big_word in sample until either no more found or big_word encapsulates the position of entity
            while(found_idx > -1):
                if found_idx <= relative_entity_start and found_idx + len(big_word) > relative_entity_end:
                    found = True
                    break
                found_idx = sample.find(big_word, found_idx + 1)
            if found:
                new_ent = entity.copy()
                new_ent['word'] = big_word
                new_ent['start'] = sample_start + found_idx
                new_ent['end'] = new_ent['start'] + len(big_word)
                if wordy:
                    print(f"replacing entity {entity}\nby {new_ent}")
                break
        if not found:
            new_ent = entity.copy()
        filtered.append(new_ent)
    return filtered