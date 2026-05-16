from dataclasses import dataclass


def direction_to_probability_up(predicted_direction: str, confidence: float) -> float:
    if not 0 <= confidence <= 1:
        raise ValueError("confidence must be between 0 and 1")
    match predicted_direction:
        case "long":
            return confidence
        case "short":
            return 1 - confidence
        case "flat":
            return 0.5
        case _:
            raise ValueError(f"unsupported predicted_direction: {predicted_direction}")


def brier_score(probability_up: float, realized_direction: str) -> float:
    if not 0 <= probability_up <= 1:
        raise ValueError("probability_up must be between 0 and 1")
    outcome = 1.0 if realized_direction == "up" else 0.0
    return (probability_up - outcome) ** 2


@dataclass(frozen=True)
class CalibrationBucket:
    lower: float
    upper: float
    count: int
    predicted_avg: float | None
    realized_frequency: float | None


def calibration_buckets(samples: list[tuple[float, float]], bin_count: int = 10) -> list[CalibrationBucket]:
    buckets: list[CalibrationBucket] = []
    width = 1.0 / bin_count
    for i in range(bin_count):
        lower = i * width
        upper = 1.0 if i == bin_count - 1 else (i + 1) * width
        if i == bin_count - 1:
            members = [(p, o) for p, o in samples if lower <= p <= upper]
        else:
            members = [(p, o) for p, o in samples if lower <= p < upper]
        if not members:
            buckets.append(CalibrationBucket(lower, upper, 0, None, None))
            continue
        buckets.append(
            CalibrationBucket(
                lower=lower,
                upper=upper,
                count=len(members),
                predicted_avg=sum(p for p, _ in members) / len(members),
                realized_frequency=sum(o for _, o in members) / len(members),
            )
        )
    return buckets
