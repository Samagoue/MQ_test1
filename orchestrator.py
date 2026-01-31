"""Main orchestrator for the complete MQ CMDB pipeline."""

from pathlib import Path
from datetime import datetime
from config.settings import Config
from utils.common import setup_utf8_output, safe_print
from utils.file_io import load_json, save_json, cleanup_output_directory
from utils.export_formats import export_directory_to_formats, generate_excel_inventory
from processors.mqmanager_processor import MQManagerProcessor
from processors.hierarchy_mashup import HierarchyMashup
from processors.change_detector import ChangeDetector, generate_html_report
from analytics.gateway_analyzer import GatewayAnalyzer, generate_gateway_report_html
from generators.doc_generator import EADocumentationGenerator
from generators.graphviz_hierarchical import HierarchicalGraphVizGenerator
from generators.application_diagram_generator import ApplicationDiagramGenerator
from generators.graphviz_individual import IndividualDiagramGenerator
from generators.dashboard_generator import generate_dashboard

class MQCMDBOrchestrator:
    """Orchestrate the complete MQ CMDB processing pipeline."""
   
    def __init__(self):
        setup_utf8_output()
        Config.ensure_directories()
   
    def run_full_pipeline(self):
        """Execute complete hierarchical pipeline."""
        safe_print("\n" + "=" * 70)
        safe_print("MQ CMDB HIERARCHICAL AUTOMATION PIPELINE")
        safe_print("=" * 70)
       
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
            else:
                safe_print("⚠ No baseline found - this will be the first baseline")

            # Update baseline
            save_json(enriched_data, baseline_file)
            safe_print(f"✓ Baseline updated: {baseline_file}")

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

            # Interactive Dashboard
            safe_print("\n[13/14] Generating interactive dashboard...")
            try:
                dashboard_file = Config.REPORTS_DIR / "dashboard.html"
                if generate_dashboard(enriched_data, dashboard_file):
                    safe_print(f"✓ Dashboard: {dashboard_file}")
                    safe_print("  → Open in browser for interactive view")
            except Exception as e:
                safe_print(f"⚠ Dashboard generation failed: {e}")

            # Final Summary
            safe_print("\n[14/14] Pipeline Summary")
            self._print_summary(enriched_data)

            safe_print("\n" + "=" * 70)
            safe_print("✓ PIPELINE COMPLETED SUCCESSFULLY")
            safe_print("=" * 70)
           
        except FileNotFoundError as e:
            safe_print(f"\n✗ ERROR: {e}")
            safe_print("Ensure all required files exist in the correct directories")
        except Exception as e:
            safe_print(f"\n✗ UNEXPECTED ERROR: {e}")
            import traceback
            traceback.print_exc()
   
    def _print_summary(self, enriched_data: dict):
        """Print summary statistics."""
        safe_print("\n" + "-" * 70)
        safe_print("SUMMARY STATISTICS")
        safe_print("-" * 70)
       
        total_orgs = len(enriched_data)
        total_depts = 0
        total_biz_ownrs = 0
        total_apps = 0
        total_mqmgrs = 0
        total_qlocal = 0
        total_qremote = 0
        total_qalias = 0
        total_connections = 0
       
        for org_name, org_data in enriched_data.items():
            departments = org_data.get('_departments', {})
            total_depts += len(departments)
           
            for dept_name, biz_owners in departments.items():
                total_biz_ownrs += len(biz_owners)
               
                for biz_ownr, applications in biz_owners.items():
                    total_apps += len(applications)
                   
                    for app_name, mqmanagers in applications.items():
                        total_mqmgrs += len(mqmanagers)
                       
                        for mqmgr, mq_data in mqmanagers.items():
                            total_qlocal += mq_data.get('qlocal_count', 0)
                            total_qremote += mq_data.get('qremote_count', 0)
                            total_qalias += mq_data.get('qalias_count', 0)
                            total_connections += len(mq_data.get('outbound', []))
       
        safe_print(f"Organizations:        {total_orgs}")
        safe_print(f"Departments:          {total_depts}")
        safe_print(f"Business Owners:      {total_biz_ownrs}")
        safe_print(f"Applications:         {total_apps}")
        safe_print(f"MQ Managers:          {total_mqmgrs}")
        safe_print(f"Total QLocal:         {total_qlocal}")
        safe_print(f"Total QRemote:        {total_qremote}")
        safe_print(f"Total QAlias:         {total_qalias}")
        safe_print(f"Total Connections:    {total_connections}")
        safe_print("-" * 70)


def main():
    """Entry point for the MQ CMDB orchestrator."""
    orchestrator = MQCMDBOrchestrator()
    orchestrator.run_full_pipeline()


if __name__ == "__main__":
    main()