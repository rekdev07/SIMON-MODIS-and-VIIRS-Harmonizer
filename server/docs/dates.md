# How dates work

## Everything is UTC

Satellites record the time of each detection in **UTC** (Coordinated Universal Time), the
same reference clock for the whole planet. FIRMS publishes UTC, the database stores UTC,
and the API answers in UTC. Timestamps end with `Z` ("Zulu" = UTC):

```
"acquired_at": "2024-04-15T19:42:00Z"   → 19:42 UTC = 13:42 in Mexico City (UTC−6)
```

Why not local time: Mexico alone spans several time zones and some had daylight saving time
until 2022. UTC has no gaps or repeated hours, and the frontend can convert to local time
for display.

## `start_date` and `end_date` are both inclusive

`start_date=2024-04-01&end_date=2024-04-30` means **all 30 days of April**, from
`2024-04-01 00:00:00 UTC` up to and including `2024-04-30 23:59:59 UTC`.

```
            start_date                                  end_date
               │                                           │
   ... 03-31 │ 04-01 │ 04-02 │  ...  │ 04-29 │ 04-30 │ 05-01 ...
               ◄────────────── included ───────────────►
```

Both are inclusive because that is how people talk about date ranges ("from April 1 to
April 30"). A single day is `start_date = end_date`.

Rules: format `YYYY-MM-DD`; `start_date <= end_date`; both between `2000-11-01` (MODIS
data begins) and **today in UTC**.

## Why filter on `acq_date` and not on `acquired_at`

Each row has both:

| Column | Type | Example |
|---|---|---|
| `acquired_at` | TIMESTAMP (UTC) | `2024-04-15 19:42:00` |
| `acq_date` | DATE (UTC day of `acquired_at`) | `2024-04-15` |

The filter is simply:

```sql
acq_date BETWEEN start_date AND end_date
```

Why:

1. **It is exactly the meaning of "inclusive days".** With timestamps you would need
   `acquired_at >= '2024-04-01 00:00' AND acquired_at < '2024-05-01 00:00'`, which is easy
   to get wrong (forgetting the last day or the `<`).
2. **It is fast.** `acq_date` has an index, and comparing small date values is cheaper
   than comparing timestamps.
3. **It matches FIRMS.** FIRMS files have an `acq_date` column with the same UTC meaning.

## The midnight case: a fire "on the wrong day"

Satellites pass over Mexico at night around 01:30 *local solar time* (and Terra around
22:30). Local evening in Mexico is already **the next day in UTC**:

```
Detection: 2024-04-16 03:30 UTC   (acq_date = 2024-04-16)
In Mexico City (UTC−6): 2024-04-15 21:30   ← still April 15 locally
```

So a nighttime fire that a person in Mexico saw on the evening of **April 15** is stored
under **April 16**:

| Query | Returns this fire? |
|---|---|
| `start_date=2024-04-15&end_date=2024-04-15` | **No** (its UTC day is the 16th) |
| `start_date=2024-04-16&end_date=2024-04-16` | Yes |
| `start_date=2024-04-15&end_date=2024-04-16` | Yes |

This is expected, not a bug: the API speaks UTC. If the frontend wants local days, it
should widen the range by one day and filter or label by local time on its side.
