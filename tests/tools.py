from typing import Dict, List#, Iterator
import extract_names

def show_all_extractions(text: str) -> Dict[str, List[List[str]]]:
    return {
        "google_extractions":
            [extractor(text) for extractor in extract_names.GOOGLE_EXTRACTORS],
        "crude_extractions":
            [extractor(text) for extractor in extract_names.CRUDE_EXTRACTORS]
    }
 
    # consensuses: Iterator[Names] = filter(
    #     min_criteria,
    #     map(fuzzy_intersect, product(google_extractions, crude_extractions))
    # )
    # refined_consensuses: Iterator[Names] = soft_filter(
    #     lambda consensus: min_names <= len(consensus) <= max_names,
    #     (
    #         refine(consensus)
    #         for consensus, refine in product(consensuses, REFINERS)
    #     )
    # )



