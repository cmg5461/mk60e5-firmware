#!/bin/sh
# usage: norm.sh file
sed -E 's/^ *[0-9A-F]+: *//; s/^sub_[0-9A-F]+:/sub:/; s/(bt|bf|br|bsr|jsr|jbsr) 0x[0-9a-f]+/\1 T/; s/\[0x[0-9a-f]+\]/[P]/' "$1"
