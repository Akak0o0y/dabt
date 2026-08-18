# Licensing

Copyright © 2026 Abdulaziz Al-Dhamri.

Dabt is dual-licensed. Rights in it are granted only under one of the two
licences described below; no other rights are granted by implication.

## 1. Open source — GNU AGPL-3.0

The default licence is the **GNU Affero General Public License, version 3**, in
[`LICENSE`](LICENSE). You may read, run, modify and redistribute Dabt under its
terms at no cost.

The clause that matters for this project is **AGPL section 13**. If you run a
modified version of Dabt so that users interact with it **over a network** —
which is how a policy gate is normally deployed — you must offer those users the
complete corresponding source of your modified version, under the AGPL.

In practice that means a bank, fintech, government-adjacent entity or PaaS
embedding Dabt into a hosted product would have to publish the source of the
system it is embedded in. For most organisations that is not acceptable, which
is what section 2 is for.

## 2. Commercial licence

If you want to use Dabt in a product or service **without** the AGPL's source
disclosure obligations, a commercial licence is available. It is intended for:

- SaaS and PaaS providers embedding the gate into a hosted platform
- Banks, fintechs and regulated entities deploying it internally without
  publishing their stack
- Vendors redistributing it inside a closed-source product
- Anyone needing warranty, indemnity or support terms the AGPL does not provide

Commercial terms are negotiated per engagement and may include a reviewed and
signed-off compliance map, which the open-source distribution deliberately does
not provide (see §4).

**To enquire:** email Abdulaziz Al-Dhamri at <abdulazizaldhamri@gmail.com>,
or open an issue at `github.com/Akak0o0y/gulf-agent-compliance-layer`.

## 3. Contributions

By contributing you agree that your contribution is licensed under the AGPL-3.0.
If a contributor licence agreement becomes necessary to keep the commercial
option viable, it will be added before contributions are accepted from outside
the copyright holder.

## 4. What these licences do **not** cover

This is the part most likely to be misread, so it is stated plainly.

**The regulatory texts are not ours to license.** The compliance map quotes
verbatim from publications of SDAIA, the National Data Management Office, the
National Cybersecurity Authority and the Saudi Central Bank. Those quotations are
included for citation and traceability. Neither the AGPL nor a commercial licence
grants you any right in those source documents; your rights in them come from
their publishers, not from us.

**No licence here makes any mapping authoritative.** Every rule, control mapping
and classification in this repository carries `confidence_level` and
`requires_legal_review: true`, and several are explicitly marked
`needs_verification`. Buying a commercial licence does not convert an engineering
artifact into a legal determination. A qualified Saudi legal or compliance
professional must review the applicable facts, entity context and source
regulations before any regulatory reliance.

**No warranty of compliance.** Dabt evaluates payloads and agent actions against
the rules currently in its map. It does not guarantee that a decision is lawful,
that detection is exhaustive, or that using it makes any organisation compliant
with PDPL, NDMO, NCA ECC-2:2024, SAMA CSF or anything else. The known limitations
are listed in `docs/superpowers/specs/`, and they are real.

## 5. History

Prior to this notice, `package.json` declared `"license": "MIT"` with no licence
file present. That declaration has been removed. This notice governs the project
from the commit that introduced it onward. Anyone who obtained a copy under the
earlier declaration should seek their own advice about what it granted; nothing
here attempts to revoke rights already granted, because a licence cannot be
retracted retrospectively.
