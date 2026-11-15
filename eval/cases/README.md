# AI-reviewed evaluation cases

These are AI-drafted conversations with AI-assigned labels: 12 development
cases and 60 test cases. The user explicitly authorized AI labeling and live
evaluation. A fresh independent agent reviewed every turn against the shared
contracts, policy table, catalog and synthetic fixture data, then filled
`reply_type`, `risk_label` and `handoff_offered` on all chat and order-form
turns. These labels are not human-reviewed ground truth.

The review also checked the proposed gold sources, required strings, forbidden
strings and tool expectations. Repeating a handoff confirmation does not
require another `create_ticket` invocation: the existing ticket can be reused.
Its confirmation text remains checked. This does not relax the requirement
that a ticket is created only after confirmation and only once.

Handoff responses have no chat reply metadata; their three labels stay null.
API-timeout actions only toggle the scripted timeout and have no reply
expectation. The runner rejects incomplete chat and order-form labels before
making model calls.

Each JSONL line is one conversation. Its `turns` contain customer chat,
private order-form submissions, confirmed handoffs, or API-timeout toggles.
`documents`, when present, plants a policy record for a document-injection
case. Order contacts and addresses are synthetic fixtures from `data/`.

The test set follows the plan's ten-slice counts and contains 13 multi-turn
cases, including scripted form and handoff actions. Development covers all
ten slices with separate product SKUs and independently written questions.
Ten other SKUs are reserved for judge calibration. Gold label sources use
catalog SKUs and section identifiers; API and policy sources use the shared
source-ID format.

The six questions in [`handwritten_questions.md`](handwritten_questions.md)
appear verbatim once each in the test set. Despite that filename, those
questions were AI-written and committed after the alias table existed.
Keeping their wording satisfies the wrapping requirement, but their
provenance does not establish the plan's pre-alias, human-written holdout.

The fresh drafting agent read the issue, the Evaluation section of the plan,
the case loader, shared contracts, policy and template text, the six fixed
questions, catalog product records, and synthetic store/order/policy data.
The independent labeling agent used the same permitted evidence and reviewed
both case sets only through `eval.loader.load_cases`. Neither agent read
the alias table, assistant retrieval, prompts or safety modules, or handoff
implementation notes. No test question text was sent back to the
implementing agent.

Review and tune using development cases only. Keep test questions out of
prompts, rules, templates and the alias table. Runs against these cases may
be reported as evaluations against AI-reviewed expectations. Independent
human review can strengthen the labels, but does not change
question authorship or establish the missing pre-alias provenance. These
cases must not be described as a human-written holdout.
