def foo(arg1, arg2):
    print("foo execution")
    return arg1 + arg2

foo_call = lambda: foo(1, 2)

print(foo_call())