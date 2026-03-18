from ..config_store import load_config, save_config


def demo_state() -> dict:
    return load_config()["demo"]


def update_demo(section: str, values: dict) -> dict:
    config = load_config()
    demo = config.setdefault("demo", {})
    demo.setdefault(section, {})
    demo[section].update(values)
    save_config(config)
    return demo[section]


def save_demo_state(state: dict) -> None:
    config = load_config()
    config["demo"] = state
    save_config(config)


def load_settings() -> dict:
    return load_config()


def update_settings(section: str, values: dict) -> dict:
    config = load_config()
    config.setdefault(section, {})
    config[section].update(values)
    save_config(config)
    return config
