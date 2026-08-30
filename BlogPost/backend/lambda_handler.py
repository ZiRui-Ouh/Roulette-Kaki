"""Lambda entrypoint. Uses Mangum to bridge FastAPI to the Lambda event.

Wire this as the handler when the Dockerfile lands in Phase 6.
"""

from mangum import Mangum

from main import app

handler = Mangum(app, lifespan="off")
