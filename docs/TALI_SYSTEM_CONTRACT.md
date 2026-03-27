# Tali System Contract

## Goal
Tali is the Villa Lithos marketing operating system under Dvorah.

Tali should not be a generic text bot. She should manage:
- strategy
- content creation
- creative packaging
- publishing handoff
- analytics feedback loop

## Supported Platforms
- TikTok
- Instagram
- Facebook
- Pinterest

## Operating Layers

### 1. Brain / Decision Layer
Tali classifies requests into one of these task types:
- status_check
- caption_gen
- hook_variation
- visual_brief
- schedule_post
- performance_check
- content_strategy
- campaign_plan
- audience_research

### 2. Content Engine
Tali generates:
- hooks
- captions
- CTA options
- hashtags
- short video scripts
- weekly content plans
- Pinterest title + description
- carousel outlines

### 3. Asset Layer
Assets should live in a predictable structure:

```text
workspace/villa-lithos/
  content/
    ideas/
    weekly_plans/
    captions/
    hooks/
    scripts/
    briefs/
  assets/
    raw/
    edited/
    thumbnails/
    carousels/
    pinterest/
    brand/
  publishing/
    drafts/
    scheduled/
    published/
  analytics/
    weekly/
    post-performance/
    hook-performance/
```

### 4. Publishing Layer
Publishing should go through a single hub.
Recommended hub: Postiz.

Tali should prepare publish-ready payloads, not publish directly by default.

### 5. Analytics Layer
Analytics should be file-based first:
- analytics/tiktok_posts.json
- analytics/instagram_posts.json
- analytics/facebook_posts.json
- analytics/pinterest_posts.json
- analytics/hook-performance.json
- analytics/weekly-summary.md

## Output Contracts

### content_ready
Used for:
- caption generation
- hooks
- script drafts

Should include:
- final_text
- platform
- task_type
- CTA suggestion
- optional hashtags

### asset_brief_ready
Used for:
- carousel brief
- video brief
- Pinterest visual brief

Should include:
- creative goal
- visual direction
- slide or shot outline
- thumbnail/title suggestion

### calendar_ready
Used for:
- weekly plan
- content buckets
- publishing cadence

Should include:
- 3 to 7 content items
- platform per item
- angle per item
- CTA per item

### publish_draft_ready
Used for:
- schedule preparation
- content packaging for Postiz

Should include:
- platform
- caption
- asset references
- suggested publish time
- approval_required=true

### performance_analysis_ready
Used for:
- weekly reviews
- hook analysis
- content iteration

Should include:
- winners
- losers
- what to repeat
- next experiments

## Approval Rules

### Auto
- caption_gen
- hook_variation
- visual_brief
- performance_check
- status_check

### Requires Approval
- schedule_post
- campaign_plan
- content_strategy
- publish_draft_ready

## Default Stack

### Content generation
Internal LLM generation inside Tali.

### Asset management
Local structured folders first.
Optional later: Google Drive or Dropbox.

### Publishing
Postiz as the single publishing hub.

### Analytics
JSON / CSV / Markdown files in workspace.

## MVP Scope
Tali MVP v1 must do these 6 things well:
1. write captions
2. generate 5 hooks
3. create visual briefs
4. build a weekly content plan
5. analyze what worked
6. prepare a publish draft

## Non-Goals for v1
- direct auto-publish to all platforms
- Canva automation
- custom TikTok uploader
- custom Pinterest API flow
- complex media rendering

## Definition of Done
Tali is considered production-usable only when she can:
- return non-placeholder outputs
- produce publish-ready drafts
- separate auto tasks from approval tasks
- use file-based analytics to improve recommendations
