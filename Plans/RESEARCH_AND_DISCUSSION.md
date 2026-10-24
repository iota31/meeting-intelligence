# Meeting Intelligence: Research and Discussion

## 1. Problem framing

The goal was a working full-stack conversational AI system over meeting transcripts, with a stack and architecture chosen from scratch. I considered a few directions before settling on meeting intelligence: document chat, code documentation search, meeting intelligence, and career fit analysis.

The build favors a clean, dependable core over an ambitious but unreliable product. The README should reflect my own reasoning rather than unedited model output.

### Directions considered

1. **Chat With Your Docs**
   - Ingest PDFs, text files, or another document format.
   - Answer questions over the collection using RAG.

2. **Code Documentation Assistant**
   - Ingest a codebase from a public GitHub repository or local files.
   - Answer questions about architecture, implementation locations, API endpoints, and dependencies.

3. **Meeting Intelligence System**
   - Analyze meeting transcripts containing speaker labels and timestamps.
   - Answer questions about discussions, decisions, and action items.
   - Speech-to-text as a bonus path.

4. **Career Intelligence Assistant**
   - Analyze a resume against multiple job descriptions.
   - Answer questions about role fit, skill gaps, experience alignment, and interview preparation.

### Deliverables I set for myself

- Public repository containing the source code.
- Quick setup instructions.
- Architecture overview.
- Notes on productionizing, scaling, and deploying on a major cloud platform.
- RAG and LLM decisions, including:
  - LLM
  - Embedding model
  - Vector database
  - Orchestration approach
  - Prompt and context management
  - Guardrails
  - Quality controls
  - Observability
- Key technical decisions and rationale.
- Engineering standards followed and standards intentionally skipped.
- Description of how AI coding tools were used.
- Improvements that would be made with more time.
- Application screenshots and a short demo.

### Evaluation signals

- Working conversational and retrieval functionality.
- A simple usable interface.
- Product value.
- Thoughtful chunking, embeddings, retrieval, prompts, context management, guardrails, quality, and observability.
- Clean, readable, structured, tested, and appropriately containerized engineering.
- Disciplined and transparent use of AI-assisted development.

### Open questions

The problem did not fix:

- A deadline or effort budget.
- A required programming language, framework, model provider, or database.
- Corpus size or upload limits.
- An accuracy target or benchmark dataset.
- Authentication, tenancy, or persistence requirements.
- A deployment platform.
- The expected level of frontend polish.
- A precise definition of "full-stack."

These gaps make explicit assumptions and disciplined scope control the important part of the work.

---

## 2. Initial option comparison

| Option | Implementation effort | Conversational-AI depth | Demo value | Engineering risk | Judgment opportunity |
|---|---:|---:|---:|---:|---:|
| Chat With Your Docs | Low-medium | Medium | Medium | Low | Medium |
| Code Documentation Assistant | Medium-high | High | High | Medium-high | Very high |
| Meeting Intelligence | Medium | High | High | Medium | High |
| Career Intelligence | Medium | High | High | Medium-high | High |

### Chat With Your Docs

This is the easiest option to implement reliably using conventional ingestion, chunking, embeddings, retrieval, and citations. Its primary weakness is differentiation: a generic document chatbot risks looking like a standard RAG tutorial.

### Code Documentation Assistant

This has strong technical and demo value because answers can cite exact files and line ranges. It creates meaningful decisions around code-aware chunking, symbols, file metadata, hybrid retrieval, dependency analysis, source-code prompt injection, and unknown-answer behavior.

The primary danger is scope creep through universal language support, compiler-quality parsing, private repository authentication, or code execution.

### Meeting Intelligence

This has a clear user workflow and natural conversational questions. Speaker- and timestamp-backed decisions, action items, and blockers are easy to demonstrate and inspect. A transcript-only implementation is simpler than code intelligence, but may feel like an offline summarizer rather than a genuine meeting assistant.

### Career Intelligence

This has obvious user value and supports multi-document comparison. However, fit scoring is subjective, fairness is difficult to defend, and resume data introduces privacy concerns. A polished implementation needs an evidence-based rubric instead of invented compatibility percentages.

---

## 3. Initial recommendation: RepoLens

