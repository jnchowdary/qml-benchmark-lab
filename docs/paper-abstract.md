# Abstract

Can a cheap pre-training quantity tell a practitioner not to bother with a
quantum kernel? We pre-registered that question on imbalanced business tabular
data, customer churn and credit-card fraud, across 360 units: three mappings,
five qubit counts, three training sizes, four quantum settings, twenty
seeds, statevector simulation only.

Neither primary cell shows a quantum advantage. On churn both endpoints reject
*against* the quantum kernel, a median deficit of 0.0659 normAP, clearing its
true minimum detectable effect by 1.31x. On fraud the test does not reject and is
reported as a bound: an advantage above 0.0063 normAP is excluded at 80% power.

For the geometric difference the registered rule returned **no verdict**, because
no regularisation column is free of ceiling breaches. That is the rule declining
to speak, not a finding that no relationship exists: at the largest
regularisation the null *is* rejected in the predicted direction, yet accounts
for 2.9% of rank variance and reverses sign across the sweep, so the quantity is
not usable as the screen it is offered as. A third rule, the source's own and one no
one had run, selects no parameter at all on 76.5% of units, returning nothing to
test.

Seventeen deviation records govern; the recovered pre-rewrite history is now
published, so every stored commit identifier resolves.
