"""
This module provides global db models.
"""

from src.model_base import Base as Base

from .auth import models as _auth_models  # noqa: E402, F401
from .autolabels import models as _autolabel_models  # noqa: E402, F401
from .files import models as _file_models  # noqa: E402, F401
from .filters import models as _filter_models  # noqa: E402, F401
from .labels import models as _label_models  # noqa: E402, F401
from .languages import models as _language_models  # noqa: E402, F401
from .memory import models as _memory_models  # noqa: E402, F401
from .memory import shadow_models as _memory_shadow_models  # noqa: E402, F401
from .memory.plugins.conventions import models as _convention_models  # noqa: E402, F401
from .memory.plugins.glossary import models as _glossary_models  # noqa: E402, F401
from .memory.plugins.translations import models as _term_translation_models  # noqa: E402, F401
from .novels import models as _novel_models  # noqa: E402, F401
from .translations import models as _translation_models  # noqa: E402, F401
