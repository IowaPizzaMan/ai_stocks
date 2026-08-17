# Feature Specification: Remove Stocks from Watchlist and Stocks Page

**Feature Branch**: `023-remove-stocks`

**Created**: 2026-08-16

**Status**: Draft

**Input**: User description: "I need a way to remove stocks from my watch list. I also need a way to remove stocks from my stock page. When I remove them from my stock page, I also want to delete the data I have on that stock. I think when you hover over the item in the watch list or the stock ticker container on the 'Stocks' page I want to see an 'x' for remove."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Unpin a stock from the watchlist (Priority: P1)

The user is looking at their watchlist and sees a ticker they no longer care to track
closely. They hover over that watchlist entry, an "x" appears on the row, they click it,
and the ticker disappears from the watchlist immediately. Everything the system already
knows about that stock — its past analyses, cached fundamentals, news — is left untouched,
because the user is only saying "stop pinning this," not "forget this."

**Why this priority**: This is the lowest-risk half of the request and the one the user
hits most often. The watchlist is a curation surface — it becomes noise the moment it can
only grow. It is also fully reversible (the ticker can be re-added), so it delivers value
with no data-loss risk.

**Independent Test**: Can be fully tested by adding two tickers to the watchlist, hovering
one, clicking its "x", and confirming that entry leaves the list while the other remains
and while the removed ticker's stock detail page still shows its prior analysis.

**Acceptance Scenarios**:

1. **Given** the watchlist contains at least one ticker, **When** the user hovers over a
   watchlist entry, **Then** a remove ("x") control appears on that entry and on no other
   entry.
2. **Given** the user is hovering a watchlist entry, **When** they click the "x", **Then**
   that ticker is removed from the watchlist and the list re-renders without it, without a
   full page reload.
3. **Given** a ticker has been removed from the watchlist, **When** the user opens that
   ticker's stock detail page, **Then** its previously stored analysis, fundamentals, and
   other cached data are still available.
4. **Given** the user clicks the "x" on a watchlist entry, **When** the removal is in
   flight, **Then** navigation to that ticker's detail page is not triggered by the same
   click.
5. **Given** the removal request fails, **When** the failure is returned, **Then** the
   entry reappears in the watchlist and the user is shown an error message explaining the
   removal did not take effect.

---

### User Story 2 - Delete a stock and its stored data from the Stocks page (Priority: P2)

The user is scanning the tile board on the Stocks page and decides a ticker no longer
belongs in the system at all — it was a bad pull, a delisted name, or simply not something
they follow. They hover its tile, an "x" appears in the corner, they click it, confirm the
destructive action, and the tile disappears. The system discards everything it had stored
for that stock: analyses, cached fundamentals, transcripts, news, institutional and
earnings records, its watchlist pin, and any not-yet-run work queued for it.

**Why this priority**: This is the higher-value cleanup (it reclaims storage and de-noises
the board) but it is destructive and irreversible, so it ships after the safe removal path
in User Story 1 is proven.

**Independent Test**: Can be fully tested by analysing a ticker so it has stored data,
deleting it from the Stocks page tile, and confirming the tile is gone, the ticker no
longer appears in search or the tracked-ticker list, and its detail page reports no data.

**Acceptance Scenarios**:

1. **Given** the Stocks page tile board is displayed, **When** the user hovers a ticker
   tile, **Then** a remove ("x") control appears on that tile and on no other tile.
2. **Given** the user is hovering a tile, **When** they click the "x", **Then** they are
   asked to confirm a destructive deletion that names the ticker and states that its stored
   data will be deleted.
3. **Given** the confirmation prompt is shown, **When** the user cancels, **Then** nothing
   is deleted and the tile remains on the board.
4. **Given** the confirmation prompt is shown, **When** the user confirms, **Then** the
   ticker is removed from the tracked universe, all stored data for that ticker is deleted,
   and the tile disappears from the board without a full page reload.
5. **Given** a deleted ticker was also on the watchlist, **When** the deletion completes,
   **Then** it is gone from the watchlist as well.
6. **Given** a deleted ticker had pending or running queued work, **When** the deletion
   completes, **Then** that queued work no longer produces a new analysis for the ticker.
7. **Given** the user clicks the "x" on a tile, **When** the removal is in flight, **Then**
   navigation to that ticker's detail page is not triggered by the same click.
