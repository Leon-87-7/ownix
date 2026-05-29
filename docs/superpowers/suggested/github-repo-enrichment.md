# Feature Request: On-the-Fly Repository Enrichment

> **⚠️ Scope note (2026-05-29):** this document describes the
> **photo-pipeline repo-enrichment post-processor** — it decorates a list of
> github.com links extracted by Gemini Vision from an image with metadata
> (stars/forks/lang/last-push). It is **not** about the
> [`repo pipeline`](../../features/postgrill/repo-url-feature.md) (single-URL
> Gemini analysis with use-case framing). Those are distinct concepts and
> share only the GitHub REST API client. The photo post-processor has
> already shipped (see CONTEXT.md `Repo enrichment` glossary entry); this
> doc is preserved as background and as the source of the optional
> filter-buttons enhancement listed at the bottom.

**PROPOSED CATEGORY**: ENHANCEMENT • **PRIORITY**: HIGH • **COMPLEXITY**: MEDIUM

## Problem Statement

Currently, the bot extracts links from images and returns a plain list with minimal context. Users receive repository names and URLs, but must manually visit each repo to evaluate:

- Project popularity and community adoption
- Maintenance status and activity level
- Primary programming language/stack compatibility
- Whether the project is production-ready or experimental

This creates friction in the discovery process. A list of 20+ repos without metadata requires users to open multiple browser tabs, check stars, scan commit history, and assess relevance — all before determining which 2-3 tools actually fit their needs.

## Proposed Solution

Enrich each extracted repository link with real-time metadata from the GitHub API before sending the formatted list to the user.

## Enriched Data Points

For each repository URL detected, fetch and display:

1. **Star count** — Proxy for community adoption and trust
2. **Last commit date** — Indicates active maintenance vs. abandoned projects
3. **Primary language** — Helps filter by stack compatibility (TypeScript, Python, Rust, etc.)
4. **Fork count** (optional) — Additional signal for project health
5. **Open issues count** (optional) — Indicator of community engagement and potential bugs

## Example Output Format

```
CURRENT OUTPUT:
• Claude Code — GitHub repository for Claude Code.
  🔗 http://github.com/anthropics/claude-code

ENRICHED OUTPUT:
• Claude Code — Official Anthropic CLI tool for agentic coding
  ⭐ 8,234 | 📅 Updated 3 days ago | 💻 TypeScript
  🔗 http://github.com/anthropics/claude-code

WITH STATUS INDICATORS:
• Claude Engineer — Autonomous coding assistant with tool use
  ⭐ 12,451 | 📅 Updated 2 weeks ago | 💻 Python | ⚠️ 127 open issues
  🔗 http://github.com/Doriandarko/claude-engineer

• [INACTIVE] SuperClaude Framework — Multi-agent orchestration
  ⭐ 342 | 📅 Last updated 8 months ago | 💻 JavaScript
  🔗 http://github.com/SuperClaude-Org/SuperClaude_Framework
```

## Technical Implementation

### API Integration

Use GitHub REST API v3 for metadata fetching:

```python
import requests
from datetime import datetime, timedelta

def enrich_repo(repo_url):
    # Extract owner/repo from URL
    # e.g., "http://github.com/anthropics/claude-code" -> "anthropics/claude-code"

    api_url = f"https://api.github.com/repos/{owner}/{repo}"

    response = requests.get(api_url, headers={
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    })

    if response.status_code == 200:
        data = response.json()
        return {
            "stars": data["stargazers_count"],
            "last_updated": data["pushed_at"],
            "language": data["language"],
            "forks": data["forks_count"],
            "open_issues": data["open_issues_count"],
            "description": data["description"]
        }
    else:
        return None
```

### Caching Strategy

To avoid rate limits and reduce latency:

1. **Cache enriched data with TTL of 24 hours**
   - Key: `repo:{owner}/{name}`
   - Value: JSON blob with metadata + timestamp
2. **Batch API requests when processing lists**
   - Use GitHub GraphQL API for multi-repo queries in single request
   - Fallback to REST API if GraphQL unavailable
3. **Rate limit handling**
   - GitHub allows 5,000 requests/hour for authenticated users
   - Implement exponential backoff if limits approached
   - Display cached data with staleness indicator if API unavailable

### Activity Status Labels

Automatically flag repositories based on last commit date:

- **Active**: Last commit within 30 days → ✅ or no label
- **Maintained**: Last commit 1-3 months ago → no label
- **Stale**: Last commit 3-6 months ago → ⚠️ (yellow warning)
- **Inactive**: Last commit >6 months ago → 🔴 or `[INACTIVE]` prefix

### Fallback Behavior

If GitHub API enrichment fails for any repo:
- Return the basic extracted link (current behavior)
- Log the failure for debugging
- Do NOT block the entire response waiting for API

## User Experience Improvements

### Visual Hierarchy

Use emoji icons for quick scanning:
- ⭐ Star count
- 📅 Last updated
- 💻 Primary language
- 🔀 Fork count
- ⚠️ Open issues / warnings

### Optional: Inline Filtering Buttons

After sending enriched list, provide Telegram inline keyboard buttons:

```
[Show All] [Active Only] [By Stars ⬇️] [Python] [TypeScript] [Rust]
```

Clicking filters re-renders the list based on selected criteria.

## Edge Cases & Considerations

1. **Non-GitHub repositories** — Skip enrichment, return plain link
2. **Private/deleted repos** — Handle 404 gracefully, mark as `[UNAVAILABLE]`
3. **Organization vs. user repos** — Same API endpoint works for both
4. **Monorepos with multiple languages** — Display primary language only
5. **Archived repositories** — GitHub API returns `archived: true` flag → display `[ARCHIVED]` label

## Success Metrics

- **Reduced click-through rate** — Users evaluate repos from enriched data without opening every link
- **Faster discovery** — Time from "comment 'repo'" to installing relevant tool decreases
- **Higher engagement** — Users interact with more diverse repos instead of defaulting to top 3 names

## Alternatives Considered

**Alternative 1: Static Pre-Enriched Lists** — Manually curate and update metadata in source images.
Rejected: requires constant manual updates, metadata goes stale quickly, doesn't scale.

**Alternative 2: External "Awesome List" Aggregator** — Redirect users to a web dashboard.
Rejected: adds friction (leaves Telegram context), requires maintaining separate web service.

## Open Questions

1. Should we display repository descriptions from GitHub, or stick to original OCR-extracted text?
2. What's the threshold for flagging "too many open issues"? Suggested: >100 open issues AND >10% of total issues are open
3. Should we fetch additional data like license type, contributor count, or latest release version?

## Implementation Checklist

- [ ] Set up GitHub API authentication (personal access token or GitHub App)
- [ ] Implement repo URL parsing and validation
- [ ] Build GitHub API client with rate limit handling
- [ ] Design enriched message template
- [ ] Implement Redis/in-memory caching layer
- [ ] Add activity status labeling logic
- [ ] Handle API failures gracefully (fallback to basic links)
- [ ] Test with various repo types (active, archived, private, deleted)
- [ ] Add optional inline filter buttons
- [ ] Monitor API usage and optimize batch requests
- [ ] Document configuration (API tokens, cache TTL, status thresholds)

## Future Enhancements

- Trending indicators — Flag repos with recent star velocity spikes
- Compatibility matrix — Show which tools work together
- Personalized recommendations — "Based on your starred repos, you might like..."
- Changelog summaries — Pull latest release notes for recently updated repos
