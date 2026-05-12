"""UniProt lookup logic for STF tools."""

from __future__ import annotations

import logging

import mygene

from tools.schemas import GetUniProtIdInput, GetUniProtIdOutput


logger = logging.getLogger(__name__)


def get_uniprot_id_logic(params: GetUniProtIdInput) -> GetUniProtIdOutput:
    """Resolve a gene symbol to a UniProt Swiss-Prot ID."""

    try:
        mg = mygene.MyGeneInfo()
        result = mg.query(params.gene_name, fields="uniprot")

        if not result or "hits" not in result or not result["hits"]:
            return GetUniProtIdOutput(gene_name=params.gene_name, protein_uniprot_id="", found=False)

        for hit in result["hits"]:
            uniprot_data = hit.get("uniprot")
            if not uniprot_data:
                continue

            if isinstance(uniprot_data, dict) and uniprot_data.get("Swiss-Prot"):
                swiss_prot = uniprot_data["Swiss-Prot"]
                uniprot_id = swiss_prot[0] if isinstance(swiss_prot, list) else str(swiss_prot)
                return GetUniProtIdOutput(
                    gene_name=params.gene_name,
                    protein_uniprot_id=uniprot_id,
                    found=bool(uniprot_id),
                )

            if isinstance(uniprot_data, str):
                return GetUniProtIdOutput(
                    gene_name=params.gene_name,
                    protein_uniprot_id=uniprot_data,
                    found=True,
                )

            if isinstance(uniprot_data, list) and uniprot_data:
                return GetUniProtIdOutput(
                    gene_name=params.gene_name,
                    protein_uniprot_id=str(uniprot_data[0]),
                    found=True,
                )

        return GetUniProtIdOutput(gene_name=params.gene_name, protein_uniprot_id="", found=False)
    except Exception as exc:
        logger.error("UniProt lookup failed for %s: %s", params.gene_name, exc)
        return GetUniProtIdOutput(gene_name=params.gene_name, protein_uniprot_id="", found=False)
