---
status: proposed
date: 2026-10-16
---

# Research: how the profile is stored, written, and shown

This is the research note that [decision 0003](../decisions/0003-profile-pass-is-a-proposal.md) and CLAUDE.md ask for before the session-end pass is changed. It compares ways to store, write, and show the profile. It recommends one design, and it drafts the rules that design would need.

Nothing here is in force. PR-01 through PR-08 in [profile.md](../features/profile.md) still hold. The draft decision is [0006](../decisions/0006-typed-profile-with-evidence.md), status proposed. The new rules in [section 9](#9-draft-rules-and-scenarios) are not yet in profile.md.

This note is not on the critical path for the v1 sign-in date (18 Oct 2026, [decision 0004](../decisions/0004-local-sign-in-before-sunday.md)). It plans work for after that date.

The file is named `profile-design`, not `profile-memory`, because the glossary lists "memory" as a word to avoid. Outside systems are named here with their own word for it ("Mem0 memory", "Letta memory blocks"). Polaris words keep their glossary meaning.

## 1. What Polaris does today

| Part | Where | What it does |
|---|---|---|
| Store | `api/polaris/profile.py` `load_profile`, `save_profile` | `profile.json` holds `{"facts": [string, ...]}`. One flat list of strings. |
| Apply changes | `profile.py` `apply_changes` | ADD appends if the exact string is new. DELETE drops exact matches. UPDATE swaps the fact whose text equals `replaces`. If nothing matches, it appends. |
| Pass | `api/polaris/profile_pass.py` | A one-shot Haiku `query()` with a JSON schema for `{action, fact, replaces}`. The system prompt is six lines. |
| Pass input | `profile_pass.py` `session_prompt` | Current facts, then each turn as `Learner: ...` / `Polaris: ...`. |
| Trigger | `api/polaris/chat.py` `run_profile_pass`, `app.py` `close_ended`, `leave_session` | Runs when a session ends (CH-05), inside the request that ends it. It reads every turn of the session again each time. |
| Read | `api/polaris/teaching.py` `turn_prompt`, `format_facts` | Every fact goes into every turn prompt as a bullet. With no facts, `_MISSING_PROFILE` tells the agent to ask and not teach. |
| Show | `app.py` `GET /api/profile`, `web/src/api.ts` `readProfile` | The endpoint and the client function exist. No screen calls them. |

## 2. Weaknesses, with evidence

**W1. Facts have no kind, source, time, or certainty.** The glossary gives the profile four kinds of fact: how the learner wants to be taught, what they can already do, where they struggle, and milestones. `Profile.facts` is `tuple[str, ...]` (`models.py`), so the store can't tell them apart. Nothing records which session a fact came from, when it was written, or whether the learner said it or the pass guessed it. So no fact can be explained, checked, or aged out.

**W2. Matching is by exact string.** `apply_changes` compares `item != fact` and `replaced in facts`. "I suck at math" and "Struggles with math" are two facts. An UPDATE whose `replaces` is reworded (`elif fact not in facts: facts.append(fact)`) appends instead of replacing, so the old fact stays next to the new one. A DELETE with any change in wording does nothing. PR-08 only holds for word-for-word repeats. The PR-08 scenario passes because it uses one fixed string.

**W3. The pass prompt does not say what a good fact is.** `profile_pass_prompt` names the four actions and the milestone meaning. It doesn't say:
- what is worth storing,
- how to word a fact,
- what never to store, such as health or other sensitive personal details, or a passing mood like "I'm tired today",
- when to DELETE.

**W4. The pass is blind to evidence.** `ChatService._turns` loads each turn's artifacts: quiz score and submitted choices, whiteboard drawing and comments, animation jobs. But `session_prompt` writes only `learner_message` and `reply`. The pass never sees:
- a quiz score, or which wrong choice the learner picked,
- the learner's drawing, their comments, or where they pointed (WB-02, WB-08),
- that the learner asked for a simpler drawing (WB-11, `Whiteboard.simplifies`).

So PR-06 milestones are guessed from chat text. A graded quiz is a better source, and the pass never reads it.

**W5. A failed pass is silent.** `ClaudeProfilePass.run` returns `()` on any exception, and `run_profile_pass` returns on any exception except `ApiKeyPresent`. Nothing is logged or stored, nothing is retried, and the learner is never told. A Claude outage during a session end loses that session's facts for good.

**W6. Every fact goes into every turn.** `format_facts` writes the whole list. Nothing selects facts for the topic, merges facts that overlap, or caps the size. The cost and noise grow with each session.

**W7. The learner can't see or correct the profile.** `readProfile` has no caller. A wrong fact ("struggles with fractions" after one slip) shapes every reply, and the learner can't see it or remove it.

**W8. A learner's whole first session asks and never teaches.** Under [decision 0005](../decisions/0005-empty-profile-keeps-asking.md), the profile stays empty until the session ends. So every reply in that first session asks again, even after the learner has answered. A first-time learner who answers in turn 2 still gets questions in turns 3, 4 and 5. This is the first thing a new learner sees.

**W9. There is nowhere to store the learner's goal.** [product.md](../product.md) says Polaris "guides a learner toward a subject they want to learn", including course material. No fact kind holds "the subject, course, exam or deadline the learner is working toward". It can only be a loose string among the others, and nothing asks for it.

## 3. Sources

The options below draw on these sources. Some details come from secondary write-ups; those are marked.

1. Chhikara et al., *Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory*, arXiv 2504.19413, 2025. <https://arxiv.org/abs/2504.19413>. Mem0 does two steps. It first pulls candidate facts out of the conversation. It then fetches the most similar stored facts and has an LLM choose ADD, UPDATE, DELETE or NOOP against them. Prompt: <https://docs.mem0.ai/features/custom-update-memory-prompt>.
2. Packer et al., *MemGPT: Towards LLMs as Operating Systems*, arXiv 2310.08560, 2023. <https://arxiv.org/abs/2310.08560>. Letta docs: <https://docs.letta.com/guides/agents/architectures/memgpt>, <https://docs.letta.com/concepts/memory-management>. MemGPT has three tiers:
   - core memory: small, labelled blocks inside the context window,
   - recall memory: the searchable conversation log,
   - archival memory: a store searched through tools.

   The agent edits its own memory through tools. A secondary tutorial says Letta also runs a separate "sleep-time" agent that tidies memory while the main agent is idle.
3. Rasmussen et al., *Zep: A Temporal Knowledge Graph Architecture for Agent Memory*, arXiv 2501.13956, 2025. <https://arxiv.org/abs/2501.13956>. Each fact has validity times, and an old fact is marked no longer valid instead of being overwritten. This is the idea behind keeping a fact's history.
4. Park et al., *Generative Agents: Interactive Simulacra of Human Behavior*, arXiv 2304.03442, 2023. <https://arxiv.org/abs/2304.03442>. Retrieval ranks stored items by recency, importance and relevance. "Reflection" writes higher-level items from many low-level ones. This is the idea behind selecting and consolidating facts.
5. OpenAI, *Memory FAQ*. <https://help.openai.com/en/articles/8590148-memory-faq>.
   - The user can view and delete saved memories one by one, or ask in chat to forget something.
   - A temporary chat neither reads nor writes memory.
   - Deleting a chat does not delete memories that came from it.
6. Anthropic, *Bringing memory to Claude*. <https://www.anthropic.com/news/memory>. The user can view and edit what Claude remembers. Memory is kept separate per project. Incognito chats are not saved to memory.
7. Corbett & Anderson, *Knowledge tracing: Modeling the acquisition of procedural knowledge*, User Modeling and User-Adapted Interaction 4(4), 1995. Badrinath, Wang & Pardos, *pyBKT*, arXiv 2105.00385, 2021. <https://arxiv.org/abs/2105.00385>. Bayesian knowledge tracing (BKT) keeps, for each skill, a probability that the skill is learned. It updates that probability after each graded attempt, using four parameters:
   - prior: the chance the skill is known before the first attempt,
   - learn: the chance of moving from unlearned to learned after an attempt,
   - guess: the chance of a correct answer while unlearned,
   - slip: the chance of a wrong answer while learned.

   The parameters are usually fitted with expectation maximization from many learners' logs, and they are known to be hard to identify from small, noisy data (summary in <https://jedm.educationaldatamining.org/index.php/JEDM/article/download/35/pdf_27>).
8. Bull & Kay, *Student Models that Invite the Learner In: The SMILI Open Learner Modelling Framework*, IJAIED 17(2), 2007, revised IJAIED 26, 2016. <https://research.birmingham.ac.uk/en/publications/smili-a-framework-for-interfaces-to-learning-data-in-open-learner/>. Overview: <https://edutechwiki.unige.ch/en/Open_learner_model>. An open learner model shows the learner what a tutor believes about them, and sometimes lets them question or edit it. Reasons given (secondary source): a more accurate model, prompting reflection, and learner trust.

## 4. Options compared

Each option is judged against these constraints:
- PR-04: the teaching agent never writes the profile.
- One local learner: no extra services, no hosting.
- Claude only, through the Agent SDK.
- WCAG AA for anything the learner sees.
- Small enough to build after the sign-in deadline.

### A. Keep the current pass

Keep `profile.json`, string facts, and string matching. Only lengthen the prompt.

- For: no migration, no new code paths.
- Against: W1, W2, W4 and W5 stay. A longer prompt can't fix string matching, because the model has no stable handle to name a fact by.
- Verdict: rejected as the end state. Its one cheap gain, a better prompt, is folded into the recommendation.

### B. Typed facts in SQLite, next to sessions

Move facts into the same SQLite database as sessions, turns and artifacts. Each fact gets:
- an id,
- a kind,
- text,
- a basis (stated, observed, or inferred),
- created and updated times,
- evidence rows that point at a session, turn, or artifact (a quiz or whiteboard).

- For:
  - Fixes W1, and makes W2 and W7 possible to fix.
  - Evidence can be a real foreign key to `sessions`, `turns` and `artifacts`, which already live in that database (`chat.py` schema).
  - One file to back up, and one transaction can write a fact and its evidence.
- Against:
  - A one-time migration from `profile.json`.
  - A schema to maintain.
- Verdict: adopt.

### C. Changes by id (Mem0-style)

The pass sees each stored fact with a short id (F1, F2 ...). UPDATE and DELETE must name an id. Code rejects an id that isn't in the list, instead of appending a new fact. This follows Mem0's update step (source 1), which shows the model the stored facts and asks it to choose an action for each.

- For:
  - Fixes W2 at the root. A reworded repeat becomes UPDATE F3 or IGNORE, and a correction replaces the right fact.
  - Short ids, mapped to real ids in code, keep the model from inventing long ids.
- Against: this does not catch two different ADDs with the same meaning in one pass. The prompt covers that, and an eval checks it.
- Mem0 also fetches only the most similar stored facts, by embedding search. Polaris has one learner with tens of facts, so the pass can see every fact, and no embedding index is needed. Revisit this if a profile grows past what fits comfortably in one prompt.
- Verdict: adopt.

### D. Tiered memory (MemGPT / Letta)

Split the profile into a small core block that is always in the prompt and a larger store that the agent searches and edits through tools.

- For: a clear answer to W6, and proven for long-running agents (source 2).
- Against:
  - The teaching agent edits its own memory in MemGPT. That breaks PR-04, which is a deliberate rule: the teaching agent must not rewrite what Polaris believes about the learner mid-reply.
  - Search tools add tool turns to every reply.
  - One learner's profile is small. Polaris already keeps the full conversation as session turns, and that plays the part of recall memory.
- Verdict: reject the architecture, keep two ideas from it.
  1. A bounded core: goal, how they want to be taught, and current struggles are always in the turn prompt, under a size budget.
  2. Tidying by a separate, non-teaching model: Letta's sleep-time agent is close to Polaris's session-end pass. The pass merges overlapping facts when a kind goes over its budget.

### E. A profile the learner can see and edit (consumer assistant pattern)

ChatGPT and Claude both let the person view stored items, edit them, and forget them one by one. Both also offer a mode that writes nothing (sources 5, 6). Open learner model research reaches the same idea in tutoring: showing the learner the model makes it more accurate and builds trust (source 8).

- For:
  - Fixes W7, and catches wrong facts that no prompt change will prevent.
  - Gives the learner a reason to trust the "honest about limits" line in product.md.
- Against:
  - A new screen, which must meet WCAG AA and be mobile first.
  - A rule is needed for what the pass may do to a fact the learner edited.
- Forgetting has a catch. The OpenAI FAQ notes that deleting a chat does not remove memories made from it, and the reverse is a risk here: when a session is reopened and ended again, a pass reading all its turns would add a forgotten fact back. Fix: the pass reads only turns it has not read before (see H below).
- Verdict: adopt. Leave out a "write nothing" session for now; v1 has one local learner. Record it as a later option.

### F. Per-concept mastery from quiz evidence (knowledge tracing)

Tag each quiz question with the concept it checks. Then track mastery for each concept from graded answers, either with BKT (source 7) or a simpler evidence rule.

- For:
  - Fixes the PR-06 half of W4. A milestone rests on graded answers, which QZ-04 already keeps in code, not on a guess from chat.
  - Wrong-choice data shows which misconception was picked, because QZ distractors are written as plausible mistakes. That can become a struggle fact with a quiz as its evidence.
- Against, for full BKT now:
  - It needs fitted parameters. Fitting needs many attempts per concept, and the fitted values are known to be hard to identify from small data (source 7).
  - One learner gives a handful of answers per concept. Default parameters would give numbers that look precise but don't mean much.
  - Quiz questions carry no concept tag today. Adding one changes `create_quiz` and quiz.md, which are being edited separately.
- Verdict: adopt an evidence rule now, and keep BKT for later.
  - Now: a milestone needs a graded quiz in which every question on that concept was answered correctly. Code checks this, not the model.
  - Later: once questions carry a concept tag and a concept has enough graded answers, a BKT estimate can show beside each milestone. It would not decide milestones by itself.

### G. A checkpoint pass early in a session with an empty profile

When the profile is empty and the learner sends a message after the first reply, run the same kind of separate pass on the turns so far before the reply is written. If it stores facts, that reply can teach.

- For:
  - Fixes W8 and keeps PR-04: the teaching agent still never writes, and the writer is still a separate model.
  - Keeps PR-02: no teaching happens while the profile is empty, because the profile is no longer empty.
  - Same code as the session-end pass with a different trigger.
- Against:
  - One extra Haiku call before that reply. It is a few seconds, and only while the profile is empty.
  - A failed or empty checkpoint must fall back cleanly to asking again.
- Alternatives considered:
  - Let the teaching agent teach once it judges the answers enough. Rejected: that is the teaching agent deciding the profile, which is what 0005 was protecting.
  - Teach regardless. Rejected for the same reason 0005 gives.
- A learner who says "just start" is answering the question. "Wants to start without questions" is a how-to-be-taught fact, and the checkpoint stores it.
- Verdict: adopt. This replaces decision 0005.

### H. Smaller items folded into the recommendation

- **Failure is recorded and shown (W5).** Each pass writes a run row with status and error. If a session-end pass failed, the next screen says so and offers a retry. Failed runs are retried when Polaris starts and when the next session starts.
- **The pass reads only new turns.** Each run stores the last turn it read. A later end of the same session reads only the turns after it. This keeps PR-05's "runs again" without re-adding forgotten facts, and it costs less.
- **The pass runs after the response.** `leave_session` waits for the pass today. It could run as a background task, and the run row (above) holds its outcome. This is optional and does not affect the rules.
- **Goal (W9).** Add a fact kind for the learner's goal. Ask for it while it is missing, as one of the things the profile is missing. Always put it first in the turn prompt.

## 5. Recommendation

Adopt **B + C + E + G**, the evidence rule from **F**, the two ideas taken from **D**, and the items in **H**. Keep BKT as a later step.

Suggested order of work, smallest and most useful first:

1. **Store and pass.**
   - SQLite tables for facts and evidence, with a migration from `profile.json`.
   - Changes by id, with code that rejects a change it can't place.
   - A full pass prompt (section 7).
   - Run rows that record failure.

   This fixes W1, W2, W3 and W5, and keeps every rule in force.
2. **First session.** The checkpoint pass (G). This fixes W8.
3. **Evidence in.** Pass inputs from quizzes, whiteboards and simpler requests (section 7). This fixes W4, apart from concept tags.
4. **Learner view.** The profile screen (section 8). This fixes W7.
5. **Goal and budget.** The goal kind (W9), and fact selection under a budget with merging by the pass (W6).
6. **Later.** Concept tags on quiz questions, then BKT estimates shown next to milestones.

Steps 1 and 2 are the minimum to call the pass design researched. Each step is one change set that leaves PR rules either in force or replaced by a written rule.

## 6. Proposed fact schema

Facts move from `profile.json` into the session database. The kinds map one to one onto the glossary's list, plus `goal`.

```sql
CREATE TABLE facts (
    id          TEXT PRIMARY KEY,           -- uuid
    kind        TEXT NOT NULL CHECK (kind IN (
                    'goal',                 -- subject, course, exam, or deadline (proposed term)
                    'taught',               -- how they want to be taught
                    'can_do',               -- what they can already do
                    'struggle',             -- where they struggle
                    'milestone',            -- they understood a concept
                    'unsorted'              -- migrated from profile.json, kind not yet known
                )),
    text        TEXT NOT NULL,              -- one short claim, third person, no quotes
    concept     TEXT,                       -- required for milestone; optional for can_do and struggle
    basis       TEXT NOT NULL CHECK (basis IN ('stated', 'observed', 'inferred')),
    written_by  TEXT NOT NULL CHECK (written_by IN ('pass', 'learner')),
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    retired_at  TEXT,                       -- set by UPDATE (old text) or by the pass's DELETE
    replaced_by TEXT REFERENCES facts(id)
);

CREATE TABLE fact_evidence (
    fact_id     TEXT NOT NULL REFERENCES facts(id) ON DELETE CASCADE,
    session_id  TEXT NOT NULL REFERENCES sessions(id),
    turn_id     TEXT REFERENCES turns(id),
    artifact_id TEXT REFERENCES artifacts(id),  -- a quiz or whiteboard
    PRIMARY KEY (fact_id, session_id, turn_id, artifact_id)
);

CREATE TABLE profile_passes (
    id           TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL REFERENCES sessions(id),
    trigger      TEXT NOT NULL CHECK (trigger IN ('checkpoint', 'end')),
    status       TEXT NOT NULL CHECK (status IN ('running', 'stored', 'no_change', 'failed')),
    error        TEXT,                      -- short reason, never learner text
    last_turn_id TEXT REFERENCES turns(id), -- newest turn this run read
    changes_json TEXT,                      -- accepted and refused changes, for the learner view and debugging
    started_at   TEXT NOT NULL,
    finished_at  TEXT
);
```

Notes on the choices:

- **`basis` instead of a number for confidence.** A model's self-reported number is hard to check, and nothing in Polaris would act on 0.7 versus 0.8. `basis` can be checked:
  - `stated`: the learner said it.
  - `observed`: a graded quiz or a drawing shows it.
  - `inferred`: the pass read it between the lines.

  The view can show it, and the turn prompt can order by it.
- **Keep history with `retired_at`/`replaced_by`, as Zep does (source 3).** An UPDATE retires the old row and links it to the new one. The view can then show "changed after session X", and a bad pass can be undone. The teaching prompt reads only rows where `retired_at IS NULL`.
- **Forgetting is a hard delete.** When the learner removes a fact, the row, its evidence, and every older version linked by `replaced_by` are deleted. A retired row is history, but a forgotten fact must leave no copy.
- **Migration.** Each string in `profile.json` becomes a row with:
  - `kind = 'unsorted'`, `basis = 'inferred'`, `written_by = 'pass'`,
  - no evidence,
  - `created_at` set to the migration time.

  The next pass is asked to sort unsorted facts by UPDATE into a real kind. The file is renamed, not deleted, after a successful migration.
- **Teaching changes.** `Profile` stops being `tuple[str, ...]`. `format_facts` groups facts by kind in this order: goal, taught, struggle, can_do, milestone.

The change the pass returns (replaces `CHANGE_SCHEMA`):

```json
{
  "changes": [
    {
      "action": "ADD | UPDATE | DELETE | IGNORE",
      "id": "F3",                 // required for UPDATE, DELETE, IGNORE; absent for ADD
      "kind": "struggle",         // required for ADD; optional on UPDATE (to sort an unsorted fact)
      "text": "Mixes up the numerator and denominator when adding fractions",
      "concept": "adding fractions",
      "basis": "observed",
      "evidence": ["T4", "Q1"],  // short ids of turns and artifacts shown in the input
      "reason": "Picked 3/8 for 1/4 + 1/8 in Q1 and said so in T4"
    }
  ]
}
```

Code checks every change before any write. A refused change is recorded in `changes_json` with its reason, and nothing is appended in its place.

- The action is one of the four.
- An `id` names a fact shown in the input. An `evidence` id names a turn or artifact shown in the input.
- A `milestone` needs `concept` and at least one quiz in `evidence`. That quiz has been graded, and every question on that concept in it was answered correctly. Until questions carry a concept tag, "on that concept" means the questions the pass names in `reason`, and code checks those were correct.
- The pass may not UPDATE or DELETE a fact with `written_by = 'learner'`. A change that would contradict one is recorded as refused.
- An ADD whose text, normalized for case, spaces and punctuation, equals an active fact of the same kind becomes IGNORE. This is a cheap backstop. Rewording is handled by C.

## 7. Pass inputs and prompt

### Inputs

Both triggers use the same input. The checkpoint pass also gets the newest learner message, which has no reply yet.

1. **Active facts**, each as `F<n> [kind, basis, written_by, updated <date>] text`.
2. **New turns**, each as `T<n>`, with the learner text and the reply text. Only turns after `last_turn_id` of the last stored run for this session.
3. **Quizzes in those turns**, each as `Q<n>`:
   - title and score,
   - each question with the learner's choice, whether it was correct, and the correct choice.

   This is server side only. QZ-03 is about the browser and still holds.
4. **Whiteboards in those turns**, each as `W<n>`:
   - who drew it,
   - the text description (WB-10),
   - the learner's comments (WB-02),
   - the part they pointed at and asked about (WB-08),
   - whether it was a simpler redraw (WB-11, `simplifies`), and how many times the learner asked for one.
5. **Animation jobs** requested in those turns, title only.

`ChatService._turns` already loads most of this. The change is in `session_prompt`, plus the extra quiz fields.

### Prompt outline

This replaces `profile_pass_prompt`. The words are a draft; the eval set below is the check.

- **What you do.** Read one Polaris session and the profile. Return changes that make the profile true now. Do not teach, draw, or create a quiz.
- **What a fact is.**
  - One short claim about the learner, in the third person, under 20 words.
  - It is useful for teaching them later.
  - Pick one kind: goal, taught, can_do, struggle, milestone.
- **Store these:**
  - the goal (subject, course, exam, deadline),
  - how they want to be taught (pace, examples, drawings, step by step, no questions first),
  - what they showed they can do,
  - a specific struggle, naming the concept and the mistake,
  - milestones backed by a quiz.
- **Never store these:**
  - passing moods or states ("tired today", "bored"),
  - health, religion, politics, sexuality, money, or details about other people, unless the learner states it themselves *and* asks Polaris to teach with it in mind; in that case basis is `stated`,
  - anything the learner asked Polaris not to remember,
  - what the reply taught, unless the learner showed they understood it,
  - guesses from one slip. A single wrong answer is a struggle only if the learner's own words or a second mistake back it.
- **Prefer UPDATE to ADD.** If a stored fact is about the same thing, UPDATE it by id, even if worded differently. Never ADD a reworded copy. IGNORE a repeat.
- **DELETE** a fact when the session shows it is no longer true. For example, a struggle the learner now handles correctly in a quiz. Cite the evidence.
- **Milestone.** Only with a quiz id in evidence, and only for a concept whose questions in that quiz were all correct.
- **Learner-written facts.** Do not change or delete them.
- **Unsorted facts.** Give each one a kind with UPDATE when the session makes the kind clear.
- **Budget.** When a kind has more than its budget of active facts (section 8), merge overlapping ones. UPDATE the one you keep, DELETE the rest, and keep their evidence.
- **Evidence.** Every change cites the turn, quiz or whiteboard ids it rests on.

### Eval set (the check for the prompt)

Each case is a stored session plus profile and an expected set of changes. Each needs a case:
- the PR-08 reworded repeat,
- a contradiction that should UPDATE,
- a struggle a quiz has now cleared, which should DELETE,
- a passing mood, which should store nothing,
- a sensitive detail mentioned in passing, which should store nothing,
- a milestone claimed in chat without a quiz, which should be refused,
- a milestone with a quiz, which should be stored,
- three simpler-drawing requests, which should store a taught fact about fewer parts,
- the first-session "just start" message, which should store a taught fact.

## 8. Learner view and turn selection

### The profile screen

Opened from the session list, as "What Polaris knows about you". It uses the existing `GET /api/profile`, which grows to return typed facts, plus three new calls: edit, remove, and add. It follows the polaris-design system and meets WCAG AA.

- **Grouped by kind**, in the same order as the turn prompt. Each group heading is plain words: "Your goal", "How you like to learn", "Where you get stuck", "What you can do", "What you have understood". An empty group says what Polaris will ask for.
- **Each fact shows:**
  - its text,
  - where it came from: "you said this", "from a quiz", or "Polaris's guess", which is `basis` in plain words,
  - a link to the session or quiz it came from,
  - when it last changed.
- **Edit.** The learner can rewrite a fact. It becomes `written_by = 'learner'` and `basis = 'stated'`.
- **Remove.** The learner can remove a fact, after one confirmation. It is a hard delete (section 6). The screen says plainly that the session it came from is kept, and that the fact will not come back from that session.
- **Add.** The learner can add a fact in any group except milestones, which need quiz evidence.
- **What changed last time.** A short list of what the latest pass did ("Added 2, changed 1"), from `profile_passes.changes_json`.
- **When a pass failed.** A line says Polaris could not update the profile from a named session, with a Retry button. The same line appears once at the top of the session list until the retry succeeds.

### What the turn prompt carries

`format_facts` keeps PR-01: the profile is read before every reply. It no longer writes every fact. It writes, in this order, until a fixed character budget is used:
1. all `goal` facts,
2. all `taught` facts,
3. `struggle` facts, newest first,
4. `can_do` and `milestone` facts, newest first.

Every kind also has a count budget, for example: goal 3, taught 8, struggle 10, can_do 15, milestone 30. When a kind goes over its count, the next pass merges facts in it. So the prompt stays bounded without an embedding index. Selection is done in code and gives the same result every time, so a scenario can check it.

Choosing facts by topic needs a concept on each fact and a concept guessed from the learner's text. That is left for later. Recency plus merging is enough while one learner's profile is small.

## 9. Draft rules and scenarios

These are written in the style of `docs/features/profile.md`. They are proposals, and are not applied to profile.md. "Changed" means the wording of a rule in force changes. "New" means a new id.

### Proposed glossary terms

| Term | Proposed meaning | Avoid |
|---|---|---|
| **Goal** | The subject, course, exam, or deadline the learner is working toward. A goal is stored as a fact on the profile. | objective, target, plan |
| **Concept** | One idea the learner can understand or not, such as "adding fractions". A milestone and a quiz question each name one. (The glossary already uses the word in **Milestone** without defining it.) | skill, topic, knowledge component |
| **Evidence** | The session, turn, quiz, or whiteboard a fact rests on. | source, citation, provenance |
| **Profile pass** | The separate model that reads a session and sends fact changes. It runs when a session ends, and as a checkpoint while the profile is empty. It never teaches. | writer, memory agent, extractor |

The **Profile** entry would change from "stored as facts: how they want to be taught, what they can already do, where they struggle, and the milestones they have reached" to start with "their goal, how they want to be taught, ...".

### Rules

```
PR-01  The profile is read before every reply.                                   (unchanged)
PR-02  When the profile is empty, the conversation fills it before any teaching.  (unchanged wording;
       the checkpoint pass, PR-09, is how it fills during the session)
PR-03  One profile is shared by every session.                                   (unchanged)
PR-04  The teaching agent does not write the profile. Only the profile pass       (changed)
       and the learner write it.
PR-05  When a session ends (CH-05), the profile pass reads the turns of that      (changed)
       session it has not read before. A later ending of the same session reads
       only the turns since.
PR-06  A milestone needs a graded quiz as evidence, in which every question on    (changed)
       that concept was answered correctly. Code checks the quiz, not the model.
PR-07  The profile pass sends fact changes as ADD, UPDATE, DELETE, or IGNORE.     (changed)
       UPDATE, DELETE, and IGNORE name a stored fact by its id. A change that
       names no stored fact is refused and nothing is added in its place.
PR-08  A fact already stored is not added again, even in other words. A repeat    (changed)
       is UPDATE or IGNORE.
PR-09  While the profile is empty, the profile pass runs on the turns so far      (new; replaces decision 0005)
       before each reply after the first. If it stores facts, that reply teaches.
PR-10  Every fact has one kind: goal, how they want to be taught, what they can   (new)
       do, where they struggle, or milestone.
PR-11  Every fact records its evidence, when it was written and last changed,     (new)
       whether the learner stated it, a quiz or drawing showed it, or the pass
       inferred it, and whether the learner wrote it.
PR-12  The profile pass reads the quizzes, whiteboards, and requests for a        (new)
       simpler drawing in the turns it reads, not only the text.
PR-13  The profile pass does not store a passing mood, or health, religion,       (new)
       politics, sexuality, money, or details about other people, unless the
       learner states it and asks Polaris to teach with it in mind.
PR-14  A failed profile pass is recorded. The learner is told which session it    (new)
       was, and can retry. Polaris retries it when it starts and when a session
       starts.
PR-15  The learner can see every fact on the profile, grouped by kind, with its    (new)
       evidence.
PR-16  The learner can edit, remove, or add a fact. A removed fact is deleted     (new)
       with its history. The profile pass does not change or delete a fact the
       learner wrote.
PR-17  The turn prompt carries the goal and how they want to be taught first,     (new)
       then the newest other facts, within a fixed budget. When a kind is over
       its budget, the next profile pass merges facts in it.
PR-18  While the profile has no goal, the reply asks for it along with what else   (new)
       is missing.
```

### Scenarios

```
Scenario: a first session teaches once the learner has answered  [PR-02, PR-04, PR-09]
  Given a learner with an empty profile
  And the first reply asked for their goal, how they want to be taught, and where they struggle
  When they answer in their next message
  Then the profile pass runs on the turns so far before the reply
  And the profile stores those facts
  And the reply teaches with those facts in hand
  And the teaching agent wrote no fact

Scenario: a checkpoint that stores nothing keeps asking  [PR-02, PR-09]
  Given a learner with an empty profile
  And the first reply asked for what the profile is missing
  When they send a message that answers none of it
  Then the profile pass stores no fact
  And the reply asks again
  And it does not teach the topic yet

Scenario: "just start" is an answer  [PR-09, PR-10]
  Given a learner with an empty profile
  And the first reply asked for what the profile is missing
  When they reply "skip the questions, just start"
  Then the profile stores a fact of kind "how they want to be taught"
  And the reply teaches

Scenario: a reworded repeat is not stored twice  [PR-07, PR-08]
  Given the profile stores the fact "Struggles with math" as F1
  When a later session has the learner say "I suck at math"
  Then the profile pass sends UPDATE F1 or IGNORE F1
  And the profile holds one fact about struggling with math

Scenario: an update that names no stored fact is refused  [PR-07]
  Given the profile stores facts F1 and F2
  When the profile pass sends UPDATE F9
  Then the change is refused and recorded
  And no fact is added

Scenario: a milestone without a quiz is refused  [PR-06]
  Given a session in which the learner says "I get fractions now"
  And no quiz in that session
  When the profile pass sends ADD of a milestone for "adding fractions"
  Then the change is refused
  And the profile has no milestone for "adding fractions"

Scenario: a milestone with a quiz is stored  [PR-06, PR-11]
  Given a graded quiz in which every question on "adding fractions" was correct
  When the profile pass sends ADD of a milestone for "adding fractions" citing that quiz
  Then the profile stores the milestone
  And its evidence names that quiz and its session

Scenario: the pass sees which wrong choice was picked  [PR-12]
  Given a graded quiz in which the learner chose "3/8" for 1/4 + 1/8
  When the session ends
  Then the profile pass input names that question, the chosen choice, and the correct one

Scenario: asking for simpler drawings is read  [PR-12]
  Given a session in which the learner asked for a simpler version of three whiteboards
  When the session ends
  Then the profile pass input shows the three simpler requests

Scenario: a passing mood is not stored  [PR-13]
  Given a session in which the learner says "I'm exhausted today"
  When the session ends
  Then the profile has no fact about being exhausted

Scenario: a failed pass is not silent  [PR-14]
  Given the profile pass fails when a session ends
  When the learner opens the session list
  Then they are told the profile was not updated from that session
  And they can retry
  And a run with status "failed" is recorded for that session

Scenario: a later ending reads only new turns  [PR-05]
  Given a session that ended and whose turns the profile pass read
  When the learner reopens it, sends one message, and leaves
  Then the profile pass reads only that one new turn

Scenario: a removed fact does not come back  [PR-05, PR-16]
  Given the profile stores a fact from session S
  And the learner removes it
  When the learner reopens S, sends a message unrelated to that fact, and leaves
  Then the profile does not hold that fact

Scenario: the pass does not overwrite the learner  [PR-16]
  Given the learner edited a fact to "Prefers drawings before formulas"
  When a later profile pass sends UPDATE or DELETE for that fact
  Then the change is refused
  And the fact still reads "Prefers drawings before formulas"

Scenario: the learner sees where a fact came from  [PR-11, PR-15]
  Given the profile stores a struggle fact with a quiz as evidence
  When the learner opens the profile screen
  Then the fact is under "Where you get stuck"
  And it says it came from a quiz
  And it links to that quiz's session

Scenario: the turn prompt stays within budget  [PR-01, PR-17]
  Given a profile with more facts than the budget allows
  When the learner sends a message
  Then the turn prompt carries every goal fact and every "how they want to be taught" fact
  And it carries no more facts than the budget allows

Scenario: the goal is asked for  [PR-18]
  Given a profile with facts but no goal
  When the learner sends a message
  Then the reply asks what they are working toward
```

The PR-08 scenario in profile.md ("I suck at math" stored, the same string seen again) still passes under these rules. The reworded scenario above is the stronger check.

## 10. Open questions

1. **Budgets.** What character budget and count budgets suit the Haiku pass and the teaching prompt? Measure them against real profiles after step 1.
2. **Concept tags.** Should `create_quiz` require a concept per question? This touches QZ rules and quiz.md, which are out of scope here.
3. **A session that writes nothing.** Should there be one, as in ChatGPT's temporary chat or Claude's incognito? Not needed for one local learner. It is worth deciding before hosting.
4. **Checkpoint limit.** Should the checkpoint pass run on every reply while the profile is empty, or at most N times per session? This note says every reply. Its cost is one Haiku call per reply, and only in that state.
5. **Removed facts and history.** Hard delete is the safe default. If the learner wants an undo, it would have to be short-lived and kept only while Polaris is running, never written to disk.
