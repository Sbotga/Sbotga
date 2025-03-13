from rapidfuzz import fuzz, process
from rapidfuzz.distance import Levenshtein
import unicodedata
import re
from functools import lru_cache


@lru_cache(None)
def preprocess(text):
    # Normalize unicode characters and convert to ASCII
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
    text = text.lower().strip()
    STAR_LIKE = (
        r"[\u2600-\u26FF]"  # Miscellaneous Symbols (includes stars like ★, ☆, ✩, ✪)
        r"|[\U0001F300-\U0001F5FF]"  # Miscellaneous Symbols and Pictographs (includes 🌟)
    )

    text = re.sub(STAR_LIKE, " ", text)
    return text


def fuzzy_match_to_dict_key_partial(
    input_str: str, dictionary: dict, sensitivity: float = 0.6
) -> str | None:
    """
    Fuzzy match input_str to the closest key in the dictionary, prioritizing partial matches and small edit distances.

    Args:
        input_str (str): The string to match.
        dictionary (dict): The dictionary to match against.
        sensitivity (float): Minimum score threshold for a valid match (0-1).

    Returns:
        str | None: Best match key if score >= sensitivity, otherwise None.
    """
    if not dictionary:
        return None

    sensitivity = sensitivity * 100  # Convert to 0-100 scale
    input_str = preprocess(input_str)
    preprocessed_keys = {key: preprocess(key) for key in dictionary.keys()}

    best_match = None
    best_score = 0

    for original_key, preprocessed_key in preprocessed_keys.items():
        # Calculate similarity and edit distance
        similarity = fuzz.token_set_ratio(input_str, preprocessed_key)
        edit_distance = Levenshtein.distance(input_str, preprocessed_key)

        # Penalize scores for large edit distances (>5 edits)
        if edit_distance > 5:
            similarity -= (edit_distance - 5) * 5

        # Favor shorter edit distances if scores are tied
        if similarity > best_score or (
            similarity == best_score
            and edit_distance < Levenshtein.distance(input_str, best_match or "")
        ):
            if similarity >= sensitivity:
                best_match = original_key
                best_score = similarity

    return best_match


def fuzzy_match_to_dict_key(
    input_str, dictionary, sensitivity: float = 0.6, ratio: bool = True
):
    """
    Fuzzy match input_str to the closest key in the dictionary.

    Args:
        input_str (str): The string to match.
        dictionary (dict): The dictionary to match against.
        sensitivity (float): Minimum score threshold for a valid match (0-1).
        ratio (bool): Use default ratio? If False, uses weighted ratio.

    Returns:
        str | None: Best match key if score >= sensitivity, otherwise None.
    """
    sensitivity = sensitivity * 100
    if not dictionary:
        return None

    # Preprocess input and dictionary keys
    input_str = preprocess(input_str)
    keys = [preprocess(key) for key in dictionary.keys()]

    # Perform fuzzy matching
    result = process.extractOne(
        input_str,
        keys,
        scorer=fuzz.ratio if ratio else fuzz.WRatio,
        processor=None,  # Already preprocessed
    )

    if result and result[1] >= sensitivity:
        # Find the original key from the preprocessed match
        matched_index = keys.index(result[0])
        return list(dictionary.keys())[matched_index]

    return None