The initial recommendation was **Option 2: Code Documentation Assistant**, provisionally named **RepoLens**.

### Product concept

A citation-first conversational assistant that ingests one public repository or repository archive and answers questions such as:

- How is authentication implemented?
- What API routes exist?
- Where is the database configured?
- Which dependencies are important?
- Where is a particular symbol implemented?

Answers would include clickable references in the form:

```text
path/to/file.ts:20-48
```

When evidence is insufficient, the assistant would say so rather than fabricate an answer.

### Initial RepoLens scope

- Public GitHub URL or repository archive input.
- TypeScript/JavaScript, Python, Markdown, JSON/YAML, and package manifests.
- File- and line-range citations.
- Conversational follow-up questions.
- Explicit insufficient-evidence behavior.
- No repository code execution.
- Repository contents treated as untrusted data rather than instructions.

Excluded:

- Private GitHub OAuth.
- Repository modification.
- Arbitrary binary formats.
- Universal programming-language support.
- Multi-user accounts.
- Compiler-grade semantic analysis.
- Automatic code generation or pull requests.

### Initial architecture proposal

- Next.js App Router and TypeScript.
- React and a minimal component library.
- Vercel AI SDK for streaming.
- PostgreSQL and pgvector.
- Vector similarity plus PostgreSQL full-text search.
- Deterministic file filtering.
- Structure-aware code chunking.
- In-process ingestion with visible status.
- Docker Compose for local PostgreSQL.

Each chunk would include:

```text
repository_id
file_path
language
symbol_name, when available
start_line
end_line
content
embedding
```

Retrieval would combine semantic similarity, lexical matching, metadata boosts, and limited adjacent-chunk expansion.

### RepoLens quality plan

Create approximately 12-20 questions covering:

- Architecture.
- API routes.
- Dependencies.
- Symbol locations.
- Configuration.
- Unanswerable questions.
- Prompt injection embedded in repository content.

Measure:

- Retrieval hit rate.
- Citation correctness.
- Answer groundedness.
- Latency.
- Token usage.

---

## 4. Blinded review-council findings

A two-round blinded review was run with MiniMax and Grok. Both independently returned **approve with changes**.

### Panel verdicts

| Reviewer | Round 1 | Round 2 |
|---|---:|---:|
| MiniMax | Approve with changes  -  78% | Approve with changes  -  82% |
| Grok | Approve with changes  -  70% | Approve with changes  -  74% |

Grok initially failed because its authentication token had been revoked. After user-authorized reauthentication, one disclosed retry succeeded. Both models then completed both rounds.

### Consensus

- Option 2 is valid and defensible.
- File-and-line citations provide a strong grounding story.
- Claims that RepoLens would necessarily be more memorable or score better are unverified.
- Citation quality is load-bearing.
- Evaluation needs a fixed, reproducible corpus.
- Repository content must be treated as untrusted at both prompt and ingestion boundaries.
- Deployment should not drive the MVP.
- Advanced retrieval should be justified through measured failures rather than assumed to be necessary.

### Material disagreement

The reviewers disagreed about whether PostgreSQL/pgvector, hybrid retrieval, and structural parsing were inherently too ambitious.

One position was that these components conflict with the principle of starting simple. The other was that a technology should not be judged as excessive merely by name and that replacing PostgreSQL with SQLite could create unnecessary rework.

The reconciled position was:

- Keep PostgreSQL/pgvector if it is the simplest practical vector store for the implementation.
- Begin with one straightforward vector retrieval path.
- Add lexical fusion only if exact-symbol retrieval failures justify it.
- Start with deterministic line-window chunks.
- Treat AST or Tree-sitter parsing as an experiment rather than a prerequisite.
- Avoid creating feature flags or multiple storage implementations solely for architectural purity.

### Reconciled RepoLens MVP

Include:

- One public GitHub repository URL as the initial input path.
- TypeScript/JavaScript, Markdown, JSON, YAML, and package manifests.
- Safe deterministic ingestion.
- Chunks with file path, line range, language/content type, optional symbol, content, and embedding.
- Vector retrieval.
- Answers with file-and-line citations.
- Insufficient-evidence responses.
- Basic follow-up questions.
- A pinned demonstration repository.
- A reproducible 12-20-question evaluation set.
- Retrieval, citation, latency, and token logging.
- Minimal functional UI.

