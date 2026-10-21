# 10,000-account live-Jev run files (`fmt: "live10k-2"`)

Written by `python -m jevsociety.live10k`. Each file sets `window.NETS[name] = rec`. The list of runs is
`viewer/runs/live10k_manifest.js` (`window.LIVE10K_MANIFEST`, one entry per run with config, cost, summary and the final
tick's metrics; `file` is null for runs kept as metrics only). Full metrics and summaries are also in `data/net_live10k.json`. Naming: `chrono` is the random feed, `engagement` the ranked
feed (by predicted likes); one tick is one day.

**live10k-2** (what ships) is live10k-1 with three per-frame fields dropped (`xy`, `camp`, `fown`: the viewer lays the graph
out in the browser and never read the other two) and with `S` and `fol` stored in full on frame 0 only. Later frames carry
`dS` and `dfol` instead: base64 `<u4` pairs (index, new value) for the entries that changed since the previous frame. This
cuts a run from about 25.6 MB to 8.5-9.7 MB. `jevsociety.live10k.save` writes live10k-2; `scripts/compact_runs.py` converts
older files. The table below describes the full live10k-1 frame.

## Top level

| Field | Meaning |
| - | - |
| `fmt` | `"live10k-2"` (`"live10k-1"` before compaction) |
| `config` | `n` (10,000), `ticks` asked, `ticks_done`, `ranker` (`chrono` / `engagement`), `seed`, `k` (20 follows), `feed` (6), `net` (`random` / `smallworld`), `drawn` (accounts recorded for drawing), `switch_to_chrono_at` (first tick on which every account uses the chronological feed, or null), `day_per_tick` (1), `frame_every` (a viewer frame every this many ticks; metrics are every tick), `stubborn` (daily chance of moving one changed position back to its tick-0 side; 0 = off), `sym` (true: Jev's lean removed by averaging each fit judgment with its mirror image), `label` (short viewer label for fair-test runs, else null). Runs without the last three are as-measured runs |
| `cost_usd` | new Jev spend of this run (cached answers are free) |
| `new_answers` | live Jev answers this run added to `data/jev_live_fit.json` |
| `stopped` | null, or why the run stopped early (budget, API error) |
| `issues`, `short`, `statements` | 16 issue names, short labels, 32 statements (statement `2*i` = side A of issue `i`, `2*i+1` = side B) |
| `axis` | survey first principal component per issue; used only for colouring (positive = liberal side A) |
| `drawn` | base64 `<u2`, length `D`: the account ids that are drawn, sorted. Drawn index `d` is account `drawn[d]` |
| `hist` | one object per tick 0..ticks_done, metrics over ALL 10,000 accounts (below) |
| `frames` | one object per recorded tick: 0, `frame_every`, 2 × `frame_every`, ... and the last tick (below). Read `frames[i].tick`, do not assume one frame per tick |

## `frames[t]` (all base64, little-endian)

| Field | Type, length | Meaning |
| - | - | - |
| `tick` | int | tick (day) |
| `S` | `<u2` × n | positions of ALL accounts after this tick: bit `i` = 1 means statement B of issue `i` |
| `camp` | packbits (`bitorder="little"`) of n bits | the society's own two-way split at this tick (bit = 1: smaller camp). All 0 when there is one camp. Labels can swap between ticks when the smaller side changes |
| `xy` | `<i2` × D × 2 | layout of the drawn accounts, centred and scaled to ±32000. Spring layout on the exposure graph among drawn accounts (who saw whose posts, weight × 0.9 per tick), warm-started from the previous frame; tick 0 uses follows among drawn accounts |
| `fol` | `<u2` × D × 20 | each drawn account's 20 follows (account ids 0..n-1, any account, drawn or not) |
| `fown` | `u1` × D | how many of those 20 follows are in the account's own camp |
| `feed` | `<u2` × D × 6 | the author ids of the up to 6 posts the drawn account saw on this frame's tick (one day, not the days between frames); 65535 = empty slot (fewer than 6 followed accounts posted) |
| `post` | `u1` × D × 6 | the statement of each of those posts (0..31, `issue = post >> 1`, side = `post & 1`); 255 = empty |
| `like` | `u1` × D | bitmask: bit `j` set if the account liked feed slot `j` |
| `adopt` | `u1` × D | issue the account switched to a feed post's side on this tick, 255 = none |
| `sil` | `<u2` × D | bitmask of issues on which the drawn account is silent (holds the position but no longer posts it) |

Frame 0 has empty `feed`/`post` and zero `like`. `S` at frame `t` is after the tick's updates; `post` holds what was posted
during tick `t` (before updates).

## `hist[t]` (all accounts)

`mean_abs_r` (sorting: mean |r| between the 16 issues; US adults 0.17), `r_gss` (match of the 120 issue-pair correlations to
GSS 2024), `minority` (share of accounts in the smaller camp; 0 = one camp), `package_gap` (issues the two camps' packages
differ on), `agree_exposure` (share of feed posts that agree with the viewer), `camp_exposure` (share of feed posts from the
viewer's own camp), `cross_ties` (share of follows that cross camps), `modularity` (follow graph by camp), `consistency`,
`echo_share`, `silent`, `silent_minority` / `silent_majority` (share of positions silenced among holders of the minority /
majority side of each issue), `unfollows` (cumulative), `switches`, `likes` (this tick), `diversity`, `liberal_share`,
`capture`, `pc1`, `pc1_self`, `cost_usd` (cumulative this run), `cache` (live answers known), `wall_s`, `chrono_share`
(share of accounts on the chronological feed).
