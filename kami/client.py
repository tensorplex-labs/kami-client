import json
import os
from functools import wraps
from typing import Any, Dict

import aiohttp
from bittensor_drand import get_encrypted_commit  # type: ignore
from dotenv import load_dotenv
from loguru import logger
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_exponential

from .exceptions import KamiAPIError
from .types import (
    AxonInfo,
    CommitRevealPayload,
    CommitTimelockedPayload,
    KeyringPairInfo,
    ServeAxonPayload,
    SetWeightsPayload,
    SubnetHyperparameters,
    SubnetMetagraph,
)

load_dotenv()


def check_response_for_error(response_data: Dict[str, Any]) -> None:
    """Check if the response contains an error field and raise KamiAPIError if found."""
    if "error" in response_data and response_data["error"]:
        error_data = response_data.get("error")
        error_type = None
        if isinstance(error_data, str):
            error_message = error_data
        elif isinstance(error_data, dict):
            error_message = error_data.get("message", str(error_data))
            error_type = error_data.get("type")
        else:
            error_message = str(error_data)
        raise KamiAPIError(error_message, error_type)

    if "statusCode" in response_data and not (
        200 <= response_data["statusCode"] <= 299
    ):
        status_code = response_data["statusCode"]
        message = response_data.get("message", "")
        error_message = f"HTTP error: {status_code}" + (
            f" - {message}" if message else ""
        )
        raise KamiAPIError(error_message)


def retry_on_error(
    max_retries: int = 10,
    multiplier: float = 1.5,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
):
    """Decorator that adds tenacity retry logic and checks for API errors in response.

    Args:
        max_retries: Maximum number of retry attempts (default: 10)
        multiplier: Exponential backoff multiplier (default: 1.5)
        min_wait: Minimum wait time in seconds (default: 1.0)
        max_wait: Maximum wait time in seconds (default: 10.0)
    """

    def decorator(func):
        @wraps(func)
        @retry(
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential(multiplier=multiplier, min=min_wait, max=max_wait),
            before_sleep=before_sleep_log(logger, "WARNING"),
            reraise=True,
        )
        async def wrapper(*args, **kwargs):
            response = await func(*args, **kwargs)
            check_response_for_error(response)
            return response

        return wrapper

    return decorator


def get_client(
    conn_limit: int = None,
    limit_per_host: int = None,  # pyright: ignore[reportArgumentType]
) -> aiohttp.ClientSession:  # type: ignore[assignment]
    if not conn_limit:
        conn_limit = 256
    if not limit_per_host:
        limit_per_host = 10

    return aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(
            ssl=False,
            limit=conn_limit,
            limit_per_host=limit_per_host,
            enable_cleanup_closed=True,
        )
    )


def resolve_env_var(env_var: str, default_value: str):
    value: str = None  # type: ignore[assignment]
    env_value = os.getenv(env_var, None)
    if env_value:
        value = env_value
        logger.info(f"{env_var}={env_value}")
    else:
        logger.info(
            f"{env_var} env var not specified, defaulting to {env_var}={default_value}"
        )
        value = default_value
    return value


