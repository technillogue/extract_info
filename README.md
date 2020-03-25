Extract names and contact information from bilingual, ungrammatical sentence fragments.

Motivating use case: advertising to clients who are similar to past clients on Facebook is easier and more effective than developing your own targetting, but requires you to have your client's contact info. This tool allows you to do that with unstructured records.

Features:
- Clean, mostly functional code with comprehensive type annotations and integration testing
- Infers needed number of names in each line based on number of emails and phone numbers (if you have multiple contact people per sale). >90% accurate by this metric.
- Tries to find a consensus between Google Cloud Knowledge Graph Named Entity Recognition (which has fewer false positives, but only works well for English) and NLTK.ne_chunk (which usually works, but has more false positives)
- Caches expensive/slow Google and NLTK calls between runs, but keeps cache files small even with long record entries
- Combinatorially tries various pre- and post- processing strategies
- Careful metaprograming makes it trivial to add more NER algorithims or pre-/post- processors 
- Includes a feature for labeling data for test cases, and updating labels mid-test if desired
- The algorithim to try combinations of strategies corresponds to a deterministic finate state automata. The tests generate a graph for this dFSA, trace the order in which strategies are tries, and use this to verify that the strategies were tried in the right order, catching some false positives and inefficient ways of getting to the right answer.
