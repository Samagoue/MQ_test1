# -*- coding: utf-8 -*-
"""
ea_shared.py
------------
Shared utilities import shim for the MQ CMDB pipeline.

Import order for each utility (highest priority wins):
  1. SHARED_SCRIPTS_DIR env var  (CI/CD or any override)
  2. /Users/samag/Documents/EA_Doc/Scripts  (macOS developer machine)
  3. C:\\Users\\BABED2P\\Documents\\WORKSPACE\\Scripts  (Windows developer machine)
  4. /data/app/Scripts           (Linux / RHEL server)

Generators and orchestrators must import from ea_shared, never directly from
utils.* or from a shared scripts path. This file is the single import boundary.
"""
import os
import sys
import platform
import warnings
from pathlib import Path

if os.environ.get("SHARED_SCRIPTS_DIR"):
    _SCRIPTS_ROOT = Path(os.environ["SHARED_SCRIPTS_DIR"])
elif platform.system() == "Darwin":
    _SCRIPTS_ROOT = Path("/Users/samag/Documents/EA_Doc/Scripts")
elif platform.system() == "Windows":
    _SCRIPTS_ROOT = Path(r"C:\Users\BABED2P\Documents\WORKSPACE\Scripts")
else:
    _SCRIPTS_ROOT = Path("/data/app/Scripts")

_ps = str(_SCRIPTS_ROOT)
if _ps not in sys.path:
    sys.path.insert(0, _ps)

SCRIPTS_ROOT = _SCRIPTS_ROOT

# ── Logging ───────────────────────────────────────────────────────────────────
from logging_config import setup_logging, get_logger, cleanup_old_logs  # noqa: F401

# ── Email ─────────────────────────────────────────────────────────────────────
try:
    from email_notifier import EmailNotifier, get_notifier  # noqa: F401
except ImportError as _e:
    EmailNotifier = None
    get_notifier  = None
    warnings.warn(f"email_notifier not found in {_SCRIPTS_ROOT}. Email disabled.", stacklevel=2)

# ── Confluence ────────────────────────────────────────────────────────────────
try:
    from confluence_client import ConfluenceClient, ConfluenceError  # noqa: F401
except ImportError as _e:
    ConfluenceClient = None
    ConfluenceError  = Exception
    warnings.warn(f"confluence_client not found in {_SCRIPTS_ROOT}. Confluence disabled.", stacklevel=2)

# ── GraphViz helpers (generic) ────────────────────────────────────────────────
try:
    from graphviz_utils import (  # noqa: F401
        render_dot, check_graphviz, safe_id, safe_stem,
        dot_graph_attrs, fdp_graph_attrs,
        _dot_str, _sanitize_dot, _html_node_label,
    )
except ImportError as _e:
    render_dot        = None
    check_graphviz    = None
    warnings.warn(f"graphviz_utils not found in {_SCRIPTS_ROOT}. Diagram rendering disabled.", stacklevel=2)

# ── Interactive SVG ───────────────────────────────────────────────────────────
try:
    from interactive_svg import make_interactive, make_html_page  # noqa: F401
except ImportError:
    make_interactive = None
    make_html_page   = None

# ── EA base generator, HTML, wiki (silent-fail - MQ does not use these yet) ───
try:
    from ea_base_generator import BaseGenerator  # noqa: F401
except ImportError:
    BaseGenerator = None

try:
    from ea_html_utils import (  # noqa: F401
        page_wrap, stats_row, stat_card, section, searchable_table,
        architecture_context, insight_panel, action_list,
        health_score_card, _esc,
    )
except ImportError:
    pass

try:
    from ea_wiki_utils import (  # noqa: F401
        page_header, page_footer, toc,
        section as wiki_section, table, stats_table, bold, status,
        architecture_context as wiki_arch_ctx,
        insight_panel as wiki_insight, action_list as wiki_actions,
        health_score,
    )
except ImportError:
    pass