8. **Given** the deletion request fails, **When** the failure is returned, **Then** the tile
   remains on the board and the user is shown an error message explaining nothing was
   deleted.

---

### User Story 3 - Reach both remove controls without a mouse (Priority: P3)

A user navigating by keyboard, or relying on a screen reader, needs the same removal
ability as a mouse user. Moving focus onto a watchlist entry or a stock tile reveals its
remove control, the control is reachable in the tab order, it announces which ticker it
removes and whether it is destructive, and it activates from the keyboard.

**Why this priority**: The hover-only affordance the user described is inherently
mouse-dependent; this story closes that gap. It is separable from P1/P2 because the removal
behaviour itself already works — this only changes how the control is reached and announced.

**Independent Test**: Can be fully tested by tabbing to a watchlist entry and a stock tile
with no pointer involved, confirming each remove control becomes visible and focusable, and
activating each one from the keyboard.

**Acceptance Scenarios**:

1. **Given** keyboard focus moves onto a watchlist entry or a stock tile, **When** focus
   lands, **Then** that item's remove control becomes visible, exactly as on hover.
2. **Given** the remove control has keyboard focus, **When** the user activates it, **Then**
   the same removal flow runs as for a mouse click, including the confirmation step for the
   destructive Stocks-page deletion.
3. **Given** a screen reader is in use, **When** it reaches a remove control, **Then** it
   announces the action and the ticker it applies to, and distinguishes unpinning from
   deletion.

---

### Edge Cases

- **Last item removed**: removing the only watchlist entry leaves the empty-state message;
  deleting the only tile leaves the board's existing empty state.
- **Same ticker in both places**: deleting from the Stocks page also clears the watchlist
  pin; unpinning from the watchlist leaves the Stocks tile in place.
- **Currently open ticker**: deleting a ticker the user is also viewing on its detail page
  leaves that page showing a "no data" state rather than stale content.
- **Repeat click**: clicking the "x" twice in quick succession removes the item once and
  does not surface a spurious "not found" error.
- **Already gone**: removing a ticker that another view already removed resolves to the
  same end state (item absent) rather than a blocking error.
- **In-flight analysis**: deleting a ticker whose analysis is mid-run must not leave an
  orphaned analysis record that resurrects the ticker on the board.
- **Automated re-discovery**: a deleted ticker that a later automated sweep (earnings
  scanner, institutional flow) encounters again — see FR-014.
- **Touch input**: on a device with no hover, the remove control must still be reachable.
- **Delisted / flagged tickers**: a ticker flagged as removed-from-market is removable by
  the same controls, not a special case.

## Requirements *(mandatory)*

### Functional Requirements

#### Watchlist removal (User Story 1)

- **FR-001**: Users MUST be able to remove a ticker from their watchlist directly from the
  watchlist display, without navigating to another screen.
- **FR-002**: The watchlist remove control MUST be revealed when the user hovers or focuses
  the corresponding watchlist entry, and MUST be hidden when the entry is neither hovered
  nor focused.
- **FR-003**: Watchlist removal MUST be non-destructive: it MUST unpin the ticker only, and
  MUST NOT delete analyses, cached fundamentals, or any other stored data for that ticker,
  nor remove it from the tracked-ticker universe.
- **FR-004**: The watchlist MUST reflect the removal immediately without a full page reload.
- **FR-005**: Activating the remove control MUST NOT also trigger the entry's normal
  navigation behaviour.

#### Stocks-page deletion (User Story 2)

- **FR-006**: Users MUST be able to delete a ticker from the Stocks page tile board directly
  from its tile.
- **FR-007**: The tile remove control MUST be revealed on hover or focus of that tile and
  hidden otherwise, matching FR-002's behaviour.
- **FR-008**: The system MUST require an explicit confirming interaction, distinct from the
  click on the "x", before performing the deletion. Clicking the "x" MUST open an inline
  confirm popover anchored to the tile — naming the ticker and stating that its stored data
  will be deleted — with a Confirm and a Cancel control; the deletion MUST only proceed when
  Confirm is activated.
- **FR-009**: On confirmation, the system MUST delete all data it holds that is scoped to
  that ticker, covering at minimum: analysis records, cached fundamentals, cached earnings
  data, cached transcripts, cached news, institutional/ownership records, the watchlist pin,
  and any pending or running queued work for the ticker.
