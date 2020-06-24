<?php

class Foo {}

function foo_function(string $greeting = "Olá", string $name = "João") {
	$foo = new Foo();
	echo $foo;
	$baz = '123';
	echo "$greeting, $name!";
}

foo
