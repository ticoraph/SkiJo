"""LLM access used by the public slope-map research project.

Les générations JSON passent par LiteLLM. La recherche web reste adaptée au fournisseur :
Gemini conserve ses outils natifs dans ``gemini_prices_finder.py`` et OpenAI utilise Responses.
"""

from __future__ import annotations

import base64
import copy
import os
from dataclasses import dataclass
from typing import Any

PROVIDERS = {"gemini", "openai"}
DEFAULT_OPENAI_MODEL = "gpt-6-luna"

# Le routage ne dépend pas de la grille tarifaire distante de LiteLLM. La copie livrée avec le
# paquet évite une requête réseau supplémentaire au premier import de chaque script.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "true")


@dataclass
class LLMResponse:
    text: str
    finish_reason: str | None
    usage: dict | None
    grounding: dict | None = None


def provider(value: str | None = None) -> str:
    selected = (value or os.getenv("LLM_PROVIDER", "openai")).strip().lower()
    if selected not in PROVIDERS:
        raise ValueError(f"LLM_PROVIDER doit valoir gemini ou openai (reçu : {selected!r})")
    return selected


def model_for(gemini_default: str, explicit: str | None = None,
              selected_provider: str | None = None) -> str:
    selected = provider(selected_provider)
    if explicit:
        model = explicit
    elif selected == "openai":
        model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    else:
        model = os.getenv("GEMINI_MODEL", gemini_default)
    for prefix in ("openai/", "gemini/", "google/"):
        model = model.removeprefix(prefix)
    return model


def api_key(selected_provider: str | None = None) -> str | None:
    selected = provider(selected_provider)
    if selected == "openai":
        return os.getenv("OPENAI_API_KEY")
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


def require_configuration(parser, selected_provider: str | None = None) -> str:
    selected = provider(selected_provider)
    if not api_key(selected):
        variable = "OPENAI_API_KEY" if selected == "openai" else "GEMINI_API_KEY"
        parser.error(f"{variable} manquante dans resort_slope_maps/.env")
    return selected


def retryable(error: Exception) -> bool:
    status = getattr(error, "status_code", None) or getattr(error, "code", None)
    return status in (429, 500, 502, 503, 504)


def qualified_model(model: str, selected_provider: str | None = None) -> str:
    selected = provider(selected_provider)
    bare = model_for(model, explicit=model, selected_provider=selected)
    return f"{selected}/{bare}"


def _normal_schema(schema: dict) -> dict:
    """Copie un schéma Gemini/OpenAPI sous forme de JSON Schema standard."""
    result = copy.deepcopy(schema)

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            kind = value.get("type")
            if isinstance(kind, str):
                value["type"] = kind.lower()
            elif isinstance(kind, list):
                value["type"] = [item.lower() if isinstance(item, str) else item
                                 for item in kind]
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(result)
    return result


def _nullable(schema: dict) -> dict:
    kind = schema.get("type")
    if isinstance(kind, str):
        schema["type"] = [kind, "null"]
    elif isinstance(kind, list):
        if "null" not in kind:
            schema["type"] = [*kind, "null"]
    elif "anyOf" in schema:
        schema["anyOf"].append({"type": "null"})
    else:
        schema = {"anyOf": [schema, {"type": "null"}]}
    return schema


def strict_schema(schema: dict) -> dict:
    """Rend le schéma compatible avec les Structured Outputs stricts d'OpenAI.

    OpenAI exige toutes les propriétés dans ``required``. Les propriétés auparavant facultatives
    deviennent donc explicitement nullables, ce qui conserve leur sens applicatif.
    """
    result = _normal_schema(schema)

    def visit(value: Any) -> Any:
        if isinstance(value, list):
            return [visit(child) for child in value]
        if not isinstance(value, dict):
            return value
        original_required = set(value.get("required", []))
        properties = value.get("properties")
        if isinstance(properties, dict):
            normalized = {}
            for name, child in properties.items():
                child = visit(child)
                normalized[name] = child if name in original_required else _nullable(child)
            value["properties"] = normalized
            value["required"] = list(properties)
            value["additionalProperties"] = False
        if "items" in value:
            value["items"] = visit(value["items"])
        for keyword in ("anyOf", "oneOf", "allOf"):
            if keyword in value:
                value[keyword] = visit(value[keyword])
        return value

    return visit(result)


def response_format(schema: dict, selected_provider: str | None = None,
                    name: str = "structured_response") -> dict:
    selected = provider(selected_provider)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "schema": strict_schema(schema) if selected == "openai" else _normal_schema(schema),
            "strict": selected == "openai",
        },
    }


