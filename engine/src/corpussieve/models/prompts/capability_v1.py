PROMPT_VERSION = "cap-v1"

SYS = "You are a category classification assistant. Respond only in JSON adhering to the schema."

CAPABILITY_TEST_CASES = [
    {
        "system": SYS,
        "prompt": (
            "Domain: Video Games. Parent: Category:Video games. "
            "Candidate: Category:Action games. Should this subcategory be included?"
        ),
        "expected": "include",
    },
    {
        "system": SYS,
        "prompt": (
            "Domain: Video Games. Parent: Category:Video games. "
            "Candidate: Category:Tabletop board games. Should this subcategory be included?"
        ),
        "expected": "exclude",
    },
    {
        "system": SYS,
        "prompt": (
            "Domain: Video Games. Parent: Category:Video games. "
            "Candidate: Category:Platform games. Should this subcategory be included?"
        ),
        "expected": "include",
    },
]
