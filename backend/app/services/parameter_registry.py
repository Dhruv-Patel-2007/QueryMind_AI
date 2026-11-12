"""ParameterRegistry for QueryMind AI 2.0 (Phase 6.1).

Provides an immutable, typed parameter container and builder to extract user-supplied
literals into parameterized placeholders (:param_0, :param_1), completely eliminating
dynamic string interpolation and defending against SQL injection prior to SQL generation.
"""

import math
import re
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Tuple, Union
from pydantic import BaseModel, ConfigDict, model_serializer

# Supported primitive immutable scalar types only.
# Mutable collections (lists, dicts, sets, bytearrays) are strictly prohibited.
SupportedScalar = Union[str, int, float, bool, None]

# Regular expression pattern enforcing strictly formatted parameter keys.
PARAMETER_KEY_PATTERN = re.compile(r"^param_\d+$")


class ParameterRegistry(BaseModel):
    """Deeply immutable registry of bound query parameters and catalog typing metadata."""
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    _bindings_tuple: Tuple[Tuple[str, SupportedScalar], ...] = ()
    _types_tuple: Tuple[Tuple[str, str], ...] = ()

    def __init__(
        self,
        bindings: Optional[Dict[str, SupportedScalar]] = None,
        types: Optional[Dict[str, str]] = None,
        **data: Any,
    ) -> None:
        super().__init__(**data)
        b = bindings or {}
        t = types or {}

        # 1. Enforce identical key sets
        b_keys = set(b.keys())
        t_keys = set(t.keys())
        if b_keys != t_keys:
            raise ValueError(
                f"Parameter key set mismatch: bindings keys {b_keys} != types keys {t_keys}"
            )

        # 2. Enforce valid key syntax and primitive scalar types
        for k, v in b.items():
            if not PARAMETER_KEY_PATTERN.match(k):
                raise ValueError(
                    f"Invalid parameter key format: '{k}'. Must match pattern '^param_\\d+$'."
                )
            if v is not None and not isinstance(v, (str, int, float, bool)):
                raise TypeError(
                    f"Parameter value for '{k}' must be an immutable scalar, got {type(v).__name__}."
                )
            if isinstance(v, float) and not math.isfinite(v):
                raise ValueError(
                    f"Float parameter value for '{k}' must be finite; NaN and Infinity are prohibited."
                )

        # 3. Deeply freeze into sorted immutable tuples of pairs
        object.__setattr__(self, "_bindings_tuple", tuple(sorted(b.items())))
        object.__setattr__(self, "_types_tuple", tuple(sorted(t.items())))

    @property
    def bindings(self) -> Mapping[str, SupportedScalar]:
        """Read-only mapping proxy of parameter bindings."""
        return MappingProxyType(dict(self._bindings_tuple))

    @property
    def types(self) -> Mapping[str, str]:
        """Read-only mapping proxy of parameter catalog data types."""
        return MappingProxyType(dict(self._types_tuple))

    def get_binding(self, key: str) -> SupportedScalar:
        """Retrieves a bound scalar value by parameter key."""
        d = dict(self._bindings_tuple)
        if key not in d:
            raise KeyError(f"Parameter key '{key}' is not registered.")
        return d[key]

    def get_type(self, key: str) -> str:
        """Retrieves the catalog data type for a parameter key."""
        d = dict(self._types_tuple)
        if key not in d:
            raise KeyError(f"Parameter key '{key}' has no registered type.")
        return d[key]

    def __len__(self) -> int:
        return len(self._bindings_tuple)

    @model_serializer
    def ser_model(self) -> Dict[str, Any]:
        """Pydantic v2 JSON serialization compatibility."""
        return {
            "bindings": dict(self._bindings_tuple),
            "types": dict(self._types_tuple),
        }


class ParameterBuilder:
    """Stateful builder used by QueryPlanner to register parameters during IR construction."""

    def __init__(self) -> None:
        self._counter: int = 0
        self._bindings: Dict[str, SupportedScalar] = {}
        self._types: Dict[str, str] = {}

    def register(self, value: Any, column_type: str = "VARCHAR") -> str:
        """Registers a scalar literal value, validates its type, and returns its parameter key.

        Args:
            value: Primitive immutable scalar value (str, int, float, bool, or None).
            column_type: Target catalog column SQL type (INTEGER, FLOAT, VARCHAR, DATE, etc.).

        Returns:
            Registered parameter placeholder key (e.g., 'param_0').
        """
        # 1. Primitive scalar type validation
        if value is not None and not isinstance(value, (str, int, float, bool)):
            raise TypeError(
                f"Parameter value must be an immutable scalar (str, int, float, bool, None), "
                f"got {type(value).__name__}."
            )

        norm_type = column_type.upper().strip()

        # 2. Strict type compatibility validation against catalog column data type
        if value is not None:
            if norm_type in ("INTEGER", "INT", "BIGINT", "SMALLINT"):
                if type(value) is bool or not isinstance(value, int):
                    raise TypeError(
                        f"Type mismatch: expected INTEGER for column type '{column_type}', "
                        f"got {type(value).__name__} ({value!r})."
                    )
            elif norm_type in ("FLOAT", "REAL", "NUMERIC", "DOUBLE", "DECIMAL"):
                if type(value) is bool or not isinstance(value, (int, float)):
                    raise TypeError(
                        f"Type mismatch: expected FLOAT/numeric for column type '{column_type}', "
                        f"got {type(value).__name__} ({value!r})."
                    )
                if isinstance(value, float) and not math.isfinite(value):
                    raise ValueError(
                        f"Float parameter value must be finite; NaN and Infinity are prohibited."
                    )
            elif norm_type in ("VARCHAR", "TEXT", "STRING", "CHAR", "DATE"):
                if not isinstance(value, str):
                    raise TypeError(
                        f"Type mismatch: expected string for column type '{column_type}', "
                        f"got {type(value).__name__} ({value!r})."
                    )

        key = f"param_{self._counter}"
        self._counter += 1
        self._bindings[key] = value
        self._types[key] = norm_type
        return key

    def build(self) -> ParameterRegistry:
        """Constructs and returns the finalized immutable ParameterRegistry."""
        return ParameterRegistry(
            bindings=dict(self._bindings),
            types=dict(self._types),
        )

