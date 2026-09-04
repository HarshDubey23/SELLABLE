"""Retired HTML surfaces, redirected into the three pages that remain.

SELLABLE accumulated twenty-odd HTML pages while it was being built: a
console, a mission viewer, an attack UI, a gateway UI, an audit UI, a
chaos room, an architecture page, a growth studio, a protocol page, three
demo pages and a discovery studio. Each one was a reasonable thing to
build at the time and a bad thing to ship: a reviewer landing on any of
them has to work out which generation of the project they are looking at.

Everything those pages showed now lives in one of three places:

    GET /                the shop — the whole buyer journey
    GET /trace/{ref}     one purchase, end to end, with its evidence
    GET /judge           the evidence console — proof, attacks, recovery

The old paths are kept as redirects rather than deleted outright so that
links in the build log, in screenshots and in anyone's browser history
still land somewhere sensible instead of on a 404. They carry no content
of their own.

Redirects are 307, not 301: a permanent redirect gets cached by the
browser and then survives a later change of layout, which is exactly the
kind of stale behaviour this file exists to remove.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter(include_in_schema=False)

# Retired path -> where its capability lives now. The fragment matters:
# it selects the tab on the judge console, so /attack-ui still lands the
# reader on the attack lab rather than on the top of a long page.
RETIRED_PAGES: dict[str, str] = {
    # --- console and its sub-pages ---
    "/console": "/judge",
    "/ui": "/judge",
    "/why": "/judge#thesis",
    "/mission": "/judge#chain",
    "/attack-ui": "/judge#attack",
    "/audit-ui": "/judge#audit",
    "/audit/timeline": "/judge#audit",
    "/gateway-ui": "/judge#gateway",
    "/metrics": "/judge#evidence",
    "/protocols": "/judge#architecture",
    "/architecture": "/judge#architecture",
    "/chaos": "/judge#recovery",
    # --- demo-era pages ---
    "/demo": "/",
    "/demo/checkout": "/",
    "/demo/shopping": "/",
    "/demo/shopping/": "/",
    "/demo/failures": "/judge#recovery",
    "/demo/judge": "/judge",
    # --- subsystem studios ---
    "/products": "/",
    "/discovery": "/",
    "/discovery/": "/",
    "/discovery/ui": "/",
    "/growth": "/judge#architecture",
    "/growth/": "/judge#architecture",
    "/growth/ui": "/judge#architecture",
}


def _make(destination: str):
    async def _redirect() -> RedirectResponse:
        return RedirectResponse(destination, status_code=307)
    return _redirect


for _path, _destination in RETIRED_PAGES.items():
    router.add_api_route(_path, _make(_destination), methods=["GET"])
