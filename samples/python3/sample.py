# python3 sample file

import abc

class Parent(abc.ABC):
    @abc.abstractmethod
    def foo():
        pass

class Child(Parent):
    pass

def hello(name: str= "João", greeting: str = "Hello", foo: str = ...):
    print('foo')
    foo = 123
    print("{}, {}!".format(greeting, name))

hello("You", "Hi")

def with_params(param: str, paramb: int, paramc: str = None):
    print(f'param={param}')



#child = Child()
#child.foo()