Defer:

- Python support.
- ZIP uploads.
- Vector/full-text fusion.
- AST or Tree-sitter parsing.
- Complex adjacent-chunk expansion.
- Private repositories.
- Accounts and multi-tenancy.
- Multi-repository conversations.
- Hosted deployment.
- Code execution, editing, or PR generation.

### Citation contract

A repository-specific claim should:

- Cite one or more `path:startLine-endLine` references.
- Use multiple citations when a claim spans files.
- Avoid presenting general programming knowledge as repository evidence.
- Say that sufficient repository evidence could not be found when retrieval is inadequate.
- Never fabricate paths, symbols, or line numbers.

### Ingestion contract

Explicit limits should cover:

- Maximum repository size.
- Maximum file count.
- Maximum individual file size.
- Clone timeout.
- Ignored dependency, generated, build, and VCS directories.
- Binary detection.
- Partial-ingestion failure behavior.
- Secret-bearing files that should not be stored or logged.

### Evaluation contract

Pin a public repository commit and version-control an evaluation grid containing:

- Question.
- Category.
- Expected file or line region.
- Whether the question should be answered.
- Whether it should produce insufficient evidence.
- Retrieval success.
- Citation correctness.
- Groundedness result.

---

## 5. An alternative analysis: Meeting Intelligence

An early alternative analysis recommended **Meeting Intelligence**, framed as a **Clinical Consultation and Stakeholder Discovery Analyzer**.

Its main reasoning was:

1. Field engineering work often lands in regulated domains such as digital health and life sciences.
2. Field engineers work closely with clients and translate ambiguous stakeholder conversations into concrete prototypes.
3. Meeting analysis can demonstrate timestamp-aware indexing, custom transcript chunking, and hybrid retrieval.

Gemini proposed:

- Next.js/React/Tailwind frontend.
- FastAPI backend.
- BM25 plus vector retrieval using pgvector or Chroma.
- FastMCP tool endpoint.
- Evaluation harness.
- Docker and GitHub Actions.

### Useful insight from Gemini

The strongest contribution was evaluator and company alignment. RepoLens optimizes for technical inspectability, while Meeting Intelligence may align more directly with:

- Healthcare and life-sciences stakeholders.
- Field-engineering discovery sessions.
- Turning ambiguous discussion into decisions and action.
- A demo understandable to both technical and business reviewers.

### Problems with Gemini's proposal

#### Unverifiable citations

The labels `[cite: 1]` and `[cite: 2]` were not accompanied by inspectable sources. Claims about company preferences for Next.js, FastAPI, MCP, hybrid retrieval, Docker, CI/CD, and evaluation harnesses should be verified before being used as architectural requirements.

#### Risky clinical framing

A doctor-patient consultation analyzer creates unnecessary concerns:

- Protected health information.
- Consent and retention.
- Medical-advice implications.
- Clinical accuracy and safety expectations.
- Ambiguity about whether extracted decisions are medically authoritative.

A safer framing is a synthetic **life-sciences stakeholder meeting** involving roles such as product lead, clinical operations, compliance, and engineering.

#### Résumé-driven architecture

FastAPI, FastMCP, BM25, vector search, Docker, and CI/CD may mirror job-description keywords without solving immediate product needs. This could look like stack matching instead of engineering judgment.

In particular:

- MCP is not required for a self-contained web application.
- Next.js plus FastAPI introduces two services and two dependency ecosystems.
- Hybrid retrieval should be added only when evaluated failures justify it.
- Deployment discussion is required in the README, but hosted deployment is not necessarily required.

### Revised comparison

| Dimension | RepoLens | Meeting Intelligence |
|---|---|---|
| Company/domain alignment | Moderate | Potentially excellent |
| Objective evidence | File and line citations | Speaker and timestamp citations |
| Implementation risk | Medium | Low-medium for transcript input; higher for live audio |
| Parsing complexity | Higher | Lower for formatted transcripts |
| Security concerns | Malicious repositories | Sensitive meeting data and consent |
| Demo clarity | Strong for engineers | Strong for mixed audiences |
| Evaluation design | Expected files and lines | Expected speakers and timestamps |
| Differentiation | Technically distinctive | Product/domain distinctive |
| Field-engineering narrative | Understand an unfamiliar system | Convert stakeholder discussions into action |

