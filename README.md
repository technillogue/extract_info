Extract names and contact information from multilingual, ungrammatical, and unstructured records. 

- Try to find a fuzzy consensus between Google Cloud Knowledge Graph Named Entity Recognition (NER) (fewer false positives, place name/human name disambiguation, but only works well for English) and NLTK.ne_chunk (which usually works for e.g. Russian or other langauges, but has more false positives)
- Infer expected number of names in each record based on contact information regexes. >90% accuracy by this metric for the motivating dataset.
- Caches expensive/slow Google and NLTK calls between runs, but keeps cache files small even with long record entries
- Explore the solution space of combining various preprocessing steps / NER backends / merge steps / filter steps while following heuristics to go from least false positives and least cost -> most false positives at bounded cost to achieve said number.
- Easy to add more named more NER backends and other strategies for each stage. Model an arbitrary number of extraction stages.
     - Desired additions: whatever aws' NRE is, some of the more aggressively mathy expectation maximization and data linkage algorithms
- Clean, almost purely functional code with comprehensive type annotations
- Integration tests verify heuristics are followed correctly and provide labeled/inferred accuracy
