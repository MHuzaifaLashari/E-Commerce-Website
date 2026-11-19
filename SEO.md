SEO changes
===========

Public pages have unique titles and descriptions plus Open Graph and Twitter metadata.
Catalogue pages update their metadata from the selected product or brand. Product color
variants share the style canonical; listing filters share the brand canonical. Product
JSON-LD uses public catalogue data only, without invented prices, ratings or availability.
Admin and login pages have noindex directives. The old sustbl.html redirect is excluded
from the sitemap. The homepage's malformed prefix before its doctype was removed and
the first hero image has high fetch priority.

Before production upload
------------------------

The live domain was not supplied. In an environment with Python installed, run:

    python tools/build_seo.py https://YOUR-LIVE-DOMAIN/

Use the actual public deployment URL, including any subdirectory. This updates canonical
URLs, absolute sharing images, and creates sitemap.xml containing public pages, brand
pages and catalogue product URLs. It also adds the sitemap location to robots.txt.
Re-run when the public URL or catalogue changes. Then run the existing hosting build;
it now includes robots.txt and sitemap.xml in its upload package.

Upload the resulting site and submit its sitemap in Google Search Console. Check live
product URLs with URL Inspection and structured data validation. Query-driven product
content and metadata still require JavaScript rendering; social crawlers that do not run
JavaScript see the generic product fallback. Server-rendered product pages would be the
next improvement if individual product previews and faster indexing are required.

Validation in this workspace
----------------------------

Static metadata and script wiring were checked. Python and a JavaScript runtime are not
installed here, so the URL generator and browser rendering need runtime verification
before deployment. No deployment or Search Console submission was performed.
