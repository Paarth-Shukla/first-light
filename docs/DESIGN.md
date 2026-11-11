# First Light — design system

The design is "The Bulletin": contemporary editorial design in the Swiss tradition. The reference implementation is the static prototype in `design/prototypes/bulletin/` (`index.html` front page, `components.html` stylebook, `styles.css` tokens and components, `fonts/`). When the app and the prototype disagree on look, the prototype wins unless this file says otherwise.

## The one idea

**Coverage is the typography.** A story's headline size, width, weight and column span come from how many outlets carried it (`sourceCount`), on a seven-step scale. Each story carries a tick mark per outlet. Nothing is big for decoration.

## Rules

- Two kinds of numeral: numerals on black tiles say where you are (edition number as split-flap digits, desk numbers 01–10, ranks); numerals with ticks say how big a story is.
- One spot colour (vermilion). It marks the live and the important: the rising sun, the lead's outlet count, unread marks, falls in markets, the Claude Desk block. Never a headline colour.
- Rules and bars, not cards. No shadows, no rounded panels, no gradients, no emoji.
- Mono for every figure, time, tag and key hint, with tabular numerals. Up and down always carry an arrow and a sign, never colour alone.
- Stories without a summary close with a stub rule and source line; they must look intended.
- The night edition is designed, not inverted: lamp-black paper, off-white signs, vermilion kept for the same meanings.
- The front page is finite. It ends with "— 30 —" and a line stating the count and reading time.
- Phone: single column, 16px gutters, bottom tab bar (Front, Wire, Desks, Markets, More), no horizontal page scroll, touch targets at least 40px.
- Motion is functional and short; all of it is removed under `prefers-reduced-motion`.

## Grafted from the other prototypes

- From `design/prototypes/broadsheet/`: a reading-progress marker ("12 of 41") that advances as stories are read; on phones a 2px line under the top bar.
- From `design/prototypes/gazette/`: a one-line "why it leads" note under the lead, generated from the story's `why` reasons.

## Vocabulary

Front Page, The Wire, desks (sections), Markets, Weekend Review, Claude Desk, Clippings (saved), Back Issues (archive), Colophon (status and about), night edition / day edition.
