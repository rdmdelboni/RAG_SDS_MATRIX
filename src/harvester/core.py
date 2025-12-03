from typing import List, Optional
from pathlib import Path
import concurrent.futures
from .base import BaseSDSProvider, SDSMetadata
from ..utils.logger import get_logger

logger = get_logger(__name__)

class SDSHarvester:
    """Manager for harvesting SDS documents from multiple providers."""

    def __init__(self, providers: Optional[List[BaseSDSProvider]] = None):
        self.providers = providers or []
        if not self.providers:
            from .providers.fisher import FisherScientificProvider
            from .providers.chemicalbook import ChemicalBookProvider
            from .providers.chemicalsafety import ChemicalSafetyProvider
            
            self.providers.append(FisherScientificProvider())
            self.providers.append(ChemicalBookProvider())
            self.providers.append(ChemicalSafetyProvider())
    
    def find_sds(self, cas_number: str) -> List[SDSMetadata]:
        """
        Search for SDSs for a given CAS number across all providers.
        Returns a list of found metadata.
        """
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.providers)) as executor:
            future_to_provider = {
                executor.submit(p.search, cas_number): p for p in self.providers
            }
            
            for future in concurrent.futures.as_completed(future_to_provider):
                provider = future_to_provider[future]
                try:
                    provider_results = future.result()
                    results.extend(provider_results)
                    logger.info(f"Found {len(provider_results)} SDSs from {provider.name} for {cas_number}")
                except Exception as exc:
                    logger.error(f"Provider {provider.name} generated an exception: {exc}")
        
        return results

    def download_sds(self, metadata: SDSMetadata, output_dir: Path) -> Optional[Path]:
        """
        Download the SDS described by metadata.
        Returns the path to the downloaded file if successful, else None.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Sanitize filename
        filename = f"{metadata.cas_number}_{metadata.source.replace(' ', '_')}.pdf"
        destination = output_dir / filename
        
        # Find the provider
        provider = next((p for p in self.providers if p.name == metadata.source), None)
        if not provider:
             # Fallback: try to find any provider that can handle this? 
             # For now, assume we can re-instantiate or use the first one if generic, 
             # but correctly we should use the one that found it.
             # If strictly decoupled, we might need a registry. 
             # For now, just iterate or use a default generic downloader?
             # Actually, the `download` method is on the provider instance.
             # If we lost the instance (e.g. across sessions), we need to re-find it.
             # Let's just try to match by name.
             from .providers.fisher import FisherScientificProvider
             from .providers.chemicalbook import ChemicalBookProvider
             from .providers.chemicalsafety import ChemicalSafetyProvider
             
             if metadata.source == "Fisher Scientific":
                 provider = FisherScientificProvider()
             elif metadata.source == "ChemicalBook":
                 provider = ChemicalBookProvider()
             elif metadata.source == "ChemicalSafety":
                 provider = ChemicalSafetyProvider()
             else:
                 logger.error(f"No provider found for source {metadata.source}")
                 return None

        if provider.download(metadata.url, destination):
            return destination
        return None
