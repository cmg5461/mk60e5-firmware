#!/bin/bash
# rng.sh START END (hex, no 0x)
awk -v s=$1 -v e=$2 'BEGIN{S=strtonum("0x" s);E=strtonum("0x" e)} /^  0[0-9A-F]{5}:/{a=strtonum("0x" substr($1,1,6)); if(a>=S&&a<E)print} /^sub_/{ if(0)print}' /c/repos/e92_mk60e5/analysis/7846816A_main.lst
