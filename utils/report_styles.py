

"""Shared CSS and JS for HTML reports (change detection, gateway analytics)."""


def get_report_css(accent_color: str = "#3498db") -> str:
    """
    Return the shared CSS block for pipeline HTML reports.

    Args:
        accent_color: Primary accent color (hex). Defaults to blue for
                      change reports; pass '#9b59b6' for gateway reports.
    """
    return f"""
        :root {{
            --accent: {accent_color};
            --accent-dark: color-mix(in srgb, {accent_color} 70%, #000);
            --bg: #f0f2f5;
            --card-bg: #ffffff;
            --text: #1e293b;
            --text-muted: #64748b;
            --border: #e2e8f0;
            --shadow: 0 1px 3px rgba(0,0,0,.08), 0 1px 2px rgba(0,0,0,.06);
            --shadow-lg: 0 4px 12px rgba(0,0,0,.1);
            --radius: 10px;
            --transition: .2s ease;
        }}

        *, *::before, *::after {{ box-sizing: border-box; }}

        body {{
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            margin: 0; padding: 0;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }}

        /* ---- Hero header ---- */
        .hero {{
            background: linear-gradient(135deg, #1e293b 0%, #334155 50%, var(--accent) 100%);
            color: #fff;
            padding: 36px 40px 28px;
        }}
        .hero h1 {{
            margin: 0 0 6px; font-size: 26px; font-weight: 700; letter-spacing: -.3px;
        }}
        .hero p {{
            margin: 0; opacity: .85; font-size: 14px;
        }}
        .hero .meta {{
            display: flex; flex-wrap: wrap; gap: 18px;
            margin-top: 14px; font-size: 13px; opacity: .8;
        }}
        .hero .meta span {{ font-family: 'SF Mono', 'Cascadia Code', monospace; }}

        /* ---- Container ---- */
        .container {{
            max-width: 1400px;
            margin: -20px auto 40px;
            padding: 0 24px;
            position: relative;
        }}

        /* ---- Summary cards ---- */
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
            gap: 14px;
            margin-bottom: 28px;
        }}
        .summary-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 20px 16px;
            text-align: center;
            box-shadow: var(--shadow);
            transition: transform var(--transition), box-shadow var(--transition);
        }}
        .summary-card:hover {{
            transform: translateY(-3px);
            box-shadow: var(--shadow-lg);
        }}
        .summary-card h3 {{
            margin: 0 0 6px; font-size: 12px; text-transform: uppercase;
            letter-spacing: .6px; color: var(--text-muted);
        }}
        .summary-card .count {{
            font-size: 34px; font-weight: 700; line-height: 1.1;
        }}
        .summary-card.accent  .count {{ color: var(--accent); }}
        .summary-card.added   .count {{ color: #16a34a; }}
        .summary-card.removed .count {{ color: #dc2626; }}
        .summary-card.modified .count {{ color: #d97706; }}
        .summary-card.internal .count {{ color: #ea580c; }}
        .summary-card.external .count {{ color: #0891b2; }}

        /* ---- Sections ---- */
        .section {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 24px 28px;
            margin-bottom: 20px;
            box-shadow: var(--shadow);
        }}
        .section h2 {{
            margin: 0 0 16px;
            font-size: 17px; font-weight: 600;
            color: var(--text);
            border-left: 4px solid var(--accent);
            padding-left: 12px;
        }}

        /* ---- Tables ---- */
        table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            font-size: 14px;
        }}
        th, td {{
            padding: 10px 14px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        th {{
            position: sticky; top: 0; z-index: 2;
            background: #1e293b;
            color: #fff;
            font-weight: 600;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: .5px;
            cursor: pointer;
            user-select: none;
            white-space: nowrap;
        }}
        th:first-child {{ border-radius: 8px 0 0 0; }}
        th:last-child  {{ border-radius: 0 8px 0 0; }}
        th::after {{
            content: '\\2195'; /* up-down arrow */
            margin-left: 6px; opacity: .4; font-size: 11px;
        }}
        th.sort-asc::after  {{ content: '\\25B2'; opacity: .9; }}
        th.sort-desc::after {{ content: '\\25BC'; opacity: .9; }}
        tbody tr {{ transition: background var(--transition); }}
        tbody tr:nth-child(even) {{ background: #f8fafc; }}
        tbody tr:hover {{ background: #e0e7ff; }}

        /* ---- Badges ---- */
        .badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 600;
            letter-spacing: .3px;
        }}
        .badge-added    {{ background: #dcfce7; color: #166534; }}
        .badge-removed  {{ background: #fee2e2; color: #991b1b; }}
        .badge-modified {{ background: #fef9c3; color: #854d0e; }}
        .badge-gateway  {{ background: #f3e8ff; color: #6b21a8; }}
        .badge-internal {{ background: #ffedd5; color: #9a3412; }}
        .badge-external {{ background: #cffafe; color: #155e75; }}
        .badge-warning  {{ background: #fee2e2; color: #991b1b; }}
        .badge-ok       {{ background: #dcfce7; color: #166534; }}

        /* ---- CSS bar chart ---- */
        .bar-wrap {{
            display: flex; align-items: center; gap: 8px;
        }}
        .bar {{
            height: 20px;
            border-radius: 4px;
            background: var(--accent);
            transition: width .4s ease;
            min-width: 4px;
        }}
        .bar-label {{
            font-size: 12px; font-weight: 600; white-space: nowrap;
        }}

        /* ---- Collapsible details ---- */
        details {{
            border: 1px solid var(--border);
            border-radius: 8px;
            margin-bottom: 10px;
        }}
        details summary {{
            cursor: pointer;
            padding: 10px 14px;
            font-weight: 600;
            font-size: 14px;
            background: #f8fafc;
            border-radius: 8px;
            list-style: none;
        }}
        details summary::before {{
            content: '\\25B6'; margin-right: 8px; font-size: 11px;
            display: inline-block; transition: transform .15s;
        }}
        details[open] summary::before {{
            transform: rotate(90deg);
        }}
        details summary::-webkit-details-marker {{ display: none; }}
        details .detail-body {{
            padding: 14px;
        }}

        /* ---- Alerts ---- */
        .alert {{
            padding: 16px 20px;
            border-radius: var(--radius);
            margin-bottom: 20px;
            border-left: 4px solid #f59e0b;
            background: #fffbeb;
        }}
        .alert-danger {{
            border-left-color: #ef4444;
            background: #fef2f2;
        }}
        .alert-success {{
            border-left-color: #22c55e;
            background: #f0fdf4;
        }}
        .alert h3 {{ margin: 0 0 6px; font-size: 15px; }}
        .alert p  {{ margin: 0; font-size: 14px; }}

        /* ---- No-changes state ---- */
        .no-changes {{
            text-align: center;
            padding: 50px 20px;
            color: var(--text-muted);
        }}
        .no-changes h2 {{ color: #16a34a; }}

        .change-detail {{
            font-size: 13px; color: var(--text-muted);
        }}

        /* ---- Print ---- */
        @media print {{
            .hero {{ background: #1e293b !important; -webkit-print-color-adjust: exact; }}
            .summary-card {{ break-inside: avoid; }}
            .section {{ break-inside: avoid; }}
            th {{ position: static; }}
            body {{ font-size: 11px; }}
        }}

        /* ---- Responsive ---- */
        @media (max-width: 768px) {{
            .hero {{ padding: 24px 20px 18px; }}
            .hero h1 {{ font-size: 20px; }}
            .container {{ padding: 0 12px; }}
            .summary {{ grid-template-columns: repeat(2, 1fr); }}
            .section {{ padding: 16px; }}
            table {{ font-size: 12px; }}
            th, td {{ padding: 8px 10px; }}
        }}
        @media (max-width: 480px) {{
            .summary {{ grid-template-columns: 1fr; }}
        }}
"""


