"""Parses GovInfo's rendered USCODE granule HTML into plain statute text. GovInfo marks
the actual codified text with a stable `class="statutory-body"` on each paragraph and
the section heading with `class="section-head"` — verified live against real granules,
not guessed from the (sparser) API documentation."""

import re
from dataclasses import dataclass

from lxml import html as lxml_html


@dataclass
class ParsedStatute:
    heading: str
    citation: str
    statutory_text: str


def parse_uscode_granule_html(html: str) -> ParsedStatute | None:
    tree = lxml_html.fromstring(html)

    heading_nodes = tree.xpath('//h3[@class="section-head"]')
    body_nodes = tree.xpath('//p[@class="statutory-body"]')
    if not heading_nodes or not body_nodes:
        return None

    heading = heading_nodes[0].text_content().strip()
    statutory_text = "\n\n".join(node.text_content().strip() for node in body_nodes)

    breadcrumb_text = " | ".join(
        span.text_content().strip() for span in tree.xpath('//span[@style]')
    )
    title_match = re.search(r"Title (\d+)", breadcrumb_text)
    section_match = re.search(r"Sec\.\s*([\w.\-]+)\s*-", breadcrumb_text)
    if title_match and section_match:
        citation = f"{title_match.group(1)} U.S.C. § {section_match.group(1)}"
    else:
        citation = heading

    return ParsedStatute(heading=heading, citation=citation, statutory_text=statutory_text)
