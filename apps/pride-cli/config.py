import os

from pydantic import BaseModel

class IPrideCliConfig(BaseModel):
    datasetPath: str
    host: str


PrideCliConfig = IPrideCliConfig(
    datasetPath=os.getenv('DATASET_PATH') or './dataset',
    host=os.getenv('HOST') or 'http://localhost:8000',
)