# frontend/src/components/stock/SentimentTab.tsx

## Purpose
Displays earnings call sentiment analysis — tone scores, keyword frequency, and QoQ tone delta.

## Sections

### 1. Tone Score Over Quarters
- Bar chart: "bullish keyword count" vs "cautious keyword count" per quarter (last 4 quarters)
- Grouped bars side by side, green vs amber
- QoQ delta arrow: "↑ Tone improved" or "↓ Tone deteriorated"

### 2. Current Quarter Summary
- Large card: current tone label (e.g., "Cautiously Optimistic") with a color-coded indicator
- Guidance stance: raised / maintained / lowered / withdrawn — with corresponding color
- CEO vs. CFO alignment: "aligned" or "divergent" with explanation

### 3. Keyword Frequency
Two columns:
- **Bullish Terms** (green): list with occurrence count badge
- **Cautious Terms** (amber): list with occurrence count badge

### 4. QoQ Delta Summary
Plain-text AI-generated paragraph from the sentiment sub-report describing how tone has shifted over the last 4 quarters.

## Dependencies
- `recharts`
- Sentiment sub-report from `useStockSignals`
