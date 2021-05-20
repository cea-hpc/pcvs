#!/bin/bash
ret=0
func()
{
	printf "=========\n$1: "
	cmd="$@"
	var=$(eval "$cmd" 2>&1)
	if test "$?" -ne 0; then
		printf "\033[1;31mN"
	else
		printf "\033[1;32m"
	fi
	printf "OK\033[0;0m\n"
	test "$V" = "1" && printf "==> $cmd:\n$var\n"
	ret=1
}

func darglint --verbosity 2 "$@"

func pydocstyle "$@"

func flake8 --docstring-style sphinx "$@"

func isort --check-only "$@"

exit $ret
