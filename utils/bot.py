from typing import List

from telegram.ext import CallbackContext


def get_all_args(context: CallbackContext) -> List[str]:
    args = context.args
    match = context.match
    if args is None:
        if match is not None:
            groups = match.groups()
            return list(groups)

    else:
        if len(args) >= 1:
            return args
    return []
