# Dabt Reference MCP Gate — Design Specification

**Date:** 18 August 2026
**Status:** Implemented
**Surface:** In-path enforcement harness over the existing Agent Action Gate API

> **Standing legal caveat.** Every regulatory mapping referenced here is an
> engineering artifact, not legal advice. Nothing here may be relied upon in a
> regulatory audit until a qualified Saudi legal or compliance professional has
> signed it off.

---

## 1. Purpose

The Agent Action Gate design (§8) deferred the reference proxy. Without it the
project had a decision API that answered correctly and nothing that sat in the
path of a real tool call, so the central claim — *an agent cannot act contrary
to the Kingdom's policy* — was demonstrated by argument rather than by
observation.

This is that piece: a stdio MCP server an agent attaches to instead of the real
one, which evaluates each `tools/call` before it executes and each result before
it is disclosed.

## 2. Generic by construction

The named integration target was CranL. The proxy carries no knowledge of it.

Which server is gated is `--server-id`, naming an entry in a validated tool
manifest, and `--manifest` loads manifests from anywhere on disk. Gating a new
organisation is therefore writing a YAML file, not forking `dabt_core`. The
`scaffold` command drafts that file from the upstream's own `tools/list`.

This required one change to existing code: `dabt_api/main.py` loaded manifests
only from its package directory, so the HTTP evaluation path could never gate a
customer's server. It now also reads `DABT_MANIFEST_DIRS`.

## 3. Architecture

```
proxy/dabt_proxy/
  outcome.py    domain types; no MCP wire types anywhere in the core
  adapter.py    MCP CallToolResult <-> the dict the engine gates
  policy.py     PolicyClient protocol; InProcess + Http implementations
  upstream.py   UpstreamClient protocol; stdio / HTTP / in-process targets
  gate.py       the decision flow. Pure: both collaborators injected
  server.py     MCP wiring, refusal rendering, audit sink
  config.py     startup validation
  scaffold.py   draft a manifest from a live server's tool list
```

`gate.py` performs no I/O. Every branch — denial, redaction, upstream failure,
uninspectable content — is reachable in a test without a subprocess or a socket,
which is why the interception guarantee is cheap to assert rather than expensive
to demonstrate.

## 4. Decisions

### 4.1 In-process policy evaluation by default

`todo.md` records that the subprocess lifecycle behind the FastAPI service is
unhardened, and the Action Gate design (§7) makes fail-closed a guarantee. Those
two facts together mean an HTTP-only proxy freezes the agent surface on the
policy service's first crash.

The default therefore imports `ActionEngine` directly: no socket, no subprocess,
so the gate cannot be defeated by making a service unavailable. `--policy-url`
switches to HTTP, because that is the pattern a production gateway copies.

Both transports parse the same payload shape — `ActionResult.to_dict()`, which
is also what FastAPI serialises — so they cannot drift in what they conclude.
`test_transports_agree` asserts this across three decision paths.

**This does not close the `server/dabt.ts` lifecycle item.** The proxy sidesteps
that dependency; it does not harden it. That todo remains open.

### 4.2 Bridging MCP's response shape

The engine gates response fields by manifest-declared name. MCP returns
`content: [ContentBlock]` plus optional `structuredContent`. Three cases:

| Upstream returned | Gated as | Consequence |
|---|---|---|
| `structuredContent` | that object | declared fields inspected; undeclared ones trip the engine's guard |
| text blocks only | `{"content": [...]}` | manifest may declare `content` as an inspected collection; otherwise REVIEW as an undeclared field |
| nothing | `{}` | nothing disclosed, so nothing withheld |

The third case matters: forcing `REVIEW` on an empty acknowledgement would make
the gate unusable for write tools that return no payload.

### 4.3 The mirrored-text trap

A server returning `structuredContent` normally also returns the same data
serialised as text, for clients predating structured output. **Substituting only
the redacted structure returns the masked value in one field and the original
secret in the other** — a proxy reporting a redaction it did not perform.

