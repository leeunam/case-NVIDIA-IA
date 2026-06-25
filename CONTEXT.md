# NVIDIA Startup Intelligence

This context defines the business language for evaluating Brazilian startups for NVIDIA Inception outreach. It is a glossary, not an implementation spec.

## Language

**Startup Candidate**:
A company discovered from a public source before the system has enough structured evidence to assess it.
_Avoid_: Lead, prospect, raw startup

**Startup Profile**:
The structured, evidence-backed representation of a startup after public pages have been collected and interpreted.
_Avoid_: Assessment target, analyzed startup, company record

**Evidence**:
A public source excerpt that supports a claim about a startup, technology, gap, recommendation, or briefing claim.
_Avoid_: Source, proof, citation when referring to startup-side evidence

**Citation**:
An official NVIDIA source excerpt used to support a claim about NVIDIA technology, program fit, or recommendation rationale.
_Avoid_: Evidence when referring to NVIDIA-side sources

**AI-Native**:
A classification for a startup where public evidence shows AI is central to the product and there is enough technical depth to treat AI as more than a feature or marketing claim.
_Avoid_: AI-first, deep AI, pure AI

**AI-Enabled**:
A classification for a startup where AI is relevant, but public evidence does not show enough centrality and technical depth for AI-native classification.
_Avoid_: AI startup, light AI

**Wrapper Risk**:
The risk that a startup's AI capability depends mainly on external APIs without evidence of proprietary data, production inference, or meaningful technical defensibility.
_Avoid_: Wrapper startup, fake AI

**Technical Gap**:
A technical need or weakness in the startup's AI stack that NVIDIA technology could plausibly address.
_Avoid_: Opportunity, recommendation, pain point

**Commercial Opportunity**:
A non-technical outreach opportunity, such as Inception fit, partner support, credits, ecosystem access, or go-to-market support.
_Avoid_: Technical gap, go-to-market gap

**Opportunity Signal**:
A preliminary signal from assessment that a startup may merit NVIDIA-related attention, before official NVIDIA knowledge has been retrieved.
_Avoid_: NVIDIA priority, final urgency

**NVIDIA Opportunity Priority**:
The final outreach priority produced after recommendation has matched a startup gap or commercial opportunity to official NVIDIA citations.
_Avoid_: Assessment urgency, opportunity signal

**NVIDIA Knowledge**:
The versioned body of official NVIDIA source material used to retrieve citations for recommendations.
_Avoid_: Curated internal knowledge, generic RAG corpus

**Technical Recommendation**:
A recommendation that maps a technical gap to an NVIDIA technology or technical resource with official NVIDIA citation support.
_Avoid_: Recommendation when the distinction from program or action matters

**Program Recommendation**:
A recommendation that maps a commercial opportunity to an NVIDIA program, such as Inception, with official NVIDIA citation support.
_Avoid_: Technical recommendation, generic Inception pitch

**Next Action**:
The concrete follow-up suggested for a human operator after assessment and recommendations, such as review, founder validation, or outreach preparation.
_Avoid_: Recommendation

**Executive Briefing**:
The final evidence-backed artifact prepared for the NVIDIA Startups & VCs manager to support outreach prioritization and conversation planning.
_Avoid_: Report, deck, summary

**Human Review Briefing**:
A briefing generated when the system cannot safely produce a final recommendation, but has enough context to ask a human to review the startup, evidence, gaps, risks, and open questions.
_Avoid_: Error report, blocked run, empty review

**Human Review**:
A workflow outcome where the system has strategic signal but lacks enough evidence, has unresolved conflict, or would otherwise risk presenting a hypothesis as fact.
_Avoid_: Manual QA, approval
