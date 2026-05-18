import asyncio
import json
import os
import re
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


@dataclass(frozen=True)
class KrakenTickerRecord:
    symbol: str
    pair: str | None
    price: float
    bid: float | None
    ask: float | None
    change24h: float | None
    volume_quote: float | None
    raw: dict[str, Any]


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
        full_args = [self.settings.kraken_cli_path, *self._with_cli_overrides(args)]
        display_args = redact_args(full_args)
        env = self._subprocess_env()
        stdin_payload = self._stdin_secret_for(args)
        proc = await asyncio.create_subprocess_exec(
            *full_args,
            stdin=asyncio.subprocess.PIPE if stdin_payload is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(stdin_payload.encode("utf-8") if stdin_payload is not None else None),
                timeout=timeout or self.settings.kraken_timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            proc.kill()
            raise KrakenCliCommandFailed(f"Kraken CLI timed out: {' '.join(display_args)}") from exc

        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            raise KrakenCliCommandFailed(f"Kraken CLI failed ({proc.returncode}) for {' '.join(display_args)}: {stderr.strip()}")
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise KrakenCliCommandFailed(f"Kraken CLI did not return strict JSON for: {' '.join(display_args)}") from exc
        return KrakenCommandResult(args=full_args, stdout=stdout, stderr=stderr, json_data=data)

    def _with_cli_overrides(self, args: list[str]) -> list[str]:
        updated = list(args)
        if not updated or updated[0] != "futures":
            return updated
        if self.settings.kraken_futures_url and "--futures-url" not in updated:
            updated.extend(["--futures-url", self.settings.kraken_futures_url])
        if self.settings.kraken_api_key and "--api-key" not in updated:
            updated.extend(["--api-key", self.settings.kraken_api_key])
        if self.settings.kraken_api_secret and "--api-secret-stdin" not in updated and "--api-secret" not in updated:
            updated.append("--api-secret-stdin")
        return updated

    def _stdin_secret_for(self, args: list[str]) -> str | None:
        if args and args[0] == "futures" and self.settings.kraken_api_secret:
            return self.settings.kraken_api_secret
        return None

    def _subprocess_env(self) -> dict[str, str]:
        env = os.environ.copy()
        if self.settings.kraken_api_key:
            env["KRAKEN_API_KEY"] = self.settings.kraken_api_key
        if self.settings.kraken_api_secret:
            env["KRAKEN_API_SECRET"] = self.settings.kraken_api_secret
        if self.settings.kraken_futures_url:
            env["KRAKEN_FUTURES_URL"] = self.settings.kraken_futures_url
        if self.settings.kraken_danger_allow_any_url_host:
            env["KRAKEN_DANGER_ALLOW_ANY_URL_HOST"] = "1"
        return env

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
        try:
            status = (await self.run_json(["futures", "paper", "status", "-o", "json"])).json_data
        except KrakenCliCommandFailed:
            init_response = await self.run_json(["futures", "paper", "init", "-o", "json"])
            status = init_response.json_data

        balance = (await self.run_json(["futures", "paper", "balance", "-o", "json"])).json_data
        payload = {"status": status, "balance": balance}
        text = json.dumps(payload).lower()
        if self.settings.kraken_require_paper_mode and "paper" not in text:
            raise KrakenNotPaperMode("Kraken futures paper status/balance did not confirm paper mode")
        return payload

    async def verify_execution_mode(self) -> dict[str, Any]:
        if self.settings.kraken_execution_mode == "paper":
            return await self.verify_paper_mode()
        if self.settings.kraken_execution_mode != "account":
            raise KrakenCliCommandFailed(f"Unsupported KRAKEN_EXECUTION_MODE={self.settings.kraken_execution_mode}")
        if self.settings.kraken_require_paper_mode:
            raise KrakenNotPaperMode("KRAKEN_EXECUTION_MODE=account requires KRAKEN_REQUIRE_PAPER_MODE=false")
        if not self.settings.kraken_api_key or not self.settings.kraken_api_secret:
            raise KrakenCliCommandFailed("KRAKEN_API_KEY and KRAKEN_API_SECRET are required for account-backed Kraken CLI trading")
        accounts = (await self.run_json(["futures", "accounts", "-o", "json"])).json_data
        positions = (await self.run_json(["futures", "positions", "-o", "json"])).json_data
        return {"status": {"mode": "account"}, "accounts": accounts, "positions": positions}

    async def discover_xstock_perp_symbols(self) -> list[str]:
        result = await self.run_json(["futures", "tickers", "-o", "json"])
        xstock_symbols = extract_xstock_perp_symbols(result.json_data)
        if len(xstock_symbols) < 3:
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
        reduce_only: bool = False,
    ) -> dict[str, Any]:
        if side not in {"buy", "sell"}:
            raise KrakenCliCommandFailed(f"Invalid futures paper side: {side}")
        if size_usd <= 0:
            raise KrakenCliCommandFailed(f"Invalid futures paper size: {size_usd}")
        if leverage < 1:
            raise KrakenCliCommandFailed(f"Invalid futures paper leverage: {leverage}")

        await self.verify_paper_mode()
        ticker_payload = (await self.run_json(["futures", "tickers", "-o", "json"])).json_data
        price = extract_price_for_symbol(ticker_payload, symbol)
        if price is None or price <= 0:
            raise KrakenCliCommandFailed(f"Could not derive futures paper order size for {symbol}: ticker price unavailable")
        size = size_usd / price
        args = [
            "futures",
            "paper",
            side,
            symbol,
            format_cli_number(size),
            "--leverage",
            str(leverage),
            "--type",
            "market",
            "--client-order-id",
            idempotency_key,
            "-o",
            "json",
        ]
        if reduce_only:
            args.insert(-2, "--reduce-only")
        result = await self.run_json(args)
        text = json.dumps(result.json_data).lower()
        if self.settings.kraken_require_paper_mode and "futures_paper" not in text and "paper" not in text:
            raise KrakenNotPaperMode("Kraken order response did not confirm futures paper mode")
        return result.json_data

    async def place_order(
        self,
        symbol: str,
        side: str,
        size_usd: float,
        leverage: int,
        idempotency_key: str,
        reduce_only: bool = False,
    ) -> dict[str, Any]:
        if self.settings.kraken_execution_mode == "paper":
            return await self.place_paper_order(symbol, side, size_usd, leverage, idempotency_key, reduce_only)
        return await self.place_account_order(symbol, side, size_usd, idempotency_key, reduce_only)

    async def place_account_order(
        self,
        symbol: str,
        side: str,
        size_usd: float,
        idempotency_key: str,
        reduce_only: bool = False,
    ) -> dict[str, Any]:
        if side not in {"buy", "sell"}:
            raise KrakenCliCommandFailed(f"Invalid futures side: {side}")
        if size_usd <= 0:
            raise KrakenCliCommandFailed(f"Invalid futures size: {size_usd}")

        await self.verify_execution_mode()
        ticker_payload = (await self.run_json(["futures", "tickers", "-o", "json"])).json_data
        price = extract_price_for_symbol(ticker_payload, symbol)
        if price is None or price <= 0:
            raise KrakenCliCommandFailed(f"Could not derive futures order size for {symbol}: ticker price unavailable")
        size = size_usd / price
        args = [
            "futures",
            "order",
            side,
            symbol,
            format_cli_number(size),
            "--type",
            "market",
            "--client-order-id",
            idempotency_key,
            "-o",
            "json",
        ]
        if reduce_only:
            args.insert(-2, "--reduce-only")
        result = await self.run_json(args)
        return result.json_data

    async def futures_paper_balance(self) -> dict[str, Any]:
        return (await self.run_json(["futures", "paper", "balance", "-o", "json"])).json_data

    async def trading_status(self) -> dict[str, Any]:
        if self.settings.kraken_execution_mode == "account":
            return await self.verify_execution_mode()
        status = (await self.run_json(["futures", "paper", "status", "-o", "json"])).json_data
        positions = (await self.run_json(["futures", "paper", "positions", "-o", "json"])).json_data
        return {"status": status, "positions": positions}

    async def futures_tickers(self) -> dict[str, Any]:
        return (await self.run_json(["futures", "tickers", "-o", "json"])).json_data


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


