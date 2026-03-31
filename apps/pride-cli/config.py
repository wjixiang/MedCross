import os

from pydantic import BaseModel

class IPrideCliConfig(BaseModel):
    datasetPath: str


PrideCliConfig = IPrideCliConfig(
    datasetPath=os.getenv('DATASET_PATH') or './dataset'
)