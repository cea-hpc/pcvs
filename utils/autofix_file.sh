#!/bin/bash

func()
{
	printf "$1: "
	var=$(eval "$@" 2>&1)
	printf "Done\n"
}

func isort "$@"
func autopep8 --recursive --in-place "$@"

printf "\n====== POST-CHECK =====\n"
cur_prefix="$(dirname $0)"
sh $cur_prefix/check_file.sh "$@"
