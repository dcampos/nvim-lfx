<?php

class Foo {}

function foo(string $greeting = "Olá", string $name = "João") {
	$foo = new Foo();
	echo $foo;
	$baz = '123';
	echo "$greeting, $name!";
}
