import asyncio
import json
import shutil
from dataclasses import dataclass
from typing import Any

from mirror.config import Settings
from mirror.errors import KrakenCliCommandFailed, KrakenCliNotInstalled, KrakenNotPaperMode, KrakenSymbolDiscoveryFailed


@dataclass(frozen=True)
class KrakenCommandResult:
    args: list[str]
    stdout: str
    stderr: str
    json_data: Any


class KrakenClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def ensure_installed(self) -> None:
        if shutil.which(self.settings.kraken_cli_path) is None:
            raise KrakenCliNotInstalled(
                "Kraken CLI not found. Install with: cargo install --git https://github.com/krakenfx/kraken-cli"
            )

    async def run_json(self, args: list[str], timeout: float | None = None) -> KrakenCommandResult:
        self.ensure_installed()
        full_args = [self.settings.kraken_cli_path, *args]
        proc = await asyncio.create_subprocess_exec(
            *full_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout or self.settings.kraken_timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            proc.kill()
            raise KrakenCliCommandFailed(f"Kraken CLI timed out: {' '.join(full_args)}") from exc

        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            raise KrakenCliCommandFailed(f"Kraken CLI failed ({proc.returncode}): {stderr.strip()}")
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise KrakenCliCommandFailed(f"Kraken CLI did not return strict JSON for: {' '.join(full_args)}") from exc
        return KrakenCommandResult(args=full_args, stdout=stdout, stderr=stderr, json_data=data)

    async def help_text(self, args: list[str] | None = None) -> str:
        self.ensure_installed()
        proc = await asyncio.create_subprocess_exec(
            self.settings.kraken_cli_path,
            *(args or ["--help"]),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_b, stderr_b = await proc.communicate()
        output = stdout_b.decode("utf-8", errors="replace") + stderr_b.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            raise KrakenCliCommandFailed(output.strip())
        return output

    async def verify_paper_mode(self) -> dict[str, Any]:
        candidates = [
            ["futures", "accounts", "-o", "json"],
            ["futures", "account", "-o", "json"],
            ["paper", "futures", "accounts", "-o", "json"],
        ]
        last_error: Exception | None = None
        for args in candidates:
            try:
                result = await self.run_json(args)
                text = json.dumps(result.json_data).lower()
                if "paper" not in text and self.settings.kraken_require_paper_mode:
                    raise KrakenNotPaperMode("Kraken account response did not confirm paper mode")
                return result.json_data
            except (KrakenCliCommandFailed, KrakenNotPaperMode) as exc:
                last_error = exc
        raise KrakenNotPaperMode(f"Unable to verify Kraken paper mode: {last_error}")

    async def discover_xstock_perp_symbols(self) -> list[str]:
        result = await self.run_json(["futures", "tickers", "-o", "json"])
        symbols = extract_symbols(result.json_data)
        xstock_symbols = [s for s in symbols if is_xstock_perp_symbol(s)]
        if len(xstock_symbols) < 3:
            raise KrakenSymbolDiscoveryFailed(
                f"Fewer than three xStock perpetual symbols discovered from Kraken output. Found: {xstock_symbols}"
            )
        return sorted(set(xstock_symbols))

    async def place_paper_order(
        self,
        symbol: str,
        side: str,
        size_usd: float,
        leverage: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        await self.verify_paper_mode()
        help_text = await self.help_text(["futures", "--help"])
        if "order" not in help_text.lower():
            raise KrakenCliCommandFailed(
                "Kraken futures order command was not discoverable from local `kraken futures --help`; refusing to trade."
            )
        raise KrakenCliCommandFailed(
            "Kraken paper futures order syntax must be verified from local help before enabling placement. "
            "Run `kraken futures --help` and extend KrakenClient with the exact official command surface."
        )


def extract_symbols(payload: Any) -> list[str]:
    symbols: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key.lower() in {"symbol", "ticker", "pair", "instrument", "instrument_name"} and isinstance(value, str):
                symbols.append(value)
            symbols.extend(extract_symbols(value))
    elif isinstance(payload, list):
        for item in payload:
            symbols.extend(extract_symbols(item))
    return symbols


def is_xstock_perp_symbol(symbol: str) -> bool:
    s = symbol.upper()
    return ("XSTOCK" in s or s.endswith("X") or ".X" in s) and ("PERP" in s or "PF_" in s or "PI_" in s)
