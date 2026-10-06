#!/bin/sh
# sh.sh lst HEXADDR COUNT
a=$(printf '%06X' $((16#$2)))
n=$(grep -n -m1 "^ *$a:" $1 | cut -d: -f1)
sed -n "${n},$((n+$3))p" $1
