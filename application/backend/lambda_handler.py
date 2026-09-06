"""Lambda entrypoint. Uses Mangum to bridge FastAPI to the Lambda event.

Wire this as the handler when the container image is built.
"""

from mangum import Mangum

from main import app

# Mangum converts AWS Lambda events into the HTTP requests FastAPI expects.
handler = Mangum(app, lifespan="off")
