#!/bin/bash
# compact listing: c.sh startlabel endlabel (hex addrs)
L=/c/repos/e92_mk60e5/analysis/7846816A_main.lst
a=$(grep -n -i "^  0*$1:" $L | head -1 | cut -d: -f1)
b=$(grep -n -i "^  0*$2:" $L | head -1 | cut -d: -f1)
sed -n "${a},${b}p" $L | cut -c1-90 | sed -E 's/^ +0*([0-9A-F]+): +[0-9A-F]{4} +/\1 /; s/^sub_0*/\n== /' | grep -v "^$" | grep -v " ldq r4-r7\| bkpt\| stop$\|\.short 0x00"
