import sys,bisect
sys.path.insert(0,'analysis/agents/m3absslip')
import fn
for a in sys.argv[1:]:
    print(a, hex(fn.fn_of(int(a,16)) or 0))
