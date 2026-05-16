def basic_regime_tags(volume_zscore: float | None = None, volatility_bps: float | None = None) -> list[str]:
    tags: list[str] = []
    if volatility_bps is not None:
        tags.append("high_volatility" if volatility_bps >= 100 else "low_volatility")
    if volume_zscore is not None:
        tags.append("high_volume" if volume_zscore >= 1 else "normal_volume")
    return tags

