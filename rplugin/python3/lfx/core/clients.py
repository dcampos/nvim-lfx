from .protocol import WorkspaceFolder
from .sessions import create_session, Session
from .settings import ClientConfig, settings
from .typing import List, Dict, Tuple, Callable, Optional
import os
from .editor import Window


def get_window_env(window: Window, config: ClientConfig) -> Tuple[List[str], Dict[str, str]]:

    # Expand language server command line environment variables
    expanded_args = list(
        os.path.expanduser(arg)
        for arg in config.binary_args
    )

    # Override OS environment variables
    env = os.environ.copy()
    for var, value in config.env.items():
        # Expand both ST and OS environment variables
        env[var] = os.path.expandvars(value)

    return expanded_args, env


def start_window_config(window: Window,
                        workspace_folders: List[WorkspaceFolder],
                        config: ClientConfig,
                        on_pre_initialize: Callable[[Session], None],
                        on_post_initialize: Callable[[Session], None],
                        on_post_exit: Callable[[str], None],
                        on_stderr_log: Optional[Callable[[str], None]]) -> Optional[Session]:
    args, env = get_window_env(window, config)
    config.binary_args = args
    return create_session(config=config,
                          workspace_folders=workspace_folders,
                          env=env,
                          settings=settings,
                          on_pre_initialize=on_pre_initialize,
                          on_post_initialize=on_post_initialize,
                          on_post_exit=lambda config_name: on_session_ended(window, config_name, on_post_exit),
                          on_stderr_log=on_stderr_log)


def on_session_ended(window: Window, config_name: str, on_post_exit_handler: Callable[[str], None]) -> None:
    on_post_exit_handler(config_name)
