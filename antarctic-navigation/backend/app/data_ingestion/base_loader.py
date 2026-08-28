import os
import glob
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseLoader(ABC):
    def __init__(self, dataset_path: str):
        self.dataset_path = dataset_path

    def search_files(self, patterns: List[str]) -> List[str]:
        files = []
        for pattern in patterns:
            search_path = os.path.join(self.dataset_path, "**", pattern)
            files.extend(glob.glob(search_path, recursive=True))
        return files

    @abstractmethod
    def validate_file(self, filepath: str) -> bool:
        pass

    @abstractmethod
    def parse_metadata(self, filepath: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def load(self, filepath: str) -> Any:
        pass

    def get_provenance(self) -> Dict[str, Any]:
        return {"source": "unknown"}
