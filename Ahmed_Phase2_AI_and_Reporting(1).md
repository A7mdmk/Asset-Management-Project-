# Phase 2 — Workstream Documentation — Ahmed Mahmoud Alkhoori

**Focus:** AI, Data, Financial Indicators, and Reporting Feasibility

**Project:** KU ResourceSavers — Intelligent, AI-Powered Circular Campus Resource Exchange and Asset Life Cycle Management System  
**Course:** COSC 336 — Introduction to Software Engineering  
**Source documents:** `Phase 1.docx` and `Phase 2.docx` already present in the shared repository.  
**Document purpose:** Standalone explanation of this allocated project workstream using the team's completed phase reports. This document describes planned requirements and feasibility, not completed implementation or independently verified personal authorship.

## Workstream coverage in the team report
Proposed ownership focuses on **3.5 AI Feasibility**, **3.6 Integration Feasibility** (AI/reporting aspects), **4 Data and AI Feasibility**, **5 Financial Feasibility** (AI cost and benefits), **8 Market and Alternative Solutions Analysis** (AI comparison), and relevant parts of **9 Legal, Ethical, Security, and Policy Feasibility**, **10 Risk Assessment**, and the **AI Log**.

## Detailed work package
### 1. Why an external AI service is proposed
The Phase 2 report proposes a limited prototype built with Django and MySQL, using a hosted AI service rather than training a new large model. AI functions include classification, semantic matching, explanations, sustainable-action suggestions, assistant responses, and report summaries. Service availability, supported inputs, usage costs, and output quality require a trial; these were feasibility proposals, not completed integration results.

### 2. Classification, embeddings, and ranked search
The classification concept uses supplied names, descriptions, specifications, photographs, and documents to suggest categories, tags, material types, and missing metadata. A custodian confirms or corrects the proposed metadata. Semantic search would compare the meaning of asset descriptions and user requests using embeddings. Hard restrictions on availability, quantity, safety, and mandatory specifications should be applied before any AI ranking.

### 3. Data required and evaluation design
The proposed sample data comprises **200 assets across five categories and four fictional departments**, plus **40 requests**, **20 transfer examples**, and **20 maintenance examples**. These are planned evaluation records, not live university data. Required AI inputs must be complete enough to evaluate suitability; unverified values should remain unknown. The document proposes independently judging relevant matches and reserving at least ten requests for a final held-out check. The report also proposes broad-category classification evaluation on 50 labelled assets. These are evaluation plans, not published accuracy findings.

### 4. AI accuracy and human oversight
An apparently relevant suggestion may fail a technical specification. As a safeguard, the plan separates deterministic validation from probabilistic recommendations and asks users to confirm suggested changes. Similarity scores are not claimed to be calibrated probabilities. Model version, decisions, and overrides should be recorded to investigate errors and promote accountability.

### 5. Reporting, savings, and sustainable impact
Operational records for requests, transfers, repairs, and inventory supply the foundation for financial and sustainability reports. Application logic should compute numeric totals before sending permitted information to AI to generate human-readable summaries. AI wording must not invent savings or emissions figures. Benefit claims should identify assumptions, price sources, evidence gaps, and the difference between modeled examples and actual campus results.

### 6. Privacy, integration, cost, and limitations
The design requires role-scoped outputs and excludes uploading real sensitive operational or personal information to external AI without authorization. API keys must not be stored in the repository. The proposed stack mentions a Gemini API connection and PythonAnywhere hosting, subject to testing and budget review. Phase 2 estimates a **total planned three-month cash budget of AED 396.63**, within a proposed **AED 450 limit**; this is a planning estimate, not proof of spending. Conventional search and reports should continue when AI is unavailable.

## Workstream summary
This workstream forms one of three complementary parts of the team documentation: user interface and stakeholder experience, asset workflows and database design, and AI-enabled matching and reporting. The phase report remains the authoritative submission; this companion document makes its respective technical scope easier to locate, review, and develop in later phases.

**Documentation basis:** KU ResourceSavers, COSC 336, Phase 1 and Phase 2 reports.
