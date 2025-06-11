class KamiAPIError(Exception):
    """Exception raised when the Kami API returns an error response."""

    def __init__(
        self,
        error_message: str,
        error_type: str = None,  # pyright: ignore[reportArgumentType]
    ):
        self.error_message = error_message
        self.error_type = error_type
        err_type_str = f"type: {error_type} " if error_type else ""
        super().__init__(f"Kami API {err_type_str} Error: {error_message}")