class KamiClient:
    """
    Kami is a class that handles the connection to the Kami API.
    """

    def __init__(self, host: str = None, port: str = None):  # type: ignore[assignment]
        _host = host or resolve_env_var("KAMI_HOST", "localhost")
        if not _host:
            raise ValueError("Could not resolve Kami host")

        _port = port or resolve_env_var("KAMI_PORT", "3000")
        if not _port:
            raise ValueError("Could not resolve Kami port")

        self.url = f"http://{_host}:{_port}"
        self.session: aiohttp.ClientSession | None = None
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _ensure_session(self):
        """Recreate session if it's closed"""
        if not self.session or self.session.closed:
            self.session = get_client()

    async def close(self):
        try:
            await self.session.close()
        except Exception:
            pass

    @retry_on_error(multiplier=1.5)
    async def get(
        self, endpoint: str, params: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """
        Send a GET request to the Kami API.

        Args:
            endpoint (str): The API endpoint to send the request to.
            params (Dict[str, Any] | None): Optional query parameters to include in the request.

        Returns:
            Dict[str, Any]: The JSON response from the API.
        """
        try:
            await self._ensure_session()
            if self.session is None:
                raise ValueError("Session is not initialized.")
            url = f"{self.url}/{endpoint}"
            async with self.session.get(
                url, headers=self.headers, params=params
            ) as response:
                return await response.json()
        except aiohttp.ClientError:
            raise
        except json.decoder.JSONDecodeError as e:
            logger.error(f"Error decoding JSON response: {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise e

    @retry_on_error(multiplier=1.5)
    async def post(
        self, endpoint: str, data: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """
        Send a POST request to the Kami API.

        Args:
            endpoint (str): The API endpoint to send the request to.
            data (Dict[str, Any] | None): Optional data to include in the request body.

        Returns:
            Dict[str, Any]: The JSON response from the API.
        """
        try:
            await self._ensure_session()
            if self.session is None:
                raise ValueError("Session is not initialized.")
            url = f"{self.url}/{endpoint}"
            async with self.session.post(
                url, headers=self.headers, json=data
            ) as response:
                return await response.json()
        except aiohttp.ClientError:
            raise
        except json.decoder.JSONDecodeError as e:
            logger.error(f"Error decoding JSON response: {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise e

    async def get_metagraph(self, netuid: int) -> SubnetMetagraph:
        """
        Get the metagraph for a given netuid.

        Args:
            netuid (int): The netuid to get the metagraph for.

        Returns:
            SubnetMetagraph: The subnet metagraph object.
        """
        get_metagraph = await self.get(f"chain/subnet-metagraph/{netuid}")
        metagraph = get_metagraph.get("data", {})
        metagraph = SubnetMetagraph.model_validate(metagraph)
        for hotkey, coldkey, axon in zip(
            metagraph.hotkeys, metagraph.coldkeys, metagraph.axons
        ):
            axon.coldkey = coldkey
            axon.hotkey = hotkey
        return metagraph

    async def get_hotkeys(self, netuid: int) -> list[str]:
        """
        Get the hotkeys for a given netuid.

        Args:
            netuid (int): The netuid to get the hotkeys for.

        Returns:
            list[str]: The list of hotkeys for the given netuid.
        """
        metagraph = await self.get_metagraph(netuid)
        return metagraph.hotkeys

    async def get_axons(self, netuid: int) -> list[AxonInfo]:
        """
        Get the axons for a given netuid.

        Args:
            netuid (int): The netuid to get the axons for.

        Returns:
            list[AxonInfo]: The list of axons for the given netuid.
        """
        metagraph = await self.get_metagraph(netuid=netuid)
        if len(metagraph.axons) == 0:
            logger.warning("No axons found in metagraph response.")

        for hotkey, coldkey, axon in zip(
            metagraph.hotkeys, metagraph.coldkeys, metagraph.axons
        ):
            axon.coldkey = coldkey
            axon.hotkey = hotkey

        return [AxonInfo.model_validate(axon) for axon in metagraph.axons]

    async def get_current_block(self) -> int:
        """
        tcurrent finalized block number.

                Returns:
                    int: The current finalized block number.
        """
        result = await self.get("chain/latest-block")
        latest_block = result.get("data", {}).get("blockNumber", "")
        return int(latest_block)

    async def get_subnet_hyperparameters(self, netuid: int) -> SubnetHyperparameters:
        """
        Get the subnet hyperparameters for a given netuid.

        Args:
            netuid (int): The netuid to get the hyperparameters for.

        Returns:
            SubnetHyperparameters: The subnet hyperparameters object.
        """
        result = await self.get(f"chain/subnet-hyperparameters/{netuid}")
        hyperparameters = result.get("data", {})
        return SubnetHyperparameters.model_validate(hyperparameters)

    async def is_hotkey_registered(
        self, netuid: int, hotkey: str, block: int | None = None
    ) -> bool:
        """
        Check if a hotkey is registered in a subnet.

        Args:
            netuid (int): The netuid to check.
            hotkey (str): The hotkey to check.
            block (int | None): Optional block number to check at. If None, uses the latest block.

        Returns:
            bool: True if the hotkey is registered, False otherwise.
        """
        result = dict[str, bool]()
        if block is None:
            result = await self.get(
                f"chain/check-hotkey?netuid={netuid}&hotkey={hotkey}"
            )
        else:
            result = await self.get(
                f"chain/check-hotkey?netuid={netuid}&hotkey={hotkey}&block={block}"
            )
        return result.get("data", {}).get("isHotkeyValid", False)

    async def serve_axon(self, payload: ServeAxonPayload) -> Dict[str, Any]:
        """
        Register an axon server with the network.

        Args:
            payload (ServeAxonPayload): The payload containing axon information.

        Returns:
            Dict[str, Any]: The JSON response from the API.
        """
        return await self.post("chain/serve-axon", data=payload.model_dump())

    async def set_weights(self, payload: SetWeightsPayload) -> Dict[str, Any]:
        """
        Set weights for neurons in the network.

        Handles both standard weight setting and commit-reveal weight setting
        based on subnet hyperparameters.

        Args:
            payload (SetWeightsPayload): The payload containing weights information.

        Returns:
            Dict[str, Any]: The JSON response from the API.
        """
        get_hpams: SubnetHyperparameters = await self.get_subnet_hyperparameters(
            payload.netuid
        )
        if get_hpams.commitRevealWeightsEnabled:
            tempo = get_hpams.tempo
            reveal_period = get_hpams.commitRevealPeriod
            if tempo == 0 or reveal_period == 0:
                raise ValueError(
                    "Tempo and reveal round must be greater than 0 for commit reveal weights."
                )

            logger.info(
                f"Commit reveal weights enabled: tempo: {tempo}, reveal_period: {reveal_period}"
            )

            # Encrypt `commit_hash` with t-lock and `get reveal_round`
            commit_for_reveal, reveal_round = get_encrypted_commit(  # type: ignore
                uids=payload.dests,
                weights=payload.weights,
                version_key=payload.version_key,
                tempo=tempo,
                current_block=await self.get_current_block(),
                netuid=payload.netuid,
                subnet_reveal_period_epochs=reveal_period,
            )

            logger.info(f"Commit for reveal: {commit_for_reveal.hex()}")  # type: ignore
            logger.info(f"Reveal round: {reveal_round}")

            if not commit_for_reveal or not reveal_round:
                raise ValueError(
                    "Failed to generate commit for reveal. Ensure that tempo and reveal round are set correctly."
                )

            cr_payload: CommitRevealPayload = CommitRevealPayload(
                netuid=payload.netuid,
                commit=commit_for_reveal.hex(),  # type: ignore
                revealRound=reveal_round,  # type: ignore
            )

            return await self.post(
                "chain/set-commit-reveal-weights",
                data=cr_payload.model_dump(),
            )
        return await self.post("chain/set-weights", data=payload.model_dump())

    async def set_timelocked_weights(
        self, payload: SetWeightsPayload
    ) -> Dict[str, Any]:
        """
        Set weights for neurons in the network.

        Handles both standard weight setting and commit-timelocked weight setting
        based on subnet hyperparameters.

        Args:
            payload (SetWeightsPayload): The payload containing weights information.

        Returns:
            Dict[str, Any]: The JSON response from the API.
        """
        get_hpams: SubnetHyperparameters = await self.get_subnet_hyperparameters(
            payload.netuid
        )
        if get_hpams.commitRevealWeightsEnabled:
            tempo = get_hpams.tempo
            reveal_period = get_hpams.commitRevealPeriod
            if tempo == 0 or reveal_period == 0:
                raise ValueError(
                    "Tempo and reveal round must be greater than 0 for commit reveal weights."
                )

            logger.info(
                f"Commit reveal weights enabled: tempo: {tempo}, reveal_period: {reveal_period}"
            )

            keypair_info: KeyringPairInfo = await self.get_keyringpair()
            # Convert dict[str, int] to bytes
            hotkey = bytes(
                keypair_info.keyringPair.publicKey[str(i)] for i in range(32)
            )

            # Encrypt `commit_hash` with t-lock and `get reveal_round`
            commit_for_reveal, reveal_round = get_encrypted_commit(  # type: ignore
                uids=payload.dests,
                weights=payload.weights,
                version_key=payload.version_key,
                tempo=tempo,
                current_block=await self.get_current_block(),
                netuid=payload.netuid,
                subnet_reveal_period_epochs=reveal_period,
                block_time=12.0,
                hotkey=hotkey,
            )

            logger.info(f"Commit for reveal: {commit_for_reveal.hex()}")  # type: ignore
            logger.info(f"Reveal round: {reveal_round}")

            if not commit_for_reveal or not reveal_round:
                raise ValueError(
                    "Failed to generate commit for reveal. Ensure that tempo and reveal round are set correctly."
                )

            cr_payload: CommitTimelockedPayload = CommitTimelockedPayload(
                netuid=payload.netuid,
                commit=commit_for_reveal.hex(),  # type: ignore
                revealRound=reveal_round,  # type: ignore
                commitRevealVersion=4,
            )

            return await self.post(
                "chain/set-timelocked-weights",
                data=cr_payload.model_dump(),
            )
        raise KamiAPIError(
            "Standard weight setting is not supported when commit-reveal is disabled"
        )

    async def sign_message(self, message: str) -> str:
        response = await self.post(
            "substrate/sign-message/sign", data={"message": message}
        )
        response_data = response.get("data", {})
        signature: str = response_data.get("signature")
        if not response_data or not signature:
            logger.error(
                f"Failed to sign message using Kami due to {response_data.get('error')}"
            )
        return signature

    async def verify(self, hotkey: str, message: str, signature: str) -> bool:
        if not signature.startswith("0x"):
            raise ValueError(
                f"Expected signature to be a hex string!, got: {signature=}"
            )

        response = await self.post(
            "substrate/sign-message/verify",
            data={"message": message, "signature": signature, "signeeAddress": hotkey},
        )
        response_data = response.get("data", {})
        is_valid: bool = response_data.get("valid", False)
        if not response_data:
            logger.error(
                f"Failed to get response from Kami while verifying signature: {signature}"
            )

        return is_valid

    async def get_keyringpair(self) -> KeyringPairInfo:
        """Get the keyring pair info based on WALLET_COLDKEY and WALLET_HOTKEY set in environment variables"""
        result = await self.get("substrate/keyring-pair-info")
        if error := result.get("error"):
            raise ValueError(
                f"Error occurred while trying to get keyring pair: {error}"
            )
        keyring_pair_info = result.get("data", {})
        return KeyringPairInfo.model_validate(keyring_pair_info)
