# Phase 1 — Workstream Documentation — Ahmed Mahmoud Alkhoori

**Focus:** AI Features, Matching, and Reporting

**Project:** KU ResourceSavers — Intelligent, AI-Powered Circular Campus Resource Exchange and Asset Life Cycle Management System  
**Course:** COSC 336 — Introduction to Software Engineering  
**Source documents:** `Phase 1.docx` and `Phase 2.docx` already present in the shared repository.  
**Document purpose:** Standalone explanation of this allocated project workstream using the team's completed phase reports. This document describes planned requirements and feasibility, not completed implementation or independently verified personal authorship.

## Workstream coverage in the team report
This share concentrates on the **Traditional and AI features**, **Business Goals and Objectives**, **Measurable Success Criteria**, **Initial Requirements Specification**, and AI-related elements of **Project Constraints**, **Scope Of The Project**, and the **Initial Project Plan Outline**. The initial project report sets out intended behavior; it does not demonstrate a working AI system.

## Detailed work package
### 1. Traditional versus AI-supported functions
The classic workflow relies on defined rules for asset registration, search, requests, approvals, transfers, and reporting. The AI-supported workflow is proposed to classify or organize descriptions of assets, match campus resource needs with available items, rank relevant options, produce understandable explanations, and assist with reports. Important asset decisions remain with authorized users. This distinction matters because AI suggestions must never act as automatic approval.

### 2. AI-assisted asset classification
The proposed classification functionality takes available item names, descriptions, specifications, images, and supporting documents as inputs. It suggests classifications and useful metadata to help custodians organize records consistently. A user should be able to review and correct a suggested classification before it becomes part of the record. Incomplete or unsuitable information should not be presented as a verified fact.

### 3. Matching resources to departmental demand
The system is intended to help requesters discover equipment even where different departments use different descriptions. Recommendations should consider the requested category, technical requirements, quantity, condition, and availability. AI similarity alone cannot make unavailable or unsafe stock eligible. Explainable results let a user compare alternatives rather than trust a score blindly.

### 4. Sustainable recommendations and assistant
Potential actions include reuse, repair, donation, and recycling. The AI component may explain choices using the available asset history and condition, but actual physical actions, approval, and policy decisions remain human-controlled. A natural-language assistant is proposed to help users locate information and navigate the system, rather than bypass permissions.

### 5. Reports, measurable goals, and caveats
The Phase 1 objectives include tracking reuse, repairs, potential avoided purchases, and estimated environmental benefits. Reports should show assumptions and distinguish estimates from verified outcomes. The plan names performance and usefulness targets: at least 90% of normal searches under three seconds under stated conditions, at least 80% of test users finishing main tasks unaided, and a suitable match in the top three AI results for at least 80% of prepared test requests. These are **targets**, not achieved test results.

### 6. Initial requirements and risks
AI-related requirements belong to the initial functional-requirements portion of the Phase 1 report (including the AI classification/matching/reporting cluster). Relevant risks include unreliable AI suggestions, unavailable data, privacy constraints, limited budget, and the need for human review. The scope remains a prototype with sample data unless real access is authorized.

## Workstream summary
This workstream forms one of three complementary parts of the team documentation: user interface and stakeholder experience, asset workflows and database design, and AI-enabled matching and reporting. The phase report remains the authoritative submission; this companion document makes its respective technical scope easier to locate, review, and develop in later phases.

**Documentation basis:** KU ResourceSavers, COSC 336, Phase 1 and Phase 2 reports.
