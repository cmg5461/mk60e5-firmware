#!/bin/bash
L=/c/repos/e92_mk60e5/analysis/7846816A_main.lst
for n in $(grep -n "0x000833da" $L | cut -d: -f1); do
 echo "---- site $(sed -n ${n}p $L | awk '{print $2}')"
 sed -n "$((n-16)),${n}p" $L | cut -c1-80 | sed -E 's/^ +0*([0-9A-F]+): +[0-9A-F]{4} +/\1 /' | grep -E "movi|mov |lrw|ld\.|st\.|bsr|jsri|^sub_|bt|bf|br|cmp"
done