RepoLens is the stronger pure engineering demonstration. Meeting Intelligence may be the stronger field-engineering and domain-aligned choice.

---

## 6. Critical correction: analyzer versus assistant

The first Meeting Intelligence concept accepted a text transcript upload and produced:

- Summary.
- Decisions.
- Action items.
- Open questions.
- Timestamp-grounded Q&A.

Although this covers the literal requirement, it is better described as a **post-meeting transcript analyzer** than a convincing **meeting assistant**.

A genuine meeting assistant should be present during the meeting.

The revised concept therefore uses **live audio as its primary input**, not video and not an already-completed transcript.

### Why audio rather than video

Audio contains the information required for:

- Spoken discussion.
- Decisions.
- Commitments.
- Speaker turns.
- Timing.

Video adds faces, gestures, screen content, bandwidth, and privacy concerns without substantially improving the core intelligence. If a video recording is supplied, the product can extract and process its audio track without analyzing video frames.

Browser screen-sharing APIs may technically provide a video track while capturing tab audio. The application can discard the video frames immediately and process audio only.

---

## 7. Revised product: live stakeholder meeting copilot

### Product statement

> A live copilot that listens to stakeholder meetings, surfaces decisions and commitments as they emerge, and produces an evidence-backed meeting record.

### User experience

The user opens the application alongside Zoom or Google Meet and clicks **Start Copilot**.

The browser captures:

- Meeting-tab or system audio for remote participants.
- Microphone audio for the local user.

The product then displays:

- A live rolling transcript.
- Candidate decisions.
- Candidate action items.
- Dependencies and blockers.
- Open questions.
- Live and post-meeting conversational Q&A.

At the end of the meeting, it generates a finalized brief with timestamp and speaker citations.

### Example

Input conversation:

```text
[00:03:12] Priya  -  Product Lead:
We should launch the pilot at the Boston site first.

[00:03:20] Marcus  -  Compliance:
That works if legal approves the updated consent form.

[00:04:05] Elena  -  Program Manager:
I'll send the revised form to legal by Friday.
```

Potential output:

```text
Decision
The pilot will begin at the Boston site, subject to legal approval.
Sources: 00:03:12, 00:03:20

Action item
Elena will send the revised consent form to legal by Friday.
Source: 00:04:05

Dependency
Legal approval of the consent form is required before the pilot begins.
Sources: 00:03:20, 00:04:05
```

The user could ask:

- Why was Boston selected?
- What is blocking the pilot?
- What did the compliance lead say?
- Which actions are assigned to Elena?
- Was a launch date actually confirmed?

Every repository-specific equivalent in this system - every meeting-specific claim - should cite the speaker and timestamp. Unsupported questions should result in an explicit insufficient-evidence answer.

---

## 8. Two levels of meeting participation

### Browser copilot  -  realistic MVP

The user starts the application and grants permission to capture meeting-tab and microphone audio.

Advantages:

- No Zoom, Teams, or Google OAuth integrations.
- No calendar integration.
- No bot-admission process.
- Operates live during the meeting.
- Demonstrates meaningful browser media and streaming-AI engineering.

Limitation:

- The user must manually start the copilot and grant audio-sharing permission.

### Autonomous meeting bot  -  production roadmap

A named bot appears as a meeting participant and joins from the calendar invitation.

This requires:

- Zoom, Teams, and Google Meet integrations.
- OAuth and calendar access.
- Bot-admission handling.
- Media-stream infrastructure.
- Recording-consent workflows.
- Retry and reconnection logic.
- Platform-specific APIs or a meeting-bot provider.

This is a credible production direction but too much platform integration for an MVP.

---

## 9. Revised live-audio workflow

```text
Live meeting audio
        ↓
Streaming speech-to-text
        ↓
Timestamped rolling transcript
        ↓
Incremental decision/action analysis
        ↓
Live copilot interface
        ↓
Final meeting brief
        ↓
Grounded conversational Q&A
```

