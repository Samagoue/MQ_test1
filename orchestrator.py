"""Main orchestrator for the complete MQ CMDB pipeline."""

import os
import sys
import traceback
from pathlib import Path
from datetime import datetime
from config.settings import Config
from utils.common import setup_utf8_output, safe_print
from utils.file_io import load_json, save_json, cleanup_output_directory
from utils.export_formats import export_directory_to_formats, generate_excel_inventory
from utils.email_notifier import get_notifier
from processors.mqmanager_processor import MQManagerProcessor
from processors.hierarchy_mashup import HierarchyMashup
from processors.change_detector import ChangeDetector, generate_html_report
from analytics.gateway_analyzer import GatewayAnalyzer, generate_gateway_report_html
from generators.doc_generator import EADocumentationGenerator
from generators.graphviz_hierarchical import HierarchicalGraphVizGenerator
from generators.application_diagram_generator import ApplicationDiagramGenerator
from generators.graphviz_individual import IndividualDiagramGenerator


class MQCMDBOrchestrator:
    """Orchestrate the complete MQ CMDB processing pipeline."""

    def __init__(self):
        setup_utf8_output()
        Config.ensure_directories()
        self._pipeline_errors: list = []
        self._summary_stats: dict = {}

    def run_full_pipeline(self) -> bool:
        """
        Execute complete hierarchical pipeline.

        Returns:
            True if pipeline completed successfully, False otherwise
        """
        safe_print("\n" + "=" * 70)
        safe_print("MQ CMDB HIERARCHICAL AUTOMATION PIPELINE")
        safe_print("=" * 70)

        success = False
        error_message = None
        enriched_data = None

        try:
            # Output cleanup (if enabled)
            if Config.ENABLE_OUTPUT_CLEANUP:
                safe_print("\n[0/14] Cleaning up old output files...")
                cleanup_results = cleanup_output_directory(
                    Config.OUTPUT_DIR,
                    Config.OUTPUT_RETENTION_DAYS,
                    Config.OUTPUT_CLEANUP_PATTERNS
                )
                if cleanup_results['total_deleted'] > 0:
                    safe_print(f"✓ Cleaned up {cleanup_results['total_deleted']} old file(s) (>{Config.OUTPUT_RETENTION_DAYS} days)")
                    for fname in cleanup_results['deleted_files'][:5]:  # Show first 5
                        safe_print(f"  - {fname}")
                    if len(cleanup_results['deleted_files']) > 5:
                        safe_print(f"  ... and {len(cleanup_results['deleted_files']) - 5} more")
                else:
                    safe_print("✓ No old files to clean up")
                if cleanup_results['errors']:
                    for error in cleanup_results['errors']:
                        safe_print(f"⚠ {error}")

            # Load data
            safe_print("\n[1/14] Loading MQ CMDB data...")
            raw_data = load_json(Config.INPUT_JSON)
            safe_print(f"✓ Loaded {len(raw_data)} records")

            # Process relationships
            safe_print("\n[2/14] Processing MQ Manager relationships...")
            processor = MQManagerProcessor(raw_data, Config.FIELD_MAPPINGS)
            directorate_data = processor.process_assets()
            processor.print_stats()

            # Convert to JSON
            safe_print("\n[3/14] Converting to JSON structure...")
            json_output = processor.convert_to_json(directorate_data)

            # Mashup with hierarchy
            safe_print("\n[4/14] Enriching with organizational hierarchy...")
            mashup = HierarchyMashup(Config.ORG_HIERARCHY_JSON, Config.APP_TO_QMGR_JSON, Config.GATEWAYS_JSON)
            enriched_data = mashup.enrich_data(json_output)
            save_json(enriched_data, Config.PROCESSED_JSON)
            safe_print(f"✓ Enriched data saved: {Config.PROCESSED_JSON}")

            # Change Detection
            safe_print("\n[5/14] Running change detection...")
            baseline_file = Config.BASELINE_JSON
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            change_detection_success = True

            if baseline_file.exists():
                try:
                    baseline_data = load_json(baseline_file)
                    detector = ChangeDetector()
                    changes = detector.compare(enriched_data, baseline_data)

                    # Get baseline timestamp from filename or use "previous"
                    baseline_timestamp = baseline_file.stat().st_mtime
                    baseline_time_str = datetime.fromtimestamp(baseline_timestamp).strftime('%Y-%m-%d %H:%M:%S')

                    # Generate HTML report
                    report_file = Config.REPORTS_DIR / f"change_report_{timestamp}.html"
                    generate_html_report(changes, report_file, timestamp, baseline_time_str)

                    safe_print(f"✓ Detected {changes['summary']['total_changes']} changes")
                    safe_print(f"✓ Change report: {report_file}")

                    # Save change data as JSON for programmatic access
                    change_json = Config.DATA_DIR / f"changes_{timestamp}.json"
                    save_json(changes, change_json)
                except Exception as e:
                    safe_print(f"⚠ Change detection failed: {e}")
                    safe_print("⚠ Baseline will NOT be updated to preserve change detection capability")
                    self._pipeline_errors.append(f"Change detection: {e}")
                    change_detection_success = False
            else:
                safe_print("⚠ No baseline found - this will be the first baseline")

            # Update baseline only if change detection succeeded (or no baseline existed)
            if change_detection_success:
                save_json(enriched_data, baseline_file)
                safe_print(f"✓ Baseline updated: {baseline_file}")
            else:
                safe_print("⚠ Baseline NOT updated due to change detection failure")

            # Generate hierarchical topology
            safe_print("\n[6/14] Generating hierarchical topology diagram...")
            gen = HierarchicalGraphVizGenerator(enriched_data, Config)
            gen.save_to_file(Config.TOPOLOGY_DOT)

            # Try to generate PDF, but don't fail if GraphViz is not installed
            pdf_generated = gen.generate_pdf(Config.TOPOLOGY_DOT, Config.TOPOLOGY_PDF)
            if not pdf_generated:
                safe_print("⚠ GraphViz not found - DOT file created, PDF skipped")
                safe_print(f"  → Install GraphViz, then run: sfdp -Tpdf {Config.TOPOLOGY_DOT} -o {Config.TOPOLOGY_PDF}")

            # Generate application diagrams
            safe_print("\n[7/14] Generating application diagrams...")
            app_diagrams_dir = Config.APPLICATION_DIAGRAMS_DIR
            app_gen = ApplicationDiagramGenerator(enriched_data, Config)
            count = app_gen.generate_all(app_diagrams_dir)
            if count > 0:
                safe_print(f"✓ Generated {count} application diagrams in {app_diagrams_dir}")
                if not pdf_generated:
                    safe_print("⚠ GraphViz required for PDF generation")
                    safe_print(f"  → To generate PDFs: cd {app_diagrams_dir} && for f in *.dot; do dot -Tpdf $f -o ${{f%.dot}}.pdf; done")
            else:
                safe_print("⚠ No application diagrams generated")

            # Generate individual MQ manager diagrams
            safe_print("\n[8/14] Generating individual MQ manager diagrams...")
            individual_diagrams_dir = Config.INDIVIDUAL_DIAGRAMS_DIR
            individual_gen = IndividualDiagramGenerator(directorate_data, Config)
            individual_count = individual_gen.generate_all(individual_diagrams_dir)
            if individual_count > 0:
                safe_print(f"✓ Generated {individual_count} individual MQ manager diagrams in {individual_diagrams_dir}")
                if not pdf_generated:
                    safe_print("⚠ GraphViz required for PDF generation")
                    safe_print(f"  → To generate PDFs: cd {individual_diagrams_dir} && for f in *.dot; do dot -Tpdf $f -o ${{f%.dot}}.pdf; done")
            else:
                safe_print("⚠ No individual diagrams generated")

            # Smart Filtered Views
            safe_print("\n[9/14] Generating smart filtered views...")
            try:
                from utils.smart_filter import generate_filtered_diagrams
                filtered_dir = Config.FILTERED_VIEWS_DIR
                filtered_count = generate_filtered_diagrams(enriched_data, filtered_dir, Config)
                if filtered_count > 0:
                    safe_print(f"✓ Generated {filtered_count} filtered view diagrams in {filtered_dir}")
                    safe_print("  Views: per-organization, gateways-only, internal/external gateways")
                else:
                    safe_print("⚠ No filtered views generated")
            except Exception as e:
                safe_print(f"⚠ Filtered view generation failed: {e}")
                self._pipeline_errors.append(f"Filtered views: {e}")

            # Gateway Analytics (if gateways exist)
            safe_print("\n[10/14] Running gateway analytics...")
            try:
                analyzer = GatewayAnalyzer(enriched_data)
                gateway_analytics = analyzer.analyze()

                if gateway_analytics['summary']['total_gateways'] > 0:
                    # Generate gateway analytics report
                    analytics_report = Config.REPORTS_DIR / f"gateway_analytics_{timestamp}.html"
                    generate_gateway_report_html(gateway_analytics, analytics_report)

                    # Save analytics data as JSON
                    analytics_json = Config.DATA_DIR / f"gateway_analytics_{timestamp}.json"
                    save_json(gateway_analytics, analytics_json)

                    safe_print(f"✓ Gateway analytics: {gateway_analytics['summary']['total_gateways']} gateways analyzed")
                    safe_print(f"✓ Report: {analytics_report}")
                else:
                    safe_print("⚠ No gateways found in data")
            except Exception as e:
                safe_print(f"⚠ Gateway analytics failed: {e}")
                self._pipeline_errors.append(f"Gateway analytics: {e}")

            # Multi-Format Exports
            safe_print("\n[11/14] Generating multi-format exports...")
            try:
                # Export main topology to SVG and PNG
                if Config.TOPOLOGY_DOT.exists():
                    from utils.export_formats import export_dot_to_svg, export_dot_to_png
                    export_dot_to_svg(Config.TOPOLOGY_DOT, Config.TOPOLOGY_DIR / "mq_topology.svg")
                    export_dot_to_png(Config.TOPOLOGY_DOT, Config.TOPOLOGY_DIR / "mq_topology.png", dpi=200)

                # Export all application diagrams
                if Config.APPLICATION_DIAGRAMS_DIR.exists():
                    export_directory_to_formats(Config.APPLICATION_DIAGRAMS_DIR, formats=['svg'], dpi=150)

                # Export all individual diagrams
                if Config.INDIVIDUAL_DIAGRAMS_DIR.exists():
                    export_directory_to_formats(Config.INDIVIDUAL_DIAGRAMS_DIR, formats=['svg'], dpi=150)

                # Generate Excel inventory
                excel_file = Config.EXPORTS_DIR / f"mqcmdb_inventory_{timestamp}.xlsx"
                if generate_excel_inventory(enriched_data, excel_file):
                    safe_print(f"✓ Excel inventory: {excel_file}")
            except Exception as e:
                safe_print(f"⚠ Multi-format export failed: {e}")
                self._pipeline_errors.append(f"Multi-format export: {e}")

            # EA Documentation Generation
            safe_print("\n[12/14] Generating Enterprise Architecture documentation...")
            try:
                ea_doc_gen = EADocumentationGenerator(enriched_data)
                confluence_doc = Config.EXPORTS_DIR / f"EA_Documentation_{timestamp}.txt"
                ea_doc_gen.generate_confluence_markup(confluence_doc)
                safe_print(f"✓ EA Documentation: {confluence_doc}")
                safe_print("  → Import into Confluence using Insert → Markup")
            except Exception as e:
                safe_print(f"⚠ EA documentation generation failed: {e}")
                self._pipeline_errors.append(f"EA documentation: {e}")

            # Final Summary
            safe_print("\n[13/14] Pipeline Summary")
            self._summary_stats = self._calculate_summary(enriched_data)
            self._print_summary(self._summary_stats)

            safe_print("\n" + "=" * 70)
            safe_print("✓ PIPELINE COMPLETED SUCCESSFULLY")
            safe_print("=" * 70)

            success = True

        except FileNotFoundError as e:
            safe_print(f"\n✗ ERROR: {e}")
            safe_print("Ensure all required files exist in the correct directories")
            error_message = f"File not found: {e}"
        except Exception as e:
            safe_print(f"\n✗ UNEXPECTED ERROR: {e}")
            error_message = f"Unexpected error: {e}\n{traceback.format_exc()}"
            traceback.print_exc()

        # Send email notification (step 14)
        self._send_notification(success, error_message)

        return success

    def _calculate_summary(self, enriched_data: dict) -> dict:
        """Calculate summary statistics."""
        stats = {
            "Organizations": len(enriched_data),
            "Departments": 0,
            "Business Owners": 0,
            "Applications": 0,
            "MQ Managers": 0,
            "Total QLocal": 0,
            "Total QRemote": 0,
            "Total QAlias": 0,
            "Total Connections": 0,
        }

        for org_name, org_data in enriched_data.items():
            departments = org_data.get('_departments', {})
            stats["Departments"] += len(departments)

            for dept_name, biz_owners in departments.items():
                stats["Business Owners"] += len(biz_owners)

                for biz_ownr, applications in biz_owners.items():
                    stats["Applications"] += len(applications)

                    for app_name, mqmanagers in applications.items():
                        stats["MQ Managers"] += len(mqmanagers)

                        for mqmgr, mq_data in mqmanagers.items():
                            stats["Total QLocal"] += mq_data.get('qlocal_count', 0)
                            stats["Total QRemote"] += mq_data.get('qremote_count', 0)
                            stats["Total QAlias"] += mq_data.get('qalias_count', 0)
                            stats["Total Connections"] += len(mq_data.get('outbound', []))

        return stats

    def _print_summary(self, stats: dict):
        """Print summary statistics."""
        safe_print("\n" + "-" * 70)
        safe_print("SUMMARY STATISTICS")
        safe_print("-" * 70)

        for key, value in stats.items():
            safe_print(f"{key + ':':21} {value}")

        safe_print("-" * 70)

        # Show warnings if any
        if self._pipeline_errors:
            safe_print("\nWarnings during execution:")
            for error in self._pipeline_errors:
                safe_print(f"  ⚠ {error}")

    def _send_notification(self, success: bool, error_message: str = None):
        """Send email notification about pipeline completion."""
        # Check if email is enabled via environment variable
        if os.environ.get("EMAIL_ENABLED", "").lower() not in ("true", "1", "yes"):
            return

        safe_print("\n[14/14] Sending email notification...")

        try:
            notifier = get_notifier()

            if not notifier.is_enabled:
                safe_print("⚠ Email notifications not configured")
                return

            # Build summary for email
            summary = self._summary_stats.copy() if self._summary_stats else {}

            if self._pipeline_errors:
                summary["Warnings"] = len(self._pipeline_errors)
                error_details = "\n".join([f"  - {e}" for e in self._pipeline_errors])
                if error_message:
                    error_message = f"{error_message}\n\nWarnings:\n{error_details}"
                else:
                    error_message = f"Warnings during execution:\n{error_details}"

            result = notifier.send_pipeline_notification(
                success=success,
                summary=summary,
                error_message=error_message,
            )

            if result:
                safe_print("✓ Email notification sent")
            else:
                safe_print("⚠ Failed to send email notification")
                for err in notifier.errors:
                    safe_print(f"  - {err}")

        except Exception as e:
            safe_print(f"⚠ Email notification error: {e}")


def main():
    """Entry point for the MQ CMDB orchestrator."""
    orchestrator = MQCMDBOrchestrator()
    success = orchestrator.run_full_pipeline()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
