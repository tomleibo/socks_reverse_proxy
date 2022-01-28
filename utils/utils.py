from collections import defaultdict
from typing import List
import re


def merge_dicts(names: List[str], *dicts):
    if len(names) is not len(dicts):
        raise Exception("names and dicts should be of same length")
    result = defaultdict(dict)
    for name, data_dict in zip(names, dicts):
        for key, value in data_dict.items():
            result[key][name] = value
    return result


def regex_check(reg: str, items: List[str]):
    pattern = None
    if reg == "all":
        pattern = '^[A-Za-z0-9]*'
    if reg == "numbers":
        pattern = '^[0-9]*'
    if reg == "letters":
        pattern = '^[A-Za-z]*'
    ans_list = []
    for item in items:
        ans_list.append(bool(re.search(pattern, item)))
    return all(ans_list)
