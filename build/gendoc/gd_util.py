flatten = (
    lambda i: [element for item in i for element in flatten(item)]
    if type(i) is list
    else [i]
)
