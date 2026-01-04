def f():
    print("f")
    print(locals())
    g()

def g():
    print("g")
    print(locals())
    def gg():
        print("gg")
        print(locals())
    gg()

class H:
    def h(self):
        print(self)
        print("h")
        print(locals())
        f()

x = H()

if __name__ == '__main__':
    print(globals())