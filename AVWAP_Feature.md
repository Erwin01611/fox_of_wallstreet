# **Title:** Add leakage-safe dynamic AVWAP feature for hourly and daily bars

## **Summary:**
This PR adds one AVWAP-derived feature column to the observation space, with all anchor detection, significance filtering, and anchor updates handled internally in the feature-engineering logic. The implementation is designed for hourly and daily OHLCV data on liquid large-cap stocks, and it uses a leakage-safe update process so the feature only changes after a swing pivot has actually been confirmed in real time. [chartschool.stockcharts](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/anchored-vwap)

## **Why this feature:**
Anchored VWAP measures the volume-weighted average price starting from a chosen anchor point rather than from the market open, which makes it useful for tracking “fair value since an important event.” Reliable AVWAP references consistently describe significant anchors as swing highs, swing lows, breakouts, earnings, or major news bars, and that is why this implementation ties the anchor to confirmed market structure instead of arbitrary timestamps. [alchemymarkets](https://alchemymarkets.com/education/indicators/anchored-vwap/)

## Locked design

For this project, the AVWAP feature will use `HLC3` as the per-bar price proxy, a dynamic swing-based anchor policy, and a significance filter so the anchor does not refresh on every small pivot in noisy markets. The goal is to expose only one model-facing AVWAP feature column while keeping the more complex anchor logic behind the scenes inside the feature builder. [litefinance](https://www.litefinance.org/blog/for-beginners/best-technical-indicators/anchored-vwap/)

| Design choice | Final decision |
|---|---|
| Feature output | One main numeric feature: `AVWAP_Dist = (Close / Active_AVWAP) - 1`  [chartschool.stockcharts](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/anchored-vwap) |
| Price proxy | `HLC3 = (High + Low + Close) / 3`  [litefinance](https://www.litefinance.org/blog/for-beginners/best-technical-indicators/anchored-vwap/) |
| Hourly pivot window | `left=5`, `right=5`  [stackoverflow](https://stackoverflow.com/questions/78577366/how-to-indicate-absolute-pivot-highs-and-lows) |
| Daily pivot window | `left=3`, `right=3`  [stackoverflow](https://stackoverflow.com/questions/78577366/how-to-indicate-absolute-pivot-highs-and-lows) |
| Update policy | Dynamic anchor that refreshes only after a confirmed and significant pivot  [ctrader](https://ctrader.com/products/2684) |
| Significance filter | Structure filter plus ATR threshold  [de.tradingview](https://de.tradingview.com/script/9hEVEaz2/) |
| ATR period | `ATR(14)`  [chartschool.stockcharts](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/average-true-range-atr-and-average-true-range-percent-atrp) |

Recommended project defaults for the ATR threshold are `0.75 × ATR(14)` on hourly bars and `1.0 × ATR(14)` on daily bars, because hourly bars are noisier while daily bars are structurally cleaner. This is a project choice, not a universal law, and it should be treated as the first serious baseline for ablation rather than as a permanent truth. [tradingview](https://www.tradingview.com/script/ls35sRAp-ZigZag-With-ATR-Filter-vnhilton/)

## Formula details

**1) Price proxy**
Each bar is reduced to one representative price using HLC3:
\[
P_t = \frac{High_t + Low_t + Close_t}{3}
\]
This is a common AVWAP input choice because it uses the bar’s range and close rather than only the closing print. [toslc.thinkorswim](https://toslc.thinkorswim.com/center/reference/thinkScript/Functions/Fundamentals/hlc3)

**2) AVWAP formula**
Once an anchor bar \(a\) has been accepted, AVWAP at time \(t\) is computed as:
\[
AVWAP_t = \frac{\sum_{i=a}^{t} (P_i \cdot Volume_i)}{\sum_{i=a}^{t} Volume_i}
\]
Anchored VWAP references describe exactly this cumulative price-times-volume over cumulative volume logic starting from the selected anchor point. [morpher](https://www.morpher.com/blog/anchored-vwap)

**3) True Range and ATR(14)**
ATR is a volatility indicator, not a direction indicator, and it is built from True Range rather than from volume. True Range for bar \(t\) is: [en.wikipedia](https://en.wikipedia.org/wiki/Average_true_range)
\[
TR_t = \max \Big( High_t - Low_t,\; |High_t - Close_{t-1}|,\; |Low_t - Close_{t-1}| \Big)
\]
This formula is used because it captures both intrabar range and gaps from the previous close. [chartschool.stockcharts](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/average-true-range-atr-and-average-true-range-percent-atrp)

The first ATR(14) is the average of the first 14 True Range values, and later values are updated using Wilder’s smoothing. A standard recursive form is: [howthemarketworks](https://www.howthemarketworks.com/rewrites/average-true-range-atr/)
\[
ATR^{first}_{14} = \frac{TR_1 + TR_2 + \cdots + TR_{14}}{14}
\]
\[
ATR_t = \frac{(ATR_{t-1} \cdot 13) + TR_t}{14}
\]
Wilder’s 14-period default is the standard convention in major ATR references. [en.wikipedia](https://en.wikipedia.org/wiki/Average_true_range)

**4) Pivot detection**
A candidate swing high at bar \(i\) is detected when its high is the maximum within a left-right window, and a candidate swing low is detected when its low is the minimum within that window. For a pivot high: [stackoverflow](https://stackoverflow.com/questions/78577366/how-to-indicate-absolute-pivot-highs-and-lows)
\[
High_i = \max(High_{i-L}, \ldots, High_i, \ldots, High_{i+R})
\]
For a pivot low:
\[
Low_i = \min(Low_{i-L}, \ldots, Low_i, \ldots, Low_{i+R})
\]
Here, \(L\) and \(R\) are the chosen left and right parameters, which are `5,5` for hourly and `3,3` for daily in this project. [youtube](https://www.youtube.com/watch?v=5I8rLVvcbok)

## Tricky part

The most important implementation detail is that a pivot is **not usable** when the candidate bar first appears. A pivot at bar \(i\) only becomes confirmed after the \(R\) right-side bars have closed, which means the whole anchor-update process begins on bar \(i+R\), not on bar \(i\) itself. [mhtechin](https://www.mhtechin.com/support/look-ahead-bias-in-rolling-window-features/)

Example: with `left=3` and `right=3`, bar 3 can only be confirmed once bar 6 has closed, because only then do we have the full 7-bar window from bar 0 to bar 6 needed to test the pivot rule. That is why the AVWAP anchor must not be updated on rows 3, 4, or 5 in that example; the first row allowed to use that pivot as an anchor is row 6, otherwise the feature leaks future information into earlier rows. [reddit](https://www.reddit.com/r/TradingView/comments/17m88to/caution_this_strategy_may_use_lookahead_bias/)

After confirmation, the pivot still does **not** automatically become the new anchor. It must first pass the significance filter, because in noisy or choppy markets many local pivots are too small to be worth resetting the AVWAP reference. [de.tradingview](https://de.tradingview.com/script/9hEVEaz2/)

## Significance filter

The significance filter is a second gate applied **after** pivot confirmation. Its job is to decide whether the confirmed pivot is important enough to replace the current active anchor. [tradingview](https://www.tradingview.com/script/hB6MTxof-Filtered-Swing-Pivot-S-R/)

For this project, the filter has two parts:

- **Structure filter:**
  Accept a new swing high only if it is higher than the last accepted swing high, and accept a new swing low only if it is lower than the last accepted swing low. [de.tradingview](https://de.tradingview.com/script/9hEVEaz2/)

- **ATR threshold filter:**
  Accept the pivot only if the move is large enough relative to recent volatility, using `ATR(14)` as the volatility yardstick. [tradingview](https://www.tradingview.com/script/ls35sRAp-ZigZag-With-ATR-Filter-vnhilton/)

Mathematically, for a new confirmed swing high at bar \(i\):
\[
High_i > High_{last\_accepted\_high}
\]
and
\[
High_i - High_{last\_accepted\_high} \ge k \cdot ATR_{14,i}
\]
where \(k\) is the chosen multiplier, set to `0.75` for hourly and `1.0` for daily in this project. The swing-low rule is the symmetric opposite using lows instead of highs. [chartschool.stockcharts](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/average-true-range-atr-and-average-true-range-percent-atrp)

In plain English, this means a pivot must be both structurally stronger and far enough away in volatility terms to count as a real update. If it fails either test, the current AVWAP anchor stays unchanged. [tradingview](https://www.tradingview.com/script/hB6MTxof-Filtered-Swing-Pivot-S-R/)

## Simple examples

**A) ATR example**
Suppose a bar has `High=110`, `Low=104`, and the previous close was `107`. Then the three True Range candidates are `6`, `3`, and `3`, so the True Range for that bar is `6` because ATR always uses the maximum of those three distances. [investopedia](https://www.investopedia.com/terms/a/atr.asp)

Suppose the last 14 True Range values average to `1.5`. Then `ATR(14)=1.5` for that bar, but that is just the current output of the indicator, not a fixed constant, because ATR changes over time with volatility. [tastylive](https://www.tastylive.com/concepts-strategies/average-true-range-atr)

**B) Pivot confirmation example**
With `left=3` and `right=3`, suppose bar 3 looks like a possible swing high. We do nothing at bars 3, 4, or 5, because the right-side confirmation window is still incomplete. [de.tradingview](https://de.tradingview.com/scripts/higherhigh/)

When bar 6 closes, we can finally test whether `High [alchemymarkets](https://alchemymarkets.com/education/indicators/anchored-vwap/)` is the maximum of bars `0..6`. If yes, bar 3 becomes a confirmed pivot high **on bar 6**, and only from bar 6 onward can it enter the significance filter and possibly replace the active anchor. [patternswizard](https://patternswizard.com/pivot-point-high-low/)

**C) Significance filter example**
Assume the last accepted swing high was `108`, the new confirmed swing high is `110`, and current `ATR(14)=1.5`. If the daily multiplier is `1.0`, then the required move is `1.5`, and the actual move is `110 - 108 = 2.0`, so the pivot passes the ATR threshold and can be accepted if it also passes the higher-high rule. [chartschool.stockcharts](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/average-true-range-atr-and-average-true-range-percent-atrp)

If instead the new swing high were `108.8`, then the move would be only `0.8`, which is below `1.5`, so the pivot would be ignored and the active anchor would remain unchanged. This is exactly how the filter prevents constant anchor resets in noisy markets. [de.tradingview](https://de.tradingview.com/script/9hEVEaz2/)

## Bar requirements

The table below states how much history each piece needs before it can be computed safely.

| Element | Required bars / inputs | Notes |
|---|---|---|
| HLC3 | Current bar only: `High`, `Low`, `Close`  [litefinance](https://www.litefinance.org/blog/for-beginners/best-technical-indicators/anchored-vwap/) | No warm-up needed |
| True Range | Current `High`, current `Low`, previous `Close`  [investopedia](https://www.investopedia.com/terms/a/atr.asp) | Needs one previous close |
| First ATR(14) | 14 True Range values  [chartschool.stockcharts](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/average-true-range-atr-and-average-true-range-percent-atrp) | Practical warm-up is 14 bars, with a previous close available for normal TR calculation |
| Pivot detection | `L` bars left, current bar, `R` bars right  [stackoverflow](https://stackoverflow.com/questions/78577366/how-to-indicate-absolute-pivot-highs-and-lows) | Total window = `L + 1 + R` |
| Pivot usability | Confirmed only on bar `i+R`  [mhtechin](https://www.mhtechin.com/support/look-ahead-bias-in-rolling-window-features/) | This is the leakage-safe start of update logic |
| Significance filter | Confirmed pivot, previous accepted same-side pivot, ATR(14)  [de.tradingview](https://de.tradingview.com/script/9hEVEaz2/) | Runs only after confirmation |
| AVWAP | All bars from accepted anchor to current bar, using price proxy and volume  [chartschool.stockcharts](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/anchored-vwap) | No fixed lookback; running sums can be maintained incrementally |

## Implementation logic

The implementation should follow this order on each new bar:

1. Compute HLC3 for the current bar. [litefinance](https://www.litefinance.org/blog/for-beginners/best-technical-indicators/anchored-vwap/)
2. Update True Range and ATR(14) once enough bars exist. [howthemarketworks](https://www.howthemarketworks.com/rewrites/average-true-range-atr/)
3. Check whether a pivot from \(R\) bars ago is now confirmable, because only closed right-side bars may be used. [mhtechin](https://www.mhtechin.com/support/look-ahead-bias-in-rolling-window-features/)
4. If a pivot is confirmed, send it through the significance filter using structure plus ATR threshold. [tradingview](https://www.tradingview.com/script/hB6MTxof-Filtered-Swing-Pivot-S-R/)
5. If the pivot passes, replace the active anchor with that pivot bar; otherwise keep the old anchor. [de.tradingview](https://de.tradingview.com/script/9hEVEaz2/)
6. Recompute or incrementally update AVWAP from the active anchor and expose `AVWAP_Dist = (Close / Active_AVWAP) - 1` as the feature column. [morpher](https://www.morpher.com/blog/anchored-vwap)
