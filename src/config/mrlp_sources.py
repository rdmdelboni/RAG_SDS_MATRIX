"""Curated sources for MRLP ingestion and RAG provenance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class SourceDomain:
    """Descriptor for an allowed MRLP data source."""

    name: str
    domain: str
    category: str
    notes: str


# High-trust domains used to build the chemical safety corpus (MRLP)
MRLP_SOURCE_DOMAINS: Final[list[SourceDomain]] = [
    SourceDomain(
        name="UNIFAL-MG Incompatibilidade Química",
        domain="unifal-mg.edu.br",
        category="incompatibility",
        notes="Regras binárias substância-vs-substância.",
    ),
    SourceDomain(
        name="CAMEO Chemicals / NOAA",
        domain="cameochemicals.noaa.gov",
        category="reactivity",
        notes="Grupos reativos e reatividade de emergência.",
    ),
    SourceDomain(
        name="CAMEO Reactivity Worksheet",
        domain="response.restoration.noaa.gov",
        category="reactivity",
        notes="Planilhas e materiais de resposta emergencial.",
    ),
    SourceDomain(
        name="CAMEO Portal",
        domain="cameo.noaa.gov",
        category="reactivity",
        notes="Portal geral do CAMEO/NOAA.",
    ),
    SourceDomain(
        name="ABNT",
        domain="abnt.org.br",
        category="norms",
        notes="NBR 14725 (partes 1-4) - requer aquisição oficial.",
    ),
    SourceDomain(
        name="MTE/SEPRT (NR-20/NR-26)",
        domain="gov.br",
        category="norms",
        notes="Normas Regulamentadoras brasileiras.",
    ),
    SourceDomain(
        name="CETESB",
        domain="cetesb.sp.gov.br",
        category="environment",
        notes="Valores orientadores e risco ambiental SP.",
    ),
    SourceDomain(
        name="CETESB Sistemas",
        domain="sistemasinter.cetesb.sp.gov.br",
        category="environment",
        notes="Consultas de produtos e dados ambientais.",
    ),
    SourceDomain(
        name="NIOSH Pocket Guide",
        domain="cdc.gov",
        category="toxicology",
        notes="IDLH, REL/PEL, métodos analíticos.",
    ),
    SourceDomain(
        name="OSHA",
        domain="osha.gov",
        category="occupational",
        notes="Boas práticas de exposição e armazenamento.",
    ),
    SourceDomain(
        name="CAS / Safe Science",
        domain="safescience.cas.org",
        category="nomenclature",
        notes="Padronização de nomes e alertas de reação.",
    ),
    SourceDomain(
        name="CAS",
        domain="cas.org",
        category="nomenclature",
        notes="Referência adicional de CAS.",
    ),
    SourceDomain(
        name="NFPA 400",
        domain="nfpa.org",
        category="reference",
        notes="Critérios complementares de segregação.",
    ),
    SourceDomain(
        name="ONU / GHS (Purple Book)",
        domain="unece.org",
        category="norms",
        notes="Base global do GHS.",
    ),
    SourceDomain(
        name="CSB",
        domain="csb.gov",
        category="investigation",
        notes="Relatórios e lições aprendidas.",
    ),
    SourceDomain(
        name="EPA",
        domain="epa.gov",
        category="reference",
        notes="Materiais de resposta e intoxicação por pesticidas.",
    ),
]


# Default whitelist (includes parent domains so subdomains are covered)
DEFAULT_MRLP_ALLOWED_DOMAINS: Final[set[str]] = {
    src.domain for src in MRLP_SOURCE_DOMAINS
}
