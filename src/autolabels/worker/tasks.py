from .inference import *

model_cache : Dict[str, NERModel] = {}

def get_ner_model(model_name : str) -> NERModel:
    if model_name in model_cache:
        return model_cache[model_name]
    
    if model_name == 'cluener':
        model_cache['cluener'] = Cluener().model
        return model_cache['cluener']

    raise ValueError(f"Model {model_name} not found in registry.")