def my_abs_test(x):
    if x < 0:
        return -x
    else:
        return x
    

def multi_retun_func(x):
    if x < 0:
        return -x, "Negative"
    elif x == 0:
        return 0, "Zero"
    else:
        return x, "Positive"