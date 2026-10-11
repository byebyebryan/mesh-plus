"""Small installed fixture corpus; owners may also supply independent cases."""

import copy
import json
import re
from dataclasses import dataclass
from importlib.resources import files


@dataclass(frozen=True)
class ProfileCase:
    case_id: str
    domain: str
    response: dict
    native: dict
    states: dict
    identities: list
    selections: list

    def __post_init__(self):
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,127}", self.case_id) or self.domain not in {"tmux", "agent"}:
            raise ValueError("conformance_case")
        if not self.selections or not all(type(s["now_ms"]) is int and type(s["rows"]) is list for s in self.selections):
            raise ValueError("conformance_oracle")


def corpus_bytes():
    return files(__package__).joinpath("corpus.json").read_bytes()


def profile_cases(domain):
    if domain not in {"tmux", "agent"}:
        raise ValueError("conformance_domain")
    data = json.loads(corpus_bytes())
    return tuple(ProfileCase(**copy.deepcopy(case)) for case in data["cases"] if case["domain"] == domain)
