#!/bin/sh
# usage: fn.sh START_HEX END_HEX  (6 hex digit upper)
awk -v s=$(printf "%d" 0x$1) -v e=$(printf "%d" 0x$2) '{a=$1; sub(":","",a); v=strtonum("0x" a); if(v>=s&&v<e) print}' /c/repos/e92_mk60e5/analysis/7846816A_main.lst
