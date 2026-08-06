"""The learning layer.

Three layers behind one interface, so replacing one never touches its callers:

  L1  scorer.py  deterministic outcome score      works from the first post
  L2  bandit.py  Thompson Sampling over arms      useful from ~25-30 matured posts
  L3  (later)    supervised uplift model          from ~100, feeds L2 as a prior

`engine.run_learning()` is the entry point. It scores, fits, ranks, and writes
everything the /learning dashboard reads.
"""
