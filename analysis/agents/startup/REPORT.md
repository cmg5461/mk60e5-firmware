# Startup and scheduler architecture: 1M 7846411A

Source: a Sonnet subagent's report, saved by the main session because the agent could not write
files. The text is condensed but faithful to the report. CPU addresses throughout.

**Verified by the main session against the binary:**
- Task entry table at 0x42700 = {0x785DA, 0x785EA, 0x78602, 0x78778, 0x785BE}.
- Priorities (u16) at 0x42714 = {3, 0, 1, 2, 4}.
- Autostart flags at 0x42734 = {1, 0, 0, 0, 1}.
- Stack tops at 0x426D8 and bottoms at 0x426EC match the table in section 2.
- 13-entry slot jump table at 0x70B28.
- vec60/vec61 point to stubs 0x42842/0x42880, which call 0x70A86/0x43FD8 as described.

Everything else is the agent's reading. "Guess" marks the agent's own inferences.

## Headline
- The firmware runs an OSEK-style preemptive OS at 0x42700–0x44100:
  - 5 static tasks;
  - ready bitmap plus per-priority queues;
  - events, error hook, ShutdownOS;
  - 0xAA stack canaries.
- The time base is a 13-slot sequencer ISR (vec60 → 0x70A86). It re-arms a D8 compare channel each slot and activates tasks.
- There is no flash-to-RAM .data copy. RAM 0x400000..0x40C000 is zeroed, plus zero loops at 0xFFF80000, 0xFFF82000 and 0xFFF84000.
- No explicit watchdog service was found.

## 1. Reset to main
```
reset 0x06C9B2
  psrset 0 (alt reg file); zero r1-r14; r0=0x40044C   <- alt-file SP (ISR stack)
  psrclr 0 (normal file);  zero r1-r14; r0=0x400320   <- normal-file SP (startup stack)
  zero cr6..cr10
  0x06CA78  RAM clear 0x400000..0x40C000; zero loops 0xFFF80000 (1 w), 0xFFF82000 (1024 w), 0xFFF84000 (4096 w)
  0x06C4A4  0 -> u16 0xFF0008            (module 0xFF0000; watchdog/RTC-like: guess)
  0x06C498  set bit15 of 0xDC0000        (clock/PLL: guess)
  0x06C4AC  clear bit5 of u16 0xFF0000
  0x06C784  PLL/clock init: tables at 0xD752E/0xD756E, programs 0xDC0000, polls 0xDC0006 bit3
  mtcr 0x40000 -> cr1 (VBR) at 0x06CA18
  0x06C4B6  INTC 0xE10000 init: ctrl clear, +0x10=0, +0x18=0xFFFFFFFF, 15-word priority table at 0xE10040
  0x06C506.. 0x06C700  timer modules D8/F8: every channel ctrl write mirrored to both
  0x06C71A  OR 7 into 0xF50000 and 0xD50000
  0x06C72E  0xD5644 (set bit1 of 0xFFF00000), 0xD5624 (clear low 5 bits), 0xD55EC (clear bit0 of 0xFFF80000)
            0xFFF00000 is masked with 0x1F00 by every IRQ stub, so probably the core priority mask (guess)
  PSR |= bit8, PSR &= ~bit31
  jsr 0x0788EE app_main: r2=0xD7F14, r3=0 -> 0x0788A8 app_init(obj, mode)
     vtbl call, 0x786A8, 0x78416, 0x7842E, 0x78538, ..., 0x786CA (5 budgets = 0xBB8)
     tail jmpi 0x42F9A (never returns)
  0x42F9A OS_Start:
     set bit1 of 0xE10018; reset both SPs
     0x4291E: canary fill 0x400320..0x40044C
     jmp 0x42BD2
  0x42BD2 OS_Init_and_Start:
     0x428F4: ready bitmap 0x400864 = 0; queue heads 0x40086A[5] = 0xFFFF
     0x4292E: fill task stacks with 0xAA
     task_state[i] = 4 (suspended); autostart via 0x43B3C
     0x42B68: INTC priority-table self-check
     0x78044: startup hook
     set 0xE10008 bit 0x80000 -> vec32 dispatcher 0x42DA4 starts the first task
```

## 2. Scheduler
OS service ids come from the high byte of the error code; names follow OSEK convention (medium confidence).

| id | service | addr |
|---|---|---|
| 0x11 | ActivateTask | 0x43974 |
| 0x12 | TerminateTask | 0x43BEA |
| 0x15 / 0x16 | GetTaskState / GetTaskID-like | 0x43E7C / 0x43DF2 |
| 0x41 | SetEvent | 0x430EC |
| 0x42 | ClearEvent | 0x4330E |
| 0x43 | GetEvent | 0x434B4 |
| 0x44 | WaitEvent | 0x436BC |

Error reporting: 0x43060 stores the code in 0x40084A and calls hook 0x780FA.

