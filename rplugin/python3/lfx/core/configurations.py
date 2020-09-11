from .editor import View
from copy import deepcopy
from .logging import debug
from .types import ClientConfig, WindowLike
from .types import config_supports_syntax
from .typing import List, Tuple, Optional, Iterator
from .workspace import get_project_config


def get_scope_client_config(view: View, configs: List[ClientConfig],
                            point: Optional[int] = None) -> Optional[ClientConfig]:
    return next(get_scope_client_configs(view, configs, point), None)


def get_scope_client_configs(view: View, configs: List[ClientConfig],
                             point: Optional[int] = None) -> Iterator[ClientConfig]:
    # When there are multiple server configurations, all of which are for
    # similar scopes (e.g. 'source.json', 'source.json.settings') the
    # configuration with the most specific scope (highest ranked selector)
    # in the current position is preferred.
    if point is None:
        sel = view.sel()
        if len(sel) > 0:
            point = sel[0].begin()

    languages = view.settings().get('lsp_language', None)
    scope_configs = []  # type: List[Tuple[ClientConfig, Optional[int]]]

    for config in configs:
        if config.enabled:
            if languages is None or config.name in languages:
                for language in config.languages:
                    for scope in language.scopes:
                        score = 0
                        if point is not None:
                            score = view.score_selector(point, scope)
                        if score > 0:
                            scope_configs.append((config, score))
                            # debug('scope {} score {}'.format(scope, score))

    return (config_score[0] for config_score in sorted(
        scope_configs, key=lambda config_score: config_score[1], reverse=True))


def get_global_client_config(view: View, global_configs: List[ClientConfig]) -> Optional[ClientConfig]:
    return get_scope_client_config(view, global_configs)


def create_window_configs(window: WindowLike, global_configs: List[ClientConfig]) -> List[ClientConfig]:
    window_config = get_project_config(window)
    return list(map(lambda c: apply_project_overrides(c, window_config), global_configs))


def apply_project_overrides(client_config: ClientConfig, lsp_project_settings: dict) -> ClientConfig:
    if client_config.name in lsp_project_settings:
        overrides = lsp_project_settings[client_config.name]
        debug('window has override for {}'.format(client_config.name), overrides)
        client_settings = _merge_dicts(client_config.settings, overrides.get("settings", {}))
        client_env = _merge_dicts(client_config.env, overrides.get("env", {}))
        return ClientConfig(
            client_config.name,
            overrides.get("command", client_config.binary_args),
            overrides.get("tcp_port", client_config.tcp_port),
            [],
            [],
            "",
            client_config.languages,
            overrides.get("enabled", client_config.enabled),
            overrides.get("initializationOptions", client_config.init_options),
            client_settings,
            client_env,
            overrides.get("tcp_host", client_config.tcp_host),
            overrides.get("experimental_capabilities", client_config.experimental_capabilities),
        )

    return client_config


def is_supported_syntax(syntax: str, configs: List[ClientConfig]) -> bool:
    for config in configs:
        if config_supports_syntax(config, syntax):
            return True
    return False


def _merge_dicts(dict_a: dict, dict_b: dict) -> dict:
    """Merge dict_b into dict_a with one level of recurse"""
    result_dict = deepcopy(dict_a)
    for key, value in dict_b.items():
        if isinstance(result_dict.get(key), dict) and isinstance(value, dict):
            result_dict.setdefault(key, {}).update(value)
        else:
            result_dict[key] = value
    return result_dict
