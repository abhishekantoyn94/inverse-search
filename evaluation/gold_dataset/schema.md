# Gold-standard evaluation set format

Each file in this directory is one hand-labeled test case:

```json
{
  "question": "...",
  "jurisdiction": "...",
  "expected_binding_authorities": ["citation_string", "..."],
  "expected_factually_similar": [{"citation_string": "...", "min_score": 0.7}],
  "expected_legally_similar": [{"citation_string": "...", "min_score": 0.7}],
  "known_negative_treatment": [{"citation_string": "...", "treatment_type": "overrules"}]
}
```

Used by `evaluation/run_eval.py` to compute citation precision/recall against
`run_research`'s output, and to sanity-check that fact/legal similarity scores land
within the labeled range. Start this set small (10-20 cases spanning the pilot
jurisdictions) and grow it as real research sessions surface disagreements — see
docs/architecture.md §9/§12 for why this exists (embedding-domain mismatch and
citation-treatment mislabeling are the two accuracy risks it's meant to catch early).
