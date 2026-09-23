# PV2 live leave / attendance / Arabic — 2026-09-23l

**Host:** `emp_1067` · **DB:** `nibras_dev` · **Mode:** Chat only  
**G5:** 96/96 unchanged.

After 23k rest-bank misses, Chat now:

- restates bound leave on "Yes, that's correct" (answer, 0 LLM) instead of fetching history
- hands off on "anything else you need?" when slots are enough
- treats "الإبلاغ عن غياب" as a leave write (clarify → confirm), not a 3-LLM "no tool"
- answers Arabic payslip amounts from the committed identity, in Arabic
- does not hijack "اعتراض على الخصومات" as net-pay recall

| Script | 23k rest | **23l** |
|---|---|---|
| ess-leave-en-01 | 6/8 | **8/8 PASS** |
| ess-attendance-mixed-01 | 6/8 | **8/8 PASS** |
| language-fidelity-ar-01 | 2/8 | **7/8** (t2 golden wants ٦٠٠٠ / dinar; host gross is 6500) |

Goldens not edited. 6500 / 1200 / 800 / 4500 were not rewritten to 6000. Night 2026-09-23 FAIL not rewritten.
