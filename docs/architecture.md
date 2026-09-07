# Inverse — Adversarial Legal Research Platform: Architecture & Delivery Plan

## Context

The goal is an AI-native legal research platform ("Inverse") whose defining feature is *adversarial* research: for every proposition, it must surface not just supporting authority but everything capable of defeating it (opposition, distinctions, limitations, reversals, inverse propositions, comparative/analogous doctrine). This is explicitly not a chatbot — it is a research engine (retrieval, ranking, citation graph, agent orchestration) with a workspace UI on top. Per the spec, no code is written until this architecture is approved. Decisions locked in with the user: **US (federal + state)** as the MVP jurisdiction, **Python (backend/agents/retrieval) + TypeScript/Next.js (frontend)** as the stack, and **OpenAI** as the sole LLM + embedding provider for MVP.

## Ambiguities identified (and how this plan resolves them)

1. **"Comparative jurisdictions" scope** — spec implies multi-jurisdiction from day one, but MVP is US-only. Resolved: comparative/analogous-jurisdiction research is a Phase 2 capability; MVP's Comparative panel is present in the UI/schema but explicitly labeled "not yet researched" rather than faking results.
2. **Crawling legality** (§18 warns against assuming any site can be scraped) — resolved by using only free/official APIs and bulk data (CourtListener, GovInfo, Congress.gov) plus user uploads for MVP; no general-purpose web crawler is built until a licensed-source strategy exists.
3. **"Good law" / treatment signals** (Shepard's/KeyCite are commercial, proprietary products) — Inverse cannot replicate them exactly. Resolved: build an approximate treatment/citation graph from open citation data (courts-db/eyecite) and **explicitly disclose it as an approximation**, not a Shepardize-equivalent, per the safety requirements in §19.
4. **Fact vs Legal similarity as separate systems** (§6) — resolved architecturally: two independent scoring pipelines (structured-fact-feature similarity vs legal-issue/doctrine similarity) that are never averaged into one number, only ever shown side-by-side.
5. **Agent granularity** (§4 lists 15 agents) — building all 15 as independently-prompted LLM agents from day one is over-engineering for MVP and increases hallucination surface area. Resolved: MVP consolidates into ~9 agents behind the same orchestration contract; the remaining roles (Comparative Law, Analogy, dedicated Fact/Legal-Similarity split, Historical) are added in Phase 2 without changing the orchestration model.
6. **What "structured answer" means for correctness** (§5, §15, §19) — the single hardest requirement is "never present inference as a holding" and "avoid fabricated authorities." Resolved via a hard architectural constraint: **agents may never emit a citation that was not returned by a retrieval tool call in that session**, and a deterministic Source Verification gate blocks any answer section whose claims don't resolve to an actual retrieved paragraph before it reaches the user.
7. **Deployment/licensing budget** — not specified. Assumption: MVP runs on free/official data sources only; commercial licensed APIs (Westlaw/Lexis/Fastcase/vLex partnerships) are a Phase 2+ business decision, not an MVP engineering dependency.

---

## 1. High-level architecture

```
                         ┌─────────────────────────┐
                         │   Next.js/TS Workspace   │
                         │  (research UI, §16)      │
                         └───────────┬─────────────┘
                                     │ REST/SSE (streaming agent progress)
                         ┌───────────▼─────────────┐
                         │   API Gateway (FastAPI)  │
                         └───────────┬─────────────┘
                                     │
                 ┌───────────────────▼────────────────────┐
                 │        Orchestrator (LangGraph)         │
                 │  mode router → agent subgraph per mode  │
                 └──┬───────┬────────┬─────────┬──────────┘
                    │       │        │         │
         ┌──────────▼┐ ┌────▼────┐ ┌─▼───────┐ ┌▼─────────────┐
         │ Issue      │ │ Statute │ │ Case     │ │ Inverse /    │
         │ Decomp.    │ │ Research│ │ Research │ │ Adversarial /│
         │ Agent      │ │ Agent   │ │ Agent(s) │ │ Precedent-   │
         └──────────┬─┘ └────┬────┘ └─┬────────┘ │ Attack Agent │
                    │        │        │           └──────┬───────┘
                    └────────┴───┬────┴──────────────────┘
                                 │  (all agents call the same toolkit —
                                 │   never free-text; every result is
                                 │   a structured, source-pointed object)
                    ┌────────────▼─────────────┐
                    │   Retrieval Toolkit API   │
                    │  keyword + vector + graph │
                    │  + metadata + reranking   │
                    └────────────┬──────────────┘
                    ┌────────────▼─────────────┐        ┌───────────────────┐
                    │  OpenSearch (hybrid: BM25 │        │  Postgres          │
                    │  + kNN vector search,     │◄──────►│  (documents,       │
                    │  filtered by metadata)    │        │  sections, courts, │
                    └────────────────────────────┘        │  citations/graph,  │
                                                            │  research sessions)│
                                                            └─────────┬──────────┘
                                                                      │
                    ┌─────────────────────────────────────────────────▼──┐
                    │              Synthesis Agent                       │
                    │  assembles the §15 structured answer ONLY from     │
                    │  claims produced upstream (no free invention)      │
                    └─────────────────────────┬───────────────────────────┘
                                              │
                    ┌─────────────────────────▼───────────────────────────┐
                    │        Source Verification Agent (hard gate)        │
                    │  every citation/claim must resolve to a retrieved   │
                    │  paragraph or the section is blocked/flagged        │
                    └───────────────────────────────────────────────────────┘
```

Everything downstream of "Retrieval Toolkit" is deterministic Python services; everything upstream of it (issue decomposition, argument construction, synthesis) is LLM-driven but constrained to operate only on tool outputs (see §12 deterministic-vs-agentic table below).

---

## 2. Database / schema design (Postgres, primary source of truth)

Core tables (simplified — FKs omitted for brevity):

- `jurisdictions(id, name, level[federal|state], parent_jurisdiction_id)`
- `courts(id, jurisdiction_id, name, level, parent_court_id, binding_scope)` — sourced from Free Law Project's **courts-db**
- `documents(id, doc_type[case|statute|regulation|secondary|discovery], jurisdiction_id, court_id, title, citation_string, date_decided_or_enacted, source_type[primary|quasi_primary|secondary|discovery], source_url, source_provider, license_note, ingestion_status, last_verified_at)`
- `document_sections(id, document_id, section_type[paragraph|holding|headnote|statute_section|footnote], sequence, text, locator (page/¶/section no.), embedding_ref)`
- `citations(id, citing_document_id, citing_section_id, cited_document_id, cited_section_id, citation_string_raw, treatment_type[cites|follows|distinguishes|approves|criticises|overrules|departs_from|interprets|applies|narrows|expands], confidence, extracted_by[rule|llm], extracted_at)` — this table *is* the authority graph edge set for MVP (recursive CTEs answer graph questions; Neo4j/Neptune is a Phase 2 migration if multi-hop query latency demands it)
- `statute_versions(id, statute_id, section_no, text, effective_start, effective_end, amendment_of)`
- `legal_entities(id, entity_type[judge|party|court], name, metadata)` + `document_entities` join table
- `propositions(id, text_summary, area_of_law)` + `proposition_documents(proposition_id, document_id, relation[support|oppose|distinguish|limit|reverse], confidence)`
- `research_sessions`, `research_questions`, `research_answers` (JSON matching the §15 structure), `claims(id, answer_id, section_name, claim_text, claim_type[authority|inference|analogy|speculation|unresolved], source_document_id, source_section_id, extract_text, confidence)` — every row in `claims` is what the Source Verification gate checks
- `folders`, `saved_research`, `users`, `orgs`

Vector embeddings are stored in OpenSearch (see §3) keyed by `document_sections.embedding_ref`, with jurisdiction/court/date/source_type mirrored as filterable fields — never a Postgres-only or OpenSearch-only source of truth for text (Postgres holds canonical text; OpenSearch holds the searchable/embedded copy).

---

## 3. Retrieval architecture (hybrid, per §9)

Single engine to minimize MVP ops burden: **OpenSearch** with a `knn_vector` field alongside BM25 text fields — gives keyword search, semantic search, and metadata filtering in one query (`bool` query combining `must` metadata filters + a hybrid of BM25 and kNN scores).

Pipeline per retrieval call:
1. **Metadata filter** (jurisdiction, court, date range, source type) — always applied first, deterministically, from the request/agent parameters, never inferred by the LLM alone.
2. **Hybrid search**: BM25 keyword score + kNN cosine similarity (OpenAI `text-embedding-3-large`) combined via reciprocal rank fusion.
3. **Citation graph expansion** (optional, mode-dependent): pull direct/indirect citing & cited documents from Postgres `citations` table for the top-K hits.
4. **Legal reranking** (deterministic scoring service, not vector-only, satisfying §9's explicit requirement): weighted formula over — jurisdiction match, court hierarchy/binding vs persuasive, recency, citation treatment signal (e.g., overruled/criticised depresses score, followed/approved boosts it), factual similarity score, legal similarity score, statutory relevance, source reliability tier. Weights are mode-dependent (e.g., Fact Similarity mode weights factual score highest; Legal Similarity mode weights doctrine/test match highest).
5. Results returned as structured objects (doc id, section id, locator, extract, all component scores) — never raw prose — so every downstream agent claim can carry an exact provenance pointer per §8.

**Fact similarity vs legal similarity (§6)** are two independent scoring functions, not two weights on one score:
- *Fact similarity*: an LLM extraction step turns both the query facts and each candidate case into a structured fact schema (parties, relationship, conduct, timeline, transaction, industry, harm, intent, procedural posture, remedy), then a deterministic similarity function (structured-field match + embedding similarity of the fact narrative) produces the % and explanation.
- *Legal similarity*: separately embeds/matches on issue, doctrine, statutory provision, test, ratio, interpretive methodology, producing its own % and explanation.
Both scores are always displayed together, never collapsed (per the explicit example in §6).

---

## 4. Agent architecture & orchestration

Orchestration framework: **LangGraph** (Python) — the Orchestrator is a graph, not a chat loop, so mode routing and multi-agent fan-out/fan-in is inspectable and testable rather than emergent.

MVP agent roster (consolidated from the spec's 15 into 9 without losing capability — the remaining 6 roles are added in Phase 2 as the graph is extended, not redesigned):

| Agent | Responsibility |
|---|---|
| Orchestrator | Classifies question, selects jurisdiction/mode(s), fans out to the subgraph(s) needed, fans in results |
| Issue Decomposition | Breaks the question into discrete legal issues + identifies jurisdiction/court hierarchy |
| Statute Research | Finds relevant statutes/sections/definitions/amendments + judicial interpretation of them |
| Case Research (parametrized: direct / fact-similar / legal-similar / citation) | Calls the Retrieval Toolkit in each of these sub-modes; Phase 2 splits this into dedicated Fact-Similarity and Legal-Similarity agents once prompt complexity warrants it |
| Precedent/Citation Agent | Builds the citation-graph view for a given authority: who cites it, who distinguishes/limits/overrules it |
| Inverse Research | Generates the inverse proposition and re-runs the retrieval pipeline against it |
| Adversarial / Precedent-Attack Agent | Produces the "opposing counsel" analysis (§13) and precedent-attack analysis (§12) — merged because both are "construct the strongest case against X" with different inputs |
| Synthesis | Assembles the §15 structured answer **only** from claims already produced by other agents — cannot introduce new authorities |
| Source Verification | Deterministic + LLM hybrid gate: walks every claim, confirms it resolves to a retrieved `document_sections` row with matching extract text; blocks/flags anything that doesn't |

**Grounding constraint (critical for §19 safety):** no agent is permitted to name a case, statute, or quotation that did not come back from a Retrieval Toolkit call in that session. This is enforced structurally — agent prompts only ever see retrieved objects to reason over, and output schemas require a `source_section_id` on every citation, which Source Verification then checks against Postgres.

---

## 5. Ingestion / source architecture (§18, US-only MVP)

```
SOURCE → fetch (API/bulk, not scraping) → jurisdiction classification (courts-db)
  → source classification (primary/quasi-primary/secondary/discovery per §7)
  → parsing → section/paragraph extraction → citation extraction (eyecite)
  → legal entity extraction → metadata enrichment → embeddings (OpenAI) → OpenSearch index
```

MVP sources (all free/official, no general crawler needed — resolves the §18 licensing concern directly):
- **CourtListener / Free Law Project** — federal + a wide swath of state case law via REST API + bulk data; also provides **eyecite** (citation extraction), **courts-db** (court hierarchy/jurisdiction metadata), **reporters-db** — these are open-source libraries built for exactly this pipeline and should be reused, not reimplemented.
- **GovInfo API** — US Code, CFR, Federal Register, Statutes at Large (official federal primary sources).
- **Congress.gov API** — bill status/legislative history (for statutory research provenance).
- **User uploads** — PDF/DOCX ingestion through the same parsing/citation/embedding pipeline, tagged `source_provider=user_upload`.
- State statutes: start with 2–3 states with clean official portals/APIs (evaluate per-state ToS before adding each one) rather than all 50 at once.

Deferred to Phase 2: general web crawler for secondary/discovery sources, licensed commercial data partnerships (Westlaw/Lexis/Fastcase/vLex) for deeper state coverage and professional-grade treatment signals.

Every ingested document retains: `source_provider`, `source_url`, `license_note`, `ingestion_status`, `last_verified_at` — required for the §19 "flag date/currency limitations" and "identify jurisdictional limitations" safety requirements.

---

## 6. UI/UX (§16)

Next.js/TypeScript workspace, not a chat window:
- **Left rail**: jurisdiction selector, court selector, date range, source-type filters, research mode selector.
- **Center**: legal question editor → streamed structured answer (collapsible sections matching §15 exactly), each proposition inline-tagged `[authority]/[inference]/[analogy]/[speculation]/[unresolved]` per §5.
- **Right rail**: research map (question → issue → authority → paragraph → proposition → counterargument → inverse, per §16's navigation requirement) + provenance drawer (claim → source → document → paragraph → extract → citation, per §8) + authority graph view (Postgres-backed graph rendered client-side for MVP; a dedicated graph viz library, not a full graph-DB round trip, is sufficient at MVP scale).
- **Panels**: Argument-For / Argument-Against, Inverse Research, (Comparative/Analogy panels present but show "not yet researched — Phase 2" rather than fabricating content).
- **Saved research folders** sidebar, tied to `folders`/`saved_research` tables.

---

## 7. MVP definition

**In scope:** US federal + 2–3 pilot states; modes = Direct Research, Statutory Research, Fact Similarity, Legal Similarity, Citation Research, Inverse Search, Adversarial Research, Precedent Attack; the 9-agent roster above; full §15 structured answer format (with explicit "not researched" placeholders for out-of-scope modes rather than fake content); full source provenance UI; Source Verification hard gate; saved research folders.

**Explicitly out of scope for MVP:** Comparative jurisdiction research, Analogy-across-areas-of-law research, Novel-law progressive broadening (§11), Historical evolution tracing, licensed commercial data, dedicated graph database, general web crawler.

## 8. Phase 2 and beyond

Add Comparative Law Agent + Analogy Agent + Historical Research Agent; implement §11's progressive-broadening novel-law search strategy; split Case Research into dedicated Fact-Similarity/Legal-Similarity agents; migrate authority graph to Neo4j/Neptune if multi-hop "how has this evolved" queries outgrow Postgres CTEs; evaluate a legal-domain cross-encoder reranker on top of the deterministic scorer; pursue licensed data partnerships for deeper state/federal coverage and professional treatment signals; expand jurisdiction coverage; add team/org collaboration on saved research.

---

## 9. Legal research accuracy risks (§10 of the dev-approach steps)

- **Fabricated citations/quotes** — mitigated structurally by the grounding constraint + Source Verification gate (§4), not just prompting.
- **Stale or wrong "good law" status** — Inverse's citation-graph treatment signals are an open-data approximation of Shepard's/KeyCite, not equivalent; must be labeled as such in the UI, with `last_verified_at` shown.
- **Jurisdiction bleed** — persuasive authority from another state/circuit must never render as binding; enforced by the deterministic ranking service, not the LLM's judgment alone.
- **Incomplete corpus** — MVP covers federal + a few states only; every answer must disclose jurisdiction/date coverage limitations (§19 requirement), generated deterministically from what was actually queried, not asserted by the LLM.
- **Citation-treatment mislabeling** (e.g., LLM misclassifying "distinguishes" vs "follows") — needs a sampled human-QA loop before trusting it as a ranking signal at scale.
- **Embedding domain mismatch** — general-purpose OpenAI embeddings may underperform on legal-semantic nuance; flag as an evaluation task (build a small gold-standard fact/legal-similarity eval set early) rather than assume it works.
- **Unauthorized-practice-of-law optics** — product must position clearly as a research tool for professionals, not legal advice; disclaimers baked into the structured answer output, not just marketing copy.

---

## 10. External data/API requirements (§11)

CourtListener API + bulk data (registration, free); Free Law Project OSS libraries — `eyecite`, `courts-db`, `reporters-db`; GovInfo API (free, official); Congress.gov API (free); OpenAI API (chat + `text-embedding-3-large`, per user's chosen provider); OpenSearch (self-hosted or managed, e.g. AWS OpenSearch Service); Postgres (with standard extensions — pgvector is *not* required if OpenSearch owns vector search, avoiding a split-brain vector store). Phase 2+: evaluate Westlaw/Lexis/Fastcase/vLex/CaseText-style licensed APIs for coverage and Shepard's/KeyCite-equivalent signals.

## 11. Deterministic vs. agentic (§12)

**Deterministic:** citation extraction (eyecite), court hierarchy/binding-persuasive determination (courts-db + rules), source-type classification, authority ranking score computation, provenance chain linking, fact/legal similarity *scoring functions* (given structured features), jurisdiction/date coverage disclosure text, the Source Verification resolution check itself.

**Agentic (LLM):** issue decomposition, per-mode query formulation, structured fact/legal-feature *extraction* from raw text (feeds the deterministic scorer), interpreting retrieved authorities into claims, adversarial/inverse argument construction, citation-treatment *classification* (cites vs. distinguishes vs. overrules — agentic now, candidate for a trained classifier later), final answer synthesis (constrained to prior claims only).

## 12. Implementation roadmap

0. **Infra & schema** — Postgres schema above, OpenSearch cluster, repo scaffold (`inverse-search/` with `apps/`, `agents/`, `ingestion/`, `retrieval/`, `ranking/`, `knowledge/`, `research/`, `evaluation/` per §17).
1. **Ingestion MVP** — CourtListener + GovInfo pipelines, eyecite/courts-db integration, user-upload path, embeddings + OpenSearch indexing.
2. **Retrieval layer** — hybrid search + deterministic legal reranking service; fact-similarity/legal-similarity scoring functions; small gold-standard eval set.
3. **Agent orchestration MVP** — LangGraph orchestrator + the 9 agents for the in-scope modes, all calling the Retrieval Toolkit (no free-text tool calls).
4. **Synthesis + Source Verification gate** — §15 structured-answer assembly with the hard grounding check before any answer reaches the UI.
5. **Workspace UI** — Next.js app: filters, mode selector, structured answer view, provenance drawer, basic authority graph view, saved folders.
6. **Evaluation & hardening** — expand the gold-standard QA set, measure citation precision/recall and fact/legal-similarity accuracy, tune ranking weights.
7. **Beta** — internal dogfooding on real research questions before wider release.

---

### Verification approach once implementation starts
Each phase gets its own automated tests (ingestion: known-document round-trip + citation-extraction accuracy against a hand-labeled sample; retrieval: precision@k on the gold-standard eval set; agents: golden-transcript regression tests with mocked retrieval results; Source Verification: adversarial tests that inject an ungrounded citation and confirm it's blocked). UI is manually verified end-to-end against real CourtListener/GovInfo data before beta.