def get_report_js() -> str:
    """Return vanilla JS for sortable table columns (no external dependencies)."""
    return """
    document.addEventListener('DOMContentLoaded', function() {
        document.querySelectorAll('table').forEach(function(table) {
            var headers = table.querySelectorAll('th');
            headers.forEach(function(th, colIndex) {
                th.addEventListener('click', function() {
                    var tbody = table.querySelector('tbody');
                    if (!tbody) return;
                    var rows = Array.from(tbody.querySelectorAll('tr'));
                    var asc = !th.classList.contains('sort-asc');

                    // Reset sibling indicators
                    headers.forEach(function(h) { h.classList.remove('sort-asc', 'sort-desc'); });
                    th.classList.add(asc ? 'sort-asc' : 'sort-desc');

                    rows.sort(function(a, b) {
                        var aText = (a.children[colIndex] || {}).textContent || '';
                        var bText = (b.children[colIndex] || {}).textContent || '';
                        // Try numeric comparison first
                        var aNum = parseFloat(aText.replace(/[^\\d.\\-]/g, ''));
                        var bNum = parseFloat(bText.replace(/[^\\d.\\-]/g, ''));
                        if (!isNaN(aNum) && !isNaN(bNum)) {
                            return asc ? aNum - bNum : bNum - aNum;
                        }
                        return asc ? aText.localeCompare(bText) : bText.localeCompare(aText);
                    });

                    rows.forEach(function(row) { tbody.appendChild(row); });
                });
            });
        });
    });
"""
