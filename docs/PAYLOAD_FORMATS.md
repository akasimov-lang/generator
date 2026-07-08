# Payload Formats

The publication payload supports two site modes.

## Simple Page

Use this for sites where showcase data, casino cards, author widgets and other
components already exist on the target site and are inserted through shortcodes.

```json
{
  "menu": {
    "header": [],
    "footer": []
  },
  "pages": [
    {
      "id": "generated",
      "slug": "/page-slug/",
      "title": "Page title",
      "publishedTime": "2026-07-08 12:00:00",
      "description": "Meta description",
      "updatedTime": "2026-07-08 12:00:00",
      "breadcrumb": "Page title",
      "content": {
        "time": 1783512000000,
        "blocks": [],
        "version": "2.31.0"
      },
      "head": [],
      "banners": []
    }
  ]
}
```

## Full Site

Use this for sites where the payload must also carry showcase/casino data.

```json
{
  "menu": {},
  "pages": [],
  "casinos": {
    "basic": [],
    "standard": []
  }
}
```

## Supported Editor.js Blocks

- `header`
- `paragraph`
- `list`
- `table`
- `shortcode`
- `image`
- `faq`
- `toc`
- `quote`
- `plusMinus`

AI generation should fill text blocks. Menu, shortcodes and showcase datasets
should come from site settings or templates.

