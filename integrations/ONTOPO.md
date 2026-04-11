# Ontopo Integration
<!-- Status: Active -->
<!-- Purpose: Restaurant booking via Ontopo platform -->

## Overview
Ontopo (ontopo.com) is Israel's leading restaurant reservation platform.
Dvorah uses it to search restaurants and check availability for Yoni.

## URL Patterns

### Restaurant Page
```
https://ontopo.com/en/il/page/{slug_or_id}
```
- Slugs can be **text** (e.g., `taizu`, `machneyuda`, `onza`) or **numeric IDs** (e.g., `83077556`)
- Both formats work identically

### City Browsing
```
https://ontopo.com/en/il/{city}
```
Cities: `tel-aviv`, `jerusalem`, `haifa`, `herzliya`, `raanana`, `ramat-gan`, `netanya`, `ashdod`, `ashkelon`, `beer-sheva`, `eilat`, `modiin`, `rehovot`, `rishon-lezion`, `petah-tikva`, `holon`, `kfar-saba`, `hod-hasharon`

### Tag Filtering
```
https://ontopo.com/en/il/{city}/tags/{tag}
```
Tags: `tasting_menu`, `romantic`, `kosher`, `israeli`, `italian`, `asian`, `seafood`, `steak`, `safe_zone`

### Menu Page (ontopo.co.il)
```
https://ontopo.co.il/en/{slug}/menu
```

## Restaurant Database
Full slug list: `state/RESTAURANT_SLUGS.json`
Contains 140+ restaurants organized by city with name, slug, cuisine type, and kosher status.

## How to Search for a Restaurant

1. **By name**: Look up in `state/RESTAURANT_SLUGS.json` by name
2. **By city**: Filter the JSON by city key (e.g., `tel_aviv`, `jerusalem`)
3. **By cuisine**: Filter by the `cuisine` field
4. **By kosher**: Filter by `kosher: true`
5. **Browse online**: Navigate to `https://ontopo.com/en/il/{city}`

## How to Build a Booking URL

Given a slug (e.g., `taizu`):
```
https://ontopo.com/en/il/page/taizu
```

This page shows:
- Restaurant info, photos, menu
- Availability calendar
- Direct booking widget

## Internal API (Unofficial)

These endpoints power the Ontopo website. No auth required but may be rate-limited:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/venue_search?query={name}` | GET | Search restaurants by name |
| `/api/venue_profile?slug={slug}` | GET | Get venue details |
| `/api/availability_search` | POST | Check table availability |

## Notes
- Checkout links (`s1.ontopo.com/checkout/...`) expire in ~15 minutes
- Hebrew interface: `ontopo.com/he/il/page/{slug}`
- The `bestof2025` page lists the 30 most popular restaurants
- Multi-branch restaurants have a `/branches` subpath
