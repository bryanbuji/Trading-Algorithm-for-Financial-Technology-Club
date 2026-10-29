from dataclasses import dataclass
from pathlib import Path
from typing import Any, Union

import yaml


@dataclass(frozen=True)
class Config:
    values: dict[str, Any]

    def __getitem__(self, key: str) -> Any:
        return self.values[key]


def load_config(path: Union[str, Path] = "config.yaml") -> Config:
    with Path(path).open() as handle:
        values = yaml.safe_load(handle)
    if not isinstance(values, dict):
        raise ValueError(f"Configuration must be a mapping: {path}")
    if values.get("direction") != "long_only":
        raise ValueError("direction must be long_only; short selling is not implemented")
    return Config(values)