### During the meeting

1. User clicks **Start Copilot**.
2. Browser asks the user to share the meeting tab with audio.
3. Audio is sent to a streaming transcription service.
4. Transcript segments appear with speakers and timestamps.
5. Every 30-60 seconds, the LLM analyzes the newly accumulated transcript window.
6. Candidate decisions, actions, blockers, and open questions appear in the UI.
7. The user can confirm or dismiss extracted items.

### After the meeting

- Final meeting brief.
- Searchable transcript.
- Action items grouped by owner.
- Conversational Q&A.
- Timestamp citations that jump to transcript segments.
- Optional playback synchronized with citations.

### Human confirmation

The system should not silently promote every statement into a decision. It should surface candidates:

```text
Possible decision detected

“Proceed with the Boston pilot after legal approval.”

[Confirm decision] [Not a decision]
```

This makes the system a copilot rather than an infallible meeting authority.

---

## 10. Core intelligence challenge

Speech-to-text is an enabling layer, not the primary intelligence. The important problem is classifying statements and their evolution:

- **Discussion:** someone raised a subject.
- **Proposal:** someone recommended an action.
- **Decision:** the group actually agreed.
- **Action item:** a specific person accepted work.
- **Dependency or blocker:** something must happen first.
- **Open question:** the meeting did not resolve it.
- **Reversal:** a later statement changed or rejected an earlier proposal or decision.

Example:

```text
[00:10] “Perhaps we should delay the pilot.”
[00:14] “No, let's keep the current launch date.”
```

A weak summarizer may report that the launch was delayed. The system should identify the first statement as a proposal and the second as the final decision.

The product should also distinguish:

- **Explicitly stated**
- **Reasonably inferred**
- **Not found**

It must not invent owners, deadlines, decisions, or rationales.

---

## 11. Lean live-copilot stack

### Application

- **Next.js App Router and TypeScript** for the full-stack application.
- **React and Tailwind CSS** for the interface.
- **Vercel AI SDK** for model calls, streaming, and structured outputs.

### Browser media

- `getDisplayMedia()` for meeting-tab audio.
- `getUserMedia()` for microphone audio.
- Web Audio API for mixing or coordinating streams if needed.

### AI and data

- A streaming speech-to-text provider for live transcription and, where supported, speaker handling.
- PostgreSQL for meetings, transcript segments, extracted items, and feedback.
- pgvector or full-text search for post-meeting transcript retrieval, only as justified by the evaluation corpus.
- Zod for validating structured model output.

### Quality

- Vitest for deterministic parser, extraction, and retrieval tests.
- Playwright for one critical start-to-answer browser flow.
- Structured logs for transcription, extraction, retrieval, latency, tokens, and failures, excluding sensitive content where appropriate.

### Explicitly excluded from the initial MVP

- FastAPI.
- MCP or FastMCP.
- Autonomous meeting bots.
- Zoom/Teams/Google Calendar integrations.
- User accounts.
- Real patient data.
- Medical recommendations.
- Complex multi-agent workflows.
- Speech model training.
- Broad CI/CD or deployment infrastructure beyond what is necessary to verify the application.

---

## 12. Live-copilot MVP boundaries

The MVP should:

- Capture live browser meeting audio.
- Capture the local user's microphone when needed.
- Produce a timestamped rolling transcript.
- Incrementally extract candidate decisions, actions, blockers, and open questions.
- Allow the user to confirm or dismiss candidates.
- Produce a final evidence-backed brief.
- Support grounded post-meeting questions.
- Link every claim to the relevant speaker and timestamp.
- Refuse unsupported questions.
- Use only synthetic life-sciences stakeholder meeting data.

The MVP should not:

- Analyze video frames.
- Join meetings autonomously.
- Process real clinical consultations or patient data.
- Make medical recommendations.
- Integrate with calendars or conferencing APIs.
- Send notifications or emails.
- Implement multi-tenant authentication.
- Depend on MCP.

If live audio capture and streaming transcription cannot be implemented reliably, RepoLens is preferable to falling back to a weak transcript-upload-only product.

---

