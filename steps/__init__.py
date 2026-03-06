"""
Pipeline step registry.

PIPELINE_STEPS defines the ordered execution sequence for the MQ CMDB pipeline.

To add a new step:
    1. Create a module in steps/ that subclasses PipelineStep
       (see core/interfaces.py for the contract)
    2. Import the class here
    3. Append an instance to PIPELINE_STEPS at the correct position

No changes to orchestrator.py are required.
"""

from steps.s00_cleanup              import OutputCleanupStep
from steps.s01_load_data            import LoadDataStep
from steps.s01_5_asset_association  import AssetAssociationStep
from steps.s02_mq_processing        import MQProcessingStep
from steps.s04_hierarchy_mashup     import HierarchyMashupStep
from steps.s05_change_detection     import ChangeDetectionStep
from steps.s06_topology_diagram     import TopologyDiagramStep
from steps.s07_application_diagrams import ApplicationDiagramStep
from steps.s08_individual_diagrams  import IndividualDiagramStep
from steps.s09_filtered_views       import FilteredViewsStep
from steps.s10_gateway_analytics    import GatewayAnalyticsStep
from steps.s10_5_consolidated_report import ConsolidatedReportStep
from steps.s11_exports              import MultiFormatExportStep
from steps.s12_ea_docs              import EADocumentationStep
from steps.s12_1_app_docs           import AppDocumentationStep
from steps.s12_3_confluence_publish import ConfluencePublishStep
from steps.s12_5_association_docs   import AssetAssociationDocStep
from steps.s13_summary              import SummaryStep
from steps.s14_notification         import NotificationStep

PIPELINE_STEPS = [
    OutputCleanupStep(),
    LoadDataStep(),
    AssetAssociationStep(),
    MQProcessingStep(),
    HierarchyMashupStep(),
    ChangeDetectionStep(),
    TopologyDiagramStep(),
    ApplicationDiagramStep(),
    IndividualDiagramStep(),
    FilteredViewsStep(),
    GatewayAnalyticsStep(),
    ConsolidatedReportStep(),
    MultiFormatExportStep(),
    EADocumentationStep(),
    AppDocumentationStep(),
    ConfluencePublishStep(),
    AssetAssociationDocStep(),
    SummaryStep(),
    NotificationStep(),
]

__all__ = ["PIPELINE_STEPS"]
