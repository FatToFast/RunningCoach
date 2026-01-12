"""Evaluation datasets.

Datasets are collections of real-world test cases:
- real_failures.json: Cases derived from actual user complaints/bugs
- edge_cases.json: Boundary conditions and unusual scenarios
- balanced_tests.json: Mix of "should do" and "should not do" cases
"""

import json
from pathlib import Path


def load_dataset(name: str) -> list[dict]:
    """Load a dataset by name.

    Args:
        name: Dataset name (without .json extension)

    Returns:
        List of test cases from the dataset
    """
    dataset_path = Path(__file__).parent / f"{name}.json"
    if not dataset_path.exists():
        return []
    with open(dataset_path, encoding="utf-8") as f:
        return json.load(f)


def get_all_datasets() -> dict[str, list[dict]]:
    """Load all available datasets.

    Returns:
        Dictionary mapping dataset names to test cases
    """
    datasets = {}
    for path in Path(__file__).parent.glob("*.json"):
        name = path.stem
        datasets[name] = load_dataset(name)
    return datasets
