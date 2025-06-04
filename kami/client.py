import json
from typing import Any, Dict

import os
import aiohttp
from bittensor_drand import get_encrypted_commit  # type: ignore
from loguru import logger
from dotenv import load_dotenv


from .types import (
    AxonInfo,
    CommitRevealPayload,
    ServeAxonPayload,
    SetWeightsPayload,
    SubnetHyperparameters,
    SubnetMetagraph,
)

load_dotenv()


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
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """
        Close the aiohttp session.
        """
        if self.session is not None:
            await self.session.close()

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
        except aiohttp.ClientError as e:
            message = f"Error connecting to Kami API: {e}"
            logger.error(message)
            raise RuntimeError(f"Error connecting to Kami API: {e}") from e
        except json.decoder.JSONDecodeError as e:
            logger.error(f"Error decoding JSON response: {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise e

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
        except aiohttp.ClientError as e:
            message = f"Error connecting to Kami API: {e}"
            logger.error(message)
            raise RuntimeError(message) from e
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
