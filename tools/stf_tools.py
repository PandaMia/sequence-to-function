"""Function tools for the consolidated STF agent."""

from __future__ import annotations

from agents import function_tool

from tools.logic.article import fetch_article_content_logic, web_search_logic
from tools.logic.database import (
    execute_sql_query_logic,
    find_article_records_logic,
    find_gene_records_logic,
    save_to_database_logic,
)
from tools.logic.uniprot import get_uniprot_id_logic
from tools.logic.vision import vision_media_logic
from tools.schemas import (
    ArticleContext,
    ExecuteSQLQueryInput,
    ExecuteSQLQueryOutput,
    FetchArticleContentInput,
    FindArticleRecordsInput,
    FindArticleRecordsOutput,
    FindGeneRecordsInput,
    FindGeneRecordsOutput,
    GetUniProtIdInput,
    GetUniProtIdOutput,
    SaveSequenceDataInput,
    SaveSequenceDataOutput,
    VisionMediaInput,
    VisionMediaOutput,
    WebSearchInput,
    WebSearchOutput,
)
from tools.tool_wrappers import add_output_schema_to_docstring, flatten_params_from_signature


class STFTools:
    """Function tools available to the single STF agent."""

    @staticmethod
    @function_tool
    @add_output_schema_to_docstring
    @flatten_params_from_signature
    def get_uniprot_id(params: GetUniProtIdInput) -> GetUniProtIdOutput:
        """Resolve a gene symbol to a UniProt Swiss-Prot ID."""

        result = get_uniprot_id_logic(params)
        return GetUniProtIdOutput(**result.model_dump())

    @staticmethod
    @function_tool
    @add_output_schema_to_docstring
    @flatten_params_from_signature
    async def save_to_database(params: SaveSequenceDataInput) -> SaveSequenceDataOutput:
        """Save extracted sequence-function data to the database."""

        result = await save_to_database_logic(params)
        return SaveSequenceDataOutput(**result.model_dump())

    @staticmethod
    @function_tool
    @add_output_schema_to_docstring
    @flatten_params_from_signature
    def fetch_article_content(params: FetchArticleContentInput) -> ArticleContext:
        """Fetch and extract content, relevant images, and PDFs from a research article URL."""

        result = fetch_article_content_logic(params)
        return ArticleContext(**result.model_dump())

    @staticmethod
    @function_tool
    @add_output_schema_to_docstring
    @flatten_params_from_signature
    def web_search(params: WebSearchInput) -> WebSearchOutput:
        """Search the web for article content or supporting source material."""

        result = web_search_logic(params)
        return WebSearchOutput(**result.model_dump())

    @staticmethod
    @function_tool
    @add_output_schema_to_docstring
    @flatten_params_from_signature
    def vision_media(params: VisionMediaInput) -> VisionMediaOutput:
        """Analyze scientific images and PDFs for sequence-function evidence."""

        result = vision_media_logic(params)
        return VisionMediaOutput(**result.model_dump())

    @staticmethod
    @function_tool
    @add_output_schema_to_docstring
    @flatten_params_from_signature
    async def execute_sql_query(params: ExecuteSQLQueryInput) -> ExecuteSQLQueryOutput:
        """Execute a read-only SQL SELECT query against the STF database."""

        result = await execute_sql_query_logic(params)
        return ExecuteSQLQueryOutput(**result.model_dump())

    @staticmethod
    @function_tool
    @add_output_schema_to_docstring
    @flatten_params_from_signature
    async def find_article_records(params: FindArticleRecordsInput) -> FindArticleRecordsOutput:
        """Check whether an article URL already has parsed sequence-function records."""

        result = await find_article_records_logic(params)
        return FindArticleRecordsOutput(**result.model_dump())

    @staticmethod
    @function_tool
    @add_output_schema_to_docstring
    @flatten_params_from_signature
    async def find_gene_records(params: FindGeneRecordsInput) -> FindGeneRecordsOutput:
        """Find sequence-function records by gene name or UniProt ID."""

        result = await find_gene_records_logic(params)
        return FindGeneRecordsOutput(**result.model_dump())


get_uniprot_id = STFTools.get_uniprot_id
save_to_database = STFTools.save_to_database
fetch_article_content = STFTools.fetch_article_content
web_search = STFTools.web_search
vision_media = STFTools.vision_media
execute_sql_query = STFTools.execute_sql_query
find_article_records = STFTools.find_article_records
find_gene_records = STFTools.find_gene_records
