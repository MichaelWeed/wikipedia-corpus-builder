PROMPT_VERSION = "intent-v1"

FACET_SYSTEM_PROMPT = (
    "You are a domain taxonomy expert. Generate conceptual facets (topical subfields "
    "or adjacent topics to exclude), NOT Wikipedia category names. Respond only in JSON."
)

BOUNDARY_SYSTEM_PROMPT = (
    "You are a domain taxonomy expert. Generate up to 8 boundary disambiguation questions "
    "to help the user refine domain scope. Respond only in JSON."
)
