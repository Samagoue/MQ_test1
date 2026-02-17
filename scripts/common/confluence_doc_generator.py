"""
Generic Confluence wiki-markup document generator.

Project-agnostic base class.  Subclass and implement the abstract methods
to produce a complete Confluence page from domain-specific data.

Assembly order:
    1. Header   (``build_header()``)
    2. TOC      (``build_toc()``)
    3. Sections (``get_sections()`` — called in order)
    4. Footer   (``build_footer()``)

Usage::

    from scripts.common.confluence_doc_generator import ConfluenceDocGenerator

    class MyDocGenerator(ConfluenceDocGenerator):
        def build_header(self): ...
        def build_toc(self): ...
        def get_sections(self): ...
        def build_footer(self): ...

    gen = MyDocGenerator()
    gen.generate(Path("output.txt"))
"""

import logging
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, List, Tuple

logger = logging.getLogger(__name__)


class ConfluenceDocGenerator(ABC):
    """Base class for generating Confluence wiki-markup documents.

    Provides reusable Confluence markup helpers and a template-method
    ``generate()`` that assembles header + TOC + sections + footer and
    writes the result to a file.
    """

    # ------------------------------------------------------------------ #
    #  Confluence markup helpers (static, reusable by anyone)
    # ------------------------------------------------------------------ #

    @staticmethod
    def styled_panel(
        title: str,
        content_lines: List[str],
        bg_color: str = "#f7f9fb",
        title_bg: str = "#2d3e50",
        title_color: str = "#fff",
        border_color: str = "#c1c7d0",
    ) -> List[str]:
        """Return a Confluence panel with a styled title bar."""
        return [
            f"{{panel:title={title}|bgColor={bg_color}|titleBGColor={title_bg}"
            f"|titleColor={title_color}|borderColor={border_color}|borderStyle=solid}}",
            *content_lines,
            "{panel}",
        ]

    @staticmethod
    def status_lozenge(label: str, colour: str = "Green") -> str:
        """Return a Confluence status lozenge macro string.

        ``colour`` must be one of: Green, Yellow, Red, Blue, Grey.
        """
        return f"{{status:colour={colour}|title={label}}}"

    @staticmethod
    def expandable(title: str, content_lines: List[str]) -> List[str]:
        """Wrap *content_lines* in an expand/collapse macro."""
        return [
            f"{{expand:title={title}}}",
            *content_lines,
            "{expand}",
        ]

    # ------------------------------------------------------------------ #
    #  Abstract methods — subclass MUST implement
    # ------------------------------------------------------------------ #

    @abstractmethod
    def build_header(self) -> List[str]:
        """Return Confluence markup lines for the document header."""
        ...

    @abstractmethod
    def build_toc(self) -> List[str]:
        """Return Confluence markup lines for the table of contents / navigation."""
        ...

    @abstractmethod
    def get_sections(self) -> List[Tuple[str, Callable[[], List[str]]]]:
        """Return an ordered list of ``(section_name, callable)`` tuples.

        Each callable takes no arguments and returns ``List[str]`` of
        Confluence markup lines for that section.
        """
        ...

    @abstractmethod
    def build_footer(self) -> List[str]:
        """Return Confluence markup lines for the document footer."""
        ...

    # ------------------------------------------------------------------ #
    #  Post-processing
    # ------------------------------------------------------------------ #

    # Matches a data row: starts with | but NOT ||
    _DATA_ROW_RE = re.compile(r"^\|(?!\|)")

    @staticmethod
    def _sanitize_table_rows(doc: List[str]) -> List[str]:
        """Fix empty cells in Confluence table data rows.

        In Confluence wiki markup ``||`` denotes a header-cell separator.
        When a dynamic value is empty the row contains an accidental ``||``
        which shifts all subsequent columns.  This method replaces every
        interior ``||`` in data rows with ``| |`` (a space-filled cell),
        leaving header rows (``||Col||Col||``) untouched.
        """
        sanitized = []
        for line in doc:
            if ConfluenceDocGenerator._DATA_ROW_RE.match(line) and "||" in line:
                # Replace every interior || with | | (repeat for consecutive empty cells)
                tail = line[1:]
                while "||" in tail:
                    tail = tail.replace("||", "| |")
                line = line[0] + tail
            sanitized.append(line)
        return sanitized

    # ------------------------------------------------------------------ #
    #  Document assembly (template method)
    # ------------------------------------------------------------------ #

    def generate(self, output_file: Path) -> bool:
        """Assemble the full document and write it to *output_file*.

        Returns ``True`` on success.
        """
        doc: List[str] = []

        doc.extend(self.build_header())
        doc.extend(self.build_toc())

        for section_name, section_callable in self.get_sections():
            logger.debug("Generating section: %s", section_name)
            doc.extend(section_callable())

        doc.extend(self.build_footer())

        doc = self._sanitize_table_rows(doc)

        output_path = Path(output_file)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(doc))

        return True
