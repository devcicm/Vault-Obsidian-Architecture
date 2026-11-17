<!-- propiedad: CARLOS IVAN CM · revisión: manual -->

# Candidate-bound release evidence

The release workflow requires each governance evidence document to mention
the complete certified `release_candidate.product_sha` as a separate hexadecimal
token. A file's existence, an abbreviated SHA, or evidence for another candidate
does not satisfy this check. The SHA must be the canonical lowercase form that
`git rev-parse` prints (40 hex digits, `[0-9a-f]`): an uppercase or SHA-256 form
is rejected on purpose, so evidence cannot drift from the commit identity git
reports. References must remain under the existing `audits/`
reference convention; unreadable or invalid UTF-8 documents fail the gate.

The existing `qa_verdict_ref` exceptions `PENDIENTE` and
`OMITIDO_POR_PROPIETARIO` remain unchanged under DEC-06. This check does not
ratify a policy, authorize a release, or prove that a document's claims are true.
All other release authorization, CI, ancestry, tree and QG checks still apply.

Historical evidence is not rewritten to pass this check. A new candidate needs
its own applicable evidence. Local regression tests execute the workflow's Python
gate with synthetic documents and stub only the unrelated git certification
results; they do not publish a release or substitute for a CI run.
