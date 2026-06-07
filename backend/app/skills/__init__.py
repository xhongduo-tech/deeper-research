"""Skills package — auto-register all offline skills on import."""
from app.skills.registry import SkillRegistry
from app.skills.offline import (
    SummarizerSkill,
    DataAnalyzerSkill,
    ChartSpecGeneratorSkill,
    KeywordExtractorSkill,
    TableBuilderSkill,
    ReportSectionWriterSkill,
    KnowledgeEnricherSkill,
    SlideScripterSkill,
    MultiPassWriterSkill,
    BusinessFrameworkSkill,
    InsightGeneratorSkill,
    SqlQuerySkill,
    PythonChartSkill,
    ExcelAnalyzerSkill,
    KnowledgeGraphSkill,
    SentimentAnalysisSkill,
    CausalAnalysisSkill,
    DocumentTemplateSkill,
    ArgumentMiningSkill,
    TemporalAnalysisSkill,
    ContradictionDetectorSkill,
)

def register_all_skills():
    for cls in [
        SummarizerSkill,
        DataAnalyzerSkill,
        ChartSpecGeneratorSkill,
        KeywordExtractorSkill,
        TableBuilderSkill,
        ReportSectionWriterSkill,
        KnowledgeEnricherSkill,
        SlideScripterSkill,
        MultiPassWriterSkill,
        BusinessFrameworkSkill,
        InsightGeneratorSkill,
        SqlQuerySkill,
        PythonChartSkill,
        ExcelAnalyzerSkill,
        KnowledgeGraphSkill,
        SentimentAnalysisSkill,
        CausalAnalysisSkill,
        DocumentTemplateSkill,
        ArgumentMiningSkill,
        TemporalAnalysisSkill,
        ContradictionDetectorSkill,
    ]:
        SkillRegistry.register(cls())

__all__ = ["SkillRegistry", "register_all_skills"]
