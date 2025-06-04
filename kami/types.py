from typing import Any, List, Tuple

from pydantic import BaseModel, Field, field_validator


class SubnetHyperparameters(BaseModel):
    """Configuration parameters for a subnet's behavior and constraints.

    This class defines all the hyperparameters that control how a subnet operates,
    including consensus mechanisms, registration limits, and economic parameters.
    """

    rho: int
    kappa: int
    immunityPeriod: int
    minAllowedWeights: int
    maxWeightsLimit: int
    tempo: int
    minDifficulty: int
    maxDifficulty: int
    difficulty: int
    weightsVersion: int
    weightsRateLimit: (
        int | str
    )  # TODO: fix on kami side for netuid 0 to return max u64 integer
    adjustmentInterval: int
    activityCutoff: int
    registrationAllowed: bool
    targetRegsPerInterval: int
    minBurn: int
    maxBurn: int
    bondsMovingAvg: int
    maxRegsPerBlock: int
    servingRateLimit: int
    maxValidators: int
    adjustmentAlpha: int
    commitRevealPeriod: int
    commitRevealWeightsEnabled: bool
    alphaHigh: int
    alphaLow: int
    liquidAlphaEnabled: bool

    @field_validator(
        "difficulty", "minDifficulty", "maxDifficulty", "adjustmentAlpha", mode="before"
    )
    @classmethod
    def validate_hex_number(cls, v: Any) -> Any:
        if isinstance(v, str) and v.startswith("0x"):
            return int(v, 16)

        if isinstance(v, int):
            return v
        return v

    class Config:
        arbitrary_types_allowed = False


class ServeAxonPayload(BaseModel):
    """Payload for registering an axon to serve requests on the network.

    Contains network configuration details needed to make an axon discoverable
    and accessible to other network participants.
    """

    netuid: int
    version: int = 1
    ip: int
    port: int
    ipType: int = Field(default=4, description="4 for IPv4 or 6 for IPv6")
    protocol: int = Field(default=4, description="Should be the same for ipType")
    placeholder1: int = 0
    placeholder2: int = 0


class SetWeightsPayload(BaseModel):
    """Payload for setting validator weights in the consensus mechanism.

    Used by validators to assign weights to miners based on their performance,
    which influences the distribution of incentives and trust scores.
    """

    netuid: int
    dests: List[int]
    weights: List[int]  # Normalized weights
    version_key: int


class CommitRevealPayload(BaseModel):
    """Payload for the commit-reveal weight setting mechanism.

    Enables a two-phase weight setting process where validators first commit
    to their weights cryptographically, then reveal them in a later round.
    """

    netuid: int
    commit: str
    revealRound: int


class MovingPrice(BaseModel):
    """Represents a moving average price with bit precision.

    Used for tracking price movements in the network's economic model.
    """

    bits: int


class SubnetIdentity(BaseModel):
    """Identity information for a subnet.

    Contains metadata that describes the subnet's purpose, contact information,
    and relevant links for community engagement and development.
    """

    subnetName: str
    githubRepo: str
    subnetContact: str
    subnetUrl: str
    discord: str
    description: str
    additional: str


class IdentitiesInfo(BaseModel):
    """Identity information for network participants.

    Contains public profile information for miners, validators, or other
    network participants to facilitate identification and communication.
    """

    name: str
    url: str
    githubRepo: str
    image: str
    discord: str
    description: str
    additional: str


class AxonInfo(BaseModel):
    """Information about an axon's network configuration and identity.

    Represents a network endpoint that can receive and process requests,
    including its network address, protocol details, and associated keys.
    """

    block: int
    version: int
    ip: str
    port: int
    ipType: int
    protocol: int
    placeholder1: int
    placeholder2: int
    # WARN: here we only set to default so pydantic validation passes for SubnetMetagraph
    # you must remember to fill these in
    hotkey: str = Field(default="")
    coldkey: str = Field(default="")


class SubnetMetagraph(BaseModel):
    """Complete state representation of a subnet's metagraph.

    Contains all information about a subnet including its participants,
    their relationships, economic metrics, and current network state.
    This is the primary data structure for understanding subnet dynamics.
    """

    netuid: int
    name: str
    symbol: str
    identity: SubnetIdentity
    networkRegisteredAt: int
    ownerHotkey: str
    ownerColdkey: str
    block: int
    tempo: int
    lastStep: int
    blocksSinceLastStep: int
    subnetEmission: int
    alphaIn: float
    alphaOut: float
    taoIn: float
    alphaOutEmission: float
    alphaInEmission: float
    taoInEmission: float
    pendingAlphaEmission: float
    pendingRootEmission: float
    subnetVolume: float
    movingPrice: MovingPrice
    rho: int
    kappa: int
    # # TODO: not sure if this field is present
    # minAllowedWeights: int
    # # TODO: not sure if this field is present
    # maxAllowedWeights: int
    weightsVersion: int
    weightsRateLimit: (
        int | str
    )  # TODO: fix on kami side for netuid 0 to return max u64 integer
    activityCutoff: int
    maxValidators: int
    numUids: int
    maxUids: int
    burn: int
    difficulty: int
    registrationAllowed: bool
    powRegistrationAllowed: bool
    immunityPeriod: int
    minDifficulty: int
    maxDifficulty: int
    minBurn: int
    maxBurn: int
    adjustmentAlpha: int
    adjustmentInterval: int
    targetRegsPerInterval: int
    maxRegsPerBlock: int
    servingRateLimit: int
    commitRevealWeightsEnabled: bool
    commitRevealPeriod: int
    liquidAlphaEnabled: bool
    alphaHigh: int
    alphaLow: int
    bondsMovingAvg: int
    hotkeys: List[str]
    coldkeys: List[str]
    identities: List[IdentitiesInfo | None]
    axons: List[AxonInfo]
    active: List[bool]
    validatorPermit: List[bool]
    pruningScore: List[int]
    lastUpdate: List[int]
    emission: List[float]
    dividends: List[float]
    incentives: List[float]
    consensus: List[float]
    trust: List[float]
    rank: List[float]
    blockAtRegistration: List[int]
    alphaStake: List[float]
    taoStake: List[float]
    totalStake: List[float]
    taoDividendsPerHotkey: List[Tuple[str, float]]
    alphaDividendsPerHotkey: List[Tuple[str, float]]

    @field_validator(
        "difficulty", "minDifficulty", "maxDifficulty", "adjustmentAlpha", mode="before"
    )
    def validate_hex_number(cls, v: Any) -> Any:
        if isinstance(v, str) and v.startswith("0x"):
            return int(v, 16)
        elif isinstance(v, int):
            return v
        return v

    class Config:
        arbitrary_types_allowed = False
