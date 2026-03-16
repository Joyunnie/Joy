import yaml


class AgentConfig:
    def __init__(self, data: dict):
        self._data = data
        self.agent = _Section(data.get("agent", {}))
        self.pm20 = _Section(data.get("pm20", {}))
        self.backup = _Section(data.get("backup", {}))


class _Section:
    def __init__(self, data: dict):
        self._data = data

    def __getattr__(self, name: str):
        if name.startswith("_"):
            return super().__getattribute__(name)
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(f"Config key not found: {name}")

    def get(self, key: str, default=None):
        return self._data.get(key, default)


def load_config(path: str) -> AgentConfig:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return AgentConfig(data)