- **FR-010**: On confirmation, the system MUST remove the ticker from the tracked-ticker
  universe so it no longer appears in the tile board, ticker search, or the tracked-ticker
  list.
- **FR-011**: Deletion MUST be all-or-nothing from the user's perspective: if it cannot
  complete, the user MUST be told nothing was deleted and the ticker MUST remain visible.
- **FR-012**: The tile board MUST reflect the deletion immediately without a full page
  reload.
- **FR-013**: Deleting a ticker MUST NOT prevent the user from adding it back later as a
  brand-new ticker with no history.
- **FR-014**: Deletion is a one-time purge, not a permanent suppression. If an automated
  discovery process (earnings scanner, institutional flow, or similar) later encounters the
  same ticker, it MUST be free to re-add it to the tracked universe as a brand-new ticker
  with no restored history, exactly as if it had never been tracked before.

#### Shared behaviour (User Story 3 and cross-cutting)

- **FR-015**: Both remove controls MUST be reachable and operable by keyboard, and MUST
  expose an accessible label identifying the action and the ticker.
- **FR-016**: The two controls MUST be visually and semantically distinguishable so the user
  can tell the reversible unpin from the destructive deletion before acting.
- **FR-017**: While a removal is in flight, the control MUST indicate that state and MUST
  NOT allow the same removal to be submitted repeatedly.
- **FR-018**: A removal that fails MUST leave the user's view consistent with the server's
  actual state and MUST surface a human-readable error.
- **FR-019**: Removing a ticker that is already absent MUST resolve to the same end state
  (the item is gone from the user's view) rather than presenting a blocking error.

### Key Entities

- **Watchlist entry**: the user's pin on a ticker. Holds the ticker symbol, display name,
  sector, status, and when it was added. Removing it affects only the pin.
- **Tracked ticker**: the system-wide record that a ticker exists in the user's universe,
  including where it was discovered and whether it is active. This is what a Stocks-page
  deletion removes.
- **Per-ticker stored data**: everything the system has accumulated keyed to one ticker —
  analyses, cached fundamentals, earnings data, transcripts, news, institutional/ownership
  records, and queued work. This is the "data I have on that stock" the user wants deleted.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can remove a stock from the watchlist in under 3 seconds and at most
  two interactions (hover, click) from the moment they see it.
- **SC-002**: A user can delete a stock and its data from the Stocks page in under 10
  seconds and at most three interactions (hover, click, confirm).
- **SC-003**: After a Stocks-page deletion, the deleted ticker appears in zero of the app's
  stock-listing surfaces (tile board, watchlist, ticker search, tracked-ticker list).
- **SC-004**: After a Stocks-page deletion, zero stored records scoped to that ticker
  remain in the system.
- **SC-005**: 100% of removals either complete and disappear from the user's view, or fail
  visibly with the item still present — no case where the view and the stored state disagree.
- **SC-006**: Accidental deletion rate is zero in testing: no destructive deletion completes
  without an explicit confirming interaction distinct from the initial click.
- **SC-007**: Both remove controls are operable end-to-end using only a keyboard.

## Assumptions

- The watchlist is displayed in the left-hand navigation rail; "remove from my watch list"
  means removing it there, and no separate watchlist management screen is being introduced
  by this feature.
- "The stock ticker container on the Stocks page" means the per-ticker tile in the Stocks
  page tile board.
- Watchlist removal is deliberately non-destructive and Stocks-page deletion is deliberately
  destructive — the user's phrasing distinguishes the two, and treating unpinning as a purge
  would make the watchlist dangerous to curate.
- The intended deletion scope is every per-ticker record the system holds, including data
  categories added after the existing delete path was written; "delete the data I have on
  that stock" is read as complete, not partial.
- Deletion is irreversible: re-adding a deleted ticker starts it from scratch with no
  restored history. No undo/restore or trash bin is in scope.
- This is a single-user, self-hosted deployment, so there is no permission model, no
  audit-trail requirement, and no concurrent-user conflict to resolve for removals.
- Market-wide and macro data (breadth, sector performance, market news, economic series) is
  not ticker-scoped and is out of scope for deletion.
- The "x" affordance is a small control shown on the item itself; the existing hover
  preview behaviour on stock tiles continues to work and must not be broken by it.
