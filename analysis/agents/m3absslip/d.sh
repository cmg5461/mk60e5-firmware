#!/bin/bash
# usage: d.sh START END (hex, no 0x)  -- prints listing lines compactly
awk -v s=$((16#$1)) -v e=$((16#$2)) '{a=strtonum("0x" substr($1,1,6)); if(a>=s&&a<e){ $2=""; print}}' analysis/7846816A_main.lst 2>/dev/null || true