| Task | Entry | Prio (0 = highest) | Autostart | Stack | Role |
|---|---|---|---|---|---|
| T0 | 0x0785DA | 3 | yes | 0x40044C..0x400578 | extended: loop {WaitEvent(1); ClearEvent(1); 0x78B20()}; event set in slot 11 |
| T1 | 0x0785EA | 0 | no | 0x400578..0x400708 | basic; slots 0, 3, 7, 10 |
| T2 | 0x078602 | 1 | no | 0x400578..0x400708 (shared with T1) | basic; slots 0, 1, 2, 5, 6, 7, 8, 9, 11, 12 |
| T3 | 0x078778 | 2 | no | 0x400000..0x400320 | basic; slot 0 only |
| T4 | 0x0785BE | 4 | yes | 0x400708..0x400834 | background: stack-usage measurement loop |

- T1, T2 and T3 call 0x783F8, 0x78256 and 0x78268, then TerminateTask.
- They go through a ROM object at 0xD7F14: a 5-entry task/runtime monitor (budget 0xBB8, error 0xA010 raised by 0x786FC).
- The real control code sits behind that object's vtable pointers (class descriptors 0xD81F4, 0xD8184, …). Not yet followed.

**Time base (vec60 → 0x70A86):**
- Slot counter 0x4009FA runs 0..12, dispatched through jump table 0x70B28.
- Each slot re-arms D8 compare 0 through 0xD6D10 (D8+0x100 += delta, ack D8+0x380). Deltas are 1000, 500, 300 or 200 counts, about 10000 per frame. "~10 ms frame at 1 MHz" is a guess.

| Slot | Activates |
|---|---|
| 0 | T1, T2, T3 (+ 0x73B78, 0x786FC) |
| 1, 2 | T2 |
| 3 | T1 |
| 4 | none (0x74364) |
| 5 | T2 (+ 0x75690) |
| 6 | T2 |
| 7 | T1, T2 (+ 0x7154A) |
| 8, 9 | T2 |
| 10 | T1 |
| 11 | SetEvent(T0, 1) + T2 |
| 12 | T2 |

**Second tick (vec61 → 0x43FD8):** acks F8+0x380, adds 624 to F8+0x100, and increments the u32 at 0x400838.

## 3. IRQs
Every vectored stub runs the same sequence:
1. Raise the mask in 0xFFF00000.
2. Set the in-ISR flag 0x400855.
3. Call the handler.
4. Check the ISR-stack canary at 0x400320 (error 0xA101 on failure).
5. Clear the flag and rfi.

The default handler 0x4273C raises error 0x2801.

| vec | handler | what | conf |
|---|---|---|---|
| 32 | 0x42DA4 | OS dispatcher (INTC 0xE10008 bit 0x80000) | high |
| 40 | 0x6DB0C | CAN module 0xDD0000 (mailbox read 0xD4554, config 0xD82D5, buffer 0x401174) | med |
| 44 | 0x7076C | serial/protocol RX via 0xFC0004/7, state 0x403368..78 | low |
| 49 | 0x70370 | F8 flag + 0xD5070 touching 0xDB0000; state 0x400A74 | low |
| 52 | 0x700E8 | D8 compare ch2; 12-state machine 0x70110 / 0x403376; same 0xFC0000 peripheral as vec44 | low-med |
| 56–59 | 0x70EC6, 0x70DB2, 0x70E3C, 0x70D2C | wheel-speed edge captures | high |
| 60 | 0x70A86 | 13-slot OS time base | high |
| 61 | 0x43FD8 | F8 periodic compare (+624), tick counter | med |
| trap1 | 0x42EF2 | OS critical-section helpers (`lrw r7,fn; trap 1`) | high |

## 4. Safety and monitoring
- **Stack canaries:** 0xAA on all stacks. Checked after every ISR and at task switch; T4 measures usage continuously.
- **INTC self-check:** the priority table is checked (entry 19 = 0, entry 29 unique, others non-zero).
- **Error hook:** leads to ShutdownOS 0x42A68.
- **Runtime budgets:** 0xD7F14 holds per-task budget records (0xBB8, error 0xA010), probably timing supervision (guess).
- **D8/F8 pairing:** init is mirrored. Wheel channels: ch0/ch1 on F8, ch2/ch3 on D8. No code comparing the two counters was found.
- **Watchdog:** not identified. Candidates are the 0xFF0000 module and the 0xF50204 bit0 toggle in T0's worker 0x78B20 (guess).
- **ROM checksum:** none seen in this pass.

## 5. Open questions
1. Where do the vtable targets behind 0xD7F14 (class descriptors 0xD81F4, 0xD8184, …) lead? That is the real ABS/ESC code and the CAN tx/rx scheduling.
2. What are 0xFF0000, 0xDC0000, 0xFFF00000 and 0xFFF80000..0xFFF84000 (watchdog, clock, priority mask, retention RAM)?
3. What is the INTC priority-index to vector mapping?
4. What is the timer clock? The PLL tables 0xD752E/0xD756E are not decoded.
5. Is 0xFC0000 (vec44/52) serial/SPI, and is 0xDB0000 an ADC? The main session separately classed 0xDB0000 as a queued SPI controller (med); these two readings conflict.
6. What is the exact delta arithmetic for slots 4 and 5?
