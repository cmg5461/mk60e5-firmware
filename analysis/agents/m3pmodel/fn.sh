#!/bin/bash
# usage: fn.sh startaddr endaddr (hex, no 0x): print listing between sub labels / addresses
L=/c/repos/e92_mk60e5/analysis/7846816A_main.lst
a=$(grep -n -i "^  0*$1:" $L | head -1 | cut -d: -f1)
b=$(grep -n -i "^  0*$2:" $L | head -1 | cut -d: -f1)
sed -n "${a},${b}p" $L | cut -c1-100 | grep -v '^$' | grep -v "ldq r4-r7,(r0)\|bkpt\|\.short 0x00\|stop$"
