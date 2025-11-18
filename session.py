import dataclasses
import typing as T

@dataclasses.dataclass
class Session:
    """
    Common properties of the current boiling invocation
    """

    key: str
    git_ref: str
    iteration: int
    command: T.List[str]


CURRENT_SESSION = Session("", "HEAD", 0, [])


def ctx() -> Session:
    return CURRENT_SESSION

def new_session(*args):
    global CURRENT_SESSION
    CURRENT_SESSION = Session(*args)