## 13. Demo strategy

Live browser audio can vary by browser and conferencing platform. The application should therefore support two clearly labeled demonstration paths using the same ingestion pipeline:

1. **Live meeting-tab audio capture.**
2. **Prerecorded audio replayed through the real-time streaming pipeline.**

The prerecorded path is a deterministic simulation, not a separate mocked implementation, if it uses the same transcription, extraction, persistence, and UI path as live audio.

A scripted synthetic meeting provides known ground truth and avoids exposing sensitive data.

---

## 14. Evaluation design for the live copilot

Prepare several scripted synthetic stakeholder meetings with known ground truth.

### Decision extraction

- Was the actual final decision identified?
- Were proposals or rejected alternatives incorrectly labeled as decisions?
- Is the supporting timestamp correct?

### Action-item extraction

- Is the action correct?
- Is the owner correct?
- Is the due date correct when explicitly stated?
- Did the system avoid inventing an owner or deadline?

### Question answering

- Is the answer correct?
- Was the supporting transcript segment retrieved?
- Is the timestamp citation correct?
- Did the answer avoid unsupported claims?

### Unanswerable questions

- Does the system decline when the meeting contains no answer?

### Contradictory discussion

- Does the system distinguish a proposal from a final decision?
- Does a later reversal supersede an earlier statement?

### Prompt injection

- Does a spoken or transcribed statement such as "ignore all prior instructions" remain meeting content rather than becoming an instruction to the assistant?

### Streaming behavior

- Does incremental processing avoid repeatedly creating duplicate actions or decisions?
- Does the finalization pass reconcile provisional items correctly?
- Does reconnecting or retrying transcription duplicate transcript segments?

### Suggested metrics

- Decision precision and recall.
- Action-item precision and recall.
- Owner accuracy.
- Due-date accuracy.
- Citation correctness.
- Retrieval hit rate.
- Groundedness.
- Duplicate-item rate.
- Unsupported-claim rate.
- Transcription-to-insight latency.
- Token and model cost per meeting minute.

---

## 15. Current decision position

There are now two credible directions:

### RepoLens

Choose this if the priority is:

- A stronger pure engineering and retrieval demonstration.
- Exact, objectively verifiable file-and-line evidence.
- Less dependence on real-time media and transcription APIs.
- A narrower operational surface.

### Live Stakeholder Meeting Copilot

Choose this if the priority is:

- Stronger alignment with field-engineering work and life-sciences stakeholders.
- A more intuitive mixed-audience product demonstration.
- Real-time conversational AI rather than post-hoc document analysis.
- Demonstrating browser media, streaming transcription, incremental extraction, human confirmation, and grounded finalization.

### Working recommendation

The current preference is the **Live Stakeholder Meeting Copilot**, provided live audio capture and streaming transcription are treated as core MVP functionality.

The product should be framed as a life-sciences stakeholder tool using synthetic data, not as a doctor-patient consultation analyzer.

The architecture should remain lean: one full-stack TypeScript application, a streaming speech-to-text provider, structured LLM extraction, evidence-backed output, and a reproducible evaluation harness. FastAPI, MCP, autonomous bots, platform integrations, and unmeasured hybrid retrieval should be deferred.

If the team is unwilling to accept the engineering risk of live audio, the preferred fallback is RepoLens - not a transcript-upload-only meeting summarizer.

---

## 16. Open decisions before implementation

1. Confirm whether to commit to the Live Stakeholder Meeting Copilot or return to RepoLens.
2. Choose the streaming speech-to-text provider based on:
   - Browser streaming support.
   - Speaker diarization capability.
   - Partial/final transcript event semantics.
   - Latency.
   - Cost.
   - Data-retention policy.
3. Decide whether both tab audio and microphone audio are required in the first demonstration.
4. Define the exact supported browser and conferencing setup.
5. Decide whether raw audio is stored or discarded after transcription.
6. Define consent and recording indicators.
7. Set meeting-duration and audio-size limits.
8. Define provisional-item reconciliation and user confirmation behavior.
9. Pin the synthetic evaluation meetings and ground-truth annotations before building extraction logic.
10. Base architectural claims on measured needs rather than assumptions about any single client.
