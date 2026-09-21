"""Retrieval evaluation package for DocuMind.

This package builds the golden-question set, computes hand-written retrieval
metrics, and runs a mode over the set to produce committed result files under
``eval/results/``. It is deliberately plain Python so every metric is
explainable in an interview and independent of any evaluation framework.
"""