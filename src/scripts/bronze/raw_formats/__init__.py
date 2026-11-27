"""Descriptions of the raw file formats bronze reads: constants only, no logic.

One module per format that has something to describe (spellings, field types,
naming patterns). Parquet describes itself, so it has none. The reading code is in
``scripts.bronze.readers`` and refers to these as ``<format>.<NAME>``. When a source
changes how it writes its files (a new header spelling, say), the edit belongs here.
"""