def extract_xstock_perp_symbols(payload: Any) -> list[str]:
    symbols: list[str] = []
    if isinstance(payload, dict):
        symbol = payload.get("symbol")
        pair = payload.get("pair")
        if (
            isinstance(symbol, str)
            and isinstance(pair, str)
            and symbol.startswith(("PF_", "PI_"))
            and is_xstock_pair(pair)
        ):
            symbols.append(symbol)
        for value in payload.values():
            symbols.extend(extract_xstock_perp_symbols(value))
    elif isinstance(payload, list):
        for item in payload:
            symbols.extend(extract_xstock_perp_symbols(item))
    return symbols


def extract_xstock_ticker_records(payload: Any) -> list[KrakenTickerRecord]:
    records: list[KrakenTickerRecord] = []
    if isinstance(payload, dict):
        symbol = payload.get("symbol")
        pair = payload.get("pair")
        if (
            isinstance(symbol, str)
            and isinstance(pair, str)
            and symbol.startswith(("PF_", "PI_"))
            and is_xstock_pair(pair)
        ):
            price = first_float(payload, ("markPrice", "last", "indexPrice", "price"))
            if price is not None and price > 0:
                records.append(
                    KrakenTickerRecord(
                        symbol=symbol,
                        pair=pair,
                        price=price,
                        bid=parse_float(payload.get("bid")),
                        ask=parse_float(payload.get("ask")),
                        change24h=parse_float(payload.get("change24h")),
                        volume_quote=parse_float(payload.get("volumeQuote")),
                        raw=payload,
                    )
                )
        for value in payload.values():
            records.extend(extract_xstock_ticker_records(value))
    elif isinstance(payload, list):
        for item in payload:
            records.extend(extract_xstock_ticker_records(item))
    return records


