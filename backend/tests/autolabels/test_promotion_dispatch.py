import inspect
from typing import get_args, get_type_hints

from src.autolabels.promotions.dispatch import taskiq_dispatcher
from src.autolabels.promotions.task_names import PROMOTE_LABELS
from src.autolabels.promotions.tasks import promote_labels


def test_the_kicker_matches_the_task_it_sends() -> None:
    params, returns = get_args(get_type_hints(taskiq_dispatcher)["_promote_labels"])
    signature = inspect.signature(promote_labels.original_func)

    assert promote_labels.task_name == PROMOTE_LABELS
    assert list(params) == [parameter.annotation for parameter in signature.parameters.values()]
    assert get_args(returns)[-1] == signature.return_annotation