So when the engine rewrote anything, the text blocks are regenerated from the
released structure rather than passed through. When nothing was rewritten the
original blocks are returned untouched, so a clean call is a byte-for-byte
passthrough. Covered by `test_redacted_structure_is_not_leaked_through_the_mirrored_text_block`
in isolation and `test_gate_does_not_leak_the_secret_through_mirrored_text`
end to end.

### 4.4 Uninspectable content

A response carrying image or audio blocks cannot be scanned. It resolves to
`REVIEW`, labelled in both languages as a limit of the detectors rather than a
finding about the content. This is a capability limit stated by the proxy, not a
regulatory determination — the distinction is made explicit in the refusal text.

### 4.5 Upstream failure is not a policy decision

If the upstream fails after an `ALLOW`, the proxy cannot know whether the
operation took effect. It reports an upstream error saying exactly that. An
audit record that claimed otherwise would be false in the direction that matters.

### 4.6 Audit records carry no payload

Every decision is one JSON line to stderr (and optionally a file), recording the
decision, rule, citation, and finding *types* and element paths — never the
matched value. A gate whose log contains the secret it just refused has moved
the leak rather than closed it. This mirrors the Evidence Vault's discipline for
source documents.

`stdout` is MCP protocol framing. Nothing else is ever written there.

Records are written as UTF-8 bytes rather than through the stream's text layer.
`sys.stderr` uses `backslashreplace` on a console that cannot represent Arabic -
the Windows default - which turned half of every bilingual record into escape
sequences and dropped its guillemets. A record surviving only in English is not
the bilingual record this project claims to produce.

### 4.7 Startup refuses rather than degrades

An unknown `server_id`, a missing or doubled upstream, a malformed
`--upstream-env`, or an unloadable map is a startup failure with a message
naming the fix. A gate that starts misconfigured gates the wrong thing.

## 5. Scaffolding, and why a draft cannot permit anything

`scaffold` infers operation from verb prefixes, and roles from parameter naming
and JSON Schema shape. Every inference is a guess, and the generated file says so
on every affected line.

Every drafted entry is `needs_verification`. Because
`ACTION-DEFAULT-ALLOW-NO-FINDING` requires `tool_confidence: verified`, a
scaffolded manifest resolves every call to `REVIEW` until a human deliberately
raises an entry. An inaccurate draft therefore fails safe.
`test_a_drafted_manifest_holds_every_call` proves this through the engine rather
than by assertion.

## 6. Demonstrability

The packaged `cranl.yaml` is a reconstruction with every entry
`needs_verification`, so every call against it stops at the request leg with
`REVIEW`. That is a visible interception, but it cannot exercise the release,
redaction, or credential-withholding paths.

So the tests ship a fixture PaaS MCP server defined in this repository, with a
manifest that can honestly say `verified` — the claim "this tool returns a
connection string" is checkable by reading the file beside it. `demo/run_demo.py`
drives it through real subprocesses and pipes.

## 7. Testing

67 tests. Highlights:

| Test | Proves |
|---|---|
| `test_denied_call_never_reaches_upstream` | the fake upstream records zero calls |
| `test_declared_credential_is_withheld_after_the_write_completes` | §3.1 of the Action Gate design: the write stands, the secret does not pass |
| `test_clean_destructive_call_is_allowed` | the scope boundary holds |
| `test_unmasked_arguments_keep_their_type` | `replicas=3` does not become `"3"` |
| `test_collection_redacts_only_flagged_elements` | per-element redaction |
| `test_collection_classification_aggregates_to_maximum` | NDMO Principle 4 across elements |
| `test_a_failing_policy_service_blocks_the_call` | fail closed |
| `test_the_audit_record_does_not_contain_what_it_withheld` | §4.6 |
| `test_transports_agree` | one behaviour, two transports |
| `test_end_to_end.py` (8 tests) | the whole path over the real protocol |

## 8. Out of scope

Production-grade gateway plumbing. Agent identity. Operational blast radius.
Resources, prompts, and completions. Any framework beyond PDPL, NDMO, NCA ECC,
and SAMA CSF.