def select_best_xstock_record(payload: Any, allowed_symbols: list[str]) -> KrakenTickerRecord | None:
    allowed = set(allowed_symbols)
    candidates = [record for record in extract_xstock_ticker_records(payload) if record.symbol in allowed]
    candidates = [record for record in candidates if record.ask is None or record.bid is None or record.ask >= record.bid]
    if not candidates:
        return None
    return max(candidates, key=tournament_opportunity_score)


def tournament_opportunity_score(record: KrakenTickerRecord) -> float:
    change = abs(record.change24h or 0.0)
    volume = max(record.volume_quote or 0.0, 1.0)
    spread_bps = 25.0
    if record.bid and record.ask and record.price:
        spread_bps = max(((record.ask - record.bid) / record.price) * 10000.0, 1.0)
    return change * (volume ** 0.25) / spread_bps


def is_xstock_pair(pair: str) -> bool:
    base = pair.split(":", 1)[0]
    return base.endswith("x") and len(base) > 1 and base[:-1].isalnum()


def is_xstock_perp_symbol(symbol: str) -> bool:
    s = symbol.upper()
    return (
        ("XSTOCK" in s or s.endswith("X") or ".X" in s or re.match(r"^PF_[A-Z0-9]+XUSD$", s) is not None)
        and ("PERP" in s or s.startswith("PF_") or s.startswith("PI_"))
    )


def extract_price_for_symbol(payload: Any, symbol: str) -> float | None:
    if isinstance(payload, dict):
        symbol_matches = any(isinstance(v, str) and v == symbol for v in payload.values())
        if symbol_matches:
            for key in ("price", "last", "markPrice", "mark_price", "lastPrice", "last_price"):
                value = payload.get(key)
                parsed = parse_float(value)
                if parsed is not None:
                    return parsed
        for value in payload.values():
            found = extract_price_for_symbol(value, symbol)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = extract_price_for_symbol(item, symbol)
            if found is not None:
                return found
    return None


def parse_float(value: Any) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def first_float(payload: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        parsed = parse_float(payload.get(key))
        if parsed is not None:
            return parsed
    return None


def format_cli_number(value: float) -> str:
    return f"{value:.8f}".rstrip("0").rstrip(".")


def redact_args(args: list[str]) -> list[str]:
    redacted: list[str] = []
    skip_next = False
    for arg in args:
        if skip_next:
            redacted.append("[REDACTED]")
            skip_next = False
            continue
        redacted.append(arg)
        if arg in {"--api-key", "--api-secret", "--api-secret-file"}:
            skip_next = True
    return redacted
