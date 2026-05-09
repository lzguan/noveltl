def f():
    print("f")
    g()


def g():
    print("g")

    def gg():
        print("gg")

    gg()


class H:
    def h(self):
        print(self)
        print("h")
        f()


x = H()
