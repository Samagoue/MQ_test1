"""Main orchestrator for the complete MQ CMDB pipeline."""

from pathlib import Path
from config.settings import Config
from utils.common import setup_utf8_output, safe_print
from utils.file_io import load_json, save_json
from processors.mqmanager_processor import MQManagerProcessor
from processors.hierarchy_mashup import HierarchyMashup
from generators.graphviz_hierarchical import HierarchicalGraphVizGenerator
from generators.application_diagram_generator import ApplicationDiagramGenerator
from generators.graphviz_individual import IndividualDiagramGenerator

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
            # Load data
            safe_print("\n[1/8] Loading MQ CMDB data...")
            raw_data = load_json(Config.INPUT_JSON)
            safe_print(f"✓ Loaded {len(raw_data)} records")

            # Process relationships
            safe_print("\n[2/8] Processing MQ Manager relationships...")
            processor = MQManagerProcessor(raw_data, Config.FIELD_MAPPINGS)
            directorate_data = processor.process_assets()
            processor.print_stats()

            # Convert to JSON
            safe_print("\n[3/8] Converting to JSON structure...")
            json_output = processor.convert_to_json(directorate_data)

            # Mashup with hierarchy
            safe_print("\n[4/8] Enriching with organizational hierarchy...")
            mashup = HierarchyMashup(Config.ORG_HIERARCHY_JSON, Config.APP_TO_QMGR_JSON, Config.GATEWAYS_JSON)
            enriched_data = mashup.enrich_data(json_output)
            save_json(enriched_data, Config.PROCESSED_JSON)
            safe_print(f"✓ Enriched data saved: {Config.PROCESSED_JSON}")

            # Generate hierarchical topology
            safe_print("\n[5/8] Generating hierarchical topology diagram...")
            gen = HierarchicalGraphVizGenerator(enriched_data, Config)
            gen.save_to_file(Config.TOPOLOGY_DOT)
           
            # Try to generate PDF, but don't fail if GraphViz is not installed
            pdf_generated = gen.generate_pdf(Config.TOPOLOGY_DOT, Config.TOPOLOGY_PDF)
            if not pdf_generated:
                safe_print("⚠ GraphViz not found - DOT file created, PDF skipped")
                safe_print(f"  → Install GraphViz, then run: sfdp -Tpdf {Config.TOPOLOGY_DOT} -o {Config.TOPOLOGY_PDF}")
           
            # Generate application diagrams
            safe_print("\n[6/8] Generating application diagrams...")
            app_diagrams_dir = Config.OUTPUT_DIR / "application_diagrams"
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
            safe_print("\n[7/8] Generating individual MQ manager diagrams...")
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