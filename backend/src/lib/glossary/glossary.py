import json
from typing import Callable
import os
import statistics

from .extractor import *
from .utils import NumpyEncoder

class GlossaryBuilder:
    """Object that builds a glossary given a list of chapters in a dictionary format
        chapter_name : chapter_content
    
    Args:
        extractor: Extractor object to extract named entities from text
        chapters: Raw data for chapters
        chapter_name_to_num:  [Optional] Callable that converts chapter names to numbers
        word_normalizer: [Optional] Callable that normalizes a word for a named entity
    
    Usage:
        Follows a pipeline. load_and_extract -> normalize_words -> flatten -> build_frequency_table -> apply_filters
    """
    def __init__(self, extractor : Extractor, chapters : dict[str, str], chapter_name_to_num : Callable[[str], int] = None, normalizer : Callable[[dict], dict] = (lambda x : x)):
        self.extractor = extractor
        self.chapters = chapters
        self.chapter_name_to_num = chapter_name_to_num
        self.normalizer = normalizer
        
        self.extracted_entities = None
        self.frequency_table = None

        self.flattened_entities = None
        
        self.first_appearances = None
        
        self.chapters_by_num = { chapter_name_to_num(chapter_name) : content for chapter_name, content in self.chapters.items() }
    
    def load_and_extract(self, wordy=False, checkpoint : str=None):
        """Computes extracted_entities in the format
            chapter_number : 
                {
                    'chapter_name' : ...
                    'entities' : [list of named entities in chapter]
                }
            Each entity is in the format
            {
                'entity_group' : ...
                'score' : ...
                'word' : ...
                'start' : ...
                'end' : ...
            }
            No filters or de-duplication applied at this stage. Words are normalized during this step.

        Args:
            wordy: enable/disable log messages
            checkpoint: file to write incomplete data to in case of failure
        """
        if checkpoint and os.path.isfile(checkpoint):
            if wordy:
                print("Loading checkpoint ...")
            try:
                with open(checkpoint, 'r') as file:
                    chap_ent_json = json.load(file)
                    self.extracted_entities = { int(key) : value for key, value in chap_ent_json.items()}
            except Exception as e:
                print(f"Error loading checkpoint: {e}")
                self.extracted_entities = {}
        elif checkpoint:
            print("No existing checkpoint file found, performing full extraction")
            self.extracted_entities = {}
        else:
            self.extracted_entities = {}


        if wordy:
            print("Extracting entities ...")
        
        for index, chapter_name in enumerate(self.chapters):
            if wordy:
                print(f"Processing chapter {chapter_name}")
            try:
                if self.chapter_name_to_num:
                    chapter_num = self.chapter_name_to_num(chapter_name)
                else:
                    chapter_num = index
                if chapter_num in self.extracted_entities:
                    continue
                ents = self.extractor.extract_named_entities(self.chapters[chapter_name])
                self.extracted_entities[chapter_num] = {'chapter_name' : chapter_name, 'entities' : ents}
            except Exception as e:
                print(f"Error processing index {index}, chapter {chapter_name}: {e}")
                if checkpoint:
                    print(f"Dumping data in {checkpoint}")
                    with open(checkpoint, 'w') as file:
                        json.dump(self.extracted_entities, file, cls=NumpyEncoder)
                exit(1)

        if wordy:
            print("Done extracting")
        if checkpoint:
            with open(checkpoint, 'w') as file:
                json.dump(self.extracted_entities, file, cls=NumpyEncoder)
        return self
    
    def normalize_words(self):
        """Normalize all words for all entries by applying the normalizer"""
        for chapter_num in self.extracted_entities:
            normalized_list = [self.normalizer(ent) for ent in self.extracted_entities[chapter_num]['entities']]
            self.extracted_entities[chapter_num]['entities'] = normalized_list
        return self

    def flatten(self):
        """Create a flattened list of entities of the form
            {
                'word' : ...
                'chapter' : ...
                'chapter_name' : ...
                'entity_group' : ...
                'score' : ...
                'start' : ...
                'end' : ...
            }
        """
        self.flattened_entities = [
            {**entity, 'chapter' : chapter_num, 'chapter_name' : self.extracted_entities[chapter_num]['chapter_name']} 
            for chapter_num in self.extracted_entities 
            for entity in self.extracted_entities[chapter_num]['entities']
        ]
        return self

    def build_frequency_table(self):
        """Builds a frequency table in the form
            {
                word : {
                    'total_count' : ...
                    'chapter_count' : ...
                    'avg_score' : ...
                    'std_dev_score' : ...
                    'dirty_count' : ...
                    'clean_avg_score' : ...
                    'clean_std_dev_score' : ...
                }
            }
        """
        aggregate_data = {}
        for ent in self.flattened_entities:
            if ent['word'] not in aggregate_data:
                aggregate_data[ent['word']] = {
                    'scores' : [ent['score']],
                    'chapters' : {ent['chapter']}, 
                    'entity_groups' : [ent['entity_group']],
                }
                if 'dirty' in ent and ent['dirty']:
                    aggregate_data[ent['word']]['clean_scores'] = []
                else:
                    aggregate_data[ent['word']]['clean_scores'] = [ent['score']]
            else:
                aggregate_data[ent['word']]['scores'].append(ent['score'])
                aggregate_data[ent['word']]['chapters'].add(ent['chapter'])
                aggregate_data[ent['word']]['entity_groups'].append(ent['entity_group'])
                if 'dirty' not in ent or not ent['dirty']:
                    aggregate_data[ent['word']]['clean_scores'].append(ent['score'])

        self.frequency_table = {
            word : {
                'total_count' : len(aggregate_data[word]['scores']),
                'chapter_count' : len(aggregate_data[word]['chapters']),
                'avg_score' : statistics.fmean(aggregate_data[word]['scores']),
                'std_dev_score' : statistics.stdev(aggregate_data[word]['scores']) if len(aggregate_data[word]['scores']) > 1 else 0.0,
                'dirty_count' : len(aggregate_data[word]['scores']) - len(aggregate_data[word]['clean_scores']),
                'clean_avg_score' : statistics.fmean(aggregate_data[word]['clean_scores']) if len(aggregate_data[word]['clean_scores']) > 0 else 0.0,
                'clean_std_dev_score' : statistics.stdev(aggregate_data[word]['clean_scores']) if len(aggregate_data[word]['clean_scores']) > 1 else 0.0
            }
            for word in aggregate_data
        }
        return self
    
    def apply_filter(self, filter_func : Callable, **kwargs):
        """Filter out entries from flattened data
        
        Args:
            filter_func: filter function that takes parameters flattened_entities, freq_table, **kwargs and returns a filtered list of entries from flattened_entities
        """
        self.flattened_entities = filter_func(self.flattened_entities, **kwargs)
        return self
    
    def build_first_appearances(self):
        """Construct a list
            {
                chapter_num : [list of entity names]
            }
            from the flattened list where the list contains only entities that have not been filtered out and first appear in the corresponding chapter
        """
        chapter_appearances = {}
        for ent in self.flattened_entities:
            if ent['chapter'] not in chapter_appearances:
                chapter_appearances[ent['chapter']] = {
                    'entities' : [ent['word']],
                    'chapter_name' : ent['chapter_name']
                }
            elif ent['word'] not in chapter_appearances[ent['chapter']]:
                chapter_appearances[ent['chapter']]['entities'].append(ent['word'])
        
        seen = set()
        sorted_keys = sorted(list(chapter_appearances.keys()))
        self.first_appearances = {}
        for chapter_num in sorted_keys:
            for word in chapter_appearances[chapter_num]['entities']:
                if word not in seen:
                    if chapter_num not in self.first_appearances:
                        self.first_appearances[chapter_num] = {
                            'chapter_name' : chapter_appearances[chapter_num]['chapter_name'],
                            'entities' : []
                        }
                    self.first_appearances[chapter_num]['entities'].append(word)
                    seen.add(word)