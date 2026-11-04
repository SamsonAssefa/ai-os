# AI and search discovery

AI OS is working toward an open foundation for AI-first computing, where agents are first-class users and people retain control of identity, data, permissions, spending, and consequential actions. The current release is an early self-hosted coordination workspace, not a desktop OS. See the [north star and roadmap](PRODUCT_ROADMAP.md) for the staged path toward an AI-native workspace and a possible standalone Linux-based distribution.

AI OS also provides readable project documentation, descriptive HTML metadata, SoftwareApplication structured data, `llms.txt`, a robots policy, a sitemap route, an OpenAPI 3.1 schema, MCP tools, and an A2A discovery card. These entry points help people and agents learn what the project supports; they do not grant API access.

## Local and hosted behavior

Localhost cannot be crawled by public search engines or AI assistants. Publishing source to GitHub makes the repository and its docs readable, but it does not publish the web application as a public website.

When you host the app, set `AIOS_PUBLIC_URL` to the actual public HTTPS origin, such as `https://ai-os.example.org`. The service uses it for sitemap URLs, the robots sitemap location, and the A2A service URL. Configure the host, HTTPS, authentication, CORS, and secret storage before exposing a service. Setting this variable does not deploy the application.

Submit the hosted sitemap to search engine webmaster tools if desired. Crawler access depends on DNS, hosting policy, robots rules, network access, and the crawler's own policies. Metadata cannot guarantee indexing or inclusion in AI answers.

## Content principles

Keep the overview, manual, API schema, extension permissions, supported protocols, and limitations consistent. Use stable public URLs. Do not publish access tokens, private customer information, or internal production data. Discovery files help an integration find documented interfaces; they are not an authentication mechanism.
