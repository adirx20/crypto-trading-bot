

# Check that the text is a positive integer
def check_int_format(text: str) -> bool:

    if text == "":
        return True

    if all(x in "0123456789" for x in text):
        try:
            int(text)
            return True

        except ValueError:
            return False

    else:
        return False


# Check that the text is a positive floating number
def check_float_format(text: str) -> bool:
    print(text)

    if text == "":
        return True

    if all(x in "0123456789." for x in text) and text.count(".") <= 1:
        try:
            float(text)
            return True

        except ValueError:
            return False

    else:
        return False
