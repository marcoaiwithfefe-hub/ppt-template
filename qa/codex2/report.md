Reviewed c49de09 against f6c30a9 through pinned code, tests and saved evidence. No tests rerun, new probes constructed or files changed. All citations refer to c49de09.

F15 | MAJOR | tests/oracle.py:275-276,302-304
C3 relationship preservation check became weaker. F11 fix replaces canonical XML comparison with normalized relationship sets. rels_of normalizes targets and discards ordering through dictionary construction (tests/oracle.py:45-57). Reordered relationships or rewritten absolute/relative targets can therefore pass despite changed canonical XML. Dedicated byte-identity test covers only one fixture's master/layout relationships (tests/test_c3_c6_package.py:39-46), leaving other outputs without equivalent protection. Fix: remove only authorized dead-slide Relationship elements from input XML, then compare remaining relationship XML canonically. Likelihood: ordinary serializer changes can trigger this gap. No application corruption demonstrated; finding concerns verification behavior.

New findings only: BLOCKER 0, MAJOR 1, MINOR 0, NICE 0.
Ship readiness: 7/10 within this round's scope. Remaining concerns are F3's incomplete consistency check, F10's final-download coverage, F15 and evidence gaps below.

Confidence: 9/10 on inspected code and test conclusions. F3's downstream allocation consequence remains unknown without dependency inspection or a new probe.

Need from you: nothing needed.
