# AI and search discovery

AI OS includes descriptive HTML metadata, SoftwareApplication structured data, a crawler-readable `llms.txt`, a robots policy, a sitemap endpoint, and public API and extension documentation.

## Local and hosted behavior

Localhost cannot be crawled by public search engines or AI assistants. Publishing source to GitHub makes the repository and its docs publicly readable, but it does not publish the web application as a public website.

When hosting the app, set `AIOS_PUBLIC_URL` to its public HTTPS origin, such as `https://ai-os.example.org`. The app uses this value when it generates sitemap URLs and the sitemap location in `robots.txt`. Keep the default GitHub links in `llms.txt` until a public domain exists, then add the public manual, API reference, and landing page links.

Submit the deployed sitemap URL through search engine webmaster tools after deployment. Crawler access depends on the hosting provider, DNS, public network access, and the crawler's own policies; metadata cannot guarantee indexing or inclusion in AI answers.

## Content principles

Keep the overview, manual, API schemas, extension permissions, supported workflows, and limitations accurate. Use stable public URLs. Do not publish access tokens, private customer information, or internal production data. AI-readable files help discovery; they are not an authentication mechanism.
