from models.underwriting import UWAssumptions
from config import load_settings


def get_default_assumptions() -> UWAssumptions:
    settings = load_settings()
    return UWAssumptions(**{k: v for k, v in settings.items() if k in UWAssumptions.model_fields})


def assumptions_from_dict(d: dict) -> UWAssumptions:
    defaults = load_settings()
    merged = {**defaults, **{k: v for k, v in d.items() if v is not None}}
    return UWAssumptions(**{k: v for k, v in merged.items() if k in UWAssumptions.model_fields})
