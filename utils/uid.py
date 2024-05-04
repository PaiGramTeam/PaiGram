import re


def mask_number(number):
    number_str = str(number)
    masked_number = None
    if len(number_str) == 9:
        masked_number = re.sub(r"(\d{2})(\d{4})(\d{3})", r"\1****\3", number_str)
    if len(number_str) == 10:
        masked_number = re.sub(r"(\d{3})(\d{4})(\d{3})", r"\1****\3", number_str)
    if masked_number:
        return masked_number
    return "Invalid input"
