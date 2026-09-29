# Bank SMS formats seen in real data

Fill this in while labelling. It drives the Week 3 templates (one or more per row).

**Only paste MASKED examples here** (copied from `data/real/masked.jsonl`). This file is
committed, so re-read each example for names or numbers the masker missed.

| Bank | Sender ID(s) | Mode | Masked example | Quirks |
|---|---|---|---|---|
| HDFC | HDFCBK | UPI debit | `Rs.450.00 debited from A/c XX1234 on 28-09-26 to VPA swiggy@icici. UPI Ref 426512345678. Avl Bal Rs.12,340.50 -HDFC Bank` | *(synthetic placeholder: replace with a real masked one)* DD-MM-YY date; "Avl Bal" |
| | | | | |

Things worth noting per format:

- Date style (`28-09-26`, `28Sep26`, `28/09/2026`, `28-Sep-2026 14:05`, none)
- Amount style (`Rs.`, `Rs `, `INR`, `₹`; commas; decimals or not)
- Account style (`XX1234`, `X1234`, `*1234`, `ending 1234`)
- Where the merchant appears (after `to`, `at`, `Info:`, inside a VPA, or missing)
- Balance present or not, and its label (`Avl Bal`, `Bal`, `Available balance`)
- Anything unusual: multiple amounts, line breaks, Hindi text, truncated SMS

## Coverage (target: at least 6 banks, 200 records)

| Bank | Labelled records |
|---|---|
| | |
