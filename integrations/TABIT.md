# Tabit Integration
<!-- Status: Partial -->
<!-- Purpose: Restaurant booking via Tabit platform -->

## Overview
Tabit (tabit.cloud) is Israel's restaurant management and booking platform.
Many Israeli restaurants use Tabit for reservations alongside or instead of Ontopo.

## URL Patterns

### Reservation Page (Israel)
```
https://tgm-rsv.tabit.cloud/#!/{restaurant_id}/booking/search
```
- Restaurant IDs are **24-character hexadecimal strings** (MongoDB ObjectIds)
- Example: `5b2a05572ee2b91700125eb6`

### Reservation Page (US)
```
https://us-tgm-rsv.tabit.cloud/#!/{restaurant_id}/booking/search
```

### Online Ordering (US)
```
https://us-tabitorder.tabit.cloud/{restaurant_slug}
```

## Known Restaurant IDs
See `state/RESTAURANT_SLUGS.json` under the `tabit` section.

**Important**: Tabit has **no public restaurant directory or search API**.
Each restaurant gets its own booking page with a unique MongoDB-style ID.

## How to Find Tabit Restaurant IDs

1. **Tabit App**: Download the Tabit app (iOS/Android) - it has built-in search by location showing real-time availability
2. **Google Search**: Search `"tgm-rsv.tabit.cloud" {restaurant_name}` to find booking pages
3. **Restaurant Websites**: Many restaurants link to their Tabit booking page from their own website
4. **Google Maps**: Some restaurants show a "Reserve a table" button that links to Tabit

## Platform Details

| Subdomain | Purpose |
|-----------|---------|
| `tgm-rsv.tabit.cloud` | Reservations (Israel) |
| `us-tgm-rsv.tabit.cloud` | Reservations (US) |
| `tgm-rsvbeta.tabit.cloud` | Reservations (Beta) |
| `reservations.tabit.cloud` | General portal |
| `us-tabitorder.tabit.cloud` | Online ordering (US) |
| `tabitisrael.co.il` | Israeli portal |

"TGM" = TabitGuest Manager

## Limitations
- No public API for listing restaurants
- No public search endpoint
- Restaurant IDs must be discovered individually
- The reservation pages use hash-based SPA routing (`#!/`)

## Notes
- Tabit is the more common platform for walk-in/casual restaurants
- Many restaurants use BOTH Ontopo and Tabit
- The Tabit app shows real-time table availability by area
- Reservation requires: name, number of guests, date, email, phone
