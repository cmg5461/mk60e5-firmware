| +01E | accel-limit vs slip A | 3 | -500..500 | [1500, 2800] | [150, 299, 21] | [0, -102, 0] | x=0x403086[w] (filtered slip, 0.01 km/h); y compared with wheel record +0x22; reader C7CCA (call 0xC7D22) | [agent, low] |
| +034 | accel-limit vs slip B | 3 | -5000..1000 | [4000, 6000] | [0, 1000, 1000] | [0, -256, -256] | x=0x403086[w]; y compared with 0x40308e[w]; reader C7CCA (0xC7DA6) | [agent, low] |
| +04E | cross-wheel add to lower limit | 4 | 0..1400 | [500, 1000, 2000] | [0, -400, -400, 1200] | [0, 819, 819, 0] | x=-0x40308e[partner wheel]; y added to 0x40300c[w] before compare with 0x403086[w]; reader C7CCA (0xC7F1E) | [agent, low] |
| +076 | low-speed offset | 2 | 0..10000 | [800] | [992, 0] | [-1270, 0] | x=0x403066 (vref); y 9.92 km/h at 0 -> 0 at 8 km/h; reader C7600 (0xC773C) | [agent, low] |
| +086 | BASE SLIP THRESHOLD set B, mode 0 | 5 | 0..30000 | [1500, 2500, 8000, 10000] | [700, 522, -27, -2833, -2138] | [-294, -173, 52, 411, 340] | x=0x403066 (vref, 0.01 km/h); y = threshold 0.01 km/h; reader C7746 -> C777E -> 0x402fc2 | [agent, med] |
| +0A8 | BASE SLIP THRESHOLD set B, mode 1 | 5 | 0..30000 | [1500, 5000, 8000, 10000] | [700, 651, 594, -1337, -2127] | [-34, -1, 11, 258, 339] | same; reader same | [agent, med] |
| +0CA | BASE SLIP THRESHOLD set B, mode 2 | 5 | 0..30000 | [1500, 5000, 8000, 10000] | [700, 552, 495, -1428, -2238] | [-102, -1, 11, 257, 340] | same; reader same | [agent, med] |
| +0EC | BASE SLIP THRESHOLD set A, mode 0 | 5 | 0..30000 | [1500, 2500, 8000, 10000] | [1500, 525, -27, -2833, -2138] | [-840, -174, 52, 411, 340] | same; reader same (default set; set B used when 0x402F6C bit4) | [agent, med] |
| +10E | BASE SLIP THRESHOLD set A, mode 1 | 5 | 0..30000 | [1500, 5000, 8000, 10000] | [1400, 965, 595, -1328, -2138] | [-362, -65, 11, 257, 340] | same; reader same | [agent, med] |
| +130 | BASE SLIP THRESHOLD set A, mode 2 | 5 | 0..30000 | [1500, 5000, 8000, 10000] | [1400, 865, 495, -1428, -2238] | [-430, -65, 11, 257, 340] | same; reader same | [agent, med] |
| +160 | extra term (min-cap), single | 2 | 0..2000 | [3000] | [1000, 1501] | [171, 0] | x=0x403066; capped result; reader C77FC (0xC783E) | [agent, low] |
| +170 | sibling of 0x160 (no direct reader found) | 2 | 0..2000 | [3000] | [500, 1499] | [341, 0] | ?; reader - | [agent, low] |
| +180 | threshold extra vs vref, mode 0 | 4 | 0..1000 | [1500, 1800, 2600] | [1000, 200, 200, 200] | [-546, 0, 0, 0] | x=0x403066 (only if >=2.50 km/h and 0x402F7E bit4 clear); reader C7852 (0xC787C) -> C78D0 r12 | [agent, low] |
| +19C | threshold extra vs vref, mode 1 | 4 | 0..1000 | [1500, 1800, 2600] | [700, 700, -125, 200] | [-341, -341, 128, 0] | same; reader same | [agent, low] |
| +1B8 | threshold extra vs vref, mode 2 | 4 | 0..1000 | [1500, 1800, 2600] | [700, 200, 200, 200] | [-341, 0, 0, 0] | same; reader same | [agent, low] |
| +1E4 | zero table (x=0x403098, all A=B=0) | 4 | 0..2000 | [2000, 4000, 6000] | [0, 0, 0, 0] | [0, 0, 0, 0] | x=0x403098 (20/40/60 km/h axis); reader C7CCA (0xC7DFA/0xC7E06) | [agent, low] |
| +200 | unread-by-lrw table? x=vref 60..100 km/h | 5 | 0..1800 | [6000, 7000, 8000, 10000] | [1700, 8900, 4000, 0, 0] | [0, -1229, -512, 0, 0] | x=0x403066; reader C9124 (0xC9130) | [agent, low] |
| +240 | engine-term curve (set 0x402F6C bit4 clear) | 4 | 0..10000 | [75, 125, 175] | [1400, 1500, 4000, 4000] | [21845, 20480, 0, 0] | x=byte 0x401142 (0..175); y 14.00..40.00; reader C9704 (0xC9726) | [agent, low] |
| +25C | engine-term curve (set 0x402F6C bit4 set) | 4 | 0..10000 | [75, 125, 175] | [1400, 1500, 4000, 4000] | [21845, 20480, 0, 0] | x=byte 0x401142; reader C9704 (0xC9716) | [agent, low] |
| +2F4 | gain % vs vref | 4 | 0..100 | [1000, 4000, 6000] | [100, 100, 166, 166] | [0, 0, -17, -17] | x=0x403066; y 100 -> 166 %? /100 scale; reader C8E96 (0xC8F92) | [agent, low] |
| +310 | excess term vs vref (all zero) | 3 | 0..2500 | [2000, 10000] | [0, 0, 0] | [0, 0, 0] | x=0x403066; reader C8E96 (0xC8ED4) | [agent, low] |
| +3D4 | unknown curve vs 30/100/150 km/h | 4 | 0..5000 | [3000, 10000, 15000] | [1800, 1774, 3492, 51] | [-68, -59, -235, 0] | x=0x403066; reader CBD98 (0xCBF62) | [agent, low] |
| +3F0 | unknown small-int curve vs 50/82/123 km/h | 4 | 0..16 | [5000, 8200, 12300] | [16, 16, 16, 4] | [-1, -1, -1, 0] | x=0x403066; reader CBD98 (0xCBE56) | [agent, low] |
| +422 | triangle 0..150 (peak at 270) | 3 | 0..150 | [90, 270] | [0, 90, 360] | [1024, 0, -1024] | x=?; reader CD490 (0xCD582) | [agent, low] |
| +438 | curve vs vref 49.6/60 km/h | 3 | 0..1000 | [4960, 6000] | [230, 77, 74] | [0, 32, 32] | x=0x403066; reader CD490 (0xCD4A2) | [agent, low] |
| +4A8 | ramp 5120/1024 (x 10,20) | 3 | 0..600 | [10, 20] | [0, 0, 0] | [5120, 5120, 5120] | x=signed byte 0x403096; reader CA7A4 (0xCA80C) | [agent, low] |
| +4C4 | ramp 5120/1024 (x 10,20) twin | 3 | 0..600 | [10, 20] | [0, 0, 0] | [5120, 5120, 5120] | x=?; reader CA826 (0xCA86C) | [agent, low] |
| +534 | ramp set mode 0 (x 22,50,78; y<=600) | 4 | 0..600 | [22, 50, 78] | [-20, 6, -37, -115] | [1862, 658, 1536, 2560] | x=signed byte 0x403096; reader CE54E (0xCE672) | [agent, low] |
| +550 | ramp set mode 1 (identical to 0x534) | 4 | 0..600 | [22, 50, 78] | [-20, 6, -37, -115] | [1862, 658, 1536, 2560] | same; reader same | [agent, low] |
| +56C | ramp set mode 2 (identical to 0x534) | 4 | 0..600 | [22, 50, 78] | [-20, 6, -37, -115] | [1862, 658, 1536, 2560] | same; reader same | [agent, low] |
| +588 | const 4500 (x 30/60/100 km/h) | 4 | 0..2000 | [3000, 6000, 10000] | [4500, 4500, 4500, 4500] | [0, 0, 0, 0] | x=0x403066; reader CE54E (0xCE65A) | [agent, low] |
| +5A4 | const 200 (x 30/60/100 km/h) | 4 | 0..2000 | [3000, 6000, 10000] | [200, 200, 200, 200] | [0, 0, 0, 0] | x=0x403066; reader CE54E (0xCE71C) | [agent, low] |
| +5C6 | factor vs vref, mode 0 (y 35.00->10.00 %?) | 4 | 0..10000 | [1500, 2500, 9000] | [3500, 2250, 1000, 1000] | [-1365, -512, 0, 0] | x=0x403066 (15/25/90 km/h); reader CA058, CA518, CB3E4 | [agent, low] |
| +5E2 | factor vs vref, mode 1 | 4 | 0..10000 | [1500, 6000, 9000] | [4500, 2834, 1498, 1498] | [-1365, -228, 0, 0] | same; reader same | [agent, low] |
| +5FE | factor vs vref, mode 2 (= mode 1) | 4 | 0..10000 | [1500, 6000, 9000] | [4500, 2834, 1498, 1498] | [-1365, -228, 0, 0] | same; reader same | [agent, low] |
| +61C | const 5 (x=8) | 2 | 1..16 | [8] | [5, 5] | [500, 500] | ?; reader CA058 (0xCA1F4 region) | [agent, low] |
| +63A | const 200 (x 50/100/150 km/h) | 4 | 0..2000 | [5000, 10000, 15000] | [200, 200, 200, 200] | [0, 0, 0, 0] | x=0x403066; reader CA058 (0xCA1F4) | [agent, low] |
| +66E | 17-word curve set mode 0 (y<=16000) | 5 | 0..16000 | [3500, 7000, 10000, 14000] | [3200, 3002, 2727, 4895, 2] | [-234, -176, -136, -358, 0] | x=0x403066 (35/70/100/140 km/h); reader CBAC6 (0xCBAF8) | [agent, low] |
| +690 | 17-word curve set mode 1 | 5 | 0..16000 | [5000, 7500, 10000, 18000] | [7000, 7024, 10564, 9000, 0] | [-184, -189, -672, -512, 0] | same (axis 50/75/100/180); reader CBAC6 | [agent, low] |
| +6B2 | 17-word curve set mode 2 | 5 | 0..16000 | [3500, 7000, 10000, 14000] | [5800, 5800, 5800, 7000, 0] | [-389, -389, -389, -512, 0] | same; reader CBAC6 | [agent, low] |
| +6D4 | 17-word curve set 2nd bank mode 0 | 5 | 0..16000 | [3500, 7000, 10000, 14000] | [6800, 6783, 6830, 12250, 0] | [-339, -334, -341, -896, 0] | same; reader CBB72 (0xCBBCE) | [agent, low] |
| +6F6 | 17-word curve set 2nd bank mode 1 | 5 | 0..16000 | [3500, 7000, 10000, 15000] | [8800, 8800, 20469, -1, -1] | [-389, -389, -2096, 0, 0] | same; reader CBB72 | [agent, low] |
| +718 | 17-word curve set 2nd bank mode 2 | 5 | 0..16000 | [3500, 7000, 10000, 14000] | [8800, 8800, 20469, -1, -1] | [-389, -389, -2096, 0, 0] | same; reader CBB72 | [agent, low] |
| +742 | zero table (x=0x403066 20/60/100 km/h) | 4 | 0..1000 | [2000, 6000, 10000] | [0, 0, 0, 0] | [0, 0, 0, 0] | x=0x403066; reader C9380 (0xC93A0/0xC93B2/0xC93E8) | [agent, low] |
| +77E | const curve 30.00 -> 15.00 (x 0.44/1.0/1.5/1.7) | 5 | 0..5000 | [44, 100, 150, 170] | [3000, 3000, 3000, 1500, 1500] | [-10240, -10240, -10240, 0, 0] | x=byte 0x4030AF; reader C9BF4 (0xC9C46) | [agent, low] |
| +7F0 | step 25/100 (x 0.25/0.75) | 3 | 0..100 | [25, 75] | [25, -12, 100] | [0, 1536, 0] | x=byte 0x4030B8; reader CA058 (0xCA186) | [agent, low] |
| +806 | step 25/98 (x 25/75 %?) | 3 | 0..100 | [2500, 7500] | [25, -12, 98] | [0, 15, 0] | x=0x4030B8*100; reader CB3E4 (0xCB522) | [agent, low] |
| +826 | zero table (x 1.24/2.5) | 3 | 0..2000 | [124, 250] | [0, 0, 0] | [0, 0, 0] | x=byte 0x401142; reader CB648 (0xCB65A) | [agent, low] |
| +83C | ramp 5.00 -> 0 (x 15/50 km/h), mode 0 | 3 | 0..1500 | [1500, 5000] | [500, 0, 0] | [-341, 0, 0] | x=0x403066; reader CB66C (0xCB694) | [agent, low] |
| +852 | ramp mode 1 | 3 | 0..1500 | [2500, 5000] | [750, 359, 101] | [-213, -53, 0] | x=0x403066; reader CB66C | [agent, low] |
| +868 | ramp mode 2 | 3 | 0..1500 | [1500, 5000] | [750, 0, 0] | [-512, 0, 0] | x=0x403066; reader CB66C | [agent, low] |
| +87E | curve mode 0 (x 85.5/100 km/h) | 3 | 0..2000 | [8550, 10000] | [100, 45, -115] | [-1, 6, 22] | x=0x403066; reader CB66C (0xCB682) | [agent, low] |
| +894 | curve mode 1 (x 120/150 km/h) | 3 | 0..2000 | [12000, 15000] | [400, 295, -101] | [5, 14, 41] | x=0x403066; reader CB66C | [agent, low] |
| +8AA | curve mode 2 (x 100/150 km/h) | 3 | 0..2000 | [10000, 15000] | [300, 398, -100] | [10, 0, 34] | x=0x403066; reader CB66C | [agent, low] |
| +8E4 | const 40.00 (x 20/40 km/h) | 3 | 0..6000 | [2000, 4000] | [4000, 4000, 4000] | [-512, -512, -512] | ?; reader no reader found | [agent, low] |