from brewblox_service import strex


def f1():
    raise RuntimeError('BOO!')


def f2():
    f1()


def f3():
    f2()


try:
    f3()
except Exception as ex:
    print(strex(ex, True))
