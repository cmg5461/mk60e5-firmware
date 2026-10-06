#!/bin/bash
# head of function: h.sh ADDR [N]
N=${2:-45}
awk -v s=$((16#$1)) -v n=$N 'BEGIN{c=0}{a=strtonum("0x" substr($1,1,6)); if(a>=s&&c<n){ $2=""; print; c++}}' analysis/7846816A_main.lst | sed 's/^0//' | grep -v "ldq\|\.short\|bkpt"
