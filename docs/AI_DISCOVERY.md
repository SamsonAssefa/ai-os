# AI and search discovery

AI OS is working toward an open foundation for AI-first computing, where agents are first-class users and people retain control of identity, data, permissions, spending, and consequential actions. The current release is an early self-hosted coordination workspace, not a desktop OS. See the [north star and roadmap](PRODUCT_ROADMAP.md) for the staged path toward an AI-native workspace and a possible standalone Linux-based distribution.

An optional model planner can draft (but cannot execute) a bounded task plan through a configured OpenAI-compatible endpoint. It is disabled by default, requires explicit consent for each prompt, and keeps provider credentials on the server.

AI OS also provides readable project documentation, descriptive HTML metadata, SoftwareApplication structured data, `llms.txt`, a robots policy, a sitemap route, an OpenAPI 3.1 schema, stateless MCP `2026-07-28` tools with legacy `2025-11-25` compatibility, and an A2A 1.0 Agent Card with a limited JSON-RPC proposal profile. Discovery metadata does not grant API access. A2A clients can propose work; a human must approve an objective before tasks can be queued.

## Local and hosted behavior

Localhost cannot be crawled by public search engines or AI assistants. Publishing source to GitHub makes the repository and its docs readable, but it does not publish the web application as a public website.

When you host the app, set `AIOS_PUBLIC_URL` to the actual public HTTPS origin, such as `https://ai-os.example.org`. The service uses it for sitemap URLs, the robots sitemap location, and the A2A service URL. Configure the host, HTTPS, authentication, CORS, and secret storage before exposing a service. Setting this variable does not deploy the application.

Submit the hosted sitemap to search engine webmaster tools if desired. Crawler access depends on DNS, hosting policy, robots rules, network access, and the crawler's own policies. Metadata cannot guarantee indexing or inclusion in AI answers.

## Content principles

Keep the overview, manual, API schema, extension permissions, supported protocols, and limitations consistent. Use stable public URLs. Do not publish access tokens, private customer information, or internal production data. Discovery files help an integration find documented interfaces; they are not an authentication mechanism.
