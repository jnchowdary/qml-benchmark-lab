# References

**What is and is not verified here.** The identifiers below — arXiv numbers,
DOIs, version dates and the source hashes in §2.6 — are recorded in this
repository and checkable against it. Titles, journals and author lists are taken
from the citation block in `README.md`, which is this repository's only
bibliographic record of them; they are **not** independently transcribed from the
sources that were read, and anyone preparing this for submission should check
them against the identifiers.

Two corrections to an earlier version of this section, both recorded rather than
quietly applied. It claimed that titles and published locators were not recorded
in this repository at all, and supplied none for [1] on that basis. That was
wrong: `README.md` records them, and the claim was made without searching for
them. And this project has dropped a co-author once — an earlier internal
document named two authors of [2] where there are three, corrected in
`docs/florez-ablan-code-check.md` C1 — which is why the paragraph above says
where each field came from instead of presenting all of them as equally checked.

**One unresolved inconsistency.** This repository spells the first author of [2]
both as **Flórez-Ablan**, in `README.md`, and as **Flórez Ablan**, in §2 of this
paper. The hyphenated form is used below because `README.md` is the only
bibliographic record here, and **it has not been verified against the published
author listing.** One of the two forms is wrong and this paper does not know
which.

---

**[1] Huang et al. (2021).** *Power of data in quantum machine learning.*
Nature Communications 12:2631. arXiv:2011.01938.

Read from the e-print LaTeX, not from a rendering. Archive SHA-256
`b510654c6628…`, `maintext.tex` SHA-256 `ceded212c4b0…` (§2.6). This is the
source of Equation (5), of Appendix D's training objective, and of Appendix F's
regularised forms F19 and F20 together with the g_tra ≤ 0.045 selection rule.
§2.2 derives the orientation of F19 from its λ → 0 limit; §2.3 records that the
source is internally inconsistent on whether the threshold is `≤` or `<`.

**[2] Flórez-Ablan, Roth and Schnabel (2025).** *On the similarity of
bandwidth-tuned quantum kernels and classical kernels.* Quantum Science and
Technology, DOI 10.1088/2058-9565/ade7ad. arXiv:2503.05602, v1 7 March 2025,
v3 28 July 2025.

Read from the e-print LaTeX. Archive SHA-256 `7ce99d754ecc…`, `main.tex`
SHA-256 `1903926fe4b5…` (§2.6). §2.4 establishes from their equation (line 210),
their argument assignment (line 213) and their released code that the quantity
they compare against √N is the reverse of the screening quantity, and that their
paper, equation and implementation are mutually consistent. §2.4 also records
that their pipeline computes `g_tra` and never compares it to anything, and that
their λ = 1/(2C) with C ∈ [32, 1024] (line 393) substitutes a C-derived λ for
the selection rule in [1]. **No claim in this paper asserts an error in their
conclusions.**

**[3] Kakavand, Strohmeyer and Schlotter (2026).** *Benchmarking Quantum Kernel
SVMs Against Classical Baselines on Tabular Data.* arXiv:2604.18837. Deposit:
DOI 10.5281/zenodo.19197916.

The only foreign records this study's audit was run against, in week 6, through
`scripts/foreign/kakavand_adapter.py`. §5.6 reports what that run produced — one
measurement and eight refusals — and states that **it found no defect in their
work and was not looking for one.** §5.6 also records that an earlier paragraph
of this project's asserted things about this deposit from the manuscript alone,
of which six of seven claims were wrong or misleading once the deposit was read.
Their statistical treatment is described in `docs/audit-protocol.md` as more
careful than this project's own registered design at the equivalent stage.

**[4] Tekeli (2026).** arXiv:2608.29422, 29 August 2026. **No title is recorded
for this source anywhere in this repository**, so none is given here.

Derives in closed form a property of the ZZ feature map that this project
checked numerically in `scripts/tekeli_check.py`; the check and its boundary are
reported in `docs/week-06-report.md`. Used as a cross-check on this study's own
kernels, not as a source for any claim about the geometric difference.

---

**Datasets.** Sources, licences and checksums are in `data/README.md`. The
customer-churn dataset carries a `copyright-authors` licence and **is not
redistributed by this repository**; the credit-card fraud dataset likewise is
referenced rather than republished. Neither appears in version control.

**This study's own artefacts.** `https://github.com/jnchowdary/qml-benchmark-lab`.
§4.7 and §7 state what a reader can and cannot verify from it: the scripts,
records and data checksums in full, and **not** the binding between a stored
result record and the code that produced it.
