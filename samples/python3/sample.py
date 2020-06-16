# python3 sample file

import abc

class Parent(abc.ABC):
    @abc.abstractmethod
    def foo():
        pass

class Child(Parent):
    pass

def hello(name: str = "João", greeting: str = "Hello"):
    print('foo')
    foo = 123
    print("{}, {}!".format(greeting, name))

hello("You", "Hi")

child = Child()
child.foo()