def _as_dict(value: Any) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_none=True)
    try:
        return dict(value)
    except (TypeError, ValueError):
        return {}


def usage_dict(usage: Any) -> dict | None:
    raw = _as_dict(usage)
    if not raw:
        return None
    details = _as_dict(raw.get("completion_tokens_details") or raw.get("output_tokens_details"))
    return {
        "prompt": raw.get("prompt_tokens", raw.get("input_tokens")),
        "output": raw.get("completion_tokens", raw.get("output_tokens")),
        "thoughts": details.get("reasoning_tokens"),
        "total": raw.get("total_tokens"),
    }


def user_content(prompt: str, images: list[tuple[str, bytes]] | None = None):
    """Contenu du message : le prompt seul, ou le prompt suivi des images (type MIME, octets),
    jointes dans l'ordre."""
    if not images:
        return prompt
    return [{"type": "text", "text": prompt},
            *({"type": "image_url", "image_url": {
                "url": f"data:{mime};base64,{base64.b64encode(data).decode()}"}}
              for mime, data in images)]


async def generate_json(prompt: str, schema: dict, model: str,
                        selected_provider: str | None = None,
                        name: str = "structured_response", timeout: int = 180,
                        images: list[tuple[str, bytes]] | None = None) -> LLMResponse:
    """Génère un objet JSON structuré via l'interface commune LiteLLM ; `images` (type MIME,
    octets) sont jointes au prompt pour les modèles qui lisent les images."""
    from litellm import acompletion

    selected = provider(selected_provider)
    kwargs = {
        "model": qualified_model(model, selected),
        "messages": [{"role": "user", "content": user_content(prompt, images)}],
        "response_format": response_format(schema, selected, name),
        "api_key": api_key(selected),
        "timeout": timeout,
        "max_retries": 0,
    }
    if selected == "openai":
        kwargs["reasoning_effort"] = "none"
    else:
        kwargs["temperature"] = 0
    response = await acompletion(**kwargs)
    choice = response.choices[0]
    content = choice.message.content
    if not isinstance(content, str) or not content:
        raise ValueError("réponse LLM vide")
    return LLMResponse(content, choice.finish_reason, usage_dict(response.usage))


def _openai_grounding(response: Any) -> dict:
    payload = _as_dict(response)
    queries: list[str] = []
    sources: list[dict] = []
    seen: set[str] = set()
    for item in payload.get("output", []):
        item = _as_dict(item)
        if item.get("type") == "web_search_call":
            action = _as_dict(item.get("action"))
            query = action.get("query")
            if isinstance(query, str) and query not in queries:
                queries.append(query)
            for source in action.get("sources") or item.get("results") or []:
                source = _as_dict(source)
                url = source.get("url") or source.get("uri")
                if isinstance(url, str) and url not in seen:
                    seen.add(url)
                    sources.append({"title": source.get("title") or url, "uri": url})
        if item.get("type") == "message":
            for content in item.get("content") or []:
                for annotation in _as_dict(content).get("annotations") or []:
                    annotation = _as_dict(annotation)
                    citation = _as_dict(annotation.get("url_citation"))
                    url = citation.get("url") or annotation.get("url")
                    title = citation.get("title") or annotation.get("title") or url
                    if isinstance(url, str) and url not in seen:
                        seen.add(url)
                        sources.append({"title": title, "uri": url})
    return {"search_queries": queries, "search_sources": sources, "url_context": []}


async def research_json(prompt: str, schema: dict, model: str,
                        name: str = "structured_research",
                        search_context_size: str = "high") -> LLMResponse:
    """Recherche web OpenAI avec Responses, puis rend le JSON demandé."""
    from litellm import aresponses

    response = await aresponses(
        model=qualified_model(model, "openai"),
        input=prompt,
        tools=[{"type": "web_search", "search_context_size": search_context_size}],
        tool_choice="required",
        include=["web_search_call.action.sources"],
        reasoning={"effort": "low"},
        store=False,
        text={"format": {
            "type": "json_schema",
            "name": name,
            "schema": strict_schema(schema),
            "strict": True,
        }},
        api_key=api_key("openai"),
        timeout=240,
    )
    text = response.output_text
    if not text:
        raise ValueError("réponse OpenAI vide")
    return LLMResponse(text, response.status, usage_dict(response.usage),
                       _openai_grounding(response))
