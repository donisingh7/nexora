from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid5

_NAMESPACE_PREFIX = "nexora-eval-fixture"


def _stable_id(name: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"{_NAMESPACE_PREFIX}:{name}")


WORKSPACE_ID = _stable_id("workspace")


@dataclass(frozen=True)
class EvalDocument:
    key: str
    filename: str
    text: str

    @property
    def chunk_id(self) -> UUID:
        return _stable_id(f"chunk:{self.key}")

    @property
    def document_id(self) -> UUID:
        return _stable_id(f"document:{self.key}")


@dataclass(frozen=True)
class EvalCase:
    query: str
    relevant_keys: frozenset[str]

    def relevant_ids(self) -> set[UUID]:
        return {_stable_id(f"chunk:{key}") for key in self.relevant_keys}


# Small, synthetic, generic policy corpus. Not derived from any real organization's
# documents - written specifically as a deterministic local evaluation fixture so
# retrieval quality can be measured without external data or credentials.
FIXTURE_DOCUMENTS: list[EvalDocument] = [
    EvalDocument(
        "vacation",
        "vacation-policy.md",
        "Employees accrue vacation days each month and may carry over up to five "
        "unused days into the next calendar year.",
    ),
    EvalDocument(
        "expense",
        "expense-policy.md",
        "Travel expense reports must be submitted within thirty days of the trip "
        "with itemized receipts attached.",
    ),
    EvalDocument(
        "security",
        "security-policy.md",
        "All laptops must have full disk encryption enabled and screens must lock "
        "automatically after five minutes of inactivity.",
    ),
    EvalDocument(
        "onboarding",
        "onboarding-guide.md",
        "New hires complete orientation during their first week, including "
        "benefits enrollment and equipment setup.",
    ),
    EvalDocument(
        "remote",
        "remote-work-policy.md",
        "Remote employees are expected to be reachable during core hours and to "
        "join the weekly team video sync.",
    ),
]

FIXTURE_CASES: list[EvalCase] = [
    EvalCase("How many vacation days carry over to next year?", frozenset({"vacation"})),
    EvalCase("When are travel expense reports due?", frozenset({"expense"})),
    EvalCase("What is the laptop encryption policy?", frozenset({"security"})),
    EvalCase("What happens during a new hire's first week?", frozenset({"onboarding"})),
    EvalCase("Do remote employees need to join a weekly sync?", frozenset({"remote"})),
]
