export type ClaimType = "authority" | "inference" | "analogy" | "speculation" | "unresolved";

export type ResearchMode =
  | "direct"
  | "fact_similarity"
  | "legal_similarity"
  | "citation"
  | "statutory"
  | "inverse"
  | "adversarial"
  | "precedent_attack"
  | "comparative"
  | "analogy"
  | "novel_area"
  | "historical";

export interface SourceRef {
  document_id: number;
  section_id: number;
  title: string;
  citation_string: string | null;
  locator: string | null;
  extract: string;
  source_url: string | null;
}

export interface Claim {
  text: string;
  claim_type: ClaimType;
  source: SourceRef | null;
  confidence: number;
  verified: boolean;
}

export interface WebResult {
  title: string;
  url: string;
  snippet: string;
}

export interface AdversarialAnalysis {
  strongest_argument_for: Claim;
  strongest_argument_against: Claim;
  weaknesses: Claim[];
  likely_opposing_authorities: Claim[];
  possible_responses: Claim[];
}

export interface InverseResearch {
  inverse_proposition: string;
  authorities_supporting_inverse: Claim[];
  alternative_interpretation: Claim | null;
}

export interface StructuredAnswer {
  question: string;
  short_answer: string;
  jurisdiction: string;
  material_facts: string[];
  issues: string[];
  governing_statutes: Claim[];
  binding_authorities: Claim[];
  persuasive_authorities: Claim[];
  factually_similar_authorities: Claim[];
  legally_similar_authorities: Claim[];
  authorities_supporting: Claim[];
  authorities_against: Claim[];
  distinguishing_authorities: Claim[];
  adversarial_analysis: AdversarialAnalysis;
  inverse_research: InverseResearch;
  comparative_authorities: Claim[];
  novel_or_analogous_authorities: Claim[];
  unresolved_questions: string[];
  research_gaps: string[];
  conclusion: string;
  jurisdiction_coverage_note: string;
  date_coverage_note: string;
  modes_not_yet_researched: ResearchMode[];
  web_verification: WebResult[];
}

export interface ConfigResponse {
  default_model: string;
  available_models: string[];
}

export interface VerificationReport {
  total_authority_claims: number;
  blocked_unverifiable_claims: number;
}

export interface ResearchResponse {
  question_id: number;
  answer_id: number;
  answer: StructuredAnswer;
  verification_report: VerificationReport;
}

export interface ChatResponse {
  reply: string;
  referenced_claims: Claim[];
  web_results: WebResult[];
}

export interface SessionSummary {
  session_id: number;
  preview: string;
  last_active_at: string;
}

export interface ChatHistoryItem {
  role: "user" | "assistant";
  content: string;
  answer_id: number | null;
  web_results: WebResult[] | null;
  answer: StructuredAnswer | null;
}

// The baseline research pass every "standard" send runs — direct + statutory authority
// research plus the adversarial for/against split, reflecting Inverse's core philosophy
// without requiring the user to tick anything.
export const STANDARD_MODES: ResearchMode[] = ["direct", "statutory", "adversarial"];

export const ADVANCED_MODES: { value: ResearchMode; label: string; implemented: boolean }[] = [
  { value: "fact_similarity", label: "Fact Similarity", implemented: true },
  { value: "legal_similarity", label: "Legal Similarity", implemented: true },
  { value: "citation", label: "Citation Research", implemented: true },
  { value: "precedent_attack", label: "Precedent Attack", implemented: true },
  { value: "comparative", label: "Comparative Research", implemented: false },
  { value: "analogy", label: "Analogy Research", implemented: false },
  { value: "novel_area", label: "Novel Area Research", implemented: false },
  { value: "historical", label: "Historical Research", implemented: false },
];

// One chat-thread turn, as rendered client-side. "research" turns carry a full
// StructuredAnswer (from /research); "text" turns are lightweight /chat follow-ups.
export type ThreadMessage =
  | { id: string; role: "user"; content: string }
  | {
      id: string;
      role: "assistant";
      kind: "research";
      answer: StructuredAnswer;
      verificationReport: VerificationReport;
    }
  | {
      id: string;
      role: "assistant";
      kind: "text";
      content: string;
      referencedClaims: Claim[];
      webResults: WebResult[];
    }
  | { id: string; role: "assistant"; kind: "error"; content: string };
