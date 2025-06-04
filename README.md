# kami-client

Python client version to call functions available in [Kami](https://github.com/tensorplex-labs/kami)

# Requirements

Setup your environment variables `KAMI_HOST` and `KAMI_HOST` in your .env file.
Alternatively you may pass in `host` and `port` params when using KamiClient.


# Example Usage

```python
from kami import KamiClient
kami_client = KamiClient(host="localhost", port="3000")
```
