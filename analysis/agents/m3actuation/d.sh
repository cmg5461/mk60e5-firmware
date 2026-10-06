#!/bin/bash
# usage: d.sh addr(hex no 0x) [n]
a=$(printf "%06x" $((16#$1)))
L=/c/repos/e92_mk60e5/analysis/7846816A_main.lst
s=$(grep -n -i "^sub_0*$a:" $L | head -1 | cut -d: -f1)
[ -z "$s" ] && s=$(grep -n -i "^  0*$a:" $L | head -1 | cut -d: -f1)
sed -n "${s},$((s+${2:-60}))p" $L | cut -c1-110
