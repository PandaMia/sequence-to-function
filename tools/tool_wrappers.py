"""Small helpers for schema-based STF function tools."""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable, Mapping
from functools import wraps
from typing import Any, get_args, get_origin, get_type_hints

from pydantic import BaseModel


def _is_base_model_subclass(candidate: Any) -> bool:
    return inspect.isclass(candidate) and issubclass(candidate, BaseModel)


def _coerce_json_value(annotation: Any, value: Any) -> Any:
    if value is None or not isinstance(value, str):
        return value

    origin = get_origin(annotation)
    supports_json = origin in (list, dict) or _is_base_model_subclass(annotation)
    if not supports_json:
        return value

    stripped = value.strip()
    if not (
        (stripped.startswith("[") and stripped.endswith("]"))
        or (stripped.startswith("{") and stripped.endswith("}"))
    ):
        return value

    try:
        return json.loads(stripped)
    except Exception:
        return value


def _coerce_payload(schema_cls: type[BaseModel], payload: Mapping[str, Any]) -> dict[str, Any]:
    coerced = dict(payload)
    for field_name, field in schema_cls.model_fields.items():
        if field_name not in coerced:
            continue
        annotation = field.annotation
        value = _coerce_json_value(annotation, coerced[field_name])
        origin = get_origin(annotation)
        if origin is list and isinstance(value, list):
            args = get_args(annotation)
            item_annotation = args[0] if args else Any
            value = [_coerce_json_value(item_annotation, item) for item in value]
        coerced[field_name] = value
    return coerced


def flatten_params_from_signature(
    fn: Callable[..., Any],
    *,
    params_name: str = "params",
) -> Callable[..., Any]:
    """Expand a BaseModel-typed `params` argument into function tool kwargs."""

    sig = inspect.signature(fn)
    if params_name not in sig.parameters:
        raise TypeError(f"{fn.__name__} must include a '{params_name}' parameter")

    hints = get_type_hints(fn)
    schema_cls = hints.get(params_name)
    if not _is_base_model_subclass(schema_cls):
        raise TypeError(f"{fn.__name__} must annotate '{params_name}' with a BaseModel subclass")

    has_ctx = "ctx" in sig.parameters
    new_params: list[inspect.Parameter] = []
    annotations: dict[str, Any] = {}
    for param in sig.parameters.values():
        if param.name == params_name:
            for field_name, field in schema_cls.model_fields.items():
                new_params.append(
                    inspect.Parameter(
                        field_name,
                        inspect.Parameter.KEYWORD_ONLY,
                        default=field,
                        annotation=field.annotation or inspect._empty,
                    )
                )
                annotations[field_name] = field.annotation or inspect._empty
        else:
            new_params.append(param)
            annotations[param.name] = param.annotation

    if "return" in getattr(fn, "__annotations__", {}):
        annotations["return"] = fn.__annotations__["return"]

    new_sig = sig.replace(parameters=new_params)

    @wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        bound = new_sig.bind_partial(*args, **kwargs)
        ctx = bound.arguments.pop("ctx", None)
        payload = _coerce_payload(schema_cls, bound.arguments)
        params = schema_cls.model_validate(payload)
        result = fn(ctx, params) if has_ctx else fn(params)
        if inspect.isawaitable(result):
            return await result
        return result

    wrapper.__signature__ = new_sig  # type: ignore[attr-defined]
    wrapper.__annotations__ = annotations
    return wrapper


def add_output_schema_to_docstring(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Append the pydantic output schema fields to a tool docstring."""

    try:
        return_type = get_type_hints(fn).get("return")
    except Exception:
        return fn

    if not _is_base_model_subclass(return_type):
        return fn

    fields = "\n".join(f"    {name}" for name in return_type.model_fields)
    doc = inspect.getdoc(fn) or ""
    fn.__doc__ = f"{doc}\n\nReturns:\n{fields}" if doc else f"Returns:\n{fields}"
    return fn
